"""Step 6E-RR static safe read-only preflight route review.

This module reviews route metadata only. It does not call APIs, import broker
code, import Private API clients, call live_order_once, or authorize HTTP POST.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

LIVE_ORDER_REAL_API_PREFLIGHT_SAFE_ROUTE_REVIEW_ID_PREFIX = "LORAPSR6ERR-"

REQUIRED_STEP6E_R_COVERAGE_FIELDS = (
    "market_session_state",
    "market_window_allowed",
    "broker_maintenance_active",
    "holiday_or_special_close",
    "market_hours_unknown",
    "account_asset_status",
    "account_asset_check_passed",
    "open_positions_count",
    "open_positions_check_passed",
    "active_orders_count",
    "active_orders_check_passed",
    "instrument_symbol",
    "instrument_min_open_order_size",
    "instrument_size_step",
    "instrument_rule_check_passed",
    "ticker_symbol",
    "ticker_spread_jpy",
    "ticker_age_seconds",
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
)


class LiveOrderRealApiPreflightSafeRouteReviewStatus(str, Enum):
    READY_FOR_STEP6E_R2_RETRY_WITH_EXISTING_SAFE_ROUTE = (
        "READY_FOR_STEP6E_R2_RETRY_WITH_EXISTING_SAFE_ROUTE"
    )
    READY_FOR_STEP6E_SAFE_ROUTE_CONSOLIDATION_IMPLEMENTATION = (
        "READY_FOR_STEP6E_SAFE_ROUTE_CONSOLIDATION_IMPLEMENTATION"
    )
    BLOCKED_STEP6E_SAFE_ROUTE_INCOMPLETE = "BLOCKED_STEP6E_SAFE_ROUTE_INCOMPLETE"
    BLOCKED_STEP6E_SAFE_ROUTE_UNSAFE = "BLOCKED_STEP6E_SAFE_ROUTE_UNSAFE"


ReviewStatus = LiveOrderRealApiPreflightSafeRouteReviewStatus


@dataclass(frozen=True)
class LiveOrderRealApiPreflightRouteCandidate:
    route_name: str
    route_file_path: str
    route_type: str
    route_scope: str
    uses_http_get: bool
    uses_http_post: bool
    uses_order_endpoint: bool
    uses_live_order_once: bool
    uses_speed_order: bool
    uses_close_order: bool
    uses_cancel_order: bool
    uses_change_order: bool
    uses_private_api: bool
    uses_public_api: bool
    uses_broker_order_path: bool
    displays_raw_request: bool
    saves_raw_request: bool
    displays_raw_response: bool
    saves_raw_response: bool
    displays_headers: bool
    saves_headers: bool
    displays_signature: bool
    saves_signature: bool
    displays_credentials: bool
    requires_env_display: bool
    requires_env_file_display: bool
    returns_sanitized_fields_only: bool
    coverage_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    review_notes: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "route_name",
            "route_file_path",
            "route_type",
            "route_scope",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        for field_name in (
            "uses_http_get",
            "uses_http_post",
            "uses_order_endpoint",
            "uses_live_order_once",
            "uses_speed_order",
            "uses_close_order",
            "uses_cancel_order",
            "uses_change_order",
            "uses_private_api",
            "uses_public_api",
            "uses_broker_order_path",
            "displays_raw_request",
            "saves_raw_request",
            "displays_raw_response",
            "saves_raw_response",
            "displays_headers",
            "saves_headers",
            "displays_signature",
            "saves_signature",
            "displays_credentials",
            "requires_env_display",
            "requires_env_file_display",
            "returns_sanitized_fields_only",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")
        _require_string_tuple("coverage_fields", self.coverage_fields)
        _require_string_tuple("missing_fields", self.missing_fields)
        _require_string_tuple("review_notes", self.review_notes)


@dataclass(frozen=True)
class LiveOrderRealApiPreflightRouteCoverageItem:
    field_name: str
    covered: bool
    source_route_name: str
    source_route_file_path: str
    coverage_type: str
    requires_future_implementation: bool
    notes: str

    def __post_init__(self) -> None:
        for field_name in (
            "field_name",
            "source_route_name",
            "source_route_file_path",
            "coverage_type",
            "notes",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        if type(self.covered) is not bool:
            raise LiveVerificationValidationError("covered must be bool")
        if type(self.requires_future_implementation) is not bool:
            raise LiveVerificationValidationError(
                "requires_future_implementation must be bool",
            )


@dataclass(frozen=True)
class LiveOrderRealApiPreflightRouteGap:
    field_name: str
    reason: str
    requires_future_implementation: bool
    recommended_resolution: str

    def __post_init__(self) -> None:
        _require_non_empty("field_name", self.field_name)
        _require_non_empty("reason", self.reason)
        _require_non_empty("recommended_resolution", self.recommended_resolution)
        if type(self.requires_future_implementation) is not bool:
            raise LiveVerificationValidationError(
                "requires_future_implementation must be bool",
            )


@dataclass(frozen=True)
class LiveOrderRealApiPreflightRouteDataPolicy:
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

    def __post_init__(self) -> None:
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
            "sanitized_fields_only",
            "git_commit_real_api_results",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")


@dataclass(frozen=True)
class LiveOrderRealApiPreflightSafeRouteReviewCheckResult:
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
class LiveOrderRealApiPreflightSafeRouteReviewSection:
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
class LiveOrderRealApiPreflightSafeRouteReview:
    review_id: str
    created_at: datetime
    source_step6e_retry_head: str
    review_status: LiveOrderRealApiPreflightSafeRouteReviewStatus
    review_ready: bool
    eligible_for_step6e_r2_retry: bool
    eligible_for_safe_route_consolidation_implementation: bool
    allowed_for_live: bool
    api_executed_this_step: bool
    read_only_api_called_this_step: bool
    public_api_called_this_step: bool
    private_api_called_this_step: bool
    broker_called_this_step: bool
    order_endpoint_called_this_step: bool
    live_order_once_called_this_step: bool
    post_executed_this_step: bool
    route_candidates: tuple[LiveOrderRealApiPreflightRouteCandidate, ...]
    coverage_items: tuple[LiveOrderRealApiPreflightRouteCoverageItem, ...]
    route_gaps: tuple[LiveOrderRealApiPreflightRouteGap, ...]
    data_policy: LiveOrderRealApiPreflightRouteDataPolicy
    safe_route_summary: str
    recommended_next_step: str
    check_results: tuple[LiveOrderRealApiPreflightSafeRouteReviewCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    sections: tuple[LiveOrderRealApiPreflightSafeRouteReviewSection, ...]

    def __post_init__(self) -> None:
        _validate_review(self)


@dataclass(frozen=True)
class LiveOrderRealApiPreflightSafeRouteReviewBuildResult:
    review: LiveOrderRealApiPreflightSafeRouteReview
    review_id: str
    review_status: LiveOrderRealApiPreflightSafeRouteReviewStatus
    review_ready: bool
    eligible_for_step6e_r2_retry: bool
    eligible_for_safe_route_consolidation_implementation: bool
    allowed_for_live: bool
    api_executed_this_step: bool
    read_only_api_called_this_step: bool
    public_api_called_this_step: bool
    private_api_called_this_step: bool
    broker_called_this_step: bool
    order_endpoint_called_this_step: bool
    live_order_once_called_this_step: bool
    post_executed_this_step: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.review.review_id != self.review_id:
            raise LiveVerificationValidationError("review_id mismatch")
        if self.review.review_status is not self.review_status:
            raise LiveVerificationValidationError("review_status mismatch")
        for field_name in (
            "allowed_for_live",
            "api_executed_this_step",
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


def build_live_order_real_api_preflight_safe_route_review(
    *,
    route_candidates: tuple[LiveOrderRealApiPreflightRouteCandidate, ...],
    source_step6e_retry_head: str,
    created_at: datetime | None = None,
    data_policy: LiveOrderRealApiPreflightRouteDataPolicy | None = None,
    safe_route_consolidation_feasible: bool = True,
) -> LiveOrderRealApiPreflightSafeRouteReviewBuildResult:
    """Build a Step 6E-RR static route review without executing any API."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    _require_non_empty("source_step6e_retry_head", source_step6e_retry_head)
    policy = data_policy or LiveOrderRealApiPreflightRouteDataPolicy()
    unsafe_reasons = _unsafe_reasons(route_candidates, policy)
    coverage_items = _build_coverage_items(route_candidates)
    route_gaps = _build_route_gaps(coverage_items)
    incomplete_reasons = _incomplete_reasons(
        route_candidates=route_candidates,
        coverage_items=coverage_items,
        safe_route_consolidation_feasible=safe_route_consolidation_feasible,
    )

    all_fields_covered = all(item.covered for item in coverage_items)
    has_safe_candidates = any(_candidate_is_safe(candidate) for candidate in route_candidates)

    if unsafe_reasons:
        status = ReviewStatus.BLOCKED_STEP6E_SAFE_ROUTE_UNSAFE
        summary = "Step 6E-RR found unsafe route boundaries"
        recommended_next_step = "redesign_without_unsafe_route_no_api_no_post"
    elif all_fields_covered and has_safe_candidates:
        status = ReviewStatus.READY_FOR_STEP6E_R2_RETRY_WITH_EXISTING_SAFE_ROUTE
        summary = "Existing safe route coverage is complete for Step 6E-R2"
        recommended_next_step = (
            "proceed_to_explicit_step6e_r2_retry_with_existing_safe_route_no_post"
        )
    elif incomplete_reasons:
        status = ReviewStatus.BLOCKED_STEP6E_SAFE_ROUTE_INCOMPLETE
        summary = "Step 6E-RR route evidence is incomplete"
        recommended_next_step = "complete_static_route_evidence_no_api_no_post"
    else:
        status = ReviewStatus.READY_FOR_STEP6E_SAFE_ROUTE_CONSOLIDATION_IMPLEMENTATION
        summary = "Safe route candidates exist, but Step 6E-R needs consolidation"
        recommended_next_step = (
            "implement_step6e_safe_route_consolidation_no_api_no_post"
        )

    blocked_reasons = _merge_reasons(unsafe_reasons, incomplete_reasons)
    if status is ReviewStatus.READY_FOR_STEP6E_SAFE_ROUTE_CONSOLIDATION_IMPLEMENTATION:
        blocked_reasons = tuple(gap.field_name for gap in route_gaps)
    review_ready = status in {
        ReviewStatus.READY_FOR_STEP6E_R2_RETRY_WITH_EXISTING_SAFE_ROUTE,
        ReviewStatus.READY_FOR_STEP6E_SAFE_ROUTE_CONSOLIDATION_IMPLEMENTATION,
    }
    check_results = _build_check_results(
        route_candidates=route_candidates,
        coverage_items=coverage_items,
        route_gaps=route_gaps,
        data_policy=policy,
        unsafe_reasons=unsafe_reasons,
        safe_route_consolidation_feasible=safe_route_consolidation_feasible,
    )
    review_id = make_live_order_real_api_preflight_safe_route_review_id(
        source_step6e_retry_head=source_step6e_retry_head,
        created_at=created,
        review_status=status,
        route_names=tuple(candidate.route_name for candidate in route_candidates),
        missing_fields=tuple(gap.field_name for gap in route_gaps),
    )
    review = LiveOrderRealApiPreflightSafeRouteReview(
        review_id=review_id,
        created_at=created,
        source_step6e_retry_head=source_step6e_retry_head,
        review_status=status,
        review_ready=review_ready,
        eligible_for_step6e_r2_retry=(
            status is ReviewStatus.READY_FOR_STEP6E_R2_RETRY_WITH_EXISTING_SAFE_ROUTE
        ),
        eligible_for_safe_route_consolidation_implementation=(
            status
            is ReviewStatus.READY_FOR_STEP6E_SAFE_ROUTE_CONSOLIDATION_IMPLEMENTATION
        ),
        allowed_for_live=False,
        api_executed_this_step=False,
        read_only_api_called_this_step=False,
        public_api_called_this_step=False,
        private_api_called_this_step=False,
        broker_called_this_step=False,
        order_endpoint_called_this_step=False,
        live_order_once_called_this_step=False,
        post_executed_this_step=False,
        route_candidates=route_candidates,
        coverage_items=coverage_items,
        route_gaps=route_gaps,
        data_policy=policy,
        safe_route_summary=summary,
        recommended_next_step=recommended_next_step,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        sections=_build_sections(
            route_candidates=route_candidates,
            coverage_items=coverage_items,
            route_gaps=route_gaps,
            recommended_next_step=recommended_next_step,
        ),
    )
    return LiveOrderRealApiPreflightSafeRouteReviewBuildResult(
        review=review,
        review_id=review.review_id,
        review_status=review.review_status,
        review_ready=review.review_ready,
        eligible_for_step6e_r2_retry=review.eligible_for_step6e_r2_retry,
        eligible_for_safe_route_consolidation_implementation=(
            review.eligible_for_safe_route_consolidation_implementation
        ),
        allowed_for_live=False,
        api_executed_this_step=False,
        read_only_api_called_this_step=False,
        public_api_called_this_step=False,
        private_api_called_this_step=False,
        broker_called_this_step=False,
        order_endpoint_called_this_step=False,
        live_order_once_called_this_step=False,
        post_executed_this_step=False,
        blocked_reasons=review.blocked_reasons,
        recommended_next_step=review.recommended_next_step,
    )


def default_live_order_real_api_preflight_route_candidates(
) -> tuple[LiveOrderRealApiPreflightRouteCandidate, ...]:
    """Return the Step 6E-RR static review of current route candidates."""
    private_fields = (
        "account_asset_status",
        "account_asset_check_passed",
        "open_positions_count",
        "open_positions_check_passed",
        "active_orders_count",
        "active_orders_check_passed",
        "raw_response_saved",
        "headers_saved",
        "credentials_displayed",
    )
    public_fields = (
        "market_session_state",
        "ticker_symbol",
    )
    policy_fields = (
        "raw_request_saved",
        "raw_request_displayed",
        "raw_response_displayed",
        "headers_displayed",
        "signature_saved",
        "signature_displayed",
        "order_ids_displayed",
        "execution_ids_displayed",
        "position_ids_displayed",
        "client_order_ids_displayed",
    )
    return (
        LiveOrderRealApiPreflightRouteCandidate(
            route_name="private_readonly_connection_script",
            route_file_path="backend/scripts/check_private_readonly_connection.py",
            route_type="existing_private_get_readonly_script",
            route_scope="account/assets, openPositions, activeOrders sanitized summary",
            uses_http_get=True,
            uses_http_post=False,
            uses_order_endpoint=False,
            uses_live_order_once=False,
            uses_speed_order=False,
            uses_close_order=False,
            uses_cancel_order=False,
            uses_change_order=False,
            uses_private_api=True,
            uses_public_api=False,
            uses_broker_order_path=False,
            displays_raw_request=False,
            saves_raw_request=False,
            displays_raw_response=False,
            saves_raw_response=False,
            displays_headers=False,
            saves_headers=False,
            displays_signature=False,
            saves_signature=False,
            displays_credentials=False,
            requires_env_display=False,
            requires_env_file_display=False,
            returns_sanitized_fields_only=True,
            coverage_fields=private_fields,
            missing_fields=tuple(
                field
                for field in REQUIRED_STEP6E_R_COVERAGE_FIELDS
                if field not in private_fields
            ),
            review_notes=(
                "static review only; script was not executed in Step 6E-RR",
                "covers three private GET checks but not market/ticker/rules/permission fields",
            ),
        ),
        LiveOrderRealApiPreflightRouteCandidate(
            route_name="gmo_public_market_data_adapter",
            route_file_path="backend/app/shadow/gmo_public.py",
            route_type="existing_public_get_market_data_adapter",
            route_scope="public status, ticker, klines adapter",
            uses_http_get=True,
            uses_http_post=False,
            uses_order_endpoint=False,
            uses_live_order_once=False,
            uses_speed_order=False,
            uses_close_order=False,
            uses_cancel_order=False,
            uses_change_order=False,
            uses_private_api=False,
            uses_public_api=True,
            uses_broker_order_path=False,
            displays_raw_request=False,
            saves_raw_request=False,
            displays_raw_response=False,
            saves_raw_response=False,
            displays_headers=False,
            saves_headers=False,
            displays_signature=False,
            saves_signature=False,
            displays_credentials=False,
            requires_env_display=False,
            requires_env_file_display=False,
            returns_sanitized_fields_only=True,
            coverage_fields=public_fields,
            missing_fields=tuple(
                field
                for field in REQUIRED_STEP6E_R_COVERAGE_FIELDS
                if field not in public_fields
            ),
            review_notes=(
                "static review only; adapter was not executed in Step 6E-RR",
                "provides public status/ticker source data but not full Step 6E sanitized result",
            ),
        ),
        LiveOrderRealApiPreflightRouteCandidate(
            route_name="step6e_rr_static_data_policy",
            route_file_path="backend/app/live_verification/live_order_real_api_preflight_safe_route_review.py",
            route_type="offline_static_policy",
            route_scope="raw/header/signature/ID non-exposure policy",
            uses_http_get=False,
            uses_http_post=False,
            uses_order_endpoint=False,
            uses_live_order_once=False,
            uses_speed_order=False,
            uses_close_order=False,
            uses_cancel_order=False,
            uses_change_order=False,
            uses_private_api=False,
            uses_public_api=False,
            uses_broker_order_path=False,
            displays_raw_request=False,
            saves_raw_request=False,
            displays_raw_response=False,
            saves_raw_response=False,
            displays_headers=False,
            saves_headers=False,
            displays_signature=False,
            saves_signature=False,
            displays_credentials=False,
            requires_env_display=False,
            requires_env_file_display=False,
            returns_sanitized_fields_only=True,
            coverage_fields=policy_fields,
            missing_fields=tuple(
                field
                for field in REQUIRED_STEP6E_R_COVERAGE_FIELDS
                if field not in policy_fields
            ),
            review_notes=(
                "static policy candidate only; it does not call any API",
                "records no raw request/response/header/signature/ID display or save",
            ),
        ),
    )


def render_live_order_real_api_preflight_safe_route_review_markdown(
    review: LiveOrderRealApiPreflightSafeRouteReview,
) -> str:
    """Render a sanitized static review without raw data or executable commands."""
    candidate_lines = "\n".join(
        (
            f"- {candidate.route_name}: file={candidate.route_file_path}, "
            f"type={candidate.route_type}, sanitized_only="
            f"{candidate.returns_sanitized_fields_only}"
        )
        for candidate in review.route_candidates
    )
    coverage_lines = "\n".join(
        (
            f"- {item.field_name}: covered={item.covered}, "
            f"source={item.source_route_name}, future="
            f"{item.requires_future_implementation}"
        )
        for item in review.coverage_items
    )
    gap_lines = "\n".join(
        f"- {gap.field_name}: {gap.recommended_resolution}" for gap in review.route_gaps
    ) or "- none"
    blocked_text = ", ".join(review.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6E-RR Safe Read-only Preflight Route Review",
            "",
            "This Step 6E-RR safe route review is offline/static only.",
            "This review does not call read-only API.",
            "This review does not call public API.",
            "This review does not call Private API.",
            "This review does not call broker.",
            "This review does not call live_order_once.",
            "This review does not execute HTTP POST.",
            (
                "This review does not display or save raw request/response, "
                "headers, signatures, credentials, or real IDs."
            ),
            "allowed_for_live=false.",
            "",
            f"review_id: {review.review_id}",
            f"review_status: {review.review_status.value}",
            f"review_ready: {review.review_ready}",
            f"eligible_for_step6e_r2_retry: {review.eligible_for_step6e_r2_retry}",
            (
                "eligible_for_safe_route_consolidation_implementation: "
                f"{review.eligible_for_safe_route_consolidation_implementation}"
            ),
            f"allowed_for_live: {review.allowed_for_live}",
            f"api_executed_this_step: {review.api_executed_this_step}",
            f"read_only_api_called_this_step: {review.read_only_api_called_this_step}",
            f"public_api_called_this_step: {review.public_api_called_this_step}",
            f"private_api_called_this_step: {review.private_api_called_this_step}",
            f"broker_called_this_step: {review.broker_called_this_step}",
            f"order_endpoint_called_this_step: {review.order_endpoint_called_this_step}",
            (
                "live_order_once_called_this_step: "
                f"{review.live_order_once_called_this_step}"
            ),
            f"post_executed_this_step: {review.post_executed_this_step}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {review.recommended_next_step}",
            "",
            "## Route Candidates",
            candidate_lines,
            "",
            "## Coverage Matrix",
            coverage_lines,
            "",
            "## Missing Fields",
            gap_lines,
            "",
            "## Data Policy",
            f"- raw_request_display_allowed: {review.data_policy.raw_request_display_allowed}",
            f"- raw_request_save_allowed: {review.data_policy.raw_request_save_allowed}",
            f"- raw_response_display_allowed: {review.data_policy.raw_response_display_allowed}",
            f"- raw_response_save_allowed: {review.data_policy.raw_response_save_allowed}",
            f"- headers_display_allowed: {review.data_policy.headers_display_allowed}",
            f"- signature_display_allowed: {review.data_policy.signature_display_allowed}",
            f"- credentials_display_allowed: {review.data_policy.credentials_display_allowed}",
            f"- sanitized_fields_only: {review.data_policy.sanitized_fields_only}",
        ),
    )


def make_live_order_real_api_preflight_safe_route_review_id(
    *,
    source_step6e_retry_head: str,
    created_at: datetime,
    review_status: LiveOrderRealApiPreflightSafeRouteReviewStatus,
    route_names: tuple[str, ...],
    missing_fields: tuple[str, ...],
) -> str:
    id_material = {
        "created_at": _ensure_aware(created_at).isoformat(),
        "missing_fields": list(missing_fields),
        "review_status": review_status.value,
        "route_names": list(route_names),
        "source_step6e_retry_head": source_step6e_retry_head,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_API_PREFLIGHT_SAFE_ROUTE_REVIEW_ID_PREFIX}{digest}"


def _build_coverage_items(
    route_candidates: tuple[LiveOrderRealApiPreflightRouteCandidate, ...],
) -> tuple[LiveOrderRealApiPreflightRouteCoverageItem, ...]:
    items: list[LiveOrderRealApiPreflightRouteCoverageItem] = []
    for required_field in REQUIRED_STEP6E_R_COVERAGE_FIELDS:
        source = next(
            (
                candidate
                for candidate in route_candidates
                if _candidate_is_safe(candidate)
                and required_field in candidate.coverage_fields
            ),
            None,
        )
        covered = source is not None
        items.append(
            LiveOrderRealApiPreflightRouteCoverageItem(
                field_name=required_field,
                covered=covered,
                source_route_name=source.route_name if source else "missing",
                source_route_file_path=source.route_file_path if source else "missing",
                coverage_type="existing_safe_route" if covered else "missing",
                requires_future_implementation=not covered,
                notes=(
                    "covered by static safe route candidate"
                    if covered
                    else "requires future safe route consolidation"
                ),
            ),
        )
    return tuple(items)


def _build_route_gaps(
    coverage_items: tuple[LiveOrderRealApiPreflightRouteCoverageItem, ...],
) -> tuple[LiveOrderRealApiPreflightRouteGap, ...]:
    return tuple(
        LiveOrderRealApiPreflightRouteGap(
            field_name=item.field_name,
            reason="required Step 6E-R sanitized field lacks complete existing coverage",
            requires_future_implementation=True,
            recommended_resolution=(
                "add safe consolidated route extraction for this field "
                "without raw output or POST"
            ),
        )
        for item in coverage_items
        if not item.covered
    )


def _unsafe_reasons(
    route_candidates: tuple[LiveOrderRealApiPreflightRouteCandidate, ...],
    data_policy: LiveOrderRealApiPreflightRouteDataPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for candidate in route_candidates:
        for flag_name in (
            "uses_http_post",
            "uses_order_endpoint",
            "uses_live_order_once",
            "uses_speed_order",
            "uses_close_order",
            "uses_cancel_order",
            "uses_change_order",
            "uses_broker_order_path",
            "displays_raw_request",
            "saves_raw_request",
            "displays_raw_response",
            "saves_raw_response",
            "displays_headers",
            "saves_headers",
            "displays_signature",
            "saves_signature",
            "displays_credentials",
            "requires_env_display",
            "requires_env_file_display",
        ):
            if getattr(candidate, flag_name) is True:
                _add_reason(reasons, f"{candidate.route_name}:{flag_name}")
    for flag_name in (
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
    ):
        if getattr(data_policy, flag_name) is True:
            _add_reason(reasons, f"data_policy:{flag_name}")
    return tuple(reasons)


def _incomplete_reasons(
    *,
    route_candidates: tuple[LiveOrderRealApiPreflightRouteCandidate, ...],
    coverage_items: tuple[LiveOrderRealApiPreflightRouteCoverageItem, ...],
    safe_route_consolidation_feasible: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not route_candidates:
        _add_reason(reasons, "no_route_candidates")
    if not any(_candidate_is_safe(candidate) for candidate in route_candidates):
        _add_reason(reasons, "no_safe_route_candidates")
    if any(not item.covered for item in coverage_items) and not safe_route_consolidation_feasible:
        _add_reason(reasons, "missing_required_fields_without_feasible_consolidation")
    if any(not candidate.returns_sanitized_fields_only for candidate in route_candidates):
        _add_reason(reasons, "sanitized_output_only_not_verified")
    return tuple(reasons)


def _candidate_is_safe(candidate: LiveOrderRealApiPreflightRouteCandidate) -> bool:
    unsafe_flags = (
        candidate.uses_http_post,
        candidate.uses_order_endpoint,
        candidate.uses_live_order_once,
        candidate.uses_speed_order,
        candidate.uses_close_order,
        candidate.uses_cancel_order,
        candidate.uses_change_order,
        candidate.uses_broker_order_path,
        candidate.displays_raw_request,
        candidate.saves_raw_request,
        candidate.displays_raw_response,
        candidate.saves_raw_response,
        candidate.displays_headers,
        candidate.saves_headers,
        candidate.displays_signature,
        candidate.saves_signature,
        candidate.displays_credentials,
        candidate.requires_env_display,
        candidate.requires_env_file_display,
    )
    return not any(unsafe_flags) and candidate.returns_sanitized_fields_only is True


def _build_check_results(
    *,
    route_candidates: tuple[LiveOrderRealApiPreflightRouteCandidate, ...],
    coverage_items: tuple[LiveOrderRealApiPreflightRouteCoverageItem, ...],
    route_gaps: tuple[LiveOrderRealApiPreflightRouteGap, ...],
    data_policy: LiveOrderRealApiPreflightRouteDataPolicy,
    unsafe_reasons: tuple[str, ...],
    safe_route_consolidation_feasible: bool,
) -> tuple[LiveOrderRealApiPreflightSafeRouteReviewCheckResult, ...]:
    return (
        _check(
            "route_candidates_present",
            bool(route_candidates),
            "route candidates are statically listed",
            _bool_text(bool(route_candidates)),
            "true",
        ),
        _check(
            "no_unsafe_route_flags",
            not unsafe_reasons,
            "no POST/order/raw/credential route flag is required",
            _bool_text(not unsafe_reasons),
            "true",
        ),
        _check(
            "all_required_coverage_fields_represented",
            set(REQUIRED_STEP6E_R_COVERAGE_FIELDS)
            == {item.field_name for item in coverage_items},
            "coverage matrix represents every required Step 6E-R field",
            str(len(coverage_items)),
            str(len(REQUIRED_STEP6E_R_COVERAGE_FIELDS)),
        ),
        _check(
            "all_required_fields_covered",
            not route_gaps,
            "existing safe routes cover every required field",
            _bool_text(not route_gaps),
            "true",
        ),
        _check(
            "safe_route_consolidation_feasible",
            safe_route_consolidation_feasible,
            "missing fields can be handled by a future safe wrapper",
            _bool_text(safe_route_consolidation_feasible),
            "true",
        ),
        _check(
            "data_policy_safe",
            _data_policy_is_safe(data_policy),
            "data policy forbids raw/header/signature/credential/ID exposure",
            _bool_text(_data_policy_is_safe(data_policy)),
            "true",
        ),
        _check(
            "api_not_executed_this_step",
            True,
            "Step 6E-RR is offline/static only",
            "false",
            "false",
        ),
        _check(
            "post_not_executed_this_step",
            True,
            "Step 6E-RR never executes HTTP POST",
            "false",
            "false",
        ),
    )


def _data_policy_is_safe(data_policy: LiveOrderRealApiPreflightRouteDataPolicy) -> bool:
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
    )


def _build_sections(
    *,
    route_candidates: tuple[LiveOrderRealApiPreflightRouteCandidate, ...],
    coverage_items: tuple[LiveOrderRealApiPreflightRouteCoverageItem, ...],
    route_gaps: tuple[LiveOrderRealApiPreflightRouteGap, ...],
    recommended_next_step: str,
) -> tuple[LiveOrderRealApiPreflightSafeRouteReviewSection, ...]:
    covered = tuple(item.field_name for item in coverage_items if item.covered)
    missing = tuple(item.field_name for item in coverage_items if not item.covered)
    return (
        LiveOrderRealApiPreflightSafeRouteReviewSection(
            section_id="scope",
            title="Step 6E-RR Scope",
            lines=(
                "offline/static route review only",
                "no read-only/public/Private API call is executed",
                "allowed_for_live remains false",
            ),
        ),
        LiveOrderRealApiPreflightSafeRouteReviewSection(
            section_id="route_candidates",
            title="Route Candidates",
            lines=tuple(candidate.route_name for candidate in route_candidates) or ("none",),
        ),
        LiveOrderRealApiPreflightSafeRouteReviewSection(
            section_id="covered_fields",
            title="Covered Fields",
            lines=covered or ("none",),
        ),
        LiveOrderRealApiPreflightSafeRouteReviewSection(
            section_id="missing_fields",
            title="Missing Fields",
            lines=missing or ("none",),
        ),
        LiveOrderRealApiPreflightSafeRouteReviewSection(
            section_id="route_gaps",
            title="Route Gaps",
            lines=tuple(gap.field_name for gap in route_gaps) or ("none",),
        ),
        LiveOrderRealApiPreflightSafeRouteReviewSection(
            section_id="recommended_next_step",
            title="Recommended Next Step",
            lines=(recommended_next_step,),
        ),
    )


def _validate_review(review: LiveOrderRealApiPreflightSafeRouteReview) -> None:
    _require_non_empty("review_id", review.review_id)
    if not review.review_id.startswith(
        LIVE_ORDER_REAL_API_PREFLIGHT_SAFE_ROUTE_REVIEW_ID_PREFIX,
    ):
        raise LiveVerificationValidationError("invalid review_id prefix")
    _ensure_aware(review.created_at)
    _require_non_empty("source_step6e_retry_head", review.source_step6e_retry_head)
    _require_non_empty("safe_route_summary", review.safe_route_summary)
    _require_non_empty("recommended_next_step", review.recommended_next_step)
    if review.allowed_for_live is not False:
        raise LiveVerificationValidationError("allowed_for_live must be False")
    for field_name in (
        "api_executed_this_step",
        "read_only_api_called_this_step",
        "public_api_called_this_step",
        "private_api_called_this_step",
        "broker_called_this_step",
        "order_endpoint_called_this_step",
        "live_order_once_called_this_step",
        "post_executed_this_step",
    ):
        if getattr(review, field_name) is not False:
            raise LiveVerificationValidationError(f"{field_name} must be False")
    if not review.coverage_items:
        raise LiveVerificationValidationError("coverage_items required")
    if not review.check_results:
        raise LiveVerificationValidationError("check_results required")
    if not review.sections:
        raise LiveVerificationValidationError("sections required")
    if review.review_status is ReviewStatus.READY_FOR_STEP6E_R2_RETRY_WITH_EXISTING_SAFE_ROUTE:
        if not review.review_ready or not review.eligible_for_step6e_r2_retry:
            raise LiveVerificationValidationError("ready existing route flags invalid")
    if (
        review.review_status
        is ReviewStatus.READY_FOR_STEP6E_SAFE_ROUTE_CONSOLIDATION_IMPLEMENTATION
    ):
        if (
            not review.review_ready
            or not review.eligible_for_safe_route_consolidation_implementation
        ):
            raise LiveVerificationValidationError("consolidation flags invalid")


def _check(
    name: str,
    passed: bool,
    reason: str,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealApiPreflightSafeRouteReviewCheckResult:
    return LiveOrderRealApiPreflightSafeRouteReviewCheckResult(
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
