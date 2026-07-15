from __future__ import annotations

from copy import deepcopy

import pytest

from app.h11_auto.contracts import (
    FormalHorizon,
    H11AutoContractError,
    SignalDecision,
)
from app.h11_auto.formal_signal_feed import (
    extract_formal_signal_from_sanitized_current,
)


def _record(horizon: str, direction: str, p_up: float) -> dict[str, object]:
    return {
        "horizon": horizon,
        "direction": direction,
        "status": "OK",
        "p_up": p_up,
        "origin_time_utc": "2026-07-15T05:00:00+00:00",
        "model_config_hash": f"sha256:{horizon}-formal-config",
        "recorded_mode": "PROSPECTIVE",
    }


def _current() -> dict[str, object]:
    return {
        "signals": [
            _record("10m", "BUY", 0.61),
            _record("30m", "SELL", 0.39),
            _record("24h", "STAY", 0.5),
        ]
    }


def test_extracts_exact_selected_formal_horizon_from_sanitized_mapping() -> None:
    signal = extract_formal_signal_from_sanitized_current(
        _current(),
        selected_horizon=FormalHorizon.MINUTES_30,
        strategy_version="SHORT_V1",
    )
    assert signal.horizon is FormalHorizon.MINUTES_30
    assert signal.decision is SignalDecision.SELL
    assert signal.signal_config_hash == "sha256:30m-formal-config"


@pytest.mark.parametrize(
    "unsafe_field",
    ["broker_sync", "open_positions", "executions", "trade_plans", "raw_response"],
)
def test_rejects_top_level_non_signal_or_broker_fields(unsafe_field: str) -> None:
    payload = _current()
    payload[unsafe_field] = object()
    with pytest.raises(H11AutoContractError, match="non-signal"):
        extract_formal_signal_from_sanitized_current(
            payload,
            selected_horizon=FormalHorizon.MINUTES_10,
            strategy_version="SHORT_V1",
        )


def test_rejects_unsafe_fields_inside_signal_instead_of_ignoring_them() -> None:
    payload = _current()
    records = payload["signals"]
    assert isinstance(records, list)
    records[0]["forecast_id"] = "should-not-cross-boundary"
    with pytest.raises(H11AutoContractError, match="unsafe"):
        extract_formal_signal_from_sanitized_current(
            payload,
            selected_horizon=FormalHorizon.MINUTES_10,
            strategy_version="SHORT_V1",
        )


def test_rejects_missing_duplicate_rolling_or_replayed_selected_signal() -> None:
    missing = _current()
    missing["signals"] = [record for record in missing["signals"] if record["horizon"] != "10m"]  # type: ignore[index]
    duplicate = _current()
    duplicate["signals"].append(deepcopy(duplicate["signals"][0]))  # type: ignore[union-attr,index]
    rolling = _current()
    rolling["signals"][0]["estimate_mode"] = "TICK_NATIVE_ROLLING_60S"  # type: ignore[index]
    replayed = _current()
    replayed["signals"][0]["recorded_mode"] = "REPLAYED_AFTER_MATURITY"  # type: ignore[index]
    for payload in (missing, duplicate, rolling, replayed):
        with pytest.raises(H11AutoContractError):
            extract_formal_signal_from_sanitized_current(
                payload,
                selected_horizon=FormalHorizon.MINUTES_10,
                strategy_version="SHORT_V1",
            )
