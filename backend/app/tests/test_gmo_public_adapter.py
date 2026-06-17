"""Offline tests for the GMO Public read-only adapter (app/shadow/gmo_public.py).

Uses httpx.MockTransport so NO real network call is made in pytest. Verifies envelope
handling, normalization into shadow Ticker/Candle, error mapping, and that no auth
header / API key is ever sent (Public read-only).
"""

import httpx
import pytest

from app.shadow.gmo_public import GmoPublicError, GmoPublicMarketDataClient
from app.shadow.models import Candle, Ticker


def _client(handler) -> GmoPublicMarketDataClient:
    transport = httpx.MockTransport(handler)
    return GmoPublicMarketDataClient(
        client=httpx.Client(base_url="https://example.test/public", transport=transport)
    )


def _ok(data):
    return httpx.Response(200, json={"status": 0, "data": data, "responsetime": "t"})


def test_fetch_ticker_normalizes_and_sends_no_auth() -> None:
    seen: dict[str, httpx.Headers] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        assert request.url.path.endswith("/v1/ticker")
        return _ok([{"symbol": "USD_JPY", "bid": "154.10", "ask": "154.14",
                     "timestamp": "2026-06-18T00:00:00.000Z", "status": "OPEN"}])

    t = _client(handler).fetch_ticker("USD_JPY")
    assert isinstance(t, Ticker)
    assert t.symbol == "USD_JPY" and t.bid == 154.10 and t.ask == 154.14
    assert round(t.mid, 3) == 154.12
    # no API key / auth header sent (Public read-only)
    h = seen["headers"]
    for key in ("authorization", "api-key", "api_key", "x-api-key"):
        assert key not in {k.lower() for k in h.keys()}


def test_fetch_candles_normalizes_klines() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/klines")
        assert request.url.params.get("symbol") == "USD_JPY"
        assert request.url.params.get("interval") == "1min"  # mapped/passed through
        return _ok([
            {"openTime": "1781308800000", "open": "154.0", "high": "154.2",
             "low": "153.9", "close": "154.1"},
            {"openTime": "1781308860000", "open": "154.1", "high": "154.3",
             "low": "154.0", "close": "154.2"},
        ])

    candles = _client(handler).fetch_candles("USD_JPY", "1min", limit=5, date="20260618")
    assert len(candles) == 2 and all(isinstance(c, Candle) for c in candles)
    assert candles[0].open == 154.0 and candles[0].close == 154.1
    assert candles[0].volume is None
    assert candles[0].time.startswith("20")  # ISO timestamp string


def test_internal_timeframe_is_mapped_to_gmo_interval() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("interval") == "5min"  # M5 -> 5min
        return _ok([{"openTime": "1781308800000", "open": "1", "high": "1",
                     "low": "1", "close": "1"}])

    _client(handler).fetch_candles("USD_JPY", "M5", date="20260618")


def test_error_envelope_raises_public_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": 1, "messages": [{"message_code": "ERR-5003"}]})

    with pytest.raises(GmoPublicError, match="rate limit"):
        _client(handler).fetch_ticker("USD_JPY")


def test_http_429_raises_public_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    with pytest.raises(GmoPublicError, match="429"):
        _client(handler).service_status()


def test_empty_klines_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _ok([])

    with pytest.raises(GmoPublicError, match="no klines"):
        _client(handler).fetch_candles("USD_JPY", "1min", date="20260618")


def test_invalid_numeric_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _ok([{"symbol": "USD_JPY", "bid": "abc", "ask": "1",
                     "timestamp": "t", "status": "OPEN"}])

    with pytest.raises(GmoPublicError, match="invalid numeric"):
        _client(handler).fetch_ticker("USD_JPY")
