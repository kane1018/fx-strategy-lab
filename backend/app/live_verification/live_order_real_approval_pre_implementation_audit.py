"""Real approval gate pre-implementation safety audit for Step 5U."""

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
from app.live_verification.live_order_real_approval_gate_generation_package import (
    LiveOrderRealApprovalGateGenerationPackage,
    LiveOrderRealApprovalGateGenerationPackageStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

PackageStatus = LiveOrderRealApprovalGateGenerationPackageStatus

LIVE_ORDER_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_ID_PREFIX = "LORAPIA-"

DEFAULT_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_RESIDUAL_RISKS = (
    "real approval gate implementation will be the first step to create real approval artifacts",
    "real API fresh preflight has not been executed in this step",
    "market and account state can change before any future POST",
    "exact match, TTL, and same session must be revalidated in the future implementation",
    "result_unknown must stop without extra orders",
    "raw response and real IDs must remain hidden in future implementation",
)

DEFAULT_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_MANUAL_CONFIRMATION_ITEMS = (
    "user explicitly requested a future real approval gate implementation step",
    "user understands real-money risk",
    "user understands post_attempt_limit=1",
    "user understands retry, loop, add, change, cancel, and close are forbidden",
    "user understands unknown means stop",
    "user understands final dynamic preflight remains required after approval",
)

DEFAULT_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_IMPLEMENTATION_BLOCKERS = (
    "explicit future request missing",
    "fresh preflight implementation not yet executed",
    "real approval_id generation not implemented",
    "real approval command generation not implemented",
    "exact match runtime validation not implemented",
    "post-approval final dynamic preflight not executed",
    "one-shot POST execution is not implemented in this step",
)

REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_DISPLAY_ALLOWED_FIELDS = (
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
    "size",
    "executionType",
    "audit_status",
    "audit_ready",
    "eligible_for_future_real_approval_gate_implementation_review",
    "allowed_for_live=false",
    "approval_id_generation_deferred_to_future_step",
    "approval_command_generation_deferred_to_future_step",
    "ttl_seconds",
    "exact_match_required",
    "same_session_required",
    "required_ack_tokens",
    "display_allowed_fields",
    "display_forbidden_fields",
    "residual_risks",
    "manual_confirmation_items",
    "implementation_blockers",
    "go_conditions",
    "no_go_conditions",
    "stop_conditions",
    "check_results",
    "blocked_reasons",
    "recommended_next_step",
)

REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_DISPLAY_FORBIDDEN_FIELDS = (
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
)


class LiveOrderRealApprovalPreImplementationAuditStatus(str, Enum):
    READY_FOR_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_REVIEW = (
        "READY_FOR_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_REVIEW"
    )
    BLOCKED_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT = (
        "BLOCKED_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT"
    )


AuditStatus = LiveOrderRealApprovalPreImplementationAuditStatus


class LiveOrderRealApprovalPreImplementationAuditBlockReason(str, Enum):
    MISSING_GENERATION_PACKAGE = "missing_generation_package"
    GENERATION_PACKAGE_NOT_READY = "generation_package_not_ready"
    GENERATION_PACKAGE_NOT_ELIGIBLE = "generation_package_not_eligible"
    PACKAGE_ALLOWS_LIVE = "package_allows_live"
    PACKAGE_NOT_DRY_RUN = "package_not_dry_run"
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


@dataclass(frozen=True)
class LiveOrderRealApprovalPreImplementationAuditCheckResult:
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
class LiveOrderRealApprovalPreImplementationAuditSection:
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
class LiveOrderRealApprovalPreImplementationAudit:
    audit_id: str
    created_at: datetime
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
    audit_status: LiveOrderRealApprovalPreImplementationAuditStatus
    audit_ready: bool
    eligible_for_future_real_approval_gate_implementation_review: bool
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
    display_allowed_fields: tuple[str, ...]
    display_forbidden_fields: tuple[str, ...]
    residual_risks: tuple[str, ...]
    manual_confirmation_items: tuple[str, ...]
    implementation_blockers: tuple[str, ...]
    go_conditions: tuple[str, ...]
    no_go_conditions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    check_results: tuple[LiveOrderRealApprovalPreImplementationAuditCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApprovalPreImplementationAuditSection, ...]

    def __post_init__(self) -> None:
        _validate_audit(self)


@dataclass(frozen=True)
class LiveOrderRealApprovalPreImplementationAuditBuildResult:
    audit: LiveOrderRealApprovalPreImplementationAudit
    audit_id: str
    audit_status: LiveOrderRealApprovalPreImplementationAuditStatus
    audit_ready: bool
    eligible_for_future_real_approval_gate_implementation_review: bool
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
        if self.audit.audit_id != self.audit_id:
            raise LiveVerificationValidationError("audit_id mismatch")
        if self.audit.audit_status is not self.audit_status:
            raise LiveVerificationValidationError("audit_status mismatch")
        if self.audit.audit_ready is not self.audit_ready:
            raise LiveVerificationValidationError("audit_ready mismatch")
        if (
            self.audit.eligible_for_future_real_approval_gate_implementation_review
            is not self.eligible_for_future_real_approval_gate_implementation_review
        ):
            raise LiveVerificationValidationError("audit eligibility mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("Step 5U never allows live execution")
        if self.approval_gate_issued is not False:
            raise LiveVerificationValidationError("Step 5U never issues approval gate")
        if self.approval_id_generated is not False:
            raise LiveVerificationValidationError("Step 5U never generates approval id")
        if self.approval_command_generated is not False:
            raise LiveVerificationValidationError(
                "Step 5U never generates approval command"
            )
        if self.approval_command_copyable is not False:
            raise LiveVerificationValidationError("Step 5U never creates copyable command")
        if self.post_executed is not False:
            raise LiveVerificationValidationError("Step 5U never executes post")
        if self.live_order_once_called is not False:
            raise LiveVerificationValidationError("Step 5U never calls live_order_once")
        if self.audit.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.audit.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_approval_pre_implementation_audit(
    *,
    generation_package: LiveOrderRealApprovalGateGenerationPackage | None,
    created_at: datetime | None = None,
    residual_risks: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_RESIDUAL_RISKS,
    manual_confirmation_items: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_MANUAL_CONFIRMATION_ITEMS,
    implementation_blockers: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_IMPLEMENTATION_BLOCKERS,
    post_attempt_limit: int = 1,
    retry_allowed: bool = False,
    loop_allowed: bool = False,
    add_order_allowed: bool = False,
    change_order_allowed: bool = False,
    cancel_order_allowed: bool = False,
    close_order_allowed: bool = False,
    post_reconciliation_required: bool = True,
) -> LiveOrderRealApprovalPreImplementationAuditBuildResult:
    """Build a dry-run safety audit without generating real approval artifacts."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    blocked_reasons = _merge_reasons(
        _package_blocked_reasons(generation_package),
        _package_existing_reasons(generation_package),
        _audit_constraint_reasons(
            generation_package=generation_package,
            residual_risks=residual_risks,
            manual_confirmation_items=manual_confirmation_items,
            implementation_blockers=implementation_blockers,
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
        generation_package=generation_package,
        residual_risks=residual_risks,
        manual_confirmation_items=manual_confirmation_items,
        implementation_blockers=implementation_blockers,
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
        audit_status = AuditStatus.BLOCKED_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT
        audit_ready = False
        eligible = False
        recommended_next_step = "fix_generation_package_blockers_no_post"
        summary = (
            "blocked real approval pre-implementation safety audit; no approval "
            "gate, approval id, approval command, API call, or POST is allowed"
        )
    else:
        audit_status = (
            AuditStatus.READY_FOR_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_REVIEW
        )
        audit_ready = True
        eligible = True
        recommended_next_step = (
            "review_audit_then_wait_for_explicit_user_instruction_for_future_real_approval_gate_implementation_no_post"
        )
        summary = (
            "ready for real approval pre-implementation safety audit review only; "
            "live post remains disallowed"
        )

    audit_id = make_live_order_real_approval_pre_implementation_audit_id(
        package_id=_text_from(generation_package, "package_id"),
        candidate_id=_text_from(generation_package, "candidate_id"),
        created_at=created,
        audit_status=audit_status,
        blocked_reasons=blocked_reasons,
    )
    audit = LiveOrderRealApprovalPreImplementationAudit(
        audit_id=audit_id,
        created_at=created,
        package_id=_text_from(generation_package, "package_id"),
        pre_approval_preflight_decision_id=_text_from(
            generation_package,
            "pre_approval_preflight_decision_id",
        ),
        snapshot_id=_text_from(generation_package, "snapshot_id"),
        plan_id=_text_from(generation_package, "plan_id"),
        checkpoint_id=_text_from(generation_package, "checkpoint_id"),
        chain_id=_text_from(generation_package, "chain_id"),
        runbook_id=_text_from(generation_package, "runbook_id"),
        boundary_id=_text_from(generation_package, "boundary_id"),
        preflight_decision_id=_text_from(generation_package, "preflight_decision_id"),
        simulation_id=_text_from(generation_package, "simulation_id"),
        preview_id=_text_from(generation_package, "preview_id"),
        design_id=_text_from(generation_package, "design_id"),
        handoff_id=_text_from(generation_package, "handoff_id"),
        operator_review_id=_text_from(generation_package, "operator_review_id"),
        bundle_id=_text_from(generation_package, "bundle_id"),
        review_id=_text_from(generation_package, "review_id"),
        candidate_id=_text_from(generation_package, "candidate_id"),
        risk_decision_id=_text_from(generation_package, "risk_decision_id"),
        trace_id=_text_from(generation_package, "trace_id"),
        session_policy_decision_id=_text_from(
            generation_package,
            "session_policy_decision_id",
        ),
        source_signal_id=_text_from(generation_package, "source_signal_id"),
        source_type=_text_from(generation_package, "source_type"),
        strategy_name=_text_from(generation_package, "strategy_name"),
        symbol=_text_from(generation_package, "symbol"),
        side=_text_from(generation_package, "side"),
        size=_int_from(generation_package, "size"),
        execution_type=_text_from(generation_package, "execution_type"),
        audit_status=audit_status,
        audit_ready=audit_ready,
        eligible_for_future_real_approval_gate_implementation_review=eligible,
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
        display_allowed_fields=REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_DISPLAY_ALLOWED_FIELDS,
        display_forbidden_fields=(
            REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_DISPLAY_FORBIDDEN_FIELDS
        ),
        residual_risks=residual_risks,
        manual_confirmation_items=manual_confirmation_items,
        implementation_blockers=implementation_blockers,
        go_conditions=_tuple_from(generation_package, "go_conditions"),
        no_go_conditions=_tuple_from(generation_package, "no_go_conditions"),
        stop_conditions=_tuple_from(generation_package, "stop_conditions"),
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
        ),
    )
    return LiveOrderRealApprovalPreImplementationAuditBuildResult(
        audit=audit,
        audit_id=audit.audit_id,
        audit_status=audit.audit_status,
        audit_ready=audit.audit_ready,
        eligible_for_future_real_approval_gate_implementation_review=(
            audit.eligible_for_future_real_approval_gate_implementation_review
        ),
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_copyable=False,
        post_executed=False,
        live_order_once_called=False,
        blocked_reasons=audit.blocked_reasons,
        recommended_next_step=audit.recommended_next_step,
    )


def render_live_order_real_approval_pre_implementation_audit_markdown(
    audit: LiveOrderRealApprovalPreImplementationAudit,
) -> str:
    """Render a sanitized safety audit without real approval artifacts."""
    blocked_text = ", ".join(audit.blocked_reasons) or "none"
    ack_lines = "\n".join(f"- {token}" for token in audit.required_ack_tokens)
    residual_lines = "\n".join(f"- {risk}" for risk in audit.residual_risks)
    manual_lines = "\n".join(f"- {item}" for item in audit.manual_confirmation_items)
    blocker_lines = "\n".join(f"- {item}" for item in audit.implementation_blockers)
    go_lines = "\n".join(f"- {condition}" for condition in audit.go_conditions)
    no_go_lines = "\n".join(f"- {condition}" for condition in audit.no_go_conditions)
    stop_lines = "\n".join(f"- {condition}" for condition in audit.stop_conditions)
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in audit.check_results
    )
    return "\n".join(
        (
            "# Step 5U Real Approval Pre-implementation Safety Audit",
            "",
            "This real approval pre-implementation audit is dry-run only.",
            "This audit does not call read-only API.",
            "This audit does not call Private API.",
            "This audit does not call live_order_once.",
            "This audit does not execute HTTP POST.",
            "This audit does not issue a real approval gate.",
            "This audit does not generate a real approval_id.",
            "This audit does not generate a real approval command.",
            "This audit does not provide copyable approval text.",
            "This audit does not authorize live POST.",
            "allowed_for_live=false.",
            "",
            f"audit_id: {audit.audit_id}",
            f"package_id: {audit.package_id}",
            "pre_approval_preflight_decision_id: "
            f"{audit.pre_approval_preflight_decision_id}",
            f"snapshot_id: {audit.snapshot_id}",
            f"plan_id: {audit.plan_id}",
            f"checkpoint_id: {audit.checkpoint_id}",
            f"chain_id: {audit.chain_id}",
            f"runbook_id: {audit.runbook_id}",
            f"boundary_id: {audit.boundary_id}",
            f"preflight_decision_id: {audit.preflight_decision_id}",
            f"simulation_id: {audit.simulation_id}",
            f"preview_id: {audit.preview_id}",
            f"design_id: {audit.design_id}",
            f"handoff_id: {audit.handoff_id}",
            f"operator_review_id: {audit.operator_review_id}",
            f"bundle_id: {audit.bundle_id}",
            f"review_id: {audit.review_id}",
            f"candidate_id: {audit.candidate_id}",
            f"risk_decision_id: {audit.risk_decision_id}",
            f"trace_id: {audit.trace_id}",
            f"session_policy_decision_id: {audit.session_policy_decision_id}",
            f"source_signal_id: {audit.source_signal_id}",
            f"source_type: {audit.source_type}",
            f"strategy_name: {audit.strategy_name}",
            f"symbol: {audit.symbol}",
            f"side: {audit.side}",
            f"size: {audit.size}",
            f"executionType: {audit.execution_type}",
            f"audit_status: {audit.audit_status.value}",
            f"audit_ready: {audit.audit_ready}",
            "eligible_for_future_real_approval_gate_implementation_review: "
            f"{audit.eligible_for_future_real_approval_gate_implementation_review}",
            f"allowed_for_live: {audit.allowed_for_live}",
            "approval_id_generation_deferred_to_future_step: "
            f"{audit.approval_id_generation_deferred_to_future_step}",
            "approval_command_generation_deferred_to_future_step: "
            f"{audit.approval_command_generation_deferred_to_future_step}",
            f"ttl_seconds: {audit.ttl_seconds}",
            f"exact_match_required: {audit.exact_match_required}",
            f"same_session_required: {audit.same_session_required}",
            f"post_attempt_limit: {audit.post_attempt_limit}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {audit.recommended_next_step}",
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
            "## Implementation Blockers",
            blocker_lines,
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


def make_live_order_real_approval_pre_implementation_audit_id(
    *,
    package_id: str,
    candidate_id: str,
    created_at: datetime,
    audit_status: LiveOrderRealApprovalPreImplementationAuditStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "audit_status": audit_status.value,
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": _ensure_aware(created_at).isoformat(),
        "package_id": package_id,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_ID_PREFIX}{digest}"


def _package_blocked_reasons(
    package: LiveOrderRealApprovalGateGenerationPackage | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(package, LiveOrderRealApprovalGateGenerationPackage):
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.MISSING_GENERATION_PACKAGE,
        )
        return tuple(reasons)
    if (
        package.package_status
        is not PackageStatus.READY_FOR_REAL_APPROVAL_GATE_GENERATION_PACKAGE_REVIEW
        or package.package_ready is not True
    ):
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.GENERATION_PACKAGE_NOT_READY,
        )
    if package.eligible_for_future_real_approval_gate_generation is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.GENERATION_PACKAGE_NOT_ELIGIBLE,
        )
    if package.allowed_for_live is not False:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.PACKAGE_ALLOWS_LIVE,
        )
    if package.dry_run_only is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.PACKAGE_NOT_DRY_RUN,
        )
    for field_value, reason in (
        (
            package.approval_gate_issued,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        ),
        (
            package.approval_id_generated,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            package.approval_command_generated,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            package.approval_command_copyable,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.APPROVAL_COMMAND_COPYABLE,
        ),
    ):
        if field_value is not False:
            _add_reason(reasons, reason)
    if package.approval_id_generation_deferred_to_future_step is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.APPROVAL_ID_GENERATION_NOT_DEFERRED,
        )
    if package.approval_command_generation_deferred_to_future_step is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.APPROVAL_COMMAND_GENERATION_NOT_DEFERRED,
        )
    if package.symbol != SUPPORTED_SYMBOL:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.UNSUPPORTED_SYMBOL,
        )
    if package.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.UNSUPPORTED_SIDE,
        )
    if package.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.UNSUPPORTED_SIZE,
        )
    if package.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        )
    return tuple(reasons)


def _package_existing_reasons(
    package: LiveOrderRealApprovalGateGenerationPackage | None,
) -> tuple[str, ...]:
    if not isinstance(package, LiveOrderRealApprovalGateGenerationPackage):
        return ()
    return tuple(package.blocked_reasons)


def _audit_constraint_reasons(
    *,
    generation_package: LiveOrderRealApprovalGateGenerationPackage | None,
    residual_risks: tuple[str, ...],
    manual_confirmation_items: tuple[str, ...],
    implementation_blockers: tuple[str, ...],
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
    if isinstance(generation_package, LiveOrderRealApprovalGateGenerationPackage):
        package = generation_package
        if package.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
            _add_reason(
                reasons,
                LiveOrderRealApprovalPreImplementationAuditBlockReason.INVALID_TTL_SECONDS,
            )
        if package.exact_match_required is not True:
            _add_reason(
                reasons,
                LiveOrderRealApprovalPreImplementationAuditBlockReason.EXACT_MATCH_NOT_REQUIRED,
            )
        if package.same_session_required is not True:
            _add_reason(
                reasons,
                LiveOrderRealApprovalPreImplementationAuditBlockReason.SAME_SESSION_NOT_REQUIRED,
            )
        if set(APPROVAL_ACK_TOKENS) - set(package.required_ack_tokens):
            _add_reason(
                reasons,
                LiveOrderRealApprovalPreImplementationAuditBlockReason.MISSING_ACK_TOKEN,
            )
        if not _display_forbidden_fields_are_complete(package.display_forbidden_fields):
            _add_reason(
                reasons,
                LiveOrderRealApprovalPreImplementationAuditBlockReason.DISPLAY_FORBIDDEN_FIELDS_INCOMPLETE,
            )
        for flag, reason in (
            (
                package.post_executed,
                LiveOrderRealApprovalPreImplementationAuditBlockReason.POST_ALREADY_EXECUTED,
            ),
            (
                package.live_order_once_called,
                LiveOrderRealApprovalPreImplementationAuditBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
            ),
            (
                package.private_api_called,
                LiveOrderRealApprovalPreImplementationAuditBlockReason.PRIVATE_API_ALREADY_CALLED,
            ),
            (
                package.broker_called,
                LiveOrderRealApprovalPreImplementationAuditBlockReason.BROKER_ALREADY_CALLED,
            ),
            (
                package.read_only_api_called,
                LiveOrderRealApprovalPreImplementationAuditBlockReason.READ_ONLY_API_ALREADY_CALLED,
            ),
            (
                package.public_api_called,
                LiveOrderRealApprovalPreImplementationAuditBlockReason.PUBLIC_API_ALREADY_CALLED,
            ),
        ):
            if flag is not False:
                _add_reason(reasons, reason)
    if post_attempt_limit != 1:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.INVALID_POST_ATTEMPT_LIMIT,
        )
    for flag, reason in (
        (
            retry_allowed,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.RETRY_ALLOWED,
        ),
        (
            loop_allowed,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.LOOP_ALLOWED,
        ),
        (
            add_order_allowed,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.ADD_ORDER_ALLOWED,
        ),
        (
            change_order_allowed,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.CHANGE_ORDER_ALLOWED,
        ),
        (
            cancel_order_allowed,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.CANCEL_ORDER_ALLOWED,
        ),
        (
            close_order_allowed,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.CLOSE_ORDER_ALLOWED,
        ),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    if post_reconciliation_required is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        )
    if not residual_risks:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.MISSING_RESIDUAL_RISKS,
        )
    if not manual_confirmation_items:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.MISSING_MANUAL_CONFIRMATION_ITEMS,
        )
    if not implementation_blockers:
        _add_reason(
            reasons,
            LiveOrderRealApprovalPreImplementationAuditBlockReason.MISSING_IMPLEMENTATION_BLOCKERS,
        )
    return tuple(reasons)


def _build_check_results(
    *,
    generation_package: LiveOrderRealApprovalGateGenerationPackage | None,
    residual_risks: tuple[str, ...],
    manual_confirmation_items: tuple[str, ...],
    implementation_blockers: tuple[str, ...],
    post_attempt_limit: int,
    retry_allowed: bool,
    loop_allowed: bool,
    add_order_allowed: bool,
    change_order_allowed: bool,
    cancel_order_allowed: bool,
    close_order_allowed: bool,
    post_reconciliation_required: bool,
) -> tuple[LiveOrderRealApprovalPreImplementationAuditCheckResult, ...]:
    package_ready = (
        isinstance(generation_package, LiveOrderRealApprovalGateGenerationPackage)
        and generation_package.package_status
        is PackageStatus.READY_FOR_REAL_APPROVAL_GATE_GENERATION_PACKAGE_REVIEW
        and generation_package.package_ready is True
        and generation_package.eligible_for_future_real_approval_gate_generation is True
    )
    allowed_false = (
        isinstance(generation_package, LiveOrderRealApprovalGateGenerationPackage)
        and generation_package.allowed_for_live is False
    )
    no_api_calls = (
        isinstance(generation_package, LiveOrderRealApprovalGateGenerationPackage)
        and generation_package.live_order_once_called is False
        and generation_package.private_api_called is False
        and generation_package.broker_called is False
        and generation_package.read_only_api_called is False
        and generation_package.public_api_called is False
    )
    post_not_executed = (
        isinstance(generation_package, LiveOrderRealApprovalGateGenerationPackage)
        and generation_package.post_executed is False
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
    return (
        _check("generation_package_ready", package_ready, _bool_text(package_ready), "true"),
        _check("allowed_for_live_false", allowed_false, _bool_text(allowed_false), "true"),
        _package_bool_check(
            generation_package,
            "approval_gate_not_issued",
            "approval_gate_issued",
            False,
        ),
        _package_bool_check(
            generation_package,
            "approval_id_not_generated",
            "approval_id_generated",
            False,
        ),
        _package_bool_check(
            generation_package,
            "approval_command_not_generated",
            "approval_command_generated",
            False,
        ),
        _package_bool_check(
            generation_package,
            "approval_command_not_copyable",
            "approval_command_copyable",
            False,
        ),
        _package_bool_check(
            generation_package,
            "approval_id_generation_deferred",
            "approval_id_generation_deferred_to_future_step",
            True,
        ),
        _package_bool_check(
            generation_package,
            "approval_command_generation_deferred",
            "approval_command_generation_deferred_to_future_step",
            True,
        ),
        _check(
            "ttl_seconds_300",
            _attr(generation_package, "ttl_seconds") == APPROVAL_GATE_TTL_SECONDS,
            _attr(generation_package, "ttl_seconds", "missing"),
            str(APPROVAL_GATE_TTL_SECONDS),
        ),
        _package_bool_check(
            generation_package,
            "exact_match_required",
            "exact_match_required",
            True,
        ),
        _package_bool_check(
            generation_package,
            "same_session_required",
            "same_session_required",
            True,
        ),
        _check(
            "required_ack_tokens_present",
            isinstance(generation_package, LiveOrderRealApprovalGateGenerationPackage)
            and not (set(APPROVAL_ACK_TOKENS) - set(generation_package.required_ack_tokens)),
            _ack_count_text(generation_package),
            str(len(APPROVAL_ACK_TOKENS)),
        ),
        _check(
            "display_forbidden_fields_include_secrets_raw_ids_real_commands",
            isinstance(generation_package, LiveOrderRealApprovalGateGenerationPackage)
            and _display_forbidden_fields_are_complete(
                generation_package.display_forbidden_fields
            ),
            _bool_text(
                isinstance(generation_package, LiveOrderRealApprovalGateGenerationPackage)
                and _display_forbidden_fields_are_complete(
                    generation_package.display_forbidden_fields
                )
            ),
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
            bool(implementation_blockers),
            str(len(implementation_blockers)),
            "non-empty",
        ),
    )


def _build_sections(
    *,
    check_results: tuple[LiveOrderRealApprovalPreImplementationAuditCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
    residual_risks: tuple[str, ...],
    manual_confirmation_items: tuple[str, ...],
    implementation_blockers: tuple[str, ...],
) -> tuple[LiveOrderRealApprovalPreImplementationAuditSection, ...]:
    blocked_text = ", ".join(blocked_reasons) if blocked_reasons else "none"
    failed_checks = tuple(check.name for check in check_results if not check.passed)
    failed_text = ", ".join(failed_checks) if failed_checks else "none"
    return (
        LiveOrderRealApprovalPreImplementationAuditSection(
            section_id="approval_artifact_boundary",
            title="Approval Artifact Boundary",
            lines=(
                "approval_gate_issued: False",
                "approval_id_generated: False",
                "approval_command_generated: False",
                "approval_command_copyable: False",
                "approval_id_generation_deferred_to_future_step: True",
                "approval_command_generation_deferred_to_future_step: True",
            ),
        ),
        LiveOrderRealApprovalPreImplementationAuditSection(
            section_id="one_shot_boundary",
            title="One-shot Boundary",
            lines=(
                "post_attempt_limit: 1",
                "post_executed: False",
                "live_order_once_called: False",
                "retry_allowed: False",
                "loop_allowed: False",
                "add/change/cancel/close allowed: False",
            ),
        ),
        LiveOrderRealApprovalPreImplementationAuditSection(
            section_id="review_material",
            title="Review Material",
            lines=(
                f"residual_risks_count: {len(residual_risks)}",
                f"manual_confirmation_items_count: {len(manual_confirmation_items)}",
                f"implementation_blockers_count: {len(implementation_blockers)}",
            ),
        ),
        LiveOrderRealApprovalPreImplementationAuditSection(
            section_id="decision",
            title="Decision",
            lines=(
                f"failed_checks: {failed_text}",
                f"blocked_reasons: {blocked_text}",
                f"recommended_next_step: {recommended_next_step}",
            ),
        ),
    )


def _validate_audit(audit: LiveOrderRealApprovalPreImplementationAudit) -> None:
    for field_name in (
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
        _require_non_empty(field_name, getattr(audit, field_name))
    if not isinstance(audit.created_at, datetime):
        raise LiveVerificationValidationError("created_at must be datetime")
    if type(audit.audit_ready) is not bool:
        raise LiveVerificationValidationError("audit_ready must be bool")
    if (
        type(audit.eligible_for_future_real_approval_gate_implementation_review)
        is not bool
    ):
        raise LiveVerificationValidationError("audit eligibility must be bool")
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
    ):
        if getattr(audit, field_name) is not expected:
            raise LiveVerificationValidationError(f"{field_name} must be {expected}")
    if audit.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("ttl_seconds must be 300")
    if audit.required_ack_tokens != APPROVAL_ACK_TOKENS:
        raise LiveVerificationValidationError("required_ack_tokens mismatch")
    if audit.post_attempt_limit != 1:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if audit.audit_ready and (
        audit.audit_status
        is not AuditStatus.READY_FOR_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_REVIEW
    ):
        raise LiveVerificationValidationError("ready audit status mismatch")
    if audit.audit_ready and audit.blocked_reasons:
        raise LiveVerificationValidationError("ready audit cannot have blockers")
    if not audit.display_allowed_fields:
        raise LiveVerificationValidationError("audit requires display allowed fields")
    if not audit.display_forbidden_fields:
        raise LiveVerificationValidationError("audit requires display forbidden fields")
    if not audit.check_results:
        raise LiveVerificationValidationError("audit requires check_results")
    if not audit.sections:
        raise LiveVerificationValidationError("audit requires sections")


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


def _package_bool_check(
    package: LiveOrderRealApprovalGateGenerationPackage | None,
    name: str,
    field_name: str,
    expected: bool,
) -> LiveOrderRealApprovalPreImplementationAuditCheckResult:
    actual = _attr(package, field_name, "missing")
    passed = actual is expected
    return _check(name, passed, _bool_text(passed), "true")


def _check(
    name: str,
    passed: bool,
    sanitized_value: object,
    expected: str,
) -> LiveOrderRealApprovalPreImplementationAuditCheckResult:
    return LiveOrderRealApprovalPreImplementationAuditCheckResult(
        name=name,
        passed=passed,
        reason="pass" if passed else "blocked",
        sanitized_value=str(sanitized_value),
        expected=expected,
    )


def _add_reason(
    reasons: list[str],
    reason: LiveOrderRealApprovalPreImplementationAuditBlockReason,
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
    package: LiveOrderRealApprovalGateGenerationPackage | None,
) -> str:
    if not isinstance(package, LiveOrderRealApprovalGateGenerationPackage):
        return "missing"
    return str(len(package.required_ack_tokens))


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{name} must be non-empty")


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
