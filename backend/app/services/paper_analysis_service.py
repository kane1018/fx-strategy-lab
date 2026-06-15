"""Read-only post-hoc analysis of paper trades.

Decomposes completed paper trades by time-of-day, market regime (ADX / ATR /
MA-slope / range), and holding time, and summarizes streak / tail risk. Pure
pandas/numpy; this module performs NO broker, order, or network I/O (the CLI
fetches candles read-only and passes them in). Indicators are used only to
*classify the regime* of each trade, never as trade signals.

Reuses the completed-trade statistics from performance_service so win rate /
expectancy / PF / max drawdown are computed identically everywhere.
"""

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from app.services.market_data_service import pip_size
from app.services.performance_service import _trade_stats

# Session time buckets in UTC (approximate; FX day opens ~21:00 UTC).
TIME_BUCKETS = {
    "early_morning": "21:00-23:59 UTC (Sydney open, thin liquidity / wide spread)",
    "tokyo": "00:00-07:59 UTC",
    "london": "08:00-12:59 UTC",
    "new_york": "13:00-20:59 UTC",
}
ADX_BANDS = [(0, 15), (15, 20), (20, 25), (25, 30), (30, 1_000)]


def time_bucket(dt: datetime) -> str:
    hour = dt.hour
    if 21 <= hour <= 23:
        return "early_morning"
    if 0 <= hour < 8:
        return "tokyo"
    if 8 <= hour < 13:
        return "london"
    return "new_york"


def holding_minutes(opened_at: datetime, closed_at: datetime) -> float:
    return max(0.0, (closed_at - opened_at).total_seconds() / 60.0)


def holding_bucket(minutes: float) -> str:
    if minutes < 5:
        return "<5min"
    if minutes < 15:
        return "5-15min"
    if minutes < 30:
        return "15-30min"
    if minutes < 60:
        return "30-60min"
    return "60min+"


def adx_bucket(adx: float | None) -> str:
    if adx is None or np.isnan(adx):
        return "unknown"
    for low, high in ADX_BANDS:
        if low <= adx < high:
            return f"ADX{low}-{high}" if high < 1_000 else "ADX30+"
    return "ADX30+"


def _tertiles(values: list[float]) -> tuple[float, float]:
    clean = [v for v in values if v is not None and not np.isnan(v)]
    if len(clean) < 3:
        return (0.0, 0.0)
    return (float(np.quantile(clean, 1 / 3)), float(np.quantile(clean, 2 / 3)))


def tertile_bucket(value: float | None, low: float, high: float) -> str:
    if value is None or np.isnan(value):
        return "unknown"
    if value <= low:
        return "low"
    if value <= high:
        return "mid"
    return "high"


def _wilder(series: pd.Series, period: int = 14) -> pd.Series:
    return series.ewm(alpha=1 / period, adjust=False).mean()


def compute_indicators(frame: pd.DataFrame, pip: float) -> pd.DataFrame:
    """Return per-bar regime indicators (ADX, ATR in pips, MA slope in pips, range in pips)."""
    high, low, close = frame["high"], frame["low"], frame["close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = _wilder(true_range)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=frame.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=frame.index
    )
    atr_di = _wilder(true_range).replace(0, np.nan)
    plus_di = 100 * _wilder(plus_dm) / atr_di
    minus_di = 100 * _wilder(minus_dm) / atr_di
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = _wilder(dx.fillna(0))
    sma = close.rolling(30).mean()
    return pd.DataFrame(
        {
            "timestamp": frame["timestamp"],
            "adx": adx,
            "atr_pips": atr / pip,
            "ma_slope_pips": (sma - sma.shift(10)) / pip,
            "range_pips": (high.rolling(20).max() - low.rolling(20).min()) / pip,
        }
    )


def indicator_lookup(frame: pd.DataFrame, symbol: str) -> dict[datetime, dict[str, float]]:
    indicators = compute_indicators(frame, pip_size(symbol))
    out: dict[datetime, dict[str, float]] = {}
    for _, row in indicators.iterrows():
        out[pd.Timestamp(row["timestamp"]).to_pydatetime().replace(tzinfo=None)] = {
            "adx": float(row["adx"]),
            "atr_pips": float(row["atr_pips"]),
            "ma_slope_pips": float(row["ma_slope_pips"]),
            "range_pips": float(row["range_pips"]),
        }
    return out


def ma_slope_class(slope_pips: float | None, flat_threshold: float) -> str:
    if slope_pips is None or np.isnan(slope_pips):
        return "unknown"
    if abs(slope_pips) <= flat_threshold:
        return "flat"
    return "uptrend" if slope_pips > 0 else "downtrend"


def enrich_trades(
    trades: list[dict[str, Any]],
    lookups: dict[str, dict[datetime, dict[str, float]]],
) -> list[dict[str, Any]]:
    """Attach time/holding/regime buckets to each trade dict (in place copies returned)."""
    enriched: list[dict[str, Any]] = []
    for trade in trades:
        regime = lookups.get(trade["symbol"], {}).get(_naive(trade["opened_at"]), {})
        minutes = holding_minutes(trade["opened_at"], trade["closed_at"])
        enriched.append(
            {
                **trade,
                "time_bucket": time_bucket(trade["opened_at"]),
                "holding_min": minutes,
                "holding_bucket": holding_bucket(minutes),
                "adx": regime.get("adx", float("nan")),
                "atr_pips": regime.get("atr_pips", float("nan")),
                "ma_slope_pips": regime.get("ma_slope_pips", float("nan")),
                "range_pips": regime.get("range_pips", float("nan")),
            }
        )
    # data-driven tertile thresholds (avoid arbitrary fixed cutoffs / overfitting)
    atr_low, atr_high = _tertiles([t["atr_pips"] for t in enriched])
    range_low, range_high = _tertiles([t["range_pips"] for t in enriched])
    flat_threshold, _ = _tertiles([abs(t["ma_slope_pips"]) for t in enriched])
    for trade in enriched:
        trade["adx_bucket"] = adx_bucket(trade["adx"])
        trade["atr_bucket"] = tertile_bucket(trade["atr_pips"], atr_low, atr_high)
        trade["range_bucket"] = tertile_bucket(trade["range_pips"], range_low, range_high)
        trade["ma_slope_class"] = ma_slope_class(trade["ma_slope_pips"], flat_threshold)
    return enriched


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


def aggregate(trades: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[float]] = {}
    for trade in trades:
        groups.setdefault(str(trade[key]), []).append(float(trade["pnl"]))
    return {name: _trade_stats(pnls) for name, pnls in sorted(groups.items())}


def aggregate_pair(
    trades: list[dict[str, Any]], key_a: str, key_b: str
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[float]] = {}
    for trade in trades:
        groups.setdefault(f"{trade[key_a]}|{trade[key_b]}", []).append(float(trade["pnl"]))
    return {name: _trade_stats(pnls) for name, pnls in sorted(groups.items())}


def streak_and_tail(trades: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(trades, key=lambda t: t["closed_at"])
    max_loss_streak = max_win_streak = cur_loss = cur_win = 0
    for trade in ordered:
        pnl = trade["pnl"]
        if pnl < 0:
            cur_loss, cur_win = cur_loss + 1, 0
        elif pnl > 0:
            cur_win, cur_loss = cur_win + 1, 0
        else:
            cur_loss = cur_win = 0
        max_loss_streak = max(max_loss_streak, cur_loss)
        max_win_streak = max(max_win_streak, cur_win)
    losers = sorted((t for t in trades if t["pnl"] < 0), key=lambda t: t["pnl"])[:5]
    winners = sorted((t for t in trades if t["pnl"] > 0), key=lambda t: -t["pnl"])[:5]

    def _ctx(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "pnl": round(r["pnl"], 4),
                "symbol": r["symbol"],
                "strategy": r["strategy"],
                "time_bucket": r["time_bucket"],
                "adx_bucket": r.get("adx_bucket"),
                "holding_bucket": r["holding_bucket"],
            }
            for r in rows
        ]

    return {
        "max_consecutive_losses": max_loss_streak,
        "max_consecutive_wins": max_win_streak,
        "max_single_loss": round(min((t["pnl"] for t in trades), default=0.0), 4),
        "max_single_win": round(max((t["pnl"] for t in trades), default=0.0), 4),
        "top5_losses": _ctx(losers),
        "top5_wins": _ctx(winners),
    }
