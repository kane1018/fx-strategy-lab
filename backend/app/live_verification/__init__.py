"""Phase 3C-1 live verification mocked core."""

from app.live_verification.correlation import (
    CandidateReference,
    RiskDecisionReference,
    SignalReference,
    build_correlated_order_intent,
    transition_after_readonly_precheck,
    transition_after_risk_decision,
    validate_live_verification_correlation,
)
from app.live_verification.dry_run import (
    LiveVerificationDryRunResult,
    ReadonlyPrecheckInput,
    run_live_verification_dry_run,
)
from app.live_verification.errors import (
    LiveVerificationCorrelationError,
    LiveVerificationError,
    LiveVerificationForbiddenActionError,
    LiveVerificationIntentError,
    LiveVerificationPrecheckError,
    LiveVerificationStateError,
    LiveVerificationValidationError,
)
from app.live_verification.intent import (
    OrderIntent,
    OrderIntentSide,
    assert_single_intent_per_run,
    build_order_intent_from_allowed_decision,
    make_order_intent_id,
)
from app.live_verification.precheck import (
    LIVE_VERIFICATION_MODE,
    SUPPORTED_SYMBOL,
    SUPPORTED_UNITS,
    PrecheckFailureReason,
    ReadonlyPrecheckResult,
    evaluate_readonly_precheck,
    make_readonly_precheck_id,
)
from app.live_verification.state import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    LiveVerificationState,
    normalize_live_verification_state,
    transition_live_verification_state,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "LIVE_VERIFICATION_MODE",
    "SUPPORTED_SYMBOL",
    "SUPPORTED_UNITS",
    "OrderIntent",
    "OrderIntentSide",
    "PrecheckFailureReason",
    "ReadonlyPrecheckResult",
    "CandidateReference",
    "LiveVerificationDryRunResult",
    "LiveVerificationError",
    "LiveVerificationCorrelationError",
    "LiveVerificationForbiddenActionError",
    "LiveVerificationIntentError",
    "LiveVerificationPrecheckError",
    "LiveVerificationState",
    "LiveVerificationStateError",
    "LiveVerificationValidationError",
    "ReadonlyPrecheckInput",
    "RiskDecisionReference",
    "SignalReference",
    "TERMINAL_STATES",
    "assert_single_intent_per_run",
    "build_correlated_order_intent",
    "build_order_intent_from_allowed_decision",
    "evaluate_readonly_precheck",
    "make_order_intent_id",
    "make_readonly_precheck_id",
    "normalize_live_verification_state",
    "run_live_verification_dry_run",
    "transition_after_readonly_precheck",
    "transition_after_risk_decision",
    "transition_live_verification_state",
    "validate_live_verification_correlation",
]
