"""Single-attempt G069 operation 60 with real service-state verification."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation  # noqa: E402
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root  # noqa: E402
from app.services.h11_v4_g069_unattended_activation_no_post import (  # noqa: E402
    G069_GENERATION_LABEL,
    G069_OPERATION_OUTCOME_FILE,
    G069_OPERATION_STARTED_FILE,
    V4G069ActivationError,
    begin_g069_one_use_marker,
    record_g069_one_use_outcome,
    verify_g069_generation_contract,
    verify_g069_scheduler_binding,
    write_g069_persistent_halt_no_post,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest  # noqa: E402


def _wait_for_g069_scheduler_readiness(
    *,
    verifier: Callable[[], None],
    readiness_timeout_seconds: int,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    """Start a fresh finite readiness window after installation has completed."""

    deadline = monotonic() + readiness_timeout_seconds
    while monotonic() < deadline:
        try:
            verifier()
            return
        except V4G069ActivationError:
            sleeper(1.0)
    raise V4G069ActivationError("G069_OPERATION_60_READINESS_TIMEOUT")


def run_once(
    *,
    repository: Path,
    installer_timeout_seconds: int = 90,
    readiness_timeout_seconds: int = 60,
) -> int:
    reviewed = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed
    )
    if generation.generation_label != G069_GENERATION_LABEL:
        print("status=G069_GENERATION_REQUIRED broker_write=false actual_post_count=0")
        return 2
    verify_g069_generation_contract(generation=generation, repository=repository)
    state_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation.digest
    )
    marker = {
        "schema": "H11_V4_G069_OPERATION_60_RESULT_V1",
        "generation_label": G069_GENERATION_LABEL,
        "generation_digest": generation.digest,
        "reviewed_files_digest": reviewed,
        "broker_write": False,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
    }
    try:
        begin_g069_one_use_marker(
            state_root=state_root,
            filename=G069_OPERATION_STARTED_FILE,
            payload={**marker, "status": "STARTED"},
        )
    except V4G069ActivationError:
        print(
            "status=G069_OPERATION_60_ALREADY_STARTED_NO_RETRY "
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
        / "Library/LaunchAgents/com.fxstrategylab.h11v4.unattended.scheduler.plist"
    )
    try:
        completed = subprocess.run(
            command,
            cwd=repository / "backend",
            check=False,
            timeout=installer_timeout_seconds,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise V4G069ActivationError("G069_OPERATION_60_INSTALL_FAILED")
        def verify_readiness() -> None:
                verify_g069_scheduler_binding(
                    generation=generation,
                    plist_path=plist_path,
                    state_root=state_root,
                    now_utc=datetime.now(UTC),
                    require_operation_60_passed=False,
                )
        _wait_for_g069_scheduler_readiness(
            verifier=verify_readiness,
            readiness_timeout_seconds=readiness_timeout_seconds,
        )
        record_g069_one_use_outcome(
            state_root=state_root,
            filename=G069_OPERATION_OUTCOME_FILE,
            payload=marker,
            outcome="PASSED",
        )
        print(
            "status=G069_OPERATION_60_PASSED_NO_POST "
            "broker_write=false actual_post_count=0"
        )
        return 0
    except Exception:
        try:
            record_g069_one_use_outcome(
                state_root=state_root,
                filename=G069_OPERATION_OUTCOME_FILE,
                payload=marker,
                outcome="UNKNOWN",
            )
            write_g069_persistent_halt_no_post(
                state_root=state_root,
                generation_digest=generation.digest,
                reviewed_files_digest=reviewed,
                reason="G069_OPERATION_60_UNKNOWN",
            )
        except V4G069ActivationError:
            pass
        print("status=G069_OPERATION_60_UNKNOWN_HALT broker_write=false actual_post_count=0")
        return 4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    return run_once(repository=args.repository.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
