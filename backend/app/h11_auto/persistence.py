"""SQLite state, hash-linked safe journal, and process lock for Phase A."""

from __future__ import annotations

import fcntl
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO
from zoneinfo import ZoneInfo

from app.h11_auto.contracts import FormalSignal, PhaseAExecutionPolicy, build_intent_id
from app.h11_auto.state_machine import AutoCycleState, require_transition

PHASE_A_SCHEMA_VERSION = "H11_AUTO_PARALLEL_PHASE_A_V1"
JST = ZoneInfo("Asia/Tokyo")
_ACTIVE_STATES = (
    AutoCycleState.INTENT_PERSISTED.value,
    AutoCycleState.PROTECTED_ENTRY_PENDING.value,
    AutoCycleState.POSITION_PROTECTED.value,
    AutoCycleState.EXIT_PENDING.value,
)


class H11AutoPersistenceError(RuntimeError):
    """Fail-closed persistence error carrying no broker values or identifiers."""


@dataclass(frozen=True)
class SafeRunGenerationBinding:
    generation_label: str
    strategy_version: str
    selected_horizon: str
    risk_policy_label: str
    dead_man_policy_label: str

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class StoredCycle:
    intent_id: str
    signal_fingerprint: str
    state: AutoCycleState
    attempt_count: int
    exit_attempt_count: int
    entry_day_jst: str | None
    created_at_utc: str
    updated_at_utc: str
    halt_reason: str | None

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class SafeJournalSummary:
    valid: bool
    event_count: int
    final_state: str
    actual_post_count: int = 0
    broker_write_performed: bool = False
    raw_id_value_exposure: bool = False

    def __bool__(self) -> bool:
        return False


class H11AutoStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        if self.path.is_symlink():
            raise H11AutoPersistenceError("state path must not be a symlink")
        if self.path.exists() and not self.path.is_file():
            raise H11AutoPersistenceError("state path must be a regular file")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._initialize()
        except sqlite3.Error as error:
            raise H11AutoPersistenceError("state database initialization failed") from error

    def _connect(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            raise H11AutoPersistenceError("state path must not be a symlink")
        if self.path.exists() and not self.path.is_file():
            raise H11AutoPersistenceError("state path must be a regular file")
        try:
            connection = sqlite3.connect(self.path, timeout=5.0)
        except sqlite3.Error as error:
            raise H11AutoPersistenceError("state database cannot be opened") from error
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cycles (
                    intent_id TEXT PRIMARY KEY,
                    signal_fingerprint TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count BETWEEN 0 AND 1),
                    exit_attempt_count INTEGER NOT NULL DEFAULT 0
                        CHECK(exit_attempt_count BETWEEN 0 AND 1),
                    entry_day_jst TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    halt_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS safe_events (
                    sequence INTEGER PRIMARY KEY,
                    intent_id TEXT NOT NULL,
                    event_category TEXT NOT NULL,
                    state_safe_label TEXT NOT NULL,
                    previous_digest TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    FOREIGN KEY(intent_id) REFERENCES cycles(intent_id)
                );
                """
            )
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO metadata(key, value) VALUES('schema_version', ?)",
                    (PHASE_A_SCHEMA_VERSION,),
                )
            elif row["value"] != PHASE_A_SCHEMA_VERSION:
                raise H11AutoPersistenceError("state schema version mismatch")

    def create_intent(
        self,
        *,
        signal: FormalSignal,
        policy: PhaseAExecutionPolicy,
        now_utc: datetime,
    ) -> StoredCycle:
        intent_id = build_intent_id(signal=signal, policy=policy)
        timestamp = _timestamp(now_utc)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                placeholders = ",".join("?" for _ in _ACTIVE_STATES)
                active = connection.execute(
                    f"SELECT 1 FROM cycles WHERE state IN ({placeholders}) LIMIT 1",  # noqa: S608
                    _ACTIVE_STATES,
                ).fetchone()
                if active is not None:
                    raise H11AutoPersistenceError("an active cycle already exists")
                halted = connection.execute(
                    "SELECT 1 FROM cycles WHERE state = ? LIMIT 1",
                    (AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED.value,),
                ).fetchone()
                if halted is not None:
                    raise H11AutoPersistenceError("operator review halt is latched")
                connection.execute(
                    """
                    INSERT INTO cycles(
                        intent_id, signal_fingerprint, state, attempt_count,
                        created_at_utc, updated_at_utc
                    ) VALUES(?, ?, ?, 0, ?, ?)
                    """,
                    (
                        intent_id,
                        signal.fingerprint,
                        AutoCycleState.INTENT_PERSISTED.value,
                        timestamp,
                        timestamp,
                    ),
                )
                self._append_event(
                    connection,
                    intent_id=intent_id,
                    event_category="INTENT_PERSISTED",
                    state=AutoCycleState.INTENT_PERSISTED,
                )
        except sqlite3.IntegrityError as error:
            raise H11AutoPersistenceError("duplicate signal intent refused") from error
        return self.load_cycle(intent_id)

    def bind_run_generation(
        self,
        *,
        generation_label: str,
        policy: PhaseAExecutionPolicy,
        risk_policy_label: str,
        risk_policy_digest: str,
        dead_man_policy_label: str,
        dead_man_policy_digest: str,
    ) -> SafeRunGenerationBinding:
        """Persist one immutable policy identity for this state database."""

        labels = {
            "generation_label": generation_label,
            "strategy_version": policy.strategy_version,
            "selected_horizon": policy.selected_horizon.value,
            "risk_policy_label": risk_policy_label,
            "dead_man_policy_label": dead_man_policy_label,
        }
        for label in labels.values():
            _validate_safe_label(label)
        for digest in (policy.signal_config_hash, risk_policy_digest, dead_man_policy_digest):
            if not isinstance(digest, str) or not digest.strip():
                raise H11AutoPersistenceError("run generation digest is invalid")
        canonical = json.dumps(
            {
                **labels,
                "signal_config_hash": policy.signal_config_hash,
                "risk_policy_digest": risk_policy_digest,
                "dead_man_policy_digest": dead_man_policy_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        run_digest = hashlib.sha256(canonical.encode()).hexdigest()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'run_generation_digest'"
                ).fetchone()
                if existing is None:
                    values = {
                        **labels,
                        "run_generation_manifest": canonical,
                        "run_generation_digest": run_digest,
                    }
                    connection.executemany(
                        "INSERT INTO metadata(key, value) VALUES(?, ?)",
                        tuple(values.items()),
                    )
                elif existing["value"] != run_digest:
                    raise H11AutoPersistenceError("run generation policy mismatch")
                else:
                    persisted_rows = dict(
                        connection.execute(
                            "SELECT key, value FROM metadata WHERE key IN "
                            "('generation_label', 'strategy_version', 'selected_horizon', "
                            "'risk_policy_label', 'dead_man_policy_label', "
                            "'run_generation_manifest')"
                        ).fetchall()
                    )
                    persisted_manifest = persisted_rows.pop(
                        "run_generation_manifest", None
                    )
                    if persisted_rows != labels or persisted_manifest != canonical:
                        raise H11AutoPersistenceError(
                            "run generation metadata is incomplete or invalid"
                        )
        except sqlite3.IntegrityError as error:
            raise H11AutoPersistenceError("run generation metadata conflict") from error
        return SafeRunGenerationBinding(**labels)

    def load_run_generation_safe(self) -> SafeRunGenerationBinding | None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT key, value FROM metadata WHERE key IN "
                "('run_generation_digest', 'run_generation_manifest', "
                "'generation_label', 'strategy_version', 'selected_horizon', "
                "'risk_policy_label', 'dead_man_policy_label')"
            ).fetchall()
        if not rows:
            return None
        values = dict(rows)
        required = {
            "run_generation_digest",
            "run_generation_manifest",
            "generation_label",
            "strategy_version",
            "selected_horizon",
            "risk_policy_label",
            "dead_man_policy_label",
        }
        if set(values) != required:
            raise H11AutoPersistenceError(
                "run generation metadata is incomplete or invalid"
            )
        manifest = values.pop("run_generation_manifest")
        digest = values.pop("run_generation_digest")
        if hashlib.sha256(manifest.encode()).hexdigest() != digest:
            raise H11AutoPersistenceError("run generation metadata digest is invalid")
        try:
            manifest_values = json.loads(manifest)
        except json.JSONDecodeError as error:
            raise H11AutoPersistenceError(
                "run generation metadata manifest is invalid"
            ) from error
        safe_values = {
            "generation_label": values["generation_label"],
            "strategy_version": values["strategy_version"],
            "selected_horizon": values["selected_horizon"],
            "risk_policy_label": values["risk_policy_label"],
            "dead_man_policy_label": values["dead_man_policy_label"],
        }
        if not isinstance(manifest_values, dict) or any(
            manifest_values.get(key) != value for key, value in safe_values.items()
        ):
            raise H11AutoPersistenceError("run generation metadata manifest is invalid")
        for value in safe_values.values():
            _validate_safe_label(value)
        return SafeRunGenerationBinding(
            **safe_values,
        )

    def record_attempt_started(self, *, intent_id: str, now_utc: datetime) -> StoredCycle:
        timestamp = _timestamp(now_utc)
        entry_day_jst = now_utc.astimezone(JST).date().isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._cycle_row(connection, intent_id)
            current = AutoCycleState(row["state"])
            if row["attempt_count"] != 0:
                raise H11AutoPersistenceError("second attempt refused")
            require_transition(current, AutoCycleState.PROTECTED_ENTRY_PENDING)
            updated = connection.execute(
                """
                UPDATE cycles
                SET attempt_count = 1, state = ?, updated_at_utc = ?, entry_day_jst = ?
                WHERE intent_id = ? AND attempt_count = 0
                """,
                (
                    AutoCycleState.PROTECTED_ENTRY_PENDING.value,
                    timestamp,
                    entry_day_jst,
                    intent_id,
                ),
            )
            if updated.rowcount != 1:
                raise H11AutoPersistenceError("attempt compare-and-set failed")
            self._append_event(
                connection,
                intent_id=intent_id,
                event_category="ENTRY_ATTEMPT_STARTED_SYNTHETIC",
                state=AutoCycleState.PROTECTED_ENTRY_PENDING,
            )
        return self.load_cycle(intent_id)

    def transition(
        self,
        *,
        intent_id: str,
        target: AutoCycleState,
        event_category: str,
        now_utc: datetime,
        halt_reason: str | None = None,
    ) -> StoredCycle:
        timestamp = _timestamp(now_utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._cycle_row(connection, intent_id)
            current = AutoCycleState(row["state"])
            require_transition(current, target)
            if target is AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED and not halt_reason:
                raise H11AutoPersistenceError("halt reason is required")
            connection.execute(
                """
                UPDATE cycles SET state = ?, updated_at_utc = ?, halt_reason = ?
                WHERE intent_id = ?
                """,
                (target.value, timestamp, halt_reason, intent_id),
            )
            self._append_event(
                connection,
                intent_id=intent_id,
                event_category=event_category,
                state=target,
            )
        return self.load_cycle(intent_id)

    def record_exit_attempt_started(
        self, *, intent_id: str, now_utc: datetime
    ) -> StoredCycle:
        timestamp = _timestamp(now_utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._cycle_row(connection, intent_id)
            current = AutoCycleState(row["state"])
            if row["exit_attempt_count"] != 0:
                raise H11AutoPersistenceError("second exit attempt refused")
            require_transition(current, AutoCycleState.EXIT_PENDING)
            updated = connection.execute(
                """
                UPDATE cycles
                SET exit_attempt_count = 1, state = ?, updated_at_utc = ?
                WHERE intent_id = ? AND exit_attempt_count = 0
                """,
                (AutoCycleState.EXIT_PENDING.value, timestamp, intent_id),
            )
            if updated.rowcount != 1:
                raise H11AutoPersistenceError("exit attempt compare-and-set failed")
            self._append_event(
                connection,
                intent_id=intent_id,
                event_category="EXIT_ATTEMPT_STARTED_SYNTHETIC",
                state=AutoCycleState.EXIT_PENDING,
            )
        return self.load_cycle(intent_id)

    def load_cycle(self, intent_id: str) -> StoredCycle:
        with self._connect() as connection:
            row = self._cycle_row(connection, intent_id)
        return StoredCycle(
            intent_id=row["intent_id"],
            signal_fingerprint=row["signal_fingerprint"],
            state=AutoCycleState(row["state"]),
            attempt_count=row["attempt_count"],
            exit_attempt_count=row["exit_attempt_count"],
            entry_day_jst=row["entry_day_jst"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
            halt_reason=row["halt_reason"],
        )

    def active_intent_count(self) -> int:
        placeholders = ",".join("?" for _ in _ACTIVE_STATES)
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM cycles WHERE state IN ({placeholders})",  # noqa: S608
                _ACTIVE_STATES,
            ).fetchone()
        return int(row["count"])

    def entry_attempts_on_jst_day(self, *, now_utc: datetime) -> int:
        _timestamp(now_utc)
        day = now_utc.astimezone(JST).date().isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM cycles WHERE entry_day_jst = ?",
                (day,),
            ).fetchone()
        return int(row["count"])

    def halt_latched(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM cycles WHERE state = ? LIMIT 1",
                (AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED.value,),
            ).fetchone()
        return row is not None

    def verify_journal(self) -> SafeJournalSummary:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM safe_events ORDER BY sequence"
            ).fetchall()
        previous = "GENESIS"
        for expected, row in enumerate(rows, start=1):
            payload = {
                "event_category": row["event_category"],
                "intent_id": row["intent_id"],
                "previous_digest": row["previous_digest"],
                "sequence": row["sequence"],
                "state_safe_label": row["state_safe_label"],
            }
            if (
                row["sequence"] != expected
                or row["previous_digest"] != previous
                or row["digest"] != _digest(payload)
            ):
                raise H11AutoPersistenceError("safe journal verification failed")
            previous = row["digest"]
        return SafeJournalSummary(
            valid=True,
            event_count=len(rows),
            final_state=rows[-1]["state_safe_label"] if rows else "EMPTY",
        )

    @staticmethod
    def _cycle_row(connection: sqlite3.Connection, intent_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM cycles WHERE intent_id = ?", (intent_id,)
        ).fetchone()
        if row is None:
            raise H11AutoPersistenceError("cycle not found")
        return row

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        *,
        intent_id: str,
        event_category: str,
        state: AutoCycleState,
    ) -> None:
        previous_row = connection.execute(
            "SELECT sequence, digest FROM safe_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        sequence = 1 if previous_row is None else previous_row["sequence"] + 1
        previous = "GENESIS" if previous_row is None else previous_row["digest"]
        payload = {
            "event_category": event_category,
            "intent_id": intent_id,
            "previous_digest": previous,
            "sequence": sequence,
            "state_safe_label": state.value,
        }
        connection.execute(
            """
            INSERT INTO safe_events(
                sequence, intent_id, event_category, state_safe_label,
                previous_digest, digest
            ) VALUES(?, ?, ?, ?, ?, ?)
            """,
            (sequence, intent_id, event_category, state.value, previous, _digest(payload)),
        )


class H11AutoProcessLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: IO[str] | None = None

    @property
    def held(self) -> bool:
        return self._handle is not None

    def acquire(self) -> bool:
        if self._handle is not None:
            return True
        if self.path.is_symlink():
            raise H11AutoPersistenceError("process lock path must not be a symlink")
        if self.path.exists() and not self.path.is_file():
            raise H11AutoPersistenceError("process lock path must be a regular file")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = self.path.open("a+", encoding="utf-8")
        except OSError as error:
            raise H11AutoPersistenceError("process lock cannot be opened") from error
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None

    def __enter__(self) -> H11AutoProcessLock:
        if not self.acquire():
            raise H11AutoPersistenceError("process lock is already held")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        self.release()


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise H11AutoPersistenceError("timestamp must be timezone-aware")
    return value.isoformat()


def _digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validate_safe_label(value: object) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 128
        or "\n" in value
        or "\r" in value
    ):
        raise H11AutoPersistenceError("run generation label is invalid")
