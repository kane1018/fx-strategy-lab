"""Entry request plan current-turn binding (no-POST, fail-closed).

This module classifies whether the actual entry gate may bind the dedicated
entry request plan to the CURRENT turn, and builds the safe-label-only
previews the gate reports. It closes the ``entry_request_plan_status:
NOT_BOUND`` blocker without ever performing a POST or exposing a raw value.

Hard rules enforced by construction:

- The operator signal (ENTRY_BUY / ENTRY_SELL) maps MECHANICALLY to the order
  kind safe label (ENTRY_OPEN_BUY / ENTRY_OPEN_SELL). The AI never decides,
  infers, or defaults a trade direction; HOLD and unknown labels are never
  executable.
- symbol / size / executionType must come from the existing approved builder
  configuration (``app.private_api.order_builders``); if any of them would
  require AI inference, binding is refused.
- Only the dedicated ENTRY request plan is bindable. Settlement, close, and
  generic plans are rejected structurally and by validation.
- No raw request body, size, price, P/L, ID, credential, signature, or
  header ever crosses this boundary. Safe previews carry labels and safe
  booleans only.
- Every result is default-deny, never truthy, and never a POST permission:
  ``actual_entry_POST_allowed`` is hardcoded false.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.private_api.order_builders import (
    GMO_FX_ENTRY_ORDER_METHOD,
    GMO_FX_ENTRY_ORDER_PATH,
    REQUEST_KIND_ENTRY,
    GmoFxPrivateRequestPlan,
    build_gmo_fx_entry_request_plan,
)
from app.services.gmo_live_approved_entry_order_profile import (
    ApprovedEntryOrderProfile,
)


class GmoEntryRequestPlanBindingError(RuntimeError):
    """Raised for fail-closed violations. Never carries a body/ID/value."""


class GmoEntryRequestPlanStatus(str, Enum):
    ENTRY_REQUEST_PLAN_BOUND_SAFE = "ENTRY_REQUEST_PLAN_BOUND_SAFE"
    ENTRY_REQUEST_PLAN_PRESENT_BUT_NEEDS_FRESH_ACTUAL_GATE = (
        "ENTRY_REQUEST_PLAN_PRESENT_BUT_NEEDS_FRESH_ACTUAL_GATE"
    )
    ENTRY_REQUEST_PLAN_PRESENT_BUT_NEEDS_INTERNAL_VALUE_SOURCE = (
        "ENTRY_REQUEST_PLAN_PRESENT_BUT_NEEDS_INTERNAL_VALUE_SOURCE"
    )
    ENTRY_REQUEST_PLAN_NOT_BOUND_NO_POST = "ENTRY_REQUEST_PLAN_NOT_BOUND_NO_POST"
    ENTRY_REQUEST_PLAN_UNSAFE_TO_USE = "ENTRY_REQUEST_PLAN_UNSAFE_TO_USE"
    ENTRY_REQUEST_PLAN_REVIEW_INCOMPLETE = "ENTRY_REQUEST_PLAN_REVIEW_INCOMPLETE"


class GmoEntryOrderKindSafeLabel(str, Enum):
    ENTRY_OPEN_BUY = "ENTRY_OPEN_BUY"
    ENTRY_OPEN_SELL = "ENTRY_OPEN_SELL"


# HOLD is intentionally absent: it is never executable, and the AI never
# supplies a direction that is missing from the operator signal.
OPERATOR_SIGNAL_TO_ORDER_KIND_SAFE_LABEL: dict[str, GmoEntryOrderKindSafeLabel] = {
    "ENTRY_BUY": GmoEntryOrderKindSafeLabel.ENTRY_OPEN_BUY,
    "ENTRY_SELL": GmoEntryOrderKindSafeLabel.ENTRY_OPEN_SELL,
}

_ORDER_KIND_TO_BUILDER_SIDE: dict[GmoEntryOrderKindSafeLabel, str] = {
    GmoEntryOrderKindSafeLabel.ENTRY_OPEN_BUY: "BUY",
    GmoEntryOrderKindSafeLabel.ENTRY_OPEN_SELL: "SELL",
}


@dataclass(frozen=True)
class EntryRequestPlanBindingInput:
    """Default-deny binding input for the CURRENT actual gate turn only.

    Every field must be supplied fresh by the actual gate; nothing here is
    read from history or banked across steps.
    """

    operator_signal_type_safe_label: str = ""
    current_turn_binding_confirmed: bool = False
    approved_symbol_source_present: bool = False
    approved_size_source_present: bool = False
    approved_execution_type_source_present: bool = False
    ai_inference_required: bool = False
    # The safe-label profile alone is not enough for a real send: a reviewed
    # internal raw value source must additionally exist. Default-deny.
    internal_raw_value_source_present: bool = False

    # violations (any true makes the plan unsafe to use)
    raw_body_exposure_requested: bool = False
    ids_exposure_requested: bool = False
    price_size_pnl_exposure_requested: bool = False
    credential_exposure_requested: bool = False
    settlement_plan_requested: bool = False
    close_plan_requested: bool = False
    generic_plan_requested: bool = False


@dataclass(frozen=True)
class EntryRequestPlanBindingResult:
    """Safe-label-only binding result. Never truthy, never a POST permission."""

    status: GmoEntryRequestPlanStatus
    order_kind_safe_label: str
    blocked_reasons: tuple[str, ...]
    request_plan_is_entry_only: bool
    request_plan_current_turn_binding: bool
    request_plan_raw_body_exposed: bool = False
    request_plan_ids_exposed: bool = False
    request_plan_price_size_pnl_exposed: bool = False
    request_plan_credentials_exposed: bool = False
    actual_entry_POST_allowed: bool = False

    def __bool__(self) -> bool:
        return False


_UNSAFE_REASONS: tuple[tuple[str, str], ...] = (
    ("raw_body_exposure_requested", "RAW_BODY_EXPOSURE_REQUESTED_BLOCKED"),
    ("ids_exposure_requested", "IDS_EXPOSURE_REQUESTED_BLOCKED"),
    (
        "price_size_pnl_exposure_requested",
        "PRICE_SIZE_PNL_EXPOSURE_REQUESTED_BLOCKED",
    ),
    ("credential_exposure_requested", "CREDENTIAL_EXPOSURE_REQUESTED_BLOCKED"),
    ("settlement_plan_requested", "SETTLEMENT_PLAN_REQUESTED_BLOCKED"),
    ("close_plan_requested", "CLOSE_PLAN_REQUESTED_BLOCKED"),
    ("generic_plan_requested", "GENERIC_PLAN_REQUESTED_BLOCKED"),
)

_NOT_BOUND_REASONS: tuple[tuple[str, str], ...] = (
    ("approved_symbol_source_present", "APPROVED_SYMBOL_SOURCE_MISSING"),
    ("approved_size_source_present", "APPROVED_SIZE_SOURCE_MISSING"),
    (
        "approved_execution_type_source_present",
        "APPROVED_EXECUTION_TYPE_SOURCE_MISSING",
    ),
)


def binding_input_from_approved_profile(
    *,
    profile: ApprovedEntryOrderProfile,
    operator_signal_type_safe_label: str,
    current_turn_binding_confirmed: bool,
) -> EntryRequestPlanBindingInput:
    """Derive a binding input from the repo-approved safe-label profile.

    The operator signal and the current-turn confirmation must be supplied
    fresh by the actual gate for THIS turn; they are never read from history
    by this function. Everything else is derived mechanically from the
    profile: when the safe labels are ready, no AI inference is required;
    when they are not, the input stays default-deny.
    """

    labels_ready = profile.safe_labels_ready
    return EntryRequestPlanBindingInput(
        operator_signal_type_safe_label=operator_signal_type_safe_label,
        current_turn_binding_confirmed=current_turn_binding_confirmed,
        approved_symbol_source_present=labels_ready,
        approved_size_source_present=labels_ready,
        approved_execution_type_source_present=labels_ready,
        ai_inference_required=not labels_ready,
        internal_raw_value_source_present=(
            profile.internal_raw_value_source_present
        ),
    )


def bind_entry_request_plan_current_turn(
    binding_input: EntryRequestPlanBindingInput,
) -> EntryRequestPlanBindingResult:
    """Classify current-turn binding readiness; never grant a POST permission."""

    unsafe_reasons = [
        reason
        for field_name, reason in _UNSAFE_REASONS
        if getattr(binding_input, field_name)
    ]
    if unsafe_reasons:
        return EntryRequestPlanBindingResult(
            status=GmoEntryRequestPlanStatus.ENTRY_REQUEST_PLAN_UNSAFE_TO_USE,
            order_kind_safe_label="",
            blocked_reasons=tuple(unsafe_reasons),
            request_plan_is_entry_only=False,
            request_plan_current_turn_binding=False,
        )

    not_bound_reasons: list[str] = []
    order_kind = OPERATOR_SIGNAL_TO_ORDER_KIND_SAFE_LABEL.get(
        binding_input.operator_signal_type_safe_label
    )
    if order_kind is None:
        not_bound_reasons.append("OPERATOR_SIGNAL_NOT_EXECUTABLE_FOR_ENTRY_PLAN")
    if binding_input.ai_inference_required:
        not_bound_reasons.append("AI_INFERENCE_REQUIRED_BLOCKED")
    for field_name, reason in _NOT_BOUND_REASONS:
        if not getattr(binding_input, field_name):
            not_bound_reasons.append(reason)
    if not_bound_reasons:
        return EntryRequestPlanBindingResult(
            status=GmoEntryRequestPlanStatus.ENTRY_REQUEST_PLAN_NOT_BOUND_NO_POST,
            order_kind_safe_label="",
            blocked_reasons=tuple(not_bound_reasons),
            request_plan_is_entry_only=True,
            request_plan_current_turn_binding=False,
        )

    if not binding_input.internal_raw_value_source_present:
        # Safe-label binding is otherwise complete, but no reviewed internal
        # raw value source exists for an actual send: the actual gate must
        # block (APPROVED_SIZE_RUNTIME_VALUE_SOURCE_MISSING family).
        return EntryRequestPlanBindingResult(
            status=(
                GmoEntryRequestPlanStatus
                .ENTRY_REQUEST_PLAN_PRESENT_BUT_NEEDS_INTERNAL_VALUE_SOURCE
            ),
            order_kind_safe_label=order_kind.value,
            blocked_reasons=("INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE",),
            request_plan_is_entry_only=True,
            request_plan_current_turn_binding=False,
        )

    if not binding_input.current_turn_binding_confirmed:
        return EntryRequestPlanBindingResult(
            status=(
                GmoEntryRequestPlanStatus
                .ENTRY_REQUEST_PLAN_PRESENT_BUT_NEEDS_FRESH_ACTUAL_GATE
            ),
            order_kind_safe_label=order_kind.value,
            blocked_reasons=("CURRENT_TURN_BINDING_NOT_CONFIRMED",),
            request_plan_is_entry_only=True,
            request_plan_current_turn_binding=False,
        )

    return EntryRequestPlanBindingResult(
        status=GmoEntryRequestPlanStatus.ENTRY_REQUEST_PLAN_BOUND_SAFE,
        order_kind_safe_label=order_kind.value,
        blocked_reasons=(),
        request_plan_is_entry_only=True,
        request_plan_current_turn_binding=True,
    )


def validate_entry_only_request_plan(plan: GmoFxPrivateRequestPlan) -> None:
    """Raise unless the plan is exactly the dedicated ENTRY plan.

    The raised error never contains the plan body or any value from it.
    """

    if plan.request_kind != REQUEST_KIND_ENTRY:
        raise GmoEntryRequestPlanBindingError(
            "request plan is not the dedicated entry plan"
        )
    if plan.method != GMO_FX_ENTRY_ORDER_METHOD:
        raise GmoEntryRequestPlanBindingError("request plan method is not entry-only")
    if plan.path != GMO_FX_ENTRY_ORDER_PATH:
        raise GmoEntryRequestPlanBindingError("request plan path is not entry-only")


def build_bound_entry_request_plan(
    *,
    binding_result: EntryRequestPlanBindingResult,
    approved_symbol: str,
    approved_size: str,
) -> GmoFxPrivateRequestPlan:
    """Build the internal entry request plan for the injected actual sender.

    Internal use only: the returned plan is handed to the actual sender and is
    never reported, logged, or previewed. ``approved_symbol`` and
    ``approved_size`` must come from the existing approved configuration; this
    function never invents, adjusts, or exposes them. It raises fail-closed
    unless the binding result is BOUND_SAFE, and the raised error never
    contains the symbol or size values.
    """

    if (
        binding_result.status
        is not GmoEntryRequestPlanStatus.ENTRY_REQUEST_PLAN_BOUND_SAFE
    ):
        raise GmoEntryRequestPlanBindingError(
            "entry request plan is not BOUND_SAFE for the current turn"
        )
    order_kind = GmoEntryOrderKindSafeLabel(binding_result.order_kind_safe_label)
    plan = build_gmo_fx_entry_request_plan(
        symbol=approved_symbol,
        side=_ORDER_KIND_TO_BUILDER_SIDE[order_kind],
        size=approved_size,
    )
    validate_entry_only_request_plan(plan)
    return plan


@dataclass(frozen=True)
class EntryRequestPlanSafePreview:
    """Safe preview of the binding. Labels and safe booleans only."""

    request_plan_status_safe_label: str
    order_kind_safe_label: str
    request_plan_is_entry_only: bool
    request_plan_current_turn_binding: bool
    request_plan_raw_body_exposed: bool = False
    request_plan_ids_exposed: bool = False
    request_plan_price_size_pnl_exposed: bool = False
    request_plan_credentials_exposed: bool = False

    def __bool__(self) -> bool:
        return False


def build_entry_request_plan_safe_preview(
    binding_result: EntryRequestPlanBindingResult,
) -> EntryRequestPlanSafePreview:
    return EntryRequestPlanSafePreview(
        request_plan_status_safe_label=binding_result.status.value,
        order_kind_safe_label=binding_result.order_kind_safe_label,
        request_plan_is_entry_only=binding_result.request_plan_is_entry_only,
        request_plan_current_turn_binding=(
            binding_result.request_plan_current_turn_binding
        ),
    )


@dataclass(frozen=True)
class ActualEntryGateSanitizedPreview:
    """Combined sanitized preview for the actual entry gate.

    Every field is a safe label or safe boolean. There is no field that can
    carry a raw request, a body, a size, a price, a P/L, an ID, a credential,
    a signature, or a header value.
    """

    operator_signal_type_safe_label: str
    order_kind_safe_label: str
    request_plan_status_safe_label: str
    request_plan_is_entry_only: bool
    approved_profile_status_safe_label: str
    approved_symbol_safe_label: str
    approved_size_profile_safe_label: str
    approved_execution_type_safe_label: str
    internal_raw_value_source_status_safe_label: str
    market_status_safe_label: str
    ticker_freshness_safe_label: str
    spread_status_safe_label: str
    runtime_position_safe_status: str
    active_pending_safe_status: str
    credential_presence_safe_boolean: bool
    permit_status_safe_label: str
    hard_guard_status_safe_label: str
    sender_injection_ready_safe_label: str
    entry_post_max_count: int = 1
    retry: bool = False
    repost: bool = False
    second_post: bool = False
    settlement_post: bool = False
    generic_close: bool = False
    raw_id_value_exposure: bool = False
    credential_value_exposed: bool = False

    def __bool__(self) -> bool:
        return False


def build_actual_entry_gate_sanitized_preview(
    *,
    operator_signal_type_safe_label: str,
    binding_preview: EntryRequestPlanSafePreview,
    approved_profile: ApprovedEntryOrderProfile,
    market_status_safe_label: str,
    ticker_freshness_safe_label: str,
    spread_status_safe_label: str,
    runtime_position_safe_status: str,
    active_pending_safe_status: str,
    credential_presence_safe_boolean: bool,
    permit_status_safe_label: str,
    hard_guard_status_safe_label: str,
    sender_injection_ready_safe_label: str,
) -> ActualEntryGateSanitizedPreview:
    """Assemble the combined sanitized preview from safe labels only."""

    return ActualEntryGateSanitizedPreview(
        operator_signal_type_safe_label=operator_signal_type_safe_label,
        order_kind_safe_label=binding_preview.order_kind_safe_label,
        request_plan_status_safe_label=(
            binding_preview.request_plan_status_safe_label
        ),
        request_plan_is_entry_only=binding_preview.request_plan_is_entry_only,
        approved_profile_status_safe_label=approved_profile.profile_status.value,
        approved_symbol_safe_label=approved_profile.approved_symbol_safe_label,
        approved_size_profile_safe_label=(
            approved_profile.approved_size_profile_safe_label
        ),
        approved_execution_type_safe_label=(
            approved_profile.approved_execution_type_safe_label
        ),
        internal_raw_value_source_status_safe_label=(
            approved_profile.internal_raw_value_source_status.value
        ),
        market_status_safe_label=market_status_safe_label,
        ticker_freshness_safe_label=ticker_freshness_safe_label,
        spread_status_safe_label=spread_status_safe_label,
        runtime_position_safe_status=runtime_position_safe_status,
        active_pending_safe_status=active_pending_safe_status,
        credential_presence_safe_boolean=credential_presence_safe_boolean,
        permit_status_safe_label=permit_status_safe_label,
        hard_guard_status_safe_label=hard_guard_status_safe_label,
        sender_injection_ready_safe_label=sender_injection_ready_safe_label,
    )
