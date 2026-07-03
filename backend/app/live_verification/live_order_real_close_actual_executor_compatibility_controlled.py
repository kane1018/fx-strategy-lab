"""Step 6G close actual executor compatibility foundation.

This module adapts a sanitized close execution route preview into a no-POST
close-specific executor compatibility preview. It does not invoke the generic
one-shot executor, transport, broker/private API, HTTP, env, ledger, receipt, or
live_order_once code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_close_order_execution_route_controlled import (
    APPROVED_CLOSE_PRIMITIVE_KIND_CLOSE_SPECIFIC,
    APPROVED_CLOSE_PRIMITIVE_KIND_DEPRECATED_UNSAFE_GENERIC,
    APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC,
    APPROVED_CLOSE_PRIMITIVE_KIND_NOT_APPROVED,
    NEXT_CYCLE_STATE_READY,
    OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED,
    SAFE_SIDE_BUY,
    SAFE_SIDE_SELL,
    CloseOrderExecutionRouteControlledResult,
)
from app.live_verification.live_order_real_close_order_route_controlled import (
    CLOSE_ORDER_TYPE_SAFE_LABEL,
    CLOSE_SIDE_SAFE_LABEL,
)
from app.live_verification.live_order_real_one_shot_post_execution_controlled import (
    SAFE_ENVIRONMENT_LABEL,
    SAFE_EXECUTABLE_ORDER_PREVIEW_LABEL,
    SAFE_RISK_LABEL,
    SAFE_TIME_IN_FORCE_LABEL,
    UNSUPPORTED_ONE_SHOT_POST_EXECUTION_LABEL,
    LiveOrderRealExecutableOrderPreviewResult,
    LiveOrderRealExecutableOrderPreviewStatus,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

EXECUTION_STEP_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY = (
    "CLOSE_ORDER_ACTUAL_EXECUTOR_COMPATIBILITY_NO_POST_C"
)
SAFE_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_LABEL = (
    "STEP6G_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_CONTROLLED_NO_POST"
)
SAFE_CLOSE_SPECIFIC_EXECUTOR_PREVIEW_LABEL = (
    "STEP6G_SANITIZED_CLOSE_SPECIFIC_EXECUTOR_PREVIEW_NO_POST"
)
PREVIOUS_CYCLE_STATE_CLOSE_EXECUTION_GATE_READY = "CLOSE_EXECUTION_GATE_READY_NO_POST"
NEXT_CYCLE_STATE_CLOSE_ACTUAL_EXECUTOR_READY = (
    "CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_READY_NO_POST"
)
NEXT_CYCLE_STATE_CLOSE_ACTUAL_EXECUTOR_BLOCKED = (
    "CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED"
)
NEXT_STEP_CLOSE_EXECUTION_GATE_RETRY_WITH_COMPATIBLE_EXECUTOR = (
    "Step 6G-PC-OX-R-CLOSE-ORDER-EXECUTION-GATE-C-RETRY-WITH-COMPATIBLE-EXECUTOR"
)
NEXT_STEP_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_FIX = (
    "fix_close_actual_executor_compatibility_blockers_no_post"
)
NEXT_STEP_OFFICIAL_SETTLEMENT_ROUTE_REVIEW = (
    "Step 6G-PC-OX-R-GMO-FX-OFFICIAL-SETTLEMENT-ROUTE-REVIEW-C"
)

_CONCRETE_CLOSE_SIDE_LABELS = frozenset({SAFE_SIDE_SELL, SAFE_SIDE_BUY})


class CloseActualExecutorCompatibilityControlledStatus(str, Enum):
    READY_NO_POST = "CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_READY_NO_POST"
    DEPRECATED_UNSAFE_GENERIC_CLOSE = (
        "CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_DEPRECATED_UNSAFE_GENERIC_CLOSE"
    )
    BLOCKED_CONTEXT = "CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_CONTEXT"
    BLOCKED_ROUTE = "CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_ROUTE"
    BLOCKED_GUARD = "CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_GUARD"
    BLOCKED_OFFICIAL_SETTLEMENT_ROUTE = (
        "CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_OFFICIAL_SETTLEMENT_ROUTE"
    )
    BLOCKED_UNSAFE = "CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_UNSAFE"


@dataclass(frozen=True)
class SanitizedCloseActualExecutorPreview:
    preview_ready: bool
    execution_step: str
    safe_preview_label: str
    close_specific_context: bool
    generic_entry_context: bool
    runtime_position_status: PositionReadOnlyControlledStatus
    position_count_safe: int
    close_symbol_safe_label: str
    close_side_safe_label: str
    close_units_fixed: int
    close_order_type_safe_label: str
    approved_close_post_primitive_ready: bool
    approved_close_post_primitive_kind: str
    one_close_post_max: bool
    close_retry_allowed: bool
    close_repost_allowed: bool
    close_second_post_allowed: bool
    entry_post_this_step: bool
    actual_close_post_allowed_now: bool
    actual_close_post_executed: bool
    transport_call_count: int
    ledger_update_this_step: bool
    receipt_handoff_this_step: bool
    raw_exposure: bool
    id_exposure: bool
    credential_value_exposure: bool
    signature_value_exposure: bool
    headers_value_exposure: bool
    actual_close_post_requires_separate_close_execution_gate: bool

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        for field_name in (
            "execution_step",
            "safe_preview_label",
            "close_symbol_safe_label",
            "close_side_safe_label",
            "close_order_type_safe_label",
            "approved_close_post_primitive_kind",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("close_units_fixed", self.close_units_fixed)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_bool_fields(self, _PREVIEW_BOOL_FIELDS)


@dataclass(frozen=True)
class CloseActualExecutorCompatibilityControlledInput:
    close_specific_context: bool = True
    generic_entry_context: bool = False
    input_close_execution_route_ready: bool = False
    input_close_executable_preview_ready: bool = False
    input_approved_close_post_primitive_ready: bool = False
    input_approved_close_post_primitive_kind: str = (
        APPROVED_CLOSE_PRIMITIVE_KIND_NOT_APPROVED
    )
    input_approved_close_post_primitive_is_generic_order: bool = False
    input_generic_order_accepted_as_close_only_with_exact_one_position_guard: bool = False
    official_gmo_rules_alignment_checked: bool = True
    official_manual_url_recorded: bool = True
    official_trading_rules_url_recorded: bool = True
    generic_opposite_order_as_close_forbidden: bool = True
    generic_close_primitive_revoked: bool = True
    official_settlement_route_confirmed: bool = False
    runtime_position_status: PositionReadOnlyControlledStatus = (
        PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    )
    position_count_safe: int = 0
    has_exactly_one_position: bool = False
    has_multiple_positions: bool = False
    close_symbol_safe_label: str = SUPPORTED_SYMBOL
    close_side_safe_label: str = CLOSE_SIDE_SAFE_LABEL
    close_units_fixed: int = SUPPORTED_UNITS
    close_order_type_safe_label: str = CLOSE_ORDER_TYPE_SAFE_LABEL
    one_close_post_max: bool = True
    close_retry_allowed: bool = False
    close_repost_allowed: bool = False
    close_second_post_allowed: bool = False
    entry_post_this_step: bool = False
    actual_close_post_allowed_now: bool = False
    actual_close_post_attempted_this_step: bool = False
    transport_call_count: int = 0
    ledger_update_this_step: bool = False
    receipt_handoff_this_step: bool = False
    raw_position_exposure_attempted: bool = False
    raw_request_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    broker_api_response_exposure_attempted: bool = False
    position_id_exposure_attempted: bool = False
    account_id_exposure_attempted: bool = False
    order_id_exposure_attempted: bool = False
    transaction_id_exposure_attempted: bool = False
    trade_id_exposure_attempted: bool = False
    real_id_exposure_attempted: bool = False
    client_order_id_actual_value_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        for field_name in (
            "input_approved_close_post_primitive_kind",
            "close_symbol_safe_label",
            "close_side_safe_label",
            "close_order_type_safe_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("close_units_fixed", self.close_units_fixed)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class CloseActualExecutorCompatibilityLevel5ConnectionResult:
    previous_cycle_state: str
    next_cycle_state: str
    close_execution_gate_may_be_planned: bool
    close_sent_reached: bool
    close_post_executed_reached: bool
    post_close_position_confirmation_reached: bool
    ledger_updated_reached: bool
    receipt_handoff_reached: bool
    level5_full_auto_cycle_completed: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("previous_cycle_state", self.previous_cycle_state)
        _require_non_empty("next_cycle_state", self.next_cycle_state)
        _validate_bool_fields(self, _LEVEL5_CONNECTION_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


@dataclass(frozen=True)
class CloseActualExecutorCompatibilityControlledResult:
    status: CloseActualExecutorCompatibilityControlledStatus
    close_actual_executor_compatibility_ready: bool
    close_specific_executor_preview_ready: bool
    safe_close_actual_executor_compatibility_label: str
    executable_preview: SanitizedCloseActualExecutorPreview
    one_shot_executor_preview: LiveOrderRealExecutableOrderPreviewResult
    level5_connection: CloseActualExecutorCompatibilityLevel5ConnectionResult
    close_specific_context: bool
    generic_entry_context: bool
    generic_entry_buy_guard_intact: bool
    generic_entry_sell_blocked: bool
    close_specific_sell_accepted: bool
    close_specific_buy_accepted: bool
    exact_one_position_guard_required: bool
    approved_primitive_required: bool
    input_close_execution_route_ready: bool
    input_close_executable_preview_ready: bool
    input_approved_close_post_primitive_ready: bool
    input_approved_close_post_primitive_kind: str
    input_approved_close_post_primitive_is_generic_order: bool
    input_generic_order_accepted_as_close_only_with_exact_one_position_guard: bool
    official_gmo_rules_alignment_checked: bool
    official_manual_url_recorded: bool
    official_trading_rules_url_recorded: bool
    generic_opposite_order_as_close_forbidden: bool
    generic_close_primitive_revoked: bool
    official_settlement_route_confirmed: bool
    close_execution_blocked_reason: str
    runtime_position_status: PositionReadOnlyControlledStatus
    position_count_safe: int
    has_exactly_one_position: bool
    has_multiple_positions: bool
    close_symbol_safe_label: str
    close_side_safe_label: str
    close_units_fixed: int
    close_order_type_safe_label: str
    one_close_post_max: bool
    close_retry_allowed: bool
    close_repost_allowed: bool
    close_second_post_allowed: bool
    entry_post_this_step: bool
    actual_close_post_allowed_now: bool
    actual_close_post_executed: bool
    transport_call_count: int
    ledger_update_this_step: bool
    receipt_handoff_this_step: bool
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
        if not isinstance(self.status, CloseActualExecutorCompatibilityControlledStatus):
            raise LiveVerificationValidationError("status must be compatibility enum")
        if not isinstance(self.runtime_position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        for field_name in (
            "safe_close_actual_executor_compatibility_label",
            "input_approved_close_post_primitive_kind",
            "close_execution_blocked_reason",
            "close_symbol_safe_label",
            "close_side_safe_label",
            "close_order_type_safe_label",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("close_units_fixed", self.close_units_fixed)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_close_actual_executor_compatibility_controlled(
    input_snapshot: CloseActualExecutorCompatibilityControlledInput | None = None,
    *,
    close_execution_route_result: CloseOrderExecutionRouteControlledResult | None = None,
) -> CloseActualExecutorCompatibilityControlledResult:
    """Build a close-specific executor compatibility preview without POST."""
    snapshot = input_snapshot or _input_from_close_execution_route(close_execution_route_result)
    reasons = _blocked_reasons(snapshot)
    ready = not reasons
    status = _status_from_reasons(reasons)
    preview = _sanitized_preview(snapshot, ready)
    one_shot_preview = _one_shot_executor_preview(snapshot, ready, reasons)
    level5_connection = connect_close_actual_executor_compatibility_level5(
        compatibility_ready=ready,
        blocked_reasons=reasons,
    )
    side_is_sell = snapshot.close_side_safe_label == SAFE_SIDE_SELL
    side_is_buy = snapshot.close_side_safe_label == SAFE_SIDE_BUY
    return CloseActualExecutorCompatibilityControlledResult(
        status=status,
        close_actual_executor_compatibility_ready=ready,
        close_specific_executor_preview_ready=ready,
        safe_close_actual_executor_compatibility_label=(
            SAFE_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_LABEL
        ),
        executable_preview=preview,
        one_shot_executor_preview=one_shot_preview,
        level5_connection=level5_connection,
        close_specific_context=snapshot.close_specific_context,
        generic_entry_context=snapshot.generic_entry_context,
        generic_entry_buy_guard_intact=True,
        generic_entry_sell_blocked=True,
        close_specific_sell_accepted=ready and side_is_sell,
        close_specific_buy_accepted=ready and side_is_buy,
        exact_one_position_guard_required=True,
        approved_primitive_required=True,
        input_close_execution_route_ready=snapshot.input_close_execution_route_ready,
        input_close_executable_preview_ready=snapshot.input_close_executable_preview_ready,
        input_approved_close_post_primitive_ready=(
            snapshot.input_approved_close_post_primitive_ready
        ),
        input_approved_close_post_primitive_kind=(
            snapshot.input_approved_close_post_primitive_kind
        ),
        input_approved_close_post_primitive_is_generic_order=(
            snapshot.input_approved_close_post_primitive_is_generic_order
        ),
        input_generic_order_accepted_as_close_only_with_exact_one_position_guard=(
            snapshot.input_generic_order_accepted_as_close_only_with_exact_one_position_guard
        ),
        official_gmo_rules_alignment_checked=(
            snapshot.official_gmo_rules_alignment_checked
        ),
        official_manual_url_recorded=snapshot.official_manual_url_recorded,
        official_trading_rules_url_recorded=(
            snapshot.official_trading_rules_url_recorded
        ),
        generic_opposite_order_as_close_forbidden=(
            snapshot.generic_opposite_order_as_close_forbidden
        ),
        generic_close_primitive_revoked=snapshot.generic_close_primitive_revoked,
        official_settlement_route_confirmed=snapshot.official_settlement_route_confirmed,
        close_execution_blocked_reason=_close_execution_blocked_reason(reasons),
        runtime_position_status=snapshot.runtime_position_status,
        position_count_safe=snapshot.position_count_safe,
        has_exactly_one_position=snapshot.has_exactly_one_position,
        has_multiple_positions=snapshot.has_multiple_positions,
        close_symbol_safe_label=snapshot.close_symbol_safe_label,
        close_side_safe_label=snapshot.close_side_safe_label,
        close_units_fixed=snapshot.close_units_fixed,
        close_order_type_safe_label=snapshot.close_order_type_safe_label,
        one_close_post_max=snapshot.one_close_post_max,
        close_retry_allowed=False,
        close_repost_allowed=False,
        close_second_post_allowed=False,
        entry_post_this_step=False,
        actual_close_post_allowed_now=False,
        actual_close_post_executed=False,
        transport_call_count=0,
        ledger_update_this_step=False,
        receipt_handoff_this_step=False,
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
        recommended_next_step=(
            NEXT_STEP_CLOSE_EXECUTION_GATE_RETRY_WITH_COMPATIBLE_EXECUTOR
            if ready
            else (
                NEXT_STEP_OFFICIAL_SETTLEMENT_ROUTE_REVIEW
                if "official_settlement_route_not_confirmed" in reasons
                else NEXT_STEP_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_FIX
            )
        ),
        blocked_reasons=reasons,
    )


def connect_close_actual_executor_compatibility_level5(
    *,
    compatibility_ready: bool,
    previous_cycle_state: str = PREVIOUS_CYCLE_STATE_CLOSE_EXECUTION_GATE_READY,
    blocked_reasons: tuple[str, ...] = (),
) -> CloseActualExecutorCompatibilityLevel5ConnectionResult:
    """Represent the Level 5 no-POST transition for close compatibility."""
    safe_reasons = blocked_reasons if isinstance(blocked_reasons, tuple) else tuple(blocked_reasons)
    next_state = (
        NEXT_CYCLE_STATE_CLOSE_ACTUAL_EXECUTOR_READY
        if compatibility_ready and previous_cycle_state == NEXT_CYCLE_STATE_READY
        else NEXT_CYCLE_STATE_CLOSE_ACTUAL_EXECUTOR_BLOCKED
    )
    connection_reasons = safe_reasons
    if previous_cycle_state != NEXT_CYCLE_STATE_READY:
        connection_reasons = tuple(
            dict.fromkeys((*connection_reasons, "previous_cycle_state_not_close_gate_ready")),
        )
    return CloseActualExecutorCompatibilityLevel5ConnectionResult(
        previous_cycle_state=previous_cycle_state,
        next_cycle_state=next_state,
        close_execution_gate_may_be_planned=compatibility_ready,
        close_sent_reached=False,
        close_post_executed_reached=False,
        post_close_position_confirmation_reached=False,
        ledger_updated_reached=False,
        receipt_handoff_reached=False,
        level5_full_auto_cycle_completed=False,
        blocked_reasons=connection_reasons,
    )


def render_close_actual_executor_compatibility_markdown(
    result: CloseActualExecutorCompatibilityControlledResult,
) -> str:
    """Render a safe close-specific executor compatibility preview only."""
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Close Actual Executor Compatibility Controlled",
            "",
            "This compatibility route renders a sanitized close executor preview only.",
            "It does not execute actual close POST or entry POST.",
            "It does not retry, repost, update ledgers, or hand off receipts.",
            "",
            f"execution_step: {EXECUTION_STEP_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY}",
            f"close_specific_context: {_bool_text(result.close_specific_context)}",
            f"generic_entry_context: {_bool_text(result.generic_entry_context)}",
            f"runtime_position_status: {result.runtime_position_status.value}",
            f"position_count_safe: {result.position_count_safe}",
            f"close_symbol_safe_label: {result.close_symbol_safe_label}",
            f"close_side_safe_label: {result.close_side_safe_label}",
            f"close_units_fixed: {result.close_units_fixed}",
            f"close_order_type_safe_label: {result.close_order_type_safe_label}",
            (
                "approved_close_post_primitive_ready: "
                f"{_bool_text(result.input_approved_close_post_primitive_ready)}"
            ),
            (
                "approved_close_post_primitive_kind: "
                f"{result.input_approved_close_post_primitive_kind}"
            ),
            (
                "official_gmo_rules_alignment_checked: "
                f"{_bool_text(result.official_gmo_rules_alignment_checked)}"
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
            f"close_execution_blocked_reason: {result.close_execution_blocked_reason}",
            f"one_close_post_max: {_bool_text(result.one_close_post_max)}",
            f"close_retry_allowed: {_bool_text(result.close_retry_allowed)}",
            f"close_repost_allowed: {_bool_text(result.close_repost_allowed)}",
            f"close_second_post_allowed: {_bool_text(result.close_second_post_allowed)}",
            f"entry_post_this_step: {_bool_text(result.entry_post_this_step)}",
            (
                "actual_close_post_allowed_now: "
                f"{_bool_text(result.actual_close_post_allowed_now)}"
            ),
            f"actual_close_post_executed: {_bool_text(result.actual_close_post_executed)}",
            f"transport_call_count: {result.transport_call_count}",
            f"ledger_update_this_step: {_bool_text(result.ledger_update_this_step)}",
            f"receipt_handoff_this_step: {_bool_text(result.receipt_handoff_this_step)}",
            f"raw_exposure: {_bool_text(result.executable_preview.raw_exposure)}",
            f"id_exposure: {_bool_text(result.executable_preview.id_exposure)}",
            (
                "credential_value_exposure: "
                f"{_bool_text(result.executable_preview.credential_value_exposure)}"
            ),
            (
                "signature_value_exposure: "
                f"{_bool_text(result.executable_preview.signature_value_exposure)}"
            ),
            (
                "headers_value_exposure: "
                f"{_bool_text(result.executable_preview.headers_value_exposure)}"
            ),
            (
                "actual_close_post_requires_separate_close_execution_gate: "
                f"{_bool_text(True)}"
            ),
            f"next_cycle_state: {result.level5_connection.next_cycle_state}",
            f"blocked_reasons: {blocked}",
            f"recommended_next_step: {result.recommended_next_step}",
        ),
    ) + "\n"


def _input_from_close_execution_route(
    result: CloseOrderExecutionRouteControlledResult | None,
) -> CloseActualExecutorCompatibilityControlledInput:
    if result is None:
        return CloseActualExecutorCompatibilityControlledInput()
    return CloseActualExecutorCompatibilityControlledInput(
        input_close_execution_route_ready=result.close_execution_route_ready,
        input_close_executable_preview_ready=result.close_executable_preview_ready,
        input_approved_close_post_primitive_ready=(
            result.approved_close_post_primitive_ready
        ),
        input_approved_close_post_primitive_kind=result.approved_close_post_primitive_kind,
        input_approved_close_post_primitive_is_generic_order=(
            result.approved_close_post_primitive_is_generic_order
        ),
        input_generic_order_accepted_as_close_only_with_exact_one_position_guard=(
            result.generic_order_accepted_as_close_only_with_exact_one_position_guard
        ),
        official_gmo_rules_alignment_checked=result.official_gmo_rules_alignment_checked,
        official_manual_url_recorded=result.official_manual_url_recorded,
        official_trading_rules_url_recorded=result.official_trading_rules_url_recorded,
        generic_opposite_order_as_close_forbidden=(
            result.generic_opposite_order_as_close_forbidden
        ),
        generic_close_primitive_revoked=result.generic_close_primitive_revoked,
        official_settlement_route_confirmed=result.official_settlement_route_confirmed,
        runtime_position_status=result.runtime_position_status,
        position_count_safe=result.position_count_safe,
        has_exactly_one_position=result.has_exactly_one_position,
        has_multiple_positions=result.has_multiple_positions,
        close_symbol_safe_label=result.close_symbol_safe_label,
        close_side_safe_label=result.close_side_safe_label,
        close_units_fixed=result.close_units_fixed,
        close_order_type_safe_label=result.close_order_type_safe_label,
        one_close_post_max=result.one_close_post_max,
        close_retry_allowed=result.close_retry_allowed,
        close_repost_allowed=result.close_repost_allowed,
        close_second_post_allowed=result.close_second_post_allowed,
        entry_post_this_step=result.entry_post_this_step,
        actual_close_post_allowed_now=result.actual_close_post_allowed_now,
        actual_close_post_attempted_this_step=result.actual_close_post_executed,
        ledger_update_this_step=result.ledger_update_this_step,
        receipt_handoff_this_step=result.receipt_handoff_this_step,
        raw_position_exposure_attempted=result.raw_position_exposed,
        raw_request_exposure_attempted=result.raw_request_exposed,
        raw_response_exposure_attempted=result.raw_response_exposed,
        broker_api_response_exposure_attempted=result.broker_api_response_exposed,
        position_id_exposure_attempted=result.position_id_exposed,
        account_id_exposure_attempted=result.account_id_exposed,
        order_id_exposure_attempted=result.order_id_exposed,
        transaction_id_exposure_attempted=result.transaction_id_exposed,
        credential_value_exposure_attempted=result.credential_value_exposed,
        signature_value_exposure_attempted=result.signature_value_exposed,
        headers_value_exposure_attempted=result.headers_value_exposed,
    )


def _blocked_reasons(
    snapshot: CloseActualExecutorCompatibilityControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.close_specific_context:
        reasons.append("close_specific_context_required")
    if snapshot.generic_entry_context:
        reasons.append("generic_entry_context_not_allowed_for_close")
    if not snapshot.input_close_execution_route_ready:
        reasons.append("input_close_execution_route_not_ready")
    if not snapshot.input_close_executable_preview_ready:
        reasons.append("input_close_executable_preview_not_ready")
    if not snapshot.input_approved_close_post_primitive_ready:
        reasons.append("input_approved_close_post_primitive_not_ready")
    if snapshot.input_approved_close_post_primitive_is_generic_order:
        reasons.append("generic_opposite_order_as_close_forbidden")
        reasons.append("generic_close_primitive_revoked")
    if (
        not snapshot.input_approved_close_post_primitive_is_generic_order
        and snapshot.input_approved_close_post_primitive_kind
        != APPROVED_CLOSE_PRIMITIVE_KIND_CLOSE_SPECIFIC
    ):
        reasons.append("official_settlement_close_specific_primitive_required")
    if (
        snapshot.input_approved_close_post_primitive_kind
        != APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC
    ):
        if snapshot.input_approved_close_post_primitive_kind not in {
            APPROVED_CLOSE_PRIMITIVE_KIND_CLOSE_SPECIFIC,
            APPROVED_CLOSE_PRIMITIVE_KIND_DEPRECATED_UNSAFE_GENERIC,
        }:
            reasons.append("approved_close_post_primitive_kind_not_supported")
    else:
        reasons.append("guarded_generic_close_primitive_deprecated_unsafe")
    if (
        snapshot.input_approved_close_post_primitive_is_generic_order
        and not snapshot.input_generic_order_accepted_as_close_only_with_exact_one_position_guard
    ):
        reasons.append("generic_order_close_exact_one_position_guard_required")
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
    if not snapshot.official_settlement_route_confirmed:
        reasons.append("official_settlement_route_not_confirmed")
    if snapshot.runtime_position_status is not PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        reasons.append("runtime_position_status_not_one_position_open")
    if snapshot.position_count_safe != 1:
        reasons.append("position_count_safe_not_1")
    if not snapshot.has_exactly_one_position:
        reasons.append("has_exactly_one_position_required")
    if snapshot.has_multiple_positions:
        reasons.append("has_multiple_positions_blocked")
    if snapshot.close_symbol_safe_label != SUPPORTED_SYMBOL:
        reasons.append("close_symbol_safe_label_must_match_supported_symbol")
    if snapshot.close_side_safe_label not in _CONCRETE_CLOSE_SIDE_LABELS:
        reasons.append("close_side_safe_label_must_be_concrete_buy_or_sell")
    if snapshot.close_side_safe_label == CLOSE_SIDE_SAFE_LABEL:
        reasons.append("opposite_placeholder_not_executable")
    if snapshot.close_units_fixed != SUPPORTED_UNITS:
        reasons.append("close_units_must_be_100")
    if snapshot.close_order_type_safe_label != CLOSE_ORDER_TYPE_SAFE_LABEL:
        reasons.append("close_order_type_must_be_market")
    if not snapshot.one_close_post_max:
        reasons.append("one_close_post_max_required")
    for field_name in (
        "close_retry_allowed",
        "close_repost_allowed",
        "close_second_post_allowed",
        "entry_post_this_step",
        "actual_close_post_allowed_now",
        "actual_close_post_attempted_this_step",
        "ledger_update_this_step",
        "receipt_handoff_this_step",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    if snapshot.transport_call_count != 0:
        reasons.append("transport_call_count_must_remain_0")
    if _raw_exposure_attempted(snapshot):
        reasons.append("raw_exposure_blocked")
    if _id_exposure_attempted(snapshot):
        reasons.append("id_exposure_blocked")
    if _credential_exposure_attempted(snapshot):
        reasons.append("credential_signature_headers_exposure_blocked")
    return tuple(dict.fromkeys(reasons))


def _close_execution_blocked_reason(reasons: tuple[str, ...]) -> str:
    if "official_settlement_route_not_confirmed" in reasons:
        return OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED
    if "generic_close_primitive_revoked" in reasons:
        return "GENERIC_CLOSE_PRIMITIVE_REVOKED"
    if reasons:
        return "CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED"
    return "NONE_NO_ACTUAL_POST_IN_THIS_STEP"


def _status_from_reasons(
    reasons: tuple[str, ...],
) -> CloseActualExecutorCompatibilityControlledStatus:
    if not reasons:
        return CloseActualExecutorCompatibilityControlledStatus.READY_NO_POST
    if "generic_close_primitive_revoked" in reasons:
        return (
            CloseActualExecutorCompatibilityControlledStatus
            .DEPRECATED_UNSAFE_GENERIC_CLOSE
        )
    if "official_settlement_route_not_confirmed" in reasons:
        return (
            CloseActualExecutorCompatibilityControlledStatus
            .BLOCKED_OFFICIAL_SETTLEMENT_ROUTE
        )
    if any(reason.endswith("_exposure_blocked") for reason in reasons):
        return CloseActualExecutorCompatibilityControlledStatus.BLOCKED_UNSAFE
    context_blocked = any(
        reason.endswith("_context_required") or "generic_entry_context" in reason
        for reason in reasons
    )
    if context_blocked:
        return CloseActualExecutorCompatibilityControlledStatus.BLOCKED_CONTEXT
    if any(reason.startswith("input_close_") for reason in reasons):
        return CloseActualExecutorCompatibilityControlledStatus.BLOCKED_ROUTE
    return CloseActualExecutorCompatibilityControlledStatus.BLOCKED_GUARD


def _sanitized_preview(
    snapshot: CloseActualExecutorCompatibilityControlledInput,
    preview_ready: bool,
) -> SanitizedCloseActualExecutorPreview:
    return SanitizedCloseActualExecutorPreview(
        preview_ready=preview_ready,
        execution_step=EXECUTION_STEP_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY,
        safe_preview_label=SAFE_CLOSE_SPECIFIC_EXECUTOR_PREVIEW_LABEL,
        close_specific_context=snapshot.close_specific_context,
        generic_entry_context=snapshot.generic_entry_context,
        runtime_position_status=snapshot.runtime_position_status,
        position_count_safe=snapshot.position_count_safe,
        close_symbol_safe_label=snapshot.close_symbol_safe_label,
        close_side_safe_label=snapshot.close_side_safe_label,
        close_units_fixed=snapshot.close_units_fixed,
        close_order_type_safe_label=snapshot.close_order_type_safe_label,
        approved_close_post_primitive_ready=(
            snapshot.input_approved_close_post_primitive_ready
        ),
        approved_close_post_primitive_kind=(
            snapshot.input_approved_close_post_primitive_kind
        ),
        one_close_post_max=snapshot.one_close_post_max,
        close_retry_allowed=False,
        close_repost_allowed=False,
        close_second_post_allowed=False,
        entry_post_this_step=False,
        actual_close_post_allowed_now=False,
        actual_close_post_executed=False,
        transport_call_count=0,
        ledger_update_this_step=False,
        receipt_handoff_this_step=False,
        raw_exposure=False,
        id_exposure=False,
        credential_value_exposure=False,
        signature_value_exposure=False,
        headers_value_exposure=False,
        actual_close_post_requires_separate_close_execution_gate=True,
    )


def _one_shot_executor_preview(
    snapshot: CloseActualExecutorCompatibilityControlledInput,
    preview_ready: bool,
    blocked_reasons: tuple[str, ...],
) -> LiveOrderRealExecutableOrderPreviewResult:
    status = (
        LiveOrderRealExecutableOrderPreviewStatus.EXECUTABLE_ORDER_PREVIEW_AVAILABLE_SAFE_SUMMARY
        if preview_ready
        else (
            LiveOrderRealExecutableOrderPreviewStatus
            .EXECUTABLE_ORDER_PREVIEW_BLOCKED_ORDER_AMBIGUITY
        )
    )
    return LiveOrderRealExecutableOrderPreviewResult(
        status=status,
        sanitized_order_preview_available=preview_ready,
        order_ambiguity=not preview_ready,
        execution_step=EXECUTION_STEP_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY,
        safe_preview_label=SAFE_EXECUTABLE_ORDER_PREVIEW_LABEL,
        fresh_preflight_passed=True,
        final_confirmation_received=True,
        ready_gate_passed=True,
        post_guard_ready=True,
        one_post_max=True,
        retry_allowed=False,
        timeout_fail_closed=True,
        actual_post_requires_post_specific_confirmation=True,
        ledger_update_this_step=False,
        receipt_handoff_this_step=False,
        raw_exposure=False,
        id_exposure=False,
        credential_value_exposure=False,
        signature_value_exposure=False,
        headers_value_exposure=False,
        symbol=(
            snapshot.close_symbol_safe_label
            if preview_ready
            else UNSUPPORTED_ONE_SHOT_POST_EXECUTION_LABEL
        ),
        side=(
            snapshot.close_side_safe_label
            if preview_ready
            else UNSUPPORTED_ONE_SHOT_POST_EXECUTION_LABEL
        ),
        order_type=(
            snapshot.close_order_type_safe_label
            if preview_ready
            else UNSUPPORTED_ONE_SHOT_POST_EXECUTION_LABEL
        ),
        size=snapshot.close_units_fixed if preview_ready else 0,
        time_in_force_label=SAFE_TIME_IN_FORCE_LABEL,
        environment_label=SAFE_ENVIRONMENT_LABEL,
        risk_label=SAFE_RISK_LABEL,
        safe_order_source_label="STEP6G_CLOSE_EXECUTION_ROUTE_SAFE_PREVIEW",
        codex_inferred_symbol=False,
        codex_inferred_side=False,
        codex_inferred_size=False,
        codex_inferred_order_type=False,
        blocked_reasons=blocked_reasons,
    )


def _raw_exposure_attempted(
    snapshot: CloseActualExecutorCompatibilityControlledInput,
) -> bool:
    return (
        snapshot.raw_position_exposure_attempted
        or snapshot.raw_request_exposure_attempted
        or snapshot.raw_response_exposure_attempted
        or snapshot.broker_api_response_exposure_attempted
    )


def _id_exposure_attempted(
    snapshot: CloseActualExecutorCompatibilityControlledInput,
) -> bool:
    return (
        snapshot.position_id_exposure_attempted
        or snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
        or snapshot.real_id_exposure_attempted
        or snapshot.client_order_id_actual_value_exposure_attempted
    )


def _credential_exposure_attempted(
    snapshot: CloseActualExecutorCompatibilityControlledInput,
) -> bool:
    return (
        snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
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


_PREVIEW_BOOL_FIELDS = (
    "preview_ready",
    "close_specific_context",
    "generic_entry_context",
    "approved_close_post_primitive_ready",
    "one_close_post_max",
    "close_retry_allowed",
    "close_repost_allowed",
    "close_second_post_allowed",
    "entry_post_this_step",
    "actual_close_post_allowed_now",
    "actual_close_post_executed",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "raw_exposure",
    "id_exposure",
    "credential_value_exposure",
    "signature_value_exposure",
    "headers_value_exposure",
    "actual_close_post_requires_separate_close_execution_gate",
)

_INPUT_BOOL_FIELDS = (
    "close_specific_context",
    "generic_entry_context",
    "input_close_execution_route_ready",
    "input_close_executable_preview_ready",
    "input_approved_close_post_primitive_ready",
    "input_approved_close_post_primitive_is_generic_order",
    "input_generic_order_accepted_as_close_only_with_exact_one_position_guard",
    "official_gmo_rules_alignment_checked",
    "official_manual_url_recorded",
    "official_trading_rules_url_recorded",
    "generic_opposite_order_as_close_forbidden",
    "generic_close_primitive_revoked",
    "official_settlement_route_confirmed",
    "has_exactly_one_position",
    "has_multiple_positions",
    "one_close_post_max",
    "close_retry_allowed",
    "close_repost_allowed",
    "close_second_post_allowed",
    "entry_post_this_step",
    "actual_close_post_allowed_now",
    "actual_close_post_attempted_this_step",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "raw_position_exposure_attempted",
    "raw_request_exposure_attempted",
    "raw_response_exposure_attempted",
    "broker_api_response_exposure_attempted",
    "position_id_exposure_attempted",
    "account_id_exposure_attempted",
    "order_id_exposure_attempted",
    "transaction_id_exposure_attempted",
    "trade_id_exposure_attempted",
    "real_id_exposure_attempted",
    "client_order_id_actual_value_exposure_attempted",
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
)

_LEVEL5_CONNECTION_BOOL_FIELDS = (
    "close_execution_gate_may_be_planned",
    "close_sent_reached",
    "close_post_executed_reached",
    "post_close_position_confirmation_reached",
    "ledger_updated_reached",
    "receipt_handoff_reached",
    "level5_full_auto_cycle_completed",
)

_RESULT_BOOL_FIELDS = (
    "close_actual_executor_compatibility_ready",
    "close_specific_executor_preview_ready",
    "close_specific_context",
    "generic_entry_context",
    "generic_entry_buy_guard_intact",
    "generic_entry_sell_blocked",
    "close_specific_sell_accepted",
    "close_specific_buy_accepted",
    "exact_one_position_guard_required",
    "approved_primitive_required",
    "input_close_execution_route_ready",
    "input_close_executable_preview_ready",
    "input_approved_close_post_primitive_ready",
    "input_approved_close_post_primitive_is_generic_order",
    "input_generic_order_accepted_as_close_only_with_exact_one_position_guard",
    "official_gmo_rules_alignment_checked",
    "official_manual_url_recorded",
    "official_trading_rules_url_recorded",
    "generic_opposite_order_as_close_forbidden",
    "generic_close_primitive_revoked",
    "official_settlement_route_confirmed",
    "has_exactly_one_position",
    "has_multiple_positions",
    "one_close_post_max",
    "close_retry_allowed",
    "close_repost_allowed",
    "close_second_post_allowed",
    "entry_post_this_step",
    "actual_close_post_allowed_now",
    "actual_close_post_executed",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
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
