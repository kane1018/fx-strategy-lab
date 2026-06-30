"""Step 6G credential presence checker execution contract skeleton.

This module declares only the future checker execution contract inputs,
outputs, and stop conditions. It does not read env, execute a checker, inspect
credential values or metadata, generate signatures or header values, call APIs,
or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_RECOMMENDED_NEXT_STEP = (
    "future_checker_execution_must_be_a_separate_step_no_env_no_check_no_post"
)
UNSUPPORTED_CHECKER_EXECUTION_CONTRACT_MODE_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealCredentialPresenceCheckerExecutionContractStatus(str, Enum):
    CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_READY_NO_ENV_NO_CHECK = (
        "CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_READY_NO_ENV_NO_CHECK"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_INPUT = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_INPUT"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_EXECUTION = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_EXECUTION"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_CODEX_ENV_ACCESS = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_CODEX_ENV_ACCESS"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_CREDENTIAL_READ = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_CREDENTIAL_READ"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_RESULT_EXPOSURE = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_RESULT_EXPOSURE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_REAL_SIGNING_OR_POST = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_REAL_SIGNING_OR_POST"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_OPERATOR_WORKFLOW = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_OPERATOR_WORKFLOW"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_DISPLAY_OR_SAVE = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_DISPLAY_OR_SAVE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_UNSUPPORTED = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_UNSUPPORTED"
    )


class LiveOrderRealCredentialPresenceCheckerExecutionContractMode(str, Enum):
    CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY = (
        "CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY"
    )


CredentialPresenceCheckerExecutionContractStatus = (
    LiveOrderRealCredentialPresenceCheckerExecutionContractStatus
)
CredentialPresenceCheckerExecutionContractMode = (
    LiveOrderRealCredentialPresenceCheckerExecutionContractMode
)


@dataclass(frozen=True)
class LiveOrderRealCredentialPresenceCheckerExecutionContractInput:
    execution_contract_mode: str = (
        CredentialPresenceCheckerExecutionContractMode
        .CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY
        .value
    )
    checker_implementation_skeleton_ready: bool = True
    operator_checker_workflow_ready: bool = True
    checker_contract_ready: bool = True
    execution_contract_declared: bool = True
    execution_inputs_declared: bool = True
    execution_outputs_declared: bool = True
    execution_stop_conditions_declared: bool = True
    execution_deferred_to_future_step: bool = True
    execution_performed: bool = False
    execution_performed_by_codex: bool = False
    execution_performed_by_operator: bool = False
    codex_env_access_requested: bool = False
    actual_environment_presence_check_performed: bool = False
    credential_read_performed: bool = False
    credential_values_present: bool = False
    credential_metadata_present: bool = False
    checker_result_available: bool = False
    checker_result_is_boolean_only: bool = True
    checker_result_detail_present: bool = False
    checker_result_unknown: bool = False
    checker_result_failed: bool = False
    checker_result_unavailable: bool = False
    checker_result_stale: bool = False
    checker_result_timeout: bool = False
    checker_result_saved: bool = False
    checker_result_displayed: bool = False
    checker_result_broadly_propagated: bool = False
    operator_workflow_preserved: bool = True
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
        _require_non_empty("execution_contract_mode", self.execution_contract_mode)
        _validate_bool_fields(
            self,
            (
                "checker_implementation_skeleton_ready",
                "operator_checker_workflow_ready",
                "checker_contract_ready",
                "execution_contract_declared",
                "execution_inputs_declared",
                "execution_outputs_declared",
                "execution_stop_conditions_declared",
                "execution_deferred_to_future_step",
                "execution_performed",
                "execution_performed_by_codex",
                "execution_performed_by_operator",
                "codex_env_access_requested",
                "actual_environment_presence_check_performed",
                "credential_read_performed",
                "credential_values_present",
                "credential_metadata_present",
                "checker_result_available",
                "checker_result_is_boolean_only",
                "checker_result_detail_present",
                "checker_result_unknown",
                "checker_result_failed",
                "checker_result_unavailable",
                "checker_result_stale",
                "checker_result_timeout",
                "checker_result_saved",
                "checker_result_displayed",
                "checker_result_broadly_propagated",
                "operator_workflow_preserved",
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
class LiveOrderRealCredentialPresenceCheckerExecutionContractCheckResult:
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
class LiveOrderRealCredentialPresenceCheckerExecutionContractResult:
    status: LiveOrderRealCredentialPresenceCheckerExecutionContractStatus
    checker_execution_contract_ready: bool
    execution_contract_mode: str
    unsupported_execution_contract_mode_present: bool
    raw_execution_contract_mode_displayed: bool
    raw_execution_contract_mode_saved: bool
    checker_implementation_skeleton_ready: bool
    operator_checker_workflow_ready: bool
    checker_contract_ready: bool
    execution_contract_declared: bool
    execution_inputs_declared: bool
    execution_outputs_declared: bool
    execution_stop_conditions_declared: bool
    execution_deferred_to_future_step: bool
    execution_performed: bool
    execution_performed_by_codex: bool
    execution_performed_by_operator: bool
    codex_env_access_requested: bool
    actual_environment_presence_check_performed: bool
    credential_read_performed: bool
    credential_values_present: bool
    credential_metadata_present: bool
    checker_result_available: bool
    checker_result_is_boolean_only: bool
    checker_result_detail_present: bool
    checker_result_unknown: bool
    checker_result_failed: bool
    checker_result_unavailable: bool
    checker_result_stale: bool
    checker_result_timeout: bool
    checker_result_saved: bool
    checker_result_displayed: bool
    checker_result_broadly_propagated: bool
    operator_workflow_preserved: bool
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
    check_results: tuple[
        LiveOrderRealCredentialPresenceCheckerExecutionContractCheckResult,
        ...,
    ]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealCredentialPresenceCheckerExecutionContractStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be checker execution contract status",
            )
        _require_non_empty("execution_contract_mode", self.execution_contract_mode)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "checker_execution_contract_ready",
                "unsupported_execution_contract_mode_present",
                "raw_execution_contract_mode_displayed",
                "raw_execution_contract_mode_saved",
                "checker_implementation_skeleton_ready",
                "operator_checker_workflow_ready",
                "checker_contract_ready",
                "execution_contract_declared",
                "execution_inputs_declared",
                "execution_outputs_declared",
                "execution_stop_conditions_declared",
                "execution_deferred_to_future_step",
                "execution_performed",
                "execution_performed_by_codex",
                "execution_performed_by_operator",
                "codex_env_access_requested",
                "actual_environment_presence_check_performed",
                "credential_read_performed",
                "credential_values_present",
                "credential_metadata_present",
                "checker_result_available",
                "checker_result_is_boolean_only",
                "checker_result_detail_present",
                "checker_result_unknown",
                "checker_result_failed",
                "checker_result_unavailable",
                "checker_result_stale",
                "checker_result_timeout",
                "checker_result_saved",
                "checker_result_displayed",
                "checker_result_broadly_propagated",
                "operator_workflow_preserved",
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


def build_live_order_real_credential_presence_checker_execution_contract(
    *,
    input_snapshot: (
        LiveOrderRealCredentialPresenceCheckerExecutionContractInput | None
    ) = None,
) -> LiveOrderRealCredentialPresenceCheckerExecutionContractResult:
    """Build checker execution contract metadata only."""
    contract_input = (
        input_snapshot
        or LiveOrderRealCredentialPresenceCheckerExecutionContractInput()
    )
    safe_contract_mode = _safe_execution_contract_mode(
        contract_input.execution_contract_mode,
    )
    unsupported_contract_mode_present = _has_unsupported_execution_contract_mode(
        contract_input,
    )

    input_reasons = _input_reasons(contract_input)
    execution_reasons = _execution_reasons(contract_input)
    env_reasons = _env_reasons(contract_input)
    credential_read_reasons = _credential_read_reasons(contract_input)
    result_exposure_reasons = _result_exposure_reasons(contract_input)
    unknown_reasons = _unknown_failed_unavailable_timeout_reasons(contract_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(contract_input)
    operator_workflow_reasons = _operator_workflow_reasons(contract_input)
    display_reasons = _display_or_save_reasons(contract_input)
    unsupported_reasons = _unsupported_reasons(contract_input)

    if input_reasons:
        status = (
            CredentialPresenceCheckerExecutionContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_INPUT
        )
        primary_reasons = input_reasons
    elif execution_reasons:
        status = (
            CredentialPresenceCheckerExecutionContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_EXECUTION
        )
        primary_reasons = execution_reasons
    elif env_reasons:
        status = (
            CredentialPresenceCheckerExecutionContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_CODEX_ENV_ACCESS
        )
        primary_reasons = env_reasons
    elif credential_read_reasons:
        status = (
            CredentialPresenceCheckerExecutionContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_CREDENTIAL_READ
        )
        primary_reasons = credential_read_reasons
    elif result_exposure_reasons:
        status = (
            CredentialPresenceCheckerExecutionContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_RESULT_EXPOSURE
        )
        primary_reasons = result_exposure_reasons
    elif unknown_reasons:
        status = (
            CredentialPresenceCheckerExecutionContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT
        )
        primary_reasons = unknown_reasons
    elif real_signing_or_post_reasons:
        status = (
            CredentialPresenceCheckerExecutionContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_REAL_SIGNING_OR_POST
        )
        primary_reasons = real_signing_or_post_reasons
    elif operator_workflow_reasons:
        status = (
            CredentialPresenceCheckerExecutionContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_OPERATOR_WORKFLOW
        )
        primary_reasons = operator_workflow_reasons
    elif display_reasons:
        status = (
            CredentialPresenceCheckerExecutionContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_DISPLAY_OR_SAVE
        )
        primary_reasons = display_reasons
    elif unsupported_reasons:
        status = (
            CredentialPresenceCheckerExecutionContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_UNSUPPORTED
        )
        primary_reasons = unsupported_reasons
    else:
        status = (
            CredentialPresenceCheckerExecutionContractStatus
            .CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_READY_NO_ENV_NO_CHECK
        )
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        input_reasons,
        execution_reasons,
        env_reasons,
        credential_read_reasons,
        result_exposure_reasons,
        unknown_reasons,
        real_signing_or_post_reasons,
        operator_workflow_reasons,
        display_reasons,
        unsupported_reasons,
    )
    ready = (
        status
        is CredentialPresenceCheckerExecutionContractStatus
        .CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_READY_NO_ENV_NO_CHECK
    )
    return LiveOrderRealCredentialPresenceCheckerExecutionContractResult(
        status=status,
        checker_execution_contract_ready=ready,
        execution_contract_mode=safe_contract_mode,
        unsupported_execution_contract_mode_present=(
            unsupported_contract_mode_present
        ),
        raw_execution_contract_mode_displayed=False,
        raw_execution_contract_mode_saved=False,
        checker_implementation_skeleton_ready=(
            contract_input.checker_implementation_skeleton_ready
        ),
        operator_checker_workflow_ready=contract_input.operator_checker_workflow_ready,
        checker_contract_ready=contract_input.checker_contract_ready,
        execution_contract_declared=contract_input.execution_contract_declared,
        execution_inputs_declared=contract_input.execution_inputs_declared,
        execution_outputs_declared=contract_input.execution_outputs_declared,
        execution_stop_conditions_declared=(
            contract_input.execution_stop_conditions_declared
        ),
        execution_deferred_to_future_step=(
            contract_input.execution_deferred_to_future_step
        ),
        execution_performed=False,
        execution_performed_by_codex=False,
        execution_performed_by_operator=False,
        codex_env_access_requested=False,
        actual_environment_presence_check_performed=False,
        credential_read_performed=False,
        credential_values_present=False,
        credential_metadata_present=False,
        checker_result_available=False,
        checker_result_is_boolean_only=contract_input.checker_result_is_boolean_only,
        checker_result_detail_present=False,
        checker_result_unknown=False,
        checker_result_failed=False,
        checker_result_unavailable=False,
        checker_result_stale=False,
        checker_result_timeout=False,
        checker_result_saved=False,
        checker_result_displayed=False,
        checker_result_broadly_propagated=False,
        operator_workflow_preserved=contract_input.operator_workflow_preserved,
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
        check_results=_build_check_results(contract_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_checker_execution_contract_blockers_no_env_no_check_no_post"
        ),
    )


def render_live_order_real_credential_presence_checker_execution_contract_markdown(
    result: LiveOrderRealCredentialPresenceCheckerExecutionContractResult,
) -> str:
    """Render sanitized checker execution contract metadata only."""
    lines = [
        "# Step 6G Credential Presence Checker Execution Contract",
        "",
        "This checker execution contract is skeleton-only.",
        "This contract does not execute the checker.",
        "This contract does not access env or .env.",
        "This contract does not read credentials.",
        "This contract does not perform an actual environment presence check.",
        "Unknown / failed / unavailable / stale / timeout results block POST.",
        "This contract does not generate real signatures.",
        "This contract does not execute API calls.",
        "This contract does not execute HTTP POST.",
        "This contract does not call order endpoint.",
        "This contract does not call live_order_once.",
        "Future checker execution must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- checker_execution_contract_ready: "
            f"{_bool_text(result.checker_execution_contract_ready)}"
        ),
        f"- execution_contract_mode: {result.execution_contract_mode}",
        (
            "- unsupported_execution_contract_mode_present: "
            f"{_bool_text(result.unsupported_execution_contract_mode_present)}"
        ),
        (
            "- raw_execution_contract_mode_displayed: "
            f"{_bool_text(result.raw_execution_contract_mode_displayed)}"
        ),
        (
            "- raw_execution_contract_mode_saved: "
            f"{_bool_text(result.raw_execution_contract_mode_saved)}"
        ),
        (
            "- checker_implementation_skeleton_ready: "
            f"{_bool_text(result.checker_implementation_skeleton_ready)}"
        ),
        (
            "- operator_checker_workflow_ready: "
            f"{_bool_text(result.operator_checker_workflow_ready)}"
        ),
        f"- checker_contract_ready: {_bool_text(result.checker_contract_ready)}",
        "",
        "## Execution Contract Safety",
        (
            "- execution_contract_declared: "
            f"{_bool_text(result.execution_contract_declared)}"
        ),
        (
            "- execution_inputs_declared: "
            f"{_bool_text(result.execution_inputs_declared)}"
        ),
        (
            "- execution_outputs_declared: "
            f"{_bool_text(result.execution_outputs_declared)}"
        ),
        (
            "- execution_stop_conditions_declared: "
            f"{_bool_text(result.execution_stop_conditions_declared)}"
        ),
        (
            "- execution_deferred_to_future_step: "
            f"{_bool_text(result.execution_deferred_to_future_step)}"
        ),
        f"- execution_performed: {_bool_text(result.execution_performed)}",
        (
            "- execution_performed_by_codex: "
            f"{_bool_text(result.execution_performed_by_codex)}"
        ),
        (
            "- execution_performed_by_operator: "
            f"{_bool_text(result.execution_performed_by_operator)}"
        ),
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
        f"- checker_result_available: {_bool_text(result.checker_result_available)}",
        (
            "- checker_result_is_boolean_only: "
            f"{_bool_text(result.checker_result_is_boolean_only)}"
        ),
        (
            "- checker_result_detail_present: "
            f"{_bool_text(result.checker_result_detail_present)}"
        ),
        f"- checker_result_unknown: {_bool_text(result.checker_result_unknown)}",
        f"- checker_result_failed: {_bool_text(result.checker_result_failed)}",
        (
            "- checker_result_unavailable: "
            f"{_bool_text(result.checker_result_unavailable)}"
        ),
        f"- checker_result_stale: {_bool_text(result.checker_result_stale)}",
        f"- checker_result_timeout: {_bool_text(result.checker_result_timeout)}",
        (
            "- checker_result_broadly_propagated: "
            f"{_bool_text(result.checker_result_broadly_propagated)}"
        ),
        (
            "- operator_workflow_preserved: "
            f"{_bool_text(result.operator_workflow_preserved)}"
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
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
) -> tuple[LiveOrderRealCredentialPresenceCheckerExecutionContractCheckResult, ...]:
    groups = (
        (
            "checker execution contract input",
            _input_reasons(contract_input),
            "execution contract skeleton mode and prerequisite contracts ready",
        ),
        (
            "execution deferred",
            _execution_reasons(contract_input),
            "checker execution is not performed in this step",
        ),
        (
            "no Codex env access",
            _env_reasons(contract_input),
            "Codex does not request env or .env access",
        ),
        (
            "no credential read",
            _credential_read_reasons(contract_input),
            "no credential read values or metadata",
        ),
        (
            "no checker result exposure",
            _result_exposure_reasons(contract_input),
            "checker result detail is not available stored displayed or propagated",
        ),
        (
            "known non-stale non-timeout checker result state",
            _unknown_failed_unavailable_timeout_reasons(contract_input),
            "checker result is not unknown failed unavailable stale or timeout",
        ),
        (
            "operator workflow preserved",
            _operator_workflow_reasons(contract_input),
            "operator-executed workflow remains preserved",
        ),
        (
            "no real signing or post",
            _real_signing_or_post_reasons(contract_input),
            "no real signing headers API post endpoint or live_order_once",
        ),
    )
    return tuple(
        LiveOrderRealCredentialPresenceCheckerExecutionContractCheckResult(
            name=name,
            passed=not reasons,
            sanitized_value="ready" if not reasons else ",".join(reasons),
            expected=expected,
        )
        for name, reasons, expected in groups
    )


def _input_reasons(
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_unsupported_execution_contract_mode(contract_input):
        reasons.append("execution_contract_mode_unsupported")
    for field_name in (
        "checker_implementation_skeleton_ready",
        "operator_checker_workflow_ready",
        "checker_contract_ready",
        "execution_contract_declared",
        "execution_inputs_declared",
        "execution_outputs_declared",
        "execution_stop_conditions_declared",
    ):
        if not getattr(contract_input, field_name):
            reasons.append(f"{field_name}_false")
    return tuple(reasons)


def _execution_reasons(
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not contract_input.execution_deferred_to_future_step:
        reasons.append("execution_deferred_to_future_step_false")
    for field_name in (
        "execution_performed",
        "execution_performed_by_codex",
        "execution_performed_by_operator",
        "actual_environment_presence_check_performed",
    ):
        if getattr(contract_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _env_reasons(
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if contract_input.codex_env_access_requested:
        reasons.append("codex_env_access_requested_unsafe")
    return tuple(reasons)


def _credential_read_reasons(
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_read_performed",
        "credential_values_present",
        "credential_metadata_present",
    ):
        if getattr(contract_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _result_exposure_reasons(
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if contract_input.checker_result_available:
        reasons.append("checker_result_available_unsafe")
    if not contract_input.checker_result_is_boolean_only:
        reasons.append("checker_result_is_boolean_only_false")
    for field_name in (
        "checker_result_detail_present",
        "checker_result_saved",
        "checker_result_displayed",
        "checker_result_broadly_propagated",
    ):
        if getattr(contract_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _unknown_failed_unavailable_timeout_reasons(
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "checker_result_unknown",
        "checker_result_failed",
        "checker_result_unavailable",
        "checker_result_stale",
        "checker_result_timeout",
    ):
        if getattr(contract_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_signing_or_post_reasons(
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
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
        if getattr(contract_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _operator_workflow_reasons(
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not contract_input.operator_workflow_preserved:
        reasons.append("operator_workflow_preserved_false")
    return tuple(reasons)


def _display_or_save_reasons(
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not contract_input.safe_to_render:
        reasons.append("safe_to_render_false")
    if not contract_input.safe_to_serialize:
        reasons.append("safe_to_serialize_false")
    return tuple(reasons)


def _unsupported_reasons(
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if contract_input.retry_allowed:
        reasons.append("retry_allowed_unsupported")
    if contract_input.loop_allowed:
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
    result: LiveOrderRealCredentialPresenceCheckerExecutionContractResult,
) -> None:
    unsafe_flags = (
        result.raw_execution_contract_mode_displayed,
        result.raw_execution_contract_mode_saved,
        result.execution_performed,
        result.execution_performed_by_codex,
        result.execution_performed_by_operator,
        result.codex_env_access_requested,
        result.actual_environment_presence_check_performed,
        result.credential_read_performed,
        result.credential_values_present,
        result.credential_metadata_present,
        result.checker_result_available,
        result.checker_result_detail_present,
        result.checker_result_unknown,
        result.checker_result_failed,
        result.checker_result_unavailable,
        result.checker_result_stale,
        result.checker_result_timeout,
        result.checker_result_saved,
        result.checker_result_displayed,
        result.checker_result_broadly_propagated,
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
            "checker execution contract result is unsafe",
        )
    if result.unsupported_execution_contract_mode_present:
        if (
            result.execution_contract_mode
            != UNSUPPORTED_CHECKER_EXECUTION_CONTRACT_MODE_LABEL
        ):
            raise LiveVerificationValidationError(
                "unsupported checker execution contract mode must use safe label",
            )
    elif (
        result.execution_contract_mode
        != CredentialPresenceCheckerExecutionContractMode
        .CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY
        .value
    ):
        raise LiveVerificationValidationError(
            "checker execution contract mode must be canonical",
        )


def _has_unsupported_execution_contract_mode(
    contract_input: LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
) -> bool:
    return (
        contract_input.execution_contract_mode
        != CredentialPresenceCheckerExecutionContractMode
        .CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY
        .value
    )


def _safe_execution_contract_mode(raw_execution_contract_mode: str) -> str:
    if (
        raw_execution_contract_mode
        == CredentialPresenceCheckerExecutionContractMode
        .CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY
        .value
    ):
        return (
            CredentialPresenceCheckerExecutionContractMode
            .CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY
            .value
        )
    return UNSUPPORTED_CHECKER_EXECUTION_CONTRACT_MODE_LABEL


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
