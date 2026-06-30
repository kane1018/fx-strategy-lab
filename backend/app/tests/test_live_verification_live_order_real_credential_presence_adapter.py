from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_credential_presence_adapter import (
    LiveOrderRealCredentialPresenceAdapterInput,
    LiveOrderRealCredentialPresenceAdapterStatus,
    build_live_order_real_credential_presence_adapter,
    render_live_order_real_credential_presence_adapter_markdown,
)

Status = LiveOrderRealCredentialPresenceAdapterStatus


def _input(**overrides: object) -> LiveOrderRealCredentialPresenceAdapterInput:
    base = LiveOrderRealCredentialPresenceAdapterInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_credential_presence_adapter(
        input_snapshot=_input(**overrides),
    )


def test_valid_adapter_skeleton_ready_no_env_no_real_check() -> None:
    result = _build()

    assert result.status is Status.CREDENTIAL_PRESENCE_ADAPTER_READY_NO_ENV_NO_REAL_CHECK
    assert result.credential_presence_adapter_ready is True
    assert result.adapter_mode == "PRESENCE_ADAPTER_SKELETON_ONLY"
    assert result.credential_presence_check_ready is True
    assert result.credential_boundary_ready is True
    assert result.credential_handle_ready is True
    assert result.credential_injection_ready is True
    assert result.operator_provided_presence_result is True
    assert result.operator_presence_result_is_boolean_only is True
    assert result.operator_presence_result_fresh is True
    assert result.operator_presence_result_reused is False
    assert result.operator_presence_result_stale is False
    assert result.operator_presence_result_previous_turn is False
    assert result.presence_result_adapted is True
    assert result.presence_result_saved is False
    assert result.presence_result_displayed is False
    assert result.presence_result_broadly_propagated is False
    assert result.sentinel_value_present is False
    assert result.sentinel_value_displayed is False
    assert result.sentinel_value_saved is False
    assert result.sentinel_hash_available is False
    assert result.sentinel_fingerprint_available is False
    assert result.sentinel_length_available is False
    assert result.credential_values_present is False
    assert result.credential_metadata_present is False
    assert result.actual_environment_presence_check_performed is False
    assert result.env_access_requested is False
    assert result.dotenv_access_requested is False
    assert result.printenv_requested is False
    assert result.real_checker_attached is False
    assert result.real_checker_executed is False
    assert result.can_generate_real_signature is False
    assert result.can_generate_real_headers is False
    assert result.can_execute_http_post is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"adapter_mode": "REAL_PRESENCE_ADAPTER"},
        {"credential_presence_check_ready": False},
        {"credential_boundary_ready": False},
        {"credential_handle_ready": False},
        {"credential_injection_ready": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_INPUT
    assert result.credential_presence_adapter_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_provided_presence_result": False},
        {"operator_presence_result_is_boolean_only": False},
        {"presence_result_adapted": False},
    ],
)
def test_operator_result_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_OPERATOR_RESULT
    assert result.credential_presence_adapter_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_presence_result_fresh": False},
        {"operator_presence_result_reused": True},
        {"operator_presence_result_stale": True},
        {"operator_presence_result_previous_turn": True},
    ],
)
def test_stale_reused_or_previous_turn_result_blocks(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_STALE_OR_REUSED_RESULT
    assert result.credential_presence_adapter_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"sentinel_value_present": True},
        {"sentinel_value_displayed": True},
        {"sentinel_value_saved": True},
        {"sentinel_hash_available": True},
        {"sentinel_fingerprint_available": True},
        {"sentinel_length_available": True},
    ],
)
def test_sentinel_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_SENTINEL_EXPOSURE
    assert result.credential_presence_adapter_ready is False


def test_credential_value_blocks() -> None:
    result = _build(credential_values_present=True)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_CREDENTIAL_VALUE
    assert result.credential_presence_adapter_ready is False


def test_credential_metadata_blocks() -> None:
    result = _build(credential_metadata_present=True)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_CREDENTIAL_METADATA
    assert result.credential_presence_adapter_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"env_access_requested": True},
        {"dotenv_access_requested": True},
        {"printenv_requested": True},
    ],
)
def test_env_access_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_ENV_ACCESS
    assert result.credential_presence_adapter_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"actual_environment_presence_check_performed": True},
        {"real_checker_attached": True},
        {"real_checker_executed": True},
    ],
)
def test_real_checker_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_REAL_CHECKER
    assert result.credential_presence_adapter_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"presence_result_saved": True},
        {"presence_result_broadly_propagated": True},
    ],
)
def test_broad_propagation_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_BROAD_PROPAGATION
    assert result.credential_presence_adapter_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"can_generate_real_signature": True},
        {"can_generate_real_headers": True},
        {"can_execute_http_post": True},
        {"http_post_executed": True},
        {"order_endpoint_called": True},
        {"live_order_once_called": True},
        {"post_allowed_this_step": True},
        {"post_executed": True},
    ],
)
def test_real_signing_or_post_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_REAL_SIGNING_OR_POST
    assert result.credential_presence_adapter_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"presence_result_displayed": True},
        {"safe_to_render": False},
        {"safe_to_serialize": False},
    ],
)
def test_display_or_save_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_ADAPTER_DISPLAY_OR_SAVE
    assert result.credential_presence_adapter_ready is False


def test_renderer_includes_warnings_and_no_sensitive_values() -> None:
    result = _build()
    rendered = render_live_order_real_credential_presence_adapter_markdown(result)

    assert "This credential presence adapter is skeleton-only." in rendered
    assert "does not access env or .env" in rendered
    assert "does not check the real environment" in rendered
    assert "does not attach or execute a real checker" in rendered
    assert "does not expose the sentinel value" in rendered
    assert "does not expose credential metadata" in rendered
    assert "does not generate real signatures" in rendered
    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "operator_presence_result_fresh: true" in rendered
    assert "operator_presence_result_reused: false" in rendered
    assert "operator_presence_result_stale: false" in rendered
    assert "presence_result_adapted: true" in rendered
    assert "actual_environment_presence_check_performed: false" in rendered
    assert "env_access_requested: false" in rendered
    assert "real_checker_attached: false" in rendered
    assert "real_checker_executed: false" in rendered
    assert "OPERATOR_SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in rendered
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in rendered
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in rendered
    assert "HANDLE_ID_SENTINEL" not in rendered
    assert "RAW_REQUEST_SENTINEL" not in rendered
    assert "RAW_RESPONSE_SENTINEL" not in rendered
    assert "REAL_ORDER_ID_SENTINEL" not in rendered
    assert "APPROVAL_COMMAND_SENTINEL" not in rendered


def test_asdict_does_not_contain_sentinel_credential_metadata_or_raw_values() -> None:
    result = _build()
    payload = repr(asdict(result))

    assert "OPERATOR_SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_HASH_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_FINGERPRINT_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_LENGTH_SHOULD_NOT_APPEAR" not in payload
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in payload
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in payload
    assert "HANDLE_ID_SENTINEL" not in payload
    assert "HANDLE_VALUE_SENTINEL" not in payload
    assert "TOKEN_VALUE_SENTINEL" not in payload
    assert "SECRET_VALUE_SENTINEL" not in payload
    assert "KEY_MATERIAL_SENTINEL" not in payload
    assert "SIGNATURE_VALUE_SENTINEL" not in payload
    assert "HEADER_VALUE_SENTINEL" not in payload
    assert "RAW_REQUEST_SENTINEL" not in payload
    assert "RAW_RESPONSE_SENTINEL" not in payload
    assert "REAL_ORDER_ID_SENTINEL" not in payload
    assert "REAL_EXECUTION_ID_SENTINEL" not in payload
    assert "REAL_POSITION_ID_SENTINEL" not in payload
    assert "APPROVAL_COMMAND_SENTINEL" not in payload


def test_new_module_does_not_import_http_private_broker_live_order_once_or_env_access() -> None:
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
        "speedOrder",
        "changeOrder",
        "cancelOrders",
        "closeOrder",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "pbcopy",
    }
    blocked_attrs = {"environ", "getenv"}
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_credential_presence_adapter.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))

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
