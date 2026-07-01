from __future__ import annotations

import ast
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from app.live_verification.live_order_real_operator_execution_result_category_contract import (
    LiveOrderRealOperatorExecutionResultCategory,
)
from app.live_verification.live_order_real_operator_result_handoff_receipt import (
    LiveOrderRealOperatorResultHandoffReceiptInput,
    LiveOrderRealOperatorResultHandoffReceiptMode,
    LiveOrderRealOperatorResultHandoffReceiptStatus,
    build_live_order_real_operator_result_handoff_receipt,
    render_live_order_real_operator_result_handoff_receipt_markdown,
)

Status = LiveOrderRealOperatorResultHandoffReceiptStatus
Mode = LiveOrderRealOperatorResultHandoffReceiptMode
Category = LiveOrderRealOperatorExecutionResultCategory
UNSUPPORTED_RAW_CATEGORY = "RAW_RECEIPT_CATEGORY_SHOULD_NOT_SURFACE"
UNSUPPORTED_SAFE_CATEGORY = "UNSUPPORTED_REDACTED"


def _input(**overrides: object) -> LiveOrderRealOperatorResultHandoffReceiptInput:
    base = LiveOrderRealOperatorResultHandoffReceiptInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_operator_result_handoff_receipt(
        input_snapshot=_input(**overrides),
    )


def test_not_provided_valid_receipt_ready_not_provided() -> None:
    result = _build()

    assert result.status is Status.OPERATOR_RESULT_HANDOFF_RECEIPT_READY_NOT_PROVIDED
    assert result.operator_result_handoff_receipt_ready is True
    assert result.receipt_mode == Mode.OPERATOR_RESULT_HANDOFF_RECEIPT_SKELETON_ONLY.value
    assert result.receipt_contract_declared is True
    assert result.receipt_boundary_declared is True
    assert result.receipt_one_time_required is True
    assert result.receipt_fresh_required is True
    assert result.receipt_non_reuse_required is True
    assert result.receipt_non_raw_required is True
    assert result.receipt_non_detail_required is True
    assert result.operator_execution_result_category_contract_ready is True
    assert result.operator_executed_execution_boundary_ready is True
    assert result.operator_result_handoff_safe is True
    assert result.operator_result_category == Category.NOT_PROVIDED.value
    assert result.operator_result_category_is_safe_label is True
    assert result.operator_result_category_is_allowed is True
    assert result.receipt_provided is False
    assert result.receipt_category_confirmed is False
    assert result.receipt_current_turn is True
    assert result.receipt_fresh is True
    assert result.receipt_stale is False
    assert result.receipt_reused is False
    assert result.receipt_previous_turn is False
    assert result.receipt_timeout is False
    assert result.receipt_unknown is False
    assert result.receipt_failed is False
    assert result.receipt_unavailable is False
    assert result.receipt_raw_value_present is False
    assert result.receipt_detail_present is False
    assert result.receipt_id_present is False
    assert result.receipt_token_present is False
    assert result.receipt_nonce_present is False
    assert result.receipt_hash_present is False
    assert result.receipt_fingerprint_present is False
    assert result.receipt_length_present is False
    assert result.actual_execution_performed is False
    assert result.codex_execution_performed is False
    assert result.env_access_requested is False
    assert result.credential_read_performed is False
    assert result.can_generate_real_signature is False
    assert result.can_generate_real_headers is False
    assert result.can_execute_http_post is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.blocked_reasons == ()


def test_ready_confirmed_valid_receipt_ready_confirmed_no_post() -> None:
    result = _build(
        operator_result_category=Category.READY_CONFIRMED.value,
        receipt_provided=True,
        receipt_category_confirmed=True,
    )

    assert (
        result.status is Status.OPERATOR_RESULT_HANDOFF_RECEIPT_READY_CONFIRMED_NO_POST
    )
    assert result.operator_result_handoff_receipt_ready is True
    assert result.operator_result_category == Category.READY_CONFIRMED.value
    assert result.receipt_provided is True
    assert result.receipt_category_confirmed is True
    assert result.receipt_current_turn is True
    assert result.receipt_fresh is True
    assert result.receipt_reused is False
    assert result.receipt_previous_turn is False
    assert result.receipt_raw_value_present is False
    assert result.receipt_detail_present is False
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
        {"receipt_mode": "UNSUPPORTED_RAW_MODE"},
        {"receipt_contract_declared": False},
        {"receipt_boundary_declared": False},
        {"receipt_one_time_required": False},
        {"receipt_fresh_required": False},
        {"receipt_non_reuse_required": False},
        {"receipt_non_raw_required": False},
        {"receipt_non_detail_required": False},
        {"operator_execution_result_category_contract_ready": False},
        {"operator_executed_execution_boundary_ready": False},
        {"operator_result_handoff_safe": False},
    ],
)
def test_input_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_INPUT
    assert result.operator_result_handoff_receipt_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_category_is_safe_label": False},
        {"operator_result_category_is_allowed": False},
        {
            "operator_result_category": Category.READY_CONFIRMED.value,
            "receipt_provided": False,
            "receipt_category_confirmed": True,
        },
        {
            "operator_result_category": Category.READY_CONFIRMED.value,
            "receipt_provided": True,
            "receipt_category_confirmed": False,
        },
        {"receipt_provided": True},
        {"receipt_category_confirmed": True},
        {"operator_result_category": Category.BLOCKED_UNSAFE_DETAIL.value},
    ],
)
def test_unsafe_category_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNSAFE_CATEGORY


def test_unsupported_raw_category_blocks_without_echoing_raw_value() -> None:
    result = _build(operator_result_category=UNSUPPORTED_RAW_CATEGORY)
    rendered = render_live_order_real_operator_result_handoff_receipt_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNSUPPORTED
    assert result.operator_result_category == UNSUPPORTED_SAFE_CATEGORY
    assert result.unsupported_category_present is True
    assert UNSUPPORTED_RAW_CATEGORY not in rendered
    assert UNSUPPORTED_RAW_CATEGORY not in payload
    assert UNSUPPORTED_SAFE_CATEGORY in rendered
    assert UNSUPPORTED_SAFE_CATEGORY in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_current_turn": False},
        {"receipt_fresh": False},
        {"receipt_stale": True},
        {"receipt_reused": True},
        {"receipt_previous_turn": True},
        {"receipt_expired": True},
        {"operator_result_category": Category.BLOCKED_STALE.value},
        {"operator_result_category": Category.BLOCKED_REUSED.value},
        {"operator_result_category": Category.BLOCKED_PREVIOUS_TURN.value},
    ],
)
def test_stale_reused_previous_receipts_block(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_STALE_OR_REUSED
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_timeout": True},
        {"receipt_unknown": True},
        {"receipt_failed": True},
        {"receipt_unavailable": True},
        {"operator_result_category": Category.BLOCKED_UNKNOWN.value},
        {"operator_result_category": Category.BLOCKED_FAILED.value},
        {"operator_result_category": Category.BLOCKED_UNAVAILABLE.value},
        {"operator_result_category": Category.BLOCKED_TIMEOUT.value},
    ],
)
def test_unknown_failed_unavailable_timeout_receipts_block(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    blocked_status = (
        Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_UNKNOWN_FAILED_UNAVAILABLE_TIMEOUT
    )
    assert result.status is blocked_status
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_raw_value_present": True},
        {"receipt_detail_present": True},
    ],
)
def test_raw_or_detail_receipt_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_RAW_OR_DETAIL


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_id_present": True},
        {"receipt_token_present": True},
        {"receipt_nonce_present": True},
        {"receipt_hash_present": True},
        {"receipt_fingerprint_present": True},
        {"receipt_length_present": True},
    ],
)
def test_identifier_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    identifier_status = (
        Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_IDENTIFIER_EXPOSURE
    )
    assert result.status is identifier_status


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_saved": True},
        {"receipt_displayed": True},
        {"receipt_broadly_propagated": True},
        {"operator_result_detail_present": True},
        {"operator_result_raw_value_present": True},
        {"checker_result_detail_present": True},
        {"sentinel_value_present": True},
    ],
)
def test_result_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_RESULT_EXPOSURE


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

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_ENV_OR_CREDENTIAL


@pytest.mark.parametrize(
    "overrides",
    [
        {"actual_execution_performed": True},
        {"codex_execution_performed": True},
    ],
)
def test_execution_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_EXECUTION


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

    signing_status = Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_REAL_SIGNING_OR_POST
    assert result.status is signing_status


@pytest.mark.parametrize(
    "overrides",
    [
        {"safe_to_render": False},
        {"safe_to_serialize": False},
    ],
)
def test_display_or_save_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_OPERATOR_RESULT_HANDOFF_RECEIPT_DISPLAY_OR_SAVE


def test_renderer_contains_required_warnings_and_no_forbidden_dummy_values() -> None:
    result = _build(
        operator_result_category=Category.READY_CONFIRMED.value,
        receipt_provided=True,
        receipt_category_confirmed=True,
    )
    rendered = render_live_order_real_operator_result_handoff_receipt_markdown(result)

    assert "This operator result handoff receipt is skeleton-only." in rendered
    assert "one-time, fresh, non-reuse, non-raw, and non-detail" in rendered
    assert "This receipt does not execute the checker." in rendered
    assert "This receipt does not access env or .env." in rendered
    assert "This receipt does not read credentials." in rendered
    assert "This receipt does not expose raw operator result values." in rendered
    assert "READY_CONFIRMED receipt does not allow POST." in rendered
    assert "NOT_PROVIDED receipt is not an actual result." in rendered
    assert "This receipt does not execute API calls." in rendered
    assert "This receipt does not execute HTTP POST." in rendered
    assert "This receipt does not call live_order_once." in rendered
    forbidden_values = (
        "CHECKER_RESULT_DETAIL_SHOULD_NOT_APPEAR",
        "CREDENTIAL_METADATA_SHOULD_NOT_APPEAR",
        "ENV_NAME_SHOULD_NOT_APPEAR",
        "OPERATOR_RESULT_DETAIL_SHOULD_NOT_APPEAR",
        "RAW_OPERATOR_RESULT_SHOULD_NOT_APPEAR",
        "RECEIPT_RAW_VALUE_SHOULD_NOT_APPEAR",
        "RECEIPT_ID_SHOULD_NOT_APPEAR",
        "SENTINEL_TEXT_SHOULD_NOT_APPEAR",
    )
    payload = repr(asdict(result))
    for forbidden in forbidden_values:
        assert forbidden not in rendered
        assert forbidden not in payload


def test_new_module_has_no_env_http_private_broker_or_live_order_imports() -> None:
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
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    package_root = Path(__file__).resolve().parents[1] / "live_verification"
    path = package_root / "live_order_real_operator_result_handoff_receipt.py"
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
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def _is_blocked_module(module: str, blocked_modules: set[str]) -> bool:
    return any(module == blocked or module.startswith(f"{blocked}.") for blocked in blocked_modules)


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""
