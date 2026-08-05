"""G077 unknown-resolution read-back candidate (fake-only, v1.1).

Same-generation resolution of an UNKNOWN write outcome via a generation-bound,
one-use read-back step.  The write itself remains one attempt per action; no
same-action retry or repost is ever performed.  The resolution reads
``latestExecutions``, ``openPositions`` and ``activeOrders`` at most once each,
classifies the outcome (fail-closed), and records opaque sanitized evidence
with canonical digests.  An unresolvable, ambiguous, partial, or timed-out
observation is terminal for the generation (persistent HALT).

v1.1 review resolution (2026-08-05)
-----------------------------------
H1  Resolution markers are bound to the action scope digest
    (``g077-resolution.{scope}.started.json`` / ``.evidence.json``) instead of
    a single generation-wide marker, with a per-generation budget of at most
    ``G077_MAX_RESOLUTIONS_PER_GENERATION`` resolutions (each scope at most
    once) and a minimum interval between read-back GETs
    (``G077_MIN_READ_INTERVAL_SECONDS``, max 4 reads/sec).
H2  Resolution must start within ``G077_RESOLUTION_START_WINDOW_SECONDS`` of
    the UNKNOWN observation and must complete within
    ``G077_RESOLUTION_COMPLETION_BUDGET_SECONDS`` of start.  The monotonic
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
M3  A non-blocking ``flock`` process lock (``g077-resolution.lock``) is held
    for the whole resolution so two processes cannot resolve concurrently.
L1  ``g077_resolution_status`` projects ``resolution_state`` independently of
    arm / release / effective / entry state; UI wiring is a later step.
L2  "Next scheduled cycle" means a later 30m cycle with a fresh M1 slot; the
    same M1 slot is never re-evaluated.

This module is fake-only: the read-back port must be a ``G077FakeOnlyCallable``
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

G077_GENERATION_LABEL = "H11_AUTO_30M_20260805_G077"

G077_RESOLUTION_PREFIX = "g077-resolution"
G077_RESOLUTION_STARTED_SUFFIX = ".started.json"
G077_RESOLUTION_EVIDENCE_SUFFIX = ".evidence.json"
G077_RESOLUTION_BUDGET_FILE = "g077-resolution.budget.json"
G077_PROCESS_LOCK_FILE = "g077-resolution.lock"
G077_PERSISTENT_HALT_FILE = "g077-persistent-halt.json"

G077_RESOLUTION_EVIDENCE_SCHEMA = "H11_V4_G077_RESOLUTION_EVIDENCE_V1"
G077_RESOLUTION_STARTED_SCHEMA = "H11_V4_G077_RESOLUTION_STARTED_V1"
G077_RESOLUTION_BUDGET_SCHEMA = "H11_V4_G077_RESOLUTION_BUDGET_V1"
G077_PERSISTENT_HALT_SCHEMA = "H11_V4_G077_PERSISTENT_HALT_V1"
G077_RESOLUTION_STATUS_SCHEMA = "H11_V4_G077_RESOLUTION_STATUS_V1"

G077_MAX_RESOLUTIONS_PER_GENERATION = 3
G077_RESOLUTION_START_WINDOW_SECONDS = 15.0
G077_RESOLUTION_COMPLETION_BUDGET_SECONDS = 60.0
G077_MIN_READ_INTERVAL_SECONDS = 0.25

NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION = "NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION"
ACTION_CONFIRMED = "ACTION_CONFIRMED"
TERMINAL_FOR_GENERATION = "TERMINAL_FOR_GENERATION"

_DIGEST = r"^sha256:[0-9a-f]{64}$"
_SCOPE_TOKEN = r"^[0-9a-f]{64}$"


class G077Error(ValueError):
    """Safe-label-only G077 failure."""


class G077ResolutionState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"
    CONFIRMED_EXECUTED = "CONFIRMED_EXECUTED"
    CONFIRMED_NOT_EXECUTED = "CONFIRMED_NOT_EXECUTED"
    CONFIRMED_PARTIAL_FILL = "CONFIRMED_PARTIAL_FILL"
    UNRESOLVED = "UNRESOLVED"


class G077ReadBackSource(str, Enum):
    LATEST_EXECUTIONS = "latestExecutions"
    OPEN_POSITIONS = "openPositions"
    ACTIVE_ORDERS = "activeOrders"


class G077WriteActionKind(str, Enum):
    INITIAL_ACTIVATION = "INITIAL_ACTIVATION"
    MARKET_ENTRY = "MARKET_ENTRY"
    EXACT_SIZE_OCO_PROTECTION = "EXACT_SIZE_OCO_PROTECTION"
    CANCEL_UNFILLED_REMAINDER = "CANCEL_UNFILLED_REMAINDER"
    POSITION_SPECIFIC_EXIT = "POSITION_SPECIFIC_EXIT"


_G077_FAKE_MODULE_PREFIXES = (
    "app.services.h11_v4_g077",
    "app.tests.h11_auto.test_v4_g077",
)


def _g077_fake_module_allowed(value: object) -> bool:
    module = value if isinstance(value, str) else getattr(value, "__module__", "")
    return any(
        module == prefix
        or module.startswith(prefix + ".")
        or module.startswith(prefix + "_")
        for prefix in _G077_FAKE_MODULE_PREFIXES
    )


class G077FakeOnlyPort:
    """Sealed marker for dependencies that are synthetic by construction."""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not _g077_fake_module_allowed(cls):
            raise TypeError("G077_FAKE_ONLY_PORT_MODULE_REQUIRED")


def _g077_fake_port(value: object) -> bool:
    return isinstance(value, G077FakeOnlyPort) and _g077_fake_module_allowed(type(value))


@dataclass(frozen=True)
class G077FakeOnlyCallable:
    """Fake-only port wrapper; a real read-back client is rejected."""

    callback: Callable[..., object]

    def __post_init__(self) -> None:
        if not _g077_fake_module_allowed(self.callback):
            raise G077Error("G077_FAKE_ONLY_CALLABLE_MODULE_REQUIRED")

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self.callback(*args, **kwargs)


@dataclass(frozen=True)
class G077SanitizedRead:
    """Sanitized per-source read-back observation (no raw identifiers)."""

    source: G077ReadBackSource
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
        raise G077Error(f"{label}_INVALID")
    return value


def _scope_token(action_scope_digest: str) -> str:
    import re

    token = action_scope_digest[len("sha256:"):]
    if re.fullmatch(_SCOPE_TOKEN, token) is None:
        raise G077Error("G077_ACTION_SCOPE_TOKEN_INVALID")
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
        raise G077Error("G077_EXCLUSIVE_ARTIFACT_EXISTS")
    try:
        descriptor = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise G077Error("G077_EXCLUSIVE_ARTIFACT_EXISTS") from None
    with descriptor:
        descriptor.write(
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    _fsync_parent(path)


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise G077Error(f"{label}_MISSING")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G077Error(f"{label}_INVALID") from error
    if not isinstance(payload, dict):
        raise G077Error(f"{label}_INVALID")
    return payload


def _resolution_started_path(state_root: Path, action_scope_digest: str) -> Path:
    token = _scope_token(action_scope_digest)
    return state_root / f"{G077_RESOLUTION_PREFIX}.{token}{G077_RESOLUTION_STARTED_SUFFIX}"


def _resolution_evidence_path(state_root: Path, action_scope_digest: str) -> Path:
    token = _scope_token(action_scope_digest)
    return state_root / f"{G077_RESOLUTION_PREFIX}.{token}{G077_RESOLUTION_EVIDENCE_SUFFIX}"


def _acquire_process_lock(path: Path):
    """Non-blocking flock; the lock is released on close or process exit."""
    descriptor = path.open("a+", encoding="utf-8")
    try:
        import fcntl

        fcntl.flock(descriptor.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError) as error:
        descriptor.close()
        raise G077Error("G077_PROCESS_LOCK_HELD") from error
    return descriptor


def engage_g077_halt(*, state_root: Path, reason: str) -> None:
    """Persist a terminal halt for the current generation (never cleared)."""
    payload = {
        "schema": G077_PERSISTENT_HALT_SCHEMA,
        "generation_label": G077_GENERATION_LABEL,
        "reason": reason,
        "status": "HALTED",
        "actual_post_authorized": False,
        "broker_post_authorized": False,
    }
    _atomic_json(state_root / G077_PERSISTENT_HALT_FILE, payload)


def _resolution_state_for_kind(
    *,
    action_kind: G077WriteActionKind,
    executions: G077SanitizedRead,
    positions: G077SanitizedRead,
    orders: G077SanitizedRead,
) -> G077ResolutionState:
    """Action-kind-specific read-back classification (M2, fail-closed)."""
    if not (executions.known and positions.known and orders.known):
        return G077ResolutionState.UNRESOLVED
    if action_kind is G077WriteActionKind.MARKET_ENTRY:
        executed = (
            executions.matched_execution_seen
            and positions.ownership_exact
            and positions.quantity_matches
            and not positions.account_flat
        )
        if executed:
            return G077ResolutionState.CONFIRMED_EXECUTED
        partial = (
            executions.matched_execution_seen
            and not positions.account_flat
            and not (positions.ownership_exact and positions.quantity_matches)
        )
        if partial:
            return G077ResolutionState.CONFIRMED_PARTIAL_FILL
        not_executed = (
            positions.account_flat
            and orders.active_orders_zero
            and not executions.matched_execution_seen
        )
        if not_executed:
            return G077ResolutionState.CONFIRMED_NOT_EXECUTED
        return G077ResolutionState.UNRESOLVED
    if action_kind is G077WriteActionKind.POSITION_SPECIFIC_EXIT:
        if positions.account_flat and orders.active_orders_zero:
            return G077ResolutionState.CONFIRMED_EXECUTED
        if not positions.account_flat and positions.ownership_exact:
            return G077ResolutionState.CONFIRMED_NOT_EXECUTED
        return G077ResolutionState.UNRESOLVED
    if action_kind is G077WriteActionKind.EXACT_SIZE_OCO_PROTECTION:
        if (
            positions.protection_confirmed
            and positions.ownership_exact
            and positions.quantity_matches
            and not positions.account_flat
        ):
            return G077ResolutionState.CONFIRMED_EXECUTED
        if positions.account_flat and orders.active_orders_zero:
            return G077ResolutionState.CONFIRMED_NOT_EXECUTED
        return G077ResolutionState.UNRESOLVED
    if action_kind is G077WriteActionKind.CANCEL_UNFILLED_REMAINDER:
        if orders.active_orders_zero:
            return G077ResolutionState.CONFIRMED_EXECUTED
        # Orders still active: the cancel did not take effect.  Per G013 no
        # further write is permitted while the unfilled remainder is pending,
        # so this is CONFIRMED_NOT_EXECUTED with a TERMINAL policy.
        return G077ResolutionState.CONFIRMED_NOT_EXECUTED
    # INITIAL_ACTIVATION: market read-back is insufficient evidence for an
    # activation outcome; UNKNOWN remains terminal (G075/G076 precedent).
    return G077ResolutionState.UNRESOLVED


def _resolution_policy(
    *, action_kind: G077WriteActionKind, state: G077ResolutionState
) -> str:
    if state is G077ResolutionState.CONFIRMED_EXECUTED:
        return ACTION_CONFIRMED
    if (
        state is G077ResolutionState.CONFIRMED_NOT_EXECUTED
        and action_kind
        in {
            G077WriteActionKind.MARKET_ENTRY,
            G077WriteActionKind.POSITION_SPECIFIC_EXIT,
            G077WriteActionKind.EXACT_SIZE_OCO_PROTECTION,
        }
    ):
        return NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION
    return TERMINAL_FOR_GENERATION


def _load_budget(*, state_root: Path, generation_digest: str) -> dict[str, object]:
    path = state_root / G077_RESOLUTION_BUDGET_FILE
    if not path.is_file():
        return {
            "schema": G077_RESOLUTION_BUDGET_SCHEMA,
            "generation_label": G077_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "resolutions_limit": G077_MAX_RESOLUTIONS_PER_GENERATION,
            "resolutions_used": 0,
            "resolved_scopes": [],
        }
    payload = _read_json(path, "G077_RESOLUTION_BUDGET")
    if payload.get("schema") != G077_RESOLUTION_BUDGET_SCHEMA:
        raise G077Error("G077_RESOLUTION_BUDGET_SCHEMA_INVALID")
    if payload.get("generation_label") != G077_GENERATION_LABEL:
        raise G077Error("G077_RESOLUTION_BUDGET_GENERATION_MISMATCH")
    if payload.get("generation_digest") != generation_digest:
        raise G077Error("G077_RESOLUTION_BUDGET_GENERATION_MISMATCH")
    return payload


def run_g077_unknown_resolution_once(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    action_scope_digest: str,
    action_kind: G077WriteActionKind,
    read_back_client: G077FakeOnlyCallable,
    unknown_observed_at_utc: datetime,
    now_utc: datetime,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Run the one-use unknown-resolution read-back step (fake-only ports).

    The per-scope started marker is created before any read.  Any post-start
    failure or unknown result is terminal for this generation and is never
    retried.  Pre-start rejections (bad digest, non-fake client, budget
    exhausted, start window exceeded, existing scope marker, held process
    lock) raise without writing any state.
    """
    _require_digest(generation_digest, "G077_GENERATION_DIGEST")
    _require_digest(reviewed_files_digest, "G077_REVIEWED_FILES_DIGEST")
    _require_digest(action_scope_digest, "G077_ACTION_SCOPE_DIGEST")
    if not isinstance(action_kind, G077WriteActionKind):
        raise G077Error("G077_ACTION_KIND_INVALID")
    if not isinstance(read_back_client, G077FakeOnlyCallable):
        raise G077Error("G077_FAKE_ONLY_READ_BACK_REQUIRED")
    if now_utc.tzinfo is None or unknown_observed_at_utc.tzinfo is None:
        raise G077Error("G077_RESOLUTION_TIME_INVALID")
    scope_token = _scope_token(action_scope_digest)
    state_root.mkdir(parents=True, exist_ok=True)
    started = _resolution_started_path(state_root, action_scope_digest)
    if started.exists() or started.is_symlink():
        raise G077Error("G077_RESOLUTION_ALREADY_STARTED_NO_RETRY")
    started_seconds = (now_utc - unknown_observed_at_utc).total_seconds()
    if started_seconds > G077_RESOLUTION_START_WINDOW_SECONDS:
        raise G077Error("G077_RESOLUTION_START_WINDOW_EXCEEDED")
    budget = _load_budget(state_root=state_root, generation_digest=generation_digest)
    resolutions_used = int(budget["resolutions_used"])
    if resolutions_used >= G077_MAX_RESOLUTIONS_PER_GENERATION:
        raise G077Error("G077_RESOLUTION_BUDGET_EXCEEDED")

    lock = _acquire_process_lock(state_root / G077_PROCESS_LOCK_FILE)
    try:
        _exclusive_json(
            started,
            {
                "schema": G077_RESOLUTION_STARTED_SCHEMA,
                "generation_label": G077_GENERATION_LABEL,
                "generation_digest": generation_digest,
                "reviewed_files_digest": reviewed_files_digest,
                "action_scope_digest": action_scope_digest,
                "action_kind": action_kind.value,
                "status": "STARTED",
            },
        )
        started_monotonic = monotonic()
        reads: dict[str, G077SanitizedRead] = {}
        reads_completed = 0
        timed_out = False
        last_read_monotonic: float | None = None
        for source in (
            G077ReadBackSource.LATEST_EXECUTIONS,
            G077ReadBackSource.OPEN_POSITIONS,
            G077ReadBackSource.ACTIVE_ORDERS,
        ):
            if monotonic() - started_monotonic > G077_RESOLUTION_COMPLETION_BUDGET_SECONDS:
                timed_out = True
                break
            if last_read_monotonic is not None:
                elapsed = monotonic() - last_read_monotonic
                if elapsed < G077_MIN_READ_INTERVAL_SECONDS:
                    sleep(G077_MIN_READ_INTERVAL_SECONDS - elapsed)
            result = read_back_client(source, now_utc)
            if not isinstance(result, G077SanitizedRead):
                raise G077Error("G077_READ_BACK_CONTRACT_INVALID")
            if result.source is not source:
                raise G077Error("G077_READ_BACK_SOURCE_MISMATCH")
            reads[source.value] = result
            reads_completed += 1
            last_read_monotonic = monotonic()
            if not result.known:
                break
        for source in (
            G077ReadBackSource.LATEST_EXECUTIONS,
            G077ReadBackSource.OPEN_POSITIONS,
            G077ReadBackSource.ACTIVE_ORDERS,
        ):
            if source.value not in reads:
                reads[source.value] = G077SanitizedRead(source=source, known=False, count=0)
        state = _resolution_state_for_kind(
            action_kind=action_kind,
            executions=reads[G077ReadBackSource.LATEST_EXECUTIONS.value],
            positions=reads[G077ReadBackSource.OPEN_POSITIONS.value],
            orders=reads[G077ReadBackSource.ACTIVE_ORDERS.value],
        )
        if timed_out:
            state = G077ResolutionState.UNRESOLVED
        policy = _resolution_policy(action_kind=action_kind, state=state)
        any_unknown = any(not read.known for read in reads.values())
        if state is G077ResolutionState.UNRESOLVED:
            if timed_out:
                halt_reason = "G077_RESOLUTION_TIMEOUT"
            elif any_unknown:
                halt_reason = "G077_READ_BACK_UNKNOWN"
            else:
                halt_reason = "G077_RESOLUTION_AMBIGUOUS"
        elif state is G077ResolutionState.CONFIRMED_PARTIAL_FILL:
            halt_reason = "G077_PARTIAL_FILL_TERMINAL"
        elif policy is TERMINAL_FOR_GENERATION:
            halt_reason = "G077_RESOLUTION_TERMINAL"
        else:
            halt_reason = None
        halted = halt_reason is not None
        base = {
            "schema": G077_RESOLUTION_EVIDENCE_SCHEMA,
            "generation_label": G077_GENERATION_LABEL,
            "generation_digest": generation_digest,
            "reviewed_files_digest": reviewed_files_digest,
            "action_scope_digest": action_scope_digest,
            "action_kind": action_kind.value,
            "status": state.value,
            "resolution_policy": policy,
            "partial_fill": state is G077ResolutionState.CONFIRMED_PARTIAL_FILL,
            "timed_out": timed_out,
            "reads_completed": reads_completed,
            "latest_executions_count": reads[
                G077ReadBackSource.LATEST_EXECUTIONS.value
            ].count,
            "open_positions_count": reads[G077ReadBackSource.OPEN_POSITIONS.value].count,
            "active_orders_count": reads[G077ReadBackSource.ACTIVE_ORDERS.value].count,
            "matched_execution_seen": reads[
                G077ReadBackSource.LATEST_EXECUTIONS.value
            ].matched_execution_seen,
            "account_flat": reads[G077ReadBackSource.OPEN_POSITIONS.value].account_flat,
            "ownership_exact": reads[
                G077ReadBackSource.OPEN_POSITIONS.value
            ].ownership_exact,
            "quantity_matches": reads[
                G077ReadBackSource.OPEN_POSITIONS.value
            ].quantity_matches,
            "protection_confirmed": reads[
                G077ReadBackSource.OPEN_POSITIONS.value
            ].protection_confirmed,
            "active_orders_zero": reads[
                G077ReadBackSource.ACTIVE_ORDERS.value
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
        _atomic_json(
            _resolution_evidence_path(state_root, action_scope_digest), evidence
        )
        resolved_scopes = list(budget["resolved_scopes"])
        resolved_scopes.append(scope_token)
        _atomic_json(
            state_root / G077_RESOLUTION_BUDGET_FILE,
            {
                "schema": G077_RESOLUTION_BUDGET_SCHEMA,
                "generation_label": G077_GENERATION_LABEL,
                "generation_digest": generation_digest,
                "resolutions_limit": G077_MAX_RESOLUTIONS_PER_GENERATION,
                "resolutions_used": resolutions_used + 1,
                "resolved_scopes": resolved_scopes,
            },
        )
        if halted:
            engage_g077_halt(
                state_root=state_root, reason=halt_reason or "G077_RESOLUTION_UNKNOWN"
            )
        return state.value
    except G077Error:
        # Post-start failures are terminal for the generation: keep the
        # no-retry marker and latch a persistent halt before re-raising.
        if started.exists() and not (state_root / G077_PERSISTENT_HALT_FILE).exists():
            try:
                engage_g077_halt(
                    state_root=state_root, reason="G077_RESOLUTION_INTERNAL_FAILURE"
                )
            except G077Error:
                pass
        raise
    finally:
        try:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        except (OSError, ValueError):
            pass
        lock.close()


def load_g077_resolution_evidence(
    *, state_root: Path, action_scope_digest: str
) -> dict[str, object]:
    """Load and schema-validate the one-use resolution evidence for a scope."""
    payload = _read_json(
        _resolution_evidence_path(state_root, action_scope_digest),
        "G077_RESOLUTION_EVIDENCE",
    )
    if payload.get("schema") != G077_RESOLUTION_EVIDENCE_SCHEMA:
        raise G077Error("G077_RESOLUTION_EVIDENCE_SCHEMA_INVALID")
    if payload.get("generation_label") != G077_GENERATION_LABEL:
        raise G077Error("G077_RESOLUTION_EVIDENCE_GENERATION_MISMATCH")
    if payload.get("action_scope_digest") != action_scope_digest:
        raise G077Error("G077_RESOLUTION_EVIDENCE_SCOPE_MISMATCH")
    status = payload.get("status")
    if status not in {
        G077ResolutionState.CONFIRMED_EXECUTED.value,
        G077ResolutionState.CONFIRMED_NOT_EXECUTED.value,
        G077ResolutionState.CONFIRMED_PARTIAL_FILL.value,
        G077ResolutionState.UNRESOLVED.value,
    }:
        raise G077Error("G077_RESOLUTION_EVIDENCE_STATUS_INVALID")
    artifact = payload.get("artifact_digest")
    if not isinstance(artifact, str) or not artifact.startswith("sha256:"):
        raise G077Error("G077_RESOLUTION_EVIDENCE_DIGEST_INVALID")
    return payload


def g077_resolution_status(*, state_root: Path) -> dict[str, object]:
    """Inert read-only projection for the operator UI (no external reads).

    ``resolution_state`` is projected independently of arm / release /
    effective / entry state (L1); it never feeds an authorization value.
    """
    halted = (state_root / G077_PERSISTENT_HALT_FILE).is_file()
    budget_path = state_root / G077_RESOLUTION_BUDGET_FILE
    resolutions: list[dict[str, object]] = []
    resolutions_used = 0
    if budget_path.is_file():
        try:
            budget = _read_json(budget_path, "G077_RESOLUTION_BUDGET")
            resolutions_used = int(budget.get("resolutions_used", 0))
        except G077Error:
            resolutions_used = -1
    scope_tokens = sorted(
        path.name[len(G077_RESOLUTION_PREFIX) + 1 : -len(G077_RESOLUTION_EVIDENCE_SUFFIX)]
        for path in state_root.glob(
            f"{G077_RESOLUTION_PREFIX}.*{G077_RESOLUTION_EVIDENCE_SUFFIX}"
        )
        if path.is_file() and not path.is_symlink()
    )
    for token in scope_tokens:
        evidence_path = state_root / (
            f"{G077_RESOLUTION_PREFIX}.{token}{G077_RESOLUTION_EVIDENCE_SUFFIX}"
        )
        try:
            payload = _read_json(evidence_path, "G077_RESOLUTION_EVIDENCE")
            valid = (
                payload.get("schema") == G077_RESOLUTION_EVIDENCE_SCHEMA
                and payload.get("generation_label") == G077_GENERATION_LABEL
                and payload.get("status")
                in {
                    G077ResolutionState.CONFIRMED_EXECUTED.value,
                    G077ResolutionState.CONFIRMED_NOT_EXECUTED.value,
                    G077ResolutionState.CONFIRMED_PARTIAL_FILL.value,
                    G077ResolutionState.UNRESOLVED.value,
                }
            )
            if not valid:
                raise G077Error("G077_RESOLUTION_EVIDENCE_STATUS_INVALID")
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
        except G077Error:
            resolutions.append(
                {
                    "scope_token": token,
                    "status": G077ResolutionState.UNRESOLVED.value,
                    "evidence_invalid": True,
                }
            )
    if not scope_tokens:
        aggregate = G077ResolutionState.NOT_REQUIRED.value
    elif any(
        item.get("status") in {
            G077ResolutionState.UNRESOLVED.value,
            G077ResolutionState.CONFIRMED_PARTIAL_FILL.value,
        }
        or item.get("evidence_invalid") is True
        for item in resolutions
    ):
        aggregate = G077ResolutionState.UNRESOLVED.value
    else:
        aggregate = G077ResolutionState.CONFIRMED_EXECUTED.value
    return {
        "schema": G077_RESOLUTION_STATUS_SCHEMA,
        "generation_label": G077_GENERATION_LABEL,
        "resolution_state": aggregate,
        "resolutions_used": resolutions_used,
        "resolutions_limit": G077_MAX_RESOLUTIONS_PER_GENERATION,
        "persistent_halt": halted,
        "evidence_present": bool(scope_tokens),
        "resolutions": resolutions,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
    }


__all__ = [
    "ACTION_CONFIRMED",
    "G077Error",
    "G077FakeOnlyCallable",
    "G077FakeOnlyPort",
    "G077ReadBackSource",
    "G077ResolutionState",
    "G077SanitizedRead",
    "G077WriteActionKind",
    "G077_GENERATION_LABEL",
    "G077_MAX_RESOLUTIONS_PER_GENERATION",
    "G077_MIN_READ_INTERVAL_SECONDS",
    "G077_PERSISTENT_HALT_FILE",
    "G077_PROCESS_LOCK_FILE",
    "G077_RESOLUTION_BUDGET_FILE",
    "G077_RESOLUTION_COMPLETION_BUDGET_SECONDS",
    "G077_RESOLUTION_EVIDENCE_SUFFIX",
    "G077_RESOLUTION_START_WINDOW_SECONDS",
    "G077_RESOLUTION_STARTED_SUFFIX",
    "NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION",
    "TERMINAL_FOR_GENERATION",
    "engage_g077_halt",
    "g077_resolution_status",
    "load_g077_resolution_evidence",
    "run_g077_unknown_resolution_once",
]
