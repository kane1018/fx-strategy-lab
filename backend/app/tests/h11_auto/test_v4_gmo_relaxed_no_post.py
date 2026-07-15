from __future__ import annotations

import inspect
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import app.h11_auto.v4_gmo_boundary as v4_boundary
import app.h11_auto.v4_gmo_contracts as v4_contracts
import app.h11_auto.v4_gmo_engine as v4_engine
import app.h11_auto.v4_gmo_evidence as v4_evidence
import app.h11_auto.v4_gmo_persistence as v4_persistence
import app.h11_auto.v4_gmo_protection as v4_protection
import app.h11_auto.v4_gmo_report as v4_report
import app.h11_auto.v4_gmo_runtime as v4_runtime
import app.h11_auto.v4_gmo_soak as v4_soak
from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.v4_gmo_boundary import FakeV4GmoBroker
from app.h11_auto.v4_gmo_contracts import (
    V4GmoAction,
    V4GmoBrokerSnapshot,
    V4GmoContractError,
    V4GmoCycleState,
    V4GmoEntryStatus,
    V4GmoExecutionPolicy,
    V4GmoPreflightSnapshot,
    V4GmoProtectionStatus,
    V4GmoSyntheticOutcome,
    build_v4_action_plan,
)
from app.h11_auto.v4_gmo_engine import (
    H11V4GmoNoPostEngine,
    V4GmoCycleStatus,
)
from app.h11_auto.v4_gmo_evidence import (
    H11_V4_GMO_CAPABILITY_EVIDENCE,
    H11_V4_GMO_CAPABILITY_EVIDENCE_HASH,
)
from app.h11_auto.v4_gmo_persistence import (
    V4GmoPersistenceError,
    V4GmoStateStore,
)
from app.h11_auto.v4_gmo_protection import (
    H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    build_exact_fill_oco_plan_no_post,
)

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


def policy(**overrides: object) -> V4GmoExecutionPolicy:
    values: dict[str, object] = {
        "strategy_version": "SHORT_V1",
        "signal_config_hash": "sha256:synthetic-signal-config",
        "selected_horizon": FormalHorizon.MINUTES_10,
        "protection_contract_hash": H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    }
    values.update(overrides)
    return V4GmoExecutionPolicy(**values)  # type: ignore[arg-type]


def preflight(**overrides: object) -> V4GmoPreflightSnapshot:
    values: dict[str, object] = {
        "boot_reconciled": True,
        "process_lock_held": True,
        "data_fresh": True,
        "clock_synchronized": True,
        "notification_path_ready": True,
        "broker_snapshot_fresh": True,
    }
    values.update(overrides)
    return V4GmoPreflightSnapshot(**values)  # type: ignore[arg-type]


def filled_snapshot(
    *,
    size: int = 10_000,
    pending: int = 0,
    protection_size: int = 0,
    protection_status: V4GmoProtectionStatus = V4GmoProtectionStatus.NONE,
) -> V4GmoBrokerSnapshot:
    return V4GmoBrokerSnapshot(
        fresh=True,
        result_known=True,
        position_count=1,
        position_side=SignalDecision.BUY,
        filled_size=size,
        pending_entry_size=pending,
        protection_size=protection_size,
        entry_status=(
            V4GmoEntryStatus.PARTIAL if pending else V4GmoEntryStatus.FILLED
        ),
        protection_status=protection_status,
    )


def fake_broker(
    *,
    outcomes: dict[V4GmoAction, list[V4GmoSyntheticOutcome]],
    snapshots: list[V4GmoBrokerSnapshot],
) -> FakeV4GmoBroker:
    return FakeV4GmoBroker(outcomes=outcomes, snapshots=snapshots)


def test_v4_policy_freezes_relaxed_but_bounded_gmo_invariants() -> None:
    frozen = policy()
    assert frozen.requested_size == 10_000
    assert frozen.max_unprotected_seconds == 15
    assert frozen.temporary_unprotected_gap_accepted is True
    assert frozen.broker_native_atomic_protection_required is False
    assert (
        frozen.broker_capability_evidence_hash
        == H11_V4_GMO_CAPABILITY_EVIDENCE_HASH
    )
    assert frozen.same_action_retry_allowed is False
    assert frozen.same_action_repost_allowed is False
    assert frozen.max_positions == 1
    assert frozen.max_entries_per_day == 1
    assert frozen.config_hash.startswith("sha256:")
    with pytest.raises(V4GmoContractError, match="cannot be changed"):
        policy(max_unprotected_seconds=16)
    with pytest.raises(V4GmoContractError, match="cannot be changed"):
        policy(same_action_retry_allowed=True)
    with pytest.raises(V4GmoContractError, match="evidence hash"):
        policy(broker_capability_evidence_hash="sha256:changed")


def test_v4_gmo_capability_evidence_is_canonical_and_hash_bound() -> None:
    assert H11_V4_GMO_CAPABILITY_EVIDENCE.schema == (
        "H11_V4_GMO_CAPABILITY_EVIDENCE_V1"
    )
    assert H11_V4_GMO_CAPABILITY_EVIDENCE.per_order_expiry_or_tif == (
        "NO_REQUEST_FIELD"
    )
    assert H11_V4_GMO_CAPABILITY_EVIDENCE.all_or_none_or_fok == "NOT_SUPPORTED"
    assert H11_V4_GMO_CAPABILITY_EVIDENCE_HASH.startswith("sha256:")
    assert len(H11_V4_GMO_CAPABILITY_EVIDENCE_HASH) == 71


def test_v4_generation_binding_is_persistent_and_immutable(tmp_path: Path) -> None:
    store = V4GmoStateStore(tmp_path / "v4.sqlite3")
    binding = store.bind_generation(
        generation_label="H11_V4_GMO_30M_G001",
        policy=policy(),
        risk_policy_label="H11_V4_RISK_V1",
        risk_policy_digest="a" * 64,
        dead_man_policy_label="H11_V4_DEAD_MAN_V1",
        dead_man_policy_digest="b" * 64,
    )
    assert store.load_generation_safe() == binding
    assert (
        store.bind_generation(
            generation_label="H11_V4_GMO_30M_G001",
            policy=policy(),
            risk_policy_label="H11_V4_RISK_V1",
            risk_policy_digest="a" * 64,
            dead_man_policy_label="H11_V4_DEAD_MAN_V1",
            dead_man_policy_digest="b" * 64,
        )
        == binding
    )
    with pytest.raises(V4GmoPersistenceError, match="policy mismatch"):
        store.bind_generation(
            generation_label="H11_V4_GMO_30M_G002",
            policy=policy(),
            risk_policy_label="H11_V4_RISK_V1",
            risk_policy_digest="a" * 64,
            dead_man_policy_label="H11_V4_DEAD_MAN_V1",
            dead_man_policy_digest="b" * 64,
        )


def test_action_plans_are_structurally_no_post_and_exact_size_bound() -> None:
    plan = build_v4_action_plan(
        cycle_ref="a" * 64,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
        side=SignalDecision.BUY,
        requested_size=4_000,
        protection_contract_hash="sha256:protection",
    )
    assert plan.requested_size == 4_000
    assert plan.actual_post_allowed is False
    assert plan.credential_read_allowed is False
    assert plan.network_access_allowed is False
    with pytest.raises(V4GmoContractError, match="cannot enable transport"):
        v4_contracts.V4GmoActionPlan(
            cycle_ref="a" * 64,
            action=V4GmoAction.MARKET_ENTRY,
            side=SignalDecision.BUY,
            requested_size=10_000,
            protection_contract_hash=None,
            route_safe_label="GMO_MARKET_ENTRY",
            actual_post_allowed=True,
        )


def test_exact_fill_oco_calculation_uses_actual_fill_size_and_frozen_atr() -> None:
    assert (
        H11_V4_GMO_PROTECTION_CONTRACT_HASH
        == v4_protection._calculate_protection_contract_hash()
    )
    buy = build_exact_fill_oco_plan_no_post(
        position_side=SignalDecision.BUY,
        reconciled_average_fill_price=Decimal("162.200"),
        frozen_signal_atr_24=Decimal("0.040"),
        reconciled_filled_size=4_000,
    )
    assert buy.exact_filled_size == 4_000
    assert buy.settlement_side is SignalDecision.SELL
    assert buy.stop_loss_price == Decimal("162.140")
    assert buy.take_profit_price == Decimal("162.290")
    assert buy.actual_post_allowed is False
    assert len(buy.plan_digest) == 64
    sell = build_exact_fill_oco_plan_no_post(
        position_side=SignalDecision.SELL,
        reconciled_average_fill_price=Decimal("162.200"),
        frozen_signal_atr_24=Decimal("0.040"),
        reconciled_filled_size=10_000,
    )
    assert sell.settlement_side is SignalDecision.BUY
    assert sell.stop_loss_price == Decimal("162.260")
    assert sell.take_profit_price == Decimal("162.110")


def test_full_fill_then_exact_oco_reaches_protected(tmp_path: Path) -> None:
    broker = fake_broker(
        outcomes={
            V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.ACCEPTED],
            V4GmoAction.EXACT_SIZE_OCO_PROTECTION: [V4GmoSyntheticOutcome.ACCEPTED],
        },
        snapshots=[
            filled_snapshot(),
            filled_snapshot(
                protection_size=10_000,
                protection_status=V4GmoProtectionStatus.EXACT_MATCH,
            ),
        ],
    )
    store = V4GmoStateStore(tmp_path / "v4.sqlite3")
    result = H11V4GmoNoPostEngine(store=store, broker=broker).run_signal_once_synthetic(
        signal=signal(), policy=policy(), preflight=preflight(), now_utc=NOW
    )
    assert result.status is V4GmoCycleStatus.POSITION_PROTECTED_SYNTHETIC
    assert result.final_state is V4GmoCycleState.POSITION_PROTECTED
    assert result.filled_size == 10_000
    assert result.protected_size == 10_000
    assert result.market_entry_attempt_count == 1
    assert result.protection_attempt_count == 1
    assert result.protection_cancel_attempt_count == 0
    assert result.cancel_attempt_count == 0
    assert result.emergency_exit_attempt_count == 0
    assert result.actual_post_count == 0
    assert result.broker_write_performed is False
    assert result.credential_read_performed is False
    assert result.network_access_performed is False
    assert [call.action for call in broker.calls] == [
        V4GmoAction.MARKET_ENTRY,
        V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
    ]
    assert store.verify_journal().valid is True


def test_partial_fill_cancels_remainder_then_protects_exact_fill(tmp_path: Path) -> None:
    broker = fake_broker(
        outcomes={
            V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.ACCEPTED],
            V4GmoAction.CANCEL_ENTRY_REMAINDER: [V4GmoSyntheticOutcome.ACCEPTED],
            V4GmoAction.EXACT_SIZE_OCO_PROTECTION: [V4GmoSyntheticOutcome.ACCEPTED],
        },
        snapshots=[
            filled_snapshot(size=4_000, pending=6_000),
            filled_snapshot(size=4_000),
            filled_snapshot(
                size=4_000,
                protection_size=4_000,
                protection_status=V4GmoProtectionStatus.EXACT_MATCH,
            ),
        ],
    )
    result = H11V4GmoNoPostEngine(
        store=V4GmoStateStore(tmp_path / "v4.sqlite3"), broker=broker
    ).run_signal_once_synthetic(
        signal=signal(), policy=policy(), preflight=preflight(), now_utc=NOW
    )
    assert result.status is V4GmoCycleStatus.POSITION_PROTECTED_SYNTHETIC
    assert result.filled_size == 4_000
    assert result.protected_size == 4_000
    assert result.action_attempt_count == 3
    assert [call.action for call in broker.calls] == [
        V4GmoAction.MARKET_ENTRY,
        V4GmoAction.CANCEL_ENTRY_REMAINDER,
        V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
    ]
    assert broker.calls[1].requested_size == 6_000
    assert broker.calls[2].requested_size == 4_000


def test_rejected_entry_reconciles_flat_without_retry(tmp_path: Path) -> None:
    broker = fake_broker(
        outcomes={V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.REJECTED]},
        snapshots=[V4GmoBrokerSnapshot.flat()],
    )
    result = H11V4GmoNoPostEngine(
        store=V4GmoStateStore(tmp_path / "v4.sqlite3"), broker=broker
    ).run_signal_once_synthetic(
        signal=signal(), policy=policy(), preflight=preflight(), now_utc=NOW
    )
    assert result.status is V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC
    assert result.market_entry_attempt_count == 1
    assert result.action_attempt_count == 1
    assert len(broker.calls) == 1


def test_unknown_entry_result_can_only_continue_after_authoritative_fill(
    tmp_path: Path,
) -> None:
    broker = fake_broker(
        outcomes={
            V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.UNKNOWN],
            V4GmoAction.EXACT_SIZE_OCO_PROTECTION: [V4GmoSyntheticOutcome.ACCEPTED],
        },
        snapshots=[
            filled_snapshot(),
            filled_snapshot(
                protection_size=10_000,
                protection_status=V4GmoProtectionStatus.EXACT_MATCH,
            ),
        ],
    )
    result = H11V4GmoNoPostEngine(
        store=V4GmoStateStore(tmp_path / "v4.sqlite3"), broker=broker
    ).run_signal_once_synthetic(
        signal=signal(), policy=policy(), preflight=preflight(), now_utc=NOW
    )
    assert result.status is V4GmoCycleStatus.POSITION_PROTECTED_SYNTHETIC
    assert result.market_entry_attempt_count == 1
    assert [call.action for call in broker.calls].count(V4GmoAction.MARKET_ENTRY) == 1


def test_unknown_entry_reconciliation_halts_without_retry(tmp_path: Path) -> None:
    unknown = V4GmoBrokerSnapshot(
        fresh=True,
        result_known=False,
        position_count=0,
        position_side=None,
        filled_size=0,
        pending_entry_size=0,
        protection_size=0,
        entry_status=V4GmoEntryStatus.UNKNOWN,
        protection_status=V4GmoProtectionStatus.UNKNOWN,
    )
    broker = fake_broker(
        outcomes={V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.TIMEOUT]},
        snapshots=[unknown],
    )
    result = H11V4GmoNoPostEngine(
        store=V4GmoStateStore(tmp_path / "v4.sqlite3"), broker=broker
    ).run_signal_once_synthetic(
        signal=signal(), policy=policy(), preflight=preflight(), now_utc=NOW
    )
    assert result.status is V4GmoCycleStatus.HALTED_OPERATOR_REVIEW_REQUIRED
    assert result.blocked_reasons == ("ENTRY_RECONCILIATION_UNKNOWN",)
    assert result.market_entry_attempt_count == 1
    assert result.action_attempt_count == 1


def test_entry_reconciliation_refuses_unexpected_existing_protection(
    tmp_path: Path,
) -> None:
    broker = fake_broker(
        outcomes={V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.ACCEPTED]},
        snapshots=[
            filled_snapshot(
                protection_size=10_000,
                protection_status=V4GmoProtectionStatus.EXACT_MATCH,
            )
        ],
    )
    result = H11V4GmoNoPostEngine(
        store=V4GmoStateStore(tmp_path / "v4.sqlite3"), broker=broker
    ).run_signal_once_synthetic(
        signal=signal(), policy=policy(), preflight=preflight(), now_utc=NOW
    )
    assert result.status is V4GmoCycleStatus.HALTED_OPERATOR_REVIEW_REQUIRED
    assert result.blocked_reasons == (
        "UNEXPECTED_PROTECTION_DURING_ENTRY_RECONCILIATION",
    )
    assert result.protection_attempt_count == 0


@pytest.mark.parametrize(
    ("protection_status", "protection_size"),
    (
        (V4GmoProtectionStatus.NONE, 0),
        (V4GmoProtectionStatus.UNDERSIZED, 8_000),
        (V4GmoProtectionStatus.OVERSIZED, 12_000),
    ),
)
def test_non_exact_protection_uses_one_position_specific_emergency_exit(
    tmp_path: Path,
    protection_status: V4GmoProtectionStatus,
    protection_size: int,
) -> None:
    outcomes = {
        V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.ACCEPTED],
        V4GmoAction.EXACT_SIZE_OCO_PROTECTION: [V4GmoSyntheticOutcome.REJECTED],
        V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT: [
            V4GmoSyntheticOutcome.ACCEPTED
        ],
    }
    snapshots = [
        filled_snapshot(),
        filled_snapshot(
            protection_size=protection_size,
            protection_status=protection_status,
        ),
    ]
    if protection_size > 0:
        outcomes[V4GmoAction.CANCEL_MISMATCHED_PROTECTION] = [
            V4GmoSyntheticOutcome.ACCEPTED
        ]
        snapshots.append(filled_snapshot())
    snapshots.append(V4GmoBrokerSnapshot.flat())
    broker = fake_broker(
        outcomes=outcomes,
        snapshots=snapshots,
    )
    result = H11V4GmoNoPostEngine(
        store=V4GmoStateStore(tmp_path / "v4.sqlite3"), broker=broker
    ).run_signal_once_synthetic(
        signal=signal(), policy=policy(), preflight=preflight(), now_utc=NOW
    )
    assert result.status is V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC
    assert result.market_entry_attempt_count == 1
    assert result.protection_attempt_count == 1
    assert result.protection_cancel_attempt_count == int(protection_size > 0)
    assert result.emergency_exit_attempt_count == 1
    assert [call.action for call in broker.calls][-1] is (
        V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT
    )


def test_emergency_exit_unknown_halts_and_is_never_reposted(tmp_path: Path) -> None:
    broker = fake_broker(
        outcomes={
            V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.ACCEPTED],
            V4GmoAction.EXACT_SIZE_OCO_PROTECTION: [V4GmoSyntheticOutcome.REJECTED],
            V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT: [V4GmoSyntheticOutcome.UNKNOWN],
        },
        snapshots=[
            filled_snapshot(),
            filled_snapshot(),
            filled_snapshot(),
        ],
    )
    result = H11V4GmoNoPostEngine(
        store=V4GmoStateStore(tmp_path / "v4.sqlite3"), broker=broker
    ).run_signal_once_synthetic(
        signal=signal(), policy=policy(), preflight=preflight(), now_utc=NOW
    )
    assert result.status is V4GmoCycleStatus.HALTED_OPERATOR_REVIEW_REQUIRED
    assert result.blocked_reasons == ("EMERGENCY_EXIT_RESULT_UNKNOWN_OR_NOT_FLAT",)
    assert result.emergency_exit_attempt_count == 1
    assert [call.action for call in broker.calls].count(
        V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT
    ) == 1


def test_unknown_protection_reconciliation_halts_without_exit_or_cancel(
    tmp_path: Path,
) -> None:
    unknown = V4GmoBrokerSnapshot(
        fresh=True,
        result_known=False,
        position_count=1,
        position_side=SignalDecision.BUY,
        filled_size=10_000,
        pending_entry_size=0,
        protection_size=0,
        entry_status=V4GmoEntryStatus.FILLED,
        protection_status=V4GmoProtectionStatus.UNKNOWN,
    )
    broker = fake_broker(
        outcomes={
            V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.ACCEPTED],
            V4GmoAction.EXACT_SIZE_OCO_PROTECTION: [V4GmoSyntheticOutcome.TIMEOUT],
        },
        snapshots=[filled_snapshot(), unknown],
    )
    result = H11V4GmoNoPostEngine(
        store=V4GmoStateStore(tmp_path / "v4.sqlite3"), broker=broker
    ).run_signal_once_synthetic(
        signal=signal(), policy=policy(), preflight=preflight(), now_utc=NOW
    )
    assert result.status is V4GmoCycleStatus.HALTED_OPERATOR_REVIEW_REQUIRED
    assert result.blocked_reasons == ("PROTECTION_RECONCILIATION_UNKNOWN",)
    assert result.protection_attempt_count == 1
    assert result.protection_cancel_attempt_count == 0
    assert result.emergency_exit_attempt_count == 0


def test_orphan_protection_is_cancelled_before_flat_is_accepted(tmp_path: Path) -> None:
    orphan = V4GmoBrokerSnapshot(
        fresh=True,
        result_known=True,
        position_count=0,
        position_side=None,
        filled_size=0,
        pending_entry_size=0,
        protection_size=10_000,
        entry_status=V4GmoEntryStatus.FILLED,
        protection_status=V4GmoProtectionStatus.EXACT_MATCH,
    )
    broker = fake_broker(
        outcomes={
            V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.ACCEPTED],
            V4GmoAction.EXACT_SIZE_OCO_PROTECTION: [V4GmoSyntheticOutcome.ACCEPTED],
            V4GmoAction.CANCEL_MISMATCHED_PROTECTION: [
                V4GmoSyntheticOutcome.ACCEPTED
            ],
        },
        snapshots=[filled_snapshot(), orphan, V4GmoBrokerSnapshot.flat()],
    )
    result = H11V4GmoNoPostEngine(
        store=V4GmoStateStore(tmp_path / "v4.sqlite3"), broker=broker
    ).run_signal_once_synthetic(
        signal=signal(), policy=policy(), preflight=preflight(), now_utc=NOW
    )
    assert result.status is V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC
    assert result.protection_cancel_attempt_count == 1
    assert result.emergency_exit_attempt_count == 0


def test_unprotected_window_expiry_forces_emergency_exit_before_protection(
    tmp_path: Path,
) -> None:
    store = V4GmoStateStore(tmp_path / "v4.sqlite3")
    cycle = store.create_cycle(signal=signal(), policy=policy(), now_utc=NOW)
    cycle = store.record_action_attempt(
        cycle_ref=cycle.cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
        target=V4GmoCycleState.MARKET_ENTRY_ATTEMPTED,
        now_utc=NOW,
    )
    cycle = store.transition(
        cycle_ref=cycle.cycle_ref,
        target=V4GmoCycleState.ENTRY_RECONCILING,
        event_category="TEST_ENTRY_RECONCILING",
        now_utc=NOW,
    )
    cycle = store.transition(
        cycle_ref=cycle.cycle_ref,
        target=V4GmoCycleState.ENTRY_FILLED_UNPROTECTED,
        event_category="TEST_ENTRY_FILLED_UNPROTECTED",
        now_utc=NOW,
        filled_size=10_000,
        unprotected_since_utc=NOW,
    )
    broker = fake_broker(
        outcomes={
            V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT: [
                V4GmoSyntheticOutcome.ACCEPTED
            ]
        },
        snapshots=[V4GmoBrokerSnapshot.flat()],
    )
    result = H11V4GmoNoPostEngine(store=store, broker=broker).resume_synthetic(
        cycle_ref=cycle.cycle_ref,
        policy=policy(),
        now_utc=NOW + timedelta(seconds=16),
    )
    assert result.status is V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC
    assert result.protection_attempt_count == 0
    assert result.emergency_exit_attempt_count == 1


def test_slow_entry_reconciliation_uses_attempt_start_for_15_second_limit(
    tmp_path: Path,
) -> None:
    class ScriptedClock:
        def __init__(self) -> None:
            self.values = [NOW, NOW + timedelta(seconds=16), NOW + timedelta(seconds=16)]

        def now_utc(self) -> datetime:
            return self.values.pop(0)

    broker = fake_broker(
        outcomes={
            V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.ACCEPTED],
            V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT: [
                V4GmoSyntheticOutcome.ACCEPTED
            ],
        },
        snapshots=[filled_snapshot(), V4GmoBrokerSnapshot.flat()],
    )
    result = H11V4GmoNoPostEngine(
        store=V4GmoStateStore(tmp_path / "v4.sqlite3"),
        broker=broker,
        clock=ScriptedClock(),
    ).run_signal_once_synthetic(
        signal=signal(),
        policy=policy(),
        preflight=preflight(),
        now_utc=NOW,
    )
    assert result.status is V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC
    assert result.protection_attempt_count == 0
    assert result.emergency_exit_attempt_count == 1
    assert [call.action for call in broker.calls] == [
        V4GmoAction.MARKET_ENTRY,
        V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
    ]


@pytest.mark.parametrize(
    ("confirmation_delay_seconds", "expected_status", "expected_reason"),
    (
        (15, V4GmoCycleStatus.POSITION_PROTECTED_SYNTHETIC, ()),
        (
            15.001,
            V4GmoCycleStatus.HALTED_OPERATOR_REVIEW_REQUIRED,
            ("PROTECTION_CONFIRMED_AFTER_DEADLINE",),
        ),
        (
            -0.001,
            V4GmoCycleStatus.HALTED_OPERATOR_REVIEW_REQUIRED,
            ("CLOCK_MOVED_BACKWARD_AT_PROTECTION_CONFIRMATION",),
        ),
    ),
)
def test_exact_protection_confirmation_rechecks_15_second_deadline(
    tmp_path: Path,
    confirmation_delay_seconds: float,
    expected_status: V4GmoCycleStatus,
    expected_reason: tuple[str, ...],
) -> None:
    class ScriptedClock:
        def __init__(self) -> None:
            self.values = [
                NOW,
                NOW,
                NOW,
                NOW + timedelta(seconds=confirmation_delay_seconds),
            ]

        def now_utc(self) -> datetime:
            return self.values.pop(0)

    broker = fake_broker(
        outcomes={
            V4GmoAction.MARKET_ENTRY: [V4GmoSyntheticOutcome.ACCEPTED],
            V4GmoAction.EXACT_SIZE_OCO_PROTECTION: [V4GmoSyntheticOutcome.ACCEPTED],
        },
        snapshots=[
            filled_snapshot(),
            filled_snapshot(
                protection_size=10_000,
                protection_status=V4GmoProtectionStatus.EXACT_MATCH,
            ),
        ],
    )
    result = H11V4GmoNoPostEngine(
        store=V4GmoStateStore(tmp_path / "v4.sqlite3"),
        broker=broker,
        clock=ScriptedClock(),
    ).run_signal_once_synthetic(
        signal=signal(),
        policy=policy(),
        preflight=preflight(),
        now_utc=NOW,
    )
    assert result.status is expected_status
    assert result.blocked_reasons == expected_reason
    assert result.protection_attempt_count == 1
    assert result.emergency_exit_attempt_count == 0


def test_restart_after_attempt_persistence_reconciles_without_resending_market(
    tmp_path: Path,
) -> None:
    store = V4GmoStateStore(tmp_path / "v4.sqlite3")
    cycle = store.create_cycle(signal=signal(), policy=policy(), now_utc=NOW)
    cycle = store.record_action_attempt(
        cycle_ref=cycle.cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
        target=V4GmoCycleState.MARKET_ENTRY_ATTEMPTED,
        now_utc=NOW,
    )
    broker = fake_broker(
        outcomes={
            V4GmoAction.EXACT_SIZE_OCO_PROTECTION: [V4GmoSyntheticOutcome.ACCEPTED]
        },
        snapshots=[
            filled_snapshot(),
            filled_snapshot(
                protection_size=10_000,
                protection_status=V4GmoProtectionStatus.EXACT_MATCH,
            ),
        ],
    )
    result = H11V4GmoNoPostEngine(store=store, broker=broker).resume_synthetic(
        cycle_ref=cycle.cycle_ref,
        policy=policy(),
        now_utc=NOW + timedelta(seconds=1),
    )
    assert result.status is V4GmoCycleStatus.POSITION_PROTECTED_SYNTHETIC
    assert result.market_entry_attempt_count == 1
    assert [call.action for call in broker.calls] == [
        V4GmoAction.EXACT_SIZE_OCO_PROTECTION
    ]


def test_restart_after_protection_attempt_reconciles_without_reposting(
    tmp_path: Path,
) -> None:
    store = V4GmoStateStore(tmp_path / "v4.sqlite3")
    cycle = store.create_cycle(signal=signal(), policy=policy(), now_utc=NOW)
    cycle = store.record_action_attempt(
        cycle_ref=cycle.cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
        target=V4GmoCycleState.MARKET_ENTRY_ATTEMPTED,
        now_utc=NOW,
    )
    cycle = store.transition(
        cycle_ref=cycle.cycle_ref,
        target=V4GmoCycleState.ENTRY_RECONCILING,
        event_category="TEST_ENTRY_RECONCILING",
        now_utc=NOW,
    )
    cycle = store.transition(
        cycle_ref=cycle.cycle_ref,
        target=V4GmoCycleState.ENTRY_FILLED_UNPROTECTED,
        event_category="TEST_ENTRY_FILLED_UNPROTECTED",
        now_utc=NOW,
        filled_size=10_000,
        unprotected_since_utc=NOW,
    )
    cycle = store.transition(
        cycle_ref=cycle.cycle_ref,
        target=V4GmoCycleState.PROTECTION_INTENT_PERSISTED,
        event_category="TEST_PROTECTION_INTENT_PERSISTED",
        now_utc=NOW,
    )
    cycle = store.record_action_attempt(
        cycle_ref=cycle.cycle_ref,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
        target=V4GmoCycleState.PROTECTION_ATTEMPTED,
        now_utc=NOW,
    )
    broker = fake_broker(
        outcomes={},
        snapshots=[
            filled_snapshot(
                protection_size=10_000,
                protection_status=V4GmoProtectionStatus.EXACT_MATCH,
            )
        ],
    )
    result = H11V4GmoNoPostEngine(store=store, broker=broker).resume_synthetic(
        cycle_ref=cycle.cycle_ref,
        policy=policy(),
        now_utc=NOW + timedelta(seconds=1),
    )
    assert result.status is V4GmoCycleStatus.POSITION_PROTECTED_SYNTHETIC
    assert result.protection_attempt_count == 1
    assert broker.calls == []


def test_concurrent_same_action_attempt_allows_exactly_one(tmp_path: Path) -> None:
    store = V4GmoStateStore(tmp_path / "v4.sqlite3")
    cycle = store.create_cycle(signal=signal(), policy=policy(), now_utc=NOW)

    def attempt() -> str:
        try:
            store.record_action_attempt(
                cycle_ref=cycle.cycle_ref,
                action=V4GmoAction.MARKET_ENTRY,
                target=V4GmoCycleState.MARKET_ENTRY_ATTEMPTED,
                now_utc=NOW,
            )
        except (V4GmoPersistenceError, V4GmoContractError):
            return "REFUSED"
        return "STARTED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["REFUSED", "STARTED"]
    assert store.action_attempt_count(cycle_ref=cycle.cycle_ref) == 1


def test_v4_journal_detects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "v4.sqlite3"
    store = V4GmoStateStore(path)
    store.create_cycle(signal=signal(), policy=policy(), now_utc=NOW)
    assert store.verify_journal().valid is True
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE safe_events SET state_safe_label = 'TAMPERED' WHERE sequence = 1"
        )
    with pytest.raises(V4GmoPersistenceError, match="verification"):
        store.verify_journal()


def test_v4_journal_detects_action_outcome_tampering(tmp_path: Path) -> None:
    path = tmp_path / "v4.sqlite3"
    store = V4GmoStateStore(path)
    cycle = store.create_cycle(signal=signal(), policy=policy(), now_utc=NOW)
    store.record_action_attempt(
        cycle_ref=cycle.cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
        target=V4GmoCycleState.MARKET_ENTRY_ATTEMPTED,
        now_utc=NOW,
    )
    store.record_action_outcome(
        cycle_ref=cycle.cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
        outcome_safe_label=V4GmoSyntheticOutcome.ACCEPTED.value,
    )
    assert store.verify_journal().valid is True
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE action_attempts SET outcome_safe_label = 'UNKNOWN'"
        )
    with pytest.raises(V4GmoPersistenceError, match="action journal"):
        store.verify_journal()


def test_v4_action_outcome_can_be_recorded_only_once(tmp_path: Path) -> None:
    store = V4GmoStateStore(tmp_path / "v4.sqlite3")
    cycle = store.create_cycle(signal=signal(), policy=policy(), now_utc=NOW)
    store.record_action_attempt(
        cycle_ref=cycle.cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
        target=V4GmoCycleState.MARKET_ENTRY_ATTEMPTED,
        now_utc=NOW,
    )
    store.record_action_outcome(
        cycle_ref=cycle.cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
        outcome_safe_label=V4GmoSyntheticOutcome.ACCEPTED.value,
    )
    with pytest.raises(V4GmoPersistenceError, match="attempt not found"):
        store.record_action_outcome(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.MARKET_ENTRY,
            outcome_safe_label=V4GmoSyntheticOutcome.UNKNOWN.value,
        )


def test_v4_journal_detects_deleted_terminal_state_event(tmp_path: Path) -> None:
    path = tmp_path / "v4.sqlite3"
    store = V4GmoStateStore(path)
    cycle = store.create_cycle(signal=signal(), policy=policy(), now_utc=NOW)
    store.transition(
        cycle_ref=cycle.cycle_ref,
        target=V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        event_category="HALTED_OPERATOR_REVIEW_REQUIRED",
        now_utc=NOW,
        halt_reason="SYNTHETIC_TEST_HALT",
    )
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM safe_events WHERE sequence = 2")
    with pytest.raises(V4GmoPersistenceError, match="state journal mismatch"):
        store.verify_journal()


def test_v4_modules_have_no_real_transport_credential_or_private_api_surface() -> None:
    source = "\n".join(
        inspect.getsource(module)
        for module in (
            v4_contracts,
            v4_boundary,
            v4_persistence,
            v4_engine,
            v4_evidence,
            v4_protection,
            v4_report,
            v4_runtime,
            v4_soak,
        )
    )
    forbidden = (
        "import httpx",
        "import requests",
        "app.private_api",
        "build_auth_headers",
        "assert_real_broker_post_allowed",
        "os.environ",
        "os.getenv",
        "load_dotenv",
        "forex-api.coin.z.com",
        "api_key",
        "api_secret",
        "raw_request",
        "raw_response",
    )
    for marker in forbidden:
        assert marker not in source
