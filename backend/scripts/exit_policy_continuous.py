"""Continuous-replay exit-policy A/B for rsi_reversal (paper, read-only).

Unlike scripts.exit_policy_ab (which replays each symbol/date separately and
force-closes at every day boundary), this concatenates each symbol's klines over
the whole period into ONE continuous series, so positions can be held across day
boundaries and are force-closed ONLY at the end of the period. That removes the
per-date force-close distortion. RSI signals are precomputed exactly (vectorized)
so the long continuous replay stays fast.

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.exit_policy_continuous
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
from app.schemas.trading import ExecutionConfig, StrategyConfig, StrategyType  # noqa: E402
from app.services.gmo_paper_service import replay_paper_trades  # noqa: E402
from app.services.market_data_service import candles_to_frame  # noqa: E402
from app.services.paper_analysis_service import holding_bucket, holding_minutes  # noqa: E402
from app.services.performance_service import _trade_stats  # noqa: E402

EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "analysis_exports"
SYMBOLS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY"]
POLICIES = ["baseline", "time_stop_30m", "time_stop_60m", "no_opposite_signal_exit"]
PERIODS = {
    "IS": ["20260601", "20260602", "20260603", "20260604", "20260605",
           "20260608", "20260609", "20260610", "20260611", "20260612"],
    "OOS": ["20260518", "20260519", "20260520", "20260521", "20260522",
            "20260525", "20260526", "20260527", "20260528", "20260529"],
}
_FORCED = "データ終了強制クローズ"


def _exit_category(reason: str) -> str:
    if "損切り" in reason:
        return "損切り到達(SL)"
    if "利確" in reason:
        return "利確到達(TP)"
    if "反対シグナル" in reason:
        return "反対シグナル"
    if "時間ストップ" in reason:
        return reason  # 時間ストップ30分 / 60分
    if "データ終了" in reason:
        return _FORCED
    return reason or "unknown"
_STAT_FIELDS = [
    "completed_trades", "win_rate", "total_pnl", "avg_win", "avg_loss", "expectancy",
    "profit_factor", "max_drawdown", "max_loss", "max_consecutive_losses",
    "forced_close_count", "forced_close_ratio", "reference_only",
]


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
    forced = sum(1 for t in trades if t["exit_reason"] == _FORCED)
    n = stats["completed_trades"]
    return {
        **{k: stats[k] for k in ["completed_trades", "win_rate", "total_pnl", "avg_win",
                                 "avg_loss", "expectancy", "profit_factor", "max_drawdown",
                                 "max_loss", "reference_only"]},
        "max_consecutive_losses": mcl,
        "forced_close_count": forced,
        "forced_close_ratio": round(forced / n, 4) if n else 0.0,
    }


def _write_csv(path: Path, rows: list[dict], keys: list[str]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([*keys, *_STAT_FIELDS])
        for r in rows:
            w.writerow([*[r[k] for k in keys], *[r["stats"][f] for f in _STAT_FIELDS]])


def main() -> int:
    strategy = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    execution = ExecutionConfig()
    broker = GmoFxBroker()
    warnings: list[str] = []

    # Concatenate each symbol's klines into one continuous series per period.
    series: dict[tuple[str, str], list] = {}
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

    results: dict[tuple[str, str], list[dict]] = {}
    for policy in POLICIES:
        for period in PERIODS:
            trades: list[dict] = []
            for symbol in SYMBOLS:
                frame = series.get((symbol, period))
                if frame is None or len(frame) < 3:
                    continue
                candles = list(_frame_to_candles(frame))
                with _mem() as db:
                    res = replay_paper_trades(
                        db, symbol=symbol, timeframe="M1", candles=candles,
                        strategy=strategy, execution=execution, exit_policy=policy,
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
                            "exit_reason": t.exit_reason or "",
                            "exit_category": _exit_category(t.exit_reason or ""),
                        })
            results[(policy, period)] = trades
            s = _summarize(trades)
            print(f"{policy:<26}{period:<4} n={s['completed_trades']:>4} "
                  f"exp={s['expectancy']:>8} PF={s['profit_factor']} maxDD={s['max_drawdown']} "
                  f"maxLoss={s['max_loss']} forced%={s['forced_close_ratio']}")

    _export(results, warnings)
    return 0


def _frame_to_candles(frame: pd.DataFrame):
    from app.schemas.trading import Candle
    for _, row in frame.iterrows():
        yield Candle(timestamp=pd.Timestamp(row["timestamp"]).to_pydatetime(),
                     open=float(row["open"]), high=float(row["high"]), low=float(row["low"]),
                     close=float(row["close"]), volume=0)


def _export(results: dict, warnings: list[str]) -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gmo_public_paper_exit_policy_continuous"
    out = EXPORT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    by_pp = [{"exit_policy": p, "period": per, "stats": _summarize(tr)}
             for (p, per), tr in results.items()]
    by_ps = []
    for (p, per), tr in results.items():
        for sym in SYMBOLS:
            sub = [t for t in tr if t["symbol"] == sym]
            if sub:
                by_ps.append({"exit_policy": p, "period": per, "symbol": sym,
                              "stats": _summarize(sub)})
    by_reason = []
    for (p, per), tr in results.items():
        reasons = sorted({t["exit_category"] for t in tr})
        for reason in reasons:
            sub = [t for t in tr if t["exit_category"] == reason]
            by_reason.append({"exit_policy": p, "period": per, "exit_reason": reason,
                              "stats": _summarize(sub)})
    by_hold = []
    for p in POLICIES:
        merged = results[(p, "IS")] + results[(p, "OOS")]
        for b in ["<5min", "5-15min", "15-30min", "30-60min", "60min+"]:
            sub = [t for t in merged if t["holding_bucket"] == b]
            if sub:
                by_hold.append(
                    {"exit_policy": p, "holding_time_bucket": b, "stats": _summarize(sub)}
                )
    by_date = []
    for (p, per), tr in results.items():
        for d in sorted({t["date"] for t in tr}):
            sub = [t for t in tr if t["date"] == d]
            by_date.append({"exit_policy": p, "period": per, "date": d, "stats": _summarize(sub)})

    _write_csv(out / "metrics_by_exit_policy_period.csv", by_pp, ["exit_policy", "period"])
    _write_csv(out / "metrics_by_exit_policy_symbol.csv", by_ps,
               ["exit_policy", "period", "symbol"])
    _write_csv(out / "metrics_by_exit_reason.csv", by_reason,
               ["exit_policy", "period", "exit_reason"])
    _write_csv(out / "metrics_by_holding_time.csv", by_hold, ["exit_policy", "holding_time_bucket"])
    _write_csv(out / "metrics_by_date.csv", by_date, ["exit_policy", "period", "date"])
    (out / "metrics_overall.json").write_text(json.dumps(
        {f"{p}|{per}": _summarize(tr) for (p, per), tr in results.items()},
        ensure_ascii=False, indent=2))
    (out / "metrics_drawdown_streaks.json").write_text(json.dumps(
        {f"{p}|{per}": {"max_consecutive_losses": _summarize(tr)["max_consecutive_losses"],
                        "max_single_loss": _summarize(tr)["max_loss"]}
         for (p, per), tr in results.items()}, ensure_ascii=False, indent=2))
    (out / "warnings.json").write_text(json.dumps({
        "data_source": "GMO Public API klines (BID), read-only",
        "strategy": "rsi_reversal only",
        "harness": "continuous: per-symbol klines concatenated over the period; positions can "
                   "span day boundaries; force-close ONLY at period end.",
        "force_close_at_end": "applied to all policies; forced_close_ratio reports its share.",
        "rsi_signals": "precomputed vectorized (exact match to per-bar path; verified by test).",
        "no_real_spread": "Public klines are single-price; spread is a fixed estimate.",
        "fetch_warnings": warnings,
    }, ensure_ascii=False, indent=2))
    (out / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_exit_policy_continuous", "strategy": "rsi_reversal",
        "exit_policies": POLICIES, "periods": PERIODS, "symbols": SYMBOLS, "interval": "1min",
        "continuous_replay": True, "force_close_at_end": True,
        "no_order_execution": True, "gmo_readonly": True, "gmo_order_enabled": False,
    }, ensure_ascii=False, indent=2))
    _write_summary(out, results)
    _write_candidates(out, results)
    print(f"\nExport written to: analysis_exports/{run_id}/")


def _md(rows: list[dict], keys: list[str]) -> str:
    cols = [*keys, "完了", "勝率", "総損益", "期待値", "PF", "最大DD", "最大単発損失",
            "max連敗", "forced%"]
    head = "| " + " | ".join(cols) + " |\n|" + "--|" * len(cols) + "\n"
    lines = []
    for r in rows:
        s = r["stats"]
        lines.append("| " + " | ".join([
            *[str(r[k]) for k in keys], str(s["completed_trades"]), f"{s['win_rate']}%",
            str(s["total_pnl"]), str(s["expectancy"]), str(s["profit_factor"]),
            str(s["max_drawdown"]), str(s["max_loss"]), str(s["max_consecutive_losses"]),
            str(s["forced_close_ratio"])]) + " |")
    return head + "\n".join(lines)


def _write_summary(out: Path, results: dict) -> None:
    is_rows = [{"exit_policy": p, "stats": _summarize(results[(p, "IS")])} for p in POLICIES]
    oos_rows = [{"exit_policy": p, "stats": _summarize(results[(p, "OOS")])} for p in POLICIES]
    text = (
        "# exit_policy 連続系列A/B (rsi_reversal, paper, read-only)\n\n"
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "連続系列(日跨ぎ可)・期間終了時のみforce-close・RSIは厳密ベクトル化。\n\n"
        "## IS (2026-06-01〜06-12)\n" + _md(is_rows, ["exit_policy"]) + "\n\n"
        "## OOS (2026-05-18〜05-29)\n" + _md(oos_rows, ["exit_policy"]) + "\n"
    )
    (out / "summary.md").write_text(text)


def _write_candidates(out: Path, results: dict) -> None:
    def improves(policy: str) -> bool:
        for per in ("IS", "OOS"):
            b, p = _summarize(results[("baseline", per)]), _summarize(results[(policy, per)])
            if not (p["expectancy"] > b["expectancy"]
                    and (p["profit_factor"] or 0) > (b["profit_factor"] or 0)
                    and p["completed_trades"] >= 30 and p["forced_close_ratio"] < 0.2):
                return False
        return True
    lines = ["# exit_policy 候補（検証のみ・実戦略未組込）\n",
             "| exit_policy | IS/OOS両方で改善(PF↑/期待値↑/≥30/forced<20%)? | 判定 |", "|--|--|--|"]
    for p in POLICIES:
        if p == "baseline":
            continue
        good = improves(p)
        lines.append(f"| {p} | {'Yes' if good else 'No'} | "
                     f"{'継続検証で有望' if good else '却下/判断保留'} |")
    (out / "exit_policy_candidates.md").write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
