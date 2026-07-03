"""Step 6G post-close position confirmation gate.

This module confirms the effect of a previous single close POST using only a
sanitized runtime position safe-read result. It does not execute close POST,
entry POST, retry, repost, ledger updates, receipt handoff, broker/private API
calls, env reads, or raw ID/value handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_credential_presence_controlled import (
    LiveOrderRealCredentialPresenceControlledResult,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_position_runtime_safe_read_controlled import (
    PositionRuntimeSafeReadControlledResult,
    build_position_runtime_safe_read_controlled,
)

POST_CLOSE_POSITION_CONFIRMATION_GATE_LABEL = (
    "STEP6G_POST_CLOSE_POSITION_CONFIRMATION_GATE_CONTROLLED"
)
PREVIOUS_CLOSE_STEP_LABEL = (
    "Step 6G-PC-OX-R-CLOSE-ORDER-EXECUTION-GATE-C-RETRY-WITH-"
    "COMPATIBLE-EXECUTOR"
)
FRESH_ENTRY_RESULT_ACCEPTED = "RESULT_ACCEPTED_SANITIZED"
CLOSE_RESULT_ACCEPTED = "RESULT_ACCEPTED_SANITIZED"
CLOSE_SAFE_RECONCILIATION_READY = "RECONCILIATION_READY_NO_RECEIPT_HANDOFF"

NEXT_STEP_LEVEL5_CYCLE_COMPLETION_HANDOFF = (
    "Step 6G-PC-OX-R-LEVEL5-CYCLE-COMPLETION-HANDOFF-C"
)
NEXT_STEP_CLOSE_ACCEPTED_POSITION_STILL_OPEN_SAFE_STOP = (
    "Step 6G-PC-OX-R-CLOSE-ACCEPTED-POSITION-STILL-OPEN-SAFE-STOP-GATE-C"
)
NEXT_STEP_MANUAL_POSITION_RISK_CHECK = (
    "Step 6G-PC-OX-R-MANUAL-POSITION-RISK-CHECK-GATE-C"
)
NEXT_STEP_POST_CLOSE_UNKNOWN_SAFE_STOP = (
    "Step 6G-PC-OX-R-POST-CLOSE-UNKNOWN-RESULT-SAFE-STOP-GATE-C"
)
NEXT_STEP_CREDENTIAL_OPERATOR_ACTION = (
    "Step 6G-PC-OX-R-POST-CLOSE-CREDENTIAL-PRESENCE-OPERATOR-ACTION-C"
)


class PostClosePositionConfirmationGateCase(str, Enum):
    CASE_1 = "CASE 1"
    CASE_2 = "CASE 2"
    CASE_3 = "CASE 3"
    CASE_4 = "CASE 4"


class PostClosePositionConfirmationStatus(str, Enum):
    NO_POSITION_AFTER_CLOSE_POST_LEVEL5_COMPLETED = (
        "NO_POSITION_AFTER_CLOSE_POST_LEVEL5_COMPLETED"
    )
    CLOSE_ACCEPTED_BUT_POSITION_STILL_VISIBLE_SAFE_STOP = (
        "CLOSE_ACCEPTED_BUT_POSITION_STILL_VISIBLE_SAFE_STOP"
    )
    POST_CLOSE_MULTIPLE_POSITIONS_BLOCKED = (
        "POST_CLOSE_MULTIPLE_POSITIONS_BLOCKED"
    )
    POST_CLOSE_POSITION_UNKNOWN_FAIL_CLOSED = (
        "POST_CLOSE_POSITION_UNKNOWN_FAIL_CLOSED"
    )
    CREDENTIAL_PRESENCE_BLOCKED = "CREDENTIAL_PRESENCE_BLOCKED"
    PREVIOUS_ENTRY_CLOSE_SUMMARY_BLOCKED = (
        "PREVIOUS_ENTRY_CLOSE_SUMMARY_BLOCKED"
    )
    UNSAFE_EXPOSURE_BLOCKED = "UNSAFE_EXPOSURE_BLOCKED"


@dataclass(frozen=True)
class PreviousEntryClosePostSafeSummaryInput:
    previous_close_step: str = PREVIOUS_CLOSE_STEP_LABEL
    fresh_entry_http_post_executed: bool = True
    fresh_entry_post_execution_count: int = 1
    fresh_entry_sanitized_result_category: str = FRESH_ENTRY_RESULT_ACCEPTED
    fresh_entry_retry_attempted: bool = False
    fresh_entry_repost_attempted: bool = False
    fresh_entry_second_post_attempted: bool = False
    close_http_post_executed: bool = True
    close_post_execution_count: int = 1
    close_result_safe_status: str = (
        "ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY"
    )
    close_sanitized_result_category: str = CLOSE_RESULT_ACCEPTED
    close_safe_reconciliation_status: str = CLOSE_SAFE_RECONCILIATION_READY
    close_retry_attempted: bool = False
    close_repost_attempted: bool = False
    close_second_post_attempted: bool = False
    ledger_updated: bool = False
    receipt_handoff_executed: bool = False
    raw_request_exposed: bool = False
    raw_response_exposed: bool = False
    broker_api_response_exposed: bool = False
    credential_value_exposed: bool = False
    signature_value_exposed: bool = False
    headers_value_exposed: bool = False
    real_id_exposed: bool = False
    account_id_exposed: bool = False
    order_id_exposed: bool = False
    transaction_id_exposed: bool = False
    position_id_exposed: bool = False
    client_order_id_actual_value_exposed: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("previous_close_step", self.previous_close_step)
        _require_non_empty(
            "fresh_entry_sanitized_result_category",
            self.fresh_entry_sanitized_result_category,
        )
        _require_non_empty("close_result_safe_status", self.close_result_safe_status)
        _require_non_empty(
            "close_sanitized_result_category",
            self.close_sanitized_result_category,
        )
        _require_non_empty(
            "close_safe_reconciliation_status",
            self.close_safe_reconciliation_status,
        )
        _validate_non_negative_int(
            "fresh_entry_post_execution_count",
            self.fresh_entry_post_execution_count,
        )
        _validate_non_negative_int(
            "close_post_execution_count",
            self.close_post_execution_count,
        )
        _validate_bool_fields(self, _PREVIOUS_ENTRY_CLOSE_BOOL_FIELDS)


@dataclass(frozen=True)
class PostClosePositionConfirmationGateInput:
    previous_summary: PreviousEntryClosePostSafeSummaryInput = field(
        default_factory=PreviousEntryClosePostSafeSummaryInput,
    )
    actual_close_post_attempted_this_step: bool = False
    close_retry_attempted_this_step: bool = False
    close_repost_attempted_this_step: bool = False
    second_close_post_attempted_this_step: bool = False
    actual_entry_post_attempted_this_step: bool = False
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
        if not isinstance(
            self.previous_summary,
            PreviousEntryClosePostSafeSummaryInput,
        ):
            raise LiveVerificationValidationError(
                "previous_summary must be PreviousEntryClosePostSafeSummaryInput",
            )
        _validate_bool_fields(self, _GATE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class PostClosePositionConfirmationGateResult:
    gate_label: str
    case: PostClosePositionConfirmationGateCase
    position_confirmation_status: PostClosePositionConfirmationStatus
    previous_close_step: str
    fresh_entry_http_post_executed: bool
    fresh_entry_post_execution_count: int
    fresh_entry_sanitized_result_category: str
    fresh_entry_retry_attempted: bool
    fresh_entry_repost_attempted: bool
    fresh_entry_second_post_attempted: bool
    close_http_post_executed: bool
    close_post_execution_count: int
    close_result_safe_status: str
    close_sanitized_result_category: str
    close_safe_reconciliation_status: str
    close_retry_attempted: bool
    close_repost_attempted: bool
    close_second_post_attempted: bool
    ledger_updated: bool
    receipt_handoff_executed: bool
    credential_presence_available: bool
    runtime_read_executed: bool
    position_source_checked: bool
    position_status_checked: bool
    position_status: PositionReadOnlyControlledStatus
    position_count_safe: int
    has_open_position: bool
    has_exactly_one_position: bool
    has_multiple_positions: bool
    new_entry_allowed: bool
    close_planning_allowed: bool
    close_execution_allowed_now: bool
    max_open_positions: int
    close_effect_confirmed_by_position: bool
    post_close_position_status: str
    next_cycle_state: str
    level5_minimal_cycle_completed: bool
    level5_full_auto_cycle_completed: bool
    entry_post_executed_once: bool
    close_post_executed_once: bool
    retry_repost_second_post_all_false: bool
    ledger_receipt_executed: bool
    retry_allowed: bool
    repost_allowed: bool
    second_close_allowed: bool
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
    actual_close_post_executed_this_step: bool
    actual_entry_post_executed_this_step: bool
    close_retry_or_repost_attempted_this_step: bool
    second_close_post_attempted_this_step: bool
    ledger_updated_this_step: bool
    receipt_handoff_executed_this_step: bool
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("gate_label", self.gate_label)
        if not isinstance(self.case, PostClosePositionConfirmationGateCase):
            raise LiveVerificationValidationError("case must be post-close enum")
        if not isinstance(
            self.position_confirmation_status,
            PostClosePositionConfirmationStatus,
        ):
            raise LiveVerificationValidationError(
                "position_confirmation_status must be post-close status enum",
            )
        if not isinstance(self.position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "position_status must be controlled enum",
            )
        _require_non_empty("post_close_position_status", self.post_close_position_status)
        _require_non_empty("next_cycle_state", self.next_cycle_state)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_non_negative_int(
            "fresh_entry_post_execution_count",
            self.fresh_entry_post_execution_count,
        )
        _validate_non_negative_int(
            "close_post_execution_count",
            self.close_post_execution_count,
        )
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("max_open_positions", self.max_open_positions)
        _validate_bool_fields(self, _GATE_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_post_close_position_confirmation_gate_controlled(
    input_snapshot: PostClosePositionConfirmationGateInput | None = None,
    *,
    runtime_result: PositionRuntimeSafeReadControlledResult | None = None,
    credential_presence_result: LiveOrderRealCredentialPresenceControlledResult
    | None = None,
) -> PostClosePositionConfirmationGateResult:
    snapshot = input_snapshot or PostClosePositionConfirmationGateInput()
    runtime = runtime_result or build_position_runtime_safe_read_controlled(
        credential_presence_result=credential_presence_result,
    )
    previous_reasons = _previous_summary_blocked_reasons(snapshot.previous_summary)
    current_reasons = _current_step_blocked_reasons(snapshot)
    case, status, post_close_status, next_state, next_step = _case_status_and_next_step(
        runtime=runtime,
        previous_reasons=previous_reasons,
        current_reasons=current_reasons,
    )
    close_confirmed = (
        status
        is PostClosePositionConfirmationStatus
        .NO_POSITION_AFTER_CLOSE_POST_LEVEL5_COMPLETED
    )
    entry_once = _entry_post_executed_once(snapshot.previous_summary)
    close_once = _close_post_executed_once(snapshot.previous_summary)
    retry_all_false = _retry_repost_second_all_false(snapshot.previous_summary)
    ledger_receipt_executed = (
        snapshot.previous_summary.ledger_updated
        or snapshot.previous_summary.receipt_handoff_executed
    )
    blocked_reasons = tuple(
        dict.fromkeys(
            (
                *previous_reasons,
                *current_reasons,
                *runtime.blocked_reasons,
            ),
        ),
    )
    return PostClosePositionConfirmationGateResult(
        gate_label=POST_CLOSE_POSITION_CONFIRMATION_GATE_LABEL,
        case=case,
        position_confirmation_status=status,
        previous_close_step=snapshot.previous_summary.previous_close_step,
        fresh_entry_http_post_executed=(
            snapshot.previous_summary.fresh_entry_http_post_executed
        ),
        fresh_entry_post_execution_count=(
            snapshot.previous_summary.fresh_entry_post_execution_count
        ),
        fresh_entry_sanitized_result_category=(
            snapshot.previous_summary.fresh_entry_sanitized_result_category
        ),
        fresh_entry_retry_attempted=(
            snapshot.previous_summary.fresh_entry_retry_attempted
        ),
        fresh_entry_repost_attempted=(
            snapshot.previous_summary.fresh_entry_repost_attempted
        ),
        fresh_entry_second_post_attempted=(
            snapshot.previous_summary.fresh_entry_second_post_attempted
        ),
        close_http_post_executed=snapshot.previous_summary.close_http_post_executed,
        close_post_execution_count=(
            snapshot.previous_summary.close_post_execution_count
        ),
        close_result_safe_status=snapshot.previous_summary.close_result_safe_status,
        close_sanitized_result_category=(
            snapshot.previous_summary.close_sanitized_result_category
        ),
        close_safe_reconciliation_status=(
            snapshot.previous_summary.close_safe_reconciliation_status
        ),
        close_retry_attempted=snapshot.previous_summary.close_retry_attempted,
        close_repost_attempted=snapshot.previous_summary.close_repost_attempted,
        close_second_post_attempted=(
            snapshot.previous_summary.close_second_post_attempted
        ),
        ledger_updated=snapshot.previous_summary.ledger_updated,
        receipt_handoff_executed=(
            snapshot.previous_summary.receipt_handoff_executed
        ),
        credential_presence_available=runtime.credential_presence_available,
        runtime_read_executed=runtime.runtime_read_executed,
        position_source_checked=runtime.position_source_checked,
        position_status_checked=runtime.position_status_checked,
        position_status=runtime.position_status,
        position_count_safe=runtime.position_count_safe,
        has_open_position=runtime.has_open_position,
        has_exactly_one_position=runtime.has_exactly_one_position,
        has_multiple_positions=runtime.has_multiple_positions,
        new_entry_allowed=False,
        close_planning_allowed=False,
        close_execution_allowed_now=False,
        max_open_positions=1,
        close_effect_confirmed_by_position=close_confirmed,
        post_close_position_status=post_close_status,
        next_cycle_state=next_state,
        level5_minimal_cycle_completed=close_confirmed,
        level5_full_auto_cycle_completed=close_confirmed,
        entry_post_executed_once=entry_once,
        close_post_executed_once=close_once,
        retry_repost_second_post_all_false=retry_all_false,
        ledger_receipt_executed=ledger_receipt_executed,
        retry_allowed=False,
        repost_allowed=False,
        second_close_allowed=False,
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
        actual_close_post_executed_this_step=False,
        actual_entry_post_executed_this_step=False,
        close_retry_or_repost_attempted_this_step=False,
        second_close_post_attempted_this_step=False,
        ledger_updated_this_step=False,
        receipt_handoff_executed_this_step=False,
        recommended_next_step=next_step,
        blocked_reasons=blocked_reasons,
    )


def render_post_close_position_confirmation_gate_markdown(
    result: PostClosePositionConfirmationGateResult,
) -> str:
    """Render safe post-close position confirmation fields only."""
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Post-Close Position Confirmation Gate",
            "",
            "This gate confirms a previous single close POST using safe position",
            "status/count only. It does not retry close POST, execute entry POST,",
            "update ledger state, hand off receipts, or expose raw/ID/value data.",
            "",
            f"case: {result.case.value}",
            f"position_confirmation_status: {result.position_confirmation_status.value}",
            (
                "fresh_entry_http_post_executed: "
                f"{_bool_text(result.fresh_entry_http_post_executed)}"
            ),
            (
                "fresh_entry_post_execution_count: "
                f"{result.fresh_entry_post_execution_count}"
            ),
            f"close_http_post_executed: {_bool_text(result.close_http_post_executed)}",
            f"close_post_execution_count: {result.close_post_execution_count}",
            f"close_sanitized_result_category: {result.close_sanitized_result_category}",
            (
                "close_safe_reconciliation_status: "
                f"{result.close_safe_reconciliation_status}"
            ),
            (
                "credential_presence_available: "
                f"{_bool_text(result.credential_presence_available)}"
            ),
            f"runtime_read_executed: {_bool_text(result.runtime_read_executed)}",
            f"position_source_checked: {_bool_text(result.position_source_checked)}",
            f"position_status_checked: {_bool_text(result.position_status_checked)}",
            f"position_status: {result.position_status.value}",
            f"position_count_safe: {result.position_count_safe}",
            f"has_open_position: {_bool_text(result.has_open_position)}",
            (
                "has_exactly_one_position: "
                f"{_bool_text(result.has_exactly_one_position)}"
            ),
            f"has_multiple_positions: {_bool_text(result.has_multiple_positions)}",
            f"new_entry_allowed: {_bool_text(result.new_entry_allowed)}",
            f"close_planning_allowed: {_bool_text(result.close_planning_allowed)}",
            (
                "close_execution_allowed_now: "
                f"{_bool_text(result.close_execution_allowed_now)}"
            ),
            (
                "close_effect_confirmed_by_position: "
                f"{_bool_text(result.close_effect_confirmed_by_position)}"
            ),
            f"post_close_position_status: {result.post_close_position_status}",
            f"next_cycle_state: {result.next_cycle_state}",
            (
                "level5_minimal_cycle_completed: "
                f"{_bool_text(result.level5_minimal_cycle_completed)}"
            ),
            (
                "level5_full_auto_cycle_completed: "
                f"{_bool_text(result.level5_full_auto_cycle_completed)}"
            ),
            f"retry_allowed: {_bool_text(result.retry_allowed)}",
            f"repost_allowed: {_bool_text(result.repost_allowed)}",
            f"second_close_allowed: {_bool_text(result.second_close_allowed)}",
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
    PostClosePositionConfirmationGateCase,
    PostClosePositionConfirmationStatus,
    str,
    str,
    str,
]:
    if previous_reasons:
        return (
            PostClosePositionConfirmationGateCase.CASE_4,
            PostClosePositionConfirmationStatus.PREVIOUS_ENTRY_CLOSE_SUMMARY_BLOCKED,
            "POST_CLOSE_POSITION_UNKNOWN_FAIL_CLOSED",
            "HALTED_UNKNOWN_POSITION",
            NEXT_STEP_POST_CLOSE_UNKNOWN_SAFE_STOP,
        )
    if current_reasons:
        return (
            PostClosePositionConfirmationGateCase.CASE_4,
            PostClosePositionConfirmationStatus.UNSAFE_EXPOSURE_BLOCKED,
            "POST_CLOSE_POSITION_UNKNOWN_FAIL_CLOSED",
            "HALTED_UNKNOWN_POSITION",
            NEXT_STEP_POST_CLOSE_UNKNOWN_SAFE_STOP,
        )
    if (
        not runtime.credential_presence_available
        or not runtime.all_required_credentials_present
    ):
        return (
            PostClosePositionConfirmationGateCase.CASE_4,
            PostClosePositionConfirmationStatus.CREDENTIAL_PRESENCE_BLOCKED,
            "POST_CLOSE_POSITION_UNKNOWN_FAIL_CLOSED",
            "HALTED_CREDENTIAL_REQUIRED",
            NEXT_STEP_CREDENTIAL_OPERATOR_ACTION,
        )
    if runtime.position_status is PositionReadOnlyControlledStatus.NO_POSITION:
        return (
            PostClosePositionConfirmationGateCase.CASE_1,
            PostClosePositionConfirmationStatus
            .NO_POSITION_AFTER_CLOSE_POST_LEVEL5_COMPLETED,
            "NO_POSITION_AFTER_CLOSE_POST",
            "LEVEL5_MINIMAL_CYCLE_COMPLETED",
            NEXT_STEP_LEVEL5_CYCLE_COMPLETION_HANDOFF,
        )
    if runtime.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        return (
            PostClosePositionConfirmationGateCase.CASE_2,
            PostClosePositionConfirmationStatus
            .CLOSE_ACCEPTED_BUT_POSITION_STILL_VISIBLE_SAFE_STOP,
            "CLOSE_ACCEPTED_BUT_POSITION_STILL_VISIBLE_SAFE_STOP",
            "CLOSE_ACCEPTED_POSITION_STILL_VISIBLE_SAFE_STOP",
            NEXT_STEP_CLOSE_ACCEPTED_POSITION_STILL_OPEN_SAFE_STOP,
        )
    if (
        runtime.position_status
        is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    ):
        return (
            PostClosePositionConfirmationGateCase.CASE_3,
            PostClosePositionConfirmationStatus.POST_CLOSE_MULTIPLE_POSITIONS_BLOCKED,
            "POST_CLOSE_MULTIPLE_POSITIONS_BLOCKED",
            "HALTED_MANUAL_CHECK_REQUIRED",
            NEXT_STEP_MANUAL_POSITION_RISK_CHECK,
        )
    return (
        PostClosePositionConfirmationGateCase.CASE_4,
        PostClosePositionConfirmationStatus.POST_CLOSE_POSITION_UNKNOWN_FAIL_CLOSED,
        "POST_CLOSE_POSITION_UNKNOWN_FAIL_CLOSED",
        "HALTED_UNKNOWN_POSITION",
        NEXT_STEP_POST_CLOSE_UNKNOWN_SAFE_STOP,
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
    if summary.close_safe_reconciliation_status != CLOSE_SAFE_RECONCILIATION_READY:
        reasons.append("close_safe_reconciliation_not_ready")
    if not _retry_repost_second_all_false(summary):
        reasons.append("retry_repost_or_second_post_attempted")
    if summary.ledger_updated or summary.receipt_handoff_executed:
        reasons.append("ledger_or_receipt_executed")
    if _previous_exposure(summary):
        reasons.append("previous_raw_id_value_exposure_blocked")
    return tuple(reasons)


def _current_step_blocked_reasons(
    snapshot: PostClosePositionConfirmationGateInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name, reason in (
        ("actual_close_post_attempted_this_step", "close_post_attempted_this_step"),
        ("close_retry_attempted_this_step", "close_retry_attempted_this_step"),
        ("close_repost_attempted_this_step", "close_repost_attempted_this_step"),
        (
            "second_close_post_attempted_this_step",
            "second_close_post_attempted_this_step",
        ),
        ("actual_entry_post_attempted_this_step", "entry_post_attempted_this_step"),
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


def _entry_post_executed_once(summary: PreviousEntryClosePostSafeSummaryInput) -> bool:
    return (
        summary.fresh_entry_http_post_executed
        and summary.fresh_entry_post_execution_count == 1
    )


def _close_post_executed_once(summary: PreviousEntryClosePostSafeSummaryInput) -> bool:
    return summary.close_http_post_executed and summary.close_post_execution_count == 1


def _retry_repost_second_all_false(
    summary: PreviousEntryClosePostSafeSummaryInput,
) -> bool:
    return not any(
        (
            summary.fresh_entry_retry_attempted,
            summary.fresh_entry_repost_attempted,
            summary.fresh_entry_second_post_attempted,
            summary.close_retry_attempted,
            summary.close_repost_attempted,
            summary.close_second_post_attempted,
        ),
    )


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


def _current_exposure(snapshot: PostClosePositionConfirmationGateInput) -> bool:
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


_PREVIOUS_ENTRY_CLOSE_BOOL_FIELDS = (
    "fresh_entry_http_post_executed",
    "fresh_entry_retry_attempted",
    "fresh_entry_repost_attempted",
    "fresh_entry_second_post_attempted",
    "close_http_post_executed",
    "close_retry_attempted",
    "close_repost_attempted",
    "close_second_post_attempted",
    "ledger_updated",
    "receipt_handoff_executed",
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

_GATE_INPUT_BOOL_FIELDS = (
    "actual_close_post_attempted_this_step",
    "close_retry_attempted_this_step",
    "close_repost_attempted_this_step",
    "second_close_post_attempted_this_step",
    "actual_entry_post_attempted_this_step",
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
    "fresh_entry_http_post_executed",
    "fresh_entry_retry_attempted",
    "fresh_entry_repost_attempted",
    "fresh_entry_second_post_attempted",
    "close_http_post_executed",
    "close_retry_attempted",
    "close_repost_attempted",
    "close_second_post_attempted",
    "ledger_updated",
    "receipt_handoff_executed",
    "credential_presence_available",
    "runtime_read_executed",
    "position_source_checked",
    "position_status_checked",
    "has_open_position",
    "has_exactly_one_position",
    "has_multiple_positions",
    "new_entry_allowed",
    "close_planning_allowed",
    "close_execution_allowed_now",
    "close_effect_confirmed_by_position",
    "level5_minimal_cycle_completed",
    "level5_full_auto_cycle_completed",
    "entry_post_executed_once",
    "close_post_executed_once",
    "retry_repost_second_post_all_false",
    "ledger_receipt_executed",
    "retry_allowed",
    "repost_allowed",
    "second_close_allowed",
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
    "actual_close_post_executed_this_step",
    "actual_entry_post_executed_this_step",
    "close_retry_or_repost_attempted_this_step",
    "second_close_post_attempted_this_step",
    "ledger_updated_this_step",
    "receipt_handoff_executed_this_step",
)
