"""Real approval gate implementation readiness review for Step 5V."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_ACK_TOKENS,
    APPROVAL_GATE_TTL_SECONDS,
)
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.live_order_real_approval_pre_implementation_audit import (
    LiveOrderRealApprovalPreImplementationAudit,
    LiveOrderRealApprovalPreImplementationAuditStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

AuditStatus = LiveOrderRealApprovalPreImplementationAuditStatus

LIVE_ORDER_REAL_APPROVAL_IMPLEMENTATION_READINESS_ID_PREFIX = "LORAIIR-"

DEFAULT_REAL_APPROVAL_IMPLEMENTATION_READINESS_RESIDUAL_RISKS = (
    "real approval gate implementation has not been performed in this step",
    "real approval_id and real approval command generation remain future work",
    "future implementation can be affected by prompt truncation or copied text errors",
    "future fresh preflight and final dynamic preflight must be rechecked",
    "market and account state can change before any future approval gate",
    "result_unknown must stop without retries or additional orders",
)

DEFAULT_REAL_APPROVAL_IMPLEMENTATION_READINESS_MANUAL_CONFIRMATION_ITEMS = (
    "user must explicitly request the future real approval gate implementation step",
    "user must confirm real-money risk before any future approval gate",
    "user must confirm order permission, IP/account state, and event window in the future step",
    "user must paste any future approval command in the same Codex session",
    "user must understand post_attempt_limit=1 and no retry, loop, add, change, cancel, or close",
)

DEFAULT_REAL_APPROVAL_IMPLEMENTATION_READINESS_BLOCKERS = (
    "future explicit user instruction required",
    "real approval gate implementation not yet performed",
    "real approval_id generation not yet performed",
    "real approval command generation not yet performed",
    "runtime exact match validation not yet performed",
    "post-approval final dynamic preflight not yet performed",
    "one-shot POST not yet performed",
    "post reconciliation not yet performed",
)

REAL_APPROVAL_IMPLEMENTATION_READINESS_DISPLAY_ALLOWED_FIELDS = (
    "review_id",
    "audit_id",
    "package_id",
    "pre_approval_preflight_decision_id",
    "snapshot_id",
    "plan_id",
    "checkpoint_id",
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
    "candidate_review_id",
    "candidate_id",
    "risk_decision_id",
    "trace_id",
    "session_policy_decision_id",
    "source_signal_id",
    "source_type",
    "strategy_name",
    "symbol",
    "side",
    "size",
    "executionType",
    "readiness_status",
    "readiness_ready",
    "eligible_for_future_real_approval_gate_implementation_step",
    "allowed_for_live=false",
    "approval_gate_issued",
    "approval_id_generated",
    "approval_command_generated",
    "approval_command_copyable",
    "ttl_seconds",
    "exact_match_required",
    "same_session_required",
    "required_ack_tokens",
    "post_attempt_limit",
    "post_executed",
    "live_order_once_called",
    "private_api_called",
    "broker_called",
    "read_only_api_called",
    "public_api_called",
    "residual_risks",
    "manual_confirmation_items",
    "implementation_blockers",
    "implementation_readiness_blockers",
    "go_conditions",
    "no_go_conditions",
    "stop_conditions",
    "check_results",
    "blocked_reasons",
    "recommended_next_step",
)

REAL_APPROVAL_IMPLEMENTATION_READINESS_DISPLAY_FORBIDDEN_FIELDS = (
    "API key value",
    "secret value",
    "signature value",
    "headers value",
    "raw request",
    "raw response",
    "order ID",
    "execution ID",
    "position ID",
    "clientOrderId",
    "request URL",
    "open price",
    "detailed P/L",
    "real approval_id",
    "real approval command",
    "copyable approval command",
    "approval command file",
    "clipboard approval command",
)


class LiveOrderRealApprovalImplementationReadinessStatus(str, Enum):
    READY_FOR_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW = (
        "READY_FOR_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW"
    )
    BLOCKED_REAL_APPROVAL_IMPLEMENTATION_READINESS = (
        "BLOCKED_REAL_APPROVAL_IMPLEMENTATION_READINESS"
    )


ReadinessStatus = LiveOrderRealApprovalImplementationReadinessStatus


class LiveOrderRealApprovalImplementationReadinessBlockReason(str, Enum):
    MISSING_PRE_IMPLEMENTATION_AUDIT = "missing_pre_implementation_audit"
    PRE_IMPLEMENTATION_AUDIT_NOT_READY = "pre_implementation_audit_not_ready"
    PRE_IMPLEMENTATION_AUDIT_NOT_ELIGIBLE = "pre_implementation_audit_not_eligible"
    AUDIT_ALLOWS_LIVE = "audit_allows_live"
    AUDIT_NOT_DRY_RUN = "audit_not_dry_run"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_ID_ALREADY_GENERATED = "approval_id_already_generated"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
    APPROVAL_COMMAND_COPYABLE = "approval_command_copyable"
    APPROVAL_ID_GENERATION_NOT_DEFERRED = "approval_id_generation_not_deferred"
    APPROVAL_COMMAND_GENERATION_NOT_DEFERRED = (
        "approval_command_generation_not_deferred"
    )
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    INVALID_TTL_SECONDS = "invalid_ttl_seconds"
    EXACT_MATCH_NOT_REQUIRED = "exact_match_not_required"
    SAME_SESSION_NOT_REQUIRED = "same_session_not_required"
    MISSING_ACK_TOKEN = "missing_ack_token"
    DISPLAY_FORBIDDEN_FIELDS_INCOMPLETE = "display_forbidden_fields_incomplete"
    INVALID_POST_ATTEMPT_LIMIT = "invalid_post_attempt_limit"
    POST_ALREADY_EXECUTED = "post_already_executed"
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
    MISSING_POST_RECONCILIATION_REQUIREMENT = (
        "missing_post_reconciliation_requirement"
    )
    MISSING_RESIDUAL_RISKS = "missing_residual_risks"
    MISSING_MANUAL_CONFIRMATION_ITEMS = "missing_manual_confirmation_items"
    MISSING_IMPLEMENTATION_BLOCKERS = "missing_implementation_blockers"
    PROMPT_TRUNCATION_RISK_NOT_REVIEWED = "prompt_truncation_risk_not_reviewed"
    STEP5U_TEST_COVERAGE_NOT_REVIEWED = "step5u_test_coverage_not_reviewed"
    STEP5U_DOCS_NOT_REVIEWED = "step5u_docs_not_reviewed"


BlockReason = LiveOrderRealApprovalImplementationReadinessBlockReason


@dataclass(frozen=True)
class LiveOrderRealApprovalImplementationReadinessCheckResult:
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
class LiveOrderRealApprovalImplementationReadinessSection:
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
class LiveOrderRealApprovalImplementationReadinessReview:
    review_id: str
    created_at: datetime
    audit_id: str
    package_id: str
    pre_approval_preflight_decision_id: str
    snapshot_id: str
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
    candidate_review_id: str
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
    readiness_status: LiveOrderRealApprovalImplementationReadinessStatus
    readiness_ready: bool
    eligible_for_future_real_approval_gate_implementation_step: bool
    allowed_for_live: bool
    requires_human_approval: bool
    explicit_user_confirmation_required: bool
    approval_gate_required: bool
    approval_gate_planned: bool
    approval_gate_issued: bool
    approval_id_generation_planned: bool
    approval_id_generation_deferred_to_future_step: bool
    approval_id_generated: bool
    approval_command_generation_planned: bool
    approval_command_generation_deferred_to_future_step: bool
    approval_command_generated: bool
    approval_command_template_only: bool
    approval_command_copyable: bool
    fresh_preflight_before_gate_required: bool
    post_approval_final_dynamic_preflight_required: bool
    one_shot_post_separate_step_required: bool
    post_reconciliation_separate_step_required: bool
    final_report_separate_step_required: bool
    dry_run_only: bool
    ttl_seconds: int
    exact_match_required: bool
    same_session_required: bool
    required_ack_tokens: tuple[str, ...]
    post_attempt_limit: int
    post_executed: bool
    live_order_once_called: bool
    private_api_called: bool
    broker_called: bool
    read_only_api_called: bool
    public_api_called: bool
    retry_allowed: bool
    loop_allowed: bool
    add_order_allowed: bool
    change_order_allowed: bool
    cancel_order_allowed: bool
    close_order_allowed: bool
    post_reconciliation_required: bool
    prompt_truncation_risk_reviewed: bool
    step5u_test_coverage_reviewed: bool
    step5u_docs_reviewed: bool
    display_allowed_fields: tuple[str, ...]
    display_forbidden_fields: tuple[str, ...]
    residual_risks: tuple[str, ...]
    manual_confirmation_items: tuple[str, ...]
    implementation_blockers: tuple[str, ...]
    implementation_readiness_blockers: tuple[str, ...]
    go_conditions: tuple[str, ...]
    no_go_conditions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    check_results: tuple[
        LiveOrderRealApprovalImplementationReadinessCheckResult,
        ...,
    ]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApprovalImplementationReadinessSection, ...]

    def __post_init__(self) -> None:
        _validate_review(self)


@dataclass(frozen=True)
class LiveOrderRealApprovalImplementationReadinessBuildResult:
    review: LiveOrderRealApprovalImplementationReadinessReview
    review_id: str
    readiness_status: LiveOrderRealApprovalImplementationReadinessStatus
    readiness_ready: bool
    eligible_for_future_real_approval_gate_implementation_step: bool
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_copyable: bool
    post_executed: bool
    live_order_once_called: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.review.review_id != self.review_id:
            raise LiveVerificationValidationError("review_id mismatch")
        if self.review.readiness_status is not self.readiness_status:
            raise LiveVerificationValidationError("readiness_status mismatch")
        if self.review.readiness_ready is not self.readiness_ready:
            raise LiveVerificationValidationError("readiness_ready mismatch")
        if (
            self.review.eligible_for_future_real_approval_gate_implementation_step
            is not self.eligible_for_future_real_approval_gate_implementation_step
        ):
            raise LiveVerificationValidationError("readiness eligibility mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("Step 5V never allows live execution")
        if self.approval_gate_issued is not False:
            raise LiveVerificationValidationError("Step 5V never issues approval gate")
        if self.approval_id_generated is not False:
            raise LiveVerificationValidationError("Step 5V never generates approval id")
        if self.approval_command_generated is not False:
            raise LiveVerificationValidationError(
                "Step 5V never generates approval command"
            )
        if self.approval_command_copyable is not False:
            raise LiveVerificationValidationError("Step 5V never creates copyable command")
        if self.post_executed is not False:
            raise LiveVerificationValidationError("Step 5V never executes post")
        if self.live_order_once_called is not False:
            raise LiveVerificationValidationError("Step 5V never calls live_order_once")
        if self.review.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.review.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_approval_implementation_readiness_review(
    *,
    pre_implementation_audit: LiveOrderRealApprovalPreImplementationAudit | None,
    created_at: datetime | None = None,
    residual_risks: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_IMPLEMENTATION_READINESS_RESIDUAL_RISKS,
    manual_confirmation_items: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_IMPLEMENTATION_READINESS_MANUAL_CONFIRMATION_ITEMS,
    implementation_readiness_blockers: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_IMPLEMENTATION_READINESS_BLOCKERS,
    prompt_truncation_risk_reviewed: bool = True,
    step5u_test_coverage_reviewed: bool = True,
    step5u_docs_reviewed: bool = True,
    post_attempt_limit: int = 1,
    retry_allowed: bool = False,
    loop_allowed: bool = False,
    add_order_allowed: bool = False,
    change_order_allowed: bool = False,
    cancel_order_allowed: bool = False,
    close_order_allowed: bool = False,
    post_reconciliation_required: bool = True,
) -> LiveOrderRealApprovalImplementationReadinessBuildResult:
    """Build a dry-run implementation readiness review without real artifacts."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    blocked_reasons = _merge_reasons(
        _audit_blocked_reasons(pre_implementation_audit),
        _audit_existing_reasons(pre_implementation_audit),
        _readiness_constraint_reasons(
            pre_implementation_audit=pre_implementation_audit,
            residual_risks=residual_risks,
            manual_confirmation_items=manual_confirmation_items,
            implementation_readiness_blockers=implementation_readiness_blockers,
            prompt_truncation_risk_reviewed=prompt_truncation_risk_reviewed,
            step5u_test_coverage_reviewed=step5u_test_coverage_reviewed,
            step5u_docs_reviewed=step5u_docs_reviewed,
            post_attempt_limit=post_attempt_limit,
            retry_allowed=retry_allowed,
            loop_allowed=loop_allowed,
            add_order_allowed=add_order_allowed,
            change_order_allowed=change_order_allowed,
            cancel_order_allowed=cancel_order_allowed,
            close_order_allowed=close_order_allowed,
            post_reconciliation_required=post_reconciliation_required,
        ),
    )
    check_results = _build_check_results(
        pre_implementation_audit=pre_implementation_audit,
        residual_risks=residual_risks,
        manual_confirmation_items=manual_confirmation_items,
        implementation_readiness_blockers=implementation_readiness_blockers,
        prompt_truncation_risk_reviewed=prompt_truncation_risk_reviewed,
        step5u_test_coverage_reviewed=step5u_test_coverage_reviewed,
        step5u_docs_reviewed=step5u_docs_reviewed,
        post_attempt_limit=post_attempt_limit,
        retry_allowed=retry_allowed,
        loop_allowed=loop_allowed,
        add_order_allowed=add_order_allowed,
        change_order_allowed=change_order_allowed,
        cancel_order_allowed=cancel_order_allowed,
        close_order_allowed=close_order_allowed,
        post_reconciliation_required=post_reconciliation_required,
    )
    if blocked_reasons:
        readiness_status = (
            ReadinessStatus.BLOCKED_REAL_APPROVAL_IMPLEMENTATION_READINESS
        )
        readiness_ready = False
        eligible = False
        recommended_next_step = "fix_pre_implementation_audit_blockers_no_post"
        summary = (
            "blocked real approval implementation readiness review; no approval "
            "gate, approval id, approval command, API call, or post is allowed"
        )
    else:
        readiness_status = (
            ReadinessStatus.READY_FOR_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW
        )
        readiness_ready = True
        eligible = True
        recommended_next_step = (
            "stop_and_wait_for_explicit_user_instruction_for_future_real_approval_gate_implementation_step_no_post"
        )
        summary = (
            "ready for real approval implementation readiness review only; "
            "live post remains disallowed"
        )

    review_id = make_live_order_real_approval_implementation_readiness_id(
        audit_id=_text_from(pre_implementation_audit, "audit_id"),
        candidate_id=_text_from(pre_implementation_audit, "candidate_id"),
        created_at=created,
        readiness_status=readiness_status,
        blocked_reasons=blocked_reasons,
    )
    implementation_blockers = _tuple_from(
        pre_implementation_audit,
        "implementation_blockers",
    )
    review = LiveOrderRealApprovalImplementationReadinessReview(
        review_id=review_id,
        created_at=created,
        audit_id=_text_from(pre_implementation_audit, "audit_id"),
        package_id=_text_from(pre_implementation_audit, "package_id"),
        pre_approval_preflight_decision_id=_text_from(
            pre_implementation_audit,
            "pre_approval_preflight_decision_id",
        ),
        snapshot_id=_text_from(pre_implementation_audit, "snapshot_id"),
        plan_id=_text_from(pre_implementation_audit, "plan_id"),
        checkpoint_id=_text_from(pre_implementation_audit, "checkpoint_id"),
        chain_id=_text_from(pre_implementation_audit, "chain_id"),
        runbook_id=_text_from(pre_implementation_audit, "runbook_id"),
        boundary_id=_text_from(pre_implementation_audit, "boundary_id"),
        preflight_decision_id=_text_from(
            pre_implementation_audit,
            "preflight_decision_id",
        ),
        simulation_id=_text_from(pre_implementation_audit, "simulation_id"),
        preview_id=_text_from(pre_implementation_audit, "preview_id"),
        design_id=_text_from(pre_implementation_audit, "design_id"),
        handoff_id=_text_from(pre_implementation_audit, "handoff_id"),
        operator_review_id=_text_from(pre_implementation_audit, "operator_review_id"),
        bundle_id=_text_from(pre_implementation_audit, "bundle_id"),
        candidate_review_id=_text_from(pre_implementation_audit, "review_id"),
        candidate_id=_text_from(pre_implementation_audit, "candidate_id"),
        risk_decision_id=_text_from(pre_implementation_audit, "risk_decision_id"),
        trace_id=_text_from(pre_implementation_audit, "trace_id"),
        session_policy_decision_id=_text_from(
            pre_implementation_audit,
            "session_policy_decision_id",
        ),
        source_signal_id=_text_from(pre_implementation_audit, "source_signal_id"),
        source_type=_text_from(pre_implementation_audit, "source_type"),
        strategy_name=_text_from(pre_implementation_audit, "strategy_name"),
        symbol=_text_from(pre_implementation_audit, "symbol"),
        side=_text_from(pre_implementation_audit, "side"),
        size=_int_from(pre_implementation_audit, "size"),
        execution_type=_text_from(pre_implementation_audit, "execution_type"),
        readiness_status=readiness_status,
        readiness_ready=readiness_ready,
        eligible_for_future_real_approval_gate_implementation_step=eligible,
        allowed_for_live=False,
        requires_human_approval=True,
        explicit_user_confirmation_required=True,
        approval_gate_required=True,
        approval_gate_planned=True,
        approval_gate_issued=False,
        approval_id_generation_planned=True,
        approval_id_generation_deferred_to_future_step=True,
        approval_id_generated=False,
        approval_command_generation_planned=True,
        approval_command_generation_deferred_to_future_step=True,
        approval_command_generated=False,
        approval_command_template_only=True,
        approval_command_copyable=False,
        fresh_preflight_before_gate_required=True,
        post_approval_final_dynamic_preflight_required=True,
        one_shot_post_separate_step_required=True,
        post_reconciliation_separate_step_required=True,
        final_report_separate_step_required=True,
        dry_run_only=True,
        ttl_seconds=APPROVAL_GATE_TTL_SECONDS,
        exact_match_required=True,
        same_session_required=True,
        required_ack_tokens=APPROVAL_ACK_TOKENS,
        post_attempt_limit=1,
        post_executed=False,
        live_order_once_called=False,
        private_api_called=False,
        broker_called=False,
        read_only_api_called=False,
        public_api_called=False,
        retry_allowed=False,
        loop_allowed=False,
        add_order_allowed=False,
        change_order_allowed=False,
        cancel_order_allowed=False,
        close_order_allowed=False,
        post_reconciliation_required=True,
        prompt_truncation_risk_reviewed=True,
        step5u_test_coverage_reviewed=True,
        step5u_docs_reviewed=True,
        display_allowed_fields=(
            REAL_APPROVAL_IMPLEMENTATION_READINESS_DISPLAY_ALLOWED_FIELDS
        ),
        display_forbidden_fields=(
            REAL_APPROVAL_IMPLEMENTATION_READINESS_DISPLAY_FORBIDDEN_FIELDS
        ),
        residual_risks=residual_risks,
        manual_confirmation_items=manual_confirmation_items,
        implementation_blockers=implementation_blockers,
        implementation_readiness_blockers=implementation_readiness_blockers,
        go_conditions=_tuple_from(pre_implementation_audit, "go_conditions"),
        no_go_conditions=_tuple_from(pre_implementation_audit, "no_go_conditions"),
        stop_conditions=_tuple_from(pre_implementation_audit, "stop_conditions"),
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
            residual_risks=residual_risks,
            manual_confirmation_items=manual_confirmation_items,
            implementation_blockers=implementation_blockers,
            implementation_readiness_blockers=implementation_readiness_blockers,
        ),
    )
    return LiveOrderRealApprovalImplementationReadinessBuildResult(
        review=review,
        review_id=review.review_id,
        readiness_status=review.readiness_status,
        readiness_ready=review.readiness_ready,
        eligible_for_future_real_approval_gate_implementation_step=(
            review.eligible_for_future_real_approval_gate_implementation_step
        ),
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_copyable=False,
        post_executed=False,
        live_order_once_called=False,
        blocked_reasons=review.blocked_reasons,
        recommended_next_step=review.recommended_next_step,
    )


def render_live_order_real_approval_implementation_readiness_markdown(
    review: LiveOrderRealApprovalImplementationReadinessReview,
) -> str:
    """Render a sanitized implementation readiness review."""
    blocked_text = ", ".join(review.blocked_reasons) or "none"
    ack_lines = "\n".join(f"- {token}" for token in review.required_ack_tokens)
    residual_lines = "\n".join(f"- {risk}" for risk in review.residual_risks)
    manual_lines = "\n".join(f"- {item}" for item in review.manual_confirmation_items)
    audit_blocker_lines = "\n".join(f"- {item}" for item in review.implementation_blockers)
    readiness_blocker_lines = "\n".join(
        f"- {item}" for item in review.implementation_readiness_blockers
    )
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in review.check_results
    )
    return "\n".join(
        (
            "# Step 5V Real Approval Implementation Readiness Review",
            "",
            "This real approval implementation readiness review is dry-run only.",
            "This review does not call read-only API.",
            "This review does not call Private API.",
            "This review does not call live_order_once.",
            "This review does not execute HTTP POST.",
            "This review does not issue a real approval gate.",
            "This review does not generate a real approval_id.",
            "This review does not generate a real approval command.",
            "This review does not provide copyable approval text.",
            "This review does not authorize live POST.",
            "allowed_for_live=false.",
            "",
            f"review_id: {review.review_id}",
            f"audit_id: {review.audit_id}",
            f"package_id: {review.package_id}",
            f"pre_approval_preflight_decision_id: {review.pre_approval_preflight_decision_id}",
            f"snapshot_id: {review.snapshot_id}",
            f"plan_id: {review.plan_id}",
            f"checkpoint_id: {review.checkpoint_id}",
            f"chain_id: {review.chain_id}",
            f"runbook_id: {review.runbook_id}",
            f"boundary_id: {review.boundary_id}",
            f"preflight_decision_id: {review.preflight_decision_id}",
            f"simulation_id: {review.simulation_id}",
            f"preview_id: {review.preview_id}",
            f"design_id: {review.design_id}",
            f"handoff_id: {review.handoff_id}",
            f"operator_review_id: {review.operator_review_id}",
            f"bundle_id: {review.bundle_id}",
            f"candidate_review_id: {review.candidate_review_id}",
            f"candidate_id: {review.candidate_id}",
            f"risk_decision_id: {review.risk_decision_id}",
            f"trace_id: {review.trace_id}",
            f"session_policy_decision_id: {review.session_policy_decision_id}",
            f"source_signal_id: {review.source_signal_id}",
            f"source_type: {review.source_type}",
            f"strategy_name: {review.strategy_name}",
            f"symbol: {review.symbol}",
            f"side: {review.side}",
            f"size: {review.size}",
            f"executionType: {review.execution_type}",
            f"readiness_status: {review.readiness_status.value}",
            f"readiness_ready: {review.readiness_ready}",
            "eligible_for_future_real_approval_gate_implementation_step: "
            f"{review.eligible_for_future_real_approval_gate_implementation_step}",
            f"allowed_for_live: {review.allowed_for_live}",
            f"approval_gate_issued: {review.approval_gate_issued}",
            f"approval_id_generated: {review.approval_id_generated}",
            f"approval_command_generated: {review.approval_command_generated}",
            f"approval_command_copyable: {review.approval_command_copyable}",
            f"ttl_seconds: {review.ttl_seconds}",
            f"exact_match_required: {review.exact_match_required}",
            f"same_session_required: {review.same_session_required}",
            f"post_attempt_limit: {review.post_attempt_limit}",
            f"post_executed: {review.post_executed}",
            f"live_order_once_called: {review.live_order_once_called}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {review.recommended_next_step}",
            "",
            "## Required ACK Tokens",
            ack_lines,
            "",
            "## Residual Risks",
            residual_lines,
            "",
            "## Manual Confirmation Items",
            manual_lines,
            "",
            "## Step 5U Implementation Blockers",
            audit_blocker_lines,
            "",
            "## Step 5V Readiness Blockers",
            readiness_blocker_lines,
            "",
            "## Check Results",
            check_lines,
        ),
    )


def make_live_order_real_approval_implementation_readiness_id(
    *,
    audit_id: str,
    candidate_id: str,
    created_at: datetime,
    readiness_status: LiveOrderRealApprovalImplementationReadinessStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "audit_id": audit_id,
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": _ensure_aware(created_at).isoformat(),
        "readiness_status": readiness_status.value,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_IMPLEMENTATION_READINESS_ID_PREFIX}{digest}"


def _audit_blocked_reasons(
    audit: LiveOrderRealApprovalPreImplementationAudit | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(audit, LiveOrderRealApprovalPreImplementationAudit):
        _add_reason(reasons, BlockReason.MISSING_PRE_IMPLEMENTATION_AUDIT)
        return tuple(reasons)
    if (
        audit.audit_status
        is not AuditStatus.READY_FOR_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_REVIEW
        or audit.audit_ready is not True
    ):
        _add_reason(reasons, BlockReason.PRE_IMPLEMENTATION_AUDIT_NOT_READY)
    if audit.eligible_for_future_real_approval_gate_implementation_review is not True:
        _add_reason(reasons, BlockReason.PRE_IMPLEMENTATION_AUDIT_NOT_ELIGIBLE)
    if audit.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.AUDIT_ALLOWS_LIVE)
    if audit.dry_run_only is not True:
        _add_reason(reasons, BlockReason.AUDIT_NOT_DRY_RUN)
    for field_value, reason in (
        (audit.approval_gate_issued, BlockReason.APPROVAL_GATE_ALREADY_ISSUED),
        (audit.approval_id_generated, BlockReason.APPROVAL_ID_ALREADY_GENERATED),
        (
            audit.approval_command_generated,
            BlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (audit.approval_command_copyable, BlockReason.APPROVAL_COMMAND_COPYABLE),
    ):
        if field_value is not False:
            _add_reason(reasons, reason)
    if audit.approval_id_generation_deferred_to_future_step is not True:
        _add_reason(reasons, BlockReason.APPROVAL_ID_GENERATION_NOT_DEFERRED)
    if audit.approval_command_generation_deferred_to_future_step is not True:
        _add_reason(reasons, BlockReason.APPROVAL_COMMAND_GENERATION_NOT_DEFERRED)
    if audit.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SYMBOL)
    if audit.side not in {LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value}:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIDE)
    if audit.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIZE)
    if audit.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_EXECUTION_TYPE)
    return tuple(reasons)


def _audit_existing_reasons(
    audit: LiveOrderRealApprovalPreImplementationAudit | None,
) -> tuple[str, ...]:
    if not isinstance(audit, LiveOrderRealApprovalPreImplementationAudit):
        return ()
    return tuple(audit.blocked_reasons)


def _readiness_constraint_reasons(
    *,
    pre_implementation_audit: LiveOrderRealApprovalPreImplementationAudit | None,
    residual_risks: tuple[str, ...],
    manual_confirmation_items: tuple[str, ...],
    implementation_readiness_blockers: tuple[str, ...],
    prompt_truncation_risk_reviewed: bool,
    step5u_test_coverage_reviewed: bool,
    step5u_docs_reviewed: bool,
    post_attempt_limit: int,
    retry_allowed: bool,
    loop_allowed: bool,
    add_order_allowed: bool,
    change_order_allowed: bool,
    cancel_order_allowed: bool,
    close_order_allowed: bool,
    post_reconciliation_required: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if isinstance(pre_implementation_audit, LiveOrderRealApprovalPreImplementationAudit):
        audit = pre_implementation_audit
        if audit.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
            _add_reason(reasons, BlockReason.INVALID_TTL_SECONDS)
        if audit.exact_match_required is not True:
            _add_reason(reasons, BlockReason.EXACT_MATCH_NOT_REQUIRED)
        if audit.same_session_required is not True:
            _add_reason(reasons, BlockReason.SAME_SESSION_NOT_REQUIRED)
        if set(APPROVAL_ACK_TOKENS) - set(audit.required_ack_tokens):
            _add_reason(reasons, BlockReason.MISSING_ACK_TOKEN)
        if not _display_forbidden_fields_are_complete(audit.display_forbidden_fields):
            _add_reason(reasons, BlockReason.DISPLAY_FORBIDDEN_FIELDS_INCOMPLETE)
        for flag, reason in (
            (audit.post_executed, BlockReason.POST_ALREADY_EXECUTED),
            (audit.live_order_once_called, BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED),
            (audit.private_api_called, BlockReason.PRIVATE_API_ALREADY_CALLED),
            (audit.broker_called, BlockReason.BROKER_ALREADY_CALLED),
            (audit.read_only_api_called, BlockReason.READ_ONLY_API_ALREADY_CALLED),
            (audit.public_api_called, BlockReason.PUBLIC_API_ALREADY_CALLED),
        ):
            if flag is not False:
                _add_reason(reasons, reason)
    if post_attempt_limit != 1:
        _add_reason(reasons, BlockReason.INVALID_POST_ATTEMPT_LIMIT)
    for flag, reason in (
        (retry_allowed, BlockReason.RETRY_ALLOWED),
        (loop_allowed, BlockReason.LOOP_ALLOWED),
        (add_order_allowed, BlockReason.ADD_ORDER_ALLOWED),
        (change_order_allowed, BlockReason.CHANGE_ORDER_ALLOWED),
        (cancel_order_allowed, BlockReason.CANCEL_ORDER_ALLOWED),
        (close_order_allowed, BlockReason.CLOSE_ORDER_ALLOWED),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    if post_reconciliation_required is not True:
        _add_reason(reasons, BlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT)
    if not residual_risks:
        _add_reason(reasons, BlockReason.MISSING_RESIDUAL_RISKS)
    if not manual_confirmation_items:
        _add_reason(reasons, BlockReason.MISSING_MANUAL_CONFIRMATION_ITEMS)
    if not implementation_readiness_blockers:
        _add_reason(reasons, BlockReason.MISSING_IMPLEMENTATION_BLOCKERS)
    if prompt_truncation_risk_reviewed is not True:
        _add_reason(reasons, BlockReason.PROMPT_TRUNCATION_RISK_NOT_REVIEWED)
    if step5u_test_coverage_reviewed is not True:
        _add_reason(reasons, BlockReason.STEP5U_TEST_COVERAGE_NOT_REVIEWED)
    if step5u_docs_reviewed is not True:
        _add_reason(reasons, BlockReason.STEP5U_DOCS_NOT_REVIEWED)
    return tuple(reasons)


def _build_check_results(
    *,
    pre_implementation_audit: LiveOrderRealApprovalPreImplementationAudit | None,
    residual_risks: tuple[str, ...],
    manual_confirmation_items: tuple[str, ...],
    implementation_readiness_blockers: tuple[str, ...],
    prompt_truncation_risk_reviewed: bool,
    step5u_test_coverage_reviewed: bool,
    step5u_docs_reviewed: bool,
    post_attempt_limit: int,
    retry_allowed: bool,
    loop_allowed: bool,
    add_order_allowed: bool,
    change_order_allowed: bool,
    cancel_order_allowed: bool,
    close_order_allowed: bool,
    post_reconciliation_required: bool,
) -> tuple[LiveOrderRealApprovalImplementationReadinessCheckResult, ...]:
    audit_ready = (
        isinstance(pre_implementation_audit, LiveOrderRealApprovalPreImplementationAudit)
        and pre_implementation_audit.audit_status
        is AuditStatus.READY_FOR_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_REVIEW
        and pre_implementation_audit.audit_ready is True
        and pre_implementation_audit.eligible_for_future_real_approval_gate_implementation_review
        is True
    )
    allowed_false = (
        isinstance(pre_implementation_audit, LiveOrderRealApprovalPreImplementationAudit)
        and pre_implementation_audit.allowed_for_live is False
    )
    no_api_calls = (
        isinstance(pre_implementation_audit, LiveOrderRealApprovalPreImplementationAudit)
        and pre_implementation_audit.live_order_once_called is False
        and pre_implementation_audit.private_api_called is False
        and pre_implementation_audit.broker_called is False
        and pre_implementation_audit.read_only_api_called is False
        and pre_implementation_audit.public_api_called is False
    )
    post_not_executed = (
        isinstance(pre_implementation_audit, LiveOrderRealApprovalPreImplementationAudit)
        and pre_implementation_audit.post_executed is False
    )
    one_shot_constraints = (
        post_attempt_limit == 1
        and retry_allowed is False
        and loop_allowed is False
        and add_order_allowed is False
        and change_order_allowed is False
        and cancel_order_allowed is False
        and close_order_allowed is False
        and post_reconciliation_required is True
    )
    display_complete = (
        isinstance(pre_implementation_audit, LiveOrderRealApprovalPreImplementationAudit)
        and _display_forbidden_fields_are_complete(
            pre_implementation_audit.display_forbidden_fields
        )
    )
    ack_present = (
        isinstance(pre_implementation_audit, LiveOrderRealApprovalPreImplementationAudit)
        and not (
            set(APPROVAL_ACK_TOKENS) - set(pre_implementation_audit.required_ack_tokens)
        )
    )
    return (
        _check("pre_implementation_audit_ready", audit_ready, _bool_text(audit_ready), "true"),
        _check(
            "prompt_truncation_risk_reviewed",
            prompt_truncation_risk_reviewed is True,
            _bool_text(prompt_truncation_risk_reviewed is True),
            "true",
        ),
        _check(
            "step5u_test_coverage_reviewed",
            step5u_test_coverage_reviewed is True,
            _bool_text(step5u_test_coverage_reviewed is True),
            "true",
        ),
        _check(
            "step5u_docs_reviewed",
            step5u_docs_reviewed is True,
            _bool_text(step5u_docs_reviewed is True),
            "true",
        ),
        _check("allowed_for_live_false", allowed_false, _bool_text(allowed_false), "true"),
        _audit_bool_check(
            pre_implementation_audit,
            "approval_gate_not_issued",
            "approval_gate_issued",
            False,
        ),
        _audit_bool_check(
            pre_implementation_audit,
            "approval_id_not_generated",
            "approval_id_generated",
            False,
        ),
        _audit_bool_check(
            pre_implementation_audit,
            "approval_command_not_generated",
            "approval_command_generated",
            False,
        ),
        _audit_bool_check(
            pre_implementation_audit,
            "approval_command_not_copyable",
            "approval_command_copyable",
            False,
        ),
        _audit_bool_check(
            pre_implementation_audit,
            "approval_id_generation_deferred",
            "approval_id_generation_deferred_to_future_step",
            True,
        ),
        _audit_bool_check(
            pre_implementation_audit,
            "approval_command_generation_deferred",
            "approval_command_generation_deferred_to_future_step",
            True,
        ),
        _check(
            "ttl_seconds_300",
            _attr(pre_implementation_audit, "ttl_seconds") == APPROVAL_GATE_TTL_SECONDS,
            _attr(pre_implementation_audit, "ttl_seconds", "missing"),
            str(APPROVAL_GATE_TTL_SECONDS),
        ),
        _audit_bool_check(
            pre_implementation_audit,
            "exact_match_required",
            "exact_match_required",
            True,
        ),
        _audit_bool_check(
            pre_implementation_audit,
            "same_session_required",
            "same_session_required",
            True,
        ),
        _check(
            "required_ack_tokens_present",
            ack_present,
            _ack_count_text(pre_implementation_audit),
            str(len(APPROVAL_ACK_TOKENS)),
        ),
        _check(
            "display_forbidden_fields_include_secrets_raw_ids_real_commands",
            display_complete,
            _bool_text(display_complete),
            "true",
        ),
        _check(
            "no_api_broker_live_order_once_called",
            no_api_calls,
            _bool_text(no_api_calls),
            "true",
        ),
        _check(
            "post_not_executed",
            post_not_executed,
            _bool_text(post_not_executed),
            "true",
        ),
        _check(
            "one_shot_constraints_preserved",
            one_shot_constraints,
            _bool_text(one_shot_constraints),
            "true",
        ),
        _check(
            "residual_risks_present",
            bool(residual_risks),
            str(len(residual_risks)),
            "non-empty",
        ),
        _check(
            "manual_confirmation_items_present",
            bool(manual_confirmation_items),
            str(len(manual_confirmation_items)),
            "non-empty",
        ),
        _check(
            "implementation_blockers_present",
            bool(implementation_readiness_blockers),
            str(len(implementation_readiness_blockers)),
            "non-empty",
        ),
        _check(
            "future_explicit_user_instruction_required",
            "future explicit user instruction required"
            in implementation_readiness_blockers,
            _bool_text(
                "future explicit user instruction required"
                in implementation_readiness_blockers
            ),
            "true",
        ),
    )


def _build_sections(
    *,
    check_results: tuple[LiveOrderRealApprovalImplementationReadinessCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
    residual_risks: tuple[str, ...],
    manual_confirmation_items: tuple[str, ...],
    implementation_blockers: tuple[str, ...],
    implementation_readiness_blockers: tuple[str, ...],
) -> tuple[LiveOrderRealApprovalImplementationReadinessSection, ...]:
    blocked_text = ", ".join(blocked_reasons) if blocked_reasons else "none"
    failed_checks = tuple(check.name for check in check_results if not check.passed)
    failed_text = ", ".join(failed_checks) if failed_checks else "none"
    return (
        LiveOrderRealApprovalImplementationReadinessSection(
            section_id="real_artifact_boundary",
            title="Real Artifact Boundary",
            lines=(
                "approval_gate_issued: False",
                "approval_id_generated: False",
                "approval_command_generated: False",
                "approval_command_copyable: False",
                "approval_id_generation_deferred_to_future_step: True",
                "approval_command_generation_deferred_to_future_step: True",
            ),
        ),
        LiveOrderRealApprovalImplementationReadinessSection(
            section_id="implementation_readiness_boundary",
            title="Implementation Readiness Boundary",
            lines=(
                "future_explicit_user_instruction_required: True",
                f"residual_risks_count: {len(residual_risks)}",
                f"manual_confirmation_items_count: {len(manual_confirmation_items)}",
                f"step5u_implementation_blockers_count: {len(implementation_blockers)}",
                f"readiness_blockers_count: {len(implementation_readiness_blockers)}",
            ),
        ),
        LiveOrderRealApprovalImplementationReadinessSection(
            section_id="one_shot_no_api_boundary",
            title="One-shot and No API Boundary",
            lines=(
                "post_attempt_limit: 1",
                "post_executed: False",
                "live_order_once_called: False",
                "private_api_called: False",
                "broker_called: False",
                "read_only_api_called: False",
                "public_api_called: False",
                "retry_loop_add_change_cancel_close_allowed: False",
            ),
        ),
        LiveOrderRealApprovalImplementationReadinessSection(
            section_id="decision",
            title="Decision",
            lines=(
                f"failed_checks: {failed_text}",
                f"blocked_reasons: {blocked_text}",
                f"recommended_next_step: {recommended_next_step}",
            ),
        ),
    )


def _validate_review(review: LiveOrderRealApprovalImplementationReadinessReview) -> None:
    for field_name in (
        "review_id",
        "audit_id",
        "package_id",
        "pre_approval_preflight_decision_id",
        "snapshot_id",
        "plan_id",
        "checkpoint_id",
        "chain_id",
        "symbol",
        "side",
        "execution_type",
        "summary",
        "recommended_next_step",
    ):
        _require_non_empty(field_name, getattr(review, field_name))
    if not isinstance(review.created_at, datetime):
        raise LiveVerificationValidationError("created_at must be datetime")
    if type(review.readiness_ready) is not bool:
        raise LiveVerificationValidationError("readiness_ready must be bool")
    if (
        type(review.eligible_for_future_real_approval_gate_implementation_step)
        is not bool
    ):
        raise LiveVerificationValidationError("readiness eligibility must be bool")
    for field_name, expected in (
        ("allowed_for_live", False),
        ("requires_human_approval", True),
        ("explicit_user_confirmation_required", True),
        ("approval_gate_required", True),
        ("approval_gate_planned", True),
        ("approval_gate_issued", False),
        ("approval_id_generation_planned", True),
        ("approval_id_generation_deferred_to_future_step", True),
        ("approval_id_generated", False),
        ("approval_command_generation_planned", True),
        ("approval_command_generation_deferred_to_future_step", True),
        ("approval_command_generated", False),
        ("approval_command_template_only", True),
        ("approval_command_copyable", False),
        ("fresh_preflight_before_gate_required", True),
        ("post_approval_final_dynamic_preflight_required", True),
        ("one_shot_post_separate_step_required", True),
        ("post_reconciliation_separate_step_required", True),
        ("final_report_separate_step_required", True),
        ("dry_run_only", True),
        ("exact_match_required", True),
        ("same_session_required", True),
        ("post_executed", False),
        ("live_order_once_called", False),
        ("private_api_called", False),
        ("broker_called", False),
        ("read_only_api_called", False),
        ("public_api_called", False),
        ("retry_allowed", False),
        ("loop_allowed", False),
        ("add_order_allowed", False),
        ("change_order_allowed", False),
        ("cancel_order_allowed", False),
        ("close_order_allowed", False),
        ("post_reconciliation_required", True),
        ("prompt_truncation_risk_reviewed", True),
        ("step5u_test_coverage_reviewed", True),
        ("step5u_docs_reviewed", True),
    ):
        if getattr(review, field_name) is not expected:
            raise LiveVerificationValidationError(f"{field_name} must be {expected}")
    if review.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("ttl_seconds must be 300")
    if review.required_ack_tokens != APPROVAL_ACK_TOKENS:
        raise LiveVerificationValidationError("required_ack_tokens mismatch")
    if review.post_attempt_limit != 1:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if review.readiness_ready and (
        review.readiness_status
        is not ReadinessStatus.READY_FOR_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW
    ):
        raise LiveVerificationValidationError("ready readiness status mismatch")
    if review.readiness_ready and review.blocked_reasons:
        raise LiveVerificationValidationError("ready review cannot have blockers")
    if not review.display_allowed_fields:
        raise LiveVerificationValidationError("review requires display allowed fields")
    if not review.display_forbidden_fields:
        raise LiveVerificationValidationError("review requires display forbidden fields")
    if review.readiness_ready and not review.residual_risks:
        raise LiveVerificationValidationError("review requires residual risks")
    if review.readiness_ready and not review.manual_confirmation_items:
        raise LiveVerificationValidationError("review requires manual confirmation items")
    if review.readiness_ready and not review.implementation_blockers:
        raise LiveVerificationValidationError("review requires implementation blockers")
    if review.readiness_ready and not review.implementation_readiness_blockers:
        raise LiveVerificationValidationError(
            "review requires implementation readiness blockers"
        )
    if not review.check_results:
        raise LiveVerificationValidationError("review requires check_results")
    if not review.sections:
        raise LiveVerificationValidationError("review requires sections")


def _display_forbidden_fields_are_complete(fields: tuple[str, ...]) -> bool:
    joined = " ".join(fields).lower()
    required_markers = (
        "api key",
        "secret",
        "signature value",
        "headers",
        "raw request",
        "raw response",
        "order id",
        "execution id",
        "position id",
        "clientorderid",
        "real approval_id",
        "real approval command",
        "copyable approval command",
    )
    return all(marker in joined for marker in required_markers)


def _audit_bool_check(
    audit: LiveOrderRealApprovalPreImplementationAudit | None,
    name: str,
    field_name: str,
    expected: bool,
) -> LiveOrderRealApprovalImplementationReadinessCheckResult:
    actual = _attr(audit, field_name, "missing")
    passed = actual is expected
    return _check(name, passed, _bool_text(passed), "true")


def _check(
    name: str,
    passed: bool,
    sanitized_value: object,
    expected: str,
) -> LiveOrderRealApprovalImplementationReadinessCheckResult:
    return LiveOrderRealApprovalImplementationReadinessCheckResult(
        name=name,
        passed=passed,
        reason="pass" if passed else "blocked",
        sanitized_value=str(sanitized_value),
        expected=expected,
    )


def _add_reason(
    reasons: list[str],
    reason: LiveOrderRealApprovalImplementationReadinessBlockReason,
) -> None:
    value = reason.value
    if value not in reasons:
        reasons.append(value)


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _tuple_from(
    obj: object | None,
    attr_name: str,
    default: tuple[str, ...] = ("missing",),
) -> tuple[str, ...]:
    value = getattr(obj, attr_name, default)
    if not isinstance(value, tuple) or not value:
        return default
    return tuple(str(item) for item in value)


def _text_from(
    obj: object | None,
    attr_name: str,
    default: str = "missing",
) -> str:
    value = getattr(obj, attr_name, default)
    if isinstance(value, Enum):
        return value.value
    if value is None or value == "":
        return default
    return str(value)


def _int_from(obj: object | None, attr_name: str, default: int = 0) -> int:
    value = getattr(obj, attr_name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _attr(obj: object | None, attr_name: str, default: object = None) -> object:
    return getattr(obj, attr_name, default)


def _ack_count_text(
    audit: LiveOrderRealApprovalPreImplementationAudit | None,
) -> str:
    if not isinstance(audit, LiveOrderRealApprovalPreImplementationAudit):
        return "missing"
    return str(len(audit.required_ack_tokens))


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{name} must be non-empty")


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
