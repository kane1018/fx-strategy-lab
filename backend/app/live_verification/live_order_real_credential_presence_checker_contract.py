"""Step 6G real credential presence checker contract, no env and no real check.

This module defines the contract boundary for a future real credential presence
checker. It does not read env, attach or execute a real checker, store
credential values or metadata, generate signatures or header values, call APIs,
or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

CREDENTIAL_PRESENCE_CHECKER_CONTRACT_RECOMMENDED_NEXT_STEP = (
    "future_real_credential_presence_check_implementation_must_be_a_separate_step"
)
UNSUPPORTED_CHECKER_CONTRACT_MODE_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealCredentialPresenceCheckerContractStatus(str, Enum):
    CREDENTIAL_PRESENCE_CHECKER_CONTRACT_READY_NO_ENV_NO_REAL_CHECK = (
        "CREDENTIAL_PRESENCE_CHECKER_CONTRACT_READY_NO_ENV_NO_REAL_CHECK"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_INPUT = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_INPUT"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_CHECKER_PRESENT = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_CHECKER_PRESENT"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_CHECK_EXECUTED = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_CHECK_EXECUTED"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_ENV_ACCESS = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_ENV_ACCESS"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_CREDENTIAL_VALUE = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_CREDENTIAL_VALUE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_CREDENTIAL_METADATA = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_CREDENTIAL_METADATA"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_RESULT_EXPOSURE = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_RESULT_EXPOSURE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_RESULT_UNKNOWN_OR_FAILED = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_RESULT_UNKNOWN_OR_FAILED"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_SIGNING_OR_POST = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_SIGNING_OR_POST"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_DISPLAY_OR_SAVE = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_DISPLAY_OR_SAVE"
    )
    BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_UNSUPPORTED = (
        "BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_UNSUPPORTED"
    )


class LiveOrderRealCredentialPresenceCheckerContractMode(str, Enum):
    CHECKER_CONTRACT_ONLY = "CHECKER_CONTRACT_ONLY"


CredentialPresenceCheckerContractStatus = (
    LiveOrderRealCredentialPresenceCheckerContractStatus
)
CredentialPresenceCheckerContractMode = LiveOrderRealCredentialPresenceCheckerContractMode


@dataclass(frozen=True)
class LiveOrderRealCredentialPresenceCheckerContractInput:
    checker_contract_mode: str = (
        CredentialPresenceCheckerContractMode.CHECKER_CONTRACT_ONLY.value
    )
    credential_presence_adapter_ready: bool = True
    credential_presence_check_ready: bool = True
    credential_boundary_ready: bool = True
    credential_handle_ready: bool = True
    credential_injection_ready: bool = True
    checker_contract_requested: bool = True
    checker_contract_ready_requested: bool = True
    real_checker_implementation_present: bool = False
    real_checker_attached: bool = False
    real_checker_executed: bool = False
    actual_environment_presence_check_performed: bool = False
    env_access_required: bool = True
    env_access_allowed: bool = False
    env_access_requested: bool = False
    dotenv_access_requested: bool = False
    printenv_requested: bool = False
    credential_values_available: bool = False
    credential_values_read: bool = False
    credential_values_displayed: bool = False
    credential_values_saved: bool = False
    credential_metadata_available: bool = False
    credential_metadata_displayed: bool = False
    credential_metadata_saved: bool = False
    checker_result_available: bool = False
    checker_result_is_boolean_only: bool = True
    checker_result_saved: bool = False
    checker_result_displayed: bool = False
    checker_result_broadly_propagated: bool = False
    checker_result_unknown: bool = False
    checker_result_failed: bool = False
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
        _require_non_empty("checker_contract_mode", self.checker_contract_mode)
        _validate_bool_fields(
            self,
            (
                "credential_presence_adapter_ready",
                "credential_presence_check_ready",
                "credential_boundary_ready",
                "credential_handle_ready",
                "credential_injection_ready",
                "checker_contract_requested",
                "checker_contract_ready_requested",
                "real_checker_implementation_present",
                "real_checker_attached",
                "real_checker_executed",
                "actual_environment_presence_check_performed",
                "env_access_required",
                "env_access_allowed",
                "env_access_requested",
                "dotenv_access_requested",
                "printenv_requested",
                "credential_values_available",
                "credential_values_read",
                "credential_values_displayed",
                "credential_values_saved",
                "credential_metadata_available",
                "credential_metadata_displayed",
                "credential_metadata_saved",
                "checker_result_available",
                "checker_result_is_boolean_only",
                "checker_result_saved",
                "checker_result_displayed",
                "checker_result_broadly_propagated",
                "checker_result_unknown",
                "checker_result_failed",
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
class LiveOrderRealCredentialPresenceCheckerContractCheckResult:
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
class LiveOrderRealCredentialPresenceCheckerContractResult:
    status: LiveOrderRealCredentialPresenceCheckerContractStatus
    credential_presence_checker_contract_ready: bool
    checker_contract_mode: str
    unsupported_checker_contract_mode_present: bool
    raw_checker_contract_mode_displayed: bool
    raw_checker_contract_mode_saved: bool
    credential_presence_adapter_ready: bool
    credential_presence_check_ready: bool
    credential_boundary_ready: bool
    credential_handle_ready: bool
    credential_injection_ready: bool
    checker_contract_requested: bool
    checker_contract_ready_requested: bool
    real_checker_implementation_present: bool
    real_checker_attached: bool
    real_checker_executed: bool
    actual_environment_presence_check_performed: bool
    env_access_required: bool
    env_access_allowed: bool
    env_access_requested: bool
    dotenv_access_requested: bool
    printenv_requested: bool
    credential_values_available: bool
    credential_values_read: bool
    credential_values_displayed: bool
    credential_values_saved: bool
    credential_metadata_available: bool
    credential_metadata_displayed: bool
    credential_metadata_saved: bool
    checker_result_available: bool
    checker_result_is_boolean_only: bool
    checker_result_saved: bool
    checker_result_displayed: bool
    checker_result_broadly_propagated: bool
    checker_result_unknown: bool
    checker_result_failed: bool
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
    check_results: tuple[LiveOrderRealCredentialPresenceCheckerContractCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealCredentialPresenceCheckerContractStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be credential presence checker contract status",
            )
        _require_non_empty("checker_contract_mode", self.checker_contract_mode)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "credential_presence_checker_contract_ready",
                "unsupported_checker_contract_mode_present",
                "raw_checker_contract_mode_displayed",
                "raw_checker_contract_mode_saved",
                "credential_presence_adapter_ready",
                "credential_presence_check_ready",
                "credential_boundary_ready",
                "credential_handle_ready",
                "credential_injection_ready",
                "checker_contract_requested",
                "checker_contract_ready_requested",
                "real_checker_implementation_present",
                "real_checker_attached",
                "real_checker_executed",
                "actual_environment_presence_check_performed",
                "env_access_required",
                "env_access_allowed",
                "env_access_requested",
                "dotenv_access_requested",
                "printenv_requested",
                "credential_values_available",
                "credential_values_read",
                "credential_values_displayed",
                "credential_values_saved",
                "credential_metadata_available",
                "credential_metadata_displayed",
                "credential_metadata_saved",
                "checker_result_available",
                "checker_result_is_boolean_only",
                "checker_result_saved",
                "checker_result_displayed",
                "checker_result_broadly_propagated",
                "checker_result_unknown",
                "checker_result_failed",
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


def build_live_order_real_credential_presence_checker_contract(
    *,
    input_snapshot: LiveOrderRealCredentialPresenceCheckerContractInput | None = None,
) -> LiveOrderRealCredentialPresenceCheckerContractResult:
    """Build a checker contract without env, credential values, or real checks."""
    checker_input = input_snapshot or LiveOrderRealCredentialPresenceCheckerContractInput()
    safe_checker_contract_mode = _safe_checker_contract_mode(
        checker_input.checker_contract_mode,
    )
    unsupported_checker_contract_mode_present = _has_unsupported_checker_contract_mode(
        checker_input,
    )

    input_reasons = _input_reasons(checker_input)
    real_checker_present_reasons = _real_checker_present_reasons(checker_input)
    real_check_executed_reasons = _real_check_executed_reasons(checker_input)
    env_reasons = _env_reasons(checker_input)
    credential_value_reasons = _credential_value_reasons(checker_input)
    credential_metadata_reasons = _credential_metadata_reasons(checker_input)
    result_exposure_reasons = _result_exposure_reasons(checker_input)
    result_unknown_or_failed_reasons = _result_unknown_or_failed_reasons(checker_input)
    real_signing_or_post_reasons = _real_signing_or_post_reasons(checker_input)
    display_reasons = _display_or_save_reasons(checker_input)
    unsupported_reasons = _unsupported_reasons(checker_input)

    if input_reasons:
        status = (
            CredentialPresenceCheckerContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_INPUT
        )
        primary_reasons = input_reasons
    elif real_checker_present_reasons:
        status = (
            CredentialPresenceCheckerContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_CHECKER_PRESENT
        )
        primary_reasons = real_checker_present_reasons
    elif real_check_executed_reasons:
        status = (
            CredentialPresenceCheckerContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_CHECK_EXECUTED
        )
        primary_reasons = real_check_executed_reasons
    elif env_reasons:
        status = (
            CredentialPresenceCheckerContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_ENV_ACCESS
        )
        primary_reasons = env_reasons
    elif credential_value_reasons:
        status = (
            CredentialPresenceCheckerContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_CREDENTIAL_VALUE
        )
        primary_reasons = credential_value_reasons
    elif credential_metadata_reasons:
        status = (
            CredentialPresenceCheckerContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_CREDENTIAL_METADATA
        )
        primary_reasons = credential_metadata_reasons
    elif result_exposure_reasons:
        status = (
            CredentialPresenceCheckerContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_RESULT_EXPOSURE
        )
        primary_reasons = result_exposure_reasons
    elif result_unknown_or_failed_reasons:
        status = (
            CredentialPresenceCheckerContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_RESULT_UNKNOWN_OR_FAILED
        )
        primary_reasons = result_unknown_or_failed_reasons
    elif real_signing_or_post_reasons:
        status = (
            CredentialPresenceCheckerContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_SIGNING_OR_POST
        )
        primary_reasons = real_signing_or_post_reasons
    elif display_reasons:
        status = (
            CredentialPresenceCheckerContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_DISPLAY_OR_SAVE
        )
        primary_reasons = display_reasons
    elif unsupported_reasons:
        status = (
            CredentialPresenceCheckerContractStatus
            .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_UNSUPPORTED
        )
        primary_reasons = unsupported_reasons
    else:
        status = (
            CredentialPresenceCheckerContractStatus
            .CREDENTIAL_PRESENCE_CHECKER_CONTRACT_READY_NO_ENV_NO_REAL_CHECK
        )
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        input_reasons,
        real_checker_present_reasons,
        real_check_executed_reasons,
        env_reasons,
        credential_value_reasons,
        credential_metadata_reasons,
        result_exposure_reasons,
        result_unknown_or_failed_reasons,
        real_signing_or_post_reasons,
        display_reasons,
        unsupported_reasons,
    )
    ready = (
        status
        is CredentialPresenceCheckerContractStatus
        .CREDENTIAL_PRESENCE_CHECKER_CONTRACT_READY_NO_ENV_NO_REAL_CHECK
    )
    return LiveOrderRealCredentialPresenceCheckerContractResult(
        status=status,
        credential_presence_checker_contract_ready=ready,
        checker_contract_mode=safe_checker_contract_mode,
        unsupported_checker_contract_mode_present=(
            unsupported_checker_contract_mode_present
        ),
        raw_checker_contract_mode_displayed=False,
        raw_checker_contract_mode_saved=False,
        credential_presence_adapter_ready=checker_input.credential_presence_adapter_ready,
        credential_presence_check_ready=checker_input.credential_presence_check_ready,
        credential_boundary_ready=checker_input.credential_boundary_ready,
        credential_handle_ready=checker_input.credential_handle_ready,
        credential_injection_ready=checker_input.credential_injection_ready,
        checker_contract_requested=checker_input.checker_contract_requested,
        checker_contract_ready_requested=(
            checker_input.checker_contract_ready_requested
        ),
        real_checker_implementation_present=False,
        real_checker_attached=False,
        real_checker_executed=False,
        actual_environment_presence_check_performed=False,
        env_access_required=checker_input.env_access_required,
        env_access_allowed=False,
        env_access_requested=False,
        dotenv_access_requested=False,
        printenv_requested=False,
        credential_values_available=False,
        credential_values_read=False,
        credential_values_displayed=False,
        credential_values_saved=False,
        credential_metadata_available=False,
        credential_metadata_displayed=False,
        credential_metadata_saved=False,
        checker_result_available=False,
        checker_result_is_boolean_only=checker_input.checker_result_is_boolean_only,
        checker_result_saved=False,
        checker_result_displayed=False,
        checker_result_broadly_propagated=False,
        checker_result_unknown=False,
        checker_result_failed=False,
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
        check_results=_build_check_results(checker_input),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            CREDENTIAL_PRESENCE_CHECKER_CONTRACT_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_credential_presence_checker_contract_blockers_no_env_no_post"
        ),
    )


def render_live_order_real_credential_presence_checker_contract_markdown(
    result: LiveOrderRealCredentialPresenceCheckerContractResult,
) -> str:
    """Render sanitized credential presence checker contract metadata only."""
    lines = [
        "# Step 6G Real Credential Presence Checker Contract",
        "",
        "This credential presence checker is contract-only.",
        "This credential presence checker does not access env or .env.",
        "This credential presence checker does not check the real environment.",
        "This credential presence checker does not attach or execute a real checker.",
        "This credential presence checker does not expose credential metadata.",
        "This credential presence checker does not persist checker results.",
        "This credential presence checker does not generate real signatures.",
        "This credential presence checker does not execute API calls.",
        "This credential presence checker does not execute HTTP POST.",
        "This credential presence checker does not call order endpoint.",
        "This credential presence checker does not call live_order_once.",
        "Future real credential presence check must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- credential_presence_checker_contract_ready: "
            f"{_bool_text(result.credential_presence_checker_contract_ready)}"
        ),
        f"- checker_contract_mode: {result.checker_contract_mode}",
        (
            "- unsupported_checker_contract_mode_present: "
            f"{_bool_text(result.unsupported_checker_contract_mode_present)}"
        ),
        (
            "- raw_checker_contract_mode_displayed: "
            f"{_bool_text(result.raw_checker_contract_mode_displayed)}"
        ),
        (
            "- raw_checker_contract_mode_saved: "
            f"{_bool_text(result.raw_checker_contract_mode_saved)}"
        ),
        (
            "- credential_presence_adapter_ready: "
            f"{_bool_text(result.credential_presence_adapter_ready)}"
        ),
        (
            "- credential_presence_check_ready: "
            f"{_bool_text(result.credential_presence_check_ready)}"
        ),
        "",
        "## Contract Safety",
        (
            "- real_checker_implementation_present: "
            f"{_bool_text(result.real_checker_implementation_present)}"
        ),
        f"- real_checker_attached: {_bool_text(result.real_checker_attached)}",
        f"- real_checker_executed: {_bool_text(result.real_checker_executed)}",
        (
            "- actual_environment_presence_check_performed: "
            f"{_bool_text(result.actual_environment_presence_check_performed)}"
        ),
        f"- env_access_required: {_bool_text(result.env_access_required)}",
        f"- env_access_allowed: {_bool_text(result.env_access_allowed)}",
        f"- env_access_requested: {_bool_text(result.env_access_requested)}",
        f"- credential_values_read: {_bool_text(result.credential_values_read)}",
        (
            "- credential_metadata_available: "
            f"{_bool_text(result.credential_metadata_available)}"
        ),
        f"- checker_result_available: {_bool_text(result.checker_result_available)}",
        (
            "- checker_result_is_boolean_only: "
            f"{_bool_text(result.checker_result_is_boolean_only)}"
        ),
        f"- checker_result_saved: {_bool_text(result.checker_result_saved)}",
        f"- checker_result_displayed: {_bool_text(result.checker_result_displayed)}",
        (
            "- checker_result_broadly_propagated: "
            f"{_bool_text(result.checker_result_broadly_propagated)}"
        ),
        f"- checker_result_unknown: {_bool_text(result.checker_result_unknown)}",
        f"- checker_result_failed: {_bool_text(result.checker_result_failed)}",
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
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> tuple[LiveOrderRealCredentialPresenceCheckerContractCheckResult, ...]:
    input_reasons = _input_reasons(checker_input)
    unsupported_reasons = _unsupported_reasons(checker_input)
    real_checker_reasons = _merge_reasons(
        _real_checker_present_reasons(checker_input),
        _real_check_executed_reasons(checker_input),
    )
    no_value_or_result_reasons = _merge_reasons(
        _env_reasons(checker_input),
        _credential_value_reasons(checker_input),
        _credential_metadata_reasons(checker_input),
        _result_exposure_reasons(checker_input),
        _result_unknown_or_failed_reasons(checker_input),
        _display_or_save_reasons(checker_input),
    )
    real_signing_or_post_reasons = _real_signing_or_post_reasons(checker_input)
    return (
        LiveOrderRealCredentialPresenceCheckerContractCheckResult(
            name="credential presence checker contract input",
            passed=not input_reasons,
            sanitized_value="ready" if not input_reasons else ",".join(input_reasons),
            expected="checker contract mode with credential presence contracts ready",
        ),
        LiveOrderRealCredentialPresenceCheckerContractCheckResult(
            name="unsupported checker contract mode non exposure",
            passed=not unsupported_reasons,
            sanitized_value=(
                "none"
                if not unsupported_reasons
                else UNSUPPORTED_CHECKER_CONTRACT_MODE_LABEL
            ),
            expected="raw checker contract mode is not retained or rendered",
        ),
        LiveOrderRealCredentialPresenceCheckerContractCheckResult(
            name="no real checker or actual environment check",
            passed=not real_checker_reasons,
            sanitized_value="none"
            if not real_checker_reasons
            else ",".join(real_checker_reasons),
            expected="no real checker implementation attachment execution or check",
        ),
        LiveOrderRealCredentialPresenceCheckerContractCheckResult(
            name="no env credential or checker result exposure",
            passed=not no_value_or_result_reasons,
            sanitized_value="none"
            if not no_value_or_result_reasons
            else ",".join(no_value_or_result_reasons),
            expected="no env access credential metadata or checker result persistence",
        ),
        LiveOrderRealCredentialPresenceCheckerContractCheckResult(
            name="no real signing or post",
            passed=not real_signing_or_post_reasons,
            sanitized_value="none"
            if not real_signing_or_post_reasons
            else ",".join(real_signing_or_post_reasons),
            expected="no real signing headers API post endpoint or live_order_once",
        ),
    )


def _input_reasons(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_presence_adapter_ready",
        "credential_presence_check_ready",
        "credential_boundary_ready",
        "credential_handle_ready",
        "credential_injection_ready",
        "checker_contract_requested",
        "checker_contract_ready_requested",
        "env_access_required",
        "checker_result_is_boolean_only",
    ):
        if not getattr(checker_input, field_name):
            reasons.append(f"{field_name}_false")
    return tuple(reasons)


def _real_checker_present_reasons(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("real_checker_implementation_present", "real_checker_attached"):
        if getattr(checker_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_check_executed_reasons(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "real_checker_executed",
        "actual_environment_presence_check_performed",
    ):
        if getattr(checker_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _env_reasons(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "env_access_allowed",
        "env_access_requested",
        "dotenv_access_requested",
        "printenv_requested",
    ):
        if getattr(checker_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_value_reasons(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_values_available",
        "credential_values_read",
        "credential_values_displayed",
        "credential_values_saved",
    ):
        if getattr(checker_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_metadata_reasons(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_metadata_available",
        "credential_metadata_displayed",
        "credential_metadata_saved",
    ):
        if getattr(checker_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _result_exposure_reasons(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "checker_result_available",
        "checker_result_saved",
        "checker_result_displayed",
        "checker_result_broadly_propagated",
    ):
        if getattr(checker_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _result_unknown_or_failed_reasons(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in ("checker_result_unknown", "checker_result_failed"):
        if getattr(checker_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_signing_or_post_reasons(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
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
        if getattr(checker_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _display_or_save_reasons(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not checker_input.safe_to_render:
        reasons.append("safe_to_render_false")
    if not checker_input.safe_to_serialize:
        reasons.append("safe_to_serialize_false")
    return tuple(reasons)


def _unsupported_reasons(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _has_unsupported_checker_contract_mode(checker_input):
        reasons.append("unsupported_checker_contract_mode_present")
    if checker_input.retry_allowed:
        reasons.append("retry_allowed_unsupported")
    if checker_input.loop_allowed:
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
    result: LiveOrderRealCredentialPresenceCheckerContractResult,
) -> None:
    unsafe_flags = (
        result.raw_checker_contract_mode_displayed,
        result.raw_checker_contract_mode_saved,
        result.real_checker_implementation_present,
        result.real_checker_attached,
        result.real_checker_executed,
        result.actual_environment_presence_check_performed,
        result.env_access_allowed,
        result.env_access_requested,
        result.dotenv_access_requested,
        result.printenv_requested,
        result.credential_values_available,
        result.credential_values_read,
        result.credential_values_displayed,
        result.credential_values_saved,
        result.credential_metadata_available,
        result.credential_metadata_displayed,
        result.credential_metadata_saved,
        result.checker_result_available,
        result.checker_result_saved,
        result.checker_result_displayed,
        result.checker_result_broadly_propagated,
        result.checker_result_unknown,
        result.checker_result_failed,
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
            "credential presence checker contract result is unsafe",
        )
    if result.unsupported_checker_contract_mode_present:
        if result.checker_contract_mode != UNSUPPORTED_CHECKER_CONTRACT_MODE_LABEL:
            raise LiveVerificationValidationError(
                "unsupported checker contract mode must use safe label",
            )
    elif (
        result.checker_contract_mode
        != CredentialPresenceCheckerContractMode.CHECKER_CONTRACT_ONLY.value
    ):
        raise LiveVerificationValidationError(
            "checker contract mode must be canonical",
        )


def _has_unsupported_checker_contract_mode(
    checker_input: LiveOrderRealCredentialPresenceCheckerContractInput,
) -> bool:
    return (
        checker_input.checker_contract_mode
        != CredentialPresenceCheckerContractMode.CHECKER_CONTRACT_ONLY.value
    )


def _safe_checker_contract_mode(raw_checker_contract_mode: str) -> str:
    if (
        raw_checker_contract_mode
        == CredentialPresenceCheckerContractMode.CHECKER_CONTRACT_ONLY.value
    ):
        return CredentialPresenceCheckerContractMode.CHECKER_CONTRACT_ONLY.value
    return UNSUPPORTED_CHECKER_CONTRACT_MODE_LABEL


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
