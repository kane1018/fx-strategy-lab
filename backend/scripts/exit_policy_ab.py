"""Exit-policy A/B analysis for rsi_reversal (paper, read-only).

Compares exit policies (baseline vs no_opposite_signal_exit vs
min_hold_30m_before_opposite_exit) on the same GMO Public klines, across the IS
and OOS windows. Entry logic / RSI params / time / ADX filters are NOT changed.
Each replay runs in a throwaway in-memory DB, so the real fx_trading.db is never
touched. force_close_at_end is applied so both policies are comparable (no open
positions left); the share of forced closes is reported as a distortion check.

No real orders, no Private API, no API key/secret.

  .venv/bin/python -m scripts.exit_policy_ab
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.brokers import GmoFxBroker, GmoFxBrokerError  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import PaperTrade  # noqa: E402
from app.schemas.trading import ExecutionConfig, StrategyConfig, StrategyType  # noqa: E402
from app.services.gmo_paper_service import EXIT_POLICIES, replay_paper_trades  # noqa: E402
from app.services.paper_analysis_service import holding_bucket, holding_minutes  # noqa: E402
from app.services.performance_service import _trade_stats  # noqa: E402

EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "analysis_exports"
SYMBOLS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY"]
PERIODS = {
    "IS": ["20260601", "20260602", "20260603", "20260604", "20260605",
           "20260608", "20260609", "20260610", "20260611", "20260612"],
    "OOS": ["20260518", "20260519", "20260520", "20260521", "20260522",
            "20260525", "20260526", "20260527", "20260528", "20260529"],
}
_FORCED_REASON = "データ終了強制クローズ"
_STAT_FIELDS = [
    "completed_trades", "win_rate", "total_pnl", "avg_win", "avg_loss",
    "expectancy", "profit_factor", "max_drawdown", "max_loss",
    "max_consecutive_losses", "forced_close_n", "forced_close_pnl", "reference_only",
]


def _mem_session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _summarize(trades: list[dict]) -> dict:
    stats = _trade_stats([t["pnl"] for t in trades])
    ordered = sorted(trades, key=lambda t: t["closed_at"])
    max_loss_streak = streak = 0
    for trade in ordered:
        if trade["pnl"] < 0:
            streak += 1
            max_loss_streak = max(max_loss_streak, streak)
        elif trade["pnl"] > 0:
            streak = 0
    forced = [t for t in trades if t["exit_reason"] == _FORCED_REASON]
    return {
        **{k: stats[k] for k in
           ["completed_trades", "win_rate", "total_pnl", "avg_win", "avg_loss",
            "expectancy", "profit_factor", "max_drawdown", "max_loss", "reference_only"]},
        "max_consecutive_losses": max_loss_streak,
        "forced_close_n": len(forced),
        "forced_close_pnl": round(sum(t["pnl"] for t in forced), 2),
    }


def _write_csv(path: Path, rows: list[dict], keys: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([*keys, *_STAT_FIELDS])
        for row in rows:
            writer.writerow([*[row[k] for k in keys], *[row["stats"][f] for f in _STAT_FIELDS]])


def main() -> int:
    strategy = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    execution = ExecutionConfig()
    broker = GmoFxBroker()  # public only; read-only
    warnings: list[str] = []

    # Fetch + cache candles once per (symbol, date), reused across all policies.
    cache: dict[tuple[str, str], list] = {}
    for _period, dates in PERIODS.items():
        for symbol in SYMBOLS:
            for date in dates:
                try:
                    cache[(symbol, date)] = broker.candles(symbol, "M1", count=1500, date=date)
                except GmoFxBrokerError as error:
                    warnings.append(f"fetch failed {symbol} {date}: {error}")
                time.sleep(0.2)
    print(f"cached candle sets: {len(cache)}")

    # (policy, period) -> list of completed trade dicts
    results: dict[tuple[str, str], list[dict]] = {}
    for policy in EXIT_POLICIES:
        for period, dates in PERIODS.items():
            trades: list[dict] = []
            for symbol in SYMBOLS:
                for date in dates:
                    candles = cache.get((symbol, date))
                    if not candles:
                        continue
                    with _mem_session() as db:
                        res = replay_paper_trades(
                            db, symbol=symbol, timeframe="M1", candles=candles,
                            strategy=strategy, execution=execution,
                            exit_policy=policy, force_close_at_end=True,
                        )
                        rows = db.scalars(
                            select(PaperTrade).where(
                                PaperTrade.session_id == res["session_id"],
                                PaperTrade.status == "closed",
                            )
                        ).all()
                        for t in rows:
                            minutes = holding_minutes(t.opened_at, t.closed_at)
                            trades.append({
                                "pnl": float(t.realized_pnl),
                                "symbol": symbol,
                                "date": t.opened_at.date().isoformat(),
                                "closed_at": t.closed_at,
                                "holding_bucket": holding_bucket(minutes),
                                "exit_reason": t.exit_reason or "",
                            })
            results[(policy, period)] = trades
            s = _summarize(trades)
            print(f"{policy:<34} {period:<3} done={s['completed_trades']:>4} "
                  f"win={s['win_rate']:>5}% exp={s['expectancy']:>8} PF={s['profit_factor']} "
                  f"maxDD={s['max_drawdown']} maxLoss={s['max_loss']} forced={s['forced_close_n']}")

    _export(results, warnings)
    return 0


def _export(results: dict[tuple[str, str], list[dict]], warnings: list[str]) -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gmo_public_paper_exit_policy_ab"
    out = EXPORT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    by_policy_period = [
        {"exit_policy": pol, "period": per, "stats": _summarize(tr)}
        for (pol, per), tr in results.items()
    ]
    by_policy = [
        {"exit_policy": pol,
         "stats": _summarize(results[(pol, "IS")] + results[(pol, "OOS")])}
        for pol in EXIT_POLICIES
    ]
    by_policy_symbol = []
    for (pol, per), tr in results.items():
        for symbol in SYMBOLS:
            sub = [t for t in tr if t["symbol"] == symbol]
            if sub:
                by_policy_symbol.append(
                    {"exit_policy": pol, "period": per, "symbol": symbol, "stats": _summarize(sub)}
                )
    by_holding = []
    for pol in EXIT_POLICIES:
        merged = results[(pol, "IS")] + results[(pol, "OOS")]
        for bucket in ["<5min", "5-15min", "15-30min", "30-60min", "60min+"]:
            sub = [t for t in merged if t["holding_bucket"] == bucket]
            if sub:
                by_holding.append(
                    {"exit_policy": pol, "holding_time_bucket": bucket, "stats": _summarize(sub)}
                )
    by_date = []
    for (pol, per), tr in results.items():
        dates = sorted({t["date"] for t in tr})
        for date in dates:
            sub = [t for t in tr if t["date"] == date]
            by_date.append(
                {"exit_policy": pol, "period": per, "date": date, "stats": _summarize(sub)}
            )

    _write_csv(out / "metrics_by_exit_policy.csv", by_policy, ["exit_policy"])
    _write_csv(out / "metrics_by_exit_policy_period.csv", by_policy_period,
               ["exit_policy", "period"])
    _write_csv(out / "metrics_by_exit_policy_symbol.csv", by_policy_symbol,
               ["exit_policy", "period", "symbol"])
    _write_csv(out / "metrics_by_holding_time.csv", by_holding,
               ["exit_policy", "holding_time_bucket"])
    _write_csv(out / "metrics_by_date.csv", by_date, ["exit_policy", "period", "date"])
    (out / "metrics_overall.json").write_text(json.dumps(
        {f"{pol}|{per}": _summarize(tr) for (pol, per), tr in results.items()},
        ensure_ascii=False, indent=2))
    (out / "metrics_drawdown_streaks.json").write_text(json.dumps(
        {f"{pol}|{per}": {
            "max_consecutive_losses": _summarize(tr)["max_consecutive_losses"],
            "max_single_loss": _summarize(tr)["max_loss"],
        } for (pol, per), tr in results.items()}, ensure_ascii=False, indent=2))
    (out / "warnings.json").write_text(json.dumps({
        "data_source": "GMO Public API klines (BID), read-only",
        "strategy": "rsi_reversal only (main judgment)",
        "force_close_at_end": "applied to ALL policies for comparability; forced_close_n "
                              "reports how many trades that affected per cell.",
        "per_date_replay": "each (symbol, date) replayed separately; positions cannot span "
                           "across calendar dates, which slightly caps holding time.",
        "no_real_spread": "Public klines are single-price; spread is a fixed estimate.",
        "fetch_warnings": warnings,
    }, ensure_ascii=False, indent=2))

    manifest = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_exit_policy_ab",
        "strategy": "rsi_reversal",
        "exit_policies": list(EXIT_POLICIES),
        "periods": PERIODS,
        "symbols": SYMBOLS,
        "interval": "1min",
        "force_close_at_end": True,
        "no_order_execution": True,
        "gmo_readonly": True,
        "gmo_order_enabled": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    _write_summary(out, results)
    _write_candidates(out, results)
    print(f"\nExport written to: analysis_exports/{run_id}/")


def _md(rows: list[dict], keys: list[str]) -> str:
    head = "| " + " | ".join([*keys, "完了", "勝率", "総損益", "期待値", "PF",
                              "最大DD", "最大単発損失", "max連敗", "forced"]) + " |\n"
    head += "|" + "--|" * (len(keys) + 9) + "\n"
    lines = []
    for r in rows:
        s = r["stats"]
        lines.append("| " + " | ".join([
            *[str(r[k]) for k in keys], str(s["completed_trades"]), f"{s['win_rate']}%",
            str(s["total_pnl"]), str(s["expectancy"]), str(s["profit_factor"]),
            str(s["max_drawdown"]), str(s["max_loss"]), str(s["max_consecutive_losses"]),
            str(s["forced_close_n"]),
        ]) + " |")
    return head + "\n".join(lines)


def _write_summary(out: Path, results: dict) -> None:
    is_rows = [{"exit_policy": p, "stats": _summarize(results[(p, "IS")])} for p in EXIT_POLICIES]
    oos_rows = [{"exit_policy": p, "stats": _summarize(results[(p, "OOS")])} for p in EXIT_POLICIES]
    base_is = _summarize(results[("baseline", "IS")])
    base_oos = _summarize(results[("baseline", "OOS")])
    diff_rows = []
    for p in EXIT_POLICIES:
        for per, base in (("IS", base_is), ("OOS", base_oos)):
            s = _summarize(results[(p, per)])
            diff_rows.append(
                f"| {per} | {p} | {round(s['expectancy'] - base['expectancy'], 4)} | "
                f"{round((s['profit_factor'] or 0) - (base['profit_factor'] or 0), 3)} | "
                f"{round(s['max_drawdown'] - base['max_drawdown'], 2)} | "
                f"{round(s['max_loss'] - base['max_loss'], 4)} |"
            )
    text = (
        "# exit_policy A/B (rsi_reversal, paper, read-only)\n\n"
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "全policyに force_close_at_end を適用（未決済0で公平比較）。\n\n"
        "## IS (2026-06-01〜06-12)\n" + _md(is_rows, ["exit_policy"]) + "\n\n"
        "## OOS (2026-05-18〜05-29)\n" + _md(oos_rows, ["exit_policy"]) + "\n\n"
        "## baselineとの差分\n"
        "| period | exit_policy | 期待値差分 | PF差分 | 最大DD差分 | 最大単発損失差分 |\n"
        "|--|--|--:|--:|--:|--:|\n" + "\n".join(diff_rows) + "\n"
    )
    (out / "summary.md").write_text(text)


def _write_candidates(out: Path, results: dict) -> None:
    def ok(policy: str) -> bool:
        b_is = _summarize(results[("baseline", "IS")])
        b_oos = _summarize(results[("baseline", "OOS")])
        p_is = _summarize(results[(policy, "IS")])
        p_oos = _summarize(results[(policy, "OOS")])
        return (
            p_is["expectancy"] > b_is["expectancy"] and p_oos["expectancy"] > b_oos["expectancy"]
            and (p_is["profit_factor"] or 0) > (b_is["profit_factor"] or 0)
            and (p_oos["profit_factor"] or 0) > (b_oos["profit_factor"] or 0)
            and p_is["completed_trades"] >= 30 and p_oos["completed_trades"] >= 30
        )
    lines = ["# exit_policy 候補（検証のみ。実戦略へは未組込）\n",
             "| exit_policy | IS/OOS両方でbaseline改善? | 判定 |", "|--|--|--|"]
    for policy in EXIT_POLICIES:
        if policy == "baseline":
            continue
        verdict = "継続検証で有望" if ok(policy) else "却下/判断保留"
        lines.append(f"| {policy} | {'Yes' if ok(policy) else 'No'} | {verdict} |")
    lines.append("\n採用条件: IS・OOS両方で 期待値↑・PF↑・各≥30件・最大DD/最大損失の悪化なし。")
    (out / "exit_policy_candidates.md").write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
