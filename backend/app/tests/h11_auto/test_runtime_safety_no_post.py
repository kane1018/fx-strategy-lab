from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.h11_auto.runtime_safety import (
    AutoRiskStopState,
    DeadManPolicy,
    DeadManStore,
    H11AutoRuntimeSafetyError,
    PhaseBRiskPolicy,
    PhaseBRiskState,
    PhaseBRiskStore,
    evaluate_risk_before_entry,
    record_closed_result,
    record_risk_entry_attempt,
)

NOW = datetime(2026, 7, 15, 8, 0, tzinfo=UTC)


def _policy(**overrides: int) -> PhaseBRiskPolicy:
    values: dict[str, object] = {
        "policy_label": "SYNTHETIC_PHASE_B_TEST",
        "per_trade_loss_bound_jpy": 500,
        "daily_loss_limit_jpy": 1_000,
        "monthly_loss_limit_jpy": 3_000,
        "maximum_consecutive_losses": 3,
        "maximum_entries_per_day": 1,
    }
    values.update(overrides)
    return PhaseBRiskPolicy(**values)  # type: ignore[arg-type]


def test_policy_requires_consistent_positive_limits_and_one_entry() -> None:
    with pytest.raises(H11AutoRuntimeSafetyError):
        _policy(maximum_entries_per_day=2)
    with pytest.raises(H11AutoRuntimeSafetyError):
        _policy(daily_loss_limit_jpy=4_000)


def test_entry_attempt_is_persistent_one_per_day_and_daily_rolls() -> None:
    policy = _policy()
    state = PhaseBRiskState(policy_digest=policy.digest)
    record_risk_entry_attempt(state=state, policy=policy, cycle_day_jst="2026-07-15")
    gate = evaluate_risk_before_entry(
        state=state, policy=policy, cycle_day_jst="2026-07-15"
    )
    assert gate.allowed is False
    assert "MAX_ENTRIES_PER_DAY_REACHED" in gate.blocked_reasons
    next_day = evaluate_risk_before_entry(
        state=state, policy=policy, cycle_day_jst="2026-07-16"
    )
    assert next_day.allowed is True
    assert state.entries_today == 0


def test_per_trade_bound_violation_kills_and_never_auto_resumes() -> None:
    policy = _policy()
    state = PhaseBRiskState(policy_digest=policy.digest)
    stop = record_closed_result(
        state=state,
        policy=policy,
        cycle_day_jst="2026-07-15",
        pnl_jpy_internal=-501,
    )
    assert stop is AutoRiskStopState.KILLED
    assert state.discipline_violation_count == 1
    gate = evaluate_risk_before_entry(
        state=state, policy=policy, cycle_day_jst="2026-08-01"
    )
    assert gate.allowed is False
    assert state.stop_state == AutoRiskStopState.KILLED.value


def test_daily_monthly_and_consecutive_stops_are_fail_closed() -> None:
    daily_policy = _policy(per_trade_loss_bound_jpy=1_000)
    daily = PhaseBRiskState(policy_digest=daily_policy.digest)
    assert (
        record_closed_result(
            state=daily,
            policy=daily_policy,
            cycle_day_jst="2026-07-15",
            pnl_jpy_internal=-1_000,
        )
        is AutoRiskStopState.STOPPED_DAILY_BUDGET
    )
    monthly_policy = _policy(
        per_trade_loss_bound_jpy=2_000,
        daily_loss_limit_jpy=2_000,
        monthly_loss_limit_jpy=3_000,
    )
    monthly = PhaseBRiskState(
        policy_digest=monthly_policy.digest,
        current_day_jst="2026-07-15",
        current_month_jst="2026-07",
        monthly_loss_jpy_internal=2_000,
    )
    assert (
        record_closed_result(
            state=monthly,
            policy=monthly_policy,
            cycle_day_jst="2026-07-15",
            pnl_jpy_internal=-1_000,
        )
        is AutoRiskStopState.STOPPED_MONTHLY_BUDGET
    )
    consecutive = PhaseBRiskState(policy_digest=daily_policy.digest)
    for _ in range(3):
        stop = record_closed_result(
            state=consecutive,
            policy=daily_policy,
            cycle_day_jst="2026-07-15",
            pnl_jpy_internal=-1,
        )
    assert stop is AutoRiskStopState.STOPPED_CONSECUTIVE_LOSSES


def test_risk_store_round_trip_and_policy_mismatch_fail_closed(tmp_path: Path) -> None:
    policy = _policy()
    store = PhaseBRiskStore(tmp_path / "risk.json", policy=policy)
    state = store.load()
    record_risk_entry_attempt(state=state, policy=policy, cycle_day_jst="2026-07-15")
    store.save(state)
    assert store.load().entries_today == 1
    with pytest.raises(H11AutoRuntimeSafetyError, match="policy"):
        PhaseBRiskStore(
            tmp_path / "risk.json",
            policy=_policy(daily_loss_limit_jpy=999),
        ).load()


def test_dead_man_missing_fresh_stale_future_and_corrupt(tmp_path: Path) -> None:
    policy = DeadManPolicy(
        policy_label="SYNTHETIC_DEAD_MAN",
        maximum_heartbeat_age_seconds=30,
    )
    path = tmp_path / "heartbeat.json"
    store = DeadManStore(path, policy=policy)
    assert store.evaluate(now_utc=NOW).reason_safe_label == "DEAD_MAN_HEARTBEAT_MISSING"
    store.heartbeat(heartbeat_utc=NOW)
    fresh = store.evaluate(now_utc=NOW + timedelta(seconds=30))
    assert fresh.alive is True
    assert fresh.halt_required is False
    assert fresh.actual_post_allowed is False
    stale = store.evaluate(now_utc=NOW + timedelta(seconds=31))
    assert stale.reason_safe_label == "DEAD_MAN_HEARTBEAT_STALE"
    future = store.evaluate(now_utc=NOW - timedelta(seconds=1))
    assert future.reason_safe_label == "DEAD_MAN_HEARTBEAT_FROM_FUTURE"
    path.write_text("not-json", encoding="utf-8")
    assert store.evaluate(now_utc=NOW).reason_safe_label == "DEAD_MAN_STATE_INVALID"


def test_dead_man_policy_mismatch_and_symlink_are_refused(tmp_path: Path) -> None:
    first = DeadManStore(
        tmp_path / "heartbeat.json",
        policy=DeadManPolicy("FIRST", 30),
    )
    first.heartbeat(heartbeat_utc=NOW)
    second = DeadManStore(
        tmp_path / "heartbeat.json",
        policy=DeadManPolicy("SECOND", 30),
    )
    assert second.evaluate(now_utc=NOW).reason_safe_label == "DEAD_MAN_STATE_INVALID"
    with pytest.raises(H11AutoRuntimeSafetyError, match="dead-man state"):
        second.heartbeat(heartbeat_utc=NOW + timedelta(seconds=1))
    with pytest.raises(H11AutoRuntimeSafetyError, match="backwards"):
        first.heartbeat(heartbeat_utc=NOW - timedelta(seconds=1))
    link = tmp_path / "heartbeat-link.json"
    link.symlink_to(tmp_path / "heartbeat.json")
    linked = DeadManStore(link, policy=DeadManPolicy("FIRST", 30))
    assert linked.evaluate(now_utc=NOW).reason_safe_label == "DEAD_MAN_HEARTBEAT_MISSING"


def test_existing_terminal_risk_stop_is_never_replaced_by_later_result() -> None:
    policy = _policy()
    state = PhaseBRiskState(
        policy_digest=policy.digest,
        stop_state=AutoRiskStopState.KILLED.value,
        current_day_jst="2026-07-15",
        current_month_jst="2026-07",
        stopped_on_jst="2026-07-15",
    )
    stop = record_closed_result(
        state=state,
        policy=policy,
        cycle_day_jst="2026-07-15",
        pnl_jpy_internal=-1,
    )
    assert stop is AutoRiskStopState.KILLED
    assert state.stop_state == AutoRiskStopState.KILLED.value


def test_risk_state_rejects_negative_or_boolean_counters(tmp_path: Path) -> None:
    policy = _policy()
    path = tmp_path / "risk.json"
    state = PhaseBRiskState(policy_digest=policy.digest)
    payload = state.__dict__.copy()
    payload["entries_today"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(H11AutoRuntimeSafetyError, match="counters"):
        PhaseBRiskStore(path, policy=policy).load()
