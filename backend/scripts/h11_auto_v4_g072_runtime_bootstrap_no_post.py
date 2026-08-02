"""G072 resident bootstrap; no broker, credential, or notification access."""

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
from app.services.h11_v4_g072_switch_control import (  # noqa: E402
    G072_GENERATION_LABEL,
    G072Error,
    G072ProcessLock,
    G072ResidentSupervisor,
    engage_g072_halt,
    verify_g072_review_artifacts,
)
from app.services.h11_v4_unattended_live_arm_state import (  # noqa: E402
    V4UnattendedLiveArmStore,
)
from app.services.h11_v4_unattended_live_paths import (  # noqa: E402
    v4_unattended_live_arm_state_path,
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
        repository=repository,
        implementation_digest=reviewed,
    )
    if (
        generation.generation_label != G072_GENERATION_LABEL
        or reviewed != args.expected_reviewed_files_digest
        or generation.digest != args.expected_generation_digest
    ):
        return 4
    verify_g072_review_artifacts(
        repository=repository,
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed,
    )
    state_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=generation.digest,
    )
    lock = G072ProcessLock(state_root)
    try:
        lock.acquire()
        arm_store = V4UnattendedLiveArmStore(
            v4_unattended_live_arm_state_path(generation_digest=generation.digest)
        )
        supervisor = G072ResidentSupervisor(
            state_root=state_root,
            generation_digest=generation.digest,
            reviewed_files_digest=reviewed,
        )
        while True:
            current = arm_store.check(
                expected_generation_digest=generation.digest,
                expected_reviewed_files_digest=reviewed,
            )
            supervisor.tick(now_utc=datetime.now(UTC), arm_on=current.armed)
            time.sleep(15)
    except (KeyboardInterrupt, G072Error, OSError, ValueError):
        engage_g072_halt(state_root=state_root, reason="G072_RUNTIME_TERMINATED")
        return 4
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
