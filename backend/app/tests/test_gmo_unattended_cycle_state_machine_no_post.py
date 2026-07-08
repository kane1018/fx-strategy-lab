"""No-POST tests for the unattended paper cycle state machine / lock / ledger."""

from __future__ import annotations

import inspect

import pytest

from app.services import gmo_unattended_cycle_state_machine as module
from app.services.gmo_unattended_cycle_state_machine import (
    PAPER_CYCLE_LOCK_SCOPE,
    PAPER_EVENT_DUPLICATE_ATTEMPT_BLOCKED_SAFE,
    PAPER_EVENT_LOCK_MISSING_BLOCKED_SAFE,
    GmoUnattendedCycleStateMachineError,
    PaperCycleLock,
    SafePaperAttemptLedger,
    UnattendedPaperCycleState,
    UnattendedPaperCycleStateMachine,
    acquire_paper_cycle_lock,
)

_S = UnattendedPaperCycleState

_HAPPY_PATH = (
    _S.SIGNAL_CANDIDATE,
    _S.PREVIEW_READY,
    _S.AWAITING_OPERATOR_CONFIRMATION,
    _S.PAPER_ENTRY_REQUESTED,
)


def _machine(*, locked: bool = True) -> UnattendedPaperCycleStateMachine:
    lock = acquire_paper_cycle_lock() if locked else PaperCycleLock()
    return UnattendedPaperCycleStateMachine(lock=lock)


def _advance(machine: UnattendedPaperCycleStateMachine, *states) -> None:
    for state in states:
        machine.transition_to(state)


class TestTransitions:
    def test_full_legal_paper_cycle_reaches_completed(self) -> None:
        machine = _machine()
        _advance(machine, *_HAPPY_PATH)
        assert machine.request_paper_entry_attempt()
        _advance(
            machine,
            _S.PAPER_ENTRY_ACCEPTED,
            _S.PAPER_POSITION_OPEN,
            _S.PAPER_SETTLEMENT_CANDIDATE,
            _S.PAPER_SETTLEMENT_REQUESTED,
        )
        assert machine.request_paper_settlement_attempt()
        _advance(
            machine,
            _S.PAPER_SETTLEMENT_ACCEPTED,
            _S.PAPER_NO_POSITION_CONFIRMED,
            _S.COMPLETED,
        )
        assert machine.state is _S.COMPLETED
        assert machine.ledger.entry_attempt_count == 1
        assert machine.ledger.settlement_attempt_count == 1
        assert machine.unattended_live_completed is False

    def test_illegal_transition_halts_safely(self) -> None:
        machine = _machine()
        machine.transition_to(_S.PAPER_POSITION_OPEN)  # illegal from IDLE
        assert machine.state is _S.HALTED
        assert machine.halt_reason_safe_label == "ILLEGAL_TRANSITION_BLOCKED"

    def test_halted_is_terminal(self) -> None:
        machine = _machine()
        machine.transition_to(_S.HALTED)
        machine.transition_to(_S.SIGNAL_CANDIDATE)
        assert machine.state is _S.HALTED

    def test_explicit_halt_is_always_legal(self) -> None:
        machine = _machine()
        _advance(machine, *_HAPPY_PATH)
        machine.transition_to(_S.HALTED)
        assert machine.state is _S.HALTED

    def test_machine_is_never_truthy(self) -> None:
        assert not _machine()


class TestAttemptGating:
    def test_attempt_without_lock_is_blocked_and_halts(self) -> None:
        machine = _machine(locked=False)
        _advance(machine, *_HAPPY_PATH)
        assert machine.request_paper_entry_attempt() is False
        assert machine.state is _S.HALTED
        assert PAPER_EVENT_LOCK_MISSING_BLOCKED_SAFE in machine.ledger.events

    def test_wrong_scope_lock_is_blocked(self) -> None:
        machine = UnattendedPaperCycleStateMachine(
            lock=PaperCycleLock(acquired=True, scope="SOMETHING_ELSE")
        )
        _advance(machine, *_HAPPY_PATH)
        assert machine.request_paper_entry_attempt() is False
        assert machine.state is _S.HALTED

    def test_entry_attempt_outside_requested_state_halts(self) -> None:
        machine = _machine()
        assert machine.request_paper_entry_attempt() is False
        assert machine.state is _S.HALTED

    def test_duplicate_entry_attempt_is_blocked(self) -> None:
        machine = _machine()
        _advance(machine, *_HAPPY_PATH)
        assert machine.request_paper_entry_attempt() is True
        assert machine.request_paper_entry_attempt() is False
        assert machine.state is _S.HALTED
        assert machine.ledger.entry_attempt_count == 1
        assert (
            PAPER_EVENT_DUPLICATE_ATTEMPT_BLOCKED_SAFE in machine.ledger.events
        )

    def test_duplicate_settlement_attempt_is_blocked(self) -> None:
        machine = _machine()
        _advance(machine, *_HAPPY_PATH)
        machine.request_paper_entry_attempt()
        _advance(
            machine,
            _S.PAPER_ENTRY_ACCEPTED,
            _S.PAPER_POSITION_OPEN,
            _S.PAPER_SETTLEMENT_CANDIDATE,
            _S.PAPER_SETTLEMENT_REQUESTED,
        )
        assert machine.request_paper_settlement_attempt() is True
        assert machine.request_paper_settlement_attempt() is False
        assert machine.state is _S.HALTED
        assert machine.ledger.settlement_attempt_count == 1


class TestLedger:
    def test_ledger_accepts_only_paper_event_categories(self) -> None:
        ledger = SafePaperAttemptLedger()
        with pytest.raises(GmoUnattendedCycleStateMachineError):
            ledger.record("RAW_BROKER_EVENT")

    def test_ledger_holds_categories_and_counts_only(self) -> None:
        ledger = SafePaperAttemptLedger()
        assert ledger.record_entry_attempt() is True
        assert ledger.record_entry_attempt() is False
        assert ledger.entry_attempt_count == 1
        assert all(event.startswith("PAPER_EVENT_") for event in ledger.events)
        assert not hasattr(ledger, "__dict__")

    def test_lock_scope_is_paper_synthetic_and_never_truthy(self) -> None:
        lock = acquire_paper_cycle_lock()
        assert lock.acquired is True
        assert lock.scope == PAPER_CYCLE_LOCK_SCOPE
        assert "BROKER" not in lock.scope or "NOT_BROKER" in lock.scope
        assert not lock


class TestModuleIsolation:
    def test_module_has_no_broker_or_env_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "requests" not in source
        assert "/private/v1" not in source
        assert "order_id" not in source
        assert "position_id" not in source
