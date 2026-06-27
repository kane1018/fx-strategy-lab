"""Real approval readiness checkpoint dry-run model for Step 5Q."""

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
from app.live_verification.live_order_e2e_dry_run_chain import (
    LiveOrderE2EDryRunChainReview,
    LiveOrderE2EDryRunChainStatus,
)
from app.live_verification.live_order_one_shot_boundary import (
    ONE_SHOT_POST_ATTEMPT_LIMIT,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_REAL_APPROVAL_READINESS_ID_PREFIX = "LORAR-"

DEFAULT_REAL_APPROVAL_GO_CONDITIONS = (
    "E2E dry-run chain ready",
    "operator reviewed full chain",
    "operator understands real money risk",
    "operator understands no auto-post",
    "operator understands all future execution steps are separate",
    "explicit user confirmation is required before future real approval gate step",
    "fresh preflight is required in a future separate step",
    "one-shot POST is a future separate step",
    "post reconciliation is a future separate step",
    "unknown means stop",
)

DEFAULT_REAL_APPROVAL_NO_GO_CONDITIONS = (
    "any blocked reason exists",
    "chain not ready",
    "any stage allowed_for_live=true",
    "any approval artifact generated",
    "any API/broker/live_order_once called",
    "post already executed",
    "operator acknowledgement missing",
    "result_unknown",
    "stale or unknown future market/account state",
    "any need to display/store raw response or real IDs",
)

DEFAULT_REAL_APPROVAL_STOP_CONDITIONS = (
    "user has not explicitly requested future real approval gate step",
    "any required acknowledgement missing",
    "any chain mismatch",
    "any stale preflight risk",
    "any result_unknown",
    "any secret/raw response/ID exposure risk",
    "any need for retry/loop/add/change/cancel/close",
    "any need to exceed one POST attempt",
)


class LiveOrderRealApprovalReadinessStatus(str, Enum):
    READY_FOR_REAL_APPROVAL_READINESS_REVIEW = (
        "READY_FOR_REAL_APPROVAL_READINESS_REVIEW"
    )
    BLOCKED_REAL_APPROVAL_READINESS = "BLOCKED_REAL_APPROVAL_READINESS"


class LiveOrderRealApprovalReadinessBlockReason(str, Enum):
    MISSING_E2E_CHAIN_REVIEW = "missing_e2e_chain_review"
    CHAIN_NOT_READY = "chain_not_ready"
    CHAIN_NOT_PLANNING_ELIGIBLE = "chain_not_planning_eligible"
    CHAIN_ALLOWS_LIVE = "chain_allows_live"
    CHAIN_NOT_DRY_RUN = "chain_not_dry_run"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_ID_ALREADY_GENERATED = "approval_id_already_generated"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
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
    OPERATOR_REVIEW_MISSING = "operator_review_missing"
    REAL_MONEY_RISK_NOT_ACKNOWLEDGED = "real_money_risk_not_acknowledged"
    NO_AUTO_POST_NOT_ACKNOWLEDGED = "no_auto_post_not_acknowledged"
    FUTURE_STEPS_SEPARATION_NOT_ACKNOWLEDGED = (
        "future_steps_separation_not_acknowledged"
    )
    UNKNOWN_STOP_RULE_NOT_ACKNOWLEDGED = "unknown_stop_rule_not_acknowledged"
    REAL_APPROVAL_GATE_NOT_SEPARATE_STEP = "real_approval_gate_not_separate_step"
    FRESH_PREFLIGHT_NOT_SEPARATE_STEP = "fresh_preflight_not_separate_step"
    ONE_SHOT_POST_NOT_SEPARATE_STEP = "one_shot_post_not_separate_step"
    POST_RECONCILIATION_NOT_SEPARATE_STEP = "post_reconciliation_not_separate_step"
    FINAL_REPORT_NOT_SEPARATE_STEP = "final_report_not_separate_step"


@dataclass(frozen=True)
class LiveOrderRealApprovalReadinessCheckResult:
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
class LiveOrderRealApprovalReadinessSection:
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
class LiveOrderRealApprovalReadinessCheckpoint:
    checkpoint_id: str
    created_at: datetime
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
    readiness_status: LiveOrderRealApprovalReadinessStatus
    readiness_ready: bool
    eligible_for_future_real_approval_gate_planning: bool
    allowed_for_live: bool
    requires_human_approval: bool
    explicit_user_confirmation_required: bool
    real_approval_gate_separate_step_required: bool
    fresh_preflight_separate_step_required: bool
    one_shot_post_separate_step_required: bool
    post_reconciliation_separate_step_required: bool
    final_report_separate_step_required: bool
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
    go_conditions: tuple[str, ...]
    no_go_conditions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    check_results: tuple[LiveOrderRealApprovalReadinessCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApprovalReadinessSection, ...]

    def __post_init__(self) -> None:
        _validate_checkpoint(self)


@dataclass(frozen=True)
class LiveOrderRealApprovalReadinessBuildResult:
    checkpoint: LiveOrderRealApprovalReadinessCheckpoint
    checkpoint_id: str
    readiness_status: LiveOrderRealApprovalReadinessStatus
    readiness_ready: bool
    eligible_for_future_real_approval_gate_planning: bool
    allowed_for_live: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.checkpoint.checkpoint_id != self.checkpoint_id:
            raise LiveVerificationValidationError("checkpoint_id mismatch")
        if self.checkpoint.readiness_status is not self.readiness_status:
            raise LiveVerificationValidationError("readiness_status mismatch")
        if self.checkpoint.readiness_ready is not self.readiness_ready:
            raise LiveVerificationValidationError("readiness_ready mismatch")
        if (
            self.checkpoint.eligible_for_future_real_approval_gate_planning
            is not self.eligible_for_future_real_approval_gate_planning
        ):
            raise LiveVerificationValidationError("planning eligibility mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("Step 5Q never allows live execution")
        if self.checkpoint.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.checkpoint.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_approval_readiness_checkpoint(
    *,
    e2e_chain_review: LiveOrderE2EDryRunChainReview | None,
    created_at: datetime | None = None,
    operator_reviewed_chain: bool = False,
    operator_understands_real_money_risk: bool = False,
    operator_understands_no_auto_post: bool = False,
    operator_understands_future_steps_are_separate: bool = False,
    operator_understands_unknown_means_stop: bool = False,
    real_approval_gate_separate_step_required: bool = True,
    fresh_preflight_separate_step_required: bool = True,
    one_shot_post_separate_step_required: bool = True,
    post_reconciliation_separate_step_required: bool = True,
    final_report_separate_step_required: bool = True,
) -> LiveOrderRealApprovalReadinessBuildResult:
    """Build a dry-run checkpoint before any future real approval gate step."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    blocked_reasons = _readiness_blocked_reasons(
        e2e_chain_review=e2e_chain_review,
        operator_reviewed_chain=operator_reviewed_chain,
        operator_understands_real_money_risk=operator_understands_real_money_risk,
        operator_understands_no_auto_post=operator_understands_no_auto_post,
        operator_understands_future_steps_are_separate=(
            operator_understands_future_steps_are_separate
        ),
        operator_understands_unknown_means_stop=operator_understands_unknown_means_stop,
        real_approval_gate_separate_step_required=(
            real_approval_gate_separate_step_required
        ),
        fresh_preflight_separate_step_required=fresh_preflight_separate_step_required,
        one_shot_post_separate_step_required=one_shot_post_separate_step_required,
        post_reconciliation_separate_step_required=(
            post_reconciliation_separate_step_required
        ),
        final_report_separate_step_required=final_report_separate_step_required,
    )
    check_results = _build_check_results(
        e2e_chain_review=e2e_chain_review,
        operator_reviewed_chain=operator_reviewed_chain,
        operator_understands_real_money_risk=operator_understands_real_money_risk,
        operator_understands_no_auto_post=operator_understands_no_auto_post,
        operator_understands_future_steps_are_separate=(
            operator_understands_future_steps_are_separate
        ),
        operator_understands_unknown_means_stop=operator_understands_unknown_means_stop,
        real_approval_gate_separate_step_required=(
            real_approval_gate_separate_step_required
        ),
        fresh_preflight_separate_step_required=fresh_preflight_separate_step_required,
        one_shot_post_separate_step_required=one_shot_post_separate_step_required,
        post_reconciliation_separate_step_required=(
            post_reconciliation_separate_step_required
        ),
        final_report_separate_step_required=final_report_separate_step_required,
    )
    if blocked_reasons:
        status = LiveOrderRealApprovalReadinessStatus.BLOCKED_REAL_APPROVAL_READINESS
        readiness_ready = False
        eligible = False
        recommended_next_step = (
            "fix_e2e_chain_blockers_no_post"
            if _chain_is_blocked(e2e_chain_review)
            else "fix_real_approval_readiness_blockers_no_post"
        )
        summary = "blocked real approval readiness checkpoint; live post remains disallowed"
    else:
        status = (
            LiveOrderRealApprovalReadinessStatus.READY_FOR_REAL_APPROVAL_READINESS_REVIEW
        )
        readiness_ready = True
        eligible = True
        recommended_next_step = "stop_and_ask_user_before_future_real_approval_gate_step"
        summary = "ready for real approval readiness review only; live post remains disallowed"

    checkpoint_id = make_live_order_real_approval_readiness_id(
        chain_id=_text_from(e2e_chain_review, "chain_id"),
        runbook_id=_text_from(e2e_chain_review, "runbook_id"),
        created_at=created,
        readiness_status=status,
        blocked_reasons=blocked_reasons,
    )
    checkpoint = LiveOrderRealApprovalReadinessCheckpoint(
        checkpoint_id=checkpoint_id,
        created_at=created,
        chain_id=_text_from(e2e_chain_review, "chain_id"),
        runbook_id=_text_from(e2e_chain_review, "runbook_id"),
        boundary_id=_text_from(e2e_chain_review, "boundary_id"),
        preflight_decision_id=_text_from(e2e_chain_review, "preflight_decision_id"),
        simulation_id=_text_from(e2e_chain_review, "simulation_id"),
        preview_id=_text_from(e2e_chain_review, "preview_id"),
        design_id=_text_from(e2e_chain_review, "design_id"),
        handoff_id=_text_from(e2e_chain_review, "handoff_id"),
        operator_review_id=_text_from(e2e_chain_review, "operator_review_id"),
        bundle_id=_text_from(e2e_chain_review, "bundle_id"),
        review_id=_text_from(e2e_chain_review, "review_id"),
        candidate_id=_text_from(e2e_chain_review, "candidate_id"),
        risk_decision_id=_text_from(e2e_chain_review, "risk_decision_id"),
        trace_id=_text_from(e2e_chain_review, "trace_id"),
        session_policy_decision_id=_text_from(
            e2e_chain_review,
            "session_policy_decision_id",
        ),
        source_signal_id=_text_from(e2e_chain_review, "source_signal_id"),
        source_type=_text_from(e2e_chain_review, "source_type"),
        strategy_name=_text_from(e2e_chain_review, "strategy_name"),
        symbol=_text_from(e2e_chain_review, "symbol"),
        side=_text_from(e2e_chain_review, "side"),
        size=_int_from(e2e_chain_review, "size"),
        execution_type=_text_from(e2e_chain_review, "execution_type"),
        readiness_status=status,
        readiness_ready=readiness_ready,
        eligible_for_future_real_approval_gate_planning=eligible,
        allowed_for_live=False,
        requires_human_approval=True,
        explicit_user_confirmation_required=True,
        real_approval_gate_separate_step_required=True,
        fresh_preflight_separate_step_required=True,
        one_shot_post_separate_step_required=True,
        post_reconciliation_separate_step_required=True,
        final_report_separate_step_required=True,
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
        go_conditions=DEFAULT_REAL_APPROVAL_GO_CONDITIONS,
        no_go_conditions=DEFAULT_REAL_APPROVAL_NO_GO_CONDITIONS,
        stop_conditions=DEFAULT_REAL_APPROVAL_STOP_CONDITIONS,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
        ),
    )
    return LiveOrderRealApprovalReadinessBuildResult(
        checkpoint=checkpoint,
        checkpoint_id=checkpoint.checkpoint_id,
        readiness_status=checkpoint.readiness_status,
        readiness_ready=checkpoint.readiness_ready,
        eligible_for_future_real_approval_gate_planning=(
            checkpoint.eligible_for_future_real_approval_gate_planning
        ),
        allowed_for_live=False,
        blocked_reasons=checkpoint.blocked_reasons,
        recommended_next_step=checkpoint.recommended_next_step,
    )


def render_live_order_real_approval_readiness_markdown(
    checkpoint: LiveOrderRealApprovalReadinessCheckpoint,
) -> str:
    """Render a sanitized real approval readiness checkpoint."""
    blocked_text = ", ".join(checkpoint.blocked_reasons) or "none"
    go_lines = "\n".join(f"- {condition}" for condition in checkpoint.go_conditions)
    no_go_lines = "\n".join(f"- {condition}" for condition in checkpoint.no_go_conditions)
    stop_lines = "\n".join(f"- {condition}" for condition in checkpoint.stop_conditions)
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in checkpoint.check_results
    )
    return "\n".join(
        (
            "# Step 5Q Real Approval Readiness Checkpoint",
            "",
            "This real approval readiness checkpoint is dry-run only.",
            "This checkpoint does not call read-only API.",
            "This checkpoint does not call Private API.",
            "This checkpoint does not call live_order_once.",
            "This checkpoint does not execute HTTP POST.",
            "This checkpoint does not issue a real approval gate.",
            "This checkpoint does not generate a real approval command.",
            "This checkpoint does not authorize live POST.",
            "allowed_for_live=false.",
            "",
            f"checkpoint_id: {checkpoint.checkpoint_id}",
            f"chain_id: {checkpoint.chain_id}",
            f"runbook_id: {checkpoint.runbook_id}",
            f"boundary_id: {checkpoint.boundary_id}",
            f"preflight_decision_id: {checkpoint.preflight_decision_id}",
            f"simulation_id: {checkpoint.simulation_id}",
            f"preview_id: {checkpoint.preview_id}",
            f"design_id: {checkpoint.design_id}",
            f"handoff_id: {checkpoint.handoff_id}",
            f"operator_review_id: {checkpoint.operator_review_id}",
            f"bundle_id: {checkpoint.bundle_id}",
            f"review_id: {checkpoint.review_id}",
            f"candidate_id: {checkpoint.candidate_id}",
            f"risk_decision_id: {checkpoint.risk_decision_id}",
            f"trace_id: {checkpoint.trace_id}",
            f"session_policy_decision_id: {checkpoint.session_policy_decision_id}",
            f"source_signal_id: {checkpoint.source_signal_id}",
            f"source_type: {checkpoint.source_type}",
            f"strategy_name: {checkpoint.strategy_name}",
            f"symbol: {checkpoint.symbol}",
            f"side: {checkpoint.side}",
            f"size: {checkpoint.size}",
            f"executionType: {checkpoint.execution_type}",
            f"readiness_status: {checkpoint.readiness_status.value}",
            f"readiness_ready: {checkpoint.readiness_ready}",
            "eligible_for_future_real_approval_gate_planning: "
            f"{checkpoint.eligible_for_future_real_approval_gate_planning}",
            f"allowed_for_live: {checkpoint.allowed_for_live}",
            "explicit_user_confirmation_required: "
            f"{checkpoint.explicit_user_confirmation_required}",
            "real_approval_gate_separate_step_required: "
            f"{checkpoint.real_approval_gate_separate_step_required}",
            "fresh_preflight_separate_step_required: "
            f"{checkpoint.fresh_preflight_separate_step_required}",
            "one_shot_post_separate_step_required: "
            f"{checkpoint.one_shot_post_separate_step_required}",
            "post_reconciliation_separate_step_required: "
            f"{checkpoint.post_reconciliation_separate_step_required}",
            "final_report_separate_step_required: "
            f"{checkpoint.final_report_separate_step_required}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {checkpoint.recommended_next_step}",
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
            "## Check Results",
            check_lines,
        ),
    )


def make_live_order_real_approval_readiness_id(
    *,
    chain_id: str,
    runbook_id: str,
    created_at: datetime,
    readiness_status: LiveOrderRealApprovalReadinessStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "chain_id": chain_id,
        "runbook_id": runbook_id,
        "created_at": _ensure_aware(created_at).isoformat(),
        "readiness_status": readiness_status.value,
        "blocked_reasons": list(blocked_reasons),
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_READINESS_ID_PREFIX}{digest}"


def _readiness_blocked_reasons(
    *,
    e2e_chain_review: LiveOrderE2EDryRunChainReview | None,
    operator_reviewed_chain: bool,
    operator_understands_real_money_risk: bool,
    operator_understands_no_auto_post: bool,
    operator_understands_future_steps_are_separate: bool,
    operator_understands_unknown_means_stop: bool,
    real_approval_gate_separate_step_required: bool,
    fresh_preflight_separate_step_required: bool,
    one_shot_post_separate_step_required: bool,
    post_reconciliation_separate_step_required: bool,
    final_report_separate_step_required: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if e2e_chain_review is None:
        _add_reason(
            reasons,
            LiveOrderRealApprovalReadinessBlockReason.MISSING_E2E_CHAIN_REVIEW,
        )
    else:
        _add_chain_reasons(reasons, e2e_chain_review)
        for reason in e2e_chain_review.blocked_reasons:
            _add_external_reason(reasons, reason)
    for flag, reason in (
        (
            operator_reviewed_chain,
            LiveOrderRealApprovalReadinessBlockReason.OPERATOR_REVIEW_MISSING,
        ),
        (
            operator_understands_real_money_risk,
            LiveOrderRealApprovalReadinessBlockReason.REAL_MONEY_RISK_NOT_ACKNOWLEDGED,
        ),
        (
            operator_understands_no_auto_post,
            LiveOrderRealApprovalReadinessBlockReason.NO_AUTO_POST_NOT_ACKNOWLEDGED,
        ),
        (
            operator_understands_future_steps_are_separate,
            LiveOrderRealApprovalReadinessBlockReason.FUTURE_STEPS_SEPARATION_NOT_ACKNOWLEDGED,
        ),
        (
            operator_understands_unknown_means_stop,
            LiveOrderRealApprovalReadinessBlockReason.UNKNOWN_STOP_RULE_NOT_ACKNOWLEDGED,
        ),
        (
            real_approval_gate_separate_step_required,
            LiveOrderRealApprovalReadinessBlockReason.REAL_APPROVAL_GATE_NOT_SEPARATE_STEP,
        ),
        (
            fresh_preflight_separate_step_required,
            LiveOrderRealApprovalReadinessBlockReason.FRESH_PREFLIGHT_NOT_SEPARATE_STEP,
        ),
        (
            one_shot_post_separate_step_required,
            LiveOrderRealApprovalReadinessBlockReason.ONE_SHOT_POST_NOT_SEPARATE_STEP,
        ),
        (
            post_reconciliation_separate_step_required,
            LiveOrderRealApprovalReadinessBlockReason.POST_RECONCILIATION_NOT_SEPARATE_STEP,
        ),
        (
            final_report_separate_step_required,
            LiveOrderRealApprovalReadinessBlockReason.FINAL_REPORT_NOT_SEPARATE_STEP,
        ),
    ):
        if flag is not True:
            _add_reason(reasons, reason)
    return tuple(reasons)


def _add_chain_reasons(
    reasons: list[str],
    chain: LiveOrderE2EDryRunChainReview,
) -> None:
    if (
        chain.chain_status
        is not LiveOrderE2EDryRunChainStatus.READY_FOR_E2E_DRY_RUN_CHAIN_REVIEW
    ):
        _add_reason(reasons, LiveOrderRealApprovalReadinessBlockReason.CHAIN_NOT_READY)
    if chain.chain_ready is not True:
        _add_reason(reasons, LiveOrderRealApprovalReadinessBlockReason.CHAIN_NOT_READY)
    if chain.eligible_for_future_real_approval_planning is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalReadinessBlockReason.CHAIN_NOT_PLANNING_ELIGIBLE,
        )
    for field_name, expected, reason in (
        (
            "allowed_for_live",
            False,
            LiveOrderRealApprovalReadinessBlockReason.CHAIN_ALLOWS_LIVE,
        ),
        (
            "dry_run_only",
            True,
            LiveOrderRealApprovalReadinessBlockReason.CHAIN_NOT_DRY_RUN,
        ),
        (
            "approval_gate_issued",
            False,
            LiveOrderRealApprovalReadinessBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        ),
        (
            "approval_id_generated",
            False,
            LiveOrderRealApprovalReadinessBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            "approval_command_generated",
            False,
            LiveOrderRealApprovalReadinessBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            "approval_command_copyable",
            False,
            LiveOrderRealApprovalReadinessBlockReason.APPROVAL_COMMAND_COPYABLE,
        ),
        (
            "post_executed",
            False,
            LiveOrderRealApprovalReadinessBlockReason.POST_ALREADY_EXECUTED,
        ),
        (
            "live_order_once_called",
            False,
            LiveOrderRealApprovalReadinessBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        ),
        (
            "private_api_called",
            False,
            LiveOrderRealApprovalReadinessBlockReason.PRIVATE_API_ALREADY_CALLED,
        ),
        (
            "broker_called",
            False,
            LiveOrderRealApprovalReadinessBlockReason.BROKER_ALREADY_CALLED,
        ),
        (
            "read_only_api_called",
            False,
            LiveOrderRealApprovalReadinessBlockReason.READ_ONLY_API_ALREADY_CALLED,
        ),
        (
            "post_reconciliation_required",
            True,
            LiveOrderRealApprovalReadinessBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        ),
    ):
        if getattr(chain, field_name) is not expected:
            _add_reason(reasons, reason)
    if chain.post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
        _add_reason(
            reasons,
            LiveOrderRealApprovalReadinessBlockReason.INVALID_POST_ATTEMPT_LIMIT,
        )
    for field_name, reason in (
        ("retry_allowed", LiveOrderRealApprovalReadinessBlockReason.RETRY_ALLOWED),
        ("loop_allowed", LiveOrderRealApprovalReadinessBlockReason.LOOP_ALLOWED),
        ("add_order_allowed", LiveOrderRealApprovalReadinessBlockReason.ADD_ORDER_ALLOWED),
        (
            "change_order_allowed",
            LiveOrderRealApprovalReadinessBlockReason.CHANGE_ORDER_ALLOWED,
        ),
        (
            "cancel_order_allowed",
            LiveOrderRealApprovalReadinessBlockReason.CANCEL_ORDER_ALLOWED,
        ),
        ("close_order_allowed", LiveOrderRealApprovalReadinessBlockReason.CLOSE_ORDER_ALLOWED),
    ):
        if getattr(chain, field_name) is not False:
            _add_reason(reasons, reason)
    if chain.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderRealApprovalReadinessBlockReason.UNSUPPORTED_SYMBOL)
    if chain.side not in (LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value):
        _add_reason(reasons, LiveOrderRealApprovalReadinessBlockReason.UNSUPPORTED_SIDE)
    if chain.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderRealApprovalReadinessBlockReason.UNSUPPORTED_SIZE)
    if chain.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(
            reasons,
            LiveOrderRealApprovalReadinessBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        )


def _build_check_results(
    *,
    e2e_chain_review: LiveOrderE2EDryRunChainReview | None,
    operator_reviewed_chain: bool,
    operator_understands_real_money_risk: bool,
    operator_understands_no_auto_post: bool,
    operator_understands_future_steps_are_separate: bool,
    operator_understands_unknown_means_stop: bool,
    real_approval_gate_separate_step_required: bool,
    fresh_preflight_separate_step_required: bool,
    one_shot_post_separate_step_required: bool,
    post_reconciliation_separate_step_required: bool,
    final_report_separate_step_required: bool,
) -> tuple[LiveOrderRealApprovalReadinessCheckResult, ...]:
    chain_ready = (
        e2e_chain_review is not None
        and e2e_chain_review.chain_status
        is LiveOrderE2EDryRunChainStatus.READY_FOR_E2E_DRY_RUN_CHAIN_REVIEW
        and e2e_chain_review.chain_ready is True
        and e2e_chain_review.eligible_for_future_real_approval_planning is True
    )
    allowed_false = (
        e2e_chain_review is not None and e2e_chain_review.allowed_for_live is False
    )
    approval_clear = (
        e2e_chain_review is not None
        and e2e_chain_review.approval_gate_issued is False
        and e2e_chain_review.approval_id_generated is False
        and e2e_chain_review.approval_command_generated is False
        and e2e_chain_review.approval_command_copyable is False
    )
    post_not_executed = (
        e2e_chain_review is not None and e2e_chain_review.post_executed is False
    )
    no_api_calls = (
        e2e_chain_review is not None
        and e2e_chain_review.live_order_once_called is False
        and e2e_chain_review.private_api_called is False
        and e2e_chain_review.broker_called is False
        and e2e_chain_review.read_only_api_called is False
    )
    one_shot_ok = (
        e2e_chain_review is not None
        and e2e_chain_review.post_attempt_limit == ONE_SHOT_POST_ATTEMPT_LIMIT
        and e2e_chain_review.retry_allowed is False
        and e2e_chain_review.loop_allowed is False
        and e2e_chain_review.add_order_allowed is False
        and e2e_chain_review.change_order_allowed is False
        and e2e_chain_review.cancel_order_allowed is False
        and e2e_chain_review.close_order_allowed is False
        and e2e_chain_review.post_reconciliation_required is True
    )
    future_steps_separated = all(
        (
            real_approval_gate_separate_step_required,
            fresh_preflight_separate_step_required,
            one_shot_post_separate_step_required,
            post_reconciliation_separate_step_required,
            final_report_separate_step_required,
        ),
    )
    operator_acknowledgements = all(
        (
            operator_reviewed_chain,
            operator_understands_real_money_risk,
            operator_understands_no_auto_post,
            operator_understands_future_steps_are_separate,
            operator_understands_unknown_means_stop,
        ),
    )
    return (
        _check("e2e_chain_ready", chain_ready, _bool_text(chain_ready), "true"),
        _check("allowed_for_live_false", allowed_false, _bool_text(allowed_false), "true"),
        _check(
            "approval_artifacts_not_generated",
            approval_clear,
            _bool_text(approval_clear),
            "true",
        ),
        _check("post_not_executed", post_not_executed, _bool_text(post_not_executed), "true"),
        _check(
            "no_api_broker_live_order_once_called",
            no_api_calls,
            _bool_text(no_api_calls),
            "true",
        ),
        _check(
            "one_shot_constraints_preserved",
            one_shot_ok,
            _bool_text(one_shot_ok),
            "post_attempt_limit=1 and no retry/loop/order mutation",
        ),
        _check(
            "future_steps_separated",
            future_steps_separated,
            _bool_text(future_steps_separated),
            "true",
        ),
        _check(
            "operator_acknowledgements_present",
            operator_acknowledgements,
            _bool_text(operator_acknowledgements),
            "true",
        ),
        _check(
            "explicit_user_confirmation_required",
            True,
            "true",
            "true",
        ),
        _check(
            "unknown_means_stop",
            operator_understands_unknown_means_stop,
            _bool_text(operator_understands_unknown_means_stop),
            "true",
        ),
    )


def _build_sections(
    *,
    check_results: tuple[LiveOrderRealApprovalReadinessCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
) -> tuple[LiveOrderRealApprovalReadinessSection, ...]:
    failed_checks = tuple(check.name for check in check_results if not check.passed)
    return (
        LiveOrderRealApprovalReadinessSection(
            section_id="go_conditions",
            title="Go Conditions",
            lines=DEFAULT_REAL_APPROVAL_GO_CONDITIONS,
        ),
        LiveOrderRealApprovalReadinessSection(
            section_id="no_go_conditions",
            title="No-go Conditions",
            lines=DEFAULT_REAL_APPROVAL_NO_GO_CONDITIONS,
        ),
        LiveOrderRealApprovalReadinessSection(
            section_id="stop_conditions",
            title="Stop Conditions",
            lines=DEFAULT_REAL_APPROVAL_STOP_CONDITIONS,
        ),
        LiveOrderRealApprovalReadinessSection(
            section_id="checks",
            title="Readiness Checks",
            lines=(
                f"failed_checks: {', '.join(failed_checks) if failed_checks else 'none'}",
                f"blocked_reasons: {', '.join(blocked_reasons) if blocked_reasons else 'none'}",
            ),
        ),
        LiveOrderRealApprovalReadinessSection(
            section_id="next_step",
            title="Recommended Next Step",
            lines=(recommended_next_step,),
        ),
    )


def _validate_checkpoint(checkpoint: LiveOrderRealApprovalReadinessCheckpoint) -> None:
    _require_non_empty("checkpoint_id", checkpoint.checkpoint_id)
    if not isinstance(checkpoint.created_at, datetime):
        raise LiveVerificationValidationError("created_at must be datetime")
    for field_name in (
        "chain_id",
        "runbook_id",
        "boundary_id",
        "preflight_decision_id",
        "simulation_id",
        "preview_id",
        "design_id",
        "handoff_id",
        "operator_review_id",
        "bundle_id",
        "review_id",
        "candidate_id",
        "risk_decision_id",
        "trace_id",
        "session_policy_decision_id",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "symbol",
        "side",
        "execution_type",
        "summary",
        "recommended_next_step",
    ):
        _require_non_empty(field_name, getattr(checkpoint, field_name))
    if type(checkpoint.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    for field_name, expected in (
        ("allowed_for_live", False),
        ("requires_human_approval", True),
        ("explicit_user_confirmation_required", True),
        ("real_approval_gate_separate_step_required", True),
        ("fresh_preflight_separate_step_required", True),
        ("one_shot_post_separate_step_required", True),
        ("post_reconciliation_separate_step_required", True),
        ("final_report_separate_step_required", True),
        ("approval_gate_required", True),
        ("approval_gate_issued", False),
        ("approval_id_generated", False),
        ("approval_command_generated", False),
        ("approval_command_template_only", True),
        ("approval_command_copyable", False),
        ("final_dynamic_preflight_required", True),
        ("dry_run_only", True),
        ("post_executed", False),
        ("live_order_once_called", False),
        ("private_api_called", False),
        ("broker_called", False),
        ("read_only_api_called", False),
        ("retry_allowed", False),
        ("loop_allowed", False),
        ("add_order_allowed", False),
        ("change_order_allowed", False),
        ("cancel_order_allowed", False),
        ("close_order_allowed", False),
        ("post_reconciliation_required", True),
    ):
        if getattr(checkpoint, field_name) is not expected:
            raise LiveVerificationValidationError(f"{field_name} safety default mismatch")
    if checkpoint.post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if not checkpoint.go_conditions:
        raise LiveVerificationValidationError("go_conditions are required")
    if not checkpoint.no_go_conditions:
        raise LiveVerificationValidationError("no_go_conditions are required")
    if not checkpoint.stop_conditions:
        raise LiveVerificationValidationError("stop_conditions are required")
    if not checkpoint.check_results:
        raise LiveVerificationValidationError("check_results are required")
    if not checkpoint.sections:
        raise LiveVerificationValidationError("sections are required")
    if (
        checkpoint.readiness_status
        is LiveOrderRealApprovalReadinessStatus.READY_FOR_REAL_APPROVAL_READINESS_REVIEW
    ):
        if not checkpoint.readiness_ready:
            raise LiveVerificationValidationError("ready checkpoint must be ready")
        if checkpoint.blocked_reasons:
            raise LiveVerificationValidationError("ready checkpoint cannot have blockers")
    if (
        checkpoint.readiness_status
        is LiveOrderRealApprovalReadinessStatus.BLOCKED_REAL_APPROVAL_READINESS
    ):
        if checkpoint.readiness_ready:
            raise LiveVerificationValidationError("blocked checkpoint cannot be ready")
        if checkpoint.eligible_for_future_real_approval_gate_planning:
            raise LiveVerificationValidationError("blocked checkpoint cannot be eligible")


def _chain_is_blocked(e2e_chain_review: LiveOrderE2EDryRunChainReview | None) -> bool:
    return (
        e2e_chain_review is not None
        and e2e_chain_review.chain_status
        is LiveOrderE2EDryRunChainStatus.BLOCKED_E2E_DRY_RUN_CHAIN
    )


def _check(
    name: str,
    passed: bool,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealApprovalReadinessCheckResult:
    return LiveOrderRealApprovalReadinessCheckResult(
        name=name,
        passed=passed,
        reason="passed" if passed else "blocked",
        sanitized_value=sanitized_value,
        expected=expected,
    )


def _add_reason(
    reasons: list[str],
    reason: LiveOrderRealApprovalReadinessBlockReason,
) -> None:
    _add_external_reason(reasons, reason.value)


def _add_external_reason(reasons: list[str], reason: str) -> None:
    if reason and reason not in reasons:
        reasons.append(reason)


def _text_from(obj: object | None, field_name: str) -> str:
    if obj is None:
        return f"missing_{field_name}"
    value = getattr(obj, field_name, None)
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, str) and value:
        return value
    return f"missing_{field_name}"


def _int_from(obj: object | None, field_name: str) -> int:
    if obj is None:
        return 0
    value = getattr(obj, field_name, 0)
    return value if type(value) is int else 0


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _require_non_empty(label: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{label} is required")


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
