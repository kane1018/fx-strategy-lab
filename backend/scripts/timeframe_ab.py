"""Timeframe sensitivity for rsi_reversal (continuous replay, paper, read-only).

Varies ONLY the candle timeframe (1min/5min/15min); RSI/SL/TP/entry/exit fixed.
Diagnostic cost scenarios current_cost / zero_cost per timeframe (judgment is on
current_cost). Tests whether a higher timeframe (larger per-trade move vs fixed
cost) lets current_cost turn positive.

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.timeframe_ab
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.brokers import GmoFxBroker, GmoFxBrokerError  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import PaperTrade  # noqa: E402
from app.schemas.trading import Candle, ExecutionConfig, StrategyConfig, StrategyType  # noqa: E402
from app.services.gmo_paper_service import replay_paper_trades  # noqa: E402
from app.services.market_data_service import candles_to_frame  # noqa: E402
from app.services.paper_analysis_service import holding_bucket, holding_minutes  # noqa: E402
from app.services.performance_service import _trade_stats  # noqa: E402

EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "analysis_exports"
SYMBOLS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY"]
TIMEFRAMES = [("M1", "1min"), ("M5", "5min"), ("M15", "15min")]  # (internal, gmo interval)
COSTS = [("current_cost", ExecutionConfig().spread_pips, ExecutionConfig().slippage_pips),
         ("zero_cost", 0.0, 0.0)]
PERIODS = {
    "IS": ["20260601", "20260602", "20260603", "20260604", "20260605",
           "20260608", "20260609", "20260610", "20260611", "20260612"],
    "OOS": ["20260518", "20260519", "20260520", "20260521", "20260522",
            "20260525", "20260526", "20260527", "20260528", "20260529"],
}
_FORCED = "データ終了強制クローズ"
_SL = "損切り到達(SL)"
_OPP = "反対シグナル"
_STAT_FIELDS = [
    "completed_trades", "win_rate", "total_pnl", "avg_win", "avg_loss", "expectancy",
    "avg_pnl_per_trade", "profit_factor", "max_drawdown", "max_loss",
    "max_consecutive_losses", "sl_count", "sl_ratio", "opp_count", "opp_total_pnl",
    "forced_close_count", "forced_close_ratio", "avg_holding_min", "reference_only",
]


def _exit_category(reason: str) -> str:
    if "損切り" in reason:
        return _SL
    if "利確" in reason:
        return "利確到達(TP)"
    if "反対シグナル" in reason:
        return _OPP
    if "データ終了" in reason:
        return _FORCED
    return reason or "unknown"


def _mem() -> Session:
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return Session(eng)


def _summarize(trades: list[dict]) -> dict:
    stats = _trade_stats([t["pnl"] for t in trades])
    streak = mcl = 0
    for t in sorted(trades, key=lambda x: x["closed_at"]):
        if t["pnl"] < 0:
            streak += 1
            mcl = max(mcl, streak)
        elif t["pnl"] > 0:
            streak = 0
    sl = [t for t in trades if t["exit_category"] == _SL]
    opp = [t for t in trades if t["exit_category"] == _OPP]
    forced = [t for t in trades if t["exit_category"] == _FORCED]
    n = stats["completed_trades"]
    avg_hold = round(sum(t["holding_min"] for t in trades) / n, 2) if n else 0.0
    return {
        **{k: stats[k] for k in ["completed_trades", "win_rate", "total_pnl", "avg_win",
                                 "avg_loss", "expectancy", "avg_pnl_per_trade", "profit_factor",
                                 "max_drawdown", "max_loss", "reference_only"]},
        "max_consecutive_losses": mcl,
        "sl_count": len(sl),
        "sl_ratio": round(len(sl) / n, 4) if n else 0.0,
        "opp_count": len(opp),
        "opp_total_pnl": round(sum(t["pnl"] for t in opp), 2),
        "forced_close_count": len(forced),
        "forced_close_ratio": round(len(forced) / n, 4) if n else 0.0,
        "avg_holding_min": avg_hold,
    }


def _write_csv(path: Path, rows: list[dict], keys: list[str]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([*keys, *_STAT_FIELDS])
        for r in rows:
            w.writerow([*[r[k] for k in keys], *[r["stats"][f] for f in _STAT_FIELDS]])


def _frame_to_candles(frame: pd.DataFrame):
    for _, row in frame.iterrows():
        yield Candle(timestamp=pd.Timestamp(row["timestamp"]).to_pydatetime(),
                     open=float(row["open"]), high=float(row["high"]), low=float(row["low"]),
                     close=float(row["close"]), volume=0)


def main() -> int:
    strategy = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    broker = GmoFxBroker()
    warnings: list[str] = []

    # Fetch + concat per (timeframe, symbol, period); reused across cost scenarios.
    series: dict[tuple[str, str, str], pd.DataFrame] = {}
    for tf_internal, _interval in TIMEFRAMES:
        for period, dates in PERIODS.items():
            for symbol in SYMBOLS:
                chunks = []
                for date in dates:
                    try:
                        chunks.append(candles_to_frame(
                            broker.candles(symbol, tf_internal, 1500, date=date)))
                    except GmoFxBrokerError as error:
                        warnings.append(f"fetch failed {tf_internal} {symbol} {date}: {error}")
                    time.sleep(0.2)
                if chunks:
                    merged = pd.concat(chunks, ignore_index=True)
                    merged = merged.sort_values("timestamp").drop_duplicates("timestamp")
                    series[(tf_internal, symbol, period)] = merged.reset_index(drop=True)
    print(f"series built: {len(series)}")

    results: dict[tuple[str, str, str], list[dict]] = {}
    for tf_internal, _interval in TIMEFRAMES:
        for cost, spread, slip in COSTS:
            execution = ExecutionConfig(spread_pips=spread, slippage_pips=slip)
            for period in PERIODS:
                trades: list[dict] = []
                for symbol in SYMBOLS:
                    frame = series.get((tf_internal, symbol, period))
                    if frame is None or len(frame) < 3:
                        continue
                    with _mem() as db:
                        res = replay_paper_trades(
                            db, symbol=symbol, timeframe=tf_internal,
                            candles=list(_frame_to_candles(frame)),
                            strategy=strategy, execution=execution, exit_policy="baseline",
                            force_close_at_end=True, fast_signals=True,
                        )
                        rows = db.scalars(select(PaperTrade).where(
                            PaperTrade.session_id == res["session_id"],
                            PaperTrade.status == "closed")).all()
                        for t in rows:
                            held = holding_minutes(t.opened_at, t.closed_at)
                            trades.append({
                                "pnl": float(t.realized_pnl), "symbol": symbol,
                                "date": t.opened_at.date().isoformat(), "closed_at": t.closed_at,
                                "holding_min": held, "holding_bucket": holding_bucket(held),
                                "exit_category": _exit_category(t.exit_reason or ""),
                            })
                results[(tf_internal, cost, period)] = trades
                s = _summarize(trades)
                print(f"{tf_internal:<4}{cost:<14}{period:<4} n={s['completed_trades']:>4} "
                      f"exp={s['expectancy']:>8} PF={s['profit_factor']} "
                      f"maxDD={s['max_drawdown']} avgHold={s['avg_holding_min']}min")

    _export(results, warnings)
    return 0


def _export(results: dict, warnings: list[str]) -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gmo_public_paper_timeframe"
    out = EXPORT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    by_tp = [{"timeframe": tf, "cost_scenario": c, "period": per, "stats": _summarize(tr)}
             for (tf, c, per), tr in results.items()]
    by_ts = []
    for (tf, c, per), tr in results.items():
        for sym in SYMBOLS:
            sub = [t for t in tr if t["symbol"] == sym]
            if sub:
                by_ts.append({"timeframe": tf, "cost_scenario": c, "period": per, "symbol": sym,
                              "stats": _summarize(sub)})
    by_reason = []
    for (tf, c, per), tr in results.items():
        for reason in sorted({t["exit_category"] for t in tr}):
            sub = [t for t in tr if t["exit_category"] == reason]
            by_reason.append({"timeframe": tf, "cost_scenario": c, "period": per,
                              "exit_reason": reason, "stats": _summarize(sub)})
    by_hold = []
    for tf, _i in TIMEFRAMES:
        for c, _s, _sl in COSTS:
            merged = results[(tf, c, "IS")] + results[(tf, c, "OOS")]
            for b in ["<5min", "5-15min", "15-30min", "30-60min", "60min+"]:
                sub = [t for t in merged if t["holding_bucket"] == b]
                if sub:
                    by_hold.append({"timeframe": tf, "cost_scenario": c,
                                    "holding_time_bucket": b, "stats": _summarize(sub)})
    by_date = []
    for (tf, c, per), tr in results.items():
        for d in sorted({t["date"] for t in tr}):
            sub = [t for t in tr if t["date"] == d]
            by_date.append({"timeframe": tf, "cost_scenario": c, "period": per, "date": d,
                            "stats": _summarize(sub)})

    _write_csv(out / "metrics_by_timeframe_period.csv", by_tp,
               ["timeframe", "cost_scenario", "period"])
    _write_csv(out / "metrics_by_timeframe_symbol.csv", by_ts,
               ["timeframe", "cost_scenario", "period", "symbol"])
    _write_csv(out / "metrics_by_exit_reason.csv", by_reason,
               ["timeframe", "cost_scenario", "period", "exit_reason"])
    _write_csv(out / "metrics_by_holding_time.csv", by_hold,
               ["timeframe", "cost_scenario", "holding_time_bucket"])
    _write_csv(out / "metrics_by_date.csv", by_date,
               ["timeframe", "cost_scenario", "period", "date"])
    (out / "metrics_overall.json").write_text(json.dumps(
        {f"{tf}|{c}|{per}": _summarize(tr) for (tf, c, per), tr in results.items()},
        ensure_ascii=False, indent=2))
    (out / "metrics_drawdown_streaks.json").write_text(json.dumps(
        {f"{tf}|{c}|{per}": {"max_consecutive_losses": _summarize(tr)["max_consecutive_losses"],
                             "max_single_loss": _summarize(tr)["max_loss"]}
         for (tf, c, per), tr in results.items()}, ensure_ascii=False, indent=2))
    (out / "warnings.json").write_text(json.dumps({
        "data_source": "GMO Public API klines (BID), read-only",
        "strategy": "rsi_reversal, exit_policy=baseline, SL=30, TP=60, only timeframe varied",
        "fixed": "RSI params, stop_loss_pips, take_profit_pips, entry, filters unchanged",
        "harness": "continuous (cross-day); force-close only at period end",
        "note": "SL/TP are fixed in PIPS regardless of timeframe; higher TF bars have wider "
                "high/low so SL/TP can be hit within one bar. 'cost' is modeled fixed friction.",
        "fetch_warnings": warnings,
    }, ensure_ascii=False, indent=2))
    (out / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_timeframe", "strategy": "rsi_reversal", "exit_policy": "baseline",
        "stop_loss_pips": ExecutionConfig().stop_loss_pips,
        "take_profit_pips": ExecutionConfig().take_profit_pips,
        "timeframes": [{"internal": tf, "gmo_interval": i} for tf, i in TIMEFRAMES],
        "cost_scenarios": [{"cost_scenario": c, "spread_pips": s, "slippage_pips": sl}
                           for c, s, sl in COSTS],
        "periods": PERIODS, "symbols": SYMBOLS, "continuous_replay": True,
        "no_order_execution": True, "gmo_readonly": True, "gmo_order_enabled": False,
    }, ensure_ascii=False, indent=2))
    _write_summary(out, results)
    _write_timeframe_edge(out, results)
    print(f"\nExport written to: analysis_exports/{run_id}/")


def _md(rows: list[dict]) -> str:
    cols = ["timeframe", "cost", "完了", "勝率", "総損益", "期待値", "PF", "最大DD",
            "最大単発損失", "avg保有(min)"]
    head = "| " + " | ".join(cols) + " |\n|" + "--|" * len(cols) + "\n"
    lines = []
    for r in rows:
        s = r["stats"]
        lines.append("| " + " | ".join([
            r["timeframe"], r["cost_scenario"], str(s["completed_trades"]), f"{s['win_rate']}%",
            str(s["total_pnl"]), str(s["expectancy"]), str(s["profit_factor"]),
            str(s["max_drawdown"]), str(s["max_loss"]), str(s["avg_holding_min"])]) + " |")
    return head + "\n".join(lines)


def _write_summary(out: Path, results: dict) -> None:
    is_rows = [{"timeframe": tf, "cost_scenario": c, "stats": _summarize(results[(tf, c, "IS")])}
               for tf, _i in TIMEFRAMES for c, _s, _sl in COSTS]
    oos_rows = [{"timeframe": tf, "cost_scenario": c, "stats": _summarize(results[(tf, c, "OOS")])}
                for tf, _i in TIMEFRAMES for c, _s, _sl in COSTS]
    text = (
        "# timeframe sensitivity (rsi_reversal, baseline exit, SL30/TP60, continuous)\n\n"
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "timeframe のみ変更（RSI/SL/TP/entry不変）。判断は current_cost 主基準。\n\n"
        "## IS (2026-06-01〜06-12)\n" + _md(is_rows) + "\n\n"
        "## OOS (2026-05-18〜05-29)\n" + _md(oos_rows) + "\n"
    )
    (out / "summary.md").write_text(text)


def _write_timeframe_edge(out: Path, results: dict) -> None:
    lines = ["# timeframe edge analysis (rsi_reversal, current_cost が主基準)\n"]
    candidate = None
    for tf, _i in TIMEFRAMES:
        is_c = _summarize(results[(tf, "current_cost", "IS")])
        oos_c = _summarize(results[(tf, "current_cost", "OOS")])
        is_z = _summarize(results[(tf, "zero_cost", "IS")])
        oos_z = _summarize(results[(tf, "zero_cost", "OOS")])
        cur_pos = (is_c["expectancy"] > 0 and oos_c["expectancy"] > 0
                   and (is_c["profit_factor"] or 0) >= 1 and (oos_c["profit_factor"] or 0) >= 1
                   and is_c["completed_trades"] >= 30 and oos_c["completed_trades"] >= 30)
        if cur_pos:
            verdict = "継続検証候補（current_costで両期間プラス）"
            candidate = candidate or tf
        elif is_z["expectancy"] > 0 and oos_z["expectancy"] > 0:
            verdict = "価格エッジあり・まだコスト負け"
        else:
            verdict = "撤退候補寄り"
        lines.append(
            f"- {tf}: current IS {is_c['expectancy']}/PF{is_c['profit_factor']}"
            f"(n{is_c['completed_trades']}), "
            f"OOS {oos_c['expectancy']}/PF{oos_c['profit_factor']}(n{oos_c['completed_trades']}); "
            f"zero IS {is_z['expectancy']}/OOS {oos_z['expectancy']} -> {verdict}"
        )
    lines.append(f"\n## 継続検証候補timeframe: {candidate or 'なし'}")
    (out / "timeframe_edge_analysis.md").write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
