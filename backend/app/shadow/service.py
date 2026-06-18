"""Shadow-trading step service (local-only, no I/O, no orders).

Given candles + a current ticker + a signal function, builds a VIRTUAL order (never
sent), updates the virtual position, computes virtual PnL, runs a safety check, and
returns a ShadowEvent. There is no broker call and no order-send path anywhere here.
"""

from __future__ import annotations

from collections.abc import Callable

from app.shadow.models import (
    Candle,
    ShadowEvent,
    Signal,
    Ticker,
    VirtualOrder,
    VirtualPosition,
    shadow_safety,
)

# A strategy function: decide an action from the recent candles. Pure, no I/O.
SignalFn = Callable[[list[Candle]], Signal]


class ShadowTrader:
    """Drives no-order shadow steps over a single symbol's virtual position."""

    def __init__(self, symbol: str, signal_fn: SignalFn, *, units: int = 1, max_units: int = 100):
        self.symbol = symbol
        self.signal_fn = signal_fn
        self.units = units
        self.max_units = max_units
        self.position = VirtualPosition(symbol=symbol)
        self.events: list[ShadowEvent] = []
        self.halted = False
        self.halt_reason = ""

    def step(self, candles: list[Candle], ticker: Ticker) -> ShadowEvent:
        """Run one shadow step. Never sends an order; only mutates the virtual position."""
        signal = self.signal_fn(candles)
        order: VirtualOrder | None = None
        halt_reason = self.halt_reason

        if not self.halted and signal.side in ("buy", "sell"):
            # Safety check BEFORE applying a (virtual) fill.
            if self.units > self.max_units:
                self.halted = True
                halt_reason = f"requested units {self.units} exceed max_units {self.max_units}"
                self.halt_reason = halt_reason
            else:
                order = VirtualOrder(side=signal.side, units=self.units, price=ticker.ask)
                self.position.apply_fill(order)

        pnl = self.position.unrealized_pnl(ticker.mid)
        event = ShadowEvent(
            time=ticker.time,
            symbol=self.symbol,
            signal=signal,
            virtual_order=order,
            position_side=self.position.side,
            position_units=self.position.units,
            position_avg_price=self.position.avg_price,
            virtual_pnl=pnl,
            halted=self.halted,
            halt_reason=halt_reason,
            safety=shadow_safety(),
        )
        self.events.append(event)
        return event
