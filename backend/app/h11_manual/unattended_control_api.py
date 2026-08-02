"""Local-only unattended arm control; never imports broker-write code."""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass, replace
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
from app.services.h11_v4_g064_position_reconciliation_no_post import (
    load_g064_position_reconciliation_no_post,
)
from app.services.h11_v4_g064_unattended_activation import (
    G064_GENERATION_LABEL,
    G064_PERSISTENT_HALT_FILE,
    V4G064ActivationError,
    verify_g064_scheduler_binding,
)
from app.services.h11_v4_g065_position_reconciliation_no_post import (
    load_g065_position_reconciliation_no_post,
)
from app.services.h11_v4_g065_unattended_activation import (
    G065_GENERATION_LABEL,
    G065_PERSISTENT_HALT_FILE,
    V4G065ActivationError,
    verify_g065_scheduler_binding,
)
from app.services.h11_v4_g066_unattended_activation import (
    G066_GENERATION_LABEL,
    G066_PERSISTENT_HALT_FILE,
    V4G066ActivationError,
)
from app.services.h11_v4_g067_unattended_activation import (
    G067_GENERATION_LABEL,
    G067_PERSISTENT_HALT_FILE,
    V4G067ActivationError,
    verify_g067_scheduler_binding,
)
from app.services.h11_v4_g068_unattended_activation_no_post import (
    G068_GENERATION_LABEL,
    G068_PERSISTENT_HALT_FILE,
    V4G068ActivationError,
    verify_g068_scheduler_binding,
)
from app.services.h11_v4_g069_position_reconciliation_no_post import (
    load_g069_position_reconciliation_no_post,
)
from app.services.h11_v4_g069_unattended_activation_no_post import (
    G069_GENERATION_LABEL,
    G069_PERSISTENT_HALT_FILE,
    V4G069ActivationError,
    verify_g069_arm_readiness_no_post,
    verify_g069_scheduler_binding,
)
from app.services.h11_v4_g070_candidate import (
    G070_GENERATION_LABEL,
    G070_PERSISTENT_HALT_FILE,
    G070Error,
    safe_g070_api_status,
    verify_g070_scheduler_binding,
)
from app.services.h11_v4_g071_atomic_activation import (
    G071_GENERATION_LABEL,
    G071_PERSISTENT_HALT_FILE,
    G071Error,
    safe_g071_api_status,
    verify_g071_scheduler_binding,
)
from app.services.h11_v4_g072_switch_control import (
    G072_GENERATION_LABEL,
    G072_PERSISTENT_HALT_FILE,
    G072Error,
    safe_g072_api_status,
    verify_g072_scheduler_binding,
)
from app.services.h11_v4_g073_runtime import (
    G073_GENERATION_LABEL,
    G073Error,
    safe_g073_api_status,
    verify_g073_scheduler_binding,
)
from app.services.h11_v4_g074_runtime import (
    G074_GENERATION_LABEL,
    G074Error,
    safe_g074_api_status,
    verify_g074_scheduler_binding,
)
from app.services.h11_v4_unattended_live_arm_state import (
    V4ArmDesiredState,
    V4UnattendedLiveArmStateError,
    V4UnattendedLiveArmStore,
)
from app.services.h11_v4_unattended_live_paths import (
    DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    v4_unattended_live_arm_state_path,
)
from app.services.h11_v4_unattended_runtime_no_post import (
    V4UnattendedRuntimeState,
    entry_evaluation_allowed,
    load_unattended_runtime_evidence_no_post,
    project_unattended_runtime_state,
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


def _verify_current_generation_runtime(contract: _CurrentContract) -> None:
    plist_path = (
        Path.home()
        / "Library"
        / "LaunchAgents"
        / "com.fxstrategylab.h11v4.unattended.scheduler.plist"
    )
    state_root = v4_gmo_runtime_state_root(
        repository=REPOSITORY,
        generation_digest=contract.generation.digest,
    )
    if contract.generation.generation_label in {
        G064_GENERATION_LABEL,
        G065_GENERATION_LABEL,
        G066_GENERATION_LABEL,
        G067_GENERATION_LABEL,
        G068_GENERATION_LABEL,
        G069_GENERATION_LABEL,
        G070_GENERATION_LABEL,
        G071_GENERATION_LABEL,
        G072_GENERATION_LABEL,
        G073_GENERATION_LABEL,
        G074_GENERATION_LABEL,
    }:
        verifier = (
            verify_g074_scheduler_binding
            if contract.generation.generation_label == G074_GENERATION_LABEL
            else verify_g073_scheduler_binding
            if contract.generation.generation_label == G073_GENERATION_LABEL
            else verify_g072_scheduler_binding
            if contract.generation.generation_label == G072_GENERATION_LABEL
            else verify_g071_scheduler_binding
            if contract.generation.generation_label == G071_GENERATION_LABEL
            else verify_g070_scheduler_binding
            if contract.generation.generation_label == G070_GENERATION_LABEL
            else verify_g069_scheduler_binding
            if contract.generation.generation_label == G069_GENERATION_LABEL
            else verify_g067_scheduler_binding
            if contract.generation.generation_label == G067_GENERATION_LABEL
            else (
                verify_g068_scheduler_binding
                if contract.generation.generation_label == G068_GENERATION_LABEL
                else (
                    verify_g065_scheduler_binding
                    if contract.generation.generation_label
                    in {G065_GENERATION_LABEL, G066_GENERATION_LABEL}
                    else verify_g064_scheduler_binding
                )
            )
        )
        verifier_kwargs = {
            "generation": contract.generation,
            "plist_path": plist_path,
            "state_root": state_root,
            "now_utc": datetime.now(UTC),
        }
        if contract.generation.generation_label in {
            G071_GENERATION_LABEL,
            G072_GENERATION_LABEL,
            G073_GENERATION_LABEL,
            G074_GENERATION_LABEL,
        }:
            verifier_kwargs["repository"] = REPOSITORY
        verifier(
            **verifier_kwargs,
        )
        return
    verify_g038_generation_activation(generation=contract.generation)
    verify_g038_scheduler_binding(
        generation=contract.generation,
        plist_path=plist_path,
        now_utc=datetime.now(UTC),
    )


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
    state_root = v4_gmo_runtime_state_root(
        repository=REPOSITORY,
        generation_digest=contract.generation.digest,
    )
    if contract.generation.generation_label in {
        G070_GENERATION_LABEL,
        G071_GENERATION_LABEL,
        G072_GENERATION_LABEL,
        G073_GENERATION_LABEL,
        G074_GENERATION_LABEL,
    }:
        status_reader = (
            safe_g074_api_status
            if contract.generation.generation_label == G074_GENERATION_LABEL
            else safe_g073_api_status
            if contract.generation.generation_label == G073_GENERATION_LABEL
            else safe_g072_api_status
            if contract.generation.generation_label == G072_GENERATION_LABEL
            else safe_g071_api_status
            if contract.generation.generation_label == G071_GENERATION_LABEL
            else safe_g070_api_status
        )
        projected = status_reader(
            state_root=state_root,
            arm_on=check.armed,
            generation_digest=contract.generation.digest,
            reviewed_files_digest=contract.reviewed_files_digest,
        )
        activation_available = bool(
            projected.get(
                "runtime_activation_available",
                projected["control_plane_state"] == "READY",
            )
        )
        result = {
            "actual_post_count": 0,
            "broker_write": False,
            "arm_control_available": True,
            "arm_state": "ON" if check.armed else "OFF",
            "desired_state": check.desired_state.value,
            **projected,
            "runtime_state": projected["effective_state"],
            "entries_today": None,
            "generation_digest": contract.generation.digest,
            "generation_label": contract.generation.generation_label,
            "maximum_entries_per_day": contract.generation.maximum_entries_per_day,
            "reason_label": projected["safe_reason_label"],
            "revision": check.revision,
            "reviewed_files_digest": contract.reviewed_files_digest,
            "live_ready": False,
            "unattended_live_supported": False,
            "daily_authorization_required": False,
            "per_trade_confirmation_required": False,
            "scheduler_ready": projected["control_plane_state"] == "READY",
            "position_reconciliation_ready": projected["reconciliation_state"]
            in {"FRESH_FLAT", "FRESH_PROTECTED"},
            "local_arm_on_available": bool(
                projected.get("local_arm_on_available", activation_available)
            ),
            "arm_ready": bool(projected.get("arm_ready", activation_available)),
            "runtime_activation_available": activation_available,
        }
        if csrf_token is not None:
            result["csrf_token"] = csrf_token
        return result
    position_evidence = None
    persistent_halt = contract.generation.generation_label in {
        G064_GENERATION_LABEL,
        G065_GENERATION_LABEL,
        G066_GENERATION_LABEL,
        G067_GENERATION_LABEL,
        G068_GENERATION_LABEL,
        G069_GENERATION_LABEL,
        G070_GENERATION_LABEL,
        G071_GENERATION_LABEL,
        G072_GENERATION_LABEL,
    } and (
        (
            state_root
            / (
                G065_PERSISTENT_HALT_FILE
                if contract.generation.generation_label == G065_GENERATION_LABEL
                else (
                    G066_PERSISTENT_HALT_FILE
                    if contract.generation.generation_label == G066_GENERATION_LABEL
                    else (
                        G067_PERSISTENT_HALT_FILE
                        if contract.generation.generation_label == G067_GENERATION_LABEL
                        else (
                            G069_PERSISTENT_HALT_FILE
                            if contract.generation.generation_label == G069_GENERATION_LABEL
                            else G072_PERSISTENT_HALT_FILE
                            if contract.generation.generation_label == G072_GENERATION_LABEL
                            else G071_PERSISTENT_HALT_FILE
                            if contract.generation.generation_label == G071_GENERATION_LABEL
                            else G070_PERSISTENT_HALT_FILE
                            if contract.generation.generation_label == G070_GENERATION_LABEL
                            else G068_PERSISTENT_HALT_FILE
                            if contract.generation.generation_label == G068_GENERATION_LABEL
                            else G064_PERSISTENT_HALT_FILE
                        )
                    )
                )
            )
        ).is_file()
        or (
            state_root
            / (
                G065_PERSISTENT_HALT_FILE
                if contract.generation.generation_label == G065_GENERATION_LABEL
                else (
                    G066_PERSISTENT_HALT_FILE
                    if contract.generation.generation_label == G066_GENERATION_LABEL
                    else (
                        G067_PERSISTENT_HALT_FILE
                        if contract.generation.generation_label == G067_GENERATION_LABEL
                        else (
                            G069_PERSISTENT_HALT_FILE
                            if contract.generation.generation_label == G069_GENERATION_LABEL
                            else G072_PERSISTENT_HALT_FILE
                            if contract.generation.generation_label == G072_GENERATION_LABEL
                            else G071_PERSISTENT_HALT_FILE
                            if contract.generation.generation_label == G071_GENERATION_LABEL
                            else G070_PERSISTENT_HALT_FILE
                            if contract.generation.generation_label == G070_GENERATION_LABEL
                            else G068_PERSISTENT_HALT_FILE
                            if contract.generation.generation_label == G068_GENERATION_LABEL
                            else G064_PERSISTENT_HALT_FILE
                        )
                    )
                )
            )
        ).is_symlink()
    )
    try:
        _verify_current_generation_runtime(contract)
        supported = not persistent_halt
    except (
        V4G038ActivationError,
        V4G064ActivationError,
        V4G065ActivationError,
        V4G066ActivationError,
        V4G067ActivationError,
        V4G068ActivationError,
        V4G069ActivationError,
    ):
        supported = False
    local_runtime_state, entries_today = _runtime_projection(contract)
    evidence = load_unattended_runtime_evidence_no_post(
        state_root=state_root,
        generation_digest=contract.generation.digest,
        arm_armed=check.armed,
        reviewed_files_digest=contract.reviewed_files_digest,
    )
    if contract.generation.generation_label in {
        G064_GENERATION_LABEL,
        G065_GENERATION_LABEL,
        G066_GENERATION_LABEL,
        G067_GENERATION_LABEL,
        G068_GENERATION_LABEL,
        G069_GENERATION_LABEL,
    }:
        if contract.generation.generation_label == G069_GENERATION_LABEL:
            position_evidence = load_g069_position_reconciliation_no_post(
                reviewed_files_digest=contract.reviewed_files_digest,
                generation_digest=contract.generation.digest,
                now_utc=datetime.now(UTC),
            )
            position_shape_ready = bool(
                position_evidence.evidence_available
                and position_evidence.evidence_fresh
                and position_evidence.generation_bound
                and (
                    (
                        position_evidence.account_flat is True
                        and position_evidence.active_orders_zero is True
                    )
                    or all(
                        getattr(position_evidence, name, False) is True
                        for name in (
                            "ownership_exact",
                            "quantity_matches",
                            "protection_confirmed",
                        )
                    )
                )
            )
        else:
            position_evidence = (
                load_g065_position_reconciliation_no_post
                if contract.generation.generation_label
                in {
                    G065_GENERATION_LABEL,
                    G066_GENERATION_LABEL,
                    G067_GENERATION_LABEL,
                    G068_GENERATION_LABEL,
                }
                else load_g064_position_reconciliation_no_post
            )(
                state_root=v4_gmo_runtime_state_root(
                    repository=REPOSITORY,
                    generation_digest=contract.generation.digest,
                ),
                generation_digest=contract.generation.digest,
                now_utc=datetime.now(UTC),
            )
            position_shape_ready = bool(
                position_evidence.evidence_available
                and position_evidence.evidence_fresh
                and position_evidence.generation_bound
            )
        position_reconciliation_ready = position_shape_ready
        if not position_evidence.evidence_available:
            evidence = replace(
                evidence,
                position_open=True,
                protection_confirmed=False,
                ownership_exact=False,
                quantity_matches=False,
                runtime_clear=False,
                unknown_halt=True,
            )
        elif contract.generation.generation_label == G069_GENERATION_LABEL:
            non_flat = not (
                position_evidence.account_flat is True
                and position_evidence.active_orders_zero is True
            )
            evidence = replace(
                evidence,
                position_open=bool(position_evidence.position_open or non_flat),
                protection_confirmed=position_evidence.protection_confirmed,
                ownership_exact=position_evidence.ownership_exact,
                quantity_matches=position_evidence.quantity_matches,
                runtime_clear=evidence.runtime_clear and position_shape_ready,
                unknown_halt=evidence.unknown_halt or not position_shape_ready,
            )
        elif position_evidence.position_open:
            evidence = replace(
                evidence,
                position_open=True,
                protection_confirmed=position_evidence.protection_confirmed,
                ownership_exact=position_evidence.ownership_exact,
                quantity_matches=position_evidence.quantity_matches,
                runtime_clear=evidence.runtime_clear,
            )
        elif contract.generation.generation_label == G064_GENERATION_LABEL:
            evidence = replace(
                evidence,
                position_open=False,
                protection_confirmed=True,
                ownership_exact=True,
                quantity_matches=True,
            )
        else:
            evidence = replace(
                evidence,
                position_open=False,
                protection_confirmed=False,
                ownership_exact=False,
                quantity_matches=False,
            )
    if persistent_halt or not supported or local_runtime_state == "HALTED":
        evidence = replace(
            evidence,
            generation_matches=(evidence.generation_matches if supported else False),
            runtime_clear=False,
            unknown_halt=True,
        )
    if local_runtime_state == "POSITION_OPEN" and not evidence.position_open:
        evidence = replace(evidence, runtime_clear=False, unknown_halt=True)
    if local_runtime_state == "FLAT" and evidence.position_open:
        evidence = replace(evidence, runtime_clear=False, unknown_halt=True)
    projected_state = project_unattended_runtime_state(evidence)
    if contract.generation.generation_label == G069_GENERATION_LABEL:
        try:
            verify_g069_arm_readiness_no_post(
                scheduler_ready=supported,
                position_evidence_available=bool(
                    position_evidence is not None and position_evidence.evidence_available
                ),
                position_evidence_fresh=bool(
                    position_evidence is not None and position_evidence.evidence_fresh
                ),
                position_generation_bound=bool(
                    position_evidence is not None and position_evidence.generation_bound
                ),
                position_open=evidence.position_open,
                account_flat=bool(
                    position_evidence is not None
                    and getattr(position_evidence, "account_flat", False) is True
                ),
                active_orders_zero=bool(
                    position_evidence is not None
                    and getattr(position_evidence, "active_orders_zero", False) is True
                ),
                ownership_exact=evidence.ownership_exact,
                quantity_matches=evidence.quantity_matches,
                protection_confirmed=evidence.protection_confirmed,
            )
            arm_ready = True
        except V4G069ActivationError:
            arm_ready = False
            projected_state = V4UnattendedRuntimeState.HALTED
    else:
        arm_ready = supported and projected_state is not V4UnattendedRuntimeState.HALTED
        position_reconciliation_ready = arm_ready
    entry_gate_open = entry_evaluation_allowed(
        evidence=evidence,
        state=projected_state,
    )
    if projected_state is V4UnattendedRuntimeState.HALTED:
        effective_state = "HALTED"
        reason = "RUNTIME_STATE_NOT_CLEAR"
        entry_state = "HALTED"
    elif projected_state in {
        V4UnattendedRuntimeState.ON_EXIT_ONLY,
        V4UnattendedRuntimeState.EXIT_ONLY,
    }:
        effective_state = projected_state.value
        reason = (
            "ARMED_ENTRY_BLOCKED_POSITION_OPEN"
            if check.armed
            else "OPERATOR_DISARMED_EXIT_MANAGEMENT_CONTINUES"
        )
        entry_state = "POSITION_OPEN"
    elif projected_state is V4UnattendedRuntimeState.ON_WAITING:
        effective_state = "ON_WAITING"
        reason = "RUNTIME_GATES_PENDING"
        entry_state = "WAITING_FOR_SIGNAL"
    else:
        effective_state = "OFF"
        reason = check.blocked_reasons[0] if check.blocked_reasons else "OPERATOR_DISARMED"
        entry_state = "DISARMED"
    result = {
        "actual_post_count": 0,
        "broker_write": False,
        "arm_control_available": True,
        "arm_state": check.desired_state.value,
        "desired_state": check.desired_state.value,
        "entry_gate_open": entry_gate_open,
        "entry_state": entry_state,
        "effective_state": effective_state,
        "runtime_state": projected_state.value,
        "entries_today": entries_today,
        "generation_digest": contract.generation.digest,
        "generation_label": contract.generation.generation_label,
        "maximum_entries_per_day": contract.generation.maximum_entries_per_day,
        "reason_label": reason,
        "revision": check.revision,
        "reviewed_files_digest": contract.reviewed_files_digest,
        "live_ready": bool(contract.generation.live_ready and supported),
        "unattended_live_supported": bool(
            contract.generation.unattended_live_supported and supported
        ),
        "daily_authorization_required": False,
        "scheduler_ready": supported,
        "position_reconciliation_ready": position_reconciliation_ready,
        "local_arm_on_available": arm_ready,
        "arm_ready": arm_ready,
        "runtime_activation_available": arm_ready,
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
        coordinator_exists = coordinator_path.is_file() and not coordinator_path.is_symlink()
        if not risk_exists and not coordinator_exists:
            return "FLAT", None
        if not risk_exists or not coordinator_exists:
            return "HALTED", None
        risk_state = PhaseBRiskStore(
            risk_path,
            policy=v4_gmo_risk_policy(),
        ).load()
        today_jst = datetime.now(UTC).astimezone(ZoneInfo("Asia/Tokyo")).date().isoformat()
        entries_today = risk_state.entries_today if risk_state.current_day_jst == today_jst else 0
        coordinator = V4GmoActualCoordinatorStore.open_monitor_observer(coordinator_path)
        if coordinator.market_attempt_count_for_day(trading_day_jst=today_jst) != entries_today:
            return "HALTED", entries_today
        snapshot = coordinator.monitor_snapshot_safe()
    except (H11AutoRuntimeSafetyError, V4GmoActualCoordinatorError, OSError):
        return "HALTED", None
    if snapshot.unknown_halt_latched or snapshot.pending_transport:
        return "HALTED", entries_today
    if contract.generation.generation_label in {
        G064_GENERATION_LABEL,
        G065_GENERATION_LABEL,
        G066_GENERATION_LABEL,
        G067_GENERATION_LABEL,
        G068_GENERATION_LABEL,
        G069_GENERATION_LABEL,
    }:
        if contract.generation.generation_label == G069_GENERATION_LABEL:
            position_evidence = load_g069_position_reconciliation_no_post(
                reviewed_files_digest=contract.reviewed_files_digest,
                generation_digest=contract.generation.digest,
                now_utc=datetime.now(UTC),
            )
        else:
            position_evidence = (
                load_g065_position_reconciliation_no_post
                if contract.generation.generation_label
                in {
                    G065_GENERATION_LABEL,
                    G066_GENERATION_LABEL,
                    G067_GENERATION_LABEL,
                    G068_GENERATION_LABEL,
                }
                else load_g064_position_reconciliation_no_post
            )(
                state_root=root,
                generation_digest=contract.generation.digest,
                now_utc=datetime.now(UTC),
            )
        if not position_evidence.evidence_available:
            return "HALTED", entries_today
        if snapshot.cycle_present != position_evidence.position_open:
            return "HALTED", entries_today
        if position_evidence.position_open:
            if not (
                position_evidence.protection_confirmed
                and position_evidence.ownership_exact
                and position_evidence.quantity_matches
                and position_evidence.generation_bound
            ):
                return "HALTED", entries_today
            return "POSITION_OPEN", entries_today
        return "FLAT", entries_today
    if snapshot.external_flat_reconciled:
        return "FLAT", entries_today
    if (
        snapshot.cycle_present
        and snapshot.entry_attempted_at_utc is not None
        and not snapshot.flat_reconciled
    ):
        if not snapshot.protection_confirmed:
            return "HALTED", entries_today
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
        current = _safe_status(contract)
        if contract.generation.generation_label == G074_GENERATION_LABEL:
            if current.get("release_state") != "ENABLED":
                raise G074Error("G074_RELEASE_CAPABILITY_LOCKED")
        elif contract.generation.generation_label != G070_GENERATION_LABEL and (
            current["runtime_activation_available"] is not True
            or current["effective_state"] == "HALTED"
        ):
            raise V4G064ActivationError("ARM_ON_RUNTIME_NOT_READY")
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
        V4G064ActivationError,
        V4G065ActivationError,
        V4G066ActivationError,
        V4G067ActivationError,
        V4G068ActivationError,
        V4G069ActivationError,
        G070Error,
        G071Error,
        G072Error,
        G073Error,
        G074Error,
        OSError,
        ValueError,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post("/off")
def turn_off(request_body: ArmChangeRequest, request: Request) -> dict:
    _require_local_csrf(request)
    try:
        require_clean_main(repository=REPOSITORY)
        contract = _load_current_contract()
        if request_body.expected_generation_digest != contract.generation.digest:
            raise V4UnattendedLiveArmStateError("ARM_STATE_GENERATION_MISMATCH")
        if request_body.expected_reviewed_files_digest != contract.reviewed_files_digest:
            raise V4UnattendedLiveArmStateError("ARM_STATE_REVIEWED_FILES_MISMATCH")
        _arm_store(contract).set_desired_state(
            desired_state=V4ArmDesiredState.DISARMED,
            expected_revision=request_body.expected_revision,
            generation_digest=contract.generation.digest,
            reviewed_files_digest=contract.reviewed_files_digest,
            changed_at_utc=datetime.now(UTC),
        )
        return _safe_status(contract)
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
