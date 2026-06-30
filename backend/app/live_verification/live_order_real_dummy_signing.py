"""Step 6G dummy signing check, no real credentials and no values.

This module checks the signing input shape with dummy-only metadata. It does
not read environment variables, use credential values, generate real
signatures, expose header values, call APIs, or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_order_transport_core import (
    TRANSPORT_CORE_HEADER_NAME_SUMMARY,
    TRANSPORT_CORE_ORDER_PATH,
)

DUMMY_SIGNING_METHOD = "POST"
DUMMY_SIGNING_ALGORITHM_LABEL = "HMAC-SHA256"
DUMMY_SIGNING_RECOMMENDED_NEXT_STEP = (
    "future_real_signing_must_be_a_separate_step_after_dummy_check"
)


class LiveOrderRealDummySigningStatus(str, Enum):
    DUMMY_SIGNING_READY_NO_CREDENTIAL_NO_API_NO_POST = (
        "DUMMY_SIGNING_READY_NO_CREDENTIAL_NO_API_NO_POST"
    )
    DUMMY_SIGNING_CHECK_PASSED_NO_VALUE_EXPOSED = (
        "DUMMY_SIGNING_CHECK_PASSED_NO_VALUE_EXPOSED"
    )
    BLOCKED_DUMMY_SIGNING_INPUT = "BLOCKED_DUMMY_SIGNING_INPUT"
    BLOCKED_DUMMY_SIGNING_REAL_CREDENTIAL_REQUESTED = (
        "BLOCKED_DUMMY_SIGNING_REAL_CREDENTIAL_REQUESTED"
    )
    BLOCKED_DUMMY_SIGNING_ENV_ACCESS = "BLOCKED_DUMMY_SIGNING_ENV_ACCESS"
    BLOCKED_DUMMY_SIGNING_REAL_SIGNATURE_REQUESTED = (
        "BLOCKED_DUMMY_SIGNING_REAL_SIGNATURE_REQUESTED"
    )
    BLOCKED_DUMMY_SIGNING_SIGNATURE_VALUE_EXPOSURE = (
        "BLOCKED_DUMMY_SIGNING_SIGNATURE_VALUE_EXPOSURE"
    )
    BLOCKED_DUMMY_SIGNING_HEADER_VALUE_EXPOSURE = (
        "BLOCKED_DUMMY_SIGNING_HEADER_VALUE_EXPOSURE"
    )
    BLOCKED_DUMMY_SIGNING_CREDENTIAL_EXPOSURE = (
        "BLOCKED_DUMMY_SIGNING_CREDENTIAL_EXPOSURE"
    )
    BLOCKED_DUMMY_SIGNING_UNSUPPORTED = "BLOCKED_DUMMY_SIGNING_UNSUPPORTED"


DummySigningStatus = LiveOrderRealDummySigningStatus


@dataclass(frozen=True)
class LiveOrderRealDummySigningInput:
    method: str = DUMMY_SIGNING_METHOD
    path: str = TRANSPORT_CORE_ORDER_PATH
    body_contract_ready: bool = True
    stable_serialization_ready: bool = True
    dummy_timestamp_label: str = "DUMMY_TIMESTAMP_LABEL"
    dummy_key_material_label: str = "DUMMY_KEY_MATERIAL_LABEL"
    dummy_secret_material_label: str = "DUMMY_SECRET_MATERIAL_LABEL"
    algorithm_label: str = DUMMY_SIGNING_ALGORITHM_LABEL
    header_names_allowed: tuple[str, ...] = TRANSPORT_CORE_HEADER_NAME_SUMMARY
    use_real_credentials: bool = False
    use_env_credentials: bool = False
    use_dotenv: bool = False
    generate_real_signature: bool = False
    expose_signature_value: bool = False
    expose_header_values: bool = False
    expose_credentials: bool = False
    store_signature_value: bool = False
    store_header_values: bool = False
    store_credentials: bool = False
    signature_value_present: bool = False
    credential_value_present: bool = False
    header_values_present: bool = False
    raw_request_displayed: bool = False
    raw_request_saved: bool = False
    raw_response_displayed: bool = False
    raw_response_saved: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    retry_allowed: bool = False
    loop_allowed: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("method", self.method)
        _require_non_empty("path", self.path)
        _require_non_empty("algorithm_label", self.algorithm_label)
        _validate_str_tuple("header_names_allowed", self.header_names_allowed)
        _validate_bool_fields(
            self,
            (
                "body_contract_ready",
                "stable_serialization_ready",
                "use_real_credentials",
                "use_env_credentials",
                "use_dotenv",
                "generate_real_signature",
                "expose_signature_value",
                "expose_header_values",
                "expose_credentials",
                "store_signature_value",
                "store_header_values",
                "store_credentials",
                "signature_value_present",
                "credential_value_present",
                "header_values_present",
                "raw_request_displayed",
                "raw_request_saved",
                "raw_response_displayed",
                "raw_response_saved",
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
class LiveOrderRealDummySigningCheckResult:
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
class LiveOrderRealDummySigningResult:
    status: LiveOrderRealDummySigningStatus
    dummy_signing_ready: bool
    dummy_signature_check_performed: bool
    dummy_signature_check_passed: bool
    algorithm_label: str
    method: str
    path: str
    header_name_labels: tuple[str, ...]
    signature_value_present: bool
    signature_value_displayed: bool
    signature_value_saved: bool
    credential_value_present: bool
    credential_value_displayed: bool
    credential_value_saved: bool
    header_values_present: bool
    header_values_displayed: bool
    header_values_saved: bool
    raw_request_displayed: bool
    raw_request_saved: bool
    raw_response_displayed: bool
    raw_response_saved: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_executed: bool
    retry_allowed: bool
    loop_allowed: bool
    check_results: tuple[LiveOrderRealDummySigningCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealDummySigningStatus):
            raise LiveVerificationValidationError("status must be dummy signing status")
        _require_non_empty("algorithm_label", self.algorithm_label)
        _require_non_empty("method", self.method)
        _require_non_empty("path", self.path)
        _validate_str_tuple("header_name_labels", self.header_name_labels)
        _validate_bool_fields(
            self,
            (
                "dummy_signing_ready",
                "dummy_signature_check_performed",
                "dummy_signature_check_passed",
                "signature_value_present",
                "signature_value_displayed",
                "signature_value_saved",
                "credential_value_present",
                "credential_value_displayed",
                "credential_value_saved",
                "header_values_present",
                "header_values_displayed",
                "header_values_saved",
                "raw_request_displayed",
                "raw_request_saved",
                "raw_response_displayed",
                "raw_response_saved",
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
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_result_safety(self)


def build_live_order_real_dummy_signing_check(
    *,
    input_snapshot: LiveOrderRealDummySigningInput | None = None,
) -> LiveOrderRealDummySigningResult:
    """Check dummy signing shape without retaining any signature value."""
    dummy_input = input_snapshot or LiveOrderRealDummySigningInput()

    env_reasons = _env_reasons(dummy_input)
    real_credential_reasons = _real_credential_reasons(dummy_input)
    real_signature_reasons = _real_signature_reasons(dummy_input)
    signature_exposure_reasons = _signature_exposure_reasons(dummy_input)
    header_exposure_reasons = _header_exposure_reasons(dummy_input)
    credential_exposure_reasons = _credential_exposure_reasons(dummy_input)
    input_reasons = _input_reasons(dummy_input)
    unsupported_reasons = _unsupported_reasons(dummy_input)

    if env_reasons:
        status = DummySigningStatus.BLOCKED_DUMMY_SIGNING_ENV_ACCESS
        primary_reasons = env_reasons
    elif real_credential_reasons:
        status = DummySigningStatus.BLOCKED_DUMMY_SIGNING_REAL_CREDENTIAL_REQUESTED
        primary_reasons = real_credential_reasons
    elif real_signature_reasons:
        status = DummySigningStatus.BLOCKED_DUMMY_SIGNING_REAL_SIGNATURE_REQUESTED
        primary_reasons = real_signature_reasons
    elif signature_exposure_reasons:
        status = DummySigningStatus.BLOCKED_DUMMY_SIGNING_SIGNATURE_VALUE_EXPOSURE
        primary_reasons = signature_exposure_reasons
    elif header_exposure_reasons:
        status = DummySigningStatus.BLOCKED_DUMMY_SIGNING_HEADER_VALUE_EXPOSURE
        primary_reasons = header_exposure_reasons
    elif credential_exposure_reasons:
        status = DummySigningStatus.BLOCKED_DUMMY_SIGNING_CREDENTIAL_EXPOSURE
        primary_reasons = credential_exposure_reasons
    elif input_reasons:
        status = DummySigningStatus.BLOCKED_DUMMY_SIGNING_INPUT
        primary_reasons = input_reasons
    elif unsupported_reasons:
        status = DummySigningStatus.BLOCKED_DUMMY_SIGNING_UNSUPPORTED
        primary_reasons = unsupported_reasons
    else:
        status = DummySigningStatus.DUMMY_SIGNING_CHECK_PASSED_NO_VALUE_EXPOSED
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        env_reasons,
        real_credential_reasons,
        real_signature_reasons,
        signature_exposure_reasons,
        header_exposure_reasons,
        credential_exposure_reasons,
        input_reasons,
        unsupported_reasons,
    )
    check_passed = status is DummySigningStatus.DUMMY_SIGNING_CHECK_PASSED_NO_VALUE_EXPOSED

    return LiveOrderRealDummySigningResult(
        status=status,
        dummy_signing_ready=check_passed,
        dummy_signature_check_performed=check_passed,
        dummy_signature_check_passed=check_passed,
        algorithm_label=dummy_input.algorithm_label,
        method=dummy_input.method,
        path=dummy_input.path,
        header_name_labels=dummy_input.header_names_allowed,
        signature_value_present=False,
        signature_value_displayed=False,
        signature_value_saved=False,
        credential_value_present=False,
        credential_value_displayed=False,
        credential_value_saved=False,
        header_values_present=False,
        header_values_displayed=False,
        header_values_saved=False,
        raw_request_displayed=False,
        raw_request_saved=False,
        raw_response_displayed=False,
        raw_response_saved=False,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_executed=False,
        retry_allowed=False,
        loop_allowed=False,
        check_results=_build_check_results(dummy_input, check_passed),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            DUMMY_SIGNING_RECOMMENDED_NEXT_STEP
            if check_passed
            else "fix_dummy_signing_blockers_no_api_no_post"
        ),
    )


def render_live_order_real_dummy_signing_markdown(
    result: LiveOrderRealDummySigningResult,
) -> str:
    """Render a value-free dummy signing summary."""
    lines = [
        "# Step 6G Dummy Signing Check",
        "",
        "This dummy signing check does not use real credentials.",
        "This dummy signing check does not generate real signatures.",
        "This dummy signing check does not expose signature values.",
        "This dummy signing check does not expose header values.",
        "This dummy signing check does not execute API calls.",
        "This dummy signing check does not execute HTTP POST.",
        "This dummy signing check does not call live_order_once.",
        "Future real signing must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- dummy_signing_ready: {_bool_text(result.dummy_signing_ready)}",
        (
            "- dummy_signature_check_performed: "
            f"{_bool_text(result.dummy_signature_check_performed)}"
        ),
        (
            "- dummy_signature_check_passed: "
            f"{_bool_text(result.dummy_signature_check_passed)}"
        ),
        f"- algorithm_label: {result.algorithm_label}",
        f"- method: {result.method}",
        f"- path: {result.path}",
        f"- header_name_labels: {','.join(result.header_name_labels)}",
        "",
        "## Safety",
        f"- signature_value_present: {_bool_text(result.signature_value_present)}",
        f"- credential_value_present: {_bool_text(result.credential_value_present)}",
        f"- header_values_present: {_bool_text(result.header_values_present)}",
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
    dummy_input: LiveOrderRealDummySigningInput,
    check_passed: bool,
) -> tuple[LiveOrderRealDummySigningCheckResult, ...]:
    input_reasons = _input_reasons(dummy_input)
    exposure_reasons = _merge_reasons(
        _signature_exposure_reasons(dummy_input),
        _header_exposure_reasons(dummy_input),
        _credential_exposure_reasons(dummy_input),
    )
    return (
        LiveOrderRealDummySigningCheckResult(
            name="dummy signing input shape",
            passed=not input_reasons,
            sanitized_value="ready" if not input_reasons else ",".join(input_reasons),
            expected="POST /v1/order dummy labels and stable body contract",
        ),
        LiveOrderRealDummySigningCheckResult(
            name="dummy signature value not retained",
            passed=not exposure_reasons,
            sanitized_value="none" if not exposure_reasons else ",".join(exposure_reasons),
            expected="no signature header credential raw or response values",
        ),
        LiveOrderRealDummySigningCheckResult(
            name="dummy HMAC-SHA256 shape check",
            passed=check_passed,
            sanitized_value="passed_no_value" if check_passed else "not_performed",
            expected="boolean/category only, no dummy signature value",
        ),
    )


def _input_reasons(dummy_input: LiveOrderRealDummySigningInput) -> tuple[str, ...]:
    reasons: list[str] = []
    if dummy_input.method != DUMMY_SIGNING_METHOD:
        reasons.append("method_not_post")
    if dummy_input.path != TRANSPORT_CORE_ORDER_PATH:
        reasons.append("path_not_order_contract")
    if not dummy_input.body_contract_ready:
        reasons.append("body_contract_not_ready")
    if not dummy_input.stable_serialization_ready:
        reasons.append("stable_serialization_not_ready")
    if not dummy_input.dummy_timestamp_label:
        reasons.append("dummy_timestamp_label_missing")
    if not dummy_input.dummy_key_material_label:
        reasons.append("dummy_key_material_label_missing")
    if not dummy_input.dummy_secret_material_label:
        reasons.append("dummy_secret_material_label_missing")
    if dummy_input.header_names_allowed != TRANSPORT_CORE_HEADER_NAME_SUMMARY:
        reasons.append("header_names_not_allowed")
    return tuple(reasons)


def _real_credential_reasons(
    dummy_input: LiveOrderRealDummySigningInput,
) -> tuple[str, ...]:
    if dummy_input.use_real_credentials:
        return ("use_real_credentials_requested",)
    return ()


def _env_reasons(dummy_input: LiveOrderRealDummySigningInput) -> tuple[str, ...]:
    reasons: list[str] = []
    if dummy_input.use_env_credentials:
        reasons.append("use_env_credentials_requested")
    if dummy_input.use_dotenv:
        reasons.append("use_dotenv_requested")
    return tuple(reasons)


def _real_signature_reasons(
    dummy_input: LiveOrderRealDummySigningInput,
) -> tuple[str, ...]:
    if dummy_input.generate_real_signature:
        return ("generate_real_signature_requested",)
    return ()


def _signature_exposure_reasons(
    dummy_input: LiveOrderRealDummySigningInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "expose_signature_value",
        "store_signature_value",
        "signature_value_present",
        "raw_request_displayed",
        "raw_request_saved",
        "raw_response_displayed",
        "raw_response_saved",
    ):
        if getattr(dummy_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _header_exposure_reasons(
    dummy_input: LiveOrderRealDummySigningInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "expose_header_values",
        "store_header_values",
        "header_values_present",
    ):
        if getattr(dummy_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _credential_exposure_reasons(
    dummy_input: LiveOrderRealDummySigningInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "expose_credentials",
        "store_credentials",
        "credential_value_present",
    ):
        if getattr(dummy_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _unsupported_reasons(dummy_input: LiveOrderRealDummySigningInput) -> tuple[str, ...]:
    reasons: list[str] = []
    if dummy_input.algorithm_label != DUMMY_SIGNING_ALGORITHM_LABEL:
        reasons.append("unsupported_algorithm")
    for field_name in (
        "http_post_executed",
        "order_endpoint_called",
        "live_order_once_called",
        "post_allowed_this_step",
        "post_executed",
        "retry_allowed",
        "loop_allowed",
    ):
        if getattr(dummy_input, field_name):
            reasons.append(f"{field_name}_unsupported")
    return tuple(reasons)


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _validate_result_safety(result: LiveOrderRealDummySigningResult) -> None:
    unsafe_flags = (
        result.signature_value_present,
        result.signature_value_displayed,
        result.signature_value_saved,
        result.credential_value_present,
        result.credential_value_displayed,
        result.credential_value_saved,
        result.header_values_present,
        result.header_values_displayed,
        result.header_values_saved,
        result.raw_request_displayed,
        result.raw_request_saved,
        result.raw_response_displayed,
        result.raw_response_saved,
        result.http_post_executed,
        result.order_endpoint_called,
        result.live_order_once_called,
        result.post_allowed_this_step,
        result.post_executed,
        result.retry_allowed,
        result.loop_allowed,
    )
    if any(unsafe_flags):
        raise LiveVerificationValidationError("dummy signing result must not expose values")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_str_tuple(field_name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple) or any(not isinstance(value, str) for value in values):
        raise LiveVerificationValidationError(f"{field_name} must be tuple[str, ...]")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
