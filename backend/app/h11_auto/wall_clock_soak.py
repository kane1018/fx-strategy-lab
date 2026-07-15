"""Bounded wall-clock fake soak for H11 auto Phase B."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Protocol

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.soak import (
    MINIMUM_PHASE_A_SOAK_CYCLES,
    PhaseASoakStatus,
    run_phase_a_fault_soak_no_post,
)


class H11AutoWallClockSoakError(RuntimeError):
    """Fail-closed bounded wall-clock soak error."""


H11_AUTO_SOAK_CHECKPOINT_VERSION = "H11_AUTO_PHASE_B_SOAK_V2_CODE_BOUND"


class WallClockSoakStatus(str, Enum):
    PASSED_FAKE_ONLY = "PASSED_FAKE_ONLY"
    FAILED_OBSERVATION_GAP = "FAILED_OBSERVATION_GAP"
    FAILED_SYNTHETIC_BATCH = "FAILED_SYNTHETIC_BATCH"
    BLOCKED_CHECKPOINT_EXISTS = "BLOCKED_CHECKPOINT_EXISTS"


@dataclass(frozen=True)
class WallClockSoakConfig:
    duration_seconds: float = 86_400.0
    batch_interval_seconds: float = 60.0
    maximum_observation_gap_seconds: float = 180.0

    def __post_init__(self) -> None:
        numeric = (
            self.duration_seconds,
            self.batch_interval_seconds,
            self.maximum_observation_gap_seconds,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            for value in numeric
        ):
            raise H11AutoWallClockSoakError("wall-clock numeric input is invalid")
        if not 1.0 <= self.duration_seconds <= 86_400.0:
            raise H11AutoWallClockSoakError("duration must be between 1 and 86400")
        if not 0.1 <= self.batch_interval_seconds <= 3_600.0:
            raise H11AutoWallClockSoakError("batch interval is invalid")
        if self.maximum_observation_gap_seconds < self.batch_interval_seconds:
            raise H11AutoWallClockSoakError(
                "maximum observation gap must cover the batch interval"
            )


@dataclass(frozen=True)
class WallClockSoakReport:
    status: WallClockSoakStatus
    started_at_utc: str
    finished_at_utc: str
    target_duration_seconds: float
    observed_elapsed_seconds: float
    batch_count: int
    synthetic_cycle_count: int
    maximum_observed_gap_seconds: float
    checkpoint_path: str
    checkpoint_schema_version: str
    implementation_digest: str
    actual_post_count: int = 0
    broker_read_performed: bool = False
    broker_write_performed: bool = False
    network_access_performed: bool = False
    credential_read_performed: bool = False
    raw_id_value_exposure: bool = False
    resident_process: bool = False
    cron: bool = False
    actual_activation_ready: bool = False

    def __bool__(self) -> bool:
        return False

    def to_safe_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass(frozen=True)
class WallClockCheckpointStatus:
    status: str
    started_at_utc: str
    last_observed_at_utc: str
    heartbeat_age_seconds: float
    heartbeat_fresh: bool
    batch_count: int
    synthetic_cycle_count: int
    checkpoint_schema_version: str
    implementation_digest: str
    implementation_matches_current_code: bool
    actual_post_count: int = 0
    broker_write_performed: bool = False
    network_access_performed: bool = False
    credential_read_performed: bool = False
    raw_id_value_exposure: bool = False
    actual_activation_ready: bool = False

    def __bool__(self) -> bool:
        return False

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)


class WallClock(Protocol):
    def monotonic(self) -> float: ...

    def now_utc(self) -> datetime: ...

    def sleep(self, seconds: float) -> None: ...


class SystemWallClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def run_wall_clock_fake_soak_no_post(
    *,
    config: WallClockSoakConfig,
    checkpoint_path: Path,
    lock_path: Path,
    clock: WallClock | None = None,
) -> WallClockSoakReport:
    """Run repeated synthetic batches for a finite real-time window.

    Existing checkpoints are never resumed or overwritten.  A stopped process
    leaves a RUNNING checkpoint, forcing a fresh path and explicit review.
    """

    clock = clock or SystemWallClock()
    implementation_digest = current_h11_auto_implementation_digest()
    if checkpoint_path.resolve() == lock_path.resolve():
        raise H11AutoWallClockSoakError("checkpoint and lock paths must be separate")
    if checkpoint_path.exists() or checkpoint_path.is_symlink():
        now = clock.now_utc().isoformat()
        return WallClockSoakReport(
            status=WallClockSoakStatus.BLOCKED_CHECKPOINT_EXISTS,
            started_at_utc=now,
            finished_at_utc=now,
            target_duration_seconds=config.duration_seconds,
            observed_elapsed_seconds=0.0,
            batch_count=0,
            synthetic_cycle_count=0,
            maximum_observed_gap_seconds=0.0,
            checkpoint_path=str(checkpoint_path),
            checkpoint_schema_version=H11_AUTO_SOAK_CHECKPOINT_VERSION,
            implementation_digest=implementation_digest,
        )
    lock = H11AutoProcessLock(lock_path)
    if not lock.acquire():
        raise H11AutoWallClockSoakError("wall-clock soak lock is already held")
    started_at = clock.now_utc()
    start_tick = clock.monotonic()
    previous_tick = start_tick
    maximum_gap = 0.0
    batches = 0
    cycles = 0
    status = WallClockSoakStatus.PASSED_FAKE_ONLY
    _write_checkpoint(
        checkpoint_path,
        {
            "checkpoint_schema_version": H11_AUTO_SOAK_CHECKPOINT_VERSION,
            "implementation_digest": implementation_digest,
            "status": "RUNNING_FAKE_ONLY",
            "started_at_utc": started_at.isoformat(),
            "last_heartbeat_at_utc": started_at.isoformat(),
            "target_duration_seconds": config.duration_seconds,
            "batch_count": 0,
            "synthetic_cycle_count": 0,
            "actual_post_count": 0,
            "broker_write_performed": False,
            "network_access_performed": False,
            "credential_read_performed": False,
        },
    )
    try:
        while True:
            current_tick = clock.monotonic()
            elapsed = current_tick - start_tick
            if elapsed >= config.duration_seconds:
                break
            gap = current_tick - previous_tick
            maximum_gap = max(maximum_gap, gap)
            if gap > config.maximum_observation_gap_seconds:
                status = WallClockSoakStatus.FAILED_OBSERVATION_GAP
                break
            batch = run_phase_a_fault_soak_no_post(
                target_cycle_count=MINIMUM_PHASE_A_SOAK_CYCLES
            )
            batches += 1
            cycles += batch.synthetic_cycle_count
            if batch.status is not PhaseASoakStatus.PASSED_SYNTHETIC_NO_POST:
                status = WallClockSoakStatus.FAILED_SYNTHETIC_BATCH
                break
            _write_checkpoint(
                checkpoint_path,
                {
                    "checkpoint_schema_version": H11_AUTO_SOAK_CHECKPOINT_VERSION,
                    "implementation_digest": implementation_digest,
                    "status": "RUNNING_FAKE_ONLY",
                    "started_at_utc": started_at.isoformat(),
                    "last_heartbeat_at_utc": clock.now_utc().isoformat(),
                    "target_duration_seconds": config.duration_seconds,
                    "observed_elapsed_seconds": elapsed,
                    "batch_count": batches,
                    "synthetic_cycle_count": cycles,
                    "maximum_observed_gap_seconds": maximum_gap,
                    "actual_post_count": 0,
                    "broker_write_performed": False,
                    "network_access_performed": False,
                    "credential_read_performed": False,
                },
            )
            remaining = config.duration_seconds - elapsed
            previous_tick = current_tick
            clock.sleep(min(config.batch_interval_seconds, remaining))
    finally:
        lock.release()

    finished_at = clock.now_utc()
    elapsed = max(0.0, clock.monotonic() - start_tick)
    report = WallClockSoakReport(
        status=status,
        started_at_utc=started_at.isoformat(),
        finished_at_utc=finished_at.isoformat(),
        target_duration_seconds=config.duration_seconds,
        observed_elapsed_seconds=elapsed,
        batch_count=batches,
        synthetic_cycle_count=cycles,
        maximum_observed_gap_seconds=maximum_gap,
        checkpoint_path=str(checkpoint_path),
        checkpoint_schema_version=H11_AUTO_SOAK_CHECKPOINT_VERSION,
        implementation_digest=implementation_digest,
    )
    _write_checkpoint(checkpoint_path, report.to_safe_dict())
    return report


def expected_completion_at(*, started_at_utc: datetime, duration_seconds: float) -> str:
    if (
        not isinstance(started_at_utc, datetime)
        or started_at_utc.tzinfo is None
        or isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, int | float)
        or not math.isfinite(duration_seconds)
        or duration_seconds <= 0
    ):
        raise H11AutoWallClockSoakError("completion inputs are invalid")
    return (started_at_utc.astimezone(UTC) + timedelta(seconds=duration_seconds)).isoformat()


def inspect_wall_clock_checkpoint(
    path: Path,
    *,
    now_utc: datetime | None = None,
    maximum_heartbeat_age_seconds: float = 180.0,
) -> WallClockCheckpointStatus:
    """Read one safe checkpoint without checking process state or mutating it."""

    if (
        isinstance(maximum_heartbeat_age_seconds, bool)
        or not isinstance(maximum_heartbeat_age_seconds, int | float)
        or not math.isfinite(maximum_heartbeat_age_seconds)
        or maximum_heartbeat_age_seconds <= 0
    ):
        raise H11AutoWallClockSoakError("heartbeat age bound is invalid")
    if path.is_symlink() or not path.is_file():
        raise H11AutoWallClockSoakError(
            "checkpoint must be a regular non-symlink file"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise H11AutoWallClockSoakError("checkpoint cannot be read") from error
    if not isinstance(payload, dict):
        raise H11AutoWallClockSoakError("checkpoint payload is invalid")
    if payload.get("checkpoint_schema_version") != H11_AUTO_SOAK_CHECKPOINT_VERSION:
        raise H11AutoWallClockSoakError("checkpoint schema version is invalid")
    implementation_digest = payload.get("implementation_digest")
    if (
        not isinstance(implementation_digest, str)
        or len(implementation_digest) != 64
        or any(character not in "0123456789abcdef" for character in implementation_digest)
    ):
        raise H11AutoWallClockSoakError("checkpoint implementation digest is invalid")
    status = payload.get("status")
    if status not in {
        "RUNNING_FAKE_ONLY",
        WallClockSoakStatus.PASSED_FAKE_ONLY.value,
        WallClockSoakStatus.FAILED_OBSERVATION_GAP.value,
        WallClockSoakStatus.FAILED_SYNTHETIC_BATCH.value,
    }:
        raise H11AutoWallClockSoakError("checkpoint status is invalid")
    started = _checkpoint_timestamp(payload.get("started_at_utc"))
    last_observed = _checkpoint_timestamp(
        payload.get("last_heartbeat_at_utc") or payload.get("finished_at_utc")
    )
    now = now_utc or datetime.now(UTC)
    if now.tzinfo is None:
        raise H11AutoWallClockSoakError("inspection time must be timezone-aware")
    age = max(0.0, (now.astimezone(UTC) - last_observed.astimezone(UTC)).total_seconds())
    if payload.get("actual_post_count", 0) != 0 or any(
        payload.get(field, False) is not False
        for field in (
            "broker_write_performed",
            "network_access_performed",
            "credential_read_performed",
            "raw_id_value_exposure",
            "actual_activation_ready",
        )
    ):
        raise H11AutoWallClockSoakError("checkpoint violates no-POST invariants")
    batch_count = payload.get("batch_count")
    cycle_count = payload.get("synthetic_cycle_count")
    if (
        isinstance(batch_count, bool)
        or not isinstance(batch_count, int)
        or batch_count < 0
        or isinstance(cycle_count, bool)
        or not isinstance(cycle_count, int)
        or cycle_count < 0
    ):
        raise H11AutoWallClockSoakError("checkpoint counts are invalid")
    return WallClockCheckpointStatus(
        status=str(status),
        started_at_utc=started.isoformat(),
        last_observed_at_utc=last_observed.isoformat(),
        heartbeat_age_seconds=age,
        heartbeat_fresh=(
            status != "RUNNING_FAKE_ONLY" or age <= maximum_heartbeat_age_seconds
        ),
        batch_count=batch_count,
        synthetic_cycle_count=cycle_count,
        checkpoint_schema_version=H11_AUTO_SOAK_CHECKPOINT_VERSION,
        implementation_digest=implementation_digest,
        implementation_matches_current_code=(
            implementation_digest == current_h11_auto_implementation_digest()
        ),
    )


def _write_checkpoint(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    if path.is_symlink() or temporary.is_symlink():
        raise H11AutoWallClockSoakError("checkpoint path must not be a symlink")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError as error:
        raise H11AutoWallClockSoakError("checkpoint cannot be written") from error


def _checkpoint_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise H11AutoWallClockSoakError("checkpoint timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise H11AutoWallClockSoakError("checkpoint timestamp is invalid") from error
    if parsed.tzinfo is None:
        raise H11AutoWallClockSoakError("checkpoint timestamp must be timezone-aware")
    return parsed


def current_h11_auto_implementation_digest() -> str:
    """Hash the broker-independent auto source loaded by the soak contract."""

    source_root = Path(__file__).resolve().parent
    sources = sorted(source_root.glob("*.py"), key=lambda path: path.name)
    if not sources:
        raise H11AutoWallClockSoakError("implementation sources are missing")
    hasher = hashlib.sha256()
    try:
        for source in sources:
            if source.is_symlink() or not source.is_file():
                raise H11AutoWallClockSoakError("implementation source is invalid")
            hasher.update(source.name.encode())
            hasher.update(b"\0")
            hasher.update(source.read_bytes())
            hasher.update(b"\0")
    except OSError as error:
        raise H11AutoWallClockSoakError("implementation sources cannot be read") from error
    return hasher.hexdigest()
