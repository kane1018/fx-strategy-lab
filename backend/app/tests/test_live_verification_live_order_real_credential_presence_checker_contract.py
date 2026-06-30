from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_credential_presence_checker_contract import (
    LiveOrderRealCredentialPresenceCheckerContractInput,
    LiveOrderRealCredentialPresenceCheckerContractStatus,
    build_live_order_real_credential_presence_checker_contract,
    render_live_order_real_credential_presence_checker_contract_markdown,
)

Status = LiveOrderRealCredentialPresenceCheckerContractStatus
UNSUPPORTED_RAW_MODE = "MODE_RAW_SHOULD_NOT_SURFACE"
UNSUPPORTED_SAFE_MODE = "UNSUPPORTED_REDACTED"


def _input(
    **overrides: object,
) -> LiveOrderRealCredentialPresenceCheckerContractInput:
    base = LiveOrderRealCredentialPresenceCheckerContractInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_credential_presence_checker_contract(
        input_snapshot=_input(**overrides),
    )


def test_valid_checker_contract_ready_no_env_no_real_check() -> None:
    result = _build()

    assert (
        result.status
        is Status.CREDENTIAL_PRESENCE_CHECKER_CONTRACT_READY_NO_ENV_NO_REAL_CHECK
    )
    assert result.credential_presence_checker_contract_ready is True
    assert result.checker_contract_mode == "CHECKER_CONTRACT_ONLY"
    assert result.unsupported_checker_contract_mode_present is False
    assert result.raw_checker_contract_mode_displayed is False
    assert result.raw_checker_contract_mode_saved is False
    assert result.credential_presence_adapter_ready is True
    assert result.credential_presence_check_ready is True
    assert result.credential_boundary_ready is True
    assert result.credential_handle_ready is True
    assert result.credential_injection_ready is True
    assert result.checker_contract_requested is True
    assert result.checker_contract_ready_requested is True
    assert result.real_checker_implementation_present is False
    assert result.real_checker_attached is False
    assert result.real_checker_executed is False
    assert result.actual_environment_presence_check_performed is False
    assert result.env_access_required is True
    assert result.env_access_allowed is False
    assert result.env_access_requested is False
    assert result.dotenv_access_requested is False
    assert result.printenv_requested is False
    assert result.credential_values_available is False
    assert result.credential_values_read is False
    assert result.credential_metadata_available is False
    assert result.checker_result_available is False
    assert result.checker_result_saved is False
    assert result.checker_result_displayed is False
    assert result.checker_result_unknown is False
    assert result.checker_result_failed is False
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
        {"credential_presence_adapter_ready": False},
        {"credential_presence_check_ready": False},
        {"credential_boundary_ready": False},
        {"credential_handle_ready": False},
        {"credential_injection_ready": False},
        {"checker_contract_requested": False},
        {"checker_contract_ready_requested": False},
        {"env_access_required": False},
        {"checker_result_is_boolean_only": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_INPUT
    assert result.credential_presence_checker_contract_ready is False


def test_unsupported_checker_contract_mode_is_blocked_and_not_echoed() -> None:
    result = _build(checker_contract_mode=UNSUPPORTED_RAW_MODE)
    rendered = render_live_order_real_credential_presence_checker_contract_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_UNSUPPORTED
    )
    assert result.credential_presence_checker_contract_ready is False
    assert result.checker_contract_mode == UNSUPPORTED_SAFE_MODE
    assert result.unsupported_checker_contract_mode_present is True
    assert result.raw_checker_contract_mode_displayed is False
    assert result.raw_checker_contract_mode_saved is False
    assert UNSUPPORTED_RAW_MODE not in repr(result)
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"real_checker_implementation_present": True},
        {"real_checker_attached": True},
    ],
)
def test_real_checker_present_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_CHECKER_PRESENT
    )
    assert result.credential_presence_checker_contract_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"real_checker_executed": True},
        {"actual_environment_presence_check_performed": True},
    ],
)
def test_real_check_executed_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_CHECK_EXECUTED
    )
    assert result.credential_presence_checker_contract_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"env_access_allowed": True},
        {"env_access_requested": True},
        {"dotenv_access_requested": True},
        {"printenv_requested": True},
    ],
)
def test_env_access_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_ENV_ACCESS
    assert result.credential_presence_checker_contract_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_values_available": True},
        {"credential_values_read": True},
        {"credential_values_displayed": True},
        {"credential_values_saved": True},
    ],
)
def test_credential_value_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_CREDENTIAL_VALUE
    )
    assert result.credential_presence_checker_contract_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_metadata_available": True},
        {"credential_metadata_displayed": True},
        {"credential_metadata_saved": True},
    ],
)
def test_credential_metadata_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_CREDENTIAL_METADATA
    )
    assert result.credential_presence_checker_contract_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"checker_result_available": True},
        {"checker_result_saved": True},
        {"checker_result_displayed": True},
        {"checker_result_broadly_propagated": True},
    ],
)
def test_checker_result_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_RESULT_EXPOSURE
    )
    assert result.credential_presence_checker_contract_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"checker_result_unknown": True},
        {"checker_result_failed": True},
    ],
)
def test_checker_result_unknown_or_failed_blocks(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_RESULT_UNKNOWN_OR_FAILED
    )
    assert result.credential_presence_checker_contract_ready is False


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
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_REAL_SIGNING_OR_POST
    )
    assert result.credential_presence_checker_contract_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"safe_to_render": False},
        {"safe_to_serialize": False},
    ],
)
def test_display_or_save_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_CONTRACT_DISPLAY_OR_SAVE
    )
    assert result.credential_presence_checker_contract_ready is False


def test_renderer_includes_warnings_and_no_sensitive_values() -> None:
    result = _build()
    rendered = render_live_order_real_credential_presence_checker_contract_markdown(
        result,
    )

    assert "This credential presence checker is contract-only." in rendered
    assert "does not access env or .env" in rendered
    assert "does not check the real environment" in rendered
    assert "does not attach or execute a real checker" in rendered
    assert "does not expose credential metadata" in rendered
    assert "does not persist checker results" in rendered
    assert "does not generate real signatures" in rendered
    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "real_checker_implementation_present: false" in rendered
    assert "actual_environment_presence_check_performed: false" in rendered
    assert "env_access_allowed: false" in rendered
    assert "env_access_requested: false" in rendered
    assert "credential_values_read: false" in rendered
    assert "checker_result_available: false" in rendered
    assert "unsupported_checker_contract_mode_present: false" in rendered
    assert "raw_checker_contract_mode_displayed: false" in rendered
    assert "raw_checker_contract_mode_saved: false" in rendered
    assert "CHECKER_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in rendered
    assert "ENV_NAME_SHOULD_NOT_APPEAR" not in rendered
    assert "OPERATOR_SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in rendered
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in rendered
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in rendered
    assert "RAW_REQUEST_SENTINEL" not in rendered
    assert "RAW_RESPONSE_SENTINEL" not in rendered
    assert "REAL_ORDER_ID_SENTINEL" not in rendered
    assert "APPROVAL_COMMAND_SENTINEL" not in rendered
    assert UNSUPPORTED_RAW_MODE not in rendered


def test_asdict_does_not_contain_credential_env_checker_or_raw_values() -> None:
    result = _build()
    payload = repr(asdict(result))

    assert "CHECKER_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in payload
    assert "ENV_NAME_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_HASH_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_FINGERPRINT_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_LENGTH_SHOULD_NOT_APPEAR" not in payload
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in payload
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in payload
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
    assert UNSUPPORTED_RAW_MODE not in payload


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
        / "live_order_real_credential_presence_checker_contract.py"
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
