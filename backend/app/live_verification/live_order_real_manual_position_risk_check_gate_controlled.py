"""Step 6G manual position risk check gate.

This module records the post-close multiple-position risk state with safe
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
from app.live_verification.live_order_real_post_close_position_confirmation_gate_controlled import (
    CLOSE_RESULT_ACCEPTED,
    FRESH_ENTRY_RESULT_ACCEPTED,
    PreviousEntryClosePostSafeSummaryInput,
)

MANUAL_POSITION_RISK_CHECK_GATE_LABEL = (
    "STEP6G_MANUAL_POSITION_RISK_CHECK_GATE_CONTROLLED"
)
GMO_FX_TRADING_MANUAL_URL_RECORDED = (
    "https://coin.z.com/corp_imgs/manual/kawasefx-trading-manual.pdf"
)
GMO_FX_TRADING_RULES_URL_RECORDED = (
    "https://coin.z.com/jp/corp/product/info/fx/#rule"
)

NEXT_STEP_MANUAL_FLATTEN_THEN_RUNTIME_FLAT_RECONCILIATION = (
    "Step 6G-PC-OX-R-MANUAL-FLATTEN-THEN-RUNTIME-FLAT-RECONCILIATION-C"
)
NEXT_STEP_RUNTIME_FLAT_RECONCILIATION_AFTER_MULTIPLE_RISK = (
    "Step 6G-PC-OX-R-RUNTIME-FLAT-RECONCILIATION-AFTER-MULTIPLE-POSITION-RISK-C"
)
NEXT_STEP_SINGLE_POSITION_MANUAL_CHECK = (
    "Step 6G-PC-OX-R-SINGLE-POSITION-STILL-OPEN-MANUAL-CHECK-GATE-C"
)
NEXT_STEP_UNKNOWN_MANUAL_POSITION_RISK_STOP = (
    "Step 6G-PC-OX-R-MANUAL-POSITION-RISK-UNKNOWN-SAFE-STOP-GATE-C"
)


class ManualPositionRiskCheckGateCase(str, Enum):
    CASE_1 = "CASE 1"
    CASE_2 = "CASE 2"
    CASE_3 = "CASE 3"
    CASE_4 = "CASE 4"


class ManualPositionRiskStatus(str, Enum):
    MULTIPLE_POSITIONS_CONFIRMED = "MULTIPLE_POSITIONS_CONFIRMED"
    ALREADY_FLAT = "ALREADY_FLAT"
    SINGLE_POSITION_STILL_OPEN = "SINGLE_POSITION_STILL_OPEN"
    UNKNOWN_FAIL_CLOSED = "UNKNOWN_FAIL_CLOSED"
    PREVIOUS_SUMMARY_BLOCKED = "PREVIOUS_SUMMARY_BLOCKED"
    UNSAFE_EXPOSURE_BLOCKED = "UNSAFE_EXPOSURE_BLOCKED"


@dataclass(frozen=True)
class OperatorUiSafeBooleanInput:
    operator_broker_ui_checked: bool = False
    operator_broker_ui_buy_position_visible: bool = False
    operator_broker_ui_sell_position_visible: bool = False
    operator_broker_ui_multiple_positions_visible: bool = False
    operator_broker_ui_values_or_ids_provided: bool = False
    operator_can_monitor: bool = False

    def __post_init__(self) -> None:
        _validate_bool_fields(self, _OPERATOR_UI_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialGmoFxRulesAlignmentInput:
    official_manual_url_recorded: bool = True
    official_trading_rules_url_recorded: bool = True
    official_gmo_rules_alignment_checked: bool = True
    generic_opposite_order_as_close_forbidden: bool = True
    generic_close_primitive_revoked: bool = True
    official_settlement_route_confirmed: bool = False

    def __post_init__(self) -> None:
        _validate_bool_fields(self, _OFFICIAL_ALIGNMENT_BOOL_FIELDS)


@dataclass(frozen=True)
class ManualPositionRiskCheckGateInput:
    previous_summary: PreviousEntryClosePostSafeSummaryInput = field(
        default_factory=PreviousEntryClosePostSafeSummaryInput,
    )
    operator_ui: OperatorUiSafeBooleanInput = field(
        default_factory=OperatorUiSafeBooleanInput,
    )
    official_alignment: OfficialGmoFxRulesAlignmentInput = field(
        default_factory=OfficialGmoFxRulesAlignmentInput,
    )
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
        if not isinstance(self.previous_summary, PreviousEntryClosePostSafeSummaryInput):
            raise LiveVerificationValidationError(
                "previous_summary must be PreviousEntryClosePostSafeSummaryInput",
            )
        if not isinstance(self.operator_ui, OperatorUiSafeBooleanInput):
            raise LiveVerificationValidationError(
                "operator_ui must be OperatorUiSafeBooleanInput",
            )
        if not isinstance(self.official_alignment, OfficialGmoFxRulesAlignmentInput):
            raise LiveVerificationValidationError(
                "official_alignment must be OfficialGmoFxRulesAlignmentInput",
            )
        _validate_bool_fields(self, _GATE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class ManualPositionRiskCheckGateResult:
    gate_label: str
    case: ManualPositionRiskCheckGateCase
    manual_position_risk_status: ManualPositionRiskStatus
    manual_position_risk_check_ready: bool
    runtime_position_checked: bool
    credential_presence_available: bool
    runtime_read_executed: bool
    position_status: PositionReadOnlyControlledStatus
    position_count_safe: int
    has_open_position: bool
    has_exactly_one_position: bool
    has_multiple_positions: bool
    multiple_positions_confirmed: bool
    suspected_hedged_positions: bool
    level5_minimal_cycle_completed: bool
    level5_full_auto_cycle_completed: bool
    entry_post_executed_once: bool
    close_post_executed_once: bool
    close_effect_confirmed_by_no_position: bool
    generic_opposite_order_created_position_risk: bool
    actual_entry_post_allowed_now: bool
    actual_close_post_allowed_now: bool
    retry_allowed: bool
    repost_allowed: bool
    second_close_allowed: bool
    ledger_update_allowed: bool
    receipt_handoff_allowed: bool
    manual_operator_flatten_recommended: bool
    official_settlement_route_required: bool
    fresh_cycle_allowed: bool
    next_cycle_state: str
    operator_broker_ui_checked: bool
    operator_broker_ui_buy_position_visible: bool
    operator_broker_ui_sell_position_visible: bool
    operator_broker_ui_multiple_positions_visible: bool
    operator_broker_ui_values_or_ids_provided: bool
    operator_can_monitor: bool
    official_manual_url_recorded: bool
    official_trading_rules_url_recorded: bool
    official_gmo_rules_alignment_checked: bool
    generic_opposite_order_as_close_forbidden: bool
    generic_close_primitive_revoked: bool
    official_settlement_route_confirmed: bool
    close_execution_blocked_reason: str
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
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("gate_label", self.gate_label)
        if not isinstance(self.case, ManualPositionRiskCheckGateCase):
            raise LiveVerificationValidationError("case must be manual risk enum")
        if not isinstance(self.manual_position_risk_status, ManualPositionRiskStatus):
            raise LiveVerificationValidationError(
                "manual_position_risk_status must be manual risk enum",
            )
        if not isinstance(self.position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "position_status must be controlled enum",
            )
        _require_non_empty("next_cycle_state", self.next_cycle_state)
        _require_non_empty(
            "close_execution_blocked_reason",
            self.close_execution_blocked_reason,
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_bool_fields(self, _GATE_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_manual_position_risk_check_gate_controlled(
    runtime_result: PositionRuntimeSafeReadControlledResult,
    input_snapshot: ManualPositionRiskCheckGateInput | None = None,
) -> ManualPositionRiskCheckGateResult:
    snapshot = input_snapshot or ManualPositionRiskCheckGateInput()
    previous_reasons = _previous_summary_blocked_reasons(snapshot.previous_summary)
    current_reasons = _current_step_blocked_reasons(snapshot)
    case, status, next_state, next_step = _case_status_and_next_step(
        runtime=runtime_result,
        previous_reasons=previous_reasons,
        current_reasons=current_reasons,
    )
    multiple_confirmed = (
        runtime_result.position_status
        is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
        and runtime_result.position_count_safe >= 2
        and not previous_reasons
        and not current_reasons
    )
    entry_once = _entry_post_executed_once(snapshot.previous_summary)
    close_once = _close_post_executed_once(snapshot.previous_summary)
    blocked_reasons = tuple(
        dict.fromkeys(
            (
                *previous_reasons,
                *current_reasons,
                *runtime_result.blocked_reasons,
                *_official_alignment_blocked_reasons(snapshot.official_alignment),
            ),
        ),
    )
    return ManualPositionRiskCheckGateResult(
        gate_label=MANUAL_POSITION_RISK_CHECK_GATE_LABEL,
        case=case,
        manual_position_risk_status=status,
        manual_position_risk_check_ready=not previous_reasons and not current_reasons,
        runtime_position_checked=runtime_result.position_status_checked,
        credential_presence_available=runtime_result.credential_presence_available,
        runtime_read_executed=runtime_result.runtime_read_executed,
        position_status=runtime_result.position_status,
        position_count_safe=runtime_result.position_count_safe,
        has_open_position=runtime_result.has_open_position,
        has_exactly_one_position=runtime_result.has_exactly_one_position,
        has_multiple_positions=runtime_result.has_multiple_positions,
        multiple_positions_confirmed=multiple_confirmed,
        suspected_hedged_positions=(
            multiple_confirmed
            or (
                snapshot.operator_ui.operator_broker_ui_buy_position_visible
                and snapshot.operator_ui.operator_broker_ui_sell_position_visible
            )
        ),
        level5_minimal_cycle_completed=False,
        level5_full_auto_cycle_completed=False,
        entry_post_executed_once=entry_once,
        close_post_executed_once=close_once,
        close_effect_confirmed_by_no_position=False,
        generic_opposite_order_created_position_risk=multiple_confirmed,
        actual_entry_post_allowed_now=False,
        actual_close_post_allowed_now=False,
        retry_allowed=False,
        repost_allowed=False,
        second_close_allowed=False,
        ledger_update_allowed=False,
        receipt_handoff_allowed=False,
        manual_operator_flatten_recommended=multiple_confirmed,
        official_settlement_route_required=True,
        fresh_cycle_allowed=False,
        next_cycle_state=next_state,
        operator_broker_ui_checked=snapshot.operator_ui.operator_broker_ui_checked,
        operator_broker_ui_buy_position_visible=(
            snapshot.operator_ui.operator_broker_ui_buy_position_visible
        ),
        operator_broker_ui_sell_position_visible=(
            snapshot.operator_ui.operator_broker_ui_sell_position_visible
        ),
        operator_broker_ui_multiple_positions_visible=(
            snapshot.operator_ui.operator_broker_ui_multiple_positions_visible
        ),
        operator_broker_ui_values_or_ids_provided=(
            snapshot.operator_ui.operator_broker_ui_values_or_ids_provided
        ),
        operator_can_monitor=snapshot.operator_ui.operator_can_monitor,
        official_manual_url_recorded=(
            snapshot.official_alignment.official_manual_url_recorded
        ),
        official_trading_rules_url_recorded=(
            snapshot.official_alignment.official_trading_rules_url_recorded
        ),
        official_gmo_rules_alignment_checked=(
            snapshot.official_alignment.official_gmo_rules_alignment_checked
        ),
        generic_opposite_order_as_close_forbidden=(
            snapshot.official_alignment.generic_opposite_order_as_close_forbidden
        ),
        generic_close_primitive_revoked=(
            snapshot.official_alignment.generic_close_primitive_revoked
        ),
        official_settlement_route_confirmed=(
            snapshot.official_alignment.official_settlement_route_confirmed
        ),
        close_execution_blocked_reason=OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED,
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
        recommended_next_step=next_step,
        blocked_reasons=blocked_reasons,
    )


def render_manual_position_risk_check_gate_markdown(
    result: ManualPositionRiskCheckGateResult,
) -> str:
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Manual Position Risk Check Gate",
            "",
            "This gate records multiple-position risk with safe status/count only.",
            "It does not execute entry POST, close POST, retry, repost, ledger,",
            "receipt handoff, or raw/ID/value handling.",
            "",
            f"case: {result.case.value}",
            f"manual_position_risk_status: {result.manual_position_risk_status.value}",
            f"runtime_read_executed: {_bool_text(result.runtime_read_executed)}",
            f"position_status: {result.position_status.value}",
            f"position_count_safe: {result.position_count_safe}",
            (
                "multiple_positions_confirmed: "
                f"{_bool_text(result.multiple_positions_confirmed)}"
            ),
            (
                "suspected_hedged_positions: "
                f"{_bool_text(result.suspected_hedged_positions)}"
            ),
            (
                "level5_minimal_cycle_completed: "
                f"{_bool_text(result.level5_minimal_cycle_completed)}"
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
                "official_settlement_route_confirmed: "
                f"{_bool_text(result.official_settlement_route_confirmed)}"
            ),
            (
                "actual_close_post_allowed_now: "
                f"{_bool_text(result.actual_close_post_allowed_now)}"
            ),
            f"close_execution_blocked_reason: {result.close_execution_blocked_reason}",
            (
                "manual_operator_flatten_recommended: "
                f"{_bool_text(result.manual_operator_flatten_recommended)}"
            ),
            f"fresh_cycle_allowed: {_bool_text(result.fresh_cycle_allowed)}",
            f"raw_position_exposed: {_bool_text(result.raw_position_exposed)}",
            f"position_id_exposed: {_bool_text(result.position_id_exposed)}",
            f"account_id_exposed: {_bool_text(result.account_id_exposed)}",
            f"order_id_exposed: {_bool_text(result.order_id_exposed)}",
            f"transaction_id_exposed: {_bool_text(result.transaction_id_exposed)}",
            (
                "broker_api_response_exposed: "
                f"{_bool_text(result.broker_api_response_exposed)}"
            ),
            (
                "credential_value_exposed: "
                f"{_bool_text(result.credential_value_exposed)}"
            ),
            f"signature_value_exposed: {_bool_text(result.signature_value_exposed)}",
            f"headers_value_exposed: {_bool_text(result.headers_value_exposed)}",
            f"blocked_reasons: {blocked}",
            f"recommended_next_step: {result.recommended_next_step}",
        ),
    ) + "\n"


def _case_status_and_next_step(
    *,
    runtime: PositionRuntimeSafeReadControlledResult,
    previous_reasons: tuple[str, ...],
    current_reasons: tuple[str, ...],
) -> tuple[
    ManualPositionRiskCheckGateCase,
    ManualPositionRiskStatus,
    str,
    str,
]:
    if previous_reasons:
        return (
            ManualPositionRiskCheckGateCase.CASE_4,
            ManualPositionRiskStatus.PREVIOUS_SUMMARY_BLOCKED,
            "HALTED_UNKNOWN_POSITION",
            NEXT_STEP_UNKNOWN_MANUAL_POSITION_RISK_STOP,
        )
    if current_reasons:
        return (
            ManualPositionRiskCheckGateCase.CASE_4,
            ManualPositionRiskStatus.UNSAFE_EXPOSURE_BLOCKED,
            "HALTED_UNKNOWN_POSITION",
            NEXT_STEP_UNKNOWN_MANUAL_POSITION_RISK_STOP,
        )
    if (
        runtime.position_status
        is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    ):
        return (
            ManualPositionRiskCheckGateCase.CASE_1,
            ManualPositionRiskStatus.MULTIPLE_POSITIONS_CONFIRMED,
            "HALTED_MANUAL_FLATTEN_REQUIRED",
            NEXT_STEP_MANUAL_FLATTEN_THEN_RUNTIME_FLAT_RECONCILIATION,
        )
    if runtime.position_status is PositionReadOnlyControlledStatus.NO_POSITION:
        return (
            ManualPositionRiskCheckGateCase.CASE_2,
            ManualPositionRiskStatus.ALREADY_FLAT,
            "RUNTIME_FLAT_AFTER_MULTIPLE_POSITION_RISK",
            NEXT_STEP_RUNTIME_FLAT_RECONCILIATION_AFTER_MULTIPLE_RISK,
        )
    if runtime.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        return (
            ManualPositionRiskCheckGateCase.CASE_3,
            ManualPositionRiskStatus.SINGLE_POSITION_STILL_OPEN,
            "HALTED_SINGLE_POSITION_STILL_OPEN",
            NEXT_STEP_SINGLE_POSITION_MANUAL_CHECK,
        )
    return (
        ManualPositionRiskCheckGateCase.CASE_4,
        ManualPositionRiskStatus.UNKNOWN_FAIL_CLOSED,
        "HALTED_UNKNOWN_POSITION",
        NEXT_STEP_UNKNOWN_MANUAL_POSITION_RISK_STOP,
    )


def _previous_summary_blocked_reasons(
    summary: PreviousEntryClosePostSafeSummaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not _entry_post_executed_once(summary):
        reasons.append("fresh_entry_post_not_exactly_once")
    if summary.fresh_entry_sanitized_result_category != FRESH_ENTRY_RESULT_ACCEPTED:
        reasons.append("fresh_entry_result_not_accepted_sanitized")
    if not _close_post_executed_once(summary):
        reasons.append("close_post_not_exactly_once")
    if summary.close_sanitized_result_category != CLOSE_RESULT_ACCEPTED:
        reasons.append("close_result_not_accepted_sanitized")
    if summary.fresh_entry_retry_attempted or summary.fresh_entry_repost_attempted:
        reasons.append("fresh_entry_retry_or_repost_attempted")
    if summary.fresh_entry_second_post_attempted:
        reasons.append("fresh_entry_second_post_attempted")
    if (
        summary.close_retry_attempted
        or summary.close_repost_attempted
        or summary.close_second_post_attempted
    ):
        reasons.append("close_retry_repost_or_second_attempted")
    if summary.ledger_updated or summary.receipt_handoff_executed:
        reasons.append("ledger_or_receipt_executed")
    if _previous_exposure(summary):
        reasons.append("previous_raw_id_value_exposure_blocked")
    return tuple(reasons)


def _current_step_blocked_reasons(
    snapshot: ManualPositionRiskCheckGateInput,
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
    if snapshot.operator_ui.operator_broker_ui_values_or_ids_provided:
        reasons.append("operator_ui_values_or_ids_provided")
    if _current_exposure(snapshot):
        reasons.append("current_step_raw_id_value_exposure_blocked")
    return tuple(reasons)


def _official_alignment_blocked_reasons(
    alignment: OfficialGmoFxRulesAlignmentInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not alignment.official_manual_url_recorded:
        reasons.append("official_manual_url_not_recorded")
    if not alignment.official_trading_rules_url_recorded:
        reasons.append("official_trading_rules_url_not_recorded")
    if not alignment.official_gmo_rules_alignment_checked:
        reasons.append("official_gmo_rules_alignment_not_checked")
    if not alignment.generic_opposite_order_as_close_forbidden:
        reasons.append("generic_opposite_order_as_close_must_be_forbidden")
    if not alignment.generic_close_primitive_revoked:
        reasons.append("generic_close_primitive_must_be_revoked")
    return tuple(reasons)


def _entry_post_executed_once(summary: PreviousEntryClosePostSafeSummaryInput) -> bool:
    return (
        summary.fresh_entry_http_post_executed
        and summary.fresh_entry_post_execution_count == 1
    )


def _close_post_executed_once(summary: PreviousEntryClosePostSafeSummaryInput) -> bool:
    return summary.close_http_post_executed and summary.close_post_execution_count == 1


def _previous_exposure(summary: PreviousEntryClosePostSafeSummaryInput) -> bool:
    return any(
        getattr(summary, field_name)
        for field_name in (
            "raw_request_exposed",
            "raw_response_exposed",
            "broker_api_response_exposed",
            "credential_value_exposed",
            "signature_value_exposed",
            "headers_value_exposed",
            "real_id_exposed",
            "account_id_exposed",
            "order_id_exposed",
            "transaction_id_exposed",
            "position_id_exposed",
            "client_order_id_actual_value_exposed",
        )
    )


def _current_exposure(snapshot: ManualPositionRiskCheckGateInput) -> bool:
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


_OPERATOR_UI_BOOL_FIELDS = (
    "operator_broker_ui_checked",
    "operator_broker_ui_buy_position_visible",
    "operator_broker_ui_sell_position_visible",
    "operator_broker_ui_multiple_positions_visible",
    "operator_broker_ui_values_or_ids_provided",
    "operator_can_monitor",
)

_OFFICIAL_ALIGNMENT_BOOL_FIELDS = (
    "official_manual_url_recorded",
    "official_trading_rules_url_recorded",
    "official_gmo_rules_alignment_checked",
    "generic_opposite_order_as_close_forbidden",
    "generic_close_primitive_revoked",
    "official_settlement_route_confirmed",
)

_GATE_INPUT_BOOL_FIELDS = (
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

_GATE_RESULT_BOOL_FIELDS = (
    "manual_position_risk_check_ready",
    "runtime_position_checked",
    "credential_presence_available",
    "runtime_read_executed",
    "has_open_position",
    "has_exactly_one_position",
    "has_multiple_positions",
    "multiple_positions_confirmed",
    "suspected_hedged_positions",
    "level5_minimal_cycle_completed",
    "level5_full_auto_cycle_completed",
    "entry_post_executed_once",
    "close_post_executed_once",
    "close_effect_confirmed_by_no_position",
    "generic_opposite_order_created_position_risk",
    "actual_entry_post_allowed_now",
    "actual_close_post_allowed_now",
    "retry_allowed",
    "repost_allowed",
    "second_close_allowed",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "manual_operator_flatten_recommended",
    "official_settlement_route_required",
    "fresh_cycle_allowed",
    "operator_broker_ui_checked",
    "operator_broker_ui_buy_position_visible",
    "operator_broker_ui_sell_position_visible",
    "operator_broker_ui_multiple_positions_visible",
    "operator_broker_ui_values_or_ids_provided",
    "operator_can_monitor",
    "official_manual_url_recorded",
    "official_trading_rules_url_recorded",
    "official_gmo_rules_alignment_checked",
    "generic_opposite_order_as_close_forbidden",
    "generic_close_primitive_revoked",
    "official_settlement_route_confirmed",
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
