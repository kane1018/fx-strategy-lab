"""Frozen contracts for the relaxed GMO execution profile (fake-only/no-POST).

This profile is intentionally separate from the strict Phase A contract.  It
accepts a short, explicitly bounded interval between a market fill and the
confirmation of an exact-size server-side OCO protection order.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo

from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.v4_gmo_evidence import H11_V4_GMO_CAPABILITY_EVIDENCE_HASH
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH

V4_GMO_PROFILE_VERSION = "H11_V4_GMO_MARKET_THEN_EXACT_OCO_NO_POST_V1"
V4_GMO_EXIT_PROFILE = "H11_V4_EXACT_OCO_POSITION_SPECIFIC_23H_EXIT_V1"
V4_GMO_BLOCKED_HOURS_JST = (5, 6, 7, 8)
V4_GMO_FRIDAY_ENTRY_CUTOFF_HOUR_JST = 0
V4_GMO_WEEKEND_DAYS_JST = (5, 6)
V4_GMO_MAXIMUM_HOLD_SECONDS = 82_800


class V4GmoContractError(ValueError):
    """Raised when a value violates the frozen v4 GMO contract."""


class V4GmoAction(str, Enum):
    MARKET_ENTRY = "MARKET_ENTRY"
    CANCEL_ENTRY_REMAINDER = "CANCEL_ENTRY_REMAINDER"
    EXACT_SIZE_OCO_PROTECTION = "EXACT_SIZE_OCO_PROTECTION"
    CANCEL_MISMATCHED_PROTECTION = "CANCEL_MISMATCHED_PROTECTION"
    CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT = "CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT"
    POSITION_SPECIFIC_EMERGENCY_EXIT = "POSITION_SPECIFIC_EMERGENCY_EXIT"
    POSITION_SPECIFIC_TIME_EXIT = "POSITION_SPECIFIC_TIME_EXIT"


class V4GmoCycleState(str, Enum):
    ENTRY_INTENT_PERSISTED = "ENTRY_INTENT_PERSISTED"
    MARKET_ENTRY_ATTEMPTED = "MARKET_ENTRY_ATTEMPTED"
    ENTRY_RECONCILING = "ENTRY_RECONCILING"
    REMAINDER_CANCEL_ATTEMPTED = "REMAINDER_CANCEL_ATTEMPTED"
    ENTRY_FILLED_UNPROTECTED = "ENTRY_FILLED_UNPROTECTED"
    PROTECTION_INTENT_PERSISTED = "PROTECTION_INTENT_PERSISTED"
    PROTECTION_ATTEMPTED = "PROTECTION_ATTEMPTED"
    PROTECTION_RECONCILING = "PROTECTION_RECONCILING"
    POSITION_PROTECTED = "POSITION_PROTECTED"
    PROTECTION_CANCEL_INTENT_PERSISTED = "PROTECTION_CANCEL_INTENT_PERSISTED"
    PROTECTION_CANCEL_ATTEMPTED = "PROTECTION_CANCEL_ATTEMPTED"
    PROTECTION_CANCEL_RECONCILING = "PROTECTION_CANCEL_RECONCILING"
    EMERGENCY_EXIT_INTENT_PERSISTED = "EMERGENCY_EXIT_INTENT_PERSISTED"
    EMERGENCY_EXIT_ATTEMPTED = "EMERGENCY_EXIT_ATTEMPTED"
    FLAT_RECONCILED = "FLAT_RECONCILED"
    HALTED_OPERATOR_REVIEW_REQUIRED = "HALTED_OPERATOR_REVIEW_REQUIRED"
    OPERATOR_RELOAD_CLEARED = "OPERATOR_RELOAD_CLEARED"


class V4GmoEntryStatus(str, Enum):
    NONE = "NONE"
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class V4GmoProtectionStatus(str, Enum):
    NONE = "NONE"
    EXACT_MATCH = "EXACT_MATCH"
    UNDERSIZED = "UNDERSIZED"
    OVERSIZED = "OVERSIZED"
    UNKNOWN = "UNKNOWN"


class V4GmoSyntheticOutcome(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class V4GmoExecutionPolicy:
    """Immutable relaxed profile selected specifically for GMO FX."""

    strategy_version: str
    signal_config_hash: str
    selected_horizon: FormalHorizon
    protection_contract_hash: str
    broker_capability_evidence_hash: str = H11_V4_GMO_CAPABILITY_EVIDENCE_HASH
    requested_size: int = 10_000
    max_unprotected_seconds: int = 15
    max_positions: int = 1
    max_entries_per_day: int = 1
    max_loss_per_trade_yen: int = 5_000
    max_loss_per_day_yen: int = 10_000
    max_loss_per_month_yen: int = 50_000
    max_consecutive_losses: int = 5
    blocked_hours_jst: tuple[int, ...] = V4_GMO_BLOCKED_HOURS_JST
    friday_entry_cutoff_hour_jst: int = V4_GMO_FRIDAY_ENTRY_CUTOFF_HOUR_JST
    weekend_days_jst: tuple[int, ...] = V4_GMO_WEEKEND_DAYS_JST
    maximum_hold_seconds: int = V4_GMO_MAXIMUM_HOLD_SECONDS
    exit_profile_label: str = V4_GMO_EXIT_PROFILE
    scale_in_allowed: bool = False
    hedging_allowed: bool = False
    generic_opposite_close_allowed: bool = False
    same_action_retry_allowed: bool = False
    same_action_repost_allowed: bool = False
    temporary_unprotected_gap_accepted: bool = True
    broker_native_atomic_protection_required: bool = False

    def __post_init__(self) -> None:
        required_labels = (
            self.strategy_version,
            self.signal_config_hash,
            self.protection_contract_hash,
        )
        if any(not isinstance(value, str) or not value.strip() for value in required_labels):
            raise V4GmoContractError("v4 policy labels and hashes are required")
        if self.protection_contract_hash != H11_V4_GMO_PROTECTION_CONTRACT_HASH:
            raise V4GmoContractError("v4 protection contract hash is not frozen")
        if self.broker_capability_evidence_hash != H11_V4_GMO_CAPABILITY_EVIDENCE_HASH:
            raise V4GmoContractError("v4 broker capability evidence hash is not frozen")
        if not isinstance(self.selected_horizon, FormalHorizon):
            raise V4GmoContractError("v4 policy horizon is invalid")
        immutable_requirements = (
            type(self.requested_size) is int and self.requested_size == 10_000,
            type(self.max_unprotected_seconds) is int
            and self.max_unprotected_seconds == 15,
            type(self.max_positions) is int and self.max_positions == 1,
            type(self.max_entries_per_day) is int and self.max_entries_per_day == 1,
            type(self.max_loss_per_trade_yen) is int
            and self.max_loss_per_trade_yen == 5_000,
            type(self.max_loss_per_day_yen) is int and self.max_loss_per_day_yen == 10_000,
            type(self.max_loss_per_month_yen) is int
            and self.max_loss_per_month_yen == 50_000,
            type(self.max_consecutive_losses) is int
            and self.max_consecutive_losses == 5,
            self.blocked_hours_jst == V4_GMO_BLOCKED_HOURS_JST,
            type(self.friday_entry_cutoff_hour_jst) is int
            and self.friday_entry_cutoff_hour_jst
            == V4_GMO_FRIDAY_ENTRY_CUTOFF_HOUR_JST,
            self.weekend_days_jst == V4_GMO_WEEKEND_DAYS_JST,
            type(self.maximum_hold_seconds) is int
            and self.maximum_hold_seconds == V4_GMO_MAXIMUM_HOLD_SECONDS,
            self.exit_profile_label == V4_GMO_EXIT_PROFILE,
            type(self.scale_in_allowed) is bool and not self.scale_in_allowed,
            type(self.hedging_allowed) is bool and not self.hedging_allowed,
            type(self.generic_opposite_close_allowed) is bool
            and not self.generic_opposite_close_allowed,
            type(self.same_action_retry_allowed) is bool
            and not self.same_action_retry_allowed,
            type(self.same_action_repost_allowed) is bool
            and not self.same_action_repost_allowed,
            type(self.temporary_unprotected_gap_accepted) is bool
            and self.temporary_unprotected_gap_accepted,
            type(self.broker_native_atomic_protection_required) is bool
            and not self.broker_native_atomic_protection_required,
        )
        if not all(immutable_requirements):
            raise V4GmoContractError("frozen v4 GMO invariants cannot be changed")

    @property
    def config_hash(self) -> str:
        canonical = json.dumps(
            {
                "broker_native_atomic_protection_required": False,
                "broker_capability_evidence_hash": self.broker_capability_evidence_hash,
                "blocked_hours_jst": list(self.blocked_hours_jst),
                "exit_profile_label": self.exit_profile_label,
                "friday_entry_cutoff_hour_jst": self.friday_entry_cutoff_hour_jst,
                "generic_opposite_close_allowed": False,
                "hedging_allowed": False,
                "max_consecutive_losses": 5,
                "max_entries_per_day": 1,
                "max_loss_per_day_yen": 10_000,
                "max_loss_per_month_yen": 50_000,
                "max_loss_per_trade_yen": 5_000,
                "max_positions": 1,
                "max_unprotected_seconds": 15,
                "maximum_hold_seconds": self.maximum_hold_seconds,
                "profile_version": V4_GMO_PROFILE_VERSION,
                "protection_contract_hash": self.protection_contract_hash,
                "requested_size": 10_000,
                "same_action_repost_allowed": False,
                "same_action_retry_allowed": False,
                "scale_in_allowed": False,
                "selected_horizon": self.selected_horizon.value,
                "signal_config_hash": self.signal_config_hash,
                "strategy_version": self.strategy_version,
                "temporary_unprotected_gap_accepted": True,
                "weekend_days_jst": list(self.weekend_days_jst),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    def accepts(self, signal: FormalSignal) -> bool:
        return (
            signal.strategy_version == self.strategy_version
            and signal.signal_config_hash == self.signal_config_hash
            and signal.horizon is self.selected_horizon
            and signal.decision in (SignalDecision.BUY, SignalDecision.SELL)
        )

    def entry_time_allowed(self, *, now_utc: datetime) -> bool:
        if now_utc.tzinfo is None:
            return False
        now_jst = now_utc.astimezone(ZoneInfo("Asia/Tokyo"))
        return not (
            now_jst.weekday() in self.weekend_days_jst
            or now_jst.hour in self.blocked_hours_jst
            or (
                now_jst.weekday() == 4
                and now_jst.hour >= self.friday_entry_cutoff_hour_jst
            )
        )


@dataclass(frozen=True)
class V4GmoPreflightSnapshot:
    boot_reconciled: bool
    process_lock_held: bool
    data_fresh: bool
    clock_synchronized: bool
    notification_path_ready: bool
    broker_snapshot_fresh: bool
    position_count: int = 0
    active_order_count: int = 0
    entries_today: int = 0
    daily_stop_clear: bool = True
    monthly_stop_clear: bool = True
    consecutive_loss_stop_clear: bool = True
    operator_halt_clear: bool = True

    def __post_init__(self) -> None:
        boolean_values = (
            self.boot_reconciled,
            self.process_lock_held,
            self.data_fresh,
            self.clock_synchronized,
            self.notification_path_ready,
            self.broker_snapshot_fresh,
            self.daily_stop_clear,
            self.monthly_stop_clear,
            self.consecutive_loss_stop_clear,
            self.operator_halt_clear,
        )
        if any(type(value) is not bool for value in boolean_values):
            raise V4GmoContractError("v4 preflight flags must be strict booleans")
        count_values = (
            self.position_count,
            self.active_order_count,
            self.entries_today,
        )
        if any(type(value) is not int or value < 0 for value in count_values):
            raise V4GmoContractError("v4 preflight counts must be non-negative integers")

    def blocked_reasons(self) -> tuple[str, ...]:
        checks = (
            (self.boot_reconciled, "BOOT_RECONCILIATION_REQUIRED"),
            (self.process_lock_held, "PROCESS_LOCK_REQUIRED"),
            (self.data_fresh, "DATA_STALE"),
            (self.clock_synchronized, "CLOCK_NOT_SYNCHRONIZED"),
            (self.notification_path_ready, "NOTIFICATION_PATH_NOT_READY"),
            (self.broker_snapshot_fresh, "BROKER_SNAPSHOT_STALE"),
            (self.position_count == 0, "POSITION_NOT_FLAT"),
            (self.active_order_count == 0, "ACTIVE_ORDER_EXISTS"),
            (self.entries_today == 0, "DAILY_ENTRY_LIMIT_REACHED"),
            (self.daily_stop_clear, "DAILY_STOP_LATCHED"),
            (self.monthly_stop_clear, "MONTHLY_STOP_LATCHED"),
            (self.consecutive_loss_stop_clear, "CONSECUTIVE_LOSS_STOP_LATCHED"),
            (self.operator_halt_clear, "OPERATOR_HALT_LATCHED"),
        )
        return tuple(reason for passed, reason in checks if not passed)


@dataclass(frozen=True)
class V4GmoBrokerSnapshot:
    """Sanitized authoritative observation; contains no broker identifiers."""

    fresh: bool
    result_known: bool
    position_count: int
    position_side: SignalDecision | None
    filled_size: int
    pending_entry_size: int
    protection_size: int
    entry_status: V4GmoEntryStatus
    protection_status: V4GmoProtectionStatus

    def __post_init__(self) -> None:
        if type(self.fresh) is not bool or type(self.result_known) is not bool:
            raise V4GmoContractError("sanitized broker flags must be strict booleans")
        if self.position_side not in (None, SignalDecision.BUY, SignalDecision.SELL):
            raise V4GmoContractError("sanitized position side is invalid")
        integer_values = (
            self.position_count,
            self.filled_size,
            self.pending_entry_size,
            self.protection_size,
        )
        if any(type(value) is not int or value < 0 for value in integer_values):
            raise V4GmoContractError("sanitized broker counts must be non-negative integers")

    @classmethod
    def flat(cls) -> V4GmoBrokerSnapshot:
        return cls(
            fresh=True,
            result_known=True,
            position_count=0,
            position_side=None,
            filled_size=0,
            pending_entry_size=0,
            protection_size=0,
            entry_status=V4GmoEntryStatus.NONE,
            protection_status=V4GmoProtectionStatus.NONE,
        )


@dataclass(frozen=True)
class V4GmoActionPlan:
    """Pure, sanitized action plan.  It cannot authorize or perform transport."""

    cycle_ref: str
    action: V4GmoAction
    side: SignalDecision
    requested_size: int
    protection_contract_hash: str | None
    route_safe_label: str
    actual_post_allowed: bool = False
    credential_read_allowed: bool = False
    network_access_allowed: bool = False

    def __post_init__(self) -> None:
        if len(self.cycle_ref) != 64 or any(
            character not in "0123456789abcdef" for character in self.cycle_ref
        ):
            raise V4GmoContractError("cycle_ref must be a sanitized SHA-256 value")
        if self.side not in (SignalDecision.BUY, SignalDecision.SELL):
            raise V4GmoContractError("v4 action side must be BUY or SELL")
        if type(self.requested_size) is not int or self.requested_size <= 0:
            raise V4GmoContractError("v4 action size must be positive")
        if not self.route_safe_label or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_" for character in self.route_safe_label
        ):
            raise V4GmoContractError("route_safe_label is invalid")
        disabled = (
            type(self.actual_post_allowed) is bool and not self.actual_post_allowed,
            type(self.credential_read_allowed) is bool and not self.credential_read_allowed,
            type(self.network_access_allowed) is bool and not self.network_access_allowed,
        )
        if not all(disabled):
            raise V4GmoContractError("v4 no-POST action plan cannot enable transport")
        if self.action is V4GmoAction.EXACT_SIZE_OCO_PROTECTION:
            if not self.protection_contract_hash:
                raise V4GmoContractError("protection action requires a frozen contract hash")
        elif self.protection_contract_hash is not None:
            raise V4GmoContractError("only protection actions may carry a protection hash")


def build_v4_cycle_ref(*, signal: FormalSignal, policy: V4GmoExecutionPolicy) -> str:
    if not policy.accepts(signal):
        raise V4GmoContractError("signal does not match the frozen v4 GMO policy")
    canonical = "|".join(
        (
            V4_GMO_PROFILE_VERSION,
            policy.config_hash,
            signal.fingerprint,
            signal.decision.value,
        )
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_v4_action_plan(
    *,
    cycle_ref: str,
    action: V4GmoAction,
    side: SignalDecision,
    requested_size: int,
    protection_contract_hash: str,
) -> V4GmoActionPlan:
    route_labels = {
        V4GmoAction.MARKET_ENTRY: "GMO_MARKET_ENTRY",
        V4GmoAction.CANCEL_ENTRY_REMAINDER: "GMO_CANCEL_ENTRY_REMAINDER",
        V4GmoAction.EXACT_SIZE_OCO_PROTECTION: "GMO_EXACT_SIZE_OCO_PROTECTION",
        V4GmoAction.CANCEL_MISMATCHED_PROTECTION: "GMO_CANCEL_MISMATCHED_PROTECTION",
        V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT: (
            "GMO_CANCEL_PROTECTION_FOR_TIME_EXIT"
        ),
        V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT: "GMO_POSITION_SPECIFIC_EXIT",
        V4GmoAction.POSITION_SPECIFIC_TIME_EXIT: "GMO_POSITION_SPECIFIC_TIME_EXIT",
    }
    return V4GmoActionPlan(
        cycle_ref=cycle_ref,
        action=action,
        side=side,
        requested_size=requested_size,
        protection_contract_hash=(
            protection_contract_hash
            if action is V4GmoAction.EXACT_SIZE_OCO_PROTECTION
            else None
        ),
        route_safe_label=route_labels[action],
    )


def require_v4_transition(
    *, current: V4GmoCycleState, target: V4GmoCycleState
) -> None:
    allowed = {
        V4GmoCycleState.ENTRY_INTENT_PERSISTED: {
            V4GmoCycleState.MARKET_ENTRY_ATTEMPTED,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.MARKET_ENTRY_ATTEMPTED: {
            V4GmoCycleState.ENTRY_RECONCILING,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.ENTRY_RECONCILING: {
            V4GmoCycleState.REMAINDER_CANCEL_ATTEMPTED,
            V4GmoCycleState.ENTRY_FILLED_UNPROTECTED,
            V4GmoCycleState.FLAT_RECONCILED,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.REMAINDER_CANCEL_ATTEMPTED: {
            V4GmoCycleState.ENTRY_RECONCILING,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.ENTRY_FILLED_UNPROTECTED: {
            V4GmoCycleState.PROTECTION_INTENT_PERSISTED,
            V4GmoCycleState.EMERGENCY_EXIT_INTENT_PERSISTED,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.PROTECTION_INTENT_PERSISTED: {
            V4GmoCycleState.PROTECTION_ATTEMPTED,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.PROTECTION_ATTEMPTED: {
            V4GmoCycleState.PROTECTION_RECONCILING,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.PROTECTION_RECONCILING: {
            V4GmoCycleState.POSITION_PROTECTED,
            V4GmoCycleState.FLAT_RECONCILED,
            V4GmoCycleState.PROTECTION_CANCEL_INTENT_PERSISTED,
            V4GmoCycleState.EMERGENCY_EXIT_INTENT_PERSISTED,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.PROTECTION_CANCEL_INTENT_PERSISTED: {
            V4GmoCycleState.PROTECTION_CANCEL_ATTEMPTED,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.PROTECTION_CANCEL_ATTEMPTED: {
            V4GmoCycleState.PROTECTION_CANCEL_RECONCILING,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.PROTECTION_CANCEL_RECONCILING: {
            V4GmoCycleState.EMERGENCY_EXIT_INTENT_PERSISTED,
            V4GmoCycleState.FLAT_RECONCILED,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.EMERGENCY_EXIT_INTENT_PERSISTED: {
            V4GmoCycleState.EMERGENCY_EXIT_ATTEMPTED,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.EMERGENCY_EXIT_ATTEMPTED: {
            V4GmoCycleState.FLAT_RECONCILED,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.POSITION_PROTECTED: {
            V4GmoCycleState.PROTECTION_CANCEL_INTENT_PERSISTED,
            V4GmoCycleState.EMERGENCY_EXIT_INTENT_PERSISTED,
            V4GmoCycleState.FLAT_RECONCILED,
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        },
        V4GmoCycleState.FLAT_RECONCILED: set(),
        V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED: {
            V4GmoCycleState.OPERATOR_RELOAD_CLEARED,
        },
        V4GmoCycleState.OPERATOR_RELOAD_CLEARED: set(),
    }
    if target not in allowed[current]:
        raise V4GmoContractError(
            f"invalid v4 GMO state transition: {current.value} -> {target.value}"
        )
