"""Dry-run review trace model for Step 5D."""

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
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_CANDIDATE_TRACE_ID_PREFIX = "LOCTRACE-"


class LiveOrderCandidateTraceStatus(str, Enum):
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    BLOCKED_TRACE_RECORDED = "BLOCKED_TRACE_RECORDED"
    BLOCKED = "BLOCKED"


class LiveOrderCandidateTraceBlockReason(str, Enum):
    CANDIDATE_ID_MISMATCH = "candidate_id_mismatch"
    CANDIDATE_ALREADY_ALLOWED_FOR_LIVE = "candidate_already_allowed_for_live"
    RISK_DECISION_ALLOWS_LIVE = "risk_decision_allows_live"
    CANDIDATE_NOT_DRY_RUN = "candidate_not_dry_run"
    RISK_DECISION_NOT_DRY_RUN = "risk_decision_not_dry_run"
    MISSING_HUMAN_APPROVAL_REQUIREMENT = "missing_human_approval_requirement"
    MISSING_APPROVAL_GATE_REQUIREMENT = "missing_approval_gate_requirement"
    MISSING_SOURCE_SIGNAL_ID = "missing_source_signal_id"
    MISSING_PAPER_SHADOW_REFERENCE = "missing_paper_shadow_reference"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"


@dataclass(frozen=True)
class LiveOrderCandidateTraceRecord:
    trace_id: str
    created_at: datetime
    source_signal_id: str
    source_type: str
    strategy_name: str
    paper_trade_ref: str | None
    shadow_run_ref: str | None
    paper_decision_ref: str | None
    shadow_decision_ref: str | None
    review_batch_id: str | None
    candidate_id: str
    risk_decision_id: str
    risk_status: str
    risk_gate_passed: bool
    eligible_for_human_review: bool
    symbol: str
    side: str
    size: int
    execution_type: str
    candidate_status: str
    trace_status: LiveOrderCandidateTraceStatus
    blocked_reasons: tuple[str, ...]
    allowed_for_live: bool
    requires_human_approval: bool
    approval_gate_required: bool
    dry_run_only: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        _validate_trace_record(self)


@dataclass(frozen=True)
class LiveOrderCandidateTraceBuildResult:
    trace_record: LiveOrderCandidateTraceRecord
    trace_id: str
    trace_status: LiveOrderCandidateTraceStatus
    blocked_reasons: tuple[str, ...]
    allowed_for_live: bool
    eligible_for_human_review: bool
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.trace_record.trace_id != self.trace_id:
            raise LiveVerificationValidationError("trace_id mismatch")
        if self.trace_record.trace_status is not self.trace_status:
            raise LiveVerificationValidationError("trace_status mismatch")
        if self.trace_record.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("trace build never allows live execution")
        if self.trace_record.allowed_for_live is not False:
            raise LiveVerificationValidationError("trace record never allows live execution")
        if type(self.eligible_for_human_review) is not bool:
            raise LiveVerificationValidationError("eligible_for_human_review must be bool")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def build_live_order_candidate_trace_record(
    *,
    candidate: LiveOrderCandidate,
    risk_decision: LiveOrderCandidateRiskDecision,
    created_at: datetime | None = None,
    paper_decision_ref: str | None = None,
    shadow_decision_ref: str | None = None,
    review_batch_id: str | None = None,
) -> LiveOrderCandidateTraceBuildResult:
    """Link a candidate and risk decision into a non-executable review trace."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    blocked_reasons = _trace_blocked_reasons(
        candidate=candidate,
        risk_decision=risk_decision,
        paper_decision_ref=paper_decision_ref,
        shadow_decision_ref=shadow_decision_ref,
    )

    risk_blocked = _risk_decision_blocked(risk_decision)
    if blocked_reasons:
        trace_status = LiveOrderCandidateTraceStatus.BLOCKED
        eligible_for_human_review = False
        risk_gate_passed = False
        recommended_next_step = "fix_trace_inputs_no_post"
    elif risk_blocked:
        trace_status = LiveOrderCandidateTraceStatus.BLOCKED_TRACE_RECORDED
        eligible_for_human_review = False
        risk_gate_passed = False
        blocked_reasons = tuple(risk_decision.blocked_reasons)
        recommended_next_step = "fix_risk_inputs_or_wait_no_post"
    else:
        trace_status = LiveOrderCandidateTraceStatus.READY_FOR_REVIEW
        eligible_for_human_review = risk_decision.eligible_for_human_review
        risk_gate_passed = risk_decision.risk_gate_passed
        recommended_next_step = "proceed_to_candidate_review_no_post"

    source_signal_id = (
        candidate.source_signal_id
        if _has_text(candidate.source_signal_id)
        else LiveOrderCandidateTraceBlockReason.MISSING_SOURCE_SIGNAL_ID.value
    )
    trace_id = make_live_order_candidate_trace_id(
        candidate_id=candidate.candidate_id,
        risk_decision_id=risk_decision.decision_id,
        source_signal_id=source_signal_id,
        created_at=created,
        paper_trade_ref=candidate.paper_trade_ref,
        shadow_run_ref=candidate.shadow_run_ref,
        paper_decision_ref=paper_decision_ref,
        shadow_decision_ref=shadow_decision_ref,
        review_batch_id=review_batch_id,
    )
    record = LiveOrderCandidateTraceRecord(
        trace_id=trace_id,
        created_at=created,
        source_signal_id=source_signal_id,
        source_type=_enum_value(candidate.source_type),
        strategy_name=candidate.strategy_name,
        paper_trade_ref=candidate.paper_trade_ref,
        shadow_run_ref=candidate.shadow_run_ref,
        paper_decision_ref=paper_decision_ref,
        shadow_decision_ref=shadow_decision_ref,
        review_batch_id=review_batch_id,
        candidate_id=candidate.candidate_id,
        risk_decision_id=risk_decision.decision_id,
        risk_status=_enum_value(risk_decision.status),
        risk_gate_passed=risk_gate_passed,
        eligible_for_human_review=eligible_for_human_review,
        symbol=candidate.symbol,
        side=_enum_value(candidate.side),
        size=candidate.size,
        execution_type=candidate.execution_type,
        candidate_status=_enum_value(candidate.status),
        trace_status=trace_status,
        blocked_reasons=tuple(blocked_reasons),
        allowed_for_live=False,
        requires_human_approval=True,
        approval_gate_required=True,
        dry_run_only=True,
        recommended_next_step=recommended_next_step,
    )
    return LiveOrderCandidateTraceBuildResult(
        trace_record=record,
        trace_id=record.trace_id,
        trace_status=record.trace_status,
        blocked_reasons=record.blocked_reasons,
        allowed_for_live=False,
        eligible_for_human_review=record.eligible_for_human_review,
        recommended_next_step=record.recommended_next_step,
    )


def make_live_order_candidate_trace_id(
    *,
    candidate_id: str,
    risk_decision_id: str,
    source_signal_id: str,
    created_at: datetime,
    paper_trade_ref: str | None,
    shadow_run_ref: str | None,
    paper_decision_ref: str | None,
    shadow_decision_ref: str | None,
    review_batch_id: str | None,
) -> str:
    _require_non_empty("candidate_id", candidate_id)
    _require_non_empty("risk_decision_id", risk_decision_id)
    _require_non_empty("source_signal_id", source_signal_id)
    created = _ensure_aware(created_at)
    id_components = {
        "candidate_id": candidate_id,
        "created_at": created.isoformat(),
        "paper_decision_ref": _optional_text(paper_decision_ref),
        "paper_trade_ref": _optional_text(paper_trade_ref),
        "review_batch_id": _optional_text(review_batch_id),
        "risk_decision_id": risk_decision_id,
        "shadow_decision_ref": _optional_text(shadow_decision_ref),
        "shadow_run_ref": _optional_text(shadow_run_ref),
        "source_signal_id": source_signal_id,
    }
    digest = hashlib.sha256(
        json.dumps(
            id_components,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    return f"{LIVE_ORDER_CANDIDATE_TRACE_ID_PREFIX}{digest.upper()}"


def _trace_blocked_reasons(
    *,
    candidate: LiveOrderCandidate,
    risk_decision: LiveOrderCandidateRiskDecision,
    paper_decision_ref: str | None,
    shadow_decision_ref: str | None,
) -> tuple[str, ...]:
    reasons: list[LiveOrderCandidateTraceBlockReason] = []

    if candidate.candidate_id != risk_decision.candidate_id:
        _add_reason(reasons, LiveOrderCandidateTraceBlockReason.CANDIDATE_ID_MISMATCH)
    if candidate.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderCandidateTraceBlockReason.CANDIDATE_ALREADY_ALLOWED_FOR_LIVE)
    if risk_decision.allowed_for_live is not False:
        _add_reason(reasons, LiveOrderCandidateTraceBlockReason.RISK_DECISION_ALLOWS_LIVE)
    if candidate.dry_run_only is not True:
        _add_reason(reasons, LiveOrderCandidateTraceBlockReason.CANDIDATE_NOT_DRY_RUN)
    if risk_decision.dry_run_only is not True:
        _add_reason(reasons, LiveOrderCandidateTraceBlockReason.RISK_DECISION_NOT_DRY_RUN)
    if (
        candidate.requires_human_approval is not True
        or risk_decision.requires_human_approval is not True
    ):
        _add_reason(
            reasons,
            LiveOrderCandidateTraceBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        )
    if (
        candidate.approval_gate_required is not True
        or risk_decision.approval_gate_required is not True
    ):
        _add_reason(
            reasons,
            LiveOrderCandidateTraceBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        )
    if not _has_text(candidate.source_signal_id):
        _add_reason(reasons, LiveOrderCandidateTraceBlockReason.MISSING_SOURCE_SIGNAL_ID)
    if not any(
        _has_text(value)
        for value in (
            candidate.paper_trade_ref,
            candidate.shadow_run_ref,
            paper_decision_ref,
            shadow_decision_ref,
        )
    ):
        _add_reason(reasons, LiveOrderCandidateTraceBlockReason.MISSING_PAPER_SHADOW_REFERENCE)
    if candidate.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, LiveOrderCandidateTraceBlockReason.UNSUPPORTED_SYMBOL)
    if _enum_value(candidate.side) not in {
        LiveOrderCandidateSide.BUY.value,
        LiveOrderCandidateSide.SELL.value,
    }:
        _add_reason(reasons, LiveOrderCandidateTraceBlockReason.UNSUPPORTED_SIDE)
    if candidate.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, LiveOrderCandidateTraceBlockReason.UNSUPPORTED_SIZE)
    if candidate.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, LiveOrderCandidateTraceBlockReason.UNSUPPORTED_EXECUTION_TYPE)

    return tuple(reason.value for reason in reasons)


def _risk_decision_blocked(risk_decision: LiveOrderCandidateRiskDecision) -> bool:
    return (
        risk_decision.status is LiveOrderCandidateRiskStatus.BLOCKED
        or risk_decision.risk_gate_passed is not True
        or risk_decision.eligible_for_human_review is not True
        or bool(risk_decision.blocked_reasons)
    )


def _validate_trace_record(record: LiveOrderCandidateTraceRecord) -> None:
    _require_non_empty("trace_id", record.trace_id)
    if not record.trace_id.startswith(LIVE_ORDER_CANDIDATE_TRACE_ID_PREFIX):
        raise LiveVerificationValidationError("trace_id must be dry-run trace id")
    _ensure_aware(record.created_at)
    _require_non_empty("source_signal_id", record.source_signal_id)
    _require_non_empty("source_type", record.source_type)
    _require_non_empty("strategy_name", record.strategy_name)
    _require_non_empty("candidate_id", record.candidate_id)
    _require_non_empty("risk_decision_id", record.risk_decision_id)
    _require_non_empty("risk_status", record.risk_status)
    if type(record.risk_gate_passed) is not bool:
        raise LiveVerificationValidationError("risk_gate_passed must be bool")
    if type(record.eligible_for_human_review) is not bool:
        raise LiveVerificationValidationError("eligible_for_human_review must be bool")
    _require_non_empty("symbol", record.symbol)
    _require_non_empty("side", record.side)
    if type(record.size) is not int:
        raise LiveVerificationValidationError("size must be int")
    _require_non_empty("execution_type", record.execution_type)
    _require_non_empty("candidate_status", record.candidate_status)
    if record.trace_status not in set(LiveOrderCandidateTraceStatus):
        raise LiveVerificationValidationError("trace_status is not supported")
    if record.allowed_for_live is not False:
        raise LiveVerificationValidationError("Step 5D never allows live execution")
    if record.requires_human_approval is not True:
        raise LiveVerificationValidationError("human approval remains required")
    if record.approval_gate_required is not True:
        raise LiveVerificationValidationError("approval gate remains required")
    if record.dry_run_only is not True:
        raise LiveVerificationValidationError("trace record must be dry-run only")
    if record.trace_status is LiveOrderCandidateTraceStatus.READY_FOR_REVIEW:
        if record.blocked_reasons:
            raise LiveVerificationValidationError("ready trace cannot have blocked reasons")
        if not record.risk_gate_passed or not record.eligible_for_human_review:
            raise LiveVerificationValidationError("ready trace must be review eligible")
    else:
        if record.risk_gate_passed or record.eligible_for_human_review:
            raise LiveVerificationValidationError("blocked trace cannot pass review")
        if not record.blocked_reasons:
            raise LiveVerificationValidationError("blocked trace requires blocked reasons")
    _require_non_empty("recommended_next_step", record.recommended_next_step)


def _add_reason(
    reasons: list[LiveOrderCandidateTraceBlockReason],
    reason: LiveOrderCandidateTraceBlockReason,
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
