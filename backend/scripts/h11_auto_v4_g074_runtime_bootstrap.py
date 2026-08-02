"""G074 resident runtime bootstrap with no external transport."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation  # noqa: E402
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root  # noqa: E402
from app.services.h11_v4_g074_runtime import (  # noqa: E402
    G074_GENERATION_LABEL,
    G074EntryDispatcher,
    G074Error,
    G074ExitDispatcher,
    G074FrozenStrategyEvaluator,
    G074OneShotActionDispatcher,
    G074ProcessLock,
    G074ResidentSupervisor,
    engage_g074_halt,
    load_g074_release_capability_digest,
    run_g074_reconciliation_cycle_once,
    verify_g074_review_artifacts,
)
from app.services.h11_v4_unattended_live_arm_state import V4UnattendedLiveArmStore  # noqa: E402
from app.services.h11_v4_unattended_live_paths import (  # noqa: E402
    v4_unattended_live_arm_state_path,  # noqa: E402
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-reviewed-files-digest", required=True)
    parser.add_argument("--expected-generation-digest", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repository = args.repository.resolve()
    if not repository.is_dir():
        return 4
    reviewed = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed
    )
    if (
        generation.generation_label != G074_GENERATION_LABEL
        or reviewed != args.expected_reviewed_files_digest
        or generation.digest != args.expected_generation_digest
    ):
        return 4
    verify_g074_review_artifacts(
        repository=repository, generation_digest=generation.digest, reviewed_files_digest=reviewed
    )
    state_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation.digest
    )
    lock = G074ProcessLock(state_root)
    try:
        lock.acquire()
        arm_store = V4UnattendedLiveArmStore(
            v4_unattended_live_arm_state_path(generation_digest=generation.digest)
        )
        supervisor = G074ResidentSupervisor(
            state_root=state_root,
            generation_digest=generation.digest,
            reviewed_files_digest=reviewed,
        )
        live_port = None
        while True:
            current = arm_store.check(
                expected_generation_digest=generation.digest,
                expected_reviewed_files_digest=reviewed,
            )
            try:
                release_digest = load_g074_release_capability_digest(
                    state_root=state_root,
                    generation_digest=generation.digest,
                    reviewed_files_digest=reviewed,
                )
            except G074Error:
                release_digest = None
            if release_digest is not None and live_port is None:
                from app.h11_auto.runtime_safety import DeadManStore, PhaseBRiskStore
                from app.h11_auto.v4_gmo_generation import (
                    v4_gmo_dead_man_policy,
                    v4_gmo_risk_policy,
                )
                from app.services.h11_v4_g074_live_runtime import (
                    G074LiveActionPort,
                    G074PrivateReconciler,
                )
                from app.services.h11_v4_unattended_live_heartbeat_chain import (
                    V4HeartbeatChainStore,
                    v4_unattended_runtime_heartbeat_policy,
                )

                live_port = G074LiveActionPort(
                    repository=repository,
                    generation=generation,
                    process_lock=lock,
                )
                actions = G074OneShotActionDispatcher.bound(
                    state_root=state_root,
                    port=live_port,
                    generation_digest=generation.digest,
                    reviewed_files_digest=reviewed,
                    release_capability_digest=release_digest,
                    strategy_artifact_digest=generation.frozen_design_digest or "",
                )
                supervisor.reconciliation_runner = lambda cycle, observed: (
                    run_g074_reconciliation_cycle_once(
                        state_root=state_root,
                        generation_digest=generation.digest,
                        reviewed_files_digest=reviewed,
                        cycle_id=cycle,
                        reconciler=G074PrivateReconciler(
                            repository=repository, generation=generation
                        ),
                        now_utc=observed,
                    )
                )
                supervisor.strategy_evaluator = G074FrozenStrategyEvaluator(
                    source=live_port,
                    generation_digest=generation.digest,
                    reviewed_files_digest=reviewed,
                    strategy_artifact_digest=generation.frozen_design_digest or "",
                )
                supervisor.entry_dispatcher = G074EntryDispatcher(actions=actions)
                supervisor.exit_dispatcher = G074ExitDispatcher(actions=actions)
                supervisor.exit_reason_provider = live_port.time_exit_reason
                risk_store = PhaseBRiskStore(
                    state_root / "risk.json", policy=v4_gmo_risk_policy()
                )
                if not risk_store.path.exists():
                    risk_store.save(risk_store.load())
                runtime_dead_man = DeadManStore(
                    state_root / "dead-man-runtime.json", policy=v4_gmo_dead_man_policy()
                )
                runtime_chain = V4HeartbeatChainStore(
                    state_root / "unattended-heartbeat-chain.json",
                    policy=v4_unattended_runtime_heartbeat_policy(),
                )
            if live_port is not None:
                observed = datetime.now(UTC)
                runtime_dead_man.heartbeat(heartbeat_utc=observed)
                runtime_chain.beat(now_utc=observed)
            supervisor.tick(now_utc=datetime.now(UTC), arm_on=current.armed)
            time.sleep(15)
    except (KeyboardInterrupt, G074Error, OSError, ValueError):
        engage_g074_halt(state_root=state_root, reason="G074_RUNTIME_TERMINATED")
        return 4
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
