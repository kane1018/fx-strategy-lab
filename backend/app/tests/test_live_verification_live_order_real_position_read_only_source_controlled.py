from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification.live_order_real_position_read_only_source_controlled import (
    PositionReadOnlySourceControlledInput,
    PositionReadOnlySourceControlledStatus,
    build_position_read_only_source_controlled,
    render_position_read_only_source_controlled_markdown,
)


def _safe_source_input(count: int) -> PositionReadOnlySourceControlledInput:
    return PositionReadOnlySourceControlledInput(
        position_source_checked=True,
        position_status_unknown=False,
        position_count_safe=count,
    )


def test_source_adapter_import_construction_and_summary_do_not_post() -> None:
    result = build_position_read_only_source_controlled()
    rendered = render_position_read_only_source_controlled_markdown(result)

    assert result.position_source_ready is True
    assert result.position_source_connected is True
    assert result.position_source_read_only is True
    assert result.position_source_checked is False
    assert result.position_status is PositionReadOnlySourceControlledStatus.UNKNOWN_FAIL_CLOSED
    assert result.actual_http_post_executed is False
    assert result.close_post_executed is False
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.receipt_handoff_executed is False
    assert "actual_http_post_executed: false" in rendered
    assert "close_post_executed: false" in rendered


def test_safe_fake_source_no_position_maps_to_entry_allowed_only() -> None:
    result = build_position_read_only_source_controlled(_safe_source_input(0))

    assert result.position_status is PositionReadOnlySourceControlledStatus.NO_POSITION
    assert result.position_count_safe == 0
    assert result.has_open_position is False
    assert result.new_entry_allowed is True
    assert result.close_planning_allowed is False
    assert result.close_execution_allowed_now is False


def test_safe_fake_source_one_position_maps_to_close_planning_only() -> None:
    result = build_position_read_only_source_controlled(_safe_source_input(1))

    assert result.position_status is PositionReadOnlySourceControlledStatus.ONE_POSITION_OPEN
    assert result.position_count_safe == 1
    assert result.has_open_position is True
    assert result.has_exactly_one_position is True
    assert result.new_entry_allowed is False
    assert result.close_planning_allowed is True
    assert result.close_execution_allowed_now is False


def test_safe_fake_source_multiple_positions_blocks_entry_and_close() -> None:
    result = build_position_read_only_source_controlled(_safe_source_input(2))

    assert (
        result.position_status
        is PositionReadOnlySourceControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    )
    assert result.position_count_safe == 2
    assert result.has_multiple_positions is True
    assert result.new_entry_allowed is False
    assert result.close_planning_allowed is False
    assert "multiple_positions_blocked" in result.blocked_reasons


def test_unknown_and_source_missing_fail_closed() -> None:
    unknown = build_position_read_only_source_controlled(
        PositionReadOnlySourceControlledInput(
            position_source_checked=False,
            position_status_unknown=True,
        ),
    )
    missing = build_position_read_only_source_controlled(
        PositionReadOnlySourceControlledInput(position_source_connected=False),
    )

    assert unknown.position_status is PositionReadOnlySourceControlledStatus.UNKNOWN_FAIL_CLOSED
    assert unknown.new_entry_allowed is False
    assert unknown.close_planning_allowed is False
    assert "position_unknown_fail_closed" in unknown.blocked_reasons
    assert missing.position_status is PositionReadOnlySourceControlledStatus.SOURCE_MISSING_BLOCKED
    assert missing.position_source_ready is False
    assert missing.new_entry_allowed is False
    assert missing.close_planning_allowed is False
    assert "position_source_missing" in missing.blocked_reasons


def test_exposure_sentinels_block_without_exposing_values() -> None:
    raw = build_position_read_only_source_controlled(
        PositionReadOnlySourceControlledInput(
            raw_response_exposure_attempted=True,
            raw_position_exposure_attempted=True,
            broker_api_response_exposure_attempted=True,
        ),
    )
    ids = build_position_read_only_source_controlled(
        PositionReadOnlySourceControlledInput(
            position_id_exposure_attempted=True,
            account_id_exposure_attempted=True,
            order_id_exposure_attempted=True,
            transaction_id_exposure_attempted=True,
        ),
    )
    credential = build_position_read_only_source_controlled(
        PositionReadOnlySourceControlledInput(
            credential_value_exposure_attempted=True,
            signature_value_exposure_attempted=True,
            headers_value_exposure_attempted=True,
        ),
    )

    assert raw.position_status is PositionReadOnlySourceControlledStatus.RAW_EXPOSURE_BLOCKED
    assert ids.position_status is PositionReadOnlySourceControlledStatus.ID_EXPOSURE_BLOCKED
    assert (
        credential.position_status
        is PositionReadOnlySourceControlledStatus.CREDENTIAL_UNAVAILABLE_BLOCKED
    )
    for result in (raw, ids, credential):
        assert result.raw_response_exposed is False
        assert result.raw_position_exposed is False
        assert result.broker_api_response_exposed is False
        assert result.position_id_exposed is False
        assert result.account_id_exposed is False
        assert result.order_id_exposed is False
        assert result.transaction_id_exposed is False
        assert result.credential_value_exposed is False
        assert result.signature_value_exposed is False
        assert result.headers_value_exposed is False
        assert result.handle_value_exposed is False


def test_position_count_safe_only_and_no_hidden_ids_or_response_fields() -> None:
    result = build_position_read_only_source_controlled(_safe_source_input(1))
    data = asdict(result)
    rendered = render_position_read_only_source_controlled_markdown(result)
    combined = repr(data) + rendered

    assert data["position_count_safe"] == 1
    for fragment in ("pos-", "order-", "txn-", "acct-", "raw_payload"):
        assert fragment not in combined
    assert "position_id_exposed: false" in rendered
    assert "broker_api_response_exposed: false" in rendered


def test_sealed_position_handle_is_not_created_or_exposed_in_this_step() -> None:
    result = build_position_read_only_source_controlled(_safe_source_input(1))

    assert result.sealed_position_handle_created is False
    assert result.handle_value_exposed is False


def test_source_module_has_no_post_broker_env_private_api_or_http_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_position_read_only_source_controlled.py"
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
