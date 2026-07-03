"""Step 6G Level 5 fast-track MVP foundation.

This module defines safe contracts for the minimum Level 5 cycle foundation:
sanitized ledger-like record, review-only receipt summary, position status,
close-route readiness, cycle state, signal MVP, and fixed fast-track config.
It does not execute HTTP POST, close POST, broker/private API calls, order
endpoints, live_order_once, ledger writes, receipt handoff, env access, or raw
ID/value handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_close_order_route_controlled import (
    CloseOrderRouteControlledInput,
    CloseOrderRouteControlledResult,
    build_close_order_route_controlled,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledResult,
    PositionReadOnlyControlledStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

LEVEL5_FAST_MVP_LABEL = "STEP6G_LEVEL5_FAST_MVP_FOUNDATION_CONTROLLED"
SAFE_LEDGER_RECORD_LABEL = "STEP6G_SAFE_SANITIZED_LEDGER_LIKE_RECORD"
SAFE_RECEIPT_SUMMARY_LABEL = "STEP6G_REVIEW_ONLY_RECEIPT_SUMMARY"
SAFE_POSITION_STATUS_LABEL = "STEP6G_POSITION_READ_ONLY_STATUS_CONTRACT"
SAFE_CLOSE_ROUTE_LABEL = "STEP6G_CLOSE_ROUTE_FOUNDATION_NO_POST"
SAFE_CYCLE_STATE_LABEL = "STEP6G_LEVEL5_CYCLE_STATE_MACHINE"
SAFE_SIGNAL_MVP_LABEL = "STEP6G_LEVEL5_SIGNAL_MVP_CONTRACT"
SAFE_ENTRY_PLANNING_LABEL = "STEP6G_LEVEL5_ENTRY_PLANNING_GATE_NO_POST"
SAFE_FAST_TRACK_CONFIG_LABEL = "STEP6G_LEVEL5_FAST_TRACK_SAFE_CONFIG"

RESULT_ACCEPTED_SANITIZED = "RESULT_ACCEPTED_SANITIZED"
RECONCILIATION_READY_NO_RECEIPT_HANDOFF = "RECONCILIATION_READY_NO_RECEIPT_HANDOFF"
SAFE_ENVIRONMENT_LABEL = "STEP6G_LEVEL5_FAST_TRACK_CONTROLLED"
SAFE_RISK_LABEL = "STEP6G_LEVEL5_100_UNITS_ONE_POSITION"


class Level5FastMvpStatus(str, Enum):
    READY = "LEVEL5_FAST_MVP_FOUNDATION_READY_NO_POST"
    BLOCKED = "LEVEL5_FAST_MVP_FOUNDATION_BLOCKED"


class SafeLedgerLikeRecordStatus(str, Enum):
    READY = "SAFE_LEDGER_LIKE_RECORD_READY_NO_LEDGER_WRITE"
    BLOCKED = "SAFE_LEDGER_LIKE_RECORD_BLOCKED"


class ReviewOnlyReceiptSummaryStatus(str, Enum):
    READY = "REVIEW_ONLY_RECEIPT_SUMMARY_READY_NO_HANDOFF"
    BLOCKED = "REVIEW_ONLY_RECEIPT_SUMMARY_BLOCKED"


class PositionReadOnlyStatus(str, Enum):
    NO_POSITION = "NO_POSITION"
    ONE_POSITION_OPEN = "ONE_POSITION_OPEN"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


class CloseRouteFoundationStatus(str, Enum):
    READY = "CLOSE_ROUTE_FOUNDATION_READY_NO_POST"
    BLOCKED = "CLOSE_ROUTE_FOUNDATION_BLOCKED"


class Level5CycleState(str, Enum):
    IDLE = "IDLE"
    ENTRY_SIGNAL = "ENTRY_SIGNAL"
    ENTRY_READY = "ENTRY_READY"
    ENTRY_SENT = "ENTRY_SENT"
    ENTRY_ACCEPTED_SANITIZED = "ENTRY_ACCEPTED_SANITIZED"
    POSITION_CHECK_PENDING = "POSITION_CHECK_PENDING"
    POSITION_OPEN_SAFE = "POSITION_OPEN_SAFE"
    UNKNOWN_RESULT_SAFE_STOP = "UNKNOWN_RESULT_SAFE_STOP"
    ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT = "ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT"
    EXIT_SIGNAL = "EXIT_SIGNAL"
    CLOSE_READY = "CLOSE_READY"
    CLOSE_SENT = "CLOSE_SENT"
    CLOSED_SAFE = "CLOSED_SAFE"
    HALTED = "HALTED"


class Level5SignalType(str, Enum):
    ENTRY_BUY = "ENTRY_BUY"
    ENTRY_SELL = "ENTRY_SELL"
    EXIT = "EXIT"
    HOLD = "HOLD"
    BLOCKED = "BLOCKED"


class Level5SignalSource(str, Enum):
    RULE_MVP = "RULE_MVP"
    MANUAL_INJECTED = "MANUAL_INJECTED"
    SAFE_SNAPSHOT = "SAFE_SNAPSHOT"
    MARKET_ADAPTER_MISSING = "MARKET_ADAPTER_MISSING"


class Level5SignalConfidenceLabel(str, Enum):
    LOW = "LOW"
    TEST_ONLY = "TEST_ONLY"
    BLOCKED = "BLOCKED"


class Level5TrendLabel(str, Enum):
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


class Level5VolatilityLabel(str, Enum):
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class Level5SpreadLabel(str, Enum):
    NORMAL = "NORMAL"
    WIDE = "WIDE"
    UNKNOWN = "UNKNOWN"


class Level5TimeMarketLabel(str, Enum):
    OK = "OK"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class Level5ExitReasonLabel(str, Enum):
    NONE = "NONE"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    MAX_HOLD_TIME = "MAX_HOLD_TIME"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Level5FastTrackConfigInput:
    symbol: str = SUPPORTED_SYMBOL
    units: int = SUPPORTED_UNITS
    max_open_positions: int = 1
    max_entry_orders_per_cycle: int = 1
    max_close_orders_per_cycle: int = 1
    retry_allowed: bool = False
    repost_allowed: bool = False
    second_post_allowed: bool = False
    human_monitoring_required: bool = True
    operator_confirmation_required_for_actual_post: bool = True
    time_market_gate_required: bool = True
    kill_switch_required: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("symbol", self.symbol)
        _validate_non_negative_int("units", self.units)
        _validate_non_negative_int("max_open_positions", self.max_open_positions)
        _validate_non_negative_int(
            "max_entry_orders_per_cycle",
            self.max_entry_orders_per_cycle,
        )
        _validate_non_negative_int(
            "max_close_orders_per_cycle",
            self.max_close_orders_per_cycle,
        )
        _validate_bool_fields(self, _FAST_CONFIG_BOOL_FIELDS)


@dataclass(frozen=True)
class Level5FastTrackConfigResult:
    config_ready: bool
    safe_config_label: str
    symbol: str
    units: int
    max_open_positions: int
    max_entry_orders_per_cycle: int
    max_close_orders_per_cycle: int
    retry_allowed: bool
    repost_allowed: bool
    second_post_allowed: bool
    human_monitoring_required: bool
    operator_confirmation_required_for_actual_post: bool
    time_market_gate_required: bool
    kill_switch_required: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("safe_config_label", self.safe_config_label)
        _validate_non_negative_int("units", self.units)
        _validate_bool_fields(self, _FAST_CONFIG_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


@dataclass(frozen=True)
class SafeLedgerLikeRecordInput:
    post_execution_count: int = 1
    sanitized_result_category: str = RESULT_ACCEPTED_SANITIZED
    safe_reconciliation_status: str = RECONCILIATION_READY_NO_RECEIPT_HANDOFF
    retry_attempted: bool = False
    second_post_attempted: bool = False
    ledger_updated: bool = False
    receipt_handoff_executed: bool = False
    raw_request_exposed: bool = False
    raw_response_exposed: bool = False
    broker_api_response_exposed: bool = False
    credential_value_exposed: bool = False
    signature_value_exposed: bool = False
    headers_value_exposed: bool = False
    real_id_exposed: bool = False

    def __post_init__(self) -> None:
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _require_non_empty("sanitized_result_category", self.sanitized_result_category)
        _require_non_empty("safe_reconciliation_status", self.safe_reconciliation_status)
        _validate_bool_fields(self, _LEDGER_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class SafeLedgerLikeRecordResult:
    status: SafeLedgerLikeRecordStatus
    safe_record_ready: bool
    safe_record_label: str
    post_execution_count: int
    sanitized_result_category: str
    safe_reconciliation_status: str
    retry_attempted: bool
    second_post_attempted: bool
    ledger_updated_before_real_ledger_step: bool
    receipt_handoff_executed: bool
    production_ledger_written: bool
    raw_id_value_exposure: bool
    credential_signature_headers_exposure: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, SafeLedgerLikeRecordStatus):
            raise LiveVerificationValidationError("status must be safe ledger status")
        _require_non_empty("safe_record_label", self.safe_record_label)
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _LEDGER_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


@dataclass(frozen=True)
class ReviewOnlyReceiptSummaryInput:
    sanitized_result_category: str = RESULT_ACCEPTED_SANITIZED
    post_execution_count: int = 1
    retry_attempted: bool = False
    second_post_attempted: bool = False
    actual_receipt_handoff_executed: bool = False
    raw_response_required: bool = False
    real_id_required: bool = False
    broker_api_response_required: bool = False
    manual_broker_ui_check_recommended: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("sanitized_result_category", self.sanitized_result_category)
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _RECEIPT_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class ReviewOnlyReceiptSummaryResult:
    status: ReviewOnlyReceiptSummaryStatus
    receipt_summary_ready: bool
    safe_receipt_summary_label: str
    actual_receipt_handoff_executed: bool
    raw_response_required: bool
    real_id_required: bool
    broker_api_response_required: bool
    manual_broker_ui_check_recommended: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, ReviewOnlyReceiptSummaryStatus):
            raise LiveVerificationValidationError("status must be receipt status")
        _require_non_empty("safe_receipt_summary_label", self.safe_receipt_summary_label)
        _validate_bool_fields(self, _RECEIPT_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


@dataclass(frozen=True)
class PositionReadOnlyStatusInput:
    position_status_checked: bool = False
    open_position_count: int = 0
    position_status_unknown: bool = True
    position_source_available: bool = False
    max_open_positions: int = 1
    raw_position_id_exposed: bool = False
    account_id_exposed: bool = False
    order_id_exposed: bool = False
    transaction_id_exposed: bool = False
    position_value_exposed: bool = False

    def __post_init__(self) -> None:
        _validate_non_negative_int("open_position_count", self.open_position_count)
        _validate_non_negative_int("max_open_positions", self.max_open_positions)
        _validate_bool_fields(self, _POSITION_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class PositionReadOnlyStatusResult:
    position_status_checked: bool
    position_status: PositionReadOnlyStatus
    safe_position_status_label: str
    open_position_count_safe: int
    max_open_positions: int
    new_entry_allowed: bool
    close_allowed: bool
    raw_position_id_exposed: bool
    account_id_exposed: bool
    order_id_exposed: bool
    transaction_id_exposed: bool
    position_value_exposed: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.position_status, PositionReadOnlyStatus):
            raise LiveVerificationValidationError("position_status must be enum")
        _require_non_empty("safe_position_status_label", self.safe_position_status_label)
        _validate_non_negative_int("open_position_count_safe", self.open_position_count_safe)
        _validate_non_negative_int("max_open_positions", self.max_open_positions)
        _validate_bool_fields(self, _POSITION_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


@dataclass(frozen=True)
class CloseRouteFoundationInput:
    position_status: PositionReadOnlyStatus = PositionReadOnlyStatus.UNKNOWN
    close_size: int = SUPPORTED_UNITS
    close_symbol_matches_position: bool = True
    close_side_is_opposite: bool = True
    close_post_executed: bool = False
    close_post_count: int = 0
    close_retry_allowed: bool = False
    close_second_post_allowed: bool = False
    raw_id_required: bool = False
    raw_response_required: bool = False
    broker_api_response_required: bool = False
    credential_signature_headers_required: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.position_status, PositionReadOnlyStatus):
            raise LiveVerificationValidationError("position_status must be enum")
        _validate_non_negative_int("close_size", self.close_size)
        _validate_non_negative_int("close_post_count", self.close_post_count)
        _validate_bool_fields(self, _CLOSE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class CloseRouteFoundationResult:
    status: CloseRouteFoundationStatus
    close_route_ready: bool
    safe_close_route_label: str
    close_post_executed: bool
    close_post_count: int
    close_retry_allowed: bool
    close_second_post_allowed: bool
    close_requires_position_status: str
    close_blocks_if_position_unknown: bool
    close_blocks_if_no_position: bool
    close_blocks_if_multiple_positions: bool
    close_size_fixed: int
    close_symbol_matches_position: bool
    close_side_is_opposite: bool
    raw_id_required: bool
    raw_response_required: bool
    broker_api_response_required: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, CloseRouteFoundationStatus):
            raise LiveVerificationValidationError("status must be close route status")
        _require_non_empty("safe_close_route_label", self.safe_close_route_label)
        _validate_non_negative_int("close_post_count", self.close_post_count)
        _validate_non_negative_int("close_size_fixed", self.close_size_fixed)
        _validate_bool_fields(self, _CLOSE_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


@dataclass(frozen=True)
class Level5SignalMvpInput:
    trend_label: Level5TrendLabel = Level5TrendLabel.FLAT
    volatility_label: Level5VolatilityLabel = Level5VolatilityLabel.NORMAL
    spread_label: Level5SpreadLabel = Level5SpreadLabel.NORMAL
    time_market_label: Level5TimeMarketLabel = Level5TimeMarketLabel.OK
    position_status: PositionReadOnlyStatus = PositionReadOnlyStatus.NO_POSITION
    exit_reason_label: Level5ExitReasonLabel = Level5ExitReasonLabel.NONE
    signal_source: Level5SignalSource = Level5SignalSource.RULE_MVP
    market_source_available: bool = True
    safe_config_allows_entry: bool = True
    actual_market_raw_value_exposed: bool = False
    actual_market_value_exposed: bool = False
    raw_market_data_exposed: bool = False
    signal_direct_post_attempted: bool = False
    signal_directly_executes_post: bool = False
    retry_or_repost_attempted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.trend_label, Level5TrendLabel):
            raise LiveVerificationValidationError("trend_label must be enum")
        if not isinstance(self.volatility_label, Level5VolatilityLabel):
            raise LiveVerificationValidationError("volatility_label must be enum")
        if not isinstance(self.spread_label, Level5SpreadLabel):
            raise LiveVerificationValidationError("spread_label must be enum")
        if not isinstance(self.time_market_label, Level5TimeMarketLabel):
            raise LiveVerificationValidationError("time_market_label must be enum")
        if not isinstance(self.position_status, PositionReadOnlyStatus):
            raise LiveVerificationValidationError("position_status must be enum")
        if not isinstance(self.exit_reason_label, Level5ExitReasonLabel):
            raise LiveVerificationValidationError("exit_reason_label must be enum")
        if not isinstance(self.signal_source, Level5SignalSource):
            raise LiveVerificationValidationError("signal_source must be enum")
        _validate_bool_fields(self, _SIGNAL_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class Level5SignalMvpResult:
    signal_checked: bool
    signal_type: Level5SignalType
    signal_source: Level5SignalSource
    signal_confidence_label: Level5SignalConfidenceLabel
    signal_reason_label: str
    actual_market_raw_value_exposed: bool
    actual_market_value_exposed: bool
    raw_market_data_exposed: bool
    signal_direct_post_attempted: bool
    signal_directly_executes_post: bool
    retry_or_repost_attempted: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.signal_type, Level5SignalType):
            raise LiveVerificationValidationError("signal_type must be enum")
        if not isinstance(self.signal_source, Level5SignalSource):
            raise LiveVerificationValidationError("signal_source must be enum")
        if not isinstance(self.signal_confidence_label, Level5SignalConfidenceLabel):
            raise LiveVerificationValidationError("confidence label must be enum")
        _require_non_empty("signal_reason_label", self.signal_reason_label)
        _validate_bool_fields(self, _SIGNAL_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


@dataclass(frozen=True)
class Level5EntryPlanningGateInput:
    position_status: PositionReadOnlyStatus = PositionReadOnlyStatus.UNKNOWN
    signal_checked: bool = False
    signal_type: Level5SignalType = Level5SignalType.HOLD
    entry_symbol_safe_label: str = SUPPORTED_SYMBOL
    entry_units_fixed: int = SUPPORTED_UNITS
    entry_order_type_safe_label: str = "MARKET"
    signal_directly_executes_post: bool = False
    actual_http_post_attempted: bool = False
    close_post_attempted: bool = False
    retry_or_repost_attempted: bool = False
    second_post_attempted: bool = False
    raw_exposure_attempted: bool = False
    id_exposure_attempted: bool = False
    credential_signature_headers_exposure_attempted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.position_status, PositionReadOnlyStatus):
            raise LiveVerificationValidationError("position_status must be enum")
        if not isinstance(self.signal_type, Level5SignalType):
            raise LiveVerificationValidationError("signal_type must be enum")
        _require_non_empty("entry_symbol_safe_label", self.entry_symbol_safe_label)
        _require_non_empty("entry_order_type_safe_label", self.entry_order_type_safe_label)
        _validate_non_negative_int("entry_units_fixed", self.entry_units_fixed)
        _validate_bool_fields(self, _ENTRY_PLANNING_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class Level5EntryPlanningGateResult:
    entry_planning_gate_ready: bool
    entry_planning_allowed: bool
    entry_execution_allowed_now: bool
    entry_execution_step_may_be_planned: bool
    entry_requires_new_confirmation: bool
    entry_requires_time_market_operator_gate: bool
    entry_execution_requires_position_status_current: bool
    entry_execution_requires_no_position: bool
    entry_execution_requires_no_retry: bool
    entry_execution_requires_no_second_post: bool
    entry_execution_requires_raw_id_exposure_false: bool
    entry_units_fixed: int
    entry_symbol_safe_label: str
    entry_order_type_safe_label: str
    entry_side_safe_label: str
    entry_retry_allowed: bool
    entry_second_post_allowed: bool
    entry_raw_exposure: bool
    entry_id_exposure: bool
    actual_http_post_executed: bool
    close_post_executed: bool
    signal_directly_executes_post: bool
    credential_signature_headers_exposure: bool
    safe_entry_planning_label: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("entry_symbol_safe_label", self.entry_symbol_safe_label)
        _require_non_empty("entry_order_type_safe_label", self.entry_order_type_safe_label)
        _require_non_empty("entry_side_safe_label", self.entry_side_safe_label)
        _require_non_empty("safe_entry_planning_label", self.safe_entry_planning_label)
        _validate_non_negative_int("entry_units_fixed", self.entry_units_fixed)
        _validate_bool_fields(self, _ENTRY_PLANNING_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


@dataclass(frozen=True)
class Level5CycleTransitionInput:
    current_state: Level5CycleState = Level5CycleState.IDLE
    entry_signal: bool = False
    entry_execution_gate_passed: bool = False
    entry_accepted_sanitized: bool = False
    position_status: PositionReadOnlyStatus = PositionReadOnlyStatus.UNKNOWN
    exit_signal: bool = False
    close_execution_gate_passed: bool = False
    close_accepted_sanitized: bool = False
    no_position_after_close: bool = False
    entry_unknown_no_position_closeout_confirmed: bool = False
    daily_limits_ok: bool = True
    retry_attempted: bool = False
    second_post_attempted: bool = False
    timeout: bool = False
    unknown: bool = False
    unavailable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.current_state, Level5CycleState):
            raise LiveVerificationValidationError("current_state must be enum")
        if not isinstance(self.position_status, PositionReadOnlyStatus):
            raise LiveVerificationValidationError("position_status must be enum")
        _validate_bool_fields(self, _CYCLE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class Level5CycleTransitionResult:
    safe_cycle_state_label: str
    previous_state: Level5CycleState
    next_state: Level5CycleState
    halted: bool
    retry_allowed: bool
    second_post_allowed: bool
    automatic_recovery_allowed: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("safe_cycle_state_label", self.safe_cycle_state_label)
        if not isinstance(self.previous_state, Level5CycleState):
            raise LiveVerificationValidationError("previous_state must be enum")
        if not isinstance(self.next_state, Level5CycleState):
            raise LiveVerificationValidationError("next_state must be enum")
        _validate_bool_fields(self, _CYCLE_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


@dataclass(frozen=True)
class Level5FastMvpFoundationResult:
    status: Level5FastMvpStatus
    foundation_ready: bool
    safe_level5_label: str
    config: Level5FastTrackConfigResult
    ledger_record: SafeLedgerLikeRecordResult
    receipt_summary: ReviewOnlyReceiptSummaryResult
    position_status: PositionReadOnlyStatusResult
    close_route: CloseRouteFoundationResult
    close_order_route: CloseOrderRouteControlledResult
    signal: Level5SignalMvpResult
    entry_planning: Level5EntryPlanningGateResult
    cycle_transition: Level5CycleTransitionResult
    actual_http_post_executed: bool
    close_post_executed: bool
    retry_attempted: bool
    second_post_attempted: bool
    ledger_updated: bool
    receipt_handoff_executed: bool
    raw_id_value_exposure: bool
    credential_signature_headers_exposure: bool
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, Level5FastMvpStatus):
            raise LiveVerificationValidationError("status must be level5 status")
        _require_non_empty("safe_level5_label", self.safe_level5_label)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(self, _FOUNDATION_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_level5_fast_track_config(
    input_snapshot: Level5FastTrackConfigInput | None = None,
) -> Level5FastTrackConfigResult:
    snapshot = input_snapshot or Level5FastTrackConfigInput()
    reasons = _fast_config_blocked_reasons(snapshot)
    return Level5FastTrackConfigResult(
        config_ready=not reasons,
        safe_config_label=SAFE_FAST_TRACK_CONFIG_LABEL,
        symbol=snapshot.symbol,
        units=snapshot.units,
        max_open_positions=snapshot.max_open_positions,
        max_entry_orders_per_cycle=snapshot.max_entry_orders_per_cycle,
        max_close_orders_per_cycle=snapshot.max_close_orders_per_cycle,
        retry_allowed=False,
        repost_allowed=False,
        second_post_allowed=False,
        human_monitoring_required=snapshot.human_monitoring_required,
        operator_confirmation_required_for_actual_post=(
            snapshot.operator_confirmation_required_for_actual_post
        ),
        time_market_gate_required=snapshot.time_market_gate_required,
        kill_switch_required=snapshot.kill_switch_required,
        blocked_reasons=reasons,
    )


def build_safe_ledger_like_record(
    input_snapshot: SafeLedgerLikeRecordInput | None = None,
) -> SafeLedgerLikeRecordResult:
    snapshot = input_snapshot or SafeLedgerLikeRecordInput()
    reasons = _ledger_blocked_reasons(snapshot)
    raw_id_value_exposure = _raw_id_value_exposed(snapshot)
    credential_exposure = _credential_signature_headers_exposed(snapshot)
    return SafeLedgerLikeRecordResult(
        status=(
            SafeLedgerLikeRecordStatus.READY
            if not reasons
            else SafeLedgerLikeRecordStatus.BLOCKED
        ),
        safe_record_ready=not reasons,
        safe_record_label=SAFE_LEDGER_RECORD_LABEL,
        post_execution_count=snapshot.post_execution_count,
        sanitized_result_category=snapshot.sanitized_result_category,
        safe_reconciliation_status=snapshot.safe_reconciliation_status,
        retry_attempted=snapshot.retry_attempted,
        second_post_attempted=snapshot.second_post_attempted,
        ledger_updated_before_real_ledger_step=snapshot.ledger_updated,
        receipt_handoff_executed=snapshot.receipt_handoff_executed,
        production_ledger_written=False,
        raw_id_value_exposure=raw_id_value_exposure,
        credential_signature_headers_exposure=credential_exposure,
        blocked_reasons=reasons,
    )


def build_review_only_receipt_summary(
    input_snapshot: ReviewOnlyReceiptSummaryInput | None = None,
) -> ReviewOnlyReceiptSummaryResult:
    snapshot = input_snapshot or ReviewOnlyReceiptSummaryInput()
    reasons = _receipt_blocked_reasons(snapshot)
    return ReviewOnlyReceiptSummaryResult(
        status=(
            ReviewOnlyReceiptSummaryStatus.READY
            if not reasons
            else ReviewOnlyReceiptSummaryStatus.BLOCKED
        ),
        receipt_summary_ready=not reasons,
        safe_receipt_summary_label=SAFE_RECEIPT_SUMMARY_LABEL,
        actual_receipt_handoff_executed=snapshot.actual_receipt_handoff_executed,
        raw_response_required=snapshot.raw_response_required,
        real_id_required=snapshot.real_id_required,
        broker_api_response_required=snapshot.broker_api_response_required,
        manual_broker_ui_check_recommended=(
            snapshot.manual_broker_ui_check_recommended
        ),
        blocked_reasons=reasons,
    )


def build_position_read_only_status(
    input_snapshot: PositionReadOnlyStatusInput | None = None,
) -> PositionReadOnlyStatusResult:
    snapshot = input_snapshot or PositionReadOnlyStatusInput()
    reasons = _position_blocked_reasons(snapshot)
    status = _position_status(snapshot, reasons)
    new_entry_allowed = (
        status is PositionReadOnlyStatus.NO_POSITION
        and snapshot.position_status_checked
        and not reasons
    )
    close_allowed = (
        status is PositionReadOnlyStatus.ONE_POSITION_OPEN
        and snapshot.open_position_count == 1
        and not reasons
    )
    return PositionReadOnlyStatusResult(
        position_status_checked=snapshot.position_status_checked,
        position_status=status,
        safe_position_status_label=SAFE_POSITION_STATUS_LABEL,
        open_position_count_safe=snapshot.open_position_count,
        max_open_positions=snapshot.max_open_positions,
        new_entry_allowed=new_entry_allowed,
        close_allowed=close_allowed,
        raw_position_id_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
        position_value_exposed=False,
        blocked_reasons=reasons,
    )


def build_close_route_foundation(
    input_snapshot: CloseRouteFoundationInput | None = None,
) -> CloseRouteFoundationResult:
    snapshot = input_snapshot or CloseRouteFoundationInput()
    reasons = _close_route_blocked_reasons(snapshot)
    return CloseRouteFoundationResult(
        status=(
            CloseRouteFoundationStatus.READY
            if not reasons
            else CloseRouteFoundationStatus.BLOCKED
        ),
        close_route_ready=not reasons,
        safe_close_route_label=SAFE_CLOSE_ROUTE_LABEL,
        close_post_executed=False,
        close_post_count=0,
        close_retry_allowed=False,
        close_second_post_allowed=False,
        close_requires_position_status=PositionReadOnlyStatus.ONE_POSITION_OPEN.value,
        close_blocks_if_position_unknown=True,
        close_blocks_if_no_position=True,
        close_blocks_if_multiple_positions=True,
        close_size_fixed=SUPPORTED_UNITS,
        close_symbol_matches_position=snapshot.close_symbol_matches_position,
        close_side_is_opposite=snapshot.close_side_is_opposite,
        raw_id_required=snapshot.raw_id_required,
        raw_response_required=snapshot.raw_response_required,
        broker_api_response_required=snapshot.broker_api_response_required,
        blocked_reasons=reasons,
    )


def evaluate_level5_signal_mvp(
    input_snapshot: Level5SignalMvpInput | None = None,
) -> Level5SignalMvpResult:
    snapshot = input_snapshot or Level5SignalMvpInput()
    blocked = _signal_blocked_reasons(snapshot)
    if blocked:
        return Level5SignalMvpResult(
            signal_checked=True,
            signal_type=Level5SignalType.BLOCKED,
            signal_source=(
                Level5SignalSource.MARKET_ADAPTER_MISSING
                if not snapshot.market_source_available
                else snapshot.signal_source
            ),
            signal_confidence_label=Level5SignalConfidenceLabel.BLOCKED,
            signal_reason_label=blocked[0],
            actual_market_raw_value_exposed=False,
            actual_market_value_exposed=False,
            raw_market_data_exposed=False,
            signal_direct_post_attempted=False,
            signal_directly_executes_post=False,
            retry_or_repost_attempted=False,
            blocked_reasons=blocked,
        )
    signal_type, reason = _signal_type_and_reason(snapshot)
    confidence = (
        Level5SignalConfidenceLabel.LOW
        if signal_type in {Level5SignalType.ENTRY_BUY, Level5SignalType.ENTRY_SELL}
        else Level5SignalConfidenceLabel.TEST_ONLY
    )
    return Level5SignalMvpResult(
        signal_checked=True,
        signal_type=signal_type,
        signal_source=snapshot.signal_source,
        signal_confidence_label=confidence,
        signal_reason_label=reason,
        actual_market_raw_value_exposed=False,
        actual_market_value_exposed=False,
        raw_market_data_exposed=False,
        signal_direct_post_attempted=False,
        signal_directly_executes_post=False,
        retry_or_repost_attempted=False,
        blocked_reasons=(),
    )


def build_level5_entry_planning_gate(
    input_snapshot: Level5EntryPlanningGateInput | None = None,
) -> Level5EntryPlanningGateResult:
    snapshot = input_snapshot or Level5EntryPlanningGateInput()
    reasons = _entry_planning_blocked_reasons(snapshot)
    side_label = _entry_side_safe_label(snapshot.signal_type)
    ready = not reasons
    return Level5EntryPlanningGateResult(
        entry_planning_gate_ready=ready,
        entry_planning_allowed=ready,
        entry_execution_allowed_now=False,
        entry_execution_step_may_be_planned=ready,
        entry_requires_new_confirmation=True,
        entry_requires_time_market_operator_gate=True,
        entry_execution_requires_position_status_current=True,
        entry_execution_requires_no_position=True,
        entry_execution_requires_no_retry=True,
        entry_execution_requires_no_second_post=True,
        entry_execution_requires_raw_id_exposure_false=True,
        entry_units_fixed=SUPPORTED_UNITS,
        entry_symbol_safe_label=SUPPORTED_SYMBOL,
        entry_order_type_safe_label="MARKET",
        entry_side_safe_label=side_label,
        entry_retry_allowed=False,
        entry_second_post_allowed=False,
        entry_raw_exposure=False,
        entry_id_exposure=False,
        actual_http_post_executed=False,
        close_post_executed=False,
        signal_directly_executes_post=False,
        credential_signature_headers_exposure=False,
        safe_entry_planning_label=SAFE_ENTRY_PLANNING_LABEL,
        blocked_reasons=reasons,
    )


def transition_level5_cycle_state(
    input_snapshot: Level5CycleTransitionInput | None = None,
) -> Level5CycleTransitionResult:
    snapshot = input_snapshot or Level5CycleTransitionInput()
    fail_reasons = _cycle_fail_reasons(snapshot)
    if fail_reasons or snapshot.current_state is Level5CycleState.HALTED:
        reasons = fail_reasons or ("halted_no_automatic_recovery",)
        return _cycle_result(snapshot, Level5CycleState.HALTED, reasons)
    if _second_entry_attempted(snapshot):
        return _cycle_result(snapshot, Level5CycleState.HALTED, ("second_entry_blocked",))

    next_state = snapshot.current_state
    reasons: tuple[str, ...] = ()
    if snapshot.current_state is Level5CycleState.IDLE:
        if snapshot.entry_signal:
            if snapshot.position_status is not PositionReadOnlyStatus.NO_POSITION:
                next_state = Level5CycleState.HALTED
                reasons = ("entry_requires_no_position",)
            elif snapshot.daily_limits_ok:
                next_state = Level5CycleState.ENTRY_READY
            else:
                next_state = Level5CycleState.HALTED
                reasons = ("daily_limits_not_ok",)
    elif snapshot.current_state is Level5CycleState.ENTRY_READY:
        if snapshot.entry_execution_gate_passed:
            next_state = Level5CycleState.ENTRY_SENT
    elif snapshot.current_state is Level5CycleState.ENTRY_SIGNAL:
        if snapshot.entry_execution_gate_passed:
            next_state = Level5CycleState.ENTRY_SENT
    elif snapshot.current_state is Level5CycleState.ENTRY_SENT:
        if snapshot.entry_accepted_sanitized:
            next_state = Level5CycleState.ENTRY_ACCEPTED_SANITIZED
    elif snapshot.current_state is Level5CycleState.ENTRY_ACCEPTED_SANITIZED:
        next_state = Level5CycleState.POSITION_CHECK_PENDING
    elif snapshot.current_state is Level5CycleState.POSITION_CHECK_PENDING:
        next_state, reasons = _position_check_next_state(snapshot.position_status)
    elif snapshot.current_state is Level5CycleState.UNKNOWN_RESULT_SAFE_STOP:
        if (
            snapshot.entry_unknown_no_position_closeout_confirmed
            and snapshot.position_status is PositionReadOnlyStatus.NO_POSITION
        ):
            next_state = Level5CycleState.ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT
        elif snapshot.entry_unknown_no_position_closeout_confirmed:
            next_state = Level5CycleState.HALTED
            reasons = ("closeout_requires_no_position",)
    elif snapshot.current_state is Level5CycleState.POSITION_OPEN_SAFE:
        if snapshot.exit_signal:
            next_state = Level5CycleState.EXIT_SIGNAL
    elif snapshot.current_state is Level5CycleState.EXIT_SIGNAL:
        if snapshot.position_status is PositionReadOnlyStatus.ONE_POSITION_OPEN:
            next_state = Level5CycleState.CLOSE_READY
        else:
            next_state = Level5CycleState.HALTED
            reasons = ("close_ready_requires_one_position",)
    elif snapshot.current_state is Level5CycleState.CLOSE_READY:
        if snapshot.close_execution_gate_passed:
            next_state = Level5CycleState.CLOSE_SENT
    elif snapshot.current_state is Level5CycleState.CLOSE_SENT:
        if snapshot.close_accepted_sanitized and snapshot.no_position_after_close:
            next_state = Level5CycleState.CLOSED_SAFE
        elif snapshot.close_accepted_sanitized:
            next_state = Level5CycleState.HALTED
            reasons = ("close_requires_no_position_after_close",)
    return _cycle_result(snapshot, next_state, reasons)


def build_level5_fast_mvp_foundation(
    *,
    config_input: Level5FastTrackConfigInput | None = None,
    ledger_input: SafeLedgerLikeRecordInput | None = None,
    receipt_input: ReviewOnlyReceiptSummaryInput | None = None,
    position_input: PositionReadOnlyStatusInput | None = None,
    position_controlled_result: PositionReadOnlyControlledResult | None = None,
    close_input: CloseRouteFoundationInput | None = None,
    close_order_route_input: CloseOrderRouteControlledInput | None = None,
    signal_input: Level5SignalMvpInput | None = None,
    cycle_input: Level5CycleTransitionInput | None = None,
) -> Level5FastMvpFoundationResult:
    config = build_level5_fast_track_config(config_input)
    ledger = build_safe_ledger_like_record(ledger_input)
    receipt = build_review_only_receipt_summary(receipt_input)
    connected_position_input = position_input or _position_input_from_controlled_route(
        position_controlled_result,
    )
    position = build_position_read_only_status(connected_position_input)
    close = build_close_route_foundation(
        close_input
        or CloseRouteFoundationInput(position_status=position.position_status),
    )
    close_order_route = build_close_order_route_controlled(
        close_order_route_input
        or _close_order_route_input_from_position(
            position,
            position_controlled_result,
        ),
    )
    signal = evaluate_level5_signal_mvp(
        signal_input
        or Level5SignalMvpInput(position_status=position.position_status),
    )
    entry_planning = build_level5_entry_planning_gate(
        Level5EntryPlanningGateInput(
            position_status=position.position_status,
            signal_checked=signal.signal_checked,
            signal_type=signal.signal_type,
            signal_directly_executes_post=signal.signal_directly_executes_post,
            retry_or_repost_attempted=signal.retry_or_repost_attempted,
            raw_exposure_attempted=(
                signal.actual_market_raw_value_exposed
                or signal.actual_market_value_exposed
                or signal.raw_market_data_exposed
            ),
        ),
    )
    cycle = transition_level5_cycle_state(
        cycle_input
        or Level5CycleTransitionInput(
            position_status=position.position_status,
            entry_signal=entry_planning.entry_planning_allowed,
        ),
    )
    blocked = _foundation_blocked_reasons(config, ledger, receipt, position, signal)
    return Level5FastMvpFoundationResult(
        status=Level5FastMvpStatus.READY if not blocked else Level5FastMvpStatus.BLOCKED,
        foundation_ready=not blocked,
        safe_level5_label=LEVEL5_FAST_MVP_LABEL,
        config=config,
        ledger_record=ledger,
        receipt_summary=receipt,
        position_status=position,
        close_route=close,
        close_order_route=close_order_route,
        signal=signal,
        entry_planning=entry_planning,
        cycle_transition=cycle,
        actual_http_post_executed=False,
        close_post_executed=False,
        retry_attempted=False,
        second_post_attempted=False,
        ledger_updated=False,
        receipt_handoff_executed=False,
        raw_id_value_exposure=False,
        credential_signature_headers_exposure=False,
        recommended_next_step="step6g_position_read_only_route_wiring_no_post",
        blocked_reasons=blocked,
    )


def render_level5_fast_mvp_foundation_markdown(
    result: Level5FastMvpFoundationResult,
) -> str:
    """Render a safe Level 5 foundation summary without raw/ID/value output."""
    lines = [
        "# Step 6G Level 5 Fast MVP Foundation",
        "",
        "This is a controlled foundation summary only.",
        "It does not execute actual POST or close POST.",
        "It does not retry, repost, or perform a second POST.",
        "It does not update ledgers or hand off actual receipts.",
        "It does not expose raw request/response, broker/API response, IDs,",
        "credential values, signature values, or headers values.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- foundation_ready: {_bool_text(result.foundation_ready)}",
        f"- safe_level5_label: {result.safe_level5_label}",
        f"- recommended_next_step: {result.recommended_next_step}",
        "",
        "## Config",
        f"- symbol: {result.config.symbol}",
        f"- units: {result.config.units}",
        f"- max_open_positions: {result.config.max_open_positions}",
        f"- retry_allowed: {_bool_text(result.config.retry_allowed)}",
        f"- second_post_allowed: {_bool_text(result.config.second_post_allowed)}",
        (
            "- human_monitoring_required: "
            f"{_bool_text(result.config.human_monitoring_required)}"
        ),
        f"- kill_switch_required: {_bool_text(result.config.kill_switch_required)}",
        "",
        "## Contracts",
        f"- safe_record_ready: {_bool_text(result.ledger_record.safe_record_ready)}",
        (
            "- receipt_summary_ready: "
            f"{_bool_text(result.receipt_summary.receipt_summary_ready)}"
        ),
        f"- position_status: {result.position_status.position_status.value}",
        f"- new_entry_allowed: {_bool_text(result.position_status.new_entry_allowed)}",
        f"- close_allowed: {_bool_text(result.position_status.close_allowed)}",
        f"- close_route_ready: {_bool_text(result.close_route.close_route_ready)}",
        (
            "- close_planning_allowed: "
            f"{_bool_text(result.close_order_route.close_planning_allowed)}"
        ),
        (
            "- close_execution_allowed_now: "
            f"{_bool_text(result.close_order_route.close_execution_allowed_now)}"
        ),
        f"- signal_type: {result.signal.signal_type.value}",
        (
            "- entry_planning_allowed: "
            f"{_bool_text(result.entry_planning.entry_planning_allowed)}"
        ),
        (
            "- entry_execution_allowed_now: "
            f"{_bool_text(result.entry_planning.entry_execution_allowed_now)}"
        ),
        f"- cycle_next_state: {result.cycle_transition.next_state.value}",
        "",
        "## Safety",
        f"- actual_http_post_executed: {_bool_text(result.actual_http_post_executed)}",
        f"- close_post_executed: {_bool_text(result.close_post_executed)}",
        f"- retry_attempted: {_bool_text(result.retry_attempted)}",
        f"- second_post_attempted: {_bool_text(result.second_post_attempted)}",
        f"- ledger_updated: {_bool_text(result.ledger_updated)}",
        f"- receipt_handoff_executed: {_bool_text(result.receipt_handoff_executed)}",
        f"- raw_id_value_exposure: {_bool_text(result.raw_id_value_exposure)}",
        (
            "- credential_signature_headers_exposure: "
            f"{_bool_text(result.credential_signature_headers_exposure)}"
        ),
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
    ]
    return "\n".join(lines) + "\n"


def _fast_config_blocked_reasons(
    snapshot: Level5FastTrackConfigInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.symbol != SUPPORTED_SYMBOL:
        reasons.append("unsupported_symbol")
    if snapshot.units != SUPPORTED_UNITS:
        reasons.append("units_must_be_100")
    if snapshot.max_open_positions != 1:
        reasons.append("max_open_positions_must_be_1")
    if snapshot.max_entry_orders_per_cycle != 1:
        reasons.append("max_entry_orders_per_cycle_must_be_1")
    if snapshot.max_close_orders_per_cycle != 1:
        reasons.append("max_close_orders_per_cycle_must_be_1")
    for flag_name in ("retry_allowed", "repost_allowed", "second_post_allowed"):
        if getattr(snapshot, flag_name):
            reasons.append(flag_name)
    for flag_name in (
        "human_monitoring_required",
        "operator_confirmation_required_for_actual_post",
        "time_market_gate_required",
        "kill_switch_required",
    ):
        if not getattr(snapshot, flag_name):
            reasons.append(f"{flag_name}_missing")
    return tuple(reasons)


def _ledger_blocked_reasons(snapshot: SafeLedgerLikeRecordInput) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.post_execution_count != 1:
        reasons.append("post_execution_count_not_1")
    if snapshot.sanitized_result_category != RESULT_ACCEPTED_SANITIZED:
        reasons.append("sanitized_result_not_accepted")
    if snapshot.safe_reconciliation_status != RECONCILIATION_READY_NO_RECEIPT_HANDOFF:
        reasons.append("reconciliation_not_ready")
    for flag_name in (
        "retry_attempted",
        "second_post_attempted",
        "ledger_updated",
        "receipt_handoff_executed",
    ):
        if getattr(snapshot, flag_name):
            reasons.append(flag_name)
    if _raw_id_value_exposed(snapshot):
        reasons.append("raw_id_value_exposure")
    if _credential_signature_headers_exposed(snapshot):
        reasons.append("credential_signature_headers_exposure")
    return tuple(reasons)


def _receipt_blocked_reasons(
    snapshot: ReviewOnlyReceiptSummaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.sanitized_result_category != RESULT_ACCEPTED_SANITIZED:
        reasons.append("sanitized_result_not_accepted")
    if snapshot.post_execution_count != 1:
        reasons.append("post_execution_count_not_1")
    for flag_name in (
        "retry_attempted",
        "second_post_attempted",
        "actual_receipt_handoff_executed",
        "raw_response_required",
        "real_id_required",
        "broker_api_response_required",
    ):
        if getattr(snapshot, flag_name):
            reasons.append(flag_name)
    if not snapshot.manual_broker_ui_check_recommended:
        reasons.append("manual_broker_ui_check_not_recommended")
    return tuple(reasons)


def _position_blocked_reasons(
    snapshot: PositionReadOnlyStatusInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.max_open_positions != 1:
        reasons.append("max_open_positions_must_be_1")
    if _position_exposure(snapshot):
        reasons.append("position_raw_id_value_exposure")
    if snapshot.open_position_count > 1:
        reasons.append("multiple_positions_blocked")
    return tuple(reasons)


def _position_status(
    snapshot: PositionReadOnlyStatusInput,
    reasons: tuple[str, ...],
) -> PositionReadOnlyStatus:
    if reasons:
        return PositionReadOnlyStatus.BLOCKED
    if not snapshot.position_status_checked or snapshot.position_status_unknown:
        return PositionReadOnlyStatus.UNKNOWN
    if snapshot.open_position_count == 0:
        return PositionReadOnlyStatus.NO_POSITION
    if snapshot.open_position_count == 1:
        return PositionReadOnlyStatus.ONE_POSITION_OPEN
    return PositionReadOnlyStatus.BLOCKED


def _close_route_blocked_reasons(
    snapshot: CloseRouteFoundationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.position_status is PositionReadOnlyStatus.UNKNOWN:
        reasons.append("position_unknown")
    elif snapshot.position_status is PositionReadOnlyStatus.NO_POSITION:
        reasons.append("no_position")
    elif snapshot.position_status is PositionReadOnlyStatus.BLOCKED:
        reasons.append("position_blocked_or_multiple")
    if snapshot.close_size != SUPPORTED_UNITS:
        reasons.append("close_size_must_be_100")
    if not snapshot.close_symbol_matches_position:
        reasons.append("close_symbol_mismatch")
    if not snapshot.close_side_is_opposite:
        reasons.append("close_side_not_opposite")
    if snapshot.close_post_executed or snapshot.close_post_count:
        reasons.append("close_post_attempted")
    if snapshot.close_retry_allowed:
        reasons.append("close_retry_allowed")
    if snapshot.close_second_post_allowed:
        reasons.append("close_second_post_allowed")
    for flag_name in (
        "raw_id_required",
        "raw_response_required",
        "broker_api_response_required",
        "credential_signature_headers_required",
    ):
        if getattr(snapshot, flag_name):
            reasons.append(flag_name)
    return tuple(reasons)


def _signal_blocked_reasons(snapshot: Level5SignalMvpInput) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.market_source_available:
        reasons.append("market_adapter_missing")
    if snapshot.position_status is not PositionReadOnlyStatus.NO_POSITION and (
        snapshot.trend_label
        in {Level5TrendLabel.UPTREND, Level5TrendLabel.DOWNTREND}
    ):
        reasons.append("entry_requires_no_position")
    if snapshot.position_status in {PositionReadOnlyStatus.UNKNOWN, PositionReadOnlyStatus.BLOCKED}:
        reasons.append("position_status_not_safe")
    if (
        not snapshot.safe_config_allows_entry
        and snapshot.position_status is PositionReadOnlyStatus.NO_POSITION
    ):
        reasons.append("safe_config_blocks_entry")
    if snapshot.actual_market_raw_value_exposed:
        reasons.append("actual_market_raw_value_exposed")
    if snapshot.actual_market_value_exposed:
        reasons.append("actual_market_value_exposed")
    if snapshot.raw_market_data_exposed:
        reasons.append("raw_market_data_exposed")
    if snapshot.spread_label is not Level5SpreadLabel.NORMAL:
        reasons.append("spread_not_normal")
    if snapshot.time_market_label is not Level5TimeMarketLabel.OK:
        reasons.append("time_market_not_ok")
    if snapshot.volatility_label is not Level5VolatilityLabel.NORMAL:
        reasons.append("volatility_not_normal")
    if snapshot.trend_label is Level5TrendLabel.UNKNOWN:
        reasons.append("trend_unknown")
    if snapshot.signal_direct_post_attempted:
        reasons.append("signal_direct_post_attempted")
    if snapshot.signal_directly_executes_post:
        reasons.append("signal_directly_executes_post")
    if snapshot.retry_or_repost_attempted:
        reasons.append("retry_or_repost_attempted")
    return tuple(reasons)


def _signal_type_and_reason(
    snapshot: Level5SignalMvpInput,
) -> tuple[Level5SignalType, str]:
    if (
        snapshot.position_status is PositionReadOnlyStatus.ONE_POSITION_OPEN
        and snapshot.exit_reason_label
        in {
            Level5ExitReasonLabel.TAKE_PROFIT,
            Level5ExitReasonLabel.STOP_LOSS,
            Level5ExitReasonLabel.MAX_HOLD_TIME,
        }
    ):
        return Level5SignalType.EXIT, f"exit_{snapshot.exit_reason_label.value.lower()}"
    if snapshot.position_status is PositionReadOnlyStatus.NO_POSITION:
        if snapshot.trend_label is Level5TrendLabel.UPTREND:
            return Level5SignalType.ENTRY_BUY, "rule_mvp_uptrend_normal_ok"
        if snapshot.trend_label is Level5TrendLabel.DOWNTREND:
            return Level5SignalType.ENTRY_SELL, "rule_mvp_downtrend_normal_ok"
        if snapshot.trend_label is Level5TrendLabel.FLAT:
            return Level5SignalType.HOLD, "rule_mvp_flat_hold"
    return Level5SignalType.HOLD, "rule_mvp_hold"


def _entry_planning_blocked_reasons(
    snapshot: Level5EntryPlanningGateInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.signal_checked:
        reasons.append("signal_missing")
    if snapshot.position_status is not PositionReadOnlyStatus.NO_POSITION:
        reasons.append("entry_requires_no_position")
    if snapshot.signal_type not in {
        Level5SignalType.ENTRY_BUY,
        Level5SignalType.ENTRY_SELL,
    }:
        reasons.append("entry_signal_required")
    if snapshot.entry_symbol_safe_label != SUPPORTED_SYMBOL:
        reasons.append("entry_symbol_must_be_usd_jpy")
    if snapshot.entry_units_fixed != SUPPORTED_UNITS:
        reasons.append("entry_units_must_be_100")
    if snapshot.entry_order_type_safe_label != "MARKET":
        reasons.append("entry_order_type_must_be_market")
    for flag_name in (
        "signal_directly_executes_post",
        "actual_http_post_attempted",
        "close_post_attempted",
        "retry_or_repost_attempted",
        "second_post_attempted",
        "raw_exposure_attempted",
        "id_exposure_attempted",
        "credential_signature_headers_exposure_attempted",
    ):
        if getattr(snapshot, flag_name):
            reasons.append(flag_name)
    return tuple(reasons)


def _entry_side_safe_label(signal_type: Level5SignalType) -> str:
    if signal_type is Level5SignalType.ENTRY_BUY:
        return "BUY"
    if signal_type is Level5SignalType.ENTRY_SELL:
        return "SELL"
    return "NOT_APPLICABLE"


def _cycle_fail_reasons(snapshot: Level5CycleTransitionInput) -> tuple[str, ...]:
    reasons: list[str] = []
    for flag_name in (
        "retry_attempted",
        "second_post_attempted",
        "timeout",
        "unknown",
        "unavailable",
    ):
        if getattr(snapshot, flag_name):
            reasons.append(flag_name)
    return tuple(reasons)


def _second_entry_attempted(snapshot: Level5CycleTransitionInput) -> bool:
    return snapshot.entry_signal and snapshot.current_state not in {
        Level5CycleState.IDLE,
        Level5CycleState.HALTED,
    }


def _position_check_next_state(
    position_status: PositionReadOnlyStatus,
) -> tuple[Level5CycleState, tuple[str, ...]]:
    if position_status is PositionReadOnlyStatus.ONE_POSITION_OPEN:
        return Level5CycleState.POSITION_OPEN_SAFE, ()
    if position_status is PositionReadOnlyStatus.UNKNOWN:
        return Level5CycleState.HALTED, ("position_unknown",)
    if position_status is PositionReadOnlyStatus.NO_POSITION:
        return Level5CycleState.HALTED, ("position_missing_after_entry",)
    return Level5CycleState.HALTED, ("position_blocked",)


def _position_input_from_controlled_route(
    result: PositionReadOnlyControlledResult | None,
) -> PositionReadOnlyStatusInput | None:
    if result is None:
        return None
    if result.position_status is PositionReadOnlyControlledStatus.NO_POSITION:
        return PositionReadOnlyStatusInput(
            position_status_checked=result.position_status_checked,
            open_position_count=0,
            position_status_unknown=False,
            position_source_available=True,
            max_open_positions=result.max_open_positions,
        )
    if result.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        return PositionReadOnlyStatusInput(
            position_status_checked=result.position_status_checked,
            open_position_count=1,
            position_status_unknown=False,
            position_source_available=True,
            max_open_positions=result.max_open_positions,
        )
    if result.position_status is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED:
        return PositionReadOnlyStatusInput(
            position_status_checked=True,
            open_position_count=max(2, result.position_count_safe),
            position_status_unknown=False,
            position_source_available=True,
            max_open_positions=result.max_open_positions,
        )
    return PositionReadOnlyStatusInput(
        position_status_checked=False,
        open_position_count=result.position_count_safe,
        position_status_unknown=True,
        position_source_available=False,
        max_open_positions=result.max_open_positions,
    )


def _close_order_route_input_from_position(
    position: PositionReadOnlyStatusResult,
    controlled_result: PositionReadOnlyControlledResult | None,
) -> CloseOrderRouteControlledInput:
    if controlled_result is not None:
        return CloseOrderRouteControlledInput(
            position_status=controlled_result.position_status,
            position_status_checked=controlled_result.position_status_checked,
            position_count_safe=controlled_result.position_count_safe,
            max_open_positions=controlled_result.max_open_positions,
            raw_position_exposure_attempted=controlled_result.raw_position_exposed,
            broker_api_response_exposure_attempted=(
                controlled_result.broker_api_response_exposed
            ),
            position_id_exposure_attempted=controlled_result.position_id_exposed,
            account_id_exposure_attempted=controlled_result.account_id_exposed,
            order_id_exposure_attempted=controlled_result.order_id_exposed,
            transaction_id_exposure_attempted=(
                controlled_result.transaction_id_exposed
            ),
            credential_value_exposure_attempted=(
                controlled_result.credential_value_exposed
            ),
            signature_value_exposure_attempted=(
                controlled_result.signature_value_exposed
            ),
            headers_value_exposure_attempted=controlled_result.headers_value_exposed,
            actual_http_post_attempted=controlled_result.actual_http_post_executed,
            close_post_attempted=controlled_result.close_post_executed,
            retry_or_repost_attempted=controlled_result.retry_attempted,
            ledger_update_attempted=controlled_result.ledger_updated,
            receipt_handoff_attempted=controlled_result.receipt_handoff_executed,
        )
    if position.position_status is PositionReadOnlyStatus.NO_POSITION:
        controlled_status = PositionReadOnlyControlledStatus.NO_POSITION
    elif position.position_status is PositionReadOnlyStatus.ONE_POSITION_OPEN:
        controlled_status = PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    elif position.position_status is PositionReadOnlyStatus.BLOCKED:
        controlled_status = PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    else:
        controlled_status = PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    return CloseOrderRouteControlledInput(
        position_status=controlled_status,
        position_status_checked=position.position_status_checked,
        position_count_safe=position.open_position_count_safe,
        max_open_positions=position.max_open_positions,
        raw_position_exposure_attempted=position.raw_position_id_exposed,
        position_id_exposure_attempted=position.raw_position_id_exposed,
        account_id_exposure_attempted=position.account_id_exposed,
        order_id_exposure_attempted=position.order_id_exposed,
        transaction_id_exposure_attempted=position.transaction_id_exposed,
        position_value_exposure_attempted=position.position_value_exposed,
    )


def _cycle_result(
    snapshot: Level5CycleTransitionInput,
    next_state: Level5CycleState,
    reasons: tuple[str, ...],
) -> Level5CycleTransitionResult:
    return Level5CycleTransitionResult(
        safe_cycle_state_label=SAFE_CYCLE_STATE_LABEL,
        previous_state=snapshot.current_state,
        next_state=next_state,
        halted=next_state is Level5CycleState.HALTED,
        retry_allowed=False,
        second_post_allowed=False,
        automatic_recovery_allowed=False,
        blocked_reasons=reasons,
    )


def _foundation_blocked_reasons(
    config: Level5FastTrackConfigResult,
    ledger: SafeLedgerLikeRecordResult,
    receipt: ReviewOnlyReceiptSummaryResult,
    position: PositionReadOnlyStatusResult,
    signal: Level5SignalMvpResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not config.config_ready:
        reasons.append("config_not_ready")
    if not ledger.safe_record_ready:
        reasons.append("ledger_record_not_ready")
    if not receipt.receipt_summary_ready:
        reasons.append("receipt_summary_not_ready")
    if position.raw_position_id_exposed or position.position_value_exposed:
        reasons.append("position_exposure")
    if signal.signal_direct_post_attempted:
        reasons.append("signal_direct_post_attempted")
    return tuple(reasons)


def _raw_id_value_exposed(snapshot: SafeLedgerLikeRecordInput) -> bool:
    return (
        snapshot.raw_request_exposed
        or snapshot.raw_response_exposed
        or snapshot.broker_api_response_exposed
        or snapshot.real_id_exposed
    )


def _credential_signature_headers_exposed(snapshot: SafeLedgerLikeRecordInput) -> bool:
    return (
        snapshot.credential_value_exposed
        or snapshot.signature_value_exposed
        or snapshot.headers_value_exposed
    )


def _position_exposure(snapshot: PositionReadOnlyStatusInput) -> bool:
    return (
        snapshot.raw_position_id_exposed
        or snapshot.account_id_exposed
        or snapshot.order_id_exposed
        or snapshot.transaction_id_exposed
        or snapshot.position_value_exposed
    )


def _validate_non_negative_int(name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{name} must be a non-negative int")


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{name} must be non-empty")


def _validate_bool_fields(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        if type(getattr(instance, name)) is not bool:
            raise LiveVerificationValidationError(f"{name} must be bool")


def _validate_blocked_reasons(reasons: tuple[str, ...]) -> None:
    if not isinstance(reasons, tuple):
        raise LiveVerificationValidationError("blocked_reasons must be tuple")
    for reason in reasons:
        _require_non_empty("blocked_reason", reason)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


_FAST_CONFIG_BOOL_FIELDS = (
    "retry_allowed",
    "repost_allowed",
    "second_post_allowed",
    "human_monitoring_required",
    "operator_confirmation_required_for_actual_post",
    "time_market_gate_required",
    "kill_switch_required",
)

_FAST_CONFIG_RESULT_BOOL_FIELDS = ("config_ready",) + _FAST_CONFIG_BOOL_FIELDS

_LEDGER_INPUT_BOOL_FIELDS = (
    "retry_attempted",
    "second_post_attempted",
    "ledger_updated",
    "receipt_handoff_executed",
    "raw_request_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
    "real_id_exposed",
)

_LEDGER_RESULT_BOOL_FIELDS = (
    "safe_record_ready",
    "retry_attempted",
    "second_post_attempted",
    "ledger_updated_before_real_ledger_step",
    "receipt_handoff_executed",
    "production_ledger_written",
    "raw_id_value_exposure",
    "credential_signature_headers_exposure",
)

_RECEIPT_INPUT_BOOL_FIELDS = (
    "retry_attempted",
    "second_post_attempted",
    "actual_receipt_handoff_executed",
    "raw_response_required",
    "real_id_required",
    "broker_api_response_required",
    "manual_broker_ui_check_recommended",
)

_RECEIPT_RESULT_BOOL_FIELDS = (
    "receipt_summary_ready",
    "actual_receipt_handoff_executed",
    "raw_response_required",
    "real_id_required",
    "broker_api_response_required",
    "manual_broker_ui_check_recommended",
)

_POSITION_INPUT_BOOL_FIELDS = (
    "position_status_checked",
    "position_status_unknown",
    "position_source_available",
    "raw_position_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
    "position_value_exposed",
)

_POSITION_RESULT_BOOL_FIELDS = (
    "position_status_checked",
    "new_entry_allowed",
    "close_allowed",
    "raw_position_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
    "position_value_exposed",
)

_CLOSE_INPUT_BOOL_FIELDS = (
    "close_symbol_matches_position",
    "close_side_is_opposite",
    "close_post_executed",
    "close_retry_allowed",
    "close_second_post_allowed",
    "raw_id_required",
    "raw_response_required",
    "broker_api_response_required",
    "credential_signature_headers_required",
)

_CLOSE_RESULT_BOOL_FIELDS = (
    "close_route_ready",
    "close_post_executed",
    "close_retry_allowed",
    "close_second_post_allowed",
    "close_blocks_if_position_unknown",
    "close_blocks_if_no_position",
    "close_blocks_if_multiple_positions",
    "close_symbol_matches_position",
    "close_side_is_opposite",
    "raw_id_required",
    "raw_response_required",
    "broker_api_response_required",
)

_SIGNAL_INPUT_BOOL_FIELDS = (
    "market_source_available",
    "safe_config_allows_entry",
    "actual_market_raw_value_exposed",
    "actual_market_value_exposed",
    "raw_market_data_exposed",
    "signal_direct_post_attempted",
    "signal_directly_executes_post",
    "retry_or_repost_attempted",
)

_SIGNAL_RESULT_BOOL_FIELDS = (
    "signal_checked",
    "actual_market_raw_value_exposed",
    "actual_market_value_exposed",
    "raw_market_data_exposed",
    "signal_direct_post_attempted",
    "signal_directly_executes_post",
    "retry_or_repost_attempted",
)

_ENTRY_PLANNING_INPUT_BOOL_FIELDS = (
    "signal_checked",
    "signal_directly_executes_post",
    "actual_http_post_attempted",
    "close_post_attempted",
    "retry_or_repost_attempted",
    "second_post_attempted",
    "raw_exposure_attempted",
    "id_exposure_attempted",
    "credential_signature_headers_exposure_attempted",
)

_ENTRY_PLANNING_RESULT_BOOL_FIELDS = (
    "entry_planning_gate_ready",
    "entry_planning_allowed",
    "entry_execution_allowed_now",
    "entry_execution_step_may_be_planned",
    "entry_requires_new_confirmation",
    "entry_requires_time_market_operator_gate",
    "entry_execution_requires_position_status_current",
    "entry_execution_requires_no_position",
    "entry_execution_requires_no_retry",
    "entry_execution_requires_no_second_post",
    "entry_execution_requires_raw_id_exposure_false",
    "entry_retry_allowed",
    "entry_second_post_allowed",
    "entry_raw_exposure",
    "entry_id_exposure",
    "actual_http_post_executed",
    "close_post_executed",
    "signal_directly_executes_post",
    "credential_signature_headers_exposure",
)

_CYCLE_INPUT_BOOL_FIELDS = (
    "entry_signal",
    "entry_execution_gate_passed",
    "entry_accepted_sanitized",
    "exit_signal",
    "close_execution_gate_passed",
    "close_accepted_sanitized",
    "no_position_after_close",
    "entry_unknown_no_position_closeout_confirmed",
    "daily_limits_ok",
    "retry_attempted",
    "second_post_attempted",
    "timeout",
    "unknown",
    "unavailable",
)

_CYCLE_RESULT_BOOL_FIELDS = (
    "halted",
    "retry_allowed",
    "second_post_allowed",
    "automatic_recovery_allowed",
)

_FOUNDATION_RESULT_BOOL_FIELDS = (
    "foundation_ready",
    "actual_http_post_executed",
    "close_post_executed",
    "retry_attempted",
    "second_post_attempted",
    "ledger_updated",
    "receipt_handoff_executed",
    "raw_id_value_exposure",
    "credential_signature_headers_exposure",
)
