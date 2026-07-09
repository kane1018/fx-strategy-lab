"""E1 kill/dead-man, budget, audit, and stage-gate tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest

import app.shadow.e1.qualification as qualification_module
from app.shadow.e1.contracts import (
    E1Policy,
    EngineDecision,
    EngineLabel,
    EnginePhase,
    ExecutionOutcome,
    FaultInjection,
    FaultKind,
    GateAction,
    HypothesisLabel,
    KillReason,
    MarketFrame,
    ReconcileStatus,
    build_hypothesis_decision,
    build_settlement_decision,
)
from app.shadow.e1.engine import E1EngineError, E1ShadowFullAutoEngine
from app.shadow.e1.persistence import (
    E1PersistenceError,
    JournalEventType,
    ShadowIntentJournal,
    VirtualVenueStateStore,
)
from app.shadow.e1.qualification import (
    E1AuditSummary,
    E1EvidenceWindow,
    E1GateStatus,
    E1GateThresholds,
    evaluate_e1_to_e2_review_gate,
    summarize_e1_bundle,
    summarize_e1_journal,
)

NOW = datetime(2026, 7, 10, 3, 0, tzinfo=UTC)


def _frame(now: datetime = NOW, *, bid: str = "150.000", ask: str = "150.004"):
    return MarketFrame.build(
        symbol="USD_JPY",
        evaluation_time=now,
        market_data_time=now,
        bid=bid,
        ask=ask,
    )


def _open(tmp_path, run_id: str, policy: E1Policy):
    root = tmp_path / run_id
    journal = ShadowIntentJournal(
        root=root,
        path=root / "intent.jsonl",
        run_id=run_id,
        config_hash=policy.config_hash,
    )
    venue = VirtualVenueStateStore(
        root=root,
        path=root / "venue.json",
        config_hash=policy.config_hash,
    )
    engine = E1ShadowFullAutoEngine(
        run_id=run_id,
        policy=policy,
        journal=journal,
        venue=venue,
        clock=lambda: NOW,
    )
    return engine, journal, venue


def _ready(tmp_path, run_id: str, policy: E1Policy):
    engine, journal, venue = _open(tmp_path, run_id, policy)
    assert engine.boot_reconcile(now=NOW) is ReconcileStatus.INITIAL_FLAT_CONFIRMED
    engine.record_heartbeat(now=NOW)
    return engine, journal, venue


def _buy(policy: E1Policy):
    return build_hypothesis_decision(
        HypothesisLabel.BUY_CANDIDATE,
        config_hash=policy.config_hash,
        reason_code="KILL_FIXTURE_BUY",
    )


def _no_action(policy: E1Policy):
    return build_hypothesis_decision(
        HypothesisLabel.NO_ACTION,
        config_hash=policy.config_hash,
        reason_code="E1_GATE_NO_ACTION",
    )


@pytest.mark.parametrize("occurrence", range(3))
def test_manual_kill_flattens_position_once_then_halts(tmp_path, occurrence: int) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, f"kill-{occurrence}", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    assert venue.position is not None
    result = engine.activate_kill(
        now=NOW + timedelta(seconds=1),
        reason=KillReason.MANUAL,
        market=_frame(NOW + timedelta(seconds=1)),
    )
    assert result.status == "KILL_FLATTENED_ONCE_THEN_HALTED"
    assert result.phase is EnginePhase.HALTED
    assert venue.position is None
    summary = summarize_e1_journal(journal, policy=policy)
    assert summary.virtual_entry_effect_count == 1
    assert summary.virtual_settlement_effect_count == 1
    assert summary.kill_test_count == 1
    assert summary.virtual_execution_count == 2
    assert summary.actual_post_count == 0
    with pytest.raises(E1EngineError, match="sticky halt"):
        engine.process_decision(decision=_no_action(policy), market=_frame())


@pytest.mark.parametrize("occurrence", range(3))
def test_deadman_expiry_flattens_once_then_halts(tmp_path, occurrence: int) -> None:
    policy = E1Policy(cooldown_seconds=0, heartbeat_timeout_seconds=60)
    engine, journal, venue = _ready(tmp_path, f"deadman-{occurrence}", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    expiry = NOW + timedelta(seconds=61)
    result = engine.check_deadman(now=expiry, market=_frame(expiry))
    assert result.status == "KILL_FLATTENED_ONCE_THEN_HALTED"
    assert engine.phase is EnginePhase.HALTED
    assert venue.position is None
    summary = summarize_e1_journal(journal, policy=policy)
    assert summary.deadman_test_count == 1
    assert summary.virtual_settlement_effect_count == 1


def test_deadman_within_sla_does_not_halt_or_execute(tmp_path) -> None:
    policy = E1Policy(heartbeat_timeout_seconds=60)
    engine, journal, venue = _ready(tmp_path, "deadman-safe", policy)
    result = engine.check_deadman(now=NOW + timedelta(seconds=60))
    assert result.status == "DEADMAN_HEARTBEAT_WITHIN_SLA"
    assert result.virtual_execution_attempted is False
    assert engine.phase is EnginePhase.READY_FLAT
    assert venue.position is None
    assert summarize_e1_journal(journal, policy=policy).deadman_test_count == 0


def test_kill_serializes_against_in_flight_entry_and_finishes_flat(
    tmp_path, monkeypatch
) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "kill-entry-race", policy)
    entry_paused = Event()
    release_entry = Event()
    kill_called = Event()
    original_execute = engine._execute_entry

    def paused_execute(**kwargs):
        entry_paused.set()
        assert release_entry.wait(timeout=2)
        return original_execute(**kwargs)

    def invoke_kill():
        kill_called.set()
        return engine.activate_kill(
            now=NOW + timedelta(seconds=1),
            reason=KillReason.MANUAL,
            market=_frame(NOW + timedelta(seconds=1)),
        )

    monkeypatch.setattr(engine, "_execute_entry", paused_execute)
    with ThreadPoolExecutor(max_workers=2) as executor:
        entry_future = executor.submit(
            engine.process_decision,
            decision=_buy(policy),
            market=_frame(),
            protective_stop_price="149.000",
        )
        assert entry_paused.wait(timeout=2)
        kill_future = executor.submit(invoke_kill)
        assert kill_called.wait(timeout=2)
        assert kill_future.done() is False
        release_entry.set()
        entry_result = entry_future.result(timeout=2)
        kill_result = kill_future.result(timeout=2)

    assert entry_result.status == "VIRTUAL_EXECUTION_CONFIRMED"
    assert kill_result.status == "KILL_FLATTENED_ONCE_THEN_HALTED"
    assert engine.phase is EnginePhase.HALTED
    assert venue.position is None
    summary = summarize_e1_journal(journal, policy=policy)
    assert summary.virtual_entry_effect_count == 1
    assert summary.virtual_settlement_effect_count == 1
    assert summary.kill_test_count == 1


def test_gate_evidence_aggregates_sticky_kill_and_deadman_across_unique_runs(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0, heartbeat_timeout_seconds=60)
    journals = []
    for index in range(3):
        engine, journal, _venue = _ready(tmp_path, f"bundle-kill-{index}", policy)
        engine.process_decision(
            decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
        )
        engine.activate_kill(
            now=NOW + timedelta(seconds=1),
            reason=KillReason.MANUAL,
            market=_frame(NOW + timedelta(seconds=1)),
        )
        journals.append(journal)
    for index in range(3):
        engine, journal, _venue = _ready(tmp_path, f"bundle-deadman-{index}", policy)
        engine.process_decision(
            decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
        )
        expiry = NOW + timedelta(seconds=61)
        engine.check_deadman(now=expiry, market=_frame(expiry))
        journals.append(journal)
    audit, _window, config_hash, identity_ok = summarize_e1_bundle(
        tuple(journals),
        policy=policy,
    )
    assert identity_ok is True
    assert config_hash == policy.config_hash
    assert audit.kill_test_count == 3
    assert audit.deadman_test_count == 3


def test_flat_kill_halts_but_does_not_count_as_flatten_exercise(tmp_path) -> None:
    policy = E1Policy()
    engine, journal, venue = _ready(tmp_path, "flat-kill-not-exercise", policy)
    result = engine.activate_kill(now=NOW, reason=KillReason.MANUAL)
    assert result.status == "KILL_HALTED_FLAT"
    assert venue.position is None
    audit = summarize_e1_journal(journal, policy=policy)
    assert audit.kill_test_count == 0
    assert audit.control_exercise_invariant_ok is False


def test_kill_unknown_settlement_never_retries_and_escalates(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "kill-unknown", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    result = engine.activate_kill(
        now=NOW + timedelta(seconds=1),
        reason=KillReason.MANUAL,
        market=_frame(NOW + timedelta(seconds=1)),
        fault=FaultInjection(kind=FaultKind.UNKNOWN_RESULT),
    )
    assert result.status == "KILL_HALTED_ESCALATION_REQUIRED"
    assert result.reason_codes == ("MANUAL_KILL", "NO_RETRY")
    assert engine.phase is EnginePhase.HALTED
    assert venue.position is not None
    settlement_starts = [
        record
        for record in journal.records
        if record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is not None
        and record.action.value == "VIRTUAL_POSITION_SPECIFIC_SETTLEMENT"
    ]
    assert len(settlement_starts) == 1
    assert journal.unresolved_intents()
    repeated = engine.activate_kill(
        now=NOW + timedelta(seconds=2),
        reason=KillReason.MANUAL,
        market=_frame(NOW + timedelta(seconds=2)),
    )
    assert repeated.status == "KILL_ALREADY_ACTIVE_NO_SECOND_ATTEMPT"
    assert repeated.virtual_execution_attempted is False
    settlement_starts_after = [
        record
        for record in journal.records
        if record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is not None
        and record.action.value == "VIRTUAL_POSITION_SPECIFIC_SETTLEMENT"
    ]
    assert len(settlement_starts_after) == 1


def test_deadman_cannot_bypass_existing_sticky_halt_or_retry_settlement(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0, heartbeat_timeout_seconds=60)
    engine, journal, venue = _ready(tmp_path, "halt-before-deadman", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    assert venue.position is not None
    rejected = engine.process_decision(
        decision=build_settlement_decision(
            position_ref=venue.position.position_ref,
            config_hash=policy.config_hash,
            reason_code="REJECTED_SETTLEMENT_FIXTURE",
        ),
        market=_frame(NOW + timedelta(seconds=1)),
        fault=FaultInjection(kind=FaultKind.REJECTED),
    )
    assert rejected.status == "VIRTUAL_EXECUTION_REJECTED_NO_RETRY"
    assert engine.phase is EnginePhase.HALTED
    starts_before = sum(
        record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is GateAction.VIRTUAL_SETTLEMENT
        for record in journal.records
    )
    deadman = engine.check_deadman(
        now=NOW + timedelta(seconds=61),
        market=_frame(NOW + timedelta(seconds=61)),
    )
    assert deadman.status == "ENGINE_ALREADY_HALTED_NO_FURTHER_ATTEMPT"
    assert deadman.virtual_execution_attempted is False
    assert venue.position is not None
    assert sum(
        record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is GateAction.VIRTUAL_SETTLEMENT
        for record in journal.records
    ) == starts_before


def test_restart_after_kill_reconciles_but_never_resumes(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, _journal, _venue = _ready(tmp_path, "kill-restart", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    engine.activate_kill(
        now=NOW + timedelta(seconds=1),
        reason=KillReason.MANUAL,
        market=_frame(NOW + timedelta(seconds=1)),
        fault=FaultInjection(
            kind=FaultKind.UNKNOWN_RESULT,
            apply_effect_before_fault=True,
        ),
    )
    restarted, _journal2, venue2 = _open(tmp_path, "kill-restart", policy)
    status = restarted.boot_reconcile(now=NOW + timedelta(seconds=2))
    assert status is ReconcileStatus.RECOVERED_PLANNED_EFFECT
    assert venue2.position is None
    assert restarted.phase is EnginePhase.HALTED
    with pytest.raises(E1EngineError, match="not currently required"):
        restarted.acknowledge_restart(
            now=NOW + timedelta(seconds=3), operator_acknowledged=True
        )


@pytest.mark.parametrize("apply_effect", [False, True])
def test_kill_path_crash_is_sticky_and_never_retries(
    tmp_path, apply_effect: bool
) -> None:
    policy = E1Policy(cooldown_seconds=0)
    run_id = f"kill-crash-{int(apply_effect)}"
    engine, journal, venue = _ready(tmp_path, run_id, policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    with pytest.raises(RuntimeError, match="simulated crash"):
        engine.activate_kill(
            now=NOW + timedelta(seconds=1),
            reason=KillReason.MANUAL,
            market=_frame(NOW + timedelta(seconds=1)),
            fault=FaultInjection(
                kind=FaultKind.CRASH_MID_VIRTUAL_EXECUTION,
                apply_effect_before_fault=apply_effect,
            ),
        )
    assert journal.kill_active is True
    settlement_starts = [
        record
        for record in journal.records
        if record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is not None
        and record.action.value == "VIRTUAL_POSITION_SPECIFIC_SETTLEMENT"
    ]
    assert len(settlement_starts) == 1
    restarted, restarted_journal, restarted_venue = _open(tmp_path, run_id, policy)
    status = restarted.boot_reconcile(now=NOW + timedelta(seconds=2))
    assert status in {
        ReconcileStatus.RECOVERED_NO_EFFECT,
        ReconcileStatus.RECOVERED_PLANNED_EFFECT,
    }
    assert restarted.phase is EnginePhase.HALTED
    assert (restarted_venue.position is None) is apply_effect
    assert any(
        record.event_type is JournalEventType.HALTED
        and record.status_label == "ENGINE_HALTED_STICKY"
        for record in restarted_journal.records
    )
    escalation_alerts = [
        record
        for record in restarted_journal.records
        if record.event_type is JournalEventType.FAKE_CRITICAL_ALERT
        and "STICKY_KILL_RESTART_POSITION_REMAINS_MANUAL_ESCALATION"
        in record.reason_codes
    ]
    assert bool(escalation_alerts) is (not apply_effect)
    assert sum(
        record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is GateAction.VIRTUAL_SETTLEMENT
        for record in restarted_journal.records
    ) == 1
    assert (
        summarize_e1_journal(
            restarted_journal,
            policy=policy,
        ).virtual_execution_count
        == 2
    )


def test_kill_intent_journal_failure_halts_without_virtual_retry(
    tmp_path, monkeypatch
) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "kill-journal-failure", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    original_append = journal.append

    def fail_kill_intent(**kwargs):
        if kwargs["event_type"] is JournalEventType.INTENT_PREPARED:
            raise E1PersistenceError("injected kill intent journal failure")
        return original_append(**kwargs)

    monkeypatch.setattr(journal, "append", fail_kill_intent)
    result = engine.activate_kill(
        now=NOW + timedelta(seconds=1),
        reason=KillReason.MANUAL,
        market=_frame(NOW + timedelta(seconds=1)),
    )
    assert result.status == "KILL_HALTED_ESCALATION_REQUIRED"
    assert result.virtual_execution_attempted is False
    assert venue.position is not None
    assert engine.phase is EnginePhase.HALTED
    assert not any(
        record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is not None
        and record.action.value == "VIRTUAL_POSITION_SPECIFIC_SETTLEMENT"
        for record in journal.records
    )


def test_daily_entry_cap_is_not_reset_within_same_day(tmp_path) -> None:
    policy = E1Policy(max_entries_per_day=1, cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "entry-cap", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    assert venue.position is not None
    engine.process_decision(
        decision=build_settlement_decision(
            position_ref=venue.position.position_ref,
            config_hash=policy.config_hash,
            reason_code="CAP_TEST_SETTLEMENT",
        ),
        market=_frame(NOW + timedelta(seconds=1)),
    )
    blocked = engine.process_decision(
        decision=_buy(policy),
        market=_frame(NOW + timedelta(seconds=2)),
        protective_stop_price="149.000",
    )
    assert blocked.status == "RISK_GATE_BLOCKED_NO_ACTION"
    assert "DAILY_ENTRY_CAP_REACHED" in blocked.reason_codes
    assert summarize_e1_journal(journal, policy=policy).virtual_entry_effect_count == 1


def test_virtual_loss_and_consecutive_loss_caps_stop_next_entry(tmp_path) -> None:
    policy = E1Policy(
        max_virtual_loss_per_trade="2",  # type: ignore[arg-type]
        max_daily_virtual_loss="2",  # type: ignore[arg-type]
        max_weekly_virtual_loss="2",  # type: ignore[arg-type]
        max_consecutive_losses=1,
        cooldown_seconds=0,
    )
    engine, _journal, venue = _ready(tmp_path, "loss-cap", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    assert venue.position is not None
    loss_time = NOW + timedelta(seconds=1)
    engine.process_decision(
        decision=build_settlement_decision(
            position_ref=venue.position.position_ref,
            config_hash=policy.config_hash,
            reason_code="LOSS_CAP_SETTLEMENT",
        ),
        market=_frame(loss_time, bid="149.000", ask="149.004"),
    )
    blocked = engine.process_decision(
        decision=_buy(policy),
        market=_frame(NOW + timedelta(seconds=2)),
        protective_stop_price="148.000",
    )
    assert blocked.status == "RISK_GATE_BLOCKED_NO_ACTION"
    assert {
        "CONSECUTIVE_LOSS_CAP_REACHED",
        "DAILY_PROSPECTIVE_VIRTUAL_LOSS_CAP_EXCEEDED",
        "WEEKLY_PROSPECTIVE_VIRTUAL_LOSS_CAP_EXCEEDED",
    }.issubset(blocked.reason_codes)


def test_default_e1_gate_thresholds_match_preregistration() -> None:
    thresholds = E1GateThresholds()
    assert thresholds.minimum_calendar_days == 14
    assert thresholds.minimum_business_days == 10
    assert thresholds.minimum_virtual_entries == 100
    assert thresholds.minimum_virtual_settlements == 100
    assert thresholds.minimum_no_action_events == 300
    assert thresholds.minimum_each_fault_handled == 5
    assert thresholds.minimum_kill_tests == 3
    assert thresholds.minimum_deadman_tests == 3
    assert thresholds.maximum_high_incidents == 0
    assert thresholds.maximum_medium_incidents == 2


def test_current_small_run_is_explicitly_not_gate_passed(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "gate-blocked", policy)
    engine.process_decision(decision=_no_action(policy), market=_frame())
    engine.process_decision(
        decision=_buy(policy),
        market=_frame(NOW + timedelta(seconds=1)),
        protective_stop_price="149.000",
    )
    assert venue.position is not None
    engine.process_decision(
        decision=build_settlement_decision(
            position_ref=venue.position.position_ref,
            config_hash=policy.config_hash,
            reason_code="GATE_FIXTURE_SETTLEMENT",
        ),
        market=_frame(NOW + timedelta(seconds=2)),
    )
    report = evaluate_e1_to_e2_review_gate(
        journals=(journal,),
        policy=policy,
    )
    assert report.status is E1GateStatus.IMPLEMENTED_NOT_GATE_PASSED
    assert "MINIMUM_CALENDAR_DAYS_NOT_MET" in report.blockers
    assert "MINIMUM_VIRTUAL_ENTRY_EVENTS_NOT_MET" in report.blockers
    assert report.e2_execution_permission is False
    assert report.e3_or_live_permission is False
    assert report.performance_proof_status is False
    assert report.audit.actual_post_count == 0
    assert not report


def test_complete_technical_evidence_still_requires_separate_e2_review(
    tmp_path, monkeypatch
) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "gate-review", policy)
    engine.process_decision(decision=_no_action(policy), market=_frame())
    engine.process_decision(
        decision=_buy(policy),
        market=_frame(NOW + timedelta(seconds=1)),
        protective_stop_price="149.000",
    )
    assert venue.position is not None
    engine.process_decision(
        decision=build_settlement_decision(
            position_ref=venue.position.position_ref,
            config_hash=policy.config_hash,
            reason_code="REVIEW_GATE_SETTLEMENT",
        ),
        market=_frame(NOW + timedelta(seconds=2)),
    )
    complete_audit = E1AuditSummary(
        durable_intent_count=200,
        consumed_shadow_token_count=200,
        virtual_execution_count=200,
        unique_intent_count=200,
        unique_token_count=200,
        virtual_entry_effect_count=100,
        virtual_settlement_effect_count=100,
        no_action_count=300,
        reconcile_mismatch_count=0,
        unresolved_intent_count=0,
        safety_violation_count=0,
        kill_test_count=3,
        deadman_test_count=3,
        fault_handled_counts=tuple(
            (kind.value, 5) for kind in qualification_module.REQUIRED_FAULT_KINDS
        ),
        cardinality_invariant_ok=True,
    )
    complete_window = E1EvidenceWindow(
        first_event_at="2026-07-01T00:00:00.000000Z",
        last_event_at="2026-07-15T00:00:00.000000Z",
        calendar_days=14,
        business_days=10,
        high_incidents=0,
        medium_incidents=0,
        incomplete_medium_postmortem_refs=(),
    )
    monkeypatch.setattr(
        qualification_module,
        "summarize_e1_bundle",
        lambda journals, policy: (
            complete_audit,
            complete_window,
            policy.config_hash,
            True,
        ),
    )
    report = evaluate_e1_to_e2_review_gate(journals=(journal,), policy=policy)
    assert report.status is E1GateStatus.EVIDENCE_COMPLETE_REVIEW_REQUIRED
    assert report.blockers == ()
    assert report.e2_review_required is True
    assert report.e2_execution_permission is False
    assert report.e3_or_live_permission is False
    assert not report


def test_medium_incident_requires_postmortem(tmp_path) -> None:
    policy = E1Policy()
    engine, journal, _venue = _ready(tmp_path, "postmortem", policy)
    engine.process_decision(decision=_no_action(policy), market=_frame())
    engine.record_incident(
        now=NOW + timedelta(seconds=1),
        incident_ref="incident:medium:one",
        severity="MEDIUM",
        reason_code="FIXTURE_MEDIUM_INCIDENT",
    )
    report = evaluate_e1_to_e2_review_gate(journals=(journal,), policy=policy)
    assert report.status is E1GateStatus.IMPLEMENTED_NOT_GATE_PASSED
    assert "MEDIUM_INCIDENT_POSTMORTEM_INCOMPLETE" in report.blockers


def test_gate_thresholds_cannot_be_relaxed() -> None:
    with pytest.raises(ValueError, match="frozen"):
        E1GateThresholds(minimum_virtual_entries=1)


def test_duplicate_effect_rows_cannot_inflate_gate_counts(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "duplicate-effect", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    assert venue.position is not None
    confirmed = next(
        record
        for record in journal.records
        if record.event_type is JournalEventType.VIRTUAL_EXECUTION_CONFIRMED
    )
    journal.append(
        event_type=JournalEventType.VIRTUAL_EXECUTION_CONFIRMED,
        timestamp=confirmed.timestamp,
        status_label="DUPLICATE_EFFECT_INJECTION",
        expected_state_digest=confirmed.expected_state_digest,
        position_count=confirmed.position_count,
        action=confirmed.action,
        intent_id=confirmed.intent_id,
        intent_digest=confirmed.intent_digest,
        token_id=confirmed.token_id,
        execution_outcome=confirmed.execution_outcome,
        fault_kind=confirmed.fault_kind,
        state_before_digest=confirmed.state_before_digest,
        planned_state_digest=confirmed.planned_state_digest,
        observed_state_digest=confirmed.observed_state_digest,
        pnl_category=confirmed.pnl_category,
        virtual_loss=confirmed.virtual_loss,
    )
    audit = summarize_e1_journal(journal, policy=policy)
    assert audit.cardinality_invariant_ok is False
    assert audit.virtual_entry_effect_count == 0
    report = evaluate_e1_to_e2_review_gate(journals=(journal,), policy=policy)
    assert "TOKEN_INTENT_EXECUTION_CARDINALITY_FAILED" in report.blockers


@pytest.mark.parametrize("corruption", ["sequence", "outcome", "state"])
def test_lifecycle_requires_exact_order_outcome_and_state_contract(
    tmp_path, corruption: str
) -> None:
    policy = E1Policy(cooldown_seconds=0)
    _engine, journal, _venue = _ready(tmp_path, f"lifecycle-{corruption}", policy)
    before = "a" * 64
    planned = "b" * 64
    common = {
        "timestamp": NOW,
        "action": GateAction.VIRTUAL_ENTRY,
        "intent_id": f"intent-{corruption}",
        "intent_digest": "c" * 64,
        "token_id": f"token-{corruption}",
        "state_before_digest": before,
        "planned_state_digest": planned,
    }

    def append_prepared() -> None:
        journal.append(
            event_type=JournalEventType.INTENT_PREPARED,
            status_label="DURABLE_INTENT_PREPARED_BEFORE_VIRTUAL_EFFECT",
            expected_state_digest=before,
            observed_state_digest=before,
            position_count=0,
            **common,
        )

    def append_started() -> None:
        journal.append(
            event_type=JournalEventType.VIRTUAL_EXECUTION_STARTED,
            status_label="VIRTUAL_EXECUTION_STARTED_ONCE",
            expected_state_digest=before,
            observed_state_digest=before,
            position_count=0,
            **common,
        )

    if corruption == "sequence":
        append_started()
        append_prepared()
    else:
        append_prepared()
        append_started()
    journal.append(
        event_type=JournalEventType.VIRTUAL_EXECUTION_CONFIRMED,
        status_label="VIRTUAL_EFFECT_CONFIRMED",
        expected_state_digest=planned,
        observed_state_digest=before if corruption == "state" else planned,
        position_count=1,
        execution_outcome=(
            ExecutionOutcome.REJECTED
            if corruption == "outcome"
            else ExecutionOutcome.ACCEPTED
        ),
        **common,
    )
    audit = summarize_e1_journal(journal, policy=policy)
    assert audit.cardinality_invariant_ok is False
    assert audit.virtual_entry_effect_count == 0


@pytest.mark.parametrize(
    ("event_type", "status_label", "count_field"),
    [
        (JournalEventType.KILL_ACTIVATED, KillReason.MANUAL.value, "kill_test_count"),
        (
            JournalEventType.DEADMAN_ACTIVATED,
            KillReason.DEADMAN_HEARTBEAT_EXPIRED.value,
            "deadman_test_count",
        ),
    ],
)
def test_control_activation_without_matching_halt_is_not_gate_evidence(
    tmp_path, event_type: JournalEventType, status_label: str, count_field: str
) -> None:
    policy = E1Policy()
    journals = []
    for index in range(3):
        _engine, journal, venue = _ready(
            tmp_path, f"invalid-control-{event_type.value}-{index}", policy
        )
        journal.append(
            event_type=event_type,
            timestamp=NOW,
            status_label=status_label,
            reason_codes=("NEW_ENTRY_BLOCKED_IMMEDIATELY",),
            expected_state_digest=venue.state_digest,
            observed_state_digest=venue.state_digest,
            position_count=0,
        )
        journals.append(journal)
    audit, _window, _config_hash, _identity_ok = summarize_e1_bundle(
        tuple(journals),
        policy=policy,
    )
    assert getattr(audit, count_field) == 0
    assert audit.control_exercise_invariant_ok is False
    report = evaluate_e1_to_e2_review_gate(
        journals=tuple(journals),
        policy=policy,
    )
    assert "KILL_DEADMAN_EXERCISE_CONTRACT_FAILED" in report.blockers


def test_multiple_control_activations_in_one_run_never_count_as_distinct_tests(
    tmp_path,
) -> None:
    policy = E1Policy()
    _engine, journal, venue = _ready(tmp_path, "duplicate-controls", policy)
    for index in range(3):
        journal.append(
            event_type=JournalEventType.KILL_ACTIVATED,
            timestamp=NOW + timedelta(seconds=index),
            status_label=KillReason.MANUAL.value,
            reason_codes=("NEW_ENTRY_BLOCKED_IMMEDIATELY",),
            expected_state_digest=venue.state_digest,
            observed_state_digest=venue.state_digest,
            position_count=0,
        )
    audit = summarize_e1_journal(journal, policy=policy)
    assert audit.kill_test_count == 0
    assert audit.control_exercise_invariant_ok is False


def test_standalone_fault_handled_row_is_not_gate_evidence(tmp_path) -> None:
    policy = E1Policy()
    _engine, journal, venue = _ready(tmp_path, "standalone-fault-row", policy)
    journal.append(
        event_type=JournalEventType.FAULT_HANDLED,
        timestamp=NOW,
        status_label="FAULT_HANDLED_WITHOUT_RETRY",
        reason_codes=(FaultKind.TIMEOUT.value,),
        expected_state_digest=venue.state_digest,
        observed_state_digest=venue.state_digest,
        position_count=0,
        action=GateAction.VIRTUAL_ENTRY,
        intent_id="intent:standalone-fault",
        intent_digest="a" * 64,
        token_id="shadowtoken:standalone-fault",
        fault_kind=FaultKind.TIMEOUT,
        state_before_digest=venue.state_digest,
        planned_state_digest="b" * 64,
    )
    audit = summarize_e1_journal(journal, policy=policy)
    assert dict(audit.fault_handled_counts)[FaultKind.TIMEOUT.value] == 0
    assert audit.fault_exercise_invariant_ok is False
    report = evaluate_e1_to_e2_review_gate(journals=(journal,), policy=policy)
    assert "FAULT_EXERCISE_EVIDENCE_INVALID" in report.blockers


def test_no_action_with_unbound_decision_digest_is_not_gate_evidence(tmp_path) -> None:
    policy = E1Policy()
    _engine, journal, venue = _ready(tmp_path, "unbound-no-action", policy)
    spec = policy.hypothesis_registry.specs[0]
    journal.append(
        event_type=JournalEventType.NO_ACTION_RECORDED,
        timestamp=NOW,
        status_label="ENGINE_NO_ACTION_TERMINAL",
        reason_codes=("FABRICATED_NO_ACTION",),
        expected_state_digest=venue.state_digest,
        observed_state_digest=venue.state_digest,
        position_count=0,
        decision_digest="d" * 64,
        hypothesis_label=HypothesisLabel.NO_ACTION,
        hypothesis_id=spec.hypothesis_id,
        hypothesis_version=spec.version,
    )
    audit = summarize_e1_journal(journal, policy=policy)
    assert audit.no_action_count == 0
    assert audit.no_action_evidence_invariant_ok is False
    report = evaluate_e1_to_e2_review_gate(journals=(journal,), policy=policy)
    assert "NO_ACTION_EVIDENCE_INVALID" in report.blockers


def test_no_action_from_unregistered_hypothesis_is_not_gate_evidence(tmp_path) -> None:
    policy = E1Policy()
    _engine, journal, venue = _ready(tmp_path, "unregistered-no-action", policy)
    decision = EngineDecision(
        engine_label=EngineLabel.NO_ACTION,
        config_hash=policy.config_hash,
        reason_code="UNREGISTERED_NO_ACTION",
        hypothesis_label=HypothesisLabel.NO_ACTION,
        hypothesis_id="NOT_REGISTERED",
        hypothesis_version="v999",
    )
    journal.append(
        event_type=JournalEventType.NO_ACTION_RECORDED,
        timestamp=NOW,
        status_label="ENGINE_NO_ACTION_TERMINAL",
        reason_codes=(decision.reason_code,),
        expected_state_digest=venue.state_digest,
        observed_state_digest=venue.state_digest,
        position_count=0,
        decision_digest=decision.decision_digest,
        hypothesis_label=decision.hypothesis_label,
        hypothesis_id=decision.hypothesis_id,
        hypothesis_version=decision.hypothesis_version,
    )
    audit = summarize_e1_journal(journal, policy=policy)
    assert audit.no_action_count == 0
    assert audit.no_action_evidence_invariant_ok is False


def test_postmortem_must_follow_one_unique_matching_incident(tmp_path) -> None:
    policy = E1Policy()
    engine, journal, _venue = _ready(tmp_path, "postmortem-chronology", policy)
    engine.record_postmortem(now=NOW, incident_ref="incident:medium:chronology")
    engine.record_incident(
        now=NOW + timedelta(seconds=1),
        incident_ref="incident:medium:chronology",
        severity="MEDIUM",
        reason_code="FIXTURE_MEDIUM_INCIDENT",
    )
    report = evaluate_e1_to_e2_review_gate(journals=(journal,), policy=policy)
    assert "MEDIUM_INCIDENT_POSTMORTEM_INCOMPLETE" in report.blockers
    assert "INCIDENT_POSTMORTEM_EVIDENCE_INVALID" in report.blockers


def test_duplicate_incident_ref_across_runs_is_invalid_evidence(tmp_path) -> None:
    policy = E1Policy()
    journals = []
    for index in range(2):
        engine, journal, _venue = _ready(tmp_path, f"duplicate-incident-{index}", policy)
        engine.record_incident(
            now=NOW + timedelta(seconds=index),
            incident_ref="incident:medium:duplicate",
            severity="MEDIUM",
            reason_code="FIXTURE_MEDIUM_INCIDENT",
        )
        journals.append(journal)
    report = evaluate_e1_to_e2_review_gate(
        journals=tuple(journals),
        policy=policy,
    )
    assert "INCIDENT_POSTMORTEM_EVIDENCE_INVALID" in report.blockers


def test_later_unique_postmortem_satisfies_medium_incident_evidence(tmp_path) -> None:
    policy = E1Policy()
    engine, journal, _venue = _ready(tmp_path, "postmortem-valid", policy)
    engine.record_incident(
        now=NOW,
        incident_ref="incident:medium:valid",
        severity="MEDIUM",
        reason_code="FIXTURE_MEDIUM_INCIDENT",
    )
    engine.record_postmortem(
        now=NOW + timedelta(seconds=1), incident_ref="incident:medium:valid"
    )
    report = evaluate_e1_to_e2_review_gate(journals=(journal,), policy=policy)
    assert "MEDIUM_INCIDENT_POSTMORTEM_INCOMPLETE" not in report.blockers
    assert "INCIDENT_POSTMORTEM_EVIDENCE_INVALID" not in report.blockers
