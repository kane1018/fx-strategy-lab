"""Step 6G manual flatten runtime flat reconciliation gate.

This module records operator manual flatten reconciliation with safe
status/count fields only. It does not execute entry POST, close POST, retry,
repost, ledger updates, receipt handoff, broker/private API calls, env reads,
or raw ID/value handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_close_order_execution_route_controlled import (
    OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_position_runtime_safe_read_controlled import (
    PositionRuntimeSafeReadControlledResult,
)

MANUAL_FLATTEN_RUNTIME_FLAT_RECONCILIATION_LABEL = (
    "STEP6G_MANUAL_FLATTEN_RUNTIME_FLAT_RECONCILIATION_CONTROLLED"
)
NEXT_STEP_GMO_OFFICIAL_SETTLEMENT_ROUTE_REVIEW = (
    "Step 6G-PC-OX-R-GMO-OFFICIAL-SETTLEMENT-ROUTE-REVIEW-C"
)
NEXT_STEP_MANUAL_POSITION_RISK_STILL_REMAINING = (
    "Step 6G-PC-OX-R-MANUAL-FLATTEN-POSITION-RISK-STILL-REMAINING-C"
)
NEXT_STEP_OPERATOR_MANUAL_FLATTEN_CONFIRMATION_RETRY = (
    "Step 6G-PC-OX-R-OPERATOR-MANUAL-FLATTEN-CONFIRMATION-RETRY-C"
)
NEXT_STEP_MANUAL_FLATTEN_UNKNOWN_SAFE_STOP = (
    "Step 6G-PC-OX-R-MANUAL-FLATTEN-RUNTIME-UNKNOWN-SAFE-STOP-C"
)


class ManualFlattenRuntimeFlatReconciliationCase(str, Enum):
    CASE_1 = "CASE 1"
    CASE_2 = "CASE 2"
    CASE_3 = "CASE 3"
    CASE_4 = "CASE 4"


class ManualFlattenRuntimeFlatReconciliationStatus(str, Enum):
    MANUAL_FLATTEN_RECONCILED = "MANUAL_FLATTEN_RECONCILED"
    POSITION_RISK_REMAINING = "POSITION_RISK_REMAINING"
    RUNTIME_FLAT_OPERATOR_CONFIRMATION_INCOMPLETE = (
        "RUNTIME_FLAT_OPERATOR_CONFIRMATION_INCOMPLETE"
    )
    UNKNOWN_FAIL_CLOSED = "UNKNOWN_FAIL_CLOSED"
    UNSAFE_EXPOSURE_BLOCKED = "UNSAFE_EXPOSURE_BLOCKED"


@dataclass(frozen=True)
class OperatorManualFlattenSafeBooleanInput:
    operator_manual_flatten_completed: bool = False
    operator_broker_ui_checked: bool = False
    operator_broker_ui_open_position_visible: bool = True
    operator_broker_ui_buy_position_visible: bool = True
    operator_broker_ui_sell_position_visible: bool = True
    operator_broker_ui_values_or_ids_provided: bool = False
    operator_can_monitor: bool = False

    def __post_init__(self) -> None:
        _validate_bool_fields(self, _OPERATOR_BOOL_FIELDS)


@dataclass(frozen=True)
class ManualFlattenRuntimeFlatReconciliationInput:
    operator: OperatorManualFlattenSafeBooleanInput = field(
        default_factory=OperatorManualFlattenSafeBooleanInput,
    )
    official_manual_url_recorded: bool = True
    official_trading_rules_url_recorded: bool = True
    official_gmo_rules_alignment_checked: bool = True
    generic_opposite_order_as_close_forbidden: bool = True
    generic_close_primitive_revoked: bool = True
    official_settlement_route_confirmed: bool = False
    actual_entry_post_attempted_this_step: bool = False
    actual_close_post_attempted_this_step: bool = False
    close_retry_attempted_this_step: bool = False
    close_repost_attempted_this_step: bool = False
    second_close_post_attempted_this_step: bool = False
    order_endpoint_called_this_step: bool = False
    live_order_once_called_this_step: bool = False
    ledger_update_attempted_this_step: bool = False
    receipt_handoff_attempted_this_step: bool = False
    raw_request_exposure_attempted_this_step: bool = False
    raw_response_exposure_attempted_this_step: bool = False
    broker_api_response_exposure_attempted_this_step: bool = False
    credential_value_exposure_attempted_this_step: bool = False
    signature_value_exposure_attempted_this_step: bool = False
    headers_value_exposure_attempted_this_step: bool = False
    real_id_exposure_attempted_this_step: bool = False
    account_id_exposure_attempted_this_step: bool = False
    order_id_exposure_attempted_this_step: bool = False
    transaction_id_exposure_attempted_this_step: bool = False
    position_id_exposure_attempted_this_step: bool = False
    actual_price_value_exposure_attempted_this_step: bool = False
    actual_pnl_value_exposure_attempted_this_step: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.operator, OperatorManualFlattenSafeBooleanInput):
            raise LiveVerificationValidationError(
                "operator must be OperatorManualFlattenSafeBooleanInput",
            )
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class ManualFlattenRuntimeFlatReconciliationResult:
    gate_label: str
    case: ManualFlattenRuntimeFlatReconciliationCase
    reconciliation_status: ManualFlattenRuntimeFlatReconciliationStatus
    operator_manual_flatten_completed: bool
    operator_broker_ui_checked: bool
    operator_broker_ui_open_position_visible: bool
    operator_broker_ui_buy_position_visible: bool
    operator_broker_ui_sell_position_visible: bool
    operator_broker_ui_values_or_ids_provided: bool
    operator_can_monitor: bool
    credential_presence_available: bool
    runtime_read_executed: bool
    position_status: PositionReadOnlyControlledStatus
    position_count_safe: int
    has_open_position: bool
    has_exactly_one_position: bool
    has_multiple_positions: bool
    manual_flatten_reconciled: bool
    runtime_flat: bool
    position_risk_remaining: bool
    next_cycle_state: str
    level5_minimal_cycle_completed: bool
    level5_full_auto_cycle_completed: bool
    fresh_cycle_allowed: bool
    official_settlement_route_required: bool
    official_manual_url_recorded: bool
    official_trading_rules_url_recorded: bool
    official_gmo_rules_alignment_checked: bool
    generic_opposite_order_as_close_forbidden: bool
    generic_close_primitive_revoked: bool
    official_settlement_route_confirmed: bool
    actual_entry_post_allowed_now: bool
    actual_close_post_allowed_now: bool
    retry_allowed: bool
    repost_allowed: bool
    second_close_allowed: bool
    ledger_update_allowed: bool
    receipt_handoff_allowed: bool
    actual_entry_post_executed_this_step: bool
    actual_close_post_executed_this_step: bool
    close_retry_attempted: bool
    close_repost_attempted: bool
    second_close_post_attempted: bool
    ledger_updated: bool
    receipt_handoff_executed: bool
    raw_position_exposed: bool
    raw_request_exposed: bool
    raw_response_exposed: bool
    broker_api_response_exposed: bool
    position_id_exposed: bool
    account_id_exposed: bool
    order_id_exposed: bool
    transaction_id_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool
    close_execution_blocked_reason: str
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("gate_label", self.gate_label)
        if not isinstance(self.case, ManualFlattenRuntimeFlatReconciliationCase):
            raise LiveVerificationValidationError("case must be manual flatten enum")
        if not isinstance(
            self.reconciliation_status,
            ManualFlattenRuntimeFlatReconciliationStatus,
        ):
            raise LiveVerificationValidationError(
                "reconciliation_status must be manual flatten enum",
            )
        if not isinstance(self.position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "position_status must be controlled enum",
            )
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _require_non_empty("next_cycle_state", self.next_cycle_state)
        _require_non_empty(
            "close_execution_blocked_reason",
            self.close_execution_blocked_reason,
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_manual_flatten_runtime_flat_reconciliation_controlled(
    runtime_result: PositionRuntimeSafeReadControlledResult,
    input_snapshot: ManualFlattenRuntimeFlatReconciliationInput | None = None,
) -> ManualFlattenRuntimeFlatReconciliationResult:
    snapshot = input_snapshot or ManualFlattenRuntimeFlatReconciliationInput()
    current_reasons = _current_step_blocked_reasons(snapshot)
    operator_ready = _operator_manual_flatten_ready(snapshot.operator)
    runtime_flat = (
        runtime_result.position_status is PositionReadOnlyControlledStatus.NO_POSITION
        and runtime_result.position_count_safe == 0
    )
    position_risk_remaining = runtime_result.position_status in {
        PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED,
    }
    case, status, next_state, next_step = _case_status_and_next_step(
        operator_ready=operator_ready,
        runtime_flat=runtime_flat,
        position_risk_remaining=position_risk_remaining,
        current_reasons=current_reasons,
    )
    manual_reconciled = (
        case is ManualFlattenRuntimeFlatReconciliationCase.CASE_1
        and operator_ready
        and runtime_flat
        and not current_reasons
    )
    blocked_reasons = tuple(
        dict.fromkeys(
            (
                *current_reasons,
                *runtime_result.blocked_reasons,
                *_operator_blocked_reasons(snapshot.operator),
                *_official_alignment_blocked_reasons(snapshot),
            ),
        ),
    )
    return ManualFlattenRuntimeFlatReconciliationResult(
        gate_label=MANUAL_FLATTEN_RUNTIME_FLAT_RECONCILIATION_LABEL,
        case=case,
        reconciliation_status=status,
        operator_manual_flatten_completed=(
            snapshot.operator.operator_manual_flatten_completed
        ),
        operator_broker_ui_checked=snapshot.operator.operator_broker_ui_checked,
        operator_broker_ui_open_position_visible=(
            snapshot.operator.operator_broker_ui_open_position_visible
        ),
        operator_broker_ui_buy_position_visible=(
            snapshot.operator.operator_broker_ui_buy_position_visible
        ),
        operator_broker_ui_sell_position_visible=(
            snapshot.operator.operator_broker_ui_sell_position_visible
        ),
        operator_broker_ui_values_or_ids_provided=(
            snapshot.operator.operator_broker_ui_values_or_ids_provided
        ),
        operator_can_monitor=snapshot.operator.operator_can_monitor,
        credential_presence_available=runtime_result.credential_presence_available,
        runtime_read_executed=runtime_result.runtime_read_executed,
        position_status=runtime_result.position_status,
        position_count_safe=runtime_result.position_count_safe,
        has_open_position=runtime_result.has_open_position,
        has_exactly_one_position=runtime_result.has_exactly_one_position,
        has_multiple_positions=runtime_result.has_multiple_positions,
        manual_flatten_reconciled=manual_reconciled,
        runtime_flat=runtime_flat,
        position_risk_remaining=position_risk_remaining and not runtime_flat,
        next_cycle_state=next_state,
        level5_minimal_cycle_completed=False,
        level5_full_auto_cycle_completed=False,
        fresh_cycle_allowed=False,
        official_settlement_route_required=True,
        official_manual_url_recorded=snapshot.official_manual_url_recorded,
        official_trading_rules_url_recorded=(
            snapshot.official_trading_rules_url_recorded
        ),
        official_gmo_rules_alignment_checked=(
            snapshot.official_gmo_rules_alignment_checked
        ),
        generic_opposite_order_as_close_forbidden=(
            snapshot.generic_opposite_order_as_close_forbidden
        ),
        generic_close_primitive_revoked=snapshot.generic_close_primitive_revoked,
        official_settlement_route_confirmed=snapshot.official_settlement_route_confirmed,
        actual_entry_post_allowed_now=False,
        actual_close_post_allowed_now=False,
        retry_allowed=False,
        repost_allowed=False,
        second_close_allowed=False,
        ledger_update_allowed=False,
        receipt_handoff_allowed=False,
        actual_entry_post_executed_this_step=False,
        actual_close_post_executed_this_step=False,
        close_retry_attempted=False,
        close_repost_attempted=False,
        second_close_post_attempted=False,
        ledger_updated=False,
        receipt_handoff_executed=False,
        raw_position_exposed=False,
        raw_request_exposed=False,
        raw_response_exposed=False,
        broker_api_response_exposed=False,
        position_id_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
        close_execution_blocked_reason=OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED,
        recommended_next_step=next_step,
        blocked_reasons=blocked_reasons,
    )


def render_manual_flatten_runtime_flat_reconciliation_markdown(
    result: ManualFlattenRuntimeFlatReconciliationResult,
) -> str:
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Manual Flatten Runtime Flat Reconciliation",
            "",
            "This gate records manual flatten reconciliation with safe status/count only.",
            "It does not execute entry POST, close POST, retry, repost, ledger,",
            "receipt handoff, or raw/ID/value handling.",
            "",
            f"case: {result.case.value}",
            f"reconciliation_status: {result.reconciliation_status.value}",
            (
                "operator_manual_flatten_completed: "
                f"{_bool_text(result.operator_manual_flatten_completed)}"
            ),
            (
                "operator_broker_ui_open_position_visible: "
                f"{_bool_text(result.operator_broker_ui_open_position_visible)}"
            ),
            f"runtime_read_executed: {_bool_text(result.runtime_read_executed)}",
            f"position_status: {result.position_status.value}",
            f"position_count_safe: {result.position_count_safe}",
            (
                "manual_flatten_reconciled: "
                f"{_bool_text(result.manual_flatten_reconciled)}"
            ),
            f"runtime_flat: {_bool_text(result.runtime_flat)}",
            (
                "position_risk_remaining: "
                f"{_bool_text(result.position_risk_remaining)}"
            ),
            (
                "level5_minimal_cycle_completed: "
                f"{_bool_text(result.level5_minimal_cycle_completed)}"
            ),
            f"fresh_cycle_allowed: {_bool_text(result.fresh_cycle_allowed)}",
            (
                "official_settlement_route_required: "
                f"{_bool_text(result.official_settlement_route_required)}"
            ),
            (
                "generic_opposite_order_as_close_forbidden: "
                f"{_bool_text(result.generic_opposite_order_as_close_forbidden)}"
            ),
            (
                "generic_close_primitive_revoked: "
                f"{_bool_text(result.generic_close_primitive_revoked)}"
            ),
            (
                "actual_close_post_allowed_now: "
                f"{_bool_text(result.actual_close_post_allowed_now)}"
            ),
            f"raw_position_exposed: {_bool_text(result.raw_position_exposed)}",
            f"position_id_exposed: {_bool_text(result.position_id_exposed)}",
            f"account_id_exposed: {_bool_text(result.account_id_exposed)}",
            f"order_id_exposed: {_bool_text(result.order_id_exposed)}",
            f"transaction_id_exposed: {_bool_text(result.transaction_id_exposed)}",
            (
                "broker_api_response_exposed: "
                f"{_bool_text(result.broker_api_response_exposed)}"
            ),
            f"credential_value_exposed: {_bool_text(result.credential_value_exposed)}",
            f"signature_value_exposed: {_bool_text(result.signature_value_exposed)}",
            f"headers_value_exposed: {_bool_text(result.headers_value_exposed)}",
            f"close_execution_blocked_reason: {result.close_execution_blocked_reason}",
            f"blocked_reasons: {blocked}",
            f"recommended_next_step: {result.recommended_next_step}",
        ),
    ) + "\n"


def _case_status_and_next_step(
    *,
    operator_ready: bool,
    runtime_flat: bool,
    position_risk_remaining: bool,
    current_reasons: tuple[str, ...],
) -> tuple[
    ManualFlattenRuntimeFlatReconciliationCase,
    ManualFlattenRuntimeFlatReconciliationStatus,
    str,
    str,
]:
    if current_reasons:
        return (
            ManualFlattenRuntimeFlatReconciliationCase.CASE_4,
            ManualFlattenRuntimeFlatReconciliationStatus.UNSAFE_EXPOSURE_BLOCKED,
            "HALTED_UNKNOWN_POSITION",
            NEXT_STEP_MANUAL_FLATTEN_UNKNOWN_SAFE_STOP,
        )
    if operator_ready and runtime_flat:
        return (
            ManualFlattenRuntimeFlatReconciliationCase.CASE_1,
            ManualFlattenRuntimeFlatReconciliationStatus.MANUAL_FLATTEN_RECONCILED,
            "MANUAL_FLATTEN_RECONCILED_FLAT",
            NEXT_STEP_GMO_OFFICIAL_SETTLEMENT_ROUTE_REVIEW,
        )
    if operator_ready and position_risk_remaining:
        return (
            ManualFlattenRuntimeFlatReconciliationCase.CASE_2,
            ManualFlattenRuntimeFlatReconciliationStatus.POSITION_RISK_REMAINING,
            "MANUAL_FLATTEN_REPORTED_POSITION_RISK_REMAINING",
            NEXT_STEP_MANUAL_POSITION_RISK_STILL_REMAINING,
        )
    if runtime_flat and not operator_ready:
        return (
            ManualFlattenRuntimeFlatReconciliationCase.CASE_3,
            (
                ManualFlattenRuntimeFlatReconciliationStatus
                .RUNTIME_FLAT_OPERATOR_CONFIRMATION_INCOMPLETE
            ),
            "RUNTIME_FLAT_OPERATOR_CONFIRMATION_INCOMPLETE",
            NEXT_STEP_OPERATOR_MANUAL_FLATTEN_CONFIRMATION_RETRY,
        )
    return (
        ManualFlattenRuntimeFlatReconciliationCase.CASE_4,
        ManualFlattenRuntimeFlatReconciliationStatus.UNKNOWN_FAIL_CLOSED,
        "HALTED_UNKNOWN_POSITION",
        NEXT_STEP_MANUAL_FLATTEN_UNKNOWN_SAFE_STOP,
    )


def _operator_manual_flatten_ready(
    operator: OperatorManualFlattenSafeBooleanInput,
) -> bool:
    return (
        operator.operator_manual_flatten_completed
        and operator.operator_broker_ui_checked
        and not operator.operator_broker_ui_open_position_visible
        and not operator.operator_broker_ui_buy_position_visible
        and not operator.operator_broker_ui_sell_position_visible
        and not operator.operator_broker_ui_values_or_ids_provided
        and operator.operator_can_monitor
    )


def _operator_blocked_reasons(
    operator: OperatorManualFlattenSafeBooleanInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not operator.operator_manual_flatten_completed:
        reasons.append("operator_manual_flatten_not_completed")
    if not operator.operator_broker_ui_checked:
        reasons.append("operator_broker_ui_not_checked")
    if operator.operator_broker_ui_open_position_visible:
        reasons.append("operator_broker_ui_open_position_visible")
    if operator.operator_broker_ui_buy_position_visible:
        reasons.append("operator_broker_ui_buy_position_visible")
    if operator.operator_broker_ui_sell_position_visible:
        reasons.append("operator_broker_ui_sell_position_visible")
    if operator.operator_broker_ui_values_or_ids_provided:
        reasons.append("operator_broker_ui_values_or_ids_provided")
    if not operator.operator_can_monitor:
        reasons.append("operator_cannot_monitor")
    return tuple(reasons)


def _current_step_blocked_reasons(
    snapshot: ManualFlattenRuntimeFlatReconciliationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name, reason in (
        ("actual_entry_post_attempted_this_step", "entry_post_attempted_this_step"),
        ("actual_close_post_attempted_this_step", "close_post_attempted_this_step"),
        ("close_retry_attempted_this_step", "close_retry_attempted_this_step"),
        ("close_repost_attempted_this_step", "close_repost_attempted_this_step"),
        (
            "second_close_post_attempted_this_step",
            "second_close_post_attempted_this_step",
        ),
        ("order_endpoint_called_this_step", "order_endpoint_called_this_step"),
        ("live_order_once_called_this_step", "live_order_once_called_this_step"),
        ("ledger_update_attempted_this_step", "ledger_update_attempted_this_step"),
        ("receipt_handoff_attempted_this_step", "receipt_handoff_attempted_this_step"),
    ):
        if getattr(snapshot, field_name):
            reasons.append(reason)
    if snapshot.operator.operator_broker_ui_values_or_ids_provided:
        reasons.append("operator_ui_values_or_ids_provided")
    if _current_exposure(snapshot):
        reasons.append("current_step_raw_id_value_exposure_blocked")
    return tuple(dict.fromkeys(reasons))


def _official_alignment_blocked_reasons(
    snapshot: ManualFlattenRuntimeFlatReconciliationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.official_manual_url_recorded:
        reasons.append("official_manual_url_not_recorded")
    if not snapshot.official_trading_rules_url_recorded:
        reasons.append("official_trading_rules_url_not_recorded")
    if not snapshot.official_gmo_rules_alignment_checked:
        reasons.append("official_gmo_rules_alignment_not_checked")
    if not snapshot.generic_opposite_order_as_close_forbidden:
        reasons.append("generic_opposite_order_as_close_must_be_forbidden")
    if not snapshot.generic_close_primitive_revoked:
        reasons.append("generic_close_primitive_must_be_revoked")
    return tuple(reasons)


def _current_exposure(
    snapshot: ManualFlattenRuntimeFlatReconciliationInput,
) -> bool:
    return any(
        getattr(snapshot, field_name)
        for field_name in (
            "raw_request_exposure_attempted_this_step",
            "raw_response_exposure_attempted_this_step",
            "broker_api_response_exposure_attempted_this_step",
            "credential_value_exposure_attempted_this_step",
            "signature_value_exposure_attempted_this_step",
            "headers_value_exposure_attempted_this_step",
            "real_id_exposure_attempted_this_step",
            "account_id_exposure_attempted_this_step",
            "order_id_exposure_attempted_this_step",
            "transaction_id_exposure_attempted_this_step",
            "position_id_exposure_attempted_this_step",
            "actual_price_value_exposure_attempted_this_step",
            "actual_pnl_value_exposure_attempted_this_step",
        )
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


_OPERATOR_BOOL_FIELDS = (
    "operator_manual_flatten_completed",
    "operator_broker_ui_checked",
    "operator_broker_ui_open_position_visible",
    "operator_broker_ui_buy_position_visible",
    "operator_broker_ui_sell_position_visible",
    "operator_broker_ui_values_or_ids_provided",
    "operator_can_monitor",
)

_INPUT_BOOL_FIELDS = (
    "official_manual_url_recorded",
    "official_trading_rules_url_recorded",
    "official_gmo_rules_alignment_checked",
    "generic_opposite_order_as_close_forbidden",
    "generic_close_primitive_revoked",
    "official_settlement_route_confirmed",
    "actual_entry_post_attempted_this_step",
    "actual_close_post_attempted_this_step",
    "close_retry_attempted_this_step",
    "close_repost_attempted_this_step",
    "second_close_post_attempted_this_step",
    "order_endpoint_called_this_step",
    "live_order_once_called_this_step",
    "ledger_update_attempted_this_step",
    "receipt_handoff_attempted_this_step",
    "raw_request_exposure_attempted_this_step",
    "raw_response_exposure_attempted_this_step",
    "broker_api_response_exposure_attempted_this_step",
    "credential_value_exposure_attempted_this_step",
    "signature_value_exposure_attempted_this_step",
    "headers_value_exposure_attempted_this_step",
    "real_id_exposure_attempted_this_step",
    "account_id_exposure_attempted_this_step",
    "order_id_exposure_attempted_this_step",
    "transaction_id_exposure_attempted_this_step",
    "position_id_exposure_attempted_this_step",
    "actual_price_value_exposure_attempted_this_step",
    "actual_pnl_value_exposure_attempted_this_step",
)

_RESULT_BOOL_FIELDS = (
    "operator_manual_flatten_completed",
    "operator_broker_ui_checked",
    "operator_broker_ui_open_position_visible",
    "operator_broker_ui_buy_position_visible",
    "operator_broker_ui_sell_position_visible",
    "operator_broker_ui_values_or_ids_provided",
    "operator_can_monitor",
    "credential_presence_available",
    "runtime_read_executed",
    "has_open_position",
    "has_exactly_one_position",
    "has_multiple_positions",
    "manual_flatten_reconciled",
    "runtime_flat",
    "position_risk_remaining",
    "level5_minimal_cycle_completed",
    "level5_full_auto_cycle_completed",
    "fresh_cycle_allowed",
    "official_settlement_route_required",
    "official_manual_url_recorded",
    "official_trading_rules_url_recorded",
    "official_gmo_rules_alignment_checked",
    "generic_opposite_order_as_close_forbidden",
    "generic_close_primitive_revoked",
    "official_settlement_route_confirmed",
    "actual_entry_post_allowed_now",
    "actual_close_post_allowed_now",
    "retry_allowed",
    "repost_allowed",
    "second_close_allowed",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "actual_entry_post_executed_this_step",
    "actual_close_post_executed_this_step",
    "close_retry_attempted",
    "close_repost_attempted",
    "second_close_post_attempted",
    "ledger_updated",
    "receipt_handoff_executed",
    "raw_position_exposed",
    "raw_request_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "position_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
)
