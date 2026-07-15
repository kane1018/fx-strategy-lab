"""Bounded fake-only fault soak for H11_AUTO_PARALLEL_PHASE_A_NO_POST."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory

from app.h11_auto.boundary import (
    FakeNotifier,
    FakePositionExitOutcome,
    FakePositionExitSender,
    FakeProtectedEntryOutcome,
    FakeProtectedEntrySender,
)
from app.h11_auto.contracts import (
    FormalHorizon,
    FormalSignal,
    PhaseAExecutionPolicy,
    SignalDecision,
)
from app.h11_auto.engine import FakeCycleStatus, H11AutoPhaseAEngine
from app.h11_auto.persistence import H11AutoStateStore
from app.h11_auto.risk import PhaseASafetySnapshot
from app.h11_auto.state_machine import AutoCycleState

MINIMUM_PHASE_A_SOAK_CYCLES = 100


class PhaseASoakStatus(str, Enum):
    PASSED_SYNTHETIC_NO_POST = "PASSED_SYNTHETIC_NO_POST"
    FAILED_SYNTHETIC_SAFE = "FAILED_SYNTHETIC_SAFE"
    BLOCKED_TARGET_TOO_SMALL = "BLOCKED_TARGET_TOO_SMALL"


@dataclass(frozen=True)
class PhaseASoakScenario:
    name: str
    decision: SignalDecision = SignalDecision.BUY
    entry_outcome: FakeProtectedEntryOutcome = (
        FakeProtectedEntryOutcome.ACCEPTED_AND_PROTECTED
    )
    exit_outcome: FakePositionExitOutcome | None = (
        FakePositionExitOutcome.ACCEPTED_AND_FLAT
    )
    safety_overrides: tuple[tuple[str, bool], ...] = ()
    notification_failure: bool = False
    expected_status: FakeCycleStatus = FakeCycleStatus.FLAT_RECONCILED_SYNTHETIC
    expected_state: AutoCycleState | None = AutoCycleState.FLAT_RECONCILED
    expected_entry_attempts: int = 1
    expected_exit_attempts: int = 1


@dataclass(frozen=True)
class PhaseASoakReport:
    status: PhaseASoakStatus
    synthetic_cycle_count: int
    matched_cycle_count: int
    mismatched_scenarios: tuple[str, ...]
    max_entry_attempts_observed: int
    max_exit_attempts_observed: int
    duplicate_attempt_invariant_ok: bool
    no_retry_invariant_ok: bool
    journal_verification_failures: int
    actual_post_count: int = 0
    broker_write_performed: bool = False
    network_access_performed: bool = False
    credential_read_performed: bool = False
    raw_id_value_exposure: bool = False
    actual_activation_ready: bool = False

    def __bool__(self) -> bool:
        return False


def build_phase_a_soak_scenarios() -> tuple[PhaseASoakScenario, ...]:
    halted = AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED
    blocked = replace(
        PhaseASoakScenario("EXTERNAL_POSITION_BLOCK"),
        safety_overrides=(("external_or_manual_position_detected", True),),
        expected_status=FakeCycleStatus.BLOCKED_SAFE,
        expected_state=None,
        expected_entry_attempts=0,
        expected_exit_attempts=0,
    )
    return (
        PhaseASoakScenario("SUCCESS_FLAT"),
        replace(
            PhaseASoakScenario("ENTRY_REJECTED"),
            entry_outcome=FakeProtectedEntryOutcome.REJECTED,
            exit_outcome=None,
            expected_status=FakeCycleStatus.HALTED_SAFE,
            expected_state=halted,
            expected_exit_attempts=0,
        ),
        replace(
            PhaseASoakScenario("ENTRY_UNKNOWN"),
            entry_outcome=FakeProtectedEntryOutcome.UNKNOWN,
            exit_outcome=None,
            expected_status=FakeCycleStatus.HALTED_SAFE,
            expected_state=halted,
            expected_exit_attempts=0,
        ),
        replace(
            PhaseASoakScenario("ENTRY_TIMEOUT"),
            entry_outcome=FakeProtectedEntryOutcome.TIMEOUT,
            exit_outcome=None,
            expected_status=FakeCycleStatus.HALTED_SAFE,
            expected_state=halted,
            expected_exit_attempts=0,
        ),
        replace(
            PhaseASoakScenario("PARTIAL_MISMATCH"),
            entry_outcome=FakeProtectedEntryOutcome.PARTIAL_FILL_SIZE_MISMATCH,
            exit_outcome=None,
            expected_status=FakeCycleStatus.HALTED_SAFE,
            expected_state=halted,
            expected_exit_attempts=0,
        ),
        replace(
            PhaseASoakScenario("EXIT_UNKNOWN"),
            exit_outcome=FakePositionExitOutcome.UNKNOWN,
            expected_status=FakeCycleStatus.HALTED_SAFE,
            expected_state=halted,
        ),
        replace(
            PhaseASoakScenario("EXIT_TIMEOUT"),
            exit_outcome=FakePositionExitOutcome.TIMEOUT,
            expected_status=FakeCycleStatus.HALTED_SAFE,
            expected_state=halted,
        ),
        blocked,
        replace(
            blocked,
            name="ACTIVE_ORDER_CONFLICT",
            safety_overrides=(("active_or_pending_order_conflict", True),),
        ),
        replace(
            blocked,
            name="STALE_DATA_BLOCK",
            safety_overrides=(("data_fresh", False),),
        ),
        replace(
            PhaseASoakScenario("STAY_NO_ACTION"),
            decision=SignalDecision.STAY,
            exit_outcome=None,
            expected_status=FakeCycleStatus.NO_ACTION_STAY,
            expected_state=None,
            expected_entry_attempts=0,
            expected_exit_attempts=0,
        ),
        replace(
            PhaseASoakScenario("NOTIFICATION_FAILURE"),
            notification_failure=True,
            exit_outcome=None,
            expected_status=FakeCycleStatus.HALTED_SAFE,
            expected_state=halted,
            expected_entry_attempts=0,
            expected_exit_attempts=0,
        ),
    )


def run_phase_a_fault_soak_no_post(
    *, target_cycle_count: int = MINIMUM_PHASE_A_SOAK_CYCLES
) -> PhaseASoakReport:
    if target_cycle_count < MINIMUM_PHASE_A_SOAK_CYCLES:
        return PhaseASoakReport(
            status=PhaseASoakStatus.BLOCKED_TARGET_TOO_SMALL,
            synthetic_cycle_count=0,
            matched_cycle_count=0,
            mismatched_scenarios=("TARGET_CYCLE_COUNT_BELOW_MINIMUM",),
            max_entry_attempts_observed=0,
            max_exit_attempts_observed=0,
            duplicate_attempt_invariant_ok=False,
            no_retry_invariant_ok=False,
            journal_verification_failures=0,
        )

    scenarios = build_phase_a_soak_scenarios()
    mismatches: list[str] = []
    max_entry = 0
    max_exit = 0
    journal_failures = 0
    base_time = datetime(2026, 7, 15, tzinfo=UTC)
    policy = PhaseAExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:synthetic-soak-config",
        selected_horizon=FormalHorizon.MINUTES_10,
    )

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
        safety = PhaseASafetySnapshot(
            boot_reconciled=True,
            process_lock_held=True,
            data_fresh=True,
            clock_synchronized=True,
            notification_path_ready=True,
        )
        safety = replace(safety, **dict(scenario.safety_overrides))
        entry_sender = FakeProtectedEntrySender(scenario.entry_outcome)
        exit_sender = FakePositionExitSender(
            scenario.exit_outcome or FakePositionExitOutcome.REJECTED
        )
        notifier = FakeNotifier(fail=scenario.notification_failure)

        with TemporaryDirectory(prefix="h11_auto_phase_a_soak_") as temp_dir:
            store = H11AutoStateStore(Path(temp_dir) / "auto.sqlite3")
            engine = H11AutoPhaseAEngine(
                store=store,
                sender=entry_sender,
                exit_sender=exit_sender,
                notifier=notifier,
            )
            result = engine.run_signal_once_synthetic(
                signal=signal, policy=policy, safety=safety, now_utc=now
            )
            if (
                result.status is FakeCycleStatus.POSITION_PROTECTED_SYNTHETIC
                and scenario.exit_outcome is not None
            ):
                result = engine.complete_exit_once_synthetic(
                    intent_id=entry_sender.calls[0], now_utc=now + timedelta(minutes=1)
                )
            max_entry = max(max_entry, result.attempt_count)
            max_exit = max(max_exit, result.exit_attempt_count)
            try:
                store.verify_journal()
            except Exception:  # noqa: BLE001 - report safe count only
                journal_failures += 1
            checks = (
                result.status is scenario.expected_status,
                result.final_state is scenario.expected_state,
                len(entry_sender.calls) == scenario.expected_entry_attempts,
                len(exit_sender.calls) == scenario.expected_exit_attempts,
                result.actual_post_count == 0,
                result.network_access_performed is False,
            )
            if not all(checks):
                mismatches.append(scenario.name)

    passed = not mismatches and journal_failures == 0 and max_entry <= 1 and max_exit <= 1
    return PhaseASoakReport(
        status=(
            PhaseASoakStatus.PASSED_SYNTHETIC_NO_POST
            if passed
            else PhaseASoakStatus.FAILED_SYNTHETIC_SAFE
        ),
        synthetic_cycle_count=target_cycle_count,
        matched_cycle_count=target_cycle_count - len(mismatches),
        mismatched_scenarios=tuple(mismatches),
        max_entry_attempts_observed=max_entry,
        max_exit_attempts_observed=max_exit,
        duplicate_attempt_invariant_ok=max_entry <= 1 and max_exit <= 1,
        no_retry_invariant_ok=max_entry <= 1 and max_exit <= 1,
        journal_verification_failures=journal_failures,
    )
