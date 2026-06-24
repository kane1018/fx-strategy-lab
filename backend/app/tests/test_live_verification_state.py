from __future__ import annotations

import pytest

from app.live_verification.errors import LiveVerificationStateError
from app.live_verification.state import (
    LiveVerificationState,
    transition_live_verification_state,
)


def test_state_happy_path_reaches_ready_for_review_only() -> None:
    state = LiveVerificationState.INIT
    state = transition_live_verification_state(state, LiveVerificationState.READONLY_PRECHECK)
    state = transition_live_verification_state(
        state, LiveVerificationState.RISK_DECISION_CONFIRMED
    )
    state = transition_live_verification_state(state, LiveVerificationState.ORDER_INTENT_CREATED)
    state = transition_live_verification_state(
        state, LiveVerificationState.MANUAL_CONFIRMATION_REQUIRED
    )
    state = transition_live_verification_state(
        state, LiveVerificationState.READY_FOR_ORDER_REVIEW
    )

    assert state is LiveVerificationState.READY_FOR_ORDER_REVIEW


def test_invalid_transition_raises() -> None:
    with pytest.raises(LiveVerificationStateError):
        transition_live_verification_state(
            LiveVerificationState.INIT,
            LiveVerificationState.ORDER_INTENT_CREATED,
        )


@pytest.mark.parametrize(
    "terminal_state",
    [LiveVerificationState.STOPPED, LiveVerificationState.FAILED],
)
def test_stopped_and_failed_do_not_transition(terminal_state: LiveVerificationState) -> None:
    with pytest.raises(LiveVerificationStateError):
        transition_live_verification_state(
            terminal_state,
            LiveVerificationState.READY_FOR_ORDER_REVIEW,
        )


def test_ready_for_review_can_only_stop_or_fail() -> None:
    assert (
        transition_live_verification_state(
            LiveVerificationState.READY_FOR_ORDER_REVIEW,
            LiveVerificationState.STOPPED,
        )
        is LiveVerificationState.STOPPED
    )
    with pytest.raises(LiveVerificationStateError):
        transition_live_verification_state(
            LiveVerificationState.READY_FOR_ORDER_REVIEW,
            LiveVerificationState.READONLY_PRECHECK,
        )


def test_order_transmission_states_do_not_exist() -> None:
    state_values = {state.value for state in LiveVerificationState}
    blocked_values = {
        "ORDER" "_SENT",
        "BROKER" "_SUBMIT",
        "PRIVATE" "_ORDER_API",
        "LIVE" "_ORDER_PLACED",
    }

    assert state_values.isdisjoint(blocked_values)


def test_unknown_state_raises() -> None:
    with pytest.raises(LiveVerificationStateError):
        transition_live_verification_state("UNKNOWN", LiveVerificationState.STOPPED)
