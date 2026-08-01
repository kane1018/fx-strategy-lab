"""Single-attempt G067 operation 60 wrapper."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation  # noqa: E402
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root  # noqa: E402
from app.services.h11_v4_g067_runtime_result_no_post import (  # noqa: E402
    begin_g067_operation_60_no_post,
    record_g067_operation_60_outcome_no_post,
)
from app.services.h11_v4_g067_unattended_activation import (  # noqa: E402
    G067_GENERATION_LABEL,
    V4G067ActivationError,
    verify_g067_generation_activation,
    verify_g067_scheduler_binding,
    write_g067_persistent_halt_no_post,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest  # noqa: E402


def run_once(*, repository: Path, timeout_seconds: int = 50) -> int:
    reviewed_digest = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed_digest
    )
    if generation.generation_label != G067_GENERATION_LABEL:
        print("status=G067_GENERATION_REQUIRED broker_write=false actual_post_count=0")
        return 2
    state_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation.digest
    )
    try:
        begin_g067_operation_60_no_post(
            state_root=state_root,
            generation_digest=generation.digest,
            reviewed_files_digest=reviewed_digest,
        )
    except Exception:
        print(
            "status=G067_OPERATION_60_ALREADY_STARTED_NO_RETRY "
            "broker_write=false actual_post_count=0"
        )
        return 3
    command = [
        str(repository / "backend/.venv/bin/python"),
        "-m",
        "scripts.h11_auto_v4_install_unattended_live_scheduler_launchagent",
        "--repository",
        str(repository),
    ]
    plist_path = (
        Path.home()
        / "Library"
        / "LaunchAgents"
        / "com.fxstrategylab.h11v4.unattended.scheduler.plist"
    )
    try:
        completed = subprocess.run(
            command,
            cwd=repository / "backend",
            check=False,
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError("G067_OPERATION_60_INSTALL_FAILED")
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                verify_g067_generation_activation(
                    generation=generation,
                    state_root=state_root,
                    repository=repository,
                    now_utc=datetime.now(UTC),
                )
                verify_g067_scheduler_binding(
                    generation=generation,
                    plist_path=plist_path,
                    state_root=state_root,
                    now_utc=datetime.now(UTC),
                )
                record_g067_operation_60_outcome_no_post(
                    state_root=state_root,
                    generation_digest=generation.digest,
                    reviewed_files_digest=reviewed_digest,
                    outcome="PASSED",
                )
                print(
                    "status=G067_OPERATION_60_PASSED_NO_POST broker_write=false actual_post_count=0"
                )
                return 0
            except (V4G067ActivationError, OSError, ValueError):
                time.sleep(1)
        raise RuntimeError("G067_OPERATION_60_READINESS_UNKNOWN")
    except Exception:
        try:
            write_g067_persistent_halt_no_post(
                state_root=state_root,
                generation_digest=generation.digest,
                reviewed_files_digest=reviewed_digest,
            )
        finally:
            try:
                record_g067_operation_60_outcome_no_post(
                    state_root=state_root,
                    generation_digest=generation.digest,
                    reviewed_files_digest=reviewed_digest,
                    outcome="UNKNOWN",
                )
            except Exception:
                pass
        print("status=G067_OPERATION_60_UNKNOWN_HALT broker_write=false actual_post_count=0")
        return 4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    return run_once(repository=args.repository.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
