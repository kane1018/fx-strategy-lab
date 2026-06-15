"""Paper-trade replay over GMO Public klines (read-only data; NO real orders).

Fetches candles from the GMO Coin 外国為替FX Public API (no API key, no auth) and
replays them through the existing strategy as VIRTUAL paper trades, persisted as
PaperTrade rows. It never calls a Private endpoint, never places/closes a real
order, and never reads GMO_FX_API_KEY/SECRET.

Run from the backend/ directory, then view results with the performance report:
  .venv/bin/python -m scripts.paper_trade_gmo --symbol USD_JPY --interval 1min --limit 100
  .venv/bin/python -m scripts.performance_report
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.brokers import GmoFxBroker, GmoFxBrokerError  # noqa: E402
from app.brokers.gmo_fx_broker import GMO_INTERVALS  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.schemas.trading import ExecutionConfig, StrategyConfig, StrategyType  # noqa: E402
from app.services.gmo_paper_service import replay_paper_trades  # noqa: E402

# GMO interval string -> internal timeframe (reverse of GMO_INTERVALS).
_INTERVAL_TO_TIMEFRAME = {gmo: internal for internal, gmo in GMO_INTERVALS.items()}


def main() -> int:
    Base.metadata.create_all(bind=engine)
    parser = argparse.ArgumentParser(description="GMO Public paper-trade replay (no real orders).")
    parser.add_argument("--symbol", default="USD_JPY")
    parser.add_argument("--interval", default="1min", choices=sorted(_INTERVAL_TO_TIMEFRAME))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--date", default=None, help="YYYYMMDD (default: today, UTC)")
    parser.add_argument("--price-type", dest="price_type", default="BID", choices=["BID", "ASK"])
    parser.add_argument(
        "--strategy",
        default=StrategyType.MOVING_AVERAGE_CROSS.value,
        choices=[s.value for s in StrategyType],
    )
    args = parser.parse_args()

    timeframe = _INTERVAL_TO_TIMEFRAME[args.interval]
    strategy = StrategyConfig(strategy_type=StrategyType(args.strategy))
    execution = ExecutionConfig()

    print(f"GMO Public read-only fetch: {args.symbol} {args.interval} limit={args.limit} "
          f"(no orders, no private API)")
    try:
        broker = GmoFxBroker()  # public only; no API key read or sent
        status = broker.service_status()
        candles = broker.candles(
            args.symbol, timeframe, count=args.limit,
            price_type=args.price_type, date=args.date,
        )
    except GmoFxBrokerError as error:
        print(f"ABORT: GMO Public fetch failed ({error}). No paper trade run.")
        return 2

    print(f"service_status={status}  bars_fetched={len(candles)}  "
          f"range={candles[0].timestamp.isoformat()} .. {candles[-1].timestamp.isoformat()}")
    min_bars = max(strategy.long_period, strategy.rsi_period, strategy.breakout_period) + 5
    if len(candles) < min_bars:
        print(f"WARN: {len(candles)} bars < {min_bars} needed for '{args.strategy}'; "
              f"signals may be sparse. Use --date for a full past day or a larger --interval.")

    with SessionLocal() as db:
        result = replay_paper_trades(
            db,
            symbol=args.symbol,
            timeframe=timeframe,
            candles=candles,
            strategy=strategy,
            execution=execution,
        )

    print("\n=== replay result (paper, virtual) ===")
    print(f"session_id          = {result['session_id']}")
    print(f"bars                = {result['bars']}")
    print(f"completed_trades    = {result['completed_trades']}")
    print(f"open_position_count = {result['open_position_count']}")
    print(f"signals (buy/sell/hold) = {result['signal_counts']}")
    if result["completed_trades"] == 0 and result["open_position_count"] == 0:
        print("\nNo paper trades generated. Likely cause:")
        print("  - strategy produced no buy/sell over this window (see signal counts above)")
        print("  - too few bars; try --date for a full past day or a larger --interval/--limit")
    print("\nNext: .venv/bin/python -m scripts.performance_report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
