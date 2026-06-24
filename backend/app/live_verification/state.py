"""State rules for Phase 3C-1 live verification mocked core."""

from __future__ import annotations

from enum import Enum

from app.live_verification.errors import LiveVerificationStateError


class LiveVerificationState(str, Enum):
    INIT = "INIT"
    READONLY_PRECHECK = "READONLY_PRECHECK"
    RISK_DECISION_CONFIRMED = "RISK_DECISION_CONFIRMED"
    ORDER_INTENT_CREATED = "ORDER_INTENT_CREATED"
    MANUAL_CONFIRMATION_REQUIRED = "MANUAL_CONFIRMATION_REQUIRED"
    READY_FOR_ORDER_REVIEW = "READY_FOR_ORDER_REVIEW"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


ALLOWED_TRANSITIONS: dict[LiveVerificationState, frozenset[LiveVerificationState]] = {
    LiveVerificationState.INIT: frozenset({
        LiveVerificationState.READONLY_PRECHECK,
        LiveVerificationState.STOPPED,
        LiveVerificationState.FAILED,
    }),
    LiveVerificationState.READONLY_PRECHECK: frozenset({
        LiveVerificationState.RISK_DECISION_CONFIRMED,
        LiveVerificationState.STOPPED,
        LiveVerificationState.FAILED,
    }),
    LiveVerificationState.RISK_DECISION_CONFIRMED: frozenset({
        LiveVerificationState.ORDER_INTENT_CREATED,
        LiveVerificationState.STOPPED,
        LiveVerificationState.FAILED,
    }),
    LiveVerificationState.ORDER_INTENT_CREATED: frozenset({
        LiveVerificationState.MANUAL_CONFIRMATION_REQUIRED,
        LiveVerificationState.STOPPED,
        LiveVerificationState.FAILED,
    }),
    LiveVerificationState.MANUAL_CONFIRMATION_REQUIRED: frozenset({
        LiveVerificationState.READY_FOR_ORDER_REVIEW,
        LiveVerificationState.STOPPED,
        LiveVerificationState.FAILED,
    }),
    LiveVerificationState.READY_FOR_ORDER_REVIEW: frozenset({
        LiveVerificationState.STOPPED,
        LiveVerificationState.FAILED,
    }),
    LiveVerificationState.STOPPED: frozenset(),
    LiveVerificationState.FAILED: frozenset(),
}

TERMINAL_STATES = frozenset({
    LiveVerificationState.STOPPED,
    LiveVerificationState.FAILED,
})


def transition_live_verification_state(
    current: LiveVerificationState | str,
    target: LiveVerificationState | str,
) -> LiveVerificationState:
    current_state = normalize_live_verification_state(current)
    target_state = normalize_live_verification_state(target)
    if current_state in TERMINAL_STATES:
        raise LiveVerificationStateError("terminal state cannot transition")
    if target_state not in ALLOWED_TRANSITIONS[current_state]:
        raise LiveVerificationStateError(
            f"invalid live verification transition: {current_state.value} -> {target_state.value}"
        )
    return target_state


def normalize_live_verification_state(value: LiveVerificationState | str) -> LiveVerificationState:
    if isinstance(value, LiveVerificationState):
        return value
    if isinstance(value, str):
        try:
            return LiveVerificationState(value)
        except ValueError as error:
            raise LiveVerificationStateError("unknown live verification state") from error
    raise LiveVerificationStateError("unknown live verification state")
