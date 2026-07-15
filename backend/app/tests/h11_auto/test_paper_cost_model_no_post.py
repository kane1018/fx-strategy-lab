from __future__ import annotations

from decimal import Decimal

import pytest

from app.h11_auto.contracts import SignalDecision
from app.h11_auto.paper import (
    GMO_API_EXECUTION_FEE_RATE,
    H11AutoPaperError,
    PaperCostModel,
    PaperQuote,
    evaluate_paper_round_trip,
)


def test_buy_round_trip_uses_ask_entry_bid_exit_slippage_and_api_fee() -> None:
    result = evaluate_paper_round_trip(
        direction=SignalDecision.BUY,
        entry_quote=PaperQuote(bid=Decimal("150.000"), ask=Decimal("150.010")),
        exit_quote=PaperQuote(bid=Decimal("150.110"), ask=Decimal("150.120")),
        costs=PaperCostModel(
            size=Decimal("100"),
            slippage_pips_per_side=Decimal("0.2"),
            holding_cost_jpy=Decimal("1"),
        ),
    )
    assert result.gross_pnl_jpy == Decimal("9.600")
    assert result.api_fee_jpy == Decimal("0.60024000")
    assert result.net_pnl_jpy == Decimal("7.99976000")
    assert result.spread_pips_at_entry == Decimal("1.0")
    assert result.actual_post_count == 0
    assert result.broker_write_performed is False
    assert result.network_access_performed is False


def test_sell_round_trip_uses_bid_entry_ask_exit_and_costs() -> None:
    result = evaluate_paper_round_trip(
        direction=SignalDecision.SELL,
        entry_quote=PaperQuote(bid=Decimal("150.000"), ask=Decimal("150.010")),
        exit_quote=PaperQuote(bid=Decimal("149.890"), ask=Decimal("149.900")),
        costs=PaperCostModel(
            size=Decimal("100"), slippage_pips_per_side=Decimal("0.2")
        ),
    )
    assert result.gross_pnl_jpy == Decimal("9.600")
    assert result.api_fee_jpy == Decimal("0.59980000")
    assert result.net_pnl_jpy == Decimal("9.00020000")


def test_zero_fee_scenario_can_be_used_as_explicit_ablation() -> None:
    result = evaluate_paper_round_trip(
        direction=SignalDecision.BUY,
        entry_quote=PaperQuote(bid=Decimal("150.000"), ask=Decimal("150.010")),
        exit_quote=PaperQuote(bid=Decimal("150.010"), ask=Decimal("150.020")),
        costs=PaperCostModel(
            size=Decimal("100"),
            slippage_pips_per_side=Decimal("0"),
            api_execution_fee_rate=Decimal("0"),
        ),
    )
    assert result.net_pnl_jpy == Decimal("0.000")
    assert GMO_API_EXECUTION_FEE_RATE == Decimal("0.00002")


@pytest.mark.parametrize(
    "call",
    [
        lambda: PaperQuote(bid=Decimal("150"), ask=Decimal("149")),
        lambda: PaperCostModel(
            size=Decimal("0"), slippage_pips_per_side=Decimal("0")
        ),
        lambda: PaperCostModel(
            size=Decimal("100"), slippage_pips_per_side=Decimal("-0.1")
        ),
        lambda: PaperQuote(bid=Decimal("NaN"), ask=Decimal("150")),
        lambda: PaperCostModel(
            size=Decimal("Infinity"), slippage_pips_per_side=Decimal("0")
        ),
        lambda: evaluate_paper_round_trip(
            direction=SignalDecision.STAY,
            entry_quote=PaperQuote(bid=Decimal("150"), ask=Decimal("150.01")),
            exit_quote=PaperQuote(bid=Decimal("150"), ask=Decimal("150.01")),
            costs=PaperCostModel(
                size=Decimal("100"), slippage_pips_per_side=Decimal("0")
            ),
        ),
        lambda: evaluate_paper_round_trip(
            direction="BUY",  # type: ignore[arg-type]
            entry_quote=PaperQuote(bid=Decimal("150"), ask=Decimal("150.01")),
            exit_quote=PaperQuote(bid=Decimal("150"), ask=Decimal("150.01")),
            costs=PaperCostModel(
                size=Decimal("100"), slippage_pips_per_side=Decimal("0")
            ),
        ),
    ],
)
def test_invalid_or_stay_paper_input_is_refused(call) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(H11AutoPaperError):
        call()
