"""Minimal demo SignalFn for shadow runs (NOT for profitability).

`momentum_signal` exists only to exercise the shadow run flow (signal -> virtual order ->
position -> PnL -> log). It is intentionally trivial and must not be read as a trading
edge. No parameter tuning / strategy research here.
"""

from __future__ import annotations

from app.shadow.models import Candle, Signal


def momentum_signal(candles: list[Candle]) -> Signal:
    """buy if last close > previous close, sell if <, flat if == / too little history.

    Demo only — not a profitability claim.
    """
    if len(candles) < 2:
        return Signal(side="flat", reason="insufficient history")
    prev_close = candles[-2].close
    last_close = candles[-1].close
    if last_close > prev_close:
        return Signal(side="buy", reason="close up vs previous")
    if last_close < prev_close:
        return Signal(side="sell", reason="close down vs previous")
    return Signal(side="flat", reason="close unchanged")
