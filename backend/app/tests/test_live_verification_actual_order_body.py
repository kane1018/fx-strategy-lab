from __future__ import annotations

from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.actual_order_body import (
    ACTUAL_ORDER_EXECUTION_TYPE,
    ACTUAL_ORDER_SETTLE_TYPE,
    ACTUAL_ORDER_TIME_IN_FORCE,
    ActualOrderRequestBody,
    build_actual_order_request_body,
    make_actual_order_body_id,
)
from app.live_verification.broker_boundary import (
    NoNetworkBrokerBoundaryResult,
    evaluate_no_network_broker_boundary,
)
from app.live_verification.errors import LiveVerificationActualOrderBodyError
from app.live_verification.http_request_skeleton import (
    DisabledHttpRequestClientSkeletonPlan,
    build_disabled_http_request_client_skeleton_plan,
)
from app.live_verification.intent import (
    OrderIntent,
    OrderIntentSide,
    build_order_intent_from_allowed_decision,
)
from app.live_verification.order_client_skeleton import (
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
from app.live_verification.signature_headers_body_plan import (
    SignatureHeadersBodyPlan,
    build_signature_headers_body_plan,
)
from app.live_verification.signature_request_design import (
    ORDER_CREATE_BODY_SHAPE_LABEL,
    ORDER_CREATE_METHOD_LABEL,
    ORDER_CREATE_PATH_LABEL,
    TIMESTAMP_PLACEHOLDER,
    SignatureHttpRequestDesignModel,
    build_signature_http_request_design_model,
)
from app.live_verification.state import LiveVerificationState

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
EXPIRES_AT = CREATED_AT + timedelta(minutes=10)
EXPECTED_BODY_FIELDS = {
    "actual_order_body_id",
    "signature_headers_body_plan_id",
    "http_request_client_skeleton_id",
    "verification_run_id",
    "symbol",
    "side",
    "size",
    "executionType",
    "timeInForce",
    "settleType",
    "body_created",
    "http_post_enabled",
    "headers_created",
    "signature_created",
    "raw_request_saved",
    "raw_response_saved",
    "credential_values_logged",
    "real_order_attempted",
}


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


def _client_plan(
    *,
    candidate: MockedOrderPayloadCandidate | None = None,
    **overrides: object,
) -> DisabledOrderClientPlan:
    kwargs = {
        "candidate": candidate or _candidate(),
        "created_at": CREATED_AT,
    }
    kwargs.update(overrides)
    return build_disabled_order_client_plan(**kwargs)


def _design(
    *,
    order_client_plan: DisabledOrderClientPlan | None = None,
    mocked_payload_candidate: MockedOrderPayloadCandidate | None = None,
    **overrides: object,
) -> SignatureHttpRequestDesignModel:
    candidate = mocked_payload_candidate or _candidate()
    plan = order_client_plan or _client_plan(candidate=candidate)
    kwargs = {
        "order_client_plan": plan,
        "mocked_payload_candidate": candidate,
        "method_label": ORDER_CREATE_METHOD_LABEL,
        "path_label": ORDER_CREATE_PATH_LABEL,
        "body_shape_label": ORDER_CREATE_BODY_SHAPE_LABEL,
        "timestamp_placeholder": TIMESTAMP_PLACEHOLDER,
    }
    kwargs.update(overrides)
    return build_signature_http_request_design_model(**kwargs)


def _skeleton(
    *,
    signature_design: SignatureHttpRequestDesignModel | None = None,
    **overrides: object,
) -> DisabledHttpRequestClientSkeletonPlan:
    kwargs = {"signature_design": signature_design or _design()}
    kwargs.update(overrides)
    return build_disabled_http_request_client_skeleton_plan(**kwargs)


def _plan(
    *,
    http_request_skeleton: DisabledHttpRequestClientSkeletonPlan | None = None,
    **overrides: object,
) -> SignatureHeadersBodyPlan:
    kwargs = {"http_request_skeleton": http_request_skeleton or _skeleton()}
    kwargs.update(overrides)
    return build_signature_headers_body_plan(**kwargs)


def _unchecked_plan(**overrides: object) -> SignatureHeadersBodyPlan:
    values = asdict(_plan())
    values.update(overrides)
    plan = object.__new__(SignatureHeadersBodyPlan)
    for field_name, value in values.items():
        object.__setattr__(plan, field_name, value)
    return plan


def _body(
    *,
    signature_headers_body_plan: SignatureHeadersBodyPlan | None = None,
    side: str | OrderIntentSide = OrderIntentSide.BUY,
    **overrides: object,
) -> ActualOrderRequestBody:
    kwargs = {
        "signature_headers_body_plan": signature_headers_body_plan or _plan(),
        "side": side,
    }
    kwargs.update(overrides)
    return build_actual_order_request_body(**kwargs)


def test_actual_order_request_body_builds_from_signature_headers_body_plan() -> None:
    plan = _plan()

    body = _body(signature_headers_body_plan=plan, side="BUY")
    same = _body(signature_headers_body_plan=plan, side=OrderIntentSide.BUY)

    assert isinstance(body, ActualOrderRequestBody)
    assert body.actual_order_body_id == same.actual_order_body_id
    assert body.actual_order_body_id == make_actual_order_body_id(
        signature_headers_body_plan_id=plan.signature_headers_body_plan_id,
        http_request_client_skeleton_id=plan.http_request_client_skeleton_id,
        verification_run_id=plan.verification_run_id,
    )
    assert body.signature_headers_body_plan_id == plan.signature_headers_body_plan_id
    assert body.http_request_client_skeleton_id == plan.http_request_client_skeleton_id
    assert body.verification_run_id == plan.verification_run_id
    assert body.symbol == "USD_JPY"
    assert body.side is OrderIntentSide.BUY
    assert body.size == 100
    assert body.executionType == ACTUAL_ORDER_EXECUTION_TYPE
    assert body.timeInForce == ACTUAL_ORDER_TIME_IN_FORCE
    assert body.settleType == ACTUAL_ORDER_SETTLE_TYPE
    assert body.body_created is True
    assert body.http_post_enabled is False
    assert body.headers_created is False
    assert body.signature_created is False
    assert body.raw_request_saved is False
    assert body.raw_response_saved is False
    assert body.credential_values_logged is False
    assert body.real_order_attempted is False


def test_actual_order_request_body_accepts_only_allowed_sides() -> None:
    sell_body = _body(side="sell")

    assert sell_body.side is OrderIntentSide.SELL

    for unsafe_side in ("", "HOLD", object()):
        with pytest.raises(LiveVerificationActualOrderBodyError):
            _body(side=unsafe_side)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"plan_passed": False},
        {"fail_reasons": ("unsafe",)},
        {"body_plan_created": False},
        {"headers_plan_created": False},
        {"signature_plan_created": False},
        {"actual_body_created": True},
        {"actual_headers_created": True},
        {"actual_signature_created": True},
        {"http_post_enabled": True},
        {"credential_values_exposed": True},
        {"raw_request_saved": True},
        {"raw_response_saved": True},
        {"headers_saved": True},
        {"signature_saved": True},
        {"api_key_value_exposed": True},
        {"api_secret_value_exposed": True},
        {"hmac_used": True},
        {"real_order_attempted": True},
        {"verification_run_id": ""},
        {"signature_headers_body_plan_id": ""},
        {"http_request_client_skeleton_id": ""},
    ],
)
def test_actual_order_request_body_rejects_unsafe_or_incomplete_plan(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(LiveVerificationActualOrderBodyError):
        _body(signature_headers_body_plan=_unchecked_plan(**overrides))


def test_actual_order_request_body_rejects_multiple_unsafe_plan_flags() -> None:
    unsafe_plan = _unchecked_plan(
        plan_passed=True,
        fail_reasons=(),
        actual_body_created=True,
        actual_headers_created=True,
        actual_signature_created=True,
        http_post_enabled=True,
        credential_values_exposed=True,
        raw_request_saved=True,
        raw_response_saved=True,
        headers_saved=True,
        signature_saved=True,
        api_key_value_exposed=True,
        api_secret_value_exposed=True,
        hmac_used=True,
        real_order_attempted=True,
    )

    with pytest.raises(LiveVerificationActualOrderBodyError):
        _body(signature_headers_body_plan=unsafe_plan)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"symbol": "EUR_USD"},
        {"size": 101},
        {"execution_type": "LIMIT"},
        {"time_in_force": "FOK"},
        {"settle_type": "CLOSE"},
        {"body_created": False},
        {"http_post_enabled": True},
        {"headers_created": True},
        {"signature_created": True},
        {"raw_request_saved": True},
        {"raw_response_saved": True},
        {"credential_values_logged": True},
        {"real_order_attempted": True},
    ],
)
def test_actual_order_request_body_rejects_unsafe_body_inputs(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(LiveVerificationActualOrderBodyError):
        _body(**kwargs)


def test_actual_order_request_body_rejects_multiple_unsafe_body_flags() -> None:
    with pytest.raises(LiveVerificationActualOrderBodyError):
        _body(
            http_post_enabled=True,
            headers_created=True,
            signature_created=True,
            raw_request_saved=True,
            raw_response_saved=True,
            credential_values_logged=True,
            real_order_attempted=True,
        )


@pytest.mark.parametrize(
    "flag_name",
    [
        "body_created",
        "http_post_enabled",
        "headers_created",
        "signature_created",
        "raw_request_saved",
        "raw_response_saved",
        "credential_values_logged",
        "real_order_attempted",
    ],
)
def test_actual_order_request_body_rejects_non_bool_safety_flags(
    flag_name: str,
) -> None:
    with pytest.raises(LiveVerificationActualOrderBodyError):
        _body(**{flag_name: "false"})


def test_actual_order_request_body_has_no_transport_header_or_credential_fields() -> None:
    body = _body()
    model_fields = {field.name for field in fields(ActualOrderRequestBody)}
    fields_from_instance = set(asdict(body))
    blocked_fields = {
        "headers",
        "actual_headers",
        "header_values",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "credential",
        "credentials",
        "authorization",
        "signature",
        "actual_signature",
        "signature_value",
        "api_sign",
        "hmac_digest",
        "raw_request",
        "raw_response",
        "http_client",
        "response",
        "endpoint",
        "method",
        "path",
        "url",
        "status_code",
        "response_body",
        "request_body",
        "request_headers",
        "body",
        "payload",
    }
    blocked_serializers = {
        "to_json",
        "json",
        "to_http_payload",
        "to_request_body",
    }

    assert model_fields == EXPECTED_BODY_FIELDS
    assert fields_from_instance == EXPECTED_BODY_FIELDS
    assert model_fields.isdisjoint(blocked_fields)
    assert all(not hasattr(body, field_name) for field_name in blocked_fields)
    assert all(not hasattr(body, name) for name in blocked_serializers)
