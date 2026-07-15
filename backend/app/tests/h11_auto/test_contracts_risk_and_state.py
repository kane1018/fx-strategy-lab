from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.h11_auto.contracts import (
    FormalHorizon,
    FormalSignal,
    H11AutoContractError,
    PhaseAExecutionPolicy,
    SignalDecision,
    build_intent_id,
)
from app.h11_auto.risk import (
    PhaseASafetySnapshot,
    evaluate_phase_a_entry_gate,
    review_actual_readiness,
)
from app.h11_auto.state_machine import (
    AutoCycleState,
    H11AutoStateError,
    SafeBrokerState,
    evaluate_boot_reconcile,
    require_transition,
)

NOW = datetime(2026, 7, 15, 1, 0, tzinfo=UTC)


def signal(
    *,
    decision: SignalDecision = SignalDecision.BUY,
    horizon: FormalHorizon = FormalHorizon.MINUTES_10,
    rolling: bool = False,
) -> FormalSignal:
    return FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:synthetic-signal-config",
        horizon=horizon,
        observed_at_utc=NOW,
        valid_until_utc=NOW + timedelta(minutes=10),
        decision=decision,
        probability_up=Decimal("0.61"),
        rolling_estimate=rolling,
    )


def policy() -> PhaseAExecutionPolicy:
    return PhaseAExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:synthetic-signal-config",
        selected_horizon=FormalHorizon.MINUTES_10,
    )


def open_safety() -> PhaseASafetySnapshot:
    return PhaseASafetySnapshot(
        boot_reconciled=True,
        process_lock_held=True,
        data_fresh=True,
        clock_synchronized=True,
        notification_path_ready=True,
    )


def test_only_finalized_formal_signal_is_accepted() -> None:
    assert signal().fingerprint == signal().fingerprint
    with pytest.raises(H11AutoContractError, match="finalized formal"):
        signal(rolling=True)
    with pytest.raises(H11AutoContractError, match="timezone-aware"):
        FormalSignal(
            strategy_version="SHORT_V1",
            signal_config_hash="sha256:test",
            horizon=FormalHorizon.MINUTES_10,
            observed_at_utc=datetime(2026, 7, 15),
            valid_until_utc=datetime(2026, 7, 15, 0, 10),
            decision=SignalDecision.BUY,
            probability_up=Decimal("0.6"),
        )
    for invalid_probability in (Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(H11AutoContractError, match="probability_up"):
            FormalSignal(
                strategy_version="SHORT_V1",
                signal_config_hash="sha256:test",
                horizon=FormalHorizon.MINUTES_10,
                observed_at_utc=NOW,
                valid_until_utc=NOW + timedelta(minutes=10),
                decision=SignalDecision.BUY,
                probability_up=invalid_probability,
            )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_positions", 2),
        ("max_entries_per_day", 2),
        ("scale_in_allowed", True),
        ("hedging_allowed", True),
        ("opposite_signal_as_exit_allowed", True),
        ("retry_allowed", True),
        ("repost_allowed", True),
        ("max_entry_attempts_per_intent", 2),
        ("broker_native_protected_entry_required", False),
    ],
)
def test_policy_safety_invariants_cannot_be_weakened(field: str, value: object) -> None:
    with pytest.raises(H11AutoContractError, match="cannot be weakened"):
        replace(policy(), **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_positions", True),
        ("max_entries_per_day", True),
        ("scale_in_allowed", 0),
        ("broker_native_protected_entry_required", 1),
    ],
)
def test_policy_refuses_boolean_integer_type_confusion(
    field: str, value: object
) -> None:
    with pytest.raises(H11AutoContractError, match="cannot be weakened"):
        replace(policy(), **{field: value})


def test_intent_id_is_deterministic_and_policy_bound() -> None:
    first = build_intent_id(signal=signal(), policy=policy())
    assert first == build_intent_id(signal=signal(), policy=policy())
    with pytest.raises(H11AutoContractError, match="does not match"):
        build_intent_id(
            signal=signal(horizon=FormalHorizon.MINUTES_30), policy=policy()
        )


def test_entry_gate_allows_only_clean_fake_cycle() -> None:
    clear = evaluate_phase_a_entry_gate(
        signal=signal(), policy=policy(), snapshot=open_safety(), now_utc=NOW
    )
    assert clear.fake_cycle_allowed is True
    assert clear.actual_post_allowed is False
    assert clear.broker_write_allowed is False

    conflict = evaluate_phase_a_entry_gate(
        signal=signal(),
        policy=policy(),
        snapshot=replace(open_safety(), external_or_manual_position_detected=True),
        now_utc=NOW,
    )
    assert conflict.fake_cycle_allowed is False
    assert "EXTERNAL_OR_MANUAL_POSITION_DETECTED" in conflict.blocked_reasons


def test_stay_expired_and_second_daily_entry_are_refused() -> None:
    stay = evaluate_phase_a_entry_gate(
        signal=signal(decision=SignalDecision.STAY),
        policy=policy(),
        snapshot=open_safety(),
        now_utc=NOW,
    )
    assert stay.fake_cycle_allowed is False
    assert "STAY_HAS_NO_ENTRY" in stay.blocked_reasons

    expired = evaluate_phase_a_entry_gate(
        signal=signal(),
        policy=policy(),
        snapshot=open_safety(),
        now_utc=NOW + timedelta(minutes=11),
    )
    assert "SIGNAL_EXPIRED_OR_CLOCK_INVALID" in expired.blocked_reasons

    second = evaluate_phase_a_entry_gate(
        signal=signal(),
        policy=policy(),
        snapshot=replace(open_safety(), entries_today=1),
        now_utc=NOW,
    )
    assert "MAX_ENTRIES_PER_DAY_REACHED" in second.blocked_reasons


def test_actual_readiness_can_be_structurally_clear_without_permission() -> None:
    blocked = review_actual_readiness()
    assert blocked.structurally_ready_for_later_adapter_review is False
    assert len(blocked.blocked_reasons) == 6
    clear = review_actual_readiness(
        broker_native_atomic_protection_confirmed=True,
        short_pending_expiry_confirmed=True,
        partial_fill_size_safety_confirmed=True,
        dedicated_account_confirmed=True,
        operator_risk_limits_frozen=True,
        always_on_host_confirmed=True,
    )
    assert clear.structurally_ready_for_later_adapter_review is True
    assert clear.actual_transport_present is False
    assert clear.actual_post_allowed is False
    assert clear.broker_write_allowed is False
    assert clear.credential_read_allowed is False


def test_state_machine_has_no_shortcut_to_position_or_restart_from_halt() -> None:
    require_transition(AutoCycleState.INTENT_PERSISTED, AutoCycleState.PROTECTED_ENTRY_PENDING)
    with pytest.raises(H11AutoStateError):
        require_transition(AutoCycleState.INTENT_PERSISTED, AutoCycleState.POSITION_PROTECTED)
    with pytest.raises(H11AutoStateError):
        require_transition(
            AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
            AutoCycleState.WAITING_SIGNAL,
        )


def test_boot_reconcile_is_state_specific_and_fail_closed() -> None:
    clear = evaluate_boot_reconcile(
        local_state=AutoCycleState.WAITING_SIGNAL,
        broker_state=SafeBrokerState.FLAT_CLEAR,
        safe_read_fresh=True,
    )
    assert clear.reconciled is True
    assert clear.target_state is AutoCycleState.ARMED
    assert clear.actual_post_allowed is False

    conflict = evaluate_boot_reconcile(
        local_state=AutoCycleState.WAITING_SIGNAL,
        broker_state=SafeBrokerState.EXTERNAL_OR_MANUAL_CONFLICT,
        safe_read_fresh=True,
    )
    assert conflict.reconciled is False
    assert conflict.target_state is AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED

    stale = evaluate_boot_reconcile(
        local_state=AutoCycleState.POSITION_PROTECTED,
        broker_state=SafeBrokerState.POSITION_PROTECTED,
        safe_read_fresh=False,
    )
    assert stale.reconciled is False
    assert "SAFE_READ_NOT_FRESH" in stale.blocked_reasons
