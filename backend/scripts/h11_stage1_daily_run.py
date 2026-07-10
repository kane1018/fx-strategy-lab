"""H-11 v2 Stage 1 daily paper run (manual batch, no-POST).

One invocation = one Stage 1 evaluation: update the local H1 cache (public
GET, read-only, operator-authorized), settle any open paper position under
the frozen exit contract, then evaluate at most one new paper entry through
the wired gates. Appends a journal line and prints safe aggregates only.

Manual daily batch by design: resident processes / cron remain forbidden
until a Stage 3 policy step.

Usage (from backend/):
    python -m scripts.h11_stage1_daily_run            # normal daily run
    python -m scripts.h11_stage1_daily_run --offline  # no fetch (cache only)
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from app.services.h11_stage1_daily_engine import (
    JST_OFFSET,
    Stage1OpenPosition,
    build_entry_decision,
    load_state,
    paper_pnl_jpy,
    save_state,
    session_from_state,
    settle_position,
    state_from_session,
)
from app.shadow.gmo_public import GmoPublicError, GmoPublicMarketDataClient
from app.strategies.h11_regime_moe import H11V2Parameters

SYMBOL = "USD_JPY"
DEV_CACHE = Path("market_data/usdjpy_h1_dev_bid.csv")
STAGE1_CACHE = Path("market_data/usdjpy_h1_stage1_bid.csv")
STATE_PATH = Path("market_data/h11_stage1_state.json")
JOURNAL_PATH = Path("market_data/h11_stage1_journal.jsonl")
PARAMS_PATH = Path("app/strategies/h11_parameters_v2.json")
STAGE1_FETCH_START = datetime(2026, 7, 11, tzinfo=UTC)
MIN_BARS_FOR_FEATURES = 700


def _append_journal(record: dict) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"recorded_at_utc": datetime.now(UTC).isoformat(timespec="seconds"), **record}
    with JOURNAL_PATH.open("a") as handle:
        handle.write(json.dumps(record) + "\n")


def _update_stage1_cache() -> None:
    client = GmoPublicMarketDataClient()
    existing: dict[str, tuple[float, float, float, float]] = {}
    if STAGE1_CACHE.exists():
        with STAGE1_CACHE.open() as handle:
            for row in csv.DictReader(handle):
                existing[row["time_utc"]] = (
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                )
    last_time = max(
        (datetime.fromisoformat(t) for t in existing), default=STAGE1_FETCH_START
    )
    day = last_time.replace(hour=0, minute=0, second=0, microsecond=0)
    today = datetime.now(UTC)
    while day <= today:
        try:
            candles = client.fetch_candles(
                SYMBOL, "H1", limit=0, price_type="BID", date=day.strftime("%Y%m%d")
            )
            for candle in candles:
                existing[candle.time] = (candle.open, candle.high, candle.low, candle.close)
        except GmoPublicError as error:
            if "no klines" not in str(error):
                raise
        day += timedelta(days=1)
        time.sleep(0.15)
    STAGE1_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with STAGE1_CACHE.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_utc", "open", "high", "low", "close"])
        for time_iso in sorted(existing):
            writer.writerow([time_iso, *existing[time_iso]])


def _load_bars() -> tuple[list[datetime], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows: dict[str, tuple[float, float, float, float]] = {}
    for path in (DEV_CACHE, STAGE1_CACHE):
        if not path.exists():
            continue
        with path.open() as handle:
            for row in csv.DictReader(handle):
                rows[row["time_utc"]] = (
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                )
    # Drop the possibly in-progress latest hour: keep bars whose open time is
    # at least one full hour behind now.
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    times = [t for t in sorted(rows) if datetime.fromisoformat(t) <= cutoff]
    arr = np.asarray([rows[t] for t in times])
    stamps = [datetime.fromisoformat(t) for t in times]
    return stamps, arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]


def main() -> int:
    parser = argparse.ArgumentParser(description="H-11 Stage 1 daily paper run (no-POST)")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    now_utc = datetime.now(UTC)
    now_jst = now_utc.replace(tzinfo=None) + JST_OFFSET

    if not args.offline:
        _update_stage1_cache()

    stamps, open_, high, low, close = _load_bars()
    if len(close) < MIN_BARS_FOR_FEATURES:
        print(f"ERROR: insufficient bars ({len(close)})")
        return 1
    # Trim to the most recent window needed for features (keeps runs fast).
    stamps = stamps[-1500:]
    open_, high, low, close = (a[-1500:] for a in (open_, high, low, close))
    hour_jst = np.asarray([(t.hour + 9) % 24 for t in stamps])
    spread_wide = ((hour_jst >= 5) & (hour_jst < 9)).astype(int)

    state = load_state(STATE_PATH, now_utc)
    session = session_from_state(state)
    params_raw = json.loads(PARAMS_PATH.read_text())
    parameters = H11V2Parameters(trend_weights=tuple(params_raw["trend_weights"]))

    summary: dict[str, object] = {
        "run_at_jst": now_jst.isoformat(timespec="seconds"),
        "stage1_started_at_utc": state.stage1_started_at_utc,
        "bars_available": len(close),
    }

    # 1) settle an open paper position if its exit contract triggered
    if state.open_position:
        position = Stage1OpenPosition(**state.open_position)
        outcome = settle_position(position, stamps, high, low, close)
        if outcome:
            route, exit_price = outcome
            pnl = paper_pnl_jpy(position.direction, position.entry_price, exit_price)
            stop_state = session.record_paper_trade_outcome_jpy(pnl, now_jst)
            state.open_position = None
            state.closed_trades += 1
            _append_journal(
                {
                    "event": "PAPER_POSITION_SETTLED",
                    "exit_route": route,
                    "paper_outcome_jpy": pnl,
                    "stop_state": stop_state.value,
                    "closed_trades_total": state.closed_trades,
                }
            )
            summary["settled"] = {"route": route, "paper_outcome_jpy": pnl}
        else:
            summary["open_position_held"] = True

    # 2) evaluate at most one new paper entry through the frozen gates
    if state.open_position is None:
        gate_reasons = session.pre_trade_gate_reasons(now_jst, event_exclusion_active=False)
        if gate_reasons:
            _append_journal({"event": "STAGE1_BLOCKED_PRE_TRADE", "reasons": gate_reasons})
            summary["entry"] = {"action": "BLOCKED", "reasons": list(gate_reasons)}
        else:
            decision = build_entry_decision(
                parameters, open_, high, low, close, hour_jst, spread_wide, stamps
            )
            if decision["action"] == "ENTER":
                position: Stage1OpenPosition = decision["position"]
                state.open_position = {
                    "direction": position.direction,
                    "entry_time_utc": position.entry_time_utc,
                    "entry_price": position.entry_price,
                    "sl_price": position.sl_price,
                    "tp_price": position.tp_price,
                    "expiry_time_utc": position.expiry_time_utc,
                }
                session._trades_today += 1
                _append_journal(
                    {
                        "event": "PAPER_ENTRY_OPENED",
                        "direction": position.direction,
                        "reason": decision["reason"],
                        "p_up": decision["p_up"],
                    }
                )
                summary["entry"] = {
                    "action": "PAPER_ENTRY_OPENED",
                    "direction": position.direction,
                    "p_up": decision["p_up"],
                }
            else:
                _append_journal(
                    {
                        "event": "STAGE1_NO_ENTRY",
                        "reason": decision["reason"],
                        "p_up": decision.get("p_up"),
                    }
                )
                summary["entry"] = {
                    "action": "NO_ENTRY",
                    "reason": decision["reason"],
                    "p_up": decision.get("p_up"),
                }

    state = state_from_session(state, session)
    save_state(STATE_PATH, state)

    summary["stop_state"] = state.stop_state
    summary["closed_trades_total"] = state.closed_trades
    summary["discipline_violations"] = len(state.discipline_violations or [])
    summary["progress_target"] = "2 weeks AND 20 paper trades AND 0 violations"
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
