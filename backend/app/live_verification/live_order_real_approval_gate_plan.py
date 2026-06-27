"""Real approval gate planning package dry-run model for Step 5R."""

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
from app.live_verification.live_order_one_shot_boundary import (
    ONE_SHOT_POST_ATTEMPT_LIMIT,
)
from app.live_verification.live_order_real_approval_readiness import (
    LiveOrderRealApprovalReadinessCheckpoint,
    LiveOrderRealApprovalReadinessStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_REAL_APPROVAL_GATE_PLAN_ID_PREFIX = "LORAGP-"

REQUIRED_REAL_APPROVAL_GATE_PLAN_PHASE_IDS = (
    "stop_and_request_explicit_user_instruction",
    "future_fresh_preflight_before_approval_gate",
    "future_real_approval_gate_generation",
    "future_approval_command_exact_match_validation",
    "future_post_approval_final_dynamic_preflight",
    "future_one_shot_post_boundary",
    "future_post_reconciliation",
    "future_final_report_and_stop",
)

DEFAULT_REAL_APPROVAL_GATE_PLAN_GO_CONDITIONS = (
    "readiness checkpoint ready",
    "explicit user instruction for future real approval gate step is required",
    "fresh preflight before gate is required",
    "approval_id generation happens only after fresh preflight in future separate step",
    "approval command generation happens only after fresh preflight in future separate step",
    "exact match required",
    "same session required",
    "TTL 300 seconds",
    "all ACK tokens required",
    "final dynamic preflight required after approval and before POST",
    "one-shot POST remains separate future step",
)

DEFAULT_REAL_APPROVAL_GATE_PLAN_NO_GO_CONDITIONS = (
    "readiness blocked",
    "no explicit user instruction",
    "stale or missing fresh preflight",
    "any approval artifact already generated",
    "any API/broker/live_order_once already called",
    "post already executed",
    "any mismatch in symbol/side/size/executionType",
    "spread/account/position/order/event/maintenance unknown",
    "raw response or real ID display/storage required",
    "retry/loop/add/change/cancel/close needed",
)

DEFAULT_REAL_APPROVAL_GATE_PLAN_STOP_CONDITIONS = (
    "user has not explicitly requested future real approval gate step",
    "fresh preflight cannot be performed safely",
    "approval expired",
    "exact match fails",
    "same session fails",
    "ACK token missing",
    "final dynamic preflight stale",
    "result_unknown",
    "reconciliation impossible",
    "any secret/raw response/ID exposure risk",
    "any need to exceed one POST attempt",
)

REAL_APPROVAL_GATE_PLAN_DISPLAY_ALLOWED_FIELDS = (
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
    "plan_status",
    "allowed_for_live=false",
    "ttl_seconds",
    "exact_match_required",
    "same_session_required",
    "required_ack_tokens",
    "go_conditions",
    "no_go_conditions",
    "stop_conditions",
    "recommended_next_step",
)

REAL_APPROVAL_GATE_PLAN_DISPLAY_FORBIDDEN_FIELDS = (
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


class LiveOrderRealApprovalGatePlanStatus(str, Enum):
    READY_FOR_REAL_APPROVAL_GATE_PLAN_REVIEW = (
        "READY_FOR_REAL_APPROVAL_GATE_PLAN_REVIEW"
    )
    BLOCKED_REAL_APPROVAL_GATE_PLAN = "BLOCKED_REAL_APPROVAL_GATE_PLAN"


class LiveOrderRealApprovalGatePlanBlockReason(str, Enum):
    MISSING_READINESS_CHECKPOINT = "missing_readiness_checkpoint"
    READINESS_NOT_READY = "readiness_not_ready"
    READINESS_NOT_PLANNING_ELIGIBLE = "readiness_not_planning_eligible"
    CHECKPOINT_ALLOWS_LIVE = "checkpoint_allows_live"
    CHECKPOINT_NOT_DRY_RUN = "checkpoint_not_dry_run"
    EXPLICIT_USER_CONFIRMATION_NOT_REQUIRED = (
        "explicit_user_confirmation_not_required"
    )
    REAL_APPROVAL_GATE_NOT_SEPARATE_STEP = "real_approval_gate_not_separate_step"
    FRESH_PREFLIGHT_BEFORE_GATE_NOT_REQUIRED = (
        "fresh_preflight_before_gate_not_required"
    )
    APPROVAL_ID_GENERATION_NOT_AFTER_FRESH_PREFLIGHT = (
        "approval_id_generation_not_after_fresh_preflight"
    )
    APPROVAL_COMMAND_GENERATION_NOT_AFTER_FRESH_PREFLIGHT = (
        "approval_command_generation_not_after_fresh_preflight"
    )
    POST_APPROVAL_FINAL_PREFLIGHT_NOT_REQUIRED = (
        "post_approval_final_preflight_not_required"
    )
    ONE_SHOT_POST_NOT_SEPARATE_STEP = "one_shot_post_not_separate_step"
    POST_RECONCILIATION_NOT_SEPARATE_STEP = "post_reconciliation_not_separate_step"
    FINAL_REPORT_NOT_SEPARATE_STEP = "final_report_not_separate_step"
    MISSING_APPROVAL_GATE_REQUIREMENT = "missing_approval_gate_requirement"
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
    INVALID_TTL_SECONDS = "invalid_ttl_seconds"
    EXACT_MATCH_NOT_REQUIRED = "exact_match_not_required"
    SAME_SESSION_NOT_REQUIRED = "same_session_not_required"
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
    MISSING_REQUIRED_ACK_TOKEN = "missing_required_ack_token"
    MISSING_REQUIRED_PHASE = "missing_required_phase"
    MISSING_GO_CONDITIONS = "missing_go_conditions"
    MISSING_NO_GO_CONDITIONS = "missing_no_go_conditions"
    MISSING_STOP_CONDITIONS = "missing_stop_conditions"


@dataclass(frozen=True)
class LiveOrderRealApprovalGatePlanPhase:
    phase_id: str
    title: str
    requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("phase_id", self.phase_id)
        _require_non_empty("phase title", self.title)
        if not self.requirements:
            raise LiveVerificationValidationError("phase requires requirements")
        for requirement in self.requirements:
            _require_non_empty("phase requirement", requirement)


@dataclass(frozen=True)
class LiveOrderRealApprovalGatePlanCheckResult:
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
class LiveOrderRealApprovalGatePlanSection:
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
class LiveOrderRealApprovalGatePlan:
    plan_id: str
    created_at: datetime
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
    plan_status: LiveOrderRealApprovalGatePlanStatus
    plan_ready: bool
    eligible_for_future_real_approval_gate_implementation: bool
    allowed_for_live: bool
    requires_human_approval: bool
    explicit_user_confirmation_required: bool
    real_approval_gate_separate_step_required: bool
    fresh_preflight_before_gate_required: bool
    approval_id_generation_after_fresh_preflight_required: bool
    approval_command_generation_after_fresh_preflight_required: bool
    post_approval_final_dynamic_preflight_required: bool
    one_shot_post_separate_step_required: bool
    post_reconciliation_separate_step_required: bool
    final_report_separate_step_required: bool
    approval_gate_required: bool
    approval_gate_planned: bool
    approval_gate_issued: bool
    approval_id_generation_planned: bool
    approval_id_generated: bool
    approval_command_generation_planned: bool
    approval_command_generated: bool
    approval_command_template_only: bool
    approval_command_copyable: bool
    ttl_seconds: int
    exact_match_required: bool
    same_session_required: bool
    required_ack_tokens: tuple[str, ...]
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
    display_allowed_fields: tuple[str, ...]
    display_forbidden_fields: tuple[str, ...]
    go_conditions: tuple[str, ...]
    no_go_conditions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    phases: tuple[LiveOrderRealApprovalGatePlanPhase, ...]
    check_results: tuple[LiveOrderRealApprovalGatePlanCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApprovalGatePlanSection, ...]

    def __post_init__(self) -> None:
        _validate_plan(self)


@dataclass(frozen=True)
class LiveOrderRealApprovalGatePlanBuildResult:
    plan: LiveOrderRealApprovalGatePlan
    plan_id: str
    plan_status: LiveOrderRealApprovalGatePlanStatus
    plan_ready: bool
    eligible_for_future_real_approval_gate_implementation: bool
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_copyable: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.plan.plan_id != self.plan_id:
            raise LiveVerificationValidationError("plan_id mismatch")
        if self.plan.plan_status is not self.plan_status:
            raise LiveVerificationValidationError("plan_status mismatch")
        if self.plan.plan_ready is not self.plan_ready:
            raise LiveVerificationValidationError("plan_ready mismatch")
        if (
            self.plan.eligible_for_future_real_approval_gate_implementation
            is not self.eligible_for_future_real_approval_gate_implementation
        ):
            raise LiveVerificationValidationError("implementation eligibility mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("Step 5R never allows live execution")
        if self.approval_gate_issued is not False:
            raise LiveVerificationValidationError("Step 5R never issues approval gate")
        if self.approval_id_generated is not False:
            raise LiveVerificationValidationError("Step 5R never generates approval id")
        if self.approval_command_generated is not False:
            raise LiveVerificationValidationError(
                "Step 5R never generates approval command"
            )
        if self.approval_command_copyable is not False:
            raise LiveVerificationValidationError("Step 5R never creates copyable command")
        if self.plan.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.plan.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_approval_gate_plan(
    *,
    real_approval_readiness_checkpoint: (
        LiveOrderRealApprovalReadinessCheckpoint | None
    ),
    created_at: datetime | None = None,
    explicit_user_confirmation_required: bool = True,
    real_approval_gate_separate_step_required: bool = True,
    fresh_preflight_before_gate_required: bool = True,
    approval_id_generation_after_fresh_preflight_required: bool = True,
    approval_command_generation_after_fresh_preflight_required: bool = True,
    post_approval_final_dynamic_preflight_required: bool = True,
    one_shot_post_separate_step_required: bool = True,
    post_reconciliation_separate_step_required: bool = True,
    final_report_separate_step_required: bool = True,
    approval_gate_required: bool = True,
    approval_gate_planned: bool = True,
    approval_gate_issued: bool = False,
    approval_id_generation_planned: bool = True,
    approval_id_generated: bool = False,
    approval_command_generation_planned: bool = True,
    approval_command_generated: bool = False,
    approval_command_template_only: bool = True,
    approval_command_copyable: bool = False,
    ttl_seconds: int = APPROVAL_GATE_TTL_SECONDS,
    exact_match_required: bool = True,
    same_session_required: bool = True,
    required_ack_tokens: tuple[str, ...] = APPROVAL_ACK_TOKENS,
    dry_run_only: bool = True,
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
    phases: tuple[
        LiveOrderRealApprovalGatePlanPhase,
        ...,
    ] | None = None,
    go_conditions: tuple[str, ...] = DEFAULT_REAL_APPROVAL_GATE_PLAN_GO_CONDITIONS,
    no_go_conditions: tuple[str, ...] = (
        DEFAULT_REAL_APPROVAL_GATE_PLAN_NO_GO_CONDITIONS
    ),
    stop_conditions: tuple[str, ...] = DEFAULT_REAL_APPROVAL_GATE_PLAN_STOP_CONDITIONS,
) -> LiveOrderRealApprovalGatePlanBuildResult:
    """Build a dry-run real approval gate planning package."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    default_plan_phases = build_default_real_approval_gate_plan_phases()
    input_plan_phases = phases if phases is not None else default_plan_phases
    output_go_conditions = go_conditions or DEFAULT_REAL_APPROVAL_GATE_PLAN_GO_CONDITIONS
    output_no_go_conditions = (
        no_go_conditions or DEFAULT_REAL_APPROVAL_GATE_PLAN_NO_GO_CONDITIONS
    )
    output_stop_conditions = (
        stop_conditions or DEFAULT_REAL_APPROVAL_GATE_PLAN_STOP_CONDITIONS
    )
    blocked_reasons = _plan_blocked_reasons(
        checkpoint=real_approval_readiness_checkpoint,
        explicit_user_confirmation_required=explicit_user_confirmation_required,
        real_approval_gate_separate_step_required=(
            real_approval_gate_separate_step_required
        ),
        fresh_preflight_before_gate_required=fresh_preflight_before_gate_required,
        approval_id_generation_after_fresh_preflight_required=(
            approval_id_generation_after_fresh_preflight_required
        ),
        approval_command_generation_after_fresh_preflight_required=(
            approval_command_generation_after_fresh_preflight_required
        ),
        post_approval_final_dynamic_preflight_required=(
            post_approval_final_dynamic_preflight_required
        ),
        one_shot_post_separate_step_required=one_shot_post_separate_step_required,
        post_reconciliation_separate_step_required=(
            post_reconciliation_separate_step_required
        ),
        final_report_separate_step_required=final_report_separate_step_required,
        approval_gate_required=approval_gate_required,
        approval_gate_issued=approval_gate_issued,
        approval_id_generated=approval_id_generated,
        approval_command_generated=approval_command_generated,
        approval_command_template_only=approval_command_template_only,
        approval_command_copyable=approval_command_copyable,
        ttl_seconds=ttl_seconds,
        exact_match_required=exact_match_required,
        same_session_required=same_session_required,
        required_ack_tokens=required_ack_tokens,
        dry_run_only=dry_run_only,
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
        phases=input_plan_phases,
        go_conditions=go_conditions,
        no_go_conditions=no_go_conditions,
        stop_conditions=stop_conditions,
    )
    check_results = _build_check_results(
        checkpoint=real_approval_readiness_checkpoint,
        explicit_user_confirmation_required=explicit_user_confirmation_required,
        real_approval_gate_separate_step_required=(
            real_approval_gate_separate_step_required
        ),
        fresh_preflight_before_gate_required=fresh_preflight_before_gate_required,
        approval_id_generation_after_fresh_preflight_required=(
            approval_id_generation_after_fresh_preflight_required
        ),
        approval_command_generation_after_fresh_preflight_required=(
            approval_command_generation_after_fresh_preflight_required
        ),
        post_approval_final_dynamic_preflight_required=(
            post_approval_final_dynamic_preflight_required
        ),
        approval_gate_issued=approval_gate_issued,
        approval_id_generated=approval_id_generated,
        approval_command_generated=approval_command_generated,
        approval_command_copyable=approval_command_copyable,
        ttl_seconds=ttl_seconds,
        exact_match_required=exact_match_required,
        same_session_required=same_session_required,
        required_ack_tokens=required_ack_tokens,
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
        plan_status = LiveOrderRealApprovalGatePlanStatus.BLOCKED_REAL_APPROVAL_GATE_PLAN
        plan_ready = False
        eligible = False
        recommended_next_step = (
            "fix_real_approval_readiness_blockers_no_post"
            if _checkpoint_is_blocked(real_approval_readiness_checkpoint)
            else "fix_real_approval_gate_plan_blockers_no_post"
        )
        summary = "blocked real approval gate plan; no approval gate is issued"
    else:
        plan_status = (
            LiveOrderRealApprovalGatePlanStatus.READY_FOR_REAL_APPROVAL_GATE_PLAN_REVIEW
        )
        plan_ready = True
        eligible = True
        recommended_next_step = (
            "stop_and_wait_for_explicit_user_instruction_for_future_real_approval_gate_step"
        )
        summary = "ready for real approval gate plan review only; no approval gate is issued"

    plan_id = make_live_order_real_approval_gate_plan_id(
        checkpoint_id=_text_from(real_approval_readiness_checkpoint, "checkpoint_id"),
        chain_id=_text_from(real_approval_readiness_checkpoint, "chain_id"),
        created_at=created,
        plan_status=plan_status,
        blocked_reasons=blocked_reasons,
    )
    plan = LiveOrderRealApprovalGatePlan(
        plan_id=plan_id,
        created_at=created,
        checkpoint_id=_text_from(real_approval_readiness_checkpoint, "checkpoint_id"),
        chain_id=_text_from(real_approval_readiness_checkpoint, "chain_id"),
        runbook_id=_text_from(real_approval_readiness_checkpoint, "runbook_id"),
        boundary_id=_text_from(real_approval_readiness_checkpoint, "boundary_id"),
        preflight_decision_id=_text_from(
            real_approval_readiness_checkpoint,
            "preflight_decision_id",
        ),
        simulation_id=_text_from(real_approval_readiness_checkpoint, "simulation_id"),
        preview_id=_text_from(real_approval_readiness_checkpoint, "preview_id"),
        design_id=_text_from(real_approval_readiness_checkpoint, "design_id"),
        handoff_id=_text_from(real_approval_readiness_checkpoint, "handoff_id"),
        operator_review_id=_text_from(
            real_approval_readiness_checkpoint,
            "operator_review_id",
        ),
        bundle_id=_text_from(real_approval_readiness_checkpoint, "bundle_id"),
        review_id=_text_from(real_approval_readiness_checkpoint, "review_id"),
        candidate_id=_text_from(real_approval_readiness_checkpoint, "candidate_id"),
        risk_decision_id=_text_from(
            real_approval_readiness_checkpoint,
            "risk_decision_id",
        ),
        trace_id=_text_from(real_approval_readiness_checkpoint, "trace_id"),
        session_policy_decision_id=_text_from(
            real_approval_readiness_checkpoint,
            "session_policy_decision_id",
        ),
        source_signal_id=_text_from(
            real_approval_readiness_checkpoint,
            "source_signal_id",
        ),
        source_type=_text_from(real_approval_readiness_checkpoint, "source_type"),
        strategy_name=_text_from(real_approval_readiness_checkpoint, "strategy_name"),
        symbol=_text_from(real_approval_readiness_checkpoint, "symbol"),
        side=_text_from(real_approval_readiness_checkpoint, "side"),
        size=_int_from(real_approval_readiness_checkpoint, "size"),
        execution_type=_text_from(
            real_approval_readiness_checkpoint,
            "execution_type",
        ),
        plan_status=plan_status,
        plan_ready=plan_ready,
        eligible_for_future_real_approval_gate_implementation=eligible,
        allowed_for_live=False,
        requires_human_approval=True,
        explicit_user_confirmation_required=True,
        real_approval_gate_separate_step_required=True,
        fresh_preflight_before_gate_required=True,
        approval_id_generation_after_fresh_preflight_required=True,
        approval_command_generation_after_fresh_preflight_required=True,
        post_approval_final_dynamic_preflight_required=True,
        one_shot_post_separate_step_required=True,
        post_reconciliation_separate_step_required=True,
        final_report_separate_step_required=True,
        approval_gate_required=True,
        approval_gate_planned=True,
        approval_gate_issued=False,
        approval_id_generation_planned=True,
        approval_id_generated=False,
        approval_command_generation_planned=True,
        approval_command_generated=False,
        approval_command_template_only=True,
        approval_command_copyable=False,
        ttl_seconds=APPROVAL_GATE_TTL_SECONDS,
        exact_match_required=True,
        same_session_required=True,
        required_ack_tokens=APPROVAL_ACK_TOKENS,
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
        display_allowed_fields=REAL_APPROVAL_GATE_PLAN_DISPLAY_ALLOWED_FIELDS,
        display_forbidden_fields=REAL_APPROVAL_GATE_PLAN_DISPLAY_FORBIDDEN_FIELDS,
        go_conditions=output_go_conditions,
        no_go_conditions=output_no_go_conditions,
        stop_conditions=output_stop_conditions,
        phases=default_plan_phases,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            phases=default_plan_phases,
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
        ),
    )
    return LiveOrderRealApprovalGatePlanBuildResult(
        plan=plan,
        plan_id=plan.plan_id,
        plan_status=plan.plan_status,
        plan_ready=plan.plan_ready,
        eligible_for_future_real_approval_gate_implementation=(
            plan.eligible_for_future_real_approval_gate_implementation
        ),
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_copyable=False,
        blocked_reasons=plan.blocked_reasons,
        recommended_next_step=plan.recommended_next_step,
    )


def build_default_real_approval_gate_plan_phases() -> tuple[
    LiveOrderRealApprovalGatePlanPhase,
    ...,
]:
    return (
        LiveOrderRealApprovalGatePlanPhase(
            phase_id="stop_and_request_explicit_user_instruction",
            title="Stop And Request Explicit User Instruction",
            requirements=(
                "Step 5R stops here",
                "future real approval gate step requires separate explicit user request",
            ),
        ),
        LiveOrderRealApprovalGatePlanPhase(
            phase_id="future_fresh_preflight_before_approval_gate",
            title="Future Fresh Preflight Before Approval Gate",
            requirements=(
                "future separate Step only",
                "approval id and command remain ungenerated before fresh preflight",
            ),
        ),
        LiveOrderRealApprovalGatePlanPhase(
            phase_id="future_real_approval_gate_generation",
            title="Future Real Approval Gate Generation",
            requirements=(
                "future separate Step only",
                "ttl_seconds=300",
                "same session and exact match required",
            ),
        ),
        LiveOrderRealApprovalGatePlanPhase(
            phase_id="future_approval_command_exact_match_validation",
            title="Future Approval Command Exact Match Validation",
            requirements=(
                "extra token, newline, extra whitespace, missing ACK, or TTL expiry stops",
            ),
        ),
        LiveOrderRealApprovalGatePlanPhase(
            phase_id="future_post_approval_final_dynamic_preflight",
            title="Future Post Approval Final Dynamic Preflight",
            requirements=(
                "recheck freshness after approval and before POST",
                "stale, unknown, wide spread, position/order present, or result_unknown stops",
            ),
        ),
        LiveOrderRealApprovalGatePlanPhase(
            phase_id="future_one_shot_post_boundary",
            title="Future One-shot POST Boundary",
            requirements=(
                "post_attempt_limit=1",
                "retry, loop, add, change, cancel, and close remain forbidden",
            ),
        ),
        LiveOrderRealApprovalGatePlanPhase(
            phase_id="future_post_reconciliation",
            title="Future Post Reconciliation",
            requirements=(
                "future read-only reconciliation only after future POST",
                "raw response and real IDs remain hidden",
            ),
        ),
        LiveOrderRealApprovalGatePlanPhase(
            phase_id="future_final_report_and_stop",
            title="Future Final Report And Stop",
            requirements=(
                "report success, failure, or unknown and stop",
                "unknown does not permit additional orders",
            ),
        ),
    )


def render_live_order_real_approval_gate_plan_markdown(
    plan: LiveOrderRealApprovalGatePlan,
) -> str:
    """Render a sanitized real approval gate plan."""
    blocked_text = ", ".join(plan.blocked_reasons) or "none"
    ack_lines = "\n".join(f"- {token}" for token in plan.required_ack_tokens)
    phase_lines = "\n".join(f"- {phase.phase_id}: {phase.title}" for phase in plan.phases)
    go_lines = "\n".join(f"- {condition}" for condition in plan.go_conditions)
    no_go_lines = "\n".join(f"- {condition}" for condition in plan.no_go_conditions)
    stop_lines = "\n".join(f"- {condition}" for condition in plan.stop_conditions)
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in plan.check_results
    )
    return "\n".join(
        (
            "# Step 5R Real Approval Gate Plan",
            "",
            "This real approval gate plan is dry-run only.",
            "This plan does not call read-only API.",
            "This plan does not call Private API.",
            "This plan does not call live_order_once.",
            "This plan does not execute HTTP POST.",
            "This plan does not issue a real approval gate.",
            "This plan does not generate a real approval_id.",
            "This plan does not generate a real approval command.",
            "This plan does not authorize live POST.",
            "allowed_for_live=false.",
            "",
            f"plan_id: {plan.plan_id}",
            f"checkpoint_id: {plan.checkpoint_id}",
            f"chain_id: {plan.chain_id}",
            f"runbook_id: {plan.runbook_id}",
            f"boundary_id: {plan.boundary_id}",
            f"preflight_decision_id: {plan.preflight_decision_id}",
            f"simulation_id: {plan.simulation_id}",
            f"preview_id: {plan.preview_id}",
            f"design_id: {plan.design_id}",
            f"handoff_id: {plan.handoff_id}",
            f"operator_review_id: {plan.operator_review_id}",
            f"bundle_id: {plan.bundle_id}",
            f"review_id: {plan.review_id}",
            f"candidate_id: {plan.candidate_id}",
            f"risk_decision_id: {plan.risk_decision_id}",
            f"trace_id: {plan.trace_id}",
            f"session_policy_decision_id: {plan.session_policy_decision_id}",
            f"source_signal_id: {plan.source_signal_id}",
            f"source_type: {plan.source_type}",
            f"strategy_name: {plan.strategy_name}",
            f"symbol: {plan.symbol}",
            f"side: {plan.side}",
            f"size: {plan.size}",
            f"executionType: {plan.execution_type}",
            f"plan_status: {plan.plan_status.value}",
            f"plan_ready: {plan.plan_ready}",
            "eligible_for_future_real_approval_gate_implementation: "
            f"{plan.eligible_for_future_real_approval_gate_implementation}",
            f"allowed_for_live: {plan.allowed_for_live}",
            f"explicit_user_confirmation_required: {plan.explicit_user_confirmation_required}",
            f"fresh_preflight_before_gate_required: {plan.fresh_preflight_before_gate_required}",
            "approval_id_generation_after_fresh_preflight_required: "
            f"{plan.approval_id_generation_after_fresh_preflight_required}",
            "approval_command_generation_after_fresh_preflight_required: "
            f"{plan.approval_command_generation_after_fresh_preflight_required}",
            "post_approval_final_dynamic_preflight_required: "
            f"{plan.post_approval_final_dynamic_preflight_required}",
            f"ttl_seconds: {plan.ttl_seconds}",
            f"exact_match_required: {plan.exact_match_required}",
            f"same_session_required: {plan.same_session_required}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {plan.recommended_next_step}",
            "",
            "## Required ACK Tokens",
            ack_lines,
            "",
            "## Phases",
            phase_lines,
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


def make_live_order_real_approval_gate_plan_id(
    *,
    checkpoint_id: str,
    chain_id: str,
    created_at: datetime,
    plan_status: LiveOrderRealApprovalGatePlanStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "checkpoint_id": checkpoint_id,
        "chain_id": chain_id,
        "created_at": _ensure_aware(created_at).isoformat(),
        "plan_status": plan_status.value,
        "blocked_reasons": list(blocked_reasons),
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_GATE_PLAN_ID_PREFIX}{digest}"


def _plan_blocked_reasons(
    *,
    checkpoint: LiveOrderRealApprovalReadinessCheckpoint | None,
    explicit_user_confirmation_required: bool,
    real_approval_gate_separate_step_required: bool,
    fresh_preflight_before_gate_required: bool,
    approval_id_generation_after_fresh_preflight_required: bool,
    approval_command_generation_after_fresh_preflight_required: bool,
    post_approval_final_dynamic_preflight_required: bool,
    one_shot_post_separate_step_required: bool,
    post_reconciliation_separate_step_required: bool,
    final_report_separate_step_required: bool,
    approval_gate_required: bool,
    approval_gate_issued: bool,
    approval_id_generated: bool,
    approval_command_generated: bool,
    approval_command_template_only: bool,
    approval_command_copyable: bool,
    ttl_seconds: int,
    exact_match_required: bool,
    same_session_required: bool,
    required_ack_tokens: tuple[str, ...],
    dry_run_only: bool,
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
    phases: tuple[LiveOrderRealApprovalGatePlanPhase, ...],
    go_conditions: tuple[str, ...],
    no_go_conditions: tuple[str, ...],
    stop_conditions: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if checkpoint is None:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_READINESS_CHECKPOINT,
        )
    else:
        _add_checkpoint_reasons(reasons, checkpoint)
        for reason in checkpoint.blocked_reasons:
            _add_external_reason(reasons, reason)
    for flag, reason in (
        (
            explicit_user_confirmation_required,
            LiveOrderRealApprovalGatePlanBlockReason.EXPLICIT_USER_CONFIRMATION_NOT_REQUIRED,
        ),
        (
            real_approval_gate_separate_step_required,
            LiveOrderRealApprovalGatePlanBlockReason.REAL_APPROVAL_GATE_NOT_SEPARATE_STEP,
        ),
        (
            fresh_preflight_before_gate_required,
            LiveOrderRealApprovalGatePlanBlockReason.FRESH_PREFLIGHT_BEFORE_GATE_NOT_REQUIRED,
        ),
        (
            approval_id_generation_after_fresh_preflight_required,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_ID_GENERATION_NOT_AFTER_FRESH_PREFLIGHT,
        ),
        (
            approval_command_generation_after_fresh_preflight_required,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_GENERATION_NOT_AFTER_FRESH_PREFLIGHT,
        ),
        (
            post_approval_final_dynamic_preflight_required,
            LiveOrderRealApprovalGatePlanBlockReason.POST_APPROVAL_FINAL_PREFLIGHT_NOT_REQUIRED,
        ),
        (
            one_shot_post_separate_step_required,
            LiveOrderRealApprovalGatePlanBlockReason.ONE_SHOT_POST_NOT_SEPARATE_STEP,
        ),
        (
            post_reconciliation_separate_step_required,
            LiveOrderRealApprovalGatePlanBlockReason.POST_RECONCILIATION_NOT_SEPARATE_STEP,
        ),
        (
            final_report_separate_step_required,
            LiveOrderRealApprovalGatePlanBlockReason.FINAL_REPORT_NOT_SEPARATE_STEP,
        ),
        (
            approval_gate_required,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        ),
        (
            dry_run_only,
            LiveOrderRealApprovalGatePlanBlockReason.CHECKPOINT_NOT_DRY_RUN,
        ),
    ):
        if flag is not True:
            _add_reason(reasons, reason)
    for flag, reason in (
        (
            approval_gate_issued,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        ),
        (
            approval_id_generated,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            approval_command_generated,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            post_executed,
            LiveOrderRealApprovalGatePlanBlockReason.POST_ALREADY_EXECUTED,
        ),
        (
            live_order_once_called,
            LiveOrderRealApprovalGatePlanBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        ),
        (
            private_api_called,
            LiveOrderRealApprovalGatePlanBlockReason.PRIVATE_API_ALREADY_CALLED,
        ),
        (broker_called, LiveOrderRealApprovalGatePlanBlockReason.BROKER_ALREADY_CALLED),
        (
            read_only_api_called,
            LiveOrderRealApprovalGatePlanBlockReason.READ_ONLY_API_ALREADY_CALLED,
        ),
        (retry_allowed, LiveOrderRealApprovalGatePlanBlockReason.RETRY_ALLOWED),
        (loop_allowed, LiveOrderRealApprovalGatePlanBlockReason.LOOP_ALLOWED),
        (add_order_allowed, LiveOrderRealApprovalGatePlanBlockReason.ADD_ORDER_ALLOWED),
        (
            change_order_allowed,
            LiveOrderRealApprovalGatePlanBlockReason.CHANGE_ORDER_ALLOWED,
        ),
        (
            cancel_order_allowed,
            LiveOrderRealApprovalGatePlanBlockReason.CANCEL_ORDER_ALLOWED,
        ),
        (
            close_order_allowed,
            LiveOrderRealApprovalGatePlanBlockReason.CLOSE_ORDER_ALLOWED,
        ),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    if approval_command_template_only is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_NOT_TEMPLATE_ONLY,
        )
    if approval_command_copyable is not False:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_COPYABLE,
        )
    if ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.INVALID_TTL_SECONDS,
        )
    if exact_match_required is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.EXACT_MATCH_NOT_REQUIRED,
        )
    if same_session_required is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.SAME_SESSION_NOT_REQUIRED,
        )
    if post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.INVALID_POST_ATTEMPT_LIMIT,
        )
    if post_reconciliation_required is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        )
    missing_ack = set(APPROVAL_ACK_TOKENS) - set(required_ack_tokens)
    if missing_ack:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_REQUIRED_ACK_TOKEN,
        )
    phase_ids = {phase.phase_id for phase in phases}
    if set(REQUIRED_REAL_APPROVAL_GATE_PLAN_PHASE_IDS) - phase_ids:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_REQUIRED_PHASE,
        )
    if not go_conditions:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_GO_CONDITIONS,
        )
    if not no_go_conditions:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_NO_GO_CONDITIONS,
        )
    if not stop_conditions:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_STOP_CONDITIONS,
        )
    return tuple(reasons)


def _add_checkpoint_reasons(
    reasons: list[str],
    checkpoint: LiveOrderRealApprovalReadinessCheckpoint,
) -> None:
    if (
        checkpoint.readiness_status
        is not LiveOrderRealApprovalReadinessStatus.READY_FOR_REAL_APPROVAL_READINESS_REVIEW
    ):
        _add_reason(reasons, LiveOrderRealApprovalGatePlanBlockReason.READINESS_NOT_READY)
    if checkpoint.readiness_ready is not True:
        _add_reason(reasons, LiveOrderRealApprovalGatePlanBlockReason.READINESS_NOT_READY)
    if checkpoint.eligible_for_future_real_approval_gate_planning is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGatePlanBlockReason.READINESS_NOT_PLANNING_ELIGIBLE,
        )
    for field_name, expected, reason in (
        (
            "allowed_for_live",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.CHECKPOINT_ALLOWS_LIVE,
        ),
        (
            "dry_run_only",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.CHECKPOINT_NOT_DRY_RUN,
        ),
        (
            "explicit_user_confirmation_required",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.EXPLICIT_USER_CONFIRMATION_NOT_REQUIRED,
        ),
        (
            "real_approval_gate_separate_step_required",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.REAL_APPROVAL_GATE_NOT_SEPARATE_STEP,
        ),
        (
            "fresh_preflight_separate_step_required",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.FRESH_PREFLIGHT_BEFORE_GATE_NOT_REQUIRED,
        ),
        (
            "one_shot_post_separate_step_required",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.ONE_SHOT_POST_NOT_SEPARATE_STEP,
        ),
        (
            "post_reconciliation_separate_step_required",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.POST_RECONCILIATION_NOT_SEPARATE_STEP,
        ),
        (
            "final_report_separate_step_required",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.FINAL_REPORT_NOT_SEPARATE_STEP,
        ),
        (
            "approval_gate_required",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        ),
        (
            "approval_gate_issued",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        ),
        (
            "approval_id_generated",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            "approval_command_generated",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            "approval_command_copyable",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.APPROVAL_COMMAND_COPYABLE,
        ),
        (
            "final_dynamic_preflight_required",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.POST_APPROVAL_FINAL_PREFLIGHT_NOT_REQUIRED,
        ),
        (
            "post_executed",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.POST_ALREADY_EXECUTED,
        ),
        (
            "live_order_once_called",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        ),
        (
            "private_api_called",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.PRIVATE_API_ALREADY_CALLED,
        ),
        (
            "broker_called",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.BROKER_ALREADY_CALLED,
        ),
        (
            "read_only_api_called",
            False,
            LiveOrderRealApprovalGatePlanBlockReason.READ_ONLY_API_ALREADY_CALLED,
        ),
        (
            "post_reconciliation_required",
            True,
            LiveOrderRealApprovalGatePlanBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        ),
    ):
        if getattr(checkpoint, field_name) is not expected:
            _add_reason(reasons, reason)
    if checkpoint.post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
        _add_reason(reasons, LiveOrderRealApprovalGatePlanBlockReason.INVALID_POST_ATTEMPT_LIMIT)
    for field_name, reason in (
        ("retry_allowed", LiveOrderRealApprovalGatePlanBlockReason.RETRY_ALLOWED),
        ("loop_allowed", LiveOrderRealApprovalGatePlanBlockReason.LOOP_ALLOWED),
        ("add_order_allowed", LiveOrderRealApprovalGatePlanBlockReason.ADD_ORDER_ALLOWED),
        ("change_order_allowed", LiveOrderRealApprovalGatePlanBlockReason.CHANGE_ORDER_ALLOWED),
        ("cancel_order_allowed", LiveOrderRealApprovalGatePlanBlockReason.CANCEL_ORDER_ALLOWED),
        ("close_order_allowed", LiveOrderRealApprovalGatePlanBlockReason.CLOSE_ORDER_ALLOWED),
    ):
        if getattr(checkpoint, field_name) is not False:
            _add_reason(reasons, reason)
    if checkpoint.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderRealApprovalGatePlanBlockReason.UNSUPPORTED_SYMBOL)
    if checkpoint.side not in (
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    ):
        _add_reason(reasons, LiveOrderRealApprovalGatePlanBlockReason.UNSUPPORTED_SIDE)
    if checkpoint.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderRealApprovalGatePlanBlockReason.UNSUPPORTED_SIZE)
    if checkpoint.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, LiveOrderRealApprovalGatePlanBlockReason.UNSUPPORTED_EXECUTION_TYPE)


def _build_check_results(
    *,
    checkpoint: LiveOrderRealApprovalReadinessCheckpoint | None,
    explicit_user_confirmation_required: bool,
    real_approval_gate_separate_step_required: bool,
    fresh_preflight_before_gate_required: bool,
    approval_id_generation_after_fresh_preflight_required: bool,
    approval_command_generation_after_fresh_preflight_required: bool,
    post_approval_final_dynamic_preflight_required: bool,
    approval_gate_issued: bool,
    approval_id_generated: bool,
    approval_command_generated: bool,
    approval_command_copyable: bool,
    ttl_seconds: int,
    exact_match_required: bool,
    same_session_required: bool,
    required_ack_tokens: tuple[str, ...],
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
) -> tuple[LiveOrderRealApprovalGatePlanCheckResult, ...]:
    checkpoint_ready = (
        checkpoint is not None
        and checkpoint.readiness_status
        is LiveOrderRealApprovalReadinessStatus.READY_FOR_REAL_APPROVAL_READINESS_REVIEW
        and checkpoint.readiness_ready is True
        and checkpoint.eligible_for_future_real_approval_gate_planning is True
    )
    allowed_false = checkpoint is not None and checkpoint.allowed_for_live is False
    approval_clear = (
        approval_gate_issued is False
        and approval_id_generated is False
        and approval_command_generated is False
        and approval_command_copyable is False
        and checkpoint is not None
        and checkpoint.approval_gate_issued is False
        and checkpoint.approval_id_generated is False
        and checkpoint.approval_command_generated is False
        and checkpoint.approval_command_copyable is False
    )
    no_api_calls = (
        live_order_once_called is False
        and private_api_called is False
        and broker_called is False
        and read_only_api_called is False
        and checkpoint is not None
        and checkpoint.live_order_once_called is False
        and checkpoint.private_api_called is False
        and checkpoint.broker_called is False
        and checkpoint.read_only_api_called is False
    )
    one_shot_ok = (
        post_attempt_limit == ONE_SHOT_POST_ATTEMPT_LIMIT
        and post_executed is False
        and retry_allowed is False
        and loop_allowed is False
        and add_order_allowed is False
        and change_order_allowed is False
        and cancel_order_allowed is False
        and close_order_allowed is False
        and post_reconciliation_required is True
    )
    return (
        _check(
            "readiness_checkpoint_ready",
            checkpoint_ready,
            _bool_text(checkpoint_ready),
            "true",
        ),
        _check("allowed_for_live_false", allowed_false, _bool_text(allowed_false), "true"),
        _check(
            "real_approval_gate_separate_step",
            real_approval_gate_separate_step_required is True,
            _bool_text(real_approval_gate_separate_step_required is True),
            "true",
        ),
        _check(
            "fresh_preflight_before_gate_required",
            fresh_preflight_before_gate_required is True,
            _bool_text(fresh_preflight_before_gate_required is True),
            "true",
        ),
        _check(
            "approval_id_generation_deferred",
            approval_id_generation_after_fresh_preflight_required is True,
            _bool_text(approval_id_generation_after_fresh_preflight_required is True),
            "after fresh preflight in future separate step",
        ),
        _check(
            "approval_command_generation_deferred",
            approval_command_generation_after_fresh_preflight_required is True,
            _bool_text(approval_command_generation_after_fresh_preflight_required is True),
            "after fresh preflight in future separate step",
        ),
        _check(
            "exact_match_required",
            exact_match_required is True,
            _bool_text(exact_match_required is True),
            "true",
        ),
        _check(
            "same_session_required",
            same_session_required is True,
            _bool_text(same_session_required is True),
            "true",
        ),
        _check(
            "ttl_300",
            ttl_seconds == APPROVAL_GATE_TTL_SECONDS,
            str(ttl_seconds),
            str(APPROVAL_GATE_TTL_SECONDS),
        ),
        _check(
            "required_ack_tokens_present",
            set(APPROVAL_ACK_TOKENS).issubset(set(required_ack_tokens)),
            str(len(required_ack_tokens)),
            str(len(APPROVAL_ACK_TOKENS)),
        ),
        _check(
            "final_dynamic_preflight_after_approval_required",
            post_approval_final_dynamic_preflight_required is True,
            _bool_text(post_approval_final_dynamic_preflight_required is True),
            "true",
        ),
        _check(
            "one_shot_constraints_preserved",
            one_shot_ok,
            _bool_text(one_shot_ok),
            "post_attempt_limit=1 and no retry/loop/order mutation",
        ),
        _check(
            "no_approval_artifacts_generated",
            approval_clear,
            _bool_text(approval_clear),
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
            post_executed is False and (checkpoint is None or checkpoint.post_executed is False),
            _bool_text(
                post_executed is False
                and (checkpoint is None or checkpoint.post_executed is False)
            ),
            "true",
        ),
    )


def _build_sections(
    *,
    phases: tuple[LiveOrderRealApprovalGatePlanPhase, ...],
    check_results: tuple[LiveOrderRealApprovalGatePlanCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
) -> tuple[LiveOrderRealApprovalGatePlanSection, ...]:
    failed_checks = tuple(check.name for check in check_results if not check.passed)
    return (
        LiveOrderRealApprovalGatePlanSection(
            section_id="phases",
            title="Approval Gate Planning Sequence",
            lines=tuple(phase.phase_id for phase in phases),
        ),
        LiveOrderRealApprovalGatePlanSection(
            section_id="go_conditions",
            title="Go Conditions",
            lines=DEFAULT_REAL_APPROVAL_GATE_PLAN_GO_CONDITIONS,
        ),
        LiveOrderRealApprovalGatePlanSection(
            section_id="no_go_conditions",
            title="No-go Conditions",
            lines=DEFAULT_REAL_APPROVAL_GATE_PLAN_NO_GO_CONDITIONS,
        ),
        LiveOrderRealApprovalGatePlanSection(
            section_id="stop_conditions",
            title="Stop Conditions",
            lines=DEFAULT_REAL_APPROVAL_GATE_PLAN_STOP_CONDITIONS,
        ),
        LiveOrderRealApprovalGatePlanSection(
            section_id="checks",
            title="Plan Checks",
            lines=(
                f"failed_checks: {', '.join(failed_checks) if failed_checks else 'none'}",
                f"blocked_reasons: {', '.join(blocked_reasons) if blocked_reasons else 'none'}",
            ),
        ),
        LiveOrderRealApprovalGatePlanSection(
            section_id="next_step",
            title="Recommended Next Step",
            lines=(recommended_next_step,),
        ),
    )


def _validate_plan(plan: LiveOrderRealApprovalGatePlan) -> None:
    _require_non_empty("plan_id", plan.plan_id)
    if not isinstance(plan.created_at, datetime):
        raise LiveVerificationValidationError("created_at must be datetime")
    for field_name in (
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
        "execution_type",
        "summary",
        "recommended_next_step",
    ):
        _require_non_empty(field_name, getattr(plan, field_name))
    if type(plan.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    for field_name, expected in (
        ("allowed_for_live", False),
        ("requires_human_approval", True),
        ("explicit_user_confirmation_required", True),
        ("real_approval_gate_separate_step_required", True),
        ("fresh_preflight_before_gate_required", True),
        ("approval_id_generation_after_fresh_preflight_required", True),
        ("approval_command_generation_after_fresh_preflight_required", True),
        ("post_approval_final_dynamic_preflight_required", True),
        ("one_shot_post_separate_step_required", True),
        ("post_reconciliation_separate_step_required", True),
        ("final_report_separate_step_required", True),
        ("approval_gate_required", True),
        ("approval_gate_planned", True),
        ("approval_gate_issued", False),
        ("approval_id_generation_planned", True),
        ("approval_id_generated", False),
        ("approval_command_generation_planned", True),
        ("approval_command_generated", False),
        ("approval_command_template_only", True),
        ("approval_command_copyable", False),
        ("exact_match_required", True),
        ("same_session_required", True),
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
        if getattr(plan, field_name) is not expected:
            raise LiveVerificationValidationError(f"{field_name} safety default mismatch")
    if plan.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("ttl_seconds must be 300")
    if plan.post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if plan.required_ack_tokens != APPROVAL_ACK_TOKENS:
        raise LiveVerificationValidationError("required_ack_tokens mismatch")
    if not set(REQUIRED_REAL_APPROVAL_GATE_PLAN_PHASE_IDS).issubset(
        {phase.phase_id for phase in plan.phases}
    ):
        raise LiveVerificationValidationError("required phases are missing")
    for value, label in (
        (plan.display_allowed_fields, "display_allowed_fields"),
        (plan.display_forbidden_fields, "display_forbidden_fields"),
        (plan.go_conditions, "go_conditions"),
        (plan.no_go_conditions, "no_go_conditions"),
        (plan.stop_conditions, "stop_conditions"),
        (plan.check_results, "check_results"),
        (plan.sections, "sections"),
    ):
        if not value:
            raise LiveVerificationValidationError(f"{label} are required")
    if (
        plan.plan_status
        is LiveOrderRealApprovalGatePlanStatus.READY_FOR_REAL_APPROVAL_GATE_PLAN_REVIEW
    ):
        if not plan.plan_ready:
            raise LiveVerificationValidationError("ready plan must be ready")
        if plan.blocked_reasons:
            raise LiveVerificationValidationError("ready plan cannot have blockers")
    if (
        plan.plan_status
        is LiveOrderRealApprovalGatePlanStatus.BLOCKED_REAL_APPROVAL_GATE_PLAN
    ):
        if plan.plan_ready:
            raise LiveVerificationValidationError("blocked plan cannot be ready")
        if plan.eligible_for_future_real_approval_gate_implementation:
            raise LiveVerificationValidationError("blocked plan cannot be eligible")


def _checkpoint_is_blocked(
    checkpoint: LiveOrderRealApprovalReadinessCheckpoint | None,
) -> bool:
    return (
        checkpoint is not None
        and checkpoint.readiness_status
        is LiveOrderRealApprovalReadinessStatus.BLOCKED_REAL_APPROVAL_READINESS
    )


def _check(
    name: str,
    passed: bool,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealApprovalGatePlanCheckResult:
    return LiveOrderRealApprovalGatePlanCheckResult(
        name=name,
        passed=passed,
        reason="passed" if passed else "blocked",
        sanitized_value=sanitized_value,
        expected=expected,
    )


def _add_reason(
    reasons: list[str],
    reason: LiveOrderRealApprovalGatePlanBlockReason,
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
