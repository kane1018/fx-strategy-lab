"""Real approval gate generation package dry-run model for Step 5T."""

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
from app.live_verification.live_order_pre_approval_fresh_preflight import (
    LiveOrderPreApprovalFreshPreflightDecision,
    LiveOrderPreApprovalFreshPreflightStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

PreApprovalStatus = LiveOrderPreApprovalFreshPreflightStatus

LIVE_ORDER_REAL_APPROVAL_GATE_GENERATION_PACKAGE_ID_PREFIX = "LORAGG-"
APPROVAL_ID_PLACEHOLDER_LABEL = (
    "<APPROVAL_ID_GENERATED_IN_FUTURE_REAL_GATE_STEP>"
)
APPROVAL_COMMAND_TEMPLATE_LABEL = (
    "<APPROVAL_COMMAND_GENERATED_IN_FUTURE_REAL_GATE_STEP>"
)
APPROVAL_COMMAND_DISPLAY_MODE = "non_copyable_label_only"

REQUIRED_REAL_APPROVAL_GATE_GENERATION_PACKAGE_PHASE_IDS = (
    "confirm_pre_approval_fresh_preflight_ready",
    "stop_before_real_approval_gate_generation",
    "future_generate_real_approval_id",
    "future_generate_real_approval_command",
    "future_display_real_approval_gate",
    "future_validate_exact_match_approval",
    "future_post_approval_final_dynamic_preflight",
    "future_one_shot_post_separate_step",
    "future_post_reconciliation",
    "future_final_report_and_stop",
)

DEFAULT_REAL_APPROVAL_GATE_GENERATION_PACKAGE_GO_CONDITIONS = (
    "pre-approval fresh preflight decision is ready",
    "explicit future user instruction is required before real approval gate generation",
    "approval_id generation is deferred to a future separate step",
    "approval command generation is deferred to a future separate step",
    "exact match is required",
    "same Codex session is required",
    "TTL is 300 seconds",
    "all ACK tokens are required",
    "future approval command must be a single exact line",
    "post-approval final dynamic preflight is required",
    "one-shot POST remains a separate future step",
)

DEFAULT_REAL_APPROVAL_GATE_GENERATION_PACKAGE_NO_GO_CONDITIONS = (
    "pre-approval fresh preflight is blocked",
    "no explicit future user instruction",
    "stale pre-approval fresh preflight",
    "approval artifact already generated",
    "any API/broker/live_order_once already called",
    "post already executed",
    "symbol/side/size/executionType mismatch",
    "raw response or real ID display/storage required",
    "retry/loop/add/change/cancel/close needed",
)

DEFAULT_REAL_APPROVAL_GATE_GENERATION_PACKAGE_STOP_CONDITIONS = (
    "no explicit future request",
    "stale pre-approval fresh preflight",
    "approval id or command would be generated before the future explicit step",
    "exact match or same session cannot be guaranteed",
    "ACK token set incomplete",
    "secret, raw data, or real ID exposure risk",
    "result_unknown",
    "need to exceed one POST attempt",
)

REAL_APPROVAL_GATE_GENERATION_PACKAGE_DISPLAY_ALLOWED_FIELDS = (
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
    "package_status",
    "package_ready",
    "eligible_for_future_real_approval_gate_generation",
    "allowed_for_live=false",
    "approval_id_generation_deferred_to_future_step",
    "approval_command_generation_deferred_to_future_step",
    "ttl_seconds",
    "exact_match_required",
    "same_session_required",
    "required_ack_tokens",
    "approval_id_placeholder_label",
    "approval_command_template_label",
    "approval_command_display_mode",
    "display_allowed_fields",
    "display_forbidden_fields",
    "phases",
    "go_conditions",
    "no_go_conditions",
    "stop_conditions",
    "check_results",
    "blocked_reasons",
    "recommended_next_step",
)

REAL_APPROVAL_GATE_GENERATION_PACKAGE_DISPLAY_FORBIDDEN_FIELDS = (
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


class LiveOrderRealApprovalGateGenerationPackageStatus(str, Enum):
    READY_FOR_REAL_APPROVAL_GATE_GENERATION_PACKAGE_REVIEW = (
        "READY_FOR_REAL_APPROVAL_GATE_GENERATION_PACKAGE_REVIEW"
    )
    BLOCKED_REAL_APPROVAL_GATE_GENERATION_PACKAGE = (
        "BLOCKED_REAL_APPROVAL_GATE_GENERATION_PACKAGE"
    )


PackageStatus = LiveOrderRealApprovalGateGenerationPackageStatus


class LiveOrderRealApprovalGateGenerationPackageBlockReason(str, Enum):
    MISSING_PRE_APPROVAL_FRESH_PREFLIGHT_DECISION = (
        "missing_pre_approval_fresh_preflight_decision"
    )
    PRE_APPROVAL_FRESH_PREFLIGHT_NOT_READY = (
        "pre_approval_fresh_preflight_not_ready"
    )
    PRE_APPROVAL_FRESH_PREFLIGHT_NOT_ELIGIBLE = (
        "pre_approval_fresh_preflight_not_eligible"
    )
    DECISION_ALLOWS_LIVE = "decision_allows_live"
    DECISION_NOT_DRY_RUN = "decision_not_dry_run"
    APPROVAL_GATE_ALREADY_ISSUED = "approval_gate_already_issued"
    APPROVAL_ID_ALREADY_GENERATED = "approval_id_already_generated"
    APPROVAL_COMMAND_ALREADY_GENERATED = "approval_command_already_generated"
    APPROVAL_COMMAND_COPYABLE = "approval_command_copyable"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    APPROVAL_ID_GENERATION_NOT_DEFERRED = "approval_id_generation_not_deferred"
    APPROVAL_COMMAND_GENERATION_NOT_DEFERRED = (
        "approval_command_generation_not_deferred"
    )
    INVALID_TTL_SECONDS = "invalid_ttl_seconds"
    EXACT_MATCH_NOT_REQUIRED = "exact_match_not_required"
    SAME_SESSION_NOT_REQUIRED = "same_session_not_required"
    MISSING_ACK_TOKEN = "missing_ack_token"
    MISSING_APPROVAL_ID_PLACEHOLDER_LABEL = "missing_approval_id_placeholder_label"
    MISSING_APPROVAL_COMMAND_TEMPLATE_LABEL = (
        "missing_approval_command_template_label"
    )
    APPROVAL_COMMAND_DISPLAY_MODE_NOT_SAFE = "approval_command_display_mode_not_safe"
    MISSING_REQUIRED_PHASE = "missing_required_phase"
    MISSING_GO_CONDITIONS = "missing_go_conditions"
    MISSING_NO_GO_CONDITIONS = "missing_no_go_conditions"
    MISSING_STOP_CONDITIONS = "missing_stop_conditions"
    POST_ALREADY_EXECUTED = "post_already_executed"
    LIVE_ORDER_ONCE_ALREADY_CALLED = "live_order_once_already_called"
    PRIVATE_API_ALREADY_CALLED = "private_api_already_called"
    BROKER_ALREADY_CALLED = "broker_already_called"
    READ_ONLY_API_ALREADY_CALLED = "read_only_api_already_called"
    PUBLIC_API_ALREADY_CALLED = "public_api_already_called"


@dataclass(frozen=True)
class LiveOrderRealApprovalGateGenerationPackagePhase:
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
class LiveOrderRealApprovalGateGenerationPackageCheckResult:
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
class LiveOrderRealApprovalGateGenerationPackageSection:
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
class LiveOrderRealApprovalGateGenerationPackage:
    package_id: str
    created_at: datetime
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
    package_status: LiveOrderRealApprovalGateGenerationPackageStatus
    package_ready: bool
    eligible_for_future_real_approval_gate_generation: bool
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
    approval_id_placeholder_label: str
    approval_command_template_label: str
    approval_command_display_mode: str
    post_executed: bool
    live_order_once_called: bool
    private_api_called: bool
    broker_called: bool
    read_only_api_called: bool
    public_api_called: bool
    display_allowed_fields: tuple[str, ...]
    display_forbidden_fields: tuple[str, ...]
    go_conditions: tuple[str, ...]
    no_go_conditions: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    phases: tuple[LiveOrderRealApprovalGateGenerationPackagePhase, ...]
    check_results: tuple[LiveOrderRealApprovalGateGenerationPackageCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApprovalGateGenerationPackageSection, ...]

    def __post_init__(self) -> None:
        _validate_package(self)


@dataclass(frozen=True)
class LiveOrderRealApprovalGateGenerationPackageBuildResult:
    package: LiveOrderRealApprovalGateGenerationPackage
    package_id: str
    package_status: LiveOrderRealApprovalGateGenerationPackageStatus
    package_ready: bool
    eligible_for_future_real_approval_gate_generation: bool
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_copyable: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.package.package_id != self.package_id:
            raise LiveVerificationValidationError("package_id mismatch")
        if self.package.package_status is not self.package_status:
            raise LiveVerificationValidationError("package_status mismatch")
        if self.package.package_ready is not self.package_ready:
            raise LiveVerificationValidationError("package_ready mismatch")
        if (
            self.package.eligible_for_future_real_approval_gate_generation
            is not self.eligible_for_future_real_approval_gate_generation
        ):
            raise LiveVerificationValidationError("package eligibility mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("Step 5T never allows live execution")
        if self.approval_gate_issued is not False:
            raise LiveVerificationValidationError("Step 5T never issues approval gate")
        if self.approval_id_generated is not False:
            raise LiveVerificationValidationError("Step 5T never generates approval id")
        if self.approval_command_generated is not False:
            raise LiveVerificationValidationError(
                "Step 5T never generates approval command"
            )
        if self.approval_command_copyable is not False:
            raise LiveVerificationValidationError("Step 5T never creates copyable command")
        if self.package.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.package.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_approval_gate_generation_package(
    *,
    pre_approval_fresh_preflight_decision: (
        LiveOrderPreApprovalFreshPreflightDecision | None
    ),
    created_at: datetime | None = None,
    approval_id_generation_deferred_to_future_step: bool = True,
    approval_command_generation_deferred_to_future_step: bool = True,
    approval_gate_issued: bool = False,
    approval_id_generated: bool = False,
    approval_command_generated: bool = False,
    approval_command_copyable: bool = False,
    ttl_seconds: int = APPROVAL_GATE_TTL_SECONDS,
    exact_match_required: bool = True,
    same_session_required: bool = True,
    required_ack_tokens: tuple[str, ...] = APPROVAL_ACK_TOKENS,
    approval_id_placeholder_label: str = APPROVAL_ID_PLACEHOLDER_LABEL,
    approval_command_template_label: str = APPROVAL_COMMAND_TEMPLATE_LABEL,
    approval_command_display_mode: str = APPROVAL_COMMAND_DISPLAY_MODE,
    phases: tuple[
        LiveOrderRealApprovalGateGenerationPackagePhase,
        ...,
    ] | None = None,
    go_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_GATE_GENERATION_PACKAGE_GO_CONDITIONS,
    no_go_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_GATE_GENERATION_PACKAGE_NO_GO_CONDITIONS,
    stop_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_REAL_APPROVAL_GATE_GENERATION_PACKAGE_STOP_CONDITIONS,
    post_executed: bool = False,
    live_order_once_called: bool = False,
    private_api_called: bool = False,
    broker_called: bool = False,
    read_only_api_called: bool = False,
    public_api_called: bool = False,
) -> LiveOrderRealApprovalGateGenerationPackageBuildResult:
    """Build a sanitized package without issuing a real gate, id, or command."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    default_phases = build_default_real_approval_gate_generation_package_phases()
    input_phases = phases if phases is not None else default_phases
    blocked_reasons = _merge_reasons(
        _decision_blocked_reasons(pre_approval_fresh_preflight_decision),
        _decision_existing_reasons(pre_approval_fresh_preflight_decision),
        _package_constraint_reasons(
            approval_id_generation_deferred_to_future_step=(
                approval_id_generation_deferred_to_future_step
            ),
            approval_command_generation_deferred_to_future_step=(
                approval_command_generation_deferred_to_future_step
            ),
            approval_gate_issued=approval_gate_issued,
            approval_id_generated=approval_id_generated,
            approval_command_generated=approval_command_generated,
            approval_command_copyable=approval_command_copyable,
            ttl_seconds=ttl_seconds,
            exact_match_required=exact_match_required,
            same_session_required=same_session_required,
            required_ack_tokens=required_ack_tokens,
            approval_id_placeholder_label=approval_id_placeholder_label,
            approval_command_template_label=approval_command_template_label,
            approval_command_display_mode=approval_command_display_mode,
            phases=input_phases,
            go_conditions=go_conditions,
            no_go_conditions=no_go_conditions,
            stop_conditions=stop_conditions,
            post_executed=post_executed,
            live_order_once_called=live_order_once_called,
            private_api_called=private_api_called,
            broker_called=broker_called,
            read_only_api_called=read_only_api_called,
            public_api_called=public_api_called,
        ),
    )
    check_results = _build_check_results(
        decision=pre_approval_fresh_preflight_decision,
        approval_id_generation_deferred_to_future_step=(
            approval_id_generation_deferred_to_future_step
        ),
        approval_command_generation_deferred_to_future_step=(
            approval_command_generation_deferred_to_future_step
        ),
        approval_gate_issued=approval_gate_issued,
        approval_id_generated=approval_id_generated,
        approval_command_generated=approval_command_generated,
        approval_command_copyable=approval_command_copyable,
        ttl_seconds=ttl_seconds,
        exact_match_required=exact_match_required,
        same_session_required=same_session_required,
        required_ack_tokens=required_ack_tokens,
        post_executed=post_executed,
        live_order_once_called=live_order_once_called,
        private_api_called=private_api_called,
        broker_called=broker_called,
        read_only_api_called=read_only_api_called,
        public_api_called=public_api_called,
    )
    if blocked_reasons:
        package_status = (
        PackageStatus.BLOCKED_REAL_APPROVAL_GATE_GENERATION_PACKAGE
        )
        package_ready = False
        eligible = False
        recommended_next_step = (
            "fix_pre_approval_fresh_preflight_blockers_no_post"
        )
        summary = (
            "blocked real approval gate generation package; no approval gate, "
            "approval id, or approval command is generated"
        )
    else:
        package_status = (
        PackageStatus.READY_FOR_REAL_APPROVAL_GATE_GENERATION_PACKAGE_REVIEW
        )
        package_ready = True
        eligible = True
        recommended_next_step = (
            "stop_and_wait_for_explicit_user_instruction_for_future_real_approval_gate_generation_step"
        )
        summary = (
            "ready for real approval gate generation package review only; "
            "live post remains disallowed"
        )

    package_id = make_live_order_real_approval_gate_generation_package_id(
        pre_approval_preflight_decision_id=_text_from(
            pre_approval_fresh_preflight_decision,
            "decision_id",
        ),
        candidate_id=_ref_from(pre_approval_fresh_preflight_decision, "candidate_id"),
        created_at=created,
        package_status=package_status,
        blocked_reasons=blocked_reasons,
    )
    package = LiveOrderRealApprovalGateGenerationPackage(
        package_id=package_id,
        created_at=created,
        pre_approval_preflight_decision_id=_text_from(
            pre_approval_fresh_preflight_decision,
            "decision_id",
        ),
        snapshot_id=_text_from(pre_approval_fresh_preflight_decision, "snapshot_id"),
        plan_id=_text_from(pre_approval_fresh_preflight_decision, "plan_id"),
        checkpoint_id=_text_from(pre_approval_fresh_preflight_decision, "checkpoint_id"),
        chain_id=_text_from(pre_approval_fresh_preflight_decision, "chain_id"),
        runbook_id=_ref_from(pre_approval_fresh_preflight_decision, "runbook_id"),
        boundary_id=_ref_from(pre_approval_fresh_preflight_decision, "boundary_id"),
        preflight_decision_id=_ref_from(
            pre_approval_fresh_preflight_decision,
            "preflight_decision_id",
        ),
        simulation_id=_ref_from(pre_approval_fresh_preflight_decision, "simulation_id"),
        preview_id=_ref_from(pre_approval_fresh_preflight_decision, "preview_id"),
        design_id=_ref_from(pre_approval_fresh_preflight_decision, "design_id"),
        handoff_id=_ref_from(pre_approval_fresh_preflight_decision, "handoff_id"),
        operator_review_id=_ref_from(
            pre_approval_fresh_preflight_decision,
            "operator_review_id",
        ),
        bundle_id=_ref_from(pre_approval_fresh_preflight_decision, "bundle_id"),
        review_id=_ref_from(pre_approval_fresh_preflight_decision, "review_id"),
        candidate_id=_ref_from(pre_approval_fresh_preflight_decision, "candidate_id"),
        risk_decision_id=_ref_from(
            pre_approval_fresh_preflight_decision,
            "risk_decision_id",
        ),
        trace_id=_ref_from(pre_approval_fresh_preflight_decision, "trace_id"),
        session_policy_decision_id=_ref_from(
            pre_approval_fresh_preflight_decision,
            "session_policy_decision_id",
        ),
        source_signal_id=_ref_from(
            pre_approval_fresh_preflight_decision,
            "source_signal_id",
        ),
        source_type=_ref_from(pre_approval_fresh_preflight_decision, "source_type"),
        strategy_name=_ref_from(
            pre_approval_fresh_preflight_decision,
            "strategy_name",
        ),
        symbol=_text_from(pre_approval_fresh_preflight_decision, "symbol"),
        side=_text_from(pre_approval_fresh_preflight_decision, "side"),
        size=_int_from(pre_approval_fresh_preflight_decision, "size"),
        execution_type=_text_from(
            pre_approval_fresh_preflight_decision,
            "execution_type",
        ),
        package_status=package_status,
        package_ready=package_ready,
        eligible_for_future_real_approval_gate_generation=eligible,
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
        approval_id_placeholder_label=APPROVAL_ID_PLACEHOLDER_LABEL,
        approval_command_template_label=APPROVAL_COMMAND_TEMPLATE_LABEL,
        approval_command_display_mode=APPROVAL_COMMAND_DISPLAY_MODE,
        post_executed=False,
        live_order_once_called=False,
        private_api_called=False,
        broker_called=False,
        read_only_api_called=False,
        public_api_called=False,
        display_allowed_fields=REAL_APPROVAL_GATE_GENERATION_PACKAGE_DISPLAY_ALLOWED_FIELDS,
        display_forbidden_fields=REAL_APPROVAL_GATE_GENERATION_PACKAGE_DISPLAY_FORBIDDEN_FIELDS,
        go_conditions=go_conditions,
        no_go_conditions=no_go_conditions,
        stop_conditions=stop_conditions,
        phases=input_phases,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            phases=input_phases,
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
        ),
    )
    return LiveOrderRealApprovalGateGenerationPackageBuildResult(
        package=package,
        package_id=package.package_id,
        package_status=package.package_status,
        package_ready=package.package_ready,
        eligible_for_future_real_approval_gate_generation=(
            package.eligible_for_future_real_approval_gate_generation
        ),
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_copyable=False,
        blocked_reasons=package.blocked_reasons,
        recommended_next_step=package.recommended_next_step,
    )


def build_default_real_approval_gate_generation_package_phases() -> tuple[
    LiveOrderRealApprovalGateGenerationPackagePhase,
    ...,
]:
    return (
        LiveOrderRealApprovalGateGenerationPackagePhase(
            phase_id="confirm_pre_approval_fresh_preflight_ready",
            title="Confirm Pre-approval Fresh Preflight Ready",
            requirements=(
                "Step 5S decision must be ready",
                "allowed_for_live remains false",
            ),
        ),
        LiveOrderRealApprovalGateGenerationPackagePhase(
            phase_id="stop_before_real_approval_gate_generation",
            title="Stop Before Real Approval Gate Generation",
            requirements=(
                "Step 5T stops here",
                "future real approval gate generation requires separate explicit user request",
            ),
        ),
        LiveOrderRealApprovalGateGenerationPackagePhase(
            phase_id="future_generate_real_approval_id",
            title="Future Generate Real Approval Id",
            requirements=(
                "future separate Step only",
                "this package uses a placeholder label only",
            ),
        ),
        LiveOrderRealApprovalGateGenerationPackagePhase(
            phase_id="future_generate_real_approval_command",
            title="Future Generate Real Approval Command",
            requirements=(
                "future separate Step only",
                "this package uses a non-copyable label only",
            ),
        ),
        LiveOrderRealApprovalGateGenerationPackagePhase(
            phase_id="future_display_real_approval_gate",
            title="Future Display Real Approval Gate",
            requirements=(
                "future separate Step only",
                "display must keep secret, raw data, and real IDs hidden",
            ),
        ),
        LiveOrderRealApprovalGateGenerationPackagePhase(
            phase_id="future_validate_exact_match_approval",
            title="Future Validate Exact Match Approval",
            requirements=(
                "ttl_seconds=300",
                "same session and exact match required",
            ),
        ),
        LiveOrderRealApprovalGateGenerationPackagePhase(
            phase_id="future_post_approval_final_dynamic_preflight",
            title="Future Post Approval Final Dynamic Preflight",
            requirements=(
                "future separate Step only",
                "must occur after approval and before any future POST",
            ),
        ),
        LiveOrderRealApprovalGateGenerationPackagePhase(
            phase_id="future_one_shot_post_separate_step",
            title="Future One-shot POST Separate Step",
            requirements=(
                "future separate Step only",
                "retry, loop, add, change, cancel, and close remain forbidden",
            ),
        ),
        LiveOrderRealApprovalGateGenerationPackagePhase(
            phase_id="future_post_reconciliation",
            title="Future Post Reconciliation",
            requirements=(
                "future separate Step only",
                "raw response and real IDs remain hidden",
            ),
        ),
        LiveOrderRealApprovalGateGenerationPackagePhase(
            phase_id="future_final_report_and_stop",
            title="Future Final Report And Stop",
            requirements=(
                "future separate Step only",
                "result_unknown stops without retry or additional orders",
            ),
        ),
    )


def render_live_order_real_approval_gate_generation_package_markdown(
    package: LiveOrderRealApprovalGateGenerationPackage,
) -> str:
    """Render a sanitized generation package without real approval artifacts."""
    blocked_text = ", ".join(package.blocked_reasons) or "none"
    ack_lines = "\n".join(f"- {token}" for token in package.required_ack_tokens)
    phase_lines = "\n".join(
        f"- {phase.phase_id}: {phase.title}" for phase in package.phases
    )
    go_lines = "\n".join(f"- {condition}" for condition in package.go_conditions)
    no_go_lines = "\n".join(f"- {condition}" for condition in package.no_go_conditions)
    stop_lines = "\n".join(f"- {condition}" for condition in package.stop_conditions)
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in package.check_results
    )
    return "\n".join(
        (
            "# Step 5T Real Approval Gate Generation Package",
            "",
            "This real approval gate generation package is dry-run only.",
            "This package does not call read-only API.",
            "This package does not call public API.",
            "This package does not call Private API.",
            "This package does not call live_order_once.",
            "This package does not execute HTTP POST.",
            "This package does not issue a real approval gate.",
            "This package does not generate a real approval_id.",
            "This package does not generate a real approval command.",
            "This package does not provide copyable approval text.",
            "This package does not authorize live POST.",
            "allowed_for_live=false.",
            "",
            f"package_id: {package.package_id}",
            "pre_approval_preflight_decision_id: "
            f"{package.pre_approval_preflight_decision_id}",
            f"snapshot_id: {package.snapshot_id}",
            f"plan_id: {package.plan_id}",
            f"checkpoint_id: {package.checkpoint_id}",
            f"chain_id: {package.chain_id}",
            f"runbook_id: {package.runbook_id}",
            f"boundary_id: {package.boundary_id}",
            f"preflight_decision_id: {package.preflight_decision_id}",
            f"simulation_id: {package.simulation_id}",
            f"preview_id: {package.preview_id}",
            f"design_id: {package.design_id}",
            f"handoff_id: {package.handoff_id}",
            f"operator_review_id: {package.operator_review_id}",
            f"bundle_id: {package.bundle_id}",
            f"review_id: {package.review_id}",
            f"candidate_id: {package.candidate_id}",
            f"risk_decision_id: {package.risk_decision_id}",
            f"trace_id: {package.trace_id}",
            f"session_policy_decision_id: {package.session_policy_decision_id}",
            f"source_signal_id: {package.source_signal_id}",
            f"source_type: {package.source_type}",
            f"strategy_name: {package.strategy_name}",
            f"symbol: {package.symbol}",
            f"side: {package.side}",
            f"size: {package.size}",
            f"executionType: {package.execution_type}",
            f"package_status: {package.package_status.value}",
            f"package_ready: {package.package_ready}",
            "eligible_for_future_real_approval_gate_generation: "
            f"{package.eligible_for_future_real_approval_gate_generation}",
            f"allowed_for_live: {package.allowed_for_live}",
            "approval_id_generation_deferred_to_future_step: "
            f"{package.approval_id_generation_deferred_to_future_step}",
            "approval_command_generation_deferred_to_future_step: "
            f"{package.approval_command_generation_deferred_to_future_step}",
            f"ttl_seconds: {package.ttl_seconds}",
            f"exact_match_required: {package.exact_match_required}",
            f"same_session_required: {package.same_session_required}",
            f"approval_id_placeholder_label: {package.approval_id_placeholder_label}",
            "approval_command_template_label: "
            f"{package.approval_command_template_label}",
            f"approval_command_display_mode: {package.approval_command_display_mode}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {package.recommended_next_step}",
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


def make_live_order_real_approval_gate_generation_package_id(
    *,
    pre_approval_preflight_decision_id: str,
    candidate_id: str,
    created_at: datetime,
    package_status: LiveOrderRealApprovalGateGenerationPackageStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": _ensure_aware(created_at).isoformat(),
        "package_status": package_status.value,
        "pre_approval_preflight_decision_id": pre_approval_preflight_decision_id,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_GATE_GENERATION_PACKAGE_ID_PREFIX}{digest}"


def _decision_blocked_reasons(
    decision: LiveOrderPreApprovalFreshPreflightDecision | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(decision, LiveOrderPreApprovalFreshPreflightDecision):
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_PRE_APPROVAL_FRESH_PREFLIGHT_DECISION,
        )
        return tuple(reasons)
    if (
        decision.preflight_status
        is not PreApprovalStatus.READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW
        or decision.preflight_passed is not True
    ):
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.PRE_APPROVAL_FRESH_PREFLIGHT_NOT_READY,
        )
    if decision.eligible_for_future_real_approval_gate_generation is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.PRE_APPROVAL_FRESH_PREFLIGHT_NOT_ELIGIBLE,
        )
    if decision.allowed_for_live is not False:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.DECISION_ALLOWS_LIVE,
        )
    if decision.dry_run_only is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.DECISION_NOT_DRY_RUN,
        )
    for field_value, reason in (
        (
            decision.approval_gate_issued,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        ),
        (
            decision.approval_id_generated,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            decision.approval_command_generated,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            decision.approval_command_copyable,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_COPYABLE,
        ),
    ):
        if field_value is not False:
            _add_reason(reasons, reason)
    if decision.symbol != SUPPORTED_SYMBOL:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.UNSUPPORTED_SYMBOL,
        )
    if decision.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.UNSUPPORTED_SIDE,
        )
    if decision.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.UNSUPPORTED_SIZE,
        )
    if decision.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        )
    return tuple(reasons)


def _decision_existing_reasons(
    decision: LiveOrderPreApprovalFreshPreflightDecision | None,
) -> tuple[str, ...]:
    if not isinstance(decision, LiveOrderPreApprovalFreshPreflightDecision):
        return ()
    return tuple(decision.blocked_reasons)


def _package_constraint_reasons(
    *,
    approval_id_generation_deferred_to_future_step: bool,
    approval_command_generation_deferred_to_future_step: bool,
    approval_gate_issued: bool,
    approval_id_generated: bool,
    approval_command_generated: bool,
    approval_command_copyable: bool,
    ttl_seconds: int,
    exact_match_required: bool,
    same_session_required: bool,
    required_ack_tokens: tuple[str, ...],
    approval_id_placeholder_label: str,
    approval_command_template_label: str,
    approval_command_display_mode: str,
    phases: tuple[LiveOrderRealApprovalGateGenerationPackagePhase, ...],
    go_conditions: tuple[str, ...],
    no_go_conditions: tuple[str, ...],
    stop_conditions: tuple[str, ...],
    post_executed: bool,
    live_order_once_called: bool,
    private_api_called: bool,
    broker_called: bool,
    read_only_api_called: bool,
    public_api_called: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if approval_id_generation_deferred_to_future_step is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_ID_GENERATION_NOT_DEFERRED,
        )
    if approval_command_generation_deferred_to_future_step is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_GENERATION_NOT_DEFERRED,
        )
    for flag, reason in (
        (
            approval_gate_issued,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        ),
        (
            approval_id_generated,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            approval_command_generated,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            approval_command_copyable,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_COPYABLE,
        ),
        (
            post_executed,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.POST_ALREADY_EXECUTED,
        ),
        (
            live_order_once_called,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        ),
        (
            private_api_called,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.PRIVATE_API_ALREADY_CALLED,
        ),
        (
            broker_called,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.BROKER_ALREADY_CALLED,
        ),
        (
            read_only_api_called,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.READ_ONLY_API_ALREADY_CALLED,
        ),
        (
            public_api_called,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.PUBLIC_API_ALREADY_CALLED,
        ),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    if ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.INVALID_TTL_SECONDS,
        )
    if exact_match_required is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.EXACT_MATCH_NOT_REQUIRED,
        )
    if same_session_required is not True:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.SAME_SESSION_NOT_REQUIRED,
        )
    if set(APPROVAL_ACK_TOKENS) - set(required_ack_tokens):
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_ACK_TOKEN,
        )
    if approval_id_placeholder_label != APPROVAL_ID_PLACEHOLDER_LABEL:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_APPROVAL_ID_PLACEHOLDER_LABEL,
        )
    if approval_command_template_label != APPROVAL_COMMAND_TEMPLATE_LABEL:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_APPROVAL_COMMAND_TEMPLATE_LABEL,
        )
    if approval_command_display_mode != APPROVAL_COMMAND_DISPLAY_MODE:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.APPROVAL_COMMAND_DISPLAY_MODE_NOT_SAFE,
        )
    phase_ids = {phase.phase_id for phase in phases}
    if set(REQUIRED_REAL_APPROVAL_GATE_GENERATION_PACKAGE_PHASE_IDS) - phase_ids:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_REQUIRED_PHASE,
        )
    if not go_conditions:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_GO_CONDITIONS,
        )
    if not no_go_conditions:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_NO_GO_CONDITIONS,
        )
    if not stop_conditions:
        _add_reason(
            reasons,
            LiveOrderRealApprovalGateGenerationPackageBlockReason.MISSING_STOP_CONDITIONS,
        )
    return tuple(reasons)


def _build_check_results(
    *,
    decision: LiveOrderPreApprovalFreshPreflightDecision | None,
    approval_id_generation_deferred_to_future_step: bool,
    approval_command_generation_deferred_to_future_step: bool,
    approval_gate_issued: bool,
    approval_id_generated: bool,
    approval_command_generated: bool,
    approval_command_copyable: bool,
    ttl_seconds: int,
    exact_match_required: bool,
    same_session_required: bool,
    required_ack_tokens: tuple[str, ...],
    post_executed: bool,
    live_order_once_called: bool,
    private_api_called: bool,
    broker_called: bool,
    read_only_api_called: bool,
    public_api_called: bool,
) -> tuple[LiveOrderRealApprovalGateGenerationPackageCheckResult, ...]:
    decision_ready = (
        decision is not None
        and decision.preflight_status
        is PreApprovalStatus.READY_FOR_PRE_APPROVAL_FRESH_PREFLIGHT_REVIEW
        and decision.preflight_passed is True
        and decision.eligible_for_future_real_approval_gate_generation is True
    )
    allowed_false = decision is not None and decision.allowed_for_live is False
    no_api_calls = (
        live_order_once_called is False
        and private_api_called is False
        and broker_called is False
        and read_only_api_called is False
        and public_api_called is False
    )
    forbidden_terms_present = _display_forbidden_fields_are_complete(
        REAL_APPROVAL_GATE_GENERATION_PACKAGE_DISPLAY_FORBIDDEN_FIELDS
    )
    return (
        _check(
            "pre_approval_fresh_preflight_ready",
            decision_ready,
            _bool_text(decision_ready),
            "true",
        ),
        _check("allowed_for_live_false", allowed_false, _bool_text(allowed_false), "true"),
        _check(
            "approval_gate_not_issued",
            approval_gate_issued is False,
            _bool_text(approval_gate_issued is False),
            "true",
        ),
        _check(
            "approval_id_not_generated",
            approval_id_generated is False,
            _bool_text(approval_id_generated is False),
            "true",
        ),
        _check(
            "approval_command_not_generated",
            approval_command_generated is False,
            _bool_text(approval_command_generated is False),
            "true",
        ),
        _check(
            "approval_command_not_copyable",
            approval_command_copyable is False,
            _bool_text(approval_command_copyable is False),
            "true",
        ),
        _check(
            "approval_id_generation_deferred",
            approval_id_generation_deferred_to_future_step is True,
            _bool_text(approval_id_generation_deferred_to_future_step is True),
            "true",
        ),
        _check(
            "approval_command_generation_deferred",
            approval_command_generation_deferred_to_future_step is True,
            _bool_text(approval_command_generation_deferred_to_future_step is True),
            "true",
        ),
        _check(
            "ttl_seconds_300",
            ttl_seconds == APPROVAL_GATE_TTL_SECONDS,
            ttl_seconds,
            str(APPROVAL_GATE_TTL_SECONDS),
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
            "required_ack_tokens_present",
            not (set(APPROVAL_ACK_TOKENS) - set(required_ack_tokens)),
            str(len(required_ack_tokens)),
            str(len(APPROVAL_ACK_TOKENS)),
        ),
        _check(
            "display_forbidden_fields_include_sensitive_terms",
            forbidden_terms_present,
            _bool_text(forbidden_terms_present),
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
            post_executed is False,
            _bool_text(post_executed is False),
            "true",
        ),
    )


def _build_sections(
    *,
    phases: tuple[LiveOrderRealApprovalGateGenerationPackagePhase, ...],
    check_results: tuple[LiveOrderRealApprovalGateGenerationPackageCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
) -> tuple[LiveOrderRealApprovalGateGenerationPackageSection, ...]:
    blocked_text = ", ".join(blocked_reasons) if blocked_reasons else "none"
    failed_checks = tuple(check.name for check in check_results if not check.passed)
    failed_text = ", ".join(failed_checks) if failed_checks else "none"
    phase_text = ", ".join(phase.phase_id for phase in phases) if phases else "none"
    return (
        LiveOrderRealApprovalGateGenerationPackageSection(
            section_id="approval_generation_deferral",
            title="Approval Generation Deferral",
            lines=(
                "approval_gate_issued: False",
                "approval_id_generated: False",
                "approval_command_generated: False",
                "approval_command_copyable: False",
                "approval_id_generation_deferred_to_future_step: True",
                "approval_command_generation_deferred_to_future_step: True",
            ),
        ),
        LiveOrderRealApprovalGateGenerationPackageSection(
            section_id="package_constraints",
            title="Package Constraints",
            lines=(
                f"ttl_seconds: {APPROVAL_GATE_TTL_SECONDS}",
                "exact_match_required: True",
                "same_session_required: True",
                f"required_phase_ids: {phase_text}",
            ),
        ),
        LiveOrderRealApprovalGateGenerationPackageSection(
            section_id="decision",
            title="Decision",
            lines=(
                f"failed_checks: {failed_text}",
                f"blocked_reasons: {blocked_text}",
                f"recommended_next_step: {recommended_next_step}",
            ),
        ),
    )


def _validate_package(
    package: LiveOrderRealApprovalGateGenerationPackage,
) -> None:
    for field_name in (
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
        _require_non_empty(field_name, getattr(package, field_name))
    if not isinstance(package.created_at, datetime):
        raise LiveVerificationValidationError("created_at must be datetime")
    if type(package.package_ready) is not bool:
        raise LiveVerificationValidationError("package_ready must be bool")
    if type(package.eligible_for_future_real_approval_gate_generation) is not bool:
        raise LiveVerificationValidationError("package eligibility must be bool")
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
    ):
        if getattr(package, field_name) is not expected:
            raise LiveVerificationValidationError(f"{field_name} must be {expected}")
    if package.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("ttl_seconds must be 300")
    if package.required_ack_tokens != APPROVAL_ACK_TOKENS:
        raise LiveVerificationValidationError("required_ack_tokens mismatch")
    if package.approval_id_placeholder_label != APPROVAL_ID_PLACEHOLDER_LABEL:
        raise LiveVerificationValidationError("approval id placeholder mismatch")
    if package.approval_command_template_label != APPROVAL_COMMAND_TEMPLATE_LABEL:
        raise LiveVerificationValidationError("approval command label mismatch")
    if package.approval_command_display_mode != APPROVAL_COMMAND_DISPLAY_MODE:
        raise LiveVerificationValidationError("approval command display mode mismatch")
    if package.package_ready and (
        package.package_status
        is not PackageStatus.READY_FOR_REAL_APPROVAL_GATE_GENERATION_PACKAGE_REVIEW
    ):
        raise LiveVerificationValidationError("ready package status mismatch")
    if package.package_ready and package.blocked_reasons:
        raise LiveVerificationValidationError("ready package cannot have blockers")
    if not package.check_results:
        raise LiveVerificationValidationError("package requires check_results")
    if not package.sections:
        raise LiveVerificationValidationError("package requires sections")


def _display_forbidden_fields_are_complete(fields: tuple[str, ...]) -> bool:
    joined = " ".join(fields).lower()
    required_markers = (
        "api key",
        "secret",
        "signature value",
        "headers",
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


def _ref_from(
    decision: LiveOrderPreApprovalFreshPreflightDecision | None,
    key: str,
) -> str:
    if decision is None:
        return "missing"
    for section in decision.sections:
        for line in section.lines:
            prefix = f"{key}: "
            if line.startswith(prefix):
                value = line.removeprefix(prefix).strip()
                return value or "missing"
    return "missing"


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


def _check(
    name: str,
    passed: bool,
    sanitized_value: object,
    expected: str,
) -> LiveOrderRealApprovalGateGenerationPackageCheckResult:
    return LiveOrderRealApprovalGateGenerationPackageCheckResult(
        name=name,
        passed=passed,
        reason="pass" if passed else "blocked",
        sanitized_value=str(sanitized_value),
        expected=expected,
    )


def _add_reason(
    reasons: list[str],
    reason: LiveOrderRealApprovalGateGenerationPackageBlockReason,
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


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{name} must be non-empty")


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
