"""Localhost-only FastAPI surface for the manual signal UI."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.h11_auto.v4_gmo_actual_coordinator import V4GmoActualCoordinatorStore
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.h11_manual.contracts import Direction, Horizon, ManualExitReason
from app.h11_manual.service import ManualSignalService
from app.h11_manual.settlement_sync import (
    BoundAccountSnapshotManualSettlementReadClient,
    DisabledManualSettlementReadClient,
    build_keychain_manual_settlement_client,
)
from app.h11_manual.unattended_control_api import unattended_auto_mode_requested
from app.services.h11_v4_unattended_account_snapshot_store_no_post import (
    V4AccountSnapshotStoreNoPost,
)
from app.services.h11_v4_unattended_live_paths import (
    DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    v4_unattended_account_snapshot_state_directory,
)
from app.shadow.gmo_public import GmoPublicError, GmoPublicMarketDataClient
from h11_v4_reviewed_digest import compute_reviewed_files_digest

router = APIRouter(prefix="/api/manual", tags=["local-manual-signal"])
_refresh_lock = Lock()
_broker_sync_lock = Lock()
_service_init_lock = Lock()
_manual_signal_service: ManualSignalService | None = None
_manual_settlement_reader_initialized = False
_REPOSITORY = Path(__file__).resolve().parents[3]
_last_refresh_monotonic = 0.0
# The browser retries a just-closed M1 candle a bounded number of times when
# the public kline feed publishes it a few seconds late.  Keep this below the
# browser retry interval so a real refresh is possible, while still coalescing
# double-clicks and overlapping page work.
AUTO_REFRESH_DEDUP_SECONDS = 8.0


def get_manual_signal_service() -> ManualSignalService:
    global _manual_signal_service

    if _manual_signal_service is not None:
        return _manual_signal_service
    with _service_init_lock:
        if _manual_signal_service is None:
            _manual_signal_service = ManualSignalService()
    return _manual_signal_service


ServiceDependency = Annotated[ManualSignalService, Depends(get_manual_signal_service)]


def get_manual_settlement_service(service: ServiceDependency) -> ManualSignalService:
    global _manual_settlement_reader_initialized

    if unattended_auto_mode_requested():
        with _service_init_lock:
            try:
                service.settlement_reader = _build_unattended_snapshot_reader()
            except (OSError, ValueError):
                service.settlement_reader = DisabledManualSettlementReadClient()
                if service is _manual_signal_service:
                    _manual_settlement_reader_initialized = False
            else:
                if service is _manual_signal_service:
                    _manual_settlement_reader_initialized = False
        return service
    if service is _manual_signal_service and not _manual_settlement_reader_initialized:
        with _service_init_lock:
            if not _manual_settlement_reader_initialized:
                service.settlement_reader = build_keychain_manual_settlement_client()
                _manual_settlement_reader_initialized = True
    return service


def _build_unattended_snapshot_reader() -> BoundAccountSnapshotManualSettlementReadClient:
    reviewed_files_digest = compute_reviewed_files_digest(repository=_REPOSITORY)
    generation = load_v4_gmo_frozen_generation(
        repository=_REPOSITORY,
        implementation_digest=reviewed_files_digest,
    )
    return BoundAccountSnapshotManualSettlementReadClient(
        store=V4AccountSnapshotStoreNoPost(
            v4_unattended_account_snapshot_state_directory(
                state_root=DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
                generation_digest=generation.digest,
            )
        ),
        expected_reviewed_files_digest=reviewed_files_digest,
        expected_generation_digest=generation.digest,
        now_factory=lambda: datetime.now(UTC),
    )


def _apply_bound_flat_reconciliation(service: ManualSignalService) -> bool:
    reader = service.settlement_reader
    if not isinstance(reader, BoundAccountSnapshotManualSettlementReadClient):
        return False
    evidence = reader.valid_evidence()
    if evidence is None:
        return False
    reviewed_files_digest = compute_reviewed_files_digest(repository=_REPOSITORY)
    generation = load_v4_gmo_frozen_generation(
        repository=_REPOSITORY,
        implementation_digest=reviewed_files_digest,
    )
    coordinator_path = (
        v4_gmo_runtime_state_root(
            repository=_REPOSITORY,
            generation_digest=generation.digest,
        )
        / "coordinator.sqlite3"
    )
    if not coordinator_path.is_file() or coordinator_path.is_symlink():
        return False
    return V4GmoActualCoordinatorStore.open_monitor_observer(
        coordinator_path
    ).reconcile_external_flat_no_post(
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed_files_digest,
        evidence_digest=evidence.artifact_digest,
        observed_at_utc=datetime.fromisoformat(evidence.observed_at_utc).astimezone(UTC),
        valid_until_utc=datetime.fromisoformat(evidence.valid_until_utc).astimezone(UTC),
        account_flat=evidence.account_flat,
        active_orders_zero=evidence.active_orders_zero,
        broker_write=evidence.broker_write,
        broker_post_count=evidence.broker_post_count,
    )


SettlementServiceDependency = Annotated[
    ManualSignalService, Depends(get_manual_settlement_service)
]


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
    plan_id: int = Field(gt=0)
    reason: ManualExitReason
    exit_price: float = Field(gt=0)


class CorrectActualFillRequest(BaseModel):
    plan_id: int = Field(gt=0)
    actual_fill_price: float = Field(gt=0)


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


@router.get("/positions")
def positions(
    service: ServiceDependency,
    limit: int = 100,
) -> dict:
    return service.position_history(limit)


@router.get("/signal-series")
def signal_series(service: ServiceDependency, limit: int = 120) -> dict:
    return service.signal_series(limit)


@router.get("/exit-plan")
def exit_plan(service: ServiceDependency) -> dict:
    return service.exit_plan_status()


@router.get("/broker-sync")
def broker_sync(service: SettlementServiceDependency) -> dict:
    if not _broker_sync_lock.acquire(blocking=False):
        status = service.exit_plan_status()
        return {
            **status["broker_sync"],
            "configured": status["broker_sync"]["status"] != "NOT_CONFIGURED",
            "events": [],
            "active_plans": status["active_plans"],
            "actual_positions": status["actual_positions"],
            "in_progress": True,
            "safety": service.broker_sync_safety_flags(actual_read=False),
        }
    try:
        result = service.synchronize_manual_settlements()
        if _apply_bound_flat_reconciliation(service):
            result["runtime_flat_reconciliation"] = {
                "status": "EXTERNAL_FLAT_RECONCILED_NO_POST",
                "broker_write": False,
                "broker_post_count": 0,
            }
        return result
    finally:
        _broker_sync_lock.release()


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
        return service.close_exit_plan(
            plan_id=request.plan_id,
            reason=request.reason,
            exit_price=request.exit_price,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/exit-plan/actual-fill")
def correct_actual_fill(request: CorrectActualFillRequest, service: ServiceDependency) -> dict:
    try:
        return service.correct_active_fill_price(
            plan_id=request.plan_id,
            actual_fill_price=request.actual_fill_price,
        )
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
