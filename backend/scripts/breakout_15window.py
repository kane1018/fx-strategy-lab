"""15-window evaluation of StrategyType.BREAKOUT (read-only, paper).

Hypothesis: in the trending weeks where rsi_reversal bleeds via its SL tail, a
breakout/trend strategy may earn by going WITH the move. Evaluates the existing
StrategyType.BREAKOUT over the SAME 15 windows, SAME fixed config (no tuning):
M5, current_cost (spread 1.2 / slippage 0.2), baseline exit, SL 30 / TP 60,
continuous replay, no ADX filter, breakout_period default (20).

Reuses the rsi_final_15window fetch/replay/classify pipeline. Adds TP tracking
and a direct comparison against the committed rsi_reversal M5 baseline.

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.breakout_15window
"""

from __future__ import annotations

import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.brokers import GmoFxBroker  # noqa: E402
from app.schemas.trading import ExecutionConfig, StrategyConfig, StrategyType  # noqa: E402
from scripts.fx_eval_common import (  # noqa: E402
    ensure_output_dir,
    run_id,
    validate_summary_schema,
    write_json,
    write_manifest,
    write_metrics_csv,
    write_summary_markdown,
    write_warnings,
)
from scripts.robustness_windows import (  # noqa: E402
    _OPP,
    _SL,
    _STAT_FIELDS,
    _summarize,
    _weekdays,
    robustness_summary,
)
from scripts.rsi_final_15window import (  # noqa: E402
    SLIP,
    SPREAD,
    SYMBOLS,
    TIMEFRAME,
    WINDOWS,
    _fetch_window_trades,
    classify_strategy,
)

EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "analysis_exports"
_TP = "利確到達(TP)"
BK_STAT_FIELDS = [*_STAT_FIELDS, "tp_count", "tp_total_pnl"]

# rsi_reversal M5 baseline reference (committed run f716631,
# 20260616_082807_gmo_public_paper_rsi_final15) for side-by-side comparison.
RSI_BASELINE_REF = {
    "median_expectancy": 0.0164, "median_pf": 1.016, "positive_windows": 8,
    "negative_windows": 7, "total_pnl": 56.95, "max_drawdown_max": 65.46,
}
RSI_WINDOW_EXP = {
    "window_1": 0.2992, "window_2": 0.122, "window_3": -0.1745, "window_4": 0.3233,
    "window_5": -0.2923, "window_6": 0.3082, "window_7": -0.0723, "window_8": 0.1197,
    "window_9": -0.2883, "window_10": 0.4045, "oos_window_1": 0.2314,
    "oos_window_2": -0.021, "oos_window_3": 0.0164, "oos_window_4": -0.3732,
    "oos_window_5": -0.1156,
}


def _summarize_bk(trades: list[dict]) -> dict:
    base = _summarize(trades)
    tp = [t for t in trades if t["exit_category"] == _TP]
    base["tp_count"] = len(tp)
    base["tp_total_pnl"] = round(sum(t["pnl"] for t in tp), 2)
    return base


def complement_stats(rsi_exp: dict[str, float], bk_stats: dict[str, dict]) -> dict:
    """How does breakout do in exactly the windows where rsi_reversal lost?"""
    neg = [w for w, e in rsi_exp.items() if e <= 0]
    bk_pos = sum(1 for w in neg if bk_stats.get(w, {}).get("expectancy", 0) > 0)
    bk_pnl = round(sum(bk_stats.get(w, {}).get("total_pnl", 0) for w in neg), 2)
    return {
        "rsi_negative_windows": len(neg),
        "breakout_positive_in_those": bk_pos,
        "breakout_total_pnl_in_those": bk_pnl,
        "windows": neg,
    }


def main() -> int:
    strategy = StrategyConfig(strategy_type=StrategyType.BREAKOUT)  # defaults: period 20
    execution = ExecutionConfig(spread_pips=SPREAD, slippage_pips=SLIP)  # SL30/TP60
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
        s = _summarize_bk(trades)
        print(f"{label:>13} {start}-{end} [{group}] n={s['completed_trades']:>4} "
              f"exp={s['expectancy']:>8} PF={s['profit_factor']} "
              f"maxDD={s['max_drawdown']} SL={s['sl_count']} TP={s['tp_count']}")

    _export(results, window_dates, window_group, warnings)
    return 0


def _export(results: dict, window_dates: dict, window_group: dict, warnings: list[str]) -> None:
    rid = run_id("breakout15")
    out = ensure_output_dir(EXPORT_ROOT / rid)

    window_stats = {label: _summarize_bk(tr) for label, tr in results.items()}
    by_window = [{"window": label, "group": window_group[label],
                  "period": f"{window_dates[label][0]}..{window_dates[label][-1]}",
                  "stats": st} for label, st in window_stats.items()]

    all_trades = [t for tr in results.values() for t in tr]
    by_symbol, by_reason, by_date = [], [], []
    symbol_window_wl: dict[str, list[int]] = {s: [0, 0] for s in SYMBOLS}
    for sym in SYMBOLS:
        sub = [t for t in all_trades if t["symbol"] == sym]
        if sub:
            by_symbol.append({"symbol": sym, "stats": _summarize_bk(sub)})
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
            by_date.append({"window": label, "date": d, "stats": _summarize_bk(sub)})
    for reason in sorted({t["exit_category"] for t in all_trades}):
        sub = [t for t in all_trades if t["exit_category"] == reason]
        by_reason.append({"exit_reason": reason, "stats": _summarize_bk(sub)})

    write_metrics_csv(out / "metrics_by_window.csv", by_window, ["window", "group", "period"],
                      stat_fields=BK_STAT_FIELDS)
    write_metrics_csv(out / "metrics_by_symbol.csv", by_symbol, ["symbol"],
                      stat_fields=BK_STAT_FIELDS)
    write_metrics_csv(out / "metrics_by_exit_reason.csv", by_reason, ["exit_reason"],
                      stat_fields=BK_STAT_FIELDS)
    write_metrics_csv(out / "metrics_by_date.csv", by_date, ["window", "date"],
                      stat_fields=BK_STAT_FIELDS)

    summary = _build_summary(results, window_stats, window_group, all_trades, symbol_window_wl)
    verdict, reasons = classify_strategy(
        median_exp=summary["median_expectancy"], median_pf=summary["median_pf"],
        positive_windows=summary["positive_windows"], n_windows=summary["window_count"],
        edge_windows=summary["edge_windows"], total_pnl=summary["total_pnl"],
        prior_median_exp=summary["group_prior10"]["median_expectancy"],
        oos_median_exp=summary["group_oos5"]["median_expectancy"],
        symbol_concentrated=summary["symbol_concentrated"],
    )
    summary["verdict"] = verdict
    validate_summary_schema(summary)
    write_json(out / "metrics_breakout_15window_summary.json", summary)

    write_warnings(out, {
        "data_source": "GMO Public API klines (BID), read-only",
        "fixed_config": f"breakout(period 20) / {TIMEFRAME} / current_cost (spread {SPREAD}, "
                        f"slippage {SLIP}) / baseline exit / SL30 / TP60 / no ADX filter",
        "windows": {label: window_dates[label] for label in results},
        "rsi_baseline_ref_run": "20260616_082807_gmo_public_paper_rsi_final15 (commit f716631)",
        "note": "breakout 15-window evaluation; no parameter tuning; Public klines single-price.",
        "fetch_warnings": warnings,
    })
    _write_manifest(out, rid, window_dates, window_group)
    _write_summary(out, by_window, by_symbol, by_reason, summary)
    _write_decision(out, summary, verdict, reasons)
    print(f"\nVERDICT: {verdict}")
    for r in reasons:
        print(f"  - {r}")
    print(f"complement: {summary['complement_vs_rsi']}")
    print(f"Export written to: analysis_exports/{rid}/")


def _build_summary(results: dict, window_stats: dict, window_group: dict,
                   all_trades: list[dict], symbol_window_wl: dict) -> dict:
    summary = robustness_summary(window_stats)
    prior_stats = {k: v for k, v in window_stats.items() if window_group[k] == "prior10"}
    oos_stats = {k: v for k, v in window_stats.items() if window_group[k] == "oos5"}

    def _grp(stats_map: dict, label: str) -> dict:
        g = robustness_summary(stats_map)
        g["total_pnl"] = round(sum(s["total_pnl"] for s in stats_map.values()), 2)
        g["label"] = label
        return g

    sl_pnl = round(sum(t["pnl"] for t in all_trades if t["exit_category"] == _SL), 2)
    tp_pnl = round(sum(t["pnl"] for t in all_trades if t["exit_category"] == _TP), 2)
    opp_pnl = round(sum(t["pnl"] for t in all_trades if t["exit_category"] == _OPP), 2)
    sl_ratios = [s["sl_ratio"] for s in window_stats.values()]
    symbol_pnl, symbol_exp, symbol_pf = {}, {}, {}
    for sym in SYMBOLS:
        st = _summarize_bk([t for t in all_trades if t["symbol"] == sym])
        symbol_pnl[sym] = st["total_pnl"]
        symbol_exp[sym] = st["expectancy"]
        symbol_pf[sym] = st["profit_factor"]
    pos_pnl = sum(v for v in symbol_pnl.values() if v > 0)
    concentrated = bool(pos_pnl > 0 and max(
        (v for v in symbol_pnl.values() if v > 0), default=0) / pos_pnl > 0.6)

    summary.update({
        "total_pnl": round(sum(s["total_pnl"] for s in window_stats.values()), 2),
        "total_sl_count": sum(s["sl_count"] for s in window_stats.values()),
        "total_tp_count": sum(s["tp_count"] for s in window_stats.values()),
        "median_sl_ratio": round(statistics.median(sl_ratios), 4) if sl_ratios else 0.0,
        "opp_total_pnl": opp_pnl,
        "tp_total_pnl": tp_pnl,
        "sl_total_pnl": sl_pnl,
        "symbol_pnl": symbol_pnl,
        "symbol_expectancy": symbol_exp,
        "symbol_pf": symbol_pf,
        "symbol_window_win_loss": {s: f"{w[0]}-{w[1]}" for s, w in symbol_window_wl.items()},
        "symbol_concentrated": concentrated,
        "group_prior10": _grp(prior_stats, "prior10"),
        "group_oos5": _grp(oos_stats, "oos5"),
        "rsi_baseline_ref": RSI_BASELINE_REF,
        "complement_vs_rsi": complement_stats(RSI_WINDOW_EXP, window_stats),
    })
    return summary


def _write_manifest(out: Path, rid: str, window_dates: dict, window_group: dict) -> None:
    write_manifest(out, {
        "run_id": rid, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_breakout15", "strategy": "breakout",
        "breakout_period": StrategyConfig(strategy_type=StrategyType.BREAKOUT).breakout_period,
        "timeframe": TIMEFRAME, "cost_scenario": "current_cost",
        "spread_pips": SPREAD, "slippage_pips": SLIP, "exit_policy": "baseline",
        "stop_loss_pips": ExecutionConfig().stop_loss_pips,
        "take_profit_pips": ExecutionConfig().take_profit_pips,
        "adx_filter": False,
        "windows": [{"window": label, "group": window_group[label], "dates": dates}
                    for label, dates in window_dates.items()],
        "symbols": SYMBOLS, "continuous_replay": True, "no_order_execution": True,
        "gmo_readonly": True, "gmo_order_enabled": False,
    })


def _write_summary(out: Path, by_window: list[dict], by_symbol: list[dict],
                   by_reason: list[dict], summary: dict) -> None:
    head = ("| window | group | 期間 | 完了 | 勝率 | 総損益 | 期待値 | PF | 最大DD "
            "| SL | TP | 判定 |\n|--|--|--|--:|--:|--:|--:|--:|--:|--:|--:|--|\n")
    rows = []
    for r in by_window:
        s = r["stats"]
        mark = "+" if s["expectancy"] > 0 else "−"
        rows.append(f"| {r['window']} | {r['group']} | {r['period']} | {s['completed_trades']} | "
                    f"{s['win_rate']}% | {s['total_pnl']} | {s['expectancy']} | "
                    f"{s['profit_factor']} | {s['max_drawdown']} | {s['sl_count']} | "
                    f"{s['tp_count']} | {mark} |")
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
    g_p, g_o, ref = summary["group_prior10"], summary["group_oos5"], summary["rsi_baseline_ref"]
    cmp = summary["complement_vs_rsi"]
    text = (
        "# StrategyType.BREAKOUT M5 15窓評価 (固定条件)\n\n"
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "rsi_reversalと同一15窓・同一固定条件で集計。\n\n"
        "## window別\n" + head + "\n".join(rows) + "\n\n"
        "## 15窓全体集計\n"
        f"- 期待値中央値: {summary['median_expectancy']} / PF中央値: {summary['median_pf']}\n"
        f"- プラスwindow: {summary['positive_windows']} / "
        f"マイナス: {summary['negative_windows']}\n"
        f"- 期待値>0かつPF>1のwindow: {summary['edge_windows']}\n"
        f"- 完了取引≥30のwindow: {summary['windows_ge30_trades']} / {summary['window_count']}\n"
        f"- 合計損益: {summary['total_pnl']} / 最大DD(最大): {summary['max_drawdown_max']}\n"
        f"- 最悪単発損失: {summary['worst_single_loss']} / "
        f"合計SL件数: {summary['total_sl_count']} / 合計TP件数: {summary['total_tp_count']} / "
        f"SL率中央値: {summary['median_sl_ratio']}\n"
        f"- TP決済 合計損益: {summary['tp_total_pnl']} / SL決済 合計損益: {summary['sl_total_pnl']}"
        f" / 反対シグナル決済 合計損益: {summary['opp_total_pnl']}\n"
        f"- 単一ペア偏重: {summary['symbol_concentrated']}\n\n"
        "## prior10 vs oos5\n"
        "| group | window数 | 期待値中央値 | PF中央値 | プラスwindow | 合計損益 | 最大DD最大 |\n"
        "|--|--:|--:|--:|--:|--:|--:|\n"
        f"| prior10 | {g_p['window_count']} | {g_p['median_expectancy']} | {g_p['median_pf']} "
        f"| {g_p['positive_windows']} | {g_p['total_pnl']} | {g_p['max_drawdown_max']} |\n"
        f"| oos5 | {g_o['window_count']} | {g_o['median_expectancy']} | {g_o['median_pf']} "
        f"| {g_o['positive_windows']} | {g_o['total_pnl']} | {g_o['max_drawdown_max']} |\n\n"
        "## rsi_reversal M5 baseline との比較\n"
        "| strategy | 期待値中央値 | PF中央値 | プラスwindow数 | 合計損益 | 最大DD最大値 |\n"
        "|--|--:|--:|--:|--:|--:|\n"
        f"| breakout | {summary['median_expectancy']} | {summary['median_pf']} | "
        f"{summary['positive_windows']} | {summary['total_pnl']} | "
        f"{summary['max_drawdown_max']} |\n"
        f"| rsi_reversal | {ref['median_expectancy']} | {ref['median_pf']} | "
        f"{ref['positive_windows']} | {ref['total_pnl']} | {ref['max_drawdown_max']} |\n\n"
        f"## rsi負け窓の補完\n"
        f"- rsiがマイナスのwindow {cmp['rsi_negative_windows']}個中、breakoutがプラス "
        f"{cmp['breakout_positive_in_those']}個・その窓でのbreakout合計損益 "
        f"{cmp['breakout_total_pnl_in_those']}\n"
        f"- 対象window: {cmp['windows']}\n\n"
        "## symbol別(15窓合算)\n"
        "| symbol | 完了 | 総損益 | 期待値 | PF | window勝敗 |\n"
        "|--|--:|--:|--:|--:|--|\n" + "\n".join(sym_rows) + "\n\n"
        "## exit_reason別(15窓合算)\n"
        "| exit_reason | 件数 | 総損益 | 期待値 |\n"
        "|--|--:|--:|--:|\n" + "\n".join(rsn_rows) + "\n"
    )
    write_summary_markdown(out, text)


def _write_decision(out: Path, summary: dict, verdict: str, reasons: list[str]) -> None:
    cmp = summary["complement_vs_rsi"]
    ref = summary["rsi_baseline_ref"]
    text = (
        "# StrategyType.BREAKOUT M5 最終判断\n\n"
        f"## 判定: {verdict}\n\n"
        "### 根拠\n" + "\n".join(f"- {r}" for r in reasons) + "\n\n"
        "### 集計\n"
        f"- 期待値中央値 {summary['median_expectancy']} / PF中央値 {summary['median_pf']}\n"
        f"- プラスwindow {summary['positive_windows']}/{summary['window_count']}・"
        f"edge(exp>0&PF>1) {summary['edge_windows']}/{summary['window_count']}\n"
        f"- 合計損益 {summary['total_pnl']}・最大DD最大 {summary['max_drawdown_max']}\n"
        f"- 前10窓 期待値中央値 {summary['group_prior10']['median_expectancy']} / "
        f"OOS5窓 期待値中央値 {summary['group_oos5']['median_expectancy']}\n"
        f"- TP決済 {summary['tp_total_pnl']} / SL決済 {summary['sl_total_pnl']} / "
        f"反対 {summary['opp_total_pnl']}\n\n"
        "### rsi_reversal M5 baseline との比較\n"
        f"- breakout 期待値中央値 {summary['median_expectancy']} / "
        f"rsi {ref['median_expectancy']}\n"
        f"- breakout 合計損益 {summary['total_pnl']} / rsi {ref['total_pnl']}\n"
        f"- rsi負け窓{cmp['rsi_negative_windows']}個中breakoutプラス"
        f"{cmp['breakout_positive_in_those']}個 (合計損益 "
        f"{cmp['breakout_total_pnl_in_those']}) → 補完性の有無\n\n"
        "### 今後の扱い\n"
        "- 継続検証候補: 主検証として残す。\n"
        "- 研究用ベースライン: 構造はあるが実用性は低い。比較用に残す。\n"
        "- 撤退: 主検証から外し、market structure / Bollinger / 別戦略へ移行。\n"
        "- breakoutパラメータ・SL/TP・フィルタの追加調整は過剰最適化のため行わない。\n"
    )
    (out / "breakout_final_decision.md").write_text(text)


if __name__ == "__main__":
    raise SystemExit(main())
