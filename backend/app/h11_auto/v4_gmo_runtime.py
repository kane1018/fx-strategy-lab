"""Finite operational runtime for the relaxed GMO v4 profile (fake-only/no-POST)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

from app.h11_auto.boundary import FakeNotifier, NotificationCategory
from app.h11_auto.contracts import FormalSignal, SignalDecision
from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import (
    AutoRiskStopState,
    DeadManStore,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
    evaluate_risk_before_entry,
    record_risk_entry_attempt,
)
from app.h11_auto.v4_gmo_boundary import (
    FakeV4GmoBroker,
    V4GmoBoundaryError,
    V4GmoSyntheticBroker,
)
from app.h11_auto.v4_gmo_contracts import (
    V4GmoBrokerSnapshot,
    V4GmoExecutionPolicy,
    V4GmoPreflightSnapshot,
    V4GmoProtectionStatus,
)
from app.h11_auto.v4_gmo_engine import (
    H11V4GmoNoPostEngine,
    V4GmoClock,
    V4GmoCycleResult,
    V4GmoCycleStatus,
)
from app.h11_auto.v4_gmo_persistence import V4GmoStateStore

JST = ZoneInfo("Asia/Tokyo")


class V4GmoRuntimeError(RuntimeError):
    """Fail-closed v4 runtime error carrying safe labels only."""


class V4GmoRuntimeStatus(str, Enum):
    NO_ACTION_STAY = "NO_ACTION_STAY"
    POSITION_PROTECTED_SYNTHETIC = "POSITION_PROTECTED_SYNTHETIC"
    FLAT_RECONCILED_SYNTHETIC = "FLAT_RECONCILED_SYNTHETIC"
    BLOCKED_SAFE = "BLOCKED_SAFE"
    HALTED_OPERATOR_REVIEW_REQUIRED = "HALTED_OPERATOR_REVIEW_REQUIRED"


class V4GmoOperatorReloadStatus(str, Enum):
    CLEARED_NO_POST = "CLEARED_NO_POST"
    NO_HALT_LATCHED = "NO_HALT_LATCHED"
    REFUSED_NOT_FLAT = "REFUSED_NOT_FLAT"


@dataclass(frozen=True)
class V4GmoRuntimeReport:
    status: V4GmoRuntimeStatus
    generation_label: str
    profile_version: str
    policy_config_hash: str
    selected_horizon: str
    boot_reconciled: bool
    process_lock_acquired: bool
    runtime_safety_bound: bool
    risk_stop_state: str
    risk_entry_recorded: bool
    dead_man_alive: bool
    notification_heartbeat_count: int
    cycle_created: bool
    final_state: str
    blocked_reasons: tuple[str, ...]
    action_attempt_count: int
    market_entry_attempt_count: int
    entry_remainder_cancel_attempt_count: int
    protection_attempt_count: int
    protection_cancel_attempt_count: int
    emergency_exit_attempt_count: int
    reconciliation_count: int
    journal_valid: bool
    journal_event_count: int
    actual_post_count: int = 0
    broker_read_performed: bool = False
    broker_write_performed: bool = False
    credential_read_performed: bool = False
    network_access_performed: bool = False
    resident_process: bool = False
    cron: bool = False
    live_ready: bool = False
    unattended_live_supported: bool = False

    def __bool__(self) -> bool:
        return False

    def to_safe_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass(frozen=True)
class V4GmoOperatorReloadReport:
    status: V4GmoOperatorReloadStatus
    process_lock_acquired: bool
    fresh_flat_reconciled: bool
    halted_cycle_cleared: bool
    global_halt_cleared: bool
    action_attempt_count: int
    reconciliation_count: int
    actual_post_count: int = 0
    broker_write_performed: bool = False
    credential_read_performed: bool = False
    network_access_performed: bool = False

    def __bool__(self) -> bool:
        return False

    def to_safe_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


def run_v4_gmo_once_no_post(
    *,
    signal: FormalSignal,
    policy: V4GmoExecutionPolicy,
    state_path: Path,
    lock_path: Path,
    risk_store: PhaseBRiskStore,
    risk_policy: PhaseBRiskPolicy,
    dead_man_store: DeadManStore,
    notifier: FakeNotifier,
    broker: V4GmoSyntheticBroker,
    generation_label: str,
    now_utc: datetime,
    clock: V4GmoClock | None = None,
) -> V4GmoRuntimeReport:
    """Execute at most one formal signal through the fake v4 boundary."""

    if now_utc.tzinfo is None:
        raise V4GmoRuntimeError("runtime clock must be timezone-aware")
    resolved_paths = {
        state_path.resolve(),
        lock_path.resolve(),
        risk_store.path.resolve(),
        dead_man_store.path.resolve(),
    }
    if len(resolved_paths) != 4:
        raise V4GmoRuntimeError("v4 runtime paths must be separate")
    if type(notifier) is not FakeNotifier or notifier.external_send_performed:  # noqa: E721
        raise V4GmoRuntimeError("v4 runtime notifier must remain fake-only")
    if type(broker) is not FakeV4GmoBroker:  # noqa: E721
        raise V4GmoRuntimeError("v4 runtime broker must remain exact fake type")
    lock = H11AutoProcessLock(lock_path)
    if not lock.acquire():
        raise V4GmoRuntimeError("v4 process lock is already held")
    store = V4GmoStateStore(state_path)
    try:
        generation = store.bind_generation(
            generation_label=generation_label,
            policy=policy,
            risk_policy_label=risk_policy.policy_label,
            risk_policy_digest=risk_policy.digest,
            dead_man_policy_label=dead_man_store.policy.policy_label,
            dead_man_policy_digest=dead_man_store.policy.digest,
        )
        risk_state = risk_store.load()
        if store.halt_latched():
            halt_reason = store.global_halt_reason_safe() or "PERSISTENT_V4_HALT_LATCHED"
            return _safe_report(
                status=V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED,
                generation=generation,
                store=store,
                broker=broker,
                notifier=notifier,
                risk_state=risk_state.stop_state,
                blocked_reasons=(halt_reason,),
            )
        if store.load_single_active_cycle_safe() is not None:
            return _safe_report(
                status=V4GmoRuntimeStatus.BLOCKED_SAFE,
                generation=generation,
                store=store,
                broker=broker,
                notifier=notifier,
                risk_state=risk_state.stop_state,
                boot_reconciled=False,
                blocked_reasons=("ACTIVE_V4_CYCLE_REQUIRES_RESUME",),
            )
        dead_man_store.heartbeat(heartbeat_utc=now_utc)
        dead_man = dead_man_store.evaluate(now_utc=now_utc)
        if not notifier.notify(NotificationCategory.HEARTBEAT) or not dead_man.alive:
            store.engage_global_halt(
                reason="RUNTIME_HEARTBEAT_OR_NOTIFICATION_FAILED",
                now_utc=now_utc,
            )
            return _safe_report(
                status=V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED,
                generation=generation,
                store=store,
                broker=broker,
                notifier=notifier,
                risk_state=risk_state.stop_state,
                dead_man_alive=dead_man.alive,
                blocked_reasons=("RUNTIME_HEARTBEAT_OR_NOTIFICATION_FAILED",),
            )
        try:
            boot = _boot_reconcile(broker)
        except V4GmoRuntimeError:
            store.engage_global_halt(
                reason="BOOT_RECONCILIATION_UNAVAILABLE",
                now_utc=now_utc,
            )
            return _safe_report(
                status=V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED,
                generation=generation,
                store=store,
                broker=broker,
                notifier=notifier,
                risk_state=risk_state.stop_state,
                boot_reconciled=False,
                blocked_reasons=("BOOT_RECONCILIATION_UNAVAILABLE",),
            )
        boot_reasons = _boot_blocked_reasons(boot)
        risk_gate = evaluate_risk_before_entry(
            state=risk_state,
            policy=risk_policy,
            cycle_day_jst=now_utc.astimezone(JST).date().isoformat(),
        )
        preflight = V4GmoPreflightSnapshot(
            boot_reconciled=not boot_reasons,
            process_lock_held=lock.held,
            data_fresh=True,
            clock_synchronized=True,
            notification_path_ready=True,
            broker_snapshot_fresh=boot.fresh,
            position_count=boot.position_count,
            active_order_count=int(
                boot.pending_entry_size > 0 or boot.protection_size > 0
            ),
            entries_today=risk_state.entries_today,
            daily_stop_clear=(
                risk_state.daily_loss_jpy_internal < risk_policy.daily_loss_limit_jpy
            ),
            monthly_stop_clear=(
                risk_state.monthly_loss_jpy_internal < risk_policy.monthly_loss_limit_jpy
            ),
            consecutive_loss_stop_clear=(
                risk_state.consecutive_losses < risk_policy.maximum_consecutive_losses
            ),
            operator_halt_clear=(
                AutoRiskStopState(risk_state.stop_state) is AutoRiskStopState.ACTIVE
            ),
        )
        if boot_reasons:
            store.engage_global_halt(reason=boot_reasons[0], now_utc=now_utc)
            return _safe_report(
                status=V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED,
                generation=generation,
                store=store,
                broker=broker,
                notifier=notifier,
                risk_state=risk_state.stop_state,
                boot_reconciled=False,
                blocked_reasons=boot_reasons,
            )
        preliminary_reasons: list[str] = []
        if signal.decision is not SignalDecision.STAY and not risk_gate.allowed:
            preliminary_reasons.extend(risk_gate.blocked_reasons)
        if preliminary_reasons:
            return _safe_report(
                status=V4GmoRuntimeStatus.BLOCKED_SAFE,
                generation=generation,
                store=store,
                broker=broker,
                notifier=notifier,
                risk_state=risk_state.stop_state,
                boot_reconciled=not boot_reasons,
                blocked_reasons=tuple(preliminary_reasons),
            )
        signal_valid = (
            signal.strategy_version == policy.strategy_version
            and signal.signal_config_hash == policy.signal_config_hash
            and signal.horizon is policy.selected_horizon
            and now_utc < signal.valid_until_utc
        )
        risk_entry_recorded = False
        if signal.decision is not SignalDecision.STAY and signal_valid:
            record_risk_entry_attempt(
                state=risk_state,
                policy=risk_policy,
                cycle_day_jst=now_utc.astimezone(JST).date().isoformat(),
            )
            risk_store.save(risk_state)
            risk_entry_recorded = True
        result = H11V4GmoNoPostEngine(
            store=store,
            broker=broker,
            clock=clock,
        ).run_signal_once_synthetic(
            signal=signal,
            policy=policy,
            preflight=preflight,
            now_utc=now_utc,
        )
        final_dead_man = dead_man_store.evaluate(now_utc=now_utc)
        return _report_from_cycle(
            result=result,
            generation=generation,
            store=store,
            broker=broker,
            notifier=notifier,
            risk_state=risk_state.stop_state,
            risk_entry_recorded=risk_entry_recorded,
            dead_man_alive=final_dead_man.alive,
        )
    finally:
        lock.release()


def resume_v4_gmo_once_no_post(
    *,
    policy: V4GmoExecutionPolicy,
    state_path: Path,
    lock_path: Path,
    risk_store: PhaseBRiskStore,
    risk_policy: PhaseBRiskPolicy,
    dead_man_store: DeadManStore,
    notifier: FakeNotifier,
    broker: V4GmoSyntheticBroker,
    generation_label: str,
    now_utc: datetime,
    clock: V4GmoClock | None = None,
) -> V4GmoRuntimeReport:
    """Resume one persisted active cycle without creating another entry intent."""

    _validate_runtime_inputs(
        now_utc=now_utc,
        state_path=state_path,
        lock_path=lock_path,
        risk_store=risk_store,
        dead_man_store=dead_man_store,
        notifier=notifier,
        broker=broker,
    )
    lock = H11AutoProcessLock(lock_path)
    if not lock.acquire():
        raise V4GmoRuntimeError("v4 process lock is already held")
    store = V4GmoStateStore(state_path)
    try:
        generation = store.bind_generation(
            generation_label=generation_label,
            policy=policy,
            risk_policy_label=risk_policy.policy_label,
            risk_policy_digest=risk_policy.digest,
            dead_man_policy_label=dead_man_store.policy.policy_label,
            dead_man_policy_digest=dead_man_store.policy.digest,
        )
        risk_state = risk_store.load()
        active = store.load_single_active_cycle_safe()
        if active is None:
            if store.halt_latched():
                reason = store.global_halt_reason_safe() or "PERSISTENT_V4_HALT_LATCHED"
                return _safe_report(
                    status=V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED,
                    generation=generation,
                    store=store,
                    broker=broker,
                    notifier=notifier,
                    risk_state=risk_state.stop_state,
                    blocked_reasons=(reason,),
                )
            return _safe_report(
                status=V4GmoRuntimeStatus.BLOCKED_SAFE,
                generation=generation,
                store=store,
                broker=broker,
                notifier=notifier,
                risk_state=risk_state.stop_state,
                blocked_reasons=("NO_ACTIVE_V4_CYCLE_TO_RESUME",),
            )
        if store.global_halt_reason_safe() is not None:
            return _safe_report(
                status=V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED,
                generation=generation,
                store=store,
                broker=broker,
                notifier=notifier,
                risk_state=risk_state.stop_state,
                blocked_reasons=(
                    store.global_halt_reason_safe() or "PERSISTENT_V4_HALT_LATCHED",
                ),
            )
        dead_man_store.heartbeat(heartbeat_utc=now_utc)
        dead_man = dead_man_store.evaluate(now_utc=now_utc)
        if not notifier.notify(NotificationCategory.HEARTBEAT) or not dead_man.alive:
            store.engage_global_halt(
                reason="RUNTIME_HEARTBEAT_OR_NOTIFICATION_FAILED",
                now_utc=now_utc,
            )
            return _safe_report(
                status=V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED,
                generation=generation,
                store=store,
                broker=broker,
                notifier=notifier,
                risk_state=risk_state.stop_state,
                dead_man_alive=dead_man.alive,
                blocked_reasons=("RUNTIME_HEARTBEAT_OR_NOTIFICATION_FAILED",),
            )
        result = H11V4GmoNoPostEngine(
            store=store,
            broker=broker,
            clock=clock,
        ).resume_synthetic(
            cycle_ref=active.cycle_ref,
            policy=policy,
            now_utc=now_utc,
        )
        return _report_from_cycle(
            result=result,
            generation=generation,
            store=store,
            broker=broker,
            notifier=notifier,
            risk_state=risk_state.stop_state,
            risk_entry_recorded=False,
            dead_man_alive=dead_man_store.evaluate(now_utc=now_utc).alive,
        )
    finally:
        lock.release()


def operator_reload_v4_gmo_no_post(
    *,
    state_path: Path,
    lock_path: Path,
    broker: V4GmoSyntheticBroker,
    confirmation: str,
    now_utc: datetime,
) -> V4GmoOperatorReloadReport:
    """Clear a v4 HALT only after an exact phrase and a fresh fake flat snapshot."""

    if confirmation != "H11_V4_GMO_OPERATOR_RELOAD_NO_POST":
        raise V4GmoRuntimeError("v4 operator reload confirmation mismatch")
    if now_utc.tzinfo is None:
        raise V4GmoRuntimeError("runtime clock must be timezone-aware")
    if state_path.resolve() == lock_path.resolve():
        raise V4GmoRuntimeError("v4 runtime paths must be separate")
    if type(broker) is not FakeV4GmoBroker:  # noqa: E721
        raise V4GmoRuntimeError("v4 runtime broker must remain exact fake type")
    lock = H11AutoProcessLock(lock_path)
    if not lock.acquire():
        raise V4GmoRuntimeError("v4 process lock is already held")
    store = V4GmoStateStore(state_path)
    try:
        halted = store.load_single_halted_cycle_safe()
        global_latched = store.global_halt_reason_safe() is not None
        if halted is None and not global_latched:
            return _reload_report(
                status=V4GmoOperatorReloadStatus.NO_HALT_LATCHED,
                broker=broker,
            )
        snapshot = _boot_reconcile(broker)
        if _boot_blocked_reasons(snapshot):
            return _reload_report(
                status=V4GmoOperatorReloadStatus.REFUSED_NOT_FLAT,
                broker=broker,
            )
        halted_cycle_cleared = False
        if halted is not None:
            store.clear_halted_cycle_no_post(
                cycle_ref=halted.cycle_ref,
                confirmation=confirmation,
                fresh_flat_confirmed=True,
                now_utc=now_utc,
            )
            halted_cycle_cleared = True
        global_halt_cleared = False
        if global_latched:
            store.clear_global_halt_no_post(
                confirmation=confirmation,
                fresh_flat_confirmed=True,
            )
            global_halt_cleared = True
        return _reload_report(
            status=V4GmoOperatorReloadStatus.CLEARED_NO_POST,
            broker=broker,
            halted_cycle_cleared=halted_cycle_cleared,
            global_halt_cleared=global_halt_cleared,
        )
    finally:
        lock.release()


def _boot_reconcile(broker: V4GmoSyntheticBroker) -> V4GmoBrokerSnapshot:
    try:
        return broker.reconcile_synthetic()
    except V4GmoBoundaryError as error:
        raise V4GmoRuntimeError("v4 boot reconciliation unavailable") from error


def _validate_runtime_inputs(
    *,
    now_utc: datetime,
    state_path: Path,
    lock_path: Path,
    risk_store: PhaseBRiskStore,
    dead_man_store: DeadManStore,
    notifier: FakeNotifier,
    broker: V4GmoSyntheticBroker,
) -> None:
    if now_utc.tzinfo is None:
        raise V4GmoRuntimeError("runtime clock must be timezone-aware")
    resolved_paths = {
        state_path.resolve(),
        lock_path.resolve(),
        risk_store.path.resolve(),
        dead_man_store.path.resolve(),
    }
    if len(resolved_paths) != 4:
        raise V4GmoRuntimeError("v4 runtime paths must be separate")
    if type(notifier) is not FakeNotifier or notifier.external_send_performed:  # noqa: E721
        raise V4GmoRuntimeError("v4 runtime notifier must remain fake-only")
    if type(broker) is not FakeV4GmoBroker:  # noqa: E721
        raise V4GmoRuntimeError("v4 runtime broker must remain exact fake type")


def _reload_report(
    *,
    status: V4GmoOperatorReloadStatus,
    broker: V4GmoSyntheticBroker,
    halted_cycle_cleared: bool = False,
    global_halt_cleared: bool = False,
) -> V4GmoOperatorReloadReport:
    return V4GmoOperatorReloadReport(
        status=status,
        process_lock_acquired=True,
        fresh_flat_reconciled=(status is V4GmoOperatorReloadStatus.CLEARED_NO_POST),
        halted_cycle_cleared=halted_cycle_cleared,
        global_halt_cleared=global_halt_cleared,
        action_attempt_count=0,
        reconciliation_count=getattr(broker, "reconciliation_count", 0),
        actual_post_count=broker.actual_post_count,
        broker_write_performed=broker.broker_write_performed,
        credential_read_performed=broker.credential_read_performed,
        network_access_performed=broker.network_access_performed,
    )


def _boot_blocked_reasons(snapshot: V4GmoBrokerSnapshot) -> tuple[str, ...]:
    checks = (
        (snapshot.fresh, "BOOT_BROKER_SNAPSHOT_STALE"),
        (snapshot.result_known, "BOOT_BROKER_RESULT_UNKNOWN"),
        (snapshot.position_count == 0, "BOOT_POSITION_NOT_FLAT"),
        (snapshot.filled_size == 0, "BOOT_FILL_STATE_NOT_FLAT"),
        (snapshot.pending_entry_size == 0, "BOOT_PENDING_ENTRY_EXISTS"),
        (snapshot.protection_size == 0, "BOOT_PROTECTION_ORDER_EXISTS"),
        (
            snapshot.protection_status is V4GmoProtectionStatus.NONE,
            "BOOT_PROTECTION_STATE_NOT_CLEAR",
        ),
    )
    return tuple(reason for passed, reason in checks if not passed)


def _report_from_cycle(
    *,
    result: V4GmoCycleResult,
    generation: object,
    store: V4GmoStateStore,
    broker: V4GmoSyntheticBroker,
    notifier: FakeNotifier,
    risk_state: str,
    risk_entry_recorded: bool,
    dead_man_alive: bool,
) -> V4GmoRuntimeReport:
    status_map = {
        V4GmoCycleStatus.NO_ACTION_STAY: V4GmoRuntimeStatus.NO_ACTION_STAY,
        V4GmoCycleStatus.BLOCKED_SAFE: V4GmoRuntimeStatus.BLOCKED_SAFE,
        V4GmoCycleStatus.POSITION_PROTECTED_SYNTHETIC: (
            V4GmoRuntimeStatus.POSITION_PROTECTED_SYNTHETIC
        ),
        V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC: (
            V4GmoRuntimeStatus.FLAT_RECONCILED_SYNTHETIC
        ),
        V4GmoCycleStatus.HALTED_OPERATOR_REVIEW_REQUIRED: (
            V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED
        ),
    }
    return _safe_report(
        status=status_map[result.status],
        generation=generation,
        store=store,
        broker=broker,
        notifier=notifier,
        risk_state=risk_state,
        risk_entry_recorded=risk_entry_recorded,
        dead_man_alive=dead_man_alive,
        cycle_created=result.cycle_ref is not None,
        final_state=result.final_state.value if result.final_state else "NONE",
        blocked_reasons=result.blocked_reasons,
        action_attempt_count=result.action_attempt_count,
        market_entry_attempt_count=result.market_entry_attempt_count,
        entry_remainder_cancel_attempt_count=result.cancel_attempt_count,
        protection_attempt_count=result.protection_attempt_count,
        protection_cancel_attempt_count=result.protection_cancel_attempt_count,
        emergency_exit_attempt_count=result.emergency_exit_attempt_count,
    )


def _safe_report(
    *,
    status: V4GmoRuntimeStatus,
    generation: object,
    store: V4GmoStateStore,
    broker: V4GmoSyntheticBroker,
    notifier: FakeNotifier,
    risk_state: str,
    boot_reconciled: bool = True,
    risk_entry_recorded: bool = False,
    dead_man_alive: bool = True,
    cycle_created: bool = False,
    final_state: str = "NONE",
    blocked_reasons: tuple[str, ...] = (),
    action_attempt_count: int = 0,
    market_entry_attempt_count: int = 0,
    entry_remainder_cancel_attempt_count: int = 0,
    protection_attempt_count: int = 0,
    protection_cancel_attempt_count: int = 0,
    emergency_exit_attempt_count: int = 0,
) -> V4GmoRuntimeReport:
    journal = store.verify_journal()
    required = (
        "generation_label",
        "profile_version",
        "policy_config_hash",
        "selected_horizon",
    )
    if any(not hasattr(generation, field) for field in required):
        raise V4GmoRuntimeError("v4 generation projection is invalid")
    return V4GmoRuntimeReport(
        status=status,
        generation_label=generation.generation_label,
        profile_version=generation.profile_version,
        policy_config_hash=generation.policy_config_hash,
        selected_horizon=generation.selected_horizon,
        boot_reconciled=boot_reconciled,
        process_lock_acquired=True,
        runtime_safety_bound=True,
        risk_stop_state=risk_state,
        risk_entry_recorded=risk_entry_recorded,
        dead_man_alive=dead_man_alive,
        notification_heartbeat_count=notifier.events.count(NotificationCategory.HEARTBEAT),
        cycle_created=cycle_created,
        final_state=final_state,
        blocked_reasons=blocked_reasons,
        action_attempt_count=action_attempt_count,
        market_entry_attempt_count=market_entry_attempt_count,
        entry_remainder_cancel_attempt_count=entry_remainder_cancel_attempt_count,
        protection_attempt_count=protection_attempt_count,
        protection_cancel_attempt_count=protection_cancel_attempt_count,
        emergency_exit_attempt_count=emergency_exit_attempt_count,
        reconciliation_count=getattr(broker, "reconciliation_count", 0),
        journal_valid=journal.valid,
        journal_event_count=journal.event_count,
        actual_post_count=broker.actual_post_count,
        broker_write_performed=broker.broker_write_performed,
        credential_read_performed=broker.credential_read_performed,
        network_access_performed=broker.network_access_performed,
    )
