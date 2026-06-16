"""Final 15-window baseline evaluation for rsi_reversal M5 (read-only, paper).

Combines the 10 prior independent weeks (Dec 2025 - May 2026) with the 5 OOS
weeks (Oct - Dec 2025) into ONE 15-window robustness set, all under the same
FIXED config (no tuning): rsi_reversal, M5, current_cost (spread 1.2 / slippage
0.2), baseline exit, SL 30 / TP 60, continuous replay, no ADX filter.

Decision: keep rsi_reversal M5 as a live candidate, retain it only as a research
baseline, or retire it from the main investigation.

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.rsi_final_15window
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

# Canonical shared definitions live in fx_eval_common; re-exported here so the
# existing `from scripts.rsi_final_15window import WINDOWS, ...` imports in the
# sibling runners keep working unchanged.
from scripts.fx_eval_common import (  # noqa: E402,F401
    EXPORT_ROOT,
    SLIP,
    SPREAD,
    SYMBOLS,
    TIMEFRAME,
    WINDOWS,
    classify_strategy,
)
from scripts.robustness_windows import (  # noqa: E402
    _OPP,
    _SL,
    _STAT_FIELDS,
    _exit_category,
    _mem,
    _summarize,
    _weekdays,
    robustness_summary,
)


def _fetch_window_trades(broker: GmoFxBroker, dates: list[str], strategy, execution,
                         warnings: list[str]) -> list[dict]:
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
    return trades


def main() -> int:
    strategy = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    execution = ExecutionConfig(spread_pips=SPREAD, slippage_pips=SLIP)
    broker = GmoFxBroker()
    warnings: list[str] = []

    results: dict[str, list[dict]] = {}
    window_dates: dict[str, list[str]] = {}
    window_group: dict[str, str] = {}
    for label, start, end, group in WINDOWS:
        dates = _weekdays(start, end)
        window_dates[label] = dates
        window_group[label] = group
        trades = _fetch_window_trades(broker, dates, strategy, execution, warnings)
        results[label] = trades
        s = _summarize(trades)
        print(f"{label:>13} {start}-{end} [{group}] n={s['completed_trades']:>4} "
              f"exp={s['expectancy']:>8} PF={s['profit_factor']} "
              f"maxDD={s['max_drawdown']} SL={s['sl_count']}")

    _export(results, window_dates, window_group, warnings)
    return 0


def _write_csv(path: Path, rows: list[dict], keys: list[str]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([*keys, *_STAT_FIELDS])
        for r in rows:
            w.writerow([*[r[k] for k in keys], *[r["stats"][f] for f in _STAT_FIELDS]])


def _export(results: dict, window_dates: dict, window_group: dict, warnings: list[str]) -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gmo_public_paper_rsi_final15"
    out = EXPORT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    window_stats = {label: _summarize(tr) for label, tr in results.items()}
    by_window = [{"window": label, "group": window_group[label],
                  "period": f"{window_dates[label][0]}..{window_dates[label][-1]}",
                  "stats": st} for label, st in window_stats.items()]

    # All trades pooled across the 15 windows.
    all_trades = [t for tr in results.values() for t in tr]
    by_symbol, by_reason, by_date = [], [], []
    symbol_window_wl: dict[str, list[int]] = {s: [0, 0] for s in SYMBOLS}  # [win, loss]
    for sym in SYMBOLS:
        sub = [t for t in all_trades if t["symbol"] == sym]
        if sub:
            by_symbol.append({"symbol": sym, "stats": _summarize(sub)})
    for label, tr in results.items():
        for sym in SYMBOLS:
            sub = [t for t in tr if t["symbol"] == sym]
            if not sub:
                continue
            if sum(t["pnl"] for t in sub) > 0:
                symbol_window_wl[sym][0] += 1
            else:
                symbol_window_wl[sym][1] += 1
        for d in sorted({t["date"] for t in tr}):
            sub = [t for t in tr if t["date"] == d]
            by_date.append({"window": label, "date": d, "stats": _summarize(sub)})
    for reason in sorted({t["exit_category"] for t in all_trades}):
        sub = [t for t in all_trades if t["exit_category"] == reason]
        by_reason.append({"exit_reason": reason, "stats": _summarize(sub)})

    _write_csv(out / "metrics_by_window.csv", by_window, ["window", "group", "period"])
    _write_csv(out / "metrics_by_symbol.csv", by_symbol, ["symbol"])
    _write_csv(out / "metrics_by_exit_reason.csv", by_reason, ["exit_reason"])
    _write_csv(out / "metrics_by_date.csv", by_date, ["window", "date"])

    summary = _build_summary(results, window_stats, window_group, all_trades, symbol_window_wl)
    (out / "metrics_15window_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2))

    verdict, reasons = classify_strategy(
        median_exp=summary["median_expectancy"], median_pf=summary["median_pf"],
        positive_windows=summary["positive_windows"], n_windows=summary["window_count"],
        edge_windows=summary["edge_windows"], total_pnl=summary["total_pnl"],
        prior_median_exp=summary["group_prior10"]["median_expectancy"],
        oos_median_exp=summary["group_oos5"]["median_expectancy"],
        symbol_concentrated=summary["symbol_concentrated"],
    )
    summary["verdict"] = verdict
    (out / "metrics_15window_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2))

    (out / "warnings.json").write_text(json.dumps({
        "data_source": "GMO Public API klines (BID), read-only",
        "fixed_config": f"rsi_reversal / {TIMEFRAME} / current_cost (spread {SPREAD}, "
                        f"slippage {SLIP}) / baseline exit / SL30 / TP60 / no ADX filter",
        "windows": {label: window_dates[label] for label in results},
        "note": "final 15-window evaluation; no parameter tuning; Public klines single-price.",
        "fetch_warnings": warnings,
    }, ensure_ascii=False, indent=2))
    _write_manifest(out, run_id, window_dates, window_group)
    _write_summary(out, by_window, by_symbol, by_reason, summary)
    _write_decision(out, summary, verdict, reasons)
    print(f"\nVERDICT: {verdict}")
    for r in reasons:
        print(f"  - {r}")
    print(f"Export written to: analysis_exports/{run_id}/")


def _build_summary(results: dict, window_stats: dict, window_group: dict,
                   all_trades: list[dict], symbol_window_wl: dict) -> dict:
    summary = robustness_summary(window_stats)
    # group split (prior10 / oos5) and chronological halves
    prior_stats = {k: v for k, v in window_stats.items() if window_group[k] == "prior10"}
    oos_stats = {k: v for k, v in window_stats.items() if window_group[k] == "oos5"}
    ordered = list(window_stats.items())  # WINDOWS order: newest -> oldest
    half = len(ordered) // 2
    recent_half = dict(ordered[:half])       # window_1.. (newest)
    older_half = dict(ordered[half:])        # ..oos_window_5 (oldest)

    def _grp(stats_map: dict, label: str) -> dict:
        g = robustness_summary(stats_map)
        g["total_pnl"] = round(sum(s["total_pnl"] for s in stats_map.values()), 2)
        g["label"] = label
        return g

    sl_pnl = round(sum(t["pnl"] for t in all_trades if t["exit_category"] == _SL), 2)
    opp_pnl = round(sum(t["pnl"] for t in all_trades if t["exit_category"] == _OPP), 2)
    sl_ratios = [s["sl_ratio"] for s in window_stats.values()]
    symbol_pnl, symbol_exp, symbol_pf = {}, {}, {}
    for sym in SYMBOLS:
        sub = [t for t in all_trades if t["symbol"] == sym]
        st = _summarize(sub)
        symbol_pnl[sym] = st["total_pnl"]
        symbol_exp[sym] = st["expectancy"]
        symbol_pf[sym] = st["profit_factor"]
    pos_pnl = sum(v for v in symbol_pnl.values() if v > 0)
    concentrated = bool(pos_pnl > 0 and max(
        (v for v in symbol_pnl.values() if v > 0), default=0) / pos_pnl > 0.6)

    summary.update({
        "total_pnl": round(sum(s["total_pnl"] for s in window_stats.values()), 2),
        "total_sl_count": sum(s["sl_count"] for s in window_stats.values()),
        "median_sl_ratio": round(statistics.median(sl_ratios), 4) if sl_ratios else 0.0,
        "opp_total_pnl": opp_pnl,
        "sl_total_pnl": sl_pnl,
        "symbol_pnl": symbol_pnl,
        "symbol_expectancy": symbol_exp,
        "symbol_pf": symbol_pf,
        "symbol_window_win_loss": {s: f"{w[0]}-{w[1]}" for s, w in symbol_window_wl.items()},
        "symbol_concentrated": concentrated,
        "group_prior10": _grp(prior_stats, "prior10"),
        "group_oos5": _grp(oos_stats, "oos5"),
        "half_recent": _grp(recent_half, "recent_half"),
        "half_older": _grp(older_half, "older_half"),
    })
    return summary


def _write_manifest(out: Path, run_id: str, window_dates: dict, window_group: dict) -> None:
    (out / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_rsi_final15", "strategy": "rsi_reversal",
        "timeframe": TIMEFRAME, "cost_scenario": "current_cost",
        "spread_pips": SPREAD, "slippage_pips": SLIP, "exit_policy": "baseline",
        "stop_loss_pips": ExecutionConfig().stop_loss_pips,
        "take_profit_pips": ExecutionConfig().take_profit_pips,
        "adx_filter": False,
        "windows": [{"window": label, "group": window_group[label], "dates": dates}
                    for label, dates in window_dates.items()],
        "symbols": SYMBOLS, "continuous_replay": True, "no_order_execution": True,
        "gmo_readonly": True, "gmo_order_enabled": False,
    }, ensure_ascii=False, indent=2))


def _write_summary(out: Path, by_window: list[dict], by_symbol: list[dict],
                   by_reason: list[dict], summary: dict) -> None:
    head = ("| window | group | 期間 | 完了 | 勝率 | 総損益 | 期待値 | PF | 最大DD | SL | 判定 |\n"
            "|--|--|--|--:|--:|--:|--:|--:|--:|--:|--|\n")
    rows = []
    for r in by_window:
        s = r["stats"]
        mark = "+" if s["expectancy"] > 0 else "−"
        rows.append(f"| {r['window']} | {r['group']} | {r['period']} | {s['completed_trades']} | "
                    f"{s['win_rate']}% | {s['total_pnl']} | {s['expectancy']} | "
                    f"{s['profit_factor']} | {s['max_drawdown']} | {s['sl_count']} | {mark} |")
    sym_rows = []
    for r in by_symbol:
        s = r["stats"]
        wl = summary["symbol_window_win_loss"][r["symbol"]]
        sym_rows.append(f"| {r['symbol']} | {s['completed_trades']} | {s['total_pnl']} | "
                        f"{s['expectancy']} | {s['profit_factor']} | {wl} |")
    rsn_rows = []
    for r in by_reason:
        s = r["stats"]
        rsn_rows.append(f"| {r['exit_reason']} | {s['completed_trades']} | {s['total_pnl']} | "
                        f"{s['expectancy']} |")
    g_p, g_o = summary["group_prior10"], summary["group_oos5"]
    text = (
        "# rsi_reversal M5 baseline 最終15窓評価 (固定条件)\n\n"
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "前10窓(Dec2025-May2026)＋OOS5窓(Oct-Dec2025)を同一固定条件で一括集計。\n\n"
        "## window別\n" + head + "\n".join(rows) + "\n\n"
        "## 15窓全体集計\n"
        f"- 期待値中央値: {summary['median_expectancy']} / PF中央値: {summary['median_pf']}\n"
        f"- プラスwindow: {summary['positive_windows']} / "
        f"マイナス: {summary['negative_windows']}\n"
        f"- 期待値>0かつPF>1のwindow: {summary['edge_windows']}\n"
        f"- 完了取引≥30のwindow: {summary['windows_ge30_trades']} / {summary['window_count']}\n"
        f"- 合計損益: {summary['total_pnl']} / 最大DD(最大): {summary['max_drawdown_max']}\n"
        f"- 最悪単発損失: {summary['worst_single_loss']} / "
        f"合計SL件数: {summary['total_sl_count']} / SL率中央値: {summary['median_sl_ratio']}\n"
        f"- 反対シグナル決済 合計損益: {summary['opp_total_pnl']} / "
        f"SL決済 合計損益: {summary['sl_total_pnl']}\n"
        f"- 単一ペア偏重: {summary['symbol_concentrated']}\n\n"
        "## 前10窓 vs OOS5窓\n"
        "| group | window数 | 期待値中央値 | PF中央値 | プラスwindow | 合計損益 | 最大DD最大 |\n"
        "|--|--:|--:|--:|--:|--:|--:|\n"
        f"| prior10 | {g_p['window_count']} | {g_p['median_expectancy']} | {g_p['median_pf']} "
        f"| {g_p['positive_windows']} | {g_p['total_pnl']} | {g_p['max_drawdown_max']} |\n"
        f"| oos5 | {g_o['window_count']} | {g_o['median_expectancy']} | {g_o['median_pf']} "
        f"| {g_o['positive_windows']} | {g_o['total_pnl']} | {g_o['max_drawdown_max']} |\n\n"
        "## symbol別(15窓合算)\n"
        "| symbol | 完了 | 総損益 | 期待値 | PF | window勝敗 |\n"
        "|--|--:|--:|--:|--:|--|\n" + "\n".join(sym_rows) + "\n\n"
        "## exit_reason別(15窓合算)\n"
        "| exit_reason | 件数 | 総損益 | 期待値 |\n"
        "|--|--:|--:|--:|\n" + "\n".join(rsn_rows) + "\n"
    )
    (out / "summary.md").write_text(text)


def _write_decision(out: Path, summary: dict, verdict: str, reasons: list[str]) -> None:
    text = (
        "# rsi_reversal M5 baseline 最終判断\n\n"
        f"## 判定: {verdict}\n\n"
        "### 根拠\n" + "\n".join(f"- {r}" for r in reasons) + "\n\n"
        "### 集計\n"
        f"- 期待値中央値 {summary['median_expectancy']} / PF中央値 {summary['median_pf']}\n"
        f"- プラスwindow {summary['positive_windows']}/{summary['window_count']}・"
        f"edge(exp>0&PF>1) {summary['edge_windows']}/{summary['window_count']}\n"
        f"- 合計損益 {summary['total_pnl']}・最大DD最大 {summary['max_drawdown_max']}\n"
        f"- 前10窓 期待値中央値 {summary['group_prior10']['median_expectancy']} "
        f"(プラス{summary['group_prior10']['positive_windows']}/10)・"
        f"OOS5窓 期待値中央値 {summary['group_oos5']['median_expectancy']} "
        f"(プラス{summary['group_oos5']['positive_windows']}/5)\n"
        f"- symbol別損益 {summary['symbol_pnl']}（偏重 {summary['symbol_concentrated']}）\n"
        f"- 反対シグナル決済 {summary['opp_total_pnl']} / SL決済 {summary['sl_total_pnl']}\n\n"
        "### 今後の扱い\n"
        "- 継続検証候補: 主検証として残す。\n"
        "- 研究用ベースライン: 弱い平均回帰傾向はあるが実用性は低い。比較用に残し、"
        "主検証は別ロジック(market structure / Bollinger 等)へ移す。\n"
        "- 撤退: rsi_reversal(既定)を主検証から外す。RSI/SL/TP/フィルター等の"
        "追加調整は過剰最適化のため行わない。\n"
    )
    (out / "rsi_reversal_final_decision.md").write_text(text)


if __name__ == "__main__":
    raise SystemExit(main())
