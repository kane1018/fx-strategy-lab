"""Persistent H-11 v3 observed-live state machine (fake-only, no-POST).

This is the no-POST implementation slice authorized for the accelerated
observed-unattended policy. It provides a process lock, atomic safe-state
persistence, legal transitions, one-attempt caps, and fail-closed handling of
unknown outcomes. It has no sender, HTTP client, credential, environment read,
broker import, or hard-guard allow path.

Only safe labels and counts are persisted. The future actual activation step
must provide a separately reviewed sealed intent/value store and transport.
"""

from __future__ import annotations

import fcntl
import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from pathlib import Path

from app.services.h11_v3_ifdoco_profile import H11_V3_CONFIG_HASH


class H11V3ObservedState(str, Enum):
    READY = "READY"
    INTENT_PERSISTED = "INTENT_PERSISTED"
    ENTRY_ATTEMPT_STARTED = "ENTRY_ATTEMPT_STARTED"
    PROTECTED_ORDER_ACTIVE = "PROTECTED_ORDER_ACTIVE"
    POSITION_PROTECTED = "POSITION_PROTECTED"
    SETTLEMENT_ATTEMPT_STARTED = "SETTLEMENT_ATTEMPT_STARTED"
    FLAT_RECONCILED = "FLAT_RECONCILED"
    HALTED = "HALTED"


class H11V3FakeOutcome(str, Enum):
    ACCEPTED_SANITIZED = "ACCEPTED_SANITIZED"
    REJECTED_SANITIZED = "REJECTED_SANITIZED"
    UNKNOWN_SANITIZED = "UNKNOWN_SANITIZED"
    TIMEOUT_SANITIZED = "TIMEOUT_SANITIZED"
    NETWORK_ERROR_SANITIZED = "NETWORK_ERROR_SANITIZED"


class H11V3ObservedStateError(RuntimeError):
    """Safe fail-closed error; never contains a raw value, ID, or secret."""


_S = H11V3ObservedState
_LEGAL_TRANSITIONS: dict[H11V3ObservedState, frozenset[H11V3ObservedState]] = {
    _S.READY: frozenset({_S.INTENT_PERSISTED, _S.HALTED}),
    _S.INTENT_PERSISTED: frozenset({_S.ENTRY_ATTEMPT_STARTED, _S.HALTED}),
    _S.ENTRY_ATTEMPT_STARTED: frozenset({_S.PROTECTED_ORDER_ACTIVE, _S.HALTED}),
    _S.PROTECTED_ORDER_ACTIVE: frozenset({_S.POSITION_PROTECTED, _S.HALTED}),
    _S.POSITION_PROTECTED: frozenset(
        {_S.SETTLEMENT_ATTEMPT_STARTED, _S.FLAT_RECONCILED, _S.HALTED}
    ),
    _S.SETTLEMENT_ATTEMPT_STARTED: frozenset({_S.FLAT_RECONCILED, _S.HALTED}),
    _S.FLAT_RECONCILED: frozenset({_S.READY, _S.HALTED}),
    _S.HALTED: frozenset(),
}


@dataclass
class H11V3ObservedPersistentState:
    config_hash: str = H11_V3_CONFIG_HASH
    state: str = H11V3ObservedState.READY.value
    entry_attempt_count: int = 0
    settlement_attempt_count: int = 0
    reconciled_flat_cycle_count: int = 0
    discipline_violation_count: int = 0
    halt_reason_safe_label: str = ""
    last_entry_day_jst: str | None = None
    actual_post: bool = False
    actual_post_count: int = 0
    credential_read: bool = False
    broker_read: bool = False

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V3FakeSafetyGate:
    """Fail-closed session-level prerequisites for a fake lifecycle."""

    boot_reconciled: bool = False
    budget_remaining: bool = False
    kill_off: bool = False
    dead_man_alive: bool = False
    notification_ready: bool = False
    broker_native_expiry_confirmed: bool = False
    sealed_credential_boundary_reviewed: bool = False


@dataclass(frozen=True)
class H11V3FakeCycleInput:
    cycle_day_jst: str
    safety_gate: H11V3FakeSafetyGate
    entry_outcome: H11V3FakeOutcome
    protection_reconciled: bool
    position_protected: bool
    broker_oco_settled: bool = False
    settlement_outcome: H11V3FakeOutcome | None = None
    flat_reconciled: bool = False


@dataclass(frozen=True)
class H11V3FakeCycleResult:
    final_state: H11V3ObservedState
    halt_reason_safe_label: str
    entry_attempt_count: int
    settlement_attempt_count: int
    actual_post: bool = False
    actual_post_count: int = 0
    broker_read: bool = False
    credential_read: bool = False


class H11V3ObservedStateStore:
    """Atomic safe-state store with a non-blocking process lock."""

    def __init__(self, state_path: Path, lock_path: Path | None = None) -> None:
        self.state_path = state_path
        self.lock_path = lock_path or state_path.with_suffix(state_path.suffix + ".lock")
        self._lock_file: object | None = None

    def __enter__(self) -> H11V3ObservedStateStore:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            lock_file.close()
            raise H11V3ObservedStateError("concurrent cycle invocation blocked") from error
        self._lock_file = lock_file
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._lock_file is None:
            return
        lock_file = self._lock_file
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
        lock_file.close()  # type: ignore[attr-defined]
        self._lock_file = None

    def load(self) -> H11V3ObservedPersistentState:
        if not self.state_path.exists():
            return H11V3ObservedPersistentState()
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        state = H11V3ObservedPersistentState(**payload)
        if state.config_hash != H11_V3_CONFIG_HASH:
            raise H11V3ObservedStateError("persisted config hash mismatch")
        return state

    def save(self, state: H11V3ObservedPersistentState) -> None:
        if self._lock_file is None:
            raise H11V3ObservedStateError("state save requires the process lock")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        serialized = json.dumps(asdict(state), ensure_ascii=True, sort_keys=True, indent=2)
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(self.state_path)


def run_h11_v3_fake_cycle_no_post(
    *,
    store: H11V3ObservedStateStore,
    cycle_input: H11V3FakeCycleInput,
) -> H11V3FakeCycleResult:
    """Run one deterministic fake lifecycle with zero network or POST."""

    with store:
        state = store.load()
        if H11V3ObservedState(state.state) is H11V3ObservedState.HALTED:
            return _result(state)
        if H11V3ObservedState(state.state) is H11V3ObservedState.FLAT_RECONCILED:
            _transition(state, H11V3ObservedState.READY)
            state.entry_attempt_count = 0
            state.settlement_attempt_count = 0
        if H11V3ObservedState(state.state) is not H11V3ObservedState.READY:
            _halt(state, "RESTART_RECONCILIATION_REQUIRED")
            store.save(state)
            return _result(state)

        gate_reason = _validate_fake_safety_gate(cycle_input)
        if gate_reason:
            _halt(state, gate_reason)
            store.save(state)
            return _result(state)
        if state.last_entry_day_jst == cycle_input.cycle_day_jst:
            _halt(state, "MAX_ENTRIES_PER_DAY_BLOCKED")
            store.save(state)
            return _result(state)

        _transition(state, H11V3ObservedState.INTENT_PERSISTED)
        store.save(state)
        _transition(state, H11V3ObservedState.ENTRY_ATTEMPT_STARTED)
        state.entry_attempt_count += 1
        state.last_entry_day_jst = cycle_input.cycle_day_jst
        # Attempt state is durable before the fake send outcome is observed.
        # A crash from this point therefore restarts into reconciliation/HALT,
        # never into a fresh attempt.
        store.save(state)
        if state.entry_attempt_count != 1:
            _halt(state, "DUPLICATE_ENTRY_ATTEMPT_BLOCKED")
            store.save(state)
            return _result(state)

        if cycle_input.entry_outcome is not H11V3FakeOutcome.ACCEPTED_SANITIZED:
            _halt(state, f"ENTRY_{cycle_input.entry_outcome.value}_HALT")
            store.save(state)
            return _result(state)
        _transition(state, H11V3ObservedState.PROTECTED_ORDER_ACTIVE)
        store.save(state)

        if not cycle_input.protection_reconciled or not cycle_input.position_protected:
            _halt(state, "SERVER_SIDE_PROTECTION_NOT_RECONCILED")
            store.save(state)
            return _result(state)
        _transition(state, H11V3ObservedState.POSITION_PROTECTED)
        store.save(state)

        if cycle_input.broker_oco_settled:
            if not cycle_input.flat_reconciled:
                _halt(state, "BROKER_OCO_FLAT_NOT_RECONCILED")
            else:
                _mark_flat(state)
            store.save(state)
            return _result(state)

        if cycle_input.settlement_outcome is None:
            store.save(state)
            return _result(state)

        _transition(state, H11V3ObservedState.SETTLEMENT_ATTEMPT_STARTED)
        state.settlement_attempt_count += 1
        # The independent settlement attempt is likewise persisted before its
        # outcome is consumed, so restart cannot resend it.
        store.save(state)
        if state.settlement_attempt_count != 1:
            _halt(state, "DUPLICATE_SETTLEMENT_ATTEMPT_BLOCKED")
        elif cycle_input.settlement_outcome is not H11V3FakeOutcome.ACCEPTED_SANITIZED:
            _halt(state, f"SETTLEMENT_{cycle_input.settlement_outcome.value}_HALT")
        elif not cycle_input.flat_reconciled:
            _halt(state, "SETTLEMENT_FLAT_NOT_RECONCILED")
        else:
            _mark_flat(state)
        store.save(state)
        return _result(state)


def _transition(
    state: H11V3ObservedPersistentState,
    target: H11V3ObservedState,
) -> None:
    current = H11V3ObservedState(state.state)
    if target not in _LEGAL_TRANSITIONS[current]:
        state.discipline_violation_count += 1
        _halt(state, "ILLEGAL_STATE_TRANSITION")
        return
    state.state = target.value


def _validate_fake_safety_gate(cycle_input: H11V3FakeCycleInput) -> str:
    try:
        date.fromisoformat(cycle_input.cycle_day_jst)
    except ValueError:
        return "INVALID_CYCLE_DAY_BLOCKED"
    checks = (
        (cycle_input.safety_gate.boot_reconciled, "BOOT_RECONCILIATION_REQUIRED"),
        (cycle_input.safety_gate.budget_remaining, "BUDGET_GATE_BLOCKED"),
        (cycle_input.safety_gate.kill_off, "KILL_SWITCH_BLOCKED"),
        (cycle_input.safety_gate.dead_man_alive, "DEAD_MAN_BLOCKED"),
        (cycle_input.safety_gate.notification_ready, "NOTIFICATION_PATH_BLOCKED"),
        (
            cycle_input.safety_gate.broker_native_expiry_confirmed,
            "BROKER_NATIVE_EXPIRY_UNKNOWN",
        ),
        (
            cycle_input.safety_gate.sealed_credential_boundary_reviewed,
            "SEALED_CREDENTIAL_BOUNDARY_NOT_REVIEWED",
        ),
    )
    return next((reason for passed, reason in checks if not passed), "")


def _halt(state: H11V3ObservedPersistentState, reason: str) -> None:
    state.state = H11V3ObservedState.HALTED.value
    state.halt_reason_safe_label = reason


def _mark_flat(state: H11V3ObservedPersistentState) -> None:
    _transition(state, H11V3ObservedState.FLAT_RECONCILED)
    state.reconciled_flat_cycle_count += 1


def _result(state: H11V3ObservedPersistentState) -> H11V3FakeCycleResult:
    return H11V3FakeCycleResult(
        final_state=H11V3ObservedState(state.state),
        halt_reason_safe_label=state.halt_reason_safe_label,
        entry_attempt_count=state.entry_attempt_count,
        settlement_attempt_count=state.settlement_attempt_count,
    )
