from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.broker_boundary import (
    NoNetworkBrokerBoundaryResult,
    evaluate_no_network_broker_boundary,
)
from app.live_verification.errors import LiveVerificationSignatureRequestDesignError
from app.live_verification.intent import OrderIntent, build_order_intent_from_allowed_decision
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


def _plan(
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
    plan = order_client_plan or _plan(candidate=candidate)
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


def _unchecked_candidate(**overrides: object) -> MockedOrderPayloadCandidate:
    values = asdict(_candidate())
    values.update(overrides)
    candidate = object.__new__(MockedOrderPayloadCandidate)
    for field_name, value in values.items():
        object.__setattr__(candidate, field_name, value)
    return candidate


def _unchecked_plan(**overrides: object) -> DisabledOrderClientPlan:
    values = asdict(_plan())
    values.update(overrides)
    plan = object.__new__(DisabledOrderClientPlan)
    for field_name, value in values.items():
        object.__setattr__(plan, field_name, value)
    return plan


def _unchecked_design(**overrides: object) -> SignatureHttpRequestDesignModel:
    values = asdict(_design())
    values.update(overrides)
    model = object.__new__(SignatureHttpRequestDesignModel)
    for field_name, value in values.items():
        object.__setattr__(model, field_name, value)
    return model


def test_signature_http_request_design_model_builds_from_disabled_plan() -> None:
    candidate = _candidate()
    plan = _plan(candidate=candidate)

    design = _design(order_client_plan=plan, mocked_payload_candidate=candidate)
    same = _design(order_client_plan=plan, mocked_payload_candidate=candidate)

    assert design.signature_request_design_id == same.signature_request_design_id
    assert design.order_client_plan_id == plan.client_plan_id
    assert design.mocked_payload_candidate_id == candidate.mocked_payload_candidate_id
    assert design.verification_run_id == plan.verification_run_id
    assert design.client_mode == "no_network_skeleton"
    assert design.disabled_by_default is True
    assert design.network_enabled is False
    assert design.credential_access_enabled is False
    assert design.actual_signature_created is False
    assert design.headers_created is False
    assert design.request_body_created is False
    assert design.http_request_created is False
    assert design.api_key_used is False
    assert design.api_secret_used is False
    assert design.hmac_used is False
    assert design.network_used is False
    assert design.real_order_attempted is False
    assert design.method_label == ORDER_CREATE_METHOD_LABEL
    assert design.path_label == ORDER_CREATE_PATH_LABEL
    assert design.body_shape_label == ORDER_CREATE_BODY_SHAPE_LABEL
    assert design.timestamp_placeholder == TIMESTAMP_PLACEHOLDER


def test_signing_source_candidate_is_placeholder_only() -> None:
    design = _design()

    assert design.signing_source_candidate == (
        "TIMESTAMP_PLACEHOLDER|ORDER_CREATE_METHOD_LABEL|"
        "ORDER_CREATE_PATH_LABEL|ORDER_CREATE_BODY_SHAPE_LABEL"
    )
    blocked_values = {
        "POST",
        "/private/v1/order",
        "API-KEY",
        "API-SIGN",
        "API-TIMESTAMP",
        "Authorization",
        "secret",
        "api_key",
        "api_secret",
        "signature actual value",
        "hmac digest",
        '{"symbol":"USD_JPY"}',
        "headers",
    }
    assert all(value not in design.signing_source_candidate for value in blocked_values)


def test_signature_http_request_design_model_does_not_hold_secret_or_transport_fields() -> None:
    design = _design()
    fields = set(asdict(design))
    blocked_fields = {
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
        "headers",
        "raw_headers",
        "signature",
        "api_sign",
        "actual_signature",
        "hmac_digest",
        "private_key",
        "request_body",
        "body",
        "payload",
        "raw_request",
        "raw_response",
        "endpoint",
        "path",
        "url",
        "method",
        "http_client",
    }

    assert fields.isdisjoint(blocked_fields)
    assert all(not hasattr(design, field_name) for field_name in blocked_fields)
    assert {
        "signature_request_design_id",
        "signing_source_candidate",
        "actual_signature_created",
        "method_label",
        "path_label",
        "body_shape_label",
        "timestamp_placeholder",
    }.issubset(fields)


@pytest.mark.parametrize(
    "overrides",
    [
        {"disabled_by_default": False},
        {"network_enabled": True},
        {"credential_access_enabled": True},
    ],
)
def test_signature_http_request_design_model_rejects_unsafe_plan_flags(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(LiveVerificationSignatureRequestDesignError):
        _design(
            order_client_plan=_unchecked_plan(**overrides),
            mocked_payload_candidate=_candidate(),
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"network_used": True},
        {"api_key_used": True},
        {"broker_called": True},
        {"real_order_attempted": True},
        {"verification_run_id": "run_2"},
        {"symbol": "EUR_USD"},
        {"size": 101},
        {"mode": "shadow"},
    ],
)
def test_signature_http_request_design_model_rejects_unsafe_candidate_fields(
    overrides: dict[str, object],
) -> None:
    candidate = _unchecked_candidate(**overrides)

    with pytest.raises(LiveVerificationSignatureRequestDesignError):
        _design(order_client_plan=_plan(), mocked_payload_candidate=candidate)


@pytest.mark.parametrize(
    "overrides",
    [
        {"method_label": "ORDER_ACTUAL_METHOD_LABEL"},
        {"path_label": "ORDER_ACTUAL_PATH_LABEL"},
        {"body_shape_label": "ORDER_ACTUAL_BODY_LABEL"},
        {"timestamp_placeholder": "TIMESTAMP_ACTUAL_VALUE"},
    ],
)
def test_signature_http_request_design_model_rejects_unapproved_design_labels(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(LiveVerificationSignatureRequestDesignError):
        _design(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"signing_source_candidate": "TIMESTAMP_PLACEHOLDER|POST"},
        {"signing_source_candidate": "TIMESTAMP_PLACEHOLDER|/private/v1/order"},
        {"signing_source_candidate": "API-KEY|API-SIGN|API-TIMESTAMP"},
        {"signing_source_candidate": "Authorization|headers|secret"},
        {"actual_signature_created": True},
        {"headers_created": True},
        {"request_body_created": True},
        {"http_request_created": True},
        {"api_key_used": True},
        {"api_secret_used": True},
        {"hmac_used": True},
        {"network_used": True},
        {"real_order_attempted": True},
    ],
)
def test_signature_http_request_design_model_rejects_actual_secret_or_http_state(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(LiveVerificationSignatureRequestDesignError):
        SignatureHttpRequestDesignModel(**asdict(_unchecked_design(**overrides)))
