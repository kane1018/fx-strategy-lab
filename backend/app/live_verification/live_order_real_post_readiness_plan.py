"""Step 6F real post-readiness planning model.

This module accepts sanitized Step 6E-R2 preflight evidence and builds a
planning-only Step 6F report. It does not call APIs, import broker or Private
API clients, call live_order_once, build an order payload, or authorize HTTP
POST.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
)
from app.live_verification.live_order_real_api_preflight_execution import (
    STEP6E_MAX_SPREAD_JPY,
    STEP6E_MAX_TICKER_AGE_SECONDS,
)
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    MARKET_HOURS_OPEN_STATE,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_REAL_POST_READINESS_PLAN_ID_PREFIX = "LORPRP6F-"
STEP6F_REQUEST_SCOPE_LABEL = (
    "post_readiness_planning_only_no_post_no_order_endpoint_no_live_order_once"
)
STEP6E_R2_PASSED_STATUS = "REAL_API_PREFLIGHT_PASSED_NO_POST"
STEP6E_SC_READY_STATUS = "SAFE_READONLY_PREFLIGHT_ROUTE_CONSOLIDATED_NO_API_NO_POST"
STEP6F_RECOMMENDED_NEXT_STEP = (
    "stop_and_wait_for_explicit_step6g_one_shot_post_request_with_fresh_preflight_"
    "no_auto_post"
)


class LiveOrderRealPostReadinessPlanStatus(str, Enum):
    POST_READINESS_PLANNED_NO_POST = "POST_READINESS_PLANNED_NO_POST"
    BLOCKED_STEP6F_REQUEST = "BLOCKED_STEP6F_REQUEST"
    BLOCKED_STEP6F_PREFLIGHT_NOT_READY = "BLOCKED_STEP6F_PREFLIGHT_NOT_READY"
    BLOCKED_STEP6F_PREFLIGHT_STALE = "BLOCKED_STEP6F_PREFLIGHT_STALE"
    BLOCKED_STEP6F_PREFLIGHT_NOT_PASSING = "BLOCKED_STEP6F_PREFLIGHT_NOT_PASSING"
    BLOCKED_STEP6F_UNSAFE_STATE = "BLOCKED_STEP6F_UNSAFE_STATE"


PostReadinessStatus = LiveOrderRealPostReadinessPlanStatus


PRE_STEP6G_GO_CONDITIONS = (
    "explicit Step 6G request required",
    "Step 6E-R2 preflight must be fresh or rerun",
    "market-hours must be rechecked immediately before Step 6G",
    "open positions and active orders must remain zero",
    "ticker spread and age must remain within limits",
    "approval artifact must be revalidated or confirmed fresh",
    "post attempt limit remains 1",
    "no retry / no loop / no add / no change / no cancel / no close",
)
PRE_STEP6G_NO_GO_CONDITIONS = (
    "no explicit Step 6G request",
    "stale preflight",
    "market closed or unknown",
    "open position exists",
    "active order exists",
    "spread too wide",
    "ticker stale",
    "permission/IP/account binding failed",
    "raw response exposure risk",
    "any order endpoint called before Step 6G",
    "any need for retry/loop/add/change/cancel/close",
)
PRE_STEP6G_STOP_CONDITIONS = (
    "unknown status",
    "result_unknown",
    "stale or missing fresh preflight",
    "approval artifact validation stale",
    "exact match cannot be guaranteed",
    "raw/secret/ID exposure risk",
    "post attempt would exceed 1",
    "any unexpected API response shape",
    "any previous step inconsistency",
)
FUTURE_STEP6G_HANDOFF_CONDITIONS = (
    "user explicitly requests Step 6G one-shot POST",
    "fresh real API preflight rerun immediately before POST",
    "approval artifact validation refreshed or confirmed",
    "exact one-line approval command still valid",
    "allowed_for_live remains false until Step 6G controlled transition",
    "Step 6G must still stop before POST if any uncertainty",
    "Step 6G must attempt at most one POST",
)
FUTURE_STEP6G_BLOCKERS = (
    "no explicit Step 6G request",
    "fresh preflight unavailable",
    "market closed / unknown",
    "open positions or active orders detected",
    "approval artifact invalid or stale",
    "command mismatch",
    "spread too wide",
    "ticker stale",
    "raw response exposure risk",
    "any need for retry/loop/add/change/cancel/close",
)


@dataclass(frozen=True)
class LiveOrderRealPostReadinessCheckResult:
    name: str
    passed: bool
    reason: str
    sanitized_value: str
    expected: str

    def __post_init__(self) -> None:
        _require_non_empty("name", self.name)
        if type(self.passed) is not bool:
            raise LiveVerificationValidationError("passed must be bool")
        _require_non_empty("reason", self.reason)
        _require_non_empty("sanitized_value", self.sanitized_value)
        _require_non_empty("expected", self.expected)


@dataclass(frozen=True)
class LiveOrderRealPostReadinessPreflightSnapshot:
    snapshot_id: str
    created_at: datetime
    source_step6e_r2_reported: bool
    source_execution_status: str
    source_api_preflight_executed: bool
    source_api_preflight_passed: bool
    source_consolidation_status: str
    source_consolidation_ready: bool
    source_eligible_for_step6f_post_readiness_planning: bool
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
    raw_request_saved: bool = False
    raw_request_displayed: bool = False
    raw_response_saved: bool = False
    raw_response_displayed: bool = False
    headers_saved: bool = False
    headers_displayed: bool = False
    signature_saved: bool = False
    signature_displayed: bool = False
    credentials_displayed: bool = False
    order_ids_displayed: bool = False
    execution_ids_displayed: bool = False
    position_ids_displayed: bool = False
    client_order_ids_displayed: bool = False
    preflight_result_age_seconds: float = 0
    preflight_result_max_age_seconds: float = 60

    def __post_init__(self) -> None:
        _require_non_empty("snapshot_id", self.snapshot_id)
        _ensure_aware(self.created_at)
        _require_non_empty("source_execution_status", self.source_execution_status)
        _require_non_empty("source_consolidation_status", self.source_consolidation_status)
        _require_non_empty("market_session_state", self.market_session_state)
        _require_non_empty("account_asset_status", self.account_asset_status)
        _require_non_empty("instrument_symbol", self.instrument_symbol)
        _require_non_empty("ticker_symbol", self.ticker_symbol)
        _validate_bool_fields(
            self,
            (
                "source_step6e_r2_reported",
                "source_api_preflight_executed",
                "source_api_preflight_passed",
                "source_consolidation_ready",
                "source_eligible_for_step6f_post_readiness_planning",
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
            ),
        )
        for field_name in (
            "open_positions_count",
            "active_orders_count",
            "instrument_min_open_order_size",
            "instrument_size_step",
        ):
            _validate_non_negative_int(field_name, getattr(self, field_name))
        for field_name in (
            "ticker_spread_jpy",
            "ticker_age_seconds",
            "preflight_result_age_seconds",
            "preflight_result_max_age_seconds",
        ):
            _validate_non_negative_number(field_name, getattr(self, field_name))
        if self.preflight_result_max_age_seconds <= 0:
            raise LiveVerificationValidationError(
                "preflight_result_max_age_seconds must be positive",
            )


@dataclass(frozen=True)
class LiveOrderRealPostReadinessRequestSnapshot:
    request_id: str
    created_at: datetime
    explicit_step6f_user_instruction_received: bool
    operator_understands_real_money_risk: bool
    operator_understands_no_post_in_step6f: bool
    operator_understands_no_order_endpoint_in_step6f: bool
    operator_understands_no_live_order_once_in_step6f: bool
    operator_understands_post_readiness_planning_only: bool
    operator_understands_step6g_required_for_one_shot_post: bool
    operator_understands_fresh_preflight_required_before_step6g: bool
    operator_understands_unknown_means_stop: bool
    request_scope_label: str

    def __post_init__(self) -> None:
        _require_non_empty("request_id", self.request_id)
        _ensure_aware(self.created_at)
        _require_non_empty("request_scope_label", self.request_scope_label)
        _validate_bool_fields(
            self,
            (
                "explicit_step6f_user_instruction_received",
                "operator_understands_real_money_risk",
                "operator_understands_no_post_in_step6f",
                "operator_understands_no_order_endpoint_in_step6f",
                "operator_understands_no_live_order_once_in_step6f",
                "operator_understands_post_readiness_planning_only",
                "operator_understands_step6g_required_for_one_shot_post",
                "operator_understands_fresh_preflight_required_before_step6g",
                "operator_understands_unknown_means_stop",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealPostReadinessGoNoGoReport:
    pre_step6g_go_conditions: tuple[str, ...]
    pre_step6g_no_go_conditions: tuple[str, ...]
    pre_step6g_stop_conditions: tuple[str, ...]
    future_step6g_handoff_conditions: tuple[str, ...]
    future_step6g_blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "pre_step6g_go_conditions",
            "pre_step6g_no_go_conditions",
            "pre_step6g_stop_conditions",
            "future_step6g_handoff_conditions",
            "future_step6g_blockers",
        ):
            _require_string_tuple(field_name, getattr(self, field_name))


@dataclass(frozen=True)
class LiveOrderRealPostReadinessPlanSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("title", self.title)
        _require_string_tuple("lines", self.lines)


@dataclass(frozen=True)
class LiveOrderRealPostReadinessPlan:
    plan_id: str
    created_at: datetime
    source_preflight_snapshot_id: str
    source_step6e_execution_status: str
    symbol: str
    side: str
    size: int
    executionType: str
    plan_status: LiveOrderRealPostReadinessPlanStatus
    plan_ready: bool
    eligible_for_step6g_one_shot_post_request: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_artifact_validated: bool
    api_preflight_passed: bool
    post_readiness_planned: bool
    post_authorized_this_step: bool
    post_allowed_this_step: bool
    post_attempt_limit: int
    post_executed: bool
    order_endpoint_called: bool
    order_payload_generated: bool
    order_payload_sent: bool
    live_order_once_called: bool
    broker_order_path_called: bool
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
    credentials_displayed: bool
    order_ids_displayed: bool
    execution_ids_displayed: bool
    position_ids_displayed: bool
    client_order_ids_displayed: bool
    fresh_preflight_required_before_step6g: bool
    approval_artifact_revalidation_required_before_step6g: bool
    market_hours_recheck_required_before_step6g: bool
    positions_orders_recheck_required_before_step6g: bool
    ticker_recheck_required_before_step6g: bool
    pre_step6g_go_conditions: tuple[str, ...]
    pre_step6g_no_go_conditions: tuple[str, ...]
    pre_step6g_stop_conditions: tuple[str, ...]
    future_step6g_handoff_conditions: tuple[str, ...]
    future_step6g_blockers: tuple[str, ...]
    request_snapshot: LiveOrderRealPostReadinessRequestSnapshot
    preflight_snapshot: LiveOrderRealPostReadinessPreflightSnapshot
    go_no_go_report: LiveOrderRealPostReadinessGoNoGoReport
    check_results: tuple[LiveOrderRealPostReadinessCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str
    sections: tuple[LiveOrderRealPostReadinessPlanSection, ...]

    def __post_init__(self) -> None:
        _require_non_empty("plan_id", self.plan_id)
        if not self.plan_id.startswith(LIVE_ORDER_REAL_POST_READINESS_PLAN_ID_PREFIX):
            raise LiveVerificationValidationError("invalid plan_id prefix")
        _ensure_aware(self.created_at)
        _require_non_empty("source_preflight_snapshot_id", self.source_preflight_snapshot_id)
        _require_non_empty("source_step6e_execution_status", self.source_step6e_execution_status)
        _require_non_empty("symbol", self.symbol)
        _require_non_empty("side", self.side)
        _require_non_empty("executionType", self.executionType)
        _validate_non_negative_int("size", self.size)
        _validate_non_negative_int("post_attempt_limit", self.post_attempt_limit)
        _validate_bool_fields(
            self,
            (
                "plan_ready",
                "eligible_for_step6g_one_shot_post_request",
                "allowed_for_live",
                "approval_gate_enabled",
                "approval_artifact_validated",
                "api_preflight_passed",
                "post_readiness_planned",
                "post_authorized_this_step",
                "post_allowed_this_step",
                "post_executed",
                "order_endpoint_called",
                "order_payload_generated",
                "order_payload_sent",
                "live_order_once_called",
                "broker_order_path_called",
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
                "credentials_displayed",
                "order_ids_displayed",
                "execution_ids_displayed",
                "position_ids_displayed",
                "client_order_ids_displayed",
                "fresh_preflight_required_before_step6g",
                "approval_artifact_revalidation_required_before_step6g",
                "market_hours_recheck_required_before_step6g",
                "positions_orders_recheck_required_before_step6g",
                "ticker_recheck_required_before_step6g",
            ),
        )
        for field_name in (
            "pre_step6g_go_conditions",
            "pre_step6g_no_go_conditions",
            "pre_step6g_stop_conditions",
            "future_step6g_handoff_conditions",
            "future_step6g_blockers",
            "blocked_reasons",
        ):
            _require_string_tuple(field_name, getattr(self, field_name), allow_empty=True)
        if not self.check_results:
            raise LiveVerificationValidationError("check_results required")
        if not self.sections:
            raise LiveVerificationValidationError("sections required")
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        if self.source_preflight_snapshot_id != self.preflight_snapshot.snapshot_id:
            raise LiveVerificationValidationError("source_preflight_snapshot_id mismatch")
        if self.source_step6e_execution_status != self.preflight_snapshot.source_execution_status:
            raise LiveVerificationValidationError("source_step6e_execution_status mismatch")
        report = self.go_no_go_report
        if self.pre_step6g_go_conditions != report.pre_step6g_go_conditions:
            raise LiveVerificationValidationError("go conditions mismatch")
        if self.pre_step6g_no_go_conditions != report.pre_step6g_no_go_conditions:
            raise LiveVerificationValidationError("no-go conditions mismatch")
        if self.pre_step6g_stop_conditions != report.pre_step6g_stop_conditions:
            raise LiveVerificationValidationError("stop conditions mismatch")
        if self.future_step6g_handoff_conditions != report.future_step6g_handoff_conditions:
            raise LiveVerificationValidationError("handoff conditions mismatch")
        if self.future_step6g_blockers != report.future_step6g_blockers:
            raise LiveVerificationValidationError("blockers mismatch")


@dataclass(frozen=True)
class LiveOrderRealPostReadinessBuildResult:
    plan: LiveOrderRealPostReadinessPlan
    plan_id: str
    plan_status: LiveOrderRealPostReadinessPlanStatus
    plan_ready: bool
    eligible_for_step6g_one_shot_post_request: bool
    allowed_for_live: bool
    post_authorized_this_step: bool
    post_allowed_this_step: bool
    post_executed: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.plan.plan_id != self.plan_id:
            raise LiveVerificationValidationError("plan_id mismatch")
        if self.plan.plan_status is not self.plan_status:
            raise LiveVerificationValidationError("plan_status mismatch")
        for field_name in (
            "plan_ready",
            "eligible_for_step6g_one_shot_post_request",
            "allowed_for_live",
            "post_authorized_this_step",
            "post_allowed_this_step",
            "post_executed",
            "blocked_reasons",
            "recommended_next_step",
        ):
            if getattr(self.plan, field_name) != getattr(self, field_name):
                raise LiveVerificationValidationError(f"{field_name} mismatch")


def build_live_order_real_post_readiness_plan(
    *,
    request_snapshot: LiveOrderRealPostReadinessRequestSnapshot,
    preflight_snapshot: LiveOrderRealPostReadinessPreflightSnapshot,
    created_at: datetime | None = None,
    symbol: str = SUPPORTED_SYMBOL,
    side: str = "BUY",
    size: int = LIVE_ORDER_CANDIDATE_SIZE,
    executionType: str = LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    allowed_for_live: bool = False,
    approval_gate_enabled: bool = True,
    approval_artifact_validated: bool = True,
    post_authorized_this_step: bool = False,
    post_allowed_this_step: bool = False,
    post_attempt_limit: int = 1,
    post_executed: bool = False,
    order_endpoint_called: bool = False,
    order_payload_generated: bool = False,
    order_payload_sent: bool = False,
    live_order_once_called: bool = False,
    broker_order_path_called: bool = False,
    retry_allowed: bool = False,
    loop_allowed: bool = False,
    add_order_allowed: bool = False,
    change_order_allowed: bool = False,
    cancel_order_allowed: bool = False,
    close_order_allowed: bool = False,
    raw_request_saved: bool | None = None,
    raw_request_displayed: bool | None = None,
    raw_response_saved: bool | None = None,
    raw_response_displayed: bool | None = None,
    headers_saved: bool | None = None,
    headers_displayed: bool | None = None,
    signature_saved: bool | None = None,
    signature_displayed: bool | None = None,
    credentials_displayed: bool | None = None,
    order_ids_displayed: bool | None = None,
    execution_ids_displayed: bool | None = None,
    position_ids_displayed: bool | None = None,
    client_order_ids_displayed: bool | None = None,
) -> LiveOrderRealPostReadinessBuildResult:
    """Build a Step 6F planning-only post-readiness report."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    exposure_flags = {
        "raw_request_saved": (
            preflight_snapshot.raw_request_saved
            if raw_request_saved is None
            else raw_request_saved
        ),
        "raw_request_displayed": (
            preflight_snapshot.raw_request_displayed
            if raw_request_displayed is None
            else raw_request_displayed
        ),
        "raw_response_saved": (
            preflight_snapshot.raw_response_saved
            if raw_response_saved is None
            else raw_response_saved
        ),
        "raw_response_displayed": (
            preflight_snapshot.raw_response_displayed
            if raw_response_displayed is None
            else raw_response_displayed
        ),
        "headers_saved": (
            preflight_snapshot.headers_saved
            if headers_saved is None
            else headers_saved
        ),
        "headers_displayed": (
            preflight_snapshot.headers_displayed
            if headers_displayed is None
            else headers_displayed
        ),
        "signature_saved": (
            preflight_snapshot.signature_saved
            if signature_saved is None
            else signature_saved
        ),
        "signature_displayed": (
            preflight_snapshot.signature_displayed
            if signature_displayed is None
            else signature_displayed
        ),
        "credentials_displayed": (
            preflight_snapshot.credentials_displayed
            if credentials_displayed is None
            else credentials_displayed
        ),
        "order_ids_displayed": (
            preflight_snapshot.order_ids_displayed
            if order_ids_displayed is None
            else order_ids_displayed
        ),
        "execution_ids_displayed": (
            preflight_snapshot.execution_ids_displayed
            if execution_ids_displayed is None
            else execution_ids_displayed
        ),
        "position_ids_displayed": (
            preflight_snapshot.position_ids_displayed
            if position_ids_displayed is None
            else position_ids_displayed
        ),
        "client_order_ids_displayed": (
            preflight_snapshot.client_order_ids_displayed
            if client_order_ids_displayed is None
            else client_order_ids_displayed
        ),
    }

    request_reasons = _request_block_reasons(request_snapshot)
    preflight_ready_reasons = _preflight_not_ready_reasons(preflight_snapshot)
    stale_reasons = _preflight_stale_reasons(preflight_snapshot)
    preflight_not_passing_reasons = _preflight_not_passing_reasons(preflight_snapshot)
    unsafe_reasons = _unsafe_state_reasons(
        allowed_for_live=allowed_for_live,
        post_authorized_this_step=post_authorized_this_step,
        post_allowed_this_step=post_allowed_this_step,
        post_attempt_limit=post_attempt_limit,
        post_executed=post_executed,
        order_endpoint_called=order_endpoint_called,
        order_payload_generated=order_payload_generated,
        order_payload_sent=order_payload_sent,
        live_order_once_called=live_order_once_called,
        broker_order_path_called=broker_order_path_called,
        retry_allowed=retry_allowed,
        loop_allowed=loop_allowed,
        add_order_allowed=add_order_allowed,
        change_order_allowed=change_order_allowed,
        cancel_order_allowed=cancel_order_allowed,
        close_order_allowed=close_order_allowed,
        exposure_flags=exposure_flags,
    )

    if request_reasons:
        status = PostReadinessStatus.BLOCKED_STEP6F_REQUEST
        recommended_next_step = "collect_explicit_step6f_request_and_acknowledgements_no_post"
    elif preflight_ready_reasons:
        status = PostReadinessStatus.BLOCKED_STEP6F_PREFLIGHT_NOT_READY
        recommended_next_step = "rerun_or_provide_passing_step6e_r2_sanitized_preflight_no_post"
    elif unsafe_reasons:
        status = PostReadinessStatus.BLOCKED_STEP6F_UNSAFE_STATE
        recommended_next_step = "stop_fix_unsafe_step6f_state_no_post"
    elif stale_reasons:
        status = PostReadinessStatus.BLOCKED_STEP6F_PREFLIGHT_STALE
        recommended_next_step = "rerun_fresh_step6e_r2_preflight_before_step6f_ready_no_post"
    elif preflight_not_passing_reasons:
        status = PostReadinessStatus.BLOCKED_STEP6F_PREFLIGHT_NOT_PASSING
        recommended_next_step = "fix_preflight_conditions_before_step6f_ready_no_post"
    else:
        status = PostReadinessStatus.POST_READINESS_PLANNED_NO_POST
        recommended_next_step = STEP6F_RECOMMENDED_NEXT_STEP

    plan_ready = status is PostReadinessStatus.POST_READINESS_PLANNED_NO_POST
    blocked_reasons = _merge_reasons(
        request_reasons,
        preflight_ready_reasons,
        unsafe_reasons,
        stale_reasons,
        preflight_not_passing_reasons,
    )
    go_no_go_report = LiveOrderRealPostReadinessGoNoGoReport(
        pre_step6g_go_conditions=PRE_STEP6G_GO_CONDITIONS,
        pre_step6g_no_go_conditions=PRE_STEP6G_NO_GO_CONDITIONS,
        pre_step6g_stop_conditions=PRE_STEP6G_STOP_CONDITIONS,
        future_step6g_handoff_conditions=FUTURE_STEP6G_HANDOFF_CONDITIONS,
        future_step6g_blockers=FUTURE_STEP6G_BLOCKERS,
    )
    check_results = _build_check_results(
        request_snapshot=request_snapshot,
        preflight_snapshot=preflight_snapshot,
        exposure_flags=exposure_flags,
        plan_ready=plan_ready,
        blocked_reasons=blocked_reasons,
        allowed_for_live=allowed_for_live,
        post_authorized_this_step=post_authorized_this_step,
        post_allowed_this_step=post_allowed_this_step,
        post_executed=post_executed,
        order_endpoint_called=order_endpoint_called,
        order_payload_generated=order_payload_generated,
        order_payload_sent=order_payload_sent,
        live_order_once_called=live_order_once_called,
        retry_allowed=retry_allowed,
        loop_allowed=loop_allowed,
        add_order_allowed=add_order_allowed,
        change_order_allowed=change_order_allowed,
        cancel_order_allowed=cancel_order_allowed,
        close_order_allowed=close_order_allowed,
    )
    plan_id = make_live_order_real_post_readiness_plan_id(
        created_at=created,
        status=status,
        request_id=request_snapshot.request_id,
        snapshot_id=preflight_snapshot.snapshot_id,
        blocked_reasons=blocked_reasons,
    )
    plan = LiveOrderRealPostReadinessPlan(
        plan_id=plan_id,
        created_at=created,
        source_preflight_snapshot_id=preflight_snapshot.snapshot_id,
        source_step6e_execution_status=preflight_snapshot.source_execution_status,
        symbol=symbol,
        side=side,
        size=size,
        executionType=executionType,
        plan_status=status,
        plan_ready=plan_ready,
        eligible_for_step6g_one_shot_post_request=plan_ready,
        allowed_for_live=allowed_for_live,
        approval_gate_enabled=approval_gate_enabled,
        approval_artifact_validated=approval_artifact_validated,
        api_preflight_passed=preflight_snapshot.source_api_preflight_passed,
        post_readiness_planned=plan_ready,
        post_authorized_this_step=post_authorized_this_step,
        post_allowed_this_step=post_allowed_this_step,
        post_attempt_limit=post_attempt_limit,
        post_executed=post_executed,
        order_endpoint_called=order_endpoint_called,
        order_payload_generated=order_payload_generated,
        order_payload_sent=order_payload_sent,
        live_order_once_called=live_order_once_called,
        broker_order_path_called=broker_order_path_called,
        retry_allowed=retry_allowed,
        loop_allowed=loop_allowed,
        add_order_allowed=add_order_allowed,
        change_order_allowed=change_order_allowed,
        cancel_order_allowed=cancel_order_allowed,
        close_order_allowed=close_order_allowed,
        raw_request_saved=exposure_flags["raw_request_saved"],
        raw_request_displayed=exposure_flags["raw_request_displayed"],
        raw_response_saved=exposure_flags["raw_response_saved"],
        raw_response_displayed=exposure_flags["raw_response_displayed"],
        headers_saved=exposure_flags["headers_saved"],
        headers_displayed=exposure_flags["headers_displayed"],
        signature_saved=exposure_flags["signature_saved"],
        signature_displayed=exposure_flags["signature_displayed"],
        credentials_displayed=exposure_flags["credentials_displayed"],
        order_ids_displayed=exposure_flags["order_ids_displayed"],
        execution_ids_displayed=exposure_flags["execution_ids_displayed"],
        position_ids_displayed=exposure_flags["position_ids_displayed"],
        client_order_ids_displayed=exposure_flags["client_order_ids_displayed"],
        fresh_preflight_required_before_step6g=True,
        approval_artifact_revalidation_required_before_step6g=True,
        market_hours_recheck_required_before_step6g=True,
        positions_orders_recheck_required_before_step6g=True,
        ticker_recheck_required_before_step6g=True,
        pre_step6g_go_conditions=go_no_go_report.pre_step6g_go_conditions,
        pre_step6g_no_go_conditions=go_no_go_report.pre_step6g_no_go_conditions,
        pre_step6g_stop_conditions=go_no_go_report.pre_step6g_stop_conditions,
        future_step6g_handoff_conditions=go_no_go_report.future_step6g_handoff_conditions,
        future_step6g_blockers=go_no_go_report.future_step6g_blockers,
        request_snapshot=request_snapshot,
        preflight_snapshot=preflight_snapshot,
        go_no_go_report=go_no_go_report,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            status=status,
            plan_ready=plan_ready,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
        ),
    )
    return LiveOrderRealPostReadinessBuildResult(
        plan=plan,
        plan_id=plan.plan_id,
        plan_status=plan.plan_status,
        plan_ready=plan.plan_ready,
        eligible_for_step6g_one_shot_post_request=(
            plan.eligible_for_step6g_one_shot_post_request
        ),
        allowed_for_live=plan.allowed_for_live,
        post_authorized_this_step=plan.post_authorized_this_step,
        post_allowed_this_step=plan.post_allowed_this_step,
        post_executed=plan.post_executed,
        blocked_reasons=plan.blocked_reasons,
        recommended_next_step=plan.recommended_next_step,
    )


def render_live_order_real_post_readiness_plan_markdown(
    plan: LiveOrderRealPostReadinessPlan,
) -> str:
    """Render a sanitized Step 6F planning report."""
    check_lines = "\n".join(
        f"- {check.name}: passed={check.passed}, value={check.sanitized_value}"
        for check in plan.check_results
    )
    blocked_text = ", ".join(plan.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6F Real Post Readiness Plan",
            "",
            "This Step 6F post-readiness plan is planning-only.",
            "This Step 6F plan does not authorize live POST.",
            "This Step 6F plan keeps allowed_for_live=false.",
            "This Step 6F plan does not call any order endpoint.",
            "This Step 6F plan does not generate or send an order payload.",
            "This Step 6F plan does not call live_order_once.",
            "This Step 6F plan does not execute HTTP POST.",
            "Step 6G requires a separate explicit request and fresh preflight.",
            "",
            f"plan_id: {plan.plan_id}",
            f"plan_status: {plan.plan_status.value}",
            f"plan_ready: {plan.plan_ready}",
            (
                "eligible_for_step6g_one_shot_post_request: "
                f"{plan.eligible_for_step6g_one_shot_post_request}"
            ),
            f"allowed_for_live: {plan.allowed_for_live}",
            f"post_readiness_planned: {plan.post_readiness_planned}",
            f"post_authorized_this_step: {plan.post_authorized_this_step}",
            f"post_allowed_this_step: {plan.post_allowed_this_step}",
            f"post_attempt_limit: {plan.post_attempt_limit}",
            f"post_executed: {plan.post_executed}",
            f"symbol: {plan.symbol}",
            f"side: {plan.side}",
            f"size: {plan.size}",
            f"executionType: {plan.executionType}",
            f"market_session_state: {plan.preflight_snapshot.market_session_state}",
            f"open_positions_count: {plan.preflight_snapshot.open_positions_count}",
            f"active_orders_count: {plan.preflight_snapshot.active_orders_count}",
            f"ticker_spread_jpy: {plan.preflight_snapshot.ticker_spread_jpy}",
            f"ticker_age_seconds: {plan.preflight_snapshot.ticker_age_seconds}",
            "",
            "## Pre Step 6G Go Conditions",
            _bullet_lines(plan.pre_step6g_go_conditions),
            "",
            "## Pre Step 6G No-go Conditions",
            _bullet_lines(plan.pre_step6g_no_go_conditions),
            "",
            "## Pre Step 6G Stop Conditions",
            _bullet_lines(plan.pre_step6g_stop_conditions),
            "",
            "## Future Step 6G Handoff Conditions",
            _bullet_lines(plan.future_step6g_handoff_conditions),
            "",
            "## Future Step 6G Blockers",
            _bullet_lines(plan.future_step6g_blockers),
            "",
            "## Check Results",
            check_lines,
            "",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {plan.recommended_next_step}",
        ),
    )


def make_live_order_real_post_readiness_plan_id(
    *,
    created_at: datetime,
    status: LiveOrderRealPostReadinessPlanStatus,
    request_id: str,
    snapshot_id: str,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "blocked_reasons": list(blocked_reasons),
        "created_at": _ensure_aware(created_at).isoformat(),
        "request_id": request_id,
        "snapshot_id": snapshot_id,
        "status": status.value,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_POST_READINESS_PLAN_ID_PREFIX}{digest}"


def _request_block_reasons(
    request_snapshot: LiveOrderRealPostReadinessRequestSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    required_true_fields = (
        "explicit_step6f_user_instruction_received",
        "operator_understands_real_money_risk",
        "operator_understands_no_post_in_step6f",
        "operator_understands_no_order_endpoint_in_step6f",
        "operator_understands_no_live_order_once_in_step6f",
        "operator_understands_post_readiness_planning_only",
        "operator_understands_step6g_required_for_one_shot_post",
        "operator_understands_fresh_preflight_required_before_step6g",
        "operator_understands_unknown_means_stop",
    )
    for field_name in required_true_fields:
        if getattr(request_snapshot, field_name) is not True:
            _add_reason(reasons, f"{field_name}_missing")
    if request_snapshot.request_scope_label != STEP6F_REQUEST_SCOPE_LABEL:
        _add_reason(reasons, "request_scope_label_invalid")
    return tuple(reasons)


def _preflight_not_ready_reasons(
    snapshot: LiveOrderRealPostReadinessPreflightSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.source_step6e_r2_reported is not True:
        _add_reason(reasons, "source_step6e_r2_not_reported")
    if snapshot.source_execution_status != STEP6E_R2_PASSED_STATUS:
        _add_reason(reasons, "source_execution_status_not_passed")
    if snapshot.source_api_preflight_executed is not True:
        _add_reason(reasons, "source_api_preflight_not_executed")
    if snapshot.source_api_preflight_passed is not True:
        _add_reason(reasons, "source_api_preflight_not_passed")
    if snapshot.source_consolidation_status != STEP6E_SC_READY_STATUS:
        _add_reason(reasons, "source_consolidation_status_not_ready")
    if snapshot.source_consolidation_ready is not True:
        _add_reason(reasons, "source_consolidation_not_ready")
    if snapshot.source_eligible_for_step6f_post_readiness_planning is not True:
        _add_reason(reasons, "source_not_eligible_for_step6f_post_readiness_planning")
    return tuple(reasons)


def _preflight_stale_reasons(
    snapshot: LiveOrderRealPostReadinessPreflightSnapshot,
) -> tuple[str, ...]:
    if snapshot.preflight_result_age_seconds > snapshot.preflight_result_max_age_seconds:
        return ("preflight_result_stale",)
    return ()


def _preflight_not_passing_reasons(
    snapshot: LiveOrderRealPostReadinessPreflightSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.market_session_state != MARKET_HOURS_OPEN_STATE:
        _add_reason(reasons, "market_session_not_open")
    if snapshot.market_window_allowed is not True:
        _add_reason(reasons, "market_window_not_allowed")
    if snapshot.broker_maintenance_active is not False:
        _add_reason(reasons, "broker_maintenance_active")
    if snapshot.holiday_or_special_close is not False:
        _add_reason(reasons, "holiday_or_special_close")
    if snapshot.market_hours_unknown is not False:
        _add_reason(reasons, "market_hours_unknown")
    if snapshot.account_asset_check_passed is not True:
        _add_reason(reasons, "account_asset_check_failed")
    if snapshot.open_positions_count != 0:
        _add_reason(reasons, "open_positions_not_zero")
    if snapshot.open_positions_check_passed is not True:
        _add_reason(reasons, "open_positions_check_failed")
    if snapshot.active_orders_count != 0:
        _add_reason(reasons, "active_orders_not_zero")
    if snapshot.active_orders_check_passed is not True:
        _add_reason(reasons, "active_orders_check_failed")
    if snapshot.instrument_symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, "instrument_symbol_unsupported")
    if snapshot.instrument_min_open_order_size > LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, "instrument_min_size_unsupported")
    if snapshot.instrument_size_step != 1:
        _add_reason(reasons, "instrument_size_step_unsupported")
    if snapshot.instrument_rule_check_passed is not True:
        _add_reason(reasons, "instrument_rule_check_failed")
    if snapshot.ticker_symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, "ticker_symbol_unsupported")
    if snapshot.ticker_spread_jpy > STEP6E_MAX_SPREAD_JPY:
        _add_reason(reasons, "ticker_spread_too_wide")
    if snapshot.ticker_age_seconds > STEP6E_MAX_TICKER_AGE_SECONDS:
        _add_reason(reasons, "ticker_age_stale")
    if snapshot.ticker_check_passed is not True:
        _add_reason(reasons, "ticker_check_failed")
    if snapshot.permission_scope_check_passed is not True:
        _add_reason(reasons, "permission_scope_check_failed")
    if snapshot.ip_account_binding_check_passed is not True:
        _add_reason(reasons, "ip_account_binding_check_failed")
    if snapshot.previous_result_unknown_check_passed is not True:
        _add_reason(reasons, "previous_result_unknown_check_failed")
    return tuple(reasons)


def _unsafe_state_reasons(
    *,
    allowed_for_live: bool,
    post_authorized_this_step: bool,
    post_allowed_this_step: bool,
    post_attempt_limit: int,
    post_executed: bool,
    order_endpoint_called: bool,
    order_payload_generated: bool,
    order_payload_sent: bool,
    live_order_once_called: bool,
    broker_order_path_called: bool,
    retry_allowed: bool,
    loop_allowed: bool,
    add_order_allowed: bool,
    change_order_allowed: bool,
    cancel_order_allowed: bool,
    close_order_allowed: bool,
    exposure_flags: dict[str, bool],
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name, value in (
        ("allowed_for_live", allowed_for_live),
        ("post_authorized_this_step", post_authorized_this_step),
        ("post_allowed_this_step", post_allowed_this_step),
        ("post_executed", post_executed),
        ("order_endpoint_called", order_endpoint_called),
        ("order_payload_generated", order_payload_generated),
        ("order_payload_sent", order_payload_sent),
        ("live_order_once_called", live_order_once_called),
        ("broker_order_path_called", broker_order_path_called),
        ("retry_allowed", retry_allowed),
        ("loop_allowed", loop_allowed),
        ("add_order_allowed", add_order_allowed),
        ("change_order_allowed", change_order_allowed),
        ("cancel_order_allowed", cancel_order_allowed),
        ("close_order_allowed", close_order_allowed),
    ):
        if value is True:
            _add_reason(reasons, f"{field_name}_unsafe")
    if post_attempt_limit != 1:
        _add_reason(reasons, "post_attempt_limit_not_one")
    for field_name, value in exposure_flags.items():
        if type(value) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")
        if value is True:
            _add_reason(reasons, f"{field_name}_unsafe")
    return tuple(reasons)


def _build_check_results(
    *,
    request_snapshot: LiveOrderRealPostReadinessRequestSnapshot,
    preflight_snapshot: LiveOrderRealPostReadinessPreflightSnapshot,
    exposure_flags: dict[str, bool],
    plan_ready: bool,
    blocked_reasons: tuple[str, ...],
    allowed_for_live: bool,
    post_authorized_this_step: bool,
    post_allowed_this_step: bool,
    post_executed: bool,
    order_endpoint_called: bool,
    order_payload_generated: bool,
    order_payload_sent: bool,
    live_order_once_called: bool,
    retry_allowed: bool,
    loop_allowed: bool,
    add_order_allowed: bool,
    change_order_allowed: bool,
    cancel_order_allowed: bool,
    close_order_allowed: bool,
) -> tuple[LiveOrderRealPostReadinessCheckResult, ...]:
    exposure_clear = all(value is False for value in exposure_flags.values())
    return (
        _check(
            "explicit Step 6F request received",
            request_snapshot.explicit_step6f_user_instruction_received is True,
            "Step 6F was explicitly requested",
            _bool_text(request_snapshot.explicit_step6f_user_instruction_received),
            "true",
        ),
        _check(
            "operator acknowledgements complete",
            not _request_block_reasons(request_snapshot),
            "all Step 6F operator acknowledgements are complete",
            _bool_text(not _request_block_reasons(request_snapshot)),
            "true",
        ),
        _check(
            "source Step 6E-R2 preflight executed",
            preflight_snapshot.source_api_preflight_executed is True,
            "source Step 6E-R2 preflight executed",
            _bool_text(preflight_snapshot.source_api_preflight_executed),
            "true",
        ),
        _check(
            "source Step 6E-R2 preflight passed",
            preflight_snapshot.source_api_preflight_passed is True,
            "source Step 6E-R2 preflight passed",
            _bool_text(preflight_snapshot.source_api_preflight_passed),
            "true",
        ),
        _check(
            "preflight not stale",
            not _preflight_stale_reasons(preflight_snapshot),
            "preflight age is within the freshness limit",
            (
                f"{preflight_snapshot.preflight_result_age_seconds}/"
                f"{preflight_snapshot.preflight_result_max_age_seconds}"
            ),
            "<= max age seconds",
        ),
        _check(
            "allowed_for_live false",
            allowed_for_live is False,
            "Step 6F keeps allowed_for_live false",
            _bool_text(allowed_for_live),
            "false",
        ),
        _check(
            "post not authorized this step",
            post_authorized_this_step is False,
            "Step 6F does not authorize post",
            _bool_text(post_authorized_this_step),
            "false",
        ),
        _check(
            "post not allowed this step",
            post_allowed_this_step is False,
            "Step 6F does not allow post",
            _bool_text(post_allowed_this_step),
            "false",
        ),
        _check(
            "post not executed",
            post_executed is False,
            "Step 6F did not execute post",
            _bool_text(post_executed),
            "false",
        ),
        _check(
            "order endpoint not called",
            order_endpoint_called is False,
            "Step 6F did not call an order endpoint",
            _bool_text(order_endpoint_called),
            "false",
        ),
        _check(
            "order payload not generated/sent",
            order_payload_generated is False and order_payload_sent is False,
            "Step 6F did not generate or send an order payload",
            f"generated={order_payload_generated};sent={order_payload_sent}",
            "generated=false;sent=false",
        ),
        _check(
            "live_order_once not called",
            live_order_once_called is False,
            "Step 6F did not call live_order_once",
            _bool_text(live_order_once_called),
            "false",
        ),
        _check(
            "market session open",
            preflight_snapshot.market_session_state == MARKET_HOURS_OPEN_STATE,
            "market session is open",
            preflight_snapshot.market_session_state,
            MARKET_HOURS_OPEN_STATE,
        ),
        _check(
            "open positions count zero",
            preflight_snapshot.open_positions_count == 0,
            "open positions count is zero",
            str(preflight_snapshot.open_positions_count),
            "0",
        ),
        _check(
            "active orders count zero",
            preflight_snapshot.active_orders_count == 0,
            "active orders count is zero",
            str(preflight_snapshot.active_orders_count),
            "0",
        ),
        _check(
            "ticker spread passed",
            preflight_snapshot.ticker_spread_jpy <= STEP6E_MAX_SPREAD_JPY,
            "ticker spread is within the Step 6E limit",
            str(preflight_snapshot.ticker_spread_jpy),
            f"<= {STEP6E_MAX_SPREAD_JPY}",
        ),
        _check(
            "ticker age passed",
            preflight_snapshot.ticker_age_seconds <= STEP6E_MAX_TICKER_AGE_SECONDS,
            "ticker age is within the Step 6E limit",
            str(preflight_snapshot.ticker_age_seconds),
            f"<= {STEP6E_MAX_TICKER_AGE_SECONDS}",
        ),
        _check(
            "permission scope passed",
            preflight_snapshot.permission_scope_check_passed is True,
            "permission scope check passed",
            _bool_text(preflight_snapshot.permission_scope_check_passed),
            "true",
        ),
        _check(
            "IP/account binding passed",
            preflight_snapshot.ip_account_binding_check_passed is True,
            "IP/account binding check passed",
            _bool_text(preflight_snapshot.ip_account_binding_check_passed),
            "true",
        ),
        _check(
            "previous result unknown false",
            preflight_snapshot.previous_result_unknown_check_passed is True,
            "previous result unknown check passed",
            _bool_text(preflight_snapshot.previous_result_unknown_check_passed),
            "true",
        ),
        _check(
            "raw/header/signature/credential/ID exposure flags false",
            exposure_clear,
            "raw/header/signature/credential/ID exposure flags are false",
            _bool_text(exposure_clear),
            "true",
        ),
        _check(
            "Step 6G handoff conditions present",
            bool(
                PRE_STEP6G_GO_CONDITIONS
                and PRE_STEP6G_NO_GO_CONDITIONS
                and PRE_STEP6G_STOP_CONDITIONS
                and FUTURE_STEP6G_HANDOFF_CONDITIONS
                and FUTURE_STEP6G_BLOCKERS
            ),
            "Step 6G go/no-go/stop/handoff/blockers are present",
            _bool_text(True),
            "true",
        ),
        _check(
            "post-readiness plan ready",
            plan_ready,
            "Step 6F ready only when no blocked reasons remain",
            _bool_text(plan_ready),
            f"true; blocked_reasons={len(blocked_reasons)}",
        ),
        _check(
            "retry loop mutation controls false",
            (
                retry_allowed is False
                and loop_allowed is False
                and add_order_allowed is False
                and change_order_allowed is False
                and cancel_order_allowed is False
                and close_order_allowed is False
            ),
            "retry/loop/add/change/cancel/close stay disabled",
            (
                f"retry={retry_allowed};loop={loop_allowed};add={add_order_allowed};"
                f"change={change_order_allowed};cancel={cancel_order_allowed};"
                f"close={close_order_allowed}"
            ),
            "all false",
        ),
    )


def _build_sections(
    *,
    status: LiveOrderRealPostReadinessPlanStatus,
    plan_ready: bool,
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
) -> tuple[LiveOrderRealPostReadinessPlanSection, ...]:
    blocked_text = ", ".join(blocked_reasons) or "none"
    return (
        LiveOrderRealPostReadinessPlanSection(
            section_id="summary",
            title="Summary",
            lines=(
                f"plan_status={status.value}",
                f"plan_ready={plan_ready}",
                f"blocked_reasons={blocked_text}",
            ),
        ),
        LiveOrderRealPostReadinessPlanSection(
            section_id="next_step",
            title="Next Step",
            lines=(recommended_next_step,),
        ),
    )


def _check(
    name: str,
    passed: bool,
    reason: str,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealPostReadinessCheckResult:
    return LiveOrderRealPostReadinessCheckResult(
        name=name,
        passed=passed,
        reason=reason,
        sanitized_value=sanitized_value,
        expected=expected,
    )


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            _add_reason(merged, reason)
    return tuple(merged)


def _add_reason(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _bullet_lines(values: tuple[str, ...]) -> str:
    return "\n".join(f"- {value}" for value in values)


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")


def _require_string_tuple(
    field_name: str,
    values: tuple[str, ...],
    *,
    allow_empty: bool = False,
) -> None:
    if not isinstance(values, tuple):
        raise LiveVerificationValidationError(f"{field_name} must be tuple")
    if not values and not allow_empty:
        raise LiveVerificationValidationError(f"{field_name} is required")
    for value in values:
        _require_non_empty(field_name, value)


def _validate_bool_fields(target: Any, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(target, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_non_negative_number(field_name: str, value: float) -> None:
    if not isinstance(value, int | float) or isinstance(value, bool) or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative number")


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value


def _bool_text(value: bool) -> str:
    return "true" if value is True else "false"
