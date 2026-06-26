"""Dry-run live-order candidate model for Step 5B."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

LIVE_ORDER_CANDIDATE_ID_PREFIX = "LOCAND-"
LIVE_ORDER_CANDIDATE_EXECUTION_TYPE = "MARKET"
LIVE_ORDER_CANDIDATE_TTL_SECONDS = 600
LIVE_ORDER_CANDIDATE_SIZE = SUPPORTED_UNITS


class LiveOrderCandidateSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"


class LiveOrderCandidateSourceType(str, Enum):
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"
    PAPER = "PAPER"
    SHADOW = "SHADOW"


class LiveOrderCandidateStatus(str, Enum):
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class LiveOrderCandidateBlockedReason(str, Enum):
    NO_TRADE_SIGNAL = "no_trade_signal"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SOURCE_TYPE = "unsupported_source_type"
    INVALID_CONFIDENCE = "invalid_confidence"
    MISSING_RATIONALE = "missing_rationale"
    MISSING_SOURCE_SIGNAL_ID = "missing_source_signal_id"
    MISSING_STRATEGY_NAME = "missing_strategy_name"
    INVALID_TIME_WINDOW = "invalid_time_window"


@dataclass(frozen=True)
class StrategySignalInput:
    source_signal_id: str
    source_type: str | LiveOrderCandidateSourceType
    strategy_name: str
    symbol: str
    side: str | LiveOrderCandidateSide
    confidence: float
    rationale: str
    created_at: datetime
    expires_at: datetime | None = None
    market_snapshot_ref: str | None = None
    paper_trade_ref: str | None = None
    shadow_run_ref: str | None = None


@dataclass(frozen=True)
class LiveOrderCandidate:
    candidate_id: str
    created_at: datetime
    expires_at: datetime
    source_signal_id: str
    source_type: LiveOrderCandidateSourceType
    strategy_name: str
    symbol: str
    side: LiveOrderCandidateSide
    size: int
    execution_type: str
    rationale: str
    confidence: float
    market_snapshot_ref: str | None
    paper_trade_ref: str | None
    shadow_run_ref: str | None
    requires_human_approval: bool
    allowed_for_live: bool
    dry_run_only: bool
    status: LiveOrderCandidateStatus
    blocked_reason: str | None
    risk_gate_required: bool
    approval_gate_required: bool

    def __post_init__(self) -> None:
        _validate_live_order_candidate(self)


@dataclass(frozen=True)
class LiveOrderCandidateBuildResult:
    candidate: LiveOrderCandidate | None
    candidate_id: str | None
    source_signal_id: str
    status: LiveOrderCandidateStatus
    blocked_reason: str | None
    allowed_for_live: bool
    requires_human_approval: bool
    risk_gate_required: bool
    approval_gate_required: bool
    dry_run_only: bool

    def __post_init__(self) -> None:
        _validate_build_result(self)


def build_live_order_candidate_dry_run(
    signal: StrategySignalInput,
) -> LiveOrderCandidateBuildResult:
    """Build a non-executable review candidate from a sanitized strategy signal."""
    created = _ensure_aware(signal.created_at)
    expires = _ensure_expires(signal.expires_at, created)
    source_type = _normalize_source_type(signal.source_type)
    side = _normalize_side(signal.side)
    blocked_reason = _blocked_reason(signal=signal, source_type=source_type, side=side)

    if blocked_reason is not None:
        return _blocked_result(
            source_signal_id=signal.source_signal_id,
            blocked_reason=blocked_reason,
        )

    candidate = LiveOrderCandidate(
        candidate_id=make_live_order_candidate_id(
            source_signal_id=signal.source_signal_id,
            source_type=source_type,
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            side=side,
            confidence=signal.confidence,
            created_at=created,
            expires_at=expires,
        ),
        created_at=created,
        expires_at=expires,
        source_signal_id=signal.source_signal_id,
        source_type=source_type,
        strategy_name=signal.strategy_name,
        symbol=signal.symbol,
        side=side,
        size=LIVE_ORDER_CANDIDATE_SIZE,
        execution_type=LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
        rationale=signal.rationale.strip(),
        confidence=float(signal.confidence),
        market_snapshot_ref=signal.market_snapshot_ref,
        paper_trade_ref=signal.paper_trade_ref,
        shadow_run_ref=signal.shadow_run_ref,
        requires_human_approval=True,
        allowed_for_live=False,
        dry_run_only=True,
        status=LiveOrderCandidateStatus.REVIEW_REQUIRED,
        blocked_reason=None,
        risk_gate_required=True,
        approval_gate_required=True,
    )
    return LiveOrderCandidateBuildResult(
        candidate=candidate,
        candidate_id=candidate.candidate_id,
        source_signal_id=candidate.source_signal_id,
        status=candidate.status,
        blocked_reason=None,
        allowed_for_live=False,
        requires_human_approval=True,
        risk_gate_required=True,
        approval_gate_required=True,
        dry_run_only=True,
    )


def make_live_order_candidate_id(
    *,
    source_signal_id: str,
    source_type: LiveOrderCandidateSourceType,
    strategy_name: str,
    symbol: str,
    side: LiveOrderCandidateSide,
    confidence: float,
    created_at: datetime,
    expires_at: datetime,
) -> str:
    for field_name, value in (
        ("source_signal_id", source_signal_id),
        ("strategy_name", strategy_name),
        ("symbol", symbol),
    ):
        _require_non_empty(field_name, value)
    created = _ensure_aware(created_at)
    expires = _ensure_aware(expires_at)
    digest = _short_hash({
        "confidence": float(confidence),
        "created_at": created.isoformat(),
        "expires_at": expires.isoformat(),
        "side": side.value,
        "source_signal_id": source_signal_id,
        "source_type": source_type.value,
        "strategy_name": strategy_name,
        "symbol": symbol,
    }).upper()
    return f"{LIVE_ORDER_CANDIDATE_ID_PREFIX}{digest}"


def _blocked_result(
    *,
    source_signal_id: str,
    blocked_reason: LiveOrderCandidateBlockedReason,
) -> LiveOrderCandidateBuildResult:
    safe_source_signal_id = (
        source_signal_id.strip()
        if _has_text(source_signal_id)
        else LiveOrderCandidateBlockedReason.MISSING_SOURCE_SIGNAL_ID.value
    )
    return LiveOrderCandidateBuildResult(
        candidate=None,
        candidate_id=None,
        source_signal_id=safe_source_signal_id,
        status=LiveOrderCandidateStatus.BLOCKED,
        blocked_reason=blocked_reason.value,
        allowed_for_live=False,
        requires_human_approval=True,
        risk_gate_required=True,
        approval_gate_required=True,
        dry_run_only=True,
    )


def _blocked_reason(
    *,
    signal: StrategySignalInput,
    source_type: LiveOrderCandidateSourceType | None,
    side: LiveOrderCandidateSide | None,
) -> LiveOrderCandidateBlockedReason | None:
    if not _has_text(signal.source_signal_id):
        return LiveOrderCandidateBlockedReason.MISSING_SOURCE_SIGNAL_ID
    if source_type is None:
        return LiveOrderCandidateBlockedReason.UNSUPPORTED_SOURCE_TYPE
    if not _has_text(signal.strategy_name):
        return LiveOrderCandidateBlockedReason.MISSING_STRATEGY_NAME
    if side is None:
        return LiveOrderCandidateBlockedReason.UNSUPPORTED_SIDE
    if side is LiveOrderCandidateSide.NO_TRADE:
        return LiveOrderCandidateBlockedReason.NO_TRADE_SIGNAL
    if signal.symbol != SUPPORTED_SYMBOL:
        return LiveOrderCandidateBlockedReason.UNSUPPORTED_SYMBOL
    if not _valid_confidence(signal.confidence):
        return LiveOrderCandidateBlockedReason.INVALID_CONFIDENCE
    if not _has_text(signal.rationale):
        return LiveOrderCandidateBlockedReason.MISSING_RATIONALE
    try:
        created = _ensure_aware(signal.created_at)
        _ensure_expires(signal.expires_at, created)
    except LiveVerificationValidationError:
        return LiveOrderCandidateBlockedReason.INVALID_TIME_WINDOW
    return None


def _validate_live_order_candidate(candidate: LiveOrderCandidate) -> None:
    _require_non_empty("candidate_id", candidate.candidate_id)
    if not candidate.candidate_id.startswith(LIVE_ORDER_CANDIDATE_ID_PREFIX):
        raise LiveVerificationValidationError("candidate_id must be dry-run candidate id")
    _require_non_empty("source_signal_id", candidate.source_signal_id)
    _require_non_empty("strategy_name", candidate.strategy_name)
    if candidate.source_type not in set(LiveOrderCandidateSourceType):
        raise LiveVerificationValidationError("source_type is not supported")
    if candidate.symbol != SUPPORTED_SYMBOL:
        raise LiveVerificationValidationError("symbol must be USD_JPY")
    if candidate.side not in {LiveOrderCandidateSide.BUY, LiveOrderCandidateSide.SELL}:
        raise LiveVerificationValidationError("review candidate side must be BUY or SELL")
    if candidate.size != LIVE_ORDER_CANDIDATE_SIZE:
        raise LiveVerificationValidationError("candidate size must be 100")
    if candidate.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        raise LiveVerificationValidationError("candidate execution type must be MARKET")
    if not _valid_confidence(candidate.confidence):
        raise LiveVerificationValidationError("confidence must be between 0 and 1")
    if not _has_text(candidate.rationale):
        raise LiveVerificationValidationError("rationale is required")
    _validate_safety_flags(
        allowed_for_live=candidate.allowed_for_live,
        requires_human_approval=candidate.requires_human_approval,
        risk_gate_required=candidate.risk_gate_required,
        approval_gate_required=candidate.approval_gate_required,
        dry_run_only=candidate.dry_run_only,
    )
    if candidate.status is not LiveOrderCandidateStatus.REVIEW_REQUIRED:
        raise LiveVerificationValidationError("candidate status must require review")
    if candidate.blocked_reason is not None:
        raise LiveVerificationValidationError("review candidate cannot have blocked_reason")
    created = _ensure_aware(candidate.created_at)
    expires = _ensure_aware(candidate.expires_at)
    if expires <= created:
        raise LiveVerificationValidationError("expires_at must be after created_at")
    expected_id = make_live_order_candidate_id(
        source_signal_id=candidate.source_signal_id,
        source_type=candidate.source_type,
        strategy_name=candidate.strategy_name,
        symbol=candidate.symbol,
        side=candidate.side,
        confidence=candidate.confidence,
        created_at=created,
        expires_at=expires,
    )
    if candidate.candidate_id != expected_id:
        raise LiveVerificationValidationError("candidate_id mismatch")


def _validate_build_result(result: LiveOrderCandidateBuildResult) -> None:
    _require_non_empty("source_signal_id", result.source_signal_id)
    if result.status not in set(LiveOrderCandidateStatus):
        raise LiveVerificationValidationError("status is not supported")
    _validate_safety_flags(
        allowed_for_live=result.allowed_for_live,
        requires_human_approval=result.requires_human_approval,
        risk_gate_required=result.risk_gate_required,
        approval_gate_required=result.approval_gate_required,
        dry_run_only=result.dry_run_only,
    )
    if result.status is LiveOrderCandidateStatus.BLOCKED:
        if result.candidate is not None or result.candidate_id is not None:
            raise LiveVerificationValidationError("blocked result cannot include candidate")
        _require_non_empty("blocked_reason", result.blocked_reason)
    else:
        if result.candidate is None or result.candidate_id != result.candidate.candidate_id:
            raise LiveVerificationValidationError("review result requires candidate")
        if result.blocked_reason is not None:
            raise LiveVerificationValidationError("review result cannot include blocked_reason")


def _validate_safety_flags(
    *,
    allowed_for_live: bool,
    requires_human_approval: bool,
    risk_gate_required: bool,
    approval_gate_required: bool,
    dry_run_only: bool,
) -> None:
    flags = {
        "allowed_for_live": allowed_for_live,
        "requires_human_approval": requires_human_approval,
        "risk_gate_required": risk_gate_required,
        "approval_gate_required": approval_gate_required,
        "dry_run_only": dry_run_only,
    }
    for name, value in flags.items():
        if type(value) is not bool:
            raise LiveVerificationValidationError(f"{name} must be bool")
    if allowed_for_live:
        raise LiveVerificationValidationError("Step 5B candidates are never allowed for live")
    if not requires_human_approval:
        raise LiveVerificationValidationError("human approval is required")
    if not risk_gate_required:
        raise LiveVerificationValidationError("risk gate is required")
    if not approval_gate_required:
        raise LiveVerificationValidationError("approval gate is required")
    if not dry_run_only:
        raise LiveVerificationValidationError("candidate must be dry-run only")


def _normalize_side(value: str | LiveOrderCandidateSide) -> LiveOrderCandidateSide | None:
    if isinstance(value, LiveOrderCandidateSide):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        if normalized == "HOLD":
            normalized = LiveOrderCandidateSide.NO_TRADE.value
        try:
            return LiveOrderCandidateSide(normalized)
        except ValueError:
            return None
    return None


def _normalize_source_type(
    value: str | LiveOrderCandidateSourceType,
) -> LiveOrderCandidateSourceType | None:
    if isinstance(value, LiveOrderCandidateSourceType):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return LiveOrderCandidateSourceType(normalized)
        except ValueError:
            return None
    return None


def _ensure_expires(value: datetime | None, created_at: datetime) -> datetime:
    if value is None:
        return created_at + timedelta(seconds=LIVE_ORDER_CANDIDATE_TTL_SECONDS)
    expires = _ensure_aware(value)
    if expires <= created_at:
        raise LiveVerificationValidationError("expires_at must be after created_at")
    return expires


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def _valid_confidence(value: float) -> bool:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return math.isfinite(float(value)) and 0.0 <= float(value) <= 1.0


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _short_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _require_non_empty(field_name: str, value: str | None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")
