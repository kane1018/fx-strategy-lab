from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_credential_presence_check import (
    LiveOrderRealCredentialPresenceCheckInput,
    LiveOrderRealCredentialPresenceCheckStatus,
    build_live_order_real_credential_presence_check,
    render_live_order_real_credential_presence_check_markdown,
)

Status = LiveOrderRealCredentialPresenceCheckStatus


def _input(**overrides: object) -> LiveOrderRealCredentialPresenceCheckInput:
    base = LiveOrderRealCredentialPresenceCheckInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_credential_presence_check(
        input_snapshot=_input(**overrides),
    )


def test_valid_operator_provided_sentinel_skeleton_ready_no_env() -> None:
    result = _build()

    assert (
        result.status
        is Status.CREDENTIAL_PRESENCE_CHECK_READY_OPERATOR_PROVIDED_NO_ENV
    )
    assert result.credential_presence_check_ready is True
    assert result.presence_check_mode == "OPERATOR_PROVIDED_SENTINEL_ONLY"
    assert result.credential_boundary_ready is True
    assert result.credential_handle_ready is True
    assert result.credential_injection_ready is True
    assert result.operator_assertion_provided is True
    assert result.operator_assertion_is_boolean_only is True
    assert result.operator_sentinel_received is True
    assert result.operator_sentinel_fresh is True
    assert result.operator_sentinel_reused is False
    assert result.operator_sentinel_stale is False
    assert result.operator_sentinel_previous_turn is False
    assert result.sentinel_value_present is False
    assert result.sentinel_value_displayed is False
    assert result.sentinel_value_saved is False
    assert result.sentinel_hash_available is False
    assert result.sentinel_fingerprint_available is False
    assert result.sentinel_length_available is False
    assert result.credential_values_present is False
    assert result.credential_metadata_present is False
    assert result.credential_presence_checked_against_environment is False
    assert result.env_access_requested is False
    assert result.dotenv_access_requested is False
    assert result.printenv_requested is False
    assert result.presence_result_broadly_propagated is False
    assert result.presence_result_saved is False
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
        {"presence_check_mode": "REAL_ENV"},
        {"credential_boundary_ready": False},
        {"credential_handle_ready": False},
        {"credential_injection_ready": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECK_INPUT
    assert result.credential_presence_check_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_assertion_provided": False},
        {"operator_assertion_is_boolean_only": False},
        {"operator_sentinel_received": False},
    ],
)
def test_operator_assertion_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECK_OPERATOR_ASSERTION
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_sentinel_fresh": False},
        {"operator_sentinel_reused": True},
        {"operator_sentinel_stale": True},
        {"operator_sentinel_previous_turn": True},
    ],
)
def test_stale_reused_or_previous_turn_sentinel_blocks(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECK_STALE_OR_REUSED_SENTINEL
    )


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

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECK_SENTINEL_EXPOSURE


def test_credential_value_blocks() -> None:
    result = _build(credential_values_present=True)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECK_CREDENTIAL_VALUE


def test_credential_metadata_blocks() -> None:
    result = _build(credential_metadata_present=True)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECK_CREDENTIAL_METADATA
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_presence_checked_against_environment": True},
        {"env_access_requested": True},
        {"dotenv_access_requested": True},
        {"printenv_requested": True},
    ],
)
def test_env_access_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECK_ENV_ACCESS


@pytest.mark.parametrize(
    "overrides",
    [
        {"presence_result_broadly_propagated": True},
        {"presence_result_saved": True},
    ],
)
def test_broad_propagation_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECK_BROAD_PROPAGATION


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

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECK_REAL_SIGNING_OR_POST
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"safe_to_render": False},
        {"safe_to_serialize": False},
    ],
)
def test_display_or_save_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECK_DISPLAY_OR_SAVE


def test_renderer_includes_required_warnings_and_no_sensitive_values() -> None:
    result = _build()
    rendered = render_live_order_real_credential_presence_check_markdown(result)

    assert "This credential presence check is skeleton-only." in rendered
    assert "does not access env or .env" in rendered
    assert "does not check the real environment" in rendered
    assert "does not expose the sentinel value" in rendered
    assert "does not expose credential metadata" in rendered
    assert "does not generate real signatures" in rendered
    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "Future real credential presence check must be a separate Step." in rendered
    assert "credential_presence_check_ready: true" in rendered
    assert "operator_sentinel_fresh: true" in rendered
    assert "operator_sentinel_reused: false" in rendered
    assert "operator_sentinel_stale: false" in rendered
    assert "sentinel_value_present: false" in rendered
    assert "credential_presence_checked_against_environment: false" in rendered
    assert "env_access_requested: false" in rendered
    assert "OPERATOR_SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in rendered
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in rendered
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in rendered
    assert "HANDLE_ID_SENTINEL" not in rendered
    assert "RAW_REQUEST_SENTINEL" not in rendered
    assert "RAW_RESPONSE_SENTINEL" not in rendered


def test_asdict_does_not_contain_sentinel_credential_metadata_or_raw_values() -> None:
    result = _build()
    payload = repr(asdict(result))

    assert "OPERATOR_SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_HASH_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_FINGERPRINT_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_LENGTH_SHOULD_NOT_APPEAR" not in payload
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in payload
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in payload
    assert "HANDLE_ID_SENTINEL" not in payload
    assert "HANDLE_VALUE_SENTINEL" not in payload
    assert "RAW_REQUEST_SENTINEL" not in payload
    assert "RAW_RESPONSE_SENTINEL" not in payload
    assert "REAL_ORDER_ID_SENTINEL" not in payload


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
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "pbcopy",
    }
    blocked_attrs = {"environ", "getenv"}
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_credential_presence_check.py"
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
