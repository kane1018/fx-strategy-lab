from datetime import datetime

from sqlalchemy.orm import Session

from app.models import BacktestRun, BacktestTrade, OrderLog, PaperTrade, PaperTradeSession
from app.services.performance_service import (
    _max_drawdown,
    _trade_stats,
    mock_e2e_performance,
    paper_performance,
    performance_report,
)


def test_trade_stats_math_and_expectancy_matches_avg_pnl() -> None:
    # 3 wins (+10,+20,+30), 2 losses (-5,-15) -> 5 completed trades.
    stats = _trade_stats([10, 20, 30, -5, -15])
    assert stats["completed_trades"] == 5
    assert stats["wins"] == 3
    assert stats["losses"] == 2
    assert stats["win_rate"] == 60.0
    assert stats["total_pnl"] == 40.0
    assert stats["avg_win"] == 20.0  # 60/3
    assert stats["avg_loss"] == 10.0  # 20/2 (positive magnitude)
    # expectancy = 0.6*20 - 0.4*10 = 8.0 ; avg per trade = 40/5 = 8.0 -> must match
    assert stats["expectancy"] == 8.0
    assert stats["avg_pnl_per_trade"] == 8.0
    assert stats["expectancy"] == stats["avg_pnl_per_trade"]
    assert stats["profit_factor"] == 3.0  # 60 / 20
    assert stats["reference_only"] is True  # < 30 trades


def test_trade_stats_empty_is_reference_only() -> None:
    stats = _trade_stats([])
    assert stats["completed_trades"] == 0
    assert stats["profit_factor"] is None
    assert stats["reference_only"] is True


def test_max_drawdown_curve() -> None:
    # equity: 10, 5, 25, 20 -> peak 25 then dip to 20 => dd 5; earlier 10->5 dd 5
    assert _max_drawdown([10, -5, 20, -5]) == 5.0
    assert _max_drawdown([-10, -10]) == 20.0


def test_backtest_aggregation_separates_symbol_and_strategy(db: Session) -> None:
    run = BacktestRun(
        symbol="USD_JPY",
        timeframe="H1",
        strategy_type="moving_average_cross",
        request_json={},
        metrics_json={"max_drawdown": 12.5},
    )
    db.add(run)
    db.flush()
    for pnl in (10.0, -4.0, 6.0):
        db.add(
            BacktestTrade(
                run_id=run.id,
                symbol="USD_JPY",
                side="buy",
                entry_time=datetime(2026, 6, 1),
                exit_time=datetime(2026, 6, 1),
                entry_price=150.0,
                exit_price=150.1,
                units=1000,
                pnl=pnl,
                entry_reason="t",
                exit_reason="t",
            )
        )
    db.commit()

    report = performance_report(db)["backtest"]
    assert report["run_count"] == 1
    assert report["symbols"] == ["USD_JPY"]
    assert report["worst_single_run_drawdown"] == 12.5
    assert report["overall"]["completed_trades"] == 3
    assert report["overall"]["total_pnl"] == 12.0
    assert report["costs_included"] is True
    assert "USD_JPY" in report["by_symbol"]
    assert "moving_average_cross" in report["by_strategy"]


def test_paper_performance_excludes_open_from_win_rate(db: Session) -> None:
    session = PaperTradeSession(
        status="stopped",
        symbol="USD_JPY",
        timeframe="M5",
        strategy_type="moving_average_cross",
        config_json={},
        initial_balance=1_000_000,
        balance=1_000_000,
    )
    db.add(session)
    db.flush()
    # 2 closed (win +8, loss -3), 1 open (unrealized +5) -> win rate from closed only.
    db.add_all(
        [
            PaperTrade(
                session_id=session.id, symbol="USD_JPY", side="buy", status="closed",
                units=1000, entry_price=150, current_price=150.08, exit_price=150.08,
                stop_loss=149.5, take_profit=150.5, realized_pnl=8.0, unrealized_pnl=0,
                entry_reason="t", closed_at=datetime(2026, 6, 1, 1),
            ),
            PaperTrade(
                session_id=session.id, symbol="USD_JPY", side="buy", status="closed",
                units=1000, entry_price=150, current_price=149.97, exit_price=149.97,
                stop_loss=149.5, take_profit=150.5, realized_pnl=-3.0, unrealized_pnl=0,
                entry_reason="t", closed_at=datetime(2026, 6, 1, 2),
            ),
            PaperTrade(
                session_id=session.id, symbol="USD_JPY", side="buy", status="open",
                units=1000, entry_price=150, current_price=150.05,
                stop_loss=149.5, take_profit=150.5, unrealized_pnl=5.0,
                entry_reason="t",
            ),
        ]
    )
    db.commit()

    paper = paper_performance(db)
    assert paper["session_count"] == 1
    assert paper["open_position_count"] == 1
    assert paper["unrealized_pnl"] == 5.0
    assert paper["overall"]["completed_trades"] == 2  # open NOT counted
    assert paper["overall"]["win_rate"] == 50.0
    assert paper["overall"]["total_pnl"] == 5.0


def test_mock_e2e_is_separated_from_strategy_performance(db: Session) -> None:
    db.add_all(
        [
            OrderLog(client_order_id="DEMO-1", mode="demo", symbol="USD_JPY", side="buy",
                     units=5, status="filled", reason="x", risk_check_json={}),
            OrderLog(client_order_id="DEMO-2", mode="demo", symbol="USD_JPY", side="buy",
                     units=5, status="closed", reason="x", risk_check_json={},
                     realized_pnl=1.0),
            OrderLog(client_order_id="DEMO-3", mode="demo", symbol="USD_JPY", side="buy",
                     units=5, status="emergency_stopped", reason="x", risk_check_json={}),
        ]
    )
    db.commit()
    op = mock_e2e_performance(db)
    assert op["mock_order_count"] == 3
    assert op["mock_fill_count"] == 2  # filled + closed
    assert op["mock_close_count"] == 1
    assert op["error_order_count"] == 1
    assert op["dry_run_count"] == 0
    assert op["excluded_from_strategy_performance"] is True
