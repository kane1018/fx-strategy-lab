"""GMO FX live-trading safety policy foundation: no-POST skeleton only.

This module builds the foundation so `risk_service` can eventually judge a
GMO live order request through explicit, testable safe gates instead of the
current unconditional rejection in `evaluate_order_risk`. It is not wired
into `evaluate_order_risk`, `AutomationRunner`, or `bot_service` yet -- that
connection is a separate, later Step. Nothing here performs an HTTP request,
reads credentials, or reads `.env`. Every value here is a safe boolean, safe
label, or safe count; nothing here is a real position ID, quantity, price,
or credential.

Three concerns live here on purpose, kept together because they are small
and interdependent:

- `GmoLiveRiskConfig`: GMO-specific risk limits and safety pins (values are
  conservative defaults or explicit two-way candidates; exact numbers are a
  separate decision).
- `GmoLiveKillSwitchState` / `evaluate_gmo_live_kill_switch`: the set of
  conditions that must all be clear before entry or settlement may proceed.
  retry, repost, and generic close are permanently disallowed regardless of
  kill switch state -- this policy never has a path that allows them.
- `GmoLiveEnablePolicyInput` / `evaluate_gmo_live_enable_policy`: the full
  checklist that must be true before GMO live trading could ever be turned
  on. This module only evaluates the checklist; it does not flip anything on
  and is not called by any live-enable UI or endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GmoLiveRiskConfigError(ValueError):
    """Raised when a GmoLiveRiskConfig would weaken a pinned safety invariant."""


@dataclass(frozen=True)
class GmoLiveRiskConfig:
    gmo_live_enabled: bool = False
    process_start_default_off: bool = True
    max_positions: int = 1
    max_entries_per_day: int = 1
    max_settlements_per_position: int = 1
    max_consecutive_losses_candidate_a: int = 2
    max_consecutive_losses_candidate_b: int = 3
    max_consecutive_losses_selected: int | None = 2
    official_settlement_route_required: bool = True
    generic_close_allowed: bool = False
    opposite_order_as_close_allowed: bool = False
    position_specific_actual_path_enabled: bool = False
    order_size_escalation_requires_review: bool = True

    def __post_init__(self) -> None:
        if not self.process_start_default_off:
            raise GmoLiveRiskConfigError("process_start_default_off must stay true")
        if self.max_positions < 1:
            raise GmoLiveRiskConfigError("max_positions must be at least 1")
        if self.max_entries_per_day < 0:
            raise GmoLiveRiskConfigError("max_entries_per_day must be non-negative")
        if self.max_settlements_per_position < 0:
            raise GmoLiveRiskConfigError(
                "max_settlements_per_position must be non-negative"
            )
        if not self.official_settlement_route_required:
            raise GmoLiveRiskConfigError("official_settlement_route_required must stay true")
        if self.generic_close_allowed:
            raise GmoLiveRiskConfigError("generic_close_allowed must stay false")
        if self.opposite_order_as_close_allowed:
            raise GmoLiveRiskConfigError("opposite_order_as_close_allowed must stay false")
        if self.position_specific_actual_path_enabled:
            raise GmoLiveRiskConfigError(
                "position_specific_actual_path_enabled must stay false"
            )
        if not self.order_size_escalation_requires_review:
            raise GmoLiveRiskConfigError("order_size_escalation_requires_review must stay true")
        candidates = (
            self.max_consecutive_losses_candidate_a,
            self.max_consecutive_losses_candidate_b,
        )
        if (
            self.max_consecutive_losses_selected is not None
            and self.max_consecutive_losses_selected not in candidates
        ):
            raise GmoLiveRiskConfigError(
                "max_consecutive_losses_selected must be one of the two candidates"
            )


class GmoLiveMaxConsecutiveLossesDecisionStatus(str, Enum):
    OPERATOR_DECISION_REQUIRED = "OPERATOR_DECISION_REQUIRED"
    MINIMAL_START_MAX_CONSECUTIVE_LOSSES_2 = (
        "MINIMAL_START_MAX_CONSECUTIVE_LOSSES_2"
    )
    MINIMAL_START_MAX_CONSECUTIVE_LOSSES_3 = (
        "MINIMAL_START_MAX_CONSECUTIVE_LOSSES_3"
    )


def classify_max_consecutive_losses_decision_status(
    risk_config: GmoLiveRiskConfig,
) -> GmoLiveMaxConsecutiveLossesDecisionStatus:
    """Classify whether the operator has picked between the two candidates.

    The current rollout policy stores `max_consecutive_losses_selected=2` by
    default (minimal-start), and keeps `None` as a safe decision-required
    state for explicit operator re-selection cases.
    """
    if risk_config.max_consecutive_losses_selected is None:
        return GmoLiveMaxConsecutiveLossesDecisionStatus.OPERATOR_DECISION_REQUIRED
    if (
        risk_config.max_consecutive_losses_selected
        == risk_config.max_consecutive_losses_candidate_a
    ):
        return (
            GmoLiveMaxConsecutiveLossesDecisionStatus.MINIMAL_START_MAX_CONSECUTIVE_LOSSES_2
        )
    return GmoLiveMaxConsecutiveLossesDecisionStatus.MINIMAL_START_MAX_CONSECUTIVE_LOSSES_3


def has_reached_max_consecutive_losses(
    current_consecutive_losses: int,
    risk_config: GmoLiveRiskConfig,
) -> bool:
    """Return whether the configured max consecutive losses limit has been reached.

    If selection is explicitly unset, return False to avoid an unsafe auto
    unlock; callers can decide whether this means "not reached" or "not
    configured" in their own decision path.
    """
    if risk_config.max_consecutive_losses_selected is None:
        return False
    return current_consecutive_losses >= risk_config.max_consecutive_losses_selected


class GmoLiveKillSwitchTrigger(str, Enum):
    MANUAL_STOP_REQUESTED = "manual_stop_requested"
    PROCESS_START_DEFAULT_OFF = "process_start_default_off"
    STALE_PRICE_DETECTED = "stale_price_detected"
    RISK_SERVICE_REJECTED = "risk_service_rejected"
    ACTIVE_OR_PENDING_ORDER_CONFLICT = "active_or_pending_order_conflict"
    MULTIPLE_POSITIONS_DETECTED = "multiple_positions_detected"
    SETTLEMENT_REJECTED = "settlement_rejected"
    SETTLEMENT_UNKNOWN_OR_TIMEOUT = "settlement_unknown_or_timeout"
    MAX_ENTRIES_PER_DAY_REACHED = "max_entries_per_day_reached"
    MAX_SETTLEMENTS_PER_POSITION_REACHED = "max_settlements_per_position_reached"
    MAX_CONSECUTIVE_LOSSES_REACHED = "max_consecutive_losses_reached"
    DAILY_LOSS_LIMIT_REACHED_OR_UNKNOWN = "daily_loss_limit_reached_or_unknown"
    HARD_GUARD_VIOLATION = "hard_guard_violation"
    RAW_OR_ID_VALUE_EXPOSURE_DETECTED = "raw_or_id_value_exposure_detected"
    GENERIC_CLOSE_ATTEMPT_DETECTED = "generic_close_attempt_detected"


@dataclass(frozen=True)
class GmoLiveKillSwitchState:
    manual_stop_requested: bool = False
    process_start_default_off: bool = True
    stale_price_detected: bool = False
    risk_service_rejected: bool = False
    active_or_pending_order_conflict: bool = False
    multiple_positions_detected: bool = False
    settlement_rejected: bool = False
    settlement_unknown_or_timeout: bool = False
    max_entries_per_day_reached: bool = False
    max_settlements_per_position_reached: bool = False
    max_consecutive_losses_reached: bool = False
    daily_loss_limit_reached_or_unknown: bool = False
    hard_guard_violation: bool = False
    raw_or_id_value_exposure_detected: bool = False
    generic_close_attempt_detected: bool = False


@dataclass(frozen=True)
class GmoLiveKillSwitchDecision:
    entry_allowed: bool
    settlement_allowed: bool
    retry_allowed: bool
    repost_allowed: bool
    generic_close_allowed: bool
    triggered_reasons: tuple[str, ...]


def evaluate_gmo_live_kill_switch(
    state: GmoLiveKillSwitchState,
) -> GmoLiveKillSwitchDecision:
    """Evaluate the GMO live kill switch from a safe-boolean state snapshot.

    Entry and settlement are both blocked the moment any trigger is true.
    retry, repost, and generic close are always false here, independent of
    the state -- this policy has no path that ever allows them.
    """
    reasons = tuple(
        trigger.value for trigger in GmoLiveKillSwitchTrigger if getattr(state, trigger.value)
    )
    tripped = bool(reasons)
    return GmoLiveKillSwitchDecision(
        entry_allowed=not tripped,
        settlement_allowed=not tripped,
        retry_allowed=False,
        repost_allowed=False,
        generic_close_allowed=False,
        triggered_reasons=reasons,
    )


_LIVE_ENABLE_REQUIRED_TRUE_FIELDS: tuple[str, ...] = (
    "operator_live_enable_declared",
    "post_incident_resume_policy_allowed",
    "hard_guard_default_deny_confirmed",
    "allow_bridge_absent",
    "production_allow_true_wiring_absent",
    "risk_config_present",
    "kill_switch_present_and_armed",
    "paper_evidence_safe_label_present",
    "official_settlement_route_required",
    "generic_close_forbidden",
    "settlement_side_provenance_ready",
    "settlement_side_docs_status_classified",
    "head_equals_origin_main",
    "working_tree_clean",
    "fresh_runtime_read_required",
    "fresh_operator_confirmation_required",
)


@dataclass(frozen=True)
class GmoLiveEnablePolicyInput:
    operator_live_enable_declared: bool = False
    post_incident_resume_policy_allowed: bool = False
    hard_guard_default_deny_confirmed: bool = False
    allow_bridge_absent: bool = False
    production_allow_true_wiring_absent: bool = False
    risk_config_present: bool = False
    kill_switch_present_and_armed: bool = False
    paper_evidence_safe_label_present: bool = False
    official_settlement_route_required: bool = False
    generic_close_forbidden: bool = False
    settlement_side_provenance_ready: bool = False
    settlement_side_docs_status_classified: bool = False
    head_equals_origin_main: bool = False
    working_tree_clean: bool = False
    fresh_runtime_read_required: bool = False
    fresh_operator_confirmation_required: bool = False


@dataclass(frozen=True)
class GmoLiveEnablePolicyResult:
    live_enable_ready: bool
    blocked_reasons: tuple[str, ...]


def evaluate_gmo_live_enable_policy(
    policy_input: GmoLiveEnablePolicyInput,
) -> GmoLiveEnablePolicyResult:
    """Evaluate whether every required gate for GMO live enable is true.

    This only evaluates the checklist; it does not enable anything and is
    not wired into any live-enable UI, endpoint, or automation path.
    """
    blocked = tuple(
        field_name
        for field_name in _LIVE_ENABLE_REQUIRED_TRUE_FIELDS
        if not getattr(policy_input, field_name)
    )
    return GmoLiveEnablePolicyResult(
        live_enable_ready=not blocked,
        blocked_reasons=blocked,
    )
