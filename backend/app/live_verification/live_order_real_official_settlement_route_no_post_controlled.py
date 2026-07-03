"""Step 6G official GMO FX settlement route no-POST preview.

This module converts the official settlement route review into a sanitized
preview. It does not create a raw request body, expose an endpoint value, import
broker or Private API clients, call HTTP, read env, update ledger state, hand off
receipts, or call live_order_once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_gmo_official_settlement_route_review_controlled import (
    CURRENT_POSITION_STATE_MANUAL_FLAT_RECONCILED,
    OFFICIAL_SETTLEMENT_ROUTE_CONFIRMED_NO_POST,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

EXECUTION_STEP_OFFICIAL_SETTLEMENT_ROUTE_NO_POST = (
    "OFFICIAL_SETTLEMENT_ROUTE_NO_POST_IMPLEMENTATION_C"
)
OFFICIAL_SETTLEMENT_ROUTE_CONFIRMATION_BASIS = (
    OFFICIAL_SETTLEMENT_ROUTE_CONFIRMED_NO_POST
)
SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED = "OFFICIAL_SIZE_BASED_SETTLEMENT"
SETTLEMENT_ROUTE_KIND_POSITION_SPECIFIC_BLOCKED = (
    "OFFICIAL_POSITION_SPECIFIC_SETTLEMENT_BLOCKED_SAFE_ID_NOT_READY"
)
SETTLEMENT_ROUTE_KIND_BLOCKED = "BLOCKED"
SETTLEMENT_ORDER_TYPE_SAFE_LABEL_MARKET = "MARKET"
SETTLEMENT_SIDE_SEMANTICS_CONFIRMED = (
    "OFFICIAL_SETTLEMENT_SIDE_SEMANTICS_CONFIRMED"
)
SETTLEMENT_SIDE_SEMANTICS_BLOCKED = "BLOCKED_SEMANTICS_UNCLEAR"
POSITION_STATUS_REQUIRED_ONE_POSITION_OPEN = "ONE_POSITION_OPEN"
POSITION_SPECIFIC_BLOCKED_REASON_SAFE_ID_NOT_READY = (
    "SAFE_IDENTIFIER_HANDLING_NOT_READY"
)
PREVIOUS_CYCLE_STATE_OFFICIAL_SETTLEMENT_REVIEWED = (
    "OFFICIAL_SETTLEMENT_ROUTE_REVIEWED_NO_POST"
)
NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_PREVIEW_READY = (
    "OFFICIAL_SETTLEMENT_PREVIEW_READY_NO_POST"
)
NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_PREVIEW_BLOCKED = (
    "OFFICIAL_SETTLEMENT_PREVIEW_BLOCKED"
)
NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-EXECUTION-GATE-C"
)
NEXT_STEP_POSITION_SPECIFIC_SAFE_HANDLE_DESIGN = (
    "Step 6G-PC-OX-R-POSITION-SPECIFIC-SETTLEMENT-SAFE-HANDLE-DESIGN-C"
)
NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_PREVIEW = (
    "fix_official_settlement_no_post_preview_blocker"
)


class OfficialSettlementRouteNoPostCase(str, Enum):
    CASE_1 = "OFFICIAL_SETTLEMENT_NO_POST_PREVIEW_READY"
    CASE_2 = "SETTLEMENT_PREVIEW_PARTIAL_BUT_BLOCKED"
    CASE_3 = "SETTLEMENT_REQUIRES_UNSAFE_RAW_ID_VALUE"
    CASE_4 = "INCONCLUSIVE"


class OfficialSettlementRouteNoPostStatus(str, Enum):
    READY_NO_POST = "OFFICIAL_SETTLEMENT_PREVIEW_READY_NO_POST"
    BLOCKED_SEMANTICS = "OFFICIAL_SETTLEMENT_PREVIEW_BLOCKED_SEMANTICS"
    BLOCKED_ROUTE = "OFFICIAL_SETTLEMENT_PREVIEW_BLOCKED_ROUTE"
    BLOCKED_UNSAFE_IDENTIFIER = (
        "OFFICIAL_SETTLEMENT_PREVIEW_BLOCKED_UNSAFE_IDENTIFIER"
    )
    BLOCKED_UNSAFE_EXPOSURE = "OFFICIAL_SETTLEMENT_PREVIEW_BLOCKED_UNSAFE_EXPOSURE"
    INCONCLUSIVE_FAIL_CLOSED = "OFFICIAL_SETTLEMENT_PREVIEW_INCONCLUSIVE_FAIL_CLOSED"


@dataclass(frozen=True)
class OfficialSettlementRouteNoPostInput:
    official_settlement_route_confirmed: bool = True
    official_settlement_route_confirmation_basis: str = (
        OFFICIAL_SETTLEMENT_ROUTE_CONFIRMATION_BASIS
    )
    generic_opposite_order_as_close_forbidden: bool = True
    generic_close_primitive_revoked: bool = True
    current_position_state: str = CURRENT_POSITION_STATE_MANUAL_FLAT_RECONCILED
    manual_flatten_reconciled: bool = True
    size_based_path_exists: bool = True
    size_based_path_requires_raw_id: bool | None = False
    position_specific_path_exists: bool = True
    position_specific_identifier_required: bool | None = True
    position_specific_identifier_safe_handling_ready: bool = False
    settlement_side_semantics_confirmed: bool = True
    symbol_safe_label: str = SUPPORTED_SYMBOL
    settlement_size_safe_label: str = str(SUPPORTED_UNITS)
    settlement_order_type_safe_label: str = SETTLEMENT_ORDER_TYPE_SAFE_LABEL_MARKET
    position_status_required: str = POSITION_STATUS_REQUIRED_ONE_POSITION_OPEN
    position_count_safe_required: int = 1
    one_settlement_post_max: bool = True
    settlement_retry_allowed: bool = False
    settlement_repost_allowed: bool = False
    settlement_second_post_allowed: bool = False
    entry_post_this_step: bool = False
    actual_entry_post_attempted_this_step: bool = False
    actual_close_post_attempted_this_step: bool = False
    actual_settlement_post_attempted_this_step: bool = False
    retry_attempted_this_step: bool = False
    repost_attempted_this_step: bool = False
    second_close_post_attempted_this_step: bool = False
    ledger_update_this_step: bool = False
    receipt_handoff_this_step: bool = False
    raw_position_exposure_attempted: bool = False
    raw_request_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    raw_endpoint_exposure_attempted: bool = False
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
    actual_market_price_exposure_attempted: bool = False
    actual_pnl_exposure_attempted: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "official_settlement_route_confirmation_basis",
            "current_position_state",
            "symbol_safe_label",
            "settlement_size_safe_label",
            "settlement_order_type_safe_label",
            "position_status_required",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int(
            "position_count_safe_required",
            self.position_count_safe_required,
        )
        _validate_tri_state(
            "size_based_path_requires_raw_id",
            self.size_based_path_requires_raw_id,
        )
        _validate_tri_state(
            "position_specific_identifier_required",
            self.position_specific_identifier_required,
        )
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementNoPostLevel5Connection:
    previous_cycle_state: str
    next_cycle_state: str
    settlement_execution_gate_may_be_planned: bool
    settlement_post_executed_reached: bool
    close_post_executed_reached: bool
    post_close_position_confirmation_reached: bool
    ledger_updated_reached: bool
    receipt_handoff_reached: bool
    level5_minimal_cycle_completed: bool
    level5_full_auto_cycle_completed: bool

    def __post_init__(self) -> None:
        _require_non_empty("previous_cycle_state", self.previous_cycle_state)
        _require_non_empty("next_cycle_state", self.next_cycle_state)
        _validate_bool_fields(self, _LEVEL5_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementRouteNoPostPreview:
    preview_ready: bool
    execution_step: str
    official_settlement_route_confirmed: bool
    official_settlement_route_confirmation_basis: str
    generic_opposite_order_as_close_forbidden: bool
    generic_close_primitive_revoked: bool
    settlement_route_kind: str
    settlement_route_is_generic_order: bool
    settlement_route_is_dedicated: bool
    settlement_route_invocation_deferred: bool
    actual_settlement_post_allowed_now: bool
    actual_close_post_allowed_now: bool
    symbol_safe_label: str
    settlement_size_safe_label: str
    settlement_order_type_safe_label: str
    settlement_side_semantics_safe_label: str
    position_status_required: str
    position_count_safe_required: int
    one_settlement_post_max: bool
    settlement_retry_allowed: bool
    settlement_repost_allowed: bool
    settlement_second_post_allowed: bool
    entry_post_this_step: bool
    ledger_update_this_step: bool
    receipt_handoff_this_step: bool
    raw_request_exposed: bool
    raw_response_exposed: bool
    raw_endpoint_exposed: bool
    broker_api_response_exposed: bool
    raw_position_exposed: bool
    position_id_exposed: bool
    account_id_exposed: bool
    order_id_exposed: bool
    transaction_id_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool

    def __post_init__(self) -> None:
        for field_name in (
            "execution_step",
            "official_settlement_route_confirmation_basis",
            "settlement_route_kind",
            "symbol_safe_label",
            "settlement_size_safe_label",
            "settlement_order_type_safe_label",
            "settlement_side_semantics_safe_label",
            "position_status_required",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int(
            "position_count_safe_required",
            self.position_count_safe_required,
        )
        _validate_bool_fields(self, _PREVIEW_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementRouteNoPostResult:
    case: OfficialSettlementRouteNoPostCase
    status: OfficialSettlementRouteNoPostStatus
    official_settlement_no_post_preview_ready: bool
    preview: OfficialSettlementRouteNoPostPreview
    level5_connection: OfficialSettlementNoPostLevel5Connection
    position_specific_path_exists: bool
    position_specific_identifier_required: bool | None
    position_specific_identifier_safe_handling_ready: bool
    position_specific_preview_allowed: bool
    position_specific_execution_blocked_reason: str
    size_based_path_exists: bool
    size_based_path_requires_raw_id: bool | None
    size_based_preview_allowed: bool
    size_based_preview_raw_request_exposed: bool
    size_based_preview_raw_endpoint_exposed: bool
    current_position_state: str
    manual_flatten_reconciled: bool
    future_actual_close_post_requires_dedicated_settlement_gate: bool
    future_actual_close_post_requires_no_raw_id_value_exposure: bool
    fresh_cycle_allowed: bool
    recommended_next_step: str
    actual_entry_post: bool
    actual_close_post: bool
    actual_settlement_post: bool
    retry_repost: bool
    second_close_post: bool
    ledger_update: bool
    receipt_handoff: bool
    real_id_exposed: bool
    trade_id_exposed: bool
    actual_market_price_exposed: bool
    actual_pnl_exposed: bool
    blocked_reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.case, OfficialSettlementRouteNoPostCase):
            raise LiveVerificationValidationError("case must be controlled enum")
        if not isinstance(self.status, OfficialSettlementRouteNoPostStatus):
            raise LiveVerificationValidationError("status must be controlled enum")
        if not isinstance(self.preview, OfficialSettlementRouteNoPostPreview):
            raise LiveVerificationValidationError("preview must be controlled result")
        if not isinstance(self.level5_connection, OfficialSettlementNoPostLevel5Connection):
            raise LiveVerificationValidationError(
                "level5_connection must be controlled result",
            )
        _validate_tri_state(
            "position_specific_identifier_required",
            self.position_specific_identifier_required,
        )
        _validate_tri_state(
            "size_based_path_requires_raw_id",
            self.size_based_path_requires_raw_id,
        )
        for field_name in (
            "position_specific_execution_blocked_reason",
            "current_position_state",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_official_settlement_route_no_post_controlled(
    preview_input: OfficialSettlementRouteNoPostInput | None = None,
) -> OfficialSettlementRouteNoPostResult:
    snapshot = preview_input or OfficialSettlementRouteNoPostInput()
    current_step_blockers = _current_step_blocked_reasons(snapshot)
    route_blockers = _route_blocked_reasons(snapshot)
    side_semantics_blocked = not snapshot.settlement_side_semantics_confirmed
    size_based_raw_id_required = snapshot.size_based_path_requires_raw_id is True
    size_based_preview_allowed = (
        snapshot.size_based_path_exists
        and snapshot.size_based_path_requires_raw_id is False
        and not side_semantics_blocked
        and not current_step_blockers
        and not route_blockers
    )
    position_specific_preview_allowed = (
        snapshot.position_specific_path_exists
        and snapshot.position_specific_identifier_required is not True
        and snapshot.position_specific_identifier_safe_handling_ready
        and not current_step_blockers
        and not route_blockers
    )
    position_specific_blocked_reason = _position_specific_blocked_reason(snapshot)

    if current_step_blockers:
        case = OfficialSettlementRouteNoPostCase.CASE_4
        status = OfficialSettlementRouteNoPostStatus.BLOCKED_UNSAFE_EXPOSURE
        route_kind = SETTLEMENT_ROUTE_KIND_BLOCKED
        preview_ready = False
        blocked_reasons = current_step_blockers
        next_step = "stop_current_step_no_post"
    elif route_blockers:
        case = OfficialSettlementRouteNoPostCase.CASE_2
        status = OfficialSettlementRouteNoPostStatus.BLOCKED_ROUTE
        route_kind = SETTLEMENT_ROUTE_KIND_BLOCKED
        preview_ready = False
        blocked_reasons = route_blockers
        next_step = NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_PREVIEW
    elif side_semantics_blocked:
        case = OfficialSettlementRouteNoPostCase.CASE_2
        status = OfficialSettlementRouteNoPostStatus.BLOCKED_SEMANTICS
        route_kind = SETTLEMENT_ROUTE_KIND_BLOCKED
        preview_ready = False
        blocked_reasons = ("settlement_side_semantics_unclear",)
        next_step = NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_PREVIEW
    elif size_based_raw_id_required:
        case = OfficialSettlementRouteNoPostCase.CASE_3
        status = OfficialSettlementRouteNoPostStatus.BLOCKED_UNSAFE_IDENTIFIER
        route_kind = SETTLEMENT_ROUTE_KIND_BLOCKED
        preview_ready = False
        blocked_reasons = ("size_based_route_requires_raw_identifier",)
        next_step = NEXT_STEP_POSITION_SPECIFIC_SAFE_HANDLE_DESIGN
    elif size_based_preview_allowed:
        case = OfficialSettlementRouteNoPostCase.CASE_1
        status = OfficialSettlementRouteNoPostStatus.READY_NO_POST
        route_kind = SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED
        preview_ready = True
        blocked_reasons = ()
        next_step = NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE
    elif snapshot.position_specific_path_exists:
        case = OfficialSettlementRouteNoPostCase.CASE_3
        status = OfficialSettlementRouteNoPostStatus.BLOCKED_UNSAFE_IDENTIFIER
        route_kind = SETTLEMENT_ROUTE_KIND_POSITION_SPECIFIC_BLOCKED
        preview_ready = False
        blocked_reasons = ("position_specific_safe_identifier_handling_not_ready",)
        next_step = NEXT_STEP_POSITION_SPECIFIC_SAFE_HANDLE_DESIGN
    else:
        case = OfficialSettlementRouteNoPostCase.CASE_4
        status = OfficialSettlementRouteNoPostStatus.INCONCLUSIVE_FAIL_CLOSED
        route_kind = SETTLEMENT_ROUTE_KIND_BLOCKED
        preview_ready = False
        blocked_reasons = ("no_safe_settlement_preview_path",)
        next_step = NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_PREVIEW

    side_semantics_label = (
        SETTLEMENT_SIDE_SEMANTICS_CONFIRMED
        if snapshot.settlement_side_semantics_confirmed
        else SETTLEMENT_SIDE_SEMANTICS_BLOCKED
    )
    next_cycle_state = (
        NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_PREVIEW_READY
        if preview_ready
        else NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_PREVIEW_BLOCKED
    )
    preview = OfficialSettlementRouteNoPostPreview(
        preview_ready=preview_ready,
        execution_step=EXECUTION_STEP_OFFICIAL_SETTLEMENT_ROUTE_NO_POST,
        official_settlement_route_confirmed=snapshot.official_settlement_route_confirmed,
        official_settlement_route_confirmation_basis=(
            snapshot.official_settlement_route_confirmation_basis
        ),
        generic_opposite_order_as_close_forbidden=(
            snapshot.generic_opposite_order_as_close_forbidden
        ),
        generic_close_primitive_revoked=snapshot.generic_close_primitive_revoked,
        settlement_route_kind=route_kind,
        settlement_route_is_generic_order=False,
        settlement_route_is_dedicated=preview_ready,
        settlement_route_invocation_deferred=True,
        actual_settlement_post_allowed_now=False,
        actual_close_post_allowed_now=False,
        symbol_safe_label=snapshot.symbol_safe_label,
        settlement_size_safe_label=snapshot.settlement_size_safe_label,
        settlement_order_type_safe_label=snapshot.settlement_order_type_safe_label,
        settlement_side_semantics_safe_label=side_semantics_label,
        position_status_required=snapshot.position_status_required,
        position_count_safe_required=snapshot.position_count_safe_required,
        one_settlement_post_max=snapshot.one_settlement_post_max,
        settlement_retry_allowed=False,
        settlement_repost_allowed=False,
        settlement_second_post_allowed=False,
        entry_post_this_step=False,
        ledger_update_this_step=False,
        receipt_handoff_this_step=False,
        raw_request_exposed=False,
        raw_response_exposed=False,
        raw_endpoint_exposed=False,
        broker_api_response_exposed=False,
        raw_position_exposed=False,
        position_id_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
    )
    level5_connection = OfficialSettlementNoPostLevel5Connection(
        previous_cycle_state=PREVIOUS_CYCLE_STATE_OFFICIAL_SETTLEMENT_REVIEWED,
        next_cycle_state=next_cycle_state,
        settlement_execution_gate_may_be_planned=preview_ready,
        settlement_post_executed_reached=False,
        close_post_executed_reached=False,
        post_close_position_confirmation_reached=False,
        ledger_updated_reached=False,
        receipt_handoff_reached=False,
        level5_minimal_cycle_completed=False,
        level5_full_auto_cycle_completed=False,
    )
    return OfficialSettlementRouteNoPostResult(
        case=case,
        status=status,
        official_settlement_no_post_preview_ready=preview_ready,
        preview=preview,
        level5_connection=level5_connection,
        position_specific_path_exists=snapshot.position_specific_path_exists,
        position_specific_identifier_required=(
            snapshot.position_specific_identifier_required
        ),
        position_specific_identifier_safe_handling_ready=(
            snapshot.position_specific_identifier_safe_handling_ready
        ),
        position_specific_preview_allowed=position_specific_preview_allowed,
        position_specific_execution_blocked_reason=position_specific_blocked_reason,
        size_based_path_exists=snapshot.size_based_path_exists,
        size_based_path_requires_raw_id=snapshot.size_based_path_requires_raw_id,
        size_based_preview_allowed=size_based_preview_allowed,
        size_based_preview_raw_request_exposed=False,
        size_based_preview_raw_endpoint_exposed=False,
        current_position_state=snapshot.current_position_state,
        manual_flatten_reconciled=snapshot.manual_flatten_reconciled,
        future_actual_close_post_requires_dedicated_settlement_gate=True,
        future_actual_close_post_requires_no_raw_id_value_exposure=True,
        fresh_cycle_allowed=False,
        recommended_next_step=next_step,
        actual_entry_post=False,
        actual_close_post=False,
        actual_settlement_post=False,
        retry_repost=False,
        second_close_post=False,
        ledger_update=False,
        receipt_handoff=False,
        real_id_exposed=False,
        trade_id_exposed=False,
        actual_market_price_exposed=False,
        actual_pnl_exposed=False,
        blocked_reasons=blocked_reasons,
    )


def render_official_settlement_route_no_post_markdown(
    result: OfficialSettlementRouteNoPostResult,
) -> str:
    if not isinstance(result, OfficialSettlementRouteNoPostResult):
        raise LiveVerificationValidationError(
            "result must be OfficialSettlementRouteNoPostResult",
        )
    preview = result.preview
    lines = [
        "# Official Settlement Route No-POST Preview",
        "",
        f"case: {result.case.value}",
        f"status: {result.status.value}",
        (
            "official_settlement_no_post_preview_ready: "
            f"{_bool_text(result.official_settlement_no_post_preview_ready)}"
        ),
        (
            "official_settlement_route_confirmed: "
            f"{_bool_text(preview.official_settlement_route_confirmed)}"
        ),
        (
            "official_settlement_route_confirmation_basis: "
            f"{preview.official_settlement_route_confirmation_basis}"
        ),
        (
            "generic_opposite_order_as_close_forbidden: "
            f"{_bool_text(preview.generic_opposite_order_as_close_forbidden)}"
        ),
        (
            "generic_close_primitive_revoked: "
            f"{_bool_text(preview.generic_close_primitive_revoked)}"
        ),
        f"settlement_route_kind: {preview.settlement_route_kind}",
        (
            "settlement_route_is_generic_order: "
            f"{_bool_text(preview.settlement_route_is_generic_order)}"
        ),
        (
            "settlement_route_is_dedicated: "
            f"{_bool_text(preview.settlement_route_is_dedicated)}"
        ),
        (
            "settlement_route_invocation_deferred: "
            f"{_bool_text(preview.settlement_route_invocation_deferred)}"
        ),
        (
            "actual_settlement_post_allowed_now: "
            f"{_bool_text(preview.actual_settlement_post_allowed_now)}"
        ),
        (
            "actual_close_post_allowed_now: "
            f"{_bool_text(preview.actual_close_post_allowed_now)}"
        ),
        f"symbol_safe_label: {preview.symbol_safe_label}",
        f"settlement_size_safe_label: {preview.settlement_size_safe_label}",
        (
            "settlement_order_type_safe_label: "
            f"{preview.settlement_order_type_safe_label}"
        ),
        (
            "settlement_side_semantics_safe_label: "
            f"{preview.settlement_side_semantics_safe_label}"
        ),
        (
            "position_specific_path_exists: "
            f"{_bool_text(result.position_specific_path_exists)}"
        ),
        (
            "position_specific_identifier_required: "
            f"{_tri_state_text(result.position_specific_identifier_required)}"
        ),
        (
            "position_specific_identifier_safe_handling_ready: "
            f"{_bool_text(result.position_specific_identifier_safe_handling_ready)}"
        ),
        (
            "position_specific_preview_allowed: "
            f"{_bool_text(result.position_specific_preview_allowed)}"
        ),
        (
            "position_specific_execution_blocked_reason: "
            f"{result.position_specific_execution_blocked_reason}"
        ),
        f"size_based_path_exists: {_bool_text(result.size_based_path_exists)}",
        (
            "size_based_path_requires_raw_id: "
            f"{_tri_state_text(result.size_based_path_requires_raw_id)}"
        ),
        f"size_based_preview_allowed: {_bool_text(result.size_based_preview_allowed)}",
        (
            "size_based_preview_raw_request_exposed: "
            f"{_bool_text(result.size_based_preview_raw_request_exposed)}"
        ),
        (
            "size_based_preview_raw_endpoint_exposed: "
            f"{_bool_text(result.size_based_preview_raw_endpoint_exposed)}"
        ),
        f"one_settlement_post_max: {_bool_text(preview.one_settlement_post_max)}",
        (
            "settlement_retry_allowed: "
            f"{_bool_text(preview.settlement_retry_allowed)}"
        ),
        (
            "settlement_repost_allowed: "
            f"{_bool_text(preview.settlement_repost_allowed)}"
        ),
        (
            "settlement_second_post_allowed: "
            f"{_bool_text(preview.settlement_second_post_allowed)}"
        ),
        f"next_cycle_state: {result.level5_connection.next_cycle_state}",
        (
            "settlement_execution_gate_may_be_planned: "
            f"{_bool_text(result.level5_connection.settlement_execution_gate_may_be_planned)}"
        ),
        f"raw_request_exposed: {_bool_text(preview.raw_request_exposed)}",
        f"raw_response_exposed: {_bool_text(preview.raw_response_exposed)}",
        f"raw_endpoint_exposed: {_bool_text(preview.raw_endpoint_exposed)}",
        (
            "broker_api_response_exposed: "
            f"{_bool_text(preview.broker_api_response_exposed)}"
        ),
        f"position_id_exposed: {_bool_text(preview.position_id_exposed)}",
        f"credential_value_exposed: {_bool_text(preview.credential_value_exposed)}",
        f"signature_value_exposed: {_bool_text(preview.signature_value_exposed)}",
        f"headers_value_exposed: {_bool_text(preview.headers_value_exposed)}",
        f"recommended_next_step: {result.recommended_next_step}",
        f"blocked_reasons: {', '.join(result.blocked_reasons) or 'none'}",
    ]
    return "\n".join(lines)


def _route_blocked_reasons(
    snapshot: OfficialSettlementRouteNoPostInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.official_settlement_route_confirmed:
        reasons.append("official_settlement_route_not_confirmed")
    if (
        snapshot.official_settlement_route_confirmation_basis
        != OFFICIAL_SETTLEMENT_ROUTE_CONFIRMATION_BASIS
    ):
        reasons.append("official_settlement_route_confirmation_basis_mismatch")
    if not snapshot.generic_opposite_order_as_close_forbidden:
        reasons.append("generic_opposite_order_as_close_not_forbidden")
    if not snapshot.generic_close_primitive_revoked:
        reasons.append("generic_close_primitive_not_revoked")
    if not snapshot.one_settlement_post_max:
        reasons.append("one_settlement_post_max_not_enforced")
    if snapshot.settlement_retry_allowed:
        reasons.append("settlement_retry_allowed")
    if snapshot.settlement_repost_allowed:
        reasons.append("settlement_repost_allowed")
    if snapshot.settlement_second_post_allowed:
        reasons.append("settlement_second_post_allowed")
    if snapshot.entry_post_this_step:
        reasons.append("entry_post_this_step")
    if snapshot.ledger_update_this_step:
        reasons.append("ledger_update_this_step")
    if snapshot.receipt_handoff_this_step:
        reasons.append("receipt_handoff_this_step")
    if snapshot.position_count_safe_required != 1:
        reasons.append("position_count_safe_required_not_one")
    if snapshot.position_status_required != POSITION_STATUS_REQUIRED_ONE_POSITION_OPEN:
        reasons.append("position_status_required_not_one_position_open")
    if snapshot.settlement_size_safe_label != str(SUPPORTED_UNITS):
        reasons.append("settlement_size_safe_label_not_supported")
    if snapshot.symbol_safe_label != SUPPORTED_SYMBOL:
        reasons.append("symbol_safe_label_not_supported")
    if snapshot.settlement_order_type_safe_label != SETTLEMENT_ORDER_TYPE_SAFE_LABEL_MARKET:
        reasons.append("settlement_order_type_not_market")
    return tuple(reasons)


def _current_step_blocked_reasons(
    snapshot: OfficialSettlementRouteNoPostInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name, reason in (
        ("actual_entry_post_attempted_this_step", "actual_entry_post_attempted"),
        ("actual_close_post_attempted_this_step", "actual_close_post_attempted"),
        ("actual_settlement_post_attempted_this_step", "actual_settlement_post_attempted"),
        ("retry_attempted_this_step", "retry_attempted"),
        ("repost_attempted_this_step", "repost_attempted"),
        ("second_close_post_attempted_this_step", "second_close_post_attempted"),
    ):
        if getattr(snapshot, field_name):
            reasons.append(reason)
    if any(
        (
            snapshot.raw_position_exposure_attempted,
            snapshot.raw_request_exposure_attempted,
            snapshot.raw_response_exposure_attempted,
            snapshot.raw_endpoint_exposure_attempted,
            snapshot.broker_api_response_exposure_attempted,
            snapshot.position_id_exposure_attempted,
            snapshot.account_id_exposure_attempted,
            snapshot.order_id_exposure_attempted,
            snapshot.transaction_id_exposure_attempted,
            snapshot.trade_id_exposure_attempted,
            snapshot.real_id_exposure_attempted,
            snapshot.client_order_id_actual_value_exposure_attempted,
            snapshot.credential_value_exposure_attempted,
            snapshot.signature_value_exposure_attempted,
            snapshot.headers_value_exposure_attempted,
            snapshot.actual_market_price_exposure_attempted,
            snapshot.actual_pnl_exposure_attempted,
        )
    ):
        reasons.append("raw_id_value_exposure_attempted")
    return tuple(reasons)


def _position_specific_blocked_reason(
    snapshot: OfficialSettlementRouteNoPostInput,
) -> str:
    if not snapshot.position_specific_path_exists:
        return "POSITION_SPECIFIC_PATH_NOT_USED"
    if (
        snapshot.position_specific_identifier_required is True
        and not snapshot.position_specific_identifier_safe_handling_ready
    ):
        return POSITION_SPECIFIC_BLOCKED_REASON_SAFE_ID_NOT_READY
    if snapshot.position_specific_identifier_required is None:
        return "POSITION_SPECIFIC_IDENTIFIER_REQUIREMENT_UNKNOWN"
    if not snapshot.position_specific_identifier_safe_handling_ready:
        return POSITION_SPECIFIC_BLOCKED_REASON_SAFE_ID_NOT_READY
    return "NONE"


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _tri_state_text(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return _bool_text(value)


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_tri_state(field_name: str, value: bool | None) -> None:
    if value is not None and type(value) is not bool:
        raise LiveVerificationValidationError(f"{field_name} must be bool or None")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_blocked_reasons(blocked_reasons: tuple[str, ...]) -> None:
    if not isinstance(blocked_reasons, tuple) or not all(
        isinstance(reason, str) and reason for reason in blocked_reasons
    ):
        raise LiveVerificationValidationError("blocked_reasons must be tuple[str, ...]")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")


_INPUT_BOOL_FIELDS = (
    "official_settlement_route_confirmed",
    "generic_opposite_order_as_close_forbidden",
    "generic_close_primitive_revoked",
    "manual_flatten_reconciled",
    "size_based_path_exists",
    "position_specific_path_exists",
    "position_specific_identifier_safe_handling_ready",
    "settlement_side_semantics_confirmed",
    "one_settlement_post_max",
    "settlement_retry_allowed",
    "settlement_repost_allowed",
    "settlement_second_post_allowed",
    "entry_post_this_step",
    "actual_entry_post_attempted_this_step",
    "actual_close_post_attempted_this_step",
    "actual_settlement_post_attempted_this_step",
    "retry_attempted_this_step",
    "repost_attempted_this_step",
    "second_close_post_attempted_this_step",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "raw_position_exposure_attempted",
    "raw_request_exposure_attempted",
    "raw_response_exposure_attempted",
    "raw_endpoint_exposure_attempted",
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
    "actual_market_price_exposure_attempted",
    "actual_pnl_exposure_attempted",
)

_LEVEL5_BOOL_FIELDS = (
    "settlement_execution_gate_may_be_planned",
    "settlement_post_executed_reached",
    "close_post_executed_reached",
    "post_close_position_confirmation_reached",
    "ledger_updated_reached",
    "receipt_handoff_reached",
    "level5_minimal_cycle_completed",
    "level5_full_auto_cycle_completed",
)

_PREVIEW_BOOL_FIELDS = (
    "preview_ready",
    "official_settlement_route_confirmed",
    "generic_opposite_order_as_close_forbidden",
    "generic_close_primitive_revoked",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "settlement_route_invocation_deferred",
    "actual_settlement_post_allowed_now",
    "actual_close_post_allowed_now",
    "one_settlement_post_max",
    "settlement_retry_allowed",
    "settlement_repost_allowed",
    "settlement_second_post_allowed",
    "entry_post_this_step",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "raw_request_exposed",
    "raw_response_exposed",
    "raw_endpoint_exposed",
    "broker_api_response_exposed",
    "raw_position_exposed",
    "position_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
)

_RESULT_BOOL_FIELDS = (
    "official_settlement_no_post_preview_ready",
    "position_specific_path_exists",
    "position_specific_identifier_safe_handling_ready",
    "position_specific_preview_allowed",
    "size_based_path_exists",
    "size_based_preview_allowed",
    "size_based_preview_raw_request_exposed",
    "size_based_preview_raw_endpoint_exposed",
    "manual_flatten_reconciled",
    "future_actual_close_post_requires_dedicated_settlement_gate",
    "future_actual_close_post_requires_no_raw_id_value_exposure",
    "fresh_cycle_allowed",
    "actual_entry_post",
    "actual_close_post",
    "actual_settlement_post",
    "retry_repost",
    "second_close_post",
    "ledger_update",
    "receipt_handoff",
    "real_id_exposed",
    "trade_id_exposed",
    "actual_market_price_exposed",
    "actual_pnl_exposed",
)
