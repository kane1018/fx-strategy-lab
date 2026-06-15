"""Batch GMO Public paper-trade replay across symbols x strategies (read-only).

Fetches each symbol's klines once from the GMO Public API (no key, no auth) and
replays them through each strategy as virtual paper trades, persisting PaperTrade
rows. No real orders, no Private API, no API key/secret. Prints a comparison
table; use scripts.performance_report for the authoritative aggregation.

  .venv/bin/python -m scripts.paper_trade_gmo_batch --date 20260612
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.brokers import GmoFxBroker, GmoFxBrokerError  # noqa: E402
from app.brokers.gmo_fx_broker import GMO_INTERVALS  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import PaperTrade  # noqa: E402
from app.schemas.trading import ExecutionConfig, StrategyConfig, StrategyType  # noqa: E402
from app.services.gmo_paper_service import replay_paper_trades  # noqa: E402
from app.services.performance_service import _trade_stats  # noqa: E402

_INTERVAL_TO_TIMEFRAME = {gmo: internal for internal, gmo in GMO_INTERVALS.items()}
_ROW = "{:<8} {:<20} {:>5} {:>7} {:>9} {:>9} {:>7} {:>5}"


def main() -> int:
    Base.metadata.create_all(bind=engine)
    parser = argparse.ArgumentParser(description="Batch GMO Public paper replay (no real orders).")
    parser.add_argument("--symbols", default="USD_JPY,EUR_JPY,GBP_JPY,AUD_JPY")
    parser.add_argument("--strategies", default="moving_average_cross,rsi_reversal,breakout")
    parser.add_argument("--interval", default="1min", choices=sorted(_INTERVAL_TO_TIMEFRAME))
    parser.add_argument("--date", default=None, help="YYYYMMDD (default: today, UTC)")
    parser.add_argument("--limit", type=int, default=1500)
    args = parser.parse_args()

    timeframe = _INTERVAL_TO_TIMEFRAME[args.interval]
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]

    broker = GmoFxBroker()  # public only; no API key read or sent
    print(f"service_status={broker.service_status()}  date={args.date or 'today'}  "
          f"interval={args.interval}  (read-only, no orders, no private API)")

    rows: list[tuple[str, str, dict, int]] = []
    for symbol in symbols:
        try:
            candles = broker.candles(symbol, timeframe, count=args.limit, date=args.date)
        except GmoFxBrokerError as error:
            print(f"  [skip] {symbol}: {error}")
            continue
        print(f"  {symbol}: bars={len(candles)}  "
              f"{candles[0].timestamp.date()}..{candles[-1].timestamp.date()}")
        for strat in strategies:
            strategy = StrategyConfig(strategy_type=StrategyType(strat))
            with SessionLocal() as db:
                result = replay_paper_trades(
                    db, symbol=symbol, timeframe=timeframe,
                    candles=candles, strategy=strategy, execution=ExecutionConfig(),
                )
                closed = db.scalars(
                    select(PaperTrade).where(
                        PaperTrade.session_id == result["session_id"],
                        PaperTrade.status == "closed",
                    )
                ).all()
                pnls = [float(t.realized_pnl) for t in closed]
            rows.append((symbol, strat, _trade_stats(pnls), result["open_position_count"]))
        time.sleep(0.4)  # be gentle with the public rate limit

    print("\n" + _ROW.format("symbol", "strategy", "done", "win%", "total", "expect", "PF", "open"))
    for symbol, strat, stats, open_count in rows:
        print(_ROW.format(
            symbol, strat, stats["completed_trades"], stats["win_rate"],
            stats["total_pnl"], stats["expectancy"], str(stats["profit_factor"]), open_count,
        ))
    print("\nNext: .venv/bin/python -m scripts.performance_report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
