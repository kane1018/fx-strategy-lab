"""E1 fault injection, crash recovery, and reconcile-first tests."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest

import app.shadow.e1.persistence as persistence_module
from app.shadow.e1.contracts import (
    E1Policy,
    EnginePhase,
    FaultInjection,
    FaultKind,
    HypothesisLabel,
    MarketFrame,
    PositionSide,
    ReconcileStatus,
    VirtualPosition,
    build_hypothesis_decision,
    build_settlement_decision,
    canonical_timestamp,
    position_digest,
)
from app.shadow.e1.engine import (
    E1EngineError,
    E1ShadowFullAutoEngine,
    SimulatedShadowCrash,
)
from app.shadow.e1.persistence import (
    E1PersistenceError,
    JournalEventType,
    ShadowIntentJournal,
    VirtualVenueStateStore,
)
from app.shadow.e1.qualification import summarize_e1_journal

NOW = datetime(2026, 7, 10, 2, 0, tzinfo=UTC)


def _frame(now: datetime = NOW) -> MarketFrame:
    return MarketFrame.build(
        symbol="USD_JPY",
        evaluation_time=now,
        market_data_time=now,
        bid="150.000",
        ask="150.004",
    )


def _paths(tmp_path, run_id: str):
    root = tmp_path / run_id
    return root, root / "intent.jsonl", root / "venue.json"


def _open_engine(tmp_path, run_id: str, policy: E1Policy):
    root, journal_path, venue_path = _paths(tmp_path, run_id)
    journal = ShadowIntentJournal(
        root=root,
        path=journal_path,
        run_id=run_id,
        config_hash=policy.config_hash,
    )
    venue = VirtualVenueStateStore(
        root=root,
        path=venue_path,
        config_hash=policy.config_hash,
    )
    return (
        E1ShadowFullAutoEngine(
            run_id=run_id,
            policy=policy,
            journal=journal,
            venue=venue,
            clock=lambda: NOW,
        ),
        journal,
        venue,
    )


def _ready(tmp_path, run_id: str, policy: E1Policy):
    engine, journal, venue = _open_engine(tmp_path, run_id, policy)
    assert engine.boot_reconcile(now=NOW) is ReconcileStatus.INITIAL_FLAT_CONFIRMED
    engine.record_heartbeat(now=NOW)
    return engine, journal, venue


def _buy(policy: E1Policy):
    return build_hypothesis_decision(
        HypothesisLabel.BUY_CANDIDATE,
        config_hash=policy.config_hash,
        reason_code="FAULT_FIXTURE_BUY",
    )


@pytest.mark.parametrize(
    "fault_kind",
    [FaultKind.TIMEOUT, FaultKind.UNKNOWN_RESULT, FaultKind.NETWORK_ERROR],
)
@pytest.mark.parametrize("occurrence", range(5))
def test_uncertain_fault_paths_reconcile_without_retry(
    tmp_path, fault_kind: FaultKind, occurrence: int
) -> None:
    run_id = f"fault-{fault_kind.value.lower()}-{occurrence}"
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, run_id, policy)
    apply_effect = occurrence % 2 == 1
    result = engine.process_decision(
        decision=_buy(policy),
        market=_frame(),
        protective_stop_price="149.000",
        fault=FaultInjection(
            kind=fault_kind,
            apply_effect_before_fault=apply_effect,
        ),
    )
    assert result.status == "VIRTUAL_EXECUTION_UNCERTAIN_RECONCILE_REQUIRED"
    assert result.reason_codes == ("NO_RETRY", "NEW_ENTRY_BLOCKED")
    assert engine.phase is EnginePhase.RECONCILE_REQUIRED
    with pytest.raises(E1EngineError, match="reconcile and acknowledge"):
        engine.process_decision(
            decision=_buy(policy),
            market=_frame(NOW + timedelta(seconds=1)),
            protective_stop_price="149.000",
        )
    before_restart = summarize_e1_journal(journal, policy=policy)
    assert before_restart.durable_intent_count == 1
    assert before_restart.virtual_execution_count == 1
    assert before_restart.unresolved_intent_count == 1

    restarted, restarted_journal, restarted_venue = _open_engine(tmp_path, run_id, policy)
    reconcile = restarted.boot_reconcile(now=NOW + timedelta(seconds=2))
    assert reconcile is (
        ReconcileStatus.RECOVERED_PLANNED_EFFECT
        if apply_effect
        else ReconcileStatus.RECOVERED_NO_EFFECT
    )
    assert restarted.phase is EnginePhase.RESTART_ACK_REQUIRED
    restarted.acknowledge_restart(
        now=NOW + timedelta(seconds=3), operator_acknowledged=True
    )
    assert restarted.phase is (
        EnginePhase.POSITION_OPEN if apply_effect else EnginePhase.READY_FLAT
    )
    assert (restarted_venue.position is not None) is apply_effect
    summary = summarize_e1_journal(restarted_journal, policy=policy)
    assert summary.unresolved_intent_count == 0
    assert summary.cardinality_invariant_ok is True
    assert dict(summary.fault_handled_counts)[fault_kind.value] == 1
    assert dict(summary.fault_handled_counts)[FaultKind.RESTART_RECONCILE.value] == 1
    assert summary.actual_post_count == 0


def test_deadman_during_unknown_state_is_durable_and_restart_cannot_resume(
    tmp_path,
) -> None:
    policy = E1Policy(cooldown_seconds=0, heartbeat_timeout_seconds=60)
    engine, journal, venue = _ready(tmp_path, "unknown-deadman-sticky", policy)
    engine.process_decision(
        decision=_buy(policy),
        market=_frame(),
        protective_stop_price="149.000",
        fault=FaultInjection(
            kind=FaultKind.UNKNOWN_RESULT,
            apply_effect_before_fault=True,
        ),
    )
    assert engine.phase is EnginePhase.RECONCILE_REQUIRED
    assert venue.position is not None
    deadman = engine.check_deadman(
        now=NOW + timedelta(seconds=61),
        market=_frame(NOW + timedelta(seconds=61)),
    )
    assert deadman.status == "RECONCILE_REQUIRED_DURABLE_KILL_NO_ATTEMPT"
    assert deadman.virtual_execution_attempted is False
    assert journal.kill_active is True
    assert journal.halted is True
    assert not any(
        record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is not None
        and record.action.value == "VIRTUAL_POSITION_SPECIFIC_SETTLEMENT"
        for record in journal.records
    )

    restarted, restarted_journal, restarted_venue = _open_engine(
        tmp_path, "unknown-deadman-sticky", policy
    )
    assert restarted.boot_reconcile(now=NOW + timedelta(seconds=62)) is (
        ReconcileStatus.RECOVERED_PLANNED_EFFECT
    )
    assert restarted.phase is EnginePhase.HALTED
    assert restarted_venue.position is not None
    assert restarted_journal.kill_active is True
    with pytest.raises(E1EngineError, match="not currently required"):
        restarted.acknowledge_restart(
            now=NOW + timedelta(seconds=63),
            operator_acknowledged=True,
        )


@pytest.mark.parametrize("apply_effect", [False, True])
@pytest.mark.parametrize("occurrence", range(5))
def test_crash_mid_virtual_execution_is_recovered_only_after_restart_reconcile(
    tmp_path, occurrence: int, apply_effect: bool
) -> None:
    run_id = f"crash-{int(apply_effect)}-{occurrence}"
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, run_id, policy)
    with pytest.raises(SimulatedShadowCrash, match="simulated crash"):
        engine.process_decision(
            decision=_buy(policy),
            market=_frame(),
            protective_stop_price="149.000",
            fault=FaultInjection(
                kind=FaultKind.CRASH_MID_VIRTUAL_EXECUTION,
                apply_effect_before_fault=apply_effect,
            ),
        )
    assert journal.unresolved_intents()
    assert [
        record.event_type
        for record in journal.records
        if record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
    ] == [JournalEventType.VIRTUAL_EXECUTION_STARTED]
    assert (venue.position is not None) is apply_effect

    restarted, restarted_journal, _ = _open_engine(tmp_path, run_id, policy)
    status = restarted.boot_reconcile(now=NOW + timedelta(seconds=1))
    assert status is (
        ReconcileStatus.RECOVERED_PLANNED_EFFECT
        if apply_effect
        else ReconcileStatus.RECOVERED_NO_EFFECT
    )
    assert restarted.phase is EnginePhase.RESTART_ACK_REQUIRED
    with pytest.raises(E1EngineError, match="reconcile and acknowledge"):
        restarted.process_decision(
            decision=_buy(policy),
            market=_frame(NOW + timedelta(seconds=2)),
            protective_stop_price="149.000",
        )
    restarted.acknowledge_restart(
        now=NOW + timedelta(seconds=3), operator_acknowledged=True
    )
    summary = summarize_e1_journal(restarted_journal, policy=policy)
    assert dict(summary.fault_handled_counts)[FaultKind.CRASH_MID_VIRTUAL_EXECUTION.value] == 1
    assert dict(summary.fault_handled_counts)[FaultKind.RESTART_RECONCILE.value] == 1
    assert summary.cardinality_invariant_ok is True


def test_partial_fill_produces_exact_reconcile_mismatch_and_sticky_halt(tmp_path) -> None:
    policy = E1Policy(
        fixed_virtual_units=2,
        max_virtual_loss_per_trade="3",  # type: ignore[arg-type]
        cooldown_seconds=0,
    )
    engine, journal, venue = _ready(tmp_path, "partial", policy)
    uncertain = engine.process_decision(
        decision=_buy(policy),
        market=_frame(),
        protective_stop_price="149.000",
        fault=FaultInjection(kind=FaultKind.PARTIAL_FILL),
    )
    assert uncertain.status == "VIRTUAL_EXECUTION_UNCERTAIN_RECONCILE_REQUIRED"
    assert venue.position is not None and venue.position.units == 1
    status = engine.reconcile_after_uncertain(now=NOW + timedelta(seconds=1))
    assert status is ReconcileStatus.MISMATCH_HALTED
    assert engine.phase is EnginePhase.HALTED
    summary = summarize_e1_journal(journal, policy=policy)
    assert summary.reconcile_mismatch_count == 1


def test_restart_never_auto_resumes_even_when_state_is_stable(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0)
    first, _journal, _venue = _ready(tmp_path, "stable-restart", policy)
    assert first.phase is EnginePhase.READY_FLAT

    restarted, _new_journal, _new_venue = _open_engine(tmp_path, "stable-restart", policy)
    assert restarted.boot_reconcile(now=NOW + timedelta(seconds=1)) is (
        ReconcileStatus.MATCHED_STABLE_STATE
    )
    assert restarted.phase is EnginePhase.RESTART_ACK_REQUIRED
    declined = restarted.acknowledge_restart(
        now=NOW + timedelta(seconds=2), operator_acknowledged=False
    )
    assert declined.status == "RESTART_ACK_NOT_PROVIDED"
    assert restarted.phase is EnginePhase.RESTART_ACK_REQUIRED
    accepted = restarted.acknowledge_restart(
        now=NOW + timedelta(seconds=3), operator_acknowledged=True
    )
    assert accepted.status == "RESTART_ACKNOWLEDGED"
    assert restarted.phase is EnginePhase.READY_FLAT


def test_stable_broker_state_mismatch_halts_without_auto_repair(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, _journal, venue = _ready(tmp_path, "mismatch", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    position = venue.position
    assert position is not None
    venue.path.write_text(
        json.dumps(
            {
                "schema_version": "e1-shadow-v1",
                "config_hash": policy.config_hash,
                "position": None,
            }
        ),
        encoding="utf-8",
    )

    restarted, restarted_journal, _ = _open_engine(tmp_path, "mismatch", policy)
    assert restarted.boot_reconcile(now=NOW + timedelta(seconds=1)) is (
        ReconcileStatus.MISMATCH_HALTED
    )
    assert restarted.phase is EnginePhase.HALTED
    assert (
        summarize_e1_journal(restarted_journal, policy=policy).reconcile_mismatch_count
        == 1
    )


def test_config_hash_drift_fails_before_engine_resume(tmp_path) -> None:
    original = E1Policy(cooldown_seconds=0)
    _ready(tmp_path, "config-drift", original)
    changed = E1Policy(cooldown_seconds=1)
    root, journal_path, _venue_path = _paths(tmp_path, "config-drift")
    with pytest.raises(E1PersistenceError, match="config hash mismatch"):
        ShadowIntentJournal(
            root=root,
            path=journal_path,
            run_id="config-drift",
            config_hash=changed.config_hash,
        )


@pytest.mark.parametrize("corrupt", ["{not-json}\n", "\n"])
def test_corrupt_or_truncated_journal_fails_closed(tmp_path, corrupt: str) -> None:
    policy = E1Policy()
    root, journal_path, _venue_path = _paths(tmp_path, "corrupt")
    root.mkdir(parents=True)
    journal_path.write_text(corrupt, encoding="utf-8")
    with pytest.raises(E1PersistenceError):
        ShadowIntentJournal(
            root=root,
            path=journal_path,
            run_id="corrupt",
            config_hash=policy.config_hash,
        )


def test_all_journal_records_stamp_the_frozen_config_hash(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, _venue = _ready(tmp_path, "hash-stamp", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    assert journal.records
    assert {record.config_hash for record in journal.records} == {policy.config_hash}
    assert all(len(record.config_hash) == 64 for record in journal.records)


def test_fault_harness_never_creates_retry_records(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, _venue = _ready(tmp_path, "no-retry", policy)
    engine.process_decision(
        decision=_buy(policy),
        market=_frame(),
        protective_stop_price="149.000",
        fault=FaultInjection(kind=FaultKind.UNKNOWN_RESULT),
    )
    statuses = [record.status_label for record in journal.records]
    assert sum(label == "VIRTUAL_EXECUTION_STARTED_ONCE" for label in statuses) == 1
    assert not any("RETRY" in label and "NO_RETRY" not in label for label in statuses)
    assert canonical_timestamp(NOW) == journal.records[0].timestamp


def test_actual_intent_fsync_failure_has_zero_virtual_effect(tmp_path, monkeypatch) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "intent-fsync", policy)

    def fail_fsync(_fd):
        raise OSError("injected fsync failure")

    monkeypatch.setattr(persistence_module.os, "fsync", fail_fsync)
    with pytest.raises(E1EngineError, match="before virtual execution"):
        engine.process_decision(
            decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
        )
    assert engine.phase is EnginePhase.HALTED
    assert venue.position is None
    assert not any(
        record.event_type is JournalEventType.INTENT_PREPARED for record in journal.records
    )


def test_execution_start_fsync_failure_still_has_zero_virtual_effect(
    tmp_path, monkeypatch
) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "start-fsync", policy)
    real_fsync = persistence_module.os.fsync
    calls = 0

    def fail_second_fsync(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected execution-start fsync failure")
        return real_fsync(fd)

    monkeypatch.setattr(persistence_module.os, "fsync", fail_second_fsync)
    with pytest.raises(E1EngineError, match="before virtual execution"):
        engine.process_decision(
            decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
        )
    assert venue.position is None
    assert sum(
        record.event_type is JournalEventType.INTENT_PREPARED for record in journal.records
    ) == 1
    assert not any(
        record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        for record in journal.records
    )


def test_virtual_venue_fsync_failure_becomes_unknown_and_reconcile_required(
    tmp_path, monkeypatch
) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "venue-fsync", policy)
    real_persist = venue._persist
    real_fsync = persistence_module.os.fsync

    def fail_venue_fsync(position, *, executor_key, **persist_contract):
        def fail(_fd):
            raise OSError("injected venue fsync failure")

        monkeypatch.setattr(persistence_module.os, "fsync", fail)
        try:
            return real_persist(
                position,
                executor_key=executor_key,
                **persist_contract,
            )
        finally:
            monkeypatch.setattr(persistence_module.os, "fsync", real_fsync)

    monkeypatch.setattr(venue, "_persist", fail_venue_fsync)
    with pytest.raises(E1EngineError, match="persistence outcome is unknown"):
        engine.process_decision(
            decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
        )
    assert engine.phase is EnginePhase.RECONCILE_REQUIRED
    assert venue.position is None
    assert journal.unresolved_intents()
    assert any(
        record.status_label == "VIRTUAL_VENUE_PERSISTENCE_UNKNOWN_RECONCILE_REQUIRED"
        for record in journal.records
    )


def test_terminal_journal_failure_after_effect_blocks_until_restart_reconcile(
    tmp_path, monkeypatch
) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "terminal-fsync", policy)
    original_append = journal.append

    def fail_terminal(**kwargs):
        if kwargs["event_type"] is JournalEventType.VIRTUAL_EXECUTION_CONFIRMED:
            raise E1PersistenceError("injected terminal journal failure")
        return original_append(**kwargs)

    monkeypatch.setattr(journal, "append", fail_terminal)
    with pytest.raises(E1EngineError, match="terminal journal persistence failed"):
        engine.process_decision(
            decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
        )
    assert engine.phase is EnginePhase.RECONCILE_REQUIRED
    assert venue.position is not None
    assert journal.unresolved_intents()

    restarted, restarted_journal, restarted_venue = _open_engine(
        tmp_path, "terminal-fsync", policy
    )
    assert restarted.boot_reconcile(now=NOW + timedelta(seconds=1)) is (
        ReconcileStatus.RECOVERED_PLANNED_EFFECT
    )
    assert restarted.phase is EnginePhase.RESTART_ACK_REQUIRED
    assert restarted_venue.position is not None
    assert not restarted_journal.unresolved_intents()


def test_in_memory_halt_blocks_deadman_after_double_persistence_failure(
    tmp_path, monkeypatch
) -> None:
    policy = E1Policy(cooldown_seconds=0, heartbeat_timeout_seconds=60)
    engine, journal, venue = _ready(tmp_path, "double-persistence-failure", policy)
    original_open = venue._open_position
    original_append = journal.append

    def apply_then_raise(position, *, executor_key):
        original_open(position, executor_key=executor_key)
        raise E1PersistenceError("injected post-effect venue uncertainty")

    def fail_uncertain_record(**kwargs):
        if kwargs["event_type"] is JournalEventType.VIRTUAL_EXECUTION_UNCERTAIN:
            raise E1PersistenceError("injected uncertainty journal failure")
        return original_append(**kwargs)

    monkeypatch.setattr(venue, "_open_position", apply_then_raise)
    monkeypatch.setattr(journal, "append", fail_uncertain_record)
    with pytest.raises(E1EngineError, match="persistence outcome is unknown"):
        engine.process_decision(
            decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
        )
    assert engine.phase is EnginePhase.HALTED
    assert journal.halted is False
    assert journal.kill_active is False
    assert venue.position is not None
    assert journal.unresolved_intents()
    settlement_starts_before = sum(
        record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is not None
        and record.action.value == "VIRTUAL_POSITION_SPECIFIC_SETTLEMENT"
        for record in journal.records
    )

    monkeypatch.setattr(journal, "append", original_append)
    result = engine.check_deadman(
        now=NOW + timedelta(seconds=61),
        market=_frame(NOW + timedelta(seconds=61)),
    )
    assert result.status == "RECONCILE_REQUIRED_DURABLE_KILL_NO_ATTEMPT"
    assert result.virtual_execution_attempted is False
    assert journal.kill_active is True
    assert journal.halted is True
    assert venue.position is not None
    assert sum(
        record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is not None
        and record.action.value == "VIRTUAL_POSITION_SPECIFIC_SETTLEMENT"
        for record in journal.records
    ) == settlement_starts_before


def test_rejected_terminal_persistence_failure_requires_restart_without_retry(
    tmp_path, monkeypatch
) -> None:
    policy = E1Policy(cooldown_seconds=0, heartbeat_timeout_seconds=60)
    engine, journal, venue = _ready(tmp_path, "rejected-terminal-failure", policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    assert venue.position is not None
    original_append = journal.append

    def fail_rejected_terminal(**kwargs):
        if kwargs["event_type"] is JournalEventType.VIRTUAL_EXECUTION_REJECTED:
            raise E1PersistenceError("injected rejected-terminal journal failure")
        return original_append(**kwargs)

    monkeypatch.setattr(journal, "append", fail_rejected_terminal)
    with pytest.raises(E1EngineError, match="rejection occurred"):
        engine.process_decision(
            decision=build_settlement_decision(
                position_ref=venue.position.position_ref,
                config_hash=policy.config_hash,
                reason_code="REJECTED_TERMINAL_FAILURE_FIXTURE",
            ),
            market=_frame(NOW + timedelta(seconds=1)),
            fault=FaultInjection(kind=FaultKind.REJECTED),
        )
    assert engine.phase is EnginePhase.RECONCILE_REQUIRED
    assert venue.position is not None
    assert journal.unresolved_intents()
    starts_before = sum(
        record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is not None
        and record.action.value == "VIRTUAL_POSITION_SPECIFIC_SETTLEMENT"
        for record in journal.records
    )
    monkeypatch.setattr(journal, "append", original_append)
    blocked = engine.check_deadman(
        now=NOW + timedelta(seconds=61),
        market=_frame(NOW + timedelta(seconds=61)),
    )
    assert blocked.status == "RECONCILE_REQUIRED_DURABLE_KILL_NO_ATTEMPT"
    assert blocked.virtual_execution_attempted is False
    assert journal.kill_active is True
    assert journal.halted is True
    assert sum(
        record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is not None
        and record.action.value == "VIRTUAL_POSITION_SPECIFIC_SETTLEMENT"
        for record in journal.records
    ) == starts_before

    restarted, restarted_journal, restarted_venue = _open_engine(
        tmp_path, "rejected-terminal-failure", policy
    )
    assert restarted.boot_reconcile(now=NOW + timedelta(seconds=2)) is (
        ReconcileStatus.RECOVERED_NO_EFFECT
    )
    assert restarted.phase is EnginePhase.HALTED
    assert restarted_venue.position is not None
    assert restarted_journal.halted is True
    assert sum(
        record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.action is not None
        and record.action.value == "VIRTUAL_POSITION_SPECIFIC_SETTLEMENT"
        for record in restarted_journal.records
    ) == starts_before


def test_concurrent_journal_instances_fail_before_duplicate_sequence(tmp_path) -> None:
    policy = E1Policy()
    root, journal_path, _venue_path = _paths(tmp_path, "concurrent-journal")
    first = ShadowIntentJournal(
        root=root,
        path=journal_path,
        run_id="concurrent-journal",
        config_hash=policy.config_hash,
    )
    second = ShadowIntentJournal(
        root=root,
        path=journal_path,
        run_id="concurrent-journal",
        config_hash=policy.config_hash,
    )
    flat = position_digest(None)
    first.append(
        event_type=JournalEventType.RUN_STARTED,
        timestamp=canonical_timestamp(NOW),
        status_label="FIRST_WRITER",
        expected_state_digest=flat,
        observed_state_digest=flat,
        position_count=0,
    )
    with pytest.raises(E1PersistenceError, match="concurrent journal"):
        second.append(
            event_type=JournalEventType.RUN_STARTED,
            timestamp=canonical_timestamp(NOW),
            status_label="SECOND_WRITER_BLOCKED",
            expected_state_digest=flat,
            observed_state_digest=flat,
            position_count=0,
        )
    reloaded = ShadowIntentJournal(
        root=root,
        path=journal_path,
        run_id="concurrent-journal",
        config_hash=policy.config_hash,
    )
    assert len(reloaded.records) == 1


def test_same_journal_instance_serializes_concurrent_appends(tmp_path) -> None:
    policy = E1Policy()
    root, journal_path, _venue_path = _paths(tmp_path, "same-journal")
    journal = ShadowIntentJournal(
        root=root,
        path=journal_path,
        run_id="same-journal",
        config_hash=policy.config_hash,
    )
    flat = position_digest(None)
    workers = 8
    barrier = Barrier(workers)

    def append_one(index: int) -> int:
        barrier.wait()
        return journal.append(
            event_type=JournalEventType.NO_ACTION_RECORDED,
            timestamp=canonical_timestamp(NOW),
            status_label=f"CONCURRENT_NO_ACTION_{index}",
            expected_state_digest=flat,
            observed_state_digest=flat,
            position_count=0,
        ).sequence

    with ThreadPoolExecutor(max_workers=workers) as executor:
        sequences = tuple(executor.map(append_one, range(workers)))

    assert sorted(sequences) == list(range(workers))
    reloaded = ShadowIntentJournal(
        root=root,
        path=journal_path,
        run_id="same-journal",
        config_hash=policy.config_hash,
    )
    assert [record.sequence for record in reloaded.records] == list(range(workers))


def test_concurrent_virtual_venue_instances_fail_closed(tmp_path) -> None:
    policy = E1Policy()
    root, _journal_path, venue_path = _paths(tmp_path, "concurrent-venue")
    first = VirtualVenueStateStore(
        root=root, path=venue_path, config_hash=policy.config_hash
    )
    second = VirtualVenueStateStore(
        root=root, path=venue_path, config_hash=policy.config_hash
    )
    first_key = object()
    second_key = object()
    first._bind_executor(first_key)
    second._bind_executor(second_key)
    position = VirtualPosition(
        position_ref="vposition:concurrent",
        symbol="USD_JPY",
        side=PositionSide.LONG,
        units=1,
        entry_price=persistence_module.finite_decimal("150", field_name="entry"),
        protective_stop_price=persistence_module.finite_decimal("149", field_name="stop"),
    )
    first._open_position(position, executor_key=first_key)
    with pytest.raises(E1PersistenceError, match="concurrent virtual venue"):
        second._open_position(position, executor_key=second_key)


def test_same_virtual_venue_instance_allows_exactly_one_concurrent_open(tmp_path) -> None:
    policy = E1Policy()
    root, _journal_path, venue_path = _paths(tmp_path, "same-venue")
    venue = VirtualVenueStateStore(
        root=root,
        path=venue_path,
        config_hash=policy.config_hash,
    )
    executor_key = object()
    venue._bind_executor(executor_key)
    barrier = Barrier(2)

    def attempt(position_ref: str) -> str:
        position = VirtualPosition(
            position_ref=position_ref,
            symbol="USD_JPY",
            side=PositionSide.LONG,
            units=1,
            entry_price=persistence_module.finite_decimal("150", field_name="entry"),
            protective_stop_price=persistence_module.finite_decimal(
                "149", field_name="stop"
            ),
        )
        barrier.wait()
        try:
            venue._open_position(position, executor_key=executor_key)
        except E1PersistenceError:
            return "BLOCKED"
        return "OPENED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(
            executor.map(attempt, ("vposition:concurrent-a", "vposition:concurrent-b"))
        )

    assert sorted(outcomes) == ["BLOCKED", "OPENED"]
    assert venue.position is not None
    assert venue.position.position_ref in {
        "vposition:concurrent-a",
        "vposition:concurrent-b",
    }


def test_virtual_venue_temporary_symlink_escape_is_blocked(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue = _ready(tmp_path, "venue-symlink", policy)
    outside = tmp_path / "outside.json"
    outside.write_text("SAFE\n", encoding="utf-8")
    temporary = venue.path.with_suffix(f"{venue.path.suffix}.tmp")
    temporary.symlink_to(outside)
    with pytest.raises(E1EngineError, match="persistence outcome is unknown"):
        engine.process_decision(
            decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
        )
    assert outside.read_text(encoding="utf-8") == "SAFE\n"
    assert venue.position is None
    assert journal.unresolved_intents()
