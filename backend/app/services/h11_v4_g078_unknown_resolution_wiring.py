"""G078 read-back resolution wiring (fake-only, generation-bound, unwired).

Connects an UNKNOWN write outcome to the one-use G078 read-back resolution
step.  This module is the caller the resolution step's C1 contract assigns
responsibility to: when a write outcome is UNKNOWN and the resolution step
refuses or fails for any reason, this layer treats the UNKNOWN as terminal
(persistent halt) so an unresolved outcome is never left unrecorded.

Wiring contract
---------------
1. The runtime write path invokes this function immediately (within the 15s
   resolution start window) after a write outcome is observed as UNKNOWN.
2. The resolution step latches a halt for start-window overruns, budget
   exhaustion, and unresolved / ambiguous / partial / timed-out
   classifications (C1).  This layer must not clobber those specific halt
   reasons.
3. Any other refusal or failure while an UNKNOWN exists (bad digest, non-fake
   port, invalid kind, invalid time, held process lock, already-started
   without evidence, unexpected read-back client exception) is treated as
   terminal HERE (C1 remainder): the halt is latched and a wiring-safe label
   is raised.
4. ``G078_RESOLUTION_ALREADY_STARTED_NO_RETRY`` with a valid evidence file is
   not a refusal: the previously recorded outcome governs and is returned.
5. The outcome is sanitized and never an authorization value; ``__bool__`` is
   always False.

This module is fake-only: the read-back client must be a
``G078FakeOnlyCallable`` (non-fake ports are rejected by the resolution
step).  It never reads Keychain, calls a Private API, sends a notification,
mutates ARM, or touches broker transport.  Integration into a live runtime is
a later generation-bound step (G079 candidate).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.services.h11_v4_g078_runtime import (
    ACTION_CONFIRMED,
    NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION,
    TERMINAL_FOR_GENERATION,
    G078FakeOnlyCallable,
    G078ResolutionState,
    G078WriteActionKind,
    engage_g078_halt,
    load_g078_resolution_evidence,
    run_g078_unknown_resolution_once,
)

G078_WIRING_SCHEMA = "H11_V4_G078_UNKNOWN_RESOLUTION_WIRING_V1"
G078_WIRING_HALT_REASON = "G078_WIRING_RESOLUTION_REFUSED_TERMINAL"


class G078WiringError(RuntimeError):
    """Safe-label-only wiring failure."""


@dataclass(frozen=True)
class G078WiringOutcome:
    """Sanitized resolution outcome (never an authorization value)."""

    action_scope_digest: str
    action_kind: str
    resolution_state: str
    resolution_policy: str
    halt_engaged: bool
    halt_reason: str | None
    actual_post_authorized: bool = False
    broker_post_authorized: bool = False
    entry_authorized: bool = False

    def __bool__(self) -> bool:
        # Never truthy: a resolution result is not an authorization value.
        return False


def _require_digest(value: str, label: str) -> None:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise G078WiringError(f"{label}_INVALID")


def _halt_path(state_root: Path) -> Path:
    return state_root / "g078-persistent-halt.json"


def _evidence_path(state_root: Path, action_scope_digest: str) -> Path:
    token = action_scope_digest[7:]
    return state_root / f"g078-resolution.{token}.evidence.json"


def _evidence_exists(state_root: Path, action_scope_digest: str) -> bool:
    path = _evidence_path(state_root, action_scope_digest)
    return path.is_file() and not path.is_symlink()


def _outcome_from_evidence(
    *, state_root: Path, action_scope_digest: str
) -> G078WiringOutcome:
    evidence = load_g078_resolution_evidence(
        state_root=state_root, action_scope_digest=action_scope_digest
    )
    return G078WiringOutcome(
        action_scope_digest=str(evidence.get("action_scope_digest", action_scope_digest)),
        action_kind=str(evidence.get("action_kind", "")),
        resolution_state=str(evidence.get("status", G078ResolutionState.UNRESOLVED.value)),
        resolution_policy=str(
            evidence.get("resolution_policy", "TERMINAL_FOR_GENERATION")
        ),
        halt_engaged=_halt_path(state_root).is_file(),
        halt_reason=evidence.get("halt_reason"),
    )


def wire_unknown_write_outcome_resolution_once(
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
) -> G078WiringOutcome:
    """Resolve one UNKNOWN write outcome via the one-use read-back step.

    The runtime write path calls this once, immediately after a write outcome
    is observed as UNKNOWN (within the resolution start window).  The returned
    outcome is sanitized and never authorizes anything.
    """
    _require_digest(generation_digest, "G078_WIRING_GENERATION_DIGEST")
    _require_digest(reviewed_files_digest, "G078_WIRING_REVIEWED_FILES_DIGEST")
    _require_digest(action_scope_digest, "G078_WIRING_ACTION_SCOPE_DIGEST")
    if not isinstance(action_kind, G078WriteActionKind):
        raise G078WiringError("G078_WIRING_ACTION_KIND_INVALID")
    if not isinstance(read_back_client, G078FakeOnlyCallable):
        raise G078WiringError("G078_WIRING_FAKE_ONLY_READ_BACK_REQUIRED")
    if now_utc.tzinfo is None or unknown_observed_at_utc.tzinfo is None:
        raise G078WiringError("G078_WIRING_RESOLUTION_TIME_INVALID")

    try:
        state = run_g078_unknown_resolution_once(
            state_root=state_root,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
            action_scope_digest=action_scope_digest,
            action_kind=action_kind,
            read_back_client=read_back_client,
            unknown_observed_at_utc=unknown_observed_at_utc,
            now_utc=now_utc,
            unknown_observed_monotonic=unknown_observed_monotonic,
            monotonic=monotonic,
        )
    except Exception as error:
        # C1 remainder: a refused or failed resolution while an UNKNOWN exists
        # leaves the outcome unresolvable unless this layer acts.
        if _evidence_exists(state_root, action_scope_digest):
            # Already resolved by a prior attempt: the recorded outcome governs.
            return _outcome_from_evidence(
                state_root=state_root, action_scope_digest=action_scope_digest
            )
        if not _halt_path(state_root).is_file():
            engage_g078_halt(state_root=state_root, reason=G078_WIRING_HALT_REASON)
        raise G078WiringError(G078_WIRING_HALT_REASON) from error

    return G078WiringOutcome(
        action_scope_digest=action_scope_digest,
        action_kind=action_kind.value,
        resolution_state=state,
        resolution_policy=_policy_for(state),
        halt_engaged=_halt_path(state_root).is_file(),
        halt_reason=_halt_reason(state_root),
    )


def _policy_for(state: str) -> str:
    if state == G078ResolutionState.CONFIRMED_EXECUTED.value:
        return ACTION_CONFIRMED
    if state == G078ResolutionState.CONFIRMED_NOT_EXECUTED.value:
        return NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION
    return TERMINAL_FOR_GENERATION


def _halt_reason(state_root: Path) -> str | None:
    path = _halt_path(state_root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return str(payload.get("reason"))
    except (OSError, json.JSONDecodeError):
        return "G078_WIRING_HALT_READ_UNKNOWN"


__all__ = [
    "G078WiringError",
    "G078WiringOutcome",
    "G078_WIRING_HALT_REASON",
    "G078_WIRING_SCHEMA",
    "wire_unknown_write_outcome_resolution_once",
]
