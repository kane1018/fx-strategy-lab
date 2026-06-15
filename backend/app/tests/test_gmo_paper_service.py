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


def test_tighter_stop_loss_reduces_sl_loss_magnitude(db: Session) -> None:
    # Open a breakout buy, then drop sharply so the stop is hit. A 15-pip stop must
    # exit with a smaller loss than a 30-pip stop on the same data.
    prices = [150.0] * 6 + [150.0 + 0.05 * s for s in range(1, 6)] + [
        150.25 - 0.05 * s for s in range(1, 30)
    ]
    candles = _series(prices)
    strat = StrategyConfig(strategy_type=StrategyType.BREAKOUT, breakout_period=2)

    def first_sl_loss(stop_pips: float) -> float:
        # Disable opposite-signal exit so the same entry is held until its stop,
        # isolating the effect of stop_loss_pips on the SL exit price.
        res = replay_paper_trades(
            db, symbol="USD_JPY", timeframe="M1", candles=candles, strategy=strat,
            execution=ExecutionConfig(stop_loss_pips=stop_pips, take_profit_pips=200,
                                      fixed_units=1000),
            exit_policy="no_opposite_signal_exit",
        )
        sl = db.scalars(
            select(PaperTrade).where(
                PaperTrade.session_id == res["session_id"],
                PaperTrade.exit_reason == "損切り到達",
            )
        ).all()
        assert sl, f"expected an SL hit at stop_loss_pips={stop_pips}"
        return float(sl[0].realized_pnl)

    loss_15 = first_sl_loss(15)
    loss_30 = first_sl_loss(30)
    # both are losses; the tighter stop loses less (closer to zero)
    assert loss_15 < 0 and loss_30 < 0
    assert loss_15 > loss_30  # -smaller magnitude > -larger magnitude


def test_zero_cost_removes_friction_and_improves_pnl(db: Session) -> None:
    # Same data/strategy; spread=slippage=0 must yield >= total realized PnL than
    # the current-cost run (friction reduces every trade), confirming spread/slippage
    # flow through the replay.
    candles = _series(_reversal_prices())
    strat = StrategyConfig(strategy_type=StrategyType.BREAKOUT, breakout_period=2)

    def total_pnl(spread: float, slip: float) -> float:
        res = replay_paper_trades(
            db, symbol="USD_JPY", timeframe="M1", candles=candles, strategy=strat,
            execution=ExecutionConfig(spread_pips=spread, slippage_pips=slip,
                                      stop_loss_pips=30, take_profit_pips=60, fixed_units=1000),
            exit_policy="baseline",
        )
        rows = db.scalars(
            select(PaperTrade).where(
                PaperTrade.session_id == res["session_id"],
                PaperTrade.status == "closed",
            )
        ).all()
        return round(sum(float(t.realized_pnl) for t in rows), 4)

    current = total_pnl(1.2, 0.2)
    zero = total_pnl(0.0, 0.0)
    assert zero > current  # removing friction strictly improves total PnL


def test_replay_honors_higher_timeframe_spacing(db: Session) -> None:
    from app.models import PaperTradeSession

    # 5-minute-spaced candles: holding times must be multiples of 5 and the session
    # records the timeframe label, confirming timeframe flows end-to-end.
    base = datetime(2026, 6, 1, 0, 0)
    prices = [150.0] * 6 + [150.0 + 0.05 * s for s in range(1, 6)] + [150.25] * 20
    candles = [
        Candle(
            timestamp=base + timedelta(minutes=5 * i),
            open=(prices[i - 1] if i else prices[0]),
            high=max(prices[i - 1] if i else prices[0], prices[i]) + 0.02,
            low=min(prices[i - 1] if i else prices[0], prices[i]) - 0.02,
            close=prices[i], volume=0,
        )
        for i in range(len(prices))
    ]
    strat = StrategyConfig(strategy_type=StrategyType.BREAKOUT, breakout_period=2)
    res = replay_paper_trades(
        db, symbol="USD_JPY", timeframe="M5", candles=candles, strategy=strat,
        execution=ExecutionConfig(stop_loss_pips=80, take_profit_pips=80, fixed_units=1000),
        exit_policy="time_stop_30m",
    )
    session = db.get(PaperTradeSession, res["session_id"])
    assert session.timeframe == "M5"
    closed = db.scalars(
        select(PaperTrade).where(
            PaperTrade.session_id == res["session_id"], PaperTrade.status == "closed"
        )
    ).all()
    assert closed
    for t in closed:
        held = (t.closed_at - t.opened_at).total_seconds() / 60
        assert held % 5 == 0  # 5-minute granularity respected


def test_robustness_summary_aggregates_windows() -> None:
    from scripts.robustness_windows import robustness_summary

    # 2 positive windows, 3 negative -> median negative, minority positive.
    window_stats = {
        "w1": {"expectancy": 0.05, "profit_factor": 1.2, "completed_trades": 40,
               "max_drawdown": 10.0, "max_loss": -2.0},
        "w2": {"expectancy": -0.03, "profit_factor": 0.9, "completed_trades": 45,
               "max_drawdown": 12.0, "max_loss": -2.5},
        "w3": {"expectancy": 0.02, "profit_factor": 1.05, "completed_trades": 25,
               "max_drawdown": 8.0, "max_loss": -1.8},
        "w4": {"expectancy": -0.1, "profit_factor": 0.6, "completed_trades": 50,
               "max_drawdown": 20.0, "max_loss": -2.7},
        "w5": {"expectancy": -0.04, "profit_factor": 0.85, "completed_trades": 38,
               "max_drawdown": 15.0, "max_loss": -2.6},
    }
    s = robustness_summary(window_stats)
    assert s["window_count"] == 5
    assert s["positive_windows"] == 2
    assert s["negative_windows"] == 3
    assert s["edge_windows"] == 2  # w1, w3 (exp>0 & PF>1)
    assert s["median_expectancy"] == -0.03  # median of sorted exps
    assert s["windows_ge30_trades"] == 4  # w3 has 25
    assert s["max_drawdown_max"] == 20.0
    assert s["worst_single_loss"] == -2.7


def test_pattern_window_stats_excludes_symbol() -> None:
    from scripts.aud_exclusion_ab import pattern_window_stats

    def _t(symbol: str, pnl: float) -> dict:
        return {"symbol": symbol, "pnl": pnl, "closed_at": datetime(2026, 1, 1),
                "exit_category": "反対シグナル"}

    results = {
        "w1": [_t("USD_JPY", 1.0), _t("AUD_JPY", -5.0)],
        "w2": [_t("EUR_JPY", 2.0), _t("AUD_JPY", -3.0)],
    }
    all_pairs = pattern_window_stats(results, set())
    ex_aud = pattern_window_stats(results, {"AUD_JPY"})
    # all_pairs counts AUD; ex_aud drops it
    assert all_pairs["w1"]["completed_trades"] == 2
    assert ex_aud["w1"]["completed_trades"] == 1
    assert all_pairs["w1"]["total_pnl"] == -4.0
    assert ex_aud["w1"]["total_pnl"] == 1.0
    assert ex_aud["w2"]["total_pnl"] == 2.0


def test_adx_filter_blocks_entries_in_strong_trend(db: Session) -> None:
    from app.services.gmo_paper_service import adx_series

    # Strong, steady uptrend -> high ADX. A breakout buy would open every time,
    # but a low ADX cap must block (skip) those entries.
    prices = [150.0 + 0.05 * i for i in range(120)]
    candles = _series(prices)
    strat = StrategyConfig(strategy_type=StrategyType.BREAKOUT, breakout_period=2)
    execution = ExecutionConfig(stop_loss_pips=80, take_profit_pips=80, fixed_units=1000)

    no_filter = replay_paper_trades(
        db, symbol="USD_JPY", timeframe="M5", candles=candles, strategy=strat,
        execution=execution, exit_policy="baseline",
    )
    filtered = replay_paper_trades(
        db, symbol="USD_JPY", timeframe="M5", candles=candles, strategy=strat,
        execution=execution, exit_policy="baseline", entry_adx_max=20,
    )
    # baseline opens trades and skips none; the ADX cap skips entries and opens fewer.
    assert no_filter["skipped_entries"] == 0
    assert filtered["skipped_entries"] > 0
    assert filtered["completed_trades"] < no_filter["completed_trades"]
    # ADX must actually be high (strong trend) on this series
    import numpy as np

    from app.services.market_data_service import candles_to_frame
    assert np.nanmax(adx_series(candles_to_frame(candles))) >= 20


def test_adx_oos_improvement_counts() -> None:
    from scripts.adx_filter_oos_ab import improvement_counts

    base = {"w1": {"expectancy": 0.10}, "w2": {"expectancy": -0.20},
            "w3": {"expectancy": 0.05}, "w4": {"expectancy": 0.30}}
    adx = {"w1": {"expectancy": 0.15}, "w2": {"expectancy": -0.05},  # better
           "w3": {"expectancy": 0.05}, "w4": {"expectancy": 0.10}}   # w3 equal, w4 worse
    improved, worsened = improvement_counts(base, adx)
    assert improved == 2  # w1, w2
    assert worsened == 1  # w4 (w3 is equal -> neither)


def test_classify_strategy_three_way() -> None:
    from scripts.rsi_final_15window import classify_strategy

    base = dict(median_pf=1.3, positive_windows=8, n_windows=15, edge_windows=8,
                symbol_concentrated=False)
    # Robustly positive in both sub-periods -> keep as main candidate.
    keep, _ = classify_strategy(median_exp=0.2, total_pnl=50.0,
                                prior_median_exp=0.2, oos_median_exp=0.1, **base)
    assert keep == "継続検証候補"
    # Mildly positive overall but OOS negative / sign flip -> reference baseline.
    ref, _ = classify_strategy(median_exp=0.05, total_pnl=20.0,
                               prior_median_exp=0.12, oos_median_exp=-0.02, **base)
    assert ref == "研究用ベースライン"
    # Net non-positive overall -> retire.
    retire, _ = classify_strategy(
        median_exp=-0.02, total_pnl=-30.0, prior_median_exp=0.12,
        oos_median_exp=-0.02, median_pf=0.98, positive_windows=6, n_windows=15,
        edge_windows=6, symbol_concentrated=False)
    assert retire == "撤退"


def test_complement_stats_counts_rsi_loss_windows() -> None:
    from scripts.breakout_15window import complement_stats

    rsi_exp = {"a": -0.1, "b": 0.2, "c": -0.3}
    bk_stats = {"a": {"expectancy": 0.1, "total_pnl": 5.0},   # rsi neg, bk +
                "b": {"expectancy": -0.2, "total_pnl": -3.0},  # rsi +, ignored
                "c": {"expectancy": -0.05, "total_pnl": -2.0}}  # rsi neg, bk -
    out = complement_stats(rsi_exp, bk_stats)
    assert out["rsi_negative_windows"] == 2  # a, c
    assert out["breakout_positive_in_those"] == 1  # a only
    assert out["breakout_total_pnl_in_those"] == 3.0  # 5 + (-2)


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
