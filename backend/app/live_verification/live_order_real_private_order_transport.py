"""Step 6G private order transport contract, no API and no POST.

This module validates contract-only prerequisites and classifies sanitized
transport outcomes for a future real transport step. It does not import an HTTP
client, call Private API, call an order endpoint, use live_order_once, or carry
raw responses, secrets, or real IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_order_transport_core import (
    TRANSPORT_CORE_ORDER_PATH,
)
from app.live_verification.live_order_real_signing_contract import (
    LiveOrderRealSigningContractResult,
    SigningContractStatus,
)

PRIVATE_ORDER_TRANSPORT_METHOD = "POST"
PRIVATE_ORDER_TRANSPORT_MODE = "CONTRACT_ONLY"
PRIVATE_ORDER_TRANSPORT_RECOMMENDED_NEXT_STEP = (
    "future_real_transport_execution_must_be_a_separate_step_with_new_confirmation"
)


class LiveOrderRealPrivateOrderTransportStatus(str, Enum):
    PRIVATE_ORDER_TRANSPORT_CONTRACT_READY_NO_API_NO_POST = (
        "PRIVATE_ORDER_TRANSPORT_CONTRACT_READY_NO_API_NO_POST"
    )
    PRIVATE_ORDER_TRANSPORT_RESULT_CLASSIFIED_NO_RETRY = (
        "PRIVATE_ORDER_TRANSPORT_RESULT_CLASSIFIED_NO_RETRY"
    )
    BLOCKED_PRIVATE_ORDER_TRANSPORT_PREREQUISITES = (
        "BLOCKED_PRIVATE_ORDER_TRANSPORT_PREREQUISITES"
    )
    BLOCKED_PRIVATE_ORDER_TRANSPORT_HTTP_POST = "BLOCKED_PRIVATE_ORDER_TRANSPORT_HTTP_POST"
    BLOCKED_PRIVATE_ORDER_TRANSPORT_ORDER_ENDPOINT = (
        "BLOCKED_PRIVATE_ORDER_TRANSPORT_ORDER_ENDPOINT"
    )
    BLOCKED_PRIVATE_ORDER_TRANSPORT_LIVE_ORDER_ONCE = (
        "BLOCKED_PRIVATE_ORDER_TRANSPORT_LIVE_ORDER_ONCE"
    )
    BLOCKED_PRIVATE_ORDER_TRANSPORT_RAW_OR_SECRET_EXPOSURE = (
        "BLOCKED_PRIVATE_ORDER_TRANSPORT_RAW_OR_SECRET_EXPOSURE"
    )
    BLOCKED_PRIVATE_ORDER_TRANSPORT_RETRY_OR_LOOP = (
        "BLOCKED_PRIVATE_ORDER_TRANSPORT_RETRY_OR_LOOP"
    )
    BLOCKED_PRIVATE_ORDER_TRANSPORT_REAL_ID_EXPOSURE = (
        "BLOCKED_PRIVATE_ORDER_TRANSPORT_REAL_ID_EXPOSURE"
    )
    BLOCKED_PRIVATE_ORDER_TRANSPORT_UNSUPPORTED = (
        "BLOCKED_PRIVATE_ORDER_TRANSPORT_UNSUPPORTED"
    )


class LiveOrderRealPrivateOrderTransportResultCategory(str, Enum):
    PRIVATE_ORDER_TRANSPORT_CONTRACT_READY_NO_API_NO_POST = (
        "PRIVATE_ORDER_TRANSPORT_CONTRACT_READY_NO_API_NO_POST"
    )
    PRIVATE_ORDER_TRANSPORT_SUCCESS_SANITIZED_CONTRACT_ONLY = (
        "PRIVATE_ORDER_TRANSPORT_SUCCESS_SANITIZED_CONTRACT_ONLY"
    )
    PRIVATE_ORDER_TRANSPORT_API_REJECTED_SANITIZED_NO_RETRY = (
        "PRIVATE_ORDER_TRANSPORT_API_REJECTED_SANITIZED_NO_RETRY"
    )
    PRIVATE_ORDER_TRANSPORT_TIMEOUT_SANITIZED_NO_RETRY = (
        "PRIVATE_ORDER_TRANSPORT_TIMEOUT_SANITIZED_NO_RETRY"
    )
    PRIVATE_ORDER_TRANSPORT_ERROR_SANITIZED_NO_RETRY = (
        "PRIVATE_ORDER_TRANSPORT_ERROR_SANITIZED_NO_RETRY"
    )
    PRIVATE_ORDER_TRANSPORT_RESULT_UNKNOWN_SANITIZED_NO_RETRY = (
        "PRIVATE_ORDER_TRANSPORT_RESULT_UNKNOWN_SANITIZED_NO_RETRY"
    )
    PRIVATE_ORDER_TRANSPORT_BLOCKED_RAW_OR_SECRET_EXPOSURE = (
        "PRIVATE_ORDER_TRANSPORT_BLOCKED_RAW_OR_SECRET_EXPOSURE"
    )
    PRIVATE_ORDER_TRANSPORT_BLOCKED_RETRY_OR_LOOP = (
        "PRIVATE_ORDER_TRANSPORT_BLOCKED_RETRY_OR_LOOP"
    )
    PRIVATE_ORDER_TRANSPORT_BLOCKED_UNSUPPORTED = (
        "PRIVATE_ORDER_TRANSPORT_BLOCKED_UNSUPPORTED"
    )


PrivateOrderTransportStatus = LiveOrderRealPrivateOrderTransportStatus
PrivateOrderTransportResultCategory = LiveOrderRealPrivateOrderTransportResultCategory


@dataclass(frozen=True)
class LiveOrderRealPrivateOrderTransportPrerequisites:
    transport_contract_mode: str = PRIVATE_ORDER_TRANSPORT_MODE
    signing_contract_ready: bool = True
    redacted_header_contract_ready: bool = True
    order_body_allowlist_passed: bool = True
    stable_serialization_ready: bool = True
    endpoint_contract_ready: bool = True
    method: str = PRIVATE_ORDER_TRANSPORT_METHOD
    path: str = TRANSPORT_CORE_ORDER_PATH
    post_attempt_limit: int = 1
    post_attempt_count_before: int = 0
    retry_allowed: bool = False
    loop_allowed: bool = False
    add_order_allowed: bool = False
    change_order_allowed: bool = False
    cancel_order_allowed: bool = False
    close_order_allowed: bool = False
    raw_request_displayed: bool = False
    raw_request_saved: bool = False
    raw_response_displayed: bool = False
    raw_response_saved: bool = False
    headers_displayed: bool = False
    headers_saved: bool = False
    signature_displayed: bool = False
    signature_saved: bool = False
    credentials_displayed: bool = False
    credentials_saved: bool = False
    real_ids_displayed: bool = False
    real_ids_saved: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("transport_contract_mode", self.transport_contract_mode)
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
                "signing_contract_ready",
                "redacted_header_contract_ready",
                "order_body_allowlist_passed",
                "stable_serialization_ready",
                "endpoint_contract_ready",
                "retry_allowed",
                "loop_allowed",
                "add_order_allowed",
                "change_order_allowed",
                "cancel_order_allowed",
                "close_order_allowed",
                "raw_request_displayed",
                "raw_request_saved",
                "raw_response_displayed",
                "raw_response_saved",
                "headers_displayed",
                "headers_saved",
                "signature_displayed",
                "signature_saved",
                "credentials_displayed",
                "credentials_saved",
                "real_ids_displayed",
                "real_ids_saved",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealPrivateOrderTransportContract:
    transport_contract_mode: str = PRIVATE_ORDER_TRANSPORT_MODE
    imports_http_client: bool = False
    imports_private_api: bool = False
    imports_broker: bool = False
    imports_live_order_once: bool = False
    can_execute_http_post: bool = False
    can_call_order_endpoint: bool = False
    can_call_live_order_once: bool = False
    can_display_raw_or_secret: bool = False
    can_display_real_ids: bool = False
    max_attempts: int = 1

    def __post_init__(self) -> None:
        _require_non_empty("transport_contract_mode", self.transport_contract_mode)
        _validate_non_negative_int("max_attempts", self.max_attempts)
        _validate_bool_fields(
            self,
            (
                "imports_http_client",
                "imports_private_api",
                "imports_broker",
                "imports_live_order_once",
                "can_execute_http_post",
                "can_call_order_endpoint",
                "can_call_live_order_once",
                "can_display_raw_or_secret",
                "can_display_real_ids",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealPrivateOrderSanitizedResultInput:
    sanitized_result_kind: str
    raw_request_present: bool = False
    raw_response_present: bool = False
    headers_present: bool = False
    signature_value_present: bool = False
    credentials_present: bool = False
    real_order_id_present: bool = False
    real_execution_id_present: bool = False
    real_position_id_present: bool = False
    real_client_order_id_present: bool = False
    retry_on_unknown: bool = False
    retry_on_timeout: bool = False
    retry_on_reject: bool = False
    retry_count: int = 0
    loop_count: int = 0

    def __post_init__(self) -> None:
        _require_non_empty("sanitized_result_kind", self.sanitized_result_kind)
        _validate_non_negative_int("retry_count", self.retry_count)
        _validate_non_negative_int("loop_count", self.loop_count)
        _validate_bool_fields(
            self,
            (
                "raw_request_present",
                "raw_response_present",
                "headers_present",
                "signature_value_present",
                "credentials_present",
                "real_order_id_present",
                "real_execution_id_present",
                "real_position_id_present",
                "real_client_order_id_present",
                "retry_on_unknown",
                "retry_on_timeout",
                "retry_on_reject",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealPrivateOrderSanitizedResult:
    result_category: LiveOrderRealPrivateOrderTransportResultCategory
    raw_or_secret_exposure: bool
    real_id_exposure: bool
    retry_count: int
    loop_count: int

    def __post_init__(self) -> None:
        if not isinstance(
            self.result_category,
            LiveOrderRealPrivateOrderTransportResultCategory,
        ):
            raise LiveVerificationValidationError("result_category must be transport category")
        _validate_non_negative_int("retry_count", self.retry_count)
        _validate_non_negative_int("loop_count", self.loop_count)
        _validate_bool_fields(self, ("raw_or_secret_exposure", "real_id_exposure"))


@dataclass(frozen=True)
class LiveOrderRealPrivateOrderTransportCheckResult:
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
class LiveOrderRealPrivateOrderTransportResult:
    status: LiveOrderRealPrivateOrderTransportStatus
    transport_contract_ready: bool
    transport_result_category: str
    signing_contract_ready: bool
    redacted_header_contract_ready: bool
    method: str
    path: str
    post_attempt_limit: int
    post_attempt_count_before: int
    no_api_executed: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_executed: bool
    retry_allowed: bool
    loop_allowed: bool
    sanitized_transport_result: LiveOrderRealPrivateOrderSanitizedResult | None
    check_results: tuple[LiveOrderRealPrivateOrderTransportCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealPrivateOrderTransportStatus):
            raise LiveVerificationValidationError("status must be private transport status")
        _validate_non_negative_int("post_attempt_limit", self.post_attempt_limit)
        _validate_non_negative_int(
            "post_attempt_count_before",
            self.post_attempt_count_before,
        )
        _validate_bool_fields(
            self,
            (
                "transport_contract_ready",
                "signing_contract_ready",
                "redacted_header_contract_ready",
                "no_api_executed",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "retry_allowed",
                "loop_allowed",
            ),
        )
        _require_non_empty("transport_result_category", self.transport_result_category)
        _require_non_empty("method", self.method)
        _require_non_empty("path", self.path)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        if self.http_post_executed:
            raise LiveVerificationValidationError("transport contract must not execute POST")
        if self.order_endpoint_called:
            raise LiveVerificationValidationError("transport contract must not call endpoint")
        if self.live_order_once_called:
            raise LiveVerificationValidationError(
                "transport contract must not call live_order_once",
            )
        if self.post_allowed_this_step:
            raise LiveVerificationValidationError("transport contract must not allow POST")
        if self.post_executed:
            raise LiveVerificationValidationError("transport contract must not mark post executed")


def validate_real_transport_prerequisites(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
) -> LiveOrderRealPrivateOrderTransportCheckResult:
    reasons = _prerequisite_reasons(prerequisites)
    return LiveOrderRealPrivateOrderTransportCheckResult(
        name="private order transport prerequisites",
        passed=not reasons,
        sanitized_value="ready" if not reasons else ",".join(reasons),
        expected="contract-only ready and no execution flags",
    )


def classify_private_order_transport_result_safely(
    sanitized_result_input: LiveOrderRealPrivateOrderSanitizedResultInput,
) -> LiveOrderRealPrivateOrderSanitizedResult:
    raw_reasons = _result_raw_or_secret_reasons(sanitized_result_input)
    real_id_reasons = _result_real_id_reasons(sanitized_result_input)
    retry_reasons = _result_retry_reasons(sanitized_result_input)
    if raw_reasons:
        category = (
            PrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_BLOCKED_RAW_OR_SECRET_EXPOSURE
        )
    elif real_id_reasons:
        category = (
            PrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_BLOCKED_RAW_OR_SECRET_EXPOSURE
        )
    elif retry_reasons:
        category = (
            PrivateOrderTransportResultCategory.PRIVATE_ORDER_TRANSPORT_BLOCKED_RETRY_OR_LOOP
        )
    else:
        category = _result_kind_category(sanitized_result_input.sanitized_result_kind)
    return LiveOrderRealPrivateOrderSanitizedResult(
        result_category=category,
        raw_or_secret_exposure=bool(raw_reasons),
        real_id_exposure=bool(real_id_reasons),
        retry_count=sanitized_result_input.retry_count,
        loop_count=sanitized_result_input.loop_count,
    )


def enforce_one_post_no_retry_contract(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
    contract: LiveOrderRealPrivateOrderTransportContract | None = None,
    sanitized_result_input: LiveOrderRealPrivateOrderSanitizedResultInput | None = None,
) -> LiveOrderRealPrivateOrderTransportCheckResult:
    reasons = _retry_or_loop_reasons(prerequisites, contract, sanitized_result_input)
    return LiveOrderRealPrivateOrderTransportCheckResult(
        name="one post no retry",
        passed=not reasons,
        sanitized_value="ready" if not reasons else ",".join(reasons),
        expected="limit=1 before=0 retry=false loop=false",
    )


def ensure_no_raw_or_secret_or_real_id_exposure(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
    contract: LiveOrderRealPrivateOrderTransportContract | None = None,
    sanitized_result_input: LiveOrderRealPrivateOrderSanitizedResultInput | None = None,
) -> LiveOrderRealPrivateOrderTransportCheckResult:
    reasons = _merge_reasons(
        _raw_or_secret_reasons(prerequisites, contract),
        _real_id_reasons(prerequisites, contract),
        _result_raw_or_secret_reasons(sanitized_result_input)
        if sanitized_result_input
        else (),
        _result_real_id_reasons(sanitized_result_input) if sanitized_result_input else (),
    )
    return LiveOrderRealPrivateOrderTransportCheckResult(
        name="no raw secret or real ID exposure",
        passed=not reasons,
        sanitized_value="none" if not reasons else ",".join(reasons),
        expected="none",
    )


def build_live_order_real_private_order_transport_contract(
    *,
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites | None = None,
    transport_contract: LiveOrderRealPrivateOrderTransportContract | None = None,
    signing_contract_result: LiveOrderRealSigningContractResult | None = None,
    sanitized_result_input: LiveOrderRealPrivateOrderSanitizedResultInput | None = None,
) -> LiveOrderRealPrivateOrderTransportResult:
    """Build the no-API/no-POST private order transport contract decision."""
    prereq = prerequisites or LiveOrderRealPrivateOrderTransportPrerequisites()
    contract = transport_contract or LiveOrderRealPrivateOrderTransportContract()
    sanitized_result = (
        classify_private_order_transport_result_safely(sanitized_result_input)
        if sanitized_result_input
        else None
    )

    signing_reasons = _signing_result_reasons(signing_contract_result)
    prereq_reasons = (*_prerequisite_reasons(prereq), *signing_reasons)
    http_post_reasons = _http_post_reasons(prereq, contract, sanitized_result_input)
    endpoint_reasons = _endpoint_called_reasons(prereq, contract)
    live_once_reasons = _live_order_once_reasons(prereq, contract)
    raw_reasons = _raw_or_secret_reasons(prereq, contract)
    real_id_reasons = _real_id_reasons(prereq, contract)
    retry_reasons = _retry_or_loop_reasons(prereq, contract, sanitized_result_input)
    result_raw_reasons = (
        _result_raw_or_secret_reasons(sanitized_result_input)
        if sanitized_result_input
        else ()
    )
    result_id_reasons = (
        _result_real_id_reasons(sanitized_result_input) if sanitized_result_input else ()
    )
    result_retry_reasons = (
        _result_retry_reasons(sanitized_result_input) if sanitized_result_input else ()
    )
    unsupported_reasons = _unsupported_reasons(prereq, contract, sanitized_result)

    if http_post_reasons:
        status = PrivateOrderTransportStatus.BLOCKED_PRIVATE_ORDER_TRANSPORT_HTTP_POST
        primary_reasons = http_post_reasons
    elif endpoint_reasons:
        status = PrivateOrderTransportStatus.BLOCKED_PRIVATE_ORDER_TRANSPORT_ORDER_ENDPOINT
        primary_reasons = endpoint_reasons
    elif live_once_reasons:
        status = PrivateOrderTransportStatus.BLOCKED_PRIVATE_ORDER_TRANSPORT_LIVE_ORDER_ONCE
        primary_reasons = live_once_reasons
    elif raw_reasons or result_raw_reasons:
        status = (
            PrivateOrderTransportStatus
            .BLOCKED_PRIVATE_ORDER_TRANSPORT_RAW_OR_SECRET_EXPOSURE
        )
        primary_reasons = (*raw_reasons, *result_raw_reasons)
    elif real_id_reasons or result_id_reasons:
        status = PrivateOrderTransportStatus.BLOCKED_PRIVATE_ORDER_TRANSPORT_REAL_ID_EXPOSURE
        primary_reasons = (*real_id_reasons, *result_id_reasons)
    elif retry_reasons or result_retry_reasons:
        status = PrivateOrderTransportStatus.BLOCKED_PRIVATE_ORDER_TRANSPORT_RETRY_OR_LOOP
        primary_reasons = (*retry_reasons, *result_retry_reasons)
    elif prereq_reasons:
        status = PrivateOrderTransportStatus.BLOCKED_PRIVATE_ORDER_TRANSPORT_PREREQUISITES
        primary_reasons = prereq_reasons
    elif unsupported_reasons:
        status = PrivateOrderTransportStatus.BLOCKED_PRIVATE_ORDER_TRANSPORT_UNSUPPORTED
        primary_reasons = unsupported_reasons
    elif sanitized_result:
        status = PrivateOrderTransportStatus.PRIVATE_ORDER_TRANSPORT_RESULT_CLASSIFIED_NO_RETRY
        primary_reasons = ()
    else:
        status = PrivateOrderTransportStatus.PRIVATE_ORDER_TRANSPORT_CONTRACT_READY_NO_API_NO_POST
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        prereq_reasons,
        http_post_reasons,
        endpoint_reasons,
        live_once_reasons,
        raw_reasons,
        real_id_reasons,
        retry_reasons,
        result_raw_reasons,
        result_id_reasons,
        result_retry_reasons,
        unsupported_reasons,
    )
    ready = status in {
        PrivateOrderTransportStatus.PRIVATE_ORDER_TRANSPORT_CONTRACT_READY_NO_API_NO_POST,
        PrivateOrderTransportStatus.PRIVATE_ORDER_TRANSPORT_RESULT_CLASSIFIED_NO_RETRY,
    }

    return LiveOrderRealPrivateOrderTransportResult(
        status=status,
        transport_contract_ready=ready,
        transport_result_category=(
            sanitized_result.result_category.value
            if sanitized_result
            else PrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_CONTRACT_READY_NO_API_NO_POST
            .value
        ),
        signing_contract_ready=prereq.signing_contract_ready and not signing_reasons,
        redacted_header_contract_ready=prereq.redacted_header_contract_ready,
        method=prereq.method,
        path=prereq.path,
        post_attempt_limit=prereq.post_attempt_limit,
        post_attempt_count_before=prereq.post_attempt_count_before,
        no_api_executed=True,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_executed=False,
        retry_allowed=False,
        loop_allowed=False,
        sanitized_transport_result=sanitized_result,
        check_results=_build_check_results(
            prereq,
            contract,
            sanitized_result,
            signing_contract_result,
            sanitized_result_input,
        ),
        blocked_reasons=blocked_reasons,
        recommended_next_step=PRIVATE_ORDER_TRANSPORT_RECOMMENDED_NEXT_STEP,
    )


def render_live_order_real_private_order_transport_markdown(
    result: LiveOrderRealPrivateOrderTransportResult,
) -> str:
    """Render sanitized transport contract metadata without raw or secret values."""
    lines = [
        "# Step 6G Private Order Transport Contract",
        "",
        "This signing contract does not use real credentials.",
        "This signing contract does not generate real signatures.",
        "This transport contract does not execute API calls.",
        "This transport contract does not execute HTTP POST.",
        "This transport contract does not call order endpoint.",
        "This transport contract does not call live_order_once.",
        "Future real signing and real transport must be a separate Step.",
        "",
        "## Status",
        f"- transport_status: {result.status.value}",
        f"- transport_contract_ready: {_bool_text(result.transport_contract_ready)}",
        f"- method: {result.method}",
        f"- path: {result.path}",
        f"- transport_result_category: {result.transport_result_category}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- retry_allowed: {_bool_text(result.retry_allowed)}",
        f"- loop_allowed: {_bool_text(result.loop_allowed)}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Check Results",
        *[
            (
                f"- {check.name}: {_bool_text(check.passed)} "
                f"({check.sanitized_value}; expected {check.expected})"
            )
            for check in result.check_results
        ],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def _build_check_results(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
    contract: LiveOrderRealPrivateOrderTransportContract,
    sanitized_result: LiveOrderRealPrivateOrderSanitizedResult | None,
    signing_contract_result: LiveOrderRealSigningContractResult | None,
    sanitized_result_input: LiveOrderRealPrivateOrderSanitizedResultInput | None,
) -> tuple[LiveOrderRealPrivateOrderTransportCheckResult, ...]:
    signing_reasons = _signing_result_reasons(signing_contract_result)
    return (
        validate_real_transport_prerequisites(prerequisites),
        LiveOrderRealPrivateOrderTransportCheckResult(
            name="signing contract",
            passed=not signing_reasons,
            sanitized_value="ready" if not signing_reasons else ",".join(signing_reasons),
            expected="ready no credential no signature",
        ),
        enforce_one_post_no_retry_contract(
            prerequisites,
            contract,
            sanitized_result_input,
        ),
        ensure_no_raw_or_secret_or_real_id_exposure(
            prerequisites,
            contract,
            sanitized_result_input,
        ),
        LiveOrderRealPrivateOrderTransportCheckResult(
            name="sanitized result classification",
            passed=(
                sanitized_result is None
                or sanitized_result.result_category
                not in {
                    PrivateOrderTransportResultCategory
                    .PRIVATE_ORDER_TRANSPORT_BLOCKED_RAW_OR_SECRET_EXPOSURE,
                    PrivateOrderTransportResultCategory
                    .PRIVATE_ORDER_TRANSPORT_BLOCKED_RETRY_OR_LOOP,
                    PrivateOrderTransportResultCategory.PRIVATE_ORDER_TRANSPORT_BLOCKED_UNSUPPORTED,
                }
            ),
            sanitized_value=(
                sanitized_result.result_category.value
                if sanitized_result
                else "not_classified"
            ),
            expected="sanitized contract category or not_classified",
        ),
    )


def _signing_result_reasons(
    signing_contract_result: LiveOrderRealSigningContractResult | None,
) -> tuple[str, ...]:
    if signing_contract_result is None:
        return ()
    reasons: list[str] = []
    if (
        signing_contract_result.status
        is not SigningContractStatus.SIGNING_CONTRACT_READY_NO_CREDENTIAL_NO_SIGNATURE
    ):
        reasons.append("signing_status_not_ready")
    if not signing_contract_result.signing_contract_ready:
        reasons.append("signing_contract_not_ready")
    if not signing_contract_result.redacted_header_contract_ready:
        reasons.append("redacted_header_contract_not_ready")
    return tuple(reasons)


def _prerequisite_reasons(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if prerequisites.transport_contract_mode != PRIVATE_ORDER_TRANSPORT_MODE:
        reasons.append("transport_contract_mode_not_contract_only")
    if not prerequisites.signing_contract_ready:
        reasons.append("signing_contract_not_ready")
    if not prerequisites.redacted_header_contract_ready:
        reasons.append("redacted_header_contract_not_ready")
    if not prerequisites.order_body_allowlist_passed:
        reasons.append("order_body_allowlist_failed")
    if not prerequisites.stable_serialization_ready:
        reasons.append("stable_serialization_not_ready")
    if not prerequisites.endpoint_contract_ready:
        reasons.append("endpoint_contract_not_ready")
    if prerequisites.method != PRIVATE_ORDER_TRANSPORT_METHOD:
        reasons.append("method_not_post")
    if prerequisites.path != TRANSPORT_CORE_ORDER_PATH:
        reasons.append("path_not_order_contract")
    return tuple(reasons)


def _http_post_reasons(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
    contract: LiveOrderRealPrivateOrderTransportContract,
    sanitized_result_input: LiveOrderRealPrivateOrderSanitizedResultInput | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if prerequisites.http_post_executed:
        reasons.append("http_post_executed")
    if contract.can_execute_http_post:
        reasons.append("transport_can_execute_http_post")
    if sanitized_result_input and sanitized_result_input.sanitized_result_kind == "real_post":
        reasons.append("sanitized_result_kind_claims_real_post")
    return tuple(reasons)


def _endpoint_called_reasons(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
    contract: LiveOrderRealPrivateOrderTransportContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if prerequisites.order_endpoint_called:
        reasons.append("order_endpoint_called")
    if contract.can_call_order_endpoint:
        reasons.append("transport_can_call_order_endpoint")
    return tuple(reasons)


def _live_order_once_reasons(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
    contract: LiveOrderRealPrivateOrderTransportContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if prerequisites.live_order_once_called:
        reasons.append("live_order_once_called")
    if contract.can_call_live_order_once:
        reasons.append("transport_can_call_live_order_once")
    if contract.imports_live_order_once:
        reasons.append("transport_imports_live_order_once")
    return tuple(reasons)


def _raw_or_secret_reasons(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
    contract: LiveOrderRealPrivateOrderTransportContract | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "raw_request_displayed",
        "raw_request_saved",
        "raw_response_displayed",
        "raw_response_saved",
        "headers_displayed",
        "headers_saved",
        "signature_displayed",
        "signature_saved",
        "credentials_displayed",
        "credentials_saved",
    ):
        if getattr(prerequisites, field_name):
            reasons.append(f"{field_name}_unsafe")
    if contract:
        for field_name in (
            "imports_http_client",
            "imports_private_api",
            "imports_broker",
            "can_display_raw_or_secret",
        ):
            if getattr(contract, field_name):
                reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _real_id_reasons(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
    contract: LiveOrderRealPrivateOrderTransportContract | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if prerequisites.real_ids_displayed:
        reasons.append("real_ids_displayed")
    if prerequisites.real_ids_saved:
        reasons.append("real_ids_saved")
    if contract and contract.can_display_real_ids:
        reasons.append("transport_can_display_real_ids")
    return tuple(reasons)


def _retry_or_loop_reasons(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
    contract: LiveOrderRealPrivateOrderTransportContract | None,
    sanitized_result_input: LiveOrderRealPrivateOrderSanitizedResultInput | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if prerequisites.post_attempt_limit != 1:
        reasons.append("post_attempt_limit_not_one")
    if prerequisites.post_attempt_count_before != 0:
        reasons.append("post_attempt_count_before_not_zero")
    for field_name in (
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
        "post_allowed_this_step",
        "post_executed",
    ):
        if getattr(prerequisites, field_name):
            reasons.append(f"{field_name}_unsafe")
    if contract and contract.max_attempts != 1:
        reasons.append("max_attempts_not_one")
    if sanitized_result_input:
        reasons.extend(_result_retry_reasons(sanitized_result_input))
    return tuple(dict.fromkeys(reasons))


def _result_raw_or_secret_reasons(
    result_input: LiveOrderRealPrivateOrderSanitizedResultInput | None,
) -> tuple[str, ...]:
    if result_input is None:
        return ()
    reasons: list[str] = []
    for field_name in (
        "raw_request_present",
        "raw_response_present",
        "headers_present",
        "signature_value_present",
        "credentials_present",
    ):
        if getattr(result_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _result_real_id_reasons(
    result_input: LiveOrderRealPrivateOrderSanitizedResultInput | None,
) -> tuple[str, ...]:
    if result_input is None:
        return ()
    reasons: list[str] = []
    for field_name in (
        "real_order_id_present",
        "real_execution_id_present",
        "real_position_id_present",
        "real_client_order_id_present",
    ):
        if getattr(result_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _result_retry_reasons(
    result_input: LiveOrderRealPrivateOrderSanitizedResultInput | None,
) -> tuple[str, ...]:
    if result_input is None:
        return ()
    reasons: list[str] = []
    for field_name in ("retry_on_unknown", "retry_on_timeout", "retry_on_reject"):
        if getattr(result_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    if result_input.retry_count:
        reasons.append("retry_count_non_zero")
    if result_input.loop_count:
        reasons.append("loop_count_non_zero")
    return tuple(reasons)


def _unsupported_reasons(
    prerequisites: LiveOrderRealPrivateOrderTransportPrerequisites,
    contract: LiveOrderRealPrivateOrderTransportContract,
    sanitized_result: LiveOrderRealPrivateOrderSanitizedResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if contract.transport_contract_mode != PRIVATE_ORDER_TRANSPORT_MODE:
        reasons.append("transport_contract_mode_unsupported")
    if prerequisites.transport_contract_mode != PRIVATE_ORDER_TRANSPORT_MODE:
        reasons.append("prerequisites_contract_mode_unsupported")
    if sanitized_result and (
        sanitized_result.result_category
        is PrivateOrderTransportResultCategory.PRIVATE_ORDER_TRANSPORT_BLOCKED_UNSUPPORTED
    ):
        reasons.append("sanitized_result_unsupported")
    return tuple(reasons)


def _result_kind_category(
    result_kind: str,
) -> LiveOrderRealPrivateOrderTransportResultCategory:
    mapping = {
        "success": (
            PrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_SUCCESS_SANITIZED_CONTRACT_ONLY
        ),
        "api_rejected": (
            PrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_API_REJECTED_SANITIZED_NO_RETRY
        ),
        "timeout": (
            PrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_TIMEOUT_SANITIZED_NO_RETRY
        ),
        "transport_error": (
            PrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_ERROR_SANITIZED_NO_RETRY
        ),
        "result_unknown": (
            PrivateOrderTransportResultCategory
            .PRIVATE_ORDER_TRANSPORT_RESULT_UNKNOWN_SANITIZED_NO_RETRY
        ),
    }
    return mapping.get(
        result_kind,
        PrivateOrderTransportResultCategory.PRIVATE_ORDER_TRANSPORT_BLOCKED_UNSUPPORTED,
    )


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
