"""Step 6E-SC safe read-only preflight route consolidation model.

This module consolidates sanitized inputs only. It does not call APIs, import
broker or Private API clients, call live_order_once, or authorize HTTP POST.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_candidate import LIVE_ORDER_CANDIDATE_SIZE
from app.live_verification.live_order_real_api_preflight_execution import (
    STEP6E_MAX_SPREAD_JPY,
    STEP6E_MAX_TICKER_AGE_SECONDS,
)
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    MARKET_HOURS_OPEN_STATE,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_REAL_API_PREFLIGHT_SAFE_ROUTE_CONSOLIDATION_ID_PREFIX = "LORAPSC6ESC-"


class LiveOrderRealApiPreflightSafeRouteConsolidationStatus(str, Enum):
    SAFE_READONLY_PREFLIGHT_ROUTE_CONSOLIDATED_NO_API_NO_POST = (
        "SAFE_READONLY_PREFLIGHT_ROUTE_CONSOLIDATED_NO_API_NO_POST"
    )
    BLOCKED_SAFE_ROUTE_CONSOLIDATION_MISSING_INPUT = (
        "BLOCKED_SAFE_ROUTE_CONSOLIDATION_MISSING_INPUT"
    )
    BLOCKED_SAFE_ROUTE_CONSOLIDATION_UNSAFE_ROUTE = (
        "BLOCKED_SAFE_ROUTE_CONSOLIDATION_UNSAFE_ROUTE"
    )
    BLOCKED_SAFE_ROUTE_CONSOLIDATION_INCOMPLETE_FIELDS = (
        "BLOCKED_SAFE_ROUTE_CONSOLIDATION_INCOMPLETE_FIELDS"
    )
    BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING = (
        "BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING"
    )


ConsolidationStatus = LiveOrderRealApiPreflightSafeRouteConsolidationStatus


@dataclass(frozen=True)
class LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput:
    source_route_name: str
    source_route_verified_no_post: bool | None
    source_route_verified_no_order_endpoint: bool | None
    source_route_verified_no_live_order_once: bool | None
    source_route_verified_no_raw_output: bool | None
    source_route_verified_sanitized_output_only: bool | None
    account_asset_status: str | None
    account_asset_check_passed: bool | None
    open_positions_count: int | None
    open_positions_check_passed: bool | None
    active_orders_count: int | None
    active_orders_check_passed: bool | None

    def __post_init__(self) -> None:
        _require_non_empty("source_route_name", self.source_route_name)
        _validate_optional_bool_fields(
            self,
            (
                "source_route_verified_no_post",
                "source_route_verified_no_order_endpoint",
                "source_route_verified_no_live_order_once",
                "source_route_verified_no_raw_output",
                "source_route_verified_sanitized_output_only",
                "account_asset_check_passed",
                "open_positions_check_passed",
                "active_orders_check_passed",
            ),
        )
        _validate_optional_int("open_positions_count", self.open_positions_count)
        _validate_optional_int("active_orders_count", self.active_orders_count)


@dataclass(frozen=True)
class LiveOrderRealApiPreflightPublicMarketSanitizedInput:
    source_route_name: str
    source_route_verified_no_post: bool | None
    source_route_verified_no_order_endpoint: bool | None
    source_route_verified_no_live_order_once: bool | None
    source_route_verified_no_raw_output: bool | None
    source_route_verified_sanitized_output_only: bool | None
    market_session_state: str | None
    market_window_allowed: bool | None
    broker_maintenance_active: bool | None
    holiday_or_special_close: bool | None
    market_hours_unknown: bool | None
    ticker_symbol: str | None
    ticker_bid: float | None
    ticker_ask: float | None
    ticker_spread_jpy: float | None
    ticker_age_seconds: float | None
    ticker_check_passed: bool | None

    def __post_init__(self) -> None:
        _require_non_empty("source_route_name", self.source_route_name)
        _validate_optional_bool_fields(
            self,
            (
                "source_route_verified_no_post",
                "source_route_verified_no_order_endpoint",
                "source_route_verified_no_live_order_once",
                "source_route_verified_no_raw_output",
                "source_route_verified_sanitized_output_only",
                "market_window_allowed",
                "broker_maintenance_active",
                "holiday_or_special_close",
                "market_hours_unknown",
                "ticker_check_passed",
            ),
        )
        for field_name in ("ticker_bid", "ticker_ask", "ticker_spread_jpy", "ticker_age_seconds"):
            _validate_optional_number(field_name, getattr(self, field_name))


@dataclass(frozen=True)
class LiveOrderRealApiPreflightLocalStaticSanitizedInput:
    source_route_name: str
    source_route_verified_no_post: bool | None
    source_route_verified_no_order_endpoint: bool | None
    source_route_verified_no_live_order_once: bool | None
    source_route_verified_no_raw_output: bool | None
    source_route_verified_sanitized_output_only: bool | None
    instrument_symbol: str | None
    instrument_min_open_order_size: int | None
    instrument_size_step: int | None
    instrument_rule_check_passed: bool | None
    permission_scope_check_passed: bool | None
    ip_account_binding_check_passed: bool | None
    previous_result_unknown_check_passed: bool | None

    def __post_init__(self) -> None:
        _require_non_empty("source_route_name", self.source_route_name)
        _validate_optional_bool_fields(
            self,
            (
                "source_route_verified_no_post",
                "source_route_verified_no_order_endpoint",
                "source_route_verified_no_live_order_once",
                "source_route_verified_no_raw_output",
                "source_route_verified_sanitized_output_only",
                "instrument_rule_check_passed",
                "permission_scope_check_passed",
                "ip_account_binding_check_passed",
                "previous_result_unknown_check_passed",
            ),
        )
        _validate_optional_int(
            "instrument_min_open_order_size",
            self.instrument_min_open_order_size,
        )
        _validate_optional_int("instrument_size_step", self.instrument_size_step)


@dataclass(frozen=True)
class LiveOrderRealApiPreflightConsolidationDataPolicy:
    raw_request_display_allowed: bool = False
    raw_request_save_allowed: bool = False
    raw_response_display_allowed: bool = False
    raw_response_save_allowed: bool = False
    headers_display_allowed: bool = False
    headers_save_allowed: bool = False
    signature_display_allowed: bool = False
    signature_save_allowed: bool = False
    credentials_display_allowed: bool = False
    credentials_save_allowed: bool = False
    real_order_ids_display_allowed: bool = False
    real_execution_ids_display_allowed: bool = False
    real_position_ids_display_allowed: bool = False
    client_order_ids_display_allowed: bool = False
    sanitized_fields_only: bool = True
    git_commit_real_api_results: bool = False
    api_execution_allowed_this_step: bool = False
    post_allowed_this_step: bool = False
    order_endpoint_allowed_this_step: bool = False
    live_order_once_allowed_this_step: bool = False

    def __post_init__(self) -> None:
        _validate_bool_fields(
            self,
            (
                "raw_request_display_allowed",
                "raw_request_save_allowed",
                "raw_response_display_allowed",
                "raw_response_save_allowed",
                "headers_display_allowed",
                "headers_save_allowed",
                "signature_display_allowed",
                "signature_save_allowed",
                "credentials_display_allowed",
                "credentials_save_allowed",
                "real_order_ids_display_allowed",
                "real_execution_ids_display_allowed",
                "real_position_ids_display_allowed",
                "client_order_ids_display_allowed",
                "sanitized_fields_only",
                "git_commit_real_api_results",
                "api_execution_allowed_this_step",
                "post_allowed_this_step",
                "order_endpoint_allowed_this_step",
                "live_order_once_allowed_this_step",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealApiPreflightConsolidationCheckResult:
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
class LiveOrderRealApiPreflightSafeRouteConsolidationSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError("section lines required")
        _require_string_tuple("lines", self.lines)


@dataclass(frozen=True)
class LiveOrderRealApiPreflightConsolidatedSanitizedResult:
    result_id: str
    created_at: datetime
    consolidation_status: LiveOrderRealApiPreflightSafeRouteConsolidationStatus
    consolidation_ready: bool
    eligible_for_step6e_r2_retry: bool
    allowed_for_live: bool
    market_session_state: str | None
    market_window_allowed: bool | None
    broker_maintenance_active: bool | None
    holiday_or_special_close: bool | None
    market_hours_unknown: bool | None
    account_asset_status: str | None
    account_asset_check_passed: bool | None
    open_positions_count: int | None
    open_positions_check_passed: bool | None
    active_orders_count: int | None
    active_orders_check_passed: bool | None
    instrument_symbol: str | None
    instrument_min_open_order_size: int | None
    instrument_size_step: int | None
    instrument_rule_check_passed: bool | None
    ticker_symbol: str | None
    ticker_spread_jpy: float | None
    ticker_age_seconds: float | None
    ticker_check_passed: bool | None
    permission_scope_check_passed: bool | None
    ip_account_binding_check_passed: bool | None
    previous_result_unknown_check_passed: bool | None
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
    read_only_api_called_this_step: bool
    public_api_called_this_step: bool
    private_api_called_this_step: bool
    broker_called_this_step: bool
    order_endpoint_called_this_step: bool
    live_order_once_called_this_step: bool
    post_executed_this_step: bool
    check_results: tuple[LiveOrderRealApiPreflightConsolidationCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        _validate_consolidated_result(self)


@dataclass(frozen=True)
class LiveOrderRealApiPreflightSafeRouteConsolidation:
    consolidation_id: str
    created_at: datetime
    private_readonly_input: LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput | None
    public_market_input: LiveOrderRealApiPreflightPublicMarketSanitizedInput | None
    local_static_input: LiveOrderRealApiPreflightLocalStaticSanitizedInput | None
    data_policy: LiveOrderRealApiPreflightConsolidationDataPolicy
    consolidated_result: LiveOrderRealApiPreflightConsolidatedSanitizedResult
    check_results: tuple[LiveOrderRealApiPreflightConsolidationCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str
    sections: tuple[LiveOrderRealApiPreflightSafeRouteConsolidationSection, ...]

    def __post_init__(self) -> None:
        _require_non_empty("consolidation_id", self.consolidation_id)
        if not self.consolidation_id.startswith(
            LIVE_ORDER_REAL_API_PREFLIGHT_SAFE_ROUTE_CONSOLIDATION_ID_PREFIX,
        ):
            raise LiveVerificationValidationError("invalid consolidation_id prefix")
        _ensure_aware(self.created_at)
        if self.consolidated_result.result_id != self.consolidation_id:
            raise LiveVerificationValidationError("result_id mismatch")
        if self.consolidated_result.check_results != self.check_results:
            raise LiveVerificationValidationError("check_results mismatch")
        if self.consolidated_result.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        if not self.sections:
            raise LiveVerificationValidationError("sections required")


@dataclass(frozen=True)
class LiveOrderRealApiPreflightSafeRouteConsolidationBuildResult:
    consolidation: LiveOrderRealApiPreflightSafeRouteConsolidation
    consolidated_result: LiveOrderRealApiPreflightConsolidatedSanitizedResult
    result_id: str
    consolidation_status: LiveOrderRealApiPreflightSafeRouteConsolidationStatus
    consolidation_ready: bool
    eligible_for_step6e_r2_retry: bool
    allowed_for_live: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str
    read_only_api_called_this_step: bool
    public_api_called_this_step: bool
    private_api_called_this_step: bool
    broker_called_this_step: bool
    order_endpoint_called_this_step: bool
    live_order_once_called_this_step: bool
    post_executed_this_step: bool

    def __post_init__(self) -> None:
        if self.consolidated_result.result_id != self.result_id:
            raise LiveVerificationValidationError("result_id mismatch")
        if self.consolidated_result.consolidation_status is not self.consolidation_status:
            raise LiveVerificationValidationError("consolidation_status mismatch")
        for field_name in (
            "allowed_for_live",
            "read_only_api_called_this_step",
            "public_api_called_this_step",
            "private_api_called_this_step",
            "broker_called_this_step",
            "order_endpoint_called_this_step",
            "live_order_once_called_this_step",
            "post_executed_this_step",
        ):
            if getattr(self, field_name) is not False:
                raise LiveVerificationValidationError(f"{field_name} must be False")


def build_live_order_real_api_preflight_safe_route_consolidation(
    *,
    private_readonly_input: LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput | None,
    public_market_input: LiveOrderRealApiPreflightPublicMarketSanitizedInput | None,
    local_static_input: LiveOrderRealApiPreflightLocalStaticSanitizedInput | None,
    created_at: datetime | None = None,
    data_policy: LiveOrderRealApiPreflightConsolidationDataPolicy | None = None,
) -> LiveOrderRealApiPreflightSafeRouteConsolidationBuildResult:
    """Consolidate sanitized Step 6E inputs without executing any API."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    policy = data_policy or LiveOrderRealApiPreflightConsolidationDataPolicy()

    missing_reasons = _missing_input_reasons(
        private_readonly_input,
        public_market_input,
        local_static_input,
    )
    unsafe_reasons = _unsafe_route_reasons(
        private_readonly_input,
        public_market_input,
        local_static_input,
        policy,
    )
    incomplete_reasons = _incomplete_field_reasons(
        private_readonly_input,
        public_market_input,
        local_static_input,
    )
    preflight_reasons = _preflight_not_passing_reasons(
        private_readonly_input,
        public_market_input,
        local_static_input,
    )

    if missing_reasons:
        status = ConsolidationStatus.BLOCKED_SAFE_ROUTE_CONSOLIDATION_MISSING_INPUT
        recommended_next_step = "provide_all_sanitized_inputs_no_api_no_post"
    elif unsafe_reasons:
        status = ConsolidationStatus.BLOCKED_SAFE_ROUTE_CONSOLIDATION_UNSAFE_ROUTE
        recommended_next_step = "fix_safe_route_verification_no_api_no_post"
    elif incomplete_reasons:
        status = ConsolidationStatus.BLOCKED_SAFE_ROUTE_CONSOLIDATION_INCOMPLETE_FIELDS
        recommended_next_step = "complete_required_sanitized_fields_no_api_no_post"
    elif preflight_reasons:
        status = ConsolidationStatus.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
        recommended_next_step = "fix_preflight_conditions_no_api_no_post"
    else:
        status = ConsolidationStatus.SAFE_READONLY_PREFLIGHT_ROUTE_CONSOLIDATED_NO_API_NO_POST
        recommended_next_step = (
            "run_step6e_r2_market_open_retry_with_consolidated_safe_route_no_post"
        )

    blocked_reasons = _merge_reasons(
        missing_reasons,
        unsafe_reasons,
        incomplete_reasons,
        preflight_reasons,
    )
    consolidation_ready = (
        status
        is ConsolidationStatus.SAFE_READONLY_PREFLIGHT_ROUTE_CONSOLIDATED_NO_API_NO_POST
    )
    check_results = _build_check_results(
        private_readonly_input=private_readonly_input,
        public_market_input=public_market_input,
        local_static_input=local_static_input,
        data_policy=policy,
        missing_reasons=missing_reasons,
        unsafe_reasons=unsafe_reasons,
        incomplete_reasons=incomplete_reasons,
        preflight_reasons=preflight_reasons,
        eligible_for_step6e_r2_retry=consolidation_ready,
    )
    result_id = make_live_order_real_api_preflight_safe_route_consolidation_id(
        created_at=created,
        status=status,
        private_route_name=_source_name(private_readonly_input),
        public_route_name=_source_name(public_market_input),
        local_route_name=_source_name(local_static_input),
        blocked_reasons=blocked_reasons,
    )
    consolidated_result = LiveOrderRealApiPreflightConsolidatedSanitizedResult(
        result_id=result_id,
        created_at=created,
        consolidation_status=status,
        consolidation_ready=consolidation_ready,
        eligible_for_step6e_r2_retry=consolidation_ready,
        allowed_for_live=False,
        market_session_state=_value(public_market_input, "market_session_state"),
        market_window_allowed=_value(public_market_input, "market_window_allowed"),
        broker_maintenance_active=_value(public_market_input, "broker_maintenance_active"),
        holiday_or_special_close=_value(public_market_input, "holiday_or_special_close"),
        market_hours_unknown=_value(public_market_input, "market_hours_unknown"),
        account_asset_status=_value(private_readonly_input, "account_asset_status"),
        account_asset_check_passed=_value(
            private_readonly_input,
            "account_asset_check_passed",
        ),
        open_positions_count=_value(private_readonly_input, "open_positions_count"),
        open_positions_check_passed=_value(
            private_readonly_input,
            "open_positions_check_passed",
        ),
        active_orders_count=_value(private_readonly_input, "active_orders_count"),
        active_orders_check_passed=_value(
            private_readonly_input,
            "active_orders_check_passed",
        ),
        instrument_symbol=_value(local_static_input, "instrument_symbol"),
        instrument_min_open_order_size=_value(
            local_static_input,
            "instrument_min_open_order_size",
        ),
        instrument_size_step=_value(local_static_input, "instrument_size_step"),
        instrument_rule_check_passed=_value(
            local_static_input,
            "instrument_rule_check_passed",
        ),
        ticker_symbol=_value(public_market_input, "ticker_symbol"),
        ticker_spread_jpy=_value(public_market_input, "ticker_spread_jpy"),
        ticker_age_seconds=_value(public_market_input, "ticker_age_seconds"),
        ticker_check_passed=_value(public_market_input, "ticker_check_passed"),
        permission_scope_check_passed=_value(
            local_static_input,
            "permission_scope_check_passed",
        ),
        ip_account_binding_check_passed=_value(
            local_static_input,
            "ip_account_binding_check_passed",
        ),
        previous_result_unknown_check_passed=_value(
            local_static_input,
            "previous_result_unknown_check_passed",
        ),
        raw_request_saved=False,
        raw_request_displayed=False,
        raw_response_saved=False,
        raw_response_displayed=False,
        headers_saved=False,
        headers_displayed=False,
        signature_saved=False,
        signature_displayed=False,
        credentials_displayed=False,
        order_ids_displayed=False,
        execution_ids_displayed=False,
        position_ids_displayed=False,
        client_order_ids_displayed=False,
        read_only_api_called_this_step=False,
        public_api_called_this_step=False,
        private_api_called_this_step=False,
        broker_called_this_step=False,
        order_endpoint_called_this_step=False,
        live_order_once_called_this_step=False,
        post_executed_this_step=False,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        recommended_next_step=recommended_next_step,
    )
    consolidation = LiveOrderRealApiPreflightSafeRouteConsolidation(
        consolidation_id=result_id,
        created_at=created,
        private_readonly_input=private_readonly_input,
        public_market_input=public_market_input,
        local_static_input=local_static_input,
        data_policy=policy,
        consolidated_result=consolidated_result,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            status=status,
            private_readonly_input=private_readonly_input,
            public_market_input=public_market_input,
            local_static_input=local_static_input,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
        ),
    )
    return LiveOrderRealApiPreflightSafeRouteConsolidationBuildResult(
        consolidation=consolidation,
        consolidated_result=consolidated_result,
        result_id=result_id,
        consolidation_status=status,
        consolidation_ready=consolidation_ready,
        eligible_for_step6e_r2_retry=consolidation_ready,
        allowed_for_live=False,
        blocked_reasons=blocked_reasons,
        recommended_next_step=recommended_next_step,
        read_only_api_called_this_step=False,
        public_api_called_this_step=False,
        private_api_called_this_step=False,
        broker_called_this_step=False,
        order_endpoint_called_this_step=False,
        live_order_once_called_this_step=False,
        post_executed_this_step=False,
    )


def render_live_order_real_api_preflight_safe_route_consolidation_markdown(
    consolidation: LiveOrderRealApiPreflightSafeRouteConsolidation,
) -> str:
    result = consolidation.consolidated_result
    check_lines = "\n".join(
        f"- {check.name}: passed={check.passed}, value={check.sanitized_value}"
        for check in result.check_results
    )
    blocked_text = ", ".join(result.blocked_reasons) or "none"
    route_names = ", ".join(
        name
        for name in (
            _source_name(consolidation.private_readonly_input),
            _source_name(consolidation.public_market_input),
            _source_name(consolidation.local_static_input),
        )
        if name != "missing"
    ) or "missing"
    return "\n".join(
        (
            "# Step 6E-SC Safe Read-only Preflight Route Consolidation",
            "",
            "This Step 6E-SC safe route consolidation is no API / no POST.",
            "This consolidation model does not call read-only API.",
            "This consolidation model does not call public API.",
            "This consolidation model does not call Private API.",
            "This consolidation model does not call broker.",
            "This consolidation model does not call live_order_once.",
            "This consolidation model does not execute HTTP POST.",
            (
                "This consolidation model does not display or save raw "
                "request/response, headers, signatures, credentials, or real IDs."
            ),
            "allowed_for_live=false.",
            "",
            f"result_id: {result.result_id}",
            f"consolidation_status: {result.consolidation_status.value}",
            f"consolidation_ready: {result.consolidation_ready}",
            f"eligible_for_step6e_r2_retry: {result.eligible_for_step6e_r2_retry}",
            f"allowed_for_live: {result.allowed_for_live}",
            f"sanitized_source_route_names: {route_names}",
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
            "",
            "## Data Policy",
            (
                "- raw_request_display_allowed: "
                f"{consolidation.data_policy.raw_request_display_allowed}"
            ),
            (
                "- raw_response_display_allowed: "
                f"{consolidation.data_policy.raw_response_display_allowed}"
            ),
            f"- headers_display_allowed: {consolidation.data_policy.headers_display_allowed}",
            f"- signature_display_allowed: {consolidation.data_policy.signature_display_allowed}",
            (
                "- credentials_display_allowed: "
                f"{consolidation.data_policy.credentials_display_allowed}"
            ),
            f"- sanitized_fields_only: {consolidation.data_policy.sanitized_fields_only}",
            "",
            "## Check Results",
            check_lines,
            "",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {result.recommended_next_step}",
        ),
    )


def make_live_order_real_api_preflight_safe_route_consolidation_id(
    *,
    created_at: datetime,
    status: LiveOrderRealApiPreflightSafeRouteConsolidationStatus,
    private_route_name: str,
    public_route_name: str,
    local_route_name: str,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "blocked_reasons": list(blocked_reasons),
        "created_at": _ensure_aware(created_at).isoformat(),
        "local_route_name": local_route_name,
        "private_route_name": private_route_name,
        "public_route_name": public_route_name,
        "status": status.value,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_API_PREFLIGHT_SAFE_ROUTE_CONSOLIDATION_ID_PREFIX}{digest}"


def _missing_input_reasons(
    private_input: LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput | None,
    public_input: LiveOrderRealApiPreflightPublicMarketSanitizedInput | None,
    local_input: LiveOrderRealApiPreflightLocalStaticSanitizedInput | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if private_input is None:
        reasons.append("missing_private_readonly_input")
    if public_input is None:
        reasons.append("missing_public_market_input")
    if local_input is None:
        reasons.append("missing_local_static_input")
    return tuple(reasons)


def _unsafe_route_reasons(
    private_input: LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput | None,
    public_input: LiveOrderRealApiPreflightPublicMarketSanitizedInput | None,
    local_input: LiveOrderRealApiPreflightLocalStaticSanitizedInput | None,
    data_policy: LiveOrderRealApiPreflightConsolidationDataPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for label, source in (
        ("private_readonly", private_input),
        ("public_market", public_input),
        ("local_static", local_input),
    ):
        if source is None:
            continue
        for field_name in (
            "source_route_verified_no_post",
            "source_route_verified_no_order_endpoint",
            "source_route_verified_no_live_order_once",
            "source_route_verified_no_raw_output",
            "source_route_verified_sanitized_output_only",
        ):
            if getattr(source, field_name) is not True:
                _add_reason(reasons, f"{label}:{field_name}_not_verified")
    for field_name in (
        "raw_request_display_allowed",
        "raw_request_save_allowed",
        "raw_response_display_allowed",
        "raw_response_save_allowed",
        "headers_display_allowed",
        "headers_save_allowed",
        "signature_display_allowed",
        "signature_save_allowed",
        "credentials_display_allowed",
        "credentials_save_allowed",
        "real_order_ids_display_allowed",
        "real_execution_ids_display_allowed",
        "real_position_ids_display_allowed",
        "client_order_ids_display_allowed",
        "git_commit_real_api_results",
        "api_execution_allowed_this_step",
        "post_allowed_this_step",
        "order_endpoint_allowed_this_step",
        "live_order_once_allowed_this_step",
    ):
        if getattr(data_policy, field_name) is True:
            _add_reason(reasons, f"data_policy:{field_name}")
    if data_policy.sanitized_fields_only is not True:
        _add_reason(reasons, "data_policy:sanitized_fields_only_not_true")
    return tuple(reasons)


def _incomplete_field_reasons(
    private_input: LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput | None,
    public_input: LiveOrderRealApiPreflightPublicMarketSanitizedInput | None,
    local_input: LiveOrderRealApiPreflightLocalStaticSanitizedInput | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if private_input is not None:
        for field_name in (
            "account_asset_status",
            "account_asset_check_passed",
            "open_positions_count",
            "open_positions_check_passed",
            "active_orders_count",
            "active_orders_check_passed",
        ):
            if _is_missing(getattr(private_input, field_name)):
                _add_reason(reasons, f"missing_{field_name}")
    if public_input is not None:
        for field_name in (
            "market_session_state",
            "market_window_allowed",
            "broker_maintenance_active",
            "holiday_or_special_close",
            "market_hours_unknown",
            "ticker_symbol",
            "ticker_spread_jpy",
            "ticker_age_seconds",
            "ticker_check_passed",
        ):
            if _is_missing(getattr(public_input, field_name)):
                _add_reason(reasons, f"missing_{field_name}")
    if local_input is not None:
        for field_name in (
            "instrument_symbol",
            "instrument_min_open_order_size",
            "instrument_size_step",
            "instrument_rule_check_passed",
            "permission_scope_check_passed",
            "ip_account_binding_check_passed",
            "previous_result_unknown_check_passed",
        ):
            if _is_missing(getattr(local_input, field_name)):
                _add_reason(reasons, f"missing_{field_name}")
    return tuple(reasons)


def _preflight_not_passing_reasons(
    private_input: LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput | None,
    public_input: LiveOrderRealApiPreflightPublicMarketSanitizedInput | None,
    local_input: LiveOrderRealApiPreflightLocalStaticSanitizedInput | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if private_input is not None:
        if private_input.account_asset_check_passed is not True:
            _add_reason(reasons, "account_asset_check_failed")
        if private_input.open_positions_count != 0:
            _add_reason(reasons, "open_positions_not_zero")
        if private_input.open_positions_check_passed is not True:
            _add_reason(reasons, "open_positions_check_failed")
        if private_input.active_orders_count != 0:
            _add_reason(reasons, "active_orders_not_zero")
        if private_input.active_orders_check_passed is not True:
            _add_reason(reasons, "active_orders_check_failed")
    if public_input is not None:
        if public_input.market_session_state != MARKET_HOURS_OPEN_STATE:
            _add_reason(reasons, "market_session_not_open")
        if public_input.market_window_allowed is not True:
            _add_reason(reasons, "market_window_not_allowed")
        if public_input.broker_maintenance_active is not False:
            _add_reason(reasons, "broker_maintenance_active")
        if public_input.holiday_or_special_close is not False:
            _add_reason(reasons, "holiday_or_special_close")
        if public_input.market_hours_unknown is not False:
            _add_reason(reasons, "market_hours_unknown")
        if public_input.ticker_symbol != SUPPORTED_SYMBOL:
            _add_reason(reasons, "ticker_symbol_unsupported")
        if (
            public_input.ticker_spread_jpy is not None
            and public_input.ticker_spread_jpy > STEP6E_MAX_SPREAD_JPY
        ):
            _add_reason(reasons, "ticker_spread_too_wide")
        if (
            public_input.ticker_age_seconds is not None
            and public_input.ticker_age_seconds > STEP6E_MAX_TICKER_AGE_SECONDS
        ):
            _add_reason(reasons, "ticker_age_stale")
        if public_input.ticker_check_passed is not True:
            _add_reason(reasons, "ticker_check_failed")
    if local_input is not None:
        if local_input.instrument_symbol != SUPPORTED_SYMBOL:
            _add_reason(reasons, "instrument_symbol_unsupported")
        if (
            local_input.instrument_min_open_order_size is not None
            and local_input.instrument_min_open_order_size > LIVE_ORDER_CANDIDATE_SIZE
        ):
            _add_reason(reasons, "instrument_min_size_unsupported")
        if local_input.instrument_size_step != 1:
            _add_reason(reasons, "instrument_size_step_unsupported")
        if local_input.instrument_rule_check_passed is not True:
            _add_reason(reasons, "instrument_rule_check_failed")
        if local_input.permission_scope_check_passed is not True:
            _add_reason(reasons, "permission_scope_check_failed")
        if local_input.ip_account_binding_check_passed is not True:
            _add_reason(reasons, "ip_account_binding_check_failed")
        if local_input.previous_result_unknown_check_passed is not True:
            _add_reason(reasons, "previous_result_unknown_check_failed")
    return tuple(reasons)


def _build_check_results(
    *,
    private_readonly_input: LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput | None,
    public_market_input: LiveOrderRealApiPreflightPublicMarketSanitizedInput | None,
    local_static_input: LiveOrderRealApiPreflightLocalStaticSanitizedInput | None,
    data_policy: LiveOrderRealApiPreflightConsolidationDataPolicy,
    missing_reasons: tuple[str, ...],
    unsafe_reasons: tuple[str, ...],
    incomplete_reasons: tuple[str, ...],
    preflight_reasons: tuple[str, ...],
    eligible_for_step6e_r2_retry: bool,
) -> tuple[LiveOrderRealApiPreflightConsolidationCheckResult, ...]:
    route_sources = (private_readonly_input, public_market_input, local_static_input)
    return (
        _check(
            "private_read_only_input_present",
            private_readonly_input is not None,
            "private read-only sanitized input is present",
            _bool_text(private_readonly_input is not None),
            "true",
        ),
        _check(
            "public_market_input_present",
            public_market_input is not None,
            "public market sanitized input is present",
            _bool_text(public_market_input is not None),
            "true",
        ),
        _check(
            "local_static_input_present",
            local_static_input is not None,
            "local/static sanitized input is present",
            _bool_text(local_static_input is not None),
            "true",
        ),
        _check(
            "all_routes_verified_no_post",
            _all_routes_verified(route_sources, "source_route_verified_no_post"),
            "all source routes are verified no POST",
            _bool_text(_all_routes_verified(route_sources, "source_route_verified_no_post")),
            "true",
        ),
        _check(
            "all_routes_verified_no_order_endpoint",
            _all_routes_verified(route_sources, "source_route_verified_no_order_endpoint"),
            "all source routes are verified no order endpoint",
            _bool_text(
                _all_routes_verified(route_sources, "source_route_verified_no_order_endpoint"),
            ),
            "true",
        ),
        _check(
            "all_routes_verified_no_live_order_once",
            _all_routes_verified(route_sources, "source_route_verified_no_live_order_once"),
            "all source routes are verified no live_order_once",
            _bool_text(
                _all_routes_verified(route_sources, "source_route_verified_no_live_order_once"),
            ),
            "true",
        ),
        _check(
            "all_routes_verified_no_raw_output",
            _all_routes_verified(route_sources, "source_route_verified_no_raw_output"),
            "all source routes are verified no raw output",
            _bool_text(_all_routes_verified(route_sources, "source_route_verified_no_raw_output")),
            "true",
        ),
        _check(
            "all_routes_verified_sanitized_output_only",
            _all_routes_verified(
                route_sources,
                "source_route_verified_sanitized_output_only",
            ),
            "all source routes return sanitized output only",
            _bool_text(
                _all_routes_verified(
                    route_sources,
                    "source_route_verified_sanitized_output_only",
                ),
            ),
            "true",
        ),
        _check(
            "market_session_open",
            public_market_input is not None
            and public_market_input.market_session_state == MARKET_HOURS_OPEN_STATE,
            "market session is open",
            _safe_text(_value(public_market_input, "market_session_state")),
            MARKET_HOURS_OPEN_STATE,
        ),
        _check(
            "market_window_allowed",
            public_market_input is not None and public_market_input.market_window_allowed is True,
            "market window is allowed",
            _bool_or_unknown(_value(public_market_input, "market_window_allowed")),
            "true",
        ),
        _check(
            "maintenance_inactive",
            public_market_input is not None
            and public_market_input.broker_maintenance_active is False,
            "broker maintenance is inactive",
            _bool_or_unknown(_value(public_market_input, "broker_maintenance_active")),
            "false",
        ),
        _check(
            "market_hours_known",
            public_market_input is not None and public_market_input.market_hours_unknown is False,
            "market hours are known",
            _bool_or_unknown(_value(public_market_input, "market_hours_unknown")),
            "false",
        ),
        _check(
            "account_asset_check_passed",
            private_readonly_input is not None
            and private_readonly_input.account_asset_check_passed is True,
            "account asset check passed",
            _bool_or_unknown(_value(private_readonly_input, "account_asset_check_passed")),
            "true",
        ),
        _check(
            "open_positions_count_zero",
            private_readonly_input is not None
            and private_readonly_input.open_positions_count == 0,
            "open positions count is zero",
            _safe_text(_value(private_readonly_input, "open_positions_count")),
            "0",
        ),
        _check(
            "active_orders_count_zero",
            private_readonly_input is not None
            and private_readonly_input.active_orders_count == 0,
            "active orders count is zero",
            _safe_text(_value(private_readonly_input, "active_orders_count")),
            "0",
        ),
        _check(
            "instrument_rule_passed",
            local_static_input is not None
            and local_static_input.instrument_rule_check_passed is True,
            "instrument rule passed",
            _bool_or_unknown(_value(local_static_input, "instrument_rule_check_passed")),
            "true",
        ),
        _check(
            "ticker_spread_passed",
            public_market_input is not None
            and public_market_input.ticker_spread_jpy is not None
            and public_market_input.ticker_spread_jpy <= STEP6E_MAX_SPREAD_JPY,
            "ticker spread is within limit",
            _safe_text(_value(public_market_input, "ticker_spread_jpy")),
            f"<= {STEP6E_MAX_SPREAD_JPY}",
        ),
        _check(
            "ticker_age_passed",
            public_market_input is not None
            and public_market_input.ticker_age_seconds is not None
            and public_market_input.ticker_age_seconds <= STEP6E_MAX_TICKER_AGE_SECONDS,
            "ticker age is within limit",
            _safe_text(_value(public_market_input, "ticker_age_seconds")),
            f"<= {STEP6E_MAX_TICKER_AGE_SECONDS}",
        ),
        _check(
            "permission_scope_passed",
            local_static_input is not None
            and local_static_input.permission_scope_check_passed is True,
            "permission scope passed",
            _bool_or_unknown(_value(local_static_input, "permission_scope_check_passed")),
            "true",
        ),
        _check(
            "ip_account_binding_passed",
            local_static_input is not None
            and local_static_input.ip_account_binding_check_passed is True,
            "IP/account binding passed",
            _bool_or_unknown(_value(local_static_input, "ip_account_binding_check_passed")),
            "true",
        ),
        _check(
            "previous_result_unknown_false",
            local_static_input is not None
            and local_static_input.previous_result_unknown_check_passed is True,
            "previous result unknown check passed",
            _bool_or_unknown(
                _value(local_static_input, "previous_result_unknown_check_passed"),
            ),
            "true",
        ),
        _check(
            "raw_request_response_not_saved_displayed",
            _data_policy_is_safe(data_policy),
            "raw request/response are not saved or displayed",
            _bool_text(_data_policy_is_safe(data_policy)),
            "true",
        ),
        _check(
            "headers_signature_credentials_not_saved_displayed",
            _data_policy_is_safe(data_policy),
            "headers/signatures/credentials are not saved or displayed",
            _bool_text(_data_policy_is_safe(data_policy)),
            "true",
        ),
        _check(
            "no_real_ids_displayed",
            _data_policy_is_safe(data_policy),
            "real IDs are not displayed",
            _bool_text(_data_policy_is_safe(data_policy)),
            "true",
        ),
        _check(
            "no_api_executed_this_step",
            True,
            "Step 6E-SC does not execute API calls",
            "false",
            "false",
        ),
        _check(
            "no_post_executed_this_step",
            True,
            "Step 6E-SC does not execute HTTP POST",
            "false",
            "false",
        ),
        _check(
            "eligible_for_step6e_r2_retry",
            eligible_for_step6e_r2_retry,
            "ready consolidation is eligible for Step 6E-R2 retry",
            _bool_text(eligible_for_step6e_r2_retry),
            "true",
        ),
        _check(
            "no_missing_input_reasons",
            not missing_reasons,
            "no source input is missing",
            _bool_text(not missing_reasons),
            "true",
        ),
        _check(
            "no_unsafe_route_reasons",
            not unsafe_reasons,
            "no source route verification failed",
            _bool_text(not unsafe_reasons),
            "true",
        ),
        _check(
            "no_incomplete_field_reasons",
            not incomplete_reasons,
            "no required sanitized field is missing",
            _bool_text(not incomplete_reasons),
            "true",
        ),
        _check(
            "no_preflight_failure_reasons",
            not preflight_reasons,
            "preflight conditions are passing",
            _bool_text(not preflight_reasons),
            "true",
        ),
    )


def _build_sections(
    *,
    status: LiveOrderRealApiPreflightSafeRouteConsolidationStatus,
    private_readonly_input: LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput | None,
    public_market_input: LiveOrderRealApiPreflightPublicMarketSanitizedInput | None,
    local_static_input: LiveOrderRealApiPreflightLocalStaticSanitizedInput | None,
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
) -> tuple[LiveOrderRealApiPreflightSafeRouteConsolidationSection, ...]:
    return (
        LiveOrderRealApiPreflightSafeRouteConsolidationSection(
            section_id="scope",
            title="Step 6E-SC Scope",
            lines=(
                "sanitized wrapper/model only",
                "no read-only/public/Private API call is executed",
                "allowed_for_live remains false",
            ),
        ),
        LiveOrderRealApiPreflightSafeRouteConsolidationSection(
            section_id="source_routes",
            title="Sanitized Source Routes",
            lines=(
                f"private={_source_name(private_readonly_input)}",
                f"public={_source_name(public_market_input)}",
                f"local={_source_name(local_static_input)}",
            ),
        ),
        LiveOrderRealApiPreflightSafeRouteConsolidationSection(
            section_id="status",
            title="Consolidation Status",
            lines=(status.value,),
        ),
        LiveOrderRealApiPreflightSafeRouteConsolidationSection(
            section_id="blocked_reasons",
            title="Blocked Reasons",
            lines=blocked_reasons or ("none",),
        ),
        LiveOrderRealApiPreflightSafeRouteConsolidationSection(
            section_id="recommended_next_step",
            title="Recommended Next Step",
            lines=(recommended_next_step,),
        ),
    )


def _validate_consolidated_result(
    result: LiveOrderRealApiPreflightConsolidatedSanitizedResult,
) -> None:
    _require_non_empty("result_id", result.result_id)
    if not result.result_id.startswith(
        LIVE_ORDER_REAL_API_PREFLIGHT_SAFE_ROUTE_CONSOLIDATION_ID_PREFIX,
    ):
        raise LiveVerificationValidationError("invalid result_id prefix")
    _ensure_aware(result.created_at)
    if result.allowed_for_live is not False:
        raise LiveVerificationValidationError("allowed_for_live must be False")
    for field_name in (
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
        "read_only_api_called_this_step",
        "public_api_called_this_step",
        "private_api_called_this_step",
        "broker_called_this_step",
        "order_endpoint_called_this_step",
        "live_order_once_called_this_step",
        "post_executed_this_step",
    ):
        if getattr(result, field_name) is not False:
            raise LiveVerificationValidationError(f"{field_name} must be False")
    if not result.check_results:
        raise LiveVerificationValidationError("check_results required")
    _require_non_empty("recommended_next_step", result.recommended_next_step)
    if (
        result.consolidation_status
        is ConsolidationStatus.SAFE_READONLY_PREFLIGHT_ROUTE_CONSOLIDATED_NO_API_NO_POST
    ):
        if not result.consolidation_ready or not result.eligible_for_step6e_r2_retry:
            raise LiveVerificationValidationError("ready consolidation flags invalid")
        if result.blocked_reasons:
            raise LiveVerificationValidationError("ready consolidation cannot be blocked")
    elif result.consolidation_ready or result.eligible_for_step6e_r2_retry:
        raise LiveVerificationValidationError("blocked consolidation flags invalid")


def _data_policy_is_safe(data_policy: LiveOrderRealApiPreflightConsolidationDataPolicy) -> bool:
    return (
        data_policy.raw_request_display_allowed is False
        and data_policy.raw_request_save_allowed is False
        and data_policy.raw_response_display_allowed is False
        and data_policy.raw_response_save_allowed is False
        and data_policy.headers_display_allowed is False
        and data_policy.headers_save_allowed is False
        and data_policy.signature_display_allowed is False
        and data_policy.signature_save_allowed is False
        and data_policy.credentials_display_allowed is False
        and data_policy.credentials_save_allowed is False
        and data_policy.real_order_ids_display_allowed is False
        and data_policy.real_execution_ids_display_allowed is False
        and data_policy.real_position_ids_display_allowed is False
        and data_policy.client_order_ids_display_allowed is False
        and data_policy.sanitized_fields_only is True
        and data_policy.git_commit_real_api_results is False
        and data_policy.api_execution_allowed_this_step is False
        and data_policy.post_allowed_this_step is False
        and data_policy.order_endpoint_allowed_this_step is False
        and data_policy.live_order_once_allowed_this_step is False
    )


def _all_routes_verified(sources: tuple[object | None, ...], field_name: str) -> bool:
    present_sources = tuple(source for source in sources if source is not None)
    return bool(present_sources) and all(
        getattr(source, field_name) is True for source in present_sources
    )


def _source_name(source: object | None) -> str:
    return getattr(source, "source_route_name", "missing") if source is not None else "missing"


def _value(source: object | None, field_name: str) -> Any:
    return getattr(source, field_name, None) if source is not None else None


def _is_missing(value: object | None) -> bool:
    return value is None or (isinstance(value, str) and value in {"", "unknown"})


def _check(
    name: str,
    passed: bool,
    reason: str,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealApiPreflightConsolidationCheckResult:
    return LiveOrderRealApiPreflightConsolidationCheckResult(
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


def _validate_bool_fields(instance: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(instance, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_optional_bool_fields(instance: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        value = getattr(instance, field_name)
        if value is not None and type(value) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool or None")


def _validate_optional_int(field_name: str, value: int | None) -> None:
    if value is not None and type(value) is not int:
        raise LiveVerificationValidationError(f"{field_name} must be int or None")


def _validate_optional_number(field_name: str, value: float | None) -> None:
    if value is not None and type(value) not in {int, float}:
        raise LiveVerificationValidationError(f"{field_name} must be number or None")


def _require_non_empty(label: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{label} required")


def _require_string_tuple(label: str, value: tuple[str, ...]) -> None:
    if not isinstance(value, tuple):
        raise LiveVerificationValidationError(f"{label} must be tuple")
    for item in value:
        _require_non_empty(label, item)


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise LiveVerificationValidationError("datetime required")
    if value.tzinfo is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _bool_or_unknown(value: object | None) -> str:
    if type(value) is bool:
        return _bool_text(value)
    return "unknown"


def _safe_text(value: object | None) -> str:
    if value is None:
        return "unknown"
    return str(value)
