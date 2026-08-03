"""G076 resident no-POST heartbeat bootstrap.

The candidate keeps the resident safety loop independent from UI and from all
external transports.  It does not install services, read credentials, query a
broker, send notifications, or mutate ARM state.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.h11_auto.runtime_safety import DeadManStore  # noqa: E402
from app.h11_auto.v4_gmo_generation import (  # noqa: E402
    load_v4_gmo_frozen_generation,
    v4_gmo_dead_man_policy,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root  # noqa: E402
from app.services.h11_v4_g076_runtime import (  # noqa: E402
    G076_GENERATION_LABEL,
    G076Error,
    G076ProcessLock,
    G076ResidentSupervisor,
    compute_g076_reviewed_files_digest,
    engage_g076_halt,
    verify_g076_review_artifacts,
)
from app.services.h11_v4_unattended_live_heartbeat_chain import (  # noqa: E402
    V4HeartbeatChainStore,
    v4_unattended_runtime_heartbeat_policy,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-reviewed-files-digest", required=True)
    parser.add_argument("--expected-generation-digest", required=True)
    return parser.parse_args()


def _refresh_safety_chain(
    *,
    dead_man: DeadManStore,
    chain: V4HeartbeatChainStore,
    dead_man_path: Path,
    chain_path: Path,
    observed: datetime,
) -> tuple[bool, bool]:
    if dead_man_path.exists():
        dead_man_result = dead_man.evaluate_current(clock=lambda: observed)
        if not dead_man_result.alive or dead_man_result.halt_required:
            return False, False
    if chain_path.exists():
        chain_result = chain.assess(now_utc=observed)
        if not chain_result.continuously_healthy:
            return False, False

    dead_man.heartbeat(heartbeat_utc=observed)
    chain.beat(now_utc=observed)
    dead_man_result = dead_man.evaluate_current(clock=lambda: observed)
    chain_result = chain.assess(now_utc=observed)
    return (
        dead_man_result.alive and not dead_man_result.halt_required,
        chain_result.continuously_healthy,
    )


def main() -> int:
    args = _parse_args()
    repository = args.repository.resolve()
    if not repository.is_dir():
        return 4
    reviewed = compute_g076_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed
    )
    if (
        generation.generation_label != G076_GENERATION_LABEL
        or reviewed != args.expected_reviewed_files_digest
        or generation.digest != args.expected_generation_digest
    ):
        return 4
    verify_g076_review_artifacts(
        repository=repository,
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed,
    )
    state_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation.digest
    )
    lock = G076ProcessLock(
        state_root,
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed,
    )
    dead_man = DeadManStore(
        state_root / "dead-man-runtime.json", policy=v4_gmo_dead_man_policy()
    )
    chain = V4HeartbeatChainStore(
        state_root / "unattended-heartbeat-chain.json",
        policy=v4_unattended_runtime_heartbeat_policy(),
    )
    dead_man_path = state_root / "dead-man-runtime.json"
    chain_path = state_root / "unattended-heartbeat-chain.json"
    try:
        lock.acquire()
        supervisor = G076ResidentSupervisor(
            state_root=state_root,
            generation_digest=generation.digest,
            reviewed_files_digest=reviewed,
        )
        while True:
            observed = datetime.now(UTC)
            dead_man_alive, heartbeat_chain_beat = _refresh_safety_chain(
                dead_man=dead_man,
                chain=chain,
                dead_man_path=dead_man_path,
                chain_path=chain_path,
                observed=observed,
            )
            supervisor.tick(
                now_utc=observed,
                arm_on=False,
                process_lock_single=True,
                dead_man_alive=dead_man_alive,
                heartbeat_chain_beat=heartbeat_chain_beat,
            )
            time.sleep(15)
    except (G076Error, KeyboardInterrupt, OSError, ValueError):
        engage_g076_halt(state_root=state_root, reason="G076_RUNTIME_TERMINATED")
        return 4
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
