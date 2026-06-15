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


def _reversal_prices() -> list[float]:
    # Flat, then climb (breakout buy), then a sustained drop (opposite sell signal).
    flat = [150.00] * 8
    climb = [150.00 + 0.05 * s for s in range(1, 13)]   # up to ~150.60
    drop = [150.60 - 0.05 * s for s in range(1, 25)]     # down through entry -> SL territory
    return flat + climb + drop


def test_exit_policy_no_opposite_signal_exit_changes_exits(db: Session) -> None:
    from app.models import PaperTradeSession
    candles = _series(_reversal_prices())
    strat = StrategyConfig(strategy_type=StrategyType.BREAKOUT, breakout_period=2)
    execution = ExecutionConfig(stop_loss_pips=30, take_profit_pips=60, fixed_units=1000)

    base = replay_paper_trades(
        db, symbol="USD_JPY", timeframe="M1", candles=candles,
        strategy=strat, execution=execution, exit_policy="baseline",
    )
    base_trades = db.scalars(
        select(PaperTrade).where(PaperTrade.session_id == base["session_id"])
    ).all()
    assert any("反対シグナル" in (t.exit_reason or "") for t in base_trades)

    nop = replay_paper_trades(
        db, symbol="USD_JPY", timeframe="M1", candles=candles,
        strategy=strat, execution=execution, exit_policy="no_opposite_signal_exit",
    )
    nop_trades = db.scalars(
        select(PaperTrade).where(PaperTrade.session_id == nop["session_id"])
    ).all()
    assert all("反対シグナル" not in (t.exit_reason or "") for t in nop_trades)
    # the session records which policy produced it
    nop_session = db.get(PaperTradeSession, nop["session_id"])
    assert nop_session.config_json["exit_policy"] == "no_opposite_signal_exit"


def test_force_close_at_end_leaves_no_open_position(db: Session) -> None:
    candles = _series(_trending_prices())
    strat = StrategyConfig(strategy_type=StrategyType.BREAKOUT, breakout_period=2)
    result = replay_paper_trades(
        db, symbol="USD_JPY", timeframe="M1", candles=candles, strategy=strat,
        execution=ExecutionConfig(stop_loss_pips=20, take_profit_pips=20, fixed_units=1000),
        exit_policy="no_opposite_signal_exit", force_close_at_end=True,
    )
    assert result["open_position_count"] == 0


def test_replay_rejects_unknown_exit_policy(db: Session) -> None:
    import pytest
    with pytest.raises(ValueError, match="exit_policy"):
        replay_paper_trades(
            db, symbol="USD_JPY", timeframe="M1", candles=_series(_trending_prices()),
            strategy=StrategyConfig(), execution=ExecutionConfig(), exit_policy="bogus",
        )


def test_fast_signals_match_exact_for_rsi(db: Session) -> None:
    # Vectorized RSI signals must produce identical trades to the per-bar path.
    import numpy as np
    rng = np.random.default_rng(7)
    prices = [150.0]
    for _ in range(300):
        prices.append(round(prices[-1] + float(rng.normal(0, 0.05)), 3))
    candles = _series(prices)
    strat = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    exact = replay_paper_trades(
        db, symbol="USD_JPY", timeframe="M1", candles=candles, strategy=strat,
        execution=ExecutionConfig(), exit_policy="baseline", fast_signals=False,
    )
    fast = replay_paper_trades(
        db, symbol="USD_JPY", timeframe="M1", candles=candles, strategy=strat,
        execution=ExecutionConfig(), exit_policy="baseline", fast_signals=True,
    )
    assert exact["completed_trades"] == fast["completed_trades"]
    assert exact["signal_counts"] == fast["signal_counts"]


def test_time_stop_30m_closes_after_30_minutes(db: Session) -> None:
    # rise (rsi won't buy here) — use breakout to open quickly, then flat hold so
    # neither SL/TP nor opposite fire; only the time stop should close it.
    prices = [150.0] * 6 + [150.0 + 0.05 * s for s in range(1, 6)] + [150.25] * 90
    candles = _series(prices)
    strat = StrategyConfig(strategy_type=StrategyType.BREAKOUT, breakout_period=2)
    execution = ExecutionConfig(stop_loss_pips=80, take_profit_pips=80, fixed_units=1000)
    res = replay_paper_trades(
        db, symbol="USD_JPY", timeframe="M1", candles=candles, strategy=strat,
        execution=execution, exit_policy="time_stop_30m",
    )
    trades = db.scalars(
        select(PaperTrade).where(PaperTrade.session_id == res["session_id"])
    ).all()
    stop_trades = [t for t in trades if t.exit_reason == "時間ストップ30分"]
    assert stop_trades, "time_stop_30m should produce at least one time-stop exit"
    t = stop_trades[0]
    held_min = (t.closed_at - t.opened_at).total_seconds() / 60
    assert 30 <= held_min <= 31  # closes on the first bar at/after 30 minutes


def test_time_stop_60m_holds_longer_than_30m(db: Session) -> None:
    prices = [150.0] * 6 + [150.0 + 0.05 * s for s in range(1, 6)] + [150.25] * 120
    candles = _series(prices)
    strat = StrategyConfig(strategy_type=StrategyType.BREAKOUT, breakout_period=2)
    execution = ExecutionConfig(stop_loss_pips=80, take_profit_pips=80, fixed_units=1000)
    res = replay_paper_trades(
        db, symbol="USD_JPY", timeframe="M1", candles=candles, strategy=strat,
        execution=execution, exit_policy="time_stop_60m",
    )
    trades = db.scalars(
        select(PaperTrade).where(
            PaperTrade.session_id == res["session_id"],
            PaperTrade.exit_reason == "時間ストップ60分",
        )
    ).all()
    assert trades
    held = (trades[0].closed_at - trades[0].opened_at).total_seconds() / 60
    assert 60 <= held <= 61


def test_continuous_replay_holds_position_across_day_boundary(db: Session) -> None:
    from datetime import timedelta

    from app.models import PaperTradeSession
    # Build a series that opens a breakout buy near a UTC midnight and then stays
    # flat across the boundary; no SL/TP/opposite -> the position must survive the
    # day change (continuous replay does NOT force-close per day).
    base = datetime(2026, 6, 1, 23, 50)
    prices = [150.0] * 3 + [150.05, 150.10, 150.15] + [150.15] * 60
    candles = [
        Candle(
            timestamp=base + timedelta(minutes=i),
            open=(prices[i - 1] if i else prices[0]),
            high=max(prices[i - 1] if i else prices[0], prices[i]) + 0.02,
            low=min(prices[i - 1] if i else prices[0], prices[i]) - 0.02,
            close=prices[i], volume=0,
        )
        for i in range(len(prices))
    ]
    strat = StrategyConfig(strategy_type=StrategyType.BREAKOUT, breakout_period=2)
    res = replay_paper_trades(
        db, symbol="USD_JPY", timeframe="M1", candles=candles, strategy=strat,
        execution=ExecutionConfig(stop_loss_pips=80, take_profit_pips=80, fixed_units=1000),
        exit_policy="time_stop_60m",
    )
    session = db.get(PaperTradeSession, res["session_id"])
    trades = db.scalars(select(PaperTrade).where(PaperTrade.session_id == session.id)).all()
    # A trade that opened before midnight and closed after it proves cross-day holding.
    spanning = [
        t for t in trades
        if t.closed_at and t.opened_at.date() != t.closed_at.date()
    ]
    assert spanning, "expected a position held across the UTC day boundary"


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
