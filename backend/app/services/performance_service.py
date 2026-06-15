"""Read-only performance aggregation over virtual-trading history.

Keeps four categories strictly separate so operational/system-check activity
(mock E2E orders, dry-run) is never mixed into strategy performance:

  1. backtest        — BacktestRun / BacktestTrade (synthetic OHLC, costs applied)
  2. paper           — PaperTradeSession / PaperTrade
  3. mock_e2e        — OrderLog in demo mode (system-check only, NOT strategy edge)
  4. dry_run         — OrderLog with status "dry_run" (GMO design; not yet persisted)

Win rate / expectancy use COMPLETED trades only (a realized PnL). Open positions
are reported separately as unrealized PnL and never counted in win rate.

This module is read-only: it never calls a broker, never connects to an API, and
never writes to the database.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BacktestRun, BacktestTrade, OrderLog, PaperTrade, PaperTradeSession


def _trade_stats(pnls: list[float]) -> dict[str, Any]:
    """Aggregate completed-trade PnLs. avg_loss is a positive magnitude so that
    expectancy = win_rate * avg_win - loss_rate * avg_loss."""
    count = len(pnls)
    if count == 0:
        return {
            "completed_trades": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "total_pnl": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy": 0.0,
            "avg_pnl_per_trade": 0.0,
            "profit_factor": None,
            "max_profit": 0.0,
            "max_loss": 0.0,
            "max_drawdown": 0.0,
            "reference_only": True,
        }
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    breakeven = [p for p in pnls if p == 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    win_rate = len(wins) / count
    loss_rate = len(losses) / count
    avg_win = gross_profit / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    total = sum(pnls)
    return {
        "completed_trades": count,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate": round(win_rate * 100, 2),
        "loss_rate": round(loss_rate * 100, 2),
        "total_pnl": round(total, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(win_rate * avg_win - loss_rate * avg_loss, 4),
        "avg_pnl_per_trade": round(total / count, 4),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "max_profit": round(max(pnls), 2),
        "max_loss": round(min(pnls), 2),
        "max_drawdown": round(_max_drawdown(pnls), 2),
        # Fewer than 30 completed trades is statistically weak: flag as reference only.
        "reference_only": count < 30,
    }


def _max_drawdown(ordered_pnls: list[float]) -> float:
    """Max peak-to-trough drawdown of the cumulative PnL curve (positive magnitude)."""
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in ordered_pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def backtest_performance(db: Session) -> dict[str, Any]:
    runs = db.scalars(select(BacktestRun).order_by(BacktestRun.id)).all()
    trades = db.scalars(select(BacktestTrade).order_by(BacktestTrade.id)).all()
    pnls = [float(trade.pnl) for trade in trades]
    by_strategy: dict[str, list[float]] = {}
    by_symbol: dict[str, list[float]] = {}
    for trade in trades:
        run = db.get(BacktestRun, trade.run_id)
        strat = run.strategy_type if run else "unknown"
        by_strategy.setdefault(strat, []).append(float(trade.pnl))
        by_symbol.setdefault(trade.symbol, []).append(float(trade.pnl))
    return {
        "category": "backtest",
        "costs_included": True,  # spread, slippage and commission are applied in backtests
        "run_count": len(runs),
        "symbols": sorted({trade.symbol for trade in trades}),
        "strategies": sorted({run.strategy_type for run in runs}),
        "worst_single_run_drawdown": round(
            max((float(run.metrics_json.get("max_drawdown", 0)) for run in runs), default=0.0),
            2,
        ),
        "overall": _trade_stats(pnls),
        "by_strategy": {name: _trade_stats(values) for name, values in by_strategy.items()},
        "by_symbol": {name: _trade_stats(values) for name, values in by_symbol.items()},
    }


def paper_performance(db: Session) -> dict[str, Any]:
    sessions = db.scalars(select(PaperTradeSession)).all()
    trades = db.scalars(
        select(PaperTrade).order_by(PaperTrade.closed_at, PaperTrade.id)
    ).all()
    closed = [t for t in trades if t.status == "closed" and t.realized_pnl is not None]
    open_trades = [t for t in trades if t.status == "open"]
    pnls = [float(t.realized_pnl) for t in closed]
    return {
        "category": "paper",
        "session_count": len(sessions),
        "open_position_count": len(open_trades),
        "unrealized_pnl": round(sum(float(t.unrealized_pnl) for t in open_trades), 2),
        "overall": _trade_stats(pnls),
    }


def mock_e2e_performance(db: Session) -> dict[str, Any]:
    """Operational system-check counts from OrderLog. NOT strategy performance."""
    orders = db.scalars(select(OrderLog)).all()
    demo = [o for o in orders if o.mode == "demo"]
    practice = [o for o in orders if o.mode == "practice"]
    dry_run = [o for o in orders if o.status == "dry_run"]
    fills = [o for o in demo if o.status in {"filled", "closed"}]
    closes = [o for o in demo if o.status == "closed"]
    error_statuses = {"emergency_stopped", "close_failed", "close_unconfirmed"}
    errors = [o for o in orders if o.status in error_statuses]
    return {
        "category": "operational_system_check",
        "note": "動作確認用。戦略成績には含めない。",
        "mock_order_count": len(demo),
        "mock_fill_count": len(fills),
        "mock_close_count": len(closes),
        "practice_order_count": len(practice),
        "dry_run_count": len(dry_run),
        "error_order_count": len(errors),
        "excluded_from_strategy_performance": True,
    }


def performance_report(db: Session) -> dict[str, Any]:
    return {
        "backtest": backtest_performance(db),
        "paper": paper_performance(db),
        "operational": mock_e2e_performance(db),
    }
