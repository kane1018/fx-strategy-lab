"""15-window evaluation of rsi_reversal on M15 (read-only, paper).

First step of the higher-timeframe phase. M5 rsi_reversal was only a research
baseline (thin edge eaten by cost + trend-day SL tail). Hypothesis: raising the
timeframe to M15 lowers entry frequency and raises per-trade range, possibly
improving the edge / cost ratio.

Same 15 windows, same FIXED config as M5 except timeframe=M15 (no tuning):
current_cost (spread 1.2 / slippage 0.2), baseline exit, SL 30 / TP 60,
4 JPY pairs, continuous replay, no filters. SL/TP are deliberately NOT re-tuned
for M15 — this is a like-for-like "does M15 help by itself" check.

Reuses scripts/fx_eval_common.py (windows, fixed config, safety metadata, run id,
classification) and the shared summarizers. market-state breakdown uses DE tertiles
only (day-class buckets would require a breakout M15 run, which is out of scope).

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.rsi_m15_15window
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.brokers import GmoFxBroker, GmoFxBrokerError  # noqa: E402
from app.models import PaperTrade  # noqa: E402
from app.schemas.trading import Candle, ExecutionConfig, StrategyConfig, StrategyType  # noqa: E402
from app.services.gmo_paper_service import replay_paper_trades  # noqa: E402
from app.services.market_data_service import candles_to_frame, pip_size  # noqa: E402
from scripts.bollinger_15window import DE_BUCKETS, de_bucket, de_thresholds  # noqa: E402
from scripts.breakout_15window import _TP, BK_STAT_FIELDS, _summarize_bk  # noqa: E402
from scripts.fx_eval_common import (  # noqa: E402
    _OPP,
    _SL,
    EXPORT_ROOT,
    SLIP,
    SPREAD,
    SYMBOLS,
    WINDOWS,
    _exit_category,
    _mem,
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
from scripts.market_state_diagnostics import _day_market_state  # noqa: E402

TIMEFRAME = "M15"

# rsi_reversal M5 baseline reference (committed run f716631) for comparison.
M5_REF = {"median_expectancy": 0.0164, "median_pf": 1.016, "positive_windows": 8,
          "total_pnl": 56.95, "max_drawdown_max": 65.46, "total_trades": 2069}


def _fetch_candles(broker: GmoFxBroker, symbol: str, dates: list[str],
                   warnings: list[str]) -> list[Candle] | None:
    chunks = []
    for date in dates:
        try:
            chunks.append(candles_to_frame(broker.candles(symbol, TIMEFRAME, 2000, date=date)))
        except GmoFxBrokerError as error:
            warnings.append(f"fetch failed {symbol} {date}: {error}")
        time.sleep(0.2)
    if not chunks:
        return None
    merged = pd.concat(chunks, ignore_index=True)
    merged = merged.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    return [Candle(timestamp=pd.Timestamp(r["timestamp"]).to_pydatetime(),
                   open=float(r["open"]), high=float(r["high"]), low=float(r["low"]),
                   close=float(r["close"]), volume=0) for _, r in merged.iterrows()]


def _replay_full(candles: list[Candle], symbol: str, strategy: StrategyConfig,
                 execution: ExecutionConfig) -> list[dict]:
    out: list[dict] = []
    with _mem() as db:
        res = replay_paper_trades(
            db, symbol=symbol, timeframe=TIMEFRAME, candles=candles, strategy=strategy,
            execution=execution, exit_policy="baseline", force_close_at_end=True,
            fast_signals=True,
        )
        rows = db.scalars(select(PaperTrade).where(
            PaperTrade.session_id == res["session_id"],
            PaperTrade.status == "closed")).all()
        for t in rows:
            out.append({"date": t.opened_at.date().isoformat(), "pnl": float(t.realized_pnl),
                        "symbol": symbol, "closed_at": t.closed_at,
                        "exit_category": _exit_category(t.exit_reason or "")})
    return out


def _collect(broker: GmoFxBroker, warnings: list[str],
             execution: ExecutionConfig | None = None) -> tuple[list[dict], dict]:
    rsi = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    if execution is None:  # default = M15 baseline (SL30/TP60); scaled variant passes its own
        execution = ExecutionConfig(spread_pips=SPREAD, slippage_pips=SLIP)
    all_trades: list[dict] = []
    day_de: dict[tuple[str, str], float] = {}
    for label, start, end, group in WINDOWS:
        dates = _weekdays(start, end)
        for symbol in SYMBOLS:
            candles = _fetch_candles(broker, symbol, dates, warnings)
            if not candles:
                continue
            pip = pip_size(symbol)
            trades = _replay_full(candles, symbol, rsi, execution)
            frame = candles_to_frame(candles)
            frame["date"] = pd.to_datetime(frame["timestamp"]).dt.date.astype(str)
            for date, day_frame in frame.groupby("date"):
                day_de[(symbol, date)] = _day_market_state(day_frame, pip)["direction_efficiency"]
            for t in trades:
                all_trades.append({**t, "window": label, "group": group})
        done = sum(1 for t in all_trades if t["window"] == label)
        print(f"{label:>13} {start}-{end} [{group}] rsi_M15 trades={done}")
    return all_trades, day_de


def _tag_de(all_trades: list[dict], day_de: dict) -> tuple[float, float]:
    lo, hi = de_thresholds(list(day_de.values()))
    for t in all_trades:
        t["de_bucket"] = de_bucket(day_de.get((t["symbol"], t["date"]), 0.0), lo, hi)
    return lo, hi


def main() -> int:
    broker = GmoFxBroker()
    warnings: list[str] = []
    all_trades, day_de = _collect(broker, warnings)
    _export(all_trades, day_de, warnings)
    return 0


def _export(all_trades: list[dict], day_de: dict, warnings: list[str]) -> None:
    rid = run_id("rsi_m15_final15")
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
    write_json(out / "metrics_rsi_m15_15window_summary.json", summary)

    write_warnings(out, {
        **fixed_config(timeframe=TIMEFRAME, strategy="rsi_reversal", adx_filter=False),
        **safety_metadata(),
        "de_tertiles": {"low<": lo, "high>=": hi},
        "comparison_ref": "rsi_reversal M5 = f716631 (committed 15-window run)",
        "note": "rsi_reversal M15 15-window evaluation; SL/TP NOT re-tuned for M15; no tuning. "
                "market-state breakdown uses DE tertiles only (day-class needs breakout M15).",
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
        "m5_ref": M5_REF,
    })
    return summary


def _write_manifest(out: Path, rid: str, win_group: dict) -> None:
    write_manifest(out, {
        "run_id": rid, "created_at": pd.Timestamp.now().isoformat(),
        "kind": "gmo_public_paper_rsi_m15_final15", "strategy": "rsi_reversal",
        **fixed_config(timeframe=TIMEFRAME, adx_filter=False),
        **safety_metadata(),
        "windows": [{"window": label, "group": g, "dates": _weekdays(s, e)}
                    for label, s, e, g in WINDOWS],
    })


def _write_summary(out, by_window, by_symbol, by_reason, by_state, summary) -> None:
    win_h = ("| window | group | 期間 | 完了 | 勝率 | 総損益 | 期待値 | PF | 最大DD | SL | TP "
             "| 判定 |\n|--|--|--|--:|--:|--:|--:|--:|--:|--:|--:|--|\n")
    win_rows = "\n".join(
        f"| {r['window']} | {r['group']} | {r['period']} | {s['completed_trades']} | "
        f"{s['win_rate']}% | {s['total_pnl']} | {s['expectancy']} | {s['profit_factor']} | "
        f"{s['max_drawdown']} | {s['sl_count']} | {s['tp_count']} | "
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
    g_p, g_o, m5 = summary["group_prior10"], summary["group_oos5"], summary["m5_ref"]
    text = (
        "# rsi_reversal M15 15窓評価 (current_cost / SL30・TP60 固定・M5と同条件)\n\n"
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "M5と同一15窓・同一固定条件で timeframe のみ M15。SL/TPはM15用に未調整。\n\n"
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
        "| group | window数 | 期待値中央値 | PF中央値 | プラスwindow | 合計損益 | 最大DD最大 |\n"
        "|--|--:|--:|--:|--:|--:|--:|\n"
        f"| prior10 | {g_p['window_count']} | {g_p['median_expectancy']} | {g_p['median_pf']} | "
        f"{g_p['positive_windows']} | {g_p['total_pnl']} | {g_p['max_drawdown_max']} |\n"
        f"| oos5 | {g_o['window_count']} | {g_o['median_expectancy']} | {g_o['median_pf']} | "
        f"{g_o['positive_windows']} | {g_o['total_pnl']} | {g_o['max_drawdown_max']} |\n\n"
        "## M5 rsi_reversal baseline との比較\n"
        "| timeframe | 期待値中央値 | PF中央値 | プラスwindow | 合計損益 | 最大DD最大 | 総取引 |\n"
        "|--|--:|--:|--:|--:|--:|--:|\n"
        f"| M15 | {summary['median_expectancy']} | {summary['median_pf']} | "
        f"{summary['positive_windows']} | {summary['total_pnl']} | "
        f"{summary['max_drawdown_max']} | {summary['total_trades']} |\n"
        f"| M5 | {m5['median_expectancy']} | {m5['median_pf']} | {m5['positive_windows']} | "
        f"{m5['total_pnl']} | {m5['max_drawdown_max']} | {m5['total_trades']} |\n\n"
        "## symbol別(15窓合算)\n"
        "| symbol | 完了 | 総損益 | 期待値 | PF | window勝敗 |\n|--|--:|--:|--:|--:|--|\n"
        + sym_rows + "\n\n"
        "## exit_reason別(15窓合算)\n"
        "| exit_reason | 件数 | 総損益 | 期待値 |\n|--|--:|--:|--:|\n" + rsn_rows + "\n\n"
        "## market-state別(DE三分位のみ・day-classはbreakout M15未実施のため省略)\n"
        "| market_state | 完了 | 総損益 | 期待値 | PF |\n|--|--:|--:|--:|--:|\n" + st_rows + "\n"
    )
    write_summary_markdown(out, text)


def _write_decision(out, summary, verdict, reasons) -> None:
    m5 = summary["m5_ref"]
    text = (
        "# rsi_reversal M15 最終判断\n\n"
        f"## 判定: {verdict}\n\n"
        "### 根拠\n" + "\n".join(f"- {r}" for r in reasons) + "\n\n"
        "### 集計\n"
        f"- 期待値中央値 {summary['median_expectancy']} / PF中央値 {summary['median_pf']} / "
        f"プラス窓 {summary['positive_windows']}/{summary['window_count']}\n"
        f"- 総取引 {summary['total_trades']}(M5={m5['total_trades']}) / "
        f"1取引期待値 {summary['per_trade_expectancy']}\n"
        f"- 合計損益 {summary['total_pnl']}(M5={m5['total_pnl']}) / "
        f"最大DD最大 {summary['max_drawdown_max']} / DD/損益 {summary['dd_to_pnl']}\n"
        f"- prior10 中央値 {summary['group_prior10']['median_expectancy']} / "
        f"oos5 中央値 {summary['group_oos5']['median_expectancy']}\n"
        f"- TP {summary['tp_total_pnl']} / SL {summary['sl_total_pnl']} / "
        f"反対 {summary['opp_total_pnl']}\n\n"
        "### 今後の扱い\n"
        "- 継続検証候補: M30/H1 や 他戦略M15 へ拡張する価値あり。\n"
        "- 研究用ベースライン: M15版ベースラインとして保存し、他戦略M15の比較基準にする。\n"
        "- 撤退: M15化でも改善せず。高時間足でも単純rsiは不可と判断。\n"
        "- SL/TP/RSIのM15向け調整は過剰最適化のため、まず素のM15で判断する。\n"
    )
    write_markdown(out / "rsi_m15_final_decision.md", text)


if __name__ == "__main__":
    raise SystemExit(main())
