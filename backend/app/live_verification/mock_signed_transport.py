"""No-network mock transport for signed header bundle verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.live_verification.actual_headers_signature import (
    HEADER_NAMES_SUMMARY,
    SIGNATURE_ALGORITHM_SUMMARY,
    ActualHeadersSignatureBundle,
    _get_sensitive_signed_headers,
)
from app.live_verification.errors import LiveVerificationMockSignedTransportError

MOCK_SIGNED_TRANSPORT_MODE = "mock_signed_no_network"


@dataclass(frozen=True)
class MockSignedOrderTransportResult:
    mock_transport_result_id: str
    bundle_id: str
    actual_order_body_id: str
    verification_run_id: str
    transport_mode: str
    network_enabled: bool
    http_client_enabled: bool
    http_post_enabled: bool
    real_order_attempted: bool
    raw_request_saved: bool
    raw_response_saved: bool
    credential_values_logged: bool
    bundle_passed: bool
    transport_passed: bool
    header_names_summary: tuple[str, ...]
    signature_algorithm_summary: str
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_transport_result(self)


def run_mock_signed_order_transport(
    *,
    bundle: ActualHeadersSignatureBundle,
    transport_mode: str = MOCK_SIGNED_TRANSPORT_MODE,
    network_enabled: bool = False,
    http_client_enabled: bool = False,
    http_post_enabled: bool = False,
    real_order_attempted: bool = False,
    raw_request_saved: bool = False,
    raw_response_saved: bool = False,
    credential_values_logged: bool = False,
) -> MockSignedOrderTransportResult:
    """Verify signed bundle presence without sending anything."""
    _ensure_bundle_type(bundle)
    _validate_bool_map({
        "network_enabled": network_enabled,
        "http_client_enabled": http_client_enabled,
        "http_post_enabled": http_post_enabled,
        "real_order_attempted": real_order_attempted,
        "raw_request_saved": raw_request_saved,
        "raw_response_saved": raw_response_saved,
        "credential_values_logged": credential_values_logged,
    })
    fail_reasons = [
        *_bundle_fail_reasons(bundle),
        *_transport_fail_reasons(
            transport_mode=transport_mode,
            network_enabled=network_enabled,
            http_client_enabled=http_client_enabled,
            http_post_enabled=http_post_enabled,
            real_order_attempted=real_order_attempted,
            raw_request_saved=raw_request_saved,
            raw_response_saved=raw_response_saved,
            credential_values_logged=credential_values_logged,
        ),
    ]
    signed_headers = _get_sensitive_signed_headers(bundle)
    if signed_headers is None or not signed_headers.has_required_headers():
        fail_reasons.append("signed_headers_missing")

    return MockSignedOrderTransportResult(
        mock_transport_result_id=make_mock_signed_order_transport_result_id(
            bundle_id=bundle.bundle_id,
            actual_order_body_id=bundle.actual_order_body_id,
            verification_run_id=bundle.verification_run_id,
        ),
        bundle_id=bundle.bundle_id,
        actual_order_body_id=bundle.actual_order_body_id,
        verification_run_id=bundle.verification_run_id,
        transport_mode=transport_mode,
        network_enabled=network_enabled,
        http_client_enabled=http_client_enabled,
        http_post_enabled=http_post_enabled,
        real_order_attempted=real_order_attempted,
        raw_request_saved=raw_request_saved,
        raw_response_saved=raw_response_saved,
        credential_values_logged=credential_values_logged,
        bundle_passed=bundle.bundle_passed,
        transport_passed=not fail_reasons,
        header_names_summary=bundle.header_names_summary,
        signature_algorithm_summary=bundle.signature_algorithm_summary,
        fail_reasons=tuple(fail_reasons),
    )


def make_mock_signed_order_transport_result_id(
    *,
    bundle_id: str,
    actual_order_body_id: str,
    verification_run_id: str,
) -> str:
    _require_non_empty("bundle_id", bundle_id)
    _require_non_empty("actual_order_body_id", actual_order_body_id)
    _require_non_empty("verification_run_id", verification_run_id)
    digest = _short_hash({
        "actual_order_body_id": actual_order_body_id,
        "bundle_id": bundle_id,
        "verification_run_id": verification_run_id,
    })
    return f"mock_signed_transport_{verification_run_id}_{digest}"


def _ensure_bundle_type(bundle: ActualHeadersSignatureBundle) -> None:
    if not isinstance(bundle, ActualHeadersSignatureBundle):
        raise LiveVerificationMockSignedTransportError("signed bundle is required")


def _bundle_fail_reasons(bundle: ActualHeadersSignatureBundle) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    for field_name, value in (
        ("bundle_id", bundle.bundle_id),
        ("actual_order_body_id", bundle.actual_order_body_id),
        ("verification_run_id", bundle.verification_run_id),
    ):
        if not _has_text(value):
            fail_reasons.append(f"bundle:{field_name}_missing")
    if not bundle.bundle_passed:
        fail_reasons.append("bundle:not_passed")
    if bundle.fail_reasons:
        fail_reasons.append("bundle:fail_reasons")
    if bundle.header_names_summary != HEADER_NAMES_SUMMARY:
        fail_reasons.append("bundle:header_names_summary")
    if bundle.signature_algorithm_summary != SIGNATURE_ALGORITHM_SUMMARY:
        fail_reasons.append("bundle:signature_algorithm_summary")
    for name, value in {
        "headers_created": bundle.headers_created,
        "signature_created": bundle.signature_created,
        "hmac_used": bundle.hmac_used,
    }.items():
        if type(value) is not bool or not value:
            fail_reasons.append(f"bundle:{name}")
    for name, value in {
        "http_post_enabled": bundle.http_post_enabled,
        "raw_headers_saved": bundle.raw_headers_saved,
        "raw_signature_saved": bundle.raw_signature_saved,
        "raw_request_saved": bundle.raw_request_saved,
        "raw_response_saved": bundle.raw_response_saved,
        "credential_values_logged": bundle.credential_values_logged,
        "api_key_value_exposed": bundle.api_key_value_exposed,
        "api_secret_value_exposed": bundle.api_secret_value_exposed,
        "signature_value_exposed": bundle.signature_value_exposed,
    }.items():
        if type(value) is not bool or value:
            fail_reasons.append(f"bundle:{name}")
    return tuple(fail_reasons)


def _transport_fail_reasons(
    *,
    transport_mode: str,
    network_enabled: bool,
    http_client_enabled: bool,
    http_post_enabled: bool,
    real_order_attempted: bool,
    raw_request_saved: bool,
    raw_response_saved: bool,
    credential_values_logged: bool,
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    if transport_mode != MOCK_SIGNED_TRANSPORT_MODE:
        fail_reasons.append("transport_mode")
    for name, value in {
        "network_enabled": network_enabled,
        "http_client_enabled": http_client_enabled,
        "http_post_enabled": http_post_enabled,
        "real_order_attempted": real_order_attempted,
        "raw_request_saved": raw_request_saved,
        "raw_response_saved": raw_response_saved,
        "credential_values_logged": credential_values_logged,
    }.items():
        if value:
            fail_reasons.append(name)
    return tuple(fail_reasons)


def _validate_transport_result(result: MockSignedOrderTransportResult) -> None:
    for field_name, value in (
        ("mock_transport_result_id", result.mock_transport_result_id),
        ("bundle_id", result.bundle_id),
        ("actual_order_body_id", result.actual_order_body_id),
        ("verification_run_id", result.verification_run_id),
        ("transport_mode", result.transport_mode),
        ("signature_algorithm_summary", result.signature_algorithm_summary),
    ):
        _require_non_empty(field_name, value)
    _validate_bool_map({
        "network_enabled": result.network_enabled,
        "http_client_enabled": result.http_client_enabled,
        "http_post_enabled": result.http_post_enabled,
        "real_order_attempted": result.real_order_attempted,
        "raw_request_saved": result.raw_request_saved,
        "raw_response_saved": result.raw_response_saved,
        "credential_values_logged": result.credential_values_logged,
        "bundle_passed": result.bundle_passed,
        "transport_passed": result.transport_passed,
    })
    if result.header_names_summary != HEADER_NAMES_SUMMARY:
        raise LiveVerificationMockSignedTransportError("header names summary mismatch")
    if result.transport_passed and result.fail_reasons:
        raise LiveVerificationMockSignedTransportError(
            "passed transport cannot contain fail reasons"
        )
    if not result.transport_passed and not result.fail_reasons:
        raise LiveVerificationMockSignedTransportError(
            "failed transport requires fail reasons"
        )
    if result.transport_passed:
        if result.transport_mode != MOCK_SIGNED_TRANSPORT_MODE:
            raise LiveVerificationMockSignedTransportError("transport mode is not allowed")
        if any((
            result.network_enabled,
            result.http_client_enabled,
            result.http_post_enabled,
            result.real_order_attempted,
            result.raw_request_saved,
            result.raw_response_saved,
            result.credential_values_logged,
        )):
            raise LiveVerificationMockSignedTransportError(
                "passed transport cannot cross no-network flags"
            )


def _validate_bool_map(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        if type(value) is not bool:
            raise LiveVerificationMockSignedTransportError(f"{name} must be bool")


def _require_non_empty(field_name: str, value: str) -> None:
    if not _has_text(value):
        raise LiveVerificationMockSignedTransportError(f"{field_name} is required")


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _short_hash(data: dict[str, object]) -> str:
    canonical = json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
