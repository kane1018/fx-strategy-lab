"""Stop-loss distance A/B for rsi_reversal (continuous replay, paper, read-only).

Holds entry/RSI/TP fixed and varies ONLY stop_loss_pips (15/20/30/40) on the
continuous (cross-day) harness. Tests whether a tighter SL caps the large-SL-hit
tail that drives rsi_reversal's loss. baseline = 30 pips.

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.stop_loss_ab
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
STOP_LOSS_PIPS = [15, 20, 30, 40]  # 30 = baseline
BASELINE_SL = 30
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
    "profit_factor", "max_drawdown", "max_loss", "max_consecutive_losses",
    "sl_count", "sl_ratio", "sl_total_pnl", "sl_avg_loss",
    "opp_count", "opp_total_pnl", "opp_expectancy",
    "forced_close_count", "forced_close_ratio", "reference_only",
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
    return {
        **{k: stats[k] for k in ["completed_trades", "win_rate", "total_pnl", "avg_win",
                                 "avg_loss", "expectancy", "profit_factor", "max_drawdown",
                                 "max_loss", "reference_only"]},
        "max_consecutive_losses": mcl,
        "sl_count": len(sl),
        "sl_ratio": round(len(sl) / n, 4) if n else 0.0,
        "sl_total_pnl": round(sum(t["pnl"] for t in sl), 2),
        "sl_avg_loss": round(sum(t["pnl"] for t in sl) / len(sl), 4) if sl else 0.0,
        "opp_count": len(opp),
        "opp_total_pnl": round(sum(t["pnl"] for t in opp), 2),
        "opp_expectancy": round(sum(t["pnl"] for t in opp) / len(opp), 4) if opp else 0.0,
        "forced_close_count": len(forced),
        "forced_close_ratio": round(len(forced) / n, 4) if n else 0.0,
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

    series: dict[tuple[str, str], pd.DataFrame] = {}
    for period, dates in PERIODS.items():
        for symbol in SYMBOLS:
            chunks = []
            for date in dates:
                try:
                    chunks.append(candles_to_frame(broker.candles(symbol, "M1", 1500, date=date)))
                except GmoFxBrokerError as error:
                    warnings.append(f"fetch failed {symbol} {date}: {error}")
                time.sleep(0.2)
            if chunks:
                merged = pd.concat(chunks, ignore_index=True)
                merged = merged.sort_values("timestamp").drop_duplicates("timestamp")
                series[(symbol, period)] = merged.reset_index(drop=True)
    print(f"continuous series built: {len(series)}")

    results: dict[tuple[int, str], list[dict]] = {}
    for sl in STOP_LOSS_PIPS:
        execution = ExecutionConfig(stop_loss_pips=sl)  # TP / RSI / entry unchanged
        for period in PERIODS:
            trades: list[dict] = []
            for symbol in SYMBOLS:
                frame = series.get((symbol, period))
                if frame is None or len(frame) < 3:
                    continue
                with _mem() as db:
                    res = replay_paper_trades(
                        db, symbol=symbol, timeframe="M1",
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
                            "holding_bucket": holding_bucket(held),
                            "exit_category": _exit_category(t.exit_reason or ""),
                        })
            results[(sl, period)] = trades
            s = _summarize(trades)
            print(f"SL={sl:>2} {period:<4} n={s['completed_trades']:>4} exp={s['expectancy']:>8} "
                  f"PF={s['profit_factor']} maxDD={s['max_drawdown']} maxLoss={s['max_loss']} "
                  f"SL件数={s['sl_count']}({s['sl_ratio']})")

    _export(results, warnings)
    return 0


def _export(results: dict, warnings: list[str]) -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gmo_public_paper_stop_loss_ab"
    out = EXPORT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    by_sp = [{"stop_loss_pips": sl, "period": per, "stats": _summarize(tr)}
             for (sl, per), tr in results.items()]
    by_ss = []
    for (sl, per), tr in results.items():
        for sym in SYMBOLS:
            sub = [t for t in tr if t["symbol"] == sym]
            if sub:
                by_ss.append({"stop_loss_pips": sl, "period": per, "symbol": sym,
                              "stats": _summarize(sub)})
    by_reason = []
    for (sl, per), tr in results.items():
        for reason in sorted({t["exit_category"] for t in tr}):
            sub = [t for t in tr if t["exit_category"] == reason]
            by_reason.append({"stop_loss_pips": sl, "period": per, "exit_reason": reason,
                              "stats": _summarize(sub)})
    by_hold = []
    for sl in STOP_LOSS_PIPS:
        merged = results[(sl, "IS")] + results[(sl, "OOS")]
        for b in ["<5min", "5-15min", "15-30min", "30-60min", "60min+"]:
            sub = [t for t in merged if t["holding_bucket"] == b]
            if sub:
                by_hold.append(
                    {"stop_loss_pips": sl, "holding_time_bucket": b, "stats": _summarize(sub)}
                )
    by_date = []
    for (sl, per), tr in results.items():
        for d in sorted({t["date"] for t in tr}):
            sub = [t for t in tr if t["date"] == d]
            by_date.append({"stop_loss_pips": sl, "period": per, "date": d,
                            "stats": _summarize(sub)})

    _write_csv(out / "metrics_by_stop_loss_period.csv", by_sp, ["stop_loss_pips", "period"])
    _write_csv(out / "metrics_by_stop_loss_symbol.csv", by_ss,
               ["stop_loss_pips", "period", "symbol"])
    _write_csv(out / "metrics_by_exit_reason.csv", by_reason,
               ["stop_loss_pips", "period", "exit_reason"])
    _write_csv(out / "metrics_by_holding_time.csv", by_hold,
               ["stop_loss_pips", "holding_time_bucket"])
    _write_csv(out / "metrics_by_date.csv", by_date, ["stop_loss_pips", "period", "date"])
    (out / "metrics_overall.json").write_text(json.dumps(
        {f"SL{sl}|{per}": _summarize(tr) for (sl, per), tr in results.items()},
        ensure_ascii=False, indent=2))
    (out / "metrics_drawdown_streaks.json").write_text(json.dumps(
        {f"SL{sl}|{per}": {"max_consecutive_losses": _summarize(tr)["max_consecutive_losses"],
                           "max_single_loss": _summarize(tr)["max_loss"]}
         for (sl, per), tr in results.items()}, ensure_ascii=False, indent=2))
    (out / "warnings.json").write_text(json.dumps({
        "data_source": "GMO Public API klines (BID), read-only",
        "strategy": "rsi_reversal, exit_policy=baseline, only stop_loss_pips varied",
        "fixed": "RSI params, take_profit_pips, entry, time/ADX filters unchanged",
        "harness": "continuous (cross-day); force-close only at period end",
        "no_real_spread": "Public klines are single-price; spread is a fixed estimate.",
        "fetch_warnings": warnings,
    }, ensure_ascii=False, indent=2))
    (out / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_stop_loss_ab", "strategy": "rsi_reversal",
        "exit_policy": "baseline", "stop_loss_pips": STOP_LOSS_PIPS, "baseline_sl": BASELINE_SL,
        "take_profit_pips": ExecutionConfig().take_profit_pips,
        "periods": PERIODS, "symbols": SYMBOLS, "interval": "1min", "continuous_replay": True,
        "no_order_execution": True, "gmo_readonly": True, "gmo_order_enabled": False,
    }, ensure_ascii=False, indent=2))
    _write_summary(out, results)
    _write_candidates(out, results)
    print(f"\nExport written to: analysis_exports/{run_id}/")


def _md(rows: list[dict]) -> str:
    cols = ["SLpips", "完了", "勝率", "総損益", "期待値", "PF", "最大DD", "最大単発損失",
            "SL件数", "SL率", "max連敗"]
    head = "| " + " | ".join(cols) + " |\n|" + "--|" * len(cols) + "\n"
    lines = []
    for r in rows:
        s = r["stats"]
        lines.append("| " + " | ".join([
            str(r["stop_loss_pips"]), str(s["completed_trades"]), f"{s['win_rate']}%",
            str(s["total_pnl"]), str(s["expectancy"]), str(s["profit_factor"]),
            str(s["max_drawdown"]), str(s["max_loss"]), str(s["sl_count"]),
            str(s["sl_ratio"]), str(s["max_consecutive_losses"])]) + " |")
    return head + "\n".join(lines)


def _write_summary(out: Path, results: dict) -> None:
    is_rows = [{"stop_loss_pips": sl, "stats": _summarize(results[(sl, "IS")])}
               for sl in STOP_LOSS_PIPS]
    oos_rows = [{"stop_loss_pips": sl, "stats": _summarize(results[(sl, "OOS")])}
                for sl in STOP_LOSS_PIPS]
    text = (
        "# stop_loss_pips A/B (rsi_reversal, baseline exit, continuous, read-only)\n\n"
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "stop_loss_pips のみ変更（RSI/TP/entry不変）。baseline=30pips。\n\n"
        "## IS (2026-06-01〜06-12)\n" + _md(is_rows) + "\n\n"
        "## OOS (2026-05-18〜05-29)\n" + _md(oos_rows) + "\n"
    )
    (out / "summary.md").write_text(text)


def _write_candidates(out: Path, results: dict) -> None:
    def improves(sl: int) -> bool:
        for per in ("IS", "OOS"):
            b = _summarize(results[(BASELINE_SL, per)])
            p = _summarize(results[(sl, per)])
            if not (p["expectancy"] > b["expectancy"]
                    and (p["profit_factor"] or 0) > (b["profit_factor"] or 0)
                    and p["max_drawdown"] <= b["max_drawdown"]
                    and p["max_loss"] >= b["max_loss"]
                    and p["completed_trades"] >= 30):
                return False
        return True
    lines = ["# stop_loss_pips 候補（検証のみ・実戦略未組込）\n",
             "| SLpips | IS/OOS両方でbaseline30改善(期待値↑/PF↑/DD↓/単発損失↓/≥30)? | 判定 |",
             "|--:|--|--|"]
    for sl in STOP_LOSS_PIPS:
        if sl == BASELINE_SL:
            continue
        good = improves(sl)
        lines.append(f"| {sl} | {'Yes' if good else 'No'} | "
                     f"{'継続検証で有望' if good else '却下/判断保留'} |")
    (out / "stop_loss_candidates.md").write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
