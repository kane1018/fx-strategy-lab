"""Local-only unattended arm control; never imports broker-write code."""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.h11_auto.runtime_safety import H11AutoRuntimeSafetyError, PhaseBRiskStore
from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    require_clean_main,
)
from app.h11_auto.v4_gmo_actual_coordinator import (
    V4GmoActualCoordinatorError,
    V4GmoActualCoordinatorStore,
)
from app.h11_auto.v4_gmo_generation import (
    V4GmoFrozenGeneration,
    V4GmoGenerationError,
    load_v4_gmo_frozen_generation,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_g038_unattended_activation import (
    V4G038ActivationError,
    verify_g038_generation_activation,
    verify_g038_scheduler_binding,
)
from app.services.h11_v4_unattended_live_arm_state import (
    V4ArmDesiredState,
    V4UnattendedLiveArmStateError,
    V4UnattendedLiveArmStore,
)
from app.services.h11_v4_unattended_live_authorization import (
    check_operator_daily_authorization,
)
from app.services.h11_v4_unattended_live_paths import (
    DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    v4_unattended_live_arm_state_path,
    v4_unattended_live_daily_authorization_path,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest

router = APIRouter(prefix="/api/manual/unattended-control", tags=["local-unattended-control"])
REPOSITORY = Path(__file__).resolve().parents[3]
_CSRF_COOKIE = "h11_v4_control_csrf"
_CSRF_HEADER = "x-h11-v4-control-csrf"
_LOCAL_ORIGINS = {
    "http://127.0.0.1:8765",
    "http://localhost:8765",
    "http://[::1]:8765",
}


class ArmChangeRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    expected_generation_digest: str = Field(min_length=71, max_length=71)
    expected_reviewed_files_digest: str = Field(min_length=71, max_length=71)


@dataclass(frozen=True)
class _CurrentContract:
    reviewed_files_digest: str
    generation: V4GmoFrozenGeneration


def _load_current_contract() -> _CurrentContract:
    reviewed = compute_reviewed_files_digest(repository=REPOSITORY)
    generation = load_v4_gmo_frozen_generation(
        repository=REPOSITORY,
        implementation_digest=reviewed,
    )
    return _CurrentContract(reviewed_files_digest=reviewed, generation=generation)


def _arm_store(contract: _CurrentContract) -> V4UnattendedLiveArmStore:
    return V4UnattendedLiveArmStore(
        v4_unattended_live_arm_state_path(
            state_root=DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
            generation_digest=contract.generation.digest,
        )
    )


def unattended_auto_mode_requested() -> bool:
    """Block manual Private GET while armed, exit-managing, halted, or unknown."""

    try:
        contract = _load_current_contract()
        arm = _arm_store(contract).check(
            expected_generation_digest=contract.generation.digest,
            expected_reviewed_files_digest=contract.reviewed_files_digest,
        )
        runtime_state, _ = _runtime_projection(contract)
        return arm.armed or runtime_state in {"POSITION_OPEN", "HALTED"}
    except (
        OSError,
        V4GmoGenerationError,
        V4UnattendedLiveArmStateError,
        ValueError,
    ):
        return True


def _safe_status(contract: _CurrentContract, *, csrf_token: str | None = None) -> dict:
    check = _arm_store(contract).check(
        expected_generation_digest=contract.generation.digest,
        expected_reviewed_files_digest=contract.reviewed_files_digest,
    )
    try:
        verify_g038_generation_activation(generation=contract.generation)
        verify_g038_scheduler_binding(
            generation=contract.generation,
            plist_path=(
                Path.home()
                / "Library"
                / "LaunchAgents"
                / "com.fxstrategylab.h11v4.unattended.scheduler.plist"
            ),
            now_utc=datetime.now(UTC),
        )
        supported = True
    except V4G038ActivationError:
        supported = False
    runtime_state, entries_today = _runtime_projection(contract)
    authorization = check_operator_daily_authorization(
        artifact_path=v4_unattended_live_daily_authorization_path(
            generation_digest=contract.generation.digest,
        ),
        expected_generation_digest=contract.generation.digest,
        now_utc=datetime.now(UTC),
    )
    if runtime_state == "HALTED":
        effective_state = "HALTED"
        reason = "RUNTIME_STATE_NOT_CLEAR"
    elif not check.armed and runtime_state == "POSITION_OPEN":
        effective_state = "EXIT_ONLY"
        reason = "OPERATOR_DISARMED_EXIT_MANAGEMENT_CONTINUES"
    elif check.armed and supported and authorization.authorized:
        effective_state = "ON_WAITING"
        reason = "RUNTIME_GATES_PENDING"
    elif check.armed and supported:
        effective_state = "ON_WAITING"
        reason = authorization.blocked_reasons[0]
    elif check.armed:
        effective_state = "HALTED"
        reason = "GENERATION_NOT_COMMISSIONED_FOR_UNATTENDED_LIVE"
    else:
        effective_state = "OFF"
        reason = check.blocked_reasons[0] if check.blocked_reasons else "OPERATOR_DISARMED"
    result = {
        "actual_post_count": 0,
        "broker_write": False,
        "desired_state": check.desired_state.value,
        "effective_state": effective_state,
        "entries_today": entries_today,
        "generation_digest": contract.generation.digest,
        "generation_label": contract.generation.generation_label,
        "maximum_entries_per_day": contract.generation.maximum_entries_per_day,
        "reason_label": reason,
        "revision": check.revision,
        "reviewed_files_digest": contract.reviewed_files_digest,
        "unattended_live_supported": supported,
        "daily_authorization_clear": authorization.authorized,
    }
    if csrf_token is not None:
        result["csrf_token"] = csrf_token
    return result


def _runtime_projection(contract: _CurrentContract) -> tuple[str, int | None]:
    root = v4_gmo_runtime_state_root(
        repository=REPOSITORY,
        generation_digest=contract.generation.digest,
    )
    coordinator_path = root / "coordinator.sqlite3"
    risk_path = root / "risk.json"
    try:
        risk_exists = risk_path.is_file() and not risk_path.is_symlink()
        coordinator_exists = (
            coordinator_path.is_file() and not coordinator_path.is_symlink()
        )
        if not risk_exists and not coordinator_exists:
            return "FLAT", None
        if not risk_exists or not coordinator_exists:
            return "HALTED", None
        risk_state = PhaseBRiskStore(
            risk_path,
            policy=v4_gmo_risk_policy(),
        ).load()
        today_jst = (
            datetime.now(UTC)
            .astimezone(ZoneInfo("Asia/Tokyo"))
            .date()
            .isoformat()
        )
        entries_today = (
            risk_state.entries_today
            if risk_state.current_day_jst == today_jst
            else 0
        )
        coordinator = V4GmoActualCoordinatorStore.open_monitor_observer(
            coordinator_path
        )
        if (
            coordinator.market_attempt_count_for_day(
                trading_day_jst=today_jst
            )
            != entries_today
        ):
            return "HALTED", entries_today
        snapshot = coordinator.monitor_snapshot_safe()
    except (H11AutoRuntimeSafetyError, V4GmoActualCoordinatorError, OSError):
        return "HALTED", None
    if snapshot.unknown_halt_latched or snapshot.pending_transport:
        return "HALTED", entries_today
    if (
        snapshot.cycle_present
        and snapshot.entry_attempted_at_utc is not None
        and not snapshot.flat_reconciled
    ):
        return "POSITION_OPEN", entries_today
    return "FLAT", entries_today


@router.get("")
def get_control_status() -> JSONResponse:
    try:
        contract = _load_current_contract()
        token = secrets.token_urlsafe(32)
        response = JSONResponse(_safe_status(contract, csrf_token=token))
        response.set_cookie(
            _CSRF_COOKIE,
            token,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/api/manual/unattended-control",
        )
        return response
    except (OSError, V4GmoGenerationError, V4UnattendedLiveArmStateError, ValueError):
        raise HTTPException(
            status_code=409,
            detail="UNATTENDED_CONTROL_CURRENT_CONTRACT_NOT_CLEAR",
        ) from None


@router.post("/on")
def turn_on(request_body: ArmChangeRequest, request: Request) -> dict:
    _require_local_csrf(request)
    try:
        require_clean_main(repository=REPOSITORY)
        contract = _load_current_contract()
        if request_body.expected_generation_digest != contract.generation.digest:
            raise V4UnattendedLiveArmStateError("ARM_STATE_GENERATION_MISMATCH")
        if request_body.expected_reviewed_files_digest != contract.reviewed_files_digest:
            raise V4UnattendedLiveArmStateError("ARM_STATE_REVIEWED_FILES_MISMATCH")
        if (
            contract.generation.live_ready is not True
            or contract.generation.unattended_live_supported is not True
        ):
            raise V4UnattendedLiveArmStateError(
                "GENERATION_NOT_COMMISSIONED_FOR_UNATTENDED_LIVE"
            )
        verify_g038_generation_activation(generation=contract.generation)
        _arm_store(contract).set_desired_state(
            desired_state=V4ArmDesiredState.ARMED,
            expected_revision=request_body.expected_revision,
            generation_digest=contract.generation.digest,
            reviewed_files_digest=contract.reviewed_files_digest,
            changed_at_utc=datetime.now(UTC),
        )
        return _safe_status(contract)
    except (
        V4ActualPreparationGuardError,
        V4GmoGenerationError,
        V4UnattendedLiveArmStateError,
        V4G038ActivationError,
        OSError,
        ValueError,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post("/off")
def turn_off(request_body: ArmChangeRequest, request: Request) -> dict:
    _require_local_csrf(request)
    try:
        check = V4UnattendedLiveArmStore(
            v4_unattended_live_arm_state_path(
                state_root=DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
                generation_digest=request_body.expected_generation_digest,
            )
        ).set_desired_state(
            desired_state=V4ArmDesiredState.DISARMED,
            expected_revision=request_body.expected_revision,
            generation_digest=request_body.expected_generation_digest,
            reviewed_files_digest=request_body.expected_reviewed_files_digest,
            changed_at_utc=datetime.now(UTC),
        )
        return {
            "actual_post_count": 0,
            "broker_write": False,
            "desired_state": check.desired_state.value,
            "effective_state": "OFF_REQUESTED",
            "entries_today": None,
            "generation_digest": check.generation_digest,
            "generation_label": "GENERATION_BOUND",
            "maximum_entries_per_day": 30,
            "reason_label": "OPERATOR_DISARMED",
            "revision": check.revision,
            "reviewed_files_digest": check.reviewed_files_digest,
            "unattended_live_supported": False,
        }
    except (
        V4UnattendedLiveArmStateError,
        OSError,
        ValueError,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


def _require_local_csrf(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin not in _LOCAL_ORIGINS:
        raise HTTPException(status_code=403, detail="UNATTENDED_CONTROL_ORIGIN_REFUSED")
    cookie = request.cookies.get(_CSRF_COOKIE, "")
    header = request.headers.get(_CSRF_HEADER, "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail="UNATTENDED_CONTROL_CSRF_REFUSED")
