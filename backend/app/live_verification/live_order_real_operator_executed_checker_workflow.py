"""Step 6G operator-executed checker workflow skeleton, no Codex env access.

This module accepts only safe boolean/category metadata for a credential
presence check performed by the operator outside Codex. It does not read env,
run a checker, store credential values or metadata, generate signatures or
header values, call APIs, or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

OPERATOR_CHECKER_WORKFLOW_RECOMMENDED_NEXT_STEP = (
    "future_real_checker_implementation_must_be_a_separate_step_no_codex_env"
)
UNSUPPORTED_OPERATOR_CHECKER_WORKFLOW_MODE_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealOperatorExecutedCheckerWorkflowStatus(str, Enum):
    OPERATOR_CHECKER_WORKFLOW_READY_NO_CODEX_ENV_NO_API_NO_POST = (
        "OPERATOR_CHECKER_WORKFLOW_READY_NO_CODEX_ENV_NO_API_NO_POST"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_INPUT = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_INPUT"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_CODEX_EXECUTION = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_CODEX_EXECUTION"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_CODEX_ENV_ACCESS = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_CODEX_ENV_ACCESS"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_OPERATOR_RESULT = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_OPERATOR_RESULT"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_STALE_OR_REUSED_RESULT = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_STALE_OR_REUSED_RESULT"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_UNKNOWN_FAILED_UNAVAILABLE = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_UNKNOWN_FAILED_UNAVAILABLE"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_RESULT_EXPOSURE = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_RESULT_EXPOSURE"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_CREDENTIAL_EXPOSURE = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_CREDENTIAL_EXPOSURE"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_ENV_NAME_EXPOSURE = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_ENV_NAME_EXPOSURE"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_REAL_SIGNING_OR_POST = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_REAL_SIGNING_OR_POST"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_DISPLAY_OR_SAVE = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_DISPLAY_OR_SAVE"
    )
    BLOCKED_OPERATOR_CHECKER_WORKFLOW_UNSUPPORTED = (
        "BLOCKED_OPERATOR_CHECKER_WORKFLOW_UNSUPPORTED"
    )


class LiveOrderRealOperatorExecutedCheckerWorkflowMode(str, Enum):
    OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY = (
        "OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY"
    )


OperatorExecutedCheckerWorkflowStatus = (
    LiveOrderRealOperatorExecutedCheckerWorkflowStatus
)
OperatorExecutedCheckerWorkflowMode = LiveOrderRealOperatorExecutedCheckerWorkflowMode


@dataclass(frozen=True)
class LiveOrderRealOperatorExecutedCheckerWorkflowInput:
    workflow_mode: str = (
        OperatorExecutedCheckerWorkflowMode
        .OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY
        .value
    )
    credential_presence_checker_contract_ready: bool = True
    credential_presence_adapter_ready: bool = True
    credential_presence_check_ready: bool = True
    operator_workflow_declared: bool = True
    operator_execution_required: bool = True
    operator_execution_performed_outside_codex: bool = True
    codex_execution_performed: bool = False
    codex_env_access_requested: bool = False
    actual_environment_presence_check_performed_by_codex: bool = False
    operator_result_provided: bool = True
    operator_result_is_boolean_only: bool = True
    operator_result_fresh: bool = True
    operator_result_stale: bool = False
    operator_result_reused: bool = False
    operator_result_previous_turn: bool = False
    operator_result_unknown: bool = False
    operator_result_failed: bool = False
    operator_result_unavailable: bool = False
    operator_result_saved: bool = False
    operator_result_displayed: bool = False
    operator_result_broadly_propagated: bool = False
    operator_result_detail_present: bool = False
    credential_values_present: bool = False
    credential_metadata_present: bool = False
    env_variable_names_present: bool = False
    sentinel_value_present: bool = False
    checker_result_detail_present: bool = False
    can_generate_real_signature: bool = False
    can_generate_real_headers: bool = False
    can_execute_http_post: bool = False
    safe_to_render: bool = True
    safe_to_serialize: bool = True
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    retry_allowed: bool = False
    loop_allowed: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("workflow_mode", self.workflow_mode)
        _validate_bool_fields(
            self,
            (
                "credential_presence_checker_contract_ready",
                "credential_presence_adapter_ready",
                "credential_presence_check_ready",
                "operator_workflow_declared",
                "operator_execution_required",
                "operator_execution_performed_outside_codex",
                "codex_execution_performed",
                "codex_env_access_requested",
                "actual_environment_presence_check_performed_by_codex",
                "operator_result_provided",
                "operator_result_is_boolean_only",
                "operator_result_fresh",
                "operator_result_stale",
                "operator_result_reused",
                "operator_result_previous_turn",
                "operator_result_unknown",
                "operator_result_failed",
                "operator_result_unavailable",
                "operator_result_saved",
                "operator_result_displayed",
                "operator_result_broadly_propagated",
                "operator_result_detail_present",
                "credential_values_present",
                "credential_metadata_present",
                "env_variable_names_present",
                "sentinel_value_present",
                "checker_result_detail_present",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "can_execute_http_post",
                "safe_to_render",
                "safe_to_serialize",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "retry_allowed",
                "loop_allowed",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealOperatorExecutedCheckerWorkflowCheckResult:
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
class LiveOrderRealOperatorExecutedCheckerWorkflowResult:
    status: LiveOrderRealOperatorExecutedCheckerWorkflowStatus
    operator_checker_workflow_ready: bool
    workflow_mode: str
    unsupported_workflow_mode_present: bool
    raw_workflow_mode_displayed: bool
    raw_workflow_mode_saved: bool
    credential_presence_checker_contract_ready: bool
    credential_presence_adapter_ready: bool
    credential_presence_check_ready: bool
    operator_workflow_declared: bool
    operator_execution_required: bool
    operator_execution_performed_outside_codex: bool
    codex_execution_performed: bool
    codex_env_access_requested: bool
    actual_environment_presence_check_performed_by_codex: bool
    operator_result_provided: bool
    operator_result_is_boolean_only: bool
    operator_result_fresh: bool
    operator_result_stale: bool
    operator_result_reused: bool
    operator_result_previous_turn: bool
    operator_result_unknown: bool
    operator_result_failed: bool
    operator_result_unavailable: bool
    operator_result_saved: bool
    operator_result_displayed: bool
    operator_result_broadly_propagated: bool
    operator_result_detail_present: bool
    credential_values_present: bool
    credential_metadata_present: bool
    env_variable_names_present: bool
    sentinel_value_present: bool
    checker_result_detail_present: bool
    can_generate_real_signature: bool
    can_generate_real_headers: bool
    can_execute_http_post: bool
    safe_to_render: bool
    safe_to_serialize: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_executed: bool
    retry_allowed: bool
    loop_allowed: bool
    check_results: tuple[LiveOrderRealOperatorExecutedCheckerWorkflowCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealOperatorExecutedCheckerWorkflowStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be operator checker workflow status",
            )
        _require_non_empty("workflow_mode", self.workflow_mode)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "operator_checker_workflow_ready",
                "unsupported_workflow_mode_present",
                "raw_workflow_mode_displayed",
                "raw_workflow_mode_saved",
                "credential_presence_checker_contract_ready",
                "credential_presence_adapter_ready",
                "credential_presence_check_ready",
                "operator_workflow_declared",
                "operator_execution_required",
                "operator_execution_performed_outside_codex",
                "codex_execution_performed",
                "codex_env_access_requested",
                "actual_environment_presence_check_performed_by_codex",
                "operator_result_provided",
                "operator_result_is_boolean_only",
                "operator_result_fresh",
                "operator_result_stale",
                "operator_result_reused",
                "operator_result_previous_turn",
                "operator_result_unknown",
                "operator_result_failed",
                "operator_result_unavailable",
                "operator_result_saved",
                "operator_result_displayed",
                "operator_result_broadly_propagated",
                "operator_result_detail_present",
                "credential_values_present",
                "credential_metadata_present",
                "env_variable_names_present",
                "sentinel_value_present",
                "checker_result_detail_present",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "can_execute_http_post",
                "safe_to_render",
                "safe_to_serialize",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "retry_allowed",
                "loop_allowed",
            ),
        )
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_operator_executed_checker_workflow(
    *,
    input_snapshot: LiveOrderRealOperatorExecutedCheckerWorkflowInput | None = None,
) -> LiveOrderRealOperatorExecutedCheckerWorkflowResult:
    """Build operator-executed checker workflow metadata only."""
    workflow_input = input_snapshot or LiveOrderRealOperatorExecutedCheckerWorkflowInput()
    safe_workflow_mode = _safe_workflow_mode(workflow_input.workflow_mode)
    unsupported_workflow_mode_present = _has_unsupported_workflow_mode(workflow_input)

    input_reasons = _input_reasons(workflow_input)
    codex_execution_reasons = _codex_execution_reasons(workflow_input)
    codex_env_reasons = _codex_env_reasons(workflow_input)
    operator_result_reasons = _operator_result_reasons(workflow_input)
    stale_reasons = _stale_or_reused_reasons(workflow_input)
    unknown_reasons = _unknown_failed_unavailable_reasons(workflow_input)
    result_exposure_reasons = _result_exposure_reasons(workflow_input)
    credential_exposure_reasons = _credential_exposure_reasons(workflow_input)
    env_name_reasons = _env_name_reasons(workflow_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(workflow_input)
    display_reasons = _display_or_save_reasons(workflow_input)
    unsupported_reasons = _unsupported_reasons(workflow_input)

    if input_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_INPUT
        )
        primary_reasons = input_reasons
    elif codex_execution_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_CODEX_EXECUTION
        )
        primary_reasons = codex_execution_reasons
    elif codex_env_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_CODEX_ENV_ACCESS
        )
        primary_reasons = codex_env_reasons
    elif operator_result_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_OPERATOR_RESULT
        )
        primary_reasons = operator_result_reasons
    elif stale_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_STALE_OR_REUSED_RESULT
        )
        primary_reasons = stale_reasons
    elif unknown_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_UNKNOWN_FAILED_UNAVAILABLE
        )
        primary_reasons = unknown_reasons
    elif result_exposure_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_RESULT_EXPOSURE
        )
        primary_reasons = result_exposure_reasons
    elif credential_exposure_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_CREDENTIAL_EXPOSURE
        )
        primary_reasons = credential_exposure_reasons
    elif env_name_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_ENV_NAME_EXPOSURE
        )
        primary_reasons = env_name_reasons
    elif real_signing_or_post_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_REAL_SIGNING_OR_POST
        )
        primary_reasons = real_signing_or_post_reasons
    elif display_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_DISPLAY_OR_SAVE
        )
        primary_reasons = display_reasons
    elif unsupported_reasons:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .BLOCKED_OPERATOR_CHECKER_WORKFLOW_UNSUPPORTED
        )
        primary_reasons = unsupported_reasons
    else:
        status = (
            OperatorExecutedCheckerWorkflowStatus
            .OPERATOR_CHECKER_WORKFLOW_READY_NO_CODEX_ENV_NO_API_NO_POST
        )
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        input_reasons,
        codex_execution_reasons,
        codex_env_reasons,
        operator_result_reasons,
        stale_reasons,
        unknown_reasons,
        result_exposure_reasons,
        credential_exposure_reasons,
        env_name_reasons,
        real_signing_or_post_reasons,
        display_reasons,
        unsupported_reasons,
    )
    ready = (
        status
        is OperatorExecutedCheckerWorkflowStatus
        .OPERATOR_CHECKER_WORKFLOW_READY_NO_CODEX_ENV_NO_API_NO_POST
    )
    return LiveOrderRealOperatorExecutedCheckerWorkflowResult(
        status=status,
        operator_checker_workflow_ready=ready,
        workflow_mode=safe_workflow_mode,
        unsupported_workflow_mode_present=unsupported_workflow_mode_present,
        raw_workflow_mode_displayed=False,
        raw_workflow_mode_saved=False,
        credential_presence_checker_contract_ready=(
            workflow_input.credential_presence_checker_contract_ready
        ),
        credential_presence_adapter_ready=(
            workflow_input.credential_presence_adapter_ready
        ),
        credential_presence_check_ready=workflow_input.credential_presence_check_ready,
        operator_workflow_declared=workflow_input.operator_workflow_declared,
        operator_execution_required=workflow_input.operator_execution_required,
        operator_execution_performed_outside_codex=(
            workflow_input.operator_execution_performed_outside_codex
        ),
        codex_execution_performed=False,
        codex_env_access_requested=False,
        actual_environment_presence_check_performed_by_codex=False,
        operator_result_provided=workflow_input.operator_result_provided,
        operator_result_is_boolean_only=(
            workflow_input.operator_result_is_boolean_only
        ),
        operator_result_fresh=workflow_input.operator_result_fresh,
        operator_result_stale=False,
        operator_result_reused=False,
        operator_result_previous_turn=False,
        operator_result_unknown=False,
        operator_result_failed=False,
        operator_result_unavailable=False,
        operator_result_saved=False,
        operator_result_displayed=False,
        operator_result_broadly_propagated=False,
        operator_result_detail_present=False,
        credential_values_present=False,
        credential_metadata_present=False,
        env_variable_names_present=False,
        sentinel_value_present=False,
        checker_result_detail_present=False,
        can_generate_real_signature=False,
        can_generate_real_headers=False,
        can_execute_http_post=False,
        safe_to_render=True,
        safe_to_serialize=True,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_executed=False,
        retry_allowed=False,
        loop_allowed=False,
        check_results=_build_check_results(workflow_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            OPERATOR_CHECKER_WORKFLOW_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_operator_checker_workflow_blockers_no_codex_env_no_post"
        ),
    )


def render_live_order_real_operator_executed_checker_workflow_markdown(
    result: LiveOrderRealOperatorExecutedCheckerWorkflowResult,
) -> str:
    """Render sanitized operator checker workflow metadata only."""
    lines = [
        "# Step 6G Operator-Executed Checker Workflow",
        "",
        "This operator checker workflow is skeleton-only.",
        "This workflow expects operator-side checking outside Codex.",
        "This workflow does not access env or .env.",
        "This workflow does not check the real environment inside Codex.",
        "This workflow does not expose operator result detail.",
        "This workflow does not expose credential metadata.",
        "This workflow does not generate real signatures.",
        "This workflow does not execute API calls.",
        "This workflow does not execute HTTP POST.",
        "This workflow does not call order endpoint.",
        "This workflow does not call live_order_once.",
        "Future real checker execution must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- operator_checker_workflow_ready: "
            f"{_bool_text(result.operator_checker_workflow_ready)}"
        ),
        f"- workflow_mode: {result.workflow_mode}",
        (
            "- unsupported_workflow_mode_present: "
            f"{_bool_text(result.unsupported_workflow_mode_present)}"
        ),
        (
            "- raw_workflow_mode_displayed: "
            f"{_bool_text(result.raw_workflow_mode_displayed)}"
        ),
        (
            "- raw_workflow_mode_saved: "
            f"{_bool_text(result.raw_workflow_mode_saved)}"
        ),
        (
            "- credential_presence_checker_contract_ready: "
            f"{_bool_text(result.credential_presence_checker_contract_ready)}"
        ),
        "",
        "## Workflow Safety",
        (
            "- operator_workflow_declared: "
            f"{_bool_text(result.operator_workflow_declared)}"
        ),
        (
            "- operator_execution_required: "
            f"{_bool_text(result.operator_execution_required)}"
        ),
        (
            "- operator_execution_performed_outside_codex: "
            f"{_bool_text(result.operator_execution_performed_outside_codex)}"
        ),
        f"- codex_execution_performed: {_bool_text(result.codex_execution_performed)}",
        f"- codex_env_access_requested: {_bool_text(result.codex_env_access_requested)}",
        (
            "- actual_environment_presence_check_performed_by_codex: "
            f"{_bool_text(result.actual_environment_presence_check_performed_by_codex)}"
        ),
        f"- operator_result_provided: {_bool_text(result.operator_result_provided)}",
        (
            "- operator_result_is_boolean_only: "
            f"{_bool_text(result.operator_result_is_boolean_only)}"
        ),
        f"- operator_result_fresh: {_bool_text(result.operator_result_fresh)}",
        f"- operator_result_unknown: {_bool_text(result.operator_result_unknown)}",
        f"- operator_result_failed: {_bool_text(result.operator_result_failed)}",
        (
            "- operator_result_unavailable: "
            f"{_bool_text(result.operator_result_unavailable)}"
        ),
        f"- operator_result_saved: {_bool_text(result.operator_result_saved)}",
        f"- operator_result_displayed: {_bool_text(result.operator_result_displayed)}",
        (
            "- operator_result_detail_present: "
            f"{_bool_text(result.operator_result_detail_present)}"
        ),
        f"- credential_values_present: {_bool_text(result.credential_values_present)}",
        (
            "- credential_metadata_present: "
            f"{_bool_text(result.credential_metadata_present)}"
        ),
        f"- env_variable_names_present: {_bool_text(result.env_variable_names_present)}",
        f"- sentinel_value_present: {_bool_text(result.sentinel_value_present)}",
        (
            "- checker_result_detail_present: "
            f"{_bool_text(result.checker_result_detail_present)}"
        ),
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
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[LiveOrderRealOperatorExecutedCheckerWorkflowCheckResult, ...]:
    groups = (
        (
            "operator checker workflow input",
            _input_reasons(workflow_input),
            "workflow skeleton mode and prerequisite contracts ready",
        ),
        (
            "no Codex checker execution",
            _codex_execution_reasons(workflow_input),
            "operator execution occurs outside Codex",
        ),
        (
            "no Codex env access",
            _codex_env_reasons(workflow_input),
            "Codex does not access env or .env",
        ),
        (
            "operator result contract",
            _operator_result_reasons(workflow_input),
            "operator result is provided as boolean/category only",
        ),
        (
            "fresh non-reused operator result",
            _stale_or_reused_reasons(workflow_input),
            "operator result is fresh and not reused",
        ),
        (
            "known successful operator result",
            _unknown_failed_unavailable_reasons(workflow_input),
            "operator result is not unknown failed or unavailable",
        ),
        (
            "no operator result detail exposure",
            _result_exposure_reasons(workflow_input),
            "operator result detail is not stored displayed or propagated",
        ),
        (
            "no credential or env name exposure",
            _merge_reasons(
                _credential_exposure_reasons(workflow_input),
                _env_name_reasons(workflow_input),
            ),
            "no credential values metadata or env names",
        ),
        (
            "no real signing or post",
            _real_signing_or_post_reasons(workflow_input),
            "no real signing headers API post endpoint or live_order_once",
        ),
    )
    return tuple(
        LiveOrderRealOperatorExecutedCheckerWorkflowCheckResult(
            name=name,
            passed=not reasons,
            sanitized_value="ready" if not reasons else ",".join(reasons),
            expected=expected,
        )
        for name, reasons, expected in groups
    )


def _input_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_unsupported_workflow_mode(workflow_input):
        reasons.append("workflow_mode_unsupported")
    for field_name in (
        "credential_presence_checker_contract_ready",
        "credential_presence_adapter_ready",
        "credential_presence_check_ready",
        "operator_workflow_declared",
        "operator_execution_required",
        "operator_execution_performed_outside_codex",
    ):
        if not getattr(workflow_input, field_name):
            reasons.append(f"{field_name}_false")
    return tuple(reasons)


def _codex_execution_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "codex_execution_performed",
        "actual_environment_presence_check_performed_by_codex",
    ):
        if getattr(workflow_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _codex_env_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[str, ...]:
    if workflow_input.codex_env_access_requested:
        return ("codex_env_access_requested_unsafe",)
    return ()


def _operator_result_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("operator_result_provided", "operator_result_is_boolean_only"):
        if not getattr(workflow_input, field_name):
            reasons.append(f"{field_name}_false")
    return tuple(reasons)


def _stale_or_reused_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not workflow_input.operator_result_fresh:
        reasons.append("operator_result_fresh_false")
    for field_name in (
        "operator_result_stale",
        "operator_result_reused",
        "operator_result_previous_turn",
    ):
        if getattr(workflow_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _unknown_failed_unavailable_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "operator_result_unknown",
        "operator_result_failed",
        "operator_result_unavailable",
    ):
        if getattr(workflow_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _result_exposure_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "operator_result_saved",
        "operator_result_displayed",
        "operator_result_broadly_propagated",
        "operator_result_detail_present",
        "sentinel_value_present",
        "checker_result_detail_present",
    ):
        if getattr(workflow_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_exposure_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("credential_values_present", "credential_metadata_present"):
        if getattr(workflow_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _env_name_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[str, ...]:
    if workflow_input.env_variable_names_present:
        return ("env_variable_names_present_unsafe",)
    return ()


def _real_signing_or_post_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
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
        if getattr(workflow_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _display_or_save_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not workflow_input.safe_to_render:
        reasons.append("safe_to_render_false")
    if not workflow_input.safe_to_serialize:
        reasons.append("safe_to_serialize_false")
    return tuple(reasons)


def _unsupported_reasons(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if workflow_input.retry_allowed:
        reasons.append("retry_allowed_unsupported")
    if workflow_input.loop_allowed:
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
    result: LiveOrderRealOperatorExecutedCheckerWorkflowResult,
) -> None:
    unsafe_flags = (
        result.raw_workflow_mode_displayed,
        result.raw_workflow_mode_saved,
        result.codex_execution_performed,
        result.codex_env_access_requested,
        result.actual_environment_presence_check_performed_by_codex,
        result.operator_result_stale,
        result.operator_result_reused,
        result.operator_result_previous_turn,
        result.operator_result_unknown,
        result.operator_result_failed,
        result.operator_result_unavailable,
        result.operator_result_saved,
        result.operator_result_displayed,
        result.operator_result_broadly_propagated,
        result.operator_result_detail_present,
        result.credential_values_present,
        result.credential_metadata_present,
        result.env_variable_names_present,
        result.sentinel_value_present,
        result.checker_result_detail_present,
        result.can_generate_real_signature,
        result.can_generate_real_headers,
        result.can_execute_http_post,
        not result.safe_to_render,
        not result.safe_to_serialize,
        result.http_post_executed,
        result.order_endpoint_called,
        result.live_order_once_called,
        result.post_allowed_this_step,
        result.post_executed,
        result.retry_allowed,
        result.loop_allowed,
    )
    if any(unsafe_flags):
        raise LiveVerificationValidationError(
            "operator checker workflow result is unsafe",
        )
    if result.unsupported_workflow_mode_present:
        if result.workflow_mode != UNSUPPORTED_OPERATOR_CHECKER_WORKFLOW_MODE_LABEL:
            raise LiveVerificationValidationError(
                "unsupported operator checker workflow mode must use safe label",
            )
    elif (
        result.workflow_mode
        != OperatorExecutedCheckerWorkflowMode
        .OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY
        .value
    ):
        raise LiveVerificationValidationError(
            "operator checker workflow mode must be canonical",
        )


def _has_unsupported_workflow_mode(
    workflow_input: LiveOrderRealOperatorExecutedCheckerWorkflowInput,
) -> bool:
    return (
        workflow_input.workflow_mode
        != OperatorExecutedCheckerWorkflowMode
        .OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY
        .value
    )


def _safe_workflow_mode(raw_workflow_mode: str) -> str:
    if (
        raw_workflow_mode
        == OperatorExecutedCheckerWorkflowMode
        .OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY
        .value
    ):
        return (
            OperatorExecutedCheckerWorkflowMode
            .OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY
            .value
        )
    return UNSUPPORTED_OPERATOR_CHECKER_WORKFLOW_MODE_LABEL


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
