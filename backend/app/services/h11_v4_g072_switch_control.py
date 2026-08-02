"""G072 switch-only rearm contract and resident projection.

This module contains only sanitized state transitions and injected reader
contracts.  The real first activation reader is isolated in the dedicated
G072 activation script and is never called by the UI.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Protocol

G072_GENERATION_LABEL = "H11_AUTO_30M_20260802_G072"
G072_PERSISTENT_HALT_FILE = "g072-persistent-halt.json"
G072_RUNTIME_STATUS_FILE = "g072-runtime-status.json"
G072_RECONCILIATION_FILE = "g072-reconciliation-current.json"
G072_SWITCH_CAPABILITY_FILE = "g072-switch-control-capability.json"
G072_TRANSACTION_STARTED_FILE = "g072-atomic-activation.started.json"
G072_TRANSACTION_OUTCOME_FILE = "g072-atomic-activation.outcome.json"
G072_OPERATION_60_STARTED_FILE = "g072-operation-60.started.json"
G072_OPERATION_60_RESULT_FILE = "g072-operation-60.result.json"
G072_MAX_EVIDENCE_AGE_SECONDS = 60


class G072Error(ValueError):
    """Safe-label-only G072 failure."""


class G072ReconciliationState(str, Enum):
    REQUIRED = "REQUIRED"
    FRESH_FLAT = "FRESH_FLAT"
    FRESH_PROTECTED = "FRESH_PROTECTED"
    UNKNOWN = "UNKNOWN"


class G072EffectiveState(str, Enum):
    OFF = "OFF"
    ON_WAITING = "ON_WAITING"
    ON_EXIT_ONLY = "ON_EXIT_ONLY"
    EXIT_ONLY = "EXIT_ONLY"
    HALTED = "HALTED"


@dataclass(frozen=True)
class G072SanitizedSnapshot:
    latest_execution_count: int
    open_position_count: int
    active_order_count: int
    ownership_exact: bool = False
    quantity_matches: bool = False
    protection_confirmed: bool = False
    broker_get_count: int = 3
    private_api_read_count: int = 3
    credential_read_count: int = 1
    broker_write: bool = False
    broker_post_count: int = 0


@dataclass(frozen=True)
class G072EntryEvaluation:
    """Safe result supplied by the existing strategy artifact, never an order."""

    evaluation_known: bool = False
    strategy_artifact_bound: bool = False
    signal_actionable: bool = False
    risk_clear: bool = False
    market_open: bool = False
    spread_clear: bool = False
    freshness_clear: bool = False
    limits_clear: bool = False
    generation_digest: str = ""
    reviewed_files_digest: str = ""
    actual_post_authorized: bool = False
    broker_post_authorized: bool = False

    def binding_valid(
        self, *, generation_digest: str, reviewed_files_digest: str
    ) -> bool:
        return (
            self.evaluation_known
            and self.strategy_artifact_bound
            and self.generation_digest == generation_digest
            and self.reviewed_files_digest == reviewed_files_digest
            and self.actual_post_authorized is False
            and self.broker_post_authorized is False
        )

    def gate_open(self, *, generation_digest: str, reviewed_files_digest: str) -> bool:
        return self.binding_valid(
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
        ) and all(
            (
                self.signal_actionable,
                self.risk_clear,
                self.market_open,
                self.spread_clear,
                self.freshness_clear,
                self.limits_clear,
            )
        )


class G072SnapshotReader(Protocol):
    def read_once(self) -> G072SanitizedSnapshot: ...

    def safe_attempt_counts(self) -> tuple[int, int, int]: ...


class G072ArmMutator(Protocol):
    def arm_once(self, *, generation_digest: str, reviewed_files_digest: str) -> bool: ...


class G072ProjectionWaiter(Protocol):
    def wait_once(
        self,
        *,
        expected_effective_state: str,
        generation_digest: str,
        reviewed_files_digest: str,
        not_before_utc: datetime,
        timeout_seconds: float,
    ) -> bool: ...


class G072EntryEvaluator(Protocol):
    def evaluate(
        self, *, now_utc: datetime, evidence: G072ReconciliationEvidence
    ) -> G072EntryEvaluation: ...


@dataclass
class G072ProcessLock:
    state_root: Path
    acquired: bool = False

    @property
    def path(self) -> Path:
        return self.state_root / "process.lock"

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def acquire(self) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise G072Error("G072_PROCESS_LOCK_SYMLINK_REFUSED")
        if self.path.exists():
            try:
                payload = _read_regular_json(self.path, "G072_PROCESS_LOCK_INVALID")
                pid = int(payload["pid"])
            except (G072Error, KeyError, TypeError, ValueError):
                raise G072Error("G072_PROCESS_LOCK_INVALID") from None
            if self._pid_alive(pid):
                raise G072Error("G072_PROCESS_LOCK_CONFLICT")
            self.path.unlink()
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise G072Error("G072_PROCESS_LOCK_CONFLICT") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "generation_label": G072_GENERATION_LABEL}, stream)
        self.acquired = True

    def release(self) -> None:
        if self.acquired and self.path.is_file() and not self.path.is_symlink():
            self.path.unlink()
        self.acquired = False


@dataclass(frozen=True)
class G072ReconciliationEvidence:
    generation_label: str
    generation_digest: str
    reviewed_files_digest: str
    observed_at_utc: str
    cycle_index: int
    state: G072ReconciliationState
    latest_execution_count: int
    open_position_count: int
    active_order_count: int
    position_open: bool
    account_flat: bool
    active_orders_zero: bool
    ownership_exact: bool
    quantity_matches: bool
    protection_confirmed: bool
    broker_write: bool
    broker_post_count: int
    private_api_read_count: int
    credential_read_count: int
    artifact_digest: str


@dataclass(frozen=True)
class G072AtomicActivationResult:
    status: str
    reconciliation_state: G072ReconciliationState
    effective_state: str
    arm_mutation_count: int
    broker_get_count: int
    broker_post_count: int
    private_api_read_count: int
    credential_read_count: int
    notification_attempt_count: int = 0
    actual_post_authorized: bool = False


def _canonical_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    if path.is_symlink():
        raise G072Error("G072_SYMLINK_PATH_REFUSED")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _exclusive_json(path: Path, payload: dict[str, object]) -> None:
    if path.is_symlink():
        raise G072Error("G072_SYMLINK_PATH_REFUSED")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise G072Error("G072_ONE_USE_MARKER_ALREADY_EXISTS_NO_RETRY") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True)


def _read_regular_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise G072Error(label)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError) as error:
        raise G072Error(label) from error
    if not isinstance(payload, dict):
        raise G072Error(label)
    return payload


def _safe_reader_attempt_counts(reader: G072SnapshotReader) -> tuple[int, int, int]:
    reporter = getattr(reader, "safe_attempt_counts", None)
    if reporter is None:
        return (0, 0, 0)
    try:
        broker_get, private_read, credential_read = reporter()
    except Exception:
        return (0, 0, 0)
    if (
        type(broker_get) is not int
        or not 0 <= broker_get <= 3
        or type(private_read) is not int
        or not 0 <= private_read <= 3
        or type(credential_read) is not int
        or not 0 <= credential_read <= 1
    ):
        return (0, 0, 0)
    return broker_get, private_read, credential_read


def _validate_snapshot(snapshot: G072SanitizedSnapshot) -> None:
    if not isinstance(snapshot, G072SanitizedSnapshot):
        raise G072Error("G072_SNAPSHOT_CONTRACT_INVALID")
    for value in (
        snapshot.latest_execution_count,
        snapshot.open_position_count,
        snapshot.active_order_count,
    ):
        if type(value) is not int or value < 0:
            raise G072Error("G072_SNAPSHOT_COUNT_INVALID")
    if (
        snapshot.broker_get_count != 3
        or snapshot.private_api_read_count != 3
        or snapshot.credential_read_count != 1
        or snapshot.broker_write is not False
        or snapshot.broker_post_count != 0
    ):
        raise G072Error("G072_SNAPSHOT_BOUNDARY_VIOLATION")


def _state_for_snapshot(snapshot: G072SanitizedSnapshot) -> G072ReconciliationState:
    if snapshot.active_order_count != 0:
        return G072ReconciliationState.UNKNOWN
    if snapshot.open_position_count == 0:
        return G072ReconciliationState.FRESH_FLAT
    if (
        snapshot.ownership_exact
        and snapshot.quantity_matches
        and snapshot.protection_confirmed
    ):
        return G072ReconciliationState.FRESH_PROTECTED
    return G072ReconciliationState.UNKNOWN


def _evidence_from_snapshot(
    *,
    snapshot: G072SanitizedSnapshot,
    generation_digest: str,
    reviewed_files_digest: str,
    cycle_index: int,
    now_utc: datetime,
) -> G072ReconciliationEvidence:
    _validate_snapshot(snapshot)
    state = _state_for_snapshot(snapshot)
    base: dict[str, object] = {
        "generation_label": G072_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "observed_at_utc": now_utc.astimezone(UTC).isoformat(),
        "cycle_index": cycle_index,
        "latest_execution_count": snapshot.latest_execution_count,
        "open_position_count": snapshot.open_position_count,
        "active_order_count": snapshot.active_order_count,
        "position_open": snapshot.open_position_count > 0,
        "account_flat": snapshot.open_position_count == 0,
        "active_orders_zero": snapshot.active_order_count == 0,
        "ownership_exact": snapshot.ownership_exact,
        "quantity_matches": snapshot.quantity_matches,
        "protection_confirmed": snapshot.protection_confirmed,
        "broker_write": False,
        "broker_post_count": 0,
        "private_api_read_count": 3,
        "credential_read_count": 1,
    }
    artifact_base = {**base, "state": state.value}
    return G072ReconciliationEvidence(
        **base,
        state=state,
        artifact_digest=_canonical_hash(artifact_base),
    )


def load_g072_reconciliation(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str, now_utc: datetime
) -> G072ReconciliationEvidence | None:
    path = state_root / G072_RECONCILIATION_FILE
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = _read_regular_json(path, "G072_RECONCILIATION_INVALID")
        state = G072ReconciliationState(str(payload.pop("state")))
        artifact_digest = str(payload.pop("artifact_digest"))
        evidence = G072ReconciliationEvidence(
            **payload,
            state=state,
            artifact_digest=artifact_digest,
        )
        base = {**asdict(evidence), "state": evidence.state.value}
        calculated = _canonical_hash(
            {key: value for key, value in base.items() if key != "artifact_digest"}
        )
    except (G072Error, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise G072Error("G072_RECONCILIATION_INVALID") from error
    observed = datetime.fromisoformat(evidence.observed_at_utc)
    if (
        evidence.generation_digest != generation_digest
        or evidence.reviewed_files_digest != reviewed_files_digest
        or evidence.artifact_digest != calculated
        or now_utc.astimezone(UTC) - observed.astimezone(UTC)
        > timedelta(seconds=G072_MAX_EVIDENCE_AGE_SECONDS)
    ):
        raise G072Error("G072_RECONCILIATION_STALE_OR_MISMATCH")
    return evidence


def engage_g072_halt(*, state_root: Path, reason: str) -> None:
    path = state_root / G072_PERSISTENT_HALT_FILE
    if path.is_symlink():
        raise G072Error("G072_HALT_SYMLINK_REFUSED")
    if path.exists():
        return
    _atomic_json(
        path,
        {
            "generation_label": G072_GENERATION_LABEL,
            "status": "HALTED",
            "reason": reason,
            "broker_write": False,
            "actual_post_count": 0,
        },
    )


def run_g072_reconciliation_cycle_once(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    cycle_index: int,
    reader: G072SnapshotReader,
    now_utc: datetime,
) -> G072ReconciliationEvidence:
    if type(cycle_index) is not int or cycle_index < 1:
        raise G072Error("G072_CYCLE_INDEX_INVALID")
    marker = state_root / f"g072-reconciliation-{cycle_index}.started.json"
    outcome = state_root / f"g072-reconciliation-{cycle_index}.outcome.json"
    if marker.exists() or marker.is_symlink() or outcome.exists() or outcome.is_symlink():
        raise G072Error("G072_RECONCILIATION_CYCLE_ALREADY_STARTED_NO_RETRY")
    _exclusive_json(
        marker,
        {
            "generation_label": G072_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "cycle_index": cycle_index,
            "status": "STARTED",
        },
    )
    snapshot: G072SanitizedSnapshot | None = None
    try:
        snapshot = reader.read_once()
        evidence = _evidence_from_snapshot(
            snapshot=snapshot,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
            cycle_index=cycle_index,
            now_utc=now_utc,
        )
        _atomic_json(
            state_root / G072_RECONCILIATION_FILE,
            {**asdict(evidence), "state": evidence.state.value},
        )
        _exclusive_json(
            outcome,
            {
                "status": (
                    "PASSED"
                    if evidence.state is not G072ReconciliationState.UNKNOWN
                    else "UNKNOWN"
                ),
                "cycle_index": cycle_index,
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "broker_get_count": 3,
                "private_api_read_count": 3,
                "credential_read_count": 1,
                "broker_post_count": 0,
            },
        )
        if evidence.state is G072ReconciliationState.UNKNOWN:
            engage_g072_halt(state_root=state_root, reason="G072_RECONCILIATION_UNKNOWN")
            raise G072Error("G072_RECONCILIATION_UNKNOWN_NO_RETRY")
        return evidence
    except Exception as error:
        broker_get, private_read, credential_read = (
            (3, 3, 1) if snapshot is not None else _safe_reader_attempt_counts(reader)
        )
        if not outcome.exists() and not outcome.is_symlink():
            _exclusive_json(
                outcome,
                {
                    "status": "UNKNOWN",
                    "cycle_index": cycle_index,
                    "generation_digest": generation_digest,
                    "reviewed_files_digest": reviewed_files_digest,
                    "broker_get_count": broker_get,
                    "private_api_read_count": private_read,
                    "credential_read_count": credential_read,
                    "broker_post_count": 0,
                },
            )
        engage_g072_halt(state_root=state_root, reason="G072_RECONCILIATION_UNKNOWN")
        if isinstance(error, G072Error):
            raise
        raise G072Error("G072_RECONCILIATION_UNKNOWN_NO_RETRY") from error


def _capability_payload(
    *,
    generation_digest: str,
    reviewed_files_digest: str,
    transaction_outcome_digest: str,
    reconciliation_artifact_digest: str,
    enabled: bool,
) -> dict[str, object]:
    base: dict[str, object] = {
        "schema": "H11_V4_G072_SWITCH_CONTROL_CAPABILITY_V1",
        "generation_label": G072_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "transaction_outcome_digest": transaction_outcome_digest,
        "reconciliation_artifact_digest": reconciliation_artifact_digest,
        "status": "ENABLED" if enabled else "PENDING_OUTCOME",
        "switch_only_rearm_available": enabled,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "daily_authorization_required": False,
        "per_trade_confirmation_required": False,
        "predecessor_authorization_reused": False,
        "predecessor_state_root_reused": False,
    }
    return {**base, "artifact_digest": _canonical_hash(base)}


def verify_g072_switch_capability(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str
) -> bool:
    try:
        capability = _read_regular_json(
            state_root / G072_SWITCH_CAPABILITY_FILE, "G072_SWITCH_CAPABILITY_INVALID"
        )
        outcome = _read_regular_json(
            state_root / G072_TRANSACTION_OUTCOME_FILE, "G072_TRANSACTION_OUTCOME_INVALID"
        )
        if outcome.get("status") != "PASSED":
            return False
        if (
            capability.get("status") != "ENABLED"
            or capability.get("switch_only_rearm_available") is not True
            or capability.get("generation_label") != G072_GENERATION_LABEL
            or capability.get("generation_digest") != generation_digest
            or capability.get("reviewed_files_digest") != reviewed_files_digest
            or capability.get("transaction_outcome_digest") != outcome.get("artifact_digest")
            or capability.get("actual_post_authorized") is not False
            or capability.get("broker_post_authorized") is not False
            or capability.get("daily_authorization_required") is not False
            or capability.get("per_trade_confirmation_required") is not False
            or capability.get("predecessor_authorization_reused") is not False
            or capability.get("predecessor_state_root_reused") is not False
        ):
            return False
        artifact = capability.pop("artifact_digest")
        return artifact == _canonical_hash(capability) and not (
            state_root / G072_PERSISTENT_HALT_FILE
        ).exists()
    except (G072Error, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _runtime_projection(
    *,
    arm_on: bool,
    evidence: G072ReconciliationEvidence | None,
    capability_valid: bool,
    halted: bool,
    entry_gate_open: bool = False,
) -> tuple[G072EffectiveState, bool, str]:
    position_open = bool(evidence and evidence.position_open)
    protected = bool(
        evidence
        and evidence.ownership_exact
        and evidence.quantity_matches
        and evidence.protection_confirmed
    )
    if halted:
        return G072EffectiveState.HALTED, False, "G072_RUNTIME_HALTED"
    if not arm_on:
        if position_open and protected:
            return G072EffectiveState.EXIT_ONLY, False, "G072_ARM_OFF_EXIT_ONLY"
        if position_open:
            return G072EffectiveState.HALTED, False, "G072_POSITION_PROTECTION_UNKNOWN"
        return G072EffectiveState.OFF, False, "G072_ARM_OFF"
    if not capability_valid:
        return G072EffectiveState.HALTED, False, "G072_SWITCH_CAPABILITY_LOCKED"
    if evidence is None:
        return G072EffectiveState.HALTED, False, "G072_RECONCILIATION_REQUIRED"
    if evidence.state is G072ReconciliationState.FRESH_FLAT:
        return (
            G072EffectiveState.ON_WAITING,
            entry_gate_open,
            "G072_ENTRY_GATE_OPEN" if entry_gate_open else "G072_WAITING_FOR_SIGNAL",
        )
    if evidence.state is G072ReconciliationState.FRESH_PROTECTED and protected:
        return G072EffectiveState.ON_EXIT_ONLY, False, "G072_PROTECTED_POSITION_EXIT_ONLY"
    return G072EffectiveState.HALTED, False, "G072_RECONCILIATION_UNKNOWN"


@dataclass
class G072ResidentSupervisor:
    state_root: Path
    generation_digest: str
    reviewed_files_digest: str
    entry_evaluator: G072EntryEvaluator | None = None

    def tick(self, *, now_utc: datetime, arm_on: bool) -> dict[str, object]:
        halted = (self.state_root / G072_PERSISTENT_HALT_FILE).exists() or (
            self.state_root / G072_PERSISTENT_HALT_FILE
        ).is_symlink()
        evidence = None
        if not halted:
            try:
                evidence = load_g072_reconciliation(
                    state_root=self.state_root,
                    generation_digest=self.generation_digest,
                    reviewed_files_digest=self.reviewed_files_digest,
                    now_utc=now_utc,
                )
            except G072Error:
                halted = True
        capability_valid = verify_g072_switch_capability(
            state_root=self.state_root,
            generation_digest=self.generation_digest,
            reviewed_files_digest=self.reviewed_files_digest,
        )
        effective, entry_gate, reason = _runtime_projection(
            arm_on=arm_on,
            evidence=evidence,
            capability_valid=capability_valid,
            halted=halted,
        )
        entry_evaluation: G072EntryEvaluation | None = None
        if effective is G072EffectiveState.ON_WAITING and evidence is not None:
            if self.entry_evaluator is not None:
                try:
                    entry_evaluation = self.entry_evaluator.evaluate(
                        now_utc=now_utc,
                        evidence=evidence,
                    )
                    if not entry_evaluation.binding_valid(
                        generation_digest=self.generation_digest,
                        reviewed_files_digest=self.reviewed_files_digest,
                    ):
                        halted = True
                    else:
                        entry_gate = entry_evaluation.gate_open(
                            generation_digest=self.generation_digest,
                            reviewed_files_digest=self.reviewed_files_digest,
                        )
                        reason = (
                            "G072_ENTRY_GATE_OPEN"
                            if entry_gate
                            else "G072_ENTRY_CONDITIONS_WAIT"
                        )
                except (G072Error, TypeError, ValueError):
                    halted = True
            if halted:
                effective, entry_gate, reason = _runtime_projection(
                    arm_on=arm_on,
                    evidence=evidence,
                    capability_valid=capability_valid,
                    halted=True,
                )
        status = {
            "generation_label": G072_GENERATION_LABEL,
            "generation_digest": self.generation_digest,
            "reviewed_files_digest": self.reviewed_files_digest,
            "arm_state": "ON" if arm_on else "OFF",
            "release_state": "ENABLED" if capability_valid else "LOCKED",
            "effective_state": effective.value,
            "entry_gate_open": entry_gate,
            "entry_state": (
                "ENTRY_READY"
                if entry_gate
                else "WAITING_FOR_SIGNAL"
                if effective is G072EffectiveState.ON_WAITING
                else "BLOCKED_POSITION_OPEN"
                if effective is G072EffectiveState.ON_EXIT_ONLY
                else "HALTED"
                if effective is G072EffectiveState.HALTED
                else "DISABLED"
            ),
            "entry_evaluation_known": bool(
                entry_evaluation and entry_evaluation.evaluation_known
            ),
            "strategy_artifact_bound": bool(
                entry_evaluation and entry_evaluation.strategy_artifact_bound
            ),
            "signal_actionable": bool(
                entry_evaluation and entry_evaluation.signal_actionable
            ),
            "risk_clear": bool(entry_evaluation and entry_evaluation.risk_clear),
            "market_open": bool(entry_evaluation and entry_evaluation.market_open),
            "spread_clear": bool(entry_evaluation and entry_evaluation.spread_clear),
            "freshness_clear": bool(
                entry_evaluation and entry_evaluation.freshness_clear
            ),
            "limits_clear": bool(entry_evaluation and entry_evaluation.limits_clear),
            "entry_state_legacy": (
                "WAITING_FOR_SIGNAL"
                if effective is G072EffectiveState.ON_WAITING
                else "BLOCKED_POSITION_OPEN"
                if effective is G072EffectiveState.ON_EXIT_ONLY
                else "HALTED"
                if effective is G072EffectiveState.HALTED
                else "DISABLED"
            ),
            "reconciliation_state": evidence.state.value if evidence else "REQUIRED",
            "position_open": bool(evidence and evidence.position_open),
            "ownership_exact": bool(evidence and evidence.ownership_exact),
            "quantity_matches": bool(evidence and evidence.quantity_matches),
            "protection_confirmed": bool(evidence and evidence.protection_confirmed),
            "safe_reason_label": reason,
            "heartbeat_at_utc": now_utc.astimezone(UTC).isoformat(),
            "dead_man_alive": True,
            "lock_single_owner": True,
            "broker_write": False,
            "actual_post_count": 0,
        }
        _atomic_json(self.state_root / G072_RUNTIME_STATUS_FILE, status)
        heartbeat = {
            "generation_digest": self.generation_digest,
            "reviewed_files_digest": self.reviewed_files_digest,
            "heartbeat_at_utc": status["heartbeat_at_utc"],
            "broker_write": False,
            "actual_post_count": 0,
        }
        _atomic_json(self.state_root / "heartbeat.json", heartbeat)
        _atomic_json(self.state_root / "dead-man.json", {**heartbeat, "alive": True})
        chain_path = self.state_root / "heartbeat-chain.json"
        index = 1
        previous = "sha256:" + "0" * 64
        if chain_path.is_file() and not chain_path.is_symlink():
            prior = _read_regular_json(chain_path, "G072_HEARTBEAT_CHAIN_INVALID")
            index = int(prior.get("chain_index", 0)) + 1
            previous = str(prior.get("chain_hash", previous))
        chain_base = {**heartbeat, "chain_index": index, "previous_chain_hash": previous}
        _atomic_json(chain_path, {**chain_base, "chain_hash": _canonical_hash(chain_base)})
        return status


def safe_g072_api_status(
    *, state_root: Path, arm_on: bool, generation_digest: str, reviewed_files_digest: str
) -> dict[str, object]:
    capability_valid = verify_g072_switch_capability(
        state_root=state_root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
    )
    path = state_root / G072_RUNTIME_STATUS_FILE
    if path.is_file() and not path.is_symlink():
        try:
            status = _read_regular_json(path, "G072_RUNTIME_STATUS_INVALID")
        except G072Error:
            status = {}
    else:
        status = {}
    effective = str(status.get("effective_state", G072EffectiveState.HALTED.value))
    if status.get("generation_digest") != generation_digest:
        effective = G072EffectiveState.HALTED.value
    return {
        "actual_post_count": 0,
        "broker_write": False,
        "arm_control_available": True,
        "arm_state": "ON" if arm_on else "OFF",
        "desired_state": "ON" if arm_on else "OFF",
        "effective_state": effective,
        "control_plane_state": (
            "HALTED" if effective == G072EffectiveState.HALTED.value else "READY"
        ),
        "entry_gate_open": bool(status.get("entry_gate_open"))
        and effective == G072EffectiveState.ON_WAITING.value,
        "entry_state": str(status.get("entry_state", "HALTED")),
        "safe_reason_label": str(status.get("safe_reason_label", "G072_RUNTIME_STATUS_REQUIRED")),
        "generation_label": G072_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "release_state": "ENABLED" if capability_valid else "LOCKED",
        "atomic_activation_complete": capability_valid,
        "runtime_activation_available": capability_valid,
        "switch_only_rearm_available": capability_valid,
        "daily_authorization_required": False,
        "per_trade_confirmation_required": False,
        "live_ready": False,
        "unattended_live_supported": False,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "local_arm_on_available": capability_valid,
        "arm_ready": capability_valid,
        "scheduler_ready": status.get("lock_single_owner") is True,
        "position_reconciliation_ready": status.get("reconciliation_state")
        in {
            G072ReconciliationState.FRESH_FLAT.value,
            G072ReconciliationState.FRESH_PROTECTED.value,
        },
    }


def verify_g072_scheduler_binding(
    *, generation: object, repository: Path, plist_path: Path, state_root: Path, now_utc: datetime
) -> None:
    if getattr(generation, "generation_label", None) != G072_GENERATION_LABEL:
        raise G072Error("G072_GENERATION_REQUIRED")
    if (state_root / G072_PERSISTENT_HALT_FILE).exists() or (
        state_root / G072_PERSISTENT_HALT_FILE
    ).is_symlink():
        raise G072Error("G072_PERSISTENT_HALT_PRESENT")
    if not plist_path.is_file() or plist_path.is_symlink():
        raise G072Error("G072_SCHEDULER_PLIST_INVALID")
    try:
        import plistlib

        payload = plistlib.loads(plist_path.read_bytes())
        arguments = payload["ProgramArguments"]
    except (OSError, KeyError, TypeError, ValueError, plistlib.InvalidFileException) as error:
        raise G072Error("G072_SCHEDULER_PLIST_INVALID") from error
    repository_text = str(repository.resolve())
    expected = str(
        repository.resolve()
        / "backend/scripts/h11_auto_v4_g072_runtime_bootstrap_no_post.py"
    )
    if expected not in arguments or repository_text not in arguments:
        raise G072Error("G072_SCHEDULER_BINDING_INVALID")
    reviewed = getattr(generation, "implementation_digest", None)
    digest = getattr(generation, "digest", None)
    if reviewed is None or digest is None:
        raise G072Error("G072_GENERATION_DIGEST_MISSING")
    if reviewed not in arguments or digest not in arguments:
        raise G072Error("G072_SCHEDULER_DIGEST_MISMATCH")
    required = (
        state_root / "heartbeat.json",
        state_root / "process.lock",
        state_root / "dead-man.json",
        state_root / "heartbeat-chain.json",
        state_root / G072_RUNTIME_STATUS_FILE,
    )
    if any(not path.is_file() or path.is_symlink() for path in required):
        raise G072Error("G072_RUNTIME_READINESS_MISSING")
    heartbeat = _read_regular_json(required[0], "G072_HEARTBEAT_INVALID")
    dead_man = _read_regular_json(required[2], "G072_DEAD_MAN_INVALID")
    status = _read_regular_json(required[4], "G072_RUNTIME_STATUS_INVALID")
    observed = datetime.fromisoformat(str(heartbeat["heartbeat_at_utc"]))
    if (
        heartbeat.get("generation_digest") != digest
        or heartbeat.get("reviewed_files_digest") != reviewed
        or heartbeat.get("broker_write") is not False
        or heartbeat.get("actual_post_count") != 0
        or dead_man.get("alive") is not True
        or status.get("generation_digest") != digest
        or status.get("reviewed_files_digest") != reviewed
        or status.get("broker_write") is not False
        or status.get("actual_post_count") != 0
        or now_utc.astimezone(UTC) - observed.astimezone(UTC)
        > timedelta(seconds=G072_MAX_EVIDENCE_AGE_SECONDS)
    ):
        raise G072Error("G072_RUNTIME_READINESS_NOT_CLEAR")


def verify_g072_review_artifacts(
    *, repository: Path, generation_digest: str, reviewed_files_digest: str
) -> None:
    root = repository / "docs/templates"
    paths = (
        root / "h11_v4_g072_frozen_generation.json",
        root / "h11_v4_g072_runtime_commissioning_evidence.json",
        root / "h11_v4_g072_independent_review_attestation.json",
    )
    try:
        manifest, evidence, attestation = (
            json.loads(path.read_text(encoding="utf-8")) for path in paths
        )
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise G072Error("G072_REVIEW_ARTIFACT_INVALID") from error
    calculated_generation = _canonical_hash(
        {
            key: value
            for key, value in manifest.items()
            if key not in {"runtime_commissioning_evidence_digest", "successor_halt_release_digest"}
        }
    )
    calculated_evidence = _canonical_hash(
        {key: value for key, value in evidence.items() if key != "artifact_digest"}
    )
    calculated_attestation = _canonical_hash(
        {key: value for key, value in attestation.items() if key != "artifact_digest"}
    )
    if (
        manifest.get("implementation_digest") != reviewed_files_digest
        or calculated_generation != generation_digest
        or evidence.get("generation_digest") != generation_digest
        or attestation.get("generation_digest") != generation_digest
        or evidence.get("reviewed_files_digest") != reviewed_files_digest
        or attestation.get("reviewed_files_digest") != reviewed_files_digest
        or evidence.get("artifact_digest") != calculated_evidence
        or attestation.get("artifact_digest") != calculated_attestation
        or manifest.get("runtime_commissioning_evidence_digest") != calculated_evidence
        or manifest.get("successor_halt_release_digest") != calculated_attestation
        or manifest.get("actual_post_authorized") is not False
        or manifest.get("live_ready") is not False
        or manifest.get("unattended_live_supported") is not False
        or any(
            evidence.get(field) is not True
            for field in (
                "focused_tests_clear",
                "related_tests_clear",
                "ruff_clear",
                "diff_check_clear",
                "danger_scan_clear",
                "architecture_review_clear",
                "safety_review_clear",
                "operations_review_clear",
            )
        )
        or any(
            evidence.get(field) != 0
            for field in (
                "broker_get_count",
                "broker_post_count",
                "private_api_read_count",
                "credential_read_count",
                "notification_attempt_count",
                "arm_mutation_count",
                "launchagent_mutation_count",
            )
        )
        or evidence.get("actual_post_authorized") is not False
        or evidence.get("broker_post_authorized") is not False
        or evidence.get("broker_write") is not False
        or attestation.get("architecture_status") != "CLEAR"
        or attestation.get("safety_status") != "CLEAR"
        or attestation.get("operations_status") != "CLEAR"
        or attestation.get("blocking_findings") != []
    ):
        raise G072Error("G072_REVIEW_ARTIFACT_BINDING_MISMATCH")


def run_g072_initial_atomic_activation_once(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    precondition_verifier: Callable[[], None],
    snapshot_reader: G072SnapshotReader,
    arm_mutator: G072ArmMutator,
    projection_waiter: G072ProjectionWaiter,
    now_utc: datetime,
    projection_timeout_seconds: float = 30.0,
) -> G072AtomicActivationResult:
    if now_utc.tzinfo is None:
        raise G072Error("G072_CLOCK_INVALID")
    outcome_path = state_root / G072_TRANSACTION_OUTCOME_FILE
    started_path = state_root / G072_TRANSACTION_STARTED_FILE
    halt_path = state_root / G072_PERSISTENT_HALT_FILE
    if outcome_path.exists() or outcome_path.is_symlink():
        raise G072Error("G072_TRANSACTION_OUTCOME_EXISTS_NO_RETRY")
    if started_path.exists() or started_path.is_symlink():
        raise G072Error("G072_TRANSACTION_ALREADY_STARTED_NO_RETRY")
    precondition_verifier()
    if halt_path.exists() or halt_path.is_symlink():
        raise G072Error("G072_PERSISTENT_HALT_PRESENT")
    _exclusive_json(
        started_path,
        {
            "generation_label": G072_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "status": "STARTED",
        },
    )
    arm_mutated = False
    snapshot: G072SanitizedSnapshot | None = None
    try:
        snapshot = snapshot_reader.read_once()
        evidence = _evidence_from_snapshot(
            snapshot=snapshot,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
            cycle_index=0,
            now_utc=now_utc,
        )
        _atomic_json(
            state_root / G072_RECONCILIATION_FILE,
            {**asdict(evidence), "state": evidence.state.value},
        )
        if evidence.state not in {
            G072ReconciliationState.FRESH_FLAT,
            G072ReconciliationState.FRESH_PROTECTED,
        }:
            raise G072Error("G072_RECONCILIATION_NOT_CLEAR")
        release_base = {
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "reconciliation_artifact_digest": evidence.artifact_digest,
            "actual_post_authorized": False,
            "broker_post_authorized": False,
        }
        _atomic_json(
            state_root / G072_SWITCH_CAPABILITY_FILE,
            _capability_payload(
                generation_digest=generation_digest,
                reviewed_files_digest=reviewed_files_digest,
                transaction_outcome_digest="PENDING",
                reconciliation_artifact_digest=str(release_base["reconciliation_artifact_digest"]),
                enabled=False,
            ),
        )
        arm_mutated = arm_mutator.arm_once(
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
        )
        if arm_mutated is not True:
            raise G072Error("G072_ARM_MUTATION_UNKNOWN")
        expected = (
            G072EffectiveState.ON_WAITING.value
            if evidence.state is G072ReconciliationState.FRESH_FLAT
            else G072EffectiveState.ON_EXIT_ONLY.value
        )
        if not projection_waiter.wait_once(
            expected_effective_state=expected,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
            not_before_utc=now_utc,
            timeout_seconds=projection_timeout_seconds,
        ):
            raise G072Error("G072_RESIDENT_PROJECTION_TIMEOUT")
        outcome_base = {
            "status": "PASSED",
            "generation_label": G072_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "reconciliation_state": evidence.state.value,
            "effective_state": expected,
            "arm_mutation_count": 1,
            "broker_get_count": 3,
            "broker_post_count": 0,
            "private_api_read_count": 3,
            "credential_read_count": 1,
            "notification_attempt_count": 0,
            "actual_post_authorized": False,
        }
        outcome = {**outcome_base, "artifact_digest": _canonical_hash(outcome_base)}
        _exclusive_json(outcome_path, outcome)
        _atomic_json(
            state_root / G072_SWITCH_CAPABILITY_FILE,
            _capability_payload(
                generation_digest=generation_digest,
                reviewed_files_digest=reviewed_files_digest,
                transaction_outcome_digest=str(outcome["artifact_digest"]),
                reconciliation_artifact_digest=evidence.artifact_digest,
                enabled=True,
            ),
        )
        return G072AtomicActivationResult(
            status="PASSED",
            reconciliation_state=evidence.state,
            effective_state=expected,
            arm_mutation_count=1,
            broker_get_count=3,
            broker_post_count=0,
            private_api_read_count=3,
            credential_read_count=1,
        )
    except Exception as error:
        broker_get, private_read, credential_read = (
            (3, 3, 1) if snapshot is not None else _safe_reader_attempt_counts(snapshot_reader)
        )
        if not outcome_path.exists() and not outcome_path.is_symlink():
            outcome_base = {
                "status": "UNKNOWN",
                "generation_label": G072_GENERATION_LABEL,
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "arm_mutation_count": 1 if arm_mutated else 0,
                "broker_get_count": broker_get,
                "broker_post_count": 0,
                "private_api_read_count": private_read,
                "credential_read_count": credential_read,
                "notification_attempt_count": 0,
                "actual_post_authorized": False,
            }
            _exclusive_json(
                outcome_path,
                {**outcome_base, "artifact_digest": _canonical_hash(outcome_base)},
            )
        engage_g072_halt(state_root=state_root, reason="G072_ATOMIC_ACTIVATION_UNKNOWN")
        if isinstance(error, G072Error):
            raise
        raise G072Error("G072_ATOMIC_ACTIVATION_UNKNOWN_NO_RETRY") from error
