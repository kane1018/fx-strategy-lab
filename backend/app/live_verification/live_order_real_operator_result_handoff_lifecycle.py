"""Step 6G operator result handoff lifecycle contract skeleton.

This module defines only safe lifecycle labels and transitions for a future
operator receipt handoff. It does not perform actual receipt handoff, receive
actual results, execute a checker, read env, inspect credentials, call APIs, or
execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_operator_execution_result_category_contract import (
    LiveOrderRealOperatorExecutionResultCategory,
)

OPERATOR_RESULT_HANDOFF_LIFECYCLE_RECOMMENDED_NEXT_STEP = (
    "operator_result_handoff_lifecycle_boundary_review_no_env_no_api_no_post"
)
UNSUPPORTED_OPERATOR_RESULT_HANDOFF_LIFECYCLE_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealOperatorResultHandoffLifecycleStatus(str, Enum):
    LIFECYCLE_NOT_READY = "LIFECYCLE_NOT_READY"
    LIFECYCLE_READY_NO_RECEIPT = "LIFECYCLE_READY_NO_RECEIPT"
    LIFECYCLE_RECEIPT_NOT_PROVIDED_NO_ACTUAL_RECEIPT = (
        "LIFECYCLE_RECEIPT_NOT_PROVIDED_NO_ACTUAL_RECEIPT"
    )
    LIFECYCLE_READY_CONFIRMED_NO_POST = "LIFECYCLE_READY_CONFIRMED_NO_POST"
    LIFECYCLE_BLOCKED_STALE = "LIFECYCLE_BLOCKED_STALE"
    LIFECYCLE_BLOCKED_REUSED = "LIFECYCLE_BLOCKED_REUSED"
    LIFECYCLE_BLOCKED_PREVIOUS_TURN = "LIFECYCLE_BLOCKED_PREVIOUS_TURN"
    LIFECYCLE_BLOCKED_TIMEOUT = "LIFECYCLE_BLOCKED_TIMEOUT"
    LIFECYCLE_BLOCKED_EXPIRED = "LIFECYCLE_BLOCKED_EXPIRED"
    LIFECYCLE_BLOCKED_UNKNOWN = "LIFECYCLE_BLOCKED_UNKNOWN"
    LIFECYCLE_BLOCKED_FAILED = "LIFECYCLE_BLOCKED_FAILED"
    LIFECYCLE_BLOCKED_UNAVAILABLE = "LIFECYCLE_BLOCKED_UNAVAILABLE"
    LIFECYCLE_BLOCKED_UNSUPPORTED = "LIFECYCLE_BLOCKED_UNSUPPORTED"
    LIFECYCLE_BLOCKED_RAW_RECEIPT = "LIFECYCLE_BLOCKED_RAW_RECEIPT"
    LIFECYCLE_BLOCKED_DETAIL_EXPOSURE = "LIFECYCLE_BLOCKED_DETAIL_EXPOSURE"
    LIFECYCLE_BLOCKED_IDENTIFIER_EXPOSURE = (
        "LIFECYCLE_BLOCKED_IDENTIFIER_EXPOSURE"
    )
    LIFECYCLE_BLOCKED_ENV_OR_CREDENTIAL = "LIFECYCLE_BLOCKED_ENV_OR_CREDENTIAL"
    LIFECYCLE_BLOCKED_ACTUAL_EXECUTION = "LIFECYCLE_BLOCKED_ACTUAL_EXECUTION"
    LIFECYCLE_BLOCKED_ACTUAL_RECEIPT = "LIFECYCLE_BLOCKED_ACTUAL_RECEIPT"
    LIFECYCLE_BLOCKED_API_OR_POST = "LIFECYCLE_BLOCKED_API_OR_POST"
    LIFECYCLE_BLOCKED_LIVE_ORDER_ONCE = "LIFECYCLE_BLOCKED_LIVE_ORDER_ONCE"
    LIFECYCLE_BLOCKED_FINAL_CONFIRMATION = "LIFECYCLE_BLOCKED_FINAL_CONFIRMATION"
    LIFECYCLE_BLOCKED_FRESH_PREFLIGHT = "LIFECYCLE_BLOCKED_FRESH_PREFLIGHT"


class LiveOrderRealOperatorResultHandoffLifecycleMode(str, Enum):
    OPERATOR_RESULT_HANDOFF_LIFECYCLE_SKELETON_ONLY = (
        "OPERATOR_RESULT_HANDOFF_LIFECYCLE_SKELETON_ONLY"
    )


class LiveOrderRealOperatorResultHandoffLifecycleState(str, Enum):
    LIFECYCLE_NOT_STARTED = "LIFECYCLE_NOT_STARTED"
    LIFECYCLE_POLICY_READY = "LIFECYCLE_POLICY_READY"
    LIFECYCLE_RECEIPT_NOT_PROVIDED = "LIFECYCLE_RECEIPT_NOT_PROVIDED"
    LIFECYCLE_RECEIPT_DECLARED_SAFE_ONLY = "LIFECYCLE_RECEIPT_DECLARED_SAFE_ONLY"
    LIFECYCLE_READY_CONFIRMED_NO_POST = "LIFECYCLE_READY_CONFIRMED_NO_POST"
    LIFECYCLE_BLOCKED = "LIFECYCLE_BLOCKED"


class LiveOrderRealOperatorResultHandoffLifecycleEvent(str, Enum):
    DECLARE_POLICY_READY = "DECLARE_POLICY_READY"
    DECLARE_RECEIPT_NOT_PROVIDED = "DECLARE_RECEIPT_NOT_PROVIDED"
    DECLARE_SAFE_CATEGORY_READY_CONFIRMED = (
        "DECLARE_SAFE_CATEGORY_READY_CONFIRMED"
    )
    DECLARE_STALE = "DECLARE_STALE"
    DECLARE_REUSED = "DECLARE_REUSED"
    DECLARE_PREVIOUS_TURN = "DECLARE_PREVIOUS_TURN"
    DECLARE_TIMEOUT = "DECLARE_TIMEOUT"
    DECLARE_UNKNOWN = "DECLARE_UNKNOWN"
    DECLARE_FAILED = "DECLARE_FAILED"
    DECLARE_UNAVAILABLE = "DECLARE_UNAVAILABLE"
    DECLARE_RAW_PRESENT = "DECLARE_RAW_PRESENT"
    DECLARE_DETAIL_PRESENT = "DECLARE_DETAIL_PRESENT"
    DECLARE_IDENTIFIER_PRESENT = "DECLARE_IDENTIFIER_PRESENT"
    DECLARE_ACTUAL_RECEIPT_ATTEMPTED = "DECLARE_ACTUAL_RECEIPT_ATTEMPTED"
    DECLARE_API_OR_POST_ATTEMPTED = "DECLARE_API_OR_POST_ATTEMPTED"


LifecycleStatus = LiveOrderRealOperatorResultHandoffLifecycleStatus
LifecycleMode = LiveOrderRealOperatorResultHandoffLifecycleMode
LifecycleState = LiveOrderRealOperatorResultHandoffLifecycleState
LifecycleEvent = LiveOrderRealOperatorResultHandoffLifecycleEvent
OperatorExecutionResultCategory = LiveOrderRealOperatorExecutionResultCategory

_UNKNOWN_FAILED_UNAVAILABLE_CATEGORIES = frozenset(
    (
        OperatorExecutionResultCategory.BLOCKED_UNKNOWN.value,
        OperatorExecutionResultCategory.BLOCKED_FAILED.value,
        OperatorExecutionResultCategory.BLOCKED_UNAVAILABLE.value,
    ),
)
_STALE_REUSED_PREVIOUS_CATEGORIES = frozenset(
    (
        OperatorExecutionResultCategory.BLOCKED_STALE.value,
        OperatorExecutionResultCategory.BLOCKED_REUSED.value,
        OperatorExecutionResultCategory.BLOCKED_PREVIOUS_TURN.value,
    ),
)


@dataclass(frozen=True)
class LiveOrderRealOperatorResultHandoffLifecycleInput:
    lifecycle_mode: str = (
        LifecycleMode.OPERATOR_RESULT_HANDOFF_LIFECYCLE_SKELETON_ONLY.value
    )
    lifecycle_declared: bool = True
    lifecycle_transition_policy_declared: bool = True
    from_state: str = LifecycleState.LIFECYCLE_POLICY_READY.value
    lifecycle_event: str = LifecycleEvent.DECLARE_RECEIPT_NOT_PROVIDED.value
    one_time_required: bool = True
    fresh_required: bool = True
    current_turn_required: bool = True
    non_reuse_required: bool = True
    previous_turn_prohibited: bool = True
    stale_prohibited: bool = True
    timeout_prohibited: bool = True
    expired_prohibited: bool = True
    non_raw_required: bool = True
    non_detail_required: bool = True
    non_identifier_required: bool = True
    safe_category_only: bool = True
    operator_result_handoff_policy_ready: bool = True
    operator_execution_result_category_contract_ready: bool = True
    operator_executed_execution_boundary_ready: bool = True
    operator_result_handoff_safe: bool = True
    operator_result_category: str = OperatorExecutionResultCategory.NOT_PROVIDED.value
    operator_result_category_is_safe_label: bool = True
    operator_result_category_is_allowed: bool = True
    ready_confirmed_is_not_post_permission: bool = True
    not_provided_is_not_actual_receipt: bool = True
    receipt_current_turn: bool = True
    receipt_fresh: bool = True
    receipt_stale: bool = False
    receipt_reused: bool = False
    receipt_previous_turn: bool = False
    receipt_expired: bool = False
    receipt_timeout: bool = False
    receipt_unknown: bool = False
    receipt_failed: bool = False
    receipt_unavailable: bool = False
    receipt_raw_value_present: bool = False
    receipt_detail_present: bool = False
    receipt_id_present: bool = False
    receipt_token_present: bool = False
    receipt_nonce_present: bool = False
    receipt_hash_present: bool = False
    receipt_fingerprint_present: bool = False
    receipt_length_present: bool = False
    receipt_saved: bool = False
    receipt_displayed: bool = False
    receipt_broadly_propagated: bool = False
    operator_result_detail_present: bool = False
    operator_result_raw_value_present: bool = False
    checker_result_detail_present: bool = False
    env_variable_names_present: bool = False
    credential_values_present: bool = False
    credential_metadata_present: bool = False
    sentinel_value_present: bool = False
    actual_receipt_handoff_executed: bool = False
    actual_result_receipt_received: bool = False
    actual_checker_execution_performed: bool = False
    actual_execution_performed: bool = False
    codex_execution_performed: bool = False
    env_access_requested: bool = False
    credential_read_performed: bool = False
    can_generate_real_signature: bool = False
    can_generate_real_headers: bool = False
    can_execute_http_post: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    final_confirmation_received: bool = False
    fresh_preflight_executed: bool = False
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("lifecycle_mode", self.lifecycle_mode)
        _require_non_empty("from_state", self.from_state)
        _require_non_empty("lifecycle_event", self.lifecycle_event)
        _require_non_empty("operator_result_category", self.operator_result_category)
        _validate_bool_fields(
            self,
            (
                "lifecycle_declared",
                "lifecycle_transition_policy_declared",
                "one_time_required",
                "fresh_required",
                "current_turn_required",
                "non_reuse_required",
                "previous_turn_prohibited",
                "stale_prohibited",
                "timeout_prohibited",
                "expired_prohibited",
                "non_raw_required",
                "non_detail_required",
                "non_identifier_required",
                "safe_category_only",
                "operator_result_handoff_policy_ready",
                "operator_execution_result_category_contract_ready",
                "operator_executed_execution_boundary_ready",
                "operator_result_handoff_safe",
                "operator_result_category_is_safe_label",
                "operator_result_category_is_allowed",
                "ready_confirmed_is_not_post_permission",
                "not_provided_is_not_actual_receipt",
                "receipt_current_turn",
                "receipt_fresh",
                "receipt_stale",
                "receipt_reused",
                "receipt_previous_turn",
                "receipt_expired",
                "receipt_timeout",
                "receipt_unknown",
                "receipt_failed",
                "receipt_unavailable",
                "receipt_raw_value_present",
                "receipt_detail_present",
                "receipt_id_present",
                "receipt_token_present",
                "receipt_nonce_present",
                "receipt_hash_present",
                "receipt_fingerprint_present",
                "receipt_length_present",
                "receipt_saved",
                "receipt_displayed",
                "receipt_broadly_propagated",
                "operator_result_detail_present",
                "operator_result_raw_value_present",
                "checker_result_detail_present",
                "env_variable_names_present",
                "credential_values_present",
                "credential_metadata_present",
                "sentinel_value_present",
                "actual_receipt_handoff_executed",
                "actual_result_receipt_received",
                "actual_checker_execution_performed",
                "actual_execution_performed",
                "codex_execution_performed",
                "env_access_requested",
                "credential_read_performed",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "can_execute_http_post",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "final_confirmation_received",
                "fresh_preflight_executed",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealOperatorResultHandoffLifecycleCheckResult:
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
class LiveOrderRealOperatorResultHandoffLifecycleResult:
    status: LiveOrderRealOperatorResultHandoffLifecycleStatus
    operator_result_handoff_lifecycle_ready: bool
    lifecycle_mode: str
    from_state: str
    to_state: str
    lifecycle_event: str
    unsupported_mode_present: bool
    unsupported_state_present: bool
    unsupported_event_present: bool
    unsupported_category_present: bool
    lifecycle_declared: bool
    lifecycle_transition_policy_declared: bool
    one_time_required: bool
    fresh_required: bool
    current_turn_required: bool
    non_reuse_required: bool
    previous_turn_prohibited: bool
    stale_prohibited: bool
    timeout_prohibited: bool
    expired_prohibited: bool
    non_raw_required: bool
    non_detail_required: bool
    non_identifier_required: bool
    safe_category_only: bool
    operator_result_handoff_policy_ready: bool
    operator_execution_result_category_contract_ready: bool
    operator_executed_execution_boundary_ready: bool
    operator_result_handoff_safe: bool
    operator_result_category: str
    operator_result_category_is_safe_label: bool
    operator_result_category_is_allowed: bool
    ready_confirmed_is_not_post_permission: bool
    not_provided_is_not_actual_receipt: bool
    receipt_current_turn: bool
    receipt_fresh: bool
    receipt_stale: bool
    receipt_reused: bool
    receipt_previous_turn: bool
    receipt_expired: bool
    receipt_timeout: bool
    receipt_unknown: bool
    receipt_failed: bool
    receipt_unavailable: bool
    receipt_raw_value_present: bool
    receipt_detail_present: bool
    receipt_id_present: bool
    receipt_token_present: bool
    receipt_nonce_present: bool
    receipt_hash_present: bool
    receipt_fingerprint_present: bool
    receipt_length_present: bool
    receipt_saved: bool
    receipt_displayed: bool
    receipt_broadly_propagated: bool
    operator_result_detail_present: bool
    operator_result_raw_value_present: bool
    checker_result_detail_present: bool
    env_variable_names_present: bool
    credential_values_present: bool
    credential_metadata_present: bool
    sentinel_value_present: bool
    actual_receipt_handoff_executed: bool
    actual_result_receipt_received: bool
    actual_checker_execution_performed: bool
    actual_execution_performed: bool
    codex_execution_performed: bool
    env_access_requested: bool
    credential_read_performed: bool
    can_generate_real_signature: bool
    can_generate_real_headers: bool
    can_execute_http_post: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_executed: bool
    final_confirmation_received: bool
    fresh_preflight_executed: bool
    safe_to_render: bool
    safe_to_serialize: bool
    check_results: tuple[LiveOrderRealOperatorResultHandoffLifecycleCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealOperatorResultHandoffLifecycleStatus):
            raise LiveVerificationValidationError(
                "status must be operator result handoff lifecycle status",
            )
        for field_name in (
            "lifecycle_mode",
            "from_state",
            "to_state",
            "lifecycle_event",
            "operator_result_category",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_bool_fields(
            self,
            (
                "operator_result_handoff_lifecycle_ready",
                "unsupported_mode_present",
                "unsupported_state_present",
                "unsupported_event_present",
                "unsupported_category_present",
                "lifecycle_declared",
                "lifecycle_transition_policy_declared",
                "one_time_required",
                "fresh_required",
                "current_turn_required",
                "non_reuse_required",
                "previous_turn_prohibited",
                "stale_prohibited",
                "timeout_prohibited",
                "expired_prohibited",
                "non_raw_required",
                "non_detail_required",
                "non_identifier_required",
                "safe_category_only",
                "operator_result_handoff_policy_ready",
                "operator_execution_result_category_contract_ready",
                "operator_executed_execution_boundary_ready",
                "operator_result_handoff_safe",
                "operator_result_category_is_safe_label",
                "operator_result_category_is_allowed",
                "ready_confirmed_is_not_post_permission",
                "not_provided_is_not_actual_receipt",
                "receipt_current_turn",
                "receipt_fresh",
                "receipt_stale",
                "receipt_reused",
                "receipt_previous_turn",
                "receipt_expired",
                "receipt_timeout",
                "receipt_unknown",
                "receipt_failed",
                "receipt_unavailable",
                "receipt_raw_value_present",
                "receipt_detail_present",
                "receipt_id_present",
                "receipt_token_present",
                "receipt_nonce_present",
                "receipt_hash_present",
                "receipt_fingerprint_present",
                "receipt_length_present",
                "receipt_saved",
                "receipt_displayed",
                "receipt_broadly_propagated",
                "operator_result_detail_present",
                "operator_result_raw_value_present",
                "checker_result_detail_present",
                "env_variable_names_present",
                "credential_values_present",
                "credential_metadata_present",
                "sentinel_value_present",
                "actual_receipt_handoff_executed",
                "actual_result_receipt_received",
                "actual_checker_execution_performed",
                "actual_execution_performed",
                "codex_execution_performed",
                "env_access_requested",
                "credential_read_performed",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "can_execute_http_post",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "final_confirmation_received",
                "fresh_preflight_executed",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_operator_result_handoff_lifecycle(
    *,
    input_snapshot: LiveOrderRealOperatorResultHandoffLifecycleInput | None = None,
) -> LiveOrderRealOperatorResultHandoffLifecycleResult:
    """Build sanitized receipt lifecycle metadata only."""
    return transition_live_order_real_operator_result_handoff_lifecycle(
        input_snapshot=input_snapshot,
    )


def transition_live_order_real_operator_result_handoff_lifecycle(
    *,
    input_snapshot: LiveOrderRealOperatorResultHandoffLifecycleInput | None = None,
) -> LiveOrderRealOperatorResultHandoffLifecycleResult:
    """Apply a pure safe-label lifecycle transition without side effects."""
    lifecycle_input = input_snapshot or LiveOrderRealOperatorResultHandoffLifecycleInput()
    safe_mode = _safe_lifecycle_mode(lifecycle_input.lifecycle_mode)
    safe_from_state = _safe_lifecycle_state(lifecycle_input.from_state)
    safe_event = _safe_lifecycle_event(lifecycle_input.lifecycle_event)
    safe_category = _safe_category_label(lifecycle_input.operator_result_category)
    unsupported_mode_present = _has_unsupported_mode(lifecycle_input.lifecycle_mode)
    unsupported_state_present = _has_unsupported_state(lifecycle_input.from_state)
    unsupported_event_present = _has_unsupported_event(lifecycle_input.lifecycle_event)
    unsupported_category_present = _has_unsupported_category(
        lifecycle_input.operator_result_category,
    )

    input_reasons = _input_reasons(lifecycle_input)
    unsupported_reasons = _unsupported_reasons(lifecycle_input)
    unsafe_category_reasons = _unsafe_category_reasons(lifecycle_input)
    stale_reasons = _stale_reasons(lifecycle_input)
    reused_reasons = _reused_reasons(lifecycle_input)
    previous_turn_reasons = _previous_turn_reasons(lifecycle_input)
    timeout_reasons = _timeout_reasons(lifecycle_input)
    expired_reasons = _expired_reasons(lifecycle_input)
    unknown_reasons = _unknown_reasons(lifecycle_input)
    failed_reasons = _failed_reasons(lifecycle_input)
    unavailable_reasons = _unavailable_reasons(lifecycle_input)
    raw_reasons = _raw_receipt_reasons(lifecycle_input)
    detail_reasons = _detail_exposure_reasons(lifecycle_input)
    identifier_reasons = _identifier_exposure_reasons(lifecycle_input)
    env_or_credential_reasons = _env_or_credential_reasons(lifecycle_input)
    actual_execution_reasons = _actual_execution_reasons(lifecycle_input)
    actual_receipt_reasons = _actual_receipt_reasons(lifecycle_input)
    live_order_once_reasons = _live_order_once_reasons(lifecycle_input)
    api_or_post_reasons = _api_or_post_reasons(lifecycle_input)
    final_confirmation_reasons = _final_confirmation_reasons(lifecycle_input)
    fresh_preflight_reasons = _fresh_preflight_reasons(lifecycle_input)
    display_reasons = _display_or_save_reasons(lifecycle_input)

    if input_reasons:
        status = LifecycleStatus.LIFECYCLE_NOT_READY
        primary_reasons = input_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif unsupported_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_UNSUPPORTED
        primary_reasons = unsupported_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif unsafe_category_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_UNSUPPORTED
        primary_reasons = unsafe_category_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif stale_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_STALE
        primary_reasons = stale_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif reused_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_REUSED
        primary_reasons = reused_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif previous_turn_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_PREVIOUS_TURN
        primary_reasons = previous_turn_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif timeout_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_TIMEOUT
        primary_reasons = timeout_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif expired_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_EXPIRED
        primary_reasons = expired_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif unknown_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_UNKNOWN
        primary_reasons = unknown_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif failed_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_FAILED
        primary_reasons = failed_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif unavailable_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_UNAVAILABLE
        primary_reasons = unavailable_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif raw_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_RAW_RECEIPT
        primary_reasons = raw_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif detail_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_DETAIL_EXPOSURE
        primary_reasons = detail_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif identifier_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_IDENTIFIER_EXPOSURE
        primary_reasons = identifier_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif env_or_credential_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_ENV_OR_CREDENTIAL
        primary_reasons = env_or_credential_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif actual_execution_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_ACTUAL_EXECUTION
        primary_reasons = actual_execution_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif actual_receipt_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_ACTUAL_RECEIPT
        primary_reasons = actual_receipt_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif live_order_once_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_LIVE_ORDER_ONCE
        primary_reasons = live_order_once_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif api_or_post_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_API_OR_POST
        primary_reasons = api_or_post_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif final_confirmation_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_FINAL_CONFIRMATION
        primary_reasons = final_confirmation_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif fresh_preflight_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_FRESH_PREFLIGHT
        primary_reasons = fresh_preflight_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif display_reasons:
        status = LifecycleStatus.LIFECYCLE_BLOCKED_DETAIL_EXPOSURE
        primary_reasons = display_reasons
        to_state = LifecycleState.LIFECYCLE_BLOCKED.value
    elif (
        safe_category == OperatorExecutionResultCategory.READY_CONFIRMED.value
        or safe_event == LifecycleEvent.DECLARE_SAFE_CATEGORY_READY_CONFIRMED.value
    ):
        status = LifecycleStatus.LIFECYCLE_READY_CONFIRMED_NO_POST
        primary_reasons = ()
        to_state = LifecycleState.LIFECYCLE_READY_CONFIRMED_NO_POST.value
    elif safe_event == LifecycleEvent.DECLARE_POLICY_READY.value:
        status = LifecycleStatus.LIFECYCLE_READY_NO_RECEIPT
        primary_reasons = ()
        to_state = LifecycleState.LIFECYCLE_POLICY_READY.value
    else:
        status = LifecycleStatus.LIFECYCLE_RECEIPT_NOT_PROVIDED_NO_ACTUAL_RECEIPT
        primary_reasons = ()
        to_state = LifecycleState.LIFECYCLE_RECEIPT_NOT_PROVIDED.value

    blocked_reasons = _merge_reasons(
        primary_reasons,
        input_reasons,
        unsupported_reasons,
        unsafe_category_reasons,
        stale_reasons,
        reused_reasons,
        previous_turn_reasons,
        timeout_reasons,
        expired_reasons,
        unknown_reasons,
        failed_reasons,
        unavailable_reasons,
        raw_reasons,
        detail_reasons,
        identifier_reasons,
        env_or_credential_reasons,
        actual_execution_reasons,
        actual_receipt_reasons,
        live_order_once_reasons,
        api_or_post_reasons,
        final_confirmation_reasons,
        fresh_preflight_reasons,
        display_reasons,
    )
    ready = status in (
        LifecycleStatus.LIFECYCLE_READY_NO_RECEIPT,
        LifecycleStatus.LIFECYCLE_RECEIPT_NOT_PROVIDED_NO_ACTUAL_RECEIPT,
        LifecycleStatus.LIFECYCLE_READY_CONFIRMED_NO_POST,
    )

    return LiveOrderRealOperatorResultHandoffLifecycleResult(
        status=status,
        operator_result_handoff_lifecycle_ready=ready,
        lifecycle_mode=safe_mode,
        from_state=safe_from_state,
        to_state=to_state,
        lifecycle_event=safe_event,
        unsupported_mode_present=unsupported_mode_present,
        unsupported_state_present=unsupported_state_present,
        unsupported_event_present=unsupported_event_present,
        unsupported_category_present=unsupported_category_present,
        lifecycle_declared=lifecycle_input.lifecycle_declared,
        lifecycle_transition_policy_declared=(
            lifecycle_input.lifecycle_transition_policy_declared
        ),
        one_time_required=lifecycle_input.one_time_required,
        fresh_required=lifecycle_input.fresh_required,
        current_turn_required=lifecycle_input.current_turn_required,
        non_reuse_required=lifecycle_input.non_reuse_required,
        previous_turn_prohibited=lifecycle_input.previous_turn_prohibited,
        stale_prohibited=lifecycle_input.stale_prohibited,
        timeout_prohibited=lifecycle_input.timeout_prohibited,
        expired_prohibited=lifecycle_input.expired_prohibited,
        non_raw_required=lifecycle_input.non_raw_required,
        non_detail_required=lifecycle_input.non_detail_required,
        non_identifier_required=lifecycle_input.non_identifier_required,
        safe_category_only=lifecycle_input.safe_category_only,
        operator_result_handoff_policy_ready=(
            lifecycle_input.operator_result_handoff_policy_ready
        ),
        operator_execution_result_category_contract_ready=(
            lifecycle_input.operator_execution_result_category_contract_ready
        ),
        operator_executed_execution_boundary_ready=(
            lifecycle_input.operator_executed_execution_boundary_ready
        ),
        operator_result_handoff_safe=lifecycle_input.operator_result_handoff_safe,
        operator_result_category=safe_category,
        operator_result_category_is_safe_label=(
            lifecycle_input.operator_result_category_is_safe_label
            and not unsupported_category_present
        ),
        operator_result_category_is_allowed=(
            lifecycle_input.operator_result_category_is_allowed
            and not unsupported_category_present
        ),
        ready_confirmed_is_not_post_permission=(
            lifecycle_input.ready_confirmed_is_not_post_permission
        ),
        not_provided_is_not_actual_receipt=(
            lifecycle_input.not_provided_is_not_actual_receipt
        ),
        receipt_current_turn=lifecycle_input.receipt_current_turn,
        receipt_fresh=lifecycle_input.receipt_fresh,
        receipt_stale=False,
        receipt_reused=False,
        receipt_previous_turn=False,
        receipt_expired=False,
        receipt_timeout=False,
        receipt_unknown=False,
        receipt_failed=False,
        receipt_unavailable=False,
        receipt_raw_value_present=False,
        receipt_detail_present=False,
        receipt_id_present=False,
        receipt_token_present=False,
        receipt_nonce_present=False,
        receipt_hash_present=False,
        receipt_fingerprint_present=False,
        receipt_length_present=False,
        receipt_saved=False,
        receipt_displayed=False,
        receipt_broadly_propagated=False,
        operator_result_detail_present=False,
        operator_result_raw_value_present=False,
        checker_result_detail_present=False,
        env_variable_names_present=False,
        credential_values_present=False,
        credential_metadata_present=False,
        sentinel_value_present=False,
        actual_receipt_handoff_executed=False,
        actual_result_receipt_received=False,
        actual_checker_execution_performed=False,
        actual_execution_performed=False,
        codex_execution_performed=False,
        env_access_requested=False,
        credential_read_performed=False,
        can_generate_real_signature=False,
        can_generate_real_headers=False,
        can_execute_http_post=False,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_executed=False,
        final_confirmation_received=False,
        fresh_preflight_executed=False,
        safe_to_render=True,
        safe_to_serialize=True,
        check_results=_build_check_results(lifecycle_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            OPERATOR_RESULT_HANDOFF_LIFECYCLE_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_operator_result_handoff_lifecycle_blockers_no_env_no_post"
        ),
    )


def render_live_order_real_operator_result_handoff_lifecycle_markdown(
    result: LiveOrderRealOperatorResultHandoffLifecycleResult,
) -> str:
    """Render sanitized receipt lifecycle metadata only."""
    lines = [
        "# Step 6G Operator Result Handoff Lifecycle",
        "",
        "This operator result handoff lifecycle contract is skeleton-only.",
        "This lifecycle does not perform actual receipt handoff.",
        "This lifecycle does not receive actual result receipts.",
        "This lifecycle does not execute the checker.",
        "This lifecycle does not access env or .env.",
        "This lifecycle does not read credentials.",
        "This lifecycle uses safe state, event, category, and boolean labels only.",
        "This lifecycle does not expose raw receipt or operator result values.",
        "This lifecycle does not expose receipt identifiers.",
        "READY_CONFIRMED is not POST permission.",
        "READY_CONFIRMED is not final confirmation.",
        "READY_CONFIRMED is not fresh preflight.",
        "NOT_PROVIDED is not an actual result receipt.",
        (
            "Unknown / failed / unavailable / stale / timeout / expired / "
            "reused / previous-turn lifecycle states fail closed."
        ),
        "This lifecycle does not generate real signatures.",
        "This lifecycle does not execute API calls.",
        "This lifecycle does not execute HTTP POST.",
        "This lifecycle does not call order endpoint.",
        "This lifecycle does not call live_order_once.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- operator_result_handoff_lifecycle_ready: "
            f"{_bool_text(result.operator_result_handoff_lifecycle_ready)}"
        ),
        f"- lifecycle_mode: {result.lifecycle_mode}",
        f"- from_state: {result.from_state}",
        f"- to_state: {result.to_state}",
        f"- lifecycle_event: {result.lifecycle_event}",
        f"- lifecycle_declared: {_bool_text(result.lifecycle_declared)}",
        (
            "- lifecycle_transition_policy_declared: "
            f"{_bool_text(result.lifecycle_transition_policy_declared)}"
        ),
        f"- one_time_required: {_bool_text(result.one_time_required)}",
        f"- fresh_required: {_bool_text(result.fresh_required)}",
        f"- current_turn_required: {_bool_text(result.current_turn_required)}",
        f"- non_reuse_required: {_bool_text(result.non_reuse_required)}",
        (
            "- previous_turn_prohibited: "
            f"{_bool_text(result.previous_turn_prohibited)}"
        ),
        f"- stale_prohibited: {_bool_text(result.stale_prohibited)}",
        f"- timeout_prohibited: {_bool_text(result.timeout_prohibited)}",
        f"- expired_prohibited: {_bool_text(result.expired_prohibited)}",
        f"- non_raw_required: {_bool_text(result.non_raw_required)}",
        f"- non_detail_required: {_bool_text(result.non_detail_required)}",
        (
            "- non_identifier_required: "
            f"{_bool_text(result.non_identifier_required)}"
        ),
        f"- safe_category_only: {_bool_text(result.safe_category_only)}",
        f"- operator_result_category: {result.operator_result_category}",
        (
            "- ready_confirmed_is_not_post_permission: "
            f"{_bool_text(result.ready_confirmed_is_not_post_permission)}"
        ),
        (
            "- not_provided_is_not_actual_receipt: "
            f"{_bool_text(result.not_provided_is_not_actual_receipt)}"
        ),
        f"- receipt_current_turn: {_bool_text(result.receipt_current_turn)}",
        f"- receipt_fresh: {_bool_text(result.receipt_fresh)}",
        f"- receipt_reused: {_bool_text(result.receipt_reused)}",
        f"- receipt_previous_turn: {_bool_text(result.receipt_previous_turn)}",
        f"- receipt_timeout: {_bool_text(result.receipt_timeout)}",
        f"- receipt_raw_value_present: {_bool_text(result.receipt_raw_value_present)}",
        f"- receipt_detail_present: {_bool_text(result.receipt_detail_present)}",
        f"- receipt_id_present: {_bool_text(result.receipt_id_present)}",
        f"- receipt_token_present: {_bool_text(result.receipt_token_present)}",
        f"- actual_receipt_handoff_executed: {_bool_text(result.actual_receipt_handoff_executed)}",
        f"- actual_result_receipt_received: {_bool_text(result.actual_result_receipt_received)}",
        (
            "- actual_checker_execution_performed: "
            f"{_bool_text(result.actual_checker_execution_performed)}"
        ),
        f"- final_confirmation_received: {_bool_text(result.final_confirmation_received)}",
        f"- fresh_preflight_executed: {_bool_text(result.fresh_preflight_executed)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def _build_check_results(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[LiveOrderRealOperatorResultHandoffLifecycleCheckResult, ...]:
    groups = (
        (
            "lifecycle contract input",
            _input_reasons(lifecycle_input),
            "lifecycle skeleton prerequisites ready",
        ),
        (
            "safe labels",
            _merge_reasons(
                _unsupported_reasons(lifecycle_input),
                _unsafe_category_reasons(lifecycle_input),
            ),
            "mode state event and category are safe labels",
        ),
        (
            "fresh current one-time lifecycle",
            _merge_reasons(
                _stale_reasons(lifecycle_input),
                _reused_reasons(lifecycle_input),
                _previous_turn_reasons(lifecycle_input),
                _timeout_reasons(lifecycle_input),
                _expired_reasons(lifecycle_input),
            ),
            "receipt lifecycle is fresh current non-reused and not timed out",
        ),
        (
            "known lifecycle state",
            _merge_reasons(
                _unknown_reasons(lifecycle_input),
                _failed_reasons(lifecycle_input),
                _unavailable_reasons(lifecycle_input),
            ),
            "lifecycle state is not unknown failed or unavailable",
        ),
        (
            "no raw detail identifier",
            _merge_reasons(
                _raw_receipt_reasons(lifecycle_input),
                _detail_exposure_reasons(lifecycle_input),
                _identifier_exposure_reasons(lifecycle_input),
            ),
            "no raw detail or identifier exposure",
        ),
        (
            "no env credential",
            _env_or_credential_reasons(lifecycle_input),
            "no env access credential read values or metadata",
        ),
        (
            "no actual execution or receipt",
            _merge_reasons(
                _actual_execution_reasons(lifecycle_input),
                _actual_receipt_reasons(lifecycle_input),
            ),
            "no checker execution actual receipt handoff or result receipt",
        ),
        (
            "no API POST live order",
            _merge_reasons(
                _api_or_post_reasons(lifecycle_input),
                _live_order_once_reasons(lifecycle_input),
            ),
            "no API POST endpoint or live_order_once",
        ),
        (
            "no final confirmation or preflight",
            _merge_reasons(
                _final_confirmation_reasons(lifecycle_input),
                _fresh_preflight_reasons(lifecycle_input),
            ),
            "no final confirmation or fresh preflight",
        ),
        (
            "safe render and serialization",
            _display_or_save_reasons(lifecycle_input),
            "render and serialization are safe",
        ),
    )
    return tuple(
        LiveOrderRealOperatorResultHandoffLifecycleCheckResult(
            name=name,
            passed=not reasons,
            sanitized_value="pass" if not reasons else "blocked",
            expected=expected,
        )
        for name, reasons, expected in groups
    )


def _input_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_unsupported_mode(lifecycle_input.lifecycle_mode):
        reasons.append("lifecycle_mode_not_skeleton_only")
    for field_name, reason in (
        ("lifecycle_declared", "lifecycle_not_declared"),
        (
            "lifecycle_transition_policy_declared",
            "lifecycle_transition_policy_not_declared",
        ),
        ("one_time_required", "one_time_not_required"),
        ("fresh_required", "fresh_not_required"),
        ("current_turn_required", "current_turn_not_required"),
        ("non_reuse_required", "non_reuse_not_required"),
        ("previous_turn_prohibited", "previous_turn_not_prohibited"),
        ("stale_prohibited", "stale_not_prohibited"),
        ("timeout_prohibited", "timeout_not_prohibited"),
        ("expired_prohibited", "expired_not_prohibited"),
        ("non_raw_required", "non_raw_not_required"),
        ("non_detail_required", "non_detail_not_required"),
        ("non_identifier_required", "non_identifier_not_required"),
        ("safe_category_only", "safe_category_only_not_required"),
        (
            "operator_result_handoff_policy_ready",
            "operator_result_handoff_policy_not_ready",
        ),
        (
            "operator_execution_result_category_contract_ready",
            "category_contract_not_ready",
        ),
        (
            "operator_executed_execution_boundary_ready",
            "execution_boundary_not_ready",
        ),
        ("operator_result_handoff_safe", "operator_handoff_not_safe"),
        (
            "ready_confirmed_is_not_post_permission",
            "ready_confirmed_post_boundary_not_fixed",
        ),
        (
            "not_provided_is_not_actual_receipt",
            "not_provided_actual_receipt_boundary_not_fixed",
        ),
    ):
        if not getattr(lifecycle_input, field_name):
            reasons.append(reason)
    return tuple(reasons)


def _unsupported_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_unsupported_state(lifecycle_input.from_state):
        reasons.append("unsupported_lifecycle_state")
    if _has_unsupported_event(lifecycle_input.lifecycle_event):
        reasons.append("unsupported_lifecycle_event")
    if _has_unsupported_category(lifecycle_input.operator_result_category):
        reasons.append("unsupported_operator_result_category")
    return tuple(reasons)


def _unsafe_category_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not lifecycle_input.operator_result_category_is_safe_label:
        reasons.append("operator_result_category_not_safe_label")
    if not lifecycle_input.operator_result_category_is_allowed:
        reasons.append("operator_result_category_not_allowed")
    return tuple(reasons)


def _stale_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    if (
        lifecycle_input.receipt_stale
        or lifecycle_input.lifecycle_event == LifecycleEvent.DECLARE_STALE.value
        or lifecycle_input.operator_result_category
        == OperatorExecutionResultCategory.BLOCKED_STALE.value
    ):
        return ("receipt_stale",)
    return ()


def _reused_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    if (
        lifecycle_input.receipt_reused
        or lifecycle_input.lifecycle_event == LifecycleEvent.DECLARE_REUSED.value
        or lifecycle_input.operator_result_category
        == OperatorExecutionResultCategory.BLOCKED_REUSED.value
    ):
        return ("receipt_reused",)
    return ()


def _previous_turn_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        lifecycle_input.receipt_previous_turn
        or lifecycle_input.lifecycle_event == LifecycleEvent.DECLARE_PREVIOUS_TURN.value
        or lifecycle_input.operator_result_category
        == OperatorExecutionResultCategory.BLOCKED_PREVIOUS_TURN.value
    ):
        reasons.append("receipt_previous_turn")
    if not lifecycle_input.receipt_current_turn:
        reasons.append("receipt_not_current_turn")
    if not lifecycle_input.receipt_fresh:
        reasons.append("receipt_not_fresh")
    return tuple(reasons)


def _timeout_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    if (
        lifecycle_input.receipt_timeout
        or lifecycle_input.lifecycle_event == LifecycleEvent.DECLARE_TIMEOUT.value
        or lifecycle_input.operator_result_category
        == OperatorExecutionResultCategory.BLOCKED_TIMEOUT.value
    ):
        return ("receipt_timeout",)
    return ()


def _expired_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    if lifecycle_input.receipt_expired:
        return ("receipt_expired",)
    return ()


def _unknown_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    if (
        lifecycle_input.receipt_unknown
        or lifecycle_input.lifecycle_event == LifecycleEvent.DECLARE_UNKNOWN.value
        or lifecycle_input.operator_result_category
        == OperatorExecutionResultCategory.BLOCKED_UNKNOWN.value
    ):
        return ("receipt_unknown",)
    return ()


def _failed_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    if (
        lifecycle_input.receipt_failed
        or lifecycle_input.lifecycle_event == LifecycleEvent.DECLARE_FAILED.value
        or lifecycle_input.operator_result_category
        == OperatorExecutionResultCategory.BLOCKED_FAILED.value
    ):
        return ("receipt_failed",)
    return ()


def _unavailable_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    if (
        lifecycle_input.receipt_unavailable
        or lifecycle_input.lifecycle_event == LifecycleEvent.DECLARE_UNAVAILABLE.value
        or lifecycle_input.operator_result_category
        == OperatorExecutionResultCategory.BLOCKED_UNAVAILABLE.value
    ):
        return ("receipt_unavailable",)
    return ()


def _raw_receipt_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    if (
        lifecycle_input.receipt_raw_value_present
        or lifecycle_input.operator_result_raw_value_present
        or lifecycle_input.lifecycle_event == LifecycleEvent.DECLARE_RAW_PRESENT.value
    ):
        return ("raw_receipt_present",)
    return ()


def _detail_exposure_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "receipt_detail_present",
        "operator_result_detail_present",
        "checker_result_detail_present",
        "sentinel_value_present",
        "receipt_saved",
        "receipt_displayed",
        "receipt_broadly_propagated",
    ):
        if getattr(lifecycle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    if lifecycle_input.lifecycle_event == LifecycleEvent.DECLARE_DETAIL_PRESENT.value:
        reasons.append("detail_present_event")
    return tuple(reasons)


def _identifier_exposure_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "receipt_id_present",
        "receipt_token_present",
        "receipt_nonce_present",
        "receipt_hash_present",
        "receipt_fingerprint_present",
        "receipt_length_present",
    ):
        if getattr(lifecycle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    if lifecycle_input.lifecycle_event == LifecycleEvent.DECLARE_IDENTIFIER_PRESENT.value:
        reasons.append("identifier_present_event")
    return tuple(reasons)


def _env_or_credential_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "env_variable_names_present",
        "credential_values_present",
        "credential_metadata_present",
        "env_access_requested",
        "credential_read_performed",
    ):
        if getattr(lifecycle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _actual_execution_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "actual_checker_execution_performed",
        "actual_execution_performed",
        "codex_execution_performed",
    ):
        if getattr(lifecycle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _actual_receipt_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if lifecycle_input.lifecycle_event == (
        LifecycleEvent.DECLARE_ACTUAL_RECEIPT_ATTEMPTED.value
    ):
        reasons.append("actual_receipt_attempted_event")
    for field_name in (
        "actual_receipt_handoff_executed",
        "actual_result_receipt_received",
    ):
        if getattr(lifecycle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _api_or_post_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if lifecycle_input.lifecycle_event == (
        LifecycleEvent.DECLARE_API_OR_POST_ATTEMPTED.value
    ):
        reasons.append("api_or_post_attempted_event")
    for field_name in (
        "can_generate_real_signature",
        "can_generate_real_headers",
        "can_execute_http_post",
        "http_post_executed",
        "order_endpoint_called",
        "post_allowed_this_step",
        "post_executed",
    ):
        if getattr(lifecycle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _live_order_once_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    if lifecycle_input.live_order_once_called:
        return ("live_order_once_called",)
    return ()


def _final_confirmation_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    if lifecycle_input.final_confirmation_received:
        return ("final_confirmation_received",)
    return ()


def _fresh_preflight_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    if lifecycle_input.fresh_preflight_executed:
        return ("fresh_preflight_executed",)
    return ()


def _display_or_save_reasons(
    lifecycle_input: LiveOrderRealOperatorResultHandoffLifecycleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not lifecycle_input.safe_to_render:
        reasons.append("render_not_safe")
    if not lifecycle_input.safe_to_serialize:
        reasons.append("serialize_not_safe")
    return tuple(reasons)


def _validate_result_safety(
    result: LiveOrderRealOperatorResultHandoffLifecycleResult,
) -> None:
    unsafe_true_fields = (
        "receipt_stale",
        "receipt_reused",
        "receipt_previous_turn",
        "receipt_expired",
        "receipt_timeout",
        "receipt_unknown",
        "receipt_failed",
        "receipt_unavailable",
        "receipt_raw_value_present",
        "receipt_detail_present",
        "receipt_id_present",
        "receipt_token_present",
        "receipt_nonce_present",
        "receipt_hash_present",
        "receipt_fingerprint_present",
        "receipt_length_present",
        "receipt_saved",
        "receipt_displayed",
        "receipt_broadly_propagated",
        "operator_result_detail_present",
        "operator_result_raw_value_present",
        "checker_result_detail_present",
        "env_variable_names_present",
        "credential_values_present",
        "credential_metadata_present",
        "sentinel_value_present",
        "actual_receipt_handoff_executed",
        "actual_result_receipt_received",
        "actual_checker_execution_performed",
        "actual_execution_performed",
        "codex_execution_performed",
        "env_access_requested",
        "credential_read_performed",
        "can_generate_real_signature",
        "can_generate_real_headers",
        "can_execute_http_post",
        "http_post_executed",
        "order_endpoint_called",
        "live_order_once_called",
        "post_allowed_this_step",
        "post_executed",
        "final_confirmation_received",
        "fresh_preflight_executed",
    )
    for field_name in unsafe_true_fields:
        if getattr(result, field_name):
            raise LiveVerificationValidationError(f"{field_name} must remain false")
    if not result.safe_to_render:
        raise LiveVerificationValidationError("lifecycle result must remain render safe")
    if not result.safe_to_serialize:
        raise LiveVerificationValidationError(
            "lifecycle result must remain serialization safe",
        )


def _safe_lifecycle_mode(lifecycle_mode: str) -> str:
    if not _has_unsupported_mode(lifecycle_mode):
        return lifecycle_mode
    return LifecycleMode.OPERATOR_RESULT_HANDOFF_LIFECYCLE_SKELETON_ONLY.value


def _safe_lifecycle_state(lifecycle_state: str) -> str:
    if not _has_unsupported_state(lifecycle_state):
        return lifecycle_state
    return UNSUPPORTED_OPERATOR_RESULT_HANDOFF_LIFECYCLE_LABEL


def _safe_lifecycle_event(lifecycle_event: str) -> str:
    if not _has_unsupported_event(lifecycle_event):
        return lifecycle_event
    return UNSUPPORTED_OPERATOR_RESULT_HANDOFF_LIFECYCLE_LABEL


def _safe_category_label(operator_result_category: str) -> str:
    if operator_result_category in {
        category.value for category in OperatorExecutionResultCategory
    }:
        return operator_result_category
    return UNSUPPORTED_OPERATOR_RESULT_HANDOFF_LIFECYCLE_LABEL


def _has_unsupported_mode(lifecycle_mode: str) -> bool:
    return lifecycle_mode != LifecycleMode.OPERATOR_RESULT_HANDOFF_LIFECYCLE_SKELETON_ONLY.value


def _has_unsupported_state(lifecycle_state: str) -> bool:
    return lifecycle_state not in {state.value for state in LifecycleState}


def _has_unsupported_event(lifecycle_event: str) -> bool:
    return lifecycle_event not in {event.value for event in LifecycleEvent}


def _has_unsupported_category(operator_result_category: str) -> bool:
    return operator_result_category not in {
        category.value for category in OperatorExecutionResultCategory
    }


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _require_non_empty(name: str, value: str) -> None:
    if not value:
        raise LiveVerificationValidationError(f"{name} must be non-empty")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")
