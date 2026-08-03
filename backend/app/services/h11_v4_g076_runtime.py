"""G076 final switch-control runtime contracts.

G076 connects the resident lifecycle to generation-bound reconciliation,
strategy evaluation, and one-shot action scopes.  All transports are injected
protocols.  The default resident path has no transport, no credential loader,
and no write capability; fake ports are the only ports used by this module's
tests.  A real release activation remains a separate boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
import secrets
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Protocol

G076_GENERATION_LABEL = "H11_AUTO_30M_20260802_G076"
G076_PERSISTENT_HALT_FILE = "g076-persistent-halt.json"
G076_RUNTIME_STATUS_FILE = "g076-runtime-status.json"
G076_RECONCILIATION_FILE = "g076-reconciliation-current.json"
G076_OPERATION_60_STARTED_FILE = "g076-operation-60.started.json"
G076_OPERATION_60_RESULT_FILE = "g076-operation-60.result.json"
G076_INITIAL_TRANSACTION_STARTED_FILE = "g076-initial-activation.started.json"
G076_INITIAL_TRANSACTION_OUTCOME_FILE = "g076-initial-activation.outcome.json"
G076_SWITCH_CAPABILITY_FILE = "g076-switch-control-capability.json"
G076_RELEASE_CAPABILITY_FILE = "g076-release-capability.json"
G076_RECOVERY_SCOPE_FILE = "g076-recovery-scope.json"
G076_MAX_EVIDENCE_AGE_SECONDS = 60
G076_RECONCILIATION_INTERVAL_SECONDS = 15
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_CYCLE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_G076_REVIEWED_ARTIFACTS = frozenset(
    {
        "docs/templates/h11_v4_g076_frozen_generation.json",
        "docs/templates/h11_v4_g076_runtime_commissioning_evidence.json",
        "docs/templates/h11_v4_g076_independent_review_attestation.json",
    }
)
_G076_BINDING_FIELDS = frozenset(
    {
        "artifact_digest",
        "generation_digest",
        "implementation_digest",
        "reviewed_files_digest",
        "runtime_commissioning_evidence_digest",
        "successor_halt_release_digest",
    }
)


class G076Error(ValueError):
    """Safe-label-only G076 failure."""


_G076_FAKE_MODULE_PREFIXES = (
    "app.services.h11_v4_g076",
    "app.tests.h11_auto.test_v4_g076",
    "scripts.h11_auto_v4_g076",
)


def _g076_fake_module_allowed(value: object) -> bool:
    module = value if isinstance(value, str) else getattr(value, "__module__", "")
    return any(
        module == prefix
        or module.startswith(prefix + ".")
        or module.startswith(prefix + "_")
        for prefix in _G076_FAKE_MODULE_PREFIXES
    )


class G076FakeOnlyPort:
    """Sealed marker for dependencies that are synthetic by construction."""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not _g076_fake_module_allowed(cls):
            raise TypeError("G076_FAKE_ONLY_PORT_MODULE_REQUIRED")


def _g076_fake_port(value: object) -> bool:
    return isinstance(value, G076FakeOnlyPort) and _g076_fake_module_allowed(type(value))


@dataclass(frozen=True)
class G076FakeOnlyCallable:
    callback: Callable[..., object]

    def __post_init__(self) -> None:
        if not _g076_fake_module_allowed(self.callback):
            raise G076Error("G076_FAKE_ONLY_CALLABLE_MODULE_REQUIRED")

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self.callback(*args, **kwargs)


def compute_g076_reviewed_files_digest(*, repository: Path) -> str:
    """Compute a stable candidate digest without self-referential bindings."""

    from h11_v4_reviewed_digest import REVIEWED_FILES

    digest = hashlib.sha256()
    root = repository.resolve()
    for relative in REVIEWED_FILES:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise G076Error("G076_REVIEWED_FILE_INVALID")
        content = path.read_bytes()
        if relative in _G076_REVIEWED_ARTIFACTS:
            try:
                payload = json.loads(content)
                if not isinstance(payload, dict):
                    raise TypeError
                for field_name in _G076_BINDING_FIELDS:
                    if field_name in payload:
                        payload[field_name] = None
                content = json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                ).encode()
            except (json.JSONDecodeError, TypeError) as error:
                raise G076Error("G076_REVIEWED_ARTIFACT_INVALID") from error
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


class G076ArmState(str, Enum):
    OFF = "OFF"
    ON = "ON"


class G076ReleaseState(str, Enum):
    LOCKED = "LOCKED"
    ENABLED = "ENABLED"


class G076EffectiveState(str, Enum):
    OFF = "OFF"
    ON_WAITING = "ON_WAITING"
    ON_EXIT_ONLY = "ON_EXIT_ONLY"
    EXIT_ONLY = "EXIT_ONLY"
    HALTED = "HALTED"


class G076EntryState(str, Enum):
    DISABLED = "DISABLED"
    WAITING_FOR_RECONCILIATION = "WAITING_FOR_RECONCILIATION"
    WAITING_FOR_SIGNAL = "WAITING_FOR_SIGNAL"
    ENTRY_READY = "ENTRY_READY"
    ACTION_IN_PROGRESS = "ACTION_IN_PROGRESS"
    BLOCKED_POSITION_OPEN = "BLOCKED_POSITION_OPEN"
    HALTED = "HALTED"


class G076ReconciliationState(str, Enum):
    REQUIRED = "REQUIRED"
    IN_PROGRESS = "IN_PROGRESS"
    FRESH_FLAT = "FRESH_FLAT"
    FRESH_PROTECTED = "FRESH_PROTECTED"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"


class G076ActionState(str, Enum):
    IDLE = "IDLE"
    STARTED = "STARTED"
    RESULT_KNOWN = "RESULT_KNOWN"
    UNKNOWN = "UNKNOWN"


class G076ExitState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PROTECTED = "PROTECTED"
    EXIT_DUE = "EXIT_DUE"
    EXIT_IN_PROGRESS = "EXIT_IN_PROGRESS"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


class G076Action(str, Enum):
    ENTRY = "ENTRY"
    PROTECTION = "PROTECTION"
    CANCEL_PROTECTION = "CANCEL_PROTECTION"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TIME_EXIT = "TIME_EXIT"
    CLOSE_POSITION = "CLOSE_POSITION"


class G076ActionOutcome(str, Enum):
    ACCEPTED = "ACCEPTED_KNOWN"
    PROTECTED = "PROTECTED_KNOWN"
    FLAT = "FLAT_KNOWN"
    UNKNOWN = "UNKNOWN"


def _canonical_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    if path.is_symlink():
        raise G076Error("G076_SYMLINK_PATH_REFUSED")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    _fsync_parent(path)


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _exclusive_json(path: Path, payload: Mapping[str, object]) -> None:
    if path.is_symlink():
        raise G076Error("G076_SYMLINK_PATH_REFUSED")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise G076Error("G076_ONE_USE_MARKER_ALREADY_EXISTS_NO_RETRY") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    _fsync_parent(path)


def _read_json(path: Path, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise G076Error(label)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G076Error(label) from error
    if not isinstance(payload, dict):
        raise G076Error(label)
    return payload


def _require_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise G076Error(label)
    return value


@dataclass(frozen=True)
class G076SanitizedSnapshot:
    latest_execution_count: int
    open_position_count: int
    active_order_count: int
    position_side: str | None = None
    ownership_exact: bool = False
    quantity_matches: bool = False
    protection_confirmed: bool = False
    broker_get_count: int = 0
    private_api_read_count: int = 0
    credential_read_count: int = 0
    broker_write: bool = False
    broker_post_count: int = 0
    pending_transport: bool = False
    unknown: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.latest_execution_count,
            self.open_position_count,
            self.active_order_count,
            self.broker_get_count,
            self.private_api_read_count,
            self.credential_read_count,
            self.broker_post_count,
        ):
            if type(value) is not int or value < 0:
                raise G076Error("G076_SNAPSHOT_COUNT_INVALID")
        if self.broker_get_count > 3:
            raise G076Error("G076_SNAPSHOT_READ_COUNT_INVALID")
        if self.private_api_read_count != 0 or self.credential_read_count != 0:
            raise G076Error("G076_SNAPSHOT_READ_COUNT_INVALID")
        if self.broker_write is not False:
            raise G076Error("G076_SNAPSHOT_BOUNDARY_VIOLATION")
        if self.broker_post_count != 0:
            raise G076Error("G076_SNAPSHOT_POST_COUNT_INVALID")
        if any(
            type(value) is not bool
            for value in (
                self.ownership_exact,
                self.quantity_matches,
                self.protection_confirmed,
                self.pending_transport,
                self.unknown,
            )
        ):
            raise G076Error("G076_SNAPSHOT_BOOLEAN_INVALID")
        if self.position_side not in {None, "BUY", "SELL"}:
            raise G076Error("G076_SNAPSHOT_SIDE_INVALID")
        if (self.open_position_count == 0) is (self.position_side is not None):
            raise G076Error("G076_SNAPSHOT_SIDE_MISMATCH")


@dataclass(frozen=True)
class G076ReconciliationEvidence:
    generation_label: str
    generation_digest: str
    reviewed_files_digest: str
    cycle_id: str
    observed_at_utc: str
    state: G076ReconciliationState
    latest_execution_count: int
    open_position_count: int
    active_order_count: int
    position_side: str | None
    position_open: bool
    account_flat: bool
    active_orders_zero: bool
    ownership_exact: bool
    quantity_matches: bool
    protection_confirmed: bool
    broker_get_count: int
    private_api_read_count: int
    credential_read_count: int
    broker_write: bool
    broker_post_count: int
    pending_transport: bool
    artifact_digest: str


def _snapshot_state(snapshot: G076SanitizedSnapshot) -> G076ReconciliationState:
    if snapshot.unknown or snapshot.pending_transport:
        return G076ReconciliationState.UNKNOWN
    if snapshot.open_position_count == 0:
        return (
            G076ReconciliationState.FRESH_FLAT
            if snapshot.active_order_count == 0
            else G076ReconciliationState.UNKNOWN
        )
    if snapshot.open_position_count != 1:
        return G076ReconciliationState.UNKNOWN
    if snapshot.active_order_count > 0 and all(
        (snapshot.ownership_exact, snapshot.quantity_matches, snapshot.protection_confirmed)
    ):
        return G076ReconciliationState.FRESH_PROTECTED
    return G076ReconciliationState.UNKNOWN


def _evidence_from_snapshot(
    *,
    snapshot: G076SanitizedSnapshot,
    generation_digest: str,
    reviewed_files_digest: str,
    cycle_id: str,
    now_utc: datetime,
) -> G076ReconciliationEvidence:
    _require_digest(generation_digest, "G076_GENERATION_DIGEST_INVALID")
    _require_digest(reviewed_files_digest, "G076_REVIEWED_DIGEST_INVALID")
    if not _CYCLE.fullmatch(cycle_id) or now_utc.tzinfo is None:
        raise G076Error("G076_CYCLE_INPUT_INVALID")
    state = _snapshot_state(snapshot)
    base: dict[str, object] = {
        "generation_label": G076_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "cycle_id": cycle_id,
        "observed_at_utc": now_utc.astimezone(UTC).isoformat(),
        "state": state.value,
        "latest_execution_count": snapshot.latest_execution_count,
        "open_position_count": snapshot.open_position_count,
        "active_order_count": snapshot.active_order_count,
        "position_side": snapshot.position_side,
        "position_open": snapshot.open_position_count > 0,
        "account_flat": snapshot.open_position_count == 0,
        "active_orders_zero": snapshot.active_order_count == 0,
        "ownership_exact": snapshot.ownership_exact,
        "quantity_matches": snapshot.quantity_matches,
        "protection_confirmed": snapshot.protection_confirmed,
        "broker_get_count": snapshot.broker_get_count,
        "private_api_read_count": snapshot.private_api_read_count,
        "credential_read_count": snapshot.credential_read_count,
        "broker_write": False,
        "broker_post_count": 0,
        "pending_transport": snapshot.pending_transport,
    }
    return G076ReconciliationEvidence(
        **{key: value for key, value in base.items() if key != "state"},
        state=state,
        artifact_digest=_canonical_hash(base),
    )


class G076ReadOnlyReconciler(Protocol):
    def reconcile_once(self, *, cycle_id: str, now_utc: datetime) -> G076SanitizedSnapshot: ...


def run_g076_reconciliation_cycle_once(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    cycle_id: str,
    reconciler: G076ReadOnlyReconciler,
    now_utc: datetime,
) -> G076ReconciliationEvidence:
    marker = state_root / f"g076-reconciliation-{cycle_id}.started.json"
    outcome = state_root / f"g076-reconciliation-{cycle_id}.outcome.json"
    if not _CYCLE.fullmatch(cycle_id):
        raise G076Error("G076_CYCLE_ID_INVALID")
    if not _g076_fake_port(reconciler):
        raise G076Error("G076_FAKE_ONLY_RECONCILER_REQUIRED")
    if marker.exists() or marker.is_symlink() or outcome.exists() or outcome.is_symlink():
        raise G076Error("G076_RECONCILIATION_CYCLE_ALREADY_STARTED_NO_RETRY")
    _exclusive_json(
        marker,
        {
            "generation_label": G076_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "cycle_id": cycle_id,
            "status": "STARTED",
        },
    )
    snapshot: G076SanitizedSnapshot | None = None
    try:
        snapshot = reconciler.reconcile_once(cycle_id=cycle_id, now_utc=now_utc)
        evidence = _evidence_from_snapshot(
            snapshot=snapshot,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
            cycle_id=cycle_id,
            now_utc=now_utc,
        )
        _atomic_json(
            state_root / G076_RECONCILIATION_FILE,
            {
                **asdict(evidence),
                "state": evidence.state.value,
            },
        )
        _exclusive_json(
            outcome,
            {
                "status": "PASSED"
                if evidence.state
                not in {
                    G076ReconciliationState.UNKNOWN,
                }
                else "UNKNOWN",
                "generation_label": G076_GENERATION_LABEL,
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "cycle_id": cycle_id,
                "broker_post_count": 0,
                "private_api_read_count": evidence.private_api_read_count,
                "credential_read_count": evidence.credential_read_count,
            },
        )
        if evidence.state is G076ReconciliationState.UNKNOWN:
            engage_g076_halt(state_root=state_root, reason="G076_RECONCILIATION_UNKNOWN")
            raise G076Error("G076_RECONCILIATION_UNKNOWN_NO_RETRY")
        return evidence
    except Exception as error:
        if not outcome.exists() and not outcome.is_symlink():
            counts = (
                (0, 0, 0)
                if snapshot is None
                else (
                    snapshot.broker_get_count,
                    snapshot.private_api_read_count,
                    snapshot.credential_read_count,
                )
            )
            _exclusive_json(
                outcome,
                {
                    "status": "UNKNOWN",
                    "generation_label": G076_GENERATION_LABEL,
                    "generation_digest": generation_digest,
                    "reviewed_files_digest": reviewed_files_digest,
                    "cycle_id": cycle_id,
                    "broker_get_count": counts[0],
                    "private_api_read_count": counts[1],
                    "credential_read_count": counts[2],
                    "broker_post_count": 0,
                },
            )
        engage_g076_halt(state_root=state_root, reason="G076_RECONCILIATION_UNKNOWN")
        if isinstance(error, G076Error):
            raise
        raise G076Error("G076_RECONCILIATION_UNKNOWN_NO_RETRY") from error


def load_g076_reconciliation(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str, now_utc: datetime
) -> G076ReconciliationEvidence | None:
    path = state_root / G076_RECONCILIATION_FILE
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = _read_json(path, "G076_RECONCILIATION_INVALID")
        state = G076ReconciliationState(payload.pop("state"))
        artifact_digest = str(payload.pop("artifact_digest"))
        evidence = G076ReconciliationEvidence(
            **payload, state=state, artifact_digest=artifact_digest
        )
    except (G076Error, KeyError, TypeError, ValueError) as error:
        raise G076Error("G076_RECONCILIATION_INVALID") from error
    calculated = _canonical_hash(
        {**asdict(evidence), "state": evidence.state.value, "artifact_digest": None}
    )
    # The writer hashes the same fields without artifact_digest; keep the comparison explicit.
    calculated = _canonical_hash(
        {
            key: value
            for key, value in {**asdict(evidence), "state": evidence.state.value}.items()
            if key != "artifact_digest"
        }
    )
    observed = datetime.fromisoformat(evidence.observed_at_utc).astimezone(UTC)
    age = (now_utc.astimezone(UTC) - observed).total_seconds()
    if (
        evidence.generation_digest != generation_digest
        or evidence.reviewed_files_digest != reviewed_files_digest
        or evidence.artifact_digest != calculated
    ):
        raise G076Error("G076_RECONCILIATION_DIGEST_MISMATCH")
    if age < 0 or age > G076_MAX_EVIDENCE_AGE_SECONDS:
        return replace(evidence, state=G076ReconciliationState.STALE)
    return evidence


def _mark_g076_reconciliation_stale(
    *, state_root: Path, evidence: G076ReconciliationEvidence, now_utc: datetime
) -> G076ReconciliationEvidence:
    stale = replace(
        evidence,
        state=G076ReconciliationState.STALE,
        observed_at_utc=now_utc.astimezone(UTC).isoformat(),
        artifact_digest="",
    )
    base = {
        key: value
        for key, value in {**asdict(stale), "state": stale.state.value}.items()
        if key != "artifact_digest"
    }
    stale = replace(stale, artifact_digest=_canonical_hash(base))
    _atomic_json(
        state_root / G076_RECONCILIATION_FILE,
        {**asdict(stale), "state": stale.state.value},
    )
    return stale


def engage_g076_halt(*, state_root: Path, reason: str) -> None:
    path = state_root / G076_PERSISTENT_HALT_FILE
    if path.exists() or path.is_symlink():
        return
    _atomic_json(
        path,
        {
            "generation_label": G076_GENERATION_LABEL,
            "status": "HALTED",
            "reason": reason,
            "broker_write": False,
            "actual_post_count": 0,
        },
    )


@dataclass(frozen=True)
class G076StrategyObservation:
    strategy_artifact_digest: str
    strategy_version: str
    symbol: str
    quantity: int
    side: str
    horizon: str
    generation_digest: str
    reviewed_files_digest: str
    signal_actionable: bool
    risk_clear: bool
    market_open: bool
    spread_clear: bool
    quote_fresh: bool
    signal_fresh: bool
    limits_clear: bool
    position_flat: bool
    active_orders_zero: bool
    pending_transport: bool = False
    action_in_progress: bool = False


@dataclass(frozen=True)
class G076StrategyDecision:
    evaluation_known: bool
    strategy_artifact_bound: bool
    signal_actionable: bool
    risk_clear: bool
    market_open: bool
    spread_clear: bool
    freshness_clear: bool
    limits_clear: bool
    generation_digest: str
    reviewed_files_digest: str
    strategy_artifact_digest: str
    side: str
    actual_post_authorized: bool = False
    broker_post_authorized: bool = False

    def binding_valid(self, *, generation_digest: str, reviewed_files_digest: str) -> bool:
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


class G076StrategyObservationSource(Protocol):
    def observe(self, *, now_utc: datetime) -> G076StrategyObservation: ...


class G076FrozenStrategyEvaluator:
    """Concrete evaluator bound to the frozen strategy artifact and digests."""

    def __init__(
        self,
        *,
        source: G076StrategyObservationSource,
        generation_digest: str,
        reviewed_files_digest: str,
        strategy_artifact_digest: str,
    ) -> None:
        if not _g076_fake_port(source):
            raise G076Error("G076_FAKE_ONLY_STRATEGY_SOURCE_REQUIRED")
        self.source = source
        self.generation_digest = _require_digest(
            generation_digest, "G076_GENERATION_DIGEST_INVALID"
        )
        self.reviewed_files_digest = _require_digest(
            reviewed_files_digest, "G076_REVIEWED_DIGEST_INVALID"
        )
        self.strategy_artifact_digest = _require_digest(
            strategy_artifact_digest, "G076_STRATEGY_DIGEST_INVALID"
        )

    def evaluate(
        self, *, now_utc: datetime, evidence: G076ReconciliationEvidence
    ) -> G076StrategyDecision:
        observation = self.source.observe(now_utc=now_utc)
        bound = (
            observation.generation_digest == self.generation_digest
            and observation.reviewed_files_digest == self.reviewed_files_digest
            and observation.strategy_artifact_digest == self.strategy_artifact_digest
            and observation.strategy_version == "SHORT_V1"
            and observation.symbol == "USD_JPY"
            and observation.quantity == 1_000
            and observation.side in {"BUY", "SELL"}
            and observation.horizon == "30m"
            and observation.position_flat is (evidence.state is G076ReconciliationState.FRESH_FLAT)
            and observation.active_orders_zero is (evidence.active_order_count == 0)
        )
        return G076StrategyDecision(
            evaluation_known=True,
            strategy_artifact_bound=bound,
            signal_actionable=observation.signal_actionable,
            risk_clear=observation.risk_clear,
            market_open=observation.market_open,
            spread_clear=observation.spread_clear,
            freshness_clear=observation.quote_fresh and observation.signal_fresh,
            limits_clear=observation.limits_clear,
            generation_digest=observation.generation_digest,
            reviewed_files_digest=observation.reviewed_files_digest,
            strategy_artifact_digest=observation.strategy_artifact_digest,
            side=observation.side,
        )


@dataclass(frozen=True)
class G076ActionScope:
    generation_digest: str
    reviewed_files_digest: str
    release_capability_digest: str
    reconciliation_artifact_digest: str
    strategy_artifact_digest: str
    cycle_id: str
    action: G076Action
    symbol: str
    quantity: int
    side: str
    expires_at_utc: str
    action_key: str
    scope_digest: str

    def __bool__(self) -> bool:
        return False


class G076ActionPort(Protocol):
    def attempt_once(self, scope: G076ActionScope) -> G076ActionOutcome: ...


@dataclass(frozen=True)
class G076RecoveryScope:
    generation_digest: str
    reviewed_files_digest: str
    release_capability_digest: str
    reconciliation_artifact_digest: str
    cycle_id: str
    symbol: str
    quantity: int
    side: str
    expires_at_utc: str
    ownership_exact: bool
    quantity_matches: bool
    protection_confirmed: bool
    action_key: str
    scope_digest: str

    def __bool__(self) -> bool:
        return False

    @property
    def cycle_ref(self) -> str:
        return self.cycle_id

    @property
    def size(self) -> int:
        return self.quantity

    @property
    def execution_type(self) -> str:
        return "RECOVERED_EXIT_ONLY"


def build_g076_recovery_scope(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    evidence: G076ReconciliationEvidence,
    side: str,
    action_key: str,
    now_utc: datetime,
    lifetime_seconds: int = 15,
) -> G076RecoveryScope:
    """Bind restart recovery to fresh, explicitly protected ownership evidence."""

    release_digest = load_g076_release_capability_digest(
        state_root=state_root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
    )
    action_digest = _require_digest(action_key, "G076_RECOVERY_ACTION_KEY_INVALID")
    if (
        side not in {"BUY", "SELL"}
        or now_utc.tzinfo is None
        or lifetime_seconds < 1
        or lifetime_seconds > 60
        or
        evidence.state is not G076ReconciliationState.FRESH_PROTECTED
        or evidence.generation_digest != generation_digest
        or evidence.reviewed_files_digest != reviewed_files_digest
        or evidence.position_open is not True
        or evidence.open_position_count != 1
        or evidence.ownership_exact is not True
        or evidence.quantity_matches is not True
        or evidence.protection_confirmed is not True
    ):
        raise G076Error("G076_RECOVERY_EVIDENCE_NOT_CLEAR")
    base: dict[str, object] = {
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "release_capability_digest": release_digest,
        "reconciliation_artifact_digest": evidence.artifact_digest,
        "cycle_id": evidence.cycle_id,
        "symbol": "USD_JPY",
        "quantity": 1_000,
        "side": side,
        "expires_at_utc": (
            now_utc.astimezone(UTC) + timedelta(seconds=lifetime_seconds)
        ).isoformat(),
        "ownership_exact": True,
        "quantity_matches": True,
        "protection_confirmed": True,
        "action_key": action_digest,
    }
    scope = G076RecoveryScope(**base, scope_digest=_canonical_hash(base))
    _exclusive_json(
        state_root / f"g076-recovery-{action_digest.removeprefix('sha256:')}.started.json",
        {
            "schema": "H11_V4_G076_RECOVERY_STARTED_V1",
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "action_key": action_digest,
            "scope_digest": scope.scope_digest,
        },
    )
    _atomic_json(
        state_root / G076_RECOVERY_SCOPE_FILE,
        {**asdict(scope), "schema": "H11_V4_G076_RECOVERY_SCOPE_V1"},
    )
    return scope


def load_g076_recovery_scope(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str, now_utc: datetime
) -> G076RecoveryScope:
    """Load one protected recovery scope without permitting a new scope."""

    payload = _read_json(
        state_root / G076_RECOVERY_SCOPE_FILE, "G076_RECOVERY_SCOPE_REQUIRED"
    )
    scope_digest = payload.pop("scope_digest", None)
    schema = payload.pop("schema", None)
    if schema != "H11_V4_G076_RECOVERY_SCOPE_V1":
        raise G076Error("G076_RECOVERY_SCOPE_SCHEMA_INVALID")
    if (
        payload.get("generation_digest") != generation_digest
        or payload.get("reviewed_files_digest") != reviewed_files_digest
        or payload.get("ownership_exact") is not True
        or payload.get("quantity_matches") is not True
        or payload.get("protection_confirmed") is not True
        or not isinstance(scope_digest, str)
        or scope_digest != _canonical_hash(payload)
    ):
        raise G076Error("G076_RECOVERY_SCOPE_BINDING_INVALID")
    try:
        expires_at = datetime.fromisoformat(str(payload["expires_at_utc"])).astimezone(UTC)
    except (KeyError, TypeError, ValueError):
        raise G076Error("G076_RECOVERY_SCOPE_EXPIRY_INVALID") from None
    if now_utc.tzinfo is None or expires_at <= now_utc.astimezone(UTC):
        engage_g076_halt(state_root=state_root, reason="G076_RECOVERY_SCOPE_EXPIRED")
        raise G076Error("G076_RECOVERY_SCOPE_EXPIRED")
    action_digest = _require_digest(
        str(payload.get("action_key", "")), "G076_RECOVERY_ACTION_KEY_INVALID"
    )
    started = state_root / f"g076-recovery-{action_digest.removeprefix('sha256:')}.started.json"
    if not started.is_file() or started.is_symlink():
        raise G076Error("G076_RECOVERY_STARTED_MARKER_REQUIRED")
    return G076RecoveryScope(**payload, scope_digest=scope_digest)


def resume_g076_protected_exit_once(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    recovery_action: G076FakeOnlyCallable,
    now_utc: datetime,
) -> G076ActionOutcome:
    """Resume only an existing protected recovery scope through a fake port."""

    if not isinstance(recovery_action, G076FakeOnlyCallable):
        raise G076Error("G076_FAKE_ONLY_RECOVERY_PORT_REQUIRED")
    scope = load_g076_recovery_scope(
        state_root=state_root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
        now_utc=now_utc,
    )
    result_path = state_root / (
        f"g076-recovery-{scope.action_key.removeprefix('sha256:')}.result.json"
    )
    if result_path.exists() or result_path.is_symlink():
        raise G076Error("G076_RECOVERY_ALREADY_RESUMED_NO_RETRY")
    try:
        outcome = recovery_action(scope)
    except BaseException as error:
        _exclusive_json(
            result_path,
            {
                "schema": "H11_V4_G076_RECOVERY_RESULT_V1",
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "action_key": scope.action_key,
                "scope_digest": scope.scope_digest,
                "status": G076ActionOutcome.UNKNOWN.value,
            },
        )
        engage_g076_halt(state_root=state_root, reason="G076_RECOVERY_RESULT_UNKNOWN")
        raise G076Error("G076_RECOVERY_RESULT_UNKNOWN_NO_RETRY") from error
    if not isinstance(outcome, G076ActionOutcome) or outcome is G076ActionOutcome.UNKNOWN:
        _exclusive_json(
            result_path,
            {
                "schema": "H11_V4_G076_RECOVERY_RESULT_V1",
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "action_key": scope.action_key,
                "scope_digest": scope.scope_digest,
                "status": G076ActionOutcome.UNKNOWN.value,
            },
        )
        engage_g076_halt(state_root=state_root, reason="G076_RECOVERY_RESULT_UNKNOWN")
        raise G076Error("G076_RECOVERY_RESULT_UNKNOWN_NO_RETRY")
    _exclusive_json(
        result_path,
        {
            "schema": "H11_V4_G076_RECOVERY_RESULT_V1",
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "action_key": scope.action_key,
            "scope_digest": scope.scope_digest,
            "status": outcome.value,
        },
    )
    return outcome


class G076OneShotActionDispatcher:
    def __init__(self, *, state_root: Path, port: G076ActionPort) -> None:
        if not _g076_fake_port(port):
            raise G076Error("G076_FAKE_ONLY_ACTION_PORT_REQUIRED")
        self.state_root = state_root
        self.port = port

    def attempt_once(
        self,
        *,
        cycle_id: str,
        action: G076Action,
        side: str,
        quantity: int,
        reconciliation_artifact_digest: str,
        now_utc: datetime,
        lifetime_seconds: int = 15,
    ) -> G076ActionOutcome:
        if side not in {"BUY", "SELL"} or quantity != 1_000 or now_utc.tzinfo is None:
            raise G076Error("G076_ACTION_SCOPE_INVALID")
        _require_digest(
            reconciliation_artifact_digest,
            "G076_RECONCILIATION_ARTIFACT_DIGEST_INVALID",
        )
        action_key = _canonical_hash(
            {
                "generation_digest": self._generation_digest,
                "cycle_id": cycle_id,
                "action": action.value,
                "reconciliation_artifact_digest": reconciliation_artifact_digest,
            }
        )
        base = {
            "generation_digest": self._generation_digest,
            "reviewed_files_digest": self._reviewed_files_digest,
            "release_capability_digest": self._release_capability_digest,
            "reconciliation_artifact_digest": reconciliation_artifact_digest,
            "strategy_artifact_digest": self._strategy_artifact_digest,
            "cycle_id": cycle_id,
            "action": action.value,
            "symbol": "USD_JPY",
            "quantity": quantity,
            "side": side,
            "expires_at_utc": (
                now_utc.astimezone(UTC) + timedelta(seconds=lifetime_seconds)
            ).isoformat(),
            "action_key": action_key,
        }
        scope = G076ActionScope(
            generation_digest=self._generation_digest,
            reviewed_files_digest=self._reviewed_files_digest,
            release_capability_digest=self._release_capability_digest,
            reconciliation_artifact_digest=reconciliation_artifact_digest,
            strategy_artifact_digest=self._strategy_artifact_digest,
            cycle_id=cycle_id,
            action=action,
            symbol="USD_JPY",
            quantity=quantity,
            side=side,
            expires_at_utc=base["expires_at_utc"],
            action_key=action_key,
            scope_digest=_canonical_hash(base),
        )
        marker = (
            self.state_root
            / f"g076-action-{scope.scope_digest.removeprefix('sha256:')}.started.json"
        )
        _exclusive_json(
            marker,
            {
                "generation_label": G076_GENERATION_LABEL,
                "generation_digest": self._generation_digest,
                "reviewed_files_digest": self._reviewed_files_digest,
                "action": action.value,
                "action_key": scope.action_key,
                "scope_digest": scope.scope_digest,
                "status": "STARTED",
            },
        )
        try:
            outcome = self.port.attempt_once(scope)
        except BaseException as error:
            _exclusive_json(
                marker.with_name(marker.name.replace(".started.", ".result.")),
                {
                    "action": action.value,
                    "action_key": scope.action_key,
                    "scope_digest": scope.scope_digest,
                    "status": G076ActionOutcome.UNKNOWN.value,
                },
            )
            engage_g076_halt(state_root=self.state_root, reason="G076_ACTION_RESULT_UNKNOWN")
            raise G076Error("G076_ACTION_RESULT_UNKNOWN_NO_RETRY") from error
        if not isinstance(outcome, G076ActionOutcome) or outcome is G076ActionOutcome.UNKNOWN:
            _exclusive_json(
                marker.with_name(marker.name.replace(".started.", ".result.")),
                {
                    "action": action.value,
                    "action_key": scope.action_key,
                    "scope_digest": scope.scope_digest,
                    "status": G076ActionOutcome.UNKNOWN.value,
                },
            )
            engage_g076_halt(state_root=self.state_root, reason="G076_ACTION_RESULT_UNKNOWN")
            raise G076Error("G076_ACTION_RESULT_UNKNOWN_NO_RETRY")
        _exclusive_json(
            marker.with_name(marker.name.replace(".started.", ".result.")),
            {
                "action": action.value,
                "action_key": scope.action_key,
                "scope_digest": scope.scope_digest,
                "status": outcome.value,
            },
        )
        return outcome

    @classmethod
    def bound(
        cls,
        *,
        state_root: Path,
        port: G076ActionPort,
        generation_digest: str,
        reviewed_files_digest: str,
        release_capability_digest: str,
        strategy_artifact_digest: str,
    ) -> G076OneShotActionDispatcher:
        _require_digest(generation_digest, "G076_GENERATION_DIGEST_INVALID")
        _require_digest(reviewed_files_digest, "G076_REVIEWED_DIGEST_INVALID")
        _require_digest(release_capability_digest, "G076_RELEASE_CAPABILITY_DIGEST_INVALID")
        _require_digest(strategy_artifact_digest, "G076_STRATEGY_ARTIFACT_DIGEST_INVALID")
        instance = cls(state_root=state_root, port=port)
        instance._generation_digest = generation_digest
        instance._reviewed_files_digest = reviewed_files_digest
        instance._release_capability_digest = release_capability_digest
        instance._strategy_artifact_digest = strategy_artifact_digest
        return instance


class G076EntryDispatcher:
    def __init__(self, *, actions: G076OneShotActionDispatcher) -> None:
        self.actions = actions

    def enter_and_protect_once(
        self,
        *,
        decision: G076StrategyDecision,
        evidence: G076ReconciliationEvidence,
        cycle_id: str,
        side: str,
        now_utc: datetime,
    ) -> tuple[G076ActionOutcome, G076ActionOutcome]:
        if evidence.state is not G076ReconciliationState.FRESH_FLAT or not decision.gate_open(
            generation_digest=evidence.generation_digest,
            reviewed_files_digest=evidence.reviewed_files_digest,
        ):
            raise G076Error("G076_ENTRY_GATE_NOT_OPEN")
        entry = self.actions.attempt_once(
            cycle_id=cycle_id, action=G076Action.ENTRY, side=side, quantity=1_000, now_utc=now_utc
            , reconciliation_artifact_digest=evidence.artifact_digest
        )
        if entry is not G076ActionOutcome.ACCEPTED:
            raise G076Error("G076_ENTRY_NOT_ACCEPTED")
        protection = self.actions.attempt_once(
            cycle_id=cycle_id,
            action=G076Action.PROTECTION,
            side=side,
            quantity=1_000,
            reconciliation_artifact_digest=evidence.artifact_digest,
            now_utc=now_utc,
        )
        if protection is not G076ActionOutcome.PROTECTED:
            engage_g076_halt(
                state_root=self.actions.state_root, reason="G076_PROTECTION_NOT_CONFIRMED"
            )
            raise G076Error("G076_PROTECTION_NOT_CONFIRMED")
        return entry, protection


class G076ExitDispatcher:
    def __init__(self, *, actions: G076OneShotActionDispatcher) -> None:
        self.actions = actions

    def exit_once(
        self,
        *,
        evidence: G076ReconciliationEvidence,
        cycle_id: str,
        side: str,
        reason: G076Action,
        now_utc: datetime,
    ) -> tuple[G076ActionOutcome, G076ActionOutcome]:
        if evidence.state is not G076ReconciliationState.FRESH_PROTECTED:
            raise G076Error("G076_EXIT_PROTECTION_NOT_CONFIRMED")
        if reason not in {G076Action.TAKE_PROFIT, G076Action.STOP_LOSS, G076Action.TIME_EXIT}:
            raise G076Error("G076_EXIT_REASON_INVALID")
        cancel = self.actions.attempt_once(
            cycle_id=cycle_id,
            action=G076Action.CANCEL_PROTECTION,
            side=side,
            quantity=1_000,
            reconciliation_artifact_digest=evidence.artifact_digest,
            now_utc=now_utc,
        )
        if cancel is not G076ActionOutcome.ACCEPTED:
            raise G076Error("G076_EXIT_CANCEL_NOT_ACCEPTED")
        close = self.actions.attempt_once(
            cycle_id=cycle_id,
            action=G076Action.CLOSE_POSITION,
            side=side,
            quantity=1_000,
            reconciliation_artifact_digest=evidence.artifact_digest,
            now_utc=now_utc,
        )
        if close is not G076ActionOutcome.FLAT:
            raise G076Error("G076_EXIT_NOT_FLAT")
        return cancel, close


@dataclass
class G076ProcessLock:
    state_root: Path
    generation_digest: str | None = None
    reviewed_files_digest: str | None = None
    acquired: bool = False

    @property
    def path(self) -> Path:
        return self.state_root / "process.lock"

    @property
    def held(self) -> bool:
        return self.acquired

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return pid > 0

    def acquire(self) -> None:
        self.state_root.mkdir(parents=True, exist_ok=True)
        if not _DIGEST.fullmatch(self.generation_digest or "") or not _DIGEST.fullmatch(
            self.reviewed_files_digest or ""
        ):
            raise G076Error("G076_PROCESS_LOCK_BINDING_REQUIRED")
        if self.path.is_symlink():
            raise G076Error("G076_PROCESS_LOCK_SYMLINK_REFUSED")
        if self.path.exists():
            try:
                payload = _read_json(self.path, "G076_PROCESS_LOCK_INVALID")
                pid = int(payload["pid"])
            except (G076Error, KeyError, TypeError, ValueError):
                raise G076Error("G076_PROCESS_LOCK_INVALID") from None
            if self._pid_alive(pid):
                raise G076Error("G076_PROCESS_LOCK_CONFLICT")
            raise G076Error("G076_PROCESS_LOCK_STALE")
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise G076Error("G076_PROCESS_LOCK_CONFLICT") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "pid": os.getpid(),
                    "generation_label": G076_GENERATION_LABEL,
                    "generation_digest": self.generation_digest,
                    "reviewed_files_digest": self.reviewed_files_digest,
                },
                stream,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _fsync_parent(self.path)
        self.acquired = True

    def release(self) -> None:
        if self.acquired and self.path.is_file() and not self.path.is_symlink():
            self.path.unlink()
            _fsync_parent(self.path)
        self.acquired = False


def _capability_valid(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str
) -> bool:
    try:
        required = (
            state_root / G076_SWITCH_CAPABILITY_FILE,
            state_root / G076_RELEASE_CAPABILITY_FILE,
            state_root / G076_INITIAL_TRANSACTION_OUTCOME_FILE,
            state_root / G076_OPERATION_60_RESULT_FILE,
        )
        if any(not path.is_file() or path.is_symlink() for path in required):
            return False
        capability = _read_json(state_root / G076_SWITCH_CAPABILITY_FILE, "G076_CAPABILITY_INVALID")
        release = _read_json(
            state_root / G076_RELEASE_CAPABILITY_FILE, "G076_RELEASE_CAPABILITY_INVALID"
        )
        outcome = _read_json(
            state_root / G076_INITIAL_TRANSACTION_OUTCOME_FILE, "G076_TRANSACTION_OUTCOME_INVALID"
        )
        operation = _read_json(
            state_root / G076_OPERATION_60_RESULT_FILE, "G076_OPERATION_60_RESULT_INVALID"
        )
        artifact = capability.pop("artifact_digest")
        release_artifact = release.pop("artifact_digest")
        outcome_artifact = outcome.pop("artifact_digest")
        operation_artifact = operation.pop("artifact_digest")
        return (
            outcome.get("status") == "PASSED"
            and outcome.get("generation_label") == G076_GENERATION_LABEL
            and outcome.get("generation_digest") == generation_digest
            and outcome.get("reviewed_files_digest") == reviewed_files_digest
            and outcome.get("broker_post_count") == 0
            and outcome.get("private_api_read_count") == 0
            and outcome.get("credential_read_count") == 0
            and outcome_artifact == _canonical_hash(outcome)
            and operation.get("status") == "PASSED"
            and operation.get("schema") == "H11_V4_G076_OPERATION_60_RESULT_V1"
            and operation.get("generation_label") == G076_GENERATION_LABEL
            and operation.get("generation_digest") == generation_digest
            and operation.get("reviewed_files_digest") == reviewed_files_digest
            and operation.get("broker_write") is False
            and operation.get("broker_post_count") == 0
            and operation.get("private_api_read_count") == 0
            and operation.get("credential_read_count") == 0
            and operation.get("arm_mutation_count") == 0
            and operation.get("notification_attempt_count") == 0
            and operation.get("actual_post_authorized") is False
            and operation_artifact == _canonical_hash(operation)
            and capability.get("status") == "ENABLED"
            and release.get("status") == "ENABLED"
            and capability.get("schema") == "H11_V4_G076_SWITCH_CONTROL_CAPABILITY_V1"
            and release.get("schema") == "H11_V4_G076_SWITCH_CONTROL_CAPABILITY_V1"
            and capability.get("generation_label") == G076_GENERATION_LABEL
            and release.get("generation_label") == G076_GENERATION_LABEL
            and capability.get("generation_digest") == generation_digest
            and release.get("generation_digest") == generation_digest
            and capability.get("reviewed_files_digest") == reviewed_files_digest
            and release.get("reviewed_files_digest") == reviewed_files_digest
            and capability.get("actual_post_authorized") is False
            and capability.get("broker_post_authorized") is False
            and capability.get("daily_authorization_required") is False
            and capability.get("per_trade_confirmation_required") is False
            and artifact == _canonical_hash(capability)
            and release_artifact == _canonical_hash(release)
            and capability == release
            and not (state_root / G076_PERSISTENT_HALT_FILE).exists()
        )
    except (G076Error, KeyError, TypeError, ValueError):
        return False


def load_g076_release_capability_digest(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str
) -> str:
    if not _capability_valid(
        state_root=state_root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
    ):
        raise G076Error("G076_RELEASE_CAPABILITY_LOCKED")
    release = _read_json(
        state_root / G076_RELEASE_CAPABILITY_FILE, "G076_RELEASE_CAPABILITY_INVALID"
    )
    digest = release.get("artifact_digest")
    return _require_digest(digest, "G076_RELEASE_CAPABILITY_DIGEST_INVALID")


@dataclass
class G076ResidentSupervisor:
    state_root: Path
    generation_digest: str
    reviewed_files_digest: str
    reconciliation_runner: Callable[[str, datetime], G076ReconciliationEvidence] | None = None
    strategy_evaluator: G076FrozenStrategyEvaluator | None = None
    entry_dispatcher: G076EntryDispatcher | None = None
    exit_dispatcher: G076ExitDispatcher | None = None
    exit_reason_provider: (
        Callable[[G076ReconciliationEvidence, datetime], G076Action | None] | None
    ) = None
    cycle_index: int = 0
    runtime_nonce: str = field(default_factory=lambda: secrets.token_hex(8), repr=False)

    def __post_init__(self) -> None:
        for callback in (self.reconciliation_runner, self.exit_reason_provider):
            if callback is not None and not isinstance(callback, G076FakeOnlyCallable):
                raise G076Error("G076_FAKE_ONLY_SUPERVISOR_CALLBACK_REQUIRED")

    def _next_cycle(self) -> str:
        self.cycle_index += 1
        return f"{self.runtime_nonce}-cycle-{self.cycle_index}"

    def tick(
        self,
        *,
        now_utc: datetime,
        arm_on: bool,
        process_lock_single: bool = True,
        dead_man_alive: bool = True,
        heartbeat_chain_beat: bool = True,
    ) -> dict[str, object]:
        if now_utc.tzinfo is None:
            raise G076Error("G076_RUNTIME_CLOCK_INVALID")
        self.state_root.mkdir(parents=True, exist_ok=True)
        halted = (self.state_root / G076_PERSISTENT_HALT_FILE).exists() or (
            self.state_root / G076_PERSISTENT_HALT_FILE
        ).is_symlink()
        evidence = None
        if not halted:
            try:
                evidence = load_g076_reconciliation(
                    state_root=self.state_root,
                    generation_digest=self.generation_digest,
                    reviewed_files_digest=self.reviewed_files_digest,
                    now_utc=now_utc,
                )
            except G076Error:
                halted = True
            if (
                not halted
                and self.reconciliation_runner is not None
                and (evidence is None or evidence.state is G076ReconciliationState.STALE)
            ):
                try:
                    evidence = self.reconciliation_runner(self._next_cycle(), now_utc)
                except G076Error:
                    halted = True
        capability = _capability_valid(
            state_root=self.state_root,
            generation_digest=self.generation_digest,
            reviewed_files_digest=self.reviewed_files_digest,
        )
        decision: G076StrategyDecision | None = None
        effective = G076EffectiveState.OFF
        entry_gate = False
        entry_state = G076EntryState.DISABLED
        reason = "G076_ARM_OFF"
        exit_state = G076ExitState.NOT_REQUIRED
        action_state = G076ActionState.IDLE
        if halted or not process_lock_single or not dead_man_alive or not heartbeat_chain_beat:
            halted = True
            effective = G076EffectiveState.HALTED
            entry_state = G076EntryState.HALTED
            reason = "G076_RUNTIME_HEALTH_NOT_CLEAR"
        elif evidence is not None and evidence.state in {
            G076ReconciliationState.UNKNOWN,
            G076ReconciliationState.STALE,
        }:
            halted = True
            effective = G076EffectiveState.HALTED
            entry_state = G076EntryState.HALTED
            reason = "G076_RECONCILIATION_NOT_CLEAR"
            exit_state = G076ExitState.UNKNOWN
        elif not capability:
            effective = G076EffectiveState.HALTED
            entry_state = G076EntryState.HALTED
            reason = "G076_RELEASE_CAPABILITY_LOCKED"
        elif evidence is not None and evidence.position_open:
            protected = all(
                (evidence.ownership_exact, evidence.quantity_matches, evidence.protection_confirmed)
            )
            if not protected or evidence.state is not G076ReconciliationState.FRESH_PROTECTED:
                halted = True
                effective = G076EffectiveState.HALTED
                entry_state = G076EntryState.HALTED
                reason = "G076_POSITION_PROTECTION_NOT_CONFIRMED"
                exit_state = G076ExitState.UNKNOWN
            else:
                effective = (
                    G076EffectiveState.ON_EXIT_ONLY if arm_on else G076EffectiveState.EXIT_ONLY
                )
                entry_state = G076EntryState.BLOCKED_POSITION_OPEN
                reason = "G076_PROTECTED_POSITION_EXIT_MANAGEMENT"
                exit_state = G076ExitState.PROTECTED
                if self.exit_reason_provider is not None and self.exit_dispatcher is not None:
                    exit_reason = self.exit_reason_provider(evidence, now_utc)
                    if exit_reason is not None:
                        if evidence.position_side not in {"BUY", "SELL"}:
                            raise G076Error("G076_EXIT_SIDE_UNKNOWN")
                        action_state = G076ActionState.STARTED
                        self.exit_dispatcher.exit_once(
                            evidence=evidence,
                            cycle_id=evidence.cycle_id,
                            side=evidence.position_side,
                            reason=exit_reason,
                            now_utc=now_utc,
                        )
                        action_state = G076ActionState.RESULT_KNOWN
                        evidence = _mark_g076_reconciliation_stale(
                            state_root=self.state_root, evidence=evidence, now_utc=now_utc
                        )
                        entry_gate = False
        elif not arm_on:
            effective = G076EffectiveState.OFF
            entry_state = G076EntryState.DISABLED
            reason = "G076_ARM_OFF"
        elif evidence is None:
            halted = True
            effective = G076EffectiveState.HALTED
            entry_state = G076EntryState.HALTED
            reason = "G076_RECONCILIATION_REQUIRED"
        elif evidence.state is G076ReconciliationState.FRESH_FLAT:
            effective = G076EffectiveState.ON_WAITING
            entry_state = G076EntryState.WAITING_FOR_SIGNAL
            reason = "G076_WAITING_FOR_SIGNAL"
            if self.strategy_evaluator is not None:
                try:
                    decision = self.strategy_evaluator.evaluate(now_utc=now_utc, evidence=evidence)
                    if not decision.binding_valid(
                        generation_digest=self.generation_digest,
                        reviewed_files_digest=self.reviewed_files_digest,
                    ):
                        halted = True
                        effective = G076EffectiveState.HALTED
                        entry_state = G076EntryState.HALTED
                        reason = "G076_STRATEGY_BINDING_NOT_CLEAR"
                    else:
                        entry_gate = decision.gate_open(
                            generation_digest=self.generation_digest,
                            reviewed_files_digest=self.reviewed_files_digest,
                        )
                        if entry_gate:
                            entry_state = G076EntryState.ENTRY_READY
                            reason = "G076_ENTRY_GATE_OPEN"
                            if self.entry_dispatcher is not None:
                                action_state = G076ActionState.STARTED
                                self.entry_dispatcher.enter_and_protect_once(
                                    decision=decision,
                                    evidence=evidence,
                                    cycle_id=evidence.cycle_id,
                                    side=decision.side,
                                    now_utc=now_utc,
                                )
                                action_state = G076ActionState.RESULT_KNOWN
                                evidence = _mark_g076_reconciliation_stale(
                                    state_root=self.state_root, evidence=evidence, now_utc=now_utc
                                )
                                entry_gate = False
                                entry_state = G076EntryState.ACTION_IN_PROGRESS
                                reason = "G076_ENTRY_LIFECYCLE_RESULT_KNOWN"
                except (G076Error, TypeError, ValueError):
                    halted = True
                    effective = G076EffectiveState.HALTED
                    entry_state = G076EntryState.HALTED
                    reason = "G076_STRATEGY_EVALUATION_UNKNOWN"
        else:
            halted = True
            effective = G076EffectiveState.HALTED
            entry_state = G076EntryState.HALTED
            reason = "G076_RECONCILIATION_STATE_INVALID"
        if halted:
            entry_gate = False
        observed = now_utc.astimezone(UTC).isoformat()
        status: dict[str, object] = {
            "schema": "H11_V4_G076_RUNTIME_STATUS_V1",
            "generation_label": G076_GENERATION_LABEL,
            "generation_digest": self.generation_digest,
            "reviewed_files_digest": self.reviewed_files_digest,
            "arm_state": G076ArmState.ON.value if arm_on else G076ArmState.OFF.value,
            "release_state": G076ReleaseState.ENABLED.value
            if capability
            else G076ReleaseState.LOCKED.value,
            "effective_state": effective.value,
            "entry_gate_open": entry_gate,
            "entry_state": entry_state.value,
            "reconciliation_state": evidence.state.value
            if evidence
            else G076ReconciliationState.REQUIRED.value,
            "action_state": action_state.value,
            "exit_state": exit_state.value,
            "safe_reason_label": reason,
            "heartbeat_at_utc": observed,
            "dead_man_alive": dead_man_alive,
            "lock_single_owner": process_lock_single,
            "heartbeat_chain_beat": heartbeat_chain_beat,
            "persistent_halt": halted,
            "pending_transport": False,
            "unknown_halt": halted,
            "strategy_evaluation_known": bool(decision and decision.evaluation_known),
            "strategy_artifact_bound": bool(decision and decision.strategy_artifact_bound),
            "signal_actionable": bool(decision and decision.signal_actionable),
            "risk_clear": bool(decision and decision.risk_clear),
            "market_open": bool(decision and decision.market_open),
            "spread_clear": bool(decision and decision.spread_clear),
            "freshness_clear": bool(decision and decision.freshness_clear),
            "limits_clear": bool(decision and decision.limits_clear),
            "position_open": bool(evidence and evidence.position_open),
            "ownership_exact": bool(evidence and evidence.ownership_exact),
            "quantity_matches": bool(evidence and evidence.quantity_matches),
            "protection_confirmed": bool(evidence and evidence.protection_confirmed),
            "broker_read": False,
            "private_api_read_count": 0,
            "credential_read_count": 0,
            "notification_attempt_count": 0,
            "broker_write": False,
            "actual_post_count": 0,
            "actual_post_authorized": False,
            "broker_post_authorized": False,
        }
        status["artifact_digest"] = _canonical_hash(status)
        _atomic_json(self.state_root / G076_RUNTIME_STATUS_FILE, status)
        heartbeat = {
            "schema": "H11_V4_G076_RESIDENT_HEARTBEAT_V1",
            "generation_label": G076_GENERATION_LABEL,
            "generation_digest": self.generation_digest,
            "reviewed_files_digest": self.reviewed_files_digest,
            "heartbeat_at_utc": observed,
            "broker_read": False,
            "private_api_read_count": 0,
            "credential_read_count": 0,
            "notification_attempt_count": 0,
            "broker_write": False,
            "actual_post_count": 0,
            "pending": False,
            "unknown_halt": halted,
        }
        _atomic_json(self.state_root / "heartbeat.json", heartbeat)
        _atomic_json(self.state_root / "dead-man.json", {**heartbeat, "alive": dead_man_alive})
        chain_path = self.state_root / "heartbeat-chain.json"
        previous = "sha256:" + "0" * 64
        index = 1
        if chain_path.is_file() and not chain_path.is_symlink():
            prior = _read_json(chain_path, "G076_HEARTBEAT_CHAIN_INVALID")
            previous = str(prior.get("chain_hash", previous))
            index = int(prior.get("chain_index", 0)) + 1
        chain_base = {**heartbeat, "chain_index": index, "previous_chain_hash": previous}
        _atomic_json(chain_path, {**chain_base, "chain_hash": _canonical_hash(chain_base)})
        return status


def safe_g076_api_status(
    *,
    state_root: Path,
    arm_on: bool,
    generation_digest: str,
    reviewed_files_digest: str,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    capability = _capability_valid(
        state_root=state_root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
    )
    try:
        status = _read_json(state_root / G076_RUNTIME_STATUS_FILE, "G076_RUNTIME_STATUS_REQUIRED")
        if (
            status.get("generation_label") != G076_GENERATION_LABEL
            or status.get("generation_digest") != generation_digest
            or status.get("reviewed_files_digest") != reviewed_files_digest
        ):
            raise G076Error("G076_RUNTIME_STATUS_BINDING_INVALID")
    except G076Error:
        status = {
            "generation_label": G076_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "effective_state": G076EffectiveState.HALTED.value,
            "entry_gate_open": False,
            "entry_state": G076EntryState.HALTED.value,
            "reconciliation_state": G076ReconciliationState.UNKNOWN.value,
            "safe_reason_label": "G076_RUNTIME_STATUS_REQUIRED",
            "lock_single_owner": False,
            "persistent_halt": True,
            "dead_man_alive": False,
            "heartbeat_chain_beat": False,
            "pending_transport": True,
            "unknown_halt": True,
        }
    effective = str(status.get("effective_state", G076EffectiveState.HALTED.value))
    if not capability:
        status = {
            **status,
            "effective_state": G076EffectiveState.HALTED.value,
            "entry_gate_open": False,
            "entry_state": G076EntryState.HALTED.value,
            "safe_reason_label": "G076_RELEASE_CAPABILITY_LOCKED",
        }
        effective = G076EffectiveState.HALTED.value
    resident_health = _g076_resident_health_clear(
        state_root=state_root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
        status=status,
        now_utc=now_utc or datetime.now(UTC),
    )
    resident_ready = (
        resident_health
        and capability
        and status.get("persistent_halt") is False
        and status.get("unknown_halt") is False
        and status.get("pending_transport") is False
        and status.get("broker_read") is False
        and status.get("lock_single_owner") is True
        and status.get("dead_man_alive") is True
        and status.get("heartbeat_chain_beat") is True
        and effective != G076EffectiveState.HALTED.value
    )
    return {
        **status,
        "control_plane_state": "READY" if resident_ready else "HALTED",
        "generation_label": G076_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "arm_state": G076ArmState.ON.value if arm_on else G076ArmState.OFF.value,
        "release_state": G076ReleaseState.ENABLED.value
        if capability
        else G076ReleaseState.LOCKED.value,
        "atomic_activation_complete": False,
        "runtime_activation_available": False,
        "switch_only_rearm_available": False,
        "local_arm_on_available": False,
        "arm_control_available": False,
        "arm_ready": False,
        "scheduler_ready": resident_ready,
        "position_reconciliation_ready": status.get("reconciliation_state")
        in {
            G076ReconciliationState.FRESH_FLAT.value,
            G076ReconciliationState.FRESH_PROTECTED.value,
        },
        "daily_authorization_required": False,
        "per_trade_confirmation_required": False,
        "live_ready": False,
        "unattended_live_supported": False,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "entry_gate_open": bool(status.get("entry_gate_open"))
        and effective == G076EffectiveState.ON_WAITING.value,
    }


def _g076_resident_health_clear(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    status: Mapping[str, object],
    now_utc: datetime,
) -> bool:
    required = (
        state_root / "heartbeat.json",
        state_root / "process.lock",
        state_root / "dead-man.json",
        state_root / "heartbeat-chain.json",
    )
    if any(not path.is_file() or path.is_symlink() for path in required):
        return False
    if (state_root / G076_PERSISTENT_HALT_FILE).exists() or (
        state_root / G076_PERSISTENT_HALT_FILE
    ).is_symlink():
        return False
    try:
        heartbeat = _read_json(required[0], "G076_HEARTBEAT_INVALID")
        lock = _read_json(required[1], "G076_PROCESS_LOCK_INVALID")
        dead_man = _read_json(required[2], "G076_DEAD_MAN_INVALID")
        chain = _read_json(required[3], "G076_HEARTBEAT_CHAIN_INVALID")
        lock_pid = int(lock["pid"])
        heartbeat_at = datetime.fromisoformat(str(heartbeat["heartbeat_at_utc"])).astimezone(UTC)
        age = (now_utc.astimezone(UTC) - heartbeat_at).total_seconds()
        chain_base = {key: value for key, value in chain.items() if key != "chain_hash"}
    except (G076Error, KeyError, TypeError, ValueError):
        return False
    return (
        lock.get("generation_label") == G076_GENERATION_LABEL
        and G076ProcessLock._pid_alive(lock_pid)
        and lock.get("generation_digest") == generation_digest
        and lock.get("reviewed_files_digest") == reviewed_files_digest
        and heartbeat.get("generation_label") == G076_GENERATION_LABEL
        and heartbeat.get("generation_digest") == generation_digest
        and heartbeat.get("reviewed_files_digest") == reviewed_files_digest
        and heartbeat.get("broker_write") is False
        and heartbeat.get("broker_read") is False
        and heartbeat.get("actual_post_count") == 0
        and heartbeat.get("pending") is False
        and heartbeat.get("unknown_halt") is False
        and dead_man.get("alive") is True
        and dead_man.get("broker_read") is False
        and dead_man.get("generation_label") == G076_GENERATION_LABEL
        and dead_man.get("generation_digest") == generation_digest
        and dead_man.get("reviewed_files_digest") == reviewed_files_digest
        and lock.get("generation_digest") == generation_digest
        and lock.get("reviewed_files_digest") == reviewed_files_digest
        and chain.get("generation_label") == G076_GENERATION_LABEL
        and chain.get("generation_digest") == generation_digest
        and chain.get("reviewed_files_digest") == reviewed_files_digest
        and chain.get("broker_write") is False
        and chain.get("broker_read") is False
        and chain.get("actual_post_count") == 0
        and chain.get("pending") is False
        and chain.get("unknown_halt") is False
        and chain.get("chain_index", 0) >= 1
        and isinstance(chain.get("previous_chain_hash"), str)
        and _DIGEST.fullmatch(chain["previous_chain_hash"]) is not None
        and chain.get("chain_hash") == _canonical_hash(chain_base)
        and status.get("heartbeat_at_utc") == heartbeat.get("heartbeat_at_utc")
        and status.get("artifact_digest")
        == _canonical_hash(
            {key: value for key, value in status.items() if key != "artifact_digest"}
        )
        and status.get("artifact_digest")
        == _canonical_hash(
            {key: value for key, value in status.items() if key != "artifact_digest"}
        )
        and age >= 0
        and age <= G076_MAX_EVIDENCE_AGE_SECONDS
    )


def verify_g076_scheduler_binding(
    *, generation: object, repository: Path, plist_path: Path, state_root: Path, now_utc: datetime
) -> None:
    if getattr(generation, "generation_label", None) != G076_GENERATION_LABEL:
        raise G076Error("G076_GENERATION_REQUIRED")
    if (state_root / G076_PERSISTENT_HALT_FILE).exists() or (
        state_root / G076_PERSISTENT_HALT_FILE
    ).is_symlink():
        raise G076Error("G076_PERSISTENT_HALT_PRESENT")
    if not plist_path.is_file() or plist_path.is_symlink():
        raise G076Error("G076_SCHEDULER_PLIST_INVALID")
    try:
        payload = plistlib.loads(plist_path.read_bytes())
        arguments = payload["ProgramArguments"]
    except (OSError, KeyError, TypeError, ValueError, plistlib.InvalidFileException) as error:
        raise G076Error("G076_SCHEDULER_PLIST_INVALID") from error
    expected = str(
        repository.resolve() / "backend/scripts/h11_auto_v4_g076_runtime_bootstrap.py"
    )
    expected_arguments = [
        str((repository.resolve() / "backend/.venv/bin/python").resolve()),
        expected,
        "--repository",
        str(repository.resolve()),
        "--expected-reviewed-files-digest",
        str(getattr(generation, "implementation_digest", "")),
        "--expected-generation-digest",
        str(getattr(generation, "digest", "")),
    ]
    if arguments != expected_arguments:
        raise G076Error("G076_SCHEDULER_BINDING_INVALID")
    required = (
        state_root / "heartbeat.json",
        state_root / "process.lock",
        state_root / "dead-man.json",
        state_root / "heartbeat-chain.json",
        state_root / G076_RUNTIME_STATUS_FILE,
    )
    if any(not path.is_file() or path.is_symlink() for path in required):
        raise G076Error("G076_RUNTIME_READINESS_MISSING")
    heartbeat = _read_json(required[0], "G076_HEARTBEAT_INVALID")
    lock = _read_json(required[1], "G076_PROCESS_LOCK_INVALID")
    dead_man = _read_json(required[2], "G076_DEAD_MAN_INVALID")
    chain = _read_json(required[3], "G076_HEARTBEAT_CHAIN_INVALID")
    status = _read_json(required[4], "G076_RUNTIME_STATUS_INVALID")
    try:
        lock_pid = int(lock["pid"])
        observed = datetime.fromisoformat(str(heartbeat["heartbeat_at_utc"])).astimezone(UTC)
    except (KeyError, TypeError, ValueError) as error:
        raise G076Error("G076_RUNTIME_READINESS_NOT_CLEAR") from error
    age = (now_utc.astimezone(UTC) - observed).total_seconds()
    chain_base = {key: value for key, value in chain.items() if key != "chain_hash"}
    if (
        lock.get("generation_label") != G076_GENERATION_LABEL
        or lock.get("generation_digest") != generation.digest
        or lock.get("reviewed_files_digest") != generation.implementation_digest
        or not G076ProcessLock._pid_alive(lock_pid)
        or heartbeat.get("generation_label") != G076_GENERATION_LABEL
        or heartbeat.get("generation_digest") != generation.digest
        or heartbeat.get("reviewed_files_digest") != generation.implementation_digest
        or heartbeat.get("broker_write") is not False
        or heartbeat.get("broker_read") is not False
        or heartbeat.get("private_api_read_count") != 0
        or heartbeat.get("credential_read_count") != 0
        or heartbeat.get("actual_post_count") != 0
        or heartbeat.get("pending") is not False
        or heartbeat.get("unknown_halt") is not False
        or dead_man.get("alive") is not True
        or dead_man.get("broker_read") is not False
        or dead_man.get("generation_label") != G076_GENERATION_LABEL
        or dead_man.get("generation_digest") != generation.digest
        or dead_man.get("reviewed_files_digest") != generation.implementation_digest
        or chain.get("generation_label") != G076_GENERATION_LABEL
        or chain.get("generation_digest") != generation.digest
        or chain.get("reviewed_files_digest") != generation.implementation_digest
        or chain.get("broker_write") is not False
        or chain.get("broker_read") is not False
        or chain.get("actual_post_count") != 0
        or chain.get("pending") is not False
        or chain.get("unknown_halt") is not False
        or status.get("generation_label") != G076_GENERATION_LABEL
        or status.get("generation_digest") != generation.digest
        or status.get("reviewed_files_digest") != generation.implementation_digest
        or status.get("persistent_halt") is not False
        or status.get("unknown_halt") is not False
        or status.get("pending_transport") is not False
        or status.get("broker_read") is not False
        or status.get("broker_write") is not False
        or status.get("actual_post_count") != 0
        or status.get("artifact_digest")
        != _canonical_hash(
            {key: value for key, value in status.items() if key != "artifact_digest"}
        )
        or chain.get("chain_index", 0) < 1
        or not isinstance(chain.get("previous_chain_hash"), str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", chain["previous_chain_hash"])
        or chain.get("chain_hash") != _canonical_hash(chain_base)
        or age < 0
        or age > G076_MAX_EVIDENCE_AGE_SECONDS
    ):
        raise G076Error("G076_RUNTIME_READINESS_NOT_CLEAR")


def verify_g076_review_artifacts(
    *, repository: Path, generation_digest: str, reviewed_files_digest: str
) -> None:
    root = repository / "docs/templates"
    paths = (
        root / "h11_v4_g076_frozen_generation.json",
        root / "h11_v4_g076_runtime_commissioning_evidence.json",
        root / "h11_v4_g076_independent_review_attestation.json",
    )
    try:
        manifest, evidence, attestation = tuple(
            json.loads(path.read_text(encoding="utf-8")) for path in paths
        )
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise G076Error("G076_REVIEW_ARTIFACT_INVALID") from error
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
    required_clear = (
        "focused_tests_clear",
        "related_tests_clear",
        "ruff_clear",
        "diff_check_clear",
        "danger_scan_clear",
        "architecture_review_clear",
        "safety_review_clear",
        "operations_review_clear",
    )
    expected_schemas = (
        manifest.get("schema") == "H11_AUTO_GENERATION_V4_GMO_FRIDAY_LIMITED_V2",
        evidence.get("schema") == "H11_V4_G076_RUNTIME_COMMISSIONING_EVIDENCE_V1",
        attestation.get("schema") == "H11_V4_G076_INDEPENDENT_REVIEW_ATTESTATION_V1",
    )
    if (
        not all(expected_schemas)
        or manifest.get("generation_label") != G076_GENERATION_LABEL
        or manifest.get("implementation_digest") != reviewed_files_digest
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
        or any(evidence.get(field) is not True for field in required_clear)
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
        or evidence.get("broker_write") is not False
        or evidence.get("actual_post_authorized") is not False
        or evidence.get("broker_post_authorized") is not False
        or attestation.get("architecture_status") != "CLEAR"
        or attestation.get("safety_status") != "CLEAR"
        or attestation.get("operations_status") != "CLEAR"
        or attestation.get("blocking_findings") != []
        or manifest.get("predecessor_generation_digest")
        != evidence.get("predecessor_generation_digest")
        or manifest.get("predecessor_generation_digest")
        != attestation.get("predecessor_generation_digest")
        or manifest.get("activation_source_generation_digest")
        != manifest.get("predecessor_generation_digest")
        or manifest.get("predecessor_initial_activation_unknown") is not True
        or evidence.get("predecessor_initial_activation_unknown") is not True
        or attestation.get("predecessor_initial_activation_unknown") is not True
        or manifest.get("predecessor_terminal_evidence_reused") is not False
        or evidence.get("predecessor_terminal_evidence_reused") is not False
        or attestation.get("predecessor_terminal_evidence_reused") is not False
        or manifest.get("predecessor_authorization_reused") is not False
        or evidence.get("predecessor_authorization_reused") is not False
        or attestation.get("predecessor_authorization_reused") is not False
        or manifest.get("predecessor_state_root_reused") is not False
        or evidence.get("predecessor_state_root_reused") is not False
        or attestation.get("predecessor_state_root_reused") is not False
    ):
        raise G076Error("G076_REVIEW_ARTIFACT_BINDING_MISMATCH")


def run_g076_initial_atomic_activation(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    reconciliation_runner: Callable[[], G076ReconciliationEvidence],
    resident_readiness_verifier: Callable[[], bool],
    arm_mutator: Callable[[], None],
    arm_state_verifier: Callable[[], bool],
    now_utc: datetime,
) -> str:
    """Run the one-use transaction with injected, separately reviewed ports."""

    if not all(
        isinstance(port, G076FakeOnlyCallable)
        for port in (
            reconciliation_runner,
            resident_readiness_verifier,
            arm_mutator,
            arm_state_verifier,
        )
    ):
        raise G076Error("G076_FAKE_ONLY_ACTIVATION_PORT_REQUIRED")
    operation = _read_json(
        state_root / G076_OPERATION_60_RESULT_FILE, "G076_OPERATION_60_RESULT_INVALID"
    )
    operation_artifact = operation.pop("artifact_digest", None)
    if (
        operation.get("status") != "PASSED"
        or operation.get("schema") != "H11_V4_G076_OPERATION_60_RESULT_V1"
        or operation.get("generation_label") != G076_GENERATION_LABEL
        or operation.get("generation_digest") != generation_digest
        or operation.get("reviewed_files_digest") != reviewed_files_digest
        or operation.get("broker_write") is not False
        or operation.get("broker_post_count") != 0
        or operation.get("private_api_read_count") != 0
        or operation.get("credential_read_count") != 0
        or operation.get("arm_mutation_count") != 0
        or operation.get("notification_attempt_count") != 0
        or operation.get("actual_post_authorized") is not False
        or operation_artifact != _canonical_hash(operation)
    ):
        raise G076Error("G076_OPERATION_60_PASSED_REQUIRED")
    if resident_readiness_verifier() is not True:
        raise G076Error("G076_RESIDENT_READINESS_REQUIRED")

    _exclusive_json(
        state_root / G076_INITIAL_TRANSACTION_STARTED_FILE,
        {
            "schema": "H11_V4_G076_INITIAL_TRANSACTION_STARTED_V1",
            "generation_label": G076_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "status": "STARTED",
        },
    )
    try:
        evidence = reconciliation_runner()
        if evidence.state not in {
            G076ReconciliationState.FRESH_FLAT,
            G076ReconciliationState.FRESH_PROTECTED,
        }:
            raise G076Error("G076_INITIAL_RECONCILIATION_NOT_CLEAR")
        base = {
            "schema": "H11_V4_G076_SWITCH_CONTROL_CAPABILITY_V1",
            "generation_label": G076_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "reconciliation_artifact_digest": evidence.artifact_digest,
            "actual_post_authorized": False,
            "broker_post_authorized": False,
            "daily_authorization_required": False,
            "per_trade_confirmation_required": False,
            "status": "ENABLED",
        }
        arm_mutator()
        if arm_state_verifier() is not True:
            raise G076Error("G076_INITIAL_ARM_MUTATION_NOT_CONFIRMED")
        _atomic_json(
            state_root / G076_RELEASE_CAPABILITY_FILE,
            {**base, "artifact_digest": _canonical_hash(base)},
        )
        _atomic_json(
            state_root / G076_SWITCH_CAPABILITY_FILE,
            {**base, "artifact_digest": _canonical_hash(base)},
        )
        outcome = {
            "schema": "H11_V4_G076_INITIAL_TRANSACTION_OUTCOME_V1",
            "status": "PASSED",
            "generation_label": G076_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "broker_post_count": 0,
            "private_api_read_count": 0,
            "credential_read_count": 0,
            "arm_mutation_count": 1,
            "notification_attempt_count": 0,
            "broker_write": False,
            "actual_post_authorized": False,
            "broker_post_authorized": False,
        }
        _atomic_json(
            state_root / G076_INITIAL_TRANSACTION_OUTCOME_FILE,
            {**outcome, "artifact_digest": _canonical_hash(outcome)},
        )
        return "PASSED"
    except Exception:
        engage_g076_halt(state_root=state_root, reason="G076_INITIAL_TRANSACTION_UNKNOWN")
        unknown = {
            "schema": "H11_V4_G076_INITIAL_TRANSACTION_OUTCOME_V1",
            "status": "UNKNOWN",
            "generation_label": G076_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "broker_post_count": 0,
            "private_api_read_count": 0,
            "credential_read_count": 0,
            "arm_mutation_count": 0,
            "notification_attempt_count": 0,
            "broker_write": False,
            "actual_post_authorized": False,
            "broker_post_authorized": False,
        }
        _atomic_json(
            state_root / G076_INITIAL_TRANSACTION_OUTCOME_FILE,
            {**unknown, "artifact_digest": _canonical_hash(unknown)},
        )
        raise


def run_g076_initial_atomic_activation_fake_only(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    reconciliation_runner: Callable[[], G076ReconciliationEvidence],
    resident_readiness_verifier: Callable[[], bool],
    now_utc: datetime,
) -> str:
    """Exercise exact transaction ordering with synthetic dependencies only."""

    mutated = False

    def mutate() -> None:
        nonlocal mutated
        mutated = True

    return run_g076_initial_atomic_activation(
        state_root=state_root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
        reconciliation_runner=G076FakeOnlyCallable(reconciliation_runner),
        resident_readiness_verifier=G076FakeOnlyCallable(resident_readiness_verifier),
        arm_mutator=G076FakeOnlyCallable(mutate),
        arm_state_verifier=G076FakeOnlyCallable(lambda: mutated),
        now_utc=now_utc,
    )


__all__ = [
    "G076Action",
    "G076ActionOutcome",
    "G076ActionScope",
    "G076ArmState",
    "G076EffectiveState",
    "G076EntryDispatcher",
    "G076EntryState",
    "G076Error",
    "G076ExitDispatcher",
    "G076ExitState",
    "G076FrozenStrategyEvaluator",
    "G076_GENERATION_LABEL",
    "compute_g076_reviewed_files_digest",
    "G076ProcessLock",
    "G076RecoveryScope",
    "G076ReadOnlyReconciler",
    "G076ReconciliationEvidence",
    "G076ReconciliationState",
    "G076ResidentSupervisor",
    "G076SanitizedSnapshot",
    "G076StrategyDecision",
    "G076StrategyObservation",
    "G076StrategyObservationSource",
    "engage_g076_halt",
    "build_g076_recovery_scope",
    "load_g076_recovery_scope",
    "load_g076_release_capability_digest",
    "load_g076_reconciliation",
    "run_g076_initial_atomic_activation",
    "run_g076_initial_atomic_activation_fake_only",
    "run_g076_reconciliation_cycle_once",
    "resume_g076_protected_exit_once",
    "safe_g076_api_status",
    "verify_g076_review_artifacts",
    "verify_g076_scheduler_binding",
]
