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
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

SCHEMA_VERSION = "shadow-risk-v1"
MARKET_SNAPSHOT_SCHEMA_VERSION = "market-snapshot-v1"
POLICY_ID = "shadow-risk-policy-v1"
DEFAULT_STOP_FILE = "shadow_exports/STOP"
DEFAULT_MAX_TICKER_AGE_SECONDS = 30
DEFAULT_MAX_TICKER_KLINE_SKEW_SECONDS = 90
USD_JPY_PIP = Decimal("0.01")


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


class SpreadProvenance(str, Enum):
    REAL_PUBLIC_BID_ASK = "REAL_PUBLIC_BID_ASK"
    SYNTHETIC_ZERO = "SYNTHETIC_ZERO"
    CANDLE_DERIVED = "CANDLE_DERIVED"
    UNKNOWN = "UNKNOWN"


class MarketSnapshotValidationError(ValueError):
    """A sanitized public market snapshot could not be trusted for risk evaluation."""

    def __init__(
        self,
        message: str,
        *,
        reason: RejectReason,
        counter_name: str = "ticker_invalid_count",
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.counter_name = counter_name


@dataclass(frozen=True)
class MarketSnapshot:
    """Sanitized local-only public ticker/kline snapshot.

    This DTO intentionally stores only normalized values required for shadow risk. It
    never carries raw responses, headers, account identifiers, broker order ids, or
    credential material.
    """

    schema_version: str
    source: str
    symbol: str
    interval: str
    kline_timestamp: str
    ticker_timestamp: str
    bid: Decimal
    ask: Decimal
    mid: Decimal
    spread_pips: Decimal
    spread_provenance: SpreadProvenance
    private_api_used: bool = False
    api_key_used: bool = False
    raw_response_saved: bool = False
    validation_status: str = "valid"
    reject_reason: RejectReason | None = None

    def __post_init__(self) -> None:
        if self.schema_version != MARKET_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {MARKET_SNAPSHOT_SCHEMA_VERSION}")
        if self.source != "gmo-public":
            raise ValueError("MarketSnapshot source must be gmo-public")
        text_fields = (
            self.symbol,
            self.interval,
            self.kline_timestamp,
            self.ticker_timestamp,
        )
        if any(not isinstance(value, str) or not value.strip() for value in text_fields):
            raise ValueError("MarketSnapshot text fields must be non-empty")
        canonical_timestamp(self.kline_timestamp)
        canonical_timestamp(self.ticker_timestamp)
        if self.spread_provenance is not SpreadProvenance.REAL_PUBLIC_BID_ASK:
            raise ValueError("MarketSnapshot requires REAL_PUBLIC_BID_ASK provenance")
        if self.private_api_used or self.api_key_used or self.raw_response_saved:
            raise ValueError("MarketSnapshot safety flags must stay false")
        for value in (self.bid, self.ask, self.mid, self.spread_pips):
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError("MarketSnapshot numeric values must be finite Decimals")
        if self.bid <= 0 or self.ask <= 0 or self.ask < self.bid:
            raise ValueError("MarketSnapshot bid/ask must be positive and ask >= bid")
        if self.spread_pips < 0:
            raise ValueError("MarketSnapshot spread_pips must be non-negative")
        if self.mid != (self.bid + self.ask) / Decimal("2"):
            raise ValueError("MarketSnapshot mid must equal (bid + ask) / 2")
        if self.spread_pips != (self.ask - self.bid) / USD_JPY_PIP:
            raise ValueError("MarketSnapshot spread_pips mismatch")
        if self.validation_status != "valid" or self.reject_reason is not None:
            raise ValueError("MarketSnapshot represents valid snapshots only")


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


def _parse_finite_decimal(value: float | Decimal | str) -> Decimal:
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("numeric value must be Decimal-compatible") from error
    if not decimal.is_finite():
        raise ValueError("numeric value must be finite")
    return decimal


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


def _is_bool(value: Any) -> bool:
    return type(value) is bool


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _policy_validation_errors(policy: Any) -> list[RejectReason]:
    if not isinstance(policy, RiskPolicy):
        return [RejectReason.UNKNOWN_STATE]

    errors: list[RejectReason] = []
    try:
        if not isinstance(policy.policy_id, str) or policy.policy_id != POLICY_ID:
            errors.append(RejectReason.UNKNOWN_STATE)
        for collection in (policy.allowed_symbols, policy.allowed_intervals):
            if (
                not isinstance(collection, tuple | list | frozenset)
                or not collection
                or any(not isinstance(value, str) or not value.strip() for value in collection)
            ):
                errors.append(RejectReason.UNKNOWN_STATE)
        positive_int_fields = (
            policy.max_candidates_per_run,
            policy.max_daily_candidates,
            policy.max_quantity,
            policy.max_consecutive_api_errors,
        )
        if any(not _is_int(value) or value <= 0 for value in positive_int_fields):
            errors.append(RejectReason.UNKNOWN_STATE)
        non_negative_int_fields = (
            policy.max_data_age_seconds,
            policy.max_future_skew_seconds,
            policy.cooldown_seconds,
        )
        if any(not _is_int(value) or value < 0 for value in non_negative_int_fields):
            errors.append(RejectReason.UNKNOWN_STATE)
        if not _is_int(policy.max_log_write_failures) or policy.max_log_write_failures != 0:
            errors.append(RejectReason.UNKNOWN_STATE)
        if policy.quantity_mode != "fixed":
            errors.append(RejectReason.UNKNOWN_STATE)
        if not _is_finite_number(policy.max_spread_pips) or policy.max_spread_pips < 0:
            errors.append(RejectReason.UNKNOWN_STATE)
        safety_booleans = (
            policy.allow_synthetic_zero_spread,
            policy.allow_private_api,
            policy.allow_api_key,
            policy.allow_real_order,
            policy.allow_broker_call,
        )
        if any(not _is_bool(value) or value for value in safety_booleans):
            errors.append(RejectReason.SAFETY_FLAG_VIOLATION)
    except (AttributeError, TypeError):
        errors.append(RejectReason.UNKNOWN_STATE)
    return list(dict.fromkeys(errors))


def _validate_policy(policy: Any) -> None:
    errors = _policy_validation_errors(policy)
    if errors:
        raise ValueError("invalid RiskPolicy invariant")


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

    def __post_init__(self) -> None:
        _validate_policy(self)


@dataclass(frozen=True)
class KillSwitchState:
    """Sticky run-local state. There is intentionally no reset/deactivate method."""

    active: bool = False
    reasons: tuple[KillSwitchReason, ...] = ()
    activated_at: str | None = None
    safety_snapshot: tuple[tuple[str, bool], ...] = ()
    consecutive_api_errors: int = 0

    def __post_init__(self) -> None:
        if type(self.active) is not bool:
            raise ValueError("KillSwitchState.active must be bool")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(reason, KillSwitchReason) for reason in self.reasons
        ):
            raise ValueError("KillSwitchState.reasons must contain KillSwitchReason values")
        if not isinstance(self.consecutive_api_errors, int) or self.consecutive_api_errors < 0:
            raise ValueError("KillSwitchState.consecutive_api_errors must be non-negative")
        if self.active:
            if not self.reasons or self.activated_at is None:
                raise ValueError("active KillSwitchState requires reasons and activated_at")
            canonical_timestamp(self.activated_at)
        elif self.reasons or self.activated_at is not None or self.safety_snapshot:
            raise ValueError("inactive KillSwitchState cannot hold active-only fields")
        if not isinstance(self.safety_snapshot, tuple):
            raise ValueError("KillSwitchState.safety_snapshot must be a tuple")
        for field_name, value in self.safety_snapshot:
            if not isinstance(field_name, str) or type(value) is not bool:
                raise ValueError("KillSwitchState.safety_snapshot entries must be str/bool pairs")

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
    spread_provenance: SpreadProvenance
    signal_name: str
    signal_reason: str
    confidence: float
    risk_status: str
    blocked_reason: tuple[RejectReason, ...]
    real_order: bool
    private_api_used: bool
    api_key_used: bool
    no_order_execution: bool
    live_trading_environment_enabled: bool
    gmo_order_enabled: bool
    created_by: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if not isinstance(self.side, SignalLabel) or self.side not in (
            SignalLabel.BUY,
            SignalLabel.SELL,
        ):
            raise ValueError("OrderCandidate side must be BUY or SELL")
        if not isinstance(self.spread_provenance, SpreadProvenance):
            raise ValueError("OrderCandidate spread_provenance must be explicit")
        safety_flags = (
            self.real_order,
            self.private_api_used,
            self.api_key_used,
            self.no_order_execution,
            self.live_trading_environment_enabled,
            self.gmo_order_enabled,
        )
        if any(not _is_bool(value) for value in safety_flags):
            raise ValueError("OrderCandidate safety flags must be bool")
        if self.real_order or self.private_api_used or self.api_key_used:
            raise ValueError("OrderCandidate safety flags must remain false")
        if not self.no_order_execution:
            raise ValueError("OrderCandidate.no_order_execution must remain true")
        if self.live_trading_environment_enabled or self.gmo_order_enabled:
            raise ValueError("OrderCandidate live/order flags must remain false")


@dataclass(frozen=True)
class RiskContext:
    evaluation_time: datetime
    spread_provenance: SpreadProvenance = SpreadProvenance.UNKNOWN
    candidates_in_run: int = 0
    candidates_today: int = 0
    existing_candidate_ids: frozenset[str] = field(default_factory=frozenset)
    last_candidate_timestamp: str | None = None
    market_closed: bool = False
    kill_switch: KillSwitchState = field(default_factory=KillSwitchState)

    def __post_init__(self) -> None:
        canonical_timestamp(self.evaluation_time)
        if not isinstance(self.spread_provenance, SpreadProvenance):
            raise ValueError("RiskContext.spread_provenance must be SpreadProvenance")
        if not _is_int(self.candidates_in_run) or self.candidates_in_run < 0:
            raise ValueError("RiskContext.candidates_in_run must be non-negative")
        if not _is_int(self.candidates_today) or self.candidates_today < 0:
            raise ValueError("RiskContext.candidates_today must be non-negative")
        if not isinstance(self.existing_candidate_ids, frozenset) or any(
            not isinstance(candidate_id, str) for candidate_id in self.existing_candidate_ids
        ):
            raise ValueError("RiskContext.existing_candidate_ids must be frozenset[str]")
        if self.last_candidate_timestamp is not None:
            canonical_timestamp(self.last_candidate_timestamp)
        if type(self.market_closed) is not bool:
            raise ValueError("RiskContext.market_closed must be bool")
        if not isinstance(self.kill_switch, KillSwitchState):
            raise ValueError("RiskContext.kill_switch must be KillSwitchState")


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
        if not isinstance(self.status, RiskStatus):
            raise ValueError("RiskDecision.status must be RiskStatus")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(reason, RejectReason) for reason in self.reasons
        ):
            raise ValueError("RiskDecision.reasons must contain RejectReason values")
        if self.status is RiskStatus.REJECT_SHADOW and not self.reasons:
            raise ValueError("REJECT_SHADOW requires at least one reason")
        if self.status is RiskStatus.ALLOW_SHADOW and self.reasons:
            raise ValueError("ALLOW_SHADOW cannot contain reject reasons")
        safety_flags = (
            self.real_order,
            self.private_api_used,
            self.api_key_used,
            self.no_order_execution,
            self.live_trading_environment_enabled,
            self.gmo_order_enabled,
        )
        if any(not _is_bool(value) for value in safety_flags):
            raise ValueError("RiskDecision safety flags must be bool")
        if self.real_order or self.private_api_used or self.api_key_used:
            raise ValueError("RiskDecision unsafe flag detected")
        if not self.no_order_execution:
            raise ValueError("RiskDecision.no_order_execution must remain true")
        if self.live_trading_environment_enabled or self.gmo_order_enabled:
            raise ValueError("RiskDecision live/order flags must remain false")


def create_public_market_snapshot(
    *,
    symbol: str,
    interval: str,
    kline_timestamp: str | datetime,
    ticker_symbol: str,
    ticker_bid: float | Decimal | str,
    ticker_ask: float | Decimal | str,
    ticker_timestamp: str | datetime,
    evaluation_time: str | datetime,
    source: str = "gmo-public",
    max_ticker_age_seconds: int = DEFAULT_MAX_TICKER_AGE_SECONDS,
    max_ticker_kline_skew_seconds: int = DEFAULT_MAX_TICKER_KLINE_SKEW_SECONDS,
    max_future_skew_seconds: int = 5,
    private_api_used: bool = False,
    api_key_used: bool = False,
    raw_response_saved: bool = False,
) -> MarketSnapshot:
    """Validate public ticker bid/ask and return a sanitized risk snapshot.

    Raises MarketSnapshotValidationError when any provenance, timestamp, or numeric
    condition fails. The caller should fail closed and never fall back to Private/auth.
    """
    if source != "gmo-public" or private_api_used or api_key_used or raw_response_saved:
        raise MarketSnapshotValidationError(
            "unsafe public ticker provenance",
            reason=RejectReason.SAFETY_FLAG_VIOLATION,
        )
    if ticker_symbol != symbol:
        raise MarketSnapshotValidationError(
            "ticker symbol mismatch",
            reason=RejectReason.INVALID_DATA,
        )
    if ticker_bid is None or ticker_ask is None or ticker_timestamp in (None, ""):
        raise MarketSnapshotValidationError(
            "missing public ticker bid/ask/timestamp",
            reason=RejectReason.MISSING_REQUIRED_FIELDS,
            counter_name="ticker_missing_count",
        )
    try:
        kline_time = _as_utc(kline_timestamp)
        ticker_time = _as_utc(ticker_timestamp)
        evaluated_at = _as_utc(evaluation_time)
    except (TypeError, ValueError) as error:
        raise MarketSnapshotValidationError(
            "invalid public ticker timestamp",
            reason=RejectReason.INVALID_DATA,
        ) from error
    if not isinstance(max_ticker_age_seconds, int) or max_ticker_age_seconds < 0:
        raise MarketSnapshotValidationError(
            "invalid ticker age policy",
            reason=RejectReason.UNKNOWN_STATE,
        )
    if not isinstance(max_ticker_kline_skew_seconds, int) or max_ticker_kline_skew_seconds < 0:
        raise MarketSnapshotValidationError(
            "invalid ticker/kline skew policy",
            reason=RejectReason.UNKNOWN_STATE,
        )
    if not isinstance(max_future_skew_seconds, int) or max_future_skew_seconds < 0:
        raise MarketSnapshotValidationError(
            "invalid future skew policy",
            reason=RejectReason.UNKNOWN_STATE,
        )
    try:
        bid = _parse_finite_decimal(ticker_bid)
        ask = _parse_finite_decimal(ticker_ask)
    except ValueError as error:
        raise MarketSnapshotValidationError(
            "invalid public ticker bid/ask",
            reason=RejectReason.INVALID_DATA,
        ) from error
    if bid <= 0 or ask <= 0 or ask < bid:
        raise MarketSnapshotValidationError(
            "public ticker bid/ask failed bounds",
            reason=RejectReason.INVALID_DATA,
        )
    age_seconds = (evaluated_at - ticker_time).total_seconds()
    if age_seconds > max_ticker_age_seconds:
        raise MarketSnapshotValidationError(
            "stale public ticker",
            reason=RejectReason.STALE_DATA,
            counter_name="ticker_stale_count",
        )
    if age_seconds < -max_future_skew_seconds:
        raise MarketSnapshotValidationError(
            "future public ticker timestamp",
            reason=RejectReason.INVALID_DATA,
        )
    if abs((ticker_time - kline_time).total_seconds()) > max_ticker_kline_skew_seconds:
        raise MarketSnapshotValidationError(
            "ticker/kline timestamp skew exceeded",
            reason=RejectReason.STALE_DATA,
            counter_name="ticker_kline_skew_reject_count",
        )
    spread_pips = (ask - bid) / USD_JPY_PIP
    if not spread_pips.is_finite() or spread_pips < 0:
        raise MarketSnapshotValidationError(
            "invalid public ticker spread",
            reason=RejectReason.INVALID_DATA,
        )
    return MarketSnapshot(
        schema_version=MARKET_SNAPSHOT_SCHEMA_VERSION,
        source=source,
        symbol=symbol,
        interval=interval,
        kline_timestamp=canonical_timestamp(kline_time),
        ticker_timestamp=canonical_timestamp(ticker_time),
        bid=bid,
        ask=ask,
        mid=(bid + ask) / Decimal("2"),
        spread_pips=spread_pips,
        spread_provenance=SpreadProvenance.REAL_PUBLIC_BID_ASK,
        private_api_used=False,
        api_key_used=False,
        raw_response_saved=False,
    )


def calculate_spread_pips(
    *,
    symbol: str,
    bid: float | Decimal | str,
    ask: float | Decimal | str,
) -> float:
    if symbol != "USD_JPY":
        raise ValueError("spread conversion is defined only for USD_JPY in Phase 2E-1")
    bid_decimal = _parse_finite_decimal(bid)
    ask_decimal = _parse_finite_decimal(ask)
    if bid_decimal <= 0 or ask_decimal <= 0 or ask_decimal < bid_decimal:
        raise ValueError("bid/ask must be finite, positive, and ask >= bid")
    return float((ask_decimal - bid_decimal) / USD_JPY_PIP)


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
    spread_provenance: SpreadProvenance,
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
        spread_provenance=spread_provenance,
        signal_name=signal_name,
        signal_reason=signal_reason,
        confidence=confidence,
        risk_status="PENDING",
        blocked_reason=(),
        real_order=False,
        private_api_used=False,
        api_key_used=False,
        no_order_execution=True,
        live_trading_environment_enabled=False,
        gmo_order_enabled=False,
        created_by="shadow_candidate_factory",
    )


def _decision(
    candidate: Any,
    context: Any,
    policy: Any,
    reasons: list[RejectReason],
) -> RiskDecision:
    unique_reasons = tuple(
        dict.fromkeys(
            reason if isinstance(reason, RejectReason) else RejectReason.UNKNOWN_STATE
            for reason in reasons
        )
    )
    candidate_id_raw = getattr(candidate, "candidate_id", None)
    candidate_id = candidate_id_raw if isinstance(candidate_id_raw, str) else "unknown"
    run_id_raw = getattr(candidate, "run_id", None)
    run_id = run_id_raw if isinstance(run_id_raw, str) else "unknown"
    step_index_raw = getattr(candidate, "step_index", -1)
    step_index = step_index_raw if _is_int(step_index_raw) else -1
    policy_id_raw = getattr(policy, "policy_id", None)
    policy_id = policy_id_raw if isinstance(policy_id_raw, str) else POLICY_ID
    try:
        timestamp = canonical_timestamp(context.evaluation_time)
    except (AttributeError, TypeError, ValueError):
        timestamp = "1970-01-01T00:00:00.000000Z"
    status = RiskStatus.REJECT_SHADOW if unique_reasons else RiskStatus.ALLOW_SHADOW
    try:
        decision_id = make_decision_id(candidate_id, policy_id)
        return RiskDecision(
            schema_version=SCHEMA_VERSION,
            decision_id=decision_id,
            candidate_id=candidate_id,
            run_id=run_id,
            step_index=step_index,
            timestamp=timestamp,
            status=status,
            reasons=unique_reasons,
            checked_policy_id=policy_id,
        )
    except Exception:
        fallback_candidate_id = "unknown"
        fallback_policy_id = POLICY_ID
        return RiskDecision(
            schema_version=SCHEMA_VERSION,
            decision_id=make_decision_id(fallback_candidate_id, fallback_policy_id),
            candidate_id=fallback_candidate_id,
            run_id="unknown",
            step_index=-1,
            timestamp="1970-01-01T00:00:00.000000Z",
            status=RiskStatus.REJECT_SHADOW,
            reasons=(RejectReason.UNKNOWN_STATE,),
            checked_policy_id=fallback_policy_id,
        )


def evaluate(
    candidate: OrderCandidate | Any,
    context: RiskContext | Any,
    policy: RiskPolicy | Any | None = None,
) -> RiskDecision:
    """Pure fail-closed shadow risk evaluation. It never permits a real order."""
    policy = RiskPolicy() if policy is None else policy
    reasons: list[RejectReason] = []
    try:
        policy_errors = _policy_validation_errors(policy)
        if policy_errors:
            return _decision(candidate, context, policy, policy_errors)
        if not isinstance(context, RiskContext):
            return _decision(candidate, context, policy, [RejectReason.UNKNOWN_STATE])
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
        if not isinstance(candidate.side, SignalLabel):
            reasons.append(RejectReason.UNKNOWN_STATE)
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
        provenances = (candidate.spread_provenance, context.spread_provenance)
        if any(not isinstance(value, SpreadProvenance) for value in provenances):
            reasons.append(RejectReason.UNKNOWN_STATE)
        elif any(
            value in (SpreadProvenance.SYNTHETIC_ZERO, SpreadProvenance.CANDLE_DERIVED)
            for value in provenances
        ):
            reasons.append(RejectReason.SYNTHETIC_SPREAD_NOT_ALLOWED)
        elif SpreadProvenance.UNKNOWN in provenances:
            reasons.append(RejectReason.INVALID_DATA)
        elif any(value is not SpreadProvenance.REAL_PUBLIC_BID_ASK for value in provenances):
            reasons.append(RejectReason.UNKNOWN_STATE)
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

        unsafe_candidate = (
            candidate.real_order
            or candidate.private_api_used
            or candidate.api_key_used
            or not candidate.no_order_execution
            or candidate.live_trading_environment_enabled
            or candidate.gmo_order_enabled
        )
        if unsafe_candidate:
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
