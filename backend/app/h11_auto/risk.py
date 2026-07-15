"""No-POST risk and readiness reviews for H-11 automatic Phase A."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.h11_auto.contracts import FormalSignal, PhaseAExecutionPolicy, SignalDecision


class H11AutoRiskError(ValueError):
    """Invalid broker-independent safety input."""


@dataclass(frozen=True)
class PhaseASafetySnapshot:
    boot_reconciled: bool = False
    process_lock_held: bool = False
    data_fresh: bool = False
    clock_synchronized: bool = False
    notification_path_ready: bool = False
    local_position_count: int = 0
    active_intent_count: int = 0
    entries_today: int = 0
    external_or_manual_position_detected: bool = False
    active_or_pending_order_conflict: bool = False
    kill_requested: bool = False

    def __post_init__(self) -> None:
        boolean_values = (
            self.boot_reconciled,
            self.process_lock_held,
            self.data_fresh,
            self.clock_synchronized,
            self.notification_path_ready,
            self.external_or_manual_position_detected,
            self.active_or_pending_order_conflict,
            self.kill_requested,
        )
        count_values = (
            self.local_position_count,
            self.active_intent_count,
            self.entries_today,
        )
        if any(type(value) is not bool for value in boolean_values) or any(
            type(value) is not int or value < 0 for value in count_values
        ):
            raise H11AutoRiskError("safety snapshot is invalid")


@dataclass(frozen=True)
class PhaseAEntryGateResult:
    fake_cycle_allowed: bool
    blocked_reasons: tuple[str, ...]
    actual_post_allowed: bool = False
    broker_write_allowed: bool = False

    def __bool__(self) -> bool:
        return False


def evaluate_phase_a_entry_gate(
    *,
    signal: FormalSignal,
    policy: PhaseAExecutionPolicy,
    snapshot: PhaseASafetySnapshot,
    now_utc: datetime,
) -> PhaseAEntryGateResult:
    reasons: list[str] = []
    if not policy.accepts(signal):
        reasons.append("SIGNAL_POLICY_MISMATCH")
    if signal.decision is SignalDecision.STAY:
        reasons.append("STAY_HAS_NO_ENTRY")
    if (
        not isinstance(now_utc, datetime)
        or now_utc.tzinfo is None
        or now_utc >= signal.valid_until_utc
    ):
        reasons.append("SIGNAL_EXPIRED_OR_CLOCK_INVALID")
    if not snapshot.boot_reconciled:
        reasons.append("BOOT_NOT_RECONCILED")
    if not snapshot.process_lock_held:
        reasons.append("PROCESS_LOCK_NOT_HELD")
    if not snapshot.data_fresh:
        reasons.append("DATA_NOT_FRESH")
    if not snapshot.clock_synchronized:
        reasons.append("CLOCK_NOT_SYNCHRONIZED")
    if not snapshot.notification_path_ready:
        reasons.append("NOTIFICATION_PATH_NOT_READY")
    if snapshot.local_position_count != 0:
        reasons.append("LOCAL_POSITION_NOT_FLAT")
    if snapshot.active_intent_count != 0:
        reasons.append("ACTIVE_INTENT_EXISTS")
    if snapshot.entries_today >= policy.max_entries_per_day:
        reasons.append("MAX_ENTRIES_PER_DAY_REACHED")
    if snapshot.external_or_manual_position_detected:
        reasons.append("EXTERNAL_OR_MANUAL_POSITION_DETECTED")
    if snapshot.active_or_pending_order_conflict:
        reasons.append("ACTIVE_OR_PENDING_ORDER_CONFLICT")
    if snapshot.kill_requested:
        reasons.append("KILL_REQUESTED")
    return PhaseAEntryGateResult(
        fake_cycle_allowed=not reasons,
        blocked_reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class ActualReadinessReview:
    structurally_ready_for_later_adapter_review: bool
    blocked_reasons: tuple[str, ...]
    actual_transport_present: bool = False
    actual_post_allowed: bool = False
    broker_write_allowed: bool = False
    credential_read_allowed: bool = False

    def __bool__(self) -> bool:
        return False


def review_actual_readiness(
    *,
    broker_native_atomic_protection_confirmed: bool = False,
    short_pending_expiry_confirmed: bool = False,
    partial_fill_size_safety_confirmed: bool = False,
    dedicated_account_confirmed: bool = False,
    operator_risk_limits_frozen: bool = False,
    always_on_host_confirmed: bool = False,
) -> ActualReadinessReview:
    checks = {
        "BROKER_NATIVE_ATOMIC_PROTECTION_NOT_CONFIRMED": (
            broker_native_atomic_protection_confirmed
        ),
        "SHORT_PENDING_EXPIRY_NOT_CONFIRMED": short_pending_expiry_confirmed,
        "PARTIAL_FILL_SIZE_SAFETY_NOT_CONFIRMED": partial_fill_size_safety_confirmed,
        "DEDICATED_ACCOUNT_NOT_CONFIRMED": dedicated_account_confirmed,
        "OPERATOR_RISK_LIMITS_NOT_FROZEN": operator_risk_limits_frozen,
        "ALWAYS_ON_HOST_NOT_CONFIRMED": always_on_host_confirmed,
    }
    blocked = tuple(reason for reason, passed in checks.items() if passed is not True)
    return ActualReadinessReview(
        structurally_ready_for_later_adapter_review=not blocked,
        blocked_reasons=blocked,
    )
