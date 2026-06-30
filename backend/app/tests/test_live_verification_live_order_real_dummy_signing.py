from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_dummy_signing import (
    LiveOrderRealDummySigningInput,
    LiveOrderRealDummySigningStatus,
    build_live_order_real_dummy_signing_check,
    render_live_order_real_dummy_signing_markdown,
)

Status = LiveOrderRealDummySigningStatus


def _input(**overrides: object) -> LiveOrderRealDummySigningInput:
    base = LiveOrderRealDummySigningInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_dummy_signing_check(
        input_snapshot=_input(**overrides),
    )


def test_valid_dummy_input_passes_without_value_exposure() -> None:
    result = _build()

    assert result.status is Status.DUMMY_SIGNING_CHECK_PASSED_NO_VALUE_EXPOSED
    assert result.dummy_signing_ready is True
    assert result.dummy_signature_check_performed is True
    assert result.dummy_signature_check_passed is True
    assert result.algorithm_label == "HMAC-SHA256"
    assert result.method == "POST"
    assert result.path == "/v1/order"
    assert result.header_name_labels == ("API-KEY", "API-TIMESTAMP", "API-SIGN")
    assert result.signature_value_present is False
    assert result.credential_value_present is False
    assert result.header_values_present is False
    assert result.raw_request_displayed is False
    assert result.raw_request_saved is False
    assert result.raw_response_displayed is False
    assert result.raw_response_saved is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.retry_allowed is False
    assert result.loop_allowed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"method": "GET"},
        {"path": "/v1/other"},
        {"body_contract_ready": False},
        {"stable_serialization_ready": False},
        {"dummy_timestamp_label": ""},
        {"dummy_key_material_label": ""},
        {"dummy_secret_material_label": ""},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_DUMMY_SIGNING_INPUT
    assert result.dummy_signing_ready is False
    assert result.dummy_signature_check_passed is False


def test_real_credentials_requested_blocks() -> None:
    result = _build(use_real_credentials=True)

    assert result.status is Status.BLOCKED_DUMMY_SIGNING_REAL_CREDENTIAL_REQUESTED
    assert "use_real_credentials_requested" in result.blocked_reasons


@pytest.mark.parametrize("field_name", ["use_env_credentials", "use_dotenv"])
def test_env_or_dotenv_access_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.BLOCKED_DUMMY_SIGNING_ENV_ACCESS


def test_real_signature_requested_blocks() -> None:
    result = _build(generate_real_signature=True)

    assert result.status is Status.BLOCKED_DUMMY_SIGNING_REAL_SIGNATURE_REQUESTED
    assert "generate_real_signature_requested" in result.blocked_reasons


@pytest.mark.parametrize(
    "field_name",
    ["expose_signature_value", "store_signature_value", "signature_value_present"],
)
def test_signature_value_exposure_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.BLOCKED_DUMMY_SIGNING_SIGNATURE_VALUE_EXPOSURE


@pytest.mark.parametrize(
    "field_name",
    ["expose_header_values", "store_header_values", "header_values_present"],
)
def test_header_value_exposure_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.BLOCKED_DUMMY_SIGNING_HEADER_VALUE_EXPOSURE


@pytest.mark.parametrize(
    "field_name",
    ["expose_credentials", "store_credentials", "credential_value_present"],
)
def test_credential_exposure_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.BLOCKED_DUMMY_SIGNING_CREDENTIAL_EXPOSURE


def test_unsupported_algorithm_blocks() -> None:
    result = _build(algorithm_label="UNSUPPORTED")

    assert result.status is Status.BLOCKED_DUMMY_SIGNING_UNSUPPORTED
    assert "unsupported_algorithm" in result.blocked_reasons


def test_renderer_does_not_include_dummy_signature_secret_or_header_values() -> None:
    result = _build()
    rendered = render_live_order_real_dummy_signing_markdown(result)

    assert "This dummy signing check does not use real credentials." in rendered
    assert "This dummy signing check does not generate real signatures." in rendered
    assert "does not expose signature values" in rendered
    assert "does not expose header values" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "Future real signing must be a separate Step." in rendered
    assert "DUMMY_SIGNATURE_VALUE_SENTINEL" not in rendered
    assert "DUMMY_SECRET_MATERIAL_VALUE_SENTINEL" not in rendered
    assert "DUMMY_HEADER_VALUE_SENTINEL" not in rendered
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in rendered
    assert "RAW_REQUEST_SENTINEL" not in rendered
    assert "RAW_RESPONSE_SENTINEL" not in rendered


def test_asdict_does_not_contain_dummy_signature_secret_header_or_credential_values() -> None:
    result = _build()
    payload = repr(asdict(result))

    assert "DUMMY_SIGNATURE_VALUE_SENTINEL" not in payload
    assert "DUMMY_SECRET_MATERIAL_VALUE_SENTINEL" not in payload
    assert "DUMMY_HEADER_VALUE_SENTINEL" not in payload
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in payload
    assert "RAW_REQUEST_SENTINEL" not in payload
    assert "RAW_RESPONSE_SENTINEL" not in payload
    assert "dummy_secret_material_label" not in payload
    assert "dummy_key_material_label" not in payload
    assert "dummy_timestamp_label" not in payload


def test_new_module_does_not_import_env_http_private_broker_or_live_order_once() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_dummy_signing.py"
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
