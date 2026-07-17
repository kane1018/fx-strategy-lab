from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.h11_auto.boundary import FakeNotifier
from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.runtime_safety import (
    DeadManPolicy,
    DeadManStore,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
)
from app.h11_auto.v4_gmo_boundary import FakeV4GmoBroker
from app.h11_auto.v4_gmo_contracts import (
    V4GmoAction,
    V4GmoBrokerSnapshot,
    V4GmoCycleState,
    V4GmoEntryStatus,
    V4GmoExecutionPolicy,
    V4GmoProtectionStatus,
    V4GmoSyntheticOutcome,
)
from app.h11_auto.v4_gmo_persistence import V4GmoStateStore
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_gmo_report import (
    V4GmoReportError,
    V4GmoReportStatus,
    render_v4_gmo_report_markdown,
    summarize_v4_gmo_state_no_post,
)
from app.h11_auto.v4_gmo_runtime import (
    V4GmoOperatorReloadStatus,
    V4GmoRuntimeStatus,
    operator_reload_v4_gmo_no_post,
    resume_v4_gmo_once_no_post,
    run_v4_gmo_once_no_post,
)

NOW = datetime(2026, 7, 15, 3, 0, tzinfo=UTC)


def _policy() -> V4GmoExecutionPolicy:
    return V4GmoExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:v4-recovery-signal",
        selected_horizon=FormalHorizon.MINUTES_10,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def _signal(*, offset_days: int = 0) -> FormalSignal:
    observed = NOW + timedelta(days=offset_days)
    return FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:v4-recovery-signal",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=observed,
        valid_until_utc=observed + timedelta(minutes=10),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.61"),
    )


def _filled(*, protected: bool = False) -> V4GmoBrokerSnapshot:
    return V4GmoBrokerSnapshot(
        fresh=True,
        result_known=True,
        position_count=1,
        position_side=SignalDecision.BUY,
        filled_size=1_000,
        pending_entry_size=0,
        protection_size=1_000 if protected else 0,
        entry_status=V4GmoEntryStatus.FILLED,
        protection_status=(
            V4GmoProtectionStatus.EXACT_MATCH
            if protected
            else V4GmoProtectionStatus.NONE
        ),
    )


def _success_broker() -> FakeV4GmoBroker:
    return FakeV4GmoBroker(
        outcomes={
            V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.ACCEPTED],
            V4GmoAction.EXACT_SIZE_OCO_PROTECTION: [V4GmoSyntheticOutcome.ACCEPTED],
        },
        snapshots=[V4GmoBrokerSnapshot.flat(), _filled(), _filled(protected=True)],
    )


def _runtime_safety(
    tmp_path: Path,
) -> tuple[PhaseBRiskStore, PhaseBRiskPolicy, DeadManStore]:
    risk = PhaseBRiskPolicy(
        policy_label="H11_V4_RISK_V1",
        per_trade_loss_bound_jpy=5_000,
        daily_loss_limit_jpy=10_000,
        monthly_loss_limit_jpy=50_000,
        maximum_consecutive_losses=5,
    )
    return (
        PhaseBRiskStore(tmp_path / "risk.json", policy=risk),
        risk,
        DeadManStore(
            tmp_path / "dead-man.json",
            policy=DeadManPolicy(
                policy_label="H11_V4_DEAD_MAN_V1",
                maximum_heartbeat_age_seconds=60,
            ),
        ),
    )


def _run_success(tmp_path: Path):
    risk_store, risk, dead_man = _runtime_safety(tmp_path)
    return run_v4_gmo_once_no_post(
        signal=_signal(),
        policy=_policy(),
        state_path=tmp_path / "v4.sqlite3",
        lock_path=tmp_path / "v4.lock",
        risk_store=risk_store,
        risk_policy=risk,
        dead_man_store=dead_man,
        notifier=FakeNotifier(),
        broker=_success_broker(),
        generation_label="H11_V4_GMO_10M_G001",
        now_utc=NOW,
    )


def test_runtime_resume_reconciles_existing_protection_without_new_action(
    tmp_path: Path,
) -> None:
    first = _run_success(tmp_path)
    assert first.status is V4GmoRuntimeStatus.POSITION_PROTECTED_SYNTHETIC
    risk_store, risk, dead_man = _runtime_safety(tmp_path)
    broker = FakeV4GmoBroker(outcomes={}, snapshots=[_filled(protected=True)])
    resumed = resume_v4_gmo_once_no_post(
        policy=_policy(),
        state_path=tmp_path / "v4.sqlite3",
        lock_path=tmp_path / "v4.lock",
        risk_store=risk_store,
        risk_policy=risk,
        dead_man_store=dead_man,
        notifier=FakeNotifier(),
        broker=broker,
        generation_label="H11_V4_GMO_10M_G001",
        now_utc=NOW + timedelta(seconds=30),
    )
    assert resumed.status is V4GmoRuntimeStatus.POSITION_PROTECTED_SYNTHETIC
    assert resumed.risk_entry_recorded is False
    assert resumed.action_attempt_count == 2
    assert broker.calls == []
    assert broker.reconciliation_count == 1


def test_runtime_resume_missing_protection_performs_one_emergency_exit(
    tmp_path: Path,
) -> None:
    _run_success(tmp_path)
    risk_store, risk, dead_man = _runtime_safety(tmp_path)
    broker = FakeV4GmoBroker(
        outcomes={
            V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT: [
                V4GmoSyntheticOutcome.ACCEPTED
            ]
        },
        snapshots=[_filled(), V4GmoBrokerSnapshot.flat()],
    )
    resumed = resume_v4_gmo_once_no_post(
        policy=_policy(),
        state_path=tmp_path / "v4.sqlite3",
        lock_path=tmp_path / "v4.lock",
        risk_store=risk_store,
        risk_policy=risk,
        dead_man_store=dead_man,
        notifier=FakeNotifier(),
        broker=broker,
        generation_label="H11_V4_GMO_10M_G001",
        now_utc=NOW + timedelta(seconds=30),
    )
    assert resumed.status is V4GmoRuntimeStatus.FLAT_RECONCILED_SYNTHETIC
    assert resumed.emergency_exit_attempt_count == 1
    assert [call.action for call in broker.calls] == [
        V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT
    ]


def test_runtime_resume_before_first_attempt_requires_fresh_flat(
    tmp_path: Path,
) -> None:
    store = V4GmoStateStore(tmp_path / "v4.sqlite3")
    store.create_cycle(signal=_signal(), policy=_policy(), now_utc=NOW)
    risk_store, risk, dead_man = _runtime_safety(tmp_path)
    broker = FakeV4GmoBroker(outcomes={}, snapshots=[_filled()])
    resumed = resume_v4_gmo_once_no_post(
        policy=_policy(),
        state_path=tmp_path / "v4.sqlite3",
        lock_path=tmp_path / "v4.lock",
        risk_store=risk_store,
        risk_policy=risk,
        dead_man_store=dead_man,
        notifier=FakeNotifier(),
        broker=broker,
        generation_label="H11_V4_GMO_10M_G001",
        now_utc=NOW + timedelta(seconds=1),
    )
    assert resumed.status is V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED
    assert resumed.market_entry_attempt_count == 0
    assert broker.calls == []


def test_operator_reload_requires_exact_phrase_and_fresh_flat_snapshot(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "v4.sqlite3"
    store = V4GmoStateStore(state_path)
    cycle = store.create_cycle(signal=_signal(), policy=_policy(), now_utc=NOW)
    store.transition(
        cycle_ref=cycle.cycle_ref,
        target=V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        event_category="HALTED_OPERATOR_REVIEW_REQUIRED",
        now_utc=NOW,
        halt_reason="SYNTHETIC_TEST_HALT",
    )
    nonflat = FakeV4GmoBroker(outcomes={}, snapshots=[_filled()])
    refused = operator_reload_v4_gmo_no_post(
        state_path=state_path,
        lock_path=tmp_path / "v4.lock",
        broker=nonflat,
        confirmation="H11_V4_GMO_OPERATOR_RELOAD_NO_POST",
        now_utc=NOW + timedelta(seconds=1),
    )
    assert refused.status is V4GmoOperatorReloadStatus.REFUSED_NOT_FLAT
    assert store.halt_latched() is True
    cleared = operator_reload_v4_gmo_no_post(
        state_path=state_path,
        lock_path=tmp_path / "v4.lock",
        broker=FakeV4GmoBroker(
            outcomes={}, snapshots=[V4GmoBrokerSnapshot.flat()]
        ),
        confirmation="H11_V4_GMO_OPERATOR_RELOAD_NO_POST",
        now_utc=NOW + timedelta(seconds=2),
    )
    assert cleared.status is V4GmoOperatorReloadStatus.CLEARED_NO_POST
    assert cleared.halted_cycle_cleared is True
    assert cleared.action_attempt_count == 0
    assert cleared.actual_post_count == 0
    assert store.load_cycle(cycle.cycle_ref).state is V4GmoCycleState.OPERATOR_RELOAD_CLEARED
    assert store.halt_latched() is False


def test_safe_report_reads_readonly_and_exposes_only_aggregate_state(
    tmp_path: Path,
) -> None:
    missing = summarize_v4_gmo_state_no_post(tmp_path / "missing.sqlite3")
    assert missing.report_status is V4GmoReportStatus.STATE_MISSING
    _run_success(tmp_path)
    report = summarize_v4_gmo_state_no_post(tmp_path / "v4.sqlite3")
    assert report.report_status is V4GmoReportStatus.READY
    assert report.cycle_count == 1
    assert report.active_cycle_count == 1
    assert report.protected_cycle_count == 1
    assert report.action_attempt_count == 2
    assert report.journal_valid is True
    assert report.actual_post_count == 0
    assert report.broker_write_performed is False
    assert report.credential_read_performed is False
    assert report.network_access_performed is False
    markdown = render_v4_gmo_report_markdown(report)
    assert "H11_V4_GMO_10M_G001" in markdown
    assert "actual_post / broker_write / credential_read: `false`" in markdown


def test_safe_report_verifies_repeated_action_categories_across_cycles(
    tmp_path: Path,
) -> None:
    path = tmp_path / "v4.sqlite3"
    store = V4GmoStateStore(path)
    for day in (0, 1):
        now = NOW + timedelta(days=day)
        cycle = store.create_cycle(signal=_signal(offset_days=day), policy=_policy(), now_utc=now)
        store.record_action_attempt(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.MARKET_ENTRY,
            target=V4GmoCycleState.MARKET_ENTRY_ATTEMPTED,
            now_utc=now,
        )
        store.record_action_outcome(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.MARKET_ENTRY,
            outcome_safe_label=V4GmoSyntheticOutcome.REJECTED.value,
        )
        store.transition(
            cycle_ref=cycle.cycle_ref,
            target=V4GmoCycleState.ENTRY_RECONCILING,
            event_category="ENTRY_RECONCILING",
            now_utc=now,
        )
        store.transition(
            cycle_ref=cycle.cycle_ref,
            target=V4GmoCycleState.FLAT_RECONCILED,
            event_category="ENTRY_REJECTED_OR_UNFILLED_FLAT",
            now_utc=now,
        )
    report = summarize_v4_gmo_state_no_post(path)
    assert report.cycle_count == 2
    assert report.market_entry_attempt_count == 2
    assert report.journal_valid is True


def test_safe_report_refuses_tampered_journal(tmp_path: Path) -> None:
    _run_success(tmp_path)
    path = tmp_path / "v4.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE safe_events SET state_safe_label = 'TAMPERED' WHERE sequence = 1"
        )
    with pytest.raises(V4GmoReportError, match="journal verification"):
        summarize_v4_gmo_state_no_post(path)
