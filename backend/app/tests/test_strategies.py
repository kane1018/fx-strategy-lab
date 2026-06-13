import pandas as pd

from app.schemas.trading import StrategyConfig, StrategyType
from app.strategies import evaluate_strategy


def frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": closes,
            "high": [value + 0.1 for value in closes],
            "low": [value - 0.1 for value in closes],
            "close": closes,
        }
    )


def test_moving_average_cross_emits_buy() -> None:
    config = StrategyConfig(
        strategy_type=StrategyType.MOVING_AVERAGE_CROSS,
        short_period=2,
        long_period=3,
    )
    signal = evaluate_strategy(frame([5, 4, 3, 2, 3, 5]), config)
    assert signal.action == "buy"


def test_breakout_excludes_current_candle_from_reference() -> None:
    config = StrategyConfig(
        strategy_type=StrategyType.BREAKOUT,
        breakout_period=3,
    )
    signal = evaluate_strategy(frame([1, 1.1, 1.2, 1.3, 2]), config)
    assert signal.action == "buy"
