"""Step 6G credential boundary skeleton, boundary-only.

This module defines a credential boundary contract for a future real signing
step. It does not read env, check real credential presence, use credential
values, generate signatures or header values, call APIs, or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

CREDENTIAL_BOUNDARY_RECOMMENDED_NEXT_STEP = (
    "future_real_credential_injection_must_be_a_separate_step"
)


class LiveOrderRealCredentialBoundaryStatus(str, Enum):
    CREDENTIAL_BOUNDARY_READY_NO_CREDENTIAL_NO_ENV = (
        "CREDENTIAL_BOUNDARY_READY_NO_CREDENTIAL_NO_ENV"
    )
    BLOCKED_CREDENTIAL_BOUNDARY_INPUT = "BLOCKED_CREDENTIAL_BOUNDARY_INPUT"
    BLOCKED_CREDENTIAL_BOUNDARY_REAL_CREDENTIAL_REQUESTED = (
        "BLOCKED_CREDENTIAL_BOUNDARY_REAL_CREDENTIAL_REQUESTED"
    )
    BLOCKED_CREDENTIAL_BOUNDARY_VALUE_PROVIDED = (
        "BLOCKED_CREDENTIAL_BOUNDARY_VALUE_PROVIDED"
    )
    BLOCKED_CREDENTIAL_BOUNDARY_VALUE_LOADED = "BLOCKED_CREDENTIAL_BOUNDARY_VALUE_LOADED"
    BLOCKED_CREDENTIAL_BOUNDARY_ENV_ACCESS = "BLOCKED_CREDENTIAL_BOUNDARY_ENV_ACCESS"
    BLOCKED_CREDENTIAL_BOUNDARY_METADATA_EXPOSURE = (
        "BLOCKED_CREDENTIAL_BOUNDARY_METADATA_EXPOSURE"
    )
    BLOCKED_CREDENTIAL_BOUNDARY_DISPLAY_OR_SAVE = (
        "BLOCKED_CREDENTIAL_BOUNDARY_DISPLAY_OR_SAVE"
    )
    BLOCKED_CREDENTIAL_BOUNDARY_REAL_SIGNING_OR_POST = (
        "BLOCKED_CREDENTIAL_BOUNDARY_REAL_SIGNING_OR_POST"
    )
    BLOCKED_CREDENTIAL_BOUNDARY_UNSUPPORTED = "BLOCKED_CREDENTIAL_BOUNDARY_UNSUPPORTED"


class LiveOrderRealCredentialBoundaryMode(str, Enum):
    BOUNDARY_ONLY = "BOUNDARY_ONLY"


CredentialBoundaryStatus = LiveOrderRealCredentialBoundaryStatus
CredentialBoundaryMode = LiveOrderRealCredentialBoundaryMode


@dataclass(frozen=True)
class LiveOrderRealCredentialBoundaryInput:
    boundary_mode: str = CredentialBoundaryMode.BOUNDARY_ONLY.value
    real_credentials_requested: bool = False
    credential_values_provided: bool = False
    credential_values_loaded: bool = False
    credential_presence_checked_against_environment: bool = False
    env_access_requested: bool = False
    dotenv_access_requested: bool = False
    printenv_requested: bool = False
    credential_length_available: bool = False
    credential_hash_available: bool = False
    credential_fingerprint_available: bool = False
    credential_preview_available: bool = False
    credential_prefix_available: bool = False
    credential_suffix_available: bool = False
    credential_values_displayed: bool = False
    credential_values_saved: bool = False
    credentials_safe_to_render: bool = True
    credentials_safe_to_serialize: bool = True
    signing_contract_ready: bool = True
    dummy_signing_ready: bool = True
    http_transport_interface_ready: bool = True
    can_generate_real_signature: bool = False
    can_generate_real_headers: bool = False
    can_execute_http_post: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    retry_allowed: bool = False
    loop_allowed: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("boundary_mode", self.boundary_mode)
        _validate_bool_fields(
            self,
            (
                "real_credentials_requested",
                "credential_values_provided",
                "credential_values_loaded",
                "credential_presence_checked_against_environment",
                "env_access_requested",
                "dotenv_access_requested",
                "printenv_requested",
                "credential_length_available",
                "credential_hash_available",
                "credential_fingerprint_available",
                "credential_preview_available",
                "credential_prefix_available",
                "credential_suffix_available",
                "credential_values_displayed",
                "credential_values_saved",
                "credentials_safe_to_render",
                "credentials_safe_to_serialize",
                "signing_contract_ready",
                "dummy_signing_ready",
                "http_transport_interface_ready",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "can_execute_http_post",
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
class LiveOrderRealCredentialBoundaryCheckResult:
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
class LiveOrderRealCredentialBoundaryResult:
    status: LiveOrderRealCredentialBoundaryStatus
    credential_boundary_ready: bool
    boundary_mode: str
    real_credentials_requested: bool
    credential_values_provided: bool
    credential_values_loaded: bool
    credential_presence_checked_against_environment: bool
    env_access_requested: bool
    dotenv_access_requested: bool
    printenv_requested: bool
    credential_metadata_exposed: bool
    credential_values_displayed: bool
    credential_values_saved: bool
    credentials_safe_to_render: bool
    credentials_safe_to_serialize: bool
    signing_contract_ready: bool
    dummy_signing_ready: bool
    http_transport_interface_ready: bool
    can_generate_real_signature: bool
    can_generate_real_headers: bool
    can_execute_http_post: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_executed: bool
    retry_allowed: bool
    loop_allowed: bool
    check_results: tuple[LiveOrderRealCredentialBoundaryCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealCredentialBoundaryStatus):
            raise LiveVerificationValidationError("status must be credential boundary status")
        _require_non_empty("boundary_mode", self.boundary_mode)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "credential_boundary_ready",
                "real_credentials_requested",
                "credential_values_provided",
                "credential_values_loaded",
                "credential_presence_checked_against_environment",
                "env_access_requested",
                "dotenv_access_requested",
                "printenv_requested",
                "credential_metadata_exposed",
                "credential_values_displayed",
                "credential_values_saved",
                "credentials_safe_to_render",
                "credentials_safe_to_serialize",
                "signing_contract_ready",
                "dummy_signing_ready",
                "http_transport_interface_ready",
                "can_generate_real_signature",
                "can_generate_real_headers",
                "can_execute_http_post",
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


def build_live_order_real_credential_boundary(
    *,
    input_snapshot: LiveOrderRealCredentialBoundaryInput | None = None,
) -> LiveOrderRealCredentialBoundaryResult:
    """Build a boundary-only credential decision without real credential access."""
    boundary_input = input_snapshot or LiveOrderRealCredentialBoundaryInput()

    input_reasons = _input_reasons(boundary_input)
    real_credential_reasons = _real_credential_reasons(boundary_input)
    value_provided_reasons = _value_provided_reasons(boundary_input)
    value_loaded_reasons = _value_loaded_reasons(boundary_input)
    env_reasons = _env_reasons(boundary_input)
    metadata_reasons = _metadata_reasons(boundary_input)
    display_reasons = _display_or_save_reasons(boundary_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(boundary_input)
    unsupported_reasons = _unsupported_reasons(boundary_input)

    if real_credential_reasons:
        status = CredentialBoundaryStatus.BLOCKED_CREDENTIAL_BOUNDARY_REAL_CREDENTIAL_REQUESTED
        primary_reasons = real_credential_reasons
    elif value_provided_reasons:
        status = CredentialBoundaryStatus.BLOCKED_CREDENTIAL_BOUNDARY_VALUE_PROVIDED
        primary_reasons = value_provided_reasons
    elif value_loaded_reasons:
        status = CredentialBoundaryStatus.BLOCKED_CREDENTIAL_BOUNDARY_VALUE_LOADED
        primary_reasons = value_loaded_reasons
    elif env_reasons:
        status = CredentialBoundaryStatus.BLOCKED_CREDENTIAL_BOUNDARY_ENV_ACCESS
        primary_reasons = env_reasons
    elif metadata_reasons:
        status = CredentialBoundaryStatus.BLOCKED_CREDENTIAL_BOUNDARY_METADATA_EXPOSURE
        primary_reasons = metadata_reasons
    elif display_reasons:
        status = CredentialBoundaryStatus.BLOCKED_CREDENTIAL_BOUNDARY_DISPLAY_OR_SAVE
        primary_reasons = display_reasons
    elif real_signing_or_post_reasons:
        status = CredentialBoundaryStatus.BLOCKED_CREDENTIAL_BOUNDARY_REAL_SIGNING_OR_POST
        primary_reasons = real_signing_or_post_reasons
    elif input_reasons:
        status = CredentialBoundaryStatus.BLOCKED_CREDENTIAL_BOUNDARY_INPUT
        primary_reasons = input_reasons
    elif unsupported_reasons:
        status = CredentialBoundaryStatus.BLOCKED_CREDENTIAL_BOUNDARY_UNSUPPORTED
        primary_reasons = unsupported_reasons
    else:
        status = CredentialBoundaryStatus.CREDENTIAL_BOUNDARY_READY_NO_CREDENTIAL_NO_ENV
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        real_credential_reasons,
        value_provided_reasons,
        value_loaded_reasons,
        env_reasons,
        metadata_reasons,
        display_reasons,
        real_signing_or_post_reasons,
        input_reasons,
        unsupported_reasons,
    )
    ready = status is CredentialBoundaryStatus.CREDENTIAL_BOUNDARY_READY_NO_CREDENTIAL_NO_ENV
    return LiveOrderRealCredentialBoundaryResult(
        status=status,
        credential_boundary_ready=ready,
        boundary_mode=boundary_input.boundary_mode,
        real_credentials_requested=False,
        credential_values_provided=False,
        credential_values_loaded=False,
        credential_presence_checked_against_environment=False,
        env_access_requested=False,
        dotenv_access_requested=False,
        printenv_requested=False,
        credential_metadata_exposed=False,
        credential_values_displayed=False,
        credential_values_saved=False,
        credentials_safe_to_render=True,
        credentials_safe_to_serialize=True,
        signing_contract_ready=boundary_input.signing_contract_ready,
        dummy_signing_ready=boundary_input.dummy_signing_ready,
        http_transport_interface_ready=boundary_input.http_transport_interface_ready,
        can_generate_real_signature=False,
        can_generate_real_headers=False,
        can_execute_http_post=False,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_executed=False,
        retry_allowed=False,
        loop_allowed=False,
        check_results=_build_check_results(boundary_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            CREDENTIAL_BOUNDARY_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_credential_boundary_blockers_no_credential_no_env_no_post"
        ),
    )


def render_live_order_real_credential_boundary_markdown(
    result: LiveOrderRealCredentialBoundaryResult,
) -> str:
    """Render sanitized boundary metadata only."""
    lines = [
        "# Step 6G Credential Boundary Skeleton",
        "",
        "This credential boundary is boundary-only.",
        "This credential boundary does not use real credentials.",
        "This credential boundary does not access env or .env.",
        "This credential boundary does not expose credential metadata.",
        "This credential boundary does not generate real signatures.",
        "This credential boundary does not execute API calls.",
        "This credential boundary does not execute HTTP POST.",
        "This credential boundary does not call order endpoint.",
        "This credential boundary does not call live_order_once.",
        "Future real credential injection must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- credential_boundary_ready: {_bool_text(result.credential_boundary_ready)}",
        f"- boundary_mode: {result.boundary_mode}",
        "",
        "## Safety",
        f"- real_credentials_requested: {_bool_text(result.real_credentials_requested)}",
        f"- credential_values_provided: {_bool_text(result.credential_values_provided)}",
        f"- credential_values_loaded: {_bool_text(result.credential_values_loaded)}",
        (
            "- credential_presence_checked_against_environment: "
            f"{_bool_text(result.credential_presence_checked_against_environment)}"
        ),
        f"- env_access_requested: {_bool_text(result.env_access_requested)}",
        f"- dotenv_access_requested: {_bool_text(result.dotenv_access_requested)}",
        f"- printenv_requested: {_bool_text(result.printenv_requested)}",
        f"- credential_metadata_exposed: {_bool_text(result.credential_metadata_exposed)}",
        f"- credential_values_displayed: {_bool_text(result.credential_values_displayed)}",
        f"- credential_values_saved: {_bool_text(result.credential_values_saved)}",
        f"- credentials_safe_to_render: {_bool_text(result.credentials_safe_to_render)}",
        f"- credentials_safe_to_serialize: {_bool_text(result.credentials_safe_to_serialize)}",
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
    boundary_input: LiveOrderRealCredentialBoundaryInput,
) -> tuple[LiveOrderRealCredentialBoundaryCheckResult, ...]:
    input_reasons = _input_reasons(boundary_input)
    no_value_reasons = _merge_reasons(
        _real_credential_reasons(boundary_input),
        _value_provided_reasons(boundary_input),
        _value_loaded_reasons(boundary_input),
        _metadata_reasons(boundary_input),
        _display_or_save_reasons(boundary_input),
    )
    env_reasons = _env_reasons(boundary_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(boundary_input)
    return (
        LiveOrderRealCredentialBoundaryCheckResult(
            name="credential boundary input",
            passed=not input_reasons,
            sanitized_value="ready" if not input_reasons else ",".join(input_reasons),
            expected="BOUNDARY_ONLY and ready prerequisite contracts",
        ),
        LiveOrderRealCredentialBoundaryCheckResult(
            name="no credential value or metadata",
            passed=not no_value_reasons,
            sanitized_value="none" if not no_value_reasons else ",".join(no_value_reasons),
            expected="no credential value metadata display save or load",
        ),
        LiveOrderRealCredentialBoundaryCheckResult(
            name="no env access",
            passed=not env_reasons,
            sanitized_value="none" if not env_reasons else ",".join(env_reasons),
            expected="no env .env printenv or real presence check",
        ),
        LiveOrderRealCredentialBoundaryCheckResult(
            name="no real signing or post",
            passed=not real_signing_or_post_reasons,
            sanitized_value="none"
            if not real_signing_or_post_reasons
            else ",".join(real_signing_or_post_reasons),
            expected="no real signing headers API post endpoint or live_order_once",
        ),
    )


def _input_reasons(
    boundary_input: LiveOrderRealCredentialBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if boundary_input.boundary_mode != CredentialBoundaryMode.BOUNDARY_ONLY.value:
        reasons.append("boundary_mode_not_boundary_only")
    for field_name in (
        "signing_contract_ready",
        "dummy_signing_ready",
        "http_transport_interface_ready",
    ):
        if not getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_false")
    return tuple(reasons)


def _real_credential_reasons(
    boundary_input: LiveOrderRealCredentialBoundaryInput,
) -> tuple[str, ...]:
    if boundary_input.real_credentials_requested:
        return ("real_credentials_requested",)
    return ()


def _value_provided_reasons(
    boundary_input: LiveOrderRealCredentialBoundaryInput,
) -> tuple[str, ...]:
    if boundary_input.credential_values_provided:
        return ("credential_values_provided",)
    return ()


def _value_loaded_reasons(
    boundary_input: LiveOrderRealCredentialBoundaryInput,
) -> tuple[str, ...]:
    if boundary_input.credential_values_loaded:
        return ("credential_values_loaded",)
    return ()


def _env_reasons(
    boundary_input: LiveOrderRealCredentialBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_presence_checked_against_environment",
        "env_access_requested",
        "dotenv_access_requested",
        "printenv_requested",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _metadata_reasons(
    boundary_input: LiveOrderRealCredentialBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_length_available",
        "credential_hash_available",
        "credential_fingerprint_available",
        "credential_preview_available",
        "credential_prefix_available",
        "credential_suffix_available",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _display_or_save_reasons(
    boundary_input: LiveOrderRealCredentialBoundaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_values_displayed",
        "credential_values_saved",
    ):
        if getattr(boundary_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    if not boundary_input.credentials_safe_to_render:
        reasons.append("credentials_safe_to_render_false")
    if not boundary_input.credentials_safe_to_serialize:
        reasons.append("credentials_safe_to_serialize_false")
    return tuple(reasons)


def _real_signing_or_post_reasons(
    boundary_input: LiveOrderRealCredentialBoundaryInput,
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


def _unsupported_reasons(
    boundary_input: LiveOrderRealCredentialBoundaryInput,
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


def _validate_result_safety(result: LiveOrderRealCredentialBoundaryResult) -> None:
    unsafe_flags = (
        result.real_credentials_requested,
        result.credential_values_provided,
        result.credential_values_loaded,
        result.credential_presence_checked_against_environment,
        result.env_access_requested,
        result.dotenv_access_requested,
        result.printenv_requested,
        result.credential_metadata_exposed,
        result.credential_values_displayed,
        result.credential_values_saved,
        not result.credentials_safe_to_render,
        not result.credentials_safe_to_serialize,
        result.can_generate_real_signature,
        result.can_generate_real_headers,
        result.can_execute_http_post,
        result.http_post_executed,
        result.order_endpoint_called,
        result.live_order_once_called,
        result.post_allowed_this_step,
        result.post_executed,
        result.retry_allowed,
        result.loop_allowed,
    )
    if any(unsafe_flags):
        raise LiveVerificationValidationError("credential boundary result is unsafe")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
