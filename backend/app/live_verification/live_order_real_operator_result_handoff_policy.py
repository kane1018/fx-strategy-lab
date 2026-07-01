"""Step 6G operator result handoff policy hardening skeleton.

This module defines only the safe policy layer for a future operator receipt
handoff. It does not implement actual receipt handoff, receive actual results,
execute a checker, read env, inspect credentials, call APIs, or execute HTTP
POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_operator_execution_result_category_contract import (
    LiveOrderRealOperatorExecutionResultCategory,
)

OPERATOR_RESULT_HANDOFF_POLICY_RECOMMENDED_NEXT_STEP = (
    "operator_result_handoff_policy_boundary_review_no_env_no_api_no_post"
)
UNSUPPORTED_OPERATOR_RESULT_HANDOFF_POLICY_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealOperatorResultHandoffPolicyStatus(str, Enum):
    OPERATOR_RESULT_HANDOFF_POLICY_READY_NO_RECEIPT = (
        "OPERATOR_RESULT_HANDOFF_POLICY_READY_NO_RECEIPT"
    )
    OPERATOR_RESULT_HANDOFF_POLICY_READY_CONFIRMED_NO_POST = (
        "OPERATOR_RESULT_HANDOFF_POLICY_READY_CONFIRMED_NO_POST"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_INPUT = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_INPUT"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNSAFE_CATEGORY = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNSAFE_CATEGORY"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_STALE_OR_REUSED = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_STALE_OR_REUSED"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_RAW_OR_DETAIL = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_RAW_OR_DETAIL"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_IDENTIFIER_EXPOSURE = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_IDENTIFIER_EXPOSURE"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ENV_OR_CREDENTIAL = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ENV_OR_CREDENTIAL"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ACTUAL_EXECUTION = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ACTUAL_EXECUTION"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ACTUAL_RECEIPT = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ACTUAL_RECEIPT"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_API_OR_POST = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_API_OR_POST"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_DISPLAY_OR_SAVE = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_DISPLAY_OR_SAVE"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNSUPPORTED = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNSUPPORTED"
    )


class LiveOrderRealOperatorResultHandoffPolicyMode(str, Enum):
    OPERATOR_RESULT_HANDOFF_POLICY_SKELETON_ONLY = (
        "OPERATOR_RESULT_HANDOFF_POLICY_SKELETON_ONLY"
    )


OperatorResultHandoffPolicyStatus = LiveOrderRealOperatorResultHandoffPolicyStatus
OperatorResultHandoffPolicyMode = LiveOrderRealOperatorResultHandoffPolicyMode
OperatorExecutionResultCategory = LiveOrderRealOperatorExecutionResultCategory

_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT_CATEGORIES = frozenset(
    (
        OperatorExecutionResultCategory.BLOCKED_UNKNOWN.value,
        OperatorExecutionResultCategory.BLOCKED_FAILED.value,
        OperatorExecutionResultCategory.BLOCKED_UNAVAILABLE.value,
        OperatorExecutionResultCategory.BLOCKED_TIMEOUT.value,
    ),
)
_STALE_OR_REUSED_CATEGORIES = frozenset(
    (
        OperatorExecutionResultCategory.BLOCKED_STALE.value,
        OperatorExecutionResultCategory.BLOCKED_REUSED.value,
        OperatorExecutionResultCategory.BLOCKED_PREVIOUS_TURN.value,
    ),
)


@dataclass(frozen=True)
class LiveOrderRealOperatorResultHandoffPolicyInput:
    policy_mode: str = (
        OperatorResultHandoffPolicyMode
        .OPERATOR_RESULT_HANDOFF_POLICY_SKELETON_ONLY
        .value
    )
    policy_declared: bool = True
    receipt_lifecycle_policy_declared: bool = True
    freshness_required: bool = True
    one_time_required: bool = True
    non_reuse_required: bool = True
    current_turn_required: bool = True
    previous_turn_prohibited: bool = True
    non_raw_required: bool = True
    non_detail_required: bool = True
    non_identifier_required: bool = True
    safe_category_only: bool = True
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
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("policy_mode", self.policy_mode)
        _require_non_empty("operator_result_category", self.operator_result_category)
        _validate_bool_fields(
            self,
            (
                "policy_declared",
                "receipt_lifecycle_policy_declared",
                "freshness_required",
                "one_time_required",
                "non_reuse_required",
                "current_turn_required",
                "previous_turn_prohibited",
                "non_raw_required",
                "non_detail_required",
                "non_identifier_required",
                "safe_category_only",
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
                "safe_to_render",
                "safe_to_serialize",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealOperatorResultHandoffPolicyCheckResult:
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
class LiveOrderRealOperatorResultHandoffPolicyResult:
    status: LiveOrderRealOperatorResultHandoffPolicyStatus
    operator_result_handoff_policy_ready: bool
    policy_mode: str
    unsupported_category_present: bool
    policy_declared: bool
    receipt_lifecycle_policy_declared: bool
    freshness_required: bool
    one_time_required: bool
    non_reuse_required: bool
    current_turn_required: bool
    previous_turn_prohibited: bool
    non_raw_required: bool
    non_detail_required: bool
    non_identifier_required: bool
    safe_category_only: bool
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
    safe_to_render: bool
    safe_to_serialize: bool
    check_results: tuple[LiveOrderRealOperatorResultHandoffPolicyCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealOperatorResultHandoffPolicyStatus):
            raise LiveVerificationValidationError(
                "status must be operator result handoff policy status",
            )
        _require_non_empty("policy_mode", self.policy_mode)
        _require_non_empty("operator_result_category", self.operator_result_category)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "operator_result_handoff_policy_ready",
                "unsupported_category_present",
                "policy_declared",
                "receipt_lifecycle_policy_declared",
                "freshness_required",
                "one_time_required",
                "non_reuse_required",
                "current_turn_required",
                "previous_turn_prohibited",
                "non_raw_required",
                "non_detail_required",
                "non_identifier_required",
                "safe_category_only",
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
                "safe_to_render",
                "safe_to_serialize",
            ),
        )
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_operator_result_handoff_policy(
    *,
    input_snapshot: LiveOrderRealOperatorResultHandoffPolicyInput | None = None,
) -> LiveOrderRealOperatorResultHandoffPolicyResult:
    """Build sanitized receipt handoff policy metadata only."""
    policy_input = input_snapshot or LiveOrderRealOperatorResultHandoffPolicyInput()
    safe_category = _safe_category_label(policy_input.operator_result_category)
    unsupported_category_present = _has_unsupported_category(policy_input)

    input_reasons = _input_reasons(policy_input)
    unsupported_reasons = _unsupported_reasons(policy_input)
    unsafe_category_reasons = _unsafe_category_reasons(policy_input)
    stale_or_reused_reasons = _stale_or_reused_reasons(policy_input)
    unknown_reasons = _unknown_failed_unavailable_timeout_reasons(policy_input)
    raw_or_detail_reasons = _raw_or_detail_reasons(policy_input)
    identifier_reasons = _identifier_exposure_reasons(policy_input)
    env_or_credential_reasons = _env_or_credential_reasons(policy_input)
    actual_execution_reasons = _actual_execution_reasons(policy_input)
    actual_receipt_reasons = _actual_receipt_reasons(policy_input)
    api_or_post_reasons = _api_or_post_reasons(policy_input)
    display_reasons = _display_or_save_reasons(policy_input)

    if input_reasons:
        status = PolicyStatus.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_INPUT
        primary_reasons = input_reasons
    elif unsupported_reasons:
        status = PolicyStatus.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNSUPPORTED
        primary_reasons = unsupported_reasons
    elif unsafe_category_reasons:
        status = PolicyStatus.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNSAFE_CATEGORY
        primary_reasons = unsafe_category_reasons
    elif stale_or_reused_reasons:
        status = PolicyStatus.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_STALE_OR_REUSED
        primary_reasons = stale_or_reused_reasons
    elif unknown_reasons:
        status = (
            PolicyStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT
        )
        primary_reasons = unknown_reasons
    elif raw_or_detail_reasons:
        status = PolicyStatus.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_RAW_OR_DETAIL
        primary_reasons = raw_or_detail_reasons
    elif identifier_reasons:
        status = (
            PolicyStatus.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_IDENTIFIER_EXPOSURE
        )
        primary_reasons = identifier_reasons
    elif env_or_credential_reasons:
        status = PolicyStatus.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ENV_OR_CREDENTIAL
        primary_reasons = env_or_credential_reasons
    elif actual_execution_reasons:
        status = PolicyStatus.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ACTUAL_EXECUTION
        primary_reasons = actual_execution_reasons
    elif actual_receipt_reasons:
        status = PolicyStatus.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_ACTUAL_RECEIPT
        primary_reasons = actual_receipt_reasons
    elif api_or_post_reasons:
        status = PolicyStatus.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_API_OR_POST
        primary_reasons = api_or_post_reasons
    elif display_reasons:
        status = PolicyStatus.BLOCKED_OPERATOR_RESULT_HANDOFF_POLICY_DISPLAY_OR_SAVE
        primary_reasons = display_reasons
    elif safe_category == OperatorExecutionResultCategory.READY_CONFIRMED.value:
        status = PolicyStatus.OPERATOR_RESULT_HANDOFF_POLICY_READY_CONFIRMED_NO_POST
        primary_reasons = ()
    else:
        status = PolicyStatus.OPERATOR_RESULT_HANDOFF_POLICY_READY_NO_RECEIPT
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        input_reasons,
        unsupported_reasons,
        unsafe_category_reasons,
        stale_or_reused_reasons,
        unknown_reasons,
        raw_or_detail_reasons,
        identifier_reasons,
        env_or_credential_reasons,
        actual_execution_reasons,
        actual_receipt_reasons,
        api_or_post_reasons,
        display_reasons,
    )
    ready = status in (
        PolicyStatus.OPERATOR_RESULT_HANDOFF_POLICY_READY_NO_RECEIPT,
        PolicyStatus.OPERATOR_RESULT_HANDOFF_POLICY_READY_CONFIRMED_NO_POST,
    )

    return LiveOrderRealOperatorResultHandoffPolicyResult(
        status=status,
        operator_result_handoff_policy_ready=ready,
        policy_mode=_safe_policy_mode(policy_input.policy_mode),
        unsupported_category_present=unsupported_category_present,
        policy_declared=policy_input.policy_declared,
        receipt_lifecycle_policy_declared=(
            policy_input.receipt_lifecycle_policy_declared
        ),
        freshness_required=policy_input.freshness_required,
        one_time_required=policy_input.one_time_required,
        non_reuse_required=policy_input.non_reuse_required,
        current_turn_required=policy_input.current_turn_required,
        previous_turn_prohibited=policy_input.previous_turn_prohibited,
        non_raw_required=policy_input.non_raw_required,
        non_detail_required=policy_input.non_detail_required,
        non_identifier_required=policy_input.non_identifier_required,
        safe_category_only=policy_input.safe_category_only,
        operator_execution_result_category_contract_ready=(
            policy_input.operator_execution_result_category_contract_ready
        ),
        operator_executed_execution_boundary_ready=(
            policy_input.operator_executed_execution_boundary_ready
        ),
        operator_result_handoff_safe=policy_input.operator_result_handoff_safe,
        operator_result_category=safe_category,
        operator_result_category_is_safe_label=(
            policy_input.operator_result_category_is_safe_label
            and not unsupported_category_present
        ),
        operator_result_category_is_allowed=(
            policy_input.operator_result_category_is_allowed
            and not unsupported_category_present
        ),
        ready_confirmed_is_not_post_permission=(
            policy_input.ready_confirmed_is_not_post_permission
        ),
        not_provided_is_not_actual_receipt=(
            policy_input.not_provided_is_not_actual_receipt
        ),
        receipt_current_turn=policy_input.receipt_current_turn,
        receipt_fresh=policy_input.receipt_fresh,
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
        safe_to_render=True,
        safe_to_serialize=True,
        check_results=_build_check_results(policy_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            OPERATOR_RESULT_HANDOFF_POLICY_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_operator_result_handoff_policy_blockers_no_env_no_post"
        ),
    )


def render_live_order_real_operator_result_handoff_policy_markdown(
    result: LiveOrderRealOperatorResultHandoffPolicyResult,
) -> str:
    """Render sanitized receipt handoff policy metadata only."""
    lines = [
        "# Step 6G Operator Result Handoff Policy",
        "",
        "This operator result handoff policy is skeleton-only.",
        "This policy hardens future receipt lifecycle boundaries only.",
        "This policy does not perform actual receipt handoff.",
        "This policy does not receive actual results.",
        "This policy does not execute the checker.",
        "This policy does not access env or .env.",
        "This policy does not read credentials.",
        "This policy does not expose raw receipt or operator result values.",
        "This policy does not expose operator result detail.",
        "READY_CONFIRMED is not POST permission.",
        "READY_CONFIRMED is not final confirmation.",
        "READY_CONFIRMED is not fresh preflight.",
        "NOT_PROVIDED is not an actual result receipt.",
        (
            "Unknown / failed / unavailable / stale / timeout / reused / "
            "previous-turn receipts fail closed."
        ),
        "This policy does not generate real signatures.",
        "This policy does not execute API calls.",
        "This policy does not execute HTTP POST.",
        "This policy does not call order endpoint.",
        "This policy does not call live_order_once.",
        "Future actual receipt handoff and final confirmation must be separate Steps.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- operator_result_handoff_policy_ready: "
            f"{_bool_text(result.operator_result_handoff_policy_ready)}"
        ),
        f"- policy_mode: {result.policy_mode}",
        f"- policy_declared: {_bool_text(result.policy_declared)}",
        (
            "- receipt_lifecycle_policy_declared: "
            f"{_bool_text(result.receipt_lifecycle_policy_declared)}"
        ),
        f"- freshness_required: {_bool_text(result.freshness_required)}",
        f"- one_time_required: {_bool_text(result.one_time_required)}",
        f"- non_reuse_required: {_bool_text(result.non_reuse_required)}",
        f"- current_turn_required: {_bool_text(result.current_turn_required)}",
        (
            "- previous_turn_prohibited: "
            f"{_bool_text(result.previous_turn_prohibited)}"
        ),
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
        (
            "- actual_receipt_handoff_executed: "
            f"{_bool_text(result.actual_receipt_handoff_executed)}"
        ),
        (
            "- actual_result_receipt_received: "
            f"{_bool_text(result.actual_result_receipt_received)}"
        ),
        (
            "- actual_checker_execution_performed: "
            f"{_bool_text(result.actual_checker_execution_performed)}"
        ),
        f"- actual_execution_performed: {_bool_text(result.actual_execution_performed)}",
        f"- codex_execution_performed: {_bool_text(result.codex_execution_performed)}",
        f"- env_access_requested: {_bool_text(result.env_access_requested)}",
        f"- credential_read_performed: {_bool_text(result.credential_read_performed)}",
        f"- can_generate_real_signature: {_bool_text(result.can_generate_real_signature)}",
        f"- can_generate_real_headers: {_bool_text(result.can_generate_real_headers)}",
        f"- can_execute_http_post: {_bool_text(result.can_execute_http_post)}",
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
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[LiveOrderRealOperatorResultHandoffPolicyCheckResult, ...]:
    groups = (
        (
            "policy contract input",
            _input_reasons(policy_input),
            "policy mode lifecycle and prerequisite gates ready",
        ),
        (
            "safe allowed category label",
            _merge_reasons(
                _unsupported_reasons(policy_input),
                _unsafe_category_reasons(policy_input),
            ),
            "category is an allowed safe enum label",
        ),
        (
            "fresh one-time non-reuse policy",
            _stale_or_reused_reasons(policy_input),
            "receipt is current turn fresh not expired and not reused",
        ),
        (
            "known non-timeout policy",
            _unknown_failed_unavailable_timeout_reasons(policy_input),
            "receipt state is not unknown failed unavailable or timeout",
        ),
        (
            "no raw or detail",
            _raw_or_detail_reasons(policy_input),
            "no receipt or operator raw value and no detail",
        ),
        (
            "no identifier exposure",
            _identifier_exposure_reasons(policy_input),
            "no receipt id token nonce hash fingerprint or length",
        ),
        (
            "no env or credential",
            _env_or_credential_reasons(policy_input),
            "no env access credential read values or metadata",
        ),
        (
            "no actual execution",
            _actual_execution_reasons(policy_input),
            "no checker execution performed",
        ),
        (
            "no actual receipt",
            _actual_receipt_reasons(policy_input),
            "no actual receipt handoff or result receipt",
        ),
        (
            "no API or POST",
            _api_or_post_reasons(policy_input),
            "no real signing headers API POST endpoint or live_order_once",
        ),
        (
            "safe render and serialization",
            _display_or_save_reasons(policy_input),
            "render and serialization are safe",
        ),
    )
    return tuple(
        LiveOrderRealOperatorResultHandoffPolicyCheckResult(
            name=name,
            passed=not reasons,
            sanitized_value="pass" if not reasons else "blocked",
            expected=expected,
        )
        for name, reasons, expected in groups
    )


def _input_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        policy_input.policy_mode
        != OperatorResultHandoffPolicyMode
        .OPERATOR_RESULT_HANDOFF_POLICY_SKELETON_ONLY
        .value
    ):
        reasons.append("policy_mode_not_skeleton_only")
    for field_name, reason in (
        ("policy_declared", "policy_not_declared"),
        (
            "receipt_lifecycle_policy_declared",
            "receipt_lifecycle_policy_not_declared",
        ),
        ("freshness_required", "freshness_not_required"),
        ("one_time_required", "one_time_not_required"),
        ("non_reuse_required", "non_reuse_not_required"),
        ("current_turn_required", "current_turn_not_required"),
        ("previous_turn_prohibited", "previous_turn_not_prohibited"),
        ("non_raw_required", "non_raw_not_required"),
        ("non_detail_required", "non_detail_not_required"),
        ("non_identifier_required", "non_identifier_not_required"),
        ("safe_category_only", "safe_category_only_not_required"),
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
        if not getattr(policy_input, field_name):
            reasons.append(reason)
    return tuple(reasons)


def _unsupported_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[str, ...]:
    if _has_unsupported_category(policy_input):
        return ("unsupported_operator_result_category",)
    return ()


def _unsafe_category_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not policy_input.operator_result_category_is_safe_label:
        reasons.append("operator_result_category_not_safe_label")
    if not policy_input.operator_result_category_is_allowed:
        reasons.append("operator_result_category_not_allowed")
    if (
        policy_input.operator_result_category
        == OperatorExecutionResultCategory.READY_CONFIRMED.value
        and not policy_input.ready_confirmed_is_not_post_permission
    ):
        reasons.append("ready_confirmed_post_boundary_missing")
    if (
        policy_input.operator_result_category
        == OperatorExecutionResultCategory.NOT_PROVIDED.value
        and not policy_input.not_provided_is_not_actual_receipt
    ):
        reasons.append("not_provided_actual_receipt_boundary_missing")
    return tuple(reasons)


def _stale_or_reused_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if policy_input.operator_result_category in _STALE_OR_REUSED_CATEGORIES:
        reasons.append("operator_result_category_stale_or_reused")
    for field_name in (
        "receipt_stale",
        "receipt_reused",
        "receipt_previous_turn",
        "receipt_expired",
    ):
        if getattr(policy_input, field_name):
            reasons.append(f"{field_name}_true")
    if not policy_input.receipt_current_turn:
        reasons.append("receipt_not_current_turn")
    if not policy_input.receipt_fresh:
        reasons.append("receipt_not_fresh")
    return tuple(reasons)


def _unknown_failed_unavailable_timeout_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        policy_input.operator_result_category
        in _UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT_CATEGORIES
    ):
        reasons.append("operator_result_category_unknown_failed_unavailable_timeout")
    for field_name in (
        "receipt_timeout",
        "receipt_unknown",
        "receipt_failed",
        "receipt_unavailable",
    ):
        if getattr(policy_input, field_name):
            reasons.append(f"{field_name}_true")
    return tuple(reasons)


def _raw_or_detail_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "receipt_raw_value_present",
        "receipt_detail_present",
        "operator_result_raw_value_present",
        "operator_result_detail_present",
        "checker_result_detail_present",
        "sentinel_value_present",
    ):
        if getattr(policy_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _identifier_exposure_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
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
        if getattr(policy_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _env_or_credential_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "env_variable_names_present",
        "credential_values_present",
        "credential_metadata_present",
        "env_access_requested",
        "credential_read_performed",
    ):
        if getattr(policy_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _actual_execution_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "actual_checker_execution_performed",
        "actual_execution_performed",
        "codex_execution_performed",
    ):
        if getattr(policy_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _actual_receipt_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "actual_receipt_handoff_executed",
        "actual_result_receipt_received",
    ):
        if getattr(policy_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _api_or_post_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "can_generate_real_signature",
        "can_generate_real_headers",
        "can_execute_http_post",
        "http_post_executed",
        "order_endpoint_called",
        "live_order_once_called",
        "post_allowed_this_step",
        "post_executed",
    ):
        if getattr(policy_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _display_or_save_reasons(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "receipt_saved",
        "receipt_displayed",
        "receipt_broadly_propagated",
    ):
        if getattr(policy_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    if not policy_input.safe_to_render:
        reasons.append("render_not_safe")
    if not policy_input.safe_to_serialize:
        reasons.append("serialize_not_safe")
    return tuple(reasons)


def _validate_result_safety(
    result: LiveOrderRealOperatorResultHandoffPolicyResult,
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
    )
    for field_name in unsafe_true_fields:
        if getattr(result, field_name):
            raise LiveVerificationValidationError(f"{field_name} must remain false")
    if not result.safe_to_render:
        raise LiveVerificationValidationError("policy result must remain render safe")
    if not result.safe_to_serialize:
        raise LiveVerificationValidationError("policy result must remain serialization safe")


def _safe_policy_mode(policy_mode: str) -> str:
    if (
        policy_mode
        == OperatorResultHandoffPolicyMode
        .OPERATOR_RESULT_HANDOFF_POLICY_SKELETON_ONLY
        .value
    ):
        return policy_mode
    return OperatorResultHandoffPolicyMode.OPERATOR_RESULT_HANDOFF_POLICY_SKELETON_ONLY.value


def _safe_category_label(operator_result_category: str) -> str:
    if operator_result_category in {
        category.value for category in OperatorExecutionResultCategory
    }:
        return operator_result_category
    return UNSUPPORTED_OPERATOR_RESULT_HANDOFF_POLICY_LABEL


def _has_unsupported_category(
    policy_input: LiveOrderRealOperatorResultHandoffPolicyInput,
) -> bool:
    return policy_input.operator_result_category not in {
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


PolicyStatus = LiveOrderRealOperatorResultHandoffPolicyStatus
PolicyMode = LiveOrderRealOperatorResultHandoffPolicyMode
