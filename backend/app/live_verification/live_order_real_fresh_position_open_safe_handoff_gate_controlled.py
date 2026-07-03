"""Fresh Step 6G position-open safe handoff gate.

This module hands off a confirmed fresh open position to the later close
execution gate as planning-only state. It never executes entry POST, close
POST, retry, repost, ledger updates, receipt handoff, broker/private API calls,
env reads, or raw ID/value handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_close_order_route_controlled import (
    CloseOrderRouteControlledResult,
)
from app.live_verification.live_order_real_fresh_post_entry_position_confirmation_gate_controlled import (  # noqa: E501
    FreshEntryPostSafeSummaryInput,
    FreshPostEntryPositionConfirmationGateInput,
    FreshPostEntryPositionConfirmationStatus,
    build_fresh_post_entry_position_confirmation_gate_controlled,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_position_runtime_safe_read_controlled import (
    PositionRuntimeSafeReadControlledResult,
    build_position_runtime_safe_read_controlled,
)

FRESH_POSITION_OPEN_SAFE_HANDOFF_GATE_LABEL = (
    "STEP6G_FRESH_POSITION_OPEN_SAFE_HANDOFF_GATE_CONTROLLED"
)
NEXT_STEP_CLOSE_ORDER_EXECUTION_GATE = (
    "Step 6G-PC-OX-R-CLOSE-ORDER-EXECUTION-GATE-C"
)
NEXT_STEP_POSITION_GONE_SAFE_STOP = (
    "Step 6G-PC-OX-R-FRESH-POSITION-GONE-BEFORE-CLOSE-SAFE-STOP-GATE-C"
)
NEXT_STEP_MANUAL_POSITION_RISK_CHECK = (
    "Step 6G-PC-OX-R-MANUAL-POSITION-RISK-CHECK-GATE-C"
)
NEXT_STEP_FRESH_POSITION_OPEN_UNKNOWN_SAFE_STOP = (
    "Step 6G-PC-OX-R-FRESH-POSITION-OPEN-HANDOFF-UNKNOWN-SAFE-STOP-GATE-C"
)


class FreshPositionOpenSafeHandoffGateCase(str, Enum):
    CASE_1 = "CASE 1"
    CASE_2 = "CASE 2"
    CASE_3 = "CASE 3"
    CASE_4 = "CASE 4"


class FreshPositionOpenSafeHandoffStatus(str, Enum):
    FRESH_POSITION_OPEN_SAFE_HANDOFF_READY = (
        "FRESH_POSITION_OPEN_SAFE_HANDOFF_READY"
    )
    FRESH_POSITION_GONE_BEFORE_CLOSE_SAFE_STOP = (
        "FRESH_POSITION_GONE_BEFORE_CLOSE_SAFE_STOP"
    )
    FRESH_MULTIPLE_POSITIONS_HANDOFF_BLOCKED = (
        "FRESH_MULTIPLE_POSITIONS_HANDOFF_BLOCKED"
    )
    FRESH_POSITION_HANDOFF_UNKNOWN_FAIL_CLOSED = (
        "FRESH_POSITION_HANDOFF_UNKNOWN_FAIL_CLOSED"
    )
    FRESH_ENTRY_SUMMARY_BLOCKED = "FRESH_ENTRY_SUMMARY_BLOCKED"
    CLOSE_ROUTE_PLANNING_BLOCKED = "CLOSE_ROUTE_PLANNING_BLOCKED"
    UNSAFE_EXPOSURE_BLOCKED = "UNSAFE_EXPOSURE_BLOCKED"
    CREDENTIAL_PRESENCE_BLOCKED = "CREDENTIAL_PRESENCE_BLOCKED"


@dataclass(frozen=True)
class FreshPositionOpenSafeHandoffGateInput:
    fresh_entry_summary: FreshEntryPostSafeSummaryInput = field(
        default_factory=FreshEntryPostSafeSummaryInput,
    )
    entry_post_attempted_this_step: bool = False
    entry_retry_attempted_this_step: bool = False
    entry_repost_attempted_this_step: bool = False
    second_entry_post_attempted_this_step: bool = False
    close_post_attempted_this_step: bool = False
    close_order_endpoint_called_this_step: bool = False
    order_endpoint_called_this_step: bool = False
    live_order_once_called_this_step: bool = False
    ledger_update_attempted_this_step: bool = False
    attempt_counter_persisted_this_step: bool = False
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
    trade_id_exposure_attempted_this_step: bool = False
    client_order_id_actual_value_exposure_attempted_this_step: bool = False
    actual_price_value_exposure_attempted_this_step: bool = False
    actual_pnl_value_exposure_attempted_this_step: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.fresh_entry_summary, FreshEntryPostSafeSummaryInput):
            raise LiveVerificationValidationError(
                "fresh_entry_summary must be FreshEntryPostSafeSummaryInput",
            )
        _validate_bool_fields(self, _GATE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class FreshPositionOpenSafeHandoffGateResult:
    gate_label: str
    case: FreshPositionOpenSafeHandoffGateCase
    handoff_status: FreshPositionOpenSafeHandoffStatus
    handoff_gate_ready: bool
    fresh_entry_post_executed: bool
    fresh_entry_post_execution_count: int
    fresh_entry_result_safe_status: str
    fresh_entry_result_safe_category: str
    fresh_entry_safe_reconciliation_status: str
    fresh_entry_retry_attempted: bool
    fresh_entry_repost_attempted: bool
    fresh_entry_second_post_attempted: bool
    previous_close_post_executed: bool
    previous_raw_id_value_exposed: bool
    credential_presence_available: bool
    runtime_position_checked: bool
    runtime_read_executed: bool
    runtime_position_status: PositionReadOnlyControlledStatus
    runtime_position_count_safe: int
    has_open_position: bool
    has_exactly_one_position: bool
    has_multiple_positions: bool
    fresh_position_open_safe: bool
    fresh_position_open_safe_handoff_ready: bool
    next_cycle_state: str
    close_route_ready: bool
    close_planning_allowed: bool
    close_execution_gate_may_be_planned: bool
    close_execution_allowed_now: bool
    close_post_executed: bool
    close_post_count: int
    close_retry_allowed: bool
    close_repost_allowed: bool
    close_second_post_allowed: bool
    requires_exactly_one_position: bool
    close_units_fixed: int
    close_order_type_safe_label: str
    retry_allowed: bool
    repost_allowed: bool
    second_entry_allowed: bool
    actual_entry_post_allowed_now: bool
    close_post_allowed_now: bool
    ledger_update_allowed: bool
    receipt_handoff_allowed: bool
    close_gate_requires_new_runtime_position_read: bool
    close_gate_requires_new_operator_readiness: bool
    close_gate_requires_new_close_preview: bool
    close_gate_requires_new_close_confirmation: bool
    close_gate_must_not_reuse_entry_confirmation: bool
    close_gate_must_not_expose_raw_id_value: bool
    level5_full_auto_cycle_completed: bool
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
    entry_post_executed_this_step: bool
    close_post_executed_this_step: bool
    retry_or_repost_attempted_this_step: bool
    second_entry_post_attempted_this_step: bool
    ledger_updated_this_step: bool
    receipt_handoff_executed_this_step: bool
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("gate_label", self.gate_label)
        if not isinstance(self.case, FreshPositionOpenSafeHandoffGateCase):
            raise LiveVerificationValidationError("case must be handoff gate enum")
        if not isinstance(self.handoff_status, FreshPositionOpenSafeHandoffStatus):
            raise LiveVerificationValidationError(
                "handoff_status must be handoff status enum",
            )
        if not isinstance(
            self.runtime_position_status,
            PositionReadOnlyControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        _require_non_empty("fresh_entry_result_safe_status", self.fresh_entry_result_safe_status)
        _require_non_empty(
            "fresh_entry_result_safe_category",
            self.fresh_entry_result_safe_category,
        )
        _require_non_empty(
            "fresh_entry_safe_reconciliation_status",
            self.fresh_entry_safe_reconciliation_status,
        )
        _require_non_empty("next_cycle_state", self.next_cycle_state)
        _require_non_empty("close_order_type_safe_label", self.close_order_type_safe_label)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_non_negative_int(
            "fresh_entry_post_execution_count",
            self.fresh_entry_post_execution_count,
        )
        _validate_non_negative_int(
            "runtime_position_count_safe",
            self.runtime_position_count_safe,
        )
        _validate_non_negative_int("close_post_count", self.close_post_count)
        _validate_non_negative_int("close_units_fixed", self.close_units_fixed)
        _validate_bool_fields(self, _GATE_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_fresh_position_open_safe_handoff_gate_controlled(
    input_snapshot: FreshPositionOpenSafeHandoffGateInput | None = None,
    *,
    runtime_result: PositionRuntimeSafeReadControlledResult | None = None,
    close_route_result: CloseOrderRouteControlledResult | None = None,
) -> FreshPositionOpenSafeHandoffGateResult:
    snapshot = input_snapshot or FreshPositionOpenSafeHandoffGateInput()
    runtime = runtime_result or build_position_runtime_safe_read_controlled()
    close_route = close_route_result or runtime.close_route
    current_reasons = _current_step_blocked_reasons(snapshot)
    fresh_confirmation = build_fresh_post_entry_position_confirmation_gate_controlled(
        FreshPostEntryPositionConfirmationGateInput(
            fresh_entry_summary=snapshot.fresh_entry_summary,
            fresh_entry_post_attempted_this_step=(
                snapshot.entry_post_attempted_this_step
            ),
            fresh_entry_retry_attempted_this_step=(
                snapshot.entry_retry_attempted_this_step
            ),
            fresh_entry_repost_attempted_this_step=(
                snapshot.entry_repost_attempted_this_step
            ),
            second_entry_post_attempted_this_step=(
                snapshot.second_entry_post_attempted_this_step
            ),
            close_post_attempted_this_step=snapshot.close_post_attempted_this_step,
            order_endpoint_called_this_step=(
                snapshot.order_endpoint_called_this_step
                or snapshot.close_order_endpoint_called_this_step
            ),
            live_order_once_called_this_step=(
                snapshot.live_order_once_called_this_step
            ),
            ledger_update_attempted_this_step=(
                snapshot.ledger_update_attempted_this_step
            ),
            receipt_handoff_attempted_this_step=(
                snapshot.receipt_handoff_attempted_this_step
            ),
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
        ),
        runtime_result=runtime,
    )
    case, status, next_state, next_step = _case_status_and_next_step(
        runtime=runtime,
        close_route=close_route,
        fresh_status=fresh_confirmation.fresh_position_confirmation_status,
        current_reasons=current_reasons,
    )
    handoff_ready = status is (
        FreshPositionOpenSafeHandoffStatus.FRESH_POSITION_OPEN_SAFE_HANDOFF_READY
    )
    summary = snapshot.fresh_entry_summary
    blocked_reasons = tuple(
        dict.fromkeys(
            (
                *fresh_confirmation.blocked_reasons,
                *current_reasons,
                *runtime.blocked_reasons,
                *close_route.blocked_reasons,
            ),
        ),
    )
    return FreshPositionOpenSafeHandoffGateResult(
        gate_label=FRESH_POSITION_OPEN_SAFE_HANDOFF_GATE_LABEL,
        case=case,
        handoff_status=status,
        handoff_gate_ready=handoff_ready,
        fresh_entry_post_executed=summary.fresh_entry_http_post_executed,
        fresh_entry_post_execution_count=summary.fresh_entry_post_execution_count,
        fresh_entry_result_safe_status=summary.fresh_entry_result_safe_status,
        fresh_entry_result_safe_category=summary.fresh_entry_sanitized_result_category,
        fresh_entry_safe_reconciliation_status=(
            summary.fresh_entry_safe_reconciliation_status
        ),
        fresh_entry_retry_attempted=summary.fresh_entry_retry_attempted,
        fresh_entry_repost_attempted=summary.fresh_entry_repost_attempted,
        fresh_entry_second_post_attempted=summary.fresh_entry_second_post_attempted,
        previous_close_post_executed=summary.close_post_executed,
        previous_raw_id_value_exposed=_summary_exposure(summary),
        credential_presence_available=runtime.credential_presence_available,
        runtime_position_checked=(
            runtime.runtime_read_executed and runtime.position_status_checked
        ),
        runtime_read_executed=runtime.runtime_read_executed,
        runtime_position_status=runtime.position_status,
        runtime_position_count_safe=runtime.position_count_safe,
        has_open_position=runtime.has_open_position,
        has_exactly_one_position=runtime.has_exactly_one_position,
        has_multiple_positions=runtime.has_multiple_positions,
        fresh_position_open_safe=(
            runtime.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
            and runtime.position_count_safe == 1
            and runtime.has_exactly_one_position
        ),
        fresh_position_open_safe_handoff_ready=handoff_ready,
        next_cycle_state=next_state,
        close_route_ready=close_route.close_route_ready,
        close_planning_allowed=close_route.close_planning_allowed and handoff_ready,
        close_execution_gate_may_be_planned=(
            close_route.close_execution_readiness.close_execution_step_may_be_planned
            and handoff_ready
        ),
        close_execution_allowed_now=False,
        close_post_executed=False,
        close_post_count=0,
        close_retry_allowed=False,
        close_repost_allowed=False,
        close_second_post_allowed=False,
        requires_exactly_one_position=close_route.requires_exactly_one_position,
        close_units_fixed=close_route.close_units_fixed,
        close_order_type_safe_label=close_route.close_order_type_safe_label,
        retry_allowed=False,
        repost_allowed=False,
        second_entry_allowed=False,
        actual_entry_post_allowed_now=False,
        close_post_allowed_now=False,
        ledger_update_allowed=False,
        receipt_handoff_allowed=False,
        close_gate_requires_new_runtime_position_read=True,
        close_gate_requires_new_operator_readiness=True,
        close_gate_requires_new_close_preview=True,
        close_gate_requires_new_close_confirmation=True,
        close_gate_must_not_reuse_entry_confirmation=True,
        close_gate_must_not_expose_raw_id_value=True,
        level5_full_auto_cycle_completed=False,
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
        entry_post_executed_this_step=False,
        close_post_executed_this_step=False,
        retry_or_repost_attempted_this_step=False,
        second_entry_post_attempted_this_step=False,
        ledger_updated_this_step=False,
        receipt_handoff_executed_this_step=False,
        recommended_next_step=next_step,
        blocked_reasons=blocked_reasons,
    )


def render_fresh_position_open_safe_handoff_gate_markdown(
    result: FreshPositionOpenSafeHandoffGateResult,
) -> str:
    """Render safe fresh position-open handoff fields only."""
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Fresh Position Open Safe Handoff Gate",
            "",
            "This gate hands off a confirmed fresh open position to close",
            "execution planning only. It does not execute entry POST, close POST,",
            "retry, repost, ledger update, receipt handoff, or expose raw/ID/value",
            "data.",
            "",
            f"case: {result.case.value}",
            f"handoff_status: {result.handoff_status.value}",
            f"handoff_gate_ready: {_bool_text(result.handoff_gate_ready)}",
            (
                "fresh_entry_post_executed: "
                f"{_bool_text(result.fresh_entry_post_executed)}"
            ),
            (
                "fresh_entry_post_execution_count: "
                f"{result.fresh_entry_post_execution_count}"
            ),
            (
                "fresh_entry_result_safe_category: "
                f"{result.fresh_entry_result_safe_category}"
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
            (
                "previous_close_post_executed: "
                f"{_bool_text(result.previous_close_post_executed)}"
            ),
            (
                "previous_raw_id_value_exposed: "
                f"{_bool_text(result.previous_raw_id_value_exposed)}"
            ),
            (
                "credential_presence_available: "
                f"{_bool_text(result.credential_presence_available)}"
            ),
            f"runtime_read_executed: {_bool_text(result.runtime_read_executed)}",
            (
                "runtime_position_checked: "
                f"{_bool_text(result.runtime_position_checked)}"
            ),
            f"runtime_position_status: {result.runtime_position_status.value}",
            f"runtime_position_count_safe: {result.runtime_position_count_safe}",
            f"has_open_position: {_bool_text(result.has_open_position)}",
            (
                "has_exactly_one_position: "
                f"{_bool_text(result.has_exactly_one_position)}"
            ),
            f"has_multiple_positions: {_bool_text(result.has_multiple_positions)}",
            (
                "fresh_position_open_safe: "
                f"{_bool_text(result.fresh_position_open_safe)}"
            ),
            (
                "fresh_position_open_safe_handoff_ready: "
                f"{_bool_text(result.fresh_position_open_safe_handoff_ready)}"
            ),
            f"next_cycle_state: {result.next_cycle_state}",
            f"close_route_ready: {_bool_text(result.close_route_ready)}",
            f"close_planning_allowed: {_bool_text(result.close_planning_allowed)}",
            (
                "close_execution_gate_may_be_planned: "
                f"{_bool_text(result.close_execution_gate_may_be_planned)}"
            ),
            (
                "close_execution_allowed_now: "
                f"{_bool_text(result.close_execution_allowed_now)}"
            ),
            f"close_post_executed: {_bool_text(result.close_post_executed)}",
            f"close_post_count: {result.close_post_count}",
            f"close_retry_allowed: {_bool_text(result.close_retry_allowed)}",
            f"close_repost_allowed: {_bool_text(result.close_repost_allowed)}",
            (
                "close_second_post_allowed: "
                f"{_bool_text(result.close_second_post_allowed)}"
            ),
            f"close_units_fixed: {result.close_units_fixed}",
            f"close_order_type_safe_label: {result.close_order_type_safe_label}",
            f"retry_allowed: {_bool_text(result.retry_allowed)}",
            f"repost_allowed: {_bool_text(result.repost_allowed)}",
            f"second_entry_allowed: {_bool_text(result.second_entry_allowed)}",
            (
                "actual_entry_post_allowed_now: "
                f"{_bool_text(result.actual_entry_post_allowed_now)}"
            ),
            f"close_post_allowed_now: {_bool_text(result.close_post_allowed_now)}",
            (
                "ledger_update_allowed: "
                f"{_bool_text(result.ledger_update_allowed)}"
            ),
            (
                "receipt_handoff_allowed: "
                f"{_bool_text(result.receipt_handoff_allowed)}"
            ),
            (
                "close_gate_requires_new_runtime_position_read: "
                f"{_bool_text(result.close_gate_requires_new_runtime_position_read)}"
            ),
            (
                "close_gate_requires_new_operator_readiness: "
                f"{_bool_text(result.close_gate_requires_new_operator_readiness)}"
            ),
            (
                "close_gate_requires_new_close_preview: "
                f"{_bool_text(result.close_gate_requires_new_close_preview)}"
            ),
            (
                "close_gate_requires_new_close_confirmation: "
                f"{_bool_text(result.close_gate_requires_new_close_confirmation)}"
            ),
            (
                "close_gate_must_not_reuse_entry_confirmation: "
                f"{_bool_text(result.close_gate_must_not_reuse_entry_confirmation)}"
            ),
            (
                "close_gate_must_not_expose_raw_id_value: "
                f"{_bool_text(result.close_gate_must_not_expose_raw_id_value)}"
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
            (
                "credential_value_exposed: "
                f"{_bool_text(result.credential_value_exposed)}"
            ),
            f"signature_value_exposed: {_bool_text(result.signature_value_exposed)}",
            f"headers_value_exposed: {_bool_text(result.headers_value_exposed)}",
            (
                "entry_post_executed_this_step: "
                f"{_bool_text(result.entry_post_executed_this_step)}"
            ),
            (
                "close_post_executed_this_step: "
                f"{_bool_text(result.close_post_executed_this_step)}"
            ),
            f"blocked_reasons: {blocked}",
            f"recommended_next_step: {result.recommended_next_step}",
        ),
    ) + "\n"


def _case_status_and_next_step(
    *,
    runtime: PositionRuntimeSafeReadControlledResult,
    close_route: CloseOrderRouteControlledResult,
    fresh_status: FreshPostEntryPositionConfirmationStatus,
    current_reasons: tuple[str, ...],
) -> tuple[
    FreshPositionOpenSafeHandoffGateCase,
    FreshPositionOpenSafeHandoffStatus,
    str,
    str,
]:
    if fresh_status is FreshPostEntryPositionConfirmationStatus.FRESH_ENTRY_SUMMARY_BLOCKED:
        return (
            FreshPositionOpenSafeHandoffGateCase.CASE_4,
            FreshPositionOpenSafeHandoffStatus.FRESH_ENTRY_SUMMARY_BLOCKED,
            "HALTED",
            NEXT_STEP_FRESH_POSITION_OPEN_UNKNOWN_SAFE_STOP,
        )
    if (
        current_reasons
        or fresh_status is FreshPostEntryPositionConfirmationStatus.UNSAFE_EXPOSURE_BLOCKED
    ):
        return (
            FreshPositionOpenSafeHandoffGateCase.CASE_4,
            FreshPositionOpenSafeHandoffStatus.UNSAFE_EXPOSURE_BLOCKED,
            "HALTED",
            NEXT_STEP_FRESH_POSITION_OPEN_UNKNOWN_SAFE_STOP,
        )
    if (
        fresh_status
        is FreshPostEntryPositionConfirmationStatus.CREDENTIAL_PRESENCE_BLOCKED
        or not runtime.credential_presence_available
        or not runtime.all_required_credentials_present
    ):
        return (
            FreshPositionOpenSafeHandoffGateCase.CASE_4,
            FreshPositionOpenSafeHandoffStatus.CREDENTIAL_PRESENCE_BLOCKED,
            "HALTED",
            NEXT_STEP_FRESH_POSITION_OPEN_UNKNOWN_SAFE_STOP,
        )
    if runtime.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        if close_route.close_route_ready and close_route.close_planning_allowed:
            return (
                FreshPositionOpenSafeHandoffGateCase.CASE_1,
                FreshPositionOpenSafeHandoffStatus
                .FRESH_POSITION_OPEN_SAFE_HANDOFF_READY,
                "FRESH_POSITION_OPEN_SAFE_HANDOFF_READY",
                NEXT_STEP_CLOSE_ORDER_EXECUTION_GATE,
            )
        return (
            FreshPositionOpenSafeHandoffGateCase.CASE_4,
            FreshPositionOpenSafeHandoffStatus.CLOSE_ROUTE_PLANNING_BLOCKED,
            "HALTED",
            NEXT_STEP_FRESH_POSITION_OPEN_UNKNOWN_SAFE_STOP,
        )
    if runtime.position_status is PositionReadOnlyControlledStatus.NO_POSITION:
        return (
            FreshPositionOpenSafeHandoffGateCase.CASE_2,
            FreshPositionOpenSafeHandoffStatus
            .FRESH_POSITION_GONE_BEFORE_CLOSE_SAFE_STOP,
            "FRESH_POSITION_GONE_BEFORE_CLOSE_SAFE_STOP",
            NEXT_STEP_POSITION_GONE_SAFE_STOP,
        )
    if (
        runtime.position_status
        is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    ):
        return (
            FreshPositionOpenSafeHandoffGateCase.CASE_3,
            FreshPositionOpenSafeHandoffStatus
            .FRESH_MULTIPLE_POSITIONS_HANDOFF_BLOCKED,
            "HALTED_MANUAL_CHECK_REQUIRED",
            NEXT_STEP_MANUAL_POSITION_RISK_CHECK,
        )
    return (
        FreshPositionOpenSafeHandoffGateCase.CASE_4,
        FreshPositionOpenSafeHandoffStatus.FRESH_POSITION_HANDOFF_UNKNOWN_FAIL_CLOSED,
        "HALTED",
        NEXT_STEP_FRESH_POSITION_OPEN_UNKNOWN_SAFE_STOP,
    )


def _current_step_blocked_reasons(
    snapshot: FreshPositionOpenSafeHandoffGateInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name, reason in (
        ("entry_post_attempted_this_step", "entry_post_attempted_this_step"),
        ("entry_retry_attempted_this_step", "entry_retry_attempted_this_step"),
        ("entry_repost_attempted_this_step", "entry_repost_attempted_this_step"),
        (
            "second_entry_post_attempted_this_step",
            "second_entry_post_attempted_this_step",
        ),
        ("close_post_attempted_this_step", "close_post_attempted_this_step"),
        (
            "close_order_endpoint_called_this_step",
            "close_order_endpoint_called_this_step",
        ),
        ("order_endpoint_called_this_step", "order_endpoint_called_this_step"),
        ("live_order_once_called_this_step", "live_order_once_called_this_step"),
        ("ledger_update_attempted_this_step", "ledger_update_attempted_this_step"),
        (
            "attempt_counter_persisted_this_step",
            "attempt_counter_persisted_this_step",
        ),
        ("receipt_handoff_attempted_this_step", "receipt_handoff_attempted_this_step"),
    ):
        if getattr(snapshot, field_name):
            reasons.append(reason)
    if _current_exposure(snapshot):
        reasons.append("current_step_raw_id_value_exposure_blocked")
    return tuple(dict.fromkeys(reasons))


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


def _current_exposure(snapshot: FreshPositionOpenSafeHandoffGateInput) -> bool:
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
            "trade_id_exposure_attempted_this_step",
            "client_order_id_actual_value_exposure_attempted_this_step",
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


_GATE_INPUT_BOOL_FIELDS = (
    "entry_post_attempted_this_step",
    "entry_retry_attempted_this_step",
    "entry_repost_attempted_this_step",
    "second_entry_post_attempted_this_step",
    "close_post_attempted_this_step",
    "close_order_endpoint_called_this_step",
    "order_endpoint_called_this_step",
    "live_order_once_called_this_step",
    "ledger_update_attempted_this_step",
    "attempt_counter_persisted_this_step",
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
    "trade_id_exposure_attempted_this_step",
    "client_order_id_actual_value_exposure_attempted_this_step",
    "actual_price_value_exposure_attempted_this_step",
    "actual_pnl_value_exposure_attempted_this_step",
)

_GATE_RESULT_BOOL_FIELDS = (
    "handoff_gate_ready",
    "fresh_entry_post_executed",
    "fresh_entry_retry_attempted",
    "fresh_entry_repost_attempted",
    "fresh_entry_second_post_attempted",
    "previous_close_post_executed",
    "previous_raw_id_value_exposed",
    "credential_presence_available",
    "runtime_position_checked",
    "runtime_read_executed",
    "has_open_position",
    "has_exactly_one_position",
    "has_multiple_positions",
    "fresh_position_open_safe",
    "fresh_position_open_safe_handoff_ready",
    "close_route_ready",
    "close_planning_allowed",
    "close_execution_gate_may_be_planned",
    "close_execution_allowed_now",
    "close_post_executed",
    "close_retry_allowed",
    "close_repost_allowed",
    "close_second_post_allowed",
    "requires_exactly_one_position",
    "retry_allowed",
    "repost_allowed",
    "second_entry_allowed",
    "actual_entry_post_allowed_now",
    "close_post_allowed_now",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "close_gate_requires_new_runtime_position_read",
    "close_gate_requires_new_operator_readiness",
    "close_gate_requires_new_close_preview",
    "close_gate_requires_new_close_confirmation",
    "close_gate_must_not_reuse_entry_confirmation",
    "close_gate_must_not_expose_raw_id_value",
    "level5_full_auto_cycle_completed",
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
    "entry_post_executed_this_step",
    "close_post_executed_this_step",
    "retry_or_repost_attempted_this_step",
    "second_entry_post_attempted_this_step",
    "ledger_updated_this_step",
    "receipt_handoff_executed_this_step",
)
