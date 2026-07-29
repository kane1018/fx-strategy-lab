"""Install and restart the non-resident unattended live scheduler LaunchAgent.

Renders and installs the plist that periodically invokes
``h11_auto_v4_unattended_live_scheduled_launcher.py``. Running this script
only installs the timer; the launcher's own PLACEHOLDER sections still gate
every real credential/transport, so installing this LaunchAgent alone
cannot place a real order or send a real notification.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    load_completed_preparation_evidence,
    load_external_preparation_gate,
    reviewed_files_digest,
)
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_launchd import (
    V4GmoLaunchdDomainNotReady,
    require_stable_v4_gmo_aqua_domain,
)
from app.h11_auto.v4_gmo_unattended_scheduler_launchd import (
    V4_GMO_UNATTENDED_SCHEDULER_LABEL,
    V4GmoUnattendedSchedulerLaunchdError,
    install_and_restart_v4_gmo_unattended_scheduler_launchagent,
    render_v4_gmo_unattended_scheduler_launchagent,
)

_LAUNCHCTL_TIMEOUT_SECONDS = {
    "print": 15.0,
    "bootout": 30.0,
    "bootstrap": 30.0,
}
_G039_GENERATION_LABEL = "H11_AUTO_30M_20260729_G039"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--start-interval-seconds", type=int, default=300)
    args = parser.parse_args()
    repository = args.repository.resolve()
    digest = reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=digest,
    )
    if getattr(generation, "generation_label", "") == _G039_GENERATION_LABEL:
        try:
            external_gate = load_external_preparation_gate(repository=repository)
            load_completed_preparation_evidence(
                external_gate=external_gate,
                generation_digest=generation.digest,
            )
        except V4ActualPreparationGuardError:
            print(
                "status=UNATTENDED_SCHEDULER_PREPARATION_NOT_CLEAR "
                "broker_write=false actual_post_count=0"
            )
            return 2
    content = render_v4_gmo_unattended_scheduler_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
        start_interval_seconds=args.start_interval_seconds,
    )
    plist_path = (
        Path.home()
        / "Library"
        / "LaunchAgents"
        / f"{V4_GMO_UNATTENDED_SCHEDULER_LABEL}.plist"
    )
    try:
        require_stable_v4_gmo_aqua_domain(user_id=os.getuid(), runner=_run)
    except V4GmoLaunchdDomainNotReady:
        print("status=GUI_DOMAIN_NOT_READY_RETRY_SAFE broker_write=false actual_post_count=0")
        return 3
    try:
        result = install_and_restart_v4_gmo_unattended_scheduler_launchagent(
            plist_path=plist_path,
            plist_content=content,
            user_id=os.getuid(),
            runner=_run,
        )
    except (V4GmoUnattendedSchedulerLaunchdError, subprocess.TimeoutExpired):
        print(
            "status=UNATTENDED_SCHEDULER_LAUNCHAGENT_BLOCKED_NO_RETRY "
            "broker_write=false actual_post_count=0"
        )
        return 2
    safe_report = result.to_safe_dict()
    print(
        "status=INSTALLED_RESTARTED_UNATTENDED_SCHEDULER "
        f"broker_write={str(safe_report['broker_write']).lower()} "
        f"actual_post_count={safe_report['actual_post_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
