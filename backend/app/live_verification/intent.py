"""Pure mocked order-intent core for Phase 3C-1."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

from app.live_verification.errors import LiveVerificationIntentError
from app.live_verification.precheck import LIVE_VERIFICATION_MODE, SUPPORTED_SYMBOL, SUPPORTED_UNITS

DEFAULT_INTENT_TTL_SECONDS = 600
ALLOW_STATUSES = frozenset({"ALLOW_SHADOW", "ALLOW"})


class OrderIntentSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class OrderIntent:
    order_intent_id: str
    candidate_id: str
    decision_id: str
    readonly_precheck_id: str
    verification_run_id: str
    symbol: str
    side: OrderIntentSide
    units: int
    mode: str
    manual_confirmation_required: bool
    readonly_precheck_passed: bool
    risk_decision_status: str
    created_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _validate_order_intent(self)


def build_order_intent_from_allowed_decision(
    *,
    candidate_id: str,
    decision_id: str,
    readonly_precheck_id: str,
    verification_run_id: str,
    symbol: str,
    side: str | OrderIntentSide,
    units: int,
    risk_decision_status: str,
    readonly_precheck_passed: bool,
    manual_confirmation_required: bool,
    mode: str = LIVE_VERIFICATION_MODE,
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
    existing_intents: Iterable[OrderIntent] = (),
) -> OrderIntent:
    """Build a validated mocked intent. It is not an executable order request."""
    normalized_side = _normalize_side(side)
    created = _ensure_aware(created_at or datetime.now(UTC), field_name="created_at")
    expires = _ensure_aware(
        expires_at or created + timedelta(seconds=DEFAULT_INTENT_TTL_SECONDS),
        field_name="expires_at",
    )
    assert_single_intent_per_run(existing_intents, verification_run_id=verification_run_id)
    return OrderIntent(
        order_intent_id=make_order_intent_id(
            candidate_id=candidate_id,
            decision_id=decision_id,
            readonly_precheck_id=readonly_precheck_id,
            verification_run_id=verification_run_id,
            symbol=symbol,
            side=normalized_side,
            units=units,
        ),
        candidate_id=candidate_id,
        decision_id=decision_id,
        readonly_precheck_id=readonly_precheck_id,
        verification_run_id=verification_run_id,
        symbol=symbol,
        side=normalized_side,
        units=units,
        mode=mode,
        manual_confirmation_required=manual_confirmation_required,
        readonly_precheck_passed=readonly_precheck_passed,
        risk_decision_status=risk_decision_status,
        created_at=created,
        expires_at=expires,
    )


def assert_single_intent_per_run(
    existing_intents: Iterable[OrderIntent],
    *,
    verification_run_id: str,
) -> None:
    _require_non_empty("verification_run_id", verification_run_id)
    if any(intent.verification_run_id == verification_run_id for intent in existing_intents):
        raise LiveVerificationIntentError("order intent already exists for verification run")


def make_order_intent_id(
    *,
    candidate_id: str,
    decision_id: str,
    readonly_precheck_id: str,
    verification_run_id: str,
    symbol: str,
    side: OrderIntentSide,
    units: int,
) -> str:
    for field_name, value in (
        ("candidate_id", candidate_id),
        ("decision_id", decision_id),
        ("readonly_precheck_id", readonly_precheck_id),
        ("verification_run_id", verification_run_id),
    ):
        _require_non_empty(field_name, value)
    digest = _short_hash({
        "candidate_id": candidate_id,
        "decision_id": decision_id,
        "readonly_precheck_id": readonly_precheck_id,
        "side": side.value,
        "symbol": symbol,
        "units": units,
        "verification_run_id": verification_run_id,
    })
    return f"intent_{verification_run_id}_{digest}"


def _validate_order_intent(intent: OrderIntent) -> None:
    for field_name, value in (
        ("order_intent_id", intent.order_intent_id),
        ("candidate_id", intent.candidate_id),
        ("decision_id", intent.decision_id),
        ("readonly_precheck_id", intent.readonly_precheck_id),
        ("verification_run_id", intent.verification_run_id),
    ):
        _require_non_empty(field_name, value)
    if intent.symbol != SUPPORTED_SYMBOL:
        raise LiveVerificationIntentError("symbol must be USD_JPY")
    if intent.units != SUPPORTED_UNITS:
        raise LiveVerificationIntentError("units must be 100")
    if intent.mode != LIVE_VERIFICATION_MODE:
        raise LiveVerificationIntentError("mode must be live_verification")
    if type(intent.manual_confirmation_required) is not bool:
        raise LiveVerificationIntentError("manual_confirmation_required must be bool")
    if not intent.manual_confirmation_required:
        raise LiveVerificationIntentError("manual confirmation is required")
    if type(intent.readonly_precheck_passed) is not bool:
        raise LiveVerificationIntentError("readonly_precheck_passed must be bool")
    if not intent.readonly_precheck_passed:
        raise LiveVerificationIntentError("read-only precheck must pass")
    if intent.risk_decision_status not in ALLOW_STATUSES:
        raise LiveVerificationIntentError("risk decision must be ALLOW")
    if not isinstance(intent.side, OrderIntentSide):
        raise LiveVerificationIntentError("side must be BUY or SELL")
    created = _ensure_aware(intent.created_at, field_name="created_at")
    expires = _ensure_aware(intent.expires_at, field_name="expires_at")
    if expires <= created:
        raise LiveVerificationIntentError("expires_at must be after created_at")
    expected_id = make_order_intent_id(
        candidate_id=intent.candidate_id,
        decision_id=intent.decision_id,
        readonly_precheck_id=intent.readonly_precheck_id,
        verification_run_id=intent.verification_run_id,
        symbol=intent.symbol,
        side=intent.side,
        units=intent.units,
    )
    if intent.order_intent_id != expected_id:
        raise LiveVerificationIntentError("order_intent_id mismatch")


def _normalize_side(side: str | OrderIntentSide) -> OrderIntentSide:
    if isinstance(side, OrderIntentSide):
        return side
    if isinstance(side, str):
        try:
            return OrderIntentSide(side.strip().upper())
        except ValueError as error:
            raise LiveVerificationIntentError("side must be BUY or SELL") from error
    raise LiveVerificationIntentError("side must be BUY or SELL")


def _ensure_aware(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise LiveVerificationIntentError(f"{field_name} must be timezone-aware datetime")
    return value.astimezone(UTC)


def _short_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationIntentError(f"{field_name} is required")
