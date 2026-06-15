"""AUD-exclusion robustness for rsi_reversal (continuous replay, paper, read-only).

Adds 5 more independent past weeks (Dec 2025 - Mar 2026) under the SAME fixed
config (M5 / current_cost / baseline / SL30 / TP60) and compares pattern A
(all 4 JPY pairs) vs pattern B (exclude AUD_JPY). Pattern B is pattern A minus
AUD trades on identical data (per-symbol replays are independent), so both views
come from one set of replays. Only AUD exclusion is tried (no other tuning).

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.aud_exclusion_ab
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
    ("window_6", "20260223", "20260306"),
    ("window_7", "20260209", "20260220"),
    ("window_8", "20260126", "20260206"),
    ("window_9", "20260112", "20260123"),
    ("window_10", "20251229", "20260109"),
]
PATTERNS = {"all_pairs": set(), "exclude_aud": {"AUD_JPY"}}


def pattern_window_stats(
    results: dict[str, list[dict]], exclude: set[str]
) -> dict[str, dict]:
    """Per-window stats for a pattern that drops `exclude` symbols (pure / testable)."""
    return {
        window: _summarize([t for t in trades if t["symbol"] not in exclude])
        for window, trades in results.items()
    }


def _write_csv(path: Path, rows: list[dict], keys: list[str]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([*keys, *_STAT_FIELDS])
        for r in rows:
            w.writerow([*[r[k] for k in keys], *[r["stats"][f] for f in _STAT_FIELDS]])


def main() -> int:
    strategy = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    execution = ExecutionConfig(spread_pips=SPREAD, slippage_pips=SLIP)
    broker = GmoFxBroker()
    warnings: list[str] = []

    results: dict[str, list[dict]] = {}
    window_dates: dict[str, list[str]] = {}
    for label, start, end in WINDOWS:
        dates = _weekdays(start, end)
        window_dates[label] = dates
        trades: list[dict] = []
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
            with _mem() as db:
                res = replay_paper_trades(
                    db, symbol=symbol, timeframe=TIMEFRAME,
                    candles=[Candle(timestamp=pd.Timestamp(r["timestamp"]).to_pydatetime(),
                                    open=float(r["open"]), high=float(r["high"]),
                                    low=float(r["low"]), close=float(r["close"]), volume=0)
                             for _, r in merged.iterrows()],
                    strategy=strategy, execution=execution, exit_policy="baseline",
                    force_close_at_end=True, fast_signals=True,
                )
                rows = db.scalars(select(PaperTrade).where(
                    PaperTrade.session_id == res["session_id"],
                    PaperTrade.status == "closed")).all()
                for t in rows:
                    trades.append({
                        "pnl": float(t.realized_pnl), "symbol": symbol,
                        "date": t.opened_at.date().isoformat(), "closed_at": t.closed_at,
                        "exit_category": _exit_category(t.exit_reason or ""),
                    })
        results[label] = trades
        print(f"{label} {start}-{end}: trades={len(trades)}")

    _export(results, window_dates, warnings)
    return 0


def _symbol_window_record(windows: list[str], results: dict[str, list[dict]],
                          symbol: str) -> str:
    signs = []
    for w in windows:
        sub = [t for t in results[w] if t["symbol"] == symbol]
        signs.append("+" if sum(t["pnl"] for t in sub) > 0 else "-")
    return "".join(signs)


def _export(results: dict, window_dates: dict, warnings: list[str]) -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gmo_public_paper_aud_exclusion"
    out = EXPORT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    pattern_stats = {p: pattern_window_stats(results, ex) for p, ex in PATTERNS.items()}
    pattern_summary = {p: robustness_summary(ws) for p, ws in pattern_stats.items()}

    by_pw = [{"pattern": p, "window": w,
              "period": f"{window_dates[w][0]}..{window_dates[w][-1]}", "stats": st}
             for p, ws in pattern_stats.items() for w, st in ws.items()]
    by_ps = []
    for p, ex in PATTERNS.items():
        for sym in SYMBOLS:
            if sym in ex:
                continue
            sub = [t for w in results for t in results[w] if t["symbol"] == sym]
            by_ps.append({"pattern": p, "symbol": sym, "stats": _summarize(sub)})
    by_reason = []
    for p, ex in PATTERNS.items():
        flat = [t for w in results for t in results[w] if t["symbol"] not in ex]
        for reason in sorted({t["exit_category"] for t in flat}):
            sub = [t for t in flat if t["exit_category"] == reason]
            by_reason.append({"pattern": p, "exit_reason": reason, "stats": _summarize(sub)})
    by_date = []
    for p, ex in PATTERNS.items():
        for w, trades in results.items():
            flat = [t for t in trades if t["symbol"] not in ex]
            for d in sorted({t["date"] for t in flat}):
                sub = [t for t in flat if t["date"] == d]
                by_date.append({"pattern": p, "window": w, "date": d, "stats": _summarize(sub)})

    _write_csv(out / "metrics_by_pattern_window.csv",
               [{"pattern": r["pattern"], "window": r["window"], "stats": r["stats"]}
                for r in by_pw], ["pattern", "window"])
    _write_csv(out / "metrics_by_pattern_symbol.csv", by_ps, ["pattern", "symbol"])
    _write_csv(out / "metrics_by_exit_reason.csv", by_reason, ["pattern", "exit_reason"])
    _write_csv(out / "metrics_by_date.csv", by_date, ["pattern", "window", "date"])

    windows = list(results.keys())
    symbol_pnl = {
        s: round(sum(t["pnl"] for w in results for t in results[w] if t["symbol"] == s), 2)
        for s in SYMBOLS
    }
    symbol_record = {s: _symbol_window_record(windows, results, s) for s in SYMBOLS}
    combined = {
        "patterns": pattern_summary,
        "symbol_pnl_all": symbol_pnl,
        "symbol_window_record": symbol_record,
        "windows": {w: window_dates[w] for w in windows},
    }
    (out / "metrics_robustness_summary.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2))
    (out / "warnings.json").write_text(json.dumps({
        "data_source": "GMO Public API klines (BID), read-only",
        "fixed_config": f"rsi_reversal / {TIMEFRAME} / current_cost (spread {SPREAD}, "
                        f"slippage {SLIP}) / baseline / SL30 / TP60",
        "patterns": {p: sorted(SYMBOLS) if not ex else sorted(set(SYMBOLS) - ex)
                     for p, ex in PATTERNS.items()},
        "windows": {w: window_dates[w] for w in windows},
        "note": "exclude_aud = all_pairs minus AUD trades on identical data. "
                "Only AUD exclusion tested; no other tuning. Public klines single-price.",
        "fetch_warnings": warnings,
    }, ensure_ascii=False, indent=2))
    _write_manifest(out, run_id, window_dates)
    _write_summary(out, pattern_stats, pattern_summary, window_dates)
    _write_aud_analysis(out, pattern_stats, pattern_summary, symbol_pnl, symbol_record)
    print("\n" + json.dumps({p: {"median_exp": s["median_expectancy"],
                                 "median_pf": s["median_pf"],
                                 "positive": s["positive_windows"]}
                             for p, s in pattern_summary.items()}, ensure_ascii=False))
    print(f"Export written to: analysis_exports/{run_id}/")


def _write_manifest(out: Path, run_id: str, window_dates: dict) -> None:
    (out / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_aud_exclusion", "strategy": "rsi_reversal",
        "timeframe": TIMEFRAME, "cost_scenario": "current_cost",
        "spread_pips": SPREAD, "slippage_pips": SLIP, "exit_policy": "baseline",
        "stop_loss_pips": ExecutionConfig().stop_loss_pips,
        "take_profit_pips": ExecutionConfig().take_profit_pips,
        "patterns": {p: sorted(set(SYMBOLS) - ex) for p, ex in PATTERNS.items()},
        "windows": [{"window": w, "dates": d} for w, d in window_dates.items()],
        "continuous_replay": True, "no_order_execution": True,
        "gmo_readonly": True, "gmo_order_enabled": False,
    }, ensure_ascii=False, indent=2))


def _window_table(window_stats: dict, window_dates: dict, pattern: str) -> str:
    head = ("| pattern | window | 期間 | 完了 | 勝率 | 総損益 | 期待値 | PF | 最大DD | 判定 |\n"
            "|--|--|--|--:|--:|--:|--:|--:|--:|--|\n")
    rows = []
    for w, s in window_stats.items():
        verdict = "プラス" if s["expectancy"] > 0 else "マイナス"
        rows.append(f"| {pattern} | {w} | {window_dates[w][0]}..{window_dates[w][-1]} | "
                    f"{s['completed_trades']} | {s['win_rate']}% | {s['total_pnl']} | "
                    f"{s['expectancy']} | {s['profit_factor']} | {s['max_drawdown']} | {verdict} |")
    return head + "\n".join(rows)


def _write_summary(out: Path, pattern_stats: dict, pattern_summary: dict,
                   window_dates: dict) -> None:
    parts = ["# AUD除外ロバスト性 (rsi_reversal M5 current_cost, 追加5週)\n",
             "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
             "固定条件・パラメータ調整なし。AUD除外のみ比較。\n"]
    for p in PATTERNS:
        parts.append(f"\n## {p} window別\n" + _window_table(pattern_stats[p], window_dates, p))
        s = pattern_summary[p]
        parts.append(
            f"\n### {p} 集計: median_exp {s['median_expectancy']} / median_PF {s['median_pf']} / "
            f"プラス {s['positive_windows']}/{s['window_count']} / "
            f"最大DD最大 {s['max_drawdown_max']}\n"
        )
    (out / "summary.md").write_text("\n".join(parts))


def _write_aud_analysis(out: Path, pattern_stats: dict, pattern_summary: dict,
                        symbol_pnl: dict, symbol_record: dict) -> None:
    a = pattern_summary["all_pairs"]
    b = pattern_summary["exclude_aud"]
    better_windows = sum(
        1 for w in pattern_stats["all_pairs"]
        if pattern_stats["exclude_aud"][w]["expectancy"]
        > pattern_stats["all_pairs"][w]["expectancy"]
    )
    n = a["window_count"]
    promising = (
        b["median_expectancy"] > a["median_expectancy"]
        and b["median_pf"] > a["median_pf"]
        and b["max_drawdown_max"] <= a["max_drawdown_max"]
        and better_windows > n / 2
    )
    verdict = "AUD除外は継続検証候補" if promising else "AUD除外は却下/判断保留"
    text = (
        "# AUD除外分析 (rsi_reversal M5 current_cost)\n\n"
        f"## 判定: {verdict}\n\n"
        f"- all_pairs:    median_exp {a['median_expectancy']} / median_PF {a['median_pf']} / "
        f"プラス {a['positive_windows']}/{n} / 最大DD最大 {a['max_drawdown_max']}\n"
        f"- exclude_aud:  median_exp {b['median_expectancy']} / median_PF {b['median_pf']} / "
        f"プラス {b['positive_windows']}/{n} / 最大DD最大 {b['max_drawdown_max']}\n"
        f"- exclude_aud が all_pairs より良かった window: {better_windows}/{n}\n\n"
        f"## symbol別合計損益(5週): {symbol_pnl}\n"
        f"## symbol別 window勝敗(w6..w10): {symbol_record}\n\n"
        "注: AUD除外は all_pairs から AUD取引を除いた同一データ比較。AUD以外のペア除外は試さない"
        "（過剰最適化回避）。\n"
    )
    (out / "aud_exclusion_analysis.md").write_text(text)


if __name__ == "__main__":
    raise SystemExit(main())
