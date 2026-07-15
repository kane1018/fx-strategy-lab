"""Bounded fake-cycle coordinator for H11_AUTO_PARALLEL_PHASE_A_NO_POST."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from app.h11_auto.boundary import (
    FakeNotifier,
    FakePositionExitOutcome,
    FakePositionExitSender,
    FakeProtectedEntryOutcome,
    FakeProtectedEntrySender,
    H11AutoBoundaryError,
    NotificationCategory,
    PhaseAPositionExitSender,
    PhaseAProtectedEntrySender,
    RefusingPositionExitSender,
    RefusingProtectedEntrySender,
)
from app.h11_auto.contracts import FormalSignal, PhaseAExecutionPolicy, SignalDecision
from app.h11_auto.persistence import H11AutoStateStore, StoredCycle
from app.h11_auto.risk import (
    PhaseAEntryGateResult,
    PhaseASafetySnapshot,
    evaluate_phase_a_entry_gate,
)
from app.h11_auto.state_machine import AutoCycleState


class FakeCycleStatus(str, Enum):
    NO_ACTION_STAY = "NO_ACTION_STAY"
    BLOCKED_SAFE = "BLOCKED_SAFE"
    POSITION_PROTECTED_SYNTHETIC = "POSITION_PROTECTED_SYNTHETIC"
    FLAT_RECONCILED_SYNTHETIC = "FLAT_RECONCILED_SYNTHETIC"
    HALTED_SAFE = "HALTED_SAFE"


@dataclass(frozen=True)
class FakeCycleResult:
    status: FakeCycleStatus
    final_state: AutoCycleState | None
    blocked_reasons: tuple[str, ...]
    intent_created: bool
    attempt_count: int
    exit_attempt_count: int = 0
    actual_post_count: int = 0
    broker_write_performed: bool = False
    network_access_performed: bool = False

    def __bool__(self) -> bool:
        return False


class H11AutoPhaseAEngine:
    def __init__(
        self,
        *,
        store: H11AutoStateStore,
        sender: PhaseAProtectedEntrySender | None = None,
        exit_sender: PhaseAPositionExitSender | None = None,
        notifier: FakeNotifier | None = None,
    ) -> None:
        self.store = store
        self.sender = sender if sender is not None else RefusingProtectedEntrySender()
        self.exit_sender = (
            exit_sender if exit_sender is not None else RefusingPositionExitSender()
        )
        self.notifier = notifier if notifier is not None else FakeNotifier()
        if type(self.sender) not in (  # noqa: E721 - exact fake boundary types only
            FakeProtectedEntrySender,
            RefusingProtectedEntrySender,
        ):
            raise H11AutoBoundaryError("PHASE_A_ENTRY_SENDER_TYPE_REFUSED")
        if type(self.exit_sender) not in (  # noqa: E721 - exact fake boundary types only
            FakePositionExitSender,
            RefusingPositionExitSender,
        ):
            raise H11AutoBoundaryError("PHASE_A_EXIT_SENDER_TYPE_REFUSED")
        if type(self.notifier) is not FakeNotifier:  # noqa: E721
            raise H11AutoBoundaryError("PHASE_A_NOTIFIER_TYPE_REFUSED")
        if (
            self.sender.fake_only is not True
            or self.exit_sender.fake_only is not True
            or self.sender.actual_post_count != 0
            or self.exit_sender.actual_post_count != 0
            or self.sender.network_access_performed
            or self.exit_sender.network_access_performed
        ):
            raise H11AutoBoundaryError("PHASE_A_NON_FAKE_BOUNDARY_REFUSED")

    def run_signal_once_synthetic(
        self,
        *,
        signal: FormalSignal,
        policy: PhaseAExecutionPolicy,
        safety: PhaseASafetySnapshot,
        now_utc: datetime,
    ) -> FakeCycleResult:
        if signal.decision is SignalDecision.STAY:
            reasons: list[str] = []
            if not policy.accepts(signal):
                reasons.append("SIGNAL_POLICY_MISMATCH")
            if now_utc.tzinfo is None or now_utc >= signal.valid_until_utc:
                reasons.append("SIGNAL_EXPIRED_OR_CLOCK_INVALID")
            if reasons:
                return FakeCycleResult(
                    status=FakeCycleStatus.BLOCKED_SAFE,
                    final_state=None,
                    blocked_reasons=tuple(reasons),
                    intent_created=False,
                    attempt_count=0,
                )
            return FakeCycleResult(
                status=FakeCycleStatus.NO_ACTION_STAY,
                final_state=None,
                blocked_reasons=(),
                intent_created=False,
                attempt_count=0,
            )
        safety = replace(
            safety,
            active_intent_count=max(
                safety.active_intent_count, self.store.active_intent_count()
            ),
            entries_today=max(
                safety.entries_today,
                self.store.entry_attempts_on_jst_day(now_utc=now_utc),
            ),
            kill_requested=safety.kill_requested or self.store.halt_latched(),
        )
        gate = evaluate_phase_a_entry_gate(
            signal=signal,
            policy=policy,
            snapshot=safety,
            now_utc=now_utc,
        )
        if not gate.fake_cycle_allowed:
            return self._blocked(gate)
        cycle = self.store.create_intent(signal=signal, policy=policy, now_utc=now_utc)
        if not self.notifier.notify(NotificationCategory.INTENT_RECORDED):
            return self._halt_before_attempt(
                cycle=cycle,
                reason="SYNTHETIC_INTENT_NOTIFICATION_FAILED",
                now_utc=now_utc,
            )
        cycle = self.store.record_attempt_started(
            intent_id=cycle.intent_id, now_utc=now_utc
        )
        try:
            outcome = self.sender.send_once_synthetic(intent_id=cycle.intent_id)
        except H11AutoBoundaryError:
            return self._halt_after_reason(
                cycle=cycle,
                reason="SYNTHETIC_BOUNDARY_REFUSED",
                now_utc=now_utc,
            )
        if outcome is FakeProtectedEntryOutcome.ACCEPTED_AND_PROTECTED:
            cycle = self.store.transition(
                intent_id=cycle.intent_id,
                target=AutoCycleState.POSITION_PROTECTED,
                event_category="POSITION_PROTECTED_SYNTHETIC",
                now_utc=now_utc,
            )
            if not self.notifier.notify(NotificationCategory.POSITION_PROTECTED):
                return self._halt_after_reason(
                    cycle=cycle,
                    reason="SYNTHETIC_PROTECTED_NOTIFICATION_FAILED",
                    now_utc=now_utc,
                )
            return self._result(
                status=FakeCycleStatus.POSITION_PROTECTED_SYNTHETIC,
                cycle=cycle,
            )
        return self._halt_after_outcome(cycle=cycle, outcome=outcome, now_utc=now_utc)

    def complete_exit_once_synthetic(
        self, *, intent_id: str, now_utc: datetime
    ) -> FakeCycleResult:
        cycle = self.store.record_exit_attempt_started(
            intent_id=intent_id, now_utc=now_utc
        )
        try:
            outcome = self.exit_sender.send_once_synthetic(intent_id=intent_id)
        except H11AutoBoundaryError:
            return self._halt_after_reason(
                cycle=cycle,
                reason="SYNTHETIC_EXIT_BOUNDARY_REFUSED",
                now_utc=now_utc,
            )
        if outcome is FakePositionExitOutcome.ACCEPTED_AND_FLAT:
            flat = self.store.transition(
                intent_id=intent_id,
                target=AutoCycleState.FLAT_RECONCILED,
                event_category="FLAT_RECONCILED_SYNTHETIC",
                now_utc=now_utc,
            )
            if not self.notifier.notify(NotificationCategory.FLAT_RECONCILED):
                return self._halt_after_reason(
                    cycle=flat,
                    reason="SYNTHETIC_FLAT_NOTIFICATION_FAILED",
                    now_utc=now_utc,
                )
            return self._result(
                status=FakeCycleStatus.FLAT_RECONCILED_SYNTHETIC,
                cycle=flat,
            )
        return self._halt_after_reason(
            cycle=cycle,
            reason=f"SYNTHETIC_EXIT_{outcome.value}",
            now_utc=now_utc,
        )

    def _halt_after_outcome(
        self,
        *,
        cycle: StoredCycle,
        outcome: FakeProtectedEntryOutcome,
        now_utc: datetime,
    ) -> FakeCycleResult:
        reason = f"SYNTHETIC_{outcome.value}"
        return self._halt_after_reason(cycle=cycle, reason=reason, now_utc=now_utc)

    def _halt_before_attempt(
        self,
        *,
        cycle: StoredCycle,
        reason: str,
        now_utc: datetime,
    ) -> FakeCycleResult:
        halted = self.store.transition(
            intent_id=cycle.intent_id,
            target=AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
            event_category="HALTED_SYNTHETIC",
            now_utc=now_utc,
            halt_reason=reason,
        )
        self.notifier.notify(NotificationCategory.HALTED)
        return self._result(
            status=FakeCycleStatus.HALTED_SAFE,
            cycle=halted,
            blocked_reasons=(reason,),
        )

    def _halt_after_reason(
        self,
        *,
        cycle: StoredCycle,
        reason: str,
        now_utc: datetime,
    ) -> FakeCycleResult:
        halted = self.store.transition(
            intent_id=cycle.intent_id,
            target=AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
            event_category="HALTED_SYNTHETIC",
            now_utc=now_utc,
            halt_reason=reason,
        )
        self.notifier.notify(NotificationCategory.HALTED)
        return self._result(
            status=FakeCycleStatus.HALTED_SAFE,
            cycle=halted,
            blocked_reasons=(reason,),
        )

    @staticmethod
    def _blocked(gate: PhaseAEntryGateResult) -> FakeCycleResult:
        return FakeCycleResult(
            status=FakeCycleStatus.BLOCKED_SAFE,
            final_state=None,
            blocked_reasons=gate.blocked_reasons,
            intent_created=False,
            attempt_count=0,
        )

    def _result(
        self,
        *,
        status: FakeCycleStatus,
        cycle: StoredCycle,
        blocked_reasons: tuple[str, ...] = (),
    ) -> FakeCycleResult:
        return FakeCycleResult(
            status=status,
            final_state=cycle.state,
            blocked_reasons=blocked_reasons,
            intent_created=True,
            attempt_count=cycle.attempt_count,
            exit_attempt_count=cycle.exit_attempt_count,
            actual_post_count=(
                self.sender.actual_post_count + self.exit_sender.actual_post_count
            ),
            network_access_performed=(
                self.sender.network_access_performed
                or self.exit_sender.network_access_performed
            ),
        )
