"""Dry-run one-shot execution runbook model for Step 5O."""

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
from app.live_verification.live_order_one_shot_boundary import (
    ONE_SHOT_POST_ATTEMPT_LIMIT,
    LiveOrderOneShotBoundaryDecision,
    LiveOrderOneShotBoundaryStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_ONE_SHOT_EXECUTION_RUNBOOK_ID_PREFIX = "LOOER-"

REQUIRED_PHASE_NAMES = (
    "real_approval_gate_separate_step",
    "fresh_final_dynamic_preflight_separate_step",
    "one_shot_http_post_separate_step",
    "post_reconciliation_separate_step",
    "final_report_and_stop",
)
REQUIRED_GO_CONDITIONS = (
    "one_shot_boundary_passed",
    "future_separate_real_approval_gate_required",
    "future_separate_fresh_final_dynamic_preflight_required",
    "post_attempt_limit_equals_1",
    "no_retry_loop_add_change_cancel_close",
    "outbound_body_allowlist_matched",
    "request_body_equals_signing_body",
    "post_reconciliation_required",
    "raw_response_display_storage_forbidden",
)
REQUIRED_NO_GO_CONDITIONS = (
    "blocked_reason_exists",
    "unknown_status",
    "stale_preflight",
    "result_unknown_true",
    "existing_position_or_order",
    "spread_too_wide",
    "maintenance_active",
    "important_event_window_not_ok",
    "git_tests_ruff_secret_scan_not_clean",
    "request_body_signing_body_mismatch",
    "raw_response_display_storage_needed",
)
REQUIRED_STOP_CONDITIONS = (
    "same_error_repeated_without_new_evidence",
    "final_dynamic_preflight_stale",
    "approval_expired",
    "result_unknown",
    "post_result_unknown",
    "reconciliation_impossible",
    "unexpected_api_response_shape",
    "secret_raw_response_id_exposure_risk",
    "retry_loop_add_change_cancel_close_needed",
    "exceed_one_post_attempt_needed",
)
FORBIDDEN_PHASE_ACTIONS = (
    "execute_http_post",
    "call_read_only_api",
    "call_private_api",
    "call_public_api",
    "call_broker",
    "call_live_order_once",
    "issue_real_approval_gate",
    "generate_real_approval_id",
    "generate_real_approval_command",
    "copy_approval_command",
    "save_approval_command",
    "retry",
    "loop",
    "add_order",
    "change_order",
    "cancel_order",
    "close_order",
    "read_ledger",
    "write_ledger",
)


class LiveOrderOneShotExecutionRunbookStatus(str, Enum):
    READY_FOR_ONE_SHOT_EXECUTION_RUNBOOK_REVIEW = (
        "READY_FOR_ONE_SHOT_EXECUTION_RUNBOOK_REVIEW"
    )
    BLOCKED_ONE_SHOT_EXECUTION_RUNBOOK = "BLOCKED_ONE_SHOT_EXECUTION_RUNBOOK"


class LiveOrderOneShotExecutionRunbookBlockReason(str, Enum):
    BOUNDARY_NOT_READY = "boundary_not_ready"
    BOUNDARY_ALLOWS_LIVE = "boundary_allows_live"
    BOUNDARY_NOT_DRY_RUN = "boundary_not_dry_run"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_ID_ALREADY_GENERATED = "approval_id_already_generated"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
    APPROVAL_COMMAND_NOT_TEMPLATE_ONLY = "approval_command_not_template_only"
    APPROVAL_COMMAND_COPYABLE = "approval_command_copyable"
    POST_ALREADY_EXECUTED = "post_already_executed"
    LIVE_ORDER_ONCE_ALREADY_CALLED = "live_order_once_already_called"
    PRIVATE_API_ALREADY_CALLED = "private_api_already_called"
    BROKER_ALREADY_CALLED = "broker_already_called"
    READ_ONLY_API_ALREADY_CALLED = "read_only_api_already_called"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    INVALID_POST_ATTEMPT_LIMIT = "invalid_post_attempt_limit"
    RETRY_ALLOWED = "retry_allowed"
    LOOP_ALLOWED = "loop_allowed"
    ADD_ORDER_ALLOWED = "add_order_allowed"
    CHANGE_ORDER_ALLOWED = "change_order_allowed"
    CANCEL_ORDER_ALLOWED = "cancel_order_allowed"
    CLOSE_ORDER_ALLOWED = "close_order_allowed"
    MISSING_POST_RECONCILIATION_REQUIREMENT = (
        "missing_post_reconciliation_requirement"
    )
    MISSING_REQUIRED_PHASE = "missing_required_phase"
    PHASE_CONTAINS_FORBIDDEN_ACTION = "phase_contains_forbidden_action"
    MISSING_GO_CONDITIONS = "missing_go_conditions"
    MISSING_NO_GO_CONDITIONS = "missing_no_go_conditions"
    MISSING_STOP_CONDITIONS = "missing_stop_conditions"


@dataclass(frozen=True)
class LiveOrderOneShotExecutionRunbookCheckResult:
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
class LiveOrderOneShotExecutionRunbookStep:
    step_id: str
    phase_name: str
    title: str
    description: str
    stop_condition: str

    def __post_init__(self) -> None:
        _require_non_empty("step_id", self.step_id)
        _require_non_empty("phase_name", self.phase_name)
        _require_non_empty("title", self.title)
        _require_non_empty("description", self.description)
        _require_non_empty("stop_condition", self.stop_condition)


@dataclass(frozen=True)
class LiveOrderOneShotExecutionRunbookPhase:
    name: str
    purpose: str
    go_conditions: tuple[str, ...]
    no_go_conditions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    next_phase: str

    def __post_init__(self) -> None:
        _require_non_empty("name", self.name)
        _require_non_empty("purpose", self.purpose)
        _require_non_empty("next_phase", self.next_phase)
        for action in self.allowed_actions:
            _require_non_empty("allowed action", action)
        for action in self.forbidden_actions:
            _require_non_empty("forbidden action", action)


@dataclass(frozen=True)
class LiveOrderOneShotExecutionRunbookSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError("runbook section requires lines")
        for line in self.lines:
            _require_non_empty("section line", line)


@dataclass(frozen=True)
class LiveOrderOneShotExecutionRunbook:
    runbook_id: str
    created_at: datetime
    boundary_id: str
    preflight_decision_id: str
    snapshot_id: str
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
    runbook_status: LiveOrderOneShotExecutionRunbookStatus
    runbook_ready: bool
    eligible_for_future_execution_planning: bool
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
    post_attempt_limit: int
    post_executed: bool
    live_order_once_called: bool
    private_api_called: bool
    broker_called: bool
    read_only_api_called: bool
    retry_allowed: bool
    loop_allowed: bool
    add_order_allowed: bool
    change_order_allowed: bool
    cancel_order_allowed: bool
    close_order_allowed: bool
    post_reconciliation_required: bool
    phases: tuple[LiveOrderOneShotExecutionRunbookPhase, ...]
    steps: tuple[LiveOrderOneShotExecutionRunbookStep, ...]
    go_conditions: tuple[str, ...]
    no_go_conditions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    check_results: tuple[LiveOrderOneShotExecutionRunbookCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderOneShotExecutionRunbookSection, ...]

    def __post_init__(self) -> None:
        _validate_runbook(self)


@dataclass(frozen=True)
class LiveOrderOneShotExecutionRunbookBuildResult:
    runbook: LiveOrderOneShotExecutionRunbook
    runbook_id: str
    runbook_status: LiveOrderOneShotExecutionRunbookStatus
    blocked_reasons: tuple[str, ...]
    runbook_ready: bool
    eligible_for_future_execution_planning: bool
    allowed_for_live: bool
    post_attempt_limit: int
    post_executed: bool
    live_order_once_called: bool
    private_api_called: bool
    broker_called: bool
    read_only_api_called: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.runbook.runbook_id != self.runbook_id:
            raise LiveVerificationValidationError("runbook_id mismatch")
        if self.runbook.runbook_status is not self.runbook_status:
            raise LiveVerificationValidationError("runbook_status mismatch")
        if self.runbook.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.runbook.runbook_ready is not self.runbook_ready:
            raise LiveVerificationValidationError("runbook_ready mismatch")
        if (
            self.runbook.eligible_for_future_execution_planning
            is not self.eligible_for_future_execution_planning
        ):
            raise LiveVerificationValidationError("eligible planning mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("Step 5O never allows live execution")
        if self.post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
            raise LiveVerificationValidationError("one-shot attempt limit mismatch")
        if self.post_executed is not False:
            raise LiveVerificationValidationError("Step 5O never executes POST")
        if self.live_order_once_called is not False:
            raise LiveVerificationValidationError("Step 5O never calls one-shot runner")
        if self.private_api_called is not False:
            raise LiveVerificationValidationError("Step 5O never calls Private API")
        if self.broker_called is not False:
            raise LiveVerificationValidationError("Step 5O never calls broker")
        if self.read_only_api_called is not False:
            raise LiveVerificationValidationError("Step 5O never calls read-only API")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def build_live_order_one_shot_execution_runbook(
    *,
    one_shot_boundary_decision: LiveOrderOneShotBoundaryDecision,
    created_at: datetime | None = None,
    phases: tuple[LiveOrderOneShotExecutionRunbookPhase, ...] | None = None,
    go_conditions: tuple[str, ...] = REQUIRED_GO_CONDITIONS,
    no_go_conditions: tuple[str, ...] = REQUIRED_NO_GO_CONDITIONS,
    stop_conditions: tuple[str, ...] = REQUIRED_STOP_CONDITIONS,
    post_attempt_limit: int = ONE_SHOT_POST_ATTEMPT_LIMIT,
    post_executed: bool = False,
    live_order_once_called: bool = False,
    private_api_called: bool = False,
    broker_called: bool = False,
    read_only_api_called: bool = False,
    retry_allowed: bool = False,
    loop_allowed: bool = False,
    add_order_allowed: bool = False,
    change_order_allowed: bool = False,
    cancel_order_allowed: bool = False,
    close_order_allowed: bool = False,
    post_reconciliation_required: bool = True,
) -> LiveOrderOneShotExecutionRunbookBuildResult:
    """Build a future execution runbook without issuing approval or calling APIs."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    safe_phases = phases or build_default_one_shot_execution_runbook_phases()
    boundary_reasons = _boundary_blocked_reasons(one_shot_boundary_decision)
    runbook_reasons = _runbook_constraint_reasons(
        phases=safe_phases,
        go_conditions=go_conditions,
        no_go_conditions=no_go_conditions,
        stop_conditions=stop_conditions,
        post_attempt_limit=post_attempt_limit,
        post_executed=post_executed,
        live_order_once_called=live_order_once_called,
        private_api_called=private_api_called,
        broker_called=broker_called,
        read_only_api_called=read_only_api_called,
        retry_allowed=retry_allowed,
        loop_allowed=loop_allowed,
        add_order_allowed=add_order_allowed,
        change_order_allowed=change_order_allowed,
        cancel_order_allowed=cancel_order_allowed,
        close_order_allowed=close_order_allowed,
        post_reconciliation_required=post_reconciliation_required,
    )
    blocked_reasons = _merge_reasons(
        boundary_reasons,
        _boundary_existing_reasons(one_shot_boundary_decision),
        runbook_reasons,
    )
    check_results = _build_check_results(
        boundary=one_shot_boundary_decision,
        phases=safe_phases,
        go_conditions=go_conditions,
        no_go_conditions=no_go_conditions,
        stop_conditions=stop_conditions,
        post_attempt_limit=post_attempt_limit,
        post_executed=post_executed,
        live_order_once_called=live_order_once_called,
        private_api_called=private_api_called,
        broker_called=broker_called,
        read_only_api_called=read_only_api_called,
        retry_allowed=retry_allowed,
        loop_allowed=loop_allowed,
        add_order_allowed=add_order_allowed,
        change_order_allowed=change_order_allowed,
        cancel_order_allowed=cancel_order_allowed,
        close_order_allowed=close_order_allowed,
        post_reconciliation_required=post_reconciliation_required,
    )

    if blocked_reasons:
        status = (
            LiveOrderOneShotExecutionRunbookStatus.BLOCKED_ONE_SHOT_EXECUTION_RUNBOOK
        )
        ready = False
        eligible = False
        if boundary_reasons or _boundary_existing_reasons(one_shot_boundary_decision):
            recommended_next_step = "fix_one_shot_boundary_blockers_no_post"
        else:
            recommended_next_step = "fix_execution_runbook_constraints_no_post"
        summary = "blocked one-shot execution runbook review; live post remains disallowed"
    else:
        status = (
            LiveOrderOneShotExecutionRunbookStatus.READY_FOR_ONE_SHOT_EXECUTION_RUNBOOK_REVIEW
        )
        ready = True
        eligible = True
        recommended_next_step = (
            "review_runbook_then_prepare_future_real_approval_gate_separate_step_no_post"
        )
        summary = (
            "ready for dry-run one-shot execution runbook review only; "
            "live post remains disallowed"
        )

    runbook_id = make_live_order_one_shot_execution_runbook_id(
        boundary_id=_boundary_text(one_shot_boundary_decision, "boundary_id"),
        candidate_id=_boundary_text(one_shot_boundary_decision, "candidate_id"),
        created_at=created,
        runbook_status=status,
        blocked_reasons=blocked_reasons,
    )
    runbook = LiveOrderOneShotExecutionRunbook(
        runbook_id=runbook_id,
        created_at=created,
        boundary_id=_boundary_text(one_shot_boundary_decision, "boundary_id"),
        preflight_decision_id=_boundary_text(
            one_shot_boundary_decision,
            "preflight_decision_id",
        ),
        snapshot_id=_boundary_text(one_shot_boundary_decision, "snapshot_id"),
        simulation_id=_boundary_text(one_shot_boundary_decision, "simulation_id"),
        preview_id=_boundary_text(one_shot_boundary_decision, "preview_id"),
        design_id=_boundary_text(one_shot_boundary_decision, "design_id"),
        handoff_id=_boundary_text(one_shot_boundary_decision, "handoff_id"),
        operator_review_id=_boundary_text(
            one_shot_boundary_decision,
            "operator_review_id",
        ),
        bundle_id=_boundary_text(one_shot_boundary_decision, "bundle_id"),
        review_id=_boundary_text(one_shot_boundary_decision, "review_id"),
        candidate_id=_boundary_text(one_shot_boundary_decision, "candidate_id"),
        risk_decision_id=_boundary_text(one_shot_boundary_decision, "risk_decision_id"),
        trace_id=_boundary_text(one_shot_boundary_decision, "trace_id"),
        session_policy_decision_id=_boundary_text(
            one_shot_boundary_decision,
            "session_policy_decision_id",
        ),
        source_signal_id=_boundary_text(one_shot_boundary_decision, "source_signal_id"),
        source_type=_boundary_text(one_shot_boundary_decision, "source_type"),
        strategy_name=_boundary_text(one_shot_boundary_decision, "strategy_name"),
        symbol=_boundary_text(one_shot_boundary_decision, "symbol"),
        side=_boundary_text(one_shot_boundary_decision, "side"),
        size=_boundary_int(one_shot_boundary_decision, "size"),
        execution_type=_boundary_text(one_shot_boundary_decision, "execution_type"),
        runbook_status=status,
        runbook_ready=ready,
        eligible_for_future_execution_planning=eligible,
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
        post_attempt_limit=ONE_SHOT_POST_ATTEMPT_LIMIT,
        post_executed=False,
        live_order_once_called=False,
        private_api_called=False,
        broker_called=False,
        read_only_api_called=False,
        retry_allowed=False,
        loop_allowed=False,
        add_order_allowed=False,
        change_order_allowed=False,
        cancel_order_allowed=False,
        close_order_allowed=False,
        post_reconciliation_required=True,
        phases=safe_phases,
        steps=build_default_one_shot_execution_runbook_steps(),
        go_conditions=tuple(go_conditions),
        no_go_conditions=tuple(no_go_conditions),
        stop_conditions=tuple(stop_conditions),
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            boundary=one_shot_boundary_decision,
            phases=safe_phases,
            status=status,
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
        ),
    )
    return LiveOrderOneShotExecutionRunbookBuildResult(
        runbook=runbook,
        runbook_id=runbook.runbook_id,
        runbook_status=runbook.runbook_status,
        blocked_reasons=runbook.blocked_reasons,
        runbook_ready=runbook.runbook_ready,
        eligible_for_future_execution_planning=runbook.eligible_for_future_execution_planning,
        allowed_for_live=False,
        post_attempt_limit=ONE_SHOT_POST_ATTEMPT_LIMIT,
        post_executed=False,
        live_order_once_called=False,
        private_api_called=False,
        broker_called=False,
        read_only_api_called=False,
        recommended_next_step=runbook.recommended_next_step,
    )


def build_default_one_shot_execution_runbook_phases() -> tuple[
    LiveOrderOneShotExecutionRunbookPhase,
    ...,
]:
    """Return the dry-run future execution phases without executing them."""
    return (
        LiveOrderOneShotExecutionRunbookPhase(
            name="real_approval_gate_separate_step",
            purpose=(
                "future separate task only; Step 5O does not issue approval gates "
                "or generate approval text"
            ),
            go_conditions=(
                "operator_explicit_approval_required_in_future_step",
                "fresh_preflight_preconditions_ready",
            ),
            no_go_conditions=("unknown_stale_or_mismatched_operator_context",),
            stop_conditions=("approval_gate_needed_in_current_step",),
            allowed_actions=("document_future_approval_requirements",),
            forbidden_actions=FORBIDDEN_PHASE_ACTIONS,
            next_phase="fresh_final_dynamic_preflight_separate_step",
        ),
        LiveOrderOneShotExecutionRunbookPhase(
            name="fresh_final_dynamic_preflight_separate_step",
            purpose=(
                "future separate task only; Step 5O does not execute dynamic "
                "preflight or call account/order APIs"
            ),
            go_conditions=(
                "real_approval_valid_and_same_session",
                "secret_safe_raw_response_hidden",
            ),
            no_go_conditions=(
                "spread_positions_orders_market_event_or_git_tests_secret_scan_ng",
            ),
            stop_conditions=("final_dynamic_preflight_stale_or_unknown",),
            allowed_actions=("document_future_preflight_requirements",),
            forbidden_actions=FORBIDDEN_PHASE_ACTIONS,
            next_phase="one_shot_http_post_separate_step",
        ),
        LiveOrderOneShotExecutionRunbookPhase(
            name="one_shot_http_post_separate_step",
            purpose=(
                "future separate task only; Step 5O does not execute HTTP POST "
                "or call the one-shot runner"
            ),
            go_conditions=(
                "fresh_preflight_age_within_limit",
                "body_allowlist_and_signing_body_match",
                "post_attempt_limit_equals_1",
            ),
            no_go_conditions=("mismatch_unknown_or_previous_result_not_confirmed",),
            stop_conditions=("need_retry_loop_or_second_attempt",),
            allowed_actions=("document_future_single_attempt_boundary",),
            forbidden_actions=FORBIDDEN_PHASE_ACTIONS,
            next_phase="post_reconciliation_separate_step",
        ),
        LiveOrderOneShotExecutionRunbookPhase(
            name="post_reconciliation_separate_step",
            purpose=(
                "future separate task only; Step 5O does not execute reconciliation "
                "or call read-only APIs"
            ),
            go_conditions=("future_single_post_attempt_completed_with_interpretable_result",),
            no_go_conditions=("result_unknown_or_reconciliation_impossible",),
            stop_conditions=("raw_response_or_id_exposure_risk",),
            allowed_actions=("document_future_sanitized_reconciliation_requirements",),
            forbidden_actions=FORBIDDEN_PHASE_ACTIONS,
            next_phase="final_report_and_stop",
        ),
        LiveOrderOneShotExecutionRunbookPhase(
            name="final_report_and_stop",
            purpose=(
                "future final report task only; stop after the one-shot result "
                "without follow-up orders"
            ),
            go_conditions=("result_reported_as_success_failure_or_unknown",),
            no_go_conditions=("additional_order_or_retry_requested",),
            stop_conditions=("final_report_complete_or_unknown_state_detected",),
            allowed_actions=("document_future_stop_report_requirements",),
            forbidden_actions=FORBIDDEN_PHASE_ACTIONS,
            next_phase="stop",
        ),
    )


def build_default_one_shot_execution_runbook_steps() -> tuple[
    LiveOrderOneShotExecutionRunbookStep,
    ...,
]:
    """Return sanitized human-readable steps for the dry-run runbook."""
    return (
        LiveOrderOneShotExecutionRunbookStep(
            step_id="step5o-approval-separate",
            phase_name="real_approval_gate_separate_step",
            title="Future real approval gate",
            description="Describe the future approval gate; do not issue it in Step 5O.",
            stop_condition="real approval gate is needed in the current task",
        ),
        LiveOrderOneShotExecutionRunbookStep(
            step_id="step5o-preflight-separate",
            phase_name="fresh_final_dynamic_preflight_separate_step",
            title="Future fresh final dynamic preflight",
            description="Describe the future preflight; do not execute it in Step 5O.",
            stop_condition="fresh API or ledger state is required in the current task",
        ),
        LiveOrderOneShotExecutionRunbookStep(
            step_id="step5o-single-attempt-separate",
            phase_name="one_shot_http_post_separate_step",
            title="Future single attempt boundary",
            description="Describe one future single attempt; do not execute it in Step 5O.",
            stop_condition="a live order attempt is requested in the current task",
        ),
        LiveOrderOneShotExecutionRunbookStep(
            step_id="step5o-reconciliation-separate",
            phase_name="post_reconciliation_separate_step",
            title="Future post reconciliation",
            description="Describe sanitized reconciliation; do not call APIs in Step 5O.",
            stop_condition="post reconciliation execution is requested in the current task",
        ),
        LiveOrderOneShotExecutionRunbookStep(
            step_id="step5o-final-report-stop",
            phase_name="final_report_and_stop",
            title="Future final report and stop",
            description="Describe the future stop report and forbid follow-up actions.",
            stop_condition="any retry or follow-up order is requested",
        ),
    )


def render_live_order_one_shot_execution_runbook_markdown(
    runbook: LiveOrderOneShotExecutionRunbook,
) -> str:
    """Render a sanitized dry-run one-shot execution runbook."""
    lines = [
        "# Live Order One-shot Execution Runbook",
        "",
        "This one-shot execution runbook is dry-run only.",
        "This runbook does not call read-only API.",
        "This runbook does not call Private API.",
        "This runbook does not call live_order_once.",
        "This runbook does not execute HTTP POST.",
        "This runbook does not issue a real approval gate.",
        "This runbook does not generate a real approval command.",
        "This runbook does not authorize live POST.",
        "allowed_for_live=false.",
        "",
        "## Summary",
        "",
        f"- runbook_id: {runbook.runbook_id}",
        f"- boundary_id: {runbook.boundary_id}",
        f"- runbook_status: {runbook.runbook_status.value}",
        f"- runbook_ready: {runbook.runbook_ready}",
        (
            "- eligible_for_future_execution_planning: "
            f"{runbook.eligible_for_future_execution_planning}"
        ),
        f"- allowed_for_live: {runbook.allowed_for_live}",
        f"- post_attempt_limit: {runbook.post_attempt_limit}",
        f"- post_executed: {runbook.post_executed}",
        f"- recommended_next_step: {runbook.recommended_next_step}",
        "",
    ]
    for section in runbook.sections:
        lines.extend([f"## {section.title}", ""])
        lines.extend(f"- {line}" for line in section.lines)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def make_live_order_one_shot_execution_runbook_id(
    *,
    boundary_id: str,
    candidate_id: str,
    created_at: datetime,
    runbook_status: LiveOrderOneShotExecutionRunbookStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    _require_non_empty("boundary_id", boundary_id)
    _require_non_empty("candidate_id", candidate_id)
    created = _ensure_aware(created_at)
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "boundary_id": boundary_id,
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "runbook_status": runbook_status.value,
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{LIVE_ORDER_ONE_SHOT_EXECUTION_RUNBOOK_ID_PREFIX}{digest.upper()}"


def _boundary_blocked_reasons(
    boundary: LiveOrderOneShotBoundaryDecision,
) -> tuple[str, ...]:
    reasons: list[LiveOrderOneShotExecutionRunbookBlockReason] = []
    if not isinstance(boundary, LiveOrderOneShotBoundaryDecision):
        return (LiveOrderOneShotExecutionRunbookBlockReason.BOUNDARY_NOT_READY.value,)
    if (
        boundary.boundary_status
        is not LiveOrderOneShotBoundaryStatus.READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW
        or boundary.boundary_passed is not True
        or boundary.eligible_for_future_one_shot_live_review is not True
    ):
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.BOUNDARY_NOT_READY)
    if boundary.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.BOUNDARY_ALLOWS_LIVE)
    if boundary.dry_run_only is not True:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.BOUNDARY_NOT_DRY_RUN)
    if boundary.approval_gate_issued is not False:
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        )
    if boundary.approval_id_generated is not False:
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        )
    if boundary.approval_command_generated is not False:
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        )
    if boundary.approval_command_template_only is not True:
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.APPROVAL_COMMAND_NOT_TEMPLATE_ONLY,
        )
    if boundary.approval_command_copyable is not False:
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.APPROVAL_COMMAND_COPYABLE,
        )
    if boundary.post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.INVALID_POST_ATTEMPT_LIMIT,
        )
    if boundary.post_executed is not False:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.POST_ALREADY_EXECUTED)
    if boundary.live_order_once_called is not False:
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        )
    if boundary.private_api_called is not False:
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.PRIVATE_API_ALREADY_CALLED,
        )
    if boundary.broker_called is not False:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.BROKER_ALREADY_CALLED)
    if boundary.read_only_api_called is not False:
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.READ_ONLY_API_ALREADY_CALLED,
        )
    if boundary.retry_allowed is not False:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.RETRY_ALLOWED)
    if boundary.loop_allowed is not False:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.LOOP_ALLOWED)
    if boundary.add_order_allowed is not False:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.ADD_ORDER_ALLOWED)
    if boundary.change_order_allowed is not False:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.CHANGE_ORDER_ALLOWED)
    if boundary.cancel_order_allowed is not False:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.CANCEL_ORDER_ALLOWED)
    if boundary.close_order_allowed is not False:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.CLOSE_ORDER_ALLOWED)
    if boundary.post_reconciliation_required is not True:
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        )
    if boundary.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.UNSUPPORTED_SYMBOL)
    if boundary.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.UNSUPPORTED_SIDE)
    if boundary.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.UNSUPPORTED_SIZE)
    if boundary.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        )
    return tuple(reason.value for reason in reasons)


def _runbook_constraint_reasons(
    *,
    phases: tuple[LiveOrderOneShotExecutionRunbookPhase, ...],
    go_conditions: tuple[str, ...],
    no_go_conditions: tuple[str, ...],
    stop_conditions: tuple[str, ...],
    post_attempt_limit: int,
    post_executed: bool,
    live_order_once_called: bool,
    private_api_called: bool,
    broker_called: bool,
    read_only_api_called: bool,
    retry_allowed: bool,
    loop_allowed: bool,
    add_order_allowed: bool,
    change_order_allowed: bool,
    cancel_order_allowed: bool,
    close_order_allowed: bool,
    post_reconciliation_required: bool,
) -> tuple[str, ...]:
    reasons: list[LiveOrderOneShotExecutionRunbookBlockReason] = []
    phase_names = {phase.name for phase in phases}
    if not set(REQUIRED_PHASE_NAMES).issubset(phase_names):
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.MISSING_REQUIRED_PHASE)
    if _phase_allowed_actions_contain_forbidden(phases):
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.PHASE_CONTAINS_FORBIDDEN_ACTION,
        )
    if not _required_conditions_present(go_conditions, REQUIRED_GO_CONDITIONS) or any(
        not phase.go_conditions for phase in phases
    ):
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.MISSING_GO_CONDITIONS)
    if not _required_conditions_present(
        no_go_conditions,
        REQUIRED_NO_GO_CONDITIONS,
    ) or any(not phase.no_go_conditions for phase in phases):
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.MISSING_NO_GO_CONDITIONS,
        )
    if not _required_conditions_present(
        stop_conditions,
        REQUIRED_STOP_CONDITIONS,
    ) or any(not phase.stop_conditions for phase in phases):
        _add_reason(
            reasons,
            LiveOrderOneShotExecutionRunbookBlockReason.MISSING_STOP_CONDITIONS,
        )
    if post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
        _add_reason(reasons, LiveOrderOneShotExecutionRunbookBlockReason.INVALID_POST_ATTEMPT_LIMIT)
    _expect_false(
        reasons,
        post_executed,
        LiveOrderOneShotExecutionRunbookBlockReason.POST_ALREADY_EXECUTED,
    )
    _expect_false(
        reasons,
        live_order_once_called,
        LiveOrderOneShotExecutionRunbookBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
    )
    _expect_false(
        reasons,
        private_api_called,
        LiveOrderOneShotExecutionRunbookBlockReason.PRIVATE_API_ALREADY_CALLED,
    )
    _expect_false(
        reasons,
        broker_called,
        LiveOrderOneShotExecutionRunbookBlockReason.BROKER_ALREADY_CALLED,
    )
    _expect_false(
        reasons,
        read_only_api_called,
        LiveOrderOneShotExecutionRunbookBlockReason.READ_ONLY_API_ALREADY_CALLED,
    )
    _expect_false(reasons, retry_allowed, LiveOrderOneShotExecutionRunbookBlockReason.RETRY_ALLOWED)
    _expect_false(reasons, loop_allowed, LiveOrderOneShotExecutionRunbookBlockReason.LOOP_ALLOWED)
    _expect_false(
        reasons,
        add_order_allowed,
        LiveOrderOneShotExecutionRunbookBlockReason.ADD_ORDER_ALLOWED,
    )
    _expect_false(
        reasons,
        change_order_allowed,
        LiveOrderOneShotExecutionRunbookBlockReason.CHANGE_ORDER_ALLOWED,
    )
    _expect_false(
        reasons,
        cancel_order_allowed,
        LiveOrderOneShotExecutionRunbookBlockReason.CANCEL_ORDER_ALLOWED,
    )
    _expect_false(
        reasons,
        close_order_allowed,
        LiveOrderOneShotExecutionRunbookBlockReason.CLOSE_ORDER_ALLOWED,
    )
    _expect_true(
        reasons,
        post_reconciliation_required,
        LiveOrderOneShotExecutionRunbookBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
    )
    return tuple(reason.value for reason in reasons)


def _build_check_results(
    *,
    boundary: LiveOrderOneShotBoundaryDecision,
    phases: tuple[LiveOrderOneShotExecutionRunbookPhase, ...],
    go_conditions: tuple[str, ...],
    no_go_conditions: tuple[str, ...],
    stop_conditions: tuple[str, ...],
    post_attempt_limit: int,
    post_executed: bool,
    live_order_once_called: bool,
    private_api_called: bool,
    broker_called: bool,
    read_only_api_called: bool,
    retry_allowed: bool,
    loop_allowed: bool,
    add_order_allowed: bool,
    change_order_allowed: bool,
    cancel_order_allowed: bool,
    close_order_allowed: bool,
    post_reconciliation_required: bool,
) -> tuple[LiveOrderOneShotExecutionRunbookCheckResult, ...]:
    phase_names = {phase.name for phase in phases}
    return (
        _check(
            "one_shot_boundary_decision",
            isinstance(boundary, LiveOrderOneShotBoundaryDecision)
            and boundary.boundary_status
            is LiveOrderOneShotBoundaryStatus.READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW
            and boundary.boundary_passed is True,
            _enum_value(getattr(boundary, "boundary_status", "missing")),
            "READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW",
        ),
        _check(
            "boundary_allowed_for_live",
            getattr(boundary, "allowed_for_live", None) is False,
            getattr(boundary, "allowed_for_live", None),
            "false",
        ),
        _check("post_attempt_limit", post_attempt_limit == 1, post_attempt_limit, "1"),
        _check("post_not_executed", post_executed is False, post_executed, "false"),
        _check(
            "live_order_once_not_called",
            live_order_once_called is False,
            live_order_once_called,
            "false",
        ),
        _check("private_api_not_called", private_api_called is False, private_api_called, "false"),
        _check("broker_not_called", broker_called is False, broker_called, "false"),
        _check(
            "read_only_api_not_called",
            read_only_api_called is False,
            read_only_api_called,
            "false",
        ),
        _check("no_retry", retry_allowed is False, retry_allowed, "false"),
        _check("no_loop", loop_allowed is False, loop_allowed, "false"),
        _check("no_add_order", add_order_allowed is False, add_order_allowed, "false"),
        _check(
            "no_change_order",
            change_order_allowed is False,
            change_order_allowed,
            "false",
        ),
        _check(
            "no_cancel_order",
            cancel_order_allowed is False,
            cancel_order_allowed,
            "false",
        ),
        _check("no_close_order", close_order_allowed is False, close_order_allowed, "false"),
        _check(
            "post_reconciliation_required",
            post_reconciliation_required is True,
            post_reconciliation_required,
            "true",
        ),
        _check(
            "required_phases",
            set(REQUIRED_PHASE_NAMES).issubset(phase_names),
            ",".join(sorted(phase_names)) if phase_names else "none",
            ",".join(REQUIRED_PHASE_NAMES),
        ),
        _check(
            "phase_allowed_actions_safe",
            not _phase_allowed_actions_contain_forbidden(phases),
            "safe" if not _phase_allowed_actions_contain_forbidden(phases) else "unsafe",
            "safe",
        ),
        _check(
            "go_conditions",
            _required_conditions_present(go_conditions, REQUIRED_GO_CONDITIONS)
            and all(phase.go_conditions for phase in phases),
            ",".join(go_conditions) if go_conditions else "none",
            ",".join(REQUIRED_GO_CONDITIONS),
        ),
        _check(
            "no_go_conditions",
            _required_conditions_present(no_go_conditions, REQUIRED_NO_GO_CONDITIONS)
            and all(phase.no_go_conditions for phase in phases),
            ",".join(no_go_conditions) if no_go_conditions else "none",
            ",".join(REQUIRED_NO_GO_CONDITIONS),
        ),
        _check(
            "stop_conditions",
            _required_conditions_present(stop_conditions, REQUIRED_STOP_CONDITIONS)
            and all(phase.stop_conditions for phase in phases),
            ",".join(stop_conditions) if stop_conditions else "none",
            ",".join(REQUIRED_STOP_CONDITIONS),
        ),
    )


def _build_sections(
    *,
    boundary: LiveOrderOneShotBoundaryDecision,
    phases: tuple[LiveOrderOneShotExecutionRunbookPhase, ...],
    status: LiveOrderOneShotExecutionRunbookStatus,
    check_results: tuple[LiveOrderOneShotExecutionRunbookCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
) -> tuple[LiveOrderOneShotExecutionRunbookSection, ...]:
    blocked_text = ", ".join(blocked_reasons) if blocked_reasons else "none"
    failed_checks = tuple(check.name for check in check_results if not check.passed)
    failed_text = ", ".join(failed_checks) if failed_checks else "none"
    phase_text = ", ".join(phase.name for phase in phases)
    return (
        LiveOrderOneShotExecutionRunbookSection(
            section_id="references",
            title="Sanitized References",
            lines=(
                _section_line(boundary, "boundary_id"),
                _section_line(boundary, "preflight_decision_id"),
                _section_line(boundary, "snapshot_id"),
                _section_line(boundary, "simulation_id"),
                _section_line(boundary, "bundle_id"),
                _section_line(boundary, "review_id"),
                _section_line(boundary, "candidate_id"),
                _section_line(boundary, "risk_decision_id"),
                _section_line(boundary, "trace_id"),
            ),
        ),
        LiveOrderOneShotExecutionRunbookSection(
            section_id="candidate",
            title="Candidate",
            lines=(
                _section_line(boundary, "source_signal_id"),
                _section_line(boundary, "source_type"),
                _section_line(boundary, "strategy_name"),
                _section_line(boundary, "symbol"),
                _section_line(boundary, "side"),
                f"size: {_boundary_int(boundary, 'size')}",
                f"executionType: {_boundary_text(boundary, 'execution_type')}",
            ),
        ),
        LiveOrderOneShotExecutionRunbookSection(
            section_id="safety_defaults",
            title="Safety Defaults",
            lines=(
                "allowed_for_live: False",
                "approval_gate_issued: False",
                "approval_id_generated: False",
                "approval_command_generated: False",
                "approval_command_template_only: True",
                "approval_command_copyable: False",
                "final_dynamic_preflight_required: True",
                "dry_run_only: True",
                "post_attempt_limit: 1",
                "post_executed: False",
                "live_order_once_called: False",
                "private_api_called: False",
                "broker_called: False",
                "read_only_api_called: False",
            ),
        ),
        LiveOrderOneShotExecutionRunbookSection(
            section_id="phases",
            title="Execution Phases",
            lines=(f"phases: {phase_text}",),
        ),
        LiveOrderOneShotExecutionRunbookSection(
            section_id="conditions",
            title="Go No-go Stop Conditions",
            lines=(
                f"go_conditions: {', '.join(REQUIRED_GO_CONDITIONS)}",
                f"no_go_conditions: {', '.join(REQUIRED_NO_GO_CONDITIONS)}",
                f"stop_conditions: {', '.join(REQUIRED_STOP_CONDITIONS)}",
            ),
        ),
        LiveOrderOneShotExecutionRunbookSection(
            section_id="decision",
            title="Runbook Decision",
            lines=(
                f"runbook_status: {status.value}",
                "allowed_for_live: False",
                f"failed_checks: {failed_text}",
                f"blocked_reasons: {blocked_text}",
                f"recommended_next_step: {recommended_next_step}",
            ),
        ),
    )


def _validate_runbook(runbook: LiveOrderOneShotExecutionRunbook) -> None:
    _require_non_empty("runbook_id", runbook.runbook_id)
    if not runbook.runbook_id.startswith(LIVE_ORDER_ONE_SHOT_EXECUTION_RUNBOOK_ID_PREFIX):
        raise LiveVerificationValidationError("runbook_id must be dry-run runbook id")
    _ensure_aware(runbook.created_at)
    for name, value in (
        ("boundary_id", runbook.boundary_id),
        ("preflight_decision_id", runbook.preflight_decision_id),
        ("snapshot_id", runbook.snapshot_id),
        ("simulation_id", runbook.simulation_id),
        ("candidate_id", runbook.candidate_id),
        ("symbol", runbook.symbol),
        ("side", runbook.side),
        ("execution_type", runbook.execution_type),
        ("summary", runbook.summary),
        ("recommended_next_step", runbook.recommended_next_step),
    ):
        _require_non_empty(name, value)
    if type(runbook.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    if runbook.runbook_status not in set(LiveOrderOneShotExecutionRunbookStatus):
        raise LiveVerificationValidationError("unsupported runbook status")
    for field_name, value in (
        ("runbook_ready", runbook.runbook_ready),
        (
            "eligible_for_future_execution_planning",
            runbook.eligible_for_future_execution_planning,
        ),
    ):
        if type(value) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")
    if runbook.allowed_for_live is not False:
        raise LiveVerificationValidationError("Step 5O never allows live execution")
    if runbook.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if runbook.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if runbook.approval_gate_issued is not False:
        raise LiveVerificationValidationError("Step 5O never issues approval gate")
    if runbook.approval_id_generated is not False:
        raise LiveVerificationValidationError("Step 5O never generates approval id")
    if runbook.approval_command_generated is not False:
        raise LiveVerificationValidationError("Step 5O never generates approval command")
    if runbook.approval_command_template_only is not True:
        raise LiveVerificationValidationError("approval command remains template-only")
    if runbook.approval_command_copyable is not False:
        raise LiveVerificationValidationError("approval command remains non-copyable")
    if runbook.final_dynamic_preflight_required is not True:
        raise LiveVerificationValidationError("final dynamic preflight remains required")
    if runbook.dry_run_only is not True:
        raise LiveVerificationValidationError("execution runbook is dry-run only")
    if runbook.post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
        raise LiveVerificationValidationError("post attempt limit must be one")
    for field_name in (
        "post_executed",
        "live_order_once_called",
        "private_api_called",
        "broker_called",
        "read_only_api_called",
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(runbook, field_name) is not False:
            raise LiveVerificationValidationError(f"{field_name} must remain false")
    if runbook.post_reconciliation_required is not True:
        raise LiveVerificationValidationError("post reconciliation remains required")
    if not runbook.phases:
        raise LiveVerificationValidationError("runbook requires phases")
    if not runbook.steps:
        raise LiveVerificationValidationError("runbook requires steps")
    if not runbook.check_results:
        raise LiveVerificationValidationError("runbook requires checks")
    if not runbook.sections:
        raise LiveVerificationValidationError("runbook requires sections")
    if (
        runbook.runbook_status
        is LiveOrderOneShotExecutionRunbookStatus.READY_FOR_ONE_SHOT_EXECUTION_RUNBOOK_REVIEW
    ):
        if (
            not runbook.runbook_ready
            or not runbook.eligible_for_future_execution_planning
        ):
            raise LiveVerificationValidationError("ready runbook must be eligible")
        if runbook.blocked_reasons:
            raise LiveVerificationValidationError("ready runbook cannot have blockers")
    else:
        if runbook.runbook_ready or runbook.eligible_for_future_execution_planning:
            raise LiveVerificationValidationError("blocked runbook cannot pass")
        if not runbook.blocked_reasons:
            raise LiveVerificationValidationError("blocked runbook requires blockers")


def _boundary_existing_reasons(
    boundary: LiveOrderOneShotBoundaryDecision,
) -> tuple[str, ...]:
    if isinstance(boundary, LiveOrderOneShotBoundaryDecision):
        return boundary.blocked_reasons
    return ()


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            if _has_text(reason) and reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _add_reason(
    reasons: list[LiveOrderOneShotExecutionRunbookBlockReason],
    reason: LiveOrderOneShotExecutionRunbookBlockReason,
) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _expect_true(
    reasons: list[LiveOrderOneShotExecutionRunbookBlockReason],
    value: object,
    false_reason: LiveOrderOneShotExecutionRunbookBlockReason,
) -> None:
    if value is not True:
        _add_reason(reasons, false_reason)


def _expect_false(
    reasons: list[LiveOrderOneShotExecutionRunbookBlockReason],
    value: object,
    true_reason: LiveOrderOneShotExecutionRunbookBlockReason,
) -> None:
    if value is not False:
        _add_reason(reasons, true_reason)


def _check(
    name: str,
    passed: bool,
    sanitized_value: object,
    expected: str,
) -> LiveOrderOneShotExecutionRunbookCheckResult:
    return LiveOrderOneShotExecutionRunbookCheckResult(
        name=name,
        passed=passed,
        reason="passed" if passed else "blocked",
        sanitized_value=_safe_value(sanitized_value),
        expected=expected,
    )


def _boundary_int(boundary: LiveOrderOneShotBoundaryDecision, field_name: str) -> int:
    value = getattr(boundary, field_name, 0)
    return value if type(value) is int else 0


def _boundary_text(
    boundary: LiveOrderOneShotBoundaryDecision,
    field_name: str,
) -> str:
    value = getattr(boundary, field_name, None)
    return value.strip() if _has_text(value) else f"missing_{field_name}"


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _enum_value(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _phase_allowed_actions_contain_forbidden(
    phases: tuple[LiveOrderOneShotExecutionRunbookPhase, ...],
) -> bool:
    forbidden = set(FORBIDDEN_PHASE_ACTIONS)
    return any(action in forbidden for phase in phases for action in phase.allowed_actions)


def _required_conditions_present(
    values: tuple[str, ...],
    required_values: tuple[str, ...],
) -> bool:
    return bool(values) and set(required_values).issubset(set(values))


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")


def _safe_value(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _section_line(boundary: LiveOrderOneShotBoundaryDecision, field_name: str) -> str:
    return f"{field_name}: {_boundary_text(boundary, field_name)}"
