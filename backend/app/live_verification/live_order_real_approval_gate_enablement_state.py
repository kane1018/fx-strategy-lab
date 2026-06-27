"""Step 6A dry-run approval gate enablement state.

This module can set approval_gate_enabled=True only as a sanitized model state.
It does not issue approval artifacts, call APIs, or authorize live execution.
"""

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
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    MARKET_HOURS_MAX_AGE_SECONDS,
    MARKET_HOURS_OPEN_STATE,
    MARKET_HOURS_SOURCE,
    MARKET_HOURS_TIMEZONE,
    LiveOrderRealApprovalEnablementDryRunPlan,
    LiveOrderRealApprovalEnablementDryRunPlanStatus,
    LiveOrderRealApprovalPreEnableGoNoGoStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

PlanStatus = LiveOrderRealApprovalEnablementDryRunPlanStatus
PlanGoNoGoStatus = LiveOrderRealApprovalPreEnableGoNoGoStatus

LIVE_ORDER_REAL_APPROVAL_GATE_ENABLEMENT_STATE_ID_PREFIX = "LORAGE6A-"
STEP6A_REQUEST_SCOPE_LABEL = "enable_approval_gate_state_only_no_artifacts_no_api_no_post"
APPROVAL_GATE_ENABLEMENT_SCOPE = "future_approval_artifact_generation_review_only"
FRESH_PREFLIGHT_SOURCE = "sanitized_snapshot_only"
FRESH_PREFLIGHT_READY_STATUS = "READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW"
FRESH_PREFLIGHT_MAX_AGE_SECONDS = 30

DEFAULT_FUTURE_STEP6B_HANDOFF_CONDITIONS = (
    "user explicitly requests Step 6B",
    "Step 6B remains no API and no POST unless separately scoped",
    "Step 6B may generate approval artifact only if explicitly requested",
    "approval_id generation must be exact and same-session scoped",
    "approval command generation must be exact-match and one-line scoped",
    "approval command must not be generated in Step 6A",
    "copyable approval text must not be generated in Step 6A",
    "post-approval final dynamic preflight still required before any POST",
    "one-shot POST remains separate future step",
)

DEFAULT_FUTURE_STEP6B_BLOCKERS = (
    "no explicit Step 6B request",
    "approval_gate_enabled is not true from Step 6A state",
    "any approval artifact already generated outside approved flow",
    "market/preflight state stale or unknown",
    "any API/broker/live_order_once called unexpectedly",
    "any secret/raw/real ID exposure risk",
    "any need for retry/loop/add/change/cancel/close",
)


class LiveOrderRealApprovalGateEnablementStateStatus(str, Enum):
    REAL_APPROVAL_GATE_ENABLED_NO_ARTIFACTS = (
        "REAL_APPROVAL_GATE_ENABLED_NO_ARTIFACTS"
    )
    BLOCKED_STEP6A_ENABLEMENT_REQUEST = "BLOCKED_STEP6A_ENABLEMENT_REQUEST"
    BLOCKED_STEP6A_SAFETY_SNAPSHOT = "BLOCKED_STEP6A_SAFETY_SNAPSHOT"
    BLOCKED_STEP6A_SOURCE_PLAN = "BLOCKED_STEP6A_SOURCE_PLAN"
    BLOCKED_STEP6A_UNSAFE_MISMATCH = "BLOCKED_STEP6A_UNSAFE_MISMATCH"


StateStatus = LiveOrderRealApprovalGateEnablementStateStatus


class LiveOrderRealApprovalGateEnablementStateBlockReason(str, Enum):
    MISSING_SOURCE_PLAN = "missing_source_plan"
    SOURCE_PLAN_NOT_READY = "source_plan_not_ready"
    SOURCE_PLAN_NOT_ELIGIBLE = "source_plan_not_eligible"
    SOURCE_PLAN_ALLOWS_LIVE = "source_plan_allows_live"
    SOURCE_PLAN_GATE_ALREADY_ENABLED = "source_plan_gate_already_enabled"
    SOURCE_PLAN_NOT_DRY_RUN = "source_plan_not_dry_run"
    SOURCE_PLAN_GATE_ALREADY_ISSUED = "source_plan_gate_already_issued"
    SOURCE_PLAN_APPROVAL_ID_ALREADY_GENERATED = (
        "source_plan_approval_id_already_generated"
    )
    SOURCE_PLAN_APPROVAL_COMMAND_ALREADY_GENERATED = (
        "source_plan_approval_command_already_generated"
    )
    SOURCE_PLAN_APPROVAL_COMMAND_COPYABLE = "source_plan_approval_command_copyable"
    SOURCE_PLAN_APPROVAL_COMMAND_EXECUTABLE = (
        "source_plan_approval_command_executable"
    )
    SOURCE_PLAN_USABLE_APPROVAL_ARTIFACTS_GENERATED = (
        "source_plan_usable_approval_artifacts_generated"
    )
    SOURCE_PLAN_REAL_APPROVAL_ARTIFACTS_AVAILABLE = (
        "source_plan_real_approval_artifacts_available"
    )
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
    MISSING_ENABLEMENT_REQUEST_SNAPSHOT = "missing_enablement_request_snapshot"
    EXPLICIT_STEP6A_REQUEST_MISSING = "explicit_step6a_request_missing"
    OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED = (
        "operator_real_money_risk_not_acknowledged"
    )
    OPERATOR_NO_POST_NOT_ACKNOWLEDGED = "operator_no_post_not_acknowledged"
    OPERATOR_NO_APPROVAL_ID_NOT_ACKNOWLEDGED = (
        "operator_no_approval_id_not_acknowledged"
    )
    OPERATOR_NO_APPROVAL_COMMAND_NOT_ACKNOWLEDGED = (
        "operator_no_approval_command_not_acknowledged"
    )
    OPERATOR_NO_COPYABLE_TEXT_NOT_ACKNOWLEDGED = (
        "operator_no_copyable_text_not_acknowledged"
    )
    OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED = (
        "operator_unknown_means_stop_not_acknowledged"
    )
    OPERATOR_STEP6B_ARTIFACTS_NOT_ACKNOWLEDGED = (
        "operator_step6b_artifacts_not_acknowledged"
    )
    OPERATOR_STEP6C_PREFLIGHT_NOT_ACKNOWLEDGED = (
        "operator_step6c_preflight_not_acknowledged"
    )
    OPERATOR_STEP6D_POST_NOT_ACKNOWLEDGED = "operator_step6d_post_not_acknowledged"
    INVALID_REQUEST_SCOPE_LABEL = "invalid_request_scope_label"
    MISSING_ENABLEMENT_SAFETY_SNAPSHOT = "missing_enablement_safety_snapshot"
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
    INVALID_FRESH_PREFLIGHT_SOURCE = "invalid_fresh_preflight_source"
    FRESH_PREFLIGHT_NOT_READY = "fresh_preflight_not_ready"
    FRESH_PREFLIGHT_NOT_PASSED = "fresh_preflight_not_passed"
    FRESH_PREFLIGHT_UNKNOWN = "fresh_preflight_unknown"
    FRESH_PREFLIGHT_STALE = "fresh_preflight_stale"
    OPEN_POSITION_EXISTS = "open_position_exists"
    ACTIVE_ORDER_EXISTS = "active_order_exists"
    RESULT_UNKNOWN = "result_unknown"
    RAW_RESPONSE_SAVED = "raw_response_saved"
    RAW_RESPONSE_DISPLAYED = "raw_response_displayed"
    SECRET_SCAN_NOT_PASSED = "secret_scan_not_passed"
    MISSING_FUTURE_STEP6B_HANDOFF_CONDITIONS = (
        "missing_future_step6b_handoff_conditions"
    )
    MISSING_FUTURE_STEP6B_BLOCKERS = "missing_future_step6b_blockers"


BlockReason = LiveOrderRealApprovalGateEnablementStateBlockReason


@dataclass(frozen=True)
class LiveOrderRealApprovalGateEnablementRequestSnapshot:
    request_id: str
    created_at: datetime
    explicit_step6a_user_instruction_received: bool
    operator_understands_real_money_risk: bool
    operator_understands_no_post_in_step6a: bool
    operator_understands_no_approval_id_in_step6a: bool
    operator_understands_no_approval_command_in_step6a: bool
    operator_understands_no_copyable_text_in_step6a: bool
    operator_understands_unknown_means_stop: bool
    operator_understands_step6b_required_for_artifacts: bool
    operator_understands_step6c_or_later_required_for_api_preflight: bool
    operator_understands_step6d_or_later_required_for_post: bool
    request_scope_label: str

    def __post_init__(self) -> None:
        _require_non_empty("request_id", self.request_id)
        _ensure_aware(self.created_at)
        _require_non_empty("request_scope_label", self.request_scope_label)
        for field_name in (
            "explicit_step6a_user_instruction_received",
            "operator_understands_real_money_risk",
            "operator_understands_no_post_in_step6a",
            "operator_understands_no_approval_id_in_step6a",
            "operator_understands_no_approval_command_in_step6a",
            "operator_understands_no_copyable_text_in_step6a",
            "operator_understands_unknown_means_stop",
            "operator_understands_step6b_required_for_artifacts",
            "operator_understands_step6c_or_later_required_for_api_preflight",
            "operator_understands_step6d_or_later_required_for_post",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")


@dataclass(frozen=True)
class LiveOrderRealApprovalGateEnablementSafetySnapshot:
    safety_snapshot_id: str
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
    market_hours_snapshot_max_age_seconds: float
    fresh_pre_approval_preflight_source: str
    fresh_pre_approval_preflight_status: str
    fresh_pre_approval_preflight_passed: bool
    fresh_pre_approval_preflight_unknown: bool
    fresh_pre_approval_preflight_age_seconds: float
    fresh_pre_approval_preflight_max_age_seconds: float
    open_positions_count: int
    active_orders_count: int
    result_unknown: bool
    raw_response_saved: bool
    raw_response_displayed: bool
    secret_scan_passed: bool

    def __post_init__(self) -> None:
        _require_non_empty("safety_snapshot_id", self.safety_snapshot_id)
        _ensure_aware(self.created_at)
        for label, value in (
            ("timezone", self.timezone),
            ("market_hours_source", self.market_hours_source),
            ("market_session_state", self.market_session_state),
            (
                "fresh_pre_approval_preflight_source",
                self.fresh_pre_approval_preflight_source,
            ),
            (
                "fresh_pre_approval_preflight_status",
                self.fresh_pre_approval_preflight_status,
            ),
        ):
            _require_non_empty(label, value)
        for field_name in (
            "is_weekend_jst",
            "market_window_allowed",
            "broker_maintenance_active",
            "holiday_or_special_close",
            "holiday_or_special_close_unknown",
            "market_hours_unknown",
            "fresh_pre_approval_preflight_passed",
            "fresh_pre_approval_preflight_unknown",
            "result_unknown",
            "raw_response_saved",
            "raw_response_displayed",
            "secret_scan_passed",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")
        for field_name in (
            "market_hours_snapshot_age_seconds",
            "market_hours_snapshot_max_age_seconds",
            "fresh_pre_approval_preflight_age_seconds",
            "fresh_pre_approval_preflight_max_age_seconds",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int | float) or isinstance(value, bool):
                raise LiveVerificationValidationError(f"{field_name} must be number")
        for field_name in ("open_positions_count", "active_orders_count"):
            if type(getattr(self, field_name)) is not int:
                raise LiveVerificationValidationError(f"{field_name} must be int")


@dataclass(frozen=True)
class LiveOrderRealApprovalGateEnablementStateCheckResult:
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
class LiveOrderRealApprovalGateEnablementStateSection:
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
class LiveOrderRealApprovalGateEnablementState:
    enablement_state_id: str
    created_at: datetime
    source_plan_id: str
    criteria_id: str
    scaffold_id: str
    implementation_readiness_review_id: str
    audit_id: str
    package_id: str
    pre_approval_preflight_decision_id: str
    snapshot_id: str
    source_type: str
    strategy_name: str
    symbol: str
    side: str
    size: int
    execution_type: str
    enablement_status: LiveOrderRealApprovalGateEnablementStateStatus
    enablement_state_ready: bool
    eligible_for_future_step6b_approval_artifact_generation: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_gate_enablement_scope: str
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
    post_allowed_this_step: bool
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
    enablement_request_snapshot: LiveOrderRealApprovalGateEnablementRequestSnapshot
    enablement_safety_snapshot: LiveOrderRealApprovalGateEnablementSafetySnapshot
    future_step6b_handoff_conditions: tuple[str, ...]
    future_step6b_blockers: tuple[str, ...]
    check_results: tuple[LiveOrderRealApprovalGateEnablementStateCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApprovalGateEnablementStateSection, ...]

    def __post_init__(self) -> None:
        _validate_state(self)


@dataclass(frozen=True)
class LiveOrderRealApprovalGateEnablementStateBuildResult:
    state: LiveOrderRealApprovalGateEnablementState
    enablement_state_id: str
    enablement_status: LiveOrderRealApprovalGateEnablementStateStatus
    enablement_state_ready: bool
    eligible_for_future_step6b_approval_artifact_generation: bool
    approval_gate_enabled: bool
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_copyable: bool
    approval_command_executable: bool
    usable_approval_artifacts_generated: bool
    real_approval_artifacts_available: bool
    post_allowed_this_step: bool
    post_executed: bool
    live_order_once_called: bool
    private_api_called: bool
    broker_called: bool
    read_only_api_called: bool
    public_api_called: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.state.enablement_state_id != self.enablement_state_id:
            raise LiveVerificationValidationError("enablement_state_id mismatch")
        if self.state.enablement_status is not self.enablement_status:
            raise LiveVerificationValidationError("enablement_status mismatch")
        if self.state.enablement_state_ready is not self.enablement_state_ready:
            raise LiveVerificationValidationError("enablement_state_ready mismatch")
        if self.state.approval_gate_enabled is not self.approval_gate_enabled:
            raise LiveVerificationValidationError("approval_gate_enabled mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("allowed_for_live must be False")
        for field_name in (
            "approval_gate_issued",
            "approval_id_generated",
            "approval_command_generated",
            "approval_command_copyable",
            "approval_command_executable",
            "usable_approval_artifacts_generated",
            "real_approval_artifacts_available",
            "post_allowed_this_step",
            "post_executed",
            "live_order_once_called",
            "private_api_called",
            "broker_called",
            "read_only_api_called",
            "public_api_called",
        ):
            if getattr(self, field_name) is not False:
                raise LiveVerificationValidationError(f"{field_name} must be False")
        if self.state.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.state.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_approval_gate_enablement_state(
    *,
    enablement_dry_run_plan: LiveOrderRealApprovalEnablementDryRunPlan | None,
    enablement_request_snapshot: (
        LiveOrderRealApprovalGateEnablementRequestSnapshot | None
    ),
    enablement_safety_snapshot: (
        LiveOrderRealApprovalGateEnablementSafetySnapshot | None
    ),
    created_at: datetime | None = None,
    future_step6b_handoff_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_FUTURE_STEP6B_HANDOFF_CONDITIONS,
    future_step6b_blockers: tuple[str, ...] = DEFAULT_FUTURE_STEP6B_BLOCKERS,
) -> LiveOrderRealApprovalGateEnablementStateBuildResult:
    """Build Step 6A enablement state without generating approval artifacts."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    plan_reasons = _source_plan_blocked_reasons(enablement_dry_run_plan)
    request_reasons = _request_blocked_reasons(enablement_request_snapshot)
    safety_reasons = _safety_blocked_reasons(enablement_safety_snapshot)
    condition_reasons = _condition_blocked_reasons(
        future_step6b_handoff_conditions=future_step6b_handoff_conditions,
        future_step6b_blockers=future_step6b_blockers,
    )
    blocked_reasons = _merge_reasons(
        plan_reasons,
        _source_plan_existing_reasons(enablement_dry_run_plan),
        request_reasons,
        safety_reasons,
        condition_reasons,
    )
    if _source_plan_is_blocked(enablement_dry_run_plan, plan_reasons):
        status = StateStatus.BLOCKED_STEP6A_SOURCE_PLAN
        ready = False
        eligible = False
        approval_gate_enabled = False
        recommended_next_step = "fix_enablement_dry_run_plan_blockers_no_post"
        summary = "blocked Step 6A state by source plan; no artifacts, API, or post"
    elif request_reasons:
        status = StateStatus.BLOCKED_STEP6A_ENABLEMENT_REQUEST
        ready = False
        eligible = False
        approval_gate_enabled = False
        recommended_next_step = (
            "provide_explicit_step6a_request_and_acknowledgements_no_post"
        )
        summary = "blocked Step 6A state by request acknowledgements; no artifacts"
    elif safety_reasons:
        status = StateStatus.BLOCKED_STEP6A_SAFETY_SNAPSHOT
        ready = False
        eligible = False
        approval_gate_enabled = False
        recommended_next_step = (
            "rerun_sanitized_safety_snapshot_when_market_open_no_api_no_post"
        )
        summary = "blocked Step 6A state by sanitized safety snapshot; no API"
    elif plan_reasons or condition_reasons:
        status = StateStatus.BLOCKED_STEP6A_UNSAFE_MISMATCH
        ready = False
        eligible = False
        approval_gate_enabled = False
        recommended_next_step = "fix_step6a_unsafe_mismatch_no_api_no_post"
        summary = "blocked Step 6A state by unsafe mismatch; no artifacts or post"
    else:
        status = StateStatus.REAL_APPROVAL_GATE_ENABLED_NO_ARTIFACTS
        ready = True
        eligible = True
        approval_gate_enabled = True
        recommended_next_step = (
            "stop_and_wait_for_explicit_step6b_approval_artifact_generation_request_no_api_no_post"
        )
        summary = (
            "Step 6A enabled approval gate state only; approval artifacts, APIs, "
            "and live post remain unavailable"
        )
    safe_request = _request_or_empty(enablement_request_snapshot, created)
    safe_safety = _safety_or_empty(enablement_safety_snapshot, created)
    check_results = _build_check_results(
        enablement_dry_run_plan=enablement_dry_run_plan,
        enablement_request_snapshot=enablement_request_snapshot,
        enablement_safety_snapshot=enablement_safety_snapshot,
        future_step6b_handoff_conditions=future_step6b_handoff_conditions,
        future_step6b_blockers=future_step6b_blockers,
        approval_gate_enabled=approval_gate_enabled,
    )
    state_id = make_live_order_real_approval_gate_enablement_state_id(
        source_plan_id=_text_from(enablement_dry_run_plan, "plan_id"),
        request_id=safe_request.request_id,
        safety_snapshot_id=safe_safety.safety_snapshot_id,
        created_at=created,
        enablement_status=status,
        blocked_reasons=blocked_reasons,
    )
    state = LiveOrderRealApprovalGateEnablementState(
        enablement_state_id=state_id,
        created_at=created,
        source_plan_id=_text_from(enablement_dry_run_plan, "plan_id"),
        criteria_id=_text_from(enablement_dry_run_plan, "criteria_id"),
        scaffold_id=_text_from(enablement_dry_run_plan, "scaffold_id"),
        implementation_readiness_review_id=_text_from(
            enablement_dry_run_plan,
            "implementation_readiness_review_id",
        ),
        audit_id=_text_from(enablement_dry_run_plan, "audit_id"),
        package_id=_text_from(enablement_dry_run_plan, "package_id"),
        pre_approval_preflight_decision_id=_text_from(
            enablement_dry_run_plan,
            "pre_approval_preflight_decision_id",
        ),
        snapshot_id=safe_safety.safety_snapshot_id,
        source_type=_text_from(enablement_dry_run_plan, "plan_source_type"),
        strategy_name=_text_from(enablement_dry_run_plan, "strategy_name"),
        symbol=_text_from(enablement_dry_run_plan, "symbol"),
        side=_text_from(enablement_dry_run_plan, "side"),
        size=_int_from(enablement_dry_run_plan, "size"),
        execution_type=_text_from(enablement_dry_run_plan, "execution_type"),
        enablement_status=status,
        enablement_state_ready=ready,
        eligible_for_future_step6b_approval_artifact_generation=eligible,
        allowed_for_live=False,
        approval_gate_enabled=approval_gate_enabled,
        approval_gate_enablement_scope=APPROVAL_GATE_ENABLEMENT_SCOPE,
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
        post_allowed_this_step=False,
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
        enablement_request_snapshot=safe_request,
        enablement_safety_snapshot=safe_safety,
        future_step6b_handoff_conditions=future_step6b_handoff_conditions,
        future_step6b_blockers=future_step6b_blockers,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
            future_step6b_handoff_conditions=future_step6b_handoff_conditions,
            future_step6b_blockers=future_step6b_blockers,
        ),
    )
    return LiveOrderRealApprovalGateEnablementStateBuildResult(
        state=state,
        enablement_state_id=state.enablement_state_id,
        enablement_status=state.enablement_status,
        enablement_state_ready=state.enablement_state_ready,
        eligible_for_future_step6b_approval_artifact_generation=(
            state.eligible_for_future_step6b_approval_artifact_generation
        ),
        approval_gate_enabled=state.approval_gate_enabled,
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_copyable=False,
        approval_command_executable=False,
        usable_approval_artifacts_generated=False,
        real_approval_artifacts_available=False,
        post_allowed_this_step=False,
        post_executed=False,
        live_order_once_called=False,
        private_api_called=False,
        broker_called=False,
        read_only_api_called=False,
        public_api_called=False,
        blocked_reasons=state.blocked_reasons,
        recommended_next_step=state.recommended_next_step,
    )


def render_live_order_real_approval_gate_enablement_state_markdown(
    state: LiveOrderRealApprovalGateEnablementState,
) -> str:
    """Render a sanitized Step 6A enablement state report."""
    blocked_text = ", ".join(state.blocked_reasons) or "none"
    handoff_lines = "\n".join(
        f"- {item}" for item in state.future_step6b_handoff_conditions
    )
    blocker_lines = "\n".join(f"- {item}" for item in state.future_step6b_blockers)
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in state.check_results
    )
    safety = state.enablement_safety_snapshot
    return "\n".join(
        (
            "# Step 6A Real Approval Gate Enablement State",
            "",
            "This Step 6A approval gate enablement state is dry-run only.",
            (
                "This Step 6A state may set approval_gate_enabled=true only as "
                "a sanitized model output."
            ),
            "This Step 6A state keeps allowed_for_live=false.",
            "This Step 6A state does not issue a real approval gate.",
            "This Step 6A state does not generate a real approval_id.",
            "This Step 6A state does not generate a real approval command.",
            "This Step 6A state does not provide copyable approval text.",
            "This Step 6A state does not call read-only API.",
            "This Step 6A state does not call public API.",
            "This Step 6A state does not call Private API.",
            "This Step 6A state does not call live_order_once.",
            "This Step 6A state does not execute HTTP POST.",
            "This Step 6A state does not authorize live POST.",
            "",
            f"enablement_state_id: {state.enablement_state_id}",
            f"source_plan_id: {state.source_plan_id}",
            f"criteria_id: {state.criteria_id}",
            f"scaffold_id: {state.scaffold_id}",
            (
                "implementation_readiness_review_id: "
                f"{state.implementation_readiness_review_id}"
            ),
            f"audit_id: {state.audit_id}",
            f"package_id: {state.package_id}",
            (
                "pre_approval_preflight_decision_id: "
                f"{state.pre_approval_preflight_decision_id}"
            ),
            f"source_type: {state.source_type}",
            f"strategy_name: {state.strategy_name}",
            f"symbol: {state.symbol}",
            f"side: {state.side}",
            f"size: {state.size}",
            f"executionType: {state.execution_type}",
            f"enablement_status: {state.enablement_status.value}",
            f"enablement_state_ready: {state.enablement_state_ready}",
            (
                "eligible_for_future_step6b_approval_artifact_generation: "
                f"{state.eligible_for_future_step6b_approval_artifact_generation}"
            ),
            f"approval_gate_enabled: {state.approval_gate_enabled}",
            f"allowed_for_live: {state.allowed_for_live}",
            f"approval_gate_enablement_scope: {state.approval_gate_enablement_scope}",
            f"approval_gate_issued: {state.approval_gate_issued}",
            f"approval_id_generated: {state.approval_id_generated}",
            f"approval_command_generated: {state.approval_command_generated}",
            f"approval_command_copyable: {state.approval_command_copyable}",
            f"approval_command_executable: {state.approval_command_executable}",
            (
                "usable_approval_artifacts_generated: "
                f"{state.usable_approval_artifacts_generated}"
            ),
            (
                "real_approval_artifacts_available: "
                f"{state.real_approval_artifacts_available}"
            ),
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {state.recommended_next_step}",
            "",
            "## Sanitized Market-hours Summary",
            f"- timezone: {safety.timezone}",
            f"- market_hours_source: {safety.market_hours_source}",
            f"- market_session_state: {safety.market_session_state}",
            f"- is_weekend_jst: {safety.is_weekend_jst}",
            f"- market_window_allowed: {safety.market_window_allowed}",
            f"- broker_maintenance_active: {safety.broker_maintenance_active}",
            f"- holiday_or_special_close: {safety.holiday_or_special_close}",
            (
                "- holiday_or_special_close_unknown: "
                f"{safety.holiday_or_special_close_unknown}"
            ),
            f"- market_hours_unknown: {safety.market_hours_unknown}",
            (
                "- market_hours_snapshot_age_seconds: "
                f"{safety.market_hours_snapshot_age_seconds}"
            ),
            "",
            "## Sanitized Fresh Preflight Summary",
            (
                "- fresh_pre_approval_preflight_source: "
                f"{safety.fresh_pre_approval_preflight_source}"
            ),
            (
                "- fresh_pre_approval_preflight_status: "
                f"{safety.fresh_pre_approval_preflight_status}"
            ),
            (
                "- fresh_pre_approval_preflight_passed: "
                f"{safety.fresh_pre_approval_preflight_passed}"
            ),
            (
                "- fresh_pre_approval_preflight_unknown: "
                f"{safety.fresh_pre_approval_preflight_unknown}"
            ),
            (
                "- fresh_pre_approval_preflight_age_seconds: "
                f"{safety.fresh_pre_approval_preflight_age_seconds}"
            ),
            f"- open_positions_count: {safety.open_positions_count}",
            f"- active_orders_count: {safety.active_orders_count}",
            f"- result_unknown: {safety.result_unknown}",
            f"- raw_response_saved: {safety.raw_response_saved}",
            f"- raw_response_displayed: {safety.raw_response_displayed}",
            f"- secret_scan_passed: {safety.secret_scan_passed}",
            "",
            "## Future Step 6B Handoff Conditions",
            handoff_lines,
            "",
            "## Future Step 6B Blockers",
            blocker_lines,
            "",
            "## Check Results",
            check_lines,
        ),
    )


def make_live_order_real_approval_gate_enablement_state_id(
    *,
    source_plan_id: str,
    request_id: str,
    safety_snapshot_id: str,
    created_at: datetime,
    enablement_status: LiveOrderRealApprovalGateEnablementStateStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "blocked_reasons": list(blocked_reasons),
        "created_at": _ensure_aware(created_at).isoformat(),
        "enablement_status": enablement_status.value,
        "request_id": request_id,
        "safety_snapshot_id": safety_snapshot_id,
        "source_plan_id": source_plan_id,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_GATE_ENABLEMENT_STATE_ID_PREFIX}{digest}"


def _source_plan_blocked_reasons(
    plan: LiveOrderRealApprovalEnablementDryRunPlan | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan):
        _add_reason(reasons, BlockReason.MISSING_SOURCE_PLAN)
        return tuple(reasons)
    if (
        plan.plan_status is not PlanStatus.READY_FOR_PRE_ENABLE_GO_NO_GO_REVIEW
        or plan.pre_enable_go_no_go_status
        is not PlanGoNoGoStatus.GO_FOR_FUTURE_STEP6A_PLANNING_ONLY
        or plan.plan_ready is not True
    ):
        _add_reason(reasons, BlockReason.SOURCE_PLAN_NOT_READY)
    if plan.eligible_for_future_step6a_enablement_planning is not True:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_NOT_ELIGIBLE)
    if plan.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_ALLOWS_LIVE)
    if plan.approval_gate_enabled is not False:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_GATE_ALREADY_ENABLED)
    if plan.dry_run_only is not True:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_NOT_DRY_RUN)
    for field_value, reason in (
        (plan.approval_gate_issued, BlockReason.SOURCE_PLAN_GATE_ALREADY_ISSUED),
        (
            plan.approval_id_generated,
            BlockReason.SOURCE_PLAN_APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            plan.approval_command_generated,
            BlockReason.SOURCE_PLAN_APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            plan.approval_command_copyable,
            BlockReason.SOURCE_PLAN_APPROVAL_COMMAND_COPYABLE,
        ),
        (
            plan.approval_command_executable,
            BlockReason.SOURCE_PLAN_APPROVAL_COMMAND_EXECUTABLE,
        ),
        (
            plan.usable_approval_artifacts_generated,
            BlockReason.SOURCE_PLAN_USABLE_APPROVAL_ARTIFACTS_GENERATED,
        ),
        (
            plan.real_approval_artifacts_available,
            BlockReason.SOURCE_PLAN_REAL_APPROVAL_ARTIFACTS_AVAILABLE,
        ),
        (plan.post_executed, BlockReason.POST_ALREADY_EXECUTED),
        (plan.live_order_once_called, BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED),
        (plan.private_api_called, BlockReason.PRIVATE_API_ALREADY_CALLED),
        (plan.broker_called, BlockReason.BROKER_ALREADY_CALLED),
        (plan.read_only_api_called, BlockReason.READ_ONLY_API_ALREADY_CALLED),
        (plan.public_api_called, BlockReason.PUBLIC_API_ALREADY_CALLED),
    ):
        if field_value is not False:
            _add_reason(reasons, reason)
    if plan.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SYMBOL)
    if plan.side not in {LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value}:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIDE)
    if plan.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIZE)
    if plan.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_EXECUTION_TYPE)
    if plan.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        _add_reason(reasons, BlockReason.INVALID_TTL_SECONDS)
    if plan.exact_match_required is not True:
        _add_reason(reasons, BlockReason.EXACT_MATCH_NOT_REQUIRED)
    if plan.same_session_required is not True:
        _add_reason(reasons, BlockReason.SAME_SESSION_NOT_REQUIRED)
    if set(APPROVAL_ACK_TOKENS) - set(plan.required_ack_tokens):
        _add_reason(reasons, BlockReason.MISSING_ACK_TOKEN)
    if plan.post_attempt_limit != 1:
        _add_reason(reasons, BlockReason.INVALID_POST_ATTEMPT_LIMIT)
    for flag, reason in (
        (plan.retry_allowed, BlockReason.RETRY_ALLOWED),
        (plan.loop_allowed, BlockReason.LOOP_ALLOWED),
        (plan.add_order_allowed, BlockReason.ADD_ORDER_ALLOWED),
        (plan.change_order_allowed, BlockReason.CHANGE_ORDER_ALLOWED),
        (plan.cancel_order_allowed, BlockReason.CANCEL_ORDER_ALLOWED),
        (plan.close_order_allowed, BlockReason.CLOSE_ORDER_ALLOWED),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    if plan.post_reconciliation_required is not True:
        _add_reason(reasons, BlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT)
    return tuple(reasons)


def _source_plan_existing_reasons(
    plan: LiveOrderRealApprovalEnablementDryRunPlan | None,
) -> tuple[str, ...]:
    if not isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan):
        return ()
    return tuple(plan.blocked_reasons)


def _request_blocked_reasons(
    snapshot: LiveOrderRealApprovalGateEnablementRequestSnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(snapshot, LiveOrderRealApprovalGateEnablementRequestSnapshot):
        _add_reason(reasons, BlockReason.MISSING_ENABLEMENT_REQUEST_SNAPSHOT)
        return tuple(reasons)
    for field_name, reason in (
        (
            "explicit_step6a_user_instruction_received",
            BlockReason.EXPLICIT_STEP6A_REQUEST_MISSING,
        ),
        (
            "operator_understands_real_money_risk",
            BlockReason.OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_post_in_step6a",
            BlockReason.OPERATOR_NO_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_approval_id_in_step6a",
            BlockReason.OPERATOR_NO_APPROVAL_ID_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_approval_command_in_step6a",
            BlockReason.OPERATOR_NO_APPROVAL_COMMAND_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_copyable_text_in_step6a",
            BlockReason.OPERATOR_NO_COPYABLE_TEXT_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_unknown_means_stop",
            BlockReason.OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6b_required_for_artifacts",
            BlockReason.OPERATOR_STEP6B_ARTIFACTS_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6c_or_later_required_for_api_preflight",
            BlockReason.OPERATOR_STEP6C_PREFLIGHT_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6d_or_later_required_for_post",
            BlockReason.OPERATOR_STEP6D_POST_NOT_ACKNOWLEDGED,
        ),
    ):
        if getattr(snapshot, field_name) is not True:
            _add_reason(reasons, reason)
    if snapshot.request_scope_label != STEP6A_REQUEST_SCOPE_LABEL:
        _add_reason(reasons, BlockReason.INVALID_REQUEST_SCOPE_LABEL)
    return tuple(reasons)


def _safety_blocked_reasons(
    snapshot: LiveOrderRealApprovalGateEnablementSafetySnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(snapshot, LiveOrderRealApprovalGateEnablementSafetySnapshot):
        _add_reason(reasons, BlockReason.MISSING_ENABLEMENT_SAFETY_SNAPSHOT)
        return tuple(reasons)
    if snapshot.timezone != MARKET_HOURS_TIMEZONE:
        _add_reason(reasons, BlockReason.INVALID_TIMEZONE)
    if snapshot.market_hours_source != MARKET_HOURS_SOURCE:
        _add_reason(reasons, BlockReason.INVALID_MARKET_HOURS_SOURCE)
    if snapshot.market_session_state != MARKET_HOURS_OPEN_STATE:
        _add_reason(reasons, BlockReason.MARKET_SESSION_NOT_OPEN)
    if snapshot.is_weekend_jst is not False:
        _add_reason(reasons, BlockReason.WEEKEND_JST)
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
    if snapshot.fresh_pre_approval_preflight_source != FRESH_PREFLIGHT_SOURCE:
        _add_reason(reasons, BlockReason.INVALID_FRESH_PREFLIGHT_SOURCE)
    if snapshot.fresh_pre_approval_preflight_status != FRESH_PREFLIGHT_READY_STATUS:
        _add_reason(reasons, BlockReason.FRESH_PREFLIGHT_NOT_READY)
    if snapshot.fresh_pre_approval_preflight_passed is not True:
        _add_reason(reasons, BlockReason.FRESH_PREFLIGHT_NOT_PASSED)
    if snapshot.fresh_pre_approval_preflight_unknown is not False:
        _add_reason(reasons, BlockReason.FRESH_PREFLIGHT_UNKNOWN)
    if (
        snapshot.fresh_pre_approval_preflight_age_seconds
        > snapshot.fresh_pre_approval_preflight_max_age_seconds
    ):
        _add_reason(reasons, BlockReason.FRESH_PREFLIGHT_STALE)
    if snapshot.open_positions_count != 0:
        _add_reason(reasons, BlockReason.OPEN_POSITION_EXISTS)
    if snapshot.active_orders_count != 0:
        _add_reason(reasons, BlockReason.ACTIVE_ORDER_EXISTS)
    if snapshot.result_unknown is not False:
        _add_reason(reasons, BlockReason.RESULT_UNKNOWN)
    if snapshot.raw_response_saved is not False:
        _add_reason(reasons, BlockReason.RAW_RESPONSE_SAVED)
    if snapshot.raw_response_displayed is not False:
        _add_reason(reasons, BlockReason.RAW_RESPONSE_DISPLAYED)
    if snapshot.secret_scan_passed is not True:
        _add_reason(reasons, BlockReason.SECRET_SCAN_NOT_PASSED)
    return tuple(reasons)


def _condition_blocked_reasons(
    *,
    future_step6b_handoff_conditions: tuple[str, ...],
    future_step6b_blockers: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not future_step6b_handoff_conditions:
        _add_reason(reasons, BlockReason.MISSING_FUTURE_STEP6B_HANDOFF_CONDITIONS)
    if not future_step6b_blockers:
        _add_reason(reasons, BlockReason.MISSING_FUTURE_STEP6B_BLOCKERS)
    return tuple(reasons)


def _build_check_results(
    *,
    enablement_dry_run_plan: LiveOrderRealApprovalEnablementDryRunPlan | None,
    enablement_request_snapshot: (
        LiveOrderRealApprovalGateEnablementRequestSnapshot | None
    ),
    enablement_safety_snapshot: (
        LiveOrderRealApprovalGateEnablementSafetySnapshot | None
    ),
    future_step6b_handoff_conditions: tuple[str, ...],
    future_step6b_blockers: tuple[str, ...],
    approval_gate_enabled: bool,
) -> tuple[LiveOrderRealApprovalGateEnablementStateCheckResult, ...]:
    plan_ready = not _source_plan_blocked_reasons(enablement_dry_run_plan)
    request_ready = not _request_blocked_reasons(enablement_request_snapshot)
    safety_ready = not _safety_blocked_reasons(enablement_safety_snapshot)
    safety = enablement_safety_snapshot
    plan = enablement_dry_run_plan
    no_api_called = isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan) and all(
        getattr(plan, field_name) is False
        for field_name in (
            "live_order_once_called",
            "private_api_called",
            "broker_called",
            "read_only_api_called",
            "public_api_called",
        )
    )
    one_shot_preserved = isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan) and (
        plan.post_attempt_limit == 1
        and plan.retry_allowed is False
        and plan.loop_allowed is False
        and plan.add_order_allowed is False
        and plan.change_order_allowed is False
        and plan.cancel_order_allowed is False
        and plan.close_order_allowed is False
    )
    return (
        _check(
            "source_enablement_dry_run_plan_ready",
            plan_ready,
            "Step 5Y-Z plan must be ready",
            _bool_text(plan_ready),
            "true",
        ),
        _check(
            "explicit_step6a_request_received",
            (
                isinstance(
                    enablement_request_snapshot,
                    LiveOrderRealApprovalGateEnablementRequestSnapshot,
                )
                and enablement_request_snapshot.explicit_step6a_user_instruction_received
                is True
            ),
            "explicit Step 6A request is required",
            _bool_text(request_ready),
            "true",
        ),
        _check(
            "operator_acknowledgements_complete",
            request_ready,
            "operator acknowledgements must be complete",
            _bool_text(request_ready),
            "true",
        ),
        _check(
            "market_hours_source_sanitized_only",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.market_hours_source == MARKET_HOURS_SOURCE,
            "market-hours source must be sanitized snapshot only",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.market_hours_source == MARKET_HOURS_SOURCE,
            ),
            "true",
        ),
        _check(
            "timezone_asia_tokyo",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.timezone == MARKET_HOURS_TIMEZONE,
            "timezone must be Asia/Tokyo",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.timezone == MARKET_HOURS_TIMEZONE,
            ),
            "true",
        ),
        _check(
            "not_weekend",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.is_weekend_jst is False,
            "weekend must block",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.is_weekend_jst is False,
            ),
            "true",
        ),
        _check(
            "market_session_open",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.market_session_state == MARKET_HOURS_OPEN_STATE,
            "market session must be open",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.market_session_state == MARKET_HOURS_OPEN_STATE,
            ),
            "true",
        ),
        _check(
            "market_window_allowed",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.market_window_allowed is True,
            "market window must be allowed",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.market_window_allowed is True,
            ),
            "true",
        ),
        _check(
            "maintenance_inactive",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.broker_maintenance_active is False,
            "broker maintenance must be inactive",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.broker_maintenance_active is False,
            ),
            "true",
        ),
        _check(
            "market_hours_snapshot_fresh",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and (
                safety.market_hours_snapshot_age_seconds
                <= safety.market_hours_snapshot_max_age_seconds
            ),
            "market-hours snapshot must be fresh",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and (
                    safety.market_hours_snapshot_age_seconds
                    <= safety.market_hours_snapshot_max_age_seconds
                ),
            ),
            "true",
        ),
        _check(
            "fresh_pre_approval_preflight_source_sanitized_only",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.fresh_pre_approval_preflight_source == FRESH_PREFLIGHT_SOURCE,
            "fresh preflight source must be sanitized snapshot only",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.fresh_pre_approval_preflight_source
                == FRESH_PREFLIGHT_SOURCE
            ),
            "true",
        ),
        _check(
            "fresh_pre_approval_preflight_ready",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.fresh_pre_approval_preflight_status
            == FRESH_PREFLIGHT_READY_STATUS
            and safety.fresh_pre_approval_preflight_passed is True
            and safety.fresh_pre_approval_preflight_unknown is False,
            "fresh preflight must be ready and not unknown",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.fresh_pre_approval_preflight_status
                == FRESH_PREFLIGHT_READY_STATUS
                and safety.fresh_pre_approval_preflight_passed is True
                and safety.fresh_pre_approval_preflight_unknown is False
            ),
            "true",
        ),
        _check(
            "fresh_pre_approval_preflight_fresh",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and (
                safety.fresh_pre_approval_preflight_age_seconds
                <= safety.fresh_pre_approval_preflight_max_age_seconds
            ),
            "fresh preflight snapshot must be fresh",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and (
                    safety.fresh_pre_approval_preflight_age_seconds
                    <= safety.fresh_pre_approval_preflight_max_age_seconds
                ),
            ),
            "true",
        ),
        _check(
            "no_open_positions",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.open_positions_count == 0,
            "open positions must be zero",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.open_positions_count == 0,
            ),
            "true",
        ),
        _check(
            "no_active_orders",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.active_orders_count == 0,
            "active orders must be zero",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.active_orders_count == 0,
            ),
            "true",
        ),
        _check(
            "no_result_unknown",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.result_unknown is False,
            "result_unknown must be false",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.result_unknown is False,
            ),
            "true",
        ),
        _check(
            "raw_response_not_saved_or_displayed",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.raw_response_saved is False
            and safety.raw_response_displayed is False,
            "raw response must not be saved or displayed",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.raw_response_saved is False
                and safety.raw_response_displayed is False
            ),
            "true",
        ),
        _check(
            "secret_scan_passed",
            isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
            and safety.secret_scan_passed is True,
            "secret scan must pass",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalGateEnablementSafetySnapshot)
                and safety.secret_scan_passed is True,
            ),
            "true",
        ),
        _check(
            "approval_gate_enabled_true_model_output_only",
            approval_gate_enabled,
            "approval_gate_enabled may be true only as Step 6A model state",
            _bool_text(approval_gate_enabled),
            "true only when all checks pass",
        ),
        _check(
            "allowed_for_live_false",
            isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
            and plan.allowed_for_live is False,
            "allowed_for_live must remain false",
            _bool_text(
                isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
                and plan.allowed_for_live is False,
            ),
            "true",
        ),
        _check(
            "approval_gate_not_issued",
            isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
            and plan.approval_gate_issued is False,
            "Step 6A must not issue an approval gate",
            _bool_text(
                isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
                and plan.approval_gate_issued is False,
            ),
            "true",
        ),
        _check(
            "approval_id_not_generated",
            isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
            and plan.approval_id_generated is False,
            "Step 6A must not generate a real approval_id",
            _bool_text(
                isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
                and plan.approval_id_generated is False,
            ),
            "true",
        ),
        _check(
            "approval_command_not_generated",
            isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
            and plan.approval_command_generated is False,
            "Step 6A must not generate an approval command",
            _bool_text(
                isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
                and plan.approval_command_generated is False,
            ),
            "true",
        ),
        _check(
            "approval_command_not_copyable",
            isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
            and plan.approval_command_copyable is False,
            "Step 6A must not produce copyable approval text",
            _bool_text(
                isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
                and plan.approval_command_copyable is False,
            ),
            "true",
        ),
        _check(
            "approval_command_not_executable",
            isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
            and plan.approval_command_executable is False,
            "Step 6A must not produce executable approval text",
            _bool_text(
                isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
                and plan.approval_command_executable is False,
            ),
            "true",
        ),
        _check(
            "no_usable_approval_artifacts",
            isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
            and plan.usable_approval_artifacts_generated is False
            and plan.real_approval_artifacts_available is False,
            "Step 6A must not create usable real approval artifacts",
            _bool_text(
                isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
                and plan.usable_approval_artifacts_generated is False
                and plan.real_approval_artifacts_available is False
            ),
            "true",
        ),
        _check(
            "no_api_broker_live_order_once_called",
            no_api_called,
            "Step 6A must not call API, broker, or live_order_once",
            _bool_text(no_api_called),
            "true",
        ),
        _check(
            "post_not_allowed_this_step",
            True,
            "Step 6A never allows HTTP POST",
            "false",
            "false",
        ),
        _check(
            "post_not_executed",
            isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
            and plan.post_executed is False,
            "Step 6A must not execute HTTP POST",
            _bool_text(
                isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan)
                and plan.post_executed is False,
            ),
            "true",
        ),
        _check(
            "one_shot_constraints_preserved",
            one_shot_preserved,
            "one-shot constraints must stay preserved",
            _bool_text(one_shot_preserved),
            "true",
        ),
        _check(
            "future_step6b_handoff_conditions_present",
            bool(future_step6b_handoff_conditions),
            "future Step 6B handoff conditions must be present",
            _bool_text(bool(future_step6b_handoff_conditions)),
            "true",
        ),
        _check(
            "future_step6b_blockers_present",
            bool(future_step6b_blockers),
            "future Step 6B blockers must be present",
            _bool_text(bool(future_step6b_blockers)),
            "true",
        ),
        _check(
            "request_safety_and_plan_all_ready",
            plan_ready and request_ready and safety_ready,
            "plan, request, and safety snapshots must all be ready",
            _bool_text(plan_ready and request_ready and safety_ready),
            "true",
        ),
    )


def _build_sections(
    *,
    check_results: tuple[LiveOrderRealApprovalGateEnablementStateCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
    future_step6b_handoff_conditions: tuple[str, ...],
    future_step6b_blockers: tuple[str, ...],
) -> tuple[LiveOrderRealApprovalGateEnablementStateSection, ...]:
    return (
        LiveOrderRealApprovalGateEnablementStateSection(
            section_id="step6a_scope",
            title="Step 6A Scope",
            lines=(
                "approval_gate_enabled may be true only as sanitized model output",
                "allowed_for_live remains false",
                "no approval artifacts, API calls, or HTTP POST are performed",
            ),
        ),
        LiveOrderRealApprovalGateEnablementStateSection(
            section_id="blocked_reasons",
            title="Blocked Reasons",
            lines=blocked_reasons or ("none",),
        ),
        LiveOrderRealApprovalGateEnablementStateSection(
            section_id="check_results",
            title="Check Results",
            lines=tuple(
                f"{check.name}: passed={check.passed}, expected={check.expected}"
                for check in check_results
            ),
        ),
        LiveOrderRealApprovalGateEnablementStateSection(
            section_id="future_step6b_handoff",
            title="Future Step 6B Handoff",
            lines=future_step6b_handoff_conditions or ("missing",),
        ),
        LiveOrderRealApprovalGateEnablementStateSection(
            section_id="future_step6b_blockers",
            title="Future Step 6B Blockers",
            lines=future_step6b_blockers or ("missing",),
        ),
        LiveOrderRealApprovalGateEnablementStateSection(
            section_id="recommended_next_step",
            title="Recommended Next Step",
            lines=(recommended_next_step,),
        ),
    )


def _validate_state(state: LiveOrderRealApprovalGateEnablementState) -> None:
    _require_non_empty("enablement_state_id", state.enablement_state_id)
    if not state.enablement_state_id.startswith(
        LIVE_ORDER_REAL_APPROVAL_GATE_ENABLEMENT_STATE_ID_PREFIX,
    ):
        raise LiveVerificationValidationError("invalid enablement_state_id prefix")
    _ensure_aware(state.created_at)
    for label, value in (
        ("source_plan_id", state.source_plan_id),
        ("criteria_id", state.criteria_id),
        ("scaffold_id", state.scaffold_id),
        (
            "implementation_readiness_review_id",
            state.implementation_readiness_review_id,
        ),
        ("audit_id", state.audit_id),
        ("package_id", state.package_id),
        (
            "pre_approval_preflight_decision_id",
            state.pre_approval_preflight_decision_id,
        ),
        ("snapshot_id", state.snapshot_id),
        ("source_type", state.source_type),
        ("strategy_name", state.strategy_name),
        ("symbol", state.symbol),
        ("side", state.side),
        ("execution_type", state.execution_type),
        ("approval_gate_enablement_scope", state.approval_gate_enablement_scope),
        ("summary", state.summary),
        ("recommended_next_step", state.recommended_next_step),
    ):
        _require_non_empty(label, value)
    if state.enablement_state_ready:
        if state.symbol != SUPPORTED_SYMBOL:
            raise LiveVerificationValidationError("unsupported symbol")
        if state.side not in {
            LiveOrderCandidateSide.BUY.value,
            LiveOrderCandidateSide.SELL.value,
        }:
            raise LiveVerificationValidationError("unsupported side")
        if state.size != LIVE_ORDER_CANDIDATE_SIZE:
            raise LiveVerificationValidationError("unsupported size")
        if state.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
            raise LiveVerificationValidationError("unsupported execution_type")
    if state.allowed_for_live is not False:
        raise LiveVerificationValidationError("allowed_for_live must be False")
    for field_name in (
        "approval_gate_issued",
        "approval_id_generated",
        "approval_command_generated",
        "approval_command_copyable",
        "approval_command_executable",
        "usable_approval_artifacts_generated",
        "real_approval_artifacts_available",
        "post_allowed_this_step",
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
        if getattr(state, field_name) is not False:
            raise LiveVerificationValidationError(f"{field_name} must be False")
    for field_name in (
        "dry_run_only",
        "requires_human_approval",
        "explicit_user_confirmation_required",
        "fresh_preflight_before_enablement_required",
        "post_enablement_safety_review_required",
        "post_approval_final_dynamic_preflight_required",
        "one_shot_post_separate_step_required",
        "post_reconciliation_separate_step_required",
        "final_report_separate_step_required",
        "exact_match_required",
        "same_session_required",
        "post_reconciliation_required",
    ):
        if getattr(state, field_name) is not True:
            raise LiveVerificationValidationError(f"{field_name} must be True")
    if state.approval_gate_enablement_scope != APPROVAL_GATE_ENABLEMENT_SCOPE:
        raise LiveVerificationValidationError("invalid approval_gate_enablement_scope")
    if state.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("invalid ttl_seconds")
    if state.post_attempt_limit != 1:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if set(APPROVAL_ACK_TOKENS) - set(state.required_ack_tokens):
        raise LiveVerificationValidationError("missing required ACK token")
    if state.enablement_state_ready:
        if (
            state.enablement_status
            is not StateStatus.REAL_APPROVAL_GATE_ENABLED_NO_ARTIFACTS
        ):
            raise LiveVerificationValidationError("ready state has invalid status")
        if state.approval_gate_enabled is not True:
            raise LiveVerificationValidationError("ready state must enable gate state")
        if (
            state.eligible_for_future_step6b_approval_artifact_generation
            is not True
        ):
            raise LiveVerificationValidationError("ready state must be Step 6B eligible")
        if state.blocked_reasons:
            raise LiveVerificationValidationError("ready state cannot have blockers")
    else:
        if state.approval_gate_enabled is not False:
            raise LiveVerificationValidationError("blocked state must not enable gate")
        if (
            state.eligible_for_future_step6b_approval_artifact_generation
            is not False
        ):
            raise LiveVerificationValidationError("blocked state cannot be eligible")
    if state.enablement_state_ready and not state.future_step6b_handoff_conditions:
        raise LiveVerificationValidationError(
            "future_step6b_handoff_conditions required",
        )
    if state.enablement_state_ready and not state.future_step6b_blockers:
        raise LiveVerificationValidationError("future_step6b_blockers required")
    if not state.check_results:
        raise LiveVerificationValidationError("check_results required")
    if not state.sections:
        raise LiveVerificationValidationError("sections required")


def _request_or_empty(
    snapshot: LiveOrderRealApprovalGateEnablementRequestSnapshot | None,
    created_at: datetime,
) -> LiveOrderRealApprovalGateEnablementRequestSnapshot:
    if isinstance(snapshot, LiveOrderRealApprovalGateEnablementRequestSnapshot):
        return snapshot
    return LiveOrderRealApprovalGateEnablementRequestSnapshot(
        request_id="missing_step6a_request_snapshot",
        created_at=created_at,
        explicit_step6a_user_instruction_received=False,
        operator_understands_real_money_risk=False,
        operator_understands_no_post_in_step6a=False,
        operator_understands_no_approval_id_in_step6a=False,
        operator_understands_no_approval_command_in_step6a=False,
        operator_understands_no_copyable_text_in_step6a=False,
        operator_understands_unknown_means_stop=False,
        operator_understands_step6b_required_for_artifacts=False,
        operator_understands_step6c_or_later_required_for_api_preflight=False,
        operator_understands_step6d_or_later_required_for_post=False,
        request_scope_label="missing",
    )


def _safety_or_empty(
    snapshot: LiveOrderRealApprovalGateEnablementSafetySnapshot | None,
    created_at: datetime,
) -> LiveOrderRealApprovalGateEnablementSafetySnapshot:
    if isinstance(snapshot, LiveOrderRealApprovalGateEnablementSafetySnapshot):
        return snapshot
    return LiveOrderRealApprovalGateEnablementSafetySnapshot(
        safety_snapshot_id="missing_step6a_safety_snapshot",
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
        market_hours_snapshot_max_age_seconds=MARKET_HOURS_MAX_AGE_SECONDS,
        fresh_pre_approval_preflight_source="missing",
        fresh_pre_approval_preflight_status="UNKNOWN",
        fresh_pre_approval_preflight_passed=False,
        fresh_pre_approval_preflight_unknown=True,
        fresh_pre_approval_preflight_age_seconds=FRESH_PREFLIGHT_MAX_AGE_SECONDS + 1,
        fresh_pre_approval_preflight_max_age_seconds=FRESH_PREFLIGHT_MAX_AGE_SECONDS,
        open_positions_count=1,
        active_orders_count=1,
        result_unknown=True,
        raw_response_saved=True,
        raw_response_displayed=True,
        secret_scan_passed=False,
    )


def _source_plan_is_blocked(
    plan: LiveOrderRealApprovalEnablementDryRunPlan | None,
    plan_reasons: tuple[str, ...],
) -> bool:
    if not isinstance(plan, LiveOrderRealApprovalEnablementDryRunPlan):
        return True
    source_blockers = {
        BlockReason.SOURCE_PLAN_NOT_READY.value,
        BlockReason.SOURCE_PLAN_NOT_ELIGIBLE.value,
        BlockReason.MISSING_SOURCE_PLAN.value,
    }
    return bool(set(plan_reasons) & source_blockers or plan.blocked_reasons)


def _check(
    name: str,
    passed: bool,
    reason: str,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealApprovalGateEnablementStateCheckResult:
    return LiveOrderRealApprovalGateEnablementStateCheckResult(
        name=name,
        passed=passed,
        reason=reason,
        sanitized_value=sanitized_value,
        expected=expected,
    )


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    reasons: list[str] = []
    for group in reason_groups:
        for reason in group:
            _add_reason(reasons, reason)
    return tuple(reasons)


def _add_reason(
    reasons: list[str],
    reason: LiveOrderRealApprovalGateEnablementStateBlockReason | str,
) -> None:
    value = reason.value if isinstance(reason, BlockReason) else reason
    if value not in reasons:
        reasons.append(value)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _text_from(source: object, attr: str) -> str:
    value = getattr(source, attr, "missing")
    if value is None:
        return "missing"
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _int_from(source: object, attr: str) -> int:
    value = getattr(source, attr, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise LiveVerificationValidationError("datetime value required")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value


def _require_non_empty(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{label} must be non-empty")
