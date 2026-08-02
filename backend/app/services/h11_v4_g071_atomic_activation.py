"""G071 atomic read-only reconciliation, release, and local ARM transaction."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from app.services.h11_v4_g070_candidate import (
    ArmState,
    ControlPlaneState,
    EffectiveState,
    EntryState,
    G070Projection,
    G070ProjectionInput,
    ReconciliationState,
    project_g070_runtime,
)

G071_GENERATION_LABEL = "H11_AUTO_30M_20260802_G071"
G071_PERSISTENT_HALT_FILE = "g071-persistent-halt.json"
G071_RUNTIME_STATUS_FILE = "g071-runtime-status.json"
G071_RECONCILIATION_FILE = "g071-reconciliation-current.json"
G071_RELEASE_CAPABILITY_FILE = "g071-release-capability.json"
G071_TRANSACTION_STARTED_FILE = "g071-atomic-activation.started.json"
G071_TRANSACTION_OUTCOME_FILE = "g071-atomic-activation.outcome.json"
G071_OPERATION_60_STARTED_FILE = "g071-operation-60.started.json"
G071_OPERATION_60_RESULT_FILE = "g071-operation-60.result.json"
G071_MAX_EVIDENCE_AGE_SECONDS = 60


class G071Error(ValueError):
    """Safe-label-only G071 failure."""


@dataclass(frozen=True)
class G071SanitizedSnapshot:
    latest_execution_count: int
    open_position_count: int
    active_order_count: int
    ownership_exact: bool = False
    quantity_matches: bool = False
    protection_confirmed: bool = False
    latest_executions_read_count: int = 1
    open_positions_read_count: int = 1
    active_orders_read_count: int = 1
    private_api_read_count: int = 3
    credential_read_count: int = 1
    broker_write: bool = False
    broker_post_count: int = 0


class G071SnapshotReader(Protocol):
    def read_once(self) -> G071SanitizedSnapshot: ...

    def safe_attempt_counts(self) -> tuple[int, int, int]: ...


class G071ArmMutator(Protocol):
    def arm_once(self, *, generation_digest: str, reviewed_files_digest: str) -> bool: ...


class G071ProjectionWaiter(Protocol):
    def wait_once(
        self,
        *,
        expected_effective_state: str,
        generation_digest: str,
        reviewed_files_digest: str,
        not_before_utc: datetime,
        timeout_seconds: float,
    ) -> bool: ...


def _safe_reader_attempt_counts(reader: G071SnapshotReader) -> tuple[int, int, int]:
    reporter = getattr(reader, "safe_attempt_counts", None)
    if reporter is None:
        return (0, 0, 0)
    try:
        broker_get_count, private_api_read_count, credential_read_count = reporter()
    except Exception:
        return (0, 0, 0)
    if (
        type(broker_get_count) is not int
        or not 0 <= broker_get_count <= 3
        or type(private_api_read_count) is not int
        or not 0 <= private_api_read_count <= 3
        or type(credential_read_count) is not int
        or not 0 <= credential_read_count <= 1
    ):
        return (0, 0, 0)
    return broker_get_count, private_api_read_count, credential_read_count


@dataclass(frozen=True)
class G071ReconciliationEvidence:
    generation_label: str
    generation_digest: str
    reviewed_files_digest: str
    observed_at_utc: str
    state: ReconciliationState
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
class G071AtomicActivationResult:
    status: str
    reconciliation_state: ReconciliationState
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
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _exclusive_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise G071Error("G071_ONE_USE_MARKER_ALREADY_EXISTS_NO_RETRY") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True)


def engage_g071_halt(*, state_root: Path, reason: str) -> None:
    halt_path = state_root / G071_PERSISTENT_HALT_FILE
    if halt_path.is_symlink():
        raise G071Error("G071_HALT_SYMLINK_REFUSED")
    _atomic_json(
        halt_path,
        {
            "generation_label": G071_GENERATION_LABEL,
            "status": "HALTED",
            "reason": reason,
            "broker_write": False,
            "actual_post_count": 0,
        },
    )


def _validate_snapshot(snapshot: G071SanitizedSnapshot) -> None:
    if not isinstance(snapshot, G071SanitizedSnapshot):
        raise G071Error("G071_SNAPSHOT_CONTRACT_INVALID")
    counts = (
        snapshot.latest_execution_count,
        snapshot.open_position_count,
        snapshot.active_order_count,
    )
    if any(type(value) is not int or value < 0 for value in counts):
        raise G071Error("G071_SNAPSHOT_COUNT_INVALID")
    if (
        snapshot.latest_executions_read_count != 1
        or snapshot.open_positions_read_count != 1
        or snapshot.active_orders_read_count != 1
        or snapshot.private_api_read_count != 3
        or snapshot.credential_read_count != 1
        or snapshot.broker_write is not False
        or snapshot.broker_post_count != 0
    ):
        raise G071Error("G071_SNAPSHOT_BOUNDARY_VIOLATION")


def _reconciliation_from_snapshot(
    *,
    snapshot: G071SanitizedSnapshot,
    generation_digest: str,
    reviewed_files_digest: str,
    now_utc: datetime,
) -> G071ReconciliationEvidence:
    _validate_snapshot(snapshot)
    position_open = snapshot.open_position_count > 0
    active_zero = snapshot.active_order_count == 0
    if not position_open and active_zero:
        state = ReconciliationState.FRESH_FLAT
    elif position_open and all(
        (
            snapshot.ownership_exact,
            snapshot.quantity_matches,
            snapshot.protection_confirmed,
        )
    ):
        state = ReconciliationState.FRESH_PROTECTED
    else:
        state = ReconciliationState.UNKNOWN
    base: dict[str, object] = {
        "generation_label": G071_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "observed_at_utc": now_utc.astimezone(UTC).isoformat(),
        "state": state.value,
        "latest_execution_count": snapshot.latest_execution_count,
        "open_position_count": snapshot.open_position_count,
        "active_order_count": snapshot.active_order_count,
        "position_open": position_open,
        "account_flat": not position_open,
        "active_orders_zero": active_zero,
        "ownership_exact": snapshot.ownership_exact,
        "quantity_matches": snapshot.quantity_matches,
        "protection_confirmed": snapshot.protection_confirmed,
        "broker_write": False,
        "broker_post_count": 0,
        "private_api_read_count": 3,
        "credential_read_count": 1,
    }
    return G071ReconciliationEvidence(
        **{**base, "state": state, "artifact_digest": _canonical_hash(base)}
    )


def run_g071_atomic_activation_once(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    precondition_verifier: Callable[[], None],
    snapshot_reader: G071SnapshotReader,
    arm_mutator: G071ArmMutator,
    projection_waiter: G071ProjectionWaiter,
    now_utc: datetime,
    projection_timeout_seconds: float = 30.0,
) -> G071AtomicActivationResult:
    """Perform the only G071 external transaction; no phase is separately callable."""

    if now_utc.tzinfo is None:
        raise G071Error("G071_CLOCK_INVALID")
    outcome_path = state_root / G071_TRANSACTION_OUTCOME_FILE
    started_path = state_root / G071_TRANSACTION_STARTED_FILE
    halt_path = state_root / G071_PERSISTENT_HALT_FILE
    if outcome_path.exists() or outcome_path.is_symlink():
        raise G071Error("G071_TRANSACTION_OUTCOME_EXISTS_NO_RETRY")
    if started_path.exists() or started_path.is_symlink():
        raise G071Error("G071_TRANSACTION_ALREADY_STARTED_NO_RETRY")
    precondition_verifier()
    if halt_path.exists() or halt_path.is_symlink():
        raise G071Error("G071_PERSISTENT_HALT_PRESENT")
    _exclusive_json(
        state_root / G071_TRANSACTION_STARTED_FILE,
        {
            "generation_label": G071_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "status": "STARTED",
        },
    )
    arm_mutated = False
    snapshot: G071SanitizedSnapshot | None = None
    try:
        snapshot = snapshot_reader.read_once()
        evidence = _reconciliation_from_snapshot(
            snapshot=snapshot,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
            now_utc=now_utc,
        )
        _atomic_json(
            state_root / G071_RECONCILIATION_FILE,
            {**asdict(evidence), "state": evidence.state.value},
        )
        if evidence.state not in {
            ReconciliationState.FRESH_FLAT,
            ReconciliationState.FRESH_PROTECTED,
        }:
            raise G071Error("G071_RECONCILIATION_NOT_CLEAR")
        release_base: dict[str, object] = {
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "reconciliation_artifact_digest": evidence.artifact_digest,
            "issued_at_utc": now_utc.astimezone(UTC).isoformat(),
            "actual_post_authorized": False,
            "broker_post_authorized": False,
            "daily_authorization_required": False,
            "per_trade_confirmation_required": False,
        }
        _atomic_json(
            state_root / G071_RELEASE_CAPABILITY_FILE,
            {**release_base, "artifact_digest": _canonical_hash(release_base)},
        )
        arm_mutated = arm_mutator.arm_once(
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
        )
        if arm_mutated is not True:
            raise G071Error("G071_ARM_MUTATION_UNKNOWN")
        expected = (
            EffectiveState.ON_WAITING.value
            if evidence.state is ReconciliationState.FRESH_FLAT
            else EffectiveState.ON_EXIT_ONLY.value
        )
        if (
            projection_waiter.wait_once(
                expected_effective_state=expected,
                generation_digest=generation_digest,
                reviewed_files_digest=reviewed_files_digest,
                not_before_utc=now_utc,
                timeout_seconds=projection_timeout_seconds,
            )
            is not True
        ):
            raise G071Error("G071_RESIDENT_PROJECTION_TIMEOUT")
        outcome = {
            "status": "PASSED",
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
        _exclusive_json(state_root / G071_TRANSACTION_OUTCOME_FILE, outcome)
        return G071AtomicActivationResult(
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
        broker_get_count, private_api_read_count, credential_read_count = (
            (3, 3, 1) if snapshot is not None else _safe_reader_attempt_counts(snapshot_reader)
        )
        unknown = {
            "status": "UNKNOWN",
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "arm_mutation_count": 1 if arm_mutated else 0,
            "broker_get_count": broker_get_count,
            "broker_post_count": 0,
            "private_api_read_count": private_api_read_count,
            "credential_read_count": credential_read_count,
            "notification_attempt_count": 0,
            "actual_post_authorized": False,
        }
        if not outcome_path.exists() and not outcome_path.is_symlink():
            _exclusive_json(state_root / G071_TRANSACTION_OUTCOME_FILE, unknown)
        engage_g071_halt(state_root=state_root, reason="G071_ATOMIC_ACTIVATION_UNKNOWN")
        if isinstance(error, G071Error):
            raise
        raise G071Error("G071_ATOMIC_ACTIVATION_UNKNOWN_NO_RETRY") from error


def load_g071_reconciliation(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str, now_utc: datetime
) -> G071ReconciliationEvidence | None:
    path = state_root / G071_RECONCILIATION_FILE
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["state"] = ReconciliationState(payload["state"])
        evidence = G071ReconciliationEvidence(**payload)
        observed = datetime.fromisoformat(evidence.observed_at_utc)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise G071Error("G071_RECONCILIATION_INVALID") from error
    base = {**asdict(evidence), "state": evidence.state.value}
    artifact_digest = str(base.pop("artifact_digest"))
    if (
        evidence.generation_digest != generation_digest
        or evidence.reviewed_files_digest != reviewed_files_digest
        or artifact_digest != _canonical_hash(base)
    ):
        raise G071Error("G071_RECONCILIATION_BINDING_MISMATCH")
    if now_utc.astimezone(UTC) - observed.astimezone(UTC) > timedelta(
        seconds=G071_MAX_EVIDENCE_AGE_SECONDS
    ):
        return G071ReconciliationEvidence(
            **{**asdict(evidence), "state": ReconciliationState.STALE}
        )
    return evidence


def _release_ready(*, state_root: Path, generation_digest: str, reviewed_files_digest: str) -> bool:
    path = state_root / G071_RELEASE_CAPABILITY_FILE
    if not path.is_file() or path.is_symlink():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        artifact = str(payload.pop("artifact_digest"))
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return False
    return bool(
        payload.get("generation_digest") == generation_digest
        and payload.get("reviewed_files_digest") == reviewed_files_digest
        and payload.get("actual_post_authorized") is False
        and payload.get("broker_post_authorized") is False
        and artifact == _canonical_hash(payload)
    )


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


class G071OwnerLock:
    def __init__(self, path: Path, *, pid_alive: Callable[[int], bool] | None = None) -> None:
        self.path = path
        self.pid_alive = pid_alive or _pid_alive
        self.acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and not self.path.is_symlink():
            try:
                existing = int(json.loads(self.path.read_text(encoding="utf-8"))["pid"])
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                raise G071Error("G071_PROCESS_LOCK_INVALID") from error
            if self.pid_alive(existing):
                raise G071Error("G071_PROCESS_LOCK_CONFLICT")
            self.path.unlink()
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise G071Error("G071_PROCESS_LOCK_CONFLICT") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid()}, stream)
        self.acquired = True

    def release(self) -> None:
        if self.acquired and self.path.is_file() and not self.path.is_symlink():
            self.path.unlink()
        self.acquired = False


@dataclass
class G071ResidentSupervisor:
    state_root: Path
    generation_digest: str
    reviewed_files_digest: str
    exit_manager: Callable[[G070Projection], None] | None = None
    entry_evaluator: Callable[[G070Projection], None] | None = None

    def tick(self, *, now_utc: datetime, arm_state: ArmState) -> G070Projection:
        if (self.state_root / G071_PERSISTENT_HALT_FILE).exists():
            projection = project_g070_runtime(
                G070ProjectionInput(
                    ControlPlaneState.HALTED, ReconciliationState.UNKNOWN, arm_state
                )
            )
        else:
            evidence = load_g071_reconciliation(
                state_root=self.state_root,
                generation_digest=self.generation_digest,
                reviewed_files_digest=self.reviewed_files_digest,
                now_utc=now_utc,
            )
            state = evidence.state if evidence else ReconciliationState.REQUIRED
            position_open = bool(evidence and evidence.position_open)
            if position_open and self.exit_manager is None:
                projection = project_g070_runtime(
                    G070ProjectionInput(
                        ControlPlaneState.HALTED, state, arm_state, position_open=True
                    )
                )
            else:
                projection = project_g070_runtime(
                    G070ProjectionInput(
                        ControlPlaneState.READY,
                        state,
                        arm_state,
                        position_open=position_open,
                        ownership_exact=bool(evidence and evidence.ownership_exact),
                        quantity_matches=bool(evidence and evidence.quantity_matches),
                        protection_confirmed=bool(evidence and evidence.protection_confirmed),
                        entry_gates_clear=bool(
                            evidence
                            and state is ReconciliationState.FRESH_FLAT
                            and _release_ready(
                                state_root=self.state_root,
                                generation_digest=self.generation_digest,
                                reviewed_files_digest=self.reviewed_files_digest,
                            )
                            and self.entry_evaluator is not None
                        ),
                    )
                )
        status: dict[str, object] = {
            "arm_state": projection.arm_state.value,
            "control_plane_state": projection.control_plane_state.value,
            "reconciliation_state": projection.reconciliation_state.value,
            "effective_state": projection.effective_state.value,
            "entry_gate_open": projection.entry_gate_open,
            "entry_state": projection.entry_state.value,
            "safe_reason_label": projection.safe_reason_label,
            "generation_label": G071_GENERATION_LABEL,
            "generation_digest": self.generation_digest,
            "reviewed_files_digest": self.reviewed_files_digest,
            "heartbeat_at_utc": now_utc.astimezone(UTC).isoformat(),
            "dead_man_alive": True,
            "lock_single_owner": True,
            "broker_write": False,
            "actual_post_count": 0,
        }
        _atomic_json(self.state_root / G071_RUNTIME_STATUS_FILE, status)
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
            prior = json.loads(chain_path.read_text(encoding="utf-8"))
            index = int(prior.get("chain_index", 0)) + 1
            previous = str(prior.get("chain_hash", previous))
        chain_base = {**heartbeat, "chain_index": index, "previous_chain_hash": previous}
        _atomic_json(chain_path, {**chain_base, "chain_hash": _canonical_hash(chain_base)})
        if projection.effective_state in {EffectiveState.ON_EXIT_ONLY, EffectiveState.EXIT_ONLY}:
            if self.exit_manager:
                self.exit_manager(projection)
        if projection.entry_gate_open and self.entry_evaluator:
            self.entry_evaluator(projection)
        return projection


def safe_g071_api_status(
    *, state_root: Path, arm_on: bool, generation_digest: str, reviewed_files_digest: str
) -> dict[str, object]:
    path = state_root / G071_RUNTIME_STATUS_FILE
    if not path.is_file() or path.is_symlink():
        projection = project_g070_runtime(
            G070ProjectionInput(
                ControlPlaneState.HALTED,
                ReconciliationState.REQUIRED,
                ArmState.ON if arm_on else ArmState.OFF,
            )
        )
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("generation_digest") != generation_digest
            or payload.get("reviewed_files_digest") != reviewed_files_digest
        ):
            raise G071Error("G071_RUNTIME_STATUS_DIGEST_MISMATCH")
        projection = project_g070_runtime(
            G070ProjectionInput(
                ControlPlaneState(payload["control_plane_state"]),
                ReconciliationState(payload["reconciliation_state"]),
                ArmState.ON if arm_on else ArmState.OFF,
                position_open=payload.get("entry_state") == EntryState.POSITION_OPEN.value,
                ownership_exact=payload.get("reconciliation_state")
                == ReconciliationState.FRESH_PROTECTED.value,
                quantity_matches=payload.get("reconciliation_state")
                == ReconciliationState.FRESH_PROTECTED.value,
                protection_confirmed=payload.get("reconciliation_state")
                == ReconciliationState.FRESH_PROTECTED.value,
                entry_gates_clear=bool(payload.get("entry_gate_open")),
            )
        )
    transaction_passed = False
    outcome_path = state_root / G071_TRANSACTION_OUTCOME_FILE
    if outcome_path.is_file() and not outcome_path.is_symlink():
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        transaction_passed = outcome.get("status") == "PASSED"
    return {
        "control_plane_state": projection.control_plane_state.value,
        "reconciliation_state": projection.reconciliation_state.value,
        "effective_state": projection.effective_state.value,
        "entry_gate_open": projection.entry_gate_open,
        "entry_state": projection.entry_state.value,
        "safe_reason_label": projection.safe_reason_label,
        "atomic_activation_complete": transaction_passed,
        # The first G071 ARM mutation is part of the indivisible transaction.
        # Generic UI ON must never substitute for, or replay, that transaction.
        "runtime_activation_available": False,
        "atomic_activation_required": not transaction_passed,
        "switch_only_rearm_available": False,
    }


def verify_g071_scheduler_binding(
    *, generation: object, repository: Path, plist_path: Path, state_root: Path, now_utc: datetime
) -> None:
    if getattr(generation, "generation_label", None) != G071_GENERATION_LABEL:
        raise G071Error("G071_GENERATION_REQUIRED")
    if (state_root / G071_PERSISTENT_HALT_FILE).exists() or (
        state_root / G071_PERSISTENT_HALT_FILE
    ).is_symlink():
        raise G071Error("G071_PERSISTENT_HALT_PRESENT")
    if not plist_path.is_file() or plist_path.is_symlink():
        raise G071Error("G071_SCHEDULER_PLIST_INVALID")
    try:
        arguments = plistlib.loads(plist_path.read_bytes())["ProgramArguments"]
        repository_index = arguments.index("--repository")
        reviewed_index = arguments.index("--expected-reviewed-files-digest")
        generation_index = arguments.index("--expected-generation-digest")
    except (OSError, KeyError, TypeError, ValueError, plistlib.InvalidFileException) as error:
        raise G071Error("G071_SCHEDULER_BINDING_MISMATCH") from error
    if (
        not any(
            str(argument).endswith("h11_auto_v4_g071_runtime_bootstrap_no_post.py")
            for argument in arguments
        )
        or arguments[reviewed_index + 1] != getattr(generation, "implementation_digest", None)
        or arguments[generation_index + 1] != getattr(generation, "digest", None)
        or arguments[repository_index + 1] != str(repository.resolve())
    ):
        raise G071Error("G071_SCHEDULER_BINDING_MISMATCH")
    paths = [
        state_root / "heartbeat.json",
        state_root / "process.lock",
        state_root / "dead-man.json",
        state_root / "heartbeat-chain.json",
        state_root / G071_RUNTIME_STATUS_FILE,
    ]
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise G071Error("G071_RUNTIME_READINESS_MISSING")
    try:
        heartbeat = json.loads(paths[0].read_text(encoding="utf-8"))
        lock = json.loads(paths[1].read_text(encoding="utf-8"))
        dead_man = json.loads(paths[2].read_text(encoding="utf-8"))
        chain = json.loads(paths[3].read_text(encoding="utf-8"))
        status = json.loads(paths[4].read_text(encoding="utf-8"))
        observed = datetime.fromisoformat(heartbeat["heartbeat_at_utc"])
        dead_observed = datetime.fromisoformat(dead_man["heartbeat_at_utc"])
        chain_observed = datetime.fromisoformat(chain["heartbeat_at_utc"])
        chain_payload = {key: value for key, value in chain.items() if key != "chain_hash"}
        lock_pid = int(lock["pid"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise G071Error("G071_RUNTIME_READINESS_INVALID") from error
    generation_digest = getattr(generation, "digest", None)
    reviewed_digest = getattr(generation, "implementation_digest", None)
    if (
        heartbeat.get("generation_digest") != generation_digest
        or heartbeat.get("reviewed_files_digest") != reviewed_digest
        or heartbeat.get("broker_write") is not False
        or heartbeat.get("actual_post_count") != 0
        or dead_man.get("generation_digest") != generation_digest
        or dead_man.get("reviewed_files_digest") != reviewed_digest
        or dead_man.get("alive") is not True
        or chain.get("generation_digest") != generation_digest
        or chain.get("reviewed_files_digest") != reviewed_digest
        or chain.get("chain_hash") != _canonical_hash(chain_payload)
        or int(chain.get("chain_index", 0)) < 1
        or status.get("generation_label") != G071_GENERATION_LABEL
        or status.get("generation_digest") != generation_digest
        or status.get("reviewed_files_digest") != reviewed_digest
        or status.get("control_plane_state") == ControlPlaneState.HALTED.value
        or status.get("broker_write") is not False
        or status.get("actual_post_count") != 0
        or lock_pid <= 0
        or not _pid_alive(lock_pid)
        or now_utc.astimezone(UTC) - observed.astimezone(UTC) > timedelta(seconds=60)
        or now_utc.astimezone(UTC) - dead_observed.astimezone(UTC) > timedelta(seconds=60)
        or now_utc.astimezone(UTC) - chain_observed.astimezone(UTC) > timedelta(seconds=60)
    ):
        raise G071Error("G071_RUNTIME_READINESS_NOT_CLEAR")


def verify_g071_review_artifacts(
    *, repository: Path, generation_digest: str, reviewed_files_digest: str
) -> None:
    root = repository / "docs/templates"
    paths = (
        root / "h11_v4_g071_frozen_generation.json",
        root / "h11_v4_g071_runtime_commissioning_evidence.json",
        root / "h11_v4_g071_independent_review_attestation.json",
    )
    try:
        manifest, evidence, attestation = (
            json.loads(path.read_text(encoding="utf-8")) for path in paths
        )
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise G071Error("G071_REVIEW_ARTIFACT_INVALID") from error
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
        raise G071Error("G071_REVIEW_ARTIFACT_BINDING_MISMATCH")
