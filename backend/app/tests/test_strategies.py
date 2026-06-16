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


def ohlc(bars: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(bars, columns=["open", "high", "low", "close"])


_FLAT = [(100.0, 100.1, 99.9, 100.0)] * 11  # 11 calm bars (lookback 12 needs >=12)


def test_market_structure_defaults_are_lookback12_wick40() -> None:
    config = StrategyConfig(strategy_type=StrategyType.MARKET_STRUCTURE_REVERSION)
    assert config.swing_lookback == 12
    assert config.swing_wick_ratio == 0.4


def test_market_structure_buy_on_swing_low_with_lower_wick() -> None:
    config = StrategyConfig(strategy_type=StrategyType.MARKET_STRUCTURE_REVERSION)
    # new swing low with a long lower wick (rejection): range 0.95, lower wick 0.9
    bar = (99.9, 99.95, 99.0, 99.95)
    assert evaluate_strategy(ohlc([*_FLAT, bar]), config).action == "buy"


def test_market_structure_sell_on_swing_high_with_upper_wick() -> None:
    config = StrategyConfig(strategy_type=StrategyType.MARKET_STRUCTURE_REVERSION)
    # new swing high with a long upper wick: range 1.0, upper wick 0.95
    bar = (100.05, 101.0, 100.0, 100.0)
    assert evaluate_strategy(ohlc([*_FLAT, bar]), config).action == "sell"


def test_market_structure_holds_without_wick_or_on_warmup() -> None:
    config = StrategyConfig(strategy_type=StrategyType.MARKET_STRUCTURE_REVERSION)
    # new swing low but no lower wick (close == low) -> hold
    no_wick = (99.1, 99.2, 99.0, 99.0)
    assert evaluate_strategy(ohlc([*_FLAT, no_wick]), config).action == "hold"
    # fewer than lookback bars -> warmup hold
    assert evaluate_strategy(ohlc(_FLAT[:5]), config).action == "hold"


def test_market_structure_uses_only_last_completed_bar() -> None:
    """No look-ahead: a swing-low wick bar fires only when it is the last row."""
    config = StrategyConfig(strategy_type=StrategyType.MARKET_STRUCTURE_REVERSION)
    bar = (99.9, 99.95, 99.0, 99.95)
    assert evaluate_strategy(ohlc([*_FLAT, bar]), config).action == "buy"
    # same bar followed by a calm bar -> last row is calm -> not buy
    followed = ohlc([*_FLAT, bar, (100.0, 100.1, 99.9, 100.0)])
    assert evaluate_strategy(followed, config).action != "buy"
