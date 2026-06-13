from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.brokers import DemoBroker, OandaBroker, OandaBrokerError
from app.brokers.base import Broker
from app.config import get_settings
from app.models import AutoTradeState, BrokerAccount, OrderLog
from app.schemas.trading import CloseOrderRequest, OrderRequest, RiskConfig
from app.services.bot_service import (
    emergency_stop_bot,
    get_or_create_bot_status,
    save_risk_settings,
)
from app.services.log_service import record_error
from app.services.risk_service import evaluate_order_risk


def connection_test(db: Session, mode: str) -> dict[str, Any]:
    if mode == "live":
        return {"mode": "live", "ok": False, "message": "実資金ブローカーは未接続です"}
    environment = "practice" if mode == "practice" else "demo"
    try:
        broker: Broker = OandaBroker() if mode == "practice" else DemoBroker()
        ok = broker.connection_test()
    except OandaBrokerError as error:
        record_error(db, "oanda.connection_test", str(error))
        return {"mode": "practice", "ok": False, "message": str(error)}
    account = db.scalar(
        select(BrokerAccount).where(BrokerAccount.environment == environment)
    )
    if not account:
        account = BrokerAccount(
            broker_name="oanda" if mode == "practice" else "demo",
            environment=environment,
            account_ref="configured-practice" if mode == "practice" else "local-demo",
        )
        db.add(account)
    account.api_connection_ok = ok
    account.last_connection_test_at = datetime.utcnow()
    account.enabled = ok
    db.commit()
    return {
        "mode": environment,
        "ok": ok,
        "message": "OANDA practice接続成功" if mode == "practice" else "デモブローカー接続成功",
    }


def _rejected_log(
    db: Session,
    request: OrderRequest,
    risk: RiskConfig,
    status: str,
    reasons: list[str],
) -> OrderLog:
    log = OrderLog(
        client_order_id=request.client_order_id,
        mode=request.mode,
        symbol=request.symbol,
        side=request.side.value,
        units=request.units,
        requested_price=request.current_price,
        status=status,
        reason="; ".join(reasons),
        risk_check_json={
            "allowed": False,
            "reasons": reasons,
            "settings": risk.model_dump(mode="json"),
        },
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def place_order(
    db: Session,
    request: OrderRequest,
    risk: RiskConfig,
    *,
    broker: Broker | None = None,
    open_positions_override: int | None = None,
) -> dict[str, Any]:
    existing = db.scalar(
        select(OrderLog).where(OrderLog.client_order_id == request.client_order_id)
    )
    if existing:
        return {
            "accepted": False,
            "status": "duplicate_blocked",
            "reasons": ["同一クライアント注文IDは処理済み"],
            "order_log_id": existing.id,
        }

    bot_status = get_or_create_bot_status(db)
    save_risk_settings(db, risk)
    if bot_status.status != "running" or bot_status.manual_stop_active:
        reasons = [bot_status.stop_reason or "Botが停止中"]
        log = _rejected_log(db, request, risk, "bot_stopped", reasons)
        return {
            "accepted": False,
            "status": "bot_stopped",
            "reasons": reasons,
            "order_log_id": log.id,
        }

    if request.mode == "practice":
        automation = db.scalar(
            select(AutoTradeState).order_by(AutoTradeState.id).limit(1)
        )
        if not automation or not automation.enabled:
            reasons = ["OANDA practice自動売買がOFF"]
            log = _rejected_log(db, request, risk, "bot_stopped", reasons)
            return {
                "accepted": False,
                "status": log.status,
                "reasons": reasons,
                "order_log_id": log.id,
            }
        if bot_status.mode != "practice":
            reasons = ["Botがpracticeモードで起動されていません"]
            log = _rejected_log(db, request, risk, "risk_rejected", reasons)
            return {
                "accepted": False,
                "status": log.status,
                "reasons": reasons,
                "order_log_id": log.id,
            }
        try:
            broker = broker or OandaBroker()
        except OandaBrokerError as error:
            reasons = [str(error)]
            log = _rejected_log(db, request, risk, "emergency_stopped", reasons)
            record_error(db, "oanda.order_setup", str(error))
            emergency_stop_bot(db, str(error))
            return {
                "accepted": False,
                "status": log.status,
                "reasons": reasons,
                "order_log_id": log.id,
            }
    else:
        broker = broker or DemoBroker()

    open_positions = open_positions_override
    if open_positions is None:
        open_positions = (
            db.scalar(
                select(func.count())
                .select_from(OrderLog)
                .where(OrderLog.status == "filled", OrderLog.symbol == request.symbol)
            )
            or 0
        )
    since = datetime.utcnow() - timedelta(days=1)
    realized = db.scalars(
        select(OrderLog.realized_pnl)
        .where(
            OrderLog.closed_at >= since,
            OrderLog.realized_pnl.is_not(None),
        )
        .order_by(OrderLog.closed_at.desc())
    ).all()
    daily_loss = abs(sum(value for value in realized if value and value < 0))
    consecutive_losses = 0
    for value in realized:
        if value is not None and value < 0:
            consecutive_losses += 1
        else:
            break
    decision = evaluate_order_risk(
        request,
        risk,
        get_settings(),
        open_positions=open_positions,
        daily_loss=daily_loss,
        consecutive_losses=consecutive_losses,
    )
    log = OrderLog(
        client_order_id=request.client_order_id,
        mode=request.mode,
        symbol=request.symbol,
        side=request.side.value,
        units=request.units,
        requested_price=request.current_price,
        status="risk_rejected" if not decision.allowed else "pending",
        reason="; ".join(decision.reasons) if decision.reasons else "リスクチェック通過",
        risk_check_json={
            "allowed": decision.allowed,
            "reasons": decision.reasons,
            "settings": risk.model_dump(mode="json"),
            "request": {
                "stop_loss": request.stop_loss,
                "take_profit": request.take_profit,
                "estimated_loss": request.estimated_loss,
                "spread_pips": request.spread_pips,
            },
        },
    )
    db.add(log)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {
            "accepted": False,
            "status": "duplicate_blocked",
            "reasons": ["同一クライアント注文IDの競合を検出"],
        }
    db.refresh(log)

    if not decision.allowed:
        return {
            "accepted": False,
            "status": log.status,
            "reasons": decision.reasons,
            "order_log_id": log.id,
        }

    try:
        result = broker.market_order(request)
        log.broker_order_id = result.broker_order_id
        log.filled_price = result.filled_price
        log.status = result.status
        log.reason = (
            "OANDA practice注文の約定確認済み"
            if request.mode == "practice"
            else "デモ注文約定確認済み"
        )
        log.risk_check_json = {
            **log.risk_check_json,
            "fill_transaction_id": result.fill_transaction_id,
            "trade_id": result.trade_id,
            "fill_time": result.fill_time.isoformat() if result.fill_time else None,
            "filled_units": result.filled_units,
        }
        db.commit()
        return {
            "accepted": True,
            "status": result.status,
            "broker_order_id": result.broker_order_id,
            "filled_price": result.filled_price,
            "fill_transaction_id": result.fill_transaction_id,
            "trade_id": result.trade_id,
            "order_log_id": log.id,
        }
    except Exception as error:
        log.status = "emergency_stopped"
        log.reason = f"注文または約定確認失敗: {error}"
        db.commit()
        record_error(
            db,
            "broker.order",
            str(error),
            {"mode": request.mode, "symbol": request.symbol},
        )
        emergency_stop_bot(db, log.reason)
        return {
            "accepted": False,
            "status": log.status,
            "reasons": [log.reason],
            "order_log_id": log.id,
        }


def close_order(db: Session, order_id: int, request: CloseOrderRequest) -> dict[str, Any]:
    log = db.get(OrderLog, order_id)
    if not log or log.status != "filled" or log.filled_price is None:
        raise ValueError("決済可能なデモポジションが見つかりません")
    if log.mode != "demo":
        raise ValueError("このAPIはローカルデモ注文専用です")
    delta = (
        request.exit_price - log.filled_price
        if log.side == "buy"
        else log.filled_price - request.exit_price
    )
    conversion = 1 / request.exit_price if log.symbol.endswith("JPY") else 1
    log.realized_pnl = delta * log.units * conversion
    log.status = "closed"
    log.closed_at = datetime.utcnow()
    log.reason = "デモポジション決済済み"
    db.commit()
    return {
        "id": log.id,
        "status": log.status,
        "realized_pnl": round(log.realized_pnl, 2),
        "exit_price": request.exit_price,
    }


def order_history(db: Session) -> list[dict[str, Any]]:
    logs = db.scalars(select(OrderLog).order_by(OrderLog.created_at.desc()).limit(100)).all()
    return [
        {
            "id": log.id,
            "client_order_id": log.client_order_id,
            "broker_order_id": log.broker_order_id,
            "mode": log.mode,
            "symbol": log.symbol,
            "side": log.side,
            "units": log.units,
            "status": log.status,
            "reason": log.reason,
            "filled_price": log.filled_price,
            "realized_pnl": log.realized_pnl,
            "closed_at": log.closed_at.isoformat() if log.closed_at else None,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
