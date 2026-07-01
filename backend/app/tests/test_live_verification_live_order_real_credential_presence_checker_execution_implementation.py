from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_credential_presence_checker_execution_implementation import (  # noqa: E501
    CredentialPresenceCheckerExecutionImplementationMode,
    LiveOrderRealCredentialPresenceCheckerExecutionImplementationInput,
    LiveOrderRealCredentialPresenceCheckerExecutionImplementationStatus,
    build_live_order_real_credential_presence_checker_execution_implementation,
    render_live_order_real_credential_presence_checker_execution_implementation_markdown,
)

Status = LiveOrderRealCredentialPresenceCheckerExecutionImplementationStatus
Mode = CredentialPresenceCheckerExecutionImplementationMode
UNSUPPORTED_RAW_MODE = "EXECUTION_IMPLEMENTATION_RAW_SHOULD_NOT_SURFACE"
UNSUPPORTED_SAFE_MODE = "UNSUPPORTED_REDACTED"


def _input(
    **overrides: object,
) -> LiveOrderRealCredentialPresenceCheckerExecutionImplementationInput:
    base = LiveOrderRealCredentialPresenceCheckerExecutionImplementationInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_credential_presence_checker_execution_implementation(
        input_snapshot=_input(**overrides),
    )


def test_valid_checker_execution_implementation_ready_no_env_no_check() -> None:
    result = _build()

    ready_status = (
        Status
        .CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_READY_NO_ENV_NO_CHECK
    )
    assert result.status is ready_status
    assert result.checker_execution_implementation_skeleton_ready is True
    assert (
        result.execution_implementation_mode
        == Mode.CHECKER_EXECUTION_IMPLEMENTATION_SKELETON_ONLY.value
    )
    assert result.checker_execution_contract_ready is True
    assert result.checker_implementation_skeleton_ready is True
    assert result.operator_result_handoff_safe is True
    assert result.operator_checker_workflow_ready is True
    assert result.execution_implementation_declared is True
    assert result.execution_interface_declared is True
    assert result.execution_lifecycle_declared is True
    assert result.execution_result_mapping_declared is True
    assert result.execution_stop_conditions_declared is True
    assert result.execution_deferred_to_future_step is True
    assert result.execution_performed is False
    assert result.execution_performed_by_codex is False
    assert result.execution_performed_by_operator is False
    assert result.env_access_requested is False
    assert result.codex_env_access_requested is False
    assert result.actual_environment_presence_check_performed is False
    assert result.credential_read_performed is False
    assert result.credential_values_present is False
    assert result.credential_metadata_present is False
    assert result.checker_result_available is False
    assert result.checker_result_detail_present is False
    assert result.checker_result_unknown is False
    assert result.checker_result_failed is False
    assert result.checker_result_unavailable is False
    assert result.checker_result_stale is False
    assert result.checker_result_timeout is False
    assert result.checker_result_saved is False
    assert result.checker_result_displayed is False
    assert result.operator_result_detail_present is False
    assert result.operator_result_raw_value_present is False
    assert result.operator_result_reused is False
    assert result.operator_result_previous_turn is False
    assert result.operator_result_timeout is False
    assert result.can_generate_real_signature is False
    assert result.can_generate_real_headers is False
    assert result.can_execute_http_post is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.safe_to_render is True
    assert result.safe_to_serialize is True
    assert result.retry_allowed is False
    assert result.loop_allowed is False
    assert result.blocked_reasons == ()


@pytest.mark.parametrize(
    "overrides",
    [
        {"execution_implementation_mode": UNSUPPORTED_RAW_MODE},
        {"checker_execution_contract_ready": False},
        {"checker_implementation_skeleton_ready": False},
        {"operator_checker_workflow_ready": False},
        {"execution_implementation_declared": False},
        {"execution_interface_declared": False},
        {"execution_lifecycle_declared": False},
        {"execution_result_mapping_declared": False},
        {"execution_stop_conditions_declared": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_INPUT
    )
    assert result.checker_execution_implementation_skeleton_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"execution_deferred_to_future_step": False},
        {"execution_performed": True},
        {"execution_performed_by_codex": True},
        {"execution_performed_by_operator": True},
        {"actual_environment_presence_check_performed": True},
    ],
)
def test_execution_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_EXECUTION
    )
    assert result.execution_performed is False
    assert result.execution_performed_by_codex is False
    assert result.execution_performed_by_operator is False
    assert result.actual_environment_presence_check_performed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"env_access_requested": True},
        {"codex_env_access_requested": True},
    ],
)
def test_env_access_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_ENV_ACCESS
    )
    assert result.env_access_requested is False
    assert result.codex_env_access_requested is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_read_performed": True},
        {"credential_values_present": True},
        {"credential_metadata_present": True},
    ],
)
def test_credential_read_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_CREDENTIAL_READ
    )
    assert result.credential_read_performed is False
    assert result.credential_values_present is False
    assert result.credential_metadata_present is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"checker_result_available": True},
        {"checker_result_detail_present": True},
        {"checker_result_saved": True},
        {"checker_result_displayed": True},
    ],
)
def test_result_exposure_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_RESULT_EXPOSURE
    )
    assert result.checker_result_available is False
    assert result.checker_result_detail_present is False
    assert result.checker_result_saved is False
    assert result.checker_result_displayed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"checker_result_unknown": True},
        {"checker_result_failed": True},
        {"checker_result_unavailable": True},
        {"checker_result_stale": True},
        {"checker_result_timeout": True},
    ],
)
def test_unknown_failed_unavailable_stale_timeout_blockers(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    blocked_status = (
        Status
        .BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT
    )
    assert result.status is blocked_status
    assert result.checker_result_unknown is False
    assert result.checker_result_failed is False
    assert result.checker_result_unavailable is False
    assert result.checker_result_stale is False
    assert result.checker_result_timeout is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_handoff_safe": False},
        {"operator_result_detail_present": True},
        {"operator_result_raw_value_present": True},
        {"operator_result_reused": True},
        {"operator_result_previous_turn": True},
        {"operator_result_timeout": True},
    ],
)
def test_operator_handoff_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_OPERATOR_HANDOFF
    )
    assert result.operator_result_detail_present is False
    assert result.operator_result_raw_value_present is False
    assert result.operator_result_reused is False
    assert result.operator_result_previous_turn is False
    assert result.operator_result_timeout is False


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
def test_real_signing_or_post_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_REAL_SIGNING_OR_POST
    )
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
        {"safe_to_render": False},
        {"safe_to_serialize": False},
    ],
)
def test_display_or_save_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_DISPLAY_OR_SAVE
    )
    assert result.safe_to_render is True
    assert result.safe_to_serialize is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"retry_allowed": True},
        {"loop_allowed": True},
    ],
)
def test_retry_or_loop_unsupported(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_UNSUPPORTED
    )
    assert result.retry_allowed is False
    assert result.loop_allowed is False


def test_unsupported_execution_implementation_mode_does_not_echo_raw_value() -> None:
    result = _build(execution_implementation_mode=UNSUPPORTED_RAW_MODE)
    rendered = (
        render_live_order_real_credential_presence_checker_execution_implementation_markdown(
            result,
        )
    )
    payload = repr(asdict(result))

    assert (
        result.status
        is Status.BLOCKED_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_INPUT
    )
    assert result.execution_implementation_mode == UNSUPPORTED_SAFE_MODE
    assert result.unsupported_execution_implementation_mode_present is True
    assert result.raw_execution_implementation_mode_displayed is False
    assert result.raw_execution_implementation_mode_saved is False
    assert UNSUPPORTED_RAW_MODE not in repr(result)
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


def test_renderer_includes_required_skeleton_only_warnings() -> None:
    result = _build()
    rendered = (
        render_live_order_real_credential_presence_checker_execution_implementation_markdown(
            result,
        )
    )

    assert "This checker execution implementation is skeleton-only." in rendered
    assert "This implementation does not execute the checker." in rendered
    assert "This implementation does not access env or .env." in rendered
    assert "This implementation does not read credentials." in rendered
    assert (
        "This implementation does not perform an actual environment presence check."
        in rendered
    )
    assert "Unknown / failed / unavailable / stale / timeout results block POST." in rendered
    assert "This implementation does not generate real signatures." in rendered
    assert "This implementation does not execute API calls." in rendered
    assert "This implementation does not execute HTTP POST." in rendered
    assert "This implementation does not call order endpoint." in rendered
    assert "This implementation does not call live_order_once." in rendered
    assert "Future checker execution must be a separate Step." in rendered
    assert "checker_execution_implementation_skeleton_ready: true" in rendered
    assert "checker_execution_contract_ready: true" in rendered
    assert "operator_result_handoff_safe: true" in rendered
    assert "execution_implementation_declared: true" in rendered
    assert "execution_interface_declared: true" in rendered
    assert "execution_lifecycle_declared: true" in rendered
    assert "execution_result_mapping_declared: true" in rendered
    assert "execution_stop_conditions_declared: true" in rendered
    assert "execution_performed: false" in rendered
    assert "env_access_requested: false" in rendered
    assert "actual_environment_presence_check_performed: false" in rendered
    assert "credential_read_performed: false" in rendered
    assert "checker_result_available: false" in rendered
    assert "checker_result_unknown: false" in rendered
    assert "checker_result_failed: false" in rendered
    assert "checker_result_unavailable: false" in rendered
    assert "checker_result_stale: false" in rendered
    assert "checker_result_timeout: false" in rendered
    assert "operator_result_raw_value_present: false" in rendered
    assert "post_allowed_this_step: false" in rendered
    assert "post_executed: false" in rendered


def test_renderer_does_not_include_forbidden_detail_values() -> None:
    rendered = (
        render_live_order_real_credential_presence_checker_execution_implementation_markdown(
            _build(),
        )
    )

    assert "CHECKER_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in rendered
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in rendered
    assert "ENV_NAME_SHOULD_NOT_APPEAR" not in rendered
    assert "OPERATOR_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in rendered
    assert "RAW_OPERATOR_RESULT_VALUE_SHOULD_NOT_APPEAR" not in rendered
    assert "SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in rendered
    assert "FULL_APPROVAL_COMMAND_SENTINEL" not in rendered
    assert "RAW_REQUEST_SENTINEL" not in rendered
    assert "RAW_RESPONSE_SENTINEL" not in rendered
    assert "REAL_ORDER_ID_SENTINEL" not in rendered
    assert UNSUPPORTED_RAW_MODE not in rendered


def test_asdict_does_not_contain_forbidden_detail_values() -> None:
    payload = repr(asdict(_build()))

    assert "CHECKER_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in payload
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in payload
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in payload
    assert "ENV_NAME_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in payload
    assert "RAW_OPERATOR_RESULT_VALUE_SHOULD_NOT_APPEAR" not in payload
    assert "SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in payload
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
        "dot" + "env",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "Authorization",
        "speed" + "Order",
        "change" + "Order",
        "cancel" + "Orders",
        "close" + "Order",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "pbcopy",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_credential_presence_checker_execution_implementation.py"
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
