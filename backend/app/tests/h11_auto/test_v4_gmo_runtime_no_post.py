from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.h11_auto.boundary import FakeNotifier
from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import (
    DeadManPolicy,
    DeadManStore,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
)
from app.h11_auto.v4_gmo_boundary import FakeV4GmoBroker, RefusingV4GmoBroker
from app.h11_auto.v4_gmo_contracts import (
    V4GmoAction,
    V4GmoBrokerSnapshot,
    V4GmoEntryStatus,
    V4GmoExecutionPolicy,
    V4GmoProtectionStatus,
    V4GmoSyntheticOutcome,
)
from app.h11_auto.v4_gmo_persistence import V4GmoPersistenceError, V4GmoStateStore
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_gmo_runtime import (
    V4GmoRuntimeError,
    V4GmoRuntimeStatus,
    run_v4_gmo_once_no_post,
)

NOW = datetime(2026, 7, 15, 2, 0, tzinfo=UTC)


def signal(*, decision: SignalDecision = SignalDecision.BUY) -> FormalSignal:
    return FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:runtime-signal-config",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=NOW,
        valid_until_utc=NOW + timedelta(minutes=10),
        decision=decision,
        probability_up=Decimal("0.61"),
    )


def policy() -> V4GmoExecutionPolicy:
    return V4GmoExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:runtime-signal-config",
        selected_horizon=FormalHorizon.MINUTES_10,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def risk_policy() -> PhaseBRiskPolicy:
    return PhaseBRiskPolicy(
        policy_label="H11_V4_RISK_V1",
        per_trade_loss_bound_jpy=5_000,
        daily_loss_limit_jpy=10_000,
        monthly_loss_limit_jpy=50_000,
        maximum_consecutive_losses=5,
    )


def runtime_stores(
    tmp_path: Path,
) -> tuple[PhaseBRiskStore, PhaseBRiskPolicy, DeadManStore]:
    risk = risk_policy()
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


def filled(*, protection: bool = False) -> V4GmoBrokerSnapshot:
    return V4GmoBrokerSnapshot(
        fresh=True,
        result_known=True,
        position_count=1,
        position_side=SignalDecision.BUY,
        filled_size=10_000,
        pending_entry_size=0,
        protection_size=10_000 if protection else 0,
        entry_status=V4GmoEntryStatus.FILLED,
        protection_status=(
            V4GmoProtectionStatus.EXACT_MATCH
            if protection
            else V4GmoProtectionStatus.NONE
        ),
    )


def success_broker() -> FakeV4GmoBroker:
    return FakeV4GmoBroker(
        outcomes={
            V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.ACCEPTED],
            V4GmoAction.EXACT_SIZE_OCO_PROTECTION: [V4GmoSyntheticOutcome.ACCEPTED],
        },
        snapshots=[V4GmoBrokerSnapshot.flat(), filled(), filled(protection=True)],
    )


def run(
    tmp_path: Path,
    *,
    broker: FakeV4GmoBroker | None = None,
    notifier: FakeNotifier | None = None,
    input_signal: FormalSignal | None = None,
    generation_label: str = "H11_V4_GMO_10M_G001",
):
    risk_store, risk, dead_man = runtime_stores(tmp_path)
    return run_v4_gmo_once_no_post(
        signal=input_signal or signal(),
        policy=policy(),
        state_path=tmp_path / "v4.sqlite3",
        lock_path=tmp_path / "v4.lock",
        risk_store=risk_store,
        risk_policy=risk,
        dead_man_store=dead_man,
        notifier=notifier if notifier is not None else FakeNotifier(),
        broker=broker if broker is not None else success_broker(),
        generation_label=generation_label,
        now_utc=NOW,
    )


def test_runtime_binds_generation_lock_risk_deadman_and_full_v4_cycle(
    tmp_path: Path,
) -> None:
    report = run(tmp_path)
    assert report.status is V4GmoRuntimeStatus.POSITION_PROTECTED_SYNTHETIC
    assert report.generation_label == "H11_V4_GMO_10M_G001"
    assert report.boot_reconciled is True
    assert report.process_lock_acquired is True
    assert report.runtime_safety_bound is True
    assert report.risk_entry_recorded is True
    assert report.dead_man_alive is True
    assert report.notification_heartbeat_count == 1
    assert report.action_attempt_count == 2
    assert report.reconciliation_count == 3
    assert report.journal_valid is True
    assert report.actual_post_count == 0
    assert report.broker_read_performed is False
    assert report.broker_write_performed is False
    assert report.credential_read_performed is False
    assert report.network_access_performed is False
    assert report.live_ready is False
    assert report.unattended_live_supported is False
    second_lock = H11AutoProcessLock(tmp_path / "v4.lock")
    assert second_lock.acquire() is True
    second_lock.release()


def test_runtime_boot_conflict_blocks_before_any_action(tmp_path: Path) -> None:
    broker = FakeV4GmoBroker(
        outcomes={},
        snapshots=[filled()],
    )
    report = run(tmp_path, broker=broker)
    assert report.status is V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED
    assert report.boot_reconciled is False
    assert "BOOT_POSITION_NOT_FLAT" in report.blocked_reasons
    assert report.action_attempt_count == 0
    assert broker.calls == []


def test_runtime_risk_gate_blocks_after_daily_entry_is_consumed(tmp_path: Path) -> None:
    risk_store, risk, dead_man = runtime_stores(tmp_path)
    state = risk_store.load()
    state.current_day_jst = "2026-07-15"
    state.current_month_jst = "2026-07"
    state.entries_today = 1
    risk_store.save(state)
    broker = FakeV4GmoBroker(outcomes={}, snapshots=[V4GmoBrokerSnapshot.flat()])
    report = run_v4_gmo_once_no_post(
        signal=signal(),
        policy=policy(),
        state_path=tmp_path / "v4.sqlite3",
        lock_path=tmp_path / "v4.lock",
        risk_store=risk_store,
        risk_policy=risk,
        dead_man_store=dead_man,
        notifier=FakeNotifier(),
        broker=broker,
        generation_label="H11_V4_GMO_10M_G001",
        now_utc=NOW,
    )
    assert report.status is V4GmoRuntimeStatus.BLOCKED_SAFE
    assert "MAX_ENTRIES_PER_DAY_REACHED" in report.blocked_reasons
    assert report.risk_entry_recorded is False
    assert broker.calls == []


def test_runtime_stay_is_no_action_and_does_not_consume_risk(tmp_path: Path) -> None:
    broker = FakeV4GmoBroker(outcomes={}, snapshots=[V4GmoBrokerSnapshot.flat()])
    report = run(tmp_path, broker=broker, input_signal=signal(decision=SignalDecision.STAY))
    assert report.status is V4GmoRuntimeStatus.NO_ACTION_STAY
    assert report.risk_entry_recorded is False
    assert report.action_attempt_count == 0


def test_runtime_notification_failure_halts_before_broker_read(tmp_path: Path) -> None:
    broker = FakeV4GmoBroker(outcomes={}, snapshots=[V4GmoBrokerSnapshot.flat()])
    report = run(tmp_path, broker=broker, notifier=FakeNotifier(fail=True))
    assert report.status is V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED
    assert report.reconciliation_count == 0
    assert report.action_attempt_count == 0
    latched = run(tmp_path, broker=success_broker())
    assert latched.status is V4GmoRuntimeStatus.HALTED_OPERATOR_REVIEW_REQUIRED
    assert latched.blocked_reasons == ("RUNTIME_HEARTBEAT_OR_NOTIFICATION_FAILED",)
    assert latched.reconciliation_count == 0
    store = V4GmoStateStore(tmp_path / "v4.sqlite3")
    with pytest.raises(V4GmoPersistenceError, match="confirmation mismatch"):
        store.clear_global_halt_no_post(
            confirmation="WRONG",
            fresh_flat_confirmed=True,
        )
    store.clear_global_halt_no_post(
        confirmation="H11_V4_GMO_OPERATOR_RELOAD_NO_POST",
        fresh_flat_confirmed=True,
    )
    resumed = run(tmp_path, broker=success_broker())
    assert resumed.status is V4GmoRuntimeStatus.POSITION_PROTECTED_SYNTHETIC


def test_runtime_expired_signal_does_not_consume_risk(tmp_path: Path) -> None:
    expired = FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:runtime-signal-config",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=NOW - timedelta(minutes=20),
        valid_until_utc=NOW - timedelta(minutes=10),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.61"),
    )
    broker = FakeV4GmoBroker(outcomes={}, snapshots=[V4GmoBrokerSnapshot.flat()])
    report = run(tmp_path, broker=broker, input_signal=expired)
    assert report.status is V4GmoRuntimeStatus.BLOCKED_SAFE
    assert "SIGNAL_EXPIRED_OR_CLOCK_INVALID" in report.blocked_reasons
    assert report.risk_entry_recorded is False


def test_runtime_generation_cannot_change_in_same_state_directory(tmp_path: Path) -> None:
    first = run(tmp_path, input_signal=signal(decision=SignalDecision.STAY))
    assert first.status is V4GmoRuntimeStatus.NO_ACTION_STAY
    with pytest.raises(V4GmoPersistenceError, match="generation policy mismatch"):
        run(
            tmp_path,
            input_signal=signal(decision=SignalDecision.STAY),
            generation_label="H11_V4_GMO_10M_G002",
        )


def test_new_signal_runtime_refuses_active_cycle_without_consuming_risk(
    tmp_path: Path,
) -> None:
    first = run(tmp_path)
    assert first.status is V4GmoRuntimeStatus.POSITION_PROTECTED_SYNTHETIC
    broker = success_broker()
    second = run(tmp_path, broker=broker)
    assert second.status is V4GmoRuntimeStatus.BLOCKED_SAFE
    assert second.blocked_reasons == ("ACTIVE_V4_CYCLE_REQUIRES_RESUME",)
    assert second.risk_entry_recorded is False
    assert broker.reconciliation_count == 0
    assert broker.calls == []


def test_runtime_refuses_non_fake_broker_type(tmp_path: Path) -> None:
    risk_store, risk, dead_man = runtime_stores(tmp_path)
    with pytest.raises(V4GmoRuntimeError, match="exact fake type"):
        run_v4_gmo_once_no_post(
            signal=signal(),
            policy=policy(),
            state_path=tmp_path / "v4.sqlite3",
            lock_path=tmp_path / "v4.lock",
            risk_store=risk_store,
            risk_policy=risk,
            dead_man_store=dead_man,
            notifier=FakeNotifier(),
            broker=RefusingV4GmoBroker(),
            generation_label="H11_V4_GMO_10M_G001",
            now_utc=NOW,
        )
