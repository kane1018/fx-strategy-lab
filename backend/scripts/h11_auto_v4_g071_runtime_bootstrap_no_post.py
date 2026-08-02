"""G071 resident bootstrap; no external adapter is constructed here."""

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
from app.services.h11_v4_g070_candidate import ArmState  # noqa: E402
from app.services.h11_v4_g071_atomic_activation import (  # noqa: E402
    G071OwnerLock,
    G071ResidentSupervisor,
    engage_g071_halt,
    verify_g071_review_artifacts,
)
from app.services.h11_v4_unattended_live_arm_state import V4UnattendedLiveArmStore  # noqa: E402
from app.services.h11_v4_unattended_live_paths import (  # noqa: E402
    DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    v4_unattended_live_arm_state_path,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest  # noqa: E402


def run_resident_candidate(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    iterations: int | None = None,
    arm_reader=lambda: ArmState.OFF,
) -> None:
    lock = G071OwnerLock(state_root / "process.lock")
    lock.acquire()
    supervisor = G071ResidentSupervisor(state_root, generation_digest, reviewed_files_digest)
    completed = 0
    try:
        while iterations is None or completed < iterations:
            supervisor.tick(now_utc=datetime.now(UTC), arm_state=arm_reader())
            completed += 1
            if iterations is None or completed < iterations:
                time.sleep(15)
    except BaseException:
        engage_g071_halt(state_root=state_root, reason="G071_RESIDENT_TERMINATED_UNKNOWN")
        raise
    finally:
        lock.release()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-generation-digest", required=True)
    parser.add_argument("--expected-reviewed-files-digest", required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    reviewed = compute_reviewed_files_digest(repository=repository)
    if reviewed != args.expected_reviewed_files_digest:
        raise SystemExit("G071_REVIEWED_DIGEST_MISMATCH")
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed
    )
    if generation.digest != args.expected_generation_digest:
        raise SystemExit("G071_GENERATION_DIGEST_MISMATCH")
    verify_g071_review_artifacts(
        repository=repository,
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed,
    )
    state_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation.digest
    )
    arm_store = V4UnattendedLiveArmStore(
        v4_unattended_live_arm_state_path(
            state_root=DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
            generation_digest=generation.digest,
        )
    )

    def arm_reader() -> ArmState:
        check = arm_store.check(
            expected_generation_digest=generation.digest,
            expected_reviewed_files_digest=reviewed,
        )
        return ArmState.ON if check.armed else ArmState.OFF

    run_resident_candidate(
        state_root=state_root,
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed,
        arm_reader=arm_reader,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
