from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import OrderLog, PaperTrade
from app.schemas.trading import PaperSessionRequest, PaperTickRequest, SignalMonitorRequest
from app.services.paper_trade_service import process_tick, start_session, stop_session
from app.services.signal_service import evaluate_monitor, start_monitor, stop_monitor


def test_paper_session_can_start_tick_and_stop(db: Session) -> None:
    session = start_session(db, PaperSessionRequest())
    assert session["status"] == "running"

    # The tick path must run and yield a positive price. Whether the synthetic,
    # date-seeded strategy opens a position on any given calendar date is not
    # deterministic, so we do not assert on trade generation here.
    tick = process_tick(db, session["id"], PaperTickRequest())
    assert tick["current_price"] > 0

    # Seed one deterministic open position, then assert the behaviour under test:
    # a manual stop closes every open position with the manual-stop reason.
    db.add(
        PaperTrade(
            session_id=session["id"],
            symbol="USD_JPY",
            side="buy",
            units=1000,
            entry_price=150.0,
            current_price=150.1,
            stop_loss=149.5,
            take_profit=151.0,
            entry_reason="test fixture position",
        )
    )
    db.commit()

    stopped = stop_session(db, session["id"])
    assert stopped["status"] == "stopped"
    assert stopped["open_positions"] == []
    assert stopped["trades"]
    assert all(trade["exit_reason"] == "手動停止" for trade in stopped["trades"])


def test_signal_monitor_never_places_orders(db: Session) -> None:
    monitor = start_monitor(SignalMonitorRequest())
    result = evaluate_monitor(db, monitor["monitor_id"])
    assert result["status"] == "running"
    order_count = db.scalar(select(func.count()).select_from(OrderLog))
    assert order_count == 0
    stopped = stop_monitor(monitor["monitor_id"])
    assert stopped["status"] == "stopped"
