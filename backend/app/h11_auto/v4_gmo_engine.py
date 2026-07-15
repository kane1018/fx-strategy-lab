"""Deterministic fake-only coordinator for the relaxed GMO v4 profile."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Protocol

from app.h11_auto.contracts import FormalSignal, SignalDecision
from app.h11_auto.v4_gmo_boundary import (
    FakeV4GmoBroker,
    RefusingV4GmoBroker,
    V4GmoBoundaryError,
    V4GmoSyntheticBroker,
)
from app.h11_auto.v4_gmo_contracts import (
    V4GmoAction,
    V4GmoBrokerSnapshot,
    V4GmoCycleState,
    V4GmoExecutionPolicy,
    V4GmoPreflightSnapshot,
    V4GmoProtectionStatus,
    build_v4_action_plan,
)
from app.h11_auto.v4_gmo_persistence import V4GmoStateStore, V4GmoStoredCycle


class V4GmoCycleStatus(str, Enum):
    NO_ACTION_STAY = "NO_ACTION_STAY"
    BLOCKED_SAFE = "BLOCKED_SAFE"
    POSITION_PROTECTED_SYNTHETIC = "POSITION_PROTECTED_SYNTHETIC"
    FLAT_RECONCILED_SYNTHETIC = "FLAT_RECONCILED_SYNTHETIC"
    HALTED_OPERATOR_REVIEW_REQUIRED = "HALTED_OPERATOR_REVIEW_REQUIRED"


class V4GmoClock(Protocol):
    def now_utc(self) -> datetime: ...


class SystemV4GmoClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class V4GmoCycleResult:
    status: V4GmoCycleStatus
    final_state: V4GmoCycleState | None
    cycle_ref: str | None
    blocked_reasons: tuple[str, ...]
    action_attempt_count: int
    market_entry_attempt_count: int
    cancel_attempt_count: int
    protection_attempt_count: int
    protection_cancel_attempt_count: int
    emergency_exit_attempt_count: int
    filled_size: int
    protected_size: int
    actual_post_count: int = 0
    broker_write_performed: bool = False
    credential_read_performed: bool = False
    network_access_performed: bool = False

    def __bool__(self) -> bool:
        return False


class H11V4GmoNoPostEngine:
    """Runs the complete multi-action sequence against exact fake boundaries."""

    def __init__(
        self,
        *,
        store: V4GmoStateStore,
        broker: V4GmoSyntheticBroker | None = None,
        clock: V4GmoClock | None = None,
    ) -> None:
        self.store = store
        self.broker = broker if broker is not None else RefusingV4GmoBroker()
        self.clock = clock
        if type(self.broker) not in (FakeV4GmoBroker, RefusingV4GmoBroker):  # noqa: E721
            raise V4GmoBoundaryError("V4_GMO_BROKER_TYPE_REFUSED")
        if (
            self.broker.fake_only is not True
            or self.broker.actual_post_count != 0
            or self.broker.broker_write_performed
            or self.broker.credential_read_performed
            or self.broker.network_access_performed
        ):
            raise V4GmoBoundaryError("V4_GMO_NON_FAKE_BOUNDARY_REFUSED")

    def run_signal_once_synthetic(
        self,
        *,
        signal: FormalSignal,
        policy: V4GmoExecutionPolicy,
        preflight: V4GmoPreflightSnapshot,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        reasons = list(preflight.blocked_reasons())
        if now_utc.tzinfo is None or now_utc >= signal.valid_until_utc:
            reasons.append("SIGNAL_EXPIRED_OR_CLOCK_INVALID")
        if signal.decision is SignalDecision.STAY:
            if (
                signal.strategy_version != policy.strategy_version
                or signal.signal_config_hash != policy.signal_config_hash
                or signal.horizon is not policy.selected_horizon
            ):
                reasons.append("SIGNAL_POLICY_MISMATCH")
            if reasons:
                return self._empty_result(
                    status=V4GmoCycleStatus.BLOCKED_SAFE,
                    reasons=tuple(reasons),
                )
            return self._empty_result(status=V4GmoCycleStatus.NO_ACTION_STAY)
        if not policy.accepts(signal):
            reasons.append("SIGNAL_POLICY_MISMATCH")
        if self.store.active_cycle_count() != 0:
            reasons.append("ACTIVE_V4_CYCLE_EXISTS")
        if self.store.halt_latched():
            reasons.append("OPERATOR_HALT_LATCHED")
        if reasons:
            return self._empty_result(
                status=V4GmoCycleStatus.BLOCKED_SAFE,
                reasons=tuple(reasons),
            )
        cycle = self.store.create_cycle(signal=signal, policy=policy, now_utc=now_utc)
        return self._attempt_market_entry(cycle=cycle, policy=policy, now_utc=now_utc)

    def resume_synthetic(
        self,
        *,
        cycle_ref: str,
        policy: V4GmoExecutionPolicy,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        cycle = self.store.load_cycle(cycle_ref)
        if cycle.policy_config_hash != policy.config_hash:
            return self._halt(
                cycle=cycle,
                reason="POLICY_CONFIG_HASH_MISMATCH",
                now_utc=now_utc,
            )
        if cycle.state is V4GmoCycleState.ENTRY_INTENT_PERSISTED:
            snapshot = self._read_snapshot_or_none()
            if snapshot is None or _flat_snapshot_blocked_reasons(snapshot):
                return self._halt(
                    cycle=cycle,
                    reason="RESTART_ENTRY_PREFLIGHT_NOT_FLAT_OR_UNKNOWN",
                    now_utc=now_utc,
                )
            return self._attempt_market_entry(cycle=cycle, policy=policy, now_utc=now_utc)
        if cycle.state is V4GmoCycleState.MARKET_ENTRY_ATTEMPTED:
            cycle = self.store.transition(
                cycle_ref=cycle_ref,
                target=V4GmoCycleState.ENTRY_RECONCILING,
                event_category="RESTART_ENTRY_RECONCILING",
                now_utc=now_utc,
            )
            return self._reconcile_entry(cycle=cycle, policy=policy, now_utc=now_utc)
        if cycle.state is V4GmoCycleState.REMAINDER_CANCEL_ATTEMPTED:
            cycle = self.store.transition(
                cycle_ref=cycle_ref,
                target=V4GmoCycleState.ENTRY_RECONCILING,
                event_category="RESTART_CANCEL_RECONCILING",
                now_utc=now_utc,
            )
            return self._reconcile_entry(cycle=cycle, policy=policy, now_utc=now_utc)
        if cycle.state is V4GmoCycleState.ENTRY_RECONCILING:
            return self._reconcile_entry(cycle=cycle, policy=policy, now_utc=now_utc)
        if cycle.state is V4GmoCycleState.ENTRY_FILLED_UNPROTECTED:
            return self._ensure_protection(cycle=cycle, policy=policy, now_utc=now_utc)
        if cycle.state is V4GmoCycleState.PROTECTION_INTENT_PERSISTED:
            return self._attempt_protection(cycle=cycle, policy=policy, now_utc=now_utc)
        if cycle.state is V4GmoCycleState.PROTECTION_ATTEMPTED:
            cycle = self.store.transition(
                cycle_ref=cycle_ref,
                target=V4GmoCycleState.PROTECTION_RECONCILING,
                event_category="RESTART_PROTECTION_RECONCILING",
                now_utc=now_utc,
            )
            return self._reconcile_protection(cycle=cycle, policy=policy, now_utc=now_utc)
        if cycle.state is V4GmoCycleState.PROTECTION_RECONCILING:
            return self._reconcile_protection(cycle=cycle, policy=policy, now_utc=now_utc)
        if cycle.state is V4GmoCycleState.PROTECTION_CANCEL_INTENT_PERSISTED:
            return self._attempt_cancel_protection(
                cycle=cycle,
                policy=policy,
                protection_size=cycle.protected_size,
                now_utc=now_utc,
            )
        if cycle.state is V4GmoCycleState.PROTECTION_CANCEL_ATTEMPTED:
            cycle = self.store.transition(
                cycle_ref=cycle_ref,
                target=V4GmoCycleState.PROTECTION_CANCEL_RECONCILING,
                event_category="RESTART_PROTECTION_CANCEL_RECONCILING",
                now_utc=now_utc,
            )
            return self._reconcile_cancelled_protection(
                cycle=cycle, policy=policy, now_utc=now_utc
            )
        if cycle.state is V4GmoCycleState.PROTECTION_CANCEL_RECONCILING:
            return self._reconcile_cancelled_protection(
                cycle=cycle, policy=policy, now_utc=now_utc
            )
        if cycle.state is V4GmoCycleState.EMERGENCY_EXIT_INTENT_PERSISTED:
            return self._attempt_emergency_exit(cycle=cycle, policy=policy, now_utc=now_utc)
        if cycle.state is V4GmoCycleState.EMERGENCY_EXIT_ATTEMPTED:
            return self._reconcile_emergency_exit(cycle=cycle, now_utc=now_utc)
        if cycle.state is V4GmoCycleState.POSITION_PROTECTED:
            return self._reconcile_existing_protected_position(
                cycle=cycle,
                policy=policy,
                now_utc=now_utc,
            )
        if cycle.state is V4GmoCycleState.FLAT_RECONCILED:
            return self._result(
                status=V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC,
                cycle=cycle,
            )
        return self._result(
            status=V4GmoCycleStatus.HALTED_OPERATOR_REVIEW_REQUIRED,
            cycle=cycle,
            reasons=(cycle.halt_reason or "OPERATOR_REVIEW_REQUIRED",),
        )

    def _reconcile_existing_protected_position(
        self,
        *,
        cycle: V4GmoStoredCycle,
        policy: V4GmoExecutionPolicy,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        snapshot = self._read_snapshot_or_none()
        if snapshot is None or not snapshot.fresh or not snapshot.result_known:
            return self._halt(
                cycle=cycle,
                reason="PROTECTED_POSITION_RECONCILIATION_UNKNOWN",
                now_utc=now_utc,
            )
        if not _flat_snapshot_blocked_reasons(snapshot):
            flat = self.store.transition(
                cycle_ref=cycle.cycle_ref,
                target=V4GmoCycleState.FLAT_RECONCILED,
                event_category="PROTECTED_POSITION_FOUND_FLAT",
                now_utc=now_utc,
                filled_size=0,
                protected_size=0,
            )
            return self._result(
                status=V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC,
                cycle=flat,
            )
        exact = (
            snapshot.position_count == 1
            and snapshot.position_side is SignalDecision(cycle.side)
            and snapshot.filled_size == cycle.filled_size
            and snapshot.pending_entry_size == 0
            and snapshot.protection_status is V4GmoProtectionStatus.EXACT_MATCH
            and snapshot.protection_size == cycle.filled_size
        )
        if exact:
            return self._result(
                status=V4GmoCycleStatus.POSITION_PROTECTED_SYNTHETIC,
                cycle=cycle,
            )
        if snapshot.position_count != 1:
            return self._halt(
                cycle=cycle,
                reason="PROTECTED_POSITION_COUNT_MISMATCH",
                now_utc=now_utc,
            )
        if snapshot.position_side is not SignalDecision(cycle.side):
            return self._halt(
                cycle=cycle,
                reason="PROTECTED_POSITION_SIDE_MISMATCH",
                now_utc=now_utc,
            )
        if snapshot.filled_size != cycle.filled_size or snapshot.pending_entry_size != 0:
            return self._halt(
                cycle=cycle,
                reason="PROTECTED_POSITION_SIZE_MISMATCH",
                now_utc=now_utc,
            )
        if snapshot.protection_size > 0:
            cancelling = self.store.transition(
                cycle_ref=cycle.cycle_ref,
                target=V4GmoCycleState.PROTECTION_CANCEL_INTENT_PERSISTED,
                event_category="RESTART_MISMATCHED_PROTECTION_CANCEL_INTENT",
                now_utc=now_utc,
                protected_size=snapshot.protection_size,
            )
            return self._attempt_cancel_protection(
                cycle=cancelling,
                policy=policy,
                protection_size=snapshot.protection_size,
                now_utc=now_utc,
            )
        return self._start_emergency_exit(
            cycle=cycle,
            policy=policy,
            reason="RESTART_PROTECTION_MISSING_EXIT_REQUIRED",
            now_utc=now_utc,
        )

    def _attempt_market_entry(
        self,
        *,
        cycle: V4GmoStoredCycle,
        policy: V4GmoExecutionPolicy,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        plan = build_v4_action_plan(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.MARKET_ENTRY,
            side=SignalDecision(cycle.side),
            requested_size=cycle.requested_size,
            protection_contract_hash=policy.protection_contract_hash,
        )
        action_time = self._now(now_utc)
        cycle = self.store.record_action_attempt(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.MARKET_ENTRY,
            target=V4GmoCycleState.MARKET_ENTRY_ATTEMPTED,
            now_utc=action_time,
        )
        try:
            outcome = self.broker.perform_once_synthetic(plan=plan)
        except V4GmoBoundaryError:
            return self._halt(
                cycle=cycle,
                reason="MARKET_ENTRY_BOUNDARY_REFUSED",
                now_utc=now_utc,
            )
        self.store.record_action_outcome(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.MARKET_ENTRY,
            outcome_safe_label=outcome.value,
        )
        reconcile_time = self._now(now_utc)
        cycle = self.store.transition(
            cycle_ref=cycle.cycle_ref,
            target=V4GmoCycleState.ENTRY_RECONCILING,
            event_category="ENTRY_RECONCILING",
            now_utc=reconcile_time,
        )
        return self._reconcile_entry(
            cycle=cycle,
            policy=policy,
            now_utc=reconcile_time,
        )

    def _reconcile_entry(
        self,
        *,
        cycle: V4GmoStoredCycle,
        policy: V4GmoExecutionPolicy,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        snapshot = self._read_snapshot_or_none()
        if snapshot is None or not snapshot.fresh or not snapshot.result_known:
            return self._halt(
                cycle=cycle,
                reason="ENTRY_RECONCILIATION_UNKNOWN",
                now_utc=now_utc,
            )
        invalid_reason = self._entry_snapshot_invalid_reason(
            snapshot=snapshot,
            cycle=cycle,
        )
        if invalid_reason is not None:
            return self._halt(cycle=cycle, reason=invalid_reason, now_utc=now_utc)
        if snapshot.pending_entry_size > 0:
            if self.store.action_attempted(
                cycle_ref=cycle.cycle_ref,
                action=V4GmoAction.CANCEL_ENTRY_REMAINDER,
            ):
                return self._halt(
                    cycle=cycle,
                    reason="ENTRY_REMAINDER_PERSISTS_AFTER_CANCEL",
                    now_utc=now_utc,
                )
            return self._attempt_cancel_remainder(
                cycle=cycle,
                policy=policy,
                snapshot=snapshot,
                now_utc=now_utc,
            )
        if snapshot.position_count == 0 and snapshot.filled_size == 0:
            flat = self.store.transition(
                cycle_ref=cycle.cycle_ref,
                target=V4GmoCycleState.FLAT_RECONCILED,
                event_category="ENTRY_REJECTED_OR_UNFILLED_FLAT",
                now_utc=now_utc,
            )
            return self._result(
                status=V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC,
                cycle=flat,
            )
        filled = self.store.transition(
            cycle_ref=cycle.cycle_ref,
            target=V4GmoCycleState.ENTRY_FILLED_UNPROTECTED,
            event_category="ENTRY_FILLED_UNPROTECTED",
            now_utc=now_utc,
            filled_size=snapshot.filled_size,
            protected_size=snapshot.protection_size,
            unprotected_since_utc=now_utc,
        )
        return self._ensure_protection(cycle=filled, policy=policy, now_utc=now_utc)

    def _attempt_cancel_remainder(
        self,
        *,
        cycle: V4GmoStoredCycle,
        policy: V4GmoExecutionPolicy,
        snapshot: V4GmoBrokerSnapshot,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        plan = build_v4_action_plan(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.CANCEL_ENTRY_REMAINDER,
            side=SignalDecision(cycle.side),
            requested_size=snapshot.pending_entry_size,
            protection_contract_hash=policy.protection_contract_hash,
        )
        cycle = self.store.record_action_attempt(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.CANCEL_ENTRY_REMAINDER,
            target=V4GmoCycleState.REMAINDER_CANCEL_ATTEMPTED,
            now_utc=now_utc,
        )
        try:
            outcome = self.broker.perform_once_synthetic(plan=plan)
        except V4GmoBoundaryError:
            return self._halt(
                cycle=cycle,
                reason="CANCEL_REMAINDER_BOUNDARY_REFUSED",
                now_utc=now_utc,
            )
        self.store.record_action_outcome(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.CANCEL_ENTRY_REMAINDER,
            outcome_safe_label=outcome.value,
        )
        cycle = self.store.transition(
            cycle_ref=cycle.cycle_ref,
            target=V4GmoCycleState.ENTRY_RECONCILING,
            event_category="CANCEL_REMAINDER_RECONCILING",
            now_utc=now_utc,
        )
        return self._reconcile_entry(cycle=cycle, policy=policy, now_utc=now_utc)

    def _ensure_protection(
        self,
        *,
        cycle: V4GmoStoredCycle,
        policy: V4GmoExecutionPolicy,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        current_time = self._now(now_utc)
        if cycle.unprotected_since_utc is None:
            return self._halt(
                cycle=cycle,
                reason="UNPROTECTED_START_TIME_MISSING",
                now_utc=current_time,
            )
        unprotected_since = datetime.fromisoformat(cycle.unprotected_since_utc)
        elapsed = (current_time - unprotected_since).total_seconds()
        if elapsed < 0:
            return self._halt(
                cycle=cycle,
                reason="CLOCK_MOVED_BACKWARD",
                now_utc=current_time,
            )
        if elapsed > policy.max_unprotected_seconds:
            return self._start_emergency_exit(
                cycle=cycle,
                policy=policy,
                reason="UNPROTECTED_WINDOW_EXCEEDED",
                now_utc=current_time,
            )
        cycle = self.store.transition(
            cycle_ref=cycle.cycle_ref,
            target=V4GmoCycleState.PROTECTION_INTENT_PERSISTED,
            event_category="PROTECTION_INTENT_PERSISTED",
            now_utc=current_time,
        )
        return self._attempt_protection(
            cycle=cycle,
            policy=policy,
            now_utc=current_time,
        )

    def _attempt_protection(
        self,
        *,
        cycle: V4GmoStoredCycle,
        policy: V4GmoExecutionPolicy,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        plan = build_v4_action_plan(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
            side=SignalDecision(cycle.side),
            requested_size=cycle.filled_size,
            protection_contract_hash=policy.protection_contract_hash,
        )
        cycle = self.store.record_action_attempt(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
            target=V4GmoCycleState.PROTECTION_ATTEMPTED,
            now_utc=now_utc,
        )
        try:
            outcome = self.broker.perform_once_synthetic(plan=plan)
        except V4GmoBoundaryError:
            return self._halt(
                cycle=cycle,
                reason="PROTECTION_BOUNDARY_REFUSED",
                now_utc=now_utc,
            )
        self.store.record_action_outcome(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
            outcome_safe_label=outcome.value,
        )
        cycle = self.store.transition(
            cycle_ref=cycle.cycle_ref,
            target=V4GmoCycleState.PROTECTION_RECONCILING,
            event_category="PROTECTION_RECONCILING",
            now_utc=now_utc,
        )
        return self._reconcile_protection(cycle=cycle, policy=policy, now_utc=now_utc)

    def _reconcile_protection(
        self,
        *,
        cycle: V4GmoStoredCycle,
        policy: V4GmoExecutionPolicy,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        snapshot = self._read_snapshot_or_none()
        if snapshot is None or not snapshot.fresh or not snapshot.result_known:
            return self._halt(
                cycle=cycle,
                reason="PROTECTION_RECONCILIATION_UNKNOWN",
                now_utc=now_utc,
            )
        if (
            snapshot.position_count == 0
            and snapshot.pending_entry_size == 0
            and snapshot.protection_size == 0
            and snapshot.protection_status is V4GmoProtectionStatus.NONE
        ):
            flat = self.store.transition(
                cycle_ref=cycle.cycle_ref,
                target=V4GmoCycleState.FLAT_RECONCILED,
                event_category="POSITION_ALREADY_FLAT",
                now_utc=now_utc,
                filled_size=0,
                protected_size=0,
            )
            return self._result(
                status=V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC,
                cycle=flat,
            )
        if snapshot.position_count == 0:
            if snapshot.protection_size > 0:
                cycle = self.store.transition(
                    cycle_ref=cycle.cycle_ref,
                    target=V4GmoCycleState.PROTECTION_CANCEL_INTENT_PERSISTED,
                    event_category="ORPHAN_PROTECTION_CANCEL_INTENT_PERSISTED",
                    now_utc=now_utc,
                    protected_size=snapshot.protection_size,
                )
                return self._attempt_cancel_protection(
                    cycle=cycle,
                    policy=policy,
                    protection_size=snapshot.protection_size,
                    now_utc=now_utc,
                )
            return self._halt(
                cycle=cycle,
                reason="FLAT_WITH_UNKNOWN_PROTECTION_STATE",
                now_utc=now_utc,
            )
        if snapshot.position_count > 1:
            return self._halt(
                cycle=cycle,
                reason="MULTIPLE_POSITIONS_DETECTED_DURING_PROTECTION",
                now_utc=now_utc,
            )
        if snapshot.position_side is not SignalDecision(cycle.side):
            return self._halt(
                cycle=cycle,
                reason="POSITION_SIDE_MISMATCH_DURING_PROTECTION",
                now_utc=now_utc,
            )
        exact = (
            snapshot.position_count == 1
            and snapshot.position_side is SignalDecision(cycle.side)
            and snapshot.filled_size == cycle.filled_size
            and snapshot.pending_entry_size == 0
            and snapshot.protection_status is V4GmoProtectionStatus.EXACT_MATCH
            and snapshot.protection_size == cycle.filled_size
        )
        if exact:
            confirmation_time = self._now(now_utc)
            if cycle.unprotected_since_utc is None:
                return self._halt(
                    cycle=cycle,
                    reason="UNPROTECTED_START_TIME_MISSING_AT_CONFIRMATION",
                    now_utc=confirmation_time,
                )
            unprotected_since = datetime.fromisoformat(cycle.unprotected_since_utc)
            elapsed = (confirmation_time - unprotected_since).total_seconds()
            if elapsed < 0:
                return self._halt(
                    cycle=cycle,
                    reason="CLOCK_MOVED_BACKWARD_AT_PROTECTION_CONFIRMATION",
                    now_utc=confirmation_time,
                )
            if elapsed > policy.max_unprotected_seconds:
                # Exact protection now exists, so do not cancel it or send a
                # blind close.  The deadline proof failed and the cycle must
                # remain latched for operator review.
                return self._halt(
                    cycle=cycle,
                    reason="PROTECTION_CONFIRMED_AFTER_DEADLINE",
                    now_utc=confirmation_time,
                )
            protected = self.store.transition(
                cycle_ref=cycle.cycle_ref,
                target=V4GmoCycleState.POSITION_PROTECTED,
                event_category="EXACT_SIZE_PROTECTION_CONFIRMED",
                now_utc=confirmation_time,
                filled_size=snapshot.filled_size,
                protected_size=snapshot.protection_size,
            )
            return self._result(
                status=V4GmoCycleStatus.POSITION_PROTECTED_SYNTHETIC,
                cycle=protected,
            )
        if (
            snapshot.protection_size > 0
            or snapshot.protection_status
            in (
                V4GmoProtectionStatus.UNDERSIZED,
                V4GmoProtectionStatus.OVERSIZED,
                V4GmoProtectionStatus.EXACT_MATCH,
            )
        ):
            cycle = self.store.transition(
                cycle_ref=cycle.cycle_ref,
                target=V4GmoCycleState.PROTECTION_CANCEL_INTENT_PERSISTED,
                event_category="MISMATCHED_PROTECTION_CANCEL_INTENT_PERSISTED",
                now_utc=now_utc,
                protected_size=snapshot.protection_size,
            )
            return self._attempt_cancel_protection(
                cycle=cycle,
                policy=policy,
                protection_size=snapshot.protection_size,
                now_utc=now_utc,
            )
        return self._start_emergency_exit(
            cycle=cycle,
            policy=policy,
            reason="PROTECTION_NOT_EXACT",
            now_utc=now_utc,
        )

    def _attempt_cancel_protection(
        self,
        *,
        cycle: V4GmoStoredCycle,
        policy: V4GmoExecutionPolicy,
        protection_size: int,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        if protection_size <= 0:
            return self._halt(
                cycle=cycle,
                reason="MISMATCHED_PROTECTION_SIZE_UNKNOWN",
                now_utc=now_utc,
            )
        plan = build_v4_action_plan(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.CANCEL_MISMATCHED_PROTECTION,
            side=SignalDecision(cycle.side),
            requested_size=protection_size,
            protection_contract_hash=policy.protection_contract_hash,
        )
        cycle = self.store.record_action_attempt(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.CANCEL_MISMATCHED_PROTECTION,
            target=V4GmoCycleState.PROTECTION_CANCEL_ATTEMPTED,
            now_utc=now_utc,
        )
        try:
            outcome = self.broker.perform_once_synthetic(plan=plan)
        except V4GmoBoundaryError:
            return self._halt(
                cycle=cycle,
                reason="PROTECTION_CANCEL_BOUNDARY_REFUSED",
                now_utc=now_utc,
            )
        self.store.record_action_outcome(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.CANCEL_MISMATCHED_PROTECTION,
            outcome_safe_label=outcome.value,
        )
        cycle = self.store.transition(
            cycle_ref=cycle.cycle_ref,
            target=V4GmoCycleState.PROTECTION_CANCEL_RECONCILING,
            event_category="PROTECTION_CANCEL_RECONCILING",
            now_utc=now_utc,
        )
        return self._reconcile_cancelled_protection(
            cycle=cycle, policy=policy, now_utc=now_utc
        )

    def _reconcile_cancelled_protection(
        self,
        *,
        cycle: V4GmoStoredCycle,
        policy: V4GmoExecutionPolicy,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        snapshot = self._read_snapshot_or_none()
        if snapshot is None or not snapshot.fresh or not snapshot.result_known:
            return self._halt(
                cycle=cycle,
                reason="PROTECTION_CANCEL_RECONCILIATION_UNKNOWN",
                now_utc=now_utc,
            )
        if (
            snapshot.position_count == 0
            and snapshot.pending_entry_size == 0
            and snapshot.protection_size == 0
            and snapshot.protection_status is V4GmoProtectionStatus.NONE
        ):
            flat = self.store.transition(
                cycle_ref=cycle.cycle_ref,
                target=V4GmoCycleState.FLAT_RECONCILED,
                event_category="PROTECTION_CANCEL_FOUND_FLAT",
                now_utc=now_utc,
                filled_size=0,
                protected_size=0,
            )
            return self._result(
                status=V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC,
                cycle=flat,
            )
        cancellation_confirmed = (
            snapshot.position_count == 1
            and snapshot.position_side is SignalDecision(cycle.side)
            and snapshot.filled_size == cycle.filled_size
            and snapshot.pending_entry_size == 0
            and snapshot.protection_size == 0
            and snapshot.protection_status is V4GmoProtectionStatus.NONE
        )
        if not cancellation_confirmed:
            return self._halt(
                cycle=cycle,
                reason="MISMATCHED_PROTECTION_PERSISTS_AFTER_CANCEL",
                now_utc=now_utc,
            )
        return self._start_emergency_exit(
            cycle=cycle,
            policy=policy,
            reason="MISMATCHED_PROTECTION_REMOVED_EXIT_REQUIRED",
            now_utc=now_utc,
        )

    def _start_emergency_exit(
        self,
        *,
        cycle: V4GmoStoredCycle,
        policy: V4GmoExecutionPolicy,
        reason: str,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        cycle = self.store.transition(
            cycle_ref=cycle.cycle_ref,
            target=V4GmoCycleState.EMERGENCY_EXIT_INTENT_PERSISTED,
            event_category=reason,
            now_utc=now_utc,
        )
        return self._attempt_emergency_exit(cycle=cycle, policy=policy, now_utc=now_utc)

    def _attempt_emergency_exit(
        self,
        *,
        cycle: V4GmoStoredCycle,
        policy: V4GmoExecutionPolicy,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        size = cycle.filled_size
        if size <= 0:
            return self._halt(
                cycle=cycle,
                reason="EMERGENCY_EXIT_SIZE_UNKNOWN",
                now_utc=now_utc,
            )
        plan = build_v4_action_plan(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
            side=SignalDecision(cycle.side),
            requested_size=size,
            protection_contract_hash=policy.protection_contract_hash,
        )
        cycle = self.store.record_action_attempt(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
            target=V4GmoCycleState.EMERGENCY_EXIT_ATTEMPTED,
            now_utc=now_utc,
        )
        try:
            outcome = self.broker.perform_once_synthetic(plan=plan)
        except V4GmoBoundaryError:
            return self._halt(
                cycle=cycle,
                reason="EMERGENCY_EXIT_BOUNDARY_REFUSED",
                now_utc=now_utc,
            )
        self.store.record_action_outcome(
            cycle_ref=cycle.cycle_ref,
            action=V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
            outcome_safe_label=outcome.value,
        )
        return self._reconcile_emergency_exit(cycle=cycle, now_utc=now_utc)

    def _reconcile_emergency_exit(
        self,
        *,
        cycle: V4GmoStoredCycle,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        snapshot = self._read_snapshot_or_none()
        if (
            snapshot is not None
            and snapshot.fresh
            and snapshot.result_known
            and snapshot.position_count == 0
            and snapshot.pending_entry_size == 0
            and snapshot.protection_size == 0
            and snapshot.protection_status is V4GmoProtectionStatus.NONE
        ):
            flat = self.store.transition(
                cycle_ref=cycle.cycle_ref,
                target=V4GmoCycleState.FLAT_RECONCILED,
                event_category="EMERGENCY_EXIT_FLAT_CONFIRMED",
                now_utc=now_utc,
                filled_size=0,
                protected_size=0,
            )
            return self._result(
                status=V4GmoCycleStatus.FLAT_RECONCILED_SYNTHETIC,
                cycle=flat,
            )
        return self._halt(
            cycle=cycle,
            reason="EMERGENCY_EXIT_RESULT_UNKNOWN_OR_NOT_FLAT",
            now_utc=now_utc,
        )

    @staticmethod
    def _entry_snapshot_invalid_reason(
        *, snapshot: V4GmoBrokerSnapshot, cycle: V4GmoStoredCycle
    ) -> str | None:
        if snapshot.position_count > 1:
            return "MULTIPLE_POSITIONS_DETECTED"
        if (
            snapshot.protection_size > 0
            or snapshot.protection_status is not V4GmoProtectionStatus.NONE
        ):
            return "UNEXPECTED_PROTECTION_DURING_ENTRY_RECONCILIATION"
        if snapshot.filled_size > cycle.requested_size:
            return "FILLED_SIZE_EXCEEDS_INTENT"
        if snapshot.pending_entry_size > cycle.requested_size:
            return "PENDING_SIZE_EXCEEDS_INTENT"
        if snapshot.filled_size + snapshot.pending_entry_size > cycle.requested_size:
            return "ENTRY_TOTAL_SIZE_EXCEEDS_INTENT"
        if snapshot.position_count == 1:
            if snapshot.position_side is not SignalDecision(cycle.side):
                return "POSITION_SIDE_MISMATCH"
            if snapshot.filled_size <= 0:
                return "POSITION_WITHOUT_RECONCILED_FILL"
        elif snapshot.filled_size > 0:
            return "FILL_WITHOUT_POSITION"
        return None

    def _read_snapshot_or_none(self) -> V4GmoBrokerSnapshot | None:
        try:
            return self.broker.reconcile_synthetic()
        except V4GmoBoundaryError:
            return None

    def _now(self, fallback: datetime) -> datetime:
        value = fallback if self.clock is None else self.clock.now_utc()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise V4GmoBoundaryError("V4_GMO_CLOCK_INVALID")
        return value

    def _halt(
        self,
        *,
        cycle: V4GmoStoredCycle,
        reason: str,
        now_utc: datetime,
    ) -> V4GmoCycleResult:
        halted = self.store.transition(
            cycle_ref=cycle.cycle_ref,
            target=V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
            event_category="HALTED_OPERATOR_REVIEW_REQUIRED",
            now_utc=now_utc,
            halt_reason=reason,
        )
        return self._result(
            status=V4GmoCycleStatus.HALTED_OPERATOR_REVIEW_REQUIRED,
            cycle=halted,
            reasons=(reason,),
        )

    def _result(
        self,
        *,
        status: V4GmoCycleStatus,
        cycle: V4GmoStoredCycle,
        reasons: tuple[str, ...] = (),
    ) -> V4GmoCycleResult:
        attempted = {
            action: int(
                self.store.action_attempted(cycle_ref=cycle.cycle_ref, action=action)
            )
            for action in V4GmoAction
        }
        return V4GmoCycleResult(
            status=status,
            final_state=cycle.state,
            cycle_ref=cycle.cycle_ref,
            blocked_reasons=reasons,
            action_attempt_count=sum(attempted.values()),
            market_entry_attempt_count=attempted[V4GmoAction.MARKET_ENTRY],
            cancel_attempt_count=attempted[V4GmoAction.CANCEL_ENTRY_REMAINDER],
            protection_attempt_count=attempted[V4GmoAction.EXACT_SIZE_OCO_PROTECTION],
            protection_cancel_attempt_count=attempted[
                V4GmoAction.CANCEL_MISMATCHED_PROTECTION
            ],
            emergency_exit_attempt_count=attempted[
                V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT
            ],
            filled_size=cycle.filled_size,
            protected_size=cycle.protected_size,
            actual_post_count=self.broker.actual_post_count,
            broker_write_performed=self.broker.broker_write_performed,
            credential_read_performed=self.broker.credential_read_performed,
            network_access_performed=self.broker.network_access_performed,
        )

    @staticmethod
    def _empty_result(
        *,
        status: V4GmoCycleStatus,
        reasons: tuple[str, ...] = (),
    ) -> V4GmoCycleResult:
        return V4GmoCycleResult(
            status=status,
            final_state=None,
            cycle_ref=None,
            blocked_reasons=reasons,
            action_attempt_count=0,
            market_entry_attempt_count=0,
            cancel_attempt_count=0,
            protection_attempt_count=0,
            protection_cancel_attempt_count=0,
            emergency_exit_attempt_count=0,
            filled_size=0,
            protected_size=0,
        )


def _flat_snapshot_blocked_reasons(
    snapshot: V4GmoBrokerSnapshot,
) -> tuple[str, ...]:
    checks = (
        (snapshot.fresh, "BROKER_SNAPSHOT_STALE"),
        (snapshot.result_known, "BROKER_RESULT_UNKNOWN"),
        (snapshot.position_count == 0, "POSITION_NOT_FLAT"),
        (snapshot.filled_size == 0, "FILL_STATE_NOT_FLAT"),
        (snapshot.pending_entry_size == 0, "PENDING_ENTRY_EXISTS"),
        (snapshot.protection_size == 0, "PROTECTION_ORDER_EXISTS"),
        (
            snapshot.protection_status is V4GmoProtectionStatus.NONE,
            "PROTECTION_STATE_NOT_CLEAR",
        ),
    )
    return tuple(reason for passed, reason in checks if not passed)
