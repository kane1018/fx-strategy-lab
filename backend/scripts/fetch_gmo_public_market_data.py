"""Local CLI: fetch GMO 外国為替FX **Public** market data (read-only, no auth).

GET-only against the Public API (status / ticker / klines). NO API key / secret / .env,
NO Private API, NO orders. Prints to stdout by default and does NOT save anything
(implicitly avoids committing real API responses to the repo). For local verification.

Usage:
    python -m scripts.fetch_gmo_public_market_data --kind status
    python -m scripts.fetch_gmo_public_market_data --kind ticker --symbol USD_JPY
    python -m scripts.fetch_gmo_public_market_data --kind candles --symbol USD_JPY \
        --interval 1min --date 20260618 --limit 5
"""

from __future__ import annotations

import argparse
from dataclasses import asdict

from app.shadow.gmo_public import GmoPublicError, GmoPublicMarketDataClient


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch GMO Public market data (read-only, no auth, no orders)."
    )
    parser.add_argument("--kind", choices=["status", "ticker", "candles"], default="ticker")
    parser.add_argument("--symbol", default="USD_JPY", help="BASE_QUOTE, e.g. USD_JPY")
    parser.add_argument("--interval", default="1min", help="GMO interval or internal TF (M1..)")
    parser.add_argument("--date", default=None, help="YYYYMMDD (klines; default today UTC)")
    parser.add_argument("--limit", type=int, default=5, help="max candles to print")
    parser.add_argument("--price-type", default="BID", choices=["BID", "ASK"])
    args = parser.parse_args()

    client = GmoPublicMarketDataClient()
    try:
        if args.kind == "status":
            print(f"status: {client.service_status()}")
        elif args.kind == "ticker":
            print(asdict(client.fetch_ticker(args.symbol)))
        else:
            candles = client.fetch_candles(
                args.symbol, args.interval, args.limit, price_type=args.price_type, date=args.date
            )
            for candle in candles:
                print(asdict(candle))
    except GmoPublicError as error:
        # Do not swallow; do not fall back to any authenticated/Private path.
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
