"""Official GMO FX settlement actual executor transport boundary, no POST.

This module turns the official size-based settlement compatibility result into
a dedicated actual-executor and transport boundary that future execution gates
can detect. It intentionally performs no HTTP call and does not import generic
order executors, live_order_once, broker/private API clients, env readers,
ledger, or receipt code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_official_settlement_actual_executor_compatibility_controlled import (  # noqa: E501
    OfficialSettlementActualExecutorCompatibilityResult,
    build_official_settlement_actual_executor_compatibility_controlled,
)
from app.live_verification.live_order_real_official_settlement_route_no_post_controlled import (  # noqa: E501
    SETTLEMENT_ORDER_TYPE_SAFE_LABEL_MARKET,
    SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED,
    SETTLEMENT_SIDE_SEMANTICS_CONFIRMED,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

EXECUTION_STEP_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_NO_POST = (
    "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_NO_POST_C"
)
SAFE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_LABEL = (
    "STEP6G_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BOUNDARY_NO_POST"
)
SAFE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_PLAN_LABEL = (
    "STEP6G_SANITIZED_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_PLAN_NO_POST"
)
SAFE_OFFICIAL_SETTLEMENT_TRANSPORT_BOUNDARY_LABEL = (
    "DEDICATED_OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_BOUNDARY_NO_POST"
)
OFFICIAL_SETTLEMENT_RESULT_ACTUAL_EXECUTOR_TRANSPORT_READY_NO_POST_SANITIZED = (
    "RESULT_ACTUAL_EXECUTOR_TRANSPORT_READY_NO_POST_SANITIZED"
)
PREVIOUS_CYCLE_STATE_OFFICIAL_SETTLEMENT_COMPATIBILITY_READY = (
    "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_READY_NO_POST"
)
NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_READY = (
    "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_READY_NO_POST"
)
NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED = (
    "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED"
)
NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-EXECUTION-GATE-C"
)
NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT = (
    "fix_official_settlement_actual_executor_transport_no_post"
)


class OfficialSettlementActualExecutorTransportNoPostStatus(str, Enum):
    READY_NO_POST = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_READY_NO_POST"
    )
    BLOCKED_COMPATIBILITY = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED_COMPATIBILITY"
    )
    BLOCKED_ROUTE = "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED_ROUTE"
    BLOCKED_POSITION = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED_POSITION"
    )
    BLOCKED_GENERIC_EXECUTOR = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED_GENERIC_EXECUTOR"
    )
    BLOCKED_POSITION_SPECIFIC_IDENTIFIER = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED_POSITION_SPECIFIC_IDENTIFIER"
    )
    BLOCKED_LIFECYCLE = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED_LIFECYCLE"
    )
    BLOCKED_UNSAFE = "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED_UNSAFE"


@dataclass(frozen=True)
class OfficialSettlementActualExecutorTransportInput:
    official_settlement_context: bool = True
    generic_order_context: bool = False
    dedicated_settlement_actual_executor_compatibility_ready: bool = True
    official_settlement_no_post_preview_ready: bool = True
    official_settlement_executor_preview_ready: bool = True
    settlement_route_kind: str = SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED
    settlement_route_is_generic_order: bool = False
    settlement_route_is_dedicated: bool = True
    generic_order_executor_used_for_settlement: bool = False
    live_order_once_used_for_settlement: bool = False
    generic_order_endpoint_used_for_settlement: bool = False
    one_shot_generic_order_path_used_for_settlement: bool = False
    position_specific_path_used: bool = False
    position_specific_identifier_safe_handling_ready: bool = False
    position_specific_preview_allowed: bool = False
    size_based_preview_allowed: bool = True
    runtime_position_status: PositionReadOnlyControlledStatus = (
        PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    )
    position_count_safe: int = 1
    has_exactly_one_position: bool = True
    has_multiple_positions: bool = False
    symbol_safe_label: str = SUPPORTED_SYMBOL
    settlement_size_safe_label: str = str(SUPPORTED_UNITS)
    settlement_order_type_safe_label: str = SETTLEMENT_ORDER_TYPE_SAFE_LABEL_MARKET
    settlement_side_semantics_safe_label: str = SETTLEMENT_SIDE_SEMANTICS_CONFIRMED
    one_settlement_post_max: bool = True
    actual_settlement_post_allowed_now: bool = False
    actual_settlement_post_executed: bool = False
    settlement_post_count: int = 0
    transport_call_count: int = 0
    http_post_executed: bool = False
    settlement_endpoint_called: bool = False
    generic_order_endpoint_called: bool = False
    entry_post_executed: bool = False
    generic_close_post_executed: bool = False
    retry_allowed: bool = False
    repost_allowed: bool = False
    second_settlement_allowed: bool = False
    ledger_update: bool = False
    receipt_handoff: bool = False
    raw_request_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    broker_api_response_exposure_attempted: bool = False
    account_id_exposure_attempted: bool = False
    order_id_exposure_attempted: bool = False
    transaction_id_exposure_attempted: bool = False
    position_id_exposure_attempted: bool = False
    trade_id_exposure_attempted: bool = False
    real_id_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    next_execution_gate_can_detect_actual_executor: bool = True
    next_execution_gate_still_requires_fresh_runtime_read: bool = True
    next_execution_gate_still_requires_operator_readiness: bool = True
    next_execution_gate_still_requires_settlement_specific_confirmation: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        for field_name in (
            "settlement_route_kind",
            "symbol_safe_label",
            "settlement_size_safe_label",
            "settlement_order_type_safe_label",
            "settlement_side_semantics_safe_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementActualExecutorPlan:
    plan_ready: bool
    execution_step: str
    safe_plan_label: str
    dedicated_actual_official_settlement_post_executor_available: bool
    settlement_route_kind: str
    settlement_route_is_generic_order: bool
    settlement_route_is_dedicated: bool
    symbol_safe_label: str
    settlement_size_safe_label: str
    settlement_order_type_safe_label: str
    settlement_side_semantics_safe_label: str
    runtime_position_status: PositionReadOnlyControlledStatus
    position_count_safe: int
    one_settlement_post_max: bool
    actual_settlement_post_allowed_now: bool
    actual_settlement_post_executed: bool
    settlement_post_count: int
    retry_allowed: bool
    repost_allowed: bool
    second_settlement_allowed: bool
    entry_post_executed: bool
    generic_close_post_executed: bool
    ledger_update: bool
    receipt_handoff: bool
    raw_id_value_credential_header_exposure: bool

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        for field_name in (
            "execution_step",
            "safe_plan_label",
            "settlement_route_kind",
            "symbol_safe_label",
            "settlement_size_safe_label",
            "settlement_order_type_safe_label",
            "settlement_side_semantics_safe_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_bool_fields(self, _PLAN_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementActualTransportBoundary:
    transport_boundary_label: str
    dedicated_actual_official_settlement_transport_boundary_ready: bool
    dedicated_settlement_transport: bool
    generic_order_transport: bool
    one_shot_generic_order_transport: bool
    can_call_live_order_once: bool
    position_specific_transport: bool
    size_based_transport: bool
    transport_invocation_deferred: bool
    transport_call_count: int
    http_post_executed: bool
    settlement_endpoint_called: bool
    generic_order_endpoint_called: bool
    live_order_once_called: bool
    raw_request_exposed: bool
    raw_response_exposed: bool
    broker_api_response_exposed: bool
    id_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool

    def __post_init__(self) -> None:
        _require_non_empty("transport_boundary_label", self.transport_boundary_label)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_bool_fields(self, _TRANSPORT_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementActualExecutorTransportLevel5Connection:
    previous_cycle_state: str
    next_cycle_state: str
    settlement_execution_gate_may_be_planned: bool
    settlement_post_executed_reached: bool
    post_settlement_position_confirmation_reached: bool
    ledger_updated_reached: bool
    receipt_handoff_reached: bool
    level5_minimal_cycle_completed: bool
    level5_full_auto_cycle_completed: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("previous_cycle_state", self.previous_cycle_state)
        _require_non_empty("next_cycle_state", self.next_cycle_state)
        _validate_bool_fields(self, _LEVEL5_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


@dataclass(frozen=True)
class OfficialSettlementActualExecutorTransportResult:
    status: OfficialSettlementActualExecutorTransportNoPostStatus
    dedicated_actual_official_settlement_post_executor_available: bool
    dedicated_actual_official_settlement_transport_boundary_ready: bool
    dedicated_settlement_actual_executor_compatibility_ready: bool
    official_settlement_no_post_preview_ready: bool
    official_settlement_executor_preview_ready: bool
    safe_executor_transport_label: str
    executor_plan: OfficialSettlementActualExecutorPlan
    transport_boundary: OfficialSettlementActualTransportBoundary
    level5_connection: OfficialSettlementActualExecutorTransportLevel5Connection
    settlement_route_kind: str
    settlement_route_is_generic_order: bool
    settlement_route_is_dedicated: bool
    generic_order_executor_used_for_settlement: bool
    live_order_once_used_for_settlement: bool
    generic_order_endpoint_used_for_settlement: bool
    one_shot_generic_order_path_used_for_settlement: bool
    position_specific_path_used: bool
    position_specific_identifier_safe_handling_ready: bool
    position_specific_preview_allowed: bool
    size_based_preview_allowed: bool
    actual_settlement_post_allowed_now: bool
    actual_settlement_post_executed: bool
    settlement_post_count: int
    transport_call_count: int
    http_post_executed: bool
    entry_post_executed: bool
    generic_close_post_executed: bool
    retry_allowed: bool
    repost_allowed: bool
    second_settlement_allowed: bool
    ledger_update: bool
    receipt_handoff: bool
    raw_id_value_credential_header_exposure: bool
    next_execution_gate_can_detect_actual_executor: bool
    next_execution_gate_still_requires_fresh_runtime_read: bool
    next_execution_gate_still_requires_operator_readiness: bool
    next_execution_gate_still_requires_settlement_specific_confirmation: bool
    result_safe_category: str
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, OfficialSettlementActualExecutorTransportNoPostStatus):
            raise LiveVerificationValidationError("status must be transport enum")
        for field_name in (
            "safe_executor_transport_label",
            "settlement_route_kind",
            "result_safe_category",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_official_settlement_actual_executor_transport_no_post_controlled(
    input_snapshot: OfficialSettlementActualExecutorTransportInput | None = None,
    *,
    compatibility_result: OfficialSettlementActualExecutorCompatibilityResult | None = None,
) -> OfficialSettlementActualExecutorTransportResult:
    """Build the dedicated actual settlement executor/transport boundary without POST."""
    snapshot = input_snapshot or _input_from_compatibility(
        compatibility_result
        or build_official_settlement_actual_executor_compatibility_controlled(),
    )
    reasons = _blocked_reasons(snapshot)
    ready = not reasons
    status = _status_from_reasons(reasons)
    exposure = _raw_exposure_attempted(snapshot) or _id_exposure_attempted(
        snapshot,
    ) or _credential_exposure_attempted(snapshot)
    executor_plan = _executor_plan(snapshot, ready, exposure)
    transport_boundary = _transport_boundary(snapshot, ready)
    level5_connection = _level5_connection(ready, reasons)

    return OfficialSettlementActualExecutorTransportResult(
        status=status,
        dedicated_actual_official_settlement_post_executor_available=ready,
        dedicated_actual_official_settlement_transport_boundary_ready=ready,
        dedicated_settlement_actual_executor_compatibility_ready=(
            snapshot.dedicated_settlement_actual_executor_compatibility_ready
        ),
        official_settlement_no_post_preview_ready=(
            snapshot.official_settlement_no_post_preview_ready
        ),
        official_settlement_executor_preview_ready=(
            snapshot.official_settlement_executor_preview_ready
        ),
        safe_executor_transport_label=(
            SAFE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_LABEL
        ),
        executor_plan=executor_plan,
        transport_boundary=transport_boundary,
        level5_connection=level5_connection,
        settlement_route_kind=snapshot.settlement_route_kind,
        settlement_route_is_generic_order=snapshot.settlement_route_is_generic_order,
        settlement_route_is_dedicated=snapshot.settlement_route_is_dedicated,
        generic_order_executor_used_for_settlement=False,
        live_order_once_used_for_settlement=False,
        generic_order_endpoint_used_for_settlement=False,
        one_shot_generic_order_path_used_for_settlement=False,
        position_specific_path_used=False,
        position_specific_identifier_safe_handling_ready=(
            snapshot.position_specific_identifier_safe_handling_ready
        ),
        position_specific_preview_allowed=snapshot.position_specific_preview_allowed,
        size_based_preview_allowed=snapshot.size_based_preview_allowed,
        actual_settlement_post_allowed_now=False,
        actual_settlement_post_executed=False,
        settlement_post_count=0,
        transport_call_count=0,
        http_post_executed=False,
        entry_post_executed=False,
        generic_close_post_executed=False,
        retry_allowed=False,
        repost_allowed=False,
        second_settlement_allowed=False,
        ledger_update=False,
        receipt_handoff=False,
        raw_id_value_credential_header_exposure=exposure,
        next_execution_gate_can_detect_actual_executor=ready,
        next_execution_gate_still_requires_fresh_runtime_read=True,
        next_execution_gate_still_requires_operator_readiness=True,
        next_execution_gate_still_requires_settlement_specific_confirmation=True,
        result_safe_category=(
            OFFICIAL_SETTLEMENT_RESULT_ACTUAL_EXECUTOR_TRANSPORT_READY_NO_POST_SANITIZED
        ),
        recommended_next_step=(
            NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE
            if ready
            else NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT
        ),
        blocked_reasons=reasons,
    )


def render_official_settlement_actual_executor_transport_no_post_markdown(
    result: OfficialSettlementActualExecutorTransportResult,
) -> str:
    """Render a sanitized actual executor/transport boundary summary."""
    if not isinstance(result, OfficialSettlementActualExecutorTransportResult):
        raise LiveVerificationValidationError(
            "result must be official settlement actual executor transport result",
        )
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Official Settlement Actual Executor Transport No-POST",
            "",
            (
                "execution_step: "
                f"{EXECUTION_STEP_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_NO_POST}"
            ),
            f"status: {result.status.value}",
            (
                "dedicated_actual_official_settlement_post_executor_available: "
                f"{_bool_text(result.dedicated_actual_official_settlement_post_executor_available)}"
            ),
            (
                "dedicated_actual_official_settlement_transport_boundary_ready: "
                f"{_bool_text(result.dedicated_actual_official_settlement_transport_boundary_ready)}"
            ),
            (
                "dedicated_settlement_actual_executor_compatibility_ready: "
                f"{_bool_text(result.dedicated_settlement_actual_executor_compatibility_ready)}"
            ),
            (
                "official_settlement_no_post_preview_ready: "
                f"{_bool_text(result.official_settlement_no_post_preview_ready)}"
            ),
            (
                "official_settlement_executor_preview_ready: "
                f"{_bool_text(result.official_settlement_executor_preview_ready)}"
            ),
            f"settlement_route_kind: {result.settlement_route_kind}",
            (
                "settlement_route_is_generic_order: "
                f"{_bool_text(result.settlement_route_is_generic_order)}"
            ),
            (
                "settlement_route_is_dedicated: "
                f"{_bool_text(result.settlement_route_is_dedicated)}"
            ),
            (
                "generic_order_executor_used_for_settlement: "
                f"{_bool_text(result.generic_order_executor_used_for_settlement)}"
            ),
            (
                "live_order_once_used_for_settlement: "
                f"{_bool_text(result.live_order_once_used_for_settlement)}"
            ),
            (
                "generic_order_endpoint_used_for_settlement: "
                f"{_bool_text(result.generic_order_endpoint_used_for_settlement)}"
            ),
            (
                "one_shot_generic_order_path_used_for_settlement: "
                f"{_bool_text(result.one_shot_generic_order_path_used_for_settlement)}"
            ),
            f"position_specific_path_used: {_bool_text(result.position_specific_path_used)}",
            (
                "position_specific_identifier_safe_handling_ready: "
                f"{_bool_text(result.position_specific_identifier_safe_handling_ready)}"
            ),
            (
                "position_specific_preview_allowed: "
                f"{_bool_text(result.position_specific_preview_allowed)}"
            ),
            f"size_based_preview_allowed: {_bool_text(result.size_based_preview_allowed)}",
            (
                "actual_settlement_post_allowed_now: "
                f"{_bool_text(result.actual_settlement_post_allowed_now)}"
            ),
            (
                "actual_settlement_post_executed: "
                f"{_bool_text(result.actual_settlement_post_executed)}"
            ),
            f"settlement_post_count: {result.settlement_post_count}",
            f"transport_call_count: {result.transport_call_count}",
            f"http_post_executed: {_bool_text(result.http_post_executed)}",
            f"entry_post_executed: {_bool_text(result.entry_post_executed)}",
            f"generic_close_post_executed: {_bool_text(result.generic_close_post_executed)}",
            f"retry_allowed: {_bool_text(result.retry_allowed)}",
            f"repost_allowed: {_bool_text(result.repost_allowed)}",
            f"second_settlement_allowed: {_bool_text(result.second_settlement_allowed)}",
            f"ledger_update: {_bool_text(result.ledger_update)}",
            f"receipt_handoff: {_bool_text(result.receipt_handoff)}",
            (
                "raw_id_value_credential_header_exposure: "
                f"{_bool_text(result.raw_id_value_credential_header_exposure)}"
            ),
            (
                "next_execution_gate_can_detect_actual_executor: "
                f"{_bool_text(result.next_execution_gate_can_detect_actual_executor)}"
            ),
            (
                "next_execution_gate_still_requires_fresh_runtime_read: "
                f"{_bool_text(result.next_execution_gate_still_requires_fresh_runtime_read)}"
            ),
            (
                "next_execution_gate_still_requires_operator_readiness: "
                f"{_bool_text(result.next_execution_gate_still_requires_operator_readiness)}"
            ),
            (
                "next_execution_gate_still_requires_settlement_specific_confirmation: "
                f"{_bool_text(result.next_execution_gate_still_requires_settlement_specific_confirmation)}"
            ),
            f"result_safe_category: {result.result_safe_category}",
            f"next_cycle_state: {result.level5_connection.next_cycle_state}",
            f"blocked_reasons: {blocked}",
            f"recommended_next_step: {result.recommended_next_step}",
        ),
    ) + "\n"


def _input_from_compatibility(
    result: OfficialSettlementActualExecutorCompatibilityResult,
) -> OfficialSettlementActualExecutorTransportInput:
    return OfficialSettlementActualExecutorTransportInput(
        dedicated_settlement_actual_executor_compatibility_ready=(
            result.dedicated_settlement_actual_executor_compatibility_ready
        ),
        official_settlement_no_post_preview_ready=(
            result.official_settlement_no_post_preview_ready
        ),
        official_settlement_executor_preview_ready=(
            result.official_settlement_executor_preview_ready
        ),
        settlement_route_kind=result.settlement_route_kind,
        settlement_route_is_generic_order=result.settlement_route_is_generic_order,
        settlement_route_is_dedicated=result.settlement_route_is_dedicated,
        generic_order_executor_used_for_settlement=(
            result.generic_order_executor_used_for_settlement
        ),
        live_order_once_used_for_settlement=result.live_order_once_used_for_settlement,
        generic_order_endpoint_used_for_settlement=(
            result.generic_order_endpoint_used_for_settlement
        ),
        position_specific_path_used=result.position_specific_path_used,
        position_specific_identifier_safe_handling_ready=(
            result.position_specific_identifier_safe_handling_ready
        ),
        runtime_position_status=result.runtime_position_status,
        position_count_safe=result.position_count_safe,
        has_exactly_one_position=result.has_exactly_one_position,
        has_multiple_positions=result.has_multiple_positions,
        actual_settlement_post_executed=result.actual_settlement_post_executed,
        settlement_post_count=result.settlement_post_count,
        entry_post_executed=result.entry_post_executed,
        generic_close_post_executed=result.generic_close_post_executed,
        retry_allowed=result.retry_allowed,
        repost_allowed=result.repost_allowed,
        second_settlement_allowed=result.second_settlement_allowed,
        ledger_update=result.ledger_update,
        receipt_handoff=result.receipt_handoff,
    )


def _blocked_reasons(
    snapshot: OfficialSettlementActualExecutorTransportInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.official_settlement_context:
        reasons.append("official_settlement_context_required")
    if snapshot.generic_order_context:
        reasons.append("generic_order_context_not_allowed_for_settlement")
    if not snapshot.dedicated_settlement_actual_executor_compatibility_ready:
        reasons.append("dedicated_settlement_actual_executor_compatibility_not_ready")
    if not snapshot.official_settlement_no_post_preview_ready:
        reasons.append("official_settlement_no_post_preview_not_ready")
    if not snapshot.official_settlement_executor_preview_ready:
        reasons.append("official_settlement_executor_preview_not_ready")
    if snapshot.settlement_route_kind != SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED:
        reasons.append("official_size_based_settlement_route_required")
    if snapshot.settlement_route_is_generic_order:
        reasons.append("settlement_route_must_not_be_generic_order")
    if not snapshot.settlement_route_is_dedicated:
        reasons.append("settlement_route_must_be_dedicated")
    if snapshot.generic_order_executor_used_for_settlement:
        reasons.append("generic_order_executor_used_for_settlement")
    if snapshot.live_order_once_used_for_settlement:
        reasons.append("live_order_once_used_for_settlement")
    if snapshot.generic_order_endpoint_used_for_settlement:
        reasons.append("generic_order_endpoint_used_for_settlement")
    if snapshot.one_shot_generic_order_path_used_for_settlement:
        reasons.append("one_shot_generic_order_path_used_for_settlement")
    if snapshot.position_specific_path_used:
        reasons.append("position_specific_path_used")
    if snapshot.position_specific_identifier_safe_handling_ready:
        reasons.append("position_specific_identifier_handling_not_this_step")
    if snapshot.position_specific_preview_allowed:
        reasons.append("position_specific_preview_must_remain_blocked")
    if not snapshot.size_based_preview_allowed:
        reasons.append("size_based_preview_not_allowed")
    if snapshot.runtime_position_status is not PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        reasons.append("runtime_position_status_not_one_position_open")
    if snapshot.position_count_safe != 1:
        reasons.append("position_count_safe_not_1")
    if not snapshot.has_exactly_one_position:
        reasons.append("has_exactly_one_position_required")
    if snapshot.has_multiple_positions:
        reasons.append("has_multiple_positions_blocked")
    if snapshot.symbol_safe_label != SUPPORTED_SYMBOL:
        reasons.append("symbol_safe_label_not_supported")
    if snapshot.settlement_size_safe_label != str(SUPPORTED_UNITS):
        reasons.append("settlement_size_safe_label_not_supported")
    if snapshot.settlement_order_type_safe_label != SETTLEMENT_ORDER_TYPE_SAFE_LABEL_MARKET:
        reasons.append("settlement_order_type_must_be_market")
    if snapshot.settlement_side_semantics_safe_label != SETTLEMENT_SIDE_SEMANTICS_CONFIRMED:
        reasons.append("settlement_side_semantics_not_confirmed")
    if not snapshot.one_settlement_post_max:
        reasons.append("one_settlement_post_max_required")
    for field_name in (
        "actual_settlement_post_allowed_now",
        "actual_settlement_post_executed",
        "http_post_executed",
        "settlement_endpoint_called",
        "generic_order_endpoint_called",
        "entry_post_executed",
        "generic_close_post_executed",
        "retry_allowed",
        "repost_allowed",
        "second_settlement_allowed",
        "ledger_update",
        "receipt_handoff",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    if snapshot.settlement_post_count != 0:
        reasons.append("settlement_post_count_must_remain_0")
    if snapshot.transport_call_count != 0:
        reasons.append("transport_call_count_must_remain_0")
    if _raw_exposure_attempted(snapshot):
        reasons.append("raw_exposure_blocked")
    if _id_exposure_attempted(snapshot):
        reasons.append("id_exposure_blocked")
    if _credential_exposure_attempted(snapshot):
        reasons.append("credential_signature_headers_exposure_blocked")
    for field_name in (
        "next_execution_gate_can_detect_actual_executor",
        "next_execution_gate_still_requires_fresh_runtime_read",
        "next_execution_gate_still_requires_operator_readiness",
        "next_execution_gate_still_requires_settlement_specific_confirmation",
    ):
        if not getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(dict.fromkeys(reasons))


def _status_from_reasons(
    reasons: tuple[str, ...],
) -> OfficialSettlementActualExecutorTransportNoPostStatus:
    if not reasons:
        return OfficialSettlementActualExecutorTransportNoPostStatus.READY_NO_POST
    if any(reason in _LIFECYCLE_BLOCKED_REASONS for reason in reasons):
        return OfficialSettlementActualExecutorTransportNoPostStatus.BLOCKED_LIFECYCLE
    if any(
        "generic" in reason or "live_order_once" in reason or "one_shot" in reason
        for reason in reasons
    ):
        return (
            OfficialSettlementActualExecutorTransportNoPostStatus
            .BLOCKED_GENERIC_EXECUTOR
        )
    if any(
        reason.startswith("runtime_position")
        or "position_count" in reason
        or reason == "has_exactly_one_position_required"
        or reason == "has_multiple_positions_blocked"
        for reason in reasons
    ):
        return OfficialSettlementActualExecutorTransportNoPostStatus.BLOCKED_POSITION
    if any(reason.startswith("position_specific") for reason in reasons):
        return (
            OfficialSettlementActualExecutorTransportNoPostStatus
            .BLOCKED_POSITION_SPECIFIC_IDENTIFIER
        )
    if any(reason.endswith("_exposure_blocked") for reason in reasons):
        return OfficialSettlementActualExecutorTransportNoPostStatus.BLOCKED_UNSAFE
    if any("compatibility" in reason for reason in reasons):
        return OfficialSettlementActualExecutorTransportNoPostStatus.BLOCKED_COMPATIBILITY
    return OfficialSettlementActualExecutorTransportNoPostStatus.BLOCKED_ROUTE


def _executor_plan(
    snapshot: OfficialSettlementActualExecutorTransportInput,
    ready: bool,
    exposure: bool,
) -> OfficialSettlementActualExecutorPlan:
    return OfficialSettlementActualExecutorPlan(
        plan_ready=ready,
        execution_step=EXECUTION_STEP_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_NO_POST,
        safe_plan_label=SAFE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_PLAN_LABEL,
        dedicated_actual_official_settlement_post_executor_available=ready,
        settlement_route_kind=snapshot.settlement_route_kind,
        settlement_route_is_generic_order=snapshot.settlement_route_is_generic_order,
        settlement_route_is_dedicated=snapshot.settlement_route_is_dedicated,
        symbol_safe_label=snapshot.symbol_safe_label,
        settlement_size_safe_label=snapshot.settlement_size_safe_label,
        settlement_order_type_safe_label=snapshot.settlement_order_type_safe_label,
        settlement_side_semantics_safe_label=snapshot.settlement_side_semantics_safe_label,
        runtime_position_status=snapshot.runtime_position_status,
        position_count_safe=snapshot.position_count_safe,
        one_settlement_post_max=snapshot.one_settlement_post_max,
        actual_settlement_post_allowed_now=False,
        actual_settlement_post_executed=False,
        settlement_post_count=0,
        retry_allowed=False,
        repost_allowed=False,
        second_settlement_allowed=False,
        entry_post_executed=False,
        generic_close_post_executed=False,
        ledger_update=False,
        receipt_handoff=False,
        raw_id_value_credential_header_exposure=exposure,
    )


def _transport_boundary(
    snapshot: OfficialSettlementActualExecutorTransportInput,
    ready: bool,
) -> OfficialSettlementActualTransportBoundary:
    return OfficialSettlementActualTransportBoundary(
        transport_boundary_label=SAFE_OFFICIAL_SETTLEMENT_TRANSPORT_BOUNDARY_LABEL,
        dedicated_actual_official_settlement_transport_boundary_ready=ready,
        dedicated_settlement_transport=True,
        generic_order_transport=False,
        one_shot_generic_order_transport=False,
        can_call_live_order_once=False,
        position_specific_transport=False,
        size_based_transport=snapshot.size_based_preview_allowed,
        transport_invocation_deferred=True,
        transport_call_count=0,
        http_post_executed=False,
        settlement_endpoint_called=False,
        generic_order_endpoint_called=False,
        live_order_once_called=False,
        raw_request_exposed=False,
        raw_response_exposed=False,
        broker_api_response_exposed=False,
        id_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
    )


def _level5_connection(
    ready: bool,
    reasons: tuple[str, ...],
) -> OfficialSettlementActualExecutorTransportLevel5Connection:
    return OfficialSettlementActualExecutorTransportLevel5Connection(
        previous_cycle_state=PREVIOUS_CYCLE_STATE_OFFICIAL_SETTLEMENT_COMPATIBILITY_READY,
        next_cycle_state=(
            NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_READY
            if ready
            else NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED
        ),
        settlement_execution_gate_may_be_planned=ready,
        settlement_post_executed_reached=False,
        post_settlement_position_confirmation_reached=False,
        ledger_updated_reached=False,
        receipt_handoff_reached=False,
        level5_minimal_cycle_completed=False,
        level5_full_auto_cycle_completed=False,
        blocked_reasons=reasons,
    )


def _raw_exposure_attempted(
    snapshot: OfficialSettlementActualExecutorTransportInput,
) -> bool:
    return (
        snapshot.raw_request_exposure_attempted
        or snapshot.raw_response_exposure_attempted
        or snapshot.broker_api_response_exposure_attempted
    )


def _id_exposure_attempted(
    snapshot: OfficialSettlementActualExecutorTransportInput,
) -> bool:
    return (
        snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.position_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
        or snapshot.real_id_exposure_attempted
    )


def _credential_exposure_attempted(
    snapshot: OfficialSettlementActualExecutorTransportInput,
) -> bool:
    return (
        snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
    )


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _validate_bool_fields(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        if type(getattr(instance, name)) is not bool:
            raise LiveVerificationValidationError(f"{name} must be bool")


def _validate_non_negative_int(name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{name} must be non-negative int")


def _validate_blocked_reasons(reasons: tuple[str, ...]) -> None:
    if not isinstance(reasons, tuple):
        raise LiveVerificationValidationError("blocked_reasons must be tuple")
    for reason in reasons:
        _require_non_empty("blocked_reason", reason)


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{name} must be non-empty")


_INPUT_BOOL_FIELDS = (
    "official_settlement_context",
    "generic_order_context",
    "dedicated_settlement_actual_executor_compatibility_ready",
    "official_settlement_no_post_preview_ready",
    "official_settlement_executor_preview_ready",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "generic_order_executor_used_for_settlement",
    "live_order_once_used_for_settlement",
    "generic_order_endpoint_used_for_settlement",
    "one_shot_generic_order_path_used_for_settlement",
    "position_specific_path_used",
    "position_specific_identifier_safe_handling_ready",
    "position_specific_preview_allowed",
    "size_based_preview_allowed",
    "has_exactly_one_position",
    "has_multiple_positions",
    "one_settlement_post_max",
    "actual_settlement_post_allowed_now",
    "actual_settlement_post_executed",
    "http_post_executed",
    "settlement_endpoint_called",
    "generic_order_endpoint_called",
    "entry_post_executed",
    "generic_close_post_executed",
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "ledger_update",
    "receipt_handoff",
    "raw_request_exposure_attempted",
    "raw_response_exposure_attempted",
    "broker_api_response_exposure_attempted",
    "account_id_exposure_attempted",
    "order_id_exposure_attempted",
    "transaction_id_exposure_attempted",
    "position_id_exposure_attempted",
    "trade_id_exposure_attempted",
    "real_id_exposure_attempted",
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
    "next_execution_gate_can_detect_actual_executor",
    "next_execution_gate_still_requires_fresh_runtime_read",
    "next_execution_gate_still_requires_operator_readiness",
    "next_execution_gate_still_requires_settlement_specific_confirmation",
)

_PLAN_BOOL_FIELDS = (
    "plan_ready",
    "dedicated_actual_official_settlement_post_executor_available",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "one_settlement_post_max",
    "actual_settlement_post_allowed_now",
    "actual_settlement_post_executed",
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "entry_post_executed",
    "generic_close_post_executed",
    "ledger_update",
    "receipt_handoff",
    "raw_id_value_credential_header_exposure",
)

_TRANSPORT_BOOL_FIELDS = (
    "dedicated_actual_official_settlement_transport_boundary_ready",
    "dedicated_settlement_transport",
    "generic_order_transport",
    "one_shot_generic_order_transport",
    "can_call_live_order_once",
    "position_specific_transport",
    "size_based_transport",
    "transport_invocation_deferred",
    "http_post_executed",
    "settlement_endpoint_called",
    "generic_order_endpoint_called",
    "live_order_once_called",
    "raw_request_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "id_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
)

_LEVEL5_BOOL_FIELDS = (
    "settlement_execution_gate_may_be_planned",
    "settlement_post_executed_reached",
    "post_settlement_position_confirmation_reached",
    "ledger_updated_reached",
    "receipt_handoff_reached",
    "level5_minimal_cycle_completed",
    "level5_full_auto_cycle_completed",
)

_RESULT_BOOL_FIELDS = (
    "dedicated_actual_official_settlement_post_executor_available",
    "dedicated_actual_official_settlement_transport_boundary_ready",
    "dedicated_settlement_actual_executor_compatibility_ready",
    "official_settlement_no_post_preview_ready",
    "official_settlement_executor_preview_ready",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "generic_order_executor_used_for_settlement",
    "live_order_once_used_for_settlement",
    "generic_order_endpoint_used_for_settlement",
    "one_shot_generic_order_path_used_for_settlement",
    "position_specific_path_used",
    "position_specific_identifier_safe_handling_ready",
    "position_specific_preview_allowed",
    "size_based_preview_allowed",
    "actual_settlement_post_allowed_now",
    "actual_settlement_post_executed",
    "http_post_executed",
    "entry_post_executed",
    "generic_close_post_executed",
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "ledger_update",
    "receipt_handoff",
    "raw_id_value_credential_header_exposure",
    "next_execution_gate_can_detect_actual_executor",
    "next_execution_gate_still_requires_fresh_runtime_read",
    "next_execution_gate_still_requires_operator_readiness",
    "next_execution_gate_still_requires_settlement_specific_confirmation",
)

_LIFECYCLE_BLOCKED_REASONS = frozenset(
    {
        "actual_settlement_post_allowed_now",
        "actual_settlement_post_executed",
        "settlement_post_count_must_remain_0",
        "transport_call_count_must_remain_0",
        "http_post_executed",
        "settlement_endpoint_called",
        "generic_order_endpoint_called",
        "entry_post_executed",
        "generic_close_post_executed",
        "retry_allowed",
        "repost_allowed",
        "second_settlement_allowed",
        "ledger_update",
        "receipt_handoff",
    },
)
