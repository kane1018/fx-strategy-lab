"""Local-only signed header bundle for mock verification only."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass

from app.live_verification.actual_order_body import (
    ACTUAL_ORDER_EXECUTION_TYPE,
    ACTUAL_ORDER_SETTLE_TYPE,
    ACTUAL_ORDER_TIME_IN_FORCE,
    ActualOrderRequestBody,
)
from app.live_verification.errors import LiveVerificationActualHeadersSignatureError
from app.live_verification.intent import OrderIntentSide
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

ORDER_CREATE_METHOD = "POST"
ORDER_CREATE_PATH = "/private/v1/order"
SIGNATURE_ALGORITHM_SUMMARY = "HMAC-SHA256-HEX"
BODY_SERIALIZATION_SUMMARY = "stable-json:executionType,settleType,side,size,symbol,timeInForce"
HEADER_NAMES_SUMMARY = ("API-KEY", "API-TIMESTAMP", "API-SIGN")


@dataclass(frozen=True)
class ActualHeadersSignatureBundle:
    bundle_id: str
    actual_order_body_id: str
    verification_run_id: str
    headers_created: bool
    signature_created: bool
    hmac_used: bool
    http_post_enabled: bool
    raw_headers_saved: bool
    raw_signature_saved: bool
    raw_request_saved: bool
    raw_response_saved: bool
    credential_values_logged: bool
    api_key_value_exposed: bool
    api_secret_value_exposed: bool
    signature_value_exposed: bool
    header_names_summary: tuple[str, ...]
    signature_algorithm_summary: str
    body_serialization_summary: str
    bundle_passed: bool
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_bundle(self)


class _SensitiveSignedHeaders:
    __slots__ = ("_body_serialization", "_headers", "_signature")

    def __init__(
        self,
        *,
        body_serialization: str,
        api_key: str,
        timestamp: str,
        signed_digest: str,
    ) -> None:
        self._body_serialization = body_serialization
        self._headers = {
            "API-KEY": api_key,
            "API-TIMESTAMP": timestamp,
            "API-SIGN": signed_digest,
        }
        self._signature = signed_digest

    def __repr__(self) -> str:
        return "_SensitiveSignedHeaders(<redacted>)"

    __str__ = __repr__

    @property
    def header_names(self) -> tuple[str, ...]:
        return tuple(self._headers)

    def has_required_headers(self) -> bool:
        return self.header_names == HEADER_NAMES_SUMMARY and all(self._headers.values())

    def verify_signature(
        self,
        *,
        api_secret: str,
        timestamp: str,
        method: str,
        path: str,
        body_serialization: str,
    ) -> bool:
        expected = _create_signature(
            api_secret=api_secret,
            timestamp=timestamp,
            method=method,
            path=path,
            body_serialization=body_serialization,
        )
        return hmac.compare_digest(self._signature, expected)

    def matches_body_serialization(self, body_serialization: str) -> bool:
        return self._body_serialization == body_serialization


def build_actual_headers_signature_bundle(
    *,
    actual_order_body: ActualOrderRequestBody,
    api_key: str,
    api_secret: str,
    timestamp: str,
    method: str = ORDER_CREATE_METHOD,
    path: str = ORDER_CREATE_PATH,
    http_post_enabled: bool = False,
    raw_headers_saved: bool = False,
    raw_signature_saved: bool = False,
    raw_request_saved: bool = False,
    raw_response_saved: bool = False,
    credential_values_logged: bool = False,
) -> ActualHeadersSignatureBundle:
    """Build signed headers for local mock transport without exposing their values."""
    _ensure_actual_order_body_type(actual_order_body)
    _validate_bool_map({
        "http_post_enabled": http_post_enabled,
        "raw_headers_saved": raw_headers_saved,
        "raw_signature_saved": raw_signature_saved,
        "raw_request_saved": raw_request_saved,
        "raw_response_saved": raw_response_saved,
        "credential_values_logged": credential_values_logged,
    })
    fail_reasons = [
        *_actual_order_body_fail_reasons(actual_order_body),
        *_credential_input_fail_reasons(
            api_key=api_key,
            api_secret=api_secret,
            timestamp=timestamp,
            method=method,
            path=path,
        ),
        *_bundle_flag_fail_reasons(
            http_post_enabled=http_post_enabled,
            raw_headers_saved=raw_headers_saved,
            raw_signature_saved=raw_signature_saved,
            raw_request_saved=raw_request_saved,
            raw_response_saved=raw_response_saved,
            credential_values_logged=credential_values_logged,
        ),
    ]
    if fail_reasons:
        raise LiveVerificationActualHeadersSignatureError(";".join(fail_reasons))

    body_serialization = serialize_actual_order_body_for_signing(actual_order_body)
    signed_digest = _create_signature(
        api_secret=api_secret,
        timestamp=timestamp,
        method=method,
        path=path,
        body_serialization=body_serialization,
    )
    bundle = ActualHeadersSignatureBundle(
        bundle_id=make_actual_headers_signature_bundle_id(
            actual_order_body_id=actual_order_body.actual_order_body_id,
            verification_run_id=actual_order_body.verification_run_id,
            timestamp=timestamp,
            method=method,
            path=path,
            body_serialization=body_serialization,
        ),
        actual_order_body_id=actual_order_body.actual_order_body_id,
        verification_run_id=actual_order_body.verification_run_id,
        headers_created=True,
        signature_created=True,
        hmac_used=True,
        http_post_enabled=http_post_enabled,
        raw_headers_saved=raw_headers_saved,
        raw_signature_saved=raw_signature_saved,
        raw_request_saved=raw_request_saved,
        raw_response_saved=raw_response_saved,
        credential_values_logged=credential_values_logged,
        api_key_value_exposed=False,
        api_secret_value_exposed=False,
        signature_value_exposed=False,
        header_names_summary=HEADER_NAMES_SUMMARY,
        signature_algorithm_summary=SIGNATURE_ALGORITHM_SUMMARY,
        body_serialization_summary=BODY_SERIALIZATION_SUMMARY,
        bundle_passed=True,
        fail_reasons=(),
    )
    object.__setattr__(
        bundle,
        "_sensitive_signed_headers",
        _SensitiveSignedHeaders(
            body_serialization=body_serialization,
            api_key=api_key,
            timestamp=timestamp,
            signed_digest=signed_digest,
        ),
    )
    return bundle


def serialize_actual_order_body_for_signing(body: ActualOrderRequestBody) -> str:
    """Return stable JSON only for in-memory signing input."""
    _ensure_actual_order_body_type(body)
    fail_reasons = _actual_order_body_fail_reasons(body)
    if fail_reasons:
        raise LiveVerificationActualHeadersSignatureError(";".join(fail_reasons))
    return json.dumps(
        {
            "executionType": body.executionType,
            "settleType": body.settleType,
            "side": body.side.value,
            "size": body.size,
            "symbol": body.symbol,
            "timeInForce": body.timeInForce,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def make_actual_headers_signature_bundle_id(
    *,
    actual_order_body_id: str,
    verification_run_id: str,
    timestamp: str,
    method: str,
    path: str,
    body_serialization: str,
) -> str:
    _require_non_empty("actual_order_body_id", actual_order_body_id)
    _require_non_empty("verification_run_id", verification_run_id)
    _require_non_empty("timestamp", timestamp)
    _require_non_empty("method", method)
    _require_non_empty("path", path)
    _require_non_empty("body_serialization", body_serialization)
    digest = _short_hash({
        "actual_order_body_id": actual_order_body_id,
        "body_serialization": body_serialization,
        "method": method,
        "path": path,
        "timestamp": timestamp,
        "verification_run_id": verification_run_id,
    })
    return f"actual_headers_signature_{verification_run_id}_{digest}"


def _get_sensitive_signed_headers(
    bundle: ActualHeadersSignatureBundle,
) -> _SensitiveSignedHeaders | None:
    value = getattr(bundle, "_sensitive_signed_headers", None)
    if isinstance(value, _SensitiveSignedHeaders):
        return value
    return None


def _ensure_actual_order_body_type(body: ActualOrderRequestBody) -> None:
    if not isinstance(body, ActualOrderRequestBody):
        raise LiveVerificationActualHeadersSignatureError("actual_order_body is required")


def _actual_order_body_fail_reasons(body: ActualOrderRequestBody) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    for field_name, value in (
        ("actual_order_body_id", body.actual_order_body_id),
        ("verification_run_id", body.verification_run_id),
    ):
        if not _has_text(value):
            fail_reasons.append(f"actual_order_body:{field_name}_missing")
    if body.symbol != SUPPORTED_SYMBOL:
        fail_reasons.append("actual_order_body:symbol")
    if body.size != SUPPORTED_UNITS:
        fail_reasons.append("actual_order_body:size")
    if body.executionType != ACTUAL_ORDER_EXECUTION_TYPE:
        fail_reasons.append("actual_order_body:executionType")
    if body.timeInForce != ACTUAL_ORDER_TIME_IN_FORCE:
        fail_reasons.append("actual_order_body:timeInForce")
    if body.settleType != ACTUAL_ORDER_SETTLE_TYPE:
        fail_reasons.append("actual_order_body:settleType")
    if not isinstance(body.side, OrderIntentSide) or body.side not in {
        OrderIntentSide.BUY,
        OrderIntentSide.SELL,
    }:
        fail_reasons.append("actual_order_body:side")
    for name, value in {
        "body_created": body.body_created,
        "http_post_enabled": body.http_post_enabled,
        "headers_created": body.headers_created,
        "signature_created": body.signature_created,
        "raw_request_saved": body.raw_request_saved,
        "raw_response_saved": body.raw_response_saved,
        "credential_values_logged": body.credential_values_logged,
        "real_order_attempted": body.real_order_attempted,
    }.items():
        if type(value) is not bool:
            fail_reasons.append(f"actual_order_body:{name}_not_bool")
    if type(body.body_created) is bool and not body.body_created:
        fail_reasons.append("actual_order_body:body_created")
    for name, value in {
        "http_post_enabled": body.http_post_enabled,
        "headers_created": body.headers_created,
        "signature_created": body.signature_created,
        "raw_request_saved": body.raw_request_saved,
        "raw_response_saved": body.raw_response_saved,
        "credential_values_logged": body.credential_values_logged,
        "real_order_attempted": body.real_order_attempted,
    }.items():
        if type(value) is bool and value:
            fail_reasons.append(f"actual_order_body:{name}")
    return tuple(fail_reasons)


def _credential_input_fail_reasons(
    *,
    api_key: str,
    api_secret: str,
    timestamp: str,
    method: str,
    path: str,
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    for field_name, value in (
        ("api_key", api_key),
        ("api_secret", api_secret),
        ("timestamp", timestamp),
    ):
        if not _has_text(value):
            fail_reasons.append(field_name)
    if method != ORDER_CREATE_METHOD:
        fail_reasons.append("method")
    if path != ORDER_CREATE_PATH:
        fail_reasons.append("path")
    return tuple(fail_reasons)


def _bundle_flag_fail_reasons(
    *,
    http_post_enabled: bool,
    raw_headers_saved: bool,
    raw_signature_saved: bool,
    raw_request_saved: bool,
    raw_response_saved: bool,
    credential_values_logged: bool,
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    for name, value in {
        "http_post_enabled": http_post_enabled,
        "raw_headers_saved": raw_headers_saved,
        "raw_signature_saved": raw_signature_saved,
        "raw_request_saved": raw_request_saved,
        "raw_response_saved": raw_response_saved,
        "credential_values_logged": credential_values_logged,
    }.items():
        if value:
            fail_reasons.append(name)
    return tuple(fail_reasons)


def _create_signature(
    *,
    api_secret: str,
    timestamp: str,
    method: str,
    path: str,
    body_serialization: str,
) -> str:
    _require_non_empty("api_secret", api_secret)
    _require_non_empty("timestamp", timestamp)
    if method != ORDER_CREATE_METHOD:
        raise LiveVerificationActualHeadersSignatureError("method must be POST")
    if path != ORDER_CREATE_PATH:
        raise LiveVerificationActualHeadersSignatureError("path must be private order")
    signing_source = f"{timestamp}{method}{path}{body_serialization}"
    return hmac.new(
        api_secret.encode("utf-8"),
        signing_source.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _validate_bundle(bundle: ActualHeadersSignatureBundle) -> None:
    for field_name, value in (
        ("bundle_id", bundle.bundle_id),
        ("actual_order_body_id", bundle.actual_order_body_id),
        ("verification_run_id", bundle.verification_run_id),
        ("signature_algorithm_summary", bundle.signature_algorithm_summary),
        ("body_serialization_summary", bundle.body_serialization_summary),
    ):
        _require_non_empty(field_name, value)
    _validate_bool_map({
        "headers_created": bundle.headers_created,
        "signature_created": bundle.signature_created,
        "hmac_used": bundle.hmac_used,
        "http_post_enabled": bundle.http_post_enabled,
        "raw_headers_saved": bundle.raw_headers_saved,
        "raw_signature_saved": bundle.raw_signature_saved,
        "raw_request_saved": bundle.raw_request_saved,
        "raw_response_saved": bundle.raw_response_saved,
        "credential_values_logged": bundle.credential_values_logged,
        "api_key_value_exposed": bundle.api_key_value_exposed,
        "api_secret_value_exposed": bundle.api_secret_value_exposed,
        "signature_value_exposed": bundle.signature_value_exposed,
        "bundle_passed": bundle.bundle_passed,
    })
    if bundle.header_names_summary != HEADER_NAMES_SUMMARY:
        raise LiveVerificationActualHeadersSignatureError("header names summary mismatch")
    if not isinstance(bundle.fail_reasons, tuple) or any(
        not isinstance(reason, str) or not reason for reason in bundle.fail_reasons
    ):
        raise LiveVerificationActualHeadersSignatureError(
            "fail_reasons must be tuple[str, ...]"
        )
    if bundle.bundle_passed and bundle.fail_reasons:
        raise LiveVerificationActualHeadersSignatureError(
            "passed bundle cannot contain fail reasons"
        )
    if not bundle.bundle_passed and not bundle.fail_reasons:
        raise LiveVerificationActualHeadersSignatureError(
            "failed bundle requires fail reasons"
        )
    if bundle.bundle_passed:
        if not all((
            bundle.headers_created,
            bundle.signature_created,
            bundle.hmac_used,
        )):
            raise LiveVerificationActualHeadersSignatureError(
                "passed bundle requires signed header markers"
            )
        if any((
            bundle.http_post_enabled,
            bundle.raw_headers_saved,
            bundle.raw_signature_saved,
            bundle.raw_request_saved,
            bundle.raw_response_saved,
            bundle.credential_values_logged,
            bundle.api_key_value_exposed,
            bundle.api_secret_value_exposed,
            bundle.signature_value_exposed,
        )):
            raise LiveVerificationActualHeadersSignatureError(
                "passed bundle cannot cross no-leak flags"
            )


def _validate_bool_map(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        if type(value) is not bool:
            raise LiveVerificationActualHeadersSignatureError(f"{name} must be bool")


def _require_non_empty(field_name: str, value: str) -> None:
    if not _has_text(value):
        raise LiveVerificationActualHeadersSignatureError(f"{field_name} is required")


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _short_hash(data: dict[str, object]) -> str:
    canonical = json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
