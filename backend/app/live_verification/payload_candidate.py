"""Mocked local-only payload candidate for Phase 3D-4 live verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.live_verification.broker_boundary import NoNetworkBrokerBoundaryResult
from app.live_verification.errors import LiveVerificationPayloadCandidateError
from app.live_verification.intent import OrderIntentSide
from app.live_verification.order_review import FinalOrderChecklist, OrderReview
from app.live_verification.precheck import (
    LIVE_VERIFICATION_MODE,
    SUPPORTED_SYMBOL,
    SUPPORTED_UNITS,
)
from app.live_verification.state import LiveVerificationState

ALLOWED_MOCKED_EXECUTION_TYPES = frozenset({"MARKET"})
ALLOWED_MOCKED_TIME_IN_FORCE = frozenset({"FAK"})
ALLOWED_MOCKED_SETTLE_TYPES = frozenset({"OPEN"})


@dataclass(frozen=True)
class MockedOrderPayloadCandidate:
    mocked_payload_candidate_id: str
    order_review_id: str
    order_intent_id: str
    verification_run_id: str
    final_checklist_id: str
    boundary_check_id: str
    symbol: str
    side: OrderIntentSide
    size: int
    execution_type: str
    time_in_force: str
    settle_type: str
    mode: str
    manual_confirmation_required: bool
    network_used: bool
    api_key_used: bool
    broker_called: bool
    real_order_attempted: bool

    def __post_init__(self) -> None:
        _validate_candidate(self)


def build_mocked_order_payload_candidate(
    *,
    order_review: OrderReview,
    final_checklist: FinalOrderChecklist,
    boundary_result: NoNetworkBrokerBoundaryResult,
    execution_type: str,
    time_in_force: str,
    settle_type: str,
) -> MockedOrderPayloadCandidate:
    """Build a local-only candidate after review, checklist, and boundary checks pass."""
    _validate_source_inputs(
        order_review=order_review,
        final_checklist=final_checklist,
        boundary_result=boundary_result,
    )
    return MockedOrderPayloadCandidate(
        mocked_payload_candidate_id=make_mocked_payload_candidate_id(
            order_review_id=order_review.order_review_id,
            final_checklist_id=final_checklist.checklist_id,
            boundary_check_id=boundary_result.boundary_check_id,
            verification_run_id=order_review.verification_run_id,
        ),
        order_review_id=order_review.order_review_id,
        order_intent_id=order_review.order_intent_id,
        verification_run_id=order_review.verification_run_id,
        final_checklist_id=final_checklist.checklist_id,
        boundary_check_id=boundary_result.boundary_check_id,
        symbol=order_review.symbol,
        side=order_review.side,
        size=order_review.units,
        execution_type=execution_type,
        time_in_force=time_in_force,
        settle_type=settle_type,
        mode=order_review.mode,
        manual_confirmation_required=order_review.manual_confirmation_required,
        network_used=boundary_result.network_used,
        api_key_used=boundary_result.api_key_used,
        broker_called=boundary_result.broker_called,
        real_order_attempted=boundary_result.real_order_attempted,
    )


def make_mocked_payload_candidate_id(
    *,
    order_review_id: str,
    final_checklist_id: str,
    boundary_check_id: str,
    verification_run_id: str,
) -> str:
    for field_name, value in (
        ("order_review_id", order_review_id),
        ("final_checklist_id", final_checklist_id),
        ("boundary_check_id", boundary_check_id),
        ("verification_run_id", verification_run_id),
    ):
        _require_non_empty(field_name, value)
    digest = _short_hash({
        "boundary_check_id": boundary_check_id,
        "final_checklist_id": final_checklist_id,
        "order_review_id": order_review_id,
        "verification_run_id": verification_run_id,
    })
    return f"mocked_payload_{verification_run_id}_{digest}"


def _validate_source_inputs(
    *,
    order_review: OrderReview,
    final_checklist: FinalOrderChecklist,
    boundary_result: NoNetworkBrokerBoundaryResult,
) -> None:
    if not final_checklist.final_checklist_passed:
        raise LiveVerificationPayloadCandidateError("final checklist must pass")
    if not boundary_result.boundary_passed:
        raise LiveVerificationPayloadCandidateError("boundary result must pass")
    if boundary_result.final_state != LiveVerificationState.READY_FOR_ORDER_REVIEW.value:
        raise LiveVerificationPayloadCandidateError("boundary result must be ready")
    if any((
        boundary_result.network_used,
        boundary_result.api_key_used,
        boundary_result.order_payload_created,
        boundary_result.broker_called,
        boundary_result.real_order_attempted,
    )):
        raise LiveVerificationPayloadCandidateError("boundary result crossed no-network flags")
    if order_review.order_review_id != final_checklist.order_review_id:
        raise LiveVerificationPayloadCandidateError("order_review_id mismatch")
    if order_review.order_review_id != boundary_result.order_review_id:
        raise LiveVerificationPayloadCandidateError("boundary order_review_id mismatch")
    if order_review.order_intent_id != boundary_result.order_intent_id:
        raise LiveVerificationPayloadCandidateError("boundary order_intent_id mismatch")
    if final_checklist.checklist_id != boundary_result.final_checklist_id:
        raise LiveVerificationPayloadCandidateError("final_checklist_id mismatch")
    if len({
        order_review.verification_run_id,
        final_checklist.verification_run_id,
        boundary_result.verification_run_id,
    }) != 1:
        raise LiveVerificationPayloadCandidateError("verification_run_id mismatch")
    if order_review.symbol != SUPPORTED_SYMBOL:
        raise LiveVerificationPayloadCandidateError("symbol must be USD_JPY")
    if order_review.units != SUPPORTED_UNITS:
        raise LiveVerificationPayloadCandidateError("size must be 100")
    if order_review.mode != LIVE_VERIFICATION_MODE:
        raise LiveVerificationPayloadCandidateError("mode must be live_verification")
    if order_review.manual_confirmation_required is not True:
        raise LiveVerificationPayloadCandidateError("manual confirmation is required")


def _validate_candidate(candidate: MockedOrderPayloadCandidate) -> None:
    for field_name, value in (
        ("mocked_payload_candidate_id", candidate.mocked_payload_candidate_id),
        ("order_review_id", candidate.order_review_id),
        ("order_intent_id", candidate.order_intent_id),
        ("verification_run_id", candidate.verification_run_id),
        ("final_checklist_id", candidate.final_checklist_id),
        ("boundary_check_id", candidate.boundary_check_id),
    ):
        _require_non_empty(field_name, value)
    if candidate.mocked_payload_candidate_id != make_mocked_payload_candidate_id(
        order_review_id=candidate.order_review_id,
        final_checklist_id=candidate.final_checklist_id,
        boundary_check_id=candidate.boundary_check_id,
        verification_run_id=candidate.verification_run_id,
    ):
        raise LiveVerificationPayloadCandidateError("mocked_payload_candidate_id mismatch")
    if candidate.symbol != SUPPORTED_SYMBOL:
        raise LiveVerificationPayloadCandidateError("symbol must be USD_JPY")
    if not isinstance(candidate.side, OrderIntentSide):
        raise LiveVerificationPayloadCandidateError("side must be BUY or SELL")
    if candidate.size != SUPPORTED_UNITS:
        raise LiveVerificationPayloadCandidateError("size must be 100")
    if candidate.execution_type not in ALLOWED_MOCKED_EXECUTION_TYPES:
        raise LiveVerificationPayloadCandidateError("execution_type is not allowed")
    if candidate.time_in_force not in ALLOWED_MOCKED_TIME_IN_FORCE:
        raise LiveVerificationPayloadCandidateError("time_in_force is not allowed")
    if candidate.settle_type not in ALLOWED_MOCKED_SETTLE_TYPES:
        raise LiveVerificationPayloadCandidateError("settle_type is not allowed")
    if candidate.mode != LIVE_VERIFICATION_MODE:
        raise LiveVerificationPayloadCandidateError("mode must be live_verification")
    if candidate.manual_confirmation_required is not True:
        raise LiveVerificationPayloadCandidateError("manual confirmation is required")
    flags = {
        "network_used": candidate.network_used,
        "api_key_used": candidate.api_key_used,
        "broker_called": candidate.broker_called,
        "real_order_attempted": candidate.real_order_attempted,
    }
    for name, value in flags.items():
        if type(value) is not bool:
            raise LiveVerificationPayloadCandidateError(f"{name} must be bool")
        if value:
            raise LiveVerificationPayloadCandidateError(f"{name} must be false")


def _short_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationPayloadCandidateError(f"{field_name} is required")
