"""Disabled real approval gate scaffold for Step 5W."""

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
from app.live_verification.live_order_real_approval_implementation_readiness import (
    LiveOrderRealApprovalImplementationReadinessReview,
    LiveOrderRealApprovalImplementationReadinessStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

ReadinessStatus = LiveOrderRealApprovalImplementationReadinessStatus

LIVE_ORDER_REAL_APPROVAL_DISABLED_SCAFFOLD_ID_PREFIX = "LORADS-"

DEFAULT_REAL_APPROVAL_DISABLED_SCAFFOLD_FUTURE_ENABLEMENT_REQUIREMENTS = (
    "explicit future user instruction required",
    "fresh pre-approval preflight must be re-run in a future separate step",
    "implementation readiness review must be rechecked",
    "real approval gate enablement must be a separate step",
    "real approval_id generation must be a separate step",
    "real approval command generation must be a separate step",
    "real approval command exact match validation required",
    "ttl_seconds must remain 300",
    "same Codex session required",
    "post-approval final dynamic preflight required",
    "one-shot POST remains a separate step",
    "post reconciliation remains a separate step",
)

DEFAULT_REAL_APPROVAL_DISABLED_SCAFFOLD_DISABLED_REASONS = (
    "scaffold intentionally disabled",
    "real approval artifacts are not generated in this step",
    "approval command is not copyable",
    "live POST is not authorized",
    "API calls are not allowed",
    "future enablement requires separate explicit user instruction",
)

REAL_APPROVAL_DISABLED_SCAFFOLD_DISPLAY_ALLOWED_FIELDS = (
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
    "scaffold_status",
    "scaffold_ready",
    "eligible_for_future_enablement_planning",
    "allowed_for_live=false",
    "approval_gate_enabled=false",
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
    "post_attempt_limit",
    "post_executed=false",
    "live_order_once_called=false",
    "private_api_called=false",
    "broker_called=false",
    "read_only_api_called=false",
    "public_api_called=false",
    "future_enablement_requirements",
    "disabled_reasons",
    "check_results",
    "blocked_reasons",
    "recommended_next_step",
)

REAL_APPROVAL_DISABLED_SCAFFOLD_DISPLAY_FORBIDDEN_FIELDS = (
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


class LiveOrderRealApprovalDisabledScaffoldStatus(str, Enum):
    READY_FOR_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD_REVIEW = (
        "READY_FOR_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD_REVIEW"
    )
    BLOCKED_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD = (
        "BLOCKED_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD"
    )


ScaffoldStatus = LiveOrderRealApprovalDisabledScaffoldStatus


class LiveOrderRealApprovalDisabledScaffoldBlockReason(str, Enum):
    MISSING_IMPLEMENTATION_READINESS_REVIEW = (
        "missing_implementation_readiness_review"
    )
    IMPLEMENTATION_READINESS_REVIEW_NOT_READY = (
        "implementation_readiness_review_not_ready"
    )
    IMPLEMENTATION_READINESS_REVIEW_NOT_ELIGIBLE = (
        "implementation_readiness_review_not_eligible"
    )
    REVIEW_ALLOWS_LIVE = "review_allows_live"
    REVIEW_NOT_DRY_RUN = "review_not_dry_run"
    APPROVAL_GATE_ENABLED = "approval_gate_enabled"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_ID_ALREADY_GENERATED = "approval_id_already_generated"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
    APPROVAL_COMMAND_COPYABLE = "approval_command_copyable"
    APPROVAL_COMMAND_EXECUTABLE = "approval_command_executable"
    USABLE_APPROVAL_ARTIFACTS_GENERATED = "usable_approval_artifacts_generated"
    REAL_APPROVAL_ARTIFACTS_AVAILABLE = "real_approval_artifacts_available"
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
    MISSING_FUTURE_ENABLEMENT_REQUIREMENTS = (
        "missing_future_enablement_requirements"
    )
    MISSING_DISABLED_REASONS = "missing_disabled_reasons"


BlockReason = LiveOrderRealApprovalDisabledScaffoldBlockReason


@dataclass(frozen=True)
class LiveOrderRealApprovalDisabledScaffoldCheckResult:
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
class LiveOrderRealApprovalDisabledScaffoldSection:
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
class LiveOrderRealApprovalDisabledScaffold:
    scaffold_id: str
    created_at: datetime
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
    scaffold_status: LiveOrderRealApprovalDisabledScaffoldStatus
    scaffold_ready: bool
    eligible_for_future_enablement_planning: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
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
    approval_command_executable: bool
    usable_approval_artifacts_generated: bool
    real_approval_artifacts_available: bool
    requires_human_approval: bool
    explicit_user_confirmation_required: bool
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
    future_enablement_requirements: tuple[str, ...]
    disabled_reasons: tuple[str, ...]
    check_results: tuple[LiveOrderRealApprovalDisabledScaffoldCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApprovalDisabledScaffoldSection, ...]

    def __post_init__(self) -> None:
        _validate_scaffold(self)


@dataclass(frozen=True)
class LiveOrderRealApprovalDisabledScaffoldBuildResult:
    scaffold: LiveOrderRealApprovalDisabledScaffold
    scaffold_id: str
    scaffold_status: LiveOrderRealApprovalDisabledScaffoldStatus
    scaffold_ready: bool
    eligible_for_future_enablement_planning: bool
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
        if self.scaffold.scaffold_id != self.scaffold_id:
            raise LiveVerificationValidationError("scaffold_id mismatch")
        if self.scaffold.scaffold_status is not self.scaffold_status:
            raise LiveVerificationValidationError("scaffold_status mismatch")
        if self.scaffold.scaffold_ready is not self.scaffold_ready:
            raise LiveVerificationValidationError("scaffold_ready mismatch")
        if (
            self.scaffold.eligible_for_future_enablement_planning
            is not self.eligible_for_future_enablement_planning
        ):
            raise LiveVerificationValidationError("scaffold eligibility mismatch")
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
        if self.scaffold.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.scaffold.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_approval_disabled_scaffold(
    *,
    implementation_readiness_review: (
        LiveOrderRealApprovalImplementationReadinessReview | None
    ),
    created_at: datetime | None = None,
    future_enablement_requirements: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_DISABLED_SCAFFOLD_FUTURE_ENABLEMENT_REQUIREMENTS,
    disabled_reasons: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_DISABLED_SCAFFOLD_DISABLED_REASONS,
    approval_gate_enabled: bool = False,
    approval_command_executable: bool = False,
    usable_approval_artifacts_generated: bool = False,
    real_approval_artifacts_available: bool = False,
    post_attempt_limit: int = 1,
    retry_allowed: bool = False,
    loop_allowed: bool = False,
    add_order_allowed: bool = False,
    change_order_allowed: bool = False,
    cancel_order_allowed: bool = False,
    close_order_allowed: bool = False,
    post_reconciliation_required: bool = True,
) -> LiveOrderRealApprovalDisabledScaffoldBuildResult:
    """Build a disabled scaffold without real approval artifacts or API calls."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    blocked_reasons = _merge_reasons(
        _review_blocked_reasons(implementation_readiness_review),
        _review_existing_reasons(implementation_readiness_review),
        _scaffold_constraint_reasons(
            implementation_readiness_review=implementation_readiness_review,
            future_enablement_requirements=future_enablement_requirements,
            disabled_reasons=disabled_reasons,
            approval_gate_enabled=approval_gate_enabled,
            approval_command_executable=approval_command_executable,
            usable_approval_artifacts_generated=usable_approval_artifacts_generated,
            real_approval_artifacts_available=real_approval_artifacts_available,
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
        implementation_readiness_review=implementation_readiness_review,
        future_enablement_requirements=future_enablement_requirements,
        disabled_reasons=disabled_reasons,
        approval_gate_enabled=approval_gate_enabled,
        approval_command_executable=approval_command_executable,
        usable_approval_artifacts_generated=usable_approval_artifacts_generated,
        real_approval_artifacts_available=real_approval_artifacts_available,
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
        scaffold_status = ScaffoldStatus.BLOCKED_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD
        scaffold_ready = False
        eligible = False
        recommended_next_step = "fix_implementation_readiness_blockers_no_post"
        summary = (
            "blocked disabled real approval scaffold; no real approval artifact, "
            "API call, live runner call, or post is allowed"
        )
    else:
        scaffold_status = (
            ScaffoldStatus.READY_FOR_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD_REVIEW
        )
        scaffold_ready = True
        eligible = True
        recommended_next_step = (
            "review_disabled_scaffold_then_stop_before_any_real_approval_artifact_generation"
        )
        summary = (
            "ready disabled real approval scaffold review only; approval gate "
            "enablement and live post remain disallowed"
        )

    scaffold_id = make_live_order_real_approval_disabled_scaffold_id(
        implementation_readiness_review_id=_text_from(
            implementation_readiness_review,
            "review_id",
        ),
        candidate_id=_text_from(implementation_readiness_review, "candidate_id"),
        created_at=created,
        scaffold_status=scaffold_status,
        blocked_reasons=blocked_reasons,
    )
    scaffold = LiveOrderRealApprovalDisabledScaffold(
        scaffold_id=scaffold_id,
        created_at=created,
        implementation_readiness_review_id=_text_from(
            implementation_readiness_review,
            "review_id",
        ),
        audit_id=_text_from(implementation_readiness_review, "audit_id"),
        package_id=_text_from(implementation_readiness_review, "package_id"),
        pre_approval_preflight_decision_id=_text_from(
            implementation_readiness_review,
            "pre_approval_preflight_decision_id",
        ),
        snapshot_id=_text_from(implementation_readiness_review, "snapshot_id"),
        plan_id=_text_from(implementation_readiness_review, "plan_id"),
        checkpoint_id=_text_from(implementation_readiness_review, "checkpoint_id"),
        chain_id=_text_from(implementation_readiness_review, "chain_id"),
        runbook_id=_text_from(implementation_readiness_review, "runbook_id"),
        boundary_id=_text_from(implementation_readiness_review, "boundary_id"),
        preflight_decision_id=_text_from(
            implementation_readiness_review,
            "preflight_decision_id",
        ),
        simulation_id=_text_from(implementation_readiness_review, "simulation_id"),
        preview_id=_text_from(implementation_readiness_review, "preview_id"),
        design_id=_text_from(implementation_readiness_review, "design_id"),
        handoff_id=_text_from(implementation_readiness_review, "handoff_id"),
        operator_review_id=_text_from(
            implementation_readiness_review,
            "operator_review_id",
        ),
        bundle_id=_text_from(implementation_readiness_review, "bundle_id"),
        candidate_review_id=_text_from(
            implementation_readiness_review,
            "candidate_review_id",
        ),
        candidate_id=_text_from(implementation_readiness_review, "candidate_id"),
        risk_decision_id=_text_from(
            implementation_readiness_review,
            "risk_decision_id",
        ),
        trace_id=_text_from(implementation_readiness_review, "trace_id"),
        session_policy_decision_id=_text_from(
            implementation_readiness_review,
            "session_policy_decision_id",
        ),
        source_signal_id=_text_from(
            implementation_readiness_review,
            "source_signal_id",
        ),
        source_type=_text_from(implementation_readiness_review, "source_type"),
        strategy_name=_text_from(implementation_readiness_review, "strategy_name"),
        symbol=_text_from(implementation_readiness_review, "symbol"),
        side=_text_from(implementation_readiness_review, "side"),
        size=_int_from(implementation_readiness_review, "size"),
        execution_type=_text_from(implementation_readiness_review, "execution_type"),
        scaffold_status=scaffold_status,
        scaffold_ready=scaffold_ready,
        eligible_for_future_enablement_planning=eligible,
        allowed_for_live=False,
        approval_gate_enabled=False,
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
        approval_command_executable=False,
        usable_approval_artifacts_generated=False,
        real_approval_artifacts_available=False,
        requires_human_approval=True,
        explicit_user_confirmation_required=True,
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
        display_allowed_fields=REAL_APPROVAL_DISABLED_SCAFFOLD_DISPLAY_ALLOWED_FIELDS,
        display_forbidden_fields=(
            REAL_APPROVAL_DISABLED_SCAFFOLD_DISPLAY_FORBIDDEN_FIELDS
        ),
        future_enablement_requirements=future_enablement_requirements,
        disabled_reasons=disabled_reasons,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
            future_enablement_requirements=future_enablement_requirements,
            disabled_reasons=disabled_reasons,
        ),
    )
    return LiveOrderRealApprovalDisabledScaffoldBuildResult(
        scaffold=scaffold,
        scaffold_id=scaffold.scaffold_id,
        scaffold_status=scaffold.scaffold_status,
        scaffold_ready=scaffold.scaffold_ready,
        eligible_for_future_enablement_planning=(
            scaffold.eligible_for_future_enablement_planning
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
        blocked_reasons=scaffold.blocked_reasons,
        recommended_next_step=scaffold.recommended_next_step,
    )


def render_live_order_real_approval_disabled_scaffold_markdown(
    scaffold: LiveOrderRealApprovalDisabledScaffold,
) -> str:
    """Render a sanitized disabled scaffold report."""
    blocked_text = ", ".join(scaffold.blocked_reasons) or "none"
    ack_lines = "\n".join(f"- {token}" for token in scaffold.required_ack_tokens)
    future_lines = "\n".join(
        f"- {item}" for item in scaffold.future_enablement_requirements
    )
    disabled_lines = "\n".join(f"- {item}" for item in scaffold.disabled_reasons)
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in scaffold.check_results
    )
    return "\n".join(
        (
            "# Step 5W Real Approval Disabled Scaffold",
            "",
            "This real approval gate scaffold is disabled and dry-run only.",
            "This scaffold does not call read-only API.",
            "This scaffold does not call Private API.",
            "This scaffold does not call live_order_once.",
            "This scaffold does not execute HTTP POST.",
            "This scaffold does not issue a real approval gate.",
            "This scaffold does not generate a real approval_id.",
            "This scaffold does not generate a real approval command.",
            "This scaffold does not provide copyable approval text.",
            "This scaffold does not authorize live POST.",
            "approval_gate_enabled=false.",
            "allowed_for_live=false.",
            "",
            f"scaffold_id: {scaffold.scaffold_id}",
            f"implementation_readiness_review_id: {scaffold.implementation_readiness_review_id}",
            f"audit_id: {scaffold.audit_id}",
            f"package_id: {scaffold.package_id}",
            f"pre_approval_preflight_decision_id: {scaffold.pre_approval_preflight_decision_id}",
            f"snapshot_id: {scaffold.snapshot_id}",
            f"plan_id: {scaffold.plan_id}",
            f"checkpoint_id: {scaffold.checkpoint_id}",
            f"chain_id: {scaffold.chain_id}",
            f"runbook_id: {scaffold.runbook_id}",
            f"boundary_id: {scaffold.boundary_id}",
            f"preflight_decision_id: {scaffold.preflight_decision_id}",
            f"simulation_id: {scaffold.simulation_id}",
            f"preview_id: {scaffold.preview_id}",
            f"design_id: {scaffold.design_id}",
            f"handoff_id: {scaffold.handoff_id}",
            f"operator_review_id: {scaffold.operator_review_id}",
            f"bundle_id: {scaffold.bundle_id}",
            f"candidate_review_id: {scaffold.candidate_review_id}",
            f"candidate_id: {scaffold.candidate_id}",
            f"risk_decision_id: {scaffold.risk_decision_id}",
            f"trace_id: {scaffold.trace_id}",
            f"session_policy_decision_id: {scaffold.session_policy_decision_id}",
            f"source_signal_id: {scaffold.source_signal_id}",
            f"source_type: {scaffold.source_type}",
            f"strategy_name: {scaffold.strategy_name}",
            f"symbol: {scaffold.symbol}",
            f"side: {scaffold.side}",
            f"size: {scaffold.size}",
            f"executionType: {scaffold.execution_type}",
            f"scaffold_status: {scaffold.scaffold_status.value}",
            f"scaffold_ready: {scaffold.scaffold_ready}",
            "eligible_for_future_enablement_planning: "
            f"{scaffold.eligible_for_future_enablement_planning}",
            f"allowed_for_live: {scaffold.allowed_for_live}",
            f"approval_gate_enabled: {scaffold.approval_gate_enabled}",
            f"approval_gate_issued: {scaffold.approval_gate_issued}",
            f"approval_id_generated: {scaffold.approval_id_generated}",
            f"approval_command_generated: {scaffold.approval_command_generated}",
            f"approval_command_copyable: {scaffold.approval_command_copyable}",
            f"approval_command_executable: {scaffold.approval_command_executable}",
            "usable_approval_artifacts_generated: "
            f"{scaffold.usable_approval_artifacts_generated}",
            f"real_approval_artifacts_available: {scaffold.real_approval_artifacts_available}",
            f"ttl_seconds: {scaffold.ttl_seconds}",
            f"exact_match_required: {scaffold.exact_match_required}",
            f"same_session_required: {scaffold.same_session_required}",
            f"post_attempt_limit: {scaffold.post_attempt_limit}",
            f"post_executed: {scaffold.post_executed}",
            f"live_order_once_called: {scaffold.live_order_once_called}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {scaffold.recommended_next_step}",
            "",
            "## Required ACK Tokens",
            ack_lines,
            "",
            "## Future Enablement Requirements",
            future_lines,
            "",
            "## Disabled Reasons",
            disabled_lines,
            "",
            "## Check Results",
            check_lines,
        ),
    )


def make_live_order_real_approval_disabled_scaffold_id(
    *,
    implementation_readiness_review_id: str,
    candidate_id: str,
    created_at: datetime,
    scaffold_status: LiveOrderRealApprovalDisabledScaffoldStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": _ensure_aware(created_at).isoformat(),
        "implementation_readiness_review_id": implementation_readiness_review_id,
        "scaffold_status": scaffold_status.value,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_DISABLED_SCAFFOLD_ID_PREFIX}{digest}"


def _review_blocked_reasons(
    review: LiveOrderRealApprovalImplementationReadinessReview | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(review, LiveOrderRealApprovalImplementationReadinessReview):
        _add_reason(reasons, BlockReason.MISSING_IMPLEMENTATION_READINESS_REVIEW)
        return tuple(reasons)
    if (
        review.readiness_status
        is not ReadinessStatus.READY_FOR_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW
        or review.readiness_ready is not True
    ):
        _add_reason(reasons, BlockReason.IMPLEMENTATION_READINESS_REVIEW_NOT_READY)
    if (
        review.eligible_for_future_real_approval_gate_implementation_step
        is not True
    ):
        _add_reason(reasons, BlockReason.IMPLEMENTATION_READINESS_REVIEW_NOT_ELIGIBLE)
    if review.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.REVIEW_ALLOWS_LIVE)
    if review.dry_run_only is not True:
        _add_reason(reasons, BlockReason.REVIEW_NOT_DRY_RUN)
    for field_value, reason in (
        (review.approval_gate_issued, BlockReason.APPROVAL_GATE_ALREADY_ISSUED),
        (review.approval_id_generated, BlockReason.APPROVAL_ID_ALREADY_GENERATED),
        (
            review.approval_command_generated,
            BlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (review.approval_command_copyable, BlockReason.APPROVAL_COMMAND_COPYABLE),
    ):
        if field_value is not False:
            _add_reason(reasons, reason)
    if review.approval_id_generation_deferred_to_future_step is not True:
        _add_reason(reasons, BlockReason.APPROVAL_ID_GENERATION_NOT_DEFERRED)
    if review.approval_command_generation_deferred_to_future_step is not True:
        _add_reason(reasons, BlockReason.APPROVAL_COMMAND_GENERATION_NOT_DEFERRED)
    if review.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SYMBOL)
    if review.side not in {LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value}:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIDE)
    if review.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIZE)
    if review.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_EXECUTION_TYPE)
    return tuple(reasons)


def _review_existing_reasons(
    review: LiveOrderRealApprovalImplementationReadinessReview | None,
) -> tuple[str, ...]:
    if not isinstance(review, LiveOrderRealApprovalImplementationReadinessReview):
        return ()
    return tuple(review.blocked_reasons)


def _scaffold_constraint_reasons(
    *,
    implementation_readiness_review: LiveOrderRealApprovalImplementationReadinessReview
    | None,
    future_enablement_requirements: tuple[str, ...],
    disabled_reasons: tuple[str, ...],
    approval_gate_enabled: bool,
    approval_command_executable: bool,
    usable_approval_artifacts_generated: bool,
    real_approval_artifacts_available: bool,
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
    if isinstance(
        implementation_readiness_review,
        LiveOrderRealApprovalImplementationReadinessReview,
    ):
        review = implementation_readiness_review
        if review.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
            _add_reason(reasons, BlockReason.INVALID_TTL_SECONDS)
        if review.exact_match_required is not True:
            _add_reason(reasons, BlockReason.EXACT_MATCH_NOT_REQUIRED)
        if review.same_session_required is not True:
            _add_reason(reasons, BlockReason.SAME_SESSION_NOT_REQUIRED)
        if set(APPROVAL_ACK_TOKENS) - set(review.required_ack_tokens):
            _add_reason(reasons, BlockReason.MISSING_ACK_TOKEN)
        if not _display_forbidden_fields_are_complete(review.display_forbidden_fields):
            _add_reason(reasons, BlockReason.DISPLAY_FORBIDDEN_FIELDS_INCOMPLETE)
        for flag, reason in (
            (review.post_executed, BlockReason.POST_ALREADY_EXECUTED),
            (review.live_order_once_called, BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED),
            (review.private_api_called, BlockReason.PRIVATE_API_ALREADY_CALLED),
            (review.broker_called, BlockReason.BROKER_ALREADY_CALLED),
            (review.read_only_api_called, BlockReason.READ_ONLY_API_ALREADY_CALLED),
            (review.public_api_called, BlockReason.PUBLIC_API_ALREADY_CALLED),
        ):
            if flag is not False:
                _add_reason(reasons, reason)
    for flag, reason in (
        (approval_gate_enabled, BlockReason.APPROVAL_GATE_ENABLED),
        (approval_command_executable, BlockReason.APPROVAL_COMMAND_EXECUTABLE),
        (
            usable_approval_artifacts_generated,
            BlockReason.USABLE_APPROVAL_ARTIFACTS_GENERATED,
        ),
        (
            real_approval_artifacts_available,
            BlockReason.REAL_APPROVAL_ARTIFACTS_AVAILABLE,
        ),
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
    if not future_enablement_requirements:
        _add_reason(reasons, BlockReason.MISSING_FUTURE_ENABLEMENT_REQUIREMENTS)
    if not disabled_reasons:
        _add_reason(reasons, BlockReason.MISSING_DISABLED_REASONS)
    return tuple(reasons)


def _build_check_results(
    *,
    implementation_readiness_review: LiveOrderRealApprovalImplementationReadinessReview
    | None,
    future_enablement_requirements: tuple[str, ...],
    disabled_reasons: tuple[str, ...],
    approval_gate_enabled: bool,
    approval_command_executable: bool,
    usable_approval_artifacts_generated: bool,
    real_approval_artifacts_available: bool,
    post_attempt_limit: int,
    retry_allowed: bool,
    loop_allowed: bool,
    add_order_allowed: bool,
    change_order_allowed: bool,
    cancel_order_allowed: bool,
    close_order_allowed: bool,
    post_reconciliation_required: bool,
) -> tuple[LiveOrderRealApprovalDisabledScaffoldCheckResult, ...]:
    review_ready = (
        isinstance(
            implementation_readiness_review,
            LiveOrderRealApprovalImplementationReadinessReview,
        )
        and implementation_readiness_review.readiness_status
        is ReadinessStatus.READY_FOR_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW
        and implementation_readiness_review.readiness_ready is True
        and (
            implementation_readiness_review.eligible_for_future_real_approval_gate_implementation_step
            is True
        )
    )
    allowed_false = (
        isinstance(
            implementation_readiness_review,
            LiveOrderRealApprovalImplementationReadinessReview,
        )
        and implementation_readiness_review.allowed_for_live is False
    )
    no_api_calls = (
        isinstance(
            implementation_readiness_review,
            LiveOrderRealApprovalImplementationReadinessReview,
        )
        and implementation_readiness_review.live_order_once_called is False
        and implementation_readiness_review.private_api_called is False
        and implementation_readiness_review.broker_called is False
        and implementation_readiness_review.read_only_api_called is False
        and implementation_readiness_review.public_api_called is False
    )
    post_not_executed = (
        isinstance(
            implementation_readiness_review,
            LiveOrderRealApprovalImplementationReadinessReview,
        )
        and implementation_readiness_review.post_executed is False
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
        isinstance(
            implementation_readiness_review,
            LiveOrderRealApprovalImplementationReadinessReview,
        )
        and _display_forbidden_fields_are_complete(
            implementation_readiness_review.display_forbidden_fields
        )
    )
    ack_present = (
        isinstance(
            implementation_readiness_review,
            LiveOrderRealApprovalImplementationReadinessReview,
        )
        and not (
            set(APPROVAL_ACK_TOKENS)
            - set(implementation_readiness_review.required_ack_tokens)
        )
    )
    return (
        _check(
            "implementation_readiness_review_ready",
            review_ready,
            _bool_text(review_ready),
            "true",
        ),
        _check(
            "approval_gate_enabled_false",
            approval_gate_enabled is False,
            _bool_text(approval_gate_enabled is False),
            "true",
        ),
        _check(
            "allowed_for_live_false",
            allowed_false,
            _bool_text(allowed_false),
            "true",
        ),
        _review_bool_check(
            implementation_readiness_review,
            "approval_gate_not_issued",
            "approval_gate_issued",
            False,
        ),
        _review_bool_check(
            implementation_readiness_review,
            "approval_id_not_generated",
            "approval_id_generated",
            False,
        ),
        _review_bool_check(
            implementation_readiness_review,
            "approval_command_not_generated",
            "approval_command_generated",
            False,
        ),
        _review_bool_check(
            implementation_readiness_review,
            "approval_command_not_copyable",
            "approval_command_copyable",
            False,
        ),
        _check(
            "approval_command_not_executable",
            approval_command_executable is False,
            _bool_text(approval_command_executable is False),
            "true",
        ),
        _check(
            "no_usable_approval_artifacts_generated",
            usable_approval_artifacts_generated is False
            and real_approval_artifacts_available is False,
            _bool_text(
                usable_approval_artifacts_generated is False
                and real_approval_artifacts_available is False
            ),
            "true",
        ),
        _review_bool_check(
            implementation_readiness_review,
            "approval_id_generation_deferred",
            "approval_id_generation_deferred_to_future_step",
            True,
        ),
        _review_bool_check(
            implementation_readiness_review,
            "approval_command_generation_deferred",
            "approval_command_generation_deferred_to_future_step",
            True,
        ),
        _check(
            "ttl_seconds_300",
            _attr(implementation_readiness_review, "ttl_seconds")
            == APPROVAL_GATE_TTL_SECONDS,
            _attr(implementation_readiness_review, "ttl_seconds", "missing"),
            str(APPROVAL_GATE_TTL_SECONDS),
        ),
        _review_bool_check(
            implementation_readiness_review,
            "exact_match_required",
            "exact_match_required",
            True,
        ),
        _review_bool_check(
            implementation_readiness_review,
            "same_session_required",
            "same_session_required",
            True,
        ),
        _check(
            "required_ack_tokens_present",
            ack_present,
            _ack_count_text(implementation_readiness_review),
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
            "future_enablement_requirements_present",
            bool(future_enablement_requirements),
            str(len(future_enablement_requirements)),
            "non-empty",
        ),
        _check(
            "disabled_reasons_present",
            bool(disabled_reasons),
            str(len(disabled_reasons)),
            "non-empty",
        ),
    )


def _build_sections(
    *,
    check_results: tuple[LiveOrderRealApprovalDisabledScaffoldCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
    future_enablement_requirements: tuple[str, ...],
    disabled_reasons: tuple[str, ...],
) -> tuple[LiveOrderRealApprovalDisabledScaffoldSection, ...]:
    blocked_text = ", ".join(blocked_reasons) if blocked_reasons else "none"
    failed_checks = tuple(check.name for check in check_results if not check.passed)
    failed_text = ", ".join(failed_checks) if failed_checks else "none"
    return (
        LiveOrderRealApprovalDisabledScaffoldSection(
            section_id="disabled_artifact_boundary",
            title="Disabled Artifact Boundary",
            lines=(
                "approval_gate_enabled: False",
                "approval_gate_issued: False",
                "approval_id_generated: False",
                "approval_command_generated: False",
                "approval_command_copyable: False",
                "approval_command_executable: False",
                "usable_approval_artifacts_generated: False",
                "real_approval_artifacts_available: False",
            ),
        ),
        LiveOrderRealApprovalDisabledScaffoldSection(
            section_id="future_enablement_boundary",
            title="Future Enablement Boundary",
            lines=(
                "future_explicit_user_instruction_required: True",
                f"future_enablement_requirements_count: {len(future_enablement_requirements)}",
                f"disabled_reasons_count: {len(disabled_reasons)}",
            ),
        ),
        LiveOrderRealApprovalDisabledScaffoldSection(
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
        LiveOrderRealApprovalDisabledScaffoldSection(
            section_id="decision",
            title="Decision",
            lines=(
                f"failed_checks: {failed_text}",
                f"blocked_reasons: {blocked_text}",
                f"recommended_next_step: {recommended_next_step}",
            ),
        ),
    )


def _validate_scaffold(scaffold: LiveOrderRealApprovalDisabledScaffold) -> None:
    for field_name in (
        "scaffold_id",
        "implementation_readiness_review_id",
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
        _require_non_empty(field_name, getattr(scaffold, field_name))
    if not isinstance(scaffold.created_at, datetime):
        raise LiveVerificationValidationError("created_at must be datetime")
    if type(scaffold.scaffold_ready) is not bool:
        raise LiveVerificationValidationError("scaffold_ready must be bool")
    if type(scaffold.eligible_for_future_enablement_planning) is not bool:
        raise LiveVerificationValidationError("scaffold eligibility must be bool")
    for field_name, expected in (
        ("allowed_for_live", False),
        ("approval_gate_enabled", False),
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
        ("approval_command_executable", False),
        ("usable_approval_artifacts_generated", False),
        ("real_approval_artifacts_available", False),
        ("requires_human_approval", True),
        ("explicit_user_confirmation_required", True),
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
        if getattr(scaffold, field_name) is not expected:
            raise LiveVerificationValidationError(f"{field_name} must be {expected}")
    if scaffold.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("ttl_seconds must be 300")
    if scaffold.required_ack_tokens != APPROVAL_ACK_TOKENS:
        raise LiveVerificationValidationError("required_ack_tokens mismatch")
    if scaffold.post_attempt_limit != 1:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if scaffold.scaffold_ready and (
        scaffold.scaffold_status
        is not ScaffoldStatus.READY_FOR_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD_REVIEW
    ):
        raise LiveVerificationValidationError("ready scaffold status mismatch")
    if scaffold.scaffold_ready and scaffold.blocked_reasons:
        raise LiveVerificationValidationError("ready scaffold cannot have blockers")
    if not scaffold.display_allowed_fields:
        raise LiveVerificationValidationError("scaffold requires display allowed fields")
    if not scaffold.display_forbidden_fields:
        raise LiveVerificationValidationError(
            "scaffold requires display forbidden fields"
        )
    if scaffold.scaffold_ready and not scaffold.future_enablement_requirements:
        raise LiveVerificationValidationError(
            "scaffold requires future enablement requirements"
        )
    if scaffold.scaffold_ready and not scaffold.disabled_reasons:
        raise LiveVerificationValidationError("scaffold requires disabled reasons")
    if not scaffold.check_results:
        raise LiveVerificationValidationError("scaffold requires check_results")
    if not scaffold.sections:
        raise LiveVerificationValidationError("scaffold requires sections")


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


def _review_bool_check(
    review: LiveOrderRealApprovalImplementationReadinessReview | None,
    name: str,
    field_name: str,
    expected: bool,
) -> LiveOrderRealApprovalDisabledScaffoldCheckResult:
    actual = _attr(review, field_name, "missing")
    passed = actual is expected
    return _check(name, passed, _bool_text(passed), "true")


def _check(
    name: str,
    passed: bool,
    sanitized_value: object,
    expected: str,
) -> LiveOrderRealApprovalDisabledScaffoldCheckResult:
    return LiveOrderRealApprovalDisabledScaffoldCheckResult(
        name=name,
        passed=passed,
        reason="pass" if passed else "blocked",
        sanitized_value=str(sanitized_value),
        expected=expected,
    )


def _add_reason(
    reasons: list[str],
    reason: LiveOrderRealApprovalDisabledScaffoldBlockReason,
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
    review: LiveOrderRealApprovalImplementationReadinessReview | None,
) -> str:
    if not isinstance(review, LiveOrderRealApprovalImplementationReadinessReview):
        return "missing"
    return str(len(review.required_ack_tokens))


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{name} must be non-empty")


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
