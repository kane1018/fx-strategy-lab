"""Tests for shadow-run aggregation (app/shadow/aggregate.py). Offline, fixture-based."""

import json

import pytest

from app.shadow.aggregate import (
    aggregate_summaries,
    load_run_summaries,
    render_group_csv,
    render_markdown,
    render_runs_csv,
    safety_violations,
)


def _safe():
    return {
        "real_order": False, "private_api_used": False, "api_key_used": False,
        "no_order_execution": True, "live_trading_environment_enabled": False,
        "gmo_readonly": True, "gmo_order_enabled": False,
    }


def _summary(run_id, **over):
    base = {
        "run_id": run_id, "source": "mock", "symbol": "USD_JPY", "interval": "M1",
        "steps_executed": 10, "events_count": 10, "virtual_orders_count": 9,
        "buy_count": 5, "sell_count": 4, "flat_count": 1, "max_abs_units": 1,
        "final_position_side": "short", "final_position_units": 1, "final_average_price": 154.0,
        "final_unrealized_pnl": 1.5, "last_price": 154.1, "data_points": 10,
        "halted": False, "halt_reason": "", "safety": _safe(),
        "created_at": "2026-06-17T00:00:00+00:00",
    }
    base.update(over)
    return base


def _write(root, run_id, summary):
    d = root / run_id
    d.mkdir()
    (d / "summary.json").write_text(json.dumps(summary))


def _write_risk_log(root, run_id, event_type, rows):
    path = root / run_id / f"{event_type}.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_load_and_aggregate_multiple_runs(tmp_path) -> None:
    _write(tmp_path, "r1", _summary("r1"))
    _write(tmp_path, "r2", _summary("r2", symbol="EUR_JPY", source="gmo-public",
                                    virtual_orders_count=3, final_unrealized_pnl=-0.5))
    summaries, broken = load_run_summaries(tmp_path)
    assert len(summaries) == 2 and broken == []
    agg = aggregate_summaries(summaries)
    assert agg["runs_count"] == 2
    assert agg["total_virtual_orders_count"] == 12
    assert agg["total_final_unrealized_pnl"] == pytest.approx(1.0)
    assert set(agg["symbols"]) == {"USD_JPY", "EUR_JPY"}
    assert set(agg["sources"]) == {"mock", "gmo-public"}
    assert agg["candidate_count"] == 0  # legacy summaries remain valid
    assert agg["shadow_risk_schema_versions"] == []


def test_grouping_by_symbol_source_interval_date(tmp_path) -> None:
    _write(tmp_path, "r1", _summary("r1"))
    _write(tmp_path, "r2", _summary("r2", symbol="EUR_JPY"))
    _write(tmp_path, "r3", _summary("r3", interval="M5", created_at="2026-06-18T00:00:00+00:00"))
    agg = aggregate_summaries(load_run_summaries(tmp_path)[0])
    assert agg["by_symbol"]["USD_JPY"]["runs_count"] == 2
    assert agg["by_symbol"]["EUR_JPY"]["runs_count"] == 1
    assert set(agg["by_interval"]) == {"M1", "M5"}
    assert set(agg["by_date"]) == {"2026-06-17", "2026-06-18"}
    assert agg["by_source"]["mock"]["runs_count"] == 3


def test_halted_runs_counted(tmp_path) -> None:
    _write(tmp_path, "r1", _summary("r1"))
    _write(tmp_path, "r2", _summary("r2", halted=True, halt_reason="exceed max_units"))
    agg = aggregate_summaries(load_run_summaries(tmp_path)[0])
    assert agg["halted_runs_count"] == 1


def test_safety_violation_detected(tmp_path) -> None:
    bad = _safe()
    bad["real_order"] = True
    _write(tmp_path, "ok", _summary("ok"))
    _write(tmp_path, "bad", _summary("bad", safety=bad))
    summaries = load_run_summaries(tmp_path)[0]
    violations = safety_violations(summaries)
    assert any(v["run_id"] == "bad" and v["field"] == "real_order" for v in violations)
    agg = aggregate_summaries(summaries)
    assert agg["safety_violation_runs_count"] == 1
    assert "bad" in agg["safety_violation_run_ids"]


def test_markdown_contains_key_sections(tmp_path) -> None:
    _write(tmp_path, "r1", _summary("r1"))
    summaries, broken = load_run_summaries(tmp_path)
    md = render_markdown(aggregate_summaries(summaries), summaries, broken)
    for token in ("## Overview", "## Totals", "### By Symbol", "### By Date",
                  "## Safety Violations", "## Halted Runs"):
        assert token in md


def test_csv_outputs(tmp_path) -> None:
    _write(tmp_path, "r1", _summary("r1"))
    summaries = load_run_summaries(tmp_path)[0]
    runs_csv = render_runs_csv(summaries)
    assert runs_csv.splitlines()[0].startswith("run_id,source,symbol")
    assert "r1" in runs_csv
    agg = aggregate_summaries(summaries)
    by_symbol = render_group_csv(agg["by_symbol"], "symbol")
    assert by_symbol.splitlines()[0].startswith("symbol,runs_count")


def test_broken_summary_skipped_and_reported(tmp_path) -> None:
    _write(tmp_path, "ok", _summary("ok"))
    bad = tmp_path / "broken"
    bad.mkdir()
    (bad / "summary.json").write_text("{ not valid json")
    summaries, broken = load_run_summaries(tmp_path)
    assert [s["run_id"] for s in summaries] == ["ok"]
    assert broken == ["broken"]


def test_zero_runs(tmp_path) -> None:
    summaries, broken = load_run_summaries(tmp_path)
    assert summaries == [] and broken == []


def test_missing_root_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_run_summaries(tmp_path / "nope")


def test_phase2e_risk_logs_are_aggregated_without_breaking_legacy(tmp_path) -> None:
    _write(tmp_path, "legacy", _summary("legacy"))
    _write(tmp_path, "risk", _summary("risk"))
    base = {"schema_version": "shadow-risk-v1", "run_id": "risk", "timestamp": "t"}
    _write_risk_log(tmp_path, "risk", "candidate_log", [
        {**base, "event_type": "candidate_log", "candidate_id": "c1"},
        {**base, "event_type": "candidate_log", "candidate_id": "c2"},
    ])
    _write_risk_log(tmp_path, "risk", "risk_decision_log", [
        {**base, "event_type": "risk_decision_log", "status": "ALLOW_SHADOW", "reasons": []},
        {**base, "event_type": "risk_decision_log", "status": "REJECT_SHADOW",
         "reasons": ["spread_too_wide"]},
    ])
    _write_risk_log(tmp_path, "risk", "kill_switch_log", [
        {**base, "event_type": "kill_switch_log", "active": True,
         "reasons": ["manual_stop_file_exists"]},
    ])

    summaries, broken = load_run_summaries(tmp_path)
    assert broken == [] and len(summaries) == 2
    agg = aggregate_summaries(summaries)
    assert agg["candidate_count"] == 2
    assert agg["risk_allow_count"] == 1
    assert agg["risk_reject_count"] == 1
    assert agg["kill_switch_count"] == 1
    assert agg["kill_switch_active_runs_count"] == 1
    assert agg["shadow_risk_schema_versions"] == ["shadow-risk-v1"]
    assert agg["reject_reasons"] == {"spread_too_wide": 1}
    assert agg["kill_switch_reasons"] == {"manual_stop_file_exists": 1}
    md = render_markdown(agg, summaries, broken)
    assert "## Shadow Risk Pipeline" in md
    assert "candidate_count: 2" in md


def test_invalid_new_schema_is_safety_violation_not_broken_legacy(tmp_path) -> None:
    _write(tmp_path, "risk", _summary("risk"))
    _write_risk_log(tmp_path, "risk", "candidate_log", [
        {"event_type": "candidate_log", "run_id": "risk", "timestamp": "t"},
    ])
    summaries, broken = load_run_summaries(tmp_path)
    assert broken == []
    agg = aggregate_summaries(summaries)
    assert agg["candidate_count"] == 1
    assert agg["safety_violation_runs_count"] == 1
    assert any(v["field"] == "risk_pipeline" for v in agg["safety_violations"])
