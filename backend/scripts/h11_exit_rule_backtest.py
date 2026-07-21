"""Compare exit rules for the H-11 SHORT_V1 30m signal on historical M1 data.

Read-only ANALYSIS tooling: no broker access of any kind, no coordinator or
ledger interaction, no reviewed-file impact. It replays the frozen production
signal (same artifact, same features, same thresholds) over cached public M1
history and simulates ALTERNATIVE EXIT RULES on identical entries, so the
operator can compare their statistics side by side. It outputs facts only; rule
selection remains an operator decision.

Simplifications (stated, deliberate):
- Entry at the signal bar's BID close; a fixed 0.5-pip round-trip spread cost is
  subtracted from every trade (production gates spread at <=0.5 pips).
- One position per rule at a time (a signal during an open position is skipped);
  the production 1-entry-per-day cap is NOT applied, to keep sample sizes usable.
- SL/TP touch detection uses M1 highs/lows; if both are touched inside the same
  minute the STOP is assumed to fill first (conservative).
- JST hours 05-08 and weekends are excluded, mirroring the production policy.
- In-sample (before the artifact's 2026-07-01 development cutoff) and
  out-of-sample windows are reported separately; only out-of-sample rows are
  honest estimates of live behaviour.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.h11_manual.contracts import Horizon
from app.h11_manual.short_model import (
    ShortModelArtifact,
    compute_short_features,
    predict_short_model,
)

REPOSITORY = Path(__file__).resolve().parents[2]
CACHE_CSV = REPOSITORY / "backend" / "market_data" / "backtest" / "usdjpy_m1_history.csv"
MANUAL_CSV = REPOSITORY / "backend" / "market_data" / "h11_manual" / "usdjpy_m1_bid.csv"
ARTIFACT = REPOSITORY / "backend" / "market_data" / "h11_manual" / "short_model_artifact.json"

BUY_THRESHOLD = 0.58
SELL_THRESHOLD = 0.42
SPREAD_PIPS = 0.5
PIP = 0.01
UNITS = 1_000
YEN_PER_PIP = UNITS * PIP  # 10 JPY per pip at 1,000 units


@dataclass(frozen=True)
class ExitRule:
    name: str
    stop_atr_multiple: float | None  # None = no stop
    take_profit_r_multiple: float | None  # in R (multiples of the stop distance)
    timeout_minutes: int


RULES = (
    ExitRule("現行 1.5ATR/1.5R/23h", 1.5, 1.5, 23 * 60),
    ExitRule("30分固定(SLTPなし)", None, None, 30),
    ExitRule("2時間固定(SLTPなし)", None, None, 120),
    ExitRule("30分+現行SLTP", 1.5, 1.5, 30),
    ExitRule("4時間+現行SLTP", 1.5, 1.5, 240),
    ExitRule("SL1.0ATR/1.5R/23h", 1.0, 1.5, 23 * 60),
    ExitRule("SL2.0ATR/1.5R/23h", 2.0, 1.5, 23 * 60),
)


def _load_frame() -> pd.DataFrame:
    frames = []
    for path in (CACHE_CSV, MANUAL_CSV):
        if path.is_file():
            frames.append(pd.read_csv(path))
    if not frames:
        raise SystemExit("no M1 data found; run h11_exit_rule_backtest_fetch first")
    frame = pd.concat(frames, ignore_index=True)
    frame["time_utc"] = pd.to_datetime(frame["time_utc"], utc=True)
    frame = (
        frame.dropna()
        .drop_duplicates(subset="time_utc", keep="first")
        .sort_values("time_utc")
        .reset_index(drop=True)
    )
    frame["time_utc"] = frame["time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return frame


def _vectorized_probabilities(artifact, frame: pd.DataFrame) -> np.ndarray:
    features = compute_short_features(frame)
    matrix = features.to_numpy(dtype=float)
    mean = np.asarray(artifact.feature_mean)
    scale = np.asarray(artifact.feature_scale)
    normalized = (matrix - mean) / scale
    weights = np.asarray(artifact.weights_30m)
    logits = normalized @ weights[:-1] + weights[-1]
    with np.errstate(over="ignore"):
        probabilities = 1.0 / (1.0 + np.exp(-logits))
    probabilities[~np.isfinite(matrix).all(axis=1)] = np.nan
    return probabilities


def _verify_vectorization(artifact, frame: pd.DataFrame, probabilities: np.ndarray) -> None:
    finite = np.flatnonzero(np.isfinite(probabilities))
    sample = finite[:: max(1, len(finite) // 5)][:5]
    for row in sample:
        reference = predict_short_model(artifact, frame, int(row), Horizon.MINUTES_30)
        if not math.isclose(reference, float(probabilities[row]), abs_tol=1e-9):
            raise SystemExit("vectorized probabilities diverge from predict_short_model")


def _hourly_atr24(frame: pd.DataFrame) -> np.ndarray:
    times = pd.to_datetime(frame["time_utc"], utc=True)
    hour_key = times.dt.floor("h")
    grouped = frame.groupby(hour_key)
    hourly = grouped.agg(
        high=("high", "max"), low=("low", "min"), close=("close", "last"), count=("close", "size")
    )
    complete = hourly[hourly["count"] >= 55]
    previous_close = complete["close"].shift(1)
    true_range = pd.concat(
        [
            complete["high"] - complete["low"],
            (complete["high"] - previous_close).abs(),
            (complete["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.rolling(24, min_periods=24).mean()
    # ATR known at the END of each completed hour -> applies to the NEXT hour's bars.
    atr_by_next_hour = {hour + pd.Timedelta(hours=1): value for hour, value in atr.items()}
    return np.array(
        [atr_by_next_hour.get(hour, np.nan) for hour in hour_key], dtype=float
    )


def _signal_rows(
    frame: pd.DataFrame, probabilities: np.ndarray, atr: np.ndarray
) -> list[tuple[int, str]]:
    times = pd.to_datetime(frame["time_utc"], utc=True)
    jst_hour = (times.dt.hour + 9) % 24
    jst_weekday = (times + pd.Timedelta(hours=9)).dt.weekday
    eligible = (
        (times.dt.minute % 30 == 0)
        & np.isfinite(probabilities)
        & np.isfinite(atr)
        & (~jst_hour.isin((5, 6, 7, 8)))
        & (jst_weekday <= 4)
    )
    rows: list[tuple[int, str]] = []
    for row in np.flatnonzero(eligible.to_numpy()):
        p = probabilities[row]
        if p >= BUY_THRESHOLD:
            rows.append((int(row), "BUY"))
        elif p <= SELL_THRESHOLD:
            rows.append((int(row), "SELL"))
    return rows


def _simulate(
    rule: ExitRule,
    signals: list[tuple[int, str]],
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    atr: np.ndarray,
    minutes_index: np.ndarray,
) -> list[tuple[int, float, int]]:
    """Return (entry_row, net_pips, hold_minutes) per executed trade."""

    trades: list[tuple[int, float, int]] = []
    busy_until = -1
    total = len(close)
    for row, side in signals:
        if row <= busy_until:
            continue
        entry = close[row]
        direction = 1.0 if side == "BUY" else -1.0
        stop = None
        target = None
        if rule.stop_atr_multiple is not None:
            distance = rule.stop_atr_multiple * atr[row]
            stop = entry - direction * distance
            target = entry + direction * distance * rule.take_profit_r_multiple
        deadline_minute = minutes_index[row] + rule.timeout_minutes
        exit_pips = None
        exit_row = row
        for later in range(row + 1, total):
            if minutes_index[later] > deadline_minute:
                exit_pips = direction * (close[later - 1] - entry) / PIP
                exit_row = later - 1
                break
            if stop is not None:
                stop_hit = low[later] <= stop if direction > 0 else high[later] >= stop
                if stop_hit:
                    exit_pips = direction * (stop - entry) / PIP
                    exit_row = later
                    break
                target_hit = (
                    high[later] >= target if direction > 0 else low[later] <= target
                )
                if target_hit:
                    exit_pips = direction * (target - entry) / PIP
                    exit_row = later
                    break
        if exit_pips is None:
            continue  # ran off the end of data
        trades.append(
            (
                row,
                exit_pips - SPREAD_PIPS,
                int(minutes_index[exit_row] - minutes_index[row]),
            )
        )
        busy_until = exit_row
    return trades


def _summarize(trades: list[tuple[int, float, int]]) -> dict[str, float]:
    if not trades:
        return {"n": 0}
    pips = np.array([t[1] for t in trades])
    holds = np.array([t[2] for t in trades])
    equity = np.cumsum(pips * YEN_PER_PIP)
    drawdown = float(np.min(equity - np.maximum.accumulate(equity)))
    return {
        "n": len(trades),
        "win%": 100.0 * float(np.mean(pips > 0)),
        "avg_pips": float(np.mean(pips)),
        "total_yen": float(np.sum(pips) * YEN_PER_PIP),
        "max_dd_yen": drawdown,
        "avg_hold_min": float(np.mean(holds)),
    }


def main() -> int:
    frame = _load_frame()
    artifact = ShortModelArtifact.load(ARTIFACT)
    probabilities = _vectorized_probabilities(artifact, frame)
    _verify_vectorization(artifact, frame, probabilities)
    atr = _hourly_atr24(frame)
    times = pd.to_datetime(frame["time_utc"], utc=True)
    minutes_index = (times.astype("int64") // 60_000_000_000).to_numpy()
    close = frame["close"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    signals = _signal_rows(frame, probabilities, atr)
    cutoff = pd.Timestamp(artifact.development_cutoff_utc)
    out_of_sample_start = int((times < cutoff).sum())

    print(
        f"データ: {frame['time_utc'].iloc[0]} 〜 {frame['time_utc'].iloc[-1]}"
        f"  ({len(frame):,} bars)"
    )
    print(f"signal候補slot数: {len(signals)}  (BUY/SELL閾値 {BUY_THRESHOLD}/{SELL_THRESHOLD})")
    print(f"out-of-sample境界(学習カットオフ): {cutoff.isoformat()}")
    print()
    for window_name, selector in (
        ("in-sample(学習期間・参考値)", lambda r: r < out_of_sample_start),
        ("out-of-sample(実力推定)", lambda r: r >= out_of_sample_start),
    ):
        window_signals = [s for s in signals if selector(s[0])]
        print(f"== {window_name}: signal {len(window_signals)}件 ==")
        print(
            f"{'規則':<24} {'件数':>4} {'勝率':>6} {'平均pips':>9}"
            f" {'合計円':>9} {'最大DD円':>9} {'平均保有分':>7}"
        )
        for rule in RULES:
            trades = _simulate(rule, window_signals, close, high, low, atr, minutes_index)
            s = _summarize(trades)
            if s["n"] == 0:
                print(f"{rule.name:<24} {0:>4}")
                continue
            print(
                f"{rule.name:<24} {s['n']:>4} {s['win%']:>5.1f}% {s['avg_pips']:>9.2f}"
                f" {s['total_yen']:>9.0f} {s['max_dd_yen']:>9.0f} {s['avg_hold_min']:>7.0f}"
            )
        print()
    print("注意: スプレッド0.5pips/往復を控除済み。1日1回制限は未適用。")
    print("      同一分内でSL/TP両到達はSL優先(保守側)。滑り・約定拒否は未考慮。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
