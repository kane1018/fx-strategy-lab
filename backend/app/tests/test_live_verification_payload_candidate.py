from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.broker_boundary import (
    NoNetworkBrokerBoundaryResult,
    evaluate_no_network_broker_boundary,
)
from app.live_verification.errors import LiveVerificationPayloadCandidateError
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
from app.live_verification.payload_candidate import (
    ALLOWED_MOCKED_EXECUTION_TYPES,
    ALLOWED_MOCKED_SETTLE_TYPES,
    ALLOWED_MOCKED_TIME_IN_FORCE,
    MockedOrderPayloadCandidate,
    build_mocked_order_payload_candidate,
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


def _checklist(
    *,
    order_review: OrderReview | None = None,
    **overrides: object,
) -> FinalOrderChecklist:
    review = order_review or _review()
    kwargs = {
        "order_review": review,
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


def _boundary(
    *,
    order_review: OrderReview | None = None,
    final_checklist: FinalOrderChecklist | None = None,
    final_state: LiveVerificationState | str = LiveVerificationState.READY_FOR_ORDER_REVIEW,
    **overrides: object,
) -> NoNetworkBrokerBoundaryResult:
    review = order_review or _review()
    checklist = final_checklist or _checklist(order_review=review)
    kwargs = {
        "order_review": review,
        "final_checklist": checklist,
        "final_state": final_state,
    }
    kwargs.update(overrides)
    return evaluate_no_network_broker_boundary(**kwargs)


def _candidate(
    *,
    order_review: OrderReview | None = None,
    final_checklist: FinalOrderChecklist | None = None,
    boundary_result: NoNetworkBrokerBoundaryResult | None = None,
    execution_type: str = "MARKET",
    time_in_force: str = "FAK",
    settle_type: str = "OPEN",
) -> MockedOrderPayloadCandidate:
    review = order_review or _review()
    checklist = final_checklist or _checklist(order_review=review)
    boundary = boundary_result or _boundary(order_review=review, final_checklist=checklist)
    return build_mocked_order_payload_candidate(
        order_review=review,
        final_checklist=checklist,
        boundary_result=boundary,
        execution_type=execution_type,
        time_in_force=time_in_force,
        settle_type=settle_type,
    )


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


def _unchecked_boundary(**overrides: object) -> NoNetworkBrokerBoundaryResult:
    values = asdict(_boundary())
    values.update(overrides)
    boundary = object.__new__(NoNetworkBrokerBoundaryResult)
    for field_name, value in values.items():
        object.__setattr__(boundary, field_name, value)
    return boundary


def test_mocked_order_payload_candidate_builds_from_passed_review_checklist_and_boundary() -> None:
    review = _review()
    checklist = _checklist(order_review=review)
    boundary = _boundary(order_review=review, final_checklist=checklist)

    candidate = _candidate(
        order_review=review,
        final_checklist=checklist,
        boundary_result=boundary,
    )
    same = _candidate(
        order_review=review,
        final_checklist=checklist,
        boundary_result=boundary,
    )

    assert candidate.mocked_payload_candidate_id == same.mocked_payload_candidate_id
    assert candidate.order_review_id == review.order_review_id
    assert candidate.order_intent_id == review.order_intent_id
    assert candidate.verification_run_id == review.verification_run_id
    assert candidate.final_checklist_id == checklist.checklist_id
    assert candidate.boundary_check_id == boundary.boundary_check_id
    assert candidate.symbol == "USD_JPY"
    assert candidate.side.value == "BUY"
    assert candidate.size == 100
    assert candidate.execution_type == "MARKET"
    assert candidate.time_in_force == "FAK"
    assert candidate.settle_type == "OPEN"
    assert candidate.mode == "live_verification"
    assert candidate.manual_confirmation_required is True
    assert candidate.network_used is False
    assert candidate.api_key_used is False
    assert candidate.broker_called is False
    assert candidate.real_order_attempted is False


def test_mocked_order_payload_candidate_does_not_hold_transport_or_credentials() -> None:
    candidate = _candidate()
    fields = set(asdict(candidate))
    blocked_fields = {
        "price",
        "order_price",
        "orderType",
        "order_type",
        "executionType",
        "timeInForce",
        "settleType",
        "losscutPrice",
        "losscut_price",
        "endpoint",
        "method",
        "path",
        "url",
        "request_body",
        "body",
        "payload",
        "order_payload",
        "raw_response",
        "response_headers",
        "headers",
        "signature",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
        "timestamp",
        "sign",
    }

    assert fields.isdisjoint(blocked_fields)
    assert all(not hasattr(candidate, field_name) for field_name in blocked_fields)
    assert {"execution_type", "time_in_force", "settle_type"}.issubset(fields)


def test_mocked_order_payload_candidate_allowed_values_are_fixed() -> None:
    candidate = _candidate(
        execution_type="MARKET",
        time_in_force="FAK",
        settle_type="OPEN",
    )

    assert ALLOWED_MOCKED_EXECUTION_TYPES == frozenset({"MARKET"})
    assert ALLOWED_MOCKED_TIME_IN_FORCE == frozenset({"FAK"})
    assert ALLOWED_MOCKED_SETTLE_TYPES == frozenset({"OPEN"})
    assert candidate.execution_type == "MARKET"
    assert candidate.time_in_force == "FAK"
    assert candidate.settle_type == "OPEN"


def test_mocked_order_payload_candidate_rejects_unpassed_final_checklist() -> None:
    review = _review()
    checklist = _checklist(order_review=review, git_clean=False)
    boundary = _boundary(order_review=review, final_checklist=checklist)

    with pytest.raises(LiveVerificationPayloadCandidateError):
        _candidate(order_review=review, final_checklist=checklist, boundary_result=boundary)


def test_mocked_order_payload_candidate_rejects_unpassed_boundary_result() -> None:
    review = _review()
    checklist = _checklist(order_review=review)
    boundary = _boundary(order_review=review, final_checklist=checklist, network_used=True)

    with pytest.raises(LiveVerificationPayloadCandidateError):
        _candidate(order_review=review, final_checklist=checklist, boundary_result=boundary)


def test_mocked_order_payload_candidate_rejects_boundary_state_other_than_ready() -> None:
    boundary = _unchecked_boundary(
        final_state=LiveVerificationState.MANUAL_CONFIRMATION_REQUIRED.value,
        boundary_passed=True,
        fail_reasons=(),
    )

    with pytest.raises(LiveVerificationPayloadCandidateError):
        _candidate(boundary_result=boundary)


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
def test_mocked_order_payload_candidate_rejects_crossed_boundary_flags(
    flag_name: str,
) -> None:
    review = _review()
    checklist = _checklist(order_review=review)
    boundary = _boundary(
        order_review=review,
        final_checklist=checklist,
        **{flag_name: True},
    )

    with pytest.raises(LiveVerificationPayloadCandidateError):
        _candidate(order_review=review, final_checklist=checklist, boundary_result=boundary)


def test_mocked_order_payload_candidate_rejects_verification_run_id_mismatch() -> None:
    boundary = _unchecked_boundary(verification_run_id="run_2")

    with pytest.raises(LiveVerificationPayloadCandidateError):
        _candidate(boundary_result=boundary)


def test_mocked_order_payload_candidate_rejects_order_review_id_mismatch() -> None:
    review = _review()
    checklist = _checklist(order_review=review)
    boundary = _unchecked_boundary(order_review_id="review_run_1_other")

    with pytest.raises(LiveVerificationPayloadCandidateError):
        _candidate(order_review=review, final_checklist=checklist, boundary_result=boundary)


def test_mocked_order_payload_candidate_rejects_checklist_order_review_id_mismatch() -> None:
    review = _review()
    checklist = _unchecked_checklist(order_review_id="review_run_1_other")
    boundary = _boundary(order_review=review, final_checklist=_checklist(order_review=review))

    with pytest.raises(LiveVerificationPayloadCandidateError):
        _candidate(order_review=review, final_checklist=checklist, boundary_result=boundary)


def test_mocked_order_payload_candidate_rejects_final_checklist_id_mismatch() -> None:
    boundary = _unchecked_boundary(final_checklist_id="checklist_run_1_other")

    with pytest.raises(LiveVerificationPayloadCandidateError):
        _candidate(boundary_result=boundary)


def test_mocked_order_payload_candidate_rejects_missing_boundary_check_id() -> None:
    boundary = _unchecked_boundary(boundary_check_id="")

    with pytest.raises(LiveVerificationPayloadCandidateError):
        _candidate(boundary_result=boundary)


@pytest.mark.parametrize(
    "review",
    [
        _unchecked_review(symbol="EUR_USD"),
        _unchecked_review(units=101),
        _unchecked_review(mode="shadow"),
        _unchecked_review(manual_confirmation_required=False),
    ],
)
def test_mocked_order_payload_candidate_rejects_unsafe_order_review_fields(
    review: OrderReview,
) -> None:
    checklist = _checklist(order_review=_review())
    boundary = _boundary(order_review=_review(), final_checklist=checklist)

    with pytest.raises(LiveVerificationPayloadCandidateError):
        build_mocked_order_payload_candidate(
            order_review=review,
            final_checklist=checklist,
            boundary_result=boundary,
            execution_type="MARKET",
            time_in_force="FAK",
            settle_type="OPEN",
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("execution_type", "LIMIT"),
        ("execution_type", "market"),
        ("execution_type", "Market"),
        ("execution_type", "MARKET "),
        ("execution_type", "executionType"),
        ("time_in_force", "FAS"),
        ("time_in_force", "fak"),
        ("time_in_force", "Fak"),
        ("time_in_force", "FAK "),
        ("time_in_force", "timeInForce"),
        ("settle_type", "CLOSE"),
        ("settle_type", "open"),
        ("settle_type", "Open"),
        ("settle_type", "OPEN "),
        ("settle_type", "settleType"),
    ],
)
def test_mocked_order_payload_candidate_rejects_unsupported_local_values(
    field_name: str,
    value: str,
) -> None:
    kwargs = {
        "execution_type": "MARKET",
        "time_in_force": "FAK",
        "settle_type": "OPEN",
        field_name: value,
    }

    with pytest.raises(LiveVerificationPayloadCandidateError):
        _candidate(**kwargs)
