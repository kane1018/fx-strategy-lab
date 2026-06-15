"""Replay GMO Public klines through the existing strategy as PAPER trades.

No real orders, no Private API, no broker order call. Given a list of candles
(e.g. fetched read-only from GMO Public API), this opens/closes VIRTUAL positions
and persists them as PaperTrade rows under a PaperTradeSession so that
performance_service.paper_performance can aggregate them. Completed (closed)
trades count toward strategy stats; a still-open final position is recorded
separately as an open paper position (unrealized).

This module is pure simulation over provided candles: it never performs network
or broker I/O itself.
"""

from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.models import PaperTrade, PaperTradeSession
from app.schemas.trading import Candle, ExecutionConfig, StrategyConfig
from app.services.market_data_service import candles_to_frame, pip_size
from app.services.paper_trade_service import _pnl
from app.strategies import evaluate_strategy


def _close_trade(
    session: PaperTradeSession,
    symbol: str,
    execution: ExecutionConfig,
    position: dict[str, Any],
    exit_price: float,
    exit_reason: str,
    closed_at: datetime,
) -> PaperTrade:
    pnl = (
        _pnl(symbol, position["side"], position["entry_price"], exit_price, position["units"])
        - execution.commission_per_trade
    )
    session.balance += pnl
    session.realized_pnl += pnl
    return PaperTrade(
        session_id=session.id,
        symbol=symbol,
        side=position["side"],
        status="closed",
        units=position["units"],
        entry_price=position["entry_price"],
        current_price=exit_price,
        exit_price=exit_price,
        stop_loss=position["stop_loss"],
        take_profit=position["take_profit"],
        unrealized_pnl=0,
        realized_pnl=round(pnl, 4),
        entry_reason=position["entry_reason"],
        exit_reason=exit_reason,
        opened_at=position["opened_at"],
        closed_at=closed_at,
    )


def replay_paper_trades(
    db: Session,
    *,
    symbol: str,
    timeframe: str,
    candles: list[Candle],
    strategy: StrategyConfig,
    execution: ExecutionConfig,
    source: str = "gmo_public_kline",
) -> dict[str, Any]:
    if len(candles) < 3:
        raise ValueError("リプレイに必要な足が不足しています（3本以上必要）")
    frame = candles_to_frame(candles)
    pip = pip_size(symbol)
    friction = pip * (execution.spread_pips / 2 + execution.slippage_pips)

    session = PaperTradeSession(
        status="running",
        symbol=symbol,
        timeframe=timeframe,
        strategy_type=strategy.strategy_type.value,
        config_json={
            "source": source,
            "bars": len(candles),
            "strategy": strategy.model_dump(mode="json"),
            "execution": execution.model_dump(mode="json"),
        },
        initial_balance=execution.initial_capital,
        balance=execution.initial_capital,
    )
    db.add(session)
    db.flush()

    position: dict[str, Any] | None = None
    completed = 0
    signal_counts = {"buy": 0, "sell": 0, "hold": 0}

    for index in range(2, len(frame)):
        row = frame.iloc[index]
        timestamp = pd.Timestamp(row["timestamp"]).to_pydatetime()
        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        signal = evaluate_strategy(frame.iloc[:index], strategy)
        signal_counts[signal.action] = signal_counts.get(signal.action, 0) + 1

        # Close on an opposite signal at the next bar's open (no look-ahead).
        if position and signal.action in {"buy", "sell"} and signal.action != position["side"]:
            exit_price = (
                open_price - friction if position["side"] == "buy" else open_price + friction
            )
            db.add(
                _close_trade(
                    session, symbol, execution, position, exit_price,
                    f"反対シグナル: {signal.reason}", timestamp,
                )
            )
            completed += 1
            position = None

        # Open a virtual position at the bar open if flat and signalled.
        if not position and signal.action in {"buy", "sell"}:
            side = signal.action
            entry = open_price + friction if side == "buy" else open_price - friction
            units = min(execution.fixed_units or 1000, session.balance * execution.leverage / entry)
            stop_distance = execution.stop_loss_pips * pip
            take_distance = execution.take_profit_pips * pip
            stop = entry - stop_distance if side == "buy" else entry + stop_distance
            take = entry + take_distance if side == "buy" else entry - take_distance
            max_risk = abs(_pnl(symbol, side, entry, stop, units))
            if units > 0 and max_risk <= session.balance * execution.max_loss_percent / 100:
                position = {
                    "side": side,
                    "entry_price": entry,
                    "units": units,
                    "stop_loss": stop,
                    "take_profit": take,
                    "entry_reason": signal.reason,
                    "opened_at": timestamp,
                }

        # Intrabar SL/TP via high/low; stop is checked first (conservative).
        if position:
            exit_raw: float | None = None
            reason = ""
            if position["side"] == "buy":
                if low <= position["stop_loss"]:
                    exit_raw, reason = position["stop_loss"], "損切り到達"
                elif high >= position["take_profit"]:
                    exit_raw, reason = position["take_profit"], "利確到達"
            else:
                if high >= position["stop_loss"]:
                    exit_raw, reason = position["stop_loss"], "損切り到達"
                elif low <= position["take_profit"]:
                    exit_raw, reason = position["take_profit"], "利確到達"
            if exit_raw is not None:
                exit_price = (
                    exit_raw - friction if position["side"] == "buy" else exit_raw + friction
                )
                db.add(
                    _close_trade(
                        session, symbol, execution, position, exit_price, reason, timestamp
                    )
                )
                completed += 1
                position = None

    open_position_count = 0
    if position:
        # Leave the final position OPEN and record it as an unrealized paper position.
        last_close = float(frame.iloc[-1]["close"])
        unrealized = _pnl(
            symbol, position["side"], position["entry_price"], last_close, position["units"]
        )
        db.add(
            PaperTrade(
                session_id=session.id,
                symbol=symbol,
                side=position["side"],
                status="open",
                units=position["units"],
                entry_price=position["entry_price"],
                current_price=last_close,
                stop_loss=position["stop_loss"],
                take_profit=position["take_profit"],
                unrealized_pnl=round(unrealized, 4),
                entry_reason=position["entry_reason"],
                opened_at=position["opened_at"],
            )
        )
        open_position_count = 1

    session.status = "stopped"
    session.stopped_at = datetime.utcnow()
    db.commit()
    return {
        "session_id": session.id,
        "bars": len(candles),
        "completed_trades": completed,
        "open_position_count": open_position_count,
        "signal_counts": signal_counts,
    }
