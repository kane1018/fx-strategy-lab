"""Fake-only tests for the Public-only, credential-free entry-gate provider."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.services.h11_v4_unattended_live_entry_gate import (
    ENTRY_GATE_QUOTE_UNAVAILABLE,
)
from app.services.h11_v4_unattended_live_entry_gate_provider import (
    unattended_live_entry_gate_provider,
)

NOW = datetime(2026, 7, 25, 3, 0, 1, tzinfo=UTC)


def _client(*, status: str = "OPEN", ticker_status: str = "OPEN", spread_pips: str = "1.0"):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/public/v1/status":
            return httpx.Response(200, json={"status": 0, "data": {"status": status}})
        assert request.url.path == "/public/v1/ticker"
        ask = 160 + float(spread_pips) * 0.01
        return httpx.Response(
            200,
            json={
                "status": 0,
                "data": [
                    {
                        "symbol": "USD_JPY",
                        "ask": f"{ask:.3f}",
                        "bid": "160.000",
                        "timestamp": "2026-07-25T03:00:00Z",
                        "status": ticker_status,
                    }
                ],
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_clear_quote_returns_empty_tuple() -> None:
    client = _client()
    assert unattended_live_entry_gate_provider(NOW, client=client) == ()
    client.close()


def test_market_not_open_is_blocked() -> None:
    client = _client(status="CLOSE")
    reasons = unattended_live_entry_gate_provider(NOW, client=client)
    assert "ENTRY_GATE_MARKET_NOT_OPEN" in reasons
    client.close()


def test_ticker_row_not_open_also_blocks_market_open_conjunction() -> None:
    # market_open must be the CONJUNCTION of /status and the ticker row's own
    # status -- /status alone reporting OPEN is not sufficient.
    client = _client(status="OPEN", ticker_status="CLOSE")
    reasons = unattended_live_entry_gate_provider(NOW, client=client)
    assert "ENTRY_GATE_MARKET_NOT_OPEN" in reasons
    client.close()


def test_wide_spread_is_blocked() -> None:
    client = _client(spread_pips="3.0")
    reasons = unattended_live_entry_gate_provider(NOW, client=client)
    assert "ENTRY_GATE_SPREAD_LIMIT_EXCEEDED" in reasons
    client.close()


def test_stale_quote_is_blocked() -> None:
    client = _client()
    stale_now = datetime(2026, 7, 25, 3, 10, 0, tzinfo=UTC)
    reasons = unattended_live_entry_gate_provider(stale_now, client=client)
    assert "ENTRY_GATE_QUOTE_NOT_FRESH" in reasons
    client.close()


def test_http_failure_collapses_to_quote_unavailable_never_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert unattended_live_entry_gate_provider(NOW, client=client) == (
        ENTRY_GATE_QUOTE_UNAVAILABLE,
    )
    client.close()


def test_malformed_ticker_schema_collapses_to_quote_unavailable_never_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/public/v1/status":
            return httpx.Response(200, json={"status": 0, "data": {"status": "OPEN"}})
        return httpx.Response(200, json={"status": 0, "data": "not-a-list"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert unattended_live_entry_gate_provider(NOW, client=client) == (
        ENTRY_GATE_QUOTE_UNAVAILABLE,
    )
    client.close()


def test_ambiguous_ticker_rows_collapses_to_quote_unavailable_never_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/public/v1/status":
            return httpx.Response(200, json={"status": 0, "data": {"status": "OPEN"}})
        row = {
            "symbol": "USD_JPY",
            "ask": "160.010",
            "bid": "160.000",
            "timestamp": "2026-07-25T03:00:00Z",
            "status": "OPEN",
        }
        return httpx.Response(200, json={"status": 0, "data": [row, row]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert unattended_live_entry_gate_provider(NOW, client=client) == (
        ENTRY_GATE_QUOTE_UNAVAILABLE,
    )
    client.close()


def test_non_numeric_bid_ask_collapses_to_quote_unavailable_never_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/public/v1/status":
            return httpx.Response(200, json={"status": 0, "data": {"status": "OPEN"}})
        return httpx.Response(
            200,
            json={
                "status": 0,
                "data": [
                    {
                        "symbol": "USD_JPY",
                        "ask": "not-a-number",
                        "bid": "160.000",
                        "timestamp": "2026-07-25T03:00:00Z",
                        "status": "OPEN",
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert unattended_live_entry_gate_provider(NOW, client=client) == (
        ENTRY_GATE_QUOTE_UNAVAILABLE,
    )
    client.close()


def test_missing_timestamp_collapses_to_quote_unavailable_never_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/public/v1/status":
            return httpx.Response(200, json={"status": 0, "data": {"status": "OPEN"}})
        return httpx.Response(
            200,
            json={
                "status": 0,
                "data": [
                    {
                        "symbol": "USD_JPY",
                        "ask": "160.010",
                        "bid": "160.000",
                        "status": "OPEN",
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert unattended_live_entry_gate_provider(NOW, client=client) == (
        ENTRY_GATE_QUOTE_UNAVAILABLE,
    )
    client.close()


def test_network_error_collapses_to_quote_unavailable_never_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert unattended_live_entry_gate_provider(NOW, client=client) == (
        ENTRY_GATE_QUOTE_UNAVAILABLE,
    )
    client.close()
