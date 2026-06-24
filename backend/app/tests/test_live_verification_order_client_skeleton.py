from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.broker_boundary import (
    NoNetworkBrokerBoundaryResult,
    evaluate_no_network_broker_boundary,
)
from app.live_verification.errors import LiveVerificationOrderClientSkeletonError
from app.live_verification.intent import OrderIntent, build_order_intent_from_allowed_decision
from app.live_verification.order_client_skeleton import (
    NO_NETWORK_CLIENT_MODE,
    DisabledOrderClientPlan,
    build_disabled_order_client_plan,
)
from app.live_verification.order_review import (
    FinalOrderChecklist,
    OrderReview,
    build_order_review_from_intent,
    evaluate_final_order_checklist,
)
from app.live_verification.payload_candidate import (
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


def _unchecked_candidate(**overrides: object) -> MockedOrderPayloadCandidate:
    values = asdict(_candidate())
    values.update(overrides)
    candidate = object.__new__(MockedOrderPayloadCandidate)
    for field_name, value in values.items():
        object.__setattr__(candidate, field_name, value)
    return candidate


def test_disabled_order_client_plan_builds_from_passed_candidate() -> None:
    candidate = _candidate()

    plan = build_disabled_order_client_plan(candidate=candidate, created_at=CREATED_AT)
    same = build_disabled_order_client_plan(candidate=candidate, created_at=CREATED_AT)

    assert isinstance(plan, DisabledOrderClientPlan)
    assert plan.client_plan_id == same.client_plan_id
    assert plan.payload_candidate_id == candidate.mocked_payload_candidate_id
    assert plan.order_review_id == candidate.order_review_id
    assert plan.final_checklist_id == candidate.final_checklist_id
    assert plan.boundary_check_id == candidate.boundary_check_id
    assert plan.verification_run_id == candidate.verification_run_id
    assert plan.symbol == "USD_JPY"
    assert plan.units == 100
    assert plan.execution_type == "MARKET"
    assert plan.time_in_force == "FAK"
    assert plan.settle_type == "OPEN"
    assert plan.client_mode == NO_NETWORK_CLIENT_MODE
    assert plan.disabled_by_default is True
    assert plan.network_enabled is False
    assert plan.credential_access_enabled is False
    assert plan.manual_confirmation_required is True
    assert plan.ready_for_future_review is True
    assert plan.created_at == CREATED_AT
    assert plan.fail_reasons == ()


def test_disabled_order_client_plan_does_not_hold_transport_or_credentials() -> None:
    plan = build_disabled_order_client_plan(candidate=_candidate(), created_at=CREATED_AT)
    fields = set(asdict(plan))
    blocked_fields = {
        "endpoint",
        "method",
        "path",
        "url",
        "request_body",
        "body",
        "payload",
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
    assert all(not hasattr(plan, field_name) for field_name in blocked_fields)


@pytest.mark.parametrize(
    "overrides",
    [
        {"network_used": True},
        {"api_key_used": True},
        {"broker_called": True},
        {"real_order_attempted": True},
    ],
)
def test_disabled_order_client_plan_rejects_candidate_that_crossed_boundary(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(LiveVerificationOrderClientSkeletonError):
        build_disabled_order_client_plan(candidate=_unchecked_candidate(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"boundary_check_id": ""},
        {"final_checklist_id": ""},
        {"order_review_id": ""},
        {"mocked_payload_candidate_id": "mocked_payload_run_2_mismatch"},
        {"verification_run_id": "run_2"},
        {"symbol": "EUR_USD"},
        {"size": 101},
        {"execution_type": "LIMIT"},
        {"time_in_force": "FAS"},
        {"settle_type": "CLOSE"},
        {"mode": "shadow"},
        {"manual_confirmation_required": False},
    ],
)
def test_disabled_order_client_plan_rejects_unsafe_candidate_fields(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(LiveVerificationOrderClientSkeletonError):
        build_disabled_order_client_plan(candidate=_unchecked_candidate(**overrides))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"disabled_by_default": False},
        {"network_enabled": True},
        {"credential_access_enabled": True},
        {"manual_confirmation_required": False},
        {"client_mode": "network_client"},
    ],
)
def test_disabled_order_client_plan_rejects_unsafe_plan_flags(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(LiveVerificationOrderClientSkeletonError):
        build_disabled_order_client_plan(candidate=_candidate(), **kwargs)


def test_disabled_order_client_plan_rejects_naive_created_at() -> None:
    with pytest.raises(LiveVerificationOrderClientSkeletonError):
        build_disabled_order_client_plan(
            candidate=_candidate(),
            created_at=datetime(2026, 1, 1, 0, 0),
        )
