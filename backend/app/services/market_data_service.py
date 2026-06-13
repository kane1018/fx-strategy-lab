from datetime import datetime

import numpy as np
import pandas as pd

from app.schemas.trading import Candle

TIMEFRAME_FREQUENCIES = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "H1": "1h",
    "H4": "4h",
    "D": "1D",
}

BASE_PRICES = {
    "USD_JPY": 157.0,
    "EUR_USD": 1.08,
    "GBP_JPY": 200.0,
    "AUD_JPY": 102.0,
}


def pip_size(symbol: str) -> float:
    return 0.01 if symbol.endswith("JPY") else 0.0001


def generate_demo_candles(
    symbol: str, timeframe: str, start: datetime, end: datetime, limit: int = 2500
) -> list[Candle]:
    frequency = TIMEFRAME_FREQUENCIES.get(timeframe, "1h")
    timestamps = pd.date_range(start=start, end=end, freq=frequency, inclusive="left")
    if len(timestamps) > limit:
        timestamps = timestamps[-limit:]
    if len(timestamps) < 80:
        timestamps = pd.date_range(end=end, periods=200, freq=frequency)

    seed = sum(ord(char) for char in f"{symbol}:{timeframe}:{start.date()}:{end.date()}")
    random = np.random.default_rng(seed)
    base = BASE_PRICES.get(symbol, 100.0)
    scale = pip_size(symbol) * 4
    drift = np.sin(np.arange(len(timestamps)) / 19) * scale * 0.35
    changes = random.normal(0, scale, len(timestamps)) + drift
    close = base + np.cumsum(changes)
    open_price = np.concatenate(([base], close[:-1]))
    wick = np.abs(random.normal(scale * 0.7, scale * 0.25, len(timestamps)))
    high = np.maximum(open_price, close) + wick
    low = np.minimum(open_price, close) - wick
    volume = random.integers(100, 2000, len(timestamps))

    return [
        Candle(
            timestamp=timestamp.to_pydatetime(),
            open=float(open_value),
            high=float(high_value),
            low=float(low_value),
            close=float(close_value),
            volume=float(volume_value),
        )
        for timestamp, open_value, high_value, low_value, close_value, volume_value in zip(
            timestamps, open_price, high, low, close, volume, strict=True
        )
    ]


def candles_to_frame(candles: list[Candle]) -> pd.DataFrame:
    frame = pd.DataFrame([candle.model_dump() for candle in candles])
    frame = frame.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    return frame


def next_demo_price(symbol: str, previous_price: float, tick_index: int) -> float:
    seed = sum(ord(char) for char in symbol) + tick_index * 7919
    random = np.random.default_rng(seed)
    return max(pip_size(symbol), previous_price + float(random.normal(0, pip_size(symbol) * 2)))
