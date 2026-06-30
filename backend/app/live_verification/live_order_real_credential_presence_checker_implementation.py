"""Step 6G credential presence checker implementation skeleton.

This module declares only the future checker implementation interface and
lifecycle metadata. It does not read env, execute a checker, inspect credential
values or metadata, generate signatures or header values, call APIs, or execute
HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_RECOMMENDED_NEXT_STEP = (
    "future_checker_execution_must_be_a_separate_step_no_env_no_post"
)
UNSUPPORTED_CHECKER_IMPLEMENTATION_MODE_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealCredentialPresenceCheckerImplementationStatus(str, Enum):
    CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_READY_NO_ENV_NO_CHECK = (
        "CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_READY_NO_ENV_NO_CHECK"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_INPUT = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_INPUT"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_EXECUTION = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_EXECUTION"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_ENV_ACCESS = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_ENV_ACCESS"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_CREDENTIAL_READ = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_CREDENTIAL_READ"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_RESULT_EXPOSURE = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_RESULT_EXPOSURE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_UNKNOWN_FAILED_UNAVAILABLE = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_UNKNOWN_FAILED_UNAVAILABLE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_REAL_SIGNING_OR_POST = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_REAL_SIGNING_OR_POST"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_OPERATOR_WORKFLOW = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_OPERATOR_WORKFLOW"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_DISPLAY_OR_SAVE = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_DISPLAY_OR_SAVE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_UNSUPPORTED = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_UNSUPPORTED"
    )


class LiveOrderRealCredentialPresenceCheckerImplementationMode(str, Enum):
    CHECKER_IMPLEMENTATION_SKELETON_ONLY = "CHECKER_IMPLEMENTATION_SKELETON_ONLY"


CredentialPresenceCheckerImplementationStatus = (
    LiveOrderRealCredentialPresenceCheckerImplementationStatus
)
CredentialPresenceCheckerImplementationMode = (
    LiveOrderRealCredentialPresenceCheckerImplementationMode
)


@dataclass(frozen=True)
class LiveOrderRealCredentialPresenceCheckerImplementationInput:
    implementation_mode: str = (
        CredentialPresenceCheckerImplementationMode
        .CHECKER_IMPLEMENTATION_SKELETON_ONLY
        .value
    )
    checker_contract_ready: bool = True
    operator_checker_workflow_ready: bool = True
    credential_presence_adapter_ready: bool = True
    credential_presence_check_ready: bool = True
    implementation_interface_declared: bool = True
    implementation_lifecycle_declared: bool = True
    execution_deferred_to_future_step: bool = True
    execution_performed: bool = False
    codex_env_access_requested: bool = False
    actual_environment_presence_check_performed: bool = False
    env_access_capability_present: bool = False
    credential_read_capability_present: bool = False
    credential_values_read: bool = False
    credential_values_present: bool = False
    credential_metadata_present: bool = False
    checker_result_available: bool = False
    checker_result_detail_present: bool = False
    checker_result_unknown: bool = False
    checker_result_failed: bool = False
    checker_result_unavailable: bool = False
    checker_result_stale: bool = False
    checker_result_saved: bool = False
    checker_result_displayed: bool = False
    operator_workflow_supported: bool = True
    operator_workflow_preserved: bool = True
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
        _require_non_empty("implementation_mode", self.implementation_mode)
        _validate_bool_fields(
            self,
            (
                "checker_contract_ready",
                "operator_checker_workflow_ready",
                "credential_presence_adapter_ready",
                "credential_presence_check_ready",
                "implementation_interface_declared",
                "implementation_lifecycle_declared",
                "execution_deferred_to_future_step",
                "execution_performed",
                "codex_env_access_requested",
                "actual_environment_presence_check_performed",
                "env_access_capability_present",
                "credential_read_capability_present",
                "credential_values_read",
                "credential_values_present",
                "credential_metadata_present",
                "checker_result_available",
                "checker_result_detail_present",
                "checker_result_unknown",
                "checker_result_failed",
                "checker_result_unavailable",
                "checker_result_stale",
                "checker_result_saved",
                "checker_result_displayed",
                "operator_workflow_supported",
                "operator_workflow_preserved",
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
class LiveOrderRealCredentialPresenceCheckerImplementationCheckResult:
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
class LiveOrderRealCredentialPresenceCheckerImplementationResult:
    status: LiveOrderRealCredentialPresenceCheckerImplementationStatus
    checker_implementation_skeleton_ready: bool
    implementation_mode: str
    unsupported_implementation_mode_present: bool
    raw_implementation_mode_displayed: bool
    raw_implementation_mode_saved: bool
    checker_contract_ready: bool
    operator_checker_workflow_ready: bool
    credential_presence_adapter_ready: bool
    credential_presence_check_ready: bool
    implementation_interface_declared: bool
    implementation_lifecycle_declared: bool
    execution_deferred_to_future_step: bool
    execution_performed: bool
    codex_env_access_requested: bool
    actual_environment_presence_check_performed: bool
    env_access_capability_present: bool
    credential_read_capability_present: bool
    credential_values_read: bool
    credential_values_present: bool
    credential_metadata_present: bool
    checker_result_available: bool
    checker_result_detail_present: bool
    checker_result_unknown: bool
    checker_result_failed: bool
    checker_result_unavailable: bool
    checker_result_stale: bool
    checker_result_saved: bool
    checker_result_displayed: bool
    operator_workflow_supported: bool
    operator_workflow_preserved: bool
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
    check_results: tuple[LiveOrderRealCredentialPresenceCheckerImplementationCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealCredentialPresenceCheckerImplementationStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be checker implementation status",
            )
        _require_non_empty("implementation_mode", self.implementation_mode)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "checker_implementation_skeleton_ready",
                "unsupported_implementation_mode_present",
                "raw_implementation_mode_displayed",
                "raw_implementation_mode_saved",
                "checker_contract_ready",
                "operator_checker_workflow_ready",
                "credential_presence_adapter_ready",
                "credential_presence_check_ready",
                "implementation_interface_declared",
                "implementation_lifecycle_declared",
                "execution_deferred_to_future_step",
                "execution_performed",
                "codex_env_access_requested",
                "actual_environment_presence_check_performed",
                "env_access_capability_present",
                "credential_read_capability_present",
                "credential_values_read",
                "credential_values_present",
                "credential_metadata_present",
                "checker_result_available",
                "checker_result_detail_present",
                "checker_result_unknown",
                "checker_result_failed",
                "checker_result_unavailable",
                "checker_result_stale",
                "checker_result_saved",
                "checker_result_displayed",
                "operator_workflow_supported",
                "operator_workflow_preserved",
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


def build_live_order_real_credential_presence_checker_implementation(
    *,
    input_snapshot: (
        LiveOrderRealCredentialPresenceCheckerImplementationInput | None
    ) = None,
) -> LiveOrderRealCredentialPresenceCheckerImplementationResult:
    """Build checker implementation skeleton metadata only."""
    implementation_input = (
        input_snapshot or LiveOrderRealCredentialPresenceCheckerImplementationInput()
    )
    safe_implementation_mode = _safe_implementation_mode(
        implementation_input.implementation_mode,
    )
    unsupported_implementation_mode_present = _has_unsupported_implementation_mode(
        implementation_input,
    )

    input_reasons = _input_reasons(implementation_input)
    execution_reasons = _execution_reasons(implementation_input)
    env_reasons = _env_reasons(implementation_input)
    credential_read_reasons = _credential_read_reasons(implementation_input)
    result_exposure_reasons = _result_exposure_reasons(implementation_input)
    unknown_reasons = _unknown_failed_unavailable_reasons(implementation_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(implementation_input)
    operator_workflow_reasons = _operator_workflow_reasons(implementation_input)
    display_reasons = _display_or_save_reasons(implementation_input)
    unsupported_reasons = _unsupported_reasons(implementation_input)

    if input_reasons:
        status = (
            CredentialPresenceCheckerImplementationStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_INPUT
        )
        primary_reasons = input_reasons
    elif execution_reasons:
        status = (
            CredentialPresenceCheckerImplementationStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_EXECUTION
        )
        primary_reasons = execution_reasons
    elif env_reasons:
        status = (
            CredentialPresenceCheckerImplementationStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_ENV_ACCESS
        )
        primary_reasons = env_reasons
    elif credential_read_reasons:
        status = (
            CredentialPresenceCheckerImplementationStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_CREDENTIAL_READ
        )
        primary_reasons = credential_read_reasons
    elif result_exposure_reasons:
        status = (
            CredentialPresenceCheckerImplementationStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_RESULT_EXPOSURE
        )
        primary_reasons = result_exposure_reasons
    elif unknown_reasons:
        status = (
            CredentialPresenceCheckerImplementationStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_UNKNOWN_FAILED_UNAVAILABLE
        )
        primary_reasons = unknown_reasons
    elif real_signing_or_post_reasons:
        status = (
            CredentialPresenceCheckerImplementationStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_REAL_SIGNING_OR_POST
        )
        primary_reasons = real_signing_or_post_reasons
    elif operator_workflow_reasons:
        status = (
            CredentialPresenceCheckerImplementationStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_OPERATOR_WORKFLOW
        )
        primary_reasons = operator_workflow_reasons
    elif display_reasons:
        status = (
            CredentialPresenceCheckerImplementationStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_DISPLAY_OR_SAVE
        )
        primary_reasons = display_reasons
    elif unsupported_reasons:
        status = (
            CredentialPresenceCheckerImplementationStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_UNSUPPORTED
        )
        primary_reasons = unsupported_reasons
    else:
        status = (
            CredentialPresenceCheckerImplementationStatus
            .CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_READY_NO_ENV_NO_CHECK
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
        is CredentialPresenceCheckerImplementationStatus
        .CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_READY_NO_ENV_NO_CHECK
    )
    return LiveOrderRealCredentialPresenceCheckerImplementationResult(
        status=status,
        checker_implementation_skeleton_ready=ready,
        implementation_mode=safe_implementation_mode,
        unsupported_implementation_mode_present=(
            unsupported_implementation_mode_present
        ),
        raw_implementation_mode_displayed=False,
        raw_implementation_mode_saved=False,
        checker_contract_ready=implementation_input.checker_contract_ready,
        operator_checker_workflow_ready=(
            implementation_input.operator_checker_workflow_ready
        ),
        credential_presence_adapter_ready=(
            implementation_input.credential_presence_adapter_ready
        ),
        credential_presence_check_ready=(
            implementation_input.credential_presence_check_ready
        ),
        implementation_interface_declared=(
            implementation_input.implementation_interface_declared
        ),
        implementation_lifecycle_declared=(
            implementation_input.implementation_lifecycle_declared
        ),
        execution_deferred_to_future_step=(
            implementation_input.execution_deferred_to_future_step
        ),
        execution_performed=False,
        codex_env_access_requested=False,
        actual_environment_presence_check_performed=False,
        env_access_capability_present=False,
        credential_read_capability_present=False,
        credential_values_read=False,
        credential_values_present=False,
        credential_metadata_present=False,
        checker_result_available=False,
        checker_result_detail_present=False,
        checker_result_unknown=False,
        checker_result_failed=False,
        checker_result_unavailable=False,
        checker_result_stale=False,
        checker_result_saved=False,
        checker_result_displayed=False,
        operator_workflow_supported=implementation_input.operator_workflow_supported,
        operator_workflow_preserved=implementation_input.operator_workflow_preserved,
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
        check_results=_build_check_results(implementation_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_checker_implementation_skeleton_blockers_no_env_no_post"
        ),
    )


def render_live_order_real_credential_presence_checker_implementation_markdown(
    result: LiveOrderRealCredentialPresenceCheckerImplementationResult,
) -> str:
    """Render sanitized checker implementation skeleton metadata only."""
    lines = [
        "# Step 6G Credential Presence Checker Implementation Skeleton",
        "",
        "This checker implementation is skeleton-only.",
        "This checker implementation does not execute the checker.",
        "This checker implementation does not access env or .env.",
        "This checker implementation does not check the real environment.",
        "This checker implementation preserves the operator-executed workflow boundary.",
        "This checker implementation does not expose checker result detail.",
        "This checker implementation does not generate real signatures.",
        "This checker implementation does not execute API calls.",
        "This checker implementation does not execute HTTP POST.",
        "This checker implementation does not call order endpoint.",
        "This checker implementation does not call live_order_once.",
        "Future checker execution must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- checker_implementation_skeleton_ready: "
            f"{_bool_text(result.checker_implementation_skeleton_ready)}"
        ),
        f"- implementation_mode: {result.implementation_mode}",
        (
            "- unsupported_implementation_mode_present: "
            f"{_bool_text(result.unsupported_implementation_mode_present)}"
        ),
        (
            "- raw_implementation_mode_displayed: "
            f"{_bool_text(result.raw_implementation_mode_displayed)}"
        ),
        (
            "- raw_implementation_mode_saved: "
            f"{_bool_text(result.raw_implementation_mode_saved)}"
        ),
        f"- checker_contract_ready: {_bool_text(result.checker_contract_ready)}",
        (
            "- operator_checker_workflow_ready: "
            f"{_bool_text(result.operator_checker_workflow_ready)}"
        ),
        "",
        "## Implementation Safety",
        (
            "- implementation_interface_declared: "
            f"{_bool_text(result.implementation_interface_declared)}"
        ),
        (
            "- implementation_lifecycle_declared: "
            f"{_bool_text(result.implementation_lifecycle_declared)}"
        ),
        (
            "- execution_deferred_to_future_step: "
            f"{_bool_text(result.execution_deferred_to_future_step)}"
        ),
        f"- execution_performed: {_bool_text(result.execution_performed)}",
        (
            "- codex_env_access_requested: "
            f"{_bool_text(result.codex_env_access_requested)}"
        ),
        (
            "- actual_environment_presence_check_performed: "
            f"{_bool_text(result.actual_environment_presence_check_performed)}"
        ),
        (
            "- env_access_capability_present: "
            f"{_bool_text(result.env_access_capability_present)}"
        ),
        (
            "- credential_read_capability_present: "
            f"{_bool_text(result.credential_read_capability_present)}"
        ),
        f"- credential_values_read: {_bool_text(result.credential_values_read)}",
        (
            "- credential_metadata_present: "
            f"{_bool_text(result.credential_metadata_present)}"
        ),
        f"- checker_result_available: {_bool_text(result.checker_result_available)}",
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
        (
            "- operator_workflow_supported: "
            f"{_bool_text(result.operator_workflow_supported)}"
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
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
) -> tuple[LiveOrderRealCredentialPresenceCheckerImplementationCheckResult, ...]:
    groups = (
        (
            "checker implementation input",
            _input_reasons(implementation_input),
            "implementation skeleton mode and prerequisite contracts ready",
        ),
        (
            "execution deferred",
            _execution_reasons(implementation_input),
            "checker execution is deferred to a future step",
        ),
        (
            "no Codex env access",
            _env_reasons(implementation_input),
            "Codex does not access env or expose env capability",
        ),
        (
            "no credential read",
            _credential_read_reasons(implementation_input),
            "no credential read capability values or metadata",
        ),
        (
            "no checker result exposure",
            _result_exposure_reasons(implementation_input),
            "checker result detail is not available stored or displayed",
        ),
        (
            "known non-stale checker result state",
            _unknown_failed_unavailable_reasons(implementation_input),
            "checker result is not unknown failed unavailable or stale",
        ),
        (
            "operator workflow preserved",
            _operator_workflow_reasons(implementation_input),
            "operator-executed workflow remains supported and preserved",
        ),
        (
            "no real signing or post",
            _real_signing_or_post_reasons(implementation_input),
            "no real signing headers API post endpoint or live_order_once",
        ),
    )
    return tuple(
        LiveOrderRealCredentialPresenceCheckerImplementationCheckResult(
            name=name,
            passed=not reasons,
            sanitized_value="ready" if not reasons else ",".join(reasons),
            expected=expected,
        )
        for name, reasons, expected in groups
    )


def _input_reasons(
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_unsupported_implementation_mode(implementation_input):
        reasons.append("implementation_mode_unsupported")
    for field_name in (
        "checker_contract_ready",
        "operator_checker_workflow_ready",
        "credential_presence_adapter_ready",
        "credential_presence_check_ready",
        "implementation_interface_declared",
        "implementation_lifecycle_declared",
    ):
        if not getattr(implementation_input, field_name):
            reasons.append(f"{field_name}_false")
    return tuple(reasons)


def _execution_reasons(
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not implementation_input.execution_deferred_to_future_step:
        reasons.append("execution_deferred_to_future_step_false")
    for field_name in (
        "execution_performed",
        "actual_environment_presence_check_performed",
    ):
        if getattr(implementation_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _env_reasons(
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("codex_env_access_requested", "env_access_capability_present"):
        if getattr(implementation_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_read_reasons(
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_read_capability_present",
        "credential_values_read",
        "credential_values_present",
        "credential_metadata_present",
    ):
        if getattr(implementation_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _result_exposure_reasons(
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "checker_result_available",
        "checker_result_detail_present",
        "checker_result_saved",
        "checker_result_displayed",
    ):
        if getattr(implementation_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _unknown_failed_unavailable_reasons(
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "checker_result_unknown",
        "checker_result_failed",
        "checker_result_unavailable",
        "checker_result_stale",
    ):
        if getattr(implementation_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_signing_or_post_reasons(
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
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
        if getattr(implementation_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _operator_workflow_reasons(
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("operator_workflow_supported", "operator_workflow_preserved"):
        if not getattr(implementation_input, field_name):
            reasons.append(f"{field_name}_false")
    return tuple(reasons)


def _display_or_save_reasons(
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not implementation_input.safe_to_render:
        reasons.append("safe_to_render_false")
    if not implementation_input.safe_to_serialize:
        reasons.append("safe_to_serialize_false")
    return tuple(reasons)


def _unsupported_reasons(
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if implementation_input.retry_allowed:
        reasons.append("retry_allowed_unsupported")
    if implementation_input.loop_allowed:
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
    result: LiveOrderRealCredentialPresenceCheckerImplementationResult,
) -> None:
    unsafe_flags = (
        result.raw_implementation_mode_displayed,
        result.raw_implementation_mode_saved,
        result.execution_performed,
        result.codex_env_access_requested,
        result.actual_environment_presence_check_performed,
        result.env_access_capability_present,
        result.credential_read_capability_present,
        result.credential_values_read,
        result.credential_values_present,
        result.credential_metadata_present,
        result.checker_result_available,
        result.checker_result_detail_present,
        result.checker_result_unknown,
        result.checker_result_failed,
        result.checker_result_unavailable,
        result.checker_result_stale,
        result.checker_result_saved,
        result.checker_result_displayed,
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
            "checker implementation skeleton result is unsafe",
        )
    if result.unsupported_implementation_mode_present:
        if result.implementation_mode != UNSUPPORTED_CHECKER_IMPLEMENTATION_MODE_LABEL:
            raise LiveVerificationValidationError(
                "unsupported checker implementation mode must use safe label",
            )
    elif (
        result.implementation_mode
        != CredentialPresenceCheckerImplementationMode
        .CHECKER_IMPLEMENTATION_SKELETON_ONLY
        .value
    ):
        raise LiveVerificationValidationError(
            "checker implementation mode must be canonical",
        )


def _has_unsupported_implementation_mode(
    implementation_input: LiveOrderRealCredentialPresenceCheckerImplementationInput,
) -> bool:
    return (
        implementation_input.implementation_mode
        != CredentialPresenceCheckerImplementationMode
        .CHECKER_IMPLEMENTATION_SKELETON_ONLY
        .value
    )


def _safe_implementation_mode(raw_implementation_mode: str) -> str:
    if (
        raw_implementation_mode
        == CredentialPresenceCheckerImplementationMode
        .CHECKER_IMPLEMENTATION_SKELETON_ONLY
        .value
    ):
        return (
            CredentialPresenceCheckerImplementationMode
            .CHECKER_IMPLEMENTATION_SKELETON_ONLY
            .value
        )
    return UNSUPPORTED_CHECKER_IMPLEMENTATION_MODE_LABEL


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
