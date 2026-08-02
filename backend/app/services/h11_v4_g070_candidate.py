"""G070 fixed-design candidate primitives; external adapters are injected only."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Protocol

G070_GENERATION_LABEL = "H11_AUTO_30M_20260802_G070"
G070_PERSISTENT_HALT_FILE = "g070-persistent-halt.json"
G070_RUNTIME_STATUS_FILE = "g070-runtime-status.json"
G070_RELEASE_CAPABILITY_FILE = "g070-release-capability.json"
G070_OPERATION_60_STARTED_FILE = "g070-operation-60.started.json"
G070_OPERATION_60_RESULT_FILE = "g070-operation-60.result.json"
G070_MAX_EVIDENCE_AGE_SECONDS = 60
G070_SLOT_SECONDS = 30


class G070Error(ValueError):
    """Safe-label-only G070 failure."""


class ControlPlaneState(str, Enum):
    READY = "READY"
    HALTED = "HALTED"


class ReconciliationState(str, Enum):
    REQUIRED = "REQUIRED"
    IN_PROGRESS = "IN_PROGRESS"
    FRESH_FLAT = "FRESH_FLAT"
    FRESH_PROTECTED = "FRESH_PROTECTED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class ArmState(str, Enum):
    OFF = "OFF"
    ON = "ON"


class EffectiveState(str, Enum):
    OFF = "OFF"
    RECOVERING = "RECOVERING"
    ON_WAITING = "ON_WAITING"
    ON_EXIT_ONLY = "ON_EXIT_ONLY"
    EXIT_ONLY = "EXIT_ONLY"
    HALTED = "HALTED"


class EntryState(str, Enum):
    DISARMED = "DISARMED"
    RECOVERING_RECONCILIATION = "RECOVERING_RECONCILIATION"
    WAITING_FOR_SIGNAL = "WAITING_FOR_SIGNAL"
    ENTRY_GATES_BLOCKED = "ENTRY_GATES_BLOCKED"
    ACTION_IN_PROGRESS = "ACTION_IN_PROGRESS"
    POSITION_OPEN = "POSITION_OPEN"
    HALTED = "HALTED"


class G070Action(str, Enum):
    MARKET_ENTRY = "MARKET_ENTRY"
    EXACT_OCO_PROTECTION = "EXACT_OCO_PROTECTION"
    PARTIAL_PENDING_CANCEL = "PARTIAL_PENDING_CANCEL"
    TIME_EXIT_OCO_CANCEL = "TIME_EXIT_OCO_CANCEL"
    POSITION_SPECIFIC_CLOSE = "POSITION_SPECIFIC_CLOSE"


@dataclass(frozen=True)
class G070ProjectionInput:
    control_plane_state: ControlPlaneState
    reconciliation_state: ReconciliationState
    arm_state: ArmState
    position_open: bool = False
    ownership_exact: bool = False
    quantity_matches: bool = False
    protection_confirmed: bool = False
    entry_gates_clear: bool = False
    action_in_progress: bool = False
    pending_transport: bool = False
    generation_matches: bool = True
    lock_single_owner: bool = True
    dead_man_alive: bool = True


@dataclass(frozen=True)
class G070Projection:
    arm_state: ArmState
    control_plane_state: ControlPlaneState
    reconciliation_state: ReconciliationState
    effective_state: EffectiveState
    entry_gate_open: bool
    entry_state: EntryState
    safe_reason_label: str


def project_g070_runtime(value: G070ProjectionInput) -> G070Projection:
    fatal = (
        value.control_plane_state is ControlPlaneState.HALTED
        or value.reconciliation_state is ReconciliationState.UNKNOWN
        or value.pending_transport
        or not value.generation_matches
        or not value.lock_single_owner
        or not value.dead_man_alive
    )
    if value.position_open and not all(
        (value.ownership_exact, value.quantity_matches, value.protection_confirmed)
    ):
        fatal = True
    if (
        value.position_open
        and value.reconciliation_state is not ReconciliationState.FRESH_PROTECTED
    ):
        fatal = True
    if (
        not value.position_open
        and value.reconciliation_state is ReconciliationState.FRESH_PROTECTED
    ):
        fatal = True
    if fatal:
        return G070Projection(
            arm_state=value.arm_state,
            control_plane_state=ControlPlaneState.HALTED,
            reconciliation_state=value.reconciliation_state,
            effective_state=EffectiveState.HALTED,
            entry_gate_open=False,
            entry_state=EntryState.HALTED,
            safe_reason_label="RUNTIME_SAFETY_NOT_PROVEN",
        )
    if value.position_open:
        return G070Projection(
            arm_state=value.arm_state,
            control_plane_state=value.control_plane_state,
            reconciliation_state=value.reconciliation_state,
            effective_state=(
                EffectiveState.ON_EXIT_ONLY
                if value.arm_state is ArmState.ON
                else EffectiveState.EXIT_ONLY
            ),
            entry_gate_open=False,
            entry_state=EntryState.POSITION_OPEN,
            safe_reason_label="PROTECTED_POSITION_EXIT_MANAGEMENT",
        )
    if value.arm_state is ArmState.OFF:
        return G070Projection(
            arm_state=value.arm_state,
            control_plane_state=value.control_plane_state,
            reconciliation_state=value.reconciliation_state,
            effective_state=EffectiveState.OFF,
            entry_gate_open=False,
            entry_state=EntryState.DISARMED,
            safe_reason_label="OPERATOR_DISARMED",
        )
    if value.reconciliation_state in {
        ReconciliationState.REQUIRED,
        ReconciliationState.IN_PROGRESS,
        ReconciliationState.STALE,
    }:
        return G070Projection(
            arm_state=value.arm_state,
            control_plane_state=value.control_plane_state,
            reconciliation_state=value.reconciliation_state,
            effective_state=EffectiveState.RECOVERING,
            entry_gate_open=False,
            entry_state=EntryState.RECOVERING_RECONCILIATION,
            safe_reason_label="RECONCILIATION_REQUIRED",
        )
    if value.action_in_progress:
        return G070Projection(
            arm_state=value.arm_state,
            control_plane_state=value.control_plane_state,
            reconciliation_state=value.reconciliation_state,
            effective_state=EffectiveState.ON_WAITING,
            entry_gate_open=False,
            entry_state=EntryState.ACTION_IN_PROGRESS,
            safe_reason_label="ACTION_IN_PROGRESS",
        )
    return G070Projection(
        arm_state=value.arm_state,
        control_plane_state=value.control_plane_state,
        reconciliation_state=value.reconciliation_state,
        effective_state=EffectiveState.ON_WAITING,
        entry_gate_open=value.entry_gates_clear,
        entry_state=(
            EntryState.WAITING_FOR_SIGNAL
            if value.entry_gates_clear
            else EntryState.ENTRY_GATES_BLOCKED
        ),
        safe_reason_label=(
            "WAITING_FOR_SIGNAL" if value.entry_gates_clear else "ENTRY_GATES_BLOCKED"
        ),
    )


class G070CredentialLoader(Protocol):
    def load_sealed(self) -> object: ...


class G070ReadOnlyClient(Protocol):
    def latest_executions(self, credential: object) -> Sequence[Mapping[str, object]]: ...
    def open_positions(self, credential: object) -> Sequence[Mapping[str, object]]: ...
    def active_orders(self, credential: object) -> Sequence[Mapping[str, object]]: ...


OwnershipMatcher = Callable[
    [
        Sequence[Mapping[str, object]],
        Sequence[Mapping[str, object]],
        Sequence[Mapping[str, object]],
    ],
    tuple[bool, bool, bool],
]


@dataclass(frozen=True)
class G070ReconciliationEvidence:
    schema: str
    generation_label: str
    generation_digest: str
    reviewed_files_digest: str
    slot_index: int
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
    previous_chain_hash: str
    chain_hash: str


def _canonical_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def engage_g070_halt(*, state_root: Path, reason: str) -> None:
    _atomic_json(
        state_root / G070_PERSISTENT_HALT_FILE,
        {
            "generation_label": G070_GENERATION_LABEL,
            "status": "HALTED",
            "reason": reason,
            "broker_write": False,
            "actual_post_count": 0,
        },
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


def _safe_slot(now_utc: datetime) -> int:
    if now_utc.tzinfo is None:
        raise G070Error("TIMEZONE_REQUIRED")
    return int(now_utc.timestamp()) // G070_SLOT_SECONDS


def run_g070_reconciliation_slot(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    credential_loader: G070CredentialLoader,
    client: G070ReadOnlyClient,
    ownership_matcher: OwnershipMatcher,
    now_utc: datetime,
) -> G070ReconciliationEvidence:
    """Run one distinct slot; marker is durable before credential/network access."""

    slot = _safe_slot(now_utc)
    slots = state_root / "g070-reconciliation-slots"
    slots.mkdir(parents=True, exist_ok=True)
    started = slots / f"{slot}.started.json"
    try:
        descriptor = os.open(started, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise G070Error("RECONCILIATION_SLOT_ALREADY_ATTEMPTED_NO_RETRY") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(
            {
                "generation_label": G070_GENERATION_LABEL,
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "slot_index": slot,
                "status": "STARTED",
            },
            stream,
            sort_keys=True,
        )
    try:
        credential = credential_loader.load_sealed()
        executions = client.latest_executions(credential)
        positions = client.open_positions(credential)
        orders = client.active_orders(credential)
        position_open = len(positions) > 0
        account_flat = not position_open
        active_zero = len(orders) == 0
        ownership, quantity, protection = (False, False, False)
        if position_open:
            ownership, quantity, protection = ownership_matcher(executions, positions, orders)
            state = (
                ReconciliationState.FRESH_PROTECTED
                if all((ownership, quantity, protection))
                else ReconciliationState.UNKNOWN
            )
        else:
            state = ReconciliationState.FRESH_FLAT if active_zero else ReconciliationState.UNKNOWN
        chain_file = state_root / "g070-reconciliation-chain.json"
        previous = "sha256:" + "0" * 64
        if chain_file.is_file() and not chain_file.is_symlink():
            loaded = json.loads(chain_file.read_text(encoding="utf-8"))
            previous = str(loaded.get("chain_hash", previous))
        base = {
            "schema": "H11_V4_G070_RECONCILIATION_V1",
            "generation_label": G070_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "slot_index": slot,
            "observed_at_utc": now_utc.astimezone(UTC).isoformat(),
            "state": state.value,
            "latest_execution_count": len(executions),
            "open_position_count": len(positions),
            "active_order_count": len(orders),
            "position_open": position_open,
            "account_flat": account_flat,
            "active_orders_zero": active_zero,
            "ownership_exact": ownership,
            "quantity_matches": quantity,
            "protection_confirmed": protection,
            "broker_write": False,
            "broker_post_count": 0,
            "private_api_read_count": 3,
            "credential_read_count": 1,
            "previous_chain_hash": previous,
        }
        chain_hash = _canonical_hash(base)
        payload = {**base, "chain_hash": chain_hash}
        _atomic_json(chain_file, {"slot_index": slot, "chain_hash": chain_hash})
        _atomic_json(state_root / "g070-reconciliation-current.json", payload)
        _atomic_json(
            slots / f"{slot}.result.json", {"status": state.value, "chain_hash": chain_hash}
        )
        return G070ReconciliationEvidence(**{**payload, "state": state})
    except Exception as error:
        _atomic_json(slots / f"{slot}.result.json", {"status": "UNKNOWN", "broker_post_count": 0})
        engage_g070_halt(state_root=state_root, reason="RECONCILIATION_RESULT_UNKNOWN")
        if isinstance(error, G070Error):
            raise
        raise G070Error("RECONCILIATION_RESULT_UNKNOWN_NO_RETRY") from error


def load_g070_reconciliation(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str, now_utc: datetime
) -> G070ReconciliationEvidence | None:
    path = state_root / "g070-reconciliation-current.json"
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["state"] = ReconciliationState(payload["state"])
        evidence = G070ReconciliationEvidence(**payload)
        observed = datetime.fromisoformat(evidence.observed_at_utc)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise G070Error("RECONCILIATION_EVIDENCE_INVALID") from error
    if (
        evidence.generation_digest != generation_digest
        or evidence.reviewed_files_digest != reviewed_files_digest
    ):
        raise G070Error("RECONCILIATION_DIGEST_MISMATCH")
    if now_utc.astimezone(UTC) - observed.astimezone(UTC) > timedelta(
        seconds=G070_MAX_EVIDENCE_AGE_SECONDS
    ):
        return G070ReconciliationEvidence(
            **{**asdict(evidence), "state": ReconciliationState.STALE}
        )
    return evidence


@dataclass(frozen=True)
class G070ReleaseCapability:
    generation_digest: str
    reviewed_files_digest: str
    reconciliation_chain_hash: str
    issued_at_utc: str
    artifact_digest: str


def activate_g070_release_once(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    canonical_g070: bool,
    independent_review_clear: bool,
    operation_60_passed: bool,
    reconciliation_runner: Callable[[], G070ReconciliationEvidence],
    now_utc: datetime,
) -> G070ReleaseCapability:
    if not all((canonical_g070, independent_review_clear, operation_60_passed)):
        raise G070Error("RELEASE_PRECONDITION_NOT_CLEAR")
    if (state_root / G070_PERSISTENT_HALT_FILE).exists():
        raise G070Error("PERSISTENT_HALT_PRESENT")
    started = state_root / "g070-release-activation.started.json"
    started.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(started, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise G070Error("RELEASE_ALREADY_STARTED_NO_RETRY") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump({"status": "STARTED", "generation_digest": generation_digest}, stream)
    try:
        evidence = reconciliation_runner()
    except Exception as error:
        engage_g070_halt(state_root=state_root, reason="RELEASE_RECONCILIATION_UNKNOWN")
        raise G070Error("RELEASE_RECONCILIATION_UNKNOWN_NO_RETRY") from error
    if evidence.state not in {ReconciliationState.FRESH_FLAT, ReconciliationState.FRESH_PROTECTED}:
        raise G070Error("RELEASE_RECONCILIATION_NOT_FRESH")
    base = {
        "schema": "H11_V4_G070_RELEASE_CAPABILITY_V1",
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "reconciliation_chain_hash": evidence.chain_hash,
        "issued_at_utc": now_utc.astimezone(UTC).isoformat(),
        "actual_post_authorized": False,
        "daily_authorization_required": False,
        "per_trade_confirmation_required": False,
    }
    digest = _canonical_hash(base)
    _atomic_json(state_root / G070_RELEASE_CAPABILITY_FILE, {**base, "artifact_digest": digest})
    return G070ReleaseCapability(
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
        reconciliation_chain_hash=evidence.chain_hash,
        issued_at_utc=base["issued_at_utc"],
        artifact_digest=digest,
    )


def load_g070_release_capability(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str
) -> G070ReleaseCapability | None:
    path = state_root / G070_RELEASE_CAPABILITY_FILE
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        artifact_digest = str(payload.pop("artifact_digest"))
        capability = G070ReleaseCapability(
            generation_digest=str(payload["generation_digest"]),
            reviewed_files_digest=str(payload["reviewed_files_digest"]),
            reconciliation_chain_hash=str(payload["reconciliation_chain_hash"]),
            issued_at_utc=str(payload["issued_at_utc"]),
            artifact_digest=artifact_digest,
        )
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise G070Error("RELEASE_CAPABILITY_INVALID") from error
    if (
        capability.generation_digest != generation_digest
        or capability.reviewed_files_digest != reviewed_files_digest
        or artifact_digest != _canonical_hash(payload)
        or payload.get("actual_post_authorized") is not False
    ):
        raise G070Error("RELEASE_CAPABILITY_BINDING_MISMATCH")
    return capability


@dataclass(frozen=True)
class G070OpaqueActionScope:
    generation_digest: str
    reviewed_files_digest: str
    cycle_ref: str
    action: G070Action
    symbol: str
    side: str
    quantity: int
    coordinator_digest: str
    expires_at_utc: str
    scope_digest: str

    def __bool__(self) -> bool:
        return False


class G070ActionScopeStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def issue(
        self,
        *,
        release: G070ReleaseCapability,
        cycle_ref: str,
        action: G070Action,
        symbol: str,
        side: str,
        quantity: int,
        coordinator_digest: str,
        now_utc: datetime,
        lifetime_seconds: int = 15,
    ) -> G070OpaqueActionScope:
        if symbol != "USD_JPY" or side not in {"BUY", "SELL"} or quantity <= 0:
            raise G070Error("ACTION_SCOPE_REQUEST_INVALID")
        stable_binding = {
            "generation_digest": release.generation_digest,
            "reviewed_files_digest": release.reviewed_files_digest,
            "cycle_ref": cycle_ref,
            "action": action.value,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "coordinator_digest": coordinator_digest,
        }
        reservation_digest = _canonical_hash(stable_binding)
        reservation = (
            self._root / "reservations" / f"{reservation_digest.removeprefix('sha256:')}.json"
        )
        reservation.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(reservation, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise G070Error("ACTION_SCOPE_ALREADY_RESERVED_NO_RETRY") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    **stable_binding,
                    "reservation_digest": reservation_digest,
                    "status": "RESERVED",
                },
                stream,
                sort_keys=True,
            )
        base = {
            **stable_binding,
            "expires_at_utc": (
                now_utc.astimezone(UTC) + timedelta(seconds=lifetime_seconds)
            ).isoformat(),
        }
        digest = _canonical_hash(base)
        issued = self._root / "issued" / f"{digest.removeprefix('sha256:')}.json"
        issued.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(issued, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise G070Error("ACTION_SCOPE_ALREADY_ISSUED_NO_RETRY") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({**base, "scope_digest": digest}, stream, sort_keys=True)
        return G070OpaqueActionScope(**{**base, "action": action, "scope_digest": digest})

    def consume_exact(
        self,
        scope: G070OpaqueActionScope,
        *,
        generation_digest: str,
        reviewed_files_digest: str,
        cycle_ref: str,
        action: G070Action,
        symbol: str,
        side: str,
        quantity: int,
        coordinator_digest: str,
        now_utc: datetime,
    ) -> None:
        expected = (
            scope.generation_digest == generation_digest,
            scope.reviewed_files_digest == reviewed_files_digest,
            scope.cycle_ref == cycle_ref,
            scope.action is action,
            scope.symbol == symbol,
            scope.side == side,
            scope.quantity == quantity,
            scope.coordinator_digest == coordinator_digest,
            now_utc.astimezone(UTC) <= datetime.fromisoformat(scope.expires_at_utc).astimezone(UTC),
        )
        if not all(expected):
            raise G070Error("ACTION_SCOPE_EXACT_BINDING_MISMATCH")
        consumed = self._root / "consumed" / f"{scope.scope_digest.removeprefix('sha256:')}.json"
        consumed.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(consumed, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise G070Error("ACTION_SCOPE_ALREADY_CONSUMED_NO_RETRY") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"scope_digest": scope.scope_digest, "status": "CONSUMED"}, stream)


class G070OwnerLock:
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
                raise G070Error("PROCESS_LOCK_INVALID") from error
            if self.pid_alive(existing):
                raise G070Error("PROCESS_LOCK_CONFLICT")
            self.path.unlink()
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise G070Error("PROCESS_LOCK_CONFLICT") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid()}, stream)
        self.acquired = True

    def release(self) -> None:
        if self.acquired and self.path.is_file() and not self.path.is_symlink():
            self.path.unlink()
        self.acquired = False


@dataclass
class G070ResidentSupervisor:
    state_root: Path
    generation_digest: str
    reviewed_files_digest: str
    reconciliation_runner: Callable[[datetime], G070ReconciliationEvidence] | None = None
    exit_manager: Callable[[G070Projection], None] | None = None
    entry_evaluator: Callable[[G070Projection], None] | None = None

    def tick(self, *, now_utc: datetime, arm_state: ArmState) -> G070Projection:
        if (self.state_root / G070_PERSISTENT_HALT_FILE).exists():
            projection = project_g070_runtime(
                G070ProjectionInput(
                    ControlPlaneState.HALTED, ReconciliationState.UNKNOWN, arm_state
                )
            )
        else:
            release_ready = (
                load_g070_release_capability(
                    state_root=self.state_root,
                    generation_digest=self.generation_digest,
                    reviewed_files_digest=self.reviewed_files_digest,
                )
                is not None
            )
            evidence = load_g070_reconciliation(
                state_root=self.state_root,
                generation_digest=self.generation_digest,
                reviewed_files_digest=self.reviewed_files_digest,
                now_utc=now_utc,
            )
            due = evidence is None or _safe_slot(now_utc) > evidence.slot_index
            if due and self.reconciliation_runner is not None:
                evidence = self.reconciliation_runner(now_utc)
            state = evidence.state if evidence is not None else ReconciliationState.REQUIRED
            exit_manager_ready = self.exit_manager is not None
            if evidence and evidence.position_open and not exit_manager_ready:
                projection = project_g070_runtime(
                    G070ProjectionInput(
                        ControlPlaneState.HALTED,
                        state,
                        arm_state,
                        position_open=True,
                    )
                )
            else:
                projection = project_g070_runtime(
                    G070ProjectionInput(
                        control_plane_state=ControlPlaneState.READY,
                        reconciliation_state=state,
                        arm_state=arm_state,
                        position_open=bool(evidence and evidence.position_open),
                        ownership_exact=bool(evidence and evidence.ownership_exact),
                        quantity_matches=bool(evidence and evidence.quantity_matches),
                        protection_confirmed=bool(evidence and evidence.protection_confirmed),
                        entry_gates_clear=bool(
                            evidence
                            and state is ReconciliationState.FRESH_FLAT
                            and release_ready
                            and self.entry_evaluator is not None
                        ),
                    )
                )
        status = {
            **{
                key: (value.value if isinstance(value, Enum) else value)
                for key, value in asdict(projection).items()
            },
            "generation_label": G070_GENERATION_LABEL,
            "generation_digest": self.generation_digest,
            "reviewed_files_digest": self.reviewed_files_digest,
            "heartbeat_at_utc": now_utc.astimezone(UTC).isoformat(),
            "dead_man_alive": True,
            "lock_single_owner": True,
            "broker_write": False,
            "actual_post_count": 0,
        }
        _atomic_json(self.state_root / G070_RUNTIME_STATUS_FILE, status)
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
        chain_index = 1
        previous_hash = "sha256:" + "0" * 64
        if chain_path.is_file() and not chain_path.is_symlink():
            prior = json.loads(chain_path.read_text(encoding="utf-8"))
            chain_index = int(prior.get("chain_index", 0)) + 1
            previous_hash = str(prior.get("chain_hash", previous_hash))
        chain_base = {**heartbeat, "chain_index": chain_index, "previous_chain_hash": previous_hash}
        _atomic_json(chain_path, {**chain_base, "chain_hash": _canonical_hash(chain_base)})
        if (
            projection.effective_state in {EffectiveState.ON_EXIT_ONLY, EffectiveState.EXIT_ONLY}
            and self.exit_manager
        ):
            self.exit_manager(projection)
        if projection.entry_gate_open and self.entry_evaluator:
            self.entry_evaluator(projection)
        return projection


def safe_g070_api_status(
    *, state_root: Path, arm_on: bool, generation_digest: str, reviewed_files_digest: str
) -> dict[str, object]:
    path = state_root / G070_RUNTIME_STATUS_FILE
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
            raise G070Error("RUNTIME_STATUS_DIGEST_MISMATCH")
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
    return {
        "control_plane_state": projection.control_plane_state.value,
        "reconciliation_state": projection.reconciliation_state.value,
        "effective_state": projection.effective_state.value,
        "entry_gate_open": projection.entry_gate_open,
        "entry_state": projection.entry_state.value,
        "safe_reason_label": projection.safe_reason_label,
    }


def verify_g070_scheduler_binding(
    *,
    generation: object,
    repository: Path,
    plist_path: Path,
    state_root: Path,
    now_utc: datetime,
) -> None:
    if getattr(generation, "generation_label", None) != G070_GENERATION_LABEL:
        raise G070Error("G070_GENERATION_REQUIRED")
    if (state_root / G070_PERSISTENT_HALT_FILE).exists() or (
        state_root / G070_PERSISTENT_HALT_FILE
    ).is_symlink():
        raise G070Error("PERSISTENT_HALT_PRESENT")
    if not plist_path.is_file() or plist_path.is_symlink():
        raise G070Error("SCHEDULER_PLIST_INVALID")
    try:
        plist = plistlib.loads(plist_path.read_bytes())
        arguments = plist["ProgramArguments"]
    except (OSError, KeyError, TypeError, ValueError, plistlib.InvalidFileException) as error:
        raise G070Error("SCHEDULER_PLIST_INVALID") from error
    try:
        repository_index = arguments.index("--repository")
        reviewed_index = arguments.index("--expected-reviewed-files-digest")
        generation_index = arguments.index("--expected-generation-digest")
    except (AttributeError, ValueError) as error:
        raise G070Error("SCHEDULER_BINDING_MISMATCH") from error
    if (
        not any(
            str(argument).endswith("h11_auto_v4_g070_runtime_bootstrap_no_post.py")
            for argument in arguments
        )
        or arguments[reviewed_index + 1] != getattr(generation, "implementation_digest", None)
        or arguments[generation_index + 1] != getattr(generation, "digest", None)
        or repository.is_symlink()
        or not repository.is_dir()
        or arguments[repository_index + 1] != str(repository.resolve())
    ):
        raise G070Error("SCHEDULER_BINDING_MISMATCH")
    for name in (
        "heartbeat.json",
        "process.lock",
        "dead-man.json",
        "heartbeat-chain.json",
        G070_RUNTIME_STATUS_FILE,
    ):
        path = state_root / name
        if not path.is_file() or path.is_symlink():
            raise G070Error("RUNTIME_READINESS_MISSING")
    try:
        heartbeat = json.loads((state_root / "heartbeat.json").read_text(encoding="utf-8"))
        dead_man = json.loads((state_root / "dead-man.json").read_text(encoding="utf-8"))
        chain = json.loads((state_root / "heartbeat-chain.json").read_text(encoding="utf-8"))
        status = json.loads((state_root / G070_RUNTIME_STATUS_FILE).read_text(encoding="utf-8"))
        lock = json.loads((state_root / "process.lock").read_text(encoding="utf-8"))
        observed = datetime.fromisoformat(heartbeat["heartbeat_at_utc"])
        dead_man_observed = datetime.fromisoformat(dead_man["heartbeat_at_utc"])
        chain_observed = datetime.fromisoformat(chain["heartbeat_at_utc"])
        chain_payload = {key: value for key, value in chain.items() if key != "chain_hash"}
        lock_pid = int(lock["pid"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise G070Error("RUNTIME_READINESS_INVALID") from error
    expected_generation = getattr(generation, "digest", None)
    expected_reviewed = getattr(generation, "implementation_digest", None)
    if (
        heartbeat.get("generation_digest") != expected_generation
        or heartbeat.get("reviewed_files_digest") != expected_reviewed
        or heartbeat.get("broker_write") is not False
        or heartbeat.get("actual_post_count") != 0
        or dead_man.get("generation_digest") != expected_generation
        or dead_man.get("reviewed_files_digest") != expected_reviewed
        or dead_man.get("alive") is not True
        or chain.get("generation_digest") != expected_generation
        or chain.get("reviewed_files_digest") != expected_reviewed
        or int(chain.get("chain_index", 0)) < 1
        or chain.get("chain_hash") != _canonical_hash(chain_payload)
        or status.get("generation_digest") != expected_generation
        or status.get("reviewed_files_digest") != expected_reviewed
        or status.get("control_plane_state") == ControlPlaneState.HALTED.value
        or status.get("broker_write") is not False
        or status.get("actual_post_count") != 0
        or lock_pid <= 0
        or not _pid_alive(lock_pid)
        or now_utc.astimezone(UTC) - observed.astimezone(UTC) > timedelta(seconds=60)
        or now_utc.astimezone(UTC) - dead_man_observed.astimezone(UTC) > timedelta(seconds=60)
        or now_utc.astimezone(UTC) - chain_observed.astimezone(UTC) > timedelta(seconds=60)
    ):
        raise G070Error("RUNTIME_READINESS_NOT_CLEAR")


def verify_g070_review_artifacts(
    *, repository: Path, generation_digest: str, reviewed_files_digest: str
) -> None:
    root = repository / "docs/templates"
    files = (
        root / "h11_v4_g070_frozen_generation.json",
        root / "h11_v4_g070_runtime_commissioning_evidence.json",
        root / "h11_v4_g070_independent_review_attestation.json",
    )
    try:
        manifest = json.loads(files[0].read_text(encoding="utf-8"))
        evidence = json.loads(files[1].read_text(encoding="utf-8"))
        attestation = json.loads(files[2].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise G070Error("G070_REVIEW_ARTIFACT_INVALID") from error
    calculated_generation_digest = _canonical_hash(
        {
            key: value
            for key, value in manifest.items()
            if key
            not in {
                "runtime_commissioning_evidence_digest",
                "successor_halt_release_digest",
            }
        }
    )
    calculated_evidence_digest = _canonical_hash(
        {key: value for key, value in evidence.items() if key != "artifact_digest"}
    )
    calculated_attestation_digest = _canonical_hash(
        {key: value for key, value in attestation.items() if key != "artifact_digest"}
    )
    if (
        manifest.get("implementation_digest") != reviewed_files_digest
        or calculated_generation_digest != generation_digest
        or evidence.get("generation_digest") != generation_digest
        or attestation.get("generation_digest") != generation_digest
        or evidence.get("reviewed_files_digest") != reviewed_files_digest
        or attestation.get("reviewed_files_digest") != reviewed_files_digest
        or evidence.get("artifact_digest") != calculated_evidence_digest
        or attestation.get("artifact_digest") != calculated_attestation_digest
        or manifest.get("runtime_commissioning_evidence_digest") != calculated_evidence_digest
        or manifest.get("successor_halt_release_digest") != calculated_attestation_digest
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
        or evidence.get("actual_post_authorized") is not False
        or evidence.get("broker_post_authorized") is not False
        or evidence.get("broker_write") is not False
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
        or attestation.get("architecture_status") != "CLEAR"
        or attestation.get("safety_status") != "CLEAR"
        or attestation.get("operations_status") != "CLEAR"
        or attestation.get("blocking_findings") != []
    ):
        raise G070Error("G070_REVIEW_ARTIFACT_BINDING_MISMATCH")
