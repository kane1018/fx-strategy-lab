"""Read-only adapter from a sanitized formal signal snapshot to Phase A."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.h11_auto.contracts import (
    FormalHorizon,
    FormalSignal,
    H11AutoContractError,
    SignalDecision,
)

_DIRECTION_MAP = {
    "BUY": SignalDecision.BUY,
    "買い": SignalDecision.BUY,
    "SELL": SignalDecision.SELL,
    "売り": SignalDecision.SELL,
    "STAY": SignalDecision.STAY,
    "NO_TRADE": SignalDecision.STAY,
    "見送り": SignalDecision.STAY,
}
_ALLOWED_SNAPSHOT_KEYS = frozenset(
    {
        "horizon",
        "direction",
        "status",
        "p_up",
        "origin_time_utc",
        "model_config_hash",
        "recorded_mode",
    }
)


def adapt_sanitized_formal_signal(
    snapshot: Mapping[str, Any], *, strategy_version: str
) -> FormalSignal:
    """Adapt values already present in the localhost formal signal response.

    The adapter performs no file, database, network, broker, or credential read.
    It rejects rolling/replayed/blocked snapshots and never infers a missing
    strategy version.
    """

    if not isinstance(strategy_version, str) or not strategy_version.strip():
        raise H11AutoContractError("strategy version must be explicit")
    if snapshot.get("status") != "OK":
        raise H11AutoContractError("blocked signal snapshot is not actionable")
    if snapshot.get("recorded_mode") != "PROSPECTIVE":
        raise H11AutoContractError("only prospective formal snapshots are accepted")
    if "estimate_mode" in snapshot or snapshot.get("formal_signal") is False:
        raise H11AutoContractError("rolling estimate snapshot is not accepted")
    if not set(snapshot).issubset(_ALLOWED_SNAPSHOT_KEYS):
        raise H11AutoContractError("formal signal snapshot contains unsafe fields")
    try:
        horizon = FormalHorizon(str(snapshot["horizon"]))
        decision = _DIRECTION_MAP[str(snapshot["direction"]).upper()]
        probability_up = Decimal(str(snapshot["p_up"]))
        origin = datetime.fromisoformat(str(snapshot["origin_time_utc"]))
        raw_config_hash = snapshot["model_config_hash"]
    except (KeyError, TypeError, ValueError, InvalidOperation) as error:
        raise H11AutoContractError("formal signal snapshot is malformed") from error
    if not isinstance(raw_config_hash, str) or not raw_config_hash.strip():
        raise H11AutoContractError("formal signal config hash is missing")
    config_hash = raw_config_hash
    if origin.tzinfo is None:
        raise H11AutoContractError("formal signal origin must be timezone-aware")
    origin = origin.astimezone(UTC)
    validity_minutes = 10 if horizon is FormalHorizon.MINUTES_10 else 30
    return FormalSignal(
        strategy_version=strategy_version,
        signal_config_hash=config_hash,
        horizon=horizon,
        observed_at_utc=origin,
        valid_until_utc=origin + timedelta(minutes=validity_minutes),
        decision=decision,
        probability_up=probability_up,
    )
