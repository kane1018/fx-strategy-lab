"""Tests for the shared 15-window evaluation helpers (scripts/fx_eval_common.py)."""

import csv
import json
from pathlib import Path

from scripts.fx_eval_common import (
    DIAGNOSTIC_SUMMARY_REQUIRED_KEYS,
    STRATEGY_SUMMARY_REQUIRED_KEYS,
    SYMBOLS,
    WINDOWS,
    classify_strategy,
    ensure_output_dir,
    fixed_config,
    group_labels,
    run_id,
    safety_metadata,
    validate_summary_schema,
    window_groups,
    write_csv,
    write_json,
    write_manifest,
    write_markdown,
    write_metrics_csv,
    write_summary_markdown,
    write_warnings,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_standard_windows_are_10_prior_plus_5_oos() -> None:
    assert len(WINDOWS) == 15
    groups = window_groups()
    assert sum(1 for g in groups.values() if g == "prior10") == 10
    assert sum(1 for g in groups.values() if g == "oos5") == 5
    assert group_labels("oos5") == [
        "oos_window_1", "oos_window_2", "oos_window_3", "oos_window_4", "oos_window_5",
    ]
    # labels unique; each entry is (label, start, end, group)
    labels = [w[0] for w in WINDOWS]
    assert len(set(labels)) == 15
    assert all(len(w) == 4 for w in WINDOWS)


def test_fixed_config_has_standard_values_and_allows_overrides() -> None:
    config = fixed_config()
    assert config["timeframe"] == "M5"
    assert config["cost_scenario"] == "current_cost"
    assert config["spread_pips"] == 1.2
    assert config["slippage_pips"] == 0.2
    assert config["stop_loss_pips"] == 30
    assert config["take_profit_pips"] == 60
    assert config["exit_policy"] == "baseline"
    assert config["symbols"] == SYMBOLS
    assert len(config["symbols"]) == 4
    # overrides win (e.g. a runner annotating its strategy/params)
    assert fixed_config(strategy="bollinger")["strategy"] == "bollinger"
    assert fixed_config(timeframe="M15")["timeframe"] == "M15"


def test_safety_metadata_is_all_read_only() -> None:
    meta = safety_metadata()
    assert meta["real_order"] is False
    assert meta["private_api_used"] is False
    assert meta["api_key_used"] is False
    assert meta["gmo_readonly"] is True
    assert meta["gmo_order_enabled"] is False


def test_run_id_is_namespaced_and_timestamped() -> None:
    rid = run_id("demo_kind")
    assert rid.endswith("_gmo_public_paper_demo_kind")
    assert len(rid.split("_")[0]) == 8  # YYYYMMDD prefix


def test_fixed_config_and_run_id_support_m15() -> None:
    # higher-timeframe phase reuses the same helpers, overriding only timeframe
    cfg = fixed_config(timeframe="M15", strategy="rsi_reversal")
    assert cfg["timeframe"] == "M15"
    assert cfg["strategy"] == "rsi_reversal"
    assert cfg["spread_pips"] == 1.2  # cost unchanged
    assert cfg["stop_loss_pips"] == 30 and cfg["take_profit_pips"] == 60  # SL/TP unchanged
    assert run_id("rsi_m15_final15").endswith("_gmo_public_paper_rsi_m15_final15")


def test_fixed_config_records_scaled_sl_tp() -> None:
    # M15 scaled-risk confound check: SL50/TP100 must be recorded, cost unchanged
    cfg = fixed_config(timeframe="M15", strategy="rsi_reversal",
                       stop_loss_pips=50, take_profit_pips=100)
    assert cfg["stop_loss_pips"] == 50 and cfg["take_profit_pips"] == 100
    assert cfg["spread_pips"] == 1.2 and cfg["slippage_pips"] == 0.2  # cost untouched
    assert run_id("rsi_m15_scaled_final15").endswith("_gmo_public_paper_rsi_m15_scaled_final15")


def test_classify_strategy_three_way_from_common() -> None:
    base = dict(median_pf=1.3, positive_windows=8, n_windows=15, edge_windows=8,
                symbol_concentrated=False)
    keep, _ = classify_strategy(median_exp=0.2, total_pnl=50.0,
                                prior_median_exp=0.2, oos_median_exp=0.1, **base)
    assert keep == "継続検証候補"
    ref, _ = classify_strategy(median_exp=0.05, total_pnl=20.0,
                               prior_median_exp=0.12, oos_median_exp=-0.02, **base)
    assert ref == "研究用ベースライン"
    retire, _ = classify_strategy(
        median_exp=-0.02, total_pnl=-30.0, prior_median_exp=0.12, oos_median_exp=-0.02,
        median_pf=0.98, positive_windows=6, n_windows=15, edge_windows=6,
        symbol_concentrated=False)
    assert retire == "撤退"


def test_fx_docs_capture_read_only_safety_terms() -> None:
    docs = "\n".join(
        [
            (PROJECT_ROOT / "README.md").read_text(),
            (PROJECT_ROOT / "docs/fx_research_m5_summary.md").read_text(),
            (PROJECT_ROOT / "docs/fx_strategy_evaluation_protocol.md").read_text(),
        ]
    )
    for term in ["read-only paper", "Private API", "実注文", "analysis_exports"]:
        assert term in docs


# --- shared report writers (mechanism only; output must match prior inline logic) ---
def test_ensure_output_dir_creates_dir(tmp_path) -> None:
    out = ensure_output_dir(tmp_path / "run_x" / "nested")
    assert out.exists() and out.is_dir()


def test_write_json_is_indented_and_preserves_japanese(tmp_path) -> None:
    path = tmp_path / "d.json"
    data = {"判定": "研究用ベースライン", "n": 15}
    write_json(path, data)
    raw = path.read_text()
    assert "研究用ベースライン" in raw  # non-ASCII preserved (ensure_ascii=False)
    assert "\n  " in raw  # indent=2
    assert json.loads(raw) == data
    # byte-identical to the prior inline call
    assert raw == json.dumps(data, ensure_ascii=False, indent=2)


def test_write_manifest_and_warnings_keep_safety_keys(tmp_path) -> None:
    out = ensure_output_dir(tmp_path / "run")
    write_manifest(out, {"run_id": "r", **safety_metadata()})
    write_warnings(out, {"note": "x", **safety_metadata()})
    man = json.loads((out / "manifest.json").read_text())
    warn = json.loads((out / "warnings.json").read_text())
    for flags in (man, warn):
        assert flags["real_order"] is False
        assert flags["private_api_used"] is False
        assert flags["gmo_order_enabled"] is False


def test_write_csv_generic_with_fieldnames(tmp_path) -> None:
    path = tmp_path / "g.csv"
    write_csv(path, [{"a": 1, "b": 2}, {"a": 3, "b": 4}], fieldnames=["a", "b"])
    rows = list(csv.reader(path.read_text().splitlines()))
    assert rows[0] == ["a", "b"]
    assert rows[1] == ["1", "2"] and rows[2] == ["3", "4"]


def test_write_csv_empty_rows_writes_header_only(tmp_path) -> None:
    # regime by_window/by_symbol can be empty; with explicit fieldnames -> header only
    path = tmp_path / "empty.csv"
    write_csv(path, [], fieldnames=["window", "n", "accuracy"])
    rows = list(csv.reader(path.read_text().splitlines()))
    assert rows == [["window", "n", "accuracy"]]


def test_write_csv_preserves_confusion_matrix_shape(tmp_path) -> None:
    # regime confusion_matrix.csv: flat dict rows, fixed column order
    path = tmp_path / "cm.csv"
    fieldnames = ["group", "actual", "pred_low_de", "pred_medium_de", "pred_high_de"]
    rows = [{"group": "oos5", "actual": "high_de",
             "pred_low_de": 7, "pred_medium_de": 34, "pred_high_de": 4}]
    write_csv(path, rows, fieldnames)
    out = list(csv.reader(path.read_text().splitlines()))
    assert out[0] == fieldnames
    assert out[1] == ["oos5", "high_de", "7", "34", "4"]


def test_write_metrics_csv_matches_key_plus_stats_shape(tmp_path) -> None:
    path = tmp_path / "m.csv"
    rows = [{"window": "w1", "stats": {"completed_trades": 10, "win_rate": 55.0}}]
    write_metrics_csv(path, rows, ["window"], stat_fields=["completed_trades", "win_rate"])
    out_rows = list(csv.reader(path.read_text().splitlines()))
    assert out_rows[0] == ["window", "completed_trades", "win_rate"]
    assert out_rows[1] == ["w1", "10", "55.0"]


def test_write_summary_markdown(tmp_path) -> None:
    out = ensure_output_dir(tmp_path / "run")
    write_summary_markdown(out, "# 要約\n本文")
    assert (out / "summary.md").read_text() == "# 要約\n本文"


def test_write_metrics_csv_supports_tp_extended_fields(tmp_path) -> None:
    # breakout/bollinger use TP-extended stat fields; column order must be preserved
    path = tmp_path / "tp.csv"
    bk_fields = ["completed_trades", "total_pnl", "tp_count", "tp_total_pnl"]
    rows = [{"window": "w1", "group": "prior10",
             "stats": {"completed_trades": 302, "total_pnl": -80.5,
                       "tp_count": 28, "tp_total_pnl": 12.3}}]
    write_metrics_csv(path, rows, ["window", "group"], stat_fields=bk_fields)
    out_rows = list(csv.reader(path.read_text().splitlines()))
    assert out_rows[0] == ["window", "group", *bk_fields]
    assert out_rows[1] == ["w1", "prior10", "302", "-80.5", "28", "12.3"]


def test_write_markdown_writes_arbitrary_path(tmp_path) -> None:
    # final_decision系の任意ファイル名へ書ける（summary.md固定ではない）
    out = ensure_output_dir(tmp_path / "run")
    write_markdown(out / "bollinger_final_decision.md", "# 判定\n撤退")
    assert (out / "bollinger_final_decision.md").read_text() == "# 判定\n撤退"


def test_write_metrics_csv_market_state_key_order(tmp_path) -> None:
    # market-state別CSV: 単一キー列 market_state + TP拡張stat列で列順を維持
    path = tmp_path / "ms.csv"
    bk_fields = ["completed_trades", "total_pnl", "tp_count", "tp_total_pnl"]
    rows = [{"market_state": "low_de",
             "stats": {"completed_trades": 1760, "total_pnl": 80.3,
                       "tp_count": 5, "tp_total_pnl": 9.0}}]
    write_metrics_csv(path, rows, ["market_state"], stat_fields=bk_fields)
    out_rows = list(csv.reader(path.read_text().splitlines()))
    assert out_rows[0] == ["market_state", *bk_fields]
    assert out_rows[1] == ["low_de", "1760", "80.3", "5", "9.0"]


# --- summary.json schema contract -----------------------------------------
def _strategy_summary_shape() -> dict:
    """Representative strategy summary (mirrors robustness_summary + _build_summary)."""
    return {
        "window_count": 15, "median_expectancy": 0.0164, "median_pf": 1.016,
        "positive_windows": 8, "negative_windows": 7, "edge_windows": 8,
        "windows_ge30_trades": 15, "max_drawdown_max": 65.46, "worst_single_loss": -3.14,
        "total_pnl": 56.95, "group_prior10": {"label": "prior10"},
        "group_oos5": {"label": "oos5"}, "symbol_pnl": {}, "verdict": "研究用ベースライン",
    }


def _diagnostic_summary_shape() -> dict:
    """Representative regime diagnostic summary (mirrors _summary_dict)."""
    return {
        "prior10_rows": 440, "oos5_rows": 220, "best_oos_rule": "roll3_de_bucket",
        "best_oos": {"accuracy": 0.38}, "oos5_majority_acc": 0.25,
        "oos_margin_vs_majority": 0.1333, "rules": {}, "verdict": "価値なし/打ち切り",
    }


def test_strategy_summary_shape_satisfies_contract() -> None:
    # presence-only contract; representative real shape must pass unchanged
    validate_summary_schema(_strategy_summary_shape())


def test_diagnostic_summary_shape_satisfies_contract() -> None:
    validate_summary_schema(_diagnostic_summary_shape(), DIAGNOSTIC_SUMMARY_REQUIRED_KEYS)


def test_validate_summary_schema_reports_missing_keys() -> None:
    summary = _strategy_summary_shape()
    del summary["total_pnl"]
    del summary["verdict"]
    try:
        validate_summary_schema(summary)
    except ValueError as exc:
        assert "total_pnl" in str(exc) and "verdict" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing required keys")


def test_validate_summary_schema_presence_only_allows_none_and_empty() -> None:
    # None values and empty verdict are allowed (presence-only, not value validation)
    summary = {k: None for k in STRATEGY_SUMMARY_REQUIRED_KEYS}
    summary["verdict"] = ""
    validate_summary_schema(summary)


def test_validate_summary_schema_allows_extra_runner_specific_keys() -> None:
    summary = {**_strategy_summary_shape(), "complement_vs_rsi": {}, "de_tertiles": {}}
    validate_summary_schema(summary)


def test_validate_summary_schema_rejects_non_mapping() -> None:
    try:
        validate_summary_schema(["not", "a", "mapping"])
    except ValueError as exc:
        assert "mapping" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-mapping summary")


def test_strategy_and_diagnostic_schemas_differ_but_share_verdict() -> None:
    assert "verdict" in STRATEGY_SUMMARY_REQUIRED_KEYS
    assert "verdict" in DIAGNOSTIC_SUMMARY_REQUIRED_KEYS
    assert set(STRATEGY_SUMMARY_REQUIRED_KEYS) != set(DIAGNOSTIC_SUMMARY_REQUIRED_KEYS)
