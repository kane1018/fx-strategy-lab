from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.h11_auto.wall_clock_soak import (
    H11AutoWallClockSoakError,
    WallClockSoakConfig,
    WallClockSoakStatus,
    current_h11_auto_implementation_digest,
    inspect_wall_clock_checkpoint,
    run_wall_clock_fake_soak_no_post,
)


class FakeClock:
    def __init__(self, *, extra_sleep_seconds: float = 0.0) -> None:
        self.tick = 0.0
        self.extra_sleep_seconds = extra_sleep_seconds
        self.base = datetime(2026, 7, 15, 7, 0, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.tick

    def now_utc(self) -> datetime:
        return self.base + timedelta(seconds=self.tick)

    def sleep(self, seconds: float) -> None:
        self.tick += seconds + self.extra_sleep_seconds


def test_bounded_wall_clock_soak_completes_and_writes_safe_checkpoint(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "soak.json"
    report = run_wall_clock_fake_soak_no_post(
        config=WallClockSoakConfig(
            duration_seconds=3,
            batch_interval_seconds=1,
            maximum_observation_gap_seconds=2,
        ),
        checkpoint_path=checkpoint,
        lock_path=tmp_path / "soak.lock",
        clock=FakeClock(),
    )
    assert report.status is WallClockSoakStatus.PASSED_FAKE_ONLY
    assert report.batch_count == 3
    assert report.synthetic_cycle_count == 300
    assert report.actual_post_count == 0
    assert report.network_access_performed is False
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["status"] == "PASSED_FAKE_ONLY"
    assert payload["actual_post_count"] == 0
    assert payload["checkpoint_schema_version"] == "H11_AUTO_PHASE_B_SOAK_V2_CODE_BOUND"
    assert payload["implementation_digest"] == current_h11_auto_implementation_digest()
    assert "intent_id" not in payload
    assert "credential" not in payload


def test_large_sleep_or_process_gap_fails_instead_of_counting_as_success(
    tmp_path: Path,
) -> None:
    report = run_wall_clock_fake_soak_no_post(
        config=WallClockSoakConfig(
            duration_seconds=20,
            batch_interval_seconds=1,
            maximum_observation_gap_seconds=2,
        ),
        checkpoint_path=tmp_path / "gap.json",
        lock_path=tmp_path / "gap.lock",
        clock=FakeClock(extra_sleep_seconds=5),
    )
    assert report.status is WallClockSoakStatus.FAILED_OBSERVATION_GAP
    assert report.batch_count == 1
    assert report.maximum_observed_gap_seconds == 6


def test_existing_checkpoint_is_never_overwritten_or_resumed(tmp_path: Path) -> None:
    checkpoint = tmp_path / "existing.json"
    checkpoint.write_text('{"status":"RUNNING_FAKE_ONLY"}\n', encoding="utf-8")
    before = checkpoint.read_text(encoding="utf-8")
    report = run_wall_clock_fake_soak_no_post(
        config=WallClockSoakConfig(
            duration_seconds=1,
            batch_interval_seconds=1,
            maximum_observation_gap_seconds=2,
        ),
        checkpoint_path=checkpoint,
        lock_path=tmp_path / "existing.lock",
        clock=FakeClock(),
    )
    assert report.status is WallClockSoakStatus.BLOCKED_CHECKPOINT_EXISTS
    assert checkpoint.read_text(encoding="utf-8") == before


def test_checkpoint_and_lock_must_be_separate(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    with pytest.raises(H11AutoWallClockSoakError, match="separate"):
        run_wall_clock_fake_soak_no_post(
            config=WallClockSoakConfig(
                duration_seconds=1,
                batch_interval_seconds=1,
                maximum_observation_gap_seconds=2,
            ),
            checkpoint_path=shared,
            lock_path=shared,
            clock=FakeClock(),
        )


def test_wall_clock_config_rejects_boolean_and_non_finite_values() -> None:
    with pytest.raises(H11AutoWallClockSoakError):
        WallClockSoakConfig(duration_seconds=True)  # type: ignore[arg-type]
    with pytest.raises(H11AutoWallClockSoakError):
        WallClockSoakConfig(maximum_observation_gap_seconds=float("nan"))


def test_checkpoint_inspection_reports_freshness_without_process_access(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "running.json"
    checkpoint.write_text(
        json.dumps(
            {
                "checkpoint_schema_version": "H11_AUTO_PHASE_B_SOAK_V2_CODE_BOUND",
                "implementation_digest": current_h11_auto_implementation_digest(),
                "status": "RUNNING_FAKE_ONLY",
                "started_at_utc": "2026-07-15T07:00:00+00:00",
                "last_heartbeat_at_utc": "2026-07-15T07:01:00+00:00",
                "batch_count": 2,
                "synthetic_cycle_count": 200,
                "actual_post_count": 0,
                "broker_write_performed": False,
                "network_access_performed": False,
                "credential_read_performed": False,
            }
        ),
        encoding="utf-8",
    )
    fresh = inspect_wall_clock_checkpoint(
        checkpoint,
        now_utc=datetime(2026, 7, 15, 7, 2, tzinfo=UTC),
        maximum_heartbeat_age_seconds=180,
    )
    assert fresh.heartbeat_fresh is True
    assert fresh.implementation_matches_current_code is True
    assert fresh.heartbeat_age_seconds == 60
    stale = inspect_wall_clock_checkpoint(
        checkpoint,
        now_utc=datetime(2026, 7, 15, 7, 5, tzinfo=UTC),
        maximum_heartbeat_age_seconds=180,
    )
    assert stale.heartbeat_fresh is False


def test_checkpoint_inspection_rejects_any_nonzero_post_marker(tmp_path: Path) -> None:
    checkpoint = tmp_path / "unsafe.json"
    checkpoint.write_text(
        json.dumps(
            {
                "checkpoint_schema_version": "H11_AUTO_PHASE_B_SOAK_V2_CODE_BOUND",
                "implementation_digest": current_h11_auto_implementation_digest(),
                "status": "RUNNING_FAKE_ONLY",
                "started_at_utc": "2026-07-15T07:00:00+00:00",
                "last_heartbeat_at_utc": "2026-07-15T07:01:00+00:00",
                "batch_count": 1,
                "synthetic_cycle_count": 100,
                "actual_post_count": 1,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(H11AutoWallClockSoakError, match="no-POST"):
        inspect_wall_clock_checkpoint(checkpoint)


def test_checkpoint_reports_code_digest_mismatch(tmp_path: Path) -> None:
    checkpoint = tmp_path / "different-code.json"
    checkpoint.write_text(
        json.dumps(
            {
                "checkpoint_schema_version": "H11_AUTO_PHASE_B_SOAK_V2_CODE_BOUND",
                "implementation_digest": "0" * 64,
                "status": "RUNNING_FAKE_ONLY",
                "started_at_utc": "2026-07-15T07:00:00+00:00",
                "last_heartbeat_at_utc": "2026-07-15T07:01:00+00:00",
                "batch_count": 1,
                "synthetic_cycle_count": 100,
                "actual_post_count": 0,
                "broker_write_performed": False,
                "network_access_performed": False,
                "credential_read_performed": False,
            }
        ),
        encoding="utf-8",
    )
    status = inspect_wall_clock_checkpoint(
        checkpoint,
        now_utc=datetime(2026, 7, 15, 7, 2, tzinfo=UTC),
    )
    assert status.heartbeat_fresh is True
    assert status.implementation_matches_current_code is False
