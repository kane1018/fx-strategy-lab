"""Dry-run criteria for future real approval gate enablement in Step 5X."""

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
from app.live_verification.live_order_real_approval_disabled_scaffold import (
    LiveOrderRealApprovalDisabledScaffold,
    LiveOrderRealApprovalDisabledScaffoldStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

ScaffoldStatus = LiveOrderRealApprovalDisabledScaffoldStatus

LIVE_ORDER_REAL_APPROVAL_ENABLEMENT_CRITERIA_ID_PREFIX = "LORAEC-"

DEFAULT_REAL_APPROVAL_ENABLEMENT_CRITERIA_FUTURE_ENABLEMENT_REQUIREMENTS = (
    "explicit future user instruction required",
    "fresh pre-approval preflight must be re-run",
    "implementation readiness review must be rechecked",
    "disabled scaffold must be rechecked",
    "enablement safety audit must be separate future step",
    "approval_gate_enabled may only change in a future explicit step",
    "real approval_id generation must remain separate",
    "real approval command generation must remain separate",
    "post-enable final dynamic preflight required",
    "one-shot POST remains separate",
    "post reconciliation remains separate",
)

DEFAULT_REAL_APPROVAL_ENABLEMENT_GO_CONDITIONS = (
    "disabled scaffold ready",
    "explicit user instruction present in future step",
    "fresh preflight rerun in future step",
    "implementation readiness rechecked in future step",
    "no blocked reasons",
    "approval artifacts still not generated",
    "approval_gate_enabled still false before future enablement step",
    "no API/broker/live_order_once called",
    "post not executed",
    "one-shot constraints preserved",
)

DEFAULT_REAL_APPROVAL_ENABLEMENT_NO_GO_CONDITIONS = (
    "no explicit future instruction",
    "stale or missing fresh preflight",
    "any blocked reason exists",
    "approval artifact already generated",
    "approval_gate_enabled already true",
    "any API/broker/live_order_once already called",
    "post already executed",
    "raw response or real ID exposure risk",
    "need for retry/loop/add/change/cancel/close",
)

DEFAULT_REAL_APPROVAL_ENABLEMENT_KILL_SWITCH_CONDITIONS = (
    "unknown status",
    "result_unknown",
    "stale preflight",
    "exact match cannot be guaranteed",
    "same session cannot be guaranteed",
    "TTL cannot be enforced",
    "ACK list incomplete",
    "secret/raw response/real ID exposure risk",
    "any API response shape unexpected",
    "any need to exceed one POST attempt",
    "any need for retry/loop/add/change/cancel/close",
)

DEFAULT_REAL_APPROVAL_ID_GENERATION_CONDITIONS = (
    "future explicit approval gate enablement step only",
    "fresh preflight completed in future step",
    "approval_gate_enabled intentionally enabled in future step",
    "no blocked reasons",
    "no secret/raw/ID exposure risk",
    "same session requirement satisfied",
)

DEFAULT_REAL_APPROVAL_COMMAND_GENERATION_CONDITIONS = (
    "future explicit approval gate enablement step only",
    "approval_id generated in the same future step",
    "fresh preflight completed in future step",
    "exact match template finalized in future step",
    "TTL 300 seconds enforced",
    "all ACK tokens present",
    "command remains one line",
    "no extra tokens / no line breaks / no copyable text before future step",
)

REAL_APPROVAL_ENABLEMENT_CRITERIA_DISPLAY_ALLOWED_FIELDS = (
    "criteria_id",
    "scaffold_id",
    "implementation_readiness_review_id",
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
    "criteria_status",
    "criteria_ready",
    "eligible_for_future_real_approval_gate_enablement_planning",
    "allowed_for_live=false",
    "approval_gate_enabled=false",
    "approval_gate_enablement_deferred_to_future_step=true",
    "approval_gate_issued=false",
    "approval_id_generated=false",
    "approval_command_generated=false",
    "approval_command_copyable=false",
    "approval_command_executable=false",
    "usable_approval_artifacts_generated=false",
    "real_approval_artifacts_available=false",
    "ttl_seconds",
    "exact_match_required",
    "same_session_required",
    "required_ack_tokens",
    "future_enablement_requirements",
    "enablement_go_conditions",
    "enablement_no_go_conditions",
    "kill_switch_conditions",
    "approval_id_generation_conditions",
    "approval_command_generation_conditions",
    "check_results",
    "blocked_reasons",
    "recommended_next_step",
)

REAL_APPROVAL_ENABLEMENT_CRITERIA_DISPLAY_FORBIDDEN_FIELDS = (
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


class LiveOrderRealApprovalEnablementCriteriaStatus(str, Enum):
    READY_FOR_REAL_APPROVAL_ENABLEMENT_CRITERIA_REVIEW = (
        "READY_FOR_REAL_APPROVAL_ENABLEMENT_CRITERIA_REVIEW"
    )
    BLOCKED_REAL_APPROVAL_ENABLEMENT_CRITERIA = (
        "BLOCKED_REAL_APPROVAL_ENABLEMENT_CRITERIA"
    )


CriteriaStatus = LiveOrderRealApprovalEnablementCriteriaStatus


class LiveOrderRealApprovalEnablementCriteriaBlockReason(str, Enum):
    MISSING_DISABLED_SCAFFOLD = "missing_disabled_scaffold"
    DISABLED_SCAFFOLD_NOT_READY = "disabled_scaffold_not_ready"
    DISABLED_SCAFFOLD_NOT_ELIGIBLE = "disabled_scaffold_not_eligible"
    SCAFFOLD_ALLOWS_LIVE = "scaffold_allows_live"
    SCAFFOLD_APPROVAL_GATE_ENABLED = "scaffold_approval_gate_enabled"
    SCAFFOLD_NOT_DRY_RUN = "scaffold_not_dry_run"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_ID_ALREADY_GENERATED = "approval_id_already_generated"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
    APPROVAL_COMMAND_COPYABLE = "approval_command_copyable"
    APPROVAL_COMMAND_EXECUTABLE = "approval_command_executable"
    USABLE_APPROVAL_ARTIFACTS_GENERATED = "usable_approval_artifacts_generated"
    REAL_APPROVAL_ARTIFACTS_AVAILABLE = "real_approval_artifacts_available"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    APPROVAL_GATE_ENABLED = "approval_gate_enabled"
    APPROVAL_GATE_ENABLEMENT_NOT_DEFERRED = (
        "approval_gate_enablement_not_deferred"
    )
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
    MISSING_FUTURE_ENABLEMENT_REQUIREMENTS = (
        "missing_future_enablement_requirements"
    )
    MISSING_ENABLEMENT_GO_CONDITIONS = "missing_enablement_go_conditions"
    MISSING_ENABLEMENT_NO_GO_CONDITIONS = "missing_enablement_no_go_conditions"
    MISSING_KILL_SWITCH_CONDITIONS = "missing_kill_switch_conditions"
    MISSING_APPROVAL_ID_GENERATION_CONDITIONS = (
        "missing_approval_id_generation_conditions"
    )
    MISSING_APPROVAL_COMMAND_GENERATION_CONDITIONS = (
        "missing_approval_command_generation_conditions"
    )


BlockReason = LiveOrderRealApprovalEnablementCriteriaBlockReason


@dataclass(frozen=True)
class LiveOrderRealApprovalEnablementCriteriaCheckResult:
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
class LiveOrderRealApprovalEnablementCriteriaSection:
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
class LiveOrderRealApprovalEnablementCriteria:
    criteria_id: str
    created_at: datetime
    scaffold_id: str
    implementation_readiness_review_id: str
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
    criteria_status: LiveOrderRealApprovalEnablementCriteriaStatus
    criteria_ready: bool
    eligible_for_future_real_approval_gate_enablement_planning: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_gate_enablement_planned: bool
    approval_gate_enablement_deferred_to_future_step: bool
    approval_gate_issued: bool
    approval_id_generation_planned: bool
    approval_id_generation_deferred_to_future_step: bool
    approval_id_generated: bool
    approval_command_generation_planned: bool
    approval_command_generation_deferred_to_future_step: bool
    approval_command_generated: bool
    approval_command_template_only: bool
    approval_command_copyable: bool
    approval_command_executable: bool
    usable_approval_artifacts_generated: bool
    real_approval_artifacts_available: bool
    requires_human_approval: bool
    explicit_user_confirmation_required: bool
    fresh_preflight_before_enablement_required: bool
    implementation_readiness_review_required: bool
    post_enablement_safety_review_required: bool
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
    future_enablement_requirements: tuple[str, ...]
    enablement_go_conditions: tuple[str, ...]
    enablement_no_go_conditions: tuple[str, ...]
    kill_switch_conditions: tuple[str, ...]
    approval_id_generation_conditions: tuple[str, ...]
    approval_command_generation_conditions: tuple[str, ...]
    display_allowed_fields: tuple[str, ...]
    display_forbidden_fields: tuple[str, ...]
    check_results: tuple[LiveOrderRealApprovalEnablementCriteriaCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApprovalEnablementCriteriaSection, ...]

    def __post_init__(self) -> None:
        _validate_criteria(self)


@dataclass(frozen=True)
class LiveOrderRealApprovalEnablementCriteriaBuildResult:
    criteria: LiveOrderRealApprovalEnablementCriteria
    criteria_id: str
    criteria_status: LiveOrderRealApprovalEnablementCriteriaStatus
    criteria_ready: bool
    eligible_for_future_real_approval_gate_enablement_planning: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_copyable: bool
    approval_command_executable: bool
    usable_approval_artifacts_generated: bool
    real_approval_artifacts_available: bool
    post_executed: bool
    live_order_once_called: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.criteria.criteria_id != self.criteria_id:
            raise LiveVerificationValidationError("criteria_id mismatch")
        if self.criteria.criteria_status is not self.criteria_status:
            raise LiveVerificationValidationError("criteria_status mismatch")
        if self.criteria.criteria_ready is not self.criteria_ready:
            raise LiveVerificationValidationError("criteria_ready mismatch")
        if (
            self.criteria.eligible_for_future_real_approval_gate_enablement_planning
            is not self.eligible_for_future_real_approval_gate_enablement_planning
        ):
            raise LiveVerificationValidationError("criteria eligibility mismatch")
        for field_name, value in (
            ("allowed_for_live", self.allowed_for_live),
            ("approval_gate_enabled", self.approval_gate_enabled),
            ("approval_gate_issued", self.approval_gate_issued),
            ("approval_id_generated", self.approval_id_generated),
            ("approval_command_generated", self.approval_command_generated),
            ("approval_command_copyable", self.approval_command_copyable),
            ("approval_command_executable", self.approval_command_executable),
            (
                "usable_approval_artifacts_generated",
                self.usable_approval_artifacts_generated,
            ),
            ("real_approval_artifacts_available", self.real_approval_artifacts_available),
            ("post_executed", self.post_executed),
            ("live_order_once_called", self.live_order_once_called),
        ):
            if value is not False:
                raise LiveVerificationValidationError(f"{field_name} must be False")
        if self.criteria.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.criteria.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_approval_enablement_criteria(
    *,
    disabled_scaffold: LiveOrderRealApprovalDisabledScaffold | None,
    created_at: datetime | None = None,
    future_enablement_requirements: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_ENABLEMENT_CRITERIA_FUTURE_ENABLEMENT_REQUIREMENTS,
    enablement_go_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_ENABLEMENT_GO_CONDITIONS,
    enablement_no_go_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_ENABLEMENT_NO_GO_CONDITIONS,
    kill_switch_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_ENABLEMENT_KILL_SWITCH_CONDITIONS,
    approval_id_generation_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_ID_GENERATION_CONDITIONS,
    approval_command_generation_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_COMMAND_GENERATION_CONDITIONS,
    approval_gate_enabled: bool = False,
    approval_gate_enablement_deferred_to_future_step: bool = True,
    post_attempt_limit: int = 1,
    retry_allowed: bool = False,
    loop_allowed: bool = False,
    add_order_allowed: bool = False,
    change_order_allowed: bool = False,
    cancel_order_allowed: bool = False,
    close_order_allowed: bool = False,
    post_reconciliation_required: bool = True,
) -> LiveOrderRealApprovalEnablementCriteriaBuildResult:
    """Build future enablement criteria without enabling real approval artifacts."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    blocked_reasons = _merge_reasons(
        _scaffold_blocked_reasons(disabled_scaffold),
        _scaffold_existing_reasons(disabled_scaffold),
        _criteria_constraint_reasons(
            disabled_scaffold=disabled_scaffold,
            future_enablement_requirements=future_enablement_requirements,
            enablement_go_conditions=enablement_go_conditions,
            enablement_no_go_conditions=enablement_no_go_conditions,
            kill_switch_conditions=kill_switch_conditions,
            approval_id_generation_conditions=approval_id_generation_conditions,
            approval_command_generation_conditions=approval_command_generation_conditions,
            approval_gate_enabled=approval_gate_enabled,
            approval_gate_enablement_deferred_to_future_step=(
                approval_gate_enablement_deferred_to_future_step
            ),
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
        disabled_scaffold=disabled_scaffold,
        future_enablement_requirements=future_enablement_requirements,
        enablement_go_conditions=enablement_go_conditions,
        enablement_no_go_conditions=enablement_no_go_conditions,
        kill_switch_conditions=kill_switch_conditions,
        approval_id_generation_conditions=approval_id_generation_conditions,
        approval_command_generation_conditions=approval_command_generation_conditions,
        approval_gate_enabled=approval_gate_enabled,
        approval_gate_enablement_deferred_to_future_step=(
            approval_gate_enablement_deferred_to_future_step
        ),
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
        criteria_status = CriteriaStatus.BLOCKED_REAL_APPROVAL_ENABLEMENT_CRITERIA
        criteria_ready = False
        eligible = False
        recommended_next_step = "fix_disabled_scaffold_blockers_no_post"
        summary = (
            "blocked real approval enablement criteria; no approval gate, "
            "approval artifact, API call, live runner call, or post is allowed"
        )
    else:
        criteria_status = (
            CriteriaStatus.READY_FOR_REAL_APPROVAL_ENABLEMENT_CRITERIA_REVIEW
        )
        criteria_ready = True
        eligible = True
        recommended_next_step = (
            "review_enablement_criteria_then_stop_before_any_real_enablement_or_approval_artifact_generation"
        )
        summary = (
            "ready real approval enablement criteria review only; approval gate "
            "enablement and live post remain disallowed"
        )

    criteria_id = make_live_order_real_approval_enablement_criteria_id(
        scaffold_id=_text_from(disabled_scaffold, "scaffold_id"),
        candidate_id=_text_from(disabled_scaffold, "candidate_id"),
        created_at=created,
        criteria_status=criteria_status,
        blocked_reasons=blocked_reasons,
    )
    criteria = LiveOrderRealApprovalEnablementCriteria(
        criteria_id=criteria_id,
        created_at=created,
        scaffold_id=_text_from(disabled_scaffold, "scaffold_id"),
        implementation_readiness_review_id=_text_from(
            disabled_scaffold,
            "implementation_readiness_review_id",
        ),
        audit_id=_text_from(disabled_scaffold, "audit_id"),
        package_id=_text_from(disabled_scaffold, "package_id"),
        pre_approval_preflight_decision_id=_text_from(
            disabled_scaffold,
            "pre_approval_preflight_decision_id",
        ),
        snapshot_id=_text_from(disabled_scaffold, "snapshot_id"),
        plan_id=_text_from(disabled_scaffold, "plan_id"),
        checkpoint_id=_text_from(disabled_scaffold, "checkpoint_id"),
        chain_id=_text_from(disabled_scaffold, "chain_id"),
        runbook_id=_text_from(disabled_scaffold, "runbook_id"),
        boundary_id=_text_from(disabled_scaffold, "boundary_id"),
        preflight_decision_id=_text_from(disabled_scaffold, "preflight_decision_id"),
        simulation_id=_text_from(disabled_scaffold, "simulation_id"),
        preview_id=_text_from(disabled_scaffold, "preview_id"),
        design_id=_text_from(disabled_scaffold, "design_id"),
        handoff_id=_text_from(disabled_scaffold, "handoff_id"),
        operator_review_id=_text_from(disabled_scaffold, "operator_review_id"),
        bundle_id=_text_from(disabled_scaffold, "bundle_id"),
        candidate_review_id=_text_from(disabled_scaffold, "candidate_review_id"),
        candidate_id=_text_from(disabled_scaffold, "candidate_id"),
        risk_decision_id=_text_from(disabled_scaffold, "risk_decision_id"),
        trace_id=_text_from(disabled_scaffold, "trace_id"),
        session_policy_decision_id=_text_from(
            disabled_scaffold,
            "session_policy_decision_id",
        ),
        source_signal_id=_text_from(disabled_scaffold, "source_signal_id"),
        source_type=_text_from(disabled_scaffold, "source_type"),
        strategy_name=_text_from(disabled_scaffold, "strategy_name"),
        symbol=_text_from(disabled_scaffold, "symbol"),
        side=_text_from(disabled_scaffold, "side"),
        size=_int_from(disabled_scaffold, "size"),
        execution_type=_text_from(disabled_scaffold, "execution_type"),
        criteria_status=criteria_status,
        criteria_ready=criteria_ready,
        eligible_for_future_real_approval_gate_enablement_planning=eligible,
        allowed_for_live=False,
        approval_gate_enabled=False,
        approval_gate_enablement_planned=True,
        approval_gate_enablement_deferred_to_future_step=True,
        approval_gate_issued=False,
        approval_id_generation_planned=True,
        approval_id_generation_deferred_to_future_step=True,
        approval_id_generated=False,
        approval_command_generation_planned=True,
        approval_command_generation_deferred_to_future_step=True,
        approval_command_generated=False,
        approval_command_template_only=True,
        approval_command_copyable=False,
        approval_command_executable=False,
        usable_approval_artifacts_generated=False,
        real_approval_artifacts_available=False,
        requires_human_approval=True,
        explicit_user_confirmation_required=True,
        fresh_preflight_before_enablement_required=True,
        implementation_readiness_review_required=True,
        post_enablement_safety_review_required=True,
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
        future_enablement_requirements=future_enablement_requirements,
        enablement_go_conditions=enablement_go_conditions,
        enablement_no_go_conditions=enablement_no_go_conditions,
        kill_switch_conditions=kill_switch_conditions,
        approval_id_generation_conditions=approval_id_generation_conditions,
        approval_command_generation_conditions=approval_command_generation_conditions,
        display_allowed_fields=REAL_APPROVAL_ENABLEMENT_CRITERIA_DISPLAY_ALLOWED_FIELDS,
        display_forbidden_fields=(
            REAL_APPROVAL_ENABLEMENT_CRITERIA_DISPLAY_FORBIDDEN_FIELDS
        ),
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
            future_enablement_requirements=future_enablement_requirements,
            enablement_go_conditions=enablement_go_conditions,
            enablement_no_go_conditions=enablement_no_go_conditions,
            kill_switch_conditions=kill_switch_conditions,
            approval_id_generation_conditions=approval_id_generation_conditions,
            approval_command_generation_conditions=approval_command_generation_conditions,
        ),
    )
    return LiveOrderRealApprovalEnablementCriteriaBuildResult(
        criteria=criteria,
        criteria_id=criteria.criteria_id,
        criteria_status=criteria.criteria_status,
        criteria_ready=criteria.criteria_ready,
        eligible_for_future_real_approval_gate_enablement_planning=(
            criteria.eligible_for_future_real_approval_gate_enablement_planning
        ),
        allowed_for_live=False,
        approval_gate_enabled=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_copyable=False,
        approval_command_executable=False,
        usable_approval_artifacts_generated=False,
        real_approval_artifacts_available=False,
        post_executed=False,
        live_order_once_called=False,
        blocked_reasons=criteria.blocked_reasons,
        recommended_next_step=criteria.recommended_next_step,
    )


def render_live_order_real_approval_enablement_criteria_markdown(
    criteria: LiveOrderRealApprovalEnablementCriteria,
) -> str:
    """Render a sanitized future enablement criteria report."""
    blocked_text = ", ".join(criteria.blocked_reasons) or "none"
    ack_lines = "\n".join(f"- {token}" for token in criteria.required_ack_tokens)
    future_lines = "\n".join(
        f"- {item}" for item in criteria.future_enablement_requirements
    )
    go_lines = "\n".join(f"- {item}" for item in criteria.enablement_go_conditions)
    no_go_lines = "\n".join(
        f"- {item}" for item in criteria.enablement_no_go_conditions
    )
    kill_lines = "\n".join(f"- {item}" for item in criteria.kill_switch_conditions)
    id_lines = "\n".join(
        f"- {item}" for item in criteria.approval_id_generation_conditions
    )
    command_lines = "\n".join(
        f"- {item}" for item in criteria.approval_command_generation_conditions
    )
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in criteria.check_results
    )
    return "\n".join(
        (
            "# Step 5X Real Approval Enablement Criteria",
            "",
            "This real approval gate enablement criteria model is dry-run only.",
            "This criteria model does not enable a real approval gate.",
            "This criteria model keeps approval_gate_enabled=false.",
            "This criteria model does not call read-only API.",
            "This criteria model does not call Private API.",
            "This criteria model does not call live_order_once.",
            "This criteria model does not execute HTTP POST.",
            "This criteria model does not issue a real approval gate.",
            "This criteria model does not generate a real approval_id.",
            "This criteria model does not generate a real approval command.",
            "This criteria model does not provide copyable approval text.",
            "This criteria model does not authorize live POST.",
            "approval_gate_enabled=false.",
            "allowed_for_live=false.",
            "",
            f"criteria_id: {criteria.criteria_id}",
            f"scaffold_id: {criteria.scaffold_id}",
            f"implementation_readiness_review_id: {criteria.implementation_readiness_review_id}",
            f"audit_id: {criteria.audit_id}",
            f"package_id: {criteria.package_id}",
            f"pre_approval_preflight_decision_id: {criteria.pre_approval_preflight_decision_id}",
            f"snapshot_id: {criteria.snapshot_id}",
            f"plan_id: {criteria.plan_id}",
            f"checkpoint_id: {criteria.checkpoint_id}",
            f"chain_id: {criteria.chain_id}",
            f"runbook_id: {criteria.runbook_id}",
            f"boundary_id: {criteria.boundary_id}",
            f"preflight_decision_id: {criteria.preflight_decision_id}",
            f"simulation_id: {criteria.simulation_id}",
            f"preview_id: {criteria.preview_id}",
            f"design_id: {criteria.design_id}",
            f"handoff_id: {criteria.handoff_id}",
            f"operator_review_id: {criteria.operator_review_id}",
            f"bundle_id: {criteria.bundle_id}",
            f"candidate_review_id: {criteria.candidate_review_id}",
            f"candidate_id: {criteria.candidate_id}",
            f"risk_decision_id: {criteria.risk_decision_id}",
            f"trace_id: {criteria.trace_id}",
            f"session_policy_decision_id: {criteria.session_policy_decision_id}",
            f"source_signal_id: {criteria.source_signal_id}",
            f"source_type: {criteria.source_type}",
            f"strategy_name: {criteria.strategy_name}",
            f"symbol: {criteria.symbol}",
            f"side: {criteria.side}",
            f"size: {criteria.size}",
            f"executionType: {criteria.execution_type}",
            f"criteria_status: {criteria.criteria_status.value}",
            f"criteria_ready: {criteria.criteria_ready}",
            "eligible_for_future_real_approval_gate_enablement_planning: "
            f"{criteria.eligible_for_future_real_approval_gate_enablement_planning}",
            f"allowed_for_live: {criteria.allowed_for_live}",
            f"approval_gate_enabled: {criteria.approval_gate_enabled}",
            "approval_gate_enablement_deferred_to_future_step: "
            f"{criteria.approval_gate_enablement_deferred_to_future_step}",
            f"approval_gate_issued: {criteria.approval_gate_issued}",
            f"approval_id_generated: {criteria.approval_id_generated}",
            f"approval_command_generated: {criteria.approval_command_generated}",
            f"approval_command_copyable: {criteria.approval_command_copyable}",
            f"approval_command_executable: {criteria.approval_command_executable}",
            "usable_approval_artifacts_generated: "
            f"{criteria.usable_approval_artifacts_generated}",
            f"real_approval_artifacts_available: {criteria.real_approval_artifacts_available}",
            f"ttl_seconds: {criteria.ttl_seconds}",
            f"exact_match_required: {criteria.exact_match_required}",
            f"same_session_required: {criteria.same_session_required}",
            f"post_attempt_limit: {criteria.post_attempt_limit}",
            f"post_executed: {criteria.post_executed}",
            f"live_order_once_called: {criteria.live_order_once_called}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {criteria.recommended_next_step}",
            "",
            "## Required ACK Tokens",
            ack_lines,
            "",
            "## Future Enablement Requirements",
            future_lines,
            "",
            "## Enablement Go Conditions",
            go_lines,
            "",
            "## Enablement No-Go Conditions",
            no_go_lines,
            "",
            "## Kill Switch Conditions",
            kill_lines,
            "",
            "## Approval ID Generation Conditions",
            id_lines,
            "",
            "## Approval Command Generation Conditions",
            command_lines,
            "",
            "## Check Results",
            check_lines,
        ),
    )


def make_live_order_real_approval_enablement_criteria_id(
    *,
    scaffold_id: str,
    candidate_id: str,
    created_at: datetime,
    criteria_status: LiveOrderRealApprovalEnablementCriteriaStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": _ensure_aware(created_at).isoformat(),
        "criteria_status": criteria_status.value,
        "scaffold_id": scaffold_id,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_ENABLEMENT_CRITERIA_ID_PREFIX}{digest}"


def _scaffold_blocked_reasons(
    scaffold: LiveOrderRealApprovalDisabledScaffold | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(scaffold, LiveOrderRealApprovalDisabledScaffold):
        _add_reason(reasons, BlockReason.MISSING_DISABLED_SCAFFOLD)
        return tuple(reasons)
    if (
        scaffold.scaffold_status
        is not ScaffoldStatus.READY_FOR_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD_REVIEW
        or scaffold.scaffold_ready is not True
    ):
        _add_reason(reasons, BlockReason.DISABLED_SCAFFOLD_NOT_READY)
    if scaffold.eligible_for_future_enablement_planning is not True:
        _add_reason(reasons, BlockReason.DISABLED_SCAFFOLD_NOT_ELIGIBLE)
    if scaffold.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.SCAFFOLD_ALLOWS_LIVE)
    if scaffold.approval_gate_enabled is not False:
        _add_reason(reasons, BlockReason.SCAFFOLD_APPROVAL_GATE_ENABLED)
    if scaffold.dry_run_only is not True:
        _add_reason(reasons, BlockReason.SCAFFOLD_NOT_DRY_RUN)
    for field_value, reason in (
        (scaffold.approval_gate_issued, BlockReason.APPROVAL_GATE_ALREADY_ISSUED),
        (scaffold.approval_id_generated, BlockReason.APPROVAL_ID_ALREADY_GENERATED),
        (
            scaffold.approval_command_generated,
            BlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (scaffold.approval_command_copyable, BlockReason.APPROVAL_COMMAND_COPYABLE),
        (
            scaffold.approval_command_executable,
            BlockReason.APPROVAL_COMMAND_EXECUTABLE,
        ),
        (
            scaffold.usable_approval_artifacts_generated,
            BlockReason.USABLE_APPROVAL_ARTIFACTS_GENERATED,
        ),
        (
            scaffold.real_approval_artifacts_available,
            BlockReason.REAL_APPROVAL_ARTIFACTS_AVAILABLE,
        ),
    ):
        if field_value is not False:
            _add_reason(reasons, reason)
    if scaffold.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SYMBOL)
    if scaffold.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIDE)
    if scaffold.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIZE)
    if scaffold.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_EXECUTION_TYPE)
    return tuple(reasons)


def _scaffold_existing_reasons(
    scaffold: LiveOrderRealApprovalDisabledScaffold | None,
) -> tuple[str, ...]:
    if not isinstance(scaffold, LiveOrderRealApprovalDisabledScaffold):
        return ()
    return tuple(scaffold.blocked_reasons)


def _criteria_constraint_reasons(
    *,
    disabled_scaffold: LiveOrderRealApprovalDisabledScaffold | None,
    future_enablement_requirements: tuple[str, ...],
    enablement_go_conditions: tuple[str, ...],
    enablement_no_go_conditions: tuple[str, ...],
    kill_switch_conditions: tuple[str, ...],
    approval_id_generation_conditions: tuple[str, ...],
    approval_command_generation_conditions: tuple[str, ...],
    approval_gate_enabled: bool,
    approval_gate_enablement_deferred_to_future_step: bool,
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
    if isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold):
        scaffold = disabled_scaffold
        if scaffold.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
            _add_reason(reasons, BlockReason.INVALID_TTL_SECONDS)
        if scaffold.exact_match_required is not True:
            _add_reason(reasons, BlockReason.EXACT_MATCH_NOT_REQUIRED)
        if scaffold.same_session_required is not True:
            _add_reason(reasons, BlockReason.SAME_SESSION_NOT_REQUIRED)
        if set(APPROVAL_ACK_TOKENS) - set(scaffold.required_ack_tokens):
            _add_reason(reasons, BlockReason.MISSING_ACK_TOKEN)
        if not _display_forbidden_fields_are_complete(scaffold.display_forbidden_fields):
            _add_reason(reasons, BlockReason.DISPLAY_FORBIDDEN_FIELDS_INCOMPLETE)
        for flag, reason in (
            (scaffold.post_executed, BlockReason.POST_ALREADY_EXECUTED),
            (scaffold.live_order_once_called, BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED),
            (scaffold.private_api_called, BlockReason.PRIVATE_API_ALREADY_CALLED),
            (scaffold.broker_called, BlockReason.BROKER_ALREADY_CALLED),
            (scaffold.read_only_api_called, BlockReason.READ_ONLY_API_ALREADY_CALLED),
            (scaffold.public_api_called, BlockReason.PUBLIC_API_ALREADY_CALLED),
        ):
            if flag is not False:
                _add_reason(reasons, reason)
    if approval_gate_enabled is not False:
        _add_reason(reasons, BlockReason.APPROVAL_GATE_ENABLED)
    if approval_gate_enablement_deferred_to_future_step is not True:
        _add_reason(reasons, BlockReason.APPROVAL_GATE_ENABLEMENT_NOT_DEFERRED)
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
    for values, reason in (
        (
            future_enablement_requirements,
            BlockReason.MISSING_FUTURE_ENABLEMENT_REQUIREMENTS,
        ),
        (enablement_go_conditions, BlockReason.MISSING_ENABLEMENT_GO_CONDITIONS),
        (enablement_no_go_conditions, BlockReason.MISSING_ENABLEMENT_NO_GO_CONDITIONS),
        (kill_switch_conditions, BlockReason.MISSING_KILL_SWITCH_CONDITIONS),
        (
            approval_id_generation_conditions,
            BlockReason.MISSING_APPROVAL_ID_GENERATION_CONDITIONS,
        ),
        (
            approval_command_generation_conditions,
            BlockReason.MISSING_APPROVAL_COMMAND_GENERATION_CONDITIONS,
        ),
    ):
        if not values:
            _add_reason(reasons, reason)
    return tuple(reasons)


def _build_check_results(
    *,
    disabled_scaffold: LiveOrderRealApprovalDisabledScaffold | None,
    future_enablement_requirements: tuple[str, ...],
    enablement_go_conditions: tuple[str, ...],
    enablement_no_go_conditions: tuple[str, ...],
    kill_switch_conditions: tuple[str, ...],
    approval_id_generation_conditions: tuple[str, ...],
    approval_command_generation_conditions: tuple[str, ...],
    approval_gate_enabled: bool,
    approval_gate_enablement_deferred_to_future_step: bool,
    post_attempt_limit: int,
    retry_allowed: bool,
    loop_allowed: bool,
    add_order_allowed: bool,
    change_order_allowed: bool,
    cancel_order_allowed: bool,
    close_order_allowed: bool,
    post_reconciliation_required: bool,
) -> tuple[LiveOrderRealApprovalEnablementCriteriaCheckResult, ...]:
    scaffold_ready = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.scaffold_status
        is ScaffoldStatus.READY_FOR_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD_REVIEW
        and disabled_scaffold.scaffold_ready is True
        and disabled_scaffold.eligible_for_future_enablement_planning is True
    )
    allowed_false = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.allowed_for_live is False
    )
    no_artifacts = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.usable_approval_artifacts_generated is False
        and disabled_scaffold.real_approval_artifacts_available is False
    )
    gate_not_issued = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.approval_gate_issued is False
    )
    id_not_generated = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.approval_id_generated is False
    )
    command_not_generated = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.approval_command_generated is False
    )
    command_not_copyable = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.approval_command_copyable is False
    )
    command_not_executable = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.approval_command_executable is False
    )
    no_api_calls = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.live_order_once_called is False
        and disabled_scaffold.private_api_called is False
        and disabled_scaffold.broker_called is False
        and disabled_scaffold.read_only_api_called is False
        and disabled_scaffold.public_api_called is False
    )
    post_not_executed = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.post_executed is False
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
    ttl_300 = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.ttl_seconds == APPROVAL_GATE_TTL_SECONDS
    )
    exact_required = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.exact_match_required is True
    )
    same_session = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and disabled_scaffold.same_session_required is True
    )
    ack_present = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and not (set(APPROVAL_ACK_TOKENS) - set(disabled_scaffold.required_ack_tokens))
    )
    display_complete = (
        isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
        and _display_forbidden_fields_are_complete(
            disabled_scaffold.display_forbidden_fields
        )
    )
    return (
        _check(
            "disabled_scaffold_ready",
            scaffold_ready,
            "disabled scaffold must be ready before future enablement criteria review",
            _bool_text(scaffold_ready),
            "true",
        ),
        _check(
            "approval_gate_enabled_false",
            approval_gate_enabled is False
            and (
                not isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
                or disabled_scaffold.approval_gate_enabled is False
            ),
            "approval gate must remain disabled in Step 5X",
            _bool_text(approval_gate_enabled),
            "false",
        ),
        _check(
            "allowed_for_live_false",
            allowed_false,
            "criteria cannot authorize live execution",
            _bool_text(allowed_false),
            "true",
        ),
        _check(
            "no_usable_approval_artifacts",
            no_artifacts,
            "usable or real approval artifacts must not exist",
            _bool_text(no_artifacts),
            "true",
        ),
        _check(
            "approval_gate_not_issued",
            gate_not_issued,
            "real approval gate must not be issued",
            _bool_text(gate_not_issued),
            "true",
        ),
        _check(
            "approval_id_not_generated",
            id_not_generated,
            "real approval_id must not be generated",
            _bool_text(id_not_generated),
            "true",
        ),
        _check(
            "approval_command_not_generated",
            command_not_generated,
            "real approval command must not be generated",
            _bool_text(command_not_generated),
            "true",
        ),
        _check(
            "approval_command_not_copyable",
            command_not_copyable,
            "approval text cannot be copyable in Step 5X",
            _bool_text(command_not_copyable),
            "true",
        ),
        _check(
            "approval_command_not_executable",
            command_not_executable,
            "approval command cannot be executable in Step 5X",
            _bool_text(command_not_executable),
            "true",
        ),
        _check(
            "future_enablement_deferred",
            approval_gate_enablement_deferred_to_future_step is True,
            "real enablement must remain a future explicit step",
            _bool_text(approval_gate_enablement_deferred_to_future_step),
            "true",
        ),
        _check(
            "approval_id_generation_deferred",
            isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
            and disabled_scaffold.approval_id_generation_deferred_to_future_step
            is True,
            "real approval_id generation must remain deferred",
            _bool_text(
                isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
                and disabled_scaffold.approval_id_generation_deferred_to_future_step
                is True
            ),
            "true",
        ),
        _check(
            "approval_command_generation_deferred",
            isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
            and disabled_scaffold.approval_command_generation_deferred_to_future_step
            is True,
            "real approval command generation must remain deferred",
            _bool_text(
                isinstance(disabled_scaffold, LiveOrderRealApprovalDisabledScaffold)
                and disabled_scaffold.approval_command_generation_deferred_to_future_step
                is True
            ),
            "true",
        ),
        _check(
            "ttl_seconds_300",
            ttl_300,
            "TTL must stay 300 seconds",
            _bool_text(ttl_300),
            "true",
        ),
        _check(
            "exact_match_required",
            exact_required,
            "exact match must remain required",
            _bool_text(exact_required),
            "true",
        ),
        _check(
            "same_session_required",
            same_session,
            "same Codex session must remain required",
            _bool_text(same_session),
            "true",
        ),
        _check(
            "required_ack_tokens_present",
            ack_present,
            "all required ACK tokens must be present",
            _bool_text(ack_present),
            "true",
        ),
        _check(
            "display_forbidden_fields_include_secrets_raw_ids_real_commands",
            display_complete,
            "display forbidden fields must include secrets, raw data, IDs, and real commands",
            _bool_text(display_complete),
            "true",
        ),
        _check(
            "no_api_broker_live_order_once_called",
            no_api_calls,
            "criteria cannot call APIs, broker, or live runner",
            _bool_text(no_api_calls),
            "true",
        ),
        _check(
            "post_not_executed",
            post_not_executed,
            "criteria cannot execute post",
            _bool_text(post_not_executed),
            "true",
        ),
        _check(
            "one_shot_constraints_preserved",
            one_shot_constraints,
            "one-shot constraints must stay fixed",
            _bool_text(one_shot_constraints),
            "true",
        ),
        _check(
            "future_enablement_requirements_present",
            bool(future_enablement_requirements),
            "future enablement requirements must be listed",
            _bool_text(bool(future_enablement_requirements)),
            "true",
        ),
        _check(
            "go_conditions_present",
            bool(enablement_go_conditions),
            "go conditions must be listed",
            _bool_text(bool(enablement_go_conditions)),
            "true",
        ),
        _check(
            "no_go_conditions_present",
            bool(enablement_no_go_conditions),
            "no-go conditions must be listed",
            _bool_text(bool(enablement_no_go_conditions)),
            "true",
        ),
        _check(
            "kill_switch_conditions_present",
            bool(kill_switch_conditions),
            "kill switch conditions must be listed",
            _bool_text(bool(kill_switch_conditions)),
            "true",
        ),
        _check(
            "approval_id_generation_conditions_present",
            bool(approval_id_generation_conditions),
            "approval_id generation conditions must be listed",
            _bool_text(bool(approval_id_generation_conditions)),
            "true",
        ),
        _check(
            "approval_command_generation_conditions_present",
            bool(approval_command_generation_conditions),
            "approval command generation conditions must be listed",
            _bool_text(bool(approval_command_generation_conditions)),
            "true",
        ),
    )


def _build_sections(
    *,
    check_results: tuple[LiveOrderRealApprovalEnablementCriteriaCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
    future_enablement_requirements: tuple[str, ...],
    enablement_go_conditions: tuple[str, ...],
    enablement_no_go_conditions: tuple[str, ...],
    kill_switch_conditions: tuple[str, ...],
    approval_id_generation_conditions: tuple[str, ...],
    approval_command_generation_conditions: tuple[str, ...],
) -> tuple[LiveOrderRealApprovalEnablementCriteriaSection, ...]:
    blocked = blocked_reasons or ("none",)
    return (
        LiveOrderRealApprovalEnablementCriteriaSection(
            section_id="criteria_summary",
            title="Criteria Summary",
            lines=(
                "Step 5X records future real approval enablement criteria only.",
                "approval_gate_enabled=false and allowed_for_live=false remain fixed.",
                f"recommended_next_step={recommended_next_step}",
            ),
        ),
        LiveOrderRealApprovalEnablementCriteriaSection(
            section_id="future_enablement_requirements",
            title="Future Enablement Requirements",
            lines=future_enablement_requirements or ("missing",),
        ),
        LiveOrderRealApprovalEnablementCriteriaSection(
            section_id="go_no_go_kill_switch",
            title="Go No-Go Kill Switch Criteria",
            lines=(
                f"go_conditions={len(enablement_go_conditions)}",
                f"no_go_conditions={len(enablement_no_go_conditions)}",
                f"kill_switch_conditions={len(kill_switch_conditions)}",
            ),
        ),
        LiveOrderRealApprovalEnablementCriteriaSection(
            section_id="approval_generation_conditions",
            title="Approval Generation Conditions",
            lines=(
                f"approval_id_generation_conditions={len(approval_id_generation_conditions)}",
                "approval_command_generation_conditions="
                f"{len(approval_command_generation_conditions)}",
                "real approval artifacts are not generated by this criteria model",
            ),
        ),
        LiveOrderRealApprovalEnablementCriteriaSection(
            section_id="checks",
            title="Check Results",
            lines=tuple(f"{check.name}: {check.passed}" for check in check_results),
        ),
        LiveOrderRealApprovalEnablementCriteriaSection(
            section_id="blocked_reasons",
            title="Blocked Reasons",
            lines=blocked,
        ),
    )


def _validate_criteria(criteria: LiveOrderRealApprovalEnablementCriteria) -> None:
    for label, value in (
        ("criteria_id", criteria.criteria_id),
        ("summary", criteria.summary),
        ("recommended_next_step", criteria.recommended_next_step),
    ):
        _require_non_empty(label, value)
    if not criteria.criteria_id.startswith(
        LIVE_ORDER_REAL_APPROVAL_ENABLEMENT_CRITERIA_ID_PREFIX
    ):
        raise LiveVerificationValidationError("criteria_id has invalid prefix")
    _ensure_aware(criteria.created_at)
    if criteria.allowed_for_live is not False:
        raise LiveVerificationValidationError("allowed_for_live must be False")
    if criteria.approval_gate_enabled is not False:
        raise LiveVerificationValidationError("approval_gate_enabled must be False")
    if criteria.approval_gate_issued is not False:
        raise LiveVerificationValidationError("approval_gate_issued must be False")
    for field_name in (
        "approval_id_generated",
        "approval_command_generated",
        "approval_command_copyable",
        "approval_command_executable",
        "usable_approval_artifacts_generated",
        "real_approval_artifacts_available",
        "post_executed",
        "live_order_once_called",
        "private_api_called",
        "broker_called",
        "read_only_api_called",
        "public_api_called",
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(criteria, field_name) is not False:
            raise LiveVerificationValidationError(f"{field_name} must be False")
    for field_name in (
        "approval_gate_enablement_planned",
        "approval_gate_enablement_deferred_to_future_step",
        "approval_id_generation_planned",
        "approval_id_generation_deferred_to_future_step",
        "approval_command_generation_planned",
        "approval_command_generation_deferred_to_future_step",
        "approval_command_template_only",
        "requires_human_approval",
        "explicit_user_confirmation_required",
        "fresh_preflight_before_enablement_required",
        "implementation_readiness_review_required",
        "post_enablement_safety_review_required",
        "post_approval_final_dynamic_preflight_required",
        "one_shot_post_separate_step_required",
        "post_reconciliation_separate_step_required",
        "final_report_separate_step_required",
        "dry_run_only",
        "exact_match_required",
        "same_session_required",
        "post_reconciliation_required",
    ):
        if getattr(criteria, field_name) is not True:
            raise LiveVerificationValidationError(f"{field_name} must be True")
    if criteria.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("ttl_seconds must be 300")
    if criteria.post_attempt_limit != 1:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if set(APPROVAL_ACK_TOKENS) - set(criteria.required_ack_tokens):
        raise LiveVerificationValidationError("required_ack_tokens missing token")
    if not criteria.check_results:
        raise LiveVerificationValidationError("check_results required")
    if not criteria.sections:
        raise LiveVerificationValidationError("sections required")
    if not _display_forbidden_fields_are_complete(criteria.display_forbidden_fields):
        raise LiveVerificationValidationError("display forbidden fields incomplete")


def _check(
    name: str,
    passed: bool,
    reason: str,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealApprovalEnablementCriteriaCheckResult:
    return LiveOrderRealApprovalEnablementCriteriaCheckResult(
        name=name,
        passed=passed,
        reason=reason,
        sanitized_value=sanitized_value,
        expected=expected,
    )


def _display_forbidden_fields_are_complete(fields: tuple[str, ...]) -> bool:
    lowered = " ".join(fields).lower()
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
    return all(marker in lowered for marker in required_markers)


def _text_from(source: object, attr: str) -> str:
    value = getattr(source, attr, "")
    if value is None:
        return ""
    return str(value)


def _int_from(source: object, attr: str) -> int:
    value = getattr(source, attr, 0)
    if type(value) is not int:
        return 0
    return value


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _add_reason(
    reasons: list[str],
    reason: LiveOrderRealApprovalEnablementCriteriaBlockReason,
) -> None:
    if reason.value not in reasons:
        reasons.append(reason.value)


def _bool_text(value: bool) -> str:
    return "true" if value is True else "false"


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _require_non_empty(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{label} must be non-empty")
