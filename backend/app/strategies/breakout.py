from typing import Literal

import pandas as pd


def breakout_signal(frame: pd.DataFrame, period: int) -> tuple[Literal["buy", "sell", "hold"], str]:
    if len(frame) < period + 1:
        return "hold", "ブレイクアウト判定に必要な価格履歴が不足"
    # Current candle is excluded from the reference range to prevent look-ahead bias.
    reference = frame.iloc[-period - 1 : -1]
    current_close = float(frame["close"].iloc[-1])
    recent_high = float(reference["high"].max())
    recent_low = float(reference["low"].min())
    if current_close > recent_high:
        return "buy", f"終値が直近{period}本の高値{recent_high:.5f}を上抜け"
    if current_close < recent_low:
        return "sell", f"終値が直近{period}本の安値{recent_low:.5f}を下抜け"
    return "hold", "参照レンジ内"
