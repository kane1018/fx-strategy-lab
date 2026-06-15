"""ADX filter OOS validation for rsi_reversal M5 (continuous replay, read-only).

Fixes adx_filter_30 (ADX period 14, threshold 30, entry-only, judged on
adx[index-1] = no look-ahead) and compares baseline vs adx_filter_30 on 5
UNUSED independent weeks (Oct-Dec 2025). No threshold search, no other tuning.

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.adx_filter_oos_ab
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
ADX_PERIOD, ADX_THRESHOLD = 14, 30.0  # fixed; not optimized
PATTERNS = [("baseline", None), ("adx_filter_30", ADX_THRESHOLD)]
# OOS weeks NOT used in prior IS/OOS runs (Oct-Dec 2025).
WINDOWS = [
    ("oos_window_1", "20251215", "20251226"),
    ("oos_window_2", "20251201", "20251212"),
    ("oos_window_3", "20251117", "20251128"),
    ("oos_window_4", "20251103", "20251114"),
    ("oos_window_5", "20251020", "20251031"),
]


def _skip_rate(completed: int, skipped: int) -> float:
    denom = completed + skipped
    return round(skipped / denom, 4) if denom else 0.0


def improvement_counts(base_ws: dict, adx_ws: dict) -> tuple[int, int]:
    """(improved, worsened) windows by expectancy: adx_filter_30 vs baseline (pure)."""
    improved = sum(1 for w in base_ws if adx_ws[w]["expectancy"] > base_ws[w]["expectancy"])
    worsened = sum(1 for w in base_ws if adx_ws[w]["expectancy"] < base_ws[w]["expectancy"])
    return improved, worsened


def _pattern_summary(results: dict, pattern: str) -> dict:
    ws = {w: _summarize(results[(pattern, w)]["trades"]) for w, _s, _e in WINDOWS}
    summary = robustness_summary(ws)
    summary["total_pnl"] = round(sum(s["total_pnl"] for s in ws.values()), 2)
    summary["total_sl_count"] = sum(s["sl_count"] for s in ws.values())
    summary["median_sl_ratio"] = round(statistics.median(s["sl_ratio"] for s in ws.values()), 4)
    summary["median_skip_rate"] = round(statistics.median(
        _skip_rate(ws[w]["completed_trades"], results[(pattern, w)]["skipped"])
        for w, _s, _e in WINDOWS), 4)
    return summary


def _write_csv(path: Path, rows: list[dict], keys: list[str], extra: list[str]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([*keys, *_STAT_FIELDS, *extra])
        for r in rows:
            w.writerow([*[r[k] for k in keys], *[r["stats"][f] for f in _STAT_FIELDS],
                        *[r.get(e, "") for e in extra]])


def main() -> int:
    strategy = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    broker = GmoFxBroker()
    warnings: list[str] = []

    # Fetch+concat each (window, symbol) once; reuse across both patterns.
    series: dict[tuple[str, str], pd.DataFrame] = {}
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
            if chunks:
                merged = pd.concat(chunks, ignore_index=True)
                series[(label, symbol)] = (
                    merged.sort_values("timestamp").drop_duplicates("timestamp")
                    .reset_index(drop=True)
                )
    print(f"series built: {len(series)}")

    results: dict[tuple[str, str], dict] = {}
    for pattern, thr in PATTERNS:
        for label, _s, _e in WINDOWS:
            trades: list[dict] = []
            skipped = 0
            for symbol in SYMBOLS:
                frame = series.get((label, symbol))
                if frame is None or len(frame) < 3:
                    continue
                with _mem() as db:
                    res = replay_paper_trades(
                        db, symbol=symbol, timeframe=TIMEFRAME,
                        candles=[Candle(timestamp=pd.Timestamp(r["timestamp"]).to_pydatetime(),
                                        open=float(r["open"]), high=float(r["high"]),
                                        low=float(r["low"]), close=float(r["close"]), volume=0)
                                 for _, r in frame.iterrows()],
                        strategy=strategy, execution=ExecutionConfig(spread_pips=SPREAD,
                                                                     slippage_pips=SLIP),
                        exit_policy="baseline", force_close_at_end=True, fast_signals=True,
                        entry_adx_max=thr,
                    )
                    skipped += res["skipped_entries"]
                    rows = db.scalars(select(PaperTrade).where(
                        PaperTrade.session_id == res["session_id"],
                        PaperTrade.status == "closed")).all()
                    for t in rows:
                        trades.append({
                            "pnl": float(t.realized_pnl), "symbol": symbol,
                            "date": t.opened_at.date().isoformat(), "closed_at": t.closed_at,
                            "exit_category": _exit_category(t.exit_reason or ""),
                        })
            results[(pattern, label)] = {"trades": trades, "skipped": skipped}
            s = _summarize(trades)
            print(f"{pattern:<14}{label:<13} n={s['completed_trades']:>4} "
                  f"exp={s['expectancy']:>8} PF={s['profit_factor']} maxDD={s['max_drawdown']} "
                  f"SL={s['sl_count']} skip%={_skip_rate(s['completed_trades'], skipped)}")

    _export(results, window_dates, warnings)
    return 0


def _export(results: dict, window_dates: dict, warnings: list[str]) -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gmo_public_paper_adx_oos"
    out = EXPORT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    by_window = []
    for pattern, _thr in PATTERNS:
        for w, _s, _e in WINDOWS:
            data = results[(pattern, w)]
            stats = _summarize(data["trades"])
            by_window.append({
                "pattern": pattern, "window": w,
                "period": f"{window_dates[w][0]}..{window_dates[w][-1]}", "stats": stats,
                "skipped_entries": data["skipped"],
                "skip_rate": _skip_rate(stats["completed_trades"], data["skipped"]),
            })
    _write_csv(out / "metrics_by_adx_oos_window.csv",
               [{"pattern": r["pattern"], "window": r["window"], "stats": r["stats"],
                 "skipped_entries": r["skipped_entries"], "skip_rate": r["skip_rate"]}
                for r in by_window],
               ["pattern", "window"], ["skipped_entries", "skip_rate"])

    by_symbol = []
    for pattern, _thr in PATTERNS:
        for sym in SYMBOLS:
            sub = [t for w, _s, _e in WINDOWS for t in results[(pattern, w)]["trades"]
                   if t["symbol"] == sym]
            if sub:
                by_symbol.append({"pattern": pattern, "symbol": sym, "stats": _summarize(sub)})
    _write_csv(out / "metrics_by_adx_oos_symbol.csv", by_symbol, ["pattern", "symbol"], [])

    by_reason = []
    for pattern, _thr in PATTERNS:
        flat = [t for w, _s, _e in WINDOWS for t in results[(pattern, w)]["trades"]]
        for reason in sorted({t["exit_category"] for t in flat}):
            sub = [t for t in flat if t["exit_category"] == reason]
            by_reason.append({"pattern": pattern, "exit_reason": reason, "stats": _summarize(sub)})
    _write_csv(out / "metrics_by_exit_reason.csv", by_reason, ["pattern", "exit_reason"], [])

    by_date = []
    for pattern, _thr in PATTERNS:
        for w, _s, _e in WINDOWS:
            flat = results[(pattern, w)]["trades"]
            for d in sorted({t["date"] for t in flat}):
                sub = [t for t in flat if t["date"] == d]
                by_date.append({"pattern": pattern, "window": w, "date": d,
                                "stats": _summarize(sub)})
    _write_csv(out / "metrics_by_date.csv", by_date, ["pattern", "window", "date"], [])

    summaries = {p: _pattern_summary(results, p) for p, _t in PATTERNS}
    base_ws = {w: _summarize(results[("baseline", w)]["trades"]) for w, _s, _e in WINDOWS}
    adx_ws = {w: _summarize(results[("adx_filter_30", w)]["trades"]) for w, _s, _e in WINDOWS}
    improved, worsened = improvement_counts(base_ws, adx_ws)
    summaries["adx_filter_30"]["improved_windows"] = improved
    summaries["adx_filter_30"]["worsened_windows"] = worsened
    (out / "metrics_adx_oos_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2))
    (out / "warnings.json").write_text(json.dumps({
        "data_source": "GMO Public API klines (BID), read-only",
        "fixed_config": f"rsi_reversal / {TIMEFRAME} / current_cost (spread {SPREAD}, "
                        f"slippage {SLIP}) / baseline exit / SL30 / TP60 / 4 pairs",
        "adx": f"period {ADX_PERIOD} fixed, threshold {ADX_THRESHOLD} fixed, entry-only, "
               "adx[index-1] (no look-ahead)",
        "oos_windows": {w: window_dates[w] for w, _s, _e in WINDOWS},
        "note": "OOS validation; no threshold search, no other tuning. Public klines single-price.",
        "fetch_warnings": warnings,
    }, ensure_ascii=False, indent=2))
    (out / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_adx_oos", "strategy": "rsi_reversal", "timeframe": TIMEFRAME,
        "cost_scenario": "current_cost", "spread_pips": SPREAD, "slippage_pips": SLIP,
        "exit_policy": "baseline", "stop_loss_pips": ExecutionConfig().stop_loss_pips,
        "take_profit_pips": ExecutionConfig().take_profit_pips,
        "adx_period": ADX_PERIOD, "adx_threshold": ADX_THRESHOLD, "adx_judgement": "adx[index-1]",
        "patterns": [p for p, _t in PATTERNS],
        "oos_windows": [{"window": w, "dates": d} for w, d in window_dates.items()],
        "symbols": SYMBOLS, "continuous_replay": True, "no_order_execution": True,
        "gmo_readonly": True, "gmo_order_enabled": False,
    }, ensure_ascii=False, indent=2))
    _write_summary(out, by_window, summaries, base_ws, adx_ws)
    _write_oos_analysis(out, summaries, improved, worsened)
    print("\n" + json.dumps({p: {"median_exp": s["median_expectancy"],
                                 "median_pf": s["median_pf"], "positive": s["positive_windows"],
                                 "sl": s["total_sl_count"]} for p, s in summaries.items()},
                            ensure_ascii=False))
    print(f"improved/worsened windows (adx vs base): {improved}/{worsened}")
    print(f"Export written to: analysis_exports/{run_id}/")


def _write_summary(out: Path, by_window: list[dict], summaries: dict,
                   base_ws: dict, adx_ws: dict) -> None:
    head = ("| pattern | window | 期間 | 完了 | 見送率 | 勝率 | 総損益 | 期待値 | PF | DD | SL |\n"
            "|--|--|--|--:|--:|--:|--:|--:|--:|--:|--:|\n")
    rows = []
    for r in by_window:
        s = r["stats"]
        rows.append(f"| {r['pattern']} | {r['window']} | {r['period']} | {s['completed_trades']} | "
                    f"{r['skip_rate']} | {s['win_rate']}% | {s['total_pnl']} | {s['expectancy']} | "
                    f"{s['profit_factor']} | {s['max_drawdown']} | {s['sl_count']} |")
    diff_rows = ["| window | 期待値差分 | PF差分 | 最大DD差分 | SL差分 |",
                 "|--|--:|--:|--:|--:|"]
    for w in base_ws:
        b, a = base_ws[w], adx_ws[w]
        diff_rows.append(
            f"| {w} | {round(a['expectancy'] - b['expectancy'], 4)} | "
            f"{round((a['profit_factor'] or 0) - (b['profit_factor'] or 0), 3)} | "
            f"{round(a['max_drawdown'] - b['max_drawdown'], 2)} | "
            f"{a['sl_count'] - b['sl_count']} |")
    parts = [
        "# ADXフィルタ OOS確認 (rsi_reversal M5 current_cost, 未使用5週 Oct-Dec 2025)\n",
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "ADX14/閾値30固定・entry専用・adx[index-1]・exit不変。\n",
        "## window別\n" + head + "\n".join(rows),
        "\n## baseline集計: " + json.dumps(summaries["baseline"], ensure_ascii=False),
        "## adx_filter_30集計: " + json.dumps(summaries["adx_filter_30"], ensure_ascii=False),
        "\n## baselineとの差分(window別)\n" + "\n".join(diff_rows),
    ]
    (out / "summary.md").write_text("\n".join(parts))


def _write_oos_analysis(out: Path, summaries: dict, improved: int, worsened: int) -> None:
    b, a = summaries["baseline"], summaries["adx_filter_30"]
    promising = (
        a["median_expectancy"] > b["median_expectancy"]
        and a["median_pf"] > b["median_pf"]
        and a["total_sl_count"] < b["total_sl_count"]
        and a["max_drawdown_max"] <= b["max_drawdown_max"]
        and a["positive_windows"] >= b["positive_windows"]
        and improved > worsened
    )
    verdict = "継続検証候補（OOSでも改善）" if promising else "却下/判断保留"
    text = (
        "# ADXフィルタ OOS分析 (rsi_reversal M5 current_cost)\n\n"
        f"## 判定: {verdict}\n\n"
        f"- baseline:      exp中央 {b['median_expectancy']} / PF中央 {b['median_pf']} / "
        f"+win {b['positive_windows']}/{b['window_count']} / SL {b['total_sl_count']} / "
        f"DD最大 {b['max_drawdown_max']} / 合計 {b['total_pnl']}\n"
        f"- adx_filter_30: exp中央 {a['median_expectancy']} / PF中央 {a['median_pf']} / "
        f"+win {a['positive_windows']}/{a['window_count']} / SL {a['total_sl_count']} / "
        f"DD最大 {a['max_drawdown_max']} / 合計 {a['total_pnl']}\n"
        f"  見送中央 {a['median_skip_rate']} / baseline比 改善window {improved} / "
        f"悪化window {worsened}\n\n"
        "採用条件: exp中央↑・PF中央↑・SL↓・最大DD悪化なし・+win≥base・改善window過半。\n"
    )
    (out / "adx_filter_oos_analysis.md").write_text(text)


if __name__ == "__main__":
    raise SystemExit(main())
