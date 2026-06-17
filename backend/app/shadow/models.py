"""Internal shadow-trading domain models (local-only, no I/O).

Plain dataclasses for normalized market data and virtual (never-sent) trading objects.
A VirtualOrder is structurally incapable of being a real order: there is no send method
anywhere in this package, and `real_order` is asserted False at construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Side = Literal["buy", "sell"]
PositionSide = Literal["long", "short", "flat"]


def shadow_safety() -> dict[str, bool]:
    """Read-only / no-order safety flags asserted by every shadow event.

    Mirrors the read-only contract used elsewhere (scripts.fx_eval_common.safety_metadata)
    plus an explicit no-live-trading flag. Shadow trading never sends orders, never uses a
    Private API, and never needs an API key / secret / .env.
    """
    return {
        "real_order": False,
        "private_api_used": False,
        "api_key_used": False,
        "no_order_execution": True,
        "live_trading_environment_enabled": False,
        "gmo_readonly": True,
        "gmo_order_enabled": False,
    }


@dataclass(frozen=True)
class Candle:
    """Normalized OHLC candle (internal format)."""

    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


@dataclass(frozen=True)
class Ticker:
    """Normalized ticker (internal format)."""

    symbol: str
    bid: float
    ask: float
    time: str

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2


@dataclass(frozen=True)
class Signal:
    """Strategy decision for one step. 'flat' means no action."""

    side: Literal["buy", "sell", "flat"]
    reason: str = ""


@dataclass(frozen=True)
class VirtualOrder:
    """A simulated order that is NEVER sent to any broker.

    `real_order` must be False; constructing with True raises, so this object cannot be
    repurposed as a live order. There is intentionally no submit/send method.
    """

    side: Side
    units: int
    price: float
    real_order: bool = False

    def __post_init__(self) -> None:
        if self.real_order:
            raise ValueError("VirtualOrder.real_order must be False (shadow trading only)")
        if self.units <= 0:
            raise ValueError("VirtualOrder.units must be positive")


@dataclass
class VirtualPosition:
    """In-memory virtual position. Updated only by simulated fills."""

    symbol: str
    side: PositionSide = "flat"
    units: int = 0
    avg_price: float = 0.0

    def apply_fill(self, order: VirtualOrder) -> None:
        """Apply a virtual fill (no broker call). Minimal long/short/flat bookkeeping."""
        signed = order.units if order.side == "buy" else -order.units
        current = self.units if self.side == "long" else -self.units if self.side == "short" else 0
        net = current + signed
        if current != 0 and (current > 0) == (signed > 0):
            # same direction: weighted-average the entry price
            total = abs(current) + abs(signed)
            self.avg_price = (self.avg_price * abs(current) + order.price * abs(signed)) / total
        elif current == 0 or (current > 0) != (signed > 0):
            # opening or flipping: new average is the fill price when direction changes
            if net == 0:
                self.avg_price = 0.0
            elif (net > 0) != (current > 0) or current == 0:
                self.avg_price = order.price
        self.units = abs(net)
        self.side = "long" if net > 0 else "short" if net < 0 else "flat"
        if self.side == "flat":
            self.avg_price = 0.0

    def unrealized_pnl(self, price: float) -> float:
        """Virtual unrealized PnL at `price` (units * price diff; sign by side)."""
        if self.side == "long":
            return (price - self.avg_price) * self.units
        if self.side == "short":
            return (self.avg_price - price) * self.units
        return 0.0


@dataclass(frozen=True)
class ShadowEvent:
    """One shadow step result: signal, optional virtual order, position snapshot, PnL."""

    time: str
    symbol: str
    signal: Signal
    virtual_order: VirtualOrder | None
    position_side: PositionSide
    position_units: int
    position_avg_price: float
    virtual_pnl: float
    halted: bool
    halt_reason: str
    safety: dict[str, bool] = field(default_factory=shadow_safety)
