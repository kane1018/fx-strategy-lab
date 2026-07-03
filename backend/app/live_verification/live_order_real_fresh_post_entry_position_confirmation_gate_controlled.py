"""Fresh Step 6G post-entry position confirmation gate.

This module confirms a fresh accepted entry POST effect using only a sanitized
runtime position safe-read result. It never executes entry POST, close POST,
retry, repost, ledger updates, receipt handoff, broker/private API calls, env
reads, or raw ID/value handling.
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
from app.live_verification.live_order_real_sanitized_post_result import (
    SafePostResultCategory,
    SafeReconciliationStatus,
)

FRESH_POST_ENTRY_POSITION_CONFIRMATION_GATE_LABEL = (
    "STEP6G_FRESH_POST_ENTRY_POSITION_CONFIRMATION_GATE_CONTROLLED"
)
PREVIOUS_FRESH_ENTRY_STEP_LABEL = (
    "Step 6G-PC-OX-R-LEVEL5-FRESH-CYCLE-ENTRY-GATE-C"
)
PREVIOUS_FRESH_ENTRY_CASE_LABEL = "CASE 1"
FRESH_ENTRY_SAFE_STATUS_ACCEPTED = (
    "ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY"
)

NEXT_STEP_FRESH_POSITION_OPEN_SAFE_HANDOFF = (
    "Step 6G-PC-OX-R-FRESH-POSITION-OPEN-SAFE-HANDOFF-GATE-C"
)
NEXT_STEP_FRESH_ACCEPTED_NO_POSITION_SAFE_STOP = (
    "Step 6G-PC-OX-R-FRESH-ENTRY-ACCEPTED-NO-POSITION-SAFE-STOP-GATE-C"
)
NEXT_STEP_MANUAL_POSITION_RISK_CHECK = (
    "Step 6G-PC-OX-R-MANUAL-POSITION-RISK-CHECK-GATE-C"
)
NEXT_STEP_FRESH_POST_ENTRY_UNKNOWN_SAFE_STOP = (
    "Step 6G-PC-OX-R-FRESH-POST-ENTRY-UNKNOWN-RESULT-SAFE-STOP-GATE-C"
)
NEXT_STEP_CREDENTIAL_OPERATOR_ACTION = (
    "Step 6G-PC-OX-R-FRESH-POST-ENTRY-CREDENTIAL-OPERATOR-ACTION-C"
)


class FreshPostEntryPositionConfirmationGateCase(str, Enum):
    CASE_1 = "CASE 1"
    CASE_2 = "CASE 2"
    CASE_3 = "CASE 3"
    CASE_4 = "CASE 4"


class FreshPostEntryPositionConfirmationStatus(str, Enum):
    FRESH_ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE = (
        "FRESH_ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE"
    )
    FRESH_ACCEPTED_BUT_NO_POSITION_VISIBLE_SAFE_STOP = (
        "FRESH_ACCEPTED_BUT_NO_POSITION_VISIBLE_SAFE_STOP"
    )
    FRESH_MULTIPLE_POSITIONS_BLOCKED = "FRESH_MULTIPLE_POSITIONS_BLOCKED"
    FRESH_POSITION_UNKNOWN_FAIL_CLOSED = "FRESH_POSITION_UNKNOWN_FAIL_CLOSED"
    CREDENTIAL_PRESENCE_BLOCKED = "CREDENTIAL_PRESENCE_BLOCKED"
    FRESH_ENTRY_SUMMARY_BLOCKED = "FRESH_ENTRY_SUMMARY_BLOCKED"
    UNSAFE_EXPOSURE_BLOCKED = "UNSAFE_EXPOSURE_BLOCKED"


@dataclass(frozen=True)
class FreshEntryPostSafeSummaryInput:
    previous_step: str = PREVIOUS_FRESH_ENTRY_STEP_LABEL
    previous_case: str = PREVIOUS_FRESH_ENTRY_CASE_LABEL
    fresh_cycle: bool = True
    previous_attempt_retry: bool = False
    previous_attempt_repost: bool = False
    fresh_entry_http_post_executed: bool = True
    fresh_entry_post_execution_count: int = 1
    fresh_entry_result_safe_status: str = FRESH_ENTRY_SAFE_STATUS_ACCEPTED
    fresh_entry_sanitized_result_category: str = (
        SafePostResultCategory.RESULT_ACCEPTED_SANITIZED.value
    )
    fresh_entry_safe_reconciliation_status: str = (
        SafeReconciliationStatus.RECONCILIATION_READY_NO_RECEIPT_HANDOFF.value
    )
    fresh_entry_retry_attempted: bool = False
    fresh_entry_repost_attempted: bool = False
    fresh_entry_second_post_attempted: bool = False
    close_post_executed: bool = False
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
        _require_non_empty("previous_step", self.previous_step)
        _require_non_empty("previous_case", self.previous_case)
        _require_non_empty(
            "fresh_entry_result_safe_status",
            self.fresh_entry_result_safe_status,
        )
        _require_non_empty(
            "fresh_entry_sanitized_result_category",
            self.fresh_entry_sanitized_result_category,
        )
        _require_non_empty(
            "fresh_entry_safe_reconciliation_status",
            self.fresh_entry_safe_reconciliation_status,
        )
        _validate_non_negative_int(
            "fresh_entry_post_execution_count",
            self.fresh_entry_post_execution_count,
        )
        _validate_bool_fields(self, _FRESH_ENTRY_SUMMARY_BOOL_FIELDS)


@dataclass(frozen=True)
class FreshPostEntryPositionConfirmationGateInput:
    fresh_entry_summary: FreshEntryPostSafeSummaryInput = field(
        default_factory=FreshEntryPostSafeSummaryInput,
    )
    fresh_entry_post_attempted_this_step: bool = False
    fresh_entry_retry_attempted_this_step: bool = False
    fresh_entry_repost_attempted_this_step: bool = False
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
        if not isinstance(self.fresh_entry_summary, FreshEntryPostSafeSummaryInput):
            raise LiveVerificationValidationError(
                "fresh_entry_summary must be FreshEntryPostSafeSummaryInput",
            )
        _validate_bool_fields(self, _GATE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class FreshPostEntryPositionConfirmationGateResult:
    gate_label: str
    case: FreshPostEntryPositionConfirmationGateCase
    fresh_position_confirmation_status: FreshPostEntryPositionConfirmationStatus
    previous_step: str
    previous_case: str
    fresh_cycle: bool
    previous_attempt_retry: bool
    previous_attempt_repost: bool
    fresh_entry_http_post_executed: bool
    fresh_entry_post_execution_count: int
    fresh_entry_result_safe_status: str
    fresh_entry_sanitized_result_category: str
    fresh_entry_safe_reconciliation_status: str
    fresh_entry_retry_attempted: bool
    fresh_entry_repost_attempted: bool
    fresh_entry_second_post_attempted: bool
    close_post_executed: bool
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
    fresh_entry_effect_confirmed_by_position: bool
    next_cycle_state: str
    close_execution_gate_may_be_planned: bool
    retry_allowed: bool
    repost_allowed: bool
    second_entry_allowed: bool
    close_post_allowed_now: bool
    level5_full_auto_cycle_completed: bool
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
    fresh_entry_post_executed_this_step: bool
    close_post_executed_this_step: bool
    retry_or_repost_attempted_this_step: bool
    second_entry_post_attempted_this_step: bool
    ledger_updated_this_step: bool
    receipt_handoff_executed_this_step: bool
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("gate_label", self.gate_label)
        if not isinstance(self.case, FreshPostEntryPositionConfirmationGateCase):
            raise LiveVerificationValidationError("case must be fresh gate enum")
        if not isinstance(
            self.fresh_position_confirmation_status,
            FreshPostEntryPositionConfirmationStatus,
        ):
            raise LiveVerificationValidationError(
                "fresh_position_confirmation_status must be fresh status enum",
            )
        if not isinstance(self.position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "position_status must be controlled enum",
            )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _require_non_empty("next_cycle_state", self.next_cycle_state)
        _validate_non_negative_int(
            "fresh_entry_post_execution_count",
            self.fresh_entry_post_execution_count,
        )
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("max_open_positions", self.max_open_positions)
        _validate_bool_fields(self, _GATE_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_fresh_post_entry_position_confirmation_gate_controlled(
    input_snapshot: FreshPostEntryPositionConfirmationGateInput | None = None,
    *,
    runtime_result: PositionRuntimeSafeReadControlledResult | None = None,
    credential_presence_result: LiveOrderRealCredentialPresenceControlledResult
    | None = None,
) -> FreshPostEntryPositionConfirmationGateResult:
    snapshot = input_snapshot or FreshPostEntryPositionConfirmationGateInput()
    runtime = runtime_result or build_position_runtime_safe_read_controlled(
        credential_presence_result=credential_presence_result,
    )
    previous_reasons = _fresh_entry_summary_blocked_reasons(
        snapshot.fresh_entry_summary,
    )
    current_reasons = _current_step_blocked_reasons(snapshot)
    case, status, next_state, next_step = _case_status_and_next_step(
        runtime=runtime,
        previous_reasons=previous_reasons,
        current_reasons=current_reasons,
    )
    confirmed = status is (
        FreshPostEntryPositionConfirmationStatus
        .FRESH_ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE
    )
    can_plan_close = confirmed and runtime.has_exactly_one_position
    blocked_reasons = tuple(
        dict.fromkeys(
            (
                *previous_reasons,
                *current_reasons,
                *runtime.blocked_reasons,
            ),
        ),
    )
    summary = snapshot.fresh_entry_summary
    return FreshPostEntryPositionConfirmationGateResult(
        gate_label=FRESH_POST_ENTRY_POSITION_CONFIRMATION_GATE_LABEL,
        case=case,
        fresh_position_confirmation_status=status,
        previous_step=summary.previous_step,
        previous_case=summary.previous_case,
        fresh_cycle=summary.fresh_cycle,
        previous_attempt_retry=summary.previous_attempt_retry,
        previous_attempt_repost=summary.previous_attempt_repost,
        fresh_entry_http_post_executed=summary.fresh_entry_http_post_executed,
        fresh_entry_post_execution_count=summary.fresh_entry_post_execution_count,
        fresh_entry_result_safe_status=summary.fresh_entry_result_safe_status,
        fresh_entry_sanitized_result_category=(
            summary.fresh_entry_sanitized_result_category
        ),
        fresh_entry_safe_reconciliation_status=(
            summary.fresh_entry_safe_reconciliation_status
        ),
        fresh_entry_retry_attempted=summary.fresh_entry_retry_attempted,
        fresh_entry_repost_attempted=summary.fresh_entry_repost_attempted,
        fresh_entry_second_post_attempted=summary.fresh_entry_second_post_attempted,
        close_post_executed=summary.close_post_executed,
        ledger_updated=summary.ledger_updated,
        receipt_handoff_executed=summary.receipt_handoff_executed,
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
        close_planning_allowed=can_plan_close,
        close_execution_allowed_now=False,
        max_open_positions=1,
        fresh_entry_effect_confirmed_by_position=confirmed,
        next_cycle_state=next_state,
        close_execution_gate_may_be_planned=can_plan_close,
        retry_allowed=False,
        repost_allowed=False,
        second_entry_allowed=False,
        close_post_allowed_now=False,
        level5_full_auto_cycle_completed=False,
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
        fresh_entry_post_executed_this_step=False,
        close_post_executed_this_step=False,
        retry_or_repost_attempted_this_step=False,
        second_entry_post_attempted_this_step=False,
        ledger_updated_this_step=False,
        receipt_handoff_executed_this_step=False,
        recommended_next_step=next_step,
        blocked_reasons=blocked_reasons,
    )


def render_fresh_post_entry_position_confirmation_gate_markdown(
    result: FreshPostEntryPositionConfirmationGateResult,
) -> str:
    """Render safe fresh post-entry position confirmation fields only."""
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Fresh Post-Entry Position Confirmation Gate",
            "",
            "This gate confirms a fresh accepted entry POST using safe position",
            "status/count only. It does not retry entry POST, execute close POST,",
            "update ledger state, hand off receipts, or expose raw/ID/value data.",
            "",
            f"case: {result.case.value}",
            (
                "fresh_position_confirmation_status: "
                f"{result.fresh_position_confirmation_status.value}"
            ),
            (
                "fresh_entry_http_post_executed: "
                f"{_bool_text(result.fresh_entry_http_post_executed)}"
            ),
            (
                "fresh_entry_post_execution_count: "
                f"{result.fresh_entry_post_execution_count}"
            ),
            (
                "fresh_entry_sanitized_result_category: "
                f"{result.fresh_entry_sanitized_result_category}"
            ),
            (
                "fresh_entry_retry_attempted: "
                f"{_bool_text(result.fresh_entry_retry_attempted)}"
            ),
            (
                "fresh_entry_repost_attempted: "
                f"{_bool_text(result.fresh_entry_repost_attempted)}"
            ),
            (
                "fresh_entry_second_post_attempted: "
                f"{_bool_text(result.fresh_entry_second_post_attempted)}"
            ),
            f"close_post_executed: {_bool_text(result.close_post_executed)}",
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
                "fresh_entry_effect_confirmed_by_position: "
                f"{_bool_text(result.fresh_entry_effect_confirmed_by_position)}"
            ),
            f"next_cycle_state: {result.next_cycle_state}",
            (
                "close_execution_gate_may_be_planned: "
                f"{_bool_text(result.close_execution_gate_may_be_planned)}"
            ),
            f"retry_allowed: {_bool_text(result.retry_allowed)}",
            f"repost_allowed: {_bool_text(result.repost_allowed)}",
            f"second_entry_allowed: {_bool_text(result.second_entry_allowed)}",
            f"close_post_allowed_now: {_bool_text(result.close_post_allowed_now)}",
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
    FreshPostEntryPositionConfirmationGateCase,
    FreshPostEntryPositionConfirmationStatus,
    str,
    str,
]:
    if previous_reasons:
        return (
            FreshPostEntryPositionConfirmationGateCase.CASE_4,
            FreshPostEntryPositionConfirmationStatus.FRESH_ENTRY_SUMMARY_BLOCKED,
            "HALTED_UNKNOWN_POSITION",
            NEXT_STEP_FRESH_POST_ENTRY_UNKNOWN_SAFE_STOP,
        )
    if current_reasons:
        return (
            FreshPostEntryPositionConfirmationGateCase.CASE_4,
            FreshPostEntryPositionConfirmationStatus.UNSAFE_EXPOSURE_BLOCKED,
            "HALTED_UNKNOWN_POSITION",
            NEXT_STEP_FRESH_POST_ENTRY_UNKNOWN_SAFE_STOP,
        )
    if (
        not runtime.credential_presence_available
        or not runtime.all_required_credentials_present
    ):
        return (
            FreshPostEntryPositionConfirmationGateCase.CASE_4,
            FreshPostEntryPositionConfirmationStatus.CREDENTIAL_PRESENCE_BLOCKED,
            "HALTED_CREDENTIAL_REQUIRED",
            NEXT_STEP_CREDENTIAL_OPERATOR_ACTION,
        )
    if runtime.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        return (
            FreshPostEntryPositionConfirmationGateCase.CASE_1,
            FreshPostEntryPositionConfirmationStatus
            .FRESH_ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE,
            "FRESH_POSITION_OPEN_SAFE",
            NEXT_STEP_FRESH_POSITION_OPEN_SAFE_HANDOFF,
        )
    if runtime.position_status is PositionReadOnlyControlledStatus.NO_POSITION:
        return (
            FreshPostEntryPositionConfirmationGateCase.CASE_2,
            FreshPostEntryPositionConfirmationStatus
            .FRESH_ACCEPTED_BUT_NO_POSITION_VISIBLE_SAFE_STOP,
            "FRESH_ACCEPTED_NO_POSITION_SAFE_STOP",
            NEXT_STEP_FRESH_ACCEPTED_NO_POSITION_SAFE_STOP,
        )
    if (
        runtime.position_status
        is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    ):
        return (
            FreshPostEntryPositionConfirmationGateCase.CASE_3,
            FreshPostEntryPositionConfirmationStatus
            .FRESH_MULTIPLE_POSITIONS_BLOCKED,
            "HALTED_MANUAL_CHECK_REQUIRED",
            NEXT_STEP_MANUAL_POSITION_RISK_CHECK,
        )
    return (
        FreshPostEntryPositionConfirmationGateCase.CASE_4,
        FreshPostEntryPositionConfirmationStatus.FRESH_POSITION_UNKNOWN_FAIL_CLOSED,
        "HALTED_UNKNOWN_POSITION",
        NEXT_STEP_FRESH_POST_ENTRY_UNKNOWN_SAFE_STOP,
    )


def _fresh_entry_summary_blocked_reasons(
    summary: FreshEntryPostSafeSummaryInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not summary.fresh_cycle:
        reasons.append("fresh_cycle_missing")
    if summary.previous_attempt_retry:
        reasons.append("previous_attempt_retry")
    if summary.previous_attempt_repost:
        reasons.append("previous_attempt_repost")
    if not summary.fresh_entry_http_post_executed:
        reasons.append("fresh_entry_post_not_executed")
    if summary.fresh_entry_post_execution_count != 1:
        reasons.append("fresh_entry_post_count_not_one")
    if summary.fresh_entry_result_safe_status != FRESH_ENTRY_SAFE_STATUS_ACCEPTED:
        reasons.append("fresh_entry_result_status_not_accepted")
    if (
        summary.fresh_entry_sanitized_result_category
        != SafePostResultCategory.RESULT_ACCEPTED_SANITIZED.value
    ):
        reasons.append("fresh_entry_result_category_not_accepted")
    if (
        summary.fresh_entry_safe_reconciliation_status
        != SafeReconciliationStatus.RECONCILIATION_READY_NO_RECEIPT_HANDOFF.value
    ):
        reasons.append("fresh_entry_reconciliation_not_ready")
    if summary.fresh_entry_retry_attempted:
        reasons.append("fresh_entry_retry_attempted")
    if summary.fresh_entry_repost_attempted:
        reasons.append("fresh_entry_repost_attempted")
    if summary.fresh_entry_second_post_attempted:
        reasons.append("fresh_entry_second_post_attempted")
    if summary.close_post_executed:
        reasons.append("close_post_executed")
    if summary.ledger_updated:
        reasons.append("ledger_updated")
    if summary.receipt_handoff_executed:
        reasons.append("receipt_handoff_executed")
    if _summary_exposure(summary):
        reasons.append("fresh_entry_raw_id_value_exposure_blocked")
    return tuple(reasons)


def _current_step_blocked_reasons(
    snapshot: FreshPostEntryPositionConfirmationGateInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name, reason in (
        ("fresh_entry_post_attempted_this_step", "fresh_entry_post_attempted_this_step"),
        ("fresh_entry_retry_attempted_this_step", "fresh_entry_retry_this_step"),
        ("fresh_entry_repost_attempted_this_step", "fresh_entry_repost_this_step"),
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


def _summary_exposure(summary: FreshEntryPostSafeSummaryInput) -> bool:
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


def _current_exposure(
    snapshot: FreshPostEntryPositionConfirmationGateInput,
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


_FRESH_ENTRY_SUMMARY_BOOL_FIELDS = (
    "fresh_cycle",
    "previous_attempt_retry",
    "previous_attempt_repost",
    "fresh_entry_http_post_executed",
    "fresh_entry_retry_attempted",
    "fresh_entry_repost_attempted",
    "fresh_entry_second_post_attempted",
    "close_post_executed",
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
    "fresh_entry_post_attempted_this_step",
    "fresh_entry_retry_attempted_this_step",
    "fresh_entry_repost_attempted_this_step",
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
    "fresh_cycle",
    "previous_attempt_retry",
    "previous_attempt_repost",
    "fresh_entry_http_post_executed",
    "fresh_entry_retry_attempted",
    "fresh_entry_repost_attempted",
    "fresh_entry_second_post_attempted",
    "close_post_executed",
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
    "fresh_entry_effect_confirmed_by_position",
    "close_execution_gate_may_be_planned",
    "retry_allowed",
    "repost_allowed",
    "second_entry_allowed",
    "close_post_allowed_now",
    "level5_full_auto_cycle_completed",
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
    "fresh_entry_post_executed_this_step",
    "close_post_executed_this_step",
    "retry_or_repost_attempted_this_step",
    "second_entry_post_attempted_this_step",
    "ledger_updated_this_step",
    "receipt_handoff_executed_this_step",
)
