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
import time
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    V4PreparationAttemptLedger,
    V4PreparationOperation,
    _attest_g064_scheduler_success_internal,
    _attest_g065_scheduler_success_internal,
    load_completed_preparation_evidence,
    load_external_preparation_gate,
    require_g040_runtime_only_monitor_completion,
    require_g052_flat_only_monitor_completion,
    require_g053_flat_only_monitor_completion,
    reviewed_files_digest,
)
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_launchd import (
    V4GmoLaunchdDomainNotReady,
    require_stable_v4_gmo_aqua_domain,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.h11_auto.v4_gmo_unattended_scheduler_launchd import (
    V4_GMO_UNATTENDED_SCHEDULER_LABEL,
    V4GmoUnattendedSchedulerLaunchdError,
    install_and_restart_v4_gmo_unattended_scheduler_launchagent,
    render_v4_gmo_unattended_scheduler_launchagent,
)
from app.services.h11_v4_g064_unattended_activation import (
    G064_GENERATION_LABEL,
    V4G064ActivationError,
    verify_g064_scheduler_binding,
    write_g064_persistent_halt_no_post,
)
from app.services.h11_v4_g065_unattended_activation import (
    G065_GENERATION_LABEL,
    V4G065ActivationError,
    verify_g065_scheduler_binding,
    write_g065_persistent_halt_no_post,
)

_LAUNCHCTL_TIMEOUT_SECONDS = {
    "print": 15.0,
    "bootout": 30.0,
    "bootstrap": 30.0,
}
_G039_GENERATION_LABEL = "H11_AUTO_30M_20260729_G039"
_G040_GENERATION_LABEL = "H11_AUTO_30M_20260729_G040"
_G041_GENERATION_LABEL = "H11_AUTO_30M_20260729_G041"
_G047_GENERATION_LABEL = "H11_AUTO_30M_20260730_G047"
_G048_GENERATION_LABEL = "H11_AUTO_30M_20260730_G048"
_G049_GENERATION_LABEL = "H11_AUTO_30M_20260730_G049"
_G050_GENERATION_LABEL = "H11_AUTO_30M_20260730_G050"
_G051_GENERATION_LABEL = "H11_AUTO_30M_20260730_G051"
_G052_GENERATION_LABEL = "H11_AUTO_30M_20260730_G052"
_G053_GENERATION_LABEL = "H11_AUTO_30M_20260730_G053"
_G054_GENERATION_LABEL = "H11_AUTO_30M_20260730_G054"
_G055_GENERATION_LABEL = "H11_AUTO_30M_20260730_G055"
_G056_GENERATION_LABEL = "H11_AUTO_30M_20260730_G056"
_G076_GENERATION_LABEL = "H11_AUTO_30M_20260802_G076"


def _wait_for_g064_scheduler_readiness(
    *, generation: object, plist_path: Path, state_root: Path
) -> None:
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        try:
            verify_g064_scheduler_binding(
                generation=generation,
                plist_path=plist_path,
                state_root=state_root,
                now_utc=datetime.now(UTC),
                maximum_age_seconds=60,
            )
            return
        except V4G064ActivationError:
            time.sleep(1.0)
    verify_g064_scheduler_binding(
        generation=generation,
        plist_path=plist_path,
        state_root=state_root,
        now_utc=datetime.now(UTC),
        maximum_age_seconds=60,
    )


def _wait_for_g065_scheduler_readiness(
    *, generation: object, plist_path: Path, state_root: Path
) -> None:
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        try:
            verify_g065_scheduler_binding(
                generation=generation,
                plist_path=plist_path,
                state_root=state_root,
                now_utc=datetime.now(UTC),
                maximum_age_seconds=60,
            )
            return
        except V4G065ActivationError:
            time.sleep(1.0)
    verify_g065_scheduler_binding(
        generation=generation,
        plist_path=plist_path,
        state_root=state_root,
        now_utc=datetime.now(UTC),
        maximum_age_seconds=60,
    )


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
    if getattr(generation, "generation_label", "") == _G076_GENERATION_LABEL:
        print(
            "status=G076_FAKE_ONLY_LAUNCHAGENT_MUTATION_DISABLED "
            "broker_write=false actual_post_count=0"
        )
        return 4
    g064_gate = None
    g064_ledger = None
    g064_operation_permit = None
    g064_runtime_state_root = None
    g065_gate = None
    g065_ledger = None
    g065_operation_permit = None
    g065_runtime_state_root = None
    if getattr(generation, "generation_label", "") == G064_GENERATION_LABEL:
        g064_runtime_state_root = v4_gmo_runtime_state_root(
            repository=repository,
            generation_digest=generation.digest,
        )
    if getattr(generation, "generation_label", "") == G065_GENERATION_LABEL:
        g065_runtime_state_root = v4_gmo_runtime_state_root(
            repository=repository,
            generation_digest=generation.digest,
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
    if getattr(generation, "generation_label", "") == _G052_GENERATION_LABEL:
        try:
            external_gate = load_external_preparation_gate(repository=repository)
            require_g052_flat_only_monitor_completion(
                repository=repository,
                external_gate=external_gate,
                generation_digest=generation.digest,
            )
        except V4ActualPreparationGuardError:
            print(
                "status=UNATTENDED_SCHEDULER_G052_FLAT_ONLY_NOT_CLEAR "
                "broker_write=false actual_post_count=0"
            )
            return 2
    if getattr(generation, "generation_label", "") == _G053_GENERATION_LABEL:
        try:
            external_gate = load_external_preparation_gate(repository=repository)
            require_g053_flat_only_monitor_completion(
                repository=repository,
                external_gate=external_gate,
                generation_digest=generation.digest,
            )
        except V4ActualPreparationGuardError:
            print(
                "status=UNATTENDED_SCHEDULER_G053_FLAT_ONLY_NOT_CLEAR "
                "broker_write=false actual_post_count=0"
            )
            return 2
    elif getattr(generation, "generation_label", "") in {
        _G040_GENERATION_LABEL,
        _G041_GENERATION_LABEL,
        _G047_GENERATION_LABEL,
        _G048_GENERATION_LABEL,
        _G049_GENERATION_LABEL,
        _G050_GENERATION_LABEL,
        _G051_GENERATION_LABEL,
        _G054_GENERATION_LABEL,
        _G055_GENERATION_LABEL,
        _G056_GENERATION_LABEL,
    }:
        try:
            external_gate = load_external_preparation_gate(repository=repository)
            require_g040_runtime_only_monitor_completion(
                repository=repository,
                external_gate=external_gate,
                generation_digest=generation.digest,
            )
        except V4ActualPreparationGuardError:
            print(
                "status=UNATTENDED_SCHEDULER_RUNTIME_ONLY_PREPARATION_NOT_CLEAR "
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
        Path.home() / "Library" / "LaunchAgents" / f"{V4_GMO_UNATTENDED_SCHEDULER_LABEL}.plist"
    )
    try:
        require_stable_v4_gmo_aqua_domain(user_id=os.getuid(), runner=_run)
    except V4GmoLaunchdDomainNotReady:
        print("status=GUI_DOMAIN_NOT_READY_RETRY_SAFE broker_write=false actual_post_count=0")
        return 3
    if getattr(generation, "generation_label", "") == G064_GENERATION_LABEL:
        try:
            g064_gate = load_external_preparation_gate(repository=repository)
            g064_ledger = V4PreparationAttemptLedger(external_gate=g064_gate)
            g064_operation_permit = g064_ledger.begin_g064_fresh(
                V4PreparationOperation.MONITOR_LAUNCHAGENT
            )
        except V4ActualPreparationGuardError:
            print(
                "status=G064_SCHEDULER_PREPARATION_NOT_CLEAR broker_write=false actual_post_count=0"
            )
            return 2
    elif getattr(generation, "generation_label", "") == G065_GENERATION_LABEL:
        try:
            g065_gate = load_external_preparation_gate(repository=repository)
            g065_ledger = V4PreparationAttemptLedger(external_gate=g065_gate)
            g065_operation_permit = g065_ledger.begin_g065_fresh(
                V4PreparationOperation.MONITOR_LAUNCHAGENT
            )
        except V4ActualPreparationGuardError:
            print(
                "status=G065_SCHEDULER_PREPARATION_NOT_CLEAR broker_write=false actual_post_count=0"
            )
            return 2
    try:
        result = install_and_restart_v4_gmo_unattended_scheduler_launchagent(
            plist_path=plist_path,
            plist_content=content,
            user_id=os.getuid(),
            runner=_run,
        )
    except (
        V4GmoUnattendedSchedulerLaunchdError,
        subprocess.TimeoutExpired,
        OSError,
    ):
        if (
            g064_ledger is not None
            and g064_runtime_state_root is not None
            and g064_gate is not None
        ):
            try:
                write_g064_persistent_halt_no_post(
                    state_root=g064_runtime_state_root,
                    generation_digest=generation.digest,
                    reviewed_files_digest=digest,
                )
            except V4G064ActivationError:
                print(
                    "status=G064_SCHEDULER_MUTATION_HALT_NOT_WRITTEN "
                    "broker_write=false actual_post_count=0"
                )
                return 2
            print("status=G064_SCHEDULER_MUTATION_NOT_CLEAR broker_write=false actual_post_count=0")
            return 2
        if (
            g065_ledger is not None
            and g065_runtime_state_root is not None
            and g065_gate is not None
        ):
            try:
                write_g065_persistent_halt_no_post(
                    state_root=g065_runtime_state_root,
                    generation_digest=generation.digest,
                    reviewed_files_digest=digest,
                )
            except V4G065ActivationError:
                print(
                    "status=G065_SCHEDULER_MUTATION_HALT_NOT_WRITTEN "
                    "broker_write=false actual_post_count=0"
                )
                return 2
            print("status=G065_SCHEDULER_MUTATION_NOT_CLEAR broker_write=false actual_post_count=0")
            return 2
        print(
            "status=UNATTENDED_SCHEDULER_LAUNCHAGENT_BLOCKED_NO_RETRY "
            "broker_write=false actual_post_count=0"
        )
        return 2
    safe_report = result.to_safe_dict()
    if g064_gate is not None and g064_ledger is not None and g064_operation_permit is not None:
        try:
            _wait_for_g064_scheduler_readiness(
                generation=generation,
                plist_path=plist_path,
                state_root=g064_runtime_state_root,
            )
            safe_report.update(
                {
                    "g064_resident_scheduler": True,
                    "heartbeat_fresh": True,
                    "heartbeat_generation_digest_match": True,
                    "process_lock_clear": True,
                    "dead_man_alive": True,
                    "heartbeat_chain_beat": True,
                    "broker_read": False,
                    "broker_write": False,
                    "actual_post_count": 0,
                    "private_api_read_count": 0,
                    "credential_read_count": 0,
                    "notification_attempt_count": 0,
                    "raw_output_retained": False,
                    "scheduler_change_attempt_count": 1,
                }
            )
            _attest_g064_scheduler_success_internal(
                g064_operation_permit,
                safe_report,
            )
            g064_ledger.complete(
                V4PreparationOperation.MONITOR_LAUNCHAGENT,
                operation_permit=g064_operation_permit,
            )
        except (V4ActualPreparationGuardError, V4G064ActivationError):
            try:
                write_g064_persistent_halt_no_post(
                    state_root=g064_runtime_state_root,
                    generation_digest=generation.digest,
                    reviewed_files_digest=digest,
                )
            except V4G064ActivationError:
                print(
                    "status=G064_SCHEDULER_READINESS_HALT_NOT_WRITTEN "
                    "broker_write=false actual_post_count=0"
                )
                return 2
            print(
                "status=G064_SCHEDULER_READINESS_NOT_CLEAR broker_write=false actual_post_count=0"
            )
            return 2
        print("status=G064_SCHEDULER_COMMISSIONED_NO_POST broker_write=false actual_post_count=0")
        return 0
    if g065_gate is not None and g065_ledger is not None and g065_operation_permit is not None:
        try:
            _wait_for_g065_scheduler_readiness(
                generation=generation,
                plist_path=plist_path,
                state_root=g065_runtime_state_root,
            )
            safe_report.update(
                {
                    "g065_resident_scheduler": True,
                    "heartbeat_fresh": True,
                    "heartbeat_generation_digest_match": True,
                    "process_lock_clear": True,
                    "dead_man_alive": True,
                    "heartbeat_chain_beat": True,
                    "broker_read": False,
                    "broker_write": False,
                    "actual_post_count": 0,
                    "private_api_read_count": 0,
                    "credential_read_count": 0,
                    "notification_attempt_count": 0,
                    "raw_output_retained": False,
                    "scheduler_change_attempt_count": 1,
                }
            )
            _attest_g065_scheduler_success_internal(
                g065_operation_permit,
                safe_report,
            )
            g065_ledger.complete(
                V4PreparationOperation.MONITOR_LAUNCHAGENT,
                operation_permit=g065_operation_permit,
            )
        except (V4ActualPreparationGuardError, V4G065ActivationError):
            try:
                write_g065_persistent_halt_no_post(
                    state_root=g065_runtime_state_root,
                    generation_digest=generation.digest,
                    reviewed_files_digest=digest,
                )
            except V4G065ActivationError:
                print(
                    "status=G065_SCHEDULER_READINESS_HALT_NOT_WRITTEN "
                    "broker_write=false actual_post_count=0"
                )
                return 2
            print(
                "status=G065_SCHEDULER_READINESS_NOT_CLEAR broker_write=false actual_post_count=0"
            )
            return 2
        print("status=G065_SCHEDULER_COMMISSIONED_NO_POST broker_write=false actual_post_count=0")
        return 0
    print(
        "status=INSTALLED_RESTARTED_UNATTENDED_SCHEDULER "
        f"broker_write={str(safe_report['broker_write']).lower()} "
        f"actual_post_count={safe_report['actual_post_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
