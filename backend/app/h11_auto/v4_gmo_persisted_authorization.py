"""Opaque one-use proof backed by a committed v4 coordinator attempt."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable

from app.h11_auto.v4_gmo_contracts import V4GmoAction, V4GmoActionPlan
from app.h11_auto.v4_gmo_protection import V4GmoExactProtectionPlan

_ISSUER_TOKEN = object()


class V4PersistedAuthorizationError(RuntimeError):
    """Fixed safe persisted-authorization failure."""


class V4PersistedActionAuthorization:
    __slots__ = (
        "_token",
        "_plan_digest",
        "_protection_plan_digest",
        "_reconciliation_digest",
        "_deadline_monotonic",
        "_verify_committed",
        "_consumed",
    )

    def __init__(
        self,
        *,
        token: object,
        plan_digest: str,
        protection_plan_digest: str | None,
        reconciliation_digest: str | None,
        deadline_monotonic: float | None,
        verify_committed: Callable[[], bool],
    ) -> None:
        if token is not _ISSUER_TOKEN:
            raise V4PersistedAuthorizationError(
                "V4_PERSISTED_AUTHORIZATION_INVALID"
            )
        self._token = token
        self._plan_digest = plan_digest
        self._protection_plan_digest = protection_plan_digest
        self._reconciliation_digest = reconciliation_digest
        self._deadline_monotonic = deadline_monotonic
        self._verify_committed = verify_committed
        self._consumed = False

    def __repr__(self) -> str:
        return "V4PersistedActionAuthorization(<redacted-one-use-db-bound>)"

    def __bool__(self) -> bool:
        return False


def _issue_persisted_action_authorization(
    *,
    plan: V4GmoActionPlan,
    protection_plan_digest: str | None,
    reconciliation_digest: str | None,
    deadline_monotonic: float | None,
    verify_committed: Callable[[], bool],
) -> V4PersistedActionAuthorization:
    """Coordinator-only issuer; the verifier re-reads the committed DB row."""

    if not callable(verify_committed):
        raise V4PersistedAuthorizationError("V4_PERSISTED_AUTHORIZATION_INVALID")
    return V4PersistedActionAuthorization(
        token=_ISSUER_TOKEN,
        plan_digest=persisted_plan_digest(plan),
        protection_plan_digest=protection_plan_digest,
        reconciliation_digest=reconciliation_digest,
        deadline_monotonic=deadline_monotonic,
        verify_committed=verify_committed,
    )


def consume_persisted_action_authorization(
    authorization: V4PersistedActionAuthorization,
    *,
    plan: V4GmoActionPlan,
    protection_plan: V4GmoExactProtectionPlan | None,
    reconciliation_digest: str | None,
    now_monotonic: float,
) -> None:
    """Exact-match, DB-reverify, and consume immediately before transport."""

    if (
        not isinstance(authorization, V4PersistedActionAuthorization)
        or getattr(authorization, "_token", None) is not _ISSUER_TOKEN
        or authorization._consumed
        or authorization._plan_digest != persisted_plan_digest(plan)
        or authorization._reconciliation_digest != reconciliation_digest
        or not _valid_monotonic(now_monotonic)
    ):
        raise V4PersistedAuthorizationError("V4_PERSISTED_AUTHORIZATION_INVALID")
    if plan.action is V4GmoAction.EXACT_SIZE_OCO_PROTECTION:
        if (
            protection_plan is None
            or authorization._protection_plan_digest
            != "sha256:" + protection_plan.plan_digest
            or authorization._deadline_monotonic is None
            or now_monotonic > authorization._deadline_monotonic
        ):
            raise V4PersistedAuthorizationError(
                "V4_PERSISTED_PROTECTION_AUTHORIZATION_INVALID"
            )
    elif authorization._protection_plan_digest is not None:
        raise V4PersistedAuthorizationError("V4_PERSISTED_AUTHORIZATION_INVALID")
    try:
        committed = authorization._verify_committed()
    except Exception as error:
        raise V4PersistedAuthorizationError(
            "V4_PERSISTED_COMMIT_REVERIFY_FAILED"
        ) from error
    if committed is not True:
        raise V4PersistedAuthorizationError(
            "V4_PERSISTED_COMMIT_REVERIFY_FAILED"
        )
    authorization._consumed = True


def persisted_plan_digest(plan: V4GmoActionPlan) -> str:
    canonical = json.dumps(
        {
            "action": plan.action.value,
            "cycle_ref": plan.cycle_ref,
            "protection_contract_hash": plan.protection_contract_hash,
            "requested_size": plan.requested_size,
            "route_safe_label": plan.route_safe_label,
            "side": plan.side.value,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _valid_monotonic(value: float) -> bool:
    return isinstance(value, int | float) and math.isfinite(value) and value >= 0
