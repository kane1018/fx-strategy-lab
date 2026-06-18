"""Local shadow-session runner: candles -> SignalFn -> ShadowTrader -> log + summary.

Pure/local: takes an already-fetched candle series, runs no-order shadow steps, writes
events.jsonl + summary.json + metadata.json under <out_root>/<run_id>/, and returns the
summary dict. No network here (the caller fetches candles), no orders, no Private API,
no secret. Output dirs (shadow_exports/) are gitignored and must never be committed.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.shadow.models import Candle, Ticker, shadow_safety
from app.shadow.service import ShadowTrader, SignalFn
from app.shadow.signals import momentum_signal


def make_mock_candles(count: int, *, start: float = 150.0, step: float = 0.1) -> list[Candle]:
    """Deterministic zig-zag candles for offline/mock shadow runs (no network)."""
    candles: list[Candle] = []
    price = start
    for i in range(count):
        delta = step if i % 2 == 0 else -step
        open_ = price
        close = round(price + delta, 5)
        candles.append(
            Candle(
                time=f"t{i:04d}",
                open=open_,
                high=round(max(open_, close) + 0.05, 5),
                low=round(min(open_, close) - 0.05, 5),
                close=close,
            )
        )
        price = close
    return candles


def _ticker_from_candle(symbol: str, candle: Candle) -> Ticker:
    # Shadow uses the candle close as both bid/ask (zero synthetic spread) for fill/PnL.
    return Ticker(symbol=symbol, bid=candle.close, ask=candle.close, time=candle.time)


def run_shadow_session(
    *,
    symbol: str,
    interval: str,
    source: str,
    candles: list[Candle],
    out_root: str | Path,
    steps: int,
    run_id: str | None = None,
    units: int = 1,
    max_units: int = 100,
    signal_fn: SignalFn = momentum_signal,
) -> dict:
    """Run a bounded, no-order shadow session and persist events + summary. Returns summary."""
    created_at = datetime.now(UTC).isoformat()
    run_id = run_id or (
        f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_shadow_{symbol}_{source}"
    )
    steps_requested = steps
    usable = candles[: max(0, steps)]
    trader = ShadowTrader(symbol, signal_fn, units=units, max_units=max_units)

    run_dir = Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    buy = sell = flat = 0
    orders = 0
    max_abs_units = 0
    last_price = None
    event_rows: list[dict] = []

    for i in range(len(usable)):
        candle = usable[i]
        ticker = _ticker_from_candle(symbol, candle)
        event = trader.step(usable[: i + 1], ticker)
        last_price = candle.close
        if event.signal.side == "buy":
            buy += 1
        elif event.signal.side == "sell":
            sell += 1
        else:
            flat += 1
        if event.virtual_order is not None:
            orders += 1
        max_abs_units = max(max_abs_units, event.position_units)
        row = {
            "run_id": run_id,
            "source": source,
            "interval": interval,
            **asdict(event),
        }
        event_rows.append(row)

    with (run_dir / "events.jsonl").open("w") as fh:
        for row in event_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "run_id": run_id,
        "source": source,
        "symbol": symbol,
        "interval": interval,
        "steps_requested": steps_requested,
        "steps_executed": len(usable),
        "events_count": len(event_rows),
        "virtual_orders_count": orders,
        "buy_count": buy,
        "sell_count": sell,
        "flat_count": flat,
        "max_abs_units": max_abs_units,
        "final_position_side": trader.position.side,
        "final_position_units": trader.position.units,
        "final_average_price": trader.position.avg_price,
        "final_unrealized_pnl": (
            trader.position.unrealized_pnl(last_price) if last_price is not None else 0.0
        ),
        "last_price": last_price,
        "data_points": len(candles),
        "halted": trader.halted,
        "halt_reason": trader.halt_reason,
        "safety": shadow_safety(),
        "created_at": created_at,
    }
    with (run_dir / "summary.json").open("w") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    metadata = {
        "run_id": run_id,
        "source": source,
        "symbol": symbol,
        "interval": interval,
        "steps_requested": steps_requested,
        "units": units,
        "max_units": max_units,
        "signal": "momentum_signal (demo only; NOT a profitability claim)",
        "created_at": created_at,
        "safety": shadow_safety(),
        "note": "Local shadow run. No real order / Private API / API key. Do not commit outputs.",
    }
    with (run_dir / "metadata.json").open("w") as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=2)

    return summary
