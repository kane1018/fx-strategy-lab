from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification.live_order_real_entry_unknown_no_position_closeout_gate_controlled import (  # noqa: E501
    ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT,
    NEXT_STEP_CLOSE_ORDER_EXECUTION_GATE,
    NEXT_STEP_LEVEL5_FRESH_CYCLE_ENTRY_GATE,
    PENDING_ORDER_SAFE_STATUS_SOURCE_MISSING,
    EntryUnknownNoPositionCloseoutCase,
    EntryUnknownNoPositionCloseoutGateInput,
    EntryUnknownNoPositionCloseoutStatus,
    ManualOperatorUiSafeCheckInput,
    build_entry_unknown_no_position_closeout_gate_controlled,
    render_entry_unknown_no_position_closeout_gate_markdown,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_position_runtime_safe_read_controlled import (
    PositionRuntimeSafeReadControlledInput,
    build_position_runtime_safe_read_controlled,
)
from app.live_verification.live_order_real_post_entry_position_confirmation_gate_controlled import (
    PreviousEntryPostSafeSummaryInput,
)


def _runtime(**overrides: object):
    defaults: dict[str, object] = {
        "credential_presence_checked": True,
        "credential_presence_available": True,
        "all_required_credentials_present": True,
        "runtime_read_executed": True,
        "runtime_read_succeeded": True,
        "position_count_safe": 0,
    }
    defaults.update(overrides)
    return build_position_runtime_safe_read_controlled(
        PositionRuntimeSafeReadControlledInput(**defaults),
    )


def test_previous_entry_count_one_and_runtime_no_position_closes_out_attempt() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        runtime_result=_runtime(),
    )

    assert result.case is EntryUnknownNoPositionCloseoutCase.CASE_1
    assert (
        result.closeout_status
        is EntryUnknownNoPositionCloseoutStatus.ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT
    )
    assert result.previous_entry_post_executed is True
    assert result.previous_entry_post_execution_count == 1
    assert result.runtime_position_status is PositionReadOnlyControlledStatus.NO_POSITION
    assert result.runtime_position_count_safe == 0
    assert result.entry_effect_confirmed_by_position is False
    assert result.entry_unknown_no_position is True
    assert result.entry_unknown_no_position_closeout_completed is True
    assert result.next_cycle_state == ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT
    assert result.fresh_cycle_may_be_planned is True
    assert result.actual_entry_post_allowed_now is False
    assert result.recommended_next_step == NEXT_STEP_LEVEL5_FRESH_CYCLE_ENTRY_GATE


def test_previous_retry_attempt_blocks_fresh_cycle_closeout() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        EntryUnknownNoPositionCloseoutGateInput(
            previous_entry_summary=PreviousEntryPostSafeSummaryInput(
                entry_retry_attempted=True,
            ),
        ),
        runtime_result=_runtime(),
    )

    assert result.case is EntryUnknownNoPositionCloseoutCase.CASE_4
    assert result.entry_unknown_no_position_closeout_completed is False
    assert result.fresh_cycle_may_be_planned is False
    assert "previous_entry_retry_attempted" in result.blocked_reasons


def test_previous_second_entry_attempt_blocks_fresh_cycle_closeout() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        EntryUnknownNoPositionCloseoutGateInput(
            previous_entry_summary=PreviousEntryPostSafeSummaryInput(
                entry_second_post_attempted=True,
            ),
        ),
        runtime_result=_runtime(),
    )

    assert result.entry_unknown_no_position_closeout_completed is False
    assert result.fresh_cycle_may_be_planned is False
    assert "previous_entry_second_post_attempted" in result.blocked_reasons


def test_previous_close_post_attempt_blocks_fresh_cycle_closeout() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        EntryUnknownNoPositionCloseoutGateInput(
            previous_entry_summary=PreviousEntryPostSafeSummaryInput(
                close_post_executed=True,
            ),
        ),
        runtime_result=_runtime(),
    )

    assert result.entry_unknown_no_position_closeout_completed is False
    assert result.fresh_cycle_may_be_planned is False
    assert "previous_close_post_executed" in result.blocked_reasons


def test_runtime_no_position_never_allows_retry_repost_second_or_close() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        runtime_result=_runtime(),
    )

    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_entry_allowed is False
    assert result.close_post_allowed_now is False
    assert result.ledger_update_allowed is False
    assert result.receipt_handoff_allowed is False
    assert result.actual_close_post_allowed_now is False


def test_runtime_one_position_routes_to_position_open_path_without_close_post() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.case is EntryUnknownNoPositionCloseoutCase.CASE_2
    assert (
        result.closeout_status
        is EntryUnknownNoPositionCloseoutStatus.POSITION_OPEN_FOUND_NO_CLOSE_POST
    )
    assert (
        result.runtime_position_status
        is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    )
    assert result.entry_effect_confirmed_by_position is True
    assert result.entry_unknown_no_position_closeout_completed is False
    assert result.close_post_allowed_now is False
    assert result.actual_close_post_allowed_now is False
    assert result.recommended_next_step == NEXT_STEP_CLOSE_ORDER_EXECUTION_GATE


def test_runtime_multiple_requires_manual_check_and_blocks_fresh_cycle() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        runtime_result=_runtime(position_count_safe=2),
    )

    assert result.case is EntryUnknownNoPositionCloseoutCase.CASE_3
    assert (
        result.runtime_position_status
        is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    )
    assert result.has_multiple_positions is True
    assert result.fresh_cycle_may_be_planned is False
    assert result.close_post_allowed_now is False


def test_runtime_unknown_fails_closed() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        runtime_result=_runtime(runtime_read_succeeded=False),
    )

    assert result.case is EntryUnknownNoPositionCloseoutCase.CASE_4
    assert (
        result.closeout_status
        is EntryUnknownNoPositionCloseoutStatus
        .UNKNOWN_FAIL_CLOSED_MANUAL_CHECK_REQUIRED
    )
    assert (
        result.runtime_position_status
        is PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    )
    assert result.fresh_cycle_may_be_planned is False
    assert result.actual_entry_post_allowed_now is False


def test_manual_ui_boolean_confirmation_has_no_value_or_id_fields() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        EntryUnknownNoPositionCloseoutGateInput(
            manual_ui_check=ManualOperatorUiSafeCheckInput(
                operator_broker_ui_checked=True,
                operator_broker_ui_open_position_visible=False,
                operator_broker_ui_pending_order_visible=False,
                operator_broker_ui_values_or_ids_provided=False,
            ),
        ),
        runtime_result=_runtime(),
    )
    blocked = build_entry_unknown_no_position_closeout_gate_controlled(
        EntryUnknownNoPositionCloseoutGateInput(
            manual_ui_check=ManualOperatorUiSafeCheckInput(
                operator_broker_ui_checked=True,
                operator_broker_ui_values_or_ids_provided=True,
            ),
        ),
        runtime_result=_runtime(),
    )

    assert result.manual_ui_confirmation_completed is True
    assert result.operator_broker_ui_values_or_ids_provided is False
    assert blocked.manual_ui_confirmation_completed is False
    assert blocked.fresh_cycle_may_be_planned is False
    assert "manual_ui_values_or_ids_provided" in blocked.blocked_reasons


def test_pending_order_source_missing_is_safe_and_non_blocking_for_no_position() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        runtime_result=_runtime(),
    )

    assert result.pending_order_safe_status == PENDING_ORDER_SAFE_STATUS_SOURCE_MISSING
    assert result.pending_order_check_required_for_fresh_cycle is False
    assert result.manual_ui_pending_order_check_recommended is True
    assert result.fresh_cycle_may_be_planned is True


def test_raw_id_value_and_credential_sentinels_block_without_exposure() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        EntryUnknownNoPositionCloseoutGateInput(
            raw_request_exposure_attempted_this_step=True,
            raw_response_exposure_attempted_this_step=True,
            broker_api_response_exposure_attempted_this_step=True,
            position_id_exposure_attempted_this_step=True,
            account_id_exposure_attempted_this_step=True,
            order_id_exposure_attempted_this_step=True,
            transaction_id_exposure_attempted_this_step=True,
            credential_value_exposure_attempted_this_step=True,
            signature_value_exposure_attempted_this_step=True,
            headers_value_exposure_attempted_this_step=True,
        ),
        runtime_result=_runtime(
            raw_response_exposure_attempted=True,
            raw_position_exposure_attempted=True,
            broker_api_response_exposure_attempted=True,
            position_id_exposure_attempted=True,
            account_id_exposure_attempted=True,
            order_id_exposure_attempted=True,
            transaction_id_exposure_attempted=True,
            credential_value_exposure_attempted=True,
            signature_value_exposure_attempted=True,
            headers_value_exposure_attempted=True,
        ),
    )
    rendered = render_entry_unknown_no_position_closeout_gate_markdown(result)
    dumped = repr(asdict(result)) + rendered

    assert result.raw_position_exposed is False
    assert result.raw_request_exposed is False
    assert result.raw_response_exposed is False
    assert result.position_id_exposed is False
    assert result.account_id_exposed is False
    assert result.order_id_exposed is False
    assert result.transaction_id_exposed is False
    assert result.broker_api_response_exposed is False
    assert result.credential_value_exposed is False
    assert result.signature_value_exposed is False
    assert result.headers_value_exposed is False
    assert result.fresh_cycle_may_be_planned is False
    for sentinel in ("raw_payload", "pos-", "acct-", "order-", "txn-", "secret"):
        assert sentinel not in dumped


def test_current_step_attempts_never_execute_post_close_ledger_or_receipt() -> None:
    result = build_entry_unknown_no_position_closeout_gate_controlled(
        EntryUnknownNoPositionCloseoutGateInput(
            actual_entry_post_attempted_this_step=True,
            entry_retry_attempted_this_step=True,
            entry_repost_attempted_this_step=True,
            second_entry_post_attempted_this_step=True,
            close_post_attempted_this_step=True,
            order_endpoint_called_this_step=True,
            live_order_once_called_this_step=True,
            ledger_update_attempted_this_step=True,
            receipt_handoff_attempted_this_step=True,
        ),
        runtime_result=_runtime(),
    )

    assert result.actual_entry_post_executed_this_step is False
    assert result.close_post_executed_this_step is False
    assert result.retry_or_repost_attempted_this_step is False
    assert result.second_entry_post_attempted_this_step is False
    assert result.ledger_updated_this_step is False
    assert result.receipt_handoff_executed_this_step is False
    assert result.fresh_cycle_may_be_planned is False
    assert "entry_post_attempted_this_step" in result.blocked_reasons
    assert "close_post_attempted_this_step" in result.blocked_reasons


def test_module_has_no_api_order_env_private_http_or_live_order_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_entry_unknown_no_position_closeout_gate_controlled.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "app.brokers",
        "httpx",
        "requests",
        "urllib",
        "urllib3",
        "socket",
        "subprocess",
        "dotenv",
        "os",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in blocked_modules
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module not in blocked_modules
