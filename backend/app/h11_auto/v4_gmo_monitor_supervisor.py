"""Monitor-only resident supervisor for the H-11 v4 G013 canary.

It emits only safe local markers and latches the coordinator HALT when a
protection or weekend-flat deadline is missed.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import DeadManStore, PhaseBRiskStore
from app.h11_auto.v4_gmo_actual_coordinator import V4GmoActualCoordinatorStore
from app.h11_auto.v4_gmo_contracts import (
    v4_gmo_scheduled_time_exit_at,
    v4_gmo_trading_day_jst,
    v4_gmo_weekend_flat_target_at,
)
from app.h11_auto.v4_gmo_generation import (
    V4GmoFrozenGeneration,
    v4_gmo_dead_man_policy,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_g038_unattended_activation import (
    verify_g038_generation_activation,
)
from app.services.h11_v4_unattended_live_heartbeat_chain import (
    V4HeartbeatChainStore,
    v4_unattended_runtime_heartbeat_policy,
)

_G052_GENERATION_LABEL = "H11_AUTO_30M_20260730_G052"
_G051_FLAT_SOURCE_GENERATION_DIGEST = (
    "sha256:640556dd46a5066b8d7223f76d5196c22e4c65449c7d2371e526662049b9bf1c"
)


class V4GmoMonitorSupervisorError(RuntimeError):
    """Fixed safe supervisor failure."""


@dataclass(frozen=True)
class V4GmoMonitorTick:
    observed_at_utc: str
    status: str
    generation_digest: str
    generation_bound: bool
    cycle_present: bool
    exit_dispatch_required: bool
    flat_target_missed: bool
    persistent_halt: bool
    runtime_risk_ready: bool = False
    dead_man_alive: bool = False
    heartbeat_chain_beat: bool = False
    broker_read: bool = False
    broker_write: bool = False
    actual_post_count: int = 0

    def __bool__(self) -> bool:
        return False


class V4GmoMonitorSupervisor:
    def __init__(
        self,
        *,
        repository: Path,
        generation: V4GmoFrozenGeneration,
        runtime_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.repository = repository.resolve()
        self.generation = generation
        self.runtime_clock = runtime_clock
        self.state_root = v4_gmo_runtime_state_root(
            repository=self.repository,
            generation_digest=generation.digest,
        )
        if self.state_root.is_symlink():
            raise V4GmoMonitorSupervisorError("V4_SUPERVISOR_STATE_ROOT_INVALID")
        self.lock = H11AutoProcessLock(self.state_root / "supervisor.lock")

    def acquire_single_process(self) -> None:
        if not self.lock.acquire():
            raise V4GmoMonitorSupervisorError("V4_SUPERVISOR_ALREADY_RUNNING")

    def close(self) -> None:
        self.lock.release()

    def run_tick(self, *, now_utc: datetime) -> V4GmoMonitorTick:
        if now_utc.tzinfo is None or not self.lock.held:
            raise V4GmoMonitorSupervisorError("V4_SUPERVISOR_TICK_INVALID")
        now_utc = now_utc.astimezone(UTC)
        runtime_lock: H11AutoProcessLock | None = None
        monitor_owns_runtime: bool | None = None
        if self.generation.generation_label in {
            "H11_AUTO_30M_20260729_G040",
            "H11_AUTO_30M_20260729_G041",
            "H11_AUTO_30M_20260730_G047",
            "H11_AUTO_30M_20260730_G048",
            "H11_AUTO_30M_20260730_G049",
            "H11_AUTO_30M_20260730_G050",
            "H11_AUTO_30M_20260730_G051",
            "H11_AUTO_30M_20260730_G052",
        }:
            runtime_lock = H11AutoProcessLock(
                self.state_root / "process.lock"
            )
            monitor_owns_runtime = runtime_lock.acquire()
        try:
            return self._run_tick_locked(
                now_utc=now_utc,
                monitor_owns_runtime=monitor_owns_runtime,
            )
        finally:
            if runtime_lock is not None and monitor_owns_runtime:
                runtime_lock.release()

    def _run_tick_locked(
        self,
        *,
        now_utc: datetime,
        monitor_owns_runtime: bool | None,
    ) -> V4GmoMonitorTick:
        runtime_safety_ready = False
        if self.generation.generation_label in {
            "H11_AUTO_30M_20260729_G040",
            "H11_AUTO_30M_20260729_G041",
            "H11_AUTO_30M_20260730_G047",
            "H11_AUTO_30M_20260730_G048",
            "H11_AUTO_30M_20260730_G049",
            "H11_AUTO_30M_20260730_G050",
            "H11_AUTO_30M_20260730_G051",
            "H11_AUTO_30M_20260730_G052",
        }:
            self._maintain_g040_runtime_safety(
                monitor_owns_runtime=monitor_owns_runtime is True,
            )
            runtime_safety_ready = True
        shared_write_allowed = monitor_owns_runtime is not False
        database = self.state_root / "coordinator.sqlite3"
        if not database.is_file() or database.is_symlink():
            tick = V4GmoMonitorTick(
                observed_at_utc=now_utc.isoformat(),
                status="WAITING_FOR_CANONICAL_RUNTIME",
                generation_digest=self.generation.digest,
                generation_bound=False,
                cycle_present=False,
                exit_dispatch_required=False,
                flat_target_missed=False,
                persistent_halt=False,
                runtime_risk_ready=runtime_safety_ready,
                dead_man_alive=runtime_safety_ready,
                heartbeat_chain_beat=runtime_safety_ready,
            )
            self._write_heartbeat(tick)
            return tick
        # OBSERVER open: a 15s tick landing inside a normal in-flight pending
        # window must not convert it into a permanent halt — the restart latch
        # belongs to the owning trading process (2026-07-21 false-latch incident).
        store = V4GmoActualCoordinatorStore.open_monitor_observer(database)
        with store._connect() as connection:
            generation_row = connection.execute(
                "SELECT value FROM metadata WHERE key='generation_digest'"
            ).fetchone()
        if (
            generation_row is None
            or generation_row["value"] != self.generation.digest
        ):
            raise V4GmoMonitorSupervisorError(
                "V4_SUPERVISOR_COORDINATOR_GENERATION_MISMATCH"
            )
        snapshot = store.monitor_snapshot_safe()
        dispatch_required = False
        flat_target_missed = False
        if snapshot.entry_attempted_at_utc is not None and not snapshot.flat_reconciled:
            # Keyed by the CYCLE's own entry day (not "now"'s day, which can differ
            # if the exit lands after local midnight): at most one cycle is ever
            # unresolved at a time, so this is naturally unique per cycle without
            # needing cycle_ref threaded through every marker.
            cycle_day = v4_gmo_trading_day_jst(snapshot.entry_attempted_at_utc)
            protection_deadline = snapshot.entry_attempted_at_utc.timestamp() + 15.0
            if now_utc.timestamp() > protection_deadline and not snapshot.protection_confirmed:
                if shared_write_allowed:
                    store.engage_unknown_halt()
                    self._write_once_marker(
                        f"protection-deadline-missed.{cycle_day}.json",
                        status="PERSISTENT_HALT_PROTECTION_DEADLINE_MISSED",
                        observed_at_utc=now_utc,
                    )
            exit_at = v4_gmo_scheduled_time_exit_at(
                entry_time_utc=snapshot.entry_attempted_at_utc
            )
            if exit_at is not None and now_utc >= exit_at:
                dispatch_required = True
                if shared_write_allowed:
                    self._write_once_marker(
                        f"exit-sequence-dispatch-required.{cycle_day}.json",
                        status="GENERATION_BOUND_EXIT_DISPATCH_REQUIRED",
                        observed_at_utc=now_utc,
                    )
            flat_target = v4_gmo_weekend_flat_target_at(
                entry_time_utc=snapshot.entry_attempted_at_utc
            )
            if flat_target is not None and now_utc >= flat_target:
                flat_target_missed = True
                if shared_write_allowed:
                    store.engage_unknown_halt()
                    self._write_once_marker(
                        f"flat-target-missed.{cycle_day}.json",
                        status="PERSISTENT_HALT_WEEKEND_FLAT_TARGET_MISSED",
                        observed_at_utc=now_utc,
                    )
        persistent_halt = store.unknown_halt_latched()
        status = (
            "PERSISTENT_HALT"
            if persistent_halt
            else "EXIT_DISPATCH_REQUIRED"
            if dispatch_required
            else "MONITORING"
        )
        tick = V4GmoMonitorTick(
            observed_at_utc=now_utc.isoformat(),
            status=status,
            generation_digest=self.generation.digest,
            generation_bound=snapshot.generation_bound,
            cycle_present=snapshot.cycle_present,
            exit_dispatch_required=dispatch_required,
            flat_target_missed=flat_target_missed,
            persistent_halt=persistent_halt,
            runtime_risk_ready=runtime_safety_ready,
            dead_man_alive=runtime_safety_ready,
            heartbeat_chain_beat=runtime_safety_ready,
        )
        self._write_heartbeat(tick)
        return tick

    def _maintain_g040_runtime_safety(
        self,
        *,
        monitor_owns_runtime: bool,
    ) -> None:
        risk_policy = v4_gmo_risk_policy()
        release = verify_g038_generation_activation(generation=self.generation)
        target_risk_store = PhaseBRiskStore(
            self.state_root / "risk.json",
            policy=risk_policy,
        )
        source_risk_store = PhaseBRiskStore(
            v4_gmo_runtime_state_root(
                repository=self.repository,
                generation_digest=(
                    _G051_FLAT_SOURCE_GENERATION_DIGEST
                    if self.generation.generation_label
                    == _G052_GENERATION_LABEL
                    else release.predecessor_halt_generation_digest
                ),
            )
            / "risk.json",
            policy=risk_policy,
        )
        if (
            source_risk_store.path.is_symlink()
            or not source_risk_store.path.is_file()
        ):
            raise V4GmoMonitorSupervisorError(
                "V4_SUPERVISOR_SOURCE_RISK_STATE_MISSING"
            )
        source_risk_state = source_risk_store.load()
        dead_man_store = DeadManStore(
            self.state_root / "dead-man.json",
            policy=v4_gmo_dead_man_policy(),
        )
        if monitor_owns_runtime:
            if not target_risk_store.path.exists():
                target_risk_store.save(source_risk_state)
            target_risk_store.load()
            coordinator = V4GmoActualCoordinatorStore(
                self.state_root / "coordinator.sqlite3",
                _latch_pending_restart_halt=False,
            )
            coordinator.bind_generation(self.generation)
            if source_risk_state.current_day_jst is not None:
                coordinator.initialize_inherited_market_attempt_baseline_once(
                    source_generation_digest=(
                        _G051_FLAT_SOURCE_GENERATION_DIGEST
                        if self.generation.generation_label
                        == _G052_GENERATION_LABEL
                        else release.predecessor_halt_generation_digest
                    ),
                    target_generation_digest=self.generation.digest,
                    trading_day_jst=source_risk_state.current_day_jst,
                    attempt_count=source_risk_state.entries_today,
                )
            dead_man_store.heartbeat(heartbeat_utc=self.runtime_clock())
            V4HeartbeatChainStore(
                self.state_root / "unattended-heartbeat-chain.json",
                policy=v4_unattended_runtime_heartbeat_policy(),
            ).beat(now_utc=self.runtime_clock())
        else:
            target_risk_store = PhaseBRiskStore(
                self.state_root / "risk.json",
                policy=risk_policy,
            )
            if (
                not target_risk_store.path.is_file()
                or target_risk_store.path.is_symlink()
                or not (self.state_root / "coordinator.sqlite3").is_file()
            ):
                raise V4GmoMonitorSupervisorError(
                    "V4_SUPERVISOR_FOREGROUND_RUNTIME_STATE_MISSING"
                )
            target_risk_store.load()
            dead_man = dead_man_store.evaluate_current(clock=self.runtime_clock)
            if not dead_man.alive:
                raise V4GmoMonitorSupervisorError(
                    "V4_SUPERVISOR_FOREGROUND_DEAD_MAN_NOT_ALIVE"
                )
            chain = V4HeartbeatChainStore(
                self.state_root / "unattended-heartbeat-chain.json",
                policy=v4_unattended_runtime_heartbeat_policy(),
            ).assess(now_utc=self.runtime_clock())
            if (
                chain.heartbeat_age_seconds is None
                or chain.heartbeat_age_seconds < 0
                or chain.heartbeat_age_seconds
                > v4_unattended_runtime_heartbeat_policy().maximum_gap_seconds
            ):
                raise V4GmoMonitorSupervisorError(
                    "V4_SUPERVISOR_FOREGROUND_HEARTBEAT_CHAIN_NOT_ALIVE"
                )

    def run_forever(
        self,
        *,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        wait: Callable[[float], None] = time.sleep,
        interval_seconds: float = 15.0,
    ) -> None:
        if interval_seconds != 15.0:
            raise V4GmoMonitorSupervisorError("V4_SUPERVISOR_INTERVAL_FROZEN")
        self.acquire_single_process()
        try:
            while True:
                try:
                    self.run_tick(now_utc=wall_clock())
                except Exception:  # noqa: BLE001
                    self._latch_halt_on_internal_failure(wall_clock())
                    if self.generation.generation_label in {
                        "H11_AUTO_30M_20260729_G040",
                        "H11_AUTO_30M_20260729_G041",
                        "H11_AUTO_30M_20260730_G047",
                        "H11_AUTO_30M_20260730_G048",
                        "H11_AUTO_30M_20260730_G049",
                        "H11_AUTO_30M_20260730_G050",
                        "H11_AUTO_30M_20260730_G051",
                        "H11_AUTO_30M_20260730_G052",
                    }:
                        raise
                wait(interval_seconds)
        finally:
            self.close()

    def _latch_halt_on_internal_failure(self, now_utc: datetime) -> None:
        runtime_lock: H11AutoProcessLock | None = None
        runtime_lock_held = False
        if self.generation.generation_label in {
            "H11_AUTO_30M_20260729_G040",
            "H11_AUTO_30M_20260729_G041",
            "H11_AUTO_30M_20260730_G047",
            "H11_AUTO_30M_20260730_G048",
            "H11_AUTO_30M_20260730_G049",
            "H11_AUTO_30M_20260730_G050",
            "H11_AUTO_30M_20260730_G051",
            "H11_AUTO_30M_20260730_G052",
        }:
            runtime_lock = H11AutoProcessLock(
                self.state_root / "process.lock"
            )
            runtime_lock_held = runtime_lock.acquire()
            if not runtime_lock_held:
                return
        try:
            database = self.state_root / "coordinator.sqlite3"
            if database.is_file() and not database.is_symlink():
                try:
                    V4GmoActualCoordinatorStore.open_monitor_observer(
                        database
                    ).engage_unknown_halt()
                except Exception:  # noqa: BLE001
                    pass
            self._write_once_marker(
                "supervisor-internal-failure.json",
                status="PERSISTENT_HALT_SUPERVISOR_INTERNAL_FAILURE",
                observed_at_utc=now_utc,
            )
        finally:
            if runtime_lock is not None and runtime_lock_held:
                runtime_lock.release()

    def _write_heartbeat(self, tick: V4GmoMonitorTick) -> None:
        self._write_atomic(self.state_root / "supervisor-heartbeat.json", asdict(tick))

    def _write_once_marker(
        self, name: str, *, status: str, observed_at_utc: datetime
    ) -> None:
        path = self.state_root / name
        if path.exists():
            return
        payload = {
            "generation_digest": self.generation.digest,
            "observed_at_utc": observed_at_utc.astimezone(UTC).isoformat(),
            "status": status,
        }
        self._write_atomic(path, payload, exclusive=True)

    @staticmethod
    def _write_atomic(
        path: Path, payload: dict[str, object], *, exclusive: bool = False
    ) -> None:
        if path.is_symlink() or path.parent.is_symlink():
            raise V4GmoMonitorSupervisorError("V4_SUPERVISOR_MARKER_PATH_INVALID")
        path.parent.mkdir(parents=True, exist_ok=True)
        if exclusive:
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                return
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return
        temporary = path.with_suffix(path.suffix + ".tmp")
        if temporary.is_symlink():
            raise V4GmoMonitorSupervisorError("V4_SUPERVISOR_MARKER_PATH_INVALID")
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)

    def __repr__(self) -> str:
        return "V4GmoMonitorSupervisor(<generation-bound-monitor-only>)"

    def __bool__(self) -> bool:
        return False
