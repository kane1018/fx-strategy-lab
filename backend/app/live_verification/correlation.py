"""ID correlation helpers for Phase 3C-2 live verification mocked core."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.live_verification.errors import LiveVerificationCorrelationError
from app.live_verification.intent import (
    ALLOW_STATUSES,
    OrderIntent,
    build_order_intent_from_allowed_decision,
)
from app.live_verification.precheck import ReadonlyPrecheckResult
from app.live_verification.state import (
    LiveVerificationState,
    transition_live_verification_state,
)


@dataclass(frozen=True)
class SignalReference:
    signal_id: str
    verification_run_id: str

    def __post_init__(self) -> None:
        _require_non_empty("signal_id", self.signal_id)
        _require_non_empty("verification_run_id", self.verification_run_id)


@dataclass(frozen=True)
class CandidateReference:
    candidate_id: str
    signal_id: str
    verification_run_id: str
    symbol: str
    side: str
    units: int

    def __post_init__(self) -> None:
        _require_non_empty("candidate_id", self.candidate_id)
        _require_non_empty("signal_id", self.signal_id)
        _require_non_empty("verification_run_id", self.verification_run_id)


@dataclass(frozen=True)
class RiskDecisionReference:
    decision_id: str
    candidate_id: str
    verification_run_id: str
    status: str

    def __post_init__(self) -> None:
        _require_non_empty("decision_id", self.decision_id)
        _require_non_empty("candidate_id", self.candidate_id)
        _require_non_empty("verification_run_id", self.verification_run_id)


def build_correlated_order_intent(
    *,
    signal: SignalReference,
    candidate: CandidateReference,
    decision: RiskDecisionReference,
    precheck: ReadonlyPrecheckResult,
    manual_confirmation_required: bool,
    existing_intents: Iterable[OrderIntent] = (),
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> OrderIntent:
    """Build an order intent only after mocked signal/candidate/decision/precheck IDs match."""
    validate_live_verification_correlation(
        signal=signal,
        candidate=candidate,
        decision=decision,
        precheck=precheck,
    )
    return build_order_intent_from_allowed_decision(
        candidate_id=candidate.candidate_id,
        decision_id=decision.decision_id,
        readonly_precheck_id=precheck.readonly_precheck_id,
        verification_run_id=candidate.verification_run_id,
        symbol=candidate.symbol,
        side=candidate.side,
        units=candidate.units,
        risk_decision_status=decision.status,
        readonly_precheck_passed=precheck.readonly_precheck_passed,
        manual_confirmation_required=manual_confirmation_required,
        created_at=created_at,
        expires_at=expires_at,
        existing_intents=existing_intents,
    )


def validate_live_verification_correlation(
    *,
    signal: SignalReference,
    candidate: CandidateReference,
    decision: RiskDecisionReference,
    precheck: ReadonlyPrecheckResult,
) -> None:
    """Fail closed unless all mocked records belong to the same verification run."""
    if candidate.signal_id != signal.signal_id:
        raise LiveVerificationCorrelationError("candidate signal_id mismatch")
    if decision.candidate_id != candidate.candidate_id:
        raise LiveVerificationCorrelationError("decision candidate_id mismatch")
    run_ids = {
        signal.verification_run_id,
        candidate.verification_run_id,
        decision.verification_run_id,
        precheck.verification_run_id,
    }
    if len(run_ids) != 1:
        raise LiveVerificationCorrelationError("verification_run_id mismatch")
    _require_non_empty("readonly_precheck_id", precheck.readonly_precheck_id)
    if decision.status not in ALLOW_STATUSES:
        raise LiveVerificationCorrelationError("risk decision must be ALLOW")
    if not precheck.readonly_precheck_passed:
        raise LiveVerificationCorrelationError("read-only precheck must pass")


def transition_after_readonly_precheck(
    current: LiveVerificationState | str,
    precheck: ReadonlyPrecheckResult,
) -> LiveVerificationState:
    if not precheck.readonly_precheck_passed:
        raise LiveVerificationCorrelationError("read-only precheck must pass")
    return transition_live_verification_state(
        current,
        LiveVerificationState.RISK_DECISION_CONFIRMED,
    )


def transition_after_risk_decision(
    current: LiveVerificationState | str,
    decision: RiskDecisionReference,
) -> LiveVerificationState:
    if decision.status not in ALLOW_STATUSES:
        raise LiveVerificationCorrelationError("risk decision must be ALLOW")
    return transition_live_verification_state(
        current,
        LiveVerificationState.ORDER_INTENT_CREATED,
    )


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationCorrelationError(f"{field_name} is required")
