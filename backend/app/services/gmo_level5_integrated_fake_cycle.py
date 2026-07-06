"""Integrated fake Level 5 cycle: chains kill switch -> live enable policy ->
the real GmoFxBroker skeleton methods -> settlement reconciliation.

`GmoFxBroker.market_order()` and `official_settlement_order()` have no real
transport implemented -- both always raise after the shared hard guard, by
design. This means an integrated cycle that actually calls those methods can
never reach an accepted entry or settlement result in this Step: if it
could, the design would be wrong (real transport would have to exist for
that). This module proves that property directly by invoking the real
broker skeleton methods (not a pure simulation, unlike
`gmo_level5_fake_cycle.py`) with a refusing fake HTTP client, and confirms
the chain fails closed at the entry step regardless of how permissive the
surrounding kill switch / live enable policy inputs are.

Settlement reconciliation (`gmo_settlement_reconciliation.py`) is exercised
independently with synthetic post-settlement safe-read fixtures, since a
real integrated run can never reach that step while entry transport does
not exist.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.brokers.gmo_fx_broker import GmoFxBroker, GmoFxBrokerError
from app.config import Settings
from app.schemas.trading import OrderRequest, Side
from app.services.gmo_live_safety_policy import (
    GmoLiveEnablePolicyInput,
    GmoLiveKillSwitchState,
    evaluate_gmo_live_enable_policy,
    evaluate_gmo_live_kill_switch,
)


@dataclass(frozen=True)
class GmoLevel5IntegratedCycleInput:
    kill_switch_state: GmoLiveKillSwitchState = GmoLiveKillSwitchState()
    live_enable_policy_input: GmoLiveEnablePolicyInput = GmoLiveEnablePolicyInput()
    manual_intervention_performed: bool = False


@dataclass(frozen=True)
class GmoLevel5IntegratedCycleResult:
    level5_full_auto_cycle_completed: bool
    entry_attempt_blocked_reason: str
    blocked_reasons: tuple[str, ...]


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


def run_gmo_level5_integrated_fake_cycle(
    cycle_input: GmoLevel5IntegratedCycleInput | None = None,
) -> GmoLevel5IntegratedCycleResult:
    """Run the integrated no-POST cycle once.

    Returns level5_full_auto_cycle_completed=True only if every upstream
    gate is permissive AND the real broker skeleton somehow did not raise --
    which cannot happen while real transport is unimplemented, by design.
    """
    snapshot = cycle_input or GmoLevel5IntegratedCycleInput()
    reasons: list[str] = []

    kill_switch_decision = evaluate_gmo_live_kill_switch(snapshot.kill_switch_state)
    if not kill_switch_decision.entry_allowed:
        reasons.append("kill_switch_triggered")

    live_enable_result = evaluate_gmo_live_enable_policy(snapshot.live_enable_policy_input)
    if not live_enable_result.live_enable_ready:
        reasons.append("live_enable_policy_not_ready")

    if snapshot.manual_intervention_performed:
        reasons.append("manual_intervention_performed")

    if reasons:
        return GmoLevel5IntegratedCycleResult(
            level5_full_auto_cycle_completed=False,
            entry_attempt_blocked_reason="upstream_gate_blocked",
            blocked_reasons=tuple(reasons),
        )

    broker = GmoFxBroker(
        Settings(_env_file=None, gmo_fx_max_units=1000),
        client=_refusing_client(),
    )
    try:
        broker.market_order(_synthetic_fixture_order())
    except GmoFxBrokerError:
        return GmoLevel5IntegratedCycleResult(
            level5_full_auto_cycle_completed=False,
            entry_attempt_blocked_reason="entry_transport_not_available",
            blocked_reasons=("entry_transport_not_available",),
        )
    # Unreachable while real transport is unimplemented. Kept explicit so a
    # future transport implementation cannot silently start "succeeding"
    # here without this module being re-reviewed first.
    raise AssertionError(
        "market_order() unexpectedly did not raise; GMO live transport "
        "design must be reviewed before this integrated cycle can be "
        "trusted to report success"
    )
