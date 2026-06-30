"""Step 6G credential handle contract, contract-only.

This module defines an opaque credential-handle contract for a future real
credential injection step. It does not create a real handle, read env, check
real credential presence, use credential values, generate signatures or header
values, call APIs, or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

CREDENTIAL_HANDLE_RECOMMENDED_NEXT_STEP = (
    "future_real_credential_injection_must_be_a_separate_step"
)


class LiveOrderRealCredentialHandleStatus(str, Enum):
    CREDENTIAL_HANDLE_READY_NO_VALUE_NO_ENV = "CREDENTIAL_HANDLE_READY_NO_VALUE_NO_ENV"
    BLOCKED_CREDENTIAL_HANDLE_INPUT = "BLOCKED_CREDENTIAL_HANDLE_INPUT"
    BLOCKED_CREDENTIAL_HANDLE_CREATED = "BLOCKED_CREDENTIAL_HANDLE_CREATED"
    BLOCKED_CREDENTIAL_HANDLE_VALUE_OR_SECRET = (
        "BLOCKED_CREDENTIAL_HANDLE_VALUE_OR_SECRET"
    )
    BLOCKED_CREDENTIAL_HANDLE_IDENTIFIER_OR_METADATA = (
        "BLOCKED_CREDENTIAL_HANDLE_IDENTIFIER_OR_METADATA"
    )
    BLOCKED_CREDENTIAL_HANDLE_DISPLAY_OR_SAVE = (
        "BLOCKED_CREDENTIAL_HANDLE_DISPLAY_OR_SAVE"
    )
    BLOCKED_CREDENTIAL_HANDLE_ENV_ACCESS = "BLOCKED_CREDENTIAL_HANDLE_ENV_ACCESS"
    BLOCKED_CREDENTIAL_HANDLE_CREDENTIAL_VALUE = (
        "BLOCKED_CREDENTIAL_HANDLE_CREDENTIAL_VALUE"
    )
    BLOCKED_CREDENTIAL_HANDLE_REAL_SIGNING_OR_POST = (
        "BLOCKED_CREDENTIAL_HANDLE_REAL_SIGNING_OR_POST"
    )
    BLOCKED_CREDENTIAL_HANDLE_UNSUPPORTED = "BLOCKED_CREDENTIAL_HANDLE_UNSUPPORTED"


class LiveOrderRealCredentialHandleMode(str, Enum):
    HANDLE_CONTRACT_ONLY = "HANDLE_CONTRACT_ONLY"


CredentialHandleStatus = LiveOrderRealCredentialHandleStatus
CredentialHandleMode = LiveOrderRealCredentialHandleMode


@dataclass(frozen=True)
class LiveOrderRealCredentialHandleInput:
    handle_mode: str = CredentialHandleMode.HANDLE_CONTRACT_ONLY.value
    credential_boundary_ready: bool = True
    handle_requested: bool = True
    handle_created: bool = False
    handle_contains_value: bool = False
    handle_contains_secret: bool = False
    handle_contains_token: bool = False
    handle_contains_key_material: bool = False
    handle_contains_identifier: bool = False
    handle_value_displayed: bool = False
    handle_value_saved: bool = False
    handle_metadata_displayed: bool = False
    handle_metadata_saved: bool = False
    handle_length_available: bool = False
    handle_hash_available: bool = False
    handle_fingerprint_available: bool = False
    handle_preview_available: bool = False
    handle_prefix_available: bool = False
    handle_suffix_available: bool = False
    env_access_requested: bool = False
    dotenv_access_requested: bool = False
    credential_values_provided: bool = False
    credential_values_loaded: bool = False
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
        _require_non_empty("handle_mode", self.handle_mode)
        _validate_bool_fields(
            self,
            (
                "credential_boundary_ready",
                "handle_requested",
                "handle_created",
                "handle_contains_value",
                "handle_contains_secret",
                "handle_contains_token",
                "handle_contains_key_material",
                "handle_contains_identifier",
                "handle_value_displayed",
                "handle_value_saved",
                "handle_metadata_displayed",
                "handle_metadata_saved",
                "handle_length_available",
                "handle_hash_available",
                "handle_fingerprint_available",
                "handle_preview_available",
                "handle_prefix_available",
                "handle_suffix_available",
                "env_access_requested",
                "dotenv_access_requested",
                "credential_values_provided",
                "credential_values_loaded",
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
class LiveOrderRealCredentialHandleCheckResult:
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
class LiveOrderRealCredentialHandleResult:
    status: LiveOrderRealCredentialHandleStatus
    credential_handle_ready: bool
    handle_mode: str
    credential_boundary_ready: bool
    handle_requested: bool
    handle_created: bool
    handle_contains_value: bool
    handle_contains_secret: bool
    handle_contains_token: bool
    handle_contains_key_material: bool
    handle_contains_identifier: bool
    handle_metadata_exposed: bool
    handle_value_displayed: bool
    handle_value_saved: bool
    handle_metadata_displayed: bool
    handle_metadata_saved: bool
    env_access_requested: bool
    dotenv_access_requested: bool
    credential_values_provided: bool
    credential_values_loaded: bool
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
    check_results: tuple[LiveOrderRealCredentialHandleCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealCredentialHandleStatus):
            raise LiveVerificationValidationError("status must be credential handle status")
        _require_non_empty("handle_mode", self.handle_mode)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "credential_handle_ready",
                "credential_boundary_ready",
                "handle_requested",
                "handle_created",
                "handle_contains_value",
                "handle_contains_secret",
                "handle_contains_token",
                "handle_contains_key_material",
                "handle_contains_identifier",
                "handle_metadata_exposed",
                "handle_value_displayed",
                "handle_value_saved",
                "handle_metadata_displayed",
                "handle_metadata_saved",
                "env_access_requested",
                "dotenv_access_requested",
                "credential_values_provided",
                "credential_values_loaded",
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


def build_live_order_real_credential_handle(
    *,
    input_snapshot: LiveOrderRealCredentialHandleInput | None = None,
) -> LiveOrderRealCredentialHandleResult:
    """Build a contract-only credential handle decision without value access."""
    handle_input = input_snapshot or LiveOrderRealCredentialHandleInput()

    input_reasons = _input_reasons(handle_input)
    created_reasons = _created_reasons(handle_input)
    value_reasons = _value_or_secret_reasons(handle_input)
    identifier_reasons = _identifier_or_metadata_reasons(handle_input)
    display_reasons = _display_or_save_reasons(handle_input)
    env_reasons = _env_reasons(handle_input)
    credential_value_reasons = _credential_value_reasons(handle_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(handle_input)
    unsupported_reasons = _unsupported_reasons(handle_input)

    if input_reasons:
        status = CredentialHandleStatus.BLOCKED_CREDENTIAL_HANDLE_INPUT
        primary_reasons = input_reasons
    elif created_reasons:
        status = CredentialHandleStatus.BLOCKED_CREDENTIAL_HANDLE_CREATED
        primary_reasons = created_reasons
    elif value_reasons:
        status = CredentialHandleStatus.BLOCKED_CREDENTIAL_HANDLE_VALUE_OR_SECRET
        primary_reasons = value_reasons
    elif identifier_reasons:
        status = CredentialHandleStatus.BLOCKED_CREDENTIAL_HANDLE_IDENTIFIER_OR_METADATA
        primary_reasons = identifier_reasons
    elif display_reasons:
        status = CredentialHandleStatus.BLOCKED_CREDENTIAL_HANDLE_DISPLAY_OR_SAVE
        primary_reasons = display_reasons
    elif env_reasons:
        status = CredentialHandleStatus.BLOCKED_CREDENTIAL_HANDLE_ENV_ACCESS
        primary_reasons = env_reasons
    elif credential_value_reasons:
        status = CredentialHandleStatus.BLOCKED_CREDENTIAL_HANDLE_CREDENTIAL_VALUE
        primary_reasons = credential_value_reasons
    elif real_signing_or_post_reasons:
        status = CredentialHandleStatus.BLOCKED_CREDENTIAL_HANDLE_REAL_SIGNING_OR_POST
        primary_reasons = real_signing_or_post_reasons
    elif unsupported_reasons:
        status = CredentialHandleStatus.BLOCKED_CREDENTIAL_HANDLE_UNSUPPORTED
        primary_reasons = unsupported_reasons
    else:
        status = CredentialHandleStatus.CREDENTIAL_HANDLE_READY_NO_VALUE_NO_ENV
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        input_reasons,
        created_reasons,
        value_reasons,
        identifier_reasons,
        display_reasons,
        env_reasons,
        credential_value_reasons,
        real_signing_or_post_reasons,
        unsupported_reasons,
    )
    ready = status is CredentialHandleStatus.CREDENTIAL_HANDLE_READY_NO_VALUE_NO_ENV
    return LiveOrderRealCredentialHandleResult(
        status=status,
        credential_handle_ready=ready,
        handle_mode=handle_input.handle_mode,
        credential_boundary_ready=handle_input.credential_boundary_ready,
        handle_requested=handle_input.handle_requested,
        handle_created=False,
        handle_contains_value=False,
        handle_contains_secret=False,
        handle_contains_token=False,
        handle_contains_key_material=False,
        handle_contains_identifier=False,
        handle_metadata_exposed=False,
        handle_value_displayed=False,
        handle_value_saved=False,
        handle_metadata_displayed=False,
        handle_metadata_saved=False,
        env_access_requested=False,
        dotenv_access_requested=False,
        credential_values_provided=False,
        credential_values_loaded=False,
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
        check_results=_build_check_results(handle_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            CREDENTIAL_HANDLE_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_credential_handle_blockers_no_value_no_env_no_post"
        ),
    )


def render_live_order_real_credential_handle_markdown(
    result: LiveOrderRealCredentialHandleResult,
) -> str:
    """Render sanitized credential handle contract metadata only."""
    lines = [
        "# Step 6G Credential Handle Contract",
        "",
        "This credential handle is contract-only.",
        "This credential handle does not create a real handle.",
        "This credential handle does not contain credential values.",
        "This credential handle does not access env or .env.",
        "This credential handle does not expose credential metadata.",
        "This credential handle does not generate real signatures.",
        "This credential handle does not execute API calls.",
        "This credential handle does not execute HTTP POST.",
        "This credential handle does not call order endpoint.",
        "This credential handle does not call live_order_once.",
        "Future real credential injection must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- credential_handle_ready: {_bool_text(result.credential_handle_ready)}",
        f"- handle_mode: {result.handle_mode}",
        f"- credential_boundary_ready: {_bool_text(result.credential_boundary_ready)}",
        "",
        "## Safety",
        f"- handle_requested: {_bool_text(result.handle_requested)}",
        f"- handle_created: {_bool_text(result.handle_created)}",
        f"- handle_contains_value: {_bool_text(result.handle_contains_value)}",
        f"- handle_contains_identifier: {_bool_text(result.handle_contains_identifier)}",
        f"- handle_metadata_exposed: {_bool_text(result.handle_metadata_exposed)}",
        f"- credential_values_provided: {_bool_text(result.credential_values_provided)}",
        f"- credential_values_loaded: {_bool_text(result.credential_values_loaded)}",
        f"- env_access_requested: {_bool_text(result.env_access_requested)}",
        f"- dotenv_access_requested: {_bool_text(result.dotenv_access_requested)}",
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
    handle_input: LiveOrderRealCredentialHandleInput,
) -> tuple[LiveOrderRealCredentialHandleCheckResult, ...]:
    input_reasons = _input_reasons(handle_input)
    no_handle_value_reasons = _merge_reasons(
        _created_reasons(handle_input),
        _value_or_secret_reasons(handle_input),
        _identifier_or_metadata_reasons(handle_input),
        _display_or_save_reasons(handle_input),
    )
    env_reasons = _env_reasons(handle_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(handle_input)
    return (
        LiveOrderRealCredentialHandleCheckResult(
            name="credential handle input",
            passed=not input_reasons,
            sanitized_value="ready" if not input_reasons else ",".join(input_reasons),
            expected="HANDLE_CONTRACT_ONLY with boundary ready and requested",
        ),
        LiveOrderRealCredentialHandleCheckResult(
            name="no handle value or metadata",
            passed=not no_handle_value_reasons,
            sanitized_value="none"
            if not no_handle_value_reasons
            else ",".join(no_handle_value_reasons),
            expected="no real handle value identifier metadata display or save",
        ),
        LiveOrderRealCredentialHandleCheckResult(
            name="no env access",
            passed=not env_reasons,
            sanitized_value="none" if not env_reasons else ",".join(env_reasons),
            expected="no env or dotenv access",
        ),
        LiveOrderRealCredentialHandleCheckResult(
            name="no real signing or post",
            passed=not real_signing_or_post_reasons,
            sanitized_value="none"
            if not real_signing_or_post_reasons
            else ",".join(real_signing_or_post_reasons),
            expected="no real signing headers API post endpoint or live_order_once",
        ),
    )


def _input_reasons(
    handle_input: LiveOrderRealCredentialHandleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if handle_input.handle_mode != CredentialHandleMode.HANDLE_CONTRACT_ONLY.value:
        reasons.append("handle_mode_not_contract_only")
    if not handle_input.credential_boundary_ready:
        reasons.append("credential_boundary_ready_false")
    if not handle_input.handle_requested:
        reasons.append("handle_requested_false")
    return tuple(reasons)


def _created_reasons(
    handle_input: LiveOrderRealCredentialHandleInput,
) -> tuple[str, ...]:
    if handle_input.handle_created:
        return ("handle_created_unsafe",)
    return ()


def _value_or_secret_reasons(
    handle_input: LiveOrderRealCredentialHandleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "handle_contains_value",
        "handle_contains_secret",
        "handle_contains_token",
        "handle_contains_key_material",
    ):
        if getattr(handle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _identifier_or_metadata_reasons(
    handle_input: LiveOrderRealCredentialHandleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "handle_contains_identifier",
        "handle_length_available",
        "handle_hash_available",
        "handle_fingerprint_available",
        "handle_preview_available",
        "handle_prefix_available",
        "handle_suffix_available",
    ):
        if getattr(handle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _display_or_save_reasons(
    handle_input: LiveOrderRealCredentialHandleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "handle_value_displayed",
        "handle_value_saved",
        "handle_metadata_displayed",
        "handle_metadata_saved",
    ):
        if getattr(handle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    if not handle_input.safe_to_render:
        reasons.append("safe_to_render_false")
    if not handle_input.safe_to_serialize:
        reasons.append("safe_to_serialize_false")
    return tuple(reasons)


def _env_reasons(
    handle_input: LiveOrderRealCredentialHandleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("env_access_requested", "dotenv_access_requested"):
        if getattr(handle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_value_reasons(
    handle_input: LiveOrderRealCredentialHandleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("credential_values_provided", "credential_values_loaded"):
        if getattr(handle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_signing_or_post_reasons(
    handle_input: LiveOrderRealCredentialHandleInput,
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
        if getattr(handle_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _unsupported_reasons(
    handle_input: LiveOrderRealCredentialHandleInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if handle_input.retry_allowed:
        reasons.append("retry_allowed_unsupported")
    if handle_input.loop_allowed:
        reasons.append("loop_allowed_unsupported")
    return tuple(reasons)


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _validate_result_safety(result: LiveOrderRealCredentialHandleResult) -> None:
    unsafe_flags = (
        result.handle_created,
        result.handle_contains_value,
        result.handle_contains_secret,
        result.handle_contains_token,
        result.handle_contains_key_material,
        result.handle_contains_identifier,
        result.handle_metadata_exposed,
        result.handle_value_displayed,
        result.handle_value_saved,
        result.handle_metadata_displayed,
        result.handle_metadata_saved,
        result.env_access_requested,
        result.dotenv_access_requested,
        result.credential_values_provided,
        result.credential_values_loaded,
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
        raise LiveVerificationValidationError("credential handle result is unsafe")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
