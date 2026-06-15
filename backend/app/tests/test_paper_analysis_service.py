from datetime import datetime

import pandas as pd

from app.services.paper_analysis_service import (
    adx_bucket,
    aggregate,
    compute_indicators,
    enrich_trades,
    holding_bucket,
    holding_minutes,
    ma_slope_class,
    streak_and_tail,
    time_bucket,
)


def test_time_buckets_cover_sessions() -> None:
    assert time_bucket(datetime(2026, 6, 12, 22)) == "early_morning"
    assert time_bucket(datetime(2026, 6, 12, 3)) == "tokyo"
    assert time_bucket(datetime(2026, 6, 12, 9)) == "london"
    assert time_bucket(datetime(2026, 6, 12, 15)) == "new_york"


def test_holding_helpers() -> None:
    assert holding_minutes(datetime(2026, 6, 1, 0, 0), datetime(2026, 6, 1, 0, 20)) == 20
    assert holding_bucket(3) == "<5min"
    assert holding_bucket(10) == "5-15min"
    assert holding_bucket(20) == "15-30min"
    assert holding_bucket(45) == "30-60min"
    assert holding_bucket(90) == "60min+"


def test_adx_and_ma_slope_buckets() -> None:
    assert adx_bucket(10) == "ADX0-15"
    assert adx_bucket(27) == "ADX25-30"
    assert adx_bucket(55) == "ADX30+"
    assert ma_slope_class(0.1, flat_threshold=0.5) == "flat"
    assert ma_slope_class(2.0, flat_threshold=0.5) == "uptrend"
    assert ma_slope_class(-2.0, flat_threshold=0.5) == "downtrend"


def test_compute_indicators_shapes_and_adx_range() -> None:
    n = 120
    base = datetime(2026, 6, 1)
    frame = pd.DataFrame(
        {
            "timestamp": [base + pd.Timedelta(minutes=i) for i in range(n)],
            "open": [150 + i * 0.05 for i in range(n)],
            "high": [150 + i * 0.05 + 0.03 for i in range(n)],
            "low": [150 + i * 0.05 - 0.03 for i in range(n)],
            "close": [150 + i * 0.05 for i in range(n)],
            "volume": [0] * n,
        }
    )
    out = compute_indicators(frame, pip=0.01)
    assert list(out.columns) == ["timestamp", "adx", "atr_pips", "ma_slope_pips", "range_pips"]
    # a clean uptrend should produce a strong (high) ADX once warmed up
    assert out["adx"].iloc[-1] > 25
    assert out["atr_pips"].iloc[-1] > 0


def test_enrich_and_aggregate_keep_completed_only() -> None:
    trades = [
        {"symbol": "USD_JPY", "strategy": "rsi_reversal", "side": "buy", "pnl": 1.0,
         "opened_at": datetime(2026, 6, 1, 3, 0), "closed_at": datetime(2026, 6, 1, 3, 40),
         "date": "2026-06-01"},
        {"symbol": "USD_JPY", "strategy": "rsi_reversal", "side": "sell", "pnl": -2.0,
         "opened_at": datetime(2026, 6, 1, 15, 0), "closed_at": datetime(2026, 6, 1, 15, 5),
         "date": "2026-06-01"},
    ]
    enriched = enrich_trades(trades, lookups={})
    assert enriched[0]["time_bucket"] == "tokyo"
    assert enriched[0]["holding_bucket"] == "30-60min"
    assert enriched[1]["time_bucket"] == "new_york"
    by_time = aggregate(enriched, "time_bucket")
    assert by_time["tokyo"]["completed_trades"] == 1
    assert by_time["new_york"]["total_pnl"] == -2.0


def test_streak_and_tail_counts() -> None:
    trades = [
        {"pnl": p, "symbol": "USD_JPY", "strategy": "s", "time_bucket": "tokyo",
         "adx_bucket": "ADX0-15", "holding_bucket": "<5min",
         "closed_at": datetime(2026, 6, 1, 0, i)}
        for i, p in enumerate([-1, -1, -1, 2, -1])
    ]
    result = streak_and_tail(trades)
    assert result["max_consecutive_losses"] == 3
    assert result["max_single_loss"] == -1.0
    assert result["max_single_win"] == 2.0
    assert len(result["top5_losses"]) == 4
