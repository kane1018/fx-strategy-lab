"""Sanitized operator review procedure for Step 5H."""

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
from app.live_verification.live_order_review_session_bundle import (
    ReviewGatedSessionBundle,
    ReviewGatedSessionBundleStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_OPERATOR_REVIEW_ID_PREFIX = "LOCOPREV-"


class LiveOrderOperatorReviewStatus(str, Enum):
    READY_FOR_OPERATOR_CHECKLIST = "READY_FOR_OPERATOR_CHECKLIST"
    BLOCKED_OPERATOR_REVIEW = "BLOCKED_OPERATOR_REVIEW"


class LiveOrderOperatorReviewBlockReason(str, Enum):
    BUNDLE_ALLOWS_LIVE = "bundle_allows_live"
    BUNDLE_NOT_DRY_RUN = "bundle_not_dry_run"
    MISSING_HUMAN_APPROVAL_REQUIREMENT = "missing_human_approval_requirement"
    MISSING_APPROVAL_GATE_REQUIREMENT = "missing_approval_gate_requirement"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    MISSING_REMAINING_SESSIONS = "missing_remaining_sessions"
    MISSING_REMAINING_DAILY_SIZE = "missing_remaining_daily_size"
    NO_REMAINING_SESSIONS = "no_remaining_sessions"
    INSUFFICIENT_REMAINING_DAILY_SIZE = "insufficient_remaining_daily_size"


@dataclass(frozen=True)
class LiveOrderOperatorReviewChecklistItem:
    item_id: str
    label: str
    detail: str
    required: bool

    def __post_init__(self) -> None:
        _require_non_empty("item_id", self.item_id)
        _require_non_empty("label", self.label)
        _require_non_empty("detail", self.detail)
        if type(self.required) is not bool:
            raise LiveVerificationValidationError("checklist item required must be bool")


@dataclass(frozen=True)
class LiveOrderOperatorReviewProcedure:
    operator_review_id: str
    created_at: datetime
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
    bundle_status: str
    operator_review_status: LiveOrderOperatorReviewStatus
    risk_gate_passed: bool
    policy_passed: bool
    eligible_for_operator_review: bool
    allowed_for_live: bool
    requires_human_approval: bool
    approval_gate_required: bool
    dry_run_only: bool
    blocked_reasons: tuple[str, ...]
    remaining_sessions_today: int | str
    remaining_daily_size: int | str
    checklist_items: tuple[LiveOrderOperatorReviewChecklistItem, ...]
    summary: str
    recommended_next_step: str

    def __post_init__(self) -> None:
        _validate_operator_review(self)


@dataclass(frozen=True)
class LiveOrderOperatorReviewBuildResult:
    procedure: LiveOrderOperatorReviewProcedure
    operator_review_id: str
    operator_review_status: LiveOrderOperatorReviewStatus
    blocked_reasons: tuple[str, ...]
    allowed_for_live: bool
    eligible_for_operator_review: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.procedure.operator_review_id != self.operator_review_id:
            raise LiveVerificationValidationError("operator_review_id mismatch")
        if self.procedure.operator_review_status is not self.operator_review_status:
            raise LiveVerificationValidationError("operator_review_status mismatch")
        if self.procedure.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("operator review never allows live execution")
        if self.procedure.allowed_for_live is not False:
            raise LiveVerificationValidationError("operator review never allows live execution")
        if type(self.eligible_for_operator_review) is not bool:
            raise LiveVerificationValidationError("eligible_for_operator_review must be bool")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def build_live_order_operator_review_procedure(
    *,
    bundle: ReviewGatedSessionBundle,
    created_at: datetime | None = None,
) -> LiveOrderOperatorReviewBuildResult:
    """Build a dry-run operator checklist without approval or live execution."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    blocked_reasons = _operator_review_blocked_reasons(bundle)
    blocked_reasons = _merge_reasons(blocked_reasons, bundle.blocked_reasons)

    if blocked_reasons:
        operator_review_status = LiveOrderOperatorReviewStatus.BLOCKED_OPERATOR_REVIEW
        eligible_for_operator_review = False
        recommended_next_step = "fix_bundle_blockers_no_post"
        summary = "blocked operator review procedure; live post remains disallowed"
        checklist_items = _blocked_checklist_items(blocked_reasons)
    else:
        operator_review_status = LiveOrderOperatorReviewStatus.READY_FOR_OPERATOR_CHECKLIST
        eligible_for_operator_review = True
        recommended_next_step = "operator_checklist_review_no_post"
        summary = "ready for operator checklist only; live post remains disallowed"
        checklist_items = _ready_checklist_items(bundle)

    operator_review_id = make_live_order_operator_review_id(
        bundle_id=bundle.bundle_id,
        candidate_id=bundle.candidate_id,
        created_at=created,
        operator_review_status=operator_review_status,
        blocked_reasons=blocked_reasons,
    )
    procedure = LiveOrderOperatorReviewProcedure(
        operator_review_id=operator_review_id,
        created_at=created,
        bundle_id=bundle.bundle_id,
        review_id=bundle.review_id,
        candidate_id=bundle.candidate_id,
        risk_decision_id=bundle.risk_decision_id,
        trace_id=bundle.trace_id,
        session_policy_decision_id=bundle.session_policy_decision_id,
        source_signal_id=bundle.source_signal_id,
        source_type=bundle.source_type,
        strategy_name=bundle.strategy_name,
        symbol=bundle.symbol,
        side=bundle.side,
        size=bundle.size,
        execution_type=bundle.execution_type,
        bundle_status=_enum_value(bundle.bundle_status),
        operator_review_status=operator_review_status,
        risk_gate_passed=bundle.risk_gate_passed,
        policy_passed=bundle.policy_passed,
        eligible_for_operator_review=eligible_for_operator_review,
        allowed_for_live=False,
        requires_human_approval=True,
        approval_gate_required=True,
        dry_run_only=True,
        blocked_reasons=blocked_reasons,
        remaining_sessions_today=bundle.remaining_sessions_today,
        remaining_daily_size=bundle.remaining_daily_size,
        checklist_items=checklist_items,
        summary=summary,
        recommended_next_step=recommended_next_step,
    )
    return LiveOrderOperatorReviewBuildResult(
        procedure=procedure,
        operator_review_id=procedure.operator_review_id,
        operator_review_status=procedure.operator_review_status,
        blocked_reasons=procedure.blocked_reasons,
        allowed_for_live=False,
        eligible_for_operator_review=procedure.eligible_for_operator_review,
        recommended_next_step=procedure.recommended_next_step,
    )


def render_live_order_operator_review_markdown(
    procedure: LiveOrderOperatorReviewProcedure,
) -> str:
    """Render a sanitized dry-run operator review checklist."""
    blocked_text = (
        ", ".join(procedure.blocked_reasons) if procedure.blocked_reasons else "none"
    )
    lines = [
        "# Live Order Operator Review Procedure",
        "",
        "This operator review is dry-run only.",
        "This review is not an approval gate.",
        "This review does not authorize live POST.",
        "allowed_for_live=false.",
        "",
        "## Summary",
        "",
        f"- operator_review_id: {procedure.operator_review_id}",
        f"- operator_review_status: {procedure.operator_review_status.value}",
        f"- bundle_id: {procedure.bundle_id}",
        f"- summary: {procedure.summary}",
        f"- recommended_next_step: {procedure.recommended_next_step}",
        "",
        "## References",
        "",
        f"- review_id: {procedure.review_id}",
        f"- candidate_id: {procedure.candidate_id}",
        f"- risk_decision_id: {procedure.risk_decision_id}",
        f"- trace_id: {procedure.trace_id}",
        f"- session_policy_decision_id: {procedure.session_policy_decision_id}",
        f"- source_signal_id: {procedure.source_signal_id}",
        f"- source_type: {procedure.source_type}",
        f"- strategy_name: {procedure.strategy_name}",
        "",
        "## Candidate",
        "",
        f"- symbol: {procedure.symbol}",
        f"- side: {procedure.side}",
        f"- size: {procedure.size}",
        f"- executionType: {procedure.execution_type}",
        "",
        "## Status",
        "",
        f"- bundle_status: {procedure.bundle_status}",
        f"- risk_gate_passed: {procedure.risk_gate_passed}",
        f"- policy_passed: {procedure.policy_passed}",
        f"- eligible_for_operator_review: {procedure.eligible_for_operator_review}",
        f"- allowed_for_live: {procedure.allowed_for_live}",
        f"- blocked_reasons: {blocked_text}",
        f"- remaining_sessions_today: {procedure.remaining_sessions_today}",
        f"- remaining_daily_size: {procedure.remaining_daily_size}",
        "",
        "## Checklist",
        "",
    ]
    for item in procedure.checklist_items:
        lines.append(f"- [{item.item_id}] {item.label}: {item.detail}")
    return "\n".join(lines).rstrip() + "\n"


def make_live_order_operator_review_id(
    *,
    bundle_id: str,
    candidate_id: str,
    created_at: datetime,
    operator_review_status: LiveOrderOperatorReviewStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    _require_non_empty("bundle_id", bundle_id)
    _require_non_empty("candidate_id", candidate_id)
    created = _ensure_aware(created_at)
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "bundle_id": bundle_id,
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "operator_review_status": operator_review_status.value,
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{LIVE_ORDER_OPERATOR_REVIEW_ID_PREFIX}{digest.upper()}"


def _operator_review_blocked_reasons(
    bundle: ReviewGatedSessionBundle,
) -> tuple[str, ...]:
    reasons: list[LiveOrderOperatorReviewBlockReason | str] = []

    if bundle.bundle_status is not ReviewGatedSessionBundleStatus.READY_FOR_OPERATOR_REVIEW:
        _add_external_reason(reasons, "bundle_not_ready_for_operator_review")
    if bundle.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderOperatorReviewBlockReason.BUNDLE_ALLOWS_LIVE)
    if bundle.dry_run_only is not True:
        _add_reason(reasons, LiveOrderOperatorReviewBlockReason.BUNDLE_NOT_DRY_RUN)
    if bundle.requires_human_approval is not True:
        _add_reason(
            reasons,
            LiveOrderOperatorReviewBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        )
    if bundle.approval_gate_required is not True:
        _add_reason(
            reasons,
            LiveOrderOperatorReviewBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        )
    if bundle.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderOperatorReviewBlockReason.UNSUPPORTED_SYMBOL)
    if bundle.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, LiveOrderOperatorReviewBlockReason.UNSUPPORTED_SIDE)
    if bundle.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderOperatorReviewBlockReason.UNSUPPORTED_SIZE)
    if bundle.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, LiveOrderOperatorReviewBlockReason.UNSUPPORTED_EXECUTION_TYPE)
    if not isinstance(bundle.remaining_sessions_today, int):
        _add_reason(reasons, LiveOrderOperatorReviewBlockReason.MISSING_REMAINING_SESSIONS)
    elif bundle.remaining_sessions_today < 1:
        _add_reason(reasons, LiveOrderOperatorReviewBlockReason.NO_REMAINING_SESSIONS)
    if not isinstance(bundle.remaining_daily_size, int):
        _add_reason(
            reasons,
            LiveOrderOperatorReviewBlockReason.MISSING_REMAINING_DAILY_SIZE,
        )
    elif bundle.remaining_daily_size < LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(
            reasons,
            LiveOrderOperatorReviewBlockReason.INSUFFICIENT_REMAINING_DAILY_SIZE,
        )
    return tuple(_reason_value(reason) for reason in reasons)


def _ready_checklist_items(
    bundle: ReviewGatedSessionBundle,
) -> tuple[LiveOrderOperatorReviewChecklistItem, ...]:
    return (
        _item("dry_run_only", "Confirm this is dry-run review only", "No order action."),
        _item("not_approval_gate", "Confirm this is not an approval gate", "No approval id."),
        _item("no_live_post", "Confirm this does not authorize live POST", "No HTTP POST."),
        _item(
            "candidate_terms",
            "Review symbol / side / size / executionType",
            f"{bundle.symbol} {bundle.side} {bundle.size} {bundle.execution_type}",
        ),
        _item(
            "risk_gate",
            "Review risk gate status",
            f"risk_gate_passed={bundle.risk_gate_passed}",
        ),
        _item(
            "session_policy",
            "Review session policy status",
            f"policy_passed={bundle.policy_passed}",
        ),
        _item(
            "remaining_sessions",
            "Review remaining session capacity",
            f"remaining_sessions_today={bundle.remaining_sessions_today}",
        ),
        _item(
            "remaining_daily_size",
            "Review remaining daily size capacity",
            f"remaining_daily_size={bundle.remaining_daily_size}",
        ),
        _item(
            "blocked_reasons",
            "Review blocked reasons if any",
            _blocked_text(bundle.blocked_reasons),
        ),
        _item(
            "future_approval_gate",
            "Confirm future approval gate is a separate Step",
            "Do not issue approval gate in Step 5H.",
        ),
        _item(
            "future_final_preflight",
            "Confirm future final dynamic preflight is a separate Step",
            "Do not run final dynamic preflight in Step 5H.",
        ),
    )


def _blocked_checklist_items(
    blocked_reasons: tuple[str, ...],
) -> tuple[LiveOrderOperatorReviewChecklistItem, ...]:
    return (
        _item(
            "review_blocked_reasons",
            "Review blocked reasons",
            _blocked_text(blocked_reasons),
        ),
        _item(
            "fix_or_wait",
            "Fix or wait until blockers are cleared",
            "Do not bypass fail-closed blockers.",
        ),
        _item(
            "do_not_approval_gate",
            "Do not proceed to approval gate",
            "A blocked operator review cannot create approval.",
        ),
        _item(
            "do_not_live_post",
            "Do not proceed to live POST",
            "A blocked operator review cannot execute.",
        ),
    )


def _item(
    item_id: str,
    label: str,
    detail: str,
) -> LiveOrderOperatorReviewChecklistItem:
    return LiveOrderOperatorReviewChecklistItem(
        item_id=item_id,
        label=label,
        detail=detail,
        required=True,
    )


def _validate_operator_review(procedure: LiveOrderOperatorReviewProcedure) -> None:
    _require_non_empty("operator_review_id", procedure.operator_review_id)
    if not procedure.operator_review_id.startswith(LIVE_ORDER_OPERATOR_REVIEW_ID_PREFIX):
        raise LiveVerificationValidationError("operator_review_id must be dry-run id")
    _ensure_aware(procedure.created_at)
    for name, value in (
        ("bundle_id", procedure.bundle_id),
        ("review_id", procedure.review_id),
        ("candidate_id", procedure.candidate_id),
        ("risk_decision_id", procedure.risk_decision_id),
        ("trace_id", procedure.trace_id),
        ("session_policy_decision_id", procedure.session_policy_decision_id),
        ("source_signal_id", procedure.source_signal_id),
        ("source_type", procedure.source_type),
        ("strategy_name", procedure.strategy_name),
        ("symbol", procedure.symbol),
        ("side", procedure.side),
        ("execution_type", procedure.execution_type),
        ("bundle_status", procedure.bundle_status),
        ("summary", procedure.summary),
        ("recommended_next_step", procedure.recommended_next_step),
    ):
        _require_non_empty(name, value)
    if type(procedure.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    if procedure.operator_review_status not in set(LiveOrderOperatorReviewStatus):
        raise LiveVerificationValidationError("unsupported operator review status")
    for field_name, value in (
        ("risk_gate_passed", procedure.risk_gate_passed),
        ("policy_passed", procedure.policy_passed),
        ("eligible_for_operator_review", procedure.eligible_for_operator_review),
    ):
        if type(value) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")
    if procedure.allowed_for_live is not False:
        raise LiveVerificationValidationError("Step 5H never allows live execution")
    if procedure.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if procedure.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if procedure.dry_run_only is not True:
        raise LiveVerificationValidationError("operator review must be dry-run only")
    if not procedure.checklist_items:
        raise LiveVerificationValidationError("operator review requires checklist items")
    if (
        procedure.operator_review_status
        is LiveOrderOperatorReviewStatus.READY_FOR_OPERATOR_CHECKLIST
    ):
        if not procedure.eligible_for_operator_review:
            raise LiveVerificationValidationError("ready operator review must be eligible")
        if procedure.blocked_reasons:
            raise LiveVerificationValidationError("ready operator review cannot be blocked")
    else:
        if procedure.eligible_for_operator_review:
            raise LiveVerificationValidationError("blocked operator review cannot be eligible")
        if not procedure.blocked_reasons:
            raise LiveVerificationValidationError("blocked operator review requires reasons")


def _add_reason(
    reasons: list[LiveOrderOperatorReviewBlockReason | str],
    reason: LiveOrderOperatorReviewBlockReason,
) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _add_external_reason(
    reasons: list[LiveOrderOperatorReviewBlockReason | str],
    reason: str,
) -> None:
    if _has_text(reason) and reason not in reasons:
        reasons.append(reason)


def _blocked_text(reasons: tuple[str, ...]) -> str:
    return ", ".join(reasons) if reasons else "none"


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


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            if _has_text(reason) and reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _reason_value(value: LiveOrderOperatorReviewBlockReason | str) -> str:
    if isinstance(value, LiveOrderOperatorReviewBlockReason):
        return value.value
    return value


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")
