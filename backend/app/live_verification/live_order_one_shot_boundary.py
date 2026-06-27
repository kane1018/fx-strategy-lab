"""Dry-run one-shot live boundary model for Step 5N."""

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
from app.live_verification.live_order_final_dynamic_preflight import (
    LiveOrderFinalDynamicPreflightDecision,
    LiveOrderFinalDynamicPreflightStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_ONE_SHOT_BOUNDARY_ID_PREFIX = "LOOSB-"
ONE_SHOT_POST_ATTEMPT_LIMIT = 1
ONE_SHOT_BODY_FIELDS_ALLOWLIST = ("symbol", "side", "size", "executionType")
ONE_SHOT_BODY_FIELDS_FORBIDDEN = (
    "apiKey",
    "secret",
    "signature",
    "headers",
    "orderId",
    "executionId",
    "positionId",
    "clientOrderId",
    "rawRequest",
    "rawResponse",
    "retryCount",
    "loopCount",
    "closeOrder",
    "cancelOrder",
    "changeOrder",
)
REQUEST_BODY_FINGERPRINT_LABEL = "sanitized_request_body_fields_only_no_values"
SIGNING_BODY_FINGERPRINT_LABEL = "sanitized_signing_body_fields_only_no_values"


class LiveOrderOneShotBoundaryStatus(str, Enum):
    READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW = (
        "READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW"
    )
    BLOCKED_ONE_SHOT_LIVE_BOUNDARY = "BLOCKED_ONE_SHOT_LIVE_BOUNDARY"


class LiveOrderOneShotBoundaryBlockReason(str, Enum):
    FINAL_DYNAMIC_PREFLIGHT_NOT_READY = "final_dynamic_preflight_not_ready"
    PREFLIGHT_ALLOWS_LIVE = "preflight_allows_live"
    PREFLIGHT_NOT_DRY_RUN = "preflight_not_dry_run"
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
    INVALID_POST_ATTEMPT_LIMIT = "invalid_post_attempt_limit"
    POST_ALREADY_EXECUTED = "post_already_executed"
    LIVE_ORDER_ONCE_ALREADY_CALLED = "live_order_once_already_called"
    PRIVATE_API_ALREADY_CALLED = "private_api_already_called"
    BROKER_ALREADY_CALLED = "broker_already_called"
    READ_ONLY_API_ALREADY_CALLED = "read_only_api_already_called"
    RETRY_ALLOWED = "retry_allowed"
    LOOP_ALLOWED = "loop_allowed"
    ADD_ORDER_ALLOWED = "add_order_allowed"
    CHANGE_ORDER_ALLOWED = "change_order_allowed"
    CANCEL_ORDER_ALLOWED = "cancel_order_allowed"
    CLOSE_ORDER_ALLOWED = "close_order_allowed"
    OUTBOUND_BODY_ALLOWLIST_MISMATCH = "outbound_body_allowlist_mismatch"
    REQUEST_BODY_SIGNING_BODY_MISMATCH = "request_body_signing_body_mismatch"
    MISSING_POST_RECONCILIATION_REQUIREMENT = (
        "missing_post_reconciliation_requirement"
    )


@dataclass(frozen=True)
class LiveOrderOneShotBoundaryCheckResult:
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
class LiveOrderOneShotBoundarySection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError("one-shot boundary section requires lines")
        for line in self.lines:
            _require_non_empty("section line", line)


@dataclass(frozen=True)
class LiveOrderPostReconciliationPlan:
    required: bool
    read_only_after_post_required: bool
    account_assets_check_required: bool
    open_positions_check_required: bool
    active_orders_check_required: bool
    result_unknown_check_required: bool
    raw_response_storage_forbidden: bool
    raw_response_display_forbidden: bool
    order_id_display_forbidden: bool
    execution_id_display_forbidden: bool
    position_id_display_forbidden: bool
    recommended_timing: str
    summary: str

    def __post_init__(self) -> None:
        for field_name in (
            "required",
            "read_only_after_post_required",
            "account_assets_check_required",
            "open_positions_check_required",
            "active_orders_check_required",
            "result_unknown_check_required",
            "raw_response_storage_forbidden",
            "raw_response_display_forbidden",
            "order_id_display_forbidden",
            "execution_id_display_forbidden",
            "position_id_display_forbidden",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")
        if self.required is not True:
            raise LiveVerificationValidationError("post reconciliation remains required")
        if self.read_only_after_post_required is not True:
            raise LiveVerificationValidationError("read-only reconciliation is required")
        if self.raw_response_storage_forbidden is not True:
            raise LiveVerificationValidationError("raw response storage remains forbidden")
        if self.raw_response_display_forbidden is not True:
            raise LiveVerificationValidationError("raw response display remains forbidden")
        if self.order_id_display_forbidden is not True:
            raise LiveVerificationValidationError("order id display remains forbidden")
        if self.execution_id_display_forbidden is not True:
            raise LiveVerificationValidationError("execution id display remains forbidden")
        if self.position_id_display_forbidden is not True:
            raise LiveVerificationValidationError("position id display remains forbidden")
        _require_non_empty("recommended_timing", self.recommended_timing)
        _require_non_empty("summary", self.summary)


@dataclass(frozen=True)
class LiveOrderOneShotBoundaryDecision:
    boundary_id: str
    created_at: datetime
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
    boundary_status: LiveOrderOneShotBoundaryStatus
    boundary_passed: bool
    eligible_for_future_one_shot_live_review: bool
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
    outbound_body_allowlist_matched: bool
    request_body_equals_signing_body: bool
    request_body_fingerprint_label: str
    signing_body_fingerprint_label: str
    body_fields_allowlist: tuple[str, ...]
    body_fields_forbidden: tuple[str, ...]
    post_reconciliation_required: bool
    post_reconciliation_plan: LiveOrderPostReconciliationPlan
    check_results: tuple[LiveOrderOneShotBoundaryCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderOneShotBoundarySection, ...]

    def __post_init__(self) -> None:
        _validate_decision(self)


@dataclass(frozen=True)
class LiveOrderOneShotBoundaryBuildResult:
    decision: LiveOrderOneShotBoundaryDecision
    boundary_id: str
    boundary_status: LiveOrderOneShotBoundaryStatus
    blocked_reasons: tuple[str, ...]
    boundary_passed: bool
    eligible_for_future_one_shot_live_review: bool
    allowed_for_live: bool
    post_attempt_limit: int
    post_executed: bool
    live_order_once_called: bool
    private_api_called: bool
    broker_called: bool
    read_only_api_called: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.decision.boundary_id != self.boundary_id:
            raise LiveVerificationValidationError("boundary_id mismatch")
        if self.decision.boundary_status is not self.boundary_status:
            raise LiveVerificationValidationError("boundary_status mismatch")
        if self.decision.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.decision.boundary_passed is not self.boundary_passed:
            raise LiveVerificationValidationError("boundary_passed mismatch")
        if (
            self.decision.eligible_for_future_one_shot_live_review
            is not self.eligible_for_future_one_shot_live_review
        ):
            raise LiveVerificationValidationError("eligible review mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("Step 5N never allows live execution")
        if self.post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
            raise LiveVerificationValidationError("one-shot attempt limit mismatch")
        if self.post_executed is not False:
            raise LiveVerificationValidationError("Step 5N never executes POST")
        if self.live_order_once_called is not False:
            raise LiveVerificationValidationError("Step 5N never calls one-shot runner")
        if self.private_api_called is not False:
            raise LiveVerificationValidationError("Step 5N never calls Private API")
        if self.broker_called is not False:
            raise LiveVerificationValidationError("Step 5N never calls broker")
        if self.read_only_api_called is not False:
            raise LiveVerificationValidationError("Step 5N never calls read-only API")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def build_live_order_one_shot_boundary(
    *,
    final_dynamic_preflight_decision: LiveOrderFinalDynamicPreflightDecision,
    created_at: datetime | None = None,
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
    outbound_body_allowlist_matched: bool = True,
    request_body_equals_signing_body: bool = True,
    body_fields_allowlist: tuple[str, ...] = ONE_SHOT_BODY_FIELDS_ALLOWLIST,
    body_fields_forbidden: tuple[str, ...] = ONE_SHOT_BODY_FIELDS_FORBIDDEN,
    post_reconciliation_required: bool = True,
) -> LiveOrderOneShotBoundaryBuildResult:
    """Build a dry-run one-shot boundary decision without live execution."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    preflight_reasons = _preflight_blocked_reasons(final_dynamic_preflight_decision)
    one_shot_reasons = _one_shot_blocked_reasons(
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
        outbound_body_allowlist_matched=outbound_body_allowlist_matched,
        request_body_equals_signing_body=request_body_equals_signing_body,
        post_reconciliation_required=post_reconciliation_required,
    )
    blocked_reasons = _merge_reasons(
        preflight_reasons,
        _preflight_existing_reasons(final_dynamic_preflight_decision),
        one_shot_reasons,
    )
    check_results = _build_check_results(
        final_dynamic_preflight_decision=final_dynamic_preflight_decision,
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
        outbound_body_allowlist_matched=outbound_body_allowlist_matched,
        request_body_equals_signing_body=request_body_equals_signing_body,
        post_reconciliation_required=post_reconciliation_required,
    )

    if blocked_reasons:
        status = LiveOrderOneShotBoundaryStatus.BLOCKED_ONE_SHOT_LIVE_BOUNDARY
        passed = False
        eligible = False
        if preflight_reasons or _preflight_existing_reasons(
            final_dynamic_preflight_decision
        ):
            recommended_next_step = "fix_final_dynamic_preflight_blockers_no_post"
        else:
            recommended_next_step = "fix_one_shot_boundary_blockers_no_post"
        summary = "blocked one-shot live boundary review; live post remains disallowed"
    else:
        status = (
            LiveOrderOneShotBoundaryStatus.READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW
        )
        passed = True
        eligible = True
        recommended_next_step = (
            "prepare_future_real_approval_gate_or_one_shot_execution_plan_separate_step_no_post"
        )
        summary = (
            "ready for future one-shot boundary review only; live post remains disallowed"
        )

    plan = build_live_order_post_reconciliation_plan()
    boundary_id = make_live_order_one_shot_boundary_id(
        preflight_decision_id=_decision_id(final_dynamic_preflight_decision),
        candidate_id=_preflight_text(final_dynamic_preflight_decision, "candidate_id"),
        created_at=created,
        boundary_status=status,
        blocked_reasons=blocked_reasons,
    )
    sections = _build_sections(
        final_dynamic_preflight_decision=final_dynamic_preflight_decision,
        status=status,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        body_fields_allowlist=tuple(body_fields_allowlist),
        body_fields_forbidden=tuple(body_fields_forbidden),
        post_reconciliation_plan=plan,
        recommended_next_step=recommended_next_step,
    )
    decision = LiveOrderOneShotBoundaryDecision(
        boundary_id=boundary_id,
        created_at=created,
        preflight_decision_id=_decision_id(final_dynamic_preflight_decision),
        snapshot_id=_preflight_text(final_dynamic_preflight_decision, "snapshot_id"),
        simulation_id=_preflight_text(final_dynamic_preflight_decision, "simulation_id"),
        preview_id=_preflight_text(final_dynamic_preflight_decision, "preview_id"),
        design_id=_preflight_text(final_dynamic_preflight_decision, "design_id"),
        handoff_id=_preflight_text(final_dynamic_preflight_decision, "handoff_id"),
        operator_review_id=_preflight_text(
            final_dynamic_preflight_decision,
            "operator_review_id",
        ),
        bundle_id=_preflight_text(final_dynamic_preflight_decision, "bundle_id"),
        review_id=_preflight_text(final_dynamic_preflight_decision, "review_id"),
        candidate_id=_preflight_text(final_dynamic_preflight_decision, "candidate_id"),
        risk_decision_id=_preflight_text(
            final_dynamic_preflight_decision,
            "risk_decision_id",
        ),
        trace_id=_preflight_text(final_dynamic_preflight_decision, "trace_id"),
        session_policy_decision_id=_preflight_text(
            final_dynamic_preflight_decision,
            "session_policy_decision_id",
        ),
        source_signal_id=_preflight_text(
            final_dynamic_preflight_decision,
            "source_signal_id",
        ),
        source_type=_preflight_text(final_dynamic_preflight_decision, "source_type"),
        strategy_name=_preflight_text(
            final_dynamic_preflight_decision,
            "strategy_name",
        ),
        symbol=_preflight_text(final_dynamic_preflight_decision, "symbol"),
        side=_preflight_text(final_dynamic_preflight_decision, "side"),
        size=_preflight_int(final_dynamic_preflight_decision, "size"),
        execution_type=_preflight_text(
            final_dynamic_preflight_decision,
            "execution_type",
        ),
        boundary_status=status,
        boundary_passed=passed,
        eligible_for_future_one_shot_live_review=eligible,
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
        outbound_body_allowlist_matched=outbound_body_allowlist_matched,
        request_body_equals_signing_body=request_body_equals_signing_body,
        request_body_fingerprint_label=REQUEST_BODY_FINGERPRINT_LABEL,
        signing_body_fingerprint_label=SIGNING_BODY_FINGERPRINT_LABEL,
        body_fields_allowlist=tuple(body_fields_allowlist),
        body_fields_forbidden=tuple(body_fields_forbidden),
        post_reconciliation_required=True,
        post_reconciliation_plan=plan,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=sections,
    )
    return LiveOrderOneShotBoundaryBuildResult(
        decision=decision,
        boundary_id=decision.boundary_id,
        boundary_status=decision.boundary_status,
        blocked_reasons=decision.blocked_reasons,
        boundary_passed=decision.boundary_passed,
        eligible_for_future_one_shot_live_review=decision.eligible_for_future_one_shot_live_review,
        allowed_for_live=False,
        post_attempt_limit=ONE_SHOT_POST_ATTEMPT_LIMIT,
        post_executed=False,
        live_order_once_called=False,
        private_api_called=False,
        broker_called=False,
        read_only_api_called=False,
        recommended_next_step=decision.recommended_next_step,
    )


def build_live_order_post_reconciliation_plan() -> LiveOrderPostReconciliationPlan:
    """Describe required post-POST read-only reconciliation without executing it."""
    return LiveOrderPostReconciliationPlan(
        required=True,
        read_only_after_post_required=True,
        account_assets_check_required=True,
        open_positions_check_required=True,
        active_orders_check_required=True,
        result_unknown_check_required=True,
        raw_response_storage_forbidden=True,
        raw_response_display_forbidden=True,
        order_id_display_forbidden=True,
        execution_id_display_forbidden=True,
        position_id_display_forbidden=True,
        recommended_timing="after_future_single_post_only_no_retry",
        summary=(
            "future post result must be reconciled once with sanitized read-only checks; "
            "Step 5N only records this plan"
        ),
    )


def render_live_order_one_shot_boundary_markdown(
    decision: LiveOrderOneShotBoundaryDecision,
) -> str:
    """Render a sanitized one-shot live boundary dry-run review."""
    lines = [
        "# Live Order One-shot Boundary",
        "",
        "This one-shot live boundary model is dry-run only.",
        "This model does not call read-only API.",
        "This model does not call Private API.",
        "This model does not call live_order_once.",
        "This model does not execute HTTP POST.",
        "This model does not authorize live POST.",
        "allowed_for_live=false.",
        "",
        "## Summary",
        "",
        f"- boundary_id: {decision.boundary_id}",
        f"- boundary_status: {decision.boundary_status.value}",
        f"- boundary_passed: {decision.boundary_passed}",
        (
            "- eligible_for_future_one_shot_live_review: "
            f"{decision.eligible_for_future_one_shot_live_review}"
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


def make_live_order_one_shot_boundary_id(
    *,
    preflight_decision_id: str,
    candidate_id: str,
    created_at: datetime,
    boundary_status: LiveOrderOneShotBoundaryStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    _require_non_empty("preflight_decision_id", preflight_decision_id)
    _require_non_empty("candidate_id", candidate_id)
    created = _ensure_aware(created_at)
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "boundary_status": boundary_status.value,
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "preflight_decision_id": preflight_decision_id,
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{LIVE_ORDER_ONE_SHOT_BOUNDARY_ID_PREFIX}{digest.upper()}"


def _preflight_blocked_reasons(
    decision: LiveOrderFinalDynamicPreflightDecision,
) -> tuple[str, ...]:
    reasons: list[LiveOrderOneShotBoundaryBlockReason] = []
    if not isinstance(decision, LiveOrderFinalDynamicPreflightDecision):
        return (LiveOrderOneShotBoundaryBlockReason.FINAL_DYNAMIC_PREFLIGHT_NOT_READY.value,)
    if (
        decision.preflight_status
        is not LiveOrderFinalDynamicPreflightStatus.READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW
        or decision.preflight_passed is not True
        or decision.eligible_for_future_one_shot_review is not True
    ):
        _add_reason(
            reasons,
            LiveOrderOneShotBoundaryBlockReason.FINAL_DYNAMIC_PREFLIGHT_NOT_READY,
        )
    if decision.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderOneShotBoundaryBlockReason.PREFLIGHT_ALLOWS_LIVE)
    if decision.dry_run_only is not True:
        _add_reason(reasons, LiveOrderOneShotBoundaryBlockReason.PREFLIGHT_NOT_DRY_RUN)
    if decision.approval_gate_issued is not False:
        _add_reason(
            reasons,
            LiveOrderOneShotBoundaryBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        )
    if decision.approval_id_generated is not False:
        _add_reason(
            reasons,
            LiveOrderOneShotBoundaryBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        )
    if decision.approval_command_generated is not False:
        _add_reason(
            reasons,
            LiveOrderOneShotBoundaryBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        )
    if decision.final_dynamic_preflight_required is not True:
        _add_reason(
            reasons,
            LiveOrderOneShotBoundaryBlockReason.MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT,
        )
    if decision.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderOneShotBoundaryBlockReason.UNSUPPORTED_SYMBOL)
    if decision.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, LiveOrderOneShotBoundaryBlockReason.UNSUPPORTED_SIDE)
    if decision.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderOneShotBoundaryBlockReason.UNSUPPORTED_SIZE)
    if decision.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, LiveOrderOneShotBoundaryBlockReason.UNSUPPORTED_EXECUTION_TYPE)
    return tuple(reason.value for reason in reasons)


def _one_shot_blocked_reasons(
    *,
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
    outbound_body_allowlist_matched: bool,
    request_body_equals_signing_body: bool,
    post_reconciliation_required: bool,
) -> tuple[str, ...]:
    reasons: list[LiveOrderOneShotBoundaryBlockReason] = []
    if post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
        _add_reason(reasons, LiveOrderOneShotBoundaryBlockReason.INVALID_POST_ATTEMPT_LIMIT)
    _expect_false(
        reasons,
        post_executed,
        LiveOrderOneShotBoundaryBlockReason.POST_ALREADY_EXECUTED,
    )
    _expect_false(
        reasons,
        live_order_once_called,
        LiveOrderOneShotBoundaryBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
    )
    _expect_false(
        reasons,
        private_api_called,
        LiveOrderOneShotBoundaryBlockReason.PRIVATE_API_ALREADY_CALLED,
    )
    _expect_false(
        reasons,
        broker_called,
        LiveOrderOneShotBoundaryBlockReason.BROKER_ALREADY_CALLED,
    )
    _expect_false(
        reasons,
        read_only_api_called,
        LiveOrderOneShotBoundaryBlockReason.READ_ONLY_API_ALREADY_CALLED,
    )
    _expect_false(reasons, retry_allowed, LiveOrderOneShotBoundaryBlockReason.RETRY_ALLOWED)
    _expect_false(reasons, loop_allowed, LiveOrderOneShotBoundaryBlockReason.LOOP_ALLOWED)
    _expect_false(
        reasons,
        add_order_allowed,
        LiveOrderOneShotBoundaryBlockReason.ADD_ORDER_ALLOWED,
    )
    _expect_false(
        reasons,
        change_order_allowed,
        LiveOrderOneShotBoundaryBlockReason.CHANGE_ORDER_ALLOWED,
    )
    _expect_false(
        reasons,
        cancel_order_allowed,
        LiveOrderOneShotBoundaryBlockReason.CANCEL_ORDER_ALLOWED,
    )
    _expect_false(
        reasons,
        close_order_allowed,
        LiveOrderOneShotBoundaryBlockReason.CLOSE_ORDER_ALLOWED,
    )
    _expect_true(
        reasons,
        outbound_body_allowlist_matched,
        LiveOrderOneShotBoundaryBlockReason.OUTBOUND_BODY_ALLOWLIST_MISMATCH,
    )
    _expect_true(
        reasons,
        request_body_equals_signing_body,
        LiveOrderOneShotBoundaryBlockReason.REQUEST_BODY_SIGNING_BODY_MISMATCH,
    )
    _expect_true(
        reasons,
        post_reconciliation_required,
        LiveOrderOneShotBoundaryBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
    )
    return tuple(reason.value for reason in reasons)


def _build_check_results(
    *,
    final_dynamic_preflight_decision: LiveOrderFinalDynamicPreflightDecision,
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
    outbound_body_allowlist_matched: bool,
    request_body_equals_signing_body: bool,
    post_reconciliation_required: bool,
) -> tuple[LiveOrderOneShotBoundaryCheckResult, ...]:
    return (
        _check(
            "final_dynamic_preflight_decision",
            isinstance(
                final_dynamic_preflight_decision,
                LiveOrderFinalDynamicPreflightDecision,
            )
            and final_dynamic_preflight_decision.preflight_status
            is LiveOrderFinalDynamicPreflightStatus.READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW
            and final_dynamic_preflight_decision.preflight_passed is True,
            _enum_value(getattr(final_dynamic_preflight_decision, "preflight_status", "missing")),
            "READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW",
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
            "outbound_body_allowlist",
            outbound_body_allowlist_matched is True,
            outbound_body_allowlist_matched,
            "true",
        ),
        _check(
            "request_body_equals_signing_body",
            request_body_equals_signing_body is True,
            request_body_equals_signing_body,
            "true",
        ),
        _check(
            "post_reconciliation_required",
            post_reconciliation_required is True,
            post_reconciliation_required,
            "true",
        ),
    )


def _build_sections(
    *,
    final_dynamic_preflight_decision: LiveOrderFinalDynamicPreflightDecision,
    status: LiveOrderOneShotBoundaryStatus,
    check_results: tuple[LiveOrderOneShotBoundaryCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    body_fields_allowlist: tuple[str, ...],
    body_fields_forbidden: tuple[str, ...],
    post_reconciliation_plan: LiveOrderPostReconciliationPlan,
    recommended_next_step: str,
) -> tuple[LiveOrderOneShotBoundarySection, ...]:
    blocked_text = ", ".join(blocked_reasons) if blocked_reasons else "none"
    failed_checks = tuple(check.name for check in check_results if not check.passed)
    failed_text = ", ".join(failed_checks) if failed_checks else "none"
    return (
        LiveOrderOneShotBoundarySection(
            section_id="references",
            title="Sanitized References",
            lines=(
                f"preflight_decision_id: {_decision_id(final_dynamic_preflight_decision)}",
                _section_line(final_dynamic_preflight_decision, "snapshot_id"),
                _section_line(final_dynamic_preflight_decision, "simulation_id"),
                _section_line(final_dynamic_preflight_decision, "bundle_id"),
                _section_line(final_dynamic_preflight_decision, "review_id"),
                _section_line(final_dynamic_preflight_decision, "candidate_id"),
                _section_line(final_dynamic_preflight_decision, "risk_decision_id"),
                _section_line(final_dynamic_preflight_decision, "trace_id"),
                "allowed_for_live: False",
            ),
        ),
        LiveOrderOneShotBoundarySection(
            section_id="candidate",
            title="Candidate",
            lines=(
                _section_line(final_dynamic_preflight_decision, "source_signal_id"),
                _section_line(final_dynamic_preflight_decision, "source_type"),
                _section_line(final_dynamic_preflight_decision, "strategy_name"),
                _section_line(final_dynamic_preflight_decision, "symbol"),
                _section_line(final_dynamic_preflight_decision, "side"),
                f"size: {_preflight_int(final_dynamic_preflight_decision, 'size')}",
                (
                    "executionType: "
                    f"{_preflight_text(final_dynamic_preflight_decision, 'execution_type')}"
                ),
            ),
        ),
        LiveOrderOneShotBoundarySection(
            section_id="one_shot",
            title="One-shot Boundary",
            lines=(
                "post_attempt_limit: 1",
                "post_executed: False",
                "live_order_once_called: False",
                "private_api_called: False",
                "broker_called: False",
                "read_only_api_called: False",
                "retry_allowed: False",
                "loop_allowed: False",
                "add_order_allowed: False",
                "change_order_allowed: False",
                "cancel_order_allowed: False",
                "close_order_allowed: False",
            ),
        ),
        LiveOrderOneShotBoundarySection(
            section_id="body_boundary",
            title="Body And Signing Boundary",
            lines=(
                f"body_fields_allowlist: {', '.join(body_fields_allowlist)}",
                f"body_fields_forbidden: {', '.join(body_fields_forbidden)}",
                f"request_body_fingerprint_label: {REQUEST_BODY_FINGERPRINT_LABEL}",
                f"signing_body_fingerprint_label: {SIGNING_BODY_FINGERPRINT_LABEL}",
                "request_body_equals_signing_body: True",
            ),
        ),
        LiveOrderOneShotBoundarySection(
            section_id="reconciliation",
            title="Post Reconciliation Plan",
            lines=(
                f"required: {post_reconciliation_plan.required}",
                "read_only_after_post_required: "
                f"{post_reconciliation_plan.read_only_after_post_required}",
                "account_assets_check_required: "
                f"{post_reconciliation_plan.account_assets_check_required}",
                "open_positions_check_required: "
                f"{post_reconciliation_plan.open_positions_check_required}",
                "active_orders_check_required: "
                f"{post_reconciliation_plan.active_orders_check_required}",
                "result_unknown_check_required: "
                f"{post_reconciliation_plan.result_unknown_check_required}",
                f"recommended_timing: {post_reconciliation_plan.recommended_timing}",
            ),
        ),
        LiveOrderOneShotBoundarySection(
            section_id="decision",
            title="Boundary Decision",
            lines=(
                f"boundary_status: {status.value}",
                "allowed_for_live: False",
                f"failed_checks: {failed_text}",
                f"blocked_reasons: {blocked_text}",
                f"recommended_next_step: {recommended_next_step}",
            ),
        ),
    )


def _validate_decision(decision: LiveOrderOneShotBoundaryDecision) -> None:
    _require_non_empty("boundary_id", decision.boundary_id)
    if not decision.boundary_id.startswith(LIVE_ORDER_ONE_SHOT_BOUNDARY_ID_PREFIX):
        raise LiveVerificationValidationError("boundary_id must be dry-run boundary id")
    _ensure_aware(decision.created_at)
    for name, value in (
        ("preflight_decision_id", decision.preflight_decision_id),
        ("snapshot_id", decision.snapshot_id),
        ("simulation_id", decision.simulation_id),
        ("candidate_id", decision.candidate_id),
        ("symbol", decision.symbol),
        ("side", decision.side),
        ("execution_type", decision.execution_type),
        ("request_body_fingerprint_label", decision.request_body_fingerprint_label),
        ("signing_body_fingerprint_label", decision.signing_body_fingerprint_label),
        ("summary", decision.summary),
        ("recommended_next_step", decision.recommended_next_step),
    ):
        _require_non_empty(name, value)
    if type(decision.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    if decision.boundary_status not in set(LiveOrderOneShotBoundaryStatus):
        raise LiveVerificationValidationError("unsupported boundary status")
    for field_name, value in (
        ("boundary_passed", decision.boundary_passed),
        (
            "eligible_for_future_one_shot_live_review",
            decision.eligible_for_future_one_shot_live_review,
        ),
        ("outbound_body_allowlist_matched", decision.outbound_body_allowlist_matched),
        (
            "request_body_equals_signing_body",
            decision.request_body_equals_signing_body,
        ),
    ):
        if type(value) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")
    if decision.allowed_for_live is not False:
        raise LiveVerificationValidationError("Step 5N never allows live execution")
    if decision.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if decision.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if decision.approval_gate_issued is not False:
        raise LiveVerificationValidationError("Step 5N never issues approval gate")
    if decision.approval_id_generated is not False:
        raise LiveVerificationValidationError("Step 5N never generates approval id")
    if decision.approval_command_generated is not False:
        raise LiveVerificationValidationError("Step 5N never generates approval command")
    if decision.approval_command_template_only is not True:
        raise LiveVerificationValidationError("approval command remains template-only")
    if decision.approval_command_copyable is not False:
        raise LiveVerificationValidationError("approval command remains non-copyable")
    if decision.final_dynamic_preflight_required is not True:
        raise LiveVerificationValidationError("final dynamic preflight remains required")
    if decision.dry_run_only is not True:
        raise LiveVerificationValidationError("one-shot boundary model is dry-run only")
    if decision.post_attempt_limit != ONE_SHOT_POST_ATTEMPT_LIMIT:
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
        if getattr(decision, field_name) is not False:
            raise LiveVerificationValidationError(f"{field_name} must remain false")
    if decision.post_reconciliation_required is not True:
        raise LiveVerificationValidationError("post reconciliation remains required")
    if not decision.body_fields_allowlist:
        raise LiveVerificationValidationError("body allowlist is required")
    if not decision.body_fields_forbidden:
        raise LiveVerificationValidationError("body forbidden fields are required")
    if not decision.check_results:
        raise LiveVerificationValidationError("boundary decision requires checks")
    if not decision.sections:
        raise LiveVerificationValidationError("boundary decision requires sections")
    if (
        decision.boundary_status
        is LiveOrderOneShotBoundaryStatus.READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW
    ):
        if (
            not decision.boundary_passed
            or not decision.eligible_for_future_one_shot_live_review
        ):
            raise LiveVerificationValidationError("ready boundary must be eligible")
        if decision.blocked_reasons:
            raise LiveVerificationValidationError("ready boundary cannot have blockers")
    else:
        if decision.boundary_passed or decision.eligible_for_future_one_shot_live_review:
            raise LiveVerificationValidationError("blocked boundary cannot pass")
        if not decision.blocked_reasons:
            raise LiveVerificationValidationError("blocked boundary requires blockers")


def _preflight_existing_reasons(
    decision: LiveOrderFinalDynamicPreflightDecision,
) -> tuple[str, ...]:
    if isinstance(decision, LiveOrderFinalDynamicPreflightDecision):
        return decision.blocked_reasons
    return ()


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            if _has_text(reason) and reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _add_reason(
    reasons: list[LiveOrderOneShotBoundaryBlockReason],
    reason: LiveOrderOneShotBoundaryBlockReason,
) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _expect_true(
    reasons: list[LiveOrderOneShotBoundaryBlockReason],
    value: object,
    false_reason: LiveOrderOneShotBoundaryBlockReason,
) -> None:
    if value is not True:
        _add_reason(reasons, false_reason)


def _expect_false(
    reasons: list[LiveOrderOneShotBoundaryBlockReason],
    value: object,
    true_reason: LiveOrderOneShotBoundaryBlockReason,
) -> None:
    if value is not False:
        _add_reason(reasons, true_reason)


def _check(
    name: str,
    passed: bool,
    sanitized_value: object,
    expected: str,
) -> LiveOrderOneShotBoundaryCheckResult:
    return LiveOrderOneShotBoundaryCheckResult(
        name=name,
        passed=passed,
        reason="passed" if passed else "blocked",
        sanitized_value=_safe_value(sanitized_value),
        expected=expected,
    )


def _decision_id(decision: LiveOrderFinalDynamicPreflightDecision) -> str:
    return _preflight_text(decision, "decision_id")


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


def _preflight_int(
    decision: LiveOrderFinalDynamicPreflightDecision,
    field_name: str,
) -> int:
    value = getattr(decision, field_name, 0)
    return value if type(value) is int else 0


def _preflight_text(
    decision: LiveOrderFinalDynamicPreflightDecision,
    field_name: str,
) -> str:
    value = getattr(decision, field_name, None)
    if _has_text(value):
        return value.strip()
    section_value = _section_field_value(decision, field_name)
    return section_value if _has_text(section_value) else f"missing_{field_name}"


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")


def _safe_value(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _section_line(
    decision: LiveOrderFinalDynamicPreflightDecision,
    field_name: str,
) -> str:
    return f"{field_name}: {_preflight_text(decision, field_name)}"


def _section_field_value(
    decision: LiveOrderFinalDynamicPreflightDecision,
    field_name: str,
) -> str:
    if not isinstance(decision, LiveOrderFinalDynamicPreflightDecision):
        return ""
    prefix = f"{field_name}: "
    for section in decision.sections:
        for line in section.lines:
            if line.startswith(prefix):
                return line.removeprefix(prefix).strip()
    return ""
