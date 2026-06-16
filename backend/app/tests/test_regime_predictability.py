"""Tests for regime predictability diagnostic helpers (no network, no trading)."""

from scripts.regime_predictability_diagnostics import (
    accuracy,
    balanced_accuracy,
    build_feature_rows,
    classify_predictability,
    confusion,
    precision,
    recall,
)


def _day(de: float, label: str, rng: float = 50.0) -> dict:
    return {"direction_efficiency": de, "daily_range_pips": rng, "atr_equiv_pips": 5.0,
            "reversals": 100, "cost_ratio": 30.0, "ret_pips": 1.0, "bull": 1,
            "de_label": label, "date": f"2026-01-{int(de * 100):02d}"}


def test_feature_rows_use_only_prior_days() -> None:
    days = [_day(0.2, "low_de"), _day(0.5, "medium_de"), _day(0.8, "high_de")]
    rows = build_feature_rows(days)
    assert len(rows) == 2  # first day dropped (no prior)
    # row for day index 1: label is TODAY (medium), prev_* is YESTERDAY (the 0.2 low day)
    assert rows[0]["label"] == "medium_de"
    assert rows[0]["prev_de"] == 0.2
    assert rows[0]["prev_de_label"] == "low_de"
    # row for day index 2: label high (today), prev is the medium day
    assert rows[1]["label"] == "high_de"
    assert rows[1]["prev_de"] == 0.5
    # no feature key leaks the current day's DE (0.8 / 0.5)
    feature_vals = [v for k, v in rows[1].items() if k.startswith("prev")]
    assert 0.8 not in feature_vals  # today's DE never appears in features


def test_classification_metrics() -> None:
    pairs = [("low_de", "low_de"), ("low_de", "high_de"),
             ("high_de", "high_de"), ("high_de", "high_de")]
    assert accuracy(pairs) == 0.75
    assert recall(pairs, "high_de") == 1.0  # both actual-high predicted high
    assert recall(pairs, "low_de") == 0.5   # 1 of 2 actual-low correct
    assert precision(pairs, "high_de") == round(2 / 3, 4)  # 2 correct of 3 predicted high
    # balanced acc = mean(recall low, recall high) over present classes = mean(0.5, 1.0)
    assert balanced_accuracy(pairs, ["low_de", "medium_de", "high_de"]) == 0.75


def test_confusion_matrix_counts() -> None:
    pairs = [("low_de", "low_de"), ("low_de", "high_de"), ("high_de", "high_de")]
    mat = confusion(pairs, ["low_de", "medium_de", "high_de"])
    assert mat["low_de"]["low_de"] == 1
    assert mat["low_de"]["high_de"] == 1
    assert mat["high_de"]["high_de"] == 1
    assert mat["medium_de"]["medium_de"] == 0


def test_classify_predictability_three_way() -> None:
    keep, _ = classify_predictability(oos_best_acc=0.55, oos_majority=0.40,
                                      oos_bal_acc=0.52, oos_high_recall=0.45)
    assert keep == "regime予測に価値あり"
    memo, _ = classify_predictability(oos_best_acc=0.43, oos_majority=0.40,
                                      oos_bal_acc=0.37, oos_high_recall=0.25)
    assert memo == "研究用メモ"
    # raw-accuracy margin alone is NOT enough: balanced acc ~random -> 打ち切り
    drop, _ = classify_predictability(oos_best_acc=0.38, oos_majority=0.25,
                                      oos_bal_acc=0.32, oos_high_recall=0.09)
    assert drop == "価値なし/打ち切り"
