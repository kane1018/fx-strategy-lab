"""Pure mocked dry-run flow for Phase 3C-3 live verification."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.live_verification.correlation import (
    CandidateReference,
    RiskDecisionReference,
    SignalReference,
    build_correlated_order_intent,
)
from app.live_verification.errors import LiveVerificationError
from app.live_verification.intent import OrderIntent
from app.live_verification.precheck import (
    LIVE_VERIFICATION_MODE,
    SUPPORTED_UNITS,
    PrecheckFailureReason,
    evaluate_readonly_precheck,
)
from app.live_verification.state import (
    LiveVerificationState,
    transition_live_verification_state,
)


@dataclass(frozen=True)
class ReadonlyPrecheckInput:
    symbol: str
    verification_run_id: str
    expected_units: int = SUPPORTED_UNITS
    mode: str = LIVE_VERIFICATION_MODE
    account_assets_ok: bool = True
    open_positions_ok: bool = True
    active_orders_ok: bool = True
    has_open_positions: bool = False
    has_active_orders: bool = False
    raw_response_saved: bool = False
    headers_saved: bool = False
    credentials_printed: bool = False
    retry_attempted: bool = False


@dataclass(frozen=True)
class LiveVerificationDryRunResult:
    verification_run_id: str
    readonly_precheck_id: str | None
    order_intent_id: str | None
    final_state: LiveVerificationState
    ready_for_order_review: bool
    fail_reason: str | None
    safety_flags: tuple[str, ...]
    order_intent: OrderIntent | None
    state_history: tuple[LiveVerificationState, ...]


def run_live_verification_dry_run(
    *,
    signal: SignalReference,
    candidate: CandidateReference,
    decision: RiskDecisionReference,
    precheck_input: ReadonlyPrecheckInput,
    manual_confirmation_required: bool,
    existing_intents: Iterable[OrderIntent] = (),
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> LiveVerificationDryRunResult:
    """Run mocked live verification to READY_FOR_ORDER_REVIEW without external I/O."""
    state = LiveVerificationState.INIT
    history = [state]
    precheck_id: str | None = None

    try:
        state = transition_live_verification_state(
            state,
            LiveVerificationState.READONLY_PRECHECK,
        )
        history.append(state)
        precheck = evaluate_readonly_precheck(
            symbol=precheck_input.symbol,
            verification_run_id=precheck_input.verification_run_id,
            expected_units=precheck_input.expected_units,
            account_assets_ok=precheck_input.account_assets_ok,
            open_positions_ok=precheck_input.open_positions_ok,
            active_orders_ok=precheck_input.active_orders_ok,
            has_open_positions=precheck_input.has_open_positions,
            has_active_orders=precheck_input.has_active_orders,
            raw_response_saved=precheck_input.raw_response_saved,
            headers_saved=precheck_input.headers_saved,
            credentials_printed=precheck_input.credentials_printed,
            mode=precheck_input.mode,
            retry_attempted=precheck_input.retry_attempted,
        )
        precheck_id = precheck.readonly_precheck_id
        if not precheck.readonly_precheck_passed:
            return _failed_result(
                verification_run_id=signal.verification_run_id,
                readonly_precheck_id=precheck_id,
                fail_reason="read-only precheck failed",
                safety_flags=_precheck_safety_flags(precheck.fail_reasons),
                state=state,
                history=history,
            )

        state = transition_live_verification_state(
            state,
            LiveVerificationState.RISK_DECISION_CONFIRMED,
        )
        history.append(state)
        intent = build_correlated_order_intent(
            signal=signal,
            candidate=candidate,
            decision=decision,
            precheck=precheck,
            manual_confirmation_required=manual_confirmation_required,
            existing_intents=existing_intents,
            created_at=created_at,
            expires_at=expires_at,
        )
        state = transition_live_verification_state(
            state,
            LiveVerificationState.ORDER_INTENT_CREATED,
        )
        history.append(state)
        state = transition_live_verification_state(
            state,
            LiveVerificationState.MANUAL_CONFIRMATION_REQUIRED,
        )
        history.append(state)
        state = transition_live_verification_state(
            state,
            LiveVerificationState.READY_FOR_ORDER_REVIEW,
        )
        history.append(state)
        return LiveVerificationDryRunResult(
            verification_run_id=signal.verification_run_id,
            readonly_precheck_id=precheck_id,
            order_intent_id=intent.order_intent_id,
            final_state=state,
            ready_for_order_review=True,
            fail_reason=None,
            safety_flags=(),
            order_intent=intent,
            state_history=tuple(history),
        )
    except LiveVerificationError as error:
        return _failed_result(
            verification_run_id=signal.verification_run_id,
            readonly_precheck_id=precheck_id,
            fail_reason=f"{error.__class__.__name__}: {error}",
            safety_flags=(error.__class__.__name__,),
            state=state,
            history=history,
        )


def _failed_result(
    *,
    verification_run_id: str,
    readonly_precheck_id: str | None,
    fail_reason: str,
    safety_flags: tuple[str, ...],
    state: LiveVerificationState,
    history: list[LiveVerificationState],
) -> LiveVerificationDryRunResult:
    failed_state = transition_live_verification_state(state, LiveVerificationState.FAILED)
    history.append(failed_state)
    return LiveVerificationDryRunResult(
        verification_run_id=verification_run_id,
        readonly_precheck_id=readonly_precheck_id,
        order_intent_id=None,
        final_state=failed_state,
        ready_for_order_review=False,
        fail_reason=fail_reason,
        safety_flags=safety_flags,
        order_intent=None,
        state_history=tuple(history),
    )


def _precheck_safety_flags(
    fail_reasons: tuple[PrecheckFailureReason, ...],
) -> tuple[str, ...]:
    return tuple(reason.value for reason in fail_reasons)
