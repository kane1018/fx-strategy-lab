"""Sanitized review report model for Step 5E live-order candidates."""

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
    LiveOrderCandidate,
    LiveOrderCandidateSide,
)
from app.live_verification.live_order_candidate_risk_gate import (
    LiveOrderCandidateRiskDecision,
    LiveOrderCandidateRiskStatus,
)
from app.live_verification.live_order_candidate_trace import (
    LiveOrderCandidateTraceRecord,
    LiveOrderCandidateTraceStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_CANDIDATE_REVIEW_ID_PREFIX = "LOCREVIEW-"


class LiveOrderCandidateReviewStatus(str, Enum):
    READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"
    BLOCKED_REVIEW = "BLOCKED_REVIEW"


class LiveOrderCandidateReviewBlockReason(str, Enum):
    CANDIDATE_ID_MISMATCH = "candidate_id_mismatch"
    RISK_DECISION_ID_MISMATCH = "risk_decision_id_mismatch"
    MISSING_TRACE_ID = "missing_trace_id"
    CANDIDATE_ALREADY_ALLOWED_FOR_LIVE = "candidate_already_allowed_for_live"
    RISK_DECISION_ALLOWS_LIVE = "risk_decision_allows_live"
    TRACE_RECORD_ALLOWS_LIVE = "trace_record_allows_live"
    CANDIDATE_NOT_DRY_RUN = "candidate_not_dry_run"
    RISK_DECISION_NOT_DRY_RUN = "risk_decision_not_dry_run"
    TRACE_RECORD_NOT_DRY_RUN = "trace_record_not_dry_run"
    MISSING_HUMAN_APPROVAL_REQUIREMENT = "missing_human_approval_requirement"
    MISSING_APPROVAL_GATE_REQUIREMENT = "missing_approval_gate_requirement"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"


@dataclass(frozen=True)
class LiveOrderCandidateReviewSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError("review section requires lines")
        for line in self.lines:
            _require_non_empty("section line", line)


@dataclass(frozen=True)
class LiveOrderCandidateReviewReport:
    review_id: str
    created_at: datetime
    candidate_id: str
    risk_decision_id: str
    trace_id: str
    source_signal_id: str
    source_type: str
    strategy_name: str
    paper_trade_ref: str | None
    shadow_run_ref: str | None
    symbol: str
    side: str
    size: int
    execution_type: str
    candidate_status: str
    risk_status: str
    trace_status: str
    review_status: LiveOrderCandidateReviewStatus
    risk_gate_passed: bool
    eligible_for_human_review: bool
    allowed_for_live: bool
    requires_human_approval: bool
    approval_gate_required: bool
    dry_run_only: bool
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderCandidateReviewSection, ...]

    def __post_init__(self) -> None:
        _validate_review_report(self)


@dataclass(frozen=True)
class LiveOrderCandidateReviewBuildResult:
    review_report: LiveOrderCandidateReviewReport
    review_id: str
    review_status: LiveOrderCandidateReviewStatus
    blocked_reasons: tuple[str, ...]
    allowed_for_live: bool
    eligible_for_human_review: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.review_report.review_id != self.review_id:
            raise LiveVerificationValidationError("review_id mismatch")
        if self.review_report.review_status is not self.review_status:
            raise LiveVerificationValidationError("review_status mismatch")
        if self.review_report.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("review build never allows live execution")
        if self.review_report.allowed_for_live is not False:
            raise LiveVerificationValidationError("review report never allows live execution")
        if type(self.eligible_for_human_review) is not bool:
            raise LiveVerificationValidationError("eligible_for_human_review must be bool")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def build_live_order_candidate_review_report(
    *,
    candidate: LiveOrderCandidate,
    risk_decision: LiveOrderCandidateRiskDecision,
    trace_record: LiveOrderCandidateTraceRecord,
    created_at: datetime | None = None,
) -> LiveOrderCandidateReviewBuildResult:
    """Build a sanitized human-readable review report without live execution."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    blocked_reasons = _review_blocked_reasons(
        candidate=candidate,
        risk_decision=risk_decision,
        trace_record=trace_record,
    )
    blocked_reasons = _merge_reasons(
        blocked_reasons,
        risk_decision.blocked_reasons,
        trace_record.blocked_reasons,
    )

    if blocked_reasons:
        review_status = LiveOrderCandidateReviewStatus.BLOCKED_REVIEW
        eligible_for_human_review = False
        risk_gate_passed = False
        recommended_next_step = "fix_blocked_reasons_no_post"
        summary = "blocked review report; live post remains disallowed"
    else:
        review_status = LiveOrderCandidateReviewStatus.READY_FOR_HUMAN_REVIEW
        eligible_for_human_review = True
        risk_gate_passed = True
        recommended_next_step = "show_to_user_for_review_no_post"
        summary = "ready for human review report only; live post remains disallowed"

    trace_id = (
        trace_record.trace_id
        if _has_text(trace_record.trace_id)
        else LiveOrderCandidateReviewBlockReason.MISSING_TRACE_ID.value
    )
    review_id = make_live_order_candidate_review_id(
        candidate_id=candidate.candidate_id,
        risk_decision_id=risk_decision.decision_id,
        trace_id=trace_id,
        created_at=created,
        review_status=review_status,
        blocked_reasons=blocked_reasons,
    )
    sections = _build_sections(
        candidate=candidate,
        risk_decision=risk_decision,
        trace_record=trace_record,
        review_status=review_status,
        blocked_reasons=blocked_reasons,
        recommended_next_step=recommended_next_step,
    )
    report = LiveOrderCandidateReviewReport(
        review_id=review_id,
        created_at=created,
        candidate_id=candidate.candidate_id,
        risk_decision_id=risk_decision.decision_id,
        trace_id=trace_id,
        source_signal_id=trace_record.source_signal_id,
        source_type=trace_record.source_type,
        strategy_name=trace_record.strategy_name,
        paper_trade_ref=trace_record.paper_trade_ref,
        shadow_run_ref=trace_record.shadow_run_ref,
        symbol=candidate.symbol,
        side=_enum_value(candidate.side),
        size=candidate.size,
        execution_type=candidate.execution_type,
        candidate_status=_enum_value(candidate.status),
        risk_status=_enum_value(risk_decision.status),
        trace_status=_enum_value(trace_record.trace_status),
        review_status=review_status,
        risk_gate_passed=risk_gate_passed,
        eligible_for_human_review=eligible_for_human_review,
        allowed_for_live=False,
        requires_human_approval=True,
        approval_gate_required=True,
        dry_run_only=True,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=sections,
    )
    return LiveOrderCandidateReviewBuildResult(
        review_report=report,
        review_id=report.review_id,
        review_status=report.review_status,
        blocked_reasons=report.blocked_reasons,
        allowed_for_live=False,
        eligible_for_human_review=report.eligible_for_human_review,
        recommended_next_step=report.recommended_next_step,
    )


def render_live_order_candidate_review_markdown(
    report: LiveOrderCandidateReviewReport,
) -> str:
    """Render a sanitized dry-run review report for human inspection."""
    lines = [
        "# Live Order Candidate Review Report",
        "",
        "This review report is dry-run only.",
        "This report is not an approval gate.",
        "This report does not authorize live POST.",
        "allowed_for_live=false.",
        "",
        "## Summary",
        "",
        f"- review_id: {report.review_id}",
        f"- review_status: {report.review_status.value}",
        f"- summary: {report.summary}",
        f"- recommended_next_step: {report.recommended_next_step}",
        "",
    ]
    for section in report.sections:
        lines.extend([f"## {section.title}", ""])
        lines.extend(f"- {line}" for line in section.lines)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def make_live_order_candidate_review_id(
    *,
    candidate_id: str,
    risk_decision_id: str,
    trace_id: str,
    created_at: datetime,
    review_status: LiveOrderCandidateReviewStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    _require_non_empty("candidate_id", candidate_id)
    _require_non_empty("risk_decision_id", risk_decision_id)
    _require_non_empty("trace_id", trace_id)
    created = _ensure_aware(created_at)
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "review_status": review_status.value,
        "risk_decision_id": risk_decision_id,
        "trace_id": trace_id,
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{LIVE_ORDER_CANDIDATE_REVIEW_ID_PREFIX}{digest.upper()}"


def _review_blocked_reasons(
    *,
    candidate: LiveOrderCandidate,
    risk_decision: LiveOrderCandidateRiskDecision,
    trace_record: LiveOrderCandidateTraceRecord,
) -> tuple[str, ...]:
    reasons: list[LiveOrderCandidateReviewBlockReason] = []

    if candidate.candidate_id != risk_decision.candidate_id:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.CANDIDATE_ID_MISMATCH)
    if candidate.candidate_id != trace_record.candidate_id:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.CANDIDATE_ID_MISMATCH)
    if risk_decision.decision_id != trace_record.risk_decision_id:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.RISK_DECISION_ID_MISMATCH)
    if not _has_text(trace_record.trace_id):
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.MISSING_TRACE_ID)

    if candidate.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.CANDIDATE_ALREADY_ALLOWED_FOR_LIVE)
    if risk_decision.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.RISK_DECISION_ALLOWS_LIVE)
    if trace_record.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.TRACE_RECORD_ALLOWS_LIVE)

    if candidate.dry_run_only is not True:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.CANDIDATE_NOT_DRY_RUN)
    if risk_decision.dry_run_only is not True:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.RISK_DECISION_NOT_DRY_RUN)
    if trace_record.dry_run_only is not True:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.TRACE_RECORD_NOT_DRY_RUN)

    if (
        candidate.requires_human_approval is not True
        or risk_decision.requires_human_approval is not True
        or trace_record.requires_human_approval is not True
    ):
        _add_reason(
            reasons,
            LiveOrderCandidateReviewBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        )
    if (
        candidate.approval_gate_required is not True
        or risk_decision.approval_gate_required is not True
        or trace_record.approval_gate_required is not True
    ):
        _add_reason(
            reasons,
            LiveOrderCandidateReviewBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        )

    if candidate.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.UNSUPPORTED_SYMBOL)
    if _enum_value(candidate.side) not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.UNSUPPORTED_SIDE)
    if candidate.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.UNSUPPORTED_SIZE)
    if candidate.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, LiveOrderCandidateReviewBlockReason.UNSUPPORTED_EXECUTION_TYPE)

    if risk_decision.status is LiveOrderCandidateRiskStatus.BLOCKED:
        return tuple(reason.value for reason in reasons)
    if trace_record.trace_status is not LiveOrderCandidateTraceStatus.READY_FOR_REVIEW:
        return tuple(reason.value for reason in reasons)
    if risk_decision.risk_gate_passed is not True or trace_record.risk_gate_passed is not True:
        return tuple(reason.value for reason in reasons)
    if (
        risk_decision.eligible_for_human_review is not True
        or trace_record.eligible_for_human_review is not True
    ):
        return tuple(reason.value for reason in reasons)
    return tuple(reason.value for reason in reasons)


def _build_sections(
    *,
    candidate: LiveOrderCandidate,
    risk_decision: LiveOrderCandidateRiskDecision,
    trace_record: LiveOrderCandidateTraceRecord,
    review_status: LiveOrderCandidateReviewStatus,
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
) -> tuple[LiveOrderCandidateReviewSection, ...]:
    blocked_text = ", ".join(blocked_reasons) if blocked_reasons else "none"
    return (
        LiveOrderCandidateReviewSection(
            section_id="candidate",
            title="Candidate",
            lines=(
                f"candidate_id: {candidate.candidate_id}",
                f"source_signal_id: {candidate.source_signal_id}",
                f"source_type: {_enum_value(candidate.source_type)}",
                f"strategy_name: {candidate.strategy_name}",
                f"paper_trade_ref: {_optional_text(candidate.paper_trade_ref)}",
                f"shadow_run_ref: {_optional_text(candidate.shadow_run_ref)}",
                f"symbol: {candidate.symbol}",
                f"side: {_enum_value(candidate.side)}",
                f"size: {candidate.size}",
                f"executionType: {candidate.execution_type}",
                f"candidate_status: {_enum_value(candidate.status)}",
            ),
        ),
        LiveOrderCandidateReviewSection(
            section_id="risk",
            title="Risk Decision",
            lines=(
                f"risk_decision_id: {risk_decision.decision_id}",
                f"risk_status: {_enum_value(risk_decision.status)}",
                f"risk_gate_passed: {risk_decision.risk_gate_passed}",
                f"eligible_for_human_review: {risk_decision.eligible_for_human_review}",
            ),
        ),
        LiveOrderCandidateReviewSection(
            section_id="trace",
            title="Trace Record",
            lines=(
                f"trace_id: {trace_record.trace_id}",
                f"trace_status: {_enum_value(trace_record.trace_status)}",
                f"allowed_for_live: {trace_record.allowed_for_live}",
                f"dry_run_only: {trace_record.dry_run_only}",
            ),
        ),
        LiveOrderCandidateReviewSection(
            section_id="review",
            title="Review Decision",
            lines=(
                f"review_status: {review_status.value}",
                "allowed_for_live: False",
                f"blocked_reasons: {blocked_text}",
                f"recommended_next_step: {recommended_next_step}",
            ),
        ),
    )


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            if _has_text(reason) and reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _validate_review_report(report: LiveOrderCandidateReviewReport) -> None:
    _require_non_empty("review_id", report.review_id)
    if not report.review_id.startswith(LIVE_ORDER_CANDIDATE_REVIEW_ID_PREFIX):
        raise LiveVerificationValidationError("review_id must be dry-run review id")
    _ensure_aware(report.created_at)
    for name, value in (
        ("candidate_id", report.candidate_id),
        ("risk_decision_id", report.risk_decision_id),
        ("trace_id", report.trace_id),
        ("source_signal_id", report.source_signal_id),
        ("source_type", report.source_type),
        ("strategy_name", report.strategy_name),
        ("symbol", report.symbol),
        ("side", report.side),
        ("execution_type", report.execution_type),
        ("candidate_status", report.candidate_status),
        ("risk_status", report.risk_status),
        ("trace_status", report.trace_status),
        ("summary", report.summary),
        ("recommended_next_step", report.recommended_next_step),
    ):
        _require_non_empty(name, value)
    if type(report.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    if report.review_status not in set(LiveOrderCandidateReviewStatus):
        raise LiveVerificationValidationError("review_status is not supported")
    if type(report.risk_gate_passed) is not bool:
        raise LiveVerificationValidationError("risk_gate_passed must be bool")
    if type(report.eligible_for_human_review) is not bool:
        raise LiveVerificationValidationError("eligible_for_human_review must be bool")
    if report.allowed_for_live is not False:
        raise LiveVerificationValidationError("Step 5E never allows live execution")
    if report.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if report.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if report.dry_run_only is not True:
        raise LiveVerificationValidationError("review report must be dry-run only")
    if report.review_status is LiveOrderCandidateReviewStatus.READY_FOR_HUMAN_REVIEW:
        if report.blocked_reasons:
            raise LiveVerificationValidationError("ready review cannot have blocked reasons")
        if not report.risk_gate_passed or not report.eligible_for_human_review:
            raise LiveVerificationValidationError("ready review must be human-review eligible")
    else:
        if report.risk_gate_passed or report.eligible_for_human_review:
            raise LiveVerificationValidationError("blocked review cannot pass")
        if not report.blocked_reasons:
            raise LiveVerificationValidationError("blocked review requires blocked reasons")
    if not report.sections:
        raise LiveVerificationValidationError("review report requires sections")


def _add_reason(
    reasons: list[LiveOrderCandidateReviewBlockReason],
    reason: LiveOrderCandidateReviewBlockReason,
) -> None:
    if reason not in reasons:
        reasons.append(reason)


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


def _optional_text(value: str | None) -> str:
    return value.strip() if _has_text(value) else "none"


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")
