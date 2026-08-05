"""G078 unknown-resolution read-back candidate (fake-only, v1.1 + corrective).

Same-generation resolution of an UNKNOWN write outcome via a generation-bound,
one-use read-back step.  The write itself remains one attempt per action; no
same-action retry or repost is ever performed.  The resolution reads
``latestExecutions``, ``openPositions`` and ``activeOrders`` at most once each,
classifies the outcome (fail-closed), and records opaque sanitized evidence
with canonical digests.  An unresolvable, ambiguous, partial, or timed-out
observation is terminal for the generation (persistent HALT).

G078 corrective resolution (2026-08-05, independent A/S/O review findings)
--------------------------------------------------------------------------
C1  Pre-start refusal is terminal when the underlying UNKNOWN can no longer be
    resolved: a start-window overrun (wall-clock and, when supplied,
    monotonic) and a budget-exhausted refusal each latch a persistent halt
    before raising (MEDIUM-1).
C2  The resolution budget is derived from the per-scope evidence files instead
    of a separate budget ledger, so evidence and budget cannot diverge across
    a crash (LOW-1) and a corrupt ledger cannot raise a raw ValueError
    (LOW-2) or project a negative count (INFO-1).
C3  The start window can additionally be enforced on the injected monotonic
    clock via ``unknown_observed_monotonic``, making the 15-second bound
    immune to wall-clock skew when the caller records the observation time on
    the same clock (LOW-3).
C4  The budget check runs under the flock process lock, so concurrent
    resolution processes cannot both pass a stale budget count.

v1.1 review resolution (2026-08-05)
-----------------------------------
H1  Resolution markers are bound to the action scope digest
    (``g078-resolution.{scope}.started.json`` / ``.evidence.json``) instead of
    a single generation-wide marker, with a per-generation budget of at most
    ``G078_MAX_RESOLUTIONS_PER_GENERATION`` resolutions (each scope at most
    once) and a minimum interval between read-back GETs
    (``G078_MIN_READ_INTERVAL_SECONDS``, max 4 reads/sec).
H2  Resolution must start within ``G078_RESOLUTION_START_WINDOW_SECONDS`` of
    the UNKNOWN observation and must complete within
    ``G078_RESOLUTION_COMPLETION_BUDGET_SECONDS`` of start.  The monotonic
    clock and sleep are injected for deterministic tests; overruns classify as
    UNRESOLVED (timed out) and halt.
M1  ``CONFIRMED_PARTIAL_FILL`` is a distinct state for an entry whose matched
    execution did not result in an exact-size owned position.  It is
    fail-closed TERMINAL for the generation: the fake-only step never cancels
    the unfilled remainder (broker write forbidden).  Cancelling the remainder
    is a separate operator-executed action with a fresh observation.
M2  Resolution semantics are action-kind-specific (see the design doc table):
    MARKET_ENTRY / POSITION_SPECIFIC_EXIT / EXACT_SIZE_OCO_PROTECTION /
    CANCEL_UNFILLED_REMAINDER / INITIAL_ACTIVATION.  Only the documented
    ``NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION`` cases are non-terminal.
M3  A non-blocking ``flock`` process lock (``g078-resolution.lock``) is held
    for the whole resolution so two processes cannot resolve concurrently.
L1  ``g078_resolution_status`` projects ``resolution_state`` independently of
    arm / release / effective / entry state; UI wiring is a later step.
L2  "Next scheduled cycle" means a later 30m cycle with a fresh M1 slot; the
    same M1 slot is never re-evaluated.

This module is fake-only: the read-back port must be a ``G078FakeOnlyCallable``
synthetic.  It never reads Keychain, calls a Private API, sends a notification,
mutates ARM, or touches broker transport.  Real execution of the read-back is a
separate, explicitly authorized release boundary.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

G078_GENERATION_LABEL = "H11_AUTO_30M_20260805_G078"

G078_RESOLUTION_PREFIX = "g078-resolution"
G078_RESOLUTION_STARTED_SUFFIX = ".started.json"
G078_RESOLUTION_EVIDENCE_SUFFIX = ".evidence.json"
G078_PROCESS_LOCK_FILE = "g078-resolution.lock"
G078_PERSISTENT_HALT_FILE = "g078-persistent-halt.json"

G078_RESOLUTION_EVIDENCE_SCHEMA = "H11_V4_G078_RESOLUTION_EVIDENCE_V1"
G078_RESOLUTION_STARTED_SCHEMA = "H11_V4_G078_RESOLUTION_STARTED_V1"
G078_PERSISTENT_HALT_SCHEMA = "H11_V4_G078_PERSISTENT_HALT_V1"
G078_RESOLUTION_STATUS_SCHEMA = "H11_V4_G078_RESOLUTION_STATUS_V1"

G078_MAX_RESOLUTIONS_PER_GENERATION = 3
G078_RESOLUTION_START_WINDOW_SECONDS = 15.0
G078_RESOLUTION_COMPLETION_BUDGET_SECONDS = 60.0
G078_MIN_READ_INTERVAL_SECONDS = 0.25

NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION = "NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION"
ACTION_CONFIRMED = "ACTION_CONFIRMED"
TERMINAL_FOR_GENERATION = "TERMINAL_FOR_GENERATION"

_DIGEST = r"^sha256:[0-9a-f]{64}$"
_SCOPE_TOKEN = r"^[0-9a-f]{64}$"


class G078Error(ValueError):
    """Safe-label-only G078 failure."""


class G078ResolutionState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"
    CONFIRMED_EXECUTED = "CONFIRMED_EXECUTED"
    CONFIRMED_NOT_EXECUTED = "CONFIRMED_NOT_EXECUTED"
    CONFIRMED_PARTIAL_FILL = "CONFIRMED_PARTIAL_FILL"
    UNRESOLVED = "UNRESOLVED"


class G078ReadBackSource(str, Enum):
    LATEST_EXECUTIONS = "latestExecutions"
    OPEN_POSITIONS = "openPositions"
    ACTIVE_ORDERS = "activeOrders"


class G078WriteActionKind(str, Enum):
    INITIAL_ACTIVATION = "INITIAL_ACTIVATION"
    MARKET_ENTRY = "MARKET_ENTRY"
    EXACT_SIZE_OCO_PROTECTION = "EXACT_SIZE_OCO_PROTECTION"
    CANCEL_UNFILLED_REMAINDER = "CANCEL_UNFILLED_REMAINDER"
    POSITION_SPECIFIC_EXIT = "POSITION_SPECIFIC_EXIT"


_G078_FAKE_MODULE_PREFIXES = (
    "app.services.h11_v4_g078",
    "app.tests.h11_auto.test_v4_g078",
)


def _g078_fake_module_allowed(value: object) -> bool:
    module = value if isinstance(value, str) else getattr(value, "__module__", "")
    return any(
        module == prefix
        or module.startswith(prefix + ".")
        or module.startswith(prefix + "_")
        for prefix in _G078_FAKE_MODULE_PREFIXES
    )


class G078FakeOnlyPort:
    """Sealed marker for dependencies that are synthetic by construction."""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not _g078_fake_module_allowed(cls):
            raise TypeError("G078_FAKE_ONLY_PORT_MODULE_REQUIRED")


def _g078_fake_port(value: object) -> bool:
    return isinstance(value, G078FakeOnlyPort) and _g078_fake_module_allowed(type(value))


@dataclass(frozen=True)
class G078FakeOnlyCallable:
    """Fake-only port wrapper; a real read-back client is rejected."""

    callback: Callable[..., object]

    def __post_init__(self) -> None:
        if not _g078_fake_module_allowed(self.callback):
            raise G078Error("G078_FAKE_ONLY_CALLABLE_MODULE_REQUIRED")

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self.callback(*args, **kwargs)


@dataclass(frozen=True)
class G078SanitizedRead:
    """Sanitized per-source read-back observation (no raw identifiers)."""

    source: G078ReadBackSource
    known: bool
    count: int = 0
    account_flat: bool = False
    ownership_exact: bool = False
    quantity_matches: bool = False
    protection_confirmed: bool = False
    active_orders_zero: bool = False
    matched_execution_seen: bool = False

    def __bool__(self) -> bool:
        return False


def _canonical_hash(payload: Mapping[str, object]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _require_digest(value: object, label: str) -> str:
    import re

    if (
        not isinstance(value, str)
        or len(value) != 71
        or re.fullmatch(_DIGEST, value) is None
    ):
        raise G078Error(f"{label}_INVALID")
    return value


def _scope_token(action_scope_digest: str) -> str:
    import re

    token = action_scope_digest[len("sha256:"):]
    if re.fullmatch(_SCOPE_TOKEN, token) is None:
        raise G078Error("G078_ACTION_SCOPE_TOKEN_INVALID")
    return token


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    temporary.replace(path)
    _fsync_parent(path)


def _fsync_parent(path: Path) -> None:
    try:
        descriptor = path.parent.open("rb")
    except OSError:
        return
    try:
        import os

        os.fsync(descriptor.fileno())
    except OSError:
        pass
    finally:
        descriptor.close()


def _exclusive_json(path: Path, payload: Mapping[str, object]) -> None:
    if path.exists() or path.is_symlink():
        raise G078Error("G078_EXCLUSIVE_ARTIFACT_EXISTS")
    try:
        descriptor = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise G078Error("G078_EXCLUSIVE_ARTIFACT_EXISTS") from None
    with descriptor:
        descriptor.write(
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    _fsync_parent(path)


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise G078Error(f"{label}_MISSING")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G078Error(f"{label}_INVALID") from error
    if not isinstance(payload, dict):
        raise G078Error(f"{label}_INVALID")
    return payload


def _resolution_started_path(state_root: Path, action_scope_digest: str) -> Path:
    token = _scope_token(action_scope_digest)
    return state_root / f"{G078_RESOLUTION_PREFIX}.{token}{G078_RESOLUTION_STARTED_SUFFIX}"


def _resolution_evidence_path(state_root: Path, action_scope_digest: str) -> Path:
    token = _scope_token(action_scope_digest)
    return state_root / f"{G078_RESOLUTION_PREFIX}.{token}{G078_RESOLUTION_EVIDENCE_SUFFIX}"


def _acquire_process_lock(path: Path):
    """Non-blocking flock; the lock is released on close or process exit."""
    descriptor = path.open("a+", encoding="utf-8")
    try:
        import fcntl

        fcntl.flock(descriptor.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError) as error:
        descriptor.close()
        raise G078Error("G078_PROCESS_LOCK_HELD") from error
    return descriptor


def engage_g078_halt(*, state_root: Path, reason: str) -> None:
    """Persist a terminal halt for the current generation (never cleared)."""
    payload = {
        "schema": G078_PERSISTENT_HALT_SCHEMA,
        "generation_label": G078_GENERATION_LABEL,
        "reason": reason,
        "status": "HALTED",
        "actual_post_authorized": False,
        "broker_post_authorized": False,
    }
    _atomic_json(state_root / G078_PERSISTENT_HALT_FILE, payload)


def _resolution_state_for_kind(
    *,
    action_kind: G078WriteActionKind,
    executions: G078SanitizedRead,
    positions: G078SanitizedRead,
    orders: G078SanitizedRead,
) -> G078ResolutionState:
    """Action-kind-specific read-back classification (M2, fail-closed)."""
    if not (executions.known and positions.known and orders.known):
        return G078ResolutionState.UNRESOLVED
    if action_kind is G078WriteActionKind.MARKET_ENTRY:
        executed = (
            executions.matched_execution_seen
            and positions.ownership_exact
            and positions.quantity_matches
            and not positions.account_flat
        )
        if executed:
            return G078ResolutionState.CONFIRMED_EXECUTED
        partial = (
            executions.matched_execution_seen
            and not positions.account_flat
            and not (positions.ownership_exact and positions.quantity_matches)
        )
        if partial:
            return G078ResolutionState.CONFIRMED_PARTIAL_FILL
        not_executed = (
            positions.account_flat
            and orders.active_orders_zero
            and not executions.matched_execution_seen
        )
        if not_executed:
            return G078ResolutionState.CONFIRMED_NOT_EXECUTED
        return G078ResolutionState.UNRESOLVED
    if action_kind is G078WriteActionKind.POSITION_SPECIFIC_EXIT:
        if positions.account_flat and orders.active_orders_zero:
            return G078ResolutionState.CONFIRMED_EXECUTED
        if not positions.account_flat and positions.ownership_exact:
            return G078ResolutionState.CONFIRMED_NOT_EXECUTED
        return G078ResolutionState.UNRESOLVED
    if action_kind is G078WriteActionKind.EXACT_SIZE_OCO_PROTECTION:
        if (
            positions.protection_confirmed
            and positions.ownership_exact
            and positions.quantity_matches
            and not positions.account_flat
        ):
            return G078ResolutionState.CONFIRMED_EXECUTED
        if positions.account_flat and orders.active_orders_zero:
            return G078ResolutionState.CONFIRMED_NOT_EXECUTED
        return G078ResolutionState.UNRESOLVED
    if action_kind is G078WriteActionKind.CANCEL_UNFILLED_REMAINDER:
        if orders.active_orders_zero:
            return G078ResolutionState.CONFIRMED_EXECUTED
        # Orders still active: the cancel did not take effect.  Per G013 no
        # further write is permitted while the unfilled remainder is pending,
        # so this is CONFIRMED_NOT_EXECUTED with a TERMINAL policy.
        return G078ResolutionState.CONFIRMED_NOT_EXECUTED
    # INITIAL_ACTIVATION: market read-back is insufficient evidence for an
    # activation outcome; UNKNOWN remains terminal (G075/G076 precedent).
    return G078ResolutionState.UNRESOLVED


def _resolution_policy(
    *, action_kind: G078WriteActionKind, state: G078ResolutionState
) -> str:
    if state is G078ResolutionState.CONFIRMED_EXECUTED:
        return ACTION_CONFIRMED
    if (
        state is G078ResolutionState.CONFIRMED_NOT_EXECUTED
        and action_kind
        in {
            G078WriteActionKind.MARKET_ENTRY,
            G078WriteActionKind.POSITION_SPECIFIC_EXIT,
            G078WriteActionKind.EXACT_SIZE_OCO_PROTECTION,
        }
    ):
        return NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION
    return TERMINAL_FOR_GENERATION


def _resolution_evidence_count(*, state_root: Path) -> int:
    """Completed resolutions = per-scope evidence files (crash-consistent).

    The evidence file is the single atomic write per resolution, so the budget
    cannot diverge from reality across a crash (LOW-1) and no separate ledger
    can be corrupted (LOW-2).  A resolution whose marker exists but whose
    evidence was never written never completed and does not consume budget.
    """
    return len(
        list(
            state_root.glob(
                f"{G078_RESOLUTION_PREFIX}.*{G078_RESOLUTION_EVIDENCE_SUFFIX}"
            )
        )
    )


def run_g078_unknown_resolution_once(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    action_scope_digest: str,
    action_kind: G078WriteActionKind,
    read_back_client: G078FakeOnlyCallable,
    unknown_observed_at_utc: datetime,
    now_utc: datetime,
    unknown_observed_monotonic: float | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Run the one-use unknown-resolution read-back step (fake-only ports).

    The per-scope started marker is created before any read.  Any post-start
    failure or unknown result is terminal for this generation and is never
    retried.  Pre-start refusals that leave the underlying UNKNOWN
    unresolvable (start-window overrun, budget exhausted) latch a persistent
    halt before raising (C1).  Caller-programming rejections (bad digest,
    non-fake client, existing scope marker, held process lock) raise without
    writing state and are the wiring step's responsibility to treat as
    terminal when an UNKNOWN write outcome exists.
    """
    _require_digest(generation_digest, "G078_GENERATION_DIGEST")
    _require_digest(reviewed_files_digest, "G078_REVIEWED_FILES_DIGEST")
    _require_digest(action_scope_digest, "G078_ACTION_SCOPE_DIGEST")
    if not isinstance(action_kind, G078WriteActionKind):
        raise G078Error("G078_ACTION_KIND_INVALID")
    if not isinstance(read_back_client, G078FakeOnlyCallable):
        raise G078Error("G078_FAKE_ONLY_READ_BACK_REQUIRED")
    if now_utc.tzinfo is None or unknown_observed_at_utc.tzinfo is None:
        raise G078Error("G078_RESOLUTION_TIME_INVALID")
    if unknown_observed_monotonic is not None and not isinstance(
        unknown_observed_monotonic, float
    ):
        raise G078Error("G078_RESOLUTION_MONOTONIC_INVALID")
    state_root.mkdir(parents=True, exist_ok=True)
    started = _resolution_started_path(state_root, action_scope_digest)
    if started.exists() or started.is_symlink():
        raise G078Error("G078_RESOLUTION_ALREADY_STARTED_NO_RETRY")
    started_seconds = (now_utc - unknown_observed_at_utc).total_seconds()
    started_monotonic_seconds = (
        monotonic() - unknown_observed_monotonic
        if unknown_observed_monotonic is not None
        else None
    )
    if (
        started_seconds > G078_RESOLUTION_START_WINDOW_SECONDS
        or (
            started_monotonic_seconds is not None
            and started_monotonic_seconds > G078_RESOLUTION_START_WINDOW_SECONDS
        )
    ):
        # The UNKNOWN can no longer be resolved inside the safety window: the
        # underlying outcome is terminal (C1).  Latch the halt before raising
        # so an unresolved UNKNOWN is never left without a terminal record.
        engage_g078_halt(
            state_root=state_root, reason="G078_RESOLUTION_START_WINDOW_EXCEEDED"
        )
        raise G078Error("G078_RESOLUTION_START_WINDOW_EXCEEDED")

    lock = _acquire_process_lock(state_root / G078_PROCESS_LOCK_FILE)
    try:
        if (
            _resolution_evidence_count(state_root=state_root)
            >= G078_MAX_RESOLUTIONS_PER_GENERATION
        ):
            # No budget remains, so this UNKNOWN is unresolvable: terminal (C1).
            engage_g078_halt(
                state_root=state_root,
                reason="G078_RESOLUTION_BUDGET_EXHAUSTED_TERMINAL",
            )
            raise G078Error("G078_RESOLUTION_BUDGET_EXCEEDED")
        _exclusive_json(
            started,
            {
                "schema": G078_RESOLUTION_STARTED_SCHEMA,
                "generation_label": G078_GENERATION_LABEL,
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "action_scope_digest": action_scope_digest,
                "action_kind": action_kind.value,
                "status": "STARTED",
            },
        )
        started_monotonic = monotonic()
        reads: dict[str, G078SanitizedRead] = {}
        reads_completed = 0
        timed_out = False
        last_read_monotonic: float | None = None
        for source in (
            G078ReadBackSource.LATEST_EXECUTIONS,
            G078ReadBackSource.OPEN_POSITIONS,
            G078ReadBackSource.ACTIVE_ORDERS,
        ):
            if monotonic() - started_monotonic > G078_RESOLUTION_COMPLETION_BUDGET_SECONDS:
                timed_out = True
                break
            if last_read_monotonic is not None:
                elapsed = monotonic() - last_read_monotonic
                if elapsed < G078_MIN_READ_INTERVAL_SECONDS:
                    sleep(G078_MIN_READ_INTERVAL_SECONDS - elapsed)
            result = read_back_client(source, now_utc)
            if not isinstance(result, G078SanitizedRead):
                raise G078Error("G078_READ_BACK_CONTRACT_INVALID")
            if result.source is not source:
                raise G078Error("G078_READ_BACK_SOURCE_MISMATCH")
            reads[source.value] = result
            reads_completed += 1
            last_read_monotonic = monotonic()
            if not result.known:
                break
        for source in (
            G078ReadBackSource.LATEST_EXECUTIONS,
            G078ReadBackSource.OPEN_POSITIONS,
            G078ReadBackSource.ACTIVE_ORDERS,
        ):
            if source.value not in reads:
                reads[source.value] = G078SanitizedRead(source=source, known=False, count=0)
        state = _resolution_state_for_kind(
            action_kind=action_kind,
            executions=reads[G078ReadBackSource.LATEST_EXECUTIONS.value],
            positions=reads[G078ReadBackSource.OPEN_POSITIONS.value],
            orders=reads[G078ReadBackSource.ACTIVE_ORDERS.value],
        )
        if timed_out:
            state = G078ResolutionState.UNRESOLVED
        policy = _resolution_policy(action_kind=action_kind, state=state)
        any_unknown = any(not read.known for read in reads.values())
        if state is G078ResolutionState.UNRESOLVED:
            if timed_out:
                halt_reason = "G078_RESOLUTION_TIMEOUT"
            elif any_unknown:
                halt_reason = "G078_READ_BACK_UNKNOWN"
            else:
                halt_reason = "G078_RESOLUTION_AMBIGUOUS"
        elif state is G078ResolutionState.CONFIRMED_PARTIAL_FILL:
            halt_reason = "G078_PARTIAL_FILL_TERMINAL"
        elif policy is TERMINAL_FOR_GENERATION:
            halt_reason = "G078_RESOLUTION_TERMINAL"
        else:
            halt_reason = None
        halted = halt_reason is not None
        base = {
            "schema": G078_RESOLUTION_EVIDENCE_SCHEMA,
            "generation_label": G078_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "action_scope_digest": action_scope_digest,
            "action_kind": action_kind.value,
            "status": state.value,
            "resolution_policy": policy,
            "partial_fill": state is G078ResolutionState.CONFIRMED_PARTIAL_FILL,
            "timed_out": timed_out,
            "reads_completed": reads_completed,
            "latest_executions_count": reads[
                G078ReadBackSource.LATEST_EXECUTIONS.value
            ].count,
            "open_positions_count": reads[G078ReadBackSource.OPEN_POSITIONS.value].count,
            "active_orders_count": reads[G078ReadBackSource.ACTIVE_ORDERS.value].count,
            "matched_execution_seen": reads[
                G078ReadBackSource.LATEST_EXECUTIONS.value
            ].matched_execution_seen,
            "account_flat": reads[G078ReadBackSource.OPEN_POSITIONS.value].account_flat,
            "ownership_exact": reads[
                G078ReadBackSource.OPEN_POSITIONS.value
            ].ownership_exact,
            "quantity_matches": reads[
                G078ReadBackSource.OPEN_POSITIONS.value
            ].quantity_matches,
            "protection_confirmed": reads[
                G078ReadBackSource.OPEN_POSITIONS.value
            ].protection_confirmed,
            "active_orders_zero": reads[
                G078ReadBackSource.ACTIVE_ORDERS.value
            ].active_orders_zero,
            "resolved_at_utc": now_utc.astimezone(UTC).isoformat(),
            "retry_attempted": False,
            "repost_attempted": False,
            "actual_post_authorized": False,
            "broker_post_authorized": False,
            "entry_authorized": False,
            "halt_reason": halt_reason,
        }
        evidence = {**base, "artifact_digest": _canonical_hash(base)}
        # The evidence file is the single atomic budget record (C2): the
        # per-generation budget is the count of per-scope evidence files.
        _atomic_json(
            _resolution_evidence_path(state_root, action_scope_digest), evidence
        )
        if halted:
            engage_g078_halt(
                state_root=state_root, reason=halt_reason or "G078_RESOLUTION_UNKNOWN"
            )
        return state.value
    except G078Error:
        # Post-start failures are terminal for the generation: keep the
        # no-retry marker and latch a persistent halt before re-raising.
        if started.exists() and not (state_root / G078_PERSISTENT_HALT_FILE).exists():
            try:
                engage_g078_halt(
                    state_root=state_root, reason="G078_RESOLUTION_INTERNAL_FAILURE"
                )
            except G078Error:
                pass
        raise
    finally:
        try:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        except (OSError, ValueError):
            pass
        lock.close()


def load_g078_resolution_evidence(
    *, state_root: Path, action_scope_digest: str
) -> dict[str, object]:
    """Load and schema-validate the one-use resolution evidence for a scope."""
    payload = _read_json(
        _resolution_evidence_path(state_root, action_scope_digest),
        "G078_RESOLUTION_EVIDENCE",
    )
    if payload.get("schema") != G078_RESOLUTION_EVIDENCE_SCHEMA:
        raise G078Error("G078_RESOLUTION_EVIDENCE_SCHEMA_INVALID")
    if payload.get("generation_label") != G078_GENERATION_LABEL:
        raise G078Error("G078_RESOLUTION_EVIDENCE_GENERATION_MISMATCH")
    if payload.get("action_scope_digest") != action_scope_digest:
        raise G078Error("G078_RESOLUTION_EVIDENCE_SCOPE_MISMATCH")
    status = payload.get("status")
    if status not in {
        G078ResolutionState.CONFIRMED_EXECUTED.value,
        G078ResolutionState.CONFIRMED_NOT_EXECUTED.value,
        G078ResolutionState.CONFIRMED_PARTIAL_FILL.value,
        G078ResolutionState.UNRESOLVED.value,
    }:
        raise G078Error("G078_RESOLUTION_EVIDENCE_STATUS_INVALID")
    artifact = payload.get("artifact_digest")
    if not isinstance(artifact, str) or not artifact.startswith("sha256:"):
        raise G078Error("G078_RESOLUTION_EVIDENCE_DIGEST_INVALID")
    return payload


def g078_resolution_status(*, state_root: Path) -> dict[str, object]:
    """Inert read-only projection for the operator UI (no external reads).

    ``resolution_state`` is projected independently of arm / release /
    effective / entry state (L1); it never feeds an authorization value.
    """
    halted = (state_root / G078_PERSISTENT_HALT_FILE).is_file()
    resolutions: list[dict[str, object]] = []
    scope_tokens = sorted(
        path.name[len(G078_RESOLUTION_PREFIX) + 1 : -len(G078_RESOLUTION_EVIDENCE_SUFFIX)]
        for path in state_root.glob(
            f"{G078_RESOLUTION_PREFIX}.*{G078_RESOLUTION_EVIDENCE_SUFFIX}"
        )
        if path.is_file() and not path.is_symlink()
    )
    for token in scope_tokens:
        evidence_path = state_root / (
            f"{G078_RESOLUTION_PREFIX}.{token}{G078_RESOLUTION_EVIDENCE_SUFFIX}"
        )
        try:
            payload = _read_json(evidence_path, "G078_RESOLUTION_EVIDENCE")
            valid = (
                payload.get("schema") == G078_RESOLUTION_EVIDENCE_SCHEMA
                and payload.get("generation_label") == G078_GENERATION_LABEL
                and payload.get("status")
                in {
                    G078ResolutionState.CONFIRMED_EXECUTED.value,
                    G078ResolutionState.CONFIRMED_NOT_EXECUTED.value,
                    G078ResolutionState.CONFIRMED_PARTIAL_FILL.value,
                    G078ResolutionState.UNRESOLVED.value,
                }
            )
            if not valid:
                raise G078Error("G078_RESOLUTION_EVIDENCE_STATUS_INVALID")
            resolutions.append(
                {
                    "scope_token": token,
                    "action_scope_digest": payload.get("action_scope_digest"),
                    "action_kind": payload.get("action_kind"),
                    "status": payload.get("status"),
                    "resolution_policy": payload.get("resolution_policy"),
                    "halt_reason": payload.get("halt_reason"),
                }
            )
        except G078Error:
            resolutions.append(
                {
                    "scope_token": token,
                    "status": G078ResolutionState.UNRESOLVED.value,
                    "evidence_invalid": True,
                }
            )
    if not scope_tokens:
        aggregate = G078ResolutionState.NOT_REQUIRED.value
    elif any(
        item.get("status") in {
            G078ResolutionState.UNRESOLVED.value,
            G078ResolutionState.CONFIRMED_PARTIAL_FILL.value,
        }
        or item.get("evidence_invalid") is True
        for item in resolutions
    ):
        aggregate = G078ResolutionState.UNRESOLVED.value
    else:
        aggregate = G078ResolutionState.CONFIRMED_EXECUTED.value
    return {
        "schema": G078_RESOLUTION_STATUS_SCHEMA,
        "generation_label": G078_GENERATION_LABEL,
        "resolution_state": aggregate,
        "resolutions_used": len(scope_tokens),
        "resolutions_limit": G078_MAX_RESOLUTIONS_PER_GENERATION,
        "persistent_halt": halted,
        "evidence_present": bool(scope_tokens),
        "resolutions": resolutions,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
    }


__all__ = [
    "ACTION_CONFIRMED",
    "G078Error",
    "G078FakeOnlyCallable",
    "G078FakeOnlyPort",
    "G078ReadBackSource",
    "G078ResolutionState",
    "G078SanitizedRead",
    "G078WriteActionKind",
    "G078_GENERATION_LABEL",
    "G078_MAX_RESOLUTIONS_PER_GENERATION",
    "G078_MIN_READ_INTERVAL_SECONDS",
    "G078_PERSISTENT_HALT_FILE",
    "G078_PROCESS_LOCK_FILE",
    "G078_RESOLUTION_COMPLETION_BUDGET_SECONDS",
    "G078_RESOLUTION_EVIDENCE_SUFFIX",
    "G078_RESOLUTION_START_WINDOW_SECONDS",
    "G078_RESOLUTION_STARTED_SUFFIX",
    "NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION",
    "TERMINAL_FOR_GENERATION",
    "engage_g078_halt",
    "g078_resolution_status",
    "load_g078_resolution_evidence",
    "run_g078_unknown_resolution_once",
]
