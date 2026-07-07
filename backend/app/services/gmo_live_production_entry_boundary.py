"""Fail-closed production entry boundary for the four remaining code blockers.

This module resolves, in a strictly no-POST form, the structural side of the
four code blockers that stand between the assembled final preflight package
and a future actual entry POST step:

1. Production real entry transport: ``DisabledProductionEntryTransport``
   composes the request-plan safe summary, sanitized preview, sealed
   credential box, one-use entry permit, and the hard-guard controlled
   supply. Its send method ALWAYS raises in this repository state: an
   activation object is required and ``ProductionEntryTransportActivation``
   cannot be constructed at all in the no-POST phase.
2. Sealed credential real operation: ``SealedSecretBox`` can hold a sealed
   token without ever exposing it -- ``repr``/``str`` never contain the
   token, there is no length/hash/fingerprint/prefix/suffix accessor, and
   unsealing always raises outside the (not yet existing) actual execution
   boundary. This module never reads the process environment or dotenv.
3. Runtime safe read real connection: a pure adapter maps the sanitized
   summary of the audited read-only connection check script onto the
   existing ``GmoRuntimeSafeReadSnapshot`` model. No network call happens
   here; executing a fresh read stays behind the read-only operator gate.
4. Hard guard allow controlled supply: ``HardGuardAllowControlledSupply``
   is default-deny and structurally cannot carry a resolved allow in this
   phase -- constructing it with a truthy resolved allow raises. Per the
   allow-bridge rejection record, nothing here computes an allow from
   booleans; the actual step passes its one explicit literal at the single
   reviewed call site under the operator gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.private_api.order_builders import (
    REQUEST_KIND_ENTRY,
    GmoFxPrivateRequestPlanSafeSummary,
)
from app.services.gmo_live_entry_post_permit import GmoEntryPostPermit
from app.services.gmo_live_entry_transport import GmoEntryPostSanitizedPreview
from app.services.gmo_live_runtime_safe_read import (
    GmoRuntimeActivePendingSafeStatus,
    GmoRuntimeMarketSafeStatus,
    GmoRuntimePositionSafeStatus,
    GmoRuntimeSafeReadSnapshot,
    GmoRuntimeSpreadSafeStatus,
    GmoRuntimeTickerFreshnessSafeStatus,
)

_SEALED_REPR = "SealedSecretBox(sealed; value never exposed)"


class GmoProductionEntryBoundaryError(RuntimeError):
    """Raised whenever this boundary is asked to act beyond the no-POST phase.

    The message never carries a credential, token, raw request/response, ID,
    or broker value.
    """


class SealedSecretBox:
    """Sealed credential holder that can never expose what it holds.

    - ``repr``/``str`` are fixed and never include the token.
    - There is no accessor for the value, its length, hash, fingerprint,
      prefix, or suffix.
    - ``unseal_inside_actual_execution_boundary`` always raises in the
      no-POST phase; the actual execution boundary that may call it does not
      exist yet and will be added only in the explicitly reviewed actual
      step.

    Tests must construct this only with synthetic placeholder tokens.
    """

    __slots__ = ("_sealed_token", "_present")

    def __init__(self, sealed_token: str | None = None) -> None:
        self._sealed_token = sealed_token
        self._present = bool(sealed_token)

    def presence_safe_boolean(self) -> bool:
        return self._present

    def unseal_inside_actual_execution_boundary(self) -> None:
        raise GmoProductionEntryBoundaryError(
            "sealed credential unseal is forbidden in the no-POST phase; the "
            "actual execution boundary does not exist yet"
        )

    def __repr__(self) -> str:
        return _SEALED_REPR

    def __str__(self) -> str:
        return _SEALED_REPR

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class HardGuardAllowControlledSupply:
    """Default-deny supply for the real-broker-post hard guard.

    ``resolved_allow`` must stay false: a truthy value raises at
    construction, so this type structurally cannot transport a resolved
    allow in this phase. It is NOT an allow bridge -- it never computes an
    allow from other booleans. In the actual step, the one explicit literal
    is passed directly at the single reviewed hard-guard call site under the
    operator current-turn gate, not through this object.
    """

    resolved_allow: bool = False
    supply_source_safe_label: str = "DEFAULT_DENY_NO_POST_STEP"
    allow_bridge_present: bool = False

    def __post_init__(self) -> None:
        if self.resolved_allow:
            raise GmoProductionEntryBoundaryError(
                "hard guard controlled supply cannot carry a resolved allow "
                "in the no-POST phase"
            )
        if self.allow_bridge_present:
            raise GmoProductionEntryBoundaryError(
                "allow bridge is rejected by the incident record and cannot "
                "be marked present"
            )

    def __bool__(self) -> bool:
        return False


def build_hard_guard_allow_controlled_supply_default_deny() -> (
    HardGuardAllowControlledSupply
):
    """The only builder in this phase; always default-deny."""

    return HardGuardAllowControlledSupply()


class ProductionEntryTransportActivation:
    """Activation token required by the production entry transport send path.

    Deliberately unconstructible in the no-POST phase: instantiating it
    raises. The actual execution step introduces its reviewed construction
    path together with the operator current-turn exact confirmation gate.
    """

    def __init__(self) -> None:
        raise GmoProductionEntryBoundaryError(
            "production entry transport activation is not constructible in "
            "the no-POST phase; it belongs to the actual execution step only"
        )


@dataclass(frozen=True)
class DisabledProductionEntryTransport:
    """Production entry transport, implemented but disabled (fail-closed).

    Entry-only by construction: a non-entry request plan is rejected before
    anything else. ``is_real_transport`` is true so the existing fake-only
    entry state machine refuses to drive it. The send path requires an
    activation object that cannot exist in this phase, and even then the
    hard-guard controlled supply is structurally deny -- so sending is
    impossible here by at least two independent layers. There is no retry,
    repost, or second-POST path: the single method raises.
    """

    plan_safe_summary: GmoFxPrivateRequestPlanSafeSummary
    sanitized_preview: GmoEntryPostSanitizedPreview
    sealed_credential: SealedSecretBox
    permit: GmoEntryPostPermit
    hard_guard_supply: HardGuardAllowControlledSupply
    activation: ProductionEntryTransportActivation | None = None
    is_real_transport: bool = True

    def send_entry_order_sanitized(self) -> None:
        if self.plan_safe_summary.request_kind != REQUEST_KIND_ENTRY:
            raise GmoProductionEntryBoundaryError(
                "production entry transport is entry-only: settlement/close/"
                "cancel/change request kinds are structurally rejected"
            )
        if not isinstance(self.activation, ProductionEntryTransportActivation):
            raise GmoProductionEntryBoundaryError(
                "production entry transport is disabled: no activation exists "
                "in the no-POST phase and no send is possible"
            )
        # Unreachable in this phase (activation cannot be constructed), and
        # kept fail-closed even if that ever changed: the controlled supply
        # is structurally deny and the shared hard guard would still refuse.
        raise GmoProductionEntryBoundaryError(
            "production entry transport send is not enabled: hard guard "
            "controlled supply is deny and the actual execution step gate "
            "is not satisfied"
        )

    def __bool__(self) -> bool:
        return False


_POSITION_STATUS_BY_COUNT = {
    0: GmoRuntimePositionSafeStatus.NO_POSITION,
    1: GmoRuntimePositionSafeStatus.ONE_POSITION_OPEN,
}

_CONNECTION_SUCCESS = "success"


def build_gmo_runtime_safe_read_snapshot_from_sanitized_connection_summary(
    *,
    connection_result: str,
    open_positions_count: int | None,
    active_orders_count: int | None,
    fresh: bool,
    market_open: bool | None = None,
    ticker_fresh: bool | None = None,
    spread_within_limit: bool | None = None,
) -> GmoRuntimeSafeReadSnapshot:
    """Map the audited read-only check's sanitized summary to a safe snapshot.

    Pure function: no network, no credentials. Inputs are exactly the safe
    fields the audited ``check_private_readonly_connection`` script prints
    (result labels and counts), plus optional public-market safe booleans.
    Anything missing or non-successful degrades to UNKNOWN, which the
    existing runtime safe-read gate treats as a blocker (fail-closed).
    """

    succeeded = connection_result == _CONNECTION_SUCCESS
    if not succeeded:
        return GmoRuntimeSafeReadSnapshot(performed=False, fresh=False)

    if open_positions_count is None:
        position_status = GmoRuntimePositionSafeStatus.UNKNOWN
    elif open_positions_count < 0:
        position_status = GmoRuntimePositionSafeStatus.UNKNOWN
    else:
        position_status = _POSITION_STATUS_BY_COUNT.get(
            open_positions_count, GmoRuntimePositionSafeStatus.MULTIPLE_POSITIONS
        )

    if active_orders_count is None or active_orders_count < 0:
        active_status = GmoRuntimeActivePendingSafeStatus.UNKNOWN
    elif active_orders_count == 0:
        active_status = GmoRuntimeActivePendingSafeStatus.CLEAR
    else:
        active_status = GmoRuntimeActivePendingSafeStatus.CONFLICT

    def _tri(value: bool | None, yes: object, no: object, unknown: object) -> object:
        if value is None:
            return unknown
        return yes if value else no

    market_status = _tri(
        market_open,
        GmoRuntimeMarketSafeStatus.OPEN,
        GmoRuntimeMarketSafeStatus.CLOSED,
        GmoRuntimeMarketSafeStatus.UNKNOWN,
    )
    ticker_status = _tri(
        ticker_fresh,
        GmoRuntimeTickerFreshnessSafeStatus.FRESH,
        GmoRuntimeTickerFreshnessSafeStatus.STALE,
        GmoRuntimeTickerFreshnessSafeStatus.UNKNOWN,
    )
    spread_status = _tri(
        spread_within_limit,
        GmoRuntimeSpreadSafeStatus.WITHIN_LIMIT,
        GmoRuntimeSpreadSafeStatus.OUT_OF_LIMIT,
        GmoRuntimeSpreadSafeStatus.UNKNOWN,
    )

    return GmoRuntimeSafeReadSnapshot(
        performed=True,
        fresh=fresh,
        position_status=position_status,
        position_count_safe=(
            open_positions_count
            if open_positions_count is not None and open_positions_count >= 0
            else None
        ),
        active_pending_status=active_status,
        active_order_count_safe=(
            active_orders_count
            if active_orders_count is not None and active_orders_count >= 0
            else None
        ),
        market_status=market_status,  # type: ignore[arg-type]
        ticker_status=ticker_status,  # type: ignore[arg-type]
        spread_status=spread_status,  # type: ignore[arg-type]
    )
