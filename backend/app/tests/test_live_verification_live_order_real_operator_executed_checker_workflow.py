from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_operator_executed_checker_workflow import (
    LiveOrderRealOperatorExecutedCheckerWorkflowInput,
    LiveOrderRealOperatorExecutedCheckerWorkflowStatus,
    build_live_order_real_operator_executed_checker_workflow,
    render_live_order_real_operator_executed_checker_workflow_markdown,
)

Status = LiveOrderRealOperatorExecutedCheckerWorkflowStatus
UNSUPPORTED_RAW_MODE = "WORKFLOW_RAW_SHOULD_NOT_SURFACE"
UNSUPPORTED_SAFE_MODE = "UNSUPPORTED_REDACTED"


def _input(
    **overrides: object,
) -> LiveOrderRealOperatorExecutedCheckerWorkflowInput:
    base = LiveOrderRealOperatorExecutedCheckerWorkflowInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_operator_executed_checker_workflow(
        input_snapshot=_input(**overrides),
    )


def test_valid_operator_workflow_ready_no_codex_env_no_api_no_post() -> None:
    result = _build()

    assert (
        result.status
        is Status.OPERATOR_CHECKER_WORKFLOW_READY_NO_CODEX_ENV_NO_API_NO_POST
    )
    assert result.operator_checker_workflow_ready is True
    assert result.workflow_mode == "OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY"
    assert result.credential_presence_checker_contract_ready is True
    assert result.credential_presence_adapter_ready is True
    assert result.credential_presence_check_ready is True
    assert result.operator_workflow_declared is True
    assert result.operator_execution_required is True
    assert result.operator_execution_performed_outside_codex is True
    assert result.codex_execution_performed is False
    assert result.codex_env_access_requested is False
    assert result.actual_environment_presence_check_performed_by_codex is False
    assert result.operator_result_handoff_declared is True
    assert result.operator_result_handoff_safe is True
    assert result.operator_result_category_only is True
    assert result.operator_result_provided is True
    assert result.operator_result_is_boolean_only is True
    assert result.operator_result_raw_value_present is False
    assert result.operator_result_raw_value_saved is False
    assert result.operator_result_raw_value_displayed is False
    assert result.operator_result_fresh is True
    assert result.operator_result_stale is False
    assert result.operator_result_reused is False
    assert result.operator_result_previous_turn is False
    assert result.operator_result_timeout is False
    assert result.operator_result_unknown is False
    assert result.operator_result_failed is False
    assert result.operator_result_unavailable is False
    assert result.operator_result_saved is False
    assert result.operator_result_displayed is False
    assert result.operator_result_broadly_propagated is False
    assert result.operator_result_detail_present is False
    assert result.credential_values_present is False
    assert result.credential_metadata_present is False
    assert result.env_variable_names_present is False
    assert result.sentinel_value_present is False
    assert result.checker_result_detail_present is False
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
        {"workflow_mode": UNSUPPORTED_RAW_MODE},
        {"credential_presence_checker_contract_ready": False},
        {"credential_presence_adapter_ready": False},
        {"credential_presence_check_ready": False},
        {"operator_workflow_declared": False},
        {"operator_execution_required": False},
        {"operator_execution_performed_outside_codex": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_INPUT
    assert result.operator_checker_workflow_ready is False


def test_unsupported_workflow_mode_is_blocked_and_not_echoed() -> None:
    result = _build(workflow_mode=UNSUPPORTED_RAW_MODE)
    rendered = render_live_order_real_operator_executed_checker_workflow_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_INPUT
    assert result.workflow_mode == UNSUPPORTED_SAFE_MODE
    assert result.unsupported_workflow_mode_present is True
    assert result.raw_workflow_mode_displayed is False
    assert result.raw_workflow_mode_saved is False
    assert UNSUPPORTED_RAW_MODE not in repr(result)
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"codex_execution_performed": True},
        {"actual_environment_presence_check_performed_by_codex": True},
    ],
)
def test_codex_execution_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_CODEX_EXECUTION
    assert result.operator_checker_workflow_ready is False


def test_codex_env_access_blocks() -> None:
    result = _build(codex_env_access_requested=True)

    assert result.status is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_CODEX_ENV_ACCESS
    assert result.operator_checker_workflow_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_handoff_declared": False},
        {"operator_result_handoff_safe": False},
        {"operator_result_category_only": False},
        {"operator_result_provided": False},
        {"operator_result_is_boolean_only": False},
    ],
)
def test_operator_result_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_HANDOFF
    assert result.operator_checker_workflow_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_raw_value_present": True},
        {"operator_result_raw_value_saved": True},
        {"operator_result_raw_value_displayed": True},
    ],
)
def test_raw_operator_result_value_exposure_blocks(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_RAW_VALUE_EXPOSURE
    assert result.operator_checker_workflow_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_fresh": False},
        {"operator_result_stale": True},
        {"operator_result_reused": True},
        {"operator_result_previous_turn": True},
    ],
)
def test_stale_or_reused_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_STALE_OR_REUSED_RESULT
    )
    assert result.operator_checker_workflow_ready is False


def test_timeout_blocks() -> None:
    result = _build(operator_result_timeout=True)

    assert result.status is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_TIMEOUT
    assert result.operator_checker_workflow_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_unknown": True},
        {"operator_result_failed": True},
        {"operator_result_unavailable": True},
    ],
)
def test_unknown_failed_unavailable_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_UNKNOWN_FAILED_UNAVAILABLE
    )
    assert result.operator_checker_workflow_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_saved": True},
        {"operator_result_displayed": True},
        {"operator_result_broadly_propagated": True},
        {"operator_result_detail_present": True},
        {"sentinel_value_present": True},
        {"checker_result_detail_present": True},
    ],
)
def test_result_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_RESULT_EXPOSURE
    assert result.operator_checker_workflow_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_values_present": True},
        {"credential_metadata_present": True},
    ],
)
def test_credential_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_CREDENTIAL_EXPOSURE
    )
    assert result.operator_checker_workflow_ready is False


def test_env_name_exposure_blocks() -> None:
    result = _build(env_variable_names_present=True)

    assert result.status is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_ENV_NAME_EXPOSURE
    assert result.operator_checker_workflow_ready is False


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
        is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_REAL_SIGNING_OR_POST
    )
    assert result.operator_checker_workflow_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"safe_to_render": False},
        {"safe_to_serialize": False},
    ],
)
def test_display_or_save_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_DISPLAY_OR_SAVE
    assert result.operator_checker_workflow_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"retry_allowed": True},
        {"loop_allowed": True},
    ],
)
def test_unsupported_runtime_controls_block(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_CHECKER_WORKFLOW_UNSUPPORTED
    assert result.operator_checker_workflow_ready is False


def test_renderer_includes_safety_warnings_and_no_sensitive_values() -> None:
    result = _build()
    rendered = render_live_order_real_operator_executed_checker_workflow_markdown(
        result,
    )

    assert "This operator checker workflow is skeleton-only." in rendered
    assert "operator-side checking outside Codex" in rendered
    assert "This operator result handoff is safe boolean/category only." in rendered
    assert "does not access env or .env" in rendered
    assert "does not read credentials" in rendered
    assert "does not check the real environment inside Codex" in rendered
    assert "does not expose operator result detail" in rendered
    assert "does not expose raw operator result values" in rendered
    assert "does not expose credential metadata" in rendered
    assert "Previous-turn, reused, stale, unknown, failed, unavailable" in rendered
    assert "does not generate real signatures" in rendered
    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "does not call live_order_once" in rendered
    assert "Future real checker execution must be a separate Step." in rendered
    assert "operator_checker_workflow_ready: true" in rendered
    assert "operator_execution_performed_outside_codex: true" in rendered
    assert "codex_execution_performed: false" in rendered
    assert "codex_env_access_requested: false" in rendered
    assert "operator_result_handoff_declared: true" in rendered
    assert "operator_result_handoff_safe: true" in rendered
    assert "operator_result_category_only: true" in rendered
    assert "operator_result_provided: true" in rendered
    assert "operator_result_is_boolean_only: true" in rendered
    assert "operator_result_raw_value_present: false" in rendered
    assert "operator_result_raw_value_saved: false" in rendered
    assert "operator_result_raw_value_displayed: false" in rendered
    assert "operator_result_fresh: true" in rendered
    assert "operator_result_timeout: false" in rendered
    assert "operator_result_unknown: false" in rendered
    assert "operator_result_failed: false" in rendered
    assert "operator_result_unavailable: false" in rendered
    assert "OPERATOR_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in rendered
    assert "RAW_OPERATOR_RESULT_VALUE_SHOULD_NOT_APPEAR" not in rendered
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in rendered
    assert "ENV_NAME_SHOULD_NOT_APPEAR" not in rendered
    assert "OPERATOR_SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in rendered
    assert "FULL_APPROVAL_COMMAND_SENTINEL" not in rendered
    assert UNSUPPORTED_RAW_MODE not in rendered


def test_asdict_does_not_contain_sensitive_detail_strings() -> None:
    result = _build()
    payload = repr(asdict(result))

    assert "OPERATOR_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in payload
    assert "RAW_OPERATOR_RESULT_VALUE_SHOULD_NOT_APPEAR" not in payload
    assert "CHECKER_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in payload
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in payload
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in payload
    assert "ENV_NAME_SHOULD_NOT_APPEAR" not in payload
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
        / "live_order_real_operator_executed_checker_workflow.py"
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
