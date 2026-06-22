"""Local-only shadow candidate and risk safety layer (Phase 2E-1).

Pure domain logic only: no files, network, database, environment settings, broker,
or order request types.  ALLOW_SHADOW permits only a later virtual calculation.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

SCHEMA_VERSION = "shadow-risk-v1"
POLICY_ID = "shadow-risk-policy-v1"
DEFAULT_STOP_FILE = "shadow_exports/STOP"


class SignalLabel(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Disposition(str, Enum):
    NO_TRADE = "NO_TRADE"
    BLOCKED_BY_RISK = "BLOCKED_BY_RISK"
    CANDIDATE_CREATED = "CANDIDATE_CREATED"
    VIRTUAL_RESULT = "VIRTUAL_RESULT"
    HALTED = "HALTED"


class SupplementalReason(str, Enum):
    INVALID_DATA = "INVALID_DATA"
    MARKET_CLOSED = "MARKET_CLOSED"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    RATE_LIMITED = "RATE_LIMITED"
    API_ERROR = "API_ERROR"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"


class RejectReason(str, Enum):
    INVALID_DATA = "invalid_data"
    MARKET_CLOSED = "market_closed"
    STALE_DATA = "stale_data"
    SPREAD_TOO_WIDE = "spread_too_wide"
    SYNTHETIC_SPREAD_NOT_ALLOWED = "synthetic_spread_not_allowed"
    MAX_CANDIDATES_PER_RUN_EXCEEDED = "max_candidates_per_run_exceeded"
    MAX_DAILY_CANDIDATES_EXCEEDED = "max_daily_candidates_exceeded"
    DUPLICATE_CANDIDATE = "duplicate_candidate"
    COOLDOWN_ACTIVE = "cooldown_active"
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_INTERVAL = "unsupported_interval"
    QUANTITY_OVER_LIMIT = "quantity_over_limit"
    QUANTITY_MODE_NOT_ALLOWED = "quantity_mode_not_allowed"
    MISSING_REQUIRED_FIELDS = "missing_required_fields"
    SAFETY_FLAG_VIOLATION = "safety_flag_violation"
    LOG_WRITE_FAILED = "log_write_failed"
    UNKNOWN_STATE = "unknown_state"


class KillSwitchReason(str, Enum):
    SAFETY_VIOLATION_DETECTED = "safety_violation_detected"
    PRIVATE_API_USED_DETECTED = "private_api_used_detected"
    API_KEY_USED_DETECTED = "api_key_used_detected"
    REAL_ORDER_TRUE_DETECTED = "real_order_true_detected"
    UNEXPECTED_BROKER_CALL_DETECTED = "unexpected_broker_call_detected"
    TOO_MANY_CANDIDATES = "too_many_candidates"
    REPEATED_API_ERRORS = "repeated_api_errors"
    BROKEN_SUMMARY_DETECTED = "broken_summary_detected"
    MANUAL_STOP_FILE_EXISTS = "manual_stop_file_exists"
    LOG_WRITE_FAILED = "log_write_failed"
    POLICY_MISMATCH = "policy_mismatch"
    UNKNOWN_EXCEPTION = "unknown_exception"
    UNKNOWN_STATE = "unknown_state"


class RiskStatus(str, Enum):
    ALLOW_SHADOW = "ALLOW_SHADOW"
    REJECT_SHADOW = "REJECT_SHADOW"


def signal_label_from_side(side: str) -> SignalLabel:
    """Convert the existing buy/sell/flat boundary explicitly into Phase 2E labels."""
    normalized = side.strip().lower()
    if normalized == "buy":
        return SignalLabel.BUY
    if normalized == "sell":
        return SignalLabel.SELL
    if normalized == "flat":
        return SignalLabel.HOLD
    raise ValueError("unsupported signal side")


def _as_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
    else:
        raise ValueError("timestamp must be a timezone-aware ISO string or datetime")
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(UTC)


def canonical_timestamp(value: str | datetime) -> str:
    return _as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_decimal(value: float | Decimal | str) -> str:
    decimal = Decimal(str(value))
    if not decimal.is_finite():
        raise ValueError("numeric value must be finite")
    rendered = format(decimal, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _short_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def make_candidate_id(
    *,
    run_id: str,
    step_index: int,
    symbol: str,
    interval: str,
    side: SignalLabel,
    signal_name: str,
    market_data_timestamp: str | datetime,
    entry_reference_price: float | Decimal | str,
) -> str:
    payload = {
        "entry_reference_price": _canonical_decimal(entry_reference_price),
        "interval": interval,
        "market_data_timestamp": canonical_timestamp(market_data_timestamp),
        "run_id": run_id,
        "side": side.value,
        "signal_name": signal_name,
        "step_index": step_index,
        "symbol": symbol,
    }
    return f"cand_{run_id}_{step_index}_{side.value.lower()}_{_short_hash(payload)}"


def make_decision_id(candidate_id: str, policy_id: str = POLICY_ID) -> str:
    suffix = _short_hash({"candidate_id": candidate_id, "policy_id": policy_id})
    return f"risk_{candidate_id}_{suffix}"


@dataclass(frozen=True)
class RiskPolicy:
    policy_id: str = POLICY_ID
    allowed_symbols: tuple[str, ...] = ("USD_JPY",)
    allowed_intervals: tuple[str, ...] = ("M1",)
    max_candidates_per_run: int = 10
    max_daily_candidates: int = 30
    max_quantity: int = 100
    quantity_mode: str = "fixed"
    max_spread_pips: float = 0.5
    max_data_age_seconds: int = 180
    max_future_skew_seconds: int = 5
    cooldown_seconds: int = 60
    max_consecutive_api_errors: int = 3
    max_log_write_failures: int = 0
    allow_synthetic_zero_spread: bool = False
    allow_private_api: bool = False
    allow_api_key: bool = False
    allow_real_order: bool = False
    allow_broker_call: bool = False


@dataclass(frozen=True)
class KillSwitchState:
    """Sticky run-local state. There is intentionally no reset/deactivate method."""

    active: bool = False
    reasons: tuple[KillSwitchReason, ...] = ()
    activated_at: str | None = None
    safety_snapshot: tuple[tuple[str, bool], ...] = ()
    consecutive_api_errors: int = 0

    def activate(
        self,
        reason: KillSwitchReason,
        *,
        timestamp: str | datetime,
        safety_snapshot: dict[str, bool] | None = None,
    ) -> KillSwitchState:
        if self.active:
            return self
        return KillSwitchState(
            active=True,
            reasons=(reason,),
            activated_at=canonical_timestamp(timestamp),
            safety_snapshot=tuple(sorted((safety_snapshot or {}).items())),
            consecutive_api_errors=self.consecutive_api_errors,
        )

    def record_api_result(
        self,
        *,
        success: bool,
        timestamp: str | datetime,
        policy: RiskPolicy,
    ) -> KillSwitchState:
        """Purely update the consecutive Public-error count; active remains sticky."""
        if self.active:
            return self
        if success:
            return KillSwitchState()
        errors = self.consecutive_api_errors + 1
        pending = KillSwitchState(consecutive_api_errors=errors)
        if errors >= policy.max_consecutive_api_errors:
            return pending.activate(KillSwitchReason.REPEATED_API_ERRORS, timestamp=timestamp)
        return pending


@dataclass(frozen=True)
class OrderCandidate:
    schema_version: str
    candidate_id: str
    run_id: str
    step_index: int
    timestamp: str
    market_data_timestamp: str
    source: str
    symbol: str
    interval: str
    side: SignalLabel
    quantity_mode: str
    quantity: int
    entry_reference_price: float
    spread_pips: float | None
    signal_name: str
    signal_reason: str
    confidence: float
    risk_status: str
    blocked_reason: tuple[RejectReason, ...]
    real_order: bool
    private_api_used: bool
    api_key_used: bool
    created_by: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if self.side not in (SignalLabel.BUY, SignalLabel.SELL):
            raise ValueError("OrderCandidate side must be BUY or SELL")
        if self.real_order or self.private_api_used or self.api_key_used:
            raise ValueError("OrderCandidate safety flags must remain false")


@dataclass(frozen=True)
class RiskContext:
    evaluation_time: datetime
    candidates_in_run: int = 0
    candidates_today: int = 0
    existing_candidate_ids: frozenset[str] = field(default_factory=frozenset)
    last_candidate_timestamp: str | None = None
    market_closed: bool = False
    synthetic_spread: bool = False
    kill_switch: KillSwitchState = field(default_factory=KillSwitchState)


@dataclass(frozen=True)
class RiskDecision:
    schema_version: str
    decision_id: str
    candidate_id: str
    run_id: str
    step_index: int
    timestamp: str
    status: RiskStatus
    reasons: tuple[RejectReason, ...]
    checked_policy_id: str
    real_order: bool = False
    private_api_used: bool = False
    api_key_used: bool = False
    no_order_execution: bool = True
    live_trading_environment_enabled: bool = False
    gmo_order_enabled: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if self.status is RiskStatus.REJECT_SHADOW and not self.reasons:
            raise ValueError("REJECT_SHADOW requires at least one reason")
        if self.status is RiskStatus.ALLOW_SHADOW and self.reasons:
            raise ValueError("ALLOW_SHADOW cannot contain reject reasons")
        if self.real_order or self.private_api_used or self.api_key_used:
            raise ValueError("RiskDecision unsafe flag detected")
        if not self.no_order_execution:
            raise ValueError("RiskDecision.no_order_execution must remain true")
        if self.live_trading_environment_enabled or self.gmo_order_enabled:
            raise ValueError("RiskDecision live/order flags must remain false")


def calculate_spread_pips(*, symbol: str, bid: float, ask: float) -> float:
    if symbol != "USD_JPY":
        raise ValueError("spread conversion is defined only for USD_JPY in Phase 2E-1")
    if not all(math.isfinite(value) and value > 0 for value in (bid, ask)) or ask < bid:
        raise ValueError("bid/ask must be finite, positive, and ask >= bid")
    return (ask - bid) / 0.01


def create_order_candidate(
    *,
    signal_label: SignalLabel,
    run_id: str,
    step_index: int,
    timestamp: str | datetime,
    market_data_timestamp: str | datetime,
    source: str,
    symbol: str,
    interval: str,
    quantity: int,
    bid: float,
    ask: float,
    signal_name: str,
    signal_reason: str,
    confidence: float,
    kill_switch: KillSwitchState | None = None,
) -> OrderCandidate | None:
    """Build a never-sent BUY/SELL candidate; HOLD or a kill state yields no candidate."""
    if signal_label is SignalLabel.HOLD or (kill_switch is not None and kill_switch.active):
        return None
    if signal_label not in (SignalLabel.BUY, SignalLabel.SELL):
        return None
    entry_price = ask if signal_label is SignalLabel.BUY else bid
    candidate_id = make_candidate_id(
        run_id=run_id,
        step_index=step_index,
        symbol=symbol,
        interval=interval,
        side=signal_label,
        signal_name=signal_name,
        market_data_timestamp=market_data_timestamp,
        entry_reference_price=entry_price,
    )
    return OrderCandidate(
        schema_version=SCHEMA_VERSION,
        candidate_id=candidate_id,
        run_id=run_id,
        step_index=step_index,
        timestamp=canonical_timestamp(timestamp),
        market_data_timestamp=canonical_timestamp(market_data_timestamp),
        source=source,
        symbol=symbol,
        interval=interval,
        side=signal_label,
        quantity_mode="fixed",
        quantity=quantity,
        entry_reference_price=entry_price,
        spread_pips=calculate_spread_pips(symbol=symbol, bid=bid, ask=ask),
        signal_name=signal_name,
        signal_reason=signal_reason,
        confidence=confidence,
        risk_status="PENDING",
        blocked_reason=(),
        real_order=False,
        private_api_used=False,
        api_key_used=False,
        created_by="shadow_candidate_factory",
    )


def _decision(
    candidate: Any,
    context: RiskContext,
    policy: RiskPolicy,
    reasons: list[RejectReason],
) -> RiskDecision:
    unique_reasons = tuple(dict.fromkeys(reasons))
    candidate_id = str(getattr(candidate, "candidate_id", "unknown"))
    run_id = str(getattr(candidate, "run_id", "unknown"))
    step_index = getattr(candidate, "step_index", -1)
    if not isinstance(step_index, int):
        step_index = -1
    try:
        timestamp = canonical_timestamp(context.evaluation_time)
    except (TypeError, ValueError):
        timestamp = "1970-01-01T00:00:00.000000Z"
    status = RiskStatus.REJECT_SHADOW if unique_reasons else RiskStatus.ALLOW_SHADOW
    return RiskDecision(
        schema_version=SCHEMA_VERSION,
        decision_id=make_decision_id(candidate_id, policy.policy_id),
        candidate_id=candidate_id,
        run_id=run_id,
        step_index=step_index,
        timestamp=timestamp,
        status=status,
        reasons=unique_reasons,
        checked_policy_id=policy.policy_id,
    )


def evaluate(
    candidate: OrderCandidate | Any,
    context: RiskContext,
    policy: RiskPolicy | None = None,
) -> RiskDecision:
    """Pure fail-closed shadow risk evaluation. It never permits a real order."""
    policy = policy or RiskPolicy()
    reasons: list[RejectReason] = []
    try:
        if not isinstance(candidate, OrderCandidate):
            return _decision(
                candidate,
                context,
                policy,
                [RejectReason.MISSING_REQUIRED_FIELDS, RejectReason.UNKNOWN_STATE],
            )
        required_text = (
            candidate.candidate_id,
            candidate.run_id,
            candidate.timestamp,
            candidate.market_data_timestamp,
            candidate.source,
            candidate.symbol,
            candidate.interval,
            candidate.signal_name,
            candidate.signal_reason,
            candidate.quantity_mode,
            candidate.risk_status,
            candidate.created_by,
        )
        if any(not isinstance(value, str) or not value.strip() for value in required_text):
            reasons.append(RejectReason.MISSING_REQUIRED_FIELDS)
        if candidate.schema_version != SCHEMA_VERSION:
            reasons.append(RejectReason.SAFETY_FLAG_VIOLATION)
        if not isinstance(candidate.step_index, int) or candidate.step_index < 0:
            reasons.append(RejectReason.INVALID_DATA)
        if (
            not math.isfinite(candidate.entry_reference_price)
            or candidate.entry_reference_price <= 0
            or not math.isfinite(candidate.confidence)
            or not 0 <= candidate.confidence <= 1
        ):
            reasons.append(RejectReason.INVALID_DATA)
        canonical_timestamp(candidate.timestamp)
        if candidate.symbol not in policy.allowed_symbols:
            reasons.append(RejectReason.UNSUPPORTED_SYMBOL)
        if candidate.interval not in policy.allowed_intervals:
            reasons.append(RejectReason.UNSUPPORTED_INTERVAL)
        if candidate.quantity_mode != policy.quantity_mode:
            reasons.append(RejectReason.QUANTITY_MODE_NOT_ALLOWED)
        if candidate.risk_status != "PENDING" or candidate.blocked_reason:
            reasons.append(RejectReason.UNKNOWN_STATE)
        if not isinstance(candidate.quantity, int) or candidate.quantity <= 0:
            reasons.append(RejectReason.INVALID_DATA)
        elif candidate.quantity > policy.max_quantity:
            reasons.append(RejectReason.QUANTITY_OVER_LIMIT)
        if candidate.spread_pips is None:
            reasons.append(RejectReason.MISSING_REQUIRED_FIELDS)
        elif not math.isfinite(candidate.spread_pips) or candidate.spread_pips < 0:
            reasons.append(RejectReason.INVALID_DATA)
        elif candidate.spread_pips > policy.max_spread_pips:
            reasons.append(RejectReason.SPREAD_TOO_WIDE)
        if context.synthetic_spread and not policy.allow_synthetic_zero_spread:
            reasons.append(RejectReason.SYNTHETIC_SPREAD_NOT_ALLOWED)
        if context.market_closed:
            reasons.append(RejectReason.MARKET_CLOSED)
        if context.kill_switch.active:
            reasons.append(RejectReason.KILL_SWITCH_ACTIVE)
        if context.candidates_in_run < 0 or context.candidates_today < 0:
            reasons.append(RejectReason.UNKNOWN_STATE)
        if context.candidates_in_run >= policy.max_candidates_per_run:
            reasons.append(RejectReason.MAX_CANDIDATES_PER_RUN_EXCEEDED)
        if context.candidates_today >= policy.max_daily_candidates:
            reasons.append(RejectReason.MAX_DAILY_CANDIDATES_EXCEEDED)
        if candidate.candidate_id in context.existing_candidate_ids:
            reasons.append(RejectReason.DUPLICATE_CANDIDATE)

        evaluation_time = _as_utc(context.evaluation_time)
        market_time = _as_utc(candidate.market_data_timestamp)
        age_seconds = (evaluation_time - market_time).total_seconds()
        if age_seconds > policy.max_data_age_seconds:
            reasons.append(RejectReason.STALE_DATA)
        elif age_seconds < -policy.max_future_skew_seconds:
            reasons.append(RejectReason.INVALID_DATA)
        if context.last_candidate_timestamp is not None:
            last_time = _as_utc(context.last_candidate_timestamp)
            elapsed = (market_time - last_time).total_seconds()
            if elapsed < 0:
                reasons.append(RejectReason.INVALID_DATA)
            elif elapsed < policy.cooldown_seconds:
                reasons.append(RejectReason.COOLDOWN_ACTIVE)

        expected_candidate_id = make_candidate_id(
            run_id=candidate.run_id,
            step_index=candidate.step_index,
            symbol=candidate.symbol,
            interval=candidate.interval,
            side=candidate.side,
            signal_name=candidate.signal_name,
            market_data_timestamp=candidate.market_data_timestamp,
            entry_reference_price=candidate.entry_reference_price,
        )
        if candidate.candidate_id != expected_candidate_id:
            reasons.append(RejectReason.SAFETY_FLAG_VIOLATION)

        unsafe_policy = policy != RiskPolicy()
        unsafe_candidate = (
            candidate.real_order or candidate.private_api_used or candidate.api_key_used
        )
        if unsafe_policy or unsafe_candidate:
            reasons.append(RejectReason.SAFETY_FLAG_VIOLATION)
    except (AttributeError, TypeError, ValueError, OverflowError):
        reasons.append(RejectReason.UNKNOWN_STATE)
    return _decision(candidate, context, policy, reasons)


def can_process_virtual_result(
    kill_switch: KillSwitchState,
    decision: RiskDecision,
) -> bool:
    """True only for an inactive kill switch and an explicit shadow-only allow."""
    return not kill_switch.active and decision.status is RiskStatus.ALLOW_SHADOW
