from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_credential_injection_controlled import (
    LiveOrderRealCredentialInjectionControlledInput,
    build_live_order_real_credential_injection_controlled,
)
from app.live_verification.live_order_real_signing_headers_controlled import (
    SAFE_HEADERS_LABEL,
    SAFE_SIGNING_LABEL,
    LiveOrderRealSigningHeadersControlledInput,
    LiveOrderRealSigningHeadersControlledStatus,
    build_live_order_real_signing_headers_controlled,
    render_live_order_real_signing_headers_controlled_markdown,
)

Status = LiveOrderRealSigningHeadersControlledStatus
DUMMY_CREDENTIAL_VALUE = "DUMMY_CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
RAW_HANDLE_SENTINEL = "RAW_HANDLE_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"
CREDENTIAL_METADATA_SENTINEL = "CREDENTIAL_METADATA_VALUE_SHOULD_NOT_SURFACE"
HEADERS_METADATA_SENTINEL = "HEADERS_METADATA_VALUE_SHOULD_NOT_SURFACE"


def _input(**overrides: object) -> LiveOrderRealSigningHeadersControlledInput:
    base = LiveOrderRealSigningHeadersControlledInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_signing_headers_controlled(
        input_snapshot=_input(**overrides),
    )


def test_default_signing_headers_ready_no_transport_api_or_post() -> None:
    result = _build()

    assert result.status is Status.SIGNING_HEADERS_READY_NO_TRANSPORT
    assert result.signing_headers_controlled_ready is True
    assert result.signing_controlled_ready is True
    assert result.headers_controlled_ready is True
    assert (
        result.signing_headers_mode
        == "SIGNING_HEADERS_CONTROLLED_IMPLEMENTATION_ONLY"
    )
    assert result.safe_signing_label == SAFE_SIGNING_LABEL
    assert result.safe_headers_label == SAFE_HEADERS_LABEL
    assert result.safe_signing_status == Status.SIGNING_HEADERS_READY_NO_TRANSPORT.value
    assert result.safe_headers_status == Status.SIGNING_HEADERS_READY_NO_TRANSPORT.value
    assert result.injection_prerequisite_checked is True
    assert result.injection_prerequisite_satisfied is True
    assert result.credential_injection_controlled_ready is True
    assert result.credential_injection_ready is True
    assert result.blocked_reasons == ()
    assert result.credential_value_exposure_attempted is False
    assert result.credential_raw_handle_exposure_attempted is False
    assert result.credential_metadata_exposure_attempted is False
    assert result.credential_length_exposure_attempted is False
    assert result.credential_hash_exposure_attempted is False
    assert result.credential_fingerprint_exposure_attempted is False
    assert result.env_actual_name_exposure_attempted is False
    assert result.signature_value_exposure_attempted is False
    assert result.signature_length_exposure_attempted is False
    assert result.signature_hash_exposure_attempted is False
    assert result.signature_fingerprint_exposure_attempted is False
    assert result.headers_value_exposure_attempted is False
    assert result.headers_metadata_exposure_attempted is False
    assert result.real_signing_attempted is False
    assert result.real_headers_generation_attempted is False
    assert result.real_transport_allowed is False
    assert result.real_transport_attempted is False
    assert result.api_call_allowed is False
    assert result.api_call_attempted is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.actual_checker_execution_performed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_receipt_handoff_executed is False
    assert result.fresh_preflight_executed is False
    assert result.final_confirmation_received is False


def test_safe_injection_result_drives_ready_without_value_exposure() -> None:
    injection_result = build_live_order_real_credential_injection_controlled()
    result = build_live_order_real_signing_headers_controlled(
        injection_result=injection_result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.SIGNING_HEADERS_READY_NO_TRANSPORT
    assert result.signing_headers_controlled_ready is True
    assert DUMMY_CREDENTIAL_VALUE not in payload
    assert RAW_HANDLE_SENTINEL not in payload
    assert SIGNATURE_VALUE_SENTINEL not in payload
    assert HEADERS_VALUE_SENTINEL not in payload


def test_missing_injection_result_fails_closed() -> None:
    injection_result = build_live_order_real_credential_injection_controlled(
        input_snapshot=LiveOrderRealCredentialInjectionControlledInput(
            required_credentials_present=False,
            all_required_credentials_present=False,
            presence_missing=True,
        ),
    )
    result = build_live_order_real_signing_headers_controlled(
        injection_result=injection_result,
    )

    assert result.status is Status.SIGNING_HEADERS_BLOCKED_MISSING_INJECTION
    assert result.signing_headers_controlled_ready is False
    assert result.injection_prerequisite_satisfied is False
    assert "credential_injection_prerequisite_missing" in result.blocked_reasons
    assert result.api_call_allowed is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"signing_unknown": True}, Status.SIGNING_HEADERS_BLOCKED_UNKNOWN),
        ({"headers_unknown": True}, Status.SIGNING_HEADERS_BLOCKED_UNKNOWN),
        ({"signing_failed": True}, Status.SIGNING_HEADERS_BLOCKED_FAILED),
        ({"headers_failed": True}, Status.SIGNING_HEADERS_BLOCKED_FAILED),
        (
            {"signing_unavailable": True},
            Status.SIGNING_HEADERS_BLOCKED_UNAVAILABLE,
        ),
        (
            {"headers_unavailable": True},
            Status.SIGNING_HEADERS_BLOCKED_UNAVAILABLE,
        ),
        ({"signing_timeout": True}, Status.SIGNING_HEADERS_BLOCKED_TIMEOUT),
        ({"headers_timeout": True}, Status.SIGNING_HEADERS_BLOCKED_TIMEOUT),
    ],
)
def test_unknown_failed_unavailable_timeout_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.signing_headers_controlled_ready is False
    assert result.api_call_allowed is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"signing_declared": False}, Status.SIGNING_HEADERS_NOT_READY),
        ({"headers_declared": False}, Status.SIGNING_HEADERS_NOT_READY),
        ({"signing_requested": False}, Status.SIGNING_HEADERS_NOT_READY),
        ({"headers_requested": False}, Status.SIGNING_HEADERS_NOT_READY),
        (
            {"injection_prerequisite_checked": False},
            Status.SIGNING_HEADERS_BLOCKED_MISSING_INJECTION,
        ),
        (
            {"credential_injection_controlled_ready": False},
            Status.SIGNING_HEADERS_BLOCKED_MISSING_INJECTION,
        ),
        (
            {"credential_injection_ready": False},
            Status.SIGNING_HEADERS_BLOCKED_MISSING_INJECTION,
        ),
        (
            {"injection_prerequisite_satisfied": False},
            Status.SIGNING_HEADERS_BLOCKED_MISSING_INJECTION,
        ),
    ],
)
def test_not_ready_or_missing_injection_blocks(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.signing_headers_controlled_ready is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"credential_value_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_CREDENTIAL_VALUE_EXPOSURE,
        ),
        (
            {"credential_raw_handle_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_RAW_HANDLE_EXPOSURE,
        ),
        (
            {"credential_metadata_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_METADATA_EXPOSURE,
        ),
        (
            {"credential_length_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"credential_hash_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"credential_fingerprint_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"env_actual_name_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"signature_value_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_SIGNATURE_VALUE_EXPOSURE,
        ),
        (
            {"signature_length_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"signature_hash_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"signature_fingerprint_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"headers_value_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_HEADERS_VALUE_EXPOSURE,
        ),
        (
            {"headers_metadata_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_METADATA_EXPOSURE,
        ),
        (
            {"unsafe_exposure_attempted": True},
            Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"safe_to_render": False},
            Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"safe_to_serialize": False},
            Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE,
        ),
    ],
)
def test_exposure_attempts_block_and_are_sanitized(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.signing_headers_controlled_ready is False
    assert result.unsafe_exposure_attempted is False
    assert result.credential_value_exposure_attempted is False
    assert result.credential_raw_handle_exposure_attempted is False
    assert result.credential_metadata_exposure_attempted is False
    assert result.credential_length_exposure_attempted is False
    assert result.credential_hash_exposure_attempted is False
    assert result.credential_fingerprint_exposure_attempted is False
    assert result.env_actual_name_exposure_attempted is False
    assert result.signature_value_exposure_attempted is False
    assert result.signature_length_exposure_attempted is False
    assert result.signature_hash_exposure_attempted is False
    assert result.signature_fingerprint_exposure_attempted is False
    assert result.headers_value_exposure_attempted is False
    assert result.headers_metadata_exposure_attempted is False
    assert result.safe_to_render is True
    assert result.safe_to_serialize is True


@pytest.mark.parametrize(
    "field_name",
    [
        "real_signing_attempted",
        "real_headers_generation_attempted",
        "real_transport_allowed",
        "real_transport_attempted",
        "api_call_allowed",
        "api_call_attempted",
    ],
)
def test_signing_headers_transport_or_api_attempts_block(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.SIGNING_HEADERS_BLOCKED_TRANSPORT_OR_API
    assert result.signing_headers_controlled_ready is False
    assert result.real_signing_attempted is False
    assert result.real_headers_generation_attempted is False
    assert result.real_transport_allowed is False
    assert result.real_transport_attempted is False
    assert result.api_call_allowed is False
    assert result.api_call_attempted is False


@pytest.mark.parametrize(
    "field_name",
    [
        "http_post_executed",
        "order_endpoint_called",
        "post_allowed_this_step",
        "post_executed",
        "actual_checker_execution_performed",
        "actual_result_receipt_received",
        "actual_receipt_handoff_executed",
        "fresh_preflight_executed",
        "final_confirmation_received",
    ],
)
def test_post_order_actual_execution_preflight_or_confirmation_blocks(
    field_name: str,
) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.SIGNING_HEADERS_BLOCKED_POST_OR_ORDER
    assert result.signing_headers_controlled_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.actual_checker_execution_performed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_receipt_handoff_executed is False
    assert result.fresh_preflight_executed is False
    assert result.final_confirmation_received is False


def test_live_order_once_blocks_separately() -> None:
    result = _build(live_order_once_called=True)

    assert result.status is Status.SIGNING_HEADERS_BLOCKED_LIVE_ORDER_ONCE
    assert result.signing_headers_controlled_ready is False
    assert result.live_order_once_called is False


def test_unsupported_mode_or_safe_labels_are_redacted() -> None:
    mode_result = _build(signing_headers_mode="UNSUPPORTED_RAW_MODE")
    signing_label_result = _build(safe_signing_label=SIGNATURE_VALUE_SENTINEL)
    headers_label_result = _build(safe_headers_label=HEADERS_VALUE_SENTINEL)

    assert mode_result.status is Status.SIGNING_HEADERS_BLOCKED_UNKNOWN
    assert mode_result.signing_headers_mode == "UNSUPPORTED_REDACTED"
    assert signing_label_result.status is Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE
    assert signing_label_result.safe_signing_label == "UNSUPPORTED_REDACTED"
    assert headers_label_result.status is Status.SIGNING_HEADERS_BLOCKED_UNSAFE_EXPOSURE
    assert headers_label_result.safe_headers_label == "UNSUPPORTED_REDACTED"
    assert SIGNATURE_VALUE_SENTINEL not in repr(asdict(signing_label_result))
    assert HEADERS_VALUE_SENTINEL not in repr(asdict(headers_label_result))


def test_renderer_and_asdict_expose_only_safe_label_status_and_booleans() -> None:
    result = _build()
    rendered = render_live_order_real_signing_headers_controlled_markdown(result)
    payload = repr(asdict(result))

    assert "signing_headers_controlled_ready: true" in rendered
    assert "signing_controlled_ready: true" in rendered
    assert "headers_controlled_ready: true" in rendered
    assert f"safe_signing_label: {SAFE_SIGNING_LABEL}" in rendered
    assert f"safe_headers_label: {SAFE_HEADERS_LABEL}" in rendered
    assert "safe_signing_status: SIGNING_HEADERS_READY_NO_TRANSPORT" in rendered
    assert "safe_headers_status: SIGNING_HEADERS_READY_NO_TRANSPORT" in rendered
    assert "Signing ready does not allow API calls." in rendered
    assert "Signing ready does not allow HTTP POST." in rendered
    assert "Signing ready does not allow real transport." in rendered
    assert "Signing ready does not allow live_order_once." in rendered
    assert "signature_value_exposure_attempted: false" in rendered
    assert "headers_value_exposure_attempted: false" in rendered
    assert "signature_length_exposure_attempted: false" in rendered
    assert "signature_hash_exposure_attempted: false" in rendered
    assert "signature_fingerprint_exposure_attempted: false" in rendered
    assert "headers_metadata_exposure_attempted: false" in rendered
    assert "real_transport_allowed: false" in rendered
    assert "api_call_allowed: false" in rendered
    assert "post_allowed_this_step: false" in rendered
    assert "live_order_once_called: false" in rendered

    for forbidden in (
        DUMMY_CREDENTIAL_VALUE,
        RAW_HANDLE_SENTINEL,
        SIGNATURE_VALUE_SENTINEL,
        HEADERS_VALUE_SENTINEL,
        CREDENTIAL_METADATA_SENTINEL,
        HEADERS_METADATA_SENTINEL,
        "CREDENTIAL_LENGTH_VALUE_SENTINEL",
        "CREDENTIAL_HASH_VALUE_SENTINEL",
        "CREDENTIAL_FINGERPRINT_VALUE_SENTINEL",
        "SIGNATURE_LENGTH_VALUE_SENTINEL",
        "SIGNATURE_HASH_VALUE_SENTINEL",
        "SIGNATURE_FINGERPRINT_VALUE_SENTINEL",
        "RAW_REQUEST_SENTINEL",
        "RAW_RESPONSE_SENTINEL",
        "REAL_ID_SENTINEL",
    ):
        assert forbidden not in rendered
        assert forbidden not in payload


def test_module_imports_no_env_crypto_http_api_post_private_broker_or_live_order_once() -> None:
    module_path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_signing_headers_controlled.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "os",
        "hmac",
        "hashlib",
        "base64",
        "app.brokers",
        "app.private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "getenv",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "pbcopy",
    }
    blocked_attrs = {"environ", "getenv"}
    blocked_calls = {
        "getenv",
        "print",
        "post",
        "request",
        "read_text",
        "write_text",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "pbcopy",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name not in blocked_modules for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in blocked_modules
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            attr = func.attr if isinstance(func, ast.Attribute) else None
            assert name not in blocked_calls
            assert attr not in blocked_calls
