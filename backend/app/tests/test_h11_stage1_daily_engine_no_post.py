"""H-11 Stage 1 daily engine tests (no-POST, synthetic bars only)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from app.services.h11_stage1_daily_engine import (
    ENTRY_EVAL_SLOTS_JST,
    Stage1OpenPosition,
    entry_evaluation_gate,
    load_state,
    paper_pnl_jpy,
    save_state,
    session_from_state,
    settle_position,
    state_from_session,
)
from app.services.h11_stage1_paper_wiring import H11Stage1StopState

T0 = datetime(2026, 7, 14, 1, 0, tzinfo=UTC)


def _position(direction: str = "PAPER_LONG") -> Stage1OpenPosition:
    return Stage1OpenPosition(
        direction=direction,
        entry_time_utc=T0.isoformat(timespec="seconds"),
        entry_price=150.00,
        sl_price=149.70 if direction == "PAPER_LONG" else 150.30,
        tp_price=150.45 if direction == "PAPER_LONG" else 149.55,
        expiry_time_utc=(T0 + timedelta(hours=24)).isoformat(timespec="seconds"),
    )


def _bars(prices: list[tuple[float, float, float]]):
    times = [T0 + timedelta(hours=i + 1) for i in range(len(prices))]
    high = np.asarray([p[0] for p in prices])
    low = np.asarray([p[1] for p in prices])
    close = np.asarray([p[2] for p in prices])
    return times, high, low, close


def test_sl_exit_long_and_conservative_both_hit():
    times, high, low, close = _bars([(150.50, 149.60, 150.00)])  # both SL and TP touched
    route, price = settle_position(_position(), times, high, low, close)
    assert route == "PAPER_EXIT_SL"  # conservative resolution
    assert price == 149.70


def test_tp_exit_short():
    times, high, low, close = _bars([(150.10, 149.50, 149.60)])
    route, price = settle_position(_position("PAPER_SHORT"), times, high, low, close)
    assert route == "PAPER_EXIT_TP"
    assert price == 149.55


def test_timeout_exit_at_expiry_close():
    flat = [(150.10, 149.90, 150.05)] * 24  # never touches SL/TP
    times, high, low, close = _bars(flat)
    route, price = settle_position(_position(), times, high, low, close)
    assert route == "PAPER_EXIT_TIMEOUT"
    assert price == 150.05


def test_position_stays_open_before_any_trigger():
    times, high, low, close = _bars([(150.10, 149.90, 150.05)] * 3)
    assert settle_position(_position(), times, high, low, close) is None


def test_paper_pnl_includes_friction_both_sides():
    # LONG flat exit: friction 0.5 pip x 2 sides x 10,000 units = -100 JPY
    assert paper_pnl_jpy("PAPER_LONG", 150.00, 150.00) == -100
    assert paper_pnl_jpy("PAPER_SHORT", 150.00, 150.00) == -100
    # LONG +30 pips gross => 3,000 - 100 friction
    assert paper_pnl_jpy("PAPER_LONG", 150.00, 150.30) == 2900


def test_state_roundtrip_preserves_ledger(tmp_path: Path):
    path = tmp_path / "state.json"
    state = load_state(path, T0)
    session = session_from_state(state)
    session.record_paper_trade_outcome_jpy(-3_000, datetime(2026, 7, 14, 10, 0))
    state = state_from_session(state, session)
    save_state(path, state)

    reloaded = load_state(path, T0)
    session2 = session_from_state(reloaded)
    assert session2._consecutive_losses == 1
    assert session2._daily_loss_jpy == 3_000
    assert session2.stop_state is H11Stage1StopState.ACTIVE
    # continue the streak across the "restart"
    for i in range(4):
        state2 = session2.record_paper_trade_outcome_jpy(
            -1_000, datetime(2026, 7, 15 + i, 10, 0)
        )
    assert state2 is H11Stage1StopState.STOPPED_CONSECUTIVE_LOSSES


def test_entry_evaluation_gate_slots_and_duplicates():
    bar = "2026-07-14T06:00:00+00:00"
    # In-slot (16 JST), fresh bar -> proceed
    assert entry_evaluation_gate(datetime(2026, 7, 14, 16, 5), None, bar) == ""
    # In-slot but the same bar was already evaluated -> skip
    assert (
        entry_evaluation_gate(datetime(2026, 7, 14, 16, 40), bar, bar)
        == "BAR_ALREADY_EVALUATED"
    )
    # In-slot, a NEW bar since the last evaluation -> proceed again
    next_bar = "2026-07-14T07:00:00+00:00"
    assert entry_evaluation_gate(datetime(2026, 7, 14, 16, 40), bar, next_bar) == ""
    # Off-schedule hours -> skip regardless of bar freshness
    for hour in (9, 12, 15, 23, 0, 3):
        assert (
            entry_evaluation_gate(datetime(2026, 7, 14, hour, 0), None, bar)
            == "OFF_SCHEDULE_RUN"
        )
    # All three configured slots are honored
    for hour in ENTRY_EVAL_SLOTS_JST:
        assert entry_evaluation_gate(datetime(2026, 7, 14, hour, 59), None, bar) == ""


def test_state_backwards_compatible_without_last_eval_field(tmp_path: Path):
    # A pre-amendment state file (no last_entry_eval_bar_utc key) must load.
    legacy = {
        "stage1_started_at_utc": "2026-07-10T21:19:18+00:00",
        "stop_state": "ACTIVE",
        "kill_switch_on": False,
        "stopped_at_utc": None,
        "monthly_loss_jpy": 0,
        "daily_loss_jpy": 0,
        "consecutive_losses": 0,
        "trades_today": 0,
        "current_day": "2026-7-14",
        "current_month": "2026-7",
        "closed_trades": 0,
        "discipline_violations": [],
        "open_position": None,
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(legacy))
    state = load_state(path, T0)
    assert state.last_entry_eval_bar_utc is None
    state.last_entry_eval_bar_utc = "2026-07-14T06:00:00+00:00"
    save_state(path, state)
    assert load_state(path, T0).last_entry_eval_bar_utc == "2026-07-14T06:00:00+00:00"
