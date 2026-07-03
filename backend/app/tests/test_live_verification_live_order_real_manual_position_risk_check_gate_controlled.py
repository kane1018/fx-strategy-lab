from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification.live_order_real_close_actual_executor_compatibility_controlled import (
    build_close_actual_executor_compatibility_controlled,
)
from app.live_verification.live_order_real_close_order_execution_route_controlled import (
    APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC,
    OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED,
    CloseOrderExecutionRouteControlledInput,
    build_close_order_execution_route_controlled,
)
from app.live_verification.live_order_real_manual_position_risk_check_gate_controlled import (
    ManualPositionRiskCheckGateCase,
    ManualPositionRiskCheckGateInput,
    ManualPositionRiskStatus,
    OperatorUiSafeBooleanInput,
    build_manual_position_risk_check_gate_controlled,
    render_manual_position_risk_check_gate_markdown,
)
from app.live_verification.live_order_real_one_shot_post_execution_controlled import (
    LiveOrderRealExecutableOrderPreviewInput,
    build_live_order_real_executable_order_preview,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_position_runtime_safe_read_controlled import (
    PositionRuntimeSafeReadControlledInput,
    build_position_runtime_safe_read_controlled,
)

RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
POSITION_ID_SENTINEL = "POSITION_ID_SHOULD_NOT_SURFACE"
ACCOUNT_ID_SENTINEL = "ACCOUNT_ID_SHOULD_NOT_SURFACE"
ORDER_ID_SENTINEL = "ORDER_ID_SHOULD_NOT_SURFACE"
TRANSACTION_ID_SENTINEL = "TRANSACTION_ID_SHOULD_NOT_SURFACE"
CREDENTIAL_VALUE_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"

_FORBIDDEN_SENTINELS = (
    RAW_RESPONSE_SENTINEL,
    POSITION_ID_SENTINEL,
    ACCOUNT_ID_SENTINEL,
    ORDER_ID_SENTINEL,
    TRANSACTION_ID_SENTINEL,
    CREDENTIAL_VALUE_SENTINEL,
    SIGNATURE_VALUE_SENTINEL,
    HEADERS_VALUE_SENTINEL,
)


def _runtime_result(count: int, *, succeeded: bool = True):
    return build_position_runtime_safe_read_controlled(
        PositionRuntimeSafeReadControlledInput(
            credential_presence_checked=True,
            credential_presence_available=True,
            all_required_credentials_present=True,
            runtime_read_requested=True,
            runtime_read_executed=True,
            runtime_read_succeeded=succeeded,
            position_count_safe=count,
        ),
    )


def _gate_input(**overrides: object) -> ManualPositionRiskCheckGateInput:
    values = {
        "operator_ui": OperatorUiSafeBooleanInput(
            operator_broker_ui_checked=True,
            operator_broker_ui_buy_position_visible=True,
            operator_broker_ui_sell_position_visible=True,
            operator_broker_ui_multiple_positions_visible=True,
            operator_broker_ui_values_or_ids_provided=False,
            operator_can_monitor=True,
        ),
    }
    values.update(overrides)
    return ManualPositionRiskCheckGateInput(**values)


def _generic_route_result():
    return build_close_order_execution_route_controlled(
        CloseOrderExecutionRouteControlledInput(
            runtime_position_status=PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
            position_count_safe=1,
            has_exactly_one_position=True,
            has_multiple_positions=False,
            close_route_ready=True,
            close_planning_allowed=True,
            fresh_entry_side_safe_label="BUY",
            approved_close_post_primitive_kind=(
                APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC
            ),
            approved_close_post_primitive_is_generic_order=True,
            generic_order_accepted_as_close_only_with_exact_one_position_guard=True,
        ),
    )


def test_multiple_positions_count_two_confirms_manual_risk_and_blocks_cycle() -> None:
    result = build_manual_position_risk_check_gate_controlled(
        _runtime_result(2),
        _gate_input(),
    )
    rendered = render_manual_position_risk_check_gate_markdown(result)
    payload = repr(asdict(result))

    assert result.case is ManualPositionRiskCheckGateCase.CASE_1
    assert (
        result.manual_position_risk_status
        is ManualPositionRiskStatus.MULTIPLE_POSITIONS_CONFIRMED
    )
    assert result.position_status is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    assert result.position_count_safe == 2
    assert result.multiple_positions_confirmed is True
    assert result.suspected_hedged_positions is True
    assert result.level5_minimal_cycle_completed is False
    assert result.level5_full_auto_cycle_completed is False
    assert result.close_effect_confirmed_by_no_position is False
    assert result.actual_entry_post_allowed_now is False
    assert result.actual_close_post_allowed_now is False
    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_close_allowed is False
    assert result.ledger_update_allowed is False
    assert result.receipt_handoff_allowed is False
    assert result.manual_operator_flatten_recommended is True
    assert result.official_settlement_route_required is True
    assert result.fresh_cycle_allowed is False
    assert result.close_execution_blocked_reason == OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED
    assert "multiple_positions_confirmed: true" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_no_position_count_zero_uses_already_flat_reconciliation_path() -> None:
    result = build_manual_position_risk_check_gate_controlled(
        _runtime_result(0),
        _gate_input(
            operator_ui=OperatorUiSafeBooleanInput(
                operator_broker_ui_checked=True,
                operator_broker_ui_multiple_positions_visible=False,
                operator_broker_ui_values_or_ids_provided=False,
                operator_can_monitor=True,
            ),
        ),
    )

    assert result.case is ManualPositionRiskCheckGateCase.CASE_2
    assert result.manual_position_risk_status is ManualPositionRiskStatus.ALREADY_FLAT
    assert result.position_status is PositionReadOnlyControlledStatus.NO_POSITION
    assert result.position_count_safe == 0
    assert result.multiple_positions_confirmed is False
    assert result.manual_operator_flatten_recommended is False
    assert result.fresh_cycle_allowed is False
    assert result.actual_close_post_allowed_now is False


def test_single_position_still_open_keeps_close_post_forbidden() -> None:
    result = build_manual_position_risk_check_gate_controlled(
        _runtime_result(1),
        _gate_input(
            operator_ui=OperatorUiSafeBooleanInput(
                operator_broker_ui_checked=True,
                operator_broker_ui_buy_position_visible=True,
                operator_broker_ui_values_or_ids_provided=False,
                operator_can_monitor=True,
            ),
        ),
    )

    assert result.case is ManualPositionRiskCheckGateCase.CASE_3
    assert (
        result.manual_position_risk_status
        is ManualPositionRiskStatus.SINGLE_POSITION_STILL_OPEN
    )
    assert result.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert result.position_count_safe == 1
    assert result.actual_close_post_allowed_now is False
    assert result.close_execution_blocked_reason == OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED


def test_unknown_position_fails_closed_without_execution() -> None:
    result = build_manual_position_risk_check_gate_controlled(
        _runtime_result(0, succeeded=False),
        _gate_input(),
    )

    assert result.case is ManualPositionRiskCheckGateCase.CASE_4
    assert result.manual_position_risk_status is ManualPositionRiskStatus.UNKNOWN_FAIL_CLOSED
    assert result.actual_entry_post_allowed_now is False
    assert result.actual_close_post_allowed_now is False
    assert result.retry_allowed is False
    assert result.second_close_allowed is False


def test_current_step_execution_or_exposure_attempts_block_manual_gate() -> None:
    result = build_manual_position_risk_check_gate_controlled(
        _runtime_result(2),
        _gate_input(
            actual_close_post_attempted_this_step=True,
            close_retry_attempted_this_step=True,
            raw_response_exposure_attempted_this_step=True,
            position_id_exposure_attempted_this_step=True,
            credential_value_exposure_attempted_this_step=True,
        ),
    )

    assert result.case is ManualPositionRiskCheckGateCase.CASE_4
    assert (
        result.manual_position_risk_status
        is ManualPositionRiskStatus.UNSAFE_EXPOSURE_BLOCKED
    )
    assert result.actual_close_post_executed_this_step is False
    assert result.close_retry_attempted is False
    assert result.raw_response_exposed is False
    assert result.position_id_exposed is False
    assert result.credential_value_exposed is False
    assert "close_post_attempted_this_step" in result.blocked_reasons
    assert "close_retry_attempted_this_step" in result.blocked_reasons
    assert "current_step_raw_id_value_exposure_blocked" in result.blocked_reasons


def test_generic_opposite_order_as_close_is_forbidden_and_revoked() -> None:
    route = _generic_route_result()
    compatibility = build_close_actual_executor_compatibility_controlled(
        close_execution_route_result=route,
    )

    assert route.close_execution_route_ready is False
    assert route.close_executable_preview_ready is False
    assert route.generic_opposite_order_as_close_forbidden is True
    assert route.generic_close_primitive_revoked is True
    assert route.official_settlement_route_confirmed is False
    assert route.actual_close_post_allowed_now is False
    assert route.close_execution_blocked_reason == OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED
    assert compatibility.close_actual_executor_compatibility_ready is False
    assert compatibility.close_specific_executor_preview_ready is False
    assert compatibility.close_specific_sell_accepted is False
    assert compatibility.actual_close_post_allowed_now is False
    assert compatibility.actual_close_post_executed is False
    assert compatibility.transport_call_count == 0
    assert "generic_close_primitive_revoked" in route.blocked_reasons
    assert "official_settlement_route_not_confirmed" in route.blocked_reasons


def test_generic_entry_buy_guard_remains_intact_and_generic_sell_blocks() -> None:
    buy_preview = build_live_order_real_executable_order_preview()
    sell_preview = build_live_order_real_executable_order_preview(
        LiveOrderRealExecutableOrderPreviewInput(side="SELL"),
    )

    assert buy_preview.sanitized_order_preview_available is True
    assert buy_preview.side == "BUY"
    assert sell_preview.sanitized_order_preview_available is False
    assert sell_preview.order_ambiguity is True
    assert "side_not_repo_defined_buy" in sell_preview.blocked_reasons


def test_manual_position_risk_module_has_no_api_order_env_or_http_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_manual_position_risk_check_gate_controlled.py"
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
