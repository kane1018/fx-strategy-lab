"""Step 6G operator-executed checker execution boundary skeleton.

This module formalizes the boundary between a future checker execution that
must remain outside Codex and the safe boolean/category handoff that Codex may
consume later. It does not read env, execute a checker, inspect credential
values or metadata, expose operator result details, generate signatures or
header values, call APIs, or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

OPERATOR_EXECUTED_EXECUTION_BOUNDARY_RECOMMENDED_NEXT_STEP = (
    "future_actual_checker_execution_must_be_a_separate_step_outside_codex"
)
UNSUPPORTED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_MODE_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealOperatorExecutedExecutionBoundaryStatus(str, Enum):
    OPERATOR_EXECUTED_EXECUTION_BOUNDARY_READY_NO_ENV_NO_CHECK = (
        "OPERATOR_EXECUTED_EXECUTION_BOUNDARY_READY_NO_ENV_NO_CHECK"
    )
    BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_INPUT = (
        "BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_INPUT"
    )
    BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_CODEX_EXECUTION = (
        "BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_CODEX_EXECUTION"
    )
    BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_OPERATOR_EXECUTION = (
        "BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_OPERATOR_EXECUTION"
    )
    BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_ENV_ACCESS = (
        "BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_ENV_ACCESS"
    )
    BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_CREDENTIAL_READ = (
        "BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_CREDENTIAL_READ"
    )
    BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_RESULT_EXPOSURE = (
        "BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_RESULT_EXPOSURE"
    )
    BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT = (  # noqa: E501
        "BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT"
    )
    BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_OPERATOR_HANDOFF = (
        "BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_OPERATOR_HANDOFF"
    )
    BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_REAL_SIGNING_OR_POST = (
        "BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_REAL_SIGNING_OR_POST"
    )
    BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_DISPLAY_OR_SAVE = (
        "BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_DISPLAY_OR_SAVE"
    )
    BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_UNSUPPORTED = (
        "BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_UNSUPPORTED"
    )


class LiveOrderRealOperatorExecutedExecutionBoundaryMode(str, Enum):
    OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY = (
        "OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY"
    )


OperatorExecutedExecutionBoundaryStatus = (
    LiveOrderRealOperatorExecutedExecutionBoundaryStatus
)
OperatorExecutedExecutionBoundaryMode = (
    LiveOrderRealOperatorExecutedExecutionBoundaryMode
)


@dataclass(frozen=True)
class LiveOrderRealOperatorExecutedExecutionBoundaryInput:
    boundary_mode: str = (
        OperatorExecutedExecutionBoundaryMode
        .OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY
        .value
    )
    boundary_declared: bool = True
    operator_execution_boundary_declared: bool = True
    operator_execution_must_be_outside_codex: bool = True
    codex_execution_forbidden: bool = True
    checker_execution_implementation_skeleton_ready: bool = True
    checker_execution_contract_ready: bool = True
    operator_result_handoff_safe: bool = True
    operator_checker_workflow_ready: bool = True
    operator_execution_performed: bool = False
    codex_execution_performed: bool = False
    env_access_requested: bool = False
    codex_env_access_requested: bool = False
    actual_environment_presence_check_performed: bool = False
    credential_read_performed: bool = False
    credential_values_present: bool = False
    credential_metadata_present: bool = False
    operator_result_provided: bool = False
    operator_result_safe_boolean_category_only: bool = True
    operator_result_detail_present: bool = False
    operator_result_raw_value_present: bool = False
    operator_result_unknown: bool = False
    operator_result_failed: bool = False
    operator_result_unavailable: bool = False
    operator_result_stale: bool = False
    operator_result_timeout: bool = False
    operator_result_reused: bool = False
    operator_result_previous_turn: bool = False
    operator_result_saved: bool = False
    operator_result_displayed: bool = False
    operator_result_broadly_propagated: bool = False
    checker_result_detail_present: bool = False
    env_variable_names_present: bool = False
    sentinel_value_present: bool = False
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
    retry_allowed: bool = False
    loop_allowed: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("boundary_mode", self.boundary_mode)
        _validate_bool_fields(
            self,
            (
                "boundary_declared",
                "operator_execution_boundary_declared",
                "operator_execution_must_be_outside_codex",
                "codex_execution_forbidden",
                "checker_execution_implementation_skeleton_ready",
                "checker_execution_contract_ready",
                "operator_result_handoff_safe",
                "operator_checker_workflow_ready",
                "operator_execution_performed",
                "codex_execution_performed",
                "env_access_requested",
                "codex_env_access_requested",
                "actual_environment_presence_check_performed",
                "credential_read_performed",
                "credential_values_present",
                "credential_metadata_present",
                "operator_result_provided",
                "operator_result_safe_boolean_category_only",
                "operator_result_detail_present",
                "operator_result_raw_value_present",
                "operator_result_unknown",
                "operator_result_failed",
                "operator_result_unavailable",
                "operator_result_stale",
                "operator_result_timeout",
                "operator_result_reused",
                "operator_result_previous_turn",
                "operator_result_saved",
                "operator_result_displayed",
                "operator_result_broadly_propagated",
                "checker_result_detail_present",
                "env_variable_names_present",
                "sentinel_value_present",
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
                "retry_allowed",
                "loop_allowed",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealOperatorExecutedExecutionBoundaryCheckResult:
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
class LiveOrderRealOperatorExecutedExecutionBoundaryResult:
    status: LiveOrderRealOperatorExecutedExecutionBoundaryStatus
    operator_executed_execution_boundary_ready: bool
    boundary_mode: str
    unsupported_boundary_mode_present: bool
    raw_boundary_mode_displayed: bool
    raw_boundary_mode_saved: bool
    boundary_declared: bool
    operator_execution_boundary_declared: bool
    operator_execution_must_be_outside_codex: bool
    codex_execution_forbidden: bool
    checker_execution_implementation_skeleton_ready: bool
    checker_execution_contract_ready: bool
    operator_result_handoff_safe: bool
    operator_checker_workflow_ready: bool
    operator_execution_performed: bool
    codex_execution_performed: bool
    env_access_requested: bool
    codex_env_access_requested: bool
    actual_environment_presence_check_performed: bool
    credential_read_performed: bool
    credential_values_present: bool
    credential_metadata_present: bool
    operator_result_provided: bool
    operator_result_safe_boolean_category_only: bool
    operator_result_detail_present: bool
    operator_result_raw_value_present: bool
    operator_result_unknown: bool
    operator_result_failed: bool
    operator_result_unavailable: bool
    operator_result_stale: bool
    operator_result_timeout: bool
    operator_result_reused: bool
    operator_result_previous_turn: bool
    operator_result_saved: bool
    operator_result_displayed: bool
    operator_result_broadly_propagated: bool
    checker_result_detail_present: bool
    env_variable_names_present: bool
    sentinel_value_present: bool
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
    retry_allowed: bool
    loop_allowed: bool
    check_results: tuple[LiveOrderRealOperatorExecutedExecutionBoundaryCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealOperatorExecutedExecutionBoundaryStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be operator executed execution boundary status",
            )
        _require_non_empty("boundary_mode", self.boundary_mode)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "operator_executed_execution_boundary_ready",
                "unsupported_boundary_mode_present",
                "raw_boundary_mode_displayed",
                "raw_boundary_mode_saved",
                "boundary_declared",
                "operator_execution_boundary_declared",
                "operator_execution_must_be_outside_codex",
                "codex_execution_forbidden",
                "checker_execution_implementation_skeleton_ready",
                "checker_execution_contract_ready",
                "operator_result_handoff_safe",
                "operator_checker_workflow_ready",
                "operator_execution_performed",
                "codex_execution_performed",
                "env_access_requested",
                "codex_env_access_requested",
                "actual_environment_presence_check_performed",
                "credential_read_performed",
                "credential_values_present",
                "credential_metadata_present",
                "operator_result_provided",
                "operator_result_safe_boolean_category_only",
                "operator_result_detail_present",
                "operator_result_raw_value_present",
                "operator_result_unknown",
                "operator_result_failed",
                "operator_result_unavailable",
                "operator_result_stale",
                "operator_result_timeout",
                "operator_result_reused",
                "operator_result_previous_turn",
                "operator_result_saved",
                "operator_result_displayed",
                "operator_result_broadly_propagated",
                "checker_result_detail_present",
                "env_variable_names_present",
                "sentinel_value_present",
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
                "retry_allowed",
                "loop_allowed",
            ),
        )
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_operator_executed_execution_boundary(
    *,
    input_snapshot: LiveOrderRealOperatorExecutedExecutionBoundaryInput | None = None,
) -> LiveOrderRealOperatorExecutedExecutionBoundaryResult:
    """Build operator-executed boundary metadata only."""
    boundary_input = input_snapshot or LiveOrderRealOperatorExecutedExecutionBoundaryInput()
    safe_boundary_mode = _safe_boundary_mode(boundary_input.boundary_mode)
    unsupported_boundary_mode_present = _has_unsupported_boundary_mode(boundary_input)

    input_reasons = _input_reasons(boundary_input)
    codex_execution_reasons = _codex_execution_reasons(boundary_input)
    operator_execution_reasons = _operator_execution_reasons(boundary_input)
    env_reasons = _env_reasons(boundary_input)
    credential_read_reasons = _credential_read_reasons(boundary_input)
    result_exposure_reasons = _result_exposure_reasons(boundary_input)
    unknown_reasons = _unknown_failed_unavailable_timeout_reasons(boundary_input)
    operator_handoff_reasons = _operator_handoff_reasons(boundary_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(boundary_input)
    display_reasons = _display_or_save_reasons(boundary_input)
    unsupported_reasons = _unsupported_reasons(boundary_input)

    if input_reasons:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_INPUT
        )
        primary_reasons = input_reasons
    elif codex_execution_reasons:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_CODEX_EXECUTION
        )
        primary_reasons = codex_execution_reasons
    elif operator_execution_reasons:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_OPERATOR_EXECUTION
        )
        primary_reasons = operator_execution_reasons
    elif env_reasons:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_ENV_ACCESS
        )
        primary_reasons = env_reasons
    elif credential_read_reasons:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_CREDENTIAL_READ
        )
        primary_reasons = credential_read_reasons
    elif result_exposure_reasons:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_RESULT_EXPOSURE
        )
        primary_reasons = result_exposure_reasons
    elif unknown_reasons:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT
        )
        primary_reasons = unknown_reasons
    elif operator_handoff_reasons:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_OPERATOR_HANDOFF
        )
        primary_reasons = operator_handoff_reasons
    elif real_signing_or_post_reasons:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_REAL_SIGNING_OR_POST
        )
        primary_reasons = real_signing_or_post_reasons
    elif display_reasons:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_DISPLAY_OR_SAVE
        )
        primary_reasons = display_reasons
    elif unsupported_reasons:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_UNSUPPORTED
        )
        primary_reasons = unsupported_reasons
    else:
        status = (
            OperatorExecutedExecutionBoundaryStatus
            .OPERATOR_EXECUTED_EXECUTION_BOUNDARY_READY_NO_ENV_NO_CHECK
        )
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        input_reasons,
        codex_execution_reasons,
        operator_execution_reasons,
        env_reasons,
        credential_read_reasons,
        result_exposure_reasons,
        unknown_reasons,
        operator_handoff_reasons,
        real_signing_or_post_reasons,
        display_reasons,
        unsupported_reasons,
    )
    ready = (
        status
        is OperatorExecutedExecutionBoundaryStatus
        .OPERATOR_EXECUTED_EXECUTION_BOUNDARY_READY_NO_ENV_NO_CHECK
    )
    return LiveOrderRealOperatorExecutedExecutionBoundaryResult(
        status=status,
        operator_executed_execution_boundary_ready=ready,
        boundary_mode=safe_boundary_mode,
        unsupported_boundary_mode_present=unsupported_boundary_mode_present,
        raw_boundary_mode_displayed=False,
        raw_boundary_mode_saved=False,
        boundary_declared=boundary_input.boundary_declared,
        operator_execution_boundary_declared=(
            boundary_input.operator_execution_boundary_declared
        ),
        operator_execution_must_be_outside_codex=(
            boundary_input.operator_execution_must_be_outside_codex
        ),
        codex_execution_forbidden=boundary_input.codex_execution_forbidden,
        checker_execution_implementation_skeleton_ready=(
            boundary_input.checker_execution_implementation_skeleton_ready
        ),
        checker_execution_contract_ready=(
            boundary_input.checker_execution_contract_ready
        ),
        operator_result_handoff_safe=boundary_input.operator_result_handoff_safe,
        operator_checker_workflow_ready=boundary_input.operator_checker_workflow_ready,
        operator_execution_performed=False,
        codex_execution_performed=False,
        env_access_requested=False,
        codex_env_access_requested=False,
        actual_environment_presence_check_performed=False,
        credential_read_performed=False,
        credential_values_present=False,
        credential_metadata_present=False,
        operator_result_provided=False,
        operator_result_safe_boolean_category_only=(
            boundary_input.operator_result_safe_boolean_category_only
        ),
        operator_result_detail_present=False,
        operator_result_raw_value_present=False,
        operator_result_unknown=False,
        operator_result_failed=False,
        operator_result_unavailable=False,
        operator_result_stale=False,
        operator_result_timeout=False,
        operator_result_reused=False,
        operator_result_previous_turn=False,
        operator_result_saved=False,
        operator_result_displayed=False,
        operator_result_broadly_propagated=False,
        checker_result_detail_present=False,
        env_variable_names_present=False,
        sentinel_value_present=False,
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
        retry_allowed=False,
        loop_allowed=False,
        check_results=_build_check_results(boundary_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            OPERATOR_EXECUTED_EXECUTION_BOUNDARY_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_operator_executed_execution_boundary_blockers_no_env_no_post"
        ),
    )


def render_live_order_real_operator_executed_execution_boundary_markdown(
    result: LiveOrderRealOperatorExecutedExecutionBoundaryResult,
) -> str:
    """Render sanitized operator-executed boundary metadata only."""
    lines = [
        "# Step 6G Operator-Executed Execution Boundary",
        "",
        "This operator-executed execution boundary is skeleton-only.",
        "This boundary keeps actual checker execution outside Codex.",
        "This boundary does not execute the checker.",
        "This boundary does not access env or .env.",
        "This boundary does not read credentials.",
        "This boundary does not perform an actual environment presence check.",
        "Codex receives only safe boolean/category handoff.",
        "Unknown / failed / unavailable / stale / timeout results block POST.",
        "This boundary does not generate real signatures.",
        "This boundary does not execute API calls.",
        "This boundary does not execute HTTP POST.",
        "This boundary does not call order endpoint.",
        "This boundary does not call live_order_once.",
        "Future actual execution must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- operator_executed_execution_boundary_ready: "
            f"{_bool_text(result.operator_executed_execution_boundary_ready)}"
        ),
        f"- boundary_mode: {result.boundary_mode}",
        (
            "- unsupported_boundary_mode_present: "
            f"{_bool_text(result.unsupported_boundary_mode_present)}"
        ),
        (
            "- raw_boundary_mode_displayed: "
            f"{_bool_text(result.raw_boundary_mode_displayed)}"
        ),
        (
            "- raw_boundary_mode_saved: "
            f"{_bool_text(result.raw_boundary_mode_saved)}"
        ),
        "",
        "## Boundary Safety",
        f"- boundary_declared: {_bool_text(result.boundary_declared)}",
        (
            "- operator_execution_boundary_declared: "
            f"{_bool_text(result.operator_execution_boundary_declared)}"
        ),
        (
            "- operator_execution_must_be_outside_codex: "
            f"{_bool_text(result.operator_execution_must_be_outside_codex)}"
        ),
        f"- codex_execution_forbidden: {_bool_text(result.codex_execution_forbidden)}",
        (
            "- checker_execution_implementation_skeleton_ready: "
            f"{_bool_text(result.checker_execution_implementation_skeleton_ready)}"
        ),
        (
            "- checker_execution_contract_ready: "
            f"{_bool_text(result.checker_execution_contract_ready)}"
        ),
        (
            "- operator_result_handoff_safe: "
            f"{_bool_text(result.operator_result_handoff_safe)}"
        ),
        (
            "- operator_checker_workflow_ready: "
            f"{_bool_text(result.operator_checker_workflow_ready)}"
        ),
        f"- operator_execution_performed: {_bool_text(result.operator_execution_performed)}",
        f"- codex_execution_performed: {_bool_text(result.codex_execution_performed)}",
        f"- env_access_requested: {_bool_text(result.env_access_requested)}",
        (
            "- codex_env_access_requested: "
            f"{_bool_text(result.codex_env_access_requested)}"
        ),
        (
            "- actual_environment_presence_check_performed: "
            f"{_bool_text(result.actual_environment_presence_check_performed)}"
        ),
        f"- credential_read_performed: {_bool_text(result.credential_read_performed)}",
        f"- credential_values_present: {_bool_text(result.credential_values_present)}",
        (
            "- credential_metadata_present: "
            f"{_bool_text(result.credential_metadata_present)}"
        ),
        f"- operator_result_provided: {_bool_text(result.operator_result_provided)}",
        (
            "- operator_result_safe_boolean_category_only: "
            f"{_bool_text(result.operator_result_safe_boolean_category_only)}"
        ),
        (
            "- operator_result_detail_present: "
            f"{_bool_text(result.operator_result_detail_present)}"
        ),
        (
            "- operator_result_raw_value_present: "
            f"{_bool_text(result.operator_result_raw_value_present)}"
        ),
        f"- operator_result_unknown: {_bool_text(result.operator_result_unknown)}",
        f"- operator_result_failed: {_bool_text(result.operator_result_failed)}",
        (
            "- operator_result_unavailable: "
            f"{_bool_text(result.operator_result_unavailable)}"
        ),
        f"- operator_result_stale: {_bool_text(result.operator_result_stale)}",
        f"- operator_result_timeout: {_bool_text(result.operator_result_timeout)}",
        f"- operator_result_reused: {_bool_text(result.operator_result_reused)}",
        (
            "- operator_result_previous_turn: "
            f"{_bool_text(result.operator_result_previous_turn)}"
        ),
        (
            "- checker_result_detail_present: "
            f"{_bool_text(result.checker_result_detail_present)}"
        ),
        (
            "- env_variable_names_present: "
            f"{_bool_text(result.env_variable_names_present)}"
        ),
        f"- sentinel_value_present: {_bool_text(result.sentinel_value_present)}",
        (
            "- can_generate_real_signature: "
            f"{_bool_text(result.can_generate_real_signature)}"
        ),
        f"- can_generate_real_headers: {_bool_text(result.can_generate_real_headers)}",
        f"- can_execute_http_post: {_bool_text(result.can_execute_http_post)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- safe_to_render: {_bool_text(result.safe_to_render)}",
        f"- safe_to_serialize: {_bool_text(result.safe_to_serialize)}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def _build_check_results(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> tuple[LiveOrderRealOperatorExecutedExecutionBoundaryCheckResult, ...]:
    groups = (
        (
            "operator executed execution boundary input",
            _input_reasons(boundary_input),
            "boundary skeleton mode and prerequisite gates ready",
        ),
        (
            "Codex execution forbidden",
            _codex_execution_reasons(boundary_input),
            "Codex execution remains forbidden and not performed",
        ),
        (
            "operator execution deferred",
            _operator_execution_reasons(boundary_input),
            "operator execution is not performed in this skeleton step",
        ),
        (
            "no env access",
            _env_reasons(boundary_input),
            "Codex does not request env or .env access",
        ),
        (
            "no credential read",
            _credential_read_reasons(boundary_input),
            "no credential read values or metadata",
        ),
        (
            "no result exposure",
            _result_exposure_reasons(boundary_input),
            "no operator detail checker detail env names or sentinel values",
        ),
        (
            "known non-stale non-timeout operator result state",
            _unknown_failed_unavailable_timeout_reasons(boundary_input),
            "operator result is not unknown failed unavailable stale or timeout",
        ),
        (
            "safe operator handoff",
            _operator_handoff_reasons(boundary_input),
            "handoff has no raw previous reused or pre-provided result",
        ),
        (
            "no real signing or post",
            _real_signing_or_post_reasons(boundary_input),
            "no real signing headers API post endpoint or live_order_once",
        ),
    )
    return tuple(
        LiveOrderRealOperatorExecutedExecutionBoundaryCheckResult(
            name=name,
            passed=not reasons,
            sanitized_value="ready" if not reasons else ",".join(reasons),
            expected=expected,
        )
        for name, reasons, expected in groups
    )


def _input_reasons(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_unsupported_boundary_mode(boundary_input):
        reasons.append("boundary_mode_unsupported")
    for field_name in (
        "boundary_declared",
        "operator_execution_boundary_declared",
        "operator_execution_must_be_outside_codex",
        "checker_execution_implementation_skeleton_ready",
        "checker_execution_contract_ready",
        "operator_checker_workflow_ready",
    ):
        if not getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_false")
    return tuple(reasons)


def _codex_execution_reasons(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not boundary_input.codex_execution_forbidden:
        reasons.append("codex_execution_forbidden_false")
    if boundary_input.codex_execution_performed:
        reasons.append("codex_execution_performed_unsafe")
    return tuple(reasons)


def _operator_execution_reasons(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if boundary_input.operator_execution_performed:
        reasons.append("operator_execution_performed_unsafe")
    return tuple(reasons)


def _env_reasons(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "env_access_requested",
        "codex_env_access_requested",
        "actual_environment_presence_check_performed",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_read_reasons(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_read_performed",
        "credential_values_present",
        "credential_metadata_present",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _result_exposure_reasons(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "operator_result_detail_present",
        "operator_result_saved",
        "operator_result_displayed",
        "operator_result_broadly_propagated",
        "checker_result_detail_present",
        "env_variable_names_present",
        "sentinel_value_present",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _unknown_failed_unavailable_timeout_reasons(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "operator_result_unknown",
        "operator_result_failed",
        "operator_result_unavailable",
        "operator_result_stale",
        "operator_result_timeout",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _operator_handoff_reasons(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not boundary_input.operator_result_handoff_safe:
        reasons.append("operator_result_handoff_safe_false")
    if boundary_input.operator_result_provided:
        reasons.append("operator_result_provided_before_future_execution")
    if not boundary_input.operator_result_safe_boolean_category_only:
        reasons.append("operator_result_safe_boolean_category_only_false")
    for field_name in (
        "operator_result_raw_value_present",
        "operator_result_reused",
        "operator_result_previous_turn",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_signing_or_post_reasons(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
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
        if getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _display_or_save_reasons(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not boundary_input.safe_to_render:
        reasons.append("safe_to_render_false")
    if not boundary_input.safe_to_serialize:
        reasons.append("safe_to_serialize_false")
    return tuple(reasons)


def _unsupported_reasons(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if boundary_input.retry_allowed:
        reasons.append("retry_allowed_unsupported")
    if boundary_input.loop_allowed:
        reasons.append("loop_allowed_unsupported")
    return tuple(reasons)


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _validate_result_safety(
    result: LiveOrderRealOperatorExecutedExecutionBoundaryResult,
) -> None:
    unsafe_flags = (
        result.raw_boundary_mode_displayed,
        result.raw_boundary_mode_saved,
        result.operator_execution_performed,
        result.codex_execution_performed,
        result.env_access_requested,
        result.codex_env_access_requested,
        result.actual_environment_presence_check_performed,
        result.credential_read_performed,
        result.credential_values_present,
        result.credential_metadata_present,
        result.operator_result_provided,
        result.operator_result_detail_present,
        result.operator_result_raw_value_present,
        result.operator_result_unknown,
        result.operator_result_failed,
        result.operator_result_unavailable,
        result.operator_result_stale,
        result.operator_result_timeout,
        result.operator_result_reused,
        result.operator_result_previous_turn,
        result.operator_result_saved,
        result.operator_result_displayed,
        result.operator_result_broadly_propagated,
        result.checker_result_detail_present,
        result.env_variable_names_present,
        result.sentinel_value_present,
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
        result.retry_allowed,
        result.loop_allowed,
    )
    if any(unsafe_flags):
        raise LiveVerificationValidationError(
            "operator executed execution boundary result is unsafe",
        )
    if result.unsupported_boundary_mode_present:
        if (
            result.boundary_mode
            != UNSUPPORTED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_MODE_LABEL
        ):
            raise LiveVerificationValidationError(
                "unsupported operator executed execution boundary mode must use safe label",
            )
    elif (
        result.boundary_mode
        != OperatorExecutedExecutionBoundaryMode
        .OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY
        .value
    ):
        raise LiveVerificationValidationError(
            "operator executed execution boundary mode must be canonical",
        )


def _has_unsupported_boundary_mode(
    boundary_input: LiveOrderRealOperatorExecutedExecutionBoundaryInput,
) -> bool:
    return (
        boundary_input.boundary_mode
        != OperatorExecutedExecutionBoundaryMode
        .OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY
        .value
    )


def _safe_boundary_mode(raw_mode: str) -> str:
    if (
        raw_mode
        == OperatorExecutedExecutionBoundaryMode
        .OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY
        .value
    ):
        return raw_mode
    return UNSUPPORTED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_MODE_LABEL


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{name} must be non-empty string")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
