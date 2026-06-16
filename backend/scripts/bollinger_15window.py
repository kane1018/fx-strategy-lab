"""15-window evaluation of Bollinger Band mean-reversion (read-only, paper).

Hypothesis: rsi_reversal's edge lives in low-DE (mean-reverting) regimes. Entering
on Bollinger band pierces (period 20, sigma 2.0) may capture those reversion moves
more adaptively than fixed RSI thresholds. Evaluated over the SAME 15 windows and
SAME fixed config (no tuning): M5, current_cost (spread 1.2 / slippage 0.2),
baseline exit, SL 30 / TP 60, continuous replay, no ADX/DE filter.

Exit choice: BASELINE exit (opposite-signal + SL/TP), identical to how rsi_reversal
and breakout were evaluated -> apples-to-apples entry comparison, zero harness
change. Center-line exit was NOT used (those metrics are reported as N/A).

Reuses the rsi/breakout/market-state pipelines. Also replays rsi + breakout per
day to attribute Bollinger results to market-state buckets (DE tertiles, day class).

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.bollinger_15window
"""

from __future__ import annotations

import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.brokers import GmoFxBroker  # noqa: E402
from app.models import PaperTrade  # noqa: E402
from app.schemas.trading import ExecutionConfig, StrategyConfig, StrategyType  # noqa: E402
from app.services.gmo_paper_service import replay_paper_trades  # noqa: E402
from app.services.market_data_service import candles_to_frame, pip_size  # noqa: E402
from scripts.breakout_15window import _TP, BK_STAT_FIELDS, _summarize_bk  # noqa: E402
from scripts.fx_eval_common import (  # noqa: E402
    ensure_output_dir,
    run_id,
    safety_metadata,
    validate_summary_schema,
    write_json,
    write_manifest,
    write_markdown,
    write_metrics_csv,
    write_summary_markdown,
    write_warnings,
)
from scripts.market_state_diagnostics import (  # noqa: E402
    _day_market_state,
    _fetch_candles,
    _replay_pnl_by_date,
    classify_day,
)
from scripts.robustness_windows import (  # noqa: E402
    _OPP,
    _SL,
    _exit_category,
    _mem,
    _weekdays,
    robustness_summary,
)
from scripts.rsi_final_15window import (  # noqa: E402
    SLIP,
    SPREAD,
    SYMBOLS,
    TIMEFRAME,
    WINDOWS,
    classify_strategy,
)

EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "analysis_exports"
BOLL_PERIOD, BOLL_SIGMA = 20, 2.0
DE_BUCKETS = ["low_de", "medium_de", "high_de"]
DAY_CLASSES = ["both_win", "rsi_only_win", "breakout_only_win", "both_lose"]

# Reference results from committed runs for side-by-side comparison.
RSI_REF = {"median_expectancy": 0.0164, "median_pf": 1.016, "positive_windows": 8,
           "total_pnl": 56.95, "max_drawdown_max": 65.46}
BK_REF = {"median_expectancy": -0.1123, "median_pf": 0.837, "positive_windows": 3,
          "total_pnl": -628.52, "max_drawdown_max": 124.66}


def de_bucket(de: float, lo_thr: float, hi_thr: float) -> str:
    if de < lo_thr:
        return "low_de"
    if de >= hi_thr:
        return "high_de"
    return "medium_de"


def de_thresholds(des: list[float]) -> tuple[float, float]:
    """Tertile cut points (descriptive bucketing, not a tuned trading threshold)."""
    if len(des) < 3:
        return 0.0, 1.0
    q = statistics.quantiles(des, n=3)
    return round(q[0], 4), round(q[1], 4)


def _replay_full_trades(candles, symbol, strategy, execution, fast) -> list[dict]:
    out: list[dict] = []
    with _mem() as db:
        res = replay_paper_trades(
            db, symbol=symbol, timeframe=TIMEFRAME, candles=candles, strategy=strategy,
            execution=execution, exit_policy="baseline", force_close_at_end=True,
            fast_signals=fast,
        )
        rows = db.scalars(select(PaperTrade).where(
            PaperTrade.session_id == res["session_id"],
            PaperTrade.status == "closed")).all()
        for t in rows:
            out.append({"date": t.opened_at.date().isoformat(), "pnl": float(t.realized_pnl),
                        "symbol": symbol, "closed_at": t.closed_at,
                        "exit_category": _exit_category(t.exit_reason or "")})
    return out


def _collect(broker: GmoFxBroker, warnings: list[str]) -> tuple[list[dict], dict]:
    boll = StrategyConfig(strategy_type=StrategyType.BOLLINGER_REVERSION)  # period20/sigma2
    rsi = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    bk = StrategyConfig(strategy_type=StrategyType.BREAKOUT)
    execution = ExecutionConfig(spread_pips=SPREAD, slippage_pips=SLIP)
    all_trades: list[dict] = []
    day_meta: dict[tuple[str, str], dict] = {}
    for label, start, end, group in WINDOWS:
        dates = _weekdays(start, end)
        for symbol in SYMBOLS:
            candles = _fetch_candles(broker, symbol, dates, warnings)
            if not candles:
                continue
            pip = pip_size(symbol)
            boll_trades = _replay_full_trades(candles, symbol, boll, execution, fast=False)
            rsi_by_date = _replay_pnl_by_date(candles, symbol, rsi, execution, fast=True)
            bk_by_date = _replay_pnl_by_date(candles, symbol, bk, execution, fast=False)
            frame = candles_to_frame(candles)
            frame["date"] = pd.to_datetime(frame["timestamp"]).dt.date.astype(str)
            for date, day_frame in frame.groupby("date"):
                rp, bp = rsi_by_date.get(date, []), bk_by_date.get(date, [])
                day_meta[(symbol, date)] = {
                    "de": _day_market_state(day_frame, pip)["direction_efficiency"],
                    "day_class": classify_day(sum(rp), sum(bp)) if rp and bp else "unclassified",
                }
            for t in boll_trades:
                all_trades.append({**t, "window": label, "group": group})
        done = sum(1 for t in all_trades if t["window"] == label)
        print(f"{label:>13} {start}-{end} [{group}] bollinger trades={done}")
    return all_trades, day_meta


def main() -> int:
    broker = GmoFxBroker()
    warnings: list[str] = []
    all_trades, day_meta = _collect(broker, warnings)
    _export(all_trades, day_meta, warnings)
    return 0


def _tag_market_state(all_trades: list[dict], day_meta: dict) -> tuple[float, float]:
    des = [m["de"] for m in day_meta.values() if m["day_class"] != "unclassified"]
    lo, hi = de_thresholds(des)
    for t in all_trades:
        meta = day_meta.get((t["symbol"], t["date"]), {"de": 0.0, "day_class": "unclassified"})
        t["de_bucket"] = de_bucket(meta["de"], lo, hi)
        t["day_class"] = meta["day_class"]
    return lo, hi


def _export(all_trades: list[dict], day_meta: dict, warnings: list[str]) -> None:
    rid = run_id("bollinger15")
    out = ensure_output_dir(EXPORT_ROOT / rid)
    lo, hi = _tag_market_state(all_trades, day_meta)

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
    for bucket in [*DE_BUCKETS, *DAY_CLASSES]:
        field = "de_bucket" if bucket in DE_BUCKETS else "day_class"
        sub = [t for t in all_trades if t.get(field) == bucket]
        by_state.append({"market_state": bucket, "stats": _summarize_bk(sub)})

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
    validate_summary_schema(summary)
    write_json(out / "metrics_bollinger_15window_summary.json", summary)

    write_warnings(out, {
        "data_source": "GMO Public API klines (BID), read-only",
        "fixed_config": f"bollinger(period {BOLL_PERIOD}, sigma {BOLL_SIGMA}) / {TIMEFRAME} / "
                        f"current_cost (spread {SPREAD}, slippage {SLIP}) / baseline exit / "
                        "SL30 / TP60 / no ADX/DE filter",
        "exit_choice": "BASELINE exit (opposite-signal + SL/TP); center-line exit NOT used (N/A)",
        "de_tertiles": {"low<": lo, "high>=": hi},
        "comparison_refs": "rsi=f716631, breakout=d1acdd6 (committed 15-window runs)",
        "note": "Bollinger 15-window evaluation; period/sigma fixed; no tuning.",
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
    summary.update({
        "total_pnl": round(sum(s["total_pnl"] for s in window_stats.values()), 2),
        "total_sl_count": sum(s["sl_count"] for s in window_stats.values()),
        "total_tp_count": sum(s["tp_count"] for s in window_stats.values()),
        "median_sl_ratio": round(statistics.median(sl_ratios), 4) if sl_ratios else 0.0,
        "tp_total_pnl": round(sum(t["pnl"] for t in all_trades if t["exit_category"] == _TP), 2),
        "sl_total_pnl": round(sum(t["pnl"] for t in all_trades if t["exit_category"] == _SL), 2),
        "opp_total_pnl": round(sum(t["pnl"] for t in all_trades if t["exit_category"] == _OPP), 2),
        "center_line_exit_count": 0,
        "center_line_exit_pnl": 0.0,
        "center_line_exit_note": "baseline exit採用のため該当なし(N/A)",
        "symbol_pnl": symbol_pnl, "symbol_expectancy": symbol_exp, "symbol_pf": symbol_pf,
        "symbol_window_win_loss": {s: f"{w[0]}-{w[1]}" for s, w in symbol_window_wl.items()},
        "symbol_concentrated": concentrated,
        "group_prior10": _grp(prior, "prior10"),
        "group_oos5": _grp(oos, "oos5"),
        "de_tertiles": {"low<": lo, "high>=": hi},
        "rsi_ref": RSI_REF, "breakout_ref": BK_REF,
    })
    return summary


def _write_manifest(out: Path, rid: str, win_group: dict) -> None:
    write_manifest(out, {
        "run_id": rid, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_bollinger15", "strategy": "bollinger_reversion",
        "bollinger_period": BOLL_PERIOD, "bollinger_sigma": BOLL_SIGMA,
        "timeframe": TIMEFRAME, "cost_scenario": "current_cost",
        "spread_pips": SPREAD, "slippage_pips": SLIP, "exit_policy": "baseline",
        "exit_choice": "baseline (opposite-signal + SL/TP); center-line exit not used",
        "stop_loss_pips": ExecutionConfig().stop_loss_pips,
        "take_profit_pips": ExecutionConfig().take_profit_pips,
        "adx_filter": False, "de_filter": False,
        "windows": [{"window": label, "group": g, "dates": _weekdays(s, e)}
                    for label, s, e, g in WINDOWS],
        "symbols": SYMBOLS, "continuous_replay": True,
        **safety_metadata(),
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
    g_p, g_o = summary["group_prior10"], summary["group_oos5"]
    rsi, bk = summary["rsi_ref"], summary["breakout_ref"]
    text = (
        "# Bollinger Band mean-reversion M5 15窓評価 (period20/sigma2.0・baseline exit)\n\n"
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "rsi/breakoutと同一15窓・同一固定条件。center-line exitは不使用(baseline採用)。\n\n"
        "## window別\n" + win_h + win_rows + "\n\n"
        "## 15窓全体集計\n"
        f"- 期待値中央値: {summary['median_expectancy']} / PF中央値: {summary['median_pf']}\n"
        f"- プラスwindow: {summary['positive_windows']} / マイナス: {summary['negative_windows']}"
        f" / edge(exp>0&PF>1): {summary['edge_windows']}\n"
        f"- 完了≥30のwindow: {summary['windows_ge30_trades']}/{summary['window_count']} / "
        f"合計損益: {summary['total_pnl']} / 最大DD最大: {summary['max_drawdown_max']}\n"
        f"- 合計SL: {summary['total_sl_count']} / 合計TP: {summary['total_tp_count']} / "
        f"SL率中央: {summary['median_sl_ratio']}\n"
        f"- TP損益: {summary['tp_total_pnl']} / SL損益: {summary['sl_total_pnl']} / "
        f"反対損益: {summary['opp_total_pnl']} / center-line exit: "
        f"{summary['center_line_exit_note']}\n"
        f"- 単一ペア偏重: {summary['symbol_concentrated']} / DE三分位 "
        f"low<{summary['de_tertiles']['low<']} high>={summary['de_tertiles']['high>=']}\n\n"
        "## prior10 vs oos5\n"
        "| group | window数 | 期待値中央値 | PF中央値 | プラスwindow | 合計損益 | 最大DD最大 |\n"
        "|--|--:|--:|--:|--:|--:|--:|\n"
        f"| prior10 | {g_p['window_count']} | {g_p['median_expectancy']} | {g_p['median_pf']} | "
        f"{g_p['positive_windows']} | {g_p['total_pnl']} | {g_p['max_drawdown_max']} |\n"
        f"| oos5 | {g_o['window_count']} | {g_o['median_expectancy']} | {g_o['median_pf']} | "
        f"{g_o['positive_windows']} | {g_o['total_pnl']} | {g_o['max_drawdown_max']} |\n\n"
        "## 戦略比較\n"
        "| strategy | 期待値中央値 | PF中央値 | プラスwindow | 合計損益 | 最大DD最大 |\n"
        "|--|--:|--:|--:|--:|--:|\n"
        f"| bollinger | {summary['median_expectancy']} | {summary['median_pf']} | "
        f"{summary['positive_windows']} | {summary['total_pnl']} | "
        f"{summary['max_drawdown_max']} |\n"
        f"| rsi_reversal | {rsi['median_expectancy']} | {rsi['median_pf']} | "
        f"{rsi['positive_windows']} | {rsi['total_pnl']} | {rsi['max_drawdown_max']} |\n"
        f"| breakout | {bk['median_expectancy']} | {bk['median_pf']} | "
        f"{bk['positive_windows']} | {bk['total_pnl']} | {bk['max_drawdown_max']} |\n\n"
        "## symbol別(15窓合算)\n"
        "| symbol | 完了 | 総損益 | 期待値 | PF | window勝敗 |\n|--|--:|--:|--:|--:|--|\n"
        + sym_rows + "\n\n"
        "## exit_reason別(15窓合算)\n"
        "| exit_reason | 件数 | 総損益 | 期待値 |\n|--|--:|--:|--:|\n" + rsn_rows + "\n\n"
        "## market-state別(Bollinger損益)\n"
        "| market_state | 完了 | 総損益 | 期待値 | PF |\n|--|--:|--:|--:|--:|\n" + st_rows + "\n"
    )
    write_summary_markdown(out, text)


def _write_decision(out, summary, verdict, reasons) -> None:
    rsi = summary["rsi_ref"]
    text = (
        "# Bollinger Band mean-reversion M5 最終判断\n\n"
        f"## 判定: {verdict}\n\n"
        "### 根拠\n" + "\n".join(f"- {r}" for r in reasons) + "\n\n"
        "### 集計\n"
        f"- 期待値中央値 {summary['median_expectancy']} / PF中央値 {summary['median_pf']} / "
        f"プラス窓 {summary['positive_windows']}/{summary['window_count']}\n"
        f"- 合計損益 {summary['total_pnl']} / 最大DD最大 {summary['max_drawdown_max']}\n"
        f"- prior10 中央値 {summary['group_prior10']['median_expectancy']} / "
        f"oos5 中央値 {summary['group_oos5']['median_expectancy']}\n"
        f"- TP {summary['tp_total_pnl']} / SL {summary['sl_total_pnl']} / "
        f"反対 {summary['opp_total_pnl']}（center-line exitは不使用）\n"
        f"- rsi比: bollinger 中央値 {summary['median_expectancy']} vs rsi "
        f"{rsi['median_expectancy']}、合計 {summary['total_pnl']} vs {rsi['total_pnl']}\n\n"
        "### 今後の扱い\n"
        "- 継続検証候補: 主検証として残す。\n"
        "- 研究用ベースライン: 構造はあるが実用性は低い。比較用に残す。\n"
        "- 撤退: 主検証から外し別アプローチへ。period/sigma/SL/TPの追加調整はしない。\n"
    )
    write_markdown(out / "bollinger_final_decision.md", text)


if __name__ == "__main__":
    raise SystemExit(main())
