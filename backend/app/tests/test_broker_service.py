import pytest
from sqlalchemy.orm import Session

from app.models import OrderLog
from app.schemas.trading import CloseOrderRequest, OrderRequest, RiskConfig, Side
from app.services.bot_service import start_bot, stop_bot
from app.services.broker_service import close_order, place_order


def request(order_id: str) -> OrderRequest:
    return OrderRequest(
        client_order_id=order_id,
        mode="demo",
        symbol="USD_JPY",
        side=Side.BUY,
        units=100,
        current_price=150,
        stop_loss=149.7,
        take_profit=150.6,
        estimated_loss=10,
        api_connection_ok=True,
    )


def test_order_requires_running_bot(db: Session) -> None:
    result = place_order(db, request("ORDER-STOPPED"), RiskConfig())
    assert result["status"] == "bot_stopped"


def test_demo_order_can_be_filled_and_closed(db: Session) -> None:
    start_bot(db, "demo")
    result = place_order(db, request("ORDER-RUNNING"), RiskConfig())
    assert result["accepted"]
    closed = close_order(
        db,
        result["order_log_id"],
        CloseOrderRequest(exit_price=result["filled_price"] + 0.1),
    )
    assert closed["status"] == "closed"
    stop_bot(db)


def test_demo_close_api_rejects_practice_order_log(db: Session) -> None:
    start_bot(db, "demo")
    result = place_order(db, request("ORDER-PRACTICE-GUARD"), RiskConfig())
    order_log = db.get(OrderLog, result["order_log_id"])
    assert order_log is not None
    order_log.mode = "practice"
    db.commit()

    with pytest.raises(ValueError, match="ローカルデモ注文専用"):
        close_order(
            db,
            result["order_log_id"],
            CloseOrderRequest(exit_price=result["filled_price"] + 0.1),
        )
