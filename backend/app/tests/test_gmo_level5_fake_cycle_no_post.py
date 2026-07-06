"""No-POST tests for the fake Level 5 full auto cycle simulation.

This never calls GmoFxBroker, order_builders, or the hard guard -- it is a
pure state-machine simulation over synthetic safe-label/safe-boolean
fixtures, because GmoFxBroker's real transport is deliberately not
implemented yet (see gmo_level5_fake_cycle.py's module docstring).
"""

from __future__ import annotations

import pathlib

import pytest

from app.services.gmo_level5_fake_cycle import (
    GmoLevel5FakeCycleInput,
    GmoLevel5PositionStatus,
    GmoLevel5ResultCategory,
    simulate_gmo_level5_fake_cycle,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "services" / "gmo_level5_fake_cycle.py"
)

ACCEPTED = GmoLevel5ResultCategory.ACCEPTED_SANITIZED.value
REJECTED = GmoLevel5ResultCategory.REJECTED_SANITIZED.value
UNKNOWN = GmoLevel5ResultCategory.UNKNOWN_SANITIZED.value

ONE_OPEN = GmoLevel5PositionStatus.ONE_POSITION_OPEN.value
NO_POSITION = GmoLevel5PositionStatus.NO_POSITION.value
MULTIPLE = GmoLevel5PositionStatus.MULTIPLE_POSITIONS.value
UNKNOWN_POSITION = GmoLevel5PositionStatus.UNKNOWN.value


def _successful_cycle_kwargs() -> dict[str, object]:
    return {
        "entry_signal_safe_label_present": True,
        "entry_result_category": ACCEPTED,
        "post_entry_position_status": ONE_OPEN,
        "settlement_result_category": ACCEPTED,
        "post_settlement_position_status": NO_POSITION,
    }


def test_fully_successful_cycle_completes_level5() -> None:
    result = simulate_gmo_level5_fake_cycle(
        GmoLevel5FakeCycleInput(**_successful_cycle_kwargs())
    )
    assert result.level5_full_auto_cycle_completed is True
    assert result.blocked_reasons == ()


def test_missing_entry_signal_blocks_level5() -> None:
    kwargs = _successful_cycle_kwargs()
    kwargs["entry_signal_safe_label_present"] = False
    result = simulate_gmo_level5_fake_cycle(GmoLevel5FakeCycleInput(**kwargs))
    assert result.level5_full_auto_cycle_completed is False
    assert "entry_signal_missing" in result.blocked_reasons


@pytest.mark.parametrize("entry_result", [REJECTED, UNKNOWN])
def test_entry_not_accepted_blocks_level5(entry_result: str) -> None:
    kwargs = _successful_cycle_kwargs()
    kwargs["entry_result_category"] = entry_result
    result = simulate_gmo_level5_fake_cycle(GmoLevel5FakeCycleInput(**kwargs))
    assert result.level5_full_auto_cycle_completed is False
    assert "entry_not_accepted" in result.blocked_reasons


@pytest.mark.parametrize("position_status", [NO_POSITION, MULTIPLE, UNKNOWN_POSITION])
def test_post_entry_position_not_confirmed_blocks_level5(position_status: str) -> None:
    kwargs = _successful_cycle_kwargs()
    kwargs["post_entry_position_status"] = position_status
    result = simulate_gmo_level5_fake_cycle(GmoLevel5FakeCycleInput(**kwargs))
    assert result.level5_full_auto_cycle_completed is False
    assert "post_entry_position_not_confirmed" in result.blocked_reasons


@pytest.mark.parametrize("settlement_result", [REJECTED, UNKNOWN])
def test_settlement_not_accepted_blocks_level5(settlement_result: str) -> None:
    kwargs = _successful_cycle_kwargs()
    kwargs["settlement_result_category"] = settlement_result
    result = simulate_gmo_level5_fake_cycle(GmoLevel5FakeCycleInput(**kwargs))
    assert result.level5_full_auto_cycle_completed is False
    assert "settlement_not_accepted" in result.blocked_reasons


@pytest.mark.parametrize("position_status", [ONE_OPEN, MULTIPLE, UNKNOWN_POSITION])
def test_post_settlement_position_not_confirmed_blocks_level5(position_status: str) -> None:
    kwargs = _successful_cycle_kwargs()
    kwargs["post_settlement_position_status"] = position_status
    result = simulate_gmo_level5_fake_cycle(GmoLevel5FakeCycleInput(**kwargs))
    assert result.level5_full_auto_cycle_completed is False
    assert "post_settlement_position_not_confirmed" in result.blocked_reasons


def test_manual_intervention_blocks_level5_even_if_otherwise_successful() -> None:
    kwargs = _successful_cycle_kwargs()
    kwargs["manual_intervention_performed"] = True
    result = simulate_gmo_level5_fake_cycle(GmoLevel5FakeCycleInput(**kwargs))
    assert result.level5_full_auto_cycle_completed is False
    assert "manual_intervention_performed" in result.blocked_reasons


@pytest.mark.parametrize(
    "flag",
    ["retry_attempted", "repost_attempted", "generic_close_attempted"],
)
def test_retry_repost_or_generic_close_blocks_level5(flag: str) -> None:
    kwargs = _successful_cycle_kwargs()
    kwargs[flag] = True
    result = simulate_gmo_level5_fake_cycle(GmoLevel5FakeCycleInput(**kwargs))
    assert result.level5_full_auto_cycle_completed is False
    assert f"{flag}" in result.blocked_reasons


def test_kill_switch_triggered_during_cycle_blocks_level5() -> None:
    kwargs = _successful_cycle_kwargs()
    kwargs["kill_switch_triggered_during_cycle"] = True
    result = simulate_gmo_level5_fake_cycle(GmoLevel5FakeCycleInput(**kwargs))
    assert result.level5_full_auto_cycle_completed is False
    assert "kill_switch_triggered_during_cycle" in result.blocked_reasons


def test_multiple_failures_all_reported() -> None:
    kwargs = _successful_cycle_kwargs()
    kwargs["entry_result_category"] = REJECTED
    kwargs["retry_attempted"] = True
    result = simulate_gmo_level5_fake_cycle(GmoLevel5FakeCycleInput(**kwargs))
    assert result.level5_full_auto_cycle_completed is False
    assert "entry_not_accepted" in result.blocked_reasons
    assert "retry_attempted" in result.blocked_reasons


def test_module_never_calls_broker_or_order_builders() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "GmoFxBroker" not in text
    assert "order_builders" not in text
    assert "real_broker_post_hard_guard" not in text
    assert "httpx" not in text


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text
