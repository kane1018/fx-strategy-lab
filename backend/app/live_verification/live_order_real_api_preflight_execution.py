"""Step 6E real API preflight execution result model.

This module evaluates sanitized read-only/preflight results. It does not call
APIs, import broker code, import Private API clients, call live_order_once, or
authorize HTTP POST.
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
from app.live_verification.live_order_real_api_preflight_plan import (
    LiveOrderRealApiPreflightPlan,
    LiveOrderRealApiPreflightPlanStatus,
)
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    MARKET_HOURS_OPEN_STATE,
    MARKET_HOURS_TIMEZONE,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

PlanStatus = LiveOrderRealApiPreflightPlanStatus

LIVE_ORDER_REAL_API_PREFLIGHT_EXECUTION_ID_PREFIX = "LORAPE6E-"
STEP6E_REQUEST_SCOPE_LABEL = (
    "real_api_preflight_execution_read_only_only_no_post_no_raw_response"
)
PREFLIGHT_PASSED_SANITIZED_STATUS = "PREFLIGHT_PASSED_SANITIZED"
STEP6E_MAX_SPREAD_JPY = 0.01
STEP6E_MAX_TICKER_AGE_SECONDS = 30
STEP6E_MIN_TICKER_AGE_SECONDS = -5
STEP6E_ROUTE_TYPE = "read_only_or_preflight_sanitized"

DEFAULT_FUTURE_STEP6F_HANDOFF_CONDITIONS = (
    "user explicitly requests Step 6F",
    "Step 6F remains no HTTP POST unless separately scoped",
    "Step 6E preflight must still be fresh",
    "market-hours must be rechecked",
    "open positions and active orders must remain zero",
    "ticker spread and age must remain within limits",
    "raw response must remain undisplayed and unsaved",
    "allowed_for_live remains false unless a later controlled step explicitly changes it",
    "one-shot POST remains Step 6G or later",
)

DEFAULT_FUTURE_STEP6F_BLOCKERS = (
    "no explicit Step 6F request",
    "Step 6E preflight missing or blocked",
    "preflight stale",
    "market/preflight state stale or unknown",
    "open positions or active orders detected",
    "spread too wide",
    "ticker stale",
    "permission or IP/account binding failed",
    "raw response exposure risk",
    "any order endpoint called unexpectedly",
    "any need for retry/loop/add/change/cancel/close",
)

DEFAULT_EXECUTED_CHECK_NAMES = (
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


class LiveOrderRealApiPreflightExecutionStatus(str, Enum):
    REAL_API_PREFLIGHT_PASSED_NO_POST = "REAL_API_PREFLIGHT_PASSED_NO_POST"
    BLOCKED_STEP6E_PREFLIGHT_REQUEST = "BLOCKED_STEP6E_PREFLIGHT_REQUEST"
    BLOCKED_STEP6E_PREFLIGHT_ENVIRONMENT = "BLOCKED_STEP6E_PREFLIGHT_ENVIRONMENT"
    BLOCKED_STEP6E_SOURCE_PLAN = "BLOCKED_STEP6E_SOURCE_PLAN"
    BLOCKED_STEP6E_REAL_API_PREFLIGHT_RESULT = (
        "BLOCKED_STEP6E_REAL_API_PREFLIGHT_RESULT"
    )
    BLOCKED_STEP6E_UNSAFE_MISMATCH = "BLOCKED_STEP6E_UNSAFE_MISMATCH"


ExecutionStatus = LiveOrderRealApiPreflightExecutionStatus


class LiveOrderRealApiPreflightExecutionBlockReason(str, Enum):
    MISSING_SOURCE_PLAN = "missing_source_plan"
    SOURCE_PLAN_NOT_READY = "source_plan_not_ready"
    SOURCE_PLAN_NOT_ELIGIBLE = "source_plan_not_eligible"
    SOURCE_PLAN_ALLOWS_LIVE = "source_plan_allows_live"
    SOURCE_PLAN_PREFLIGHT_NOT_PLANNED = "source_plan_preflight_not_planned"
    SOURCE_PLAN_PREFLIGHT_ALREADY_EXECUTED = "source_plan_preflight_already_executed"
    SOURCE_PLAN_API_ALREADY_CALLED = "source_plan_api_already_called"
    SOURCE_PLAN_BROKER_ALREADY_CALLED = "source_plan_broker_already_called"
    SOURCE_PLAN_LIVE_ORDER_ONCE_ALREADY_CALLED = (
        "source_plan_live_order_once_already_called"
    )
    SOURCE_PLAN_POST_ALLOWED = "source_plan_post_allowed"
    SOURCE_PLAN_POST_ALREADY_EXECUTED = "source_plan_post_already_executed"
    SOURCE_PLAN_UNSUPPORTED_SYMBOL = "source_plan_unsupported_symbol"
    SOURCE_PLAN_UNSUPPORTED_SIDE = "source_plan_unsupported_side"
    SOURCE_PLAN_UNSUPPORTED_SIZE = "source_plan_unsupported_size"
    SOURCE_PLAN_UNSUPPORTED_EXECUTION_TYPE = "source_plan_unsupported_execution_type"
    MISSING_REQUEST_SNAPSHOT = "missing_request_snapshot"
    EXPLICIT_STEP6E_REQUEST_MISSING = "explicit_step6e_request_missing"
    OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED = (
        "operator_real_money_risk_not_acknowledged"
    )
    OPERATOR_READ_ONLY_PREFLIGHT_NOT_ACKNOWLEDGED = (
        "operator_read_only_preflight_not_acknowledged"
    )
    OPERATOR_NO_POST_NOT_ACKNOWLEDGED = "operator_no_post_not_acknowledged"
    OPERATOR_NO_ORDER_ENDPOINT_NOT_ACKNOWLEDGED = (
        "operator_no_order_endpoint_not_acknowledged"
    )
    OPERATOR_NO_LIVE_ORDER_ONCE_NOT_ACKNOWLEDGED = (
        "operator_no_live_order_once_not_acknowledged"
    )
    OPERATOR_NO_RAW_RESPONSE_DISPLAY_NOT_ACKNOWLEDGED = (
        "operator_no_raw_response_display_not_acknowledged"
    )
    OPERATOR_NO_RAW_RESPONSE_SAVE_NOT_ACKNOWLEDGED = (
        "operator_no_raw_response_save_not_acknowledged"
    )
    OPERATOR_STEP6F_NOT_ACKNOWLEDGED = "operator_step6f_not_acknowledged"
    OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED = (
        "operator_unknown_means_stop_not_acknowledged"
    )
    INVALID_REQUEST_SCOPE_LABEL = "invalid_request_scope_label"
    MISSING_ENVIRONMENT_CHECK = "missing_environment_check"
    GIT_NOT_CLEAN = "git_not_clean"
    TESTS_NOT_RECENTLY_PASSED = "tests_not_recently_passed"
    RUFF_NOT_RECENTLY_PASSED = "ruff_not_recently_passed"
    SECRET_SCAN_NOT_PASSED = "secret_scan_not_passed"
    INVALID_TIMEZONE = "invalid_timezone"
    WEEKEND_JST = "weekend_jst"
    MARKET_PREFILTER_FAILED = "market_prefilter_failed"
    SAFE_READ_ONLY_ROUTE_NOT_FOUND = "safe_read_only_route_not_found"
    SAFE_READ_ONLY_ROUTE_NO_POST_NOT_VERIFIED = (
        "safe_read_only_route_no_post_not_verified"
    )
    SAFE_READ_ONLY_ROUTE_NO_ORDER_ENDPOINT_NOT_VERIFIED = (
        "safe_read_only_route_no_order_endpoint_not_verified"
    )
    SAFE_READ_ONLY_ROUTE_NO_LIVE_ORDER_ONCE_NOT_VERIFIED = (
        "safe_read_only_route_no_live_order_once_not_verified"
    )
    SAFE_READ_ONLY_ROUTE_NO_RAW_OUTPUT_NOT_VERIFIED = (
        "safe_read_only_route_no_raw_output_not_verified"
    )
    SAFE_READ_ONLY_ROUTE_SANITIZED_ONLY_NOT_VERIFIED = (
        "safe_read_only_route_sanitized_only_not_verified"
    )
    ENV_VALUES_DISPLAYED = "env_values_displayed"
    ENV_FILE_DISPLAYED = "env_file_displayed"
    MISSING_SANITIZED_RESULT = "missing_sanitized_result"
    API_PREFLIGHT_NOT_EXECUTED = "api_preflight_not_executed"
    API_PREFLIGHT_STATUS_NOT_PASSED = "api_preflight_status_not_passed"
    MARKET_SESSION_NOT_OPEN = "market_session_not_open"
    MARKET_WINDOW_NOT_ALLOWED = "market_window_not_allowed"
    BROKER_MAINTENANCE_ACTIVE = "broker_maintenance_active"
    HOLIDAY_OR_SPECIAL_CLOSE = "holiday_or_special_close"
    MARKET_HOURS_UNKNOWN = "market_hours_unknown"
    ACCOUNT_ASSET_CHECK_FAILED = "account_asset_check_failed"
    OPEN_POSITIONS_NOT_ZERO = "open_positions_not_zero"
    ACTIVE_ORDERS_NOT_ZERO = "active_orders_not_zero"
    INSTRUMENT_SYMBOL_UNSUPPORTED = "instrument_symbol_unsupported"
    INSTRUMENT_MIN_SIZE_UNSUPPORTED = "instrument_min_size_unsupported"
    INSTRUMENT_SIZE_STEP_UNSUPPORTED = "instrument_size_step_unsupported"
    INSTRUMENT_RULE_CHECK_FAILED = "instrument_rule_check_failed"
    TICKER_SYMBOL_UNSUPPORTED = "ticker_symbol_unsupported"
    TICKER_SPREAD_TOO_WIDE = "ticker_spread_too_wide"
    TICKER_AGE_STALE = "ticker_age_stale"
    TICKER_CHECK_FAILED = "ticker_check_failed"
    PERMISSION_SCOPE_CHECK_FAILED = "permission_scope_check_failed"
    IP_ACCOUNT_BINDING_CHECK_FAILED = "ip_account_binding_check_failed"
    PREVIOUS_RESULT_UNKNOWN_CHECK_FAILED = "previous_result_unknown_check_failed"
    RAW_REQUEST_SAVED = "raw_request_saved"
    RAW_REQUEST_DISPLAYED = "raw_request_displayed"
    RAW_RESPONSE_SAVED = "raw_response_saved"
    RAW_RESPONSE_DISPLAYED = "raw_response_displayed"
    HEADERS_SAVED = "headers_saved"
    HEADERS_DISPLAYED = "headers_displayed"
    SIGNATURE_SAVED = "signature_saved"
    SIGNATURE_DISPLAYED = "signature_displayed"
    CREDENTIALS_DISPLAYED = "credentials_displayed"
    ORDER_IDS_DISPLAYED = "order_ids_displayed"
    EXECUTION_IDS_DISPLAYED = "execution_ids_displayed"
    POSITION_IDS_DISPLAYED = "position_ids_displayed"
    CLIENT_ORDER_IDS_DISPLAYED = "client_order_ids_displayed"
    EXECUTION_ALLOWS_LIVE = "execution_allows_live"
    ORDER_ENDPOINT_CALLED = "order_endpoint_called"
    ORDER_PAYLOAD_GENERATED = "order_payload_generated"
    ORDER_PAYLOAD_SENT = "order_payload_sent"
    LIVE_ORDER_ONCE_CALLED = "live_order_once_called"
    POST_ALLOWED_THIS_STEP = "post_allowed_this_step"
    POST_EXECUTED = "post_executed"
    RETRY_ALLOWED = "retry_allowed"
    LOOP_ALLOWED = "loop_allowed"
    ADD_ORDER_ALLOWED = "add_order_allowed"
    CHANGE_ORDER_ALLOWED = "change_order_allowed"
    CANCEL_ORDER_ALLOWED = "cancel_order_allowed"
    CLOSE_ORDER_ALLOWED = "close_order_allowed"
    MISSING_EXECUTED_CHECKS = "missing_executed_checks"
    MISSING_FUTURE_STEP6F_HANDOFF_CONDITIONS = (
        "missing_future_step6f_handoff_conditions"
    )
    MISSING_FUTURE_STEP6F_BLOCKERS = "missing_future_step6f_blockers"


BlockReason = LiveOrderRealApiPreflightExecutionBlockReason


@dataclass(frozen=True)
class LiveOrderRealApiPreflightExecutionRequestSnapshot:
    request_id: str
    created_at: datetime
    explicit_step6e_user_instruction_received: bool
    operator_understands_real_money_risk: bool
    operator_understands_read_only_preflight_only: bool
    operator_understands_no_post_in_step6e: bool
    operator_understands_no_order_endpoint_in_step6e: bool
    operator_understands_no_live_order_once_in_step6e: bool
    operator_understands_no_raw_response_display: bool
    operator_understands_no_raw_response_save: bool
    operator_understands_step6f_required_for_post_readiness: bool
    operator_understands_unknown_means_stop: bool
    request_scope_label: str

    def __post_init__(self) -> None:
        _require_non_empty("request_id", self.request_id)
        _ensure_aware(self.created_at)
        _require_non_empty("request_scope_label", self.request_scope_label)
        for field_name in (
            "explicit_step6e_user_instruction_received",
            "operator_understands_real_money_risk",
            "operator_understands_read_only_preflight_only",
            "operator_understands_no_post_in_step6e",
            "operator_understands_no_order_endpoint_in_step6e",
            "operator_understands_no_live_order_once_in_step6e",
            "operator_understands_no_raw_response_display",
            "operator_understands_no_raw_response_save",
            "operator_understands_step6f_required_for_post_readiness",
            "operator_understands_unknown_means_stop",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")


@dataclass(frozen=True)
class LiveOrderRealApiPreflightExecutionEnvironmentCheck:
    environment_check_id: str
    created_at: datetime
    git_clean: bool
    tests_recently_passed: bool
    ruff_recently_passed: bool
    secret_scan_passed: bool
    current_timezone: str
    is_weekend_jst: bool
    local_market_hours_prefilter_passed: bool
    safe_read_only_route_found: bool
    safe_read_only_route_name: str
    safe_read_only_route_verified_no_post: bool
    safe_read_only_route_verified_no_order_endpoint: bool
    safe_read_only_route_verified_no_live_order_once: bool
    safe_read_only_route_verified_no_raw_output: bool
    safe_read_only_route_verified_sanitized_output_only: bool
    env_values_displayed: bool
    env_file_displayed: bool

    def __post_init__(self) -> None:
        _require_non_empty("environment_check_id", self.environment_check_id)
        _ensure_aware(self.created_at)
        _require_non_empty("current_timezone", self.current_timezone)
        _require_non_empty("safe_read_only_route_name", self.safe_read_only_route_name)
        for field_name in (
            "git_clean",
            "tests_recently_passed",
            "ruff_recently_passed",
            "secret_scan_passed",
            "is_weekend_jst",
            "local_market_hours_prefilter_passed",
            "safe_read_only_route_found",
            "safe_read_only_route_verified_no_post",
            "safe_read_only_route_verified_no_order_endpoint",
            "safe_read_only_route_verified_no_live_order_once",
            "safe_read_only_route_verified_no_raw_output",
            "safe_read_only_route_verified_sanitized_output_only",
            "env_values_displayed",
            "env_file_displayed",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")


@dataclass(frozen=True)
class LiveOrderRealApiPreflightSanitizedResult:
    result_id: str
    created_at: datetime
    api_preflight_executed: bool
    api_preflight_route_name: str
    api_preflight_route_type: str
    api_preflight_result_status: str
    market_session_state: str
    market_window_allowed: bool
    broker_maintenance_active: bool
    holiday_or_special_close: bool
    market_hours_unknown: bool
    account_asset_status: str
    account_asset_check_passed: bool
    open_positions_count: int
    open_positions_check_passed: bool
    active_orders_count: int
    active_orders_check_passed: bool
    instrument_symbol: str
    instrument_min_open_order_size: int
    instrument_size_step: int
    instrument_rule_check_passed: bool
    ticker_symbol: str
    ticker_spread_jpy: float
    ticker_age_seconds: float
    ticker_check_passed: bool
    permission_scope_check_passed: bool
    ip_account_binding_check_passed: bool
    previous_result_unknown_check_passed: bool
    raw_request_saved: bool
    raw_request_displayed: bool
    raw_response_saved: bool
    raw_response_displayed: bool
    headers_saved: bool
    headers_displayed: bool
    signature_saved: bool
    signature_displayed: bool
    credentials_displayed: bool
    order_ids_displayed: bool
    execution_ids_displayed: bool
    position_ids_displayed: bool
    client_order_ids_displayed: bool

    def __post_init__(self) -> None:
        _require_non_empty("result_id", self.result_id)
        _ensure_aware(self.created_at)
        for label, value in (
            ("api_preflight_route_name", self.api_preflight_route_name),
            ("api_preflight_route_type", self.api_preflight_route_type),
            ("api_preflight_result_status", self.api_preflight_result_status),
            ("market_session_state", self.market_session_state),
            ("account_asset_status", self.account_asset_status),
            ("instrument_symbol", self.instrument_symbol),
            ("ticker_symbol", self.ticker_symbol),
        ):
            _require_non_empty(label, value)
        for field_name in (
            "open_positions_count",
            "active_orders_count",
            "instrument_min_open_order_size",
            "instrument_size_step",
        ):
            value = getattr(self, field_name)
            if type(value) is not int:
                raise LiveVerificationValidationError(f"{field_name} must be int")
        for field_name in ("ticker_spread_jpy", "ticker_age_seconds"):
            value = getattr(self, field_name)
            if not isinstance(value, int | float) or isinstance(value, bool):
                raise LiveVerificationValidationError(f"{field_name} must be number")
        for field_name in (
            "api_preflight_executed",
            "market_window_allowed",
            "broker_maintenance_active",
            "holiday_or_special_close",
            "market_hours_unknown",
            "account_asset_check_passed",
            "open_positions_check_passed",
            "active_orders_check_passed",
            "instrument_rule_check_passed",
            "ticker_check_passed",
            "permission_scope_check_passed",
            "ip_account_binding_check_passed",
            "previous_result_unknown_check_passed",
            "raw_request_saved",
            "raw_request_displayed",
            "raw_response_saved",
            "raw_response_displayed",
            "headers_saved",
            "headers_displayed",
            "signature_saved",
            "signature_displayed",
            "credentials_displayed",
            "order_ids_displayed",
            "execution_ids_displayed",
            "position_ids_displayed",
            "client_order_ids_displayed",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")


@dataclass(frozen=True)
class LiveOrderRealApiPreflightExecutedCheck:
    name: str
    api_preflight_route_name: str
    must_be_read_only: bool
    must_not_post: bool
    sanitized_only: bool
    raw_output_suppressed: bool

    def __post_init__(self) -> None:
        _require_non_empty("executed check name", self.name)
        _require_non_empty("api_preflight_route_name", self.api_preflight_route_name)
        for field_name in (
            "must_be_read_only",
            "must_not_post",
            "sanitized_only",
            "raw_output_suppressed",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")


@dataclass(frozen=True)
class LiveOrderRealApiPreflightExecutionCheckResult:
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
class LiveOrderRealApiPreflightExecutionSection:
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
class LiveOrderRealApiPreflightExecution:
    execution_id: str
    created_at: datetime
    source_plan_id: str
    source_validation_id: str
    source_artifact_id: str
    symbol: str
    side: str
    size: int
    execution_type: str
    execution_status: LiveOrderRealApiPreflightExecutionStatus
    execution_ready: bool
    api_preflight_executed: bool
    api_preflight_passed: bool
    eligible_for_step6f_post_readiness_planning: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_artifact_validated: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_validated: bool
    approval_command_displayed: bool
    approval_command_copyable: bool
    read_only_api_called: bool
    public_api_called: bool
    private_api_called: bool
    broker_called: bool
    order_endpoint_called: bool
    order_payload_generated: bool
    order_payload_sent: bool
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
    raw_request_saved: bool
    raw_request_displayed: bool
    raw_response_saved: bool
    raw_response_displayed: bool
    headers_saved: bool
    headers_displayed: bool
    signature_saved: bool
    signature_displayed: bool
    request_snapshot: LiveOrderRealApiPreflightExecutionRequestSnapshot
    environment_check: LiveOrderRealApiPreflightExecutionEnvironmentCheck
    sanitized_result: LiveOrderRealApiPreflightSanitizedResult
    executed_checks: tuple[LiveOrderRealApiPreflightExecutedCheck, ...]
    future_step6f_handoff_conditions: tuple[str, ...]
    future_step6f_blockers: tuple[str, ...]
    check_results: tuple[LiveOrderRealApiPreflightExecutionCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApiPreflightExecutionSection, ...]

    def __post_init__(self) -> None:
        _validate_execution(self)


@dataclass(frozen=True)
class LiveOrderRealApiPreflightExecutionBuildResult:
    execution: LiveOrderRealApiPreflightExecution
    execution_id: str
    execution_status: LiveOrderRealApiPreflightExecutionStatus
    execution_ready: bool
    api_preflight_executed: bool
    api_preflight_passed: bool
    eligible_for_step6f_post_readiness_planning: bool
    allowed_for_live: bool
    post_allowed_this_step: bool
    post_executed: bool
    order_endpoint_called: bool
    order_payload_generated: bool
    order_payload_sent: bool
    live_order_once_called: bool
    raw_response_saved: bool
    raw_response_displayed: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.execution.execution_id != self.execution_id:
            raise LiveVerificationValidationError("execution_id mismatch")
        if self.execution.execution_status is not self.execution_status:
            raise LiveVerificationValidationError("execution_status mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("allowed_for_live must be False")
        for field_name in (
            "post_allowed_this_step",
            "post_executed",
            "order_endpoint_called",
            "order_payload_generated",
            "order_payload_sent",
            "live_order_once_called",
            "raw_response_saved",
            "raw_response_displayed",
        ):
            if getattr(self, field_name) is not False:
                raise LiveVerificationValidationError(f"{field_name} must be False")
        if self.execution.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")


def build_live_order_real_api_preflight_execution(
    *,
    source_plan: LiveOrderRealApiPreflightPlan | None,
    request_snapshot: LiveOrderRealApiPreflightExecutionRequestSnapshot | None,
    environment_check: LiveOrderRealApiPreflightExecutionEnvironmentCheck | None,
    sanitized_result: LiveOrderRealApiPreflightSanitizedResult | None,
    created_at: datetime | None = None,
    executed_checks: tuple[
        LiveOrderRealApiPreflightExecutedCheck,
        ...,
    ] | None = None,
    future_step6f_handoff_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_FUTURE_STEP6F_HANDOFF_CONDITIONS,
    future_step6f_blockers: tuple[str, ...] = DEFAULT_FUTURE_STEP6F_BLOCKERS,
    allowed_for_live: bool = False,
    order_endpoint_called: bool = False,
    order_payload_generated: bool = False,
    order_payload_sent: bool = False,
    live_order_once_called: bool = False,
    post_allowed_this_step: bool = False,
    post_executed: bool = False,
    retry_allowed: bool = False,
    loop_allowed: bool = False,
    add_order_allowed: bool = False,
    change_order_allowed: bool = False,
    cancel_order_allowed: bool = False,
    close_order_allowed: bool = False,
) -> LiveOrderRealApiPreflightExecutionBuildResult:
    """Build a Step 6E result from sanitized inputs only."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    checks = executed_checks or default_live_order_real_api_preflight_executed_checks(
        sanitized_result,
    )
    source_reasons = _source_plan_blocked_reasons(source_plan)
    request_reasons = _request_blocked_reasons(request_snapshot)
    environment_reasons = _environment_blocked_reasons(environment_check)
    result_reasons = _sanitized_result_blocked_reasons(sanitized_result)
    unsafe_reasons = _unsafe_flag_reasons(
        allowed_for_live=allowed_for_live,
        order_endpoint_called=order_endpoint_called,
        order_payload_generated=order_payload_generated,
        order_payload_sent=order_payload_sent,
        live_order_once_called=live_order_once_called,
        post_allowed_this_step=post_allowed_this_step,
        post_executed=post_executed,
        retry_allowed=retry_allowed,
        loop_allowed=loop_allowed,
        add_order_allowed=add_order_allowed,
        change_order_allowed=change_order_allowed,
        cancel_order_allowed=cancel_order_allowed,
        close_order_allowed=close_order_allowed,
    )
    condition_reasons = _condition_blocked_reasons(
        executed_checks=checks,
        future_step6f_handoff_conditions=future_step6f_handoff_conditions,
        future_step6f_blockers=future_step6f_blockers,
    )

    if _source_plan_is_missing_or_not_ready(source_plan, source_reasons):
        status = ExecutionStatus.BLOCKED_STEP6E_SOURCE_PLAN
        recommended_next_step = "fix_step6d_preflight_plan_blockers_no_post"
        summary = "blocked Step 6E by source Step 6D plan"
    elif request_reasons:
        status = ExecutionStatus.BLOCKED_STEP6E_PREFLIGHT_REQUEST
        recommended_next_step = (
            "provide_explicit_step6e_request_and_acknowledgements_no_post"
        )
        summary = "blocked Step 6E by request acknowledgements"
    elif environment_reasons:
        status = ExecutionStatus.BLOCKED_STEP6E_PREFLIGHT_ENVIRONMENT
        recommended_next_step = "fix_environment_or_wait_for_market_open_no_post"
        summary = "blocked Step 6E by environment or route safety"
    elif result_reasons:
        status = ExecutionStatus.BLOCKED_STEP6E_REAL_API_PREFLIGHT_RESULT
        recommended_next_step = "inspect_sanitized_preflight_failures_no_post"
        summary = "blocked Step 6E by sanitized preflight result"
    elif source_reasons or unsafe_reasons or condition_reasons:
        status = ExecutionStatus.BLOCKED_STEP6E_UNSAFE_MISMATCH
        recommended_next_step = "fix_step6e_unsafe_mismatch_no_post"
        summary = "blocked Step 6E by unsafe mismatch"
    else:
        status = ExecutionStatus.REAL_API_PREFLIGHT_PASSED_NO_POST
        recommended_next_step = (
            "stop_and_wait_for_explicit_step6f_post_readiness_planning_request_no_post"
        )
        summary = (
            "Step 6E sanitized preflight passed; no order endpoint, "
            "live_order_once, or HTTP POST was authorized"
        )

    blocked_reasons = _merge_reasons(
        source_reasons,
        request_reasons,
        environment_reasons,
        result_reasons,
        unsafe_reasons,
        condition_reasons,
    )
    ready = status is ExecutionStatus.REAL_API_PREFLIGHT_PASSED_NO_POST
    safe_request = _request_or_empty(request_snapshot, created)
    safe_environment = _environment_or_empty(environment_check, created)
    safe_result = _result_or_empty(sanitized_result, created)
    check_results = _build_check_results(
        source_plan=source_plan,
        request_snapshot=request_snapshot,
        environment_check=environment_check,
        sanitized_result=sanitized_result,
        executed_checks=checks,
        future_step6f_handoff_conditions=future_step6f_handoff_conditions,
        unsafe_reasons=unsafe_reasons,
    )
    execution_id = make_live_order_real_api_preflight_execution_id(
        source_plan_id=_text_from(source_plan, "plan_id"),
        request_id=safe_request.request_id,
        environment_check_id=safe_environment.environment_check_id,
        result_id=safe_result.result_id,
        created_at=created,
        execution_status=status,
        blocked_reasons=blocked_reasons,
    )
    execution = LiveOrderRealApiPreflightExecution(
        execution_id=execution_id,
        created_at=created,
        source_plan_id=_text_from(source_plan, "plan_id"),
        source_validation_id=_text_from(source_plan, "source_validation_id"),
        source_artifact_id=_text_from(source_plan, "source_artifact_id"),
        symbol=_text_from(source_plan, "symbol"),
        side=_text_from(source_plan, "side"),
        size=_int_from(source_plan, "size"),
        execution_type=_text_from(source_plan, "execution_type"),
        execution_status=status,
        execution_ready=ready,
        api_preflight_executed=ready or (
            isinstance(sanitized_result, LiveOrderRealApiPreflightSanitizedResult)
            and sanitized_result.api_preflight_executed is True
        ),
        api_preflight_passed=ready,
        eligible_for_step6f_post_readiness_planning=ready,
        allowed_for_live=False,
        approval_gate_enabled=ready,
        approval_artifact_validated=ready,
        approval_gate_issued=False,
        approval_id_generated=ready,
        approval_command_generated=ready,
        approval_command_validated=ready,
        approval_command_displayed=False,
        approval_command_copyable=False,
        read_only_api_called=ready,
        public_api_called=False,
        private_api_called=False,
        broker_called=False,
        order_endpoint_called=False,
        order_payload_generated=False,
        order_payload_sent=False,
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
        raw_request_saved=False,
        raw_request_displayed=False,
        raw_response_saved=False,
        raw_response_displayed=False,
        headers_saved=False,
        headers_displayed=False,
        signature_saved=False,
        signature_displayed=False,
        request_snapshot=safe_request,
        environment_check=safe_environment,
        sanitized_result=safe_result,
        executed_checks=checks,
        future_step6f_handoff_conditions=future_step6f_handoff_conditions,
        future_step6f_blockers=future_step6f_blockers,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            sanitized_result=safe_result,
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
            future_step6f_handoff_conditions=future_step6f_handoff_conditions,
            future_step6f_blockers=future_step6f_blockers,
        ),
    )
    return LiveOrderRealApiPreflightExecutionBuildResult(
        execution=execution,
        execution_id=execution.execution_id,
        execution_status=execution.execution_status,
        execution_ready=execution.execution_ready,
        api_preflight_executed=execution.api_preflight_executed,
        api_preflight_passed=execution.api_preflight_passed,
        eligible_for_step6f_post_readiness_planning=(
            execution.eligible_for_step6f_post_readiness_planning
        ),
        allowed_for_live=False,
        post_allowed_this_step=False,
        post_executed=False,
        order_endpoint_called=False,
        order_payload_generated=False,
        order_payload_sent=False,
        live_order_once_called=False,
        raw_response_saved=False,
        raw_response_displayed=False,
        blocked_reasons=execution.blocked_reasons,
        recommended_next_step=execution.recommended_next_step,
    )


def default_live_order_real_api_preflight_executed_checks(
    sanitized_result: LiveOrderRealApiPreflightSanitizedResult | None,
) -> tuple[LiveOrderRealApiPreflightExecutedCheck, ...]:
    route_name = _text_from(sanitized_result, "api_preflight_route_name")
    return tuple(
        LiveOrderRealApiPreflightExecutedCheck(
            name=name,
            api_preflight_route_name=route_name,
            must_be_read_only=True,
            must_not_post=True,
            sanitized_only=True,
            raw_output_suppressed=True,
        )
        for name in DEFAULT_EXECUTED_CHECK_NAMES
    )


def render_live_order_real_api_preflight_execution_markdown(
    execution: LiveOrderRealApiPreflightExecution,
) -> str:
    """Render a sanitized Step 6E result without raw data or executable commands."""
    result = execution.sanitized_result
    blocked_text = ", ".join(execution.blocked_reasons) or "none"
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, "
            f"value={check.sanitized_value}, expected={check.expected}"
        )
        for check in execution.check_results
    )
    handoff_lines = "\n".join(
        f"- {item}" for item in execution.future_step6f_handoff_conditions
    )
    blocker_lines = "\n".join(f"- {item}" for item in execution.future_step6f_blockers)
    return "\n".join(
        (
            "# Step 6E Real API Preflight Execution",
            "",
            "This Step 6E real API preflight execution is read-only/preflight only.",
            "This Step 6E result does not authorize live POST.",
            "This Step 6E result keeps allowed_for_live=false.",
            "This Step 6E result does not call any order endpoint.",
            "This Step 6E result does not execute HTTP POST.",
            "This Step 6E result does not call live_order_once.",
            "This Step 6E renderer does not display raw request or raw response.",
            (
                "This Step 6E renderer does not display headers, signatures, "
                "credentials, or real order IDs."
            ),
            "",
            f"execution_id: {execution.execution_id}",
            f"source_plan_id: {execution.source_plan_id}",
            f"source_validation_id: {execution.source_validation_id}",
            f"source_artifact_id: {execution.source_artifact_id}",
            f"symbol: {execution.symbol}",
            f"side: {execution.side}",
            f"size: {execution.size}",
            f"executionType: {execution.execution_type}",
            f"execution_status: {execution.execution_status.value}",
            f"execution_ready: {execution.execution_ready}",
            f"api_preflight_executed: {execution.api_preflight_executed}",
            f"api_preflight_passed: {execution.api_preflight_passed}",
            (
                "eligible_for_step6f_post_readiness_planning: "
                f"{execution.eligible_for_step6f_post_readiness_planning}"
            ),
            f"allowed_for_live: {execution.allowed_for_live}",
            f"approval_gate_enabled: {execution.approval_gate_enabled}",
            f"approval_artifact_validated: {execution.approval_artifact_validated}",
            f"market_session_state: {result.market_session_state}",
            f"market_window_allowed: {result.market_window_allowed}",
            f"account_asset_status: {result.account_asset_status}",
            f"open_positions_count: {result.open_positions_count}",
            f"active_orders_count: {result.active_orders_count}",
            f"instrument_symbol: {result.instrument_symbol}",
            (
                "instrument_min_open_order_size: "
                f"{result.instrument_min_open_order_size}"
            ),
            f"instrument_size_step: {result.instrument_size_step}",
            f"ticker_symbol: {result.ticker_symbol}",
            f"ticker_spread_jpy: {result.ticker_spread_jpy}",
            f"ticker_age_seconds: {result.ticker_age_seconds}",
            (
                "permission_scope_check_passed: "
                f"{result.permission_scope_check_passed}"
            ),
            (
                "ip_account_binding_check_passed: "
                f"{result.ip_account_binding_check_passed}"
            ),
            (
                "previous_result_unknown_check_passed: "
                f"{result.previous_result_unknown_check_passed}"
            ),
            f"raw_request_saved: {execution.raw_request_saved}",
            f"raw_request_displayed: {execution.raw_request_displayed}",
            f"raw_response_saved: {execution.raw_response_saved}",
            f"raw_response_displayed: {execution.raw_response_displayed}",
            f"headers_saved: {execution.headers_saved}",
            f"headers_displayed: {execution.headers_displayed}",
            f"signature_saved: {execution.signature_saved}",
            f"signature_displayed: {execution.signature_displayed}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {execution.recommended_next_step}",
            "",
            "## Future Step 6F Handoff",
            handoff_lines,
            "",
            "## Future Step 6F Blockers",
            blocker_lines,
            "",
            "## Check Results",
            check_lines,
        ),
    )


def make_live_order_real_api_preflight_execution_id(
    *,
    source_plan_id: str,
    request_id: str,
    environment_check_id: str,
    result_id: str,
    created_at: datetime,
    execution_status: LiveOrderRealApiPreflightExecutionStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "blocked_reasons": list(blocked_reasons),
        "created_at": _ensure_aware(created_at).isoformat(),
        "environment_check_id": environment_check_id,
        "execution_status": execution_status.value,
        "request_id": request_id,
        "result_id": result_id,
        "source_plan_id": source_plan_id,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_API_PREFLIGHT_EXECUTION_ID_PREFIX}{digest}"


def _source_plan_blocked_reasons(
    plan: LiveOrderRealApiPreflightPlan | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(plan, LiveOrderRealApiPreflightPlan):
        _add_reason(reasons, BlockReason.MISSING_SOURCE_PLAN)
        return tuple(reasons)
    if (
        plan.plan_status is not PlanStatus.API_PREFLIGHT_PLAN_READY_NO_REAL_API_NO_POST
        or plan.plan_ready is not True
    ):
        _add_reason(reasons, BlockReason.SOURCE_PLAN_NOT_READY)
    if plan.eligible_for_step6e_real_api_preflight_execution is not True:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_NOT_ELIGIBLE)
    if plan.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_ALLOWS_LIVE)
    if plan.api_preflight_planned is not True:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_PREFLIGHT_NOT_PLANNED)
    if plan.api_preflight_executed is not False:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_PREFLIGHT_ALREADY_EXECUTED)
    if plan.read_only_api_called is not False or plan.public_api_called is not False:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_API_ALREADY_CALLED)
    if plan.private_api_called is not False:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_API_ALREADY_CALLED)
    if plan.broker_called is not False:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_BROKER_ALREADY_CALLED)
    if plan.live_order_once_called is not False:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_LIVE_ORDER_ONCE_ALREADY_CALLED)
    if plan.post_allowed_this_step is not False:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_POST_ALLOWED)
    if plan.post_executed is not False:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_POST_ALREADY_EXECUTED)
    if plan.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_UNSUPPORTED_SYMBOL)
    if plan.side not in {LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value}:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_UNSUPPORTED_SIDE)
    if plan.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_UNSUPPORTED_SIZE)
    if plan.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, BlockReason.SOURCE_PLAN_UNSUPPORTED_EXECUTION_TYPE)
    return tuple(reasons)


def _request_blocked_reasons(
    snapshot: LiveOrderRealApiPreflightExecutionRequestSnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(snapshot, LiveOrderRealApiPreflightExecutionRequestSnapshot):
        _add_reason(reasons, BlockReason.MISSING_REQUEST_SNAPSHOT)
        return tuple(reasons)
    for field_name, reason in (
        (
            "explicit_step6e_user_instruction_received",
            BlockReason.EXPLICIT_STEP6E_REQUEST_MISSING,
        ),
        (
            "operator_understands_real_money_risk",
            BlockReason.OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_read_only_preflight_only",
            BlockReason.OPERATOR_READ_ONLY_PREFLIGHT_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_post_in_step6e",
            BlockReason.OPERATOR_NO_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_order_endpoint_in_step6e",
            BlockReason.OPERATOR_NO_ORDER_ENDPOINT_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_live_order_once_in_step6e",
            BlockReason.OPERATOR_NO_LIVE_ORDER_ONCE_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_raw_response_display",
            BlockReason.OPERATOR_NO_RAW_RESPONSE_DISPLAY_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_raw_response_save",
            BlockReason.OPERATOR_NO_RAW_RESPONSE_SAVE_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6f_required_for_post_readiness",
            BlockReason.OPERATOR_STEP6F_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_unknown_means_stop",
            BlockReason.OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED,
        ),
    ):
        if getattr(snapshot, field_name) is not True:
            _add_reason(reasons, reason)
    if snapshot.request_scope_label != STEP6E_REQUEST_SCOPE_LABEL:
        _add_reason(reasons, BlockReason.INVALID_REQUEST_SCOPE_LABEL)
    return tuple(reasons)


def _environment_blocked_reasons(
    environment: LiveOrderRealApiPreflightExecutionEnvironmentCheck | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(environment, LiveOrderRealApiPreflightExecutionEnvironmentCheck):
        _add_reason(reasons, BlockReason.MISSING_ENVIRONMENT_CHECK)
        return tuple(reasons)
    for field_name, reason in (
        ("git_clean", BlockReason.GIT_NOT_CLEAN),
        ("tests_recently_passed", BlockReason.TESTS_NOT_RECENTLY_PASSED),
        ("ruff_recently_passed", BlockReason.RUFF_NOT_RECENTLY_PASSED),
        ("secret_scan_passed", BlockReason.SECRET_SCAN_NOT_PASSED),
    ):
        if getattr(environment, field_name) is not True:
            _add_reason(reasons, reason)
    if environment.current_timezone != MARKET_HOURS_TIMEZONE:
        _add_reason(reasons, BlockReason.INVALID_TIMEZONE)
    if environment.is_weekend_jst is not False:
        _add_reason(reasons, BlockReason.WEEKEND_JST)
    if environment.local_market_hours_prefilter_passed is not True:
        _add_reason(reasons, BlockReason.MARKET_PREFILTER_FAILED)
    for field_name, reason in (
        ("safe_read_only_route_found", BlockReason.SAFE_READ_ONLY_ROUTE_NOT_FOUND),
        (
            "safe_read_only_route_verified_no_post",
            BlockReason.SAFE_READ_ONLY_ROUTE_NO_POST_NOT_VERIFIED,
        ),
        (
            "safe_read_only_route_verified_no_order_endpoint",
            BlockReason.SAFE_READ_ONLY_ROUTE_NO_ORDER_ENDPOINT_NOT_VERIFIED,
        ),
        (
            "safe_read_only_route_verified_no_live_order_once",
            BlockReason.SAFE_READ_ONLY_ROUTE_NO_LIVE_ORDER_ONCE_NOT_VERIFIED,
        ),
        (
            "safe_read_only_route_verified_no_raw_output",
            BlockReason.SAFE_READ_ONLY_ROUTE_NO_RAW_OUTPUT_NOT_VERIFIED,
        ),
        (
            "safe_read_only_route_verified_sanitized_output_only",
            BlockReason.SAFE_READ_ONLY_ROUTE_SANITIZED_ONLY_NOT_VERIFIED,
        ),
    ):
        if getattr(environment, field_name) is not True:
            _add_reason(reasons, reason)
    if environment.env_values_displayed is not False:
        _add_reason(reasons, BlockReason.ENV_VALUES_DISPLAYED)
    if environment.env_file_displayed is not False:
        _add_reason(reasons, BlockReason.ENV_FILE_DISPLAYED)
    return tuple(reasons)


def _sanitized_result_blocked_reasons(
    result: LiveOrderRealApiPreflightSanitizedResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(result, LiveOrderRealApiPreflightSanitizedResult):
        _add_reason(reasons, BlockReason.MISSING_SANITIZED_RESULT)
        return tuple(reasons)
    if result.api_preflight_executed is not True:
        _add_reason(reasons, BlockReason.API_PREFLIGHT_NOT_EXECUTED)
    if result.api_preflight_result_status != PREFLIGHT_PASSED_SANITIZED_STATUS:
        _add_reason(reasons, BlockReason.API_PREFLIGHT_STATUS_NOT_PASSED)
    if result.market_session_state != MARKET_HOURS_OPEN_STATE:
        _add_reason(reasons, BlockReason.MARKET_SESSION_NOT_OPEN)
    if result.market_window_allowed is not True:
        _add_reason(reasons, BlockReason.MARKET_WINDOW_NOT_ALLOWED)
    if result.broker_maintenance_active is not False:
        _add_reason(reasons, BlockReason.BROKER_MAINTENANCE_ACTIVE)
    if result.holiday_or_special_close is not False:
        _add_reason(reasons, BlockReason.HOLIDAY_OR_SPECIAL_CLOSE)
    if result.market_hours_unknown is not False:
        _add_reason(reasons, BlockReason.MARKET_HOURS_UNKNOWN)
    if result.account_asset_check_passed is not True:
        _add_reason(reasons, BlockReason.ACCOUNT_ASSET_CHECK_FAILED)
    if result.open_positions_count != 0 or result.open_positions_check_passed is not True:
        _add_reason(reasons, BlockReason.OPEN_POSITIONS_NOT_ZERO)
    if result.active_orders_count != 0 or result.active_orders_check_passed is not True:
        _add_reason(reasons, BlockReason.ACTIVE_ORDERS_NOT_ZERO)
    if result.instrument_symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, BlockReason.INSTRUMENT_SYMBOL_UNSUPPORTED)
    if result.instrument_min_open_order_size > LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, BlockReason.INSTRUMENT_MIN_SIZE_UNSUPPORTED)
    if result.instrument_size_step != 1:
        _add_reason(reasons, BlockReason.INSTRUMENT_SIZE_STEP_UNSUPPORTED)
    if result.instrument_rule_check_passed is not True:
        _add_reason(reasons, BlockReason.INSTRUMENT_RULE_CHECK_FAILED)
    if result.ticker_symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, BlockReason.TICKER_SYMBOL_UNSUPPORTED)
    if result.ticker_spread_jpy > STEP6E_MAX_SPREAD_JPY:
        _add_reason(reasons, BlockReason.TICKER_SPREAD_TOO_WIDE)
    if (
        result.ticker_age_seconds > STEP6E_MAX_TICKER_AGE_SECONDS
        or result.ticker_age_seconds < STEP6E_MIN_TICKER_AGE_SECONDS
    ):
        _add_reason(reasons, BlockReason.TICKER_AGE_STALE)
    if result.ticker_check_passed is not True:
        _add_reason(reasons, BlockReason.TICKER_CHECK_FAILED)
    if result.permission_scope_check_passed is not True:
        _add_reason(reasons, BlockReason.PERMISSION_SCOPE_CHECK_FAILED)
    if result.ip_account_binding_check_passed is not True:
        _add_reason(reasons, BlockReason.IP_ACCOUNT_BINDING_CHECK_FAILED)
    if result.previous_result_unknown_check_passed is not True:
        _add_reason(reasons, BlockReason.PREVIOUS_RESULT_UNKNOWN_CHECK_FAILED)
    for flag, reason in (
        (result.raw_request_saved, BlockReason.RAW_REQUEST_SAVED),
        (result.raw_request_displayed, BlockReason.RAW_REQUEST_DISPLAYED),
        (result.raw_response_saved, BlockReason.RAW_RESPONSE_SAVED),
        (result.raw_response_displayed, BlockReason.RAW_RESPONSE_DISPLAYED),
        (result.headers_saved, BlockReason.HEADERS_SAVED),
        (result.headers_displayed, BlockReason.HEADERS_DISPLAYED),
        (result.signature_saved, BlockReason.SIGNATURE_SAVED),
        (result.signature_displayed, BlockReason.SIGNATURE_DISPLAYED),
        (result.credentials_displayed, BlockReason.CREDENTIALS_DISPLAYED),
        (result.order_ids_displayed, BlockReason.ORDER_IDS_DISPLAYED),
        (result.execution_ids_displayed, BlockReason.EXECUTION_IDS_DISPLAYED),
        (result.position_ids_displayed, BlockReason.POSITION_IDS_DISPLAYED),
        (result.client_order_ids_displayed, BlockReason.CLIENT_ORDER_IDS_DISPLAYED),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    return tuple(reasons)


def _unsafe_flag_reasons(
    *,
    allowed_for_live: bool,
    order_endpoint_called: bool,
    order_payload_generated: bool,
    order_payload_sent: bool,
    live_order_once_called: bool,
    post_allowed_this_step: bool,
    post_executed: bool,
    retry_allowed: bool,
    loop_allowed: bool,
    add_order_allowed: bool,
    change_order_allowed: bool,
    cancel_order_allowed: bool,
    close_order_allowed: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for flag, reason in (
        (allowed_for_live, BlockReason.EXECUTION_ALLOWS_LIVE),
        (order_endpoint_called, BlockReason.ORDER_ENDPOINT_CALLED),
        (order_payload_generated, BlockReason.ORDER_PAYLOAD_GENERATED),
        (order_payload_sent, BlockReason.ORDER_PAYLOAD_SENT),
        (live_order_once_called, BlockReason.LIVE_ORDER_ONCE_CALLED),
        (post_allowed_this_step, BlockReason.POST_ALLOWED_THIS_STEP),
        (post_executed, BlockReason.POST_EXECUTED),
        (retry_allowed, BlockReason.RETRY_ALLOWED),
        (loop_allowed, BlockReason.LOOP_ALLOWED),
        (add_order_allowed, BlockReason.ADD_ORDER_ALLOWED),
        (change_order_allowed, BlockReason.CHANGE_ORDER_ALLOWED),
        (cancel_order_allowed, BlockReason.CANCEL_ORDER_ALLOWED),
        (close_order_allowed, BlockReason.CLOSE_ORDER_ALLOWED),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    return tuple(reasons)


def _condition_blocked_reasons(
    *,
    executed_checks: tuple[LiveOrderRealApiPreflightExecutedCheck, ...],
    future_step6f_handoff_conditions: tuple[str, ...],
    future_step6f_blockers: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    check_names = {check.name for check in executed_checks}
    if not set(DEFAULT_EXECUTED_CHECK_NAMES).issubset(check_names):
        _add_reason(reasons, BlockReason.MISSING_EXECUTED_CHECKS)
    for check in executed_checks:
        if not _executed_check_is_safe(check):
            _add_reason(reasons, BlockReason.MISSING_EXECUTED_CHECKS)
            break
    if not future_step6f_handoff_conditions:
        _add_reason(reasons, BlockReason.MISSING_FUTURE_STEP6F_HANDOFF_CONDITIONS)
    if not future_step6f_blockers:
        _add_reason(reasons, BlockReason.MISSING_FUTURE_STEP6F_BLOCKERS)
    return tuple(reasons)


def _build_check_results(
    *,
    source_plan: LiveOrderRealApiPreflightPlan | None,
    request_snapshot: LiveOrderRealApiPreflightExecutionRequestSnapshot | None,
    environment_check: LiveOrderRealApiPreflightExecutionEnvironmentCheck | None,
    sanitized_result: LiveOrderRealApiPreflightSanitizedResult | None,
    executed_checks: tuple[LiveOrderRealApiPreflightExecutedCheck, ...],
    future_step6f_handoff_conditions: tuple[str, ...],
    unsafe_reasons: tuple[str, ...],
) -> tuple[LiveOrderRealApiPreflightExecutionCheckResult, ...]:
    source_ready = not _source_plan_blocked_reasons(source_plan)
    request_ready = not _request_blocked_reasons(request_snapshot)
    environment_ready = not _environment_blocked_reasons(environment_check)
    result_ready = not _sanitized_result_blocked_reasons(sanitized_result)
    executed_check_names = {check.name for check in executed_checks}
    no_order_post = not unsafe_reasons

    def check_bool(
        name: str,
        passed: bool,
        reason: str,
    ) -> LiveOrderRealApiPreflightExecutionCheckResult:
        return _check(name, passed, reason, _bool_text(passed), "true")

    def result_bool(
        name: str,
        field_name: str,
        expected: bool,
        reason: str,
    ) -> LiveOrderRealApiPreflightExecutionCheckResult:
        passed = _result_flag(sanitized_result, field_name, expected)
        return check_bool(name, passed, reason)

    return (
        check_bool("source_step6d_plan_ready", source_ready, "Step 6D plan ready"),
        check_bool(
            "explicit_step6e_request_received",
            request_ready,
            "explicit Step 6E request received",
        ),
        check_bool("environment_safe", environment_ready, "environment safe"),
        check_bool(
            "market_open_prefilter_passed",
            _environment_flag(
                environment_check,
                "local_market_hours_prefilter_passed",
                True,
            ),
            "market open prefilter passed",
        ),
        check_bool(
            "safe_read_only_route_found",
            _environment_flag(environment_check, "safe_read_only_route_found", True),
            "safe read-only route found",
        ),
        check_bool(
            "no_order_endpoint_route_used",
            _environment_flag(
                environment_check,
                "safe_read_only_route_verified_no_order_endpoint",
                True,
            ),
            "no order endpoint route used",
        ),
        result_bool(
            "api_preflight_executed",
            "api_preflight_executed",
            True,
            "API preflight executed via sanitized route",
        ),
        check_bool(
            "market_session_open",
            _result_text(sanitized_result, "market_session_state")
            == MARKET_HOURS_OPEN_STATE,
            "market session open",
        ),
        result_bool(
            "account_asset_check_passed",
            "account_asset_check_passed",
            True,
            "account asset check passed",
        ),
        check_bool(
            "open_positions_count_zero",
            _result_int(sanitized_result, "open_positions_count") == 0,
            "open positions count zero",
        ),
        check_bool(
            "active_orders_count_zero",
            _result_int(sanitized_result, "active_orders_count") == 0,
            "active orders count zero",
        ),
        result_bool(
            "instrument_rule_passed",
            "instrument_rule_check_passed",
            True,
            "instrument rule passed",
        ),
        check_bool(
            "ticker_spread_passed",
            _result_number(sanitized_result, "ticker_spread_jpy")
            <= STEP6E_MAX_SPREAD_JPY,
            "ticker spread passed",
        ),
        check_bool(
            "ticker_age_passed",
            STEP6E_MIN_TICKER_AGE_SECONDS
            <= _result_number(sanitized_result, "ticker_age_seconds")
            <= STEP6E_MAX_TICKER_AGE_SECONDS,
            "ticker age passed",
        ),
        result_bool(
            "permission_scope_passed",
            "permission_scope_check_passed",
            True,
            "permission scope passed",
        ),
        result_bool(
            "ip_account_binding_passed",
            "ip_account_binding_check_passed",
            True,
            "IP/account binding passed",
        ),
        result_bool(
            "previous_result_unknown_false",
            "previous_result_unknown_check_passed",
            True,
            "previous result unknown false",
        ),
        result_bool(
            "raw_request_not_saved_displayed",
            "raw_request_saved",
            False,
            "raw request not saved/displayed",
        ),
        result_bool(
            "raw_response_not_saved_displayed",
            "raw_response_saved",
            False,
            "raw response not saved/displayed",
        ),
        result_bool(
            "headers_not_saved_displayed",
            "headers_saved",
            False,
            "headers not saved/displayed",
        ),
        result_bool(
            "signature_not_saved_displayed",
            "signature_saved",
            False,
            "signature not saved/displayed",
        ),
        result_bool(
            "credentials_not_displayed",
            "credentials_displayed",
            False,
            "credentials not displayed",
        ),
        result_bool(
            "no_order_ids_displayed",
            "order_ids_displayed",
            False,
            "no order IDs displayed",
        ),
        check_bool(
            "no_api_broker_order_post",
            no_order_post and result_ready,
            "no API/broker/order POST",
        ),
        check_bool(
            "live_order_once_not_called",
            no_order_post,
            "live_order_once not called",
        ),
        check_bool(
            "post_not_allowed_this_step",
            no_order_post,
            "post not allowed this step",
        ),
        check_bool("post_not_executed", no_order_post, "post not executed"),
        check_bool(
            "future_step6f_handoff_conditions_present",
            bool(future_step6f_handoff_conditions),
            "future Step 6F handoff conditions present",
        ),
        check_bool(
            "executed_checks_present",
            set(DEFAULT_EXECUTED_CHECK_NAMES).issubset(executed_check_names),
            "executed checks present",
        ),
    )


def _build_sections(
    *,
    sanitized_result: LiveOrderRealApiPreflightSanitizedResult,
    check_results: tuple[LiveOrderRealApiPreflightExecutionCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
    future_step6f_handoff_conditions: tuple[str, ...],
    future_step6f_blockers: tuple[str, ...],
) -> tuple[LiveOrderRealApiPreflightExecutionSection, ...]:
    return (
        LiveOrderRealApiPreflightExecutionSection(
            section_id="step6e_scope",
            title="Step 6E Scope",
            lines=(
                "read-only/preflight result evaluation only",
                "allowed_for_live remains false",
                "no order endpoint, live_order_once, ledger, or HTTP POST is performed",
            ),
        ),
        LiveOrderRealApiPreflightExecutionSection(
            section_id="sanitized_result",
            title="Sanitized Result",
            lines=(
                f"market_session_state={sanitized_result.market_session_state}",
                f"open_positions_count={sanitized_result.open_positions_count}",
                f"active_orders_count={sanitized_result.active_orders_count}",
                f"ticker_spread_jpy={sanitized_result.ticker_spread_jpy}",
                f"ticker_age_seconds={sanitized_result.ticker_age_seconds}",
            ),
        ),
        LiveOrderRealApiPreflightExecutionSection(
            section_id="blocked_reasons",
            title="Blocked Reasons",
            lines=blocked_reasons or ("none",),
        ),
        LiveOrderRealApiPreflightExecutionSection(
            section_id="check_results",
            title="Check Results",
            lines=tuple(
                f"{check.name}: passed={check.passed}, expected={check.expected}"
                for check in check_results
            ),
        ),
        LiveOrderRealApiPreflightExecutionSection(
            section_id="future_step6f_handoff",
            title="Future Step 6F Handoff",
            lines=future_step6f_handoff_conditions or ("missing",),
        ),
        LiveOrderRealApiPreflightExecutionSection(
            section_id="future_step6f_blockers",
            title="Future Step 6F Blockers",
            lines=future_step6f_blockers or ("missing",),
        ),
        LiveOrderRealApiPreflightExecutionSection(
            section_id="recommended_next_step",
            title="Recommended Next Step",
            lines=(recommended_next_step,),
        ),
    )


def _validate_execution(execution: LiveOrderRealApiPreflightExecution) -> None:
    _require_non_empty("execution_id", execution.execution_id)
    if not execution.execution_id.startswith(
        LIVE_ORDER_REAL_API_PREFLIGHT_EXECUTION_ID_PREFIX,
    ):
        raise LiveVerificationValidationError("invalid execution_id prefix")
    _ensure_aware(execution.created_at)
    for label, value in (
        ("source_plan_id", execution.source_plan_id),
        ("source_validation_id", execution.source_validation_id),
        ("source_artifact_id", execution.source_artifact_id),
        ("symbol", execution.symbol),
        ("side", execution.side),
        ("execution_type", execution.execution_type),
        ("summary", execution.summary),
        ("recommended_next_step", execution.recommended_next_step),
    ):
        _require_non_empty(label, value)
    if execution.allowed_for_live is not False:
        raise LiveVerificationValidationError("allowed_for_live must be False")
    for field_name in (
        "approval_gate_issued",
        "approval_command_displayed",
        "approval_command_copyable",
        "public_api_called",
        "private_api_called",
        "broker_called",
        "order_endpoint_called",
        "order_payload_generated",
        "order_payload_sent",
        "live_order_once_called",
        "post_allowed_this_step",
        "post_executed",
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
        "raw_request_saved",
        "raw_request_displayed",
        "raw_response_saved",
        "raw_response_displayed",
        "headers_saved",
        "headers_displayed",
        "signature_saved",
        "signature_displayed",
    ):
        if getattr(execution, field_name) is not False:
            raise LiveVerificationValidationError(f"{field_name} must be False")
    if execution.post_attempt_limit != 1:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    for field_name in (
        "executed_checks",
        "future_step6f_handoff_conditions",
        "future_step6f_blockers",
        "check_results",
        "sections",
    ):
        if not getattr(execution, field_name):
            raise LiveVerificationValidationError(f"{field_name} required")
    if execution.execution_ready:
        if execution.execution_status is not ExecutionStatus.REAL_API_PREFLIGHT_PASSED_NO_POST:
            raise LiveVerificationValidationError("ready execution has invalid status")
        for field_name in (
            "api_preflight_executed",
            "api_preflight_passed",
            "eligible_for_step6f_post_readiness_planning",
            "approval_gate_enabled",
            "approval_artifact_validated",
            "approval_id_generated",
            "approval_command_generated",
            "approval_command_validated",
            "read_only_api_called",
        ):
            if getattr(execution, field_name) is not True:
                raise LiveVerificationValidationError(f"{field_name} must be True")
        if execution.symbol != SUPPORTED_SYMBOL:
            raise LiveVerificationValidationError("unsupported symbol")
        if execution.side not in {
            LiveOrderCandidateSide.BUY.value,
            LiveOrderCandidateSide.SELL.value,
        }:
            raise LiveVerificationValidationError("unsupported side")
        if execution.size != LIVE_ORDER_CANDIDATE_SIZE:
            raise LiveVerificationValidationError("unsupported size")
        if execution.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
            raise LiveVerificationValidationError("unsupported execution_type")
    else:
        for field_name in (
            "api_preflight_passed",
            "eligible_for_step6f_post_readiness_planning",
            "approval_gate_enabled",
            "approval_artifact_validated",
            "approval_id_generated",
            "approval_command_generated",
            "approval_command_validated",
            "read_only_api_called",
        ):
            if getattr(execution, field_name) is not False:
                raise LiveVerificationValidationError(f"{field_name} must be False")


def _executed_check_is_safe(check: LiveOrderRealApiPreflightExecutedCheck) -> bool:
    return (
        check.must_be_read_only is True
        and check.must_not_post is True
        and check.sanitized_only is True
        and check.raw_output_suppressed is True
    )


def _source_plan_is_missing_or_not_ready(
    plan: LiveOrderRealApiPreflightPlan | None,
    reasons: tuple[str, ...],
) -> bool:
    if not isinstance(plan, LiveOrderRealApiPreflightPlan):
        return True
    source_blocking = {
        BlockReason.MISSING_SOURCE_PLAN.value,
        BlockReason.SOURCE_PLAN_NOT_READY.value,
        BlockReason.SOURCE_PLAN_NOT_ELIGIBLE.value,
    }
    return bool(set(reasons) & source_blocking)


def _request_or_empty(
    snapshot: LiveOrderRealApiPreflightExecutionRequestSnapshot | None,
    created_at: datetime,
) -> LiveOrderRealApiPreflightExecutionRequestSnapshot:
    if isinstance(snapshot, LiveOrderRealApiPreflightExecutionRequestSnapshot):
        return snapshot
    return LiveOrderRealApiPreflightExecutionRequestSnapshot(
        request_id="missing",
        created_at=created_at,
        explicit_step6e_user_instruction_received=False,
        operator_understands_real_money_risk=False,
        operator_understands_read_only_preflight_only=False,
        operator_understands_no_post_in_step6e=False,
        operator_understands_no_order_endpoint_in_step6e=False,
        operator_understands_no_live_order_once_in_step6e=False,
        operator_understands_no_raw_response_display=False,
        operator_understands_no_raw_response_save=False,
        operator_understands_step6f_required_for_post_readiness=False,
        operator_understands_unknown_means_stop=False,
        request_scope_label="missing",
    )


def _environment_or_empty(
    environment: LiveOrderRealApiPreflightExecutionEnvironmentCheck | None,
    created_at: datetime,
) -> LiveOrderRealApiPreflightExecutionEnvironmentCheck:
    if isinstance(environment, LiveOrderRealApiPreflightExecutionEnvironmentCheck):
        return environment
    return LiveOrderRealApiPreflightExecutionEnvironmentCheck(
        environment_check_id="missing",
        created_at=created_at,
        git_clean=False,
        tests_recently_passed=False,
        ruff_recently_passed=False,
        secret_scan_passed=False,
        current_timezone="missing",
        is_weekend_jst=True,
        local_market_hours_prefilter_passed=False,
        safe_read_only_route_found=False,
        safe_read_only_route_name="missing",
        safe_read_only_route_verified_no_post=False,
        safe_read_only_route_verified_no_order_endpoint=False,
        safe_read_only_route_verified_no_live_order_once=False,
        safe_read_only_route_verified_no_raw_output=False,
        safe_read_only_route_verified_sanitized_output_only=False,
        env_values_displayed=True,
        env_file_displayed=True,
    )


def _result_or_empty(
    result: LiveOrderRealApiPreflightSanitizedResult | None,
    created_at: datetime,
) -> LiveOrderRealApiPreflightSanitizedResult:
    if isinstance(result, LiveOrderRealApiPreflightSanitizedResult):
        return result
    return LiveOrderRealApiPreflightSanitizedResult(
        result_id="missing",
        created_at=created_at,
        api_preflight_executed=False,
        api_preflight_route_name="missing",
        api_preflight_route_type="missing",
        api_preflight_result_status="missing",
        market_session_state="missing",
        market_window_allowed=False,
        broker_maintenance_active=True,
        holiday_or_special_close=True,
        market_hours_unknown=True,
        account_asset_status="missing",
        account_asset_check_passed=False,
        open_positions_count=-1,
        open_positions_check_passed=False,
        active_orders_count=-1,
        active_orders_check_passed=False,
        instrument_symbol="missing",
        instrument_min_open_order_size=999999,
        instrument_size_step=0,
        instrument_rule_check_passed=False,
        ticker_symbol="missing",
        ticker_spread_jpy=999999.0,
        ticker_age_seconds=999999.0,
        ticker_check_passed=False,
        permission_scope_check_passed=False,
        ip_account_binding_check_passed=False,
        previous_result_unknown_check_passed=False,
        raw_request_saved=True,
        raw_request_displayed=True,
        raw_response_saved=True,
        raw_response_displayed=True,
        headers_saved=True,
        headers_displayed=True,
        signature_saved=True,
        signature_displayed=True,
        credentials_displayed=True,
        order_ids_displayed=True,
        execution_ids_displayed=True,
        position_ids_displayed=True,
        client_order_ids_displayed=True,
    )


def _check(
    name: str,
    passed: bool,
    reason: str,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealApiPreflightExecutionCheckResult:
    return LiveOrderRealApiPreflightExecutionCheckResult(
        name=name,
        passed=passed,
        reason=reason,
        sanitized_value=sanitized_value,
        expected=expected,
    )


def _result_flag(
    result: LiveOrderRealApiPreflightSanitizedResult | None,
    field_name: str,
    expected: bool,
) -> bool:
    return (
        isinstance(result, LiveOrderRealApiPreflightSanitizedResult)
        and getattr(result, field_name) is expected
    )


def _environment_flag(
    environment: LiveOrderRealApiPreflightExecutionEnvironmentCheck | None,
    field_name: str,
    expected: bool,
) -> bool:
    return (
        isinstance(environment, LiveOrderRealApiPreflightExecutionEnvironmentCheck)
        and getattr(environment, field_name) is expected
    )


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _add_reason(
    reasons: list[str],
    reason: LiveOrderRealApiPreflightExecutionBlockReason,
) -> None:
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


def _result_text(
    result: LiveOrderRealApiPreflightSanitizedResult | None,
    field_name: str,
) -> str:
    return _text_from(result, field_name)


def _result_int(
    result: LiveOrderRealApiPreflightSanitizedResult | None,
    field_name: str,
) -> int:
    return _int_from(result, field_name)


def _result_number(
    result: LiveOrderRealApiPreflightSanitizedResult | None,
    field_name: str,
) -> float:
    value = getattr(result, field_name, 999999.0)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return 999999.0


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
