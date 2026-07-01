from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_operator_execution_result_category_contract import (
    LiveOrderRealOperatorExecutionResultCategory,
    LiveOrderRealOperatorExecutionResultCategoryContractInput,
    LiveOrderRealOperatorExecutionResultCategoryContractMode,
    LiveOrderRealOperatorExecutionResultCategoryContractStatus,
    build_live_order_real_operator_execution_result_category_contract,
    render_live_order_real_operator_execution_result_category_contract_markdown,
)

Status = LiveOrderRealOperatorExecutionResultCategoryContractStatus
Mode = LiveOrderRealOperatorExecutionResultCategoryContractMode
Category = LiveOrderRealOperatorExecutionResultCategory
UNSUPPORTED_RAW_CATEGORY = "RAW_OPERATOR_RESULT_CATEGORY_SHOULD_NOT_SURFACE"
UNSUPPORTED_SAFE_CATEGORY = "UNSUPPORTED_REDACTED"


def _input(
    **overrides: object,
) -> LiveOrderRealOperatorExecutionResultCategoryContractInput:
    base = LiveOrderRealOperatorExecutionResultCategoryContractInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_operator_execution_result_category_contract(
        input_snapshot=_input(**overrides),
    )


def test_not_provided_valid_input_ready_no_result() -> None:
    result = _build()

    assert (
        result.status
        is Status.OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_NO_RESULT
    )
    assert result.operator_execution_result_category_contract_ready is True
    assert (
        result.category_contract_mode
        == Mode.OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ONLY.value
    )
    assert result.allowed_category_set_declared is True
    assert result.operator_executed_execution_boundary_ready is True
    assert result.operator_result_handoff_safe is True
    assert result.operator_checker_workflow_ready is True
    assert result.operator_result_category == Category.NOT_PROVIDED.value
    assert result.operator_result_category_is_safe_label is True
    assert result.operator_result_category_is_allowed is True
    assert result.operator_result_provided is False
    assert result.operator_result_ready_confirmed is False
    assert result.operator_result_blocked is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.blocked_reasons == ()


def test_ready_confirmed_valid_input_ready_confirmed_no_post() -> None:
    result = _build(
        operator_result_category=Category.READY_CONFIRMED.value,
        operator_result_provided=True,
        operator_result_ready_confirmed=True,
    )

    assert (
        result.status
        is Status.OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_CONFIRMED_NO_POST
    )
    assert result.operator_execution_result_category_contract_ready is True
    assert result.operator_result_category == Category.READY_CONFIRMED.value
    assert result.operator_result_provided is True
    assert result.operator_result_ready_confirmed is True
    assert result.operator_result_blocked is False
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
        {"category_contract_mode": "UNSUPPORTED_RAW_MODE"},
        {"category_contract_declared": False},
        {"allowed_category_set_declared": False},
        {"operator_executed_execution_boundary_ready": False},
        {"operator_result_handoff_safe": False},
        {"operator_checker_workflow_ready": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_INPUT
    )
    assert result.operator_execution_result_category_contract_ready is False


def test_unsupported_raw_category_blocks_without_echoing_raw_value() -> None:
    result = _build(operator_result_category=UNSUPPORTED_RAW_CATEGORY)
    rendered = render_live_order_real_operator_execution_result_category_contract_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNSUPPORTED_CATEGORY
    )
    assert result.operator_result_category == UNSUPPORTED_SAFE_CATEGORY
    assert result.unsupported_category_present is True
    assert UNSUPPORTED_RAW_CATEGORY not in rendered
    assert UNSUPPORTED_RAW_CATEGORY not in payload
    assert UNSUPPORTED_SAFE_CATEGORY in rendered
    assert UNSUPPORTED_SAFE_CATEGORY in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_category_is_safe_label": False},
        {
            "operator_result_category": Category.READY_CONFIRMED.value,
            "operator_result_provided": False,
            "operator_result_ready_confirmed": True,
        },
        {
            "operator_result_category": Category.READY_CONFIRMED.value,
            "operator_result_provided": True,
            "operator_result_ready_confirmed": False,
        },
        {"operator_result_provided": True},
        {"operator_result_ready_confirmed": True},
        {"operator_result_blocked": True},
        {"operator_result_category": Category.BLOCKED_UNSAFE_DETAIL.value},
    ],
)
def test_unsafe_category_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNSAFE_CATEGORY
    )


def test_category_is_allowed_false_blocks_as_unsupported_category() -> None:
    result = _build(operator_result_category_is_allowed=False)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNSUPPORTED_CATEGORY
    )


@pytest.mark.parametrize(
    "category",
    [
        Category.BLOCKED_UNKNOWN,
        Category.BLOCKED_FAILED,
        Category.BLOCKED_UNAVAILABLE,
        Category.BLOCKED_STALE,
        Category.BLOCKED_TIMEOUT,
    ],
)
def test_unknown_failed_unavailable_stale_timeout_categories_block(
    category: Category,
) -> None:
    result = _build(
        operator_result_category=category.value,
        operator_result_provided=True,
        operator_result_blocked=True,
    )

    blocked_status = (
        Status
        .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT
    )
    assert result.status is blocked_status
    assert result.operator_result_category == category.value
    assert result.operator_result_blocked is True
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


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
def test_unknown_failed_unavailable_stale_timeout_flags_block(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    blocked_status = (
        Status
        .BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT
    )
    assert result.status is blocked_status
    assert result.operator_result_unknown is False
    assert result.operator_result_failed is False
    assert result.operator_result_unavailable is False
    assert result.operator_result_stale is False
    assert result.operator_result_timeout is False


@pytest.mark.parametrize(
    "category",
    [
        Category.BLOCKED_REUSED,
        Category.BLOCKED_PREVIOUS_TURN,
    ],
)
def test_reused_previous_categories_block(category: Category) -> None:
    result = _build(
        operator_result_category=category.value,
        operator_result_provided=True,
        operator_result_blocked=True,
    )

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_REUSED_OR_PREVIOUS
    )
    assert result.operator_result_category == category.value
    assert result.operator_result_blocked is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_reused": True},
        {"operator_result_previous_turn": True},
    ],
)
def test_reused_previous_flags_block(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_REUSED_OR_PREVIOUS
    )
    assert result.operator_result_reused is False
    assert result.operator_result_previous_turn is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_detail_present": True},
        {"operator_result_raw_value_present": True},
        {"operator_result_saved": True},
        {"operator_result_displayed": True},
        {"operator_result_broadly_propagated": True},
        {"checker_result_detail_present": True},
        {"sentinel_value_present": True},
    ],
)
def test_result_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_RESULT_EXPOSURE
    )
    assert result.operator_result_detail_present is False
    assert result.operator_result_raw_value_present is False
    assert result.checker_result_detail_present is False
    assert result.sentinel_value_present is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"env_variable_names_present": True},
        {"credential_values_present": True},
        {"credential_metadata_present": True},
        {"env_access_requested": True},
        {"credential_read_performed": True},
    ],
)
def test_env_or_credential_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ENV_OR_CREDENTIAL
    )
    assert result.env_variable_names_present is False
    assert result.credential_values_present is False
    assert result.credential_metadata_present is False
    assert result.env_access_requested is False
    assert result.credential_read_performed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"actual_execution_performed": True},
        {"codex_execution_performed": True},
    ],
)
def test_execution_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_EXECUTION
    )
    assert result.actual_execution_performed is False
    assert result.codex_execution_performed is False


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
        is Status.BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_REAL_SIGNING_OR_POST
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
def test_display_or_save_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.BLOCKED_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_DISPLAY_OR_SAVE
    )
    assert result.safe_to_render is True
    assert result.safe_to_serialize is True


def test_renderer_includes_required_category_only_warnings() -> None:
    rendered = render_live_order_real_operator_execution_result_category_contract_markdown(
        _build(
            operator_result_category=Category.READY_CONFIRMED.value,
            operator_result_provided=True,
            operator_result_ready_confirmed=True,
        ),
    )

    assert "This operator execution result category contract is category-only." in rendered
    assert "This contract does not execute the checker." in rendered
    assert "This contract does not access env or .env." in rendered
    assert "This contract does not read credentials." in rendered
    assert "This contract does not expose raw operator result values." in rendered
    assert "READY_CONFIRMED does not allow POST." in rendered
    assert "NOT_PROVIDED is not actual result receipt." in rendered
    assert "This contract does not generate real signatures." in rendered
    assert "This contract does not execute API calls." in rendered
    assert "This contract does not execute HTTP POST." in rendered
    assert "This contract does not call order endpoint." in rendered
    assert "This contract does not call live_order_once." in rendered
    assert (
        "Future actual execution and final confirmation must be separate Steps."
        in rendered
    )


def test_renderer_and_asdict_do_not_include_unsafe_dummy_values() -> None:
    result = _build()
    rendered = render_live_order_real_operator_execution_result_category_contract_markdown(
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
        / "live_order_real_operator_execution_result_category_contract.py"
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
