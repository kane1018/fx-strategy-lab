"""Step 6G sanitized POST result and reconciliation contract.

This module defines a safe result/reconciliation boundary for a future POST
result. It does not receive raw responses, parse broker/API payloads, import
HTTP clients, call APIs, execute HTTP POST, call order endpoints, call
live_order_once, run fresh preflight, run final confirmation, or update ledgers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_post_guard_controlled import (
    SAFE_POST_GUARD_LABEL,
    LiveOrderRealPostGuardControlledResult,
    LiveOrderRealPostGuardControlledStatus,
)

SANITIZED_POST_RESULT_RECOMMENDED_NEXT_STEP = (
    "sanitized_post_result_boundary_review_no_api_no_post"
)
SAFE_POST_RESULT_LABEL = "CONTROLLED_SANITIZED_POST_RESULT_BOUNDARY"
SAFE_RECONCILIATION_LABEL = "CONTROLLED_RECONCILIATION_BOUNDARY"
UNSUPPORTED_SANITIZED_RESULT_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealSanitizedPostResultStatus(str, Enum):
    SANITIZED_RESULT_NOT_READY = "SANITIZED_RESULT_NOT_READY"
    SANITIZED_RESULT_READY_NO_RECEIPT = "SANITIZED_RESULT_READY_NO_RECEIPT"
    SANITIZED_RESULT_BLOCKED_MISSING_POST_GUARD = (
        "SANITIZED_RESULT_BLOCKED_MISSING_POST_GUARD"
    )
    SANITIZED_RESULT_BLOCKED_UNKNOWN = "SANITIZED_RESULT_BLOCKED_UNKNOWN"
    SANITIZED_RESULT_BLOCKED_FAILED = "SANITIZED_RESULT_BLOCKED_FAILED"
    SANITIZED_RESULT_BLOCKED_UNAVAILABLE = "SANITIZED_RESULT_BLOCKED_UNAVAILABLE"
    SANITIZED_RESULT_BLOCKED_TIMEOUT = "SANITIZED_RESULT_BLOCKED_TIMEOUT"
    SANITIZED_RESULT_BLOCKED_REJECTED = "SANITIZED_RESULT_BLOCKED_REJECTED"
    SANITIZED_RESULT_BLOCKED_PARTIAL = "SANITIZED_RESULT_BLOCKED_PARTIAL"
    SANITIZED_RESULT_BLOCKED_AMBIGUOUS = "SANITIZED_RESULT_BLOCKED_AMBIGUOUS"
    SANITIZED_RESULT_BLOCKED_UNMATCHED = "SANITIZED_RESULT_BLOCKED_UNMATCHED"
    SANITIZED_RESULT_BLOCKED_STALE = "SANITIZED_RESULT_BLOCKED_STALE"
    SANITIZED_RESULT_BLOCKED_PREVIOUS_TURN = (
        "SANITIZED_RESULT_BLOCKED_PREVIOUS_TURN"
    )
    SANITIZED_RESULT_BLOCKED_REUSED = "SANITIZED_RESULT_BLOCKED_REUSED"
    SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE = (
        "SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE"
    )
    SANITIZED_RESULT_BLOCKED_RAW_REQUEST_EXPOSURE = (
        "SANITIZED_RESULT_BLOCKED_RAW_REQUEST_EXPOSURE"
    )
    SANITIZED_RESULT_BLOCKED_RAW_RESPONSE_EXPOSURE = (
        "SANITIZED_RESULT_BLOCKED_RAW_RESPONSE_EXPOSURE"
    )
    SANITIZED_RESULT_BLOCKED_BROKER_RESPONSE_EXPOSURE = (
        "SANITIZED_RESULT_BLOCKED_BROKER_RESPONSE_EXPOSURE"
    )
    SANITIZED_RESULT_BLOCKED_API_RESPONSE_EXPOSURE = (
        "SANITIZED_RESULT_BLOCKED_API_RESPONSE_EXPOSURE"
    )
    SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE = (
        "SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE"
    )
    SANITIZED_RESULT_BLOCKED_API_ATTEMPTED = (
        "SANITIZED_RESULT_BLOCKED_API_ATTEMPTED"
    )
    SANITIZED_RESULT_BLOCKED_POST_ATTEMPTED = (
        "SANITIZED_RESULT_BLOCKED_POST_ATTEMPTED"
    )
    SANITIZED_RESULT_BLOCKED_ORDER_ENDPOINT = (
        "SANITIZED_RESULT_BLOCKED_ORDER_ENDPOINT"
    )
    SANITIZED_RESULT_BLOCKED_LIVE_ORDER_ONCE = (
        "SANITIZED_RESULT_BLOCKED_LIVE_ORDER_ONCE"
    )
    SANITIZED_RESULT_BLOCKED_LEDGER_UPDATE = (
        "SANITIZED_RESULT_BLOCKED_LEDGER_UPDATE"
    )
    SANITIZED_RESULT_BLOCKED_ACTUAL_RECEIPT = (
        "SANITIZED_RESULT_BLOCKED_ACTUAL_RECEIPT"
    )
    SANITIZED_RESULT_BLOCKED_PREFLIGHT_OR_CONFIRMATION = (
        "SANITIZED_RESULT_BLOCKED_PREFLIGHT_OR_CONFIRMATION"
    )


class LiveOrderRealSanitizedPostResultMode(str, Enum):
    SANITIZED_POST_RESULT_CONTRACT_ONLY = "SANITIZED_POST_RESULT_CONTRACT_ONLY"


class LiveOrderRealSafePostResultCategory(str, Enum):
    RESULT_NOT_RECEIVED = "RESULT_NOT_RECEIVED"
    RESULT_ACCEPTED_SANITIZED = "RESULT_ACCEPTED_SANITIZED"
    RESULT_REJECTED_SANITIZED = "RESULT_REJECTED_SANITIZED"
    RESULT_UNKNOWN_FAIL_CLOSED = "RESULT_UNKNOWN_FAIL_CLOSED"
    RESULT_TIMEOUT_FAIL_CLOSED = "RESULT_TIMEOUT_FAIL_CLOSED"
    RESULT_UNAVAILABLE_FAIL_CLOSED = "RESULT_UNAVAILABLE_FAIL_CLOSED"
    RESULT_RECONCILIATION_REQUIRED = "RESULT_RECONCILIATION_REQUIRED"


class LiveOrderRealSafeReconciliationStatus(str, Enum):
    RECONCILIATION_READY_NO_RECEIPT_HANDOFF = (
        "RECONCILIATION_READY_NO_RECEIPT_HANDOFF"
    )
    RECONCILIATION_BLOCKED_NOT_READY = "RECONCILIATION_BLOCKED_NOT_READY"


SanitizedPostResultStatus = LiveOrderRealSanitizedPostResultStatus
SanitizedPostResultMode = LiveOrderRealSanitizedPostResultMode
SafePostResultCategory = LiveOrderRealSafePostResultCategory
SafeReconciliationStatus = LiveOrderRealSafeReconciliationStatus


@dataclass(frozen=True)
class LiveOrderRealSanitizedPostResultInput:
    result_mode: str = (
        SanitizedPostResultMode.SANITIZED_POST_RESULT_CONTRACT_ONLY.value
    )
    result_contract_declared: bool = True
    result_contract_requested: bool = True
    post_guard_prerequisite_checked: bool = True
    post_guard_controlled_ready: bool = True
    post_guard_prerequisite_satisfied: bool = True
    safe_post_guard_label: str = SAFE_POST_GUARD_LABEL
    safe_post_guard_status: str = (
        LiveOrderRealPostGuardControlledStatus.POST_GUARD_READY_NO_POST.value
    )
    safe_post_result_label: str = SAFE_POST_RESULT_LABEL
    safe_reconciliation_label: str = SAFE_RECONCILIATION_LABEL
    result_unknown: bool = False
    result_failed: bool = False
    result_unavailable: bool = False
    result_timeout: bool = False
    result_rejected: bool = False
    result_partial: bool = False
    result_ambiguous: bool = False
    result_unmatched: bool = False
    result_stale: bool = False
    result_previous_turn: bool = False
    result_reused: bool = False
    unsafe_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    raw_request_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    request_body_exposure_attempted: bool = False
    response_body_exposure_attempted: bool = False
    broker_response_exposure_attempted: bool = False
    api_response_exposure_attempted: bool = False
    endpoint_actual_value_exposure_attempted: bool = False
    account_id_exposure_attempted: bool = False
    order_id_exposure_attempted: bool = False
    transaction_id_exposure_attempted: bool = False
    position_id_exposure_attempted: bool = False
    trade_id_exposure_attempted: bool = False
    real_id_exposure_attempted: bool = False
    confirmation_phrase_exposure_attempted: bool = False
    preflight_detail_exposure_attempted: bool = False
    ledger_state_exposure_attempted: bool = False
    raw_request_stored: bool = False
    raw_response_stored: bool = False
    broker_response_exposed: bool = False
    api_response_exposed: bool = False
    real_id_exposed: bool = False
    api_call_allowed: bool = False
    api_call_attempted: bool = False
    http_client_present: bool = False
    http_post_executed: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    actual_checker_execution_performed: bool = False
    actual_result_receipt_received: bool = False
    actual_receipt_handoff_executed: bool = False
    actual_receipt_handoff_allowed: bool = False
    ledger_update_allowed: bool = False
    ledger_update_attempted: bool = False
    attempt_counter_persisted: bool = False
    fresh_preflight_executed: bool = False
    final_confirmation_received: bool = False
    raw_request_blocked: bool = True
    raw_response_blocked: bool = True
    broker_api_response_blocked: bool = True
    real_id_blocked: bool = True
    credential_signature_headers_blocked: bool = True
    fresh_preflight_required: bool = True
    final_confirmation_required: bool = True
    ledger_design_required: bool = True
    attempt_counter_design_required: bool = True
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("result_mode", self.result_mode)
        _require_non_empty("safe_post_guard_label", self.safe_post_guard_label)
        _require_non_empty("safe_post_guard_status", self.safe_post_guard_status)
        _require_non_empty("safe_post_result_label", self.safe_post_result_label)
        _require_non_empty("safe_reconciliation_label", self.safe_reconciliation_label)
        _validate_bool_fields(self, _SANITIZED_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealSanitizedPostResultCheckResult:
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
class LiveOrderRealSanitizedPostResultResult:
    status: LiveOrderRealSanitizedPostResultStatus
    sanitized_post_result_ready: bool
    reconciliation_ready: bool
    result_mode: str
    result_contract_declared: bool
    result_contract_requested: bool
    post_guard_prerequisite_checked: bool
    post_guard_prerequisite_satisfied: bool
    post_guard_controlled_ready: bool
    safe_post_guard_label: str
    safe_post_guard_status: str
    safe_post_result_label: str
    safe_post_result_status: str
    safe_result_category: str
    safe_reconciliation_label: str
    safe_reconciliation_status: str
    result_unknown: bool
    result_failed: bool
    result_unavailable: bool
    result_timeout: bool
    result_rejected: bool
    result_partial: bool
    result_ambiguous: bool
    result_unmatched: bool
    result_stale: bool
    result_previous_turn: bool
    result_reused: bool
    unsafe_exposure_attempted: bool
    credential_value_exposure_attempted: bool
    signature_value_exposure_attempted: bool
    headers_value_exposure_attempted: bool
    raw_request_exposure_attempted: bool
    raw_response_exposure_attempted: bool
    request_body_exposure_attempted: bool
    response_body_exposure_attempted: bool
    broker_response_exposure_attempted: bool
    api_response_exposure_attempted: bool
    endpoint_actual_value_exposure_attempted: bool
    account_id_exposure_attempted: bool
    order_id_exposure_attempted: bool
    transaction_id_exposure_attempted: bool
    position_id_exposure_attempted: bool
    trade_id_exposure_attempted: bool
    real_id_exposure_attempted: bool
    confirmation_phrase_exposure_attempted: bool
    preflight_detail_exposure_attempted: bool
    ledger_state_exposure_attempted: bool
    raw_request_stored: bool
    raw_response_stored: bool
    broker_response_exposed: bool
    api_response_exposed: bool
    real_id_exposed: bool
    api_call_allowed: bool
    api_call_attempted: bool
    http_client_present: bool
    http_post_executed: bool
    post_allowed_this_step: bool
    post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    actual_checker_execution_performed: bool
    actual_result_receipt_received: bool
    actual_receipt_handoff_executed: bool
    actual_receipt_handoff_allowed: bool
    ledger_update_allowed: bool
    ledger_update_attempted: bool
    attempt_counter_persisted: bool
    fresh_preflight_executed: bool
    final_confirmation_received: bool
    raw_request_blocked: bool
    raw_response_blocked: bool
    broker_api_response_blocked: bool
    real_id_blocked: bool
    credential_signature_headers_blocked: bool
    fresh_preflight_required: bool
    final_confirmation_required: bool
    ledger_design_required: bool
    attempt_counter_design_required: bool
    safe_to_render: bool
    safe_to_serialize: bool
    check_results: tuple[LiveOrderRealSanitizedPostResultCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealSanitizedPostResultStatus):
            raise LiveVerificationValidationError(
                "status must be sanitized post result status",
            )
        _require_non_empty("result_mode", self.result_mode)
        _require_non_empty("safe_post_guard_label", self.safe_post_guard_label)
        _require_non_empty("safe_post_guard_status", self.safe_post_guard_status)
        _require_non_empty("safe_post_result_label", self.safe_post_result_label)
        _require_non_empty("safe_post_result_status", self.safe_post_result_status)
        _require_non_empty("safe_result_category", self.safe_result_category)
        _require_non_empty("safe_reconciliation_label", self.safe_reconciliation_label)
        _require_non_empty(
            "safe_reconciliation_status",
            self.safe_reconciliation_status,
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(self, _SANITIZED_RESULT_BOOL_FIELDS)
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_sanitized_post_result(
    *,
    input_snapshot: LiveOrderRealSanitizedPostResultInput | None = None,
    post_guard_result: LiveOrderRealPostGuardControlledResult | None = None,
) -> LiveOrderRealSanitizedPostResultResult:
    """Build a safe result contract without API, POST, raw response, or ledger I/O."""
    snapshot = input_snapshot or LiveOrderRealSanitizedPostResultInput()
    if post_guard_result is not None:
        snapshot = _merge_post_guard_result(snapshot, post_guard_result)

    status, primary_reasons = _status_from_input(snapshot)
    ready = status is SanitizedPostResultStatus.SANITIZED_RESULT_READY_NO_RECEIPT
    prerequisite_satisfied = _post_guard_prerequisite_satisfied(snapshot)
    category = _category_from_status(status)
    reconciliation_status = (
        SafeReconciliationStatus.RECONCILIATION_READY_NO_RECEIPT_HANDOFF.value
        if ready
        else SafeReconciliationStatus.RECONCILIATION_BLOCKED_NOT_READY.value
    )
    reconciliation_ready = ready
    safe_mode = (
        snapshot.result_mode
        if snapshot.result_mode
        == SanitizedPostResultMode.SANITIZED_POST_RESULT_CONTRACT_ONLY.value
        else UNSUPPORTED_SANITIZED_RESULT_LABEL
    )
    safe_post_guard_label = (
        snapshot.safe_post_guard_label
        if snapshot.safe_post_guard_label == SAFE_POST_GUARD_LABEL
        else UNSUPPORTED_SANITIZED_RESULT_LABEL
    )
    safe_post_result_label = (
        snapshot.safe_post_result_label
        if snapshot.safe_post_result_label == SAFE_POST_RESULT_LABEL
        else UNSUPPORTED_SANITIZED_RESULT_LABEL
    )
    safe_reconciliation_label = (
        snapshot.safe_reconciliation_label
        if snapshot.safe_reconciliation_label == SAFE_RECONCILIATION_LABEL
        else UNSUPPORTED_SANITIZED_RESULT_LABEL
    )
    blocked_reasons = _blocked_reasons(
        snapshot=snapshot,
        primary_reasons=primary_reasons,
    )

    return LiveOrderRealSanitizedPostResultResult(
        status=status,
        sanitized_post_result_ready=ready,
        reconciliation_ready=reconciliation_ready,
        result_mode=safe_mode,
        result_contract_declared=snapshot.result_contract_declared,
        result_contract_requested=snapshot.result_contract_requested,
        post_guard_prerequisite_checked=snapshot.post_guard_prerequisite_checked,
        post_guard_prerequisite_satisfied=prerequisite_satisfied,
        post_guard_controlled_ready=snapshot.post_guard_controlled_ready,
        safe_post_guard_label=safe_post_guard_label,
        safe_post_guard_status=snapshot.safe_post_guard_status,
        safe_post_result_label=safe_post_result_label,
        safe_post_result_status=status.value,
        safe_result_category=category.value,
        safe_reconciliation_label=safe_reconciliation_label,
        safe_reconciliation_status=reconciliation_status,
        result_unknown=snapshot.result_unknown,
        result_failed=snapshot.result_failed,
        result_unavailable=snapshot.result_unavailable,
        result_timeout=snapshot.result_timeout,
        result_rejected=snapshot.result_rejected,
        result_partial=snapshot.result_partial,
        result_ambiguous=snapshot.result_ambiguous,
        result_unmatched=snapshot.result_unmatched,
        result_stale=snapshot.result_stale,
        result_previous_turn=snapshot.result_previous_turn,
        result_reused=snapshot.result_reused,
        unsafe_exposure_attempted=False,
        credential_value_exposure_attempted=False,
        signature_value_exposure_attempted=False,
        headers_value_exposure_attempted=False,
        raw_request_exposure_attempted=False,
        raw_response_exposure_attempted=False,
        request_body_exposure_attempted=False,
        response_body_exposure_attempted=False,
        broker_response_exposure_attempted=False,
        api_response_exposure_attempted=False,
        endpoint_actual_value_exposure_attempted=False,
        account_id_exposure_attempted=False,
        order_id_exposure_attempted=False,
        transaction_id_exposure_attempted=False,
        position_id_exposure_attempted=False,
        trade_id_exposure_attempted=False,
        real_id_exposure_attempted=False,
        confirmation_phrase_exposure_attempted=False,
        preflight_detail_exposure_attempted=False,
        ledger_state_exposure_attempted=False,
        raw_request_stored=False,
        raw_response_stored=False,
        broker_response_exposed=False,
        api_response_exposed=False,
        real_id_exposed=False,
        api_call_allowed=False,
        api_call_attempted=False,
        http_client_present=False,
        http_post_executed=False,
        post_allowed_this_step=False,
        post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        actual_checker_execution_performed=False,
        actual_result_receipt_received=False,
        actual_receipt_handoff_executed=False,
        actual_receipt_handoff_allowed=False,
        ledger_update_allowed=False,
        ledger_update_attempted=False,
        attempt_counter_persisted=False,
        fresh_preflight_executed=False,
        final_confirmation_received=False,
        raw_request_blocked=snapshot.raw_request_blocked,
        raw_response_blocked=snapshot.raw_response_blocked,
        broker_api_response_blocked=snapshot.broker_api_response_blocked,
        real_id_blocked=snapshot.real_id_blocked,
        credential_signature_headers_blocked=(
            snapshot.credential_signature_headers_blocked
        ),
        fresh_preflight_required=snapshot.fresh_preflight_required,
        final_confirmation_required=snapshot.final_confirmation_required,
        ledger_design_required=snapshot.ledger_design_required,
        attempt_counter_design_required=snapshot.attempt_counter_design_required,
        safe_to_render=True,
        safe_to_serialize=True,
        check_results=_build_check_results(
            snapshot=snapshot,
            status=status,
            ready=ready,
            prerequisite_satisfied=prerequisite_satisfied,
            safe_post_result_label=safe_post_result_label,
            safe_reconciliation_label=safe_reconciliation_label,
        ),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            SANITIZED_POST_RESULT_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_sanitized_post_result_blockers_no_api_no_post"
        ),
    )


def render_live_order_real_sanitized_post_result_markdown(
    result: LiveOrderRealSanitizedPostResultResult,
) -> str:
    """Render a safe sanitized result/reconciliation summary only."""
    lines = [
        "# Step 6G Sanitized POST Result Contract",
        "",
        "This is a sanitized POST result and reconciliation contract only.",
        "This result contains safe labels, statuses, booleans, and categories.",
        "This result does not execute API calls.",
        "This result does not execute HTTP POST.",
        "This result does not call order endpoints.",
        "This result does not call live_order_once.",
        "This result does not create or store raw requests.",
        "This result does not receive or store raw responses.",
        "This result does not expose broker or API response values.",
        "This result does not expose credential, signature, or headers values.",
        "This result does not expose real, account, order, or transaction IDs.",
        "This result does not expose confirmation phrase or ledger state values.",
        "Sanitized result ready does not allow POST.",
        "Reconciliation ready does not allow ledger updates or receipt handoff.",
        "Fresh preflight and final confirmation remain required later.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- sanitized_post_result_ready: "
            f"{_bool_text(result.sanitized_post_result_ready)}"
        ),
        f"- reconciliation_ready: {_bool_text(result.reconciliation_ready)}",
        f"- result_mode: {result.result_mode}",
        f"- safe_post_result_label: {result.safe_post_result_label}",
        f"- safe_post_result_status: {result.safe_post_result_status}",
        f"- safe_result_category: {result.safe_result_category}",
        f"- safe_reconciliation_label: {result.safe_reconciliation_label}",
        f"- safe_reconciliation_status: {result.safe_reconciliation_status}",
        "",
        "## Safety",
        f"- raw_request_stored: {_bool_text(result.raw_request_stored)}",
        f"- raw_response_stored: {_bool_text(result.raw_response_stored)}",
        (
            "- broker_response_exposed: "
            f"{_bool_text(result.broker_response_exposed)}"
        ),
        f"- api_response_exposed: {_bool_text(result.api_response_exposed)}",
        f"- real_id_exposed: {_bool_text(result.real_id_exposed)}",
        f"- api_call_allowed: {_bool_text(result.api_call_allowed)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- ledger_update_allowed: {_bool_text(result.ledger_update_allowed)}",
        (
            "- actual_receipt_handoff_allowed: "
            f"{_bool_text(result.actual_receipt_handoff_allowed)}"
        ),
        (
            "- actual_result_receipt_received: "
            f"{_bool_text(result.actual_result_receipt_received)}"
        ),
        (
            "- actual_receipt_handoff_executed: "
            f"{_bool_text(result.actual_receipt_handoff_executed)}"
        ),
        f"- fresh_preflight_executed: {_bool_text(result.fresh_preflight_executed)}",
        (
            "- final_confirmation_received: "
            f"{_bool_text(result.final_confirmation_received)}"
        ),
        f"- raw_request_blocked: {_bool_text(result.raw_request_blocked)}",
        f"- raw_response_blocked: {_bool_text(result.raw_response_blocked)}",
        (
            "- broker_api_response_blocked: "
            f"{_bool_text(result.broker_api_response_blocked)}"
        ),
        f"- real_id_blocked: {_bool_text(result.real_id_blocked)}",
        (
            "- credential_signature_headers_blocked: "
            f"{_bool_text(result.credential_signature_headers_blocked)}"
        ),
        f"- fresh_preflight_required: {_bool_text(result.fresh_preflight_required)}",
        (
            "- final_confirmation_required: "
            f"{_bool_text(result.final_confirmation_required)}"
        ),
        f"- ledger_design_required: {_bool_text(result.ledger_design_required)}",
        (
            "- attempt_counter_design_required: "
            f"{_bool_text(result.attempt_counter_design_required)}"
        ),
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines)


def _merge_post_guard_result(
    snapshot: LiveOrderRealSanitizedPostResultInput,
    post_guard_result: LiveOrderRealPostGuardControlledResult,
) -> LiveOrderRealSanitizedPostResultInput:
    return replace(
        snapshot,
        post_guard_controlled_ready=post_guard_result.post_guard_ready,
        post_guard_prerequisite_satisfied=post_guard_result.post_guard_ready,
        safe_post_guard_label=post_guard_result.safe_post_guard_label,
        safe_post_guard_status=post_guard_result.safe_post_guard_status,
        result_unknown=snapshot.result_unknown or post_guard_result.post_guard_unknown,
        result_failed=snapshot.result_failed or post_guard_result.post_guard_failed,
        result_unavailable=(
            snapshot.result_unavailable or post_guard_result.post_guard_unavailable
        ),
        result_timeout=snapshot.result_timeout or post_guard_result.post_guard_timeout,
        result_rejected=(
            snapshot.result_rejected or post_guard_result.post_guard_rejected
        ),
        result_stale=snapshot.result_stale or post_guard_result.post_guard_stale,
        result_previous_turn=(
            snapshot.result_previous_turn or post_guard_result.post_guard_previous_turn
        ),
        result_reused=snapshot.result_reused or post_guard_result.post_guard_reused,
        api_call_allowed=(
            snapshot.api_call_allowed or post_guard_result.api_call_allowed
        ),
        api_call_attempted=(
            snapshot.api_call_attempted or post_guard_result.api_call_attempted
        ),
        http_client_present=(
            snapshot.http_client_present or post_guard_result.http_client_present
        ),
        http_post_executed=(
            snapshot.http_post_executed or post_guard_result.http_post_executed
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step or post_guard_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or post_guard_result.post_executed,
        order_endpoint_called=(
            snapshot.order_endpoint_called or post_guard_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called or post_guard_result.live_order_once_called
        ),
        actual_checker_execution_performed=(
            snapshot.actual_checker_execution_performed
            or post_guard_result.actual_checker_execution_performed
        ),
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or post_guard_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or post_guard_result.actual_receipt_handoff_executed
        ),
        fresh_preflight_executed=(
            snapshot.fresh_preflight_executed
            or post_guard_result.fresh_preflight_executed
        ),
        final_confirmation_received=(
            snapshot.final_confirmation_received
            or post_guard_result.final_confirmation_received
        ),
    )


def _status_from_input(
    snapshot: LiveOrderRealSanitizedPostResultInput,
) -> tuple[LiveOrderRealSanitizedPostResultStatus, tuple[str, ...]]:
    if (
        snapshot.result_mode
        != SanitizedPostResultMode.SANITIZED_POST_RESULT_CONTRACT_ONLY.value
    ):
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_UNKNOWN, (
            "unsupported_sanitized_result_mode",
        )
    if not snapshot.result_contract_declared or not snapshot.result_contract_requested:
        return SanitizedPostResultStatus.SANITIZED_RESULT_NOT_READY, (
            "sanitized_result_not_declared_or_requested",
        )
    if not _post_guard_prerequisite_satisfied(snapshot):
        return (
            SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_MISSING_POST_GUARD,
            ("post_guard_prerequisite_missing",),
        )
    if snapshot.result_unknown:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_UNKNOWN, (
            "result_unknown",
        )
    if snapshot.result_failed:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_FAILED, (
            "result_failed",
        )
    if snapshot.result_unavailable:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_UNAVAILABLE, (
            "result_unavailable",
        )
    if snapshot.result_timeout:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_TIMEOUT, (
            "result_timeout",
        )
    if snapshot.result_rejected:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_REJECTED, (
            "result_rejected",
        )
    if snapshot.result_partial:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_PARTIAL, (
            "result_partial",
        )
    if snapshot.result_ambiguous:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_AMBIGUOUS, (
            "result_ambiguous",
        )
    if snapshot.result_unmatched:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_UNMATCHED, (
            "result_unmatched",
        )
    if snapshot.result_stale:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_STALE, (
            "result_stale",
        )
    if snapshot.result_previous_turn:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_PREVIOUS_TURN, (
            "result_previous_turn",
        )
    if snapshot.result_reused:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_REUSED, (
            "result_reused",
        )
    if snapshot.raw_request_exposure_attempted or snapshot.raw_request_stored:
        return (
            SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_RAW_REQUEST_EXPOSURE,
            ("raw_request_exposure_or_storage_attempted",),
        )
    if snapshot.raw_response_exposure_attempted or snapshot.raw_response_stored:
        return (
            SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_RAW_RESPONSE_EXPOSURE,
            ("raw_response_exposure_or_storage_attempted",),
        )
    if snapshot.broker_response_exposure_attempted or snapshot.broker_response_exposed:
        return (
            SanitizedPostResultStatus
            .SANITIZED_RESULT_BLOCKED_BROKER_RESPONSE_EXPOSURE,
            ("broker_response_exposure_attempted",),
        )
    if snapshot.api_response_exposure_attempted or snapshot.api_response_exposed:
        return (
            SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_API_RESPONSE_EXPOSURE,
            ("api_response_exposure_attempted",),
        )
    if _identifier_exposure_attempted(snapshot):
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE, (
            "identifier_exposure_attempted",
        )
    if _unsafe_exposure_attempted(snapshot):
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_UNSAFE_EXPOSURE, (
            "unsafe_exposure_attempted",
        )
    if (
        snapshot.api_call_allowed
        or snapshot.api_call_attempted
        or snapshot.http_client_present
    ):
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_API_ATTEMPTED, (
            "api_attempted_or_allowed",
        )
    if (
        snapshot.http_post_executed
        or snapshot.post_allowed_this_step
        or snapshot.post_executed
    ):
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_POST_ATTEMPTED, (
            "post_attempted_or_allowed",
        )
    if snapshot.order_endpoint_called:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_ORDER_ENDPOINT, (
            "order_endpoint_called",
        )
    if snapshot.live_order_once_called:
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_LIVE_ORDER_ONCE, (
            "live_order_once_called",
        )
    if (
        snapshot.ledger_update_allowed
        or snapshot.ledger_update_attempted
        or snapshot.attempt_counter_persisted
    ):
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_LEDGER_UPDATE, (
            "ledger_update_or_attempt_counter_attempted",
        )
    if (
        snapshot.actual_checker_execution_performed
        or snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
        or snapshot.actual_receipt_handoff_allowed
    ):
        return SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_ACTUAL_RECEIPT, (
            "actual_receipt_or_handoff_attempted",
        )
    if (
        snapshot.fresh_preflight_executed
        or snapshot.final_confirmation_received
        or not snapshot.raw_request_blocked
        or not snapshot.raw_response_blocked
        or not snapshot.broker_api_response_blocked
        or not snapshot.real_id_blocked
        or not snapshot.credential_signature_headers_blocked
        or not snapshot.fresh_preflight_required
        or not snapshot.final_confirmation_required
        or not snapshot.ledger_design_required
        or not snapshot.attempt_counter_design_required
    ):
        return (
            SanitizedPostResultStatus
            .SANITIZED_RESULT_BLOCKED_PREFLIGHT_OR_CONFIRMATION,
            ("sanitized_result_final_gate_blocker_missing_or_executed",),
        )
    return SanitizedPostResultStatus.SANITIZED_RESULT_READY_NO_RECEIPT, ()


def _category_from_status(
    status: LiveOrderRealSanitizedPostResultStatus,
) -> LiveOrderRealSafePostResultCategory:
    if status is SanitizedPostResultStatus.SANITIZED_RESULT_READY_NO_RECEIPT:
        return SafePostResultCategory.RESULT_NOT_RECEIVED
    if status is SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_REJECTED:
        return SafePostResultCategory.RESULT_REJECTED_SANITIZED
    if status is SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_TIMEOUT:
        return SafePostResultCategory.RESULT_TIMEOUT_FAIL_CLOSED
    if status is SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_UNAVAILABLE:
        return SafePostResultCategory.RESULT_UNAVAILABLE_FAIL_CLOSED
    if status in {
        SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_RAW_REQUEST_EXPOSURE,
        SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_RAW_RESPONSE_EXPOSURE,
        SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_BROKER_RESPONSE_EXPOSURE,
        SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_API_RESPONSE_EXPOSURE,
        SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_REAL_ID_EXPOSURE,
        SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_LEDGER_UPDATE,
        SanitizedPostResultStatus.SANITIZED_RESULT_BLOCKED_ACTUAL_RECEIPT,
    }:
        return SafePostResultCategory.RESULT_RECONCILIATION_REQUIRED
    return SafePostResultCategory.RESULT_UNKNOWN_FAIL_CLOSED


def _blocked_reasons(
    *,
    snapshot: LiveOrderRealSanitizedPostResultInput,
    primary_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons = list(primary_reasons)
    if not snapshot.post_guard_prerequisite_checked:
        reasons.append("post_guard_prerequisite_not_checked")
    if not snapshot.post_guard_controlled_ready:
        reasons.append("post_guard_controlled_not_ready")
    if snapshot.safe_post_guard_label != SAFE_POST_GUARD_LABEL:
        reasons.append("safe_post_guard_label_invalid")
    if snapshot.safe_post_guard_status != _ready_post_guard_status():
        reasons.append("safe_post_guard_status_not_ready")
    if snapshot.safe_post_result_label != SAFE_POST_RESULT_LABEL:
        reasons.append("safe_post_result_label_invalid")
    if snapshot.safe_reconciliation_label != SAFE_RECONCILIATION_LABEL:
        reasons.append("safe_reconciliation_label_invalid")
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
    if snapshot.transaction_id_exposure_attempted:
        reasons.append("transaction_id_exposure_attempted")
    if snapshot.position_id_exposure_attempted:
        reasons.append("position_id_exposure_attempted")
    if snapshot.trade_id_exposure_attempted:
        reasons.append("trade_id_exposure_attempted")
    if snapshot.real_id_exposure_attempted:
        reasons.append("real_id_exposure_attempted")
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
    snapshot: LiveOrderRealSanitizedPostResultInput,
    status: LiveOrderRealSanitizedPostResultStatus,
    ready: bool,
    prerequisite_satisfied: bool,
    safe_post_result_label: str,
    safe_reconciliation_label: str,
) -> tuple[LiveOrderRealSanitizedPostResultCheckResult, ...]:
    return (
        LiveOrderRealSanitizedPostResultCheckResult(
            name="sanitized result contract mode",
            passed=(
                snapshot.result_mode
                == SanitizedPostResultMode.SANITIZED_POST_RESULT_CONTRACT_ONLY.value
            ),
            sanitized_value=(
                snapshot.result_mode
                if snapshot.result_mode
                == SanitizedPostResultMode.SANITIZED_POST_RESULT_CONTRACT_ONLY.value
                else UNSUPPORTED_SANITIZED_RESULT_LABEL
            ),
            expected="sanitized POST result contract only",
        ),
        LiveOrderRealSanitizedPostResultCheckResult(
            name="safe sanitized result label",
            passed=safe_post_result_label == SAFE_POST_RESULT_LABEL,
            sanitized_value=safe_post_result_label,
            expected="fixed safe result label",
        ),
        LiveOrderRealSanitizedPostResultCheckResult(
            name="safe reconciliation label",
            passed=safe_reconciliation_label == SAFE_RECONCILIATION_LABEL,
            sanitized_value=safe_reconciliation_label,
            expected="fixed safe reconciliation label",
        ),
        LiveOrderRealSanitizedPostResultCheckResult(
            name="post guard prerequisite",
            passed=prerequisite_satisfied,
            sanitized_value="ready" if prerequisite_satisfied else "blocked",
            expected="controlled POST guard ready",
        ),
        LiveOrderRealSanitizedPostResultCheckResult(
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
        LiveOrderRealSanitizedPostResultCheckResult(
            name="no raw broker api response or real id",
            passed=(
                not snapshot.raw_request_stored
                and not snapshot.raw_response_stored
                and not snapshot.broker_response_exposed
                and not snapshot.api_response_exposed
                and not snapshot.real_id_exposed
                and snapshot.raw_request_blocked
                and snapshot.raw_response_blocked
                and snapshot.broker_api_response_blocked
                and snapshot.real_id_blocked
            ),
            sanitized_value="blocked",
            expected="no raw request response broker API response or real ID",
        ),
        LiveOrderRealSanitizedPostResultCheckResult(
            name="reconciliation is not ledger or receipt handoff",
            passed=(
                not snapshot.ledger_update_allowed
                and not snapshot.ledger_update_attempted
                and not snapshot.attempt_counter_persisted
                and not snapshot.actual_receipt_handoff_allowed
                and not snapshot.actual_result_receipt_received
                and not snapshot.actual_receipt_handoff_executed
            ),
            sanitized_value="blocked",
            expected="no ledger update no actual receipt handoff",
        ),
        LiveOrderRealSanitizedPostResultCheckResult(
            name="ready is not post permission",
            passed=ready
            == (status is SanitizedPostResultStatus.SANITIZED_RESULT_READY_NO_RECEIPT),
            sanitized_value=status.value,
            expected="ready no POST no receipt",
        ),
    )


def _post_guard_prerequisite_satisfied(
    snapshot: LiveOrderRealSanitizedPostResultInput,
) -> bool:
    return (
        snapshot.post_guard_prerequisite_checked
        and snapshot.post_guard_controlled_ready
        and snapshot.post_guard_prerequisite_satisfied
        and snapshot.safe_post_guard_label == SAFE_POST_GUARD_LABEL
        and snapshot.safe_post_guard_status == _ready_post_guard_status()
    )


def _identifier_exposure_attempted(
    snapshot: LiveOrderRealSanitizedPostResultInput,
) -> bool:
    return (
        snapshot.endpoint_actual_value_exposure_attempted
        or snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.position_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
        or snapshot.real_id_exposure_attempted
        or snapshot.real_id_exposed
    )


def _unsafe_exposure_attempted(
    snapshot: LiveOrderRealSanitizedPostResultInput,
) -> bool:
    return (
        snapshot.unsafe_exposure_attempted
        or snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
        or snapshot.request_body_exposure_attempted
        or snapshot.response_body_exposure_attempted
        or snapshot.confirmation_phrase_exposure_attempted
        or snapshot.preflight_detail_exposure_attempted
        or snapshot.ledger_state_exposure_attempted
        or snapshot.safe_post_guard_label != SAFE_POST_GUARD_LABEL
        or snapshot.safe_post_result_label != SAFE_POST_RESULT_LABEL
        or snapshot.safe_reconciliation_label != SAFE_RECONCILIATION_LABEL
        or not snapshot.safe_to_render
        or not snapshot.safe_to_serialize
    )


def _validate_result_safety(result: LiveOrderRealSanitizedPostResultResult) -> None:
    if result.sanitized_post_result_ready and (
        result.api_call_allowed
        or result.api_call_attempted
        or result.http_client_present
        or result.http_post_executed
        or result.post_allowed_this_step
        or result.post_executed
        or result.order_endpoint_called
        or result.live_order_once_called
        or result.ledger_update_allowed
        or result.actual_receipt_handoff_allowed
        or result.actual_result_receipt_received
        or result.actual_receipt_handoff_executed
        or result.fresh_preflight_executed
        or result.final_confirmation_received
    ):
        raise LiveVerificationValidationError(
            "sanitized result ready must not authorize execution",
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
        result.broker_response_exposure_attempted,
        result.api_response_exposure_attempted,
        result.endpoint_actual_value_exposure_attempted,
        result.account_id_exposure_attempted,
        result.order_id_exposure_attempted,
        result.transaction_id_exposure_attempted,
        result.position_id_exposure_attempted,
        result.trade_id_exposure_attempted,
        result.real_id_exposure_attempted,
        result.confirmation_phrase_exposure_attempted,
        result.preflight_detail_exposure_attempted,
        result.ledger_state_exposure_attempted,
        result.raw_request_stored,
        result.raw_response_stored,
        result.broker_response_exposed,
        result.api_response_exposed,
        result.real_id_exposed,
        result.api_call_allowed,
        result.api_call_attempted,
        result.http_client_present,
        result.http_post_executed,
        result.post_allowed_this_step,
        result.post_executed,
        result.order_endpoint_called,
        result.live_order_once_called,
        result.actual_checker_execution_performed,
        result.actual_result_receipt_received,
        result.actual_receipt_handoff_executed,
        result.actual_receipt_handoff_allowed,
        result.ledger_update_allowed,
        result.ledger_update_attempted,
        result.attempt_counter_persisted,
        result.fresh_preflight_executed,
        result.final_confirmation_received,
    )
    if any(forbidden_flags):
        raise LiveVerificationValidationError(
            "sanitized post result must sanitize unsafe flags",
        )


def _ready_post_guard_status() -> str:
    return LiveOrderRealPostGuardControlledStatus.POST_GUARD_READY_NO_POST.value


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return tuple(deduped)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _require_non_empty(name: str, value: str) -> None:
    if not value:
        raise LiveVerificationValidationError(f"{name} must be non-empty")


def _validate_bool_fields(instance: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(instance, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


_SANITIZED_INPUT_BOOL_FIELDS = (
    "result_contract_declared",
    "result_contract_requested",
    "post_guard_prerequisite_checked",
    "post_guard_controlled_ready",
    "post_guard_prerequisite_satisfied",
    "result_unknown",
    "result_failed",
    "result_unavailable",
    "result_timeout",
    "result_rejected",
    "result_partial",
    "result_ambiguous",
    "result_unmatched",
    "result_stale",
    "result_previous_turn",
    "result_reused",
    "unsafe_exposure_attempted",
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
    "raw_request_exposure_attempted",
    "raw_response_exposure_attempted",
    "request_body_exposure_attempted",
    "response_body_exposure_attempted",
    "broker_response_exposure_attempted",
    "api_response_exposure_attempted",
    "endpoint_actual_value_exposure_attempted",
    "account_id_exposure_attempted",
    "order_id_exposure_attempted",
    "transaction_id_exposure_attempted",
    "position_id_exposure_attempted",
    "trade_id_exposure_attempted",
    "real_id_exposure_attempted",
    "confirmation_phrase_exposure_attempted",
    "preflight_detail_exposure_attempted",
    "ledger_state_exposure_attempted",
    "raw_request_stored",
    "raw_response_stored",
    "broker_response_exposed",
    "api_response_exposed",
    "real_id_exposed",
    "api_call_allowed",
    "api_call_attempted",
    "http_client_present",
    "http_post_executed",
    "post_allowed_this_step",
    "post_executed",
    "order_endpoint_called",
    "live_order_once_called",
    "actual_checker_execution_performed",
    "actual_result_receipt_received",
    "actual_receipt_handoff_executed",
    "actual_receipt_handoff_allowed",
    "ledger_update_allowed",
    "ledger_update_attempted",
    "attempt_counter_persisted",
    "fresh_preflight_executed",
    "final_confirmation_received",
    "raw_request_blocked",
    "raw_response_blocked",
    "broker_api_response_blocked",
    "real_id_blocked",
    "credential_signature_headers_blocked",
    "fresh_preflight_required",
    "final_confirmation_required",
    "ledger_design_required",
    "attempt_counter_design_required",
    "safe_to_render",
    "safe_to_serialize",
)

_SANITIZED_RESULT_BOOL_FIELDS = (
    "sanitized_post_result_ready",
    "reconciliation_ready",
    *_SANITIZED_INPUT_BOOL_FIELDS,
)
