from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_http_transport_interface import (
    LiveOrderRealHttpTransportInterfaceInput,
    LiveOrderRealHttpTransportInterfaceStatus,
    build_live_order_real_http_transport_interface,
    render_live_order_real_http_transport_interface_markdown,
)

Status = LiveOrderRealHttpTransportInterfaceStatus


def _input(**overrides: object) -> LiveOrderRealHttpTransportInterfaceInput:
    base = LiveOrderRealHttpTransportInterfaceInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_http_transport_interface(
        input_snapshot=_input(**overrides),
    )


def test_valid_interface_only_input_ready_no_api_no_post() -> None:
    result = _build()

    assert result.status is Status.HTTP_TRANSPORT_INTERFACE_READY_NO_API_NO_POST
    assert result.interface_ready is True
    assert result.interface_mode == "INTERFACE_ONLY"
    assert result.method == "POST"
    assert result.path == "/v1/order"
    assert result.endpoint_contract_ready is True
    assert result.signing_contract_ready is True
    assert result.dummy_signing_ready is True
    assert result.private_order_transport_contract_ready is True
    assert result.http_client_present is False
    assert result.can_execute_http_post is False
    assert result.can_call_order_endpoint is False
    assert result.can_call_live_order_once is False
    assert result.credential_values_provided is False
    assert result.signature_value_generated is False
    assert result.header_values_present is False
    assert result.raw_request_present is False
    assert result.raw_response_present is False
    assert result.real_ids_present is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.retry_allowed is False
    assert result.loop_allowed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"interface_mode": "REAL_TRANSPORT"},
        {"method": "GET"},
        {"path": "/v1/other"},
        {"endpoint_contract_ready": False},
        {"order_body_allowlist_passed": False},
        {"stable_serialization_ready": False},
        {"signing_contract_ready": False},
        {"dummy_signing_ready": False},
        {"dummy_signature_check_passed": False},
        {"private_order_transport_contract_ready": False},
        {"one_shot_no_retry_ready": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_HTTP_TRANSPORT_INTERFACE_INPUT
    assert result.interface_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"post_attempt_limit": 2},
        {"post_attempt_count_before": 1},
        {"retry_allowed": True},
        {"loop_allowed": True},
        {"add_order_allowed": True},
        {"change_order_allowed": True},
        {"cancel_order_allowed": True},
        {"close_order_allowed": True},
    ],
)
def test_retry_loop_or_attempt_state_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_HTTP_TRANSPORT_INTERFACE_RETRY_OR_LOOP


def test_real_transport_requested_blocks() -> None:
    result = _build(real_transport_requested=True)

    assert result.status is Status.BLOCKED_HTTP_TRANSPORT_INTERFACE_REAL_TRANSPORT_REQUESTED
    assert "real_transport_requested" in result.blocked_reasons


def test_http_client_present_blocks() -> None:
    result = _build(http_client_present=True)

    assert result.status is Status.BLOCKED_HTTP_TRANSPORT_INTERFACE_HTTP_CLIENT_PRESENT
    assert "http_client_present" in result.blocked_reasons


def test_http_post_capability_blocks() -> None:
    result = _build(can_execute_http_post=True)

    assert result.status is Status.BLOCKED_HTTP_TRANSPORT_INTERFACE_HTTP_POST
    assert "can_execute_http_post" in result.blocked_reasons


def test_order_endpoint_capability_blocks() -> None:
    result = _build(can_call_order_endpoint=True)

    assert result.status is Status.BLOCKED_HTTP_TRANSPORT_INTERFACE_ORDER_ENDPOINT
    assert "can_call_order_endpoint" in result.blocked_reasons


def test_live_order_once_capability_blocks() -> None:
    result = _build(can_call_live_order_once=True)

    assert result.status is Status.BLOCKED_HTTP_TRANSPORT_INTERFACE_LIVE_ORDER_ONCE
    assert "can_call_live_order_once" in result.blocked_reasons


@pytest.mark.parametrize(
    "field_name",
    [
        "credential_values_provided",
        "signature_value_generated",
        "header_values_present",
        "raw_request_present",
        "raw_response_present",
    ],
)
def test_raw_or_secret_exposure_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.BLOCKED_HTTP_TRANSPORT_INTERFACE_RAW_OR_SECRET_EXPOSURE


def test_real_id_exposure_blocks() -> None:
    result = _build(real_ids_present=True)

    assert result.status is Status.BLOCKED_HTTP_TRANSPORT_INTERFACE_REAL_ID_EXPOSURE


def test_renderer_includes_required_warnings_without_sensitive_values() -> None:
    result = _build()
    rendered = render_live_order_real_http_transport_interface_markdown(result)

    assert "This HTTP transport interface is interface-only." in rendered
    assert "does not include an HTTP client" in rendered
    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "does not call order endpoint" in rendered
    assert "does not call live_order_once" in rendered
    assert "Future real transport must be a separate Step." in rendered
    assert "RAW_REQUEST_SENTINEL" not in rendered
    assert "RAW_RESPONSE_SENTINEL" not in rendered
    assert "REAL_ORDER_ID_SENTINEL" not in rendered
    assert "FULL_APPROVAL_COMMAND_SENTINEL" not in rendered
    assert "DUMMY_SIGNATURE_VALUE_SENTINEL" not in rendered
    assert "DUMMY_SECRET_MATERIAL_VALUE_SENTINEL" not in rendered


def test_asdict_does_not_contain_sensitive_or_real_id_values() -> None:
    result = _build()
    payload = repr(asdict(result))

    assert "RAW_REQUEST_SENTINEL" not in payload
    assert "RAW_RESPONSE_SENTINEL" not in payload
    assert "REAL_ORDER_ID_SENTINEL" not in payload
    assert "REAL_EXECUTION_ID_SENTINEL" not in payload
    assert "REAL_POSITION_ID_SENTINEL" not in payload
    assert "FULL_APPROVAL_COMMAND_SENTINEL" not in payload
    assert "DUMMY_SIGNATURE_VALUE_SENTINEL" not in payload
    assert "DUMMY_SECRET_MATERIAL_VALUE_SENTINEL" not in payload


def test_new_module_does_not_import_http_private_broker_live_order_once_or_env_access() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_http_transport_interface.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
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
        "app.brokers",
        "app.private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "getenv",
        "ENABLE_LIVE_TRADING",
        "GMO_FX_API_KEY",
        "GMO_FX_API_SECRET",
        "Authorization",
        "OrderRequest",
        "speedOrder",
        "changeOrder",
        "cancelOrders",
        "closeOrder",
        "live_order_once",
        "pbcopy",
    }
    blocked_attrs = {"environ", "getenv"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def _is_blocked_module(module: str, blocked_modules: set[str]) -> bool:
    return any(
        module == blocked or module.startswith(f"{blocked}.")
        for blocked in blocked_modules
    )
