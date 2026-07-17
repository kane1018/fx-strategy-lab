"""Pure exact-fill OCO calculation for the GMO v4 profile (no-POST)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from app.h11_auto.contracts import SignalDecision

H11_V4_GMO_PROTECTION_SPEC = {
    "symbol": "USD_JPY",
    "entry_execution_type": "MARKET",
    "protection_order_type": "OCO",
    "protection_size_source": "RECONCILED_ACTUAL_FILLED_SIZE",
    "stop_loss_atr_multiplier": "1.50",
    "take_profit_r_multiple": "1.50",
    "tick_size": "0.001",
    "max_intended_size": 1_000,
    "same_action_retry_allowed": False,
    "same_action_repost_allowed": False,
    "actual_post_allowed": False,
}


def _calculate_protection_contract_hash() -> str:
    canonical = json.dumps(
        H11_V4_GMO_PROTECTION_SPEC,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("ascii")).hexdigest()


H11_V4_GMO_PROTECTION_CONTRACT_HASH = (
    "sha256:2b2a5d8669737177050260e46904723d69bd956b9893447efdcced2e6aae1518"
)


class V4GmoProtectionError(ValueError):
    """Fixed validation error for the pure protection calculation."""


@dataclass(frozen=True)
class V4GmoExactProtectionPlan:
    symbol: str
    position_side: SignalDecision
    settlement_side: SignalDecision
    exact_filled_size: int
    take_profit_price: Decimal
    stop_loss_price: Decimal
    contract_hash: str
    actual_post_allowed: bool = False
    credential_read_allowed: bool = False
    network_access_allowed: bool = False

    def __post_init__(self) -> None:
        if self.symbol != "USD_JPY":
            raise V4GmoProtectionError("v4 protection symbol is not frozen USD_JPY")
        if self.position_side not in (SignalDecision.BUY, SignalDecision.SELL):
            raise V4GmoProtectionError("v4 protection position side is invalid")
        expected_settlement = (
            SignalDecision.SELL
            if self.position_side is SignalDecision.BUY
            else SignalDecision.BUY
        )
        if self.settlement_side is not expected_settlement:
            raise V4GmoProtectionError("v4 protection settlement side is invalid")
        if not 0 < self.exact_filled_size <= 1_000:
            raise V4GmoProtectionError("v4 protection size is outside the frozen bound")
        if self.take_profit_price <= 0 or self.stop_loss_price <= 0:
            raise V4GmoProtectionError("v4 protection prices must be positive")
        if self.contract_hash != H11_V4_GMO_PROTECTION_CONTRACT_HASH:
            raise V4GmoProtectionError("v4 protection contract hash mismatch")
        if (
            self.actual_post_allowed
            or self.credential_read_allowed
            or self.network_access_allowed
        ):
            raise V4GmoProtectionError("pure v4 protection plan cannot enable transport")

    @property
    def canonical_json(self) -> str:
        return json.dumps(
            {
                "contract_hash": self.contract_hash,
                "exact_filled_size": self.exact_filled_size,
                "position_side": self.position_side.value,
                "settlement_side": self.settlement_side.value,
                "stop_loss_price": format(self.stop_loss_price, "f"),
                "symbol": self.symbol,
                "take_profit_price": format(self.take_profit_price, "f"),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def plan_digest(self) -> str:
        return hashlib.sha256(self.canonical_json.encode()).hexdigest()


def build_exact_fill_oco_plan_no_post(
    *,
    position_side: SignalDecision,
    reconciled_average_fill_price: Decimal,
    frozen_signal_atr_24: Decimal,
    reconciled_filled_size: int,
) -> V4GmoExactProtectionPlan:
    """Derive OCO prices from the actual average fill and frozen signal ATR."""

    tick = Decimal(H11_V4_GMO_PROTECTION_SPEC["tick_size"])
    if position_side not in (SignalDecision.BUY, SignalDecision.SELL):
        raise V4GmoProtectionError("position side must be BUY or SELL")
    if reconciled_average_fill_price <= 0 or frozen_signal_atr_24 <= 0:
        raise V4GmoProtectionError("fill price and frozen ATR must be positive")
    if type(reconciled_filled_size) is not int or not 0 < reconciled_filled_size <= 1_000:
        raise V4GmoProtectionError("reconciled fill size is outside the frozen bound")
    risk_width = frozen_signal_atr_24 * Decimal(
        H11_V4_GMO_PROTECTION_SPEC["stop_loss_atr_multiplier"]
    )
    reward_width = risk_width * Decimal(
        H11_V4_GMO_PROTECTION_SPEC["take_profit_r_multiple"]
    )
    if position_side is SignalDecision.BUY:
        stop = _round_down(reconciled_average_fill_price - risk_width, tick)
        take = _round_up(reconciled_average_fill_price + reward_width, tick)
        settlement_side = SignalDecision.SELL
    else:
        stop = _round_up(reconciled_average_fill_price + risk_width, tick)
        take = _round_down(reconciled_average_fill_price - reward_width, tick)
        settlement_side = SignalDecision.BUY
    if min(stop, take) <= 0:
        raise V4GmoProtectionError("derived protection prices must remain positive")
    return V4GmoExactProtectionPlan(
        symbol="USD_JPY",
        position_side=position_side,
        settlement_side=settlement_side,
        exact_filled_size=reconciled_filled_size,
        take_profit_price=take,
        stop_loss_price=stop,
        contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def _round_up(value: Decimal, increment: Decimal) -> Decimal:
    return (value / increment).to_integral_value(rounding=ROUND_CEILING) * increment


def _round_down(value: Decimal, increment: Decimal) -> Decimal:
    return (value / increment).to_integral_value(rounding=ROUND_FLOOR) * increment
