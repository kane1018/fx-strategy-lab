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


def test_bollinger_defaults_are_period20_sigma2() -> None:
    config = StrategyConfig(strategy_type=StrategyType.BOLLINGER_REVERSION)
    assert config.bollinger_period == 20
    assert config.bollinger_sigma == 2.0


def test_bollinger_buy_on_lower_band_pierce() -> None:
    config = StrategyConfig(strategy_type=StrategyType.BOLLINGER_REVERSION)  # period20/sigma2
    # 19 flat closes + one sharp drop -> last close < lower band -> mean-reversion buy.
    signal = evaluate_strategy(frame([100.0] * 19 + [99.0]), config)
    assert signal.action == "buy"


def test_bollinger_sell_on_upper_band_pierce() -> None:
    config = StrategyConfig(strategy_type=StrategyType.BOLLINGER_REVERSION)
    signal = evaluate_strategy(frame([100.0] * 19 + [101.0]), config)
    assert signal.action == "sell"


def test_bollinger_holds_within_band_and_on_warmup() -> None:
    config = StrategyConfig(strategy_type=StrategyType.BOLLINGER_REVERSION)
    # Fewer than `period` bars -> warmup hold.
    assert evaluate_strategy(frame([100.0] * 10), config).action == "hold"
    # Flat series -> std 0 -> hold (no false band pierce).
    assert evaluate_strategy(frame([100.0] * 20), config).action == "hold"


def test_bollinger_signal_uses_only_last_completed_bar() -> None:
    """No look-ahead: the signal keys off the last row of the slice it is given."""
    config = StrategyConfig(strategy_type=StrategyType.BOLLINGER_REVERSION)
    base = [100.0] * 19
    # last bar is the drop -> buy
    assert evaluate_strategy(frame(base + [99.0]), config).action == "buy"
    # same drop but followed by a normal bar -> last row is normal -> not buy
    assert evaluate_strategy(frame(base + [99.0, 100.0]), config).action != "buy"
