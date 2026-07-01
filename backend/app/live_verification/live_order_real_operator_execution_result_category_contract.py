"""Step 6G operator-side execution result category contract.

This module defines only the safe category labels that a future operator-side
checker execution may hand off to Codex. It does not execute a checker, read
env, inspect credentials, expose raw operator result values, call APIs, or
execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

OPERATOR_EXECUTION_RESULT_CATEGORY_RECOMMENDED_NEXT_STEP = (
    "future_actual_execution_and_final_confirmation_must_be_separate_steps"
)
UNSUPPORTED_OPERATOR_EXECUTION_RESULT_CATEGORY_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealOperatorExecutionResultCategoryContractStatus(str, Enum):
    OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_NO_RESULT = (
        "OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_NO_RESULT"
    )
    OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_CONFIRMED_NO_POST = (
        "OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_CONFIRMED_NO_POST"
    )
    BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_INPUT = (
        "BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_INPUT"
    )
    BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNSUPPORTED_CATEGORY = (
        "BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNSUPPORTED_CATEGORY"
    )
    BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNSAFE_CATEGORY = (
        "BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNSAFE_CATEGORY"
    )
    BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT = (  # noqa: E501
        "BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT"
    )
    BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_REUSED_OR_PREVIOUS = (
        "BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_REUSED_OR_PREVIOUS"
    )
    BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_RESULT_EXPOSURE = (
        "BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_RESULT_EXPOSURE"
    )
    BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ENV_OR_CREDENTIAL = (
        "BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ENV_OR_CREDENTIAL"
    )
    BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_EXECUTION = (
        "BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_EXECUTION"
    )
    BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_REAL_SIGNING_OR_POST = (
        "BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_REAL_SIGNING_OR_POST"
    )
    BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_DISPLAY_OR_SAVE = (
        "BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_DISPLAY_OR_SAVE"
    )


class LiveOrderRealOperatorExecutionResultCategoryContractMode(str, Enum):
    OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ONLY = (
        "OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ONLY"
    )


class LiveOrderRealOperatorExecutionResultCategory(str, Enum):
    NOT_PROVIDED = "NOT_PROVIDED"
    READY_CONFIRMED = "READY_CONFIRMED"
    BLOCKED_UNKNOWN = "BLOCKED_UNKNOWN"
    BLOCKED_FAILED = "BLOCKED_FAILED"
    BLOCKED_UNAVAILABLE = "BLOCKED_UNAVAILABLE"
    BLOCKED_STALE = "BLOCKED_STALE"
    BLOCKED_TIMEOUT = "BLOCKED_TIMEOUT"
    BLOCKED_REUSED = "BLOCKED_REUSED"
    BLOCKED_PREVIOUS_TURN = "BLOCKED_PREVIOUS_TURN"
    BLOCKED_UNSAFE_DETAIL = "BLOCKED_UNSAFE_DETAIL"
    BLOCKED_UNSUPPORTED = "BLOCKED_UNSUPPORTED"


OperatorExecutionResultCategoryContractStatus = (
    LiveOrderRealOperatorExecutionResultCategoryContractStatus
)
OperatorExecutionResultCategoryContractMode = (
    LiveOrderRealOperatorExecutionResultCategoryContractMode
)
OperatorExecutionResultCategory = LiveOrderRealOperatorExecutionResultCategory

_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT_CATEGORIES = frozenset(
    (
        OperatorExecutionResultCategory.BLOCKED_UNKNOWN.value,
        OperatorExecutionResultCategory.BLOCKED_FAILED.value,
        OperatorExecutionResultCategory.BLOCKED_UNAVAILABLE.value,
        OperatorExecutionResultCategory.BLOCKED_STALE.value,
        OperatorExecutionResultCategory.BLOCKED_TIMEOUT.value,
    ),
)
_REUSED_OR_PREVIOUS_CATEGORIES = frozenset(
    (
        OperatorExecutionResultCategory.BLOCKED_REUSED.value,
        OperatorExecutionResultCategory.BLOCKED_PREVIOUS_TURN.value,
    ),
)


@dataclass(frozen=True)
class LiveOrderRealOperatorExecutionResultCategoryContractInput:
    category_contract_mode: str = (
        OperatorExecutionResultCategoryContractMode
        .OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ONLY
        .value
    )
    category_contract_declared: bool = True
    allowed_category_set_declared: bool = True
    operator_executed_execution_boundary_ready: bool = True
    operator_result_handoff_safe: bool = True
    operator_checker_workflow_ready: bool = True
    operator_result_category: str = OperatorExecutionResultCategory.NOT_PROVIDED.value
    operator_result_category_is_safe_label: bool = True
    operator_result_category_is_allowed: bool = True
    operator_result_provided: bool = False
    operator_result_ready_confirmed: bool = False
    operator_result_blocked: bool = False
    operator_result_unknown: bool = False
    operator_result_failed: bool = False
    operator_result_unavailable: bool = False
    operator_result_stale: bool = False
    operator_result_timeout: bool = False
    operator_result_reused: bool = False
    operator_result_previous_turn: bool = False
    operator_result_detail_present: bool = False
    operator_result_raw_value_present: bool = False
    operator_result_saved: bool = False
    operator_result_displayed: bool = False
    operator_result_broadly_propagated: bool = False
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
        _require_non_empty("category_contract_mode", self.category_contract_mode)
        _require_non_empty("operator_result_category", self.operator_result_category)
        _validate_bool_fields(
            self,
            (
                "category_contract_declared",
                "allowed_category_set_declared",
                "operator_executed_execution_boundary_ready",
                "operator_result_handoff_safe",
                "operator_checker_workflow_ready",
                "operator_result_category_is_safe_label",
                "operator_result_category_is_allowed",
                "operator_result_provided",
                "operator_result_ready_confirmed",
                "operator_result_blocked",
                "operator_result_unknown",
                "operator_result_failed",
                "operator_result_unavailable",
                "operator_result_stale",
                "operator_result_timeout",
                "operator_result_reused",
                "operator_result_previous_turn",
                "operator_result_detail_present",
                "operator_result_raw_value_present",
                "operator_result_saved",
                "operator_result_displayed",
                "operator_result_broadly_propagated",
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
class LiveOrderRealOperatorExecutionResultCategoryContractCheckResult:
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
class LiveOrderRealOperatorExecutionResultCategoryContractResult:
    status: LiveOrderRealOperatorExecutionResultCategoryContractStatus
    operator_execution_result_category_contract_ready: bool
    category_contract_mode: str
    unsupported_category_present: bool
    raw_category_displayed: bool
    raw_category_saved: bool
    category_contract_declared: bool
    allowed_category_set_declared: bool
    operator_executed_execution_boundary_ready: bool
    operator_result_handoff_safe: bool
    operator_checker_workflow_ready: bool
    operator_result_category: str
    operator_result_category_is_safe_label: bool
    operator_result_category_is_allowed: bool
    operator_result_provided: bool
    operator_result_ready_confirmed: bool
    operator_result_blocked: bool
    operator_result_unknown: bool
    operator_result_failed: bool
    operator_result_unavailable: bool
    operator_result_stale: bool
    operator_result_timeout: bool
    operator_result_reused: bool
    operator_result_previous_turn: bool
    operator_result_detail_present: bool
    operator_result_raw_value_present: bool
    operator_result_saved: bool
    operator_result_displayed: bool
    operator_result_broadly_propagated: bool
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
    check_results: tuple[
        LiveOrderRealOperatorExecutionResultCategoryContractCheckResult,
        ...,
    ]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealOperatorExecutionResultCategoryContractStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be operator execution result category contract status",
            )
        _require_non_empty("category_contract_mode", self.category_contract_mode)
        _require_non_empty("operator_result_category", self.operator_result_category)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "operator_execution_result_category_contract_ready",
                "unsupported_category_present",
                "raw_category_displayed",
                "raw_category_saved",
                "category_contract_declared",
                "allowed_category_set_declared",
                "operator_executed_execution_boundary_ready",
                "operator_result_handoff_safe",
                "operator_checker_workflow_ready",
                "operator_result_category_is_safe_label",
                "operator_result_category_is_allowed",
                "operator_result_provided",
                "operator_result_ready_confirmed",
                "operator_result_blocked",
                "operator_result_unknown",
                "operator_result_failed",
                "operator_result_unavailable",
                "operator_result_stale",
                "operator_result_timeout",
                "operator_result_reused",
                "operator_result_previous_turn",
                "operator_result_detail_present",
                "operator_result_raw_value_present",
                "operator_result_saved",
                "operator_result_displayed",
                "operator_result_broadly_propagated",
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


def build_live_order_real_operator_execution_result_category_contract(
    *,
    input_snapshot: LiveOrderRealOperatorExecutionResultCategoryContractInput | None = None,
) -> LiveOrderRealOperatorExecutionResultCategoryContractResult:
    """Build sanitized operator execution result category metadata only."""
    category_input = (
        input_snapshot or LiveOrderRealOperatorExecutionResultCategoryContractInput()
    )
    safe_category = _safe_category_label(category_input.operator_result_category)
    unsupported_category_present = _has_unsupported_category(category_input)

    input_reasons = _input_reasons(category_input)
    unsupported_category_reasons = _unsupported_category_reasons(category_input)
    unsafe_category_reasons = _unsafe_category_reasons(category_input)
    unknown_reasons = _unknown_failed_unavailable_timeout_reasons(category_input)
    reused_reasons = _reused_or_previous_reasons(category_input)
    result_exposure_reasons = _result_exposure_reasons(category_input)
    env_or_credential_reasons = _env_or_credential_reasons(category_input)
    execution_reasons = _execution_reasons(category_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(category_input)
    display_reasons = _display_or_save_reasons(category_input)

    if input_reasons:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_INPUT
        )
        primary_reasons = input_reasons
    elif unsupported_category_reasons:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNSUPPORTED_CATEGORY
        )
        primary_reasons = unsupported_category_reasons
    elif unsafe_category_reasons:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNSAFE_CATEGORY
        )
        primary_reasons = unsafe_category_reasons
    elif unknown_reasons:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT
        )
        primary_reasons = unknown_reasons
    elif reused_reasons:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_REUSED_OR_PREVIOUS
        )
        primary_reasons = reused_reasons
    elif result_exposure_reasons:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_RESULT_EXPOSURE
        )
        primary_reasons = result_exposure_reasons
    elif env_or_credential_reasons:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ENV_OR_CREDENTIAL
        )
        primary_reasons = env_or_credential_reasons
    elif execution_reasons:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_EXECUTION
        )
        primary_reasons = execution_reasons
    elif real_signing_or_post_reasons:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_REAL_SIGNING_OR_POST
        )
        primary_reasons = real_signing_or_post_reasons
    elif display_reasons:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_DISPLAY_OR_SAVE
        )
        primary_reasons = display_reasons
    elif safe_category == OperatorExecutionResultCategory.READY_CONFIRMED.value:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_CONFIRMED_NO_POST
        )
        primary_reasons = ()
    else:
        status = (
            OperatorExecutionResultCategoryContractStatus
            .OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_NO_RESULT
        )
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        input_reasons,
        unsupported_category_reasons,
        unsafe_category_reasons,
        unknown_reasons,
        reused_reasons,
        result_exposure_reasons,
        env_or_credential_reasons,
        execution_reasons,
        real_signing_or_post_reasons,
        display_reasons,
    )
    ready = status in (
        OperatorExecutionResultCategoryContractStatus
        .OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_NO_RESULT,
        OperatorExecutionResultCategoryContractStatus
        .OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_CONFIRMED_NO_POST,
    )
    ready_confirmed = (
        status
        is OperatorExecutionResultCategoryContractStatus
        .OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_CONFIRMED_NO_POST
    )
    return LiveOrderRealOperatorExecutionResultCategoryContractResult(
        status=status,
        operator_execution_result_category_contract_ready=ready,
        category_contract_mode=_safe_contract_mode(
            category_input.category_contract_mode,
        ),
        unsupported_category_present=unsupported_category_present,
        raw_category_displayed=False,
        raw_category_saved=False,
        category_contract_declared=category_input.category_contract_declared,
        allowed_category_set_declared=category_input.allowed_category_set_declared,
        operator_executed_execution_boundary_ready=(
            category_input.operator_executed_execution_boundary_ready
        ),
        operator_result_handoff_safe=category_input.operator_result_handoff_safe,
        operator_checker_workflow_ready=category_input.operator_checker_workflow_ready,
        operator_result_category=safe_category,
        operator_result_category_is_safe_label=(
            category_input.operator_result_category_is_safe_label
            and not unsupported_category_present
        ),
        operator_result_category_is_allowed=(
            category_input.operator_result_category_is_allowed
            and not unsupported_category_present
        ),
        operator_result_provided=ready_confirmed or category_input.operator_result_provided,
        operator_result_ready_confirmed=ready_confirmed,
        operator_result_blocked=bool(
            safe_category.startswith("BLOCKED_") or category_input.operator_result_blocked,
        ),
        operator_result_unknown=False,
        operator_result_failed=False,
        operator_result_unavailable=False,
        operator_result_stale=False,
        operator_result_timeout=False,
        operator_result_reused=False,
        operator_result_previous_turn=False,
        operator_result_detail_present=False,
        operator_result_raw_value_present=False,
        operator_result_saved=False,
        operator_result_displayed=False,
        operator_result_broadly_propagated=False,
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
        check_results=_build_check_results(category_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            OPERATOR_EXECUTION_RESULT_CATEGORY_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_operator_execution_result_category_contract_blockers_no_env_no_post"
        ),
    )


def render_live_order_real_operator_execution_result_category_contract_markdown(
    result: LiveOrderRealOperatorExecutionResultCategoryContractResult,
) -> str:
    """Render sanitized operator execution result category metadata only."""
    lines = [
        "# Step 6G Operator Execution Result Category Contract",
        "",
        "This operator execution result category contract is category-only.",
        "This contract does not execute the checker.",
        "This contract does not access env or .env.",
        "This contract does not read credentials.",
        "This contract does not expose raw operator result values.",
        "This contract does not expose operator result detail.",
        "READY_CONFIRMED does not allow POST.",
        "NOT_PROVIDED is not actual result receipt.",
        (
            "Unknown / failed / unavailable / stale / timeout / reused / "
            "previous-turn categories block POST."
        ),
        "This contract does not generate real signatures.",
        "This contract does not execute API calls.",
        "This contract does not execute HTTP POST.",
        "This contract does not call order endpoint.",
        "This contract does not call live_order_once.",
        "Future actual execution and final confirmation must be separate Steps.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- operator_execution_result_category_contract_ready: "
            f"{_bool_text(result.operator_execution_result_category_contract_ready)}"
        ),
        f"- category_contract_mode: {result.category_contract_mode}",
        (
            "- allowed_category_set_declared: "
            f"{_bool_text(result.allowed_category_set_declared)}"
        ),
        f"- operator_result_category: {result.operator_result_category}",
        (
            "- operator_result_category_is_safe_label: "
            f"{_bool_text(result.operator_result_category_is_safe_label)}"
        ),
        (
            "- operator_result_category_is_allowed: "
            f"{_bool_text(result.operator_result_category_is_allowed)}"
        ),
        f"- operator_result_provided: {_bool_text(result.operator_result_provided)}",
        (
            "- operator_result_ready_confirmed: "
            f"{_bool_text(result.operator_result_ready_confirmed)}"
        ),
        f"- operator_result_blocked: {_bool_text(result.operator_result_blocked)}",
        f"- actual_execution_performed: {_bool_text(result.actual_execution_performed)}",
        f"- codex_execution_performed: {_bool_text(result.codex_execution_performed)}",
        f"- env_access_requested: {_bool_text(result.env_access_requested)}",
        f"- credential_read_performed: {_bool_text(result.credential_read_performed)}",
        (
            "- operator_result_raw_value_present: "
            f"{_bool_text(result.operator_result_raw_value_present)}"
        ),
        (
            "- operator_result_detail_present: "
            f"{_bool_text(result.operator_result_detail_present)}"
        ),
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
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
) -> tuple[LiveOrderRealOperatorExecutionResultCategoryContractCheckResult, ...]:
    groups = (
        (
            "category contract input",
            _input_reasons(category_input),
            "category contract mode and prerequisite gates ready",
        ),
        (
            "safe allowed category label",
            _merge_reasons(
                _unsupported_category_reasons(category_input),
                _unsafe_category_reasons(category_input),
            ),
            "category is an allowed safe enum label",
        ),
        (
            "known non-stale non-timeout category",
            _unknown_failed_unavailable_timeout_reasons(category_input),
            "category is not unknown failed unavailable stale or timeout",
        ),
        (
            "not reused or previous turn",
            _reused_or_previous_reasons(category_input),
            "category is not reused or previous-turn",
        ),
        (
            "no result exposure",
            _result_exposure_reasons(category_input),
            "no raw result detail checker detail env names or sentinel values",
        ),
        (
            "no env or credential",
            _env_or_credential_reasons(category_input),
            "no env access credential read values or metadata",
        ),
        (
            "no execution",
            _execution_reasons(category_input),
            "no actual or Codex execution performed",
        ),
        (
            "no real signing or post",
            _real_signing_or_post_reasons(category_input),
            "no real signing headers API POST endpoint or live_order_once",
        ),
        (
            "safe render and serialization",
            _display_or_save_reasons(category_input),
            "render and serialization are safe",
        ),
    )
    return tuple(
        LiveOrderRealOperatorExecutionResultCategoryContractCheckResult(
            name=name,
            passed=not reasons,
            sanitized_value="ready" if not reasons else ",".join(reasons),
            expected=expected,
        )
        for name, reasons, expected in groups
    )


def _input_reasons(
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_unsupported_contract_mode(category_input.category_contract_mode):
        reasons.append("category_contract_mode_unsupported")
    for field_name in (
        "category_contract_declared",
        "allowed_category_set_declared",
        "operator_executed_execution_boundary_ready",
        "operator_result_handoff_safe",
        "operator_checker_workflow_ready",
    ):
        if not getattr(category_input, field_name):
            reasons.append(f"{field_name}_false")
    return tuple(reasons)


def _unsupported_category_reasons(
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_unsupported_category(category_input):
        reasons.append("operator_result_category_unsupported")
    if not category_input.operator_result_category_is_allowed:
        reasons.append("operator_result_category_is_allowed_false")
    if (
        _safe_category_label(category_input.operator_result_category)
        == OperatorExecutionResultCategory.BLOCKED_UNSUPPORTED.value
    ):
        reasons.append("operator_result_category_blocked_unsupported")
    return tuple(reasons)


def _unsafe_category_reasons(
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    safe_category = _safe_category_label(category_input.operator_result_category)
    if not category_input.operator_result_category_is_safe_label:
        reasons.append("operator_result_category_is_safe_label_false")
    if safe_category == OperatorExecutionResultCategory.READY_CONFIRMED.value:
        if not category_input.operator_result_provided:
            reasons.append("ready_confirmed_requires_operator_result_provided")
        if not category_input.operator_result_ready_confirmed:
            reasons.append("ready_confirmed_requires_ready_flag")
        if category_input.operator_result_blocked:
            reasons.append("ready_confirmed_must_not_be_blocked")
    if safe_category == OperatorExecutionResultCategory.NOT_PROVIDED.value:
        if category_input.operator_result_provided:
            reasons.append("not_provided_must_not_mark_result_provided")
        if category_input.operator_result_ready_confirmed:
            reasons.append("not_provided_must_not_mark_ready_confirmed")
        if category_input.operator_result_blocked:
            reasons.append("not_provided_must_not_mark_blocked")
    if safe_category == OperatorExecutionResultCategory.BLOCKED_UNSAFE_DETAIL.value:
        reasons.append("operator_result_category_blocked_unsafe_detail")
    return tuple(reasons)


def _unknown_failed_unavailable_timeout_reasons(
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    safe_category = _safe_category_label(category_input.operator_result_category)
    if safe_category in _UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT_CATEGORIES:
        reasons.append(f"operator_result_category_{safe_category.lower()}")
    for field_name in (
        "operator_result_unknown",
        "operator_result_failed",
        "operator_result_unavailable",
        "operator_result_stale",
        "operator_result_timeout",
    ):
        if getattr(category_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _reused_or_previous_reasons(
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    safe_category = _safe_category_label(category_input.operator_result_category)
    if safe_category in _REUSED_OR_PREVIOUS_CATEGORIES:
        reasons.append(f"operator_result_category_{safe_category.lower()}")
    for field_name in (
        "operator_result_reused",
        "operator_result_previous_turn",
    ):
        if getattr(category_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _result_exposure_reasons(
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "operator_result_detail_present",
        "operator_result_raw_value_present",
        "operator_result_saved",
        "operator_result_displayed",
        "operator_result_broadly_propagated",
        "checker_result_detail_present",
        "sentinel_value_present",
    ):
        if getattr(category_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _env_or_credential_reasons(
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "env_variable_names_present",
        "credential_values_present",
        "credential_metadata_present",
        "env_access_requested",
        "credential_read_performed",
    ):
        if getattr(category_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _execution_reasons(
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if category_input.actual_execution_performed:
        reasons.append("actual_execution_performed_unsafe")
    if category_input.codex_execution_performed:
        reasons.append("codex_execution_performed_unsafe")
    return tuple(reasons)


def _real_signing_or_post_reasons(
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
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
        if getattr(category_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _display_or_save_reasons(
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not category_input.safe_to_render:
        reasons.append("safe_to_render_false")
    if not category_input.safe_to_serialize:
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
    result: LiveOrderRealOperatorExecutionResultCategoryContractResult,
) -> None:
    unsafe_flags = (
        result.raw_category_displayed,
        result.raw_category_saved,
        result.operator_result_unknown,
        result.operator_result_failed,
        result.operator_result_unavailable,
        result.operator_result_stale,
        result.operator_result_timeout,
        result.operator_result_reused,
        result.operator_result_previous_turn,
        result.operator_result_detail_present,
        result.operator_result_raw_value_present,
        result.operator_result_saved,
        result.operator_result_displayed,
        result.operator_result_broadly_propagated,
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
            "operator execution result category contract result is unsafe",
        )
    if result.unsupported_category_present:
        if result.operator_result_category != UNSUPPORTED_OPERATOR_EXECUTION_RESULT_CATEGORY_LABEL:
            raise LiveVerificationValidationError(
                "unsupported operator result category must use safe label",
            )
    elif result.operator_result_category not in _allowed_category_values():
        raise LiveVerificationValidationError(
            "operator result category must be an allowed safe label",
        )
    if result.operator_result_ready_confirmed:
        if result.post_allowed_this_step or result.post_executed:
            raise LiveVerificationValidationError(
                "READY_CONFIRMED must not allow or execute POST",
            )


def _has_unsupported_contract_mode(raw_mode: str) -> bool:
    return (
        raw_mode
        != OperatorExecutionResultCategoryContractMode
        .OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ONLY
        .value
    )


def _safe_contract_mode(raw_mode: str) -> str:
    if not _has_unsupported_contract_mode(raw_mode):
        return raw_mode
    return UNSUPPORTED_OPERATOR_EXECUTION_RESULT_CATEGORY_LABEL


def _has_unsupported_category(
    category_input: LiveOrderRealOperatorExecutionResultCategoryContractInput,
) -> bool:
    return category_input.operator_result_category not in _allowed_category_values()


def _safe_category_label(raw_category: str) -> str:
    if raw_category in _allowed_category_values():
        return raw_category
    return UNSUPPORTED_OPERATOR_EXECUTION_RESULT_CATEGORY_LABEL


def _allowed_category_values() -> frozenset[str]:
    return frozenset(category.value for category in OperatorExecutionResultCategory)


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{name} must be non-empty string")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
