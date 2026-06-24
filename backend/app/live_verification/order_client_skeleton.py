"""Disabled no-network client plan for Phase 3D-6 live verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from app.live_verification.errors import LiveVerificationOrderClientSkeletonError
from app.live_verification.payload_candidate import (
    ALLOWED_MOCKED_EXECUTION_TYPES,
    ALLOWED_MOCKED_SETTLE_TYPES,
    ALLOWED_MOCKED_TIME_IN_FORCE,
    MockedOrderPayloadCandidate,
    make_mocked_payload_candidate_id,
)
from app.live_verification.precheck import (
    LIVE_VERIFICATION_MODE,
    SUPPORTED_SYMBOL,
    SUPPORTED_UNITS,
)

NO_NETWORK_CLIENT_MODE = "no_network_skeleton"


@dataclass(frozen=True)
class DisabledOrderClientPlan:
    client_plan_id: str
    payload_candidate_id: str
    order_review_id: str
    final_checklist_id: str
    boundary_check_id: str
    verification_run_id: str
    symbol: str
    units: int
    execution_type: str
    time_in_force: str
    settle_type: str
    client_mode: str
    disabled_by_default: bool
    network_enabled: bool
    credential_access_enabled: bool
    manual_confirmation_required: bool
    ready_for_future_review: bool
    created_at: datetime
    fail_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_client_plan(self)


def build_disabled_order_client_plan(
    *,
    candidate: MockedOrderPayloadCandidate,
    client_mode: str = NO_NETWORK_CLIENT_MODE,
    disabled_by_default: bool = True,
    network_enabled: bool = False,
    credential_access_enabled: bool = False,
    manual_confirmation_required: bool | None = None,
    created_at: datetime | None = None,
) -> DisabledOrderClientPlan:
    """Build a local-only plan that cannot activate transport or credential access."""
    _validate_candidate(candidate)
    manual_required = (
        candidate.manual_confirmation_required
        if manual_confirmation_required is None
        else manual_confirmation_required
    )
    return DisabledOrderClientPlan(
        client_plan_id=make_disabled_order_client_plan_id(
            payload_candidate_id=candidate.mocked_payload_candidate_id,
            verification_run_id=candidate.verification_run_id,
        ),
        payload_candidate_id=candidate.mocked_payload_candidate_id,
        order_review_id=candidate.order_review_id,
        final_checklist_id=candidate.final_checklist_id,
        boundary_check_id=candidate.boundary_check_id,
        verification_run_id=candidate.verification_run_id,
        symbol=candidate.symbol,
        units=candidate.size,
        execution_type=candidate.execution_type,
        time_in_force=candidate.time_in_force,
        settle_type=candidate.settle_type,
        client_mode=client_mode,
        disabled_by_default=disabled_by_default,
        network_enabled=network_enabled,
        credential_access_enabled=credential_access_enabled,
        manual_confirmation_required=manual_required,
        ready_for_future_review=True,
        created_at=_ensure_aware(created_at or datetime.now(UTC), field_name="created_at"),
        fail_reasons=(),
    )


def make_disabled_order_client_plan_id(
    *,
    payload_candidate_id: str,
    verification_run_id: str,
) -> str:
    _require_non_empty("payload_candidate_id", payload_candidate_id)
    _require_non_empty("verification_run_id", verification_run_id)
    digest = _short_hash({
        "payload_candidate_id": payload_candidate_id,
        "verification_run_id": verification_run_id,
    })
    return f"disabled_client_{verification_run_id}_{digest}"


def _validate_candidate(candidate: MockedOrderPayloadCandidate) -> None:
    for field_name, value in (
        ("mocked_payload_candidate_id", candidate.mocked_payload_candidate_id),
        ("order_review_id", candidate.order_review_id),
        ("final_checklist_id", candidate.final_checklist_id),
        ("boundary_check_id", candidate.boundary_check_id),
        ("verification_run_id", candidate.verification_run_id),
    ):
        _require_non_empty(field_name, value)
    expected_id = make_mocked_payload_candidate_id(
        order_review_id=candidate.order_review_id,
        final_checklist_id=candidate.final_checklist_id,
        boundary_check_id=candidate.boundary_check_id,
        verification_run_id=candidate.verification_run_id,
    )
    if candidate.mocked_payload_candidate_id != expected_id:
        raise LiveVerificationOrderClientSkeletonError("payload candidate id mismatch")
    if candidate.symbol != SUPPORTED_SYMBOL:
        raise LiveVerificationOrderClientSkeletonError("symbol must be USD_JPY")
    if candidate.size != SUPPORTED_UNITS:
        raise LiveVerificationOrderClientSkeletonError("units must be 100")
    if candidate.execution_type not in ALLOWED_MOCKED_EXECUTION_TYPES:
        raise LiveVerificationOrderClientSkeletonError("execution_type is not allowed")
    if candidate.time_in_force not in ALLOWED_MOCKED_TIME_IN_FORCE:
        raise LiveVerificationOrderClientSkeletonError("time_in_force is not allowed")
    if candidate.settle_type not in ALLOWED_MOCKED_SETTLE_TYPES:
        raise LiveVerificationOrderClientSkeletonError("settle_type is not allowed")
    if candidate.mode != LIVE_VERIFICATION_MODE:
        raise LiveVerificationOrderClientSkeletonError("mode must be live_verification")
    if candidate.manual_confirmation_required is not True:
        raise LiveVerificationOrderClientSkeletonError("manual confirmation is required")
    _validate_false_flags({
        "network_used": candidate.network_used,
        "api_key_used": candidate.api_key_used,
        "broker_called": candidate.broker_called,
        "real_order_attempted": candidate.real_order_attempted,
    })


def _validate_client_plan(plan: DisabledOrderClientPlan) -> None:
    for field_name, value in (
        ("client_plan_id", plan.client_plan_id),
        ("payload_candidate_id", plan.payload_candidate_id),
        ("order_review_id", plan.order_review_id),
        ("final_checklist_id", plan.final_checklist_id),
        ("boundary_check_id", plan.boundary_check_id),
        ("verification_run_id", plan.verification_run_id),
    ):
        _require_non_empty(field_name, value)
    expected_id = make_disabled_order_client_plan_id(
        payload_candidate_id=plan.payload_candidate_id,
        verification_run_id=plan.verification_run_id,
    )
    if plan.client_plan_id != expected_id:
        raise LiveVerificationOrderClientSkeletonError("client_plan_id mismatch")
    if plan.symbol != SUPPORTED_SYMBOL:
        raise LiveVerificationOrderClientSkeletonError("symbol must be USD_JPY")
    if plan.units != SUPPORTED_UNITS:
        raise LiveVerificationOrderClientSkeletonError("units must be 100")
    if plan.execution_type not in ALLOWED_MOCKED_EXECUTION_TYPES:
        raise LiveVerificationOrderClientSkeletonError("execution_type is not allowed")
    if plan.time_in_force not in ALLOWED_MOCKED_TIME_IN_FORCE:
        raise LiveVerificationOrderClientSkeletonError("time_in_force is not allowed")
    if plan.settle_type not in ALLOWED_MOCKED_SETTLE_TYPES:
        raise LiveVerificationOrderClientSkeletonError("settle_type is not allowed")
    if plan.client_mode != NO_NETWORK_CLIENT_MODE:
        raise LiveVerificationOrderClientSkeletonError("client mode is not allowed")
    _require_true("disabled_by_default", plan.disabled_by_default)
    _require_false("network_enabled", plan.network_enabled)
    _require_false("credential_access_enabled", plan.credential_access_enabled)
    _require_true("manual_confirmation_required", plan.manual_confirmation_required)
    _require_true("ready_for_future_review", plan.ready_for_future_review)
    _ensure_aware(plan.created_at, field_name="created_at")
    if plan.fail_reasons != ():
        raise LiveVerificationOrderClientSkeletonError("fail_reasons must be empty")


def _validate_false_flags(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        _require_false(name, value)


def _require_true(field_name: str, value: bool) -> None:
    if type(value) is not bool:
        raise LiveVerificationOrderClientSkeletonError(f"{field_name} must be bool")
    if not value:
        raise LiveVerificationOrderClientSkeletonError(f"{field_name} must be true")


def _require_false(field_name: str, value: bool) -> None:
    if type(value) is not bool:
        raise LiveVerificationOrderClientSkeletonError(f"{field_name} must be bool")
    if value:
        raise LiveVerificationOrderClientSkeletonError(f"{field_name} must be false")


def _ensure_aware(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise LiveVerificationOrderClientSkeletonError(
            f"{field_name} must be timezone-aware datetime"
        )
    return value.astimezone(UTC)


def _short_hash(data: dict[str, object]) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationOrderClientSkeletonError(f"{field_name} is required")
