"""Disabled order submission skeleton with no network side effects."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.live_verification.actual_headers_signature import ActualHeadersSignatureBundle
from app.live_verification.errors import LiveVerificationOrderSubmissionSkeletonError

ORDER_SUBMISSION_ALLOWED_ENDPOINT_PATH = "/private/v1/order"
ORDER_SUBMISSION_ALLOWED_HTTP_METHOD = "POST"
ORDER_SUBMISSION_SKELETON_MODE = "disabled_order_submission_skeleton"
MOCK_ORDER_SUBMISSION_SKELETON_MODE = "mock_order_submission_skeleton_no_network"
ALLOWED_MAX_DAILY_ATTEMPTS = frozenset({1, 2})


@dataclass(frozen=True)
class OrderSubmissionSafetyContext:
    manual_approval_confirmed: bool
    open_positions_count: int
    active_orders_count: int
    previous_result_known: bool
    result_unknown: bool
    session_attempt_count: int
    daily_attempt_count: int
    max_daily_attempts: int
    retry_enabled: bool
    loop_enabled: bool

    def __post_init__(self) -> None:
        _validate_safety_context_types(self)


@dataclass(frozen=True)
class OrderSubmissionSafetyDecision:
    safety_decision_id: str
    manual_approval_confirmed: bool
    open_positions_count: int
    active_orders_count: int
    previous_result_known: bool
    result_unknown: bool
    session_attempt_count: int
    daily_attempt_count: int
    max_daily_attempts: int
    retry_enabled: bool
    loop_enabled: bool
    safety_passed: bool
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_safety_decision(self)


@dataclass(frozen=True)
class DisabledOrderSubmissionSkeletonResult:
    submission_skeleton_id: str
    safety_decision_id: str
    bundle_id: str
    actual_order_body_id: str
    verification_run_id: str
    submission_mode: str
    endpoint_path: str
    http_method: str
    endpoint_allowlisted: bool
    manual_approval_confirmed: bool
    safety_passed: bool
    network_enabled: bool
    http_client_enabled: bool
    http_post_enabled: bool
    mock_transport_only: bool
    retry_enabled: bool
    loop_enabled: bool
    result_unknown: bool
    real_order_attempted: bool
    raw_request_saved: bool
    raw_response_saved: bool
    raw_headers_saved: bool
    raw_signature_saved: bool
    credential_values_logged: bool
    skeleton_passed: bool
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_submission_skeleton_result(self)


@dataclass(frozen=True)
class MockOrderSubmissionSkeletonResult:
    mock_submission_result_id: str
    submission_skeleton_id: str
    bundle_id: str
    actual_order_body_id: str
    verification_run_id: str
    transport_mode: str
    network_enabled: bool
    http_client_enabled: bool
    http_post_enabled: bool
    real_order_attempted: bool
    result_unknown: bool
    raw_request_saved: bool
    raw_response_saved: bool
    credential_values_logged: bool
    skeleton_passed: bool
    mock_transport_passed: bool
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_mock_submission_result(self)


def evaluate_order_submission_safety(
    context: OrderSubmissionSafetyContext,
) -> OrderSubmissionSafetyDecision:
    """Evaluate human and account-state gates before any future order attempt."""
    _ensure_safety_context_type(context)
    fail_reasons = _submission_safety_fail_reasons(context)
    return OrderSubmissionSafetyDecision(
        safety_decision_id=make_order_submission_safety_decision_id(context),
        manual_approval_confirmed=context.manual_approval_confirmed,
        open_positions_count=context.open_positions_count,
        active_orders_count=context.active_orders_count,
        previous_result_known=context.previous_result_known,
        result_unknown=context.result_unknown,
        session_attempt_count=context.session_attempt_count,
        daily_attempt_count=context.daily_attempt_count,
        max_daily_attempts=context.max_daily_attempts,
        retry_enabled=context.retry_enabled,
        loop_enabled=context.loop_enabled,
        safety_passed=not fail_reasons,
        fail_reasons=tuple(fail_reasons),
    )


def build_disabled_order_submission_skeleton(
    *,
    signed_bundle: ActualHeadersSignatureBundle,
    safety_context: OrderSubmissionSafetyContext,
    endpoint_path: str = ORDER_SUBMISSION_ALLOWED_ENDPOINT_PATH,
    http_method: str = ORDER_SUBMISSION_ALLOWED_HTTP_METHOD,
    network_enabled: bool = False,
    http_client_enabled: bool = False,
    http_post_enabled: bool = False,
    mock_transport_only: bool = True,
    retry_enabled: bool = False,
    loop_enabled: bool = False,
    result_unknown: bool = False,
    real_order_attempted: bool = False,
    raw_request_saved: bool = False,
    raw_response_saved: bool = False,
    raw_headers_saved: bool = False,
    raw_signature_saved: bool = False,
    credential_values_logged: bool = False,
) -> DisabledOrderSubmissionSkeletonResult:
    """Build a local-only order submission boundary without sending anything."""
    _ensure_bundle_type(signed_bundle)
    _ensure_safety_context_type(safety_context)
    _validate_bool_map({
        "network_enabled": network_enabled,
        "http_client_enabled": http_client_enabled,
        "http_post_enabled": http_post_enabled,
        "mock_transport_only": mock_transport_only,
        "retry_enabled": retry_enabled,
        "loop_enabled": loop_enabled,
        "result_unknown": result_unknown,
        "real_order_attempted": real_order_attempted,
        "raw_request_saved": raw_request_saved,
        "raw_response_saved": raw_response_saved,
        "raw_headers_saved": raw_headers_saved,
        "raw_signature_saved": raw_signature_saved,
        "credential_values_logged": credential_values_logged,
    })
    safety_decision = evaluate_order_submission_safety(safety_context)
    endpoint_allowlisted = (
        endpoint_path == ORDER_SUBMISSION_ALLOWED_ENDPOINT_PATH
        and http_method == ORDER_SUBMISSION_ALLOWED_HTTP_METHOD
    )
    fail_reasons = _dedupe_reasons((
        *_signed_bundle_fail_reasons(signed_bundle),
        *safety_decision.fail_reasons,
        *_submission_skeleton_flag_fail_reasons(
            endpoint_path=endpoint_path,
            http_method=http_method,
            endpoint_allowlisted=endpoint_allowlisted,
            network_enabled=network_enabled,
            http_client_enabled=http_client_enabled,
            http_post_enabled=http_post_enabled,
            mock_transport_only=mock_transport_only,
            retry_enabled=retry_enabled,
            loop_enabled=loop_enabled,
            result_unknown=result_unknown,
            real_order_attempted=real_order_attempted,
            raw_request_saved=raw_request_saved,
            raw_response_saved=raw_response_saved,
            raw_headers_saved=raw_headers_saved,
            raw_signature_saved=raw_signature_saved,
            credential_values_logged=credential_values_logged,
        ),
    ))
    return DisabledOrderSubmissionSkeletonResult(
        submission_skeleton_id=make_disabled_order_submission_skeleton_id(
            bundle_id=signed_bundle.bundle_id,
            actual_order_body_id=signed_bundle.actual_order_body_id,
            verification_run_id=signed_bundle.verification_run_id,
            safety_decision_id=safety_decision.safety_decision_id,
            endpoint_path=endpoint_path,
            http_method=http_method,
        ),
        safety_decision_id=safety_decision.safety_decision_id,
        bundle_id=signed_bundle.bundle_id,
        actual_order_body_id=signed_bundle.actual_order_body_id,
        verification_run_id=signed_bundle.verification_run_id,
        submission_mode=ORDER_SUBMISSION_SKELETON_MODE,
        endpoint_path=endpoint_path,
        http_method=http_method,
        endpoint_allowlisted=endpoint_allowlisted,
        manual_approval_confirmed=safety_context.manual_approval_confirmed,
        safety_passed=safety_decision.safety_passed,
        network_enabled=network_enabled,
        http_client_enabled=http_client_enabled,
        http_post_enabled=http_post_enabled,
        mock_transport_only=mock_transport_only,
        retry_enabled=retry_enabled or safety_context.retry_enabled,
        loop_enabled=loop_enabled or safety_context.loop_enabled,
        result_unknown=result_unknown or safety_context.result_unknown,
        real_order_attempted=real_order_attempted,
        raw_request_saved=raw_request_saved,
        raw_response_saved=raw_response_saved,
        raw_headers_saved=raw_headers_saved,
        raw_signature_saved=raw_signature_saved,
        credential_values_logged=credential_values_logged,
        skeleton_passed=not fail_reasons,
        fail_reasons=fail_reasons,
    )


def run_mock_order_submission_skeleton(
    *,
    submission_skeleton: DisabledOrderSubmissionSkeletonResult,
    transport_mode: str = MOCK_ORDER_SUBMISSION_SKELETON_MODE,
    network_enabled: bool = False,
    http_client_enabled: bool = False,
    http_post_enabled: bool = False,
    real_order_attempted: bool = False,
    result_unknown: bool = False,
    raw_request_saved: bool = False,
    raw_response_saved: bool = False,
    credential_values_logged: bool = False,
) -> MockOrderSubmissionSkeletonResult:
    """Verify the submission skeleton with a mock-only no-network transport."""
    _ensure_submission_skeleton_type(submission_skeleton)
    _validate_bool_map({
        "network_enabled": network_enabled,
        "http_client_enabled": http_client_enabled,
        "http_post_enabled": http_post_enabled,
        "real_order_attempted": real_order_attempted,
        "result_unknown": result_unknown,
        "raw_request_saved": raw_request_saved,
        "raw_response_saved": raw_response_saved,
        "credential_values_logged": credential_values_logged,
    })
    fail_reasons = _dedupe_reasons((
        *_submission_result_fail_reasons(submission_skeleton),
        *_mock_submission_transport_fail_reasons(
            transport_mode=transport_mode,
            network_enabled=network_enabled,
            http_client_enabled=http_client_enabled,
            http_post_enabled=http_post_enabled,
            real_order_attempted=real_order_attempted,
            result_unknown=result_unknown,
            raw_request_saved=raw_request_saved,
            raw_response_saved=raw_response_saved,
            credential_values_logged=credential_values_logged,
        ),
    ))
    return MockOrderSubmissionSkeletonResult(
        mock_submission_result_id=make_mock_order_submission_skeleton_result_id(
            submission_skeleton_id=submission_skeleton.submission_skeleton_id,
            bundle_id=submission_skeleton.bundle_id,
            verification_run_id=submission_skeleton.verification_run_id,
        ),
        submission_skeleton_id=submission_skeleton.submission_skeleton_id,
        bundle_id=submission_skeleton.bundle_id,
        actual_order_body_id=submission_skeleton.actual_order_body_id,
        verification_run_id=submission_skeleton.verification_run_id,
        transport_mode=transport_mode,
        network_enabled=network_enabled,
        http_client_enabled=http_client_enabled,
        http_post_enabled=http_post_enabled,
        real_order_attempted=real_order_attempted,
        result_unknown=result_unknown,
        raw_request_saved=raw_request_saved,
        raw_response_saved=raw_response_saved,
        credential_values_logged=credential_values_logged,
        skeleton_passed=submission_skeleton.skeleton_passed,
        mock_transport_passed=not fail_reasons,
        fail_reasons=fail_reasons,
    )


def make_order_submission_safety_decision_id(
    context: OrderSubmissionSafetyContext,
) -> str:
    _ensure_safety_context_type(context)
    digest = _short_hash({
        "active_orders_count": context.active_orders_count,
        "daily_attempt_count": context.daily_attempt_count,
        "loop_enabled": context.loop_enabled,
        "manual_approval_confirmed": context.manual_approval_confirmed,
        "max_daily_attempts": context.max_daily_attempts,
        "open_positions_count": context.open_positions_count,
        "previous_result_known": context.previous_result_known,
        "result_unknown": context.result_unknown,
        "retry_enabled": context.retry_enabled,
        "session_attempt_count": context.session_attempt_count,
    })
    return f"order_submission_safety_{digest}"


def make_disabled_order_submission_skeleton_id(
    *,
    bundle_id: str,
    actual_order_body_id: str,
    verification_run_id: str,
    safety_decision_id: str,
    endpoint_path: str,
    http_method: str,
) -> str:
    _require_non_empty("bundle_id", bundle_id)
    _require_non_empty("actual_order_body_id", actual_order_body_id)
    _require_non_empty("verification_run_id", verification_run_id)
    _require_non_empty("safety_decision_id", safety_decision_id)
    _require_non_empty("endpoint_path", endpoint_path)
    _require_non_empty("http_method", http_method)
    digest = _short_hash({
        "actual_order_body_id": actual_order_body_id,
        "bundle_id": bundle_id,
        "endpoint_path": endpoint_path,
        "http_method": http_method,
        "safety_decision_id": safety_decision_id,
        "verification_run_id": verification_run_id,
    })
    return f"disabled_order_submission_{verification_run_id}_{digest}"


def make_mock_order_submission_skeleton_result_id(
    *,
    submission_skeleton_id: str,
    bundle_id: str,
    verification_run_id: str,
) -> str:
    _require_non_empty("submission_skeleton_id", submission_skeleton_id)
    _require_non_empty("bundle_id", bundle_id)
    _require_non_empty("verification_run_id", verification_run_id)
    digest = _short_hash({
        "bundle_id": bundle_id,
        "submission_skeleton_id": submission_skeleton_id,
        "verification_run_id": verification_run_id,
    })
    return f"mock_order_submission_{verification_run_id}_{digest}"


def _submission_safety_fail_reasons(
    context: OrderSubmissionSafetyContext,
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    if not context.manual_approval_confirmed:
        fail_reasons.append("manual_approval_required")
    if context.open_positions_count > 0:
        fail_reasons.append("open_positions_present")
    if context.active_orders_count > 0:
        fail_reasons.append("active_orders_present")
    if not context.previous_result_known:
        fail_reasons.append("previous_result_unknown")
    if context.result_unknown:
        fail_reasons.append("result_unknown")
    if context.session_attempt_count > 0:
        fail_reasons.append("session_attempt_already_used")
    if context.max_daily_attempts not in ALLOWED_MAX_DAILY_ATTEMPTS:
        fail_reasons.append("max_daily_attempts")
    if context.daily_attempt_count >= context.max_daily_attempts:
        fail_reasons.append("daily_attempt_limit_reached")
    if context.retry_enabled:
        fail_reasons.append("retry_enabled")
    if context.loop_enabled:
        fail_reasons.append("loop_enabled")
    return tuple(fail_reasons)


def _signed_bundle_fail_reasons(
    bundle: ActualHeadersSignatureBundle,
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    for field_name, value in (
        ("bundle_id", bundle.bundle_id),
        ("actual_order_body_id", bundle.actual_order_body_id),
        ("verification_run_id", bundle.verification_run_id),
    ):
        if not _has_text(value):
            fail_reasons.append(f"bundle:{field_name}_missing")
    if not bundle.bundle_passed:
        fail_reasons.append("bundle:not_passed")
    if bundle.fail_reasons:
        fail_reasons.append("bundle:fail_reasons")
    for name, value in {
        "headers_created": bundle.headers_created,
        "signature_created": bundle.signature_created,
        "hmac_used": bundle.hmac_used,
    }.items():
        if not _is_bool(value) or not value:
            fail_reasons.append(f"bundle:{name}")
    for name, value in {
        "http_post_enabled": bundle.http_post_enabled,
        "raw_headers_saved": bundle.raw_headers_saved,
        "raw_signature_saved": bundle.raw_signature_saved,
        "raw_request_saved": bundle.raw_request_saved,
        "raw_response_saved": bundle.raw_response_saved,
        "credential_values_logged": bundle.credential_values_logged,
        "api_key_value_exposed": bundle.api_key_value_exposed,
        "api_secret_value_exposed": bundle.api_secret_value_exposed,
        "signature_value_exposed": bundle.signature_value_exposed,
    }.items():
        if not _is_bool(value) or value:
            fail_reasons.append(f"bundle:{name}")
    return tuple(fail_reasons)


def _submission_skeleton_flag_fail_reasons(
    *,
    endpoint_path: str,
    http_method: str,
    endpoint_allowlisted: bool,
    network_enabled: bool,
    http_client_enabled: bool,
    http_post_enabled: bool,
    mock_transport_only: bool,
    retry_enabled: bool,
    loop_enabled: bool,
    result_unknown: bool,
    real_order_attempted: bool,
    raw_request_saved: bool,
    raw_response_saved: bool,
    raw_headers_saved: bool,
    raw_signature_saved: bool,
    credential_values_logged: bool,
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    if endpoint_path != ORDER_SUBMISSION_ALLOWED_ENDPOINT_PATH:
        fail_reasons.append("endpoint_path")
    if http_method != ORDER_SUBMISSION_ALLOWED_HTTP_METHOD:
        fail_reasons.append("http_method")
    if not endpoint_allowlisted:
        fail_reasons.append("endpoint_allowlisted")
    if not mock_transport_only:
        fail_reasons.append("mock_transport_only")
    for name, value in {
        "network_enabled": network_enabled,
        "http_client_enabled": http_client_enabled,
        "http_post_enabled": http_post_enabled,
        "retry_enabled": retry_enabled,
        "loop_enabled": loop_enabled,
        "result_unknown": result_unknown,
        "real_order_attempted": real_order_attempted,
        "raw_request_saved": raw_request_saved,
        "raw_response_saved": raw_response_saved,
        "raw_headers_saved": raw_headers_saved,
        "raw_signature_saved": raw_signature_saved,
        "credential_values_logged": credential_values_logged,
    }.items():
        if value:
            fail_reasons.append(name)
    return tuple(fail_reasons)


def _submission_result_fail_reasons(
    result: DisabledOrderSubmissionSkeletonResult,
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    for field_name, value in (
        ("submission_skeleton_id", result.submission_skeleton_id),
        ("bundle_id", result.bundle_id),
        ("actual_order_body_id", result.actual_order_body_id),
        ("verification_run_id", result.verification_run_id),
    ):
        if not _has_text(value):
            fail_reasons.append(f"skeleton:{field_name}_missing")
    if not result.skeleton_passed:
        fail_reasons.append("skeleton:not_passed")
    if result.fail_reasons:
        fail_reasons.append("skeleton:fail_reasons")
    if result.submission_mode != ORDER_SUBMISSION_SKELETON_MODE:
        fail_reasons.append("skeleton:submission_mode")
    if result.endpoint_path != ORDER_SUBMISSION_ALLOWED_ENDPOINT_PATH:
        fail_reasons.append("skeleton:endpoint_path")
    if result.http_method != ORDER_SUBMISSION_ALLOWED_HTTP_METHOD:
        fail_reasons.append("skeleton:http_method")
    if not result.endpoint_allowlisted:
        fail_reasons.append("skeleton:endpoint_allowlisted")
    if not result.safety_passed:
        fail_reasons.append("skeleton:safety_passed")
    if not result.mock_transport_only:
        fail_reasons.append("skeleton:mock_transport_only")
    for name, value in {
        "network_enabled": result.network_enabled,
        "http_client_enabled": result.http_client_enabled,
        "http_post_enabled": result.http_post_enabled,
        "retry_enabled": result.retry_enabled,
        "loop_enabled": result.loop_enabled,
        "result_unknown": result.result_unknown,
        "real_order_attempted": result.real_order_attempted,
        "raw_request_saved": result.raw_request_saved,
        "raw_response_saved": result.raw_response_saved,
        "raw_headers_saved": result.raw_headers_saved,
        "raw_signature_saved": result.raw_signature_saved,
        "credential_values_logged": result.credential_values_logged,
    }.items():
        if not _is_bool(value) or value:
            fail_reasons.append(f"skeleton:{name}")
    return tuple(fail_reasons)


def _mock_submission_transport_fail_reasons(
    *,
    transport_mode: str,
    network_enabled: bool,
    http_client_enabled: bool,
    http_post_enabled: bool,
    real_order_attempted: bool,
    result_unknown: bool,
    raw_request_saved: bool,
    raw_response_saved: bool,
    credential_values_logged: bool,
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    if transport_mode != MOCK_ORDER_SUBMISSION_SKELETON_MODE:
        fail_reasons.append("transport_mode")
    for name, value in {
        "network_enabled": network_enabled,
        "http_client_enabled": http_client_enabled,
        "http_post_enabled": http_post_enabled,
        "real_order_attempted": real_order_attempted,
        "result_unknown": result_unknown,
        "raw_request_saved": raw_request_saved,
        "raw_response_saved": raw_response_saved,
        "credential_values_logged": credential_values_logged,
    }.items():
        if value:
            fail_reasons.append(name)
    return tuple(fail_reasons)


def _validate_safety_context_types(context: OrderSubmissionSafetyContext) -> None:
    _validate_bool_map({
        "manual_approval_confirmed": context.manual_approval_confirmed,
        "previous_result_known": context.previous_result_known,
        "result_unknown": context.result_unknown,
        "retry_enabled": context.retry_enabled,
        "loop_enabled": context.loop_enabled,
    })
    for name, value in {
        "open_positions_count": context.open_positions_count,
        "active_orders_count": context.active_orders_count,
        "session_attempt_count": context.session_attempt_count,
        "daily_attempt_count": context.daily_attempt_count,
        "max_daily_attempts": context.max_daily_attempts,
    }.items():
        if type(value) is not int:
            raise LiveVerificationOrderSubmissionSkeletonError(f"{name} must be int")
        if value < 0:
            raise LiveVerificationOrderSubmissionSkeletonError(
                f"{name} must be non-negative"
            )


def _validate_safety_decision(decision: OrderSubmissionSafetyDecision) -> None:
    _require_non_empty("safety_decision_id", decision.safety_decision_id)
    _validate_bool_map({
        "manual_approval_confirmed": decision.manual_approval_confirmed,
        "previous_result_known": decision.previous_result_known,
        "result_unknown": decision.result_unknown,
        "retry_enabled": decision.retry_enabled,
        "loop_enabled": decision.loop_enabled,
        "safety_passed": decision.safety_passed,
    })
    if not isinstance(decision.fail_reasons, tuple) or any(
        not isinstance(reason, str) or not reason for reason in decision.fail_reasons
    ):
        raise LiveVerificationOrderSubmissionSkeletonError(
            "fail_reasons must be tuple[str, ...]"
        )
    if decision.safety_passed and decision.fail_reasons:
        raise LiveVerificationOrderSubmissionSkeletonError(
            "passed safety decision cannot contain fail reasons"
        )
    if not decision.safety_passed and not decision.fail_reasons:
        raise LiveVerificationOrderSubmissionSkeletonError(
            "failed safety decision requires fail reasons"
        )


def _validate_submission_skeleton_result(
    result: DisabledOrderSubmissionSkeletonResult,
) -> None:
    for field_name, value in (
        ("submission_skeleton_id", result.submission_skeleton_id),
        ("safety_decision_id", result.safety_decision_id),
        ("bundle_id", result.bundle_id),
        ("actual_order_body_id", result.actual_order_body_id),
        ("verification_run_id", result.verification_run_id),
        ("submission_mode", result.submission_mode),
        ("endpoint_path", result.endpoint_path),
        ("http_method", result.http_method),
    ):
        _require_non_empty(field_name, value)
    _validate_bool_map({
        "endpoint_allowlisted": result.endpoint_allowlisted,
        "manual_approval_confirmed": result.manual_approval_confirmed,
        "safety_passed": result.safety_passed,
        "network_enabled": result.network_enabled,
        "http_client_enabled": result.http_client_enabled,
        "http_post_enabled": result.http_post_enabled,
        "mock_transport_only": result.mock_transport_only,
        "retry_enabled": result.retry_enabled,
        "loop_enabled": result.loop_enabled,
        "result_unknown": result.result_unknown,
        "real_order_attempted": result.real_order_attempted,
        "raw_request_saved": result.raw_request_saved,
        "raw_response_saved": result.raw_response_saved,
        "raw_headers_saved": result.raw_headers_saved,
        "raw_signature_saved": result.raw_signature_saved,
        "credential_values_logged": result.credential_values_logged,
        "skeleton_passed": result.skeleton_passed,
    })
    if not isinstance(result.fail_reasons, tuple) or any(
        not isinstance(reason, str) or not reason for reason in result.fail_reasons
    ):
        raise LiveVerificationOrderSubmissionSkeletonError(
            "fail_reasons must be tuple[str, ...]"
        )
    if result.skeleton_passed and result.fail_reasons:
        raise LiveVerificationOrderSubmissionSkeletonError(
            "passed skeleton cannot contain fail reasons"
        )
    if not result.skeleton_passed and not result.fail_reasons:
        raise LiveVerificationOrderSubmissionSkeletonError(
            "failed skeleton requires fail reasons"
        )
    if result.skeleton_passed:
        if any((
            result.submission_mode != ORDER_SUBMISSION_SKELETON_MODE,
            result.endpoint_path != ORDER_SUBMISSION_ALLOWED_ENDPOINT_PATH,
            result.http_method != ORDER_SUBMISSION_ALLOWED_HTTP_METHOD,
            not result.endpoint_allowlisted,
            not result.manual_approval_confirmed,
            not result.safety_passed,
            result.network_enabled,
            result.http_client_enabled,
            result.http_post_enabled,
            not result.mock_transport_only,
            result.retry_enabled,
            result.loop_enabled,
            result.result_unknown,
            result.real_order_attempted,
            result.raw_request_saved,
            result.raw_response_saved,
            result.raw_headers_saved,
            result.raw_signature_saved,
            result.credential_values_logged,
        )):
            raise LiveVerificationOrderSubmissionSkeletonError(
                "passed skeleton crossed a disabled order boundary"
            )


def _validate_mock_submission_result(result: MockOrderSubmissionSkeletonResult) -> None:
    for field_name, value in (
        ("mock_submission_result_id", result.mock_submission_result_id),
        ("submission_skeleton_id", result.submission_skeleton_id),
        ("bundle_id", result.bundle_id),
        ("actual_order_body_id", result.actual_order_body_id),
        ("verification_run_id", result.verification_run_id),
        ("transport_mode", result.transport_mode),
    ):
        _require_non_empty(field_name, value)
    _validate_bool_map({
        "network_enabled": result.network_enabled,
        "http_client_enabled": result.http_client_enabled,
        "http_post_enabled": result.http_post_enabled,
        "real_order_attempted": result.real_order_attempted,
        "result_unknown": result.result_unknown,
        "raw_request_saved": result.raw_request_saved,
        "raw_response_saved": result.raw_response_saved,
        "credential_values_logged": result.credential_values_logged,
        "skeleton_passed": result.skeleton_passed,
        "mock_transport_passed": result.mock_transport_passed,
    })
    if not isinstance(result.fail_reasons, tuple) or any(
        not isinstance(reason, str) or not reason for reason in result.fail_reasons
    ):
        raise LiveVerificationOrderSubmissionSkeletonError(
            "fail_reasons must be tuple[str, ...]"
        )
    if result.mock_transport_passed and result.fail_reasons:
        raise LiveVerificationOrderSubmissionSkeletonError(
            "passed mock transport cannot contain fail reasons"
        )
    if not result.mock_transport_passed and not result.fail_reasons:
        raise LiveVerificationOrderSubmissionSkeletonError(
            "failed mock transport requires fail reasons"
        )
    if result.mock_transport_passed:
        if any((
            result.transport_mode != MOCK_ORDER_SUBMISSION_SKELETON_MODE,
            result.network_enabled,
            result.http_client_enabled,
            result.http_post_enabled,
            result.real_order_attempted,
            result.result_unknown,
            result.raw_request_saved,
            result.raw_response_saved,
            result.credential_values_logged,
            not result.skeleton_passed,
        )):
            raise LiveVerificationOrderSubmissionSkeletonError(
                "passed mock transport crossed a no-network boundary"
            )


def _ensure_bundle_type(bundle: ActualHeadersSignatureBundle) -> None:
    if not isinstance(bundle, ActualHeadersSignatureBundle):
        raise LiveVerificationOrderSubmissionSkeletonError("signed bundle is required")


def _ensure_safety_context_type(context: OrderSubmissionSafetyContext) -> None:
    if not isinstance(context, OrderSubmissionSafetyContext):
        raise LiveVerificationOrderSubmissionSkeletonError(
            "order submission safety context is required"
        )


def _ensure_submission_skeleton_type(
    result: DisabledOrderSubmissionSkeletonResult,
) -> None:
    if not isinstance(result, DisabledOrderSubmissionSkeletonResult):
        raise LiveVerificationOrderSubmissionSkeletonError(
            "order submission skeleton is required"
        )


def _validate_bool_map(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        if not _is_bool(value):
            raise LiveVerificationOrderSubmissionSkeletonError(f"{name} must be bool")


def _is_bool(value: object) -> bool:
    return type(value) is bool


def _require_non_empty(field_name: str, value: str) -> None:
    if not _has_text(value):
        raise LiveVerificationOrderSubmissionSkeletonError(f"{field_name} is required")


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _dedupe_reasons(reasons: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(reason for reason in reasons if reason))


def _short_hash(data: dict[str, object]) -> str:
    canonical = json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
