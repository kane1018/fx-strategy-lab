"""G028 local-only unattended runtime integration.

This generation proves lifecycle and persistence contracts only. It contains
no credential loader, HTTP client, Private API adapter, notification sender,
permit, or broker transport. A later generation must separately review any
external snapshot adapter.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import DeadManPolicy, DeadManStore

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_RECEIPT_SCHEMA = "H11_V4_G028_EXTERNAL_APPROVAL_RECEIPT_V1"
_STARTED = "g028-private-snapshot.started.json"
_PASSED = "g028-private-snapshot.fake-passed.json"
_HEARTBEAT = "g028-supervisor-heartbeat.json"
_SHUTDOWN = "g028-supervisor-shutdown.json"
_ENTRY_HALT = "g028-entry-halt.json"
_UNKNOWN_HALT = "g028-unknown-halt.json"
_LIFECYCLE = "g028-protected-cycle.fake.json"
_HOLD_SECONDS = 1_800


class V4G028RuntimeNoPostError(RuntimeError):
    """Fixed safe G028 failure."""


@dataclass(frozen=True)
class V4G028FakeSnapshotNoPost:
    latest_executions_count: int
    open_positions_count: int
    active_orders_count: int
    source: str = "SYNTHETIC_FAKE_NO_POST"

    def __post_init__(self) -> None:
        if self.source != "SYNTHETIC_FAKE_NO_POST" or any(
            type(value) is not int or value < 0
            for value in (
                self.latest_executions_count,
                self.open_positions_count,
                self.active_orders_count,
            )
        ):
            raise V4G028RuntimeNoPostError("G028_FAKE_SNAPSHOT_INVALID")


@dataclass(frozen=True)
class V4G028SnapshotTransactionResultNoPost:
    status: str
    account_flat: bool
    active_orders_zero: bool
    approval_receipt_consumed: bool = True
    started_marker_written: bool = True
    modeled_private_get_count: int = 3
    private_api_read: bool = False
    credential_read: bool = False
    broker_get_count: int = 0
    broker_write: bool = False
    broker_post_count: int = 0
    notification_send_count: int = 0

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4G028ArmProjectionNoPost:
    reviewed_files_digest: str
    generation_digest: str
    desired_state: str

    def __post_init__(self) -> None:
        _require_digest(self.reviewed_files_digest)
        _require_digest(self.generation_digest)
        if self.desired_state not in {"ARMED", "DISARMED", "BLOCKED"}:
            raise V4G028RuntimeNoPostError("G028_ARM_PROJECTION_INVALID")

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4G028ProtectedCycleNoPost:
    reviewed_files_digest: str
    generation_digest: str
    cycle_binding_digest: str
    entry_filled_at_utc: str
    exact_protection_confirmed: bool
    source: str = "SYNTHETIC_FAKE_NO_POST"

    def __post_init__(self) -> None:
        for value in (
            self.reviewed_files_digest,
            self.generation_digest,
            self.cycle_binding_digest,
        ):
            _require_digest(value)
        _utc(datetime.fromisoformat(self.entry_filled_at_utc))
        if (
            self.exact_protection_confirmed is not True
            or self.source != "SYNTHETIC_FAKE_NO_POST"
        ):
            raise V4G028RuntimeNoPostError("G028_PROTECTED_CYCLE_INVALID")


@dataclass(frozen=True)
class V4G028SupervisorResultNoPost:
    status: str
    entry_halted: bool
    settlement_monitor_required: bool
    persistent_halt: bool
    process_lock_held: bool
    dead_man_updated: bool
    heartbeat_updated: bool
    broker_write: bool = False
    broker_post_count: int = 0
    private_api_read: bool = False
    credential_read: bool = False
    notification_send_count: int = 0

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4G028SettlementDispatchResultNoPost:
    status: str
    due: bool
    marker_written: bool
    broker_write: bool = False
    broker_post_count: int = 0
    private_api_read: bool = False
    credential_read: bool = False
    notification_send_count: int = 0

    def __bool__(self) -> bool:
        return False


def consume_external_approval_for_fake_snapshot_no_post(
    *,
    anchor_directory_fd: int,
    approval_receipt_fd: int,
    reviewed_files_digest: str,
    generation_digest: str,
    snapshot: V4G028FakeSnapshotNoPost,
    observed_at_utc: datetime,
) -> V4G028SnapshotTransactionResultNoPost:
    """Atomically consume a pre-validated receipt on a caller-held anchor inode."""

    _require_digest(reviewed_files_digest)
    _require_digest(generation_digest)
    observed = _utc(observed_at_utc)
    anchor_stat = os.fstat(anchor_directory_fd)
    if not stat.S_ISDIR(anchor_stat.st_mode):
        raise V4G028RuntimeNoPostError("G028_ANCHOR_FD_INVALID")
    receipt_stat = os.fstat(approval_receipt_fd)
    if (
        not stat.S_ISREG(receipt_stat.st_mode)
        or receipt_stat.st_uid != os.getuid()
        or receipt_stat.st_mode & 0o777 != 0o600
    ):
        raise V4G028RuntimeNoPostError("G028_APPROVAL_RECEIPT_FD_INVALID")
    receipt = _read_json_fd(approval_receipt_fd)
    _validate_receipt(
        receipt,
        reviewed_files_digest=reviewed_files_digest,
        generation_digest=generation_digest,
        observed_at_utc=observed,
        anchor_device=anchor_stat.st_dev,
        anchor_inode=anchor_stat.st_ino,
    )
    started = {
        "schema": "H11_V4_G028_FAKE_SNAPSHOT_STARTED_V1",
        "status": "G028_EXTERNAL_APPROVAL_RECEIPT_CONSUMED_FAKE_SNAPSHOT_STARTED",
        "reviewed_files_digest": reviewed_files_digest,
        "generation_digest": generation_digest,
        "approval_receipt_digest": receipt["artifact_digest"],
        "anchor_device": anchor_stat.st_dev,
        "anchor_inode": anchor_stat.st_ino,
        "observed_at_utc": observed.isoformat(),
        "private_api_read": False,
        "broker_post_count": 0,
    }
    started["artifact_digest"] = _digest(started)
    _write_once_at(anchor_directory_fd, _STARTED, started)
    passed = {
        "schema": "H11_V4_G028_FAKE_SNAPSHOT_PASSED_V1",
        "status": "G028_FAKE_SNAPSHOT_RECORDED_NO_EXTERNAL_ACTION",
        "reviewed_files_digest": reviewed_files_digest,
        "generation_digest": generation_digest,
        "started_marker_digest": started["artifact_digest"],
        "account_flat": snapshot.open_positions_count == 0,
        "active_orders_zero": snapshot.active_orders_count == 0,
        "modeled_private_get_count": 3,
        "private_api_read": False,
        "credential_read": False,
        "broker_get_count": 0,
        "broker_write": False,
        "broker_post_count": 0,
    }
    passed["artifact_digest"] = _digest(passed)
    _write_once_at(anchor_directory_fd, _PASSED, passed)
    return V4G028SnapshotTransactionResultNoPost(
        status=str(passed["status"]),
        account_flat=bool(passed["account_flat"]),
        active_orders_zero=bool(passed["active_orders_zero"]),
    )


def record_fake_protected_cycle_once_no_post(
    *, state_directory: Path, cycle: V4G028ProtectedCycleNoPost
) -> None:
    payload = {
        "schema": "H11_V4_G028_PROTECTED_CYCLE_FAKE_V1",
        **cycle.__dict__,
    }
    payload["artifact_digest"] = _digest(payload)
    state_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory_fd = _open_directory(state_directory)
    try:
        _write_once_at(directory_fd, _LIFECYCLE, payload)
    finally:
        os.close(directory_fd)


class V4G028ResidentSupervisorNoPost:
    """Foreground-resident supervisor with local-only durable state."""

    def __init__(
        self,
        *,
        state_directory: Path,
        reviewed_files_digest: str,
        generation_digest: str,
        maximum_heartbeat_age_seconds: int = 60,
    ) -> None:
        _require_digest(reviewed_files_digest)
        _require_digest(generation_digest)
        self.root = state_directory
        self.reviewed = reviewed_files_digest
        self.generation = generation_digest
        self.process_lock = H11AutoProcessLock(state_directory / "g028-supervisor.lock")
        self.dead_man = DeadManStore(
            state_directory / "g028-dead-man.json",
            policy=DeadManPolicy(
                policy_label="H11_V4_G028_DEAD_MAN_NO_POST",
                maximum_heartbeat_age_seconds=maximum_heartbeat_age_seconds,
            ),
        )
        self.heartbeat_path = state_directory / _HEARTBEAT
        self._persistent_halt = False
        self._settlement_required = False

    def start(
        self, *, now_utc: datetime, arm: V4G028ArmProjectionNoPost
    ) -> V4G028SupervisorResultNoPost:
        now = _utc(now_utc)
        self._require_arm_binding(arm)
        if not self.process_lock.acquire():
            return self._result(
                "G028_SUPERVISOR_PROCESS_LOCK_HELD_FAIL_CLOSED",
                lock_held=False,
                persistent_halt=True,
            )
        try:
            self._persistent_halt = self._unknown_halt_exists()
            cycle = self._load_cycle(now)
            self._settlement_required = cycle is not None
            dead_man_exists = self.dead_man.path.is_file()
            heartbeat_exists = self.heartbeat_path.is_file()
            entry_halt_exists = (self.root / _ENTRY_HALT).is_file()
            if dead_man_exists != heartbeat_exists:
                self._latch_unknown(now, "G028_PARTIAL_HEARTBEAT_STATE")
                self._persistent_halt = True
            if (dead_man_exists or heartbeat_exists) and not entry_halt_exists:
                self._latch_unknown(now, "G028_ENTRY_HALT_MISSING")
                self._persistent_halt = True
            if entry_halt_exists and not validate_g028_entry_halt_no_post(
                path=self.root / _ENTRY_HALT,
                expected_reviewed_files_digest=self.reviewed,
                expected_generation_digest=self.generation,
            ):
                self._latch_unknown(now, "G028_ENTRY_HALT_INVALID")
                self._persistent_halt = True
            if (
                heartbeat_exists
                and cycle is None
                and not self._clean_shutdown_after_heartbeat()
            ):
                self._latch_unknown(now, "G028_UNCLEAN_RESTART_WITHOUT_CYCLE")
                self._persistent_halt = True
            previous = self.dead_man.evaluate(now_utc=now)
            if previous.halt_required and cycle is None and heartbeat_exists:
                self._persistent_halt = True
                self._latch_unknown(now, "G028_STARTUP_STALE_WITHOUT_CYCLE")
            status = self._status(arm)
            self._beat(now)
            self._write_entry_halt(status, now)
            return self._result(
                status,
                lock_held=True,
                persistent_halt=self._persistent_halt,
            )
        except Exception:
            try:
                self._latch_unknown(now, "G028_SUPERVISOR_START_EXCEPTION")
            except Exception:
                pass
            self.process_lock.release()
            raise

    def tick(
        self, *, now_utc: datetime, arm: V4G028ArmProjectionNoPost
    ) -> V4G028SupervisorResultNoPost:
        if not self.process_lock.held:
            raise V4G028RuntimeNoPostError("G028_SUPERVISOR_NOT_RUNNING")
        now = _utc(now_utc)
        try:
            self._require_arm_binding(arm)
            cycle = self._load_cycle(now)
            self._settlement_required = cycle is not None
            previous = self.dead_man.evaluate(now_utc=now)
            if previous.halt_required:
                if cycle is None:
                    self._latch_unknown(now, "G028_SLEEP_GAP_WITHOUT_CYCLE")
                    self._persistent_halt = True
                else:
                    self._settlement_required = True
            self._beat(now)
            status = self._status(arm)
            if self._settlement_required and not self._persistent_halt:
                dispatch = dispatch_30m_exit_fake_no_post(
                    state_directory=self.root,
                    reviewed_files_digest=self.reviewed,
                    generation_digest=self.generation,
                    observed_at_utc=now,
                )
                if dispatch.due:
                    status = dispatch.status
            self._write_entry_halt(status, now)
            return self._result(
                status,
                lock_held=True,
                persistent_halt=self._persistent_halt,
            )
        except Exception:
            try:
                self._latch_unknown(now, "G028_SUPERVISOR_TICK_EXCEPTION")
            except Exception:
                pass
            self.process_lock.release()
            raise

    def stop(
        self, *, now_utc: datetime, reason: str
    ) -> V4G028SupervisorResultNoPost:
        if reason not in {"CTRL_C", "PROCESS_EXIT", "HOST_SHUTDOWN", "ARM_OFF"}:
            raise V4G028RuntimeNoPostError("G028_STOP_REASON_INVALID")
        if not self.process_lock.held:
            raise V4G028RuntimeNoPostError("G028_STOP_PROCESS_LOCK_REQUIRED")
        now = _utc(now_utc)
        status = "G028_SUPERVISOR_STOPPED_ENTRY_DISABLED_NO_POST"
        try:
            heartbeat = self._validated_heartbeat()
            shutdown = self._payload(
                status=status,
                observed_at_utc=now,
                reason=reason,
                heartbeat_artifact_digest=heartbeat["artifact_digest"],
                heartbeat_sequence=heartbeat["sequence"],
            )
            shutdown["artifact_digest"] = _digest(shutdown)
            _write_replace(self.root / _SHUTDOWN, shutdown)
            self._write_entry_halt(status, now)
        except Exception:
            try:
                self._latch_unknown(now, "G028_SUPERVISOR_STOP_PERSISTENCE_FAILED")
                self._persistent_halt = True
            finally:
                self.process_lock.release()
            raise
        finally:
            if self.process_lock.held:
                self.process_lock.release()
        return self._result(
            status,
            lock_held=False,
            persistent_halt=self._persistent_halt,
        )

    def fail_closed(self, *, now_utc: datetime, reason: str) -> None:
        now = _utc(now_utc)
        try:
            self._latch_unknown(now, reason)
            self._persistent_halt = True
            self._write_entry_halt(
                "G028_SUPERVISOR_UNKNOWN_STATE_PERSISTENT_HALT", now
            )
        finally:
            self.process_lock.release()

    def _status(self, arm: V4G028ArmProjectionNoPost) -> str:
        if self._persistent_halt:
            return "G028_SUPERVISOR_UNKNOWN_STATE_PERSISTENT_HALT"
        if self._settlement_required:
            return "G028_SUPERVISOR_EXIT_RECOVERY_REQUIRED_NO_POST"
        if arm.desired_state == "DISARMED":
            return "G028_SUPERVISOR_ARM_OFF_ENTRY_DISABLED_NO_POST"
        if arm.desired_state == "BLOCKED":
            return "G028_SUPERVISOR_ARM_INVALID_ENTRY_DISABLED_NO_POST"
        return "G028_SUPERVISOR_RUNNING_ENTRY_DISABLED_NO_POST"

    def _require_arm_binding(self, arm: V4G028ArmProjectionNoPost) -> None:
        if (
            arm.reviewed_files_digest != self.reviewed
            or arm.generation_digest != self.generation
        ):
            raise V4G028RuntimeNoPostError("G028_ARM_GENERATION_BINDING_INVALID")

    def _load_cycle(self, now: datetime) -> dict[str, Any] | None:
        path = self.root / _LIFECYCLE
        if not path.exists():
            return None
        if path.is_symlink() or path.stat().st_mode & 0o777 not in {0o600, 0o644}:
            self._latch_unknown(now, "G028_PROTECTED_CYCLE_INVALID")
            self._persistent_halt = True
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._latch_unknown(now, "G028_PROTECTED_CYCLE_INVALID")
            self._persistent_halt = True
            return None
        if (
            payload.get("schema") != "H11_V4_G028_PROTECTED_CYCLE_FAKE_V1"
            or payload.get("source") != "SYNTHETIC_FAKE_NO_POST"
            or payload.get("reviewed_files_digest") != self.reviewed
            or payload.get("generation_digest") != self.generation
            or payload.get("exact_protection_confirmed") is not True
            or payload.get("artifact_digest") != _digest(payload)
        ):
            self._latch_unknown(now, "G028_PROTECTED_CYCLE_INVALID")
            self._persistent_halt = True
            return None
        return payload

    def _beat(self, now: datetime) -> None:
        self.dead_man.heartbeat(heartbeat_utc=now)
        sequence, previous_digest = 1, None
        if self.heartbeat_path.exists():
            previous = self._validated_heartbeat()
            sequence = int(previous["sequence"]) + 1
            previous_digest = previous["artifact_digest"]
        payload = self._payload(
            status="G028_SUPERVISOR_HEARTBEAT_NO_POST",
            observed_at_utc=now,
            sequence=sequence,
            previous_artifact_digest=previous_digest,
        )
        payload["artifact_digest"] = _digest(payload)
        _write_replace(self.heartbeat_path, payload)

    def _latch_unknown(self, now: datetime, reason: str) -> None:
        payload = self._payload(
            status="G028_SUPERVISOR_UNKNOWN_STATE_PERSISTENT_HALT",
            observed_at_utc=now,
            reason=reason,
        )
        payload["artifact_digest"] = _digest(payload)
        if not (self.root / _UNKNOWN_HALT).exists():
            directory_fd = _open_directory(self.root)
            try:
                _write_once_at(directory_fd, _UNKNOWN_HALT, payload)
            finally:
                os.close(directory_fd)

    def _unknown_halt_exists(self) -> bool:
        return (self.root / _UNKNOWN_HALT).is_file()

    def _clean_shutdown_after_heartbeat(self) -> bool:
        shutdown_path = self.root / _SHUTDOWN
        if not shutdown_path.is_file() or shutdown_path.is_symlink():
            return False
        try:
            shutdown = json.loads(shutdown_path.read_text(encoding="utf-8"))
            heartbeat = self._validated_heartbeat()
            shutdown_at = _utc(datetime.fromisoformat(shutdown["observed_at_utc"]))
            heartbeat_at = _utc(datetime.fromisoformat(heartbeat["observed_at_utc"]))
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            V4G028RuntimeNoPostError,
        ):
            return False
        return (
            shutdown.get("schema") == "H11_V4_G028_LOCAL_SUPERVISOR_STATE_V1"
            and shutdown.get("status")
            == "G028_SUPERVISOR_STOPPED_ENTRY_DISABLED_NO_POST"
            and shutdown.get("reason")
            in {"CTRL_C", "PROCESS_EXIT", "HOST_SHUTDOWN", "ARM_OFF"}
            and shutdown.get("reviewed_files_digest") == self.reviewed
            and shutdown.get("generation_digest") == self.generation
            and shutdown.get("artifact_digest") == _digest(shutdown)
            and shutdown.get("heartbeat_artifact_digest")
            == heartbeat["artifact_digest"]
            and shutdown.get("heartbeat_sequence") == heartbeat["sequence"]
            and shutdown_at >= heartbeat_at
        )

    def _validated_heartbeat(self) -> dict[str, Any]:
        if not self.heartbeat_path.is_file() or self.heartbeat_path.is_symlink():
            raise V4G028RuntimeNoPostError("G028_HEARTBEAT_CHAIN_INVALID")
        try:
            payload = json.loads(self.heartbeat_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise V4G028RuntimeNoPostError(
                "G028_HEARTBEAT_CHAIN_INVALID"
            ) from None
        previous_digest = payload.get("previous_artifact_digest")
        if (
            payload.get("schema") != "H11_V4_G028_LOCAL_SUPERVISOR_STATE_V1"
            or payload.get("status") != "G028_SUPERVISOR_HEARTBEAT_NO_POST"
            or payload.get("reviewed_files_digest") != self.reviewed
            or payload.get("generation_digest") != self.generation
            or not isinstance(payload.get("sequence"), int)
            or payload["sequence"] < 1
            or (
                previous_digest is not None
                and (
                    not isinstance(previous_digest, str)
                    or not previous_digest.startswith("sha256:")
                    or len(previous_digest) != 71
                )
            )
            or payload.get("artifact_digest") != _digest(payload)
        ):
            raise V4G028RuntimeNoPostError("G028_HEARTBEAT_CHAIN_INVALID")
        return payload

    def _write_entry_halt(self, status: str, now: datetime) -> None:
        payload = self._payload(
            status="G028_ENTRY_HALT_ACTIVE_NO_POST",
            observed_at_utc=now,
        )
        payload["schema"] = "H11_V4_G028_ENTRY_HALT_V1"
        payload["artifact_digest"] = _digest(payload)
        _write_replace(self.root / _ENTRY_HALT, payload)

    def _payload(self, *, status: str, observed_at_utc: datetime, **extra: Any):
        return {
            "schema": "H11_V4_G028_LOCAL_SUPERVISOR_STATE_V1",
            "status": status,
            "reviewed_files_digest": self.reviewed,
            "generation_digest": self.generation,
            "observed_at_utc": observed_at_utc.isoformat(),
            "entry_halted": True,
            "broker_write": False,
            "broker_post_count": 0,
            **extra,
        }

    def _result(
        self, status: str, *, lock_held: bool, persistent_halt: bool
    ) -> V4G028SupervisorResultNoPost:
        return V4G028SupervisorResultNoPost(
            status=status,
            entry_halted=True,
            settlement_monitor_required=self._settlement_required,
            persistent_halt=persistent_halt,
            process_lock_held=lock_held,
            dead_man_updated=lock_held,
            heartbeat_updated=lock_held,
        )


def dispatch_30m_exit_fake_no_post(
    *,
    state_directory: Path,
    reviewed_files_digest: str,
    generation_digest: str,
    observed_at_utc: datetime,
) -> V4G028SettlementDispatchResultNoPost:
    """Read a synthetic protected lifecycle and persist a cycle-bound due marker."""

    _require_digest(reviewed_files_digest)
    _require_digest(generation_digest)
    observed = _utc(observed_at_utc)
    lifecycle_path = state_directory / _LIFECYCLE
    if lifecycle_path.is_symlink() or not lifecycle_path.is_file():
        raise V4G028RuntimeNoPostError("G028_EXIT_LIFECYCLE_MISSING")
    try:
        lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
        entry = _utc(datetime.fromisoformat(lifecycle["entry_filled_at_utc"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise V4G028RuntimeNoPostError("G028_EXIT_LIFECYCLE_INVALID") from None
    cycle = lifecycle.get("cycle_binding_digest")
    _require_digest(cycle)
    if (
        lifecycle.get("schema") != "H11_V4_G028_PROTECTED_CYCLE_FAKE_V1"
        or lifecycle.get("source") != "SYNTHETIC_FAKE_NO_POST"
        or lifecycle.get("reviewed_files_digest") != reviewed_files_digest
        or lifecycle.get("generation_digest") != generation_digest
        or lifecycle.get("exact_protection_confirmed") is not True
        or lifecycle.get("artifact_digest") != _digest(lifecycle)
    ):
        raise V4G028RuntimeNoPostError("G028_EXIT_LIFECYCLE_INVALID")
    if observed < entry + timedelta(seconds=_HOLD_SECONDS):
        return V4G028SettlementDispatchResultNoPost(
            status="G028_EXIT_NOT_DUE_MONITORING_NO_POST",
            due=False,
            marker_written=False,
        )
    filename = f"g028-settlement-dispatch.{cycle.removeprefix('sha256:')}.json"
    marker = state_directory / filename
    if marker.is_file() and not marker.is_symlink():
        existing = json.loads(marker.read_text(encoding="utf-8"))
        expected_scheduled = (
            entry + timedelta(seconds=_HOLD_SECONDS)
        ).isoformat()
        if (
            existing.get("schema")
            == "H11_V4_G028_30M_EXIT_DISPATCH_FAKE_NO_POST_V1"
            and existing.get("status")
            == "G028_30M_EXIT_DUE_REVIEW_REQUIRED_NO_POST"
            and existing.get("reviewed_files_digest") == reviewed_files_digest
            and existing.get("generation_digest") == generation_digest
            and existing.get("cycle_binding_digest") == cycle
            and existing.get("scheduled_exit_at_utc") == expected_scheduled
            and existing.get("broker_write") is False
            and existing.get("broker_post_count") == 0
            and existing.get("artifact_digest") == _digest(existing)
        ):
            return V4G028SettlementDispatchResultNoPost(
                status="G028_30M_EXIT_ALREADY_DISPATCHED_NO_POST",
                due=True,
                marker_written=False,
            )
        raise V4G028RuntimeNoPostError("G028_EXIT_MARKER_INVALID")
    payload = {
        "schema": "H11_V4_G028_30M_EXIT_DISPATCH_FAKE_NO_POST_V1",
        "status": "G028_30M_EXIT_DUE_REVIEW_REQUIRED_NO_POST",
        "reviewed_files_digest": reviewed_files_digest,
        "generation_digest": generation_digest,
        "cycle_binding_digest": cycle,
        "scheduled_exit_at_utc": (
            entry + timedelta(seconds=_HOLD_SECONDS)
        ).isoformat(),
        "observed_at_utc": observed.isoformat(),
        "broker_write": False,
        "broker_post_count": 0,
    }
    payload["artifact_digest"] = _digest(payload)
    directory_fd = _open_directory(state_directory)
    try:
        _write_once_at(directory_fd, filename, payload)
    finally:
        os.close(directory_fd)
    return V4G028SettlementDispatchResultNoPost(
        status=str(payload["status"]), due=True, marker_written=True
    )


def _validate_receipt(
    payload: dict[str, Any],
    *,
    reviewed_files_digest: str,
    generation_digest: str,
    observed_at_utc: datetime,
    anchor_device: int,
    anchor_inode: int,
) -> None:
    try:
        valid_until = _utc(datetime.fromisoformat(payload["valid_until_utc"]))
    except (KeyError, TypeError, ValueError):
        raise V4G028RuntimeNoPostError("G028_APPROVAL_RECEIPT_INVALID") from None
    if (
        payload.get("schema") != _RECEIPT_SCHEMA
        or payload.get("reviewed_files_digest") != reviewed_files_digest
        or payload.get("generation_digest") != generation_digest
        or payload.get("scope") != "FAKE_SNAPSHOT_TRANSACTION_ONLY"
        or payload.get("anchor_device") != anchor_device
        or payload.get("anchor_inode") != anchor_inode
        or payload.get("private_api_authorized") is not False
        or payload.get("broker_post_authorized") is not False
        or payload.get("artifact_digest") != _digest(payload)
        or observed_at_utc > valid_until
    ):
        raise V4G028RuntimeNoPostError("G028_APPROVAL_RECEIPT_INVALID")


def _read_json_fd(descriptor: int) -> dict[str, Any]:
    try:
        with os.fdopen(os.dup(descriptor), "r", encoding="utf-8") as handle:
            handle.seek(0)
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        raise V4G028RuntimeNoPostError("G028_APPROVAL_RECEIPT_INVALID") from None
    if not isinstance(payload, dict):
        raise V4G028RuntimeNoPostError("G028_APPROVAL_RECEIPT_INVALID")
    return payload


def _open_directory(path: Path) -> int:
    if path.is_symlink() or not path.is_dir():
        raise V4G028RuntimeNoPostError("G028_STATE_DIRECTORY_INVALID")
    return os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )


def _write_once_at(directory_fd: int, filename: str, payload: dict[str, Any]) -> None:
    try:
        descriptor = os.open(
            filename,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_fd,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.fsync(directory_fd)
    except FileExistsError:
        raise V4G028RuntimeNoPostError("G028_OPERATION_ALREADY_ATTEMPTED") from None
    except OSError:
        raise V4G028RuntimeNoPostError("G028_STATE_WRITE_FAILED") from None


def _write_replace(path: Path, payload: dict[str, Any]) -> None:
    if path.is_symlink():
        raise V4G028RuntimeNoPostError("G028_STATE_PATH_INVALID")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        directory_fd = _open_directory(path.parent)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        raise V4G028RuntimeNoPostError("G028_STATE_WRITE_FAILED") from None


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise V4G028RuntimeNoPostError("G028_TIME_INVALID")
    return value.astimezone(UTC)


def _require_digest(value: object) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise V4G028RuntimeNoPostError("G028_DIGEST_INVALID")


def _digest(payload: dict[str, Any]) -> str:
    canonical = {key: value for key, value in payload.items() if key != "artifact_digest"}
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def validate_g028_entry_halt_no_post(
    *,
    path: Path,
    expected_reviewed_files_digest: str,
    expected_generation_digest: str,
) -> bool:
    """Validate the generation-bound local entry-HALT artifact."""

    if not path.is_file() or path.is_symlink():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        payload.get("schema") == "H11_V4_G028_ENTRY_HALT_V1"
        and payload.get("status") == "G028_ENTRY_HALT_ACTIVE_NO_POST"
        and payload.get("reviewed_files_digest")
        == expected_reviewed_files_digest
        and payload.get("generation_digest") == expected_generation_digest
        and payload.get("entry_halted") is True
        and payload.get("broker_write") is False
        and payload.get("broker_post_count") == 0
        and payload.get("artifact_digest") == _digest(payload)
    )
