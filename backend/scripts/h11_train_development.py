"""H-11 development training CLI (operator-authorized public GET, no-POST).

Operator authorization: 2026-07-11 (public GET for development data only).
- GET-only against the GMO Public API (klines). No auth, no Private API, no orders.
- Raw candles are cached under backend/market_data/ (gitignored, never committed).
- stdout prints ONLY safe aggregates (row counts, Brier / log loss); never raw
  prices, spreads, or per-bar values.
- Development-only: bars at/after the spec-freeze cutoff (2026-07-11 00:00 JST)
  are dropped. The forward formal-test period stays untouched.

Usage (from backend/):
    python -m scripts.h11_train_development           # fetch (or reuse cache) + train
    python -m scripts.h11_train_development --offline # cache only, no network
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from app.shadow.gmo_public import GmoPublicError, GmoPublicMarketDataClient
from app.strategies.h11_regime_moe import (
    H11_CONFIG_HASH,
    H11_V2_CONFIG_HASH,
    H11PredictionStatus,
    _fit_logistic,
    _sigmoid,
    chronological_split,
    compute_features,
    directional_labels,
    predict_h11,
    predict_h11_v2,
    train_h11_model,
    train_h11_v2,
)

DEV_CUTOFF_UTC = datetime(2026, 7, 10, 15, 0, tzinfo=UTC)  # 2026-07-11 00:00 JST
FETCH_START_UTC = datetime(2024, 1, 1, tzinfo=UTC)
FETCH_SLEEP_SECONDS = 0.15  # polite pacing against the public endpoint
SYMBOL = "USD_JPY"
CACHE_PATH = Path("market_data/usdjpy_h1_dev_bid.csv")
PARAMETERS_PATH = Path("app/strategies/h11_parameters_v1.json")
METRICS_PATH = Path("market_data/h11_dev_validation_metrics.json")


def _fetch_to_cache() -> None:
    # The public 1hour klines endpoint only serves per-day files (date=YYYYMMDD),
    # so iterate calendar days; closed days return an empty payload and are skipped.
    client = GmoPublicMarketDataClient()
    rows: dict[str, tuple[float, float, float, float]] = {}
    day = FETCH_START_UTC
    fetched_days = skipped_days = 0
    while day <= DEV_CUTOFF_UTC:
        try:
            candles = client.fetch_candles(
                SYMBOL, "H1", limit=0, price_type="BID", date=day.strftime("%Y%m%d")
            )
            for candle in candles:
                rows[candle.time] = (candle.open, candle.high, candle.low, candle.close)
            fetched_days += 1
        except GmoPublicError as error:
            if "no klines" in str(error):
                skipped_days += 1  # market closed (weekend/holiday)
            else:
                raise
        day += timedelta(days=1)
        time.sleep(FETCH_SLEEP_SECONDS)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_utc", "open", "high", "low", "close"])
        for time_iso in sorted(rows):
            writer.writerow([time_iso, *rows[time_iso]])
    print(f"cache written: rows={len(rows)} days_fetched={fetched_days} days_closed={skipped_days}")


def _load_cache() -> tuple[np.ndarray, ...]:
    times: list[datetime] = []
    ohlc: list[tuple[float, float, float, float]] = []
    with CACHE_PATH.open() as handle:
        for row in csv.DictReader(handle):
            stamp = datetime.fromisoformat(row["time_utc"])
            if stamp >= DEV_CUTOFF_UTC:
                continue  # development-only: never touch the forward period
            times.append(stamp)
            ohlc.append(
                (float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]))
            )
    arr = np.asarray(ohlc)
    hour_jst = np.asarray([(t.hour + 9) % 24 for t in times])
    # LIQUIDITY_COST_STATE (frozen spec): wide category = outside the 9:00-翌5:00 JST
    # quoting window, i.e. 5:00-8:59 JST.
    spread_wide = ((hour_jst >= 5) & (hour_jst < 9)).astype(int)
    return arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], hour_jst, spread_wide


def _brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def _log_loss(p: np.ndarray, y: np.ndarray) -> float:
    q = np.clip(p, 1e-9, 1.0 - 1e-9)
    return float(-np.mean(y * np.log(q) + (1.0 - y) * np.log(1.0 - q)))


def _run_v1(features, labels, rows) -> tuple[dict, dict]:
    parameters = train_h11_model(features, labels)
    moe_p, expert_p, scored = [], [], 0
    for row in rows:
        pred = predict_h11(parameters, features.expert_features[row], features.regime_axes[row])
        if pred.prediction_status is H11PredictionStatus.OK:
            moe_p.append(pred.p_up)
            expert_p.append(pred.expert_probabilities)
            scored += 1
    y = labels[rows][: len(moe_p)]
    moe = np.asarray(moe_p)
    experts = np.asarray(expert_p)
    equal_weight = experts.mean(axis=1)
    metrics = {
        "config_hash": H11_CONFIG_HASH,
        "validation_rows_scored": scored,
        "validation_coverage": round(scored / max(len(rows), 1), 4),
        "brier_moe": round(_brier(moe, y), 6),
        "brier_equal_weight": round(_brier(equal_weight, y), 6),
        "brier_baseline_p05": 0.25,
        "brier_expert_trend": round(_brier(experts[:, 0], y), 6),
        "brier_expert_meanrev": round(_brier(experts[:, 1], y), 6),
        "brier_expert_breakout": round(_brier(experts[:, 2], y), 6),
        "log_loss_moe": round(_log_loss(moe, y), 6),
        "log_loss_equal_weight": round(_log_loss(equal_weight, y), 6),
    }
    artifact = {
        "expert_weights": parameters.expert_weights,
        "router_weights": parameters.router_weights,
    }
    return metrics, artifact


def _run_v2(features, labels, rows) -> tuple[dict, dict]:
    parameters = train_h11_v2(features, labels)
    v2_p, scored = [], 0
    for row in rows:
        pred = predict_h11_v2(
            parameters, features.expert_features[row], features.regime_axes[row]
        )
        if pred.prediction_status is H11PredictionStatus.OK:
            v2_p.append(pred.p_up)
            scored += 1
    y = labels[rows][: len(v2_p)]
    v2 = np.asarray(v2_p)

    # Direct-model comparator (v2 spec §2): one logistic on all 9 expert features.
    usable = features.eligible & np.isfinite(labels)
    idx_train, _ = chronological_split(len(labels))
    train_rows = idx_train[usable[idx_train]]
    flat_train = features.expert_features[train_rows].reshape(len(train_rows), -1)
    w_direct = _fit_logistic(flat_train, labels[train_rows])
    flat_valid = features.expert_features[rows].reshape(len(rows), -1)
    direct = _sigmoid(np.hstack([flat_valid, np.ones((len(rows), 1))]) @ w_direct)[: len(v2)]

    metrics = {
        "config_hash": H11_V2_CONFIG_HASH,
        "validation_rows_scored": scored,
        "validation_coverage": round(scored / max(len(rows), 1), 4),
        "brier_v2_trend_single": round(_brier(v2, y), 6),
        "brier_direct_model_9feat": round(_brier(direct, y), 6),
        "brier_baseline_p05": 0.25,
        "relative_improvement_vs_baseline": round(1.0 - _brier(v2, y) / 0.25, 6),
        "log_loss_v2_trend_single": round(_log_loss(v2, y), 6),
        "log_loss_direct_model_9feat": round(_log_loss(direct, y), 6),
    }
    artifact = {"trend_weights": parameters.trend_weights}
    return metrics, artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="H-11 development training (no-POST)")
    parser.add_argument("--offline", action="store_true", help="use cache only, no network")
    parser.add_argument("--version", type=int, choices=[1, 2], default=1)
    args = parser.parse_args()

    if not args.offline and not CACHE_PATH.exists():
        try:
            _fetch_to_cache()
        except GmoPublicError as error:
            print(f"ERROR: {error}")
            return 1
    if not CACHE_PATH.exists():
        print("ERROR: no cache and --offline given")
        return 1

    open_, high, low, close, hour_jst, spread_wide = _load_cache()
    print(f"development bars (pre-cutoff): {len(close)}")

    features = compute_features(open_, high, low, close, hour_jst, spread_wide)
    labels = directional_labels(close)
    _, valid_idx = chronological_split(len(labels))
    rows = valid_idx[features.eligible[valid_idx] & np.isfinite(labels[valid_idx])]

    runner = _run_v2 if args.version == 2 else _run_v1
    metrics, artifact = runner(features, labels, rows)
    metrics = {
        **metrics,
        "trained_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "development_cutoff_utc": DEV_CUTOFF_UTC.isoformat(timespec="seconds"),
        "scope": "DEVELOPMENT_VALIDATION_ONLY_NOT_FORMAL_TEST_NOT_EDGE_EVIDENCE",
        "performance_proof_status": False,
    }

    params_path = (
        PARAMETERS_PATH
        if args.version == 1
        else Path("app/strategies/h11_parameters_v2.json")
    )
    params_path.write_text(
        json.dumps(
            {
                "config_hash": metrics["config_hash"],
                "trained_at_utc": metrics["trained_at_utc"],
                "development_cutoff_utc": metrics["development_cutoff_utc"],
                "scope": metrics["scope"],
                **artifact,
            },
            indent=2,
        )
    )
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    metrics_path = METRICS_PATH.with_name(f"h11_dev_validation_metrics_v{args.version}.json")
    metrics_path.write_text(json.dumps(metrics, indent=2))

    for key, value in metrics.items():
        print(f"{key}: {value}")
    brier_key = "brier_moe" if args.version == 1 else "brier_v2_trend_single"
    if not math.isfinite(metrics[brier_key]):
        print("ERROR: non-finite metric")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
