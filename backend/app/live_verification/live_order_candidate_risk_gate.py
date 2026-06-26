"""Fail-closed risk gate for Step 5C live-order candidates."""

from __future__ import annotations

import hashlib
import json
import math
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
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_CANDIDATE_RISK_DECISION_ID_PREFIX = "LOCRISK-"
LIVE_ORDER_CANDIDATE_MAX_SPREAD_JPY = 0.01
LIVE_ORDER_CANDIDATE_MAX_TICKER_AGE_SECONDS = 5.0


class LiveOrderCandidateRiskStatus(str, Enum):
    PASSED_FOR_HUMAN_REVIEW = "PASSED_FOR_HUMAN_REVIEW"
    BLOCKED = "BLOCKED"


class LiveOrderCandidateRiskBlockReason(str, Enum):
    INVALID_CANDIDATE_STATUS = "invalid_candidate_status"
    CANDIDATE_ALREADY_ALLOWED_FOR_LIVE = "candidate_already_allowed_for_live"
    CANDIDATE_NOT_DRY_RUN = "candidate_not_dry_run"
    MISSING_HUMAN_APPROVAL_REQUIREMENT = "missing_human_approval_requirement"
    MISSING_RISK_GATE_REQUIREMENT = "missing_risk_gate_requirement"
    MISSING_APPROVAL_GATE_REQUIREMENT = "missing_approval_gate_requirement"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    ACCOUNT_ASSETS_UNAVAILABLE = "account_assets_unavailable"
    OPEN_POSITION_EXISTS = "open_position_exists"
    ACTIVE_ORDER_EXISTS = "active_order_exists"
    MISSING_SYMBOL_RULES = "missing_symbol_rules"
    MIN_ORDER_SIZE_TOO_LARGE = "min_order_size_too_large"
    SIZE_STEP_MISMATCH = "size_step_mismatch"
    MISSING_SPREAD = "missing_spread"
    SPREAD_TOO_WIDE = "spread_too_wide"
    MISSING_TICKER_AGE = "missing_ticker_age"
    TICKER_TOO_OLD = "ticker_too_old"
    MARKET_WINDOW_NOT_ALLOWED = "market_window_not_allowed"
    MAINTENANCE_ACTIVE = "maintenance_active"
    IMPORTANT_EVENT_WINDOW_NOT_CONFIRMED = "important_event_window_not_confirmed"
    LEDGER_ALREADY_USED = "ledger_already_used"
    DAILY_ATTEMPT_EXISTS = "daily_attempt_exists"
    SESSION_ATTEMPT_EXISTS = "session_attempt_exists"
    RESULT_UNKNOWN_STATE = "result_unknown_state"
    GIT_NOT_CLEAN = "git_not_clean"
    TESTS_NOT_PASSED = "tests_not_passed"
    RUFF_NOT_PASSED = "ruff_not_passed"
    SECRET_SCAN_NOT_PASSED = "secret_scan_not_passed"
    RAW_RESPONSE_SAVED = "raw_response_saved"
    RAW_RESPONSE_DISPLAYED = "raw_response_displayed"
    MISSING_REQUIRED_RISK_INPUT = "missing_required_risk_input"
    INVALID_RISK_INPUT = "invalid_risk_input"


@dataclass(frozen=True)
class LiveOrderCandidateRiskSnapshot:
    snapshot_id: str | None
    created_at: datetime | None
    account_assets_success: bool | None
    open_positions_count: int | None
    active_orders_count: int | None
    symbol_min_open_order_size: int | None
    symbol_size_step: int | None
    spread_jpy: float | None
    ticker_age_seconds: float | None
    market_window_allowed: bool | None
    maintenance_active: bool | None
    important_event_window_ok: bool | None
    ledger_unused: bool | None
    daily_live_attempt_count: int | None
    session_live_attempt_count: int | None
    result_unknown: bool | None
    git_clean: bool | None
    tests_passed: bool | None
    ruff_passed: bool | None
    secret_scan_passed: bool | None
    raw_response_saved: bool | None
    raw_response_displayed: bool | None


@dataclass(frozen=True)
class LiveOrderCandidateRiskDecision:
    decision_id: str
    candidate_id: str
    status: LiveOrderCandidateRiskStatus
    risk_gate_passed: bool
    eligible_for_human_review: bool
    allowed_for_live: bool
    requires_human_approval: bool
    approval_gate_required: bool
    dry_run_only: bool
    blocked_reasons: tuple[str, ...]
    reason_summary: str
    recommended_next_step: str

    def __post_init__(self) -> None:
        _validate_decision(self)


def evaluate_live_order_candidate_risk_gate(
    *,
    candidate: LiveOrderCandidate | None,
    snapshot: LiveOrderCandidateRiskSnapshot,
) -> LiveOrderCandidateRiskDecision:
    """Evaluate a dry-run candidate for human review eligibility only."""
    reasons: list[LiveOrderCandidateRiskBlockReason] = []
    candidate_id = _candidate_id(candidate)

    _evaluate_candidate(candidate, reasons)
    _evaluate_snapshot(snapshot, candidate, reasons)

    blocked_reasons = tuple(reason.value for reason in reasons)
    passed = not blocked_reasons
    status = (
        LiveOrderCandidateRiskStatus.PASSED_FOR_HUMAN_REVIEW
        if passed
        else LiveOrderCandidateRiskStatus.BLOCKED
    )
    recommended_next_step = (
        "proceed_to_candidate_review_no_post"
        if passed
        else "fix_inputs_or_wait_no_post"
    )
    reason_summary = (
        "risk gate passed for human review candidate only; live post remains disallowed"
        if passed
        else "blocked: " + ", ".join(blocked_reasons)
    )

    return LiveOrderCandidateRiskDecision(
        decision_id=make_live_order_candidate_risk_decision_id(
            candidate_id=candidate_id,
            snapshot_id=snapshot.snapshot_id,
            created_at=snapshot.created_at,
            blocked_reasons=blocked_reasons,
        ),
        candidate_id=candidate_id,
        status=status,
        risk_gate_passed=passed,
        eligible_for_human_review=passed,
        allowed_for_live=False,
        requires_human_approval=True,
        approval_gate_required=True,
        dry_run_only=True,
        blocked_reasons=blocked_reasons,
        reason_summary=reason_summary,
        recommended_next_step=recommended_next_step,
    )


def make_live_order_candidate_risk_decision_id(
    *,
    candidate_id: str,
    snapshot_id: str | None,
    created_at: datetime | None,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_components = {
        "blocked_reasons": list(blocked_reasons),
        "candidate_id": candidate_id,
        "created_at": _datetime_to_text(created_at),
        "snapshot_id": snapshot_id if _has_text(snapshot_id) else "missing_snapshot_id",
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{LIVE_ORDER_CANDIDATE_RISK_DECISION_ID_PREFIX}{digest.upper()}"


def _evaluate_candidate(
    candidate: LiveOrderCandidate | None,
    reasons: list[LiveOrderCandidateRiskBlockReason],
) -> None:
    if not isinstance(candidate, LiveOrderCandidate):
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.INVALID_CANDIDATE_STATUS)
        return

    status_value = _enum_value(candidate.status)
    if status_value not in {"REVIEW_REQUIRED", "CREATED"}:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.INVALID_CANDIDATE_STATUS)
    if candidate.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.CANDIDATE_ALREADY_ALLOWED_FOR_LIVE)
    if candidate.dry_run_only is not True:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.CANDIDATE_NOT_DRY_RUN)
    if candidate.requires_human_approval is not True:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT)
    if candidate.risk_gate_required is not True:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_RISK_GATE_REQUIREMENT)
    if candidate.approval_gate_required is not True:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT)
    if candidate.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.UNSUPPORTED_SYMBOL)
    if _enum_value(candidate.side) not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.UNSUPPORTED_SIDE)
    if candidate.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.UNSUPPORTED_SIZE)
    if candidate.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.UNSUPPORTED_EXECUTION_TYPE)


def _evaluate_snapshot(
    snapshot: LiveOrderCandidateRiskSnapshot,
    candidate: LiveOrderCandidate | None,
    reasons: list[LiveOrderCandidateRiskBlockReason],
) -> None:
    if not isinstance(snapshot, LiveOrderCandidateRiskSnapshot):
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_REQUIRED_RISK_INPUT)
        return

    if not _has_text(snapshot.snapshot_id):
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_REQUIRED_RISK_INPUT)
    if not _valid_datetime(snapshot.created_at):
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.INVALID_RISK_INPUT)

    if snapshot.account_assets_success is not True:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.ACCOUNT_ASSETS_UNAVAILABLE)
    _evaluate_count(
        reasons,
        value=snapshot.open_positions_count,
        positive_reason=LiveOrderCandidateRiskBlockReason.OPEN_POSITION_EXISTS,
    )
    _evaluate_count(
        reasons,
        value=snapshot.active_orders_count,
        positive_reason=LiveOrderCandidateRiskBlockReason.ACTIVE_ORDER_EXISTS,
    )
    _evaluate_symbol_rules(snapshot, candidate, reasons)
    _evaluate_spread_and_ticker(snapshot, reasons)
    _evaluate_market_conditions(snapshot, reasons)
    _evaluate_attempt_state(snapshot, reasons)
    _evaluate_repo_safety(snapshot, reasons)


def _evaluate_count(
    reasons: list[LiveOrderCandidateRiskBlockReason],
    *,
    value: int | None,
    positive_reason: LiveOrderCandidateRiskBlockReason,
) -> None:
    if value is None:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_REQUIRED_RISK_INPUT)
        return
    if not _is_int(value) or value < 0:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.INVALID_RISK_INPUT)
        return
    if value > 0:
        _add_reason(reasons, positive_reason)


def _evaluate_symbol_rules(
    snapshot: LiveOrderCandidateRiskSnapshot,
    candidate: LiveOrderCandidate | None,
    reasons: list[LiveOrderCandidateRiskBlockReason],
) -> None:
    min_size = snapshot.symbol_min_open_order_size
    step = snapshot.symbol_size_step
    if min_size is None or step is None:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_SYMBOL_RULES)
        return
    if not _is_int(min_size) or not _is_int(step) or min_size < 1 or step < 1:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.INVALID_RISK_INPUT)
        return
    if min_size > LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MIN_ORDER_SIZE_TOO_LARGE)
    candidate_size = (
        candidate.size
        if isinstance(candidate, LiveOrderCandidate)
        else LIVE_ORDER_CANDIDATE_SIZE
    )
    if candidate_size % step != 0:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.SIZE_STEP_MISMATCH)


def _evaluate_spread_and_ticker(
    snapshot: LiveOrderCandidateRiskSnapshot,
    reasons: list[LiveOrderCandidateRiskBlockReason],
) -> None:
    if snapshot.spread_jpy is None:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_SPREAD)
    elif not _is_finite_number(snapshot.spread_jpy) or snapshot.spread_jpy < 0:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.INVALID_RISK_INPUT)
    elif snapshot.spread_jpy > LIVE_ORDER_CANDIDATE_MAX_SPREAD_JPY:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.SPREAD_TOO_WIDE)

    if snapshot.ticker_age_seconds is None:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_TICKER_AGE)
    elif not _is_finite_number(snapshot.ticker_age_seconds) or snapshot.ticker_age_seconds < 0:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.INVALID_RISK_INPUT)
    elif snapshot.ticker_age_seconds > LIVE_ORDER_CANDIDATE_MAX_TICKER_AGE_SECONDS:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.TICKER_TOO_OLD)


def _evaluate_market_conditions(
    snapshot: LiveOrderCandidateRiskSnapshot,
    reasons: list[LiveOrderCandidateRiskBlockReason],
) -> None:
    if snapshot.market_window_allowed is not True:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MARKET_WINDOW_NOT_ALLOWED)
    if snapshot.maintenance_active is None:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_REQUIRED_RISK_INPUT)
    elif snapshot.maintenance_active is not False:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MAINTENANCE_ACTIVE)
    if snapshot.important_event_window_ok is not True:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.IMPORTANT_EVENT_WINDOW_NOT_CONFIRMED)


def _evaluate_attempt_state(
    snapshot: LiveOrderCandidateRiskSnapshot,
    reasons: list[LiveOrderCandidateRiskBlockReason],
) -> None:
    if snapshot.ledger_unused is not True:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.LEDGER_ALREADY_USED)
    _evaluate_count(
        reasons,
        value=snapshot.daily_live_attempt_count,
        positive_reason=LiveOrderCandidateRiskBlockReason.DAILY_ATTEMPT_EXISTS,
    )
    _evaluate_count(
        reasons,
        value=snapshot.session_live_attempt_count,
        positive_reason=LiveOrderCandidateRiskBlockReason.SESSION_ATTEMPT_EXISTS,
    )
    if snapshot.result_unknown is None:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_REQUIRED_RISK_INPUT)
    elif snapshot.result_unknown is not False:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.RESULT_UNKNOWN_STATE)


def _evaluate_repo_safety(
    snapshot: LiveOrderCandidateRiskSnapshot,
    reasons: list[LiveOrderCandidateRiskBlockReason],
) -> None:
    for value, reason in (
        (snapshot.git_clean, LiveOrderCandidateRiskBlockReason.GIT_NOT_CLEAN),
        (snapshot.tests_passed, LiveOrderCandidateRiskBlockReason.TESTS_NOT_PASSED),
        (snapshot.ruff_passed, LiveOrderCandidateRiskBlockReason.RUFF_NOT_PASSED),
        (snapshot.secret_scan_passed, LiveOrderCandidateRiskBlockReason.SECRET_SCAN_NOT_PASSED),
    ):
        if value is not True:
            _add_reason(reasons, reason)
    if snapshot.raw_response_saved is None:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_REQUIRED_RISK_INPUT)
    elif snapshot.raw_response_saved is not False:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.RAW_RESPONSE_SAVED)
    if snapshot.raw_response_displayed is None:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.MISSING_REQUIRED_RISK_INPUT)
    elif snapshot.raw_response_displayed is not False:
        _add_reason(reasons, LiveOrderCandidateRiskBlockReason.RAW_RESPONSE_DISPLAYED)


def _validate_decision(decision: LiveOrderCandidateRiskDecision) -> None:
    _require_non_empty("decision_id", decision.decision_id)
    if not decision.decision_id.startswith(LIVE_ORDER_CANDIDATE_RISK_DECISION_ID_PREFIX):
        raise LiveVerificationValidationError("decision_id must be a risk decision id")
    _require_non_empty("candidate_id", decision.candidate_id)
    if decision.status not in set(LiveOrderCandidateRiskStatus):
        raise LiveVerificationValidationError("risk status is not supported")
    if type(decision.risk_gate_passed) is not bool:
        raise LiveVerificationValidationError("risk_gate_passed must be bool")
    if type(decision.eligible_for_human_review) is not bool:
        raise LiveVerificationValidationError("eligible_for_human_review must be bool")
    if decision.allowed_for_live is not False:
        raise LiveVerificationValidationError("Step 5C never allows live execution")
    if decision.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval is required")
    if decision.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate is required")
    if decision.dry_run_only is not True:
        raise LiveVerificationValidationError("risk decision must be dry-run only")
    if decision.status is LiveOrderCandidateRiskStatus.PASSED_FOR_HUMAN_REVIEW:
        if not decision.risk_gate_passed or not decision.eligible_for_human_review:
            raise LiveVerificationValidationError("passed decision must be review eligible")
        if decision.blocked_reasons:
            raise LiveVerificationValidationError("passed decision cannot have blocked reasons")
    else:
        if decision.risk_gate_passed or decision.eligible_for_human_review:
            raise LiveVerificationValidationError("blocked decision cannot pass risk gate")
        if not decision.blocked_reasons:
            raise LiveVerificationValidationError("blocked decision requires blocked reasons")
    _require_non_empty("reason_summary", decision.reason_summary)
    _require_non_empty("recommended_next_step", decision.recommended_next_step)


def _candidate_id(candidate: LiveOrderCandidate | None) -> str:
    if isinstance(candidate, LiveOrderCandidate) and _has_text(candidate.candidate_id):
        return candidate.candidate_id
    return "missing_candidate"


def _add_reason(
    reasons: list[LiveOrderCandidateRiskBlockReason],
    reason: LiveOrderCandidateRiskBlockReason,
) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _enum_value(value: object) -> object:
    return value.value if isinstance(value, Enum) else value


def _datetime_to_text(value: datetime | None) -> str:
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(UTC).isoformat()
    return "invalid_created_at"


def _valid_datetime(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None


def _is_int(value: object) -> bool:
    return type(value) is int


def _is_finite_number(value: object) -> bool:
    return type(value) in {int, float} and math.isfinite(float(value))


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_non_empty(field_name: str, value: str) -> None:
    if not _has_text(value):
        raise LiveVerificationValidationError(f"{field_name} is required")
