from typing import Literal

import pandas as pd


def calculate_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    average_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    average_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    relative_strength = average_gain / average_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + relative_strength))
    return rsi.fillna(50)


def rsi_reversal_signal(
    frame: pd.DataFrame, period: int, oversold: float, overbought: float
) -> tuple[Literal["buy", "sell", "hold"], str]:
    if len(frame) < period + 2:
        return "hold", "RSIの計算に必要な価格履歴が不足"
    rsi = calculate_rsi(frame["close"], period)
    previous, current = float(rsi.iloc[-2]), float(rsi.iloc[-1])
    if previous > oversold and current <= oversold:
        return "buy", f"RSI({period})={current:.1f}が売られすぎライン{oversold}以下"
    if previous < overbought and current >= overbought:
        return "sell", f"RSI({period})={current:.1f}が買われすぎライン{overbought}以上"
    return "hold", f"RSI({period})={current:.1f}、閾値到達なし"
