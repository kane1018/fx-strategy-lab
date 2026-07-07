"""Official settlement execution boundary (no-POST implementation, injection-gated).

Mirror of ``gmo_live_actual_entry_execution_boundary`` for the dedicated
official size-based settlement route. It implements the single reviewed call
site through which a FUTURE actual settlement step could send exactly one
official settlement order -- without this module ever touching the network,
reading a credential value, or exposing a raw request/response, an ID, or a
broker value.

Hard rules enforced by construction:

- Settlement-only: the call site accepts only the dedicated
  OFFICIAL_SETTLEMENT request plan (``POST /private/v1/closeOrder``,
  size-based). Entry, generic, cancel, and change plans are rejected
  structurally. A generic opposite entry order used as a close has no
  surface here, and this module imports neither the one-shot live order
  primitive nor any legacy controlled/simulation module.
- The settlement side is never decided here: it must arrive as a ready
  mechanical provenance (prior ENTRY_BUY -> SETTLEMENT_SELL, prior
  ENTRY_SELL -> SETTLEMENT_BUY) from
  ``gmo_live_official_settlement_preflight``.
- The permit is settlement-only, one-POST-max, single-use, and never
  resolves the hard guard. The activation is one-use, never truthy, and
  derives the hard-guard ``allow`` solely from ``granted`` (no literal, no
  reusable allow bridge).
- ``send_official_settlement_post_once`` calls the shared real-broker-post
  hard guard exactly once, invokes the injected sender exactly once, and
  never resends on ANY outcome (accepted / rejected / unknown / timeout /
  network / client / server). There is no retry, repost, or second-POST
  branch in this module at all.
- Only sanitized ``SettlementPostSafeOutcome`` categories cross this
  boundary. There is no field carrying a raw request/response, an ID, a
  size, a price, a P/L, or a credential.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from app.private_api.order_builders import (
    REQUEST_KIND_OFFICIAL_SETTLEMENT,
    GmoFxPrivateRequestPlan,
)
from app.security.real_broker_post_hard_guard import (
    RealBrokerPostHardGuardError,
    assert_real_broker_post_allowed,
)
from app.services.gmo_live_official_settlement_preflight import (
    GmoOfficialSettlementPreflightError,
    OfficialSettlementSideProvenance,
    derive_official_settlement_side_from_prior_entry,
    validate_official_settlement_only_request_plan,
)

# Exact current-turn operator labels required for an executable settlement.
# These are settlement-specific: the entry-gate confirmations are NEVER
# reusable for a settlement step.
REQUIRED_SETTLEMENT_EXACT_CONFIRMATION = (
    "CONFIRM_ONE_SETTLEMENT_POST_MAX_NO_RETRY_NO_REPOST_NO_ENTRY"
)
REQUIRED_SETTLEMENT_READINESS = (
    "OPERATOR_READY_FOR_ONE_SETTLEMENT_POST_MAX_NO_RETRY_NO_REPOST"
)
REQUIRED_SETTLEMENT_UNDERSTANDS_RISK = (
    "OPERATOR_ACKNOWLEDGES_ACTUAL_BROKER_WRITE_RISK"
)

_SANITIZED_ACTIVATION_REPR = "OfficialSettlementExecutionActivation(<sanitized>)"

SETTLEMENT_POST_PERMIT_SCOPE_SETTLEMENT_ONLY = "SETTLEMENT_ONLY"

_FORBIDDEN_SETTLEMENT_PERMIT_SCOPES = frozenset(
    {
        "ENTRY",
        "ENTRY_ONLY",
        "GENERIC",
        "GENERIC_CLOSE",
        "GENERIC_OPPOSITE_ORDER",
        "CANCEL",
        "CANCELORDERS",
        "CHANGE",
        "CHANGEORDER",
    }
)


class GmoOfficialSettlementExecutionBoundaryError(RuntimeError):
    """Raised for fail-closed violations. Never carries a body/ID/value."""


class SettlementPostSafeOutcome(str, Enum):
    """Sanitized outcome categories only. Never raw/ID/value."""

    RESULT_ACCEPTED_SANITIZED = "RESULT_ACCEPTED_SANITIZED"
    RESULT_REJECTED_SANITIZED = "RESULT_REJECTED_SANITIZED"
    RESULT_UNKNOWN_SANITIZED = "RESULT_UNKNOWN_SANITIZED"
    RESULT_TIMEOUT_SANITIZED = "RESULT_TIMEOUT_SANITIZED"
    RESULT_NETWORK_ERROR_SANITIZED = "RESULT_NETWORK_ERROR_SANITIZED"
    RESULT_CLIENT_ERROR_SANITIZED = "RESULT_CLIENT_ERROR_SANITIZED"
    RESULT_SERVER_ERROR_SANITIZED = "RESULT_SERVER_ERROR_SANITIZED"
    RESULT_BLOCKED_BEFORE_POST_SANITIZED = "RESULT_BLOCKED_BEFORE_POST_SANITIZED"


@dataclass(frozen=True)
class OfficialSettlementOperatorCurrentTurnInput:
    """Current-turn operator labels. Not banked; supplied per actual step.

    The settlement direction is NOT an operator field: it is derived
    mechanically from ``prior_entry_signal_safe_label``.
    """

    prior_entry_signal_safe_label: str
    exact_confirmation: str
    readiness: str
    understands_risk: str


def verify_official_settlement_operator_input(
    operator_input: OfficialSettlementOperatorCurrentTurnInput,
) -> tuple[bool, OfficialSettlementSideProvenance, str]:
    """Return (ok, side_provenance, reason). AI never decides the side."""

    provenance = derive_official_settlement_side_from_prior_entry(
        operator_input.prior_entry_signal_safe_label
    )
    if operator_input.exact_confirmation != REQUIRED_SETTLEMENT_EXACT_CONFIRMATION:
        return (False, provenance, "OPERATOR_EXACT_CONFIRMATION_MISMATCH")
    if operator_input.readiness != REQUIRED_SETTLEMENT_READINESS:
        return (False, provenance, "OPERATOR_READINESS_MISMATCH")
    if operator_input.understands_risk != REQUIRED_SETTLEMENT_UNDERSTANDS_RISK:
        return (False, provenance, "OPERATOR_UNDERSTANDS_RISK_MISMATCH")
    if not provenance.ready:
        return (False, provenance, "SETTLEMENT_SIDE_NOT_DERIVABLE")
    return (True, provenance, "OPERATOR_INPUT_VERIFIED")


class GmoOfficialSettlementPostPermitStatus(str, Enum):
    PERMIT_DENIED_DEFAULT = "PERMIT_DENIED_DEFAULT"
    PERMIT_DENIED_MISSING_CURRENT_TURN_CONFIRMATION = (
        "PERMIT_DENIED_MISSING_CURRENT_TURN_CONFIRMATION"
    )
    PERMIT_DENIED_MISSING_OPERATOR_READINESS = (
        "PERMIT_DENIED_MISSING_OPERATOR_READINESS"
    )
    PERMIT_DENIED_SIDE_PROVENANCE_NOT_READY = (
        "PERMIT_DENIED_SIDE_PROVENANCE_NOT_READY"
    )
    PERMIT_DENIED_RETRY_OR_REPOST_CONTEXT = "PERMIT_DENIED_RETRY_OR_REPOST_CONTEXT"
    PERMIT_DENIED_ALREADY_CONSUMED = "PERMIT_DENIED_ALREADY_CONSUMED"
    PERMIT_GRANTED_EPHEMERAL_SETTLEMENT_ONE_SHOT = (
        "PERMIT_GRANTED_EPHEMERAL_SETTLEMENT_ONE_SHOT"
    )


@dataclass(frozen=True)
class GmoOfficialSettlementPostPermit:
    """Ephemeral, single-use, settlement-only permit. Never an allow-bridge."""

    status: GmoOfficialSettlementPostPermitStatus
    permit_granted: bool
    scope: str = SETTLEMENT_POST_PERMIT_SCOPE_SETTLEMENT_ONLY
    one_post_max: int = 1
    consumed: bool = False
    storable: bool = False
    reusable: bool = False
    entry_use_allowed: bool = False
    generic_close_use_allowed: bool = False
    cancel_use_allowed: bool = False
    change_use_allowed: bool = False
    retry_use_allowed: bool = False
    repost_use_allowed: bool = False
    second_post_use_allowed: bool = False
    hard_guard_allow_resolved: bool = False

    def __bool__(self) -> bool:
        return False

    @property
    def usable_for_one_settlement_post(self) -> bool:
        return (
            self.permit_granted
            and not self.consumed
            and self.scope == SETTLEMENT_POST_PERMIT_SCOPE_SETTLEMENT_ONLY
            and self.one_post_max == 1
            and not self.entry_use_allowed
            and not self.generic_close_use_allowed
            and not self.cancel_use_allowed
            and not self.change_use_allowed
            and not self.retry_use_allowed
            and not self.repost_use_allowed
            and not self.second_post_use_allowed
        )


def build_gmo_official_settlement_post_permit(
    *,
    operator_current_turn_exact_confirmation_present: bool,
    operator_readiness_present: bool,
    settlement_side_provenance_ready: bool,
    retry_or_repost_context: bool = False,
) -> GmoOfficialSettlementPostPermit:
    """Build a fail-closed ephemeral settlement permit from current-turn signals.

    All inputs describe THIS turn only. None are read from a file, history,
    docs, or a prior report by this function.
    """

    if retry_or_repost_context:
        return GmoOfficialSettlementPostPermit(
            status=(
                GmoOfficialSettlementPostPermitStatus
                .PERMIT_DENIED_RETRY_OR_REPOST_CONTEXT
            ),
            permit_granted=False,
        )
    if not operator_current_turn_exact_confirmation_present:
        return GmoOfficialSettlementPostPermit(
            status=(
                GmoOfficialSettlementPostPermitStatus
                .PERMIT_DENIED_MISSING_CURRENT_TURN_CONFIRMATION
            ),
            permit_granted=False,
        )
    if not operator_readiness_present:
        return GmoOfficialSettlementPostPermit(
            status=(
                GmoOfficialSettlementPostPermitStatus
                .PERMIT_DENIED_MISSING_OPERATOR_READINESS
            ),
            permit_granted=False,
        )
    if not settlement_side_provenance_ready:
        return GmoOfficialSettlementPostPermit(
            status=(
                GmoOfficialSettlementPostPermitStatus
                .PERMIT_DENIED_SIDE_PROVENANCE_NOT_READY
            ),
            permit_granted=False,
        )
    return GmoOfficialSettlementPostPermit(
        status=(
            GmoOfficialSettlementPostPermitStatus
            .PERMIT_GRANTED_EPHEMERAL_SETTLEMENT_ONE_SHOT
        ),
        permit_granted=True,
    )


def consume_gmo_official_settlement_post_permit(
    permit: GmoOfficialSettlementPostPermit,
) -> GmoOfficialSettlementPostPermit:
    """Consume a permit exactly once; the result can never authorize a POST."""

    return GmoOfficialSettlementPostPermit(
        status=GmoOfficialSettlementPostPermitStatus.PERMIT_DENIED_ALREADY_CONSUMED,
        permit_granted=False,
        consumed=True,
    )


class GmoOfficialSettlementPermitScopeError(ValueError):
    """Raised when a settlement permit is checked against a non-settlement scope."""


def assert_settlement_only_permit_scope(requested_scope: str) -> None:
    """Reject any attempt to use a settlement permit for a non-settlement scope."""

    normalized = requested_scope.strip().upper()
    if normalized in _FORBIDDEN_SETTLEMENT_PERMIT_SCOPES:
        raise GmoOfficialSettlementPermitScopeError(
            "settlement post permit is settlement-only and cannot be used "
            "for entry/generic/cancel/change scopes"
        )
    if normalized != SETTLEMENT_POST_PERMIT_SCOPE_SETTLEMENT_ONLY:
        raise GmoOfficialSettlementPermitScopeError(
            "unknown permit scope is rejected"
        )


@dataclass(frozen=True)
class OfficialSettlementExecutionActivation:
    """One-use, settlement-only activation. Never truthy; never carries secrets."""

    granted: bool
    denied_reason: str
    settlement_side_safe_label: str
    settlement_only: bool = True
    one_use: bool = True
    entry_allowed: bool = False
    generic_order_allowed: bool = False
    generic_close_allowed: bool = False
    position_specific_allowed: bool = False
    retry_allowed: bool = False
    repost_allowed: bool = False
    second_post_allowed: bool = False
    # Derived from ``granted`` by the factory; never a literal, never banked.
    grants_hard_guard_allow: bool = False

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return _SANITIZED_ACTIVATION_REPR

    def __str__(self) -> str:
        return _SANITIZED_ACTIVATION_REPR


def _denied_activation(reason: str) -> OfficialSettlementExecutionActivation:
    return OfficialSettlementExecutionActivation(
        granted=False,
        denied_reason=reason,
        settlement_side_safe_label="",
        grants_hard_guard_allow=False,
    )


def build_official_settlement_execution_activation(
    *,
    operator_input: OfficialSettlementOperatorCurrentTurnInput,
    settlement_preflight_ready: bool,
    fresh_runtime_one_position_gate_ready: bool,
    active_pending_clear_confirmed: bool,
    one_use_settlement_permit_usable: bool,
    hard_guard_controlled_supply_default_deny_present: bool,
    sanitized_preview_ready: bool,
    credential_presence_safe_boolean: bool,
    settlement_size_source_present_not_exposed: bool,
    official_settlement_route_ready: bool,
    market_open_safe_label_confirmed: bool,
    ticker_fresh_safe_label_confirmed: bool,
    spread_within_limit_safe_label_confirmed: bool,
) -> OfficialSettlementExecutionActivation:
    """Build a fail-closed one-use activation for exactly one settlement POST.

    Every argument describes the CURRENT actual step only (fresh values). No
    argument is read from a file, history, or prior report by this function,
    and nothing here is bankable across steps.
    """

    ok, provenance, reason = verify_official_settlement_operator_input(
        operator_input
    )
    if not ok:
        return _denied_activation(reason)

    gate_reasons: list[tuple[bool, str]] = [
        (settlement_preflight_ready, "SETTLEMENT_PREFLIGHT_NOT_READY"),
        (
            fresh_runtime_one_position_gate_ready,
            "FRESH_RUNTIME_ONE_POSITION_GATE_NOT_READY",
        ),
        (active_pending_clear_confirmed, "ACTIVE_PENDING_NOT_CLEAR"),
        (one_use_settlement_permit_usable, "SETTLEMENT_PERMIT_NOT_USABLE"),
        (
            hard_guard_controlled_supply_default_deny_present,
            "HARD_GUARD_CONTROLLED_SUPPLY_MISSING",
        ),
        (sanitized_preview_ready, "SANITIZED_PREVIEW_NOT_READY"),
        (credential_presence_safe_boolean, "CREDENTIAL_PRESENCE_NOT_CONFIRMED"),
        (
            settlement_size_source_present_not_exposed,
            "SETTLEMENT_SIZE_SOURCE_NOT_PRESENT",
        ),
        (official_settlement_route_ready, "OFFICIAL_SETTLEMENT_ROUTE_NOT_READY"),
        (market_open_safe_label_confirmed, "MARKET_OPEN_SAFE_LABEL_NOT_CONFIRMED"),
        (ticker_fresh_safe_label_confirmed, "TICKER_FRESH_SAFE_LABEL_NOT_CONFIRMED"),
        (
            spread_within_limit_safe_label_confirmed,
            "SPREAD_WITHIN_LIMIT_SAFE_LABEL_NOT_CONFIRMED",
        ),
    ]
    for satisfied, deny_reason in gate_reasons:
        if not satisfied:
            return _denied_activation(deny_reason)

    granted = True
    return OfficialSettlementExecutionActivation(
        granted=granted,
        denied_reason="",
        settlement_side_safe_label=provenance.settlement_side_safe_label,
        grants_hard_guard_allow=granted,
    )


@runtime_checkable
class OfficialSettlementOneShotSender(Protocol):
    """Injected at the actual settlement step only.

    A real implementation unseals the sealed credential internally, builds
    auth headers, performs exactly one HTTP POST to the dedicated official
    settlement endpoint, and returns ONLY a sanitized outcome category -- it
    never returns or logs a raw request/response, an ID, a size, a price, a
    P/L, or a credential.
    """

    def send_settlement_once_sanitized(
        self,
        *,
        method: str,
        path: str,
        body_json: str,
    ) -> SettlementPostSafeOutcome:
        """Send exactly one settlement order; return a sanitized outcome only."""


@dataclass
class FakeOfficialSettlementOneShotSender:
    """Test-only sender. Performs no network and exposes no raw/ID/value."""

    preset_outcome: SettlementPostSafeOutcome = (
        SettlementPostSafeOutcome.RESULT_UNKNOWN_SANITIZED
    )
    send_call_count: int = 0

    def send_settlement_once_sanitized(
        self,
        *,
        method: str,
        path: str,
        body_json: str,
    ) -> SettlementPostSafeOutcome:
        self.send_call_count += 1
        if self.send_call_count > 1:
            # A single-use flow must never call the sender twice.
            raise GmoOfficialSettlementExecutionBoundaryError(
                "sender invoked more than once (no retry/repost/second POST)"
            )
        return self.preset_outcome


@dataclass(frozen=True)
class RefusingOfficialSettlementOneShotSender:
    """Default-state sender proving no real send path is wired in this step."""

    def send_settlement_once_sanitized(
        self,
        *,
        method: str,
        path: str,
        body_json: str,
    ) -> SettlementPostSafeOutcome:
        raise GmoOfficialSettlementExecutionBoundaryError(
            "no real settlement sender is injected in the no-POST phase; a "
            "real sender is supplied only at the reviewed actual settlement "
            "execution step"
        )


@dataclass(frozen=True)
class OfficialSettlementExecutionResult:
    """Sanitized result only. Never raw/ID/value/credential."""

    outcome_category: SettlementPostSafeOutcome
    settlement_post_attempted: bool
    settlement_post_attempt_count: int
    retry_performed: bool = False
    repost_performed: bool = False
    second_post_performed: bool = False
    entry_post_performed: bool = False
    generic_close_performed: bool = False
    position_specific_settlement_performed: bool = False
    raw_response_exposed: bool = False
    raw_ids_exposed: bool = False
    raw_price_or_size_values_exposed: bool = False
    raw_profit_loss_values_exposed: bool = False
    credential_value_exposed: bool = False
    next_recommended_step: str = ""

    def __bool__(self) -> bool:
        return False


_NEXT_STEP_BY_OUTCOME = {
    SettlementPostSafeOutcome.RESULT_ACCEPTED_SANITIZED: (
        "POST_SETTLEMENT_READ_ONLY_NO_POSITION_CONFIRMATION_NO_POST"
    ),
}
_DEFAULT_NEXT_STEP = "REJECTED_OR_UNKNOWN_SAFE_REVIEW_NO_REPOST"


def send_official_settlement_post_once(
    *,
    activation: OfficialSettlementExecutionActivation,
    request_plan: GmoFxPrivateRequestPlan,
    sender: OfficialSettlementOneShotSender,
) -> OfficialSettlementExecutionResult:
    """The single reviewed actual-settlement call site. Sends at most once.

    Fail-closed before any send:
    - the activation must be granted, settlement-only, and not permit
      entry/generic/position-specific/retry/repost/second POST,
    - the request plan must be the dedicated OFFICIAL_SETTLEMENT plan (never
      an entry, generic, cancel, or change plan),
    - the shared real-broker-post hard guard must pass with ``allow`` derived
      solely from ``activation.granted``.

    On ANY outcome (accepted/rejected/unknown/timeout/network/client/server)
    it returns immediately. There is no retry, repost, or second-POST branch
    in this function at all.
    """

    if not activation.granted:
        return _blocked_result(activation.denied_reason or "ACTIVATION_NOT_GRANTED")
    if not activation.settlement_only or activation.entry_allowed:
        return _blocked_result("ACTIVATION_NOT_SETTLEMENT_ONLY")
    if (
        activation.generic_order_allowed
        or activation.generic_close_allowed
        or activation.position_specific_allowed
        or activation.retry_allowed
        or activation.repost_allowed
        or activation.second_post_allowed
    ):
        return _blocked_result("ACTIVATION_ALLOWS_FORBIDDEN_SCOPE")
    if request_plan.request_kind != REQUEST_KIND_OFFICIAL_SETTLEMENT:
        return _blocked_result("REQUEST_PLAN_NOT_OFFICIAL_SETTLEMENT_ONLY")
    try:
        validate_official_settlement_only_request_plan(request_plan)
    except GmoOfficialSettlementPreflightError:
        return _blocked_result("REQUEST_PLAN_NOT_OFFICIAL_SETTLEMENT_ONLY")

    try:
        assert_real_broker_post_allowed(allow=activation.grants_hard_guard_allow)
    except RealBrokerPostHardGuardError:
        return _blocked_result("HARD_GUARD_DENIED")

    # Exactly one send attempt; the attempt counts as 1 the moment it starts.
    outcome = sender.send_settlement_once_sanitized(
        method=request_plan.method,
        path=request_plan.path,
        body_json=request_plan.body_json,
    )
    return OfficialSettlementExecutionResult(
        outcome_category=outcome,
        settlement_post_attempted=True,
        settlement_post_attempt_count=1,
        next_recommended_step=_NEXT_STEP_BY_OUTCOME.get(outcome, _DEFAULT_NEXT_STEP),
    )


def _blocked_result(reason: str) -> OfficialSettlementExecutionResult:
    return OfficialSettlementExecutionResult(
        outcome_category=(
            SettlementPostSafeOutcome.RESULT_BLOCKED_BEFORE_POST_SANITIZED
        ),
        settlement_post_attempted=False,
        settlement_post_attempt_count=0,
        next_recommended_step=f"BLOCKED_SAFE_REVIEW_NO_POST:{reason}",
    )
