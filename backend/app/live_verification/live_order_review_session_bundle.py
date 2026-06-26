"""Sanitized review-gated session operation bundle for Step 5G."""

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
from app.live_verification.live_order_candidate_review import (
    LiveOrderCandidateReviewReport,
    LiveOrderCandidateReviewStatus,
)
from app.live_verification.live_order_session_policy import (
    ReviewGatedSessionPolicyDecision,
    ReviewGatedSessionPolicyStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

REVIEW_GATED_SESSION_BUNDLE_ID_PREFIX = "LOCBUNDLE-"
UNKNOWN_CAPACITY = "unknown"


class ReviewGatedSessionBundleStatus(str, Enum):
    READY_FOR_OPERATOR_REVIEW = "READY_FOR_OPERATOR_REVIEW"
    BLOCKED_BUNDLE = "BLOCKED_BUNDLE"


class ReviewGatedSessionBundleBlockReason(str, Enum):
    REVIEW_ID_MISMATCH = "review_id_mismatch"
    REVIEW_REPORT_ALLOWS_LIVE = "review_report_allows_live"
    SESSION_POLICY_ALLOWS_LIVE = "session_policy_allows_live"
    REVIEW_REPORT_NOT_DRY_RUN = "review_report_not_dry_run"
    SESSION_POLICY_NOT_DRY_RUN = "session_policy_not_dry_run"
    MISSING_HUMAN_APPROVAL_REQUIREMENT = "missing_human_approval_requirement"
    MISSING_APPROVAL_GATE_REQUIREMENT = "missing_approval_gate_requirement"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    MISSING_SESSION_COUNT = "missing_session_count"
    MISSING_DAILY_SIZE_TOTAL = "missing_daily_size_total"
    INVALID_REMAINING_SESSIONS = "invalid_remaining_sessions"
    INVALID_REMAINING_DAILY_SIZE = "invalid_remaining_daily_size"


@dataclass(frozen=True)
class ReviewGatedSessionBundleSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError("bundle section requires lines")
        for line in self.lines:
            _require_non_empty("section line", line)


@dataclass(frozen=True)
class ReviewGatedSessionBundle:
    bundle_id: str
    created_at: datetime
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
    review_status: str
    policy_status: str
    bundle_status: ReviewGatedSessionBundleStatus
    risk_gate_passed: bool
    eligible_for_human_review: bool
    policy_passed: bool
    eligible_for_review_session: bool
    allowed_for_live: bool
    requires_human_approval: bool
    approval_gate_required: bool
    dry_run_only: bool
    blocked_reasons: tuple[str, ...]
    session_size: int
    session_count_today: int | str
    max_sessions_per_day: int
    remaining_sessions_today: int | str
    daily_live_size_total: int | str
    max_daily_size_total: int
    remaining_daily_size: int | str
    min_minutes_between_sessions: int
    minutes_since_last_session: int | str
    next_session_time_hint: str
    summary: str
    recommended_next_step: str
    sections: tuple[ReviewGatedSessionBundleSection, ...]

    def __post_init__(self) -> None:
        _validate_bundle(self)


@dataclass(frozen=True)
class ReviewGatedSessionBundleBuildResult:
    bundle: ReviewGatedSessionBundle
    bundle_id: str
    bundle_status: ReviewGatedSessionBundleStatus
    blocked_reasons: tuple[str, ...]
    allowed_for_live: bool
    eligible_for_review_session: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.bundle.bundle_id != self.bundle_id:
            raise LiveVerificationValidationError("bundle_id mismatch")
        if self.bundle.bundle_status is not self.bundle_status:
            raise LiveVerificationValidationError("bundle_status mismatch")
        if self.bundle.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("bundle build never allows live execution")
        if self.bundle.allowed_for_live is not False:
            raise LiveVerificationValidationError("bundle never allows live execution")
        if type(self.eligible_for_review_session) is not bool:
            raise LiveVerificationValidationError("eligible_for_review_session must be bool")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def build_review_gated_session_bundle(
    *,
    review_report: LiveOrderCandidateReviewReport,
    session_policy_decision: ReviewGatedSessionPolicyDecision,
    created_at: datetime | None = None,
    session_count_today: int | None = None,
    daily_live_size_total: int | None = None,
    max_sessions_per_day: int | None = None,
    max_daily_size_total: int | None = None,
    min_minutes_between_sessions: int | None = None,
    minutes_since_last_session: int | None = None,
    next_session_time_hint: str | None = None,
) -> ReviewGatedSessionBundleBuildResult:
    """Build a sanitized operation bundle without approval or live execution."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    max_sessions = _fallback_positive_int(
        max_sessions_per_day,
        session_policy_decision.max_sessions_per_day,
    )
    max_daily_size = _fallback_positive_int(
        max_daily_size_total,
        session_policy_decision.max_daily_size_total,
    )
    min_minutes = _fallback_positive_int(
        min_minutes_between_sessions,
        session_policy_decision.min_minutes_between_sessions,
    )
    remaining_sessions = _remaining_capacity(max_sessions, session_count_today)
    remaining_daily_size = _remaining_capacity(max_daily_size, daily_live_size_total)

    blocked_reasons = _bundle_blocked_reasons(
        review_report=review_report,
        session_policy_decision=session_policy_decision,
        session_count_today=session_count_today,
        daily_live_size_total=daily_live_size_total,
        remaining_sessions_today=remaining_sessions,
        remaining_daily_size=remaining_daily_size,
    )
    blocked_reasons = _merge_reasons(
        blocked_reasons,
        review_report.blocked_reasons,
        session_policy_decision.blocked_reasons,
    )

    if blocked_reasons:
        bundle_status = ReviewGatedSessionBundleStatus.BLOCKED_BUNDLE
        eligible_for_review_session = False
        policy_passed = False
        recommended_next_step = "fix_blocked_reasons_no_post"
        summary = "blocked operation bundle; live post remains disallowed"
    else:
        bundle_status = ReviewGatedSessionBundleStatus.READY_FOR_OPERATOR_REVIEW
        eligible_for_review_session = True
        policy_passed = True
        recommended_next_step = "operator_review_no_post"
        summary = "ready for operator review only; live post remains disallowed"

    bundle_id = make_review_gated_session_bundle_id(
        review_id=review_report.review_id,
        session_policy_decision_id=session_policy_decision.decision_id,
        candidate_id=review_report.candidate_id,
        created_at=created,
        bundle_status=bundle_status,
        blocked_reasons=blocked_reasons,
    )
    minutes_value: int | str = (
        minutes_since_last_session
        if _valid_int(minutes_since_last_session)
        else UNKNOWN_CAPACITY
    )
    next_hint = (
        next_session_time_hint.strip()
        if _has_text(next_session_time_hint)
        else "not_calculated_no_post"
    )
    sections = _build_sections(
        review_report=review_report,
        session_policy_decision=session_policy_decision,
        bundle_status=bundle_status,
        blocked_reasons=blocked_reasons,
        session_count_today=_capacity_value(session_count_today),
        remaining_sessions_today=remaining_sessions,
        daily_live_size_total=_capacity_value(daily_live_size_total),
        remaining_daily_size=remaining_daily_size,
        max_sessions_per_day=max_sessions,
        max_daily_size_total=max_daily_size,
        min_minutes_between_sessions=min_minutes,
        minutes_since_last_session=minutes_value,
        next_session_time_hint=next_hint,
        recommended_next_step=recommended_next_step,
    )
    bundle = ReviewGatedSessionBundle(
        bundle_id=bundle_id,
        created_at=created,
        review_id=review_report.review_id,
        candidate_id=review_report.candidate_id,
        risk_decision_id=review_report.risk_decision_id,
        trace_id=review_report.trace_id,
        session_policy_decision_id=session_policy_decision.decision_id,
        source_signal_id=review_report.source_signal_id,
        source_type=review_report.source_type,
        strategy_name=review_report.strategy_name,
        symbol=review_report.symbol,
        side=review_report.side,
        size=review_report.size,
        execution_type=review_report.execution_type,
        review_status=_enum_value(review_report.review_status),
        policy_status=_enum_value(session_policy_decision.status),
        bundle_status=bundle_status,
        risk_gate_passed=review_report.risk_gate_passed,
        eligible_for_human_review=review_report.eligible_for_human_review,
        policy_passed=policy_passed,
        eligible_for_review_session=eligible_for_review_session,
        allowed_for_live=False,
        requires_human_approval=True,
        approval_gate_required=True,
        dry_run_only=True,
        blocked_reasons=blocked_reasons,
        session_size=session_policy_decision.session_size,
        session_count_today=_capacity_value(session_count_today),
        max_sessions_per_day=max_sessions,
        remaining_sessions_today=remaining_sessions,
        daily_live_size_total=_capacity_value(daily_live_size_total),
        max_daily_size_total=max_daily_size,
        remaining_daily_size=remaining_daily_size,
        min_minutes_between_sessions=min_minutes,
        minutes_since_last_session=minutes_value,
        next_session_time_hint=next_hint,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=sections,
    )
    return ReviewGatedSessionBundleBuildResult(
        bundle=bundle,
        bundle_id=bundle.bundle_id,
        bundle_status=bundle.bundle_status,
        blocked_reasons=bundle.blocked_reasons,
        allowed_for_live=False,
        eligible_for_review_session=bundle.eligible_for_review_session,
        recommended_next_step=bundle.recommended_next_step,
    )


def render_review_gated_session_bundle_markdown(
    bundle: ReviewGatedSessionBundle,
) -> str:
    """Render a sanitized dry-run operation bundle for human inspection."""
    lines = [
        "# Review-gated Session Operation Bundle",
        "",
        "This operation bundle is dry-run only.",
        "This bundle is not an approval gate.",
        "This bundle does not authorize live POST.",
        "allowed_for_live=false.",
        "",
        "## Summary",
        "",
        f"- bundle_id: {bundle.bundle_id}",
        f"- bundle_status: {bundle.bundle_status.value}",
        f"- summary: {bundle.summary}",
        f"- recommended_next_step: {bundle.recommended_next_step}",
        "",
    ]
    for section in bundle.sections:
        lines.extend([f"## {section.title}", ""])
        lines.extend(f"- {line}" for line in section.lines)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def make_review_gated_session_bundle_id(
    *,
    review_id: str,
    session_policy_decision_id: str,
    candidate_id: str,
    created_at: datetime,
    bundle_status: ReviewGatedSessionBundleStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    _require_non_empty("review_id", review_id)
    _require_non_empty("session_policy_decision_id", session_policy_decision_id)
    _require_non_empty("candidate_id", candidate_id)
    created = _ensure_aware(created_at)
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "bundle_status": bundle_status.value,
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "review_id": review_id,
        "session_policy_decision_id": session_policy_decision_id,
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{REVIEW_GATED_SESSION_BUNDLE_ID_PREFIX}{digest.upper()}"


def _bundle_blocked_reasons(
    *,
    review_report: LiveOrderCandidateReviewReport,
    session_policy_decision: ReviewGatedSessionPolicyDecision,
    session_count_today: int | None,
    daily_live_size_total: int | None,
    remaining_sessions_today: int | str,
    remaining_daily_size: int | str,
) -> tuple[str, ...]:
    reasons: list[ReviewGatedSessionBundleBlockReason] = []

    if review_report.review_id != session_policy_decision.review_id:
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.REVIEW_ID_MISMATCH)
    if review_report.allowed_for_live is not False:
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.REVIEW_REPORT_ALLOWS_LIVE)
    if session_policy_decision.allowed_for_live is not False:
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.SESSION_POLICY_ALLOWS_LIVE)
    if review_report.dry_run_only is not True:
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.REVIEW_REPORT_NOT_DRY_RUN)
    if session_policy_decision.dry_run_only is not True:
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.SESSION_POLICY_NOT_DRY_RUN)
    if (
        review_report.requires_human_approval is not True
        or session_policy_decision.requires_human_approval is not True
    ):
        _add_reason(
            reasons,
            ReviewGatedSessionBundleBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        )
    if (
        review_report.approval_gate_required is not True
        or session_policy_decision.approval_gate_required is not True
    ):
        _add_reason(
            reasons,
            ReviewGatedSessionBundleBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        )
    if review_report.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.UNSUPPORTED_SYMBOL)
    if review_report.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.UNSUPPORTED_SIDE)
    if review_report.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.UNSUPPORTED_SIZE)
    if review_report.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.UNSUPPORTED_EXECUTION_TYPE)
    if review_report.review_status is not LiveOrderCandidateReviewStatus.READY_FOR_HUMAN_REVIEW:
        _add_external_reason(reasons, "invalid_review_status")
    if (
        session_policy_decision.status
        is not ReviewGatedSessionPolicyStatus.POLICY_PASSED_FOR_REVIEW
    ):
        _add_external_reason(reasons, "invalid_policy_status")
    if review_report.eligible_for_human_review is not True:
        _add_external_reason(reasons, "review_not_human_review_eligible")
    if session_policy_decision.eligible_for_review_session is not True:
        _add_external_reason(reasons, "policy_not_review_session_eligible")
    if session_policy_decision.policy_passed is not True:
        _add_external_reason(reasons, "policy_not_passed")
    if not _valid_int(session_count_today):
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.MISSING_SESSION_COUNT)
    if not _valid_int(daily_live_size_total):
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.MISSING_DAILY_SIZE_TOTAL)
    if not isinstance(remaining_sessions_today, int) or remaining_sessions_today < 0:
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.INVALID_REMAINING_SESSIONS)
    if not isinstance(remaining_daily_size, int) or remaining_daily_size < 0:
        _add_reason(reasons, ReviewGatedSessionBundleBlockReason.INVALID_REMAINING_DAILY_SIZE)
    return tuple(_reason_value(reason) for reason in reasons)


def _build_sections(
    *,
    review_report: LiveOrderCandidateReviewReport,
    session_policy_decision: ReviewGatedSessionPolicyDecision,
    bundle_status: ReviewGatedSessionBundleStatus,
    blocked_reasons: tuple[str, ...],
    session_count_today: int | str,
    remaining_sessions_today: int | str,
    daily_live_size_total: int | str,
    remaining_daily_size: int | str,
    max_sessions_per_day: int,
    max_daily_size_total: int,
    min_minutes_between_sessions: int,
    minutes_since_last_session: int | str,
    next_session_time_hint: str,
    recommended_next_step: str,
) -> tuple[ReviewGatedSessionBundleSection, ...]:
    blocked_text = ", ".join(blocked_reasons) if blocked_reasons else "none"
    return (
        ReviewGatedSessionBundleSection(
            section_id="review",
            title="Review Report",
            lines=(
                f"review_id: {review_report.review_id}",
                f"candidate_id: {review_report.candidate_id}",
                f"risk_decision_id: {review_report.risk_decision_id}",
                f"trace_id: {review_report.trace_id}",
                f"review_status: {_enum_value(review_report.review_status)}",
                f"risk_gate_passed: {review_report.risk_gate_passed}",
                f"eligible_for_human_review: {review_report.eligible_for_human_review}",
            ),
        ),
        ReviewGatedSessionBundleSection(
            section_id="candidate",
            title="Candidate",
            lines=(
                f"source_signal_id: {review_report.source_signal_id}",
                f"source_type: {review_report.source_type}",
                f"strategy_name: {review_report.strategy_name}",
                f"symbol: {review_report.symbol}",
                f"side: {review_report.side}",
                f"size: {review_report.size}",
                f"executionType: {review_report.execution_type}",
            ),
        ),
        ReviewGatedSessionBundleSection(
            section_id="session_policy",
            title="Session Policy",
            lines=(
                f"session_policy_decision_id: {session_policy_decision.decision_id}",
                f"policy_status: {_enum_value(session_policy_decision.status)}",
                f"policy_passed: {session_policy_decision.policy_passed}",
                "eligible_for_review_session: "
                f"{session_policy_decision.eligible_for_review_session}",
                f"session_count_today: {session_count_today}",
                f"max_sessions_per_day: {max_sessions_per_day}",
                f"remaining_sessions_today: {remaining_sessions_today}",
                f"daily_live_size_total: {daily_live_size_total}",
                f"max_daily_size_total: {max_daily_size_total}",
                f"remaining_daily_size: {remaining_daily_size}",
                f"min_minutes_between_sessions: {min_minutes_between_sessions}",
                f"minutes_since_last_session: {minutes_since_last_session}",
                f"next_session_time_hint: {next_session_time_hint}",
            ),
        ),
        ReviewGatedSessionBundleSection(
            section_id="bundle",
            title="Operation Bundle",
            lines=(
                f"bundle_status: {bundle_status.value}",
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


def _remaining_capacity(max_value: int, used_value: int | None) -> int | str:
    if not _valid_int(used_value):
        return UNKNOWN_CAPACITY
    return max_value - used_value


def _capacity_value(value: int | None) -> int | str:
    return value if _valid_int(value) else UNKNOWN_CAPACITY


def _fallback_positive_int(candidate: int | None, fallback: int) -> int:
    if _valid_positive_int(candidate):
        return candidate
    return fallback if _valid_positive_int(fallback) else 0


def _validate_bundle(bundle: ReviewGatedSessionBundle) -> None:
    _require_non_empty("bundle_id", bundle.bundle_id)
    if not bundle.bundle_id.startswith(REVIEW_GATED_SESSION_BUNDLE_ID_PREFIX):
        raise LiveVerificationValidationError("bundle_id must be dry-run bundle id")
    _ensure_aware(bundle.created_at)
    for name, value in (
        ("review_id", bundle.review_id),
        ("candidate_id", bundle.candidate_id),
        ("risk_decision_id", bundle.risk_decision_id),
        ("trace_id", bundle.trace_id),
        ("session_policy_decision_id", bundle.session_policy_decision_id),
        ("source_signal_id", bundle.source_signal_id),
        ("source_type", bundle.source_type),
        ("strategy_name", bundle.strategy_name),
        ("symbol", bundle.symbol),
        ("side", bundle.side),
        ("execution_type", bundle.execution_type),
        ("review_status", bundle.review_status),
        ("policy_status", bundle.policy_status),
        ("next_session_time_hint", bundle.next_session_time_hint),
        ("summary", bundle.summary),
        ("recommended_next_step", bundle.recommended_next_step),
    ):
        _require_non_empty(name, value)
    if type(bundle.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    if bundle.bundle_status not in set(ReviewGatedSessionBundleStatus):
        raise LiveVerificationValidationError("unsupported bundle status")
    for field_name, value in (
        ("risk_gate_passed", bundle.risk_gate_passed),
        ("eligible_for_human_review", bundle.eligible_for_human_review),
        ("policy_passed", bundle.policy_passed),
        ("eligible_for_review_session", bundle.eligible_for_review_session),
    ):
        if type(value) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")
    if bundle.allowed_for_live is not False:
        raise LiveVerificationValidationError("Step 5G never allows live execution")
    if bundle.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if bundle.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if bundle.dry_run_only is not True:
        raise LiveVerificationValidationError("bundle must be dry-run only")
    for field_name, value in (
        ("session_size", bundle.session_size),
        ("max_sessions_per_day", bundle.max_sessions_per_day),
        ("max_daily_size_total", bundle.max_daily_size_total),
        ("min_minutes_between_sessions", bundle.min_minutes_between_sessions),
    ):
        if not _valid_positive_int(value):
            raise LiveVerificationValidationError(f"{field_name} must be positive int")
    if bundle.bundle_status is ReviewGatedSessionBundleStatus.READY_FOR_OPERATOR_REVIEW:
        if not bundle.eligible_for_review_session or not bundle.policy_passed:
            raise LiveVerificationValidationError("ready bundle must be review-session eligible")
        if bundle.blocked_reasons:
            raise LiveVerificationValidationError("ready bundle cannot have blocked reasons")
    else:
        if bundle.eligible_for_review_session or bundle.policy_passed:
            raise LiveVerificationValidationError("blocked bundle cannot pass")
        if not bundle.blocked_reasons:
            raise LiveVerificationValidationError("blocked bundle requires blocked reasons")
    if not bundle.sections:
        raise LiveVerificationValidationError("bundle requires sections")


def _add_reason(
    reasons: list[ReviewGatedSessionBundleBlockReason | str],
    reason: ReviewGatedSessionBundleBlockReason,
) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _add_external_reason(
    reasons: list[ReviewGatedSessionBundleBlockReason | str],
    reason: str,
) -> None:
    if _has_text(reason) and reason not in reasons:
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


def _reason_value(value: ReviewGatedSessionBundleBlockReason | str) -> str:
    if isinstance(value, ReviewGatedSessionBundleBlockReason):
        return value.value
    return value


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")


def _valid_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _valid_positive_int(value: object) -> bool:
    return type(value) is int and value > 0
