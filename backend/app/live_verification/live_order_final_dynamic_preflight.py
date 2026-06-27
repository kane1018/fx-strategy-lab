"""Dry-run final dynamic preflight model for Step 5M."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_approval_validation_simulator import (
    LiveOrderApprovalValidationSimulation,
    LiveOrderApprovalValidationSimulationStatus,
)
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_FINAL_DYNAMIC_PREFLIGHT_ID_PREFIX = "LOFDP-"
FINAL_DYNAMIC_PREFLIGHT_MAX_SPREAD_JPY = 0.01
FINAL_DYNAMIC_PREFLIGHT_TICKER_AGE_THRESHOLD_SECONDS = 30
FINAL_DYNAMIC_PREFLIGHT_AGE_THRESHOLD_SECONDS = 30


class LiveOrderFinalDynamicPreflightStatus(str, Enum):
    READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW = (
        "READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW"
    )
    BLOCKED_FINAL_DYNAMIC_PREFLIGHT = "BLOCKED_FINAL_DYNAMIC_PREFLIGHT"


class LiveOrderFinalDynamicPreflightBlockReason(str, Enum):
    APPROVAL_VALIDATION_NOT_PASSED = "approval_validation_not_passed"
    SIMULATION_ALLOWS_LIVE = "simulation_allows_live"
    SIMULATION_NOT_DRY_RUN = "simulation_not_dry_run"
    SIMULATION_APPROVAL_GATE_ISSUED = "simulation_approval_gate_issued"
    SIMULATION_APPROVAL_ID_GENERATED = "simulation_approval_id_generated"
    SIMULATION_APPROVAL_COMMAND_GENERATED = "simulation_approval_command_generated"
    SIMULATION_MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT = (
        "simulation_missing_final_dynamic_preflight_requirement"
    )
    SNAPSHOT_ALLOWS_LIVE = "snapshot_allows_live"
    SNAPSHOT_NOT_DRY_RUN = "snapshot_not_dry_run"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_ID_ALREADY_GENERATED = "approval_id_already_generated"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
    MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT = (
        "missing_final_dynamic_preflight_requirement"
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
    LEDGER_NOT_UNUSED = "ledger_not_unused"
    SESSION_ATTEMPT_LIMIT_REACHED = "session_attempt_limit_reached"
    DAILY_SIZE_LIMIT_EXCEEDED = "daily_size_limit_exceeded"
    PREVIOUS_RESULT_NOT_CONFIRMED = "previous_result_not_confirmed"
    RESULT_UNKNOWN = "result_unknown"
    GIT_NOT_CLEAN = "git_not_clean"
    TESTS_NOT_PASSED = "tests_not_passed"
    RUFF_NOT_PASSED = "ruff_not_passed"
    SECRET_SCAN_NOT_PASSED = "secret_scan_not_passed"
    RAW_RESPONSE_SAVED = "raw_response_saved"
    RAW_RESPONSE_DISPLAYED = "raw_response_displayed"
    OUTBOUND_BODY_ALLOWLIST_MISMATCH = "outbound_body_allowlist_mismatch"
    REQUEST_BODY_SIGNING_BODY_MISMATCH = "request_body_signing_body_mismatch"
    MISSING_FINAL_PREFLIGHT_AGE = "missing_final_preflight_age"
    INVALID_FINAL_PREFLIGHT_AGE = "invalid_final_preflight_age"
    STALE_FINAL_PREFLIGHT = "stale_final_preflight"


@dataclass(frozen=True)
class LiveOrderFinalDynamicPreflightCheckResult:
    name: str
    passed: bool
    reason: str
    sanitized_value: str
    expected: str

    def __post_init__(self) -> None:
        _require_non_empty("name", self.name)
        if type(self.passed) is not bool:
            raise LiveVerificationValidationError("check result passed must be bool")
        _require_non_empty("reason", self.reason)
        _require_non_empty("sanitized_value", self.sanitized_value)
        _require_non_empty("expected", self.expected)


@dataclass(frozen=True)
class LiveOrderFinalDynamicPreflightSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError(
                "final dynamic preflight section requires lines"
            )
        for line in self.lines:
            _require_non_empty("section line", line)


@dataclass(frozen=True)
class LiveOrderFinalDynamicPreflightSnapshot:
    snapshot_id: str
    created_at: datetime
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
        FINAL_DYNAMIC_PREFLIGHT_TICKER_AGE_THRESHOLD_SECONDS
    )
    market_window_allowed: bool | None = None
    maintenance_active: bool | None = None
    important_event_window_ok: bool | None = None
    ledger_unused: bool | None = None
    session_attempt_count_today: int | None = None
    max_sessions_per_day: int = 2
    daily_live_size_total: int | None = None
    max_daily_size_total: int = 200
    previous_result_confirmed: bool | None = None
    result_unknown: bool | None = None
    git_clean: bool | None = None
    tests_passed: bool | None = None
    ruff_passed: bool | None = None
    secret_scan_passed: bool | None = None
    raw_response_saved: bool | None = None
    raw_response_displayed: bool | None = None
    outbound_body_allowlist_matched: bool | None = None
    request_body_equals_signing_body: bool | None = None
    final_preflight_age_seconds: float | int | None = None
    final_preflight_age_threshold_seconds: int = (
        FINAL_DYNAMIC_PREFLIGHT_AGE_THRESHOLD_SECONDS
    )
    allowed_for_live: bool = False
    requires_human_approval: bool = True
    approval_gate_required: bool = True
    approval_gate_issued: bool = False
    approval_id_generated: bool = False
    approval_command_generated: bool = False
    approval_command_template_only: bool = True
    approval_command_copyable: bool = False
    final_dynamic_preflight_required: bool = True
    dry_run_only: bool = True


@dataclass(frozen=True)
class LiveOrderFinalDynamicPreflightDecision:
    decision_id: str
    created_at: datetime
    snapshot_id: str
    simulation_id: str
    symbol: str
    side: str
    size: int
    execution_type: str
    preflight_status: LiveOrderFinalDynamicPreflightStatus
    preflight_passed: bool
    eligible_for_future_one_shot_review: bool
    allowed_for_live: bool
    requires_human_approval: bool
    approval_gate_required: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_template_only: bool
    approval_command_copyable: bool
    final_dynamic_preflight_required: bool
    dry_run_only: bool
    check_results: tuple[LiveOrderFinalDynamicPreflightCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderFinalDynamicPreflightSection, ...]

    def __post_init__(self) -> None:
        _validate_decision(self)


@dataclass(frozen=True)
class LiveOrderFinalDynamicPreflightBuildResult:
    decision: LiveOrderFinalDynamicPreflightDecision
    decision_id: str
    preflight_status: LiveOrderFinalDynamicPreflightStatus
    blocked_reasons: tuple[str, ...]
    preflight_passed: bool
    eligible_for_future_one_shot_review: bool
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    final_dynamic_preflight_required: bool
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
            self.decision.eligible_for_future_one_shot_review
            is not self.eligible_for_future_one_shot_review
        ):
            raise LiveVerificationValidationError("eligible review mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("Step 5M never allows live execution")
        if self.approval_gate_issued is not False:
            raise LiveVerificationValidationError("Step 5M never issues approval gate")
        if self.approval_id_generated is not False:
            raise LiveVerificationValidationError("Step 5M never generates approval id")
        if self.approval_command_generated is not False:
            raise LiveVerificationValidationError(
                "Step 5M never generates approval command"
            )
        if self.final_dynamic_preflight_required is not True:
            raise LiveVerificationValidationError("final dynamic preflight remains required")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def evaluate_live_order_final_dynamic_preflight(
    *,
    approval_validation_simulation: LiveOrderApprovalValidationSimulation | None,
    snapshot: LiveOrderFinalDynamicPreflightSnapshot,
    created_at: datetime | None = None,
) -> LiveOrderFinalDynamicPreflightBuildResult:
    """Evaluate sanitized final dynamic preflight inputs without live execution."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    simulation_reasons = _simulation_blocked_reasons(approval_validation_simulation)
    snapshot_reasons = _snapshot_blocked_reasons(snapshot)
    preflight_reasons = _preflight_blocked_reasons(snapshot)
    blocked_reasons = _merge_reasons(
        simulation_reasons,
        _simulation_existing_reasons(approval_validation_simulation),
        snapshot_reasons,
        preflight_reasons,
    )
    check_results = _build_check_results(
        simulation=approval_validation_simulation,
        snapshot=snapshot,
        blocked_reasons=blocked_reasons,
    )

    if blocked_reasons:
        status = LiveOrderFinalDynamicPreflightStatus.BLOCKED_FINAL_DYNAMIC_PREFLIGHT
        passed = False
        eligible = False
        if simulation_reasons or _simulation_existing_reasons(
            approval_validation_simulation
        ):
            recommended_next_step = "fix_approval_validation_blockers_no_post"
        else:
            recommended_next_step = "fix_final_dynamic_preflight_snapshot_no_post"
        summary = "blocked dry-run final dynamic preflight review; live post remains disallowed"
    else:
        status = (
            LiveOrderFinalDynamicPreflightStatus.READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW
        )
        passed = True
        eligible = True
        recommended_next_step = "prepare_future_one_shot_boundary_design_no_post"
        summary = (
            "ready for future one-shot boundary review only; live post remains disallowed"
        )

    decision_id = make_live_order_final_dynamic_preflight_id(
        snapshot_id=_snapshot_id(snapshot),
        simulation_id=_simulation_id(approval_validation_simulation, snapshot),
        candidate_id=_candidate_id(snapshot),
        created_at=created,
        preflight_status=status,
        blocked_reasons=blocked_reasons,
    )
    decision = LiveOrderFinalDynamicPreflightDecision(
        decision_id=decision_id,
        created_at=created,
        snapshot_id=_snapshot_id(snapshot),
        simulation_id=_simulation_id(approval_validation_simulation, snapshot),
        symbol=_snapshot_text(snapshot, "symbol"),
        side=_snapshot_text(snapshot, "side"),
        size=_snapshot_int(snapshot, "size"),
        execution_type=_snapshot_text(snapshot, "execution_type"),
        preflight_status=status,
        preflight_passed=passed,
        eligible_for_future_one_shot_review=eligible,
        allowed_for_live=False,
        requires_human_approval=True,
        approval_gate_required=True,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_template_only=True,
        approval_command_copyable=False,
        final_dynamic_preflight_required=True,
        dry_run_only=True,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(snapshot, status, check_results, blocked_reasons),
    )
    return LiveOrderFinalDynamicPreflightBuildResult(
        decision=decision,
        decision_id=decision.decision_id,
        preflight_status=decision.preflight_status,
        blocked_reasons=decision.blocked_reasons,
        preflight_passed=decision.preflight_passed,
        eligible_for_future_one_shot_review=decision.eligible_for_future_one_shot_review,
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        final_dynamic_preflight_required=True,
        recommended_next_step=decision.recommended_next_step,
    )


def render_live_order_final_dynamic_preflight_markdown(
    decision: LiveOrderFinalDynamicPreflightDecision,
) -> str:
    """Render a sanitized final dynamic preflight dry-run review."""
    lines = [
        "# Live Order Final Dynamic Preflight",
        "",
        "This final dynamic preflight model is dry-run only.",
        "This model does not call read-only API.",
        "This model does not call Private API.",
        "This model does not execute final dynamic preflight.",
        "This model does not authorize live POST.",
        "allowed_for_live=false.",
        "",
        "## Summary",
        "",
        f"- decision_id: {decision.decision_id}",
        f"- preflight_status: {decision.preflight_status.value}",
        f"- preflight_passed: {decision.preflight_passed}",
        (
            "- eligible_for_future_one_shot_review: "
            f"{decision.eligible_for_future_one_shot_review}"
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


def make_live_order_final_dynamic_preflight_id(
    *,
    snapshot_id: str,
    simulation_id: str,
    candidate_id: str,
    created_at: datetime,
    preflight_status: LiveOrderFinalDynamicPreflightStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    _require_non_empty("snapshot_id", snapshot_id)
    _require_non_empty("simulation_id", simulation_id)
    _require_non_empty("candidate_id", candidate_id)
    created = _ensure_aware(created_at)
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "preflight_status": preflight_status.value,
        "simulation_id": simulation_id,
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
    return f"{LIVE_ORDER_FINAL_DYNAMIC_PREFLIGHT_ID_PREFIX}{digest.upper()}"


def _simulation_blocked_reasons(
    simulation: LiveOrderApprovalValidationSimulation | None,
) -> tuple[str, ...]:
    reasons: list[LiveOrderFinalDynamicPreflightBlockReason] = []
    if not isinstance(simulation, LiveOrderApprovalValidationSimulation):
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.APPROVAL_VALIDATION_NOT_PASSED,
        )
        return tuple(reason.value for reason in reasons)
    if (
        simulation.simulation_status
        is not LiveOrderApprovalValidationSimulationStatus.SIMULATED_APPROVAL_VALIDATION_PASSED
    ):
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.APPROVAL_VALIDATION_NOT_PASSED,
        )
    if simulation.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_ALLOWS_LIVE)
    if simulation.dry_run_only is not True:
        _add_reason(reasons, LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_NOT_DRY_RUN)
    if simulation.approval_gate_issued is not False:
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_APPROVAL_GATE_ISSUED,
        )
    if simulation.approval_id_generated is not False:
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_APPROVAL_ID_GENERATED,
        )
    if simulation.approval_command_generated is not False:
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_APPROVAL_COMMAND_GENERATED,
        )
    if simulation.final_dynamic_preflight_required is not True:
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT,
        )
    return tuple(reason.value for reason in reasons)


def _snapshot_blocked_reasons(
    snapshot: LiveOrderFinalDynamicPreflightSnapshot,
) -> tuple[str, ...]:
    reasons: list[LiveOrderFinalDynamicPreflightBlockReason] = []
    if not isinstance(snapshot, LiveOrderFinalDynamicPreflightSnapshot):
        return (LiveOrderFinalDynamicPreflightBlockReason.ACCOUNT_ASSETS_NOT_SUCCESS.value,)
    if snapshot.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderFinalDynamicPreflightBlockReason.SNAPSHOT_ALLOWS_LIVE)
    if snapshot.dry_run_only is not True:
        _add_reason(reasons, LiveOrderFinalDynamicPreflightBlockReason.SNAPSHOT_NOT_DRY_RUN)
    if snapshot.approval_gate_issued is not False:
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        )
    if snapshot.approval_id_generated is not False:
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        )
    if snapshot.approval_command_generated is not False:
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        )
    if snapshot.final_dynamic_preflight_required is not True:
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT,
        )
    if snapshot.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderFinalDynamicPreflightBlockReason.UNSUPPORTED_SYMBOL)
    if snapshot.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, LiveOrderFinalDynamicPreflightBlockReason.UNSUPPORTED_SIDE)
    if snapshot.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderFinalDynamicPreflightBlockReason.UNSUPPORTED_SIZE)
    if snapshot.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        )
    return tuple(reason.value for reason in reasons)


def _preflight_blocked_reasons(
    snapshot: LiveOrderFinalDynamicPreflightSnapshot,
) -> tuple[str, ...]:
    reasons: list[LiveOrderFinalDynamicPreflightBlockReason] = []
    if snapshot.account_assets_status != "success":
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.ACCOUNT_ASSETS_NOT_SUCCESS,
        )
    _evaluate_zero_count(
        reasons,
        value=snapshot.open_positions_count,
        positive_reason=LiveOrderFinalDynamicPreflightBlockReason.OPEN_POSITIONS_EXIST,
    )
    _evaluate_zero_count(
        reasons,
        value=snapshot.active_orders_count,
        positive_reason=LiveOrderFinalDynamicPreflightBlockReason.ACTIVE_ORDERS_EXIST,
    )
    if snapshot.min_open_order_size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.INVALID_MIN_OPEN_ORDER_SIZE,
        )
    if snapshot.size_step != 1:
        _add_reason(reasons, LiveOrderFinalDynamicPreflightBlockReason.INVALID_SIZE_STEP)
    if snapshot.ticker_available is not True:
        _add_reason(reasons, LiveOrderFinalDynamicPreflightBlockReason.TICKER_UNAVAILABLE)
    _evaluate_spread(reasons, snapshot.spread_jpy)
    _evaluate_age(
        reasons,
        value=snapshot.ticker_age_seconds,
        threshold=snapshot.ticker_age_threshold_seconds,
        missing_reason=LiveOrderFinalDynamicPreflightBlockReason.MISSING_TICKER_AGE,
        invalid_reason=LiveOrderFinalDynamicPreflightBlockReason.INVALID_TICKER_AGE,
        stale_reason=LiveOrderFinalDynamicPreflightBlockReason.STALE_TICKER,
    )
    _expect_true(
        reasons,
        snapshot.market_window_allowed,
        LiveOrderFinalDynamicPreflightBlockReason.MARKET_WINDOW_NOT_ALLOWED,
    )
    _expect_false(
        reasons,
        snapshot.maintenance_active,
        LiveOrderFinalDynamicPreflightBlockReason.MAINTENANCE_ACTIVE,
    )
    _expect_true(
        reasons,
        snapshot.important_event_window_ok,
        LiveOrderFinalDynamicPreflightBlockReason.IMPORTANT_EVENT_WINDOW_NOT_OK,
    )
    _expect_true(
        reasons,
        snapshot.ledger_unused,
        LiveOrderFinalDynamicPreflightBlockReason.LEDGER_NOT_UNUSED,
    )
    if (
        not _valid_int(snapshot.session_attempt_count_today)
        or not _valid_int(snapshot.max_sessions_per_day)
        or snapshot.session_attempt_count_today >= snapshot.max_sessions_per_day
    ):
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.SESSION_ATTEMPT_LIMIT_REACHED,
        )
    if (
        not _valid_int(snapshot.daily_live_size_total)
        or not _valid_int(snapshot.max_daily_size_total)
        or snapshot.daily_live_size_total + LIVE_ORDER_CANDIDATE_SIZE
        > snapshot.max_daily_size_total
    ):
        _add_reason(
            reasons,
            LiveOrderFinalDynamicPreflightBlockReason.DAILY_SIZE_LIMIT_EXCEEDED,
        )
    _expect_true(
        reasons,
        snapshot.previous_result_confirmed,
        LiveOrderFinalDynamicPreflightBlockReason.PREVIOUS_RESULT_NOT_CONFIRMED,
    )
    _expect_false(
        reasons,
        snapshot.result_unknown,
        LiveOrderFinalDynamicPreflightBlockReason.RESULT_UNKNOWN,
    )
    _expect_true(
        reasons,
        snapshot.git_clean,
        LiveOrderFinalDynamicPreflightBlockReason.GIT_NOT_CLEAN,
    )
    _expect_true(
        reasons,
        snapshot.tests_passed,
        LiveOrderFinalDynamicPreflightBlockReason.TESTS_NOT_PASSED,
    )
    _expect_true(
        reasons,
        snapshot.ruff_passed,
        LiveOrderFinalDynamicPreflightBlockReason.RUFF_NOT_PASSED,
    )
    _expect_true(
        reasons,
        snapshot.secret_scan_passed,
        LiveOrderFinalDynamicPreflightBlockReason.SECRET_SCAN_NOT_PASSED,
    )
    _expect_false(
        reasons,
        snapshot.raw_response_saved,
        LiveOrderFinalDynamicPreflightBlockReason.RAW_RESPONSE_SAVED,
    )
    _expect_false(
        reasons,
        snapshot.raw_response_displayed,
        LiveOrderFinalDynamicPreflightBlockReason.RAW_RESPONSE_DISPLAYED,
    )
    _expect_true(
        reasons,
        snapshot.outbound_body_allowlist_matched,
        LiveOrderFinalDynamicPreflightBlockReason.OUTBOUND_BODY_ALLOWLIST_MISMATCH,
    )
    _expect_true(
        reasons,
        snapshot.request_body_equals_signing_body,
        LiveOrderFinalDynamicPreflightBlockReason.REQUEST_BODY_SIGNING_BODY_MISMATCH,
    )
    _evaluate_age(
        reasons,
        value=snapshot.final_preflight_age_seconds,
        threshold=snapshot.final_preflight_age_threshold_seconds,
        missing_reason=LiveOrderFinalDynamicPreflightBlockReason.MISSING_FINAL_PREFLIGHT_AGE,
        invalid_reason=LiveOrderFinalDynamicPreflightBlockReason.INVALID_FINAL_PREFLIGHT_AGE,
        stale_reason=LiveOrderFinalDynamicPreflightBlockReason.STALE_FINAL_PREFLIGHT,
    )
    return tuple(reason.value for reason in reasons)


def _build_check_results(
    *,
    simulation: LiveOrderApprovalValidationSimulation | None,
    snapshot: LiveOrderFinalDynamicPreflightSnapshot,
    blocked_reasons: tuple[str, ...],
) -> tuple[LiveOrderFinalDynamicPreflightCheckResult, ...]:
    session_attempts_passed = (
        _valid_int(snapshot.session_attempt_count_today)
        and _valid_int(snapshot.max_sessions_per_day)
        and snapshot.session_attempt_count_today < snapshot.max_sessions_per_day
    )
    daily_size_passed = (
        _valid_int(snapshot.daily_live_size_total)
        and _valid_int(snapshot.max_daily_size_total)
        and snapshot.daily_live_size_total + LIVE_ORDER_CANDIDATE_SIZE
        <= snapshot.max_daily_size_total
    )
    return (
        _check(
            "approval_validation_simulation",
            not _has_any(
                blocked_reasons,
                {
                    LiveOrderFinalDynamicPreflightBlockReason.APPROVAL_VALIDATION_NOT_PASSED.value,
                    LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_ALLOWS_LIVE.value,
                    LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_NOT_DRY_RUN.value,
                    LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_APPROVAL_GATE_ISSUED.value,
                    LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_APPROVAL_ID_GENERATED.value,
                    LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_APPROVAL_COMMAND_GENERATED.value,
                    LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT.value,
                },
            ),
            _enum_value(simulation.simulation_status)
            if isinstance(simulation, LiveOrderApprovalValidationSimulation)
            else "missing",
            "SIMULATED_APPROVAL_VALIDATION_PASSED",
        ),
        _check(
            "account_assets",
            snapshot.account_assets_status == "success",
            snapshot.account_assets_status,
            "success",
        ),
        _check(
            "open_positions",
            snapshot.open_positions_count == 0,
            snapshot.open_positions_count,
            "0",
        ),
        _check(
            "active_orders",
            snapshot.active_orders_count == 0,
            snapshot.active_orders_count,
            "0",
        ),
        _check(
            "min_open_order_size",
            snapshot.min_open_order_size == 100,
            snapshot.min_open_order_size,
            "100",
        ),
        _check("size_step", snapshot.size_step == 1, snapshot.size_step, "1"),
        _check(
            "ticker_available",
            snapshot.ticker_available is True,
            snapshot.ticker_available,
            "true",
        ),
        _check(
            "spread",
            _numeric(snapshot.spread_jpy)
            and snapshot.spread_jpy <= FINAL_DYNAMIC_PREFLIGHT_MAX_SPREAD_JPY,
            snapshot.spread_jpy,
            "<=0.01",
        ),
        _check(
            "ticker_age",
            _valid_age(
                snapshot.ticker_age_seconds,
                snapshot.ticker_age_threshold_seconds,
            ),
            snapshot.ticker_age_seconds,
            f"0..{snapshot.ticker_age_threshold_seconds}",
        ),
        _check(
            "market_window",
            snapshot.market_window_allowed is True,
            snapshot.market_window_allowed,
            "true",
        ),
        _check(
            "maintenance",
            snapshot.maintenance_active is False,
            snapshot.maintenance_active,
            "false",
        ),
        _check(
            "important_event",
            snapshot.important_event_window_ok is True,
            snapshot.important_event_window_ok,
            "true",
        ),
        _check("ledger_unused", snapshot.ledger_unused is True, snapshot.ledger_unused, "true"),
        _check(
            "session_attempts",
            session_attempts_passed,
            snapshot.session_attempt_count_today,
            f"<{snapshot.max_sessions_per_day}",
        ),
        _check(
            "daily_live_size",
            daily_size_passed,
            snapshot.daily_live_size_total,
            f"+100<={snapshot.max_daily_size_total}",
        ),
        _check(
            "previous_result_confirmed",
            snapshot.previous_result_confirmed is True,
            snapshot.previous_result_confirmed,
            "true",
        ),
        _check(
            "result_unknown",
            snapshot.result_unknown is False,
            snapshot.result_unknown,
            "false",
        ),
        _check("git_clean", snapshot.git_clean is True, snapshot.git_clean, "true"),
        _check("tests_passed", snapshot.tests_passed is True, snapshot.tests_passed, "true"),
        _check("ruff_passed", snapshot.ruff_passed is True, snapshot.ruff_passed, "true"),
        _check(
            "secret_scan_passed",
            snapshot.secret_scan_passed is True,
            snapshot.secret_scan_passed,
            "true",
        ),
        _check(
            "raw_response_saved",
            snapshot.raw_response_saved is False,
            snapshot.raw_response_saved,
            "false",
        ),
        _check(
            "raw_response_displayed",
            snapshot.raw_response_displayed is False,
            snapshot.raw_response_displayed,
            "false",
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
            "final_preflight_age",
            _valid_age(
                snapshot.final_preflight_age_seconds,
                snapshot.final_preflight_age_threshold_seconds,
            ),
            snapshot.final_preflight_age_seconds,
            f"0..{snapshot.final_preflight_age_threshold_seconds}",
        ),
    )


def _build_sections(
    snapshot: LiveOrderFinalDynamicPreflightSnapshot,
    status: LiveOrderFinalDynamicPreflightStatus,
    check_results: tuple[LiveOrderFinalDynamicPreflightCheckResult, ...],
    blocked_reasons: tuple[str, ...],
) -> tuple[LiveOrderFinalDynamicPreflightSection, ...]:
    blocked_text = ", ".join(blocked_reasons) if blocked_reasons else "none"
    failed_checks = tuple(check.name for check in check_results if not check.passed)
    failed_text = ", ".join(failed_checks) if failed_checks else "none"
    return (
        LiveOrderFinalDynamicPreflightSection(
            section_id="references",
            title="Sanitized References",
            lines=(
                f"snapshot_id: {snapshot.snapshot_id}",
                f"simulation_id: {snapshot.simulation_id}",
                f"preview_id: {snapshot.preview_id}",
                f"design_id: {snapshot.design_id}",
                f"handoff_id: {snapshot.handoff_id}",
                f"operator_review_id: {snapshot.operator_review_id}",
                f"bundle_id: {snapshot.bundle_id}",
                f"review_id: {snapshot.review_id}",
                f"candidate_id: {snapshot.candidate_id}",
                f"risk_decision_id: {snapshot.risk_decision_id}",
                f"trace_id: {snapshot.trace_id}",
                f"session_policy_decision_id: {snapshot.session_policy_decision_id}",
            ),
        ),
        LiveOrderFinalDynamicPreflightSection(
            section_id="candidate",
            title="Candidate",
            lines=(
                f"source_signal_id: {snapshot.source_signal_id}",
                f"source_type: {snapshot.source_type}",
                f"strategy_name: {snapshot.strategy_name}",
                f"symbol: {snapshot.symbol}",
                f"side: {snapshot.side}",
                f"size: {snapshot.size}",
                f"executionType: {snapshot.execution_type}",
            ),
        ),
        LiveOrderFinalDynamicPreflightSection(
            section_id="preflight",
            title="Final Dynamic Preflight Snapshot",
            lines=(
                f"account_assets_status: {snapshot.account_assets_status}",
                f"open_positions_count: {_safe_value(snapshot.open_positions_count)}",
                f"active_orders_count: {_safe_value(snapshot.active_orders_count)}",
                f"min_open_order_size: {_safe_value(snapshot.min_open_order_size)}",
                f"size_step: {_safe_value(snapshot.size_step)}",
                f"ticker_available: {_safe_value(snapshot.ticker_available)}",
                f"spread_jpy: {_safe_value(snapshot.spread_jpy)}",
                f"ticker_age_seconds: {_safe_value(snapshot.ticker_age_seconds)}",
                f"final_preflight_age_seconds: {_safe_value(snapshot.final_preflight_age_seconds)}",
            ),
        ),
        LiveOrderFinalDynamicPreflightSection(
            section_id="decision",
            title="Decision",
            lines=(
                f"preflight_status: {status.value}",
                "allowed_for_live: False",
                "approval_gate_issued: False",
                "approval_id_generated: False",
                "approval_command_generated: False",
                f"failed_checks: {failed_text}",
                f"blocked_reasons: {blocked_text}",
            ),
        ),
    )


def _simulation_existing_reasons(
    simulation: LiveOrderApprovalValidationSimulation | None,
) -> tuple[str, ...]:
    if isinstance(simulation, LiveOrderApprovalValidationSimulation):
        return simulation.blocked_reasons
    return ()


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            if _has_text(reason) and reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _evaluate_zero_count(
    reasons: list[LiveOrderFinalDynamicPreflightBlockReason],
    *,
    value: object,
    positive_reason: LiveOrderFinalDynamicPreflightBlockReason,
) -> None:
    if not _valid_int(value) or value > 0:
        _add_reason(reasons, positive_reason)


def _evaluate_spread(
    reasons: list[LiveOrderFinalDynamicPreflightBlockReason],
    value: object,
) -> None:
    if not _numeric(value):
        _add_reason(reasons, LiveOrderFinalDynamicPreflightBlockReason.MISSING_SPREAD)
    elif value > FINAL_DYNAMIC_PREFLIGHT_MAX_SPREAD_JPY:
        _add_reason(reasons, LiveOrderFinalDynamicPreflightBlockReason.SPREAD_TOO_WIDE)


def _evaluate_age(
    reasons: list[LiveOrderFinalDynamicPreflightBlockReason],
    *,
    value: object,
    threshold: object,
    missing_reason: LiveOrderFinalDynamicPreflightBlockReason,
    invalid_reason: LiveOrderFinalDynamicPreflightBlockReason,
    stale_reason: LiveOrderFinalDynamicPreflightBlockReason,
) -> None:
    if value is None:
        _add_reason(reasons, missing_reason)
    elif not _numeric(value) or value < 0:
        _add_reason(reasons, invalid_reason)
    elif not _valid_int(threshold) or value > threshold:
        _add_reason(reasons, stale_reason)


def _expect_true(
    reasons: list[LiveOrderFinalDynamicPreflightBlockReason],
    value: object,
    false_reason: LiveOrderFinalDynamicPreflightBlockReason,
) -> None:
    if value is not True:
        _add_reason(reasons, false_reason)


def _expect_false(
    reasons: list[LiveOrderFinalDynamicPreflightBlockReason],
    value: object,
    true_reason: LiveOrderFinalDynamicPreflightBlockReason,
) -> None:
    if value is not False:
        _add_reason(reasons, true_reason)


def _check(
    name: str,
    passed: bool,
    sanitized_value: object,
    expected: str,
) -> LiveOrderFinalDynamicPreflightCheckResult:
    return LiveOrderFinalDynamicPreflightCheckResult(
        name=name,
        passed=passed,
        reason="passed" if passed else "blocked",
        sanitized_value=_safe_value(sanitized_value),
        expected=expected,
    )


def _validate_decision(decision: LiveOrderFinalDynamicPreflightDecision) -> None:
    _require_non_empty("decision_id", decision.decision_id)
    if not decision.decision_id.startswith(LIVE_ORDER_FINAL_DYNAMIC_PREFLIGHT_ID_PREFIX):
        raise LiveVerificationValidationError("decision_id must be dry-run preflight id")
    _ensure_aware(decision.created_at)
    for name, value in (
        ("snapshot_id", decision.snapshot_id),
        ("simulation_id", decision.simulation_id),
        ("symbol", decision.symbol),
        ("side", decision.side),
        ("execution_type", decision.execution_type),
        ("summary", decision.summary),
        ("recommended_next_step", decision.recommended_next_step),
    ):
        _require_non_empty(name, value)
    if type(decision.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    if decision.preflight_status not in set(LiveOrderFinalDynamicPreflightStatus):
        raise LiveVerificationValidationError("unsupported preflight status")
    for field_name, value in (
        ("preflight_passed", decision.preflight_passed),
        (
            "eligible_for_future_one_shot_review",
            decision.eligible_for_future_one_shot_review,
        ),
    ):
        if type(value) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")
    if decision.allowed_for_live is not False:
        raise LiveVerificationValidationError("Step 5M never allows live execution")
    if decision.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if decision.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if decision.approval_gate_issued is not False:
        raise LiveVerificationValidationError("Step 5M never issues approval gate")
    if decision.approval_id_generated is not False:
        raise LiveVerificationValidationError("Step 5M never generates approval id")
    if decision.approval_command_generated is not False:
        raise LiveVerificationValidationError("Step 5M never generates approval command")
    if decision.approval_command_template_only is not True:
        raise LiveVerificationValidationError("approval command remains template-only")
    if decision.approval_command_copyable is not False:
        raise LiveVerificationValidationError("approval command remains non-copyable")
    if decision.final_dynamic_preflight_required is not True:
        raise LiveVerificationValidationError("final dynamic preflight remains required")
    if decision.dry_run_only is not True:
        raise LiveVerificationValidationError("final dynamic preflight model is dry-run only")
    if not decision.check_results:
        raise LiveVerificationValidationError("decision requires check results")
    if not decision.sections:
        raise LiveVerificationValidationError("decision requires sections")
    if (
        decision.preflight_status
        is LiveOrderFinalDynamicPreflightStatus.READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW
    ):
        if (
            not decision.preflight_passed
            or not decision.eligible_for_future_one_shot_review
        ):
            raise LiveVerificationValidationError("ready preflight must be eligible")
        if decision.blocked_reasons:
            raise LiveVerificationValidationError("ready preflight cannot have blockers")
    else:
        if decision.preflight_passed or decision.eligible_for_future_one_shot_review:
            raise LiveVerificationValidationError("blocked preflight cannot pass")
        if not decision.blocked_reasons:
            raise LiveVerificationValidationError("blocked preflight requires blockers")


def _add_reason(
    reasons: list[LiveOrderFinalDynamicPreflightBlockReason],
    reason: LiveOrderFinalDynamicPreflightBlockReason,
) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _candidate_id(snapshot: LiveOrderFinalDynamicPreflightSnapshot) -> str:
    return _snapshot_text(snapshot, "candidate_id")


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


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")


def _safe_value(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _simulation_id(
    simulation: LiveOrderApprovalValidationSimulation | None,
    snapshot: LiveOrderFinalDynamicPreflightSnapshot,
) -> str:
    if isinstance(simulation, LiveOrderApprovalValidationSimulation) and _has_text(
        simulation.simulation_id
    ):
        return simulation.simulation_id
    return _snapshot_text(snapshot, "simulation_id")


def _snapshot_id(snapshot: LiveOrderFinalDynamicPreflightSnapshot) -> str:
    return _snapshot_text(snapshot, "snapshot_id")


def _snapshot_int(
    snapshot: LiveOrderFinalDynamicPreflightSnapshot,
    field_name: str,
) -> int:
    value = getattr(snapshot, field_name, 0)
    return value if type(value) is int else 0


def _snapshot_text(
    snapshot: LiveOrderFinalDynamicPreflightSnapshot,
    field_name: str,
) -> str:
    value = getattr(snapshot, field_name, None)
    return value.strip() if _has_text(value) else f"missing_{field_name}"


def _valid_age(value: object, threshold: object) -> bool:
    return _numeric(value) and _valid_int(threshold) and 0 <= value <= threshold


def _valid_int(value: object) -> bool:
    return type(value) is int and value >= 0
