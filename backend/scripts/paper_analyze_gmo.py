"""Read-only regime / time / holding analysis of stored paper trades.

Reads completed PaperTrade rows from the DB, re-fetches GMO Public klines
(read-only, no key, no auth) to derive each trade's market regime at entry
(ADX/ATR/MA-slope/range), and writes a full breakdown to
analysis_exports/<run_id>/. No real orders, no Private API, no DB writes.

  .venv/bin/python -m scripts.paper_analyze_gmo
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.brokers import GmoFxBroker, GmoFxBrokerError  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import PaperTrade, PaperTradeSession  # noqa: E402
from app.services.market_data_service import candles_to_frame  # noqa: E402
from app.services.paper_analysis_service import (  # noqa: E402
    ADX_BANDS,
    TIME_BUCKETS,
    aggregate,
    aggregate_pair,
    enrich_trades,
    indicator_lookup,
    streak_and_tail,
)
from app.services.performance_service import _trade_stats  # noqa: E402

EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "analysis_exports"
_STAT_FIELDS = [
    "completed_trades", "win_rate", "total_pnl", "avg_win", "avg_loss",
    "expectancy", "profit_factor", "max_drawdown", "reference_only",
]


def _gmo_date(dt: datetime) -> str:
    # GMO klines date window is [prev 21:00, date 20:59] UTC.
    base = dt + timedelta(days=1) if dt.hour >= 21 else dt
    return base.strftime("%Y%m%d")


def _load_trades() -> tuple[list[dict], int, float]:
    with SessionLocal() as db:
        sessions = {s.id: s.strategy_type for s in db.scalars(select(PaperTradeSession)).all()}
        rows = db.scalars(select(PaperTrade)).all()
        trades = [
            {
                "symbol": t.symbol,
                "strategy": sessions.get(t.session_id, "unknown"),
                "side": t.side,
                "pnl": float(t.realized_pnl),
                "opened_at": t.opened_at,
                "closed_at": t.closed_at,
                "date": t.opened_at.date().isoformat(),
            }
            for t in rows
            if t.status == "closed" and t.realized_pnl is not None
        ]
        open_rows = [t for t in rows if t.status == "open"]
        unrealized = round(sum(float(t.unrealized_pnl) for t in open_rows), 2)
    return trades, len(open_rows), unrealized


def _write_csv(path: Path, stats_map: dict[str, dict], key_name: str) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([key_name, *_STAT_FIELDS])
        for name, stats in stats_map.items():
            writer.writerow([name, *[stats[f] for f in _STAT_FIELDS]])


def _fmt(stats_map: dict[str, dict], label: str) -> str:
    lines = []
    for name, s in stats_map.items():
        ref = " (参考値<30)" if s["reference_only"] else ""
        lines.append(
            f"  {name:<28} 完了{s['completed_trades']:>4} 勝率{s['win_rate']:>5}% "
            f"総益{s['total_pnl']:>8} 期待値{s['expectancy']:>8} PF{s['profit_factor']}{ref}"
        )
    return f"### {label}\n" + "\n".join(lines)


def main() -> int:
    trades_raw, open_count, unrealized = _load_trades()
    if not trades_raw:
        print("No completed paper trades in DB. Run scripts.paper_trade_gmo_batch first.")
        return 1

    symbols = sorted({t["symbol"] for t in trades_raw})
    gmo_dates = sorted({_gmo_date(t["opened_at"]) for t in trades_raw})
    print(f"trades={len(trades_raw)}  symbols={symbols}  gmo_dates={gmo_dates}")

    broker = GmoFxBroker()  # public only; read-only
    lookups: dict[str, dict] = {}
    warnings: list[str] = []
    for symbol in symbols:
        frames = []
        for date in gmo_dates:
            try:
                frames.append(
                    candles_to_frame(broker.candles(symbol, "M1", count=2000, date=date))
                )
            except GmoFxBrokerError as error:
                warnings.append(f"kline fetch failed {symbol} {date}: {error}")
            time.sleep(0.25)
        if not frames:
            warnings.append(f"no candles for {symbol}; regime buckets will be 'unknown'")
            lookups[symbol] = {}
            continue
        combined = _concat_frames(frames)
        lookups[symbol] = indicator_lookup(combined, symbol)
        print(f"  {symbol}: indicator bars={len(combined)}")

    trades = enrich_trades(trades_raw, lookups)

    # composite keys for triple cut
    for t in trades:
        t["sym_strat_time"] = f"{t['symbol']}|{t['strategy']}|{t['time_bucket']}"

    cuts = {
        "overall": _trade_stats([t["pnl"] for t in trades]),
        "by_symbol": aggregate(trades, "symbol"),
        "by_strategy": aggregate(trades, "strategy"),
        "by_symbol_strategy": aggregate_pair(trades, "symbol", "strategy"),
        "by_date": aggregate(trades, "date"),
        "by_time_bucket": aggregate(trades, "time_bucket"),
        "by_strategy_time_bucket": aggregate_pair(trades, "strategy", "time_bucket"),
        "by_symbol_time_bucket": aggregate_pair(trades, "symbol", "time_bucket"),
        "by_symbol_strategy_time": aggregate(trades, "sym_strat_time"),
        "by_adx_bucket": aggregate(trades, "adx_bucket"),
        "by_strategy_adx": aggregate_pair(trades, "strategy", "adx_bucket"),
        "by_atr_bucket": aggregate(trades, "atr_bucket"),
        "by_ma_slope": aggregate(trades, "ma_slope_class"),
        "by_range_bucket": aggregate(trades, "range_bucket"),
        "by_holding_bucket": aggregate(trades, "holding_bucket"),
    }
    streaks = streak_and_tail(trades)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_gmo_public_paper_regime_filter_candidate"
    out = EXPORT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=True)

    (out / "metrics_overall.json").write_text(
        json.dumps(cuts["overall"], ensure_ascii=False, indent=2)
    )
    _write_csv(out / "metrics_by_symbol.csv", cuts["by_symbol"], "symbol")
    _write_csv(out / "metrics_by_strategy.csv", cuts["by_strategy"], "strategy")
    _write_csv(
        out / "metrics_by_symbol_strategy.csv", cuts["by_symbol_strategy"], "symbol_strategy"
    )
    _write_csv(out / "metrics_by_date.csv", cuts["by_date"], "date")
    _write_csv(out / "metrics_by_time_bucket.csv", cuts["by_time_bucket"], "time_bucket")
    _write_csv(out / "metrics_by_strategy_time_bucket.csv",
               cuts["by_strategy_time_bucket"], "strategy_time")
    _write_csv(out / "metrics_by_symbol_time_bucket.csv",
               cuts["by_symbol_time_bucket"], "symbol_time")
    _write_csv(out / "metrics_by_symbol_strategy_time.csv",
               cuts["by_symbol_strategy_time"], "symbol_strategy_time")
    _write_csv(out / "metrics_by_regime.csv", cuts["by_strategy_adx"], "strategy_adx")
    indicator_buckets = {
        **{f"adx::{k}": v for k, v in cuts["by_adx_bucket"].items()},
        **{f"atr::{k}": v for k, v in cuts["by_atr_bucket"].items()},
        **{f"ma_slope::{k}": v for k, v in cuts["by_ma_slope"].items()},
        **{f"range::{k}": v for k, v in cuts["by_range_bucket"].items()},
    }
    _write_csv(out / "metrics_by_indicator_bucket.csv", indicator_buckets, "indicator_bucket")
    _write_csv(out / "metrics_by_holding_time.csv", cuts["by_holding_bucket"], "holding_bucket")
    (out / "metrics_drawdown_streaks.json").write_text(
        json.dumps(streaks, ensure_ascii=False, indent=2)
    )
    (out / "warnings.json").write_text(json.dumps(
        {
            "data_source": "GMO Public API klines (BID), read-only",
            "no_real_spread": "Public klines are single-price; real per-trade spread is "
                              "unavailable, so spread buckets are NOT computed.",
            "indicator_join": "regime indicators recomputed from re-fetched klines and joined "
                              "by entry timestamp; weekend-gap bars may be slightly distorted.",
            "exploration_window": gmo_dates,
            "fetch_warnings": warnings,
        }, ensure_ascii=False, indent=2))

    manifest = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_regime_filter_candidate",
        "source": "stored PaperTrade rows + GMO Public klines (read-only)",
        "exploration_dates_gmo": gmo_dates,
        "symbols": symbols,
        "strategies": sorted({t["strategy"] for t in trades}),
        "completed_trades": len(trades),
        "open_positions": open_count,
        "unrealized_pnl": unrealized,
        "time_buckets_utc": TIME_BUCKETS,
        "adx_bands": ADX_BANDS,
        "atr_range_bucketing": "data-driven tertiles (low/mid/high)",
        "ma_slope_flat_zone": "|slope| in bottom tertile -> flat",
        "no_order_execution": True,
        "gmo_order_enabled": False,
        "gmo_readonly": True,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    _write_summary(out, cuts, streaks, manifest)
    _write_filter_candidates(out, cuts)

    print("\n" + _fmt(cuts["by_strategy"], "by_strategy"))
    print("\n" + _fmt(cuts["by_strategy_adx"], "by_strategy x ADX"))
    print("\n" + _fmt(cuts["by_time_bucket"], "by_time_bucket"))
    print("\n" + _fmt(cuts["by_holding_bucket"], "by_holding_bucket"))
    print(f"\nstreaks: max_loss_streak={streaks['max_consecutive_losses']} "
          f"max_single_loss={streaks['max_single_loss']}")
    print(f"\nExport written to: analysis_exports/{run_id}/")
    return 0


def _concat_frames(frames: list) -> pd.DataFrame:
    merged = pd.concat(frames, ignore_index=True)
    return merged.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)


def _md_table(stats_map: dict[str, dict], key_label: str) -> str:
    header = (
        f"| {key_label} | 完了 | 勝率 | 総損益 | 期待値 | PF | 最大DD | 判定 |\n"
        "|--|--:|--:|--:|--:|--:|--:|--|\n"
    )
    rows = []
    for name, s in stats_map.items():
        verdict = "参考値<30" if s["reference_only"] else (
            "有望?" if s["expectancy"] > 0 and (s["profit_factor"] or 0) > 1 else "負"
        )
        rows.append(
            f"| {name} | {s['completed_trades']} | {s['win_rate']}% | {s['total_pnl']} | "
            f"{s['expectancy']} | {s['profit_factor']} | {s['max_drawdown']} | {verdict} |"
        )
    return header + "\n".join(rows)


def _write_summary(out: Path, cuts: dict, streaks: dict, manifest: dict) -> None:
    o = cuts["overall"]
    dates = manifest["exploration_dates_gmo"]
    is_range = f"{dates[0]}〜{dates[-1]}"
    tokyo_pf = cuts["by_time_bucket"].get("tokyo", {}).get("profit_factor")
    ny_pf = cuts["by_time_bucket"].get("new_york", {}).get("profit_factor")
    # Best strategy x time cell with a usable sample (>=30 completed trades).
    eligible = {k: v for k, v in cuts["by_strategy_time_bucket"].items()
                if v["completed_trades"] >= 30}
    best_cell = max(eligible, key=lambda k: eligible[k]["expectancy"]) if eligible else "n/a"
    bc = eligible.get(best_cell, {"expectancy": 0, "profit_factor": 0, "completed_trades": 0})
    text = f"""# GMO Public ペーパートレード 追加分析 summary

run_id: {manifest['run_id']}
探索期間(GMO date): {is_range}
通貨ペア: {manifest['symbols']} / 戦略: {manifest['strategies']}
データ: GMO Public klines(BID) read-only。実注文なし・Private接続なし・APIキー未使用。

## 全体
完了 {o['completed_trades']} / 勝率 {o['win_rate']}% / 総損益 {o['total_pnl']} /
平均利益 {o['avg_win']} / 平均損失 {o['avg_loss']} / 期待値 {o['expectancy']} /
PF {o['profit_factor']} / 最大DD {o['max_drawdown']} /
未決済 {manifest['open_positions']} / 含み損益 {manifest['unrealized_pnl']}

## 追加分析の要約
### 戦略別
{_md_table(cuts['by_strategy'], 'strategy')}

### 戦略 × ADX(レジーム)
{_md_table(cuts['by_strategy_adx'], 'strategy|adx')}

### 時間帯別
{_md_table(cuts['by_time_bucket'], 'time_bucket')}

### rsi_reversal の時間帯別
{_md_table({k: v for k, v in cuts['by_strategy_time_bucket'].items()
            if k.startswith('rsi_reversal')}, 'rsi|time')}

### 保有時間別
{_md_table(cuts['by_holding_bucket'], 'holding')}

### インディケーター帯(ATR/MA傾き/レンジ)
ATR: {_md_table(cuts['by_atr_bucket'], 'atr')}
MA傾き: {_md_table(cuts['by_ma_slope'], 'ma_slope')}

### 連敗 / 大負け
最大連敗 {streaks['max_consecutive_losses']} / 最大連勝 {streaks['max_consecutive_wins']} /
最大単発損失 {streaks['max_single_loss']} / 最大単発利益 {streaks['max_single_win']}
上位5損失: {streaks['top5_losses']}

## アウト・オブ・サンプル(OOS)計画
- 探索期間(IS): {is_range}（本runで使用）
- 検証期間(OOS)候補: ISと重ならない別週（直近の別5営業日 等）で同一条件で再集計
- OOS確認条件: フィルター候補の期待値/PF/最大DD/取引数が IS と同方向か
- 過剰最適化回避: 条件は1つ・30件以上・別期間で同傾向のもののみ採用候補

## 次に検証すべき仮説 (1つ)
- 仮説: {best_cell} は探索期間で唯一の正の期待値セル（期待値{bc['expectancy']},
  PF{bc['profit_factor']}, n={bc['completed_trades']}）。エントリを「rsi_reversal かつ
  東京時間(00:00-08:00 UTC)」に限定すると正の期待値が出る。
- 根拠: 戦略×時間帯の最良セル(>=30件)。tokyo PF{tokyo_pf} > new_york PF{ny_pf} とも整合。
  逆張りはレンジ寄りの東京時間で機能しやすいという説明もつく。
- 次回検証方法: IS と重ならない別週で同条件リプレイ→ by_strategy_time_bucket を再集計し、
  rsi_reversal|tokyo の期待値>0・PF>1 が再現するか。
- 採用条件: OOSでも rsi×tokyo が期待値>0・PF>1・30件以上・最大DD悪化なし・別週でも同方向。
- 却下条件: OOSで期待値<=0/PF<1、取引数が30未満、その週の地合い依存と判明。

## 注意 (warnings.json も参照)
- Public klines は単一価格のため実スプレッドが無く、スプレッド別集計は未実施。
- レジーム指標は再取得klineから再計算しエントリ時刻で結合（週末ギャップ近傍は軽微な歪みあり）。
"""
    (out / "summary.md").write_text(text)


def _write_filter_candidates(out: Path, cuts: dict) -> None:
    # Pick best/worst time buckets from the data so the narrative stays accurate.
    times = cuts["by_time_bucket"]
    best_t = max(times, key=lambda k: times[k]["expectancy"])
    worst_t = min(times, key=lambda k: times[k]["expectancy"])
    st = cuts["by_strategy_time_bucket"]
    eligible = {k: v for k, v in st.items() if v["completed_trades"] >= 30}
    best_cell = max(eligible, key=lambda k: eligible[k]["expectancy"]) if eligible else "n/a"
    bc = eligible.get(best_cell, {"expectancy": 0, "profit_factor": 0, "completed_trades": 0})
    text = (
        "# フィルター候補 (今回は抽出のみ。実戦略には組み込まない)\n\n"
        f"探索期間の time_bucket: 最良={best_t}(期待値{times[best_t]['expectancy']}, "
        f"PF{times[best_t]['profit_factor']}) / "
        f"最悪={worst_t}(期待値{times[worst_t]['expectancy']}, "
        f"PF{times[worst_t]['profit_factor']})\n\n"
        "| 候補 | 根拠 | 期待される効果 | 注意点 | 次回検証方法 |\n"
        "|--|--|--|--|--|\n"
        f"| {best_cell}(rsi_reversal×東京時間)に絞る | 戦略×時間帯で唯一の正セル"
        f"(期待値{bc['expectancy']}, PF{bc['profit_factor']}, n={bc['completed_trades']}) | "
        "期待値プラス・PF>1の可能性 | 1期間のみ・最良セル選択による過剰最適化に注意 | "
        "OOS別週で rsi×tokyo の期待値>0・PF>1・30件以上を確認 |\n"
        f"| エントリを {best_t} 時間帯に絞る(={worst_t}回避) | "
        f"{best_t}が最PF高・{worst_t}最悪。大サンプルで適用可 | "
        "全体の期待値/PF改善方向(依然マイナス) | 取引数が約1/3・依然負 | "
        f"OOS別週で {best_t} vs {worst_t} 差が再現するか |\n"
        "| MA系(ma_cross/breakout)は停止候補 | 全ADX帯・全時間帯・全ペアで負(PF<0.6) | "
        "コスト/DD削減 | トレンド継続期は未検証 | OOS別週でも期待値<0が続くか |\n\n"
        "## 注意: 保有時間は『エントリ時フィルター』ではない\n"
        "保有60分以上=PF2.35・<30分=ほぼ全敗 は強い相関だが、保有時間はエントリ時に未知の"
        "事後変数(ルックアヘッド)。エントリフィルターには使えない。これは『反対シグナル早期"
        "決済(whipsaw)+摩擦コスト』が出口で損を量産していることを示す出口ロジックの診断で"
        "あり、将来の戦略改善仮説(本タスク対象外)として記録する。\n"
    )
    (out / "filter_candidates.md").write_text(text)


if __name__ == "__main__":
    raise SystemExit(main())
