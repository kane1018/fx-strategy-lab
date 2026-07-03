"""Official GMO FX settlement actual-executor compatibility, no POST.

This module adapts the official size-based settlement no-POST preview into a
dedicated settlement executor compatibility boundary. It does not import generic
order executors, call live_order_once, use Private API clients, call HTTP, read
env, update ledgers, hand off receipts, or expose raw/ID/value material.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_official_settlement_route_no_post_controlled import (
    SETTLEMENT_ORDER_TYPE_SAFE_LABEL_MARKET,
    SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED,
    SETTLEMENT_SIDE_SEMANTICS_CONFIRMED,
    OfficialSettlementRouteNoPostResult,
    build_official_settlement_route_no_post_controlled,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

EXECUTION_STEP_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY = (
    "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_NO_POST_C"
)
SAFE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_LABEL = (
    "STEP6G_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_CONTROLLED_NO_POST"
)
SAFE_OFFICIAL_SETTLEMENT_EXECUTOR_PREVIEW_LABEL = (
    "STEP6G_SANITIZED_OFFICIAL_SETTLEMENT_EXECUTOR_PREVIEW_NO_POST"
)
NO_POST_SETTLEMENT_TRANSPORT_LABEL = (
    "DEDICATED_OFFICIAL_SETTLEMENT_NO_POST_TRANSPORT_COMPATIBILITY"
)
OFFICIAL_SETTLEMENT_RESULT_COMPATIBLE_NO_POST_SANITIZED = (
    "RESULT_COMPATIBLE_NO_POST_SANITIZED"
)
PREVIOUS_CYCLE_STATE_OFFICIAL_SETTLEMENT_PREVIEW_READY = (
    "OFFICIAL_SETTLEMENT_PREVIEW_READY_NO_POST"
)
NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_EXECUTOR_READY = (
    "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_READY_NO_POST"
)
NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_EXECUTOR_BLOCKED = (
    "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED"
)
NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-EXECUTION-GATE-C"
)
NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_EXECUTOR_COMPATIBILITY = (
    "fix_official_settlement_actual_executor_compatibility_no_post"
)


class OfficialSettlementActualExecutorCompatibilityStatus(str, Enum):
    READY_NO_POST = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_READY_NO_POST"
    )
    BLOCKED_PREVIEW = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_PREVIEW"
    )
    BLOCKED_POSITION = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_POSITION"
    )
    BLOCKED_GENERIC_EXECUTOR = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_GENERIC_EXECUTOR"
    )
    BLOCKED_POSITION_SPECIFIC_IDENTIFIER = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_POSITION_SPECIFIC_IDENTIFIER"
    )
    BLOCKED_CONTRACT = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_CONTRACT"
    )
    BLOCKED_UNSAFE = (
        "OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_UNSAFE"
    )


@dataclass(frozen=True)
class NoPostOfficialSettlementTransportCompatibility:
    transport_label: str = NO_POST_SETTLEMENT_TRANSPORT_LABEL
    no_post_transport_ready: bool = True
    dedicated_settlement_transport: bool = True
    generic_order_transport: bool = False
    fake_transport_call_count: int = 0
    transport_call_count: int = 0
    http_post_executed: bool = False
    settlement_endpoint_called: bool = False
    generic_order_endpoint_called: bool = False
    live_order_once_called: bool = False
    raw_request_exposed: bool = False
    raw_response_exposed: bool = False
    broker_api_response_exposed: bool = False
    id_exposed: bool = False
    credential_value_exposed: bool = False
    signature_value_exposed: bool = False
    headers_value_exposed: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("transport_label", self.transport_label)
        _validate_non_negative_int("fake_transport_call_count", self.fake_transport_call_count)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_bool_fields(self, _TRANSPORT_BOOL_FIELDS)


@dataclass(frozen=True)
class SanitizedOfficialSettlementExecutorCompatibilityPreview:
    preview_ready: bool
    execution_step: str
    safe_preview_label: str
    official_settlement_context: bool
    generic_order_context: bool
    runtime_position_status: PositionReadOnlyControlledStatus
    position_count_safe: int
    settlement_route_kind: str
    settlement_route_is_generic_order: bool
    settlement_route_is_dedicated: bool
    settlement_route_invocation_deferred: bool
    symbol_safe_label: str
    settlement_size_safe_label: str
    settlement_order_type_safe_label: str
    settlement_side_semantics_safe_label: str
    one_settlement_post_max: bool
    settlement_retry_allowed: bool
    settlement_repost_allowed: bool
    settlement_second_post_allowed: bool
    actual_settlement_post_allowed_now: bool
    actual_settlement_post_executed: bool
    settlement_post_count: int
    entry_post_executed: bool
    generic_close_post_executed: bool
    ledger_update: bool
    receipt_handoff: bool
    raw_exposure: bool
    id_exposure: bool
    credential_value_exposure: bool
    signature_value_exposure: bool
    headers_value_exposure: bool
    actual_settlement_post_requires_separate_execution_gate: bool

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        for field_name in (
            "execution_step",
            "safe_preview_label",
            "settlement_route_kind",
            "symbol_safe_label",
            "settlement_size_safe_label",
            "settlement_order_type_safe_label",
            "settlement_side_semantics_safe_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_bool_fields(self, _PREVIEW_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementActualExecutorCompatibilityInput:
    official_settlement_context: bool = True
    generic_order_context: bool = False
    official_settlement_no_post_preview_ready: bool = True
    official_settlement_route_confirmed: bool = True
    settlement_route_kind: str = SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED
    settlement_route_is_generic_order: bool = False
    settlement_route_is_dedicated: bool = True
    settlement_route_invocation_deferred: bool = True
    size_based_path_exists: bool = True
    size_based_path_requires_raw_id: bool | None = False
    size_based_preview_allowed: bool = True
    position_specific_path_exists: bool = True
    position_specific_path_used: bool = False
    position_specific_identifier_required: bool | None = True
    position_specific_identifier_safe_handling_ready: bool = False
    position_specific_preview_allowed: bool = False
    generic_opposite_order_as_close_forbidden: bool = True
    generic_close_primitive_revoked: bool = True
    generic_order_executor_used_for_settlement: bool = False
    live_order_once_used_for_settlement: bool = False
    generic_order_endpoint_used_for_settlement: bool = False
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
    settlement_retry_allowed: bool = False
    settlement_repost_allowed: bool = False
    settlement_second_post_allowed: bool = False
    entry_post_allowed: bool = False
    generic_close_allowed: bool = False
    actual_settlement_post_allowed_now: bool = False
    actual_settlement_post_executed: bool = False
    settlement_post_count: int = 0
    no_post_transport_ready: bool = True
    no_post_transport_call_count: int = 0
    ledger_update_allowed: bool = False
    receipt_handoff_allowed: bool = False
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
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False

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
        _validate_tri_state(
            "size_based_path_requires_raw_id",
            self.size_based_path_requires_raw_id,
        )
        _validate_tri_state(
            "position_specific_identifier_required",
            self.position_specific_identifier_required,
        )
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_non_negative_int(
            "no_post_transport_call_count",
            self.no_post_transport_call_count,
        )
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementActualExecutorCompatibilityLevel5Connection:
    previous_cycle_state: str
    next_cycle_state: str
    settlement_execution_gate_may_be_planned: bool
    settlement_post_executed_reached: bool
    close_post_executed_reached: bool
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
class OfficialSettlementActualExecutorCompatibilityResult:
    status: OfficialSettlementActualExecutorCompatibilityStatus
    dedicated_settlement_actual_executor_compatibility_ready: bool
    official_settlement_executor_preview_ready: bool
    safe_compatibility_label: str
    executable_preview: SanitizedOfficialSettlementExecutorCompatibilityPreview
    no_post_transport: NoPostOfficialSettlementTransportCompatibility
    level5_connection: OfficialSettlementActualExecutorCompatibilityLevel5Connection
    official_settlement_no_post_preview_ready: bool
    settlement_route_kind: str
    settlement_route_is_generic_order: bool
    settlement_route_is_dedicated: bool
    generic_order_executor_used_for_settlement: bool
    live_order_once_used_for_settlement: bool
    generic_order_endpoint_used_for_settlement: bool
    position_specific_path_used: bool
    position_specific_identifier_safe_handling_ready: bool
    multiple_positions_blocked: bool
    one_position_required: bool
    runtime_position_status: PositionReadOnlyControlledStatus
    position_count_safe: int
    has_exactly_one_position: bool
    has_multiple_positions: bool
    actual_settlement_post_executed: bool
    settlement_post_count: int
    entry_post_executed: bool
    generic_close_post_executed: bool
    retry_allowed: bool
    repost_allowed: bool
    second_settlement_allowed: bool
    entry_post_allowed: bool
    generic_close_allowed: bool
    ledger_update: bool
    receipt_handoff: bool
    raw_id_value_credential_header_exposure: bool
    result_safe_category: str
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            OfficialSettlementActualExecutorCompatibilityStatus,
        ):
            raise LiveVerificationValidationError("status must be compatibility enum")
        if not isinstance(self.runtime_position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        for field_name in (
            "safe_compatibility_label",
            "settlement_route_kind",
            "result_safe_category",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_official_settlement_actual_executor_compatibility_controlled(
    input_snapshot: OfficialSettlementActualExecutorCompatibilityInput | None = None,
    *,
    settlement_preview_result: OfficialSettlementRouteNoPostResult | None = None,
) -> OfficialSettlementActualExecutorCompatibilityResult:
    """Build dedicated settlement executor compatibility without POST."""
    snapshot = input_snapshot or _input_from_settlement_preview(
        settlement_preview_result or build_official_settlement_route_no_post_controlled(),
    )
    reasons = _blocked_reasons(snapshot)
    ready = not reasons
    status = _status_from_reasons(reasons)
    executable_preview = _sanitized_preview(snapshot, ready)
    no_post_transport = _no_post_transport(snapshot)
    level5_connection = _level5_connection(ready, reasons)
    exposure = _raw_exposure_attempted(snapshot) or _id_exposure_attempted(
        snapshot,
    ) or _credential_exposure_attempted(snapshot)

    return OfficialSettlementActualExecutorCompatibilityResult(
        status=status,
        dedicated_settlement_actual_executor_compatibility_ready=ready,
        official_settlement_executor_preview_ready=ready,
        safe_compatibility_label=(
            SAFE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY_LABEL
        ),
        executable_preview=executable_preview,
        no_post_transport=no_post_transport,
        level5_connection=level5_connection,
        official_settlement_no_post_preview_ready=(
            snapshot.official_settlement_no_post_preview_ready
        ),
        settlement_route_kind=snapshot.settlement_route_kind,
        settlement_route_is_generic_order=snapshot.settlement_route_is_generic_order,
        settlement_route_is_dedicated=snapshot.settlement_route_is_dedicated,
        generic_order_executor_used_for_settlement=False,
        live_order_once_used_for_settlement=False,
        generic_order_endpoint_used_for_settlement=False,
        position_specific_path_used=False,
        position_specific_identifier_safe_handling_ready=(
            snapshot.position_specific_identifier_safe_handling_ready
        ),
        multiple_positions_blocked=True,
        one_position_required=True,
        runtime_position_status=snapshot.runtime_position_status,
        position_count_safe=snapshot.position_count_safe,
        has_exactly_one_position=snapshot.has_exactly_one_position,
        has_multiple_positions=snapshot.has_multiple_positions,
        actual_settlement_post_executed=False,
        settlement_post_count=0,
        entry_post_executed=False,
        generic_close_post_executed=False,
        retry_allowed=False,
        repost_allowed=False,
        second_settlement_allowed=False,
        entry_post_allowed=False,
        generic_close_allowed=False,
        ledger_update=False,
        receipt_handoff=False,
        raw_id_value_credential_header_exposure=exposure,
        result_safe_category=OFFICIAL_SETTLEMENT_RESULT_COMPATIBLE_NO_POST_SANITIZED,
        recommended_next_step=(
            NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE
            if ready
            else NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_EXECUTOR_COMPATIBILITY
        ),
        blocked_reasons=reasons,
    )


def render_official_settlement_actual_executor_compatibility_markdown(
    result: OfficialSettlementActualExecutorCompatibilityResult,
) -> str:
    """Render a sanitized compatibility summary without raw request details."""
    if not isinstance(result, OfficialSettlementActualExecutorCompatibilityResult):
        raise LiveVerificationValidationError(
            "result must be official settlement compatibility result",
        )
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Official Settlement Actual Executor Compatibility No-POST",
            "",
            f"execution_step: {EXECUTION_STEP_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY}",
            f"status: {result.status.value}",
            (
                "dedicated_settlement_actual_executor_compatibility_ready: "
                f"{_bool_text(result.dedicated_settlement_actual_executor_compatibility_ready)}"
            ),
            (
                "official_settlement_no_post_preview_ready: "
                f"{_bool_text(result.official_settlement_no_post_preview_ready)}"
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
            f"runtime_position_status: {result.runtime_position_status.value}",
            f"position_count_safe: {result.position_count_safe}",
            f"one_position_required: {_bool_text(result.one_position_required)}",
            (
                "position_specific_identifier_safe_handling_ready: "
                f"{_bool_text(result.position_specific_identifier_safe_handling_ready)}"
            ),
            f"position_specific_path_used: {_bool_text(result.position_specific_path_used)}",
            (
                "actual_settlement_post_executed: "
                f"{_bool_text(result.actual_settlement_post_executed)}"
            ),
            f"settlement_post_count: {result.settlement_post_count}",
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
            f"no_post_transport_call_count: {result.no_post_transport.transport_call_count}",
            f"result_safe_category: {result.result_safe_category}",
            f"next_cycle_state: {result.level5_connection.next_cycle_state}",
            f"blocked_reasons: {blocked}",
            f"recommended_next_step: {result.recommended_next_step}",
        ),
    ) + "\n"


def _input_from_settlement_preview(
    result: OfficialSettlementRouteNoPostResult,
) -> OfficialSettlementActualExecutorCompatibilityInput:
    preview = result.preview
    return OfficialSettlementActualExecutorCompatibilityInput(
        official_settlement_no_post_preview_ready=(
            result.official_settlement_no_post_preview_ready
        ),
        official_settlement_route_confirmed=preview.official_settlement_route_confirmed,
        settlement_route_kind=preview.settlement_route_kind,
        settlement_route_is_generic_order=preview.settlement_route_is_generic_order,
        settlement_route_is_dedicated=preview.settlement_route_is_dedicated,
        settlement_route_invocation_deferred=preview.settlement_route_invocation_deferred,
        size_based_path_exists=result.size_based_path_exists,
        size_based_path_requires_raw_id=result.size_based_path_requires_raw_id,
        size_based_preview_allowed=result.size_based_preview_allowed,
        position_specific_path_exists=result.position_specific_path_exists,
        position_specific_identifier_required=(
            result.position_specific_identifier_required
        ),
        position_specific_identifier_safe_handling_ready=(
            result.position_specific_identifier_safe_handling_ready
        ),
        position_specific_preview_allowed=result.position_specific_preview_allowed,
        generic_opposite_order_as_close_forbidden=(
            preview.generic_opposite_order_as_close_forbidden
        ),
        generic_close_primitive_revoked=preview.generic_close_primitive_revoked,
        symbol_safe_label=preview.symbol_safe_label,
        settlement_size_safe_label=preview.settlement_size_safe_label,
        settlement_order_type_safe_label=preview.settlement_order_type_safe_label,
        settlement_side_semantics_safe_label=(
            preview.settlement_side_semantics_safe_label
        ),
        one_settlement_post_max=preview.one_settlement_post_max,
        settlement_retry_allowed=preview.settlement_retry_allowed,
        settlement_repost_allowed=preview.settlement_repost_allowed,
        settlement_second_post_allowed=preview.settlement_second_post_allowed,
        actual_settlement_post_allowed_now=preview.actual_settlement_post_allowed_now,
    )


def _blocked_reasons(
    snapshot: OfficialSettlementActualExecutorCompatibilityInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.official_settlement_context:
        reasons.append("official_settlement_context_required")
    if snapshot.generic_order_context:
        reasons.append("generic_order_context_not_allowed_for_settlement")
    if not snapshot.official_settlement_no_post_preview_ready:
        reasons.append("official_settlement_no_post_preview_not_ready")
    if not snapshot.official_settlement_route_confirmed:
        reasons.append("official_settlement_route_not_confirmed")
    if snapshot.settlement_route_kind != SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED:
        reasons.append("official_size_based_settlement_route_required")
    if snapshot.settlement_route_is_generic_order:
        reasons.append("settlement_route_must_not_be_generic_order")
    if not snapshot.settlement_route_is_dedicated:
        reasons.append("settlement_route_must_be_dedicated")
    if not snapshot.settlement_route_invocation_deferred:
        reasons.append("settlement_route_invocation_must_be_deferred")
    if not snapshot.size_based_path_exists:
        reasons.append("size_based_path_missing")
    if snapshot.size_based_path_requires_raw_id is not False:
        reasons.append("size_based_path_must_not_require_raw_id")
    if not snapshot.size_based_preview_allowed:
        reasons.append("size_based_preview_not_allowed")
    if snapshot.position_specific_path_used:
        reasons.append("position_specific_path_used")
    if snapshot.position_specific_identifier_safe_handling_ready:
        reasons.append("position_specific_identifier_handling_not_this_step")
    if snapshot.position_specific_preview_allowed:
        reasons.append("position_specific_preview_must_remain_blocked")
    if not snapshot.generic_opposite_order_as_close_forbidden:
        reasons.append("generic_opposite_order_as_close_must_be_forbidden")
    if not snapshot.generic_close_primitive_revoked:
        reasons.append("generic_close_primitive_must_be_revoked")
    if snapshot.generic_order_executor_used_for_settlement:
        reasons.append("generic_order_executor_used_for_settlement")
    if snapshot.live_order_once_used_for_settlement:
        reasons.append("live_order_once_used_for_settlement")
    if snapshot.generic_order_endpoint_used_for_settlement:
        reasons.append("generic_order_endpoint_used_for_settlement")
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
        "settlement_retry_allowed",
        "settlement_repost_allowed",
        "settlement_second_post_allowed",
        "entry_post_allowed",
        "generic_close_allowed",
        "actual_settlement_post_allowed_now",
        "actual_settlement_post_executed",
        "ledger_update_allowed",
        "receipt_handoff_allowed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    if snapshot.settlement_post_count != 0:
        reasons.append("settlement_post_count_must_remain_0")
    if not snapshot.no_post_transport_ready:
        reasons.append("no_post_transport_not_ready")
    if snapshot.no_post_transport_call_count != 0:
        reasons.append("no_post_transport_call_count_must_remain_0")
    if _raw_exposure_attempted(snapshot):
        reasons.append("raw_exposure_blocked")
    if _id_exposure_attempted(snapshot):
        reasons.append("id_exposure_blocked")
    if _credential_exposure_attempted(snapshot):
        reasons.append("credential_signature_headers_exposure_blocked")
    return tuple(dict.fromkeys(reasons))


def _status_from_reasons(
    reasons: tuple[str, ...],
) -> OfficialSettlementActualExecutorCompatibilityStatus:
    if not reasons:
        return OfficialSettlementActualExecutorCompatibilityStatus.READY_NO_POST
    if any("generic" in reason or "live_order_once" in reason for reason in reasons):
        return (
            OfficialSettlementActualExecutorCompatibilityStatus
            .BLOCKED_GENERIC_EXECUTOR
        )
    if any(
        reason.startswith("runtime_position")
        or "position_count" in reason
        or reason == "has_exactly_one_position_required"
        or reason == "has_multiple_positions_blocked"
        for reason in reasons
    ):
        return OfficialSettlementActualExecutorCompatibilityStatus.BLOCKED_POSITION
    if any(reason.startswith("position_specific") for reason in reasons):
        return (
            OfficialSettlementActualExecutorCompatibilityStatus
            .BLOCKED_POSITION_SPECIFIC_IDENTIFIER
        )
    if any(reason.endswith("_exposure_blocked") for reason in reasons):
        return OfficialSettlementActualExecutorCompatibilityStatus.BLOCKED_UNSAFE
    if any(
        "preview" in reason
        or "route" in reason
        or reason.startswith("size_based_path")
        for reason in reasons
    ):
        return OfficialSettlementActualExecutorCompatibilityStatus.BLOCKED_PREVIEW
    return OfficialSettlementActualExecutorCompatibilityStatus.BLOCKED_CONTRACT


def _sanitized_preview(
    snapshot: OfficialSettlementActualExecutorCompatibilityInput,
    ready: bool,
) -> SanitizedOfficialSettlementExecutorCompatibilityPreview:
    return SanitizedOfficialSettlementExecutorCompatibilityPreview(
        preview_ready=ready,
        execution_step=EXECUTION_STEP_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY,
        safe_preview_label=SAFE_OFFICIAL_SETTLEMENT_EXECUTOR_PREVIEW_LABEL,
        official_settlement_context=snapshot.official_settlement_context,
        generic_order_context=snapshot.generic_order_context,
        runtime_position_status=snapshot.runtime_position_status,
        position_count_safe=snapshot.position_count_safe,
        settlement_route_kind=snapshot.settlement_route_kind,
        settlement_route_is_generic_order=snapshot.settlement_route_is_generic_order,
        settlement_route_is_dedicated=snapshot.settlement_route_is_dedicated,
        settlement_route_invocation_deferred=snapshot.settlement_route_invocation_deferred,
        symbol_safe_label=snapshot.symbol_safe_label,
        settlement_size_safe_label=snapshot.settlement_size_safe_label,
        settlement_order_type_safe_label=snapshot.settlement_order_type_safe_label,
        settlement_side_semantics_safe_label=(
            snapshot.settlement_side_semantics_safe_label
        ),
        one_settlement_post_max=snapshot.one_settlement_post_max,
        settlement_retry_allowed=False,
        settlement_repost_allowed=False,
        settlement_second_post_allowed=False,
        actual_settlement_post_allowed_now=False,
        actual_settlement_post_executed=False,
        settlement_post_count=0,
        entry_post_executed=False,
        generic_close_post_executed=False,
        ledger_update=False,
        receipt_handoff=False,
        raw_exposure=False,
        id_exposure=False,
        credential_value_exposure=False,
        signature_value_exposure=False,
        headers_value_exposure=False,
        actual_settlement_post_requires_separate_execution_gate=True,
    )


def _no_post_transport(
    snapshot: OfficialSettlementActualExecutorCompatibilityInput,
) -> NoPostOfficialSettlementTransportCompatibility:
    return NoPostOfficialSettlementTransportCompatibility(
        no_post_transport_ready=snapshot.no_post_transport_ready,
        fake_transport_call_count=0,
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
) -> OfficialSettlementActualExecutorCompatibilityLevel5Connection:
    return OfficialSettlementActualExecutorCompatibilityLevel5Connection(
        previous_cycle_state=PREVIOUS_CYCLE_STATE_OFFICIAL_SETTLEMENT_PREVIEW_READY,
        next_cycle_state=(
            NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_EXECUTOR_READY
            if ready
            else NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_EXECUTOR_BLOCKED
        ),
        settlement_execution_gate_may_be_planned=ready,
        settlement_post_executed_reached=False,
        close_post_executed_reached=False,
        ledger_updated_reached=False,
        receipt_handoff_reached=False,
        level5_minimal_cycle_completed=False,
        level5_full_auto_cycle_completed=False,
        blocked_reasons=reasons,
    )


def _raw_exposure_attempted(
    snapshot: OfficialSettlementActualExecutorCompatibilityInput,
) -> bool:
    return (
        snapshot.raw_position_exposure_attempted
        or snapshot.raw_request_exposure_attempted
        or snapshot.raw_response_exposure_attempted
        or snapshot.broker_api_response_exposure_attempted
    )


def _id_exposure_attempted(
    snapshot: OfficialSettlementActualExecutorCompatibilityInput,
) -> bool:
    return (
        snapshot.position_id_exposure_attempted
        or snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
        or snapshot.real_id_exposure_attempted
    )


def _credential_exposure_attempted(
    snapshot: OfficialSettlementActualExecutorCompatibilityInput,
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


def _validate_tri_state(field_name: str, value: bool | None) -> None:
    if value is not None and type(value) is not bool:
        raise LiveVerificationValidationError(f"{field_name} must be bool or None")


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


_TRANSPORT_BOOL_FIELDS = (
    "no_post_transport_ready",
    "dedicated_settlement_transport",
    "generic_order_transport",
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

_PREVIEW_BOOL_FIELDS = (
    "preview_ready",
    "official_settlement_context",
    "generic_order_context",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "settlement_route_invocation_deferred",
    "one_settlement_post_max",
    "settlement_retry_allowed",
    "settlement_repost_allowed",
    "settlement_second_post_allowed",
    "actual_settlement_post_allowed_now",
    "actual_settlement_post_executed",
    "entry_post_executed",
    "generic_close_post_executed",
    "ledger_update",
    "receipt_handoff",
    "raw_exposure",
    "id_exposure",
    "credential_value_exposure",
    "signature_value_exposure",
    "headers_value_exposure",
    "actual_settlement_post_requires_separate_execution_gate",
)

_INPUT_BOOL_FIELDS = (
    "official_settlement_context",
    "generic_order_context",
    "official_settlement_no_post_preview_ready",
    "official_settlement_route_confirmed",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "settlement_route_invocation_deferred",
    "size_based_path_exists",
    "size_based_preview_allowed",
    "position_specific_path_exists",
    "position_specific_path_used",
    "position_specific_identifier_safe_handling_ready",
    "position_specific_preview_allowed",
    "generic_opposite_order_as_close_forbidden",
    "generic_close_primitive_revoked",
    "generic_order_executor_used_for_settlement",
    "live_order_once_used_for_settlement",
    "generic_order_endpoint_used_for_settlement",
    "has_exactly_one_position",
    "has_multiple_positions",
    "one_settlement_post_max",
    "settlement_retry_allowed",
    "settlement_repost_allowed",
    "settlement_second_post_allowed",
    "entry_post_allowed",
    "generic_close_allowed",
    "actual_settlement_post_allowed_now",
    "actual_settlement_post_executed",
    "no_post_transport_ready",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
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
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
)

_LEVEL5_BOOL_FIELDS = (
    "settlement_execution_gate_may_be_planned",
    "settlement_post_executed_reached",
    "close_post_executed_reached",
    "ledger_updated_reached",
    "receipt_handoff_reached",
    "level5_minimal_cycle_completed",
    "level5_full_auto_cycle_completed",
)

_RESULT_BOOL_FIELDS = (
    "dedicated_settlement_actual_executor_compatibility_ready",
    "official_settlement_executor_preview_ready",
    "official_settlement_no_post_preview_ready",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "generic_order_executor_used_for_settlement",
    "live_order_once_used_for_settlement",
    "generic_order_endpoint_used_for_settlement",
    "position_specific_path_used",
    "position_specific_identifier_safe_handling_ready",
    "multiple_positions_blocked",
    "one_position_required",
    "has_exactly_one_position",
    "has_multiple_positions",
    "actual_settlement_post_executed",
    "entry_post_executed",
    "generic_close_post_executed",
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "entry_post_allowed",
    "generic_close_allowed",
    "ledger_update",
    "receipt_handoff",
    "raw_id_value_credential_header_exposure",
)
