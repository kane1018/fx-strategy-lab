from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.h11_auto.boundary import FakeNotifier, NotificationCategory
from app.h11_auto.contracts import (
    FormalHorizon,
    FormalSignal,
    H11AutoContractError,
    PhaseAExecutionPolicy,
    SignalDecision,
)
from app.h11_auto.paper_runner import (
    BoundedPaperRunConfig,
    BoundedPaperRunStatus,
    H11AutoPaperRunnerError,
    load_sanitized_formal_signal_jsonl,
    run_bounded_paper_signals_no_post,
)
from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import (
    AutoRiskStopState,
    DeadManPolicy,
    DeadManStore,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
)

NOW = datetime(2026, 7, 15, 4, 0, tzinfo=UTC)
GENERATION_LABEL = "SYNTHETIC_PHASE_B_TEST_GENERATION"


def _policy() -> PhaseAExecutionPolicy:
    return PhaseAExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:phase-b-paper-test",
        selected_horizon=FormalHorizon.MINUTES_10,
    )


def _signal(decision: SignalDecision) -> FormalSignal:
    return FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:phase-b-paper-test",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=NOW,
        valid_until_utc=NOW + timedelta(minutes=10),
        decision=decision,
        probability_up=Decimal("0.61"),
    )


def _runtime(
    tmp_path: Path,
) -> tuple[PhaseBRiskStore, PhaseBRiskPolicy, DeadManStore]:
    risk_policy = PhaseBRiskPolicy(
        policy_label="SYNTHETIC_RUNNER_TEST",
        per_trade_loss_bound_jpy=500,
        daily_loss_limit_jpy=1_000,
        monthly_loss_limit_jpy=3_000,
        maximum_consecutive_losses=3,
    )
    return (
        PhaseBRiskStore(tmp_path / "risk.json", policy=risk_policy),
        risk_policy,
        DeadManStore(
            tmp_path / "dead-man.json",
            policy=DeadManPolicy("SYNTHETIC_RUNNER_DEAD_MAN", 60),
        ),
    )


def test_bounded_runner_stops_on_protected_position_without_implicit_exit(
    tmp_path: Path,
) -> None:
    risk_store, risk_policy, dead_man = _runtime(tmp_path)
    report = run_bounded_paper_signals_no_post(
        signals=(_signal(SignalDecision.STAY), _signal(SignalDecision.BUY)),
        policy=_policy(),
        state_path=tmp_path / "state.sqlite3",
        lock_path=tmp_path / "auto.lock",
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        notifier=FakeNotifier(),
        generation_label=GENERATION_LABEL,
        config=BoundedPaperRunConfig(),
        now_provider=lambda: NOW + timedelta(minutes=1),
        monotonic_provider=lambda: 1.0,
    )
    assert report.status is BoundedPaperRunStatus.POSITION_PROTECTED_STOPPED
    assert report.input_records_seen == 2
    assert report.stay_records == 1
    assert report.entry_attempts == 1
    assert report.exit_attempts == 0
    assert report.protected_positions == 1
    assert report.actual_post_count == 0
    assert report.broker_read_performed is False
    assert report.broker_write_performed is False
    assert report.network_access_performed is False
    assert report.credential_read_performed is False
    assert report.resident_process is False
    assert report.cron is False
    assert report.runtime_safety_bound is True
    assert report.risk_stop_state == "ACTIVE"
    assert report.dead_man_alive is True
    assert report.notification_heartbeat_count == 2
    assert report.external_notification_send_performed is False
    assert risk_store.load().entries_today == 1


def test_synthetic_auto_flat_is_explicit_and_still_one_attempt_each(
    tmp_path: Path,
) -> None:
    risk_store, risk_policy, dead_man = _runtime(tmp_path)
    report = run_bounded_paper_signals_no_post(
        signals=(_signal(SignalDecision.BUY),),
        policy=_policy(),
        state_path=tmp_path / "state.sqlite3",
        lock_path=tmp_path / "auto.lock",
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        notifier=FakeNotifier(),
        generation_label=GENERATION_LABEL,
        config=BoundedPaperRunConfig(synthetic_auto_flat=True),
        now_provider=lambda: NOW + timedelta(minutes=1),
        monotonic_provider=lambda: 1.0,
    )
    assert report.status is BoundedPaperRunStatus.COMPLETED_FAKE_ONLY
    assert report.entry_attempts == 1
    assert report.exit_attempts == 1
    assert report.flat_reconciliations == 1
    assert report.journal_valid is True


def test_runner_refuses_second_process_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "auto.lock"
    first = H11AutoProcessLock(lock_path)
    assert first.acquire() is True
    risk_store, risk_policy, dead_man = _runtime(tmp_path)
    try:
        with pytest.raises(H11AutoPaperRunnerError, match="already held"):
            run_bounded_paper_signals_no_post(
                signals=(_signal(SignalDecision.STAY),),
                policy=_policy(),
                state_path=tmp_path / "state.sqlite3",
                lock_path=lock_path,
                risk_store=risk_store,
                risk_policy=risk_policy,
                dead_man_store=dead_man,
                notifier=FakeNotifier(),
                generation_label=GENERATION_LABEL,
                now_provider=lambda: NOW,
            )
    finally:
        first.release()


def test_runner_refuses_shared_state_and_lock_path(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    risk_store, risk_policy, dead_man = _runtime(tmp_path)
    with pytest.raises(H11AutoPaperRunnerError, match="separate"):
        run_bounded_paper_signals_no_post(
            signals=(_signal(SignalDecision.STAY),),
            policy=_policy(),
            state_path=shared,
            lock_path=shared,
            risk_store=risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man,
            notifier=FakeNotifier(),
            generation_label=GENERATION_LABEL,
            now_provider=lambda: NOW,
        )


def test_local_jsonl_loader_is_bounded_and_rejects_symlink(tmp_path: Path) -> None:
    payload = {
        "horizon": "10m",
        "direction": "BUY",
        "status": "OK",
        "p_up": 0.61,
        "origin_time_utc": NOW.isoformat(),
        "model_config_hash": "sha256:phase-b-paper-test",
        "recorded_mode": "PROSPECTIVE",
    }
    source = tmp_path / "signals.jsonl"
    source.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    signals = load_sanitized_formal_signal_jsonl(
        source, strategy_version="SHORT_V1", maximum_records=1
    )
    assert len(signals) == 1
    link = tmp_path / "signals-link.jsonl"
    link.symlink_to(source)
    with pytest.raises(H11AutoPaperRunnerError, match="non-symlink"):
        load_sanitized_formal_signal_jsonl(
            link, strategy_version="SHORT_V1", maximum_records=1
        )


def test_local_jsonl_loader_rejects_unsafe_fields_and_oversized_lines(
    tmp_path: Path,
) -> None:
    unsafe = {
        "horizon": "10m",
        "direction": "BUY",
        "status": "OK",
        "p_up": 0.61,
        "origin_time_utc": NOW.isoformat(),
        "model_config_hash": "sha256:phase-b-paper-test",
        "recorded_mode": "PROSPECTIVE",
        "raw_response": "forbidden",
    }
    unsafe_path = tmp_path / "unsafe.jsonl"
    unsafe_path.write_text(json.dumps(unsafe) + "\n", encoding="utf-8")
    with pytest.raises(H11AutoContractError, match="unsafe fields"):
        load_sanitized_formal_signal_jsonl(
            unsafe_path,
            strategy_version="SHORT_V1",
            maximum_records=1,
        )

    oversized = tmp_path / "oversized.jsonl"
    oversized.write_text(" " * 65_537 + "\n", encoding="utf-8")
    with pytest.raises(H11AutoPaperRunnerError, match="too large"):
        load_sanitized_formal_signal_jsonl(
            oversized,
            strategy_version="SHORT_V1",
            maximum_records=1,
        )


def test_bounded_config_refuses_boolean_and_non_finite_limits() -> None:
    with pytest.raises(H11AutoPaperRunnerError):
        BoundedPaperRunConfig(maximum_signal_records=True)  # type: ignore[arg-type]
    with pytest.raises(H11AutoPaperRunnerError):
        BoundedPaperRunConfig(maximum_wall_seconds=float("nan"))


def test_runner_enforces_record_and_wall_clock_bounds(tmp_path: Path) -> None:
    times = iter((0.0, 2.0))
    risk_store, risk_policy, dead_man = _runtime(tmp_path)
    report = run_bounded_paper_signals_no_post(
        signals=(_signal(SignalDecision.STAY),),
        policy=_policy(),
        state_path=tmp_path / "state.sqlite3",
        lock_path=tmp_path / "auto.lock",
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        notifier=FakeNotifier(),
        generation_label=GENERATION_LABEL,
        config=BoundedPaperRunConfig(maximum_wall_seconds=1.0),
        now_provider=lambda: NOW,
        monotonic_provider=lambda: next(times),
    )
    assert report.status is BoundedPaperRunStatus.BOUNDED_LIMIT_REACHED
    assert report.input_records_seen == 0


def test_persistent_risk_stop_blocks_before_engine_attempt(tmp_path: Path) -> None:
    risk_store, risk_policy, dead_man = _runtime(tmp_path)
    state = risk_store.load()
    state.stop_state = AutoRiskStopState.KILLED.value
    state.stopped_on_jst = "2026-07-15"
    risk_store.save(state)
    report = run_bounded_paper_signals_no_post(
        signals=(_signal(SignalDecision.BUY),),
        policy=_policy(),
        state_path=tmp_path / "state.sqlite3",
        lock_path=tmp_path / "auto.lock",
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        notifier=FakeNotifier(),
        generation_label=GENERATION_LABEL,
        now_provider=lambda: NOW + timedelta(minutes=1),
        monotonic_provider=lambda: 1.0,
    )
    assert report.status is BoundedPaperRunStatus.HALTED_SAFE
    assert report.blocked_records == 1
    assert report.halt_count == 1
    assert report.entry_attempts == 0
    assert report.risk_stop_state == AutoRiskStopState.KILLED.value


def test_fake_notification_failure_halts_before_entry_attempt(tmp_path: Path) -> None:
    risk_store, risk_policy, dead_man = _runtime(tmp_path)
    notifier = FakeNotifier(fail=True)
    report = run_bounded_paper_signals_no_post(
        signals=(_signal(SignalDecision.BUY),),
        policy=_policy(),
        state_path=tmp_path / "state.sqlite3",
        lock_path=tmp_path / "auto.lock",
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        notifier=notifier,
        generation_label=GENERATION_LABEL,
        now_provider=lambda: NOW + timedelta(minutes=1),
        monotonic_provider=lambda: 1.0,
    )
    assert report.status is BoundedPaperRunStatus.HALTED_SAFE
    assert report.input_records_seen == 1
    assert report.halt_count == 1
    assert report.entry_attempts == 0
    assert report.notification_heartbeat_count == 1
    assert notifier.events == [NotificationCategory.HEARTBEAT]
    assert report.external_notification_send_performed is False
    assert risk_store.load().entries_today == 0


def test_runner_refuses_subclassed_fake_notifier(tmp_path: Path) -> None:
    class NotifierSubclass(FakeNotifier):
        pass

    risk_store, risk_policy, dead_man = _runtime(tmp_path)
    with pytest.raises(H11AutoPaperRunnerError, match="fake-only"):
        run_bounded_paper_signals_no_post(
            signals=(_signal(SignalDecision.STAY),),
            policy=_policy(),
            state_path=tmp_path / "state.sqlite3",
            lock_path=tmp_path / "auto.lock",
            risk_store=risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man,
            notifier=NotifierSubclass(),
            generation_label=GENERATION_LABEL,
            now_provider=lambda: NOW,
            monotonic_provider=lambda: 1.0,
        )
