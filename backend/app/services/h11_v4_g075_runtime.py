"""G075 final switch-control runtime contracts.

G075 connects the resident lifecycle to generation-bound reconciliation,
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

from app.h11_auto.v4_gmo_runtime_paths import V4_GMO_RUNTIME_STATE_RELATIVE

G075_GENERATION_LABEL = "H11_AUTO_30M_20260802_G075"
G075_PERSISTENT_HALT_FILE = "g075-persistent-halt.json"
G075_RUNTIME_STATUS_FILE = "g075-runtime-status.json"
G075_RECONCILIATION_FILE = "g075-reconciliation-current.json"
G075_OPERATION_60_STARTED_FILE = "g075-operation-60.started.json"
G075_OPERATION_60_RESULT_FILE = "g075-operation-60.result.json"
G075_INITIAL_TRANSACTION_STARTED_FILE = "g075-initial-activation.started.json"
G075_INITIAL_TRANSACTION_OUTCOME_FILE = "g075-initial-activation.outcome.json"
G075_SWITCH_CAPABILITY_FILE = "g075-switch-control-capability.json"
G075_RELEASE_CAPABILITY_FILE = "g075-release-capability.json"
G075_RECOVERY_SCOPE_FILE = "g075-recovery-scope.json"
G075_MAX_EVIDENCE_AGE_SECONDS = 60
G075_RECONCILIATION_INTERVAL_SECONDS = 15
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_CYCLE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


class G075Error(ValueError):
    """Safe-label-only G075 failure."""


class G075ArmState(str, Enum):
    OFF = "OFF"
    ON = "ON"


class G075ReleaseState(str, Enum):
    LOCKED = "LOCKED"
    ENABLED = "ENABLED"


class G075EffectiveState(str, Enum):
    OFF = "OFF"
    ON_WAITING = "ON_WAITING"
    ON_EXIT_ONLY = "ON_EXIT_ONLY"
    EXIT_ONLY = "EXIT_ONLY"
    HALTED = "HALTED"


class G075EntryState(str, Enum):
    DISABLED = "DISABLED"
    WAITING_FOR_RECONCILIATION = "WAITING_FOR_RECONCILIATION"
    WAITING_FOR_SIGNAL = "WAITING_FOR_SIGNAL"
    ENTRY_READY = "ENTRY_READY"
    ACTION_IN_PROGRESS = "ACTION_IN_PROGRESS"
    BLOCKED_POSITION_OPEN = "BLOCKED_POSITION_OPEN"
    HALTED = "HALTED"


class G075ReconciliationState(str, Enum):
    REQUIRED = "REQUIRED"
    IN_PROGRESS = "IN_PROGRESS"
    FRESH_FLAT = "FRESH_FLAT"
    FRESH_PROTECTED = "FRESH_PROTECTED"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"


class G075ActionState(str, Enum):
    IDLE = "IDLE"
    STARTED = "STARTED"
    RESULT_KNOWN = "RESULT_KNOWN"
    UNKNOWN = "UNKNOWN"


class G075ExitState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PROTECTED = "PROTECTED"
    EXIT_DUE = "EXIT_DUE"
    EXIT_IN_PROGRESS = "EXIT_IN_PROGRESS"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


class G075Action(str, Enum):
    ENTRY = "ENTRY"
    PROTECTION = "PROTECTION"
    CANCEL_PROTECTION = "CANCEL_PROTECTION"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TIME_EXIT = "TIME_EXIT"
    CLOSE_POSITION = "CLOSE_POSITION"


class G075ActionOutcome(str, Enum):
    ACCEPTED = "ACCEPTED_KNOWN"
    PROTECTED = "PROTECTED_KNOWN"
    FLAT = "FLAT_KNOWN"
    UNKNOWN = "UNKNOWN"


def _canonical_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    if path.is_symlink():
        raise G075Error("G075_SYMLINK_PATH_REFUSED")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _exclusive_json(path: Path, payload: Mapping[str, object]) -> None:
    if path.is_symlink():
        raise G075Error("G075_SYMLINK_PATH_REFUSED")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise G075Error("G075_ONE_USE_MARKER_ALREADY_EXISTS_NO_RETRY") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True)


def _read_json(path: Path, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise G075Error(label)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G075Error(label) from error
    if not isinstance(payload, dict):
        raise G075Error(label)
    return payload


def _require_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise G075Error(label)
    return value


@dataclass(frozen=True)
class G075SanitizedSnapshot:
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
                raise G075Error("G075_SNAPSHOT_COUNT_INVALID")
        if self.broker_get_count > 3 or self.private_api_read_count > 3:
            raise G075Error("G075_SNAPSHOT_READ_COUNT_INVALID")
        if self.credential_read_count > 1 or self.broker_write is not False:
            raise G075Error("G075_SNAPSHOT_BOUNDARY_VIOLATION")
        if self.broker_post_count != 0:
            raise G075Error("G075_SNAPSHOT_POST_COUNT_INVALID")
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
            raise G075Error("G075_SNAPSHOT_BOOLEAN_INVALID")
        if self.position_side not in {None, "BUY", "SELL"}:
            raise G075Error("G075_SNAPSHOT_SIDE_INVALID")
        if (self.open_position_count == 0) is (self.position_side is not None):
            raise G075Error("G075_SNAPSHOT_SIDE_MISMATCH")


@dataclass(frozen=True)
class G075ReconciliationEvidence:
    generation_label: str
    generation_digest: str
    reviewed_files_digest: str
    cycle_id: str
    observed_at_utc: str
    state: G075ReconciliationState
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


def _snapshot_state(snapshot: G075SanitizedSnapshot) -> G075ReconciliationState:
    if snapshot.unknown or snapshot.pending_transport:
        return G075ReconciliationState.UNKNOWN
    if snapshot.open_position_count == 0:
        return (
            G075ReconciliationState.FRESH_FLAT
            if snapshot.active_order_count == 0
            else G075ReconciliationState.UNKNOWN
        )
    if snapshot.active_order_count > 0 and all(
        (snapshot.ownership_exact, snapshot.quantity_matches, snapshot.protection_confirmed)
    ):
        return G075ReconciliationState.FRESH_PROTECTED
    return G075ReconciliationState.UNKNOWN


def _evidence_from_snapshot(
    *,
    snapshot: G075SanitizedSnapshot,
    generation_digest: str,
    reviewed_files_digest: str,
    cycle_id: str,
    now_utc: datetime,
) -> G075ReconciliationEvidence:
    _require_digest(generation_digest, "G075_GENERATION_DIGEST_INVALID")
    _require_digest(reviewed_files_digest, "G075_REVIEWED_DIGEST_INVALID")
    if not _CYCLE.fullmatch(cycle_id) or now_utc.tzinfo is None:
        raise G075Error("G075_CYCLE_INPUT_INVALID")
    state = _snapshot_state(snapshot)
    base: dict[str, object] = {
        "generation_label": G075_GENERATION_LABEL,
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
    return G075ReconciliationEvidence(
        **{key: value for key, value in base.items() if key != "state"},
        state=state,
        artifact_digest=_canonical_hash(base),
    )


class G075ReadOnlyReconciler(Protocol):
    def reconcile_once(self, *, cycle_id: str, now_utc: datetime) -> G075SanitizedSnapshot: ...


def run_g075_reconciliation_cycle_once(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    cycle_id: str,
    reconciler: G075ReadOnlyReconciler,
    now_utc: datetime,
) -> G075ReconciliationEvidence:
    marker = state_root / f"g075-reconciliation-{cycle_id}.started.json"
    outcome = state_root / f"g075-reconciliation-{cycle_id}.outcome.json"
    if not _CYCLE.fullmatch(cycle_id):
        raise G075Error("G075_CYCLE_ID_INVALID")
    if marker.exists() or marker.is_symlink() or outcome.exists() or outcome.is_symlink():
        raise G075Error("G075_RECONCILIATION_CYCLE_ALREADY_STARTED_NO_RETRY")
    _exclusive_json(
        marker,
        {
            "generation_label": G075_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "cycle_id": cycle_id,
            "status": "STARTED",
        },
    )
    snapshot: G075SanitizedSnapshot | None = None
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
            state_root / G075_RECONCILIATION_FILE,
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
                    G075ReconciliationState.UNKNOWN,
                }
                else "UNKNOWN",
                "generation_label": G075_GENERATION_LABEL,
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "cycle_id": cycle_id,
                "broker_post_count": 0,
                "private_api_read_count": evidence.private_api_read_count,
                "credential_read_count": evidence.credential_read_count,
            },
        )
        if evidence.state is G075ReconciliationState.UNKNOWN:
            engage_g075_halt(state_root=state_root, reason="G075_RECONCILIATION_UNKNOWN")
            raise G075Error("G075_RECONCILIATION_UNKNOWN_NO_RETRY")
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
                    "generation_label": G075_GENERATION_LABEL,
                    "generation_digest": generation_digest,
                    "reviewed_files_digest": reviewed_files_digest,
                    "cycle_id": cycle_id,
                    "broker_get_count": counts[0],
                    "private_api_read_count": counts[1],
                    "credential_read_count": counts[2],
                    "broker_post_count": 0,
                },
            )
        engage_g075_halt(state_root=state_root, reason="G075_RECONCILIATION_UNKNOWN")
        if isinstance(error, G075Error):
            raise
        raise G075Error("G075_RECONCILIATION_UNKNOWN_NO_RETRY") from error
    # NOTE: D-P2-2 (Safety P2-1) kept the narrow `except Exception` here by
    # design.  The above block is the recovery-time poisoning path; widening
    # to BaseException would re-raise KeyboardInterrupt INTO the outcome
    # write (already attempted above), risking a half-written file.  The
    # transport-level BaseException broadening in
    # h11_v4_gmo_actual_transport.py is the correct boundary.


def load_g075_reconciliation(
    *, state_root: Path, generation_digest: str, reviewed_files_digest: str, now_utc: datetime
) -> G075ReconciliationEvidence | None:
    path = state_root / G075_RECONCILIATION_FILE
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = _read_json(path, "G075_RECONCILIATION_INVALID")
        state = G075ReconciliationState(payload.pop("state"))
        artifact_digest = str(payload.pop("artifact_digest"))
        evidence = G075ReconciliationEvidence(
            **payload, state=state, artifact_digest=artifact_digest
        )
    except (G075Error, KeyError, TypeError, ValueError) as error:
        raise G075Error("G075_RECONCILIATION_INVALID") from error
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
        raise G075Error("G075_RECONCILIATION_DIGEST_MISMATCH")
    if age < 0 or age > G075_MAX_EVIDENCE_AGE_SECONDS:
        return replace(evidence, state=G075ReconciliationState.STALE)
    return evidence


def engage_g075_halt(*, state_root: Path, reason: str) -> None:
    path = state_root / G075_PERSISTENT_HALT_FILE
    if path.exists() or path.is_symlink():
        return
    _atomic_json(
        path,
        {
            "generation_label": G075_GENERATION_LABEL,
            "status": "HALTED",
            "reason": reason,
            "broker_write": False,
            "actual_post_count": 0,
        },
    )


def require_g075_no_unresolved_halt(*, repository: Path) -> None:
    """Refuse startup while any generation root holds an unresolved halt.

    State roots are keyed by generation digest, so minting a generation or
    re-baking a digest silently re-keys the runtime and orphans a latched
    persistent halt.  This scan is deliberately independent of the frozen
    generation manifest: manifest edits are the mechanism by which the two
    existing halts were orphaned, so the manifest cannot be the authority on
    whether a halt is outstanding.  There is intentionally no release path
    here; discharging a halt is an operator decision and a separate design.
    """
    runtime_root = repository.resolve() / V4_GMO_RUNTIME_STATE_RELATIVE
    if not runtime_root.is_dir():
        return
    for generation_root in sorted(runtime_root.glob("generation-*")):
        for halt_path in sorted(generation_root.glob("g0*-persistent-halt.json")):
            if halt_path.exists() or halt_path.is_symlink():
                raise G075Error("G075_UNRESOLVED_HALT_PRESENT")


@dataclass(frozen=True)
class G075StrategyObservation:
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
class G075StrategyDecision:
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


class G075StrategyObservationSource(Protocol):
    def observe(self, *, now_utc: datetime) -> G075StrategyObservation: ...


class G075FrozenStrategyEvaluator:
    """Concrete evaluator bound to the frozen strategy artifact and digests."""

    def __init__(
        self,
        *,
        source: G075StrategyObservationSource,
        generation_digest: str,
        reviewed_files_digest: str,
        strategy_artifact_digest: str,
    ) -> None:
        self.source = source
        self.generation_digest = _require_digest(
            generation_digest, "G075_GENERATION_DIGEST_INVALID"
        )
        self.reviewed_files_digest = _require_digest(
            reviewed_files_digest, "G075_REVIEWED_DIGEST_INVALID"
        )
        self.strategy_artifact_digest = _require_digest(
            strategy_artifact_digest, "G075_STRATEGY_DIGEST_INVALID"
        )

    def evaluate(
        self, *, now_utc: datetime, evidence: G075ReconciliationEvidence
    ) -> G075StrategyDecision:
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
            and observation.position_flat is (evidence.state is G075ReconciliationState.FRESH_FLAT)
            and observation.active_orders_zero is (evidence.active_order_count == 0)
        )
        return G075StrategyDecision(
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
class G075ActionScope:
    generation_digest: str
    reviewed_files_digest: str
    release_capability_digest: str
    reconciliation_artifact_digest: str
    strategy_artifact_digest: str
    cycle_id: str
    action: G075Action
    symbol: str
    quantity: int
    side: str
    expires_at_utc: str
    action_key: str
    scope_digest: str

    def __bool__(self) -> bool:
        return False


class G075ActionPort(Protocol):
    def attempt_once(self, scope: G075ActionScope) -> G075ActionOutcome: ...


@dataclass(frozen=True)
class G075RecoveryScope:
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


def build_g075_recovery_scope(
    *,
    repository: Path,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    evidence: G075ReconciliationEvidence,
    side: str,
    action_key: str,
    now_utc: datetime,
    lifetime_seconds: int = 15,
) -> G075RecoveryScope:
    """Bind restart recovery to fresh, explicitly protected ownership evidence."""

    release_digest = load_g075_release_capability_digest(
        repository=repository,
        state_root=state_root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
    )
    action_digest = _require_digest(action_key, "G075_RECOVERY_ACTION_KEY_INVALID")
    if (
        side not in {"BUY", "SELL"}
        or now_utc.tzinfo is None
        or lifetime_seconds < 1
        or lifetime_seconds > 60
        or
        evidence.state is not G075ReconciliationState.FRESH_PROTECTED
        or evidence.generation_digest != generation_digest
        or evidence.reviewed_files_digest != reviewed_files_digest
        or evidence.position_open is not True
        or evidence.ownership_exact is not True
        or evidence.quantity_matches is not True
        or evidence.protection_confirmed is not True
    ):
        raise G075Error("G075_RECOVERY_EVIDENCE_NOT_CLEAR")
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
    scope = G075RecoveryScope(**base, scope_digest=_canonical_hash(base))
    _exclusive_json(
        state_root / f"g075-recovery-{action_digest.removeprefix('sha256:')}.started.json",
        {
            "schema": "H11_V4_G075_RECOVERY_STARTED_V1",
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "action_key": action_digest,
            "scope_digest": scope.scope_digest,
        },
    )
    _atomic_json(
        state_root / G075_RECOVERY_SCOPE_FILE,
        {**asdict(scope), "schema": "H11_V4_G075_RECOVERY_SCOPE_V1"},
    )
    return scope


def _g075_pre_dispatch_retryable(error: BaseException) -> bool:
    """True when a port failure is a pre-dispatch failure (no POST sent).

    The transport's unknown-post callback is the only authority on "a POST may
    have reached the broker": it latches the coordinator store before
    re-raising.  The coordinated path re-raises a labeled error when the store
    is not latched; the G075 live port applies the same classification.
    Imported lazily: the transport module imports this module, so a module-level
    import here would be circular.
    """
    from app.services.h11_v4_gmo_coordinated_actual_path import (
        V4GmoCoordinatedPathError,
    )

    return (
        isinstance(error, V4GmoCoordinatedPathError)
        and str(error) == "V4_GMO_PRE_DISPATCH_FAILURE_NO_POST_SENT"
    )


class G075OneShotActionDispatcher:
    def __init__(self, *, state_root: Path, port: G075ActionPort) -> None:
        self.state_root = state_root
        self.port = port

    def attempt_once(
        self,
        *,
        cycle_id: str,
        action: G075Action,
        side: str,
        quantity: int,
        reconciliation_artifact_digest: str,
        now_utc: datetime,
        lifetime_seconds: int = 15,
    ) -> G075ActionOutcome:
        if side not in {"BUY", "SELL"} or quantity != 1_000 or now_utc.tzinfo is None:
            raise G075Error("G075_ACTION_SCOPE_INVALID")
        _require_digest(
            reconciliation_artifact_digest,
            "G075_RECONCILIATION_ARTIFACT_DIGEST_INVALID",
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
        scope = G075ActionScope(
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
            / f"g075-action-{scope.scope_digest.removeprefix('sha256:')}.started.json"
        )
        _exclusive_json(
            marker,
            {
                "generation_label": G075_GENERATION_LABEL,
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
            if _g075_pre_dispatch_retryable(error):
                # Pre-dispatch failure: no POST may have reached the broker
                # (the transport's unknown-post callback is the only authority
                # that latches).  Drop the started marker so the action can be
                # retried, and do NOT manufacture a false-UNKNOWN halt.
                os.remove(marker)
                raise G075Error("G075_ACTION_PRE_DISPATCH_FAILED_RETRYABLE") from error
            _exclusive_json(
                marker.with_name(marker.name.replace(".started.", ".result.")),
                {
                    "action": action.value,
                    "action_key": scope.action_key,
                    "scope_digest": scope.scope_digest,
                    "status": G075ActionOutcome.UNKNOWN.value,
                },
            )
            engage_g075_halt(state_root=self.state_root, reason="G075_ACTION_RESULT_UNKNOWN")
            raise G075Error("G075_ACTION_RESULT_UNKNOWN_NO_RETRY") from error
        if not isinstance(outcome, G075ActionOutcome) or outcome is G075ActionOutcome.UNKNOWN:
            _exclusive_json(
                marker.with_name(marker.name.replace(".started.", ".result.")),
                {
                    "action": action.value,
                    "action_key": scope.action_key,
                    "scope_digest": scope.scope_digest,
                    "status": G075ActionOutcome.UNKNOWN.value,
                },
            )
            engage_g075_halt(state_root=self.state_root, reason="G075_ACTION_RESULT_UNKNOWN")
            raise G075Error("G075_ACTION_RESULT_UNKNOWN_NO_RETRY")
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
        port: G075ActionPort,
        generation_digest: str,
        reviewed_files_digest: str,
        release_capability_digest: str,
        strategy_artifact_digest: str,
    ) -> G075OneShotActionDispatcher:
        _require_digest(generation_digest, "G075_GENERATION_DIGEST_INVALID")
        _require_digest(reviewed_files_digest, "G075_REVIEWED_DIGEST_INVALID")
        _require_digest(release_capability_digest, "G075_RELEASE_CAPABILITY_DIGEST_INVALID")
        _require_digest(strategy_artifact_digest, "G075_STRATEGY_ARTIFACT_DIGEST_INVALID")
        instance = cls(state_root=state_root, port=port)
        instance._generation_digest = generation_digest
        instance._reviewed_files_digest = reviewed_files_digest
        instance._release_capability_digest = release_capability_digest
        instance._strategy_artifact_digest = strategy_artifact_digest
        return instance


class G075EntryDispatcher:
    def __init__(self, *, actions: G075OneShotActionDispatcher) -> None:
        self.actions = actions

    def enter_and_protect_once(
        self,
        *,
        decision: G075StrategyDecision,
        evidence: G075ReconciliationEvidence,
        cycle_id: str,
        side: str,
        now_utc: datetime,
    ) -> tuple[G075ActionOutcome, G075ActionOutcome]:
        if evidence.state is not G075ReconciliationState.FRESH_FLAT or not decision.gate_open(
            generation_digest=evidence.generation_digest,
            reviewed_files_digest=evidence.reviewed_files_digest,
        ):
            raise G075Error("G075_ENTRY_GATE_NOT_OPEN")
        entry = self.actions.attempt_once(
            cycle_id=cycle_id, action=G075Action.ENTRY, side=side, quantity=1_000, now_utc=now_utc
            , reconciliation_artifact_digest=evidence.artifact_digest
        )
        if entry is not G075ActionOutcome.ACCEPTED:
            raise G075Error("G075_ENTRY_NOT_ACCEPTED")
        protection = self.actions.attempt_once(
            cycle_id=cycle_id,
            action=G075Action.PROTECTION,
            side=side,
            quantity=1_000,
            reconciliation_artifact_digest=evidence.artifact_digest,
            now_utc=now_utc,
        )
        if protection is not G075ActionOutcome.PROTECTED:
            engage_g075_halt(
                state_root=self.actions.state_root, reason="G075_PROTECTION_NOT_CONFIRMED"
            )
            raise G075Error("G075_PROTECTION_NOT_CONFIRMED")
        return entry, protection


class G075ExitDispatcher:
    def __init__(self, *, actions: G075OneShotActionDispatcher) -> None:
        self.actions = actions

    def exit_once(
        self,
        *,
        evidence: G075ReconciliationEvidence,
        cycle_id: str,
        side: str,
        reason: G075Action,
        now_utc: datetime,
    ) -> tuple[G075ActionOutcome, G075ActionOutcome]:
        if evidence.state is not G075ReconciliationState.FRESH_PROTECTED:
            raise G075Error("G075_EXIT_PROTECTION_NOT_CONFIRMED")
        if reason not in {G075Action.TAKE_PROFIT, G075Action.STOP_LOSS, G075Action.TIME_EXIT}:
            raise G075Error("G075_EXIT_REASON_INVALID")
        cancel = self.actions.attempt_once(
            cycle_id=cycle_id,
            action=G075Action.CANCEL_PROTECTION,
            side=side,
            quantity=1_000,
            reconciliation_artifact_digest=evidence.artifact_digest,
            now_utc=now_utc,
        )
        if cancel is not G075ActionOutcome.ACCEPTED:
            raise G075Error("G075_EXIT_CANCEL_NOT_ACCEPTED")
        close = self.actions.attempt_once(
            cycle_id=cycle_id,
            action=G075Action.CLOSE_POSITION,
            side=side,
            quantity=1_000,
            reconciliation_artifact_digest=evidence.artifact_digest,
            now_utc=now_utc,
        )
        if close is not G075ActionOutcome.FLAT:
            raise G075Error("G075_EXIT_NOT_FLAT")
        return cancel, close


@dataclass
class G075ProcessLock:
    state_root: Path
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
        if self.path.is_symlink():
            raise G075Error("G075_PROCESS_LOCK_SYMLINK_REFUSED")
        if self.path.exists():
            try:
                payload = _read_json(self.path, "G075_PROCESS_LOCK_INVALID")
                pid = int(payload["pid"])
            except (G075Error, KeyError, TypeError, ValueError):
                raise G075Error("G075_PROCESS_LOCK_INVALID") from None
            if self._pid_alive(pid):
                raise G075Error("G075_PROCESS_LOCK_CONFLICT")
            os.remove(self.path)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise G075Error("G075_PROCESS_LOCK_CONFLICT") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "generation_label": G075_GENERATION_LABEL}, stream)
        self.acquired = True

    def release(self) -> None:
        if self.acquired and self.path.is_file() and not self.path.is_symlink():
            os.remove(self.path)
        self.acquired = False


def _capability_valid(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    repository: Path,
) -> bool:
    if repository is not None:
        try:
            require_g075_no_unresolved_halt(repository=repository)
        except Exception:  # noqa: BLE001
            # Scan failure is fail-closed: an unresolved halt OR an
            # unreadable runtime directory both mean "not clear".
            return False
    try:
        capability = _read_json(state_root / G075_SWITCH_CAPABILITY_FILE, "G075_CAPABILITY_INVALID")
        release = _read_json(
            state_root / G075_RELEASE_CAPABILITY_FILE, "G075_RELEASE_CAPABILITY_INVALID"
        )
        outcome = _read_json(
            state_root / G075_INITIAL_TRANSACTION_OUTCOME_FILE, "G075_TRANSACTION_OUTCOME_INVALID"
        )
        operation = _read_json(
            state_root / G075_OPERATION_60_RESULT_FILE, "G075_OPERATION_60_RESULT_INVALID"
        )
        artifact = capability.pop("artifact_digest")
        release_artifact = release.pop("artifact_digest")
        outcome_artifact = outcome.pop("artifact_digest")
        return (
            outcome.get("status") == "PASSED"
            and outcome.get("generation_label") == G075_GENERATION_LABEL
            and outcome.get("generation_digest") == generation_digest
            and outcome.get("reviewed_files_digest") == reviewed_files_digest
            and outcome.get("broker_post_count") == 0
            and outcome_artifact == _canonical_hash(outcome)
            and operation.get("status") == "PASSED"
            and operation.get("generation_label") == G075_GENERATION_LABEL
            and operation.get("generation_digest") == generation_digest
            and operation.get("reviewed_files_digest") == reviewed_files_digest
            and capability.get("status") == "ENABLED"
            and release.get("status") == "ENABLED"
            and capability.get("generation_label") == G075_GENERATION_LABEL
            and release.get("generation_label") == G075_GENERATION_LABEL
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
            and not (state_root / G075_PERSISTENT_HALT_FILE).exists()
        )
    except (G075Error, KeyError, TypeError, ValueError):
        return False


def load_g075_release_capability_digest(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    repository: Path,
) -> str:
    if not _capability_valid(
        state_root=state_root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
        repository=repository,
    ):
        raise G075Error("G075_RELEASE_CAPABILITY_LOCKED")
    release = _read_json(
        state_root / G075_RELEASE_CAPABILITY_FILE, "G075_RELEASE_CAPABILITY_INVALID"
    )
    digest = release.get("artifact_digest")
    return _require_digest(digest, "G075_RELEASE_CAPABILITY_DIGEST_INVALID")


@dataclass
class G075ResidentSupervisor:
    state_root: Path
    generation_digest: str
    reviewed_files_digest: str
    repository: Path
    reconciliation_runner: Callable[[str, datetime], G075ReconciliationEvidence] | None = None
    strategy_evaluator: G075FrozenStrategyEvaluator | None = None
    entry_dispatcher: G075EntryDispatcher | None = None
    exit_dispatcher: G075ExitDispatcher | None = None
    exit_reason_provider: (
        Callable[[G075ReconciliationEvidence, datetime], G075Action | None] | None
    ) = None
    cycle_index: int = 0
    runtime_nonce: str = field(default_factory=lambda: secrets.token_hex(8), repr=False)

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
            raise G075Error("G075_RUNTIME_CLOCK_INVALID")
        self.state_root.mkdir(parents=True, exist_ok=True)
        halted = (self.state_root / G075_PERSISTENT_HALT_FILE).exists() or (
            self.state_root / G075_PERSISTENT_HALT_FILE
        ).is_symlink()
        predecessor_halted = False
        if not halted and self.repository is not None:
            try:
                require_g075_no_unresolved_halt(repository=self.repository)
            except G075Error:
                halted = True
                predecessor_halted = True
        evidence = None
        if not halted:
            try:
                evidence = load_g075_reconciliation(
                    state_root=self.state_root,
                    generation_digest=self.generation_digest,
                    reviewed_files_digest=self.reviewed_files_digest,
                    now_utc=now_utc,
                )
            except G075Error:
                halted = True
            if (
                not halted
                and self.reconciliation_runner is not None
                and (evidence is None or evidence.state is G075ReconciliationState.STALE)
            ):
                try:
                    evidence = self.reconciliation_runner(self._next_cycle(), now_utc)
                except G075Error:
                    halted = True
        capability = _capability_valid(
            state_root=self.state_root,
            generation_digest=self.generation_digest,
            reviewed_files_digest=self.reviewed_files_digest,
            repository=self.repository,
        )
        decision: G075StrategyDecision | None = None
        effective = G075EffectiveState.OFF
        entry_gate = False
        entry_state = G075EntryState.DISABLED
        reason = "G075_ARM_OFF"
        exit_state = G075ExitState.NOT_REQUIRED
        action_state = G075ActionState.IDLE
        if halted or not process_lock_single or not dead_man_alive or not heartbeat_chain_beat:
            halted = True
            effective = G075EffectiveState.HALTED
            entry_state = G075EntryState.HALTED
            reason = (
                "G075_UNRESOLVED_HALT_PRESENT"
                if predecessor_halted
                else "G075_RUNTIME_HEALTH_NOT_CLEAR"
            )
        elif evidence is not None and evidence.state in {
            G075ReconciliationState.UNKNOWN,
            G075ReconciliationState.STALE,
        }:
            halted = True
            effective = G075EffectiveState.HALTED
            entry_state = G075EntryState.HALTED
            reason = "G075_RECONCILIATION_NOT_CLEAR"
            exit_state = G075ExitState.UNKNOWN
        elif evidence is not None and evidence.position_open:
            protected = all(
                (evidence.ownership_exact, evidence.quantity_matches, evidence.protection_confirmed)
            )
            if not protected or evidence.state is not G075ReconciliationState.FRESH_PROTECTED:
                halted = True
                effective = G075EffectiveState.HALTED
                entry_state = G075EntryState.HALTED
                reason = "G075_POSITION_PROTECTION_NOT_CONFIRMED"
                exit_state = G075ExitState.UNKNOWN
            else:
                effective = (
                    G075EffectiveState.ON_EXIT_ONLY if arm_on else G075EffectiveState.EXIT_ONLY
                )
                entry_state = G075EntryState.BLOCKED_POSITION_OPEN
                reason = "G075_PROTECTED_POSITION_EXIT_MANAGEMENT"
                exit_state = G075ExitState.PROTECTED
                if self.exit_reason_provider is not None and self.exit_dispatcher is not None:
                    exit_reason = self.exit_reason_provider(evidence, now_utc)
                    if exit_reason is not None:
                        if evidence.position_side not in {"BUY", "SELL"}:
                            raise G075Error("G075_EXIT_SIDE_UNKNOWN")
                        action_state = G075ActionState.STARTED
                        self.exit_dispatcher.exit_once(
                            evidence=evidence,
                            cycle_id=evidence.cycle_id,
                            side=evidence.position_side,
                            reason=exit_reason,
                            now_utc=now_utc,
                        )
                        action_state = G075ActionState.RESULT_KNOWN
                        entry_gate = False
        elif not arm_on:
            effective = G075EffectiveState.OFF
            entry_state = G075EntryState.DISABLED
            reason = "G075_ARM_OFF"
        elif not capability:
            effective = G075EffectiveState.HALTED
            entry_state = G075EntryState.HALTED
            reason = "G075_RELEASE_CAPABILITY_LOCKED"
        elif evidence is None:
            effective = G075EffectiveState.ON_WAITING
            entry_state = G075EntryState.WAITING_FOR_RECONCILIATION
            reason = "G075_RECONCILIATION_REQUIRED"
        elif evidence.state is G075ReconciliationState.FRESH_FLAT:
            effective = G075EffectiveState.ON_WAITING
            entry_state = G075EntryState.WAITING_FOR_SIGNAL
            reason = "G075_WAITING_FOR_SIGNAL"
            if self.strategy_evaluator is not None:
                try:
                    decision = self.strategy_evaluator.evaluate(now_utc=now_utc, evidence=evidence)
                    if not decision.binding_valid(
                        generation_digest=self.generation_digest,
                        reviewed_files_digest=self.reviewed_files_digest,
                    ):
                        halted = True
                        effective = G075EffectiveState.HALTED
                        entry_state = G075EntryState.HALTED
                        reason = "G075_STRATEGY_BINDING_NOT_CLEAR"
                    else:
                        entry_gate = decision.gate_open(
                            generation_digest=self.generation_digest,
                            reviewed_files_digest=self.reviewed_files_digest,
                        )
                        if entry_gate:
                            entry_state = G075EntryState.ENTRY_READY
                            reason = "G075_ENTRY_GATE_OPEN"
                            if self.entry_dispatcher is not None:
                                action_state = G075ActionState.STARTED
                                self.entry_dispatcher.enter_and_protect_once(
                                    decision=decision,
                                    evidence=evidence,
                                    cycle_id=evidence.cycle_id,
                                    side=decision.side,
                                    now_utc=now_utc,
                                )
                                action_state = G075ActionState.RESULT_KNOWN
                                entry_gate = False
                                entry_state = G075EntryState.ACTION_IN_PROGRESS
                                reason = "G075_ENTRY_LIFECYCLE_RESULT_KNOWN"
                except (G075Error, TypeError, ValueError):
                    halted = True
                    effective = G075EffectiveState.HALTED
                    entry_state = G075EntryState.HALTED
                    reason = "G075_STRATEGY_EVALUATION_UNKNOWN"
        else:
            halted = True
            effective = G075EffectiveState.HALTED
            entry_state = G075EntryState.HALTED
            reason = "G075_RECONCILIATION_STATE_INVALID"
        if halted:
            entry_gate = False
        observed = now_utc.astimezone(UTC).isoformat()
        status: dict[str, object] = {
            "schema": "H11_V4_G075_RUNTIME_STATUS_V1",
            "generation_label": G075_GENERATION_LABEL,
            "generation_digest": self.generation_digest,
            "reviewed_files_digest": self.reviewed_files_digest,
            "arm_state": G075ArmState.ON.value if arm_on else G075ArmState.OFF.value,
            "release_state": G075ReleaseState.ENABLED.value
            if capability
            else G075ReleaseState.LOCKED.value,
            "effective_state": effective.value,
            "entry_gate_open": entry_gate,
            "entry_state": entry_state.value,
            "reconciliation_state": evidence.state.value
            if evidence
            else G075ReconciliationState.REQUIRED.value,
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
        _atomic_json(self.state_root / G075_RUNTIME_STATUS_FILE, status)
        heartbeat = {
            "schema": "H11_V4_G075_RESIDENT_HEARTBEAT_V1",
            "generation_label": G075_GENERATION_LABEL,
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
            prior = _read_json(chain_path, "G075_HEARTBEAT_CHAIN_INVALID")
            previous = str(prior.get("chain_hash", previous))
            index = int(prior.get("chain_index", 0)) + 1
        chain_base = {**heartbeat, "chain_index": index, "previous_chain_hash": previous}
        _atomic_json(chain_path, {**chain_base, "chain_hash": _canonical_hash(chain_base)})
        return status


def safe_g075_api_status(
    *,
    state_root: Path,
    arm_on: bool,
    generation_digest: str,
    reviewed_files_digest: str,
    repository: Path,
) -> dict[str, object]:
    capability = _capability_valid(
        state_root=state_root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
        repository=repository,
    )
    try:
        status = _read_json(state_root / G075_RUNTIME_STATUS_FILE, "G075_RUNTIME_STATUS_REQUIRED")
    except G075Error:
        status = {
            "effective_state": G075EffectiveState.OFF.value,
            "entry_gate_open": False,
            "entry_state": G075EntryState.DISABLED.value,
            "reconciliation_state": G075ReconciliationState.REQUIRED.value,
            "safe_reason_label": "G075_RUNTIME_STATUS_REQUIRED",
            "lock_single_owner": False,
            "persistent_halt": False,
        }
    effective = str(status.get("effective_state", G075EffectiveState.HALTED.value))
    halt_scan = "NOT_CHECKED"
    scan_halted = False
    if repository is not None:
        try:
            require_g075_no_unresolved_halt(repository=repository)
            halt_scan = "CLEAR"
        except G075Error:
            halt_scan = "UNRESOLVED_HALT_PRESENT"
            scan_halted = True
        except Exception:  # noqa: BLE001
            # The display must never crash on a scan failure; report it.
            halt_scan = "SCAN_FAILED"
    persistent_halt = bool(status.get("persistent_halt")) or scan_halted
    return {
        **status,
        "control_plane_state": "HALTED" if persistent_halt else "READY",
        "persistent_halt": persistent_halt,
        "halt_scan": halt_scan,
        "generation_label": G075_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "arm_state": G075ArmState.ON.value if arm_on else G075ArmState.OFF.value,
        "release_state": G075ReleaseState.ENABLED.value
        if capability
        else G075ReleaseState.LOCKED.value,
        "atomic_activation_complete": capability,
        "runtime_activation_available": capability,
        "switch_only_rearm_available": capability,
        "local_arm_on_available": True,
        "arm_control_available": True,
        "arm_ready": True,
        "scheduler_ready": status.get("lock_single_owner") is True,
        "position_reconciliation_ready": status.get("reconciliation_state")
        in {
            G075ReconciliationState.FRESH_FLAT.value,
            G075ReconciliationState.FRESH_PROTECTED.value,
        },
        "daily_authorization_required": False,
        "per_trade_confirmation_required": False,
        "live_ready": False,
        "unattended_live_supported": False,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "entry_gate_open": bool(status.get("entry_gate_open"))
        and effective == G075EffectiveState.ON_WAITING.value,
    }


def verify_g075_scheduler_binding(
    *, generation: object, repository: Path, plist_path: Path, state_root: Path, now_utc: datetime
) -> None:
    if generation.generation_label != G075_GENERATION_LABEL:
        raise G075Error("G075_GENERATION_REQUIRED")
    if (state_root / G075_PERSISTENT_HALT_FILE).exists() or (
        state_root / G075_PERSISTENT_HALT_FILE
    ).is_symlink():
        raise G075Error("G075_PERSISTENT_HALT_PRESENT")
    if not plist_path.is_file() or plist_path.is_symlink():
        raise G075Error("G075_SCHEDULER_PLIST_INVALID")
    try:
        payload = plistlib.loads(plist_path.read_bytes())
        arguments = payload["ProgramArguments"]
    except (OSError, KeyError, TypeError, ValueError, plistlib.InvalidFileException) as error:
        raise G075Error("G075_SCHEDULER_PLIST_INVALID") from error
    expected = str(
        repository.resolve() / "backend/scripts/h11_auto_v4_g075_runtime_bootstrap.py"
    )
    expected_arguments = [
        str((repository.resolve() / "backend/.venv/bin/python").resolve()),
        expected,
        "--repository",
        str(repository.resolve()),
        "--expected-reviewed-files-digest",
        str(generation.implementation_digest),
        "--expected-generation-digest",
        str(generation.digest),
    ]
    if arguments != expected_arguments:
        raise G075Error("G075_SCHEDULER_BINDING_INVALID")
    required = (
        state_root / "heartbeat.json",
        state_root / "process.lock",
        state_root / "dead-man.json",
        state_root / "heartbeat-chain.json",
        state_root / G075_RUNTIME_STATUS_FILE,
    )
    if any(not path.is_file() or path.is_symlink() for path in required):
        raise G075Error("G075_RUNTIME_READINESS_MISSING")
    heartbeat = _read_json(required[0], "G075_HEARTBEAT_INVALID")
    lock = _read_json(required[1], "G075_PROCESS_LOCK_INVALID")
    dead_man = _read_json(required[2], "G075_DEAD_MAN_INVALID")
    chain = _read_json(required[3], "G075_HEARTBEAT_CHAIN_INVALID")
    status = _read_json(required[4], "G075_RUNTIME_STATUS_INVALID")
    try:
        lock_pid = int(lock["pid"])
        observed = datetime.fromisoformat(str(heartbeat["heartbeat_at_utc"])).astimezone(UTC)
    except (KeyError, TypeError, ValueError) as error:
        raise G075Error("G075_RUNTIME_READINESS_NOT_CLEAR") from error
    age = (now_utc.astimezone(UTC) - observed).total_seconds()
    chain_base = {key: value for key, value in chain.items() if key != "chain_hash"}
    if (
        lock.get("generation_label") != G075_GENERATION_LABEL
        or not G075ProcessLock._pid_alive(lock_pid)
        or heartbeat.get("generation_digest") != generation.digest
        or heartbeat.get("reviewed_files_digest") != generation.implementation_digest
        or heartbeat.get("broker_write") is not False
        or heartbeat.get("actual_post_count") != 0
        or heartbeat.get("pending") is not False
        or heartbeat.get("unknown_halt") is not False
        or dead_man.get("alive") is not True
        or dead_man.get("generation_digest") != generation.digest
        or dead_man.get("reviewed_files_digest") != generation.implementation_digest
        or status.get("generation_digest") != generation.digest
        or status.get("reviewed_files_digest") != generation.implementation_digest
        or status.get("persistent_halt") is not False
        or status.get("broker_write") is not False
        or status.get("actual_post_count") != 0
        or chain.get("chain_index", 0) < 1
        or not isinstance(chain.get("previous_chain_hash"), str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", chain["previous_chain_hash"])
        or chain.get("chain_hash") != _canonical_hash(chain_base)
        or age < 0
        or age > G075_MAX_EVIDENCE_AGE_SECONDS
    ):
        raise G075Error("G075_RUNTIME_READINESS_NOT_CLEAR")


def verify_g075_review_artifacts(
    *, repository: Path, generation_digest: str, reviewed_files_digest: str
) -> None:
    root = repository / "docs/templates"
    paths = (
        root / "h11_v4_g075_frozen_generation.json",
        root / "h11_v4_g075_runtime_commissioning_evidence.json",
        root / "h11_v4_g075_independent_review_attestation.json",
    )
    try:
        manifest, evidence, attestation = tuple(
            json.loads(path.read_text(encoding="utf-8")) for path in paths
        )
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise G075Error("G075_REVIEW_ARTIFACT_INVALID") from error
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
    if (
        manifest.get("generation_label") != G075_GENERATION_LABEL
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
    ):
        raise G075Error("G075_REVIEW_ARTIFACT_BINDING_MISMATCH")


def run_g075_initial_atomic_activation(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    reconciliation_runner: Callable[[], G075ReconciliationEvidence],
    arm_mutator: Callable[[], None],
    arm_state_verifier: Callable[[], bool],
    now_utc: datetime,
) -> str:
    """Run the one-use transaction with injected, separately reviewed ports."""

    operation = _read_json(
        state_root / G075_OPERATION_60_RESULT_FILE, "G075_OPERATION_60_RESULT_INVALID"
    )
    if (
        operation.get("status") != "PASSED"
        or operation.get("generation_label") != G075_GENERATION_LABEL
        or operation.get("generation_digest") != generation_digest
        or operation.get("reviewed_files_digest") != reviewed_files_digest
    ):
        raise G075Error("G075_OPERATION_60_PASSED_REQUIRED")

    _exclusive_json(
        state_root / G075_INITIAL_TRANSACTION_STARTED_FILE,
        {
            "generation_label": G075_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "status": "STARTED",
        },
    )
    try:
        evidence = reconciliation_runner()
        if evidence.state not in {
            G075ReconciliationState.FRESH_FLAT,
            G075ReconciliationState.FRESH_PROTECTED,
        }:
            raise G075Error("G075_INITIAL_RECONCILIATION_NOT_CLEAR")
        base = {
            "schema": "H11_V4_G075_SWITCH_CONTROL_CAPABILITY_V1",
            "generation_label": G075_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "reconciliation_artifact_digest": evidence.artifact_digest,
            "actual_post_authorized": False,
            "broker_post_authorized": False,
            "daily_authorization_required": False,
            "per_trade_confirmation_required": False,
            "status": "ENABLED",
        }
        _atomic_json(
            state_root / G075_RELEASE_CAPABILITY_FILE,
            {**base, "artifact_digest": _canonical_hash(base)},
        )
        _atomic_json(
            state_root / G075_SWITCH_CAPABILITY_FILE,
            {**base, "artifact_digest": _canonical_hash(base)},
        )
        arm_mutator()
        if arm_state_verifier() is not True:
            raise G075Error("G075_INITIAL_ARM_MUTATION_NOT_CONFIRMED")
        outcome = {
            "status": "PASSED",
            "generation_label": G075_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "broker_post_count": 0,
            "private_api_read_count": 0,
            "credential_read_count": 0,
        }
        _atomic_json(
            state_root / G075_INITIAL_TRANSACTION_OUTCOME_FILE,
            {**outcome, "artifact_digest": _canonical_hash(outcome)},
        )
        return "PASSED"
    except BaseException:
        # D-P2-2 (Safety P2-1): widen to BaseException so KeyboardInterrupt
        # during the activation transaction runs the same halt + outcome
        # write path as a normal exception.  Behaviour (halt latched,
        # outcome UNKNOWN recorded) is unchanged.
        engage_g075_halt(state_root=state_root, reason="G075_INITIAL_TRANSACTION_UNKNOWN")
        _atomic_json(
            state_root / G075_INITIAL_TRANSACTION_OUTCOME_FILE,
            {
                "status": "UNKNOWN",
                "generation_label": G075_GENERATION_LABEL,
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "broker_post_count": 0,
            },
        )
        raise


def run_g075_initial_atomic_activation_fake_only(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    reconciliation_runner: Callable[[], G075ReconciliationEvidence],
    now_utc: datetime,
) -> str:
    """Exercise exact transaction ordering with synthetic dependencies only."""

    mutated = False

    def mutate() -> None:
        nonlocal mutated
        mutated = True

    return run_g075_initial_atomic_activation(
        state_root=state_root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
        reconciliation_runner=reconciliation_runner,
        arm_mutator=mutate,
        arm_state_verifier=lambda: mutated,
        now_utc=now_utc,
    )


__all__ = [
    "G075Action",
    "G075ActionOutcome",
    "G075ActionScope",
    "G075ArmState",
    "G075EffectiveState",
    "G075EntryDispatcher",
    "G075EntryState",
    "G075Error",
    "G075ExitDispatcher",
    "G075ExitState",
    "G075FrozenStrategyEvaluator",
    "G075_GENERATION_LABEL",
    "G075ProcessLock",
    "G075RecoveryScope",
    "G075ReadOnlyReconciler",
    "G075ReconciliationEvidence",
    "G075ReconciliationState",
    "G075ResidentSupervisor",
    "G075SanitizedSnapshot",
    "G075StrategyDecision",
    "G075StrategyObservation",
    "G075StrategyObservationSource",
    "engage_g075_halt",
    "build_g075_recovery_scope",
    "load_g075_release_capability_digest",
    "load_g075_reconciliation",
    "require_g075_no_unresolved_halt",
    "run_g075_initial_atomic_activation",
    "run_g075_initial_atomic_activation_fake_only",
    "run_g075_reconciliation_cycle_once",
    "safe_g075_api_status",
    "verify_g075_review_artifacts",
    "verify_g075_scheduler_binding",
]
