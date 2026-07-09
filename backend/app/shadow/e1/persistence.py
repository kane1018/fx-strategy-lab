"""Durable local persistence for E1 intent/audit and virtual venue state."""

from __future__ import annotations

import fcntl
import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any

from app.shadow.e1.contracts import (
    E1_SCHEMA_VERSION,
    ExecutionOutcome,
    FaultKind,
    GateAction,
    HypothesisLabel,
    PnlCategory,
    PositionSide,
    VirtualPosition,
    canonical_decimal,
    canonical_timestamp,
    finite_decimal,
    parse_timestamp,
    position_digest,
    shadow_safety_flags,
)


class E1PersistenceError(RuntimeError):
    """Persistence failed; callers must halt without virtual execution."""


_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")


class JournalEventType(str, Enum):
    RUN_STARTED = "RUN_STARTED"
    HEARTBEAT_RECORDED = "HEARTBEAT_RECORDED"
    NO_ACTION_RECORDED = "NO_ACTION_RECORDED"
    INTENT_PREPARED = "INTENT_PREPARED"
    VIRTUAL_EXECUTION_STARTED = "VIRTUAL_EXECUTION_STARTED"
    VIRTUAL_EXECUTION_CONFIRMED = "VIRTUAL_EXECUTION_CONFIRMED"
    VIRTUAL_EXECUTION_REJECTED = "VIRTUAL_EXECUTION_REJECTED"
    VIRTUAL_EXECUTION_UNCERTAIN = "VIRTUAL_EXECUTION_UNCERTAIN"
    RECONCILE_MATCHED = "RECONCILE_MATCHED"
    RECONCILE_MISMATCH = "RECONCILE_MISMATCH"
    RESTART_ACK_RECORDED = "RESTART_ACK_RECORDED"
    KILL_ACTIVATED = "KILL_ACTIVATED"
    DEADMAN_ACTIVATED = "DEADMAN_ACTIVATED"
    FAKE_CRITICAL_ALERT = "FAKE_CRITICAL_ALERT"
    HALTED = "HALTED"
    FAULT_HANDLED = "FAULT_HANDLED"
    INCIDENT_RECORDED = "INCIDENT_RECORDED"
    POSTMORTEM_RECORDED = "POSTMORTEM_RECORDED"


_RESOLVING_EVENTS = frozenset(
    {
        JournalEventType.VIRTUAL_EXECUTION_CONFIRMED,
        JournalEventType.VIRTUAL_EXECUTION_REJECTED,
        JournalEventType.RECONCILE_MATCHED,
        JournalEventType.RECONCILE_MISMATCH,
    }
)


@dataclass(frozen=True)
class JournalRecord:
    schema_version: str
    sequence: int
    event_type: JournalEventType
    timestamp: str
    recorded_at: str
    run_id: str
    config_hash: str
    status_label: str
    reason_codes: tuple[str, ...]
    expected_state_digest: str
    position_count: int
    action: GateAction | None = None
    intent_id: str | None = None
    intent_digest: str | None = None
    token_id: str | None = None
    decision_digest: str | None = None
    hypothesis_label: HypothesisLabel | None = None
    hypothesis_id: str | None = None
    hypothesis_version: str | None = None
    execution_outcome: ExecutionOutcome | None = None
    fault_kind: FaultKind = FaultKind.NONE
    state_before_digest: str | None = None
    planned_state_digest: str | None = None
    observed_state_digest: str | None = None
    pnl_category: PnlCategory = PnlCategory.NOT_APPLICABLE
    virtual_loss: str = "0"
    incident_ref: str | None = None
    incident_severity: str | None = None
    safety: dict[str, bool | int] | None = None

    def __post_init__(self) -> None:
        if self.schema_version != E1_SCHEMA_VERSION:
            raise E1PersistenceError("journal schema mismatch")
        if type(self.sequence) is not int or self.sequence < 0:
            raise E1PersistenceError("journal sequence must be non-negative")
        if not isinstance(self.event_type, JournalEventType):
            raise E1PersistenceError("journal event type is invalid")
        canonical_timestamp(self.timestamp)
        canonical_timestamp(self.recorded_at)
        if not _SAFE_LABEL.fullmatch(self.run_id) or len(self.config_hash) != 64:
            raise E1PersistenceError("journal run/config identity is invalid")
        if not _SAFE_LABEL.fullmatch(self.status_label) or any(
            not isinstance(item, str) or not _SAFE_LABEL.fullmatch(item)
            for item in self.reason_codes
        ):
            raise E1PersistenceError("journal safe labels must be non-empty")
        digests = (
            self.expected_state_digest,
            self.intent_digest,
            self.decision_digest,
            self.state_before_digest,
            self.planned_state_digest,
            self.observed_state_digest,
        )
        if any(value is not None and len(value) != 64 for value in digests):
            raise E1PersistenceError("journal state digest is invalid")
        if self.position_count not in {0, 1}:
            raise E1PersistenceError("journal position_count must be zero or one")
        if self.action is not None and not isinstance(self.action, GateAction):
            raise E1PersistenceError("journal action is invalid")
        if self.hypothesis_label is not None and not isinstance(
            self.hypothesis_label, HypothesisLabel
        ):
            raise E1PersistenceError("journal hypothesis label is invalid")
        if self.execution_outcome is not None and not isinstance(
            self.execution_outcome, ExecutionOutcome
        ):
            raise E1PersistenceError("journal execution outcome is invalid")
        if not isinstance(self.fault_kind, FaultKind):
            raise E1PersistenceError("journal fault kind is invalid")
        if not isinstance(self.pnl_category, PnlCategory):
            raise E1PersistenceError("journal pnl category is invalid")
        loss = finite_decimal(self.virtual_loss, field_name="virtual_loss")
        if loss < 0 or (self.pnl_category is not PnlCategory.LOSS and loss != 0):
            raise E1PersistenceError("journal virtual loss contract is invalid")
        if self.safety != shadow_safety_flags():
            raise E1PersistenceError("journal safety flags are not the E1 fixed values")
        lifecycle_events = {
            JournalEventType.INTENT_PREPARED,
            JournalEventType.VIRTUAL_EXECUTION_STARTED,
            JournalEventType.VIRTUAL_EXECUTION_CONFIRMED,
            JournalEventType.VIRTUAL_EXECUTION_REJECTED,
            JournalEventType.VIRTUAL_EXECUTION_UNCERTAIN,
        }
        if self.event_type in lifecycle_events:
            required = (
                self.action,
                self.intent_id,
                self.intent_digest,
                self.token_id,
                self.state_before_digest,
                self.planned_state_digest,
            )
            if any(value is None for value in required):
                raise E1PersistenceError("execution lifecycle record is incomplete")
        if self.event_type in _RESOLVING_EVENTS and self.intent_id is not None:
            required = (
                self.action,
                self.intent_digest,
                self.token_id,
                self.state_before_digest,
                self.planned_state_digest,
            )
            if any(value is None for value in required):
                raise E1PersistenceError("intent resolution record is incomplete")
        if self.event_type is JournalEventType.FAULT_HANDLED:
            required = (
                self.action,
                self.intent_id,
                self.intent_digest,
                self.token_id,
                self.state_before_digest,
                self.planned_state_digest,
                self.observed_state_digest,
            )
            if (
                any(value is None for value in required)
                or self.fault_kind is FaultKind.NONE
                or self.execution_outcome is not None
                or self.status_label != "FAULT_HANDLED_WITHOUT_RETRY"
                or self.reason_codes != (self.fault_kind.value,)
            ):
                raise E1PersistenceError("fault handled record is incomplete or invalid")
        decision_fields = (
            self.decision_digest,
            self.hypothesis_label,
            self.hypothesis_id,
            self.hypothesis_version,
        )
        is_terminal_no_action = (
            self.event_type is JournalEventType.NO_ACTION_RECORDED
            and self.status_label == "ENGINE_NO_ACTION_TERMINAL"
        )
        if is_terminal_no_action:
            if (
                any(value is None for value in decision_fields)
                or self.action is not None
                or self.intent_id is not None
                or len(self.reason_codes) != 1
                or not _SAFE_LABEL.fullmatch(self.hypothesis_id or "")
                or not _SAFE_LABEL.fullmatch(self.hypothesis_version or "")
            ):
                raise E1PersistenceError("terminal no-action decision evidence is incomplete")
        elif any(value is not None for value in decision_fields):
            raise E1PersistenceError("decision evidence fields are event-specific")
        if self.event_type is JournalEventType.INCIDENT_RECORDED:
            if (
                not isinstance(self.incident_ref, str)
                or not _SAFE_LABEL.fullmatch(self.incident_ref)
                or self.incident_severity not in {"HIGH", "MEDIUM"}
            ):
                raise E1PersistenceError("incident record requires safe ref and severity")
        elif self.event_type is JournalEventType.POSTMORTEM_RECORDED:
            if (
                not isinstance(self.incident_ref, str)
                or not _SAFE_LABEL.fullmatch(self.incident_ref)
                or self.incident_severity is not None
            ):
                raise E1PersistenceError("postmortem record requires incident_ref only")
        elif self.incident_ref is not None or self.incident_severity is not None:
            raise E1PersistenceError("incident fields are event-specific")

    def as_json_dict(self) -> dict[str, Any]:
        row = asdict(self)
        for field_name in (
            "event_type",
            "action",
            "hypothesis_label",
            "execution_outcome",
            "fault_kind",
            "pnl_category",
        ):
            value = getattr(self, field_name)
            row[field_name] = value.value if isinstance(value, Enum) else None
        row["reason_codes"] = list(self.reason_codes)
        return row

    @classmethod
    def from_json_dict(cls, row: dict[str, Any]) -> JournalRecord:
        expected_fields = set(cls.__dataclass_fields__)
        if set(row) != expected_fields:
            raise E1PersistenceError("journal record fields are invalid")
        try:
            return cls(
                schema_version=row["schema_version"],
                sequence=row["sequence"],
                event_type=JournalEventType(row["event_type"]),
                timestamp=row["timestamp"],
                recorded_at=row["recorded_at"],
                run_id=row["run_id"],
                config_hash=row["config_hash"],
                status_label=row["status_label"],
                reason_codes=tuple(row["reason_codes"]),
                expected_state_digest=row["expected_state_digest"],
                position_count=row["position_count"],
                action=GateAction(row["action"]) if row["action"] is not None else None,
                intent_id=row["intent_id"],
                intent_digest=row["intent_digest"],
                token_id=row["token_id"],
                decision_digest=row["decision_digest"],
                hypothesis_label=(
                    HypothesisLabel(row["hypothesis_label"])
                    if row["hypothesis_label"] is not None
                    else None
                ),
                hypothesis_id=row["hypothesis_id"],
                hypothesis_version=row["hypothesis_version"],
                execution_outcome=(
                    ExecutionOutcome(row["execution_outcome"])
                    if row["execution_outcome"] is not None
                    else None
                ),
                fault_kind=FaultKind(row["fault_kind"]),
                state_before_digest=row["state_before_digest"],
                planned_state_digest=row["planned_state_digest"],
                observed_state_digest=row["observed_state_digest"],
                pnl_category=PnlCategory(row["pnl_category"]),
                virtual_loss=row["virtual_loss"],
                incident_ref=row["incident_ref"],
                incident_severity=row["incident_severity"],
                safety=row["safety"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise E1PersistenceError("journal record cannot be decoded") from error


def _prepare_local_path(root: Path, path: Path) -> tuple[Path, Path]:
    try:
        root.mkdir(parents=True, exist_ok=True)
        resolved_root = root.resolve(strict=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = path.parent.resolve(strict=True)
    except OSError as error:
        raise E1PersistenceError("E1 persistence root cannot be prepared") from error
    if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
        raise E1PersistenceError("E1 persistence path escapes its trusted root")
    if path.is_symlink() or path.parent.is_symlink():
        raise E1PersistenceError("E1 persistence path cannot be a symlink")
    return resolved_root, resolved_parent / path.name


def _fsync_directory(directory: Path) -> None:
    descriptor: int | None = None
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags)
        os.fsync(descriptor)
    except OSError as error:
        raise E1PersistenceError("persistence parent directory fsync failed") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


class ShadowIntentJournal:
    """Append-only fsync journal.  Every row carries the frozen config hash."""

    def __init__(self, *, root: Path, path: Path, run_id: str, config_hash: str) -> None:
        if not isinstance(run_id, str) or not _SAFE_LABEL.fullmatch(run_id):
            raise E1PersistenceError("journal run_id must be a safe local identifier")
        self.root, self.path = _prepare_local_path(root, path)
        self.lock_path = self.root / f".{self.path.name}.lock"
        self._process_lock = RLock()
        self.run_id = run_id
        self.config_hash = config_hash
        with self._locked():
            self._records = self._load()
        if any(record.run_id != run_id for record in self._records):
            raise E1PersistenceError("journal run_id mismatch")
        if any(record.config_hash != config_hash for record in self._records):
            raise E1PersistenceError("journal config hash mismatch")

    def _load(self) -> list[JournalRecord]:
        if not self.path.exists():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise E1PersistenceError("journal cannot be read") from error
        if not lines or any(not line.strip() for line in lines):
            raise E1PersistenceError("journal is empty or truncated")
        records: list[JournalRecord] = []
        for sequence, line in enumerate(lines):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as error:
                raise E1PersistenceError("journal contains invalid JSON") from error
            if not isinstance(raw, dict):
                raise E1PersistenceError("journal row must be an object")
            record = JournalRecord.from_json_dict(raw)
            if record.sequence != sequence:
                raise E1PersistenceError("journal sequence is not contiguous")
            records.append(record)
        return records

    @contextmanager
    def _locked(self) -> Iterator[None]:
        if self.lock_path.is_symlink():
            raise E1PersistenceError("journal lock path cannot be a symlink")
        try:
            with self._process_lock, self.lock_path.open(
                "a+", encoding="utf-8"
            ) as lock_handle:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except OSError as error:
            raise E1PersistenceError("journal single-writer lock failed") from error

    @property
    def records(self) -> tuple[JournalRecord, ...]:
        with self._process_lock:
            return tuple(self._records)

    @property
    def is_new(self) -> bool:
        with self._process_lock:
            return not self._records

    @property
    def expected_state_digest(self) -> str:
        with self._process_lock:
            if not self._records:
                return position_digest(None)
            return self._records[-1].expected_state_digest

    @property
    def kill_active(self) -> bool:
        with self._process_lock:
            return any(
                record.event_type
                in {JournalEventType.KILL_ACTIVATED, JournalEventType.DEADMAN_ACTIVATED}
                for record in self._records
            )

    @property
    def halted(self) -> bool:
        with self._process_lock:
            return any(
                record.event_type is JournalEventType.HALTED for record in self._records
            )

    @property
    def last_heartbeat(self) -> str | None:
        with self._process_lock:
            for record in reversed(self._records):
                if record.event_type is JournalEventType.HEARTBEAT_RECORDED:
                    return record.timestamp
        return None

    def append(
        self,
        *,
        event_type: JournalEventType,
        timestamp: str,
        status_label: str,
        expected_state_digest: str,
        position_count: int,
        reason_codes: tuple[str, ...] = (),
        action: GateAction | None = None,
        intent_id: str | None = None,
        intent_digest: str | None = None,
        token_id: str | None = None,
        decision_digest: str | None = None,
        hypothesis_label: HypothesisLabel | None = None,
        hypothesis_id: str | None = None,
        hypothesis_version: str | None = None,
        execution_outcome: ExecutionOutcome | None = None,
        fault_kind: FaultKind = FaultKind.NONE,
        state_before_digest: str | None = None,
        planned_state_digest: str | None = None,
        observed_state_digest: str | None = None,
        pnl_category: PnlCategory = PnlCategory.NOT_APPLICABLE,
        virtual_loss: str = "0",
        incident_ref: str | None = None,
        incident_severity: str | None = None,
    ) -> JournalRecord:
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise E1PersistenceError("journal path became a symlink")
        with self._locked():
            disk_records = self._load()
            if disk_records != self._records:
                raise E1PersistenceError("concurrent journal modification detected")
            creates_journal = not self.path.exists()
            record = JournalRecord(
                schema_version=E1_SCHEMA_VERSION,
                sequence=len(self._records),
                event_type=event_type,
                timestamp=canonical_timestamp(timestamp),
                recorded_at=canonical_timestamp(datetime.now(UTC)),
                run_id=self.run_id,
                config_hash=self.config_hash,
                status_label=status_label,
                reason_codes=reason_codes,
                expected_state_digest=expected_state_digest,
                position_count=position_count,
                action=action,
                intent_id=intent_id,
                intent_digest=intent_digest,
                token_id=token_id,
                decision_digest=decision_digest,
                hypothesis_label=hypothesis_label,
                hypothesis_id=hypothesis_id,
                hypothesis_version=hypothesis_version,
                execution_outcome=execution_outcome,
                fault_kind=fault_kind,
                state_before_digest=state_before_digest,
                planned_state_digest=planned_state_digest,
                observed_state_digest=observed_state_digest,
                pnl_category=pnl_category,
                virtual_loss=canonical_decimal(virtual_loss),
                incident_ref=incident_ref,
                incident_severity=incident_severity,
                safety=shadow_safety_flags(),
            )
            serialized = json.dumps(
                record.as_json_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            try:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(f"{serialized}\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                if creates_journal:
                    _fsync_directory(self.path.parent)
            except OSError as error:
                raise E1PersistenceError("journal append/fsync failed") from error
            self._records.append(record)
        return record

    def unresolved_intents(self) -> tuple[JournalRecord, ...]:
        prepared: dict[str, JournalRecord] = {}
        resolved: set[str] = set()
        for record in self.records:
            if record.event_type is JournalEventType.INTENT_PREPARED and record.intent_id:
                if record.intent_id in prepared:
                    raise E1PersistenceError("duplicate intent_id in journal")
                prepared[record.intent_id] = record
            elif record.event_type in _RESOLVING_EVENTS and record.intent_id:
                resolved.add(record.intent_id)
        return tuple(record for intent, record in prepared.items() if intent not in resolved)

    def risk_counters(self, *, now: str) -> dict[str, Any]:
        current = parse_timestamp(now)
        day = current.date()
        iso_year, iso_week, _ = current.isocalendar()
        entries_today = 0
        daily_loss = finite_decimal(0, field_name="daily_loss")
        weekly_loss = finite_decimal(0, field_name="weekly_loss")
        consecutive_losses = 0
        last_entry_at: str | None = None
        records = self.records
        prepared_times = {
            record.intent_id: record.timestamp
            for record in records
            if record.event_type is JournalEventType.INTENT_PREPARED and record.intent_id
        }
        for record in records:
            is_effect = record.event_type is JournalEventType.VIRTUAL_EXECUTION_CONFIRMED or (
                record.event_type is JournalEventType.RECONCILE_MATCHED
                and record.status_label == "RECOVERED_PLANNED_EFFECT"
            )
            if not is_effect or record.action is None:
                continue
            effective_timestamp = (
                prepared_times.get(record.intent_id, record.timestamp)
                if record.event_type is JournalEventType.RECONCILE_MATCHED
                else record.timestamp
            )
            event_time = parse_timestamp(effective_timestamp)
            if record.action is GateAction.VIRTUAL_ENTRY:
                if event_time.date() == day:
                    entries_today += 1
                last_entry_at = effective_timestamp
                continue
            if record.action is GateAction.VIRTUAL_SETTLEMENT:
                loss = finite_decimal(record.virtual_loss, field_name="virtual_loss")
                if event_time.date() == day:
                    daily_loss += loss
                event_year, event_week, _ = event_time.isocalendar()
                if (event_year, event_week) == (iso_year, iso_week):
                    weekly_loss += loss
                if record.pnl_category is PnlCategory.LOSS:
                    consecutive_losses += 1
                else:
                    consecutive_losses = 0
        return {
            "entries_today": entries_today,
            "daily_loss": daily_loss,
            "weekly_loss": weekly_loss,
            "consecutive_losses": consecutive_losses,
            "last_entry_at": last_entry_at,
        }


class VirtualVenueStateStore:
    """Independent virtual venue state used by exact restart reconciliation."""

    def __init__(self, *, root: Path, path: Path, config_hash: str) -> None:
        self.root, self.path = _prepare_local_path(root, path)
        self.lock_path = self.root / f".{self.path.name}.lock"
        self._process_lock = RLock()
        self.config_hash = config_hash
        self._executor_key: object | None = None
        with self._locked():
            self._position = self._load()

    @contextmanager
    def _locked(self) -> Iterator[None]:
        if self.lock_path.is_symlink():
            raise E1PersistenceError("virtual venue lock path cannot be a symlink")
        try:
            with self._process_lock, self.lock_path.open(
                "a+", encoding="utf-8"
            ) as lock_handle:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except OSError as error:
            raise E1PersistenceError("virtual venue single-writer lock failed") from error

    def _bind_executor(self, executor_key: object) -> None:
        with self._process_lock:
            if self._executor_key is not None:
                raise E1PersistenceError("virtual venue executor is already bound")
            self._executor_key = executor_key

    def _assert_executor_key(self, executor_key: object) -> None:
        if self._executor_key is None or executor_key is not self._executor_key:
            raise E1PersistenceError("virtual venue mutation requires the bound executor")

    def _load(self) -> VirtualPosition | None:
        if not self.path.exists():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise E1PersistenceError("virtual venue state cannot be read") from error
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "config_hash", "position"}:
            raise E1PersistenceError("virtual venue state schema is invalid")
        if raw["schema_version"] != E1_SCHEMA_VERSION or raw["config_hash"] != self.config_hash:
            raise E1PersistenceError("virtual venue state config hash mismatch")
        position = raw["position"]
        if position is None:
            return None
        expected = {
            "position_ref",
            "symbol",
            "side",
            "units",
            "entry_price",
            "protective_stop_price",
        }
        if not isinstance(position, dict) or set(position) != expected:
            raise E1PersistenceError("virtual venue position schema is invalid")
        try:
            return VirtualPosition(
                position_ref=position["position_ref"],
                symbol=position["symbol"],
                side=PositionSide(position["side"]),
                units=position["units"],
                entry_price=finite_decimal(position["entry_price"], field_name="entry_price"),
                protective_stop_price=finite_decimal(
                    position["protective_stop_price"], field_name="protective_stop_price"
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise E1PersistenceError("virtual venue position cannot be decoded") from error

    @property
    def position(self) -> VirtualPosition | None:
        with self._process_lock:
            return self._position

    @property
    def state_digest(self) -> str:
        with self._process_lock:
            return position_digest(self._position)

    @property
    def position_count(self) -> int:
        with self._process_lock:
            return int(self._position is not None)

    def _persist(
        self,
        position: VirtualPosition | None,
        *,
        executor_key: object,
        require_flat: bool,
        expected_position_ref: str | None,
    ) -> None:
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise E1PersistenceError("virtual venue path became a symlink")
        payload = {
            "schema_version": E1_SCHEMA_VERSION,
            "config_hash": self.config_hash,
            "position": (
                None
                if position is None
                else {
                    "position_ref": position.position_ref,
                    "symbol": position.symbol,
                    "side": position.side.value,
                    "units": position.units,
                    "entry_price": canonical_decimal(position.entry_price),
                    "protective_stop_price": canonical_decimal(position.protective_stop_price),
                }
            ),
        }
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        if temporary.is_symlink():
            raise E1PersistenceError("virtual venue temporary path cannot be a symlink")
        with self._locked():
            self._assert_executor_key(executor_key)
            disk_position = self._load()
            if disk_position != self._position:
                raise E1PersistenceError("concurrent virtual venue modification detected")
            if require_flat:
                if disk_position is not None or position is None:
                    raise E1PersistenceError("virtual venue position limit is one")
            elif (
                disk_position is None
                or disk_position.position_ref != expected_position_ref
                or position is not None
            ):
                raise E1PersistenceError("position-specific virtual settlement mismatch")
            try:
                with temporary.open("w", encoding="utf-8") as handle:
                    json.dump(
                        payload,
                        handle,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                temporary.replace(self.path)
            except OSError as error:
                raise E1PersistenceError("virtual venue state write/fsync failed") from error
            _fsync_directory(self.path.parent)
            self._position = position

    def _open_position(self, position: VirtualPosition, *, executor_key: object) -> None:
        self._persist(
            position,
            executor_key=executor_key,
            require_flat=True,
            expected_position_ref=None,
        )

    def _settle_position_specific(self, *, position_ref: str, executor_key: object) -> None:
        self._persist(
            None,
            executor_key=executor_key,
            require_flat=False,
            expected_position_ref=position_ref,
        )
