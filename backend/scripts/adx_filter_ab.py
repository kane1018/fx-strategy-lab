"""ADX regime-filter A/B for rsi_reversal M5 current_cost (continuous, read-only).

Holds everything fixed (rsi_reversal / M5 / current_cost / baseline exit / SL30 /
TP60 / 4 pairs) and varies ONLY an entry-side ADX(14) regime filter:
  baseline       - no filter
  adx_filter_25  - skip NEW entries when ADX >= 25 (exits unchanged)
  adx_filter_30  - skip NEW entries when ADX >= 30 (exits unchanged)
Compared across the same 10 independent past weeks. ADX period fixed at 14
(not optimized); thresholds fixed at 25/30.

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.adx_filter_ab
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.brokers import GmoFxBroker, GmoFxBrokerError  # noqa: E402
from app.models import PaperTrade  # noqa: E402
from app.schemas.trading import Candle, ExecutionConfig, StrategyConfig, StrategyType  # noqa: E402
from app.services.gmo_paper_service import replay_paper_trades  # noqa: E402
from app.services.market_data_service import candles_to_frame  # noqa: E402
from scripts.robustness_windows import (  # noqa: E402
    _STAT_FIELDS,
    _exit_category,
    _mem,
    _summarize,
    _weekdays,
    robustness_summary,
)

EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "analysis_exports"
SYMBOLS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY"]
TIMEFRAME = "M5"
SPREAD, SLIP = ExecutionConfig().spread_pips, ExecutionConfig().slippage_pips
WINDOWS = [
    ("window_1", "20260504", "20260515"), ("window_2", "20260420", "20260501"),
    ("window_3", "20260406", "20260417"), ("window_4", "20260323", "20260403"),
    ("window_5", "20260309", "20260320"), ("window_6", "20260223", "20260306"),
    ("window_7", "20260209", "20260220"), ("window_8", "20260126", "20260206"),
    ("window_9", "20260112", "20260123"), ("window_10", "20251229", "20260109"),
]
PATTERNS = [("baseline", None), ("adx_filter_25", 25.0), ("adx_filter_30", 30.0)]


def _flat(keys: dict, stats: dict, extra: dict | None = None) -> dict:
    row = {**keys, **{f: stats[f] for f in _STAT_FIELDS}}
    if extra:
        row.update(extra)
    return row


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    strategy = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    execution = ExecutionConfig(spread_pips=SPREAD, slippage_pips=SLIP)
    broker = GmoFxBroker()
    warnings: list[str] = []

    cache: dict[tuple[str, str], list[Candle]] = {}
    window_dates: dict[str, list[str]] = {}
    for label, start, end in WINDOWS:
        dates = _weekdays(start, end)
        window_dates[label] = dates
        for symbol in SYMBOLS:
            chunks = []
            for date in dates:
                try:
                    chunks.append(
                        candles_to_frame(broker.candles(symbol, TIMEFRAME, 2000, date=date))
                    )
                except GmoFxBrokerError as error:
                    warnings.append(f"fetch failed {symbol} {date}: {error}")
                time.sleep(0.2)
            if not chunks:
                continue
            merged = pd.concat(chunks, ignore_index=True)
            merged = (
                merged.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
            )
            cache[(label, symbol)] = [
                Candle(timestamp=pd.Timestamp(r["timestamp"]).to_pydatetime(),
                       open=float(r["open"]), high=float(r["high"]), low=float(r["low"]),
                       close=float(r["close"]), volume=0)
                for _, r in merged.iterrows()
            ]
    print(f"cached series: {len(cache)}")

    # results[(pattern, window)] = {"trades": [...], "skipped": int}
    results: dict[tuple[str, str], dict] = {}
    for pattern, thr in PATTERNS:
        for label, _s, _e in WINDOWS:
            trades: list[dict] = []
            skipped = 0
            for symbol in SYMBOLS:
                candles = cache.get((label, symbol))
                if not candles or len(candles) < 3:
                    continue
                with _mem() as db:
                    res = replay_paper_trades(
                        db, symbol=symbol, timeframe=TIMEFRAME, candles=candles,
                        strategy=strategy, execution=execution, exit_policy="baseline",
                        force_close_at_end=True, fast_signals=True, entry_adx_max=thr,
                    )
                    skipped += res["skipped_entries"]
                    rows = db.scalars(select(PaperTrade).where(
                        PaperTrade.session_id == res["session_id"],
                        PaperTrade.status == "closed")).all()
                    for t in rows:
                        trades.append({
                            "pnl": float(t.realized_pnl), "symbol": symbol,
                            "date": t.opened_at.date().isoformat(), "closed_at": t.closed_at,
                            "exit_category": _exit_category(t.exit_reason or "")})
            results[(pattern, label)] = {"trades": trades, "skipped": skipped}
        med = statistics.median(
            [_summarize(results[(pattern, w)]["trades"])["expectancy"] for w, _s, _e in WINDOWS]
        )
        print(f"{pattern}: median_exp={round(med, 4)}")

    _export(results, window_dates, warnings)
    return 0


def _skip_rate(window: dict) -> float:
    completed = len(window["trades"])
    denom = completed + window["skipped"]
    return round(window["skipped"] / denom, 4) if denom else 0.0


def _pattern_summary(results: dict, pattern: str) -> dict:
    window_stats = {w: _summarize(results[(pattern, w)]["trades"]) for w, _s, _e in WINDOWS}
    summ = robustness_summary(window_stats)
    summ["total_sl_count"] = sum(s["sl_count"] for s in window_stats.values())
    summ["median_sl_ratio"] = round(
        statistics.median([s["sl_ratio"] for s in window_stats.values()]), 4)
    summ["median_skip_rate"] = round(
        statistics.median([_skip_rate(results[(pattern, w)]) for w, _s, _e in WINDOWS]), 4)
    summ["total_pnl"] = round(sum(s["total_pnl"] for s in window_stats.values()), 2)
    return summ


def _export(results: dict, window_dates: dict, warnings: list[str]) -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gmo_public_paper_adx_filter"
    out = EXPORT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    win_rows = []
    for pattern, _thr in PATTERNS:
        for w, _s, _e in WINDOWS:
            data = results[(pattern, w)]
            stats = _summarize(data["trades"])
            win_rows.append(_flat(
                {"pattern": pattern, "window": w,
                 "period": f"{window_dates[w][0]}..{window_dates[w][-1]}"},
                stats, {"skipped_entries": data["skipped"], "skip_rate": _skip_rate(data)}))
    _write_csv(out / "metrics_by_regime_filter_window.csv", win_rows,
               ["pattern", "window", "period", *_STAT_FIELDS, "skipped_entries", "skip_rate"])

    sym_rows = []
    for pattern, _thr in PATTERNS:
        for sym in SYMBOLS:
            sub = [t for w, _s, _e in WINDOWS for t in results[(pattern, w)]["trades"]
                   if t["symbol"] == sym]
            sym_rows.append(_flat({"pattern": pattern, "symbol": sym}, _summarize(sub)))
    _write_csv(out / "metrics_by_regime_filter_symbol.csv", sym_rows,
               ["pattern", "symbol", *_STAT_FIELDS])

    reason_rows = []
    for pattern, _thr in PATTERNS:
        flat = [t for w, _s, _e in WINDOWS for t in results[(pattern, w)]["trades"]]
        for reason in sorted({t["exit_category"] for t in flat}):
            sub = [t for t in flat if t["exit_category"] == reason]
            reason_rows.append(_flat({"pattern": pattern, "exit_reason": reason}, _summarize(sub)))
    _write_csv(out / "metrics_by_exit_reason.csv", reason_rows,
               ["pattern", "exit_reason", *_STAT_FIELDS])

    date_rows = []
    for pattern, _thr in PATTERNS:
        for w, _s, _e in WINDOWS:
            flat = results[(pattern, w)]["trades"]
            for d in sorted({t["date"] for t in flat}):
                sub = [t for t in flat if t["date"] == d]
                date_rows.append(_flat({"pattern": pattern, "window": w, "date": d},
                                       _summarize(sub)))
    _write_csv(out / "metrics_by_date.csv", date_rows,
               ["pattern", "window", "date", *_STAT_FIELDS])

    summaries = {p: _pattern_summary(results, p) for p, _t in PATTERNS}
    (out / "metrics_regime_filter_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2))
    (out / "warnings.json").write_text(json.dumps({
        "data_source": "GMO Public API klines (BID), read-only",
        "fixed_config": f"rsi_reversal / {TIMEFRAME} / current_cost (spread {SPREAD}, "
                        f"slippage {SLIP}) / baseline exit / SL30 / TP60 / 4 pairs",
        "adx": "period 14 (fixed, not optimized); thresholds 25/30; entry-only filter "
               "(blocks NEW entries when ADX>=threshold; exits unchanged)",
        "windows": {w: window_dates[w] for w, _s, _e in WINDOWS},
        "note": "10 independent weeks. Public klines single-price. No other tuning.",
        "fetch_warnings": warnings,
    }, ensure_ascii=False, indent=2))
    _write_manifest(out, run_id, window_dates)
    _write_summary(out, results, summaries, window_dates)
    _write_adx_analysis(out, summaries)
    print("\n" + json.dumps({p: {"median_exp": s["median_expectancy"], "median_pf": s["median_pf"],
                                 "positive": s["positive_windows"], "sl": s["total_sl_count"],
                                 "skip%": s["median_skip_rate"]}
                             for p, s in summaries.items()}, ensure_ascii=False))
    print(f"Export written to: analysis_exports/{run_id}/")


def _write_manifest(out: Path, run_id: str, window_dates: dict) -> None:
    (out / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_adx_filter", "strategy": "rsi_reversal", "timeframe": TIMEFRAME,
        "cost_scenario": "current_cost", "spread_pips": SPREAD, "slippage_pips": SLIP,
        "exit_policy": "baseline", "stop_loss_pips": ExecutionConfig().stop_loss_pips,
        "take_profit_pips": ExecutionConfig().take_profit_pips, "symbols": SYMBOLS,
        "adx_period": 14, "patterns": [{"pattern": p, "adx_max": t} for p, t in PATTERNS],
        "windows": [{"window": w, "dates": d} for w, d in window_dates.items()],
        "continuous_replay": True, "no_order_execution": True,
        "gmo_readonly": True, "gmo_order_enabled": False,
    }, ensure_ascii=False, indent=2))


def _write_summary(out: Path, results: dict, summaries: dict, window_dates: dict) -> None:
    parts = ["# ADXレジームフィルタ (rsi_reversal M5 current_cost, 独立10週)\n",
             "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
             "entry時ADX(14)で新規見送り。exitは不変。\n"]
    for pattern, _thr in PATTERNS:
        head = ("| window | 期間 | 完了 | 見送率 | 勝率 | 総損益 | 期待値 | PF | DD | SL |\n"
                "|--|--|--:|--:|--:|--:|--:|--:|--:|--:|\n")
        rows = []
        for w, _s, _e in WINDOWS:
            data = results[(pattern, w)]
            s = _summarize(data["trades"])
            rows.append(f"| {w} | {window_dates[w][0]}..{window_dates[w][-1]} | "
                        f"{s['completed_trades']} | {_skip_rate(data)} | {s['win_rate']}% | "
                        f"{s['total_pnl']} | {s['expectancy']} | {s['profit_factor']} | "
                        f"{s['max_drawdown']} | {s['sl_count']} |")
        sm = summaries[pattern]
        parts.append(
            f"\n## {pattern}\n" + head + "\n".join(rows) +
            f"\n\n集計: exp中央 {sm['median_expectancy']} / PF中央 {sm['median_pf']} / "
            f"+win {sm['positive_windows']}/{sm['window_count']} / SL {sm['total_sl_count']} / "
            f"DD最大 {sm['max_drawdown_max']} / 見送中央 {sm['median_skip_rate']}\n"
        )
    (out / "summary.md").write_text("\n".join(parts))


def _write_adx_analysis(out: Path, summaries: dict) -> None:
    base = summaries["baseline"]
    lines = ["# ADXフィルタ分析 (rsi_reversal M5 current_cost)\n",
             f"- baseline: exp中央 {base['median_expectancy']} / PF中央 {base['median_pf']} / "
             f"+win {base['positive_windows']}/{base['window_count']} / "
             f"SL {base['total_sl_count']} / DD最大 {base['max_drawdown_max']}\n"]
    promising = []
    for pattern in ("adx_filter_25", "adx_filter_30"):
        s = summaries[pattern]
        ok = (
            s["median_expectancy"] > base["median_expectancy"]
            and s["median_pf"] > base["median_pf"]
            and s["max_drawdown_max"] <= base["max_drawdown_max"]
            and s["total_sl_count"] < base["total_sl_count"]
            and s["positive_windows"] >= base["positive_windows"]
        )
        verdict = "継続検証候補" if ok else "却下/判断保留"
        if ok:
            promising.append(pattern)
        lines.append(
            f"- {pattern}: exp中央 {s['median_expectancy']} / PF中央 {s['median_pf']} / "
            f"+win {s['positive_windows']}/{s['window_count']} / SL {s['total_sl_count']} / "
            f"DD最大 {s['max_drawdown_max']} / 見送中央 {s['median_skip_rate']} -> {verdict}"
        )
    lines.append(f"\n## 有望なフィルタ: {promising or 'なし'}")
    lines.append("注: ADX period=14固定・閾値25/30固定。フィルタは新規エントリーのみ（exit不変）。")
    (out / "adx_filter_analysis.md").write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
