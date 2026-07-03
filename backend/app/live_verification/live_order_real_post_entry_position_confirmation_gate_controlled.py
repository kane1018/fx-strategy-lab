"""Step 6G post-entry position confirmation gate.

This module confirms the effect of a previous single entry POST using only a
sanitized runtime position safe-read result. It does not execute entry POST,
close POST, retry, repost, ledger updates, receipt handoff, broker/private API
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

POST_ENTRY_POSITION_CONFIRMATION_GATE_LABEL = (
    "STEP6G_POST_ENTRY_POSITION_CONFIRMATION_GATE_CONTROLLED"
)
PREVIOUS_ENTRY_STEP_LABEL = (
    "Step 6G-PC-OX-R-ENTRY-ORDER-EXECUTION-GATE-C-RETRY-WITH-"
    "EXPLICIT-SIGNAL-AND-OPERATOR-READINESS"
)
PREVIOUS_ENTRY_CASE_LABEL = "CASE 3"
ENTRY_RESULT_UNKNOWN_BLOCKED = "unknown/blocked"

NEXT_STEP_POSITION_OPEN_SAFE_HANDOFF = (
    "Step 6G-PC-OX-R-LEVEL5-POSITION-OPEN-SAFE-HANDOFF-GATE-C"
)
NEXT_STEP_ENTRY_UNKNOWN_NO_POSITION_CLOSEOUT = (
    "Step 6G-PC-OX-R-ENTRY-UNKNOWN-NO-POSITION-CLOSEOUT-GATE-C"
)
NEXT_STEP_MANUAL_POSITION_RISK_CHECK = (
    "Step 6G-PC-OX-R-MANUAL-POSITION-RISK-CHECK-GATE-C"
)
NEXT_STEP_POST_ENTRY_UNKNOWN_SAFE_STOP = (
    "Step 6G-PC-OX-R-POST-ENTRY-UNKNOWN-RESULT-SAFE-STOP-GATE-C"
)
NEXT_STEP_CREDENTIAL_OPERATOR_ACTION = (
    "Step 6G-PC-OX-R-POST-ENTRY-CREDENTIAL-PRESENCE-OPERATOR-ACTION-C"
)


class PostEntryPositionConfirmationGateCase(str, Enum):
    CASE_1 = "CASE 1"
    CASE_2 = "CASE 2"
    CASE_3 = "CASE 3"
    CASE_4 = "CASE 4"


class PostEntryPositionConfirmationStatus(str, Enum):
    ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE = (
        "ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE"
    )
    NO_POSITION_AFTER_ENTRY_POST = "NO_POSITION_AFTER_ENTRY_POST"
    MULTIPLE_POSITIONS_BLOCKED_MANUAL_CHECK_REQUIRED = (
        "MULTIPLE_POSITIONS_BLOCKED_MANUAL_CHECK_REQUIRED"
    )
    UNKNOWN_FAIL_CLOSED_MANUAL_CHECK_REQUIRED = (
        "UNKNOWN_FAIL_CLOSED_MANUAL_CHECK_REQUIRED"
    )
    CREDENTIAL_PRESENCE_BLOCKED = "CREDENTIAL_PRESENCE_BLOCKED"
    PREVIOUS_ENTRY_SUMMARY_BLOCKED = "PREVIOUS_ENTRY_SUMMARY_BLOCKED"
    UNSAFE_EXPOSURE_BLOCKED = "UNSAFE_EXPOSURE_BLOCKED"


@dataclass(frozen=True)
class PreviousEntryPostSafeSummaryInput:
    previous_step: str = PREVIOUS_ENTRY_STEP_LABEL
    previous_case: str = PREVIOUS_ENTRY_CASE_LABEL
    entry_http_post_executed: bool = True
    entry_post_execution_count: int = 1
    entry_retry_attempted: bool = False
    entry_second_post_attempted: bool = False
    close_post_executed: bool = False
    ledger_updated: bool = False
    receipt_handoff_executed: bool = False
    entry_sanitized_result_category: str = ENTRY_RESULT_UNKNOWN_BLOCKED
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
            "entry_sanitized_result_category",
            self.entry_sanitized_result_category,
        )
        _validate_non_negative_int(
            "entry_post_execution_count",
            self.entry_post_execution_count,
        )
        _validate_bool_fields(self, _PREVIOUS_ENTRY_BOOL_FIELDS)


@dataclass(frozen=True)
class PostEntryPositionConfirmationGateInput:
    previous_entry_summary: PreviousEntryPostSafeSummaryInput = (
        field(default_factory=PreviousEntryPostSafeSummaryInput)
    )
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
        _validate_bool_fields(self, _GATE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class PostEntryPositionConfirmationGateResult:
    gate_label: str
    case: PostEntryPositionConfirmationGateCase
    position_confirmation_status: PostEntryPositionConfirmationStatus
    previous_step: str
    previous_case: str
    entry_http_post_executed: bool
    entry_post_execution_count: int
    entry_retry_attempted: bool
    entry_second_post_attempted: bool
    close_post_executed: bool
    ledger_updated: bool
    receipt_handoff_executed: bool
    entry_sanitized_result_category: str
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
    entry_effect_confirmed_by_position: bool
    next_cycle_state: str
    close_execution_gate_may_be_planned: bool
    retry_allowed: bool
    second_entry_allowed: bool
    close_post_allowed_now: bool
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
        if not isinstance(self.case, PostEntryPositionConfirmationGateCase):
            raise LiveVerificationValidationError("case must be post-entry enum")
        if not isinstance(
            self.position_confirmation_status,
            PostEntryPositionConfirmationStatus,
        ):
            raise LiveVerificationValidationError(
                "position_confirmation_status must be post-entry status enum",
            )
        if not isinstance(self.position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "position_status must be controlled enum",
            )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _require_non_empty("next_cycle_state", self.next_cycle_state)
        _validate_non_negative_int(
            "entry_post_execution_count",
            self.entry_post_execution_count,
        )
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("max_open_positions", self.max_open_positions)
        _validate_bool_fields(self, _GATE_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_post_entry_position_confirmation_gate_controlled(
    input_snapshot: PostEntryPositionConfirmationGateInput | None = None,
    *,
    runtime_result: PositionRuntimeSafeReadControlledResult | None = None,
    credential_presence_result: LiveOrderRealCredentialPresenceControlledResult
    | None = None,
) -> PostEntryPositionConfirmationGateResult:
    snapshot = input_snapshot or PostEntryPositionConfirmationGateInput()
    runtime = runtime_result or build_position_runtime_safe_read_controlled(
        credential_presence_result=credential_presence_result,
    )
    previous_reasons = _previous_entry_blocked_reasons(snapshot.previous_entry_summary)
    current_reasons = _current_step_blocked_reasons(snapshot)
    case, status, next_state, next_step = _case_status_and_next_step(
        runtime=runtime,
        previous_reasons=previous_reasons,
        current_reasons=current_reasons,
    )
    confirmed = status is (
        PostEntryPositionConfirmationStatus
        .ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE
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
    return PostEntryPositionConfirmationGateResult(
        gate_label=POST_ENTRY_POSITION_CONFIRMATION_GATE_LABEL,
        case=case,
        position_confirmation_status=status,
        previous_step=snapshot.previous_entry_summary.previous_step,
        previous_case=snapshot.previous_entry_summary.previous_case,
        entry_http_post_executed=snapshot.previous_entry_summary.entry_http_post_executed,
        entry_post_execution_count=(
            snapshot.previous_entry_summary.entry_post_execution_count
        ),
        entry_retry_attempted=snapshot.previous_entry_summary.entry_retry_attempted,
        entry_second_post_attempted=(
            snapshot.previous_entry_summary.entry_second_post_attempted
        ),
        close_post_executed=snapshot.previous_entry_summary.close_post_executed,
        ledger_updated=snapshot.previous_entry_summary.ledger_updated,
        receipt_handoff_executed=(
            snapshot.previous_entry_summary.receipt_handoff_executed
        ),
        entry_sanitized_result_category=(
            snapshot.previous_entry_summary.entry_sanitized_result_category
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
        close_planning_allowed=can_plan_close,
        close_execution_allowed_now=False,
        max_open_positions=1,
        entry_effect_confirmed_by_position=confirmed,
        next_cycle_state=next_state,
        close_execution_gate_may_be_planned=can_plan_close,
        retry_allowed=False,
        second_entry_allowed=False,
        close_post_allowed_now=False,
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


def render_post_entry_position_confirmation_gate_markdown(
    result: PostEntryPositionConfirmationGateResult,
) -> str:
    """Render safe post-entry position confirmation fields only."""
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Post-Entry Position Confirmation Gate",
            "",
            "This gate confirms a previous single entry POST using safe position",
            "status/count only. It does not retry entry POST, execute close POST,",
            "update ledger state, hand off receipts, or expose raw/ID/value data.",
            "",
            f"case: {result.case.value}",
            f"position_confirmation_status: {result.position_confirmation_status.value}",
            f"entry_http_post_executed: {_bool_text(result.entry_http_post_executed)}",
            f"entry_post_execution_count: {result.entry_post_execution_count}",
            f"entry_retry_attempted: {_bool_text(result.entry_retry_attempted)}",
            (
                "entry_second_post_attempted: "
                f"{_bool_text(result.entry_second_post_attempted)}"
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
                "entry_effect_confirmed_by_position: "
                f"{_bool_text(result.entry_effect_confirmed_by_position)}"
            ),
            f"next_cycle_state: {result.next_cycle_state}",
            (
                "close_execution_gate_may_be_planned: "
                f"{_bool_text(result.close_execution_gate_may_be_planned)}"
            ),
            f"retry_allowed: {_bool_text(result.retry_allowed)}",
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
    PostEntryPositionConfirmationGateCase,
    PostEntryPositionConfirmationStatus,
    str,
    str,
]:
    if previous_reasons:
        return (
            PostEntryPositionConfirmationGateCase.CASE_4,
            PostEntryPositionConfirmationStatus.PREVIOUS_ENTRY_SUMMARY_BLOCKED,
            "HALTED_UNKNOWN_RESULT_SAFE_STOP",
            NEXT_STEP_POST_ENTRY_UNKNOWN_SAFE_STOP,
        )
    if current_reasons:
        return (
            PostEntryPositionConfirmationGateCase.CASE_4,
            PostEntryPositionConfirmationStatus.UNSAFE_EXPOSURE_BLOCKED,
            "HALTED_UNKNOWN_POSITION",
            NEXT_STEP_POST_ENTRY_UNKNOWN_SAFE_STOP,
        )
    if (
        not runtime.credential_presence_available
        or not runtime.all_required_credentials_present
    ):
        return (
            PostEntryPositionConfirmationGateCase.CASE_4,
            PostEntryPositionConfirmationStatus.CREDENTIAL_PRESENCE_BLOCKED,
            "HALTED_CREDENTIAL_REQUIRED",
            NEXT_STEP_CREDENTIAL_OPERATOR_ACTION,
        )
    if runtime.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        return (
            PostEntryPositionConfirmationGateCase.CASE_1,
            PostEntryPositionConfirmationStatus
            .ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE,
            "POSITION_OPEN_SAFE",
            NEXT_STEP_POSITION_OPEN_SAFE_HANDOFF,
        )
    if runtime.position_status is PositionReadOnlyControlledStatus.NO_POSITION:
        return (
            PostEntryPositionConfirmationGateCase.CASE_2,
            PostEntryPositionConfirmationStatus.NO_POSITION_AFTER_ENTRY_POST,
            "UNKNOWN_RESULT_SAFE_STOP",
            NEXT_STEP_ENTRY_UNKNOWN_NO_POSITION_CLOSEOUT,
        )
    if (
        runtime.position_status
        is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    ):
        return (
            PostEntryPositionConfirmationGateCase.CASE_3,
            PostEntryPositionConfirmationStatus
            .MULTIPLE_POSITIONS_BLOCKED_MANUAL_CHECK_REQUIRED,
            "HALTED_MANUAL_CHECK_REQUIRED",
            NEXT_STEP_MANUAL_POSITION_RISK_CHECK,
        )
    return (
        PostEntryPositionConfirmationGateCase.CASE_4,
        PostEntryPositionConfirmationStatus.UNKNOWN_FAIL_CLOSED_MANUAL_CHECK_REQUIRED,
        "HALTED_UNKNOWN_POSITION",
        NEXT_STEP_POST_ENTRY_UNKNOWN_SAFE_STOP,
    )


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
    snapshot: PostEntryPositionConfirmationGateInput,
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


def _current_exposure(snapshot: PostEntryPositionConfirmationGateInput) -> bool:
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


_PREVIOUS_ENTRY_BOOL_FIELDS = (
    "entry_http_post_executed",
    "entry_retry_attempted",
    "entry_second_post_attempted",
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
    "entry_http_post_executed",
    "entry_retry_attempted",
    "entry_second_post_attempted",
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
    "entry_effect_confirmed_by_position",
    "close_execution_gate_may_be_planned",
    "retry_allowed",
    "second_entry_allowed",
    "close_post_allowed_now",
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
