"""No-POST entry actual-gate PRECHECK for GMO live execution.

This module classifies whether every pre-entry gate is satisfied BEFORE the
separate entry POST gate step. It is read-only and no-POST by design:

- The precheck result is never an execution permission.
  `actual_entry_POST_allowed` is hardcoded ``False`` and the summary's
  ``__bool__`` is ``False`` so it can never act as an allow-bridge.
- The operator current-turn exact confirmation is deliberately NOT an input
  here: a confirmation cannot be captured, banked, or replayed by this
  precheck. It stays "still required" and is only ever handled by the
  separate ``ENTRY_POST_GATE_WITH_OPERATOR_CURRENT_TURN_CONFIRMATION`` step.
- The entry side comes only from an operator safe label
  (``ENTRY_BUY`` / ``ENTRY_SELL`` / ``HOLD``). This module never decides,
  infers, or defaults a trade direction; unknown text is classified as
  unsafe raw text and blocks, and ``HOLD`` never becomes an entry candidate.

Nothing here reads credentials, ``.env``, or the network, and nothing here
carries a raw response, a real position/order ID, or a broker value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GmoEntryOperatorSignalSafeLabel(str, Enum):
    """Safe labels for the operator-provided entry signal.

    Only the operator supplies one of these; this module never derives
    ``ENTRY_BUY`` / ``ENTRY_SELL`` / ``HOLD`` from market data or any
    inference of its own.
    """

    ENTRY_BUY = "ENTRY_BUY"
    ENTRY_SELL = "ENTRY_SELL"
    HOLD = "HOLD"
    OPERATOR_SIGNAL_NOT_PROVIDED = "OPERATOR_SIGNAL_NOT_PROVIDED"
    OPERATOR_SIGNAL_UNSAFE_RAW_TEXT_PROVIDED = (
        "OPERATOR_SIGNAL_UNSAFE_RAW_TEXT_PROVIDED"
    )


def normalize_entry_operator_signal_safe_label(
    candidate: str | GmoEntryOperatorSignalSafeLabel | None,
) -> GmoEntryOperatorSignalSafeLabel:
    """Validate an operator entry-signal label without interpreting raw text."""

    if candidate is None:
        return GmoEntryOperatorSignalSafeLabel.OPERATOR_SIGNAL_NOT_PROVIDED
    if isinstance(candidate, GmoEntryOperatorSignalSafeLabel):
        return candidate
    try:
        return GmoEntryOperatorSignalSafeLabel(str(candidate))
    except ValueError:
        return GmoEntryOperatorSignalSafeLabel.OPERATOR_SIGNAL_UNSAFE_RAW_TEXT_PROVIDED


class GmoEntryActualGatePrecheckStatus(str, Enum):
    ENTRY_PRECHECK_BLOCKED_BY_REPO_STATE = "ENTRY_PRECHECK_BLOCKED_BY_REPO_STATE"
    ENTRY_PRECHECK_BLOCKED_BY_CREDENTIAL_BOUNDARY = (
        "ENTRY_PRECHECK_BLOCKED_BY_CREDENTIAL_BOUNDARY"
    )
    ENTRY_PRECHECK_BLOCKED_BY_RUNTIME_SAFE_READ = (
        "ENTRY_PRECHECK_BLOCKED_BY_RUNTIME_SAFE_READ"
    )
    ENTRY_PRECHECK_BLOCKED_BY_RUNTIME_POSITION_STATE = (
        "ENTRY_PRECHECK_BLOCKED_BY_RUNTIME_POSITION_STATE"
    )
    ENTRY_PRECHECK_BLOCKED_BY_OPERATOR_SIGNAL = (
        "ENTRY_PRECHECK_BLOCKED_BY_OPERATOR_SIGNAL"
    )
    ENTRY_PRECHECK_BLOCKED_BY_OPERATOR_READINESS = (
        "ENTRY_PRECHECK_BLOCKED_BY_OPERATOR_READINESS"
    )
    ENTRY_PRECHECK_BLOCKED_BY_POST_POLICY = "ENTRY_PRECHECK_BLOCKED_BY_POST_POLICY"
    ENTRY_PRECHECK_READY_NO_POST_OPERATOR_CURRENT_TURN_GATE_REQUIRED = (
        "ENTRY_PRECHECK_READY_NO_POST_OPERATOR_CURRENT_TURN_GATE_REQUIRED"
    )


class GmoEntryActualGatePrecheckNextStep(str, Enum):
    NEXT_STEP_ENTRY_POST_GATE_WITH_OPERATOR_CURRENT_TURN_CONFIRMATION = (
        "NEXT_STEP_ENTRY_POST_GATE_WITH_OPERATOR_CURRENT_TURN_CONFIRMATION"
    )
    NEXT_STEP_ENTRY_ACTUAL_GATE_PRECHECK_OPERATOR_CONFIRMATION_REQUIRED = (
        "NEXT_STEP_ENTRY_ACTUAL_GATE_PRECHECK_OPERATOR_CONFIRMATION_REQUIRED"
    )
    NEXT_STEP_RESOLVE_ENTRY_PRECHECK_BLOCKERS_NO_POST = (
        "NEXT_STEP_RESOLVE_ENTRY_PRECHECK_BLOCKERS_NO_POST"
    )


_OPERATOR_BLOCKERS = frozenset(
    {
        "ENTRY_PRECHECK_OPERATOR_SIGNAL_NOT_PROVIDED",
        "ENTRY_PRECHECK_OPERATOR_SIGNAL_UNSAFE_RAW_TEXT",
        "ENTRY_PRECHECK_OPERATOR_SIGNAL_HOLD_NO_ENTRY_CANDIDATE",
        "ENTRY_PRECHECK_OPERATOR_READINESS_NOT_CONFIRMED",
    }
)


@dataclass(frozen=True)
class GmoEntryActualGatePrecheckInput:
    """Safe inputs for the entry precheck. Every default is fail-closed.

    There is intentionally no field for an operator current-turn exact
    confirmation: that confirmation belongs exclusively to the separate
    entry POST gate step and must never be banked through this precheck.
    """

    head_equals_origin_main_safe: bool = False
    working_tree_clean_safe: bool = False
    credential_presence_safe_boolean: bool = False
    credential_boundary_ready: bool = False
    credential_actual_use_operator_approved: bool = False
    runtime_safe_read_performed: bool = False
    runtime_safe_read_fresh: bool = False
    pre_entry_open_positions_count_safe: int | None = None
    pre_entry_active_or_pending_order_conflict_count_safe: int | None = None
    fresh_entry_signal_safe_label_exists: bool = False
    entry_signal_is_fresh: bool = False
    operator_entry_signal_safe_label: str | GmoEntryOperatorSignalSafeLabel | None = None
    operator_readiness_confirmed: bool = False
    max_entry_post_count: int = 1
    retry_requested: bool = False
    repost_requested: bool = False
    second_post_requested: bool = False
    settlement_post_requested: bool = False
    generic_close_requested: bool = False


@dataclass(frozen=True)
class GmoEntryActualGatePrecheckSummary:
    """No-POST precheck snapshot. Never an execution permission.

    ``__bool__`` stays false so this object can never be used as an
    allow-bridge, and the actual-POST / AI-decision / confirmation fields
    below are hardcoded by the builder and never derived from inputs.
    """

    precheck_ready: bool
    status: GmoEntryActualGatePrecheckStatus
    blocked_reasons: tuple[str, ...]
    operator_entry_signal_safe_label: GmoEntryOperatorSignalSafeLabel
    entry_candidate_exists: bool
    recommended_next_step: GmoEntryActualGatePrecheckNextStep
    ai_trade_decision_performed: bool = False
    actual_entry_POST_allowed: bool = False
    entry_post_execution_gate_is_separate_step: bool = True
    operator_current_turn_exact_confirmation_still_required: bool = True
    operator_confirmation_substituted: bool = False
    max_entry_post_limit: int = 1
    retry_allowed: bool = False
    repost_allowed: bool = False
    second_post_allowed: bool = False

    def __bool__(self) -> bool:
        return False


def classify_gmo_entry_actual_gate_precheck_blockers(
    precheck_input: GmoEntryActualGatePrecheckInput,
) -> tuple[str, ...]:
    """Build deterministic blocker labels for the entry precheck."""

    blockers: list[str] = []

    if not precheck_input.head_equals_origin_main_safe:
        blockers.append("ENTRY_PRECHECK_HEAD_MISMATCH")
    if not precheck_input.working_tree_clean_safe:
        blockers.append("ENTRY_PRECHECK_WORKING_TREE_NOT_CLEAN")

    if not precheck_input.credential_presence_safe_boolean:
        blockers.append("ENTRY_PRECHECK_CREDENTIAL_PRESENCE_NOT_CONFIRMED")
    if not precheck_input.credential_boundary_ready:
        blockers.append("ENTRY_PRECHECK_CREDENTIAL_BOUNDARY_NOT_READY")
    if not precheck_input.credential_actual_use_operator_approved:
        blockers.append("ENTRY_PRECHECK_CREDENTIAL_ACTUAL_USE_NOT_APPROVED")

    if not precheck_input.runtime_safe_read_performed:
        blockers.append("ENTRY_PRECHECK_RUNTIME_SAFE_READ_NOT_PERFORMED")
    if not precheck_input.runtime_safe_read_fresh:
        blockers.append("ENTRY_PRECHECK_RUNTIME_SAFE_READ_STALE")

    if precheck_input.pre_entry_open_positions_count_safe != 0:
        blockers.append("ENTRY_PRECHECK_OPEN_POSITIONS_NOT_ZERO")
    if precheck_input.pre_entry_active_or_pending_order_conflict_count_safe != 0:
        blockers.append("ENTRY_PRECHECK_ACTIVE_PENDING_ORDER_CONFLICT")

    if not precheck_input.fresh_entry_signal_safe_label_exists:
        blockers.append("ENTRY_PRECHECK_FRESH_ENTRY_SIGNAL_MISSING")
    if not precheck_input.entry_signal_is_fresh:
        blockers.append("ENTRY_PRECHECK_ENTRY_SIGNAL_STALE")

    signal = normalize_entry_operator_signal_safe_label(
        precheck_input.operator_entry_signal_safe_label,
    )
    if signal is GmoEntryOperatorSignalSafeLabel.OPERATOR_SIGNAL_NOT_PROVIDED:
        blockers.append("ENTRY_PRECHECK_OPERATOR_SIGNAL_NOT_PROVIDED")
    if signal is GmoEntryOperatorSignalSafeLabel.OPERATOR_SIGNAL_UNSAFE_RAW_TEXT_PROVIDED:
        blockers.append("ENTRY_PRECHECK_OPERATOR_SIGNAL_UNSAFE_RAW_TEXT")
    if signal is GmoEntryOperatorSignalSafeLabel.HOLD:
        blockers.append("ENTRY_PRECHECK_OPERATOR_SIGNAL_HOLD_NO_ENTRY_CANDIDATE")

    if not precheck_input.operator_readiness_confirmed:
        blockers.append("ENTRY_PRECHECK_OPERATOR_READINESS_NOT_CONFIRMED")

    if precheck_input.max_entry_post_count != 1:
        blockers.append("ENTRY_PRECHECK_POST_LIMIT_INVALID")
    if (
        precheck_input.retry_requested
        or precheck_input.repost_requested
        or precheck_input.second_post_requested
    ):
        blockers.append("ENTRY_PRECHECK_RETRY_REPOST_OR_SECOND_POST_REQUESTED")
    if precheck_input.settlement_post_requested:
        blockers.append("ENTRY_PRECHECK_SETTLEMENT_POST_REQUESTED")
    if precheck_input.generic_close_requested:
        blockers.append("ENTRY_PRECHECK_GENERIC_CLOSE_REQUESTED")

    return tuple(blockers)


def _status_from_blockers(
    blockers: tuple[str, ...],
) -> GmoEntryActualGatePrecheckStatus:
    def _any(*labels: str) -> bool:
        return any(label in blockers for label in labels)

    if _any(
        "ENTRY_PRECHECK_HEAD_MISMATCH",
        "ENTRY_PRECHECK_WORKING_TREE_NOT_CLEAN",
    ):
        return GmoEntryActualGatePrecheckStatus.ENTRY_PRECHECK_BLOCKED_BY_REPO_STATE
    if _any(
        "ENTRY_PRECHECK_CREDENTIAL_PRESENCE_NOT_CONFIRMED",
        "ENTRY_PRECHECK_CREDENTIAL_BOUNDARY_NOT_READY",
        "ENTRY_PRECHECK_CREDENTIAL_ACTUAL_USE_NOT_APPROVED",
    ):
        return (
            GmoEntryActualGatePrecheckStatus.ENTRY_PRECHECK_BLOCKED_BY_CREDENTIAL_BOUNDARY
        )
    if _any(
        "ENTRY_PRECHECK_RUNTIME_SAFE_READ_NOT_PERFORMED",
        "ENTRY_PRECHECK_RUNTIME_SAFE_READ_STALE",
    ):
        return GmoEntryActualGatePrecheckStatus.ENTRY_PRECHECK_BLOCKED_BY_RUNTIME_SAFE_READ
    if _any(
        "ENTRY_PRECHECK_OPEN_POSITIONS_NOT_ZERO",
        "ENTRY_PRECHECK_ACTIVE_PENDING_ORDER_CONFLICT",
    ):
        return (
            GmoEntryActualGatePrecheckStatus.ENTRY_PRECHECK_BLOCKED_BY_RUNTIME_POSITION_STATE
        )
    if _any(
        "ENTRY_PRECHECK_OPERATOR_SIGNAL_NOT_PROVIDED",
        "ENTRY_PRECHECK_OPERATOR_SIGNAL_UNSAFE_RAW_TEXT",
        "ENTRY_PRECHECK_OPERATOR_SIGNAL_HOLD_NO_ENTRY_CANDIDATE",
        "ENTRY_PRECHECK_FRESH_ENTRY_SIGNAL_MISSING",
        "ENTRY_PRECHECK_ENTRY_SIGNAL_STALE",
    ):
        return GmoEntryActualGatePrecheckStatus.ENTRY_PRECHECK_BLOCKED_BY_OPERATOR_SIGNAL
    if "ENTRY_PRECHECK_OPERATOR_READINESS_NOT_CONFIRMED" in blockers:
        return (
            GmoEntryActualGatePrecheckStatus.ENTRY_PRECHECK_BLOCKED_BY_OPERATOR_READINESS
        )
    if blockers:
        return GmoEntryActualGatePrecheckStatus.ENTRY_PRECHECK_BLOCKED_BY_POST_POLICY
    return (
        GmoEntryActualGatePrecheckStatus
        .ENTRY_PRECHECK_READY_NO_POST_OPERATOR_CURRENT_TURN_GATE_REQUIRED
    )


def build_gmo_live_entry_actual_gate_precheck_summary(
    precheck_input: GmoEntryActualGatePrecheckInput | None = None,
) -> GmoEntryActualGatePrecheckSummary:
    """Build the no-POST entry precheck summary.

    A ready result only means "the separate operator current-turn POST gate
    step may be prepared next". It never authorizes an entry POST: the
    actual-POST fields below are hardcoded and independent of the inputs.
    """

    snapshot = precheck_input or GmoEntryActualGatePrecheckInput()
    blockers = classify_gmo_entry_actual_gate_precheck_blockers(snapshot)
    status = _status_from_blockers(blockers)
    signal = normalize_entry_operator_signal_safe_label(
        snapshot.operator_entry_signal_safe_label,
    )
    precheck_ready = not blockers
    entry_candidate_exists = precheck_ready and signal in (
        GmoEntryOperatorSignalSafeLabel.ENTRY_BUY,
        GmoEntryOperatorSignalSafeLabel.ENTRY_SELL,
    )

    if precheck_ready:
        next_step = (
            GmoEntryActualGatePrecheckNextStep
            .NEXT_STEP_ENTRY_POST_GATE_WITH_OPERATOR_CURRENT_TURN_CONFIRMATION
        )
    elif any(label in _OPERATOR_BLOCKERS for label in blockers):
        next_step = (
            GmoEntryActualGatePrecheckNextStep
            .NEXT_STEP_ENTRY_ACTUAL_GATE_PRECHECK_OPERATOR_CONFIRMATION_REQUIRED
        )
    else:
        next_step = (
            GmoEntryActualGatePrecheckNextStep
            .NEXT_STEP_RESOLVE_ENTRY_PRECHECK_BLOCKERS_NO_POST
        )

    return GmoEntryActualGatePrecheckSummary(
        precheck_ready=precheck_ready,
        status=status,
        blocked_reasons=blockers,
        operator_entry_signal_safe_label=signal,
        entry_candidate_exists=entry_candidate_exists,
        recommended_next_step=next_step,
        ai_trade_decision_performed=False,
        actual_entry_POST_allowed=False,
        entry_post_execution_gate_is_separate_step=True,
        operator_current_turn_exact_confirmation_still_required=True,
        operator_confirmation_substituted=False,
        max_entry_post_limit=1,
        retry_allowed=False,
        repost_allowed=False,
        second_post_allowed=False,
    )
