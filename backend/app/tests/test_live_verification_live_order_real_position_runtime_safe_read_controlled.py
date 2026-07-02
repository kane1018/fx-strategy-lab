from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_position_runtime_safe_read_controlled import (
    POSITION_RUNTIME_READ_RECOMMENDED_NEXT_STEP_NO_POSITION,
    POSITION_RUNTIME_READ_RECOMMENDED_NEXT_STEP_ONE_POSITION,
    PositionRuntimeSafeReadControlledInput,
    build_position_runtime_safe_read_controlled,
    render_position_runtime_safe_read_controlled_markdown,
)
from app.live_verification.live_order_real_step6g_level5_fast_mvp_controlled import (
    Level5CycleState,
    Level5CycleTransitionInput,
    PositionReadOnlyStatus,
    build_level5_fast_mvp_foundation,
)


def _runtime_input(**overrides: object) -> PositionRuntimeSafeReadControlledInput:
    defaults: dict[str, object] = {
        "credential_presence_checked": True,
        "credential_presence_available": True,
        "all_required_credentials_present": True,
        "runtime_read_executed": True,
        "runtime_read_succeeded": True,
        "position_count_safe": 0,
    }
    defaults.update(overrides)
    return PositionRuntimeSafeReadControlledInput(**defaults)


def test_credential_missing_blocks_runtime_read() -> None:
    result = build_position_runtime_safe_read_controlled(
        PositionRuntimeSafeReadControlledInput(
            credential_presence_checked=True,
            credential_presence_available=False,
            all_required_credentials_present=False,
        ),
    )

    assert result.runtime_read_executed is False
    assert result.position_status_checked is False
    assert result.new_entry_allowed is False
    assert result.close_planning_allowed is False
    assert result.close_execution_allowed_now is False
    assert "credential_presence_unavailable" in result.blocked_reasons


def test_runtime_read_safe_no_position_maps_correctly() -> None:
    result = build_position_runtime_safe_read_controlled(_runtime_input())

    assert result.position_runtime_safe_read_ready is True
    assert result.position_status is PositionReadOnlyControlledStatus.NO_POSITION
    assert result.position_count_safe == 0
    assert result.has_open_position is False
    assert result.new_entry_allowed is True
    assert result.close_planning_allowed is False
    assert result.close_execution_allowed_now is False
    assert result.recommended_next_step == POSITION_RUNTIME_READ_RECOMMENDED_NEXT_STEP_NO_POSITION


def test_runtime_read_safe_one_position_maps_correctly() -> None:
    result = build_position_runtime_safe_read_controlled(
        _runtime_input(position_count_safe=1),
    )

    assert result.position_runtime_safe_read_ready is True
    assert result.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert result.position_count_safe == 1
    assert result.has_exactly_one_position is True
    assert result.new_entry_allowed is False
    assert result.close_planning_allowed is True
    assert result.close_execution_allowed_now is False
    assert result.recommended_next_step == POSITION_RUNTIME_READ_RECOMMENDED_NEXT_STEP_ONE_POSITION


def test_runtime_read_safe_multiple_maps_blocked() -> None:
    result = build_position_runtime_safe_read_controlled(
        _runtime_input(position_count_safe=2),
    )

    assert result.position_status is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    assert result.position_count_safe == 2
    assert result.has_multiple_positions is True
    assert result.new_entry_allowed is False
    assert result.close_planning_allowed is False
    assert "multiple_positions_blocked" in result.blocked_reasons


def test_runtime_read_unknown_maps_fail_closed() -> None:
    result = build_position_runtime_safe_read_controlled(
        _runtime_input(runtime_read_succeeded=False),
    )

    assert result.position_runtime_safe_read_ready is False
    assert result.position_status is PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    assert result.position_status_checked is False
    assert result.new_entry_allowed is False
    assert result.close_planning_allowed is False
    assert "runtime_read_unknown_fail_closed" in result.blocked_reasons


def test_raw_id_value_and_credential_sentinels_block_without_exposure() -> None:
    result = build_position_runtime_safe_read_controlled(
        _runtime_input(
            raw_response_exposure_attempted=True,
            raw_position_exposure_attempted=True,
            broker_api_response_exposure_attempted=True,
            position_id_exposure_attempted=True,
            account_id_exposure_attempted=True,
            order_id_exposure_attempted=True,
            transaction_id_exposure_attempted=True,
            actual_price_value_exposure_attempted=True,
            actual_pnl_value_exposure_attempted=True,
            credential_value_exposure_attempted=True,
            signature_value_exposure_attempted=True,
            headers_value_exposure_attempted=True,
        ),
    )
    rendered = render_position_runtime_safe_read_controlled_markdown(result)
    dumped = repr(asdict(result)) + rendered

    assert result.position_runtime_safe_read_ready is False
    assert result.raw_position_exposed is False
    assert result.position_id_exposed is False
    assert result.account_id_exposed is False
    assert result.order_id_exposed is False
    assert result.transaction_id_exposed is False
    assert result.broker_api_response_exposed is False
    assert result.credential_value_exposed is False
    assert result.signature_value_exposed is False
    assert result.headers_value_exposed is False
    for sentinel in ("raw_payload", "pos-", "acct-", "order-", "txn-", "secret"):
        assert sentinel not in dumped


def test_level5_uses_runtime_no_position_correctly() -> None:
    runtime = build_position_runtime_safe_read_controlled(_runtime_input())
    result = build_level5_fast_mvp_foundation(
        position_controlled_result=runtime.position_route,
    )

    assert result.position_status.position_status is PositionReadOnlyStatus.NO_POSITION
    assert result.position_status.new_entry_allowed is True
    assert result.close_order_route.close_planning_allowed is False


def test_level5_uses_runtime_one_position_for_close_ready_without_post() -> None:
    runtime = build_position_runtime_safe_read_controlled(
        _runtime_input(position_count_safe=1),
    )
    result = build_level5_fast_mvp_foundation(
        position_controlled_result=runtime.position_route,
        cycle_input=Level5CycleTransitionInput(
            current_state=Level5CycleState.EXIT_SIGNAL,
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
        ),
    )

    assert result.position_status.new_entry_allowed is False
    assert result.close_order_route.close_planning_allowed is True
    assert result.close_order_route.close_execution_allowed_now is False
    assert result.cycle_transition.next_state is Level5CycleState.CLOSE_READY
    assert result.close_post_executed is False


def test_runtime_read_never_executes_post_retry_ledger_or_receipt() -> None:
    result = build_position_runtime_safe_read_controlled(
        _runtime_input(
            actual_http_post_attempted=True,
            close_post_attempted=True,
            retry_or_repost_attempted=True,
            ledger_update_attempted=True,
            receipt_handoff_attempted=True,
        ),
    )

    assert result.actual_http_post_executed is False
    assert result.close_post_executed is False
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.receipt_handoff_executed is False
    assert result.close_execution_allowed_now is False


def test_runtime_safe_read_module_has_no_api_order_env_private_or_http_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_position_runtime_safe_read_controlled.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "app.brokers",
        "app.private_api",
        "backend.scripts",
        "scripts",
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
        "environ",
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
