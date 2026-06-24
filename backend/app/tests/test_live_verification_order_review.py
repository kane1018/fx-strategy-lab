from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.errors import LiveVerificationOrderReviewError
from app.live_verification.intent import (
    OrderIntent,
    OrderIntentSide,
    build_order_intent_from_allowed_decision,
)
from app.live_verification.order_review import (
    build_order_review_from_intent,
    evaluate_final_order_checklist,
)

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


def _unchecked_intent(**overrides: object) -> OrderIntent:
    values = asdict(_intent())
    values.update(overrides)
    intent = object.__new__(OrderIntent)
    for field_name, value in values.items():
        object.__setattr__(intent, field_name, value)
    return intent


def _review(**overrides: object):
    kwargs = {"intent": _intent(), "ready_for_order_review": True}
    kwargs.update(overrides)
    return build_order_review_from_intent(**kwargs)


def _checklist(**overrides: object):
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


def test_order_review_builds_review_only_object_from_intent() -> None:
    intent = _intent()
    review = build_order_review_from_intent(
        intent=intent,
        ready_for_order_review=True,
        review_notes=("human review pending",),
    )
    same = build_order_review_from_intent(intent=intent, ready_for_order_review=True)

    assert review.order_review_id == same.order_review_id
    assert review.order_intent_id == intent.order_intent_id
    assert review.candidate_id == intent.candidate_id
    assert review.decision_id == intent.decision_id
    assert review.readonly_precheck_id == intent.readonly_precheck_id
    assert review.verification_run_id == intent.verification_run_id
    assert review.symbol == "USD_JPY"
    assert review.side is OrderIntentSide.BUY
    assert review.units == 100
    assert review.mode == "live_verification"
    assert review.manual_confirmation_required is True
    assert review.ready_for_order_review is True
    assert review.review_notes == ("human review pending",)


def test_order_review_does_not_hold_executable_or_transport_fields() -> None:
    fields = set(asdict(_review()))

    assert "order_payload" not in fields
    assert "endpoint" not in fields
    assert "method" not in fields
    assert "raw_response" not in fields
    assert "headers" not in fields
    assert "signature" not in fields
    assert "api_key" not in fields
    assert "api_secret" not in fields


@pytest.mark.parametrize(
    "intent",
    [
        _unchecked_intent(symbol="EUR_USD"),
        _unchecked_intent(units=101),
        _unchecked_intent(mode="shadow"),
        _unchecked_intent(readonly_precheck_passed=False),
        _unchecked_intent(manual_confirmation_required=False),
        _unchecked_intent(risk_decision_status="REJECT_SHADOW"),
    ],
)
def test_order_review_rejects_unsafe_intent_fields(intent: OrderIntent) -> None:
    with pytest.raises(LiveVerificationOrderReviewError):
        build_order_review_from_intent(intent=intent, ready_for_order_review=True)


def test_order_review_rejects_not_ready_for_order_review() -> None:
    with pytest.raises(LiveVerificationOrderReviewError):
        build_order_review_from_intent(intent=_intent(), ready_for_order_review=False)


def test_final_checklist_passes_when_all_required_items_are_true() -> None:
    checklist = _checklist()
    same = _checklist()

    assert checklist.final_checklist_passed is True
    assert checklist.fail_reasons == ()
    assert checklist.checklist_id == same.checklist_id
    assert checklist.order_review_id == _review().order_review_id
    assert checklist.verification_run_id == "run_1"


@pytest.mark.parametrize(
    "field_name",
    [
        "git_clean",
        "tests_passed",
        "ruff_passed",
        "secret_scan_passed",
        "readonly_precheck_passed",
        "no_open_positions",
        "no_active_orders",
        "risk_decision_allow",
        "ready_for_order_review",
        "symbol_is_usd_jpy",
        "units_is_100",
        "single_intent_for_run",
        "manual_confirmation_required",
        "user_explicit_approval",
        "broker_not_implemented",
        "order_api_not_implemented",
        "raw_response_not_saved",
        "headers_not_saved",
        "signature_not_saved",
    ],
)
def test_final_checklist_fails_when_any_required_item_is_false(field_name: str) -> None:
    checklist = _checklist(**{field_name: False})

    assert checklist.final_checklist_passed is False
    assert field_name in checklist.fail_reasons


def test_final_checklist_records_multiple_fail_reasons() -> None:
    checklist = _checklist(
        git_clean=False,
        tests_passed=False,
        broker_not_implemented=False,
        raw_response_not_saved=False,
    )

    assert checklist.final_checklist_passed is False
    assert checklist.fail_reasons == (
        "git_clean",
        "tests_passed",
        "broker_not_implemented",
        "raw_response_not_saved",
    )
