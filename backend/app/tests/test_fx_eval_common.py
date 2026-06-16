"""Tests for the shared 15-window evaluation helpers (scripts/fx_eval_common.py)."""

from pathlib import Path

from scripts.fx_eval_common import (
    SYMBOLS,
    WINDOWS,
    classify_strategy,
    fixed_config,
    group_labels,
    run_id,
    safety_metadata,
    window_groups,
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
