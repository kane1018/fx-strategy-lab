"""End-to-end dry-run chain review model for Step 5P."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_approval_gate_design import (
    LiveOrderApprovalGateDesign,
)
from app.live_verification.live_order_approval_gate_preview import (
    LiveOrderApprovalGatePreview,
)
from app.live_verification.live_order_approval_handoff import (
    LiveOrderApprovalHandoffPackage,
)
from app.live_verification.live_order_approval_validation_simulator import (
    LiveOrderApprovalValidationSimulation,
)
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidate,
    LiveOrderCandidateSide,
)
from app.live_verification.live_order_candidate_review import (
    LiveOrderCandidateReviewReport,
)
from app.live_verification.live_order_candidate_risk_gate import (
    LiveOrderCandidateRiskDecision,
)
from app.live_verification.live_order_candidate_trace import (
    LiveOrderCandidateTraceRecord,
)
from app.live_verification.live_order_execution_runbook import (
    LiveOrderOneShotExecutionRunbook,
)
from app.live_verification.live_order_final_dynamic_preflight import (
    LiveOrderFinalDynamicPreflightDecision,
)
from app.live_verification.live_order_one_shot_boundary import (
    ONE_SHOT_POST_ATTEMPT_LIMIT,
    LiveOrderOneShotBoundaryDecision,
)
from app.live_verification.live_order_operator_review import (
    LiveOrderOperatorReviewProcedure,
)
from app.live_verification.live_order_review_session_bundle import (
    ReviewGatedSessionBundle,
)
from app.live_verification.live_order_session_policy import (
    ReviewGatedSessionPolicyDecision,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_E2E_DRY_RUN_CHAIN_ID_PREFIX = "LOE2E-"

REQUIRED_E2E_DRY_RUN_CHAIN_STAGE_NAMES = (
    "candidate_dry_run",
    "risk_gate",
    "trace_record",
    "review_report",
    "session_policy",
    "session_bundle",
    "operator_review",
    "approval_handoff",
    "approval_gate_design",
    "approval_gate_preview",
    "approval_validation_simulation",
    "final_dynamic_preflight",
    "one_shot_boundary",
    "execution_runbook",
)


class LiveOrderE2EDryRunChainStatus(str, Enum):
    READY_FOR_E2E_DRY_RUN_CHAIN_REVIEW = "READY_FOR_E2E_DRY_RUN_CHAIN_REVIEW"
    BLOCKED_E2E_DRY_RUN_CHAIN = "BLOCKED_E2E_DRY_RUN_CHAIN"


class LiveOrderE2EDryRunChainBlockReason(str, Enum):
    MISSING_REQUIRED_STAGE = "missing_required_stage"
    STAGE_NOT_READY = "stage_not_ready"
    STAGE_ID_MISMATCH = "stage_id_mismatch"
    CANDIDATE_ID_MISMATCH = "candidate_id_mismatch"
    REVIEW_ID_MISMATCH = "review_id_mismatch"
    TRACE_ID_MISMATCH = "trace_id_mismatch"
    RISK_DECISION_ID_MISMATCH = "risk_decision_id_mismatch"
    SOURCE_SIGNAL_ID_MISMATCH = "source_signal_id_mismatch"
    SYMBOL_MISMATCH = "symbol_mismatch"
    SIDE_MISMATCH = "side_mismatch"
    SIZE_MISMATCH = "size_mismatch"
    EXECUTION_TYPE_MISMATCH = "execution_type_mismatch"
    STAGE_ALLOWS_LIVE = "stage_allows_live"
    STAGE_NOT_DRY_RUN = "stage_not_dry_run"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_ID_ALREADY_GENERATED = "approval_id_already_generated"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
    APPROVAL_COMMAND_COPYABLE = "approval_command_copyable"
    POST_ALREADY_EXECUTED = "post_already_executed"
    LIVE_ORDER_ONCE_ALREADY_CALLED = "live_order_once_already_called"
    PRIVATE_API_ALREADY_CALLED = "private_api_already_called"
    BROKER_ALREADY_CALLED = "broker_already_called"
    READ_ONLY_API_ALREADY_CALLED = "read_only_api_already_called"
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


@dataclass(frozen=True)
class LiveOrderE2EDryRunChainStage:
    name: str
    stage_id: str
    status: str
    ready: bool
    allowed_for_live: bool
    dry_run_only: bool
    summary: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("stage name", self.name)
        _require_non_empty("stage_id", self.stage_id)
        _require_non_empty("stage status", self.status)
        if type(self.ready) is not bool:
            raise LiveVerificationValidationError("stage ready must be bool")
        if type(self.allowed_for_live) is not bool:
            raise LiveVerificationValidationError("stage allowed_for_live must be bool")
        if type(self.dry_run_only) is not bool:
            raise LiveVerificationValidationError("stage dry_run_only must be bool")
        _require_non_empty("stage summary", self.summary)
        for reason in self.blocked_reasons:
            _require_non_empty("stage blocked reason", reason)


@dataclass(frozen=True)
class LiveOrderE2EDryRunChainCheckResult:
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
class LiveOrderE2EDryRunChainSection:
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
class LiveOrderE2EDryRunChainReview:
    chain_id: str
    created_at: datetime
    candidate_id: str
    risk_decision_id: str
    trace_id: str
    review_id: str
    session_policy_decision_id: str
    bundle_id: str
    operator_review_id: str
    handoff_id: str
    design_id: str
    preview_id: str
    simulation_id: str
    preflight_decision_id: str
    boundary_id: str
    runbook_id: str
    source_signal_id: str
    source_type: str
    strategy_name: str
    symbol: str
    side: str
    size: int
    execution_type: str
    chain_status: LiveOrderE2EDryRunChainStatus
    chain_ready: bool
    eligible_for_future_real_approval_planning: bool
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
    stages: tuple[LiveOrderE2EDryRunChainStage, ...]
    check_results: tuple[LiveOrderE2EDryRunChainCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderE2EDryRunChainSection, ...]

    def __post_init__(self) -> None:
        _validate_chain_review(self)


@dataclass(frozen=True)
class LiveOrderE2EDryRunChainBuildResult:
    chain_review: LiveOrderE2EDryRunChainReview
    chain_id: str
    chain_status: LiveOrderE2EDryRunChainStatus
    blocked_reasons: tuple[str, ...]
    chain_ready: bool
    eligible_for_future_real_approval_planning: bool
    allowed_for_live: bool
    post_attempt_limit: int
    post_executed: bool
    live_order_once_called: bool
    private_api_called: bool
    broker_called: bool
    read_only_api_called: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.chain_review.chain_id != self.chain_id:
            raise LiveVerificationValidationError("chain_id mismatch")
        if self.chain_review.chain_status is not self.chain_status:
            raise LiveVerificationValidationError("chain_status mismatch")
        if self.chain_review.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.chain_review.chain_ready is not self.chain_ready:
            raise LiveVerificationValidationError("chain_ready mismatch")
        if (
            self.chain_review.eligible_for_future_real_approval_planning
            is not self.eligible_for_future_real_approval_planning
        ):
            raise LiveVerificationValidationError("planning eligibility mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("Step 5P never allows live execution")
        if self.post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
            raise LiveVerificationValidationError("post attempt limit mismatch")
        if self.post_executed is not False:
            raise LiveVerificationValidationError("Step 5P never executes POST")
        if self.live_order_once_called is not False:
            raise LiveVerificationValidationError("Step 5P never calls live_order_once")
        if self.private_api_called is not False:
            raise LiveVerificationValidationError("Step 5P never calls Private API")
        if self.broker_called is not False:
            raise LiveVerificationValidationError("Step 5P never calls broker")
        if self.read_only_api_called is not False:
            raise LiveVerificationValidationError("Step 5P never calls read-only API")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def build_live_order_e2e_dry_run_chain_review(
    *,
    candidate: LiveOrderCandidate | None,
    risk_decision: LiveOrderCandidateRiskDecision | None,
    trace_record: LiveOrderCandidateTraceRecord | None,
    review_report: LiveOrderCandidateReviewReport | None,
    session_policy_decision: ReviewGatedSessionPolicyDecision | None,
    session_bundle: ReviewGatedSessionBundle | None,
    operator_review: LiveOrderOperatorReviewProcedure | None,
    approval_handoff: LiveOrderApprovalHandoffPackage | None,
    approval_gate_design: LiveOrderApprovalGateDesign | None,
    approval_gate_preview: LiveOrderApprovalGatePreview | None,
    approval_validation_simulation: LiveOrderApprovalValidationSimulation | None,
    final_dynamic_preflight_decision: LiveOrderFinalDynamicPreflightDecision | None,
    one_shot_boundary_decision: LiveOrderOneShotBoundaryDecision | None,
    execution_runbook: LiveOrderOneShotExecutionRunbook | None,
    created_at: datetime | None = None,
) -> LiveOrderE2EDryRunChainBuildResult:
    """Review the Step 5B-5O dry-run chain without API calls or live execution."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    stage_inputs = _stage_inputs(
        candidate=candidate,
        risk_decision=risk_decision,
        trace_record=trace_record,
        review_report=review_report,
        session_policy_decision=session_policy_decision,
        session_bundle=session_bundle,
        operator_review=operator_review,
        approval_handoff=approval_handoff,
        approval_gate_design=approval_gate_design,
        approval_gate_preview=approval_gate_preview,
        approval_validation_simulation=approval_validation_simulation,
        final_dynamic_preflight_decision=final_dynamic_preflight_decision,
        one_shot_boundary_decision=one_shot_boundary_decision,
        execution_runbook=execution_runbook,
    )
    stages = tuple(_build_stage(stage_input) for stage_input in stage_inputs)
    objects = tuple(stage_input.obj for stage_input in stage_inputs if stage_input.obj is not None)
    blocked_reasons = _chain_blocked_reasons(stage_inputs=stage_inputs, stages=stages)
    check_results = _build_check_results(stage_inputs=stage_inputs, stages=stages)

    if blocked_reasons:
        status = LiveOrderE2EDryRunChainStatus.BLOCKED_E2E_DRY_RUN_CHAIN
        ready = False
        eligible = False
        recommended_next_step = "fix_e2e_dry_run_chain_blockers_no_post"
        summary = "blocked E2E dry-run chain review; live post remains disallowed"
    else:
        status = LiveOrderE2EDryRunChainStatus.READY_FOR_E2E_DRY_RUN_CHAIN_REVIEW
        ready = True
        eligible = True
        recommended_next_step = (
            "review_e2e_dry_run_chain_then_prepare_future_real_approval_planning_"
            "separate_step_no_post"
        )
        summary = "ready for E2E dry-run chain review only; live post remains disallowed"

    chain_id = make_live_order_e2e_dry_run_chain_id(
        candidate_id=_text_from(candidate, "candidate_id"),
        runbook_id=_text_from(execution_runbook, "runbook_id"),
        created_at=created,
        chain_status=status,
        blocked_reasons=blocked_reasons,
    )
    chain_review = LiveOrderE2EDryRunChainReview(
        chain_id=chain_id,
        created_at=created,
        candidate_id=_text_from(candidate, "candidate_id"),
        risk_decision_id=_text_from(risk_decision, "decision_id"),
        trace_id=_text_from(trace_record, "trace_id"),
        review_id=_text_from(review_report, "review_id"),
        session_policy_decision_id=_text_from(session_policy_decision, "decision_id"),
        bundle_id=_text_from(session_bundle, "bundle_id"),
        operator_review_id=_text_from(operator_review, "operator_review_id"),
        handoff_id=_text_from(approval_handoff, "handoff_id"),
        design_id=_text_from(approval_gate_design, "design_id"),
        preview_id=_text_from(approval_gate_preview, "preview_id"),
        simulation_id=_text_from(approval_validation_simulation, "simulation_id"),
        preflight_decision_id=_text_from(final_dynamic_preflight_decision, "decision_id"),
        boundary_id=_text_from(one_shot_boundary_decision, "boundary_id"),
        runbook_id=_text_from(execution_runbook, "runbook_id"),
        source_signal_id=_first_text(objects, "source_signal_id"),
        source_type=_first_text(objects, "source_type"),
        strategy_name=_first_text(objects, "strategy_name"),
        symbol=_first_text(objects, "symbol"),
        side=_first_text(objects, "side"),
        size=_first_int(objects, "size"),
        execution_type=_first_text(objects, "execution_type"),
        chain_status=status,
        chain_ready=ready,
        eligible_for_future_real_approval_planning=eligible,
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
        stages=stages,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            stages=stages,
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
        ),
    )
    return LiveOrderE2EDryRunChainBuildResult(
        chain_review=chain_review,
        chain_id=chain_review.chain_id,
        chain_status=chain_review.chain_status,
        blocked_reasons=chain_review.blocked_reasons,
        chain_ready=chain_review.chain_ready,
        eligible_for_future_real_approval_planning=(
            chain_review.eligible_for_future_real_approval_planning
        ),
        allowed_for_live=False,
        post_attempt_limit=ONE_SHOT_POST_ATTEMPT_LIMIT,
        post_executed=False,
        live_order_once_called=False,
        private_api_called=False,
        broker_called=False,
        read_only_api_called=False,
        recommended_next_step=chain_review.recommended_next_step,
    )


def render_live_order_e2e_dry_run_chain_markdown(
    chain_review: LiveOrderE2EDryRunChainReview,
) -> str:
    """Render a sanitized dry-run chain report."""
    blocked_text = ", ".join(chain_review.blocked_reasons) or "none"
    stage_lines = "\n".join(
        (
            f"- {stage.name}: status={stage.status}, ready={stage.ready}, "
            f"allowed_for_live={stage.allowed_for_live}, dry_run_only={stage.dry_run_only}"
        )
        for stage in chain_review.stages
    )
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in chain_review.check_results
    )
    return "\n".join(
        (
            "# Step 5P E2E Dry-run Chain Review",
            "",
            "This E2E dry-run chain review is dry-run only.",
            "This review does not call read-only API.",
            "This review does not call Private API.",
            "This review does not call live_order_once.",
            "This review does not execute HTTP POST.",
            "This review does not issue a real approval gate.",
            "This review does not generate a real approval command.",
            "This review does not authorize live POST.",
            "allowed_for_live=false.",
            "",
            f"chain_id: {chain_review.chain_id}",
            f"candidate_id: {chain_review.candidate_id}",
            f"risk_decision_id: {chain_review.risk_decision_id}",
            f"trace_id: {chain_review.trace_id}",
            f"review_id: {chain_review.review_id}",
            f"session_policy_decision_id: {chain_review.session_policy_decision_id}",
            f"bundle_id: {chain_review.bundle_id}",
            f"operator_review_id: {chain_review.operator_review_id}",
            f"handoff_id: {chain_review.handoff_id}",
            f"design_id: {chain_review.design_id}",
            f"preview_id: {chain_review.preview_id}",
            f"simulation_id: {chain_review.simulation_id}",
            f"preflight_decision_id: {chain_review.preflight_decision_id}",
            f"boundary_id: {chain_review.boundary_id}",
            f"runbook_id: {chain_review.runbook_id}",
            f"source_signal_id: {chain_review.source_signal_id}",
            f"source_type: {chain_review.source_type}",
            f"strategy_name: {chain_review.strategy_name}",
            f"symbol: {chain_review.symbol}",
            f"side: {chain_review.side}",
            f"size: {chain_review.size}",
            f"executionType: {chain_review.execution_type}",
            f"chain_status: {chain_review.chain_status.value}",
            f"chain_ready: {chain_review.chain_ready}",
            "eligible_for_future_real_approval_planning: "
            f"{chain_review.eligible_for_future_real_approval_planning}",
            f"allowed_for_live: {chain_review.allowed_for_live}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {chain_review.recommended_next_step}",
            "",
            "## Stages",
            stage_lines,
            "",
            "## Check Results",
            check_lines,
        ),
    )


def make_live_order_e2e_dry_run_chain_id(
    *,
    candidate_id: str,
    runbook_id: str,
    created_at: datetime,
    chain_status: LiveOrderE2EDryRunChainStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "candidate_id": candidate_id,
        "runbook_id": runbook_id,
        "created_at": _ensure_aware(created_at).isoformat(),
        "chain_status": chain_status.value,
        "blocked_reasons": list(blocked_reasons),
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_E2E_DRY_RUN_CHAIN_ID_PREFIX}{digest}"


@dataclass(frozen=True)
class _StageInput:
    name: str
    obj: object | None
    id_field: str
    status_field: str
    ready_status: str
    ready_flag_field: str | None = None


def _stage_inputs(
    *,
    candidate: LiveOrderCandidate | None,
    risk_decision: LiveOrderCandidateRiskDecision | None,
    trace_record: LiveOrderCandidateTraceRecord | None,
    review_report: LiveOrderCandidateReviewReport | None,
    session_policy_decision: ReviewGatedSessionPolicyDecision | None,
    session_bundle: ReviewGatedSessionBundle | None,
    operator_review: LiveOrderOperatorReviewProcedure | None,
    approval_handoff: LiveOrderApprovalHandoffPackage | None,
    approval_gate_design: LiveOrderApprovalGateDesign | None,
    approval_gate_preview: LiveOrderApprovalGatePreview | None,
    approval_validation_simulation: LiveOrderApprovalValidationSimulation | None,
    final_dynamic_preflight_decision: LiveOrderFinalDynamicPreflightDecision | None,
    one_shot_boundary_decision: LiveOrderOneShotBoundaryDecision | None,
    execution_runbook: LiveOrderOneShotExecutionRunbook | None,
) -> tuple[_StageInput, ...]:
    return (
        _StageInput("candidate_dry_run", candidate, "candidate_id", "status", "REVIEW_REQUIRED"),
        _StageInput(
            "risk_gate",
            risk_decision,
            "decision_id",
            "status",
            "PASSED_FOR_HUMAN_REVIEW",
            "risk_gate_passed",
        ),
        _StageInput(
            "trace_record",
            trace_record,
            "trace_id",
            "trace_status",
            "READY_FOR_REVIEW",
        ),
        _StageInput(
            "review_report",
            review_report,
            "review_id",
            "review_status",
            "READY_FOR_HUMAN_REVIEW",
            "eligible_for_human_review",
        ),
        _StageInput(
            "session_policy",
            session_policy_decision,
            "decision_id",
            "status",
            "POLICY_PASSED_FOR_REVIEW",
            "policy_passed",
        ),
        _StageInput(
            "session_bundle",
            session_bundle,
            "bundle_id",
            "bundle_status",
            "READY_FOR_OPERATOR_REVIEW",
            "eligible_for_review_session",
        ),
        _StageInput(
            "operator_review",
            operator_review,
            "operator_review_id",
            "operator_review_status",
            "READY_FOR_OPERATOR_CHECKLIST",
            "eligible_for_operator_review",
        ),
        _StageInput(
            "approval_handoff",
            approval_handoff,
            "handoff_id",
            "handoff_status",
            "READY_FOR_APPROVAL_HANDOFF_REVIEW",
        ),
        _StageInput(
            "approval_gate_design",
            approval_gate_design,
            "design_id",
            "design_status",
            "READY_FOR_APPROVAL_GATE_DESIGN_REVIEW",
        ),
        _StageInput(
            "approval_gate_preview",
            approval_gate_preview,
            "preview_id",
            "preview_status",
            "READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW",
        ),
        _StageInput(
            "approval_validation_simulation",
            approval_validation_simulation,
            "simulation_id",
            "simulation_status",
            "SIMULATED_APPROVAL_VALIDATION_PASSED",
            "simulated_command_exact_match",
        ),
        _StageInput(
            "final_dynamic_preflight",
            final_dynamic_preflight_decision,
            "decision_id",
            "preflight_status",
            "READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW",
            "preflight_passed",
        ),
        _StageInput(
            "one_shot_boundary",
            one_shot_boundary_decision,
            "boundary_id",
            "boundary_status",
            "READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW",
            "boundary_passed",
        ),
        _StageInput(
            "execution_runbook",
            execution_runbook,
            "runbook_id",
            "runbook_status",
            "READY_FOR_ONE_SHOT_EXECUTION_RUNBOOK_REVIEW",
            "runbook_ready",
        ),
    )


def _build_stage(stage_input: _StageInput) -> LiveOrderE2EDryRunChainStage:
    if stage_input.obj is None:
        return LiveOrderE2EDryRunChainStage(
            name=stage_input.name,
            stage_id=f"missing_{stage_input.name}_id",
            status="missing",
            ready=False,
            allowed_for_live=False,
            dry_run_only=False,
            summary="missing required dry-run stage input",
            blocked_reasons=(
                LiveOrderE2EDryRunChainBlockReason.MISSING_REQUIRED_STAGE.value,
            ),
        )
    status = _enum_value(getattr(stage_input.obj, stage_input.status_field, "missing_status"))
    ready = status == stage_input.ready_status
    if stage_input.ready_flag_field is not None:
        ready = ready and getattr(stage_input.obj, stage_input.ready_flag_field, None) is True
    blocked_reasons = _existing_reasons(stage_input.obj)
    if not ready:
        blocked_reasons = _merge_reasons(
            blocked_reasons,
            (LiveOrderE2EDryRunChainBlockReason.STAGE_NOT_READY.value,),
        )
    return LiveOrderE2EDryRunChainStage(
        name=stage_input.name,
        stage_id=_text_from(stage_input.obj, stage_input.id_field),
        status=status,
        ready=ready,
        allowed_for_live=getattr(stage_input.obj, "allowed_for_live", False) is True,
        dry_run_only=getattr(stage_input.obj, "dry_run_only", False) is True,
        summary=_safe_text(getattr(stage_input.obj, "summary", status), status),
        blocked_reasons=blocked_reasons,
    )


def _chain_blocked_reasons(
    *,
    stage_inputs: tuple[_StageInput, ...],
    stages: tuple[LiveOrderE2EDryRunChainStage, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    objects = tuple(stage_input.obj for stage_input in stage_inputs if stage_input.obj is not None)

    if any(stage_input.obj is None for stage_input in stage_inputs):
        _add_reason(reasons, LiveOrderE2EDryRunChainBlockReason.MISSING_REQUIRED_STAGE)
    if {stage.name for stage in stages} != set(REQUIRED_E2E_DRY_RUN_CHAIN_STAGE_NAMES):
        _add_reason(reasons, LiveOrderE2EDryRunChainBlockReason.MISSING_REQUIRED_STAGE)
    for stage in stages:
        if not stage.ready:
            _add_reason(reasons, LiveOrderE2EDryRunChainBlockReason.STAGE_NOT_READY)
        for reason in stage.blocked_reasons:
            _add_external_reason(reasons, reason)

    _add_id_consistency_reasons(reasons, stage_inputs)
    _add_value_consistency_reason(
        reasons,
        objects,
        field_name="source_signal_id",
        expected=_text_from(stage_inputs[0].obj, "source_signal_id"),
        reason=LiveOrderE2EDryRunChainBlockReason.SOURCE_SIGNAL_ID_MISMATCH,
    )
    _add_value_consistency_reason(
        reasons,
        objects,
        field_name="symbol",
        expected=SUPPORTED_SYMBOL,
        reason=LiveOrderE2EDryRunChainBlockReason.SYMBOL_MISMATCH,
    )
    _add_value_consistency_reason(
        reasons,
        objects,
        field_name="side",
        expected_values=(LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value),
        reason=LiveOrderE2EDryRunChainBlockReason.SIDE_MISMATCH,
    )
    _add_value_consistency_reason(
        reasons,
        objects,
        field_name="size",
        expected=LIVE_ORDER_CANDIDATE_SIZE,
        reason=LiveOrderE2EDryRunChainBlockReason.SIZE_MISMATCH,
    )
    _add_value_consistency_reason(
        reasons,
        objects,
        field_name="execution_type",
        expected=LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
        reason=LiveOrderE2EDryRunChainBlockReason.EXECUTION_TYPE_MISMATCH,
    )
    _add_safety_flag_reasons(reasons, objects)
    return tuple(reasons)


def _add_id_consistency_reasons(
    reasons: list[str],
    stage_inputs: tuple[_StageInput, ...],
) -> None:
    objects = tuple(stage_input.obj for stage_input in stage_inputs if stage_input.obj is not None)
    candidate = stage_inputs[0].obj
    risk_decision = stage_inputs[1].obj
    trace_record = stage_inputs[2].obj
    review_report = stage_inputs[3].obj
    policy_decision = stage_inputs[4].obj
    session_bundle = stage_inputs[5].obj
    operator_review = stage_inputs[6].obj
    approval_handoff = stage_inputs[7].obj
    approval_gate_design = stage_inputs[8].obj
    approval_gate_preview = stage_inputs[9].obj
    simulation = stage_inputs[10].obj
    final_preflight = stage_inputs[11].obj
    boundary = stage_inputs[12].obj
    runbook = stage_inputs[13].obj

    _add_value_consistency_reason(
        reasons,
        objects,
        field_name="candidate_id",
        expected=_text_from(candidate, "candidate_id"),
        reason=LiveOrderE2EDryRunChainBlockReason.CANDIDATE_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(risk_decision, "decision_id"),
        objects=objects,
        reference_field="risk_decision_id",
        reason=LiveOrderE2EDryRunChainBlockReason.RISK_DECISION_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(trace_record, "trace_id"),
        objects=objects,
        reference_field="trace_id",
        reason=LiveOrderE2EDryRunChainBlockReason.TRACE_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(review_report, "review_id"),
        objects=objects,
        reference_field="review_id",
        reason=LiveOrderE2EDryRunChainBlockReason.REVIEW_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(policy_decision, "decision_id"),
        objects=objects,
        reference_field="session_policy_decision_id",
        reason=LiveOrderE2EDryRunChainBlockReason.STAGE_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(session_bundle, "bundle_id"),
        objects=objects,
        reference_field="bundle_id",
        reason=LiveOrderE2EDryRunChainBlockReason.STAGE_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(operator_review, "operator_review_id"),
        objects=objects,
        reference_field="operator_review_id",
        reason=LiveOrderE2EDryRunChainBlockReason.STAGE_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(approval_handoff, "handoff_id"),
        objects=objects,
        reference_field="handoff_id",
        reason=LiveOrderE2EDryRunChainBlockReason.STAGE_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(approval_gate_design, "design_id"),
        objects=objects,
        reference_field="design_id",
        reason=LiveOrderE2EDryRunChainBlockReason.STAGE_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(approval_gate_preview, "preview_id"),
        objects=objects,
        reference_field="preview_id",
        reason=LiveOrderE2EDryRunChainBlockReason.STAGE_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(simulation, "simulation_id"),
        objects=objects,
        reference_field="simulation_id",
        reason=LiveOrderE2EDryRunChainBlockReason.STAGE_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(final_preflight, "decision_id"),
        objects=(boundary, runbook),
        reference_field="preflight_decision_id",
        reason=LiveOrderE2EDryRunChainBlockReason.STAGE_ID_MISMATCH,
    )
    _add_id_reference_reason(
        reasons,
        expected=_text_from(boundary, "boundary_id"),
        objects=(runbook,),
        reference_field="boundary_id",
        reason=LiveOrderE2EDryRunChainBlockReason.STAGE_ID_MISMATCH,
    )


def _add_safety_flag_reasons(reasons: list[str], objects: tuple[object, ...]) -> None:
    if any(getattr(obj, "allowed_for_live", None) is not False for obj in objects):
        _add_reason(reasons, LiveOrderE2EDryRunChainBlockReason.STAGE_ALLOWS_LIVE)
    if any(getattr(obj, "dry_run_only", None) is not True for obj in objects):
        _add_reason(reasons, LiveOrderE2EDryRunChainBlockReason.STAGE_NOT_DRY_RUN)
    if any(getattr(obj, "approval_gate_issued", False) is True for obj in objects):
        _add_reason(
            reasons,
            LiveOrderE2EDryRunChainBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        )
    if any(getattr(obj, "approval_id_generated", False) is True for obj in objects):
        _add_reason(
            reasons,
            LiveOrderE2EDryRunChainBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        )
    if any(getattr(obj, "approval_command_generated", False) is True for obj in objects):
        _add_reason(
            reasons,
            LiveOrderE2EDryRunChainBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        )
    if any(getattr(obj, "approval_command_copyable", False) is True for obj in objects):
        _add_reason(
            reasons,
            LiveOrderE2EDryRunChainBlockReason.APPROVAL_COMMAND_COPYABLE,
        )
    if any(getattr(obj, "post_executed", False) is True for obj in objects):
        _add_reason(reasons, LiveOrderE2EDryRunChainBlockReason.POST_ALREADY_EXECUTED)
    if any(getattr(obj, "live_order_once_called", False) is True for obj in objects):
        _add_reason(
            reasons,
            LiveOrderE2EDryRunChainBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        )
    if any(getattr(obj, "private_api_called", False) is True for obj in objects):
        _add_reason(
            reasons,
            LiveOrderE2EDryRunChainBlockReason.PRIVATE_API_ALREADY_CALLED,
        )
    if any(getattr(obj, "broker_called", False) is True for obj in objects):
        _add_reason(reasons, LiveOrderE2EDryRunChainBlockReason.BROKER_ALREADY_CALLED)
    if any(getattr(obj, "read_only_api_called", False) is True for obj in objects):
        _add_reason(
            reasons,
            LiveOrderE2EDryRunChainBlockReason.READ_ONLY_API_ALREADY_CALLED,
        )
    if any(getattr(obj, "post_attempt_limit", ONE_SHOT_POST_ATTEMPT_LIMIT) != 1 for obj in objects):
        _add_reason(
            reasons,
            LiveOrderE2EDryRunChainBlockReason.INVALID_POST_ATTEMPT_LIMIT,
        )
    for field_name, reason in (
        ("retry_allowed", LiveOrderE2EDryRunChainBlockReason.RETRY_ALLOWED),
        ("loop_allowed", LiveOrderE2EDryRunChainBlockReason.LOOP_ALLOWED),
        ("add_order_allowed", LiveOrderE2EDryRunChainBlockReason.ADD_ORDER_ALLOWED),
        ("change_order_allowed", LiveOrderE2EDryRunChainBlockReason.CHANGE_ORDER_ALLOWED),
        ("cancel_order_allowed", LiveOrderE2EDryRunChainBlockReason.CANCEL_ORDER_ALLOWED),
        ("close_order_allowed", LiveOrderE2EDryRunChainBlockReason.CLOSE_ORDER_ALLOWED),
    ):
        if any(getattr(obj, field_name, False) is True for obj in objects):
            _add_reason(reasons, reason)
    if any(getattr(obj, "post_reconciliation_required", True) is not True for obj in objects):
        _add_reason(
            reasons,
            LiveOrderE2EDryRunChainBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        )


def _build_check_results(
    *,
    stage_inputs: tuple[_StageInput, ...],
    stages: tuple[LiveOrderE2EDryRunChainStage, ...],
) -> tuple[LiveOrderE2EDryRunChainCheckResult, ...]:
    objects = tuple(stage_input.obj for stage_input in stage_inputs if stage_input.obj is not None)
    stage_names = {stage.name for stage in stages}
    all_required_present = all(stage_input.obj is not None for stage_input in stage_inputs)
    stage_statuses_ready = all(stage.ready for stage in stages)
    symbol_ok = _values_consistent(objects, "symbol", expected=SUPPORTED_SYMBOL)
    side_ok = _values_consistent(
        objects,
        "side",
        expected_values=(LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value),
    )
    size_ok = _values_consistent(objects, "size", expected=LIVE_ORDER_CANDIDATE_SIZE)
    execution_type_ok = _values_consistent(
        objects,
        "execution_type",
        expected=LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    )
    source_ok = _values_consistent(
        objects,
        "source_signal_id",
        expected=_text_from(stage_inputs[0].obj, "source_signal_id"),
    )
    ids_ok = not any(
        reason
        in {
            LiveOrderE2EDryRunChainBlockReason.CANDIDATE_ID_MISMATCH.value,
            LiveOrderE2EDryRunChainBlockReason.RISK_DECISION_ID_MISMATCH.value,
            LiveOrderE2EDryRunChainBlockReason.TRACE_ID_MISMATCH.value,
            LiveOrderE2EDryRunChainBlockReason.REVIEW_ID_MISMATCH.value,
            LiveOrderE2EDryRunChainBlockReason.STAGE_ID_MISMATCH.value,
        }
        for reason in _chain_blocked_reasons(stage_inputs=stage_inputs, stages=stages)
    )
    allowed_false = all(getattr(obj, "allowed_for_live", None) is False for obj in objects)
    dry_run_true = all(getattr(obj, "dry_run_only", None) is True for obj in objects)
    approval_clear = not any(
        getattr(obj, "approval_gate_issued", False) is True
        or getattr(obj, "approval_id_generated", False) is True
        or getattr(obj, "approval_command_generated", False) is True
        or getattr(obj, "approval_command_copyable", False) is True
        for obj in objects
    )
    post_not_executed = not any(getattr(obj, "post_executed", False) is True for obj in objects)
    no_api_calls = not any(
        getattr(obj, "live_order_once_called", False) is True
        or getattr(obj, "private_api_called", False) is True
        or getattr(obj, "broker_called", False) is True
        or getattr(obj, "read_only_api_called", False) is True
        for obj in objects
    )
    one_shot_ok = all(
        getattr(obj, "post_attempt_limit", ONE_SHOT_POST_ATTEMPT_LIMIT)
        == ONE_SHOT_POST_ATTEMPT_LIMIT
        and getattr(obj, "retry_allowed", False) is False
        and getattr(obj, "loop_allowed", False) is False
        and getattr(obj, "add_order_allowed", False) is False
        and getattr(obj, "change_order_allowed", False) is False
        and getattr(obj, "cancel_order_allowed", False) is False
        and getattr(obj, "close_order_allowed", False) is False
        for obj in objects
    )
    reconciliation_required = all(
        getattr(obj, "post_reconciliation_required", True) is True for obj in objects
    )
    return (
        _check(
            "all_required_stages_present",
            all_required_present
            and set(REQUIRED_E2E_DRY_RUN_CHAIN_STAGE_NAMES).issubset(stage_names),
            ",".join(sorted(stage_names)) if stage_names else "none",
            ",".join(REQUIRED_E2E_DRY_RUN_CHAIN_STAGE_NAMES),
        ),
        _check(
            "stage_statuses_ready",
            stage_statuses_ready,
            _bool_text(stage_statuses_ready),
            "true",
        ),
        _check("symbol_consistency", symbol_ok, _values_text(objects, "symbol"), SUPPORTED_SYMBOL),
        _check(
            "side_consistency",
            side_ok,
            _values_text(objects, "side"),
            "BUY or SELL consistently",
        ),
        _check("size_consistency", size_ok, _values_text(objects, "size"), "100"),
        _check(
            "execution_type_consistency",
            execution_type_ok,
            _values_text(objects, "execution_type"),
            "MARKET",
        ),
        _check(
            "source_signal_consistency",
            source_ok,
            _values_text(objects, "source_signal_id"),
            "single sanitized source signal id",
        ),
        _check(
            "candidate_review_trace_risk_session_ids_consistency",
            ids_ok,
            "consistent" if ids_ok else "mismatch",
            "consistent",
        ),
        _check(
            "allowed_for_live_false_across_chain",
            allowed_false,
            _bool_text(allowed_false),
            "true",
        ),
        _check("dry_run_only_true_across_chain", dry_run_true, _bool_text(dry_run_true), "true"),
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
            "post_reconciliation_required",
            reconciliation_required,
            _bool_text(reconciliation_required),
            "true",
        ),
    )


def _build_sections(
    *,
    stages: tuple[LiveOrderE2EDryRunChainStage, ...],
    check_results: tuple[LiveOrderE2EDryRunChainCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
) -> tuple[LiveOrderE2EDryRunChainSection, ...]:
    blocked_text = ", ".join(blocked_reasons) if blocked_reasons else "none"
    failed_checks = tuple(check.name for check in check_results if not check.passed)
    failed_text = ", ".join(failed_checks) if failed_checks else "none"
    return (
        LiveOrderE2EDryRunChainSection(
            section_id="stages",
            title="Dry-run Stages",
            lines=tuple(
                f"{stage.name}: {stage.status} ready={stage.ready}" for stage in stages
            ),
        ),
        LiveOrderE2EDryRunChainSection(
            section_id="checks",
            title="Chain Checks",
            lines=(
                f"failed_checks: {failed_text}",
                f"blocked_reasons: {blocked_text}",
            ),
        ),
        LiveOrderE2EDryRunChainSection(
            section_id="safety",
            title="Safety Defaults",
            lines=(
                "allowed_for_live: False",
                "approval_gate_issued: False",
                "approval_id_generated: False",
                "approval_command_generated: False",
                "approval_command_copyable: False",
                "post_executed: False",
                "live_order_once_called: False",
                "private_api_called: False",
                "broker_called: False",
                "read_only_api_called: False",
                "post_attempt_limit: 1",
            ),
        ),
        LiveOrderE2EDryRunChainSection(
            section_id="next_step",
            title="Recommended Next Step",
            lines=(recommended_next_step,),
        ),
    )


def _validate_chain_review(chain_review: LiveOrderE2EDryRunChainReview) -> None:
    _require_non_empty("chain_id", chain_review.chain_id)
    if not isinstance(chain_review.created_at, datetime):
        raise LiveVerificationValidationError("created_at must be datetime")
    for field_name in (
        "candidate_id",
        "risk_decision_id",
        "trace_id",
        "review_id",
        "session_policy_decision_id",
        "bundle_id",
        "operator_review_id",
        "handoff_id",
        "design_id",
        "preview_id",
        "simulation_id",
        "preflight_decision_id",
        "boundary_id",
        "runbook_id",
        "source_signal_id",
        "source_type",
        "strategy_name",
        "symbol",
        "side",
        "execution_type",
        "summary",
        "recommended_next_step",
    ):
        _require_non_empty(field_name, getattr(chain_review, field_name))
    if type(chain_review.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    for field_name, expected in (
        ("allowed_for_live", False),
        ("requires_human_approval", True),
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
        if getattr(chain_review, field_name) is not expected:
            raise LiveVerificationValidationError(f"{field_name} safety default mismatch")
    if chain_review.post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if chain_review.allowed_for_live is not False:
        raise LiveVerificationValidationError("Step 5P never allows live execution")
    if not chain_review.stages:
        raise LiveVerificationValidationError("stages are required")
    if not chain_review.check_results:
        raise LiveVerificationValidationError("check_results are required")
    if not chain_review.sections:
        raise LiveVerificationValidationError("sections are required")
    if (
        chain_review.chain_status
        is LiveOrderE2EDryRunChainStatus.READY_FOR_E2E_DRY_RUN_CHAIN_REVIEW
    ):
        if not chain_review.chain_ready:
            raise LiveVerificationValidationError("ready chain must be ready")
        if chain_review.blocked_reasons:
            raise LiveVerificationValidationError("ready chain cannot have blockers")
    if chain_review.chain_status is LiveOrderE2EDryRunChainStatus.BLOCKED_E2E_DRY_RUN_CHAIN:
        if chain_review.chain_ready:
            raise LiveVerificationValidationError("blocked chain cannot be ready")
        if chain_review.eligible_for_future_real_approval_planning:
            raise LiveVerificationValidationError("blocked chain cannot be eligible")


def _add_value_consistency_reason(
    reasons: list[str],
    objects: tuple[object, ...],
    *,
    field_name: str,
    reason: LiveOrderE2EDryRunChainBlockReason,
    expected: object | None = None,
    expected_values: tuple[object, ...] | None = None,
) -> None:
    if not _values_consistent(
        objects,
        field_name,
        expected=expected,
        expected_values=expected_values,
    ):
        _add_reason(reasons, reason)


def _add_id_reference_reason(
    reasons: list[str],
    *,
    expected: str,
    objects: tuple[object | None, ...],
    reference_field: str,
    reason: LiveOrderE2EDryRunChainBlockReason,
) -> None:
    if not _has_text(expected):
        _add_reason(reasons, reason)
        return
    for obj in objects:
        if obj is None or not hasattr(obj, reference_field):
            continue
        if _safe_value(getattr(obj, reference_field)) != expected:
            _add_reason(reasons, reason)
            return


def _values_consistent(
    objects: tuple[object, ...],
    field_name: str,
    *,
    expected: object | None = None,
    expected_values: tuple[object, ...] | None = None,
) -> bool:
    values = tuple(
        _safe_value(getattr(obj, field_name))
        for obj in objects
        if hasattr(obj, field_name)
    )
    if not values:
        return False
    if expected_values is not None:
        normalized = {_safe_value(value) for value in expected_values}
        return len(set(values)) == 1 and values[0] in normalized
    if expected is not None:
        expected_text = _safe_value(expected)
        return all(value == expected_text for value in values)
    return len(set(values)) == 1


def _values_text(objects: tuple[object, ...], field_name: str) -> str:
    values = tuple(
        _safe_value(getattr(obj, field_name))
        for obj in objects
        if hasattr(obj, field_name)
    )
    return ",".join(sorted(set(values))) if values else "missing"


def _existing_reasons(obj: object) -> tuple[str, ...]:
    reasons: list[str] = []
    blocked_reasons = getattr(obj, "blocked_reasons", ())
    if isinstance(blocked_reasons, tuple):
        for reason in blocked_reasons:
            text = _enum_value(reason)
            if _has_text(text):
                reasons.append(text)
    blocked_reason = getattr(obj, "blocked_reason", None)
    text = _enum_value(blocked_reason)
    if _has_text(text) and text not in {"none", "None"}:
        reasons.append(text)
    return tuple(dict.fromkeys(reasons))


def _check(
    name: str,
    passed: bool,
    sanitized_value: object,
    expected: str,
) -> LiveOrderE2EDryRunChainCheckResult:
    return LiveOrderE2EDryRunChainCheckResult(
        name=name,
        passed=bool(passed),
        reason="passed" if passed else f"{name}_failed",
        sanitized_value=_safe_value(sanitized_value),
        expected=expected,
    )


def _text_from(obj: object | None, field_name: str) -> str:
    if obj is None:
        return f"missing_{field_name}"
    value = getattr(obj, field_name, None)
    return _safe_value(value) if _has_text(_safe_value(value)) else f"missing_{field_name}"


def _first_text(objects: tuple[object, ...], field_name: str) -> str:
    for obj in objects:
        if hasattr(obj, field_name):
            value = _safe_value(getattr(obj, field_name))
            if _has_text(value):
                return value
    return f"missing_{field_name}"


def _first_int(objects: tuple[object, ...], field_name: str) -> int:
    for obj in objects:
        value = getattr(obj, field_name, None)
        if type(value) is int:
            return value
    return 0


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            _add_external_reason(merged, reason)
    return tuple(merged)


def _add_reason(
    reasons: list[str],
    reason: LiveOrderE2EDryRunChainBlockReason,
) -> None:
    if reason.value not in reasons:
        reasons.append(reason.value)


def _add_external_reason(reasons: list[str], reason: str) -> None:
    if _has_text(reason) and reason not in reasons:
        reasons.append(reason)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _enum_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")


def _safe_text(value: object, fallback: str) -> str:
    text = _safe_value(value)
    return text if _has_text(text) else fallback


def _safe_value(value: object) -> str:
    if value is None:
        return "missing"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)
