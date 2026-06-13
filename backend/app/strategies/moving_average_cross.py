from typing import Literal

import pandas as pd


def moving_average_cross_signal(
    frame: pd.DataFrame, short_period: int, long_period: int
) -> tuple[Literal["buy", "sell", "hold"], str]:
    if len(frame) < long_period + 1:
        return "hold", "移動平均の計算に必要な価格履歴が不足"
    close = frame["close"]
    short_ma = close.rolling(short_period).mean()
    long_ma = close.rolling(long_period).mean()
    previous_short, current_short = short_ma.iloc[-2], short_ma.iloc[-1]
    previous_long, current_long = long_ma.iloc[-2], long_ma.iloc[-1]
    if previous_short <= previous_long and current_short > current_long:
        return "buy", f"短期MA({short_period})が長期MA({long_period})を上抜け"
    if previous_short >= previous_long and current_short < current_long:
        return "sell", f"短期MA({short_period})が長期MA({long_period})を下抜け"
    return "hold", "移動平均クロスなし"
