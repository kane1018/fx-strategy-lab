"""Non-destructive current-host and persistent KILL rehearsal for H-11 v4."""

from __future__ import annotations

import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.runtime_safety import (
    AutoRiskStopState,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
    engage_risk_kill,
    evaluate_risk_before_entry,
)
from app.h11_auto.v4_actual_preparation_guard import (
    V4ExternalPreparationGate,
    V4PreparationOperation,
    V4PreparationOperationPermit,
    _attest_host_kill_success_internal,
    require_external_preparation_gate,
    require_operation_permit,
)


class V4ActualHostKillRehearsalError(RuntimeError):
    """Fixed safe host/KILL rehearsal failure."""


_ADMIN_NETWORK_TIME_COMMAND = (
    "/usr/bin/osascript",
    "-e",
    'do shell script "/usr/sbin/systemsetup -getusingnetworktime" '
    "with administrator privileges",
)
_SNTP_CLOCK_COMMAND = ("/usr/bin/sntp", "-t", "2", "time.apple.com")
_READONLY_HOST_COMMAND_TIMEOUT_SECONDS = 5.0
_SNTP_WRAPPER_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class V4ActualHostKillReport:
    status: str
    host_is_macos: bool
    disk_free_bytes_sufficient: bool
    external_power_connected: bool | None
    network_time_enabled: bool | None
    network_time_admin_fallback_used: bool
    clock_probe_succeeded: bool
    absolute_clock_skew_seconds: float | None
    clock_skew_within_five_seconds: bool
    disposable_process_started: bool
    disposable_process_sigkill_observed: bool
    persistent_kill_latched: bool
    entry_blocked_after_reload: bool
    actual_runtime_process_killed: bool = False
    disposable_coordinator_process_killed: bool = False
    coordinator_pending_marker_restart_halt_observed: bool = False
    sleep_performed: bool = False
    reboot_performed: bool = False
    network_changed: bool = False
    keychain_locked: bool = False
    resident_process_added: bool = False
    launchd_installed: bool = False
    cron_added: bool = False
    broker_get_count: int = 0
    broker_post_count: int = 0

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __bool__(self) -> bool:
        return False


def run_actual_host_kill_rehearsal(
    *,
    external_gate: V4ExternalPreparationGate,
    operation_permit: V4PreparationOperationPermit,
    cycle_day_jst: str,
    command_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    admin_command_runner: (
        Callable[[list[str]], subprocess.CompletedProcess[str]] | None
    ) = None,
) -> V4ActualHostKillReport:
    """Inspect host and SIGKILL only a disposable child, then prove KILL persistence."""

    require_external_preparation_gate(external_gate)
    require_operation_permit(
        operation_permit,
        expected_operation=V4PreparationOperation.HOST_KILL,
        claim=True,
    )
    state_dir = (
        external_gate.state_root_for_internal_preparation_only() / "host_kill"
    )
    unresolved_state_dir = state_dir.expanduser()
    if unresolved_state_dir.is_symlink():
        raise V4ActualHostKillRehearsalError("HOST_REHEARSAL_STATE_SYMLINK_FORBIDDEN")
    state_dir = unresolved_state_dir.resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    runner = command_runner or _run_readonly_host_command
    admin_runner = admin_command_runner or _run_readonly_admin_host_command
    host_is_macos = platform.system() == "Darwin"
    free = shutil.disk_usage(state_dir).free
    disk_sufficient = free >= 1_000_000_000
    external_power = _external_power_state(runner) if host_is_macos else None
    if external_power is not True:
        return V4ActualHostKillReport(
            status="BLOCKED_CURRENT_HOST_AC_POWER_NOT_CLEAR",
            host_is_macos=host_is_macos,
            disk_free_bytes_sufficient=disk_sufficient,
            external_power_connected=external_power,
            network_time_enabled=None,
            network_time_admin_fallback_used=False,
            clock_probe_succeeded=False,
            absolute_clock_skew_seconds=None,
            clock_skew_within_five_seconds=False,
            disposable_process_started=False,
            disposable_process_sigkill_observed=False,
            persistent_kill_latched=False,
            entry_blocked_after_reload=False,
        )
    if host_is_macos:
        network_time, network_time_admin_fallback_used = _network_time_state(
            runner,
            admin_runner,
        )
    else:
        network_time, network_time_admin_fallback_used = None, False
    clock_skew = _clock_skew_seconds(runner) if host_is_macos else None
    clock_probe_succeeded = clock_skew is not None
    clock_skew_within_five_seconds = (
        clock_skew is not None and clock_skew <= 5.0
    )

    child: subprocess.Popen[bytes] | None = None
    try:
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        started = child.poll() is None
        if not started:
            raise V4ActualHostKillRehearsalError("DISPOSABLE_KILL_PROCESS_NOT_STARTED")
        os.kill(child.pid, signal.SIGKILL)
        try:
            returncode = child.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            raise V4ActualHostKillRehearsalError(
                "DISPOSABLE_KILL_NOT_OBSERVED"
            ) from None
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5.0)
    killed = returncode == -signal.SIGKILL
    coordinator_killed, restart_halt_observed = _coordinator_kill_probe(
        state_dir=state_dir,
        implementation_digest=(
            external_gate.reviewed_digest_for_internal_preparation_only()
        ),
    )

    policy = PhaseBRiskPolicy(
        policy_label="H11_V4_ACTUAL_PREPARATION_KILL_V1",
        per_trade_loss_bound_jpy=5_000,
        daily_loss_limit_jpy=10_000,
        monthly_loss_limit_jpy=50_000,
        maximum_consecutive_losses=5,
    )
    store = PhaseBRiskStore(state_dir / "v4_actual_preparation_kill.json", policy=policy)
    state = store.load()
    engage_risk_kill(state=state, cycle_day_jst=cycle_day_jst)
    store.save(state)
    reloaded = store.load()
    gate = evaluate_risk_before_entry(
        state=reloaded,
        policy=policy,
        cycle_day_jst=cycle_day_jst,
    )
    latched = AutoRiskStopState(reloaded.stop_state) is AutoRiskStopState.KILLED
    entry_blocked = not gate.allowed and "PERSISTENT_RISK_STOPPED" in gate.blocked_reasons
    clear = (
        host_is_macos
        and disk_sufficient
        and external_power is True
        and network_time is True
        and clock_skew_within_five_seconds
        and killed
        and coordinator_killed
        and restart_halt_observed
        and latched
        and entry_blocked
    )
    report = V4ActualHostKillReport(
        status=(
            "PASSED_CURRENT_HOST_GENERIC_KILL_PREPARATION_NO_BROKER_POST"
            if clear
            else "BLOCKED_CURRENT_HOST_REQUIREMENT_NOT_CLEAR"
        ),
        host_is_macos=host_is_macos,
        disk_free_bytes_sufficient=disk_sufficient,
        external_power_connected=external_power,
        network_time_enabled=network_time,
        network_time_admin_fallback_used=network_time_admin_fallback_used,
        clock_probe_succeeded=clock_probe_succeeded,
        absolute_clock_skew_seconds=clock_skew,
        clock_skew_within_five_seconds=clock_skew_within_five_seconds,
        disposable_process_started=started,
        disposable_process_sigkill_observed=killed,
        persistent_kill_latched=latched,
        entry_blocked_after_reload=entry_blocked,
        actual_runtime_process_killed=False,
        disposable_coordinator_process_killed=coordinator_killed,
        coordinator_pending_marker_restart_halt_observed=restart_halt_observed,
    )
    if clear:
        _attest_host_kill_success_internal(operation_permit, report.to_safe_dict())
    return report


def _coordinator_kill_probe(
    *, state_dir: Path, implementation_digest: str
) -> tuple[bool, bool]:
    state_path = state_dir / "v4_actual_coordinator_kill.sqlite3"
    transport_marker = state_dir / "v4_actual_coordinator_transport_called"
    observed = datetime.now(UTC).isoformat()
    child = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scripts.h11_auto_v4_coordinator_kill_probe",
            "--state-path",
            str(state_path),
            "--implementation-digest",
            implementation_digest,
            "--observed-at-utc",
            observed,
            "--mode",
            "initial",
            "--transport-marker",
            str(transport_marker),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    stopped = False
    try:
        for _ in range(50):
            waited_pid, wait_status = os.waitpid(
                child.pid, os.WNOHANG | os.WUNTRACED
            )
            if waited_pid == child.pid and os.WIFSTOPPED(wait_status):
                stopped = True
                break
            if child.poll() is not None:
                break
            time.sleep(0.1)
        if not stopped:
            raise V4ActualHostKillRehearsalError(
                "COORDINATOR_KILL_PROCESS_NOT_READY"
            )
        os.kill(child.pid, signal.SIGKILL)
        killed = child.wait(timeout=5.0) == -signal.SIGKILL
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5.0)
    restarted = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.h11_auto_v4_coordinator_kill_probe",
            "--state-path",
            str(state_path),
            "--implementation-digest",
            implementation_digest,
            "--observed-at-utc",
            observed,
            "--mode",
            "restart",
            "--transport-marker",
            str(transport_marker),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5.0,
        check=False,
    )
    restart_halt_observed = restarted.returncode == 0 and not transport_marker.exists()
    return killed, restart_halt_observed


def _run_readonly_host_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    timeout_seconds = (
        _SNTP_WRAPPER_TIMEOUT_SECONDS
        if tuple(command) == _SNTP_CLOCK_COMMAND
        else _READONLY_HOST_COMMAND_TIMEOUT_SECONDS
    )
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise V4ActualHostKillRehearsalError("READ_ONLY_HOST_CHECK_FAILED") from error


def _run_readonly_admin_host_command(
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    if tuple(command) != _ADMIN_NETWORK_TIME_COMMAND:
        raise V4ActualHostKillRehearsalError("ADMIN_HOST_COMMAND_FORBIDDEN")
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise V4ActualHostKillRehearsalError(
            "ADMIN_READ_ONLY_HOST_CHECK_FAILED"
        ) from error


def _external_power_state(
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]],
) -> bool | None:
    result = runner(["pmset", "-g", "batt"])
    if result.returncode != 0:
        return None
    if "AC Power" in result.stdout:
        return True
    if "Battery Power" in result.stdout:
        return False
    return None


def _network_time_state(
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]],
    admin_runner: Callable[[list[str]], subprocess.CompletedProcess[str]],
) -> tuple[bool | None, bool]:
    direct_command = ["/usr/sbin/systemsetup", "-getusingnetworktime"]
    result = runner(direct_command)
    direct_state = _network_time_value(result)
    if direct_state is not None:
        return direct_state, False
    fallback_used = True
    result = admin_runner(list(_ADMIN_NETWORK_TIME_COMMAND))
    return _network_time_value(result), fallback_used


def _network_time_value(
    result: subprocess.CompletedProcess[str],
) -> bool | None:
    if result.returncode != 0:
        return None
    normalized = result.stdout.strip().lower()
    if normalized == "network time: on":
        return True
    if normalized == "network time: off":
        return False
    return None


def _clock_skew_seconds(
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]],
) -> float | None:
    """Return only an absolute aggregate; never retain the time-server response."""

    result = runner(list(_SNTP_CLOCK_COMMAND))
    if result.returncode != 0:
        return None
    match = re.search(r"(?:^|\s)([+-]\d+(?:\.\d+)?)", result.stdout)
    if match is None:
        return None
    try:
        return abs(float(match.group(1)))
    except ValueError:
        return None
