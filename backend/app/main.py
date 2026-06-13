import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_db
from app.schemas.trading import (
    AutoTradeConfig,
    BacktestRequest,
    BacktestResponse,
    BotStartRequest,
    CloseOrderRequest,
    OrderSubmission,
    PaperSessionRequest,
    PaperTickRequest,
    SignalMonitorRequest,
)
from app.services.automation_service import (
    automation_runner,
    automation_snapshot,
    initialize_automation,
    recover_automation_after_restart,
    run_automation_cycle,
    stop_automation,
)
from app.services.backtest_service import run_backtest
from app.services.bot_service import bot_snapshot, start_bot
from app.services.broker_service import (
    close_order,
    connection_test,
    order_history,
    place_order,
)
from app.services.paper_trade_service import (
    error_stop_session,
    get_session,
    process_tick,
    start_session,
    stop_session,
)
from app.services.signal_service import (
    evaluate_monitor,
    signal_history,
    start_monitor,
    stop_monitor,
)

settings = get_settings()
logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        recover_automation_after_restart(db)
    yield
    automation_runner.stop()


app = FastAPI(
    title="FX Strategy Lab API",
    version="0.1.0",
    description="Personal FX strategy validation and safety-first demo trading API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Db = Annotated[Session, Depends(get_db)]


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "live_trading_environment_enabled": settings.enable_live_trading,
        "live_broker_implemented": False,
    }


@app.post("/api/backtests", response_model=BacktestResponse)
def create_backtest(request: BacktestRequest, db: Db) -> BacktestResponse:
    return run_backtest(db, request)


@app.post("/api/paper/sessions")
def create_paper_session(request: PaperSessionRequest, db: Db) -> dict:
    return start_session(db, request)


@app.get("/api/paper/sessions/{session_id}")
def read_paper_session(session_id: int, db: Db) -> dict:
    try:
        return get_session(db, session_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/paper/sessions/{session_id}/tick")
def paper_tick(session_id: int, request: PaperTickRequest, db: Db) -> dict:
    try:
        return process_tick(db, session_id, request)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        error_stop_session(db, session_id, f"価格処理エラー: {error}")
        raise HTTPException(
            status_code=500,
            detail="価格処理に失敗したためペーパートレードを停止しました",
        ) from error


@app.post("/api/paper/sessions/{session_id}/stop")
def paper_stop(session_id: int, db: Db) -> dict:
    try:
        return stop_session(db, session_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/signals/monitors")
def create_signal_monitor(request: SignalMonitorRequest) -> dict:
    return start_monitor(request)


@app.post("/api/signals/monitors/{monitor_id}/evaluate")
def check_signal_monitor(monitor_id: str, db: Db) -> dict:
    try:
        return evaluate_monitor(db, monitor_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/signals/monitors/{monitor_id}/stop")
def disable_signal_monitor(monitor_id: str) -> dict:
    return stop_monitor(monitor_id)


@app.get("/api/signals")
def read_signals(db: Db) -> list[dict]:
    return signal_history(db)


@app.post("/api/broker/connection-test")
def test_broker_connection(
    db: Db, mode: str = Query(default="demo", pattern="^(demo|practice|live)$")
) -> dict:
    return connection_test(db, mode)


@app.post("/api/orders")
def create_order(submission: OrderSubmission, db: Db) -> dict:
    return place_order(db, submission.request, submission.risk)


@app.get("/api/orders")
def read_orders(db: Db) -> list[dict]:
    return order_history(db)


@app.post("/api/orders/{order_id}/close")
def close_demo_order(order_id: int, request: CloseOrderRequest, db: Db) -> dict:
    try:
        return close_order(db, order_id, request)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/bot/status")
def read_bot_status(db: Db) -> dict:
    return bot_snapshot(db)


@app.post("/api/bot/start")
def enable_bot(request: BotStartRequest, db: Db) -> dict:
    return start_bot(db, request.mode)


@app.post("/api/bot/stop")
def disable_bot(db: Db) -> dict:
    automation_runner.stop()
    return stop_automation(db)


@app.get("/api/automation/status")
def read_automation_status(db: Db) -> dict:
    return automation_snapshot(db)


@app.post("/api/automation/start")
def start_automation(request: AutoTradeConfig, db: Db) -> dict:
    try:
        result = initialize_automation(db, request)
    except Exception as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    automation_runner.start(request.interval_seconds)
    return result


@app.post("/api/automation/cycle")
def automation_cycle(db: Db) -> dict:
    return run_automation_cycle(db)


@app.post("/api/automation/stop")
def disable_automation(db: Db) -> dict:
    automation_runner.stop()
    return stop_automation(db)
