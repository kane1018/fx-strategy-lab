"""Bounded wall-clock H-11 v3 fake soak runner (no-POST).

This is a self-terminating test job, not a service or scheduler.  Completion is
driven by timezone-aware wall-clock comparison.  The injected clock and waiter
make the lifecycle deterministic in tests without sleeping.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from threading import Event

from app.services.h11_v3_fault_soak import (
    H11V3FaultSoakReport,
    H11V3FaultSoakStatus,
    run_h11_v3_fault_soak_no_post,
)

WALL_CLOCK_24H_SECONDS = 24 * 60 * 60


class H11V3WallClockSoakError(RuntimeError):
    """Safe wall-clock soak configuration or state error."""


class H11V3WallClockSoakState(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED_SAFE = "FAILED_SAFE"


@dataclass(frozen=True)
class H11V3WallClockSoakStatus:
    state: H11V3WallClockSoakState
    started_at_utc: str
    expected_complete_at_utc: str
    last_check_at_utc: str
    completed_at_utc: str | None
    duration_seconds: int
    poll_seconds: int
    soak_interval_seconds: int
    soak_runs_completed: int
    last_soak_status: str
    wall_clock_24h_soak_completed: bool
    bounded_self_terminating_job: bool = True
    resident_process: bool = False
    cron: bool = False
    actual_post_count: int = 0
    broker_read_performed: bool = False
    broker_write_performed: bool = False
    credential_read: bool = False
    external_notification_sent: bool = False
    raw_id_value_exposure: bool = False

    def __bool__(self) -> bool:
        return False


def run_h11_v3_wall_clock_soak_no_post(
    *,
    duration_seconds: int,
    poll_seconds: int,
    soak_interval_seconds: int,
    status_path: Path,
    target_cycle_count: int = 100,
    clock: Callable[[], datetime] | None = None,
    waiter: Callable[[float], object] | None = None,
    soak_runner: Callable[[], H11V3FaultSoakReport] | None = None,
) -> H11V3WallClockSoakStatus:
    if duration_seconds <= 0 or poll_seconds <= 0 or soak_interval_seconds <= 0:
        raise H11V3WallClockSoakError("wall-clock soak intervals must be positive")
    if target_cycle_count < 100:
        raise H11V3WallClockSoakError("synthetic cycle count must be at least 100")

    now_fn = clock or _utc_now
    wait_fn = waiter or _wait
    run_soak = soak_runner or (
        lambda: run_h11_v3_fault_soak_no_post(
            target_cycle_count=target_cycle_count
        )
    )
    started_at = _normalized_now(now_fn)
    expected_complete_at = started_at + timedelta(seconds=duration_seconds)
    last_soak_at: datetime | None = None
    last_soak_status = "NOT_RUN"
    soak_runs_completed = 0

    while True:
        now = _normalized_now(now_fn)
        if now >= expected_complete_at:
            final = _status(
                state=H11V3WallClockSoakState.COMPLETED,
                started_at=started_at,
                expected_complete_at=expected_complete_at,
                last_check_at=now,
                completed_at=now,
                duration_seconds=duration_seconds,
                poll_seconds=poll_seconds,
                soak_interval_seconds=soak_interval_seconds,
                soak_runs_completed=soak_runs_completed,
                last_soak_status=last_soak_status,
            )
            _write_status(status_path, final)
            return final

        if (
            last_soak_at is None
            or (now - last_soak_at).total_seconds() >= soak_interval_seconds
        ):
            report = run_soak()
            last_soak_status = report.status.value
            if report.status is not H11V3FaultSoakStatus.PASSED_SYNTHETIC_NO_POST:
                failed = _status(
                    state=H11V3WallClockSoakState.FAILED_SAFE,
                    started_at=started_at,
                    expected_complete_at=expected_complete_at,
                    last_check_at=now,
                    completed_at=now,
                    duration_seconds=duration_seconds,
                    poll_seconds=poll_seconds,
                    soak_interval_seconds=soak_interval_seconds,
                    soak_runs_completed=soak_runs_completed,
                    last_soak_status=last_soak_status,
                )
                _write_status(status_path, failed)
                return failed
            soak_runs_completed += 1
            last_soak_at = now

        running = _status(
            state=H11V3WallClockSoakState.RUNNING,
            started_at=started_at,
            expected_complete_at=expected_complete_at,
            last_check_at=now,
            completed_at=None,
            duration_seconds=duration_seconds,
            poll_seconds=poll_seconds,
            soak_interval_seconds=soak_interval_seconds,
            soak_runs_completed=soak_runs_completed,
            last_soak_status=last_soak_status,
        )
        _write_status(status_path, running)
        remaining_seconds = (expected_complete_at - now).total_seconds()
        wait_fn(min(float(poll_seconds), remaining_seconds))


def read_h11_v3_wall_clock_soak_status(
    status_path: Path,
) -> H11V3WallClockSoakStatus:
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
        payload["state"] = H11V3WallClockSoakState(payload["state"])
        status = H11V3WallClockSoakStatus(**payload)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError) as error:
        raise H11V3WallClockSoakError("wall-clock soak status is unavailable") from error
    return status


def _status(
    *,
    state: H11V3WallClockSoakState,
    started_at: datetime,
    expected_complete_at: datetime,
    last_check_at: datetime,
    completed_at: datetime | None,
    duration_seconds: int,
    poll_seconds: int,
    soak_interval_seconds: int,
    soak_runs_completed: int,
    last_soak_status: str,
) -> H11V3WallClockSoakStatus:
    return H11V3WallClockSoakStatus(
        state=state,
        started_at_utc=_format_time(started_at),
        expected_complete_at_utc=_format_time(expected_complete_at),
        last_check_at_utc=_format_time(last_check_at),
        completed_at_utc=(
            _format_time(completed_at) if completed_at is not None else None
        ),
        duration_seconds=duration_seconds,
        poll_seconds=poll_seconds,
        soak_interval_seconds=soak_interval_seconds,
        soak_runs_completed=soak_runs_completed,
        last_soak_status=last_soak_status,
        wall_clock_24h_soak_completed=(
            state is H11V3WallClockSoakState.COMPLETED
            and duration_seconds >= WALL_CLOCK_24H_SECONDS
        ),
    )


def _write_status(path: Path, status: H11V3WallClockSoakStatus) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    payload = asdict(status)
    payload["state"] = status.state.value
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))
        handle.flush()
        os.fsync(handle.fileno())
    temp_path.replace(path)


def _normalized_now(clock: Callable[[], datetime]) -> datetime:
    current = clock()
    if current.tzinfo is None:
        raise H11V3WallClockSoakError("wall-clock source must be timezone-aware")
    return current.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _wait(seconds: float) -> None:
    Event().wait(seconds)


def _format_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")
