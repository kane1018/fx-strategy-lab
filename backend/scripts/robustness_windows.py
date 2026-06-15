"""Final multi-window robustness check for rsi_reversal (read-only, paper).

FIXED conditions (no tuning): rsi_reversal, M5, current_cost (spread 1.2 /
slippage 0.2), baseline exit, SL 30 / TP 60, continuous replay. Replays the same
config across several INDEPENDENT past weeks to decide whether the one IS-positive
M5 result reproduces, or rsi_reversal (default) should be retired from the main
investigation.

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.robustness_windows
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from datetime import datetime, timedelta
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
from app.services.performance_service import _trade_stats  # noqa: E402

EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "analysis_exports"
SYMBOLS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY"]
# FIXED config (M5 current_cost baseline SL30/TP60)
TIMEFRAME = "M5"
SPREAD, SLIP = ExecutionConfig().spread_pips, ExecutionConfig().slippage_pips
# (label, start, end) — independent weeks NOT overlapping prior IS/OOS (06-01..06-12, 05-18..05-29)
WINDOWS = [
    ("window_1", "20260504", "20260515"),
    ("window_2", "20260420", "20260501"),
    ("window_3", "20260406", "20260417"),
    ("window_4", "20260323", "20260403"),
    ("window_5", "20260309", "20260320"),
]
_FORCED = "データ終了強制クローズ"
_SL = "損切り到達(SL)"
_OPP = "反対シグナル"
_STAT_FIELDS = [
    "completed_trades", "win_rate", "total_pnl", "expectancy", "profit_factor",
    "max_drawdown", "max_loss", "max_consecutive_losses", "sl_count", "sl_ratio",
    "opp_count", "opp_total_pnl", "forced_close_count", "forced_close_ratio", "reference_only",
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


def _weekdays(start: str, end: str) -> list[str]:
    s = datetime.strptime(start, "%Y%m%d").date()
    e = datetime.strptime(end, "%Y%m%d").date()
    out, d = [], s
    while d <= e:
        if d.weekday() < 5:
            out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out


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
    return {
        **{k: stats[k] for k in ["completed_trades", "win_rate", "total_pnl", "expectancy",
                                 "profit_factor", "max_drawdown", "max_loss", "reference_only"]},
        "max_consecutive_losses": mcl,
        "sl_count": len(sl),
        "sl_ratio": round(len(sl) / n, 4) if n else 0.0,
        "opp_count": len(opp),
        "opp_total_pnl": round(sum(t["pnl"] for t in opp), 2),
        "forced_close_count": len(forced),
        "forced_close_ratio": round(len(forced) / n, 4) if n else 0.0,
    }


def robustness_summary(window_stats: dict[str, dict]) -> dict:
    """Aggregate per-window stats into a robustness verdict (pure / testable)."""
    rows = list(window_stats.values())
    exps = [r["expectancy"] for r in rows]
    pfs = [r["profit_factor"] or 0.0 for r in rows]
    n = len(rows)
    return {
        "window_count": n,
        "median_expectancy": round(statistics.median(exps), 4) if rows else 0.0,
        "median_pf": round(statistics.median(pfs), 4) if rows else 0.0,
        "positive_windows": sum(1 for e in exps if e > 0),
        "negative_windows": sum(1 for e in exps if e <= 0),
        "edge_windows": sum(
            1 for r in rows if r["expectancy"] > 0 and (r["profit_factor"] or 0) > 1
        ),
        "windows_ge30_trades": sum(1 for r in rows if r["completed_trades"] >= 30),
        "max_drawdown_max": round(max((r["max_drawdown"] for r in rows), default=0.0), 2),
        "worst_single_loss": round(min((r["max_loss"] for r in rows), default=0.0), 4),
    }


def _decision(summary: dict, n_windows: int, symbol_concentrated: bool) -> tuple[str, list[str]]:
    reasons: list[str] = []
    majority = n_windows / 2
    keep = (
        summary["positive_windows"] > majority
        and summary["edge_windows"] > majority
        and summary["median_expectancy"] > 0
        and summary["windows_ge30_trades"] == n_windows
        and not symbol_concentrated
    )
    if summary["median_expectancy"] <= 0:
        reasons.append(f"期待値中央値 {summary['median_expectancy']} ≤ 0")
    if summary["median_pf"] < 1:
        reasons.append(f"PF中央値 {summary['median_pf']} < 1")
    if summary["positive_windows"] <= majority:
        reasons.append(f"プラスwindow {summary['positive_windows']}/{n_windows} が過半未満")
    if summary["windows_ge30_trades"] < n_windows:
        reasons.append("一部windowで完了取引<30件（参考値）")
    if symbol_concentrated:
        reasons.append("利益が単一通貨ペアに偏重")
    verdict = "継続検証候補（撤退撤回）" if keep else "撤退確定"
    if not reasons:
        reasons.append("全採用条件を満たす")
    return verdict, reasons


def main() -> int:
    strategy = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    execution = ExecutionConfig(spread_pips=SPREAD, slippage_pips=SLIP)  # current_cost, SL30/TP60
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
        s = _summarize(trades)
        print(f"{label} {start}-{end} n={s['completed_trades']:>4} exp={s['expectancy']:>8} "
              f"PF={s['profit_factor']} maxDD={s['max_drawdown']} maxLoss={s['max_loss']}")

    _export(results, window_dates, warnings)
    return 0


def _write_csv(path: Path, rows: list[dict], keys: list[str]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([*keys, *_STAT_FIELDS])
        for r in rows:
            w.writerow([*[r[k] for k in keys], *[r["stats"][f] for f in _STAT_FIELDS]])


def _export(results: dict, window_dates: dict, warnings: list[str]) -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gmo_public_paper_rsi_robustness"
    out = EXPORT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    window_stats = {label: _summarize(tr) for label, tr in results.items()}
    by_window = [{"window": label, "period": f"{window_dates[label][0]}..{window_dates[label][-1]}",
                  "stats": st} for label, st in window_stats.items()]
    by_ws, by_reason, by_date = [], [], []
    symbol_pnl: dict[str, float] = {s: 0.0 for s in SYMBOLS}
    symbol_trades: dict[str, list[dict]] = {s: [] for s in SYMBOLS}
    for label, tr in results.items():
        for sym in SYMBOLS:
            sub = [t for t in tr if t["symbol"] == sym]
            if sub:
                by_ws.append({"window": label, "symbol": sym, "stats": _summarize(sub)})
                symbol_pnl[sym] += sum(t["pnl"] for t in sub)
                symbol_trades[sym].extend(sub)
        for reason in sorted({t["exit_category"] for t in tr}):
            sub = [t for t in tr if t["exit_category"] == reason]
            by_reason.append({"window": label, "exit_reason": reason, "stats": _summarize(sub)})
        for d in sorted({t["date"] for t in tr}):
            sub = [t for t in tr if t["date"] == d]
            by_date.append({"window": label, "date": d, "stats": _summarize(sub)})

    _write_csv(out / "metrics_by_window.csv",
               [{"window": r["window"], "period": r["period"], "stats": r["stats"]}
                for r in by_window], ["window", "period"])
    _write_csv(out / "metrics_by_window_symbol.csv", by_ws, ["window", "symbol"])
    _write_csv(out / "metrics_by_exit_reason.csv", by_reason, ["window", "exit_reason"])
    _write_csv(out / "metrics_by_date.csv", by_date, ["window", "date"])

    summary = robustness_summary(window_stats)
    total_pnl = sum(symbol_pnl.values())
    pos_pnl = sum(v for v in symbol_pnl.values() if v > 0)
    top_symbol = max(symbol_pnl, key=lambda s: symbol_pnl[s])
    # concentration: a single symbol provides >60% of all positive symbol-pnl
    symbol_concentrated = bool(pos_pnl > 0 and max(
        (v for v in symbol_pnl.values() if v > 0), default=0) / pos_pnl > 0.6)
    summary["symbol_pnl"] = {s: round(v, 2) for s, v in symbol_pnl.items()}
    summary["symbol_concentrated"] = symbol_concentrated
    summary["total_pnl"] = round(total_pnl, 2)
    (out / "metrics_robustness_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2))

    verdict, reasons = _decision(summary, len(results), symbol_concentrated)
    (out / "warnings.json").write_text(json.dumps({
        "data_source": "GMO Public API klines (BID), read-only",
        "fixed_config": f"rsi_reversal / {TIMEFRAME} / current_cost (spread {SPREAD}, "
                        f"slippage {SLIP}) / baseline exit / SL30 / TP60",
        "windows": {label: window_dates[label] for label in results},
        "note": "final retirement check; no parameter tuning. Public klines single-price.",
        "fetch_warnings": warnings,
    }, ensure_ascii=False, indent=2))
    _write_manifest(out, run_id, window_dates)
    _write_summary(out, by_window, summary)
    _write_decision(out, summary, verdict, reasons, top_symbol)
    print(f"\n{verdict}: {reasons}")
    print(f"Export written to: analysis_exports/{run_id}/")


def _write_manifest(out: Path, run_id: str, window_dates: dict) -> None:
    (out / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_rsi_robustness", "strategy": "rsi_reversal",
        "timeframe": TIMEFRAME, "cost_scenario": "current_cost",
        "spread_pips": SPREAD, "slippage_pips": SLIP, "exit_policy": "baseline",
        "stop_loss_pips": ExecutionConfig().stop_loss_pips,
        "take_profit_pips": ExecutionConfig().take_profit_pips,
        "windows": [{"window": label, "dates": dates} for label, dates in window_dates.items()],
        "symbols": SYMBOLS, "continuous_replay": True, "no_order_execution": True,
        "gmo_readonly": True, "gmo_order_enabled": False,
    }, ensure_ascii=False, indent=2))


def _write_summary(out: Path, by_window: list[dict], summary: dict) -> None:
    head = ("| window | 期間 | 完了 | 勝率 | 総損益 | 期待値 | PF | 最大DD | 最大単発損失 |\n"
            "|--|--|--:|--:|--:|--:|--:|--:|--:|\n")
    rows = []
    for r in by_window:
        s = r["stats"]
        rows.append(f"| {r['window']} | {r['period']} | {s['completed_trades']} | "
                    f"{s['win_rate']}% | {s['total_pnl']} | {s['expectancy']} | "
                    f"{s['profit_factor']} | {s['max_drawdown']} | {s['max_loss']} |")
    text = (
        "# rsi_reversal 最終ロバスト性確認 (M5 / current_cost / 固定条件)\n\n"
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "独立した複数週で同一固定条件を再集計（パラメータ調整なし）。\n\n"
        "## window別\n" + head + "\n".join(rows) + "\n\n"
        f"## 全window集計\n"
        f"- 期待値中央値: {summary['median_expectancy']}\n"
        f"- PF中央値: {summary['median_pf']}\n"
        f"- プラスwindow: {summary['positive_windows']} / マイナス: {summary['negative_windows']}\n"
        f"- 期待値>0かつPF>1のwindow: {summary['edge_windows']}\n"
        f"- 完了取引≥30のwindow: {summary['windows_ge30_trades']} / {summary['window_count']}\n"
        f"- 最大DD(最大): {summary['max_drawdown_max']}\n"
        f"- 最悪単発損失: {summary['worst_single_loss']}\n"
        f"- symbol別損益: {summary['symbol_pnl']}\n"
        f"- 単一ペア偏重: {summary['symbol_concentrated']}\n"
    )
    (out / "summary.md").write_text(text)


def _write_decision(out: Path, summary: dict, verdict: str, reasons: list[str],
                    top_symbol: str) -> None:
    text = (
        "# rsi_reversal 撤退判断\n\n"
        f"## 判定: {verdict}\n\n"
        "### 根拠\n" + "\n".join(f"- {r}" for r in reasons) + "\n\n"
        f"### 集計\n"
        f"- 期待値中央値 {summary['median_expectancy']} / PF中央値 {summary['median_pf']}\n"
        f"- プラスwindow {summary['positive_windows']}/{summary['window_count']}・"
        f"edge(exp>0&PF>1) {summary['edge_windows']}/{summary['window_count']}\n"
        f"- symbol別損益 {summary['symbol_pnl']}（最大寄与 {top_symbol}・偏重 "
        f"{summary['symbol_concentrated']}）\n\n"
        "### 今後の扱い\n"
        "- 撤退確定の場合: rsi_reversal(既定)は主検証から外し、別戦略/別アプローチへ。\n"
        "- RSIパラメータ・SL/TP・フィルター等のさらなる調整は過剰最適化のため行わない。\n"
    )
    (out / "rsi_reversal_retirement_decision.md").write_text(text)


if __name__ == "__main__":
    raise SystemExit(main())
