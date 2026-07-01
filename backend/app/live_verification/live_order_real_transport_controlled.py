"""Step 6G controlled transport boundary.

This module converts a safe signing/headers result into transport readiness
labels, safe statuses, and booleans only. It does not create raw requests,
receive raw responses, import HTTP clients, call APIs, execute HTTP POST, call
order endpoints, or call live_order_once.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_signing_headers_controlled import (
    SAFE_HEADERS_LABEL,
    SAFE_SIGNING_LABEL,
    LiveOrderRealSigningHeadersControlledResult,
    LiveOrderRealSigningHeadersControlledStatus,
)

TRANSPORT_CONTROLLED_RECOMMENDED_NEXT_STEP = (
    "transport_controlled_boundary_review_no_api_no_post"
)
SAFE_TRANSPORT_LABEL = "CONTROLLED_TRANSPORT_BOUNDARY"
UNSUPPORTED_TRANSPORT_CONTROLLED_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealTransportControlledStatus(str, Enum):
    TRANSPORT_NOT_READY = "TRANSPORT_NOT_READY"
    TRANSPORT_READY_NO_API_NO_POST = "TRANSPORT_READY_NO_API_NO_POST"
    TRANSPORT_BLOCKED_MISSING_SIGNING_HEADERS = (
        "TRANSPORT_BLOCKED_MISSING_SIGNING_HEADERS"
    )
    TRANSPORT_BLOCKED_UNKNOWN = "TRANSPORT_BLOCKED_UNKNOWN"
    TRANSPORT_BLOCKED_FAILED = "TRANSPORT_BLOCKED_FAILED"
    TRANSPORT_BLOCKED_UNAVAILABLE = "TRANSPORT_BLOCKED_UNAVAILABLE"
    TRANSPORT_BLOCKED_TIMEOUT = "TRANSPORT_BLOCKED_TIMEOUT"
    TRANSPORT_BLOCKED_UNSAFE_EXPOSURE = "TRANSPORT_BLOCKED_UNSAFE_EXPOSURE"
    TRANSPORT_BLOCKED_CREDENTIAL_VALUE_EXPOSURE = (
        "TRANSPORT_BLOCKED_CREDENTIAL_VALUE_EXPOSURE"
    )
    TRANSPORT_BLOCKED_SIGNATURE_VALUE_EXPOSURE = (
        "TRANSPORT_BLOCKED_SIGNATURE_VALUE_EXPOSURE"
    )
    TRANSPORT_BLOCKED_HEADERS_VALUE_EXPOSURE = (
        "TRANSPORT_BLOCKED_HEADERS_VALUE_EXPOSURE"
    )
    TRANSPORT_BLOCKED_RAW_REQUEST_EXPOSURE = (
        "TRANSPORT_BLOCKED_RAW_REQUEST_EXPOSURE"
    )
    TRANSPORT_BLOCKED_RAW_RESPONSE_EXPOSURE = (
        "TRANSPORT_BLOCKED_RAW_RESPONSE_EXPOSURE"
    )
    TRANSPORT_BLOCKED_API_ATTEMPTED = "TRANSPORT_BLOCKED_API_ATTEMPTED"
    TRANSPORT_BLOCKED_POST_ATTEMPTED = "TRANSPORT_BLOCKED_POST_ATTEMPTED"
    TRANSPORT_BLOCKED_ORDER_ENDPOINT = "TRANSPORT_BLOCKED_ORDER_ENDPOINT"
    TRANSPORT_BLOCKED_LIVE_ORDER_ONCE = "TRANSPORT_BLOCKED_LIVE_ORDER_ONCE"
    TRANSPORT_BLOCKED_PREFLIGHT_OR_CONFIRMATION = (
        "TRANSPORT_BLOCKED_PREFLIGHT_OR_CONFIRMATION"
    )


class LiveOrderRealTransportControlledMode(str, Enum):
    TRANSPORT_CONTROLLED_IMPLEMENTATION_ONLY = (
        "TRANSPORT_CONTROLLED_IMPLEMENTATION_ONLY"
    )


TransportControlledStatus = LiveOrderRealTransportControlledStatus
TransportControlledMode = LiveOrderRealTransportControlledMode


@dataclass(frozen=True)
class LiveOrderRealTransportControlledInput:
    transport_mode: str = (
        TransportControlledMode.TRANSPORT_CONTROLLED_IMPLEMENTATION_ONLY.value
    )
    transport_declared: bool = True
    transport_requested: bool = True
    signing_headers_prerequisite_checked: bool = True
    signing_headers_controlled_ready: bool = True
    signing_controlled_ready: bool = True
    headers_controlled_ready: bool = True
    signing_headers_prerequisite_satisfied: bool = True
    safe_signing_label: str = SAFE_SIGNING_LABEL
    safe_headers_label: str = SAFE_HEADERS_LABEL
    safe_signing_status: str = (
        LiveOrderRealSigningHeadersControlledStatus
        .SIGNING_HEADERS_READY_NO_TRANSPORT
        .value
    )
    safe_headers_status: str = (
        LiveOrderRealSigningHeadersControlledStatus
        .SIGNING_HEADERS_READY_NO_TRANSPORT
        .value
    )
    safe_transport_label: str = SAFE_TRANSPORT_LABEL
    transport_unknown: bool = False
    transport_failed: bool = False
    transport_unavailable: bool = False
    transport_timeout: bool = False
    unsafe_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    raw_request_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    request_body_exposure_attempted: bool = False
    response_body_exposure_attempted: bool = False
    endpoint_actual_value_exposure_attempted: bool = False
    account_id_exposure_attempted: bool = False
    order_id_exposure_attempted: bool = False
    real_id_exposure_attempted: bool = False
    broker_api_response_exposure_attempted: bool = False
    api_call_allowed: bool = False
    api_call_attempted: bool = False
    http_client_present: bool = False
    real_transport_attempted: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    actual_checker_execution_performed: bool = False
    actual_result_receipt_received: bool = False
    actual_receipt_handoff_executed: bool = False
    fresh_preflight_executed: bool = False
    final_confirmation_received: bool = False
    one_post_max_required: bool = True
    no_retry_required: bool = True
    fresh_preflight_required: bool = True
    final_confirmation_required: bool = True
    sanitized_result_required: bool = True
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("transport_mode", self.transport_mode)
        _require_non_empty("safe_signing_label", self.safe_signing_label)
        _require_non_empty("safe_headers_label", self.safe_headers_label)
        _require_non_empty("safe_signing_status", self.safe_signing_status)
        _require_non_empty("safe_headers_status", self.safe_headers_status)
        _require_non_empty("safe_transport_label", self.safe_transport_label)
        _validate_bool_fields(
            self,
            (
                "transport_declared",
                "transport_requested",
                "signing_headers_prerequisite_checked",
                "signing_headers_controlled_ready",
                "signing_controlled_ready",
                "headers_controlled_ready",
                "signing_headers_prerequisite_satisfied",
                "transport_unknown",
                "transport_failed",
                "transport_unavailable",
                "transport_timeout",
                "unsafe_exposure_attempted",
                "credential_value_exposure_attempted",
                "signature_value_exposure_attempted",
                "headers_value_exposure_attempted",
                "raw_request_exposure_attempted",
                "raw_response_exposure_attempted",
                "request_body_exposure_attempted",
                "response_body_exposure_attempted",
                "endpoint_actual_value_exposure_attempted",
                "account_id_exposure_attempted",
                "order_id_exposure_attempted",
                "real_id_exposure_attempted",
                "broker_api_response_exposure_attempted",
                "api_call_allowed",
                "api_call_attempted",
                "http_client_present",
                "real_transport_attempted",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "actual_checker_execution_performed",
                "actual_result_receipt_received",
                "actual_receipt_handoff_executed",
                "fresh_preflight_executed",
                "final_confirmation_received",
                "one_post_max_required",
                "no_retry_required",
                "fresh_preflight_required",
                "final_confirmation_required",
                "sanitized_result_required",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealTransportControlledCheckResult:
    name: str
    passed: bool
    sanitized_value: str
    expected: str

    def __post_init__(self) -> None:
        _require_non_empty("name", self.name)
        if type(self.passed) is not bool:
            raise LiveVerificationValidationError("passed must be bool")
        _require_non_empty("sanitized_value", self.sanitized_value)
        _require_non_empty("expected", self.expected)


@dataclass(frozen=True)
class LiveOrderRealTransportControlledResult:
    status: LiveOrderRealTransportControlledStatus
    transport_controlled_ready: bool
    transport_mode: str
    transport_declared: bool
    transport_requested: bool
    signing_headers_prerequisite_checked: bool
    signing_headers_prerequisite_satisfied: bool
    signing_headers_controlled_ready: bool
    signing_controlled_ready: bool
    headers_controlled_ready: bool
    safe_signing_label: str
    safe_headers_label: str
    safe_signing_status: str
    safe_headers_status: str
    safe_transport_label: str
    safe_transport_status: str
    transport_unknown: bool
    transport_failed: bool
    transport_unavailable: bool
    transport_timeout: bool
    unsafe_exposure_attempted: bool
    credential_value_exposure_attempted: bool
    signature_value_exposure_attempted: bool
    headers_value_exposure_attempted: bool
    raw_request_exposure_attempted: bool
    raw_response_exposure_attempted: bool
    request_body_exposure_attempted: bool
    response_body_exposure_attempted: bool
    endpoint_actual_value_exposure_attempted: bool
    account_id_exposure_attempted: bool
    order_id_exposure_attempted: bool
    real_id_exposure_attempted: bool
    broker_api_response_exposure_attempted: bool
    api_call_allowed: bool
    api_call_attempted: bool
    http_client_present: bool
    real_transport_attempted: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_executed: bool
    actual_checker_execution_performed: bool
    actual_result_receipt_received: bool
    actual_receipt_handoff_executed: bool
    fresh_preflight_executed: bool
    final_confirmation_received: bool
    one_post_max_required: bool
    no_retry_required: bool
    fresh_preflight_required: bool
    final_confirmation_required: bool
    sanitized_result_required: bool
    safe_to_render: bool
    safe_to_serialize: bool
    check_results: tuple[LiveOrderRealTransportControlledCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealTransportControlledStatus):
            raise LiveVerificationValidationError(
                "status must be transport controlled status",
            )
        _require_non_empty("transport_mode", self.transport_mode)
        _require_non_empty("safe_signing_label", self.safe_signing_label)
        _require_non_empty("safe_headers_label", self.safe_headers_label)
        _require_non_empty("safe_signing_status", self.safe_signing_status)
        _require_non_empty("safe_headers_status", self.safe_headers_status)
        _require_non_empty("safe_transport_label", self.safe_transport_label)
        _require_non_empty("safe_transport_status", self.safe_transport_status)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "transport_controlled_ready",
                "transport_declared",
                "transport_requested",
                "signing_headers_prerequisite_checked",
                "signing_headers_prerequisite_satisfied",
                "signing_headers_controlled_ready",
                "signing_controlled_ready",
                "headers_controlled_ready",
                "transport_unknown",
                "transport_failed",
                "transport_unavailable",
                "transport_timeout",
                "unsafe_exposure_attempted",
                "credential_value_exposure_attempted",
                "signature_value_exposure_attempted",
                "headers_value_exposure_attempted",
                "raw_request_exposure_attempted",
                "raw_response_exposure_attempted",
                "request_body_exposure_attempted",
                "response_body_exposure_attempted",
                "endpoint_actual_value_exposure_attempted",
                "account_id_exposure_attempted",
                "order_id_exposure_attempted",
                "real_id_exposure_attempted",
                "broker_api_response_exposure_attempted",
                "api_call_allowed",
                "api_call_attempted",
                "http_client_present",
                "real_transport_attempted",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "actual_checker_execution_performed",
                "actual_result_receipt_received",
                "actual_receipt_handoff_executed",
                "fresh_preflight_executed",
                "final_confirmation_received",
                "one_post_max_required",
                "no_retry_required",
                "fresh_preflight_required",
                "final_confirmation_required",
                "sanitized_result_required",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_transport_controlled(
    *,
    input_snapshot: LiveOrderRealTransportControlledInput | None = None,
    signing_headers_result: LiveOrderRealSigningHeadersControlledResult | None = None,
) -> LiveOrderRealTransportControlledResult:
    """Build a safe transport readiness result without transport execution."""
    snapshot = input_snapshot or LiveOrderRealTransportControlledInput()
    if signing_headers_result is not None:
        snapshot = _merge_signing_headers_result(snapshot, signing_headers_result)

    status, primary_reasons = _status_from_input(snapshot)
    blocked_reasons = _blocked_reasons(snapshot=snapshot, primary_reasons=primary_reasons)
    ready = status is TransportControlledStatus.TRANSPORT_READY_NO_API_NO_POST
    prerequisite_satisfied = _signing_headers_prerequisite_satisfied(snapshot)
    safe_mode = (
        snapshot.transport_mode
        if snapshot.transport_mode
        == TransportControlledMode.TRANSPORT_CONTROLLED_IMPLEMENTATION_ONLY.value
        else UNSUPPORTED_TRANSPORT_CONTROLLED_LABEL
    )
    safe_signing_label = (
        snapshot.safe_signing_label
        if snapshot.safe_signing_label == SAFE_SIGNING_LABEL
        else UNSUPPORTED_TRANSPORT_CONTROLLED_LABEL
    )
    safe_headers_label = (
        snapshot.safe_headers_label
        if snapshot.safe_headers_label == SAFE_HEADERS_LABEL
        else UNSUPPORTED_TRANSPORT_CONTROLLED_LABEL
    )
    safe_transport_label = (
        snapshot.safe_transport_label
        if snapshot.safe_transport_label == SAFE_TRANSPORT_LABEL
        else UNSUPPORTED_TRANSPORT_CONTROLLED_LABEL
    )

    return LiveOrderRealTransportControlledResult(
        status=status,
        transport_controlled_ready=ready,
        transport_mode=safe_mode,
        transport_declared=snapshot.transport_declared,
        transport_requested=snapshot.transport_requested,
        signing_headers_prerequisite_checked=(
            snapshot.signing_headers_prerequisite_checked
        ),
        signing_headers_prerequisite_satisfied=prerequisite_satisfied,
        signing_headers_controlled_ready=snapshot.signing_headers_controlled_ready,
        signing_controlled_ready=snapshot.signing_controlled_ready,
        headers_controlled_ready=snapshot.headers_controlled_ready,
        safe_signing_label=safe_signing_label,
        safe_headers_label=safe_headers_label,
        safe_signing_status=snapshot.safe_signing_status,
        safe_headers_status=snapshot.safe_headers_status,
        safe_transport_label=safe_transport_label,
        safe_transport_status=status.value,
        transport_unknown=snapshot.transport_unknown,
        transport_failed=snapshot.transport_failed,
        transport_unavailable=snapshot.transport_unavailable,
        transport_timeout=snapshot.transport_timeout,
        unsafe_exposure_attempted=False,
        credential_value_exposure_attempted=False,
        signature_value_exposure_attempted=False,
        headers_value_exposure_attempted=False,
        raw_request_exposure_attempted=False,
        raw_response_exposure_attempted=False,
        request_body_exposure_attempted=False,
        response_body_exposure_attempted=False,
        endpoint_actual_value_exposure_attempted=False,
        account_id_exposure_attempted=False,
        order_id_exposure_attempted=False,
        real_id_exposure_attempted=False,
        broker_api_response_exposure_attempted=False,
        api_call_allowed=False,
        api_call_attempted=False,
        http_client_present=False,
        real_transport_attempted=False,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_executed=False,
        actual_checker_execution_performed=False,
        actual_result_receipt_received=False,
        actual_receipt_handoff_executed=False,
        fresh_preflight_executed=False,
        final_confirmation_received=False,
        one_post_max_required=snapshot.one_post_max_required,
        no_retry_required=snapshot.no_retry_required,
        fresh_preflight_required=snapshot.fresh_preflight_required,
        final_confirmation_required=snapshot.final_confirmation_required,
        sanitized_result_required=snapshot.sanitized_result_required,
        safe_to_render=True,
        safe_to_serialize=True,
        check_results=_build_check_results(
            snapshot=snapshot,
            status=status,
            ready=ready,
            prerequisite_satisfied=prerequisite_satisfied,
            safe_transport_label=safe_transport_label,
        ),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            TRANSPORT_CONTROLLED_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_transport_controlled_blockers_no_api_no_post"
        ),
    )


def render_live_order_real_transport_controlled_markdown(
    result: LiveOrderRealTransportControlledResult,
) -> str:
    """Render a safe controlled transport summary only."""
    lines = [
        "# Step 6G Transport Controlled Boundary",
        "",
        "This is a controlled transport boundary, not real transport.",
        "This result contains only safe labels, safe statuses, and booleans.",
        "This result does not execute API calls.",
        "This result does not execute HTTP POST.",
        "This result does not call order endpoints.",
        "This result does not call live_order_once.",
        "This result does not contain credential values.",
        "This result does not contain signature values.",
        "This result does not contain headers values.",
        "This result does not contain raw requests.",
        "This result does not contain raw responses.",
        "This result does not expose real IDs, account IDs, or order IDs.",
        "Transport ready does not allow POST.",
        "Transport ready does not allow order endpoint calls.",
        "Transport ready does not allow live_order_once.",
        "Transport ready is not fresh preflight.",
        "Transport ready is not final confirmation.",
        "One POST max and no retry remain future blockers.",
        "Missing, unknown, failed, unavailable, and timeout states fail closed.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- transport_controlled_ready: {_bool_text(result.transport_controlled_ready)}",
        f"- transport_mode: {result.transport_mode}",
        f"- safe_transport_label: {result.safe_transport_label}",
        f"- safe_transport_status: {result.safe_transport_status}",
        (
            "- signing_headers_prerequisite_checked: "
            f"{_bool_text(result.signing_headers_prerequisite_checked)}"
        ),
        (
            "- signing_headers_prerequisite_satisfied: "
            f"{_bool_text(result.signing_headers_prerequisite_satisfied)}"
        ),
        (
            "- signing_headers_controlled_ready: "
            f"{_bool_text(result.signing_headers_controlled_ready)}"
        ),
        f"- signing_controlled_ready: {_bool_text(result.signing_controlled_ready)}",
        f"- headers_controlled_ready: {_bool_text(result.headers_controlled_ready)}",
        "",
        "## Safety",
        f"- unsafe_exposure_attempted: {_bool_text(result.unsafe_exposure_attempted)}",
        (
            "- credential_value_exposure_attempted: "
            f"{_bool_text(result.credential_value_exposure_attempted)}"
        ),
        (
            "- signature_value_exposure_attempted: "
            f"{_bool_text(result.signature_value_exposure_attempted)}"
        ),
        (
            "- headers_value_exposure_attempted: "
            f"{_bool_text(result.headers_value_exposure_attempted)}"
        ),
        (
            "- raw_request_exposure_attempted: "
            f"{_bool_text(result.raw_request_exposure_attempted)}"
        ),
        (
            "- raw_response_exposure_attempted: "
            f"{_bool_text(result.raw_response_exposure_attempted)}"
        ),
        f"- api_call_allowed: {_bool_text(result.api_call_allowed)}",
        f"- api_call_attempted: {_bool_text(result.api_call_attempted)}",
        f"- http_client_present: {_bool_text(result.http_client_present)}",
        f"- real_transport_attempted: {_bool_text(result.real_transport_attempted)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- fresh_preflight_executed: {_bool_text(result.fresh_preflight_executed)}",
        (
            "- final_confirmation_received: "
            f"{_bool_text(result.final_confirmation_received)}"
        ),
        "",
        "## Future Blockers",
        f"- one_post_max_required: {_bool_text(result.one_post_max_required)}",
        f"- no_retry_required: {_bool_text(result.no_retry_required)}",
        f"- fresh_preflight_required: {_bool_text(result.fresh_preflight_required)}",
        (
            "- final_confirmation_required: "
            f"{_bool_text(result.final_confirmation_required)}"
        ),
        f"- sanitized_result_required: {_bool_text(result.sanitized_result_required)}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines)


def _merge_signing_headers_result(
    snapshot: LiveOrderRealTransportControlledInput,
    signing_headers_result: LiveOrderRealSigningHeadersControlledResult,
) -> LiveOrderRealTransportControlledInput:
    return replace(
        snapshot,
        signing_headers_controlled_ready=(
            signing_headers_result.signing_headers_controlled_ready
        ),
        signing_controlled_ready=signing_headers_result.signing_controlled_ready,
        headers_controlled_ready=signing_headers_result.headers_controlled_ready,
        signing_headers_prerequisite_satisfied=(
            signing_headers_result.signing_headers_controlled_ready
            and signing_headers_result.signing_controlled_ready
            and signing_headers_result.headers_controlled_ready
        ),
        safe_signing_label=signing_headers_result.safe_signing_label,
        safe_headers_label=signing_headers_result.safe_headers_label,
        safe_signing_status=signing_headers_result.safe_signing_status,
        safe_headers_status=signing_headers_result.safe_headers_status,
        transport_unknown=(
            snapshot.transport_unknown
            or signing_headers_result.signing_unknown
            or signing_headers_result.headers_unknown
        ),
        transport_failed=(
            snapshot.transport_failed
            or signing_headers_result.signing_failed
            or signing_headers_result.headers_failed
        ),
        transport_unavailable=(
            snapshot.transport_unavailable
            or signing_headers_result.signing_unavailable
            or signing_headers_result.headers_unavailable
        ),
        transport_timeout=(
            snapshot.transport_timeout
            or signing_headers_result.signing_timeout
            or signing_headers_result.headers_timeout
        ),
    )


def _status_from_input(
    snapshot: LiveOrderRealTransportControlledInput,
) -> tuple[LiveOrderRealTransportControlledStatus, tuple[str, ...]]:
    if (
        snapshot.transport_mode
        != TransportControlledMode.TRANSPORT_CONTROLLED_IMPLEMENTATION_ONLY.value
    ):
        return TransportControlledStatus.TRANSPORT_BLOCKED_UNKNOWN, (
            "unsupported_transport_mode",
        )
    if not snapshot.transport_declared or not snapshot.transport_requested:
        return TransportControlledStatus.TRANSPORT_NOT_READY, (
            "transport_not_declared_or_requested",
        )
    if not _signing_headers_prerequisite_satisfied(snapshot):
        return TransportControlledStatus.TRANSPORT_BLOCKED_MISSING_SIGNING_HEADERS, (
            "signing_headers_prerequisite_missing",
        )
    if snapshot.transport_unknown:
        return TransportControlledStatus.TRANSPORT_BLOCKED_UNKNOWN, (
            "transport_unknown",
        )
    if snapshot.transport_failed:
        return TransportControlledStatus.TRANSPORT_BLOCKED_FAILED, (
            "transport_failed",
        )
    if snapshot.transport_unavailable:
        return TransportControlledStatus.TRANSPORT_BLOCKED_UNAVAILABLE, (
            "transport_unavailable",
        )
    if snapshot.transport_timeout:
        return TransportControlledStatus.TRANSPORT_BLOCKED_TIMEOUT, (
            "transport_timeout",
        )
    if snapshot.credential_value_exposure_attempted:
        return (
            TransportControlledStatus.TRANSPORT_BLOCKED_CREDENTIAL_VALUE_EXPOSURE,
            ("credential_value_exposure_attempted",),
        )
    if snapshot.signature_value_exposure_attempted:
        return (
            TransportControlledStatus.TRANSPORT_BLOCKED_SIGNATURE_VALUE_EXPOSURE,
            ("signature_value_exposure_attempted",),
        )
    if snapshot.headers_value_exposure_attempted:
        return (
            TransportControlledStatus.TRANSPORT_BLOCKED_HEADERS_VALUE_EXPOSURE,
            ("headers_value_exposure_attempted",),
        )
    if snapshot.raw_request_exposure_attempted:
        return TransportControlledStatus.TRANSPORT_BLOCKED_RAW_REQUEST_EXPOSURE, (
            "raw_request_exposure_attempted",
        )
    if snapshot.raw_response_exposure_attempted:
        return TransportControlledStatus.TRANSPORT_BLOCKED_RAW_RESPONSE_EXPOSURE, (
            "raw_response_exposure_attempted",
        )
    if _unsafe_exposure_attempted(snapshot):
        return TransportControlledStatus.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE, (
            "unsafe_exposure_attempted",
        )
    if (
        snapshot.api_call_allowed
        or snapshot.api_call_attempted
        or snapshot.http_client_present
        or snapshot.real_transport_attempted
    ):
        return TransportControlledStatus.TRANSPORT_BLOCKED_API_ATTEMPTED, (
            "transport_or_api_attempted",
        )
    if snapshot.http_post_executed or snapshot.post_allowed_this_step or snapshot.post_executed:
        return TransportControlledStatus.TRANSPORT_BLOCKED_POST_ATTEMPTED, (
            "post_attempted_or_allowed",
        )
    if snapshot.order_endpoint_called:
        return TransportControlledStatus.TRANSPORT_BLOCKED_ORDER_ENDPOINT, (
            "order_endpoint_called",
        )
    if snapshot.live_order_once_called:
        return TransportControlledStatus.TRANSPORT_BLOCKED_LIVE_ORDER_ONCE, (
            "live_order_once_called",
        )
    if (
        snapshot.actual_checker_execution_performed
        or snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
        or snapshot.fresh_preflight_executed
        or snapshot.final_confirmation_received
        or not snapshot.one_post_max_required
        or not snapshot.no_retry_required
        or not snapshot.fresh_preflight_required
        or not snapshot.final_confirmation_required
        or not snapshot.sanitized_result_required
    ):
        return (
            TransportControlledStatus.TRANSPORT_BLOCKED_PREFLIGHT_OR_CONFIRMATION,
            ("future_post_gate_blocker_missing_or_executed",),
        )
    return TransportControlledStatus.TRANSPORT_READY_NO_API_NO_POST, ()


def _blocked_reasons(
    *,
    snapshot: LiveOrderRealTransportControlledInput,
    primary_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons = list(primary_reasons)
    if not snapshot.signing_headers_prerequisite_checked:
        reasons.append("signing_headers_prerequisite_not_checked")
    if not snapshot.signing_headers_controlled_ready:
        reasons.append("signing_headers_controlled_not_ready")
    if not snapshot.signing_controlled_ready:
        reasons.append("signing_controlled_not_ready")
    if not snapshot.headers_controlled_ready:
        reasons.append("headers_controlled_not_ready")
    if snapshot.safe_signing_label != SAFE_SIGNING_LABEL:
        reasons.append("safe_signing_label_invalid")
    if snapshot.safe_headers_label != SAFE_HEADERS_LABEL:
        reasons.append("safe_headers_label_invalid")
    if snapshot.safe_transport_label != SAFE_TRANSPORT_LABEL:
        reasons.append("safe_transport_label_invalid")
    if snapshot.safe_signing_status != _ready_signing_headers_status():
        reasons.append("safe_signing_status_not_ready")
    if snapshot.safe_headers_status != _ready_signing_headers_status():
        reasons.append("safe_headers_status_not_ready")
    if snapshot.request_body_exposure_attempted:
        reasons.append("request_body_exposure_attempted")
    if snapshot.response_body_exposure_attempted:
        reasons.append("response_body_exposure_attempted")
    if snapshot.endpoint_actual_value_exposure_attempted:
        reasons.append("endpoint_actual_value_exposure_attempted")
    if snapshot.account_id_exposure_attempted:
        reasons.append("account_id_exposure_attempted")
    if snapshot.order_id_exposure_attempted:
        reasons.append("order_id_exposure_attempted")
    if snapshot.real_id_exposure_attempted:
        reasons.append("real_id_exposure_attempted")
    if snapshot.broker_api_response_exposure_attempted:
        reasons.append("broker_api_response_exposure_attempted")
    if not snapshot.safe_to_render:
        reasons.append("render_not_safe")
    if not snapshot.safe_to_serialize:
        reasons.append("serialize_not_safe")
    return _dedupe(reasons)


def _build_check_results(
    *,
    snapshot: LiveOrderRealTransportControlledInput,
    status: LiveOrderRealTransportControlledStatus,
    ready: bool,
    prerequisite_satisfied: bool,
    safe_transport_label: str,
) -> tuple[LiveOrderRealTransportControlledCheckResult, ...]:
    return (
        LiveOrderRealTransportControlledCheckResult(
            name="controlled transport mode",
            passed=(
                snapshot.transport_mode
                == TransportControlledMode.TRANSPORT_CONTROLLED_IMPLEMENTATION_ONLY.value
            ),
            sanitized_value=(
                snapshot.transport_mode
                if snapshot.transport_mode
                == TransportControlledMode.TRANSPORT_CONTROLLED_IMPLEMENTATION_ONLY.value
                else UNSUPPORTED_TRANSPORT_CONTROLLED_LABEL
            ),
            expected="transport controlled implementation only",
        ),
        LiveOrderRealTransportControlledCheckResult(
            name="safe transport label",
            passed=safe_transport_label == SAFE_TRANSPORT_LABEL,
            sanitized_value=safe_transport_label,
            expected="fixed safe transport label",
        ),
        LiveOrderRealTransportControlledCheckResult(
            name="signing headers prerequisite",
            passed=prerequisite_satisfied,
            sanitized_value="ready" if prerequisite_satisfied else "blocked",
            expected="controlled signing headers ready",
        ),
        LiveOrderRealTransportControlledCheckResult(
            name="no api post live_order_once",
            passed=(
                not snapshot.api_call_allowed
                and not snapshot.api_call_attempted
                and not snapshot.http_client_present
                and not snapshot.real_transport_attempted
                and not snapshot.http_post_executed
                and not snapshot.order_endpoint_called
                and not snapshot.live_order_once_called
                and not snapshot.post_allowed_this_step
                and not snapshot.post_executed
            ),
            sanitized_value="blocked",
            expected="no API no POST no order endpoint no live_order_once",
        ),
        LiveOrderRealTransportControlledCheckResult(
            name="future post blockers",
            passed=(
                snapshot.one_post_max_required
                and snapshot.no_retry_required
                and snapshot.fresh_preflight_required
                and snapshot.final_confirmation_required
                and snapshot.sanitized_result_required
            ),
            sanitized_value="required",
            expected="one POST max no retry preflight confirmation sanitized result",
        ),
        LiveOrderRealTransportControlledCheckResult(
            name="ready is not execution permission",
            passed=ready
            == (status is TransportControlledStatus.TRANSPORT_READY_NO_API_NO_POST),
            sanitized_value=status.value,
            expected="ready no API no POST",
        ),
    )


def _signing_headers_prerequisite_satisfied(
    snapshot: LiveOrderRealTransportControlledInput,
) -> bool:
    return (
        snapshot.signing_headers_prerequisite_checked
        and snapshot.signing_headers_controlled_ready
        and snapshot.signing_controlled_ready
        and snapshot.headers_controlled_ready
        and snapshot.signing_headers_prerequisite_satisfied
        and snapshot.safe_signing_label == SAFE_SIGNING_LABEL
        and snapshot.safe_headers_label == SAFE_HEADERS_LABEL
        and snapshot.safe_signing_status == _ready_signing_headers_status()
        and snapshot.safe_headers_status == _ready_signing_headers_status()
    )


def _unsafe_exposure_attempted(
    snapshot: LiveOrderRealTransportControlledInput,
) -> bool:
    return (
        snapshot.unsafe_exposure_attempted
        or snapshot.request_body_exposure_attempted
        or snapshot.response_body_exposure_attempted
        or snapshot.endpoint_actual_value_exposure_attempted
        or snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.real_id_exposure_attempted
        or snapshot.broker_api_response_exposure_attempted
        or snapshot.safe_transport_label != SAFE_TRANSPORT_LABEL
        or snapshot.safe_signing_label != SAFE_SIGNING_LABEL
        or snapshot.safe_headers_label != SAFE_HEADERS_LABEL
        or not snapshot.safe_to_render
        or not snapshot.safe_to_serialize
    )


def _validate_result_safety(result: LiveOrderRealTransportControlledResult) -> None:
    if result.transport_controlled_ready and (
        result.api_call_allowed
        or result.api_call_attempted
        or result.http_client_present
        or result.real_transport_attempted
        or result.http_post_executed
        or result.order_endpoint_called
        or result.live_order_once_called
        or result.post_allowed_this_step
        or result.post_executed
        or result.fresh_preflight_executed
        or result.final_confirmation_received
    ):
        raise LiveVerificationValidationError(
            "transport controlled ready must not authorize execution",
        )
    forbidden_flags = (
        result.unsafe_exposure_attempted,
        result.credential_value_exposure_attempted,
        result.signature_value_exposure_attempted,
        result.headers_value_exposure_attempted,
        result.raw_request_exposure_attempted,
        result.raw_response_exposure_attempted,
        result.request_body_exposure_attempted,
        result.response_body_exposure_attempted,
        result.endpoint_actual_value_exposure_attempted,
        result.account_id_exposure_attempted,
        result.order_id_exposure_attempted,
        result.real_id_exposure_attempted,
        result.broker_api_response_exposure_attempted,
        result.api_call_allowed,
        result.api_call_attempted,
        result.http_client_present,
        result.real_transport_attempted,
        result.http_post_executed,
        result.order_endpoint_called,
        result.live_order_once_called,
        result.post_allowed_this_step,
        result.post_executed,
        result.actual_checker_execution_performed,
        result.actual_result_receipt_received,
        result.actual_receipt_handoff_executed,
        result.fresh_preflight_executed,
        result.final_confirmation_received,
    )
    if any(forbidden_flags):
        raise LiveVerificationValidationError(
            "transport controlled result must sanitize unsafe flags",
        )


def _ready_signing_headers_status() -> str:
    return (
        LiveOrderRealSigningHeadersControlledStatus
        .SIGNING_HEADERS_READY_NO_TRANSPORT
        .value
    )


def _dedupe(values: list[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return tuple(deduped)


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
