from __future__ import annotations

from dataclasses import asdict, fields

import pytest

from app.live_verification.actual_headers_signature import ActualHeadersSignatureBundle
from app.live_verification.errors import LiveVerificationOrderSubmissionSkeletonError
from app.live_verification.order_submission_skeleton import (
    MOCK_ORDER_SUBMISSION_SKELETON_MODE,
    ORDER_SUBMISSION_ALLOWED_ENDPOINT_PATH,
    ORDER_SUBMISSION_ALLOWED_HTTP_METHOD,
    ORDER_SUBMISSION_SKELETON_MODE,
    DisabledOrderSubmissionSkeletonResult,
    MockOrderSubmissionSkeletonResult,
    OrderSubmissionSafetyContext,
    OrderSubmissionSafetyDecision,
    build_disabled_order_submission_skeleton,
    evaluate_order_submission_safety,
    make_disabled_order_submission_skeleton_id,
    make_mock_order_submission_skeleton_result_id,
    make_order_submission_safety_decision_id,
    run_mock_order_submission_skeleton,
)
from app.tests.test_live_verification_actual_headers_signature import (
    DUMMY_API_KEY,
    DUMMY_API_SECRET,
    _bundle,
)

DUMMY_SIGNATURE_VALUE = "dummy_signature_for_unit_test"
EXPECTED_SAFETY_DECISION_FIELDS = {
    "safety_decision_id",
    "manual_approval_confirmed",
    "open_positions_count",
    "active_orders_count",
    "previous_result_known",
    "result_unknown",
    "session_attempt_count",
    "daily_attempt_count",
    "max_daily_attempts",
    "retry_enabled",
    "loop_enabled",
    "safety_passed",
    "fail_reasons",
}
EXPECTED_SKELETON_FIELDS = {
    "submission_skeleton_id",
    "safety_decision_id",
    "bundle_id",
    "actual_order_body_id",
    "verification_run_id",
    "submission_mode",
    "endpoint_path",
    "http_method",
    "endpoint_allowlisted",
    "manual_approval_confirmed",
    "safety_passed",
    "network_enabled",
    "http_client_enabled",
    "http_post_enabled",
    "mock_transport_only",
    "retry_enabled",
    "loop_enabled",
    "result_unknown",
    "real_order_attempted",
    "raw_request_saved",
    "raw_response_saved",
    "raw_headers_saved",
    "raw_signature_saved",
    "credential_values_logged",
    "skeleton_passed",
    "fail_reasons",
}
EXPECTED_MOCK_FIELDS = {
    "mock_submission_result_id",
    "submission_skeleton_id",
    "bundle_id",
    "actual_order_body_id",
    "verification_run_id",
    "transport_mode",
    "network_enabled",
    "http_client_enabled",
    "http_post_enabled",
    "real_order_attempted",
    "result_unknown",
    "raw_request_saved",
    "raw_response_saved",
    "credential_values_logged",
    "skeleton_passed",
    "mock_transport_passed",
    "fail_reasons",
}
BLOCKED_PUBLIC_FIELDS = {
    "api_key",
    "api_secret",
    "secret",
    "token",
    "credential",
    "credentials",
    "authorization",
    "headers",
    "actual_headers",
    "header_values",
    "signature",
    "actual_signature",
    "signature_value",
    "api_sign",
    "hmac_digest",
    "raw_headers",
    "raw_signature",
    "raw_request",
    "raw_response",
    "request_url",
    "url",
    "http_client",
    "response",
    "status_code",
    "response_body",
    "request_body",
    "request_headers",
    "body",
    "payload",
}


def _safety_context(**overrides: object) -> OrderSubmissionSafetyContext:
    values = {
        "manual_approval_confirmed": True,
        "open_positions_count": 0,
        "active_orders_count": 0,
        "previous_result_known": True,
        "result_unknown": False,
        "session_attempt_count": 0,
        "daily_attempt_count": 0,
        "max_daily_attempts": 1,
        "retry_enabled": False,
        "loop_enabled": False,
    }
    values.update(overrides)
    return OrderSubmissionSafetyContext(**values)


def _skeleton(
    *,
    signed_bundle: ActualHeadersSignatureBundle | None = None,
    safety_context: OrderSubmissionSafetyContext | None = None,
    **overrides: object,
) -> DisabledOrderSubmissionSkeletonResult:
    return build_disabled_order_submission_skeleton(
        signed_bundle=signed_bundle or _bundle(),
        safety_context=safety_context or _safety_context(),
        **overrides,
    )


def _unchecked_bundle(**overrides: object) -> ActualHeadersSignatureBundle:
    values = asdict(_bundle())
    values.update(overrides)
    bundle = object.__new__(ActualHeadersSignatureBundle)
    for field_name, value in values.items():
        object.__setattr__(bundle, field_name, value)
    return bundle


def test_order_submission_safety_context_passes_when_all_guards_are_clear() -> None:
    context = _safety_context()

    decision = evaluate_order_submission_safety(context)
    same = evaluate_order_submission_safety(context)

    assert isinstance(decision, OrderSubmissionSafetyDecision)
    assert decision.safety_decision_id == same.safety_decision_id
    assert decision.safety_decision_id == make_order_submission_safety_decision_id(
        context
    )
    assert decision.manual_approval_confirmed is True
    assert decision.open_positions_count == 0
    assert decision.active_orders_count == 0
    assert decision.previous_result_known is True
    assert decision.result_unknown is False
    assert decision.session_attempt_count == 0
    assert decision.daily_attempt_count == 0
    assert decision.max_daily_attempts == 1
    assert decision.retry_enabled is False
    assert decision.loop_enabled is False
    assert decision.safety_passed is True
    assert decision.fail_reasons == ()
    assert set(asdict(decision)) == EXPECTED_SAFETY_DECISION_FIELDS
    assert {field.name for field in fields(OrderSubmissionSafetyDecision)} == (
        EXPECTED_SAFETY_DECISION_FIELDS
    )


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"manual_approval_confirmed": False}, "manual_approval_required"),
        ({"open_positions_count": 1}, "open_positions_present"),
        ({"active_orders_count": 1}, "active_orders_present"),
        ({"previous_result_known": False}, "previous_result_unknown"),
        ({"result_unknown": True}, "result_unknown"),
        ({"session_attempt_count": 1}, "session_attempt_already_used"),
        ({"daily_attempt_count": 1, "max_daily_attempts": 1}, "daily_attempt_limit_reached"),
        ({"max_daily_attempts": 3}, "max_daily_attempts"),
        ({"retry_enabled": True}, "retry_enabled"),
        ({"loop_enabled": True}, "loop_enabled"),
    ],
)
def test_order_submission_safety_context_fails_closed(
    overrides: dict[str, object],
    expected_reason: str,
) -> None:
    decision = evaluate_order_submission_safety(_safety_context(**overrides))

    assert decision.safety_passed is False
    assert expected_reason in decision.fail_reasons


def test_order_submission_safety_keeps_multiple_fail_reasons() -> None:
    decision = evaluate_order_submission_safety(
        _safety_context(
            manual_approval_confirmed=False,
            open_positions_count=1,
            active_orders_count=1,
            previous_result_known=False,
            result_unknown=True,
            session_attempt_count=1,
            daily_attempt_count=1,
            max_daily_attempts=1,
            retry_enabled=True,
            loop_enabled=True,
        )
    )

    assert decision.safety_passed is False
    assert set(decision.fail_reasons) >= {
        "manual_approval_required",
        "open_positions_present",
        "active_orders_present",
        "previous_result_unknown",
        "result_unknown",
        "session_attempt_already_used",
        "daily_attempt_limit_reached",
        "retry_enabled",
        "loop_enabled",
    }


def test_disabled_order_submission_skeleton_accepts_safe_bundle_and_context() -> None:
    bundle = _bundle()
    context = _safety_context()
    decision = evaluate_order_submission_safety(context)

    result = _skeleton(signed_bundle=bundle, safety_context=context)
    same = _skeleton(signed_bundle=bundle, safety_context=context)

    assert isinstance(result, DisabledOrderSubmissionSkeletonResult)
    assert result.submission_skeleton_id == same.submission_skeleton_id
    assert result.submission_skeleton_id == make_disabled_order_submission_skeleton_id(
        bundle_id=bundle.bundle_id,
        actual_order_body_id=bundle.actual_order_body_id,
        verification_run_id=bundle.verification_run_id,
        safety_decision_id=decision.safety_decision_id,
        endpoint_path=ORDER_SUBMISSION_ALLOWED_ENDPOINT_PATH,
        http_method=ORDER_SUBMISSION_ALLOWED_HTTP_METHOD,
    )
    assert result.safety_decision_id == decision.safety_decision_id
    assert result.bundle_id == bundle.bundle_id
    assert result.actual_order_body_id == bundle.actual_order_body_id
    assert result.verification_run_id == bundle.verification_run_id
    assert result.submission_mode == ORDER_SUBMISSION_SKELETON_MODE
    assert result.endpoint_path == ORDER_SUBMISSION_ALLOWED_ENDPOINT_PATH
    assert result.http_method == ORDER_SUBMISSION_ALLOWED_HTTP_METHOD
    assert result.endpoint_allowlisted is True
    assert result.manual_approval_confirmed is True
    assert result.safety_passed is True
    assert result.network_enabled is False
    assert result.http_client_enabled is False
    assert result.http_post_enabled is False
    assert result.mock_transport_only is True
    assert result.retry_enabled is False
    assert result.loop_enabled is False
    assert result.result_unknown is False
    assert result.real_order_attempted is False
    assert result.raw_request_saved is False
    assert result.raw_response_saved is False
    assert result.raw_headers_saved is False
    assert result.raw_signature_saved is False
    assert result.credential_values_logged is False
    assert result.skeleton_passed is True
    assert result.fail_reasons == ()


@pytest.mark.parametrize(
    ("bundle_overrides", "expected_reason"),
    [
        ({"bundle_passed": False}, "bundle:not_passed"),
        ({"fail_reasons": ("unsafe",)}, "bundle:fail_reasons"),
        ({"headers_created": False}, "bundle:headers_created"),
        ({"signature_created": False}, "bundle:signature_created"),
        ({"hmac_used": False}, "bundle:hmac_used"),
        ({"http_post_enabled": True}, "bundle:http_post_enabled"),
        ({"raw_headers_saved": True}, "bundle:raw_headers_saved"),
        ({"raw_signature_saved": True}, "bundle:raw_signature_saved"),
        ({"raw_request_saved": True}, "bundle:raw_request_saved"),
        ({"raw_response_saved": True}, "bundle:raw_response_saved"),
        ({"credential_values_logged": True}, "bundle:credential_values_logged"),
        ({"api_key_value_exposed": True}, "bundle:api_key_value_exposed"),
        ({"api_secret_value_exposed": True}, "bundle:api_secret_value_exposed"),
        ({"signature_value_exposed": True}, "bundle:signature_value_exposed"),
    ],
)
def test_disabled_order_submission_skeleton_fails_for_unsafe_bundle(
    bundle_overrides: dict[str, object],
    expected_reason: str,
) -> None:
    result = _skeleton(signed_bundle=_unchecked_bundle(**bundle_overrides))

    assert result.skeleton_passed is False
    assert expected_reason in result.fail_reasons


@pytest.mark.parametrize(
    ("kwargs", "expected_reason"),
    [
        ({"endpoint_path": "/private/v1/activeOrders"}, "endpoint_path"),
        ({"http_method": "GET"}, "http_method"),
        ({"network_enabled": True}, "network_enabled"),
        ({"http_client_enabled": True}, "http_client_enabled"),
        ({"http_post_enabled": True}, "http_post_enabled"),
        ({"mock_transport_only": False}, "mock_transport_only"),
        ({"retry_enabled": True}, "retry_enabled"),
        ({"loop_enabled": True}, "loop_enabled"),
        ({"result_unknown": True}, "result_unknown"),
        ({"real_order_attempted": True}, "real_order_attempted"),
        ({"raw_request_saved": True}, "raw_request_saved"),
        ({"raw_response_saved": True}, "raw_response_saved"),
        ({"raw_headers_saved": True}, "raw_headers_saved"),
        ({"raw_signature_saved": True}, "raw_signature_saved"),
        ({"credential_values_logged": True}, "credential_values_logged"),
    ],
)
def test_disabled_order_submission_skeleton_fails_for_unsafe_flags(
    kwargs: dict[str, object],
    expected_reason: str,
) -> None:
    result = _skeleton(**kwargs)

    assert result.skeleton_passed is False
    assert expected_reason in result.fail_reasons


def test_disabled_order_submission_skeleton_keeps_multiple_fail_reasons() -> None:
    result = _skeleton(
        safety_context=_safety_context(
            manual_approval_confirmed=False,
            open_positions_count=1,
            active_orders_count=1,
            result_unknown=True,
            retry_enabled=True,
        ),
        network_enabled=True,
        http_client_enabled=True,
        http_post_enabled=True,
        mock_transport_only=False,
        raw_request_saved=True,
        raw_response_saved=True,
        raw_headers_saved=True,
        raw_signature_saved=True,
        credential_values_logged=True,
    )

    assert result.skeleton_passed is False
    assert set(result.fail_reasons) >= {
        "manual_approval_required",
        "open_positions_present",
        "active_orders_present",
        "result_unknown",
        "retry_enabled",
        "network_enabled",
        "http_client_enabled",
        "http_post_enabled",
        "mock_transport_only",
        "raw_request_saved",
        "raw_response_saved",
        "raw_headers_saved",
        "raw_signature_saved",
        "credential_values_logged",
    }


def test_disabled_order_submission_skeleton_does_not_expose_sensitive_values() -> None:
    result = _skeleton()
    public_views = (
        repr(result),
        str(result),
        repr(asdict(result)),
        str(asdict(result)),
    )

    for view in public_views:
        assert DUMMY_API_KEY not in view
        assert DUMMY_API_SECRET not in view
        assert DUMMY_SIGNATURE_VALUE not in view
    assert set(asdict(result)) == EXPECTED_SKELETON_FIELDS
    assert {field.name for field in fields(DisabledOrderSubmissionSkeletonResult)} == (
        EXPECTED_SKELETON_FIELDS
    )
    assert set(asdict(result)).isdisjoint(BLOCKED_PUBLIC_FIELDS)
    assert all(not hasattr(result, field_name) for field_name in BLOCKED_PUBLIC_FIELDS)


def test_mock_order_submission_skeleton_accepts_passed_skeleton_without_network() -> None:
    skeleton = _skeleton()

    result = run_mock_order_submission_skeleton(submission_skeleton=skeleton)
    same = run_mock_order_submission_skeleton(submission_skeleton=skeleton)

    assert isinstance(result, MockOrderSubmissionSkeletonResult)
    assert result.mock_submission_result_id == same.mock_submission_result_id
    assert result.mock_submission_result_id == make_mock_order_submission_skeleton_result_id(
        submission_skeleton_id=skeleton.submission_skeleton_id,
        bundle_id=skeleton.bundle_id,
        verification_run_id=skeleton.verification_run_id,
    )
    assert result.submission_skeleton_id == skeleton.submission_skeleton_id
    assert result.bundle_id == skeleton.bundle_id
    assert result.actual_order_body_id == skeleton.actual_order_body_id
    assert result.verification_run_id == skeleton.verification_run_id
    assert result.transport_mode == MOCK_ORDER_SUBMISSION_SKELETON_MODE
    assert result.network_enabled is False
    assert result.http_client_enabled is False
    assert result.http_post_enabled is False
    assert result.real_order_attempted is False
    assert result.result_unknown is False
    assert result.raw_request_saved is False
    assert result.raw_response_saved is False
    assert result.credential_values_logged is False
    assert result.skeleton_passed is True
    assert result.mock_transport_passed is True
    assert result.fail_reasons == ()


@pytest.mark.parametrize(
    ("kwargs", "expected_reason"),
    [
        ({"transport_mode": "network_transport"}, "transport_mode"),
        ({"network_enabled": True}, "network_enabled"),
        ({"http_client_enabled": True}, "http_client_enabled"),
        ({"http_post_enabled": True}, "http_post_enabled"),
        ({"real_order_attempted": True}, "real_order_attempted"),
        ({"result_unknown": True}, "result_unknown"),
        ({"raw_request_saved": True}, "raw_request_saved"),
        ({"raw_response_saved": True}, "raw_response_saved"),
        ({"credential_values_logged": True}, "credential_values_logged"),
    ],
)
def test_mock_order_submission_skeleton_fails_for_unsafe_flags(
    kwargs: dict[str, object],
    expected_reason: str,
) -> None:
    result = run_mock_order_submission_skeleton(
        submission_skeleton=_skeleton(),
        **kwargs,
    )

    assert result.mock_transport_passed is False
    assert expected_reason in result.fail_reasons


def test_mock_order_submission_skeleton_fails_for_failed_skeleton() -> None:
    skeleton = _skeleton(network_enabled=True, http_post_enabled=True)

    result = run_mock_order_submission_skeleton(submission_skeleton=skeleton)

    assert result.mock_transport_passed is False
    assert result.skeleton_passed is False
    assert "skeleton:not_passed" in result.fail_reasons
    assert "skeleton:fail_reasons" in result.fail_reasons


def test_mock_order_submission_skeleton_does_not_expose_sensitive_values() -> None:
    result = run_mock_order_submission_skeleton(submission_skeleton=_skeleton())
    public_views = (
        repr(result),
        str(result),
        repr(asdict(result)),
        str(asdict(result)),
    )

    for view in public_views:
        assert DUMMY_API_KEY not in view
        assert DUMMY_API_SECRET not in view
        assert DUMMY_SIGNATURE_VALUE not in view
    assert set(asdict(result)) == EXPECTED_MOCK_FIELDS
    assert {field.name for field in fields(MockOrderSubmissionSkeletonResult)} == (
        EXPECTED_MOCK_FIELDS
    )
    assert set(asdict(result)).isdisjoint(BLOCKED_PUBLIC_FIELDS)
    assert all(not hasattr(result, field_name) for field_name in BLOCKED_PUBLIC_FIELDS)


def test_order_submission_skeleton_rejects_wrong_input_types() -> None:
    with pytest.raises(LiveVerificationOrderSubmissionSkeletonError):
        evaluate_order_submission_safety(object())  # type: ignore[arg-type]
    with pytest.raises(LiveVerificationOrderSubmissionSkeletonError):
        build_disabled_order_submission_skeleton(
            signed_bundle=object(),  # type: ignore[arg-type]
            safety_context=_safety_context(),
        )
    with pytest.raises(LiveVerificationOrderSubmissionSkeletonError):
        run_mock_order_submission_skeleton(
            submission_skeleton=object(),  # type: ignore[arg-type]
        )
