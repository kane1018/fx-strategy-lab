"""No-POST tests for the runtime safe-read gate (fake client only)."""

from __future__ import annotations

import pathlib
from dataclasses import fields, replace

import pytest

from app.services.gmo_live_runtime_safe_read import (
    FakeRuntimeSafeReadClient,
    GmoRuntimeActivePendingSafeStatus,
    GmoRuntimeMarketSafeStatus,
    GmoRuntimePositionSafeStatus,
    GmoRuntimeSafeReadGateStatus,
    GmoRuntimeSafeReadSnapshot,
    GmoRuntimeSpreadSafeStatus,
    GmoRuntimeTickerFreshnessSafeStatus,
    evaluate_gmo_runtime_safe_read_gate,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_runtime_safe_read.py"
)


def _clear_snapshot(**overrides) -> GmoRuntimeSafeReadSnapshot:
    base = GmoRuntimeSafeReadSnapshot(
        performed=True,
        fresh=True,
        position_status=GmoRuntimePositionSafeStatus.NO_POSITION,
        position_count_safe=0,
        active_pending_status=GmoRuntimeActivePendingSafeStatus.CLEAR,
        active_order_count_safe=0,
        market_status=GmoRuntimeMarketSafeStatus.OPEN,
        ticker_status=GmoRuntimeTickerFreshnessSafeStatus.FRESH,
        spread_status=GmoRuntimeSpreadSafeStatus.WITHIN_LIMIT,
    )
    return replace(base, **overrides)


def test_default_snapshot_is_fail_closed() -> None:
    result = evaluate_gmo_runtime_safe_read_gate(GmoRuntimeSafeReadSnapshot())
    assert result.ready is False
    assert result.status is GmoRuntimeSafeReadGateStatus.RUNTIME_SAFE_READ_GATE_BLOCKED
    assert "RUNTIME_SAFE_READ_NOT_PERFORMED" in result.blocked_reasons
    assert "RUNTIME_POSITION_STATUS_NOT_NO_POSITION" in result.blocked_reasons
    assert bool(result) is False


def test_fully_clear_snapshot_is_ready() -> None:
    client = FakeRuntimeSafeReadClient(snapshot=_clear_snapshot())
    result = evaluate_gmo_runtime_safe_read_gate(client.read_safe_snapshot())
    assert result.ready is True
    assert (
        result.status
        is GmoRuntimeSafeReadGateStatus.RUNTIME_SAFE_READ_GATE_READY_NO_POSITION_CLEAR
    )
    assert result.blocked_reasons == ()


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"performed": False}, "RUNTIME_SAFE_READ_NOT_PERFORMED"),
        ({"fresh": False}, "RUNTIME_SAFE_READ_STALE"),
        (
            {"position_status": GmoRuntimePositionSafeStatus.ONE_POSITION_OPEN,
             "position_count_safe": 1},
            "RUNTIME_POSITION_STATUS_NOT_NO_POSITION",
        ),
        (
            {"position_status": GmoRuntimePositionSafeStatus.UNKNOWN,
             "position_count_safe": None},
            "RUNTIME_POSITION_COUNT_NOT_ZERO",
        ),
        (
            {"active_pending_status": GmoRuntimeActivePendingSafeStatus.CONFLICT,
             "active_order_count_safe": 1},
            "RUNTIME_ACTIVE_PENDING_NOT_CLEAR",
        ),
        (
            {"active_pending_status": GmoRuntimeActivePendingSafeStatus.UNKNOWN,
             "active_order_count_safe": None},
            "RUNTIME_ACTIVE_ORDER_COUNT_NOT_ZERO",
        ),
        ({"market_status": GmoRuntimeMarketSafeStatus.CLOSED}, "RUNTIME_MARKET_NOT_OPEN"),
        ({"market_status": GmoRuntimeMarketSafeStatus.UNKNOWN}, "RUNTIME_MARKET_NOT_OPEN"),
        (
            {"ticker_status": GmoRuntimeTickerFreshnessSafeStatus.STALE},
            "RUNTIME_TICKER_NOT_FRESH",
        ),
        (
            {"spread_status": GmoRuntimeSpreadSafeStatus.OUT_OF_LIMIT},
            "RUNTIME_SPREAD_NOT_WITHIN_LIMIT",
        ),
        (
            {"spread_status": GmoRuntimeSpreadSafeStatus.UNKNOWN},
            "RUNTIME_SPREAD_NOT_WITHIN_LIMIT",
        ),
    ],
)
def test_each_condition_fails_closed(overrides: dict, expected: str) -> None:
    result = evaluate_gmo_runtime_safe_read_gate(_clear_snapshot(**overrides))
    assert result.ready is False
    assert expected in result.blocked_reasons


def test_snapshot_has_no_raw_or_id_or_value_fields() -> None:
    field_names = {field.name for field in fields(GmoRuntimeSafeReadSnapshot)}
    for banned in (
        "raw", "payload", "position_id", "order_id", "trade_id", "price",
        "size", "pnl", "profit", "loss", "timestamp",
    ):
        assert not any(banned in name for name in field_names)


def test_module_does_not_read_env_or_network() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "httpx" not in text
    assert "requests" not in text
    assert "app.live_verification" not in text
    assert "live_order_once" not in text
