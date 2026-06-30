"""Step 6G credential presence check skeleton, operator-provided only.

This module turns operator-provided boolean/sentinel metadata into a safe
presence-ready contract. It does not read env, check real credential presence,
store sentinel text, generate signatures or header values, call APIs, or execute
HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

CREDENTIAL_PRESENCE_CHECK_RECOMMENDED_NEXT_STEP = (
    "future_real_credential_presence_check_must_be_a_separate_step"
)


class LiveOrderRealCredentialPresenceCheckStatus(str, Enum):
    CREDENTIAL_PRESENCE_CHECK_READY_OPERATOR_PROVIDED_NO_ENV = (
        "CREDENTIAL_PRESENCE_CHECK_READY_OPERATOR_PROVIDED_NO_ENV"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECK_INPUT = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECK_INPUT"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECK_OPERATOR_ASSERTION = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECK_OPERATOR_ASSERTION"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECK_STALE_OR_REUSED_SENTINEL = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECK_STALE_OR_REUSED_SENTINEL"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECK_SENTINEL_EXPOSURE = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECK_SENTINEL_EXPOSURE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECK_CREDENTIAL_VALUE = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECK_CREDENTIAL_VALUE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECK_CREDENTIAL_METADATA = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECK_CREDENTIAL_METADATA"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECK_ENV_ACCESS = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECK_ENV_ACCESS"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECK_BROAD_PROPAGATION = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECK_BROAD_PROPAGATION"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECK_REAL_SIGNING_OR_POST = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECK_REAL_SIGNING_OR_POST"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECK_DISPLAY_OR_SAVE = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECK_DISPLAY_OR_SAVE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECK_UNSUPPORTED = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECK_UNSUPPORTED"
    )


class LiveOrderRealCredentialPresenceCheckMode(str, Enum):
    OPERATOR_PROVIDED_SENTINEL_ONLY = "OPERATOR_PROVIDED_SENTINEL_ONLY"


CredentialPresenceCheckStatus = LiveOrderRealCredentialPresenceCheckStatus
CredentialPresenceCheckMode = LiveOrderRealCredentialPresenceCheckMode


@dataclass(frozen=True)
class LiveOrderRealCredentialPresenceCheckInput:
    presence_check_mode: str = (
        CredentialPresenceCheckMode.OPERATOR_PROVIDED_SENTINEL_ONLY.value
    )
    credential_boundary_ready: bool = True
    credential_handle_ready: bool = True
    credential_injection_ready: bool = True
    operator_assertion_provided: bool = True
    operator_assertion_is_boolean_only: bool = True
    operator_sentinel_received: bool = True
    operator_sentinel_fresh: bool = True
    operator_sentinel_reused: bool = False
    operator_sentinel_stale: bool = False
    operator_sentinel_previous_turn: bool = False
    sentinel_value_present: bool = False
    sentinel_value_displayed: bool = False
    sentinel_value_saved: bool = False
    sentinel_hash_available: bool = False
    sentinel_fingerprint_available: bool = False
    sentinel_length_available: bool = False
    credential_values_present: bool = False
    credential_metadata_present: bool = False
    credential_presence_checked_against_environment: bool = False
    env_access_requested: bool = False
    dotenv_access_requested: bool = False
    printenv_requested: bool = False
    presence_result_broadly_propagated: bool = False
    presence_result_saved: bool = False
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
        _require_non_empty("presence_check_mode", self.presence_check_mode)
        _validate_bool_fields(
            self,
            (
                "credential_boundary_ready",
                "credential_handle_ready",
                "credential_injection_ready",
                "operator_assertion_provided",
                "operator_assertion_is_boolean_only",
                "operator_sentinel_received",
                "operator_sentinel_fresh",
                "operator_sentinel_reused",
                "operator_sentinel_stale",
                "operator_sentinel_previous_turn",
                "sentinel_value_present",
                "sentinel_value_displayed",
                "sentinel_value_saved",
                "sentinel_hash_available",
                "sentinel_fingerprint_available",
                "sentinel_length_available",
                "credential_values_present",
                "credential_metadata_present",
                "credential_presence_checked_against_environment",
                "env_access_requested",
                "dotenv_access_requested",
                "printenv_requested",
                "presence_result_broadly_propagated",
                "presence_result_saved",
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
class LiveOrderRealCredentialPresenceCheckCheckResult:
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
class LiveOrderRealCredentialPresenceCheckResult:
    status: LiveOrderRealCredentialPresenceCheckStatus
    credential_presence_check_ready: bool
    presence_check_mode: str
    credential_boundary_ready: bool
    credential_handle_ready: bool
    credential_injection_ready: bool
    operator_assertion_provided: bool
    operator_assertion_is_boolean_only: bool
    operator_sentinel_received: bool
    operator_sentinel_fresh: bool
    operator_sentinel_reused: bool
    operator_sentinel_stale: bool
    operator_sentinel_previous_turn: bool
    sentinel_value_present: bool
    sentinel_value_displayed: bool
    sentinel_value_saved: bool
    sentinel_hash_available: bool
    sentinel_fingerprint_available: bool
    sentinel_length_available: bool
    credential_values_present: bool
    credential_metadata_present: bool
    credential_presence_checked_against_environment: bool
    env_access_requested: bool
    dotenv_access_requested: bool
    printenv_requested: bool
    presence_result_broadly_propagated: bool
    presence_result_saved: bool
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
    check_results: tuple[LiveOrderRealCredentialPresenceCheckCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealCredentialPresenceCheckStatus):
            raise LiveVerificationValidationError(
                "status must be credential presence check status",
            )
        _require_non_empty("presence_check_mode", self.presence_check_mode)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "credential_presence_check_ready",
                "credential_boundary_ready",
                "credential_handle_ready",
                "credential_injection_ready",
                "operator_assertion_provided",
                "operator_assertion_is_boolean_only",
                "operator_sentinel_received",
                "operator_sentinel_fresh",
                "operator_sentinel_reused",
                "operator_sentinel_stale",
                "operator_sentinel_previous_turn",
                "sentinel_value_present",
                "sentinel_value_displayed",
                "sentinel_value_saved",
                "sentinel_hash_available",
                "sentinel_fingerprint_available",
                "sentinel_length_available",
                "credential_values_present",
                "credential_metadata_present",
                "credential_presence_checked_against_environment",
                "env_access_requested",
                "dotenv_access_requested",
                "printenv_requested",
                "presence_result_broadly_propagated",
                "presence_result_saved",
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


def build_live_order_real_credential_presence_check(
    *,
    input_snapshot: LiveOrderRealCredentialPresenceCheckInput | None = None,
) -> LiveOrderRealCredentialPresenceCheckResult:
    """Build an operator-provided presence skeleton without env or value access."""
    presence_input = input_snapshot or LiveOrderRealCredentialPresenceCheckInput()

    input_reasons = _input_reasons(presence_input)
    operator_reasons = _operator_assertion_reasons(presence_input)
    stale_reasons = _stale_or_reused_sentinel_reasons(presence_input)
    sentinel_exposure_reasons = _sentinel_exposure_reasons(presence_input)
    credential_value_reasons = _credential_value_reasons(presence_input)
    credential_metadata_reasons = _credential_metadata_reasons(presence_input)
    env_reasons = _env_reasons(presence_input)
    broad_reasons = _broad_propagation_reasons(presence_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(presence_input)
    display_reasons = _display_or_save_reasons(presence_input)
    unsupported_reasons = _unsupported_reasons(presence_input)

    if input_reasons:
        status = CredentialPresenceCheckStatus.BLOCKED_CREDENTIAL_PRESENCE_CHECK_INPUT
        primary_reasons = input_reasons
    elif operator_reasons:
        status = (
            CredentialPresenceCheckStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECK_OPERATOR_ASSERTION
        )
        primary_reasons = operator_reasons
    elif stale_reasons:
        status = (
            CredentialPresenceCheckStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECK_STALE_OR_REUSED_SENTINEL
        )
        primary_reasons = stale_reasons
    elif sentinel_exposure_reasons:
        status = (
            CredentialPresenceCheckStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECK_SENTINEL_EXPOSURE
        )
        primary_reasons = sentinel_exposure_reasons
    elif credential_value_reasons:
        status = (
            CredentialPresenceCheckStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECK_CREDENTIAL_VALUE
        )
        primary_reasons = credential_value_reasons
    elif credential_metadata_reasons:
        status = (
            CredentialPresenceCheckStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECK_CREDENTIAL_METADATA
        )
        primary_reasons = credential_metadata_reasons
    elif env_reasons:
        status = (
            CredentialPresenceCheckStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECK_ENV_ACCESS
        )
        primary_reasons = env_reasons
    elif broad_reasons:
        status = (
            CredentialPresenceCheckStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECK_BROAD_PROPAGATION
        )
        primary_reasons = broad_reasons
    elif real_signing_or_post_reasons:
        status = (
            CredentialPresenceCheckStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECK_REAL_SIGNING_OR_POST
        )
        primary_reasons = real_signing_or_post_reasons
    elif display_reasons:
        status = (
            CredentialPresenceCheckStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECK_DISPLAY_OR_SAVE
        )
        primary_reasons = display_reasons
    elif unsupported_reasons:
        status = (
            CredentialPresenceCheckStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECK_UNSUPPORTED
        )
        primary_reasons = unsupported_reasons
    else:
        status = (
            CredentialPresenceCheckStatus
            .CREDENTIAL_PRESENCE_CHECK_READY_OPERATOR_PROVIDED_NO_ENV
        )
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        input_reasons,
        operator_reasons,
        stale_reasons,
        sentinel_exposure_reasons,
        credential_value_reasons,
        credential_metadata_reasons,
        env_reasons,
        broad_reasons,
        real_signing_or_post_reasons,
        display_reasons,
        unsupported_reasons,
    )
    ready = (
        status
        is CredentialPresenceCheckStatus
        .CREDENTIAL_PRESENCE_CHECK_READY_OPERATOR_PROVIDED_NO_ENV
    )
    return LiveOrderRealCredentialPresenceCheckResult(
        status=status,
        credential_presence_check_ready=ready,
        presence_check_mode=presence_input.presence_check_mode,
        credential_boundary_ready=presence_input.credential_boundary_ready,
        credential_handle_ready=presence_input.credential_handle_ready,
        credential_injection_ready=presence_input.credential_injection_ready,
        operator_assertion_provided=presence_input.operator_assertion_provided,
        operator_assertion_is_boolean_only=(
            presence_input.operator_assertion_is_boolean_only
        ),
        operator_sentinel_received=presence_input.operator_sentinel_received,
        operator_sentinel_fresh=presence_input.operator_sentinel_fresh,
        operator_sentinel_reused=False,
        operator_sentinel_stale=False,
        operator_sentinel_previous_turn=False,
        sentinel_value_present=False,
        sentinel_value_displayed=False,
        sentinel_value_saved=False,
        sentinel_hash_available=False,
        sentinel_fingerprint_available=False,
        sentinel_length_available=False,
        credential_values_present=False,
        credential_metadata_present=False,
        credential_presence_checked_against_environment=False,
        env_access_requested=False,
        dotenv_access_requested=False,
        printenv_requested=False,
        presence_result_broadly_propagated=False,
        presence_result_saved=False,
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
        check_results=_build_check_results(presence_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            CREDENTIAL_PRESENCE_CHECK_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_credential_presence_check_blockers_no_env_no_post"
        ),
    )


def render_live_order_real_credential_presence_check_markdown(
    result: LiveOrderRealCredentialPresenceCheckResult,
) -> str:
    """Render sanitized credential presence skeleton metadata only."""
    lines = [
        "# Step 6G Credential Presence Check Skeleton",
        "",
        "This credential presence check is skeleton-only.",
        "This credential presence check does not access env or .env.",
        "This credential presence check does not check the real environment.",
        "This credential presence check does not expose the sentinel value.",
        "This credential presence check does not expose credential metadata.",
        "This credential presence check does not generate real signatures.",
        "This credential presence check does not execute API calls.",
        "This credential presence check does not execute HTTP POST.",
        "This credential presence check does not call order endpoint.",
        "This credential presence check does not call live_order_once.",
        "Future real credential presence check must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- credential_presence_check_ready: "
            f"{_bool_text(result.credential_presence_check_ready)}"
        ),
        f"- presence_check_mode: {result.presence_check_mode}",
        f"- credential_boundary_ready: {_bool_text(result.credential_boundary_ready)}",
        f"- credential_handle_ready: {_bool_text(result.credential_handle_ready)}",
        f"- credential_injection_ready: {_bool_text(result.credential_injection_ready)}",
        "",
        "## Operator Assertion",
        (
            "- operator_assertion_provided: "
            f"{_bool_text(result.operator_assertion_provided)}"
        ),
        (
            "- operator_assertion_is_boolean_only: "
            f"{_bool_text(result.operator_assertion_is_boolean_only)}"
        ),
        f"- operator_sentinel_received: {_bool_text(result.operator_sentinel_received)}",
        f"- operator_sentinel_fresh: {_bool_text(result.operator_sentinel_fresh)}",
        f"- operator_sentinel_reused: {_bool_text(result.operator_sentinel_reused)}",
        f"- operator_sentinel_stale: {_bool_text(result.operator_sentinel_stale)}",
        (
            "- operator_sentinel_previous_turn: "
            f"{_bool_text(result.operator_sentinel_previous_turn)}"
        ),
        "",
        "## Safety",
        f"- sentinel_value_present: {_bool_text(result.sentinel_value_present)}",
        f"- credential_values_present: {_bool_text(result.credential_values_present)}",
        f"- credential_metadata_present: {_bool_text(result.credential_metadata_present)}",
        (
            "- credential_presence_checked_against_environment: "
            f"{_bool_text(result.credential_presence_checked_against_environment)}"
        ),
        f"- env_access_requested: {_bool_text(result.env_access_requested)}",
        f"- dotenv_access_requested: {_bool_text(result.dotenv_access_requested)}",
        f"- printenv_requested: {_bool_text(result.printenv_requested)}",
        (
            "- presence_result_broadly_propagated: "
            f"{_bool_text(result.presence_result_broadly_propagated)}"
        ),
        f"- presence_result_saved: {_bool_text(result.presence_result_saved)}",
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
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
) -> tuple[LiveOrderRealCredentialPresenceCheckCheckResult, ...]:
    input_reasons = _input_reasons(presence_input)
    operator_reasons = _merge_reasons(
        _operator_assertion_reasons(presence_input),
        _stale_or_reused_sentinel_reasons(presence_input),
        _sentinel_exposure_reasons(presence_input),
    )
    no_credential_reasons = _merge_reasons(
        _credential_value_reasons(presence_input),
        _credential_metadata_reasons(presence_input),
        _env_reasons(presence_input),
        _broad_propagation_reasons(presence_input),
        _display_or_save_reasons(presence_input),
    )
    real_signing_or_post_reasons = _real_signing_or_post_reasons(presence_input)
    return (
        LiveOrderRealCredentialPresenceCheckCheckResult(
            name="credential presence input",
            passed=not input_reasons,
            sanitized_value="ready" if not input_reasons else ",".join(input_reasons),
            expected="operator provided sentinel mode with credential contracts ready",
        ),
        LiveOrderRealCredentialPresenceCheckCheckResult(
            name="operator sentinel freshness",
            passed=not operator_reasons,
            sanitized_value="fresh" if not operator_reasons else ",".join(operator_reasons),
            expected="boolean assertion fresh sentinel and no sentinel exposure",
        ),
        LiveOrderRealCredentialPresenceCheckCheckResult(
            name="no credential value metadata env or broad propagation",
            passed=not no_credential_reasons,
            sanitized_value="none"
            if not no_credential_reasons
            else ",".join(no_credential_reasons),
            expected="no credential values metadata real env check or saved presence result",
        ),
        LiveOrderRealCredentialPresenceCheckCheckResult(
            name="no real signing or post",
            passed=not real_signing_or_post_reasons,
            sanitized_value="none"
            if not real_signing_or_post_reasons
            else ",".join(real_signing_or_post_reasons),
            expected="no real signing headers API post endpoint or live_order_once",
        ),
    )


def _input_reasons(
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        presence_input.presence_check_mode
        != CredentialPresenceCheckMode.OPERATOR_PROVIDED_SENTINEL_ONLY.value
    ):
        reasons.append("presence_check_mode_not_operator_provided_sentinel_only")
    if not presence_input.credential_boundary_ready:
        reasons.append("credential_boundary_ready_false")
    if not presence_input.credential_handle_ready:
        reasons.append("credential_handle_ready_false")
    if not presence_input.credential_injection_ready:
        reasons.append("credential_injection_ready_false")
    return tuple(reasons)


def _operator_assertion_reasons(
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not presence_input.operator_assertion_provided:
        reasons.append("operator_assertion_provided_false")
    if not presence_input.operator_assertion_is_boolean_only:
        reasons.append("operator_assertion_is_boolean_only_false")
    if not presence_input.operator_sentinel_received:
        reasons.append("operator_sentinel_received_false")
    return tuple(reasons)


def _stale_or_reused_sentinel_reasons(
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not presence_input.operator_sentinel_fresh:
        reasons.append("operator_sentinel_fresh_false")
    for field_name in (
        "operator_sentinel_reused",
        "operator_sentinel_stale",
        "operator_sentinel_previous_turn",
    ):
        if getattr(presence_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _sentinel_exposure_reasons(
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "sentinel_value_present",
        "sentinel_value_displayed",
        "sentinel_value_saved",
        "sentinel_hash_available",
        "sentinel_fingerprint_available",
        "sentinel_length_available",
    ):
        if getattr(presence_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_value_reasons(
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
) -> tuple[str, ...]:
    if presence_input.credential_values_present:
        return ("credential_values_present_unsafe",)
    return ()


def _credential_metadata_reasons(
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
) -> tuple[str, ...]:
    if presence_input.credential_metadata_present:
        return ("credential_metadata_present_unsafe",)
    return ()


def _env_reasons(
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_presence_checked_against_environment",
        "env_access_requested",
        "dotenv_access_requested",
        "printenv_requested",
    ):
        if getattr(presence_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _broad_propagation_reasons(
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("presence_result_broadly_propagated", "presence_result_saved"):
        if getattr(presence_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_signing_or_post_reasons(
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
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
        if getattr(presence_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _display_or_save_reasons(
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not presence_input.safe_to_render:
        reasons.append("safe_to_render_false")
    if not presence_input.safe_to_serialize:
        reasons.append("safe_to_serialize_false")
    return tuple(reasons)


def _unsupported_reasons(
    presence_input: LiveOrderRealCredentialPresenceCheckInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if presence_input.retry_allowed:
        reasons.append("retry_allowed_unsupported")
    if presence_input.loop_allowed:
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
    result: LiveOrderRealCredentialPresenceCheckResult,
) -> None:
    unsafe_flags = (
        result.operator_sentinel_reused,
        result.operator_sentinel_stale,
        result.operator_sentinel_previous_turn,
        result.sentinel_value_present,
        result.sentinel_value_displayed,
        result.sentinel_value_saved,
        result.sentinel_hash_available,
        result.sentinel_fingerprint_available,
        result.sentinel_length_available,
        result.credential_values_present,
        result.credential_metadata_present,
        result.credential_presence_checked_against_environment,
        result.env_access_requested,
        result.dotenv_access_requested,
        result.printenv_requested,
        result.presence_result_broadly_propagated,
        result.presence_result_saved,
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
            "credential presence check result is unsafe",
        )


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
