"""No-POST runtime safe-read boundary for GMO live pre-entry checks.

Models the read-only confirmation a future entry gate needs (NO_POSITION /
count=0 / active-pending clear / market open / ticker fresh / spread within
limit), using only safe statuses and safe counts.

Hard rules enforced by construction:

- A client only ever returns a ``GmoRuntimeSafeReadSnapshot`` of safe
  statuses and non-negative safe counts. There is no field that can carry a
  raw payload, a position/order/trade ID, a size, a price, a P/L, or a
  timestamp.
- This module performs no HTTP and reads no credentials or ``.env``. The
  fake client is the only client here; a real read-only client integration
  is a separate, explicitly reviewed step.
- The gate is fail-closed: unknown, stale, or non-zero states all block.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class GmoRuntimePositionSafeStatus(str, Enum):
    NO_POSITION = "NO_POSITION"
    ONE_POSITION_OPEN = "ONE_POSITION_OPEN"
    MULTIPLE_POSITIONS = "MULTIPLE_POSITIONS"
    UNKNOWN = "UNKNOWN"


class GmoRuntimeActivePendingSafeStatus(str, Enum):
    CLEAR = "CLEAR"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


class GmoRuntimeMarketSafeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class GmoRuntimeTickerFreshnessSafeStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class GmoRuntimeSpreadSafeStatus(str, Enum):
    WITHIN_LIMIT = "WITHIN_LIMIT"
    OUT_OF_LIMIT = "OUT_OF_LIMIT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GmoRuntimeSafeReadSnapshot:
    """Safe-status/safe-count snapshot only. Never raw payload or IDs."""

    performed: bool = False
    fresh: bool = False
    position_status: GmoRuntimePositionSafeStatus = (
        GmoRuntimePositionSafeStatus.UNKNOWN
    )
    position_count_safe: int | None = None
    active_pending_status: GmoRuntimeActivePendingSafeStatus = (
        GmoRuntimeActivePendingSafeStatus.UNKNOWN
    )
    active_order_count_safe: int | None = None
    market_status: GmoRuntimeMarketSafeStatus = GmoRuntimeMarketSafeStatus.UNKNOWN
    ticker_status: GmoRuntimeTickerFreshnessSafeStatus = (
        GmoRuntimeTickerFreshnessSafeStatus.UNKNOWN
    )
    spread_status: GmoRuntimeSpreadSafeStatus = GmoRuntimeSpreadSafeStatus.UNKNOWN

    def __bool__(self) -> bool:
        return False


class GmoRuntimeSafeReadClient(Protocol):
    """A read-only client that returns only a safe-status/safe-count snapshot."""

    def read_safe_snapshot(self) -> GmoRuntimeSafeReadSnapshot:
        """Return the safe snapshot. Never a raw payload, ID, or broker value."""


@dataclass(frozen=True)
class FakeRuntimeSafeReadClient:
    """Test-only client. Its fields are safe statuses/counts by construction."""

    snapshot: GmoRuntimeSafeReadSnapshot = GmoRuntimeSafeReadSnapshot()

    def read_safe_snapshot(self) -> GmoRuntimeSafeReadSnapshot:
        return self.snapshot


class GmoRuntimeSafeReadGateStatus(str, Enum):
    RUNTIME_SAFE_READ_GATE_READY_NO_POSITION_CLEAR = (
        "RUNTIME_SAFE_READ_GATE_READY_NO_POSITION_CLEAR"
    )
    RUNTIME_SAFE_READ_GATE_BLOCKED = "RUNTIME_SAFE_READ_GATE_BLOCKED"


@dataclass(frozen=True)
class GmoRuntimeSafeReadGateResult:
    ready: bool
    status: GmoRuntimeSafeReadGateStatus
    blocked_reasons: tuple[str, ...]
    snapshot: GmoRuntimeSafeReadSnapshot

    def __bool__(self) -> bool:
        return False


def evaluate_gmo_runtime_safe_read_gate(
    snapshot: GmoRuntimeSafeReadSnapshot,
) -> GmoRuntimeSafeReadGateResult:
    """Fail-closed gate: pass only when the snapshot is fully safe and clear."""

    blockers: list[str] = []
    if not snapshot.performed:
        blockers.append("RUNTIME_SAFE_READ_NOT_PERFORMED")
    if not snapshot.fresh:
        blockers.append("RUNTIME_SAFE_READ_STALE")
    if snapshot.position_status is not GmoRuntimePositionSafeStatus.NO_POSITION:
        blockers.append("RUNTIME_POSITION_STATUS_NOT_NO_POSITION")
    if snapshot.position_count_safe != 0:
        blockers.append("RUNTIME_POSITION_COUNT_NOT_ZERO")
    if (
        snapshot.active_pending_status
        is not GmoRuntimeActivePendingSafeStatus.CLEAR
    ):
        blockers.append("RUNTIME_ACTIVE_PENDING_NOT_CLEAR")
    if snapshot.active_order_count_safe != 0:
        blockers.append("RUNTIME_ACTIVE_ORDER_COUNT_NOT_ZERO")
    if snapshot.market_status is not GmoRuntimeMarketSafeStatus.OPEN:
        blockers.append("RUNTIME_MARKET_NOT_OPEN")
    if snapshot.ticker_status is not GmoRuntimeTickerFreshnessSafeStatus.FRESH:
        blockers.append("RUNTIME_TICKER_NOT_FRESH")
    if snapshot.spread_status is not GmoRuntimeSpreadSafeStatus.WITHIN_LIMIT:
        blockers.append("RUNTIME_SPREAD_NOT_WITHIN_LIMIT")

    ready = not blockers
    return GmoRuntimeSafeReadGateResult(
        ready=ready,
        status=(
            GmoRuntimeSafeReadGateStatus.RUNTIME_SAFE_READ_GATE_READY_NO_POSITION_CLEAR
            if ready
            else GmoRuntimeSafeReadGateStatus.RUNTIME_SAFE_READ_GATE_BLOCKED
        ),
        blocked_reasons=tuple(blockers),
        snapshot=snapshot,
    )
