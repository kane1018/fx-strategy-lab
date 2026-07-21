"""Typed H-11 GMO relaxed v4 adapter with fake-first execution tests.

The adapter maps the frozen v4 actions to the six permitted GMO Private API
routes and converts three authoritative GET responses into the existing safe
``V4GmoBrokerSnapshot``.  Broker identifiers exist only inside redacted,
in-memory objects.  They are never returned in safe results or persisted.

No transport is selected here.  The caller must inject a transport; the real
httpx transport remains activation-gated in ``h11_v4_gmo_actual_transport``.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from enum import Enum
from typing import Any

from app.h11_auto.contracts import SignalDecision
from app.h11_auto.v4_activation_preparation import (
    v4_reconciliation_get_offsets_seconds,
)
from app.h11_auto.v4_gmo_contracts import (
    V4GmoAction,
    V4GmoActionPlan,
    V4GmoBrokerSnapshot,
    V4GmoEntryStatus,
    V4GmoProtectionStatus,
)
from app.h11_auto.v4_gmo_persisted_authorization import (
    V4PersistedActionAuthorization,
    consume_persisted_action_authorization,
)
from app.h11_auto.v4_gmo_protection import V4GmoExactProtectionPlan
from app.services.h11_v4_gmo_actual_transport import (
    V4_GMO_SURFACEABLE_FAILURE_CLASSES,
    V4GmoActualTransportError,
    V4GmoPrivateEnvelope,
    V4GmoPrivateRequest,
    V4GmoPrivateTransport,
    v4_gmo_private_request_binding_digest,
)
from app.services.h11_v4_gmo_public_market_status import (
    V4GmoPublicMarketStatusError,
    V4GmoPublicMarketStatusTransportGuard,
)

SYMBOL = "USD_JPY"
LATEST_EXECUTIONS_TRANSPORT_PATH = "/private/v1/latestExecutions"
OPEN_POSITIONS_TRANSPORT_PATH = "/private/v1/openPositions"
ACTIVE_ORDERS_TRANSPORT_PATH = "/private/v1/activeOrders"
ORDER_TRANSPORT_PATH = "/private/v1/order"
CANCEL_TRANSPORT_PATH = "/private/v1/cancelOrders"
CLOSE_ORDER_TRANSPORT_PATH = "/private/v1/closeOrder"


class V4GmoActualAdapterError(RuntimeError):
    """Safe adapter failure containing fixed labels only."""


class V4GmoPrivateOutcome(str, Enum):
    ACCEPTED_SANITIZED = "ACCEPTED_SANITIZED"
    REJECTED_SANITIZED = "REJECTED_SANITIZED"
    UNKNOWN_SANITIZED = "UNKNOWN_SANITIZED"


@dataclass(frozen=True, repr=False)
class _PositionPart:
    position_id: str
    size: int

    def __repr__(self) -> str:
        return "_PositionPart(<redacted>)"


@dataclass(frozen=True, repr=False)
class V4GmoPositionBundle:
    """Ephemeral position identifiers linked from owned entry executions."""

    _parts: tuple[_PositionPart, ...]

    def __post_init__(self) -> None:
        if not self._parts or len(self._parts) > 10:
            raise V4GmoActualAdapterError("V4_GMO_POSITION_BUNDLE_SIZE_INVALID")
        if any(not part.position_id or part.size <= 0 for part in self._parts):
            raise V4GmoActualAdapterError("V4_GMO_POSITION_BUNDLE_INVALID")

    @property
    def total_size(self) -> int:
        return sum(part.size for part in self._parts)

    def _settle_positions_for_internal_request(self) -> list[dict[str, object]]:
        return [
            {"positionId": _number_if_numeric(part.position_id), "size": str(part.size)}
            for part in self._parts
        ]

    def __repr__(self) -> str:
        return (
            "V4GmoPositionBundle(parts=<redacted>, "
            f"part_count={len(self._parts)}, total_size={self.total_size})"
        )

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True, repr=False)
class V4GmoActualReconciliation:
    snapshot: V4GmoBrokerSnapshot
    position_bundle: V4GmoPositionBundle | None
    average_fill_price: Decimal | None
    closed_size: int = 0
    realized_pnl_jpy_internal: int | None = None
    account_position_count: int = 0
    account_active_order_count: int = 0
    unowned_position_count: int = 0
    unowned_active_order_count: int = 0
    source_read_count: int = 3
    raw_response_retained: bool = False
    identifier_exposed: bool = False

    def __repr__(self) -> str:
        return (
            "V4GmoActualReconciliation(snapshot=<sanitized>, "
            "identifiers=<redacted>, raw_response_retained=False)"
        )

    def __bool__(self) -> bool:
        return False

    def _binding_digest_internal(self) -> str:
        """Bind sanitized state and redacted position ownership in memory."""

        parts = (
            []
            if self.position_bundle is None
            else [
                {"position_id": part.position_id, "size": part.size}
                for part in self.position_bundle._parts
            ]
        )
        canonical = json.dumps(
            {
                "average_fill_price": (
                    None
                    if self.average_fill_price is None
                    else format(self.average_fill_price, "f")
                ),
                "account_active_order_count": self.account_active_order_count,
                "account_position_count": self.account_position_count,
                "entry_status": self.snapshot.entry_status.value,
                "closed_size": self.closed_size,
                "filled_size": self.snapshot.filled_size,
                "fresh": self.snapshot.fresh,
                "pending_entry_size": self.snapshot.pending_entry_size,
                "position_count": self.snapshot.position_count,
                "position_side": (
                    None
                    if self.snapshot.position_side is None
                    else self.snapshot.position_side.value
                ),
                "positions": parts,
                "protection_size": self.snapshot.protection_size,
                "protection_status": self.snapshot.protection_status.value,
                "result_known": self.snapshot.result_known,
                "realized_pnl_jpy_internal": self.realized_pnl_jpy_internal,
                "unowned_active_order_count": self.unowned_active_order_count,
                "unowned_position_count": self.unowned_position_count,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True, repr=False)
class _ExecutionRow:
    client_order_id: str
    position_id: str
    settle_type: str
    side: str
    size: int
    net_realized_pnl_jpy: Decimal


@dataclass(frozen=True, repr=False)
class _PositionRow:
    symbol: str
    position_id: str
    side: str
    size: int
    price: Decimal


@dataclass(frozen=True, repr=False)
class _ActiveOrderRow:
    symbol: str
    client_order_id: str
    settle_type: str
    size: int


def v4_gmo_client_order_id(*, cycle_ref: str, action: V4GmoAction) -> str:
    if len(cycle_ref) != 64 or any(character not in "0123456789abcdef" for character in cycle_ref):
        raise V4GmoActualAdapterError("V4_GMO_CYCLE_REF_INVALID")
    prefixes = {
        V4GmoAction.MARKET_ENTRY: "H11V4E",
        V4GmoAction.EXACT_SIZE_OCO_PROTECTION: "H11V4P",
        V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT: "H11V4X",
        V4GmoAction.POSITION_SPECIFIC_TIME_EXIT: "H11V4T",
    }
    normalized = action
    if action is V4GmoAction.CANCEL_ENTRY_REMAINDER:
        normalized = V4GmoAction.MARKET_ENTRY
    elif action is V4GmoAction.CANCEL_MISMATCHED_PROTECTION:
        normalized = V4GmoAction.EXACT_SIZE_OCO_PROTECTION
    elif action is V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT:
        normalized = V4GmoAction.EXACT_SIZE_OCO_PROTECTION
    return prefixes[normalized] + cycle_ref[:30]


@dataclass
class V4GmoActualAdapter:
    transport: V4GmoPrivateTransport
    _attempted: set[tuple[str, V4GmoAction]] = field(default_factory=set, init=False)
    _last_private_get_start_monotonic: float | None = field(
        default=None,
        init=False,
        repr=False,
    )
    # Diagnostic only: the FIXED internal label of the most recent perform_once
    # failure (e.g. V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT). Never broker response
    # content, identifiers, or credentials — internal constant labels only.
    last_failure_class: str | None = field(default=None, init=False, repr=False)

    def __repr__(self) -> str:
        return "V4GmoActualAdapter(<transport-redacted>)"

    def perform_once(
        self,
        *,
        plan: V4GmoActionPlan,
        persisted_authorization: V4PersistedActionAuthorization,
        now_monotonic: float,
        reconciliation: V4GmoActualReconciliation | None = None,
        protection_plan: V4GmoExactProtectionPlan | None = None,
        public_market_status_guard: (
            V4GmoPublicMarketStatusTransportGuard | None
        ) = None,
    ) -> V4GmoPrivateOutcome:
        # Reset first so the diagnostic is strictly per-call: a failure in the
        # pre-transport guards below can never leave a previous call's label behind.
        self.last_failure_class = None
        key = (plan.cycle_ref, plan.action)
        if key in self._attempted:
            raise V4GmoActualAdapterError("V4_GMO_SAME_ACTION_SECOND_ATTEMPT_FORBIDDEN")
        request = self._build_action_request(
            plan=plan,
            reconciliation=reconciliation,
            protection_plan=protection_plan,
        )
        transport_authorization = consume_persisted_action_authorization(
            persisted_authorization,
            plan=plan,
            protection_plan=protection_plan,
            reconciliation_digest=(
                None
                if reconciliation is None
                else reconciliation._binding_digest_internal()
            ),
            request_binding_digest=v4_gmo_private_request_binding_digest(request),
            now_monotonic=now_monotonic,
        )
        self._attempted.add(key)
        market_guard_actions = {
            V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
            V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
        }
        if plan.action in market_guard_actions:
            if type(public_market_status_guard) is not V4GmoPublicMarketStatusTransportGuard:
                raise V4GmoActualAdapterError(
                    "V4_GMO_PUBLIC_MARKET_STATUS_GUARD_REQUIRED"
                )
            try:
                public_market_status_guard.require_fresh_open_at_transport_boundary()
            except V4GmoPublicMarketStatusError:
                raise V4GmoActualAdapterError(
                    "V4_GMO_PUBLIC_MARKET_OPEN_REQUIRED_AT_TRANSPORT_BOUNDARY"
                ) from None
        elif public_market_status_guard is not None:
            raise V4GmoActualAdapterError(
                "V4_GMO_PUBLIC_MARKET_STATUS_GUARD_UNEXPECTED"
            )
        try:
            payload = self.transport.request(
                request,
                persisted_transport_authorization=transport_authorization,
            )
        except (V4GmoActualTransportError, TimeoutError, OSError) as error:
            self.last_failure_class = _sanitized_failure_class(error)
            return V4GmoPrivateOutcome.UNKNOWN_SANITIZED
        try:
            status = _envelope_status(payload)
        except V4GmoActualAdapterError:
            self.last_failure_class = "V4_GMO_PRIVATE_RESULT_UNKNOWN_ENVELOPE_INVALID"
            return V4GmoPrivateOutcome.UNKNOWN_SANITIZED
        if status != 0:
            self.last_failure_class = "V4_GMO_PRIVATE_RESULT_REJECTED_BY_BROKER"
            return V4GmoPrivateOutcome.REJECTED_SANITIZED
        return V4GmoPrivateOutcome.ACCEPTED_SANITIZED

    def reconcile(
        self,
        *,
        cycle_ref: str,
        side: SignalDecision,
        requested_size: int,
        monotonic_factory: Callable[[], float],
        wait: Callable[[float], None],
    ) -> V4GmoActualReconciliation:
        return self.reconcile_at_fixed_cadence(
            cycle_ref=cycle_ref,
            side=side,
            requested_size=requested_size,
            monotonic_factory=monotonic_factory,
            wait=wait,
        )

    def reconcile_at_fixed_cadence(
        self,
        *,
        cycle_ref: str,
        side: SignalDecision,
        requested_size: int,
        monotonic_factory: Callable[[], float],
        wait: Callable[[float], None],
    ) -> V4GmoActualReconciliation:
        """Perform three authoritative GETs with >=0.25s start separation.

        This actual-coordinator path applies a conservative 0.25s delay before
        the first GET after adapter creation/restart.  It does not retry a
        failed GET and it does not tighten the operator-frozen cadence.
        """

        _validate_cycle_inputs(
            cycle_ref=cycle_ref,
            side=side,
            requested_size=requested_size,
        )
        offsets = v4_reconciliation_get_offsets_seconds()
        start = float(monotonic_factory())
        if not math.isfinite(start) or start < 0:
            return _unknown_reconciliation()

        def request_at(offset: float, request: V4GmoPrivateRequest) -> Any:
            # A new adapter is treated as a conservative restart boundary: its
            # first GET is delayed by one full cadence interval.  The shared
            # field then carries the account cadence across reconciliation
            # calls made by this runtime.
            target = start + 0.25 + offset
            if self._last_private_get_start_monotonic is not None:
                target = max(
                    target,
                    self._last_private_get_start_monotonic + 0.25,
                )
            current = float(monotonic_factory())
            if (
                not math.isfinite(current)
                or current < 0
                or (
                    self._last_private_get_start_monotonic is not None
                    and current < self._last_private_get_start_monotonic
                )
            ):
                raise V4GmoActualAdapterError(
                    "V4_GMO_RECONCILIATION_CADENCE_CLOCK_INVALID"
                )
            remaining = target - current
            if remaining > 0:
                wait(remaining)
            actual_start = float(monotonic_factory())
            if (
                not math.isfinite(actual_start)
                or actual_start < target
                or (
                    self._last_private_get_start_monotonic is not None
                    and actual_start < self._last_private_get_start_monotonic + 0.25
                )
            ):
                raise V4GmoActualAdapterError(
                    "V4_GMO_RECONCILIATION_CADENCE_NOT_REACHED"
                )
            self._last_private_get_start_monotonic = actual_start
            return _envelope_data(self.transport.request(request))

        try:
            executions = _parse_executions(
                request_at(
                    offsets[0],
                    _get_request(
                        LATEST_EXECUTIONS_TRANSPORT_PATH,
                        "/v1/latestExecutions",
                        {"symbol": SYMBOL, "count": "100"},
                    ),
                )
            )
            positions = _parse_positions(
                request_at(
                    offsets[1],
                    _get_request(
                        OPEN_POSITIONS_TRANSPORT_PATH,
                        "/v1/openPositions",
                        {"count": "100"},
                    ),
                )
            )
            active_orders = _parse_active_orders(
                request_at(
                    offsets[2],
                    _get_request(
                        ACTIVE_ORDERS_TRANSPORT_PATH,
                        "/v1/activeOrders",
                        {"count": "100"},
                    ),
                )
            )
            return _reconcile_rows(
                cycle_ref=cycle_ref,
                side=side,
                requested_size=requested_size,
                executions=executions,
                positions=positions,
                active_orders=active_orders,
            )
        except (
            V4GmoActualTransportError,
            V4GmoActualAdapterError,
            TimeoutError,
            OSError,
            ValueError,
            InvalidOperation,
        ):
            return _unknown_reconciliation()

    def _build_action_request(
        self,
        *,
        plan: V4GmoActionPlan,
        reconciliation: V4GmoActualReconciliation | None,
        protection_plan: V4GmoExactProtectionPlan | None,
    ) -> V4GmoPrivateRequest:
        client_order_id = v4_gmo_client_order_id(
            cycle_ref=plan.cycle_ref,
            action=plan.action,
        )
        if plan.action is V4GmoAction.MARKET_ENTRY:
            body: Mapping[str, object] = {
                "symbol": SYMBOL,
                "side": plan.side.value,
                "size": str(plan.requested_size),
                "clientOrderId": client_order_id,
                "executionType": "MARKET",
            }
            return _post_request(ORDER_TRANSPORT_PATH, "/v1/order", body)
        if plan.action in (
            V4GmoAction.CANCEL_ENTRY_REMAINDER,
            V4GmoAction.CANCEL_MISMATCHED_PROTECTION,
            V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
        ):
            if reconciliation is None or reconciliation.snapshot.fresh is not True:
                raise V4GmoActualAdapterError(
                    "V4_GMO_AUTHORITATIVE_RECONCILIATION_REQUIRED"
                )
            snapshot = reconciliation.snapshot
            if snapshot.result_known is not True or snapshot.position_side not in {
                None,
                plan.side,
            }:
                raise V4GmoActualAdapterError("V4_GMO_RECONCILIATION_MISMATCH")
            if plan.action is V4GmoAction.CANCEL_ENTRY_REMAINDER:
                valid_cancel_state = (
                    snapshot.entry_status
                    in {V4GmoEntryStatus.PENDING, V4GmoEntryStatus.PARTIAL}
                    and snapshot.pending_entry_size == plan.requested_size
                    and snapshot.pending_entry_size > 0
                    and snapshot.position_count <= 1
                )
            elif plan.action is V4GmoAction.CANCEL_MISMATCHED_PROTECTION:
                valid_cancel_state = (
                    snapshot.position_count == 1
                    and snapshot.filled_size > 0
                    and snapshot.protection_size == plan.requested_size
                    and snapshot.protection_status
                    in {
                        V4GmoProtectionStatus.UNDERSIZED,
                        V4GmoProtectionStatus.OVERSIZED,
                    }
                )
            else:
                valid_cancel_state = (
                    snapshot.position_count == 1
                    and snapshot.filled_size > 0
                    and snapshot.protection_size == plan.requested_size
                    and snapshot.protection_status
                    is V4GmoProtectionStatus.EXACT_MATCH
                )
            if not valid_cancel_state:
                raise V4GmoActualAdapterError("V4_GMO_CANCEL_STATE_MISMATCH")
            return _post_request(
                CANCEL_TRANSPORT_PATH,
                "/v1/cancelOrders",
                {"clientOrderIds": [client_order_id]},
            )
        if reconciliation is None or reconciliation.position_bundle is None:
            raise V4GmoActualAdapterError("V4_GMO_POSITION_RECONCILIATION_REQUIRED")
        if reconciliation.snapshot.result_known is not True:
            raise V4GmoActualAdapterError("V4_GMO_RECONCILIATION_UNKNOWN")
        snapshot = reconciliation.snapshot
        if (
            snapshot.fresh is not True
            or snapshot.position_count != 1
            or snapshot.position_side is not plan.side
            or snapshot.entry_status is not V4GmoEntryStatus.FILLED
            or snapshot.pending_entry_size != 0
            or snapshot.filled_size != plan.requested_size
        ):
            raise V4GmoActualAdapterError("V4_GMO_POSITION_STATE_MISMATCH")
        if reconciliation.position_bundle.total_size != plan.requested_size:
            raise V4GmoActualAdapterError("V4_GMO_POSITION_SIZE_MISMATCH")
        settlement_side = (
            SignalDecision.SELL if plan.side is SignalDecision.BUY else SignalDecision.BUY
        )
        if plan.action is V4GmoAction.EXACT_SIZE_OCO_PROTECTION:
            if protection_plan is None:
                raise V4GmoActualAdapterError("V4_GMO_PROTECTION_PLAN_REQUIRED")
            if (
                snapshot.protection_size != 0
                or snapshot.protection_status is not V4GmoProtectionStatus.NONE
                or
                protection_plan.position_side is not plan.side
                or protection_plan.settlement_side is not settlement_side
                or protection_plan.exact_filled_size != plan.requested_size
                or protection_plan.contract_hash != plan.protection_contract_hash
            ):
                raise V4GmoActualAdapterError("V4_GMO_PROTECTION_PLAN_MISMATCH")
            body = {
                "symbol": SYMBOL,
                "side": settlement_side.value,
                "clientOrderId": client_order_id,
                "executionType": "OCO",
                "limitPrice": format(protection_plan.take_profit_price, "f"),
                "stopPrice": format(protection_plan.stop_loss_price, "f"),
                "settlePosition": (
                    reconciliation.position_bundle._settle_positions_for_internal_request()
                ),
            }
            return _post_request(CLOSE_ORDER_TRANSPORT_PATH, "/v1/closeOrder", body)
        if plan.action in {
            V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
            V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
        }:
            if (
                snapshot.protection_size != 0
                or snapshot.protection_status is not V4GmoProtectionStatus.NONE
            ):
                raise V4GmoActualAdapterError("V4_GMO_EMERGENCY_EXIT_STATE_MISMATCH")
            body = {
                "symbol": SYMBOL,
                "side": settlement_side.value,
                "clientOrderId": client_order_id,
                "executionType": "MARKET",
                "settlePosition": (
                    reconciliation.position_bundle._settle_positions_for_internal_request()
                ),
            }
            return _post_request(CLOSE_ORDER_TRANSPORT_PATH, "/v1/closeOrder", body)
        raise V4GmoActualAdapterError("V4_GMO_ACTION_NOT_SUPPORTED")


def _reconcile_rows(
    *,
    cycle_ref: str,
    side: SignalDecision,
    requested_size: int,
    executions: tuple[_ExecutionRow, ...],
    positions: tuple[_PositionRow, ...],
    active_orders: tuple[_ActiveOrderRow, ...],
) -> V4GmoActualReconciliation:
    entry_id = v4_gmo_client_order_id(cycle_ref=cycle_ref, action=V4GmoAction.MARKET_ENTRY)
    protection_id = v4_gmo_client_order_id(
        cycle_ref=cycle_ref, action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION
    )
    exit_id = v4_gmo_client_order_id(
        cycle_ref=cycle_ref, action=V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT
    )
    time_exit_id = v4_gmo_client_order_id(
        cycle_ref=cycle_ref, action=V4GmoAction.POSITION_SPECIFIC_TIME_EXIT
    )
    permitted_client_ids = {entry_id, protection_id, exit_id, time_exit_id}

    owned_open_rows = tuple(
        row
        for row in executions
        if row.client_order_id == entry_id and row.settle_type == "OPEN"
    )
    if any(row.side != side.value for row in owned_open_rows):
        return _unknown_reconciliation()
    owned_position_sizes: dict[str, int] = {}
    for row in owned_open_rows:
        owned_position_sizes[row.position_id] = (
            owned_position_sizes.get(row.position_id, 0) + row.size
        )
    if sum(owned_position_sizes.values()) > requested_size:
        return _unknown_reconciliation()
    owned_position_ids = set(owned_position_sizes)
    unowned_positions = tuple(
        row
        for row in positions
        if row.symbol != SYMBOL or row.position_id not in owned_position_ids
    )
    unowned_active_orders = tuple(
        row
        for row in active_orders
        if row.symbol != SYMBOL or row.client_order_id not in permitted_client_ids
    )
    if unowned_positions or unowned_active_orders:
        return _unknown_reconciliation(
            account_position_count=len(positions),
            account_active_order_count=len(active_orders),
            unowned_position_count=len(unowned_positions),
            unowned_active_order_count=len(unowned_active_orders),
        )
    positions = tuple(
        row
        for row in positions
        if row.symbol == SYMBOL and row.position_id in owned_position_ids
    )
    active_orders = tuple(
        row
        for row in active_orders
        if row.symbol == SYMBOL and row.client_order_id in permitted_client_ids
    )
    if positions and (
        not owned_position_ids
        or any(row.position_id not in owned_position_ids for row in positions)
    ):
        return _unknown_reconciliation()
    if any(row.side != side.value for row in positions):
        return _unknown_reconciliation()
    if len(positions) > 10:
        return _unknown_reconciliation()

    filled_size = sum(row.size for row in positions)
    if filled_size > requested_size:
        return _unknown_reconciliation()
    bundle = (
        V4GmoPositionBundle(tuple(_PositionPart(row.position_id, row.size) for row in positions))
        if positions
        else None
    )
    average_fill_price = (
        sum((row.price * row.size for row in positions), Decimal("0")) / Decimal(filled_size)
        if filled_size
        else None
    )
    close_rows = tuple(
        row
        for row in executions
        if row.settle_type == "CLOSE"
        and row.client_order_id in {protection_id, exit_id, time_exit_id}
    )
    expected_close_side = (
        SignalDecision.SELL.value
        if side is SignalDecision.BUY
        else SignalDecision.BUY.value
    )
    if any(
        row.position_id not in owned_position_ids
        or row.side != expected_close_side
        for row in close_rows
    ):
        return _unknown_reconciliation()
    closed_size_by_position: dict[str, int] = {}
    for row in close_rows:
        closed_size_by_position[row.position_id] = (
            closed_size_by_position.get(row.position_id, 0) + row.size
        )
    if any(
        closed_size > owned_position_sizes[position_id]
        for position_id, closed_size in closed_size_by_position.items()
    ):
        return _unknown_reconciliation()
    closed_size = sum(row.size for row in close_rows)
    if closed_size > requested_size:
        return _unknown_reconciliation()
    realized_pnl_jpy_internal = (
        int(
            sum(
                (row.net_realized_pnl_jpy for row in close_rows),
                Decimal("0"),
            ).to_integral_value(rounding=ROUND_FLOOR)
        )
        if close_rows
        else None
    )

    active_entry = tuple(row for row in active_orders if row.client_order_id == entry_id)
    active_protection = tuple(row for row in active_orders if row.client_order_id == protection_id)
    if any(row.settle_type not in {"", "OPEN"} for row in active_entry):
        return _unknown_reconciliation()
    if any(row.settle_type not in {"", "CLOSE"} for row in active_protection):
        return _unknown_reconciliation()
    pending_size = requested_size - filled_size if active_entry else 0
    if pending_size < 0:
        return _unknown_reconciliation()

    if active_protection:
        sizes = {row.size for row in active_protection}
        if len(sizes) != 1:
            return _unknown_reconciliation()
        protection_size = sizes.pop()
        if protection_size == filled_size and filled_size > 0:
            protection_status = V4GmoProtectionStatus.EXACT_MATCH
        elif protection_size < filled_size:
            protection_status = V4GmoProtectionStatus.UNDERSIZED
        else:
            protection_status = V4GmoProtectionStatus.OVERSIZED
    else:
        protection_size = 0
        protection_status = V4GmoProtectionStatus.NONE

    if active_entry and filled_size:
        entry_status = V4GmoEntryStatus.PARTIAL
    elif active_entry:
        entry_status = V4GmoEntryStatus.PENDING
    elif filled_size:
        entry_status = V4GmoEntryStatus.FILLED
    else:
        entry_status = V4GmoEntryStatus.NONE

    snapshot = V4GmoBrokerSnapshot(
        fresh=True,
        result_known=True,
        position_count=1 if positions else 0,
        position_side=side if positions else None,
        filled_size=filled_size,
        pending_entry_size=pending_size,
        protection_size=protection_size,
        entry_status=entry_status,
        protection_status=protection_status,
    )
    return V4GmoActualReconciliation(
        snapshot=snapshot,
        position_bundle=bundle,
        average_fill_price=average_fill_price,
        closed_size=closed_size,
        realized_pnl_jpy_internal=realized_pnl_jpy_internal,
        account_position_count=len(positions),
        account_active_order_count=len(active_orders),
        unowned_position_count=0,
        unowned_active_order_count=0,
    )


def _parse_executions(data: Any) -> tuple[_ExecutionRow, ...]:
    rows = _rows(data, endpoint="EXECUTIONS")
    parsed: list[_ExecutionRow] = []
    for row in rows:
        if str(row.get("symbol", "")) != SYMBOL:
            continue
        # latestExecutions can legitimately include unrelated manual history
        # without clientOrderId. It is not owned by this v4 cycle and is
        # ignored. Any current open position still has to link to this cycle's
        # explicit clientOrderId below, so ignoring history cannot claim
        # ownership of an unowned position.
        client_order_id = str(row.get("clientOrderId", ""))
        if not client_order_id:
            continue
        parsed.append(
            _ExecutionRow(
                client_order_id=client_order_id,
                position_id=_required_string(row, "positionId"),
                settle_type=_required_choice(row, "settleType", {"OPEN", "CLOSE"}),
                side=_required_choice(row, "side", {"BUY", "SELL"}),
                size=_positive_int(row, "size"),
                net_realized_pnl_jpy=(
                    _required_decimal(row, "lossGain")
                    + _required_decimal(row, "fee")
                    + _required_decimal(row, "settledSwap")
                    if str(row.get("settleType", "")).upper() == "CLOSE"
                    else Decimal("0")
                ),
            )
        )
    return tuple(parsed)


def _parse_positions(data: Any) -> tuple[_PositionRow, ...]:
    rows = _rows(data, endpoint="POSITIONS")
    parsed: list[_PositionRow] = []
    for row in rows:
        price_value = row.get("price", row.get("averagePrice"))
        price = Decimal(str(price_value))
        if price <= 0:
            raise V4GmoActualAdapterError("V4_GMO_POSITION_PRICE_INVALID")
        parsed.append(
            _PositionRow(
                symbol=_required_string(row, "symbol"),
                position_id=_required_string(row, "positionId"),
                side=_required_choice(row, "side", {"BUY", "SELL"}),
                size=_positive_int(row, "size"),
                price=price,
            )
        )
    return tuple(parsed)


def _parse_active_orders(data: Any) -> tuple[_ActiveOrderRow, ...]:
    rows = _rows(data, endpoint="ACTIVE_ORDERS")
    parsed: list[_ActiveOrderRow] = []
    for row in rows:
        parsed.append(
            _ActiveOrderRow(
                symbol=_required_string(row, "symbol"),
                client_order_id=_required_string(row, "clientOrderId"),
                settle_type=str(row.get("settleType", "")).upper(),
                size=_positive_int(row, "size"),
            )
        )
    return tuple(parsed)


def _rows(data: Any, *, endpoint: str) -> Sequence[Mapping[str, Any]]:
    if data is None:
        return ()
    if isinstance(data, list):
        rows = data
    elif isinstance(data, Mapping) and isinstance(data.get("list"), list):
        rows = data["list"]
    else:
        raise V4GmoActualAdapterError(f"V4_GMO_{endpoint}_SCHEMA_INVALID")
    if any(not isinstance(row, Mapping) for row in rows):
        raise V4GmoActualAdapterError(f"V4_GMO_{endpoint}_ROW_INVALID")
    return rows


def _get_request(
    transport_path: str,
    signing_path: str,
    params: Mapping[str, str],
) -> V4GmoPrivateRequest:
    return V4GmoPrivateRequest(
        method="GET",
        transport_path=transport_path,
        signing_path=signing_path,
        params=params,
        body=None,
    )


def _post_request(
    transport_path: str,
    signing_path: str,
    body: Mapping[str, Any],
) -> V4GmoPrivateRequest:
    return V4GmoPrivateRequest(
        method="POST",
        transport_path=transport_path,
        signing_path=signing_path,
        params={},
        body=body,
    )


def _sanitized_failure_class(error: Exception) -> str:
    """Return one FIXED internal diagnostic label for a failed private call.

    Membership in the closed ``V4_GMO_SURFACEABLE_FAILURE_CLASSES`` allow-list is
    exact, so no exception text can pass through — not even one shaped like an
    internal label. Anything unrecognised collapses to the base UNKNOWN label.
    """

    if isinstance(error, V4GmoActualTransportError):
        label = str(error)
        if label in V4_GMO_SURFACEABLE_FAILURE_CLASSES:
            return label
    if isinstance(error, TimeoutError):
        return "V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT"
    if isinstance(error, OSError):
        return "V4_GMO_PRIVATE_RESULT_UNKNOWN_CONNECTION"
    return "V4_GMO_PRIVATE_RESULT_UNKNOWN"


def _envelope_status(payload: V4GmoPrivateEnvelope) -> int:
    if not isinstance(payload, V4GmoPrivateEnvelope):
        raise V4GmoActualAdapterError("V4_GMO_RESPONSE_ENVELOPE_INVALID")
    return payload._status_for_adapter()


def _envelope_data(payload: V4GmoPrivateEnvelope) -> Any:
    if _envelope_status(payload) != 0:
        raise V4GmoActualAdapterError("V4_GMO_RESPONSE_REJECTED")
    return payload._data_for_adapter()


def _required_string(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None or str(value) == "":
        raise V4GmoActualAdapterError("V4_GMO_REQUIRED_FIELD_MISSING")
    return str(value)


def _required_choice(row: Mapping[str, Any], key: str, choices: set[str]) -> str:
    value = _required_string(row, key).upper()
    if value not in choices:
        raise V4GmoActualAdapterError("V4_GMO_ENUM_FIELD_INVALID")
    return value


def _positive_int(row: Mapping[str, Any], key: str) -> int:
    value = Decimal(_required_string(row, key))
    if value <= 0 or value != value.to_integral_value():
        raise V4GmoActualAdapterError("V4_GMO_SIZE_FIELD_INVALID")
    return int(value)


def _required_decimal(row: Mapping[str, Any], key: str) -> Decimal:
    value = Decimal(_required_string(row, key))
    if not value.is_finite():
        raise V4GmoActualAdapterError("V4_GMO_DECIMAL_FIELD_INVALID")
    return value


def _number_if_numeric(value: str) -> int | str:
    return int(value) if value.isdigit() else value


def _validate_cycle_inputs(*, cycle_ref: str, side: SignalDecision, requested_size: int) -> None:
    v4_gmo_client_order_id(cycle_ref=cycle_ref, action=V4GmoAction.MARKET_ENTRY)
    if side not in (SignalDecision.BUY, SignalDecision.SELL):
        raise V4GmoActualAdapterError("V4_GMO_SIDE_INVALID")
    if type(requested_size) is not int or not 0 < requested_size <= 1_000:
        raise V4GmoActualAdapterError("V4_GMO_REQUESTED_SIZE_INVALID")


def _unknown_reconciliation(
    *,
    account_position_count: int = 0,
    account_active_order_count: int = 0,
    unowned_position_count: int = 0,
    unowned_active_order_count: int = 0,
) -> V4GmoActualReconciliation:
    return V4GmoActualReconciliation(
        snapshot=V4GmoBrokerSnapshot(
            fresh=False,
            result_known=False,
            position_count=0,
            position_side=None,
            filled_size=0,
            pending_entry_size=0,
            protection_size=0,
            entry_status=V4GmoEntryStatus.UNKNOWN,
            protection_status=V4GmoProtectionStatus.UNKNOWN,
        ),
        position_bundle=None,
        average_fill_price=None,
        account_position_count=account_position_count,
        account_active_order_count=account_active_order_count,
        unowned_position_count=unowned_position_count,
        unowned_active_order_count=unowned_active_order_count,
    )
