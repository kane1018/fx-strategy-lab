from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import OrderLog
from app.schemas.trading import PaperSessionRequest, PaperTickRequest, SignalMonitorRequest
from app.services.paper_trade_service import process_tick, start_session, stop_session
from app.services.signal_service import evaluate_monitor, start_monitor, stop_monitor


def test_paper_session_can_start_tick_and_stop(db: Session) -> None:
    session = start_session(db, PaperSessionRequest())
    assert session["status"] == "running"
    tick = process_tick(db, session["id"], PaperTickRequest())
    assert tick["current_price"] > 0
    stopped = stop_session(db, session["id"])
    assert stopped["status"] == "stopped"
    assert stopped["open_positions"] == []
    assert stopped["trades"][0]["exit_reason"] == "手動停止"


def test_signal_monitor_never_places_orders(db: Session) -> None:
    monitor = start_monitor(SignalMonitorRequest())
    result = evaluate_monitor(db, monitor["monitor_id"])
    assert result["status"] == "running"
    order_count = db.scalar(select(func.count()).select_from(OrderLog))
    assert order_count == 0
    stopped = stop_monitor(monitor["monitor_id"])
    assert stopped["status"] == "stopped"
