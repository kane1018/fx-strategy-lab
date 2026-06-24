from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.correlation import (
    CandidateReference,
    RiskDecisionReference,
    SignalReference,
)
from app.live_verification.dry_run import (
    ReadonlyPrecheckInput,
    run_live_verification_dry_run,
)
from app.live_verification.errors import LiveVerificationStateError
from app.live_verification.intent import OrderIntent
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


def _precheck_input(
    *,
    run_id: str = "run_1",
    symbol: str = "USD_JPY",
    expected_units: int = 100,
    account_assets_ok: bool = True,
    open_positions_ok: bool = True,
    active_orders_ok: bool = True,
    has_open_positions: bool = False,
    has_active_orders: bool = False,
    raw_response_saved: bool = False,
    headers_saved: bool = False,
    credentials_printed: bool = False,
    retry_attempted: bool = False,
) -> ReadonlyPrecheckInput:
    return ReadonlyPrecheckInput(
        symbol=symbol,
        verification_run_id=run_id,
        expected_units=expected_units,
        account_assets_ok=account_assets_ok,
        open_positions_ok=open_positions_ok,
        active_orders_ok=active_orders_ok,
        has_open_positions=has_open_positions,
        has_active_orders=has_active_orders,
        raw_response_saved=raw_response_saved,
        headers_saved=headers_saved,
        credentials_printed=credentials_printed,
        retry_attempted=retry_attempted,
    )


def _run(
    *,
    signal: SignalReference | None = None,
    candidate: CandidateReference | None = None,
    decision: RiskDecisionReference | None = None,
    precheck_input: ReadonlyPrecheckInput | None = None,
    existing_intents: tuple[OrderIntent, ...] = (),
    manual_confirmation_required: bool = True,
):
    return run_live_verification_dry_run(
        signal=signal or _signal(),
        candidate=candidate or _candidate(),
        decision=decision or _decision(),
        precheck_input=precheck_input or _precheck_input(),
        manual_confirmation_required=manual_confirmation_required,
        existing_intents=existing_intents,
        created_at=CREATED_AT,
        expires_at=EXPIRES_AT,
    )


@pytest.mark.parametrize("status", ["ALLOW_SHADOW", "ALLOW"])
def test_dry_run_reaches_ready_for_order_review_with_correlated_allow_flow(
    status: str,
) -> None:
    result = _run(decision=_decision(status=status))

    assert result.ready_for_order_review is True
    assert result.final_state is LiveVerificationState.READY_FOR_ORDER_REVIEW
    assert result.fail_reason is None
    assert result.safety_flags == ()
    assert result.state_history == (
        LiveVerificationState.INIT,
        LiveVerificationState.READONLY_PRECHECK,
        LiveVerificationState.RISK_DECISION_CONFIRMED,
        LiveVerificationState.ORDER_INTENT_CREATED,
        LiveVerificationState.MANUAL_CONFIRMATION_REQUIRED,
        LiveVerificationState.READY_FOR_ORDER_REVIEW,
    )
    assert result.order_intent is not None
    assert result.order_intent_id == result.order_intent.order_intent_id
    assert result.readonly_precheck_id == result.order_intent.readonly_precheck_id
    assert result.order_intent.candidate_id == "cand_run_1_000001_buy_abc123"
    assert result.order_intent.decision_id == "risk_cand_run_1_000001_buy_abc123_def456"
    assert result.order_intent.verification_run_id == "run_1"
    assert result.order_intent.symbol == "USD_JPY"
    assert result.order_intent.units == 100
    assert result.order_intent.mode == "live_verification"
    assert result.order_intent.manual_confirmation_required is True


@pytest.mark.parametrize(
    ("precheck_input", "safety_flag"),
    [
        (_precheck_input(account_assets_ok=False), "account_assets_failed"),
        (_precheck_input(open_positions_ok=False), "open_positions_failed"),
        (_precheck_input(active_orders_ok=False), "active_orders_failed"),
        (_precheck_input(has_open_positions=True), "has_open_positions"),
        (_precheck_input(has_active_orders=True), "has_active_orders"),
        (_precheck_input(raw_response_saved=True), "raw_response_saved"),
        (_precheck_input(headers_saved=True), "headers_saved"),
        (_precheck_input(credentials_printed=True), "credentials_printed"),
        (_precheck_input(retry_attempted=True), "retry_attempted"),
    ],
)
def test_dry_run_precheck_failures_fail_closed(
    precheck_input: ReadonlyPrecheckInput,
    safety_flag: str,
) -> None:
    result = _run(precheck_input=precheck_input)

    assert result.ready_for_order_review is False
    assert result.final_state is LiveVerificationState.FAILED
    assert result.order_intent is None
    assert result.order_intent_id is None
    assert result.fail_reason == "read-only precheck failed"
    assert safety_flag in result.safety_flags
    assert LiveVerificationState.READY_FOR_ORDER_REVIEW not in result.state_history


def test_dry_run_rejects_non_allow_risk_decision() -> None:
    result = _run(decision=_decision(status="REJECT_SHADOW"))

    assert result.final_state is LiveVerificationState.FAILED
    assert result.ready_for_order_review is False
    assert result.order_intent is None
    assert "LiveVerificationCorrelationError" in result.safety_flags
    assert LiveVerificationState.ORDER_INTENT_CREATED not in result.state_history


@pytest.mark.parametrize(
    "override",
    [
        {"candidate": _candidate(run_id="candidate_run")},
        {"decision": _decision(run_id="decision_run")},
        {"precheck_input": _precheck_input(run_id="precheck_run")},
    ],
)
def test_dry_run_rejects_verification_run_id_mismatch(override: dict) -> None:
    result = _run(**override)

    assert result.final_state is LiveVerificationState.FAILED
    assert result.ready_for_order_review is False
    assert result.order_intent is None
    assert "LiveVerificationCorrelationError" in result.safety_flags


@pytest.mark.parametrize(
    "override",
    [
        {"candidate": _candidate(symbol="EUR_USD")},
        {"candidate": _candidate(units=101)},
        {"manual_confirmation_required": False},
    ],
)
def test_dry_run_rejects_unsupported_intent_inputs(override: dict) -> None:
    result = _run(**override)

    assert result.final_state is LiveVerificationState.FAILED
    assert result.ready_for_order_review is False
    assert result.order_intent is None
    assert "LiveVerificationIntentError" in result.safety_flags


def test_dry_run_rejects_second_intent_for_same_verification_run() -> None:
    first = _run()
    assert first.order_intent is not None

    second = _run(existing_intents=(first.order_intent,))

    assert second.final_state is LiveVerificationState.FAILED
    assert second.ready_for_order_review is False
    assert second.order_intent is None
    assert "LiveVerificationIntentError" in second.safety_flags


def test_dry_run_result_does_not_hold_transport_or_credential_fields() -> None:
    fields = set(asdict(_run()))

    assert "raw_response" not in fields
    assert "headers" not in fields
    assert "signature" not in fields
    assert "api_key" not in fields
    assert "api_secret" not in fields
    assert "order_payload" not in fields


def test_dry_run_stops_at_ready_for_order_review_without_transmission_state() -> None:
    state_values = {state.value for state in LiveVerificationState}
    blocked_values = {
        "ORDER" "_SENT",
        "BROKER" "_SUBMIT",
        "PRIVATE" "_ORDER_API",
        "LIVE" "_ORDER_PLACED",
    }

    assert state_values.isdisjoint(blocked_values)
    with pytest.raises(LiveVerificationStateError):
        transition_live_verification_state(
            LiveVerificationState.READY_FOR_ORDER_REVIEW,
            "ORDER" "_SENT",
        )


@pytest.mark.parametrize(
    "terminal_state",
    [LiveVerificationState.STOPPED, LiveVerificationState.FAILED],
)
def test_dry_run_terminal_states_do_not_reach_ready_for_review(
    terminal_state: LiveVerificationState,
) -> None:
    with pytest.raises(LiveVerificationStateError):
        transition_live_verification_state(
            terminal_state,
            LiveVerificationState.READY_FOR_ORDER_REVIEW,
        )
