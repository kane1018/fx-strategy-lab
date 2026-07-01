from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_operator_executed_execution_boundary import (
    LiveOrderRealOperatorExecutedExecutionBoundaryInput,
    LiveOrderRealOperatorExecutedExecutionBoundaryMode,
    LiveOrderRealOperatorExecutedExecutionBoundaryStatus,
    build_live_order_real_operator_executed_execution_boundary,
    render_live_order_real_operator_executed_execution_boundary_markdown,
)

Status = LiveOrderRealOperatorExecutedExecutionBoundaryStatus
Mode = LiveOrderRealOperatorExecutedExecutionBoundaryMode
UNSUPPORTED_RAW_MODE = "OPERATOR_EXECUTION_BOUNDARY_RAW_SHOULD_NOT_SURFACE"
UNSUPPORTED_SAFE_MODE = "UNSUPPORTED_REDACTED"


def _input(**overrides: object) -> LiveOrderRealOperatorExecutedExecutionBoundaryInput:
    base = LiveOrderRealOperatorExecutedExecutionBoundaryInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_operator_executed_execution_boundary(
        input_snapshot=_input(**overrides),
    )


def test_valid_operator_executed_execution_boundary_ready_no_env_no_check() -> None:
    result = _build()

    assert (
        result.status
        is Status.OPERATOR_EXECUTED_EXECUTION_BOUNDARY_READY_NO_ENV_NO_CHECK
    )
    assert result.operator_executed_execution_boundary_ready is True
    assert (
        result.boundary_mode
        == Mode.OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY.value
    )
    assert result.boundary_declared is True
    assert result.operator_execution_boundary_declared is True
    assert result.operator_execution_must_be_outside_codex is True
    assert result.codex_execution_forbidden is True
    assert result.checker_execution_implementation_skeleton_ready is True
    assert result.checker_execution_contract_ready is True
    assert result.operator_result_handoff_safe is True
    assert result.operator_checker_workflow_ready is True
    assert result.operator_execution_performed is False
    assert result.codex_execution_performed is False
    assert result.env_access_requested is False
    assert result.codex_env_access_requested is False
    assert result.actual_environment_presence_check_performed is False
    assert result.credential_read_performed is False
    assert result.credential_values_present is False
    assert result.credential_metadata_present is False
    assert result.operator_result_provided is False
    assert result.operator_result_safe_boolean_category_only is True
    assert result.operator_result_detail_present is False
    assert result.operator_result_raw_value_present is False
    assert result.operator_result_unknown is False
    assert result.operator_result_failed is False
    assert result.operator_result_unavailable is False
    assert result.operator_result_stale is False
    assert result.operator_result_timeout is False
    assert result.operator_result_reused is False
    assert result.operator_result_previous_turn is False
    assert result.operator_result_saved is False
    assert result.operator_result_displayed is False
    assert result.operator_result_broadly_propagated is False
    assert result.checker_result_detail_present is False
    assert result.env_variable_names_present is False
    assert result.sentinel_value_present is False
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
        {"boundary_mode": UNSUPPORTED_RAW_MODE},
        {"boundary_declared": False},
        {"operator_execution_boundary_declared": False},
        {"operator_execution_must_be_outside_codex": False},
        {"checker_execution_implementation_skeleton_ready": False},
        {"checker_execution_contract_ready": False},
        {"operator_checker_workflow_ready": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_INPUT
    assert result.operator_executed_execution_boundary_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"codex_execution_forbidden": False},
        {"codex_execution_performed": True},
    ],
)
def test_codex_execution_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_CODEX_EXECUTION
    )
    assert result.codex_execution_performed is False


def test_operator_execution_performed_blocks() -> None:
    result = _build(operator_execution_performed=True)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_OPERATOR_EXECUTION
    )
    assert result.operator_execution_performed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"env_access_requested": True},
        {"codex_env_access_requested": True},
        {"actual_environment_presence_check_performed": True},
    ],
)
def test_env_access_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_ENV_ACCESS
    assert result.env_access_requested is False
    assert result.codex_env_access_requested is False
    assert result.actual_environment_presence_check_performed is False


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
        is Status.BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_CREDENTIAL_READ
    )
    assert result.credential_read_performed is False
    assert result.credential_values_present is False
    assert result.credential_metadata_present is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_detail_present": True},
        {"operator_result_saved": True},
        {"operator_result_displayed": True},
        {"operator_result_broadly_propagated": True},
        {"checker_result_detail_present": True},
        {"env_variable_names_present": True},
        {"sentinel_value_present": True},
    ],
)
def test_result_exposure_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_RESULT_EXPOSURE
    )
    assert result.operator_result_detail_present is False
    assert result.operator_result_saved is False
    assert result.operator_result_displayed is False
    assert result.operator_result_broadly_propagated is False
    assert result.checker_result_detail_present is False
    assert result.env_variable_names_present is False
    assert result.sentinel_value_present is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_unknown": True},
        {"operator_result_failed": True},
        {"operator_result_unavailable": True},
        {"operator_result_stale": True},
        {"operator_result_timeout": True},
    ],
)
def test_unknown_failed_unavailable_stale_timeout_blockers(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    blocked_status = (
        Status
        .BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT
    )
    assert result.status is blocked_status
    assert result.operator_result_unknown is False
    assert result.operator_result_failed is False
    assert result.operator_result_unavailable is False
    assert result.operator_result_stale is False
    assert result.operator_result_timeout is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_handoff_safe": False},
        {"operator_result_provided": True},
        {"operator_result_safe_boolean_category_only": False},
        {"operator_result_raw_value_present": True},
        {"operator_result_reused": True},
        {"operator_result_previous_turn": True},
    ],
)
def test_operator_handoff_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_OPERATOR_HANDOFF
    )
    assert result.operator_result_handoff_safe is (
        False if overrides.get("operator_result_handoff_safe") is False else True
    )
    assert result.operator_result_provided is False
    assert result.operator_result_raw_value_present is False
    assert result.operator_result_reused is False
    assert result.operator_result_previous_turn is False


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
        is Status.BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_REAL_SIGNING_OR_POST
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
        is Status.BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_DISPLAY_OR_SAVE
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
def test_unsupported_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_EXECUTED_EXECUTION_BOUNDARY_UNSUPPORTED
    assert result.retry_allowed is False
    assert result.loop_allowed is False


def test_unsupported_boundary_mode_uses_safe_label_without_echoing_raw_value() -> None:
    result = _build(boundary_mode=UNSUPPORTED_RAW_MODE)
    rendered = render_live_order_real_operator_executed_execution_boundary_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert result.boundary_mode == UNSUPPORTED_SAFE_MODE
    assert result.unsupported_boundary_mode_present is True
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


def test_renderer_includes_required_skeleton_warnings() -> None:
    rendered = render_live_order_real_operator_executed_execution_boundary_markdown(
        _build(),
    )

    assert "This operator-executed execution boundary is skeleton-only." in rendered
    assert "This boundary keeps actual checker execution outside Codex." in rendered
    assert "This boundary does not execute the checker." in rendered
    assert "This boundary does not access env or .env." in rendered
    assert "This boundary does not read credentials." in rendered
    assert (
        "This boundary does not perform an actual environment presence check."
        in rendered
    )
    assert "Codex receives only safe boolean/category handoff." in rendered
    assert "Unknown / failed / unavailable / stale / timeout results block POST." in rendered
    assert "This boundary does not generate real signatures." in rendered
    assert "This boundary does not execute API calls." in rendered
    assert "This boundary does not execute HTTP POST." in rendered
    assert "This boundary does not call order endpoint." in rendered
    assert "This boundary does not call live_order_once." in rendered
    assert "Future actual execution must be a separate Step." in rendered


def test_renderer_and_asdict_do_not_include_unsafe_dummy_values() -> None:
    result = _build()
    rendered = render_live_order_real_operator_executed_execution_boundary_markdown(
        result,
    )
    payload = repr(asdict(result))

    forbidden_values = (
        "CHECKER_RESULT_DETAIL_SHOULD_NOT_APPEAR",
        "CREDENTIAL_METADATA_VALUE_SHOULD_NOT_APPEAR",
        "ENV_NAME_SHOULD_NOT_APPEAR",
        "OPERATOR_RESULT_DETAIL_SHOULD_NOT_APPEAR",
        "RAW_OPERATOR_RESULT_VALUE_SHOULD_NOT_APPEAR",
        "SENTINEL_TEXT_SHOULD_NOT_APPEAR",
    )
    for value in forbidden_values:
        assert value not in rendered
        assert value not in payload


def test_new_module_has_no_env_http_private_broker_or_live_order_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_operator_executed_execution_boundary.py"
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
        "live_order_once",
    }
    blocked_names = {
        "environ",
        "getenv",
        "GMO_FX_API_KEY",
        "GMO_FX_API_SECRET",
        "Authorization",
        "speedOrder",
        "changeOrder",
        "cancelOrders",
        "closeOrder",
        "ENABLE_LIVE_TRADING",
        "LIVE_ORDER_PLACED",
        "BROKER_SUBMIT",
        "ORDER_SENT",
        "pbcopy",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                alias.name not in blocked_modules
                and not any(
                    alias.name.startswith(f"{blocked}.")
                    for blocked in blocked_modules
                )
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module not in blocked_modules
            assert not any(module.startswith(f"{blocked}.") for blocked in blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_names
