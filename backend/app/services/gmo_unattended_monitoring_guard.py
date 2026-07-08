"""Unattended monitoring guard (no-POST, fail-closed, safe labels only).

Evaluates a safe-label-only snapshot into a single guard decision for the
paper/synthetic unattended readiness layer. This module has no broker, HTTP,
credential, environment, or raw-value surface at all:

- Inputs are safe status enums and safe booleans. There is structurally no
  field for a raw price, spread, PnL, timestamp, size, or ID, so none can be
  logged, raised, or reported from here.
- Fail-closed: every UNKNOWN status halts. Multiple halt causes are ranked
  by a fixed priority; the decision is the highest-priority cause and the
  result also carries every matched cause for reporting.
- ``GUARD_PASS`` is NEVER an actual permission: the result pins
  ``guard_pass_is_actual_permission = False`` and ``live_post_allowed =
  False``, and the result is never truthy. Passing this guard only means the
  PAPER layer may continue.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GmoUnattendedGuardError(RuntimeError):
    """Raised for fail-closed violations. Never carries a raw value."""


class MarketSafeStatus(str, Enum):
    MARKET_SAFE = "MARKET_SAFE"
    MARKET_UNSAFE = "MARKET_UNSAFE"
    MARKET_UNKNOWN = "MARKET_UNKNOWN"


class TickerFreshStatus(str, Enum):
    TICKER_FRESH = "TICKER_FRESH"
    TICKER_STALE = "TICKER_STALE"
    TICKER_UNKNOWN = "TICKER_UNKNOWN"


class SpreadSafeStatus(str, Enum):
    SPREAD_WITHIN_LIMIT = "SPREAD_WITHIN_LIMIT"
    SPREAD_OUT_OF_LIMIT = "SPREAD_OUT_OF_LIMIT"
    SPREAD_UNKNOWN = "SPREAD_UNKNOWN"


class RuntimePositionSafeStatus(str, Enum):
    NO_POSITION = "NO_POSITION"
    ONE_POSITION_OPEN = "ONE_POSITION_OPEN"
    MULTIPLE_POSITIONS_OPEN = "MULTIPLE_POSITIONS_OPEN"
    POSITION_UNKNOWN = "POSITION_UNKNOWN"


class PositionCountSafeStatus(str, Enum):
    COUNT_ZERO = "COUNT_ZERO"
    COUNT_ONE = "COUNT_ONE"
    COUNT_MISMATCH = "COUNT_MISMATCH"
    COUNT_UNKNOWN = "COUNT_UNKNOWN"


class ActivePendingOrderSafeStatus(str, Enum):
    NO_ACTIVE_PENDING_ORDERS = "NO_ACTIVE_PENDING_ORDERS"
    ACTIVE_PENDING_ORDERS_PRESENT = "ACTIVE_PENDING_ORDERS_PRESENT"
    ACTIVE_PENDING_ORDERS_UNKNOWN = "ACTIVE_PENDING_ORDERS_UNKNOWN"


class MaxHoldStatus(str, Enum):
    HOLD_WITHIN_LIMIT = "HOLD_WITHIN_LIMIT"
    HOLD_LIMIT_EXCEEDED = "HOLD_LIMIT_EXCEEDED"
    HOLD_UNKNOWN = "HOLD_UNKNOWN"


class MaxLossStatus(str, Enum):
    """Loss safe categories only. A raw PnL value never exists here."""

    LOSS_WITHIN_LIMIT = "LOSS_WITHIN_LIMIT"
    LOSS_LIMIT_EXCEEDED = "LOSS_LIMIT_EXCEEDED"
    LOSS_UNKNOWN = "LOSS_UNKNOWN"


class ConsecutiveFailureStatus(str, Enum):
    FAILURE_WITHIN_LIMIT = "FAILURE_WITHIN_LIMIT"
    FAILURE_LIMIT_EXCEEDED = "FAILURE_LIMIT_EXCEEDED"
    FAILURE_UNKNOWN = "FAILURE_UNKNOWN"


class UnknownEventStatus(str, Enum):
    UNKNOWN_WITHIN_LIMIT = "UNKNOWN_WITHIN_LIMIT"
    UNKNOWN_LIMIT_EXCEEDED = "UNKNOWN_LIMIT_EXCEEDED"
    UNKNOWN_PRESENT = "UNKNOWN_PRESENT"


class PaperTransportStatus(str, Enum):
    FAKE_TRANSPORT_CONFIRMED = "FAKE_TRANSPORT_CONFIRMED"
    TRANSPORT_UNKNOWN = "TRANSPORT_UNKNOWN"
    REAL_TRANSPORT_BLOCKED = "REAL_TRANSPORT_BLOCKED"


class StateConsistencyStatus(str, Enum):
    STATE_CONSISTENT = "STATE_CONSISTENT"
    STATE_INCONSISTENT = "STATE_INCONSISTENT"
    STATE_UNKNOWN = "STATE_UNKNOWN"


class UnattendedGuardDecision(str, Enum):
    GUARD_PASS = "GUARD_PASS"
    GUARD_HALT_KILL_SWITCH = "GUARD_HALT_KILL_SWITCH"
    GUARD_HALT_REAL_TRANSPORT = "GUARD_HALT_REAL_TRANSPORT"
    GUARD_HALT_STATE_INCONSISTENT = "GUARD_HALT_STATE_INCONSISTENT"
    GUARD_HALT_MARKET_UNSAFE = "GUARD_HALT_MARKET_UNSAFE"
    GUARD_HALT_TICKER_STALE = "GUARD_HALT_TICKER_STALE"
    GUARD_HALT_SPREAD_OUT_OF_LIMIT = "GUARD_HALT_SPREAD_OUT_OF_LIMIT"
    GUARD_HALT_POSITION_COUNT_MISMATCH = "GUARD_HALT_POSITION_COUNT_MISMATCH"
    GUARD_HALT_ACTIVE_PENDING_PRESENT = "GUARD_HALT_ACTIVE_PENDING_PRESENT"
    GUARD_HALT_MAX_HOLD_EXCEEDED = "GUARD_HALT_MAX_HOLD_EXCEEDED"
    GUARD_HALT_MAX_LOSS_EXCEEDED = "GUARD_HALT_MAX_LOSS_EXCEEDED"
    GUARD_HALT_FAILURE_LIMIT = "GUARD_HALT_FAILURE_LIMIT"
    GUARD_HALT_UNKNOWN_EVENT = "GUARD_HALT_UNKNOWN_EVENT"
    GUARD_HALT_INPUT_UNKNOWN = "GUARD_HALT_INPUT_UNKNOWN"
    GUARD_HALT_UNSUPPORTED = "GUARD_HALT_UNSUPPORTED"


@dataclass(frozen=True)
class UnattendedMonitoringGuardSafeSnapshot:
    """Safe-label-only guard input. Default state is fully UNKNOWN (halts).

    ``kill_switch_engaged`` is tri-state on purpose: ``None`` means the kill
    switch state could not be determined, which halts.
    """

    kill_switch_engaged: bool | None = None
    market_safe_status: MarketSafeStatus = MarketSafeStatus.MARKET_UNKNOWN
    ticker_fresh_status: TickerFreshStatus = TickerFreshStatus.TICKER_UNKNOWN
    spread_safe_status: SpreadSafeStatus = SpreadSafeStatus.SPREAD_UNKNOWN
    runtime_position_safe_status: RuntimePositionSafeStatus = (
        RuntimePositionSafeStatus.POSITION_UNKNOWN
    )
    position_count_safe: PositionCountSafeStatus = (
        PositionCountSafeStatus.COUNT_UNKNOWN
    )
    active_pending_order_safe_status: ActivePendingOrderSafeStatus = (
        ActivePendingOrderSafeStatus.ACTIVE_PENDING_ORDERS_UNKNOWN
    )
    max_hold_status: MaxHoldStatus = MaxHoldStatus.HOLD_UNKNOWN
    max_loss_status: MaxLossStatus = MaxLossStatus.LOSS_UNKNOWN
    consecutive_failure_status: ConsecutiveFailureStatus = (
        ConsecutiveFailureStatus.FAILURE_UNKNOWN
    )
    unknown_event_status: UnknownEventStatus = UnknownEventStatus.UNKNOWN_PRESENT
    paper_transport_status: PaperTransportStatus = (
        PaperTransportStatus.TRANSPORT_UNKNOWN
    )
    state_consistency_status: StateConsistencyStatus = (
        StateConsistencyStatus.STATE_UNKNOWN
    )


@dataclass(frozen=True)
class UnattendedMonitoringGuardResult:
    """Guard outcome. Never truthy, never an actual permission."""

    decision: UnattendedGuardDecision
    halted: bool
    halt_causes: tuple[UnattendedGuardDecision, ...]
    guard_pass_is_actual_permission: bool = False
    live_post_allowed: bool = False
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False
    raw_value_exposure: bool = False

    def __bool__(self) -> bool:
        return False


# Fixed halt priority: the first matched cause becomes the decision.
_POSITION_OK = frozenset(
    {
        RuntimePositionSafeStatus.NO_POSITION,
        RuntimePositionSafeStatus.ONE_POSITION_OPEN,
    }
)
_COUNT_OK = frozenset(
    {PositionCountSafeStatus.COUNT_ZERO, PositionCountSafeStatus.COUNT_ONE}
)


def evaluate_unattended_monitoring_guard(
    snapshot: UnattendedMonitoringGuardSafeSnapshot,
) -> UnattendedMonitoringGuardResult:
    """Evaluate the guard snapshot fail-closed.

    Every UNKNOWN halts. The returned decision is the highest-priority
    matched cause; ``halt_causes`` lists all matched causes in priority
    order. GUARD_PASS still never allows a live POST.
    """

    causes: list[UnattendedGuardDecision] = []

    if snapshot.kill_switch_engaged is not False:
        # Engaged (True) or indeterminate (None) both halt.
        causes.append(UnattendedGuardDecision.GUARD_HALT_KILL_SWITCH)
    if snapshot.paper_transport_status is not (
        PaperTransportStatus.FAKE_TRANSPORT_CONFIRMED
    ):
        causes.append(UnattendedGuardDecision.GUARD_HALT_REAL_TRANSPORT)
    if snapshot.state_consistency_status is not (
        StateConsistencyStatus.STATE_CONSISTENT
    ):
        causes.append(UnattendedGuardDecision.GUARD_HALT_STATE_INCONSISTENT)
    if snapshot.market_safe_status is not MarketSafeStatus.MARKET_SAFE:
        causes.append(UnattendedGuardDecision.GUARD_HALT_MARKET_UNSAFE)
    if snapshot.ticker_fresh_status is not TickerFreshStatus.TICKER_FRESH:
        causes.append(UnattendedGuardDecision.GUARD_HALT_TICKER_STALE)
    if snapshot.spread_safe_status is not SpreadSafeStatus.SPREAD_WITHIN_LIMIT:
        causes.append(UnattendedGuardDecision.GUARD_HALT_SPREAD_OUT_OF_LIMIT)
    if (
        snapshot.runtime_position_safe_status not in _POSITION_OK
        or snapshot.position_count_safe not in _COUNT_OK
    ):
        causes.append(UnattendedGuardDecision.GUARD_HALT_POSITION_COUNT_MISMATCH)
    if snapshot.active_pending_order_safe_status is not (
        ActivePendingOrderSafeStatus.NO_ACTIVE_PENDING_ORDERS
    ):
        causes.append(UnattendedGuardDecision.GUARD_HALT_ACTIVE_PENDING_PRESENT)
    if snapshot.max_hold_status is not MaxHoldStatus.HOLD_WITHIN_LIMIT:
        causes.append(UnattendedGuardDecision.GUARD_HALT_MAX_HOLD_EXCEEDED)
    if snapshot.max_loss_status is not MaxLossStatus.LOSS_WITHIN_LIMIT:
        causes.append(UnattendedGuardDecision.GUARD_HALT_MAX_LOSS_EXCEEDED)
    if snapshot.consecutive_failure_status is not (
        ConsecutiveFailureStatus.FAILURE_WITHIN_LIMIT
    ):
        causes.append(UnattendedGuardDecision.GUARD_HALT_FAILURE_LIMIT)
    if snapshot.unknown_event_status is not UnknownEventStatus.UNKNOWN_WITHIN_LIMIT:
        causes.append(UnattendedGuardDecision.GUARD_HALT_UNKNOWN_EVENT)

    if causes:
        return UnattendedMonitoringGuardResult(
            decision=causes[0],
            halted=True,
            halt_causes=tuple(causes),
        )
    return UnattendedMonitoringGuardResult(
        decision=UnattendedGuardDecision.GUARD_PASS,
        halted=False,
        halt_causes=(),
    )


def build_all_safe_guard_snapshot() -> UnattendedMonitoringGuardSafeSnapshot:
    """All-green snapshot for tests and paper scenarios (flat, clear, safe)."""

    return UnattendedMonitoringGuardSafeSnapshot(
        kill_switch_engaged=False,
        market_safe_status=MarketSafeStatus.MARKET_SAFE,
        ticker_fresh_status=TickerFreshStatus.TICKER_FRESH,
        spread_safe_status=SpreadSafeStatus.SPREAD_WITHIN_LIMIT,
        runtime_position_safe_status=RuntimePositionSafeStatus.NO_POSITION,
        position_count_safe=PositionCountSafeStatus.COUNT_ZERO,
        active_pending_order_safe_status=(
            ActivePendingOrderSafeStatus.NO_ACTIVE_PENDING_ORDERS
        ),
        max_hold_status=MaxHoldStatus.HOLD_WITHIN_LIMIT,
        max_loss_status=MaxLossStatus.LOSS_WITHIN_LIMIT,
        consecutive_failure_status=ConsecutiveFailureStatus.FAILURE_WITHIN_LIMIT,
        unknown_event_status=UnknownEventStatus.UNKNOWN_WITHIN_LIMIT,
        paper_transport_status=PaperTransportStatus.FAKE_TRANSPORT_CONFIRMED,
        state_consistency_status=StateConsistencyStatus.STATE_CONSISTENT,
    )
