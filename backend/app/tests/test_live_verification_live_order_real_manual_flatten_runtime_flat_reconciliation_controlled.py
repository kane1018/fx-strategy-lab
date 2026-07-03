from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification import (
    live_order_real_manual_flatten_runtime_flat_reconciliation_controlled as gate,
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


def _operator_ready(
    **overrides: object,
) -> gate.OperatorManualFlattenSafeBooleanInput:
    values = {
        "operator_manual_flatten_completed": True,
        "operator_broker_ui_checked": True,
        "operator_broker_ui_open_position_visible": False,
        "operator_broker_ui_buy_position_visible": False,
        "operator_broker_ui_sell_position_visible": False,
        "operator_broker_ui_values_or_ids_provided": False,
        "operator_can_monitor": True,
    }
    values.update(overrides)
    return gate.OperatorManualFlattenSafeBooleanInput(**values)


def _gate_input(
    **overrides: object,
) -> gate.ManualFlattenRuntimeFlatReconciliationInput:
    values = {"operator": _operator_ready()}
    values.update(overrides)
    return gate.ManualFlattenRuntimeFlatReconciliationInput(**values)


def test_manual_flatten_booleans_and_runtime_no_position_reconcile_flat() -> None:
    result = gate.build_manual_flatten_runtime_flat_reconciliation_controlled(
        _runtime_result(0),
        _gate_input(),
    )
    rendered = gate.render_manual_flatten_runtime_flat_reconciliation_markdown(result)
    payload = repr(asdict(result))

    assert result.case is gate.ManualFlattenRuntimeFlatReconciliationCase.CASE_1
    assert (
        result.reconciliation_status
        is gate.ManualFlattenRuntimeFlatReconciliationStatus.MANUAL_FLATTEN_RECONCILED
    )
    assert result.position_status is PositionReadOnlyControlledStatus.NO_POSITION
    assert result.position_count_safe == 0
    assert result.manual_flatten_reconciled is True
    assert result.runtime_flat is True
    assert result.position_risk_remaining is False
    assert result.next_cycle_state == "MANUAL_FLATTEN_RECONCILED_FLAT"
    assert result.level5_minimal_cycle_completed is False
    assert result.level5_full_auto_cycle_completed is False
    assert result.fresh_cycle_allowed is False
    assert result.official_settlement_route_required is True
    assert result.generic_opposite_order_as_close_forbidden is True
    assert result.generic_close_primitive_revoked is True
    assert result.official_settlement_route_confirmed is False
    assert result.actual_entry_post_allowed_now is False
    assert result.actual_close_post_allowed_now is False
    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_close_allowed is False
    assert result.ledger_update_allowed is False
    assert result.receipt_handoff_allowed is False
    assert result.raw_response_exposed is False
    assert result.position_id_exposed is False
    assert result.credential_value_exposed is False
    assert "manual_flatten_reconciled: true" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_runtime_multiple_after_manual_flatten_keeps_position_risk_remaining() -> None:
    result = gate.build_manual_flatten_runtime_flat_reconciliation_controlled(
        _runtime_result(2),
        _gate_input(),
    )

    assert result.case is gate.ManualFlattenRuntimeFlatReconciliationCase.CASE_2
    assert (
        result.reconciliation_status
        is gate.ManualFlattenRuntimeFlatReconciliationStatus.POSITION_RISK_REMAINING
    )
    assert result.position_status is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    assert result.position_count_safe == 2
    assert result.manual_flatten_reconciled is False
    assert result.position_risk_remaining is True
    assert result.actual_close_post_allowed_now is False
    assert result.fresh_cycle_allowed is False


def test_runtime_one_position_after_manual_flatten_keeps_position_risk_remaining() -> None:
    result = gate.build_manual_flatten_runtime_flat_reconciliation_controlled(
        _runtime_result(1),
        _gate_input(),
    )

    assert result.case is gate.ManualFlattenRuntimeFlatReconciliationCase.CASE_2
    assert result.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert result.position_count_safe == 1
    assert result.manual_flatten_reconciled is False
    assert result.position_risk_remaining is True
    assert result.actual_close_post_allowed_now is False


def test_runtime_unknown_fails_closed_without_execution() -> None:
    result = gate.build_manual_flatten_runtime_flat_reconciliation_controlled(
        _runtime_result(0, succeeded=False),
        _gate_input(),
    )

    assert result.case is gate.ManualFlattenRuntimeFlatReconciliationCase.CASE_4
    assert (
        result.reconciliation_status
        is gate.ManualFlattenRuntimeFlatReconciliationStatus.UNKNOWN_FAIL_CLOSED
    )
    assert result.manual_flatten_reconciled is False
    assert result.actual_entry_post_allowed_now is False
    assert result.actual_close_post_allowed_now is False
    assert result.retry_allowed is False
    assert result.second_close_allowed is False


def test_runtime_flat_with_incomplete_operator_boolean_is_partial_case() -> None:
    result = gate.build_manual_flatten_runtime_flat_reconciliation_controlled(
        _runtime_result(0),
        _gate_input(
            operator=_operator_ready(operator_manual_flatten_completed=False),
        ),
    )

    assert result.case is gate.ManualFlattenRuntimeFlatReconciliationCase.CASE_3
    assert (
        result.reconciliation_status
        is gate.ManualFlattenRuntimeFlatReconciliationStatus
        .RUNTIME_FLAT_OPERATOR_CONFIRMATION_INCOMPLETE
    )
    assert result.runtime_flat is True
    assert result.manual_flatten_reconciled is False
    assert "operator_manual_flatten_not_completed" in result.blocked_reasons


def test_operator_values_or_ids_provided_blocks_reconciliation() -> None:
    result = gate.build_manual_flatten_runtime_flat_reconciliation_controlled(
        _runtime_result(0),
        _gate_input(
            operator=_operator_ready(operator_broker_ui_values_or_ids_provided=True),
        ),
    )

    assert result.case is gate.ManualFlattenRuntimeFlatReconciliationCase.CASE_4
    assert (
        result.reconciliation_status
        is gate.ManualFlattenRuntimeFlatReconciliationStatus.UNSAFE_EXPOSURE_BLOCKED
    )
    assert result.manual_flatten_reconciled is False
    assert result.raw_response_exposed is False
    assert result.position_id_exposed is False
    assert "operator_ui_values_or_ids_provided" in result.blocked_reasons


def test_current_step_execution_or_exposure_attempts_block_reconciliation() -> None:
    result = gate.build_manual_flatten_runtime_flat_reconciliation_controlled(
        _runtime_result(0),
        _gate_input(
            actual_close_post_attempted_this_step=True,
            close_retry_attempted_this_step=True,
            ledger_update_attempted_this_step=True,
            raw_response_exposure_attempted_this_step=True,
            transaction_id_exposure_attempted_this_step=True,
            credential_value_exposure_attempted_this_step=True,
        ),
    )

    assert result.case is gate.ManualFlattenRuntimeFlatReconciliationCase.CASE_4
    assert result.actual_close_post_executed_this_step is False
    assert result.close_retry_attempted is False
    assert result.ledger_updated is False
    assert result.raw_response_exposed is False
    assert result.transaction_id_exposed is False
    assert result.credential_value_exposed is False
    assert "close_post_attempted_this_step" in result.blocked_reasons
    assert "close_retry_attempted_this_step" in result.blocked_reasons
    assert "ledger_update_attempted_this_step" in result.blocked_reasons
    assert "current_step_raw_id_value_exposure_blocked" in result.blocked_reasons


def test_manual_flatten_reconciliation_module_has_no_api_order_env_or_http_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_manual_flatten_runtime_flat_reconciliation_controlled.py"
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
