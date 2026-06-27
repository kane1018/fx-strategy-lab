"""Dry-run pre-approval fresh preflight model for Step 5S."""

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
from app.live_verification.live_order_real_approval_gate_plan import (
    LiveOrderRealApprovalGatePlan,
    LiveOrderRealApprovalGatePlanStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_PRE_APPROVAL_FRESH_PREFLIGHT_ID_PREFIX = "LOPAFP-"
PRE_APPROVAL_FRESH_PREFLIGHT_MAX_SPREAD_JPY = 0.01
PRE_APPROVAL_FRESH_PREFLIGHT_TICKER_AGE_THRESHOLD_SECONDS = 30
PRE_APPROVAL_FRESH_PREFLIGHT_AGE_THRESHOLD_SECONDS = 30


class LiveOrderPreApprovalFreshPreflightStatus(str, Enum):
    READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW = (
        "READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW"
    )
    BLOCKED_PRE_APPROVAL_FRESH_PREFLIGHT = "BLOCKED_PRE_APPROVAL_FRESH_PREFLIGHT"


class LiveOrderPreApprovalFreshPreflightBlockReason(str, Enum):
    MISSING_REAL_APPROVAL_GATE_PLAN = "missing_real_approval_gate_plan"
    REAL_APPROVAL_GATE_PLAN_NOT_READY = "real_approval_gate_plan_not_ready"
    PLAN_ALLOWS_LIVE = "plan_allows_live"
    PLAN_NOT_DRY_RUN = "plan_not_dry_run"
    PLAN_APPROVAL_GATE_ALREADY_ISSUED = "plan_approval_gate_already_issued"
    PLAN_APPROVAL_ID_ALREADY_GENERATED = "plan_approval_id_already_generated"
    PLAN_APPROVAL_COMMAND_ALREADY_GENERATED = (
        "plan_approval_command_already_generated"
    )
    PLAN_APPROVAL_COMMAND_COPYABLE = "plan_approval_command_copyable"
    PLAN_FRESH_PREFLIGHT_BEFORE_GATE_NOT_REQUIRED = (
        "plan_fresh_preflight_before_gate_not_required"
    )
    PLAN_APPROVAL_ID_GENERATION_NOT_AFTER_FRESH_PREFLIGHT = (
        "plan_approval_id_generation_not_after_fresh_preflight"
    )
    PLAN_APPROVAL_COMMAND_GENERATION_NOT_AFTER_FRESH_PREFLIGHT = (
        "plan_approval_command_generation_not_after_fresh_preflight"
    )
    SNAPSHOT_ALLOWS_LIVE = "snapshot_allows_live"
    SNAPSHOT_NOT_DRY_RUN = "snapshot_not_dry_run"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_ID_ALREADY_GENERATED = "approval_id_already_generated"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
    APPROVAL_COMMAND_COPYABLE = "approval_command_copyable"
    FRESH_PREFLIGHT_BEFORE_GATE_NOT_REQUIRED = (
        "fresh_preflight_before_gate_not_required"
    )
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    ACCOUNT_ASSETS_NOT_SUCCESS = "account_assets_not_success"
    OPEN_POSITIONS_EXIST = "open_positions_exist"
    ACTIVE_ORDERS_EXIST = "active_orders_exist"
    INVALID_MIN_OPEN_ORDER_SIZE = "invalid_min_open_order_size"
    INVALID_SIZE_STEP = "invalid_size_step"
    TICKER_UNAVAILABLE = "ticker_unavailable"
    MISSING_SPREAD = "missing_spread"
    SPREAD_TOO_WIDE = "spread_too_wide"
    MISSING_TICKER_AGE = "missing_ticker_age"
    INVALID_TICKER_AGE = "invalid_ticker_age"
    STALE_TICKER = "stale_ticker"
    MARKET_WINDOW_NOT_ALLOWED = "market_window_not_allowed"
    MAINTENANCE_ACTIVE = "maintenance_active"
    IMPORTANT_EVENT_WINDOW_NOT_OK = "important_event_window_not_ok"
    API_SCOPE_NOT_CHECKED = "api_scope_not_checked"
    ORDER_PERMISSION_NOT_CHECKED = "order_permission_not_checked"
    IP_ACCOUNT_CHECK_NOT_PASSED = "ip_account_check_not_passed"
    PREVIOUS_RESULT_NOT_CONFIRMED = "previous_result_not_confirmed"
    RESULT_UNKNOWN = "result_unknown"
    SESSION_ATTEMPT_LIMIT_REACHED = "session_attempt_limit_reached"
    DAILY_SIZE_LIMIT_EXCEEDED = "daily_size_limit_exceeded"
    GIT_NOT_CLEAN = "git_not_clean"
    TESTS_NOT_PASSED = "tests_not_passed"
    RUFF_NOT_PASSED = "ruff_not_passed"
    SECRET_SCAN_NOT_PASSED = "secret_scan_not_passed"
    RAW_RESPONSE_SAVED = "raw_response_saved"
    RAW_RESPONSE_DISPLAYED = "raw_response_displayed"
    OUTBOUND_BODY_ALLOWLIST_MISMATCH = "outbound_body_allowlist_mismatch"
    REQUEST_BODY_SIGNING_BODY_MISMATCH = "request_body_signing_body_mismatch"
    MISSING_PRE_APPROVAL_FRESH_PREFLIGHT_AGE = (
        "missing_pre_approval_fresh_preflight_age"
    )
    INVALID_PRE_APPROVAL_FRESH_PREFLIGHT_AGE = (
        "invalid_pre_approval_fresh_preflight_age"
    )
    STALE_PRE_APPROVAL_FRESH_PREFLIGHT = "stale_pre_approval_fresh_preflight"


@dataclass(frozen=True)
class LiveOrderPreApprovalFreshPreflightCheckResult:
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
class LiveOrderPreApprovalFreshPreflightSection:
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
class LiveOrderPreApprovalFreshPreflightSnapshot:
    snapshot_id: str
    created_at: datetime
    plan_id: str
    checkpoint_id: str
    chain_id: str
    runbook_id: str
    boundary_id: str
    preflight_decision_id: str
    simulation_id: str
    preview_id: str
    design_id: str
    handoff_id: str
    operator_review_id: str
    bundle_id: str
    review_id: str
    candidate_id: str
    risk_decision_id: str
    trace_id: str
    session_policy_decision_id: str
    source_signal_id: str
    source_type: str
    strategy_name: str
    symbol: str
    side: str
    size: int
    execution_type: str
    account_assets_status: str
    open_positions_count: int | None
    active_orders_count: int | None
    min_open_order_size: int | None
    size_step: int | None
    ticker_available: bool | None
    spread_jpy: float | int | None
    ticker_age_seconds: float | int | None
    ticker_age_threshold_seconds: int = (
        PRE_APPROVAL_FRESH_PREFLIGHT_TICKER_AGE_THRESHOLD_SECONDS
    )
    market_window_allowed: bool | None = None
    maintenance_active: bool | None = None
    important_event_window_ok: bool | None = None
    api_scope_checked: bool | None = None
    order_permission_checked: bool | None = None
    ip_account_check_passed: bool | None = None
    previous_result_confirmed: bool | None = None
    result_unknown: bool | None = None
    session_attempt_count_today: int | None = None
    max_sessions_per_day: int = 2
    daily_live_size_total: int | None = None
    max_daily_size_total: int = 200
    git_clean: bool | None = None
    tests_passed: bool | None = None
    ruff_passed: bool | None = None
    secret_scan_passed: bool | None = None
    raw_response_saved: bool | None = None
    raw_response_displayed: bool | None = None
    outbound_body_allowlist_matched: bool | None = None
    request_body_equals_signing_body: bool | None = None
    pre_approval_fresh_preflight_age_seconds: float | int | None = None
    pre_approval_fresh_preflight_age_threshold_seconds: int = (
        PRE_APPROVAL_FRESH_PREFLIGHT_AGE_THRESHOLD_SECONDS
    )
    allowed_for_live: bool = False
    requires_human_approval: bool = True
    explicit_user_confirmation_required: bool = True
    approval_gate_required: bool = True
    approval_gate_planned: bool = True
    approval_gate_issued: bool = False
    approval_id_generation_planned: bool = True
    approval_id_generated: bool = False
    approval_command_generation_planned: bool = True
    approval_command_generated: bool = False
    approval_command_template_only: bool = True
    approval_command_copyable: bool = False
    fresh_preflight_before_gate_required: bool = True
    post_approval_final_dynamic_preflight_required: bool = True
    dry_run_only: bool = True


@dataclass(frozen=True)
class LiveOrderPreApprovalFreshPreflightDecision:
    decision_id: str
    created_at: datetime
    snapshot_id: str
    plan_id: str
    checkpoint_id: str
    chain_id: str
    symbol: str
    side: str
    size: int
    execution_type: str
    preflight_status: LiveOrderPreApprovalFreshPreflightStatus
    preflight_passed: bool
    eligible_for_future_real_approval_gate_generation: bool
    allowed_for_live: bool
    requires_human_approval: bool
    explicit_user_confirmation_required: bool
    approval_gate_required: bool
    approval_gate_planned: bool
    approval_gate_issued: bool
    approval_id_generation_planned: bool
    approval_id_generated: bool
    approval_command_generation_planned: bool
    approval_command_generated: bool
    approval_command_template_only: bool
    approval_command_copyable: bool
    fresh_preflight_before_gate_required: bool
    post_approval_final_dynamic_preflight_required: bool
    dry_run_only: bool
    check_results: tuple[LiveOrderPreApprovalFreshPreflightCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderPreApprovalFreshPreflightSection, ...]

    def __post_init__(self) -> None:
        _validate_decision(self)


@dataclass(frozen=True)
class LiveOrderPreApprovalFreshPreflightBuildResult:
    decision: LiveOrderPreApprovalFreshPreflightDecision
    decision_id: str
    preflight_status: LiveOrderPreApprovalFreshPreflightStatus
    blocked_reasons: tuple[str, ...]
    preflight_passed: bool
    eligible_for_future_real_approval_gate_generation: bool
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_copyable: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.decision.decision_id != self.decision_id:
            raise LiveVerificationValidationError("decision_id mismatch")
        if self.decision.preflight_status is not self.preflight_status:
            raise LiveVerificationValidationError("preflight_status mismatch")
        if self.decision.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.decision.preflight_passed is not self.preflight_passed:
            raise LiveVerificationValidationError("preflight_passed mismatch")
        if (
            self.decision.eligible_for_future_real_approval_gate_generation
            is not self.eligible_for_future_real_approval_gate_generation
        ):
            raise LiveVerificationValidationError("eligible generation mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("Step 5S never allows live execution")
        if self.approval_gate_issued is not False:
            raise LiveVerificationValidationError("Step 5S never issues approval gate")
        if self.approval_id_generated is not False:
            raise LiveVerificationValidationError("Step 5S never generates approval id")
        if self.approval_command_generated is not False:
            raise LiveVerificationValidationError(
                "Step 5S never generates approval command"
            )
        if self.approval_command_copyable is not False:
            raise LiveVerificationValidationError("Step 5S never creates copyable command")
        if self.decision.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def evaluate_live_order_pre_approval_fresh_preflight(
    *,
    real_approval_gate_plan: LiveOrderRealApprovalGatePlan | None,
    snapshot: LiveOrderPreApprovalFreshPreflightSnapshot,
    created_at: datetime | None = None,
) -> LiveOrderPreApprovalFreshPreflightBuildResult:
    """Evaluate sanitized pre-approval fresh preflight inputs without API calls."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    plan_reasons = _plan_blocked_reasons(real_approval_gate_plan)
    snapshot_reasons = _snapshot_blocked_reasons(snapshot)
    preflight_reasons = _preflight_blocked_reasons(snapshot)
    blocked_reasons = _merge_reasons(
        plan_reasons,
        _plan_existing_reasons(real_approval_gate_plan),
        snapshot_reasons,
        preflight_reasons,
    )
    check_results = _build_check_results(
        plan=real_approval_gate_plan,
        snapshot=snapshot,
        blocked_reasons=blocked_reasons,
    )

    if blocked_reasons:
        status = (
            LiveOrderPreApprovalFreshPreflightStatus.BLOCKED_PRE_APPROVAL_FRESH_PREFLIGHT
        )
        passed = False
        eligible = False
        recommended_next_step = (
            "fix_real_approval_gate_plan_blockers_no_post"
            if plan_reasons or _plan_existing_reasons(real_approval_gate_plan)
            else "fix_pre_approval_fresh_preflight_snapshot_no_post"
        )
        summary = (
            "blocked dry-run pre-approval fresh preflight; no approval gate is issued"
        )
    else:
        status = (
            LiveOrderPreApprovalFreshPreflightStatus.READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW
        )
        passed = True
        eligible = True
        recommended_next_step = (
            "prepare_future_real_approval_gate_generation_separate_step_no_post"
        )
        summary = (
            "ready for future real approval gate generation review only; "
            "live post remains disallowed"
        )

    decision_id = make_live_order_pre_approval_fresh_preflight_id(
        snapshot_id=_snapshot_text(snapshot, "snapshot_id"),
        plan_id=_plan_id(real_approval_gate_plan, snapshot),
        candidate_id=_snapshot_text(snapshot, "candidate_id"),
        created_at=created,
        preflight_status=status,
        blocked_reasons=blocked_reasons,
    )
    decision = LiveOrderPreApprovalFreshPreflightDecision(
        decision_id=decision_id,
        created_at=created,
        snapshot_id=_snapshot_text(snapshot, "snapshot_id"),
        plan_id=_plan_id(real_approval_gate_plan, snapshot),
        checkpoint_id=_snapshot_text(snapshot, "checkpoint_id"),
        chain_id=_snapshot_text(snapshot, "chain_id"),
        symbol=_snapshot_text(snapshot, "symbol"),
        side=_snapshot_text(snapshot, "side"),
        size=_snapshot_int(snapshot, "size"),
        execution_type=_snapshot_text(snapshot, "execution_type"),
        preflight_status=status,
        preflight_passed=passed,
        eligible_for_future_real_approval_gate_generation=eligible,
        allowed_for_live=False,
        requires_human_approval=True,
        explicit_user_confirmation_required=True,
        approval_gate_required=True,
        approval_gate_planned=True,
        approval_gate_issued=False,
        approval_id_generation_planned=True,
        approval_id_generated=False,
        approval_command_generation_planned=True,
        approval_command_generated=False,
        approval_command_template_only=True,
        approval_command_copyable=False,
        fresh_preflight_before_gate_required=True,
        post_approval_final_dynamic_preflight_required=True,
        dry_run_only=True,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(snapshot, status, check_results, blocked_reasons),
    )
    return LiveOrderPreApprovalFreshPreflightBuildResult(
        decision=decision,
        decision_id=decision.decision_id,
        preflight_status=decision.preflight_status,
        blocked_reasons=decision.blocked_reasons,
        preflight_passed=decision.preflight_passed,
        eligible_for_future_real_approval_gate_generation=(
            decision.eligible_for_future_real_approval_gate_generation
        ),
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_copyable=False,
        recommended_next_step=decision.recommended_next_step,
    )


def render_live_order_pre_approval_fresh_preflight_markdown(
    decision: LiveOrderPreApprovalFreshPreflightDecision,
) -> str:
    """Render a sanitized pre-approval fresh preflight dry-run review."""
    lines = [
        "# Step 5S Pre-approval Fresh Preflight",
        "",
        "This pre-approval fresh preflight model is dry-run only.",
        "This model does not call read-only API.",
        "This model does not call Private API.",
        "This model does not call live_order_once.",
        "This model does not execute HTTP POST.",
        "This model does not issue a real approval gate.",
        "This model does not generate a real approval_id.",
        "This model does not generate a real approval command.",
        "This model does not authorize live POST.",
        "allowed_for_live=false.",
        "",
        "## Summary",
        "",
        f"- decision_id: {decision.decision_id}",
        f"- preflight_status: {decision.preflight_status.value}",
        f"- preflight_passed: {decision.preflight_passed}",
        (
            "- eligible_for_future_real_approval_gate_generation: "
            f"{decision.eligible_for_future_real_approval_gate_generation}"
        ),
        f"- summary: {decision.summary}",
        f"- recommended_next_step: {decision.recommended_next_step}",
        "",
    ]
    for section in decision.sections:
        lines.extend([f"## {section.title}", ""])
        lines.extend(f"- {line}" for line in section.lines)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def make_live_order_pre_approval_fresh_preflight_id(
    *,
    snapshot_id: str,
    plan_id: str,
    candidate_id: str,
    created_at: datetime,
    preflight_status: LiveOrderPreApprovalFreshPreflightStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    _require_non_empty("snapshot_id", snapshot_id)
    _require_non_empty("plan_id", plan_id)
    _require_non_empty("candidate_id", candidate_id)
    created = _ensure_aware(created_at)
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "plan_id": plan_id,
        "preflight_status": preflight_status.value,
        "snapshot_id": snapshot_id,
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{LIVE_ORDER_PRE_APPROVAL_FRESH_PREFLIGHT_ID_PREFIX}{digest.upper()}"


def _plan_blocked_reasons(
    plan: LiveOrderRealApprovalGatePlan | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(plan, LiveOrderRealApprovalGatePlan):
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.MISSING_REAL_APPROVAL_GATE_PLAN,
        )
        return tuple(reasons)
    if (
        plan.plan_status
        is not LiveOrderRealApprovalGatePlanStatus.READY_FOR_REAL_APPROVAL_GATE_PLAN_REVIEW
        or plan.plan_ready is not True
        or plan.eligible_for_future_real_approval_gate_implementation is not True
    ):
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.REAL_APPROVAL_GATE_PLAN_NOT_READY,
        )
    if plan.allowed_for_live is not False:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_ALLOWS_LIVE,
        )
    if plan.dry_run_only is not True:
        _add_reason(reasons, LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_NOT_DRY_RUN)
    if plan.approval_gate_issued is not False:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_GATE_ALREADY_ISSUED,
        )
    if plan.approval_id_generated is not False:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_ID_ALREADY_GENERATED,
        )
    if plan.approval_command_generated is not False:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_COMMAND_ALREADY_GENERATED,
        )
    if plan.approval_command_copyable is not False:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_COMMAND_COPYABLE,
        )
    if plan.fresh_preflight_before_gate_required is not True:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_FRESH_PREFLIGHT_BEFORE_GATE_NOT_REQUIRED,
        )
    if plan.approval_id_generation_after_fresh_preflight_required is not True:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_ID_GENERATION_NOT_AFTER_FRESH_PREFLIGHT,
        )
    if plan.approval_command_generation_after_fresh_preflight_required is not True:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_APPROVAL_COMMAND_GENERATION_NOT_AFTER_FRESH_PREFLIGHT,
        )
    return tuple(reasons)


def _snapshot_blocked_reasons(
    snapshot: LiveOrderPreApprovalFreshPreflightSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.allowed_for_live is not False:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.SNAPSHOT_ALLOWS_LIVE,
        )
    if snapshot.dry_run_only is not True:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.SNAPSHOT_NOT_DRY_RUN,
        )
    for field_value, reason in (
        (
            snapshot.approval_gate_issued,
            LiveOrderPreApprovalFreshPreflightBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        ),
        (
            snapshot.approval_id_generated,
            LiveOrderPreApprovalFreshPreflightBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            snapshot.approval_command_generated,
            LiveOrderPreApprovalFreshPreflightBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            snapshot.approval_command_copyable,
            LiveOrderPreApprovalFreshPreflightBlockReason.APPROVAL_COMMAND_COPYABLE,
        ),
    ):
        if field_value is not False:
            _add_reason(reasons, reason)
    if snapshot.fresh_preflight_before_gate_required is not True:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.FRESH_PREFLIGHT_BEFORE_GATE_NOT_REQUIRED,
        )
    if snapshot.symbol != SUPPORTED_SYMBOL:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.UNSUPPORTED_SYMBOL,
        )
    if snapshot.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, LiveOrderPreApprovalFreshPreflightBlockReason.UNSUPPORTED_SIDE)
    if snapshot.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderPreApprovalFreshPreflightBlockReason.UNSUPPORTED_SIZE)
    if snapshot.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        )
    return tuple(reasons)


def _preflight_blocked_reasons(
    snapshot: LiveOrderPreApprovalFreshPreflightSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.account_assets_status != "success":
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.ACCOUNT_ASSETS_NOT_SUCCESS,
        )
    _evaluate_zero_count(
        reasons,
        value=snapshot.open_positions_count,
        positive_reason=LiveOrderPreApprovalFreshPreflightBlockReason.OPEN_POSITIONS_EXIST,
    )
    _evaluate_zero_count(
        reasons,
        value=snapshot.active_orders_count,
        positive_reason=LiveOrderPreApprovalFreshPreflightBlockReason.ACTIVE_ORDERS_EXIST,
    )
    if snapshot.min_open_order_size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.INVALID_MIN_OPEN_ORDER_SIZE,
        )
    if snapshot.size_step != 1:
        _add_reason(reasons, LiveOrderPreApprovalFreshPreflightBlockReason.INVALID_SIZE_STEP)
    if snapshot.ticker_available is not True:
        _add_reason(reasons, LiveOrderPreApprovalFreshPreflightBlockReason.TICKER_UNAVAILABLE)
    _evaluate_spread(reasons, snapshot.spread_jpy)
    _evaluate_age(
        reasons,
        value=snapshot.ticker_age_seconds,
        threshold=snapshot.ticker_age_threshold_seconds,
        missing_reason=LiveOrderPreApprovalFreshPreflightBlockReason.MISSING_TICKER_AGE,
        invalid_reason=LiveOrderPreApprovalFreshPreflightBlockReason.INVALID_TICKER_AGE,
        stale_reason=LiveOrderPreApprovalFreshPreflightBlockReason.STALE_TICKER,
    )
    _expect_true(
        reasons,
        snapshot.market_window_allowed,
        LiveOrderPreApprovalFreshPreflightBlockReason.MARKET_WINDOW_NOT_ALLOWED,
    )
    _expect_false(
        reasons,
        snapshot.maintenance_active,
        LiveOrderPreApprovalFreshPreflightBlockReason.MAINTENANCE_ACTIVE,
    )
    _expect_true(
        reasons,
        snapshot.important_event_window_ok,
        LiveOrderPreApprovalFreshPreflightBlockReason.IMPORTANT_EVENT_WINDOW_NOT_OK,
    )
    _expect_true(
        reasons,
        snapshot.api_scope_checked,
        LiveOrderPreApprovalFreshPreflightBlockReason.API_SCOPE_NOT_CHECKED,
    )
    _expect_true(
        reasons,
        snapshot.order_permission_checked,
        LiveOrderPreApprovalFreshPreflightBlockReason.ORDER_PERMISSION_NOT_CHECKED,
    )
    _expect_true(
        reasons,
        snapshot.ip_account_check_passed,
        LiveOrderPreApprovalFreshPreflightBlockReason.IP_ACCOUNT_CHECK_NOT_PASSED,
    )
    _expect_true(
        reasons,
        snapshot.previous_result_confirmed,
        LiveOrderPreApprovalFreshPreflightBlockReason.PREVIOUS_RESULT_NOT_CONFIRMED,
    )
    _expect_false(
        reasons,
        snapshot.result_unknown,
        LiveOrderPreApprovalFreshPreflightBlockReason.RESULT_UNKNOWN,
    )
    if (
        not _valid_int(snapshot.session_attempt_count_today)
        or not _valid_int(snapshot.max_sessions_per_day)
        or snapshot.session_attempt_count_today >= snapshot.max_sessions_per_day
    ):
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.SESSION_ATTEMPT_LIMIT_REACHED,
        )
    if (
        not _valid_int(snapshot.daily_live_size_total)
        or not _valid_int(snapshot.max_daily_size_total)
        or snapshot.daily_live_size_total + LIVE_ORDER_CANDIDATE_SIZE
        > snapshot.max_daily_size_total
    ):
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.DAILY_SIZE_LIMIT_EXCEEDED,
        )
    _expect_true(
        reasons,
        snapshot.git_clean,
        LiveOrderPreApprovalFreshPreflightBlockReason.GIT_NOT_CLEAN,
    )
    _expect_true(
        reasons,
        snapshot.tests_passed,
        LiveOrderPreApprovalFreshPreflightBlockReason.TESTS_NOT_PASSED,
    )
    _expect_true(
        reasons,
        snapshot.ruff_passed,
        LiveOrderPreApprovalFreshPreflightBlockReason.RUFF_NOT_PASSED,
    )
    _expect_true(
        reasons,
        snapshot.secret_scan_passed,
        LiveOrderPreApprovalFreshPreflightBlockReason.SECRET_SCAN_NOT_PASSED,
    )
    _expect_false(
        reasons,
        snapshot.raw_response_saved,
        LiveOrderPreApprovalFreshPreflightBlockReason.RAW_RESPONSE_SAVED,
    )
    _expect_false(
        reasons,
        snapshot.raw_response_displayed,
        LiveOrderPreApprovalFreshPreflightBlockReason.RAW_RESPONSE_DISPLAYED,
    )
    _expect_true(
        reasons,
        snapshot.outbound_body_allowlist_matched,
        LiveOrderPreApprovalFreshPreflightBlockReason.OUTBOUND_BODY_ALLOWLIST_MISMATCH,
    )
    _expect_true(
        reasons,
        snapshot.request_body_equals_signing_body,
        LiveOrderPreApprovalFreshPreflightBlockReason.REQUEST_BODY_SIGNING_BODY_MISMATCH,
    )
    _evaluate_age(
        reasons,
        value=snapshot.pre_approval_fresh_preflight_age_seconds,
        threshold=snapshot.pre_approval_fresh_preflight_age_threshold_seconds,
        missing_reason=LiveOrderPreApprovalFreshPreflightBlockReason.MISSING_PRE_APPROVAL_FRESH_PREFLIGHT_AGE,
        invalid_reason=LiveOrderPreApprovalFreshPreflightBlockReason.INVALID_PRE_APPROVAL_FRESH_PREFLIGHT_AGE,
        stale_reason=LiveOrderPreApprovalFreshPreflightBlockReason.STALE_PRE_APPROVAL_FRESH_PREFLIGHT,
    )
    return tuple(reasons)


def _build_check_results(
    *,
    plan: LiveOrderRealApprovalGatePlan | None,
    snapshot: LiveOrderPreApprovalFreshPreflightSnapshot,
    blocked_reasons: tuple[str, ...],
) -> tuple[LiveOrderPreApprovalFreshPreflightCheckResult, ...]:
    plan_ready = not _has_any(
        blocked_reasons,
        {
            LiveOrderPreApprovalFreshPreflightBlockReason.MISSING_REAL_APPROVAL_GATE_PLAN.value,
            LiveOrderPreApprovalFreshPreflightBlockReason.REAL_APPROVAL_GATE_PLAN_NOT_READY.value,
            LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_ALLOWS_LIVE.value,
            LiveOrderPreApprovalFreshPreflightBlockReason.PLAN_NOT_DRY_RUN.value,
        },
    )
    approval_artifacts_clear = (
        snapshot.approval_gate_issued is False
        and snapshot.approval_id_generated is False
        and snapshot.approval_command_generated is False
        and snapshot.approval_command_copyable is False
        and isinstance(plan, LiveOrderRealApprovalGatePlan)
        and plan.approval_gate_issued is False
        and plan.approval_id_generated is False
        and plan.approval_command_generated is False
        and plan.approval_command_copyable is False
    )
    instrument_rules = (
        snapshot.min_open_order_size == LIVE_ORDER_CANDIDATE_SIZE
        and snapshot.size_step == 1
    )
    session_limit = (
        _valid_int(snapshot.session_attempt_count_today)
        and _valid_int(snapshot.max_sessions_per_day)
        and snapshot.session_attempt_count_today < snapshot.max_sessions_per_day
    )
    daily_limit = (
        _valid_int(snapshot.daily_live_size_total)
        and _valid_int(snapshot.max_daily_size_total)
        and snapshot.daily_live_size_total + LIVE_ORDER_CANDIDATE_SIZE
        <= snapshot.max_daily_size_total
    )
    return (
        _check(
            "real_approval_gate_plan_ready",
            plan_ready,
            _enum_value(plan.plan_status)
            if isinstance(plan, LiveOrderRealApprovalGatePlan)
            else "missing",
            "READY_FOR_REAL_APPROVAL_GATE_PLAN_REVIEW",
        ),
        _check(
            "allowed_for_live_false",
            snapshot.allowed_for_live is False
            and (
                not isinstance(plan, LiveOrderRealApprovalGatePlan)
                or plan.allowed_for_live is False
            ),
            snapshot.allowed_for_live,
            "false",
        ),
        _check(
            "approval_artifacts_not_generated",
            approval_artifacts_clear,
            "clear" if approval_artifacts_clear else "not_clear",
            "clear",
        ),
        _check(
            "account_assets_success",
            snapshot.account_assets_status == "success",
            snapshot.account_assets_status,
            "success",
        ),
        _check(
            "open_positions_zero",
            snapshot.open_positions_count == 0,
            snapshot.open_positions_count,
            "0",
        ),
        _check(
            "active_orders_zero",
            snapshot.active_orders_count == 0,
            snapshot.active_orders_count,
            "0",
        ),
        _check(
            "instrument_rules",
            instrument_rules,
            f"{snapshot.min_open_order_size}/{snapshot.size_step}",
            "100/1",
        ),
        _check(
            "ticker_available",
            snapshot.ticker_available is True,
            snapshot.ticker_available,
            "true",
        ),
        _check(
            "spread_within_threshold",
            _numeric(snapshot.spread_jpy)
            and snapshot.spread_jpy <= PRE_APPROVAL_FRESH_PREFLIGHT_MAX_SPREAD_JPY,
            snapshot.spread_jpy,
            "<=0.01",
        ),
        _check(
            "ticker_age_fresh",
            _valid_age(snapshot.ticker_age_seconds, snapshot.ticker_age_threshold_seconds),
            snapshot.ticker_age_seconds,
            f"0..{snapshot.ticker_age_threshold_seconds}",
        ),
        _check(
            "market_maintenance_event",
            snapshot.market_window_allowed is True
            and snapshot.maintenance_active is False
            and snapshot.important_event_window_ok is True,
            f"{_safe_value(snapshot.market_window_allowed)}/"
            f"{_safe_value(snapshot.maintenance_active)}/"
            f"{_safe_value(snapshot.important_event_window_ok)}",
            "true/false/true",
        ),
        _check(
            "api_scope_order_permission_ip_account",
            snapshot.api_scope_checked is True
            and snapshot.order_permission_checked is True
            and snapshot.ip_account_check_passed is True,
            f"{_safe_value(snapshot.api_scope_checked)}/"
            f"{_safe_value(snapshot.order_permission_checked)}/"
            f"{_safe_value(snapshot.ip_account_check_passed)}",
            "true/true/true",
        ),
        _check(
            "previous_result_confirmed",
            snapshot.previous_result_confirmed is True,
            snapshot.previous_result_confirmed,
            "true",
        ),
        _check(
            "result_unknown_false",
            snapshot.result_unknown is False,
            snapshot.result_unknown,
            "false",
        ),
        _check(
            "session_limit",
            session_limit,
            snapshot.session_attempt_count_today,
            f"<{snapshot.max_sessions_per_day}",
        ),
        _check(
            "daily_limit",
            daily_limit,
            snapshot.daily_live_size_total,
            f"+100<={snapshot.max_daily_size_total}",
        ),
        _check(
            "git_tests_ruff_secret_scan",
            snapshot.git_clean is True
            and snapshot.tests_passed is True
            and snapshot.ruff_passed is True
            and snapshot.secret_scan_passed is True,
            f"{_safe_value(snapshot.git_clean)}/"
            f"{_safe_value(snapshot.tests_passed)}/"
            f"{_safe_value(snapshot.ruff_passed)}/"
            f"{_safe_value(snapshot.secret_scan_passed)}",
            "true/true/true/true",
        ),
        _check(
            "raw_response_not_saved_or_displayed",
            snapshot.raw_response_saved is False and snapshot.raw_response_displayed is False,
            f"{_safe_value(snapshot.raw_response_saved)}/"
            f"{_safe_value(snapshot.raw_response_displayed)}",
            "false/false",
        ),
        _check(
            "outbound_body_allowlist",
            snapshot.outbound_body_allowlist_matched is True,
            snapshot.outbound_body_allowlist_matched,
            "true",
        ),
        _check(
            "request_body_equals_signing_body",
            snapshot.request_body_equals_signing_body is True,
            snapshot.request_body_equals_signing_body,
            "true",
        ),
        _check(
            "pre_approval_fresh_preflight_age",
            _valid_age(
                snapshot.pre_approval_fresh_preflight_age_seconds,
                snapshot.pre_approval_fresh_preflight_age_threshold_seconds,
            ),
            snapshot.pre_approval_fresh_preflight_age_seconds,
            f"0..{snapshot.pre_approval_fresh_preflight_age_threshold_seconds}",
        ),
    )


def _build_sections(
    snapshot: LiveOrderPreApprovalFreshPreflightSnapshot,
    status: LiveOrderPreApprovalFreshPreflightStatus,
    check_results: tuple[LiveOrderPreApprovalFreshPreflightCheckResult, ...],
    blocked_reasons: tuple[str, ...],
) -> tuple[LiveOrderPreApprovalFreshPreflightSection, ...]:
    blocked_text = ", ".join(blocked_reasons) if blocked_reasons else "none"
    failed_checks = tuple(check.name for check in check_results if not check.passed)
    failed_text = ", ".join(failed_checks) if failed_checks else "none"
    return (
        LiveOrderPreApprovalFreshPreflightSection(
            section_id="references",
            title="Sanitized References",
            lines=(
                f"snapshot_id: {snapshot.snapshot_id}",
                f"plan_id: {snapshot.plan_id}",
                f"checkpoint_id: {snapshot.checkpoint_id}",
                f"chain_id: {snapshot.chain_id}",
                f"runbook_id: {snapshot.runbook_id}",
                f"boundary_id: {snapshot.boundary_id}",
                f"preflight_decision_id: {snapshot.preflight_decision_id}",
                f"simulation_id: {snapshot.simulation_id}",
                f"preview_id: {snapshot.preview_id}",
                f"design_id: {snapshot.design_id}",
                f"handoff_id: {snapshot.handoff_id}",
                f"operator_review_id: {snapshot.operator_review_id}",
                f"bundle_id: {snapshot.bundle_id}",
                f"review_id: {snapshot.review_id}",
            ),
        ),
        LiveOrderPreApprovalFreshPreflightSection(
            section_id="candidate",
            title="Candidate",
            lines=(
                f"candidate_id: {snapshot.candidate_id}",
                f"risk_decision_id: {snapshot.risk_decision_id}",
                f"trace_id: {snapshot.trace_id}",
                f"session_policy_decision_id: {snapshot.session_policy_decision_id}",
                f"source_signal_id: {snapshot.source_signal_id}",
                f"source_type: {snapshot.source_type}",
                f"strategy_name: {snapshot.strategy_name}",
                f"symbol: {snapshot.symbol}",
                f"side: {snapshot.side}",
                f"size: {snapshot.size}",
                f"executionType: {snapshot.execution_type}",
            ),
        ),
        LiveOrderPreApprovalFreshPreflightSection(
            section_id="preflight",
            title="Pre-approval Fresh Preflight Snapshot",
            lines=(
                f"account_assets_status: {snapshot.account_assets_status}",
                f"open_positions_count: {_safe_value(snapshot.open_positions_count)}",
                f"active_orders_count: {_safe_value(snapshot.active_orders_count)}",
                f"min_open_order_size: {_safe_value(snapshot.min_open_order_size)}",
                f"size_step: {_safe_value(snapshot.size_step)}",
                f"ticker_available: {_safe_value(snapshot.ticker_available)}",
                f"spread_jpy: {_safe_value(snapshot.spread_jpy)}",
                f"ticker_age_seconds: {_safe_value(snapshot.ticker_age_seconds)}",
                "pre_approval_fresh_preflight_age_seconds: "
                f"{_safe_value(snapshot.pre_approval_fresh_preflight_age_seconds)}",
            ),
        ),
        LiveOrderPreApprovalFreshPreflightSection(
            section_id="approval_boundaries",
            title="Approval Boundaries",
            lines=(
                "approval_gate_issued: False",
                "approval_id_generated: False",
                "approval_command_generated: False",
                "approval_command_copyable: False",
                "allowed_for_live: False",
                "dry_run_only: True",
            ),
        ),
        LiveOrderPreApprovalFreshPreflightSection(
            section_id="decision",
            title="Decision",
            lines=(
                f"preflight_status: {status.value}",
                f"failed_checks: {failed_text}",
                f"blocked_reasons: {blocked_text}",
            ),
        ),
    )


def _plan_existing_reasons(plan: LiveOrderRealApprovalGatePlan | None) -> tuple[str, ...]:
    if isinstance(plan, LiveOrderRealApprovalGatePlan):
        return plan.blocked_reasons
    return ()


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            if _has_text(reason) and reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _evaluate_zero_count(
    reasons: list[str],
    *,
    value: object,
    positive_reason: LiveOrderPreApprovalFreshPreflightBlockReason,
) -> None:
    if not _valid_int(value) or value > 0:
        _add_reason(reasons, positive_reason)


def _evaluate_spread(reasons: list[str], value: object) -> None:
    if not _numeric(value):
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.MISSING_SPREAD,
        )
    elif value > PRE_APPROVAL_FRESH_PREFLIGHT_MAX_SPREAD_JPY:
        _add_reason(
            reasons,
            LiveOrderPreApprovalFreshPreflightBlockReason.SPREAD_TOO_WIDE,
        )


def _evaluate_age(
    reasons: list[str],
    *,
    value: object,
    threshold: object,
    missing_reason: LiveOrderPreApprovalFreshPreflightBlockReason,
    invalid_reason: LiveOrderPreApprovalFreshPreflightBlockReason,
    stale_reason: LiveOrderPreApprovalFreshPreflightBlockReason,
) -> None:
    if value is None:
        _add_reason(reasons, missing_reason)
    elif not _numeric(value) or value < 0:
        _add_reason(reasons, invalid_reason)
    elif not _valid_int(threshold) or value > threshold:
        _add_reason(reasons, stale_reason)


def _expect_true(
    reasons: list[str],
    value: object,
    false_reason: LiveOrderPreApprovalFreshPreflightBlockReason,
) -> None:
    if value is not True:
        _add_reason(reasons, false_reason)


def _expect_false(
    reasons: list[str],
    value: object,
    true_reason: LiveOrderPreApprovalFreshPreflightBlockReason,
) -> None:
    if value is not False:
        _add_reason(reasons, true_reason)


def _check(
    name: str,
    passed: bool,
    sanitized_value: object,
    expected: str,
) -> LiveOrderPreApprovalFreshPreflightCheckResult:
    return LiveOrderPreApprovalFreshPreflightCheckResult(
        name=name,
        passed=passed,
        reason="passed" if passed else "blocked",
        sanitized_value=_safe_value(sanitized_value),
        expected=expected,
    )


def _validate_decision(decision: LiveOrderPreApprovalFreshPreflightDecision) -> None:
    _require_non_empty("decision_id", decision.decision_id)
    if not decision.decision_id.startswith(
        LIVE_ORDER_PRE_APPROVAL_FRESH_PREFLIGHT_ID_PREFIX
    ):
        raise LiveVerificationValidationError("decision_id must be dry-run preflight id")
    _ensure_aware(decision.created_at)
    for field_name, value in (
        ("snapshot_id", decision.snapshot_id),
        ("plan_id", decision.plan_id),
        ("checkpoint_id", decision.checkpoint_id),
        ("chain_id", decision.chain_id),
        ("symbol", decision.symbol),
        ("side", decision.side),
        ("execution_type", decision.execution_type),
        ("summary", decision.summary),
        ("recommended_next_step", decision.recommended_next_step),
    ):
        _require_non_empty(field_name, value)
    if type(decision.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    if decision.preflight_status not in set(LiveOrderPreApprovalFreshPreflightStatus):
        raise LiveVerificationValidationError("unsupported preflight status")
    for field_name, value in (
        ("preflight_passed", decision.preflight_passed),
        (
            "eligible_for_future_real_approval_gate_generation",
            decision.eligible_for_future_real_approval_gate_generation,
        ),
    ):
        if type(value) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")
    if decision.allowed_for_live is not False:
        raise LiveVerificationValidationError("Step 5S never allows live execution")
    if decision.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if decision.explicit_user_confirmation_required is not True:
        raise LiveVerificationValidationError("explicit user confirmation is required")
    if decision.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if decision.approval_gate_planned is not True:
        raise LiveVerificationValidationError("approval gate remains planned only")
    if decision.approval_gate_issued is not False:
        raise LiveVerificationValidationError("Step 5S never issues approval gate")
    if decision.approval_id_generation_planned is not True:
        raise LiveVerificationValidationError("approval id generation remains future")
    if decision.approval_id_generated is not False:
        raise LiveVerificationValidationError("Step 5S never generates approval id")
    if decision.approval_command_generation_planned is not True:
        raise LiveVerificationValidationError("approval command generation remains future")
    if decision.approval_command_generated is not False:
        raise LiveVerificationValidationError("Step 5S never generates approval command")
    if decision.approval_command_template_only is not True:
        raise LiveVerificationValidationError("approval command remains template-only")
    if decision.approval_command_copyable is not False:
        raise LiveVerificationValidationError("approval command remains non-copyable")
    if decision.fresh_preflight_before_gate_required is not True:
        raise LiveVerificationValidationError("fresh preflight before gate is required")
    if decision.post_approval_final_dynamic_preflight_required is not True:
        raise LiveVerificationValidationError("post-approval final preflight remains required")
    if decision.dry_run_only is not True:
        raise LiveVerificationValidationError("pre-approval preflight model is dry-run only")
    if not decision.check_results:
        raise LiveVerificationValidationError("decision requires check results")
    if not decision.sections:
        raise LiveVerificationValidationError("decision requires sections")
    if (
        decision.preflight_status
        is LiveOrderPreApprovalFreshPreflightStatus.READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW
    ):
        if (
            not decision.preflight_passed
            or not decision.eligible_for_future_real_approval_gate_generation
        ):
            raise LiveVerificationValidationError("ready preflight must be eligible")
        if decision.blocked_reasons:
            raise LiveVerificationValidationError("ready preflight cannot have blockers")
    else:
        if (
            decision.preflight_passed
            or decision.eligible_for_future_real_approval_gate_generation
        ):
            raise LiveVerificationValidationError("blocked preflight cannot pass")
        if not decision.blocked_reasons:
            raise LiveVerificationValidationError("blocked preflight requires blockers")


def _add_reason(
    reasons: list[str],
    reason: LiveOrderPreApprovalFreshPreflightBlockReason,
) -> None:
    if reason.value not in reasons:
        reasons.append(reason.value)


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _enum_value(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _has_any(values: tuple[str, ...], candidates: set[str]) -> bool:
    return any(value in candidates for value in values)


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _numeric(value: object) -> bool:
    return type(value) in {int, float}


def _plan_id(
    plan: LiveOrderRealApprovalGatePlan | None,
    snapshot: LiveOrderPreApprovalFreshPreflightSnapshot,
) -> str:
    if isinstance(plan, LiveOrderRealApprovalGatePlan) and _has_text(plan.plan_id):
        return plan.plan_id
    return _snapshot_text(snapshot, "plan_id")


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")


def _safe_value(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _snapshot_int(
    snapshot: LiveOrderPreApprovalFreshPreflightSnapshot,
    field_name: str,
) -> int:
    value = getattr(snapshot, field_name, 0)
    return value if type(value) is int else 0


def _snapshot_text(
    snapshot: LiveOrderPreApprovalFreshPreflightSnapshot,
    field_name: str,
) -> str:
    value = getattr(snapshot, field_name, None)
    return value.strip() if _has_text(value) else f"missing_{field_name}"


def _valid_age(value: object, threshold: object) -> bool:
    return _numeric(value) and _valid_int(threshold) and 0 <= value <= threshold


def _valid_int(value: object) -> bool:
    return type(value) is int and value >= 0
