"""Tests for the shared 15-window evaluation helpers (scripts/fx_eval_common.py)."""

import csv
import json
from pathlib import Path

from scripts.fx_eval_common import (
    DIAGNOSTIC_SUMMARY_REQUIRED_KEYS,
    REPORT_DETAIL_REQUIRED_KEYS,
    REPORT_INDEX_ERROR_REQUIRED_KEYS,
    REPORT_INDEX_REQUIRED_KEYS,
    REPORT_INDEX_SAFETY_KEYS,
    STRATEGY_SUMMARY_REQUIRED_KEYS,
    SYMBOLS,
    WINDOWS,
    classify_strategy,
    ensure_output_dir,
    fixed_config,
    format_report_detail_markdown,
    format_report_index_markdown,
    group_labels,
    list_report_index,
    report_detail,
    report_index_entry,
    run_id,
    safety_metadata,
    validate_report_detail,
    validate_report_index_row,
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


# --- report index entry (read-only metadata for a future report-list UI) ----------
def _write_run(tmp_path, manifest=None, warnings=None, summaries=None):
    run = ensure_output_dir(tmp_path / "20260101_000000_gmo_public_paper_demo")
    if manifest is not None:
        write_json(run / "manifest.json", manifest)
    if warnings is not None:
        write_json(run / "warnings.json", warnings)
    for name, body in (summaries or {}).items():
        write_json(run / name, body)
    return run


def _safe_manifest() -> dict:
    return {"run_id": "20260101_000000_gmo_public_paper_demo", "kind": "gmo_public_paper_x",
            "strategy": "rsi_reversal", "timeframe": "M5", "cost_scenario": "current_cost",
            "spread_pips": 1.2, "slippage_pips": 0.2, "stop_loss_pips": 30,
            "take_profit_pips": 60, "created_at": "2026-01-01T00:00:00", **safety_metadata()}


def _strategy_summary_json() -> dict:
    return {"verdict": "撤退", "median_expectancy": -0.01, "median_pf": 0.9,
            "total_pnl": -5.0, "max_drawdown_max": 12.3, "window_count": 15}


def test_report_index_entry_minimal_strategy(tmp_path) -> None:
    run = _write_run(tmp_path, _safe_manifest(), {"fetch_warnings": []},
                     {"metrics_x_15window_summary.json": _strategy_summary_json()})
    entry = report_index_entry(run)
    assert all(k in entry for k in REPORT_INDEX_REQUIRED_KEYS)
    assert entry["kind"] == "gmo_public_paper_x"
    assert entry["strategy"] == "rsi_reversal"
    assert entry["cost_scenario"] == "current_cost" and entry["timeframe"] == "M5"
    assert entry["verdict"] == "撤退" and entry["median_pf"] == 0.9
    assert entry["read_only_confirmed"] is True and entry["safety_complete"] is True
    assert entry["warnings_count"] == 0 and entry["has_warnings"] is False
    assert entry["summary_file"] == "metrics_x_15window_summary.json"


def test_report_index_entry_no_summary_raises(tmp_path) -> None:
    run = _write_run(tmp_path, _safe_manifest(), {"fetch_warnings": []})
    try:
        report_index_entry(run)
    except FileNotFoundError as exc:
        assert "summary" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError when no summary exists")


def test_report_index_entry_multiple_summaries_raises(tmp_path) -> None:
    run = _write_run(tmp_path, _safe_manifest(), {"fetch_warnings": []},
                     {"metrics_a_15window_summary.json": _strategy_summary_json(),
                      "metrics_b_15window_summary.json": _strategy_summary_json()})
    try:
        report_index_entry(run)
    except ValueError as exc:
        assert "multiple" in str(exc)
    else:
        raise AssertionError("expected ValueError for multiple summary files")


def test_report_index_entry_missing_safety_not_optimistic(tmp_path) -> None:
    # older strategy runner: manifest has only 3 of 6 safety flags -> not confirmed
    manifest = {k: v for k, v in _safe_manifest().items()
                if k not in ("real_order", "private_api_used", "api_key_used")}
    run = _write_run(tmp_path, manifest, {"fetch_warnings": []},
                     {"metrics_x_15window_summary.json": _strategy_summary_json()})
    entry = report_index_entry(run)
    assert entry["read_only_confirmed"] is False  # unknown is never optimistic
    assert entry["safety_complete"] is False
    assert entry["safety"]["real_order"] is None


def test_report_index_entry_safety_conflict_detected(tmp_path) -> None:
    manifest = {**_safe_manifest(), "real_order": False}
    warnings = {"fetch_warnings": [], "real_order": True}  # disagree with manifest
    run = _write_run(tmp_path, manifest, warnings,
                     {"metrics_x_15window_summary.json": _strategy_summary_json()})
    entry = report_index_entry(run)
    assert "real_order" in entry["safety_conflicts"]
    assert entry["read_only_confirmed"] is False


def test_report_index_entry_counts_warnings(tmp_path) -> None:
    run = _write_run(tmp_path, _safe_manifest(),
                     {"fetch_warnings": ["2026-01-01 missing", "2025-12-25 missing"]},
                     {"metrics_x_15window_summary.json": _strategy_summary_json()})
    entry = report_index_entry(run)
    assert entry["warnings_count"] == 2 and entry["has_warnings"] is True


def test_report_index_entry_diagnostic_summary(tmp_path) -> None:
    # regime diagnostic summary lacks median_expectancy/total_pnl -> None, still builds
    manifest = {**_safe_manifest(), "kind": "gmo_public_paper_regime_predictability",
                "strategy": None}
    diag = {"verdict": "価値なし/打ち切り", "best_oos_rule": "roll3_de_bucket",
            "best_oos": {}, "oos5_majority_acc": 0.25, "oos_margin_vs_majority": 0.13}
    run = _write_run(tmp_path, manifest, {"fetch_warnings": []},
                     {"metrics_regime_predictability_summary.json": diag})
    entry = report_index_entry(run)
    assert entry["verdict"] == "価値なし/打ち切り"
    assert entry["median_expectancy"] is None and entry["total_pnl"] is None
    assert entry["read_only_confirmed"] is True


def test_report_index_entry_run_id_falls_back_to_dirname(tmp_path) -> None:
    # no manifest -> run_id from dir name, metadata None, safety not confirmed
    run = _write_run(tmp_path, None, {"fetch_warnings": []},
                     {"metrics_x_15window_summary.json": _strategy_summary_json()})
    entry = report_index_entry(run)
    assert entry["run_id"] == "20260101_000000_gmo_public_paper_demo"
    assert entry["kind"] is None and entry["read_only_confirmed"] is False


# --- completed safety metadata in older strategy-runner manifests -----------------
def test_safety_metadata_covers_all_report_index_keys() -> None:
    meta = safety_metadata()
    assert set(REPORT_INDEX_SAFETY_KEYS) <= set(meta)  # all 6 index flags present
    assert meta == {"real_order": False, "private_api_used": False, "api_key_used": False,
                    "gmo_readonly": True, "gmo_order_enabled": False,
                    "no_order_execution": True}


def test_report_index_confirms_completed_older_runner_manifest(tmp_path) -> None:
    # what rsi_final/breakout/bollinger/market_structure manifests now emit:
    # legacy keys come from **safety_metadata(), so all 6 flags are present.
    manifest = {"run_id": "20260101_000000_gmo_public_paper_rsi_final15",
                "kind": "gmo_public_paper_rsi_final15", "strategy": "rsi_reversal",
                "timeframe": "M5", "cost_scenario": "current_cost", "spread_pips": 1.2,
                "slippage_pips": 0.2, "stop_loss_pips": 30, "take_profit_pips": 60,
                "created_at": "2026-01-01T00:00:00", "symbols": ["USD_JPY"],
                "continuous_replay": True, **safety_metadata()}
    # older runners' warnings.json carries no safety flags (only data warnings)
    warnings = {"data_source": "x", "fixed_config": "y", "fetch_warnings": []}
    run = _write_run(tmp_path, manifest, warnings,
                     {"metrics_15window_summary.json": _strategy_summary_json()})
    entry = report_index_entry(run)
    assert entry["safety_complete"] is True
    assert entry["read_only_confirmed"] is True
    assert entry["safety_conflicts"] == []
    # legacy 3 keys preserved at their original values
    assert entry["safety"]["no_order_execution"] is True
    assert entry["safety"]["gmo_readonly"] is True
    assert entry["safety"]["gmo_order_enabled"] is False
    # the 3 newly-completed keys
    assert entry["safety"]["real_order"] is False
    assert entry["safety"]["private_api_used"] is False
    assert entry["safety"]["api_key_used"] is False


# --- list_report_index (read-only multi-run listing for a future report UI) -------
def _make_run(root, name, created_at="2026-01-01T00:00:00", *, n_summary=1,
              bad_manifest=False):
    run = ensure_output_dir(root / name)
    if bad_manifest:
        (run / "manifest.json").write_text("{ not valid json ")
    else:
        write_json(run / "manifest.json", {"run_id": name, "kind": "k", "strategy": "s",
                                           "timeframe": "M5", "cost_scenario": "current_cost",
                                           "created_at": created_at, **safety_metadata()})
    write_json(run / "warnings.json", {"fetch_warnings": []})
    for i in range(n_summary):
        write_json(run / f"metrics_{i}_15window_summary.json", _strategy_summary_json())
    return run


def test_list_report_index_sorts_by_created_at_desc(tmp_path) -> None:
    _make_run(tmp_path, "run_a", "2026-01-01T00:00:00")
    _make_run(tmp_path, "run_c", "2026-03-01T00:00:00")
    _make_run(tmp_path, "run_b", "2026-02-01T00:00:00")
    rows = list_report_index(tmp_path)
    assert [r["run_id"] for r in rows] == ["run_c", "run_b", "run_a"]
    assert all(r["has_error"] is False for r in rows)


def test_list_report_index_ignores_files_and_hidden_dirs(tmp_path) -> None:
    _make_run(tmp_path, "run_a")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "note.txt").write_text("x")
    (tmp_path / ".DS_Store").write_text("")
    rows = list_report_index(tmp_path)
    assert [r["run_id"] for r in rows] == ["run_a"]


def test_list_report_index_no_summary_becomes_error_row(tmp_path) -> None:
    _make_run(tmp_path, "ok_run", "2026-02-01T00:00:00")
    _make_run(tmp_path, "broken_run", n_summary=0)  # no summary file
    rows = list_report_index(tmp_path)
    ok = [r for r in rows if r["run_id"] == "ok_run"][0]
    broken = [r for r in rows if r["run_id"] == "broken_run"][0]
    assert ok["has_error"] is False  # one bad run does not drop the good ones
    assert broken["has_error"] is True
    assert broken["read_only_confirmed"] is False
    assert broken["created_at"] is None and broken["summary_file"] is None
    assert "summary" in broken["error"]
    assert rows[-1]["run_id"] == "broken_run"  # error rows sort last


def test_list_report_index_multiple_summary_becomes_error_row(tmp_path) -> None:
    _make_run(tmp_path, "dup_run", n_summary=2)
    rows = list_report_index(tmp_path)
    assert rows[0]["has_error"] is True and "multiple" in rows[0]["error"]


def test_list_report_index_json_parse_error_row(tmp_path) -> None:
    _make_run(tmp_path, "bad_json", bad_manifest=True)
    rows = list_report_index(tmp_path)
    assert rows[0]["has_error"] is True and rows[0]["run_id"] == "bad_json"


def test_list_report_index_missing_root_raises(tmp_path) -> None:
    try:
        list_report_index(tmp_path / "does_not_exist")
    except FileNotFoundError as exc:
        assert "exports_root" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError for missing exports_root")


def test_list_report_index_empty_root_returns_empty(tmp_path) -> None:
    assert list_report_index(tmp_path) == []


def test_list_report_index_orders_created_then_nocreated_then_error(tmp_path) -> None:
    _make_run(tmp_path, "has_created", "2026-05-01T00:00:00")
    # normal run but manifest missing -> created_at None (still not an error)
    nocreated = ensure_output_dir(tmp_path / "no_created")
    write_json(nocreated / "warnings.json", {"fetch_warnings": []})
    write_json(nocreated / "metrics_0_15window_summary.json", _strategy_summary_json())
    _make_run(tmp_path, "broken", n_summary=0)
    rows = list_report_index(tmp_path)
    order = [r["run_id"] for r in rows]
    assert order == ["has_created", "no_created", "broken"]
    assert rows[1]["created_at"] is None and rows[1]["has_error"] is False


# --- format_report_index_markdown (render report-index rows for humans/ChatGPT) ---
def _ok_row(**over):
    row = {
        "run_id": "20260101_000000_gmo_public_paper_rsi",
        "kind": "rsi_final15", "strategy": "rsi_reversal", "timeframe": "M5",
        "cost_scenario": "current_cost", "verdict": "研究用ベースライン",
        "median_expectancy": 0.123456, "median_pf": 1.23456, "total_pnl": 123.456,
        "max_drawdown_max": -45.678, "created_at": "2026-01-01T00:00:00",
        "summary_file": "metrics_rsi_15window_summary.json",
        "safety": {k: False for k in REPORT_INDEX_SAFETY_KEYS},
        "safety_complete": True, "safety_conflicts": [], "read_only_confirmed": True,
        "warnings_count": 0, "has_warnings": False, "has_error": False,
    }
    row.update(over)
    return row


def _err_row(**over):
    row = {
        "run_id": "broken_run", "error": "no metrics_*_summary.json found",
        "has_error": True, "read_only_confirmed": False, "created_at": None,
        "summary_file": None,
    }
    row.update(over)
    return row


def _data_rows(md):
    return md.splitlines()[2:]  # skip header + separator


def _cells(line):
    return [c.strip() for c in line.strip("|").split("|")]


def test_format_report_index_empty_returns_header_only() -> None:
    md = format_report_index_markdown([])
    lines = md.splitlines()
    assert len(lines) == 2  # header + separator, no data rows
    assert lines[0].startswith("| status | run_id |")
    assert set(lines[1].replace(" ", "").split("|")) <= {"", "---"}
    assert not md.endswith("\n")  # no trailing newline


def test_format_report_index_ok_row() -> None:
    md = format_report_index_markdown([_ok_row()])
    body = _data_rows(md)
    assert len(body) == 1
    cells = _cells(body[0])
    assert cells[0] == "OK"
    assert cells[1] == "20260101_000000_gmo_public_paper_rsi"
    assert cells[7] == "0.1235"   # expectancy 4dp (rounded)
    assert cells[8] == "1.235"    # pf 3dp
    assert cells[9] == "123.46"   # total_pnl 2dp
    assert cells[10] == "-45.68"  # max_dd 2dp
    assert cells[11] == "read-only"
    assert cells[12] == "0"       # warnings
    assert cells[-1] == "-"       # error empty


def test_format_report_index_preserves_row_order() -> None:
    rows = [_ok_row(run_id="a"), _ok_row(run_id="b"), _ok_row(run_id="c")]
    md = format_report_index_markdown(rows)
    ids = [_cells(line)[1] for line in _data_rows(md)]
    assert ids == ["a", "b", "c"]


def test_format_report_index_error_row_status() -> None:
    cells = _cells(_data_rows(format_report_index_markdown([_err_row()]))[0])
    assert cells[0] == "ERROR"
    assert cells[1] == "broken_run"
    assert cells[11] == "-"  # safety
    assert cells[12] == "-"  # warnings
    assert "summary" in cells[-1]  # error message shown


def test_format_report_index_unconfirmed_status() -> None:
    cells = _cells(_data_rows(
        format_report_index_markdown([_ok_row(read_only_confirmed=False)]))[0])
    assert cells[0] == "UNCONFIRMED"
    assert cells[11] == "unconfirmed"


def test_format_report_index_conflict_status() -> None:
    row = _ok_row(read_only_confirmed=False,
                  safety_conflicts=["real_order", "gmo_readonly"])
    cells = _cells(_data_rows(format_report_index_markdown([row]))[0])
    assert cells[0] == "CONFLICT"
    assert cells[11] == "conflict:real_order,gmo_readonly"


def test_format_report_index_warn_status_when_data_warnings() -> None:
    cells = _cells(_data_rows(format_report_index_markdown(
        [_ok_row(warnings_count=2, has_warnings=True)]))[0])
    assert cells[0] == "WARN"
    assert cells[12] == "2"


def test_format_report_index_none_and_missing_become_dash() -> None:
    row = _ok_row(verdict=None, median_expectancy=None, median_pf=None,
                  total_pnl=None, max_drawdown_max=None, created_at=None, strategy="")
    row.pop("kind")  # missing key entirely
    cells = _cells(_data_rows(format_report_index_markdown([row]))[0])
    assert cells[2] == "-"   # kind missing
    assert cells[3] == "-"   # strategy empty string
    assert cells[6] == "-"   # verdict None
    assert cells[7] == "-" and cells[8] == "-"
    assert cells[9] == "-" and cells[10] == "-"
    assert cells[13] == "-"  # created_at None


def test_format_report_index_escapes_pipe_and_newline() -> None:
    row = _ok_row(strategy="a|b", verdict="line1\nline2")
    line = _data_rows(format_report_index_markdown([row]))[0]
    assert r"a\|b" in line             # pipe escaped
    assert "line1 line2" in line       # newline collapsed to space
    assert len(_data_rows(format_report_index_markdown([row]))) == 1  # still 1 row


def test_format_report_index_diagnostic_row_with_none_numerics() -> None:
    # regime diagnostic rows carry a verdict but no strategy headline metrics
    row = _ok_row(kind="regime_diag", strategy="regime_predictability",
                  median_expectancy=None, median_pf=None, total_pnl=None,
                  max_drawdown_max=None, verdict="予測可能性=低")
    cells = _cells(_data_rows(format_report_index_markdown([row]))[0])
    assert cells[0] == "OK"
    assert cells[7] == "-" and cells[8] == "-"
    assert cells[9] == "-" and cells[10] == "-"


# --- validate_report_index_row (presence-only contract for report-index rows) ------
def test_validate_report_index_row_passes_on_complete_normal_row() -> None:
    validate_report_index_row(_ok_row())  # no raise


def test_validate_report_index_row_missing_key_raises_with_name() -> None:
    row = _ok_row()
    del row["verdict"]
    try:
        validate_report_index_row(row)
    except ValueError as exc:
        assert "verdict" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing key")


def test_validate_report_index_row_allows_extra_keys() -> None:
    validate_report_index_row(_ok_row(extra="anything", debug=123))  # no raise


def test_validate_report_index_row_allows_none_and_empty_values() -> None:
    # presence-only: None / "" are valid as long as the key exists
    row = _ok_row(verdict=None, strategy="", median_expectancy=None)
    validate_report_index_row(row)  # no raise


def test_validate_report_index_row_rejects_non_mapping() -> None:
    for bad in (["run_id"], "run_id", 42, None):
        try:
            validate_report_index_row(bad)
        except ValueError as exc:
            assert "mapping" in str(exc)
        else:
            raise AssertionError(f"expected ValueError for non-mapping: {bad!r}")


def test_validate_report_index_row_error_schema_passes() -> None:
    validate_report_index_row(_err_row(), REPORT_INDEX_ERROR_REQUIRED_KEYS)  # no raise


def test_validate_report_index_row_error_schema_missing_key_raises() -> None:
    row = _err_row()
    del row["error"]
    try:
        validate_report_index_row(row, REPORT_INDEX_ERROR_REQUIRED_KEYS)
    except ValueError as exc:
        assert "error" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing error-row key")


def test_validate_report_index_row_safety_conflict_and_diagnostic_rows_pass() -> None:
    conflict = _ok_row(read_only_confirmed=False,
                       safety_conflicts=["real_order"])
    diag = _ok_row(kind="regime_diag", strategy="regime_predictability",
                   median_expectancy=None, median_pf=None, total_pnl=None,
                   max_drawdown_max=None, verdict="予測可能性=低")
    validate_report_index_row(conflict)
    validate_report_index_row(diag)


def test_list_report_index_rows_satisfy_their_contracts(tmp_path) -> None:
    _make_run(tmp_path, "ok_run", "2026-02-01T00:00:00")
    _make_run(tmp_path, "broken_run", n_summary=0)  # -> error row
    rows = list_report_index(tmp_path)
    for row in rows:
        if row["has_error"]:
            validate_report_index_row(row, REPORT_INDEX_ERROR_REQUIRED_KEYS)
        else:
            validate_report_index_row(row)


def test_report_index_entry_output_satisfies_required_keys(tmp_path) -> None:
    run = _make_run(tmp_path, "entry_run", "2026-02-01T00:00:00")
    validate_report_index_row(report_index_entry(run))  # entry-level contract


def test_formatter_still_tolerates_rows_that_fail_validation() -> None:
    # the formatter must stay lenient even on a row the validator would reject
    sparse = {"run_id": "sparse", "has_error": False}
    try:
        validate_report_index_row(sparse)
    except ValueError:
        pass
    else:
        raise AssertionError("expected sparse row to fail validation")
    md = format_report_index_markdown([sparse])  # must NOT raise
    assert "sparse" in md


# --- report_detail (read-only single-run detail data for a future run-detail UI) ---
def _make_detail_run(root, name="detail_run", *, with_md=True, n_summary=1):
    run = _make_run(root, name, "2026-02-01T00:00:00", n_summary=n_summary)
    (run / "metrics_by_window.csv").write_text("window,n,accuracy\nw1,30,0.55\n")
    (run / "metrics_by_symbol.csv").write_text("symbol,n\nUSD_JPY,40\n")
    (run / ".DS_Store").write_text("junk")  # hidden -> ignored
    if with_md:
        (run / "summary.md").write_text("# Summary\n研究用ベースライン\n", encoding="utf-8")
        (run / "rsi_final_decision.md").write_text("# 判定\n継続検証候補\n", encoding="utf-8")
    return run


def test_report_detail_builds_from_normal_run(tmp_path) -> None:
    run = _make_detail_run(tmp_path)
    detail = report_detail(run)
    validate_report_detail(detail)  # no raise
    for key in REPORT_DETAIL_REQUIRED_KEYS:
        assert key in detail
    assert detail["run_id"] == "detail_run"
    assert detail["run_dir"] == str(run)
    assert isinstance(detail["index"], dict) and detail["index"]["run_id"] == "detail_run"
    assert isinstance(detail["manifest"], dict) and detail["manifest"]["kind"] == "k"
    assert isinstance(detail["warnings"], dict)
    assert isinstance(detail["summary"], dict) and "verdict" in detail["summary"]
    assert detail["summary_file"] == "metrics_0_15window_summary.json"


def test_report_detail_classifies_and_lists_files(tmp_path) -> None:
    run = _make_detail_run(tmp_path)
    detail = report_detail(run)
    names = {f["name"] for f in detail["files"]}
    assert ".DS_Store" not in names  # hidden ignored
    assert {"manifest.json", "warnings.json", "metrics_by_window.csv"} <= names
    # every file entry carries name / kind / size_bytes, size read from stat (not body)
    for f in detail["files"]:
        assert set(f) == {"name", "kind", "size_bytes"}
        assert isinstance(f["size_bytes"], int) and f["size_bytes"] >= 0
    assert "metrics_0_15window_summary.json" in detail["metrics_files"]
    assert "metrics_by_window.csv" in detail["csv_files"]
    assert "metrics_by_symbol.csv" in detail["csv_files"]
    assert "summary.md" in detail["markdown_files"]
    kinds = {f["name"]: f["kind"] for f in detail["files"]}
    assert kinds["manifest.json"] == "json"
    assert kinds["metrics_by_window.csv"] == "csv"
    assert kinds["summary.md"] == "markdown"


def test_report_detail_does_not_read_csv_body(tmp_path) -> None:
    run = _make_detail_run(tmp_path)
    detail = report_detail(run)
    # CSVs appear only as file metadata; no key holds their text content
    assert "USD_JPY" not in json.dumps(detail, ensure_ascii=False, default=str)


def test_report_detail_reads_small_markdown_bodies(tmp_path) -> None:
    run = _make_detail_run(tmp_path)
    detail = report_detail(run)
    assert detail["summary_markdown_file"] == "summary.md"
    assert detail["summary_markdown"] is not None
    assert "研究用ベースライン" in detail["summary_markdown"]
    assert detail["final_decision_file"] == "rsi_final_decision.md"
    assert "継続検証候補" in detail["final_decision_markdown"]


def test_report_detail_markdown_absent_keeps_keys_none(tmp_path) -> None:
    run = _make_detail_run(tmp_path, with_md=False)
    detail = report_detail(run)
    assert detail["summary_markdown_file"] is None
    assert detail["summary_markdown"] is None
    assert detail["final_decision_file"] is None
    assert detail["final_decision_markdown"] is None
    validate_report_detail(detail)  # still valid (md keys are not required)


def test_report_detail_missing_run_dir_raises(tmp_path) -> None:
    try:
        report_detail(tmp_path / "nope")
    except FileNotFoundError as exc:
        assert "run_dir" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError for missing run_dir")


def test_report_detail_no_summary_raises(tmp_path) -> None:
    run = _make_run(tmp_path, "no_sum", n_summary=0)
    try:
        report_detail(run)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError when no summary JSON")


def test_report_detail_multiple_summary_raises(tmp_path) -> None:
    run = _make_run(tmp_path, "dup", n_summary=2)
    try:
        report_detail(run)
    except ValueError as exc:
        assert "multiple" in str(exc)
    else:
        raise AssertionError("expected ValueError for multiple summary JSON")


def test_report_detail_diagnostic_and_conflict_runs_build(tmp_path) -> None:
    diag = ensure_output_dir(tmp_path / "regime")
    write_json(diag / "manifest.json", {"run_id": "regime", "kind": "regime_diag",
                                        "strategy": "regime_predictability", "timeframe": "M5",
                                        "cost_scenario": "current_cost",
                                        "created_at": "2026-02-02T00:00:00", **safety_metadata()})
    write_json(diag / "warnings.json", {"fetch_warnings": []})
    write_json(diag / "metrics_regime_summary.json", _diagnostic_summary_shape())
    validate_report_detail(report_detail(diag))  # diagnostic run

    conflict = ensure_output_dir(tmp_path / "conflict")
    write_json(conflict / "manifest.json", {"run_id": "conflict", "kind": "k", "strategy": "s",
                                            "timeframe": "M5", "cost_scenario": "current_cost",
                                            "created_at": "2026-02-03T00:00:00",
                                            **safety_metadata()})
    # warnings disagree on a safety flag -> safety_conflicts in index, still buildable
    write_json(conflict / "warnings.json", {"fetch_warnings": [], "real_order": True})
    write_json(conflict / "metrics_0_15window_summary.json", _strategy_summary_json())
    detail = report_detail(conflict)
    validate_report_detail(detail)
    assert detail["index"]["safety_conflicts"]  # conflict surfaced via index


def test_validate_report_detail_missing_key_raises_with_name() -> None:
    detail = {k: None for k in REPORT_DETAIL_REQUIRED_KEYS}
    del detail["summary"]
    try:
        validate_report_detail(detail)
    except ValueError as exc:
        assert "summary" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing key")


def test_validate_report_detail_rejects_non_mapping_and_allows_extras() -> None:
    for bad in (["x"], "x", 7, None):
        try:
            validate_report_detail(bad)
        except ValueError as exc:
            assert "mapping" in str(exc)
        else:
            raise AssertionError(f"expected ValueError for non-mapping: {bad!r}")
    ok = {k: None for k in REPORT_DETAIL_REQUIRED_KEYS}
    ok["extra"] = "anything"
    validate_report_detail(ok)  # extras allowed, None values allowed


# --- format_report_detail_markdown (render one run's detail for humans/ChatGPT) -----
def _full_detail(**over):
    index = {
        "run_id": "20260201_000000_gmo_public_paper_rsi", "kind": "rsi_final15",
        "strategy": "rsi_reversal", "timeframe": "M5", "cost_scenario": "current_cost",
        "spread_pips": 1.2, "slippage_pips": 0.2, "stop_loss_pips": 30,
        "take_profit_pips": 60, "verdict": "研究用ベースライン",
        "median_expectancy": 0.0821, "median_pf": 1.143, "total_pnl": 312.4,
        "max_drawdown_max": -88.2, "created_at": "2026-02-01T00:00:00",
        "summary_file": "metrics_0_15window_summary.json",
        "safety": {k: (k in ("gmo_readonly", "no_order_execution"))
                   for k in REPORT_INDEX_SAFETY_KEYS},
        "safety_complete": True, "safety_conflicts": [], "read_only_confirmed": True,
        "warnings_count": 0, "has_warnings": False,
    }
    summary = {
        "window_count": 15, "median_expectancy": 0.0821, "median_pf": 1.143,
        "positive_windows": 9, "negative_windows": 6, "total_pnl": 312.4,
        "max_drawdown_max": -88.2, "group_prior10": {"median_expectancy": 0.1},
        "group_oos5": {"median_expectancy": 0.05}, "verdict": "研究用ベースライン",
    }
    detail = {
        "run_id": "20260201_000000_gmo_public_paper_rsi",
        "run_dir": "/x/run", "index": index, "manifest": {"run_id": "x"},
        "warnings": {"fetch_warnings": []}, "summary": summary,
        "summary_file": "metrics_0_15window_summary.json",
        "summary_markdown_file": "summary.md",
        "summary_markdown": "# Summary\n研究用ベースライン\n",
        "final_decision_file": "rsi_final_decision.md",
        "final_decision_markdown": "# 判定\n継続検証候補\n",
        "files": [
            {"name": "manifest.json", "kind": "json", "size_bytes": 512},
            {"name": "metrics_by_window.csv", "kind": "csv", "size_bytes": 2048},
            {"name": "summary.md", "kind": "markdown", "size_bytes": 256},
        ],
        "metrics_files": ["metrics_0_15window_summary.json"],
        "csv_files": ["metrics_by_window.csv"], "markdown_files": ["summary.md"],
    }
    detail.update(over)
    return detail


def _section(md, title):
    # return the lines belonging to "## <title>" up to the next "## " heading
    lines = md.splitlines()
    start = lines.index(f"## {title}")
    rest = lines[start + 1:]
    end = next((i for i, ln in enumerate(rest) if ln.startswith("## ")), len(rest))
    return rest[:end]


def test_format_report_detail_has_all_sections_and_title() -> None:
    md = format_report_detail_markdown(_full_detail())
    assert md.startswith("# FX Report Detail: 20260201_000000_gmo_public_paper_rsi")
    for title in ("Overview", "Safety", "Metrics Summary", "Cost / Execution",
                  "Files", "Summary Markdown", "Final Decision"):
        assert f"## {title}" in md
    assert not md.endswith("\n")  # no trailing newline


def test_format_report_detail_overview_and_metrics_values() -> None:
    md = format_report_detail_markdown(_full_detail())
    overview = "\n".join(_section(md, "Overview"))
    assert "| run_id | 20260201_000000_gmo_public_paper_rsi |" in overview
    assert "| strategy | rsi_reversal |" in overview
    assert "| verdict | 研究用ベースライン |" in overview
    metrics = "\n".join(_section(md, "Metrics Summary"))
    assert "| median_expectancy | 0.0821 |" in metrics  # 4dp
    assert "| median_pf | 1.143 |" in metrics            # 3dp
    assert "| total_pnl | 312.40 |" in metrics           # 2dp
    assert "| max_drawdown_max | -88.20 |" in metrics     # 2dp
    assert "| positive_windows | 9 |" in metrics


def test_format_report_detail_safety_table() -> None:
    safety = "\n".join(_section(format_report_detail_markdown(_full_detail()), "Safety"))
    assert "| read_only_confirmed | True |" in safety
    assert "| real_order | False |" in safety
    assert "| gmo_readonly | True |" in safety
    assert "| safety_conflicts | - |" in safety


def test_format_report_detail_safety_conflicts_listed() -> None:
    d = _full_detail()
    d["index"]["safety_conflicts"] = ["real_order", "gmo_readonly"]
    safety = "\n".join(_section(format_report_detail_markdown(d), "Safety"))
    assert "| safety_conflicts | real_order,gmo_readonly |" in safety


def test_format_report_detail_cost_table() -> None:
    cost = "\n".join(_section(format_report_detail_markdown(_full_detail()), "Cost / Execution"))
    assert "| cost_scenario | current_cost |" in cost
    assert "| spread_pips | 1.2 |" in cost
    assert "| stop_loss_pips | 30 |" in cost


def test_format_report_detail_files_table_and_no_csv_body() -> None:
    md = format_report_detail_markdown(_full_detail())
    files = _section(md, "Files")
    assert files[0] == "| name | kind | size_bytes |"
    body = "\n".join(files)
    assert "| manifest.json | json | 512 |" in body
    assert "| metrics_by_window.csv | csv | 2048 |" in body
    # CSV body content must never appear (only metadata)
    assert "window,n,accuracy" not in md


def test_format_report_detail_embeds_markdown_bodies() -> None:
    md = format_report_detail_markdown(_full_detail())
    assert "研究用ベースライン" in "\n".join(_section(md, "Summary Markdown"))
    assert "継続検証候補" in "\n".join(_section(md, "Final Decision"))


def test_format_report_detail_missing_bodies_become_dash() -> None:
    md = format_report_detail_markdown(
        _full_detail(summary_markdown=None, final_decision_markdown=None))
    assert "-" in [ln.strip() for ln in _section(md, "Summary Markdown")]
    assert "-" in [ln.strip() for ln in _section(md, "Final Decision")]


def test_format_report_detail_handles_none_and_missing_keys() -> None:
    d = _full_detail()
    d["index"]["verdict"] = None
    d["summary"]["median_expectancy"] = None
    del d["index"]["strategy"]  # missing key
    md = format_report_detail_markdown(d)
    assert "| verdict | - |" in md
    assert "| strategy | - |" in md
    assert "| median_expectancy | - |" in md


def test_format_report_detail_escapes_pipe_in_cells() -> None:
    d = _full_detail()
    d["index"]["strategy"] = "a|b"
    md = format_report_detail_markdown(d)
    assert r"| strategy | a\|b |" in md


def test_format_report_detail_empty_files_keeps_header() -> None:
    md = format_report_detail_markdown(_full_detail(files=[]))
    files = _section(md, "Files")
    assert files[0] == "| name | kind | size_bytes |"
    assert files[1] == "| --- | --- | --- |"
    # no data rows between header/separator and the section break
    assert all(not ln.startswith("| metrics") for ln in files)


def test_format_report_detail_compact_dict_cells() -> None:
    metrics = "\n".join(_section(format_report_detail_markdown(_full_detail()), "Metrics Summary"))
    assert '"median_expectancy": 0.1' in metrics  # group_prior10 as compact JSON


def test_format_report_detail_diagnostic_detail_does_not_break() -> None:
    # regime diagnostic summaries lack strategy headline metrics -> dashes, no crash
    diag = _full_detail()
    diag["summary"] = {"best_oos_rule": "high_de", "best_oos": 0.55,
                       "oos5_majority_acc": 0.5, "oos_margin_vs_majority": 0.05,
                       "verdict": "予測可能性=低"}
    md = format_report_detail_markdown(diag)
    metrics = "\n".join(_section(md, "Metrics Summary"))
    assert "| median_expectancy | - |" in metrics
    assert "| group_prior10 | - |" in metrics


def test_format_report_detail_from_report_detail_tmp_path(tmp_path) -> None:
    run = _make_detail_run(tmp_path)
    md = format_report_detail_markdown(report_detail(run))
    assert md.startswith("# FX Report Detail: detail_run")
    assert "## Files" in md and "研究用ベースライン" in md
