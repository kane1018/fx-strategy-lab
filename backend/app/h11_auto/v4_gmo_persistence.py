"""Independent SQLite journal for the relaxed GMO v4 profile."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.h11_auto.contracts import FormalSignal
from app.h11_auto.v4_gmo_contracts import (
    V4_GMO_PROFILE_VERSION,
    V4GmoAction,
    V4GmoCycleState,
    V4GmoExecutionPolicy,
    V4GmoSyntheticOutcome,
    build_v4_cycle_ref,
    require_v4_transition,
)

V4_GMO_SCHEMA_VERSION = "H11_V4_GMO_RELAXED_STATE_V1"
JST = ZoneInfo("Asia/Tokyo")
_ACTIVE_STATES = tuple(
    state.value
    for state in V4GmoCycleState
    if state
    not in (
        V4GmoCycleState.FLAT_RECONCILED,
        V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        V4GmoCycleState.OPERATOR_RELOAD_CLEARED,
    )
)


class V4GmoPersistenceError(RuntimeError):
    """Fixed safe persistence failure with no broker identifier values."""


@dataclass(frozen=True)
class V4GmoStoredCycle:
    cycle_ref: str
    signal_fingerprint: str
    policy_config_hash: str
    state: V4GmoCycleState
    side: str
    requested_size: int
    filled_size: int
    protected_size: int
    unprotected_since_utc: str | None
    entry_day_jst: str
    created_at_utc: str
    updated_at_utc: str
    halt_reason: str | None

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4GmoGenerationBinding:
    generation_label: str
    profile_version: str
    policy_config_hash: str
    strategy_version: str
    selected_horizon: str
    risk_policy_label: str
    dead_man_policy_label: str
    protection_contract_hash: str
    broker_capability_evidence_hash: str

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4GmoJournalSummary:
    valid: bool
    event_count: int
    action_attempt_count: int
    final_state: str
    actual_post_count: int = 0
    broker_write_performed: bool = False
    credential_read_performed: bool = False
    network_access_performed: bool = False
    raw_or_id_value_exposure: bool = False

    def __bool__(self) -> bool:
        return False


class V4GmoStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        if self.path.is_symlink():
            raise V4GmoPersistenceError("v4 state path must not be a symlink")
        if self.path.exists() and not self.path.is_file():
            raise V4GmoPersistenceError("v4 state path must be a regular file")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._initialize()
        except sqlite3.Error as error:
            raise V4GmoPersistenceError("v4 state initialization failed") from error

    def _connect(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            raise V4GmoPersistenceError("v4 state path must not be a symlink")
        try:
            connection = sqlite3.connect(self.path, timeout=5.0)
        except sqlite3.Error as error:
            raise V4GmoPersistenceError("v4 state database cannot be opened") from error
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
                    cycle_ref TEXT PRIMARY KEY,
                    signal_fingerprint TEXT NOT NULL UNIQUE,
                    policy_config_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
                    requested_size INTEGER NOT NULL CHECK(requested_size > 0),
                    filled_size INTEGER NOT NULL DEFAULT 0 CHECK(filled_size >= 0),
                    protected_size INTEGER NOT NULL DEFAULT 0 CHECK(protected_size >= 0),
                    unprotected_since_utc TEXT,
                    entry_day_jst TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    halt_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS action_attempts (
                    cycle_ref TEXT NOT NULL,
                    action_kind TEXT NOT NULL,
                    attempted_at_utc TEXT NOT NULL,
                    outcome_safe_label TEXT NOT NULL,
                    PRIMARY KEY(cycle_ref, action_kind),
                    FOREIGN KEY(cycle_ref) REFERENCES cycles(cycle_ref)
                );
                CREATE TABLE IF NOT EXISTS safe_events (
                    sequence INTEGER PRIMARY KEY,
                    cycle_ref TEXT NOT NULL,
                    event_category TEXT NOT NULL,
                    state_safe_label TEXT NOT NULL,
                    previous_digest TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    FOREIGN KEY(cycle_ref) REFERENCES cycles(cycle_ref)
                );
                """
            )
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                connection.executemany(
                    "INSERT INTO metadata(key, value) VALUES(?, ?)",
                    (
                        ("schema_version", V4_GMO_SCHEMA_VERSION),
                        ("profile_version", V4_GMO_PROFILE_VERSION),
                        ("actual_post_allowed", "false"),
                    ),
                )
            elif row["value"] != V4_GMO_SCHEMA_VERSION:
                raise V4GmoPersistenceError("v4 state schema version mismatch")

    def create_cycle(
        self,
        *,
        signal: FormalSignal,
        policy: V4GmoExecutionPolicy,
        now_utc: datetime,
    ) -> V4GmoStoredCycle:
        cycle_ref = build_v4_cycle_ref(signal=signal, policy=policy)
        timestamp = _timestamp(now_utc)
        entry_day_jst = now_utc.astimezone(JST).date().isoformat()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                placeholders = ",".join("?" for _ in _ACTIVE_STATES)
                active = connection.execute(
                    f"SELECT 1 FROM cycles WHERE state IN ({placeholders}) LIMIT 1",  # noqa: S608
                    _ACTIVE_STATES,
                ).fetchone()
                if active is not None:
                    raise V4GmoPersistenceError("an active v4 GMO cycle already exists")
                if self._halt_latched_with_connection(connection):
                    raise V4GmoPersistenceError("v4 GMO operator halt is latched")
                market_attempt = connection.execute(
                    """
                    SELECT 1 FROM action_attempts AS attempts
                    JOIN cycles ON cycles.cycle_ref = attempts.cycle_ref
                    WHERE attempts.action_kind = ? AND cycles.entry_day_jst = ?
                    LIMIT 1
                    """,
                    (V4GmoAction.MARKET_ENTRY.value, entry_day_jst),
                ).fetchone()
                if market_attempt is not None:
                    raise V4GmoPersistenceError("v4 GMO daily entry attempt already exists")
                connection.execute(
                    """
                    INSERT INTO cycles(
                        cycle_ref, signal_fingerprint, policy_config_hash, state,
                        side, requested_size, entry_day_jst, created_at_utc, updated_at_utc
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cycle_ref,
                        signal.fingerprint,
                        policy.config_hash,
                        V4GmoCycleState.ENTRY_INTENT_PERSISTED.value,
                        signal.decision.value,
                        policy.requested_size,
                        entry_day_jst,
                        timestamp,
                        timestamp,
                    ),
                )
                self._append_event(
                    connection,
                    cycle_ref=cycle_ref,
                    event_category="ENTRY_INTENT_PERSISTED",
                    state=V4GmoCycleState.ENTRY_INTENT_PERSISTED,
                )
        except sqlite3.IntegrityError as error:
            raise V4GmoPersistenceError("duplicate v4 GMO cycle refused") from error
        return self.load_cycle(cycle_ref)

    def bind_generation(
        self,
        *,
        generation_label: str,
        policy: V4GmoExecutionPolicy,
        risk_policy_label: str,
        risk_policy_digest: str,
        dead_man_policy_label: str,
        dead_man_policy_digest: str,
    ) -> V4GmoGenerationBinding:
        labels = {
            "generation_label": generation_label,
            "profile_version": V4_GMO_PROFILE_VERSION,
            "policy_config_hash": policy.config_hash,
            "strategy_version": policy.strategy_version,
            "selected_horizon": policy.selected_horizon.value,
            "risk_policy_label": risk_policy_label,
            "dead_man_policy_label": dead_man_policy_label,
            "protection_contract_hash": policy.protection_contract_hash,
            "broker_capability_evidence_hash": policy.broker_capability_evidence_hash,
        }
        for key, value in labels.items():
            if key.endswith("hash"):
                if not isinstance(value, str) or not value.startswith("sha256:"):
                    raise V4GmoPersistenceError("v4 generation hash is invalid")
            else:
                _validate_generation_label(value)
        for digest in (risk_policy_digest, dead_man_policy_digest):
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise V4GmoPersistenceError("v4 generation digest is invalid")
        manifest = json.dumps(
            {
                **labels,
                "risk_policy_digest": risk_policy_digest,
                "dead_man_policy_digest": dead_man_policy_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        generation_digest = hashlib.sha256(manifest.encode()).hexdigest()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'generation_digest'"
                ).fetchone()
                if existing is None:
                    values = {
                        **labels,
                        "generation_manifest": manifest,
                        "generation_digest": generation_digest,
                    }
                    values.pop("profile_version")
                    connection.executemany(
                        "INSERT INTO metadata(key, value) VALUES(?, ?)",
                        tuple(values.items()),
                    )
                elif existing["value"] != generation_digest:
                    raise V4GmoPersistenceError("v4 generation policy mismatch")
                else:
                    rows = connection.execute(
                        "SELECT key, value FROM metadata WHERE key IN "
                        "('generation_manifest', 'generation_label', 'profile_version', "
                        "'policy_config_hash', 'strategy_version', 'selected_horizon', "
                        "'risk_policy_label', 'dead_man_policy_label', "
                        "'protection_contract_hash', "
                        "'broker_capability_evidence_hash')"
                    ).fetchall()
                    persisted = dict(rows)
                    if persisted.pop("generation_manifest", None) != manifest:
                        raise V4GmoPersistenceError("v4 generation manifest mismatch")
                    if persisted != labels:
                        raise V4GmoPersistenceError("v4 generation metadata mismatch")
        except sqlite3.IntegrityError as error:
            raise V4GmoPersistenceError("v4 generation metadata conflict") from error
        return V4GmoGenerationBinding(**labels)

    def load_generation_safe(self) -> V4GmoGenerationBinding | None:
        keys = (
            "generation_digest",
            "generation_manifest",
            "generation_label",
            "profile_version",
            "policy_config_hash",
            "strategy_version",
            "selected_horizon",
            "risk_policy_label",
            "dead_man_policy_label",
            "protection_contract_hash",
            "broker_capability_evidence_hash",
        )
        placeholders = ",".join("?" for _ in keys)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT key, value FROM metadata WHERE key IN ({placeholders})",  # noqa: S608
                keys,
            ).fetchall()
        if not rows:
            return None
        values = dict(rows)
        if set(values) != set(keys):
            raise V4GmoPersistenceError("v4 generation metadata is incomplete")
        manifest = values.pop("generation_manifest")
        digest = values.pop("generation_digest")
        if hashlib.sha256(manifest.encode()).hexdigest() != digest:
            raise V4GmoPersistenceError("v4 generation digest mismatch")
        try:
            payload = json.loads(manifest)
        except json.JSONDecodeError as error:
            raise V4GmoPersistenceError("v4 generation manifest is invalid") from error
        if not isinstance(payload, dict) or any(
            payload.get(key) != value for key, value in values.items()
        ):
            raise V4GmoPersistenceError("v4 generation manifest mismatch")
        return V4GmoGenerationBinding(**values)

    def load_cycle(self, cycle_ref: str) -> V4GmoStoredCycle:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM cycles WHERE cycle_ref = ?", (cycle_ref,)
            ).fetchone()
        if row is None:
            raise V4GmoPersistenceError("v4 GMO cycle not found")
        return _stored_cycle(row)

    def load_single_active_cycle_safe(self) -> V4GmoStoredCycle | None:
        placeholders = ",".join("?" for _ in _ACTIVE_STATES)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM cycles WHERE state IN ({placeholders}) "  # noqa: S608
                "ORDER BY created_at_utc",
                _ACTIVE_STATES,
            ).fetchall()
        if len(rows) > 1:
            raise V4GmoPersistenceError("multiple active v4 GMO cycles detected")
        return None if not rows else _stored_cycle(rows[0])

    def load_single_halted_cycle_safe(self) -> V4GmoStoredCycle | None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM cycles WHERE state = ? ORDER BY created_at_utc",
                (V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED.value,),
            ).fetchall()
        if len(rows) > 1:
            raise V4GmoPersistenceError("multiple halted v4 GMO cycles detected")
        return None if not rows else _stored_cycle(rows[0])

    def record_action_attempt(
        self,
        *,
        cycle_ref: str,
        action: V4GmoAction,
        target: V4GmoCycleState,
        now_utc: datetime,
    ) -> V4GmoStoredCycle:
        timestamp = _timestamp(now_utc)
        expected_target = {
            V4GmoAction.MARKET_ENTRY: V4GmoCycleState.MARKET_ENTRY_ATTEMPTED,
            V4GmoAction.CANCEL_ENTRY_REMAINDER: (
                V4GmoCycleState.REMAINDER_CANCEL_ATTEMPTED
            ),
            V4GmoAction.EXACT_SIZE_OCO_PROTECTION: V4GmoCycleState.PROTECTION_ATTEMPTED,
            V4GmoAction.CANCEL_MISMATCHED_PROTECTION: (
                V4GmoCycleState.PROTECTION_CANCEL_ATTEMPTED
            ),
            V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT: (
                V4GmoCycleState.EMERGENCY_EXIT_ATTEMPTED
            ),
        }[action]
        if target is not expected_target:
            raise V4GmoPersistenceError("v4 action and attempt state do not match")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT state FROM cycles WHERE cycle_ref = ?", (cycle_ref,)
                ).fetchone()
                if row is None:
                    raise V4GmoPersistenceError("v4 GMO cycle not found")
                current = V4GmoCycleState(row["state"])
                require_v4_transition(current=current, target=target)
                connection.execute(
                    """
                    INSERT INTO action_attempts(
                        cycle_ref, action_kind, attempted_at_utc, outcome_safe_label
                    ) VALUES(?, ?, ?, 'ATTEMPT_STARTED')
                    """,
                    (cycle_ref, action.value, timestamp),
                )
                connection.execute(
                    "UPDATE cycles SET state = ?, updated_at_utc = ?, "
                    "unprotected_since_utc = CASE WHEN ? = ? "
                    "THEN COALESCE(unprotected_since_utc, ?) "
                    "ELSE unprotected_since_utc END WHERE cycle_ref = ?",
                    (
                        target.value,
                        timestamp,
                        action.value,
                        V4GmoAction.MARKET_ENTRY.value,
                        timestamp,
                        cycle_ref,
                    ),
                )
                self._append_event(
                    connection,
                    cycle_ref=cycle_ref,
                    event_category=f"{action.value}_ATTEMPT_STARTED",
                    state=target,
                )
        except sqlite3.IntegrityError as error:
            raise V4GmoPersistenceError("second v4 GMO action attempt refused") from error
        return self.load_cycle(cycle_ref)

    def record_action_outcome(
        self,
        *,
        cycle_ref: str,
        action: V4GmoAction,
        outcome_safe_label: str,
    ) -> None:
        _validate_safe_label(outcome_safe_label)
        if outcome_safe_label not in {outcome.value for outcome in V4GmoSyntheticOutcome}:
            raise V4GmoPersistenceError("v4 action outcome label is invalid")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE action_attempts SET outcome_safe_label = ?
                WHERE cycle_ref = ? AND action_kind = ?
                  AND outcome_safe_label = 'ATTEMPT_STARTED'
                """,
                (outcome_safe_label, cycle_ref, action.value),
            )
            if cursor.rowcount != 1:
                raise V4GmoPersistenceError("v4 GMO action attempt not found")
            row = connection.execute(
                "SELECT state FROM cycles WHERE cycle_ref = ?", (cycle_ref,)
            ).fetchone()
            if row is None:
                raise V4GmoPersistenceError("v4 GMO cycle not found")
            self._append_event(
                connection,
                cycle_ref=cycle_ref,
                event_category=f"{action.value}_{outcome_safe_label}",
                state=V4GmoCycleState(row["state"]),
            )

    def transition(
        self,
        *,
        cycle_ref: str,
        target: V4GmoCycleState,
        event_category: str,
        now_utc: datetime,
        filled_size: int | None = None,
        protected_size: int | None = None,
        unprotected_since_utc: datetime | None = None,
        halt_reason: str | None = None,
    ) -> V4GmoStoredCycle:
        _validate_safe_label(event_category)
        if halt_reason is not None:
            _validate_safe_label(halt_reason)
        timestamp = _timestamp(now_utc)
        updates = ["state = ?", "updated_at_utc = ?"]
        values: list[object] = [target.value, timestamp]
        if filled_size is not None:
            if type(filled_size) is not int or filled_size < 0:
                raise V4GmoPersistenceError("v4 reconciled fill size is invalid")
            updates.append("filled_size = ?")
            values.append(filled_size)
        if protected_size is not None:
            if type(protected_size) is not int or protected_size < 0:
                raise V4GmoPersistenceError("v4 reconciled protection size is invalid")
            updates.append("protected_size = ?")
            values.append(protected_size)
        if unprotected_since_utc is not None:
            updates.append("unprotected_since_utc = COALESCE(unprotected_since_utc, ?)")
            values.append(_timestamp(unprotected_since_utc))
        if halt_reason is not None:
            updates.append("halt_reason = ?")
            values.append(halt_reason)
        values.append(cycle_ref)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM cycles WHERE cycle_ref = ?", (cycle_ref,)
            ).fetchone()
            if row is None:
                raise V4GmoPersistenceError("v4 GMO cycle not found")
            current = V4GmoCycleState(row["state"])
            require_v4_transition(current=current, target=target)
            connection.execute(
                f"UPDATE cycles SET {', '.join(updates)} WHERE cycle_ref = ?",  # noqa: S608
                tuple(values),
            )
            self._append_event(
                connection,
                cycle_ref=cycle_ref,
                event_category=event_category,
                state=target,
            )
        return self.load_cycle(cycle_ref)

    def action_attempted(self, *, cycle_ref: str, action: V4GmoAction) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM action_attempts WHERE cycle_ref = ? AND action_kind = ?",
                (cycle_ref, action.value),
            ).fetchone()
        return row is not None

    def action_attempt_count(self, *, cycle_ref: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM action_attempts WHERE cycle_ref = ?",
                (cycle_ref,),
            ).fetchone()
        return int(row["count"])

    def active_cycle_count(self) -> int:
        placeholders = ",".join("?" for _ in _ACTIVE_STATES)
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM cycles WHERE state IN ({placeholders})",  # noqa: S608
                _ACTIVE_STATES,
            ).fetchone()
        return int(row["count"])

    def halt_latched(self) -> bool:
        with self._connect() as connection:
            return self._halt_latched_with_connection(connection)

    def engage_global_halt(self, *, reason: str, now_utc: datetime) -> None:
        _validate_safe_label(reason)
        timestamp = _timestamp(now_utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(
                """
                INSERT INTO metadata(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (
                    ("global_halt_latched", "true"),
                    ("global_halt_reason", reason),
                    ("global_halt_at_utc", timestamp),
                ),
            )

    def global_halt_reason_safe(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'global_halt_reason'"
            ).fetchone()
        return None if row is None else str(row["value"])

    def clear_global_halt_no_post(
        self,
        *,
        confirmation: str,
        fresh_flat_confirmed: bool,
    ) -> None:
        if confirmation != "H11_V4_GMO_OPERATOR_RELOAD_NO_POST":
            raise V4GmoPersistenceError("v4 operator reload confirmation mismatch")
        if type(fresh_flat_confirmed) is not bool or not fresh_flat_confirmed:
            raise V4GmoPersistenceError("v4 operator reload requires fresh flat state")
        if self.active_cycle_count() != 0:
            raise V4GmoPersistenceError("v4 operator reload refused while cycle is active")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM metadata WHERE key IN "
                "('global_halt_latched', 'global_halt_reason', 'global_halt_at_utc')"
            )

    def clear_halted_cycle_no_post(
        self,
        *,
        cycle_ref: str,
        confirmation: str,
        fresh_flat_confirmed: bool,
        now_utc: datetime,
    ) -> V4GmoStoredCycle:
        if confirmation != "H11_V4_GMO_OPERATOR_RELOAD_NO_POST":
            raise V4GmoPersistenceError("v4 operator reload confirmation mismatch")
        if type(fresh_flat_confirmed) is not bool or not fresh_flat_confirmed:
            raise V4GmoPersistenceError("v4 operator reload requires fresh flat state")
        cycle = self.load_cycle(cycle_ref)
        if cycle.state is not V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED:
            raise V4GmoPersistenceError("v4 cycle is not halted for operator review")
        return self.transition(
            cycle_ref=cycle_ref,
            target=V4GmoCycleState.OPERATOR_RELOAD_CLEARED,
            event_category="OPERATOR_RELOAD_CLEARED_NO_POST",
            now_utc=now_utc,
            filled_size=0,
            protected_size=0,
        )

    @staticmethod
    def _halt_latched_with_connection(connection: sqlite3.Connection) -> bool:
        global_row = connection.execute(
            "SELECT value FROM metadata WHERE key = 'global_halt_latched'"
        ).fetchone()
        if global_row is not None and global_row["value"] == "true":
            return True
        row = connection.execute(
            "SELECT 1 FROM cycles WHERE state = ? LIMIT 1",
            (V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED.value,),
        ).fetchone()
        return row is not None

    def verify_journal(self) -> V4GmoJournalSummary:
        with self._connect() as connection:
            events = connection.execute(
                "SELECT * FROM safe_events ORDER BY sequence"
            ).fetchall()
            attempt_row = connection.execute(
                "SELECT COUNT(*) AS count FROM action_attempts"
            ).fetchone()
            attempts = connection.execute(
                "SELECT cycle_ref, action_kind, outcome_safe_label FROM action_attempts"
            ).fetchall()
            cycles = connection.execute(
                "SELECT cycle_ref, state FROM cycles"
            ).fetchall()
        previous = "GENESIS"
        final_state = "EMPTY"
        final_state_by_cycle: dict[str, str] = {}
        for expected_sequence, row in enumerate(events, start=1):
            expected = _event_digest(
                sequence=int(row["sequence"]),
                cycle_ref=row["cycle_ref"],
                event_category=row["event_category"],
                state_safe_label=row["state_safe_label"],
                previous_digest=previous,
            )
            if (
                row["sequence"] != expected_sequence
                or row["previous_digest"] != previous
                or row["digest"] != expected
            ):
                raise V4GmoPersistenceError("v4 safe journal verification failed")
            previous = row["digest"]
            final_state = row["state_safe_label"]
            final_state_by_cycle[str(row["cycle_ref"])] = str(row["state_safe_label"])
        if set(final_state_by_cycle) != {str(row["cycle_ref"]) for row in cycles}:
            raise V4GmoPersistenceError("v4 cycle journal coverage failed")
        if any(
            final_state_by_cycle[str(row["cycle_ref"])] != str(row["state"])
            for row in cycles
        ):
            raise V4GmoPersistenceError("v4 cycle state journal mismatch")
        event_categories = [
            (row["cycle_ref"], row["event_category"]) for row in events
        ]
        for attempt in attempts:
            expected_start = f"{attempt['action_kind']}_ATTEMPT_STARTED"
            expected_outcome = f"{attempt['action_kind']}_{attempt['outcome_safe_label']}"
            cycle_ref = attempt["cycle_ref"]
            start_matches = event_categories.count((cycle_ref, expected_start))
            outcome_categories = [
                category
                for event_cycle_ref, category in event_categories
                if event_cycle_ref == cycle_ref
                and category.startswith(f"{attempt['action_kind']}_")
                and category != expected_start
            ]
            outcome_matches = outcome_categories.count(expected_outcome)
            outcome_pending = attempt["outcome_safe_label"] == "ATTEMPT_STARTED"
            if start_matches != 1 or (
                outcome_pending and outcome_categories
            ) or (
                not outcome_pending
                and (outcome_matches != 1 or len(outcome_categories) != 1)
            ):
                raise V4GmoPersistenceError("v4 action journal verification failed")
        start_count = sum(
            event_category.endswith("_ATTEMPT_STARTED")
            for _, event_category in event_categories
        )
        if start_count != int(attempt_row["count"]):
            raise V4GmoPersistenceError("v4 action journal verification failed")
        return V4GmoJournalSummary(
            valid=True,
            event_count=len(events),
            action_attempt_count=int(attempt_row["count"]),
            final_state=final_state,
        )

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        *,
        cycle_ref: str,
        event_category: str,
        state: V4GmoCycleState,
    ) -> None:
        _validate_safe_label(event_category)
        row = connection.execute(
            "SELECT sequence, digest FROM safe_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        sequence = 1 if row is None else int(row["sequence"]) + 1
        previous = "GENESIS" if row is None else row["digest"]
        digest = _event_digest(
            sequence=sequence,
            cycle_ref=cycle_ref,
            event_category=event_category,
            state_safe_label=state.value,
            previous_digest=previous,
        )
        connection.execute(
            """
            INSERT INTO safe_events(
                sequence, cycle_ref, event_category, state_safe_label,
                previous_digest, digest
            ) VALUES(?, ?, ?, ?, ?, ?)
            """,
            (sequence, cycle_ref, event_category, state.value, previous, digest),
        )


def _stored_cycle(row: sqlite3.Row) -> V4GmoStoredCycle:
    return V4GmoStoredCycle(
        cycle_ref=row["cycle_ref"],
        signal_fingerprint=row["signal_fingerprint"],
        policy_config_hash=row["policy_config_hash"],
        state=V4GmoCycleState(row["state"]),
        side=row["side"],
        requested_size=int(row["requested_size"]),
        filled_size=int(row["filled_size"]),
        protected_size=int(row["protected_size"]),
        unprotected_since_utc=row["unprotected_since_utc"],
        entry_day_jst=row["entry_day_jst"],
        created_at_utc=row["created_at_utc"],
        updated_at_utc=row["updated_at_utc"],
        halt_reason=row["halt_reason"],
    )


def _timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise V4GmoPersistenceError("v4 timestamp must be timezone-aware")
    return value.isoformat()


def _validate_safe_label(value: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 120:
        raise V4GmoPersistenceError("v4 safe label is invalid")
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    if any(character not in allowed for character in value):
        raise V4GmoPersistenceError("v4 safe label is invalid")


def _validate_generation_label(value: str) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 128
        or "\n" in value
        or "\r" in value
    ):
        raise V4GmoPersistenceError("v4 generation label is invalid")
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-"
    if any(character not in allowed for character in value):
        raise V4GmoPersistenceError("v4 generation label is invalid")


def _event_digest(
    *,
    sequence: int,
    cycle_ref: str,
    event_category: str,
    state_safe_label: str,
    previous_digest: str,
) -> str:
    canonical = "|".join(
        (
            str(sequence),
            cycle_ref,
            event_category,
            state_safe_label,
            previous_digest,
        )
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
