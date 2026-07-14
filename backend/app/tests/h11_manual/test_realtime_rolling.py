"""Pure rolling-frame tests for the non-formal every-second estimate."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.h11_manual.realtime import build_rolling_feature_frame


def _m1(rows: int = 100) -> pd.DataFrame:
    close = np.linspace(159.8, 160.2, rows)
    return pd.DataFrame(
        {
            "time_utc": pd.date_range("2026-07-14T00:00:00Z", periods=rows, freq="min").astype(str),
            "open": close - 0.002,
            "high": close + 0.006,
            "low": close - 0.006,
            "close": close,
        }
    )


def test_bootstrap_uses_m1_history_and_latest_rolling_minute() -> None:
    ticks = pd.DataFrame(
        {
            "sample_time_utc": pd.date_range("2026-07-14T02:00:00Z", periods=30, freq="s").astype(
                str
            ),
            "bid": np.linspace(160.0, 160.03, 30),
        }
    )
    result = build_rolling_feature_frame(_m1(), ticks)
    assert result.tick_native_window_ready is False
    assert result.sample_count == 30
    assert len(result.frame) == 91
    assert result.frame.iloc[-1]["close"] == 160.03


def test_native_rolling_frame_requires_31_high_coverage_windows() -> None:
    ticks = pd.DataFrame(
        {
            "sample_time_utc": pd.date_range(
                "2026-07-14T02:00:00Z", periods=31 * 60, freq="s"
            ).astype(str),
            "bid": 160.0 + np.sin(np.arange(31 * 60) / 50) * 0.01,
        }
    )
    result = build_rolling_feature_frame(_m1(), ticks)
    assert result.tick_native_window_ready is True
    assert len(result.frame) == 31
    assert result.coverage_seconds == 31 * 60


def test_native_rolling_frame_fails_closed_on_large_sample_gap() -> None:
    times = pd.date_range("2026-07-14T02:00:00Z", periods=31 * 60, freq="s")
    keep = ~((times >= times[900]) & (times <= times[920]))
    ticks = pd.DataFrame(
        {"sample_time_utc": times[keep].astype(str), "bid": np.linspace(160.0, 160.02, keep.sum())}
    )
    result = build_rolling_feature_frame(_m1(), ticks)
    assert result.tick_native_window_ready is False
