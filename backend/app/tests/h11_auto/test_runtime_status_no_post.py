from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.h11_auto.runtime_safety import (
    AutoRiskStopState,
    DeadManPolicy,
    DeadManStore,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
    record_risk_entry_attempt,
)
from app.h11_auto.runtime_status import project_runtime_safety_status

NOW = datetime(2026, 7, 15, 9, 0, tzinfo=UTC)


def _setup(
    tmp_path: Path,
) -> tuple[PhaseBRiskPolicy, PhaseBRiskStore, DeadManStore]:
    policy = PhaseBRiskPolicy(
        policy_label="STATUS_TEST",
        per_trade_loss_bound_jpy=500,
        daily_loss_limit_jpy=1_000,
        monthly_loss_limit_jpy=3_000,
        maximum_consecutive_losses=3,
    )
    return (
        policy,
        PhaseBRiskStore(tmp_path / "risk.json", policy=policy),
        DeadManStore(
            tmp_path / "dead-man.json",
            policy=DeadManPolicy("STATUS_DEAD_MAN", 60),
        ),
    )


def test_projection_is_safe_and_allows_fresh_active_state(tmp_path: Path) -> None:
    policy, risk_store, dead_man = _setup(tmp_path)
    dead_man.heartbeat(heartbeat_utc=NOW)
    projection = project_runtime_safety_status(
        risk_store=risk_store,
        risk_policy=policy,
        dead_man_store=dead_man,
        cycle_day_jst="2026-07-15",
        now_utc=NOW + timedelta(seconds=30),
    )
    assert projection.risk_stop_state == AutoRiskStopState.ACTIVE.value
    assert projection.entry_allowed_by_risk is True
    assert projection.dead_man_alive is True
    assert projection.halt_required is False
    assert projection.actual_post_allowed is False
    assert projection.broker_write_allowed is False
    assert "daily_loss_jpy_internal" not in projection.to_safe_dict()
    assert "monthly_loss_jpy_internal" not in projection.to_safe_dict()


def test_projection_halts_for_stopped_risk_or_stale_dead_man(tmp_path: Path) -> None:
    policy, risk_store, dead_man = _setup(tmp_path)
    state = risk_store.load()
    state.stop_state = AutoRiskStopState.KILLED.value
    state.stopped_on_jst = "2026-07-15"
    risk_store.save(state)
    dead_man.heartbeat(heartbeat_utc=NOW)
    projection = project_runtime_safety_status(
        risk_store=risk_store,
        risk_policy=policy,
        dead_man_store=dead_man,
        cycle_day_jst="2026-07-15",
        now_utc=NOW + timedelta(seconds=61),
    )
    assert projection.entry_allowed_by_risk is False
    assert projection.dead_man_alive is False
    assert projection.halt_required is True
    assert projection.dead_man_reason == "DEAD_MAN_HEARTBEAT_STALE"


def test_used_daily_entry_slot_blocks_entry_without_incident_halt(tmp_path: Path) -> None:
    policy, risk_store, dead_man = _setup(tmp_path)
    state = risk_store.load()
    record_risk_entry_attempt(
        state=state,
        policy=policy,
        cycle_day_jst="2026-07-15",
    )
    risk_store.save(state)
    dead_man.heartbeat(heartbeat_utc=NOW)
    projection = project_runtime_safety_status(
        risk_store=risk_store,
        risk_policy=policy,
        dead_man_store=dead_man,
        cycle_day_jst="2026-07-15",
        now_utc=NOW + timedelta(seconds=30),
    )
    assert projection.entry_allowed_by_risk is False
    assert projection.risk_blocked_reasons == ("MAX_ENTRIES_PER_DAY_REACHED",)
    assert projection.halt_required is False
