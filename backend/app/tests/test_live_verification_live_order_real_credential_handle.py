from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_credential_handle import (
    LiveOrderRealCredentialHandleInput,
    LiveOrderRealCredentialHandleStatus,
    build_live_order_real_credential_handle,
    render_live_order_real_credential_handle_markdown,
)

Status = LiveOrderRealCredentialHandleStatus


def _input(**overrides: object) -> LiveOrderRealCredentialHandleInput:
    base = LiveOrderRealCredentialHandleInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_credential_handle(
        input_snapshot=_input(**overrides),
    )


def test_valid_handle_contract_input_ready_no_value_no_env() -> None:
    result = _build()

    assert result.status is Status.CREDENTIAL_HANDLE_READY_NO_VALUE_NO_ENV
    assert result.credential_handle_ready is True
    assert result.handle_mode == "HANDLE_CONTRACT_ONLY"
    assert result.credential_boundary_ready is True
    assert result.handle_requested is True
    assert result.handle_created is False
    assert result.handle_contains_value is False
    assert result.handle_contains_secret is False
    assert result.handle_contains_token is False
    assert result.handle_contains_key_material is False
    assert result.handle_contains_identifier is False
    assert result.handle_metadata_exposed is False
    assert result.credential_values_provided is False
    assert result.credential_values_loaded is False
    assert result.env_access_requested is False
    assert result.can_generate_real_signature is False
    assert result.can_generate_real_headers is False
    assert result.can_execute_http_post is False
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
        {"handle_mode": "REAL_HANDLE"},
        {"credential_boundary_ready": False},
        {"handle_requested": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_HANDLE_INPUT
    assert result.credential_handle_ready is False


def test_handle_created_blocks() -> None:
    result = _build(handle_created=True)

    assert result.status is Status.BLOCKED_CREDENTIAL_HANDLE_CREATED
    assert "handle_created_unsafe" in result.blocked_reasons
    assert result.handle_created is False


@pytest.mark.parametrize(
    "field_name",
    [
        "handle_contains_value",
        "handle_contains_secret",
        "handle_contains_token",
        "handle_contains_key_material",
    ],
)
def test_value_secret_token_or_key_material_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.BLOCKED_CREDENTIAL_HANDLE_VALUE_OR_SECRET
    assert result.handle_contains_value is False
    assert result.handle_contains_secret is False
    assert result.handle_contains_token is False
    assert result.handle_contains_key_material is False


@pytest.mark.parametrize(
    "field_name",
    [
        "handle_contains_identifier",
        "handle_length_available",
        "handle_hash_available",
        "handle_fingerprint_available",
        "handle_preview_available",
        "handle_prefix_available",
        "handle_suffix_available",
    ],
)
def test_identifier_or_metadata_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.BLOCKED_CREDENTIAL_HANDLE_IDENTIFIER_OR_METADATA
    assert result.handle_contains_identifier is False
    assert result.handle_metadata_exposed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"handle_value_displayed": True},
        {"handle_value_saved": True},
        {"handle_metadata_displayed": True},
        {"handle_metadata_saved": True},
        {"safe_to_render": False},
        {"safe_to_serialize": False},
    ],
)
def test_display_save_or_unsafe_render_serialization_blocks(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_HANDLE_DISPLAY_OR_SAVE
    assert result.safe_to_render is True
    assert result.safe_to_serialize is True


@pytest.mark.parametrize(
    "field_name",
    [
        "env_access_requested",
        "dotenv_access_requested",
    ],
)
def test_env_or_dotenv_access_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.BLOCKED_CREDENTIAL_HANDLE_ENV_ACCESS
    assert result.env_access_requested is False
    assert result.dotenv_access_requested is False


@pytest.mark.parametrize(
    "field_name",
    [
        "credential_values_provided",
        "credential_values_loaded",
    ],
)
def test_credential_value_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.BLOCKED_CREDENTIAL_HANDLE_CREDENTIAL_VALUE
    assert result.credential_values_provided is False
    assert result.credential_values_loaded is False


@pytest.mark.parametrize(
    "field_name",
    [
        "can_generate_real_signature",
        "can_generate_real_headers",
        "can_execute_http_post",
        "http_post_executed",
        "order_endpoint_called",
        "live_order_once_called",
        "post_allowed_this_step",
        "post_executed",
    ],
)
def test_real_signing_headers_or_post_blocks(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.BLOCKED_CREDENTIAL_HANDLE_REAL_SIGNING_OR_POST


@pytest.mark.parametrize("field_name", ["retry_allowed", "loop_allowed"])
def test_retry_or_loop_is_unsupported(field_name: str) -> None:
    result = _build(**{field_name: True})

    assert result.status is Status.BLOCKED_CREDENTIAL_HANDLE_UNSUPPORTED


def test_renderer_includes_required_warnings_without_handle_or_credential_metadata() -> None:
    result = _build()
    rendered = render_live_order_real_credential_handle_markdown(result)

    assert "This credential handle is contract-only." in rendered
    assert "does not create a real handle" in rendered
    assert "does not contain credential values" in rendered
    assert "does not access env or .env" in rendered
    assert "does not expose credential metadata" in rendered
    assert "does not generate real signatures" in rendered
    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "Future real credential injection must be a separate Step." in rendered
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in rendered
    assert "HANDLE_ID_SENTINEL" not in rendered
    assert "HANDLE_TOKEN_SENTINEL" not in rendered
    assert "HANDLE_SECRET_SENTINEL" not in rendered
    assert "HANDLE_VALUE_SENTINEL" not in rendered
    assert "KEY_MATERIAL_SENTINEL" not in rendered
    assert "HANDLE_LENGTH_VALUE_SENTINEL" not in rendered
    assert "HANDLE_HASH_VALUE_SENTINEL" not in rendered
    assert "HANDLE_FINGERPRINT_VALUE_SENTINEL" not in rendered
    assert "HANDLE_PREVIEW_VALUE_SENTINEL" not in rendered
    assert "HANDLE_PREFIX_VALUE_SENTINEL" not in rendered
    assert "HANDLE_SUFFIX_VALUE_SENTINEL" not in rendered
    assert "RAW_REQUEST_SENTINEL" not in rendered
    assert "RAW_RESPONSE_SENTINEL" not in rendered


def test_asdict_does_not_contain_handle_values_identifiers_or_metadata_fields() -> None:
    result = _build()
    payload = repr(asdict(result))

    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in payload
    assert "HANDLE_ID_SENTINEL" not in payload
    assert "HANDLE_TOKEN_SENTINEL" not in payload
    assert "HANDLE_SECRET_SENTINEL" not in payload
    assert "HANDLE_VALUE_SENTINEL" not in payload
    assert "KEY_MATERIAL_SENTINEL" not in payload
    assert "HANDLE_LENGTH_VALUE_SENTINEL" not in payload
    assert "HANDLE_HASH_VALUE_SENTINEL" not in payload
    assert "HANDLE_FINGERPRINT_VALUE_SENTINEL" not in payload
    assert "HANDLE_PREVIEW_VALUE_SENTINEL" not in payload
    assert "HANDLE_PREFIX_VALUE_SENTINEL" not in payload
    assert "HANDLE_SUFFIX_VALUE_SENTINEL" not in payload
    assert "handle_length_available" not in payload
    assert "handle_hash_available" not in payload
    assert "handle_fingerprint_available" not in payload
    assert "handle_preview_available" not in payload
    assert "handle_prefix_available" not in payload
    assert "handle_suffix_available" not in payload
    assert "RAW_REQUEST_SENTINEL" not in payload
    assert "RAW_RESPONSE_SENTINEL" not in payload


def test_new_module_does_not_import_env_http_private_broker_or_live_order_once() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_credential_handle.py"
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
