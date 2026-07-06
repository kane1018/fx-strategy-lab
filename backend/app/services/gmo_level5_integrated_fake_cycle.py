"""Integrated fake Level 5 cycle: chains runner boundary -> risk shadow gate
-> live enable policy / kill switch -> the real GmoFxBroker skeleton methods
-> settlement reconciliation.

`GmoFxBroker.market_order()` and `official_settlement_order()` have no real
transport implemented -- both always raise after the shared hard guard, by
design. This means the default (real-broker) path of this integrated cycle
can never reach an accepted entry or settlement result: if it could, the
design would be wrong (real transport would have to exist for that). This
module proves that property directly by invoking the real broker skeleton
methods (not a pure simulation, unlike `gmo_level5_fake_cycle.py`) with a
refusing fake HTTP client, and confirms the chain fails closed regardless of
how permissive the surrounding runner boundary / risk shadow gate / kill
switch / live enable policy inputs are.

The cycle input also carries a second, clearly separate simulate switch that
skips the real broker call entirely and substitutes a synthetic "accepted"
result so the surrounding state-machine logic (settlement reconciliation,
Level 5 completion criteria) can be exercised end-to-end without real
transport existing. That switch has nothing to do with the real-broker-post
hard guard's own allow flag -- it never sets that flag, never touches
`GmoFxBroker`, and must only ever be enabled from test fixtures (pinned by a
dedicated no-production-wiring test below). Level 5 can only complete when
that switch is enabled; the real-broker path is fail-closed by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.brokers.gmo_fx_broker import ENTRY_SIDE_SAFE_LABEL_BUY, GmoFxBroker, GmoFxBrokerError
from app.config import Settings
from app.schemas.trading import OrderRequest, Side
from app.services.gmo_live_runner_boundary import (
    GmoLiveRunnerBoundaryInput,
    build_gmo_live_runner_boundary_summary,
)
from app.services.gmo_settlement_reconciliation import (
    GmoSettlementReconciliationStatus,
    GmoSettlementResultCategory,
    GmoSettlementSafeReadSnapshot,
    build_gmo_settlement_reconciliation_input_from_safe_snapshot,
    evaluate_gmo_settlement_reconciliation,
)
from app.services.risk_service import (
    GmoLiveReadinessShadowInput,
    evaluate_gmo_live_readiness_shadow,
)


@dataclass(frozen=True)
class GmoLevel5IntegratedCycleInput:
    runner_boundary_input: GmoLiveRunnerBoundaryInput = GmoLiveRunnerBoundaryInput()
    shadow_gate_input: GmoLiveReadinessShadowInput = GmoLiveReadinessShadowInput()
    manual_intervention_performed: bool = False
    settlement_snapshot: GmoSettlementSafeReadSnapshot | None = None
    simulate_accepted_transport_for_state_machine_test_only: bool = False


@dataclass(frozen=True)
class GmoLevel5IntegratedCycleResult:
    level5_full_auto_cycle_completed: bool
    entry_attempt_blocked_reason: str
    blocked_reasons: tuple[str, ...]
    official_settlement_transport_fails_closed: bool


def _refusing_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError(
            "integrated fake cycle must never perform a real HTTP request"
        )

    return httpx.Client(
        base_url="https://forex-api.coin.z.com/public",
        transport=httpx.MockTransport(handler),
    )


def _synthetic_fixture_order() -> OrderRequest:
    return OrderRequest(
        client_order_id="GMO-LEVEL5-INTEGRATED-FIXTURE",
        mode="demo",
        symbol="USD_JPY",
        side=Side.BUY,
        units=100,
        current_price=150.0,
        stop_loss=149.7,
        take_profit=150.6,
        estimated_loss=10,
        api_connection_ok=True,
    )


def _confirm_official_settlement_fails_closed(broker: GmoFxBroker) -> bool:
    """Independently confirm the settlement skeleton also fails closed.

    Not part of the entry/settlement chain itself -- just a side
    verification, run every time this cycle executes, that
    `official_settlement_order` still raises before any transport.
    """
    try:
        broker.official_settlement_order(
            symbol="USD_JPY",
            entry_side_safe_label=ENTRY_SIDE_SAFE_LABEL_BUY,
            size=100,
        )
    except GmoFxBrokerError:
        return True
    return False  # pragma: no cover - would mean transport now exists


def run_gmo_level5_integrated_fake_cycle(
    cycle_input: GmoLevel5IntegratedCycleInput | None = None,
) -> GmoLevel5IntegratedCycleResult:
    """Run the integrated no-POST cycle once.

    Default mode (simulate flag False): returns
    level5_full_auto_cycle_completed=True only if every upstream gate is
    permissive AND the real broker skeleton somehow did not raise -- which
    cannot happen while real transport is unimplemented, by design.

    Simulate mode (simulate flag True): substitutes a synthetic accepted
    entry so settlement reconciliation can be exercised; Level 5 can be True
    here, but only when reconciliation also confirms NO_POSITION/count=0.
    """
    snapshot = cycle_input or GmoLevel5IntegratedCycleInput()
    reasons: list[str] = []

    runner_summary = build_gmo_live_runner_boundary_summary(snapshot.runner_boundary_input)
    if not runner_summary.runner_may_start_gmo_live_entry:
        reasons.append("runner_boundary_blocked")

    shadow_result = evaluate_gmo_live_readiness_shadow(snapshot.shadow_gate_input)
    if not shadow_result.entry_shadow_allowed:
        reasons.append("risk_shadow_gate_blocked")

    if snapshot.manual_intervention_performed:
        reasons.append("manual_intervention_performed")

    broker = GmoFxBroker(
        Settings(_env_file=None, gmo_fx_max_units=1000),
        client=_refusing_client(),
    )
    settlement_fails_closed = _confirm_official_settlement_fails_closed(broker)

    if reasons:
        return GmoLevel5IntegratedCycleResult(
            level5_full_auto_cycle_completed=False,
            entry_attempt_blocked_reason="upstream_gate_blocked",
            blocked_reasons=tuple(reasons),
            official_settlement_transport_fails_closed=settlement_fails_closed,
        )

    if not snapshot.simulate_accepted_transport_for_state_machine_test_only:
        try:
            broker.market_order(_synthetic_fixture_order())
        except GmoFxBrokerError:
            return GmoLevel5IntegratedCycleResult(
                level5_full_auto_cycle_completed=False,
                entry_attempt_blocked_reason="entry_transport_not_available",
                blocked_reasons=("entry_transport_not_available",),
                official_settlement_transport_fails_closed=settlement_fails_closed,
            )
        # Unreachable while real transport is unimplemented. Kept explicit so
        # a future transport implementation cannot silently start
        # "succeeding" here without this module being re-reviewed first.
        raise AssertionError(
            "market_order() unexpectedly did not raise; GMO live transport "
            "design must be reviewed before this integrated cycle can be "
            "trusted to report success"
        )

    if not runner_summary.runner_may_start_gmo_live_settlement:
        settlement_blocked_reasons = (
            "settlement_gate_blocked",
            *runner_summary.settlement_blocked_reasons,
        )
        return GmoLevel5IntegratedCycleResult(
            level5_full_auto_cycle_completed=False,
            entry_attempt_blocked_reason="settlement_gate_blocked",
            blocked_reasons=settlement_blocked_reasons,
            official_settlement_transport_fails_closed=settlement_fails_closed,
        )
    if not shadow_result.settlement_shadow_allowed:
        return GmoLevel5IntegratedCycleResult(
            level5_full_auto_cycle_completed=False,
            entry_attempt_blocked_reason="settlement_gate_blocked",
            blocked_reasons=("risk_shadow_settlement_blocked",),
            official_settlement_transport_fails_closed=settlement_fails_closed,
        )

    if snapshot.settlement_snapshot is None:
        return GmoLevel5IntegratedCycleResult(
            level5_full_auto_cycle_completed=False,
            entry_attempt_blocked_reason="settlement_snapshot_missing",
            blocked_reasons=("settlement_snapshot_missing",),
            official_settlement_transport_fails_closed=settlement_fails_closed,
        )

    reconciliation_input = build_gmo_settlement_reconciliation_input_from_safe_snapshot(
        settlement_result_category=GmoSettlementResultCategory.ACCEPTED_SANITIZED.value,
        snapshot=snapshot.settlement_snapshot,
    )
    reconciliation_result = evaluate_gmo_settlement_reconciliation(reconciliation_input)
    if reconciliation_result.status is not GmoSettlementReconciliationStatus.RECONCILED_NO_POSITION:
        return GmoLevel5IntegratedCycleResult(
            level5_full_auto_cycle_completed=False,
            entry_attempt_blocked_reason="settlement_not_reconciled",
            blocked_reasons=(reconciliation_result.safe_reason,),
            official_settlement_transport_fails_closed=settlement_fails_closed,
        )

    return GmoLevel5IntegratedCycleResult(
        level5_full_auto_cycle_completed=True,
        entry_attempt_blocked_reason="",
        blocked_reasons=(),
        official_settlement_transport_fails_closed=settlement_fails_closed,
    )
