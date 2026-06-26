"""Review-gated session policy model for Step 5F."""

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
from app.live_verification.precheck import SUPPORTED_SYMBOL

REVIEW_GATED_SESSION_POLICY_DECISION_ID_PREFIX = "LOCPOLICY-"
REVIEW_GATED_SESSION_SIZE = LIVE_ORDER_CANDIDATE_SIZE
REVIEW_GATED_MAX_SESSIONS_PER_DAY = 2
REVIEW_GATED_MIN_MINUTES_BETWEEN_SESSIONS = 120
REVIEW_GATED_MAX_DAILY_SIZE_TOTAL = 200


class ReviewGatedSessionPolicyStatus(str, Enum):
    POLICY_PASSED_FOR_REVIEW = "POLICY_PASSED_FOR_REVIEW"
    BLOCKED = "BLOCKED"


class ReviewGatedSessionPolicyBlockReason(str, Enum):
    INVALID_REVIEW_STATUS = "invalid_review_status"
    REVIEW_ALREADY_ALLOWED_FOR_LIVE = "review_already_allowed_for_live"
    REVIEW_NOT_DRY_RUN = "review_not_dry_run"
    MISSING_HUMAN_APPROVAL_REQUIREMENT = "missing_human_approval_requirement"
    MISSING_APPROVAL_GATE_REQUIREMENT = "missing_approval_gate_requirement"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    INITIAL_MICRO_LIVE_NOT_COMPLETED = "initial_micro_live_not_completed"
    PREVIOUS_ORDER_RESULT_NOT_CONFIRMED = "previous_order_result_not_confirmed"
    PREVIOUS_RESULT_UNKNOWN_STATE = "previous_result_unknown_state"
    OPEN_POSITION_EXISTS = "open_position_exists"
    ACTIVE_ORDER_EXISTS = "active_order_exists"
    MAX_SESSIONS_PER_DAY_REACHED = "max_sessions_per_day_reached"
    UNSUPPORTED_SESSION_SIZE = "unsupported_session_size"
    DAILY_SIZE_LIMIT_EXCEEDED = "daily_size_limit_exceeded"
    SESSION_INTERVAL_TOO_SHORT = "session_interval_too_short"
    GIT_NOT_CLEAN = "git_not_clean"
    TESTS_NOT_PASSED = "tests_not_passed"
    RUFF_NOT_PASSED = "ruff_not_passed"
    SECRET_SCAN_NOT_PASSED = "secret_scan_not_passed"
    RAW_RESPONSE_SAVED = "raw_response_saved"
    RAW_RESPONSE_DISPLAYED = "raw_response_displayed"
    MARKET_WINDOW_NOT_ALLOWED = "market_window_not_allowed"
    MAINTENANCE_ACTIVE = "maintenance_active"
    IMPORTANT_EVENT_WINDOW_NOT_CONFIRMED = "important_event_window_not_confirmed"
    MISSING_REQUIRED_SESSION_INPUT = "missing_required_session_input"
    INVALID_SESSION_INPUT = "invalid_session_input"


@dataclass(frozen=True)
class ReviewGatedSessionPolicySnapshot:
    snapshot_id: str | None
    created_at: datetime | None
    policy_date: str | None
    initial_micro_live_completed: bool | None
    previous_order_result_confirmed: bool | None
    previous_result_unknown: bool | None
    open_positions_count: int | None
    active_orders_count: int | None
    session_count_today: int | None
    daily_live_size_total: int | None
    last_session_completed_at: datetime | None = None
    minutes_since_last_session: int | None = None
    session_size: int | None = REVIEW_GATED_SESSION_SIZE
    max_sessions_per_day: int | None = REVIEW_GATED_MAX_SESSIONS_PER_DAY
    min_minutes_between_sessions: int | None = REVIEW_GATED_MIN_MINUTES_BETWEEN_SESSIONS
    max_daily_size_total: int | None = REVIEW_GATED_MAX_DAILY_SIZE_TOTAL
    git_clean: bool | None = None
    tests_passed: bool | None = None
    ruff_passed: bool | None = None
    secret_scan_passed: bool | None = None
    raw_response_saved: bool | None = None
    raw_response_displayed: bool | None = None
    market_window_allowed: bool | None = None
    maintenance_active: bool | None = None
    important_event_window_ok: bool | None = None


@dataclass(frozen=True)
class ReviewGatedSessionPolicyDecision:
    decision_id: str
    review_id: str
    candidate_id: str
    status: ReviewGatedSessionPolicyStatus
    policy_passed: bool
    eligible_for_review_session: bool
    allowed_for_live: bool
    requires_human_approval: bool
    approval_gate_required: bool
    dry_run_only: bool
    session_size: int
    max_sessions_per_day: int
    min_minutes_between_sessions: int
    max_daily_size_total: int
    blocked_reasons: tuple[str, ...]
    reason_summary: str
    recommended_next_step: str

    def __post_init__(self) -> None:
        _validate_decision(self)


def evaluate_review_gated_session_policy(
    *,
    review_report: LiveOrderCandidateReviewReport | None,
    snapshot: ReviewGatedSessionPolicySnapshot,
) -> ReviewGatedSessionPolicyDecision:
    """Evaluate sanitized session policy inputs without allowing live execution."""
    reasons: list[ReviewGatedSessionPolicyBlockReason] = []

    _evaluate_review_report(review_report, reasons)
    _evaluate_snapshot(snapshot, reasons)

    blocked_reasons = tuple(reason.value for reason in reasons)
    passed = not blocked_reasons
    status = (
        ReviewGatedSessionPolicyStatus.POLICY_PASSED_FOR_REVIEW
        if passed
        else ReviewGatedSessionPolicyStatus.BLOCKED
    )
    recommended_next_step = (
        "proceed_to_review_gated_session_design_no_post"
        if passed
        else "fix_session_policy_inputs_no_post"
    )
    reason_summary = (
        "session policy passed for review session candidate only; live post remains disallowed"
        if passed
        else "blocked: " + ", ".join(blocked_reasons)
    )
    review_id = _review_id(review_report)
    candidate_id = _candidate_id(review_report)
    session_size = _safe_positive_int(snapshot.session_size, REVIEW_GATED_SESSION_SIZE)
    max_sessions_per_day = _safe_positive_int(
        snapshot.max_sessions_per_day,
        REVIEW_GATED_MAX_SESSIONS_PER_DAY,
    )
    min_minutes_between_sessions = _safe_positive_int(
        snapshot.min_minutes_between_sessions,
        REVIEW_GATED_MIN_MINUTES_BETWEEN_SESSIONS,
    )
    max_daily_size_total = _safe_positive_int(
        snapshot.max_daily_size_total,
        REVIEW_GATED_MAX_DAILY_SIZE_TOTAL,
    )

    snapshot_id = snapshot.snapshot_id if isinstance(
        snapshot,
        ReviewGatedSessionPolicySnapshot,
    ) else None
    snapshot_created_at = snapshot.created_at if isinstance(
        snapshot,
        ReviewGatedSessionPolicySnapshot,
    ) else None

    return ReviewGatedSessionPolicyDecision(
        decision_id=make_review_gated_session_policy_decision_id(
            review_id=review_id,
            candidate_id=candidate_id,
            snapshot_id=snapshot_id,
            created_at=snapshot_created_at,
            blocked_reasons=blocked_reasons,
        ),
        review_id=review_id,
        candidate_id=candidate_id,
        status=status,
        policy_passed=passed,
        eligible_for_review_session=passed,
        allowed_for_live=False,
        requires_human_approval=True,
        approval_gate_required=True,
        dry_run_only=True,
        session_size=session_size,
        max_sessions_per_day=max_sessions_per_day,
        min_minutes_between_sessions=min_minutes_between_sessions,
        max_daily_size_total=max_daily_size_total,
        blocked_reasons=blocked_reasons,
        reason_summary=reason_summary,
        recommended_next_step=recommended_next_step,
    )


def make_review_gated_session_policy_decision_id(
    *,
    review_id: str,
    candidate_id: str,
    snapshot_id: str | None,
    created_at: datetime | None,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": _safe_text(candidate_id, "missing_candidate_id"),
        "created_at": _datetime_to_text(created_at),
        "review_id": _safe_text(review_id, "missing_review_id"),
        "snapshot_id": _safe_text(snapshot_id, "missing_snapshot_id"),
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{REVIEW_GATED_SESSION_POLICY_DECISION_ID_PREFIX}{digest.upper()}"


def _evaluate_review_report(
    review_report: LiveOrderCandidateReviewReport | None,
    reasons: list[ReviewGatedSessionPolicyBlockReason],
) -> None:
    if not isinstance(review_report, LiveOrderCandidateReviewReport):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.INVALID_REVIEW_STATUS)
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
        return

    if review_report.review_status is not LiveOrderCandidateReviewStatus.READY_FOR_HUMAN_REVIEW:
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.INVALID_REVIEW_STATUS)
    if review_report.allowed_for_live is not False:
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.REVIEW_ALREADY_ALLOWED_FOR_LIVE)
    if review_report.dry_run_only is not True:
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.REVIEW_NOT_DRY_RUN)
    if review_report.requires_human_approval is not True:
        _add_reason(
            reasons,
            ReviewGatedSessionPolicyBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        )
    if review_report.approval_gate_required is not True:
        _add_reason(
            reasons,
            ReviewGatedSessionPolicyBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        )
    if review_report.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.UNSUPPORTED_SYMBOL)
    if review_report.side not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.UNSUPPORTED_SIDE)
    if review_report.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.UNSUPPORTED_SIZE)
    if review_report.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.UNSUPPORTED_EXECUTION_TYPE)


def _evaluate_snapshot(
    snapshot: ReviewGatedSessionPolicySnapshot,
    reasons: list[ReviewGatedSessionPolicyBlockReason],
) -> None:
    if not isinstance(snapshot, ReviewGatedSessionPolicySnapshot):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
        return

    _evaluate_identity(snapshot, reasons)
    _evaluate_initial_state(snapshot, reasons)
    _evaluate_account_state(snapshot, reasons)
    _evaluate_session_limits(snapshot, reasons)
    _evaluate_repo_safety(snapshot, reasons)
    _evaluate_market_safety(snapshot, reasons)


def _evaluate_identity(
    snapshot: ReviewGatedSessionPolicySnapshot,
    reasons: list[ReviewGatedSessionPolicyBlockReason],
) -> None:
    if not _has_text(snapshot.snapshot_id):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
    if not _valid_datetime(snapshot.created_at):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.INVALID_SESSION_INPUT)
    if not _has_text(snapshot.policy_date):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)


def _evaluate_initial_state(
    snapshot: ReviewGatedSessionPolicySnapshot,
    reasons: list[ReviewGatedSessionPolicyBlockReason],
) -> None:
    if _missing_bool(snapshot.initial_micro_live_completed):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
    elif snapshot.initial_micro_live_completed is not True:
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.INITIAL_MICRO_LIVE_NOT_COMPLETED)

    if _missing_bool(snapshot.previous_order_result_confirmed):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
    elif snapshot.previous_order_result_confirmed is not True:
        _add_reason(
            reasons,
            ReviewGatedSessionPolicyBlockReason.PREVIOUS_ORDER_RESULT_NOT_CONFIRMED,
        )

    if _missing_bool(snapshot.previous_result_unknown):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
    elif snapshot.previous_result_unknown is not False:
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.PREVIOUS_RESULT_UNKNOWN_STATE)


def _evaluate_account_state(
    snapshot: ReviewGatedSessionPolicySnapshot,
    reasons: list[ReviewGatedSessionPolicyBlockReason],
) -> None:
    _evaluate_count(
        reasons,
        value=snapshot.open_positions_count,
        positive_reason=ReviewGatedSessionPolicyBlockReason.OPEN_POSITION_EXISTS,
    )
    _evaluate_count(
        reasons,
        value=snapshot.active_orders_count,
        positive_reason=ReviewGatedSessionPolicyBlockReason.ACTIVE_ORDER_EXISTS,
    )


def _evaluate_session_limits(
    snapshot: ReviewGatedSessionPolicySnapshot,
    reasons: list[ReviewGatedSessionPolicyBlockReason],
) -> None:
    if not _valid_int(snapshot.max_sessions_per_day) or not _valid_int(
        snapshot.min_minutes_between_sessions
    ) or not _valid_int(snapshot.max_daily_size_total):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.INVALID_SESSION_INPUT)
        return
    if (
        snapshot.max_sessions_per_day != REVIEW_GATED_MAX_SESSIONS_PER_DAY
        or snapshot.min_minutes_between_sessions
        != REVIEW_GATED_MIN_MINUTES_BETWEEN_SESSIONS
        or snapshot.max_daily_size_total != REVIEW_GATED_MAX_DAILY_SIZE_TOTAL
    ):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.INVALID_SESSION_INPUT)

    if not _valid_int(snapshot.session_count_today):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
        return
    if not _valid_int(snapshot.daily_live_size_total):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
        return
    if not _valid_int(snapshot.session_size):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
        return

    if snapshot.session_count_today >= REVIEW_GATED_MAX_SESSIONS_PER_DAY:
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MAX_SESSIONS_PER_DAY_REACHED)
    if snapshot.session_size != REVIEW_GATED_SESSION_SIZE:
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.UNSUPPORTED_SESSION_SIZE)
    if (
        snapshot.daily_live_size_total + snapshot.session_size
        > REVIEW_GATED_MAX_DAILY_SIZE_TOTAL
    ):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.DAILY_SIZE_LIMIT_EXCEEDED)
    if snapshot.session_count_today > 0:
        if not _valid_int(snapshot.minutes_since_last_session):
            _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
        elif snapshot.minutes_since_last_session < REVIEW_GATED_MIN_MINUTES_BETWEEN_SESSIONS:
            _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.SESSION_INTERVAL_TOO_SHORT)


def _evaluate_repo_safety(
    snapshot: ReviewGatedSessionPolicySnapshot,
    reasons: list[ReviewGatedSessionPolicyBlockReason],
) -> None:
    _expect_true(
        reasons,
        value=snapshot.git_clean,
        false_reason=ReviewGatedSessionPolicyBlockReason.GIT_NOT_CLEAN,
    )
    _expect_true(
        reasons,
        value=snapshot.tests_passed,
        false_reason=ReviewGatedSessionPolicyBlockReason.TESTS_NOT_PASSED,
    )
    _expect_true(
        reasons,
        value=snapshot.ruff_passed,
        false_reason=ReviewGatedSessionPolicyBlockReason.RUFF_NOT_PASSED,
    )
    _expect_true(
        reasons,
        value=snapshot.secret_scan_passed,
        false_reason=ReviewGatedSessionPolicyBlockReason.SECRET_SCAN_NOT_PASSED,
    )
    _expect_false(
        reasons,
        value=snapshot.raw_response_saved,
        true_reason=ReviewGatedSessionPolicyBlockReason.RAW_RESPONSE_SAVED,
    )
    _expect_false(
        reasons,
        value=snapshot.raw_response_displayed,
        true_reason=ReviewGatedSessionPolicyBlockReason.RAW_RESPONSE_DISPLAYED,
    )


def _evaluate_market_safety(
    snapshot: ReviewGatedSessionPolicySnapshot,
    reasons: list[ReviewGatedSessionPolicyBlockReason],
) -> None:
    _expect_true(
        reasons,
        value=snapshot.market_window_allowed,
        false_reason=ReviewGatedSessionPolicyBlockReason.MARKET_WINDOW_NOT_ALLOWED,
    )
    _expect_false(
        reasons,
        value=snapshot.maintenance_active,
        true_reason=ReviewGatedSessionPolicyBlockReason.MAINTENANCE_ACTIVE,
    )
    _expect_true(
        reasons,
        value=snapshot.important_event_window_ok,
        false_reason=ReviewGatedSessionPolicyBlockReason.IMPORTANT_EVENT_WINDOW_NOT_CONFIRMED,
    )


def _evaluate_count(
    reasons: list[ReviewGatedSessionPolicyBlockReason],
    *,
    value: int | None,
    positive_reason: ReviewGatedSessionPolicyBlockReason,
) -> None:
    if not _valid_int(value):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
    elif value > 0:
        _add_reason(reasons, positive_reason)


def _expect_true(
    reasons: list[ReviewGatedSessionPolicyBlockReason],
    *,
    value: bool | None,
    false_reason: ReviewGatedSessionPolicyBlockReason,
) -> None:
    if _missing_bool(value):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
    elif value is not True:
        _add_reason(reasons, false_reason)


def _expect_false(
    reasons: list[ReviewGatedSessionPolicyBlockReason],
    *,
    value: bool | None,
    true_reason: ReviewGatedSessionPolicyBlockReason,
) -> None:
    if _missing_bool(value):
        _add_reason(reasons, ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT)
    elif value is not False:
        _add_reason(reasons, true_reason)


def _validate_decision(decision: ReviewGatedSessionPolicyDecision) -> None:
    _require_non_empty("decision_id", decision.decision_id)
    if not decision.decision_id.startswith(REVIEW_GATED_SESSION_POLICY_DECISION_ID_PREFIX):
        raise LiveVerificationValidationError("decision_id must be dry-run policy id")
    _require_non_empty("review_id", decision.review_id)
    _require_non_empty("candidate_id", decision.candidate_id)
    if decision.status not in set(ReviewGatedSessionPolicyStatus):
        raise LiveVerificationValidationError("unsupported policy status")
    if type(decision.policy_passed) is not bool:
        raise LiveVerificationValidationError("policy_passed must be bool")
    if type(decision.eligible_for_review_session) is not bool:
        raise LiveVerificationValidationError("eligible_for_review_session must be bool")
    if decision.allowed_for_live is not False:
        raise LiveVerificationValidationError("Step 5F never allows live execution")
    if decision.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if decision.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if decision.dry_run_only is not True:
        raise LiveVerificationValidationError("session policy must be dry-run only")
    for field_name, value in (
        ("session_size", decision.session_size),
        ("max_sessions_per_day", decision.max_sessions_per_day),
        ("min_minutes_between_sessions", decision.min_minutes_between_sessions),
        ("max_daily_size_total", decision.max_daily_size_total),
    ):
        if not _valid_int(value):
            raise LiveVerificationValidationError(f"{field_name} must be a positive int")
    if decision.status is ReviewGatedSessionPolicyStatus.POLICY_PASSED_FOR_REVIEW:
        if not decision.policy_passed or not decision.eligible_for_review_session:
            raise LiveVerificationValidationError("passed policy must be eligible")
        if decision.blocked_reasons:
            raise LiveVerificationValidationError("passed policy cannot have blocked reasons")
    else:
        if decision.policy_passed or decision.eligible_for_review_session:
            raise LiveVerificationValidationError("blocked policy cannot pass")
        if not decision.blocked_reasons:
            raise LiveVerificationValidationError("blocked policy requires blocked reasons")
    _require_non_empty("reason_summary", decision.reason_summary)
    _require_non_empty("recommended_next_step", decision.recommended_next_step)


def _add_reason(
    reasons: list[ReviewGatedSessionPolicyBlockReason],
    reason: ReviewGatedSessionPolicyBlockReason,
) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _candidate_id(review_report: LiveOrderCandidateReviewReport | None) -> str:
    if isinstance(review_report, LiveOrderCandidateReviewReport) and _has_text(
        review_report.candidate_id
    ):
        return review_report.candidate_id
    return "missing_candidate_id"


def _datetime_to_text(value: datetime | None) -> str:
    if _valid_datetime(value):
        return value.astimezone(UTC).isoformat()
    return "missing_created_at"


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _missing_bool(value: object) -> bool:
    return type(value) is not bool


def _review_id(review_report: LiveOrderCandidateReviewReport | None) -> str:
    if isinstance(review_report, LiveOrderCandidateReviewReport) and _has_text(
        review_report.review_id
    ):
        return review_report.review_id
    return "missing_review_id"


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")


def _safe_positive_int(value: int | None, fallback: int) -> int:
    return value if _valid_int(value) else fallback


def _safe_text(value: str | None, fallback: str) -> str:
    return value.strip() if _has_text(value) else fallback


def _valid_datetime(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None


def _valid_int(value: object) -> bool:
    return type(value) is int and value >= 0
