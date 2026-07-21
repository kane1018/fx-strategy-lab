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
from app.h11_auto.v4_gmo_actual_coordinator import V4GmoActualCoordinatorStore
from app.h11_auto.v4_gmo_contracts import (
    v4_gmo_scheduled_time_exit_at,
    v4_gmo_trading_day_jst,
    v4_gmo_weekend_flat_target_at,
)
from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root


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
    broker_read: bool = False
    broker_write: bool = False
    actual_post_count: int = 0

    def __bool__(self) -> bool:
        return False


class V4GmoMonitorSupervisor:
    def __init__(self, *, repository: Path, generation: V4GmoFrozenGeneration) -> None:
        self.repository = repository.resolve()
        self.generation = generation
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
            )
            self._write_heartbeat(tick)
            return tick
        # OBSERVER open: a 15s tick landing inside a normal in-flight pending
        # window must not convert it into a permanent halt — the restart latch
        # belongs to the owning trading process (2026-07-21 false-latch incident).
        store = V4GmoActualCoordinatorStore.open_monitor_observer(database)
        store.bind_generation(self.generation)
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
        )
        self._write_heartbeat(tick)
        return tick

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
                wait(interval_seconds)
        finally:
            self.close()

    def _latch_halt_on_internal_failure(self, now_utc: datetime) -> None:
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
