"""Install and restart the reviewed monitor-only G013 LaunchAgent."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    V4PreparationAttemptLedger,
    V4PreparationFailureCode,
    V4PreparationOperation,
    _attest_monitor_launchagent_success_internal,
    load_external_preparation_gate,
    load_g040_runtime_only_carry_forward_evidence,
    require_operation_permit,
    reviewed_files_digest,
)
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_launchd import (
    V4_GMO_LAUNCHD_SAFE_FAILURE_CODES,
    V4_GMO_MONITOR_LABEL,
    V4GmoLaunchdDomainNotReady,
    V4GmoLaunchdError,
    V4GmoLaunchdFailureCode,
    install_and_restart_v4_gmo_monitor_launchagent,
    render_v4_gmo_monitor_launchagent,
    require_stable_v4_gmo_aqua_domain,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root

_LAUNCHCTL_TIMEOUT_SECONDS = {
    "print": 15.0,
    "bootout": 30.0,
    "bootstrap": 30.0,
}
_G039_GENERATION_LABEL = "H11_AUTO_30M_20260729_G039"
_G039_DESKTOP_ACCESS_PROBE_TIMEOUT_SECONDS = 15.0
_G040_GENERATION_LABEL = "H11_AUTO_30M_20260729_G040"
_G041_GENERATION_LABEL = "H11_AUTO_30M_20260729_G041"
_G045_GENERATION_LABEL = "H11_AUTO_30M_20260729_G045"
_G040_RUNTIME_STARTUP_PROBE_TIMEOUT_SECONDS = 20.0


class V4MonitorLaunchagentFailureCode(StrEnum):
    PREPARATION_OPERATION_FAILED = "PREPARATION_OPERATION_FAILED"
    PREPARATION_SEQUENCE_BLOCKED = "PREPARATION_SEQUENCE_BLOCKED"
    PREPARATION_OPERATION_IN_PROGRESS = "PREPARATION_OPERATION_IN_PROGRESS"
    PREPARATION_OPERATION_ALREADY_ATTEMPTED = (
        "PREPARATION_OPERATION_ALREADY_ATTEMPTED"
    )
    PREPARATION_GENERATION_TERMINAL_UNRESOLVED = (
        "PREPARATION_GENERATION_TERMINAL_UNRESOLVED"
    )
    PREPARATION_PERSISTENCE_FAILED = "PREPARATION_PERSISTENCE_FAILED"
    PREPARATION_PERMIT_INVALID = "PREPARATION_PERMIT_INVALID"
    DESKTOP_ACCESS_NOT_CLEAR = "G039_LAUNCHD_DESKTOP_ACCESS_NOT_CLEAR"
    FAILURE_CLASS_UNKNOWN = "MONITOR_LAUNCHAGENT_FAILURE_CLASS_UNKNOWN"


class V4MonitorLaunchagentBeginState(StrEnum):
    PRE_BEGIN = "PRE_BEGIN"
    BEGIN_INDETERMINATE = "BEGIN_INDETERMINATE"
    MARKER_PERSISTED = "MARKER_PERSISTED"


def _safe_failure_class(error: BaseException) -> str:
    if isinstance(error, subprocess.TimeoutExpired):
        command = error.cmd
        action = (
            command[1]
            if isinstance(command, list | tuple)
            and len(command) >= 2
            and command[0] == "launchctl"
            else None
        )
        timeout_codes = {
            "print": V4GmoLaunchdFailureCode.PRINT_TIMEOUT.value,
            "bootout": V4GmoLaunchdFailureCode.BOOTOUT_TIMEOUT.value,
            "bootstrap": V4GmoLaunchdFailureCode.BOOTSTRAP_TIMEOUT.value,
        }
        if action in timeout_codes:
            return timeout_codes[action]
        return V4GmoLaunchdFailureCode.COMMAND_TIMEOUT.value
    if isinstance(error, V4ActualPreparationGuardError):
        preparation_codes = {
            V4PreparationFailureCode.SEQUENCE_PREVIOUS_NOT_CLEAR: (
                V4MonitorLaunchagentFailureCode.PREPARATION_SEQUENCE_BLOCKED.value
            ),
            V4PreparationFailureCode.OPERATION_IN_PROGRESS: (
                V4MonitorLaunchagentFailureCode.PREPARATION_OPERATION_IN_PROGRESS.value
            ),
            V4PreparationFailureCode.OPERATION_ALREADY_ATTEMPTED: (
                V4MonitorLaunchagentFailureCode
                .PREPARATION_OPERATION_ALREADY_ATTEMPTED.value
            ),
            V4PreparationFailureCode.GENERATION_TERMINAL_UNRESOLVED: (
                V4MonitorLaunchagentFailureCode
                .PREPARATION_GENERATION_TERMINAL_UNRESOLVED.value
            ),
            V4PreparationFailureCode.ATTEMPT_NOT_PERSISTED: (
                V4MonitorLaunchagentFailureCode.PREPARATION_PERSISTENCE_FAILED.value
            ),
            V4PreparationFailureCode.PASS_NOT_PERSISTED: (
                V4MonitorLaunchagentFailureCode.PREPARATION_PERSISTENCE_FAILED.value
            ),
            V4PreparationFailureCode.OPERATION_PERMIT_INVALID: (
                V4MonitorLaunchagentFailureCode.PREPARATION_PERMIT_INVALID.value
            ),
        }
        if error.code in preparation_codes:
            return preparation_codes[error.code]
        return V4MonitorLaunchagentFailureCode.PREPARATION_OPERATION_FAILED.value
    if isinstance(error, V4GmoLaunchdError):
        if (
            error.code is not None
            and error.code.value in V4_GMO_LAUNCHD_SAFE_FAILURE_CODES
        ):
            return error.code.value
    return V4MonitorLaunchagentFailureCode.FAILURE_CLASS_UNKNOWN.value


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    if (
        len(command) < 2
        or command[0] != "launchctl"
        or command[1] not in _LAUNCHCTL_TIMEOUT_SECONDS
    ):
        return subprocess.CompletedProcess(
            args=command,
            returncode=126,
            stdout="",
            stderr="",
        )
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=_LAUNCHCTL_TIMEOUT_SECONDS[command[1]],
        check=False,
    )


def _probe_g039_launchd_desktop_access(
    *,
    repository: Path,
    user_id: int,
    python_executable: Path,
) -> bool:
    """Prove launchd-user-context Desktop read access before op60 is claimed."""

    target = repository / "backend" / "h11_v4_reviewed_digest.py"
    if target.is_symlink() or not target.is_file():
        return False
    command = [
        "launchctl",
        "asuser",
        str(user_id),
        str(python_executable),
        "-I",
        "-c",
        (
            "from pathlib import Path; import sys; "
            "data=Path(sys.argv[1]).read_bytes(); "
            "raise SystemExit(0 if data else 2)"
        ),
        str(target),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=_G039_DESKTOP_ACCESS_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return (
        result.returncode == 0
        and result.stdout == ""
        and result.stderr == ""
    )


def _probe_g040_launchd_runtime_startup(
    *,
    repository: Path,
    user_id: int,
    python_executable: Path,
    reviewed_files_digest_value: str,
    generation_digest: str,
) -> bool:
    command = [
        "launchctl",
        "asuser",
        str(user_id),
        str(python_executable),
        "-m",
        "scripts.h11_auto_v4_monitor_supervisor",
        "--repository",
        str(repository),
        "--expected-reviewed-files-digest",
        reviewed_files_digest_value,
        "--expected-generation-digest",
        generation_digest,
        "--startup-probe",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=repository / "backend",
            capture_output=True,
            text=True,
            timeout=_G040_RUNTIME_STARTUP_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
        report = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False
    return (
        result.returncode == 0
        and report.get("status") == "V4_MONITOR_STARTUP_PROBE_CLEAR_NO_POST"
        and report.get("runtime_risk_ready") is True
        and report.get("dead_man_alive") is True
        and report.get("heartbeat_chain_beat") is True
        and report.get("broker_write") is False
        and report.get("broker_post_count") == 0
        and report.get("credential_read") is False
        and report.get("private_api_read") is False
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    try:
        digest = reviewed_files_digest(repository=repository)
        generation = load_v4_gmo_frozen_generation(
            repository=repository,
            implementation_digest=digest,
        )
        content = render_v4_gmo_monitor_launchagent(
            repository=repository,
            generation=generation,
            python_executable=Path(sys.executable),
        )
    except Exception as error:
        print(
            "status=MONITOR_LAUNCHAGENT_PRECHECK_BLOCKED_NO_MARKER_CLAIMED "
            f"failure_class={_safe_failure_class(error)} "
            "broker_write=false actual_post_count=0"
        )
        return 2
    plist_path = (
        Path.home() / "Library" / "LaunchAgents" / f"{V4_GMO_MONITOR_LABEL}.plist"
    )
    state_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=generation.digest,
    )
    try:
        require_stable_v4_gmo_aqua_domain(
            user_id=os.getuid(),
            runner=_run,
        )
    except V4GmoLaunchdDomainNotReady as error:
        failure_class = (
            _safe_failure_class(error.__cause__)
            if isinstance(error.__cause__, subprocess.TimeoutExpired)
            else V4GmoLaunchdFailureCode.GUI_DOMAIN_NOT_READY.value
        )
        print(
            "status=GUI_DOMAIN_NOT_READY_RETRY_SAFE "
            f"failure_class={failure_class} "
            "broker_write=false actual_post_count=0"
        )
        return 3
    except subprocess.TimeoutExpired as error:
        print(
            "status=GUI_DOMAIN_NOT_READY_RETRY_SAFE "
            f"failure_class={_safe_failure_class(error)} "
            "broker_write=false actual_post_count=0"
        )
        return 3
    except Exception as error:
        print(
            "status=GUI_DOMAIN_CHECK_BLOCKED_NO_MARKER_CLAIMED "
            f"failure_class={_safe_failure_class(error)} "
            "broker_write=false actual_post_count=0"
        )
        return 2
    if getattr(generation, "generation_label", "") == _G039_GENERATION_LABEL:
        if not _probe_g039_launchd_desktop_access(
            repository=repository,
            user_id=os.getuid(),
            python_executable=Path(sys.executable),
        ):
            print(
                "status=MONITOR_LAUNCHAGENT_DESKTOP_ACCESS_BLOCKED_"
                "NO_MARKER_CLAIMED "
                "failure_class=G039_LAUNCHD_DESKTOP_ACCESS_NOT_CLEAR "
                "broker_write=false actual_post_count=0"
            )
            return 2
    startup_process_lock: H11AutoProcessLock | None = None
    if getattr(generation, "generation_label", "") in {
        _G040_GENERATION_LABEL,
        _G041_GENERATION_LABEL,
        _G045_GENERATION_LABEL,
    }:
        startup_process_lock = H11AutoProcessLock(state_root / "process.lock")
        if not startup_process_lock.acquire():
            print(
                "status=MONITOR_LAUNCHAGENT_PROCESS_LOCK_BLOCKED_"
                "NO_MARKER_CLAIMED "
                "failure_class=G040_RUNTIME_PROCESS_LOCK_NOT_CLEAR "
                "broker_write=false actual_post_count=0"
            )
            return 2
        if not _probe_g040_launchd_runtime_startup(
            repository=repository,
            user_id=os.getuid(),
            python_executable=Path(sys.executable),
            reviewed_files_digest_value=digest,
            generation_digest=generation.digest,
        ):
            print(
                "status=MONITOR_LAUNCHAGENT_RUNTIME_STARTUP_BLOCKED_"
                "NO_MARKER_CLAIMED "
                "failure_class=G040_RUNTIME_STARTUP_NOT_CLEAR "
                "broker_write=false actual_post_count=0"
            )
            startup_process_lock.release()
            return 2
    begin_state = V4MonitorLaunchagentBeginState.PRE_BEGIN
    expected_runtime_initialized = (
        getattr(generation, "generation_label", "")
        == _G045_GENERATION_LABEL
    )
    try:
        external_gate = load_external_preparation_gate(repository=repository)
        ledger = V4PreparationAttemptLedger(external_gate=external_gate)
        operation = V4PreparationOperation.MONITOR_LAUNCHAGENT
        runtime_carry_forward = None
        if getattr(generation, "generation_label", "") in {
            _G040_GENERATION_LABEL,
            _G041_GENERATION_LABEL,
            _G045_GENERATION_LABEL,
        }:
            runtime_carry_forward = (
                load_g040_runtime_only_carry_forward_evidence(
                    repository=repository,
                    external_gate=external_gate,
                    generation_digest=generation.digest,
                )
            )
        begin_state = V4MonitorLaunchagentBeginState.BEGIN_INDETERMINATE
        if runtime_carry_forward is None:
            operation_permit = ledger.begin(operation)
        else:
            operation_permit = ledger.begin_g040_runtime_only_monitor(
                repository=repository,
                generation_digest=generation.digest,
            )
        begin_state = V4MonitorLaunchagentBeginState.MARKER_PERSISTED
        require_operation_permit(
            operation_permit,
            expected_operation=operation,
            claim=True,
        )
        result = install_and_restart_v4_gmo_monitor_launchagent(
            plist_path=plist_path,
            plist_content=content,
            user_id=os.getuid(),
            runner=_run,
            heartbeat_path=state_root / "supervisor-heartbeat.json",
            expected_generation_digest=generation.digest,
            wall_clock=lambda: datetime.now(UTC),
            expected_runtime_initialized=expected_runtime_initialized,
        )
        if getattr(generation, "generation_label", "") in {
            _G040_GENERATION_LABEL,
            _G041_GENERATION_LABEL,
            _G045_GENERATION_LABEL,
        }:
            try:
                heartbeat = json.loads(
                    (state_root / "supervisor-heartbeat.json").read_text(
                        encoding="utf-8"
                    )
                )
            except (OSError, json.JSONDecodeError) as error:
                raise V4GmoLaunchdError(
                    "G040_RUNTIME_HEARTBEAT_NOT_CLEAR"
                ) from error
            if (
                heartbeat.get("runtime_risk_ready") is not True
                or heartbeat.get("dead_man_alive") is not True
                or heartbeat.get("heartbeat_chain_beat") is not True
                or heartbeat.get("broker_write") is not False
                or heartbeat.get("actual_post_count") != 0
            ):
                raise V4GmoLaunchdError(
                    "G040_RUNTIME_SAFETY_NOT_CLEAR"
                )
        safe_report = result.to_safe_dict()
        _attest_monitor_launchagent_success_internal(
            operation_permit,
            safe_report,
            expected_runtime_initialized=expected_runtime_initialized,
        )
        ledger.complete(operation, operation_permit=operation_permit)
    except Exception as error:
        if startup_process_lock is not None:
            startup_process_lock.release()
        failure_class = _safe_failure_class(error)
        if begin_state is V4MonitorLaunchagentBeginState.MARKER_PERSISTED:
            status = "MONITOR_LAUNCHAGENT_BLOCKED_NO_RETRY"
        elif begin_state is V4MonitorLaunchagentBeginState.BEGIN_INDETERMINATE:
            if failure_class in {
                V4MonitorLaunchagentFailureCode.PREPARATION_SEQUENCE_BLOCKED.value,
                V4MonitorLaunchagentFailureCode.PREPARATION_OPERATION_IN_PROGRESS.value,
            }:
                status = "MONITOR_LAUNCHAGENT_BEGIN_REFUSED_NO_NEW_MARKER"
            elif failure_class in {
                V4MonitorLaunchagentFailureCode
                .PREPARATION_OPERATION_ALREADY_ATTEMPTED.value,
                V4MonitorLaunchagentFailureCode
                .PREPARATION_GENERATION_TERMINAL_UNRESOLVED.value,
            }:
                status = (
                    "MONITOR_LAUNCHAGENT_BEGIN_REFUSED_EXISTING_TERMINAL_NO_RETRY"
                )
            else:
                status = (
                    "MONITOR_LAUNCHAGENT_BEGIN_BLOCKED_STATE_UNKNOWN_NO_RETRY"
                )
        else:
            status = "MONITOR_LAUNCHAGENT_PRECHECK_BLOCKED_NO_MARKER_CLAIMED"
        print(
            f"status={status} "
            f"failure_class={failure_class} "
            "broker_write=false actual_post_count=0"
        )
        return 2
    if startup_process_lock is not None:
        startup_process_lock.release()
    print(
        "status=INSTALLED_RESTARTED_MONITOR_ONLY "
        f"broker_write={str(result.broker_write).lower()} "
        f"actual_post_count={result.actual_post_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
