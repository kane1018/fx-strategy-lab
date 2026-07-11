"""Frozen H-11 v3 IFDOCO execution profile (pure, deterministic, no-POST).

The predictive model remains H-11 v2's single TREND expert. Version 3 changes
only the execution contract so a pending STOP entry and broker-side OCO
protection can be represented by one IFDOCO request plan.

This module performs no network access, reads no environment or credential,
and never calls a sender. The live activation gate remains closed until the
public capability review and a separate actual-activation step are complete.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import Enum

from app.private_api.order_builders import (
    GmoFxPrivateRequestPlan,
    build_gmo_fx_ifdoco_request_plan,
)
from app.strategies.h11_regime_moe import H11_V2_CONFIG_HASH

H11_V3_FROZEN_SPEC = {
    "hypothesis_id": "H-11_REGIME_ADAPTIVE_MOE_DIRECTIONAL_PROBABILITY",
    "version": 3,
    "prediction_model_config_hash": H11_V2_CONFIG_HASH,
    "prediction_model": "TREND_CONTINUATION_SINGLE_EXPERT",
    "entry_route": "POST /private/v1/ifoOrder",
    "entry_order_type": "IFDOCO",
    "first_execution_type": "STOP",
    "entry_trigger_atr_multiplier": "0.10",
    "sl_atr_multiplier": "1.50",
    "tp_r_multiple": "1.50",
    "position_size_units": 10_000,
    "max_entries_per_day": 1,
    "max_open_positions": 1,
    "operator_observation_required": True,
    "operator_observation_is_execution_gate": False,
    "per_trade_confirmation_required": False,
    "server_side_oco_required": True,
    "broker_native_pending_expiry_required": True,
    "automatic_cancel_allowed": False,
    "retry_allowed": False,
    "repost_allowed": False,
    "second_entry_post_allowed": False,
    "unknown_result_action": "HALT",
    "automatic_restart_after_stop": False,
}

H11_V3_CAPABILITY_CONTRACT = {
    "symbol": "USD_JPY",
    "min_open_order_size": "100",
    "size_step": "1",
    "tick_size": "0.001",
    "public_spec_review_date": "2026-07-11",
    "actual_account_capability_confirmed": False,
}


def _calculate_config_hash() -> str:
    canonical = json.dumps(
        H11_V3_FROZEN_SPEC,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _calculate_capability_contract_hash() -> str:
    canonical = json.dumps(
        H11_V3_CAPABILITY_CONTRACT,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("ascii")).hexdigest()


# Literal pinned after operator approval. A regression test requires it to
# equal the canonical spec above, so any change is forced to become v4.
H11_V3_CONFIG_HASH = (
    "sha256:737765dcbed89befceef8660d2b362c834344cc7e36e139d2ff75984914c3262"
)
H11_V3_CAPABILITY_CONTRACT_HASH = (
    "sha256:f35fe67b0129c310154bbc4b877d30165db98e6e5617547504145baa4af5f5d5"
)


class H11V3Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class H11V3ProfileError(ValueError):
    """Fail-closed profile validation error; never carries a secret or ID."""


class H11V3AutomaticPlanStatus(str, Enum):
    READY_NO_POST = "READY_NO_POST"
    BLOCKED_NO_SIGNAL = "BLOCKED_NO_SIGNAL"
    BLOCKED_CONFIG_MISMATCH = "BLOCKED_CONFIG_MISMATCH"


@dataclass(frozen=True)
class H11V3IfdocoCandidate:
    """Synthetic/future-internal values for one protected request plan.

    Values must never be rendered in a safe report. Tests use synthetic
    fixtures only. The actual activation step will construct the candidate
    inside a sealed boundary from fresh market data.
    """

    direction: H11V3Direction
    entry_stop_price: Decimal
    take_profit_price: Decimal
    stop_loss_price: Decimal
    size_units: int = 10_000


@dataclass(frozen=True)
class H11V3SafePreview:
    config_hash_matches: bool
    capability_contract_hash_matches: bool
    request_kind_safe_label: str
    first_execution_type_safe_label: str
    server_side_oco_required: bool
    retry_allowed: bool = False
    repost_allowed: bool = False
    second_entry_post_allowed: bool = False
    actual_post_allowed: bool = False
    actual_post_count: int = 0


@dataclass(frozen=True)
class H11V3AutomaticPlanDecision:
    """Internal plan decision with a permanently sanitized representation."""

    status: H11V3AutomaticPlanStatus
    reason_safe_label: str
    plan: GmoFxPrivateRequestPlan | None = None
    actual_post_allowed: bool = False
    actual_post_count: int = 0

    def __repr__(self) -> str:
        return "H11V3AutomaticPlanDecision(<sanitized>)"

    def __str__(self) -> str:
        return "H11V3AutomaticPlanDecision(<sanitized>)"

    def __bool__(self) -> bool:
        return False


def build_h11_v3_candidate(
    *,
    direction: H11V3Direction,
    reference_close: Decimal,
    atr_24: Decimal,
    price_increment: Decimal,
) -> H11V3IfdocoCandidate:
    """Apply the frozen 0.10 ATR trigger, 1.50 ATR SL, and 1.50R TP."""

    if reference_close <= 0 or atr_24 <= 0 or price_increment <= 0:
        raise H11V3ProfileError("reference, ATR, and price increment must be positive")
    if price_increment != Decimal(H11_V3_CAPABILITY_CONTRACT["tick_size"]):
        raise H11V3ProfileError("price increment differs from the v3 capability contract")

    trigger_width = atr_24 * Decimal("0.10")
    risk_width = atr_24 * Decimal("1.50")
    reward_width = risk_width * Decimal("1.50")
    if direction is H11V3Direction.BUY:
        entry = _round_up(reference_close + trigger_width, price_increment)
        stop = _round_down(entry - risk_width, price_increment)
        take = _round_up(entry + reward_width, price_increment)
    else:
        entry = _round_down(reference_close - trigger_width, price_increment)
        stop = _round_up(entry + risk_width, price_increment)
        take = _round_down(entry - reward_width, price_increment)

    if min(entry, stop, take) <= 0:
        raise H11V3ProfileError("derived protected prices must stay positive")
    return H11V3IfdocoCandidate(
        direction=direction,
        entry_stop_price=entry,
        take_profit_price=take,
        stop_loss_price=stop,
    )


def build_h11_v3_ifdoco_plan_no_post(
    *,
    candidate: H11V3IfdocoCandidate,
    symbol: str,
    client_order_id: str | None = None,
) -> GmoFxPrivateRequestPlan:
    """Build the pure IFDOCO plan; never sign or send it."""

    if symbol != H11_V3_CAPABILITY_CONTRACT["symbol"]:
        raise H11V3ProfileError("symbol differs from the v3 capability contract")
    if candidate.size_units != H11_V3_FROZEN_SPEC["position_size_units"]:
        raise H11V3ProfileError("candidate size differs from frozen v3 size")
    size = str(candidate.size_units)
    return build_gmo_fx_ifdoco_request_plan(
        symbol=symbol,
        first_side=candidate.direction.value,
        first_size=size,
        first_price=_decimal_string(candidate.entry_stop_price),
        second_size=size,
        second_limit_price=_decimal_string(candidate.take_profit_price),
        second_stop_price=_decimal_string(candidate.stop_loss_price),
        client_order_id=client_order_id,
    )


def build_h11_v3_automatic_plan_no_post(
    *,
    preview_signal_safe_label: str,
    expected_config_hash: str,
    reference_close: Decimal,
    atr_24: Decimal,
    price_increment: Decimal,
    symbol: str,
    client_order_id: str | None = None,
) -> H11V3AutomaticPlanDecision:
    """Map the frozen H-11 preview signal to a protected plan without sending.

    HOLD, UNKNOWN, missing, or any unrecognized label is a blocked no-op. This
    is the v3 automatic decision adapter, but it has no transport capability.
    """

    if expected_config_hash != H11_V3_CONFIG_HASH:
        return H11V3AutomaticPlanDecision(
            status=H11V3AutomaticPlanStatus.BLOCKED_CONFIG_MISMATCH,
            reason_safe_label="V3_CONFIG_HASH_MISMATCH",
        )
    direction_by_signal = {
        "AUTO_PREVIEW_SIGNAL_BUY": H11V3Direction.BUY,
        "AUTO_PREVIEW_SIGNAL_SELL": H11V3Direction.SELL,
    }
    direction = direction_by_signal.get(preview_signal_safe_label)
    if direction is None:
        return H11V3AutomaticPlanDecision(
            status=H11V3AutomaticPlanStatus.BLOCKED_NO_SIGNAL,
            reason_safe_label="NO_EXECUTABLE_V3_SIGNAL",
        )
    candidate = build_h11_v3_candidate(
        direction=direction,
        reference_close=reference_close,
        atr_24=atr_24,
        price_increment=price_increment,
    )
    plan = build_h11_v3_ifdoco_plan_no_post(
        candidate=candidate,
        symbol=symbol,
        client_order_id=client_order_id,
    )
    return H11V3AutomaticPlanDecision(
        status=H11V3AutomaticPlanStatus.READY_NO_POST,
        reason_safe_label="V3_IFDOCO_PLAN_READY_NO_POST",
        plan=plan,
    )


def build_h11_v3_safe_preview() -> H11V3SafePreview:
    return H11V3SafePreview(
        config_hash_matches=H11_V3_CONFIG_HASH == _calculate_config_hash(),
        capability_contract_hash_matches=(
            H11_V3_CAPABILITY_CONTRACT_HASH
            == _calculate_capability_contract_hash()
        ),
        request_kind_safe_label="IFDOCO_PROTECTED_ENTRY",
        first_execution_type_safe_label="STOP",
        server_side_oco_required=True,
    )


def _round_up(value: Decimal, increment: Decimal) -> Decimal:
    return (value / increment).to_integral_value(rounding=ROUND_CEILING) * increment


def _round_down(value: Decimal, increment: Decimal) -> Decimal:
    return (value / increment).to_integral_value(rounding=ROUND_FLOOR) * increment


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")
