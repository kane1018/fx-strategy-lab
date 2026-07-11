"""Bounded H-11 v3 fault-injection soak (synthetic, fake-only, no-POST).

The soak repeatedly exercises the persistent state machine, risk gate, safe
journal, reconciliation labels, and fake notifier. It is immediate and finite:
no sleep, daemon, cron, network, credential, broker, or actual sender exists.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.h11_v3_observed_live_state import (
    H11V3FakeCycleInput,
    H11V3FakeOutcome,
    H11V3FakeSafetyGate,
    H11V3ObservedState,
    H11V3ObservedStateStore,
    run_h11_v3_fake_cycle_no_post,
)
from app.services.h11_v3_runtime_safety import (
    H11V3BootReconcileInput,
    H11V3BrokerCycleSafeStatus,
    H11V3FakeNotifier,
    H11V3JournalEvent,
    H11V3NotificationCategory,
    H11V3RiskPersistentState,
    H11V3SafeJournal,
    evaluate_h11_v3_boot_reconcile,
    evaluate_h11_v3_risk_before_entry,
    record_h11_v3_entry_attempt,
)

H11_V3_MIN_SYNTHETIC_SOAK_CYCLES = 100


class H11V3FaultSoakStatus(str, Enum):
    PASSED_SYNTHETIC_NO_POST = "PASSED_SYNTHETIC_NO_POST"
    FAILED_SYNTHETIC_SAFE = "FAILED_SYNTHETIC_SAFE"
    BLOCKED_PLAN_INVALID = "BLOCKED_PLAN_INVALID"


@dataclass(frozen=True)
class H11V3FaultScenario:
    name_safe_label: str
    cycle_input: H11V3FakeCycleInput
    expected_state: H11V3ObservedState
    expected_entry_attempts: int
    expected_settlement_attempts: int


@dataclass(frozen=True)
class H11V3FaultSoakReport:
    status: H11V3FaultSoakStatus
    synthetic_cycle_count: int
    matched_cycle_count: int
    mismatched_scenarios: tuple[str, ...]
    final_state_distribution: tuple[tuple[str, int], ...]
    halt_reason_distribution: tuple[tuple[str, int], ...]
    journal_verification_failures: int
    notification_failures: int
    max_entry_attempts_observed: int
    max_settlement_attempts_observed: int
    duplicate_attempt_invariant_ok: bool
    no_retry_invariant_ok: bool
    actual_post_count: int = 0
    broker_read_performed: bool = False
    credential_env_read: bool = False
    raw_id_value_exposure: bool = False
    wall_clock_24h_soak_completed: bool = False
    actual_activation_ready: bool = False

    def __bool__(self) -> bool:
        return False


def build_h11_v3_fault_scenarios() -> tuple[H11V3FaultScenario, ...]:
    open_gate = H11V3FakeSafetyGate(
        boot_reconciled=True,
        budget_remaining=True,
        kill_off=True,
        dead_man_alive=True,
        notification_ready=True,
        broker_native_expiry_confirmed=True,
        sealed_credential_boundary_reviewed=True,
    )

    def cycle(
        *,
        entry: H11V3FakeOutcome = H11V3FakeOutcome.ACCEPTED_SANITIZED,
        gate: H11V3FakeSafetyGate = open_gate,
        protection: bool = True,
        position: bool = True,
        oco: bool = False,
        settlement: H11V3FakeOutcome | None = None,
        flat: bool = False,
    ) -> H11V3FakeCycleInput:
        return H11V3FakeCycleInput(
            cycle_day_jst="2026-07-13",
            safety_gate=gate,
            entry_outcome=entry,
            protection_reconciled=protection,
            position_protected=position,
            broker_oco_settled=oco,
            settlement_outcome=settlement,
            flat_reconciled=flat,
        )

    halted = H11V3ObservedState.HALTED
    return (
        H11V3FaultScenario(
            "SUCCESS_BROKER_OCO",
            cycle(oco=True, flat=True),
            H11V3ObservedState.FLAT_RECONCILED,
            1,
            0,
        ),
        H11V3FaultScenario(
            "SUCCESS_DEDICATED_SETTLEMENT",
            cycle(settlement=H11V3FakeOutcome.ACCEPTED_SANITIZED, flat=True),
            H11V3ObservedState.FLAT_RECONCILED,
            1,
            1,
        ),
        H11V3FaultScenario(
            "ENTRY_TIMEOUT",
            cycle(entry=H11V3FakeOutcome.TIMEOUT_SANITIZED),
            halted,
            1,
            0,
        ),
        H11V3FaultScenario(
            "ENTRY_NETWORK_ERROR",
            cycle(entry=H11V3FakeOutcome.NETWORK_ERROR_SANITIZED),
            halted,
            1,
            0,
        ),
        H11V3FaultScenario(
            "ENTRY_REJECTED",
            cycle(entry=H11V3FakeOutcome.REJECTED_SANITIZED),
            halted,
            1,
            0,
        ),
        H11V3FaultScenario(
            "PROTECTION_NOT_RECONCILED",
            cycle(protection=False),
            halted,
            1,
            0,
        ),
        H11V3FaultScenario(
            "BROKER_OCO_FLAT_UNKNOWN",
            cycle(oco=True, flat=False),
            halted,
            1,
            0,
        ),
        H11V3FaultScenario(
            "SETTLEMENT_UNKNOWN",
            cycle(settlement=H11V3FakeOutcome.UNKNOWN_SANITIZED),
            halted,
            1,
            1,
        ),
        H11V3FaultScenario(
            "BOOT_RECONCILIATION_MISSING",
            cycle(gate=replace(open_gate, boot_reconciled=False)),
            halted,
            0,
            0,
        ),
        H11V3FaultScenario(
            "DEAD_MAN_MISSING",
            cycle(gate=replace(open_gate, dead_man_alive=False)),
            halted,
            0,
            0,
        ),
        H11V3FaultScenario(
            "NOTIFICATION_PATH_MISSING",
            cycle(gate=replace(open_gate, notification_ready=False)),
            halted,
            0,
            0,
        ),
        H11V3FaultScenario(
            "PENDING_EXPIRY_UNKNOWN",
            cycle(gate=replace(open_gate, broker_native_expiry_confirmed=False)),
            halted,
            0,
            0,
        ),
        H11V3FaultScenario(
            "SEALED_CREDENTIAL_BOUNDARY_MISSING",
            cycle(gate=replace(open_gate, sealed_credential_boundary_reviewed=False)),
            halted,
            0,
            0,
        ),
    )


def run_h11_v3_fault_soak_no_post(
    *, target_cycle_count: int = H11_V3_MIN_SYNTHETIC_SOAK_CYCLES
) -> H11V3FaultSoakReport:
    if target_cycle_count < H11_V3_MIN_SYNTHETIC_SOAK_CYCLES:
        return H11V3FaultSoakReport(
            status=H11V3FaultSoakStatus.BLOCKED_PLAN_INVALID,
            synthetic_cycle_count=0,
            matched_cycle_count=0,
            mismatched_scenarios=("TARGET_CYCLE_COUNT_BELOW_MINIMUM",),
            final_state_distribution=(),
            halt_reason_distribution=(),
            journal_verification_failures=0,
            notification_failures=0,
            max_entry_attempts_observed=0,
            max_settlement_attempts_observed=0,
            duplicate_attempt_invariant_ok=False,
            no_retry_invariant_ok=False,
        )

    scenarios = build_h11_v3_fault_scenarios()
    mismatches: list[str] = []
    final_states: list[str] = []
    halt_reasons: list[str] = []
    journal_failures = 0
    notification_failures = 0
    max_entry = 0
    max_settlement = 0

    for index in range(target_cycle_count):
        scenario = scenarios[index % len(scenarios)]
        with TemporaryDirectory(prefix="h11_v3_soak_") as temp_dir:
            root = Path(temp_dir)
            journal = H11V3SafeJournal(root / "journal.jsonl")
            state_store = H11V3ObservedStateStore(root / "state.json")
            risk_state = H11V3RiskPersistentState()
            risk_gate = evaluate_h11_v3_risk_before_entry(
                state=risk_state, cycle_day_jst=scenario.cycle_input.cycle_day_jst
            )
            if not risk_gate.allowed:
                mismatches.append(f"{scenario.name_safe_label}_RISK_GATE")
                continue

            boot = evaluate_h11_v3_boot_reconcile(
                H11V3BootReconcileInput(
                    local_state=H11V3ObservedState.READY,
                    broker_status=H11V3BrokerCycleSafeStatus.FLAT_CLEAR,
                    safe_read_performed=True,
                    safe_read_fresh=True,
                )
            )
            if boot.reconciled:
                journal.append(
                    cycle_day_jst=scenario.cycle_input.cycle_day_jst,
                    event=H11V3JournalEvent.BOOT_RECONCILED,
                    state=H11V3ObservedState.READY,
                )

            if scenario.expected_entry_attempts:
                record_h11_v3_entry_attempt(
                    state=risk_state,
                    cycle_day_jst=scenario.cycle_input.cycle_day_jst,
                )
                journal.append(
                    cycle_day_jst=scenario.cycle_input.cycle_day_jst,
                    event=H11V3JournalEvent.INTENT_PERSISTED,
                    state=H11V3ObservedState.INTENT_PERSISTED,
                )

            result = run_h11_v3_fake_cycle_no_post(
                store=state_store, cycle_input=scenario.cycle_input
            )
            event = (
                H11V3JournalEvent.FLAT_RECONCILED
                if result.final_state is H11V3ObservedState.FLAT_RECONCILED
                else H11V3JournalEvent.HALTED
            )
            journal.append(
                cycle_day_jst=scenario.cycle_input.cycle_day_jst,
                event=event,
                state=result.final_state,
            )
            try:
                journal.summary()
            except Exception:  # noqa: BLE001 - safe count only in the report
                journal_failures += 1

            notifier = H11V3FakeNotifier()
            notification = (
                H11V3NotificationCategory.FLAT_CONFIRMED
                if result.final_state is H11V3ObservedState.FLAT_RECONCILED
                else H11V3NotificationCategory.UNKNOWN_HALTED
            )
            if not notifier.notify(notification):
                notification_failures += 1

            matched = (
                result.final_state is scenario.expected_state
                and result.entry_attempt_count == scenario.expected_entry_attempts
                and result.settlement_attempt_count
                == scenario.expected_settlement_attempts
                and result.actual_post_count == 0
            )
            if not matched:
                mismatches.append(scenario.name_safe_label)
            final_states.append(result.final_state.value)
            if result.halt_reason_safe_label:
                halt_reasons.append(result.halt_reason_safe_label)
            max_entry = max(max_entry, result.entry_attempt_count)
            max_settlement = max(max_settlement, result.settlement_attempt_count)

    passed = not mismatches and not journal_failures and not notification_failures
    return H11V3FaultSoakReport(
        status=(
            H11V3FaultSoakStatus.PASSED_SYNTHETIC_NO_POST
            if passed
            else H11V3FaultSoakStatus.FAILED_SYNTHETIC_SAFE
        ),
        synthetic_cycle_count=target_cycle_count,
        matched_cycle_count=target_cycle_count - len(mismatches),
        mismatched_scenarios=tuple(mismatches),
        final_state_distribution=_distribution(final_states),
        halt_reason_distribution=_distribution(halt_reasons),
        journal_verification_failures=journal_failures,
        notification_failures=notification_failures,
        max_entry_attempts_observed=max_entry,
        max_settlement_attempts_observed=max_settlement,
        duplicate_attempt_invariant_ok=max_entry <= 1 and max_settlement <= 1,
        no_retry_invariant_ok=max_entry <= 1 and max_settlement <= 1,
    )


def _distribution(values: list[str]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return tuple(sorted(counts.items()))
