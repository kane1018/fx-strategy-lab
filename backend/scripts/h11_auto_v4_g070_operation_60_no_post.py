"""G070 one-use commissioning algorithm; tests inject installer and verifier."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from app.services.h11_v4_g070_candidate import (
    G070_OPERATION_60_RESULT_FILE,
    G070_OPERATION_60_STARTED_FILE,
    G070Error,
    engage_g070_halt,
    verify_g070_review_artifacts,
    verify_g070_scheduler_binding,
)

_LAUNCHCTL_TIMEOUT_SECONDS = {
    "print": 15.0,
    "bootout": 30.0,
    "bootstrap": 30.0,
}


def _run_launchctl(command: list[str]) -> subprocess.CompletedProcess[str]:
    if (
        len(command) < 2
        or command[0] != "launchctl"
        or command[1] not in _LAUNCHCTL_TIMEOUT_SECONDS
    ):
        return subprocess.CompletedProcess(args=command, returncode=126, stdout="", stderr="")
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=_LAUNCHCTL_TIMEOUT_SECONDS[command[1]],
        check=False,
    )


def run_g070_operation_60_candidate(
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
    state_root.mkdir(parents=True, exist_ok=True)
    started = state_root / G070_OPERATION_60_STARTED_FILE
    try:
        descriptor = os.open(started, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise G070Error("G070_OPERATION_60_ALREADY_STARTED_NO_RETRY") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(
            {
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
            },
            stream,
        )
    try:
        installer_started = monotonic()
        installer()
        if monotonic() - installer_started > installer_timeout_seconds:
            outcome = "UNKNOWN"
        else:
            readiness_started = monotonic()
            outcome = "UNKNOWN"
            while monotonic() - readiness_started <= readiness_timeout_seconds:
                if readiness_verifier():
                    outcome = "PASSED"
                    break
                sleep(0.25)
    except Exception:
        outcome = "UNKNOWN"
    (state_root / G070_OPERATION_60_RESULT_FILE).write_text(
        json.dumps(
            {
                "status": outcome,
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "reconciliation_state": "REQUIRED",
                "entry_gate_open": False,
                "broker_post_count": 0,
                "private_api_read_count": 0,
                "credential_read_count": 0,
                "notification_attempt_count": 0,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    if outcome == "UNKNOWN":
        engage_g070_halt(state_root=state_root, reason="G070_OPERATION_60_UNKNOWN")
    return outcome


def main() -> int:
    from app.h11_auto.v4_actual_preparation_guard import require_clean_main
    from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
    from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
    from app.h11_auto.v4_gmo_unattended_scheduler_launchd import (
        V4_GMO_UNATTENDED_SCHEDULER_LABEL,
        install_and_restart_v4_gmo_unattended_scheduler_launchagent,
        render_v4_gmo_unattended_scheduler_launchagent,
    )
    from h11_v4_reviewed_digest import compute_reviewed_files_digest

    repository = Path(__file__).resolve().parents[2]
    require_clean_main(repository=repository)
    reviewed = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed
    )
    verify_g070_review_artifacts(
        repository=repository,
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed,
    )
    state_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation.digest
    )
    plist_path = Path.home() / "Library/LaunchAgents" / f"{V4_GMO_UNATTENDED_SCHEDULER_LABEL}.plist"
    plist = render_v4_gmo_unattended_scheduler_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
    )

    def installer() -> None:
        install_and_restart_v4_gmo_unattended_scheduler_launchagent(
            plist_path=plist_path,
            plist_content=plist,
            user_id=os.getuid(),
            runner=_run_launchctl,
        )

    outcome = run_g070_operation_60_candidate(
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
    print(f"G070_OPERATION_60_{outcome}_NO_POST")
    return 0 if outcome == "PASSED" else 4


def _readiness(*, generation, repository: Path, plist_path: Path, state_root: Path) -> bool:
    try:
        from datetime import UTC, datetime

        verify_g070_scheduler_binding(
            generation=generation,
            repository=repository,
            plist_path=plist_path,
            state_root=state_root,
            now_utc=datetime.now(UTC),
        )
    except Exception:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
