from __future__ import annotations

from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.broker_boundary import (
    NoNetworkBrokerBoundaryResult,
    evaluate_no_network_broker_boundary,
)
from app.live_verification.errors import LiveVerificationHttpRequestSkeletonError
from app.live_verification.http_request_skeleton import (
    NO_NETWORK_HTTP_REQUEST_CLIENT_MODE,
    DisabledHttpRequestClientSkeletonPlan,
    build_disabled_http_request_client_skeleton_plan,
    make_disabled_http_request_client_skeleton_id,
)
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
EXPECTED_SKELETON_FIELDS = {
    "http_request_client_skeleton_id",
    "signature_request_design_id",
    "order_client_plan_id",
    "mocked_payload_candidate_id",
    "verification_run_id",
    "client_mode",
    "disabled_by_default",
    "network_enabled",
    "credential_access_enabled",
    "http_client_enabled",
    "http_post_enabled",
    "headers_created",
    "request_body_created",
    "actual_signature_created",
    "raw_request_created",
    "raw_response_saved",
    "signature_saved",
    "api_key_used",
    "api_secret_used",
    "hmac_used",
    "real_order_attempted",
    "skeleton_passed",
    "fail_reasons",
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


def _unchecked_design(**overrides: object) -> SignatureHttpRequestDesignModel:
    values = asdict(_design())
    values.update(overrides)
    model = object.__new__(SignatureHttpRequestDesignModel)
    for field_name, value in values.items():
        object.__setattr__(model, field_name, value)
    return model


def _skeleton(
    *,
    signature_design: SignatureHttpRequestDesignModel | None = None,
    **overrides: object,
) -> DisabledHttpRequestClientSkeletonPlan:
    kwargs = {"signature_design": signature_design or _design()}
    kwargs.update(overrides)
    return build_disabled_http_request_client_skeleton_plan(**kwargs)


def test_disabled_http_request_client_skeleton_builds_from_signature_design() -> None:
    design = _design()

    skeleton = _skeleton(signature_design=design)
    same = _skeleton(signature_design=design)

    assert isinstance(skeleton, DisabledHttpRequestClientSkeletonPlan)
    assert skeleton.http_request_client_skeleton_id == same.http_request_client_skeleton_id
    assert skeleton.http_request_client_skeleton_id == (
        make_disabled_http_request_client_skeleton_id(
            signature_request_design_id=design.signature_request_design_id,
            order_client_plan_id=design.order_client_plan_id,
            mocked_payload_candidate_id=design.mocked_payload_candidate_id,
            verification_run_id=design.verification_run_id,
        )
    )
    assert skeleton.signature_request_design_id == design.signature_request_design_id
    assert skeleton.order_client_plan_id == design.order_client_plan_id
    assert skeleton.mocked_payload_candidate_id == design.mocked_payload_candidate_id
    assert skeleton.verification_run_id == design.verification_run_id
    assert skeleton.client_mode == NO_NETWORK_HTTP_REQUEST_CLIENT_MODE
    assert skeleton.disabled_by_default is True
    assert skeleton.network_enabled is False
    assert skeleton.credential_access_enabled is False
    assert skeleton.http_client_enabled is False
    assert skeleton.http_post_enabled is False
    assert skeleton.headers_created is False
    assert skeleton.request_body_created is False
    assert skeleton.actual_signature_created is False
    assert skeleton.raw_request_created is False
    assert skeleton.raw_response_saved is False
    assert skeleton.signature_saved is False
    assert skeleton.api_key_used is False
    assert skeleton.api_secret_used is False
    assert skeleton.hmac_used is False
    assert skeleton.real_order_attempted is False
    assert skeleton.skeleton_passed is True
    assert skeleton.fail_reasons == ()


def test_disabled_http_request_client_skeleton_has_only_safe_fields() -> None:
    skeleton = _skeleton()
    model_fields = {field.name for field in fields(DisabledHttpRequestClientSkeletonPlan)}
    fields_from_instance = set(asdict(skeleton))
    blocked_fields = {
        "endpoint",
        "method",
        "path",
        "url",
        "headers",
        "request_headers",
        "request_body",
        "body",
        "payload",
        "raw_request",
        "raw_response",
        "signature",
        "api_sign",
        "actual_signature",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
        "http_client",
        "response",
        "status_code",
        "response_body",
    }

    assert model_fields == EXPECTED_SKELETON_FIELDS
    assert fields_from_instance == EXPECTED_SKELETON_FIELDS
    assert model_fields.isdisjoint(blocked_fields)
    assert all(not hasattr(skeleton, field_name) for field_name in blocked_fields)


@pytest.mark.parametrize(
    "overrides,expected_reason",
    [
        ({"disabled_by_default": False}, "signature_design:disabled_by_default"),
        ({"network_enabled": True}, "signature_design:network_enabled"),
        (
            {"credential_access_enabled": True},
            "signature_design:credential_access_enabled",
        ),
        (
            {"actual_signature_created": True},
            "signature_design:actual_signature_created",
        ),
        ({"headers_created": True}, "signature_design:headers_created"),
        ({"request_body_created": True}, "signature_design:request_body_created"),
        ({"http_request_created": True}, "signature_design:http_request_created"),
        ({"api_key_used": True}, "signature_design:api_key_used"),
        ({"api_secret_used": True}, "signature_design:api_secret_used"),
        ({"hmac_used": True}, "signature_design:hmac_used"),
        ({"network_used": True}, "signature_design:network_used"),
        ({"real_order_attempted": True}, "signature_design:real_order_attempted"),
        ({"signature_request_design_id": ""}, "signature_request_design_id_missing"),
        ({"order_client_plan_id": ""}, "order_client_plan_id_missing"),
        ({"mocked_payload_candidate_id": ""}, "mocked_payload_candidate_id_missing"),
        ({"verification_run_id": ""}, "verification_run_id_missing"),
    ],
)
def test_disabled_http_request_client_skeleton_fails_closed_for_unsafe_signature_design(
    overrides: dict[str, object],
    expected_reason: str,
) -> None:
    skeleton = _skeleton(signature_design=_unchecked_design(**overrides))

    assert skeleton.skeleton_passed is False
    assert expected_reason in skeleton.fail_reasons


@pytest.mark.parametrize(
    "kwargs,expected_reason",
    [
        ({"client_mode": "network_http_client"}, "client_mode"),
        ({"disabled_by_default": False}, "disabled_by_default"),
        ({"network_enabled": True}, "network_enabled"),
        ({"credential_access_enabled": True}, "credential_access_enabled"),
        ({"http_client_enabled": True}, "http_client_enabled"),
        ({"http_post_enabled": True}, "http_post_enabled"),
        ({"headers_created": True}, "headers_created"),
        ({"request_body_created": True}, "request_body_created"),
        ({"actual_signature_created": True}, "actual_signature_created"),
        ({"raw_request_created": True}, "raw_request_created"),
        ({"raw_response_saved": True}, "raw_response_saved"),
        ({"signature_saved": True}, "signature_saved"),
        ({"api_key_used": True}, "api_key_used"),
        ({"api_secret_used": True}, "api_secret_used"),
        ({"hmac_used": True}, "hmac_used"),
        ({"real_order_attempted": True}, "real_order_attempted"),
    ],
)
def test_disabled_http_request_client_skeleton_fails_closed_for_unsafe_skeleton_flags(
    kwargs: dict[str, object],
    expected_reason: str,
) -> None:
    skeleton = _skeleton(**kwargs)

    assert skeleton.skeleton_passed is False
    assert expected_reason in skeleton.fail_reasons


def test_disabled_http_request_client_skeleton_keeps_multiple_fail_reasons() -> None:
    skeleton = _skeleton(
        signature_design=_unchecked_design(
            network_enabled=True,
            api_key_used=True,
            real_order_attempted=True,
        ),
        http_client_enabled=True,
        http_post_enabled=True,
        raw_response_saved=True,
    )

    assert skeleton.skeleton_passed is False
    assert {
        "signature_design:network_enabled",
        "signature_design:api_key_used",
        "signature_design:real_order_attempted",
        "http_client_enabled",
        "http_post_enabled",
        "raw_response_saved",
    }.issubset(set(skeleton.fail_reasons))


@pytest.mark.parametrize(
    "flag_name",
    [
        "disabled_by_default",
        "network_enabled",
        "credential_access_enabled",
        "http_client_enabled",
        "http_post_enabled",
        "headers_created",
        "request_body_created",
        "actual_signature_created",
        "raw_request_created",
        "raw_response_saved",
        "signature_saved",
        "api_key_used",
        "api_secret_used",
        "hmac_used",
        "real_order_attempted",
    ],
)
def test_disabled_http_request_client_skeleton_rejects_non_bool_safety_flags(
    flag_name: str,
) -> None:
    with pytest.raises(LiveVerificationHttpRequestSkeletonError):
        DisabledHttpRequestClientSkeletonPlan(
            **asdict(_skeleton(**{flag_name: "false"}))
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"skeleton_passed": True, "fail_reasons": ("unsafe",)},
        {"skeleton_passed": False, "fail_reasons": ()},
        {"network_enabled": True, "skeleton_passed": True},
    ],
)
def test_disabled_http_request_client_skeleton_rejects_inconsistent_result_state(
    overrides: dict[str, object],
) -> None:
    values = asdict(_skeleton())
    values.update(overrides)

    with pytest.raises(LiveVerificationHttpRequestSkeletonError):
        DisabledHttpRequestClientSkeletonPlan(**values)
