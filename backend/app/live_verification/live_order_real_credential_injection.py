"""Step 6G credential injection skeleton, skeleton-only.

This module defines the stop conditions for a future real credential injection
step. It does not inject real credentials, create handles, read env, check real
credential presence, generate signatures or header values, call APIs, or execute
HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

CREDENTIAL_INJECTION_RECOMMENDED_NEXT_STEP = (
    "future_real_credential_injection_must_be_a_separate_step"
)


class LiveOrderRealCredentialInjectionStatus(str, Enum):
    CREDENTIAL_INJECTION_READY_NO_VALUE_NO_ENV = (
        "CREDENTIAL_INJECTION_READY_NO_VALUE_NO_ENV"
    )
    BLOCKED_CREDENTIAL_INJECTION_INPUT = "BLOCKED_CREDENTIAL_INJECTION_INPUT"
    BLOCKED_CREDENTIAL_INJECTION_PERFORMED = "BLOCKED_CREDENTIAL_INJECTION_PERFORMED"
    BLOCKED_CREDENTIAL_INJECTION_REAL_CREDENTIAL_AVAILABLE = (
        "BLOCKED_CREDENTIAL_INJECTION_REAL_CREDENTIAL_AVAILABLE"
    )
    BLOCKED_CREDENTIAL_INJECTION_CREDENTIAL_VALUE = (
        "BLOCKED_CREDENTIAL_INJECTION_CREDENTIAL_VALUE"
    )
    BLOCKED_CREDENTIAL_INJECTION_CREDENTIAL_METADATA = (
        "BLOCKED_CREDENTIAL_INJECTION_CREDENTIAL_METADATA"
    )
    BLOCKED_CREDENTIAL_INJECTION_HANDLE_VALUE = (
        "BLOCKED_CREDENTIAL_INJECTION_HANDLE_VALUE"
    )
    BLOCKED_CREDENTIAL_INJECTION_ENV_ACCESS = (
        "BLOCKED_CREDENTIAL_INJECTION_ENV_ACCESS"
    )
    BLOCKED_CREDENTIAL_INJECTION_REAL_SIGNING_OR_POST = (
        "BLOCKED_CREDENTIAL_INJECTION_REAL_SIGNING_OR_POST"
    )
    BLOCKED_CREDENTIAL_INJECTION_DISPLAY_OR_SAVE = (
        "BLOCKED_CREDENTIAL_INJECTION_DISPLAY_OR_SAVE"
    )
    BLOCKED_CREDENTIAL_INJECTION_UNSUPPORTED = (
        "BLOCKED_CREDENTIAL_INJECTION_UNSUPPORTED"
    )


class LiveOrderRealCredentialInjectionMode(str, Enum):
    INJECTION_SKELETON_ONLY = "INJECTION_SKELETON_ONLY"


CredentialInjectionStatus = LiveOrderRealCredentialInjectionStatus
CredentialInjectionMode = LiveOrderRealCredentialInjectionMode


@dataclass(frozen=True)
class LiveOrderRealCredentialInjectionInput:
    injection_mode: str = CredentialInjectionMode.INJECTION_SKELETON_ONLY.value
    credential_boundary_ready: bool = True
    credential_handle_ready: bool = True
    injection_requested: bool = True
    injection_performed: bool = False
    real_credential_values_available: bool = False
    real_credential_values_injected: bool = False
    credential_values_provided: bool = False
    credential_values_loaded: bool = False
    credential_values_displayed: bool = False
    credential_values_saved: bool = False
    credential_metadata_available: bool = False
    credential_metadata_displayed: bool = False
    credential_metadata_saved: bool = False
    handle_created: bool = False
    handle_contains_value: bool = False
    handle_contains_identifier: bool = False
    handle_value_displayed: bool = False
    handle_value_saved: bool = False
    env_access_requested: bool = False
    dotenv_access_requested: bool = False
    credential_presence_checked_against_environment: bool = False
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
        _require_non_empty("injection_mode", self.injection_mode)
        _validate_bool_fields(
            self,
            (
                "credential_boundary_ready",
                "credential_handle_ready",
                "injection_requested",
                "injection_performed",
                "real_credential_values_available",
                "real_credential_values_injected",
                "credential_values_provided",
                "credential_values_loaded",
                "credential_values_displayed",
                "credential_values_saved",
                "credential_metadata_available",
                "credential_metadata_displayed",
                "credential_metadata_saved",
                "handle_created",
                "handle_contains_value",
                "handle_contains_identifier",
                "handle_value_displayed",
                "handle_value_saved",
                "env_access_requested",
                "dotenv_access_requested",
                "credential_presence_checked_against_environment",
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
class LiveOrderRealCredentialInjectionCheckResult:
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
class LiveOrderRealCredentialInjectionResult:
    status: LiveOrderRealCredentialInjectionStatus
    credential_injection_ready: bool
    injection_mode: str
    credential_boundary_ready: bool
    credential_handle_ready: bool
    injection_requested: bool
    injection_performed: bool
    real_credential_values_available: bool
    real_credential_values_injected: bool
    credential_values_provided: bool
    credential_values_loaded: bool
    credential_values_displayed: bool
    credential_values_saved: bool
    credential_metadata_available: bool
    credential_metadata_displayed: bool
    credential_metadata_saved: bool
    handle_created: bool
    handle_contains_value: bool
    handle_contains_identifier: bool
    handle_value_displayed: bool
    handle_value_saved: bool
    env_access_requested: bool
    dotenv_access_requested: bool
    credential_presence_checked_against_environment: bool
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
    check_results: tuple[LiveOrderRealCredentialInjectionCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealCredentialInjectionStatus):
            raise LiveVerificationValidationError(
                "status must be credential injection status",
            )
        _require_non_empty("injection_mode", self.injection_mode)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "credential_injection_ready",
                "credential_boundary_ready",
                "credential_handle_ready",
                "injection_requested",
                "injection_performed",
                "real_credential_values_available",
                "real_credential_values_injected",
                "credential_values_provided",
                "credential_values_loaded",
                "credential_values_displayed",
                "credential_values_saved",
                "credential_metadata_available",
                "credential_metadata_displayed",
                "credential_metadata_saved",
                "handle_created",
                "handle_contains_value",
                "handle_contains_identifier",
                "handle_value_displayed",
                "handle_value_saved",
                "env_access_requested",
                "dotenv_access_requested",
                "credential_presence_checked_against_environment",
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


def build_live_order_real_credential_injection(
    *,
    input_snapshot: LiveOrderRealCredentialInjectionInput | None = None,
) -> LiveOrderRealCredentialInjectionResult:
    """Build a skeleton-only credential injection decision without value access."""
    injection_input = input_snapshot or LiveOrderRealCredentialInjectionInput()

    input_reasons = _input_reasons(injection_input)
    performed_reasons = _performed_reasons(injection_input)
    real_credential_reasons = _real_credential_available_reasons(injection_input)
    credential_value_reasons = _credential_value_reasons(injection_input)
    credential_metadata_reasons = _credential_metadata_reasons(injection_input)
    handle_value_reasons = _handle_value_reasons(injection_input)
    env_reasons = _env_reasons(injection_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(injection_input)
    display_reasons = _display_or_save_reasons(injection_input)
    unsupported_reasons = _unsupported_reasons(injection_input)

    if input_reasons:
        status = CredentialInjectionStatus.BLOCKED_CREDENTIAL_INJECTION_INPUT
        primary_reasons = input_reasons
    elif performed_reasons:
        status = CredentialInjectionStatus.BLOCKED_CREDENTIAL_INJECTION_PERFORMED
        primary_reasons = performed_reasons
    elif real_credential_reasons:
        status = (
            CredentialInjectionStatus
            .BLOCKED_CREDENTIAL_INJECTION_REAL_CREDENTIAL_AVAILABLE
        )
        primary_reasons = real_credential_reasons
    elif credential_value_reasons:
        status = CredentialInjectionStatus.BLOCKED_CREDENTIAL_INJECTION_CREDENTIAL_VALUE
        primary_reasons = credential_value_reasons
    elif credential_metadata_reasons:
        status = (
            CredentialInjectionStatus
            .BLOCKED_CREDENTIAL_INJECTION_CREDENTIAL_METADATA
        )
        primary_reasons = credential_metadata_reasons
    elif handle_value_reasons:
        status = CredentialInjectionStatus.BLOCKED_CREDENTIAL_INJECTION_HANDLE_VALUE
        primary_reasons = handle_value_reasons
    elif env_reasons:
        status = CredentialInjectionStatus.BLOCKED_CREDENTIAL_INJECTION_ENV_ACCESS
        primary_reasons = env_reasons
    elif real_signing_or_post_reasons:
        status = (
            CredentialInjectionStatus
            .BLOCKED_CREDENTIAL_INJECTION_REAL_SIGNING_OR_POST
        )
        primary_reasons = real_signing_or_post_reasons
    elif display_reasons:
        status = CredentialInjectionStatus.BLOCKED_CREDENTIAL_INJECTION_DISPLAY_OR_SAVE
        primary_reasons = display_reasons
    elif unsupported_reasons:
        status = CredentialInjectionStatus.BLOCKED_CREDENTIAL_INJECTION_UNSUPPORTED
        primary_reasons = unsupported_reasons
    else:
        status = CredentialInjectionStatus.CREDENTIAL_INJECTION_READY_NO_VALUE_NO_ENV
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        input_reasons,
        performed_reasons,
        real_credential_reasons,
        credential_value_reasons,
        credential_metadata_reasons,
        handle_value_reasons,
        env_reasons,
        real_signing_or_post_reasons,
        display_reasons,
        unsupported_reasons,
    )
    ready = (
        status
        is CredentialInjectionStatus.CREDENTIAL_INJECTION_READY_NO_VALUE_NO_ENV
    )
    return LiveOrderRealCredentialInjectionResult(
        status=status,
        credential_injection_ready=ready,
        injection_mode=injection_input.injection_mode,
        credential_boundary_ready=injection_input.credential_boundary_ready,
        credential_handle_ready=injection_input.credential_handle_ready,
        injection_requested=injection_input.injection_requested,
        injection_performed=False,
        real_credential_values_available=False,
        real_credential_values_injected=False,
        credential_values_provided=False,
        credential_values_loaded=False,
        credential_values_displayed=False,
        credential_values_saved=False,
        credential_metadata_available=False,
        credential_metadata_displayed=False,
        credential_metadata_saved=False,
        handle_created=False,
        handle_contains_value=False,
        handle_contains_identifier=False,
        handle_value_displayed=False,
        handle_value_saved=False,
        env_access_requested=False,
        dotenv_access_requested=False,
        credential_presence_checked_against_environment=False,
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
        check_results=_build_check_results(injection_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            CREDENTIAL_INJECTION_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_credential_injection_blockers_no_value_no_env_no_post"
        ),
    )


def render_live_order_real_credential_injection_markdown(
    result: LiveOrderRealCredentialInjectionResult,
) -> str:
    """Render sanitized credential injection skeleton metadata only."""
    lines = [
        "# Step 6G Credential Injection Skeleton",
        "",
        "This credential injection is skeleton-only.",
        "This credential injection does not inject real credentials.",
        "This credential injection does not access env or .env.",
        "This credential injection does not expose credential metadata.",
        "This credential injection does not generate real signatures.",
        "This credential injection does not execute API calls.",
        "This credential injection does not execute HTTP POST.",
        "This credential injection does not call order endpoint.",
        "This credential injection does not call live_order_once.",
        "Future real credential injection must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- credential_injection_ready: {_bool_text(result.credential_injection_ready)}",
        f"- injection_mode: {result.injection_mode}",
        f"- credential_boundary_ready: {_bool_text(result.credential_boundary_ready)}",
        f"- credential_handle_ready: {_bool_text(result.credential_handle_ready)}",
        "",
        "## Safety",
        f"- injection_requested: {_bool_text(result.injection_requested)}",
        f"- injection_performed: {_bool_text(result.injection_performed)}",
        (
            "- real_credential_values_available: "
            f"{_bool_text(result.real_credential_values_available)}"
        ),
        (
            "- real_credential_values_injected: "
            f"{_bool_text(result.real_credential_values_injected)}"
        ),
        f"- credential_values_provided: {_bool_text(result.credential_values_provided)}",
        f"- credential_values_loaded: {_bool_text(result.credential_values_loaded)}",
        (
            "- credential_metadata_available: "
            f"{_bool_text(result.credential_metadata_available)}"
        ),
        f"- handle_created: {_bool_text(result.handle_created)}",
        f"- handle_contains_value: {_bool_text(result.handle_contains_value)}",
        f"- handle_contains_identifier: {_bool_text(result.handle_contains_identifier)}",
        f"- env_access_requested: {_bool_text(result.env_access_requested)}",
        f"- dotenv_access_requested: {_bool_text(result.dotenv_access_requested)}",
        (
            "- credential_presence_checked_against_environment: "
            f"{_bool_text(result.credential_presence_checked_against_environment)}"
        ),
        f"- can_generate_real_signature: {_bool_text(result.can_generate_real_signature)}",
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
    injection_input: LiveOrderRealCredentialInjectionInput,
) -> tuple[LiveOrderRealCredentialInjectionCheckResult, ...]:
    input_reasons = _input_reasons(injection_input)
    no_injection_reasons = _merge_reasons(
        _performed_reasons(injection_input),
        _real_credential_available_reasons(injection_input),
        _credential_value_reasons(injection_input),
        _credential_metadata_reasons(injection_input),
        _handle_value_reasons(injection_input),
        _display_or_save_reasons(injection_input),
    )
    env_reasons = _env_reasons(injection_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(injection_input)
    return (
        LiveOrderRealCredentialInjectionCheckResult(
            name="credential injection input",
            passed=not input_reasons,
            sanitized_value="ready" if not input_reasons else ",".join(input_reasons),
            expected="INJECTION_SKELETON_ONLY with boundary handle ready and requested",
        ),
        LiveOrderRealCredentialInjectionCheckResult(
            name="no credential injection value or metadata",
            passed=not no_injection_reasons,
            sanitized_value="none"
            if not no_injection_reasons
            else ",".join(no_injection_reasons),
            expected="no real credential value injection handle metadata display or save",
        ),
        LiveOrderRealCredentialInjectionCheckResult(
            name="no env access",
            passed=not env_reasons,
            sanitized_value="none" if not env_reasons else ",".join(env_reasons),
            expected="no env dotenv or real presence check",
        ),
        LiveOrderRealCredentialInjectionCheckResult(
            name="no real signing or post",
            passed=not real_signing_or_post_reasons,
            sanitized_value="none"
            if not real_signing_or_post_reasons
            else ",".join(real_signing_or_post_reasons),
            expected="no real signing headers API post endpoint or live_order_once",
        ),
    )


def _input_reasons(
    injection_input: LiveOrderRealCredentialInjectionInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        injection_input.injection_mode
        != CredentialInjectionMode.INJECTION_SKELETON_ONLY.value
    ):
        reasons.append("injection_mode_not_skeleton_only")
    if not injection_input.credential_boundary_ready:
        reasons.append("credential_boundary_ready_false")
    if not injection_input.credential_handle_ready:
        reasons.append("credential_handle_ready_false")
    if not injection_input.injection_requested:
        reasons.append("injection_requested_false")
    return tuple(reasons)


def _performed_reasons(
    injection_input: LiveOrderRealCredentialInjectionInput,
) -> tuple[str, ...]:
    if injection_input.injection_performed:
        return ("injection_performed_unsafe",)
    return ()


def _real_credential_available_reasons(
    injection_input: LiveOrderRealCredentialInjectionInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "real_credential_values_available",
        "real_credential_values_injected",
    ):
        if getattr(injection_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_value_reasons(
    injection_input: LiveOrderRealCredentialInjectionInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("credential_values_provided", "credential_values_loaded"):
        if getattr(injection_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_metadata_reasons(
    injection_input: LiveOrderRealCredentialInjectionInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_metadata_available",
        "credential_metadata_displayed",
        "credential_metadata_saved",
    ):
        if getattr(injection_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _handle_value_reasons(
    injection_input: LiveOrderRealCredentialInjectionInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "handle_created",
        "handle_contains_value",
        "handle_contains_identifier",
    ):
        if getattr(injection_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _env_reasons(
    injection_input: LiveOrderRealCredentialInjectionInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "env_access_requested",
        "dotenv_access_requested",
        "credential_presence_checked_against_environment",
    ):
        if getattr(injection_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_signing_or_post_reasons(
    injection_input: LiveOrderRealCredentialInjectionInput,
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
        if getattr(injection_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _display_or_save_reasons(
    injection_input: LiveOrderRealCredentialInjectionInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_values_displayed",
        "credential_values_saved",
        "handle_value_displayed",
        "handle_value_saved",
    ):
        if getattr(injection_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    if not injection_input.safe_to_render:
        reasons.append("safe_to_render_false")
    if not injection_input.safe_to_serialize:
        reasons.append("safe_to_serialize_false")
    return tuple(reasons)


def _unsupported_reasons(
    injection_input: LiveOrderRealCredentialInjectionInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if injection_input.retry_allowed:
        reasons.append("retry_allowed_unsupported")
    if injection_input.loop_allowed:
        reasons.append("loop_allowed_unsupported")
    return tuple(reasons)


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _validate_result_safety(result: LiveOrderRealCredentialInjectionResult) -> None:
    unsafe_flags = (
        result.injection_performed,
        result.real_credential_values_available,
        result.real_credential_values_injected,
        result.credential_values_provided,
        result.credential_values_loaded,
        result.credential_values_displayed,
        result.credential_values_saved,
        result.credential_metadata_available,
        result.credential_metadata_displayed,
        result.credential_metadata_saved,
        result.handle_created,
        result.handle_contains_value,
        result.handle_contains_identifier,
        result.handle_value_displayed,
        result.handle_value_saved,
        result.env_access_requested,
        result.dotenv_access_requested,
        result.credential_presence_checked_against_environment,
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
        raise LiveVerificationValidationError("credential injection result is unsafe")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
