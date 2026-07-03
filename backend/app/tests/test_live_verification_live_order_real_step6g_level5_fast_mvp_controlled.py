from __future__ import annotations

import ast
from pathlib import Path

from app.live_verification.live_order_real_close_order_execution_route_controlled import (
    APPROVED_CLOSE_PRIMITIVE_KIND_CLOSE_SPECIFIC,
    APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC,
    NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ROUTE_MISSING,
    NEXT_CYCLE_STATE_READY,
    NEXT_CYCLE_STATE_SIDE_UNRESOLVED,
    CloseOrderExecutionRouteControlledInput,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledInput,
    PositionReadOnlyControlledStatus,
    build_position_read_only_controlled,
)
from app.live_verification.live_order_real_step6g_level5_fast_mvp_controlled import (
    CloseRouteFoundationInput,
    CloseRouteFoundationStatus,
    Level5CycleState,
    Level5CycleTransitionInput,
    Level5EntryPlanningGateInput,
    Level5ExitReasonLabel,
    Level5FastTrackConfigInput,
    Level5SignalMvpInput,
    Level5SignalSource,
    Level5SignalType,
    Level5SpreadLabel,
    Level5TimeMarketLabel,
    Level5TrendLabel,
    Level5VolatilityLabel,
    PositionReadOnlyStatus,
    PositionReadOnlyStatusInput,
    ReviewOnlyReceiptSummaryInput,
    SafeLedgerLikeRecordInput,
    build_close_route_foundation,
    build_level5_entry_planning_gate,
    build_level5_fast_mvp_foundation,
    build_level5_fast_track_config,
    build_position_read_only_status,
    build_review_only_receipt_summary,
    build_safe_ledger_like_record,
    evaluate_level5_signal_mvp,
    render_level5_fast_mvp_foundation_markdown,
    transition_level5_cycle_state,
)


def test_safe_ledger_like_record_accepts_sanitized_accepted_result() -> None:
    result = build_safe_ledger_like_record()

    assert result.safe_record_ready is True
    assert result.post_execution_count == 1
    assert result.sanitized_result_category == "RESULT_ACCEPTED_SANITIZED"
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.production_ledger_written is False
    assert result.raw_id_value_exposure is False
    assert result.credential_signature_headers_exposure is False


def test_safe_ledger_like_record_blocks_retry_or_second_post() -> None:
    retry_result = build_safe_ledger_like_record(
        SafeLedgerLikeRecordInput(retry_attempted=True),
    )
    second_result = build_safe_ledger_like_record(
        SafeLedgerLikeRecordInput(second_post_attempted=True),
    )

    assert retry_result.safe_record_ready is False
    assert "retry_attempted" in retry_result.blocked_reasons
    assert second_result.safe_record_ready is False
    assert "second_post_attempted" in second_result.blocked_reasons


def test_safe_ledger_like_record_blocks_raw_or_value_exposure() -> None:
    result = build_safe_ledger_like_record(
        SafeLedgerLikeRecordInput(raw_response_exposed=True, headers_value_exposed=True),
    )

    assert result.safe_record_ready is False
    assert result.raw_id_value_exposure is True
    assert result.credential_signature_headers_exposure is True


def test_review_only_receipt_summary_is_ready_without_actual_handoff() -> None:
    result = build_review_only_receipt_summary()

    assert result.receipt_summary_ready is True
    assert result.actual_receipt_handoff_executed is False
    assert result.raw_response_required is False
    assert result.real_id_required is False
    assert result.manual_broker_ui_check_recommended is True


def test_review_only_receipt_summary_blocks_real_receipt_requirements() -> None:
    result = build_review_only_receipt_summary(
        ReviewOnlyReceiptSummaryInput(raw_response_required=True, real_id_required=True),
    )

    assert result.receipt_summary_ready is False
    assert "raw_response_required" in result.blocked_reasons
    assert "real_id_required" in result.blocked_reasons


def test_position_status_blocks_new_entry_when_unknown() -> None:
    result = build_position_read_only_status()

    assert result.position_status_checked is False
    assert result.position_status is PositionReadOnlyStatus.UNKNOWN
    assert result.new_entry_allowed is False
    assert result.close_allowed is False


def test_position_status_allows_entry_only_when_no_position() -> None:
    result = build_position_read_only_status(
        PositionReadOnlyStatusInput(
            position_status_checked=True,
            position_status_unknown=False,
            position_source_available=True,
            open_position_count=0,
        ),
    )

    assert result.position_status is PositionReadOnlyStatus.NO_POSITION
    assert result.new_entry_allowed is True
    assert result.close_allowed is False


def test_position_status_allows_close_only_with_one_position() -> None:
    result = build_position_read_only_status(
        PositionReadOnlyStatusInput(
            position_status_checked=True,
            position_status_unknown=False,
            position_source_available=True,
            open_position_count=1,
        ),
    )

    assert result.position_status is PositionReadOnlyStatus.ONE_POSITION_OPEN
    assert result.new_entry_allowed is False
    assert result.close_allowed is True
    assert result.raw_position_id_exposed is False


def test_position_status_blocks_multiple_positions() -> None:
    result = build_position_read_only_status(
        PositionReadOnlyStatusInput(
            position_status_checked=True,
            position_status_unknown=False,
            position_source_available=True,
            open_position_count=2,
        ),
    )

    assert result.position_status is PositionReadOnlyStatus.BLOCKED
    assert result.new_entry_allowed is False
    assert result.close_allowed is False
    assert "multiple_positions_blocked" in result.blocked_reasons


def test_close_route_foundation_never_executes_post_when_ready() -> None:
    result = build_close_route_foundation(
        CloseRouteFoundationInput(position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN),
    )

    assert result.status is CloseRouteFoundationStatus.READY
    assert result.close_route_ready is True
    assert result.close_post_executed is False
    assert result.close_post_count == 0
    assert result.close_retry_allowed is False
    assert result.close_second_post_allowed is False
    assert result.close_size_fixed == 100


def test_close_route_blocks_no_position_unknown_and_multiple_position_status() -> None:
    no_position = build_close_route_foundation(
        CloseRouteFoundationInput(position_status=PositionReadOnlyStatus.NO_POSITION),
    )
    unknown = build_close_route_foundation()
    blocked = build_close_route_foundation(
        CloseRouteFoundationInput(position_status=PositionReadOnlyStatus.BLOCKED),
    )

    assert no_position.close_route_ready is False
    assert "no_position" in no_position.blocked_reasons
    assert unknown.close_route_ready is False
    assert "position_unknown" in unknown.blocked_reasons
    assert blocked.close_route_ready is False
    assert "position_blocked_or_multiple" in blocked.blocked_reasons


def test_close_route_blocks_raw_id_or_close_post_attempts() -> None:
    result = build_close_route_foundation(
        CloseRouteFoundationInput(
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
            close_post_executed=True,
            close_post_count=1,
            raw_id_required=True,
        ),
    )

    assert result.close_route_ready is False
    assert result.close_post_executed is False
    assert result.close_post_count == 0
    assert "close_post_attempted" in result.blocked_reasons
    assert "raw_id_required" in result.blocked_reasons


def test_cycle_state_machine_entry_to_position_check_path() -> None:
    entry = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.IDLE,
            entry_signal=True,
            position_status=PositionReadOnlyStatus.NO_POSITION,
        ),
    )
    sent = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.ENTRY_SIGNAL,
            entry_execution_gate_passed=True,
        ),
    )
    accepted = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.ENTRY_SENT,
            entry_accepted_sanitized=True,
        ),
    )
    pending = transition_level5_cycle_state(
        Level5CycleTransitionInput(current_state=Level5CycleState.ENTRY_ACCEPTED_SANITIZED),
    )

    assert entry.next_state is Level5CycleState.ENTRY_READY
    assert sent.next_state is Level5CycleState.ENTRY_SENT
    assert accepted.next_state is Level5CycleState.ENTRY_ACCEPTED_SANITIZED
    assert pending.next_state is Level5CycleState.POSITION_CHECK_PENDING


def test_cycle_state_machine_position_check_halts_on_unknown() -> None:
    result = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.POSITION_CHECK_PENDING,
            position_status=PositionReadOnlyStatus.UNKNOWN,
        ),
    )

    assert result.next_state is Level5CycleState.HALTED
    assert result.halted is True
    assert result.automatic_recovery_allowed is False


def test_cycle_state_machine_closes_out_unknown_result_no_position() -> None:
    result = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.UNKNOWN_RESULT_SAFE_STOP,
            position_status=PositionReadOnlyStatus.NO_POSITION,
            entry_unknown_no_position_closeout_confirmed=True,
        ),
    )
    blocked = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.UNKNOWN_RESULT_SAFE_STOP,
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
            entry_unknown_no_position_closeout_confirmed=True,
        ),
    )

    assert result.next_state is Level5CycleState.ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT
    assert result.retry_allowed is False
    assert result.second_post_allowed is False
    assert result.automatic_recovery_allowed is False
    assert blocked.next_state is Level5CycleState.HALTED
    assert "closeout_requires_no_position" in blocked.blocked_reasons


def test_cycle_state_machine_prevents_second_entry() -> None:
    result = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.POSITION_OPEN_SAFE,
            entry_signal=True,
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
        ),
    )

    assert result.next_state is Level5CycleState.HALTED
    assert result.retry_allowed is False
    assert result.second_post_allowed is False
    assert "second_entry_blocked" in result.blocked_reasons


def test_cycle_state_machine_exit_to_close_and_closed_safe() -> None:
    exit_signal = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.POSITION_OPEN_SAFE,
            exit_signal=True,
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
        ),
    )
    ready = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.EXIT_SIGNAL,
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
        ),
    )
    sent = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.CLOSE_READY,
            close_execution_gate_passed=True,
        ),
    )
    closed = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.CLOSE_SENT,
            close_accepted_sanitized=True,
            no_position_after_close=True,
        ),
    )

    assert exit_signal.next_state is Level5CycleState.EXIT_SIGNAL
    assert ready.next_state is Level5CycleState.CLOSE_READY
    assert sent.next_state is Level5CycleState.CLOSE_SENT
    assert closed.next_state is Level5CycleState.CLOSED_SAFE


def test_signal_mvp_emits_hold_by_default() -> None:
    result = evaluate_level5_signal_mvp()

    assert result.signal_checked is True
    assert result.signal_type is Level5SignalType.HOLD
    assert result.signal_source is Level5SignalSource.RULE_MVP
    assert result.actual_market_raw_value_exposed is False
    assert result.actual_market_value_exposed is False
    assert result.raw_market_data_exposed is False
    assert result.signal_direct_post_attempted is False
    assert result.signal_directly_executes_post is False


def test_signal_mvp_emits_entry_only_when_no_position() -> None:
    result = evaluate_level5_signal_mvp(
        Level5SignalMvpInput(
            trend_label=Level5TrendLabel.UPTREND,
            position_status=PositionReadOnlyStatus.NO_POSITION,
        ),
    )
    blocked = evaluate_level5_signal_mvp(
        Level5SignalMvpInput(
            trend_label=Level5TrendLabel.UPTREND,
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
        ),
    )

    assert result.signal_type is Level5SignalType.ENTRY_BUY
    assert blocked.signal_type is Level5SignalType.BLOCKED
    assert "entry_requires_no_position" in blocked.blocked_reasons


def test_signal_entry_gate_buy_planning_ready_from_safe_snapshot() -> None:
    signal = evaluate_level5_signal_mvp(
        Level5SignalMvpInput(
            trend_label=Level5TrendLabel.UPTREND,
            spread_label=Level5SpreadLabel.NORMAL,
            time_market_label=Level5TimeMarketLabel.OK,
            volatility_label=Level5VolatilityLabel.NORMAL,
            position_status=PositionReadOnlyStatus.NO_POSITION,
            signal_source=Level5SignalSource.SAFE_SNAPSHOT,
        ),
    )
    planning = build_level5_entry_planning_gate(
        Level5EntryPlanningGateInput(
            position_status=PositionReadOnlyStatus.NO_POSITION,
            signal_checked=signal.signal_checked,
            signal_type=signal.signal_type,
        ),
    )

    assert signal.signal_type is Level5SignalType.ENTRY_BUY
    assert signal.signal_confidence_label.name == "LOW"
    assert signal.signal_reason_label == "rule_mvp_uptrend_normal_ok"
    assert signal.actual_market_value_exposed is False
    assert signal.raw_market_data_exposed is False
    assert signal.signal_directly_executes_post is False
    assert planning.entry_planning_gate_ready is True
    assert planning.entry_planning_allowed is True
    assert planning.entry_execution_allowed_now is False
    assert planning.entry_execution_step_may_be_planned is True
    assert planning.entry_units_fixed == 100
    assert planning.entry_symbol_safe_label == "USD_JPY"
    assert planning.entry_order_type_safe_label == "MARKET"
    assert planning.entry_side_safe_label == "BUY"
    assert planning.entry_retry_allowed is False
    assert planning.entry_second_post_allowed is False
    assert planning.entry_raw_exposure is False
    assert planning.entry_id_exposure is False
    assert planning.actual_http_post_executed is False
    assert planning.close_post_executed is False


def test_signal_entry_gate_sell_planning_ready_from_safe_snapshot() -> None:
    signal = evaluate_level5_signal_mvp(
        Level5SignalMvpInput(
            trend_label=Level5TrendLabel.DOWNTREND,
            spread_label=Level5SpreadLabel.NORMAL,
            time_market_label=Level5TimeMarketLabel.OK,
            position_status=PositionReadOnlyStatus.NO_POSITION,
            signal_source=Level5SignalSource.SAFE_SNAPSHOT,
        ),
    )
    planning = build_level5_entry_planning_gate(
        Level5EntryPlanningGateInput(
            position_status=PositionReadOnlyStatus.NO_POSITION,
            signal_checked=signal.signal_checked,
            signal_type=signal.signal_type,
        ),
    )

    assert signal.signal_type is Level5SignalType.ENTRY_SELL
    assert signal.signal_reason_label == "rule_mvp_downtrend_normal_ok"
    assert planning.entry_planning_allowed is True
    assert planning.entry_side_safe_label == "SELL"
    assert planning.entry_execution_allowed_now is False


def test_signal_entry_gate_hold_and_market_blocks_do_not_plan_entry() -> None:
    hold_signal = evaluate_level5_signal_mvp(
        Level5SignalMvpInput(
            trend_label=Level5TrendLabel.FLAT,
            position_status=PositionReadOnlyStatus.NO_POSITION,
        ),
    )
    wide_signal = evaluate_level5_signal_mvp(
        Level5SignalMvpInput(
            trend_label=Level5TrendLabel.UPTREND,
            spread_label=Level5SpreadLabel.WIDE,
            position_status=PositionReadOnlyStatus.NO_POSITION,
        ),
    )
    unknown_market_signal = evaluate_level5_signal_mvp(
        Level5SignalMvpInput(
            trend_label=Level5TrendLabel.UNKNOWN,
            time_market_label=Level5TimeMarketLabel.UNKNOWN,
            position_status=PositionReadOnlyStatus.NO_POSITION,
        ),
    )
    hold_planning = build_level5_entry_planning_gate(
        Level5EntryPlanningGateInput(
            position_status=PositionReadOnlyStatus.NO_POSITION,
            signal_checked=hold_signal.signal_checked,
            signal_type=hold_signal.signal_type,
        ),
    )

    assert hold_signal.signal_type is Level5SignalType.HOLD
    assert hold_planning.entry_planning_allowed is False
    assert "entry_signal_required" in hold_planning.blocked_reasons
    assert wide_signal.signal_type is Level5SignalType.BLOCKED
    assert "spread_not_normal" in wide_signal.blocked_reasons
    assert unknown_market_signal.signal_type is Level5SignalType.BLOCKED
    assert "trend_unknown" in unknown_market_signal.blocked_reasons
    assert "time_market_not_ok" in unknown_market_signal.blocked_reasons


def test_entry_planning_blocks_non_no_position_and_exposure_attempts() -> None:
    one_position = build_level5_entry_planning_gate(
        Level5EntryPlanningGateInput(
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
            signal_checked=True,
            signal_type=Level5SignalType.ENTRY_BUY,
        ),
    )
    unknown_position = build_level5_entry_planning_gate(
        Level5EntryPlanningGateInput(
            position_status=PositionReadOnlyStatus.UNKNOWN,
            signal_checked=True,
            signal_type=Level5SignalType.ENTRY_BUY,
        ),
    )
    multiple_position = build_level5_entry_planning_gate(
        Level5EntryPlanningGateInput(
            position_status=PositionReadOnlyStatus.BLOCKED,
            signal_checked=True,
            signal_type=Level5SignalType.ENTRY_BUY,
        ),
    )
    unsafe = build_level5_entry_planning_gate(
        Level5EntryPlanningGateInput(
            position_status=PositionReadOnlyStatus.NO_POSITION,
            signal_checked=True,
            signal_type=Level5SignalType.ENTRY_BUY,
            raw_exposure_attempted=True,
            id_exposure_attempted=True,
            credential_signature_headers_exposure_attempted=True,
            retry_or_repost_attempted=True,
            second_post_attempted=True,
        ),
    )

    for result in (one_position, unknown_position, multiple_position):
        assert result.entry_planning_allowed is False
        assert "entry_requires_no_position" in result.blocked_reasons
    assert unsafe.entry_planning_allowed is False
    assert unsafe.entry_execution_allowed_now is False
    assert "raw_exposure_attempted" in unsafe.blocked_reasons
    assert "id_exposure_attempted" in unsafe.blocked_reasons
    assert "credential_signature_headers_exposure_attempted" in unsafe.blocked_reasons
    assert unsafe.entry_retry_allowed is False
    assert unsafe.entry_second_post_allowed is False


def test_signal_mvp_emits_exit_only_when_position_open() -> None:
    result = evaluate_level5_signal_mvp(
        Level5SignalMvpInput(
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
            exit_reason_label=Level5ExitReasonLabel.TAKE_PROFIT,
        ),
    )
    no_position = evaluate_level5_signal_mvp(
        Level5SignalMvpInput(
            position_status=PositionReadOnlyStatus.NO_POSITION,
            exit_reason_label=Level5ExitReasonLabel.TAKE_PROFIT,
        ),
    )

    assert result.signal_type is Level5SignalType.EXIT
    assert no_position.signal_type is Level5SignalType.HOLD


def test_signal_mvp_blocks_missing_market_source_and_direct_post() -> None:
    result = evaluate_level5_signal_mvp(
        Level5SignalMvpInput(
            market_source_available=False,
            signal_direct_post_attempted=True,
            retry_or_repost_attempted=True,
        ),
    )

    assert result.signal_type is Level5SignalType.BLOCKED
    assert result.signal_direct_post_attempted is False
    assert "market_adapter_missing" in result.blocked_reasons
    assert "signal_direct_post_attempted" in result.blocked_reasons


def test_fast_config_fixes_units_one_position_and_no_retry() -> None:
    result = build_level5_fast_track_config()

    assert result.config_ready is True
    assert result.symbol == "USD_JPY"
    assert result.units == 100
    assert result.max_open_positions == 1
    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_post_allowed is False
    assert result.human_monitoring_required is True
    assert result.kill_switch_required is True


def test_fast_config_blocks_unsafe_overrides() -> None:
    result = build_level5_fast_track_config(
        Level5FastTrackConfigInput(units=101, max_open_positions=2, retry_allowed=True),
    )

    assert result.config_ready is False
    assert result.retry_allowed is False
    assert "units_must_be_100" in result.blocked_reasons
    assert "max_open_positions_must_be_1" in result.blocked_reasons
    assert "retry_allowed" in result.blocked_reasons


def test_foundation_summary_never_executes_post_or_ledger_receipt() -> None:
    result = build_level5_fast_mvp_foundation(
        position_input=PositionReadOnlyStatusInput(
            position_status_checked=True,
            position_status_unknown=False,
            position_source_available=True,
            open_position_count=0,
        ),
    )
    rendered = render_level5_fast_mvp_foundation_markdown(result)

    assert result.foundation_ready is True
    assert result.actual_http_post_executed is False
    assert result.close_post_executed is False
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.receipt_handoff_executed is False
    assert result.raw_id_value_exposure is False
    assert result.credential_signature_headers_exposure is False
    assert "actual_http_post_executed: false" in rendered
    assert "close_post_executed: false" in rendered


def test_foundation_connects_position_route_unknown_to_entry_block() -> None:
    position_route = build_position_read_only_controlled(
        PositionReadOnlyControlledInput(
            position_source_available=True,
            position_status_checked=False,
            position_status_unknown=True,
        ),
    )
    result = build_level5_fast_mvp_foundation(
        position_controlled_result=position_route,
        cycle_input=Level5CycleTransitionInput(
            current_state=Level5CycleState.IDLE,
            entry_signal=True,
        ),
    )

    assert result.position_status.position_status is PositionReadOnlyStatus.UNKNOWN
    assert result.position_status.new_entry_allowed is False
    assert result.close_route.close_route_ready is False
    assert result.signal.signal_type is Level5SignalType.BLOCKED
    assert result.cycle_transition.next_state is Level5CycleState.HALTED
    assert "entry_requires_no_position" in result.cycle_transition.blocked_reasons


def test_foundation_uses_default_connected_position_source_as_unknown_fail_closed() -> None:
    position_route = build_position_read_only_controlled()
    result = build_level5_fast_mvp_foundation(position_controlled_result=position_route)

    assert result.position_status.position_status is PositionReadOnlyStatus.UNKNOWN
    assert result.position_status.new_entry_allowed is False
    assert result.position_status.close_allowed is False
    assert result.close_route.close_route_ready is False
    assert result.close_order_route.close_planning_allowed is False
    assert result.close_order_route.close_execution_allowed_now is False
    assert "position_unknown" in result.close_route.blocked_reasons


def test_foundation_connects_one_position_to_close_planning_only() -> None:
    position_route = build_position_read_only_controlled(
        PositionReadOnlyControlledInput(
            position_source_available=True,
            position_status_checked=True,
            position_status_unknown=False,
            position_count_safe=1,
        ),
    )
    result = build_level5_fast_mvp_foundation(position_controlled_result=position_route)

    assert result.position_status.position_status is PositionReadOnlyStatus.ONE_POSITION_OPEN
    assert result.position_status.new_entry_allowed is False
    assert result.position_status.close_allowed is True
    assert result.close_route.close_route_ready is True
    assert result.close_order_route.close_planning_allowed is True
    assert result.close_order_route.close_execution_allowed_now is False
    assert result.close_order_route.close_post_executed is False
    assert result.close_execution_route.close_execution_route_ready is False
    assert result.close_execution_route.close_executable_preview_ready is False
    assert result.close_execution_route.next_cycle_state == NEXT_CYCLE_STATE_SIDE_UNRESOLVED
    assert result.close_execution_route.actual_close_post_allowed_now is False
    assert result.close_execution_route.actual_close_post_executed is False
    assert result.close_route.close_post_executed is False
    assert result.actual_http_post_executed is False
    assert result.close_post_executed is False


def test_foundation_blocks_guarded_generic_close_execution_route_no_post_input() -> None:
    result = build_level5_fast_mvp_foundation(
        close_execution_route_input=CloseOrderExecutionRouteControlledInput(
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
    rendered = render_level5_fast_mvp_foundation_markdown(result)

    assert result.close_execution_route.close_execution_route_ready is False
    assert result.close_execution_route.close_executable_preview_ready is False
    assert result.close_execution_route.close_side_safe_label == "SELL"
    assert (
        result.close_execution_route.next_cycle_state
        == NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ROUTE_MISSING
    )
    assert result.close_execution_route.generic_close_primitive_revoked is True
    assert result.close_execution_route.official_settlement_route_confirmed is False
    assert result.close_execution_route.actual_close_post_allowed_now is False
    assert result.close_execution_route.actual_close_post_executed is False
    assert result.close_execution_route.close_retry_allowed is False
    assert result.close_execution_route.close_repost_allowed is False
    assert result.close_execution_route.close_second_post_allowed is False
    assert result.close_execution_route.ledger_update_this_step is False
    assert result.close_execution_route.receipt_handoff_this_step is False
    assert "close_execution_route_ready: false" in rendered
    assert "close_executable_preview_ready: false" in rendered
    assert "actual_close_post_allowed_now: false" in rendered


def test_foundation_accepts_official_close_specific_route_ready_no_post_input() -> None:
    result = build_level5_fast_mvp_foundation(
        close_execution_route_input=CloseOrderExecutionRouteControlledInput(
            runtime_position_status=PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
            position_count_safe=1,
            has_exactly_one_position=True,
            has_multiple_positions=False,
            close_route_ready=True,
            close_planning_allowed=True,
            fresh_entry_side_safe_label="BUY",
            approved_close_post_primitive_kind=(
                APPROVED_CLOSE_PRIMITIVE_KIND_CLOSE_SPECIFIC
            ),
            approved_close_post_primitive_is_close_specific=True,
            approved_close_post_primitive_is_generic_order=False,
            generic_order_accepted_as_close_only_with_exact_one_position_guard=False,
            official_settlement_route_confirmed=True,
        ),
    )

    assert result.close_execution_route.close_execution_route_ready is True
    assert result.close_execution_route.close_executable_preview_ready is True
    assert result.close_execution_route.close_side_safe_label == "SELL"
    assert result.close_execution_route.next_cycle_state == NEXT_CYCLE_STATE_READY
    assert result.close_execution_route.actual_close_post_allowed_now is False
    assert result.close_execution_route.actual_close_post_executed is False


def test_cycle_blocks_second_entry_when_position_route_has_one_position() -> None:
    position_route = build_position_read_only_controlled(
        PositionReadOnlyControlledInput(
            position_source_available=True,
            position_status_checked=True,
            position_status_unknown=False,
            position_count_safe=1,
        ),
    )
    result = build_level5_fast_mvp_foundation(
        position_controlled_result=position_route,
        cycle_input=Level5CycleTransitionInput(
            current_state=Level5CycleState.POSITION_OPEN_SAFE,
            entry_signal=True,
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
        ),
    )

    assert result.cycle_transition.next_state is Level5CycleState.HALTED
    assert result.cycle_transition.retry_allowed is False
    assert result.cycle_transition.second_post_allowed is False
    assert "second_entry_blocked" in result.cycle_transition.blocked_reasons


def test_foundation_connects_multiple_position_route_to_close_block() -> None:
    position_route = build_position_read_only_controlled(
        PositionReadOnlyControlledInput(
            position_source_available=True,
            position_status_checked=True,
            position_status_unknown=False,
            position_count_safe=2,
        ),
    )
    result = build_level5_fast_mvp_foundation(position_controlled_result=position_route)

    assert result.position_status.position_status is PositionReadOnlyStatus.BLOCKED
    assert result.position_status.new_entry_allowed is False
    assert result.position_status.close_allowed is False
    assert result.close_route.close_route_ready is False
    assert result.close_order_route.close_planning_allowed is False
    assert "position_blocked_or_multiple" in result.close_route.blocked_reasons


def test_level5_exit_signal_one_position_reaches_close_ready_without_post() -> None:
    result = build_level5_fast_mvp_foundation(
        position_input=PositionReadOnlyStatusInput(
            position_status_checked=True,
            position_status_unknown=False,
            position_source_available=True,
            open_position_count=1,
        ),
        cycle_input=Level5CycleTransitionInput(
            current_state=Level5CycleState.EXIT_SIGNAL,
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
        ),
    )

    assert result.cycle_transition.next_state is Level5CycleState.CLOSE_READY
    assert result.close_order_route.close_planning_allowed is True
    assert result.close_order_route.close_execution_allowed_now is False
    assert result.close_order_route.close_post_executed is False
    assert result.close_post_executed is False


def test_level5_exit_signal_blocks_unknown_no_position_and_multiple() -> None:
    unknown = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.EXIT_SIGNAL,
            position_status=PositionReadOnlyStatus.UNKNOWN,
        ),
    )
    no_position = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.EXIT_SIGNAL,
            position_status=PositionReadOnlyStatus.NO_POSITION,
        ),
    )
    multiple = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.EXIT_SIGNAL,
            position_status=PositionReadOnlyStatus.BLOCKED,
        ),
    )

    for result in (unknown, no_position, multiple):
        assert result.next_state is Level5CycleState.HALTED
        assert result.halted is True
        assert "close_ready_requires_one_position" in result.blocked_reasons


def test_level5_close_ready_does_not_reach_close_sent_without_execution_gate() -> None:
    result = transition_level5_cycle_state(
        Level5CycleTransitionInput(current_state=Level5CycleState.CLOSE_READY),
    )

    assert result.next_state is Level5CycleState.CLOSE_READY
    assert result.next_state is not Level5CycleState.CLOSE_SENT
    assert result.retry_allowed is False
    assert result.second_post_allowed is False


def test_level5_signal_entry_cycle_reaches_entry_ready_without_post() -> None:
    result = build_level5_fast_mvp_foundation(
        position_input=PositionReadOnlyStatusInput(
            position_status_checked=True,
            position_status_unknown=False,
            position_source_available=True,
            open_position_count=0,
        ),
        signal_input=Level5SignalMvpInput(
            trend_label=Level5TrendLabel.UPTREND,
            spread_label=Level5SpreadLabel.NORMAL,
            time_market_label=Level5TimeMarketLabel.OK,
            position_status=PositionReadOnlyStatus.NO_POSITION,
            signal_source=Level5SignalSource.SAFE_SNAPSHOT,
        ),
    )

    assert result.position_status.position_status is PositionReadOnlyStatus.NO_POSITION
    assert result.signal.signal_type is Level5SignalType.ENTRY_BUY
    assert result.entry_planning.entry_planning_gate_ready is True
    assert result.entry_planning.entry_planning_allowed is True
    assert result.entry_planning.entry_execution_allowed_now is False
    assert result.entry_planning.entry_execution_step_may_be_planned is True
    assert result.entry_planning.entry_side_safe_label == "BUY"
    assert result.cycle_transition.next_state is Level5CycleState.ENTRY_READY
    assert result.cycle_transition.next_state is not Level5CycleState.ENTRY_SENT
    assert result.actual_http_post_executed is False
    assert result.close_post_executed is False
    assert result.retry_attempted is False
    assert result.second_post_attempted is False


def test_level5_signal_entry_cycle_blocks_hold_unknown_open_and_multiple() -> None:
    hold = build_level5_fast_mvp_foundation(
        position_input=PositionReadOnlyStatusInput(
            position_status_checked=True,
            position_status_unknown=False,
            position_source_available=True,
            open_position_count=0,
        ),
        signal_input=Level5SignalMvpInput(
            trend_label=Level5TrendLabel.FLAT,
            position_status=PositionReadOnlyStatus.NO_POSITION,
        ),
    )
    unknown = build_level5_fast_mvp_foundation(
        position_input=PositionReadOnlyStatusInput(),
        signal_input=Level5SignalMvpInput(
            trend_label=Level5TrendLabel.UPTREND,
            position_status=PositionReadOnlyStatus.UNKNOWN,
        ),
    )
    one_position = build_level5_fast_mvp_foundation(
        position_input=PositionReadOnlyStatusInput(
            position_status_checked=True,
            position_status_unknown=False,
            position_source_available=True,
            open_position_count=1,
        ),
        signal_input=Level5SignalMvpInput(
            trend_label=Level5TrendLabel.UPTREND,
            position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN,
        ),
    )
    multiple = build_level5_fast_mvp_foundation(
        position_input=PositionReadOnlyStatusInput(
            position_status_checked=True,
            position_status_unknown=False,
            position_source_available=True,
            open_position_count=2,
        ),
        signal_input=Level5SignalMvpInput(
            trend_label=Level5TrendLabel.UPTREND,
            position_status=PositionReadOnlyStatus.BLOCKED,
        ),
    )

    assert hold.signal.signal_type is Level5SignalType.HOLD
    assert hold.entry_planning.entry_planning_allowed is False
    assert hold.cycle_transition.next_state is Level5CycleState.IDLE
    for result in (unknown, one_position, multiple):
        assert result.entry_planning.entry_planning_allowed is False
        assert result.cycle_transition.next_state is not Level5CycleState.ENTRY_SENT
        assert result.actual_http_post_executed is False
        assert result.close_post_executed is False


def test_entry_ready_does_not_reach_entry_sent_without_execution_gate() -> None:
    result = transition_level5_cycle_state(
        Level5CycleTransitionInput(current_state=Level5CycleState.ENTRY_READY),
    )

    assert result.next_state is Level5CycleState.ENTRY_READY
    assert result.next_state is not Level5CycleState.ENTRY_SENT
    assert result.retry_allowed is False
    assert result.second_post_allowed is False


def test_new_module_import_construct_and_summary_have_no_execution_dependencies() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_step6g_level5_fast_mvp_controlled.py"
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
            assert all(
                not alias.name.startswith(tuple(blocked_modules))
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(tuple(blocked_modules))
