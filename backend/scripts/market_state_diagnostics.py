"""No-trade / market-state diagnostics (read-only, paper).

Both simple mean-reversion (rsi_reversal) and simple trend (breakout) failed on
M5 / current_cost. This script does NOT add a new rule or filter. It DIAGNOSES,
per day / window / symbol, the market state under which BOTH strategies lose, to
decide whether a 'no-trade' filter could separate tradable days from chop, and
to pick ONE no-trade candidate to test later (no implementation, no tuning).

Runs rsi_reversal (fast) and breakout on the SAME fetched candles (one fetch per
window-symbol) over the same 15 windows, joins per-day PnL with market-state
indicators (range, ATR-equivalent, direction efficiency, reversals, cost ratio).

No real orders, no Private API, no API key/secret. In-memory DBs only.

  .venv/bin/python -m scripts.market_state_diagnostics
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
from app.services.market_data_service import candles_to_frame, pip_size  # noqa: E402
from scripts.robustness_windows import _mem, _weekdays  # noqa: E402
from scripts.rsi_final_15window import SLIP, SPREAD, SYMBOLS, TIMEFRAME, WINDOWS  # noqa: E402

EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "analysis_exports"
# Assumed round-trip cost in pips (spread + 2x slippage). Used only as a scale.
ASSUMED_COST_PIPS = round(SPREAD + 2 * SLIP, 4)
CLASSES = ["both_win", "rsi_only_win", "breakout_only_win", "both_lose"]


# --- pure indicator helpers (unit-tested) ---------------------------------
def daily_range_pips(highs: list[float], lows: list[float], pip: float) -> float:
    if not highs or not lows or pip <= 0:
        return 0.0
    return round((max(highs) - min(lows)) / pip, 2)


def direction_efficiency(open_: float, close: float, high: float, low: float) -> float:
    """|close-open| / (high-low). 1.0 = clean directional day, ~0 = chop."""
    rng = high - low
    if rng <= 0:
        return 0.0
    return round(abs(close - open_) / rng, 4)


def count_reversals(closes: list[float]) -> int:
    """Number of sign changes in consecutive close-to-close moves (chop proxy)."""
    signs = [1 if b > a else -1 if b < a else 0 for a, b in zip(closes, closes[1:], strict=False)]
    nz = [s for s in signs if s != 0]
    return sum(1 for a, b in zip(nz, nz[1:], strict=False) if a != b)


def classify_day(rsi_pnl: float, bk_pnl: float) -> str:
    if rsi_pnl > 0 and bk_pnl > 0:
        return "both_win"
    if rsi_pnl > 0 >= bk_pnl:
        return "rsi_only_win"
    if bk_pnl > 0 >= rsi_pnl:
        return "breakout_only_win"
    return "both_lose"


def pick_no_trade_candidate(scores: dict[str, float]) -> str:
    """Pick the indicator that best separates both_lose from the rest."""
    return max(scores, key=lambda k: scores[k]) if scores else ""


# --- data plumbing --------------------------------------------------------
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


def _replay_pnl_by_date(candles: list[Candle], symbol: str, strategy: StrategyConfig,
                        execution: ExecutionConfig, fast: bool) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
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
            out.setdefault(t.opened_at.date().isoformat(), []).append(float(t.realized_pnl))
    return out


def _day_market_state(day_frame: pd.DataFrame, pip: float) -> dict:
    highs = [float(x) for x in day_frame["high"]]
    lows = [float(x) for x in day_frame["low"]]
    closes = [float(x) for x in day_frame["close"]]
    open_ = float(day_frame["open"].iloc[0])
    close = closes[-1]
    high, low = max(highs), min(lows)
    rng = daily_range_pips(highs, lows, pip)
    bar_ranges = [(h - low_) / pip for h, low_ in zip(highs, lows, strict=True)]
    atr = round(sum(bar_ranges) / len(bar_ranges), 3) if bar_ranges else 0.0
    return {
        "daily_range_pips": rng,
        "atr_equiv_pips": atr,
        "direction_efficiency": direction_efficiency(open_, close, high, low),
        "reversals": count_reversals(closes),
        "bars": len(day_frame),
        "cost_ratio": round(rng / ASSUMED_COST_PIPS, 2) if ASSUMED_COST_PIPS else 0.0,
    }


def _build_records(broker: GmoFxBroker, warnings: list[str]) -> list[dict]:
    rsi = StrategyConfig(strategy_type=StrategyType.RSI_REVERSAL)
    breakout = StrategyConfig(strategy_type=StrategyType.BREAKOUT)
    execution = ExecutionConfig(spread_pips=SPREAD, slippage_pips=SLIP)
    records: list[dict] = []
    for label, start, end, group in WINDOWS:
        dates = _weekdays(start, end)
        for symbol in SYMBOLS:
            candles = _fetch_candles(broker, symbol, dates, warnings)
            if not candles:
                continue
            pip = pip_size(symbol)
            rsi_pnl = _replay_pnl_by_date(candles, symbol, rsi, execution, fast=True)
            bk_pnl = _replay_pnl_by_date(candles, symbol, breakout, execution, fast=False)
            frame = candles_to_frame(candles)
            frame["date"] = pd.to_datetime(frame["timestamp"]).dt.date.astype(str)
            for date, day_frame in frame.groupby("date"):
                rp, bp = rsi_pnl.get(date, []), bk_pnl.get(date, [])
                ms = _day_market_state(day_frame, pip)
                rec = {
                    "window": label, "group": group, "symbol": symbol, "date": date,
                    "rsi_pnl": round(sum(rp), 2), "rsi_trades": len(rp),
                    "breakout_pnl": round(sum(bp), 2), "breakout_trades": len(bp),
                    **ms,
                }
                rec["classified"] = bool(rp and bp)
                rec["classification"] = classify_day(rec["rsi_pnl"], rec["breakout_pnl"])
                records.append(rec)
        done = sum(1 for r in records if r["window"] == label)
        print(f"{label:>13} {start}-{end} [{group}] day-symbol records={done}")
    return records


# --- aggregation / export -------------------------------------------------
def _median(values: list[float]) -> float:
    return round(statistics.median(values), 4) if values else 0.0


def _mean(values: list[float]) -> float:
    return round(statistics.mean(values), 4) if values else 0.0


def _class_aggregate(records: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    clf = [r for r in records if r["classified"]]
    for cls in CLASSES:
        sub = [r for r in clf if r["classification"] == cls]
        out[cls] = {
            "days": len(sub),
            "rsi_pnl": round(sum(r["rsi_pnl"] for r in sub), 2),
            "breakout_pnl": round(sum(r["breakout_pnl"] for r in sub), 2),
            "avg_range_pips": _mean([r["daily_range_pips"] for r in sub]),
            "avg_atr_pips": _mean([r["atr_equiv_pips"] for r in sub]),
            "avg_direction_efficiency": _mean([r["direction_efficiency"] for r in sub]),
            "avg_reversals": _mean([float(r["reversals"]) for r in sub]),
            "avg_rsi_trades": _mean([float(r["rsi_trades"]) for r in sub]),
            "avg_breakout_trades": _mean([float(r["breakout_trades"]) for r in sub]),
            "avg_cost_ratio": _mean([r["cost_ratio"] for r in sub]),
        }
    return out


def _window_rows(records: list[dict]) -> list[dict]:
    rows = []
    for label, _start, _end, group in WINDOWS:
        sub = [r for r in records if r["window"] == label]
        clf = [r for r in sub if r["classified"]]
        rsi_pnl = round(sum(r["rsi_pnl"] for r in sub), 2)
        bk_pnl = round(sum(r["breakout_pnl"] for r in sub), 2)
        rows.append({
            "window": label, "group": group,
            "period": f"{sub[0]['date']}..{sub[-1]['date']}" if sub else "",
            "rsi_pnl": rsi_pnl, "breakout_pnl": bk_pnl,
            "classification": classify_day(rsi_pnl, bk_pnl),
            "median_range_pips": _median([r["daily_range_pips"] for r in clf]),
            "median_atr_pips": _median([r["atr_equiv_pips"] for r in clf]),
            "median_direction_efficiency": _median([r["direction_efficiency"] for r in clf]),
            "median_reversals": _median([float(r["reversals"]) for r in clf]),
            "avg_rsi_trades": _mean([float(r["rsi_trades"]) for r in clf]),
            "avg_breakout_trades": _mean([float(r["breakout_trades"]) for r in clf]),
            "median_cost_ratio": _median([r["cost_ratio"] for r in clf]),
        })
    return rows


def _symbol_rows(records: list[dict]) -> list[dict]:
    rows = []
    for sym in SYMBOLS:
        sub = [r for r in records if r["symbol"] == sym]
        clf = [r for r in sub if r["classified"]]
        counts = {cls: sum(1 for r in clf if r["classification"] == cls) for cls in CLASSES}
        rows.append({
            "symbol": sym,
            "both_lose_days": counts["both_lose"],
            "rsi_only_win_days": counts["rsi_only_win"],
            "breakout_only_win_days": counts["breakout_only_win"],
            "both_win_days": counts["both_win"],
            "avg_range_pips": _mean([r["daily_range_pips"] for r in clf]),
            "avg_direction_efficiency": _mean([r["direction_efficiency"] for r in clf]),
            "avg_rsi_trades": _mean([float(r["rsi_trades"]) for r in clf]),
            "avg_breakout_trades": _mean([float(r["breakout_trades"]) for r in clf]),
            "rsi_pnl": round(sum(r["rsi_pnl"] for r in sub), 2),
            "breakout_pnl": round(sum(r["breakout_pnl"] for r in sub), 2),
        })
    return rows


def _separation_scores(class_agg: dict) -> dict[str, dict]:
    """Relative separation of both_lose vs the union of win-containing classes."""
    bl = class_agg["both_lose"]
    others = [class_agg[c] for c in CLASSES if c != "both_lose"]
    tot = sum(o["days"] for o in others) or 1

    def _w(field: str) -> float:  # day-weighted mean across the other classes
        return sum(o[field] * o["days"] for o in others) / tot

    # Neutral keys + sign-aware notes (both_lose direction is read from the data,
    # not assumed): low DE = chop, high DE = trend.
    metrics = {
        "volatility_range": ("avg_range_pips", "日次レンジ(ボラ/コスト比)"),
        "direction_efficiency": ("avg_direction_efficiency", "DE 低=チョップ / 高=トレンド"),
        "reversals_overtrading": ("avg_reversals", "M5方向転換回数(ダマシ/過剰取引)"),
    }
    out: dict[str, dict] = {}
    for key, (field, note) in metrics.items():
        bl_v, oth_v = bl[field], _w(field)
        score = abs(bl_v - oth_v) / (abs(oth_v) + 1e-9)
        direction = "高い" if bl_v > oth_v else "低い"
        out[key] = {"both_lose": round(bl_v, 4), "others": round(oth_v, 4),
                    "rel_separation": round(score, 4),
                    "both_lose_direction": direction, "note": note}
    return out


def main() -> int:
    broker = GmoFxBroker()
    warnings: list[str] = []
    records = _build_records(broker, warnings)
    _export(records, warnings)
    return 0


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _export(records: list[dict], warnings: list[str]) -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gmo_public_paper_market_state"
    out = EXPORT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    class_agg = _class_aggregate(records)
    window_rows = _window_rows(records)
    symbol_rows = _symbol_rows(records)
    both_lose = [r for r in records if r["classified"] and r["classification"] == "both_lose"]
    scores = _separation_scores(class_agg)
    candidate = pick_no_trade_candidate({k: v["rel_separation"] for k, v in scores.items()})

    _write_csv(out / "metrics_by_window_market_state.csv", window_rows)
    _write_csv(out / "metrics_by_date_market_state.csv", records)
    _write_csv(out / "metrics_by_symbol_market_state.csv", symbol_rows)
    _write_csv(out / "both_lose_diagnostics.csv", both_lose)

    classified = [r for r in records if r["classified"]]
    summary = {
        "total_day_symbol_records": len(records),
        "classified_records": len(classified),
        "unclassified_records": len(records) - len(classified),
        "class_counts": {c: class_agg[c]["days"] for c in CLASSES},
        "class_aggregate": class_agg,
        "separation_scores": scores,
        "no_trade_candidate": candidate,
        "assumed_cost_pips": ASSUMED_COST_PIPS,
    }
    (out / "metrics_market_state_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2))

    (out / "warnings.json").write_text(json.dumps({
        "data_source": "GMO Public API klines (BID), read-only",
        "fixed_config": f"M5 / current_cost (spread {SPREAD}, slippage {SLIP}) / 4 pairs / "
                        "continuous replay; diagnosis only (no filter, no tuning)",
        "strategies": ["rsi_reversal (fast)", "breakout (period 20)"],
        "indicator_defs": {
            "daily_range_pips": "(day high - day low) / pip",
            "atr_equiv_pips": "mean of per-M5-bar (high-low) / pip",
            "direction_efficiency": "|day close - day open| / (day high - day low)",
            "reversals": "sign changes in consecutive M5 close-to-close moves",
            "cost_ratio": f"daily_range_pips / assumed round-trip cost ({ASSUMED_COST_PIPS} pips)",
        },
        "classification": "per (date, symbol) with rsi_trades>=1 and breakout_trades>=1",
        "note": "no-trade candidate is the indicator best separating both_lose; NOT a tuned "
                "threshold and NOT implemented.",
        "fetch_warnings": warnings,
    }, ensure_ascii=False, indent=2))
    _write_manifest(out, run_id)
    _write_summary(out, window_rows, class_agg, symbol_rows, scores, candidate, summary)
    _write_candidate(out, scores, candidate, class_agg)
    print(f"\nclass counts: {summary['class_counts']}")
    print(f"no_trade_candidate: {candidate}")
    print(f"Export written to: analysis_exports/{run_id}/")


def _write_manifest(out: Path, run_id: str) -> None:
    (out / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_market_state_diagnostics",
        "strategies": ["rsi_reversal", "breakout"],
        "timeframe": TIMEFRAME, "cost_scenario": "current_cost",
        "spread_pips": SPREAD, "slippage_pips": SLIP, "assumed_cost_pips": ASSUMED_COST_PIPS,
        "windows": [{"window": label, "group": group, "dates": _weekdays(s, e)}
                    for label, s, e, group in WINDOWS],
        "symbols": SYMBOLS, "continuous_replay": True, "no_order_execution": True,
        "diagnosis_only": True, "no_filter_implemented": True, "no_threshold_search": True,
        "gmo_readonly": True, "gmo_order_enabled": False,
    }, ensure_ascii=False, indent=2))


def _write_summary(out: Path, window_rows: list[dict], class_agg: dict, symbol_rows: list[dict],
                   scores: dict, candidate: str, summary: dict) -> None:
    win_h = ("| window | group | rsi損益 | breakout損益 | 分類 | レンジ中央 | ATR中央 | DE中央 "
             "| 反転中央 | rsi取引/日 | bk取引/日 | コスト比中央 |\n"
             "|--|--|--:|--:|--|--:|--:|--:|--:|--:|--:|--:|\n")
    win_rows = "\n".join(
        f"| {r['window']} | {r['group']} | {r['rsi_pnl']} | {r['breakout_pnl']} | "
        f"{r['classification']} | {r['median_range_pips']} | {r['median_atr_pips']} | "
        f"{r['median_direction_efficiency']} | {r['median_reversals']} | "
        f"{r['avg_rsi_trades']} | {r['avg_breakout_trades']} | {r['median_cost_ratio']} |"
        for r in window_rows)
    cls_h = ("| 分類 | 日数 | rsi損益 | breakout損益 | 平均レンジ | 平均ATR | 平均DE | 平均反転 "
             "| 平均rsi取引 | 平均bk取引 | 平均コスト比 |\n"
             "|--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|\n")
    cls_rows = "\n".join(
        f"| {c} | {a['days']} | {a['rsi_pnl']} | {a['breakout_pnl']} | {a['avg_range_pips']} | "
        f"{a['avg_atr_pips']} | {a['avg_direction_efficiency']} | {a['avg_reversals']} | "
        f"{a['avg_rsi_trades']} | {a['avg_breakout_trades']} | {a['avg_cost_ratio']} |"
        for c, a in ((c, class_agg[c]) for c in CLASSES))
    sym_h = ("| symbol | both_lose | rsi_only | bk_only | both_win | 平均レンジ | 平均DE "
             "| 平均rsi取引 | 平均bk取引 | rsi損益 | bk損益 |\n"
             "|--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|\n")
    sym_rows = "\n".join(
        f"| {r['symbol']} | {r['both_lose_days']} | {r['rsi_only_win_days']} | "
        f"{r['breakout_only_win_days']} | {r['both_win_days']} | {r['avg_range_pips']} | "
        f"{r['avg_direction_efficiency']} | {r['avg_rsi_trades']} | {r['avg_breakout_trades']} | "
        f"{r['rsi_pnl']} | {r['breakout_pnl']} |"
        for r in symbol_rows)
    sep_rows = "\n".join(
        f"| {k} | {v['both_lose']} | {v['others']} | {v['both_lose_direction']} | "
        f"{v['rel_separation']} | {v['note']} |"
        for k, v in scores.items())
    text = (
        "# no-trade / market-state 診断 (rsi_reversal vs breakout, M5)\n\n"
        "GMO Public klines。実注文なし・Private接続なし・APIキー未使用。"
        "フィルタ未実装・閾値探索なし・診断のみ。分類は (date,symbol) 単位"
        "(両戦略とも当日1取引以上)。\n\n"
        f"- day-symbol記録 {summary['total_day_symbol_records']} / "
        f"分類対象 {summary['classified_records']} / "
        f"対象外 {summary['unclassified_records']}\n"
        f"- 分類カウント: {summary['class_counts']}\n"
        f"- 想定往復コスト: {ASSUMED_COST_PIPS} pips\n\n"
        "## window別 market state 診断\n" + win_h + win_rows + "\n\n"
        "## 分類別集計\n" + cls_h + cls_rows + "\n\n"
        "## symbol別 market state\n" + sym_h + sym_rows + "\n\n"
        "## both_lose 分離スコア(both_lose vs その他)\n"
        "| 指標 | both_lose | その他 | both_lose方向 | 相対分離 | 解釈 |\n"
        "|--|--:|--:|--|--:|--|\n"
        + sep_rows + "\n\n"
        f"## no-trade候補(最大分離): **{candidate}**\n"
    )
    (out / "summary.md").write_text(text)


def _write_candidate(out: Path, scores: dict, candidate: str, class_agg: dict) -> None:
    chosen = scores.get(candidate, {})
    text = (
        "# 次に検証すべき no-trade 候補 (1つだけ)\n\n"
        f"## 候補: {candidate}\n\n"
        f"- 解釈: {chosen.get('note', '')}\n"
        f"- both_lose群の値 {chosen.get('both_lose')} / その他群 {chosen.get('others')} "
        f"(相対分離 {chosen.get('rel_separation')})\n\n"
        "## 全候補の分離スコア\n"
        + "\n".join(f"- {k}: both_lose {v['both_lose']} / others {v['others']} / "
                    f"sep {v['rel_separation']}" for k, v in scores.items()) + "\n\n"
        "## 採用条件(将来テスト時)\n"
        "- 同一15窓・同一固定条件で、この1指標による entry-only no-trade ゲートを"
        "rsi_reversal baseline に追加し、IS/OOS群比較で baseline比 期待値中央値↑・"
        "PF中央値↑・プラス窓↑・OOSで崩れない・単一窓/ペア依存でない。\n\n"
        "## 却下条件\n"
        "- OOSで非再現、baseline以下、改善が単一窓/単一ペア依存、見送り率が高すぎて"
        "活動が枯れる。\n\n"
        "## 実装時の注意\n"
        "- ルックアヘッド禁止(当日確定前のバーまでで判定、ADXフィルタと同じ index-1 規約)。\n"
        "- 閾値は1点固定で開始し探索しない。決済ロジックは不変。\n\n"
        "## 今回実装していないこと\n"
        "- no-tradeフィルタ本体・閾値探索・SL/TP/パラメータ変更・複数指標の併用。\n"
    )
    (out / "no_trade_candidate.md").write_text(text)


if __name__ == "__main__":
    raise SystemExit(main())
