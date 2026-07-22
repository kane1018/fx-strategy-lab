"""Install and restart the reviewed monitor-only G013 LaunchAgent."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    V4PreparationAttemptLedger,
    V4PreparationOperation,
    _attest_monitor_launchagent_success_internal,
    load_external_preparation_gate,
    require_operation_permit,
    reviewed_files_digest,
)
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_launchd import (
    V4_GMO_MONITOR_LABEL,
    V4GmoLaunchdDomainNotReady,
    V4GmoLaunchdError,
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
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
    except V4GmoLaunchdDomainNotReady:
        print(
            "status=GUI_DOMAIN_NOT_READY_RETRY_SAFE "
            "broker_write=false actual_post_count=0"
        )
        return 3
    try:
        external_gate = load_external_preparation_gate(repository=repository)
        ledger = V4PreparationAttemptLedger(external_gate=external_gate)
        operation = V4PreparationOperation.MONITOR_LAUNCHAGENT
        operation_permit = ledger.begin(operation)
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
        )
        safe_report = result.to_safe_dict()
        _attest_monitor_launchagent_success_internal(
            operation_permit,
            safe_report,
        )
        ledger.complete(operation, operation_permit=operation_permit)
    except (
        V4ActualPreparationGuardError,
        V4GmoLaunchdError,
        subprocess.TimeoutExpired,
    ):
        print(
            "status=MONITOR_LAUNCHAGENT_BLOCKED_NO_RETRY "
            "broker_write=false actual_post_count=0"
        )
        return 2
    print(
        "status=INSTALLED_RESTARTED_MONITOR_ONLY "
        f"broker_write={str(result.broker_write).lower()} "
        f"actual_post_count={result.actual_post_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
