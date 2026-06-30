"""Step 6G HTTP transport interface skeleton, interface-only.

This module defines a future transport boundary without an HTTP client. It does
not use credentials, generate signatures or header values, call APIs, execute
HTTP POST, call an order endpoint, or call live_order_once.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_order_transport_core import (
    TRANSPORT_CORE_ORDER_PATH,
)

HTTP_TRANSPORT_INTERFACE_METHOD = "POST"
HTTP_TRANSPORT_INTERFACE_RECOMMENDED_NEXT_STEP = (
    "future_real_transport_must_be_a_separate_reviewed_step"
)


class LiveOrderRealHttpTransportInterfaceStatus(str, Enum):
    HTTP_TRANSPORT_INTERFACE_READY_NO_API_NO_POST = (
        "HTTP_TRANSPORT_INTERFACE_READY_NO_API_NO_POST"
    )
    BLOCKED_HTTP_TRANSPORT_INTERFACE_INPUT = "BLOCKED_HTTP_TRANSPORT_INTERFACE_INPUT"
    BLOCKED_HTTP_TRANSPORT_INTERFACE_REAL_TRANSPORT_REQUESTED = (
        "BLOCKED_HTTP_TRANSPORT_INTERFACE_REAL_TRANSPORT_REQUESTED"
    )
    BLOCKED_HTTP_TRANSPORT_INTERFACE_HTTP_CLIENT_PRESENT = (
        "BLOCKED_HTTP_TRANSPORT_INTERFACE_HTTP_CLIENT_PRESENT"
    )
    BLOCKED_HTTP_TRANSPORT_INTERFACE_HTTP_POST = (
        "BLOCKED_HTTP_TRANSPORT_INTERFACE_HTTP_POST"
    )
    BLOCKED_HTTP_TRANSPORT_INTERFACE_ORDER_ENDPOINT = (
        "BLOCKED_HTTP_TRANSPORT_INTERFACE_ORDER_ENDPOINT"
    )
    BLOCKED_HTTP_TRANSPORT_INTERFACE_LIVE_ORDER_ONCE = (
        "BLOCKED_HTTP_TRANSPORT_INTERFACE_LIVE_ORDER_ONCE"
    )
    BLOCKED_HTTP_TRANSPORT_INTERFACE_RAW_OR_SECRET_EXPOSURE = (
        "BLOCKED_HTTP_TRANSPORT_INTERFACE_RAW_OR_SECRET_EXPOSURE"
    )
    BLOCKED_HTTP_TRANSPORT_INTERFACE_REAL_ID_EXPOSURE = (
        "BLOCKED_HTTP_TRANSPORT_INTERFACE_REAL_ID_EXPOSURE"
    )
    BLOCKED_HTTP_TRANSPORT_INTERFACE_RETRY_OR_LOOP = (
        "BLOCKED_HTTP_TRANSPORT_INTERFACE_RETRY_OR_LOOP"
    )
    BLOCKED_HTTP_TRANSPORT_INTERFACE_UNSUPPORTED = (
        "BLOCKED_HTTP_TRANSPORT_INTERFACE_UNSUPPORTED"
    )


class LiveOrderRealHttpTransportInterfaceMode(str, Enum):
    INTERFACE_ONLY = "INTERFACE_ONLY"


HttpTransportInterfaceStatus = LiveOrderRealHttpTransportInterfaceStatus
HttpTransportInterfaceMode = LiveOrderRealHttpTransportInterfaceMode


@dataclass(frozen=True)
class LiveOrderRealHttpTransportInterfaceContract:
    interface_mode: str = HttpTransportInterfaceMode.INTERFACE_ONLY.value
    real_transport_requested: bool = False
    http_client_present: bool = False
    can_execute_http_post: bool = False
    can_call_order_endpoint: bool = False
    can_call_live_order_once: bool = False
    can_accept_credential_values: bool = False
    can_accept_signature_values: bool = False
    can_accept_header_values: bool = False
    can_hold_raw_request: bool = False
    can_hold_raw_response: bool = False
    can_hold_real_ids: bool = False
    max_attempts: int = 1

    def __post_init__(self) -> None:
        _require_non_empty("interface_mode", self.interface_mode)
        _validate_non_negative_int("max_attempts", self.max_attempts)
        _validate_bool_fields(
            self,
            (
                "real_transport_requested",
                "http_client_present",
                "can_execute_http_post",
                "can_call_order_endpoint",
                "can_call_live_order_once",
                "can_accept_credential_values",
                "can_accept_signature_values",
                "can_accept_header_values",
                "can_hold_raw_request",
                "can_hold_raw_response",
                "can_hold_real_ids",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealHttpTransportInterfaceInput:
    interface_mode: str = HttpTransportInterfaceMode.INTERFACE_ONLY.value
    method: str = HTTP_TRANSPORT_INTERFACE_METHOD
    path: str = TRANSPORT_CORE_ORDER_PATH
    endpoint_contract_ready: bool = True
    order_body_allowlist_passed: bool = True
    stable_serialization_ready: bool = True
    signing_contract_ready: bool = True
    dummy_signing_ready: bool = True
    dummy_signature_check_passed: bool = True
    private_order_transport_contract_ready: bool = True
    one_shot_no_retry_ready: bool = True
    post_attempt_limit: int = 1
    post_attempt_count_before: int = 0
    retry_allowed: bool = False
    loop_allowed: bool = False
    add_order_allowed: bool = False
    change_order_allowed: bool = False
    cancel_order_allowed: bool = False
    close_order_allowed: bool = False
    real_transport_requested: bool = False
    http_client_present: bool = False
    can_execute_http_post: bool = False
    can_call_order_endpoint: bool = False
    can_call_live_order_once: bool = False
    credential_values_provided: bool = False
    signature_value_generated: bool = False
    header_values_present: bool = False
    raw_request_present: bool = False
    raw_response_present: bool = False
    real_ids_present: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("interface_mode", self.interface_mode)
        _require_non_empty("method", self.method)
        _require_non_empty("path", self.path)
        _validate_non_negative_int("post_attempt_limit", self.post_attempt_limit)
        _validate_non_negative_int(
            "post_attempt_count_before",
            self.post_attempt_count_before,
        )
        _validate_bool_fields(
            self,
            (
                "endpoint_contract_ready",
                "order_body_allowlist_passed",
                "stable_serialization_ready",
                "signing_contract_ready",
                "dummy_signing_ready",
                "dummy_signature_check_passed",
                "private_order_transport_contract_ready",
                "one_shot_no_retry_ready",
                "retry_allowed",
                "loop_allowed",
                "add_order_allowed",
                "change_order_allowed",
                "cancel_order_allowed",
                "close_order_allowed",
                "real_transport_requested",
                "http_client_present",
                "can_execute_http_post",
                "can_call_order_endpoint",
                "can_call_live_order_once",
                "credential_values_provided",
                "signature_value_generated",
                "header_values_present",
                "raw_request_present",
                "raw_response_present",
                "real_ids_present",
                "post_allowed_this_step",
                "post_executed",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealHttpTransportInterfaceCheckResult:
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
class LiveOrderRealHttpTransportInterfaceResult:
    status: LiveOrderRealHttpTransportInterfaceStatus
    interface_ready: bool
    interface_mode: str
    method: str
    path: str
    endpoint_contract_ready: bool
    signing_contract_ready: bool
    dummy_signing_ready: bool
    private_order_transport_contract_ready: bool
    http_client_present: bool
    can_execute_http_post: bool
    can_call_order_endpoint: bool
    can_call_live_order_once: bool
    credential_values_provided: bool
    signature_value_generated: bool
    header_values_present: bool
    raw_request_present: bool
    raw_response_present: bool
    real_ids_present: bool
    post_allowed_this_step: bool
    post_executed: bool
    retry_allowed: bool
    loop_allowed: bool
    check_results: tuple[LiveOrderRealHttpTransportInterfaceCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealHttpTransportInterfaceStatus):
            raise LiveVerificationValidationError("status must be interface status")
        _require_non_empty("interface_mode", self.interface_mode)
        _require_non_empty("method", self.method)
        _require_non_empty("path", self.path)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(
            self,
            (
                "interface_ready",
                "endpoint_contract_ready",
                "signing_contract_ready",
                "dummy_signing_ready",
                "private_order_transport_contract_ready",
                "http_client_present",
                "can_execute_http_post",
                "can_call_order_endpoint",
                "can_call_live_order_once",
                "credential_values_provided",
                "signature_value_generated",
                "header_values_present",
                "raw_request_present",
                "raw_response_present",
                "real_ids_present",
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


def build_live_order_real_http_transport_interface(
    *,
    input_snapshot: LiveOrderRealHttpTransportInterfaceInput | None = None,
    interface_contract: LiveOrderRealHttpTransportInterfaceContract | None = None,
) -> LiveOrderRealHttpTransportInterfaceResult:
    """Build an interface-only transport boundary decision."""
    interface_input = input_snapshot or LiveOrderRealHttpTransportInterfaceInput()
    contract = interface_contract or LiveOrderRealHttpTransportInterfaceContract()

    retry_reasons = _retry_or_loop_reasons(interface_input, contract)
    real_id_reasons = _real_id_reasons(interface_input, contract)
    raw_reasons = _raw_or_secret_reasons(interface_input, contract)
    real_transport_reasons = _real_transport_reasons(interface_input, contract)
    http_client_reasons = _http_client_reasons(interface_input, contract)
    http_post_reasons = _http_post_reasons(interface_input, contract)
    endpoint_reasons = _order_endpoint_reasons(interface_input, contract)
    live_once_reasons = _live_order_once_reasons(interface_input, contract)
    input_reasons = _input_reasons(interface_input, contract)
    unsupported_reasons = _unsupported_reasons(interface_input, contract)

    if retry_reasons:
        status = HttpTransportInterfaceStatus.BLOCKED_HTTP_TRANSPORT_INTERFACE_RETRY_OR_LOOP
        primary_reasons = retry_reasons
    elif real_id_reasons:
        status = HttpTransportInterfaceStatus.BLOCKED_HTTP_TRANSPORT_INTERFACE_REAL_ID_EXPOSURE
        primary_reasons = real_id_reasons
    elif raw_reasons:
        status = (
            HttpTransportInterfaceStatus
            .BLOCKED_HTTP_TRANSPORT_INTERFACE_RAW_OR_SECRET_EXPOSURE
        )
        primary_reasons = raw_reasons
    elif real_transport_reasons:
        status = (
            HttpTransportInterfaceStatus
            .BLOCKED_HTTP_TRANSPORT_INTERFACE_REAL_TRANSPORT_REQUESTED
        )
        primary_reasons = real_transport_reasons
    elif http_client_reasons:
        status = (
            HttpTransportInterfaceStatus
            .BLOCKED_HTTP_TRANSPORT_INTERFACE_HTTP_CLIENT_PRESENT
        )
        primary_reasons = http_client_reasons
    elif http_post_reasons:
        status = HttpTransportInterfaceStatus.BLOCKED_HTTP_TRANSPORT_INTERFACE_HTTP_POST
        primary_reasons = http_post_reasons
    elif endpoint_reasons:
        status = (
            HttpTransportInterfaceStatus
            .BLOCKED_HTTP_TRANSPORT_INTERFACE_ORDER_ENDPOINT
        )
        primary_reasons = endpoint_reasons
    elif live_once_reasons:
        status = HttpTransportInterfaceStatus.BLOCKED_HTTP_TRANSPORT_INTERFACE_LIVE_ORDER_ONCE
        primary_reasons = live_once_reasons
    elif input_reasons:
        status = HttpTransportInterfaceStatus.BLOCKED_HTTP_TRANSPORT_INTERFACE_INPUT
        primary_reasons = input_reasons
    elif unsupported_reasons:
        status = HttpTransportInterfaceStatus.BLOCKED_HTTP_TRANSPORT_INTERFACE_UNSUPPORTED
        primary_reasons = unsupported_reasons
    else:
        status = HttpTransportInterfaceStatus.HTTP_TRANSPORT_INTERFACE_READY_NO_API_NO_POST
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        retry_reasons,
        real_id_reasons,
        raw_reasons,
        real_transport_reasons,
        http_client_reasons,
        http_post_reasons,
        endpoint_reasons,
        live_once_reasons,
        input_reasons,
        unsupported_reasons,
    )
    ready = (
        status
        is HttpTransportInterfaceStatus.HTTP_TRANSPORT_INTERFACE_READY_NO_API_NO_POST
    )
    return LiveOrderRealHttpTransportInterfaceResult(
        status=status,
        interface_ready=ready,
        interface_mode=interface_input.interface_mode,
        method=interface_input.method,
        path=interface_input.path,
        endpoint_contract_ready=interface_input.endpoint_contract_ready,
        signing_contract_ready=interface_input.signing_contract_ready,
        dummy_signing_ready=interface_input.dummy_signing_ready,
        private_order_transport_contract_ready=(
            interface_input.private_order_transport_contract_ready
        ),
        http_client_present=False,
        can_execute_http_post=False,
        can_call_order_endpoint=False,
        can_call_live_order_once=False,
        credential_values_provided=False,
        signature_value_generated=False,
        header_values_present=False,
        raw_request_present=False,
        raw_response_present=False,
        real_ids_present=False,
        post_allowed_this_step=False,
        post_executed=False,
        retry_allowed=False,
        loop_allowed=False,
        check_results=_build_check_results(interface_input, contract),
        blocked_reasons=blocked_reasons,
        recommended_next_step=(
            HTTP_TRANSPORT_INTERFACE_RECOMMENDED_NEXT_STEP
            if ready
            else "fix_http_transport_interface_blockers_no_api_no_post"
        ),
    )


def render_live_order_real_http_transport_interface_markdown(
    result: LiveOrderRealHttpTransportInterfaceResult,
) -> str:
    """Render only sanitized interface metadata."""
    lines = [
        "# Step 6G HTTP Transport Interface Skeleton",
        "",
        "This HTTP transport interface is interface-only.",
        "This HTTP transport interface does not include an HTTP client.",
        "This HTTP transport interface does not execute API calls.",
        "This HTTP transport interface does not execute HTTP POST.",
        "This HTTP transport interface does not call order endpoint.",
        "This HTTP transport interface does not call live_order_once.",
        "Future real transport must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- interface_ready: {_bool_text(result.interface_ready)}",
        f"- interface_mode: {result.interface_mode}",
        f"- method: {result.method}",
        f"- path: {result.path}",
        f"- endpoint_contract_ready: {_bool_text(result.endpoint_contract_ready)}",
        f"- signing_contract_ready: {_bool_text(result.signing_contract_ready)}",
        f"- dummy_signing_ready: {_bool_text(result.dummy_signing_ready)}",
        (
            "- private_order_transport_contract_ready: "
            f"{_bool_text(result.private_order_transport_contract_ready)}"
        ),
        "",
        "## Safety",
        f"- http_client_present: {_bool_text(result.http_client_present)}",
        f"- can_execute_http_post: {_bool_text(result.can_execute_http_post)}",
        f"- can_call_order_endpoint: {_bool_text(result.can_call_order_endpoint)}",
        f"- can_call_live_order_once: {_bool_text(result.can_call_live_order_once)}",
        f"- credential_values_provided: {_bool_text(result.credential_values_provided)}",
        f"- signature_value_generated: {_bool_text(result.signature_value_generated)}",
        f"- header_values_present: {_bool_text(result.header_values_present)}",
        f"- raw_request_present: {_bool_text(result.raw_request_present)}",
        f"- raw_response_present: {_bool_text(result.raw_response_present)}",
        f"- real_ids_present: {_bool_text(result.real_ids_present)}",
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
    interface_input: LiveOrderRealHttpTransportInterfaceInput,
    contract: LiveOrderRealHttpTransportInterfaceContract,
) -> tuple[LiveOrderRealHttpTransportInterfaceCheckResult, ...]:
    return (
        LiveOrderRealHttpTransportInterfaceCheckResult(
            name="interface input",
            passed=not _input_reasons(interface_input, contract),
            sanitized_value=(
                "ready"
                if not _input_reasons(interface_input, contract)
                else ",".join(_input_reasons(interface_input, contract))
            ),
            expected="INTERFACE_ONLY POST /v1/order and ready prerequisites",
        ),
        LiveOrderRealHttpTransportInterfaceCheckResult(
            name="transport disabled",
            passed=not _merge_reasons(
                _real_transport_reasons(interface_input, contract),
                _http_client_reasons(interface_input, contract),
                _http_post_reasons(interface_input, contract),
                _order_endpoint_reasons(interface_input, contract),
                _live_order_once_reasons(interface_input, contract),
            ),
            sanitized_value="disabled",
            expected="no real transport client post endpoint or live_order_once",
        ),
        LiveOrderRealHttpTransportInterfaceCheckResult(
            name="no raw secret or real ID exposure",
            passed=not _merge_reasons(
                _raw_or_secret_reasons(interface_input, contract),
                _real_id_reasons(interface_input, contract),
            ),
            sanitized_value="none",
            expected="no credentials signatures header values raw data or real IDs",
        ),
        LiveOrderRealHttpTransportInterfaceCheckResult(
            name="one shot no retry",
            passed=not _retry_or_loop_reasons(interface_input, contract),
            sanitized_value="ready"
            if not _retry_or_loop_reasons(interface_input, contract)
            else ",".join(_retry_or_loop_reasons(interface_input, contract)),
            expected="limit=1 before=0 retry=false loop=false",
        ),
    )


def _input_reasons(
    interface_input: LiveOrderRealHttpTransportInterfaceInput,
    contract: LiveOrderRealHttpTransportInterfaceContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if interface_input.interface_mode != HttpTransportInterfaceMode.INTERFACE_ONLY.value:
        reasons.append("interface_mode_not_interface_only")
    if contract.interface_mode != HttpTransportInterfaceMode.INTERFACE_ONLY.value:
        reasons.append("contract_mode_not_interface_only")
    if interface_input.method != HTTP_TRANSPORT_INTERFACE_METHOD:
        reasons.append("method_not_post")
    if interface_input.path != TRANSPORT_CORE_ORDER_PATH:
        reasons.append("path_not_order_contract")
    for field_name in (
        "endpoint_contract_ready",
        "order_body_allowlist_passed",
        "stable_serialization_ready",
        "signing_contract_ready",
        "dummy_signing_ready",
        "dummy_signature_check_passed",
        "private_order_transport_contract_ready",
        "one_shot_no_retry_ready",
    ):
        if not getattr(interface_input, field_name):
            reasons.append(f"{field_name}_false")
    if contract.max_attempts != 1:
        reasons.append("contract_max_attempts_not_one")
    return tuple(reasons)


def _real_transport_reasons(
    interface_input: LiveOrderRealHttpTransportInterfaceInput,
    contract: LiveOrderRealHttpTransportInterfaceContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if interface_input.real_transport_requested:
        reasons.append("real_transport_requested")
    if contract.real_transport_requested:
        reasons.append("contract_real_transport_requested")
    return tuple(reasons)


def _http_client_reasons(
    interface_input: LiveOrderRealHttpTransportInterfaceInput,
    contract: LiveOrderRealHttpTransportInterfaceContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if interface_input.http_client_present:
        reasons.append("http_client_present")
    if contract.http_client_present:
        reasons.append("contract_http_client_present")
    return tuple(reasons)


def _http_post_reasons(
    interface_input: LiveOrderRealHttpTransportInterfaceInput,
    contract: LiveOrderRealHttpTransportInterfaceContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if interface_input.can_execute_http_post:
        reasons.append("can_execute_http_post")
    if contract.can_execute_http_post:
        reasons.append("contract_can_execute_http_post")
    return tuple(reasons)


def _order_endpoint_reasons(
    interface_input: LiveOrderRealHttpTransportInterfaceInput,
    contract: LiveOrderRealHttpTransportInterfaceContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if interface_input.can_call_order_endpoint:
        reasons.append("can_call_order_endpoint")
    if contract.can_call_order_endpoint:
        reasons.append("contract_can_call_order_endpoint")
    return tuple(reasons)


def _live_order_once_reasons(
    interface_input: LiveOrderRealHttpTransportInterfaceInput,
    contract: LiveOrderRealHttpTransportInterfaceContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if interface_input.can_call_live_order_once:
        reasons.append("can_call_live_order_once")
    if contract.can_call_live_order_once:
        reasons.append("contract_can_call_live_order_once")
    return tuple(reasons)


def _raw_or_secret_reasons(
    interface_input: LiveOrderRealHttpTransportInterfaceInput,
    contract: LiveOrderRealHttpTransportInterfaceContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "credential_values_provided",
        "signature_value_generated",
        "header_values_present",
        "raw_request_present",
        "raw_response_present",
    ):
        if getattr(interface_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    for field_name in (
        "can_accept_credential_values",
        "can_accept_signature_values",
        "can_accept_header_values",
        "can_hold_raw_request",
        "can_hold_raw_response",
    ):
        if getattr(contract, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_id_reasons(
    interface_input: LiveOrderRealHttpTransportInterfaceInput,
    contract: LiveOrderRealHttpTransportInterfaceContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if interface_input.real_ids_present:
        reasons.append("real_ids_present")
    if contract.can_hold_real_ids:
        reasons.append("contract_can_hold_real_ids")
    return tuple(reasons)


def _retry_or_loop_reasons(
    interface_input: LiveOrderRealHttpTransportInterfaceInput,
    contract: LiveOrderRealHttpTransportInterfaceContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if interface_input.post_attempt_limit != 1:
        reasons.append("post_attempt_limit_not_one")
    if interface_input.post_attempt_count_before != 0:
        reasons.append("post_attempt_count_before_not_zero")
    if contract.max_attempts != 1:
        reasons.append("contract_max_attempts_not_one")
    for field_name in (
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(interface_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _unsupported_reasons(
    interface_input: LiveOrderRealHttpTransportInterfaceInput,
    contract: LiveOrderRealHttpTransportInterfaceContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if interface_input.post_allowed_this_step:
        reasons.append("post_allowed_this_step_true")
    if interface_input.post_executed:
        reasons.append("post_executed_true")
    if contract.max_attempts < 1:
        reasons.append("contract_max_attempts_zero")
    return tuple(reasons)


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _validate_result_safety(result: LiveOrderRealHttpTransportInterfaceResult) -> None:
    unsafe_flags = (
        result.http_client_present,
        result.can_execute_http_post,
        result.can_call_order_endpoint,
        result.can_call_live_order_once,
        result.credential_values_provided,
        result.signature_value_generated,
        result.header_values_present,
        result.raw_request_present,
        result.raw_response_present,
        result.real_ids_present,
        result.post_allowed_this_step,
        result.post_executed,
        result.retry_allowed,
        result.loop_allowed,
    )
    if any(unsafe_flags):
        raise LiveVerificationValidationError(
            "HTTP transport interface result must stay no API no POST",
        )


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
