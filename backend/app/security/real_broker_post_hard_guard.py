"""Hard guard for the real broker POST boundary.

Incident context: an audit found that a small number of modules under
`app.live_verification` (the one-shot live order primitive,
`live_order_real_official_settlement_actual_transport_no_post_controlled`,
`live_order_real_one_shot_post_real_delegate_controlled`) contain genuine
httpx-based HTTP POST capability toward real GMO FX endpoints, separate from
the "Step 6G controlled/safe" simulation family. This module is the single
shared, default-deny checkpoint that each of those real-POST call sites must
pass immediately before touching the network.

This module intentionally lives outside `app.live_verification` (which
production broker/service code must never import) so that a future real
`GmoFxBroker` order-write path can depend on this checkpoint without
depending on the Step 6G controlled/simulation family.

This guard does not read environment variables or `.env`, does not accept or
inspect credential values, and does not accept or inspect request/response
content. It only evaluates one explicit boolean supplied by the caller for
that one call.
"""

from __future__ import annotations

from dataclasses import dataclass


class RealBrokerPostHardGuardError(RuntimeError):
    """Raised when a real broker POST is attempted without explicit allow."""


REAL_BROKER_POST_HARD_GUARD_ALLOWED_LABEL = "REAL_BROKER_POST_HARD_GUARD_ALLOWED_EXPLICIT"
REAL_BROKER_POST_HARD_GUARD_DENIED_LABEL = "REAL_BROKER_POST_HARD_GUARD_DENIED_DEFAULT"


@dataclass(frozen=True)
class RealBrokerPostHardGuardResult:
    safe_label: str
    allowed: bool


def assert_real_broker_post_allowed(*, allow: bool) -> RealBrokerPostHardGuardResult:
    """Default-deny checkpoint for the real broker POST boundary.

    `allow` must be the literal boolean `True`, supplied explicitly by the
    caller for this one call. Any other value — `False`, `None`, `0`, a
    truthy string, or anything derived from an environment variable or
    `.env` file — is denied. There is no environment-based unlock.
    """
    if allow is not True:
        raise RealBrokerPostHardGuardError(REAL_BROKER_POST_HARD_GUARD_DENIED_LABEL)
    return RealBrokerPostHardGuardResult(
        safe_label=REAL_BROKER_POST_HARD_GUARD_ALLOWED_LABEL,
        allowed=True,
    )
