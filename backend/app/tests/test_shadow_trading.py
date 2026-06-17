"""Tests for the local-only shadow-trading foundation (app/shadow/*).

Mock/fixture based, no network, no broker, no API key. Verifies normalization, that
virtual orders are never real, position/PnL bookkeeping, safety flags, and the max-units
halt. The real GMO Public API adapter is out of scope (Phase 2B).
"""

import pytest

from app.shadow.market_data import (
    MockMarketDataClient,
    normalize_candles,
    normalize_ticker,
)
from app.shadow.models import (
    Candle,
    Signal,
    Ticker,
    VirtualOrder,
    VirtualPosition,
    shadow_safety,
)
from app.shadow.service import ShadowTrader

# --- mock public market data (NOT a claim about the real GMO schema) ---
_MOCK_TICKER = {
    "symbol": "USD_JPY",
    "bid": 154.10,
    "ask": 154.14,
    "timestamp": "2026-06-17T00:00:00",
}
_MOCK_CANDLES = [
    {"time": "t1", "open": 154.0, "high": 154.2, "low": 153.9, "close": 154.1, "volume": 10},
    {"time": "t2", "open": 154.1, "high": 154.3, "low": 154.0, "close": 154.2},
]


def _buy(_candles):
    return Signal(side="buy", reason="mock always-buy")


def _flat(_candles):
    return Signal(side="flat", reason="mock no-op")


def test_normalize_ticker_and_candles() -> None:
    t = normalize_ticker(_MOCK_TICKER)
    assert isinstance(t, Ticker) and t.symbol == "USD_JPY"
    assert t.bid == 154.10 and t.ask == 154.14
    assert round(t.mid, 3) == 154.12
    candles = normalize_candles(_MOCK_CANDLES)
    assert len(candles) == 2 and all(isinstance(c, Candle) for c in candles)
    assert candles[0].volume == 10 and candles[1].volume is None


def test_mock_client_is_offline() -> None:
    t = normalize_ticker(_MOCK_TICKER)
    candles = normalize_candles(_MOCK_CANDLES)
    client = MockMarketDataClient(tickers={"USD_JPY": t}, candles={"USD_JPY": candles})
    assert client.fetch_ticker("USD_JPY").symbol == "USD_JPY"
    assert len(client.fetch_candles("USD_JPY", "1min", 1)) == 1  # respects limit


def test_virtual_order_cannot_be_real() -> None:
    o = VirtualOrder(side="buy", units=1, price=154.14)
    assert o.real_order is False
    with pytest.raises(ValueError):
        VirtualOrder(side="buy", units=1, price=1.0, real_order=True)
    with pytest.raises(ValueError):
        VirtualOrder(side="buy", units=0, price=1.0)


def test_shadow_safety_flags_are_read_only() -> None:
    s = shadow_safety()
    assert s["real_order"] is False
    assert s["private_api_used"] is False
    assert s["api_key_used"] is False
    assert s["no_order_execution"] is True
    assert s["live_trading_environment_enabled"] is False


def test_step_produces_virtual_order_and_updates_position() -> None:
    t = normalize_ticker(_MOCK_TICKER)
    candles = normalize_candles(_MOCK_CANDLES)
    trader = ShadowTrader("USD_JPY", _buy, units=2)
    event = trader.step(candles, t)
    assert event.virtual_order is not None
    assert event.virtual_order.real_order is False  # never a real order
    assert event.position_side == "long" and event.position_units == 2
    assert event.safety["real_order"] is False and event.safety["no_order_execution"] is True
    assert event.halted is False


def test_virtual_pnl_moves_with_price() -> None:
    pos = VirtualPosition(symbol="USD_JPY")
    pos.apply_fill(VirtualOrder(side="buy", units=10, price=154.0))
    assert pos.side == "long" and pos.units == 10
    assert pos.unrealized_pnl(154.5) == pytest.approx((154.5 - 154.0) * 10)
    assert pos.unrealized_pnl(153.5) == pytest.approx((153.5 - 154.0) * 10)


def test_flat_signal_creates_no_order() -> None:
    t = normalize_ticker(_MOCK_TICKER)
    trader = ShadowTrader("USD_JPY", _flat)
    event = trader.step(normalize_candles(_MOCK_CANDLES), t)
    assert event.virtual_order is None
    assert event.position_side == "flat" and event.virtual_pnl == 0.0


def test_max_units_halts_without_position_change() -> None:
    t = normalize_ticker(_MOCK_TICKER)
    trader = ShadowTrader("USD_JPY", _buy, units=500, max_units=100)
    event = trader.step(normalize_candles(_MOCK_CANDLES), t)
    assert event.halted is True
    assert "exceed max_units" in event.halt_reason
    assert event.virtual_order is None  # no order applied when halted
    assert event.position_side == "flat" and event.position_units == 0
