from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.schemas.trading import (
    BacktestRequest,
    Candle,
    ExecutionConfig,
    StrategyConfig,
    StrategyType,
)
from app.services.backtest_service import run_backtest


def test_backtest_persists_run_and_applies_costs(db: Session) -> None:
    start = datetime(2025, 1, 1)
    closes = [100, 99, 98, 97, 98, 100, 102, 101, 99, 97, 96, 98, 101]
    candles = [
        Candle(
            timestamp=start + timedelta(hours=index),
            open=value,
            high=value + 0.5,
            low=value - 0.5,
            close=value,
        )
        for index, value in enumerate(closes)
    ]
    response = run_backtest(
        db,
        BacktestRequest(
            symbol="EUR_USD",
            timeframe="H1",
            start=start,
            end=start + timedelta(hours=len(candles)),
            candles=candles,
            strategy=StrategyConfig(
                strategy_type=StrategyType.MOVING_AVERAGE_CROSS,
                short_period=2,
                long_period=3,
            ),
            execution=ExecutionConfig(
                initial_capital=10_000,
                fixed_units=100,
                stop_loss_pips=10_000,
                take_profit_pips=10_000,
                spread_pips=2,
                slippage_pips=1,
                commission_per_trade=1,
            ),
        ),
    )
    assert response.run_id > 0
    assert response.metrics.trade_count > 0
    assert all(trade.entry_time > start for trade in response.trades)
    assert response.warnings
