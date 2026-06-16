from dataclasses import dataclass
from typing import Literal

import pandas as pd

from app.schemas.trading import StrategyConfig, StrategyType
from app.strategies.bollinger import bollinger_reversion_signal
from app.strategies.breakout import breakout_signal
from app.strategies.moving_average_cross import moving_average_cross_signal
from app.strategies.rsi_reversal import rsi_reversal_signal


@dataclass(frozen=True)
class StrategySignal:
    action: Literal["buy", "sell", "hold"]
    reason: str


def evaluate_strategy(frame: pd.DataFrame, config: StrategyConfig) -> StrategySignal:
    if config.strategy_type == StrategyType.MOVING_AVERAGE_CROSS:
        action, reason = moving_average_cross_signal(frame, config.short_period, config.long_period)
    elif config.strategy_type == StrategyType.RSI_REVERSAL:
        action, reason = rsi_reversal_signal(
            frame, config.rsi_period, config.oversold, config.overbought
        )
    elif config.strategy_type == StrategyType.BOLLINGER_REVERSION:
        action, reason = bollinger_reversion_signal(
            frame, config.bollinger_period, config.bollinger_sigma
        )
    else:
        action, reason = breakout_signal(frame, config.breakout_period)
    return StrategySignal(action=action, reason=reason)
