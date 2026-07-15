"""Pure USD/JPY paper fill and cost model for automatic Phase A research."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.h11_auto.contracts import SignalDecision

USD_JPY_PIP_SIZE = Decimal("0.01")
GMO_API_EXECUTION_FEE_RATE = Decimal("0.00002")  # 0.002% of executed JPY notional


class H11AutoPaperError(ValueError):
    """Invalid synthetic quote or cost-model input."""


@dataclass(frozen=True)
class PaperQuote:
    bid: Decimal
    ask: Decimal

    def __post_init__(self) -> None:
        if (
            not _finite_decimal(self.bid)
            or not _finite_decimal(self.ask)
            or self.bid <= 0
            or self.ask <= 0
            or self.ask < self.bid
        ):
            raise H11AutoPaperError("paper quote must have positive bid <= ask")


@dataclass(frozen=True)
class PaperCostModel:
    size: Decimal
    slippage_pips_per_side: Decimal
    api_execution_fee_rate: Decimal = GMO_API_EXECUTION_FEE_RATE
    holding_cost_jpy: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        values = (
            self.size,
            self.slippage_pips_per_side,
            self.api_execution_fee_rate,
            self.holding_cost_jpy,
        )
        if any(not _finite_decimal(value) for value in values):
            raise H11AutoPaperError("paper cost input must be finite decimals")
        if self.size <= 0:
            raise H11AutoPaperError("paper size must be positive")
        if self.slippage_pips_per_side < 0:
            raise H11AutoPaperError("paper slippage cannot be negative")
        if self.api_execution_fee_rate < 0:
            raise H11AutoPaperError("paper API fee cannot be negative")
        if self.holding_cost_jpy < 0:
            raise H11AutoPaperError("paper holding cost cannot be negative")


@dataclass(frozen=True)
class PaperRoundTripResult:
    direction: SignalDecision
    gross_pnl_jpy: Decimal
    api_fee_jpy: Decimal
    holding_cost_jpy: Decimal
    net_pnl_jpy: Decimal
    spread_pips_at_entry: Decimal
    spread_pips_at_exit: Decimal
    actual_post_count: int = 0
    broker_write_performed: bool = False
    network_access_performed: bool = False

    def __bool__(self) -> bool:
        return False


def evaluate_paper_round_trip(
    *,
    direction: SignalDecision,
    entry_quote: PaperQuote,
    exit_quote: PaperQuote,
    costs: PaperCostModel,
) -> PaperRoundTripResult:
    if not isinstance(direction, SignalDecision):
        raise H11AutoPaperError("paper direction is invalid")
    if direction is SignalDecision.STAY:
        raise H11AutoPaperError("Stay has no paper round trip")
    slippage = costs.slippage_pips_per_side * USD_JPY_PIP_SIZE
    if direction is SignalDecision.BUY:
        entry_fill = entry_quote.ask + slippage
        exit_fill = exit_quote.bid - slippage
        gross = (exit_fill - entry_fill) * costs.size
    else:
        entry_fill = entry_quote.bid - slippage
        exit_fill = exit_quote.ask + slippage
        gross = (entry_fill - exit_fill) * costs.size
    if entry_fill <= 0 or exit_fill <= 0:
        raise H11AutoPaperError("paper fill became non-positive")
    api_fee = (
        (entry_fill * costs.size) + (exit_fill * costs.size)
    ) * costs.api_execution_fee_rate
    net = gross - api_fee - costs.holding_cost_jpy
    return PaperRoundTripResult(
        direction=direction,
        gross_pnl_jpy=gross,
        api_fee_jpy=api_fee,
        holding_cost_jpy=costs.holding_cost_jpy,
        net_pnl_jpy=net,
        spread_pips_at_entry=(entry_quote.ask - entry_quote.bid) / USD_JPY_PIP_SIZE,
        spread_pips_at_exit=(exit_quote.ask - exit_quote.bid) / USD_JPY_PIP_SIZE,
    )


def _finite_decimal(value: object) -> bool:
    return isinstance(value, Decimal) and value.is_finite()
