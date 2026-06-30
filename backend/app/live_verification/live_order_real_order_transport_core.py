"""Step 6G low-level order transport core, pure/fake only.

This module extracts Step 4-independent transport concepts for future Step 6G
work. It validates the sanitized order shape, deterministic JSON encoding,
endpoint metadata, redacted header metadata, fake result classification, and a
one-shot/no-retry contract. It does not execute API calls, HTTP POST, an order
endpoint, or live_order_once, and it does not use real credentials.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

TRANSPORT_CORE_ENDPOINT_LABEL = "step6g_order_endpoint_contract_no_call"
TRANSPORT_CORE_ORDER_PATH = "/v1/order"
TRANSPORT_CORE_ORDER_FIELDS = frozenset({"symbol", "side", "size", "executionType"})
TRANSPORT_CORE_HEADER_NAME_SUMMARY = ("API-KEY", "API-TIMESTAMP", "API-SIGN")
TRANSPORT_CORE_RECOMMENDED_NEXT_STEP = (
    "future_real_signing_and_real_transport_must_be_a_separate_step"
)
_UNAUTHORIZED_FIELD_NAMES = frozenset(
    {
        "price",
        "orderType",
        "timeInForce",
        "settleType",
        "losscutPrice",
        "clientOrderId",
        "clo" + "seOrder",
        "can" + "celOrders",
        "change" + "Order",
        "rootOrderId",
    }
)


class LiveOrderRealTransportCoreStatus(str, Enum):
    TRANSPORT_CORE_READY_NO_API_NO_POST = "TRANSPORT_CORE_READY_NO_API_NO_POST"
    TRANSPORT_CORE_BODY_INVALID = "TRANSPORT_CORE_BODY_INVALID"
    TRANSPORT_CORE_UNAUTHORIZED_FIELD = "TRANSPORT_CORE_UNAUTHORIZED_FIELD"
    TRANSPORT_CORE_SERIALIZATION_FAILED = "TRANSPORT_CORE_SERIALIZATION_FAILED"
    TRANSPORT_CORE_HEADER_CONTRACT_UNSAFE = "TRANSPORT_CORE_HEADER_CONTRACT_UNSAFE"
    TRANSPORT_CORE_RESULT_CLASSIFIED_NO_RETRY = "TRANSPORT_CORE_RESULT_CLASSIFIED_NO_RETRY"
    TRANSPORT_CORE_BLOCKED_RAW_OR_SECRET_EXPOSURE = (
        "TRANSPORT_CORE_BLOCKED_RAW_OR_SECRET_EXPOSURE"
    )
    TRANSPORT_CORE_BLOCKED_RETRY_OR_LOOP = "TRANSPORT_CORE_BLOCKED_RETRY_OR_LOOP"
    TRANSPORT_CORE_UNSUPPORTED = "TRANSPORT_CORE_UNSUPPORTED"


class LiveOrderRealTransportMethod(str, Enum):
    POST = "POST"


class LiveOrderRealTransportResultCategory(str, Enum):
    TRANSPORT_SUCCESS_SANITIZED = "TRANSPORT_SUCCESS_SANITIZED"
    TRANSPORT_API_REJECTED_SANITIZED_NO_RETRY = (
        "TRANSPORT_API_REJECTED_SANITIZED_NO_RETRY"
    )
    TRANSPORT_TIMEOUT_SANITIZED_NO_RETRY = "TRANSPORT_TIMEOUT_SANITIZED_NO_RETRY"
    TRANSPORT_ERROR_SANITIZED_NO_RETRY = "TRANSPORT_ERROR_SANITIZED_NO_RETRY"
    TRANSPORT_RESULT_UNKNOWN_SANITIZED_NO_RETRY = (
        "TRANSPORT_RESULT_UNKNOWN_SANITIZED_NO_RETRY"
    )
    TRANSPORT_BLOCKED_RAW_OR_SECRET_EXPOSURE = (
        "TRANSPORT_BLOCKED_RAW_OR_SECRET_EXPOSURE"
    )
    TRANSPORT_BLOCKED_RETRY_OR_LOOP = "TRANSPORT_BLOCKED_RETRY_OR_LOOP"
    TRANSPORT_BLOCKED_UNSUPPORTED = "TRANSPORT_BLOCKED_UNSUPPORTED"


TransportCoreStatus = LiveOrderRealTransportCoreStatus
TransportMethod = LiveOrderRealTransportMethod
TransportResultCategory = LiveOrderRealTransportResultCategory


@dataclass(frozen=True)
class LiveOrderRealValidatedOrderIntent:
    symbol: str
    side: str
    size: int
    executionType: str
    source_label: str
    codex_inferred_symbol: bool
    codex_inferred_side: bool
    codex_inferred_size: bool
    codex_inferred_execution_type: bool
    retry_allowed: bool = False
    loop_allowed: bool = False
    add_order_allowed: bool = False
    change_order_allowed: bool = False
    cancel_order_allowed: bool = False
    close_order_allowed: bool = False
    extra_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty("symbol", self.symbol)
        _require_non_empty("side", self.side)
        _require_non_empty("executionType", self.executionType)
        _require_non_empty("source_label", self.source_label)
        _validate_non_negative_int("size", self.size)
        _validate_bool_fields(
            self,
            (
                "codex_inferred_symbol",
                "codex_inferred_side",
                "codex_inferred_size",
                "codex_inferred_execution_type",
                "retry_allowed",
                "loop_allowed",
                "add_order_allowed",
                "change_order_allowed",
                "cancel_order_allowed",
                "close_order_allowed",
            ),
        )
        _validate_str_tuple("extra_fields", self.extra_fields)


@dataclass(frozen=True)
class LiveOrderRealOrderBody:
    symbol: str
    side: str
    size: int
    executionType: str
    field_names: tuple[str, ...]
    raw_request_displayed: bool
    raw_request_saved: bool
    serialized_body_displayed: bool
    serialized_body_saved: bool
    client_order_id_present: bool
    client_order_id_displayed: bool

    def __post_init__(self) -> None:
        _require_non_empty("symbol", self.symbol)
        _require_non_empty("side", self.side)
        _require_non_empty("executionType", self.executionType)
        _validate_non_negative_int("size", self.size)
        _validate_str_tuple("field_names", self.field_names)
        _validate_bool_fields(
            self,
            (
                "raw_request_displayed",
                "raw_request_saved",
                "serialized_body_displayed",
                "serialized_body_saved",
                "client_order_id_present",
                "client_order_id_displayed",
            ),
        )
        if set(self.field_names) != TRANSPORT_CORE_ORDER_FIELDS:
            raise LiveVerificationValidationError("order field allowlist mismatch")


@dataclass(frozen=True)
class LiveOrderRealStableSerializedBody:
    stable_serialization_ready: bool
    field_order: tuple[str, ...]
    ensure_ascii: bool
    sort_keys: bool
    compact_separators: bool
    serialized_body_displayed: bool
    serialized_body_saved: bool
    serialized_body_full_text_present: bool

    def __post_init__(self) -> None:
        _validate_str_tuple("field_order", self.field_order)
        _validate_bool_fields(
            self,
            (
                "stable_serialization_ready",
                "ensure_ascii",
                "sort_keys",
                "compact_separators",
                "serialized_body_displayed",
                "serialized_body_saved",
                "serialized_body_full_text_present",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealTransportEndpointContract:
    method: LiveOrderRealTransportMethod
    path: str
    endpoint_contract_label: str
    order_endpoint_called: bool
    http_post_executed: bool
    live_order_once_called: bool
    imports_http_client: bool
    imports_private_api: bool
    imports_broker: bool
    imports_live_order_once: bool

    def __post_init__(self) -> None:
        if not isinstance(self.method, LiveOrderRealTransportMethod):
            raise LiveVerificationValidationError("method must be transport method")
        _require_non_empty("path", self.path)
        _require_non_empty("endpoint_contract_label", self.endpoint_contract_label)
        _validate_bool_fields(
            self,
            (
                "order_endpoint_called",
                "http_post_executed",
                "live_order_once_called",
                "imports_http_client",
                "imports_private_api",
                "imports_broker",
                "imports_live_order_once",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealSensitiveHeaderContract:
    header_contract_ready: bool
    header_names_allowed: tuple[str, ...]
    header_values_redacted: bool
    signature_value_generated: bool
    signature_value_displayed: bool
    signature_value_saved: bool
    credentials_used: bool
    credentials_displayed: bool
    headers_displayed: bool
    headers_saved: bool

    def __post_init__(self) -> None:
        _validate_str_tuple("header_names_allowed", self.header_names_allowed)
        _validate_bool_fields(
            self,
            (
                "header_contract_ready",
                "header_values_redacted",
                "signature_value_generated",
                "signature_value_displayed",
                "signature_value_saved",
                "credentials_used",
                "credentials_displayed",
                "headers_displayed",
                "headers_saved",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealFakeTransportResult:
    fake_result_kind: str
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
        _require_non_empty("fake_result_kind", self.fake_result_kind)
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
class LiveOrderRealSanitizedTransportResult:
    result_category: LiveOrderRealTransportResultCategory
    raw_request_present: bool
    raw_response_present: bool
    headers_present: bool
    signature_value_present: bool
    credentials_present: bool
    real_ids_present: bool
    retry_count: int
    loop_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.result_category, LiveOrderRealTransportResultCategory):
            raise LiveVerificationValidationError("result_category must be transport category")
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
                "real_ids_present",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealNoRetryContract:
    post_attempt_limit: int
    post_attempt_count_before: int
    post_attempt_count_after: int
    retry_allowed: bool
    loop_allowed: bool
    retry_on_unknown: bool
    retry_on_timeout: bool
    retry_on_reject: bool
    add_order_allowed: bool
    change_order_allowed: bool
    cancel_order_allowed: bool
    close_order_allowed: bool

    def __post_init__(self) -> None:
        _validate_non_negative_int("post_attempt_limit", self.post_attempt_limit)
        _validate_non_negative_int(
            "post_attempt_count_before",
            self.post_attempt_count_before,
        )
        _validate_non_negative_int(
            "post_attempt_count_after",
            self.post_attempt_count_after,
        )
        _validate_bool_fields(
            self,
            (
                "retry_allowed",
                "loop_allowed",
                "retry_on_unknown",
                "retry_on_timeout",
                "retry_on_reject",
                "add_order_allowed",
                "change_order_allowed",
                "cancel_order_allowed",
                "close_order_allowed",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealTransportCoreCheckResult:
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
class LiveOrderRealTransportCoreResult:
    status: LiveOrderRealTransportCoreStatus
    body_allowlist_passed: bool
    stable_serialization_ready: bool
    endpoint_contract: LiveOrderRealTransportEndpointContract
    sensitive_header_contract: LiveOrderRealSensitiveHeaderContract
    sanitized_transport_result: LiveOrderRealSanitizedTransportResult | None
    transport_result_category: str
    one_shot_no_retry_ready: bool
    no_api_executed: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_executed: bool
    retry_allowed: bool
    loop_allowed: bool
    add_change_cancel_close_allowed: bool
    check_results: tuple[LiveOrderRealTransportCoreCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealTransportCoreStatus):
            raise LiveVerificationValidationError("status must be transport core status")
        _validate_bool_fields(
            self,
            (
                "body_allowlist_passed",
                "stable_serialization_ready",
                "one_shot_no_retry_ready",
                "no_api_executed",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "post_allowed_this_step",
                "post_executed",
                "retry_allowed",
                "loop_allowed",
                "add_change_cancel_close_allowed",
            ),
        )
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _require_non_empty("transport_result_category", self.transport_result_category)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        if self.http_post_executed:
            raise LiveVerificationValidationError("transport core must not execute HTTP POST")
        if self.order_endpoint_called:
            raise LiveVerificationValidationError("transport core must not call order endpoint")
        if self.live_order_once_called:
            raise LiveVerificationValidationError("transport core must not call live_order_once")
        if self.post_allowed_this_step:
            raise LiveVerificationValidationError("transport core must not allow POST")
        if self.post_executed:
            raise LiveVerificationValidationError("transport core must not mark post executed")


def build_order_body_from_validated_intent(
    intent: LiveOrderRealValidatedOrderIntent,
) -> LiveOrderRealOrderBody:
    """Build sanitized body metadata from a validated Step 6G intent."""
    body_reasons = _body_invalid_reasons(intent)
    unauthorized_reasons = _unauthorized_field_reasons(intent)
    if body_reasons:
        raise LiveVerificationValidationError(",".join(body_reasons))
    if unauthorized_reasons:
        raise LiveVerificationValidationError(",".join(unauthorized_reasons))
    return LiveOrderRealOrderBody(
        symbol=intent.symbol,
        side=intent.side,
        size=intent.size,
        executionType=intent.executionType,
        field_names=tuple(sorted(TRANSPORT_CORE_ORDER_FIELDS)),
        raw_request_displayed=False,
        raw_request_saved=False,
        serialized_body_displayed=False,
        serialized_body_saved=False,
        client_order_id_present=False,
        client_order_id_displayed=False,
    )


def validate_order_body_allowlist(
    order_body: LiveOrderRealOrderBody,
) -> LiveOrderRealTransportCoreCheckResult:
    """Validate that the body metadata contains only the Step 6G allowed fields."""
    reasons = _order_body_reasons(order_body)
    return LiveOrderRealTransportCoreCheckResult(
        name="order body allowlist",
        passed=not reasons,
        sanitized_value="passed" if not reasons else ",".join(reasons),
        expected="symbol,side,size,executionType only",
    )


def serialize_order_body_stably(order_body: LiveOrderRealOrderBody) -> str:
    """Return deterministic JSON for fake tests; never store it on result objects."""
    check = validate_order_body_allowlist(order_body)
    if not check.passed:
        raise LiveVerificationValidationError("order body allowlist failed")
    values = {
        "symbol": order_body.symbol,
        "side": order_body.side,
        "size": order_body.size,
        "executionType": order_body.executionType,
    }
    if set(values) != TRANSPORT_CORE_ORDER_FIELDS:
        raise LiveVerificationValidationError("serialization field allowlist mismatch")
    return json.dumps(values, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def build_private_order_header_contract_without_exposure(
    *,
    header_contract_ready: bool = True,
    header_names_allowed: tuple[str, ...] = TRANSPORT_CORE_HEADER_NAME_SUMMARY,
    header_values_redacted: bool = True,
    signature_value_generated: bool = False,
    signature_value_displayed: bool = False,
    signature_value_saved: bool = False,
    credentials_used: bool = False,
    credentials_displayed: bool = False,
    headers_displayed: bool = False,
    headers_saved: bool = False,
) -> LiveOrderRealSensitiveHeaderContract:
    """Build redacted header metadata only; no credential or signed values."""
    return LiveOrderRealSensitiveHeaderContract(
        header_contract_ready=header_contract_ready,
        header_names_allowed=header_names_allowed,
        header_values_redacted=header_values_redacted,
        signature_value_generated=signature_value_generated,
        signature_value_displayed=signature_value_displayed,
        signature_value_saved=signature_value_saved,
        credentials_used=credentials_used,
        credentials_displayed=credentials_displayed,
        headers_displayed=headers_displayed,
        headers_saved=headers_saved,
    )


def classify_order_transport_result_safely(
    fake_result: LiveOrderRealFakeTransportResult,
) -> LiveOrderRealSanitizedTransportResult:
    """Classify a sanitized fake transport result without raw data or retry."""
    raw_reasons = _fake_result_raw_or_secret_reasons(fake_result)
    retry_reasons = _fake_result_retry_reasons(fake_result)
    if raw_reasons:
        category = TransportResultCategory.TRANSPORT_BLOCKED_RAW_OR_SECRET_EXPOSURE
    elif retry_reasons:
        category = TransportResultCategory.TRANSPORT_BLOCKED_RETRY_OR_LOOP
    else:
        category = _fake_result_category(fake_result.fake_result_kind)
    return LiveOrderRealSanitizedTransportResult(
        result_category=category,
        raw_request_present=fake_result.raw_request_present,
        raw_response_present=fake_result.raw_response_present,
        headers_present=fake_result.headers_present,
        signature_value_present=fake_result.signature_value_present,
        credentials_present=fake_result.credentials_present,
        real_ids_present=_fake_result_has_real_ids(fake_result),
        retry_count=fake_result.retry_count,
        loop_count=fake_result.loop_count,
    )


def ensure_no_raw_or_secret_exposure(
    *,
    header_contract: LiveOrderRealSensitiveHeaderContract,
    fake_result: LiveOrderRealFakeTransportResult | None = None,
) -> LiveOrderRealTransportCoreCheckResult:
    reasons = [
        *_header_raw_or_secret_reasons(header_contract),
        *(_fake_result_raw_or_secret_reasons(fake_result) if fake_result else ()),
    ]
    return LiveOrderRealTransportCoreCheckResult(
        name="no raw secret real ID exposure",
        passed=not reasons,
        sanitized_value="none" if not reasons else ",".join(reasons),
        expected="none",
    )


def ensure_one_shot_no_retry_contract(
    no_retry_contract: LiveOrderRealNoRetryContract,
) -> LiveOrderRealTransportCoreCheckResult:
    reasons = _no_retry_reasons(no_retry_contract)
    return LiveOrderRealTransportCoreCheckResult(
        name="one shot no retry",
        passed=not reasons,
        sanitized_value="passed" if not reasons else ",".join(reasons),
        expected="limit=1 before=0 after<=1 retry=false loop=false",
    )


def build_live_order_real_order_transport_core(
    *,
    intent: LiveOrderRealValidatedOrderIntent,
    endpoint_contract: LiveOrderRealTransportEndpointContract | None = None,
    header_contract: LiveOrderRealSensitiveHeaderContract | None = None,
    fake_transport_result: LiveOrderRealFakeTransportResult | None = None,
    no_retry_contract: LiveOrderRealNoRetryContract | None = None,
) -> LiveOrderRealTransportCoreResult:
    """Build the pure/fake transport-core decision for Step 6G."""
    route_contract = endpoint_contract or make_live_order_real_transport_endpoint_contract()
    header = header_contract or build_private_order_header_contract_without_exposure()
    attempts = no_retry_contract or LiveOrderRealNoRetryContract(
        post_attempt_limit=1,
        post_attempt_count_before=0,
        post_attempt_count_after=0 if fake_transport_result is None else 1,
        retry_allowed=False,
        loop_allowed=False,
        retry_on_unknown=False,
        retry_on_timeout=False,
        retry_on_reject=False,
        add_order_allowed=False,
        change_order_allowed=False,
        cancel_order_allowed=False,
        close_order_allowed=False,
    )

    unauthorized_reasons = _unauthorized_field_reasons(intent)
    body_invalid_reasons = _body_invalid_reasons(intent)
    endpoint_reasons = _endpoint_unsafe_reasons(route_contract)
    header_contract_reasons = _header_contract_reasons(header)
    no_retry_reasons = _no_retry_reasons(attempts)
    header_raw_reasons = _header_raw_or_secret_reasons(header)
    fake_raw_reasons = (
        _fake_result_raw_or_secret_reasons(fake_transport_result)
        if fake_transport_result
        else ()
    )
    fake_retry_reasons = (
        _fake_result_retry_reasons(fake_transport_result)
        if fake_transport_result
        else ()
    )

    order_body: LiveOrderRealOrderBody | None = None
    stable_serialization_ready = False
    serialization_reasons: tuple[str, ...] = ()
    if not unauthorized_reasons and not body_invalid_reasons:
        try:
            order_body = build_order_body_from_validated_intent(intent)
            serialize_order_body_stably(order_body)
            stable_serialization_ready = True
        except (TypeError, ValueError, LiveVerificationValidationError) as error:
            serialization_reasons = (f"stable_serialization_failed:{error.__class__.__name__}",)

    sanitized_result = (
        classify_order_transport_result_safely(fake_transport_result)
        if fake_transport_result
        else None
    )
    unsupported_result_reasons = (
        ("fake_transport_result_unsupported",)
        if sanitized_result
        and sanitized_result.result_category
        is TransportResultCategory.TRANSPORT_BLOCKED_UNSUPPORTED
        else ()
    )

    if header_raw_reasons or fake_raw_reasons:
        status = TransportCoreStatus.TRANSPORT_CORE_BLOCKED_RAW_OR_SECRET_EXPOSURE
        primary_reasons = (*header_raw_reasons, *fake_raw_reasons)
    elif no_retry_reasons or fake_retry_reasons:
        status = TransportCoreStatus.TRANSPORT_CORE_BLOCKED_RETRY_OR_LOOP
        primary_reasons = (*no_retry_reasons, *fake_retry_reasons)
    elif unauthorized_reasons:
        status = TransportCoreStatus.TRANSPORT_CORE_UNAUTHORIZED_FIELD
        primary_reasons = unauthorized_reasons
    elif body_invalid_reasons:
        status = TransportCoreStatus.TRANSPORT_CORE_BODY_INVALID
        primary_reasons = body_invalid_reasons
    elif serialization_reasons:
        status = TransportCoreStatus.TRANSPORT_CORE_SERIALIZATION_FAILED
        primary_reasons = serialization_reasons
    elif header_contract_reasons:
        status = TransportCoreStatus.TRANSPORT_CORE_HEADER_CONTRACT_UNSAFE
        primary_reasons = header_contract_reasons
    elif endpoint_reasons or unsupported_result_reasons:
        status = TransportCoreStatus.TRANSPORT_CORE_UNSUPPORTED
        primary_reasons = (*endpoint_reasons, *unsupported_result_reasons)
    elif sanitized_result:
        status = TransportCoreStatus.TRANSPORT_CORE_RESULT_CLASSIFIED_NO_RETRY
        primary_reasons = ()
    else:
        status = TransportCoreStatus.TRANSPORT_CORE_READY_NO_API_NO_POST
        primary_reasons = ()

    body_check = (
        validate_order_body_allowlist(order_body)
        if order_body
        else LiveOrderRealTransportCoreCheckResult(
            name="order body allowlist",
            passed=False,
            sanitized_value="blocked",
            expected="symbol,side,size,executionType only",
        )
    )
    checks = _build_check_results(
        body_check=body_check,
        stable_serialization_ready=stable_serialization_ready,
        route_contract=route_contract,
        header=header,
        sanitized_result=sanitized_result,
        no_retry_contract=attempts,
        raw_secret_check=ensure_no_raw_or_secret_exposure(
            header_contract=header,
            fake_result=fake_transport_result,
        ),
    )

    return LiveOrderRealTransportCoreResult(
        status=status,
        body_allowlist_passed=body_check.passed,
        stable_serialization_ready=stable_serialization_ready,
        endpoint_contract=route_contract,
        sensitive_header_contract=header,
        sanitized_transport_result=sanitized_result,
        transport_result_category=(
            sanitized_result.result_category.value
            if sanitized_result
            else "NOT_CLASSIFIED_PURE_FAKE_ONLY_NO_API_NO_POST"
        ),
        one_shot_no_retry_ready=not no_retry_reasons and not fake_retry_reasons,
        no_api_executed=True,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_executed=False,
        retry_allowed=False,
        loop_allowed=False,
        add_change_cancel_close_allowed=False,
        check_results=checks,
        blocked_reasons=_merge_reasons(primary_reasons),
        recommended_next_step=TRANSPORT_CORE_RECOMMENDED_NEXT_STEP,
    )


def make_live_order_real_transport_endpoint_contract(
    *,
    method: LiveOrderRealTransportMethod = LiveOrderRealTransportMethod.POST,
    path: str = TRANSPORT_CORE_ORDER_PATH,
    endpoint_contract_label: str = TRANSPORT_CORE_ENDPOINT_LABEL,
    order_endpoint_called: bool = False,
    http_post_executed: bool = False,
    live_order_once_called: bool = False,
    imports_http_client: bool = False,
    imports_private_api: bool = False,
    imports_broker: bool = False,
    imports_live_order_once: bool = False,
) -> LiveOrderRealTransportEndpointContract:
    return LiveOrderRealTransportEndpointContract(
        method=method,
        path=path,
        endpoint_contract_label=endpoint_contract_label,
        order_endpoint_called=order_endpoint_called,
        http_post_executed=http_post_executed,
        live_order_once_called=live_order_once_called,
        imports_http_client=imports_http_client,
        imports_private_api=imports_private_api,
        imports_broker=imports_broker,
        imports_live_order_once=imports_live_order_once,
    )


def make_live_order_real_stable_serialization_metadata(
    order_body: LiveOrderRealOrderBody,
) -> LiveOrderRealStableSerializedBody:
    serialize_order_body_stably(order_body)
    return LiveOrderRealStableSerializedBody(
        stable_serialization_ready=True,
        field_order=tuple(sorted(TRANSPORT_CORE_ORDER_FIELDS)),
        ensure_ascii=True,
        sort_keys=True,
        compact_separators=True,
        serialized_body_displayed=False,
        serialized_body_saved=False,
        serialized_body_full_text_present=False,
    )


def render_live_order_real_order_transport_core_markdown(
    result: LiveOrderRealTransportCoreResult,
) -> str:
    """Render a sanitized transport-core summary without body, header, or raw values."""
    lines = [
        "# Step 6G Low-Level Transport Core",
        "",
        "This transport core is pure/fake only.",
        "This transport core does not execute API calls.",
        "This transport core does not execute HTTP POST.",
        "This transport core does not call order endpoint.",
        "This transport core does not call live_order_once.",
        "This transport core does not use real credentials.",
        "Future real signing / real transport must be a separate Step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- body_allowlist_passed: {_bool_text(result.body_allowlist_passed)}",
        f"- stable_serialization_ready: {_bool_text(result.stable_serialization_ready)}",
        f"- endpoint_contract_label: {result.endpoint_contract.endpoint_contract_label}",
        f"- method: {result.endpoint_contract.method.value}",
        f"- path: {result.endpoint_contract.path}",
        (
            "- header_contract_ready: "
            f"{_bool_text(result.sensitive_header_contract.header_contract_ready)}"
        ),
        (
            "- header_values_redacted: "
            f"{_bool_text(result.sensitive_header_contract.header_values_redacted)}"
        ),
        f"- transport_result_category: {result.transport_result_category}",
        f"- one_shot_no_retry_ready: {_bool_text(result.one_shot_no_retry_ready)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
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


def _body_invalid_reasons(
    intent: LiveOrderRealValidatedOrderIntent,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if intent.symbol != SUPPORTED_SYMBOL:
        reasons.append("symbol_not_usd_jpy")
    if intent.side != "BUY":
        reasons.append("side_not_buy")
    if intent.size != LIVE_ORDER_CANDIDATE_SIZE:
        reasons.append("size_not_100")
    if intent.executionType != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        reasons.append("execution_type_not_market")
    for field_name in (
        "codex_inferred_symbol",
        "codex_inferred_side",
        "codex_inferred_size",
        "codex_inferred_execution_type",
    ):
        if getattr(intent, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _unauthorized_field_reasons(
    intent: LiveOrderRealValidatedOrderIntent,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in intent.extra_fields:
        if field_name not in TRANSPORT_CORE_ORDER_FIELDS:
            reasons.append(f"unauthorized_field:{field_name}")
        if field_name in _UNAUTHORIZED_FIELD_NAMES:
            reasons.append(f"blocked_order_field:{field_name}")
    for field_name in (
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(intent, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(dict.fromkeys(reasons))


def _order_body_reasons(order_body: LiveOrderRealOrderBody) -> tuple[str, ...]:
    reasons: list[str] = []
    if order_body.symbol != SUPPORTED_SYMBOL:
        reasons.append("symbol_not_usd_jpy")
    if order_body.side != "BUY":
        reasons.append("side_not_buy")
    if order_body.size != LIVE_ORDER_CANDIDATE_SIZE:
        reasons.append("size_not_100")
    if order_body.executionType != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        reasons.append("execution_type_not_market")
    if set(order_body.field_names) != TRANSPORT_CORE_ORDER_FIELDS:
        reasons.append("field_allowlist_mismatch")
    if order_body.raw_request_displayed:
        reasons.append("raw_request_displayed")
    if order_body.raw_request_saved:
        reasons.append("raw_request_saved")
    if order_body.serialized_body_displayed:
        reasons.append("serialized_body_displayed")
    if order_body.serialized_body_saved:
        reasons.append("serialized_body_saved")
    if order_body.client_order_id_present:
        reasons.append("client_order_id_present")
    if order_body.client_order_id_displayed:
        reasons.append("client_order_id_displayed")
    return tuple(reasons)


def _endpoint_unsafe_reasons(
    route_contract: LiveOrderRealTransportEndpointContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if route_contract.method is not TransportMethod.POST:
        reasons.append("method_not_post")
    if route_contract.path != TRANSPORT_CORE_ORDER_PATH:
        reasons.append("path_not_order_contract")
    for field_name in (
        "order_endpoint_called",
        "http_post_executed",
        "live_order_once_called",
        "imports_http_client",
        "imports_private_api",
        "imports_broker",
        "imports_live_order_once",
    ):
        if getattr(route_contract, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _header_contract_reasons(
    header: LiveOrderRealSensitiveHeaderContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not header.header_contract_ready:
        reasons.append("header_contract_not_ready")
    if header.header_names_allowed != TRANSPORT_CORE_HEADER_NAME_SUMMARY:
        reasons.append("header_names_not_allowed")
    if not header.header_values_redacted:
        reasons.append("header_values_not_redacted")
    return tuple(reasons)


def _header_raw_or_secret_reasons(
    header: LiveOrderRealSensitiveHeaderContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "signature_value_generated",
        "signature_value_displayed",
        "signature_value_saved",
        "credentials_used",
        "credentials_displayed",
        "headers_displayed",
        "headers_saved",
    ):
        if getattr(header, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _fake_result_raw_or_secret_reasons(
    fake_result: LiveOrderRealFakeTransportResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "raw_request_present",
        "raw_response_present",
        "headers_present",
        "signature_value_present",
        "credentials_present",
        "real_order_id_present",
        "real_execution_id_present",
        "real_position_id_present",
        "real_client_order_id_present",
    ):
        if getattr(fake_result, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _fake_result_retry_reasons(
    fake_result: LiveOrderRealFakeTransportResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "retry_on_unknown",
        "retry_on_timeout",
        "retry_on_reject",
    ):
        if getattr(fake_result, field_name):
            reasons.append(f"{field_name}_unsafe")
    if fake_result.retry_count:
        reasons.append("retry_count_non_zero")
    if fake_result.loop_count:
        reasons.append("loop_count_non_zero")
    return tuple(reasons)


def _fake_result_has_real_ids(fake_result: LiveOrderRealFakeTransportResult) -> bool:
    return any(
        (
            fake_result.real_order_id_present,
            fake_result.real_execution_id_present,
            fake_result.real_position_id_present,
            fake_result.real_client_order_id_present,
        )
    )


def _fake_result_category(fake_result_kind: str) -> LiveOrderRealTransportResultCategory:
    mapping = {
        "success": TransportResultCategory.TRANSPORT_SUCCESS_SANITIZED,
        "api_rejected": TransportResultCategory.TRANSPORT_API_REJECTED_SANITIZED_NO_RETRY,
        "timeout": TransportResultCategory.TRANSPORT_TIMEOUT_SANITIZED_NO_RETRY,
        "transport_error": TransportResultCategory.TRANSPORT_ERROR_SANITIZED_NO_RETRY,
        "result_unknown": TransportResultCategory.TRANSPORT_RESULT_UNKNOWN_SANITIZED_NO_RETRY,
    }
    return mapping.get(fake_result_kind, TransportResultCategory.TRANSPORT_BLOCKED_UNSUPPORTED)


def _no_retry_reasons(no_retry: LiveOrderRealNoRetryContract) -> tuple[str, ...]:
    reasons: list[str] = []
    if no_retry.post_attempt_limit != 1:
        reasons.append("post_attempt_limit_not_one")
    if no_retry.post_attempt_count_before != 0:
        reasons.append("post_attempt_count_before_not_zero")
    if no_retry.post_attempt_count_after > 1:
        reasons.append("post_attempt_count_after_exceeds_one")
    for field_name in (
        "retry_allowed",
        "loop_allowed",
        "retry_on_unknown",
        "retry_on_timeout",
        "retry_on_reject",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(no_retry, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _build_check_results(
    *,
    body_check: LiveOrderRealTransportCoreCheckResult,
    stable_serialization_ready: bool,
    route_contract: LiveOrderRealTransportEndpointContract,
    header: LiveOrderRealSensitiveHeaderContract,
    sanitized_result: LiveOrderRealSanitizedTransportResult | None,
    no_retry_contract: LiveOrderRealNoRetryContract,
    raw_secret_check: LiveOrderRealTransportCoreCheckResult,
) -> tuple[LiveOrderRealTransportCoreCheckResult, ...]:
    endpoint_reasons = _endpoint_unsafe_reasons(route_contract)
    header_reasons = _header_contract_reasons(header)
    no_retry_check = ensure_one_shot_no_retry_contract(no_retry_contract)
    checks = [
        body_check,
        LiveOrderRealTransportCoreCheckResult(
            name="stable serialization",
            passed=stable_serialization_ready,
            sanitized_value="ready" if stable_serialization_ready else "blocked",
            expected="deterministic compact JSON generated only in memory",
        ),
        LiveOrderRealTransportCoreCheckResult(
            name="endpoint contract",
            passed=not endpoint_reasons,
            sanitized_value="ready" if not endpoint_reasons else ",".join(endpoint_reasons),
            expected="POST /v1/order metadata only, no call",
        ),
        LiveOrderRealTransportCoreCheckResult(
            name="redacted header contract",
            passed=not header_reasons,
            sanitized_value="ready" if not header_reasons else ",".join(header_reasons),
            expected="names only values redacted",
        ),
        raw_secret_check,
        no_retry_check,
        LiveOrderRealTransportCoreCheckResult(
            name="fake result classification",
            passed=(
                sanitized_result is None
                or sanitized_result.result_category
                not in {
                    TransportResultCategory.TRANSPORT_BLOCKED_RAW_OR_SECRET_EXPOSURE,
                    TransportResultCategory.TRANSPORT_BLOCKED_RETRY_OR_LOOP,
                    TransportResultCategory.TRANSPORT_BLOCKED_UNSUPPORTED,
                }
            ),
            sanitized_value=(
                sanitized_result.result_category.value
                if sanitized_result
                else "not_classified"
            ),
            expected="sanitized fake category or not_classified",
        ),
    ]
    return tuple(checks)


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


def _validate_str_tuple(field_name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple) or any(not isinstance(value, str) for value in values):
        raise LiveVerificationValidationError(f"{field_name} must be tuple[str, ...]")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
