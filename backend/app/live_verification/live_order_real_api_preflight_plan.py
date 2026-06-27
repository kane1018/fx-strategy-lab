"""Step 6D dry-run real API preflight planning.

This module plans future API preflight checks from a validated Step 6C artifact.
It does not call APIs, read ledgers, issue approval gates, or authorize POST.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.live_order_real_approval_artifact_validation import (
    LiveOrderRealApprovalArtifactValidation,
    LiveOrderRealApprovalArtifactValidationStatus,
)
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    MARKET_HOURS_OPEN_STATE,
    MARKET_HOURS_SOURCE,
    MARKET_HOURS_TIMEZONE,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

ValidationStatus = LiveOrderRealApprovalArtifactValidationStatus

LIVE_ORDER_REAL_API_PREFLIGHT_PLAN_ID_PREFIX = "LORAPP6D-"
STEP6D_REQUEST_SCOPE_LABEL = "api_preflight_planning_only_no_real_api_no_post"
DEFAULT_STEP6D_SOURCE_VALIDATION_MAX_AGE_SECONDS = 300
DEFAULT_STEP6D_MARKET_HOURS_MAX_AGE_SECONDS = 30
PLANNED_CHECK_FUTURE_STEP = "Step 6E or later"
PLANNED_CHECK_API_CLASSIFICATION = "future_read_only_or_preflight_only"
RAW_RESPONSE_POLICY = "extract_sanitized_fields_only_no_save_no_display"
DISPLAY_POLICY = "sanitized_summary_only"
STORE_POLICY = "do_not_store_raw"

REQUIRED_PLANNED_CHECK_NAMES = (
    "market_hours_and_session_check",
    "account_asset_status_check",
    "open_positions_count_check",
    "active_orders_count_check",
    "instrument_rule_check",
    "ticker_spread_check",
    "ticker_age_check",
    "permission_scope_check",
    "ip_account_binding_check",
    "previous_result_unknown_check",
    "raw_response_handling_check",
)

DEFAULT_API_PREFLIGHT_GO_CONDITIONS = (
    "Step 6C validation ready",
    "explicit Step 6D planning request received",
    "approval_gate_enabled true from state-only flow",
    "allowed_for_live false",
    "no approval command full display",
    "no API called in Step 6D",
    "planned checks complete",
    "raw response handling policy safe",
    "market open in sanitized snapshot",
    "no weekend / maintenance / unknown",
    "future Step 6E explicit request still required",
)

DEFAULT_API_PREFLIGHT_NO_GO_CONDITIONS = (
    "Step 6C validation missing or blocked",
    "no explicit Step 6D request",
    "validation stale",
    "weekend / market closed / maintenance / unknown",
    "raw response display or save required",
    "credential/header/signature display required",
    "any API already called unexpectedly",
    "live_order_once already called",
    "post already executed",
    "approval command full display required",
    "retry/loop/add/change/cancel/close needed",
)

DEFAULT_API_PREFLIGHT_STOP_CONDITIONS = (
    "unknown status",
    "result_unknown",
    "stale validation",
    "stale market-hours snapshot",
    "exact match cannot be guaranteed",
    "same session cannot be guaranteed",
    "raw response cannot be kept hidden",
    "secret/header/signature exposure risk",
    "any need to exceed one POST attempt",
    "any need for retry/loop/add/change/cancel/close",
)

DEFAULT_FUTURE_STEP6E_HANDOFF_CONDITIONS = (
    "user explicitly requests Step 6E",
    "Step 6E is real API preflight execution only",
    "Step 6E remains no POST unless separately scoped",
    "Step 6E may call only approved read-only/preflight APIs",
    "Step 6E must not call order action endpoints",
    "Step 6E must not call live_order_once",
    "raw responses must not be saved or displayed",
    "only sanitized extracted fields may be reported",
    "open positions and active orders must be zero",
    "spread and ticker age must be within threshold",
    "result_unknown must stop",
    "allowed_for_live remains false unless a later controlled step explicitly changes it",
)

DEFAULT_FUTURE_STEP6E_BLOCKERS = (
    "no explicit Step 6E request",
    "Step 6D plan missing or blocked",
    "validation stale",
    "market closed/weekend/unknown",
    "approval artifact expired",
    "raw response handling policy unsafe",
    "any secret/header/signature exposure risk",
    "any POST-like endpoint required",
    "any retry/loop/add/change/cancel/close required",
)

DEFAULT_ALLOWED_DISPLAY_FIELDS = (
    "market_session_state",
    "market_window_allowed",
    "spread_jpy",
    "ticker_age_seconds",
    "open_positions_count",
    "active_orders_count",
    "instrument_min_order_size",
    "instrument_size_step",
    "permission_scope_checked",
    "ip_account_check_passed",
    "result_unknown",
)

DEFAULT_FORBIDDEN_DISPLAY_FIELDS = (
    "API key",
    "secret",
    "Authorization header",
    "request signing digest",
    "raw request",
    "raw response",
    "headers",
    "order ID",
    "execution ID",
    "position ID",
    "clientOrderId",
    "account number",
    "full API URL with credentials",
)

DEFAULT_ALLOWED_STORAGE_FIELDS = (
    "plan_id",
    "planned_check_names",
    "sanitized_check_results",
    "blocked_reasons",
)

DEFAULT_FORBIDDEN_STORAGE_FIELDS = DEFAULT_FORBIDDEN_DISPLAY_FIELDS


class LiveOrderRealApiPreflightPlanStatus(str, Enum):
    API_PREFLIGHT_PLAN_READY_NO_REAL_API_NO_POST = (
        "API_PREFLIGHT_PLAN_READY_NO_REAL_API_NO_POST"
    )
    BLOCKED_STEP6D_API_PREFLIGHT_PLAN_REQUEST = (
        "BLOCKED_STEP6D_API_PREFLIGHT_PLAN_REQUEST"
    )
    BLOCKED_STEP6D_API_PREFLIGHT_PLAN_SAFETY_SNAPSHOT = (
        "BLOCKED_STEP6D_API_PREFLIGHT_PLAN_SAFETY_SNAPSHOT"
    )
    BLOCKED_STEP6D_SOURCE_VALIDATION = "BLOCKED_STEP6D_SOURCE_VALIDATION"
    BLOCKED_STEP6D_UNSAFE_MISMATCH = "BLOCKED_STEP6D_UNSAFE_MISMATCH"


PlanStatus = LiveOrderRealApiPreflightPlanStatus


class LiveOrderRealApiPreflightPlanBlockReason(str, Enum):
    MISSING_SOURCE_VALIDATION = "missing_source_validation"
    SOURCE_VALIDATION_NOT_READY = "source_validation_not_ready"
    SOURCE_VALIDATION_NOT_ELIGIBLE = "source_validation_not_eligible"
    SOURCE_VALIDATION_ALLOWS_LIVE = "source_validation_allows_live"
    SOURCE_GATE_NOT_ENABLED = "source_gate_not_enabled"
    SOURCE_GATE_ALREADY_ISSUED = "source_gate_already_issued"
    SOURCE_APPROVAL_COMMAND_COPYABLE = "source_approval_command_copyable"
    SOURCE_APPROVAL_COMMAND_DISPLAYED = "source_approval_command_displayed"
    SOURCE_APPROVAL_COMMAND_PERSISTED = "source_approval_command_persisted"
    SOURCE_APPROVAL_COMMAND_COPIED_TO_CLIPBOARD = (
        "source_approval_command_copied_to_clipboard"
    )
    SOURCE_APPROVAL_COMMAND_EXECUTABLE = "source_approval_command_executable"
    SOURCE_POST_ALLOWED_THIS_STEP = "source_post_allowed_this_step"
    SOURCE_POST_ALREADY_EXECUTED = "source_post_already_executed"
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
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    MISSING_PLAN_REQUEST_SNAPSHOT = "missing_plan_request_snapshot"
    EXPLICIT_STEP6D_REQUEST_MISSING = "explicit_step6d_request_missing"
    OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED = (
        "operator_real_money_risk_not_acknowledged"
    )
    OPERATOR_NO_API_EXECUTION_NOT_ACKNOWLEDGED = (
        "operator_no_api_execution_not_acknowledged"
    )
    OPERATOR_NO_POST_NOT_ACKNOWLEDGED = "operator_no_post_not_acknowledged"
    OPERATOR_NO_LIVE_ORDER_ONCE_NOT_ACKNOWLEDGED = (
        "operator_no_live_order_once_not_acknowledged"
    )
    OPERATOR_PLANNING_ONLY_NOT_ACKNOWLEDGED = (
        "operator_planning_only_not_acknowledged"
    )
    OPERATOR_STEP6E_PREFLIGHT_NOT_ACKNOWLEDGED = (
        "operator_step6e_preflight_not_acknowledged"
    )
    OPERATOR_STEP6F_POST_NOT_ACKNOWLEDGED = "operator_step6f_post_not_acknowledged"
    OPERATOR_RAW_RESPONSE_POLICY_NOT_ACKNOWLEDGED = (
        "operator_raw_response_policy_not_acknowledged"
    )
    OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED = (
        "operator_unknown_means_stop_not_acknowledged"
    )
    INVALID_REQUEST_SCOPE_LABEL = "invalid_request_scope_label"
    MISSING_PLAN_SAFETY_SNAPSHOT = "missing_plan_safety_snapshot"
    SOURCE_VALIDATION_STALE = "source_validation_stale"
    SAFETY_GATE_NOT_ENABLED = "safety_gate_not_enabled"
    SAFETY_ARTIFACT_NOT_VALIDATED = "safety_artifact_not_validated"
    SAFETY_NOT_ELIGIBLE_FOR_STEP6D = "safety_not_eligible_for_step6d"
    SAFETY_ALLOWS_LIVE = "safety_allows_live"
    SAFETY_GATE_ALREADY_ISSUED = "safety_gate_already_issued"
    SAFETY_APPROVAL_COMMAND_COPYABLE = "safety_approval_command_copyable"
    SAFETY_APPROVAL_COMMAND_DISPLAYED = "safety_approval_command_displayed"
    SAFETY_APPROVAL_COMMAND_PERSISTED = "safety_approval_command_persisted"
    SAFETY_APPROVAL_COMMAND_COPIED_TO_CLIPBOARD = (
        "safety_approval_command_copied_to_clipboard"
    )
    SAFETY_APPROVAL_COMMAND_EXECUTABLE = "safety_approval_command_executable"
    INVALID_TIMEZONE = "invalid_timezone"
    INVALID_MARKET_HOURS_SOURCE = "invalid_market_hours_source"
    MARKET_SESSION_NOT_OPEN = "market_session_not_open"
    WEEKEND_JST = "weekend_jst"
    MARKET_WINDOW_NOT_ALLOWED = "market_window_not_allowed"
    BROKER_MAINTENANCE_ACTIVE = "broker_maintenance_active"
    HOLIDAY_OR_SPECIAL_CLOSE = "holiday_or_special_close"
    HOLIDAY_OR_SPECIAL_CLOSE_UNKNOWN = "holiday_or_special_close_unknown"
    MARKET_HOURS_UNKNOWN = "market_hours_unknown"
    MARKET_HOURS_SNAPSHOT_STALE = "market_hours_snapshot_stale"
    RAW_RESPONSE_SAVED = "raw_response_saved"
    RAW_RESPONSE_DISPLAYED = "raw_response_displayed"
    RAW_REQUEST_SAVED = "raw_request_saved"
    HEADERS_DISPLAYED = "headers_displayed"
    SIGNATURE_DISPLAYED = "signature_displayed"
    SECRET_SCAN_NOT_PASSED = "secret_scan_not_passed"
    GIT_NOT_CLEAN = "git_not_clean"
    TESTS_NOT_PASSED = "tests_not_passed"
    RUFF_NOT_PASSED = "ruff_not_passed"
    PLANNED_CHECKS_INCOMPLETE = "planned_checks_incomplete"
    UNSAFE_PLANNED_CHECK = "unsafe_planned_check"
    DATA_HANDLING_POLICY_UNSAFE = "data_handling_policy_unsafe"
    MISSING_API_PREFLIGHT_GO_CONDITIONS = "missing_api_preflight_go_conditions"
    MISSING_API_PREFLIGHT_NO_GO_CONDITIONS = "missing_api_preflight_no_go_conditions"
    MISSING_API_PREFLIGHT_STOP_CONDITIONS = "missing_api_preflight_stop_conditions"
    MISSING_FUTURE_STEP6E_HANDOFF_CONDITIONS = (
        "missing_future_step6e_handoff_conditions"
    )
    MISSING_FUTURE_STEP6E_BLOCKERS = "missing_future_step6e_blockers"


BlockReason = LiveOrderRealApiPreflightPlanBlockReason


@dataclass(frozen=True)
class LiveOrderRealApiPreflightPlanRequestSnapshot:
    request_id: str
    created_at: datetime
    explicit_step6d_user_instruction_received: bool
    operator_understands_real_money_risk: bool
    operator_understands_no_api_execution_in_step6d: bool
    operator_understands_no_post_in_step6d: bool
    operator_understands_no_live_order_once_in_step6d: bool
    operator_understands_planning_only: bool
    operator_understands_step6e_required_for_real_api_preflight: bool
    operator_understands_step6f_or_later_required_for_post: bool
    operator_understands_raw_response_not_saved_or_displayed: bool
    operator_understands_unknown_means_stop: bool
    request_scope_label: str

    def __post_init__(self) -> None:
        _require_non_empty("request_id", self.request_id)
        _ensure_aware(self.created_at)
        _require_non_empty("request_scope_label", self.request_scope_label)
        for field_name in (
            "explicit_step6d_user_instruction_received",
            "operator_understands_real_money_risk",
            "operator_understands_no_api_execution_in_step6d",
            "operator_understands_no_post_in_step6d",
            "operator_understands_no_live_order_once_in_step6d",
            "operator_understands_planning_only",
            "operator_understands_step6e_required_for_real_api_preflight",
            "operator_understands_step6f_or_later_required_for_post",
            "operator_understands_raw_response_not_saved_or_displayed",
            "operator_understands_unknown_means_stop",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")


@dataclass(frozen=True)
class LiveOrderRealApiPreflightPlanSafetySnapshot:
    safety_snapshot_id: str
    created_at: datetime
    source_validation_age_seconds: float
    source_validation_max_age_seconds: float
    approval_gate_enabled: bool
    approval_artifact_validated: bool
    eligible_for_step6d_api_preflight_planning: bool
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_command_copyable: bool
    approval_command_displayed: bool
    approval_command_persisted: bool
    approval_command_copied_to_clipboard: bool
    approval_command_executable: bool
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
    raw_response_saved: bool
    raw_response_displayed: bool
    raw_request_saved: bool
    headers_displayed: bool
    signature_displayed: bool
    secret_scan_passed: bool
    git_clean: bool
    tests_passed: bool
    ruff_passed: bool
    post_executed: bool
    live_order_once_called: bool
    private_api_called: bool
    broker_called: bool
    read_only_api_called: bool
    public_api_called: bool

    def __post_init__(self) -> None:
        _require_non_empty("safety_snapshot_id", self.safety_snapshot_id)
        _ensure_aware(self.created_at)
        for label, value in (
            ("timezone", self.timezone),
            ("market_hours_source", self.market_hours_source),
            ("market_session_state", self.market_session_state),
        ):
            _require_non_empty(label, value)
        for field_name in (
            "source_validation_age_seconds",
            "source_validation_max_age_seconds",
            "market_hours_snapshot_age_seconds",
            "market_hours_snapshot_max_age_seconds",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int | float) or isinstance(value, bool):
                raise LiveVerificationValidationError(f"{field_name} must be number")
        for field_name in (
            "approval_gate_enabled",
            "approval_artifact_validated",
            "eligible_for_step6d_api_preflight_planning",
            "allowed_for_live",
            "approval_gate_issued",
            "approval_command_copyable",
            "approval_command_displayed",
            "approval_command_persisted",
            "approval_command_copied_to_clipboard",
            "approval_command_executable",
            "is_weekend_jst",
            "market_window_allowed",
            "broker_maintenance_active",
            "holiday_or_special_close",
            "holiday_or_special_close_unknown",
            "market_hours_unknown",
            "raw_response_saved",
            "raw_response_displayed",
            "raw_request_saved",
            "headers_displayed",
            "signature_displayed",
            "secret_scan_passed",
            "git_clean",
            "tests_passed",
            "ruff_passed",
            "post_executed",
            "live_order_once_called",
            "private_api_called",
            "broker_called",
            "read_only_api_called",
            "public_api_called",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")


@dataclass(frozen=True)
class LiveOrderRealApiPreflightPlannedCheck:
    name: str
    purpose: str
    future_step: str
    data_category: str
    api_classification: str
    must_be_read_only: bool
    must_not_post: bool
    raw_response_policy: str
    display_policy: str
    store_policy: str
    success_condition: str
    fail_closed_condition: str

    def __post_init__(self) -> None:
        for label, value in (
            ("name", self.name),
            ("purpose", self.purpose),
            ("future_step", self.future_step),
            ("data_category", self.data_category),
            ("api_classification", self.api_classification),
            ("raw_response_policy", self.raw_response_policy),
            ("display_policy", self.display_policy),
            ("store_policy", self.store_policy),
            ("success_condition", self.success_condition),
            ("fail_closed_condition", self.fail_closed_condition),
        ):
            _require_non_empty(label, value)
        for field_name in ("must_be_read_only", "must_not_post"):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")


@dataclass(frozen=True)
class LiveOrderRealApiPreflightDataHandlingPolicy:
    raw_request_saved: bool
    raw_request_displayed: bool
    raw_response_saved: bool
    raw_response_displayed: bool
    headers_saved: bool
    headers_displayed: bool
    signature_saved: bool
    signature_displayed: bool
    order_id_display_allowed: bool
    execution_id_display_allowed: bool
    position_id_display_allowed: bool
    client_order_id_display_allowed: bool
    credential_display_allowed: bool
    credential_storage_allowed: bool
    sanitized_fields_only: bool
    allowed_display_fields: tuple[str, ...]
    forbidden_display_fields: tuple[str, ...]
    allowed_storage_fields: tuple[str, ...]
    forbidden_storage_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "raw_request_saved",
            "raw_request_displayed",
            "raw_response_saved",
            "raw_response_displayed",
            "headers_saved",
            "headers_displayed",
            "signature_saved",
            "signature_displayed",
            "order_id_display_allowed",
            "execution_id_display_allowed",
            "position_id_display_allowed",
            "client_order_id_display_allowed",
            "credential_display_allowed",
            "credential_storage_allowed",
            "sanitized_fields_only",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")
        for field_name in (
            "allowed_display_fields",
            "forbidden_display_fields",
            "allowed_storage_fields",
            "forbidden_storage_fields",
        ):
            values = getattr(self, field_name)
            if not values:
                raise LiveVerificationValidationError(f"{field_name} required")
            for value in values:
                _require_non_empty(field_name, value)


@dataclass(frozen=True)
class LiveOrderRealApiPreflightPlanCheckResult:
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
class LiveOrderRealApiPreflightPlanSection:
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
class LiveOrderRealApiPreflightPlan:
    plan_id: str
    created_at: datetime
    source_validation_id: str
    source_artifact_id: str
    source_enablement_state_id: str
    symbol: str
    side: str
    size: int
    execution_type: str
    source_type: str
    strategy_name: str
    plan_status: LiveOrderRealApiPreflightPlanStatus
    plan_ready: bool
    eligible_for_step6e_real_api_preflight_execution: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_artifact_validated: bool
    approval_gate_issued: bool
    approval_command_copyable: bool
    approval_command_displayed: bool
    approval_command_executable: bool
    api_preflight_planned: bool
    api_preflight_executed: bool
    real_api_execution_deferred_to_step6e: bool
    read_only_api_called: bool
    public_api_called: bool
    private_api_called: bool
    broker_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_attempt_limit: int
    post_executed: bool
    retry_allowed: bool
    loop_allowed: bool
    add_order_allowed: bool
    change_order_allowed: bool
    cancel_order_allowed: bool
    close_order_allowed: bool
    planned_checks: tuple[LiveOrderRealApiPreflightPlannedCheck, ...]
    data_handling_policy: LiveOrderRealApiPreflightDataHandlingPolicy
    api_preflight_go_conditions: tuple[str, ...]
    api_preflight_no_go_conditions: tuple[str, ...]
    api_preflight_stop_conditions: tuple[str, ...]
    future_step6e_handoff_conditions: tuple[str, ...]
    future_step6e_blockers: tuple[str, ...]
    request_snapshot: LiveOrderRealApiPreflightPlanRequestSnapshot
    safety_snapshot: LiveOrderRealApiPreflightPlanSafetySnapshot
    check_results: tuple[LiveOrderRealApiPreflightPlanCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApiPreflightPlanSection, ...]

    def __post_init__(self) -> None:
        _validate_plan(self)


@dataclass(frozen=True)
class LiveOrderRealApiPreflightPlanBuildResult:
    plan: LiveOrderRealApiPreflightPlan
    plan_id: str
    plan_status: LiveOrderRealApiPreflightPlanStatus
    plan_ready: bool
    eligible_for_step6e_real_api_preflight_execution: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_artifact_validated: bool
    approval_gate_issued: bool
    approval_command_copyable: bool
    approval_command_displayed: bool
    api_preflight_planned: bool
    api_preflight_executed: bool
    read_only_api_called: bool
    public_api_called: bool
    private_api_called: bool
    broker_called: bool
    live_order_once_called: bool
    post_allowed_this_step: bool
    post_executed: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.plan.plan_id != self.plan_id:
            raise LiveVerificationValidationError("plan_id mismatch")
        if self.plan.plan_status is not self.plan_status:
            raise LiveVerificationValidationError("plan_status mismatch")
        if self.plan.plan_ready is not self.plan_ready:
            raise LiveVerificationValidationError("plan_ready mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("allowed_for_live must be False")
        for field_name in (
            "approval_gate_issued",
            "approval_command_copyable",
            "approval_command_displayed",
            "api_preflight_executed",
            "read_only_api_called",
            "public_api_called",
            "private_api_called",
            "broker_called",
            "live_order_once_called",
            "post_allowed_this_step",
            "post_executed",
        ):
            if getattr(self, field_name) is not False:
                raise LiveVerificationValidationError(f"{field_name} must be False")
        if self.plan.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.plan.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_api_preflight_plan(
    *,
    source_validation: LiveOrderRealApprovalArtifactValidation | None,
    plan_request_snapshot: LiveOrderRealApiPreflightPlanRequestSnapshot | None,
    plan_safety_snapshot: LiveOrderRealApiPreflightPlanSafetySnapshot | None,
    created_at: datetime | None = None,
    planned_checks: tuple[
        LiveOrderRealApiPreflightPlannedCheck,
        ...,
    ] | None = None,
    data_handling_policy: LiveOrderRealApiPreflightDataHandlingPolicy | None = None,
    api_preflight_go_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_API_PREFLIGHT_GO_CONDITIONS,
    api_preflight_no_go_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_API_PREFLIGHT_NO_GO_CONDITIONS,
    api_preflight_stop_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_API_PREFLIGHT_STOP_CONDITIONS,
    future_step6e_handoff_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_FUTURE_STEP6E_HANDOFF_CONDITIONS,
    future_step6e_blockers: tuple[str, ...] = DEFAULT_FUTURE_STEP6E_BLOCKERS,
) -> LiveOrderRealApiPreflightPlanBuildResult:
    """Build a Step 6D API preflight plan without executing any API calls."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    checks = planned_checks or default_live_order_real_api_preflight_planned_checks()
    policy = data_handling_policy or default_live_order_real_api_preflight_data_policy()

    source_reasons = _source_validation_blocked_reasons(source_validation)
    request_reasons = _request_blocked_reasons(plan_request_snapshot)
    safety_reasons = _safety_blocked_reasons(plan_safety_snapshot)
    condition_reasons = _condition_blocked_reasons(
        planned_checks=checks,
        data_handling_policy=policy,
        api_preflight_go_conditions=api_preflight_go_conditions,
        api_preflight_no_go_conditions=api_preflight_no_go_conditions,
        api_preflight_stop_conditions=api_preflight_stop_conditions,
        future_step6e_handoff_conditions=future_step6e_handoff_conditions,
        future_step6e_blockers=future_step6e_blockers,
    )

    if _source_validation_is_missing_or_not_ready(source_validation, source_reasons):
        status = PlanStatus.BLOCKED_STEP6D_SOURCE_VALIDATION
        recommended_next_step = "fix_step6c_validation_blockers_no_api_no_post"
        summary = "blocked Step 6D plan by source Step 6C validation"
    elif request_reasons:
        status = PlanStatus.BLOCKED_STEP6D_API_PREFLIGHT_PLAN_REQUEST
        recommended_next_step = (
            "provide_explicit_step6d_request_and_acknowledgements_no_api_no_post"
        )
        summary = "blocked Step 6D plan by request acknowledgements"
    elif safety_reasons:
        status = PlanStatus.BLOCKED_STEP6D_API_PREFLIGHT_PLAN_SAFETY_SNAPSHOT
        recommended_next_step = "rerun_sanitized_step6d_safety_snapshot_no_api_no_post"
        summary = "blocked Step 6D plan by sanitized safety snapshot"
    elif source_reasons or condition_reasons:
        status = PlanStatus.BLOCKED_STEP6D_UNSAFE_MISMATCH
        recommended_next_step = "fix_step6d_unsafe_mismatch_no_api_no_post"
        summary = "blocked Step 6D plan by unsafe mismatch"
    else:
        status = PlanStatus.API_PREFLIGHT_PLAN_READY_NO_REAL_API_NO_POST
        recommended_next_step = (
            "stop_and_wait_for_explicit_step6e_real_api_preflight_execution_request_no_post"
        )
        summary = (
            "Step 6D planned future API preflight checks only; no API or POST "
            "was executed and live execution remains unavailable"
        )

    blocked_reasons = _merge_reasons(
        source_reasons,
        request_reasons,
        safety_reasons,
        condition_reasons,
    )
    ready = status is PlanStatus.API_PREFLIGHT_PLAN_READY_NO_REAL_API_NO_POST
    safe_request = _request_or_empty(plan_request_snapshot, created)
    safe_safety = _safety_or_empty(plan_safety_snapshot, created)
    validation = source_validation
    check_results = _build_check_results(
        source_validation=validation,
        request_snapshot=plan_request_snapshot,
        safety_snapshot=plan_safety_snapshot,
        planned_checks=checks,
        data_handling_policy=policy,
        api_preflight_go_conditions=api_preflight_go_conditions,
        api_preflight_no_go_conditions=api_preflight_no_go_conditions,
        api_preflight_stop_conditions=api_preflight_stop_conditions,
        future_step6e_handoff_conditions=future_step6e_handoff_conditions,
    )
    plan_id = make_live_order_real_api_preflight_plan_id(
        source_validation_id=_text_from(validation, "validation_id"),
        request_id=safe_request.request_id,
        safety_snapshot_id=safe_safety.safety_snapshot_id,
        created_at=created,
        plan_status=status,
        blocked_reasons=blocked_reasons,
    )
    plan = LiveOrderRealApiPreflightPlan(
        plan_id=plan_id,
        created_at=created,
        source_validation_id=_text_from(validation, "validation_id"),
        source_artifact_id=_text_from(validation, "source_artifact_id"),
        source_enablement_state_id=_text_from(
            validation,
            "source_enablement_state_id",
        ),
        symbol=_text_from(validation, "symbol"),
        side=_text_from(validation, "side"),
        size=_int_from(validation, "size"),
        execution_type=_text_from(validation, "execution_type"),
        source_type=_text_from(validation, "source_type"),
        strategy_name=_text_from(validation, "strategy_name"),
        plan_status=status,
        plan_ready=ready,
        eligible_for_step6e_real_api_preflight_execution=ready,
        allowed_for_live=False,
        approval_gate_enabled=ready,
        approval_artifact_validated=ready,
        approval_gate_issued=False,
        approval_command_copyable=False,
        approval_command_displayed=False,
        approval_command_executable=False,
        api_preflight_planned=ready,
        api_preflight_executed=False,
        real_api_execution_deferred_to_step6e=ready,
        read_only_api_called=False,
        public_api_called=False,
        private_api_called=False,
        broker_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_attempt_limit=1,
        post_executed=False,
        retry_allowed=False,
        loop_allowed=False,
        add_order_allowed=False,
        change_order_allowed=False,
        cancel_order_allowed=False,
        close_order_allowed=False,
        planned_checks=checks,
        data_handling_policy=policy,
        api_preflight_go_conditions=api_preflight_go_conditions,
        api_preflight_no_go_conditions=api_preflight_no_go_conditions,
        api_preflight_stop_conditions=api_preflight_stop_conditions,
        future_step6e_handoff_conditions=future_step6e_handoff_conditions,
        future_step6e_blockers=future_step6e_blockers,
        request_snapshot=safe_request,
        safety_snapshot=safe_safety,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            planned_checks=checks,
            data_handling_policy=policy,
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
            future_step6e_handoff_conditions=future_step6e_handoff_conditions,
            future_step6e_blockers=future_step6e_blockers,
        ),
    )
    return LiveOrderRealApiPreflightPlanBuildResult(
        plan=plan,
        plan_id=plan.plan_id,
        plan_status=plan.plan_status,
        plan_ready=plan.plan_ready,
        eligible_for_step6e_real_api_preflight_execution=(
            plan.eligible_for_step6e_real_api_preflight_execution
        ),
        allowed_for_live=False,
        approval_gate_enabled=plan.approval_gate_enabled,
        approval_artifact_validated=plan.approval_artifact_validated,
        approval_gate_issued=False,
        approval_command_copyable=False,
        approval_command_displayed=False,
        api_preflight_planned=plan.api_preflight_planned,
        api_preflight_executed=False,
        read_only_api_called=False,
        public_api_called=False,
        private_api_called=False,
        broker_called=False,
        live_order_once_called=False,
        post_allowed_this_step=False,
        post_executed=False,
        blocked_reasons=plan.blocked_reasons,
        recommended_next_step=plan.recommended_next_step,
    )


def default_live_order_real_api_preflight_planned_checks() -> tuple[
    LiveOrderRealApiPreflightPlannedCheck,
    ...,
]:
    return tuple(
        LiveOrderRealApiPreflightPlannedCheck(
            name=name,
            purpose=purpose,
            future_step=PLANNED_CHECK_FUTURE_STEP,
            data_category=data_category,
            api_classification=PLANNED_CHECK_API_CLASSIFICATION,
            must_be_read_only=True,
            must_not_post=True,
            raw_response_policy=RAW_RESPONSE_POLICY,
            display_policy=DISPLAY_POLICY,
            store_policy=STORE_POLICY,
            success_condition=success,
            fail_closed_condition=fail_closed,
        )
        for name, purpose, data_category, success, fail_closed in (
            (
                "market_hours_and_session_check",
                "confirm market session and maintenance state",
                "market_hours",
                "market open and not maintenance",
                "closed, stale, or unknown market state",
            ),
            (
                "account_asset_status_check",
                "confirm account asset endpoint is reachable in future step",
                "account",
                "account/assets success summarized only",
                "account/assets failure or unknown",
            ),
            (
                "open_positions_count_check",
                "confirm no open positions before any later action",
                "positions",
                "open_positions_count is zero",
                "open_positions_count nonzero or unknown",
            ),
            (
                "active_orders_count_check",
                "confirm no active orders before any later action",
                "orders",
                "active_orders_count is zero",
                "active_orders_count nonzero or unknown",
            ),
            (
                "instrument_rule_check",
                "confirm USD_JPY minimum size and step rules",
                "instrument_rules",
                "instrument min size and step support 100 units",
                "instrument rules missing, stale, or incompatible",
            ),
            (
                "ticker_spread_check",
                "confirm spread is within future threshold",
                "ticker",
                "spread_jpy within threshold",
                "spread unavailable, stale, or above threshold",
            ),
            (
                "ticker_age_check",
                "confirm ticker freshness",
                "ticker",
                "ticker_age_seconds within threshold",
                "ticker age unknown or stale",
            ),
            (
                "permission_scope_check",
                "confirm order permission scope before later execution planning",
                "permission",
                "permission scope checked and sanitized",
                "permission missing, unknown, or unsafe",
            ),
            (
                "ip_account_binding_check",
                "confirm IP/account restrictions before later execution planning",
                "account_controls",
                "IP/account binding checked and sanitized",
                "IP/account check missing, unknown, or unsafe",
            ),
            (
                "previous_result_unknown_check",
                "confirm no unresolved previous live result",
                "previous_result",
                "result_unknown is false",
                "result_unknown true or unknown",
            ),
            (
                "raw_response_handling_check",
                "confirm future raw response handling remains hidden",
                "data_handling",
                "raw responses extracted to sanitized fields only",
                "raw response display or save required",
            ),
        )
    )


def default_live_order_real_api_preflight_data_policy() -> (
    LiveOrderRealApiPreflightDataHandlingPolicy
):
    return LiveOrderRealApiPreflightDataHandlingPolicy(
        raw_request_saved=False,
        raw_request_displayed=False,
        raw_response_saved=False,
        raw_response_displayed=False,
        headers_saved=False,
        headers_displayed=False,
        signature_saved=False,
        signature_displayed=False,
        order_id_display_allowed=False,
        execution_id_display_allowed=False,
        position_id_display_allowed=False,
        client_order_id_display_allowed=False,
        credential_display_allowed=False,
        credential_storage_allowed=False,
        sanitized_fields_only=True,
        allowed_display_fields=DEFAULT_ALLOWED_DISPLAY_FIELDS,
        forbidden_display_fields=DEFAULT_FORBIDDEN_DISPLAY_FIELDS,
        allowed_storage_fields=DEFAULT_ALLOWED_STORAGE_FIELDS,
        forbidden_storage_fields=DEFAULT_FORBIDDEN_STORAGE_FIELDS,
    )


def render_live_order_real_api_preflight_plan_markdown(
    plan: LiveOrderRealApiPreflightPlan,
) -> str:
    """Render a sanitized Step 6D plan without raw data or executable commands."""
    blocked_text = ", ".join(plan.blocked_reasons) or "none"
    check_lines = "\n".join(
        (
            f"- {check.name}: future_step={check.future_step}, "
            f"must_be_read_only={check.must_be_read_only}, "
            f"must_not_post={check.must_not_post}, "
            f"raw_policy={check.raw_response_policy}"
        )
        for check in plan.planned_checks
    )
    result_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in plan.check_results
    )
    go_lines = "\n".join(f"- {item}" for item in plan.api_preflight_go_conditions)
    no_go_lines = "\n".join(f"- {item}" for item in plan.api_preflight_no_go_conditions)
    stop_lines = "\n".join(f"- {item}" for item in plan.api_preflight_stop_conditions)
    handoff_lines = "\n".join(
        f"- {item}" for item in plan.future_step6e_handoff_conditions
    )
    blocker_lines = "\n".join(f"- {item}" for item in plan.future_step6e_blockers)
    policy = plan.data_handling_policy
    return "\n".join(
        (
            "# Step 6D Real API Preflight Plan",
            "",
            "This Step 6D API preflight plan is dry-run only.",
            "This Step 6D plan does not call read-only API.",
            "This Step 6D plan does not call public API.",
            "This Step 6D plan does not call Private API.",
            "This Step 6D plan does not call broker code.",
            "This Step 6D plan does not call live_order_once.",
            "This Step 6D plan does not execute HTTP POST.",
            "This Step 6D plan does not authorize live POST.",
            "This Step 6D plan keeps allowed_for_live=false.",
            "This Step 6D plan does not display or save raw request/response.",
            "",
            f"plan_id: {plan.plan_id}",
            f"source_validation_id: {plan.source_validation_id}",
            f"source_artifact_id: {plan.source_artifact_id}",
            f"source_enablement_state_id: {plan.source_enablement_state_id}",
            f"source_type: {plan.source_type}",
            f"strategy_name: {plan.strategy_name}",
            f"symbol: {plan.symbol}",
            f"side: {plan.side}",
            f"size: {plan.size}",
            f"executionType: {plan.execution_type}",
            f"plan_status: {plan.plan_status.value}",
            f"plan_ready: {plan.plan_ready}",
            (
                "eligible_for_step6e_real_api_preflight_execution: "
                f"{plan.eligible_for_step6e_real_api_preflight_execution}"
            ),
            f"approval_gate_enabled: {plan.approval_gate_enabled}",
            f"allowed_for_live: {plan.allowed_for_live}",
            f"approval_gate_issued: {plan.approval_gate_issued}",
            f"approval_command_copyable: {plan.approval_command_copyable}",
            f"approval_command_displayed: {plan.approval_command_displayed}",
            f"api_preflight_planned: {plan.api_preflight_planned}",
            f"api_preflight_executed: {plan.api_preflight_executed}",
            (
                "real_api_execution_deferred_to_step6e: "
                f"{plan.real_api_execution_deferred_to_step6e}"
            ),
            f"post_allowed_this_step: {plan.post_allowed_this_step}",
            f"post_attempt_limit: {plan.post_attempt_limit}",
            f"post_executed: {plan.post_executed}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {plan.recommended_next_step}",
            "",
            "## Planned Checks",
            check_lines,
            "",
            "## Data Handling Policy",
            f"- sanitized_fields_only: {policy.sanitized_fields_only}",
            f"- raw_request_saved: {policy.raw_request_saved}",
            f"- raw_request_displayed: {policy.raw_request_displayed}",
            f"- raw_response_saved: {policy.raw_response_saved}",
            f"- raw_response_displayed: {policy.raw_response_displayed}",
            f"- headers_saved: {policy.headers_saved}",
            f"- headers_displayed: {policy.headers_displayed}",
            f"- signature_saved: {policy.signature_saved}",
            f"- signature_displayed: {policy.signature_displayed}",
            f"- credential_display_allowed: {policy.credential_display_allowed}",
            f"- credential_storage_allowed: {policy.credential_storage_allowed}",
            "",
            "## Go Conditions",
            go_lines,
            "",
            "## No-go Conditions",
            no_go_lines,
            "",
            "## Stop Conditions",
            stop_lines,
            "",
            "## Future Step 6E Handoff",
            handoff_lines,
            "",
            "## Future Step 6E Blockers",
            blocker_lines,
            "",
            "## Check Results",
            result_lines,
        ),
    )


def make_live_order_real_api_preflight_plan_id(
    *,
    source_validation_id: str,
    request_id: str,
    safety_snapshot_id: str,
    created_at: datetime,
    plan_status: LiveOrderRealApiPreflightPlanStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "blocked_reasons": list(blocked_reasons),
        "created_at": _ensure_aware(created_at).isoformat(),
        "plan_status": plan_status.value,
        "request_id": request_id,
        "safety_snapshot_id": safety_snapshot_id,
        "source_validation_id": source_validation_id,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_API_PREFLIGHT_PLAN_ID_PREFIX}{digest}"


def _source_validation_blocked_reasons(
    validation: LiveOrderRealApprovalArtifactValidation | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(validation, LiveOrderRealApprovalArtifactValidation):
        _add_reason(reasons, BlockReason.MISSING_SOURCE_VALIDATION)
        return tuple(reasons)
    if (
        validation.validation_status
        is not ValidationStatus.APPROVAL_ARTIFACT_VALIDATED_NO_API_NO_POST
        or validation.validation_ready is not True
    ):
        _add_reason(reasons, BlockReason.SOURCE_VALIDATION_NOT_READY)
    if validation.approval_artifact_validated is not True:
        _add_reason(reasons, BlockReason.SOURCE_VALIDATION_NOT_READY)
    if validation.eligible_for_step6d_api_preflight_planning is not True:
        _add_reason(reasons, BlockReason.SOURCE_VALIDATION_NOT_ELIGIBLE)
    if validation.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.SOURCE_VALIDATION_ALLOWS_LIVE)
    if validation.approval_gate_enabled is not True:
        _add_reason(reasons, BlockReason.SOURCE_GATE_NOT_ENABLED)
    for flag, reason in (
        (validation.approval_gate_issued, BlockReason.SOURCE_GATE_ALREADY_ISSUED),
        (
            validation.approval_command_copyable,
            BlockReason.SOURCE_APPROVAL_COMMAND_COPYABLE,
        ),
        (
            validation.approval_command_displayed,
            BlockReason.SOURCE_APPROVAL_COMMAND_DISPLAYED,
        ),
        (
            validation.approval_command_persisted,
            BlockReason.SOURCE_APPROVAL_COMMAND_PERSISTED,
        ),
        (
            validation.approval_command_copied_to_clipboard,
            BlockReason.SOURCE_APPROVAL_COMMAND_COPIED_TO_CLIPBOARD,
        ),
        (
            validation.approval_command_executable,
            BlockReason.SOURCE_APPROVAL_COMMAND_EXECUTABLE,
        ),
        (validation.post_allowed_this_step, BlockReason.SOURCE_POST_ALLOWED_THIS_STEP),
        (validation.post_executed, BlockReason.SOURCE_POST_ALREADY_EXECUTED),
        (validation.live_order_once_called, BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED),
        (validation.private_api_called, BlockReason.PRIVATE_API_ALREADY_CALLED),
        (validation.broker_called, BlockReason.BROKER_ALREADY_CALLED),
        (validation.read_only_api_called, BlockReason.READ_ONLY_API_ALREADY_CALLED),
        (validation.public_api_called, BlockReason.PUBLIC_API_ALREADY_CALLED),
        (validation.retry_allowed, BlockReason.RETRY_ALLOWED),
        (validation.loop_allowed, BlockReason.LOOP_ALLOWED),
        (validation.add_order_allowed, BlockReason.ADD_ORDER_ALLOWED),
        (validation.change_order_allowed, BlockReason.CHANGE_ORDER_ALLOWED),
        (validation.cancel_order_allowed, BlockReason.CANCEL_ORDER_ALLOWED),
        (validation.close_order_allowed, BlockReason.CLOSE_ORDER_ALLOWED),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    if validation.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SYMBOL)
    if validation.side not in {LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value}:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIDE)
    if validation.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIZE)
    if validation.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_EXECUTION_TYPE)
    return tuple(reasons)


def _request_blocked_reasons(
    snapshot: LiveOrderRealApiPreflightPlanRequestSnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(snapshot, LiveOrderRealApiPreflightPlanRequestSnapshot):
        _add_reason(reasons, BlockReason.MISSING_PLAN_REQUEST_SNAPSHOT)
        return tuple(reasons)
    for field_name, reason in (
        (
            "explicit_step6d_user_instruction_received",
            BlockReason.EXPLICIT_STEP6D_REQUEST_MISSING,
        ),
        (
            "operator_understands_real_money_risk",
            BlockReason.OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_api_execution_in_step6d",
            BlockReason.OPERATOR_NO_API_EXECUTION_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_post_in_step6d",
            BlockReason.OPERATOR_NO_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_live_order_once_in_step6d",
            BlockReason.OPERATOR_NO_LIVE_ORDER_ONCE_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_planning_only",
            BlockReason.OPERATOR_PLANNING_ONLY_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6e_required_for_real_api_preflight",
            BlockReason.OPERATOR_STEP6E_PREFLIGHT_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6f_or_later_required_for_post",
            BlockReason.OPERATOR_STEP6F_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_raw_response_not_saved_or_displayed",
            BlockReason.OPERATOR_RAW_RESPONSE_POLICY_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_unknown_means_stop",
            BlockReason.OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED,
        ),
    ):
        if getattr(snapshot, field_name) is not True:
            _add_reason(reasons, reason)
    if snapshot.request_scope_label != STEP6D_REQUEST_SCOPE_LABEL:
        _add_reason(reasons, BlockReason.INVALID_REQUEST_SCOPE_LABEL)
    return tuple(reasons)


def _safety_blocked_reasons(
    snapshot: LiveOrderRealApiPreflightPlanSafetySnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(snapshot, LiveOrderRealApiPreflightPlanSafetySnapshot):
        _add_reason(reasons, BlockReason.MISSING_PLAN_SAFETY_SNAPSHOT)
        return tuple(reasons)
    if snapshot.source_validation_age_seconds > snapshot.source_validation_max_age_seconds:
        _add_reason(reasons, BlockReason.SOURCE_VALIDATION_STALE)
    if snapshot.approval_gate_enabled is not True:
        _add_reason(reasons, BlockReason.SAFETY_GATE_NOT_ENABLED)
    if snapshot.approval_artifact_validated is not True:
        _add_reason(reasons, BlockReason.SAFETY_ARTIFACT_NOT_VALIDATED)
    if snapshot.eligible_for_step6d_api_preflight_planning is not True:
        _add_reason(reasons, BlockReason.SAFETY_NOT_ELIGIBLE_FOR_STEP6D)
    if snapshot.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.SAFETY_ALLOWS_LIVE)
    for flag, reason in (
        (snapshot.approval_gate_issued, BlockReason.SAFETY_GATE_ALREADY_ISSUED),
        (
            snapshot.approval_command_copyable,
            BlockReason.SAFETY_APPROVAL_COMMAND_COPYABLE,
        ),
        (
            snapshot.approval_command_displayed,
            BlockReason.SAFETY_APPROVAL_COMMAND_DISPLAYED,
        ),
        (
            snapshot.approval_command_persisted,
            BlockReason.SAFETY_APPROVAL_COMMAND_PERSISTED,
        ),
        (
            snapshot.approval_command_copied_to_clipboard,
            BlockReason.SAFETY_APPROVAL_COMMAND_COPIED_TO_CLIPBOARD,
        ),
        (
            snapshot.approval_command_executable,
            BlockReason.SAFETY_APPROVAL_COMMAND_EXECUTABLE,
        ),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
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
    for flag, reason in (
        (snapshot.raw_response_saved, BlockReason.RAW_RESPONSE_SAVED),
        (snapshot.raw_response_displayed, BlockReason.RAW_RESPONSE_DISPLAYED),
        (snapshot.raw_request_saved, BlockReason.RAW_REQUEST_SAVED),
        (snapshot.headers_displayed, BlockReason.HEADERS_DISPLAYED),
        (snapshot.signature_displayed, BlockReason.SIGNATURE_DISPLAYED),
        (snapshot.post_executed, BlockReason.SOURCE_POST_ALREADY_EXECUTED),
        (snapshot.live_order_once_called, BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED),
        (snapshot.private_api_called, BlockReason.PRIVATE_API_ALREADY_CALLED),
        (snapshot.broker_called, BlockReason.BROKER_ALREADY_CALLED),
        (snapshot.read_only_api_called, BlockReason.READ_ONLY_API_ALREADY_CALLED),
        (snapshot.public_api_called, BlockReason.PUBLIC_API_ALREADY_CALLED),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    for flag, reason in (
        (snapshot.secret_scan_passed, BlockReason.SECRET_SCAN_NOT_PASSED),
        (snapshot.git_clean, BlockReason.GIT_NOT_CLEAN),
        (snapshot.tests_passed, BlockReason.TESTS_NOT_PASSED),
        (snapshot.ruff_passed, BlockReason.RUFF_NOT_PASSED),
    ):
        if flag is not True:
            _add_reason(reasons, reason)
    return tuple(reasons)


def _condition_blocked_reasons(
    *,
    planned_checks: tuple[LiveOrderRealApiPreflightPlannedCheck, ...],
    data_handling_policy: LiveOrderRealApiPreflightDataHandlingPolicy,
    api_preflight_go_conditions: tuple[str, ...],
    api_preflight_no_go_conditions: tuple[str, ...],
    api_preflight_stop_conditions: tuple[str, ...],
    future_step6e_handoff_conditions: tuple[str, ...],
    future_step6e_blockers: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    check_names = {check.name for check in planned_checks}
    if not set(REQUIRED_PLANNED_CHECK_NAMES).issubset(check_names):
        _add_reason(reasons, BlockReason.PLANNED_CHECKS_INCOMPLETE)
    for check in planned_checks:
        if not _planned_check_is_safe(check):
            _add_reason(reasons, BlockReason.UNSAFE_PLANNED_CHECK)
            break
    if not _data_handling_policy_is_safe(data_handling_policy):
        _add_reason(reasons, BlockReason.DATA_HANDLING_POLICY_UNSAFE)
    if not api_preflight_go_conditions:
        _add_reason(reasons, BlockReason.MISSING_API_PREFLIGHT_GO_CONDITIONS)
    if not api_preflight_no_go_conditions:
        _add_reason(reasons, BlockReason.MISSING_API_PREFLIGHT_NO_GO_CONDITIONS)
    if not api_preflight_stop_conditions:
        _add_reason(reasons, BlockReason.MISSING_API_PREFLIGHT_STOP_CONDITIONS)
    if not future_step6e_handoff_conditions:
        _add_reason(reasons, BlockReason.MISSING_FUTURE_STEP6E_HANDOFF_CONDITIONS)
    if not future_step6e_blockers:
        _add_reason(reasons, BlockReason.MISSING_FUTURE_STEP6E_BLOCKERS)
    return tuple(reasons)


def _build_check_results(
    *,
    source_validation: LiveOrderRealApprovalArtifactValidation | None,
    request_snapshot: LiveOrderRealApiPreflightPlanRequestSnapshot | None,
    safety_snapshot: LiveOrderRealApiPreflightPlanSafetySnapshot | None,
    planned_checks: tuple[LiveOrderRealApiPreflightPlannedCheck, ...],
    data_handling_policy: LiveOrderRealApiPreflightDataHandlingPolicy,
    api_preflight_go_conditions: tuple[str, ...],
    api_preflight_no_go_conditions: tuple[str, ...],
    api_preflight_stop_conditions: tuple[str, ...],
    future_step6e_handoff_conditions: tuple[str, ...],
) -> tuple[LiveOrderRealApiPreflightPlanCheckResult, ...]:
    source_ready = not _source_validation_blocked_reasons(source_validation)
    request_ready = not _request_blocked_reasons(request_snapshot)
    planned_checks_complete = set(REQUIRED_PLANNED_CHECK_NAMES).issubset(
        {check.name for check in planned_checks},
    )
    raw_policy_safe = _data_handling_policy_is_safe(data_handling_policy)
    no_api_called = (
        isinstance(safety_snapshot, LiveOrderRealApiPreflightPlanSafetySnapshot)
        and all(
            getattr(safety_snapshot, field_name) is False
            for field_name in (
                "read_only_api_called",
                "public_api_called",
                "private_api_called",
                "broker_called",
                "live_order_once_called",
            )
        )
    )

    def check_bool(
        name: str,
        passed: bool,
        reason: str,
    ) -> LiveOrderRealApiPreflightPlanCheckResult:
        return _check(
            name,
            passed,
            reason,
            _bool_text(passed),
            "true",
        )

    def validation_bool(
        name: str,
        field_name: str,
        expected: bool,
        reason: str,
    ) -> LiveOrderRealApiPreflightPlanCheckResult:
        passed = _validation_flag(source_validation, field_name, expected)
        return check_bool(name, passed, reason)

    def safety_bool(
        name: str,
        field_name: str,
        expected: bool,
        reason: str,
    ) -> LiveOrderRealApiPreflightPlanCheckResult:
        passed = _safety_flag(safety_snapshot, field_name, expected)
        return check_bool(name, passed, reason)

    return (
        check_bool(
            "source_validation_ready",
            source_ready,
            "Step 6C validation ready",
        ),
        check_bool(
            "explicit_step6d_request_received",
            request_ready,
            "explicit Step 6D request is required",
        ),
        check_bool(
            "operator_acknowledgements_complete",
            request_ready,
            "operator acknowledgements are required",
        ),
        validation_bool(
            "approval_gate_enabled_true",
            "approval_gate_enabled",
            True,
            "approval_gate_enabled must be true from state-only flow",
        ),
        validation_bool(
            "allowed_for_live_false",
            "allowed_for_live",
            False,
            "allowed_for_live must remain false",
        ),
        validation_bool(
            "approval_gate_not_issued",
            "approval_gate_issued",
            False,
            "approval gate must not be issued",
        ),
        validation_bool(
            "approval_command_not_displayed",
            "approval_command_displayed",
            False,
            "approval command must not be displayed",
        ),
        validation_bool(
            "approval_command_not_copyable",
            "approval_command_copyable",
            False,
            "approval command must not be copyable",
        ),
        check_bool(
            "no_api_called_in_step6d",
            no_api_called,
            "Step 6D must not call any API",
        ),
        safety_bool(
            "no_read_only_api_called_in_step6d",
            "read_only_api_called",
            False,
            "Step 6D must not call read-only API",
        ),
        safety_bool(
            "no_public_api_called_in_step6d",
            "public_api_called",
            False,
            "Step 6D must not call public API",
        ),
        safety_bool(
            "no_private_api_called_in_step6d",
            "private_api_called",
            False,
            "Step 6D must not call Private API",
        ),
        safety_bool(
            "no_broker_called_in_step6d",
            "broker_called",
            False,
            "Step 6D must not call broker code",
        ),
        safety_bool(
            "no_live_order_once_called",
            "live_order_once_called",
            False,
            "Step 6D must not call live_order_once",
        ),
        validation_bool(
            "no_post_allowed_this_step",
            "post_allowed_this_step",
            False,
            "Step 6D must not allow POST",
        ),
        safety_bool(
            "no_post_executed",
            "post_executed",
            False,
            "Step 6D must not execute POST",
        ),
        check_bool(
            "raw_response_policy_safe",
            raw_policy_safe,
            "raw response policy must remain safe",
        ),
        check_bool(
            "headers_signature_policy_safe",
            raw_policy_safe,
            "headers and signature policy must remain safe",
        ),
        check_bool(
            "planned_checks_complete",
            planned_checks_complete,
            "planned checks must be complete",
        ),
        check_bool(
            "future_step6e_handoff_conditions_present",
            bool(future_step6e_handoff_conditions),
            "future Step 6E handoff conditions must be present",
        ),
        check_bool(
            "api_preflight_go_conditions_present",
            bool(api_preflight_go_conditions),
            "go conditions must be present",
        ),
        check_bool(
            "api_preflight_no_go_conditions_present",
            bool(api_preflight_no_go_conditions),
            "no-go conditions must be present",
        ),
        check_bool(
            "api_preflight_stop_conditions_present",
            bool(api_preflight_stop_conditions),
            "stop conditions must be present",
        ),
    )


def _build_sections(
    *,
    planned_checks: tuple[LiveOrderRealApiPreflightPlannedCheck, ...],
    data_handling_policy: LiveOrderRealApiPreflightDataHandlingPolicy,
    check_results: tuple[LiveOrderRealApiPreflightPlanCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
    future_step6e_handoff_conditions: tuple[str, ...],
    future_step6e_blockers: tuple[str, ...],
) -> tuple[LiveOrderRealApiPreflightPlanSection, ...]:
    return (
        LiveOrderRealApiPreflightPlanSection(
            section_id="step6d_scope",
            title="Step 6D Scope",
            lines=(
                "API preflight planning only",
                "allowed_for_live remains false",
                "no read-only/public/Private API is called",
                "no broker, live_order_once, ledger, or HTTP POST is performed",
            ),
        ),
        LiveOrderRealApiPreflightPlanSection(
            section_id="planned_checks",
            title="Planned Checks",
            lines=tuple(check.name for check in planned_checks),
        ),
        LiveOrderRealApiPreflightPlanSection(
            section_id="data_handling_policy",
            title="Data Handling Policy",
            lines=(
                f"sanitized_fields_only={data_handling_policy.sanitized_fields_only}",
                f"raw_response_saved={data_handling_policy.raw_response_saved}",
                f"raw_response_displayed={data_handling_policy.raw_response_displayed}",
            ),
        ),
        LiveOrderRealApiPreflightPlanSection(
            section_id="blocked_reasons",
            title="Blocked Reasons",
            lines=blocked_reasons or ("none",),
        ),
        LiveOrderRealApiPreflightPlanSection(
            section_id="check_results",
            title="Check Results",
            lines=tuple(
                f"{check.name}: passed={check.passed}, expected={check.expected}"
                for check in check_results
            ),
        ),
        LiveOrderRealApiPreflightPlanSection(
            section_id="future_step6e_handoff",
            title="Future Step 6E Handoff",
            lines=future_step6e_handoff_conditions or ("missing",),
        ),
        LiveOrderRealApiPreflightPlanSection(
            section_id="future_step6e_blockers",
            title="Future Step 6E Blockers",
            lines=future_step6e_blockers or ("missing",),
        ),
        LiveOrderRealApiPreflightPlanSection(
            section_id="recommended_next_step",
            title="Recommended Next Step",
            lines=(recommended_next_step,),
        ),
    )


def _validate_plan(plan: LiveOrderRealApiPreflightPlan) -> None:
    _require_non_empty("plan_id", plan.plan_id)
    if not plan.plan_id.startswith(LIVE_ORDER_REAL_API_PREFLIGHT_PLAN_ID_PREFIX):
        raise LiveVerificationValidationError("invalid plan_id prefix")
    _ensure_aware(plan.created_at)
    for label, value in (
        ("source_validation_id", plan.source_validation_id),
        ("source_artifact_id", plan.source_artifact_id),
        ("source_enablement_state_id", plan.source_enablement_state_id),
        ("symbol", plan.symbol),
        ("side", plan.side),
        ("execution_type", plan.execution_type),
        ("source_type", plan.source_type),
        ("strategy_name", plan.strategy_name),
        ("summary", plan.summary),
        ("recommended_next_step", plan.recommended_next_step),
    ):
        _require_non_empty(label, value)
    if plan.allowed_for_live is not False:
        raise LiveVerificationValidationError("allowed_for_live must be False")
    for field_name in (
        "approval_gate_issued",
        "approval_command_copyable",
        "approval_command_displayed",
        "approval_command_executable",
        "api_preflight_executed",
        "read_only_api_called",
        "public_api_called",
        "private_api_called",
        "broker_called",
        "live_order_once_called",
        "post_allowed_this_step",
        "post_executed",
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(plan, field_name) is not False:
            raise LiveVerificationValidationError(f"{field_name} must be False")
    if plan.post_attempt_limit != 1:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if not plan.planned_checks:
        raise LiveVerificationValidationError("planned_checks required")
    if not _data_handling_policy_is_safe(plan.data_handling_policy):
        raise LiveVerificationValidationError("unsafe data handling policy")
    for field_name in (
        "api_preflight_go_conditions",
        "api_preflight_no_go_conditions",
        "api_preflight_stop_conditions",
        "future_step6e_handoff_conditions",
        "future_step6e_blockers",
        "check_results",
        "sections",
    ):
        if not getattr(plan, field_name):
            raise LiveVerificationValidationError(f"{field_name} required")
    if plan.plan_ready:
        if plan.plan_status is not PlanStatus.API_PREFLIGHT_PLAN_READY_NO_REAL_API_NO_POST:
            raise LiveVerificationValidationError("ready plan has invalid status")
        for field_name in (
            "eligible_for_step6e_real_api_preflight_execution",
            "approval_gate_enabled",
            "approval_artifact_validated",
            "api_preflight_planned",
            "real_api_execution_deferred_to_step6e",
        ):
            if getattr(plan, field_name) is not True:
                raise LiveVerificationValidationError(f"{field_name} must be True")
        if plan.symbol != SUPPORTED_SYMBOL:
            raise LiveVerificationValidationError("unsupported symbol")
        if plan.side not in {LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value}:
            raise LiveVerificationValidationError("unsupported side")
        if plan.size != LIVE_ORDER_CANDIDATE_SIZE:
            raise LiveVerificationValidationError("unsupported size")
        if plan.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
            raise LiveVerificationValidationError("unsupported execution_type")
    else:
        for field_name in (
            "eligible_for_step6e_real_api_preflight_execution",
            "approval_gate_enabled",
            "approval_artifact_validated",
            "api_preflight_planned",
            "real_api_execution_deferred_to_step6e",
        ):
            if getattr(plan, field_name) is not False:
                raise LiveVerificationValidationError(f"{field_name} must be False")


def _planned_check_is_safe(check: LiveOrderRealApiPreflightPlannedCheck) -> bool:
    return (
        check.future_step == PLANNED_CHECK_FUTURE_STEP
        and check.api_classification == PLANNED_CHECK_API_CLASSIFICATION
        and check.must_be_read_only is True
        and check.must_not_post is True
        and check.raw_response_policy == RAW_RESPONSE_POLICY
        and check.display_policy == DISPLAY_POLICY
        and check.store_policy == STORE_POLICY
    )


def _data_handling_policy_is_safe(
    policy: LiveOrderRealApiPreflightDataHandlingPolicy,
) -> bool:
    false_fields = (
        "raw_request_saved",
        "raw_request_displayed",
        "raw_response_saved",
        "raw_response_displayed",
        "headers_saved",
        "headers_displayed",
        "signature_saved",
        "signature_displayed",
        "order_id_display_allowed",
        "execution_id_display_allowed",
        "position_id_display_allowed",
        "client_order_id_display_allowed",
        "credential_display_allowed",
        "credential_storage_allowed",
    )
    return (
        all(getattr(policy, field_name) is False for field_name in false_fields)
        and policy.sanitized_fields_only is True
        and bool(policy.allowed_display_fields)
        and bool(policy.forbidden_display_fields)
        and bool(policy.allowed_storage_fields)
        and bool(policy.forbidden_storage_fields)
    )


def _source_validation_is_missing_or_not_ready(
    validation: LiveOrderRealApprovalArtifactValidation | None,
    reasons: tuple[str, ...],
) -> bool:
    if not isinstance(validation, LiveOrderRealApprovalArtifactValidation):
        return True
    source_blocking = {
        BlockReason.MISSING_SOURCE_VALIDATION.value,
        BlockReason.SOURCE_VALIDATION_NOT_READY.value,
        BlockReason.SOURCE_VALIDATION_NOT_ELIGIBLE.value,
    }
    return bool(set(reasons) & source_blocking)


def _request_or_empty(
    snapshot: LiveOrderRealApiPreflightPlanRequestSnapshot | None,
    created_at: datetime,
) -> LiveOrderRealApiPreflightPlanRequestSnapshot:
    if isinstance(snapshot, LiveOrderRealApiPreflightPlanRequestSnapshot):
        return snapshot
    return LiveOrderRealApiPreflightPlanRequestSnapshot(
        request_id="missing",
        created_at=created_at,
        explicit_step6d_user_instruction_received=False,
        operator_understands_real_money_risk=False,
        operator_understands_no_api_execution_in_step6d=False,
        operator_understands_no_post_in_step6d=False,
        operator_understands_no_live_order_once_in_step6d=False,
        operator_understands_planning_only=False,
        operator_understands_step6e_required_for_real_api_preflight=False,
        operator_understands_step6f_or_later_required_for_post=False,
        operator_understands_raw_response_not_saved_or_displayed=False,
        operator_understands_unknown_means_stop=False,
        request_scope_label="missing",
    )


def _safety_or_empty(
    snapshot: LiveOrderRealApiPreflightPlanSafetySnapshot | None,
    created_at: datetime,
) -> LiveOrderRealApiPreflightPlanSafetySnapshot:
    if isinstance(snapshot, LiveOrderRealApiPreflightPlanSafetySnapshot):
        return snapshot
    return LiveOrderRealApiPreflightPlanSafetySnapshot(
        safety_snapshot_id="missing",
        created_at=created_at,
        source_validation_age_seconds=999999,
        source_validation_max_age_seconds=DEFAULT_STEP6D_SOURCE_VALIDATION_MAX_AGE_SECONDS,
        approval_gate_enabled=False,
        approval_artifact_validated=False,
        eligible_for_step6d_api_preflight_planning=False,
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_command_copyable=False,
        approval_command_displayed=False,
        approval_command_persisted=False,
        approval_command_copied_to_clipboard=False,
        approval_command_executable=False,
        timezone=MARKET_HOURS_TIMEZONE,
        market_hours_source=MARKET_HOURS_SOURCE,
        market_session_state="missing",
        is_weekend_jst=True,
        market_window_allowed=False,
        broker_maintenance_active=True,
        holiday_or_special_close=True,
        holiday_or_special_close_unknown=True,
        market_hours_unknown=True,
        market_hours_snapshot_age_seconds=999999,
        market_hours_snapshot_max_age_seconds=DEFAULT_STEP6D_MARKET_HOURS_MAX_AGE_SECONDS,
        raw_response_saved=True,
        raw_response_displayed=True,
        raw_request_saved=True,
        headers_displayed=True,
        signature_displayed=True,
        secret_scan_passed=False,
        git_clean=False,
        tests_passed=False,
        ruff_passed=False,
        post_executed=True,
        live_order_once_called=True,
        private_api_called=True,
        broker_called=True,
        read_only_api_called=True,
        public_api_called=True,
    )


def _check(
    name: str,
    passed: bool,
    reason: str,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealApiPreflightPlanCheckResult:
    return LiveOrderRealApiPreflightPlanCheckResult(
        name=name,
        passed=passed,
        reason=reason,
        sanitized_value=sanitized_value,
        expected=expected,
    )


def _validation_flag(
    validation: LiveOrderRealApprovalArtifactValidation | None,
    field_name: str,
    expected: bool,
) -> bool:
    return (
        isinstance(validation, LiveOrderRealApprovalArtifactValidation)
        and getattr(validation, field_name) is expected
    )


def _safety_flag(
    snapshot: LiveOrderRealApiPreflightPlanSafetySnapshot | None,
    field_name: str,
    expected: bool,
) -> bool:
    return (
        isinstance(snapshot, LiveOrderRealApiPreflightPlanSafetySnapshot)
        and getattr(snapshot, field_name) is expected
    )


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _add_reason(reasons: list[str], reason: LiveOrderRealApiPreflightPlanBlockReason) -> None:
    if reason.value not in reasons:
        reasons.append(reason.value)


def _require_non_empty(label: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{label} required")


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise LiveVerificationValidationError("datetime required")
    if value.tzinfo is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value


def _text_from(obj: object, field_name: str) -> str:
    value = getattr(obj, field_name, "missing")
    return value if isinstance(value, str) and value else "missing"


def _int_from(obj: object, field_name: str) -> int:
    value = getattr(obj, field_name, 0)
    return value if type(value) is int else 0


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
