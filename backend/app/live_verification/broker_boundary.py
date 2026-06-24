"""No-network broker boundary checks for Phase 3D-2A live verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.live_verification.errors import (
    LiveVerificationBrokerBoundaryError,
    LiveVerificationStateError,
)
from app.live_verification.order_review import FinalOrderChecklist, OrderReview
from app.live_verification.precheck import (
    LIVE_VERIFICATION_MODE,
    SUPPORTED_SYMBOL,
    SUPPORTED_UNITS,
)
from app.live_verification.state import (
    LiveVerificationState,
    normalize_live_verification_state,
)


@dataclass(frozen=True)
class NoNetworkBrokerBoundaryResult:
    boundary_check_id: str
    order_review_id: str
    order_intent_id: str
    verification_run_id: str
    final_checklist_id: str
    boundary_passed: bool
    final_state: str
    network_used: bool
    api_key_used: bool
    order_payload_created: bool
    broker_called: bool
    real_order_attempted: bool
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_boundary_result(self)


def evaluate_no_network_broker_boundary(
    *,
    order_review: OrderReview,
    final_checklist: FinalOrderChecklist,
    final_state: LiveVerificationState | str,
    network_used: bool = False,
    api_key_used: bool = False,
    order_payload_created: bool = False,
    broker_called: bool = False,
    real_order_attempted: bool = False,
) -> NoNetworkBrokerBoundaryResult:
    """Evaluate the mocked no-network boundary without creating an executable order."""
    flags = {
        "network_used": network_used,
        "api_key_used": api_key_used,
        "order_payload_created": order_payload_created,
        "broker_called": broker_called,
        "real_order_attempted": real_order_attempted,
    }
    _validate_bool_map(flags)

    order_review_id = _safe_text(
        getattr(order_review, "order_review_id", None),
        "missing_order_review_id",
    )
    order_intent_id = _safe_text(
        getattr(order_review, "order_intent_id", None),
        "missing_order_intent_id",
    )
    review_run_id = _safe_text(
        getattr(order_review, "verification_run_id", None),
        "missing_verification_run_id",
    )
    final_checklist_id = _safe_text(
        getattr(final_checklist, "checklist_id", None),
        "missing_final_checklist_id",
    )
    checklist_run_id = _safe_text(
        getattr(final_checklist, "verification_run_id", None),
        "missing_checklist_verification_run_id",
    )
    normalized_state = _normalize_state_value(final_state)

    fail_reasons = list(_structural_fail_reasons(
        order_review=order_review,
        final_checklist=final_checklist,
        review_run_id=review_run_id,
        checklist_run_id=checklist_run_id,
        normalized_state=normalized_state,
        flags=flags,
    ))

    if final_checklist_id == "missing_final_checklist_id":
        fail_reasons.append("final_checklist_id_missing")
    if order_review_id == "missing_order_review_id":
        fail_reasons.append("order_review_id_missing")
    if order_intent_id == "missing_order_intent_id":
        fail_reasons.append("order_intent_id_missing")

    return NoNetworkBrokerBoundaryResult(
        boundary_check_id=make_no_network_boundary_check_id(
            order_review_id=order_review_id,
            final_checklist_id=final_checklist_id,
            verification_run_id=review_run_id,
        ),
        order_review_id=order_review_id,
        order_intent_id=order_intent_id,
        verification_run_id=review_run_id,
        final_checklist_id=final_checklist_id,
        boundary_passed=not fail_reasons,
        final_state=normalized_state,
        fail_reasons=tuple(fail_reasons),
        **flags,
    )


def make_no_network_boundary_check_id(
    *,
    order_review_id: str,
    final_checklist_id: str,
    verification_run_id: str,
) -> str:
    _require_non_empty("order_review_id", order_review_id)
    _require_non_empty("final_checklist_id", final_checklist_id)
    _require_non_empty("verification_run_id", verification_run_id)
    digest = _short_hash({
        "final_checklist_id": final_checklist_id,
        "order_review_id": order_review_id,
        "verification_run_id": verification_run_id,
    })
    return f"boundary_{verification_run_id}_{digest}"


def _structural_fail_reasons(
    *,
    order_review: OrderReview,
    final_checklist: FinalOrderChecklist,
    review_run_id: str,
    checklist_run_id: str,
    normalized_state: str,
    flags: dict[str, bool],
) -> tuple[str, ...]:
    fail_reasons: list[str] = []
    if not getattr(final_checklist, "final_checklist_passed", False):
        fail_reasons.append("final_checklist_not_passed")
        for reason in getattr(final_checklist, "fail_reasons", ()):
            if isinstance(reason, str) and reason:
                fail_reasons.append(f"final_checklist:{reason}")
    if normalized_state != LiveVerificationState.READY_FOR_ORDER_REVIEW.value:
        fail_reasons.append("final_state_not_ready_for_order_review")
    for name, value in flags.items():
        if value:
            fail_reasons.append(name)
    if getattr(order_review, "symbol", None) != SUPPORTED_SYMBOL:
        fail_reasons.append("symbol_not_usd_jpy")
    if getattr(order_review, "units", None) != SUPPORTED_UNITS:
        fail_reasons.append("units_not_100")
    if getattr(order_review, "mode", None) != LIVE_VERIFICATION_MODE:
        fail_reasons.append("mode_not_live_verification")
    if getattr(order_review, "readonly_precheck_passed", None) is not True:
        fail_reasons.append("readonly_precheck_not_passed")
    if getattr(order_review, "manual_confirmation_required", None) is not True:
        fail_reasons.append("manual_confirmation_required_not_true")
    if getattr(order_review, "ready_for_order_review", None) is not True:
        fail_reasons.append("order_review_not_ready")
    if review_run_id != checklist_run_id:
        fail_reasons.append("verification_run_id_mismatch")
    if getattr(final_checklist, "order_review_id", None) != getattr(
        order_review,
        "order_review_id",
        None,
    ):
        fail_reasons.append("order_review_id_mismatch")
    return tuple(fail_reasons)


def _normalize_state_value(value: LiveVerificationState | str) -> str:
    try:
        return normalize_live_verification_state(value).value
    except LiveVerificationStateError:
        return "UNKNOWN"


def _validate_boundary_result(result: NoNetworkBrokerBoundaryResult) -> None:
    for field_name, value in (
        ("boundary_check_id", result.boundary_check_id),
        ("order_review_id", result.order_review_id),
        ("order_intent_id", result.order_intent_id),
        ("verification_run_id", result.verification_run_id),
        ("final_checklist_id", result.final_checklist_id),
        ("final_state", result.final_state),
    ):
        _require_non_empty(field_name, value)
    if result.boundary_check_id != make_no_network_boundary_check_id(
        order_review_id=result.order_review_id,
        final_checklist_id=result.final_checklist_id,
        verification_run_id=result.verification_run_id,
    ):
        raise LiveVerificationBrokerBoundaryError("boundary_check_id mismatch")
    flags = {
        "boundary_passed": result.boundary_passed,
        "network_used": result.network_used,
        "api_key_used": result.api_key_used,
        "order_payload_created": result.order_payload_created,
        "broker_called": result.broker_called,
        "real_order_attempted": result.real_order_attempted,
    }
    _validate_bool_map(flags)
    if not isinstance(result.fail_reasons, tuple) or any(
        not isinstance(reason, str) or not reason for reason in result.fail_reasons
    ):
        raise LiveVerificationBrokerBoundaryError("fail_reasons must be tuple[str, ...]")
    if result.boundary_passed and result.fail_reasons:
        raise LiveVerificationBrokerBoundaryError("passed boundary cannot contain fail reasons")
    if not result.boundary_passed and not result.fail_reasons:
        raise LiveVerificationBrokerBoundaryError("failed boundary requires fail reasons")
    if result.boundary_passed:
        if result.final_state != LiveVerificationState.READY_FOR_ORDER_REVIEW.value:
            raise LiveVerificationBrokerBoundaryError("passed boundary requires ready state")
        if any((
            result.network_used,
            result.api_key_used,
            result.order_payload_created,
            result.broker_called,
            result.real_order_attempted,
        )):
            raise LiveVerificationBrokerBoundaryError(
                "passed boundary cannot cross no-network flags"
            )


def _validate_bool_map(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        if type(value) is not bool:
            raise LiveVerificationBrokerBoundaryError(f"{name} must be bool")


def _safe_text(value: object, missing_value: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return missing_value


def _short_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationBrokerBoundaryError(f"{field_name} is required")
