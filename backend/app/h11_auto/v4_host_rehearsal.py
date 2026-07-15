"""Finite host/supervisor rehearsal for H-11 v4 (fake-only/no-POST)."""

from __future__ import annotations

import plistlib
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.h11_auto.v4_activation_preparation import (
    V4ApprovedOperatorSelections,
    V4ClockObservation,
    assess_v4_clock,
)
from app.services.h11_v4_notification_binding_no_post import (
    H11V4DisabledDualRouteNotifier,
    H11V4NotificationEvent,
)


class V4HostRehearsalError(RuntimeError):
    """Safe finite rehearsal failure."""


class V4HostClock(Protocol):
    def monotonic(self) -> float: ...

    def now_utc(self) -> datetime: ...

    def wait(self, seconds: float) -> None: ...


class SystemV4HostClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    def wait(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass(frozen=True)
class V4HostRehearsalReport:
    status: str
    started_at_utc: str
    finished_at_utc: str
    observed_elapsed_seconds: float
    target_duration_seconds: float
    heartbeat_count: int
    clock_assessment_count: int
    primary_notification_ready: bool
    secondary_notification_ready: bool
    maximum_unprotected_window_contract_seconds: int
    measured_fake_pipeline_seconds: float
    supervisor_template_disabled: bool
    actual_post_count: int = 0
    broker_read_performed: bool = False
    broker_write_performed: bool = False
    credential_read_performed: bool = False
    external_notification_send_performed: bool = False
    resident_process_added: bool = False
    launchd_installed: bool = False
    cron: bool = False
    actual_activation_ready: bool = False

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __bool__(self) -> bool:
        return False


def render_disabled_launchd_template(*, python_executable: str, repository: Path) -> bytes:
    """Return a non-installed, disabled template with no credential material."""

    if not python_executable.startswith("/") or not repository.is_absolute():
        raise V4HostRehearsalError("launchd template paths must be absolute")
    payload = {
        "Label": "com.fxstrategylab.h11-v4-disabled-no-post",
        "ProgramArguments": [
            python_executable,
            "-m",
            "scripts.h11_auto_v4_host_rehearsal",
            "--duration-seconds",
            "15",
        ],
        "WorkingDirectory": str(repository / "backend"),
        "Disabled": True,
        "RunAtLoad": False,
        "KeepAlive": False,
        "ProcessType": "Background",
    }
    return plistlib.dumps(payload, sort_keys=True)


def run_v4_host_rehearsal_no_post(
    *,
    duration_seconds: float,
    notifier: H11V4DisabledDualRouteNotifier,
    clock: V4HostClock | None = None,
) -> V4HostRehearsalReport:
    """Run a bounded current-host rehearsal without broker or external I/O."""

    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, int | float)
        or not 0.1 <= duration_seconds <= 60.0
    ):
        raise V4HostRehearsalError("rehearsal duration must be between 0.1 and 60 seconds")
    if not isinstance(notifier, H11V4DisabledDualRouteNotifier):
        raise V4HostRehearsalError("rehearsal notifier must be the disabled fake binding")
    clock = clock or SystemV4HostClock()
    policy = V4ApprovedOperatorSelections()
    started_wall = clock.now_utc()
    started_tick = clock.monotonic()
    previous_wall: datetime | None = None
    previous_tick: float | None = None
    heartbeat_count = 0
    clock_assessment_count = 0
    primary_ready = True
    secondary_ready = True
    fake_pipeline_completed_tick: float | None = None
    next_heartbeat_at = started_tick
    while True:
        current_tick = clock.monotonic()
        elapsed = current_tick - started_tick
        if elapsed >= duration_seconds:
            break
        current_wall = clock.now_utc()
        assessment = assess_v4_clock(
            V4ClockObservation(
                wall_time_utc=current_wall,
                monotonic_seconds=current_tick,
                previous_wall_time_utc=previous_wall,
                previous_monotonic_seconds=previous_tick,
                system_clock_sync_known=True,
                absolute_clock_skew_seconds=0.0,
            )
        )
        clock_assessment_count += 1
        if assessment.halt_required:
            raise V4HostRehearsalError("host clock rehearsal failed closed")
        previous_wall = current_wall
        previous_tick = current_tick
        if current_tick >= next_heartbeat_at:
            result = notifier.notify_once(H11V4NotificationEvent.BOOT_RECONCILIATION_CLEAR)
            heartbeat_count += 1
            primary_ready = primary_ready and result.primary_ready
            secondary_ready = secondary_ready and result.secondary_ready
            if result.halt_required:
                raise V4HostRehearsalError("fake notification rehearsal failed closed")
            if fake_pipeline_completed_tick is None:
                fake_pipeline_completed_tick = clock.monotonic()
            next_heartbeat_at = current_tick + min(
                policy.heartbeat_interval_seconds,
                duration_seconds,
            )
        remaining = duration_seconds - elapsed
        clock.wait(min(0.25, remaining))
    finished_tick = clock.monotonic()
    finished_wall = clock.now_utc()
    measured = max(0.0, finished_tick - started_tick)
    if fake_pipeline_completed_tick is None:
        raise V4HostRehearsalError("fake pipeline completion was not observed")
    pipeline_elapsed = max(0.0, fake_pipeline_completed_tick - started_tick)
    status = (
        "PASSED_FAKE_ONLY_NOT_ACTIVATED"
        if measured >= duration_seconds
        and pipeline_elapsed <= 15
        and primary_ready
        and secondary_ready
        else "FAILED_FAKE_ONLY"
    )
    return V4HostRehearsalReport(
        status=status,
        started_at_utc=started_wall.isoformat(),
        finished_at_utc=finished_wall.isoformat(),
        observed_elapsed_seconds=measured,
        target_duration_seconds=float(duration_seconds),
        heartbeat_count=heartbeat_count,
        clock_assessment_count=clock_assessment_count,
        primary_notification_ready=primary_ready,
        secondary_notification_ready=secondary_ready,
        maximum_unprotected_window_contract_seconds=15,
        measured_fake_pipeline_seconds=pipeline_elapsed,
        supervisor_template_disabled=True,
    )
