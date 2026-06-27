"""Step 5Y-Z dry-run plan before any real approval gate enablement."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_GATE_TTL_SECONDS,
)
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.live_order_real_approval_enablement_criteria import (
    LiveOrderRealApprovalEnablementCriteria,
    LiveOrderRealApprovalEnablementCriteriaStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

CriteriaStatus = LiveOrderRealApprovalEnablementCriteriaStatus

LIVE_ORDER_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN_ID_PREFIX = "LORAEYZ-"
MARKET_HOURS_TIMEZONE = "Asia/Tokyo"
MARKET_HOURS_SOURCE = "sanitized_snapshot_only"
MARKET_HOURS_OPEN_STATE = "OPEN"
MARKET_HOURS_MAX_AGE_SECONDS = 30

DEFAULT_PRE_ENABLE_GO_CONDITIONS = (
    "enablement criteria ready",
    "approval_gate_enabled remains false",
    "allowed_for_live remains false",
    "market-hours guard passed with sanitized snapshot",
    "not weekend",
    "market session open in sanitized snapshot",
    "no maintenance in sanitized snapshot",
    "no approval artifacts generated",
    "no API/broker/live_order_once called",
    "no POST executed",
    "one-shot constraints preserved",
    "explicit future Step 6A user instruction still required",
)

DEFAULT_PRE_ENABLE_NO_GO_CONDITIONS = (
    "weekend or market closed",
    "market hours unknown",
    "stale market-hours snapshot",
    "broker maintenance",
    "special holiday/close unknown",
    "criteria blocked",
    "approval_gate_enabled already true",
    "approval artifacts already generated",
    "any API/broker/live_order_once already called",
    "post already executed",
    "any need for retry/loop/add/change/cancel/close",
    "secret/raw response/real ID exposure risk",
)

DEFAULT_PRE_ENABLE_STOP_CONDITIONS = (
    "no explicit future Step 6A user instruction",
    "weekend/market closed/unknown",
    "fresh preflight cannot be rerun in future step",
    "exact match cannot be guaranteed",
    "same session cannot be guaranteed",
    "TTL cannot be enforced",
    "ACK tokens incomplete",
    "any result_unknown",
    "any exposure risk for secret/raw/real ID",
    "any need to exceed one POST attempt",
)

DEFAULT_FUTURE_STEP6A_HANDOFF_CONDITIONS = (
    "user explicitly requests Step 6A",
    "rerun fresh market-hours/weekend guard",
    "rerun fresh pre-approval preflight",
    "rerun implementation readiness review if stale",
    "keep no POST in Step 6A unless separately requested later",
    "keep approval_id generation separate unless Step 6A explicitly scopes it",
    "keep approval command generation separate unless Step 6A explicitly scopes it",
    "maintain allowed_for_live=false until explicitly changed in a future controlled step",
)

DEFAULT_FUTURE_STEP6A_BLOCKERS = (
    "weekend or market closed",
    "missing explicit Step 6A request",
    "stale or unknown market-hours snapshot",
    "stale or missing fresh preflight",
    "any approval artifact already generated outside approved flow",
    "any API/broker/live_order_once already called unexpectedly",
    "any secret/raw/real ID exposure risk",
    "any need for retry/loop/add/change/cancel/close",
)

REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN_DISPLAY_ALLOWED_FIELDS = (
    "plan_id",
    "criteria_id",
    "scaffold_id",
    "implementation_readiness_review_id",
    "audit_id",
    "package_id",
    "pre_approval_preflight_decision_id",
    "snapshot_id",
    "source_type",
    "strategy_name",
    "symbol",
    "side",
    "size",
    "executionType",
    "plan_status",
    "plan_ready",
    "pre_enable_go_no_go_status",
    "eligible_for_future_step6a_enablement_planning",
    "allowed_for_live=false",
    "approval_gate_enabled=false",
    "approval_id_generated=false",
    "approval_command_generated=false",
    "approval_command_copyable=false",
    "approval_command_executable=false",
    "market_hours_guard_status",
    "market_hours_block_reasons",
    "sanitized market-hours summary",
    "pre_enable_go_conditions",
    "pre_enable_no_go_conditions",
    "pre_enable_stop_conditions",
    "future_step6a_handoff_conditions",
    "future_step6a_blockers",
    "check_results",
    "blocked_reasons",
    "recommended_next_step",
)

REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN_DISPLAY_FORBIDDEN_FIELDS = (
    "API key value",
    "secret value",
    "signature value",
    "headers value",
    "raw request",
    "raw response",
    "order ID",
    "execution ID",
    "position ID",
    "clientOrderId",
    "request URL",
    "open price",
    "detailed P/L",
    "real approval_id",
    "real approval command",
    "copyable approval command",
    "approval command file",
    "clipboard approval command",
)


class LiveOrderRealApprovalEnablementDryRunPlanStatus(str, Enum):
    READY_FOR_PRE_ENABLE_GO_NO_GO_REVIEW = "READY_FOR_PRE_ENABLE_GO_NO_GO_REVIEW"
    BLOCKED_PRE_ENABLE_MARKET_HOURS = "BLOCKED_PRE_ENABLE_MARKET_HOURS"
    BLOCKED_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN = (
        "BLOCKED_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN"
    )


PlanStatus = LiveOrderRealApprovalEnablementDryRunPlanStatus


class LiveOrderRealApprovalMarketHoursGuardStatus(str, Enum):
    MARKET_HOURS_GUARD_PASSED = "MARKET_HOURS_GUARD_PASSED"
    MARKET_HOURS_GUARD_BLOCKED = "MARKET_HOURS_GUARD_BLOCKED"


MarketHoursStatus = LiveOrderRealApprovalMarketHoursGuardStatus


class LiveOrderRealApprovalPreEnableGoNoGoStatus(str, Enum):
    GO_FOR_FUTURE_STEP6A_PLANNING_ONLY = "GO_FOR_FUTURE_STEP6A_PLANNING_ONLY"
    NO_GO_MARKET_HOURS = "NO_GO_MARKET_HOURS"
    NO_GO_ENABLEMENT_CRITERIA = "NO_GO_ENABLEMENT_CRITERIA"
    NO_GO_UNSAFE_MISMATCH = "NO_GO_UNSAFE_MISMATCH"


GoNoGoStatus = LiveOrderRealApprovalPreEnableGoNoGoStatus


class LiveOrderRealApprovalEnablementDryRunPlanBlockReason(str, Enum):
    MISSING_ENABLEMENT_CRITERIA = "missing_enablement_criteria"
    ENABLEMENT_CRITERIA_NOT_READY = "enablement_criteria_not_ready"
    ENABLEMENT_CRITERIA_NOT_ELIGIBLE = "enablement_criteria_not_eligible"
    CRITERIA_ALLOWS_LIVE = "criteria_allows_live"
    CRITERIA_APPROVAL_GATE_ENABLED = "criteria_approval_gate_enabled"
    CRITERIA_NOT_DRY_RUN = "criteria_not_dry_run"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_ID_ALREADY_GENERATED = "approval_id_already_generated"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
    APPROVAL_COMMAND_COPYABLE = "approval_command_copyable"
    APPROVAL_COMMAND_EXECUTABLE = "approval_command_executable"
    USABLE_APPROVAL_ARTIFACTS_GENERATED = "usable_approval_artifacts_generated"
    REAL_APPROVAL_ARTIFACTS_AVAILABLE = "real_approval_artifacts_available"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    INVALID_TTL_SECONDS = "invalid_ttl_seconds"
    EXACT_MATCH_NOT_REQUIRED = "exact_match_not_required"
    SAME_SESSION_NOT_REQUIRED = "same_session_not_required"
    MISSING_ACK_TOKEN = "missing_ack_token"
    INVALID_POST_ATTEMPT_LIMIT = "invalid_post_attempt_limit"
    POST_ALREADY_EXECUTED = "post_already_executed"
    LIVE_ORDER_ONCE_ALREADY_CALLED = "live_order_once_already_called"
    PRIVATE_API_ALREADY_CALLED = "private_api_already_called"
    BROKER_ALREADY_CALLED = "broker_already_called"
    READ_ONLY_API_ALREADY_CALLED = "read_only_api_already_called"
    PUBLIC_API_ALREADY_CALLED = "public_api_already_called"
    RETRY_ALLOWED = "retry_allowed"
    LOOP_ALLOWED = "loop_allowed"
    ADD_ORDER_ALLOWED = "add_order_allowed"
    CHANGE_ORDER_ALLOWED = "change_order_allowed"
    CANCEL_ORDER_ALLOWED = "cancel_order_allowed"
    CLOSE_ORDER_ALLOWED = "close_order_allowed"
    MISSING_POST_RECONCILIATION_REQUIREMENT = (
        "missing_post_reconciliation_requirement"
    )
    WEEKEND_JST = "weekend_jst"
    MARKET_SESSION_NOT_OPEN = "market_session_not_open"
    MARKET_WINDOW_NOT_ALLOWED = "market_window_not_allowed"
    BROKER_MAINTENANCE_ACTIVE = "broker_maintenance_active"
    HOLIDAY_OR_SPECIAL_CLOSE = "holiday_or_special_close"
    HOLIDAY_OR_SPECIAL_CLOSE_UNKNOWN = "holiday_or_special_close_unknown"
    MARKET_HOURS_UNKNOWN = "market_hours_unknown"
    MARKET_HOURS_SNAPSHOT_STALE = "market_hours_snapshot_stale"
    INVALID_MARKET_HOURS_SOURCE = "invalid_market_hours_source"
    INVALID_TIMEZONE = "invalid_timezone"
    MISSING_MARKET_HOURS_SNAPSHOT = "missing_market_hours_snapshot"
    MISSING_PRE_ENABLE_GO_CONDITIONS = "missing_pre_enable_go_conditions"
    MISSING_PRE_ENABLE_NO_GO_CONDITIONS = "missing_pre_enable_no_go_conditions"
    MISSING_PRE_ENABLE_STOP_CONDITIONS = "missing_pre_enable_stop_conditions"
    MISSING_FUTURE_STEP6A_HANDOFF_CONDITIONS = (
        "missing_future_step6a_handoff_conditions"
    )
    MISSING_FUTURE_STEP6A_BLOCKERS = "missing_future_step6a_blockers"


BlockReason = LiveOrderRealApprovalEnablementDryRunPlanBlockReason


@dataclass(frozen=True)
class LiveOrderRealApprovalMarketHoursGuardSnapshot:
    snapshot_id: str
    created_at: datetime
    timezone: str
    market_hours_source: str
    market_session_state: str
    is_weekend_jst: bool
    market_window_allowed: bool
    broker_maintenance_active: bool
    holiday_or_special_close: bool
    holiday_or_special_close_unknown: bool
    market_hours_unknown: bool
    market_hours_snapshot_age_seconds: float
    market_hours_snapshot_max_age_seconds: float = MARKET_HOURS_MAX_AGE_SECONDS

    def __post_init__(self) -> None:
        _require_non_empty("snapshot_id", self.snapshot_id)
        _require_non_empty("timezone", self.timezone)
        _require_non_empty("market_hours_source", self.market_hours_source)
        _require_non_empty("market_session_state", self.market_session_state)
        _ensure_aware(self.created_at)
        for field_name in (
            "is_weekend_jst",
            "market_window_allowed",
            "broker_maintenance_active",
            "holiday_or_special_close",
            "holiday_or_special_close_unknown",
            "market_hours_unknown",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")
        for field_name in (
            "market_hours_snapshot_age_seconds",
            "market_hours_snapshot_max_age_seconds",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int | float) or isinstance(value, bool):
                raise LiveVerificationValidationError(f"{field_name} must be number")


@dataclass(frozen=True)
class LiveOrderRealApprovalEnablementDryRunPlanCheckResult:
    name: str
    passed: bool
    reason: str
    sanitized_value: str
    expected: str

    def __post_init__(self) -> None:
        _require_non_empty("check name", self.name)
        if type(self.passed) is not bool:
            raise LiveVerificationValidationError("check passed must be bool")
        _require_non_empty("check reason", self.reason)
        _require_non_empty("check sanitized_value", self.sanitized_value)
        _require_non_empty("check expected", self.expected)


@dataclass(frozen=True)
class LiveOrderRealApprovalEnablementDryRunPlanSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("section title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError("section requires lines")
        for line in self.lines:
            _require_non_empty("section line", line)


@dataclass(frozen=True)
class LiveOrderRealApprovalPreEnableGoNoGoReport:
    status: LiveOrderRealApprovalPreEnableGoNoGoStatus
    go_conditions: tuple[str, ...]
    no_go_conditions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    future_step6a_handoff_conditions: tuple[str, ...]
    future_step6a_blockers: tuple[str, ...]
    summary: str
    recommended_next_step: str

    def __post_init__(self) -> None:
        _require_non_empty("report summary", self.summary)
        _require_non_empty("report recommended_next_step", self.recommended_next_step)
        for label, values in (
            ("go_conditions", self.go_conditions),
            ("no_go_conditions", self.no_go_conditions),
            ("stop_conditions", self.stop_conditions),
            (
                "future_step6a_handoff_conditions",
                self.future_step6a_handoff_conditions,
            ),
            ("future_step6a_blockers", self.future_step6a_blockers),
        ):
            if not values:
                raise LiveVerificationValidationError(f"{label} required")


@dataclass(frozen=True)
class LiveOrderRealApprovalEnablementDryRunPlan:
    plan_id: str
    created_at: datetime
    criteria_id: str
    scaffold_id: str
    implementation_readiness_review_id: str
    audit_id: str
    package_id: str
    pre_approval_preflight_decision_id: str
    snapshot_id: str
    plan_source_type: str
    strategy_name: str
    symbol: str
    side: str
    size: int
    execution_type: str
    plan_status: LiveOrderRealApprovalEnablementDryRunPlanStatus
    plan_ready: bool
    pre_enable_go_no_go_status: LiveOrderRealApprovalPreEnableGoNoGoStatus
    eligible_for_future_step6a_enablement_planning: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_gate_enablement_planned: bool
    approval_gate_enablement_deferred_to_future_step: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_copyable: bool
    approval_command_executable: bool
    usable_approval_artifacts_generated: bool
    real_approval_artifacts_available: bool
    dry_run_only: bool
    requires_human_approval: bool
    explicit_user_confirmation_required: bool
    fresh_preflight_before_enablement_required: bool
    implementation_readiness_review_required: bool
    market_hours_guard_required: bool
    weekend_blocker_required: bool
    post_enablement_safety_review_required: bool
    post_approval_final_dynamic_preflight_required: bool
    one_shot_post_separate_step_required: bool
    post_reconciliation_separate_step_required: bool
    final_report_separate_step_required: bool
    ttl_seconds: int
    exact_match_required: bool
    same_session_required: bool
    required_ack_tokens: tuple[str, ...]
    post_attempt_limit: int
    post_executed: bool
    live_order_once_called: bool
    private_api_called: bool
    broker_called: bool
    read_only_api_called: bool
    public_api_called: bool
    retry_allowed: bool
    loop_allowed: bool
    add_order_allowed: bool
    change_order_allowed: bool
    cancel_order_allowed: bool
    close_order_allowed: bool
    post_reconciliation_required: bool
    market_hours_snapshot: LiveOrderRealApprovalMarketHoursGuardSnapshot
    market_hours_guard_status: LiveOrderRealApprovalMarketHoursGuardStatus
    market_hours_block_reasons: tuple[str, ...]
    pre_enable_go_no_go_report: LiveOrderRealApprovalPreEnableGoNoGoReport
    enablement_dry_run_steps: tuple[str, ...]
    pre_enable_go_conditions: tuple[str, ...]
    pre_enable_no_go_conditions: tuple[str, ...]
    pre_enable_stop_conditions: tuple[str, ...]
    future_step6a_handoff_conditions: tuple[str, ...]
    future_step6a_blockers: tuple[str, ...]
    display_allowed_fields: tuple[str, ...]
    display_forbidden_fields: tuple[str, ...]
    check_results: tuple[LiveOrderRealApprovalEnablementDryRunPlanCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApprovalEnablementDryRunPlanSection, ...]

    def __post_init__(self) -> None:
        _validate_plan(self)


@dataclass(frozen=True)
class LiveOrderRealApprovalEnablementDryRunPlanBuildResult:
    plan: LiveOrderRealApprovalEnablementDryRunPlan
    plan_id: str
    plan_status: LiveOrderRealApprovalEnablementDryRunPlanStatus
    plan_ready: bool
    pre_enable_go_no_go_status: LiveOrderRealApprovalPreEnableGoNoGoStatus
    eligible_for_future_step6a_enablement_planning: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_copyable: bool
    approval_command_executable: bool
    post_executed: bool
    live_order_once_called: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.plan.plan_id != self.plan_id:
            raise LiveVerificationValidationError("plan_id mismatch")
        if self.plan.plan_status is not self.plan_status:
            raise LiveVerificationValidationError("plan_status mismatch")
        if self.plan.plan_ready is not self.plan_ready:
            raise LiveVerificationValidationError("plan_ready mismatch")
        for field_name, value in (
            ("allowed_for_live", self.allowed_for_live),
            ("approval_gate_enabled", self.approval_gate_enabled),
            ("approval_gate_issued", self.approval_gate_issued),
            ("approval_id_generated", self.approval_id_generated),
            ("approval_command_generated", self.approval_command_generated),
            ("approval_command_copyable", self.approval_command_copyable),
            ("approval_command_executable", self.approval_command_executable),
            ("post_executed", self.post_executed),
            ("live_order_once_called", self.live_order_once_called),
        ):
            if value is not False:
                raise LiveVerificationValidationError(f"{field_name} must be False")
        if self.plan.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.plan.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_approval_enablement_dry_run_plan(
    *,
    enablement_criteria: LiveOrderRealApprovalEnablementCriteria | None,
    market_hours_snapshot: LiveOrderRealApprovalMarketHoursGuardSnapshot | None,
    created_at: datetime | None = None,
    pre_enable_go_conditions: tuple[str, ...] = DEFAULT_PRE_ENABLE_GO_CONDITIONS,
    pre_enable_no_go_conditions: tuple[str, ...] = DEFAULT_PRE_ENABLE_NO_GO_CONDITIONS,
    pre_enable_stop_conditions: tuple[str, ...] = DEFAULT_PRE_ENABLE_STOP_CONDITIONS,
    future_step6a_handoff_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_FUTURE_STEP6A_HANDOFF_CONDITIONS,
    future_step6a_blockers: tuple[str, ...] = DEFAULT_FUTURE_STEP6A_BLOCKERS,
) -> LiveOrderRealApprovalEnablementDryRunPlanBuildResult:
    """Build a no-API Step 5Y-Z plan from criteria and sanitized market hours."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    market_reasons = _market_hours_blocked_reasons(market_hours_snapshot)
    criteria_reasons = _criteria_blocked_reasons(enablement_criteria)
    condition_reasons = _condition_blocked_reasons(
        pre_enable_go_conditions=pre_enable_go_conditions,
        pre_enable_no_go_conditions=pre_enable_no_go_conditions,
        pre_enable_stop_conditions=pre_enable_stop_conditions,
        future_step6a_handoff_conditions=future_step6a_handoff_conditions,
        future_step6a_blockers=future_step6a_blockers,
    )
    blocked_reasons = _merge_reasons(
        criteria_reasons,
        _criteria_existing_reasons(enablement_criteria),
        market_reasons,
        condition_reasons,
    )
    market_guard_status = (
        MarketHoursStatus.MARKET_HOURS_GUARD_BLOCKED
        if market_reasons
        else MarketHoursStatus.MARKET_HOURS_GUARD_PASSED
    )
    if market_reasons:
        plan_status = PlanStatus.BLOCKED_PRE_ENABLE_MARKET_HOURS
        plan_ready = False
        go_no_go_status = GoNoGoStatus.NO_GO_MARKET_HOURS
        eligible = False
        recommended_next_step = (
            "wait_for_market_open_and_rerun_sanitized_market_hours_guard_no_api_no_post"
        )
        summary = (
            "blocked pre-enable plan by sanitized market-hours guard; no real "
            "approval enablement, API call, or post is allowed"
        )
    elif criteria_reasons or _criteria_existing_reasons(enablement_criteria):
        plan_status = PlanStatus.BLOCKED_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN
        plan_ready = False
        go_no_go_status = GoNoGoStatus.NO_GO_ENABLEMENT_CRITERIA
        eligible = False
        recommended_next_step = "fix_enablement_criteria_blockers_no_post"
        summary = (
            "blocked pre-enable plan by criteria; no real approval enablement, "
            "API call, or post is allowed"
        )
    elif condition_reasons:
        plan_status = PlanStatus.BLOCKED_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN
        plan_ready = False
        go_no_go_status = GoNoGoStatus.NO_GO_UNSAFE_MISMATCH
        eligible = False
        recommended_next_step = "fix_pre_enable_plan_condition_lists_no_post"
        summary = (
            "blocked pre-enable plan by missing condition lists; no real approval "
            "enablement, API call, or post is allowed"
        )
    else:
        plan_status = PlanStatus.READY_FOR_PRE_ENABLE_GO_NO_GO_REVIEW
        plan_ready = True
        go_no_go_status = GoNoGoStatus.GO_FOR_FUTURE_STEP6A_PLANNING_ONLY
        eligible = True
        recommended_next_step = (
            "stop_and_wait_for_explicit_user_instruction_for_step6a_real_approval_gate_enablement_no_post"
        )
        summary = (
            "ready pre-enable go/no-go review only; future Step 6A still requires "
            "explicit user instruction and no live post is authorized"
        )

    safe_snapshot = _snapshot_or_empty(market_hours_snapshot, created)
    check_results = _build_check_results(
        enablement_criteria=enablement_criteria,
        market_hours_snapshot=market_hours_snapshot,
        market_reasons=market_reasons,
        pre_enable_go_conditions=pre_enable_go_conditions,
        pre_enable_no_go_conditions=pre_enable_no_go_conditions,
        pre_enable_stop_conditions=pre_enable_stop_conditions,
        future_step6a_handoff_conditions=future_step6a_handoff_conditions,
        future_step6a_blockers=future_step6a_blockers,
    )
    report = LiveOrderRealApprovalPreEnableGoNoGoReport(
        status=go_no_go_status,
        go_conditions=_non_empty_condition_values(pre_enable_go_conditions),
        no_go_conditions=_non_empty_condition_values(pre_enable_no_go_conditions),
        stop_conditions=_non_empty_condition_values(pre_enable_stop_conditions),
        future_step6a_handoff_conditions=_non_empty_condition_values(
            future_step6a_handoff_conditions,
        ),
        future_step6a_blockers=_non_empty_condition_values(future_step6a_blockers),
        summary=summary,
        recommended_next_step=recommended_next_step,
    )
    plan_id = make_live_order_real_approval_enablement_dry_run_plan_id(
        criteria_id=_text_from(enablement_criteria, "criteria_id"),
        snapshot_id=safe_snapshot.snapshot_id,
        created_at=created,
        plan_status=plan_status,
        blocked_reasons=blocked_reasons,
    )
    plan = LiveOrderRealApprovalEnablementDryRunPlan(
        plan_id=plan_id,
        created_at=created,
        criteria_id=_text_from(enablement_criteria, "criteria_id"),
        scaffold_id=_text_from(enablement_criteria, "scaffold_id"),
        implementation_readiness_review_id=_text_from(
            enablement_criteria,
            "implementation_readiness_review_id",
        ),
        audit_id=_text_from(enablement_criteria, "audit_id"),
        package_id=_text_from(enablement_criteria, "package_id"),
        pre_approval_preflight_decision_id=_text_from(
            enablement_criteria,
            "pre_approval_preflight_decision_id",
        ),
        snapshot_id=safe_snapshot.snapshot_id,
        plan_source_type="step5yz_sanitized_dry_run_plan",
        strategy_name=_text_from(enablement_criteria, "strategy_name"),
        symbol=_text_from(enablement_criteria, "symbol"),
        side=_text_from(enablement_criteria, "side"),
        size=_int_from(enablement_criteria, "size"),
        execution_type=_text_from(enablement_criteria, "execution_type"),
        plan_status=plan_status,
        plan_ready=plan_ready,
        pre_enable_go_no_go_status=go_no_go_status,
        eligible_for_future_step6a_enablement_planning=eligible,
        allowed_for_live=False,
        approval_gate_enabled=False,
        approval_gate_enablement_planned=True,
        approval_gate_enablement_deferred_to_future_step=True,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_copyable=False,
        approval_command_executable=False,
        usable_approval_artifacts_generated=False,
        real_approval_artifacts_available=False,
        dry_run_only=True,
        requires_human_approval=True,
        explicit_user_confirmation_required=True,
        fresh_preflight_before_enablement_required=True,
        implementation_readiness_review_required=True,
        market_hours_guard_required=True,
        weekend_blocker_required=True,
        post_enablement_safety_review_required=True,
        post_approval_final_dynamic_preflight_required=True,
        one_shot_post_separate_step_required=True,
        post_reconciliation_separate_step_required=True,
        final_report_separate_step_required=True,
        ttl_seconds=APPROVAL_GATE_TTL_SECONDS,
        exact_match_required=True,
        same_session_required=True,
        required_ack_tokens=APPROVAL_ACK_TOKENS,
        post_attempt_limit=1,
        post_executed=False,
        live_order_once_called=False,
        private_api_called=False,
        broker_called=False,
        read_only_api_called=False,
        public_api_called=False,
        retry_allowed=False,
        loop_allowed=False,
        add_order_allowed=False,
        change_order_allowed=False,
        cancel_order_allowed=False,
        close_order_allowed=False,
        post_reconciliation_required=True,
        market_hours_snapshot=safe_snapshot,
        market_hours_guard_status=market_guard_status,
        market_hours_block_reasons=market_reasons,
        pre_enable_go_no_go_report=report,
        enablement_dry_run_steps=(
            "review Step 5X criteria",
            "evaluate sanitized market-hours/weekend snapshot",
            "record final pre-enable go/no-go only",
            "stop before real approval enablement or artifact generation",
        ),
        pre_enable_go_conditions=pre_enable_go_conditions,
        pre_enable_no_go_conditions=pre_enable_no_go_conditions,
        pre_enable_stop_conditions=pre_enable_stop_conditions,
        future_step6a_handoff_conditions=future_step6a_handoff_conditions,
        future_step6a_blockers=future_step6a_blockers,
        display_allowed_fields=REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN_DISPLAY_ALLOWED_FIELDS,
        display_forbidden_fields=(
            REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN_DISPLAY_FORBIDDEN_FIELDS
        ),
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
            pre_enable_go_conditions=pre_enable_go_conditions,
            pre_enable_no_go_conditions=pre_enable_no_go_conditions,
            pre_enable_stop_conditions=pre_enable_stop_conditions,
            future_step6a_handoff_conditions=future_step6a_handoff_conditions,
            future_step6a_blockers=future_step6a_blockers,
        ),
    )
    return LiveOrderRealApprovalEnablementDryRunPlanBuildResult(
        plan=plan,
        plan_id=plan.plan_id,
        plan_status=plan.plan_status,
        plan_ready=plan.plan_ready,
        pre_enable_go_no_go_status=plan.pre_enable_go_no_go_status,
        eligible_for_future_step6a_enablement_planning=(
            plan.eligible_for_future_step6a_enablement_planning
        ),
        allowed_for_live=False,
        approval_gate_enabled=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_copyable=False,
        approval_command_executable=False,
        post_executed=False,
        live_order_once_called=False,
        blocked_reasons=plan.blocked_reasons,
        recommended_next_step=plan.recommended_next_step,
    )


def render_live_order_real_approval_enablement_dry_run_plan_markdown(
    plan: LiveOrderRealApprovalEnablementDryRunPlan,
) -> str:
    """Render a sanitized Step 5Y-Z pre-enable report."""
    blocked_text = ", ".join(plan.blocked_reasons) or "none"
    market_blocked_text = ", ".join(plan.market_hours_block_reasons) or "none"
    go_lines = "\n".join(f"- {item}" for item in plan.pre_enable_go_conditions)
    no_go_lines = "\n".join(f"- {item}" for item in plan.pre_enable_no_go_conditions)
    stop_lines = "\n".join(f"- {item}" for item in plan.pre_enable_stop_conditions)
    handoff_lines = "\n".join(
        f"- {item}" for item in plan.future_step6a_handoff_conditions
    )
    blocker_lines = "\n".join(f"- {item}" for item in plan.future_step6a_blockers)
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in plan.check_results
    )
    snapshot = plan.market_hours_snapshot
    return "\n".join(
        (
            "# Step 5Y-Z Real Approval Enablement Dry-run Plan",
            "",
            "This Step 5Y-Z enablement dry-run plan is dry-run only.",
            "This plan does not enable a real approval gate.",
            "This plan keeps approval_gate_enabled=false.",
            "This plan keeps allowed_for_live=false.",
            "This plan uses sanitized market-hours snapshot only.",
            "This plan does not call read-only API.",
            "This plan does not call public API.",
            "This plan does not call Private API.",
            "This plan does not call live_order_once.",
            "This plan does not execute HTTP POST.",
            "This plan does not issue a real approval gate.",
            "This plan does not generate a real approval_id.",
            "This plan does not generate a real approval command.",
            "This plan does not provide copyable approval text.",
            "This plan does not authorize live POST.",
            "",
            f"plan_id: {plan.plan_id}",
            f"criteria_id: {plan.criteria_id}",
            f"scaffold_id: {plan.scaffold_id}",
            f"implementation_readiness_review_id: {plan.implementation_readiness_review_id}",
            f"audit_id: {plan.audit_id}",
            f"package_id: {plan.package_id}",
            f"pre_approval_preflight_decision_id: {plan.pre_approval_preflight_decision_id}",
            f"snapshot_id: {plan.snapshot_id}",
            f"source_type: {plan.plan_source_type}",
            f"strategy_name: {plan.strategy_name}",
            f"symbol: {plan.symbol}",
            f"side: {plan.side}",
            f"size: {plan.size}",
            f"executionType: {plan.execution_type}",
            f"plan_status: {plan.plan_status.value}",
            f"plan_ready: {plan.plan_ready}",
            f"pre_enable_go_no_go_status: {plan.pre_enable_go_no_go_status.value}",
            "eligible_for_future_step6a_enablement_planning: "
            f"{plan.eligible_for_future_step6a_enablement_planning}",
            f"allowed_for_live: {plan.allowed_for_live}",
            f"approval_gate_enabled: {plan.approval_gate_enabled}",
            "approval_gate_enablement_deferred_to_future_step: "
            f"{plan.approval_gate_enablement_deferred_to_future_step}",
            f"approval_id_generated: {plan.approval_id_generated}",
            f"approval_command_generated: {plan.approval_command_generated}",
            f"approval_command_copyable: {plan.approval_command_copyable}",
            f"approval_command_executable: {plan.approval_command_executable}",
            f"market_hours_guard_status: {plan.market_hours_guard_status.value}",
            f"market_hours_block_reasons: {market_blocked_text}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {plan.recommended_next_step}",
            "",
            "## Sanitized Market-hours Summary",
            f"- timezone: {snapshot.timezone}",
            f"- market_hours_source: {snapshot.market_hours_source}",
            f"- market_session_state: {snapshot.market_session_state}",
            f"- is_weekend_jst: {snapshot.is_weekend_jst}",
            f"- market_window_allowed: {snapshot.market_window_allowed}",
            f"- broker_maintenance_active: {snapshot.broker_maintenance_active}",
            f"- holiday_or_special_close: {snapshot.holiday_or_special_close}",
            (
                "- holiday_or_special_close_unknown: "
                f"{snapshot.holiday_or_special_close_unknown}"
            ),
            f"- market_hours_unknown: {snapshot.market_hours_unknown}",
            (
                "- market_hours_snapshot_age_seconds: "
                f"{snapshot.market_hours_snapshot_age_seconds}"
            ),
            (
                "- market_hours_snapshot_max_age_seconds: "
                f"{snapshot.market_hours_snapshot_max_age_seconds}"
            ),
            "",
            "## Pre-enable Go Conditions",
            go_lines,
            "",
            "## Pre-enable No-Go Conditions",
            no_go_lines,
            "",
            "## Pre-enable Stop Conditions",
            stop_lines,
            "",
            "## Future Step 6A Handoff Conditions",
            handoff_lines,
            "",
            "## Future Step 6A Blockers",
            blocker_lines,
            "",
            "## Check Results",
            check_lines,
        ),
    )


def make_live_order_real_approval_enablement_dry_run_plan_id(
    *,
    criteria_id: str,
    snapshot_id: str,
    created_at: datetime,
    plan_status: LiveOrderRealApprovalEnablementDryRunPlanStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "blocked_reasons": list(blocked_reasons),
        "created_at": _ensure_aware(created_at).isoformat(),
        "criteria_id": criteria_id,
        "plan_status": plan_status.value,
        "snapshot_id": snapshot_id,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN_ID_PREFIX}{digest}"


def _criteria_blocked_reasons(
    criteria: LiveOrderRealApprovalEnablementCriteria | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(criteria, LiveOrderRealApprovalEnablementCriteria):
        _add_reason(reasons, BlockReason.MISSING_ENABLEMENT_CRITERIA)
        return tuple(reasons)
    if (
        criteria.criteria_status
        is not CriteriaStatus.READY_FOR_REAL_APPROVAL_ENABLEMENT_CRITERIA_REVIEW
        or criteria.criteria_ready is not True
    ):
        _add_reason(reasons, BlockReason.ENABLEMENT_CRITERIA_NOT_READY)
    if (
        criteria.eligible_for_future_real_approval_gate_enablement_planning
        is not True
    ):
        _add_reason(reasons, BlockReason.ENABLEMENT_CRITERIA_NOT_ELIGIBLE)
    if criteria.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.CRITERIA_ALLOWS_LIVE)
    if criteria.approval_gate_enabled is not False:
        _add_reason(reasons, BlockReason.CRITERIA_APPROVAL_GATE_ENABLED)
    if criteria.dry_run_only is not True:
        _add_reason(reasons, BlockReason.CRITERIA_NOT_DRY_RUN)
    for field_value, reason in (
        (criteria.approval_gate_issued, BlockReason.APPROVAL_GATE_ALREADY_ISSUED),
        (criteria.approval_id_generated, BlockReason.APPROVAL_ID_ALREADY_GENERATED),
        (
            criteria.approval_command_generated,
            BlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (criteria.approval_command_copyable, BlockReason.APPROVAL_COMMAND_COPYABLE),
        (
            criteria.approval_command_executable,
            BlockReason.APPROVAL_COMMAND_EXECUTABLE,
        ),
        (
            criteria.usable_approval_artifacts_generated,
            BlockReason.USABLE_APPROVAL_ARTIFACTS_GENERATED,
        ),
        (
            criteria.real_approval_artifacts_available,
            BlockReason.REAL_APPROVAL_ARTIFACTS_AVAILABLE,
        ),
        (criteria.post_executed, BlockReason.POST_ALREADY_EXECUTED),
        (criteria.live_order_once_called, BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED),
        (criteria.private_api_called, BlockReason.PRIVATE_API_ALREADY_CALLED),
        (criteria.broker_called, BlockReason.BROKER_ALREADY_CALLED),
        (criteria.read_only_api_called, BlockReason.READ_ONLY_API_ALREADY_CALLED),
        (criteria.public_api_called, BlockReason.PUBLIC_API_ALREADY_CALLED),
    ):
        if field_value is not False:
            _add_reason(reasons, reason)
    if criteria.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SYMBOL)
    if criteria.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIDE)
    if criteria.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIZE)
    if criteria.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_EXECUTION_TYPE)
    if criteria.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        _add_reason(reasons, BlockReason.INVALID_TTL_SECONDS)
    if criteria.exact_match_required is not True:
        _add_reason(reasons, BlockReason.EXACT_MATCH_NOT_REQUIRED)
    if criteria.same_session_required is not True:
        _add_reason(reasons, BlockReason.SAME_SESSION_NOT_REQUIRED)
    if set(APPROVAL_ACK_TOKENS) - set(criteria.required_ack_tokens):
        _add_reason(reasons, BlockReason.MISSING_ACK_TOKEN)
    if criteria.post_attempt_limit != 1:
        _add_reason(reasons, BlockReason.INVALID_POST_ATTEMPT_LIMIT)
    for flag, reason in (
        (criteria.retry_allowed, BlockReason.RETRY_ALLOWED),
        (criteria.loop_allowed, BlockReason.LOOP_ALLOWED),
        (criteria.add_order_allowed, BlockReason.ADD_ORDER_ALLOWED),
        (criteria.change_order_allowed, BlockReason.CHANGE_ORDER_ALLOWED),
        (criteria.cancel_order_allowed, BlockReason.CANCEL_ORDER_ALLOWED),
        (criteria.close_order_allowed, BlockReason.CLOSE_ORDER_ALLOWED),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    if criteria.post_reconciliation_required is not True:
        _add_reason(reasons, BlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT)
    return tuple(reasons)


def _criteria_existing_reasons(
    criteria: LiveOrderRealApprovalEnablementCriteria | None,
) -> tuple[str, ...]:
    if not isinstance(criteria, LiveOrderRealApprovalEnablementCriteria):
        return ()
    return tuple(criteria.blocked_reasons)


def _market_hours_blocked_reasons(
    snapshot: LiveOrderRealApprovalMarketHoursGuardSnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(snapshot, LiveOrderRealApprovalMarketHoursGuardSnapshot):
        _add_reason(reasons, BlockReason.MISSING_MARKET_HOURS_SNAPSHOT)
        return tuple(reasons)
    if snapshot.timezone != MARKET_HOURS_TIMEZONE:
        _add_reason(reasons, BlockReason.INVALID_TIMEZONE)
    if snapshot.market_hours_source != MARKET_HOURS_SOURCE:
        _add_reason(reasons, BlockReason.INVALID_MARKET_HOURS_SOURCE)
    if snapshot.is_weekend_jst is not False:
        _add_reason(reasons, BlockReason.WEEKEND_JST)
    if snapshot.market_session_state != MARKET_HOURS_OPEN_STATE:
        _add_reason(reasons, BlockReason.MARKET_SESSION_NOT_OPEN)
    if snapshot.market_window_allowed is not True:
        _add_reason(reasons, BlockReason.MARKET_WINDOW_NOT_ALLOWED)
    if snapshot.broker_maintenance_active is not False:
        _add_reason(reasons, BlockReason.BROKER_MAINTENANCE_ACTIVE)
    if snapshot.holiday_or_special_close is not False:
        _add_reason(reasons, BlockReason.HOLIDAY_OR_SPECIAL_CLOSE)
    if snapshot.holiday_or_special_close_unknown is not False:
        _add_reason(reasons, BlockReason.HOLIDAY_OR_SPECIAL_CLOSE_UNKNOWN)
    if snapshot.market_hours_unknown is not False:
        _add_reason(reasons, BlockReason.MARKET_HOURS_UNKNOWN)
    if (
        snapshot.market_hours_snapshot_age_seconds
        > snapshot.market_hours_snapshot_max_age_seconds
    ):
        _add_reason(reasons, BlockReason.MARKET_HOURS_SNAPSHOT_STALE)
    return tuple(reasons)


def _condition_blocked_reasons(
    *,
    pre_enable_go_conditions: tuple[str, ...],
    pre_enable_no_go_conditions: tuple[str, ...],
    pre_enable_stop_conditions: tuple[str, ...],
    future_step6a_handoff_conditions: tuple[str, ...],
    future_step6a_blockers: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    for values, reason in (
        (pre_enable_go_conditions, BlockReason.MISSING_PRE_ENABLE_GO_CONDITIONS),
        (
            pre_enable_no_go_conditions,
            BlockReason.MISSING_PRE_ENABLE_NO_GO_CONDITIONS,
        ),
        (pre_enable_stop_conditions, BlockReason.MISSING_PRE_ENABLE_STOP_CONDITIONS),
        (
            future_step6a_handoff_conditions,
            BlockReason.MISSING_FUTURE_STEP6A_HANDOFF_CONDITIONS,
        ),
        (future_step6a_blockers, BlockReason.MISSING_FUTURE_STEP6A_BLOCKERS),
    ):
        if not values:
            _add_reason(reasons, reason)
    return tuple(reasons)


def _build_check_results(
    *,
    enablement_criteria: LiveOrderRealApprovalEnablementCriteria | None,
    market_hours_snapshot: LiveOrderRealApprovalMarketHoursGuardSnapshot | None,
    market_reasons: tuple[str, ...],
    pre_enable_go_conditions: tuple[str, ...],
    pre_enable_no_go_conditions: tuple[str, ...],
    pre_enable_stop_conditions: tuple[str, ...],
    future_step6a_handoff_conditions: tuple[str, ...],
    future_step6a_blockers: tuple[str, ...],
) -> tuple[LiveOrderRealApprovalEnablementDryRunPlanCheckResult, ...]:
    criteria_ready = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.criteria_status
        is CriteriaStatus.READY_FOR_REAL_APPROVAL_ENABLEMENT_CRITERIA_REVIEW
        and enablement_criteria.criteria_ready is True
        and (
            enablement_criteria.eligible_for_future_real_approval_gate_enablement_planning
            is True
        )
    )
    gate_disabled = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.approval_gate_enabled is False
    )
    allowed_false = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.allowed_for_live is False
    )
    no_artifacts = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.usable_approval_artifacts_generated is False
        and enablement_criteria.real_approval_artifacts_available is False
    )
    gate_not_issued = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.approval_gate_issued is False
    )
    id_not_generated = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.approval_id_generated is False
    )
    command_not_generated = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.approval_command_generated is False
    )
    command_not_copyable = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.approval_command_copyable is False
    )
    command_not_executable = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.approval_command_executable is False
    )
    no_api_calls = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.live_order_once_called is False
        and enablement_criteria.private_api_called is False
        and enablement_criteria.broker_called is False
        and enablement_criteria.read_only_api_called is False
        and enablement_criteria.public_api_called is False
    )
    post_not_executed = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.post_executed is False
    )
    one_shot = (
        isinstance(enablement_criteria, LiveOrderRealApprovalEnablementCriteria)
        and enablement_criteria.post_attempt_limit == 1
        and enablement_criteria.retry_allowed is False
        and enablement_criteria.loop_allowed is False
        and enablement_criteria.add_order_allowed is False
        and enablement_criteria.change_order_allowed is False
        and enablement_criteria.cancel_order_allowed is False
        and enablement_criteria.close_order_allowed is False
        and enablement_criteria.post_reconciliation_required is True
    )
    source_ok = (
        isinstance(market_hours_snapshot, LiveOrderRealApprovalMarketHoursGuardSnapshot)
        and market_hours_snapshot.market_hours_source == MARKET_HOURS_SOURCE
    )
    timezone_ok = (
        isinstance(market_hours_snapshot, LiveOrderRealApprovalMarketHoursGuardSnapshot)
        and market_hours_snapshot.timezone == MARKET_HOURS_TIMEZONE
    )
    not_weekend = (
        isinstance(market_hours_snapshot, LiveOrderRealApprovalMarketHoursGuardSnapshot)
        and market_hours_snapshot.is_weekend_jst is False
    )
    market_open = (
        isinstance(market_hours_snapshot, LiveOrderRealApprovalMarketHoursGuardSnapshot)
        and market_hours_snapshot.market_session_state == MARKET_HOURS_OPEN_STATE
    )
    window_allowed = (
        isinstance(market_hours_snapshot, LiveOrderRealApprovalMarketHoursGuardSnapshot)
        and market_hours_snapshot.market_window_allowed is True
    )
    maintenance_inactive = (
        isinstance(market_hours_snapshot, LiveOrderRealApprovalMarketHoursGuardSnapshot)
        and market_hours_snapshot.broker_maintenance_active is False
    )
    snapshot_fresh = (
        isinstance(market_hours_snapshot, LiveOrderRealApprovalMarketHoursGuardSnapshot)
        and not market_reasons
    )
    return (
        _check(
            "enablement_criteria_ready",
            criteria_ready,
            "enablement criteria must be ready",
            _bool_text(criteria_ready),
            "true",
        ),
        _check(
            "approval_gate_enabled_false",
            gate_disabled,
            "real approval gate must remain disabled",
            _bool_text(gate_disabled),
            "true",
        ),
        _check(
            "allowed_for_live_false",
            allowed_false,
            "plan cannot authorize live execution",
            _bool_text(allowed_false),
            "true",
        ),
        _check(
            "no_usable_approval_artifacts",
            no_artifacts,
            "usable approval artifacts must not exist",
            _bool_text(no_artifacts),
            "true",
        ),
        _check(
            "approval_gate_not_issued",
            gate_not_issued,
            "real approval gate must not be issued",
            _bool_text(gate_not_issued),
            "true",
        ),
        _check(
            "approval_id_not_generated",
            id_not_generated,
            "real approval_id must not be generated",
            _bool_text(id_not_generated),
            "true",
        ),
        _check(
            "approval_command_not_generated",
            command_not_generated,
            "real approval command must not be generated",
            _bool_text(command_not_generated),
            "true",
        ),
        _check(
            "approval_command_not_copyable",
            command_not_copyable,
            "approval command must not be copyable",
            _bool_text(command_not_copyable),
            "true",
        ),
        _check(
            "approval_command_not_executable",
            command_not_executable,
            "approval command must not be executable",
            _bool_text(command_not_executable),
            "true",
        ),
        _check(
            "market_hours_guard_source_sanitized_only",
            source_ok,
            "market-hours guard must use sanitized snapshot only",
            _bool_text(source_ok),
            "true",
        ),
        _check(
            "timezone_asia_tokyo",
            timezone_ok,
            "market-hours snapshot timezone must be Asia/Tokyo",
            _bool_text(timezone_ok),
            "true",
        ),
        _check(
            "not_weekend",
            not_weekend,
            "weekend must block",
            _bool_text(not_weekend),
            "true",
        ),
        _check(
            "market_session_open",
            market_open,
            "market session must be open in sanitized snapshot",
            _bool_text(market_open),
            "true",
        ),
        _check(
            "market_window_allowed",
            window_allowed,
            "market window must be allowed in sanitized snapshot",
            _bool_text(window_allowed),
            "true",
        ),
        _check(
            "maintenance_inactive",
            maintenance_inactive,
            "broker maintenance must be inactive in sanitized snapshot",
            _bool_text(maintenance_inactive),
            "true",
        ),
        _check(
            "market_hours_snapshot_fresh",
            snapshot_fresh,
            "market-hours snapshot must be fresh and safe",
            _bool_text(snapshot_fresh),
            "true",
        ),
        _check(
            "no_api_broker_live_order_once_called",
            no_api_calls,
            "plan cannot call APIs, broker, or live runner",
            _bool_text(no_api_calls),
            "true",
        ),
        _check(
            "post_not_executed",
            post_not_executed,
            "plan cannot execute post",
            _bool_text(post_not_executed),
            "true",
        ),
        _check(
            "one_shot_constraints_preserved",
            one_shot,
            "one-shot constraints must be preserved",
            _bool_text(one_shot),
            "true",
        ),
        _check(
            "pre_enable_go_conditions_present",
            bool(pre_enable_go_conditions),
            "pre-enable go conditions must be listed",
            _bool_text(bool(pre_enable_go_conditions)),
            "true",
        ),
        _check(
            "pre_enable_no_go_conditions_present",
            bool(pre_enable_no_go_conditions),
            "pre-enable no-go conditions must be listed",
            _bool_text(bool(pre_enable_no_go_conditions)),
            "true",
        ),
        _check(
            "pre_enable_stop_conditions_present",
            bool(pre_enable_stop_conditions),
            "pre-enable stop conditions must be listed",
            _bool_text(bool(pre_enable_stop_conditions)),
            "true",
        ),
        _check(
            "future_step6a_handoff_conditions_present",
            bool(future_step6a_handoff_conditions),
            "future Step 6A handoff conditions must be listed",
            _bool_text(bool(future_step6a_handoff_conditions)),
            "true",
        ),
        _check(
            "future_step6a_blockers_present",
            bool(future_step6a_blockers),
            "future Step 6A blockers must be listed",
            _bool_text(bool(future_step6a_blockers)),
            "true",
        ),
    )


def _build_sections(
    *,
    check_results: tuple[LiveOrderRealApprovalEnablementDryRunPlanCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
    pre_enable_go_conditions: tuple[str, ...],
    pre_enable_no_go_conditions: tuple[str, ...],
    pre_enable_stop_conditions: tuple[str, ...],
    future_step6a_handoff_conditions: tuple[str, ...],
    future_step6a_blockers: tuple[str, ...],
) -> tuple[LiveOrderRealApprovalEnablementDryRunPlanSection, ...]:
    blocked = blocked_reasons or ("none",)
    return (
        LiveOrderRealApprovalEnablementDryRunPlanSection(
            section_id="plan_summary",
            title="Plan Summary",
            lines=(
                "Step 5Y-Z records pre-enable dry-run evidence only.",
                "approval_gate_enabled=false and allowed_for_live=false remain fixed.",
                f"recommended_next_step={recommended_next_step}",
            ),
        ),
        LiveOrderRealApprovalEnablementDryRunPlanSection(
            section_id="pre_enable_go_conditions",
            title="Pre-enable Go Conditions",
            lines=pre_enable_go_conditions or ("missing",),
        ),
        LiveOrderRealApprovalEnablementDryRunPlanSection(
            section_id="pre_enable_no_go_conditions",
            title="Pre-enable No-Go Conditions",
            lines=pre_enable_no_go_conditions or ("missing",),
        ),
        LiveOrderRealApprovalEnablementDryRunPlanSection(
            section_id="pre_enable_stop_conditions",
            title="Pre-enable Stop Conditions",
            lines=pre_enable_stop_conditions or ("missing",),
        ),
        LiveOrderRealApprovalEnablementDryRunPlanSection(
            section_id="future_step6a",
            title="Future Step 6A Handoff",
            lines=(
                f"handoff_conditions={len(future_step6a_handoff_conditions)}",
                f"blockers={len(future_step6a_blockers)}",
                "Step 6A still requires explicit user instruction",
            ),
        ),
        LiveOrderRealApprovalEnablementDryRunPlanSection(
            section_id="checks",
            title="Check Results",
            lines=tuple(f"{check.name}: {check.passed}" for check in check_results),
        ),
        LiveOrderRealApprovalEnablementDryRunPlanSection(
            section_id="blocked_reasons",
            title="Blocked Reasons",
            lines=blocked,
        ),
    )


def _validate_plan(plan: LiveOrderRealApprovalEnablementDryRunPlan) -> None:
    for label, value in (
        ("plan_id", plan.plan_id),
        ("summary", plan.summary),
        ("recommended_next_step", plan.recommended_next_step),
    ):
        _require_non_empty(label, value)
    if not plan.plan_id.startswith(
        LIVE_ORDER_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN_ID_PREFIX,
    ):
        raise LiveVerificationValidationError("plan_id has invalid prefix")
    _ensure_aware(plan.created_at)
    if plan.allowed_for_live is not False:
        raise LiveVerificationValidationError("allowed_for_live must be False")
    if plan.approval_gate_enabled is not False:
        raise LiveVerificationValidationError("approval_gate_enabled must be False")
    for field_name in (
        "approval_gate_issued",
        "approval_id_generated",
        "approval_command_generated",
        "approval_command_copyable",
        "approval_command_executable",
        "usable_approval_artifacts_generated",
        "real_approval_artifacts_available",
        "post_executed",
        "live_order_once_called",
        "private_api_called",
        "broker_called",
        "read_only_api_called",
        "public_api_called",
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(plan, field_name) is not False:
            raise LiveVerificationValidationError(f"{field_name} must be False")
    for field_name in (
        "approval_gate_enablement_planned",
        "approval_gate_enablement_deferred_to_future_step",
        "dry_run_only",
        "requires_human_approval",
        "explicit_user_confirmation_required",
        "fresh_preflight_before_enablement_required",
        "implementation_readiness_review_required",
        "market_hours_guard_required",
        "weekend_blocker_required",
        "post_enablement_safety_review_required",
        "post_approval_final_dynamic_preflight_required",
        "one_shot_post_separate_step_required",
        "post_reconciliation_separate_step_required",
        "final_report_separate_step_required",
        "exact_match_required",
        "same_session_required",
        "post_reconciliation_required",
    ):
        if getattr(plan, field_name) is not True:
            raise LiveVerificationValidationError(f"{field_name} must be True")
    if plan.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("ttl_seconds must be 300")
    if plan.post_attempt_limit != 1:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if set(APPROVAL_ACK_TOKENS) - set(plan.required_ack_tokens):
        raise LiveVerificationValidationError("required_ack_tokens missing token")
    if not plan.check_results:
        raise LiveVerificationValidationError("check_results required")
    if not plan.sections:
        raise LiveVerificationValidationError("sections required")
    if not _display_forbidden_fields_are_complete(plan.display_forbidden_fields):
        raise LiveVerificationValidationError("display forbidden fields incomplete")


def _snapshot_or_empty(
    snapshot: LiveOrderRealApprovalMarketHoursGuardSnapshot | None,
    created_at: datetime,
) -> LiveOrderRealApprovalMarketHoursGuardSnapshot:
    if isinstance(snapshot, LiveOrderRealApprovalMarketHoursGuardSnapshot):
        return snapshot
    return LiveOrderRealApprovalMarketHoursGuardSnapshot(
        snapshot_id="missing_market_hours_snapshot",
        created_at=created_at,
        timezone="missing",
        market_hours_source="missing",
        market_session_state="UNKNOWN",
        is_weekend_jst=True,
        market_window_allowed=False,
        broker_maintenance_active=True,
        holiday_or_special_close=False,
        holiday_or_special_close_unknown=True,
        market_hours_unknown=True,
        market_hours_snapshot_age_seconds=MARKET_HOURS_MAX_AGE_SECONDS + 1,
    )


def _check(
    name: str,
    passed: bool,
    reason: str,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealApprovalEnablementDryRunPlanCheckResult:
    return LiveOrderRealApprovalEnablementDryRunPlanCheckResult(
        name=name,
        passed=passed,
        reason=reason,
        sanitized_value=sanitized_value,
        expected=expected,
    )


def _display_forbidden_fields_are_complete(fields: tuple[str, ...]) -> bool:
    lowered = " ".join(fields).lower()
    required_markers = (
        "api key",
        "secret",
        "signature value",
        "headers",
        "raw request",
        "raw response",
        "order id",
        "execution id",
        "position id",
        "clientorderid",
        "real approval_id",
        "real approval command",
        "copyable approval command",
    )
    return all(marker in lowered for marker in required_markers)


def _text_from(source: object, attr: str) -> str:
    value = getattr(source, attr, "")
    if value is None:
        return ""
    return str(value)


def _int_from(source: object, attr: str) -> int:
    value = getattr(source, attr, 0)
    if type(value) is not int:
        return 0
    return value


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _non_empty_condition_values(values: tuple[str, ...]) -> tuple[str, ...]:
    return values or ("missing",)


def _add_reason(
    reasons: list[str],
    reason: LiveOrderRealApprovalEnablementDryRunPlanBlockReason,
) -> None:
    if reason.value not in reasons:
        reasons.append(reason.value)


def _bool_text(value: bool) -> str:
    return "true" if value is True else "false"


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _require_non_empty(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{label} must be non-empty")
