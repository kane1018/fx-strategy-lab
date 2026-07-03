"""Step 6G close order execution route foundation.

This module turns planning-only close route state into a sanitized executable
preview contract. It never invokes a primitive and never imports broker,
Private API, HTTP, env, ledger, receipt, or live_order_once code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_close_order_route_controlled import (
    CLOSE_ORDER_TYPE_SAFE_LABEL,
    CLOSE_SIDE_SAFE_LABEL,
    CloseOrderRouteControlledResult,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

SAFE_CLOSE_ORDER_EXECUTION_ROUTE_LABEL = (
    "STEP6G_CLOSE_ORDER_EXECUTION_ROUTE_CONTROLLED_NO_POST"
)
SAFE_CLOSE_EXECUTABLE_PREVIEW_LABEL = (
    "STEP6G_SANITIZED_CLOSE_EXECUTABLE_PREVIEW_NO_POST"
)
EXECUTION_STEP_CLOSE_ROUTE_NO_POST = (
    "CLOSE_ORDER_EXECUTION_ROUTE_IMPLEMENTATION_NO_POST_C"
)
NEXT_STEP_CLOSE_EXECUTION_GATE_RETRY = (
    "Step 6G-PC-OX-R-CLOSE-ORDER-EXECUTION-GATE-C-RETRY-WITH-EXECUTABLE-ROUTE"
)
NEXT_STEP_CLOSE_PRIMITIVE_REVIEW = (
    "Step 6G-PC-OX-R-CLOSE-PRIMITIVE-APPROVAL-REVIEW-C"
)
APPROVED_CLOSE_PRIMITIVE_KIND_NOT_APPROVED = "NOT_APPROVED"
APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC = (
    "GUARDED_GENERIC_ORDER_CLOSE_PRIMITIVE_NO_POST"
)
APPROVED_CLOSE_PRIMITIVE_KIND_CLOSE_SPECIFIC = (
    "CLOSE_SPECIFIC_APPROVED_PRIMITIVE_NO_POST"
)
PREVIOUS_CYCLE_STATE_FRESH_HANDOFF = "FRESH_POSITION_OPEN_SAFE_HANDOFF_READY"
NEXT_CYCLE_STATE_READY = "CLOSE_EXECUTION_GATE_READY_NO_POST"
NEXT_CYCLE_STATE_SIDE_UNRESOLVED = (
    "CLOSE_EXECUTION_ROUTE_BLOCKED_SIDE_UNRESOLVED"
)
NEXT_CYCLE_STATE_SIDE_MISMATCH = "CLOSE_EXECUTION_ROUTE_BLOCKED_SIDE_MISMATCH"
NEXT_CYCLE_STATE_PRIMITIVE_MISSING = (
    "CLOSE_EXECUTION_ROUTE_BLOCKED_PRIMITIVE_MISSING"
)
NEXT_CYCLE_STATE_POSITION_BLOCKED = "CLOSE_EXECUTION_ROUTE_BLOCKED_POSITION"
NEXT_CYCLE_STATE_UNSAFE_BLOCKED = "CLOSE_EXECUTION_ROUTE_BLOCKED_UNSAFE"
SAFE_SIDE_BUY = "BUY"
SAFE_SIDE_SELL = "SELL"
SIDE_SOURCE_NONE = "NONE"
SIDE_SOURCE_MULTIPLE_SAFE_INPUTS = "MULTIPLE_SAFE_INPUTS"
SIDE_SOURCE_FRESH_ENTRY = "fresh_entry_side_safe_label"
SIDE_SOURCE_OPERATOR_SIGNAL = "operator_signal_type"
SIDE_SOURCE_POSITION_SIDE = "safe_position_side_label"
OPERATOR_SIGNAL_ENTRY_BUY = "ENTRY_BUY"
OPERATOR_SIGNAL_ENTRY_SELL = "ENTRY_SELL"
SIDE_NOT_PROVIDED = "NOT_PROVIDED"

_CONCRETE_SIDE_LABELS = frozenset({SAFE_SIDE_BUY, SAFE_SIDE_SELL})
_UNRESOLVED_SIDE_LABELS = frozenset(
    {
        SIDE_NOT_PROVIDED,
        "UNKNOWN",
        "NONE",
        "MIXED",
        "MULTIPLE",
        "NOT_APPLICABLE",
        CLOSE_SIDE_SAFE_LABEL,
    },
)


class CloseOrderExecutionRouteControlledStatus(str, Enum):
    READY_NO_POST = "CLOSE_EXECUTION_ROUTE_READY_NO_POST"
    BLOCKED_SIDE_UNRESOLVED = (
        "CLOSE_EXECUTION_ROUTE_BLOCKED_SIDE_UNRESOLVED"
    )
    BLOCKED_SIDE_MISMATCH = "CLOSE_EXECUTION_ROUTE_BLOCKED_SIDE_MISMATCH"
    BLOCKED_POSITION = "CLOSE_EXECUTION_ROUTE_BLOCKED_POSITION"
    BLOCKED_PRIMITIVE_MISSING = (
        "CLOSE_EXECUTION_ROUTE_BLOCKED_PRIMITIVE_MISSING"
    )
    BLOCKED_UNSAFE = "CLOSE_EXECUTION_ROUTE_BLOCKED_UNSAFE"


@dataclass(frozen=True)
class CloseSideDerivationSummary:
    close_side_derivation_source: str
    input_side_safe_label: str
    close_side_safe_label: str
    side_concrete: bool
    opposite_placeholder_accepted: bool
    side_mismatch_detected: bool
    codex_inferred_side: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "close_side_derivation_source",
            "input_side_safe_label",
            "close_side_safe_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _SIDE_DERIVATION_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


@dataclass(frozen=True)
class SanitizedCloseExecutablePreview:
    preview_ready: bool
    execution_step: str
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
            "close_symbol_safe_label",
            "close_side_safe_label",
            "close_order_type_safe_label",
            "approved_close_post_primitive_kind",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("close_units_fixed", self.close_units_fixed)
        _validate_bool_fields(self, _PREVIEW_BOOL_FIELDS)


@dataclass(frozen=True)
class CloseOrderExecutionRouteControlledInput:
    previous_cycle_state: str = PREVIOUS_CYCLE_STATE_FRESH_HANDOFF
    runtime_position_status: PositionReadOnlyControlledStatus = (
        PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    )
    position_count_safe: int = 0
    has_exactly_one_position: bool = False
    has_multiple_positions: bool = False
    close_route_ready: bool = False
    close_planning_allowed: bool = False
    fresh_entry_side_safe_label: str = SIDE_NOT_PROVIDED
    operator_signal_type: str = SIDE_NOT_PROVIDED
    safe_position_side_label: str = SIDE_NOT_PROVIDED
    close_symbol_safe_label: str = SUPPORTED_SYMBOL
    close_units_fixed: int = SUPPORTED_UNITS
    close_order_type_safe_label: str = CLOSE_ORDER_TYPE_SAFE_LABEL
    approved_close_post_primitive_kind: str = APPROVED_CLOSE_PRIMITIVE_KIND_NOT_APPROVED
    approved_close_post_primitive_is_close_specific: bool = False
    approved_close_post_primitive_is_generic_order: bool = False
    generic_order_accepted_as_close_only_with_exact_one_position_guard: bool = False
    close_primitive_invocation_deferred: bool = True
    actual_close_post_allowed_now: bool = False
    one_close_post_max: bool = True
    close_retry_allowed: bool = False
    close_repost_allowed: bool = False
    close_second_post_allowed: bool = False
    entry_post_this_step: bool = False
    ledger_update_this_step: bool = False
    receipt_handoff_this_step: bool = False
    actual_close_post_attempted_this_step: bool = False
    raw_position_exposure_attempted: bool = False
    raw_request_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    broker_api_response_exposure_attempted: bool = False
    position_id_exposure_attempted: bool = False
    account_id_exposure_attempted: bool = False
    order_id_exposure_attempted: bool = False
    transaction_id_exposure_attempted: bool = False
    trade_id_exposure_attempted: bool = False
    client_order_id_actual_value_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        _require_non_empty("previous_cycle_state", self.previous_cycle_state)
        for field_name in (
            "fresh_entry_side_safe_label",
            "operator_signal_type",
            "safe_position_side_label",
            "close_symbol_safe_label",
            "close_order_type_safe_label",
            "approved_close_post_primitive_kind",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("close_units_fixed", self.close_units_fixed)
        _validate_bool_fields(self, _ROUTE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class CloseOrderExecutionRouteControlledResult:
    status: CloseOrderExecutionRouteControlledStatus
    close_execution_route_ready: bool
    close_executable_preview_ready: bool
    safe_close_execution_route_label: str
    side_derivation: CloseSideDerivationSummary
    executable_preview: SanitizedCloseExecutablePreview
    approved_close_post_primitive_ready: bool
    approved_close_post_primitive_kind: str
    approved_close_post_primitive_is_close_specific: bool
    approved_close_post_primitive_is_generic_order: bool
    generic_order_accepted_as_close_only_with_exact_one_position_guard: bool
    close_primitive_invocation_deferred: bool
    actual_close_post_allowed_now: bool
    previous_cycle_state: str
    next_cycle_state: str
    close_execution_gate_may_be_planned: bool
    close_sent_reached: bool
    close_post_executed_reached: bool
    post_close_position_confirmation_reached: bool
    ledger_updated_reached: bool
    receipt_handoff_reached: bool
    level5_full_auto_cycle_completed: bool
    runtime_position_status: PositionReadOnlyControlledStatus
    position_count_safe: int
    has_exactly_one_position: bool
    has_multiple_positions: bool
    close_route_ready: bool
    close_planning_allowed: bool
    close_symbol_safe_label: str
    close_side_safe_label: str
    close_units_fixed: int
    close_order_type_safe_label: str
    one_close_post_max: bool
    close_retry_allowed: bool
    close_repost_allowed: bool
    close_second_post_allowed: bool
    entry_post_this_step: bool
    ledger_update_this_step: bool
    receipt_handoff_this_step: bool
    actual_close_post_executed: bool
    close_post_execution_count: int
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
        if not isinstance(self.status, CloseOrderExecutionRouteControlledStatus):
            raise LiveVerificationValidationError(
                "status must be close execution route enum",
            )
        if not isinstance(self.runtime_position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        for field_name in (
            "safe_close_execution_route_label",
            "approved_close_post_primitive_kind",
            "previous_cycle_state",
            "next_cycle_state",
            "close_symbol_safe_label",
            "close_side_safe_label",
            "close_order_type_safe_label",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("close_units_fixed", self.close_units_fixed)
        _validate_non_negative_int(
            "close_post_execution_count",
            self.close_post_execution_count,
        )
        _validate_bool_fields(self, _ROUTE_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_close_order_execution_route_controlled(
    input_snapshot: CloseOrderExecutionRouteControlledInput | None = None,
    *,
    close_order_route_result: CloseOrderRouteControlledResult | None = None,
) -> CloseOrderExecutionRouteControlledResult:
    """Build a close executable preview contract without invoking any primitive."""
    snapshot = input_snapshot or _input_from_close_order_route(close_order_route_result)
    side_summary = derive_close_side_safe_label(snapshot)
    position_reasons = _position_blocked_reasons(snapshot)
    primitive_ready = _approved_close_primitive_ready(snapshot, side_summary)
    primitive_reasons = _primitive_blocked_reasons(snapshot, side_summary)
    unsafe_reasons = _unsafe_blocked_reasons(snapshot)
    contract_reasons = _contract_blocked_reasons(snapshot)
    reasons = tuple(
        dict.fromkeys(
            position_reasons
            + side_summary.blocked_reasons
            + primitive_reasons
            + unsafe_reasons
            + contract_reasons,
        ),
    )
    ready = not reasons
    next_state = _next_cycle_state(position_reasons, side_summary, primitive_ready, unsafe_reasons)
    status = _status_from_state(next_state, ready)
    preview = _sanitized_preview(snapshot, side_summary, primitive_ready, ready)
    return CloseOrderExecutionRouteControlledResult(
        status=status,
        close_execution_route_ready=ready,
        close_executable_preview_ready=ready,
        safe_close_execution_route_label=SAFE_CLOSE_ORDER_EXECUTION_ROUTE_LABEL,
        side_derivation=side_summary,
        executable_preview=preview,
        approved_close_post_primitive_ready=primitive_ready,
        approved_close_post_primitive_kind=snapshot.approved_close_post_primitive_kind,
        approved_close_post_primitive_is_close_specific=(
            snapshot.approved_close_post_primitive_is_close_specific
        ),
        approved_close_post_primitive_is_generic_order=(
            snapshot.approved_close_post_primitive_is_generic_order
        ),
        generic_order_accepted_as_close_only_with_exact_one_position_guard=(
            snapshot.generic_order_accepted_as_close_only_with_exact_one_position_guard
        ),
        close_primitive_invocation_deferred=True,
        actual_close_post_allowed_now=False,
        previous_cycle_state=snapshot.previous_cycle_state,
        next_cycle_state=next_state,
        close_execution_gate_may_be_planned=ready,
        close_sent_reached=False,
        close_post_executed_reached=False,
        post_close_position_confirmation_reached=False,
        ledger_updated_reached=False,
        receipt_handoff_reached=False,
        level5_full_auto_cycle_completed=False,
        runtime_position_status=snapshot.runtime_position_status,
        position_count_safe=snapshot.position_count_safe,
        has_exactly_one_position=snapshot.has_exactly_one_position,
        has_multiple_positions=snapshot.has_multiple_positions,
        close_route_ready=snapshot.close_route_ready,
        close_planning_allowed=snapshot.close_planning_allowed,
        close_symbol_safe_label=snapshot.close_symbol_safe_label,
        close_side_safe_label=side_summary.close_side_safe_label,
        close_units_fixed=SUPPORTED_UNITS,
        close_order_type_safe_label=CLOSE_ORDER_TYPE_SAFE_LABEL,
        one_close_post_max=True,
        close_retry_allowed=False,
        close_repost_allowed=False,
        close_second_post_allowed=False,
        entry_post_this_step=False,
        ledger_update_this_step=False,
        receipt_handoff_this_step=False,
        actual_close_post_executed=False,
        close_post_execution_count=0,
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
        recommended_next_step=(
            NEXT_STEP_CLOSE_EXECUTION_GATE_RETRY
            if ready
            else NEXT_STEP_CLOSE_PRIMITIVE_REVIEW
        ),
        blocked_reasons=reasons,
    )


def derive_close_side_safe_label(
    snapshot: CloseOrderExecutionRouteControlledInput,
) -> CloseSideDerivationSummary:
    candidates = _side_candidates(snapshot)
    if not candidates:
        placeholder_seen = _placeholder_side_seen(snapshot)
        reasons = (
            ("opposite_placeholder_not_executable",)
            if placeholder_seen
            else ("close_side_unresolved",)
        )
        return CloseSideDerivationSummary(
            close_side_derivation_source=SIDE_SOURCE_NONE,
            input_side_safe_label=CLOSE_SIDE_SAFE_LABEL if placeholder_seen else SIDE_NOT_PROVIDED,
            close_side_safe_label=CLOSE_SIDE_SAFE_LABEL,
            side_concrete=False,
            opposite_placeholder_accepted=False,
            side_mismatch_detected=False,
            codex_inferred_side=False,
            blocked_reasons=reasons,
        )
    side_labels = {candidate[2] for candidate in candidates}
    if len(side_labels) > 1:
        return CloseSideDerivationSummary(
            close_side_derivation_source=SIDE_SOURCE_MULTIPLE_SAFE_INPUTS,
            input_side_safe_label="CONFLICTING_SAFE_INPUTS",
            close_side_safe_label="SIDE_MISMATCH_BLOCKED",
            side_concrete=False,
            opposite_placeholder_accepted=False,
            side_mismatch_detected=True,
            codex_inferred_side=False,
            blocked_reasons=("close_side_safe_label_mismatch",),
        )
    source_label = (
        candidates[0][0]
        if len(candidates) == 1
        else SIDE_SOURCE_MULTIPLE_SAFE_INPUTS
    )
    input_label = (
        candidates[0][1]
        if len(candidates) == 1
        else "CONSISTENT_SAFE_INPUTS"
    )
    side_label = candidates[0][2]
    return CloseSideDerivationSummary(
        close_side_derivation_source=source_label,
        input_side_safe_label=input_label,
        close_side_safe_label=side_label,
        side_concrete=True,
        opposite_placeholder_accepted=False,
        side_mismatch_detected=False,
        codex_inferred_side=False,
        blocked_reasons=(),
    )


def render_close_order_executable_preview_markdown(
    result: CloseOrderExecutionRouteControlledResult,
) -> str:
    """Render a safe close executable preview only."""
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Close Order Execution Route Controlled",
            "",
            "This route renders a sanitized executable close preview only.",
            "It does not execute actual close POST or entry POST.",
            "It does not retry, repost, update ledgers, or hand off receipts.",
            "",
            f"execution_step: {EXECUTION_STEP_CLOSE_ROUTE_NO_POST}",
            f"runtime_position_status: {result.runtime_position_status.value}",
            f"position_count_safe: {result.position_count_safe}",
            f"close_symbol_safe_label: {result.close_symbol_safe_label}",
            f"close_side_safe_label: {result.close_side_safe_label}",
            f"close_units_fixed: {result.close_units_fixed}",
            f"close_order_type_safe_label: {result.close_order_type_safe_label}",
            (
                "approved_close_post_primitive_ready: "
                f"{_bool_text(result.approved_close_post_primitive_ready)}"
            ),
            (
                "approved_close_post_primitive_kind: "
                f"{result.approved_close_post_primitive_kind}"
            ),
            f"one_close_post_max: {_bool_text(result.one_close_post_max)}",
            f"close_retry_allowed: {_bool_text(result.close_retry_allowed)}",
            f"close_repost_allowed: {_bool_text(result.close_repost_allowed)}",
            (
                "close_second_post_allowed: "
                f"{_bool_text(result.close_second_post_allowed)}"
            ),
            f"entry_post_this_step: {_bool_text(result.entry_post_this_step)}",
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
            f"actual_close_post_allowed_now: {_bool_text(result.actual_close_post_allowed_now)}",
            f"actual_close_post_executed: {_bool_text(result.actual_close_post_executed)}",
            f"next_cycle_state: {result.next_cycle_state}",
            f"blocked_reasons: {blocked}",
            f"recommended_next_step: {result.recommended_next_step}",
        ),
    ) + "\n"


def _input_from_close_order_route(
    result: CloseOrderRouteControlledResult | None,
) -> CloseOrderExecutionRouteControlledInput:
    if result is None:
        return CloseOrderExecutionRouteControlledInput()
    return CloseOrderExecutionRouteControlledInput(
        runtime_position_status=(
            PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
            if result.close_planning_allowed
            else PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
        ),
        position_count_safe=1 if result.close_planning_allowed else 0,
        has_exactly_one_position=result.close_planning_allowed,
        has_multiple_positions=False,
        close_route_ready=result.close_route_ready,
        close_planning_allowed=result.close_planning_allowed,
        close_symbol_safe_label=result.close_symbol_safe_label,
        close_units_fixed=result.close_units_fixed,
        close_order_type_safe_label=result.close_order_type_safe_label,
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
        actual_close_post_attempted_this_step=result.close_post_executed,
        close_retry_allowed=result.close_retry_allowed,
        close_repost_allowed=result.close_repost_allowed,
        close_second_post_allowed=result.close_second_post_allowed,
    )


def _side_candidates(
    snapshot: CloseOrderExecutionRouteControlledInput,
) -> tuple[tuple[str, str, str], ...]:
    candidates: list[tuple[str, str, str]] = []
    entry_side = _close_side_from_entry_side(snapshot.fresh_entry_side_safe_label)
    if entry_side:
        candidates.append(
            (SIDE_SOURCE_FRESH_ENTRY, snapshot.fresh_entry_side_safe_label, entry_side),
        )
    operator_side = _close_side_from_operator_signal(snapshot.operator_signal_type)
    if operator_side:
        candidates.append(
            (SIDE_SOURCE_OPERATOR_SIGNAL, snapshot.operator_signal_type, operator_side),
        )
    position_side = _close_side_from_position_side(snapshot.safe_position_side_label)
    if position_side:
        candidates.append(
            (SIDE_SOURCE_POSITION_SIDE, snapshot.safe_position_side_label, position_side),
        )
    return tuple(candidates)


def _close_side_from_entry_side(side_label: str) -> str | None:
    if side_label == SAFE_SIDE_BUY:
        return SAFE_SIDE_SELL
    if side_label == SAFE_SIDE_SELL:
        return SAFE_SIDE_BUY
    if side_label in _UNRESOLVED_SIDE_LABELS:
        return None
    return None


def _close_side_from_operator_signal(signal_type: str) -> str | None:
    if signal_type == OPERATOR_SIGNAL_ENTRY_BUY:
        return SAFE_SIDE_SELL
    if signal_type == OPERATOR_SIGNAL_ENTRY_SELL:
        return SAFE_SIDE_BUY
    if signal_type in _UNRESOLVED_SIDE_LABELS:
        return None
    return None


def _close_side_from_position_side(side_label: str) -> str | None:
    if side_label == SAFE_SIDE_BUY:
        return SAFE_SIDE_SELL
    if side_label == SAFE_SIDE_SELL:
        return SAFE_SIDE_BUY
    if side_label in _UNRESOLVED_SIDE_LABELS:
        return None
    return None


def _placeholder_side_seen(snapshot: CloseOrderExecutionRouteControlledInput) -> bool:
    return (
        snapshot.fresh_entry_side_safe_label == CLOSE_SIDE_SAFE_LABEL
        or snapshot.operator_signal_type == CLOSE_SIDE_SAFE_LABEL
        or snapshot.safe_position_side_label == CLOSE_SIDE_SAFE_LABEL
    )


def _position_blocked_reasons(
    snapshot: CloseOrderExecutionRouteControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.runtime_position_status is not PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        reasons.append("runtime_position_status_not_one_position_open")
    if snapshot.position_count_safe != 1:
        reasons.append("position_count_safe_not_1")
    if not snapshot.has_exactly_one_position:
        reasons.append("has_exactly_one_position_required")
    if snapshot.has_multiple_positions:
        reasons.append("has_multiple_positions_blocked")
    if not snapshot.close_route_ready:
        reasons.append("close_route_not_ready")
    if not snapshot.close_planning_allowed:
        reasons.append("close_planning_not_allowed")
    if snapshot.close_units_fixed != SUPPORTED_UNITS:
        reasons.append("close_units_must_be_100")
    if snapshot.close_symbol_safe_label != SUPPORTED_SYMBOL:
        reasons.append("close_symbol_safe_label_must_match_supported_symbol")
    if snapshot.close_order_type_safe_label != CLOSE_ORDER_TYPE_SAFE_LABEL:
        reasons.append("close_order_type_must_be_market")
    return tuple(reasons)


def _approved_close_primitive_ready(
    snapshot: CloseOrderExecutionRouteControlledInput,
    side_summary: CloseSideDerivationSummary,
) -> bool:
    if not side_summary.side_concrete:
        return False
    if snapshot.approved_close_post_primitive_is_close_specific:
        return snapshot.approved_close_post_primitive_kind not in {
            APPROVED_CLOSE_PRIMITIVE_KIND_NOT_APPROVED,
            SIDE_NOT_PROVIDED,
        }
    if snapshot.approved_close_post_primitive_is_generic_order:
        return (
            snapshot.generic_order_accepted_as_close_only_with_exact_one_position_guard
            and snapshot.runtime_position_status
            is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
            and snapshot.position_count_safe == 1
            and snapshot.has_exactly_one_position
            and not snapshot.has_multiple_positions
            and snapshot.close_units_fixed == SUPPORTED_UNITS
            and snapshot.close_order_type_safe_label == CLOSE_ORDER_TYPE_SAFE_LABEL
            and snapshot.approved_close_post_primitive_kind
            == APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC
        )
    return False


def _primitive_blocked_reasons(
    snapshot: CloseOrderExecutionRouteControlledInput,
    side_summary: CloseSideDerivationSummary,
) -> tuple[str, ...]:
    if not side_summary.side_concrete:
        return ()
    if _approved_close_primitive_ready(snapshot, side_summary):
        return ()
    if snapshot.approved_close_post_primitive_is_generic_order:
        if not snapshot.generic_order_accepted_as_close_only_with_exact_one_position_guard:
            return ("generic_order_close_guard_missing",)
        if (
            snapshot.approved_close_post_primitive_kind
            != APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC
        ):
            return ("approved_close_post_primitive_kind_not_guarded_generic",)
    if snapshot.approved_close_post_primitive_is_close_specific:
        return ("approved_close_post_primitive_kind_missing",)
    return ("approved_close_post_primitive_missing",)


def _unsafe_blocked_reasons(
    snapshot: CloseOrderExecutionRouteControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if _raw_exposure_attempted(snapshot):
        reasons.append("raw_exposure_blocked")
    if _id_exposure_attempted(snapshot):
        reasons.append("id_exposure_blocked")
    if _credential_exposure_attempted(snapshot):
        reasons.append("credential_signature_headers_exposure_blocked")
    return tuple(reasons)


def _contract_blocked_reasons(
    snapshot: CloseOrderExecutionRouteControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "actual_close_post_allowed_now",
        "close_retry_allowed",
        "close_repost_allowed",
        "close_second_post_allowed",
        "entry_post_this_step",
        "ledger_update_this_step",
        "receipt_handoff_this_step",
        "actual_close_post_attempted_this_step",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    if not snapshot.one_close_post_max:
        reasons.append("one_close_post_max_required")
    if not snapshot.close_primitive_invocation_deferred:
        reasons.append("close_primitive_invocation_must_be_deferred")
    return tuple(reasons)


def _raw_exposure_attempted(snapshot: CloseOrderExecutionRouteControlledInput) -> bool:
    return (
        snapshot.raw_position_exposure_attempted
        or snapshot.raw_request_exposure_attempted
        or snapshot.raw_response_exposure_attempted
        or snapshot.broker_api_response_exposure_attempted
    )


def _id_exposure_attempted(snapshot: CloseOrderExecutionRouteControlledInput) -> bool:
    return (
        snapshot.position_id_exposure_attempted
        or snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
        or snapshot.client_order_id_actual_value_exposure_attempted
    )


def _credential_exposure_attempted(
    snapshot: CloseOrderExecutionRouteControlledInput,
) -> bool:
    return (
        snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
    )


def _next_cycle_state(
    position_reasons: tuple[str, ...],
    side_summary: CloseSideDerivationSummary,
    primitive_ready: bool,
    unsafe_reasons: tuple[str, ...],
) -> str:
    if unsafe_reasons:
        return NEXT_CYCLE_STATE_UNSAFE_BLOCKED
    if position_reasons:
        return NEXT_CYCLE_STATE_POSITION_BLOCKED
    if side_summary.side_mismatch_detected:
        return NEXT_CYCLE_STATE_SIDE_MISMATCH
    if not side_summary.side_concrete:
        return NEXT_CYCLE_STATE_SIDE_UNRESOLVED
    if not primitive_ready:
        return NEXT_CYCLE_STATE_PRIMITIVE_MISSING
    return NEXT_CYCLE_STATE_READY


def _status_from_state(
    next_state: str,
    ready: bool,
) -> CloseOrderExecutionRouteControlledStatus:
    if ready:
        return CloseOrderExecutionRouteControlledStatus.READY_NO_POST
    if next_state == NEXT_CYCLE_STATE_SIDE_MISMATCH:
        return CloseOrderExecutionRouteControlledStatus.BLOCKED_SIDE_MISMATCH
    if next_state == NEXT_CYCLE_STATE_SIDE_UNRESOLVED:
        return CloseOrderExecutionRouteControlledStatus.BLOCKED_SIDE_UNRESOLVED
    if next_state == NEXT_CYCLE_STATE_PRIMITIVE_MISSING:
        return CloseOrderExecutionRouteControlledStatus.BLOCKED_PRIMITIVE_MISSING
    if next_state == NEXT_CYCLE_STATE_UNSAFE_BLOCKED:
        return CloseOrderExecutionRouteControlledStatus.BLOCKED_UNSAFE
    return CloseOrderExecutionRouteControlledStatus.BLOCKED_POSITION


def _sanitized_preview(
    snapshot: CloseOrderExecutionRouteControlledInput,
    side_summary: CloseSideDerivationSummary,
    primitive_ready: bool,
    preview_ready: bool,
) -> SanitizedCloseExecutablePreview:
    return SanitizedCloseExecutablePreview(
        preview_ready=preview_ready,
        execution_step=EXECUTION_STEP_CLOSE_ROUTE_NO_POST,
        runtime_position_status=snapshot.runtime_position_status,
        position_count_safe=snapshot.position_count_safe,
        close_symbol_safe_label=snapshot.close_symbol_safe_label,
        close_side_safe_label=side_summary.close_side_safe_label,
        close_units_fixed=SUPPORTED_UNITS,
        close_order_type_safe_label=CLOSE_ORDER_TYPE_SAFE_LABEL,
        approved_close_post_primitive_ready=primitive_ready,
        approved_close_post_primitive_kind=snapshot.approved_close_post_primitive_kind,
        one_close_post_max=True,
        close_retry_allowed=False,
        close_repost_allowed=False,
        close_second_post_allowed=False,
        entry_post_this_step=False,
        ledger_update_this_step=False,
        receipt_handoff_this_step=False,
        raw_exposure=False,
        id_exposure=False,
        credential_value_exposure=False,
        signature_value_exposure=False,
        headers_value_exposure=False,
        actual_close_post_requires_separate_close_execution_gate=True,
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


_SIDE_DERIVATION_BOOL_FIELDS = (
    "side_concrete",
    "opposite_placeholder_accepted",
    "side_mismatch_detected",
    "codex_inferred_side",
)

_PREVIEW_BOOL_FIELDS = (
    "preview_ready",
    "approved_close_post_primitive_ready",
    "one_close_post_max",
    "close_retry_allowed",
    "close_repost_allowed",
    "close_second_post_allowed",
    "entry_post_this_step",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "raw_exposure",
    "id_exposure",
    "credential_value_exposure",
    "signature_value_exposure",
    "headers_value_exposure",
    "actual_close_post_requires_separate_close_execution_gate",
)

_ROUTE_INPUT_BOOL_FIELDS = (
    "has_exactly_one_position",
    "has_multiple_positions",
    "close_route_ready",
    "close_planning_allowed",
    "approved_close_post_primitive_is_close_specific",
    "approved_close_post_primitive_is_generic_order",
    "generic_order_accepted_as_close_only_with_exact_one_position_guard",
    "close_primitive_invocation_deferred",
    "actual_close_post_allowed_now",
    "one_close_post_max",
    "close_retry_allowed",
    "close_repost_allowed",
    "close_second_post_allowed",
    "entry_post_this_step",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "actual_close_post_attempted_this_step",
    "raw_position_exposure_attempted",
    "raw_request_exposure_attempted",
    "raw_response_exposure_attempted",
    "broker_api_response_exposure_attempted",
    "position_id_exposure_attempted",
    "account_id_exposure_attempted",
    "order_id_exposure_attempted",
    "transaction_id_exposure_attempted",
    "trade_id_exposure_attempted",
    "client_order_id_actual_value_exposure_attempted",
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
)

_ROUTE_RESULT_BOOL_FIELDS = (
    "close_execution_route_ready",
    "close_executable_preview_ready",
    "approved_close_post_primitive_ready",
    "approved_close_post_primitive_is_close_specific",
    "approved_close_post_primitive_is_generic_order",
    "generic_order_accepted_as_close_only_with_exact_one_position_guard",
    "close_primitive_invocation_deferred",
    "actual_close_post_allowed_now",
    "close_execution_gate_may_be_planned",
    "close_sent_reached",
    "close_post_executed_reached",
    "post_close_position_confirmation_reached",
    "ledger_updated_reached",
    "receipt_handoff_reached",
    "level5_full_auto_cycle_completed",
    "has_exactly_one_position",
    "has_multiple_positions",
    "close_route_ready",
    "close_planning_allowed",
    "one_close_post_max",
    "close_retry_allowed",
    "close_repost_allowed",
    "close_second_post_allowed",
    "entry_post_this_step",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "actual_close_post_executed",
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
