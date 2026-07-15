from __future__ import annotations

from copy import deepcopy

import pytest

from app.h11_auto.contracts import FormalHorizon, H11AutoContractError, SignalDecision
from app.h11_auto.signal_adapter import adapt_sanitized_formal_signal


def snapshot() -> dict[str, object]:
    return {
        "horizon": "10m",
        "direction": "買い",
        "status": "OK",
        "p_up": 0.61,
        "origin_time_utc": "2026-07-15T03:00:00+00:00",
        "model_config_hash": "sha256:formal-signal-config",
        "recorded_mode": "PROSPECTIVE",
    }


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        ("買い", SignalDecision.BUY),
        ("売り", SignalDecision.SELL),
        ("見送り", SignalDecision.STAY),
        ("BUY", SignalDecision.BUY),
        ("SELL", SignalDecision.SELL),
        ("STAY", SignalDecision.STAY),
    ],
)
def test_adapts_existing_sanitized_formal_shape_without_manual_import(
    direction: str, expected: SignalDecision
) -> None:
    payload = snapshot()
    payload["direction"] = direction
    formal = adapt_sanitized_formal_signal(payload, strategy_version="SHORT_V1")
    assert formal.decision is expected
    assert formal.horizon is FormalHorizon.MINUTES_10
    assert formal.signal_config_hash == "sha256:formal-signal-config"
    assert formal.valid_until_utc.isoformat() == "2026-07-15T03:10:00+00:00"


def test_30m_snapshot_receives_30m_validity() -> None:
    payload = snapshot()
    payload["horizon"] = "30m"
    formal = adapt_sanitized_formal_signal(payload, strategy_version="SHORT_V1")
    assert formal.horizon is FormalHorizon.MINUTES_30
    assert formal.valid_until_utc.isoformat() == "2026-07-15T03:30:00+00:00"


@pytest.mark.parametrize(
    "mutation",
    [
        {"status": "BLOCKED"},
        {"recorded_mode": "REPLAYED_AFTER_MATURITY"},
        {"recorded_mode": None},
        {"horizon": "24h"},
        {"origin_time_utc": None},
        {"model_config_hash": None},
        {"p_up": None},
        {"direction": "判定不可"},
        {"estimate_mode": "TICK_NATIVE_ROLLING_60S", "formal_signal": False},
    ],
)
def test_rejects_blocked_replayed_rolling_or_malformed_snapshot(
    mutation: dict[str, object]
) -> None:
    payload = deepcopy(snapshot())
    payload.update(mutation)
    with pytest.raises(H11AutoContractError):
        adapt_sanitized_formal_signal(payload, strategy_version="SHORT_V1")


def test_strategy_version_is_never_inferred() -> None:
    with pytest.raises(H11AutoContractError, match="explicit"):
        adapt_sanitized_formal_signal(snapshot(), strategy_version="")


@pytest.mark.parametrize(
    "unsafe_field",
    ("raw_response", "credential", "position_id", "execution_id", "broker_state"),
)
def test_rejects_non_signal_or_sensitive_fields(unsafe_field: str) -> None:
    payload = snapshot()
    payload[unsafe_field] = "must-not-be-read-as-signal"
    with pytest.raises(H11AutoContractError, match="unsafe fields"):
        adapt_sanitized_formal_signal(payload, strategy_version="SHORT_V1")
