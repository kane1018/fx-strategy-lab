from datetime import UTC, datetime, timedelta
from math import floor
from threading import Event, Lock, Thread, current_thread
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokers import OandaBroker, OandaBrokerError
from app.brokers.base import BrokerResult
from app.database import SessionLocal
from app.models import AutoTradeState, OrderLog, Signal
from app.schemas.trading import AutoTradeConfig, OrderRequest, Side
from app.services.bot_service import (
    bot_snapshot,
    emergency_stop_bot,
    get_or_create_bot_status,
    risk_stop_bot,
    start_bot,
    stop_bot,
)
from app.services.broker_service import place_order
from app.services.log_service import record_error
from app.services.market_data_service import candles_to_frame, pip_size
from app.strategies import evaluate_strategy

AUTO_MONITOR_ID = "auto-practice"
_cycle_lock = Lock()


def get_or_create_automation_state(db: Session) -> AutoTradeState:
    state = db.scalar(select(AutoTradeState).order_by(AutoTradeState.id).limit(1))
    if not state:
        state = AutoTradeState()
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def _positions_snapshot(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for position in positions:
        symbol = str(position["instrument"])
        for key, side in (("long", "buy"), ("short", "sell")):
            details = position.get(key, {})
            units = abs(float(details.get("units", 0)))
            if units <= 0:
                continue
            normalized.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "units": units,
                    "average_price": float(details.get("averagePrice", 0) or 0),
                    "unrealized_pnl": float(details.get("unrealizedPL", 0) or 0),
                }
            )
    return normalized


def _assert_fresh_price(timestamp: datetime) -> None:
    observed_at = timestamp
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    if datetime.now(UTC) - observed_at > timedelta(seconds=60):
        raise OandaBrokerError("OANDA価格が古いため取引を停止しました")


def automation_snapshot(db: Session) -> dict[str, Any]:
    state = get_or_create_automation_state(db)
    return {
        "enabled": state.enabled,
        "environment": state.environment,
        "last_signal": state.last_signal_json,
        "last_risk": state.last_risk_json,
        "last_order_id": state.last_order_id,
        "last_fill": state.last_fill_json,
        "current_positions": state.current_positions_json,
        "last_price_at": state.last_price_at.isoformat() if state.last_price_at else None,
        "last_balance_at": (
            state.last_balance_at.isoformat() if state.last_balance_at else None
        ),
        "last_cycle_at": state.last_cycle_at.isoformat() if state.last_cycle_at else None,
        "consecutive_failures": state.consecutive_failures,
        "bot": bot_snapshot(db),
    }


def _save_signal(
    db: Session,
    config: AutoTradeConfig,
    action: str,
    price: float,
    stop_loss: float,
    take_profit: float,
    reason: str,
) -> Signal:
    signal = Signal(
        monitor_id=AUTO_MONITOR_ID,
        symbol=config.symbol,
        timeframe=config.timeframe,
        strategy_name=config.strategy.strategy_type.value,
        side=action,
        price=price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reason=reason,
        risk_percent=config.execution.risk_percent,
        notice="OANDA practice専用の自動売買シグナルです。実資金注文には使用されません。",
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


def _build_order(
    config: AutoTradeConfig,
    action: str,
    price: float,
    balance: float,
    spread_pips: float,
    quote_home_conversion: float,
) -> OrderRequest:
    pip = pip_size(config.symbol)
    stop_distance = config.execution.stop_loss_pips * pip
    take_distance = config.execution.take_profit_pips * pip
    side = Side(action)
    stop_loss = price - stop_distance if side == Side.BUY else price + stop_distance
    take_profit = price + take_distance if side == Side.BUY else price - take_distance
    loss_per_unit = stop_distance * quote_home_conversion
    if loss_per_unit <= 0:
        raise ValueError("注文数量計算に必要な損失換算値が不正です")
    risk_budget = min(
        balance * config.execution.risk_percent / 100,
        config.risk.max_loss_per_trade,
    )
    risk_based_units = floor(risk_budget / loss_per_unit)
    requested_units = config.execution.fixed_units or risk_based_units
    units = floor(min(requested_units, risk_based_units, config.risk.max_units))
    if units < 1:
        raise ValueError("リスク上限内で発注可能な注文数量がありません")
    estimated_loss = units * loss_per_unit
    return OrderRequest(
        client_order_id=f"AUTO-{uuid4().hex[:20].upper()}",
        mode="practice",
        symbol=config.symbol,
        side=side,
        units=units,
        current_price=price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        spread_pips=spread_pips,
        estimated_loss=estimated_loss,
        manual_stop_available=True,
        logs_enabled=True,
        api_connection_ok=True,
    )


def _reconcile_closed_positions(
    db: Session,
    broker: OandaBroker,
    symbol: str,
    current_positions: list[dict[str, Any]],
) -> bool:
    if any(position["symbol"] == symbol for position in current_positions):
        return False
    logs = db.scalars(
        select(OrderLog).where(
            OrderLog.mode == "practice",
            OrderLog.symbol == symbol,
            OrderLog.status == "filled",
        )
    ).all()
    for log in logs:
        trade_id = str(log.risk_check_json.get("trade_id") or "")
        if not trade_id:
            log.status = "close_unconfirmed"
            log.reason = "OANDAポジション消失後のTrade IDを確認できません"
            db.commit()
            raise OandaBrokerError(log.reason)
        summary = broker.closed_trade_summary(trade_id)
        log.status = "closed"
        log.realized_pnl = float(summary["realized_pnl"])
        log.closed_at = datetime.fromisoformat(
            str(summary["closed_at"]).replace("Z", "+00:00")
        ).replace(tzinfo=None)
        log.reason = "OANDA決済Transactionと確定損益を照合済み"
        log.risk_check_json = {
            **log.risk_check_json,
            "close_summary": summary,
        }
    if logs:
        db.commit()
        return True
    return False


def _close_position(
    db: Session,
    broker: OandaBroker,
    state: AutoTradeState,
    position: dict[str, Any],
    current_price: float,
    reason: str,
) -> dict[str, Any]:
    bot = get_or_create_bot_status(db)
    if bot.status != "running" or bot.manual_stop_active or bot.mode != "practice":
        raise OandaBrokerError("Bot停止中のため自動決済できません")
    log = OrderLog(
        client_order_id=f"AUTO-CLOSE-{uuid4().hex[:18].upper()}",
        mode="practice",
        symbol=position["symbol"],
        side=position["side"],
        units=position["units"],
        requested_price=current_price,
        status="pending_close",
        reason=reason,
        risk_check_json={
            "allowed": True,
            "reduce_only": True,
            "reason": "既存ポジションのリスク削減決済",
        },
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    try:
        result: BrokerResult = broker.close_position(
            position["symbol"], position["side"]
        )
        log.broker_order_id = result.broker_order_id
        log.filled_price = result.filled_price
        log.status = "closed"
        log.realized_pnl = result.realized_pnl
        log.closed_at = datetime.utcnow()
        log.reason = f"{reason}; OANDA practice決済約定確認済み"
        log.risk_check_json = {
            **log.risk_check_json,
            "fill_transaction_id": result.fill_transaction_id,
            "fill_time": result.fill_time.isoformat() if result.fill_time else None,
            "realized_pnl": result.realized_pnl,
            "financing": result.financing,
            "commission": result.commission,
            "guaranteed_execution_fee": result.guaranteed_execution_fee,
            "half_spread_cost": result.half_spread_cost,
            "closed_trade_ids": list(result.closed_trade_ids),
        }
        entry_logs = db.scalars(
            select(OrderLog).where(
                OrderLog.mode == "practice",
                OrderLog.symbol == position["symbol"],
                OrderLog.status == "filled",
            )
        ).all()
        for entry_log in entry_logs:
            trade_id = str(entry_log.risk_check_json.get("trade_id") or "")
            if trade_id and trade_id in result.closed_trade_ids:
                entry_log.status = "closed"
                entry_log.realized_pnl = result.realized_pnl
                entry_log.closed_at = log.closed_at
                entry_log.reason = "OANDA practice反対シグナル決済を照合済み"
        state.consecutive_failures = 0
        db.commit()
        return {
            "accepted": True,
            "status": "closed",
            "broker_order_id": result.broker_order_id,
            "fill_transaction_id": result.fill_transaction_id,
            "filled_price": result.filled_price,
            "order_log_id": log.id,
        }
    except Exception as error:
        log.status = "close_failed"
        log.reason = f"自動決済失敗: {error}"
        state.consecutive_failures += 1
        db.commit()
        record_error(
            db,
            "automation.close",
            str(error),
            {"symbol": position["symbol"], "attempt": state.consecutive_failures},
        )
        if state.consecutive_failures >= 2:
            state.enabled = False
            db.commit()
            emergency_stop_bot(db, "自動決済失敗が連続したため停止")
        return {
            "accepted": False,
            "status": "close_failed",
            "reasons": [str(error)],
            "order_log_id": log.id,
        }


def _fatal_stop(db: Session, state: AutoTradeState, source: str, error: Exception) -> None:
    message = str(error)
    state.enabled = False
    state.consecutive_failures += 1
    state.last_cycle_at = datetime.utcnow()
    db.commit()
    record_error(db, source, message)
    emergency_stop_bot(db, message)


def initialize_automation(
    db: Session,
    config: AutoTradeConfig,
    broker: OandaBroker | None = None,
) -> dict[str, Any]:
    state = get_or_create_automation_state(db)
    try:
        broker = broker or OandaBroker()
        account = broker.account_summary()
        price = broker.current_price(config.symbol)
        _assert_fresh_price(price.timestamp)
        candles = broker.candles(config.symbol, config.timeframe, 50)
        positions = _positions_snapshot(broker.open_positions())
        if not candles:
            raise OandaBrokerError("戦略判定用の価格履歴がありません")
    except Exception as error:
        _fatal_stop(db, state, "automation.initialize", error)
        raise
    state.enabled = True
    state.environment = "practice"
    state.config_json = config.model_dump(mode="json")
    state.current_positions_json = positions
    state.last_price_at = price.timestamp.replace(tzinfo=None)
    state.last_balance_at = datetime.utcnow()
    state.last_cycle_at = datetime.utcnow()
    state.consecutive_failures = 0
    db.commit()
    start_bot(db, "practice")
    return {
        **automation_snapshot(db),
        "account": {
            "balance": account.balance,
            "nav": account.nav,
            "currency": account.currency,
        },
    }


def _run_automation_cycle(
    db: Session,
    broker: OandaBroker | None = None,
) -> dict[str, Any]:
    state = get_or_create_automation_state(db)
    bot = get_or_create_bot_status(db)
    if not state.enabled or bot.status != "running" or bot.mode != "practice":
        return automation_snapshot(db)
    config = AutoTradeConfig.model_validate(state.config_json)
    try:
        broker = broker or OandaBroker()
        account = broker.account_summary()
        state.last_balance_at = datetime.utcnow()
        price = broker.current_price(config.symbol)
        _assert_fresh_price(price.timestamp)
        state.last_price_at = price.timestamp.replace(tzinfo=None)
        history_count = max(
            config.strategy.long_period,
            config.strategy.rsi_period,
            config.strategy.breakout_period,
        ) + 5
        candles = broker.candles(config.symbol, config.timeframe, history_count)
        strategy_signal = evaluate_strategy(candles_to_frame(candles), config.strategy)
        positions = _positions_snapshot(broker.open_positions())
        state.current_positions_json = positions
        state.last_signal_json = {
            "action": strategy_signal.action,
            "reason": strategy_signal.reason,
            "price": price.midpoint,
            "created_at": datetime.utcnow().isoformat(),
        }
        state.last_cycle_at = datetime.utcnow()
        state.consecutive_failures = 0
        db.commit()
    except Exception as error:
        _fatal_stop(db, state, "automation.market_or_account", error)
        return automation_snapshot(db)

    try:
        reconciled_close = _reconcile_closed_positions(
            db,
            broker,
            config.symbol,
            positions,
        )
    except Exception as error:
        _fatal_stop(db, state, "automation.close_reconciliation", error)
        return automation_snapshot(db)
    if reconciled_close:
        state.last_fill_json = {
            "accepted": True,
            "status": "closed",
            "reason": "OANDA側決済を照合済み",
        }
        state.last_cycle_at = datetime.utcnow()
        db.commit()
        return automation_snapshot(db)
    position = next(
        (item for item in positions if item["symbol"] == config.symbol),
        None,
    )
    action = strategy_signal.action
    if action in {"buy", "sell"}:
        pip = pip_size(config.symbol)
        stop = (
            price.midpoint - config.execution.stop_loss_pips * pip
            if action == "buy"
            else price.midpoint + config.execution.stop_loss_pips * pip
        )
        take = (
            price.midpoint + config.execution.take_profit_pips * pip
            if action == "buy"
            else price.midpoint - config.execution.take_profit_pips * pip
        )
        _save_signal(
            db,
            config,
            action,
            price.midpoint,
            stop,
            take,
            strategy_signal.reason,
        )

    if position and action in {"buy", "sell"} and action != position["side"]:
        result = _close_position(
            db,
            broker,
            state,
            position,
            price.midpoint,
            f"反対シグナル: {strategy_signal.reason}",
        )
        state.last_fill_json = result
        state.last_order_id = str(result.get("broker_order_id") or "")
        state.last_cycle_at = datetime.utcnow()
        db.commit()
        return automation_snapshot(db)

    if not position and action in {"buy", "sell"}:
        try:
            entry_price = price.ask if action == "buy" else price.bid
            order = _build_order(
                config,
                action,
                entry_price,
                account.balance,
                price.spread_pips,
                price.quote_home_conversion,
            )
        except ValueError as error:
            state.last_risk_json = {"allowed": False, "reasons": [str(error)]}
            state.enabled = False
            db.commit()
            risk_stop_bot(db, str(error))
            return automation_snapshot(db)
        result = place_order(
            db,
            order,
            config.risk,
            broker=broker,
            open_positions_override=len(positions),
        )
        state.last_risk_json = {
            "allowed": bool(result.get("accepted")),
            "reasons": result.get("reasons", []),
            "units": order.units,
            "estimated_loss": order.estimated_loss,
        }
        state.last_order_id = str(result.get("broker_order_id") or "")
        state.last_fill_json = result
        if not result.get("accepted"):
            state.enabled = False
            db.commit()
            if get_or_create_bot_status(db).status == "running":
                risk_stop_bot(db, "; ".join(result.get("reasons", ["注文拒否"])))
            return automation_snapshot(db)
        try:
            state.current_positions_json = _positions_snapshot(broker.open_positions())
            state.last_cycle_at = datetime.utcnow()
            db.commit()
        except Exception as error:
            _fatal_stop(db, state, "automation.position_confirmation", error)
    return automation_snapshot(db)


def run_automation_cycle(
    db: Session,
    broker: OandaBroker | None = None,
) -> dict[str, Any]:
    if not _cycle_lock.acquire(blocking=False):
        return automation_snapshot(db)
    try:
        return _run_automation_cycle(db, broker)
    finally:
        _cycle_lock.release()


def stop_automation(db: Session, reason: str = "手動停止") -> dict[str, Any]:
    state = get_or_create_automation_state(db)
    state.enabled = False
    db.commit()
    stop_bot(db, reason)
    return automation_snapshot(db)


def recover_automation_after_restart(db: Session) -> None:
    state = get_or_create_automation_state(db)
    if state.enabled:
        state.enabled = False
        db.commit()
        stop_bot(db, "プロセス再起動後は自動売買の再確認が必要です")


class AutomationRunner:
    def __init__(self) -> None:
        self._stop = Event()
        self._lock = Lock()
        self._thread: Thread | None = None

    def start(self, interval_seconds: int) -> None:
        with self._lock:
            self.stop()
            self._stop.clear()
            self._thread = Thread(
                target=self._run,
                args=(interval_seconds,),
                daemon=True,
                name="oanda-practice-automation",
            )
            self._thread.start()

    def _run(self, interval_seconds: int) -> None:
        while not self._stop.wait(interval_seconds):
            with SessionLocal() as db:
                run_automation_cycle(db)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not current_thread():
            thread.join(timeout=2)
        self._thread = None


automation_runner = AutomationRunner()
