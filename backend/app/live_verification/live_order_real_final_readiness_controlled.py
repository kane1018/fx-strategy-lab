"""Step 6G final readiness controlled contract.

This module consolidates the final pre-POST readiness blockers as a safe
contract only. It does not call APIs, execute HTTP POST, call order endpoints,
call live_order_once, run fresh preflight, obtain final confirmation, update
ledgers, persist attempt counters, receive actual results, or hand off receipts.
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
from app.live_verification.live_order_real_sanitized_post_result import (
    SAFE_POST_RESULT_LABEL,
    SAFE_RECONCILIATION_LABEL,
    LiveOrderRealSafeReconciliationStatus,
    LiveOrderRealSanitizedPostResultResult,
    LiveOrderRealSanitizedPostResultStatus,
)

FINAL_READINESS_RECOMMENDED_NEXT_STEP = (
    "final_readiness_contract_boundary_review_no_api_no_post"
)
SAFE_FINAL_READINESS_LABEL = "CONTROLLED_FINAL_READINESS_BOUNDARY"
UNSUPPORTED_FINAL_READINESS_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealFinalReadinessControlledStatus(str, Enum):
    FINAL_READINESS_NOT_READY = "FINAL_READINESS_NOT_READY"
    FINAL_READINESS_READY_NO_POST = "FINAL_READINESS_READY_NO_POST"
    FINAL_READINESS_BLOCKED_MISSING_POST_GUARD = (
        "FINAL_READINESS_BLOCKED_MISSING_POST_GUARD"
    )
    FINAL_READINESS_BLOCKED_MISSING_SANITIZED_RESULT = (
        "FINAL_READINESS_BLOCKED_MISSING_SANITIZED_RESULT"
    )
    FINAL_READINESS_BLOCKED_FRESH_PREFLIGHT_REQUIRED = (
        "FINAL_READINESS_BLOCKED_FRESH_PREFLIGHT_REQUIRED"
    )
    FINAL_READINESS_BLOCKED_FINAL_CONFIRMATION_REQUIRED = (
        "FINAL_READINESS_BLOCKED_FINAL_CONFIRMATION_REQUIRED"
    )
    FINAL_READINESS_BLOCKED_LEDGER_ATTEMPT_COUNTER_REQUIRED = (
        "FINAL_READINESS_BLOCKED_LEDGER_ATTEMPT_COUNTER_REQUIRED"
    )
    FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF_REQUIRED = (
        "FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF_REQUIRED"
    )
    FINAL_READINESS_BLOCKED_UNKNOWN = "FINAL_READINESS_BLOCKED_UNKNOWN"
    FINAL_READINESS_BLOCKED_FAILED = "FINAL_READINESS_BLOCKED_FAILED"
    FINAL_READINESS_BLOCKED_UNAVAILABLE = "FINAL_READINESS_BLOCKED_UNAVAILABLE"
    FINAL_READINESS_BLOCKED_TIMEOUT = "FINAL_READINESS_BLOCKED_TIMEOUT"
    FINAL_READINESS_BLOCKED_STALE = "FINAL_READINESS_BLOCKED_STALE"
    FINAL_READINESS_BLOCKED_PREVIOUS_TURN = (
        "FINAL_READINESS_BLOCKED_PREVIOUS_TURN"
    )
    FINAL_READINESS_BLOCKED_REUSED = "FINAL_READINESS_BLOCKED_REUSED"
    FINAL_READINESS_BLOCKED_CONFIRMATION_REUSE = (
        "FINAL_READINESS_BLOCKED_CONFIRMATION_REUSE"
    )
    FINAL_READINESS_BLOCKED_STEP4_APPROVAL_REUSE = (
        "FINAL_READINESS_BLOCKED_STEP4_APPROVAL_REUSE"
    )
    FINAL_READINESS_BLOCKED_LEDGER_STATE_REUSE = (
        "FINAL_READINESS_BLOCKED_LEDGER_STATE_REUSE"
    )
    FINAL_READINESS_BLOCKED_UNSAFE_EXPOSURE = (
        "FINAL_READINESS_BLOCKED_UNSAFE_EXPOSURE"
    )
    FINAL_READINESS_BLOCKED_RAW_REQUEST_EXPOSURE = (
        "FINAL_READINESS_BLOCKED_RAW_REQUEST_EXPOSURE"
    )
    FINAL_READINESS_BLOCKED_RAW_RESPONSE_EXPOSURE = (
        "FINAL_READINESS_BLOCKED_RAW_RESPONSE_EXPOSURE"
    )
    FINAL_READINESS_BLOCKED_BROKER_API_RESPONSE_EXPOSURE = (
        "FINAL_READINESS_BLOCKED_BROKER_API_RESPONSE_EXPOSURE"
    )
    FINAL_READINESS_BLOCKED_REAL_ID_EXPOSURE = (
        "FINAL_READINESS_BLOCKED_REAL_ID_EXPOSURE"
    )
    FINAL_READINESS_BLOCKED_API_ATTEMPTED = (
        "FINAL_READINESS_BLOCKED_API_ATTEMPTED"
    )
    FINAL_READINESS_BLOCKED_POST_ATTEMPTED = (
        "FINAL_READINESS_BLOCKED_POST_ATTEMPTED"
    )
    FINAL_READINESS_BLOCKED_ORDER_ENDPOINT = (
        "FINAL_READINESS_BLOCKED_ORDER_ENDPOINT"
    )
    FINAL_READINESS_BLOCKED_LIVE_ORDER_ONCE = (
        "FINAL_READINESS_BLOCKED_LIVE_ORDER_ONCE"
    )
    FINAL_READINESS_BLOCKED_PREFLIGHT_EXECUTED = (
        "FINAL_READINESS_BLOCKED_PREFLIGHT_EXECUTED"
    )
    FINAL_READINESS_BLOCKED_FINAL_CONFIRMATION_EXECUTED = (
        "FINAL_READINESS_BLOCKED_FINAL_CONFIRMATION_EXECUTED"
    )
    FINAL_READINESS_BLOCKED_LEDGER_UPDATE = (
        "FINAL_READINESS_BLOCKED_LEDGER_UPDATE"
    )
    FINAL_READINESS_BLOCKED_ATTEMPT_COUNTER_PERSISTENCE = (
        "FINAL_READINESS_BLOCKED_ATTEMPT_COUNTER_PERSISTENCE"
    )
    FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF = (
        "FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF"
    )


class LiveOrderRealFinalReadinessControlledMode(str, Enum):
    FINAL_READINESS_CONTROLLED_IMPLEMENTATION_ONLY = (
        "FINAL_READINESS_CONTROLLED_IMPLEMENTATION_ONLY"
    )


FinalReadinessControlledStatus = LiveOrderRealFinalReadinessControlledStatus
FinalReadinessControlledMode = LiveOrderRealFinalReadinessControlledMode


@dataclass(frozen=True)
class LiveOrderRealFinalReadinessControlledInput:
    final_readiness_mode: str = (
        FinalReadinessControlledMode
        .FINAL_READINESS_CONTROLLED_IMPLEMENTATION_ONLY
        .value
    )
    final_readiness_declared: bool = True
    final_readiness_requested: bool = True
    post_guard_prerequisite_checked: bool = True
    post_guard_controlled_ready: bool = True
    post_guard_prerequisite_satisfied: bool = True
    safe_post_guard_label: str = SAFE_POST_GUARD_LABEL
    safe_post_guard_status: str = (
        LiveOrderRealPostGuardControlledStatus.POST_GUARD_READY_NO_POST.value
    )
    sanitized_result_prerequisite_checked: bool = True
    sanitized_post_result_ready: bool = True
    reconciliation_ready: bool = True
    sanitized_result_prerequisite_satisfied: bool = True
    safe_post_result_label: str = SAFE_POST_RESULT_LABEL
    safe_post_result_status: str = (
        LiveOrderRealSanitizedPostResultStatus.SANITIZED_RESULT_READY_NO_RECEIPT.value
    )
    safe_reconciliation_label: str = SAFE_RECONCILIATION_LABEL
    safe_reconciliation_status: str = (
        LiveOrderRealSafeReconciliationStatus
        .RECONCILIATION_READY_NO_RECEIPT_HANDOFF
        .value
    )
    safe_final_readiness_label: str = SAFE_FINAL_READINESS_LABEL
    final_readiness_unknown: bool = False
    final_readiness_failed: bool = False
    final_readiness_unavailable: bool = False
    final_readiness_timeout: bool = False
    final_readiness_stale: bool = False
    final_readiness_previous_turn: bool = False
    final_readiness_reused: bool = False
    fresh_preflight_required: bool = True
    fresh_preflight_current_required: bool = True
    fresh_preflight_non_reuse_required: bool = True
    fresh_preflight_must_be_after_latest_readiness: bool = True
    fresh_preflight_failed_fail_closed: bool = True
    fresh_preflight_unknown_fail_closed: bool = True
    fresh_preflight_timeout_fail_closed: bool = True
    fresh_preflight_unavailable_fail_closed: bool = True
    fresh_preflight_executed: bool = False
    fresh_preflight_reused: bool = False
    fresh_preflight_stale: bool = False
    fresh_preflight_unknown: bool = False
    fresh_preflight_failed: bool = False
    fresh_preflight_timeout: bool = False
    fresh_preflight_unavailable: bool = False
    final_confirmation_required: bool = True
    final_confirmation_must_be_after_fresh_preflight: bool = True
    final_confirmation_new_required: bool = True
    final_confirmation_current_turn_required: bool = True
    final_confirmation_one_time_required: bool = True
    final_confirmation_non_reuse_required: bool = True
    previous_turn_confirmation_reuse_blocked: bool = True
    step4_approval_phrase_reuse_blocked: bool = True
    confirmation_phrase_exposure_blocked: bool = True
    final_confirmation_received: bool = False
    final_confirmation_reused: bool = False
    previous_turn_confirmation_reused: bool = False
    step4_approval_phrase_reused: bool = False
    confirmation_phrase_exposure_attempted: bool = False
    ledger_attempt_counter_required: bool = True
    ledger_update_allowed: bool = False
    ledger_update_attempted: bool = False
    attempt_counter_persistence_allowed: bool = False
    attempt_counter_persisted: bool = False
    ledger_state_exposure_blocked: bool = True
    ledger_state_exposure_attempted: bool = False
    ledger_state_reuse_blocked: bool = True
    ledger_state_reused: bool = False
    one_post_max_runtime_recheck_required: bool = True
    no_retry_runtime_recheck_required: bool = True
    actual_receipt_handoff_required: bool = True
    actual_result_receipt_received: bool = False
    actual_receipt_handoff_executed: bool = False
    actual_receipt_handoff_allowed: bool = False
    actual_receipt_safe_summary_required: bool = True
    raw_broker_api_response_exposure_blocked: bool = True
    receipt_handoff_is_not_ledger_permission: bool = True
    receipt_handoff_is_not_retry_permission: bool = True
    receipt_handoff_is_not_repost_permission: bool = True
    one_shot_post_readiness_blocked: bool = True
    one_shot_post_allowed: bool = False
    api_call_allowed: bool = False
    api_call_attempted: bool = False
    http_client_present: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
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
    preflight_detail_exposure_attempted: bool = False
    approval_command_exposure_attempted: bool = False
    raw_request_stored: bool = False
    raw_response_stored: bool = False
    broker_response_exposed: bool = False
    api_response_exposed: bool = False
    real_id_exposed: bool = False
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("final_readiness_mode", self.final_readiness_mode)
        _require_non_empty("safe_post_guard_label", self.safe_post_guard_label)
        _require_non_empty("safe_post_guard_status", self.safe_post_guard_status)
        _require_non_empty("safe_post_result_label", self.safe_post_result_label)
        _require_non_empty("safe_post_result_status", self.safe_post_result_status)
        _require_non_empty(
            "safe_reconciliation_label",
            self.safe_reconciliation_label,
        )
        _require_non_empty(
            "safe_reconciliation_status",
            self.safe_reconciliation_status,
        )
        _require_non_empty(
            "safe_final_readiness_label",
            self.safe_final_readiness_label,
        )
        _validate_bool_fields(self, _FINAL_READINESS_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealFinalReadinessControlledCheckResult:
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
class LiveOrderRealFinalReadinessControlledResult:
    status: LiveOrderRealFinalReadinessControlledStatus
    final_readiness_controlled_ready: bool
    final_readiness_mode: str
    final_readiness_declared: bool
    final_readiness_requested: bool
    post_guard_prerequisite_checked: bool
    post_guard_controlled_ready: bool
    post_guard_prerequisite_satisfied: bool
    safe_post_guard_label: str
    safe_post_guard_status: str
    sanitized_result_prerequisite_checked: bool
    sanitized_post_result_ready: bool
    reconciliation_ready: bool
    sanitized_result_prerequisite_satisfied: bool
    safe_post_result_label: str
    safe_post_result_status: str
    safe_reconciliation_label: str
    safe_reconciliation_status: str
    safe_final_readiness_label: str
    safe_final_readiness_status: str
    final_readiness_unknown: bool
    final_readiness_failed: bool
    final_readiness_unavailable: bool
    final_readiness_timeout: bool
    final_readiness_stale: bool
    final_readiness_previous_turn: bool
    final_readiness_reused: bool
    fresh_preflight_required: bool
    fresh_preflight_current_required: bool
    fresh_preflight_non_reuse_required: bool
    fresh_preflight_must_be_after_latest_readiness: bool
    fresh_preflight_failed_fail_closed: bool
    fresh_preflight_unknown_fail_closed: bool
    fresh_preflight_timeout_fail_closed: bool
    fresh_preflight_unavailable_fail_closed: bool
    fresh_preflight_executed: bool
    fresh_preflight_reused: bool
    fresh_preflight_stale: bool
    fresh_preflight_unknown: bool
    fresh_preflight_failed: bool
    fresh_preflight_timeout: bool
    fresh_preflight_unavailable: bool
    final_confirmation_required: bool
    final_confirmation_must_be_after_fresh_preflight: bool
    final_confirmation_new_required: bool
    final_confirmation_current_turn_required: bool
    final_confirmation_one_time_required: bool
    final_confirmation_non_reuse_required: bool
    previous_turn_confirmation_reuse_blocked: bool
    step4_approval_phrase_reuse_blocked: bool
    confirmation_phrase_exposure_blocked: bool
    final_confirmation_received: bool
    final_confirmation_reused: bool
    previous_turn_confirmation_reused: bool
    step4_approval_phrase_reused: bool
    confirmation_phrase_exposure_attempted: bool
    ledger_attempt_counter_required: bool
    ledger_update_allowed: bool
    ledger_update_attempted: bool
    attempt_counter_persistence_allowed: bool
    attempt_counter_persisted: bool
    ledger_state_exposure_blocked: bool
    ledger_state_exposure_attempted: bool
    ledger_state_reuse_blocked: bool
    ledger_state_reused: bool
    one_post_max_runtime_recheck_required: bool
    no_retry_runtime_recheck_required: bool
    actual_receipt_handoff_required: bool
    actual_result_receipt_received: bool
    actual_receipt_handoff_executed: bool
    actual_receipt_handoff_allowed: bool
    actual_receipt_safe_summary_required: bool
    raw_broker_api_response_exposure_blocked: bool
    receipt_handoff_is_not_ledger_permission: bool
    receipt_handoff_is_not_retry_permission: bool
    receipt_handoff_is_not_repost_permission: bool
    one_shot_post_readiness_blocked: bool
    one_shot_post_allowed: bool
    api_call_allowed: bool
    api_call_attempted: bool
    http_client_present: bool
    post_allowed_this_step: bool
    post_executed: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
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
    preflight_detail_exposure_attempted: bool
    approval_command_exposure_attempted: bool
    raw_request_stored: bool
    raw_response_stored: bool
    broker_response_exposed: bool
    api_response_exposed: bool
    real_id_exposed: bool
    safe_to_render: bool
    safe_to_serialize: bool
    check_results: tuple[LiveOrderRealFinalReadinessControlledCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealFinalReadinessControlledStatus):
            raise LiveVerificationValidationError(
                "status must be final readiness controlled status",
            )
        _require_non_empty("final_readiness_mode", self.final_readiness_mode)
        _require_non_empty("safe_post_guard_label", self.safe_post_guard_label)
        _require_non_empty("safe_post_guard_status", self.safe_post_guard_status)
        _require_non_empty("safe_post_result_label", self.safe_post_result_label)
        _require_non_empty("safe_post_result_status", self.safe_post_result_status)
        _require_non_empty(
            "safe_reconciliation_label",
            self.safe_reconciliation_label,
        )
        _require_non_empty(
            "safe_reconciliation_status",
            self.safe_reconciliation_status,
        )
        _require_non_empty(
            "safe_final_readiness_label",
            self.safe_final_readiness_label,
        )
        _require_non_empty(
            "safe_final_readiness_status",
            self.safe_final_readiness_status,
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(self, _FINAL_READINESS_RESULT_BOOL_FIELDS)
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_final_readiness_controlled(
    *,
    input_snapshot: LiveOrderRealFinalReadinessControlledInput | None = None,
    post_guard_result: LiveOrderRealPostGuardControlledResult | None = None,
    sanitized_result: LiveOrderRealSanitizedPostResultResult | None = None,
) -> LiveOrderRealFinalReadinessControlledResult:
    """Build a safe final readiness contract without any execution side effects."""
    snapshot = input_snapshot or LiveOrderRealFinalReadinessControlledInput()
    if post_guard_result is not None:
        snapshot = _merge_post_guard_result(snapshot, post_guard_result)
    if sanitized_result is not None:
        snapshot = _merge_sanitized_result(snapshot, sanitized_result)

    status, primary_reasons = _status_from_input(snapshot)
    ready = status is FinalReadinessControlledStatus.FINAL_READINESS_READY_NO_POST
    safe_mode = (
        snapshot.final_readiness_mode
        if snapshot.final_readiness_mode
        == (
            FinalReadinessControlledMode
            .FINAL_READINESS_CONTROLLED_IMPLEMENTATION_ONLY
            .value
        )
        else UNSUPPORTED_FINAL_READINESS_LABEL
    )
    safe_label = (
        snapshot.safe_final_readiness_label
        if snapshot.safe_final_readiness_label == SAFE_FINAL_READINESS_LABEL
        else UNSUPPORTED_FINAL_READINESS_LABEL
    )
    safe_post_guard_label = (
        snapshot.safe_post_guard_label
        if snapshot.safe_post_guard_label == SAFE_POST_GUARD_LABEL
        else UNSUPPORTED_FINAL_READINESS_LABEL
    )
    safe_post_result_label = (
        snapshot.safe_post_result_label
        if snapshot.safe_post_result_label == SAFE_POST_RESULT_LABEL
        else UNSUPPORTED_FINAL_READINESS_LABEL
    )
    safe_reconciliation_label = (
        snapshot.safe_reconciliation_label
        if snapshot.safe_reconciliation_label == SAFE_RECONCILIATION_LABEL
        else UNSUPPORTED_FINAL_READINESS_LABEL
    )
    blocked_reasons = _blocked_reasons(
        snapshot=snapshot,
        primary_reasons=primary_reasons,
    )

    return LiveOrderRealFinalReadinessControlledResult(
        status=status,
        final_readiness_controlled_ready=ready,
        final_readiness_mode=safe_mode,
        final_readiness_declared=snapshot.final_readiness_declared,
        final_readiness_requested=snapshot.final_readiness_requested,
        post_guard_prerequisite_checked=snapshot.post_guard_prerequisite_checked,
        post_guard_controlled_ready=snapshot.post_guard_controlled_ready,
        post_guard_prerequisite_satisfied=(
            _post_guard_prerequisite_satisfied(snapshot)
        ),
        safe_post_guard_label=safe_post_guard_label,
        safe_post_guard_status=snapshot.safe_post_guard_status,
        sanitized_result_prerequisite_checked=(
            snapshot.sanitized_result_prerequisite_checked
        ),
        sanitized_post_result_ready=snapshot.sanitized_post_result_ready,
        reconciliation_ready=snapshot.reconciliation_ready,
        sanitized_result_prerequisite_satisfied=(
            _sanitized_result_prerequisite_satisfied(snapshot)
        ),
        safe_post_result_label=safe_post_result_label,
        safe_post_result_status=snapshot.safe_post_result_status,
        safe_reconciliation_label=safe_reconciliation_label,
        safe_reconciliation_status=snapshot.safe_reconciliation_status,
        safe_final_readiness_label=safe_label,
        safe_final_readiness_status=status.value,
        final_readiness_unknown=snapshot.final_readiness_unknown,
        final_readiness_failed=snapshot.final_readiness_failed,
        final_readiness_unavailable=snapshot.final_readiness_unavailable,
        final_readiness_timeout=snapshot.final_readiness_timeout,
        final_readiness_stale=snapshot.final_readiness_stale,
        final_readiness_previous_turn=snapshot.final_readiness_previous_turn,
        final_readiness_reused=snapshot.final_readiness_reused,
        fresh_preflight_required=snapshot.fresh_preflight_required,
        fresh_preflight_current_required=snapshot.fresh_preflight_current_required,
        fresh_preflight_non_reuse_required=(
            snapshot.fresh_preflight_non_reuse_required
        ),
        fresh_preflight_must_be_after_latest_readiness=(
            snapshot.fresh_preflight_must_be_after_latest_readiness
        ),
        fresh_preflight_failed_fail_closed=(
            snapshot.fresh_preflight_failed_fail_closed
        ),
        fresh_preflight_unknown_fail_closed=(
            snapshot.fresh_preflight_unknown_fail_closed
        ),
        fresh_preflight_timeout_fail_closed=(
            snapshot.fresh_preflight_timeout_fail_closed
        ),
        fresh_preflight_unavailable_fail_closed=(
            snapshot.fresh_preflight_unavailable_fail_closed
        ),
        fresh_preflight_executed=False,
        fresh_preflight_reused=False,
        fresh_preflight_stale=False,
        fresh_preflight_unknown=False,
        fresh_preflight_failed=False,
        fresh_preflight_timeout=False,
        fresh_preflight_unavailable=False,
        final_confirmation_required=snapshot.final_confirmation_required,
        final_confirmation_must_be_after_fresh_preflight=(
            snapshot.final_confirmation_must_be_after_fresh_preflight
        ),
        final_confirmation_new_required=snapshot.final_confirmation_new_required,
        final_confirmation_current_turn_required=(
            snapshot.final_confirmation_current_turn_required
        ),
        final_confirmation_one_time_required=(
            snapshot.final_confirmation_one_time_required
        ),
        final_confirmation_non_reuse_required=(
            snapshot.final_confirmation_non_reuse_required
        ),
        previous_turn_confirmation_reuse_blocked=(
            snapshot.previous_turn_confirmation_reuse_blocked
        ),
        step4_approval_phrase_reuse_blocked=(
            snapshot.step4_approval_phrase_reuse_blocked
        ),
        confirmation_phrase_exposure_blocked=(
            snapshot.confirmation_phrase_exposure_blocked
        ),
        final_confirmation_received=False,
        final_confirmation_reused=False,
        previous_turn_confirmation_reused=False,
        step4_approval_phrase_reused=False,
        confirmation_phrase_exposure_attempted=False,
        ledger_attempt_counter_required=snapshot.ledger_attempt_counter_required,
        ledger_update_allowed=False,
        ledger_update_attempted=False,
        attempt_counter_persistence_allowed=False,
        attempt_counter_persisted=False,
        ledger_state_exposure_blocked=snapshot.ledger_state_exposure_blocked,
        ledger_state_exposure_attempted=False,
        ledger_state_reuse_blocked=snapshot.ledger_state_reuse_blocked,
        ledger_state_reused=False,
        one_post_max_runtime_recheck_required=(
            snapshot.one_post_max_runtime_recheck_required
        ),
        no_retry_runtime_recheck_required=snapshot.no_retry_runtime_recheck_required,
        actual_receipt_handoff_required=snapshot.actual_receipt_handoff_required,
        actual_result_receipt_received=False,
        actual_receipt_handoff_executed=False,
        actual_receipt_handoff_allowed=False,
        actual_receipt_safe_summary_required=(
            snapshot.actual_receipt_safe_summary_required
        ),
        raw_broker_api_response_exposure_blocked=(
            snapshot.raw_broker_api_response_exposure_blocked
        ),
        receipt_handoff_is_not_ledger_permission=(
            snapshot.receipt_handoff_is_not_ledger_permission
        ),
        receipt_handoff_is_not_retry_permission=(
            snapshot.receipt_handoff_is_not_retry_permission
        ),
        receipt_handoff_is_not_repost_permission=(
            snapshot.receipt_handoff_is_not_repost_permission
        ),
        one_shot_post_readiness_blocked=snapshot.one_shot_post_readiness_blocked,
        one_shot_post_allowed=False,
        api_call_allowed=False,
        api_call_attempted=False,
        http_client_present=False,
        post_allowed_this_step=False,
        post_executed=False,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
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
        preflight_detail_exposure_attempted=False,
        approval_command_exposure_attempted=False,
        raw_request_stored=False,
        raw_response_stored=False,
        broker_response_exposed=False,
        api_response_exposed=False,
        real_id_exposed=False,
        safe_to_render=True,
        safe_to_serialize=True,
        check_results=_build_check_results(
            snapshot=snapshot,
            status=status,
            ready=ready,
            safe_label=safe_label,
        ),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            FINAL_READINESS_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_final_readiness_blockers_no_api_no_post"
        ),
    )


def render_live_order_real_final_readiness_controlled_markdown(
    result: LiveOrderRealFinalReadinessControlledResult,
) -> str:
    """Render a safe final readiness summary only."""
    lines = [
        "# Step 6G Final Readiness Controlled Contract",
        "",
        "This is a final readiness contract only.",
        "It contains safe labels, statuses, booleans, and blocked reason labels.",
        "It does not execute API calls.",
        "It does not execute HTTP POST.",
        "It does not call order endpoints.",
        "It does not call live_order_once.",
        "It does not run fresh preflight.",
        "It does not obtain final confirmation.",
        "It does not update ledgers or persist attempt counters.",
        "It does not receive actual results or hand off receipts.",
        "It does not expose raw requests, raw responses, broker/API responses, IDs,",
        "credential values, signature values, headers values, confirmation phrases,",
        "ledger state values, or approval command values.",
        "Final readiness ready does not allow POST.",
        "One-shot POST allowed remains false.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- final_readiness_controlled_ready: "
            f"{_bool_text(result.final_readiness_controlled_ready)}"
        ),
        f"- final_readiness_mode: {result.final_readiness_mode}",
        f"- safe_final_readiness_label: {result.safe_final_readiness_label}",
        f"- safe_final_readiness_status: {result.safe_final_readiness_status}",
        "",
        "## Required Contracts",
        f"- fresh_preflight_required: {_bool_text(result.fresh_preflight_required)}",
        (
            "- fresh_preflight_current_required: "
            f"{_bool_text(result.fresh_preflight_current_required)}"
        ),
        (
            "- fresh_preflight_non_reuse_required: "
            f"{_bool_text(result.fresh_preflight_non_reuse_required)}"
        ),
        (
            "- final_confirmation_required: "
            f"{_bool_text(result.final_confirmation_required)}"
        ),
        (
            "- final_confirmation_current_turn_required: "
            f"{_bool_text(result.final_confirmation_current_turn_required)}"
        ),
        (
            "- final_confirmation_one_time_required: "
            f"{_bool_text(result.final_confirmation_one_time_required)}"
        ),
        (
            "- ledger_attempt_counter_required: "
            f"{_bool_text(result.ledger_attempt_counter_required)}"
        ),
        (
            "- actual_receipt_handoff_required: "
            f"{_bool_text(result.actual_receipt_handoff_required)}"
        ),
        (
            "- one_shot_post_readiness_blocked: "
            f"{_bool_text(result.one_shot_post_readiness_blocked)}"
        ),
        "",
        "## Non-Execution",
        f"- fresh_preflight_executed: {_bool_text(result.fresh_preflight_executed)}",
        (
            "- final_confirmation_received: "
            f"{_bool_text(result.final_confirmation_received)}"
        ),
        f"- ledger_update_allowed: {_bool_text(result.ledger_update_allowed)}",
        (
            "- attempt_counter_persistence_allowed: "
            f"{_bool_text(result.attempt_counter_persistence_allowed)}"
        ),
        (
            "- actual_receipt_handoff_executed: "
            f"{_bool_text(result.actual_receipt_handoff_executed)}"
        ),
        f"- one_shot_post_allowed: {_bool_text(result.one_shot_post_allowed)}",
        f"- api_call_allowed: {_bool_text(result.api_call_allowed)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines)


def _merge_post_guard_result(
    snapshot: LiveOrderRealFinalReadinessControlledInput,
    post_guard_result: LiveOrderRealPostGuardControlledResult,
) -> LiveOrderRealFinalReadinessControlledInput:
    return replace(
        snapshot,
        post_guard_controlled_ready=post_guard_result.post_guard_ready,
        post_guard_prerequisite_satisfied=post_guard_result.post_guard_ready,
        safe_post_guard_label=post_guard_result.safe_post_guard_label,
        safe_post_guard_status=post_guard_result.safe_post_guard_status,
        final_readiness_unknown=(
            snapshot.final_readiness_unknown or post_guard_result.post_guard_unknown
        ),
        final_readiness_failed=(
            snapshot.final_readiness_failed or post_guard_result.post_guard_failed
        ),
        final_readiness_unavailable=(
            snapshot.final_readiness_unavailable
            or post_guard_result.post_guard_unavailable
        ),
        final_readiness_timeout=(
            snapshot.final_readiness_timeout or post_guard_result.post_guard_timeout
        ),
        final_readiness_stale=(
            snapshot.final_readiness_stale or post_guard_result.post_guard_stale
        ),
        final_readiness_previous_turn=(
            snapshot.final_readiness_previous_turn
            or post_guard_result.post_guard_previous_turn
        ),
        final_readiness_reused=(
            snapshot.final_readiness_reused or post_guard_result.post_guard_reused
        ),
        api_call_allowed=(
            snapshot.api_call_allowed or post_guard_result.api_call_allowed
        ),
        api_call_attempted=(
            snapshot.api_call_attempted or post_guard_result.api_call_attempted
        ),
        http_client_present=(
            snapshot.http_client_present or post_guard_result.http_client_present
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step or post_guard_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or post_guard_result.post_executed,
        http_post_executed=(
            snapshot.http_post_executed or post_guard_result.http_post_executed
        ),
        order_endpoint_called=(
            snapshot.order_endpoint_called or post_guard_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called or post_guard_result.live_order_once_called
        ),
        fresh_preflight_executed=(
            snapshot.fresh_preflight_executed
            or post_guard_result.fresh_preflight_executed
        ),
        final_confirmation_received=(
            snapshot.final_confirmation_received
            or post_guard_result.final_confirmation_received
        ),
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or post_guard_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or post_guard_result.actual_receipt_handoff_executed
        ),
    )


def _merge_sanitized_result(
    snapshot: LiveOrderRealFinalReadinessControlledInput,
    sanitized_result: LiveOrderRealSanitizedPostResultResult,
) -> LiveOrderRealFinalReadinessControlledInput:
    return replace(
        snapshot,
        sanitized_post_result_ready=sanitized_result.sanitized_post_result_ready,
        reconciliation_ready=sanitized_result.reconciliation_ready,
        sanitized_result_prerequisite_satisfied=(
            sanitized_result.sanitized_post_result_ready
            and sanitized_result.reconciliation_ready
        ),
        safe_post_result_label=sanitized_result.safe_post_result_label,
        safe_post_result_status=sanitized_result.safe_post_result_status,
        safe_reconciliation_label=sanitized_result.safe_reconciliation_label,
        safe_reconciliation_status=sanitized_result.safe_reconciliation_status,
        final_readiness_unknown=(
            snapshot.final_readiness_unknown or sanitized_result.result_unknown
        ),
        final_readiness_failed=(
            snapshot.final_readiness_failed or sanitized_result.result_failed
        ),
        final_readiness_unavailable=(
            snapshot.final_readiness_unavailable or sanitized_result.result_unavailable
        ),
        final_readiness_timeout=(
            snapshot.final_readiness_timeout or sanitized_result.result_timeout
        ),
        final_readiness_stale=(
            snapshot.final_readiness_stale or sanitized_result.result_stale
        ),
        final_readiness_previous_turn=(
            snapshot.final_readiness_previous_turn
            or sanitized_result.result_previous_turn
        ),
        final_readiness_reused=(
            snapshot.final_readiness_reused or sanitized_result.result_reused
        ),
        unsafe_exposure_attempted=(
            snapshot.unsafe_exposure_attempted
            or sanitized_result.unsafe_exposure_attempted
        ),
        raw_request_stored=(
            snapshot.raw_request_stored or sanitized_result.raw_request_stored
        ),
        raw_response_stored=(
            snapshot.raw_response_stored or sanitized_result.raw_response_stored
        ),
        broker_response_exposed=(
            snapshot.broker_response_exposed
            or sanitized_result.broker_response_exposed
        ),
        api_response_exposed=(
            snapshot.api_response_exposed or sanitized_result.api_response_exposed
        ),
        real_id_exposed=snapshot.real_id_exposed or sanitized_result.real_id_exposed,
        api_call_allowed=(
            snapshot.api_call_allowed or sanitized_result.api_call_allowed
        ),
        api_call_attempted=(
            snapshot.api_call_attempted or sanitized_result.api_call_attempted
        ),
        http_client_present=(
            snapshot.http_client_present or sanitized_result.http_client_present
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step or sanitized_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or sanitized_result.post_executed,
        http_post_executed=(
            snapshot.http_post_executed or sanitized_result.http_post_executed
        ),
        order_endpoint_called=(
            snapshot.order_endpoint_called or sanitized_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called or sanitized_result.live_order_once_called
        ),
        ledger_update_allowed=(
            snapshot.ledger_update_allowed or sanitized_result.ledger_update_allowed
        ),
        ledger_update_attempted=(
            snapshot.ledger_update_attempted or sanitized_result.ledger_update_attempted
        ),
        attempt_counter_persisted=(
            snapshot.attempt_counter_persisted
            or sanitized_result.attempt_counter_persisted
        ),
        fresh_preflight_executed=(
            snapshot.fresh_preflight_executed
            or sanitized_result.fresh_preflight_executed
        ),
        final_confirmation_received=(
            snapshot.final_confirmation_received
            or sanitized_result.final_confirmation_received
        ),
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or sanitized_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or sanitized_result.actual_receipt_handoff_executed
        ),
        actual_receipt_handoff_allowed=(
            snapshot.actual_receipt_handoff_allowed
            or sanitized_result.actual_receipt_handoff_allowed
        ),
    )


def _status_from_input(
    snapshot: LiveOrderRealFinalReadinessControlledInput,
) -> tuple[LiveOrderRealFinalReadinessControlledStatus, tuple[str, ...]]:
    if (
        snapshot.final_readiness_mode
        != (
            FinalReadinessControlledMode
            .FINAL_READINESS_CONTROLLED_IMPLEMENTATION_ONLY
            .value
        )
    ):
        return FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_UNKNOWN, (
            "unsupported_final_readiness_mode",
        )
    if (
        not snapshot.final_readiness_declared
        or not snapshot.final_readiness_requested
    ):
        return FinalReadinessControlledStatus.FINAL_READINESS_NOT_READY, (
            "final_readiness_not_declared_or_requested",
        )
    if not _post_guard_prerequisite_satisfied(snapshot):
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_MISSING_POST_GUARD,
            ("post_guard_prerequisite_missing",),
        )
    if not _sanitized_result_prerequisite_satisfied(snapshot):
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_MISSING_SANITIZED_RESULT,
            ("sanitized_result_prerequisite_missing",),
        )
    if snapshot.final_readiness_unknown or snapshot.fresh_preflight_unknown:
        return FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_UNKNOWN, (
            "final_readiness_or_fresh_preflight_unknown",
        )
    if snapshot.final_readiness_failed or snapshot.fresh_preflight_failed:
        return FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_FAILED, (
            "final_readiness_or_fresh_preflight_failed",
        )
    if snapshot.final_readiness_unavailable or snapshot.fresh_preflight_unavailable:
        return (
            FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_UNAVAILABLE,
            ("final_readiness_or_fresh_preflight_unavailable",),
        )
    if snapshot.final_readiness_timeout or snapshot.fresh_preflight_timeout:
        return FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_TIMEOUT, (
            "final_readiness_or_fresh_preflight_timeout",
        )
    if snapshot.final_readiness_stale or snapshot.fresh_preflight_stale:
        return FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_STALE, (
            "final_readiness_or_fresh_preflight_stale",
        )
    if snapshot.final_readiness_previous_turn:
        return (
            FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_PREVIOUS_TURN,
            ("final_readiness_previous_turn",),
        )
    if snapshot.final_readiness_reused or snapshot.fresh_preflight_reused:
        return FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_REUSED, (
            "final_readiness_or_fresh_preflight_reused",
        )
    if not _fresh_preflight_contract_complete(snapshot):
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_FRESH_PREFLIGHT_REQUIRED,
            ("fresh_preflight_required_contract_missing",),
        )
    if snapshot.fresh_preflight_executed:
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_PREFLIGHT_EXECUTED,
            ("fresh_preflight_executed_in_contract_step",),
        )
    if not _final_confirmation_contract_complete(snapshot):
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_FINAL_CONFIRMATION_REQUIRED,
            ("final_confirmation_required_contract_missing",),
        )
    if snapshot.final_confirmation_received:
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_FINAL_CONFIRMATION_EXECUTED,
            ("final_confirmation_received_in_contract_step",),
        )
    if snapshot.final_confirmation_reused or snapshot.previous_turn_confirmation_reused:
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_CONFIRMATION_REUSE,
            ("final_confirmation_reuse_attempted",),
        )
    if snapshot.step4_approval_phrase_reused:
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_STEP4_APPROVAL_REUSE,
            ("step4_approval_phrase_reuse_attempted",),
        )
    if snapshot.ledger_update_allowed or snapshot.ledger_update_attempted:
        return FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_LEDGER_UPDATE, (
            "ledger_update_attempted_or_allowed",
        )
    if snapshot.attempt_counter_persistence_allowed:
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_ATTEMPT_COUNTER_PERSISTENCE,
            ("attempt_counter_persistence_allowed",),
        )
    if snapshot.attempt_counter_persisted:
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_ATTEMPT_COUNTER_PERSISTENCE,
            ("attempt_counter_persisted",),
        )
    if snapshot.ledger_state_reused:
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_LEDGER_STATE_REUSE,
            ("ledger_state_reuse_attempted",),
        )
    if not _ledger_attempt_counter_contract_complete(snapshot):
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_LEDGER_ATTEMPT_COUNTER_REQUIRED,
            ("ledger_attempt_counter_required_contract_missing",),
        )
    if (
        snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
        or snapshot.actual_receipt_handoff_allowed
    ):
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF,
            ("actual_receipt_or_handoff_attempted",),
        )
    if not _actual_receipt_contract_complete(snapshot):
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF_REQUIRED,
            ("actual_receipt_handoff_required_contract_missing",),
        )
    if snapshot.raw_request_exposure_attempted or snapshot.raw_request_stored:
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_RAW_REQUEST_EXPOSURE,
            ("raw_request_exposure_or_storage_attempted",),
        )
    if snapshot.raw_response_exposure_attempted or snapshot.raw_response_stored:
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_RAW_RESPONSE_EXPOSURE,
            ("raw_response_exposure_or_storage_attempted",),
        )
    if (
        snapshot.broker_response_exposure_attempted
        or snapshot.api_response_exposure_attempted
        or snapshot.broker_response_exposed
        or snapshot.api_response_exposed
    ):
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_BROKER_API_RESPONSE_EXPOSURE,
            ("broker_or_api_response_exposure_attempted",),
        )
    if _identifier_exposure_attempted(snapshot):
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_REAL_ID_EXPOSURE,
            ("identifier_exposure_attempted",),
        )
    if _unsafe_exposure_attempted(snapshot):
        return (
            FinalReadinessControlledStatus
            .FINAL_READINESS_BLOCKED_UNSAFE_EXPOSURE,
            ("unsafe_exposure_attempted",),
        )
    if (
        snapshot.api_call_allowed
        or snapshot.api_call_attempted
        or snapshot.http_client_present
    ):
        return FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_API_ATTEMPTED, (
            "api_attempted_or_allowed",
        )
    if (
        snapshot.post_allowed_this_step
        or snapshot.post_executed
        or snapshot.http_post_executed
        or snapshot.one_shot_post_allowed
    ):
        return (
            FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_POST_ATTEMPTED,
            ("post_attempted_or_allowed",),
        )
    if snapshot.order_endpoint_called:
        return FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_ORDER_ENDPOINT, (
            "order_endpoint_called",
        )
    if snapshot.live_order_once_called:
        return FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_LIVE_ORDER_ONCE, (
            "live_order_once_called",
        )
    if not snapshot.one_shot_post_readiness_blocked:
        return (
            FinalReadinessControlledStatus.FINAL_READINESS_BLOCKED_POST_ATTEMPTED,
            ("one_shot_post_readiness_not_blocked",),
        )
    return FinalReadinessControlledStatus.FINAL_READINESS_READY_NO_POST, ()


def _blocked_reasons(
    *,
    snapshot: LiveOrderRealFinalReadinessControlledInput,
    primary_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons = list(primary_reasons)
    if snapshot.safe_final_readiness_label != SAFE_FINAL_READINESS_LABEL:
        reasons.append("safe_final_readiness_label_invalid")
    if not snapshot.post_guard_prerequisite_checked:
        reasons.append("post_guard_prerequisite_not_checked")
    if not snapshot.post_guard_controlled_ready:
        reasons.append("post_guard_controlled_not_ready")
    if snapshot.safe_post_guard_label != SAFE_POST_GUARD_LABEL:
        reasons.append("safe_post_guard_label_invalid")
    if snapshot.safe_post_guard_status != _ready_post_guard_status():
        reasons.append("safe_post_guard_status_not_ready")
    if not snapshot.sanitized_result_prerequisite_checked:
        reasons.append("sanitized_result_prerequisite_not_checked")
    if not snapshot.sanitized_post_result_ready:
        reasons.append("sanitized_post_result_not_ready")
    if not snapshot.reconciliation_ready:
        reasons.append("reconciliation_not_ready")
    if snapshot.safe_post_result_label != SAFE_POST_RESULT_LABEL:
        reasons.append("safe_post_result_label_invalid")
    if snapshot.safe_post_result_status != _ready_sanitized_result_status():
        reasons.append("safe_post_result_status_not_ready")
    if snapshot.safe_reconciliation_label != SAFE_RECONCILIATION_LABEL:
        reasons.append("safe_reconciliation_label_invalid")
    if snapshot.safe_reconciliation_status != _ready_reconciliation_status():
        reasons.append("safe_reconciliation_status_not_ready")
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
    if snapshot.preflight_detail_exposure_attempted:
        reasons.append("preflight_detail_exposure_attempted")
    if snapshot.confirmation_phrase_exposure_attempted:
        reasons.append("confirmation_phrase_exposure_attempted")
    if snapshot.ledger_state_exposure_attempted:
        reasons.append("ledger_state_exposure_attempted")
    if snapshot.approval_command_exposure_attempted:
        reasons.append("approval_command_exposure_attempted")
    if not snapshot.safe_to_render:
        reasons.append("render_not_safe")
    if not snapshot.safe_to_serialize:
        reasons.append("serialize_not_safe")
    return _dedupe(reasons)


def _build_check_results(
    *,
    snapshot: LiveOrderRealFinalReadinessControlledInput,
    status: LiveOrderRealFinalReadinessControlledStatus,
    ready: bool,
    safe_label: str,
) -> tuple[LiveOrderRealFinalReadinessControlledCheckResult, ...]:
    return (
        LiveOrderRealFinalReadinessControlledCheckResult(
            name="final readiness contract mode",
            passed=(
                snapshot.final_readiness_mode
                == (
                    FinalReadinessControlledMode
                    .FINAL_READINESS_CONTROLLED_IMPLEMENTATION_ONLY
                    .value
                )
            ),
            sanitized_value=(
                snapshot.final_readiness_mode
                if snapshot.final_readiness_mode
                == (
                    FinalReadinessControlledMode
                    .FINAL_READINESS_CONTROLLED_IMPLEMENTATION_ONLY
                    .value
                )
                else UNSUPPORTED_FINAL_READINESS_LABEL
            ),
            expected="final readiness controlled implementation only",
        ),
        LiveOrderRealFinalReadinessControlledCheckResult(
            name="safe final readiness label",
            passed=safe_label == SAFE_FINAL_READINESS_LABEL,
            sanitized_value=safe_label,
            expected="fixed safe final readiness label",
        ),
        LiveOrderRealFinalReadinessControlledCheckResult(
            name="prerequisites ready",
            passed=(
                _post_guard_prerequisite_satisfied(snapshot)
                and _sanitized_result_prerequisite_satisfied(snapshot)
            ),
            sanitized_value="ready"
            if (
                _post_guard_prerequisite_satisfied(snapshot)
                and _sanitized_result_prerequisite_satisfied(snapshot)
            )
            else "blocked",
            expected="controlled POST guard and sanitized result ready",
        ),
        LiveOrderRealFinalReadinessControlledCheckResult(
            name="fresh and final required but not executed",
            passed=(
                _fresh_preflight_contract_complete(snapshot)
                and _final_confirmation_contract_complete(snapshot)
                and not snapshot.fresh_preflight_executed
                and not snapshot.final_confirmation_received
            ),
            sanitized_value="required_not_executed",
            expected="fresh preflight and final confirmation required later",
        ),
        LiveOrderRealFinalReadinessControlledCheckResult(
            name="ledger attempt counter and receipt contract",
            passed=(
                _ledger_attempt_counter_contract_complete(snapshot)
                and _actual_receipt_contract_complete(snapshot)
                and not snapshot.ledger_update_allowed
                and not snapshot.ledger_update_attempted
                and not snapshot.attempt_counter_persistence_allowed
                and not snapshot.attempt_counter_persisted
                and not snapshot.actual_result_receipt_received
                and not snapshot.actual_receipt_handoff_executed
                and not snapshot.actual_receipt_handoff_allowed
            ),
            sanitized_value="required_not_executed",
            expected="ledger attempt counter and receipt handoff required later",
        ),
        LiveOrderRealFinalReadinessControlledCheckResult(
            name="no api post live_order_once",
            passed=(
                not snapshot.api_call_allowed
                and not snapshot.api_call_attempted
                and not snapshot.http_client_present
                and not snapshot.post_allowed_this_step
                and not snapshot.post_executed
                and not snapshot.http_post_executed
                and not snapshot.order_endpoint_called
                and not snapshot.live_order_once_called
                and not snapshot.one_shot_post_allowed
            ),
            sanitized_value="blocked",
            expected="no API no POST no order endpoint no live_order_once",
        ),
        LiveOrderRealFinalReadinessControlledCheckResult(
            name="ready is not post permission",
            passed=ready
            == (status is FinalReadinessControlledStatus.FINAL_READINESS_READY_NO_POST),
            sanitized_value=status.value,
            expected="ready no POST one-shot remains blocked",
        ),
    )


def _post_guard_prerequisite_satisfied(
    snapshot: LiveOrderRealFinalReadinessControlledInput,
) -> bool:
    return (
        snapshot.post_guard_prerequisite_checked
        and snapshot.post_guard_controlled_ready
        and snapshot.post_guard_prerequisite_satisfied
        and snapshot.safe_post_guard_label == SAFE_POST_GUARD_LABEL
        and snapshot.safe_post_guard_status == _ready_post_guard_status()
    )


def _sanitized_result_prerequisite_satisfied(
    snapshot: LiveOrderRealFinalReadinessControlledInput,
) -> bool:
    return (
        snapshot.sanitized_result_prerequisite_checked
        and snapshot.sanitized_post_result_ready
        and snapshot.reconciliation_ready
        and snapshot.sanitized_result_prerequisite_satisfied
        and snapshot.safe_post_result_label == SAFE_POST_RESULT_LABEL
        and snapshot.safe_post_result_status == _ready_sanitized_result_status()
        and snapshot.safe_reconciliation_label == SAFE_RECONCILIATION_LABEL
        and snapshot.safe_reconciliation_status == _ready_reconciliation_status()
    )


def _fresh_preflight_contract_complete(
    snapshot: LiveOrderRealFinalReadinessControlledInput,
) -> bool:
    return (
        snapshot.fresh_preflight_required
        and snapshot.fresh_preflight_current_required
        and snapshot.fresh_preflight_non_reuse_required
        and snapshot.fresh_preflight_must_be_after_latest_readiness
        and snapshot.fresh_preflight_failed_fail_closed
        and snapshot.fresh_preflight_unknown_fail_closed
        and snapshot.fresh_preflight_timeout_fail_closed
        and snapshot.fresh_preflight_unavailable_fail_closed
    )


def _final_confirmation_contract_complete(
    snapshot: LiveOrderRealFinalReadinessControlledInput,
) -> bool:
    return (
        snapshot.final_confirmation_required
        and snapshot.final_confirmation_must_be_after_fresh_preflight
        and snapshot.final_confirmation_new_required
        and snapshot.final_confirmation_current_turn_required
        and snapshot.final_confirmation_one_time_required
        and snapshot.final_confirmation_non_reuse_required
        and snapshot.previous_turn_confirmation_reuse_blocked
        and snapshot.step4_approval_phrase_reuse_blocked
        and snapshot.confirmation_phrase_exposure_blocked
    )


def _ledger_attempt_counter_contract_complete(
    snapshot: LiveOrderRealFinalReadinessControlledInput,
) -> bool:
    return (
        snapshot.ledger_attempt_counter_required
        and not snapshot.ledger_update_allowed
        and not snapshot.attempt_counter_persistence_allowed
        and snapshot.ledger_state_exposure_blocked
        and snapshot.ledger_state_reuse_blocked
        and snapshot.one_post_max_runtime_recheck_required
        and snapshot.no_retry_runtime_recheck_required
    )


def _actual_receipt_contract_complete(
    snapshot: LiveOrderRealFinalReadinessControlledInput,
) -> bool:
    return (
        snapshot.actual_receipt_handoff_required
        and not snapshot.actual_receipt_handoff_allowed
        and snapshot.actual_receipt_safe_summary_required
        and snapshot.raw_broker_api_response_exposure_blocked
        and snapshot.receipt_handoff_is_not_ledger_permission
        and snapshot.receipt_handoff_is_not_retry_permission
        and snapshot.receipt_handoff_is_not_repost_permission
    )


def _identifier_exposure_attempted(
    snapshot: LiveOrderRealFinalReadinessControlledInput,
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
    snapshot: LiveOrderRealFinalReadinessControlledInput,
) -> bool:
    return (
        snapshot.unsafe_exposure_attempted
        or snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
        or snapshot.request_body_exposure_attempted
        or snapshot.response_body_exposure_attempted
        or snapshot.preflight_detail_exposure_attempted
        or snapshot.confirmation_phrase_exposure_attempted
        or snapshot.ledger_state_exposure_attempted
        or snapshot.approval_command_exposure_attempted
        or not snapshot.confirmation_phrase_exposure_blocked
        or not snapshot.ledger_state_exposure_blocked
        or not snapshot.raw_broker_api_response_exposure_blocked
        or snapshot.safe_final_readiness_label != SAFE_FINAL_READINESS_LABEL
        or not snapshot.safe_to_render
        or not snapshot.safe_to_serialize
    )


def _validate_result_safety(
    result: LiveOrderRealFinalReadinessControlledResult,
) -> None:
    if result.final_readiness_controlled_ready and (
        result.api_call_allowed
        or result.api_call_attempted
        or result.http_client_present
        or result.post_allowed_this_step
        or result.post_executed
        or result.http_post_executed
        or result.order_endpoint_called
        or result.live_order_once_called
        or result.fresh_preflight_executed
        or result.final_confirmation_received
        or result.ledger_update_allowed
        or result.ledger_update_attempted
        or result.attempt_counter_persistence_allowed
        or result.attempt_counter_persisted
        or result.actual_result_receipt_received
        or result.actual_receipt_handoff_executed
        or result.actual_receipt_handoff_allowed
        or result.one_shot_post_allowed
    ):
        raise LiveVerificationValidationError(
            "final readiness ready must not authorize execution",
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
        result.preflight_detail_exposure_attempted,
        result.confirmation_phrase_exposure_attempted,
        result.ledger_state_exposure_attempted,
        result.approval_command_exposure_attempted,
        result.raw_request_stored,
        result.raw_response_stored,
        result.broker_response_exposed,
        result.api_response_exposed,
        result.real_id_exposed,
        result.api_call_allowed,
        result.api_call_attempted,
        result.http_client_present,
        result.post_allowed_this_step,
        result.post_executed,
        result.http_post_executed,
        result.order_endpoint_called,
        result.live_order_once_called,
        result.fresh_preflight_executed,
        result.fresh_preflight_reused,
        result.fresh_preflight_stale,
        result.fresh_preflight_unknown,
        result.fresh_preflight_failed,
        result.fresh_preflight_timeout,
        result.fresh_preflight_unavailable,
        result.final_confirmation_received,
        result.final_confirmation_reused,
        result.previous_turn_confirmation_reused,
        result.step4_approval_phrase_reused,
        result.ledger_update_allowed,
        result.ledger_update_attempted,
        result.attempt_counter_persistence_allowed,
        result.attempt_counter_persisted,
        result.ledger_state_reused,
        result.actual_result_receipt_received,
        result.actual_receipt_handoff_executed,
        result.actual_receipt_handoff_allowed,
        result.one_shot_post_allowed,
    )
    if any(forbidden_flags):
        raise LiveVerificationValidationError(
            "final readiness contract must sanitize unsafe flags",
        )


def _ready_post_guard_status() -> str:
    return LiveOrderRealPostGuardControlledStatus.POST_GUARD_READY_NO_POST.value


def _ready_sanitized_result_status() -> str:
    return (
        LiveOrderRealSanitizedPostResultStatus
        .SANITIZED_RESULT_READY_NO_RECEIPT
        .value
    )


def _ready_reconciliation_status() -> str:
    return (
        LiveOrderRealSafeReconciliationStatus
        .RECONCILIATION_READY_NO_RECEIPT_HANDOFF
        .value
    )


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


_FINAL_READINESS_BOOL_FIELDS = (
    "final_readiness_declared",
    "final_readiness_requested",
    "post_guard_prerequisite_checked",
    "post_guard_controlled_ready",
    "post_guard_prerequisite_satisfied",
    "sanitized_result_prerequisite_checked",
    "sanitized_post_result_ready",
    "reconciliation_ready",
    "sanitized_result_prerequisite_satisfied",
    "final_readiness_unknown",
    "final_readiness_failed",
    "final_readiness_unavailable",
    "final_readiness_timeout",
    "final_readiness_stale",
    "final_readiness_previous_turn",
    "final_readiness_reused",
    "fresh_preflight_required",
    "fresh_preflight_current_required",
    "fresh_preflight_non_reuse_required",
    "fresh_preflight_must_be_after_latest_readiness",
    "fresh_preflight_failed_fail_closed",
    "fresh_preflight_unknown_fail_closed",
    "fresh_preflight_timeout_fail_closed",
    "fresh_preflight_unavailable_fail_closed",
    "fresh_preflight_executed",
    "fresh_preflight_reused",
    "fresh_preflight_stale",
    "fresh_preflight_unknown",
    "fresh_preflight_failed",
    "fresh_preflight_timeout",
    "fresh_preflight_unavailable",
    "final_confirmation_required",
    "final_confirmation_must_be_after_fresh_preflight",
    "final_confirmation_new_required",
    "final_confirmation_current_turn_required",
    "final_confirmation_one_time_required",
    "final_confirmation_non_reuse_required",
    "previous_turn_confirmation_reuse_blocked",
    "step4_approval_phrase_reuse_blocked",
    "confirmation_phrase_exposure_blocked",
    "final_confirmation_received",
    "final_confirmation_reused",
    "previous_turn_confirmation_reused",
    "step4_approval_phrase_reused",
    "confirmation_phrase_exposure_attempted",
    "ledger_attempt_counter_required",
    "ledger_update_allowed",
    "ledger_update_attempted",
    "attempt_counter_persistence_allowed",
    "attempt_counter_persisted",
    "ledger_state_exposure_blocked",
    "ledger_state_exposure_attempted",
    "ledger_state_reuse_blocked",
    "ledger_state_reused",
    "one_post_max_runtime_recheck_required",
    "no_retry_runtime_recheck_required",
    "actual_receipt_handoff_required",
    "actual_result_receipt_received",
    "actual_receipt_handoff_executed",
    "actual_receipt_handoff_allowed",
    "actual_receipt_safe_summary_required",
    "raw_broker_api_response_exposure_blocked",
    "receipt_handoff_is_not_ledger_permission",
    "receipt_handoff_is_not_retry_permission",
    "receipt_handoff_is_not_repost_permission",
    "one_shot_post_readiness_blocked",
    "one_shot_post_allowed",
    "api_call_allowed",
    "api_call_attempted",
    "http_client_present",
    "post_allowed_this_step",
    "post_executed",
    "http_post_executed",
    "order_endpoint_called",
    "live_order_once_called",
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
    "preflight_detail_exposure_attempted",
    "approval_command_exposure_attempted",
    "raw_request_stored",
    "raw_response_stored",
    "broker_response_exposed",
    "api_response_exposed",
    "real_id_exposed",
    "safe_to_render",
    "safe_to_serialize",
)

_FINAL_READINESS_RESULT_BOOL_FIELDS = (
    "final_readiness_controlled_ready",
    *_FINAL_READINESS_BOOL_FIELDS,
)
