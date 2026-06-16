"""15-window evaluation of rsi_reversal on M15 with SCALED risk (read-only, paper).

Confound check, NOT an SL/TP search. M15 baseline reused M5's SL30/TP60, which may
be too tight for M15's larger bars (baseline SL ratio 0.586 vs M5 0.487). Volatility
scales ~ sqrt(time); M5->M15 is 3x, so 30*sqrt(3)≈52 and 60*sqrt(3)≈104. We test ONE
pre-fixed scaled setting, SL50 / TP100 (RR 1:2 kept), to see whether SL30/TP60 was an
unfair confound. Same 15 windows, same current_cost, same rsi_reversal, baseline exit.

This is a single fixed point. Do NOT try SL40/SL60/SL70/TP120 etc.

Reuses rsi_m15_15window (_collect/_tag_de) and fx_eval_common writers.

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.rsi_m15_scaled_15window
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from app.brokers import GmoFxBroker  # noqa: E402
from app.schemas.trading import ExecutionConfig  # noqa: E402
from scripts.bollinger_15window import DE_BUCKETS  # noqa: E402
from scripts.breakout_15window import _TP, BK_STAT_FIELDS, _summarize_bk  # noqa: E402
from scripts.fx_eval_common import (  # noqa: E402
    _OPP,
    _SL,
    EXPORT_ROOT,
    SLIP,
    SPREAD,
    SYMBOLS,
    WINDOWS,
    _weekdays,
    classify_strategy,
    ensure_output_dir,
    fixed_config,
    robustness_summary,
    run_id,
    safety_metadata,
    write_json,
    write_manifest,
    write_markdown,
    write_metrics_csv,
    write_summary_markdown,
    write_warnings,
)
from scripts.rsi_m15_15window import M5_REF, TIMEFRAME, _collect, _tag_de  # noqa: E402

SL_PIPS, TP_PIPS = 50.0, 100.0

# rsi_reversal M15 baseline (SL30/TP60) reference — committed run 6e120b1.
M15_BASELINE_REF = {"median_expectancy": 0.0047, "median_pf": 1.004, "positive_windows": 8,
                    "total_pnl": -7.47, "max_drawdown_max": 60.91, "total_trades": 935,
                    "median_sl_ratio": 0.5862}


def main() -> int:
    broker = GmoFxBroker()
    warnings: list[str] = []
    execution = ExecutionConfig(spread_pips=SPREAD, slippage_pips=SLIP,
                                stop_loss_pips=SL_PIPS, take_profit_pips=TP_PIPS)
    all_trades, day_de = _collect(broker, warnings, execution)
    _export(all_trades, day_de, warnings)
    return 0


def _export(all_trades: list[dict], day_de: dict, warnings: list[str]) -> None:
    rid = run_id("rsi_m15_scaled_final15")
    out = ensure_output_dir(EXPORT_ROOT / rid)
    lo, hi = _tag_de(all_trades, day_de)

    window_stats = {label: _summarize_bk([t for t in all_trades if t["window"] == label])
                    for label, _s, _e, _g in WINDOWS}
    win_group = {label: g for label, _s, _e, g in WINDOWS}
    win_dates = {label: f"{_weekdays(s, e)[0]}..{_weekdays(s, e)[-1]}"
                 for label, s, e, _g in WINDOWS}
    by_window = [{"window": label, "group": win_group[label], "period": win_dates[label],
                  "stats": st} for label, st in window_stats.items()]

    by_symbol, by_reason, by_date, by_state = [], [], [], []
    symbol_window_wl = {s: [0, 0] for s in SYMBOLS}
    for sym in SYMBOLS:
        sub = [t for t in all_trades if t["symbol"] == sym]
        if sub:
            by_symbol.append({"symbol": sym, "stats": _summarize_bk(sub)})
    for label, _s, _e, _g in WINDOWS:
        wsub = [t for t in all_trades if t["window"] == label]
        for sym in SYMBOLS:
            ssub = [t for t in wsub if t["symbol"] == sym]
            if not ssub:
                continue
            symbol_window_wl[sym][0 if sum(t["pnl"] for t in ssub) > 0 else 1] += 1
        for d in sorted({t["date"] for t in wsub}):
            by_date.append({"window": label, "date": d,
                            "stats": _summarize_bk([t for t in wsub if t["date"] == d])})
    for reason in sorted({t["exit_category"] for t in all_trades}):
        by_reason.append({"exit_reason": reason,
                          "stats": _summarize_bk([t for t in all_trades
                                                  if t["exit_category"] == reason])})
    for bucket in DE_BUCKETS:
        by_state.append({"market_state": bucket,
                         "stats": _summarize_bk([t for t in all_trades
                                                 if t.get("de_bucket") == bucket])})

    write_metrics_csv(out / "metrics_by_window.csv", by_window, ["window", "group", "period"],
                      stat_fields=BK_STAT_FIELDS)
    write_metrics_csv(out / "metrics_by_symbol.csv", by_symbol, ["symbol"],
                      stat_fields=BK_STAT_FIELDS)
    write_metrics_csv(out / "metrics_by_exit_reason.csv", by_reason, ["exit_reason"],
                      stat_fields=BK_STAT_FIELDS)
    write_metrics_csv(out / "metrics_by_date.csv", by_date, ["window", "date"],
                      stat_fields=BK_STAT_FIELDS)
    write_metrics_csv(out / "metrics_by_market_state.csv", by_state, ["market_state"],
                      stat_fields=BK_STAT_FIELDS)

    summary = _build_summary(all_trades, window_stats, win_group, symbol_window_wl, lo, hi)
    verdict, reasons = classify_strategy(
        median_exp=summary["median_expectancy"], median_pf=summary["median_pf"],
        positive_windows=summary["positive_windows"], n_windows=summary["window_count"],
        edge_windows=summary["edge_windows"], total_pnl=summary["total_pnl"],
        prior_median_exp=summary["group_prior10"]["median_expectancy"],
        oos_median_exp=summary["group_oos5"]["median_expectancy"],
        symbol_concentrated=summary["symbol_concentrated"],
    )
    summary["verdict"] = verdict
    write_json(out / "metrics_rsi_m15_scaled_15window_summary.json", summary)

    write_warnings(out, {
        **fixed_config(timeframe=TIMEFRAME, strategy="rsi_reversal",
                       stop_loss_pips=SL_PIPS, take_profit_pips=TP_PIPS, adx_filter=False),
        **safety_metadata(),
        "de_tertiles": {"low<": lo, "high>=": hi},
        "comparison_refs": "M15 baseline=6e120b1, M5 baseline=f716631 (committed runs)",
        "note": "rsi_reversal M15 SCALED-risk (SL50/TP100) confound check; single fixed point, "
                "NOT an SL/TP search. market-state breakdown uses DE tertiles only.",
        "fetch_warnings": warnings,
    })
    _write_manifest(out, rid, win_group)
    _write_summary(out, by_window, by_symbol, by_reason, by_state, summary)
    _write_decision(out, summary, verdict, reasons)
    print(f"\nVERDICT: {verdict}")
    for r in reasons:
        print(f"  - {r}")
    print(f"Export written to: analysis_exports/{rid}/")


def _build_summary(all_trades, window_stats, win_group, symbol_window_wl, lo, hi) -> dict:
    summary = robustness_summary(window_stats)
    prior = {k: v for k, v in window_stats.items() if win_group[k] == "prior10"}
    oos = {k: v for k, v in window_stats.items() if win_group[k] == "oos5"}

    def _grp(stats_map, label):
        g = robustness_summary(stats_map)
        g["total_pnl"] = round(sum(s["total_pnl"] for s in stats_map.values()), 2)
        g["median_sl_ratio"] = round(
            statistics.median([s["sl_ratio"] for s in stats_map.values()]), 4
        ) if stats_map else 0.0
        g["label"] = label
        return g

    symbol_pnl, symbol_exp, symbol_pf = {}, {}, {}
    for sym in SYMBOLS:
        st = _summarize_bk([t for t in all_trades if t["symbol"] == sym])
        symbol_pnl[sym], symbol_exp[sym], symbol_pf[sym] = (
            st["total_pnl"], st["expectancy"], st["profit_factor"])
    pos_pnl = sum(v for v in symbol_pnl.values() if v > 0)
    concentrated = bool(pos_pnl > 0 and max(
        (v for v in symbol_pnl.values() if v > 0), default=0) / pos_pnl > 0.6)
    sl_ratios = [s["sl_ratio"] for s in window_stats.values()]
    total_trades = sum(s["completed_trades"] for s in window_stats.values())
    total_pnl = round(sum(s["total_pnl"] for s in window_stats.values()), 2)
    summary.update({
        "total_pnl": total_pnl,
        "total_trades": total_trades,
        "per_trade_expectancy": round(total_pnl / total_trades, 4) if total_trades else 0.0,
        "dd_to_pnl": round(summary["max_drawdown_max"] / total_pnl, 2) if total_pnl > 0 else None,
        "total_sl_count": sum(s["sl_count"] for s in window_stats.values()),
        "total_tp_count": sum(s["tp_count"] for s in window_stats.values()),
        "median_sl_ratio": round(statistics.median(sl_ratios), 4) if sl_ratios else 0.0,
        "tp_total_pnl": round(sum(t["pnl"] for t in all_trades if t["exit_category"] == _TP), 2),
        "sl_total_pnl": round(sum(t["pnl"] for t in all_trades if t["exit_category"] == _SL), 2),
        "opp_total_pnl": round(sum(t["pnl"] for t in all_trades if t["exit_category"] == _OPP), 2),
        "symbol_pnl": symbol_pnl, "symbol_expectancy": symbol_exp, "symbol_pf": symbol_pf,
        "symbol_window_win_loss": {s: f"{w[0]}-{w[1]}" for s, w in symbol_window_wl.items()},
        "symbol_concentrated": concentrated,
        "group_prior10": _grp(prior, "prior10"),
        "group_oos5": _grp(oos, "oos5"),
        "de_tertiles": {"low<": lo, "high>=": hi},
        "m15_baseline_ref": M15_BASELINE_REF,
        "m5_ref": M5_REF,
    })
    return summary


def _write_manifest(out: Path, rid: str, win_group: dict) -> None:
    write_manifest(out, {
        "run_id": rid, "created_at": pd.Timestamp.now().isoformat(),
        "kind": "gmo_public_paper_rsi_m15_scaled_final15", "strategy": "rsi_reversal",
        "scaled_risk_note": "SL50/TP100 (1:2) — single fixed confound check vs M15 baseline 30/60",
        **fixed_config(timeframe=TIMEFRAME, stop_loss_pips=SL_PIPS,
                       take_profit_pips=TP_PIPS, adx_filter=False),
        **safety_metadata(),
        "windows": [{"window": label, "group": g, "dates": _weekdays(s, e)}
                    for label, s, e, g in WINDOWS],
    })


def _write_summary(out, by_window, by_symbol, by_reason, by_state, summary) -> None:
    win_h = ("| window | group | 期間 | 完了 | 勝率 | 総損益 | 期待値 | PF | 最大DD | SL | SL率 "
             "| TP | 判定 |\n|--|--|--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--|\n")
    win_rows = "\n".join(
        f"| {r['window']} | {r['group']} | {r['period']} | {s['completed_trades']} | "
        f"{s['win_rate']}% | {s['total_pnl']} | {s['expectancy']} | {s['profit_factor']} | "
        f"{s['max_drawdown']} | {s['sl_count']} | {s['sl_ratio']} | {s['tp_count']} | "
        f"{'+' if s['expectancy'] > 0 else '−'} |"
        for r in by_window for s in [r["stats"]])
    sym_rows = "\n".join(
        f"| {r['symbol']} | {r['stats']['completed_trades']} | {r['stats']['total_pnl']} | "
        f"{r['stats']['expectancy']} | {r['stats']['profit_factor']} | "
        f"{summary['symbol_window_win_loss'][r['symbol']]} |" for r in by_symbol)
    rsn_rows = "\n".join(
        f"| {r['exit_reason']} | {r['stats']['completed_trades']} | {r['stats']['total_pnl']} | "
        f"{r['stats']['expectancy']} |" for r in by_reason)
    st_rows = "\n".join(
        f"| {r['market_state']} | {r['stats']['completed_trades']} | {r['stats']['total_pnl']} | "
        f"{r['stats']['expectancy']} | {r['stats']['profit_factor']} |" for r in by_state)
    g_p, g_o = summary["group_prior10"], summary["group_oos5"]
    m15, m5 = summary["m15_baseline_ref"], summary["m5_ref"]
    cmp_h = ("| 条件 | 期待値中央値 | PF中央値 | プラスwindow | 合計損益 | 最大DD最大 | 総取引 "
             "| SL率中央 |\n|--|--:|--:|--:|--:|--:|--:|--:|\n")
    cmp_rows = (
        f"| M15 scaled(50/100) | {summary['median_expectancy']} | {summary['median_pf']} | "
        f"{summary['positive_windows']} | {summary['total_pnl']} | {summary['max_drawdown_max']} "
        f"| {summary['total_trades']} | {summary['median_sl_ratio']} |\n"
        f"| M15 baseline(30/60) | {m15['median_expectancy']} | {m15['median_pf']} | "
        f"{m15['positive_windows']} | {m15['total_pnl']} | {m15['max_drawdown_max']} | "
        f"{m15['total_trades']} | {m15['median_sl_ratio']} |\n"
        f"| M5 baseline(30/60) | {m5['median_expectancy']} | {m5['median_pf']} | "
        f"{m5['positive_windows']} | {m5['total_pnl']} | {m5['max_drawdown_max']} | "
        f"{m5['total_trades']} | 0.487 |\n")
    text = (
        "# rsi_reversal M15 scaled-risk 15窓評価 (SL50/TP100・1点固定の交絡確認)\n\n"
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "SL/TP探索ではなくSL30/TP60交絡の1点固定診断。M15 baseline/M5 baselineと同一15窓。\n\n"
        "## window別\n" + win_h + win_rows + "\n\n"
        "## 15窓全体集計\n"
        f"- 期待値中央値: {summary['median_expectancy']} / PF中央値: {summary['median_pf']}\n"
        f"- プラスwindow: {summary['positive_windows']} / マイナス: {summary['negative_windows']}"
        f" / edge(exp>0&PF>1): {summary['edge_windows']}\n"
        f"- 完了≥30のwindow: {summary['windows_ge30_trades']}/{summary['window_count']} / "
        f"総取引: {summary['total_trades']} / 1取引期待値: {summary['per_trade_expectancy']}\n"
        f"- 合計損益: {summary['total_pnl']} / 最大DD最大: {summary['max_drawdown_max']} / "
        f"DD/損益: {summary['dd_to_pnl']}\n"
        f"- 合計SL: {summary['total_sl_count']} / 合計TP: {summary['total_tp_count']} / "
        f"SL率中央: {summary['median_sl_ratio']}\n"
        f"- TP損益: {summary['tp_total_pnl']} / SL損益: {summary['sl_total_pnl']} / "
        f"反対損益: {summary['opp_total_pnl']}\n"
        f"- 単一ペア偏重: {summary['symbol_concentrated']} / DE三分位 "
        f"low<{summary['de_tertiles']['low<']} high>={summary['de_tertiles']['high>=']}\n\n"
        "## prior10 vs oos5\n"
        "| group | window数 | 期待値中央値 | PF中央値 | プラスwindow | 合計損益 | 最大DD最大 "
        "| SL率中央 |\n|--|--:|--:|--:|--:|--:|--:|--:|\n"
        f"| prior10 | {g_p['window_count']} | {g_p['median_expectancy']} | {g_p['median_pf']} | "
        f"{g_p['positive_windows']} | {g_p['total_pnl']} | {g_p['max_drawdown_max']} | "
        f"{g_p['median_sl_ratio']} |\n"
        f"| oos5 | {g_o['window_count']} | {g_o['median_expectancy']} | {g_o['median_pf']} | "
        f"{g_o['positive_windows']} | {g_o['total_pnl']} | {g_o['max_drawdown_max']} | "
        f"{g_o['median_sl_ratio']} |\n\n"
        "## M15 baseline / M5 baseline との比較\n" + cmp_h + cmp_rows + "\n"
        "## symbol別(15窓合算)\n"
        "| symbol | 完了 | 総損益 | 期待値 | PF | window勝敗 |\n|--|--:|--:|--:|--:|--|\n"
        + sym_rows + "\n\n"
        "## exit_reason別(15窓合算)\n"
        "| exit_reason | 件数 | 総損益 | 期待値 |\n|--|--:|--:|--:|\n" + rsn_rows + "\n\n"
        "## market-state別(DE三分位のみ)\n"
        "| market_state | 完了 | 総損益 | 期待値 | PF |\n|--|--:|--:|--:|--:|\n" + st_rows + "\n"
    )
    write_summary_markdown(out, text)


def _write_decision(out, summary, verdict, reasons) -> None:
    m15, m5 = summary["m15_baseline_ref"], summary["m5_ref"]
    text = (
        "# rsi_reversal M15 scaled-risk (SL50/TP100) 最終判断\n\n"
        f"## 判定: {verdict}\n\n"
        "### 根拠\n" + "\n".join(f"- {r}" for r in reasons) + "\n\n"
        "### 集計\n"
        f"- 期待値中央値 {summary['median_expectancy']} / PF中央値 {summary['median_pf']} / "
        f"プラス窓 {summary['positive_windows']}/{summary['window_count']}\n"
        f"- 合計損益 {summary['total_pnl']} "
        f"（M15base={m15['total_pnl']} / M5base={m5['total_pnl']}）\n"
        f"- SL率中央 {summary['median_sl_ratio']} "
        f"（M15base={m15['median_sl_ratio']} / M5base=0.487）\n"
        f"- 総取引 {summary['total_trades']}（M15base={m15['total_trades']}）/ "
        f"1取引期待値 {summary['per_trade_expectancy']}\n"
        f"- prior10 中央値 {summary['group_prior10']['median_expectancy']} / "
        f"oos5 中央値 {summary['group_oos5']['median_expectancy']}\n"
        f"- TP {summary['tp_total_pnl']} / SL {summary['sl_total_pnl']} / "
        f"反対 {summary['opp_total_pnl']}\n\n"
        "### SL/TP交絡の解釈\n"
        "- SL率が baseline より下がり総損益・期待値が改善 → SL30/TP60 はM15に不利な交絡だった。\n"
        "- 改善しない/悪化 → 交絡ではなく、M15でも単純rsiにエッジが無い。\n\n"
        "### 今後の扱い\n"
        "- 継続検証候補 / 研究用ベースライン / 撤退 のいずれか（本文の判定に従う）。\n"
        "- これは1点固定の交絡確認。SL/TPの多点探索は過剰最適化のため行わない。\n"
    )
    write_markdown(out / "rsi_m15_scaled_final_decision.md", text)


if __name__ == "__main__":
    raise SystemExit(main())
