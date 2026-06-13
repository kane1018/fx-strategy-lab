from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Signal
from app.schemas.trading import SignalMonitorRequest
from app.services.market_data_service import (
    candles_to_frame,
    generate_demo_candles,
    next_demo_price,
    pip_size,
)
from app.strategies import evaluate_strategy

NOTICE = "これは自分用の売買補助シグナルです。最終判断は必ず自分で行ってください。"


@dataclass
class MonitoredPosition:
    side: str
    entry_price: float
    stop_loss: float
    take_profit: float


@dataclass
class MonitorState:
    request: SignalMonitorRequest
    evaluation_count: int = 0
    last_price: float | None = None
    position: MonitoredPosition | None = None


monitors: dict[str, MonitorState] = {}


def start_monitor(request: SignalMonitorRequest) -> dict[str, Any]:
    monitor_id = uuid4().hex
    monitors[monitor_id] = MonitorState(request=request)
    return {"monitor_id": monitor_id, "status": "running"}


def stop_monitor(monitor_id: str) -> dict[str, Any]:
    monitors.pop(monitor_id, None)
    return {"monitor_id": monitor_id, "status": "stopped"}


def _save_signal(
    db: Session,
    *,
    monitor_id: str,
    request: SignalMonitorRequest,
    side: str,
    price: float,
    stop_loss: float,
    take_profit: float,
    reason: str,
) -> Signal:
    signal = Signal(
        monitor_id=monitor_id,
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy_name=request.strategy.strategy_type.value,
        side=side,
        price=price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reason=reason,
        risk_percent=request.execution.risk_percent,
        notice=NOTICE,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


def evaluate_monitor(db: Session, monitor_id: str) -> dict[str, Any]:
    state = monitors.get(monitor_id)
    if not state:
        raise ValueError("稼働中のシグナル監視が見つかりません")
    request = state.request
    now = datetime.utcnow()
    candles = generate_demo_candles(
        request.symbol, request.timeframe, now - timedelta(days=30), now
    )
    base_price = state.last_price or candles[-1].close
    price = next_demo_price(request.symbol, base_price, state.evaluation_count)
    state.evaluation_count += 1
    state.last_price = price
    candles[-1].close = price
    candles[-1].high = max(candles[-1].high, price)
    candles[-1].low = min(candles[-1].low, price)
    strategy_result = evaluate_strategy(candles_to_frame(candles), request.strategy)
    notification: Signal | None = None

    if state.position:
        position = state.position
        stop_hit = (
            price <= position.stop_loss if position.side == "buy" else price >= position.stop_loss
        )
        take_hit = (
            price >= position.take_profit
            if position.side == "buy"
            else price <= position.take_profit
        )
        opposite = (
            strategy_result.action in {"buy", "sell"} and strategy_result.action != position.side
        )
        if stop_hit:
            notification = _save_signal(
                db,
                monitor_id=monitor_id,
                request=request,
                side="stop_loss",
                price=price,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                reason="監視中の仮想ポジションが推奨損切り価格に到達",
            )
            state.position = None
        elif take_hit:
            notification = _save_signal(
                db,
                monitor_id=monitor_id,
                request=request,
                side="take_profit",
                price=price,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                reason="監視中の仮想ポジションが推奨利確価格に到達",
            )
            state.position = None
        elif opposite:
            notification = _save_signal(
                db,
                monitor_id=monitor_id,
                request=request,
                side="exit",
                price=price,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                reason=f"反対シグナルによる決済候補: {strategy_result.reason}",
            )
            state.position = None

    if not state.position and not notification and strategy_result.action in {"buy", "sell"}:
        pip = pip_size(request.symbol)
        stop_distance = request.execution.stop_loss_pips * pip
        take_distance = request.execution.take_profit_pips * pip
        stop = price - stop_distance if strategy_result.action == "buy" else price + stop_distance
        take = price + take_distance if strategy_result.action == "buy" else price - take_distance
        state.position = MonitoredPosition(
            side=strategy_result.action,
            entry_price=price,
            stop_loss=stop,
            take_profit=take,
        )
        notification = _save_signal(
            db,
            monitor_id=monitor_id,
            request=request,
            side=strategy_result.action,
            price=price,
            stop_loss=stop,
            take_profit=take,
            reason=strategy_result.reason,
        )

    return {
        "monitor_id": monitor_id,
        "status": "running",
        "current_price": price,
        "action": notification.side if notification else strategy_result.action,
        "reason": notification.reason if notification else strategy_result.reason,
        "notification": serialize_signal(notification) if notification else None,
        "monitored_position": (
            {
                "side": state.position.side,
                "entry_price": state.position.entry_price,
                "stop_loss": state.position.stop_loss,
                "take_profit": state.position.take_profit,
            }
            if state.position
            else None
        ),
    }


def serialize_signal(signal: Signal) -> dict[str, Any]:
    return {
        "id": signal.id,
        "monitor_id": signal.monitor_id,
        "symbol": signal.symbol,
        "timeframe": signal.timeframe,
        "strategy_name": signal.strategy_name,
        "side": signal.side,
        "price": signal.price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "reason": signal.reason,
        "risk_percent": signal.risk_percent,
        "notice": signal.notice,
        "created_at": signal.created_at.isoformat(),
    }


def signal_history(db: Session) -> list[dict[str, Any]]:
    signals = db.scalars(select(Signal).order_by(Signal.created_at.desc()).limit(100)).all()
    return [serialize_signal(signal) for signal in signals]
