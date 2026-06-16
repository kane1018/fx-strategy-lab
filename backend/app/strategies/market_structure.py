from typing import Literal

import pandas as pd


def market_structure_reversion_signal(
    frame: pd.DataFrame, lookback: int, wick_ratio: float
) -> tuple[Literal["buy", "sell", "hold"], str]:
    """Mean-reversion at swing extremes with a rejection wick.

    Long when the latest COMPLETED bar marks (or ties) the swing low of the last
    `lookback` bars AND has a lower wick >= `wick_ratio` of its range; short is the
    mirror at the swing high. In the replay loop the frame is sliced to [:index],
    so the latest row is the last completed bar -> no look-ahead (same information
    set as the rsi/breakout/bollinger signals).
    """
    if len(frame) < lookback:
        return "hold", "スイング判定に必要な価格履歴が不足"
    recent = frame.iloc[-lookback:]
    row = frame.iloc[-1]
    high, low = float(row["high"]), float(row["low"])
    open_, close = float(row["open"]), float(row["close"])
    rng = high - low
    if rng <= 0:
        return "hold", "レンジゼロ"
    lower_wick = min(open_, close) - low
    upper_wick = high - max(open_, close)
    swing_low = low <= float(recent["low"].min())
    swing_high = high >= float(recent["high"].max())
    if swing_low and lower_wick >= wick_ratio * rng:
        return "buy", f"直近{lookback}本スイング安値+下ヒゲ{lower_wick / rng:.0%}(平均回帰)"
    if swing_high and upper_wick >= wick_ratio * rng:
        return "sell", f"直近{lookback}本スイング高値+上ヒゲ{upper_wick / rng:.0%}(平均回帰)"
    return "hold", "スイング極値/ヒゲ条件を満たさず"
