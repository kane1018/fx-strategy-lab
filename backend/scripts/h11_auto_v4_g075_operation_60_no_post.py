"""One-use G075 operation 60 with separate installer/readiness windows."""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from app.services.h11_v4_g075_runtime import (
    G075_OPERATION_60_RESULT_FILE,
    G075_OPERATION_60_STARTED_FILE,
    G075Error,
    engage_g075_halt,
    require_g075_no_unresolved_halt,
    verify_g075_review_artifacts,
    verify_g075_scheduler_binding,
)


def _run_launchctl(command: list[str]) -> subprocess.CompletedProcess[str]:
    if (
        len(command) < 2
        or command[0] != "launchctl"
        or command[1] not in {"print", "bootout", "bootstrap"}
    ):
        return subprocess.CompletedProcess(args=command, returncode=126, stdout="", stderr="")
    return subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)


def run_g075_operation_60_candidate(
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
    started = state_root / G075_OPERATION_60_STARTED_FILE
    _exclusive_start(started, generation_digest, reviewed_files_digest)
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
        "generation_label": G075_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
        "arm_mutation_count": 0,
        "notification_attempt_count": 0,
    }
    result_path = state_root / G075_OPERATION_60_RESULT_FILE
    if result_path.exists() or result_path.is_symlink():
        raise G075Error("G075_OPERATION_60_RESULT_EXISTS_NO_RETRY")
    result_path.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    if outcome == "UNKNOWN":
        engage_g075_halt(state_root=state_root, reason="G075_OPERATION_60_UNKNOWN")
    return outcome


def _exclusive_start(path: Path, generation_digest: str, reviewed_files_digest: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise G075Error("G075_OPERATION_60_ALREADY_STARTED_NO_RETRY") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(
            {
                "generation_label": G075_GENERATION_LABEL,
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "status": "STARTED",
            },
            stream,
            sort_keys=True,
        )


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
    # D-P1a: refuse BEFORE any marker write, so the one-shot marker is not
    # burned on a guaranteed-UNKNOWN outcome.  Mirrors the same early gate
    # added to unattended_control_api.turn_on() and runbook §3.4.
    require_g075_no_unresolved_halt(repository=repository)
    reviewed = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed
    )
    verify_g075_review_artifacts(
        repository=repository, generation_digest=generation.digest, reviewed_files_digest=reviewed
    )
    state_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation.digest
    )
    plist_path = Path.home() / "Library/LaunchAgents" / f"{V4_GMO_UNATTENDED_SCHEDULER_LABEL}.plist"
    plist = render_v4_gmo_unattended_scheduler_launchagent(
        repository=repository,
        generation=generation,
        python_executable=repository / "backend/.venv/bin/python",
    )

    def installer() -> None:
        install_and_restart_v4_gmo_unattended_scheduler_launchagent(
            plist_path=plist_path, plist_content=plist, user_id=os.getuid(), runner=_run_launchctl
        )

    outcome = run_g075_operation_60_candidate(
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
    print(f"G075_OPERATION_60_{outcome}_NO_POST")
    return 0 if outcome == "PASSED" else 4


def _readiness(*, generation, repository: Path, plist_path: Path, state_root: Path) -> bool:
    from datetime import UTC, datetime

    try:
        verify_g075_scheduler_binding(
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
