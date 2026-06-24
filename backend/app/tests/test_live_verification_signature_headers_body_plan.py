from __future__ import annotations

from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.broker_boundary import (
    NoNetworkBrokerBoundaryResult,
    evaluate_no_network_broker_boundary,
)
from app.live_verification.errors import LiveVerificationSignatureHeadersBodyPlanError
from app.live_verification.http_request_skeleton import (
    DisabledHttpRequestClientSkeletonPlan,
    build_disabled_http_request_client_skeleton_plan,
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
from app.live_verification.signature_headers_body_plan import (
    SIGNATURE_HEADERS_BODY_PLAN_MODE,
    SignatureHeadersBodyPlan,
    build_signature_headers_body_plan,
    make_signature_headers_body_plan_id,
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
EXPECTED_PLAN_FIELDS = {
    "signature_headers_body_plan_id",
    "http_request_client_skeleton_id",
    "signature_request_design_id",
    "order_client_plan_id",
    "mocked_payload_candidate_id",
    "verification_run_id",
    "plan_mode",
    "body_plan_created",
    "headers_plan_created",
    "signature_plan_created",
    "actual_body_created",
    "actual_headers_created",
    "actual_signature_created",
    "http_post_enabled",
    "credential_values_exposed",
    "raw_request_saved",
    "raw_response_saved",
    "headers_saved",
    "signature_saved",
    "api_key_value_exposed",
    "api_secret_value_exposed",
    "hmac_used",
    "real_order_attempted",
    "plan_passed",
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


def _unchecked_skeleton(**overrides: object) -> DisabledHttpRequestClientSkeletonPlan:
    values = asdict(_skeleton())
    values.update(overrides)
    skeleton = object.__new__(DisabledHttpRequestClientSkeletonPlan)
    for field_name, value in values.items():
        object.__setattr__(skeleton, field_name, value)
    return skeleton


def _plan(
    *,
    http_request_skeleton: DisabledHttpRequestClientSkeletonPlan | None = None,
    **overrides: object,
) -> SignatureHeadersBodyPlan:
    kwargs = {"http_request_skeleton": http_request_skeleton or _skeleton()}
    kwargs.update(overrides)
    return build_signature_headers_body_plan(**kwargs)


def test_signature_headers_body_plan_builds_from_http_request_skeleton() -> None:
    skeleton = _skeleton()

    plan = _plan(http_request_skeleton=skeleton)
    same = _plan(http_request_skeleton=skeleton)

    assert isinstance(plan, SignatureHeadersBodyPlan)
    assert plan.signature_headers_body_plan_id == same.signature_headers_body_plan_id
    assert plan.signature_headers_body_plan_id == make_signature_headers_body_plan_id(
        http_request_client_skeleton_id=skeleton.http_request_client_skeleton_id,
        signature_request_design_id=skeleton.signature_request_design_id,
        verification_run_id=skeleton.verification_run_id,
    )
    assert plan.http_request_client_skeleton_id == skeleton.http_request_client_skeleton_id
    assert plan.signature_request_design_id == skeleton.signature_request_design_id
    assert plan.order_client_plan_id == skeleton.order_client_plan_id
    assert plan.mocked_payload_candidate_id == skeleton.mocked_payload_candidate_id
    assert plan.verification_run_id == skeleton.verification_run_id
    assert plan.plan_mode == SIGNATURE_HEADERS_BODY_PLAN_MODE
    assert plan.body_plan_created is True
    assert plan.headers_plan_created is True
    assert plan.signature_plan_created is True
    assert plan.actual_body_created is False
    assert plan.actual_headers_created is False
    assert plan.actual_signature_created is False
    assert plan.http_post_enabled is False
    assert plan.credential_values_exposed is False
    assert plan.raw_request_saved is False
    assert plan.raw_response_saved is False
    assert plan.headers_saved is False
    assert plan.signature_saved is False
    assert plan.api_key_value_exposed is False
    assert plan.api_secret_value_exposed is False
    assert plan.hmac_used is False
    assert plan.real_order_attempted is False
    assert plan.plan_passed is True
    assert plan.fail_reasons == ()


def test_signature_headers_body_plan_has_only_plan_fields() -> None:
    plan = _plan()
    model_fields = {field.name for field in fields(SignatureHeadersBodyPlan)}
    fields_from_instance = set(asdict(plan))
    blocked_fields = {
        "actual_body",
        "body",
        "request_body",
        "body_json",
        "actual_headers",
        "headers",
        "header_values",
        "actual_signature",
        "signature",
        "api_sign",
        "hmac_digest",
        "api_key",
        "api_secret",
        "secret",
        "token",
        "authorization",
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
        "request_headers",
    }

    assert model_fields == EXPECTED_PLAN_FIELDS
    assert fields_from_instance == EXPECTED_PLAN_FIELDS
    assert model_fields.isdisjoint(blocked_fields)
    assert all(not hasattr(plan, field_name) for field_name in blocked_fields)


@pytest.mark.parametrize(
    "overrides,expected_reason",
    [
        ({"skeleton_passed": False}, "http_request_skeleton:not_passed"),
        (
            {"fail_reasons": ("http_client_enabled",)},
            "http_request_skeleton:fail_reasons",
        ),
        (
            {"disabled_by_default": False},
            "http_request_skeleton:disabled_by_default",
        ),
        ({"network_enabled": True}, "http_request_skeleton:network_enabled"),
        (
            {"credential_access_enabled": True},
            "http_request_skeleton:credential_access_enabled",
        ),
        ({"http_client_enabled": True}, "http_request_skeleton:http_client_enabled"),
        ({"http_post_enabled": True}, "http_request_skeleton:http_post_enabled"),
        ({"headers_created": True}, "http_request_skeleton:headers_created"),
        ({"request_body_created": True}, "http_request_skeleton:request_body_created"),
        (
            {"actual_signature_created": True},
            "http_request_skeleton:actual_signature_created",
        ),
        ({"raw_request_created": True}, "http_request_skeleton:raw_request_created"),
        ({"raw_response_saved": True}, "http_request_skeleton:raw_response_saved"),
        ({"signature_saved": True}, "http_request_skeleton:signature_saved"),
        ({"api_key_used": True}, "http_request_skeleton:api_key_used"),
        ({"api_secret_used": True}, "http_request_skeleton:api_secret_used"),
        ({"hmac_used": True}, "http_request_skeleton:hmac_used"),
        ({"real_order_attempted": True}, "http_request_skeleton:real_order_attempted"),
        ({"verification_run_id": ""}, "verification_run_id_missing"),
        (
            {"http_request_client_skeleton_id": ""},
            "http_request_client_skeleton_id_missing",
        ),
        ({"signature_request_design_id": ""}, "signature_request_design_id_missing"),
    ],
)
def test_signature_headers_body_plan_fails_closed_for_unsafe_skeleton(
    overrides: dict[str, object],
    expected_reason: str,
) -> None:
    plan = _plan(http_request_skeleton=_unchecked_skeleton(**overrides))

    assert plan.plan_passed is False
    assert expected_reason in plan.fail_reasons


@pytest.mark.parametrize(
    "kwargs,expected_reason",
    [
        ({"plan_mode": "actual_signature_headers_body"}, "plan_mode"),
        ({"body_plan_created": False}, "body_plan_created"),
        ({"headers_plan_created": False}, "headers_plan_created"),
        ({"signature_plan_created": False}, "signature_plan_created"),
        ({"actual_body_created": True}, "actual_body_created"),
        ({"actual_headers_created": True}, "actual_headers_created"),
        ({"actual_signature_created": True}, "actual_signature_created"),
        ({"http_post_enabled": True}, "http_post_enabled"),
        ({"credential_values_exposed": True}, "credential_values_exposed"),
        ({"raw_request_saved": True}, "raw_request_saved"),
        ({"raw_response_saved": True}, "raw_response_saved"),
        ({"headers_saved": True}, "headers_saved"),
        ({"signature_saved": True}, "signature_saved"),
        ({"api_key_value_exposed": True}, "api_key_value_exposed"),
        ({"api_secret_value_exposed": True}, "api_secret_value_exposed"),
        ({"hmac_used": True}, "hmac_used"),
        ({"real_order_attempted": True}, "real_order_attempted"),
    ],
)
def test_signature_headers_body_plan_fails_closed_for_unsafe_plan_flags(
    kwargs: dict[str, object],
    expected_reason: str,
) -> None:
    plan = _plan(**kwargs)

    assert plan.plan_passed is False
    assert expected_reason in plan.fail_reasons


def test_signature_headers_body_plan_keeps_multiple_fail_reasons() -> None:
    plan = _plan(
        http_request_skeleton=_unchecked_skeleton(
            network_enabled=True,
            api_key_used=True,
            fail_reasons=("unsafe_skeleton",),
        ),
        actual_body_created=True,
        actual_headers_created=True,
        actual_signature_created=True,
        http_post_enabled=True,
    )

    assert plan.plan_passed is False
    assert {
        "http_request_skeleton:network_enabled",
        "http_request_skeleton:api_key_used",
        "http_request_skeleton:fail_reasons",
        "actual_body_created",
        "actual_headers_created",
        "actual_signature_created",
        "http_post_enabled",
    }.issubset(set(plan.fail_reasons))


def test_signature_headers_body_plan_accumulates_credential_and_raw_artifact_reasons() -> None:
    plan = _plan(
        http_request_skeleton=_unchecked_skeleton(
            credential_access_enabled=True,
            raw_request_created=True,
            raw_response_saved=True,
            signature_saved=True,
            api_secret_used=True,
        ),
        credential_values_exposed=True,
        raw_request_saved=True,
        raw_response_saved=True,
        headers_saved=True,
        signature_saved=True,
        api_key_value_exposed=True,
        api_secret_value_exposed=True,
    )

    assert plan.plan_passed is False
    assert {
        "http_request_skeleton:credential_access_enabled",
        "http_request_skeleton:raw_request_created",
        "http_request_skeleton:raw_response_saved",
        "http_request_skeleton:signature_saved",
        "http_request_skeleton:api_secret_used",
        "credential_values_exposed",
        "raw_request_saved",
        "raw_response_saved",
        "headers_saved",
        "signature_saved",
        "api_key_value_exposed",
        "api_secret_value_exposed",
    }.issubset(set(plan.fail_reasons))


@pytest.mark.parametrize(
    "overrides,expected_reason",
    [
        ({"order_client_plan_id": ""}, "order_client_plan_id_missing"),
        ({"mocked_payload_candidate_id": ""}, "mocked_payload_candidate_id_missing"),
        (
            {"http_request_client_skeleton_id": "wrong_skeleton_id"},
            "http_request_client_skeleton_id_mismatch",
        ),
    ],
)
def test_signature_headers_body_plan_fails_closed_for_missing_or_mismatched_skeleton_ids(
    overrides: dict[str, object],
    expected_reason: str,
) -> None:
    plan = _plan(http_request_skeleton=_unchecked_skeleton(**overrides))

    assert plan.plan_passed is False
    assert expected_reason in plan.fail_reasons


@pytest.mark.parametrize(
    "flag_name",
    [
        "body_plan_created",
        "headers_plan_created",
        "signature_plan_created",
        "actual_body_created",
        "actual_headers_created",
        "actual_signature_created",
        "http_post_enabled",
        "credential_values_exposed",
        "raw_request_saved",
        "raw_response_saved",
        "headers_saved",
        "signature_saved",
        "api_key_value_exposed",
        "api_secret_value_exposed",
        "hmac_used",
        "real_order_attempted",
    ],
)
def test_signature_headers_body_plan_rejects_non_bool_safety_flags(
    flag_name: str,
) -> None:
    with pytest.raises(LiveVerificationSignatureHeadersBodyPlanError):
        SignatureHeadersBodyPlan(**asdict(_plan(**{flag_name: "false"})))


@pytest.mark.parametrize(
    "overrides",
    [
        {"plan_passed": True, "fail_reasons": ("unsafe",)},
        {"plan_passed": False, "fail_reasons": ()},
        {"actual_body_created": True, "plan_passed": True},
        {"actual_headers_created": True, "plan_passed": True},
        {"actual_signature_created": True, "plan_passed": True},
        {"plan_mode": "actual_signature_headers_body", "plan_passed": True},
    ],
)
def test_signature_headers_body_plan_rejects_inconsistent_result_state(
    overrides: dict[str, object],
) -> None:
    values = asdict(_plan())
    values.update(overrides)

    with pytest.raises(LiveVerificationSignatureHeadersBodyPlanError):
        SignatureHeadersBodyPlan(**values)
