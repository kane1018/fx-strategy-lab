"""Market-data normalization + client interface for shadow trading (local-only).

Public market data only (price / candles). NO Private API, NO API key, NO orders.
The real GMO Public API adapter is intentionally NOT implemented here: its exact
endpoints/response shapes must be confirmed against the official spec first (Phase 2B).
Until then we define (a) a client Protocol, (b) normalizers from a documented *mock*
shape to the internal Candle/Ticker, and (c) an in-memory MockMarketDataClient for tests.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from app.shadow.models import Candle, Ticker


class MarketDataClient(Protocol):
    """Read-only public market-data source (interface).

    A future Phase 2B adapter (e.g. GMO Public API) implements this. It must be
    PUBLIC/read-only: no auth, no API key, no order capability.
    """

    def fetch_ticker(self, symbol: str) -> Ticker: ...

    def fetch_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]: ...


# NOTE: the dict keys below are a *mock* shape for tests/design, not a claim about the
# real GMO Public API. Confirm the official schema before writing the real adapter.
def normalize_ticker(raw: Mapping[str, object]) -> Ticker:
    """Normalize a mock public-ticker dict to the internal Ticker."""
    return Ticker(
        symbol=str(raw["symbol"]),
        bid=float(raw["bid"]),  # type: ignore[arg-type]
        ask=float(raw["ask"]),  # type: ignore[arg-type]
        time=str(raw.get("timestamp", "")),
    )


def normalize_candles(raw: Sequence[Mapping[str, object]]) -> list[Candle]:
    """Normalize a sequence of mock OHLC dicts to internal Candles."""
    candles: list[Candle] = []
    for row in raw:
        candles.append(
            Candle(
                time=str(row.get("time", "")),
                open=float(row["open"]),  # type: ignore[arg-type]
                high=float(row["high"]),  # type: ignore[arg-type]
                low=float(row["low"]),  # type: ignore[arg-type]
                close=float(row["close"]),  # type: ignore[arg-type]
                volume=float(row["volume"]) if "volume" in row else None,  # type: ignore[arg-type]
            )
        )
    return candles


class MockMarketDataClient:
    """In-memory MarketDataClient for tests/local runs. No network, no auth.

    Holds pre-built fixtures so shadow trading can be exercised deterministically without
    touching any real API.
    """

    def __init__(
        self,
        tickers: Mapping[str, Ticker] | None = None,
        candles: Mapping[str, list[Candle]] | None = None,
    ) -> None:
        self._tickers = dict(tickers or {})
        self._candles = dict(candles or {})

    def fetch_ticker(self, symbol: str) -> Ticker:
        return self._tickers[symbol]

    def fetch_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        return list(self._candles.get(symbol, []))[-limit:]
