from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledInput,
    PositionReadOnlyControlledStatus,
    build_position_read_only_controlled,
    render_position_read_only_controlled_markdown,
)
from app.live_verification.live_order_real_position_read_only_source_controlled import (
    PositionReadOnlySourceControlledInput,
    build_position_read_only_source_controlled,
)


def _safe_source_input(count: int) -> PositionReadOnlyControlledInput:
    return PositionReadOnlyControlledInput(
        position_source_available=True,
        position_status_checked=True,
        position_status_unknown=False,
        position_count_safe=count,
    )


def test_no_position_allows_new_entry_and_blocks_close_planning() -> None:
    result = build_position_read_only_controlled(_safe_source_input(0))

    assert result.position_read_only_route_ready is True
    assert result.position_status_checked is True
    assert result.position_status is PositionReadOnlyControlledStatus.NO_POSITION
    assert result.position_count_safe == 0
    assert result.has_open_position is False
    assert result.has_exactly_one_position is False
    assert result.has_multiple_positions is False
    assert result.new_entry_allowed is True
    assert result.close_planning_allowed is False
    assert result.close_execution_allowed_now is False
    assert result.max_open_positions == 1


def test_one_position_blocks_entry_and_allows_close_planning_only() -> None:
    result = build_position_read_only_controlled(_safe_source_input(1))

    assert result.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert result.position_count_safe == 1
    assert result.has_open_position is True
    assert result.has_exactly_one_position is True
    assert result.new_entry_allowed is False
    assert result.close_planning_allowed is True
    assert result.close_execution_allowed_now is False


def test_multiple_positions_block_entry_and_close_planning() -> None:
    result = build_position_read_only_controlled(_safe_source_input(2))

    assert result.position_read_only_route_ready is False
    assert result.position_status is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    assert result.position_count_safe == 2
    assert result.has_multiple_positions is True
    assert result.new_entry_allowed is False
    assert result.close_planning_allowed is False
    assert "multiple_positions_blocked" in result.blocked_reasons


def test_unknown_and_source_missing_fail_closed() -> None:
    unknown = build_position_read_only_controlled(
        PositionReadOnlyControlledInput(
            position_source_available=True,
            position_status_checked=False,
            position_status_unknown=True,
        ),
    )
    missing = build_position_read_only_controlled(PositionReadOnlyControlledInput())

    assert unknown.position_status is PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    assert unknown.new_entry_allowed is False
    assert unknown.close_planning_allowed is False
    assert "position_unknown_fail_closed" in unknown.blocked_reasons
    assert missing.position_status is PositionReadOnlyControlledStatus.SOURCE_MISSING_BLOCKED
    assert missing.position_status_checked is False
    assert missing.new_entry_allowed is False
    assert missing.close_planning_allowed is False
    assert "position_source_missing" in missing.blocked_reasons


def test_default_current_route_uses_connected_source_summary() -> None:
    result = build_position_read_only_controlled()

    assert result.position_status is PositionReadOnlyControlledStatus.NO_POSITION
    assert result.position_status_checked is True
    assert result.position_count_safe == 0
    assert result.new_entry_allowed is True
    assert result.close_planning_allowed is False
    assert "position_source_missing" not in result.blocked_reasons


def test_current_route_accepts_safe_connected_source_result() -> None:
    source = build_position_read_only_source_controlled(
        PositionReadOnlySourceControlledInput(position_count_safe=1),
    )

    result = build_position_read_only_controlled(source_result=source)

    assert result.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert result.position_count_safe == 1
    assert result.new_entry_allowed is False
    assert result.close_planning_allowed is True


def test_current_route_maps_source_unknown_and_exposure_fail_closed() -> None:
    unknown_source = build_position_read_only_source_controlled(
        PositionReadOnlySourceControlledInput(
            position_source_checked=False,
            position_status_unknown=True,
        ),
    )
    raw_source = build_position_read_only_source_controlled(
        PositionReadOnlySourceControlledInput(raw_response_exposure_attempted=True),
    )

    unknown = build_position_read_only_controlled(source_result=unknown_source)
    raw = build_position_read_only_controlled(source_result=raw_source)

    assert unknown.position_status is PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    assert unknown.new_entry_allowed is False
    assert unknown.close_planning_allowed is False
    assert raw.position_status is PositionReadOnlyControlledStatus.RAW_EXPOSURE_BLOCKED
    assert raw.raw_position_exposed is False
    assert raw.broker_api_response_exposed is False


def test_raw_id_value_and_credential_exposure_attempts_block_without_exposing() -> None:
    raw = build_position_read_only_controlled(
        PositionReadOnlyControlledInput(
            position_source_available=True,
            position_status_checked=True,
            position_status_unknown=False,
            raw_position_exposure_attempted=True,
        ),
    )
    ids = build_position_read_only_controlled(
        PositionReadOnlyControlledInput(
            position_source_available=True,
            position_status_checked=True,
            position_status_unknown=False,
            position_id_exposure_attempted=True,
            account_id_exposure_attempted=True,
            order_id_exposure_attempted=True,
            transaction_id_exposure_attempted=True,
        ),
    )
    values = build_position_read_only_controlled(
        PositionReadOnlyControlledInput(
            position_source_available=True,
            position_status_checked=True,
            position_status_unknown=False,
            actual_price_value_exposure_attempted=True,
            actual_pnl_value_exposure_attempted=True,
        ),
    )
    credential = build_position_read_only_controlled(
        PositionReadOnlyControlledInput(
            position_source_available=True,
            position_status_checked=True,
            position_status_unknown=False,
            credential_value_exposure_attempted=True,
            signature_value_exposure_attempted=True,
            headers_value_exposure_attempted=True,
        ),
    )

    assert raw.position_status is PositionReadOnlyControlledStatus.RAW_EXPOSURE_BLOCKED
    assert ids.position_status is PositionReadOnlyControlledStatus.ID_EXPOSURE_BLOCKED
    assert values.position_status is PositionReadOnlyControlledStatus.VALUE_EXPOSURE_BLOCKED
    assert (
        credential.position_status
        is PositionReadOnlyControlledStatus.CREDENTIAL_UNAVAILABLE_BLOCKED
    )
    for result in (raw, ids, values, credential):
        assert result.position_read_only_route_ready is False
        assert result.raw_position_exposed is False
        assert result.position_id_exposed is False
        assert result.account_id_exposed is False
        assert result.order_id_exposed is False
        assert result.transaction_id_exposed is False
        assert result.credential_value_exposed is False
        assert result.signature_value_exposed is False
        assert result.headers_value_exposed is False
        assert result.broker_api_response_exposed is False


def test_position_count_safe_only_and_no_hidden_ids_or_response_fields() -> None:
    result = build_position_read_only_controlled(_safe_source_input(1))
    data = asdict(result)

    assert data["position_count_safe"] == 1
    forbidden_fragments = ("pos-", "order-", "txn-", "acct-", "raw_payload")
    rendered = render_position_read_only_controlled_markdown(result)
    combined = repr(data) + rendered
    for fragment in forbidden_fragments:
        assert fragment not in combined
    assert "position_id_exposed: false" in rendered
    assert "broker/API responses" in rendered


def test_summary_never_executes_post_close_retry_ledger_or_receipt() -> None:
    result = build_position_read_only_controlled(_safe_source_input(1))
    rendered = render_position_read_only_controlled_markdown(result)

    assert result.actual_http_post_executed is False
    assert result.close_post_executed is False
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.receipt_handoff_executed is False
    assert "actual_http_post_executed: false" in rendered
    assert "close_post_executed: false" in rendered


def test_new_module_has_no_post_broker_env_or_private_api_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_position_read_only_controlled.py"
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
