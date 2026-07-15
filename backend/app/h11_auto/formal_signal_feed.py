"""Pure contract for a sanitized manual-current signal handoff."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.h11_auto.contracts import FormalHorizon, FormalSignal, H11AutoContractError
from app.h11_auto.signal_adapter import adapt_sanitized_formal_signal

_ALLOWED_SIGNAL_KEYS = frozenset(
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


def extract_formal_signal_from_sanitized_current(
    current: Mapping[str, Any],
    *,
    selected_horizon: FormalHorizon,
    strategy_version: str,
) -> FormalSignal:
    """Select one formal signal without importing or calling the manual UI.

    The caller must provide an already-sanitized mapping containing only a
    `signals` sequence.  Broker sync, trade-plan, execution, position, and raw
    fields are rejected instead of ignored.
    """

    if set(current) != {"signals"}:
        raise H11AutoContractError("current handoff contains non-signal fields")
    records = current.get("signals")
    if isinstance(records, str | bytes) or not isinstance(records, Sequence):
        raise H11AutoContractError("current handoff signals are malformed")
    matches: list[Mapping[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise H11AutoContractError("current handoff signal is malformed")
        if not set(record).issubset(_ALLOWED_SIGNAL_KEYS):
            raise H11AutoContractError("current handoff signal contains unsafe fields")
        if record.get("horizon") == selected_horizon.value:
            matches.append(record)
    if len(matches) != 1:
        raise H11AutoContractError("selected formal horizon must occur exactly once")
    return adapt_sanitized_formal_signal(
        matches[0],
        strategy_version=strategy_version,
    )
