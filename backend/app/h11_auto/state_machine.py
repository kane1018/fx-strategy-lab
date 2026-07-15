"""Deterministic state machine for the fake-only automatic cycle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class H11AutoStateError(RuntimeError):
    """Fail-closed state transition error with safe labels only."""


class AutoCycleState(str, Enum):
    OFF = "OFF"
    BOOT_RECONCILING = "BOOT_RECONCILING"
    ARMED = "ARMED"
    WAITING_SIGNAL = "WAITING_SIGNAL"
    INTENT_PERSISTED = "INTENT_PERSISTED"
    PROTECTED_ENTRY_PENDING = "PROTECTED_ENTRY_PENDING"
    POSITION_PROTECTED = "POSITION_PROTECTED"
    EXIT_PENDING = "EXIT_PENDING"
    FLAT_RECONCILED = "FLAT_RECONCILED"
    HALTED_OPERATOR_REVIEW_REQUIRED = "HALTED_OPERATOR_REVIEW_REQUIRED"


class SafeBrokerState(str, Enum):
    FLAT_CLEAR = "FLAT_CLEAR"
    PROTECTED_ENTRY_PENDING = "PROTECTED_ENTRY_PENDING"
    POSITION_PROTECTED = "POSITION_PROTECTED"
    FLAT_AFTER_EXIT = "FLAT_AFTER_EXIT"
    EXTERNAL_OR_MANUAL_CONFLICT = "EXTERNAL_OR_MANUAL_CONFLICT"
    UNKNOWN = "UNKNOWN"


_ALLOWED_TRANSITIONS: dict[AutoCycleState, frozenset[AutoCycleState]] = {
    AutoCycleState.OFF: frozenset({AutoCycleState.BOOT_RECONCILING}),
    AutoCycleState.BOOT_RECONCILING: frozenset(
        {AutoCycleState.ARMED, AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED}
    ),
    AutoCycleState.ARMED: frozenset(
        {AutoCycleState.WAITING_SIGNAL, AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED}
    ),
    AutoCycleState.WAITING_SIGNAL: frozenset(
        {AutoCycleState.INTENT_PERSISTED, AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED}
    ),
    AutoCycleState.INTENT_PERSISTED: frozenset(
        {
            AutoCycleState.PROTECTED_ENTRY_PENDING,
            AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        }
    ),
    AutoCycleState.PROTECTED_ENTRY_PENDING: frozenset(
        {
            AutoCycleState.POSITION_PROTECTED,
            AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        }
    ),
    AutoCycleState.POSITION_PROTECTED: frozenset(
        {AutoCycleState.EXIT_PENDING, AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED}
    ),
    AutoCycleState.EXIT_PENDING: frozenset(
        {AutoCycleState.FLAT_RECONCILED, AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED}
    ),
    AutoCycleState.FLAT_RECONCILED: frozenset(
        {
            AutoCycleState.WAITING_SIGNAL,
            AutoCycleState.OFF,
            AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        }
    ),
    AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED: frozenset(),
}


def require_transition(current: AutoCycleState, target: AutoCycleState) -> None:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise H11AutoStateError(f"transition refused: {current.value} -> {target.value}")


@dataclass(frozen=True)
class BootReconcileResult:
    reconciled: bool
    target_state: AutoCycleState
    blocked_reasons: tuple[str, ...]
    actual_post_allowed: bool = False

    def __bool__(self) -> bool:
        return False


def evaluate_boot_reconcile(
    *,
    local_state: AutoCycleState,
    broker_state: SafeBrokerState,
    safe_read_fresh: bool,
) -> BootReconcileResult:
    reasons: list[str] = []
    if not isinstance(local_state, AutoCycleState) or not isinstance(
        broker_state, SafeBrokerState
    ):
        return BootReconcileResult(
            reconciled=False,
            target_state=AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
            blocked_reasons=("RECONCILE_INPUT_INVALID",),
        )
    if safe_read_fresh is not True:
        reasons.append("SAFE_READ_NOT_FRESH")
    compatible = {
        AutoCycleState.OFF: {SafeBrokerState.FLAT_CLEAR},
        AutoCycleState.BOOT_RECONCILING: {SafeBrokerState.FLAT_CLEAR},
        AutoCycleState.ARMED: {SafeBrokerState.FLAT_CLEAR},
        AutoCycleState.WAITING_SIGNAL: {SafeBrokerState.FLAT_CLEAR},
        AutoCycleState.INTENT_PERSISTED: {SafeBrokerState.FLAT_CLEAR},
        AutoCycleState.PROTECTED_ENTRY_PENDING: {
            SafeBrokerState.PROTECTED_ENTRY_PENDING
        },
        AutoCycleState.POSITION_PROTECTED: {SafeBrokerState.POSITION_PROTECTED},
        AutoCycleState.EXIT_PENDING: {
            SafeBrokerState.POSITION_PROTECTED,
            SafeBrokerState.FLAT_AFTER_EXIT,
        },
        AutoCycleState.FLAT_RECONCILED: {
            SafeBrokerState.FLAT_CLEAR,
            SafeBrokerState.FLAT_AFTER_EXIT,
        },
        AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED: set(),
    }
    if broker_state in {
        SafeBrokerState.UNKNOWN,
        SafeBrokerState.EXTERNAL_OR_MANUAL_CONFLICT,
    }:
        reasons.append(broker_state.value)
    elif broker_state not in compatible[local_state]:
        reasons.append("LOCAL_BROKER_STATE_MISMATCH")
    reconciled = not reasons
    return BootReconcileResult(
        reconciled=reconciled,
        target_state=(
            AutoCycleState.ARMED
            if reconciled
            else AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED
        ),
        blocked_reasons=tuple(reasons),
    )
