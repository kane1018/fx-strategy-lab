from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PaperTrade, PaperTradeSession
from app.schemas.trading import Candle, PaperSessionRequest, PaperTickRequest, Side
from app.services.market_data_service import (
    candles_to_frame,
    generate_demo_candles,
    next_demo_price,
    pip_size,
)
from app.strategies import evaluate_strategy


def serialize_trade(trade: PaperTrade) -> dict[str, Any]:
    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side,
        "status": trade.status,
        "units": trade.units,
        "entry_price": trade.entry_price,
        "current_price": trade.current_price,
        "exit_price": trade.exit_price,
        "stop_loss": trade.stop_loss,
        "take_profit": trade.take_profit,
        "unrealized_pnl": round(trade.unrealized_pnl, 2),
        "realized_pnl": trade.realized_pnl,
        "entry_reason": trade.entry_reason,
        "exit_reason": trade.exit_reason,
        "opened_at": trade.opened_at.isoformat(),
        "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
    }


def session_snapshot(db: Session, session: PaperTradeSession) -> dict[str, Any]:
    trades = db.scalars(
        select(PaperTrade)
        .where(PaperTrade.session_id == session.id)
        .order_by(PaperTrade.opened_at.desc())
    ).all()
    open_trades = [trade for trade in trades if trade.status == "open"]
    today = datetime.now(UTC).date()
    today_closed = [
        trade for trade in trades if trade.closed_at and trade.closed_at.date() == today
    ]
    unrealized = sum(trade.unrealized_pnl for trade in open_trades)
    return {
        "id": session.id,
        "status": session.status,
        "symbol": session.symbol,
        "timeframe": session.timeframe,
        "strategy_type": session.strategy_type,
        "balance": round(session.balance, 2),
        "equity": round(session.balance + unrealized, 2),
        "realized_pnl": round(session.realized_pnl, 2),
        "unrealized_pnl": round(unrealized, 2),
        "today_trade_count": len(today_closed),
        "today_max_loss": round(
            min((trade.realized_pnl or 0 for trade in today_closed), default=0),
            2,
        ),
        "error_message": session.error_message,
        "open_positions": [serialize_trade(trade) for trade in open_trades],
        "trades": [serialize_trade(trade) for trade in trades[:50]],
    }


def start_session(db: Session, request: PaperSessionRequest) -> dict[str, Any]:
    active = db.scalar(select(PaperTradeSession).where(PaperTradeSession.status == "running"))
    if active:
        stop_session(db, active.id, "新しいセッション開始")
    session = PaperTradeSession(
        status="running",
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy_type=request.strategy.strategy_type.value,
        config_json=request.model_dump(mode="json"),
        initial_balance=request.execution.initial_capital,
        balance=request.execution.initial_capital,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session_snapshot(db, session)


def stop_session(db: Session, session_id: int, reason: str = "手動停止") -> dict[str, Any]:
    session = db.get(PaperTradeSession, session_id)
    if not session:
        raise ValueError("ペーパートレードセッションが見つかりません")
    config = PaperSessionRequest.model_validate(session.config_json)
    open_trades = db.scalars(
        select(PaperTrade).where(
            PaperTrade.session_id == session.id,
            PaperTrade.status == "open",
        )
    ).all()
    for trade in open_trades:
        trade.status = "closed"
        trade.exit_price = trade.current_price
        trade.realized_pnl = (
            _pnl(
                trade.symbol,
                trade.side,
                trade.entry_price,
                trade.current_price,
                trade.units,
            )
            - config.execution.commission_per_trade
        )
        trade.unrealized_pnl = 0
        trade.exit_reason = reason
        trade.closed_at = datetime.utcnow()
        session.balance += trade.realized_pnl
        session.realized_pnl += trade.realized_pnl
    session.status = "stopped"
    session.error_message = reason
    session.stopped_at = datetime.utcnow()
    db.commit()
    return session_snapshot(db, session)


def error_stop_session(db: Session, session_id: int, reason: str) -> None:
    session = db.get(PaperTradeSession, session_id)
    if not session:
        return
    stop_session(db, session_id, reason)
    session = db.get(PaperTradeSession, session_id)
    session.status = "error_stopped"
    session.error_message = reason
    db.commit()


def _pnl(symbol: str, side: str, entry: float, current: float, units: float) -> float:
    delta = current - entry if side == "buy" else entry - current
    conversion = 1 / current if symbol.endswith("JPY") else 1
    return delta * units * conversion


def process_tick(db: Session, session_id: int, tick: PaperTickRequest) -> dict[str, Any]:
    session = db.get(PaperTradeSession, session_id)
    if not session:
        raise ValueError("ペーパートレードセッションが見つかりません")
    if session.status != "running":
        raise ValueError("停止中のセッションには価格を投入できません")

    config = PaperSessionRequest.model_validate(session.config_json)
    trades = db.scalars(select(PaperTrade).where(PaperTrade.session_id == session.id)).all()
    open_trade = next((trade for trade in trades if trade.status == "open"), None)
    tick_index = len(trades) + int((datetime.utcnow() - session.started_at).total_seconds() // 2)
    previous_price = (
        open_trade.current_price
        if open_trade
        else generate_demo_candles(
            session.symbol,
            session.timeframe,
            datetime.utcnow() - timedelta(days=5),
            datetime.utcnow(),
        )[-1].close
    )
    price = tick.price or next_demo_price(session.symbol, previous_price, tick_index)

    if open_trade:
        open_trade.current_price = price
        open_trade.unrealized_pnl = _pnl(
            session.symbol, open_trade.side, open_trade.entry_price, price, open_trade.units
        )
        hit_stop = (
            price <= open_trade.stop_loss
            if open_trade.side == "buy"
            else price >= open_trade.stop_loss
        )
        hit_take = (
            price >= open_trade.take_profit
            if open_trade.side == "buy"
            else price <= open_trade.take_profit
        )
        if hit_stop or hit_take:
            open_trade.status = "closed"
            open_trade.exit_price = price
            open_trade.realized_pnl = (
                open_trade.unrealized_pnl - config.execution.commission_per_trade
            )
            open_trade.unrealized_pnl = 0
            open_trade.exit_reason = "損切り到達" if hit_stop else "利確到達"
            open_trade.closed_at = datetime.utcnow()
            session.balance += open_trade.realized_pnl
            session.realized_pnl += open_trade.realized_pnl
            open_trade = None

    history = generate_demo_candles(
        session.symbol,
        session.timeframe,
        datetime.utcnow() - timedelta(days=20),
        datetime.utcnow(),
    )
    latest = history[-1]
    history[-1] = Candle(
        timestamp=datetime.utcnow(),
        open=latest.close,
        high=max(latest.close, price),
        low=min(latest.close, price),
        close=price,
        volume=latest.volume,
    )
    signal = evaluate_strategy(candles_to_frame(history), config.strategy)

    if not open_trade and signal.action in {"buy", "sell"}:
        pip = pip_size(session.symbol)
        side = Side(signal.action)
        friction = pip * (config.execution.spread_pips / 2 + config.execution.slippage_pips)
        entry = price + friction if side == Side.BUY else price - friction
        units = min(
            config.execution.fixed_units or 1000,
            session.balance * config.execution.leverage / entry,
        )
        stop_distance = config.execution.stop_loss_pips * pip
        take_distance = config.execution.take_profit_pips * pip
        stop_price = entry - stop_distance if side == Side.BUY else entry + stop_distance
        estimated_loss = abs(_pnl(session.symbol, side.value, entry, stop_price, units))
        if estimated_loss <= session.balance * config.execution.max_loss_percent / 100:
            trade = PaperTrade(
                session_id=session.id,
                symbol=session.symbol,
                side=side.value,
                units=units,
                entry_price=entry,
                current_price=price,
                stop_loss=entry - stop_distance if side == Side.BUY else entry + stop_distance,
                take_profit=entry + take_distance if side == Side.BUY else entry - take_distance,
                entry_reason=signal.reason,
            )
            db.add(trade)

    if session.balance <= 0:
        session.status = "risk_stopped"
        session.error_message = "仮想残高が0以下になったため停止"
        session.stopped_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    snapshot = session_snapshot(db, session)
    snapshot["current_price"] = price
    snapshot["last_signal"] = {"action": signal.action, "reason": signal.reason}
    return snapshot


def get_session(db: Session, session_id: int) -> dict[str, Any]:
    session = db.get(PaperTradeSession, session_id)
    if not session:
        raise ValueError("ペーパートレードセッションが見つかりません")
    return session_snapshot(db, session)
