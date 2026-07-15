"""No-POST tests for H-11 v3 persistent runtime safety primitives."""

from __future__ import annotations

import inspect
import json
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.h11_stage1_paper_wiring import MONTHLY_MAX_LOSS_JPY
from app.services.h11_v3_observed_live_state import H11V3ObservedState
from app.services.h11_v3_runtime_safety import (
    H11V3BootReconcileInput,
    H11V3BrokerCycleSafeStatus,
    H11V3DeadManStore,
    H11V3FakeNotifier,
    H11V3FillCompletenessStatus,
    H11V3JournalEvent,
    H11V3NotificationCategory,
    H11V3PendingExpiryStatus,
    H11V3PostEntryReconcileInput,
    H11V3ProtectionChildrenStatus,
    H11V3RiskPersistentState,
    H11V3RiskStopState,
    H11V3RiskStore,
    H11V3RuntimeSafetyError,
    H11V3SafeJournal,
    H11V3SafeJournalRecord,
    engage_h11_v3_kill,
    evaluate_h11_v3_boot_reconcile,
    evaluate_h11_v3_post_entry_reconcile,
    evaluate_h11_v3_risk_before_entry,
    operator_reload_h11_v3_risk,
    record_h11_v3_closed_result,
    record_h11_v3_entry_attempt,
)


def test_safe_journal_appends_and_verifies_chain(tmp_path: Path) -> None:
    journal = H11V3SafeJournal(tmp_path / "journal.jsonl")
    journal.append(
        cycle_day_jst="2026-07-13",
        event=H11V3JournalEvent.BOOT_RECONCILED,
        state=H11V3ObservedState.READY,
    )
    journal.append(
        cycle_day_jst="2026-07-13",
        event=H11V3JournalEvent.INTENT_PERSISTED,
        state=H11V3ObservedState.INTENT_PERSISTED,
    )
    summary = journal.summary()
    assert summary.valid is True
    assert summary.record_count == 2
    assert summary.actual_post_count == 0
    assert summary.raw_id_value_exposure is False
    assert journal.read_verified()[1].previous_digest == journal.read_verified()[0].digest


def test_safe_journal_detects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    journal = H11V3SafeJournal(path)
    journal.append(
        cycle_day_jst="2026-07-13",
        event=H11V3JournalEvent.BOOT_RECONCILED,
        state=H11V3ObservedState.READY,
    )
    payload = json.loads(path.read_text())
    payload["state_safe_label"] = H11V3ObservedState.HALTED.value
    path.write_text(json.dumps(payload) + "\n")
    with pytest.raises(H11V3RuntimeSafetyError, match="verification"):
        journal.read_verified()


def test_safe_journal_record_has_no_raw_value_fields() -> None:
    names = {field.name for field in fields(H11V3SafeJournalRecord)}
    forbidden = {
        "price",
        "pnl",
        "size",
        "order_id",
        "position_id",
        "execution_id",
        "client_order_id",
        "credential",
        "raw_request",
        "raw_response",
    }
    assert names.isdisjoint(forbidden)


def test_risk_gate_enforces_one_entry_per_day_and_daily_reset() -> None:
    state = H11V3RiskPersistentState()
    assert evaluate_h11_v3_risk_before_entry(
        state=state, cycle_day_jst="2026-07-13"
    ).allowed
    record_h11_v3_entry_attempt(state=state, cycle_day_jst="2026-07-13")
    same_day = evaluate_h11_v3_risk_before_entry(
        state=state, cycle_day_jst="2026-07-13"
    )
    assert same_day.allowed is False
    assert "MAX_ENTRIES_PER_DAY_REACHED" in same_day.blocked_reasons
    assert evaluate_h11_v3_risk_before_entry(
        state=state, cycle_day_jst="2026-07-14"
    ).allowed


def test_risk_stops_on_daily_and_resets_next_day() -> None:
    state = H11V3RiskPersistentState()
    record_h11_v3_closed_result(
        state=state, cycle_day_jst="2026-07-13", pnl_jpy_internal=-5_000
    )
    stop = record_h11_v3_closed_result(
        state=state, cycle_day_jst="2026-07-13", pnl_jpy_internal=-5_000
    )
    assert stop is H11V3RiskStopState.STOPPED_DAILY_BUDGET
    next_day = evaluate_h11_v3_risk_before_entry(
        state=state, cycle_day_jst="2026-07-14"
    )
    assert next_day.allowed is True
    assert next_day.stop_state is H11V3RiskStopState.ACTIVE


def test_risk_stops_on_monthly_budget_and_loss_figure_survives_rollover() -> None:
    state = H11V3RiskPersistentState()
    # Per-trade loss stays within PER_TRADE_MAX_LOSS_BOUND_JPY (5,000) so this
    # exercises the monthly-budget path rather than the per-trade KILL path.
    # A win is interleaved before every 5th loss so consecutive_losses never
    # reaches MAX_CONSECUTIVE_LOSSES_STOP (5) and pre-empts the monthly stop.
    # Dates land near month-end (like the v2 Stage 1 equivalent test) so
    # 2026-08-01 falls inside the 14-day cooling window.
    pnl_sequence = [
        -5_000,
        -5_000,
        -5_000,
        -5_000,
        0,
        -5_000,
        -5_000,
        -5_000,
        -5_000,
        0,
        -5_000,
        -5_000,
    ]
    stop = H11V3RiskStopState.ACTIVE
    for offset, pnl in enumerate(pnl_sequence):
        stop = record_h11_v3_closed_result(
            state=state,
            cycle_day_jst=f"2026-07-{14 + offset:02d}",
            pnl_jpy_internal=pnl,
        )
        if stop is not H11V3RiskStopState.ACTIVE:
            break
    assert stop is H11V3RiskStopState.STOPPED_MONTHLY_BUDGET
    assert state.stopped_on_jst == "2026-07-25"
    lost_at_stop = state.monthly_loss_jpy
    assert lost_at_stop >= MONTHLY_MAX_LOSS_JPY

    # Cross into next month without ever calling operator_reload_h11_v3_risk.
    blocked = evaluate_h11_v3_risk_before_entry(
        state=state, cycle_day_jst="2026-08-01"
    )
    assert blocked.allowed is False
    assert blocked.stop_state is H11V3RiskStopState.STOPPED_MONTHLY_BUDGET
    # The post-mortem evidence must survive the calendar rollover, not reset.
    assert state.monthly_loss_jpy == lost_at_stop

    # Next month but inside the 14-day cooling window (7 days): still refused.
    assert not operator_reload_h11_v3_risk(
        state=state,
        reload_day_jst="2026-08-01",
        postmortem_complete=True,
        review_approved=True,
    )
    assert operator_reload_h11_v3_risk(
        state=state,
        reload_day_jst="2026-08-15",
        postmortem_complete=True,
        review_approved=True,
    )
    assert state.stop_state == H11V3RiskStopState.ACTIVE.value
    assert state.monthly_loss_jpy == 0


def test_risk_stops_on_consecutive_losses_and_reload_rules() -> None:
    state = H11V3RiskPersistentState()
    for offset in range(5):
        stop = record_h11_v3_closed_result(
            state=state,
            cycle_day_jst=f"2026-07-{13 + offset:02d}",
            pnl_jpy_internal=-1_000,
        )
    assert stop is H11V3RiskStopState.STOPPED_CONSECUTIVE_LOSSES
    assert not operator_reload_h11_v3_risk(
        state=state,
        reload_day_jst="2026-07-31",
        postmortem_complete=True,
        review_approved=True,
    )
    assert operator_reload_h11_v3_risk(
        state=state,
        reload_day_jst="2026-08-03",
        postmortem_complete=True,
        review_approved=True,
    )
    assert state.stop_state == H11V3RiskStopState.ACTIVE.value


def test_per_trade_bound_violation_kills_and_persists(tmp_path: Path) -> None:
    state = H11V3RiskPersistentState()
    stop = record_h11_v3_closed_result(
        state=state, cycle_day_jst="2026-07-13", pnl_jpy_internal=-5_001
    )
    assert stop is H11V3RiskStopState.KILLED
    assert state.discipline_violation_count == 1
    store = H11V3RiskStore(tmp_path / "risk.json")
    store.save(state)
    assert store.load().stop_state == H11V3RiskStopState.KILLED.value


def test_malformed_risk_state_is_safe_error(tmp_path: Path) -> None:
    path = tmp_path / "risk.json"
    path.write_text("not-json")
    with pytest.raises(H11V3RuntimeSafetyError, match="malformed"):
        H11V3RiskStore(path).load()


def test_kill_is_fail_closed() -> None:
    state = H11V3RiskPersistentState()
    engage_h11_v3_kill(state=state, cycle_day_jst="2026-07-13")
    gate = evaluate_h11_v3_risk_before_entry(
        state=state, cycle_day_jst="2026-07-13"
    )
    assert gate.allowed is False
    assert gate.stop_state is H11V3RiskStopState.KILLED


@pytest.mark.parametrize(
    ("local", "broker", "expected"),
    [
        (
            H11V3ObservedState.READY,
            H11V3BrokerCycleSafeStatus.FLAT_CLEAR,
            True,
        ),
        (
            H11V3ObservedState.PROTECTED_ORDER_ACTIVE,
            H11V3BrokerCycleSafeStatus.PROTECTED_PENDING,
            True,
        ),
        (
            H11V3ObservedState.POSITION_PROTECTED,
            H11V3BrokerCycleSafeStatus.POSITION_PROTECTED,
            True,
        ),
        (
            H11V3ObservedState.READY,
            H11V3BrokerCycleSafeStatus.POSITION_PROTECTED,
            False,
        ),
        (
            H11V3ObservedState.ENTRY_ATTEMPT_STARTED,
            H11V3BrokerCycleSafeStatus.UNKNOWN,
            False,
        ),
    ],
)
def test_boot_reconciliation_is_state_specific(
    local: H11V3ObservedState,
    broker: H11V3BrokerCycleSafeStatus,
    expected: bool,
) -> None:
    result = evaluate_h11_v3_boot_reconcile(
        H11V3BootReconcileInput(
            local_state=local,
            broker_status=broker,
            safe_read_performed=True,
            safe_read_fresh=True,
        )
    )
    assert result.reconciled is expected
    assert result.actual_post_allowed is False


def test_missing_boot_read_and_notification_failure_are_safe() -> None:
    boot = evaluate_h11_v3_boot_reconcile(
        H11V3BootReconcileInput(local_state=H11V3ObservedState.READY)
    )
    assert boot.reconciled is False
    notifier = H11V3FakeNotifier(fail=True)
    assert notifier.notify(H11V3NotificationCategory.UNKNOWN_HALTED) is False
    assert notifier.external_send is False


def test_post_entry_reconcile_requires_full_fill_both_children_and_expiry() -> None:
    ready = evaluate_h11_v3_post_entry_reconcile(
        H11V3PostEntryReconcileInput(
            fill_status=H11V3FillCompletenessStatus.FULL,
            protection_status=H11V3ProtectionChildrenStatus.BOTH_ACTIVE,
            pending_expiry_status=(
                H11V3PendingExpiryStatus.CONFIRMED_WITHIN_SIGNAL_WINDOW
            ),
            safe_read_performed=True,
            safe_read_fresh=True,
        )
    )
    assert ready.protected_position_ready is True
    assert ready.halt_required is False
    assert ready.actual_post_allowed is False

    partial = evaluate_h11_v3_post_entry_reconcile(
        H11V3PostEntryReconcileInput(
            fill_status=H11V3FillCompletenessStatus.PARTIAL,
            protection_status=H11V3ProtectionChildrenStatus.ONE_OR_MORE_MISSING,
            pending_expiry_status=H11V3PendingExpiryStatus.UNKNOWN,
            safe_read_performed=True,
            safe_read_fresh=True,
        )
    )
    assert partial.protected_position_ready is False
    assert partial.halt_required is True
    assert partial.retry_allowed is False
    assert partial.repost_allowed is False
    assert partial.second_entry_post_allowed is False
    assert "ENTRY_FILL_PARTIAL_HALT" in partial.reasons


def test_dead_man_missing_stale_future_and_alive(tmp_path: Path) -> None:
    store = H11V3DeadManStore(tmp_path / "heartbeat.json")
    now = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)
    assert store.evaluate(now_utc=now, maximum_age_seconds=180).halt_required

    store.heartbeat(heartbeat_utc=now)
    alive = store.evaluate(
        now_utc=now + timedelta(seconds=180), maximum_age_seconds=180
    )
    assert alive.alive is True
    assert alive.halt_required is False

    stale = store.evaluate(
        now_utc=now + timedelta(seconds=181), maximum_age_seconds=180
    )
    assert stale.alive is False
    assert stale.reason_safe_label == "DEAD_MAN_HEARTBEAT_STALE"

    future = store.evaluate(
        now_utc=now - timedelta(seconds=1), maximum_age_seconds=180
    )
    assert future.reason_safe_label == "DEAD_MAN_HEARTBEAT_FROM_FUTURE"

    (tmp_path / "heartbeat.json").write_text(
        json.dumps(
            {
                "config_hash": H11V3RiskPersistentState().config_hash,
                "last_heartbeat_utc": "2026-07-13T00:00:00",
            }
        )
    )
    invalid = store.evaluate(now_utc=now, maximum_age_seconds=180)
    assert invalid.reason_safe_label == "DEAD_MAN_STATE_INVALID"


def test_runtime_safety_module_has_no_external_capability() -> None:
    import app.services.h11_v3_runtime_safety as module

    source = inspect.getsource(module)
    for marker in (
        "httpx",
        "requests",
        "os.environ",
        "getenv",
        "load_dotenv",
        "build_auth_headers",
        "assert_real_broker_post_allowed",
        "allow=True",
    ):
        assert marker not in source
