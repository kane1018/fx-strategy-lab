from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.correlation import (
    CandidateReference,
    RiskDecisionReference,
    SignalReference,
    build_correlated_order_intent,
    transition_after_readonly_precheck,
    transition_after_risk_decision,
)
from app.live_verification.errors import (
    LiveVerificationCorrelationError,
    LiveVerificationIntentError,
    LiveVerificationPrecheckError,
    LiveVerificationStateError,
)
from app.live_verification.intent import OrderIntent
from app.live_verification.precheck import evaluate_readonly_precheck
from app.live_verification.state import (
    LiveVerificationState,
    transition_live_verification_state,
)

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
EXPIRES_AT = CREATED_AT + timedelta(minutes=10)


def _signal(*, run_id: str = "run_1", signal_id: str = "signal_1") -> SignalReference:
    return SignalReference(signal_id=signal_id, verification_run_id=run_id)


def _candidate(
    *,
    run_id: str = "run_1",
    signal_id: str = "signal_1",
    candidate_id: str = "cand_run_1_000001_buy_abc123",
    symbol: str = "USD_JPY",
    units: int = 100,
) -> CandidateReference:
    return CandidateReference(
        candidate_id=candidate_id,
        signal_id=signal_id,
        verification_run_id=run_id,
        symbol=symbol,
        side="BUY",
        units=units,
    )


def _decision(
    *,
    run_id: str = "run_1",
    candidate_id: str = "cand_run_1_000001_buy_abc123",
    decision_id: str = "risk_cand_run_1_000001_buy_abc123_def456",
    status: str = "ALLOW_SHADOW",
) -> RiskDecisionReference:
    return RiskDecisionReference(
        decision_id=decision_id,
        candidate_id=candidate_id,
        verification_run_id=run_id,
        status=status,
    )


def _precheck(*, run_id: str = "run_1", passed: bool = True):
    return evaluate_readonly_precheck(
        symbol="USD_JPY",
        verification_run_id=run_id,
        expected_units=100,
        account_assets_ok=passed,
        open_positions_ok=True,
        active_orders_ok=True,
        has_open_positions=False,
        has_active_orders=False,
        raw_response_saved=False,
        headers_saved=False,
        credentials_printed=False,
    )


def _intent(
    *,
    signal: SignalReference | None = None,
    candidate: CandidateReference | None = None,
    decision: RiskDecisionReference | None = None,
    precheck=None,
    existing_intents: tuple[OrderIntent, ...] = (),
    manual_confirmation_required: bool = True,
) -> OrderIntent:
    return build_correlated_order_intent(
        signal=signal or _signal(),
        candidate=candidate or _candidate(),
        decision=decision or _decision(),
        precheck=precheck or _precheck(),
        manual_confirmation_required=manual_confirmation_required,
        existing_intents=existing_intents,
        created_at=CREATED_AT,
        expires_at=EXPIRES_AT,
    )


def test_correlated_ids_build_deterministic_order_intent() -> None:
    intent = _intent()
    same = _intent()

    assert intent.order_intent_id == same.order_intent_id
    assert intent.candidate_id == "cand_run_1_000001_buy_abc123"
    assert intent.decision_id == "risk_cand_run_1_000001_buy_abc123_def456"
    assert intent.readonly_precheck_id == _precheck().readonly_precheck_id
    assert intent.verification_run_id == "run_1"
    assert intent.symbol == "USD_JPY"
    assert intent.units == 100
    assert intent.manual_confirmation_required is True
    assert intent.readonly_precheck_passed is True


@pytest.mark.parametrize(
    "factory",
    [
        lambda: _candidate(candidate_id=""),
        lambda: _decision(decision_id=""),
        lambda: replace(_precheck(), readonly_precheck_id=""),
        lambda: _signal(run_id=""),
        lambda: _candidate(run_id=""),
        lambda: _decision(run_id=""),
    ],
)
def test_required_ids_are_rejected(factory) -> None:
    with pytest.raises((LiveVerificationCorrelationError, LiveVerificationPrecheckError)):
        factory()


@pytest.mark.parametrize(
    ("kwargs", "error_type"),
    [
        ({"decision": _decision(status="REJECT_SHADOW")}, LiveVerificationCorrelationError),
        ({"precheck": _precheck(passed=False)}, LiveVerificationCorrelationError),
        ({"candidate": _candidate(symbol="EUR_USD")}, LiveVerificationIntentError),
        ({"candidate": _candidate(units=101)}, LiveVerificationIntentError),
        ({"manual_confirmation_required": False}, LiveVerificationIntentError),
    ],
)
def test_unsafe_or_incomplete_correlation_rejects_intent(
    kwargs: dict,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        _intent(**kwargs)


@pytest.mark.parametrize(
    "override",
    [
        {"candidate": _candidate(run_id="candidate_run")},
        {"decision": _decision(run_id="decision_run")},
        {"precheck": _precheck(run_id="precheck_run")},
    ],
)
def test_verification_run_id_mismatch_is_rejected(override: dict) -> None:
    with pytest.raises(LiveVerificationCorrelationError):
        _intent(**override)


def test_candidate_signal_mismatch_is_rejected() -> None:
    with pytest.raises(LiveVerificationCorrelationError):
        _intent(candidate=_candidate(signal_id="other_signal"))


def test_decision_candidate_mismatch_is_rejected() -> None:
    with pytest.raises(LiveVerificationCorrelationError):
        _intent(decision=_decision(candidate_id="other_candidate"))


def test_same_run_rejects_second_intent_but_different_run_can_build() -> None:
    first = _intent()

    with pytest.raises(LiveVerificationIntentError):
        _intent(existing_intents=(first,))

    other_run_intent = _intent(
        signal=_signal(run_id="run_2", signal_id="signal_2"),
        candidate=_candidate(
            run_id="run_2",
            signal_id="signal_2",
            candidate_id="cand_run_2_000001_buy_abc123",
        ),
        decision=_decision(
            run_id="run_2",
            candidate_id="cand_run_2_000001_buy_abc123",
            decision_id="risk_cand_run_2_000001_buy_abc123_def456",
        ),
        precheck=_precheck(run_id="run_2"),
        existing_intents=(first,),
    )

    assert other_run_intent.verification_run_id == "run_2"


def test_state_correlation_reaches_ready_for_review_only_after_valid_steps() -> None:
    state = LiveVerificationState.INIT
    state = transition_live_verification_state(state, LiveVerificationState.READONLY_PRECHECK)
    state = transition_after_readonly_precheck(state, _precheck())
    state = transition_after_risk_decision(state, _decision())
    state = transition_live_verification_state(
        state,
        LiveVerificationState.MANUAL_CONFIRMATION_REQUIRED,
    )
    state = transition_live_verification_state(
        state,
        LiveVerificationState.READY_FOR_ORDER_REVIEW,
    )

    assert state is LiveVerificationState.READY_FOR_ORDER_REVIEW


def test_state_correlation_rejects_failed_precheck_before_risk_confirmation() -> None:
    state = transition_live_verification_state(
        LiveVerificationState.INIT,
        LiveVerificationState.READONLY_PRECHECK,
    )

    with pytest.raises(LiveVerificationCorrelationError):
        transition_after_readonly_precheck(state, _precheck(passed=False))


def test_state_correlation_rejects_rejected_decision_before_intent_created() -> None:
    state = transition_live_verification_state(
        LiveVerificationState.READONLY_PRECHECK,
        LiveVerificationState.RISK_DECISION_CONFIRMED,
    )

    with pytest.raises(LiveVerificationCorrelationError):
        transition_after_risk_decision(state, _decision(status="REJECT_SHADOW"))


def test_ready_for_review_does_not_continue_to_transmission_state() -> None:
    blocked_values = {
        "ORDER" "_SENT",
        "BROKER" "_SUBMIT",
        "PRIVATE" "_ORDER_API",
        "LIVE" "_ORDER_PLACED",
    }
    state_values = {state.value for state in LiveVerificationState}

    assert state_values.isdisjoint(blocked_values)
    with pytest.raises(LiveVerificationStateError):
        transition_live_verification_state(
            LiveVerificationState.READY_FOR_ORDER_REVIEW,
            "ORDER" "_SENT",
        )
