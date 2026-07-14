"""Localhost-only FastAPI surface for the manual signal UI."""

from __future__ import annotations

from functools import lru_cache
from threading import Lock
from time import monotonic
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.h11_manual.contracts import Direction, Horizon, ManualExitReason, OperatorDecision
from app.h11_manual.service import ManualSignalService
from app.shadow.gmo_public import GmoPublicError, GmoPublicMarketDataClient

router = APIRouter(prefix="/api/manual", tags=["local-manual-signal"])
_refresh_lock = Lock()
_last_refresh_monotonic = 0.0
AUTO_REFRESH_DEDUP_SECONDS = 30.0


@lru_cache
def get_manual_signal_service() -> ManualSignalService:
    return ManualSignalService()


ServiceDependency = Annotated[ManualSignalService, Depends(get_manual_signal_service)]


class DecisionRequest(BaseModel):
    horizon: Horizon
    decision: OperatorDecision
    forecast_id: str | None = None
    note: str = Field(default="", max_length=500)


class RealtimeTickRequest(BaseModel):
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)
    market_time_utc: str = Field(min_length=10, max_length=64)


class OpenExitPlanRequest(BaseModel):
    forecast_id: str = Field(min_length=10, max_length=80)
    horizon: Horizon
    direction: Direction
    entry_price: float = Field(gt=0)
    stop_loss_price: float = Field(gt=0)
    take_profit_price: float = Field(gt=0)


class QuickStartExitPlanRequest(BaseModel):
    forecast_id: str = Field(min_length=10, max_length=80)
    horizon: Horizon
    direction: Direction


class CloseExitPlanRequest(BaseModel):
    reason: ManualExitReason
    exit_price: float = Field(gt=0)


@router.get("/current")
def current(service: ServiceDependency) -> dict:
    return service.current()


@router.post("/refresh")
def refresh(service: ServiceDependency, force: bool = False) -> dict:
    global _last_refresh_monotonic

    if not _refresh_lock.acquire(blocking=False):
        response = service.current(record=False)
        response["refresh"] = {"status": "IN_PROGRESS", "short_model_trained": False}
        return response
    client = GmoPublicMarketDataClient()
    try:
        elapsed = monotonic() - _last_refresh_monotonic
        if not force and _last_refresh_monotonic and elapsed < AUTO_REFRESH_DEDUP_SECONDS:
            response = service.current(record=False)
            response["refresh"] = {
                "status": "RECENTLY_REFRESHED",
                "short_model_trained": False,
            }
            return response
        response = service.refresh(client)
        _last_refresh_monotonic = monotonic()
        response["refresh"]["status"] = "UPDATED"
        return response
    except (GmoPublicError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    finally:
        client.client.close()
        _refresh_lock.release()


@router.post("/decisions")
def decision(
    request: DecisionRequest,
    service: ServiceDependency,
) -> dict:
    return service.record_decision(
        horizon=request.horizon,
        decision=request.decision,
        forecast_id=request.forecast_id,
        note=request.note,
    )


@router.post("/realtime-estimate")
def realtime_estimate(request: RealtimeTickRequest, service: ServiceDependency) -> dict:
    try:
        return service.realtime_estimate(
            bid=request.bid,
            ask=request.ask,
            market_time_utc=request.market_time_utc,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/history")
def history(
    service: ServiceDependency,
    limit: int = 100,
) -> dict:
    return service.history(limit)


@router.get("/signal-series")
def signal_series(service: ServiceDependency, limit: int = 120) -> dict:
    return service.signal_series(limit)


@router.get("/exit-plan")
def exit_plan(service: ServiceDependency) -> dict:
    return service.exit_plan_status()


@router.post("/exit-plan")
def open_exit_plan(request: OpenExitPlanRequest, service: ServiceDependency) -> dict:
    try:
        return service.open_exit_plan(
            forecast_id=request.forecast_id,
            horizon=request.horizon,
            direction=request.direction,
            entry_price=request.entry_price,
            stop_loss_price=request.stop_loss_price,
            take_profit_price=request.take_profit_price,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/exit-plan/quick-start")
def quick_start_exit_plan(request: QuickStartExitPlanRequest, service: ServiceDependency) -> dict:
    try:
        return service.quick_start_exit_plan(
            forecast_id=request.forecast_id,
            horizon=request.horizon,
            direction=request.direction,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/exit-plan/close")
def close_exit_plan(request: CloseExitPlanRequest, service: ServiceDependency) -> dict:
    try:
        return service.close_exit_plan(reason=request.reason, exit_price=request.exit_price)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/validation")
def validation(service: ServiceDependency) -> dict:
    return service.validation()


@router.get("/chart")
def chart(
    service: ServiceDependency,
    timeframe: Literal["1m", "10m", "30m", "1h"] = "1m",
    limit: int = 180,
) -> dict:
    return service.chart(timeframe, limit=limit)
