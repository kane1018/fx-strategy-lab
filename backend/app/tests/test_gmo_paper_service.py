from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PaperTrade, PaperTradeSession
from app.schemas.trading import Candle, ExecutionConfig, StrategyConfig, StrategyType
from app.services.gmo_paper_service import replay_paper_trades
from app.services.performance_service import paper_performance


def _series(prices: list[float]) -> list[Candle]:
    base = datetime(2026, 6, 15, 0, 0)
    candles: list[Candle] = []
    for i, close in enumerate(prices):
        prev = prices[i - 1] if i else close
        candles.append(
            Candle(
                timestamp=base + timedelta(minutes=i),
                open=prev,
                high=max(prev, close) + 0.02,
                low=min(prev, close) - 0.02,
                close=close,
                volume=0,
            )
        )
    return candles


def _trending_prices() -> list[float]:
    # Flat base so a 2-bar breakout does not trigger, then a steady climb that
    # breaks out (buy) and runs far enough to hit take-profit.
    flat = [150.00] * 12
    climb = [150.00 + 0.05 * step for step in range(1, 26)]
    return flat + climb


def test_replay_persists_paper_trades_and_feeds_performance(db: Session) -> None:
    candles = _series(_trending_prices())
    strategy = StrategyConfig(strategy_type=StrategyType.BREAKOUT, breakout_period=2)
    result = replay_paper_trades(
        db,
        symbol="USD_JPY",
        timeframe="M1",
        candles=candles,
        strategy=strategy,
        execution=ExecutionConfig(stop_loss_pips=20, take_profit_pips=20, fixed_units=1000),
    )

    assert result["bars"] == len(candles)
    assert result["signal_counts"]["buy"] > 0
    # A session and at least one paper trade (closed or open) must be persisted.
    session = db.scalar(select(PaperTradeSession))
    assert session is not None and session.status == "stopped"
    assert session.config_json["source"] == "gmo_public_kline"
    trades = db.scalars(select(PaperTrade)).all()
    assert len(trades) >= 1
    assert result["completed_trades"] + result["open_position_count"] == len(trades)

    # performance_service must categorize these as paper trades.
    paper = paper_performance(db)
    assert paper["session_count"] == 1
    completed = paper["overall"]["completed_trades"]
    assert completed == result["completed_trades"]
    if completed:
        # expectancy equals average pnl per completed trade by construction.
        assert paper["overall"]["expectancy"] == paper["overall"]["avg_pnl_per_trade"]


def test_replay_requires_minimum_bars(db: Session) -> None:
    import pytest

    with pytest.raises(ValueError, match="不足"):
        replay_paper_trades(
            db,
            symbol="USD_JPY",
            timeframe="M1",
            candles=_series([150.0, 150.1]),
            strategy=StrategyConfig(),
            execution=ExecutionConfig(),
        )


def test_replay_with_no_signal_creates_session_but_no_trades(db: Session) -> None:
    # Perfectly flat series -> no breakout, no trades.
    candles = _series([150.0] * 40)
    result = replay_paper_trades(
        db,
        symbol="USD_JPY",
        timeframe="M1",
        candles=candles,
        strategy=StrategyConfig(strategy_type=StrategyType.BREAKOUT, breakout_period=2),
        execution=ExecutionConfig(),
    )
    assert result["completed_trades"] == 0
    assert result["open_position_count"] == 0
    assert db.scalar(select(PaperTradeSession)) is not None
    assert db.scalars(select(PaperTrade)).all() == []
