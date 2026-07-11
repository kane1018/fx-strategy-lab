"""H-11 Stage 1 wiring firing tests (no-POST, fake transports only).

Covers the ACTIVE-policy Stage 1 promotion requirement: at least one
successful firing test per budget / stop-criteria path.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.gmo_paper_auto_cycle_runner import (
    GmoPaperAutoCycleStatus,
    build_all_safe_paper_scenario_input,
)
from app.services.h11_stage1_paper_wiring import (
    DAILY_MAX_LOSS_JPY,
    MAX_CONSECUTIVE_LOSSES_STOP,
    MONTHLY_MAX_LOSS_JPY,
    PER_TRADE_MAX_LOSS_BOUND_JPY,
    H11Stage1BlockReason,
    H11Stage1CycleStatus,
    H11Stage1Session,
    H11Stage1StopState,
)
from app.strategies.h11_regime_moe import (
    H11_V2_CONFIG_HASH,
    H11Prediction,
    H11PredictionStatus,
)

TUESDAY_10AM = datetime(2026, 7, 14, 10, 0)  # Tue 10:00 JST (allowed hours)


def _v2_prediction(p_up: float = 0.65) -> H11Prediction:
    return H11Prediction(
        p_up=p_up,
        p_down=1.0 - p_up,
        expert_probabilities=(p_up,),
        expert_weights=(1.0,),
        model_uncertainty=0.0,
        prediction_status=H11PredictionStatus.OK,
        config_hash=H11_V2_CONFIG_HASH,
    )


def _run(session: H11Stage1Session, *, now=TUESDAY_10AM, p_up=0.65, event=False):
    return session.run_stage1_cycle_once(
        prediction=_v2_prediction(p_up),
        now_jst=now,
        event_exclusion_active=event,
        scenario=build_all_safe_paper_scenario_input(),
    )


def test_full_cycle_runs_and_counts_trade():
    session = H11Stage1Session()
    result = _run(session)
    assert result.status is H11Stage1CycleStatus.CYCLE_RAN
    assert (
        result.paper_cycle_result.status
        is GmoPaperAutoCycleStatus.PAPER_CYCLE_COMPLETE
    )
    assert result.execution_permission is False
    assert result.actual_entry_POST_allowed is False
    assert bool(result) is False


def test_max_trades_per_day_fires():
    session = H11Stage1Session()
    assert _run(session).status is H11Stage1CycleStatus.CYCLE_RAN
    second = _run(session, now=TUESDAY_10AM + timedelta(hours=1))
    assert second.status is H11Stage1CycleStatus.BLOCKED_PRE_CYCLE
    assert H11Stage1BlockReason.MAX_TRADES_PER_DAY_REACHED.value in second.blocked_reasons
    # next day resets
    next_day = _run(session, now=TUESDAY_10AM + timedelta(days=1))
    assert next_day.status is H11Stage1CycleStatus.CYCLE_RAN


def test_daily_budget_stop_fires_and_expires_next_day():
    session = H11Stage1Session()
    state = session.record_paper_trade_outcome_jpy(-DAILY_MAX_LOSS_JPY, TUESDAY_10AM)
    assert state is H11Stage1StopState.STOPPED_DAILY_BUDGET
    blocked = _run(session, now=TUESDAY_10AM + timedelta(hours=1))
    assert H11Stage1BlockReason.SESSION_STOPPED.value in blocked.blocked_reasons
    assert _run(session, now=TUESDAY_10AM + timedelta(days=1)).status is (
        H11Stage1CycleStatus.CYCLE_RAN
    )


def test_monthly_budget_stop_fires_and_same_month_reload_refused():
    session = H11Stage1Session()
    day = TUESDAY_10AM + timedelta(days=7)  # start 2026-07-21
    for _ in range(5):  # 5 days x 10,000 = monthly cap -> stop at 2026-07-25
        session.record_paper_trade_outcome_jpy(-DAILY_MAX_LOSS_JPY, day)
        day += timedelta(days=1)
    assert session.stop_state is H11Stage1StopState.STOPPED_MONTHLY_BUDGET
    # monthly stop does not expire with the day
    assert H11Stage1BlockReason.SESSION_STOPPED.value in _run(
        session, now=day + timedelta(days=1)
    ).blocked_reasons
    # same-month reload refused by code
    assert session.operator_reload(day + timedelta(days=1)) is False
    # next month but inside the 14-day cooling window (7 days): still refused
    assert session.operator_reload(datetime(2026, 8, 1, 10, 0)) is False
    # next month and cooled >= 14 days: accepted
    assert session.operator_reload(datetime(2026, 8, 10, 10, 0)) is True
    assert session.stop_state is H11Stage1StopState.ACTIVE


def test_monthly_loss_figure_survives_month_rollover_while_stopped():
    """The post-mortem evidence must not be erased by a calendar month change."""

    session = H11Stage1Session()
    day = TUESDAY_10AM + timedelta(days=7)
    for _ in range(5):
        session.record_paper_trade_outcome_jpy(-DAILY_MAX_LOSS_JPY, day)
        day += timedelta(days=1)
    assert session.stop_state is H11Stage1StopState.STOPPED_MONTHLY_BUDGET
    lost_at_stop = session._monthly_loss_jpy
    assert lost_at_stop >= MONTHLY_MAX_LOSS_JPY

    # Cross into next month without ever calling operator_reload.
    _run(session, now=datetime(2026, 8, 1, 10, 0))
    assert session.stop_state is H11Stage1StopState.STOPPED_MONTHLY_BUDGET
    assert session._monthly_loss_jpy == lost_at_stop  # preserved, not zeroed

    # Once reloaded, the figure is intentionally cleared.
    assert session.operator_reload(datetime(2026, 8, 10, 10, 0)) is True
    assert session._monthly_loss_jpy == 0


def test_consecutive_loss_stop_fires():
    session = H11Stage1Session()
    for i in range(MAX_CONSECUTIVE_LOSSES_STOP):
        state = session.record_paper_trade_outcome_jpy(
            -1_000, TUESDAY_10AM + timedelta(days=i)
        )
    assert state is H11Stage1StopState.STOPPED_CONSECUTIVE_LOSSES
    # a win before the fifth loss resets the streak
    fresh = H11Stage1Session()
    for i in range(MAX_CONSECUTIVE_LOSSES_STOP - 1):
        fresh.record_paper_trade_outcome_jpy(-1_000, TUESDAY_10AM + timedelta(days=i))
    fresh.record_paper_trade_outcome_jpy(500, TUESDAY_10AM + timedelta(days=4))
    assert fresh.stop_state is H11Stage1StopState.ACTIVE


def test_per_trade_bound_violation_recorded():
    session = H11Stage1Session()
    session.record_paper_trade_outcome_jpy(
        -(PER_TRADE_MAX_LOSS_BOUND_JPY + 1), TUESDAY_10AM
    )
    assert "PER_TRADE_LOSS_BOUND_EXCEEDED" in session.discipline_violation_log


def test_trading_hours_and_calendar_gates():
    session = H11Stage1Session()
    early = _run(session, now=datetime(2026, 7, 14, 6, 0))  # 6:00 JST blocked
    assert H11Stage1BlockReason.OUTSIDE_TRADING_HOURS.value in early.blocked_reasons
    friday_late = _run(session, now=datetime(2026, 7, 17, 21, 30))  # Fri 21:30
    assert (
        H11Stage1BlockReason.FRIDAY_LATE_ENTRY_BLOCKED.value
        in friday_late.blocked_reasons
    )
    saturday = _run(session, now=datetime(2026, 7, 18, 10, 0))
    assert H11Stage1BlockReason.WEEKEND_BLOCKED.value in saturday.blocked_reasons
    event = _run(session, event=True)
    assert H11Stage1BlockReason.EVENT_EXCLUSION_WINDOW.value in event.blocked_reasons


def test_kill_switch_blocks_and_does_not_settle():
    session = H11Stage1Session()
    session.engage_kill_switch()
    result = _run(session)
    assert result.status is H11Stage1CycleStatus.BLOCKED_PRE_CYCLE
    assert H11Stage1BlockReason.KILL_SWITCH_ON.value in result.blocked_reasons
    assert result.paper_cycle_result is None  # no auto-close / no settlement fired
    assert session.operator_reload(TUESDAY_10AM + timedelta(days=60)) is False


def test_hold_band_and_blocked_prediction_produce_no_order():
    session = H11Stage1Session()
    hold = _run(session, p_up=0.50)
    assert hold.status is H11Stage1CycleStatus.NO_ORDER_HOLD
    assert hold.paper_cycle_result is None

    blocked_prediction = H11Prediction(
        p_up=None,
        p_down=None,
        expert_probabilities=None,
        expert_weights=None,
        model_uncertainty=None,
        prediction_status=H11PredictionStatus.BLOCKED,
        block_reasons=("MODEL_NOT_TRAINED",),
        config_hash=H11_V2_CONFIG_HASH,
    )
    result = session.run_stage1_cycle_once(
        prediction=blocked_prediction,
        now_jst=TUESDAY_10AM,
        event_exclusion_active=False,
        scenario=build_all_safe_paper_scenario_input(),
    )
    assert result.status is H11Stage1CycleStatus.NO_ORDER_UNKNOWN_BLOCKED


def test_v1_hash_prediction_is_blocked_by_version_pinning():
    session = H11Stage1Session()
    v1_pred = H11Prediction(
        p_up=0.9,
        p_down=0.1,
        expert_probabilities=(0.9, 0.9, 0.9),
        expert_weights=(1 / 3, 1 / 3, 1 / 3),
        model_uncertainty=0.0,
        prediction_status=H11PredictionStatus.OK,
    )  # default config_hash = v1
    result = session.run_stage1_cycle_once(
        prediction=v1_pred,
        now_jst=TUESDAY_10AM,
        event_exclusion_active=False,
        scenario=build_all_safe_paper_scenario_input(),
    )
    assert result.status is H11Stage1CycleStatus.NO_ORDER_UNKNOWN_BLOCKED


def test_frozen_constants_match_operator_approved_budget():
    assert MONTHLY_MAX_LOSS_JPY == 50_000
    assert DAILY_MAX_LOSS_JPY == 10_000
    assert PER_TRADE_MAX_LOSS_BOUND_JPY == 5_000
    assert MAX_CONSECUTIVE_LOSSES_STOP == 5
