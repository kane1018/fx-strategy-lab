"""Step 6G credential presence adapter skeleton, no env and no real check.

This module adapts operator-provided presence-result metadata into a safe
adapter-ready contract. It does not read env, attach or execute a real checker,
store sentinel text, generate signatures or header values, call APIs, or execute
HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

CREDENTIAL_PRESENCE_ADAPTER_RECOMMENDED_NEXT_STEP = (
    "future_real_credential_presence_check_must_be_a_separate_step"
)


class LiveOrderRealCredentialPresenceAdapterStatus(str, Enum):
    CREDENTIAL_PRESENCE_ADAPTER_READY_NO_ENV_NO_REAL_CHECK = (
        "CREDENTIAL_PRESENCE_ADAPTER_READY_NO_ENV_NO_REAL_CHECK"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_INPUT = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_INPUT"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_OPERATOR_RESULT = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_OPERATOR_RESULT"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_STALE_OR_REUSED_RESULT = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_STALE_OR_REUSED_RESULT"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_SENTINEL_EXPOSURE = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_SENTINEL_EXPOSURE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_CREDENTIAL_VALUE = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_CREDENTIAL_VALUE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_CREDENTIAL_METADATA = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_CREDENTIAL_METADATA"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_ENV_ACCESS = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_ENV_ACCESS"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_REAL_CHECKER = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_REAL_CHECKER"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_BROAD_PROPAGATION = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_BROAD_PROPAGATION"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_REAL_SIGNING_OR_POST = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_REAL_SIGNING_OR_POST"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_DISPLAY_OR_SAVE = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_DISPLAY_OR_SAVE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_UNSUPPORTED = (
        "BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_UNSUPPORTED"
    )


class LiveOrderRealCredentialPresenceAdapterMode(str, Enum):
    PRESENCE_ADAPTER_SKELETON_ONLY = "PRESENCE_ADAPTER_SKELETON_ONLY"


CredentialPresenceAdapterStatus = LiveOrderRealCredentialPresenceAdapterStatus
CredentialPresenceAdapterMode = LiveOrderRealCredentialPresenceAdapterMode


@dataclass(frozen=True)
class LiveOrderRealCredentialPresenceAdapterInput:
    adapter_mode: str = CredentialPresenceAdapterMode.PRESENCE_ADAPTER_SKELETON_ONLY.value
    credential_presence_check_ready: bool = True
    credential_boundary_ready: bool = True
    credential_handle_ready: bool = True
    credential_injection_ready: bool = True
    operator_provided_presence_result: bool = True
    operator_presence_result_is_boolean_only: bool = True
    operator_presence_result_fresh: bool = True
    operator_presence_result_reused: bool = False
    operator_presence_result_stale: bool = False
    operator_presence_result_previous_turn: bool = False
    presence_result_adapted: bool = True
    presence_result_saved: bool = False
    presence_result_displayed: bool = False
    presence_result_broadly_propagated: bool = False
    sentinel_value_present: bool = False
    sentinel_value_displayed: bool = False
    sentinel_value_saved: bool = False
    sentinel_hash_available: bool = False
    sentinel_fingerprint_available: bool = False
    sentinel_length_available: bool = False
    credential_values_present: bool = False
    credential_metadata_present: bool = False
    actual_environment_presence_check_performed: bool = False
    env_access_requested: bool = False
    dotenv_access_requested: bool = False
    printenv_requested: bool = False
    real_checker_attached: bool = False
    real_checker_executed: bool = False
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
        _require_non_empty("adapter_mode", self.adapter_mode)
        _validate_bool_fields(
            self,
            (
                "credential_presence_check_ready",
                "credential_boundary_ready",
                "credential_handle_ready",
                "credential_injection_ready",
                "operator_provided_presence_result",
                "operator_presence_result_is_boolean_only",
                "operator_presence_result_fresh",
                "operator_presence_result_reused",
                "operator_presence_result_stale",
                "operator_presence_result_previous_turn",
                "presence_result_adapted",
                "presence_result_saved",
                "presence_result_displayed",
                "presence_result_broadly_propagated",
                "sentinel_value_present",
                "sentinel_value_displayed",
                "sentinel_value_saved",
                "sentinel_hash_available",
                "sentinel_fingerprint_available",
                "sentinel_length_available",
                "credential_values_present",
                "credential_metadata_present",
                "actual_environment_presence_check_performed",
                "env_access_requested",
                "dotenv_access_requested",
                "printenv_requested",
                "real_checker_attached",
                "real_checker_executed",
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
class LiveOrderRealCredentialPresenceAdapterCheckResult:
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
class LiveOrderRealCredentialPresenceAdapterResult:
    status: LiveOrderRealCredentialPresenceAdapterStatus
    credential_presence_adapter_ready: bool
    adapter_mode: str
    credential_presence_check_ready: bool
    credential_boundary_ready: bool
    credential_handle_ready: bool
    credential_injection_ready: bool
    operator_provided_presence_result: bool
    operator_presence_result_is_boolean_only: bool
    operator_presence_result_fresh: bool
    operator_presence_result_reused: bool
    operator_presence_result_stale: bool
    operator_presence_result_previous_turn: bool
    presence_result_adapted: bool
    presence_result_saved: bool
    presence_result_displayed: bool
    presence_result_broadly_propagated: bool
    sentinel_value_present: bool
    sentinel_value_displayed: bool
    sentinel_value_saved: bool
    sentinel_hash_available: bool
    sentinel_fingerprint_available: bool
    sentinel_length_available: bool
    credential_values_present: bool
    credential_metadata_present: bool
    actual_environment_presence_check_performed: bool
    env_access_requested: bool
    dotenv_access_requested: bool
    printenv_requested: bool
    real_checker_attached: bool
    real_checker_executed: bool
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
    check_results: tuple[LiveOrderRealCredentialPresenceAdapterCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealCredentialPresenceAdapterStatus):
            raise LiveVerificationValidationError(
                "status must be credential presence adapter status",
            )
        _require_non_empty("adapter_mode", self.adapter_mode)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "credential_presence_adapter_ready",
                "credential_presence_check_ready",
                "credential_boundary_ready",
                "credential_handle_ready",
                "credential_injection_ready",
                "operator_provided_presence_result",
                "operator_presence_result_is_boolean_only",
                "operator_presence_result_fresh",
                "operator_presence_result_reused",
                "operator_presence_result_stale",
                "operator_presence_result_previous_turn",
                "presence_result_adapted",
                "presence_result_saved",
                "presence_result_displayed",
                "presence_result_broadly_propagated",
                "sentinel_value_present",
                "sentinel_value_displayed",
                "sentinel_value_saved",
                "sentinel_hash_available",
                "sentinel_fingerprint_available",
                "sentinel_length_available",
                "credential_values_present",
                "credential_metadata_present",
                "actual_environment_presence_check_performed",
                "env_access_requested",
                "dotenv_access_requested",
                "printenv_requested",
                "real_checker_attached",
                "real_checker_executed",
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


def build_live_order_real_credential_presence_adapter(
    *,
    input_snapshot: LiveOrderRealCredentialPresenceAdapterInput | None = None,
) -> LiveOrderRealCredentialPresenceAdapterResult:
    """Build a presence adapter skeleton without env, values, or a real checker."""
    adapter_input = input_snapshot or LiveOrderRealCredentialPresenceAdapterInput()

    input_reasons = _input_reasons(adapter_input)
    operator_reasons = _operator_result_reasons(adapter_input)
    stale_reasons = _stale_or_reused_result_reasons(adapter_input)
    sentinel_exposure_reasons = _sentinel_exposure_reasons(adapter_input)
    credential_value_reasons = _credential_value_reasons(adapter_input)
    credential_metadata_reasons = _credential_metadata_reasons(adapter_input)
    env_reasons = _env_reasons(adapter_input)
    real_checker_reasons = _real_checker_reasons(adapter_input)
    broad_reasons = _broad_propagation_reasons(adapter_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(adapter_input)
    display_reasons = _display_or_save_reasons(adapter_input)
    unsupported_reasons = _unsupported_reasons(adapter_input)

    if input_reasons:
        status = CredentialPresenceAdapterStatus.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_INPUT
        primary_reasons = input_reasons
    elif operator_reasons:
        status = (
            CredentialPresenceAdapterStatus
            .BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_OPERATOR_RESULT
        )
        primary_reasons = operator_reasons
    elif stale_reasons:
        status = (
            CredentialPresenceAdapterStatus
            .BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_STALE_OR_REUSED_RESULT
        )
        primary_reasons = stale_reasons
    elif sentinel_exposure_reasons:
        status = (
            CredentialPresenceAdapterStatus
            .BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_SENTINEL_EXPOSURE
        )
        primary_reasons = sentinel_exposure_reasons
    elif credential_value_reasons:
        status = (
            CredentialPresenceAdapterStatus
            .BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_CREDENTIAL_VALUE
        )
        primary_reasons = credential_value_reasons
    elif credential_metadata_reasons:
        status = (
            CredentialPresenceAdapterStatus
            .BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_CREDENTIAL_METADATA
        )
        primary_reasons = credential_metadata_reasons
    elif env_reasons:
        status = (
            CredentialPresenceAdapterStatus
            .BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_ENV_ACCESS
        )
        primary_reasons = env_reasons
    elif real_checker_reasons:
        status = (
            CredentialPresenceAdapterStatus
            .BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_REAL_CHECKER
        )
        primary_reasons = real_checker_reasons
    elif broad_reasons:
        status = (
            CredentialPresenceAdapterStatus
            .BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_BROAD_PROPAGATION
        )
        primary_reasons = broad_reasons
    elif real_signing_or_post_reasons:
        status = (
            CredentialPresenceAdapterStatus
            .BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_REAL_SIGNING_OR_POST
        )
        primary_reasons = real_signing_or_post_reasons
    elif display_reasons:
        status = (
            CredentialPresenceAdapterStatus
            .BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_DISPLAY_OR_SAVE
        )
        primary_reasons = display_reasons
    elif unsupported_reasons:
        status = (
            CredentialPresenceAdapterStatus
            .BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_UNSUPPORTED
        )
        primary_reasons = unsupported_reasons
    else:
        status = (
            CredentialPresenceAdapterStatus
            .CREDENTIAL_PRESENCE_ADAPTER_READY_NO_ENV_NO_REAL_CHECK
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
        real_checker_reasons,
        broad_reasons,
        real_signing_or_post_reasons,
        display_reasons,
        unsupported_reasons,
    )
    ready = (
        status
        is CredentialPresenceAdapterStatus
        .CREDENTIAL_PRESENCE_ADAPTER_READY_NO_ENV_NO_REAL_CHECK
    )
    return LiveOrderRealCredentialPresenceAdapterResult(
        status=status,
        credential_presence_adapter_ready=ready,
        adapter_mode=adapter_input.adapter_mode,
        credential_presence_check_ready=adapter_input.credential_presence_check_ready,
        credential_boundary_ready=adapter_input.credential_boundary_ready,
        credential_handle_ready=adapter_input.credential_handle_ready,
        credential_injection_ready=adapter_input.credential_injection_ready,
        operator_provided_presence_result=adapter_input.operator_provided_presence_result,
        operator_presence_result_is_boolean_only=(
            adapter_input.operator_presence_result_is_boolean_only
        ),
        operator_presence_result_fresh=adapter_input.operator_presence_result_fresh,
        operator_presence_result_reused=False,
        operator_presence_result_stale=False,
        operator_presence_result_previous_turn=False,
        presence_result_adapted=adapter_input.presence_result_adapted,
        presence_result_saved=False,
        presence_result_displayed=False,
        presence_result_broadly_propagated=False,
        sentinel_value_present=False,
        sentinel_value_displayed=False,
        sentinel_value_saved=False,
        sentinel_hash_available=False,
        sentinel_fingerprint_available=False,
        sentinel_length_available=False,
        credential_values_present=False,
        credential_metadata_present=False,
        actual_environment_presence_check_performed=False,
        env_access_requested=False,
        dotenv_access_requested=False,
        printenv_requested=False,
        real_checker_attached=False,
        real_checker_executed=False,
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
        check_results=_build_check_results(adapter_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            CREDENTIAL_PRESENCE_ADAPTER_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_credential_presence_adapter_blockers_no_env_no_post"
        ),
    )


def render_live_order_real_credential_presence_adapter_markdown(
    result: LiveOrderRealCredentialPresenceAdapterResult,
) -> str:
    """Render sanitized credential presence adapter metadata only."""
    lines = [
        "# Step 6G Credential Presence Adapter Skeleton",
        "",
        "This credential presence adapter is skeleton-only.",
        "This credential presence adapter does not access env or .env.",
        "This credential presence adapter does not check the real environment.",
        "This credential presence adapter does not attach or execute a real checker.",
        "This credential presence adapter does not expose the sentinel value.",
        "This credential presence adapter does not expose credential metadata.",
        "This credential presence adapter does not generate real signatures.",
        "This credential presence adapter does not execute API calls.",
        "This credential presence adapter does not execute HTTP POST.",
        "This credential presence adapter does not call order endpoint.",
        "This credential presence adapter does not call live_order_once.",
        "Future real credential presence check must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- credential_presence_adapter_ready: "
            f"{_bool_text(result.credential_presence_adapter_ready)}"
        ),
        f"- adapter_mode: {result.adapter_mode}",
        (
            "- credential_presence_check_ready: "
            f"{_bool_text(result.credential_presence_check_ready)}"
        ),
        f"- credential_boundary_ready: {_bool_text(result.credential_boundary_ready)}",
        f"- credential_handle_ready: {_bool_text(result.credential_handle_ready)}",
        f"- credential_injection_ready: {_bool_text(result.credential_injection_ready)}",
        "",
        "## Operator Presence Result",
        (
            "- operator_provided_presence_result: "
            f"{_bool_text(result.operator_provided_presence_result)}"
        ),
        (
            "- operator_presence_result_is_boolean_only: "
            f"{_bool_text(result.operator_presence_result_is_boolean_only)}"
        ),
        (
            "- operator_presence_result_fresh: "
            f"{_bool_text(result.operator_presence_result_fresh)}"
        ),
        (
            "- operator_presence_result_reused: "
            f"{_bool_text(result.operator_presence_result_reused)}"
        ),
        (
            "- operator_presence_result_stale: "
            f"{_bool_text(result.operator_presence_result_stale)}"
        ),
        (
            "- operator_presence_result_previous_turn: "
            f"{_bool_text(result.operator_presence_result_previous_turn)}"
        ),
        f"- presence_result_adapted: {_bool_text(result.presence_result_adapted)}",
        "",
        "## Safety",
        f"- presence_result_saved: {_bool_text(result.presence_result_saved)}",
        f"- presence_result_displayed: {_bool_text(result.presence_result_displayed)}",
        (
            "- presence_result_broadly_propagated: "
            f"{_bool_text(result.presence_result_broadly_propagated)}"
        ),
        f"- sentinel_value_present: {_bool_text(result.sentinel_value_present)}",
        f"- credential_values_present: {_bool_text(result.credential_values_present)}",
        f"- credential_metadata_present: {_bool_text(result.credential_metadata_present)}",
        (
            "- actual_environment_presence_check_performed: "
            f"{_bool_text(result.actual_environment_presence_check_performed)}"
        ),
        f"- env_access_requested: {_bool_text(result.env_access_requested)}",
        f"- dotenv_access_requested: {_bool_text(result.dotenv_access_requested)}",
        f"- printenv_requested: {_bool_text(result.printenv_requested)}",
        f"- real_checker_attached: {_bool_text(result.real_checker_attached)}",
        f"- real_checker_executed: {_bool_text(result.real_checker_executed)}",
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
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
) -> tuple[LiveOrderRealCredentialPresenceAdapterCheckResult, ...]:
    input_reasons = _input_reasons(adapter_input)
    operator_reasons = _merge_reasons(
        _operator_result_reasons(adapter_input),
        _stale_or_reused_result_reasons(adapter_input),
    )
    no_value_or_env_reasons = _merge_reasons(
        _sentinel_exposure_reasons(adapter_input),
        _credential_value_reasons(adapter_input),
        _credential_metadata_reasons(adapter_input),
        _env_reasons(adapter_input),
        _real_checker_reasons(adapter_input),
        _broad_propagation_reasons(adapter_input),
        _display_or_save_reasons(adapter_input),
    )
    real_signing_or_post_reasons = _real_signing_or_post_reasons(adapter_input)
    return (
        LiveOrderRealCredentialPresenceAdapterCheckResult(
            name="credential presence adapter input",
            passed=not input_reasons,
            sanitized_value="ready" if not input_reasons else ",".join(input_reasons),
            expected="presence adapter skeleton mode with credential contracts ready",
        ),
        LiveOrderRealCredentialPresenceAdapterCheckResult(
            name="operator presence result",
            passed=not operator_reasons,
            sanitized_value="fresh" if not operator_reasons else ",".join(operator_reasons),
            expected="boolean-only fresh operator result adapted without reuse",
        ),
        LiveOrderRealCredentialPresenceAdapterCheckResult(
            name="no sentinel credential env real checker or broad propagation",
            passed=not no_value_or_env_reasons,
            sanitized_value="none"
            if not no_value_or_env_reasons
            else ",".join(no_value_or_env_reasons),
            expected="no sentinel values credential metadata env access or real checker",
        ),
        LiveOrderRealCredentialPresenceAdapterCheckResult(
            name="no real signing or post",
            passed=not real_signing_or_post_reasons,
            sanitized_value="none"
            if not real_signing_or_post_reasons
            else ",".join(real_signing_or_post_reasons),
            expected="no real signing headers API post endpoint or live_order_once",
        ),
    )


def _input_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        adapter_input.adapter_mode
        != CredentialPresenceAdapterMode.PRESENCE_ADAPTER_SKELETON_ONLY.value
    ):
        reasons.append("adapter_mode_not_presence_adapter_skeleton_only")
    for field_name in (
        "credential_presence_check_ready",
        "credential_boundary_ready",
        "credential_handle_ready",
        "credential_injection_ready",
    ):
        if not getattr(adapter_input, field_name):
            reasons.append(f"{field_name}_false")
    return tuple(reasons)


def _operator_result_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not adapter_input.operator_provided_presence_result:
        reasons.append("operator_provided_presence_result_false")
    if not adapter_input.operator_presence_result_is_boolean_only:
        reasons.append("operator_presence_result_is_boolean_only_false")
    if not adapter_input.presence_result_adapted:
        reasons.append("presence_result_adapted_false")
    return tuple(reasons)


def _stale_or_reused_result_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not adapter_input.operator_presence_result_fresh:
        reasons.append("operator_presence_result_fresh_false")
    for field_name in (
        "operator_presence_result_reused",
        "operator_presence_result_stale",
        "operator_presence_result_previous_turn",
    ):
        if getattr(adapter_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _sentinel_exposure_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
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
        if getattr(adapter_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_value_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
) -> tuple[str, ...]:
    if adapter_input.credential_values_present:
        return ("credential_values_present_unsafe",)
    return ()


def _credential_metadata_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
) -> tuple[str, ...]:
    if adapter_input.credential_metadata_present:
        return ("credential_metadata_present_unsafe",)
    return ()


def _env_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("env_access_requested", "dotenv_access_requested", "printenv_requested"):
        if getattr(adapter_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_checker_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "actual_environment_presence_check_performed",
        "real_checker_attached",
        "real_checker_executed",
    ):
        if getattr(adapter_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _broad_propagation_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("presence_result_saved", "presence_result_broadly_propagated"):
        if getattr(adapter_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_signing_or_post_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
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
        if getattr(adapter_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _display_or_save_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if adapter_input.presence_result_displayed:
        reasons.append("presence_result_displayed_unsafe")
    if not adapter_input.safe_to_render:
        reasons.append("safe_to_render_false")
    if not adapter_input.safe_to_serialize:
        reasons.append("safe_to_serialize_false")
    return tuple(reasons)


def _unsupported_reasons(
    adapter_input: LiveOrderRealCredentialPresenceAdapterInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if adapter_input.retry_allowed:
        reasons.append("retry_allowed_unsupported")
    if adapter_input.loop_allowed:
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
    result: LiveOrderRealCredentialPresenceAdapterResult,
) -> None:
    unsafe_flags = (
        result.operator_presence_result_reused,
        result.operator_presence_result_stale,
        result.operator_presence_result_previous_turn,
        result.presence_result_saved,
        result.presence_result_displayed,
        result.presence_result_broadly_propagated,
        result.sentinel_value_present,
        result.sentinel_value_displayed,
        result.sentinel_value_saved,
        result.sentinel_hash_available,
        result.sentinel_fingerprint_available,
        result.sentinel_length_available,
        result.credential_values_present,
        result.credential_metadata_present,
        result.actual_environment_presence_check_performed,
        result.env_access_requested,
        result.dotenv_access_requested,
        result.printenv_requested,
        result.real_checker_attached,
        result.real_checker_executed,
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
            "credential presence adapter result is unsafe",
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
