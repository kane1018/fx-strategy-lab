"""Pure integrated unattended lifecycle decision with no live connection.

The decision is evidence for a separate review. It is not a transport allow
value, owns no secret material or client, and cannot issue an entry or exit
permit.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from app.h11_auto.runtime_safety import PhaseBRiskPolicy
from app.services.h11_v4_unattended_account_snapshot_evidence_no_post import (
    V4BoundAccountSnapshotEvidenceNoPost,
    V4BoundAccountSnapshotEvidenceNoPostError,
    validate_bound_account_snapshot_evidence_no_post,
)
from app.services.h11_v4_unattended_commissioning_no_post import (
    V4CommissioningArtifact,
    V4CommissioningStatus,
    V4PredecessorCanaryCompletionArtifact,
    V4ShadowEvidenceArtifact,
    commissioning_evidence_is_canonical,
    commissioning_historical_evidence_is_canonical,
    evaluate_commissioning,
)
from app.services.h11_v4_unattended_operational_readiness_no_post import (
    V4OperationalReadinessEvidenceNoPost,
    V4OperationalReadinessNoPostError,
    validate_operational_readiness_evidence_no_post,
)

_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_EVIDENCE_SCHEMA = "H11_V4_UNATTENDED_CONTROLLER_EVIDENCE_NO_POST_V2"
_ACTUAL_INTEGRATION_IMPLEMENTED = False
_ZERO_DIGEST = "sha256:" + ("0" * 64)


class V4IntegratedControllerError(ValueError):
    """Fixed safe failure for invalid lifecycle evidence."""


class V4IntegratedControllerStatus(str, Enum):
    IDLE_NO_POST = "IDLE_NO_POST"
    OPERATIONAL_DEGRADED_NO_POST = "OPERATIONAL_DEGRADED_NO_POST"
    ENTRY_BLOCKED_NO_POST = "ENTRY_BLOCKED_NO_POST"
    ENTRY_SCOPE_REVIEW_REQUIRED_NO_POST = "ENTRY_SCOPE_REVIEW_REQUIRED_NO_POST"
    PROTECTED_POSITION_MONITORING_NO_POST = "PROTECTED_POSITION_MONITORING_NO_POST"
    EXIT_SCOPE_REVIEW_REQUIRED_NO_POST = "EXIT_SCOPE_REVIEW_REQUIRED_NO_POST"
    PERSISTENT_HALT_NO_POST = "PERSISTENT_HALT_NO_POST"
    STORAGE_UNAVAILABLE_NO_POST = "STORAGE_UNAVAILABLE_NO_POST"


@dataclass(frozen=True)
class V4IntegratedControllerEvidence:
    schema: str
    reviewed_files_digest: str
    generation_digest: str
    cycle_binding_digest: str
    expected_cycle_binding_digest: str
    protection_cycle_binding_digest: str
    scheduled_exit_cycle_binding_digest: str
    expected_risk_policy_digest: str
    arm_reviewed_files_digest: str
    arm_generation_digest: str
    arm_armed: bool
    process_lock_clear: bool
    persistent_halt_clear: bool
    dead_man_clear: bool
    heartbeat_chain_clear: bool
    notification_ready: bool
    market_open: bool
    formal_signal_actionable: bool
    quote_fresh: bool
    spread_within_limit: bool
    account_snapshot_known: bool
    account_flat: bool
    active_orders_zero: bool
    exact_protection_confirmed: bool
    protection_observed_current: bool
    position_ownership_confirmed: bool
    scheduled_exit_due: bool
    transport_action_pending: bool
    result_unknown: bool
    daily_entry_count: int
    daily_loss_jpy: int
    monthly_loss_jpy: int
    consecutive_losses: int
    observed_at_utc: str
    valid_until_utc: str
    account_snapshot_evidence_digest: str
    operational_readiness_evidence_digest: str
    artifact_digest: str


def build_integrated_controller_evidence(
    *,
    reviewed_files_digest: str,
    generation_digest: str,
    cycle_binding_digest: str,
    expected_cycle_binding_digest: str,
    protection_cycle_binding_digest: str,
    scheduled_exit_cycle_binding_digest: str,
    expected_risk_policy_digest: str,
    arm_reviewed_files_digest: str,
    arm_generation_digest: str,
    arm_armed: bool,
    process_lock_clear: bool,
    persistent_halt_clear: bool,
    dead_man_clear: bool,
    heartbeat_chain_clear: bool,
    notification_ready: bool,
    market_open: bool,
    formal_signal_actionable: bool,
    quote_fresh: bool,
    spread_within_limit: bool,
    account_snapshot_known: bool,
    account_flat: bool,
    active_orders_zero: bool,
    exact_protection_confirmed: bool,
    protection_observed_current: bool,
    position_ownership_confirmed: bool,
    scheduled_exit_due: bool,
    transport_action_pending: bool,
    result_unknown: bool,
    daily_entry_count: int,
    daily_loss_jpy: int,
    monthly_loss_jpy: int,
    consecutive_losses: int,
    observed_at_utc: str,
    valid_until_utc: str,
    account_snapshot_evidence_digest: str = _ZERO_DIGEST,
    operational_readiness_evidence_digest: str = _ZERO_DIGEST,
) -> V4IntegratedControllerEvidence:
    payload: dict[str, object] = {
        "schema": _EVIDENCE_SCHEMA,
        "reviewed_files_digest": reviewed_files_digest,
        "generation_digest": generation_digest,
        "cycle_binding_digest": cycle_binding_digest,
        "expected_cycle_binding_digest": expected_cycle_binding_digest,
        "protection_cycle_binding_digest": protection_cycle_binding_digest,
        "scheduled_exit_cycle_binding_digest": scheduled_exit_cycle_binding_digest,
        "expected_risk_policy_digest": expected_risk_policy_digest,
        "arm_reviewed_files_digest": arm_reviewed_files_digest,
        "arm_generation_digest": arm_generation_digest,
        "arm_armed": arm_armed,
        "process_lock_clear": process_lock_clear,
        "persistent_halt_clear": persistent_halt_clear,
        "dead_man_clear": dead_man_clear,
        "heartbeat_chain_clear": heartbeat_chain_clear,
        "notification_ready": notification_ready,
        "market_open": market_open,
        "formal_signal_actionable": formal_signal_actionable,
        "quote_fresh": quote_fresh,
        "spread_within_limit": spread_within_limit,
        "account_snapshot_known": account_snapshot_known,
        "account_flat": account_flat,
        "active_orders_zero": active_orders_zero,
        "exact_protection_confirmed": exact_protection_confirmed,
        "protection_observed_current": protection_observed_current,
        "position_ownership_confirmed": position_ownership_confirmed,
        "scheduled_exit_due": scheduled_exit_due,
        "transport_action_pending": transport_action_pending,
        "result_unknown": result_unknown,
        "daily_entry_count": daily_entry_count,
        "daily_loss_jpy": daily_loss_jpy,
        "monthly_loss_jpy": monthly_loss_jpy,
        "consecutive_losses": consecutive_losses,
        "observed_at_utc": observed_at_utc,
        "valid_until_utc": valid_until_utc,
        "account_snapshot_evidence_digest": account_snapshot_evidence_digest,
        "operational_readiness_evidence_digest": operational_readiness_evidence_digest,
    }
    return V4IntegratedControllerEvidence(
        **payload,
        artifact_digest=_canonical_digest(payload),
    )


@dataclass(frozen=True)
class V4IntegratedControllerSnapshot:
    reviewed_files_digest: str
    generation_digest: str
    cycle_binding_digest: str
    expected_cycle_binding_digest: str
    risk_policy: PhaseBRiskPolicy
    expected_risk_policy_digest: str
    commissioning_artifact: V4CommissioningArtifact
    commissioning_shadow: V4ShadowEvidenceArtifact
    predecessor_completion: V4PredecessorCanaryCompletionArtifact | None
    account_snapshot_evidence: V4BoundAccountSnapshotEvidenceNoPost | None
    operational_readiness_evidence: V4OperationalReadinessEvidenceNoPost | None
    evidence: V4IntegratedControllerEvidence

    def __getattr__(self, name: str) -> object:
        evidence_fields = V4IntegratedControllerEvidence.__dataclass_fields__
        if name in evidence_fields:
            return getattr(self.evidence, name)
        raise AttributeError(name)


@dataclass(frozen=True)
class V4IntegratedControllerDecision:
    status: V4IntegratedControllerStatus
    blocked_reasons: tuple[str, ...]
    separate_review_required: bool
    persistent_halt: bool
    actual_integration_implemented: bool = False
    permit_issued: bool = False
    broker_post_authorized: bool = False
    broker_write: bool = False
    actual_post_count: int = 0

    def __post_init__(self) -> None:
        if (
            type(self.separate_review_required) is not bool
            or type(self.persistent_halt) is not bool
            or type(self.actual_integration_implemented) is not bool
            or type(self.permit_issued) is not bool
            or type(self.broker_post_authorized) is not bool
            or type(self.broker_write) is not bool
            or type(self.actual_post_count) is not int
            or self.actual_integration_implemented is not False
            or self.permit_issued is not False
            or self.broker_post_authorized is not False
            or self.broker_write is not False
            or self.actual_post_count != 0
        ):
            raise V4IntegratedControllerError("INTEGRATED_DECISION_LIVE_CLAIM_REFUSED")

    def __bool__(self) -> bool:
        return False

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "blocked_reasons": list(self.blocked_reasons),
            "separate_review_required": self.separate_review_required,
            "persistent_halt": self.persistent_halt,
            "actual_integration_implemented": False,
            "permit_issued": False,
            "broker_post_authorized": False,
            "broker_write": False,
            "actual_post_count": 0,
        }


class V4IntegratedControllerStore:
    """Durably record sanitized lifecycle status and persistent HALT."""

    def __init__(self, database: Path) -> None:
        self._database = database
        self._available = True
        try:
            if database.is_symlink():
                raise OSError
            database.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS integrated_controller_state (
                        generation_digest TEXT NOT NULL,
                        cycle_binding_digest TEXT NOT NULL,
                        reviewed_files_digest TEXT NOT NULL,
                        status TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL,
                        PRIMARY KEY (generation_digest, cycle_binding_digest)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS integrated_account_snapshot_consumption (
                        generation_digest TEXT NOT NULL,
                        evidence_digest TEXT NOT NULL,
                        consumed_at_utc TEXT NOT NULL,
                        PRIMARY KEY (generation_digest, evidence_digest)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS integrated_generation_halt (
                        generation_digest TEXT PRIMARY KEY,
                        reviewed_files_digest TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL
                    )
                    """
                )
        except (OSError, sqlite3.Error):
            self._available = False

    def evaluate_and_record(
        self, snapshot: V4IntegratedControllerSnapshot
    ) -> V4IntegratedControllerDecision:
        _validate_snapshot(snapshot)
        if not self._available:
            return _storage_unavailable()
        connection: sqlite3.Connection | None = None
        try:
            connection = self._connect()
            connection.execute("BEGIN IMMEDIATE")
            generation_halt = connection.execute(
                """
                SELECT reviewed_files_digest, reason
                FROM integrated_generation_halt
                WHERE generation_digest=?
                """,
                (snapshot.generation_digest,),
            ).fetchone()
            if generation_halt is not None:
                connection.rollback()
                if str(generation_halt[0]) != snapshot.reviewed_files_digest:
                    return _halt("PERSISTED_HALT_REVIEW_BOUNDARY_MISMATCH")
                return _halt(
                    "PERSISTENT_GENERATION_HALT_LATCHED",
                    _safe_persisted_halt_reason(generation_halt[1]),
                )
            legacy_halt = connection.execute(
                """
                SELECT 1
                FROM integrated_controller_state
                WHERE generation_digest=? AND status=?
                LIMIT 1
                """,
                (
                    snapshot.generation_digest,
                    V4IntegratedControllerStatus.PERSISTENT_HALT_NO_POST.value,
                ),
            ).fetchone()
            if legacy_halt is not None:
                decision = _halt("PERSISTENT_LEGACY_GENERATION_HALT_LATCHED")
                self._record_generation_halt(connection, snapshot, decision)
                connection.commit()
                return decision
            previous = self._load(connection, snapshot)
            if previous is not None:
                previous_reviewed, previous_status = previous
                if previous_reviewed != snapshot.reviewed_files_digest:
                    decision = _halt("PERSISTED_REVIEW_BOUNDARY_MISMATCH")
                    self._record(connection, snapshot, decision)
                    self._record_generation_halt(connection, snapshot, decision)
                    connection.commit()
                    return decision
                if previous_status == V4IntegratedControllerStatus.PERSISTENT_HALT_NO_POST.value:
                    decision = _halt("PERSISTENT_HALT_LATCHED")
                    self._record_generation_halt(connection, snapshot, decision)
                    connection.commit()
                    return decision
            if snapshot.account_snapshot_known:
                consumed = connection.execute(
                    """
                    INSERT OR IGNORE INTO integrated_account_snapshot_consumption
                    VALUES (?, ?, ?)
                    """,
                    (
                        snapshot.generation_digest,
                        snapshot.account_snapshot_evidence_digest,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                if consumed.rowcount != 1:
                    decision = _halt("ACCOUNT_SNAPSHOT_EVIDENCE_REUSED")
                    self._record(connection, snapshot, decision)
                    self._record_generation_halt(connection, snapshot, decision)
                    connection.commit()
                    return decision
            decision = evaluate_integrated_controller(snapshot)
            self._record(connection, snapshot, decision)
            if decision.persistent_halt:
                self._record_generation_halt(connection, snapshot, decision)
            connection.commit()
            return decision
        except (OSError, sqlite3.Error):
            if connection is not None:
                connection.rollback()
            return _storage_unavailable()
        finally:
            if connection is not None:
                connection.close()

    def _load(
        self,
        connection: sqlite3.Connection,
        snapshot: V4IntegratedControllerSnapshot,
    ) -> tuple[str, str] | None:
        row = connection.execute(
            """
            SELECT reviewed_files_digest, status
            FROM integrated_controller_state
            WHERE generation_digest=? AND cycle_binding_digest=?
            """,
            (snapshot.generation_digest, snapshot.cycle_binding_digest),
        ).fetchone()
        if row is None:
            return None
        return str(row[0]), str(row[1])

    def _record(
        self,
        connection: sqlite3.Connection,
        snapshot: V4IntegratedControllerSnapshot,
        decision: V4IntegratedControllerDecision,
    ) -> None:
        connection.execute(
            """
            INSERT INTO integrated_controller_state VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(generation_digest, cycle_binding_digest)
            DO UPDATE SET
                reviewed_files_digest=excluded.reviewed_files_digest,
                status=CASE
                    WHEN integrated_controller_state.status=?
                    THEN integrated_controller_state.status
                    ELSE excluded.status
                END,
                updated_at_utc=excluded.updated_at_utc
            """,
            (
                snapshot.generation_digest,
                snapshot.cycle_binding_digest,
                snapshot.reviewed_files_digest,
                decision.status.value,
                datetime.now(UTC).isoformat(),
                V4IntegratedControllerStatus.PERSISTENT_HALT_NO_POST.value,
            ),
        )

    def _record_generation_halt(
        self,
        connection: sqlite3.Connection,
        snapshot: V4IntegratedControllerSnapshot,
        decision: V4IntegratedControllerDecision,
    ) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO integrated_generation_halt VALUES (?, ?, ?, ?)
            """,
            (
                snapshot.generation_digest,
                snapshot.reviewed_files_digest,
                decision.blocked_reasons[0],
                datetime.now(UTC).isoformat(),
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database)


def evaluate_integrated_controller(
    snapshot: V4IntegratedControllerSnapshot,
) -> V4IntegratedControllerDecision:
    """Evaluate one sanitized lifecycle snapshot without issuing an action."""

    _validate_snapshot(snapshot)
    if snapshot.risk_policy.digest != snapshot.expected_risk_policy_digest:
        return _halt("RISK_POLICY_BINDING_MISMATCH")
    integrity_blockers = _review_evidence_integrity_blockers(snapshot)
    if integrity_blockers:
        return _halt(*integrity_blockers)
    if snapshot.cycle_binding_digest != snapshot.expected_cycle_binding_digest:
        return _halt("CYCLE_BINDING_MISMATCH")
    if not snapshot.persistent_halt_clear:
        return _halt("PERSISTENT_HALT_NOT_CLEAR")
    if snapshot.result_unknown:
        return _halt("RESULT_UNKNOWN")
    if snapshot.transport_action_pending:
        return _halt("TRANSPORT_ACTION_PENDING")
    if not snapshot.account_snapshot_known:
        return _halt("ACCOUNT_SNAPSHOT_UNKNOWN")
    if not snapshot.account_flat:
        return _evaluate_open_position(snapshot)
    if not snapshot.active_orders_zero:
        return _halt("FLAT_WITH_ACTIVE_ORDERS")
    operational_blockers = _operational_blockers(snapshot)
    if not snapshot.formal_signal_actionable:
        if operational_blockers:
            return _decision(
                V4IntegratedControllerStatus.OPERATIONAL_DEGRADED_NO_POST,
                blocked_reasons=operational_blockers,
            )
        return _decision(V4IntegratedControllerStatus.IDLE_NO_POST)
    blockers = _entry_blockers(snapshot)
    if blockers:
        return _decision(
            V4IntegratedControllerStatus.ENTRY_BLOCKED_NO_POST,
            blocked_reasons=blockers,
        )
    return _decision(
        V4IntegratedControllerStatus.ENTRY_SCOPE_REVIEW_REQUIRED_NO_POST,
        separate_review_required=True,
    )


def _evaluate_open_position(
    snapshot: V4IntegratedControllerSnapshot,
) -> V4IntegratedControllerDecision:
    if snapshot.active_orders_zero:
        return _halt("OPEN_POSITION_WITHOUT_ACTIVE_PROTECTION")
    if (
        not snapshot.exact_protection_confirmed
        or not snapshot.protection_observed_current
        or not snapshot.position_ownership_confirmed
    ):
        return _halt("OPEN_POSITION_NOT_EXACTLY_PROTECTED")
    if (
        snapshot.protection_cycle_binding_digest != snapshot.cycle_binding_digest
        or snapshot.scheduled_exit_cycle_binding_digest != snapshot.cycle_binding_digest
    ):
        return _halt("OPEN_POSITION_CYCLE_BINDING_MISMATCH")
    review_blockers = _review_boundary_blockers(
        snapshot, require_commissioning_ready=True
    )
    if review_blockers:
        return _halt(*review_blockers)
    operational_blockers = _operational_blockers(snapshot)
    if operational_blockers:
        return _halt(*operational_blockers)
    if snapshot.scheduled_exit_due:
        return _decision(
            V4IntegratedControllerStatus.EXIT_SCOPE_REVIEW_REQUIRED_NO_POST,
            separate_review_required=True,
        )
    return _decision(V4IntegratedControllerStatus.PROTECTED_POSITION_MONITORING_NO_POST)


def _entry_blockers(snapshot: V4IntegratedControllerSnapshot) -> tuple[str, ...]:
    reasons: list[str] = []
    reasons.extend(_review_boundary_blockers(snapshot, require_commissioning_ready=True))
    if not snapshot.arm_armed:
        reasons.append("PERSISTENT_ARM_NOT_CLEAR")
    reasons.extend(_operational_blockers(snapshot))
    if not snapshot.market_open:
        reasons.append("MARKET_NOT_OPEN")
    if not snapshot.quote_fresh:
        reasons.append("QUOTE_NOT_FRESH")
    if not snapshot.spread_within_limit:
        reasons.append("SPREAD_LIMIT_EXCEEDED")
    policy = snapshot.risk_policy
    if snapshot.daily_entry_count >= policy.maximum_entries_per_day:
        reasons.append("DAILY_ENTRY_LIMIT_REACHED")
    if snapshot.daily_loss_jpy >= policy.daily_loss_limit_jpy:
        reasons.append("DAILY_REALIZED_LOSS_LIMIT_REACHED")
    if snapshot.monthly_loss_jpy >= policy.monthly_loss_limit_jpy:
        reasons.append("MONTHLY_REALIZED_LOSS_LIMIT_REACHED")
    if snapshot.consecutive_losses >= policy.maximum_consecutive_losses:
        reasons.append("CONSECUTIVE_LOSS_LIMIT_REACHED")
    if _ACTUAL_INTEGRATION_IMPLEMENTED is not True:
        reasons.append("ACTUAL_INTEGRATION_STATE_INVALID")
    return tuple(dict.fromkeys(reasons))


def _review_boundary_blockers(
    snapshot: V4IntegratedControllerSnapshot,
    *,
    require_commissioning_ready: bool,
) -> tuple[str, ...]:
    reasons = list(_review_evidence_integrity_blockers(snapshot))
    if reasons:
        return tuple(reasons)
    artifact = snapshot.commissioning_artifact
    canonical = commissioning_evidence_is_canonical(
        artifact,
        snapshot.commissioning_shadow,
        snapshot.predecessor_completion,
    )
    if not canonical:
        reasons.append("COMMISSIONING_EVIDENCE_INVALID")
        return tuple(reasons)
    commissioning = evaluate_commissioning(
        artifact,
        snapshot.commissioning_shadow,
        snapshot.predecessor_completion,
    )
    if (
        require_commissioning_ready
        and commissioning.status is not V4CommissioningStatus.READY_FOR_SEPARATE_LIVE_REVIEW
    ):
        reasons.append("COMMISSIONING_NOT_READY")
    return tuple(reasons)


def _review_evidence_integrity_blockers(
    snapshot: V4IntegratedControllerSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        snapshot.arm_reviewed_files_digest != snapshot.reviewed_files_digest
        or snapshot.arm_generation_digest != snapshot.generation_digest
    ):
        reasons.append("ARM_REVIEW_BOUNDARY_MISMATCH")
    artifact = snapshot.commissioning_artifact
    if (
        artifact.reviewed_files_digest != snapshot.reviewed_files_digest
        or artifact.generation_digest != snapshot.generation_digest
        or artifact.shadow_reviewed_files_digest != snapshot.reviewed_files_digest
        or artifact.shadow_generation_digest != snapshot.generation_digest
    ):
        reasons.append("COMMISSIONING_REVIEW_BOUNDARY_MISMATCH")
    historical_canonical = commissioning_historical_evidence_is_canonical(
        artifact,
        snapshot.commissioning_shadow,
        snapshot.predecessor_completion,
    )
    if not historical_canonical:
        reasons.append("COMMISSIONING_HISTORICAL_EVIDENCE_INVALID")
        return tuple(reasons)
    if artifact.architecture_review_clear is not True:
        reasons.append("ARCHITECTURE_REVIEW_NOT_CLEAR")
    if artifact.safety_review_clear is not True:
        reasons.append("SAFETY_REVIEW_NOT_CLEAR")
    if artifact.operations_review_clear is not True:
        reasons.append("OPERATIONS_REVIEW_NOT_CLEAR")
    return tuple(reasons)


def _operational_blockers(snapshot: V4IntegratedControllerSnapshot) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.process_lock_clear:
        reasons.append("PROCESS_LOCK_NOT_CLEAR")
    if not snapshot.dead_man_clear:
        reasons.append("DEAD_MAN_NOT_CLEAR")
    if not snapshot.heartbeat_chain_clear:
        reasons.append("HEARTBEAT_CHAIN_NOT_CLEAR")
    if not snapshot.notification_ready:
        reasons.append("NOTIFICATION_NOT_READY")
    return tuple(reasons)


def _validate_snapshot(snapshot: V4IntegratedControllerSnapshot) -> None:
    if type(snapshot) is not V4IntegratedControllerSnapshot:
        raise V4IntegratedControllerError("INTEGRATED_SNAPSHOT_INVALID")
    if type(snapshot.evidence) is not V4IntegratedControllerEvidence:
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_INVALID")
    _validate_evidence(snapshot.evidence)
    for digest in (
        snapshot.reviewed_files_digest,
        snapshot.generation_digest,
        snapshot.cycle_binding_digest,
        snapshot.expected_cycle_binding_digest,
    ):
        if not _SHA256.fullmatch(digest):
            raise V4IntegratedControllerError("INTEGRATED_SNAPSHOT_DIGEST_INVALID")
    if (
        type(snapshot.risk_policy) is not PhaseBRiskPolicy
        or type(snapshot.expected_risk_policy_digest) is not str
        or not _HEX64.fullmatch(snapshot.expected_risk_policy_digest)
    ):
        raise V4IntegratedControllerError("INTEGRATED_RISK_POLICY_INVALID")
    evidence = snapshot.evidence
    if (
        evidence.reviewed_files_digest != snapshot.reviewed_files_digest
        or evidence.generation_digest != snapshot.generation_digest
        or evidence.cycle_binding_digest != snapshot.cycle_binding_digest
        or evidence.expected_cycle_binding_digest
        != snapshot.expected_cycle_binding_digest
        or evidence.expected_risk_policy_digest
        != snapshot.expected_risk_policy_digest
    ):
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_BINDING_MISMATCH")
    if (
        type(snapshot.commissioning_artifact) is not V4CommissioningArtifact
        or type(snapshot.commissioning_shadow) is not V4ShadowEvidenceArtifact
        or (
            snapshot.predecessor_completion is not None
            and type(snapshot.predecessor_completion)
            is not V4PredecessorCanaryCompletionArtifact
        )
    ):
        raise V4IntegratedControllerError("INTEGRATED_COMMISSIONING_EVIDENCE_INVALID")
    account_snapshot = snapshot.account_snapshot_evidence
    if evidence.account_snapshot_known:
        if type(account_snapshot) is not V4BoundAccountSnapshotEvidenceNoPost:
            raise V4IntegratedControllerError(
                "INTEGRATED_ACCOUNT_SNAPSHOT_EVIDENCE_REQUIRED"
            )
        try:
            validate_bound_account_snapshot_evidence_no_post(
                account_snapshot,
                expected_reviewed_files_digest=snapshot.reviewed_files_digest,
                expected_generation_digest=snapshot.generation_digest,
                expected_cycle_binding_digest=snapshot.cycle_binding_digest,
                now_utc=datetime.now(UTC),
            )
        except V4BoundAccountSnapshotEvidenceNoPostError as error:
            raise V4IntegratedControllerError(
                "INTEGRATED_ACCOUNT_SNAPSHOT_EVIDENCE_INVALID"
            ) from error
        if (
            account_snapshot.artifact_digest
            != evidence.account_snapshot_evidence_digest
            or account_snapshot.account_flat is not evidence.account_flat
            or account_snapshot.active_orders_zero
            is not evidence.active_orders_zero
        ):
            raise V4IntegratedControllerError(
                "INTEGRATED_ACCOUNT_SNAPSHOT_EVIDENCE_BINDING_MISMATCH"
            )
    elif account_snapshot is not None:
        raise V4IntegratedControllerError(
            "INTEGRATED_ACCOUNT_SNAPSHOT_EVIDENCE_UNEXPECTED"
        )
    operational = snapshot.operational_readiness_evidence
    if evidence.operational_readiness_evidence_digest != _ZERO_DIGEST:
        if type(operational) is not V4OperationalReadinessEvidenceNoPost:
            raise V4IntegratedControllerError(
                "INTEGRATED_OPERATIONAL_READINESS_EVIDENCE_REQUIRED"
            )
        try:
            validate_operational_readiness_evidence_no_post(
                operational,
                expected_reviewed_files_digest=snapshot.reviewed_files_digest,
                expected_generation_digest=snapshot.generation_digest,
                now_utc=datetime.now(UTC),
            )
        except V4OperationalReadinessNoPostError as error:
            raise V4IntegratedControllerError(
                "INTEGRATED_OPERATIONAL_READINESS_EVIDENCE_INVALID"
            ) from error
        if (
            operational.artifact_digest
            != evidence.operational_readiness_evidence_digest
            or operational.process_lock_clear is not evidence.process_lock_clear
            or operational.dead_man_clear is not evidence.dead_man_clear
            or operational.heartbeat_chain_clear is not evidence.heartbeat_chain_clear
            or operational.notification_ready is not evidence.notification_ready
        ):
            raise V4IntegratedControllerError(
                "INTEGRATED_OPERATIONAL_READINESS_EVIDENCE_BINDING_MISMATCH"
            )
    elif operational is not None or any(
        (
            evidence.process_lock_clear,
            evidence.dead_man_clear,
            evidence.heartbeat_chain_clear,
            evidence.notification_ready,
        )
    ):
        raise V4IntegratedControllerError(
            "INTEGRATED_OPERATIONAL_READINESS_EVIDENCE_UNEXPECTED"
        )


def _validate_evidence(
    evidence: V4IntegratedControllerEvidence,
) -> None:
    if evidence.schema != _EVIDENCE_SCHEMA:
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_SCHEMA_INVALID")
    payload = asdict(evidence)
    artifact_digest = payload.pop("artifact_digest")
    if (
        type(artifact_digest) is not str
        or not _SHA256.fullmatch(artifact_digest)
        or artifact_digest != _canonical_digest(payload)
    ):
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_DIGEST_INVALID")
    for digest in (
        evidence.reviewed_files_digest,
        evidence.generation_digest,
        evidence.cycle_binding_digest,
        evidence.expected_cycle_binding_digest,
        evidence.protection_cycle_binding_digest,
        evidence.scheduled_exit_cycle_binding_digest,
        evidence.arm_reviewed_files_digest,
        evidence.arm_generation_digest,
        evidence.account_snapshot_evidence_digest,
        evidence.operational_readiness_evidence_digest,
    ):
        if type(digest) is not str or not _SHA256.fullmatch(digest):
            raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_DIGEST_INVALID")
    if (
        type(evidence.expected_risk_policy_digest) is not str
        or not _HEX64.fullmatch(evidence.expected_risk_policy_digest)
    ):
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_POLICY_INVALID")
    boolean_values = (
        evidence.arm_armed,
        evidence.process_lock_clear,
        evidence.persistent_halt_clear,
        evidence.dead_man_clear,
        evidence.heartbeat_chain_clear,
        evidence.notification_ready,
        evidence.market_open,
        evidence.formal_signal_actionable,
        evidence.quote_fresh,
        evidence.spread_within_limit,
        evidence.account_snapshot_known,
        evidence.account_flat,
        evidence.active_orders_zero,
        evidence.exact_protection_confirmed,
        evidence.protection_observed_current,
        evidence.position_ownership_confirmed,
        evidence.scheduled_exit_due,
        evidence.transport_action_pending,
        evidence.result_unknown,
    )
    if any(type(value) is not bool for value in boolean_values):
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_BOOLEAN_INVALID")
    counters = (
        evidence.daily_entry_count,
        evidence.daily_loss_jpy,
        evidence.monthly_loss_jpy,
        evidence.consecutive_losses,
    )
    if any(type(value) is not int for value in counters):
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_COUNTER_INVALID")
    if (
        evidence.daily_entry_count < 0
        or evidence.daily_loss_jpy < 0
        or evidence.monthly_loss_jpy < 0
        or evidence.consecutive_losses < 0
        or (
            evidence.account_snapshot_known
            and evidence.account_snapshot_evidence_digest == _ZERO_DIGEST
        )
        or (
            not evidence.account_snapshot_known
            and evidence.account_snapshot_evidence_digest != _ZERO_DIGEST
        )
        or (
            evidence.operational_readiness_evidence_digest == _ZERO_DIGEST
            and any(
                (
                    evidence.process_lock_clear,
                    evidence.dead_man_clear,
                    evidence.heartbeat_chain_clear,
                    evidence.notification_ready,
                )
            )
        )
    ):
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_COUNTER_INVALID")
    observed = _parse_utc(evidence.observed_at_utc)
    valid_until = _parse_utc(evidence.valid_until_utc)
    evaluated = datetime.now(UTC)
    if (
        observed > evaluated
        or evaluated > valid_until
        or valid_until <= observed
        or (valid_until - observed).total_seconds() > 120
    ):
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_NOT_FRESH")


def _parse_utc(value: object) -> datetime:
    if type(value) is not str:
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_TIME_INVALID")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_TIME_INVALID") from None
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise V4IntegratedControllerError("INTEGRATED_EVIDENCE_TIME_INVALID")
    return parsed


def _safe_persisted_halt_reason(value: object) -> str:
    if (
        type(value) is str
        and 1 <= len(value) <= 128
        and re.fullmatch(r"[A-Z0-9_]+", value) is not None
    ):
        return value
    return "PERSISTED_HALT_REASON_INVALID"


def _canonical_digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _decision(
    status: V4IntegratedControllerStatus,
    *,
    blocked_reasons: tuple[str, ...] = (),
    separate_review_required: bool = False,
) -> V4IntegratedControllerDecision:
    return V4IntegratedControllerDecision(
        status=status,
        blocked_reasons=blocked_reasons,
        separate_review_required=separate_review_required,
        persistent_halt=False,
    )


def _halt(*reasons: str) -> V4IntegratedControllerDecision:
    return V4IntegratedControllerDecision(
        status=V4IntegratedControllerStatus.PERSISTENT_HALT_NO_POST,
        blocked_reasons=tuple(dict.fromkeys(reasons)),
        separate_review_required=False,
        persistent_halt=True,
    )


def _storage_unavailable() -> V4IntegratedControllerDecision:
    return V4IntegratedControllerDecision(
        status=V4IntegratedControllerStatus.STORAGE_UNAVAILABLE_NO_POST,
        blocked_reasons=("DURABLE_STATE_UNAVAILABLE",),
        separate_review_required=False,
        persistent_halt=False,
    )
