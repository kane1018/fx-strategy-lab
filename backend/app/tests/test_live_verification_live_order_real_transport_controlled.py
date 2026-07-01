from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_signing_headers_controlled import (
    LiveOrderRealSigningHeadersControlledInput,
    build_live_order_real_signing_headers_controlled,
)
from app.live_verification.live_order_real_transport_controlled import (
    SAFE_TRANSPORT_LABEL,
    LiveOrderRealTransportControlledInput,
    LiveOrderRealTransportControlledStatus,
    build_live_order_real_transport_controlled,
    render_live_order_real_transport_controlled_markdown,
)

Status = LiveOrderRealTransportControlledStatus
CREDENTIAL_VALUE_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"
RAW_REQUEST_SENTINEL = "RAW_REQUEST_SHOULD_NOT_SURFACE"
RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
REQUEST_BODY_SENTINEL = "REQUEST_BODY_SHOULD_NOT_SURFACE"
RESPONSE_BODY_SENTINEL = "RESPONSE_BODY_SHOULD_NOT_SURFACE"
ENDPOINT_SENTINEL = "ENDPOINT_ACTUAL_VALUE_SHOULD_NOT_SURFACE"
REAL_ID_SENTINEL = "REAL_ID_SHOULD_NOT_SURFACE"
BROKER_RESPONSE_SENTINEL = "BROKER_API_RESPONSE_SHOULD_NOT_SURFACE"


def _input(**overrides: object) -> LiveOrderRealTransportControlledInput:
    base = LiveOrderRealTransportControlledInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_transport_controlled(
        input_snapshot=_input(**overrides),
    )


def test_default_transport_ready_no_api_post_or_live_order_once() -> None:
    result = _build()

    assert result.status is Status.TRANSPORT_READY_NO_API_NO_POST
    assert result.transport_controlled_ready is True
    assert result.transport_mode == "TRANSPORT_CONTROLLED_IMPLEMENTATION_ONLY"
    assert result.safe_transport_label == SAFE_TRANSPORT_LABEL
    assert result.safe_transport_status == Status.TRANSPORT_READY_NO_API_NO_POST.value
    assert result.signing_headers_prerequisite_checked is True
    assert result.signing_headers_prerequisite_satisfied is True
    assert result.signing_headers_controlled_ready is True
    assert result.signing_controlled_ready is True
    assert result.headers_controlled_ready is True
    assert result.blocked_reasons == ()
    assert result.api_call_allowed is False
    assert result.api_call_attempted is False
    assert result.http_client_present is False
    assert result.real_transport_attempted is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.fresh_preflight_executed is False
    assert result.final_confirmation_received is False
    assert result.one_post_max_required is True
    assert result.no_retry_required is True
    assert result.fresh_preflight_required is True
    assert result.final_confirmation_required is True
    assert result.sanitized_result_required is True


def test_safe_signing_headers_result_drives_ready_without_value_exposure() -> None:
    signing_headers_result = build_live_order_real_signing_headers_controlled()
    result = build_live_order_real_transport_controlled(
        signing_headers_result=signing_headers_result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.TRANSPORT_READY_NO_API_NO_POST
    assert result.transport_controlled_ready is True
    assert CREDENTIAL_VALUE_SENTINEL not in payload
    assert SIGNATURE_VALUE_SENTINEL not in payload
    assert HEADERS_VALUE_SENTINEL not in payload
    assert RAW_REQUEST_SENTINEL not in payload
    assert RAW_RESPONSE_SENTINEL not in payload


def test_missing_signing_headers_prerequisite_fails_closed() -> None:
    signing_headers_result = build_live_order_real_signing_headers_controlled(
        input_snapshot=LiveOrderRealSigningHeadersControlledInput(
            signing_declared=False,
        ),
    )
    result = build_live_order_real_transport_controlled(
        signing_headers_result=signing_headers_result,
    )

    assert result.status is Status.TRANSPORT_BLOCKED_MISSING_SIGNING_HEADERS
    assert result.transport_controlled_ready is False
    assert result.signing_headers_prerequisite_satisfied is False
    assert "signing_headers_prerequisite_missing" in result.blocked_reasons
    assert result.api_call_allowed is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"transport_unknown": True}, Status.TRANSPORT_BLOCKED_UNKNOWN),
        ({"transport_failed": True}, Status.TRANSPORT_BLOCKED_FAILED),
        (
            {"transport_unavailable": True},
            Status.TRANSPORT_BLOCKED_UNAVAILABLE,
        ),
        ({"transport_timeout": True}, Status.TRANSPORT_BLOCKED_TIMEOUT),
    ],
)
def test_unknown_failed_unavailable_timeout_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.transport_controlled_ready is False
    assert result.api_call_allowed is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"credential_value_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_CREDENTIAL_VALUE_EXPOSURE,
        ),
        (
            {"signature_value_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_SIGNATURE_VALUE_EXPOSURE,
        ),
        (
            {"headers_value_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_HEADERS_VALUE_EXPOSURE,
        ),
        (
            {"raw_request_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_RAW_REQUEST_EXPOSURE,
        ),
        (
            {"raw_response_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_RAW_RESPONSE_EXPOSURE,
        ),
        (
            {"request_body_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"response_body_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"endpoint_actual_value_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"account_id_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"order_id_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"real_id_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"broker_api_response_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"unsafe_exposure_attempted": True},
            Status.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"safe_to_render": False},
            Status.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"safe_to_serialize": False},
            Status.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE,
        ),
    ],
)
def test_exposure_attempts_block_and_are_sanitized(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.transport_controlled_ready is False
    assert result.credential_value_exposure_attempted is False
    assert result.signature_value_exposure_attempted is False
    assert result.headers_value_exposure_attempted is False
    assert result.raw_request_exposure_attempted is False
    assert result.raw_response_exposure_attempted is False
    assert result.request_body_exposure_attempted is False
    assert result.response_body_exposure_attempted is False
    assert result.endpoint_actual_value_exposure_attempted is False
    assert result.account_id_exposure_attempted is False
    assert result.order_id_exposure_attempted is False
    assert result.real_id_exposure_attempted is False
    assert result.broker_api_response_exposure_attempted is False
    assert result.safe_to_render is True
    assert result.safe_to_serialize is True


@pytest.mark.parametrize(
    "field_name",
    [
        "api_call_allowed",
        "api_call_attempted",
        "http_client_present",
        "real_transport_attempted",
    ],
)
def test_transport_api_or_http_attempts_block(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.TRANSPORT_BLOCKED_API_ATTEMPTED
    assert result.transport_controlled_ready is False
    assert result.api_call_allowed is False
    assert result.api_call_attempted is False
    assert result.http_client_present is False
    assert result.real_transport_attempted is False


@pytest.mark.parametrize(
    "field_name",
    [
        "http_post_executed",
        "post_allowed_this_step",
        "post_executed",
    ],
)
def test_post_attempts_block(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.TRANSPORT_BLOCKED_POST_ATTEMPTED
    assert result.transport_controlled_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False


def test_order_endpoint_blocks_separately() -> None:
    result = _build(order_endpoint_called=True)

    assert result.status is Status.TRANSPORT_BLOCKED_ORDER_ENDPOINT
    assert result.transport_controlled_ready is False
    assert result.order_endpoint_called is False


def test_live_order_once_blocks_separately() -> None:
    result = _build(live_order_once_called=True)

    assert result.status is Status.TRANSPORT_BLOCKED_LIVE_ORDER_ONCE
    assert result.transport_controlled_ready is False
    assert result.live_order_once_called is False


@pytest.mark.parametrize(
    "field_name",
    [
        "actual_checker_execution_performed",
        "actual_result_receipt_received",
        "actual_receipt_handoff_executed",
        "fresh_preflight_executed",
        "final_confirmation_received",
        "one_post_max_required",
        "no_retry_required",
        "fresh_preflight_required",
        "final_confirmation_required",
        "sanitized_result_required",
    ],
)
def test_future_post_gate_or_actual_execution_blocks(field_name: str) -> None:
    value = False if field_name.endswith("_required") else True
    result = _build(**{field_name: value})

    assert result.status is Status.TRANSPORT_BLOCKED_PREFLIGHT_OR_CONFIRMATION
    assert result.transport_controlled_ready is False
    assert result.actual_checker_execution_performed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_receipt_handoff_executed is False
    assert result.fresh_preflight_executed is False
    assert result.final_confirmation_received is False


def test_unsupported_mode_or_safe_label_is_redacted() -> None:
    mode_result = _build(transport_mode="UNSUPPORTED_RAW_MODE")
    label_result = _build(safe_transport_label=RAW_REQUEST_SENTINEL)

    assert mode_result.status is Status.TRANSPORT_BLOCKED_UNKNOWN
    assert mode_result.transport_mode == "UNSUPPORTED_REDACTED"
    assert label_result.status is Status.TRANSPORT_BLOCKED_UNSAFE_EXPOSURE
    assert label_result.safe_transport_label == "UNSUPPORTED_REDACTED"
    assert RAW_REQUEST_SENTINEL not in repr(asdict(label_result))


def test_renderer_and_asdict_expose_only_safe_summary() -> None:
    result = _build()
    rendered = render_live_order_real_transport_controlled_markdown(result)
    payload = repr(asdict(result))

    assert "transport_controlled_ready: true" in rendered
    assert f"safe_transport_label: {SAFE_TRANSPORT_LABEL}" in rendered
    assert "safe_transport_status: TRANSPORT_READY_NO_API_NO_POST" in rendered
    assert "Transport ready does not allow POST." in rendered
    assert "Transport ready does not allow order endpoint calls." in rendered
    assert "Transport ready does not allow live_order_once." in rendered
    assert "api_call_allowed: false" in rendered
    assert "http_post_executed: false" in rendered
    assert "order_endpoint_called: false" in rendered
    assert "live_order_once_called: false" in rendered
    assert "one_post_max_required: true" in rendered
    assert "no_retry_required: true" in rendered

    for forbidden in (
        CREDENTIAL_VALUE_SENTINEL,
        SIGNATURE_VALUE_SENTINEL,
        HEADERS_VALUE_SENTINEL,
        RAW_REQUEST_SENTINEL,
        RAW_RESPONSE_SENTINEL,
        REQUEST_BODY_SENTINEL,
        RESPONSE_BODY_SENTINEL,
        ENDPOINT_SENTINEL,
        REAL_ID_SENTINEL,
        BROKER_RESPONSE_SENTINEL,
    ):
        assert forbidden not in rendered
        assert forbidden not in payload


def test_module_imports_no_env_crypto_http_api_post_private_broker_or_live_order_once() -> None:
    module_path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_transport_controlled.py"
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
        "send",
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
