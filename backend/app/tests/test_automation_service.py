from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokers.base import BrokerResult
from app.brokers.oanda_broker import OandaAccount, OandaBrokerError, OandaPrice
from app.models import AutoTradeState, BotLog, ErrorLog, OrderLog, Signal
from app.schemas.trading import (
    AutoTradeConfig,
    Candle,
    ExecutionConfig,
    OrderRequest,
    RiskConfig,
    StrategyConfig,
    StrategyType,
)
from app.services.automation_service import initialize_automation, run_automation_cycle
from app.services.bot_service import get_or_create_bot_status, start_bot
from app.services.broker_service import place_order


class FakeOandaBroker:
    def __init__(self, *, position_side: str | None = None) -> None:
        self.position_side = position_side
        self.fail_price = False
        self.fail_balance = False
        self.fail_order = False
        self.fail_close = False
        self.stale_price = False
        self.spread_pips = 2
        self.closed_summary: dict[str, Any] | None = None

    def account_summary(self) -> OandaAccount:
        if self.fail_balance:
            raise OandaBrokerError("account summary unavailable")
        return OandaAccount(
            balance=100000,
            nav=100000,
            currency="JPY",
            open_position_count=1 if self.position_side else 0,
        )

    def current_price(self, symbol: str) -> OandaPrice:
        if self.fail_price:
            raise OandaBrokerError("price unavailable")
        return OandaPrice(
            symbol=symbol,
            bid=149.99,
            ask=150.01,
            midpoint=150,
            spread_pips=self.spread_pips,
            timestamp=(
                datetime.now(UTC) - timedelta(minutes=5)
                if self.stale_price
                else datetime.now(UTC)
            ),
            quote_home_conversion=0.0067,
        )

    def candles(self, symbol: str, timeframe: str, count: int = 200) -> list[Candle]:
        del symbol, timeframe
        now = datetime.now(UTC)
        candles = [
            Candle(
                timestamp=now + timedelta(minutes=index),
                open=149.0,
                high=149.2,
                low=148.8,
                close=149.0,
                volume=1,
            )
            for index in range(max(count - 1, 2))
        ]
        candles.append(
            Candle(
                timestamp=now + timedelta(minutes=len(candles)),
                open=149.1,
                high=150.2,
                low=149.0,
                close=150.1,
                volume=1,
            )
        )
        return candles

    def open_positions(self) -> list[dict[str, Any]]:
        if not self.position_side:
            return []
        long_units = "100" if self.position_side == "buy" else "0"
        short_units = "-100" if self.position_side == "sell" else "0"
        return [
            {
                "instrument": "USD_JPY",
                "long": {
                    "units": long_units,
                    "averagePrice": "149.9",
                    "unrealizedPL": "5",
                },
                "short": {
                    "units": short_units,
                    "averagePrice": "150.1",
                    "unrealizedPL": "-5",
                },
            }
        ]

    def market_order(self, request: OrderRequest) -> BrokerResult:
        if self.fail_order:
            raise OandaBrokerError("fill confirmation failed")
        self.position_side = request.side.value
        return BrokerResult(
            broker_order_id="order-1",
            status="filled",
            filled_price=request.current_price,
            fill_transaction_id="fill-1",
            trade_id="trade-1",
            fill_time=datetime.now(UTC),
            filled_units=request.units,
        )

    def close_position(self, symbol: str, side: str) -> BrokerResult:
        del symbol, side
        if self.fail_close:
            raise OandaBrokerError("close failed")
        self.position_side = None
        return BrokerResult(
            broker_order_id="close-1",
            status="closed",
            filled_price=150,
            fill_transaction_id="close-fill-1",
            fill_time=datetime.now(UTC),
            filled_units=100,
            realized_pnl=5,
            closed_trade_ids=("trade-1",),
        )

    def closed_trade_summary(self, trade_id: str) -> dict[str, Any]:
        if self.closed_summary is None:
            raise OandaBrokerError("closed trade unavailable")
        return {**self.closed_summary, "trade_id": trade_id}


def config() -> AutoTradeConfig:
    return AutoTradeConfig(
        strategy=StrategyConfig(
            strategy_type=StrategyType.BREAKOUT,
            breakout_period=2,
        ),
        execution=ExecutionConfig(
            fixed_units=100,
            risk_percent=1,
            stop_loss_pips=30,
            take_profit_pips=60,
        ),
        risk=RiskConfig(
            max_daily_loss=100,
            max_loss_per_trade=25,
            max_positions=1,
            max_units=1000,
            max_consecutive_losses=3,
            max_spread_pips=3,
        ),
        interval_seconds=30,
    )


def test_signal_risk_order_fill_and_position_are_connected(db: Session) -> None:
    broker = FakeOandaBroker()
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]
    result = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]

    assert result["last_signal"]["action"] == "buy"
    assert result["last_risk"]["allowed"] is True
    assert result["last_fill"]["fill_transaction_id"] == "fill-1"
    assert result["current_positions"][0]["side"] == "buy"
    assert db.scalar(select(Signal)) is not None
    order = db.scalar(select(OrderLog).where(OrderLog.status == "filled"))
    assert order is not None
    assert order.risk_check_json["allowed"] is True
    assert order.risk_check_json["fill_transaction_id"] == "fill-1"
    assert order.risk_check_json["fill_time"]
    assert order.risk_check_json["filled_units"] == 100


def test_practice_order_is_blocked_when_automation_is_off(db: Session) -> None:
    start_bot(db, "practice")
    request = OrderRequest(
        client_order_id="PRACTICE-OFF-1",
        mode="practice",
        symbol="USD_JPY",
        side="buy",
        units=100,
        current_price=150,
        stop_loss=149.7,
        take_profit=150.6,
        spread_pips=1,
        estimated_loss=10,
        api_connection_ok=True,
    )
    result = place_order(db, request, RiskConfig())
    assert result["accepted"] is False
    assert "自動売買がOFF" in result["reasons"][0]
    assert db.scalar(select(OrderLog).where(OrderLog.status == "bot_stopped"))


def test_price_failure_stops_bot_and_logs_error(db: Session) -> None:
    broker = FakeOandaBroker()
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]
    broker.fail_price = True
    result = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]

    assert result["enabled"] is False
    assert result["bot"]["status"] == "error_stopped"
    assert db.scalar(select(ErrorLog).where(ErrorLog.source == "automation.market_or_account"))
    assert db.scalar(select(BotLog).where(BotLog.status == "error_stopped"))


def test_rate_limit_stops_bot_and_preserves_reason(db: Session) -> None:
    broker = FakeOandaBroker()
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]
    broker.fail_price = True
    original_current_price = broker.current_price

    def rate_limited(symbol: str) -> OandaPrice:
        del symbol
        raise OandaBrokerError("OANDA API error (429): rate limit")

    broker.current_price = rate_limited  # type: ignore[method-assign]
    result = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]
    broker.current_price = original_current_price  # type: ignore[method-assign]
    assert result["enabled"] is False
    assert result["bot"]["status"] == "error_stopped"
    assert "429" in result["bot"]["stop_reason"]


def test_fill_confirmation_failure_stops_bot(db: Session) -> None:
    broker = FakeOandaBroker()
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]
    broker.fail_order = True
    result = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]

    assert result["enabled"] is False
    assert result["bot"]["status"] == "error_stopped"
    failed = db.scalar(select(OrderLog).where(OrderLog.status == "emergency_stopped"))
    assert failed is not None


def test_opposite_signal_closes_position(db: Session) -> None:
    broker = FakeOandaBroker(position_side="sell")
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]
    result = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]

    assert result["last_fill"]["status"] == "closed"
    assert broker.position_side is None
    assert db.scalar(select(OrderLog).where(OrderLog.status == "closed"))


def test_order_limits_are_rejected_and_logged(db: Session) -> None:
    broker = FakeOandaBroker()
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]
    state = db.scalar(select(AutoTradeState))
    assert state is not None
    request = OrderRequest(
        client_order_id="PRACTICE-LIMIT-1",
        mode="practice",
        symbol="USD_JPY",
        side="buy",
        units=1001,
        current_price=150,
        stop_loss=149.7,
        take_profit=150.6,
        spread_pips=1,
        estimated_loss=10,
        api_connection_ok=True,
    )
    result = place_order(
        db,
        request,
        config().risk,
        broker=broker,  # type: ignore[arg-type]
        open_positions_override=0,
    )
    assert result["accepted"] is False
    assert "最大取引数量を超過" in result["reasons"]
    assert db.scalar(select(OrderLog).where(OrderLog.status == "risk_rejected"))
    assert get_or_create_bot_status(db).status == "running"


def test_stale_price_stops_before_order(db: Session) -> None:
    broker = FakeOandaBroker()
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]
    broker.stale_price = True
    result = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]
    assert result["enabled"] is False
    assert result["bot"]["status"] == "error_stopped"
    assert db.scalar(select(OrderLog)) is None


def test_wide_spread_is_risk_stopped(db: Session) -> None:
    broker = FakeOandaBroker()
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]
    broker.spread_pips = 4
    result = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]
    assert result["enabled"] is False
    assert result["bot"]["status"] == "risk_stopped"
    rejected = db.scalar(select(OrderLog).where(OrderLog.status == "risk_rejected"))
    assert rejected is not None
    assert "スプレッド上限を超過" in rejected.reason


def test_external_sl_tp_close_is_reconciled_with_realized_pnl(db: Session) -> None:
    broker = FakeOandaBroker()
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]
    first = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]
    assert first["last_fill"]["status"] == "filled"
    broker.position_side = None
    broker.closed_summary = {
        "status": "closed",
        "realized_pnl": 7.25,
        "gross_pl": 7.5,
        "financing": -0.1,
        "commission": 0.15,
        "guaranteed_execution_fee": 0,
        "half_spread_cost": 0.2,
        "average_close_price": 150.2,
        "closed_at": datetime.now(UTC).isoformat(),
        "closing_transaction_ids": ["close-fill-2"],
    }
    result = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]
    closed = db.scalar(select(OrderLog).where(OrderLog.status == "closed"))
    assert result["last_fill"]["status"] == "closed"
    assert closed is not None
    assert closed.realized_pnl == 7.25


def test_balance_failure_stops_bot_and_logs_error(db: Session) -> None:
    broker = FakeOandaBroker()
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]
    broker.fail_balance = True
    result = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]

    assert result["enabled"] is False
    assert result["bot"]["status"] == "error_stopped"
    assert db.scalar(
        select(ErrorLog).where(ErrorLog.source == "automation.market_or_account")
    )
    assert db.scalar(select(OrderLog)) is None


def test_max_positions_blocks_order_without_stopping_bot(db: Session) -> None:
    broker = FakeOandaBroker()
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]
    request = OrderRequest(
        client_order_id="PRACTICE-MAXPOS-1",
        mode="practice",
        symbol="USD_JPY",
        side="buy",
        units=10,
        current_price=150,
        stop_loss=149.7,
        take_profit=150.6,
        spread_pips=1,
        estimated_loss=10,
        api_connection_ok=True,
    )
    result = place_order(
        db,
        request,
        config().risk,  # max_positions=1
        broker=broker,  # type: ignore[arg-type]
        open_positions_override=1,
    )
    assert result["accepted"] is False
    assert "最大ポジション数に到達" in result["reasons"]
    assert get_or_create_bot_status(db).status == "running"


def test_repeated_close_failure_emergency_stops_bot(db: Session) -> None:
    broker = FakeOandaBroker(position_side="sell")
    broker.fail_close = True
    initialize_automation(db, config(), broker=broker)  # type: ignore[arg-type]

    first = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]
    assert first["last_fill"]["status"] == "close_failed"
    assert first["enabled"] is True
    assert first["bot"]["status"] == "running"

    second = run_automation_cycle(db, broker=broker)  # type: ignore[arg-type]
    assert second["enabled"] is False
    assert second["bot"]["status"] == "error_stopped"
    assert db.scalar(select(ErrorLog).where(ErrorLog.source == "automation.close"))
