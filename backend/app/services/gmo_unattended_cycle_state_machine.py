"""Unattended PAPER cycle state machine, lock, and safe attempt ledger.

Paper/synthetic scope only. This module gives the unattended readiness layer
the pieces that structurally prevent duplicate attempts:

- A state machine with an explicit legal-transition table. An illegal
  transition never raises data outward: it moves the machine to ``HALTED``
  and records a safe event.
- A cycle lock that is paper/synthetic-scoped by construction (the scope
  string is fixed) and is required before any paper attempt can be recorded.
- A safe attempt ledger holding ONLY safe event category labels and counts.
  There is no field for a broker/order/position/transaction ID, a size, a
  price, or a PnL, so none can be stored. Entry and settlement attempts are
  each capped at one per cycle; a duplicate is refused and the machine
  halts.

Nothing here touches a broker, the network, credentials, ``.env``, or the
live attempt ledger on disk. Completion of a paper cycle is NEVER
"unattended live completed": the result pins that flag false.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GmoUnattendedCycleStateMachineError(RuntimeError):
    """Raised for fail-closed violations. Never carries a raw value."""


class UnattendedPaperCycleState(str, Enum):
    IDLE = "IDLE"
    SIGNAL_CANDIDATE = "SIGNAL_CANDIDATE"
    PREVIEW_READY = "PREVIEW_READY"
    AWAITING_OPERATOR_CONFIRMATION = "AWAITING_OPERATOR_CONFIRMATION"
    PAPER_ENTRY_REQUESTED = "PAPER_ENTRY_REQUESTED"
    PAPER_ENTRY_ACCEPTED = "PAPER_ENTRY_ACCEPTED"
    PAPER_POSITION_OPEN = "PAPER_POSITION_OPEN"
    PAPER_SETTLEMENT_CANDIDATE = "PAPER_SETTLEMENT_CANDIDATE"
    PAPER_SETTLEMENT_REQUESTED = "PAPER_SETTLEMENT_REQUESTED"
    PAPER_SETTLEMENT_ACCEPTED = "PAPER_SETTLEMENT_ACCEPTED"
    PAPER_NO_POSITION_CONFIRMED = "PAPER_NO_POSITION_CONFIRMED"
    HALTED = "HALTED"
    COMPLETED = "COMPLETED"


_S = UnattendedPaperCycleState

# Every state may always move to HALTED (safe halt is always legal).
LEGAL_TRANSITIONS: dict[UnattendedPaperCycleState, frozenset[UnattendedPaperCycleState]] = {
    _S.IDLE: frozenset({_S.SIGNAL_CANDIDATE}),
    _S.SIGNAL_CANDIDATE: frozenset({_S.PREVIEW_READY, _S.IDLE}),
    _S.PREVIEW_READY: frozenset({_S.AWAITING_OPERATOR_CONFIRMATION, _S.IDLE}),
    _S.AWAITING_OPERATOR_CONFIRMATION: frozenset(
        {_S.PAPER_ENTRY_REQUESTED, _S.IDLE}
    ),
    _S.PAPER_ENTRY_REQUESTED: frozenset({_S.PAPER_ENTRY_ACCEPTED}),
    _S.PAPER_ENTRY_ACCEPTED: frozenset({_S.PAPER_POSITION_OPEN}),
    _S.PAPER_POSITION_OPEN: frozenset({_S.PAPER_SETTLEMENT_CANDIDATE}),
    _S.PAPER_SETTLEMENT_CANDIDATE: frozenset({_S.PAPER_SETTLEMENT_REQUESTED}),
    _S.PAPER_SETTLEMENT_REQUESTED: frozenset({_S.PAPER_SETTLEMENT_ACCEPTED}),
    _S.PAPER_SETTLEMENT_ACCEPTED: frozenset({_S.PAPER_NO_POSITION_CONFIRMED}),
    _S.PAPER_NO_POSITION_CONFIRMED: frozenset({_S.COMPLETED}),
    _S.HALTED: frozenset(),
    _S.COMPLETED: frozenset(),
}

PAPER_CYCLE_LOCK_SCOPE = "PAPER_SYNTHETIC_ONLY_NOT_BROKER_BOUND"

_ALLOWED_EVENT_PREFIX = "PAPER_EVENT_"

PAPER_EVENT_SIGNAL_CANDIDATE = "PAPER_EVENT_SIGNAL_CANDIDATE"
PAPER_EVENT_PREVIEW_READY = "PAPER_EVENT_PREVIEW_READY"
PAPER_EVENT_ENTRY_ATTEMPT_RECORDED = "PAPER_EVENT_ENTRY_ATTEMPT_RECORDED"
PAPER_EVENT_ENTRY_ACCEPTED_SAFE = "PAPER_EVENT_ENTRY_ACCEPTED_SAFE"
PAPER_EVENT_POSITION_OPEN_CONFIRMED_SAFE = (
    "PAPER_EVENT_POSITION_OPEN_CONFIRMED_SAFE"
)
PAPER_EVENT_SETTLEMENT_ATTEMPT_RECORDED = "PAPER_EVENT_SETTLEMENT_ATTEMPT_RECORDED"
PAPER_EVENT_SETTLEMENT_ACCEPTED_SAFE = "PAPER_EVENT_SETTLEMENT_ACCEPTED_SAFE"
PAPER_EVENT_NO_POSITION_CONFIRMED_SAFE = "PAPER_EVENT_NO_POSITION_CONFIRMED_SAFE"
PAPER_EVENT_GUARD_HALTED_SAFE = "PAPER_EVENT_GUARD_HALTED_SAFE"
PAPER_EVENT_ILLEGAL_TRANSITION_HALTED_SAFE = (
    "PAPER_EVENT_ILLEGAL_TRANSITION_HALTED_SAFE"
)
PAPER_EVENT_DUPLICATE_ATTEMPT_BLOCKED_SAFE = (
    "PAPER_EVENT_DUPLICATE_ATTEMPT_BLOCKED_SAFE"
)
PAPER_EVENT_LOCK_MISSING_BLOCKED_SAFE = "PAPER_EVENT_LOCK_MISSING_BLOCKED_SAFE"


@dataclass(frozen=True)
class PaperCycleLock:
    """Paper/synthetic-scoped cycle lock. Never bound to a broker or account.

    The scope string is fixed at construction; a lock claiming any other
    scope is rejected by the state machine.
    """

    acquired: bool = False
    scope: str = PAPER_CYCLE_LOCK_SCOPE

    def __bool__(self) -> bool:
        return False


def acquire_paper_cycle_lock() -> PaperCycleLock:
    """Acquire the in-memory paper cycle lock (paper scope only)."""

    return PaperCycleLock(acquired=True)


class SafePaperAttemptLedger:
    """In-memory ledger of safe event categories and counts only.

    Structurally cannot store an ID or a value: ``record`` accepts only
    strings with the ``PAPER_EVENT_`` prefix from a fixed vocabulary shape,
    and the only numeric state is the per-kind attempt counters.
    """

    __slots__ = ("_events", "_entry_attempts", "_settlement_attempts")

    def __init__(self) -> None:
        self._events: list[str] = []
        self._entry_attempts = 0
        self._settlement_attempts = 0

    def record(self, event_category: str) -> None:
        if not event_category.startswith(_ALLOWED_EVENT_PREFIX):
            raise GmoUnattendedCycleStateMachineError(
                "attempt ledger accepts PAPER_EVENT_* safe categories only"
            )
        self._events.append(event_category)

    def record_entry_attempt(self) -> bool:
        """Record one paper entry attempt. Returns False on a duplicate."""

        if self._entry_attempts >= 1:
            self.record(PAPER_EVENT_DUPLICATE_ATTEMPT_BLOCKED_SAFE)
            return False
        self._entry_attempts += 1
        self.record(PAPER_EVENT_ENTRY_ATTEMPT_RECORDED)
        return True

    def record_settlement_attempt(self) -> bool:
        """Record one paper settlement attempt. Returns False on a duplicate."""

        if self._settlement_attempts >= 1:
            self.record(PAPER_EVENT_DUPLICATE_ATTEMPT_BLOCKED_SAFE)
            return False
        self._settlement_attempts += 1
        self.record(PAPER_EVENT_SETTLEMENT_ATTEMPT_RECORDED)
        return True

    @property
    def entry_attempt_count(self) -> int:
        return self._entry_attempts

    @property
    def settlement_attempt_count(self) -> int:
        return self._settlement_attempts

    @property
    def events(self) -> tuple[str, ...]:
        return tuple(self._events)


@dataclass
class UnattendedPaperCycleStateMachine:
    """Paper cycle state machine with legal-transition enforcement.

    Illegal transitions, missing locks, and duplicate attempts all converge
    to the ``HALTED`` state with a safe event; nothing raises data outward
    during normal operation.
    """

    lock: PaperCycleLock
    ledger: SafePaperAttemptLedger = field(default_factory=SafePaperAttemptLedger)
    state: UnattendedPaperCycleState = UnattendedPaperCycleState.IDLE
    halt_reason_safe_label: str = ""
    # Paper completion is never live completion; fixed false.
    unattended_live_completed: bool = False

    def _halt(self, event: str, reason: str) -> UnattendedPaperCycleState:
        self.ledger.record(event)
        self.state = UnattendedPaperCycleState.HALTED
        self.halt_reason_safe_label = reason
        return self.state

    def transition_to(
        self, new_state: UnattendedPaperCycleState
    ) -> UnattendedPaperCycleState:
        """Perform one transition; illegal targets halt safely."""

        if new_state is UnattendedPaperCycleState.HALTED:
            return self._halt(
                PAPER_EVENT_GUARD_HALTED_SAFE, "EXPLICIT_SAFE_HALT"
            )
        if new_state not in LEGAL_TRANSITIONS[self.state]:
            return self._halt(
                PAPER_EVENT_ILLEGAL_TRANSITION_HALTED_SAFE,
                "ILLEGAL_TRANSITION_BLOCKED",
            )
        self.state = new_state
        return self.state

    def _attempt_allowed(self) -> bool:
        if not (self.lock.acquired and self.lock.scope == PAPER_CYCLE_LOCK_SCOPE):
            self.ledger.record(PAPER_EVENT_LOCK_MISSING_BLOCKED_SAFE)
            self._halt(
                PAPER_EVENT_GUARD_HALTED_SAFE, "LOCK_NOT_ACQUIRED_BLOCKED"
            )
            return False
        return True

    def request_paper_entry_attempt(self) -> bool:
        """Gate one paper entry attempt behind lock + state + ledger cap."""

        if not self._attempt_allowed():
            return False
        if self.state is not UnattendedPaperCycleState.PAPER_ENTRY_REQUESTED:
            self._halt(
                PAPER_EVENT_ILLEGAL_TRANSITION_HALTED_SAFE,
                "ENTRY_ATTEMPT_OUTSIDE_REQUESTED_STATE",
            )
            return False
        if not self.ledger.record_entry_attempt():
            self._halt(
                PAPER_EVENT_GUARD_HALTED_SAFE, "DUPLICATE_ENTRY_ATTEMPT_BLOCKED"
            )
            return False
        return True

    def request_paper_settlement_attempt(self) -> bool:
        """Gate one paper settlement attempt behind lock + state + ledger cap."""

        if not self._attempt_allowed():
            return False
        if self.state is not UnattendedPaperCycleState.PAPER_SETTLEMENT_REQUESTED:
            self._halt(
                PAPER_EVENT_ILLEGAL_TRANSITION_HALTED_SAFE,
                "SETTLEMENT_ATTEMPT_OUTSIDE_REQUESTED_STATE",
            )
            return False
        if not self.ledger.record_settlement_attempt():
            self._halt(
                PAPER_EVENT_GUARD_HALTED_SAFE,
                "DUPLICATE_SETTLEMENT_ATTEMPT_BLOCKED",
            )
            return False
        return True

    def __bool__(self) -> bool:
        return False
