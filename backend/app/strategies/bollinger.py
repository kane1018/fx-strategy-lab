from typing import Literal

import pandas as pd


def bollinger_reversion_signal(
    frame: pd.DataFrame, period: int, sigma: float
) -> tuple[Literal["buy", "sell", "hold"], str]:
    """Mean-reversion: buy when close pierces the lower band, sell on the upper band.

    Bands use the last `period` closes (population std). The latest row is the most
    recent COMPLETED bar in the replay loop (frame is sliced to [:index]), so there
    is no look-ahead — same information set as the rsi/breakout signals.
    """
    if len(frame) < period:
        return "hold", "ボリンジャー判定に必要な価格履歴が不足"
    window = frame["close"].iloc[-period:]
    mean = float(window.mean())
    std = float(window.std(ddof=0))
    if std <= 0:
        return "hold", "標準偏差ゼロ"
    upper = mean + sigma * std
    lower = mean - sigma * std
    close = float(frame["close"].iloc[-1])
    if close <= lower:
        return "buy", f"終値{close:.5f}がlower band{lower:.5f}以下(平均回帰)"
    if close >= upper:
        return "sell", f"終値{close:.5f}がupper band{upper:.5f}以上(平均回帰)"
    return "hold", f"バンド内({lower:.5f}〜{upper:.5f})"
