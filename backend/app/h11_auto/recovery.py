"""Crash/restart recovery decisions for the no-POST Phase A state machine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.h11_auto.persistence import StoredCycle
from app.h11_auto.state_machine import AutoCycleState, SafeBrokerState


class RecoveryAction(str, Enum):
    START_SYNTHETIC_ATTEMPT = "START_SYNTHETIC_ATTEMPT"
    OBSERVE_PENDING_NO_RESEND = "OBSERVE_PENDING_NO_RESEND"
    MONITOR_PROTECTED_POSITION = "MONITOR_PROTECTED_POSITION"
    CONFIRM_FLAT_NO_WRITE = "CONFIRM_FLAT_NO_WRITE"
    HALT_OPERATOR_REVIEW = "HALT_OPERATOR_REVIEW"


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    safe_to_continue_observation: bool
    entry_resend_allowed: bool
    exit_resend_allowed: bool
    blocked_reasons: tuple[str, ...]
    actual_post_allowed: bool = False

    def __bool__(self) -> bool:
        return False


def evaluate_restart_recovery(
    *, cycle: StoredCycle, broker_state: SafeBrokerState, safe_read_fresh: bool
) -> RecoveryDecision:
    if not safe_read_fresh:
        return _halt("SAFE_READ_NOT_FRESH")
    if broker_state in {
        SafeBrokerState.UNKNOWN,
        SafeBrokerState.EXTERNAL_OR_MANUAL_CONFLICT,
    }:
        return _halt(broker_state.value)
    if cycle.state is AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED:
        return _halt("LOCAL_STATE_ALREADY_HALTED")

    if cycle.state is AutoCycleState.INTENT_PERSISTED:
        if cycle.attempt_count == 0 and broker_state is SafeBrokerState.FLAT_CLEAR:
            return RecoveryDecision(
                action=RecoveryAction.START_SYNTHETIC_ATTEMPT,
                safe_to_continue_observation=True,
                entry_resend_allowed=False,
                exit_resend_allowed=False,
                blocked_reasons=(),
            )
        return _halt("INTENT_STATE_MISMATCH")

    if cycle.state is AutoCycleState.PROTECTED_ENTRY_PENDING:
        if (
            cycle.attempt_count == 1
            and broker_state is SafeBrokerState.PROTECTED_ENTRY_PENDING
        ):
            return RecoveryDecision(
                action=RecoveryAction.OBSERVE_PENDING_NO_RESEND,
                safe_to_continue_observation=True,
                entry_resend_allowed=False,
                exit_resend_allowed=False,
                blocked_reasons=(),
            )
        return _halt("PENDING_ENTRY_STATE_MISMATCH")

    if cycle.state is AutoCycleState.POSITION_PROTECTED:
        if broker_state is SafeBrokerState.POSITION_PROTECTED:
            return RecoveryDecision(
                action=RecoveryAction.MONITOR_PROTECTED_POSITION,
                safe_to_continue_observation=True,
                entry_resend_allowed=False,
                exit_resend_allowed=False,
                blocked_reasons=(),
            )
        return _halt("PROTECTED_POSITION_STATE_MISMATCH")

    if cycle.state is AutoCycleState.EXIT_PENDING:
        if cycle.exit_attempt_count != 1:
            return _halt("EXIT_ATTEMPT_LEDGER_MISMATCH")
        if broker_state is SafeBrokerState.POSITION_PROTECTED:
            return _halt("EXIT_RESULT_UNKNOWN_NO_RESEND")
        if broker_state is SafeBrokerState.FLAT_AFTER_EXIT:
            return RecoveryDecision(
                action=RecoveryAction.CONFIRM_FLAT_NO_WRITE,
                safe_to_continue_observation=True,
                entry_resend_allowed=False,
                exit_resend_allowed=False,
                blocked_reasons=(),
            )
        return _halt("EXIT_STATE_MISMATCH")

    if cycle.state is AutoCycleState.FLAT_RECONCILED:
        if broker_state in {SafeBrokerState.FLAT_CLEAR, SafeBrokerState.FLAT_AFTER_EXIT}:
            return RecoveryDecision(
                action=RecoveryAction.CONFIRM_FLAT_NO_WRITE,
                safe_to_continue_observation=True,
                entry_resend_allowed=False,
                exit_resend_allowed=False,
                blocked_reasons=(),
            )
        return _halt("FLAT_STATE_MISMATCH")

    return _halt("LOCAL_STATE_NOT_RECOVERABLE")


def _halt(reason: str) -> RecoveryDecision:
    return RecoveryDecision(
        action=RecoveryAction.HALT_OPERATOR_REVIEW,
        safe_to_continue_observation=False,
        entry_resend_allowed=False,
        exit_resend_allowed=False,
        blocked_reasons=(reason,),
    )
