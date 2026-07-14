"""Every-second rolling research estimates, isolated from formal forecasts."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

ROLLING_WINDOW_SECONDS = 60
ROLLING_BAR_COUNT = 31
MIN_SAMPLES_PER_ROLLING_BAR = 45
MAX_SAMPLE_GAP_SECONDS = 5


@dataclass(frozen=True)
class RollingFrameResult:
    frame: pd.DataFrame
    tick_native_window_ready: bool
    sample_count: int
    coverage_seconds: int


def _candle(time_utc: pd.Timestamp, prices: pd.Series) -> dict[str, object]:
    return {
        "time_utc": time_utc.isoformat(),
        "open": float(prices.iloc[0]),
        "high": float(prices.max()),
        "low": float(prices.min()),
        "close": float(prices.iloc[-1]),
    }


def _normalized_ticks(ticks: pd.DataFrame) -> pd.DataFrame:
    if ticks.empty or not {"sample_time_utc", "bid"}.issubset(ticks.columns):
        return pd.DataFrame(columns=["sample_time_utc", "bid"])
    result = ticks[["sample_time_utc", "bid"]].copy()
    result["sample_time_utc"] = pd.to_datetime(result["sample_time_utc"], utc=True, errors="coerce")
    result["bid"] = pd.to_numeric(result["bid"], errors="coerce")
    return (
        result.dropna()
        .sort_values("sample_time_utc")
        .drop_duplicates("sample_time_utc", keep="last")
        .reset_index(drop=True)
    )


def build_rolling_feature_frame(m1: pd.DataFrame, ticks: pd.DataFrame) -> RollingFrameResult:
    """Build an offset M1-equivalent frame ending at the latest one-second sample.

    Until 31 complete, sufficiently sampled rolling minutes exist, the historical
    part comes from completed M1 candles and only the latest 60-second candle is
    tick-derived. This bootstrap mode is display-only and never a formal signal.
    """

    normalized = _normalized_ticks(ticks)
    if normalized.empty:
        return RollingFrameResult(pd.DataFrame(), False, 0, 0)
    latest = normalized.iloc[-1]["sample_time_utc"]
    earliest = normalized.iloc[0]["sample_time_utc"]
    coverage_seconds = max(0, int((latest - earliest).total_seconds()) + 1)

    native_rows: list[dict[str, object]] = []
    native_ready = True
    for offset in reversed(range(ROLLING_BAR_COUNT)):
        end = latest - pd.Timedelta(seconds=offset * ROLLING_WINDOW_SECONDS)
        start = end - pd.Timedelta(seconds=ROLLING_WINDOW_SECONDS)
        window = normalized[
            (normalized["sample_time_utc"] > start) & (normalized["sample_time_utc"] <= end)
        ]
        if len(window) < MIN_SAMPLES_PER_ROLLING_BAR:
            native_ready = False
            break
        gaps = window["sample_time_utc"].diff().dt.total_seconds().dropna()
        if not gaps.empty and float(gaps.max()) > MAX_SAMPLE_GAP_SECONDS:
            native_ready = False
            break
        native_rows.append(_candle(end, window["bid"]))
    if native_ready and len(native_rows) == ROLLING_BAR_COUNT:
        return RollingFrameResult(
            pd.DataFrame(native_rows), True, len(normalized), coverage_seconds
        )

    latest_window = normalized[
        normalized["sample_time_utc"] > latest - pd.Timedelta(seconds=ROLLING_WINDOW_SECONDS)
    ]
    if latest_window.empty or m1.empty:
        return RollingFrameResult(pd.DataFrame(), False, len(normalized), coverage_seconds)
    history = m1[["time_utc", "open", "high", "low", "close"]].tail(90).copy()
    rolling_row = pd.DataFrame([_candle(latest, latest_window["bid"])])
    frame = pd.concat([history, rolling_row], ignore_index=True)
    return RollingFrameResult(frame, False, len(normalized), coverage_seconds)
