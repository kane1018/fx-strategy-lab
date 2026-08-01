import os
from pathlib import Path

import pytest

from app.h11_auto import v4_actual_preparation_guard as guard
from app.services.h11_v4_g064_unattended_activation import (
    V4G064ActivationError,
    write_g064_persistent_halt_no_post,
)

G064_LABEL = "H11_AUTO_30M_20260801_G064"
DIGEST = "sha256:" + "a" * 64


def _gate(tmp_path: Path, *, generation_label: str = G064_LABEL):
    return guard.V4ExternalPreparationGate(
        token=guard._GATE_TOKEN,
        reviewed_files_digest=DIGEST,
        state_root=tmp_path / ("state-" + "b" * 64),
        generation_label=generation_label,
    )


def _complete(ledger, permit, operation, report):
    guard.require_operation_permit(permit, expected_operation=operation, claim=True)
    permit._completion_report = report
    permit._completion_digest = guard._completion_digest(
        operation=operation,
        safe_report=report,
        reviewed_files_digest=permit._reviewed_files_digest,
        generation_digest=permit._generation_digest,
    )
    ledger.complete(operation, operation_permit=permit)


def test_g064_fresh_sequence_skips_legacy_operations_and_is_terminal(
    tmp_path: Path,
) -> None:
    gate = _gate(tmp_path)
    ledger = guard.V4PreparationAttemptLedger(external_gate=gate)

    with pytest.raises(guard.V4ActualPreparationGuardError):
        ledger.begin(guard.V4PreparationOperation.PUSHOVER)

    presence = ledger.begin_g064_fresh(guard.V4PreparationOperation.PRESENCE)
    _complete(
        ledger,
        presence,
        guard.V4PreparationOperation.PRESENCE,
        {
            "total_required": 6,
            "present_count": 6,
            "all_present": True,
            "values_read": False,
        },
    )
    keychain = ledger.begin_g064_fresh(guard.V4PreparationOperation.KEYCHAIN_ACCESS)
    _complete(
        ledger,
        keychain,
        guard.V4PreparationOperation.KEYCHAIN_ACCESS,
        {
            "total_required": 6,
            "accessible_count": 6,
            "all_accessible": True,
            "credential_value_exposed": False,
        },
    )
    private_get = ledger.begin_g064_fresh(guard.V4PreparationOperation.PRIVATE_GET)
    _complete(
        ledger,
        private_get,
        guard.V4PreparationOperation.PRIVATE_GET,
        {
            "broker_get_count": 3,
            "account_wide_snapshot_clear": True,
            "account_flat": True,
            "account_active_orders_zero": True,
            "cadence_offsets_seconds": (0.0, 0.25, 0.5),
            "broker_post_count": 0,
            "broker_write_performed": False,
        },
    )
    monitor = ledger.begin_g064_fresh(
        guard.V4PreparationOperation.MONITOR_LAUNCHAGENT
    )
    _complete(
        ledger,
        monitor,
        guard.V4PreparationOperation.MONITOR_LAUNCHAGENT,
        {
            "g064_resident_scheduler": True,
            "installed": True,
            "bootstrapped": True,
            "service_running": True,
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
            "previous_service_present": False,
            "previous_service_booted_out": False,
        },
    )

    with pytest.raises(guard.V4ActualPreparationGuardError):
        ledger.begin_g064_fresh(guard.V4PreparationOperation.PUSHOVER)
    with pytest.raises(guard.V4ActualPreparationGuardError):
        guard.V4PreparationAttemptLedger(external_gate=gate).begin_g064_fresh(
            guard.V4PreparationOperation.PRESENCE
        )


def test_g064_fresh_ledger_rejects_non_g064_generation(tmp_path: Path) -> None:
    gate = _gate(tmp_path, generation_label="H11_AUTO_30M_20260731_G063")
    ledger = guard.V4PreparationAttemptLedger(external_gate=gate)
    with pytest.raises(guard.V4ActualPreparationGuardError):
        ledger.begin_g064_fresh(guard.V4PreparationOperation.PRESENCE)


def test_g064_scheduler_report_requires_independent_runtime_evidence() -> None:
    report = {
        "g064_resident_scheduler": True,
        "installed": True,
        "bootstrapped": True,
        "service_running": True,
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
        "previous_service_present": False,
        "previous_service_booted_out": False,
    }
    assert guard._operation_report_is_clear(
        guard.V4PreparationOperation.MONITOR_LAUNCHAGENT, report
    )
    report["process_lock_clear"] = False
    assert not guard._operation_report_is_clear(
        guard.V4PreparationOperation.MONITOR_LAUNCHAGENT, report
    )


def test_g064_readiness_failure_has_no_post_persistent_halt_path(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "runtime"
    write_g064_persistent_halt_no_post(
        state_root=state_root,
        generation_digest="sha256:" + "c" * 64,
        reviewed_files_digest=DIGEST,
    )
    payload = (state_root / "g064-runtime-halt.json").read_text(encoding="utf-8")
    assert '"status":"HALTED"' in payload
    assert '"broker_write":false' in payload
    assert '"actual_post_count":0' in payload


def test_g064_halt_writer_rejects_temp_race_and_mismatched_existing_halt(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "runtime"
    state_root.mkdir()
    temporary = state_root / f"g064-runtime-halt.json.{os.getpid()}.tmp"
    temporary.write_text("unsafe", encoding="utf-8")
    with pytest.raises(V4G064ActivationError):
        write_g064_persistent_halt_no_post(
            state_root=state_root,
            generation_digest="sha256:" + "c" * 64,
            reviewed_files_digest=DIGEST,
        )
    temporary.unlink()
    write_g064_persistent_halt_no_post(
        state_root=state_root,
        generation_digest="sha256:" + "c" * 64,
        reviewed_files_digest=DIGEST,
    )
    with pytest.raises(V4G064ActivationError):
        write_g064_persistent_halt_no_post(
            state_root=state_root,
            generation_digest="sha256:" + "d" * 64,
            reviewed_files_digest=DIGEST,
        )
