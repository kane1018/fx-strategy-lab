"""Single-attempt G068 operation 60 with real service-state verification."""

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
from app.services.h11_v4_g068_unattended_activation_no_post import (  # noqa: E402
    G068_GENERATION_LABEL,
    G068_OPERATION_OUTCOME_FILE,
    G068_OPERATION_STARTED_FILE,
    V4G068ActivationError,
    begin_g068_one_use_marker,
    record_g068_one_use_outcome,
    verify_g068_generation_contract,
    verify_g068_scheduler_binding,
    write_g068_persistent_halt_no_post,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest  # noqa: E402


def run_once(*, repository: Path, timeout_seconds: int = 50) -> int:
    reviewed = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed
    )
    if generation.generation_label != G068_GENERATION_LABEL:
        print("status=G068_GENERATION_REQUIRED broker_write=false actual_post_count=0")
        return 2
    verify_g068_generation_contract(generation=generation, repository=repository)
    state_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation.digest
    )
    marker = {
        "schema": "H11_V4_G068_OPERATION_60_RESULT_V1",
        "generation_label": G068_GENERATION_LABEL,
        "generation_digest": generation.digest,
        "reviewed_files_digest": reviewed,
        "broker_write": False,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
    }
    try:
        begin_g068_one_use_marker(
            state_root=state_root,
            filename=G068_OPERATION_STARTED_FILE,
            payload={**marker, "status": "STARTED"},
        )
    except V4G068ActivationError:
        print(
            "status=G068_OPERATION_60_ALREADY_STARTED_NO_RETRY "
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
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise V4G068ActivationError("G068_OPERATION_60_INSTALL_FAILED")
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                verify_g068_scheduler_binding(
                    generation=generation,
                    plist_path=plist_path,
                    state_root=state_root,
                    now_utc=datetime.now(UTC),
                )
                record_g068_one_use_outcome(
                    state_root=state_root,
                    filename=G068_OPERATION_OUTCOME_FILE,
                    payload=marker,
                    outcome="PASSED",
                )
                print(
                    "status=G068_OPERATION_60_PASSED_NO_POST "
                    "broker_write=false actual_post_count=0"
                )
                return 0
            except V4G068ActivationError:
                time.sleep(1)
        raise V4G068ActivationError("G068_OPERATION_60_HEALTH_TIMEOUT")
    except Exception:
        try:
            record_g068_one_use_outcome(
                state_root=state_root,
                filename=G068_OPERATION_OUTCOME_FILE,
                payload=marker,
                outcome="UNKNOWN",
            )
            write_g068_persistent_halt_no_post(
                state_root=state_root,
                generation_digest=generation.digest,
                reviewed_files_digest=reviewed,
                reason="G068_OPERATION_60_UNKNOWN",
            )
        except V4G068ActivationError:
            pass
        print("status=G068_OPERATION_60_UNKNOWN_HALT broker_write=false actual_post_count=0")
        return 4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    return run_once(repository=args.repository.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
