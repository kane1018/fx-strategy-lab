"""Durable fake-outcome restart-safe time-exit state machine.

This module has no credential, network, broker, order-builder, executor, or
actual transport dependency. It records synthetic test outcomes only; a future
position-specific close implementation must be a separately reviewed module.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from app.services.h11_v4_unattended_exit_recovery_no_post import (
    V4ExitRecoverySnapshot,
    V4ExitRecoveryStatus,
    evaluate_exit_recovery,
)

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


class V4RestartSafeExitStatus(str, Enum):
    MONITORING_NO_WRITE = "MONITORING_NO_WRITE"
    COMPLETE_FLAT_NO_WRITE = "COMPLETE_FLAT_NO_WRITE"
    FAKE_EXIT_COMPLETED_NO_POST = "FAKE_EXIT_COMPLETED_NO_POST"
    PERSISTENT_HALT_NO_RETRY = "PERSISTENT_HALT_NO_RETRY"
    STORAGE_UNAVAILABLE_NO_POST = "STORAGE_UNAVAILABLE_NO_POST"


@dataclass(frozen=True)
class V4FakePositionSpecificExitResult:
    """Synthetic local test input, not an executor result or transport output."""

    fake_only: bool
    result_known: bool
    flat_reconciled: bool
    broker_write: bool = False
    actual_post_count: int = 0


@dataclass(frozen=True)
class V4RestartSafeExitDecision:
    status: V4RestartSafeExitStatus
    persistent_halt: bool
    fake_outcome_applied: bool
    broker_write: bool = False
    actual_post_count: int = 0

    def __bool__(self) -> bool:
        """A local state result can never become a transport allow value."""

        return False


class V4RestartSafeExitStore:
    """SQLite-backed, generation-bound one-use scope journal."""

    def __init__(self, database: Path) -> None:
        self._database = database
        try:
            self._initialize()
            self._available = True
        except (OSError, sqlite3.Error):
            self._available = False

    def run_once(
        self,
        *,
        snapshot: V4ExitRecoverySnapshot,
        fake_result: V4FakePositionSpecificExitResult,
        reviewed_files_digest: str,
        generation_digest: str,
    ) -> V4RestartSafeExitDecision:
        """Apply one fake outcome; never invokes injected or external code."""

        if not self._available:
            return V4RestartSafeExitDecision(
                status=V4RestartSafeExitStatus.STORAGE_UNAVAILABLE_NO_POST,
                persistent_halt=False,
                fake_outcome_applied=False,
            )
        try:
            return self._run_once(
                snapshot=snapshot,
                fake_result=fake_result,
                reviewed_files_digest=reviewed_files_digest,
                generation_digest=generation_digest,
            )
        except (OSError, sqlite3.Error):
            return V4RestartSafeExitDecision(
                status=V4RestartSafeExitStatus.STORAGE_UNAVAILABLE_NO_POST,
                persistent_halt=False,
                fake_outcome_applied=False,
            )

    def _run_once(
        self,
        *,
        snapshot: V4ExitRecoverySnapshot,
        fake_result: V4FakePositionSpecificExitResult,
        reviewed_files_digest: str,
        generation_digest: str,
    ) -> V4RestartSafeExitDecision:
        if not _SHA256.fullmatch(reviewed_files_digest) or not _SHA256.fullmatch(
            generation_digest
        ):
            return self._persistent_halt(
                snapshot.cycle_binding_digest,
                reviewed_files_digest,
                generation_digest,
            )
        existing = self._scope(snapshot.cycle_binding_digest)
        if existing is not None:
            status, stored_reviewed, stored_generation = existing
            if (
                stored_reviewed != reviewed_files_digest
                or stored_generation != generation_digest
            ):
                return self._persistent_halt(
                    snapshot.cycle_binding_digest,
                    reviewed_files_digest,
                    generation_digest,
                )
            if status == "COMPLETE":
                return V4RestartSafeExitDecision(
                    status=V4RestartSafeExitStatus.COMPLETE_FLAT_NO_WRITE,
                    persistent_halt=False,
                    fake_outcome_applied=False,
                )
            return self._persistent_halt(
                snapshot.cycle_binding_digest,
                reviewed_files_digest,
                generation_digest,
            )
        recovery = evaluate_exit_recovery(snapshot)
        if recovery.status is V4ExitRecoveryStatus.COMPLETE_FLAT_NO_WRITE:
            return V4RestartSafeExitDecision(
                status=V4RestartSafeExitStatus.COMPLETE_FLAT_NO_WRITE,
                persistent_halt=False,
                fake_outcome_applied=False,
            )
        if recovery.status is V4ExitRecoveryStatus.MONITOR_TICK_SAFE_NO_WRITE:
            return V4RestartSafeExitDecision(
                status=V4RestartSafeExitStatus.MONITORING_NO_WRITE,
                persistent_halt=False,
                fake_outcome_applied=False,
            )
        if recovery.status is not V4ExitRecoveryStatus.EXIT_SCOPE_REQUIRED_NO_WRITE:
            return self._persistent_halt(
                snapshot.cycle_binding_digest,
                reviewed_files_digest,
                generation_digest,
            )
        if not self._claim_once(
            snapshot.cycle_binding_digest, reviewed_files_digest, generation_digest
        ):
            return self._persistent_halt(
                snapshot.cycle_binding_digest,
                reviewed_files_digest,
                generation_digest,
            )
        if (
            fake_result.fake_only is not True
            or fake_result.broker_write is not False
            or fake_result.actual_post_count != 0
            or fake_result.result_known is not True
            or fake_result.flat_reconciled is not True
        ):
            return self._persistent_halt(
                snapshot.cycle_binding_digest,
                reviewed_files_digest,
                generation_digest,
            )
        if not self._mark_complete(snapshot.cycle_binding_digest):
            return self._persistent_halt(
                snapshot.cycle_binding_digest,
                reviewed_files_digest,
                generation_digest,
            )
        return V4RestartSafeExitDecision(
            status=V4RestartSafeExitStatus.FAKE_EXIT_COMPLETED_NO_POST,
            persistent_halt=False,
            fake_outcome_applied=True,
        )

    def scope_status(self, *, cycle_binding_digest: str) -> str | None:
        scope = self._scope(cycle_binding_digest)
        return None if scope is None else scope[0]

    def _scope(self, cycle_binding_digest: str) -> tuple[str, str, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT status, reviewed_files_digest, generation_digest
                FROM restart_safe_exit_scopes WHERE cycle_binding_digest=?
                """,
                (cycle_binding_digest,),
            ).fetchone()
        if row is None:
            return None
        return (str(row[0]), str(row[1]), str(row[2]))

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS restart_safe_exit_scopes (
                    cycle_binding_digest TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK(status IN ('CLAIMED', 'COMPLETE', 'HALTED')),
                    reviewed_files_digest TEXT NOT NULL,
                    generation_digest TEXT NOT NULL,
                    claimed_at_utc TEXT NOT NULL
                )
                """
            )

    def _claim_once(
        self,
        cycle_binding_digest: str,
        reviewed_files_digest: str,
        generation_digest: str,
    ) -> bool:
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO restart_safe_exit_scopes VALUES (?, 'CLAIMED', ?, ?, ?)",
                    (
                        cycle_binding_digest,
                        reviewed_files_digest,
                        generation_digest,
                        datetime.now(UTC).isoformat(),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def _mark_complete(self, cycle_binding_digest: str) -> bool:
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE restart_safe_exit_scopes SET status='COMPLETE' "
                "WHERE cycle_binding_digest=? AND status='CLAIMED'",
                (cycle_binding_digest,),
            )
        return result.rowcount == 1

    def _persistent_halt(
        self,
        cycle_binding_digest: str,
        reviewed_files_digest: str,
        generation_digest: str,
    ) -> V4RestartSafeExitDecision:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO restart_safe_exit_scopes VALUES (?, 'HALTED', ?, ?, ?)
                ON CONFLICT(cycle_binding_digest) DO UPDATE SET status='HALTED'
                """,
                (
                    cycle_binding_digest,
                    reviewed_files_digest,
                    generation_digest,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return _halt_decision()

    def _connect(self) -> sqlite3.Connection:
        self._database.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self._database)


def _halt_decision() -> V4RestartSafeExitDecision:
    return V4RestartSafeExitDecision(
        status=V4RestartSafeExitStatus.PERSISTENT_HALT_NO_RETRY,
        persistent_halt=True,
        fake_outcome_applied=False,
    )
