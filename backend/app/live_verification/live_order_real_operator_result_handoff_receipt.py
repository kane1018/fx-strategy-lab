"""Step 6G operator result handoff receipt skeleton.

This module defines only the safe receipt contract for a future operator-side
checker result category handoff. It does not execute a checker, accept raw
operator result values, read env, inspect credentials, call APIs, or execute
HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_operator_execution_result_category_contract import (
    LiveOrderRealOperatorExecutionResultCategory,
)

OPERATOR_RESULT_HANDOFF_RECEIPT_RECOMMENDED_NEXT_STEP = (
    "future_actual_receipt_handoff_and_final_confirmation_must_be_separate_steps"
)
UNSUPPORTED_OPERATOR_RESULT_HANDOFF_RECEIPT_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealOperatorResultHandoffReceiptStatus(str, Enum):
    OPERATOR_RESULT_HANDOFF_RECEIPT_READY_NOT_PROVIDED = (
        "OPERATOR_RESULT_HANDOFF_RECEIPT_READY_NOT_PROVIDED"
    )
    OPERATOR_RESULT_HANDOFF_RECEIPT_READY_CONFIRMED_NO_POST = (
        "OPERATOR_RESULT_HANDOFF_RECEIPT_READY_CONFIRMED_NO_POST"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_INPUT = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_INPUT"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNSAFE_CATEGORY = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNSAFE_CATEGORY"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_STALE_OR_REUSED = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_STALE_OR_REUSED"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_RAW_OR_DETAIL = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_RAW_OR_DETAIL"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_IDENTIFIER_EXPOSURE = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_IDENTIFIER_EXPOSURE"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_RESULT_EXPOSURE = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_RESULT_EXPOSURE"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_ENV_OR_CREDENTIAL = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_ENV_OR_CREDENTIAL"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_EXECUTION = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_EXECUTION"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_REAL_SIGNING_OR_POST = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_REAL_SIGNING_OR_POST"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_DISPLAY_OR_SAVE = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_DISPLAY_OR_SAVE"
    )
    BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNSUPPORTED = (
        "BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNSUPPORTED"
    )


class LiveOrderRealOperatorResultHandoffReceiptMode(str, Enum):
    OPERATOR_RESULT_HANDOFF_RECEIPT_SKELETON_ONLY = (
        "OPERATOR_RESULT_HANDOFF_RECEIPT_SKELETON_ONLY"
    )


OperatorResultHandoffReceiptStatus = LiveOrderRealOperatorResultHandoffReceiptStatus
OperatorResultHandoffReceiptMode = LiveOrderRealOperatorResultHandoffReceiptMode
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
class LiveOrderRealOperatorResultHandoffReceiptInput:
    receipt_mode: str = (
        OperatorResultHandoffReceiptMode
        .OPERATOR_RESULT_HANDOFF_RECEIPT_SKELETON_ONLY
        .value
    )
    receipt_contract_declared: bool = True
    receipt_boundary_declared: bool = True
    receipt_one_time_required: bool = True
    receipt_fresh_required: bool = True
    receipt_non_reuse_required: bool = True
    receipt_non_raw_required: bool = True
    receipt_non_detail_required: bool = True
    operator_execution_result_category_contract_ready: bool = True
    operator_executed_execution_boundary_ready: bool = True
    operator_result_handoff_safe: bool = True
    operator_result_category: str = OperatorExecutionResultCategory.NOT_PROVIDED.value
    operator_result_category_is_safe_label: bool = True
    operator_result_category_is_allowed: bool = True
    receipt_provided: bool = False
    receipt_category_confirmed: bool = False
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
        _require_non_empty("receipt_mode", self.receipt_mode)
        _require_non_empty("operator_result_category", self.operator_result_category)
        _validate_bool_fields(
            self,
            (
                "receipt_contract_declared",
                "receipt_boundary_declared",
                "receipt_one_time_required",
                "receipt_fresh_required",
                "receipt_non_reuse_required",
                "receipt_non_raw_required",
                "receipt_non_detail_required",
                "operator_execution_result_category_contract_ready",
                "operator_executed_execution_boundary_ready",
                "operator_result_handoff_safe",
                "operator_result_category_is_safe_label",
                "operator_result_category_is_allowed",
                "receipt_provided",
                "receipt_category_confirmed",
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
class LiveOrderRealOperatorResultHandoffReceiptCheckResult:
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
class LiveOrderRealOperatorResultHandoffReceiptResult:
    status: LiveOrderRealOperatorResultHandoffReceiptStatus
    operator_result_handoff_receipt_ready: bool
    receipt_mode: str
    unsupported_category_present: bool
    receipt_contract_declared: bool
    receipt_boundary_declared: bool
    receipt_one_time_required: bool
    receipt_fresh_required: bool
    receipt_non_reuse_required: bool
    receipt_non_raw_required: bool
    receipt_non_detail_required: bool
    operator_execution_result_category_contract_ready: bool
    operator_executed_execution_boundary_ready: bool
    operator_result_handoff_safe: bool
    operator_result_category: str
    operator_result_category_is_safe_label: bool
    operator_result_category_is_allowed: bool
    receipt_provided: bool
    receipt_category_confirmed: bool
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
    check_results: tuple[LiveOrderRealOperatorResultHandoffReceiptCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealOperatorResultHandoffReceiptStatus):
            raise LiveVerificationValidationError(
                "status must be operator result handoff receipt status",
            )
        _require_non_empty("receipt_mode", self.receipt_mode)
        _require_non_empty("operator_result_category", self.operator_result_category)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "operator_result_handoff_receipt_ready",
                "unsupported_category_present",
                "receipt_contract_declared",
                "receipt_boundary_declared",
                "receipt_one_time_required",
                "receipt_fresh_required",
                "receipt_non_reuse_required",
                "receipt_non_raw_required",
                "receipt_non_detail_required",
                "operator_execution_result_category_contract_ready",
                "operator_executed_execution_boundary_ready",
                "operator_result_handoff_safe",
                "operator_result_category_is_safe_label",
                "operator_result_category_is_allowed",
                "receipt_provided",
                "receipt_category_confirmed",
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


def build_live_order_real_operator_result_handoff_receipt(
    *,
    input_snapshot: LiveOrderRealOperatorResultHandoffReceiptInput | None = None,
) -> LiveOrderRealOperatorResultHandoffReceiptResult:
    """Build sanitized operator result handoff receipt metadata only."""
    receipt_input = input_snapshot or LiveOrderRealOperatorResultHandoffReceiptInput()
    safe_category = _safe_category_label(receipt_input.operator_result_category)
    unsupported_category_present = _has_unsupported_category(receipt_input)

    input_reasons = _input_reasons(receipt_input)
    unsupported_reasons = _unsupported_reasons(receipt_input)
    unsafe_category_reasons = _unsafe_category_reasons(receipt_input)
    stale_or_reused_reasons = _stale_or_reused_reasons(receipt_input)
    unknown_reasons = _unknown_failed_unavailable_timeout_reasons(receipt_input)
    raw_or_detail_reasons = _raw_or_detail_reasons(receipt_input)
    identifier_reasons = _identifier_exposure_reasons(receipt_input)
    result_exposure_reasons = _result_exposure_reasons(receipt_input)
    env_or_credential_reasons = _env_or_credential_reasons(receipt_input)
    execution_reasons = _execution_reasons(receipt_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(receipt_input)
    display_reasons = _display_or_save_reasons(receipt_input)

    if input_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_INPUT
        )
        primary_reasons = input_reasons
    elif unsupported_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNSUPPORTED
        )
        primary_reasons = unsupported_reasons
    elif unsafe_category_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNSAFE_CATEGORY
        )
        primary_reasons = unsafe_category_reasons
    elif stale_or_reused_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_STALE_OR_REUSED
        )
        primary_reasons = stale_or_reused_reasons
    elif unknown_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT
        )
        primary_reasons = unknown_reasons
    elif raw_or_detail_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_RAW_OR_DETAIL
        )
        primary_reasons = raw_or_detail_reasons
    elif identifier_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_IDENTIFIER_EXPOSURE
        )
        primary_reasons = identifier_reasons
    elif result_exposure_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_RESULT_EXPOSURE
        )
        primary_reasons = result_exposure_reasons
    elif env_or_credential_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_ENV_OR_CREDENTIAL
        )
        primary_reasons = env_or_credential_reasons
    elif execution_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_EXECUTION
        )
        primary_reasons = execution_reasons
    elif real_signing_or_post_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_REAL_SIGNING_OR_POST
        )
        primary_reasons = real_signing_or_post_reasons
    elif display_reasons:
        status = (
            OperatorResultHandoffReceiptStatus
            .BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_DISPLAY_OR_SAVE
        )
        primary_reasons = display_reasons
    elif safe_category == OperatorExecutionResultCategory.READY_CONFIRMED.value:
        status = (
            OperatorResultHandoffReceiptStatus
            .OPERATOR_RESULT_HANDOFF_RECEIPT_READY_CONFIRMED_NO_POST
        )
        primary_reasons = ()
    else:
        status = (
            OperatorResultHandoffReceiptStatus
            .OPERATOR_RESULT_HANDOFF_RECEIPT_READY_NOT_PROVIDED
        )
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
        result_exposure_reasons,
        env_or_credential_reasons,
        execution_reasons,
        real_signing_or_post_reasons,
        display_reasons,
    )
    ready = status in (
        OperatorResultHandoffReceiptStatus
        .OPERATOR_RESULT_HANDOFF_RECEIPT_READY_NOT_PROVIDED,
        OperatorResultHandoffReceiptStatus
        .OPERATOR_RESULT_HANDOFF_RECEIPT_READY_CONFIRMED_NO_POST,
    )
    ready_confirmed = (
        status
        is OperatorResultHandoffReceiptStatus
        .OPERATOR_RESULT_HANDOFF_RECEIPT_READY_CONFIRMED_NO_POST
    )

    return LiveOrderRealOperatorResultHandoffReceiptResult(
        status=status,
        operator_result_handoff_receipt_ready=ready,
        receipt_mode=_safe_receipt_mode(receipt_input.receipt_mode),
        unsupported_category_present=unsupported_category_present,
        receipt_contract_declared=receipt_input.receipt_contract_declared,
        receipt_boundary_declared=receipt_input.receipt_boundary_declared,
        receipt_one_time_required=receipt_input.receipt_one_time_required,
        receipt_fresh_required=receipt_input.receipt_fresh_required,
        receipt_non_reuse_required=receipt_input.receipt_non_reuse_required,
        receipt_non_raw_required=receipt_input.receipt_non_raw_required,
        receipt_non_detail_required=receipt_input.receipt_non_detail_required,
        operator_execution_result_category_contract_ready=(
            receipt_input.operator_execution_result_category_contract_ready
        ),
        operator_executed_execution_boundary_ready=(
            receipt_input.operator_executed_execution_boundary_ready
        ),
        operator_result_handoff_safe=receipt_input.operator_result_handoff_safe,
        operator_result_category=safe_category,
        operator_result_category_is_safe_label=(
            receipt_input.operator_result_category_is_safe_label
            and not unsupported_category_present
        ),
        operator_result_category_is_allowed=(
            receipt_input.operator_result_category_is_allowed
            and not unsupported_category_present
        ),
        receipt_provided=ready_confirmed,
        receipt_category_confirmed=ready_confirmed,
        receipt_current_turn=receipt_input.receipt_current_turn,
        receipt_fresh=receipt_input.receipt_fresh,
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
        check_results=_build_check_results(receipt_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            OPERATOR_RESULT_HANDOFF_RECEIPT_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_operator_result_handoff_receipt_blockers_no_env_no_post"
        ),
    )


def render_live_order_real_operator_result_handoff_receipt_markdown(
    result: LiveOrderRealOperatorResultHandoffReceiptResult,
) -> str:
    """Render sanitized operator result handoff receipt metadata only."""
    lines = [
        "# Step 6G Operator Result Handoff Receipt",
        "",
        "This operator result handoff receipt is skeleton-only.",
        "This receipt is one-time, fresh, non-reuse, non-raw, and non-detail.",
        "This receipt does not execute the checker.",
        "This receipt does not access env or .env.",
        "This receipt does not read credentials.",
        "This receipt does not expose raw operator result values.",
        "This receipt does not expose operator result detail.",
        "READY_CONFIRMED receipt does not allow POST.",
        "NOT_PROVIDED receipt is not an actual result.",
        (
            "Unknown / failed / unavailable / stale / timeout / reused / "
            "previous-turn receipts block POST."
        ),
        "This receipt does not generate real signatures.",
        "This receipt does not execute API calls.",
        "This receipt does not execute HTTP POST.",
        "This receipt does not call order endpoint.",
        "This receipt does not call live_order_once.",
        "Future actual receipt handoff and final confirmation must be separate Steps.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- operator_result_handoff_receipt_ready: "
            f"{_bool_text(result.operator_result_handoff_receipt_ready)}"
        ),
        f"- receipt_mode: {result.receipt_mode}",
        (
            "- receipt_contract_declared: "
            f"{_bool_text(result.receipt_contract_declared)}"
        ),
        (
            "- receipt_boundary_declared: "
            f"{_bool_text(result.receipt_boundary_declared)}"
        ),
        (
            "- receipt_one_time_required: "
            f"{_bool_text(result.receipt_one_time_required)}"
        ),
        f"- receipt_fresh_required: {_bool_text(result.receipt_fresh_required)}",
        (
            "- receipt_non_reuse_required: "
            f"{_bool_text(result.receipt_non_reuse_required)}"
        ),
        f"- receipt_non_raw_required: {_bool_text(result.receipt_non_raw_required)}",
        (
            "- receipt_non_detail_required: "
            f"{_bool_text(result.receipt_non_detail_required)}"
        ),
        f"- operator_result_category: {result.operator_result_category}",
        f"- receipt_provided: {_bool_text(result.receipt_provided)}",
        (
            "- receipt_category_confirmed: "
            f"{_bool_text(result.receipt_category_confirmed)}"
        ),
        f"- receipt_current_turn: {_bool_text(result.receipt_current_turn)}",
        f"- receipt_fresh: {_bool_text(result.receipt_fresh)}",
        f"- receipt_reused: {_bool_text(result.receipt_reused)}",
        f"- receipt_previous_turn: {_bool_text(result.receipt_previous_turn)}",
        f"- receipt_timeout: {_bool_text(result.receipt_timeout)}",
        f"- receipt_raw_value_present: {_bool_text(result.receipt_raw_value_present)}",
        f"- receipt_detail_present: {_bool_text(result.receipt_detail_present)}",
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
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> tuple[LiveOrderRealOperatorResultHandoffReceiptCheckResult, ...]:
    groups = (
        (
            "receipt contract input",
            _input_reasons(receipt_input),
            "receipt mode and prerequisite gates ready",
        ),
        (
            "safe allowed category label",
            _merge_reasons(
                _unsupported_reasons(receipt_input),
                _unsafe_category_reasons(receipt_input),
            ),
            "category is an allowed safe enum label",
        ),
        (
            "fresh one-time non-reuse receipt",
            _stale_or_reused_reasons(receipt_input),
            "receipt is current turn fresh not expired and not reused",
        ),
        (
            "known non-timeout receipt",
            _unknown_failed_unavailable_timeout_reasons(receipt_input),
            "receipt is not unknown failed unavailable or timeout",
        ),
        (
            "no raw or detail receipt",
            _raw_or_detail_reasons(receipt_input),
            "receipt has no raw value and no detail",
        ),
        (
            "no receipt identifier exposure",
            _identifier_exposure_reasons(receipt_input),
            "receipt exposes no id token nonce hash fingerprint or length",
        ),
        (
            "no result exposure",
            _result_exposure_reasons(receipt_input),
            "no operator checker detail env names sentinel or saved receipt",
        ),
        (
            "no env or credential",
            _env_or_credential_reasons(receipt_input),
            "no env access credential read values or metadata",
        ),
        (
            "no execution",
            _execution_reasons(receipt_input),
            "no actual or Codex execution performed",
        ),
        (
            "no real signing or post",
            _real_signing_or_post_reasons(receipt_input),
            "no real signing headers API POST endpoint or live_order_once",
        ),
        (
            "safe render and serialization",
            _display_or_save_reasons(receipt_input),
            "render and serialization are safe",
        ),
    )
    return tuple(
        LiveOrderRealOperatorResultHandoffReceiptCheckResult(
            name=name,
            passed=not reasons,
            sanitized_value="ready" if not reasons else ",".join(reasons),
            expected=expected,
        )
        for name, reasons, expected in groups
    )


def _input_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_unsupported_receipt_mode(receipt_input.receipt_mode):
        reasons.append("receipt_mode_unsupported")
    for field_name in (
        "receipt_contract_declared",
        "receipt_boundary_declared",
        "receipt_one_time_required",
        "receipt_fresh_required",
        "receipt_non_reuse_required",
        "receipt_non_raw_required",
        "receipt_non_detail_required",
        "operator_execution_result_category_contract_ready",
        "operator_executed_execution_boundary_ready",
        "operator_result_handoff_safe",
    ):
        if not getattr(receipt_input, field_name):
            reasons.append(f"{field_name}_false")
    return tuple(reasons)


def _unsupported_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_unsupported_category(receipt_input):
        reasons.append("operator_result_category_unsupported")
    if (
        _safe_category_label(receipt_input.operator_result_category)
        == OperatorExecutionResultCategory.BLOCKED_UNSUPPORTED.value
    ):
        reasons.append("operator_result_category_blocked_unsupported")
    return tuple(reasons)


def _unsafe_category_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    safe_category = _safe_category_label(receipt_input.operator_result_category)
    if not receipt_input.operator_result_category_is_safe_label:
        reasons.append("operator_result_category_is_safe_label_false")
    if not receipt_input.operator_result_category_is_allowed:
        reasons.append("operator_result_category_is_allowed_false")
    if safe_category == OperatorExecutionResultCategory.READY_CONFIRMED.value:
        if not receipt_input.receipt_provided:
            reasons.append("ready_confirmed_receipt_requires_receipt_provided")
        if not receipt_input.receipt_category_confirmed:
            reasons.append("ready_confirmed_receipt_requires_category_confirmed")
    if safe_category == OperatorExecutionResultCategory.NOT_PROVIDED.value:
        if receipt_input.receipt_provided:
            reasons.append("not_provided_must_not_mark_receipt_provided")
        if receipt_input.receipt_category_confirmed:
            reasons.append("not_provided_must_not_mark_category_confirmed")
    if safe_category == OperatorExecutionResultCategory.BLOCKED_UNSAFE_DETAIL.value:
        reasons.append("operator_result_category_blocked_unsafe_detail")
    return tuple(reasons)


def _stale_or_reused_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    safe_category = _safe_category_label(receipt_input.operator_result_category)
    if safe_category in _STALE_OR_REUSED_CATEGORIES:
        reasons.append(f"operator_result_category_{safe_category.lower()}")
    if not receipt_input.receipt_current_turn:
        reasons.append("receipt_current_turn_false")
    if not receipt_input.receipt_fresh:
        reasons.append("receipt_fresh_false")
    for field_name in (
        "receipt_stale",
        "receipt_reused",
        "receipt_previous_turn",
        "receipt_expired",
    ):
        if getattr(receipt_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _unknown_failed_unavailable_timeout_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    safe_category = _safe_category_label(receipt_input.operator_result_category)
    if safe_category in _UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT_CATEGORIES:
        reasons.append(f"operator_result_category_{safe_category.lower()}")
    for field_name in (
        "receipt_timeout",
        "receipt_unknown",
        "receipt_failed",
        "receipt_unavailable",
    ):
        if getattr(receipt_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _raw_or_detail_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "receipt_raw_value_present",
        "receipt_detail_present",
    ):
        if getattr(receipt_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _identifier_exposure_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
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
        if getattr(receipt_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _result_exposure_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "receipt_saved",
        "receipt_displayed",
        "receipt_broadly_propagated",
        "operator_result_detail_present",
        "operator_result_raw_value_present",
        "checker_result_detail_present",
        "sentinel_value_present",
    ):
        if getattr(receipt_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _env_or_credential_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "env_variable_names_present",
        "credential_values_present",
        "credential_metadata_present",
        "env_access_requested",
        "credential_read_performed",
    ):
        if getattr(receipt_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _execution_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if receipt_input.actual_execution_performed:
        reasons.append("actual_execution_performed_unsafe")
    if receipt_input.codex_execution_performed:
        reasons.append("codex_execution_performed_unsafe")
    return tuple(reasons)


def _real_signing_or_post_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
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
        if getattr(receipt_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _display_or_save_reasons(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not receipt_input.safe_to_render:
        reasons.append("safe_to_render_false")
    if not receipt_input.safe_to_serialize:
        reasons.append("safe_to_serialize_false")
    return tuple(reasons)


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _validate_result_safety(
    result: LiveOrderRealOperatorResultHandoffReceiptResult,
) -> None:
    unsafe_flags = (
        result.receipt_stale,
        result.receipt_reused,
        result.receipt_previous_turn,
        result.receipt_expired,
        result.receipt_timeout,
        result.receipt_unknown,
        result.receipt_failed,
        result.receipt_unavailable,
        result.receipt_raw_value_present,
        result.receipt_detail_present,
        result.receipt_id_present,
        result.receipt_token_present,
        result.receipt_nonce_present,
        result.receipt_hash_present,
        result.receipt_fingerprint_present,
        result.receipt_length_present,
        result.receipt_saved,
        result.receipt_displayed,
        result.receipt_broadly_propagated,
        result.operator_result_detail_present,
        result.operator_result_raw_value_present,
        result.checker_result_detail_present,
        result.env_variable_names_present,
        result.credential_values_present,
        result.credential_metadata_present,
        result.sentinel_value_present,
        result.actual_execution_performed,
        result.codex_execution_performed,
        result.env_access_requested,
        result.credential_read_performed,
        result.can_generate_real_signature,
        result.can_generate_real_headers,
        result.can_execute_http_post,
        result.http_post_executed,
        result.order_endpoint_called,
        result.live_order_once_called,
        result.post_allowed_this_step,
        result.post_executed,
        not result.safe_to_render,
        not result.safe_to_serialize,
    )
    if any(unsafe_flags):
        raise LiveVerificationValidationError(
            "operator result handoff receipt result is unsafe",
        )
    if result.unsupported_category_present:
        if result.operator_result_category != UNSUPPORTED_OPERATOR_RESULT_HANDOFF_RECEIPT_LABEL:
            raise LiveVerificationValidationError(
                "unsupported operator result receipt category must use safe label",
            )
    elif result.operator_result_category not in _allowed_category_values():
        raise LiveVerificationValidationError(
            "operator result receipt category must be an allowed safe label",
        )
    if result.receipt_category_confirmed:
        if result.post_allowed_this_step or result.post_executed:
            raise LiveVerificationValidationError(
                "READY_CONFIRMED receipt must not allow or execute POST",
            )
    if result.receipt_provided and not result.receipt_category_confirmed:
        raise LiveVerificationValidationError(
            "provided receipt must be category-confirmed only",
        )


def _has_unsupported_receipt_mode(raw_mode: str) -> bool:
    return raw_mode not in {
        OperatorResultHandoffReceiptMode
        .OPERATOR_RESULT_HANDOFF_RECEIPT_SKELETON_ONLY
        .value,
    }


def _safe_receipt_mode(raw_mode: str) -> str:
    if _has_unsupported_receipt_mode(raw_mode):
        return (
            OperatorResultHandoffReceiptMode
            .OPERATOR_RESULT_HANDOFF_RECEIPT_SKELETON_ONLY
            .value
        )
    return raw_mode


def _has_unsupported_category(
    receipt_input: LiveOrderRealOperatorResultHandoffReceiptInput,
) -> bool:
    return receipt_input.operator_result_category not in _allowed_category_values()


def _safe_category_label(raw_category: str) -> str:
    if raw_category in _allowed_category_values():
        return raw_category
    return UNSUPPORTED_OPERATOR_RESULT_HANDOFF_RECEIPT_LABEL


def _allowed_category_values() -> set[str]:
    return {category.value for category in OperatorExecutionResultCategory}


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{name} must be non-empty string")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
