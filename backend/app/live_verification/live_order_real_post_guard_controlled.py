"""Step 6G controlled POST guard boundary.

This module converts a safe transport controlled result into POST guard
readiness labels, safe statuses, and booleans only. It does not create raw
requests, receive raw responses, import HTTP clients, call APIs, execute HTTP
POST, call order endpoints, call live_order_once, run fresh preflight, run final
confirmation, or update ledgers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_transport_controlled import (
    SAFE_TRANSPORT_LABEL,
    LiveOrderRealTransportControlledResult,
    LiveOrderRealTransportControlledStatus,
)

POST_GUARD_CONTROLLED_RECOMMENDED_NEXT_STEP = (
    "post_guard_controlled_boundary_review_no_api_no_post"
)
SAFE_POST_GUARD_LABEL = "CONTROLLED_POST_GUARD_BOUNDARY"
UNSUPPORTED_POST_GUARD_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealPostGuardControlledStatus(str, Enum):
    POST_GUARD_NOT_READY = "POST_GUARD_NOT_READY"
    POST_GUARD_READY_NO_POST = "POST_GUARD_READY_NO_POST"
    POST_GUARD_BLOCKED_MISSING_TRANSPORT = "POST_GUARD_BLOCKED_MISSING_TRANSPORT"
    POST_GUARD_BLOCKED_UNKNOWN = "POST_GUARD_BLOCKED_UNKNOWN"
    POST_GUARD_BLOCKED_FAILED = "POST_GUARD_BLOCKED_FAILED"
    POST_GUARD_BLOCKED_UNAVAILABLE = "POST_GUARD_BLOCKED_UNAVAILABLE"
    POST_GUARD_BLOCKED_TIMEOUT = "POST_GUARD_BLOCKED_TIMEOUT"
    POST_GUARD_BLOCKED_REJECTED = "POST_GUARD_BLOCKED_REJECTED"
    POST_GUARD_BLOCKED_STALE = "POST_GUARD_BLOCKED_STALE"
    POST_GUARD_BLOCKED_PREVIOUS_TURN = "POST_GUARD_BLOCKED_PREVIOUS_TURN"
    POST_GUARD_BLOCKED_REUSED = "POST_GUARD_BLOCKED_REUSED"
    POST_GUARD_BLOCKED_UNSAFE_EXPOSURE = "POST_GUARD_BLOCKED_UNSAFE_EXPOSURE"
    POST_GUARD_BLOCKED_RETRY_ATTEMPTED = "POST_GUARD_BLOCKED_RETRY_ATTEMPTED"
    POST_GUARD_BLOCKED_SECOND_POST_ATTEMPTED = (
        "POST_GUARD_BLOCKED_SECOND_POST_ATTEMPTED"
    )
    POST_GUARD_BLOCKED_MULTIPLE_POST_ATTEMPTS = (
        "POST_GUARD_BLOCKED_MULTIPLE_POST_ATTEMPTS"
    )
    POST_GUARD_BLOCKED_API_ATTEMPTED = "POST_GUARD_BLOCKED_API_ATTEMPTED"
    POST_GUARD_BLOCKED_POST_ATTEMPTED = "POST_GUARD_BLOCKED_POST_ATTEMPTED"
    POST_GUARD_BLOCKED_ORDER_ENDPOINT = "POST_GUARD_BLOCKED_ORDER_ENDPOINT"
    POST_GUARD_BLOCKED_LIVE_ORDER_ONCE = "POST_GUARD_BLOCKED_LIVE_ORDER_ONCE"
    POST_GUARD_BLOCKED_RAW_REQUEST_EXPOSURE = (
        "POST_GUARD_BLOCKED_RAW_REQUEST_EXPOSURE"
    )
    POST_GUARD_BLOCKED_RAW_RESPONSE_EXPOSURE = (
        "POST_GUARD_BLOCKED_RAW_RESPONSE_EXPOSURE"
    )
    POST_GUARD_BLOCKED_PREFLIGHT_OR_CONFIRMATION = (
        "POST_GUARD_BLOCKED_PREFLIGHT_OR_CONFIRMATION"
    )


class LiveOrderRealPostGuardControlledMode(str, Enum):
    POST_GUARD_CONTROLLED_IMPLEMENTATION_ONLY = (
        "POST_GUARD_CONTROLLED_IMPLEMENTATION_ONLY"
    )


PostGuardControlledStatus = LiveOrderRealPostGuardControlledStatus
PostGuardControlledMode = LiveOrderRealPostGuardControlledMode


@dataclass(frozen=True)
class LiveOrderRealPostGuardControlledInput:
    post_guard_mode: str = (
        PostGuardControlledMode.POST_GUARD_CONTROLLED_IMPLEMENTATION_ONLY.value
    )
    post_guard_declared: bool = True
    post_guard_requested: bool = True
    transport_prerequisite_checked: bool = True
    transport_controlled_ready: bool = True
    transport_prerequisite_satisfied: bool = True
    safe_transport_label: str = SAFE_TRANSPORT_LABEL
    safe_transport_status: str = (
        LiveOrderRealTransportControlledStatus.TRANSPORT_READY_NO_API_NO_POST.value
    )
    safe_post_guard_label: str = SAFE_POST_GUARD_LABEL
    post_guard_unknown: bool = False
    post_guard_failed: bool = False
    post_guard_unavailable: bool = False
    post_guard_timeout: bool = False
    post_guard_rejected: bool = False
    post_guard_stale: bool = False
    post_guard_previous_turn: bool = False
    post_guard_reused: bool = False
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
    confirmation_phrase_exposure_attempted: bool = False
    preflight_detail_exposure_attempted: bool = False
    ledger_state_exposure_attempted: bool = False
    api_call_allowed: bool = False
    api_call_attempted: bool = False
    http_client_present: bool = False
    http_post_executed: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    retry_attempted: bool = False
    second_post_attempted: bool = False
    multiple_post_attempts_attempted: bool = False
    actual_checker_execution_performed: bool = False
    actual_result_receipt_received: bool = False
    actual_receipt_handoff_executed: bool = False
    fresh_preflight_executed: bool = False
    final_confirmation_received: bool = False
    one_post_max_enforced: bool = True
    no_retry_enforced: bool = True
    timeout_fail_closed_enforced: bool = True
    max_post_attempts_allowed: int = 1
    second_post_attempt_blocked: bool = True
    multiple_post_attempts_blocked: bool = True
    retry_after_failure_blocked: bool = True
    retry_after_timeout_blocked: bool = True
    retry_after_unknown_blocked: bool = True
    fresh_preflight_required: bool = True
    final_confirmation_required: bool = True
    sanitized_result_required: bool = True
    preflight_must_be_current: bool = True
    confirmation_must_be_new_for_this_step: bool = True
    step4_approval_phrase_reuse_blocked: bool = True
    ledger_state_reuse_blocked: bool = True
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("post_guard_mode", self.post_guard_mode)
        _require_non_empty("safe_transport_label", self.safe_transport_label)
        _require_non_empty("safe_transport_status", self.safe_transport_status)
        _require_non_empty("safe_post_guard_label", self.safe_post_guard_label)
        if self.max_post_attempts_allowed != 1:
            raise LiveVerificationValidationError(
                "max_post_attempts_allowed must be 1",
            )
        _validate_bool_fields(
            self,
            (
                "post_guard_declared",
                "post_guard_requested",
                "transport_prerequisite_checked",
                "transport_controlled_ready",
                "transport_prerequisite_satisfied",
                "post_guard_unknown",
                "post_guard_failed",
                "post_guard_unavailable",
                "post_guard_timeout",
                "post_guard_rejected",
                "post_guard_stale",
                "post_guard_previous_turn",
                "post_guard_reused",
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
                "confirmation_phrase_exposure_attempted",
                "preflight_detail_exposure_attempted",
                "ledger_state_exposure_attempted",
                "api_call_allowed",
                "api_call_attempted",
                "http_client_present",
                "http_post_executed",
                "post_allowed_this_step",
                "post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "retry_attempted",
                "second_post_attempted",
                "multiple_post_attempts_attempted",
                "actual_checker_execution_performed",
                "actual_result_receipt_received",
                "actual_receipt_handoff_executed",
                "fresh_preflight_executed",
                "final_confirmation_received",
                "one_post_max_enforced",
                "no_retry_enforced",
                "timeout_fail_closed_enforced",
                "second_post_attempt_blocked",
                "multiple_post_attempts_blocked",
                "retry_after_failure_blocked",
                "retry_after_timeout_blocked",
                "retry_after_unknown_blocked",
                "fresh_preflight_required",
                "final_confirmation_required",
                "sanitized_result_required",
                "preflight_must_be_current",
                "confirmation_must_be_new_for_this_step",
                "step4_approval_phrase_reuse_blocked",
                "ledger_state_reuse_blocked",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealPostGuardControlledCheckResult:
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
class LiveOrderRealPostGuardControlledResult:
    status: LiveOrderRealPostGuardControlledStatus
    post_guard_ready: bool
    post_guard_mode: str
    post_guard_declared: bool
    post_guard_requested: bool
    transport_prerequisite_checked: bool
    transport_prerequisite_satisfied: bool
    transport_controlled_ready: bool
    safe_transport_label: str
    safe_transport_status: str
    safe_post_guard_label: str
    safe_post_guard_status: str
    post_guard_unknown: bool
    post_guard_failed: bool
    post_guard_unavailable: bool
    post_guard_timeout: bool
    post_guard_rejected: bool
    post_guard_stale: bool
    post_guard_previous_turn: bool
    post_guard_reused: bool
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
    confirmation_phrase_exposure_attempted: bool
    preflight_detail_exposure_attempted: bool
    ledger_state_exposure_attempted: bool
    api_call_allowed: bool
    api_call_attempted: bool
    http_client_present: bool
    http_post_executed: bool
    post_allowed_this_step: bool
    post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    retry_attempted: bool
    second_post_attempted: bool
    multiple_post_attempts_attempted: bool
    actual_checker_execution_performed: bool
    actual_result_receipt_received: bool
    actual_receipt_handoff_executed: bool
    fresh_preflight_executed: bool
    final_confirmation_received: bool
    one_post_max_enforced: bool
    no_retry_enforced: bool
    timeout_fail_closed_enforced: bool
    max_post_attempts_allowed: int
    second_post_attempt_blocked: bool
    multiple_post_attempts_blocked: bool
    retry_after_failure_blocked: bool
    retry_after_timeout_blocked: bool
    retry_after_unknown_blocked: bool
    fresh_preflight_required: bool
    final_confirmation_required: bool
    sanitized_result_required: bool
    preflight_must_be_current: bool
    confirmation_must_be_new_for_this_step: bool
    step4_approval_phrase_reuse_blocked: bool
    ledger_state_reuse_blocked: bool
    safe_to_render: bool
    safe_to_serialize: bool
    check_results: tuple[LiveOrderRealPostGuardControlledCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealPostGuardControlledStatus):
            raise LiveVerificationValidationError(
                "status must be post guard controlled status",
            )
        _require_non_empty("post_guard_mode", self.post_guard_mode)
        _require_non_empty("safe_transport_label", self.safe_transport_label)
        _require_non_empty("safe_transport_status", self.safe_transport_status)
        _require_non_empty("safe_post_guard_label", self.safe_post_guard_label)
        _require_non_empty("safe_post_guard_status", self.safe_post_guard_status)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        if self.max_post_attempts_allowed != 1:
            raise LiveVerificationValidationError(
                "max_post_attempts_allowed must be 1",
            )
        _validate_bool_fields(
            self,
            (
                "post_guard_ready",
                "post_guard_declared",
                "post_guard_requested",
                "transport_prerequisite_checked",
                "transport_prerequisite_satisfied",
                "transport_controlled_ready",
                "post_guard_unknown",
                "post_guard_failed",
                "post_guard_unavailable",
                "post_guard_timeout",
                "post_guard_rejected",
                "post_guard_stale",
                "post_guard_previous_turn",
                "post_guard_reused",
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
                "confirmation_phrase_exposure_attempted",
                "preflight_detail_exposure_attempted",
                "ledger_state_exposure_attempted",
                "api_call_allowed",
                "api_call_attempted",
                "http_client_present",
                "http_post_executed",
                "post_allowed_this_step",
                "post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "retry_attempted",
                "second_post_attempted",
                "multiple_post_attempts_attempted",
                "actual_checker_execution_performed",
                "actual_result_receipt_received",
                "actual_receipt_handoff_executed",
                "fresh_preflight_executed",
                "final_confirmation_received",
                "one_post_max_enforced",
                "no_retry_enforced",
                "timeout_fail_closed_enforced",
                "second_post_attempt_blocked",
                "multiple_post_attempts_blocked",
                "retry_after_failure_blocked",
                "retry_after_timeout_blocked",
                "retry_after_unknown_blocked",
                "fresh_preflight_required",
                "final_confirmation_required",
                "sanitized_result_required",
                "preflight_must_be_current",
                "confirmation_must_be_new_for_this_step",
                "step4_approval_phrase_reuse_blocked",
                "ledger_state_reuse_blocked",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_post_guard_controlled(
    *,
    input_snapshot: LiveOrderRealPostGuardControlledInput | None = None,
    transport_result: LiveOrderRealTransportControlledResult | None = None,
) -> LiveOrderRealPostGuardControlledResult:
    """Build a safe POST guard result without API, POST, or live execution."""
    snapshot = input_snapshot or LiveOrderRealPostGuardControlledInput()
    if transport_result is not None:
        snapshot = _merge_transport_result(snapshot, transport_result)

    status, primary_reasons = _status_from_input(snapshot)
    blocked_reasons = _blocked_reasons(snapshot=snapshot, primary_reasons=primary_reasons)
    ready = status is PostGuardControlledStatus.POST_GUARD_READY_NO_POST
    prerequisite_satisfied = _transport_prerequisite_satisfied(snapshot)
    safe_mode = (
        snapshot.post_guard_mode
        if snapshot.post_guard_mode
        == PostGuardControlledMode.POST_GUARD_CONTROLLED_IMPLEMENTATION_ONLY.value
        else UNSUPPORTED_POST_GUARD_LABEL
    )
    safe_transport_label = (
        snapshot.safe_transport_label
        if snapshot.safe_transport_label == SAFE_TRANSPORT_LABEL
        else UNSUPPORTED_POST_GUARD_LABEL
    )
    safe_post_guard_label = (
        snapshot.safe_post_guard_label
        if snapshot.safe_post_guard_label == SAFE_POST_GUARD_LABEL
        else UNSUPPORTED_POST_GUARD_LABEL
    )

    return LiveOrderRealPostGuardControlledResult(
        status=status,
        post_guard_ready=ready,
        post_guard_mode=safe_mode,
        post_guard_declared=snapshot.post_guard_declared,
        post_guard_requested=snapshot.post_guard_requested,
        transport_prerequisite_checked=snapshot.transport_prerequisite_checked,
        transport_prerequisite_satisfied=prerequisite_satisfied,
        transport_controlled_ready=snapshot.transport_controlled_ready,
        safe_transport_label=safe_transport_label,
        safe_transport_status=snapshot.safe_transport_status,
        safe_post_guard_label=safe_post_guard_label,
        safe_post_guard_status=status.value,
        post_guard_unknown=snapshot.post_guard_unknown,
        post_guard_failed=snapshot.post_guard_failed,
        post_guard_unavailable=snapshot.post_guard_unavailable,
        post_guard_timeout=snapshot.post_guard_timeout,
        post_guard_rejected=snapshot.post_guard_rejected,
        post_guard_stale=snapshot.post_guard_stale,
        post_guard_previous_turn=snapshot.post_guard_previous_turn,
        post_guard_reused=snapshot.post_guard_reused,
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
        confirmation_phrase_exposure_attempted=False,
        preflight_detail_exposure_attempted=False,
        ledger_state_exposure_attempted=False,
        api_call_allowed=False,
        api_call_attempted=False,
        http_client_present=False,
        http_post_executed=False,
        post_allowed_this_step=False,
        post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        retry_attempted=False,
        second_post_attempted=False,
        multiple_post_attempts_attempted=False,
        actual_checker_execution_performed=False,
        actual_result_receipt_received=False,
        actual_receipt_handoff_executed=False,
        fresh_preflight_executed=False,
        final_confirmation_received=False,
        one_post_max_enforced=snapshot.one_post_max_enforced,
        no_retry_enforced=snapshot.no_retry_enforced,
        timeout_fail_closed_enforced=snapshot.timeout_fail_closed_enforced,
        max_post_attempts_allowed=snapshot.max_post_attempts_allowed,
        second_post_attempt_blocked=snapshot.second_post_attempt_blocked,
        multiple_post_attempts_blocked=snapshot.multiple_post_attempts_blocked,
        retry_after_failure_blocked=snapshot.retry_after_failure_blocked,
        retry_after_timeout_blocked=snapshot.retry_after_timeout_blocked,
        retry_after_unknown_blocked=snapshot.retry_after_unknown_blocked,
        fresh_preflight_required=snapshot.fresh_preflight_required,
        final_confirmation_required=snapshot.final_confirmation_required,
        sanitized_result_required=snapshot.sanitized_result_required,
        preflight_must_be_current=snapshot.preflight_must_be_current,
        confirmation_must_be_new_for_this_step=(
            snapshot.confirmation_must_be_new_for_this_step
        ),
        step4_approval_phrase_reuse_blocked=(
            snapshot.step4_approval_phrase_reuse_blocked
        ),
        ledger_state_reuse_blocked=snapshot.ledger_state_reuse_blocked,
        safe_to_render=True,
        safe_to_serialize=True,
        check_results=_build_check_results(
            snapshot=snapshot,
            status=status,
            ready=ready,
            prerequisite_satisfied=prerequisite_satisfied,
            safe_post_guard_label=safe_post_guard_label,
        ),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            POST_GUARD_CONTROLLED_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_post_guard_controlled_blockers_no_api_no_post"
        ),
    )


def render_live_order_real_post_guard_controlled_markdown(
    result: LiveOrderRealPostGuardControlledResult,
) -> str:
    """Render a safe controlled POST guard summary only."""
    lines = [
        "# Step 6G POST Guard Controlled Boundary",
        "",
        "This is a controlled POST guard boundary, not an API call or HTTP POST.",
        "This result contains only safe labels, safe statuses, and booleans.",
        "This result does not execute API calls.",
        "This result does not execute HTTP POST.",
        "This result does not call order endpoints.",
        "This result does not call live_order_once.",
        "This result does not create raw requests.",
        "This result does not receive raw responses.",
        "This result does not contain credential values.",
        "This result does not contain signature values.",
        "This result does not contain headers values.",
        "This result does not expose real IDs, account IDs, or order IDs.",
        "This result does not expose confirmation phrase values.",
        "This result does not expose ledger state values.",
        "POST guard ready does not allow POST.",
        "POST guard ready does not allow order endpoint calls.",
        "POST guard ready does not allow live_order_once.",
        "POST guard ready is not fresh preflight.",
        "POST guard ready is not final confirmation.",
        "One POST max, no retry, and timeout fail-closed are enforced.",
        "Fresh preflight, final confirmation, and sanitized result remain required.",
        "Unknown, failed, unavailable, timeout, rejected, stale, previous-turn, "
        "and reused states fail closed.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- post_guard_ready: {_bool_text(result.post_guard_ready)}",
        f"- post_guard_mode: {result.post_guard_mode}",
        f"- safe_post_guard_label: {result.safe_post_guard_label}",
        f"- safe_post_guard_status: {result.safe_post_guard_status}",
        (
            "- transport_prerequisite_checked: "
            f"{_bool_text(result.transport_prerequisite_checked)}"
        ),
        (
            "- transport_prerequisite_satisfied: "
            f"{_bool_text(result.transport_prerequisite_satisfied)}"
        ),
        (
            "- transport_controlled_ready: "
            f"{_bool_text(result.transport_controlled_ready)}"
        ),
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
        (
            "- confirmation_phrase_exposure_attempted: "
            f"{_bool_text(result.confirmation_phrase_exposure_attempted)}"
        ),
        (
            "- ledger_state_exposure_attempted: "
            f"{_bool_text(result.ledger_state_exposure_attempted)}"
        ),
        f"- api_call_allowed: {_bool_text(result.api_call_allowed)}",
        f"- api_call_attempted: {_bool_text(result.api_call_attempted)}",
        f"- http_client_present: {_bool_text(result.http_client_present)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- retry_attempted: {_bool_text(result.retry_attempted)}",
        f"- second_post_attempted: {_bool_text(result.second_post_attempted)}",
        (
            "- multiple_post_attempts_attempted: "
            f"{_bool_text(result.multiple_post_attempts_attempted)}"
        ),
        f"- fresh_preflight_executed: {_bool_text(result.fresh_preflight_executed)}",
        (
            "- final_confirmation_received: "
            f"{_bool_text(result.final_confirmation_received)}"
        ),
        "",
        "## Guard",
        f"- one_post_max_enforced: {_bool_text(result.one_post_max_enforced)}",
        f"- no_retry_enforced: {_bool_text(result.no_retry_enforced)}",
        (
            "- timeout_fail_closed_enforced: "
            f"{_bool_text(result.timeout_fail_closed_enforced)}"
        ),
        f"- max_post_attempts_allowed: {result.max_post_attempts_allowed}",
        (
            "- second_post_attempt_blocked: "
            f"{_bool_text(result.second_post_attempt_blocked)}"
        ),
        (
            "- multiple_post_attempts_blocked: "
            f"{_bool_text(result.multiple_post_attempts_blocked)}"
        ),
        (
            "- retry_after_failure_blocked: "
            f"{_bool_text(result.retry_after_failure_blocked)}"
        ),
        (
            "- retry_after_timeout_blocked: "
            f"{_bool_text(result.retry_after_timeout_blocked)}"
        ),
        (
            "- retry_after_unknown_blocked: "
            f"{_bool_text(result.retry_after_unknown_blocked)}"
        ),
        f"- fresh_preflight_required: {_bool_text(result.fresh_preflight_required)}",
        (
            "- final_confirmation_required: "
            f"{_bool_text(result.final_confirmation_required)}"
        ),
        f"- sanitized_result_required: {_bool_text(result.sanitized_result_required)}",
        (
            "- preflight_must_be_current: "
            f"{_bool_text(result.preflight_must_be_current)}"
        ),
        (
            "- confirmation_must_be_new_for_this_step: "
            f"{_bool_text(result.confirmation_must_be_new_for_this_step)}"
        ),
        (
            "- step4_approval_phrase_reuse_blocked: "
            f"{_bool_text(result.step4_approval_phrase_reuse_blocked)}"
        ),
        (
            "- ledger_state_reuse_blocked: "
            f"{_bool_text(result.ledger_state_reuse_blocked)}"
        ),
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines)


def _merge_transport_result(
    snapshot: LiveOrderRealPostGuardControlledInput,
    transport_result: LiveOrderRealTransportControlledResult,
) -> LiveOrderRealPostGuardControlledInput:
    return replace(
        snapshot,
        transport_controlled_ready=transport_result.transport_controlled_ready,
        transport_prerequisite_satisfied=transport_result.transport_controlled_ready,
        safe_transport_label=transport_result.safe_transport_label,
        safe_transport_status=transport_result.safe_transport_status,
        post_guard_unknown=snapshot.post_guard_unknown or transport_result.transport_unknown,
        post_guard_failed=snapshot.post_guard_failed or transport_result.transport_failed,
        post_guard_unavailable=(
            snapshot.post_guard_unavailable or transport_result.transport_unavailable
        ),
        post_guard_timeout=snapshot.post_guard_timeout or transport_result.transport_timeout,
        api_call_allowed=(
            snapshot.api_call_allowed or transport_result.api_call_allowed
        ),
        api_call_attempted=(
            snapshot.api_call_attempted or transport_result.api_call_attempted
        ),
        http_client_present=(
            snapshot.http_client_present or transport_result.http_client_present
        ),
        http_post_executed=(
            snapshot.http_post_executed or transport_result.http_post_executed
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step or transport_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or transport_result.post_executed,
        order_endpoint_called=(
            snapshot.order_endpoint_called or transport_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called or transport_result.live_order_once_called
        ),
        actual_checker_execution_performed=(
            snapshot.actual_checker_execution_performed
            or transport_result.actual_checker_execution_performed
        ),
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or transport_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or transport_result.actual_receipt_handoff_executed
        ),
        fresh_preflight_executed=(
            snapshot.fresh_preflight_executed
            or transport_result.fresh_preflight_executed
        ),
        final_confirmation_received=(
            snapshot.final_confirmation_received
            or transport_result.final_confirmation_received
        ),
    )


def _status_from_input(
    snapshot: LiveOrderRealPostGuardControlledInput,
) -> tuple[LiveOrderRealPostGuardControlledStatus, tuple[str, ...]]:
    if (
        snapshot.post_guard_mode
        != PostGuardControlledMode.POST_GUARD_CONTROLLED_IMPLEMENTATION_ONLY.value
    ):
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_UNKNOWN, (
            "unsupported_post_guard_mode",
        )
    if not snapshot.post_guard_declared or not snapshot.post_guard_requested:
        return PostGuardControlledStatus.POST_GUARD_NOT_READY, (
            "post_guard_not_declared_or_requested",
        )
    if not _transport_prerequisite_satisfied(snapshot):
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_MISSING_TRANSPORT, (
            "transport_prerequisite_missing",
        )
    if snapshot.post_guard_unknown:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_UNKNOWN, (
            "post_guard_unknown",
        )
    if snapshot.post_guard_failed:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_FAILED, (
            "post_guard_failed",
        )
    if snapshot.post_guard_unavailable:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_UNAVAILABLE, (
            "post_guard_unavailable",
        )
    if snapshot.post_guard_timeout:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_TIMEOUT, (
            "post_guard_timeout",
        )
    if snapshot.post_guard_rejected:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_REJECTED, (
            "post_guard_rejected",
        )
    if snapshot.post_guard_stale:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_STALE, (
            "post_guard_stale",
        )
    if snapshot.post_guard_previous_turn:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_PREVIOUS_TURN, (
            "post_guard_previous_turn",
        )
    if snapshot.post_guard_reused:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_REUSED, (
            "post_guard_reused",
        )
    if snapshot.retry_attempted:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_RETRY_ATTEMPTED, (
            "retry_attempted",
        )
    if snapshot.second_post_attempted:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_SECOND_POST_ATTEMPTED, (
            "second_post_attempted",
        )
    if snapshot.multiple_post_attempts_attempted:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_MULTIPLE_POST_ATTEMPTS, (
            "multiple_post_attempts_attempted",
        )
    if snapshot.raw_request_exposure_attempted:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_RAW_REQUEST_EXPOSURE, (
            "raw_request_exposure_attempted",
        )
    if snapshot.raw_response_exposure_attempted:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_RAW_RESPONSE_EXPOSURE, (
            "raw_response_exposure_attempted",
        )
    if _unsafe_exposure_attempted(snapshot):
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_UNSAFE_EXPOSURE, (
            "unsafe_exposure_attempted",
        )
    if (
        snapshot.api_call_allowed
        or snapshot.api_call_attempted
        or snapshot.http_client_present
    ):
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_API_ATTEMPTED, (
            "api_attempted_or_allowed",
        )
    if (
        snapshot.http_post_executed
        or snapshot.post_allowed_this_step
        or snapshot.post_executed
    ):
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_POST_ATTEMPTED, (
            "post_attempted_or_allowed",
        )
    if snapshot.order_endpoint_called:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_ORDER_ENDPOINT, (
            "order_endpoint_called",
        )
    if snapshot.live_order_once_called:
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_LIVE_ORDER_ONCE, (
            "live_order_once_called",
        )
    if (
        snapshot.actual_checker_execution_performed
        or snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
        or snapshot.fresh_preflight_executed
        or snapshot.final_confirmation_received
        or not snapshot.one_post_max_enforced
        or not snapshot.no_retry_enforced
        or not snapshot.timeout_fail_closed_enforced
        or snapshot.max_post_attempts_allowed != 1
        or not snapshot.second_post_attempt_blocked
        or not snapshot.multiple_post_attempts_blocked
        or not snapshot.retry_after_failure_blocked
        or not snapshot.retry_after_timeout_blocked
        or not snapshot.retry_after_unknown_blocked
        or not snapshot.fresh_preflight_required
        or not snapshot.final_confirmation_required
        or not snapshot.sanitized_result_required
        or not snapshot.preflight_must_be_current
        or not snapshot.confirmation_must_be_new_for_this_step
        or not snapshot.step4_approval_phrase_reuse_blocked
        or not snapshot.ledger_state_reuse_blocked
    ):
        return PostGuardControlledStatus.POST_GUARD_BLOCKED_PREFLIGHT_OR_CONFIRMATION, (
            "post_guard_or_final_gate_blocker_missing_or_executed",
        )
    return PostGuardControlledStatus.POST_GUARD_READY_NO_POST, ()


def _blocked_reasons(
    *,
    snapshot: LiveOrderRealPostGuardControlledInput,
    primary_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons = list(primary_reasons)
    if not snapshot.transport_prerequisite_checked:
        reasons.append("transport_prerequisite_not_checked")
    if not snapshot.transport_controlled_ready:
        reasons.append("transport_controlled_not_ready")
    if snapshot.safe_transport_label != SAFE_TRANSPORT_LABEL:
        reasons.append("safe_transport_label_invalid")
    if snapshot.safe_transport_status != _ready_transport_status():
        reasons.append("safe_transport_status_not_ready")
    if snapshot.safe_post_guard_label != SAFE_POST_GUARD_LABEL:
        reasons.append("safe_post_guard_label_invalid")
    if snapshot.credential_value_exposure_attempted:
        reasons.append("credential_value_exposure_attempted")
    if snapshot.signature_value_exposure_attempted:
        reasons.append("signature_value_exposure_attempted")
    if snapshot.headers_value_exposure_attempted:
        reasons.append("headers_value_exposure_attempted")
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
    if snapshot.confirmation_phrase_exposure_attempted:
        reasons.append("confirmation_phrase_exposure_attempted")
    if snapshot.preflight_detail_exposure_attempted:
        reasons.append("preflight_detail_exposure_attempted")
    if snapshot.ledger_state_exposure_attempted:
        reasons.append("ledger_state_exposure_attempted")
    if not snapshot.safe_to_render:
        reasons.append("render_not_safe")
    if not snapshot.safe_to_serialize:
        reasons.append("serialize_not_safe")
    return _dedupe(reasons)


def _build_check_results(
    *,
    snapshot: LiveOrderRealPostGuardControlledInput,
    status: LiveOrderRealPostGuardControlledStatus,
    ready: bool,
    prerequisite_satisfied: bool,
    safe_post_guard_label: str,
) -> tuple[LiveOrderRealPostGuardControlledCheckResult, ...]:
    return (
        LiveOrderRealPostGuardControlledCheckResult(
            name="controlled post guard mode",
            passed=(
                snapshot.post_guard_mode
                == PostGuardControlledMode.POST_GUARD_CONTROLLED_IMPLEMENTATION_ONLY.value
            ),
            sanitized_value=(
                snapshot.post_guard_mode
                if snapshot.post_guard_mode
                == PostGuardControlledMode.POST_GUARD_CONTROLLED_IMPLEMENTATION_ONLY.value
                else UNSUPPORTED_POST_GUARD_LABEL
            ),
            expected="post guard controlled implementation only",
        ),
        LiveOrderRealPostGuardControlledCheckResult(
            name="safe post guard label",
            passed=safe_post_guard_label == SAFE_POST_GUARD_LABEL,
            sanitized_value=safe_post_guard_label,
            expected="fixed safe post guard label",
        ),
        LiveOrderRealPostGuardControlledCheckResult(
            name="transport prerequisite",
            passed=prerequisite_satisfied,
            sanitized_value="ready" if prerequisite_satisfied else "blocked",
            expected="controlled transport ready",
        ),
        LiveOrderRealPostGuardControlledCheckResult(
            name="no api post live_order_once",
            passed=(
                not snapshot.api_call_allowed
                and not snapshot.api_call_attempted
                and not snapshot.http_client_present
                and not snapshot.http_post_executed
                and not snapshot.post_allowed_this_step
                and not snapshot.post_executed
                and not snapshot.order_endpoint_called
                and not snapshot.live_order_once_called
            ),
            sanitized_value="blocked",
            expected="no API no POST no order endpoint no live_order_once",
        ),
        LiveOrderRealPostGuardControlledCheckResult(
            name="one post max no retry timeout fail closed",
            passed=(
                snapshot.one_post_max_enforced
                and snapshot.no_retry_enforced
                and snapshot.timeout_fail_closed_enforced
                and snapshot.max_post_attempts_allowed == 1
                and snapshot.second_post_attempt_blocked
                and snapshot.multiple_post_attempts_blocked
                and snapshot.retry_after_failure_blocked
                and snapshot.retry_after_timeout_blocked
                and snapshot.retry_after_unknown_blocked
            ),
            sanitized_value="enforced",
            expected="one POST max no retry timeout fail-closed",
        ),
        LiveOrderRealPostGuardControlledCheckResult(
            name="final gate blockers",
            passed=(
                snapshot.fresh_preflight_required
                and snapshot.final_confirmation_required
                and snapshot.sanitized_result_required
                and snapshot.preflight_must_be_current
                and snapshot.confirmation_must_be_new_for_this_step
                and snapshot.step4_approval_phrase_reuse_blocked
                and snapshot.ledger_state_reuse_blocked
            ),
            sanitized_value="required",
            expected="fresh preflight final confirmation sanitized result",
        ),
        LiveOrderRealPostGuardControlledCheckResult(
            name="ready is not post permission",
            passed=ready == (status is PostGuardControlledStatus.POST_GUARD_READY_NO_POST),
            sanitized_value=status.value,
            expected="ready no POST",
        ),
    )


def _transport_prerequisite_satisfied(
    snapshot: LiveOrderRealPostGuardControlledInput,
) -> bool:
    return (
        snapshot.transport_prerequisite_checked
        and snapshot.transport_controlled_ready
        and snapshot.transport_prerequisite_satisfied
        and snapshot.safe_transport_label == SAFE_TRANSPORT_LABEL
        and snapshot.safe_transport_status == _ready_transport_status()
    )


def _unsafe_exposure_attempted(
    snapshot: LiveOrderRealPostGuardControlledInput,
) -> bool:
    return (
        snapshot.unsafe_exposure_attempted
        or snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
        or snapshot.request_body_exposure_attempted
        or snapshot.response_body_exposure_attempted
        or snapshot.endpoint_actual_value_exposure_attempted
        or snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.real_id_exposure_attempted
        or snapshot.broker_api_response_exposure_attempted
        or snapshot.confirmation_phrase_exposure_attempted
        or snapshot.preflight_detail_exposure_attempted
        or snapshot.ledger_state_exposure_attempted
        or snapshot.safe_transport_label != SAFE_TRANSPORT_LABEL
        or snapshot.safe_post_guard_label != SAFE_POST_GUARD_LABEL
        or not snapshot.safe_to_render
        or not snapshot.safe_to_serialize
    )


def _validate_result_safety(result: LiveOrderRealPostGuardControlledResult) -> None:
    if result.post_guard_ready and (
        result.api_call_allowed
        or result.api_call_attempted
        or result.http_client_present
        or result.http_post_executed
        or result.post_allowed_this_step
        or result.post_executed
        or result.order_endpoint_called
        or result.live_order_once_called
        or result.retry_attempted
        or result.second_post_attempted
        or result.multiple_post_attempts_attempted
        or result.fresh_preflight_executed
        or result.final_confirmation_received
    ):
        raise LiveVerificationValidationError(
            "post guard ready must not authorize execution",
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
        result.confirmation_phrase_exposure_attempted,
        result.preflight_detail_exposure_attempted,
        result.ledger_state_exposure_attempted,
        result.api_call_allowed,
        result.api_call_attempted,
        result.http_client_present,
        result.http_post_executed,
        result.post_allowed_this_step,
        result.post_executed,
        result.order_endpoint_called,
        result.live_order_once_called,
        result.retry_attempted,
        result.second_post_attempted,
        result.multiple_post_attempts_attempted,
        result.actual_checker_execution_performed,
        result.actual_result_receipt_received,
        result.actual_receipt_handoff_executed,
        result.fresh_preflight_executed,
        result.final_confirmation_received,
    )
    if any(forbidden_flags):
        raise LiveVerificationValidationError(
            "post guard controlled result must sanitize unsafe flags",
        )


def _ready_transport_status() -> str:
    return (
        LiveOrderRealTransportControlledStatus.TRANSPORT_READY_NO_API_NO_POST.value
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
