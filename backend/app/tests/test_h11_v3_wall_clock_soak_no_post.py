"""Deterministic tests for the bounded H-11 v3 wall-clock fake soak."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.h11_v3_fault_soak import (
    H11V3FaultSoakStatus,
    run_h11_v3_fault_soak_no_post,
)
from app.services.h11_v3_wall_clock_soak import (
    WALL_CLOCK_24H_SECONDS,
    H11V3WallClockSoakError,
    H11V3WallClockSoakState,
    read_h11_v3_wall_clock_soak_status,
    run_h11_v3_wall_clock_soak_no_post,
)


class _FakeClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current

    def wait(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


def test_wall_clock_soak_uses_time_comparison_and_writes_safe_status(
    tmp_path: Path,
) -> None:
    clock = _FakeClock(datetime(2026, 7, 11, 0, 0, tzinfo=UTC))
    passed_report = run_h11_v3_fault_soak_no_post(target_cycle_count=100)
    status_path = tmp_path / "status.json"

    result = run_h11_v3_wall_clock_soak_no_post(
        duration_seconds=180,
        poll_seconds=60,
        soak_interval_seconds=60,
        status_path=status_path,
        clock=clock.now,
        waiter=clock.wait,
        soak_runner=lambda: passed_report,
    )

    assert result.state is H11V3WallClockSoakState.COMPLETED
    assert result.soak_runs_completed == 3
    assert result.wall_clock_24h_soak_completed is False
    assert result.bounded_self_terminating_job is True
    assert result.resident_process is False
    assert result.cron is False
    assert result.actual_post_count == 0
    assert result.broker_write_performed is False
    assert result.credential_read is False
    assert read_h11_v3_wall_clock_soak_status(status_path) == result


def test_exact_24h_duration_sets_completion_only_after_elapsed_wall_time(
    tmp_path: Path,
) -> None:
    clock = _FakeClock(datetime(2026, 7, 11, 0, 0, tzinfo=UTC))
    passed_report = run_h11_v3_fault_soak_no_post(target_cycle_count=100)
    result = run_h11_v3_wall_clock_soak_no_post(
        duration_seconds=WALL_CLOCK_24H_SECONDS,
        poll_seconds=12 * 60 * 60,
        soak_interval_seconds=12 * 60 * 60,
        status_path=tmp_path / "status.json",
        clock=clock.now,
        waiter=clock.wait,
        soak_runner=lambda: passed_report,
    )
    assert result.state is H11V3WallClockSoakState.COMPLETED
    assert result.soak_runs_completed == 2
    assert result.wall_clock_24h_soak_completed is True
    assert result.expected_complete_at_utc == "2026-07-12T00:00:00+00:00"


def test_failed_synthetic_run_stops_wall_clock_job_safely(tmp_path: Path) -> None:
    clock = _FakeClock(datetime(2026, 7, 11, 0, 0, tzinfo=UTC))
    passed_report = run_h11_v3_fault_soak_no_post(target_cycle_count=100)
    failed_report = replace(
        passed_report,
        status=H11V3FaultSoakStatus.FAILED_SYNTHETIC_SAFE,
    )
    result = run_h11_v3_wall_clock_soak_no_post(
        duration_seconds=60,
        poll_seconds=10,
        soak_interval_seconds=10,
        status_path=tmp_path / "status.json",
        clock=clock.now,
        waiter=clock.wait,
        soak_runner=lambda: failed_report,
    )
    assert result.state is H11V3WallClockSoakState.FAILED_SAFE
    assert result.soak_runs_completed == 0
    assert result.actual_post_count == 0


def test_invalid_intervals_naive_clock_and_bad_status_fail_closed(
    tmp_path: Path,
) -> None:
    with pytest.raises(H11V3WallClockSoakError, match="positive"):
        run_h11_v3_wall_clock_soak_no_post(
            duration_seconds=0,
            poll_seconds=1,
            soak_interval_seconds=1,
            status_path=tmp_path / "status.json",
        )
    with pytest.raises(H11V3WallClockSoakError, match="timezone-aware"):
        run_h11_v3_wall_clock_soak_no_post(
            duration_seconds=1,
            poll_seconds=1,
            soak_interval_seconds=1,
            status_path=tmp_path / "status.json",
            clock=lambda: datetime(2026, 7, 11),
        )
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("not-json", encoding="utf-8")
    with pytest.raises(H11V3WallClockSoakError, match="unavailable"):
        read_h11_v3_wall_clock_soak_status(bad_path)
