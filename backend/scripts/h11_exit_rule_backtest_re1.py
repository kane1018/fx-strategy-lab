"""H-11 R-E1 exit-policy research harness (Phase A1 + Stage 1 of A2).

Read-only ANALYSIS tooling: no broker access of any kind, no coordinator or
ledger interaction, no reviewed-file impact. Replays the frozen production
signal (same artifact, same features, same thresholds) exactly as
``h11_exit_rule_backtest.py`` does, and compares the R-E1 candidate registry
(design doc: docs/H11_V4_EXIT_POLICY_RE1_DESIGN_20260725.md) against it.

Scope of THIS script (explicitly, so nothing here is mistaken for more than
it is):
- A0 (no SL/TP, 30m timeout) and PROD-G014-REPLAY (1.5ATR/1.5R/23h, i.e. the
  live-frozen exit profile prior to the 2026-07-27 30m re-freeze) reproduced
  as regression checks against the pre-existing h11_exit_rule_backtest.py
  output -- PROD-G014-REPLAY is excluded from the FDR candidate pool
  (design doc Sec 3.1) since it is a 23h-hold regression check, not a
  30m-horizon candidate.
- The A1 3x3 common_R grid (9 candidates), common_R shared and clamped
  per design doc Sec 2 (this fixes the v1 bug: SL multiple no longer
  changes the realized TP distance).
- Cost models C0/C1/C1b/C2/C3/C5 (Sec 6) applied post-hoc to the same
  simulated trades (cost never changes touch order/exit price, only P&L).
- Cost-durability classification (Robust/Fragile/Reject; "Deployable"
  needs a B2 real spread distribution and is not computed here).
- Stage 1 selection: paired daily bootstrap (Sec 7) of each A1 candidate
  vs A0, then Benjamini-Hochberg FDR (q=0.10) across the 9 candidates.
- A run manifest (Sec 11) with git commit, input hashes, and the fixed
  bootstrap seed.

NOT in scope here (left for a follow-up run, per the design doc's own
Phase table): A2 (reversal exits), A3 (TR-spike), Stage 2/3, Layer2
(production concurrency/entries-per-day/loss-limit simulation), and the
BID_ASK_M1 price-face mode (falls back to LEGACY_BID_ONLY automatically
if the ASK cache does not yet cover the full BID window; this is reported
explicitly in the output, never silently substituted).
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
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
ASK_CACHE_CSV = (
    REPOSITORY / "backend" / "market_data" / "backtest" / "usdjpy_m1_history_ask.csv"
)
MANUAL_CSV = REPOSITORY / "backend" / "market_data" / "h11_manual" / "usdjpy_m1_bid.csv"
ARTIFACT = REPOSITORY / "backend" / "market_data" / "h11_manual" / "short_model_artifact.json"

BUY_THRESHOLD = 0.58
SELL_THRESHOLD = 0.42
PIP = 0.01
UNITS = 1_000
YEN_PER_PIP = UNITS * PIP  # 10 JPY per pip at 1,000 units
TICK_SIZE = 0.001  # GMO USD/JPY tick size (design doc Sec 2)

# --- common_R (design doc Sec 2, fixed, not a tuning target) ---------------
FIXED_ATR_MULTIPLIER = 1.0
COMMON_R_MIN_STOP_PIPS = 3.0
COMMON_R_MAX_STOP_PIPS = 20.0
SL_R_VALUES = (0.8, 1.0, 1.2)
TP_R_VALUES = (1.0, 1.5, 2.0)
COMMON_R_FLOOR_PIPS = COMMON_R_MIN_STOP_PIPS / min(SL_R_VALUES)
COMMON_R_CAP_PIPS = COMMON_R_MAX_STOP_PIPS / max(SL_R_VALUES)
A1_MAX_HOLD_MINUTES = 30

# --- cost models (design doc Sec 6) ----------------------------------------
# LEGACY_BID_ONLY: prices are BID on both legs, so the whole round-trip cost
# must be subtracted explicitly here.
COST_MODELS = {
    "C0": 0.0,
    "C1": 0.5,
    "C1b": 1.0,
    "C2": 1.5,
    "C3": 2.0,
}
# BID_ASK_M1: the spread is ALREADY realized in the entry/exit prices
# (BUY enters at ASK and exits at BID; SELL the reverse), so subtracting a
# fixed spread on top would double-count it -- explicitly forbidden by the
# design doc Sec 6. Only slippage-style extras may be added in this mode.
SLIPPAGE_MODELS = {
    "S0": 0.0,
    "S1": 0.1,
    "S2": 0.3,
}
C5_STRESS_HOURS_JST = frozenset({21, 22, 23, 5, 6, 7, 8})
C5_EXTRA_PIPS = 0.5

BOOTSTRAP_SEED = 20260725
BOOTSTRAP_RESAMPLES = 5_000
BOOTSTRAP_EXPECTED_BLOCK_LENGTH_DAYS = 5.0
FDR_Q = 0.10


@dataclass(frozen=True)
class A1Candidate:
    candidate_id: str
    sl_r: float
    tp_r: float


A1_REGISTRY = tuple(
    A1Candidate(f"A1-{int(tp * 10):02d}-{int(sl * 10):02d}", sl, tp)
    for tp in TP_R_VALUES
    for sl in SL_R_VALUES
)


@dataclass(frozen=True)
class Trade:
    entry_row: int
    exit_row: int
    side: str
    raw_pips: float  # BEFORE any cost model subtraction
    hold_minutes: int
    floor_clamped: bool
    cap_clamped: bool


@dataclass(frozen=True)
class PriceFaces:
    """Which price face each leg of a trade actually transacts on.

    LEGACY_BID_ONLY uses BID everywhere and relies on an explicit round-trip
    cost model. BID_ASK_M1 realizes the spread in the prices themselves:
    a BUY pays ASK on entry and receives BID on exit (so its stop/target are
    touched on the BID series), and a SELL is the mirror image.
    """

    mode: str
    bid_close: np.ndarray
    bid_high: np.ndarray
    bid_low: np.ndarray
    ask_close: np.ndarray | None

    def entry(self, row: int, direction: float) -> float:
        if self.mode == "BID_ASK_M1" and direction > 0:
            return float(self.ask_close[row])
        return float(self.bid_close[row])

    def exit_close(self, row: int, direction: float) -> float:
        if self.mode == "BID_ASK_M1" and direction < 0:
            return float(self.ask_close[row])
        return float(self.bid_close[row])

    def exit_high(self, row: int, direction: float) -> float:
        # SELL exits on ASK; ASK == BID + spread, and only M1 ASK closes are
        # cached, so the ASK high/low are approximated by shifting the BID
        # extremes by that bar's realized spread (documented approximation).
        if self.mode == "BID_ASK_M1" and direction < 0:
            spread = float(self.ask_close[row]) - float(self.bid_close[row])
            return float(self.bid_high[row]) + spread
        return float(self.bid_high[row])

    def exit_low(self, row: int, direction: float) -> float:
        if self.mode == "BID_ASK_M1" and direction < 0:
            spread = float(self.ask_close[row]) - float(self.bid_close[row])
            return float(self.bid_low[row]) + spread
        return float(self.bid_low[row])


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


def _load_ask_frame_or_none(bid_frame: pd.DataFrame) -> pd.DataFrame | None:
    if not ASK_CACHE_CSV.is_file():
        return None
    ask = pd.read_csv(ASK_CACHE_CSV)
    if ask.empty:
        return None
    ask["time_utc"] = pd.to_datetime(ask["time_utc"], utc=True)
    ask = ask.dropna().drop_duplicates(subset="time_utc", keep="first").sort_values("time_utc")
    ask["time_utc"] = ask["time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    # Coverage must be a superset of the BID frame's timestamps, or ASK mode
    # is not usable yet -- never silently substitute a partial series.
    if not set(bid_frame["time_utc"]).issubset(set(ask["time_utc"])):
        return None
    return ask


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


def _quantize(price: float) -> float:
    return round(round(price / TICK_SIZE) * TICK_SIZE, 6)


def _common_r_pips(atr_price_units: float) -> tuple[float, bool, bool]:
    """Return (common_R in pips, floor_clamped, cap_clamped)."""

    raw_pips = FIXED_ATR_MULTIPLIER * (atr_price_units / PIP)
    floor_clamped = raw_pips < COMMON_R_FLOOR_PIPS
    cap_clamped = raw_pips > COMMON_R_CAP_PIPS
    clamped = min(max(raw_pips, COMMON_R_FLOOR_PIPS), COMMON_R_CAP_PIPS)
    return clamped, floor_clamped, cap_clamped


def _simulate_a1(
    candidate: A1Candidate,
    signals: list[tuple[int, str]],
    faces: PriceFaces,
    atr: np.ndarray,
    minutes_index: np.ndarray,
) -> list[Trade]:
    """common_R-based 3x3 grid candidate; SL-first on same-bar conflict."""

    trades: list[Trade] = []
    busy_until = -1
    total = len(faces.bid_close)
    for row, side in signals:
        if row <= busy_until:
            continue
        direction = 1.0 if side == "BUY" else -1.0
        entry = faces.entry(row, direction)
        common_r_pips, floor_clamped, cap_clamped = _common_r_pips(atr[row])
        sl_dist = candidate.sl_r * common_r_pips * PIP
        tp_dist = candidate.tp_r * common_r_pips * PIP
        stop = _quantize(entry - direction * sl_dist)
        target = _quantize(entry + direction * tp_dist)
        deadline_minute = minutes_index[row] + A1_MAX_HOLD_MINUTES
        exit_pips = None
        exit_row = row
        for later in range(row + 1, total):
            if minutes_index[later] > deadline_minute:
                previous = later - 1
                exit_pips = (
                    direction * (faces.exit_close(previous, direction) - entry) / PIP
                )
                exit_row = previous
                break
            bar_high = faces.exit_high(later, direction)
            bar_low = faces.exit_low(later, direction)
            stop_hit = bar_low <= stop if direction > 0 else bar_high >= stop
            if stop_hit:
                exit_pips = direction * (stop - entry) / PIP
                exit_row = later
                break
            target_hit = bar_high >= target if direction > 0 else bar_low <= target
            if target_hit:
                exit_pips = direction * (target - entry) / PIP
                exit_row = later
                break
        if exit_pips is None:
            continue
        trades.append(
            Trade(
                entry_row=row,
                exit_row=exit_row,
                side=side,
                raw_pips=exit_pips,
                hold_minutes=int(minutes_index[exit_row] - minutes_index[row]),
                floor_clamped=floor_clamped,
                cap_clamped=cap_clamped,
            )
        )
        busy_until = exit_row
    return trades


def _simulate_prod_replay(
    signals: list[tuple[int, str]],
    faces: PriceFaces,
    atr: np.ndarray,
    minutes_index: np.ndarray,
    *,
    timeout_minutes: int = 23 * 60,
) -> list[Trade]:
    """Replay 1.5ATR SL / 1.5R TP with an explicit time limit."""

    trades: list[Trade] = []
    busy_until = -1
    total = len(faces.bid_close)
    if timeout_minutes <= 0:
        raise ValueError("PROD_REPLAY_TIMEOUT_INVALID")
    for row, side in signals:
        if row <= busy_until:
            continue
        direction = 1.0 if side == "BUY" else -1.0
        entry = faces.entry(row, direction)
        distance = 1.5 * atr[row]
        stop = entry - direction * distance
        target = entry + direction * distance * 1.5
        deadline_minute = minutes_index[row] + timeout_minutes
        exit_pips = None
        exit_row = row
        for later in range(row + 1, total):
            if minutes_index[later] > deadline_minute:
                previous = later - 1
                exit_pips = (
                    direction * (faces.exit_close(previous, direction) - entry) / PIP
                )
                exit_row = previous
                break
            bar_high = faces.exit_high(later, direction)
            bar_low = faces.exit_low(later, direction)
            stop_hit = bar_low <= stop if direction > 0 else bar_high >= stop
            if stop_hit:
                exit_pips = direction * (stop - entry) / PIP
                exit_row = later
                break
            target_hit = bar_high >= target if direction > 0 else bar_low <= target
            if target_hit:
                exit_pips = direction * (target - entry) / PIP
                exit_row = later
                break
        if exit_pips is None:
            continue
        trades.append(
            Trade(
                entry_row=row,
                exit_row=exit_row,
                side=side,
                raw_pips=exit_pips,
                hold_minutes=int(minutes_index[exit_row] - minutes_index[row]),
                floor_clamped=False,
                cap_clamped=False,
            )
        )
        busy_until = exit_row
    return trades


def _simulate_a0(
    signals: list[tuple[int, str]],
    faces: PriceFaces,
    minutes_index: np.ndarray,
) -> list[Trade]:
    trades: list[Trade] = []
    busy_until = -1
    total = len(faces.bid_close)
    for row, side in signals:
        if row <= busy_until:
            continue
        direction = 1.0 if side == "BUY" else -1.0
        entry = faces.entry(row, direction)
        deadline_minute = minutes_index[row] + A1_MAX_HOLD_MINUTES
        exit_row = row
        for later in range(row + 1, total):
            if minutes_index[later] > deadline_minute:
                exit_row = later - 1
                break
            exit_row = later
        if exit_row == row:
            continue
        exit_pips = direction * (faces.exit_close(exit_row, direction) - entry) / PIP
        trades.append(
            Trade(
                entry_row=row,
                exit_row=exit_row,
                side=side,
                raw_pips=exit_pips,
                hold_minutes=int(minutes_index[exit_row] - minutes_index[row]),
                floor_clamped=False,
                cap_clamped=False,
            )
        )
        busy_until = exit_row
    return trades


def _apply_cost_c5(trade: Trade, exit_hour_jst: np.ndarray) -> float:
    base = COST_MODELS["C1b"]
    if int(exit_hour_jst[trade.exit_row]) in C5_STRESS_HOURS_JST:
        return base + C5_EXTRA_PIPS
    return base


def _net_pips_by_day(
    trades: list[Trade], jst_day: np.ndarray, cost_pips: float | None, exit_hour_jst=None
) -> dict[str, float]:
    by_day: dict[str, float] = {}
    for trade in trades:
        day = jst_day[trade.entry_row]
        cost = cost_pips if cost_pips is not None else _apply_cost_c5(trade, exit_hour_jst)
        by_day[day] = by_day.get(day, 0.0) + (trade.raw_pips - cost)
    return by_day


def _stationary_bootstrap_indices(
    n: int, expected_block_length: float, rng: np.random.Generator
) -> np.ndarray:
    if n == 0:
        return np.array([], dtype=int)
    p = 1.0 / expected_block_length
    indices = np.empty(n, dtype=int)
    indices[0] = rng.integers(0, n)
    for i in range(1, n):
        if rng.random() < p:
            indices[i] = rng.integers(0, n)
        else:
            indices[i] = (indices[i - 1] + 1) % n
    return indices


def _paired_bootstrap(
    delta_series: np.ndarray, resamples: int, seed: int
) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    n = len(delta_series)
    if n == 0:
        return {
            "mean_delta": 0.0,
            "median_delta": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "p_value_one_sided": 1.0,
        }
    means = np.empty(resamples, dtype=float)
    for b in range(resamples):
        idx = _stationary_bootstrap_indices(n, BOOTSTRAP_EXPECTED_BLOCK_LENGTH_DAYS, rng)
        means[b] = delta_series[idx].mean()
    p_value = float(np.mean(means <= 0.0))
    return {
        "mean_delta": float(delta_series.mean()),
        "median_delta": float(np.median(delta_series)),
        "ci_low": float(np.percentile(means, 2.5)),
        "ci_high": float(np.percentile(means, 97.5)),
        "p_value_one_sided": p_value,
    }


def _benjamini_hochberg(p_values: dict[str, float], q: float) -> dict[str, bool]:
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(ordered)
    survives: dict[str, bool] = {name: False for name, _ in ordered}
    max_rank_surviving = 0
    for rank, (_name, p) in enumerate(ordered, start=1):
        if p <= (rank / m) * q:
            max_rank_surviving = rank
    for rank, (name, _p) in enumerate(ordered, start=1):
        survives[name] = rank <= max_rank_surviving
    return survives


def _cost_durability(
    candidate_net_by_cost: dict[str, float], low_id: str, high_id: str
) -> str:
    if candidate_net_by_cost[low_id] <= 0:
        return "Reject"
    if candidate_net_by_cost[high_id] > 0:
        return "Robust"
    return "Fragile"


def _break_even_cost_pips(trades: list[Trade]) -> float | None:
    if not trades:
        return None
    return float(np.mean([t.raw_pips for t in trades]))


def _clamp_stats(trades: list[Trade]) -> tuple[int, int, float]:
    if not trades:
        return 0, 0, 0.0
    floor_n = sum(1 for t in trades if t.floor_clamped)
    cap_n = sum(1 for t in trades if t.cap_clamped)
    return floor_n, cap_n, (floor_n + cap_n) / len(trades)


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "UNKNOWN"


def main() -> int:
    started_at = datetime.now(UTC).isoformat()
    frame = _load_frame()
    ask_frame = _load_ask_frame_or_none(frame)
    price_mode = "BID_ASK_M1" if ask_frame is not None else "LEGACY_BID_ONLY"

    artifact = ShortModelArtifact.load(ARTIFACT)
    probabilities = _vectorized_probabilities(artifact, frame)
    _verify_vectorization(artifact, frame, probabilities)
    atr = _hourly_atr24(frame)
    times = pd.to_datetime(frame["time_utc"], utc=True)
    minutes_index = (times.astype("int64") // 60_000_000_000).to_numpy()
    jst_times = times + pd.Timedelta(hours=9)
    jst_day = jst_times.dt.strftime("%Y-%m-%d").to_numpy()
    exit_hour_jst = jst_times.dt.hour.to_numpy()

    bid_close = frame["close"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)

    ask_close = None
    if price_mode == "BID_ASK_M1":
        ask_close = (
            ask_frame.set_index("time_utc")
            .reindex(frame["time_utc"])["close"]
            .to_numpy(dtype=float)
        )
    faces = PriceFaces(
        mode=price_mode,
        bid_close=bid_close,
        bid_high=high,
        bid_low=low,
        ask_close=ask_close,
    )
    # In BID_ASK_M1 the spread is already realized in the transacted prices,
    # so the "cost" axis becomes slippage only -- re-subtracting a fixed
    # spread here would double-count it (design doc Sec 6).
    active_cost_models = (
        SLIPPAGE_MODELS if price_mode == "BID_ASK_M1" else COST_MODELS
    )
    baseline_cost_id = "S0" if price_mode == "BID_ASK_M1" else "C1b"
    headline_cost_id = "S0" if price_mode == "BID_ASK_M1" else "C1"
    durability_low_id = "S0" if price_mode == "BID_ASK_M1" else "C1b"
    durability_high_id = "S2" if price_mode == "BID_ASK_M1" else "C3"

    signals = _signal_rows(frame, probabilities, atr)
    cutoff = pd.Timestamp(artifact.development_cutoff_utc)
    development_end_row = int((times < cutoff).sum())
    is_signals = [(r, s) for r, s in signals if r < development_end_row]
    reused_holdout_signals = [(r, s) for r, s in signals if r >= development_end_row]

    ask_note = (
        " (スプレッドは価格に実現済み; コスト軸=slippageのみ)"
        if price_mode == "BID_ASK_M1"
        else " (ASKデータ未整備/未カバーのためBIDのみ; コスト軸=往復コスト)"
    )
    print("=" * 78)
    print("H-11 R-E1 exit-policy research harness -- Phase A1 + Stage 1 of A2")
    print("=" * 78)
    print(
        f"データ: {frame['time_utc'].iloc[0]} 〜 {frame['time_utc'].iloc[-1]}"
        f" ({len(frame):,} bars)"
    )
    print(f"価格面モード: {price_mode}" + ask_note)
    print(
        f"signal候補slot数: {len(signals)}"
        f" (development内 {len(is_signals)} / reused holdout {len(reused_holdout_signals)})"
    )
    print(
        f"common_R: fixed_atr_multiplier={FIXED_ATR_MULTIPLIER},"
        f" floor={COMMON_R_FLOOR_PIPS:.3f}pips, cap={COMMON_R_CAP_PIPS:.3f}pips"
    )
    print()

    # --- regression checks -------------------------------------------------
    a0_trades_dev = _simulate_a0(is_signals, faces, minutes_index)
    a0_trades_reused = _simulate_a0(reused_holdout_signals, faces, minutes_index)
    prod_trades_dev = _simulate_prod_replay(is_signals, faces, atr, minutes_index)
    prod_trades_reused = _simulate_prod_replay(
        reused_holdout_signals, faces, atr, minutes_index
    )
    g019_trades_dev = _simulate_prod_replay(
        is_signals, faces, atr, minutes_index, timeout_minutes=30
    )
    g019_trades_reused = _simulate_prod_replay(
        reused_holdout_signals,
        faces,
        atr,
        minutes_index,
        timeout_minutes=30,
    )

    headline_cost = active_cost_models[headline_cost_id]
    print("-- 回帰確認 (development / reused holdout) --")
    regression_replays: list[dict[str, object]] = []
    for label, trades in (
        ("A0 (30分固定、SLTPなし)", a0_trades_dev + a0_trades_reused),
        ("PROD-G014-REPLAY (1.5ATR/1.5R/23h、簡易比較)", prod_trades_dev + prod_trades_reused),
        (
            "PROD-G019-CANDIDATE (1.5ATR/1.5R/30m、簡易比較)",
            g019_trades_dev + g019_trades_reused,
        ),
    ):
        pips = (
            np.array([t.raw_pips - headline_cost for t in trades])
            if trades
            else np.array([])
        )
        n = len(trades)
        total_yen = float(pips.sum() * YEN_PER_PIP) if n else 0.0
        avg_pips = float(pips.mean()) if n else 0.0
        print(
            f"  {label}: n={n}, net_yen({headline_cost_id})={total_yen:,.0f}, "
            f"avg_pips({headline_cost_id})={avg_pips:.3f}"
        )
        regression_replays.append(
            {
                "label": label,
                "trade_count": n,
                "headline_cost_id": headline_cost_id,
                "net_yen": total_yen,
                "average_net_pips": avg_pips,
            }
        )
    print()

    # --- A1 grid (Stage 1) --------------------------------------------------
    a0_reg_by_day_dev = _net_pips_by_day(
        a0_trades_dev, jst_day, cost_pips=active_cost_models[baseline_cost_id]
    )
    all_clamp_floor = all_clamp_cap = 0
    all_clamp_total = 0

    candidate_rows: list[dict[str, object]] = []
    candidate_daily_delta: dict[str, np.ndarray] = {}
    all_days = sorted(set(jst_day[[r for r, _ in is_signals]]) | set(a0_reg_by_day_dev.keys()))

    for candidate in A1_REGISTRY:
        trades = _simulate_a1(candidate, is_signals, faces, atr, minutes_index)
        floor_n, cap_n, clamp_rate = _clamp_stats(trades)
        all_clamp_floor += floor_n
        all_clamp_cap += cap_n
        all_clamp_total += len(trades)

        net_by_cost = {}
        for cost_id, cost_pips in active_cost_models.items():
            by_day = _net_pips_by_day(trades, jst_day, cost_pips=cost_pips)
            net_by_cost[cost_id] = sum(by_day.values())
        if price_mode == "LEGACY_BID_ONLY":
            by_day_c5 = _net_pips_by_day(
                trades, jst_day, cost_pips=None, exit_hour_jst=exit_hour_jst
            )
            net_by_cost["C5"] = sum(by_day_c5.values())

        by_day_baseline = _net_pips_by_day(
            trades, jst_day, cost_pips=active_cost_models[baseline_cost_id]
        )
        delta_by_day = np.array(
            [by_day_baseline.get(day, 0.0) - a0_reg_by_day_dev.get(day, 0.0) for day in all_days]
        )
        candidate_daily_delta[candidate.candidate_id] = delta_by_day
        break_even = _break_even_cost_pips(trades)

        candidate_rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "sl_r": candidate.sl_r,
                "tp_r": candidate.tp_r,
                "n_trades": len(trades),
                "net_pips_by_cost": {k: round(v, 3) for k, v in net_by_cost.items()},
                "net_yen_baseline": round(
                    net_by_cost[baseline_cost_id] * YEN_PER_PIP, 0
                ),
                "break_even_extra_cost_pips": (
                    round(break_even, 4) if break_even is not None else None
                ),
                "cost_durability": _cost_durability(
                    net_by_cost, durability_low_id, durability_high_id
                ),
                "clamp_floor_count": floor_n,
                "clamp_cap_count": cap_n,
                "clamp_rate": round(clamp_rate, 4),
            }
        )

    overall_clamp_rate = (
        (all_clamp_floor + all_clamp_cap) / all_clamp_total if all_clamp_total else 0.0
    )
    print(
        f"-- common_Rクランプ発生率(全A1候補合算): floor={all_clamp_floor}"
        f" cap={all_clamp_cap} rate={overall_clamp_rate:.3f} --"
    )
    print()

    print(f"-- A1 3x3グリッド (development, vs A0, {baseline_cost_id}基準) --")
    p_values: dict[str, float] = {}
    bootstrap_results: dict[str, dict[str, float]] = {}
    for row in candidate_rows:
        cid = row["candidate_id"]
        delta = candidate_daily_delta[cid]
        stats = _paired_bootstrap(delta, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)
        bootstrap_results[cid] = stats
        p_values[cid] = stats["p_value_one_sided"]
        break_even = row["break_even_extra_cost_pips"]
        print(
            f"  {cid}: n={row['n_trades']:>4} "
            f"net_yen({baseline_cost_id})={row['net_yen_baseline']:>10,.0f} "
            f"耐久性={row['cost_durability']:<7} break_even={break_even} "
            f"clamp_rate={row['clamp_rate']:.3f} "
            f"Δmean/day={stats['mean_delta']:.4f} "
            f"CI=[{stats['ci_low']:.4f},{stats['ci_high']:.4f}] "
            f"p={stats['p_value_one_sided']:.4f}"
        )

    fdr_survives = _benjamini_hochberg(p_values, FDR_Q)
    print()
    print(f"-- BH-FDR (q={FDR_Q}) 生存候補 --")
    survivors = [cid for cid, ok in fdr_survives.items() if ok]
    if survivors:
        for cid in survivors:
            print(f"  {cid}")
    else:
        print("  (生存候補なし -- 全候補がA0に対しFDR基準で有意な改善を示さなかった)")
    print()

    zero_cost_id = "S0" if price_mode == "BID_ASK_M1" else "C0"
    all_zero_cost_negative = all(
        row["net_pips_by_cost"][zero_cost_id] <= 0 for row in candidate_rows
    )
    print(f"-- {zero_cost_id}(追加コストなし)診断 --")
    if price_mode == "BID_ASK_M1":
        print(
            "  実測スプレッドは既に価格へ反映済み。"
            + (
                "全候補マイナス -> 実コスト後の優位性なし"
                if all_zero_cost_negative
                else "一部候補プラス -> slippage耐性の確認が必要"
            )
        )
    else:
        print(
            "  全候補C0マイナス -> 方向エッジ/価格経路自体が負"
            if all_zero_cost_negative
            else "  一部候補はC0でプラス -> コストが主要因の可能性"
        )
    print()

    # --- manifest ------------------------------------------------------------
    finished_at = datetime.now(UTC).isoformat()
    manifest = {
        "git_commit": _git_commit(),
        "script_sha256": _sha256_file(Path(__file__)),
        "entry_artifact_sha256": _sha256_file(ARTIFACT),
        "bid_data_sha256": _sha256_file(CACHE_CSV),
        "ask_data_sha256": _sha256_file(ASK_CACHE_CSV),
        "price_mode": price_mode,
        "python_version": sys.version,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "run_started_at": started_at,
        "run_finished_at": finished_at,
        "candidate_registry": [
            {"candidate_id": c.candidate_id, "sl_r": c.sl_r, "tp_r": c.tp_r} for c in A1_REGISTRY
        ],
        "fdr_q": FDR_Q,
        "common_r_floor_pips": COMMON_R_FLOOR_PIPS,
        "common_r_cap_pips": COMMON_R_CAP_PIPS,
    }
    manifest_json = json.dumps(manifest, sort_keys=True, indent=2)
    manifest_path = (
        REPOSITORY / "backend" / "market_data" / "backtest" / "re1_stage1_manifest_latest.json"
    )
    manifest_path.write_text(manifest_json, encoding="utf-8")
    manifest_sha = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
    print(f"manifest saved: {manifest_path} (output_sha256=sha256:{manifest_sha})")

    results_path = (
        REPOSITORY / "backend" / "market_data" / "backtest" / "re1_stage1_results_latest.json"
    )
    results_path.write_text(
        json.dumps(
            {
                "price_mode": price_mode,
                "regression_replays": regression_replays,
                "candidates": candidate_rows,
                "bootstrap": bootstrap_results,
                "fdr_survivors": survivors,
                "all_zero_cost_negative": all_zero_cost_negative,
                "manifest_output_sha256": f"sha256:{manifest_sha}",
            },
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"results saved: {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
