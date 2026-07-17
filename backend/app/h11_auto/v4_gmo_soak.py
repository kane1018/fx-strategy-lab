"""Bounded fake-only fault matrix for the relaxed GMO v4 profile."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory

from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.v4_gmo_boundary import FakeV4GmoBroker
from app.h11_auto.v4_gmo_contracts import (
    V4GmoAction,
    V4GmoBrokerSnapshot,
    V4GmoCycleState,
    V4GmoEntryStatus,
    V4GmoExecutionPolicy,
    V4GmoPreflightSnapshot,
    V4GmoProtectionStatus,
    V4GmoSyntheticOutcome,
)
from app.h11_auto.v4_gmo_engine import (
    H11V4GmoNoPostEngine,
    V4GmoCycleStatus,
)
from app.h11_auto.v4_gmo_persistence import V4GmoStateStore
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH

MINIMUM_V4_GMO_SOAK_CYCLES = 100


class V4GmoSoakStatus(str, Enum):
    PASSED_SYNTHETIC_NO_POST = "PASSED_SYNTHETIC_NO_POST"
    FAILED_SYNTHETIC_SAFE = "FAILED_SYNTHETIC_SAFE"
    BLOCKED_TARGET_TOO_SMALL = "BLOCKED_TARGET_TOO_SMALL"


@dataclass(frozen=True)
class V4GmoSoakScenario:
    name: str
    decision: SignalDecision
    outcomes: tuple[tuple[V4GmoAction, tuple[V4GmoSyntheticOutcome, ...]], ...]
    snapshots: tuple[V4GmoBrokerSnapshot, ...]
    expected_status: V4GmoCycleStatus
    expected_state: V4GmoCycleState | None
    expected_calls: tuple[V4GmoAction, ...]
    preflight_position_count: int = 0
    preflight_data_fresh: bool = True


@dataclass(frozen=True)
class V4GmoSoakReport:
    status: V4GmoSoakStatus
    synthetic_cycle_count: int
    matched_cycle_count: int
    scenario_count: int
    mismatched_scenarios: tuple[str, ...]
    max_total_action_attempts_observed: int
    max_same_action_attempts_observed: int
    max_reconciliation_reads_observed: int
    one_attempt_per_action_invariant_ok: bool
    journal_verification_failures: int
    actual_post_count: int = 0
    broker_write_performed: bool = False
    credential_read_performed: bool = False
    network_access_performed: bool = False
    raw_or_id_value_exposure: bool = False
    live_ready: bool = False
    unattended_live_supported: bool = False

    def __bool__(self) -> bool:
        return False


def build_v4_gmo_soak_scenarios() -> tuple[V4GmoSoakScenario, ...]:
    entry = V4GmoAction.MARKET_ENTRY
    remainder = V4GmoAction.CANCEL_ENTRY_REMAINDER
    protection = V4GmoAction.EXACT_SIZE_OCO_PROTECTION
    cancel_protection = V4GmoAction.CANCEL_MISMATCHED_PROTECTION
    emergency = V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT
    protected_status = V4GmoCycleStatus.POSITION_PROTECTED_SYNTHETIC
    flat_status = V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC
    halted_status = V4GmoCycleStatus.HALTED_OPERATOR_REVIEW_REQUIRED
    return (
        V4GmoSoakScenario(
            "FULL_FILL_PROTECTED",
            SignalDecision.BUY,
            _outcomes((entry, "ACCEPTED"), (protection, "ACCEPTED")),
            (_position(), _position(protection_size=1_000)),
            protected_status,
            V4GmoCycleState.POSITION_PROTECTED,
            (entry, protection),
        ),
        V4GmoSoakScenario(
            "PARTIAL_REMAINDER_CANCEL_THEN_PROTECT",
            SignalDecision.BUY,
            _outcomes(
                (entry, "ACCEPTED"),
                (remainder, "ACCEPTED"),
                (protection, "ACCEPTED"),
            ),
            (
                _position(filled_size=600, pending_entry_size=400),
                _position(filled_size=600),
                _position(filled_size=600, protection_size=600),
            ),
            protected_status,
            V4GmoCycleState.POSITION_PROTECTED,
            (entry, remainder, protection),
        ),
        V4GmoSoakScenario(
            "ENTRY_REJECTED_FLAT",
            SignalDecision.BUY,
            _outcomes((entry, "REJECTED")),
            (V4GmoBrokerSnapshot.flat(),),
            flat_status,
            V4GmoCycleState.FLAT_RECONCILED,
            (entry,),
        ),
        V4GmoSoakScenario(
            "ENTRY_UNKNOWN_BUT_FILL_RECONCILED",
            SignalDecision.BUY,
            _outcomes((entry, "UNKNOWN"), (protection, "ACCEPTED")),
            (_position(), _position(protection_size=1_000)),
            protected_status,
            V4GmoCycleState.POSITION_PROTECTED,
            (entry, protection),
        ),
        V4GmoSoakScenario(
            "ENTRY_RECONCILIATION_UNKNOWN_HALT",
            SignalDecision.BUY,
            _outcomes((entry, "TIMEOUT")),
            (_unknown_snapshot(),),
            halted_status,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
            (entry,),
        ),
        V4GmoSoakScenario(
            "PROTECTION_UNKNOWN_BUT_EXACT_RECONCILED",
            SignalDecision.BUY,
            _outcomes((entry, "ACCEPTED"), (protection, "UNKNOWN")),
            (_position(), _position(protection_size=1_000)),
            protected_status,
            V4GmoCycleState.POSITION_PROTECTED,
            (entry, protection),
        ),
        V4GmoSoakScenario(
            "PROTECTION_MISSING_EMERGENCY_FLAT",
            SignalDecision.BUY,
            _outcomes(
                (entry, "ACCEPTED"),
                (protection, "REJECTED"),
                (emergency, "ACCEPTED"),
            ),
            (_position(), _position(), V4GmoBrokerSnapshot.flat()),
            flat_status,
            V4GmoCycleState.FLAT_RECONCILED,
            (entry, protection, emergency),
        ),
        V4GmoSoakScenario(
            "UNDERSIZED_PROTECTION_CANCEL_THEN_EMERGENCY_FLAT",
            SignalDecision.BUY,
            _outcomes(
                (entry, "ACCEPTED"),
                (protection, "ACCEPTED"),
                (cancel_protection, "ACCEPTED"),
                (emergency, "ACCEPTED"),
            ),
            (
                _position(),
                _position(protection_size=500),
                _position(),
                V4GmoBrokerSnapshot.flat(),
            ),
            flat_status,
            V4GmoCycleState.FLAT_RECONCILED,
            (entry, protection, cancel_protection, emergency),
        ),
        V4GmoSoakScenario(
            "PROTECTION_PERSISTS_AFTER_CANCEL_HALT",
            SignalDecision.BUY,
            _outcomes(
                (entry, "ACCEPTED"),
                (protection, "ACCEPTED"),
                (cancel_protection, "UNKNOWN"),
            ),
            (
                _position(),
                _position(protection_size=500),
                _position(protection_size=500),
            ),
            halted_status,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
            (entry, protection, cancel_protection),
        ),
        V4GmoSoakScenario(
            "EMERGENCY_RESULT_UNKNOWN_HALT",
            SignalDecision.BUY,
            _outcomes(
                (entry, "ACCEPTED"),
                (protection, "REJECTED"),
                (emergency, "TIMEOUT"),
            ),
            (_position(), _position(), _position()),
            halted_status,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
            (entry, protection, emergency),
        ),
        V4GmoSoakScenario(
            "ORPHAN_PROTECTION_CANCELLED_FLAT",
            SignalDecision.BUY,
            _outcomes(
                (entry, "ACCEPTED"),
                (protection, "ACCEPTED"),
                (cancel_protection, "ACCEPTED"),
            ),
            (
                _position(),
                _orphan_protection(),
                V4GmoBrokerSnapshot.flat(),
            ),
            flat_status,
            V4GmoCycleState.FLAT_RECONCILED,
            (entry, protection, cancel_protection),
        ),
        V4GmoSoakScenario(
            "STAY_NO_ACTION",
            SignalDecision.STAY,
            (),
            (),
            V4GmoCycleStatus.NO_ACTION_STAY,
            None,
            (),
        ),
        V4GmoSoakScenario(
            "PREFLIGHT_POSITION_CONFLICT",
            SignalDecision.BUY,
            (),
            (),
            V4GmoCycleStatus.BLOCKED_SAFE,
            None,
            (),
            preflight_position_count=1,
        ),
        V4GmoSoakScenario(
            "PREFLIGHT_STALE_DATA",
            SignalDecision.BUY,
            (),
            (),
            V4GmoCycleStatus.BLOCKED_SAFE,
            None,
            (),
            preflight_data_fresh=False,
        ),
    )


def run_v4_gmo_fault_soak_no_post(
    *, target_cycle_count: int = MINIMUM_V4_GMO_SOAK_CYCLES
) -> V4GmoSoakReport:
    if type(target_cycle_count) is not int or target_cycle_count < MINIMUM_V4_GMO_SOAK_CYCLES:
        return V4GmoSoakReport(
            status=V4GmoSoakStatus.BLOCKED_TARGET_TOO_SMALL,
            synthetic_cycle_count=0,
            matched_cycle_count=0,
            scenario_count=len(build_v4_gmo_soak_scenarios()),
            mismatched_scenarios=("TARGET_CYCLE_COUNT_BELOW_MINIMUM",),
            max_total_action_attempts_observed=0,
            max_same_action_attempts_observed=0,
            max_reconciliation_reads_observed=0,
            one_attempt_per_action_invariant_ok=False,
            journal_verification_failures=0,
        )
    scenarios = build_v4_gmo_soak_scenarios()
    policy = V4GmoExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:v4-gmo-soak-signal",
        selected_horizon=FormalHorizon.MINUTES_10,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    base_time = datetime(2026, 7, 15, tzinfo=UTC)
    mismatches: list[str] = []
    journal_failures = 0
    max_total_actions = 0
    max_same_action = 0
    max_reconciliations = 0
    actual_posts = 0
    for index in range(target_cycle_count):
        scenario = scenarios[index % len(scenarios)]
        now = base_time + timedelta(minutes=index)
        signal = FormalSignal(
            strategy_version=policy.strategy_version,
            signal_config_hash=policy.signal_config_hash,
            horizon=policy.selected_horizon,
            observed_at_utc=now,
            valid_until_utc=now + timedelta(minutes=10),
            decision=scenario.decision,
            probability_up=Decimal("0.61"),
        )
        preflight = V4GmoPreflightSnapshot(
            boot_reconciled=True,
            process_lock_held=True,
            data_fresh=scenario.preflight_data_fresh,
            clock_synchronized=True,
            notification_path_ready=True,
            broker_snapshot_fresh=True,
            position_count=scenario.preflight_position_count,
        )
        outcomes = {
            action: list(values) for action, values in scenario.outcomes
        }
        broker = FakeV4GmoBroker(
            outcomes=outcomes,
            snapshots=list(scenario.snapshots),
        )
        with TemporaryDirectory(prefix="h11_v4_gmo_soak_") as temp_dir:
            store = V4GmoStateStore(Path(temp_dir) / "v4.sqlite3")
            result = H11V4GmoNoPostEngine(store=store, broker=broker).run_signal_once_synthetic(
                signal=signal,
                policy=policy,
                preflight=preflight,
                now_utc=now,
            )
            try:
                store.verify_journal()
            except Exception:  # noqa: BLE001 - expose only a safe aggregate count
                journal_failures += 1
            call_actions = tuple(call.action for call in broker.calls)
            per_action = tuple(call_actions.count(action) for action in V4GmoAction)
            max_same_action = max(max_same_action, *per_action)
            max_total_actions = max(max_total_actions, len(call_actions))
            max_reconciliations = max(
                max_reconciliations, broker.reconciliation_count
            )
            actual_posts += broker.actual_post_count
            checks = (
                result.status is scenario.expected_status,
                result.final_state is scenario.expected_state,
                call_actions == scenario.expected_calls,
                max(per_action, default=0) <= 1,
                result.actual_post_count == 0,
                result.broker_write_performed is False,
                result.credential_read_performed is False,
                result.network_access_performed is False,
            )
            if not all(checks):
                mismatches.append(scenario.name)
    passed = (
        not mismatches
        and journal_failures == 0
        and max_same_action <= 1
        and actual_posts == 0
    )
    return V4GmoSoakReport(
        status=(
            V4GmoSoakStatus.PASSED_SYNTHETIC_NO_POST
            if passed
            else V4GmoSoakStatus.FAILED_SYNTHETIC_SAFE
        ),
        synthetic_cycle_count=target_cycle_count,
        matched_cycle_count=target_cycle_count - len(mismatches),
        scenario_count=len(scenarios),
        mismatched_scenarios=tuple(mismatches),
        max_total_action_attempts_observed=max_total_actions,
        max_same_action_attempts_observed=max_same_action,
        max_reconciliation_reads_observed=max_reconciliations,
        one_attempt_per_action_invariant_ok=max_same_action <= 1,
        journal_verification_failures=journal_failures,
        actual_post_count=actual_posts,
    )


def _outcomes(
    *values: tuple[V4GmoAction, str],
) -> tuple[tuple[V4GmoAction, tuple[V4GmoSyntheticOutcome, ...]], ...]:
    return tuple(
        (action, (V4GmoSyntheticOutcome(outcome),)) for action, outcome in values
    )


def _position(
    *,
    filled_size: int = 1_000,
    pending_entry_size: int = 0,
    protection_size: int = 0,
) -> V4GmoBrokerSnapshot:
    return V4GmoBrokerSnapshot(
        fresh=True,
        result_known=True,
        position_count=1,
        position_side=SignalDecision.BUY,
        filled_size=filled_size,
        pending_entry_size=pending_entry_size,
        protection_size=protection_size,
        entry_status=(
            V4GmoEntryStatus.PARTIAL
            if pending_entry_size > 0
            else V4GmoEntryStatus.FILLED
        ),
        protection_status=(
            V4GmoProtectionStatus.NONE
            if protection_size == 0
            else (
                V4GmoProtectionStatus.EXACT_MATCH
                if protection_size == filled_size
                else V4GmoProtectionStatus.UNDERSIZED
            )
        ),
    )


def _unknown_snapshot() -> V4GmoBrokerSnapshot:
    return V4GmoBrokerSnapshot(
        fresh=False,
        result_known=False,
        position_count=0,
        position_side=None,
        filled_size=0,
        pending_entry_size=0,
        protection_size=0,
        entry_status=V4GmoEntryStatus.UNKNOWN,
        protection_status=V4GmoProtectionStatus.UNKNOWN,
    )


def _orphan_protection() -> V4GmoBrokerSnapshot:
    return V4GmoBrokerSnapshot(
        fresh=True,
        result_known=True,
        position_count=0,
        position_side=None,
        filled_size=0,
        pending_entry_size=0,
        protection_size=1_000,
        entry_status=V4GmoEntryStatus.NONE,
        protection_status=V4GmoProtectionStatus.EXACT_MATCH,
    )
