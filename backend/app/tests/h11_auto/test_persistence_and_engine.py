from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.h11_auto.boundary import (
    FakeNotifier,
    FakePositionExitOutcome,
    FakePositionExitSender,
    FakeProtectedEntryOutcome,
    FakeProtectedEntrySender,
    H11AutoBoundaryError,
    NotificationCategory,
    RefusingProtectedEntrySender,
)
from app.h11_auto.contracts import (
    FormalHorizon,
    FormalSignal,
    PhaseAExecutionPolicy,
    SignalDecision,
)
from app.h11_auto.engine import FakeCycleStatus, H11AutoPhaseAEngine
from app.h11_auto.persistence import (
    H11AutoPersistenceError,
    H11AutoProcessLock,
    H11AutoStateStore,
)
from app.h11_auto.risk import PhaseASafetySnapshot
from app.h11_auto.state_machine import AutoCycleState

NOW = datetime(2026, 7, 15, 2, 0, tzinfo=UTC)


def signal(decision: SignalDecision = SignalDecision.BUY) -> FormalSignal:
    return FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:synthetic-signal-config",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=NOW,
        valid_until_utc=NOW + timedelta(minutes=10),
        decision=decision,
        probability_up=Decimal("0.61"),
    )


def policy() -> PhaseAExecutionPolicy:
    return PhaseAExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:synthetic-signal-config",
        selected_horizon=FormalHorizon.MINUTES_10,
    )


def safety(**overrides: object) -> PhaseASafetySnapshot:
    values: dict[str, object] = {
        "boot_reconciled": True,
        "process_lock_held": True,
        "data_fresh": True,
        "clock_synchronized": True,
        "notification_path_ready": True,
    }
    values.update(overrides)
    return PhaseASafetySnapshot(**values)  # type: ignore[arg-type]


def test_store_persists_intent_before_attempt_and_refuses_second_attempt(
    tmp_path: Path,
) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    cycle = store.create_intent(signal=signal(), policy=policy(), now_utc=NOW)
    assert cycle.state is AutoCycleState.INTENT_PERSISTED
    assert cycle.attempt_count == 0
    started = store.record_attempt_started(intent_id=cycle.intent_id, now_utc=NOW)
    assert started.state is AutoCycleState.PROTECTED_ENTRY_PENDING
    assert started.attempt_count == 1
    assert started.exit_attempt_count == 0
    assert started.entry_day_jst == "2026-07-15"
    assert store.entry_attempts_on_jst_day(now_utc=NOW) == 1
    with pytest.raises(H11AutoPersistenceError, match="second attempt"):
        store.record_attempt_started(intent_id=cycle.intent_id, now_utc=NOW)


def test_run_generation_policy_is_persisted_and_immutable(tmp_path: Path) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    bound = store.bind_run_generation(
        generation_label="PHASE_B_GENERATION_001",
        policy=policy(),
        risk_policy_label="RISK_POLICY_001",
        risk_policy_digest="risk-digest-001",
        dead_man_policy_label="DEAD_MAN_POLICY_001",
        dead_man_policy_digest="dead-man-digest-001",
    )
    assert bound.generation_label == "PHASE_B_GENERATION_001"
    assert bound.selected_horizon == "10m"
    assert store.load_run_generation_safe() == bound
    assert (
        store.bind_run_generation(
            generation_label="PHASE_B_GENERATION_001",
            policy=policy(),
            risk_policy_label="RISK_POLICY_001",
            risk_policy_digest="risk-digest-001",
            dead_man_policy_label="DEAD_MAN_POLICY_001",
            dead_man_policy_digest="dead-man-digest-001",
        )
        == bound
    )
    with pytest.raises(H11AutoPersistenceError, match="policy mismatch"):
        store.bind_run_generation(
            generation_label="PHASE_B_GENERATION_001",
            policy=policy(),
            risk_policy_label="RISK_POLICY_001",
            risk_policy_digest="risk-digest-changed",
            dead_man_policy_label="DEAD_MAN_POLICY_001",
            dead_man_policy_digest="dead-man-digest-001",
        )


def test_state_and_lock_symlinks_are_refused(tmp_path: Path) -> None:
    state_target = tmp_path / "state-target.sqlite3"
    state_target.touch()
    state_link = tmp_path / "state-link.sqlite3"
    state_link.symlink_to(state_target)
    with pytest.raises(H11AutoPersistenceError, match="state path"):
        H11AutoStateStore(state_link)

    lock_target = tmp_path / "lock-target"
    lock_target.touch()
    lock_link = tmp_path / "lock-link"
    lock_link.symlink_to(lock_target)
    with pytest.raises(H11AutoPersistenceError, match="lock path"):
        H11AutoProcessLock(lock_link).acquire()

    state_directory = tmp_path / "state-directory"
    state_directory.mkdir()
    with pytest.raises(H11AutoPersistenceError, match="regular file"):
        H11AutoStateStore(state_directory)
    lock_directory = tmp_path / "lock-directory"
    lock_directory.mkdir()
    with pytest.raises(H11AutoPersistenceError, match="regular file"):
        H11AutoProcessLock(lock_directory).acquire()


def test_store_refuses_duplicate_signal_and_parallel_active_intent(tmp_path: Path) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    store.create_intent(signal=signal(), policy=policy(), now_utc=NOW)
    with pytest.raises(H11AutoPersistenceError, match="active cycle"):
        store.create_intent(signal=signal(), policy=policy(), now_utc=NOW)
    assert store.active_intent_count() == 1


def test_hash_linked_journal_detects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "auto.sqlite3"
    store = H11AutoStateStore(path)
    cycle = store.create_intent(signal=signal(), policy=policy(), now_utc=NOW)
    store.record_attempt_started(intent_id=cycle.intent_id, now_utc=NOW)
    summary = store.verify_journal()
    assert summary.valid is True
    assert summary.event_count == 2
    assert summary.actual_post_count == 0
    assert summary.broker_write_performed is False
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE safe_events SET state_safe_label = 'TAMPERED' WHERE sequence = 1"
        )
    with pytest.raises(H11AutoPersistenceError, match="verification"):
        store.verify_journal()


def test_nonblocking_process_lock_refuses_second_holder(tmp_path: Path) -> None:
    path = tmp_path / "auto.lock"
    first = H11AutoProcessLock(path)
    second = H11AutoProcessLock(path)
    assert first.acquire() is True
    assert first.held is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()


def test_concurrent_entry_attempt_compare_and_set_allows_exactly_one(tmp_path: Path) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    cycle = store.create_intent(signal=signal(), policy=policy(), now_utc=NOW)

    def attempt() -> str:
        try:
            store.record_attempt_started(intent_id=cycle.intent_id, now_utc=NOW)
        except H11AutoPersistenceError:
            return "REFUSED"
        return "STARTED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["REFUSED", "STARTED"]
    assert store.load_cycle(cycle.intent_id).attempt_count == 1


def test_concurrent_duplicate_intent_creation_allows_exactly_one(tmp_path: Path) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")

    def create() -> str:
        try:
            store.create_intent(signal=signal(), policy=policy(), now_utc=NOW)
        except H11AutoPersistenceError:
            return "REFUSED"
        return "CREATED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: create(), range(2)))
    assert sorted(results) == ["CREATED", "REFUSED"]
    assert store.active_intent_count() == 1


def test_halt_is_persistently_latched_and_refuses_new_intent(tmp_path: Path) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    cycle = store.create_intent(signal=signal(), policy=policy(), now_utc=NOW)
    store.transition(
        intent_id=cycle.intent_id,
        target=AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        event_category="HALTED_SYNTHETIC",
        now_utc=NOW,
        halt_reason="SYNTHETIC_TEST_HALT",
    )
    assert store.halt_latched() is True
    next_signal = FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:synthetic-signal-config",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=NOW + timedelta(minutes=1),
        valid_until_utc=NOW + timedelta(minutes=11),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.62"),
    )
    with pytest.raises(H11AutoPersistenceError, match="halt is latched"):
        store.create_intent(signal=next_signal, policy=policy(), now_utc=NOW)


def test_engine_enforces_persistent_one_entry_per_jst_day_after_flat(
    tmp_path: Path,
) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    entry_sender = FakeProtectedEntrySender(
        FakeProtectedEntryOutcome.ACCEPTED_AND_PROTECTED
    )
    engine = H11AutoPhaseAEngine(
        store=store,
        sender=entry_sender,
        exit_sender=FakePositionExitSender(FakePositionExitOutcome.ACCEPTED_AND_FLAT),
    )
    engine.run_signal_once_synthetic(
        signal=signal(), policy=policy(), safety=safety(), now_utc=NOW
    )
    engine.complete_exit_once_synthetic(
        intent_id=entry_sender.calls[0], now_utc=NOW + timedelta(minutes=1)
    )
    next_signal = FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:synthetic-signal-config",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=NOW + timedelta(minutes=2),
        valid_until_utc=NOW + timedelta(minutes=12),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.62"),
    )
    result = engine.run_signal_once_synthetic(
        signal=next_signal,
        policy=policy(),
        safety=safety(entries_today=0),
        now_utc=NOW + timedelta(minutes=2),
    )
    assert result.status is FakeCycleStatus.BLOCKED_SAFE
    assert result.blocked_reasons == ("MAX_ENTRIES_PER_DAY_REACHED",)
    assert len(entry_sender.calls) == 1


def test_fake_accepted_cycle_reaches_protected_state_without_network(tmp_path: Path) -> None:
    sender = FakeProtectedEntrySender(FakeProtectedEntryOutcome.ACCEPTED_AND_PROTECTED)
    notifier = FakeNotifier()
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    result = H11AutoPhaseAEngine(
        store=store, sender=sender, notifier=notifier
    ).run_signal_once_synthetic(
        signal=signal(), policy=policy(), safety=safety(), now_utc=NOW
    )
    assert result.status is FakeCycleStatus.POSITION_PROTECTED_SYNTHETIC
    assert result.final_state is AutoCycleState.POSITION_PROTECTED
    assert result.attempt_count == 1
    assert result.exit_attempt_count == 0
    assert result.actual_post_count == 0
    assert result.broker_write_performed is False
    assert result.network_access_performed is False
    assert len(sender.calls) == 1
    assert notifier.events == [
        NotificationCategory.INTENT_RECORDED,
        NotificationCategory.POSITION_PROTECTED,
    ]


@pytest.mark.parametrize(
    "outcome",
    [
        FakeProtectedEntryOutcome.REJECTED,
        FakeProtectedEntryOutcome.UNKNOWN,
        FakeProtectedEntryOutcome.TIMEOUT,
        FakeProtectedEntryOutcome.PARTIAL_FILL_SIZE_MISMATCH,
    ],
)
def test_every_nonaccepted_fake_outcome_halts_without_retry(
    tmp_path: Path, outcome: FakeProtectedEntryOutcome
) -> None:
    sender = FakeProtectedEntrySender(outcome)
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    result = H11AutoPhaseAEngine(store=store, sender=sender).run_signal_once_synthetic(
        signal=signal(), policy=policy(), safety=safety(), now_utc=NOW
    )
    assert result.status is FakeCycleStatus.HALTED_SAFE
    assert result.final_state is AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED
    assert result.attempt_count == 1
    assert len(sender.calls) == 1
    assert result.actual_post_count == 0


def test_stay_and_blocked_gate_create_no_intent(tmp_path: Path) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    engine = H11AutoPhaseAEngine(
        store=store,
        sender=FakeProtectedEntrySender(FakeProtectedEntryOutcome.ACCEPTED_AND_PROTECTED),
    )
    stay = engine.run_signal_once_synthetic(
        signal=signal(SignalDecision.STAY),
        policy=policy(),
        safety=safety(),
        now_utc=NOW,
    )
    assert stay.status is FakeCycleStatus.NO_ACTION_STAY
    assert stay.intent_created is False
    blocked = engine.run_signal_once_synthetic(
        signal=signal(),
        policy=policy(),
        safety=safety(external_or_manual_position_detected=True),
        now_utc=NOW,
    )
    assert blocked.status is FakeCycleStatus.BLOCKED_SAFE
    assert blocked.intent_created is False
    assert store.active_intent_count() == 0


def test_stay_still_requires_matching_unexpired_formal_contract(tmp_path: Path) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    mismatched_policy = PhaseAExecutionPolicy(
        strategy_version="OTHER",
        signal_config_hash="sha256:other",
        selected_horizon=FormalHorizon.MINUTES_10,
    )
    result = H11AutoPhaseAEngine(store=store).run_signal_once_synthetic(
        signal=signal(SignalDecision.STAY),
        policy=mismatched_policy,
        safety=safety(),
        now_utc=NOW + timedelta(minutes=11),
    )
    assert result.status is FakeCycleStatus.BLOCKED_SAFE
    assert result.blocked_reasons == (
        "SIGNAL_POLICY_MISMATCH",
        "SIGNAL_EXPIRED_OR_CLOCK_INVALID",
    )
    assert result.intent_created is False


def test_default_sender_is_structurally_refusing() -> None:
    sender = RefusingProtectedEntrySender()
    assert not sender
    assert sender.actual_post_count == 0
    assert sender.network_access_performed is False
    with pytest.raises(H11AutoBoundaryError, match="ACTUAL_TRANSPORT_ABSENT"):
        sender.send_once_synthetic(intent_id="safe-synthetic-intent")


def test_engine_rejects_sender_type_outside_phase_a_fake_boundary(tmp_path: Path) -> None:
    class UntrustedSender:
        fake_only = False
        network_access_performed = False
        actual_post_count = 0

        def send_once_synthetic(self, *, intent_id: str) -> FakeProtectedEntryOutcome:
            del intent_id
            return FakeProtectedEntryOutcome.ACCEPTED_AND_PROTECTED

    with pytest.raises(H11AutoBoundaryError, match="SENDER_TYPE_REFUSED"):
        H11AutoPhaseAEngine(
            store=H11AutoStateStore(tmp_path / "auto.sqlite3"),
            sender=UntrustedSender(),  # type: ignore[arg-type]
        )


def test_engine_rejects_subclassed_fake_boundaries(tmp_path: Path) -> None:
    class SenderSubclass(FakeProtectedEntrySender):
        pass

    class NotifierSubclass(FakeNotifier):
        pass

    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    with pytest.raises(H11AutoBoundaryError, match="ENTRY_SENDER_TYPE_REFUSED"):
        H11AutoPhaseAEngine(
            store=store,
            sender=SenderSubclass(FakeProtectedEntryOutcome.ACCEPTED_AND_PROTECTED),
        )
    with pytest.raises(H11AutoBoundaryError, match="NOTIFIER_TYPE_REFUSED"):
        H11AutoPhaseAEngine(store=store, notifier=NotifierSubclass())


def test_full_fake_cycle_reaches_flat_with_one_entry_and_one_exit_attempt(
    tmp_path: Path,
) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    entry_sender = FakeProtectedEntrySender(
        FakeProtectedEntryOutcome.ACCEPTED_AND_PROTECTED
    )
    exit_sender = FakePositionExitSender(FakePositionExitOutcome.ACCEPTED_AND_FLAT)
    engine = H11AutoPhaseAEngine(
        store=store, sender=entry_sender, exit_sender=exit_sender
    )
    opened = engine.run_signal_once_synthetic(
        signal=signal(), policy=policy(), safety=safety(), now_utc=NOW
    )
    intent_id = entry_sender.calls[0]
    flat = engine.complete_exit_once_synthetic(
        intent_id=intent_id, now_utc=NOW + timedelta(minutes=5)
    )
    assert opened.final_state is AutoCycleState.POSITION_PROTECTED
    assert flat.status is FakeCycleStatus.FLAT_RECONCILED_SYNTHETIC
    assert flat.final_state is AutoCycleState.FLAT_RECONCILED
    assert flat.attempt_count == 1
    assert flat.exit_attempt_count == 1
    assert len(entry_sender.calls) == 1
    assert len(exit_sender.calls) == 1
    assert flat.actual_post_count == 0
    assert store.active_intent_count() == 0
    assert store.verify_journal().event_count == 5


@pytest.mark.parametrize(
    "outcome",
    [
        FakePositionExitOutcome.REJECTED,
        FakePositionExitOutcome.UNKNOWN,
        FakePositionExitOutcome.TIMEOUT,
    ],
)
def test_nonaccepted_exit_halts_and_cannot_be_attempted_twice(
    tmp_path: Path, outcome: FakePositionExitOutcome
) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    entry_sender = FakeProtectedEntrySender(
        FakeProtectedEntryOutcome.ACCEPTED_AND_PROTECTED
    )
    exit_sender = FakePositionExitSender(outcome)
    engine = H11AutoPhaseAEngine(
        store=store, sender=entry_sender, exit_sender=exit_sender
    )
    engine.run_signal_once_synthetic(
        signal=signal(), policy=policy(), safety=safety(), now_utc=NOW
    )
    result = engine.complete_exit_once_synthetic(
        intent_id=entry_sender.calls[0], now_utc=NOW + timedelta(minutes=5)
    )
    assert result.status is FakeCycleStatus.HALTED_SAFE
    assert result.final_state is AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED
    assert result.exit_attempt_count == 1
    assert len(exit_sender.calls) == 1
    with pytest.raises(H11AutoPersistenceError):
        engine.complete_exit_once_synthetic(
            intent_id=entry_sender.calls[0], now_utc=NOW + timedelta(minutes=6)
        )


def test_engine_with_default_refusing_sender_halts_after_one_synthetic_attempt(
    tmp_path: Path,
) -> None:
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    result = H11AutoPhaseAEngine(store=store).run_signal_once_synthetic(
        signal=signal(), policy=policy(), safety=safety(), now_utc=NOW
    )
    assert result.status is FakeCycleStatus.HALTED_SAFE
    assert result.final_state is AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED
    assert result.attempt_count == 1
    assert result.blocked_reasons == ("SYNTHETIC_BOUNDARY_REFUSED",)
    assert result.actual_post_count == 0


@pytest.mark.parametrize("fail_stage", ["intent", "protected"])
def test_notification_failure_halts_fail_closed(
    tmp_path: Path, fail_stage: str
) -> None:
    fail_category = (
        NotificationCategory.INTENT_RECORDED
        if fail_stage == "intent"
        else NotificationCategory.POSITION_PROTECTED
    )
    notifier = FakeNotifier(fail_categories=frozenset({fail_category}))
    store = H11AutoStateStore(tmp_path / "auto.sqlite3")
    result = H11AutoPhaseAEngine(
        store=store,
        sender=FakeProtectedEntrySender(
            FakeProtectedEntryOutcome.ACCEPTED_AND_PROTECTED
        ),
        notifier=notifier,
    ).run_signal_once_synthetic(
        signal=signal(), policy=policy(), safety=safety(), now_utc=NOW
    )
    assert result.status is FakeCycleStatus.HALTED_SAFE
    assert result.final_state is AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED
    assert result.actual_post_count == 0
    if fail_stage == "intent":
        assert result.attempt_count == 0
    else:
        assert result.attempt_count == 1
