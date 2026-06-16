"""Tests for the shared 15-window evaluation helpers (scripts/fx_eval_common.py)."""

import csv
import json
from pathlib import Path

from scripts.fx_eval_common import (
    DIAGNOSTIC_SUMMARY_REQUIRED_KEYS,
    REPORT_INDEX_REQUIRED_KEYS,
    REPORT_INDEX_SAFETY_KEYS,
    STRATEGY_SUMMARY_REQUIRED_KEYS,
    SYMBOLS,
    WINDOWS,
    classify_strategy,
    ensure_output_dir,
    fixed_config,
    format_report_index_markdown,
    group_labels,
    list_report_index,
    report_index_entry,
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
