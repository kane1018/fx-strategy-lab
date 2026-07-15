from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.h11_auto.contracts import (
    FormalHorizon,
    FormalSignal,
    PhaseAExecutionPolicy,
    SignalDecision,
)
from app.h11_auto.persistence import H11AutoStateStore
from app.h11_auto.recovery import RecoveryAction, evaluate_restart_recovery
from app.h11_auto.state_machine import AutoCycleState, SafeBrokerState

NOW = datetime(2026, 7, 15, 3, 0, tzinfo=UTC)


def _cycle(tmp_path: Path):  # type: ignore[no-untyped-def]
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    signal = FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:recovery-test",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=NOW,
        valid_until_utc=NOW + timedelta(minutes=10),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.6"),
    )
    policy = PhaseAExecutionPolicy(
        strategy_version=signal.strategy_version,
        signal_config_hash=signal.signal_config_hash,
        selected_horizon=signal.horizon,
    )
    cycle = store.create_intent(signal=signal, policy=policy, now_utc=NOW)
    return store, cycle


def test_restart_before_attempt_can_continue_only_as_first_synthetic_attempt(
    tmp_path: Path,
) -> None:
    _, cycle = _cycle(tmp_path)
    decision = evaluate_restart_recovery(
        cycle=cycle, broker_state=SafeBrokerState.FLAT_CLEAR, safe_read_fresh=True
    )
    assert decision.action is RecoveryAction.START_SYNTHETIC_ATTEMPT
    assert decision.safe_to_continue_observation is True
    assert decision.entry_resend_allowed is False
    assert decision.actual_post_allowed is False


def test_crash_after_attempt_never_allows_entry_resend(tmp_path: Path) -> None:
    store, cycle = _cycle(tmp_path)
    pending = store.record_attempt_started(intent_id=cycle.intent_id, now_utc=NOW)
    decision = evaluate_restart_recovery(
        cycle=pending,
        broker_state=SafeBrokerState.PROTECTED_ENTRY_PENDING,
        safe_read_fresh=True,
    )
    assert decision.action is RecoveryAction.OBSERVE_PENDING_NO_RESEND
    assert decision.entry_resend_allowed is False
    assert decision.exit_resend_allowed is False


def test_unknown_stale_or_external_state_always_halts(tmp_path: Path) -> None:
    _, cycle = _cycle(tmp_path)
    for broker_state, fresh in (
        (SafeBrokerState.UNKNOWN, True),
        (SafeBrokerState.EXTERNAL_OR_MANUAL_CONFLICT, True),
        (SafeBrokerState.FLAT_CLEAR, False),
    ):
        decision = evaluate_restart_recovery(
            cycle=cycle, broker_state=broker_state, safe_read_fresh=fresh
        )
        assert decision.action is RecoveryAction.HALT_OPERATOR_REVIEW
        assert decision.safe_to_continue_observation is False
        assert decision.entry_resend_allowed is False


def test_exit_unknown_never_allows_second_exit_attempt(tmp_path: Path) -> None:
    store, cycle = _cycle(tmp_path)
    pending = store.record_attempt_started(intent_id=cycle.intent_id, now_utc=NOW)
    protected = store.transition(
        intent_id=cycle.intent_id,
        target=AutoCycleState.POSITION_PROTECTED,
        event_category="POSITION_PROTECTED_SYNTHETIC",
        now_utc=NOW,
    )
    assert pending.attempt_count == 1
    exiting = store.record_exit_attempt_started(
        intent_id=protected.intent_id, now_utc=NOW
    )
    decision = evaluate_restart_recovery(
        cycle=exiting,
        broker_state=SafeBrokerState.POSITION_PROTECTED,
        safe_read_fresh=True,
    )
    assert decision.action is RecoveryAction.HALT_OPERATOR_REVIEW
    assert decision.blocked_reasons == ("EXIT_RESULT_UNKNOWN_NO_RESEND",)
    assert decision.exit_resend_allowed is False


@pytest.mark.parametrize(
    "broker_state",
    [SafeBrokerState.FLAT_CLEAR, SafeBrokerState.FLAT_AFTER_EXIT],
)
def test_flat_reconciliation_can_resume_observation_without_write(
    tmp_path: Path, broker_state: SafeBrokerState
) -> None:
    store, cycle = _cycle(tmp_path)
    store.record_attempt_started(intent_id=cycle.intent_id, now_utc=NOW)
    store.transition(
        intent_id=cycle.intent_id,
        target=AutoCycleState.POSITION_PROTECTED,
        event_category="POSITION_PROTECTED_SYNTHETIC",
        now_utc=NOW,
    )
    store.record_exit_attempt_started(intent_id=cycle.intent_id, now_utc=NOW)
    flat = store.transition(
        intent_id=cycle.intent_id,
        target=AutoCycleState.FLAT_RECONCILED,
        event_category="FLAT_RECONCILED_SYNTHETIC",
        now_utc=NOW,
    )
    decision = evaluate_restart_recovery(
        cycle=flat, broker_state=broker_state, safe_read_fresh=True
    )
    assert decision.action is RecoveryAction.CONFIRM_FLAT_NO_WRITE
    assert decision.actual_post_allowed is False
