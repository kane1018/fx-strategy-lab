"""Step 6G entry unknown/no-position closeout gate.

This module closes out a previous unknown/blocked entry attempt only as a safe
state transition when a sanitized runtime position safe read still shows no
position. It does not execute entry POST, retry, repost, close POST, broker
writes, ledger updates, receipt handoff, env reads, or raw ID/value handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_position_runtime_safe_read_controlled import (
    PositionRuntimeSafeReadControlledResult,
    build_position_runtime_safe_read_controlled,
)
from app.live_verification.live_order_real_post_entry_position_confirmation_gate_controlled import (
    PostEntryPositionConfirmationGateInput,
    PostEntryPositionConfirmationGateResult,
    PostEntryPositionConfirmationStatus,
    PreviousEntryPostSafeSummaryInput,
    build_post_entry_position_confirmation_gate_controlled,
)
from app.live_verification.live_order_real_step6g_level5_fast_mvp_controlled import (
    Level5CycleState,
    Level5CycleTransitionInput,
    PositionReadOnlyStatus,
    transition_level5_cycle_state,
)

ENTRY_UNKNOWN_NO_POSITION_CLOSEOUT_GATE_LABEL = (
    "STEP6G_ENTRY_UNKNOWN_NO_POSITION_CLOSEOUT_GATE_CONTROLLED"
)
PREVIOUS_CYCLE_STATE_UNKNOWN_RESULT_SAFE_STOP = "UNKNOWN_RESULT_SAFE_STOP"
ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT = "ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT"
PREVIOUS_ENTRY_RESULT_SAFE_CATEGORY_UNKNOWN_BLOCKED = "UNKNOWN_BLOCKED"
PENDING_ORDER_SAFE_STATUS_SOURCE_MISSING = "NOT_CHECKED_SOURCE_MISSING"
NEXT_STEP_LEVEL5_FRESH_CYCLE_ENTRY_GATE = (
    "Step 6G-PC-OX-R-LEVEL5-FRESH-CYCLE-ENTRY-GATE-C"
)
NEXT_STEP_CLOSE_ORDER_EXECUTION_GATE = (
    "Step 6G-PC-OX-R-CLOSE-ORDER-EXECUTION-GATE-C"
)
NEXT_STEP_MANUAL_POSITION_RISK_CHECK = (
    "Step 6G-PC-OX-R-MANUAL-POSITION-RISK-CHECK-GATE-C"
)
NEXT_STEP_POST_ENTRY_UNKNOWN_SAFE_STOP = (
    "Step 6G-PC-OX-R-POST-ENTRY-UNKNOWN-RESULT-SAFE-STOP-GATE-C"
)


class EntryUnknownNoPositionCloseoutCase(str, Enum):
    CASE_1 = "CASE 1"
    CASE_2 = "CASE 2"
    CASE_3 = "CASE 3"
    CASE_4 = "CASE 4"


class EntryUnknownNoPositionCloseoutStatus(str, Enum):
    ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT = "ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT"
    POSITION_OPEN_FOUND_NO_CLOSE_POST = "POSITION_OPEN_FOUND_NO_CLOSE_POST"
    MULTIPLE_POSITIONS_MANUAL_CHECK_REQUIRED = (
        "MULTIPLE_POSITIONS_MANUAL_CHECK_REQUIRED"
    )
    UNKNOWN_FAIL_CLOSED_MANUAL_CHECK_REQUIRED = (
        "UNKNOWN_FAIL_CLOSED_MANUAL_CHECK_REQUIRED"
    )
    PREVIOUS_ENTRY_SUMMARY_BLOCKED = "PREVIOUS_ENTRY_SUMMARY_BLOCKED"
    UNSAFE_EXPOSURE_BLOCKED = "UNSAFE_EXPOSURE_BLOCKED"


@dataclass(frozen=True)
class ManualOperatorUiSafeCheckInput:
    operator_broker_ui_checked: bool = False
    operator_broker_ui_open_position_visible: bool = False
    operator_broker_ui_pending_order_visible: bool = False
    operator_broker_ui_can_monitor: bool = True
    operator_broker_ui_values_or_ids_provided: bool = False

    def __post_init__(self) -> None:
        _validate_bool_fields(self, _MANUAL_UI_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class EntryUnknownNoPositionCloseoutGateInput:
    previous_entry_summary: PreviousEntryPostSafeSummaryInput = field(
        default_factory=PreviousEntryPostSafeSummaryInput,
    )
    manual_ui_check: ManualOperatorUiSafeCheckInput = field(
        default_factory=ManualOperatorUiSafeCheckInput,
    )
    previous_cycle_state: str = PREVIOUS_CYCLE_STATE_UNKNOWN_RESULT_SAFE_STOP
    pending_order_safe_status: str = PENDING_ORDER_SAFE_STATUS_SOURCE_MISSING
    actual_entry_post_attempted_this_step: bool = False
    entry_retry_attempted_this_step: bool = False
    entry_repost_attempted_this_step: bool = False
    second_entry_post_attempted_this_step: bool = False
    close_post_attempted_this_step: bool = False
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
        if not isinstance(self.previous_entry_summary, PreviousEntryPostSafeSummaryInput):
            raise LiveVerificationValidationError(
                "previous_entry_summary must be PreviousEntryPostSafeSummaryInput",
            )
        if not isinstance(self.manual_ui_check, ManualOperatorUiSafeCheckInput):
            raise LiveVerificationValidationError(
                "manual_ui_check must be ManualOperatorUiSafeCheckInput",
            )
        _require_non_empty("previous_cycle_state", self.previous_cycle_state)
        _require_non_empty("pending_order_safe_status", self.pending_order_safe_status)
        _validate_bool_fields(self, _GATE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class EntryUnknownNoPositionCloseoutGateResult:
    gate_label: str
    case: EntryUnknownNoPositionCloseoutCase
    closeout_status: EntryUnknownNoPositionCloseoutStatus
    closeout_gate_ready: bool
    previous_entry_post_executed: bool
    previous_entry_post_execution_count: int
    previous_entry_result_safe_category: str
    previous_entry_retry_attempted: bool
    previous_entry_second_post_attempted: bool
    previous_close_post_executed: bool
    previous_ledger_or_receipt_executed: bool
    previous_raw_id_value_exposed: bool
    credential_presence_available: bool
    runtime_position_checked: bool
    runtime_read_executed: bool
    runtime_position_status: PositionReadOnlyControlledStatus
    runtime_position_count_safe: int
    has_open_position: bool
    has_exactly_one_position: bool
    has_multiple_positions: bool
    entry_effect_confirmed_by_position: bool
    entry_unknown_no_position: bool
    entry_unknown_no_position_closeout_completed: bool
    retry_allowed: bool
    repost_allowed: bool
    second_entry_allowed: bool
    close_post_allowed_now: bool
    ledger_update_allowed: bool
    receipt_handoff_allowed: bool
    fresh_cycle_may_be_planned: bool
    fresh_cycle_requires_new_position_read: bool
    fresh_cycle_requires_new_signal: bool
    fresh_cycle_requires_new_operator_readiness: bool
    fresh_cycle_requires_new_entry_confirmation: bool
    fresh_cycle_must_not_reuse_previous_confirmation: bool
    fresh_cycle_must_not_reuse_previous_attempt: bool
    actual_entry_post_allowed_now: bool
    actual_close_post_allowed_now: bool
    previous_cycle_state: str
    next_cycle_state: str
    close_execution_gate_may_be_planned: bool
    operator_broker_ui_checked: bool
    operator_broker_ui_open_position_visible: bool
    operator_broker_ui_pending_order_visible: bool
    operator_broker_ui_can_monitor: bool
    operator_broker_ui_values_or_ids_provided: bool
    manual_ui_confirmation_completed: bool
    manual_ui_check_remaining_risk: bool
    pending_order_safe_status: str
    pending_order_check_required_for_fresh_cycle: bool
    manual_ui_pending_order_check_recommended: bool
    raw_position_exposed: bool
    raw_request_exposed: bool
    raw_response_exposed: bool
    position_id_exposed: bool
    account_id_exposed: bool
    order_id_exposed: bool
    transaction_id_exposed: bool
    broker_api_response_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool
    actual_entry_post_executed_this_step: bool
    close_post_executed_this_step: bool
    retry_or_repost_attempted_this_step: bool
    second_entry_post_attempted_this_step: bool
    ledger_updated_this_step: bool
    receipt_handoff_executed_this_step: bool
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("gate_label", self.gate_label)
        if not isinstance(self.case, EntryUnknownNoPositionCloseoutCase):
            raise LiveVerificationValidationError("case must be closeout enum")
        if not isinstance(self.closeout_status, EntryUnknownNoPositionCloseoutStatus):
            raise LiveVerificationValidationError(
                "closeout_status must be closeout status enum",
            )
        if not isinstance(
            self.runtime_position_status,
            PositionReadOnlyControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        _require_non_empty(
            "previous_entry_result_safe_category",
            self.previous_entry_result_safe_category,
        )
        _require_non_empty("previous_cycle_state", self.previous_cycle_state)
        _require_non_empty("next_cycle_state", self.next_cycle_state)
        _require_non_empty("pending_order_safe_status", self.pending_order_safe_status)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_non_negative_int(
            "previous_entry_post_execution_count",
            self.previous_entry_post_execution_count,
        )
        _validate_non_negative_int(
            "runtime_position_count_safe",
            self.runtime_position_count_safe,
        )
        _validate_bool_fields(self, _GATE_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_entry_unknown_no_position_closeout_gate_controlled(
    input_snapshot: EntryUnknownNoPositionCloseoutGateInput | None = None,
    *,
    post_entry_result: PostEntryPositionConfirmationGateResult | None = None,
    runtime_result: PositionRuntimeSafeReadControlledResult | None = None,
) -> EntryUnknownNoPositionCloseoutGateResult:
    snapshot = input_snapshot or EntryUnknownNoPositionCloseoutGateInput()
    post_entry = post_entry_result or build_post_entry_position_confirmation_gate_controlled(
        _post_entry_input_from_closeout_input(snapshot),
        runtime_result=runtime_result or build_position_runtime_safe_read_controlled(),
    )
    previous_reasons = _previous_entry_blocked_reasons(snapshot.previous_entry_summary)
    current_reasons = _current_step_blocked_reasons(snapshot)
    manual_reasons = _manual_ui_blocked_reasons(snapshot.manual_ui_check)
    post_entry_reasons = _post_entry_blocked_reasons(post_entry)
    hard_blocked_reasons = tuple(
        dict.fromkeys(
            (
                *previous_reasons,
                *current_reasons,
                *manual_reasons,
                *post_entry_reasons,
            ),
        ),
    )
    blocked_reasons = tuple(
        dict.fromkeys(
            (
                *hard_blocked_reasons,
                *post_entry.blocked_reasons,
            ),
        ),
    )
    case, status, next_state, next_step = _case_status_and_next_step(
        post_entry=post_entry,
        blocked_reasons=hard_blocked_reasons,
    )
    closeout_completed = status is (
        EntryUnknownNoPositionCloseoutStatus.ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT
    )
    position_open = status is (
        EntryUnknownNoPositionCloseoutStatus.POSITION_OPEN_FOUND_NO_CLOSE_POST
    )
    fresh_cycle_may_be_planned = closeout_completed and not hard_blocked_reasons
    manual_completed = _manual_ui_confirmation_completed(snapshot.manual_ui_check)
    cycle_state = _safe_cycle_next_state(closeout_completed)
    safe_next_state = cycle_state or next_state
    return EntryUnknownNoPositionCloseoutGateResult(
        gate_label=ENTRY_UNKNOWN_NO_POSITION_CLOSEOUT_GATE_LABEL,
        case=case,
        closeout_status=status,
        closeout_gate_ready=closeout_completed and not hard_blocked_reasons,
        previous_entry_post_executed=snapshot.previous_entry_summary.entry_http_post_executed,
        previous_entry_post_execution_count=(
            snapshot.previous_entry_summary.entry_post_execution_count
        ),
        previous_entry_result_safe_category=(
            PREVIOUS_ENTRY_RESULT_SAFE_CATEGORY_UNKNOWN_BLOCKED
        ),
        previous_entry_retry_attempted=(
            snapshot.previous_entry_summary.entry_retry_attempted
        ),
        previous_entry_second_post_attempted=(
            snapshot.previous_entry_summary.entry_second_post_attempted
        ),
        previous_close_post_executed=snapshot.previous_entry_summary.close_post_executed,
        previous_ledger_or_receipt_executed=(
            snapshot.previous_entry_summary.ledger_updated
            or snapshot.previous_entry_summary.receipt_handoff_executed
        ),
        previous_raw_id_value_exposed=False,
        credential_presence_available=post_entry.credential_presence_available,
        runtime_position_checked=post_entry.position_status_checked,
        runtime_read_executed=post_entry.runtime_read_executed,
        runtime_position_status=post_entry.position_status,
        runtime_position_count_safe=post_entry.position_count_safe,
        has_open_position=post_entry.has_open_position,
        has_exactly_one_position=post_entry.has_exactly_one_position,
        has_multiple_positions=post_entry.has_multiple_positions,
        entry_effect_confirmed_by_position=position_open,
        entry_unknown_no_position=closeout_completed,
        entry_unknown_no_position_closeout_completed=closeout_completed,
        retry_allowed=False,
        repost_allowed=False,
        second_entry_allowed=False,
        close_post_allowed_now=False,
        ledger_update_allowed=False,
        receipt_handoff_allowed=False,
        fresh_cycle_may_be_planned=fresh_cycle_may_be_planned,
        fresh_cycle_requires_new_position_read=True,
        fresh_cycle_requires_new_signal=True,
        fresh_cycle_requires_new_operator_readiness=True,
        fresh_cycle_requires_new_entry_confirmation=True,
        fresh_cycle_must_not_reuse_previous_confirmation=True,
        fresh_cycle_must_not_reuse_previous_attempt=True,
        actual_entry_post_allowed_now=False,
        actual_close_post_allowed_now=False,
        previous_cycle_state=snapshot.previous_cycle_state,
        next_cycle_state=safe_next_state,
        close_execution_gate_may_be_planned=position_open,
        operator_broker_ui_checked=snapshot.manual_ui_check.operator_broker_ui_checked,
        operator_broker_ui_open_position_visible=(
            snapshot.manual_ui_check.operator_broker_ui_open_position_visible
        ),
        operator_broker_ui_pending_order_visible=(
            snapshot.manual_ui_check.operator_broker_ui_pending_order_visible
        ),
        operator_broker_ui_can_monitor=snapshot.manual_ui_check.operator_broker_ui_can_monitor,
        operator_broker_ui_values_or_ids_provided=(
            snapshot.manual_ui_check.operator_broker_ui_values_or_ids_provided
        ),
        manual_ui_confirmation_completed=manual_completed,
        manual_ui_check_remaining_risk=not manual_completed,
        pending_order_safe_status=snapshot.pending_order_safe_status,
        pending_order_check_required_for_fresh_cycle=False,
        manual_ui_pending_order_check_recommended=True,
        raw_position_exposed=False,
        raw_request_exposed=False,
        raw_response_exposed=False,
        position_id_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
        broker_api_response_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
        actual_entry_post_executed_this_step=False,
        close_post_executed_this_step=False,
        retry_or_repost_attempted_this_step=False,
        second_entry_post_attempted_this_step=False,
        ledger_updated_this_step=False,
        receipt_handoff_executed_this_step=False,
        recommended_next_step=next_step,
        blocked_reasons=blocked_reasons,
    )


def render_entry_unknown_no_position_closeout_gate_markdown(
    result: EntryUnknownNoPositionCloseoutGateResult,
) -> str:
    """Render safe closeout fields only."""
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Entry Unknown No-Position Closeout Gate",
            "",
            "This gate closes out a previous unknown/blocked entry attempt only",
            "as a safe state transition. It does not retry, repost, execute a",
            "second entry POST, execute close POST, update ledgers, hand off",
            "receipts, or expose raw/ID/value data.",
            "",
            f"case: {result.case.value}",
            f"closeout_status: {result.closeout_status.value}",
            f"closeout_gate_ready: {_bool_text(result.closeout_gate_ready)}",
            (
                "previous_entry_post_executed: "
                f"{_bool_text(result.previous_entry_post_executed)}"
            ),
            (
                "previous_entry_post_execution_count: "
                f"{result.previous_entry_post_execution_count}"
            ),
            (
                "previous_entry_retry_attempted: "
                f"{_bool_text(result.previous_entry_retry_attempted)}"
            ),
            (
                "previous_entry_second_post_attempted: "
                f"{_bool_text(result.previous_entry_second_post_attempted)}"
            ),
            (
                "previous_close_post_executed: "
                f"{_bool_text(result.previous_close_post_executed)}"
            ),
            f"runtime_read_executed: {_bool_text(result.runtime_read_executed)}",
            f"position_status: {result.runtime_position_status.value}",
            f"position_count_safe: {result.runtime_position_count_safe}",
            (
                "entry_unknown_no_position_closeout_completed: "
                f"{_bool_text(result.entry_unknown_no_position_closeout_completed)}"
            ),
            f"next_cycle_state: {result.next_cycle_state}",
            f"retry_allowed: {_bool_text(result.retry_allowed)}",
            f"repost_allowed: {_bool_text(result.repost_allowed)}",
            f"second_entry_allowed: {_bool_text(result.second_entry_allowed)}",
            f"close_post_allowed_now: {_bool_text(result.close_post_allowed_now)}",
            (
                "actual_entry_post_allowed_now: "
                f"{_bool_text(result.actual_entry_post_allowed_now)}"
            ),
            (
                "fresh_cycle_may_be_planned: "
                f"{_bool_text(result.fresh_cycle_may_be_planned)}"
            ),
            (
                "fresh_cycle_requires_new_position_read: "
                f"{_bool_text(result.fresh_cycle_requires_new_position_read)}"
            ),
            (
                "fresh_cycle_must_not_reuse_previous_attempt: "
                f"{_bool_text(result.fresh_cycle_must_not_reuse_previous_attempt)}"
            ),
            (
                "operator_broker_ui_checked: "
                f"{_bool_text(result.operator_broker_ui_checked)}"
            ),
            (
                "manual_ui_confirmation_completed: "
                f"{_bool_text(result.manual_ui_confirmation_completed)}"
            ),
            f"pending_order_safe_status: {result.pending_order_safe_status}",
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


def _post_entry_input_from_closeout_input(
    snapshot: EntryUnknownNoPositionCloseoutGateInput,
) -> PostEntryPositionConfirmationGateInput:
    return PostEntryPositionConfirmationGateInput(
        previous_entry_summary=snapshot.previous_entry_summary,
        actual_entry_post_attempted_this_step=(
            snapshot.actual_entry_post_attempted_this_step
        ),
        entry_retry_attempted_this_step=snapshot.entry_retry_attempted_this_step,
        entry_repost_attempted_this_step=snapshot.entry_repost_attempted_this_step,
        second_entry_post_attempted_this_step=(
            snapshot.second_entry_post_attempted_this_step
        ),
        close_post_attempted_this_step=snapshot.close_post_attempted_this_step,
        order_endpoint_called_this_step=snapshot.order_endpoint_called_this_step,
        live_order_once_called_this_step=snapshot.live_order_once_called_this_step,
        ledger_update_attempted_this_step=snapshot.ledger_update_attempted_this_step,
        receipt_handoff_attempted_this_step=snapshot.receipt_handoff_attempted_this_step,
        raw_request_exposure_attempted_this_step=(
            snapshot.raw_request_exposure_attempted_this_step
        ),
        raw_response_exposure_attempted_this_step=(
            snapshot.raw_response_exposure_attempted_this_step
        ),
        broker_api_response_exposure_attempted_this_step=(
            snapshot.broker_api_response_exposure_attempted_this_step
        ),
        credential_value_exposure_attempted_this_step=(
            snapshot.credential_value_exposure_attempted_this_step
        ),
        signature_value_exposure_attempted_this_step=(
            snapshot.signature_value_exposure_attempted_this_step
        ),
        headers_value_exposure_attempted_this_step=(
            snapshot.headers_value_exposure_attempted_this_step
        ),
        real_id_exposure_attempted_this_step=(
            snapshot.real_id_exposure_attempted_this_step
        ),
        account_id_exposure_attempted_this_step=(
            snapshot.account_id_exposure_attempted_this_step
        ),
        order_id_exposure_attempted_this_step=(
            snapshot.order_id_exposure_attempted_this_step
        ),
        transaction_id_exposure_attempted_this_step=(
            snapshot.transaction_id_exposure_attempted_this_step
        ),
        position_id_exposure_attempted_this_step=(
            snapshot.position_id_exposure_attempted_this_step
        ),
        actual_price_value_exposure_attempted_this_step=(
            snapshot.actual_price_value_exposure_attempted_this_step
        ),
        actual_pnl_value_exposure_attempted_this_step=(
            snapshot.actual_pnl_value_exposure_attempted_this_step
        ),
    )


def _case_status_and_next_step(
    *,
    post_entry: PostEntryPositionConfirmationGateResult,
    blocked_reasons: tuple[str, ...],
) -> tuple[
    EntryUnknownNoPositionCloseoutCase,
    EntryUnknownNoPositionCloseoutStatus,
    str,
    str,
]:
    if blocked_reasons:
        return (
            EntryUnknownNoPositionCloseoutCase.CASE_4,
            EntryUnknownNoPositionCloseoutStatus.PREVIOUS_ENTRY_SUMMARY_BLOCKED,
            "HALTED_UNKNOWN_RESULT_SAFE_STOP",
            NEXT_STEP_POST_ENTRY_UNKNOWN_SAFE_STOP,
        )
    if post_entry.position_status is PositionReadOnlyControlledStatus.NO_POSITION:
        return (
            EntryUnknownNoPositionCloseoutCase.CASE_1,
            EntryUnknownNoPositionCloseoutStatus.ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT,
            ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT,
            NEXT_STEP_LEVEL5_FRESH_CYCLE_ENTRY_GATE,
        )
    if post_entry.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        return (
            EntryUnknownNoPositionCloseoutCase.CASE_2,
            EntryUnknownNoPositionCloseoutStatus.POSITION_OPEN_FOUND_NO_CLOSE_POST,
            "POSITION_OPEN_SAFE",
            NEXT_STEP_CLOSE_ORDER_EXECUTION_GATE,
        )
    if (
        post_entry.position_status
        is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    ):
        return (
            EntryUnknownNoPositionCloseoutCase.CASE_3,
            EntryUnknownNoPositionCloseoutStatus
            .MULTIPLE_POSITIONS_MANUAL_CHECK_REQUIRED,
            "HALTED_MANUAL_CHECK_REQUIRED",
            NEXT_STEP_MANUAL_POSITION_RISK_CHECK,
        )
    return (
        EntryUnknownNoPositionCloseoutCase.CASE_4,
        EntryUnknownNoPositionCloseoutStatus
        .UNKNOWN_FAIL_CLOSED_MANUAL_CHECK_REQUIRED,
        "HALTED_UNKNOWN_POSITION",
        NEXT_STEP_POST_ENTRY_UNKNOWN_SAFE_STOP,
    )


def _safe_cycle_next_state(closeout_completed: bool) -> str:
    if not closeout_completed:
        return ""
    result = transition_level5_cycle_state(
        Level5CycleTransitionInput(
            current_state=Level5CycleState.UNKNOWN_RESULT_SAFE_STOP,
            position_status=PositionReadOnlyStatus.NO_POSITION,
            entry_unknown_no_position_closeout_confirmed=True,
        ),
    )
    return result.next_state.value


def _previous_entry_blocked_reasons(
    summary: PreviousEntryPostSafeSummaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not summary.entry_http_post_executed:
        reasons.append("previous_entry_post_not_executed")
    if summary.entry_post_execution_count != 1:
        reasons.append("previous_entry_post_count_not_one")
    if summary.entry_retry_attempted:
        reasons.append("previous_entry_retry_attempted")
    if summary.entry_second_post_attempted:
        reasons.append("previous_entry_second_post_attempted")
    if summary.close_post_executed:
        reasons.append("previous_close_post_executed")
    if summary.ledger_updated:
        reasons.append("previous_ledger_updated")
    if summary.receipt_handoff_executed:
        reasons.append("previous_receipt_handoff_executed")
    if _previous_exposure(summary):
        reasons.append("previous_raw_id_value_exposure_blocked")
    return tuple(reasons)


def _current_step_blocked_reasons(
    snapshot: EntryUnknownNoPositionCloseoutGateInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name, reason in (
        ("actual_entry_post_attempted_this_step", "entry_post_attempted_this_step"),
        ("entry_retry_attempted_this_step", "entry_retry_attempted_this_step"),
        ("entry_repost_attempted_this_step", "entry_repost_attempted_this_step"),
        (
            "second_entry_post_attempted_this_step",
            "second_entry_post_attempted_this_step",
        ),
        ("close_post_attempted_this_step", "close_post_attempted_this_step"),
        ("order_endpoint_called_this_step", "order_endpoint_called_this_step"),
        ("live_order_once_called_this_step", "live_order_once_called_this_step"),
        ("ledger_update_attempted_this_step", "ledger_update_attempted_this_step"),
        ("receipt_handoff_attempted_this_step", "receipt_handoff_attempted_this_step"),
    ):
        if getattr(snapshot, field_name):
            reasons.append(reason)
    if _current_exposure(snapshot):
        reasons.append("current_step_raw_id_value_exposure_blocked")
    return tuple(reasons)


def _manual_ui_blocked_reasons(
    snapshot: ManualOperatorUiSafeCheckInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.operator_broker_ui_values_or_ids_provided:
        reasons.append("manual_ui_values_or_ids_provided")
    return tuple(reasons)


def _post_entry_blocked_reasons(
    post_entry: PostEntryPositionConfirmationGateResult,
) -> tuple[str, ...]:
    if post_entry.position_confirmation_status in {
        PostEntryPositionConfirmationStatus.NO_POSITION_AFTER_ENTRY_POST,
        PostEntryPositionConfirmationStatus.ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE,
        PostEntryPositionConfirmationStatus
        .MULTIPLE_POSITIONS_BLOCKED_MANUAL_CHECK_REQUIRED,
        PostEntryPositionConfirmationStatus.UNKNOWN_FAIL_CLOSED_MANUAL_CHECK_REQUIRED,
    }:
        return ()
    return (post_entry.position_confirmation_status.value.lower(),)


def _manual_ui_confirmation_completed(
    snapshot: ManualOperatorUiSafeCheckInput,
) -> bool:
    return (
        snapshot.operator_broker_ui_checked
        and not snapshot.operator_broker_ui_open_position_visible
        and not snapshot.operator_broker_ui_pending_order_visible
        and not snapshot.operator_broker_ui_values_or_ids_provided
    )


def _previous_exposure(summary: PreviousEntryPostSafeSummaryInput) -> bool:
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


def _current_exposure(snapshot: EntryUnknownNoPositionCloseoutGateInput) -> bool:
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


def _validate_bool_fields(instance: object, fields: tuple[str, ...]) -> None:
    for field_name in fields:
        if not isinstance(getattr(instance, field_name), bool):
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_blocked_reasons(reasons: tuple[str, ...]) -> None:
    if not isinstance(reasons, tuple):
        raise LiveVerificationValidationError("blocked_reasons must be tuple")
    for reason in reasons:
        _require_non_empty("blocked_reason", reason)


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


_MANUAL_UI_INPUT_BOOL_FIELDS = (
    "operator_broker_ui_checked",
    "operator_broker_ui_open_position_visible",
    "operator_broker_ui_pending_order_visible",
    "operator_broker_ui_can_monitor",
    "operator_broker_ui_values_or_ids_provided",
)

_GATE_INPUT_BOOL_FIELDS = (
    "actual_entry_post_attempted_this_step",
    "entry_retry_attempted_this_step",
    "entry_repost_attempted_this_step",
    "second_entry_post_attempted_this_step",
    "close_post_attempted_this_step",
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
    "closeout_gate_ready",
    "previous_entry_post_executed",
    "previous_entry_retry_attempted",
    "previous_entry_second_post_attempted",
    "previous_close_post_executed",
    "previous_ledger_or_receipt_executed",
    "previous_raw_id_value_exposed",
    "credential_presence_available",
    "runtime_position_checked",
    "runtime_read_executed",
    "has_open_position",
    "has_exactly_one_position",
    "has_multiple_positions",
    "entry_effect_confirmed_by_position",
    "entry_unknown_no_position",
    "entry_unknown_no_position_closeout_completed",
    "retry_allowed",
    "repost_allowed",
    "second_entry_allowed",
    "close_post_allowed_now",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "fresh_cycle_may_be_planned",
    "fresh_cycle_requires_new_position_read",
    "fresh_cycle_requires_new_signal",
    "fresh_cycle_requires_new_operator_readiness",
    "fresh_cycle_requires_new_entry_confirmation",
    "fresh_cycle_must_not_reuse_previous_confirmation",
    "fresh_cycle_must_not_reuse_previous_attempt",
    "actual_entry_post_allowed_now",
    "actual_close_post_allowed_now",
    "close_execution_gate_may_be_planned",
    "operator_broker_ui_checked",
    "operator_broker_ui_open_position_visible",
    "operator_broker_ui_pending_order_visible",
    "operator_broker_ui_can_monitor",
    "operator_broker_ui_values_or_ids_provided",
    "manual_ui_confirmation_completed",
    "manual_ui_check_remaining_risk",
    "pending_order_check_required_for_fresh_cycle",
    "manual_ui_pending_order_check_recommended",
    "raw_position_exposed",
    "raw_request_exposed",
    "raw_response_exposed",
    "position_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
    "broker_api_response_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
    "actual_entry_post_executed_this_step",
    "close_post_executed_this_step",
    "retry_or_repost_attempted_this_step",
    "second_entry_post_attempted_this_step",
    "ledger_updated_this_step",
    "receipt_handoff_executed_this_step",
)
