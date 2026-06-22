"""Tests for shadow-run aggregation (app/shadow/aggregate.py). Offline, fixture-based."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.shadow.aggregate import (
    aggregate_summaries,
    load_run_summaries,
    render_group_csv,
    render_markdown,
    render_runs_csv,
    safety_violations,
)
from app.shadow.audit import write_audit_event
from app.shadow.audit_schema import KillSwitchAuditRecord, VirtualResultAuditRecord
from app.shadow.risk import (
    KillSwitchReason,
    RiskContext,
    SignalLabel,
    SpreadProvenance,
    create_order_candidate,
    evaluate,
)

NOW = datetime(2026, 6, 22, 3, 0, tzinfo=UTC)
MARKET_TIME = NOW - timedelta(seconds=30)


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


def _risk_file(root, run_id, event_type):
    return root / run_id / f"{event_type}.jsonl"


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _candidate(run_id, step_index=0):
    candidate = create_order_candidate(
        signal_label=SignalLabel.BUY,
        run_id=run_id,
        step_index=step_index,
        timestamp=NOW,
        market_data_timestamp=MARKET_TIME + timedelta(seconds=step_index),
        source="mock",
        symbol="USD_JPY",
        interval="M1",
        quantity=100,
        bid=154.100 + step_index * 0.001,
        ask=154.104 + step_index * 0.001,
        spread_provenance=SpreadProvenance.REAL_PUBLIC_BID_ASK,
        signal_name="summary_test",
        signal_reason="fixture",
        confidence=0.8,
    )
    assert candidate is not None
    return candidate


def _context(**overrides):
    values = {
        "evaluation_time": NOW,
        "spread_provenance": SpreadProvenance.REAL_PUBLIC_BID_ASK,
    }
    values.update(overrides)
    return RiskContext(**values)


def _write_valid_risk_pair(root, run_id, step_index=0, *, reject=False):
    candidate = _candidate(run_id, step_index)
    context = _context(market_closed=True) if reject else _context()
    decision = evaluate(candidate, context)
    write_audit_event(root, run_id=run_id, event_type="candidate_log", payload=candidate)
    write_audit_event(root, run_id=run_id, event_type="risk_decision_log", payload=decision)
    return candidate, decision


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
    _write_valid_risk_pair(tmp_path, "risk", 0)
    _write_valid_risk_pair(tmp_path, "risk", 1, reject=True)
    kill = KillSwitchAuditRecord(
        run_id="risk",
        timestamp=NOW.isoformat(),
        active=True,
        reasons=(KillSwitchReason.MANUAL_STOP_FILE_EXISTS,),
        activated_at=NOW.isoformat(),
        trigger="manual_stop_file_exists",
    )
    write_audit_event(tmp_path, run_id="risk", event_type="kill_switch_log", payload=kill)

    summaries, broken = load_run_summaries(tmp_path)
    assert broken == [] and len(summaries) == 2
    agg = aggregate_summaries(summaries)
    assert agg["candidate_count"] == 2
    assert agg["risk_allow_count"] == 1
    assert agg["risk_reject_count"] == 1
    assert agg["kill_switch_count"] == 1
    assert agg["kill_switch_active_runs_count"] == 1
    assert agg["shadow_risk_schema_versions"] == ["shadow-risk-v1"]
    assert agg["reject_reasons"] == {"market_closed": 1}
    assert agg["kill_switch_reasons"] == {"manual_stop_file_exists": 1}
    md = render_markdown(agg, summaries, broken)
    assert "## Shadow Risk Pipeline" in md
    assert "candidate_count: 2" in md


def test_public_ticker_optional_summary_counts_are_backward_compatible(tmp_path) -> None:
    _write(tmp_path, "legacy", _summary("legacy"))
    _write(
        tmp_path,
        "ticker",
        _summary(
            "ticker",
            shadow_risk_enabled=True,
            ticker_bid_ask_used_count=2,
            real_public_bid_ask_count=2,
            synthetic_spread_reject_count=1,
            ticker_missing_count=1,
            ticker_stale_count=1,
            ticker_invalid_count=1,
            ticker_kline_skew_reject_count=1,
            public_ticker_fetch_error_count=1,
            spread_too_wide_count=1,
        ),
    )

    summaries, broken = load_run_summaries(tmp_path)
    agg = aggregate_summaries(summaries)
    assert broken == []
    assert agg["ticker_bid_ask_used_count"] == 2
    assert agg["real_public_bid_ask_count"] == 2
    assert agg["synthetic_spread_reject_count"] == 1
    assert agg["ticker_missing_count"] == 1
    assert agg["ticker_stale_count"] == 1
    assert agg["ticker_invalid_count"] == 1
    assert agg["ticker_kline_skew_reject_count"] == 1
    assert agg["public_ticker_fetch_error_count"] == 1
    assert agg["spread_too_wide_count"] == 1
    md = render_markdown(agg, summaries, broken)
    assert "## Public Ticker Bid/Ask" in md
    assert "real_public_bid_ask_count: 2" in md


def test_invalid_new_schema_is_safety_violation_not_broken_legacy(tmp_path) -> None:
    _write(tmp_path, "risk", _summary("risk"))
    _write_risk_log(tmp_path, "risk", "candidate_log", [
        {"event_type": "candidate_log", "run_id": "risk", "timestamp": "t"},
    ])
    summaries, broken = load_run_summaries(tmp_path)
    assert broken == []
    agg = aggregate_summaries(summaries)
    assert agg["candidate_count"] == 0
    assert agg["invalid_risk_row_count"] == 1
    assert agg["safety_violation_runs_count"] == 1
    assert any("candidate_log" in v["field"] for v in agg["safety_violations"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("real_order", True),
        ("private_api_used", True),
        ("api_key_used", True),
        ("no_order_execution", False),
        ("live_trading_environment_enabled", True),
        ("gmo_order_enabled", True),
    ],
)
def test_unsafe_candidate_risk_row_is_violation_and_not_counted(tmp_path, field, value) -> None:
    _write(tmp_path, "risk", _summary("risk"))
    _write_valid_risk_pair(tmp_path, "risk")
    path = _risk_file(tmp_path, "risk", "candidate_log")
    rows = _read_jsonl(path)
    rows[0][field] = value
    _write_jsonl(path, rows)

    agg = aggregate_summaries(load_run_summaries(tmp_path)[0])
    assert agg["candidate_count"] == 0
    assert agg["risk_allow_count"] == 0
    assert agg["safety_violation_runs_count"] == 1
    assert any(v["field"] == f"candidate_log.{field}" for v in agg["safety_violations"])


@pytest.mark.parametrize(
    ("event_type", "mutate", "expected_field"),
    [
        ("candidate_log", lambda row: row.update({"unexpected": True}), "unexpected"),
        ("candidate_log", lambda row: row.pop("candidate_id"), "candidate_id"),
        ("candidate_log", lambda row: row.update({"schema_version": "bad"}), "schema_version"),
        ("candidate_log", lambda row: row.update({"event_type": "bad_event"}), "event_type"),
        ("candidate_log", lambda row: row.update({"run_id": "other"}), "run_id"),
        ("risk_decision_log", lambda row: row.update({"reasons": ["not_a_reason"]}), "reasons"),
        (
            "risk_decision_log",
            lambda row: row.update({"decision_id": "risk_cand_other_0_buy_abc_bad"}),
            "decision_id",
        ),
    ],
)
def test_invalid_risk_row_schema_is_violation_and_not_counted(
    tmp_path, event_type, mutate, expected_field
) -> None:
    _write(tmp_path, "risk", _summary("risk"))
    _write_valid_risk_pair(tmp_path, "risk", reject=True)
    path = _risk_file(tmp_path, "risk", event_type)
    rows = _read_jsonl(path)
    mutate(rows[0])
    _write_jsonl(path, rows)

    agg = aggregate_summaries(load_run_summaries(tmp_path)[0])
    assert agg["candidate_count"] == 0
    assert agg["risk_reject_count"] == 0
    assert agg["safety_violation_runs_count"] == 1
    assert any(expected_field in v["field"] for v in agg["safety_violations"])


def test_decision_without_candidate_is_violation_and_not_counted(tmp_path) -> None:
    _write(tmp_path, "risk", _summary("risk"))
    candidate = _candidate("risk")
    decision = evaluate(candidate, _context())
    write_audit_event(tmp_path, run_id="risk", event_type="risk_decision_log", payload=decision)

    agg = aggregate_summaries(load_run_summaries(tmp_path)[0])
    assert agg["candidate_count"] == 0
    assert agg["risk_allow_count"] == 0
    assert agg["safety_violation_runs_count"] == 1
    assert any("candidate_id" in v["field"] for v in agg["safety_violations"])


def test_candidate_without_decision_is_violation_and_not_counted(tmp_path) -> None:
    _write(tmp_path, "risk", _summary("risk"))
    candidate = _candidate("risk")
    write_audit_event(tmp_path, run_id="risk", event_type="candidate_log", payload=candidate)

    agg = aggregate_summaries(load_run_summaries(tmp_path)[0])
    assert agg["candidate_count"] == 0
    assert agg["risk_allow_count"] == 0
    assert agg["safety_violation_runs_count"] == 1
    assert any("candidate_id" in v["field"] for v in agg["safety_violations"])


def test_duplicate_decision_is_violation_and_not_counted(tmp_path) -> None:
    _write(tmp_path, "risk", _summary("risk"))
    _candidate, decision = _write_valid_risk_pair(tmp_path, "risk")
    write_audit_event(tmp_path, run_id="risk", event_type="risk_decision_log", payload=decision)

    agg = aggregate_summaries(load_run_summaries(tmp_path)[0])
    assert agg["candidate_count"] == 0
    assert agg["risk_allow_count"] == 0
    assert agg["safety_violation_runs_count"] == 1
    assert any("decision_id" in v["field"] for v in agg["safety_violations"])


def test_virtual_result_without_allow_is_violation_and_not_counted(tmp_path) -> None:
    _write(tmp_path, "risk", _summary("risk"))
    candidate, decision = _write_valid_risk_pair(tmp_path, "risk", reject=True)
    virtual_result = VirtualResultAuditRecord(
        run_id="risk",
        timestamp=NOW.isoformat(),
        candidate_id=candidate.candidate_id,
        decision_id=decision.decision_id,
        status="VIRTUAL_RESULT",
        position_side="flat",
        units=0,
        unrealized_pnl=0.0,
    )
    write_audit_event(
        tmp_path,
        run_id="risk",
        event_type="virtual_result_log",
        payload=virtual_result,
    )

    agg = aggregate_summaries(load_run_summaries(tmp_path)[0])
    assert agg["virtual_result_count"] == 0
    assert agg["safety_violation_runs_count"] == 1
    assert any("virtual_result_log.decision_id" == v["field"] for v in agg["safety_violations"])
