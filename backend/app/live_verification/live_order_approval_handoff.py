"""Sanitized approval handoff package for Step 5I."""

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
from app.live_verification.live_order_operator_review import (
    LiveOrderOperatorReviewProcedure,
    LiveOrderOperatorReviewStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_APPROVAL_HANDOFF_ID_PREFIX = "LOCAHND-"


class LiveOrderApprovalHandoffStatus(str, Enum):
    READY_FOR_APPROVAL_HANDOFF_REVIEW = "READY_FOR_APPROVAL_HANDOFF_REVIEW"
    BLOCKED_HANDOFF = "BLOCKED_HANDOFF"


class LiveOrderApprovalHandoffBlockReason(str, Enum):
    OPERATOR_REVIEW_NOT_READY = "operator_review_not_ready"
    OPERATOR_REVIEW_ALLOWS_LIVE = "operator_review_allows_live"
    OPERATOR_REVIEW_NOT_DRY_RUN = "operator_review_not_dry_run"
    MISSING_HUMAN_APPROVAL_REQUIREMENT = "missing_human_approval_requirement"
    MISSING_APPROVAL_GATE_REQUIREMENT = "missing_approval_gate_requirement"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"


@dataclass(frozen=True)
class LiveOrderApprovalHandoffSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError("handoff section requires lines")
        for line in self.lines:
            _require_non_empty("section line", line)


@dataclass(frozen=True)
class LiveOrderApprovalHandoffPackage:
    handoff_id: str
    created_at: datetime
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
    operator_review_status: str
    handoff_status: LiveOrderApprovalHandoffStatus
    eligible_for_operator_review: bool
    allowed_for_live: bool
    requires_human_approval: bool
    approval_gate_required: bool
    approval_gate_issued: bool
    approval_command_generated: bool
    final_dynamic_preflight_required: bool
    dry_run_only: bool
    display_allowed_fields: tuple[str, ...]
    display_forbidden_fields: tuple[str, ...]
    final_dynamic_preflight_items: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderApprovalHandoffSection, ...]

    def __post_init__(self) -> None:
        _validate_handoff_package(self)


@dataclass(frozen=True)
class LiveOrderApprovalHandoffBuildResult:
    package: LiveOrderApprovalHandoffPackage
    handoff_id: str
    handoff_status: LiveOrderApprovalHandoffStatus
    blocked_reasons: tuple[str, ...]
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_command_generated: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.package.handoff_id != self.handoff_id:
            raise LiveVerificationValidationError("handoff_id mismatch")
        if self.package.handoff_status is not self.handoff_status:
            raise LiveVerificationValidationError("handoff_status mismatch")
        if self.package.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("handoff never allows live execution")
        if self.approval_gate_issued is not False:
            raise LiveVerificationValidationError("handoff never issues approval gate")
        if self.approval_command_generated is not False:
            raise LiveVerificationValidationError("handoff never generates approval command")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def build_live_order_approval_handoff_package(
    *,
    operator_review: LiveOrderOperatorReviewProcedure,
    created_at: datetime | None = None,
) -> LiveOrderApprovalHandoffBuildResult:
    """Build a dry-run approval handoff package without approval or execution."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    blocked_reasons = _merge_reasons(
        _handoff_blocked_reasons(operator_review),
        operator_review.blocked_reasons,
    )

    if blocked_reasons:
        handoff_status = LiveOrderApprovalHandoffStatus.BLOCKED_HANDOFF
        eligible_for_operator_review = False
        recommended_next_step = "fix_operator_review_blockers_no_post"
        summary = "blocked approval handoff package; approval gate remains separate"
    else:
        handoff_status = LiveOrderApprovalHandoffStatus.READY_FOR_APPROVAL_HANDOFF_REVIEW
        eligible_for_operator_review = True
        recommended_next_step = "prepare_future_approval_gate_in_separate_step_no_post"
        summary = "ready for approval handoff review only; no approval gate is issued"

    handoff_id = make_live_order_approval_handoff_id(
        operator_review_id=operator_review.operator_review_id,
        candidate_id=operator_review.candidate_id,
        created_at=created,
        handoff_status=handoff_status,
        blocked_reasons=blocked_reasons,
    )
    package = LiveOrderApprovalHandoffPackage(
        handoff_id=handoff_id,
        created_at=created,
        operator_review_id=operator_review.operator_review_id,
        bundle_id=operator_review.bundle_id,
        review_id=operator_review.review_id,
        candidate_id=operator_review.candidate_id,
        risk_decision_id=operator_review.risk_decision_id,
        trace_id=operator_review.trace_id,
        session_policy_decision_id=operator_review.session_policy_decision_id,
        source_signal_id=operator_review.source_signal_id,
        source_type=operator_review.source_type,
        strategy_name=operator_review.strategy_name,
        symbol=operator_review.symbol,
        side=operator_review.side,
        size=operator_review.size,
        execution_type=operator_review.execution_type,
        operator_review_status=_enum_value(operator_review.operator_review_status),
        handoff_status=handoff_status,
        eligible_for_operator_review=eligible_for_operator_review,
        allowed_for_live=False,
        requires_human_approval=True,
        approval_gate_required=True,
        approval_gate_issued=False,
        approval_command_generated=False,
        final_dynamic_preflight_required=True,
        dry_run_only=True,
        display_allowed_fields=DISPLAY_ALLOWED_FIELDS,
        display_forbidden_fields=DISPLAY_FORBIDDEN_FIELDS,
        final_dynamic_preflight_items=FINAL_DYNAMIC_PREFLIGHT_ITEMS,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_handoff_sections(blocked_reasons),
    )
    return LiveOrderApprovalHandoffBuildResult(
        package=package,
        handoff_id=package.handoff_id,
        handoff_status=package.handoff_status,
        blocked_reasons=package.blocked_reasons,
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_command_generated=False,
        recommended_next_step=package.recommended_next_step,
    )


def render_live_order_approval_handoff_markdown(
    package: LiveOrderApprovalHandoffPackage,
) -> str:
    """Render a sanitized dry-run approval handoff package."""
    blocked_text = ", ".join(package.blocked_reasons) if package.blocked_reasons else "none"
    lines = [
        "# Live Order Approval Handoff Package",
        "",
        "This approval handoff is dry-run only.",
        "This handoff is not an approval gate.",
        "This handoff does not generate approval_id or approval command.",
        "This handoff does not authorize live POST.",
        "allowed_for_live=false.",
        "",
        "## Summary",
        "",
        f"- handoff_id: {package.handoff_id}",
        f"- handoff_status: {package.handoff_status.value}",
        f"- operator_review_id: {package.operator_review_id}",
        f"- summary: {package.summary}",
        f"- recommended_next_step: {package.recommended_next_step}",
        "",
        "## References",
        "",
        f"- bundle_id: {package.bundle_id}",
        f"- review_id: {package.review_id}",
        f"- candidate_id: {package.candidate_id}",
        f"- risk_decision_id: {package.risk_decision_id}",
        f"- trace_id: {package.trace_id}",
        f"- session_policy_decision_id: {package.session_policy_decision_id}",
        f"- source_signal_id: {package.source_signal_id}",
        f"- source_type: {package.source_type}",
        f"- strategy_name: {package.strategy_name}",
        "",
        "## Candidate",
        "",
        f"- symbol: {package.symbol}",
        f"- side: {package.side}",
        f"- size: {package.size}",
        f"- executionType: {package.execution_type}",
        "",
        "## Safety Flags",
        "",
        f"- operator_review_status: {package.operator_review_status}",
        f"- eligible_for_operator_review: {package.eligible_for_operator_review}",
        f"- allowed_for_live: {package.allowed_for_live}",
        f"- requires_human_approval: {package.requires_human_approval}",
        f"- approval_gate_required: {package.approval_gate_required}",
        f"- approval_gate_issued: {package.approval_gate_issued}",
        f"- approval_command_generated: {package.approval_command_generated}",
        f"- final_dynamic_preflight_required: {package.final_dynamic_preflight_required}",
        f"- dry_run_only: {package.dry_run_only}",
        f"- blocked_reasons: {blocked_text}",
        "",
        "## Display Allowed Fields",
        "",
    ]
    lines.extend(f"- {field}" for field in package.display_allowed_fields)
    lines.extend(["", "## Display Forbidden Fields", ""])
    lines.extend(f"- {field}" for field in package.display_forbidden_fields)
    lines.extend(["", "## Final Dynamic Preflight Items", ""])
    lines.extend(f"- {item}" for item in package.final_dynamic_preflight_items)
    lines.extend(["", "## Sections", ""])
    for section in package.sections:
        lines.append(f"### {section.title}")
        lines.extend(f"- {line}" for line in section.lines)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def make_live_order_approval_handoff_id(
    *,
    operator_review_id: str,
    candidate_id: str,
    created_at: datetime,
    handoff_status: LiveOrderApprovalHandoffStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    _require_non_empty("operator_review_id", operator_review_id)
    _require_non_empty("candidate_id", candidate_id)
    created = _ensure_aware(created_at)
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "handoff_status": handoff_status.value,
        "operator_review_id": operator_review_id,
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{LIVE_ORDER_APPROVAL_HANDOFF_ID_PREFIX}{digest.upper()}"


DISPLAY_ALLOWED_FIELDS = (
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
    "operator_review_status",
    "eligible_for_operator_review",
    "allowed_for_live=false",
    "approval_gate_required=true",
    "approval_gate_issued=false",
    "approval_command_generated=false",
    "final_dynamic_preflight_required=true",
    "blocked_reasons",
    "recommended_next_step",
)

DISPLAY_FORBIDDEN_FIELDS = (
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
    "approval_id",
    "approval command",
)

FINAL_DYNAMIC_PREFLIGHT_ITEMS = (
    "API key / secret presence: set/missing only",
    "account/assets: success",
    "open_positions_count=0",
    "active_orders_count=0",
    "USD_JPY minOpenOrderSize=100",
    "USD_JPY sizeStep=1",
    "public ticker bid/ask retrieval success",
    "spread_jpy <= 0.01",
    "ticker_age_seconds within threshold",
    "market window allowed",
    "maintenance=false",
    "important_event_window_ok=true",
    "ledger unused",
    "daily/session attempt count within policy",
    "previous result confirmed",
    "result_unknown=false",
    "Git clean",
    "tests pass",
    "ruff pass",
    "secret scan pass",
    "raw_response_saved=false",
    "raw_response_displayed=false",
    "outbound body allowlist matches",
    "request body == signing body",
    "final_preflight_age <= 30 seconds",
)


def _handoff_blocked_reasons(
    operator_review: LiveOrderOperatorReviewProcedure,
) -> tuple[str, ...]:
    reasons: list[LiveOrderApprovalHandoffBlockReason | str] = []
    if (
        operator_review.operator_review_status
        is not LiveOrderOperatorReviewStatus.READY_FOR_OPERATOR_CHECKLIST
    ):
        _add_reason(reasons, LiveOrderApprovalHandoffBlockReason.OPERATOR_REVIEW_NOT_READY)
    if operator_review.allowed_for_live is not False:
        _add_reason(
            reasons,
            LiveOrderApprovalHandoffBlockReason.OPERATOR_REVIEW_ALLOWS_LIVE,
        )
    if operator_review.dry_run_only is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalHandoffBlockReason.OPERATOR_REVIEW_NOT_DRY_RUN,
        )
    if operator_review.requires_human_approval is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalHandoffBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        )
    if operator_review.approval_gate_required is not True:
        _add_reason(
            reasons,
            LiveOrderApprovalHandoffBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        )
    if operator_review.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderApprovalHandoffBlockReason.UNSUPPORTED_SYMBOL)
    if operator_review.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, LiveOrderApprovalHandoffBlockReason.UNSUPPORTED_SIDE)
    if operator_review.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderApprovalHandoffBlockReason.UNSUPPORTED_SIZE)
    if operator_review.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(
            reasons,
            LiveOrderApprovalHandoffBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        )
    return tuple(_reason_value(reason) for reason in reasons)


def _handoff_sections(
    blocked_reasons: tuple[str, ...],
) -> tuple[LiveOrderApprovalHandoffSection, ...]:
    if blocked_reasons:
        return (
            LiveOrderApprovalHandoffSection(
                section_id="blocked_handoff",
                title="Blocked Handoff",
                lines=(
                    "Do not proceed to approval gate.",
                    "Do not generate approval_id or approval command.",
                    "Do not proceed to live POST.",
                    f"blocked_reasons={_blocked_text(blocked_reasons)}",
                ),
            ),
        )
    return (
        LiveOrderApprovalHandoffSection(
            section_id="ready_handoff",
            title="Ready Handoff Review",
            lines=(
                "Review sanitized display-allowed fields only.",
                "Do not show display-forbidden fields.",
                "Approval gate must be a separate future Step.",
                "Final dynamic preflight must be a separate future Step.",
            ),
        ),
    )


def _validate_handoff_package(package: LiveOrderApprovalHandoffPackage) -> None:
    _require_non_empty("handoff_id", package.handoff_id)
    if not package.handoff_id.startswith(LIVE_ORDER_APPROVAL_HANDOFF_ID_PREFIX):
        raise LiveVerificationValidationError("handoff_id must be dry-run id")
    _ensure_aware(package.created_at)
    for name, value in (
        ("operator_review_id", package.operator_review_id),
        ("bundle_id", package.bundle_id),
        ("review_id", package.review_id),
        ("candidate_id", package.candidate_id),
        ("risk_decision_id", package.risk_decision_id),
        ("trace_id", package.trace_id),
        ("session_policy_decision_id", package.session_policy_decision_id),
        ("source_signal_id", package.source_signal_id),
        ("source_type", package.source_type),
        ("strategy_name", package.strategy_name),
        ("symbol", package.symbol),
        ("side", package.side),
        ("execution_type", package.execution_type),
        ("operator_review_status", package.operator_review_status),
        ("summary", package.summary),
        ("recommended_next_step", package.recommended_next_step),
    ):
        _require_non_empty(name, value)
    if type(package.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    if package.handoff_status not in set(LiveOrderApprovalHandoffStatus):
        raise LiveVerificationValidationError("unsupported handoff status")
    if type(package.eligible_for_operator_review) is not bool:
        raise LiveVerificationValidationError("eligible_for_operator_review must be bool")
    if package.allowed_for_live is not False:
        raise LiveVerificationValidationError("handoff never allows live execution")
    if package.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if package.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if package.approval_gate_issued is not False:
        raise LiveVerificationValidationError("handoff never issues approval gate")
    if package.approval_command_generated is not False:
        raise LiveVerificationValidationError("handoff never generates approval command")
    if package.final_dynamic_preflight_required is not True:
        raise LiveVerificationValidationError("final dynamic preflight remains required")
    if package.dry_run_only is not True:
        raise LiveVerificationValidationError("handoff must be dry-run only")
    if not package.display_allowed_fields:
        raise LiveVerificationValidationError("handoff requires display allowed fields")
    if not package.display_forbidden_fields:
        raise LiveVerificationValidationError("handoff requires display forbidden fields")
    if not package.final_dynamic_preflight_items:
        raise LiveVerificationValidationError("handoff requires final preflight items")
    if not package.sections:
        raise LiveVerificationValidationError("handoff requires sections")
    if (
        package.handoff_status
        is LiveOrderApprovalHandoffStatus.READY_FOR_APPROVAL_HANDOFF_REVIEW
    ):
        if not package.eligible_for_operator_review:
            raise LiveVerificationValidationError("ready handoff must be eligible")
        if package.blocked_reasons:
            raise LiveVerificationValidationError("ready handoff cannot be blocked")
    else:
        if package.eligible_for_operator_review:
            raise LiveVerificationValidationError("blocked handoff cannot be eligible")
        if not package.blocked_reasons:
            raise LiveVerificationValidationError("blocked handoff requires reasons")


def _add_reason(
    reasons: list[LiveOrderApprovalHandoffBlockReason | str],
    reason: LiveOrderApprovalHandoffBlockReason,
) -> None:
    if reason not in reasons:
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


def _reason_value(value: LiveOrderApprovalHandoffBlockReason | str) -> str:
    if isinstance(value, LiveOrderApprovalHandoffBlockReason):
        return value.value
    return value


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")
