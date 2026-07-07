"""Actual entry execution boundary (no-POST implementation, injection-gated).

This module implements the single reviewed call site through which a FUTURE
actual entry POST step could send exactly one entry order -- without this
module ever touching the network, reading a credential value, or exposing a
raw request/response, an ID, or a broker value.

The three sensitive capabilities are injection points, never implemented
here:

- the real one-shot HTTP send,
- the sealed credential unseal, and
- the auth-header build,

all live inside an injected ``ActualEntryOneShotSender`` that the caller
supplies only at the actual execution step. This module ships only a fake
sender (for tests) and a refusing sender (proving the default state cannot
send). No module-level code constructs a real sender, so this step performs
zero POSTs and zero network calls.

Fail-closed guarantees enforced here:

- The activation is granted only when EVERY gate input is satisfied, is
  entry-only, single-use, and never grants settlement/close/retry/repost.
- ``send_actual_entry_post_once`` calls the shared real-broker-post hard
  guard exactly once, deriving ``allow`` from ``activation.granted`` (no
  literal allow, no reusable allow bridge), invokes the injected sender
  exactly once, and never resends on any outcome.
- Only sanitized ``EntryPostSafeOutcome`` categories cross this boundary.
  There is no field carrying a raw request/response, an ID, a size, a price,
  a P/L, or a credential.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from app.private_api.order_builders import (
    REQUEST_KIND_ENTRY,
    GmoFxPrivateRequestPlan,
)
from app.security.real_broker_post_hard_guard import (
    RealBrokerPostHardGuardError,
    assert_real_broker_post_allowed,
)

# Exact current-turn operator labels required for an executable entry.
REQUIRED_ENTRY_EXACT_CONFIRMATION = (
    "CONFIRM_ONE_ENTRY_POST_MAX_NO_RETRY_NO_REPOST_NO_SETTLEMENT"
)
REQUIRED_ENTRY_READINESS = "OPERATOR_READY_FOR_ONE_ENTRY_POST_MAX_NO_RETRY_NO_REPOST"
REQUIRED_ENTRY_UNDERSTANDS_RISK = "OPERATOR_ACKNOWLEDGES_ACTUAL_BROKER_WRITE_RISK"

# HOLD is intentionally absent: it is never executable.
_EXECUTABLE_SIGNAL_TO_ACTION = {
    "ENTRY_BUY": "ENTRY_OPEN_BUY",
    "ENTRY_SELL": "ENTRY_OPEN_SELL",
}

_SANITIZED_ACTIVATION_REPR = "ActualEntryExecutionActivation(<sanitized>)"


class ActualEntryExecutionBoundaryError(RuntimeError):
    """Raised for fail-closed violations. Never carries a body/ID/value."""


class EntryPostSafeOutcome(str, Enum):
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
class ActualEntryOperatorCurrentTurnInput:
    """Current-turn operator labels. Not banked; supplied per actual step."""

    signal_type_safe_label: str
    exact_confirmation: str
    readiness: str
    understands_risk: str


def verify_actual_entry_operator_input(
    operator_input: ActualEntryOperatorCurrentTurnInput,
) -> tuple[bool, str, str]:
    """Return (ok, order_action_safe_label, reason). AI never decides side."""

    if operator_input.exact_confirmation != REQUIRED_ENTRY_EXACT_CONFIRMATION:
        return (False, "", "OPERATOR_EXACT_CONFIRMATION_MISMATCH")
    if operator_input.readiness != REQUIRED_ENTRY_READINESS:
        return (False, "", "OPERATOR_READINESS_MISMATCH")
    if operator_input.understands_risk != REQUIRED_ENTRY_UNDERSTANDS_RISK:
        return (False, "", "OPERATOR_UNDERSTANDS_RISK_MISMATCH")
    action = _EXECUTABLE_SIGNAL_TO_ACTION.get(operator_input.signal_type_safe_label)
    if action is None:
        # HOLD or any non-executable/unknown label is never turned into a POST.
        return (False, "", "OPERATOR_SIGNAL_NOT_EXECUTABLE")
    return (True, action, "OPERATOR_INPUT_VERIFIED")


@dataclass(frozen=True)
class ActualEntryExecutionActivation:
    """One-use, entry-only activation. Never truthy; never carries secrets/IDs."""

    granted: bool
    denied_reason: str
    order_action_safe_label: str
    entry_only: bool = True
    one_use: bool = True
    settlement_allowed: bool = False
    close_allowed: bool = False
    generic_order_allowed: bool = False
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


def _denied_activation(reason: str) -> ActualEntryExecutionActivation:
    return ActualEntryExecutionActivation(
        granted=False,
        denied_reason=reason,
        order_action_safe_label="",
        grants_hard_guard_allow=False,
    )


def build_actual_entry_execution_activation(
    *,
    operator_input: ActualEntryOperatorCurrentTurnInput,
    final_preflight_ready: bool,
    fresh_runtime_gate_ready: bool,
    written_signoff_recorded: bool,
    paper_evidence_confirmed: bool,
    anomaly_evidence_confirmed: bool,
    one_use_entry_permit_usable: bool,
    hard_guard_controlled_supply_default_deny_present: bool,
    sanitized_preview_ready: bool,
    credential_presence_safe_boolean: bool,
) -> ActualEntryExecutionActivation:
    """Build a fail-closed one-use activation for exactly one entry POST.

    Every argument describes the CURRENT actual step only (fresh values). No
    argument is read from a file, history, or prior report by this function,
    and nothing here is bankable across steps.
    """

    ok, action, reason = verify_actual_entry_operator_input(operator_input)
    if not ok:
        return _denied_activation(reason)

    gate_reasons: list[tuple[bool, str]] = [
        (final_preflight_ready, "FINAL_PREFLIGHT_NOT_READY"),
        (fresh_runtime_gate_ready, "FRESH_RUNTIME_GATE_NOT_READY"),
        (written_signoff_recorded, "WRITTEN_SIGNOFF_NOT_RECORDED"),
        (paper_evidence_confirmed, "PAPER_EVIDENCE_NOT_CONFIRMED"),
        (anomaly_evidence_confirmed, "ANOMALY_EVIDENCE_NOT_CONFIRMED"),
        (one_use_entry_permit_usable, "ENTRY_PERMIT_NOT_USABLE"),
        (
            hard_guard_controlled_supply_default_deny_present,
            "HARD_GUARD_CONTROLLED_SUPPLY_MISSING",
        ),
        (sanitized_preview_ready, "SANITIZED_PREVIEW_NOT_READY"),
        (credential_presence_safe_boolean, "CREDENTIAL_PRESENCE_NOT_CONFIRMED"),
    ]
    for satisfied, deny_reason in gate_reasons:
        if not satisfied:
            return _denied_activation(deny_reason)

    granted = True
    return ActualEntryExecutionActivation(
        granted=granted,
        denied_reason="",
        order_action_safe_label=action,
        grants_hard_guard_allow=granted,
    )


@runtime_checkable
class ActualEntryOneShotSender(Protocol):
    """Injected at the actual step only.

    A real implementation unseals the sealed credential internally, builds
    auth headers, performs exactly one HTTP POST to the entry endpoint, and
    returns ONLY a sanitized outcome category -- it never returns or logs a
    raw request/response, an ID, a size, a price, a P/L, or a credential.
    """

    def send_entry_once_sanitized(
        self,
        *,
        method: str,
        path: str,
        body_json: str,
    ) -> EntryPostSafeOutcome:
        """Send exactly one entry order and return a sanitized outcome only."""


@dataclass
class FakeActualEntryOneShotSender:
    """Test-only sender. Performs no network and exposes no raw/ID/value."""

    preset_outcome: EntryPostSafeOutcome = EntryPostSafeOutcome.RESULT_UNKNOWN_SANITIZED
    send_call_count: int = 0

    def send_entry_once_sanitized(
        self,
        *,
        method: str,
        path: str,
        body_json: str,
    ) -> EntryPostSafeOutcome:
        self.send_call_count += 1
        if self.send_call_count > 1:
            # A single-use flow must never call the sender twice.
            raise ActualEntryExecutionBoundaryError(
                "sender invoked more than once (no retry/repost/second POST)"
            )
        return self.preset_outcome


@dataclass(frozen=True)
class RefusingActualEntryOneShotSender:
    """Default-state sender proving no real send path is wired in this step."""

    def send_entry_once_sanitized(
        self,
        *,
        method: str,
        path: str,
        body_json: str,
    ) -> EntryPostSafeOutcome:
        raise ActualEntryExecutionBoundaryError(
            "no real entry sender is injected in the no-POST phase; a real "
            "sender is supplied only at the reviewed actual execution step"
        )


@dataclass(frozen=True)
class ActualEntryExecutionResult:
    """Sanitized result only. Never raw/ID/value/credential."""

    outcome_category: EntryPostSafeOutcome
    post_attempted: bool
    post_attempt_count: int
    retry_performed: bool = False
    repost_performed: bool = False
    second_post_performed: bool = False
    settlement_post_performed: bool = False
    generic_close_performed: bool = False
    raw_response_exposed: bool = False
    raw_ids_exposed: bool = False
    raw_price_or_size_values_exposed: bool = False
    credential_value_exposed: bool = False
    next_recommended_step: str = ""

    def __bool__(self) -> bool:
        return False


_NEXT_STEP_BY_OUTCOME = {
    EntryPostSafeOutcome.RESULT_ACCEPTED_SANITIZED: (
        "POST_ENTRY_READ_ONLY_POSITION_CONFIRMATION_NO_POST"
    ),
}
_DEFAULT_NEXT_STEP = "REJECTED_OR_UNKNOWN_SAFE_REVIEW_NO_REPOST"


def send_actual_entry_post_once(
    *,
    activation: ActualEntryExecutionActivation,
    request_plan: GmoFxPrivateRequestPlan,
    sender: ActualEntryOneShotSender,
) -> ActualEntryExecutionResult:
    """The single reviewed actual-entry call site. Sends at most once.

    Fail-closed before any send:
    - the activation must be granted, entry-only, and not permit
      settlement/close/generic/retry/repost/second POST,
    - the request plan must be the dedicated ENTRY plan (never a settlement,
      close, cancel, or change plan),
    - the shared real-broker-post hard guard must pass with ``allow`` derived
      solely from ``activation.granted``.

    On ANY outcome (accepted/rejected/unknown/timeout/network/client/server)
    it returns immediately. There is no retry, repost, or second-POST branch
    in this function at all.
    """

    if not activation.granted:
        return _blocked_result(activation.denied_reason or "ACTIVATION_NOT_GRANTED")
    if not activation.entry_only or activation.settlement_allowed:
        return _blocked_result("ACTIVATION_NOT_ENTRY_ONLY")
    if (
        activation.close_allowed
        or activation.generic_order_allowed
        or activation.retry_allowed
        or activation.repost_allowed
        or activation.second_post_allowed
    ):
        return _blocked_result("ACTIVATION_ALLOWS_FORBIDDEN_SCOPE")
    if request_plan.request_kind != REQUEST_KIND_ENTRY:
        return _blocked_result("REQUEST_PLAN_NOT_ENTRY_ONLY")

    try:
        assert_real_broker_post_allowed(allow=activation.grants_hard_guard_allow)
    except RealBrokerPostHardGuardError:
        return _blocked_result("HARD_GUARD_DENIED")

    # Exactly one send attempt; the attempt counts as 1 the moment it starts.
    outcome = sender.send_entry_once_sanitized(
        method=request_plan.method,
        path=request_plan.path,
        body_json=request_plan.body_json,
    )
    return ActualEntryExecutionResult(
        outcome_category=outcome,
        post_attempted=True,
        post_attempt_count=1,
        next_recommended_step=_NEXT_STEP_BY_OUTCOME.get(outcome, _DEFAULT_NEXT_STEP),
    )


def _blocked_result(reason: str) -> ActualEntryExecutionResult:
    return ActualEntryExecutionResult(
        outcome_category=EntryPostSafeOutcome.RESULT_BLOCKED_BEFORE_POST_SANITIZED,
        post_attempted=False,
        post_attempt_count=0,
        next_recommended_step=f"BLOCKED_SAFE_REVIEW_NO_POST:{reason}",
    )
