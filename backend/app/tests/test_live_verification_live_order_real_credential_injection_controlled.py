from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_credential_injection_controlled import (
    SAFE_CREDENTIAL_HANDLE_LABEL,
    LiveOrderRealCredentialInjectionControlledInput,
    LiveOrderRealCredentialInjectionControlledStatus,
    build_live_order_real_credential_injection_controlled,
    render_live_order_real_credential_injection_controlled_markdown,
)

Status = LiveOrderRealCredentialInjectionControlledStatus
DUMMY_VALUE = "DUMMY_CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
RAW_HANDLE_SENTINEL = "RAW_HANDLE_VALUE_SHOULD_NOT_SURFACE"
METADATA_SENTINEL = "CREDENTIAL_METADATA_VALUE_SHOULD_NOT_SURFACE"


class SafePresenceResult:
    process_env_checked_for_presence_only = True
    credential_presence_controlled_ready = True
    required_credentials_present = True
    all_required_credentials_present = True
    presence_missing = False
    presence_unknown = False
    presence_failed = False
    presence_unavailable = False
    presence_timeout = False
    unsafe_exposure_attempted = False
    env_file_read = False
    env_example_file_read = False
    env_actual_names_present = False
    credential_values_present = False
    credential_lengths_present = False
    credential_hashes_present = False
    credential_fingerprints_present = False
    credential_metadata_present = False
    actual_checker_execution_performed = False
    actual_result_receipt_received = False
    actual_receipt_handoff_executed = False
    can_generate_real_signature = False
    can_generate_real_headers = False
    real_signing_allowed = False
    real_headers_generation_allowed = False
    real_transport_allowed = False
    api_call_allowed = False
    api_call_attempted = False
    http_post_executed = False
    order_endpoint_called = False
    live_order_once_called = False
    post_allowed_this_step = False
    post_executed = False
    fresh_preflight_executed = False
    final_confirmation_received = False
    safe_to_render = True
    safe_to_serialize = True


class MissingPresenceResult(SafePresenceResult):
    credential_presence_controlled_ready = False
    required_credentials_present = False
    all_required_credentials_present = False
    presence_missing = True


def _input(
    **overrides: object,
) -> LiveOrderRealCredentialInjectionControlledInput:
    base = LiveOrderRealCredentialInjectionControlledInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_credential_injection_controlled(
        input_snapshot=_input(**overrides),
    )


def test_default_controlled_injection_ready_no_signing_api_or_post() -> None:
    result = _build()

    assert result.status is Status.CREDENTIAL_INJECTION_READY_NO_SIGNING
    assert result.credential_injection_ready is True
    assert result.injection_mode == "CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY"
    assert result.safe_credential_handle_label == SAFE_CREDENTIAL_HANDLE_LABEL
    assert result.safe_injection_status == Status.CREDENTIAL_INJECTION_READY_NO_SIGNING.value
    assert result.presence_prerequisite_checked is True
    assert result.presence_prerequisite_satisfied is True
    assert result.credential_presence_controlled_ready is True
    assert result.required_credentials_present is True
    assert result.all_required_credentials_present is True
    assert result.blocked_reasons == ()
    assert result.credential_value_exposure_attempted is False
    assert result.credential_raw_handle_exposure_attempted is False
    assert result.credential_metadata_exposure_attempted is False
    assert result.credential_length_exposure_attempted is False
    assert result.credential_hash_exposure_attempted is False
    assert result.credential_fingerprint_exposure_attempted is False
    assert result.env_actual_name_exposure_attempted is False
    assert result.can_generate_real_signature is False
    assert result.can_generate_real_headers is False
    assert result.real_signing_allowed is False
    assert result.real_headers_generation_allowed is False
    assert result.real_transport_allowed is False
    assert result.api_call_allowed is False
    assert result.api_call_attempted is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.actual_checker_execution_performed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_receipt_handoff_executed is False
    assert result.fresh_preflight_executed is False
    assert result.final_confirmation_received is False


def test_safe_presence_result_can_drive_controlled_injection_without_value_exposure() -> None:
    result = build_live_order_real_credential_injection_controlled(
        presence_result=SafePresenceResult(),
    )
    payload = repr(asdict(result))

    assert result.status is Status.CREDENTIAL_INJECTION_READY_NO_SIGNING
    assert result.credential_injection_ready is True
    assert DUMMY_VALUE not in payload


def test_missing_presence_result_fails_closed() -> None:
    result = build_live_order_real_credential_injection_controlled(
        presence_result=MissingPresenceResult(),
    )

    assert result.status is Status.CREDENTIAL_INJECTION_BLOCKED_MISSING_PRESENCE
    assert result.credential_injection_ready is False
    assert result.presence_prerequisite_satisfied is False
    assert "credential_presence_prerequisite_missing" in result.blocked_reasons
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"presence_unknown": True}, Status.CREDENTIAL_INJECTION_BLOCKED_UNKNOWN),
        ({"presence_failed": True}, Status.CREDENTIAL_INJECTION_BLOCKED_FAILED),
        (
            {"presence_unavailable": True},
            Status.CREDENTIAL_INJECTION_BLOCKED_UNAVAILABLE,
        ),
        ({"presence_timeout": True}, Status.CREDENTIAL_INJECTION_BLOCKED_TIMEOUT),
    ],
)
def test_unknown_failed_unavailable_timeout_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.credential_injection_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"injection_declared": False},
            Status.CREDENTIAL_INJECTION_NOT_READY,
        ),
        (
            {"injection_requested": False},
            Status.CREDENTIAL_INJECTION_NOT_READY,
        ),
        (
            {"presence_prerequisite_checked": False},
            Status.CREDENTIAL_INJECTION_BLOCKED_MISSING_PRESENCE,
        ),
        (
            {"credential_presence_controlled_ready": False},
            Status.CREDENTIAL_INJECTION_BLOCKED_MISSING_PRESENCE,
        ),
        (
            {"required_credentials_present": False},
            Status.CREDENTIAL_INJECTION_BLOCKED_MISSING_PRESENCE,
        ),
        (
            {"all_required_credentials_present": False},
            Status.CREDENTIAL_INJECTION_BLOCKED_MISSING_PRESENCE,
        ),
        (
            {"presence_missing": True},
            Status.CREDENTIAL_INJECTION_BLOCKED_MISSING_PRESENCE,
        ),
    ],
)
def test_not_ready_or_missing_presence_blocks(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.credential_injection_ready is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"credential_value_exposure_attempted": True},
            Status.CREDENTIAL_INJECTION_BLOCKED_VALUE_EXPOSURE,
        ),
        (
            {"credential_raw_handle_exposure_attempted": True},
            Status.CREDENTIAL_INJECTION_BLOCKED_RAW_HANDLE_EXPOSURE,
        ),
        (
            {"credential_metadata_exposure_attempted": True},
            Status.CREDENTIAL_INJECTION_BLOCKED_METADATA_EXPOSURE,
        ),
        (
            {"credential_length_exposure_attempted": True},
            Status.CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"credential_hash_exposure_attempted": True},
            Status.CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"credential_fingerprint_exposure_attempted": True},
            Status.CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"env_actual_name_exposure_attempted": True},
            Status.CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"unsafe_exposure_attempted": True},
            Status.CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"safe_to_render": False},
            Status.CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"safe_to_serialize": False},
            Status.CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE,
        ),
    ],
)
def test_exposure_attempts_block_and_are_sanitized(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.credential_injection_ready is False
    assert result.unsafe_exposure_attempted is False
    assert result.credential_value_exposure_attempted is False
    assert result.credential_raw_handle_exposure_attempted is False
    assert result.credential_metadata_exposure_attempted is False
    assert result.credential_length_exposure_attempted is False
    assert result.credential_hash_exposure_attempted is False
    assert result.credential_fingerprint_exposure_attempted is False
    assert result.env_actual_name_exposure_attempted is False
    assert result.safe_to_render is True
    assert result.safe_to_serialize is True


@pytest.mark.parametrize(
    "field_name",
    [
        "can_generate_real_signature",
        "can_generate_real_headers",
        "real_signing_allowed",
        "real_headers_generation_allowed",
        "real_transport_allowed",
    ],
)
def test_signing_headers_or_transport_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.CREDENTIAL_INJECTION_BLOCKED_SIGNING_OR_HEADERS
    assert result.credential_injection_ready is False
    assert result.can_generate_real_signature is False
    assert result.can_generate_real_headers is False
    assert result.real_signing_allowed is False
    assert result.real_headers_generation_allowed is False
    assert result.real_transport_allowed is False


@pytest.mark.parametrize(
    "field_name",
    [
        "api_call_allowed",
        "api_call_attempted",
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
def test_api_post_actual_execution_preflight_or_confirmation_blocks(
    field_name: str,
) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.CREDENTIAL_INJECTION_BLOCKED_API_OR_POST
    assert result.credential_injection_ready is False
    assert result.api_call_allowed is False
    assert result.api_call_attempted is False
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

    assert result.status is Status.CREDENTIAL_INJECTION_BLOCKED_LIVE_ORDER_ONCE
    assert result.credential_injection_ready is False
    assert result.live_order_once_called is False


def test_unsupported_mode_or_safe_handle_label_is_redacted() -> None:
    mode_result = _build(injection_mode="UNSUPPORTED_RAW_MODE")
    label_result = _build(safe_credential_handle_label=RAW_HANDLE_SENTINEL)

    assert mode_result.status is Status.CREDENTIAL_INJECTION_BLOCKED_UNKNOWN
    assert mode_result.injection_mode == "UNSUPPORTED_REDACTED"
    assert label_result.status is Status.CREDENTIAL_INJECTION_BLOCKED_UNSAFE_EXPOSURE
    assert label_result.safe_credential_handle_label == "UNSUPPORTED_REDACTED"
    assert RAW_HANDLE_SENTINEL not in repr(asdict(label_result))


def test_renderer_and_asdict_expose_only_safe_label_status_and_booleans() -> None:
    result = _build()
    rendered = render_live_order_real_credential_injection_controlled_markdown(result)
    payload = repr(asdict(result))

    assert "safe_credential_handle_label: CONTROLLED_CREDENTIAL_HANDLE" in rendered
    assert "safe_injection_status: CREDENTIAL_INJECTION_READY_NO_SIGNING" in rendered
    assert "credential_injection_ready: true" in rendered
    assert "Injection ready does not allow signing." in rendered
    assert "Injection ready does not allow API calls." in rendered
    assert "Injection ready does not allow HTTP POST." in rendered
    assert "Injection ready does not allow live_order_once." in rendered
    assert "credential_value_exposure_attempted: false" in rendered
    assert "credential_raw_handle_exposure_attempted: false" in rendered
    assert "credential_length_exposure_attempted: false" in rendered
    assert "credential_hash_exposure_attempted: false" in rendered
    assert "credential_fingerprint_exposure_attempted: false" in rendered
    assert "credential_metadata_exposure_attempted: false" in rendered
    assert "env_actual_name_exposure_attempted: false" in rendered
    assert "real_signing_allowed: false" in rendered
    assert "api_call_allowed: false" in rendered
    assert "post_allowed_this_step: false" in rendered
    assert "live_order_once_called: false" in rendered

    for forbidden in (
        DUMMY_VALUE,
        RAW_HANDLE_SENTINEL,
        METADATA_SENTINEL,
        "CREDENTIAL_LENGTH_VALUE_SENTINEL",
        "CREDENTIAL_HASH_VALUE_SENTINEL",
        "CREDENTIAL_FINGERPRINT_VALUE_SENTINEL",
        "SIGNATURE_VALUE_SENTINEL",
        "HEADERS_VALUE_SENTINEL",
        "RAW_REQUEST_SENTINEL",
        "RAW_RESPONSE_SENTINEL",
        "REAL_ID_SENTINEL",
    ):
        assert forbidden not in rendered
        assert forbidden not in payload


def test_module_imports_no_env_http_api_post_private_broker_or_live_order_once() -> None:
    module_path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_credential_injection_controlled.py"
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
