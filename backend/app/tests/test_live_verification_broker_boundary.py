from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.broker_boundary import evaluate_no_network_broker_boundary
from app.live_verification.intent import (
    OrderIntent,
    build_order_intent_from_allowed_decision,
)
from app.live_verification.order_review import (
    FinalOrderChecklist,
    OrderReview,
    build_order_review_from_intent,
    evaluate_final_order_checklist,
)
from app.live_verification.state import LiveVerificationState

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
EXPIRES_AT = CREATED_AT + timedelta(minutes=10)


def _intent(**overrides: object) -> OrderIntent:
    kwargs = {
        "candidate_id": "cand_run_1_000001_buy_abc123",
        "decision_id": "risk_cand_run_1_000001_buy_abc123_def456",
        "readonly_precheck_id": "precheck_run_1_abc123",
        "verification_run_id": "run_1",
        "symbol": "USD_JPY",
        "side": "BUY",
        "units": 100,
        "risk_decision_status": "ALLOW_SHADOW",
        "readonly_precheck_passed": True,
        "manual_confirmation_required": True,
        "created_at": CREATED_AT,
        "expires_at": EXPIRES_AT,
    }
    kwargs.update(overrides)
    return build_order_intent_from_allowed_decision(**kwargs)


def _review(**overrides: object) -> OrderReview:
    kwargs = {"intent": _intent(), "ready_for_order_review": True}
    kwargs.update(overrides)
    return build_order_review_from_intent(**kwargs)


def _checklist(**overrides: object) -> FinalOrderChecklist:
    kwargs = {
        "order_review": _review(),
        "git_clean": True,
        "tests_passed": True,
        "ruff_passed": True,
        "secret_scan_passed": True,
        "no_open_positions": True,
        "no_active_orders": True,
        "single_intent_for_run": True,
        "user_explicit_approval": True,
        "broker_not_implemented": True,
        "order_api_not_implemented": True,
        "raw_response_not_saved": True,
        "headers_not_saved": True,
        "signature_not_saved": True,
    }
    kwargs.update(overrides)
    return evaluate_final_order_checklist(**kwargs)


def _unchecked_review(**overrides: object) -> OrderReview:
    values = asdict(_review())
    values.update(overrides)
    review = object.__new__(OrderReview)
    for field_name, value in values.items():
        object.__setattr__(review, field_name, value)
    return review


def _unchecked_checklist(**overrides: object) -> FinalOrderChecklist:
    values = asdict(_checklist())
    values.update(overrides)
    checklist = object.__new__(FinalOrderChecklist)
    for field_name, value in values.items():
        object.__setattr__(checklist, field_name, value)
    return checklist


def test_no_network_boundary_passes_for_review_checklist_and_ready_state() -> None:
    review = _review()
    checklist = _checklist(order_review=review)

    result = evaluate_no_network_broker_boundary(
        order_review=review,
        final_checklist=checklist,
        final_state=LiveVerificationState.READY_FOR_ORDER_REVIEW,
    )
    same = evaluate_no_network_broker_boundary(
        order_review=review,
        final_checklist=checklist,
        final_state=LiveVerificationState.READY_FOR_ORDER_REVIEW,
    )

    assert result.boundary_passed is True
    assert result.fail_reasons == ()
    assert result.boundary_check_id == same.boundary_check_id
    assert result.order_review_id == review.order_review_id
    assert result.order_intent_id == review.order_intent_id
    assert result.verification_run_id == review.verification_run_id
    assert result.final_checklist_id == checklist.checklist_id
    assert result.final_state == "READY_FOR_ORDER_REVIEW"
    assert result.network_used is False
    assert result.api_key_used is False
    assert result.order_payload_created is False
    assert result.broker_called is False
    assert result.real_order_attempted is False


def test_no_network_boundary_fails_when_final_checklist_is_not_passed() -> None:
    review = _review()
    checklist = _checklist(order_review=review, git_clean=False)

    result = evaluate_no_network_broker_boundary(
        order_review=review,
        final_checklist=checklist,
        final_state=LiveVerificationState.READY_FOR_ORDER_REVIEW,
    )

    assert result.boundary_passed is False
    assert "final_checklist_not_passed" in result.fail_reasons
    assert "final_checklist:git_clean" in result.fail_reasons


def test_no_network_boundary_fails_when_final_state_is_not_ready() -> None:
    review = _review()
    checklist = _checklist(order_review=review)

    result = evaluate_no_network_broker_boundary(
        order_review=review,
        final_checklist=checklist,
        final_state=LiveVerificationState.MANUAL_CONFIRMATION_REQUIRED,
    )

    assert result.boundary_passed is False
    assert "final_state_not_ready_for_order_review" in result.fail_reasons


def test_no_network_boundary_accumulates_multiple_fail_closed_reasons() -> None:
    review = _review()
    checklist = _checklist(order_review=review, git_clean=False, tests_passed=False)

    result = evaluate_no_network_broker_boundary(
        order_review=review,
        final_checklist=checklist,
        final_state=LiveVerificationState.MANUAL_CONFIRMATION_REQUIRED,
        network_used=True,
        api_key_used=True,
        order_payload_created=True,
        broker_called=True,
        real_order_attempted=True,
    )

    assert result.boundary_passed is False
    assert "final_checklist_not_passed" in result.fail_reasons
    assert "final_checklist:git_clean" in result.fail_reasons
    assert "final_checklist:tests_passed" in result.fail_reasons
    assert "final_state_not_ready_for_order_review" in result.fail_reasons
    assert "network_used" in result.fail_reasons
    assert "api_key_used" in result.fail_reasons
    assert "order_payload_created" in result.fail_reasons
    assert "broker_called" in result.fail_reasons
    assert "real_order_attempted" in result.fail_reasons


@pytest.mark.parametrize(
    "flag_name",
    [
        "network_used",
        "api_key_used",
        "order_payload_created",
        "broker_called",
        "real_order_attempted",
    ],
)
def test_no_network_boundary_fails_when_no_network_flag_is_crossed(flag_name: str) -> None:
    review = _review()
    checklist = _checklist(order_review=review)

    result = evaluate_no_network_broker_boundary(
        order_review=review,
        final_checklist=checklist,
        final_state=LiveVerificationState.READY_FOR_ORDER_REVIEW,
        **{flag_name: True},
    )

    assert result.boundary_passed is False
    assert flag_name in result.fail_reasons


@pytest.mark.parametrize(
    ("review", "reason"),
    [
        (_unchecked_review(symbol="EUR_USD"), "symbol_not_usd_jpy"),
        (_unchecked_review(units=101), "units_not_100"),
        (_unchecked_review(mode="shadow"), "mode_not_live_verification"),
        (_unchecked_review(order_review_id=""), "order_review_id_missing"),
    ],
)
def test_no_network_boundary_fails_for_unsafe_review_fields(
    review: OrderReview,
    reason: str,
) -> None:
    checklist = _checklist(order_review=_review())

    result = evaluate_no_network_broker_boundary(
        order_review=review,
        final_checklist=checklist,
        final_state=LiveVerificationState.READY_FOR_ORDER_REVIEW,
    )

    assert result.boundary_passed is False
    assert reason in result.fail_reasons


def test_no_network_boundary_fails_when_final_checklist_id_is_missing() -> None:
    review = _review()
    checklist = _unchecked_checklist(checklist_id="")

    result = evaluate_no_network_broker_boundary(
        order_review=review,
        final_checklist=checklist,
        final_state=LiveVerificationState.READY_FOR_ORDER_REVIEW,
    )

    assert result.boundary_passed is False
    assert "final_checklist_id_missing" in result.fail_reasons


def test_no_network_boundary_fails_when_verification_run_ids_do_not_match() -> None:
    review = _review()
    second_intent = _intent(
        candidate_id="cand_run_2_000001_buy_abc123",
        decision_id="risk_cand_run_2_000001_buy_abc123_def456",
        readonly_precheck_id="precheck_run_2_abc123",
        verification_run_id="run_2",
    )
    second_review = _review(intent=second_intent)
    checklist = _checklist(order_review=second_review)

    result = evaluate_no_network_broker_boundary(
        order_review=review,
        final_checklist=checklist,
        final_state=LiveVerificationState.READY_FOR_ORDER_REVIEW,
    )

    assert result.boundary_passed is False
    assert "verification_run_id_mismatch" in result.fail_reasons
    assert "order_review_id_mismatch" in result.fail_reasons


def test_no_network_boundary_accumulates_id_mismatch_and_checklist_failures() -> None:
    review = _review()
    second_intent = _intent(
        candidate_id="cand_run_2_000001_buy_abc123",
        decision_id="risk_cand_run_2_000001_buy_abc123_def456",
        readonly_precheck_id="precheck_run_2_abc123",
        verification_run_id="run_2",
    )
    second_review = _review(intent=second_intent)
    checklist = _checklist(
        order_review=second_review,
        ruff_passed=False,
        secret_scan_passed=False,
    )

    result = evaluate_no_network_broker_boundary(
        order_review=review,
        final_checklist=checklist,
        final_state=LiveVerificationState.INIT,
    )

    assert result.boundary_passed is False
    assert "verification_run_id_mismatch" in result.fail_reasons
    assert "order_review_id_mismatch" in result.fail_reasons
    assert "final_checklist_not_passed" in result.fail_reasons
    assert "final_checklist:ruff_passed" in result.fail_reasons
    assert "final_checklist:secret_scan_passed" in result.fail_reasons
    assert "final_state_not_ready_for_order_review" in result.fail_reasons


def test_no_network_boundary_result_does_not_hold_payload_transport_or_credentials() -> None:
    result = evaluate_no_network_broker_boundary(
        order_review=_review(),
        final_checklist=_checklist(),
        final_state=LiveVerificationState.READY_FOR_ORDER_REVIEW,
    )
    fields = set(asdict(result))

    blocked_fields = {
        "price",
        "order_price",
        "orderType",
        "order_type",
        "executionType",
        "execution_type",
        "timeInForce",
        "time_in_force",
        "settleType",
        "settle_type",
        "losscutPrice",
        "losscut_price",
        "order_payload",
        "payload",
        "request_body",
        "body",
        "endpoint",
        "method",
        "path",
        "url",
        "raw_response",
        "response_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "secret",
        "token",
    }

    assert fields.isdisjoint(blocked_fields)
