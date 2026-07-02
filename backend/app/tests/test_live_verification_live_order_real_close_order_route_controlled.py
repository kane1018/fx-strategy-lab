from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification.live_order_real_close_order_route_controlled import (
    CLOSE_ORDER_TYPE_SAFE_LABEL,
    CloseOrderRouteControlledInput,
    CloseOrderRouteControlledStatus,
    build_close_order_route_controlled,
    render_close_order_route_controlled_markdown,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledInput,
    PositionReadOnlyControlledStatus,
    build_position_read_only_controlled,
)


def _one_position_input() -> CloseOrderRouteControlledInput:
    return CloseOrderRouteControlledInput(
        position_status=PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        position_status_checked=True,
        position_count_safe=1,
    )


def test_no_position_blocks_close() -> None:
    result = build_close_order_route_controlled(
        CloseOrderRouteControlledInput(
            position_status=PositionReadOnlyControlledStatus.NO_POSITION,
            position_status_checked=True,
            position_count_safe=0,
        ),
    )

    assert result.close_route_ready is False
    assert result.close_planning_allowed is False
    assert result.close_execution_allowed_now is False
    assert "no_position" in result.blocked_reasons


def test_one_position_open_allows_close_planning_only() -> None:
    result = build_close_order_route_controlled(_one_position_input())

    assert result.status is CloseOrderRouteControlledStatus.READY
    assert result.close_route_ready is True
    assert result.close_planning_allowed is True
    assert result.close_execution_allowed_now is False
    assert result.close_post_executed is False
    assert result.close_post_count == 0
    assert result.close_retry_allowed is False
    assert result.close_repost_allowed is False
    assert result.close_second_post_allowed is False


def test_multiple_unknown_and_source_missing_block_close() -> None:
    multiple = build_close_order_route_controlled(
        CloseOrderRouteControlledInput(
            position_status=PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED,
            position_status_checked=True,
            position_count_safe=2,
        ),
    )
    unknown = build_close_order_route_controlled()
    missing = build_close_order_route_controlled(
        CloseOrderRouteControlledInput(
            position_status=PositionReadOnlyControlledStatus.SOURCE_MISSING_BLOCKED,
        ),
    )

    assert multiple.close_planning_allowed is False
    assert "multiple_positions_blocked" in multiple.blocked_reasons
    assert unknown.close_planning_allowed is False
    assert "position_unknown" in unknown.blocked_reasons
    assert missing.close_planning_allowed is False
    assert "position_source_missing" in missing.blocked_reasons


def test_exposure_attempts_block_close_without_exposing() -> None:
    raw = build_close_order_route_controlled(
        CloseOrderRouteControlledInput(
            position_status=PositionReadOnlyControlledStatus.RAW_EXPOSURE_BLOCKED,
            raw_position_exposure_attempted=True,
            raw_request_exposure_attempted=True,
            raw_response_exposure_attempted=True,
            broker_api_response_exposure_attempted=True,
        ),
    )
    ids = build_close_order_route_controlled(
        CloseOrderRouteControlledInput(
            position_status=PositionReadOnlyControlledStatus.ID_EXPOSURE_BLOCKED,
            position_id_exposure_attempted=True,
            account_id_exposure_attempted=True,
            order_id_exposure_attempted=True,
            transaction_id_exposure_attempted=True,
        ),
    )
    values = build_close_order_route_controlled(
        CloseOrderRouteControlledInput(
            position_status=PositionReadOnlyControlledStatus.VALUE_EXPOSURE_BLOCKED,
            position_value_exposure_attempted=True,
        ),
    )

    for result in (raw, ids, values):
        assert result.close_route_ready is False
        assert result.raw_position_exposed is False
        assert result.raw_request_exposed is False
        assert result.raw_response_exposed is False
        assert result.broker_api_response_exposed is False
        assert result.position_id_exposed is False
        assert result.account_id_exposed is False
        assert result.order_id_exposed is False
        assert result.transaction_id_exposed is False
        assert result.credential_value_exposed is False
        assert result.signature_value_exposed is False
        assert result.headers_value_exposed is False


def test_sealed_close_instruction_safe_summary_only() -> None:
    result = build_close_order_route_controlled(_one_position_input())
    instruction = result.sealed_close_instruction
    data = asdict(result)
    rendered = render_close_order_route_controlled_markdown(result)
    combined = repr(data) + rendered

    assert instruction.sealed_close_instruction_ready is True
    assert instruction.safe_symbol_label == "USD_JPY"
    assert instruction.safe_side_label == "OPPOSITE_OF_SAFE_POSITION_SIDE"
    assert instruction.safe_units_label == 100
    assert instruction.safe_order_type_label == CLOSE_ORDER_TYPE_SAFE_LABEL
    assert instruction.position_handle_value_exposed is False
    assert instruction.position_id_exposed is False
    assert instruction.raw_position_exposed is False
    for fragment in ("pos-", "order-", "txn-", "acct-", "raw_payload"):
        assert fragment not in combined
    assert "position_id_exposed: false" in rendered


def test_close_execution_readiness_is_planning_only() -> None:
    result = build_close_order_route_controlled(_one_position_input())
    readiness = result.close_execution_readiness

    assert readiness.close_execution_step_may_be_planned is True
    assert readiness.close_execution_requires_new_confirmation is True
    assert readiness.close_execution_requires_time_market_operator_gate is True
    assert readiness.close_execution_requires_position_status_current is True
    assert readiness.close_execution_requires_exactly_one_position is True
    assert readiness.close_execution_requires_no_retry is True
    assert readiness.close_execution_requires_no_second_post is True
    assert readiness.close_execution_requires_raw_id_exposure_false is True
    assert readiness.close_execution_permission_granted_now is False


def test_position_route_result_connects_to_close_route() -> None:
    position = build_position_read_only_controlled(
        PositionReadOnlyControlledInput(
            position_source_available=True,
            position_status_checked=True,
            position_status_unknown=False,
            position_count_safe=1,
        ),
    )

    result = build_close_order_route_controlled(position_result=position)

    assert result.close_planning_allowed is True
    assert result.close_execution_allowed_now is False


def test_default_position_route_unknown_blocks_close() -> None:
    result = build_close_order_route_controlled()

    assert result.close_route_ready is False
    assert result.close_planning_allowed is False
    assert result.close_execution_readiness.close_execution_step_may_be_planned is False
    assert "position_unknown" in result.blocked_reasons


def test_close_route_never_executes_post_retry_ledger_or_receipt() -> None:
    result = build_close_order_route_controlled(
        CloseOrderRouteControlledInput(
            position_status=PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
            position_status_checked=True,
            position_count_safe=1,
            actual_http_post_attempted=True,
            close_post_attempted=True,
            retry_or_repost_attempted=True,
            ledger_update_attempted=True,
            receipt_handoff_attempted=True,
        ),
    )

    assert result.close_route_ready is False
    assert result.actual_http_post_executed is False
    assert result.close_post_executed is False
    assert result.close_post_count == 0
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.receipt_handoff_executed is False
    assert "actual_http_post_attempted" in result.blocked_reasons
    assert "close_post_attempted" in result.blocked_reasons


def test_close_route_module_has_no_api_order_env_private_or_http_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_close_order_route_controlled.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "app.brokers",
        "app.private_api",
        "httpx",
        "requests",
        "urllib",
        "urllib3",
        "socket",
        "subprocess",
        "dotenv",
        "os",
    }
    blocked_names = {
        "live_order_once",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "getenv",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not alias.name.startswith(tuple(blocked_modules))
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(tuple(blocked_modules))
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
