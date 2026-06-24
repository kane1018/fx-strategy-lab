"""Review-only order review models for Phase 3D-1 live verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from app.live_verification.errors import LiveVerificationOrderReviewError
from app.live_verification.intent import ALLOW_STATUSES, OrderIntent, OrderIntentSide
from app.live_verification.precheck import (
    LIVE_VERIFICATION_MODE,
    SUPPORTED_SYMBOL,
    SUPPORTED_UNITS,
)


@dataclass(frozen=True)
class OrderReview:
    order_review_id: str
    order_intent_id: str
    candidate_id: str
    decision_id: str
    readonly_precheck_id: str
    verification_run_id: str
    symbol: str
    side: OrderIntentSide
    units: int
    mode: str
    risk_decision_status: str
    readonly_precheck_passed: bool
    ready_for_order_review: bool
    manual_confirmation_required: bool
    created_at: datetime
    expires_at: datetime
    review_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_order_review(self)


@dataclass(frozen=True)
class FinalOrderChecklist:
    checklist_id: str
    order_review_id: str
    verification_run_id: str
    git_clean: bool
    tests_passed: bool
    ruff_passed: bool
    secret_scan_passed: bool
    readonly_precheck_passed: bool
    no_open_positions: bool
    no_active_orders: bool
    risk_decision_allow: bool
    ready_for_order_review: bool
    symbol_is_usd_jpy: bool
    units_is_100: bool
    single_intent_for_run: bool
    manual_confirmation_required: bool
    user_explicit_approval: bool
    broker_not_implemented: bool
    order_api_not_implemented: bool
    raw_response_not_saved: bool
    headers_not_saved: bool
    signature_not_saved: bool
    final_checklist_passed: bool
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_final_order_checklist(self)


def build_order_review_from_intent(
    *,
    intent: OrderIntent,
    ready_for_order_review: bool,
    review_notes: tuple[str, ...] = (),
) -> OrderReview:
    """Convert a validated intent into a review-only object."""
    if type(ready_for_order_review) is not bool:
        raise LiveVerificationOrderReviewError("ready_for_order_review must be bool")
    return OrderReview(
        order_review_id=make_order_review_id(
            order_intent_id=intent.order_intent_id,
            verification_run_id=intent.verification_run_id,
        ),
        order_intent_id=intent.order_intent_id,
        candidate_id=intent.candidate_id,
        decision_id=intent.decision_id,
        readonly_precheck_id=intent.readonly_precheck_id,
        verification_run_id=intent.verification_run_id,
        symbol=intent.symbol,
        side=intent.side,
        units=intent.units,
        mode=intent.mode,
        risk_decision_status=intent.risk_decision_status,
        readonly_precheck_passed=intent.readonly_precheck_passed,
        ready_for_order_review=ready_for_order_review,
        manual_confirmation_required=intent.manual_confirmation_required,
        created_at=intent.created_at,
        expires_at=intent.expires_at,
        review_notes=review_notes,
    )


def evaluate_final_order_checklist(
    *,
    order_review: OrderReview,
    git_clean: bool,
    tests_passed: bool,
    ruff_passed: bool,
    secret_scan_passed: bool,
    no_open_positions: bool,
    no_active_orders: bool,
    single_intent_for_run: bool,
    user_explicit_approval: bool,
    broker_not_implemented: bool,
    order_api_not_implemented: bool,
    raw_response_not_saved: bool,
    headers_not_saved: bool,
    signature_not_saved: bool,
    readonly_precheck_passed: bool | None = None,
    risk_decision_allow: bool | None = None,
    ready_for_order_review: bool | None = None,
    symbol_is_usd_jpy: bool | None = None,
    units_is_100: bool | None = None,
    manual_confirmation_required: bool | None = None,
) -> FinalOrderChecklist:
    """Evaluate final human-review prerequisites without crossing the no-order boundary."""
    flags = {
        "git_clean": git_clean,
        "tests_passed": tests_passed,
        "ruff_passed": ruff_passed,
        "secret_scan_passed": secret_scan_passed,
        "readonly_precheck_passed": _default_bool(
            readonly_precheck_passed,
            order_review.readonly_precheck_passed,
        ),
        "no_open_positions": no_open_positions,
        "no_active_orders": no_active_orders,
        "risk_decision_allow": _default_bool(
            risk_decision_allow,
            order_review.risk_decision_status in ALLOW_STATUSES,
        ),
        "ready_for_order_review": _default_bool(
            ready_for_order_review,
            order_review.ready_for_order_review,
        ),
        "symbol_is_usd_jpy": _default_bool(
            symbol_is_usd_jpy,
            order_review.symbol == SUPPORTED_SYMBOL,
        ),
        "units_is_100": _default_bool(units_is_100, order_review.units == SUPPORTED_UNITS),
        "single_intent_for_run": single_intent_for_run,
        "manual_confirmation_required": _default_bool(
            manual_confirmation_required,
            order_review.manual_confirmation_required,
        ),
        "user_explicit_approval": user_explicit_approval,
        "broker_not_implemented": broker_not_implemented,
        "order_api_not_implemented": order_api_not_implemented,
        "raw_response_not_saved": raw_response_not_saved,
        "headers_not_saved": headers_not_saved,
        "signature_not_saved": signature_not_saved,
    }
    _validate_bool_map(flags)
    fail_reasons = tuple(name for name, passed in flags.items() if not passed)
    return FinalOrderChecklist(
        checklist_id=make_final_checklist_id(
            order_review_id=order_review.order_review_id,
            verification_run_id=order_review.verification_run_id,
        ),
        order_review_id=order_review.order_review_id,
        verification_run_id=order_review.verification_run_id,
        final_checklist_passed=not fail_reasons,
        fail_reasons=fail_reasons,
        **flags,
    )


def make_order_review_id(*, order_intent_id: str, verification_run_id: str) -> str:
    _require_non_empty("order_intent_id", order_intent_id)
    _require_non_empty("verification_run_id", verification_run_id)
    digest = _short_hash({
        "order_intent_id": order_intent_id,
        "verification_run_id": verification_run_id,
    })
    return f"review_{verification_run_id}_{digest}"


def make_final_checklist_id(*, order_review_id: str, verification_run_id: str) -> str:
    _require_non_empty("order_review_id", order_review_id)
    _require_non_empty("verification_run_id", verification_run_id)
    digest = _short_hash({
        "order_review_id": order_review_id,
        "verification_run_id": verification_run_id,
    })
    return f"checklist_{verification_run_id}_{digest}"


def _validate_order_review(review: OrderReview) -> None:
    for field_name, value in (
        ("order_review_id", review.order_review_id),
        ("order_intent_id", review.order_intent_id),
        ("candidate_id", review.candidate_id),
        ("decision_id", review.decision_id),
        ("readonly_precheck_id", review.readonly_precheck_id),
        ("verification_run_id", review.verification_run_id),
    ):
        _require_non_empty(field_name, value)
    if review.order_review_id != make_order_review_id(
        order_intent_id=review.order_intent_id,
        verification_run_id=review.verification_run_id,
    ):
        raise LiveVerificationOrderReviewError("order_review_id mismatch")
    if review.symbol != SUPPORTED_SYMBOL:
        raise LiveVerificationOrderReviewError("symbol must be USD_JPY")
    if review.units != SUPPORTED_UNITS:
        raise LiveVerificationOrderReviewError("units must be 100")
    if review.mode != LIVE_VERIFICATION_MODE:
        raise LiveVerificationOrderReviewError("mode must be live_verification")
    if not isinstance(review.side, OrderIntentSide):
        raise LiveVerificationOrderReviewError("side must be BUY or SELL")
    if review.risk_decision_status not in ALLOW_STATUSES:
        raise LiveVerificationOrderReviewError("risk decision must be ALLOW")
    _require_true("readonly_precheck_passed", review.readonly_precheck_passed)
    _require_true("ready_for_order_review", review.ready_for_order_review)
    _require_true("manual_confirmation_required", review.manual_confirmation_required)
    _ensure_aware(review.created_at, field_name="created_at")
    _ensure_aware(review.expires_at, field_name="expires_at")
    if review.expires_at <= review.created_at:
        raise LiveVerificationOrderReviewError("expires_at must be after created_at")
    if not isinstance(review.review_notes, tuple) or any(
        not isinstance(note, str) for note in review.review_notes
    ):
        raise LiveVerificationOrderReviewError("review_notes must be tuple[str, ...]")


def _validate_final_order_checklist(checklist: FinalOrderChecklist) -> None:
    _require_non_empty("checklist_id", checklist.checklist_id)
    _require_non_empty("order_review_id", checklist.order_review_id)
    _require_non_empty("verification_run_id", checklist.verification_run_id)
    if checklist.checklist_id != make_final_checklist_id(
        order_review_id=checklist.order_review_id,
        verification_run_id=checklist.verification_run_id,
    ):
        raise LiveVerificationOrderReviewError("checklist_id mismatch")
    flags = {
        "git_clean": checklist.git_clean,
        "tests_passed": checklist.tests_passed,
        "ruff_passed": checklist.ruff_passed,
        "secret_scan_passed": checklist.secret_scan_passed,
        "readonly_precheck_passed": checklist.readonly_precheck_passed,
        "no_open_positions": checklist.no_open_positions,
        "no_active_orders": checklist.no_active_orders,
        "risk_decision_allow": checklist.risk_decision_allow,
        "ready_for_order_review": checklist.ready_for_order_review,
        "symbol_is_usd_jpy": checklist.symbol_is_usd_jpy,
        "units_is_100": checklist.units_is_100,
        "single_intent_for_run": checklist.single_intent_for_run,
        "manual_confirmation_required": checklist.manual_confirmation_required,
        "user_explicit_approval": checklist.user_explicit_approval,
        "broker_not_implemented": checklist.broker_not_implemented,
        "order_api_not_implemented": checklist.order_api_not_implemented,
        "raw_response_not_saved": checklist.raw_response_not_saved,
        "headers_not_saved": checklist.headers_not_saved,
        "signature_not_saved": checklist.signature_not_saved,
    }
    _validate_bool_map(flags)
    expected_fail_reasons = tuple(name for name, passed in flags.items() if not passed)
    if checklist.fail_reasons != expected_fail_reasons:
        raise LiveVerificationOrderReviewError("fail_reasons mismatch")
    if checklist.final_checklist_passed != (not expected_fail_reasons):
        raise LiveVerificationOrderReviewError("final_checklist_passed mismatch")


def _default_bool(value: bool | None, default: bool) -> bool:
    return default if value is None else value


def _validate_bool_map(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        if type(value) is not bool:
            raise LiveVerificationOrderReviewError(f"{name} must be bool")


def _require_true(field_name: str, value: bool) -> None:
    if type(value) is not bool:
        raise LiveVerificationOrderReviewError(f"{field_name} must be bool")
    if not value:
        raise LiveVerificationOrderReviewError(f"{field_name} must be true")


def _ensure_aware(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise LiveVerificationOrderReviewError(f"{field_name} must be timezone-aware datetime")
    return value.astimezone(UTC)


def _short_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationOrderReviewError(f"{field_name} is required")
