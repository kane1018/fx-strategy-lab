from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_credential_presence_checker_implementation import (
    LiveOrderRealCredentialPresenceCheckerImplementationInput,
    LiveOrderRealCredentialPresenceCheckerImplementationStatus,
    build_live_order_real_credential_presence_checker_implementation,
    render_live_order_real_credential_presence_checker_implementation_markdown,
)

Status = LiveOrderRealCredentialPresenceCheckerImplementationStatus
UNSUPPORTED_RAW_MODE = "IMPLEMENTATION_RAW_SHOULD_NOT_SURFACE"
UNSUPPORTED_SAFE_MODE = "UNSUPPORTED_REDACTED"


def _input(
    **overrides: object,
) -> LiveOrderRealCredentialPresenceCheckerImplementationInput:
    base = LiveOrderRealCredentialPresenceCheckerImplementationInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_credential_presence_checker_implementation(
        input_snapshot=_input(**overrides),
    )


def test_valid_checker_implementation_skeleton_ready_no_env_no_check() -> None:
    result = _build()

    assert (
        result.status
        is Status.CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_READY_NO_ENV_NO_CHECK
    )
    assert result.checker_implementation_skeleton_ready is True
    assert result.implementation_mode == "CHECKER_IMPLEMENTATION_SKELETON_ONLY"
    assert result.checker_contract_ready is True
    assert result.operator_checker_workflow_ready is True
    assert result.credential_presence_adapter_ready is True
    assert result.credential_presence_check_ready is True
    assert result.implementation_interface_declared is True
    assert result.implementation_lifecycle_declared is True
    assert result.execution_deferred_to_future_step is True
    assert result.execution_performed is False
    assert result.codex_env_access_requested is False
    assert result.actual_environment_presence_check_performed is False
    assert result.env_access_capability_present is False
    assert result.credential_read_capability_present is False
    assert result.credential_values_read is False
    assert result.credential_values_present is False
    assert result.credential_metadata_present is False
    assert result.checker_result_available is False
    assert result.checker_result_detail_present is False
    assert result.checker_result_unknown is False
    assert result.checker_result_failed is False
    assert result.checker_result_unavailable is False
    assert result.checker_result_stale is False
    assert result.operator_workflow_supported is True
    assert result.operator_workflow_preserved is True
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
        {"implementation_mode": UNSUPPORTED_RAW_MODE},
        {"checker_contract_ready": False},
        {"operator_checker_workflow_ready": False},
        {"credential_presence_adapter_ready": False},
        {"credential_presence_check_ready": False},
        {"implementation_interface_declared": False},
        {"implementation_lifecycle_declared": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_INPUT
    )
    assert result.checker_implementation_skeleton_ready is False


def test_unsupported_implementation_mode_is_blocked_and_not_echoed() -> None:
    result = _build(implementation_mode=UNSUPPORTED_RAW_MODE)
    rendered = render_live_order_real_credential_presence_checker_implementation_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_INPUT
    )
    assert result.implementation_mode == UNSUPPORTED_SAFE_MODE
    assert result.unsupported_implementation_mode_present is True
    assert result.raw_implementation_mode_displayed is False
    assert result.raw_implementation_mode_saved is False
    assert UNSUPPORTED_RAW_MODE not in repr(result)
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"execution_deferred_to_future_step": False},
        {"execution_performed": True},
        {"actual_environment_presence_check_performed": True},
    ],
)
def test_execution_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_EXECUTION
    )
    assert result.checker_implementation_skeleton_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"codex_env_access_requested": True},
        {"env_access_capability_present": True},
    ],
)
def test_env_access_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_ENV_ACCESS
    )
    assert result.checker_implementation_skeleton_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_read_capability_present": True},
        {"credential_values_read": True},
        {"credential_values_present": True},
        {"credential_metadata_present": True},
    ],
)
def test_credential_read_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_CREDENTIAL_READ
    )
    assert result.checker_implementation_skeleton_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"checker_result_available": True},
        {"checker_result_detail_present": True},
        {"checker_result_saved": True},
        {"checker_result_displayed": True},
    ],
)
def test_result_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_RESULT_EXPOSURE
    )
    assert result.checker_implementation_skeleton_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"checker_result_unknown": True},
        {"checker_result_failed": True},
        {"checker_result_unavailable": True},
        {"checker_result_stale": True},
    ],
)
def test_unknown_failed_unavailable_stale_blocks(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_UNKNOWN_FAILED_UNAVAILABLE
    )
    assert result.checker_implementation_skeleton_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_workflow_supported": False},
        {"operator_workflow_preserved": False},
    ],
)
def test_operator_workflow_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_OPERATOR_WORKFLOW
    )
    assert result.checker_implementation_skeleton_ready is False


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
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_REAL_SIGNING_OR_POST
    )
    assert result.checker_implementation_skeleton_ready is False


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
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_DISPLAY_OR_SAVE
    )
    assert result.checker_implementation_skeleton_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"retry_allowed": True},
        {"loop_allowed": True},
    ],
)
def test_unsupported_runtime_controls_block(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_UNSUPPORTED
    )
    assert result.checker_implementation_skeleton_ready is False


def test_renderer_includes_safety_warnings_and_no_sensitive_values() -> None:
    result = _build()
    rendered = render_live_order_real_credential_presence_checker_implementation_markdown(
        result,
    )

    assert "This checker implementation is skeleton-only." in rendered
    assert "does not execute the checker" in rendered
    assert "does not access env or .env" in rendered
    assert "does not check the real environment" in rendered
    assert "preserves the operator-executed workflow boundary" in rendered
    assert "does not expose checker result detail" in rendered
    assert "does not generate real signatures" in rendered
    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "does not call live_order_once" in rendered
    assert "Future checker execution must be a separate Step." in rendered
    assert "checker_implementation_skeleton_ready: true" in rendered
    assert "checker_contract_ready: true" in rendered
    assert "operator_checker_workflow_ready: true" in rendered
    assert "execution_deferred_to_future_step: true" in rendered
    assert "execution_performed: false" in rendered
    assert "codex_env_access_requested: false" in rendered
    assert "actual_environment_presence_check_performed: false" in rendered
    assert "operator_workflow_supported: true" in rendered
    assert "operator_workflow_preserved: true" in rendered
    assert "CHECKER_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in rendered
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in rendered
    assert "ENV_NAME_SHOULD_NOT_APPEAR" not in rendered
    assert "OPERATOR_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in rendered
    assert "OPERATOR_SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in rendered
    assert "FULL_APPROVAL_COMMAND_SENTINEL" not in rendered
    assert UNSUPPORTED_RAW_MODE not in rendered


def test_asdict_does_not_contain_sensitive_detail_strings() -> None:
    result = _build()
    payload = repr(asdict(result))

    assert "CHECKER_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in payload
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in payload
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in payload
    assert "ENV_NAME_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in payload
    assert "FULL_APPROVAL_COMMAND_SENTINEL" not in payload
    assert "RAW_REQUEST_SENTINEL" not in payload
    assert "RAW_RESPONSE_SENTINEL" not in payload
    assert "REAL_ORDER_ID_SENTINEL" not in payload
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
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "pbcopy",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_credential_presence_checker_implementation.py"
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
