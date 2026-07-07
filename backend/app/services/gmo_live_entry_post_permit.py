"""No-POST ephemeral entry POST permit model for GMO live execution.

This models the ephemeral, single-use permit that a future controlled
actual-POST gate would require immediately before an entry order. It is
deliberately incapable of unlocking anything by itself:

- The permit is entry-only. It is never valid for settlement, close, cancel,
  or change. Those scopes are rejected structurally.
- The permit is one-POST-max and single-use: once consumed it cannot be
  reused, and it is not storable/bankable across turns.
- It is granted only from an ephemeral current-turn operator confirmation
  for a concrete ENTRY_BUY / ENTRY_SELL signal; HOLD, missing confirmation,
  or missing readiness all fail closed.
- It NEVER resolves the real-broker-post hard guard to ``allow=True``.
  ``hard_guard_allow_resolved`` is hardcoded false: wiring a granted permit
  to an actual ``allow=True`` remains a separate, explicitly reviewed
  controlled step and is intentionally not done here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

ENTRY_POST_PERMIT_SCOPE_ENTRY_ONLY = "ENTRY_ONLY"

_FORBIDDEN_PERMIT_SCOPES = frozenset(
    {"SETTLEMENT", "CLOSE", "CLOSEORDER", "CANCEL", "CANCELORDERS", "CHANGE", "CHANGEORDER"}
)


class GmoEntryPostPermitStatus(str, Enum):
    PERMIT_DENIED_DEFAULT = "PERMIT_DENIED_DEFAULT"
    PERMIT_DENIED_MISSING_CURRENT_TURN_CONFIRMATION = (
        "PERMIT_DENIED_MISSING_CURRENT_TURN_CONFIRMATION"
    )
    PERMIT_DENIED_MISSING_OPERATOR_READINESS = (
        "PERMIT_DENIED_MISSING_OPERATOR_READINESS"
    )
    PERMIT_DENIED_SIGNAL_NOT_ENTRY = "PERMIT_DENIED_SIGNAL_NOT_ENTRY"
    PERMIT_DENIED_RETRY_OR_REPOST_CONTEXT = "PERMIT_DENIED_RETRY_OR_REPOST_CONTEXT"
    PERMIT_DENIED_ALREADY_CONSUMED = "PERMIT_DENIED_ALREADY_CONSUMED"
    PERMIT_GRANTED_EPHEMERAL_ENTRY_ONE_SHOT = (
        "PERMIT_GRANTED_EPHEMERAL_ENTRY_ONE_SHOT"
    )


@dataclass(frozen=True)
class GmoEntryPostPermit:
    """Ephemeral, single-use, entry-only permit. Never an allow-bridge."""

    status: GmoEntryPostPermitStatus
    permit_granted: bool
    scope: str = ENTRY_POST_PERMIT_SCOPE_ENTRY_ONLY
    one_post_max: int = 1
    consumed: bool = False
    storable: bool = False
    reusable: bool = False
    settlement_use_allowed: bool = False
    close_use_allowed: bool = False
    cancel_use_allowed: bool = False
    change_use_allowed: bool = False
    retry_use_allowed: bool = False
    repost_use_allowed: bool = False
    second_post_use_allowed: bool = False
    hard_guard_allow_resolved: bool = False

    def __bool__(self) -> bool:
        return False

    @property
    def usable_for_one_entry_post(self) -> bool:
        return (
            self.permit_granted
            and not self.consumed
            and self.scope == ENTRY_POST_PERMIT_SCOPE_ENTRY_ONLY
            and self.one_post_max == 1
            and not self.settlement_use_allowed
            and not self.close_use_allowed
            and not self.cancel_use_allowed
            and not self.change_use_allowed
            and not self.retry_use_allowed
            and not self.repost_use_allowed
            and not self.second_post_use_allowed
        )


def build_gmo_entry_post_permit(
    *,
    operator_current_turn_exact_confirmation_present: bool,
    operator_readiness_present: bool,
    operator_signal_is_entry_buy_or_sell: bool,
    retry_or_repost_context: bool = False,
) -> GmoEntryPostPermit:
    """Build a fail-closed ephemeral entry permit from current-turn signals.

    All inputs describe THIS turn only. None are read from a file, history,
    docs, or a prior report by this function.
    """

    if retry_or_repost_context:
        return GmoEntryPostPermit(
            status=GmoEntryPostPermitStatus.PERMIT_DENIED_RETRY_OR_REPOST_CONTEXT,
            permit_granted=False,
        )
    if not operator_current_turn_exact_confirmation_present:
        return GmoEntryPostPermit(
            status=(
                GmoEntryPostPermitStatus.PERMIT_DENIED_MISSING_CURRENT_TURN_CONFIRMATION
            ),
            permit_granted=False,
        )
    if not operator_readiness_present:
        return GmoEntryPostPermit(
            status=GmoEntryPostPermitStatus.PERMIT_DENIED_MISSING_OPERATOR_READINESS,
            permit_granted=False,
        )
    if not operator_signal_is_entry_buy_or_sell:
        return GmoEntryPostPermit(
            status=GmoEntryPostPermitStatus.PERMIT_DENIED_SIGNAL_NOT_ENTRY,
            permit_granted=False,
        )
    return GmoEntryPostPermit(
        status=GmoEntryPostPermitStatus.PERMIT_GRANTED_EPHEMERAL_ENTRY_ONE_SHOT,
        permit_granted=True,
    )


def consume_gmo_entry_post_permit(permit: GmoEntryPostPermit) -> GmoEntryPostPermit:
    """Consume a granted permit exactly once.

    A consumed permit is returned with ``permit_granted=False`` and
    ``consumed=True`` so it can never be reused for a second POST. Consuming
    an already-consumed or ungranted permit yields an explicit denied state.
    """

    if not permit.usable_for_one_entry_post:
        return GmoEntryPostPermit(
            status=GmoEntryPostPermitStatus.PERMIT_DENIED_ALREADY_CONSUMED,
            permit_granted=False,
            consumed=True,
        )
    return GmoEntryPostPermit(
        status=GmoEntryPostPermitStatus.PERMIT_DENIED_ALREADY_CONSUMED,
        permit_granted=False,
        consumed=True,
    )


class GmoEntryPostPermitScopeError(ValueError):
    """Raised when a permit is checked against a non-entry scope."""


def assert_entry_only_permit_scope(requested_scope: str) -> None:
    """Reject any attempt to use an entry permit for a non-entry scope."""

    normalized = requested_scope.strip().upper()
    if normalized in _FORBIDDEN_PERMIT_SCOPES:
        raise GmoEntryPostPermitScopeError(
            "entry post permit is entry-only and cannot be used for "
            "settlement/close/cancel/change scopes"
        )
    if normalized != ENTRY_POST_PERMIT_SCOPE_ENTRY_ONLY:
        raise GmoEntryPostPermitScopeError("unknown permit scope is rejected")
