"""Regime predictability diagnostic (read-only, NO trading).

Closing diagnostic for the research phase. Across M5/M15/scaled, rsi_reversal wins
in low-DE (chop) and loses in high-DE (trend). A no-trade filter or regime switch is
only viable if today's DE regime can be predicted from PAST bars (no look-ahead).

This script does NOT trade. It labels each (symbol, day) by its DE tertile
(low/medium/high), builds features from PRIOR days only, and tests whether simple
rules / baselines beat the majority class out-of-sample (prior10 vs oos5). No sklearn,
no new deps — plain baselines and fixed-threshold rules (thresholds set on prior10
and applied unchanged to oos5).

Label uses the day's own OHLC; features never use the current day. No real orders,
no Private API, no API key/secret. In-memory only (no DB writes).

  .venv/bin/python -m scripts.regime_predictability_diagnostics
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from app.brokers import GmoFxBroker  # noqa: E402
from app.services.market_data_service import candles_to_frame, pip_size  # noqa: E402
from scripts.bollinger_15window import de_bucket, de_thresholds  # noqa: E402
from scripts.fx_eval_common import (  # noqa: E402
    EXPORT_ROOT,
    SYMBOLS,
    WINDOWS,
    _weekdays,
    fixed_config,
    run_id,
    safety_metadata,
)
from scripts.market_state_diagnostics import _day_market_state, _fetch_candles  # noqa: E402

CLASSES = ["low_de", "medium_de", "high_de"]
RULES = ["majority", "persistence", "vote3", "vote5",
         "prior_de_bucket", "roll3_de_bucket", "roll3_range_high"]


# --- pure helpers (unit-tested) -------------------------------------------
def _mean(values: list[float]) -> float:
    return round(statistics.mean(values), 4) if values else 0.0


def _vote(labels: list[str]) -> str:
    return Counter(labels).most_common(1)[0][0]


def build_feature_rows(day_records: list[dict]) -> list[dict]:
    """Per-day rows whose features come ONLY from prior days (no look-ahead).

    day_records: chronological list for one symbol within one window, each with
    direction_efficiency / daily_range_pips / atr_equiv_pips / reversals /
    cost_ratio / ret_pips / bull / de_label / date.
    """
    rows = []
    for i in range(1, len(day_records)):
        cur, prev = day_records[i], day_records[i - 1]
        last3, last5 = day_records[max(0, i - 3):i], day_records[max(0, i - 5):i]
        rows.append({
            "date": cur["date"], "label": cur["de_label"],  # label = TODAY (allowed)
            "prev_de": prev["direction_efficiency"],
            "prev_range": prev["daily_range_pips"],
            "prev_atr": prev["atr_equiv_pips"],
            "prev_reversals": prev["reversals"],
            "prev_cost_ratio": prev["cost_ratio"],
            "prev_ret": prev["ret_pips"],
            "prev_bull": prev["bull"],
            "prev_de_label": prev["de_label"],
            "roll3_de": _mean([d["direction_efficiency"] for d in last3]) if len(last3) >= 3
            else None,
            "roll3_range": _mean([d["daily_range_pips"] for d in last3]) if len(last3) >= 3
            else None,
            "roll5_de": _mean([d["direction_efficiency"] for d in last5]) if len(last5) >= 5
            else None,
            "vote3_label": _vote([d["de_label"] for d in last3]) if len(last3) >= 3 else None,
            "vote5_label": _vote([d["de_label"] for d in last5]) if len(last5) >= 5 else None,
        })
    return rows


def predict(rule: str, row: dict, ctx: dict) -> str | None:
    if rule == "majority":
        return ctx["majority_label"]
    if rule == "persistence":
        return row["prev_de_label"]
    if rule == "vote3":
        return row["vote3_label"]
    if rule == "vote5":
        return row["vote5_label"]
    if rule == "prior_de_bucket":
        return de_bucket(row["prev_de"], ctx["lo"], ctx["hi"])
    if rule == "roll3_de_bucket":
        return de_bucket(row["roll3_de"], ctx["lo"], ctx["hi"]) if row["roll3_de"] is not None \
            else None
    if rule == "roll3_range_high":
        v = row["roll3_range"]
        return None if v is None else ("high_de" if v >= ctx["range_thr"] else "low_de")
    return None


def accuracy(pairs: list[tuple[str, str]]) -> float:
    return round(sum(1 for t, p in pairs if t == p) / len(pairs), 4) if pairs else 0.0


def recall(pairs: list[tuple[str, str]], cls: str) -> float:
    tp = sum(1 for t, p in pairs if t == cls and p == cls)
    actual = sum(1 for t, _p in pairs if t == cls)
    return round(tp / actual, 4) if actual else 0.0


def precision(pairs: list[tuple[str, str]], cls: str) -> float:
    tp = sum(1 for t, p in pairs if t == cls and p == cls)
    predicted = sum(1 for _t, p in pairs if p == cls)
    return round(tp / predicted, 4) if predicted else 0.0


def balanced_accuracy(pairs: list[tuple[str, str]], classes: list[str]) -> float:
    present = [c for c in classes if any(t == c for t, _p in pairs)]
    return round(statistics.mean([recall(pairs, c) for c in present]), 4) if present else 0.0


def confusion(pairs: list[tuple[str, str]], classes: list[str]) -> dict[str, dict[str, int]]:
    mat = {t: {p: 0 for p in classes} for t in classes}
    for t, p in pairs:
        if t in mat and p in mat[t]:
            mat[t][p] += 1
    return mat


def classify_predictability(oos_best_acc: float, oos_majority: float,
                            oos_bal_acc: float, oos_high_recall: float) -> tuple[str, list[str]]:
    margin = round(oos_best_acc - oos_majority, 4)
    reasons = [f"OOS best acc {oos_best_acc} vs majority {oos_majority} (margin {margin})",
               f"OOS balanced acc {oos_bal_acc}", f"OOS high_de recall {oos_high_recall}"]
    # Balanced accuracy is the primary gate (random ~0.333 for 3 classes). Raw-accuracy
    # margin is unreliable when the OOS class mix is imbalanced, so it is only a
    # secondary requirement, never sufficient on its own.
    if oos_bal_acc > 0.40 and oos_high_recall > 0.30 and margin > 0.03:
        return "regime予測に価値あり", reasons
    if oos_bal_acc > 0.36 and oos_high_recall > 0.20:
        return "研究用メモ", reasons
    return "価値なし/打ち切り", reasons


# --- data plumbing --------------------------------------------------------
def _day_record(day_frame: pd.DataFrame, pip: float) -> dict:
    ms = _day_market_state(day_frame, pip)
    o = float(day_frame["open"].iloc[0])
    c = float(day_frame["close"].iloc[-1])
    ms["ret_pips"] = round((c - o) / pip, 2)
    ms["bull"] = 1 if c > o else 0
    return ms


def _collect_days(broker: GmoFxBroker, warnings: list[str]) -> list[dict]:
    """Per (window, symbol) chronological day records (DE + features-source)."""
    per_series: list[dict] = []
    for label, start, end, group in WINDOWS:
        dates = _weekdays(start, end)
        for symbol in SYMBOLS:
            candles = _fetch_candles(broker, symbol, dates, warnings)
            if not candles:
                continue
            pip = pip_size(symbol)
            frame = candles_to_frame(candles)
            frame["date"] = pd.to_datetime(frame["timestamp"]).dt.date.astype(str)
            day_records = []
            for date, day_frame in frame.groupby("date"):
                rec = _day_record(day_frame, pip)
                rec["date"] = date
                day_records.append(rec)
            day_records.sort(key=lambda r: r["date"])
            per_series.append({"window": label, "group": group, "symbol": symbol,
                               "days": day_records})
        done = sum(len(s["days"]) for s in per_series if s["window"] == label)
        print(f"{label:>13} {start}-{end} [{group}] day records={done}")
    return per_series


def main() -> int:
    broker = GmoFxBroker()
    warnings: list[str] = []
    per_series = _collect_days(broker, warnings)
    _export(per_series, warnings)
    return 0


def _label_and_rows(per_series: list[dict]) -> tuple[list[dict], float, float]:
    """Label days by prior10 DE tertiles, then build prior-only feature rows."""
    prior_des = [d["direction_efficiency"] for s in per_series if s["group"] == "prior10"
                 for d in s["days"]]
    lo, hi = de_thresholds(prior_des)
    for s in per_series:
        for d in s["days"]:
            d["de_label"] = de_bucket(d["direction_efficiency"], lo, hi)
    rows = []
    for s in per_series:
        for row in build_feature_rows(s["days"]):
            rows.append({**row, "window": s["window"], "group": s["group"], "symbol": s["symbol"]})
    return rows, lo, hi


def _eval_rule(rows: list[dict], rule: str, ctx: dict) -> dict:
    pairs = [(r["label"], predict(rule, r, ctx)) for r in rows]
    pairs = [(t, p) for t, p in pairs if p is not None]
    return {
        "n": len(pairs), "accuracy": accuracy(pairs),
        "balanced_accuracy": balanced_accuracy(pairs, CLASSES),
        "high_de_precision": precision(pairs, "high_de"),
        "high_de_recall": recall(pairs, "high_de"),
        "low_de_precision": precision(pairs, "low_de"),
        "low_de_recall": recall(pairs, "low_de"),
        "_pairs": pairs,
    }


def _export(per_series: list[dict], warnings: list[str]) -> None:
    rid = run_id("regime_predictability")
    out = EXPORT_ROOT / rid
    out.mkdir(parents=True, exist_ok=True)
    rows, lo, hi = _label_and_rows(per_series)
    prior_rows = [r for r in rows if r["group"] == "prior10"]
    oos_rows = [r for r in rows if r["group"] == "oos5"]

    # context fixed on prior10 only
    majority_label = Counter(r["label"] for r in prior_rows).most_common(1)[0][0]
    roll3_ranges = [r["roll3_range"] for r in prior_rows if r["roll3_range"] is not None]
    ctx = {"lo": lo, "hi": hi, "majority_label": majority_label,
           "range_thr": round(statistics.median(roll3_ranges), 4) if roll3_ranges else 0.0}

    by_rule, prior_results, oos_results = [], {}, {}
    for rule in RULES:
        pr, oo = _eval_rule(prior_rows, rule, ctx), _eval_rule(oos_rows, rule, ctx)
        prior_results[rule], oos_results[rule] = pr, oo
        by_rule.append({"rule": rule, "prior": pr, "oos": oo})

    # majority baseline accuracy per group (share of prior10 majority class)
    def _maj_acc(rs):
        return round(sum(1 for r in rs if r["label"] == majority_label) / len(rs), 4) if rs else 0.0
    prior_maj, oos_maj = _maj_acc(prior_rows), _maj_acc(oos_rows)

    # best OOS rule by balanced accuracy (excluding the trivial majority rule)
    ranked = sorted([r for r in RULES if r != "majority"],
                    key=lambda r: oos_results[r]["balanced_accuracy"], reverse=True)
    best = ranked[0]
    verdict, reasons = classify_predictability(
        oos_results[best]["accuracy"], oos_maj,
        oos_results[best]["balanced_accuracy"], oos_results[best]["high_de_recall"])

    _write_by_rule_csv(out / "metrics_by_rule.csv", by_rule)
    _write_window_symbol_csv(out, rows, ctx, best)
    _write_confusion(out, prior_results[best]["_pairs"], oos_results[best]["_pairs"])
    summary = _summary_dict(prior_rows, oos_rows, prior_maj, oos_maj, best, prior_results,
                            oos_results, ctx, verdict)
    (out / "metrics_regime_predictability_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2))
    (out / "warnings.json").write_text(json.dumps({
        **fixed_config(timeframe="M5", purpose="regime_predictability_diagnostic_no_trading"),
        **safety_metadata(),
        "label": "DE tertile (low/medium/high); thresholds from prior10 only, applied to oos5",
        "de_tertiles": {"low<": lo, "high>=": hi},
        "feature_rule": "features use PRIOR days only; label uses current day's OHLC",
        "no_trading": True, "no_sklearn": True,
        "note": "regime predictability diagnostic; no orders, no strategy change.",
        "fetch_warnings": warnings,
    }, ensure_ascii=False, indent=2))
    _write_manifest(out, rid, lo, hi)
    _write_summary(out, summary, by_rule, prior_maj, oos_maj)
    _write_decision(out, summary, verdict, reasons)
    print(f"\nbest OOS rule: {best} | acc {oos_results[best]['accuracy']} "
          f"vs majority {oos_maj} | bal {oos_results[best]['balanced_accuracy']}")
    print(f"VERDICT: {verdict}")
    print(f"Export written to: analysis_exports/{rid}/")


def _summary_dict(prior_rows, oos_rows, prior_maj, oos_maj, best, prior_results, oos_results,
                  ctx, verdict) -> dict:
    return {
        "prior10_rows": len(prior_rows), "oos5_rows": len(oos_rows),
        "prior10_majority_acc": prior_maj, "oos5_majority_acc": oos_maj,
        "majority_label": ctx["majority_label"],
        "best_oos_rule": best,
        "best_oos": {k: oos_results[best][k] for k in oos_results[best] if k != "_pairs"},
        "best_prior": {k: prior_results[best][k] for k in prior_results[best] if k != "_pairs"},
        "oos_margin_vs_majority": round(oos_results[best]["accuracy"] - oos_maj, 4),
        "rules": {r: {"prior_acc": prior_results[r]["accuracy"],
                      "oos_acc": oos_results[r]["accuracy"],
                      "oos_balanced_acc": oos_results[r]["balanced_accuracy"],
                      "oos_high_recall": oos_results[r]["high_de_recall"]}
                  for r in RULES},
        "de_tertiles": {"low<": ctx["lo"], "high>=": ctx["hi"]},
        "verdict": verdict,
    }


def _write_by_rule_csv(path: Path, by_rule: list[dict]) -> None:
    fields = ["n", "accuracy", "balanced_accuracy", "high_de_precision", "high_de_recall",
              "low_de_precision", "low_de_recall"]
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rule", "group", *fields])
        for r in by_rule:
            for grp in ("prior", "oos"):
                w.writerow([r["rule"], grp, *[r[grp][f] for f in fields]])


def _write_window_symbol_csv(out: Path, rows: list[dict], ctx: dict, best: str) -> None:
    def _block(keyfn, keyname, path):
        groups: dict = {}
        for r in rows:
            groups.setdefault(keyfn(r), []).append(r)
        with path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow([keyname, "n", "accuracy", "balanced_accuracy", "high_de_recall",
                        "low_de_recall"])
            for key in sorted(groups):
                res = _eval_rule(groups[key], best, ctx)
                w.writerow([key, res["n"], res["accuracy"], res["balanced_accuracy"],
                            res["high_de_recall"], res["low_de_recall"]])
    _block(lambda r: r["window"], "window", out / "metrics_by_window.csv")
    _block(lambda r: r["symbol"], "symbol", out / "metrics_by_symbol.csv")


def _write_confusion(out: Path, prior_pairs, oos_pairs) -> None:
    with (out / "confusion_matrix.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["group", "actual", *[f"pred_{c}" for c in CLASSES]])
        for grp, pairs in (("prior10", prior_pairs), ("oos5", oos_pairs)):
            mat = confusion(pairs, CLASSES)
            for actual in CLASSES:
                w.writerow([grp, actual, *[mat[actual][c] for c in CLASSES]])


def _write_manifest(out: Path, rid: str, lo: float, hi: float) -> None:
    (out / "manifest.json").write_text(json.dumps({
        "run_id": rid, "created_at": datetime.now().isoformat(),
        "kind": "gmo_public_paper_regime_predictability", "no_trading": True,
        **fixed_config(timeframe="M5", purpose="regime_predictability_diagnostic"),
        **safety_metadata(),
        "label_definition": "abs(day_close-day_open)/(day_high-day_low) -> DE tertile",
        "de_tertiles": {"low<": lo, "high>=": hi},
        "rules": RULES,
        "windows": [{"window": label, "group": g, "dates": _weekdays(s, e)}
                    for label, s, e, g in WINDOWS],
        "symbols": SYMBOLS,
    }, ensure_ascii=False, indent=2))


def _write_summary(out: Path, summary: dict, by_rule: list[dict],
                   prior_maj: float, oos_maj: float) -> None:
    rule_rows = "\n".join(
        f"| {r['rule']} | {r['prior']['accuracy']} | {r['oos']['accuracy']} | "
        f"{r['oos']['balanced_accuracy']} | {r['oos']['high_de_precision']} | "
        f"{r['oos']['high_de_recall']} | {r['oos']['low_de_precision']} | "
        f"{r['oos']['low_de_recall']} |" for r in by_rule)
    b = summary["best_oos"]
    text = (
        "# regime予測可能性診断 (当日DE区分を前日までの情報で予測できるか)\n\n"
        "GMO Public klines。**売買なし・実注文なし**・Private接続なし・APIキー未使用。"
        "ラベルは当日DEの三分位(閾値はprior10のみで決定しoos5へ固定適用)。"
        "特徴量は前日までのみ(当日OHLC不使用)。sklearn不使用。\n\n"
        "## prior10 vs oos5\n"
        "| group | 件数 | majority baseline | best rule acc | balanced acc | high_de recall "
        "| low_de recall | 判定 |\n|--|--:|--:|--:|--:|--:|--:|--|\n"
        f"| prior10 | {summary['prior10_rows']} | {prior_maj} | "
        f"{summary['best_prior']['accuracy']} | {summary['best_prior']['balanced_accuracy']} | "
        f"{summary['best_prior']['high_de_recall']} | {summary['best_prior']['low_de_recall']} "
        f"| — |\n"
        f"| oos5 | {summary['oos5_rows']} | {oos_maj} | {b['accuracy']} | "
        f"{b['balanced_accuracy']} | {b['high_de_recall']} | {b['low_de_recall']} | "
        f"{summary['verdict']} |\n\n"
        f"best OOS rule: **{summary['best_oos_rule']}** / majority class "
        f"`{summary['majority_label']}` / OOS margin {summary['oos_margin_vs_majority']}\n\n"
        "## rule別結果\n"
        "| rule | prior acc | oos acc | oos balanced | high_de prec | high_de recall "
        "| low_de prec | low_de recall |\n|--|--:|--:|--:|--:|--:|--:|--:|\n"
        + rule_rows + "\n\n"
        "ランダム相当の目安: 3クラスで accuracy≈0.333 / balanced≈0.333。\n"
        "majority/persistence/vote/threshold いずれも oos でこれを明確に超えるかが判断軸。\n"
    )
    (out / "summary.md").write_text(text)


def _write_decision(out: Path, summary: dict, verdict: str, reasons: list[str]) -> None:
    b = summary["best_oos"]
    text = (
        "# regime予測可能性 最終判断\n\n"
        f"## 判定: {verdict}\n\n"
        "### 根拠\n" + "\n".join(f"- {r}" for r in reasons) + "\n\n"
        "### 集計\n"
        f"- best OOS rule: {summary['best_oos_rule']}\n"
        f"- OOS accuracy {b['accuracy']} vs majority {summary['oos5_majority_acc']} "
        f"(margin {summary['oos_margin_vs_majority']})\n"
        f"- OOS balanced acc {b['balanced_accuracy']} / high_de recall {b['high_de_recall']} "
        f"/ low_de recall {b['low_de_recall']}\n\n"
        "### 含意\n"
        "- 価値なし/打ち切り: 前日情報で当日regimeを実用的に予測できない → 未来情報なしの "
        "no-trade/regime切替は機能しにくい。単純研究を閉じM5 rsiを研究用ベースライン保存。\n"
        "- 研究用メモ: 弱い予測力。説明用に残すが実戦略には入れない。\n"
        "- 価値あり: OOSでmajorityを明確に超える → no-trade/regime切替の検証に進む余地。\n"
    )
    (out / "regime_predictability_final_decision.md").write_text(text)


if __name__ == "__main__":
    raise SystemExit(main())
