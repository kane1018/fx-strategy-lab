"""Fetch and cache USD_JPY M1 history from the GMO PUBLIC API for backtesting.

Read-only market-data tooling: public endpoints only, no credentials, no broker
writes, no coordinator/ledger interaction. Days already cached are skipped, so
the script is resumable and never re-downloads. Weekend/holiday days simply have
no klines and are recorded as empty so they are not retried.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from app.shadow.gmo_public import GmoPublicError, GmoPublicMarketDataClient

REPOSITORY = Path(__file__).resolve().parents[2]
CACHE_ROOT = REPOSITORY / "backend" / "market_data" / "backtest"
CACHE_CSV = CACHE_ROOT / "usdjpy_m1_history.csv"
CACHE_STATE = CACHE_ROOT / "fetched_days.json"
START_DAY = date(2025, 1, 2)
REQUEST_GAP_SECONDS = 0.25


def main() -> int:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    fetched: dict[str, int] = {}
    if CACHE_STATE.is_file():
        fetched = json.loads(CACHE_STATE.read_text(encoding="utf-8"))
    new_rows: list[str] = []
    if not CACHE_CSV.is_file():
        CACHE_CSV.write_text("time_utc,open,high,low,close\n", encoding="utf-8")
    client = GmoPublicMarketDataClient()
    day = START_DAY
    today = datetime.now(UTC).date()
    requested = 0
    try:
        while day <= today:
            label = day.strftime("%Y%m%d")
            if label not in fetched:
                try:
                    candles = client.fetch_candles(
                        "USD_JPY", "M1", limit=0, price_type="BID", date=label
                    )
                except GmoPublicError:
                    candles = []
                for candle in candles:
                    new_rows.append(
                        f"{candle.time},{candle.open},{candle.high},"
                        f"{candle.low},{candle.close}"
                    )
                fetched[label] = len(candles)
                requested += 1
                if requested % 40 == 0:
                    with CACHE_CSV.open("a", encoding="utf-8") as handle:
                        handle.write("\n".join(new_rows) + ("\n" if new_rows else ""))
                    new_rows = []
                    CACHE_STATE.write_text(json.dumps(fetched), encoding="utf-8")
                    print(f"progress: {label} ({requested} days fetched)", flush=True)
                time.sleep(REQUEST_GAP_SECONDS)
            day += timedelta(days=1)
    finally:
        client.client.close()
        if new_rows:
            with CACHE_CSV.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(new_rows) + "\n")
        CACHE_STATE.write_text(json.dumps(fetched), encoding="utf-8")
    total_days = sum(1 for count in fetched.values() if count)
    print(f"done: {len(fetched)} days recorded, {total_days} with data", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
