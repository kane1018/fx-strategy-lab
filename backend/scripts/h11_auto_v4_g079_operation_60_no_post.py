"""One-use G079 operation 60 with separate installer/readiness windows.

Commissioning gate for the G079 candidate.  The operator runs this script
after G079 promotion (canonical template must carry the G079 label).  It
renders and installs the unattended scheduler LaunchAgent (real launchctl
operations), waits for resident readiness, and writes an exclusive
``g079-operation-60.result.json``.  Any UNKNOWN or post-start failure is
terminal and never retried.  Broker POST stays forbidden (default-deny).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import require_clean_main
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.h11_auto.v4_gmo_unattended_scheduler_launchd import (
    V4_GMO_UNATTENDED_SCHEDULER_LABEL,
    install_and_restart_v4_gmo_unattended_scheduler_launchagent,
    render_v4_gmo_unattended_scheduler_launchagent,
)
from app.services.h11_v4_g079_runtime import (
    G079_OPERATION_60_RESULT_FILE,
    G079_OPERATION_60_STARTED_FILE,
    G079Error,
    engage_g079_halt,
    verify_g079_scheduler_binding,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest


def _run_launchctl(command: list[str]) -> subprocess.CompletedProcess[str]:
    if (
        len(command) < 2
        or command[0] != "launchctl"
        or command[1] not in {"print", "bootout", "bootstrap"}
    ):
        return subprocess.CompletedProcess(args=command, returncode=126, stdout="", stderr="")
    return subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)


def _exclusive_json(path: Path, payload: dict[str, object]) -> None:
    try:
        descriptor = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise G079Error("G079_OPERATION_60_ALREADY_STARTED_NO_RETRY") from None
    with descriptor:
        descriptor.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _canonical_hash(payload: dict[str, object]) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def run_g079_operation_60_candidate(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    installer: Callable[[], None],
    readiness_verifier: Callable[[], bool],
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    installer_timeout_seconds: float = 60,
    readiness_timeout_seconds: float = 60,
) -> str:
    """Exercise finite timeout ordering with the real installer/readiness."""
    started = state_root / G079_OPERATION_60_STARTED_FILE
    _exclusive_json(
        started,
        {
            "generation_label": "H11_AUTO_30M_20260805_G079",
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "status": "STARTED",
        },
    )
    outcome = "UNKNOWN"
    try:
        start = monotonic()
        installer()
        if monotonic() - start <= installer_timeout_seconds:
            readiness_start = monotonic()
            while monotonic() - readiness_start <= readiness_timeout_seconds:
                if readiness_verifier():
                    outcome = "PASSED"
                    break
                sleep(0.25)
    except Exception:
        outcome = "UNKNOWN"
    result = {
        "status": outcome,
        "generation_label": "H11_AUTO_30M_20260805_G079",
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
        "arm_mutation_count": 0,
        "notification_attempt_count": 0,
        "broker_write": False,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
    }
    result["artifact_digest"] = _canonical_hash(
        {k: v for k, v in result.items() if k != "artifact_digest"}
    )
    _exclusive_json(state_root / G079_OPERATION_60_RESULT_FILE, result)
    if outcome != "PASSED":
        engage_g079_halt(state_root=state_root, reason="G079_OPERATION_60_UNKNOWN")
    return outcome


def _readiness(*, generation, repository: Path, plist_path: Path, state_root: Path) -> bool:
    from datetime import UTC, datetime

    try:
        verify_g079_scheduler_binding(
            generation=generation,
            repository=repository,
            plist_path=plist_path,
            state_root=state_root,
            now_utc=datetime.now(UTC),
        )
    except Exception:
        return False
    return True


def main() -> int:
    repository = Path(__file__).resolve().parents[2]
    require_clean_main(repository=repository)
    reviewed = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed
    )
    if generation.generation_label != "H11_AUTO_30M_20260805_G079":
        raise G079Error("G079_OPERATION_60_CANONICAL_NOT_G079")
    state_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation.digest
    )
    plist_path = (
        Path.home()
        / "Library/LaunchAgents"
        / f"{V4_GMO_UNATTENDED_SCHEDULER_LABEL}.plist"
    )
    plist = render_v4_gmo_unattended_scheduler_launchagent(
        repository=repository,
        generation=generation,
        python_executable=repository / "backend/.venv/bin/python",
    )

    def installer() -> None:
        install_and_restart_v4_gmo_unattended_scheduler_launchagent(
            plist_path=plist_path,
            plist_content=plist,
            user_id=os.getuid(),
            runner=_run_launchctl,
        )

    outcome = run_g079_operation_60_candidate(
        state_root=state_root,
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed,
        installer=installer,
        readiness_verifier=lambda: _readiness(
            generation=generation,
            repository=repository,
            plist_path=plist_path,
            state_root=state_root,
        ),
    )
    print(f"G079_OPERATION_60_{outcome}_NO_POST")
    return 0 if outcome == "PASSED" else 4


if __name__ == "__main__":
    raise SystemExit(main())
