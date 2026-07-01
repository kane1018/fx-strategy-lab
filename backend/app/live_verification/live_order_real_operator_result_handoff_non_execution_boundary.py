"""Step 6G receipt handoff non-execution boundary skeleton.

This module consolidates the receipt, policy, and lifecycle ready contracts into
a safe non-execution boundary. It does not perform actual receipt handoff,
receive actual results, execute a checker, read env, inspect credentials, call
APIs, call live_order_once, or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_operator_execution_result_category_contract import (
    LiveOrderRealOperatorExecutionResultCategory,
)

OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_RECOMMENDED_NEXT_STEP = (
    "env_access_decision_gate_review_only_no_env_no_api_no_post"
)
UNSUPPORTED_OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_LABEL = (
    "UNSUPPORTED_REDACTED"
)


class LiveOrderRealOperatorResultHandoffNonExecutionBoundaryStatus(str, Enum):
    NON_EXECUTION_BOUNDARY_NOT_READY = "NON_EXECUTION_BOUNDARY_NOT_READY"
    NON_EXECUTION_BOUNDARY_READY_NO_HANDOFF = (
        "NON_EXECUTION_BOUNDARY_READY_NO_HANDOFF"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_RECEIPT_NOT_READY = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_RECEIPT_NOT_READY"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_POLICY_NOT_READY = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_POLICY_NOT_READY"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_LIFECYCLE_NOT_READY = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_LIFECYCLE_NOT_READY"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_HANDOFF = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_HANDOFF"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_RECEIPT = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_RECEIPT"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_EXECUTION = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_EXECUTION"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_ENV_OR_CREDENTIAL = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_ENV_OR_CREDENTIAL"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_API_OR_POST = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_API_OR_POST"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_LIVE_ORDER_ONCE = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_LIVE_ORDER_ONCE"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_RAW_OR_DETAIL_OR_IDENTIFIER = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_RAW_OR_DETAIL_OR_IDENTIFIER"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_FINAL_CONFIRMATION_OR_PREFLIGHT = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_FINAL_CONFIRMATION_OR_PREFLIGHT"
    )
    NON_EXECUTION_BOUNDARY_BLOCKED_UNSUPPORTED = (
        "NON_EXECUTION_BOUNDARY_BLOCKED_UNSUPPORTED"
    )


class LiveOrderRealOperatorResultHandoffNonExecutionBoundaryMode(str, Enum):
    OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_SKELETON_ONLY = (
        "OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_SKELETON_ONLY"
    )


NonExecutionBoundaryStatus = (
    LiveOrderRealOperatorResultHandoffNonExecutionBoundaryStatus
)
NonExecutionBoundaryMode = LiveOrderRealOperatorResultHandoffNonExecutionBoundaryMode
OperatorExecutionResultCategory = LiveOrderRealOperatorExecutionResultCategory

_BLOCKED_CATEGORIES = frozenset(
    (
        OperatorExecutionResultCategory.BLOCKED_UNKNOWN.value,
        OperatorExecutionResultCategory.BLOCKED_FAILED.value,
        OperatorExecutionResultCategory.BLOCKED_UNAVAILABLE.value,
        OperatorExecutionResultCategory.BLOCKED_STALE.value,
        OperatorExecutionResultCategory.BLOCKED_TIMEOUT.value,
        OperatorExecutionResultCategory.BLOCKED_REUSED.value,
        OperatorExecutionResultCategory.BLOCKED_PREVIOUS_TURN.value,
        OperatorExecutionResultCategory.BLOCKED_UNSAFE_DETAIL.value,
        OperatorExecutionResultCategory.BLOCKED_UNSUPPORTED.value,
    ),
)


@dataclass(frozen=True)
class LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput:
    boundary_mode: str = (
        NonExecutionBoundaryMode
        .OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_SKELETON_ONLY
        .value
    )
    boundary_declared: bool = True
    receipt_contract_ready: bool = True
    policy_contract_ready: bool = True
    lifecycle_contract_ready: bool = True
    receipt_ready: bool = True
    policy_ready: bool = True
    lifecycle_ready: bool = True
    actual_handoff_prohibited: bool = True
    actual_receipt_prohibited: bool = True
    actual_checker_execution_prohibited: bool = True
    env_access_prohibited: bool = True
    credential_read_prohibited: bool = True
    credential_injection_prohibited: bool = True
    api_prohibited: bool = True
    post_prohibited: bool = True
    live_order_once_prohibited: bool = True
    fresh_preflight_prohibited: bool = True
    final_confirmation_prohibited: bool = True
    safe_category_only: bool = True
    raw_detail_identifier_prohibited: bool = True
    ready_flags_are_not_post_permission: bool = True
    ready_flags_are_not_actual_handoff_permission: bool = True
    operator_result_category: str = OperatorExecutionResultCategory.NOT_PROVIDED.value
    operator_result_category_is_safe_label: bool = True
    operator_result_category_is_allowed: bool = True
    ready_confirmed_is_not_post_permission: bool = True
    not_provided_is_not_actual_receipt: bool = True
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
    env_access_allowed: bool = False
    credential_read_performed: bool = False
    credential_read_allowed: bool = False
    credential_injection_allowed: bool = False
    can_generate_real_signature: bool = False
    can_generate_real_headers: bool = False
    can_execute_http_post: bool = False
    real_signing_allowed: bool = False
    real_transport_allowed: bool = False
    api_call_attempted: bool = False
    read_only_api_call_attempted: bool = False
    public_api_call_attempted: bool = False
    private_api_call_attempted: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    fresh_preflight_executed: bool = False
    final_confirmation_received: bool = False
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("boundary_mode", self.boundary_mode)
        _require_non_empty("operator_result_category", self.operator_result_category)
        _validate_bool_fields(
            self,
            (
                "boundary_declared",
                "receipt_contract_ready",
                "policy_contract_ready",
                "lifecycle_contract_ready",
                "receipt_ready",
                "policy_ready",
                "lifecycle_ready",
                "actual_handoff_prohibited",
                "actual_receipt_prohibited",
                "actual_checker_execution_prohibited",
                "env_access_prohibited",
                "credential_read_prohibited",
                "credential_injection_prohibited",
                "api_prohibited",
                "post_prohibited",
                "live_order_once_prohibited",
                "fresh_preflight_prohibited",
                "final_confirmation_prohibited",
                "safe_category_only",
                "raw_detail_identifier_prohibited",
                "ready_flags_are_not_post_permission",
                "ready_flags_are_not_actual_handoff_permission",
                "operator_result_category_is_safe_label",
                "operator_result_category_is_allowed",
                "ready_confirmed_is_not_post_permission",
                "not_provided_is_not_actual_receipt",
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
                "env_access_allowed",
                "credential_read_performed",
                "credential_read_allowed",
                "credential_injection_allowed",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "can_execute_http_post",
                "real_signing_allowed",
                "real_transport_allowed",
                "api_call_attempted",
                "read_only_api_call_attempted",
                "public_api_call_attempted",
                "private_api_call_attempted",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "fresh_preflight_executed",
                "final_confirmation_received",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealOperatorResultHandoffNonExecutionBoundaryCheckResult:
    name: str
    passed: bool
    sanitized_value: str
    expected: str

    def __post_init__(self) -> None:
        _require_non_empty("name", self.name)
        _require_non_empty("sanitized_value", self.sanitized_value)
        _require_non_empty("expected", self.expected)
        _validate_bool_fields(self, ("passed",))


@dataclass(frozen=True)
class LiveOrderRealOperatorResultHandoffNonExecutionBoundaryResult:
    status: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryStatus
    operator_result_handoff_non_execution_boundary_ready: bool
    boundary_mode: str
    boundary_declared: bool
    receipt_contract_ready: bool
    policy_contract_ready: bool
    lifecycle_contract_ready: bool
    receipt_ready: bool
    policy_ready: bool
    lifecycle_ready: bool
    actual_handoff_prohibited: bool
    actual_receipt_prohibited: bool
    actual_checker_execution_prohibited: bool
    env_access_prohibited: bool
    credential_read_prohibited: bool
    credential_injection_prohibited: bool
    api_prohibited: bool
    post_prohibited: bool
    live_order_once_prohibited: bool
    fresh_preflight_prohibited: bool
    final_confirmation_prohibited: bool
    safe_category_only: bool
    raw_detail_identifier_prohibited: bool
    ready_flags_are_not_post_permission: bool
    ready_flags_are_not_actual_handoff_permission: bool
    operator_result_category: str
    operator_result_category_is_safe_label: bool
    operator_result_category_is_allowed: bool
    ready_confirmed_is_not_post_permission: bool
    not_provided_is_not_actual_receipt: bool
    unsupported_mode_present: bool
    unsupported_category_present: bool
    blocked_category_present: bool
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
    env_access_allowed: bool
    credential_read_performed: bool
    credential_read_allowed: bool
    credential_injection_allowed: bool
    can_generate_real_signature: bool
    can_generate_real_headers: bool
    can_execute_http_post: bool
    real_signing_allowed: bool
    real_transport_allowed: bool
    api_call_attempted: bool
    read_only_api_call_attempted: bool
    public_api_call_attempted: bool
    private_api_call_attempted: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_executed: bool
    fresh_preflight_executed: bool
    final_confirmation_received: bool
    safe_to_render: bool
    safe_to_serialize: bool
    check_results: tuple[
        LiveOrderRealOperatorResultHandoffNonExecutionBoundaryCheckResult,
        ...,
    ]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        _require_non_empty("boundary_mode", self.boundary_mode)
        _require_non_empty("operator_result_category", self.operator_result_category)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "operator_result_handoff_non_execution_boundary_ready",
                "boundary_declared",
                "receipt_contract_ready",
                "policy_contract_ready",
                "lifecycle_contract_ready",
                "receipt_ready",
                "policy_ready",
                "lifecycle_ready",
                "actual_handoff_prohibited",
                "actual_receipt_prohibited",
                "actual_checker_execution_prohibited",
                "env_access_prohibited",
                "credential_read_prohibited",
                "credential_injection_prohibited",
                "api_prohibited",
                "post_prohibited",
                "live_order_once_prohibited",
                "fresh_preflight_prohibited",
                "final_confirmation_prohibited",
                "safe_category_only",
                "raw_detail_identifier_prohibited",
                "ready_flags_are_not_post_permission",
                "ready_flags_are_not_actual_handoff_permission",
                "operator_result_category_is_safe_label",
                "operator_result_category_is_allowed",
                "ready_confirmed_is_not_post_permission",
                "not_provided_is_not_actual_receipt",
                "unsupported_mode_present",
                "unsupported_category_present",
                "blocked_category_present",
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
                "env_access_allowed",
                "credential_read_performed",
                "credential_read_allowed",
                "credential_injection_allowed",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "can_execute_http_post",
                "real_signing_allowed",
                "real_transport_allowed",
                "api_call_attempted",
                "read_only_api_call_attempted",
                "public_api_call_attempted",
                "private_api_call_attempted",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "fresh_preflight_executed",
                "final_confirmation_received",
                "safe_to_render",
                "safe_to_serialize",
            ),
        )


def build_live_order_real_operator_result_handoff_non_execution_boundary(
    *,
    input_snapshot: (
        LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput | None
    ) = None,
) -> LiveOrderRealOperatorResultHandoffNonExecutionBoundaryResult:
    boundary_input = (
        input_snapshot
        if input_snapshot is not None
        else LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput()
    )
    status = _status(boundary_input)
    blocked_reasons = _blocked_reasons(boundary_input)
    safe_category = _safe_category(boundary_input.operator_result_category)
    return LiveOrderRealOperatorResultHandoffNonExecutionBoundaryResult(
        status=status,
        operator_result_handoff_non_execution_boundary_ready=(
            status
            is NonExecutionBoundaryStatus.NON_EXECUTION_BOUNDARY_READY_NO_HANDOFF
        ),
        boundary_mode=_safe_mode(boundary_input.boundary_mode),
        boundary_declared=boundary_input.boundary_declared,
        receipt_contract_ready=boundary_input.receipt_contract_ready,
        policy_contract_ready=boundary_input.policy_contract_ready,
        lifecycle_contract_ready=boundary_input.lifecycle_contract_ready,
        receipt_ready=boundary_input.receipt_ready,
        policy_ready=boundary_input.policy_ready,
        lifecycle_ready=boundary_input.lifecycle_ready,
        actual_handoff_prohibited=boundary_input.actual_handoff_prohibited,
        actual_receipt_prohibited=boundary_input.actual_receipt_prohibited,
        actual_checker_execution_prohibited=(
            boundary_input.actual_checker_execution_prohibited
        ),
        env_access_prohibited=boundary_input.env_access_prohibited,
        credential_read_prohibited=boundary_input.credential_read_prohibited,
        credential_injection_prohibited=(
            boundary_input.credential_injection_prohibited
        ),
        api_prohibited=boundary_input.api_prohibited,
        post_prohibited=boundary_input.post_prohibited,
        live_order_once_prohibited=boundary_input.live_order_once_prohibited,
        fresh_preflight_prohibited=boundary_input.fresh_preflight_prohibited,
        final_confirmation_prohibited=boundary_input.final_confirmation_prohibited,
        safe_category_only=boundary_input.safe_category_only,
        raw_detail_identifier_prohibited=(
            boundary_input.raw_detail_identifier_prohibited
        ),
        ready_flags_are_not_post_permission=(
            boundary_input.ready_flags_are_not_post_permission
        ),
        ready_flags_are_not_actual_handoff_permission=(
            boundary_input.ready_flags_are_not_actual_handoff_permission
        ),
        operator_result_category=safe_category,
        operator_result_category_is_safe_label=(
            boundary_input.operator_result_category_is_safe_label
            and safe_category
            != UNSUPPORTED_OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_LABEL
        ),
        operator_result_category_is_allowed=(
            boundary_input.operator_result_category_is_allowed
            and safe_category
            != UNSUPPORTED_OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_LABEL
        ),
        ready_confirmed_is_not_post_permission=(
            boundary_input.ready_confirmed_is_not_post_permission
        ),
        not_provided_is_not_actual_receipt=(
            boundary_input.not_provided_is_not_actual_receipt
        ),
        unsupported_mode_present=_unsupported_mode_present(boundary_input),
        unsupported_category_present=_unsupported_category_present(boundary_input),
        blocked_category_present=_blocked_category_present(boundary_input),
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
        env_access_allowed=False,
        credential_read_performed=False,
        credential_read_allowed=False,
        credential_injection_allowed=False,
        can_generate_real_signature=False,
        can_generate_real_headers=False,
        can_execute_http_post=False,
        real_signing_allowed=False,
        real_transport_allowed=False,
        api_call_attempted=False,
        read_only_api_call_attempted=False,
        public_api_call_attempted=False,
        private_api_call_attempted=False,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_executed=False,
        fresh_preflight_executed=False,
        final_confirmation_received=False,
        safe_to_render=boundary_input.safe_to_render,
        safe_to_serialize=boundary_input.safe_to_serialize,
        check_results=_build_check_results(boundary_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_RECOMMENDED_NEXT_STEP
        ),
    )


def render_live_order_real_operator_result_handoff_non_execution_boundary_markdown(
    result: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryResult,
) -> str:
    lines = [
        "# Step 6G Operator Result Handoff Non-Execution Boundary",
        "",
        "This non-execution boundary is skeleton-only.",
        "It consolidates receipt, policy, and lifecycle readiness only.",
        "It does not perform actual receipt handoff.",
        "It does not receive actual result receipts.",
        "It does not execute the checker.",
        "It does not access env or .env.",
        "It does not read or inject credentials.",
        "Receipt, policy, lifecycle, and boundary ready flags do not allow POST.",
        "READY_CONFIRMED does not allow POST.",
        "NOT_PROVIDED is not an actual result receipt.",
        "Ready flags do not allow actual handoff.",
        "This boundary does not expose raw, detail, or identifier values.",
        "This boundary does not execute API calls.",
        "This boundary does not execute HTTP POST.",
        "This boundary does not call order endpoint.",
        "This boundary does not call live_order_once.",
        "This boundary does not perform final confirmation or fresh preflight.",
        "Future env access requires a separate decision gate.",
        "",
        "## Safe Summary",
        f"- status: {result.status.value}",
        (
            "- operator_result_handoff_non_execution_boundary_ready: "
            f"{_bool_text(result.operator_result_handoff_non_execution_boundary_ready)}"
        ),
        f"- boundary_mode: {result.boundary_mode}",
        f"- boundary_declared: {_bool_text(result.boundary_declared)}",
        f"- receipt_contract_ready: {_bool_text(result.receipt_contract_ready)}",
        f"- policy_contract_ready: {_bool_text(result.policy_contract_ready)}",
        f"- lifecycle_contract_ready: {_bool_text(result.lifecycle_contract_ready)}",
        f"- receipt_ready: {_bool_text(result.receipt_ready)}",
        f"- policy_ready: {_bool_text(result.policy_ready)}",
        f"- lifecycle_ready: {_bool_text(result.lifecycle_ready)}",
        (
            "- ready_flags_are_not_post_permission: "
            f"{_bool_text(result.ready_flags_are_not_post_permission)}"
        ),
        (
            "- ready_flags_are_not_actual_handoff_permission: "
            f"{_bool_text(result.ready_flags_are_not_actual_handoff_permission)}"
        ),
        f"- operator_result_category: {result.operator_result_category}",
        (
            "- ready_confirmed_is_not_post_permission: "
            f"{_bool_text(result.ready_confirmed_is_not_post_permission)}"
        ),
        (
            "- not_provided_is_not_actual_receipt: "
            f"{_bool_text(result.not_provided_is_not_actual_receipt)}"
        ),
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
        f"- env_access_allowed: {_bool_text(result.env_access_allowed)}",
        f"- credential_read_allowed: {_bool_text(result.credential_read_allowed)}",
        (
            "- credential_injection_allowed: "
            f"{_bool_text(result.credential_injection_allowed)}"
        ),
        f"- can_execute_http_post: {_bool_text(result.can_execute_http_post)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- fresh_preflight_executed: {_bool_text(result.fresh_preflight_executed)}",
        f"- final_confirmation_received: {_bool_text(result.final_confirmation_received)}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def _status(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> LiveOrderRealOperatorResultHandoffNonExecutionBoundaryStatus:
    if _unsupported_reasons(boundary_input):
        return NonExecutionBoundaryStatus.NON_EXECUTION_BOUNDARY_BLOCKED_UNSUPPORTED
    if _input_reasons(boundary_input):
        return NonExecutionBoundaryStatus.NON_EXECUTION_BOUNDARY_NOT_READY
    if _receipt_not_ready_reasons(boundary_input):
        return (
            NonExecutionBoundaryStatus
            .NON_EXECUTION_BOUNDARY_BLOCKED_RECEIPT_NOT_READY
        )
    if _policy_not_ready_reasons(boundary_input):
        return (
            NonExecutionBoundaryStatus
            .NON_EXECUTION_BOUNDARY_BLOCKED_POLICY_NOT_READY
        )
    if _lifecycle_not_ready_reasons(boundary_input):
        return (
            NonExecutionBoundaryStatus
            .NON_EXECUTION_BOUNDARY_BLOCKED_LIFECYCLE_NOT_READY
        )
    if _raw_detail_identifier_reasons(boundary_input):
        return (
            NonExecutionBoundaryStatus
            .NON_EXECUTION_BOUNDARY_BLOCKED_RAW_OR_DETAIL_OR_IDENTIFIER
        )
    if _actual_handoff_reasons(boundary_input):
        return NonExecutionBoundaryStatus.NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_HANDOFF
    if _actual_receipt_reasons(boundary_input):
        return NonExecutionBoundaryStatus.NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_RECEIPT
    if _actual_execution_reasons(boundary_input):
        return NonExecutionBoundaryStatus.NON_EXECUTION_BOUNDARY_BLOCKED_ACTUAL_EXECUTION
    if _env_or_credential_reasons(boundary_input):
        return (
            NonExecutionBoundaryStatus
            .NON_EXECUTION_BOUNDARY_BLOCKED_ENV_OR_CREDENTIAL
        )
    if _live_order_once_reasons(boundary_input):
        return NonExecutionBoundaryStatus.NON_EXECUTION_BOUNDARY_BLOCKED_LIVE_ORDER_ONCE
    if _api_or_post_reasons(boundary_input):
        return NonExecutionBoundaryStatus.NON_EXECUTION_BOUNDARY_BLOCKED_API_OR_POST
    if _final_confirmation_or_preflight_reasons(boundary_input):
        return (
            NonExecutionBoundaryStatus
            .NON_EXECUTION_BOUNDARY_BLOCKED_FINAL_CONFIRMATION_OR_PREFLIGHT
        )
    if _display_or_save_reasons(boundary_input):
        return (
            NonExecutionBoundaryStatus
            .NON_EXECUTION_BOUNDARY_BLOCKED_RAW_OR_DETAIL_OR_IDENTIFIER
        )
    return NonExecutionBoundaryStatus.NON_EXECUTION_BOUNDARY_READY_NO_HANDOFF


def _build_check_results(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[LiveOrderRealOperatorResultHandoffNonExecutionBoundaryCheckResult, ...]:
    groups = (
        (
            "non-execution boundary input",
            _merge_reasons(_unsupported_reasons(boundary_input), _input_reasons(boundary_input)),
            "boundary skeleton prerequisites ready",
        ),
        (
            "receipt policy lifecycle ready",
            _merge_reasons(
                _receipt_not_ready_reasons(boundary_input),
                _policy_not_ready_reasons(boundary_input),
                _lifecycle_not_ready_reasons(boundary_input),
            ),
            "receipt policy and lifecycle contracts are ready",
        ),
        (
            "no actual handoff receipt execution",
            _merge_reasons(
                _actual_handoff_reasons(boundary_input),
                _actual_receipt_reasons(boundary_input),
                _actual_execution_reasons(boundary_input),
            ),
            "no actual handoff receipt or checker execution",
        ),
        (
            "no env credential",
            _env_or_credential_reasons(boundary_input),
            "no env access credential read or injection",
        ),
        (
            "no API POST live order",
            _merge_reasons(
                _api_or_post_reasons(boundary_input),
                _live_order_once_reasons(boundary_input),
            ),
            "no API POST endpoint or live_order_once",
        ),
        (
            "no raw detail identifier",
            _raw_detail_identifier_reasons(boundary_input),
            "no raw detail or identifier exposure",
        ),
        (
            "no final confirmation or preflight",
            _final_confirmation_or_preflight_reasons(boundary_input),
            "no final confirmation or fresh preflight",
        ),
        (
            "safe render and serialization",
            _display_or_save_reasons(boundary_input),
            "render and serialization are safe",
        ),
    )
    return tuple(
        LiveOrderRealOperatorResultHandoffNonExecutionBoundaryCheckResult(
            name=name,
            passed=not reasons,
            sanitized_value="pass" if not reasons else "blocked",
            expected=expected,
        )
        for name, reasons, expected in groups
    )


def _blocked_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    return _merge_reasons(
        _unsupported_reasons(boundary_input),
        _input_reasons(boundary_input),
        _receipt_not_ready_reasons(boundary_input),
        _policy_not_ready_reasons(boundary_input),
        _lifecycle_not_ready_reasons(boundary_input),
        _raw_detail_identifier_reasons(boundary_input),
        _actual_handoff_reasons(boundary_input),
        _actual_receipt_reasons(boundary_input),
        _actual_execution_reasons(boundary_input),
        _env_or_credential_reasons(boundary_input),
        _live_order_once_reasons(boundary_input),
        _api_or_post_reasons(boundary_input),
        _final_confirmation_or_preflight_reasons(boundary_input),
        _display_or_save_reasons(boundary_input),
    )


def _unsupported_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _unsupported_mode_present(boundary_input):
        reasons.append("unsupported_boundary_mode")
    if _unsupported_category_present(boundary_input):
        reasons.append("unsupported_operator_result_category")
    return tuple(reasons)


def _input_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "boundary_declared",
        "actual_handoff_prohibited",
        "actual_receipt_prohibited",
        "actual_checker_execution_prohibited",
        "env_access_prohibited",
        "credential_read_prohibited",
        "credential_injection_prohibited",
        "api_prohibited",
        "post_prohibited",
        "live_order_once_prohibited",
        "fresh_preflight_prohibited",
        "final_confirmation_prohibited",
        "safe_category_only",
        "raw_detail_identifier_prohibited",
        "ready_flags_are_not_post_permission",
        "ready_flags_are_not_actual_handoff_permission",
        "operator_result_category_is_safe_label",
        "operator_result_category_is_allowed",
        "ready_confirmed_is_not_post_permission",
        "not_provided_is_not_actual_receipt",
        "safe_to_render",
        "safe_to_serialize",
    ):
        if not getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_false")
    if _blocked_category_present(boundary_input):
        reasons.append("operator_result_category_blocked")
    return tuple(reasons)


def _receipt_not_ready_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    return _false_field_reasons(
        boundary_input,
        ("receipt_contract_ready", "receipt_ready"),
    )


def _policy_not_ready_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    return _false_field_reasons(
        boundary_input,
        ("policy_contract_ready", "policy_ready"),
    )


def _lifecycle_not_ready_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    return _false_field_reasons(
        boundary_input,
        ("lifecycle_contract_ready", "lifecycle_ready"),
    )


def _raw_detail_identifier_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "receipt_raw_value_present",
        "receipt_detail_present",
        "receipt_id_present",
        "receipt_token_present",
        "receipt_nonce_present",
        "receipt_hash_present",
        "receipt_fingerprint_present",
        "receipt_length_present",
        "operator_result_detail_present",
        "operator_result_raw_value_present",
        "checker_result_detail_present",
        "sentinel_value_present",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _actual_handoff_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    if boundary_input.actual_receipt_handoff_executed:
        return ("actual_receipt_handoff_executed",)
    return ()


def _actual_receipt_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    if boundary_input.actual_result_receipt_received:
        return ("actual_result_receipt_received",)
    return ()


def _actual_execution_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "actual_checker_execution_performed",
        "actual_execution_performed",
        "codex_execution_performed",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _env_or_credential_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "env_variable_names_present",
        "credential_values_present",
        "credential_metadata_present",
        "env_access_requested",
        "env_access_allowed",
        "credential_read_performed",
        "credential_read_allowed",
        "credential_injection_allowed",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _api_or_post_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "can_generate_real_signature",
        "can_generate_real_headers",
        "can_execute_http_post",
        "real_signing_allowed",
        "real_transport_allowed",
        "api_call_attempted",
        "read_only_api_call_attempted",
        "public_api_call_attempted",
        "private_api_call_attempted",
        "http_post_executed",
        "order_endpoint_called",
        "post_allowed_this_step",
        "post_executed",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _live_order_once_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    if boundary_input.live_order_once_called:
        return ("live_order_once_called",)
    return ()


def _final_confirmation_or_preflight_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if boundary_input.final_confirmation_received:
        reasons.append("final_confirmation_received")
    if boundary_input.fresh_preflight_executed:
        reasons.append("fresh_preflight_executed")
    return tuple(reasons)


def _display_or_save_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "receipt_saved",
        "receipt_displayed",
        "receipt_broadly_propagated",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _false_field_reasons(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
    field_names: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        f"{field_name}_false"
        for field_name in field_names
        if not getattr(boundary_input, field_name)
    )


def _safe_mode(raw_mode: str) -> str:
    if raw_mode in {mode.value for mode in NonExecutionBoundaryMode}:
        return raw_mode
    return UNSUPPORTED_OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_LABEL


def _safe_category(raw_category: str) -> str:
    if raw_category in {category.value for category in OperatorExecutionResultCategory}:
        return raw_category
    return UNSUPPORTED_OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_LABEL


def _unsupported_mode_present(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> bool:
    return boundary_input.boundary_mode not in {
        mode.value for mode in NonExecutionBoundaryMode
    }


def _unsupported_category_present(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> bool:
    return boundary_input.operator_result_category not in {
        category.value for category in OperatorExecutionResultCategory
    }


def _blocked_category_present(
    boundary_input: LiveOrderRealOperatorResultHandoffNonExecutionBoundaryInput,
) -> bool:
    return boundary_input.operator_result_category in _BLOCKED_CATEGORIES


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        merged.extend(group)
    return tuple(merged)


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be a non-empty string")


def _validate_bool_fields(instance: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if not isinstance(getattr(instance, field_name), bool):
            raise LiveVerificationValidationError(f"{field_name} must be a bool")


def _bool_text(value: bool) -> str:
    return str(value).lower()
