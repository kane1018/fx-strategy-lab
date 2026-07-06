"""No-POST tests for the GMO live kill switch policy.

Pure dataclass/logic tests: no network, no credentials, no `.env`, no
broker calls.
"""

from __future__ import annotations

import pytest

from app.services.gmo_live_safety_policy import (
    GmoLiveKillSwitchState,
    GmoLiveKillSwitchTrigger,
    evaluate_gmo_live_kill_switch,
)

_ARMED_STATE_KWARGS = {"process_start_default_off": False}


def test_process_start_defaults_to_blocked() -> None:
    decision = evaluate_gmo_live_kill_switch(GmoLiveKillSwitchState())
    assert decision.entry_allowed is False
    assert decision.settlement_allowed is False
    assert "process_start_default_off" in decision.triggered_reasons


def test_armed_state_with_no_other_trigger_allows_entry_and_settlement() -> None:
    decision = evaluate_gmo_live_kill_switch(
        GmoLiveKillSwitchState(**_ARMED_STATE_KWARGS)
    )
    assert decision.entry_allowed is True
    assert decision.settlement_allowed is True
    assert decision.triggered_reasons == ()


@pytest.mark.parametrize(
    "trigger",
    list(GmoLiveKillSwitchTrigger),
)
def test_every_trigger_blocks_entry_and_settlement(
    trigger: GmoLiveKillSwitchTrigger,
) -> None:
    kwargs = dict(_ARMED_STATE_KWARGS)
    kwargs[trigger.value] = True
    decision = evaluate_gmo_live_kill_switch(GmoLiveKillSwitchState(**kwargs))
    assert decision.entry_allowed is False
    assert decision.settlement_allowed is False
    assert trigger.value in decision.triggered_reasons


def test_manual_stop_blocks_even_when_armed() -> None:
    decision = evaluate_gmo_live_kill_switch(
        GmoLiveKillSwitchState(process_start_default_off=False, manual_stop_requested=True)
    )
    assert decision.entry_allowed is False
    assert decision.settlement_allowed is False


def test_stale_price_blocks() -> None:
    decision = evaluate_gmo_live_kill_switch(
        GmoLiveKillSwitchState(process_start_default_off=False, stale_price_detected=True)
    )
    assert decision.entry_allowed is False


def test_risk_service_rejected_blocks() -> None:
    decision = evaluate_gmo_live_kill_switch(
        GmoLiveKillSwitchState(process_start_default_off=False, risk_service_rejected=True)
    )
    assert decision.entry_allowed is False


def test_settlement_rejected_unknown_timeout_block_settlement() -> None:
    for flag in ("settlement_rejected", "settlement_unknown_or_timeout"):
        decision = evaluate_gmo_live_kill_switch(
            GmoLiveKillSwitchState(process_start_default_off=False, **{flag: True})
        )
        assert decision.settlement_allowed is False


def test_active_or_pending_conflict_blocks() -> None:
    decision = evaluate_gmo_live_kill_switch(
        GmoLiveKillSwitchState(
            process_start_default_off=False, active_or_pending_order_conflict=True,
        )
    )
    assert decision.entry_allowed is False


def test_multiple_positions_detected_blocks() -> None:
    decision = evaluate_gmo_live_kill_switch(
        GmoLiveKillSwitchState(process_start_default_off=False, multiple_positions_detected=True)
    )
    assert decision.entry_allowed is False
    assert decision.settlement_allowed is False


def test_max_entries_per_day_reached_blocks() -> None:
    decision = evaluate_gmo_live_kill_switch(
        GmoLiveKillSwitchState(process_start_default_off=False, max_entries_per_day_reached=True)
    )
    assert decision.entry_allowed is False


def test_max_settlements_per_position_reached_blocks() -> None:
    decision = evaluate_gmo_live_kill_switch(
        GmoLiveKillSwitchState(
            process_start_default_off=False,
            max_settlements_per_position_reached=True,
        )
    )
    assert decision.settlement_allowed is False


def test_generic_close_attempt_detected_blocks_everything() -> None:
    decision = evaluate_gmo_live_kill_switch(
        GmoLiveKillSwitchState(
            process_start_default_off=False, generic_close_attempt_detected=True,
        )
    )
    assert decision.entry_allowed is False
    assert decision.settlement_allowed is False


def test_retry_repost_generic_close_are_always_false() -> None:
    for state in (
        GmoLiveKillSwitchState(),
        GmoLiveKillSwitchState(**_ARMED_STATE_KWARGS),
        GmoLiveKillSwitchState(process_start_default_off=False, manual_stop_requested=True),
    ):
        decision = evaluate_gmo_live_kill_switch(state)
        assert decision.retry_allowed is False
        assert decision.repost_allowed is False
        assert decision.generic_close_allowed is False


def test_multiple_simultaneous_triggers_are_all_reported() -> None:
    decision = evaluate_gmo_live_kill_switch(
        GmoLiveKillSwitchState(
            process_start_default_off=False,
            stale_price_detected=True,
            risk_service_rejected=True,
        )
    )
    assert decision.entry_allowed is False
    assert "stale_price_detected" in decision.triggered_reasons
    assert "risk_service_rejected" in decision.triggered_reasons
