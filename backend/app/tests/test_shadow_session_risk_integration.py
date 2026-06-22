"""Phase 2E-2 session risk/audit integration tests.

Offline only. These tests keep the legacy session path unchanged and exercise the
explicit risk/audit path without Private API, broker, API keys, or real orders.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from app.shadow.aggregate import aggregate_summaries, load_run_summaries
from app.shadow.audit import AuditLogWriteError
from app.shadow.models import Candle, Signal, Ticker
from app.shadow.risk import create_public_market_snapshot
from app.shadow.session import make_mock_candles, run_shadow_session

BASE_TIME = datetime(2026, 6, 22, 3, 0, tzinfo=UTC)


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _iso_candles(count: int) -> list[Candle]:
    candles: list[Candle] = []
    price = 150.0
    for index in range(count):
        close = round(price + (0.1 if index % 2 == 0 else -0.1), 5)
        candles.append(
            Candle(
                time=(BASE_TIME + timedelta(seconds=index)).isoformat(),
                open=price,
                high=max(price, close) + 0.05,
                low=min(price, close) - 0.05,
                close=close,
            )
        )
        price = close
    return candles


def _static_now() -> datetime:
    return BASE_TIME + timedelta(seconds=30)


def test_legacy_session_default_does_not_emit_risk_logs(tmp_path) -> None:
    summary = run_shadow_session(
        symbol="USD_JPY",
        interval="M1",
        source="mock",
        candles=make_mock_candles(5),
        out_root=tmp_path,
        steps=5,
        run_id="legacy",
    )

    run_dir = tmp_path / "legacy"
    assert summary["virtual_orders_count"] >= 1
    assert summary.get("shadow_risk_enabled") is None
    assert not (run_dir / "signal_decision_log.jsonl").exists()
    assert not (run_dir / "candidate_log.jsonl").exists()
    agg = aggregate_summaries(load_run_summaries(tmp_path)[0])
    assert agg["candidate_count"] == 0
    assert agg["risk_allow_count"] == 0
    assert agg["risk_reject_count"] == 0


def test_risk_enabled_mock_run_rejects_synthetic_spread_and_writes_audit_logs(tmp_path) -> None:
    summary = run_shadow_session(
        symbol="USD_JPY",
        interval="M1",
        source="mock",
        candles=make_mock_candles(5),
        out_root=tmp_path,
        steps=5,
        run_id="risk_reject",
        enable_shadow_risk=True,
    )

    run_dir = tmp_path / "risk_reject"
    signal_rows = _read_jsonl(run_dir / "signal_decision_log.jsonl")
    candidate_rows = _read_jsonl(run_dir / "candidate_log.jsonl")
    decision_rows = _read_jsonl(run_dir / "risk_decision_log.jsonl")

    assert summary["exit_code"] == 0
    assert summary["shadow_risk_enabled"] is True
    assert summary["virtual_orders_count"] == 0
    assert summary["synthetic_spread_reject_count"] == 4
    assert summary["real_public_bid_ask_count"] == 0
    assert len(signal_rows) == 5
    assert len(candidate_rows) == 4
    assert len(decision_rows) == 4
    assert not (run_dir / "virtual_result_log.jsonl").exists()
    assert all(row["status"] == "REJECT_SHADOW" for row in decision_rows)
    assert all("synthetic_spread_not_allowed" in row["reasons"] for row in decision_rows)

    agg = aggregate_summaries(load_run_summaries(tmp_path)[0])
    assert agg["candidate_count"] == 4
    assert agg["risk_allow_count"] == 0
    assert agg["risk_reject_count"] == 4
    assert agg["synthetic_spread_reject_count"] == 4
    assert agg["safety_violation_runs_count"] == 0


def test_risk_enabled_hold_signal_writes_signal_only(tmp_path) -> None:
    def always_flat(_candles) -> Signal:
        return Signal(side="flat", reason="test hold")

    summary = run_shadow_session(
        symbol="USD_JPY",
        interval="M1",
        source="mock",
        candles=make_mock_candles(3),
        out_root=tmp_path,
        steps=3,
        run_id="risk_hold",
        signal_fn=always_flat,
        enable_shadow_risk=True,
    )

    run_dir = tmp_path / "risk_hold"
    assert summary["candidate_count"] == 0
    assert summary["risk_allow_count"] == 0
    assert summary["virtual_orders_count"] == 0
    assert len(_read_jsonl(run_dir / "signal_decision_log.jsonl")) == 3
    assert not (run_dir / "candidate_log.jsonl").exists()
    assert not (run_dir / "virtual_result_log.jsonl").exists()


def test_risk_enabled_public_bid_ask_allows_and_correlates_virtual_result(tmp_path) -> None:
    def public_snapshot(candle: Candle, evaluation_time: datetime):
        return create_public_market_snapshot(
            symbol="USD_JPY",
            interval="M1",
            kline_timestamp=candle.time,
            ticker_symbol="USD_JPY",
            ticker_bid=candle.close,
            ticker_ask=candle.close + 0.001,
            ticker_timestamp=candle.time,
            evaluation_time=evaluation_time,
        )

    summary = run_shadow_session(
        symbol="USD_JPY",
        interval="M1",
        source="gmo-public",
        candles=_iso_candles(2),
        out_root=tmp_path,
        steps=2,
        run_id="risk_allow",
        enable_shadow_risk=True,
        risk_snapshot_fn=public_snapshot,
        now_fn=_static_now,
    )

    run_dir = tmp_path / "risk_allow"
    candidates = _read_jsonl(run_dir / "candidate_log.jsonl")
    decisions = _read_jsonl(run_dir / "risk_decision_log.jsonl")
    virtual_results = _read_jsonl(run_dir / "virtual_result_log.jsonl")

    assert summary["exit_code"] == 0
    assert summary["candidate_count"] == 1
    assert summary["risk_allow_count"] == 1
    assert summary["risk_reject_count"] == 0
    assert summary["virtual_orders_count"] == 1
    assert summary["ticker_bid_ask_used_count"] == 1
    assert summary["real_public_bid_ask_count"] == 1
    assert summary["raw_response_saved"] is False
    assert len(candidates) == len(decisions) == len(virtual_results) == 1
    assert candidates[0]["spread_provenance"] == "REAL_PUBLIC_BID_ASK"
    assert candidates[0]["spread_pips"] == 0.1
    assert decisions[0]["status"] == "ALLOW_SHADOW"
    assert virtual_results[0]["candidate_id"] == candidates[0]["candidate_id"]
    assert virtual_results[0]["decision_id"] == decisions[0]["decision_id"]

    agg = aggregate_summaries(load_run_summaries(tmp_path)[0])
    assert agg["candidate_count"] == 1
    assert agg["risk_allow_count"] == 1
    assert agg["virtual_result_count"] == 1
    assert agg["real_public_bid_ask_count"] == 1
    assert agg["safety_violation_runs_count"] == 0


def test_unvalidated_ticker_hook_is_not_real_public_provenance(tmp_path) -> None:
    def explicit_ticker(candle: Candle) -> Ticker:
        return Ticker(
            symbol="USD_JPY",
            bid=candle.close,
            ask=candle.close + 0.001,
            time=candle.time,
        )

    summary = run_shadow_session(
        symbol="USD_JPY",
        interval="M1",
        source="mock",
        candles=_iso_candles(2),
        out_root=tmp_path,
        steps=2,
        run_id="unvalidated_ticker",
        enable_shadow_risk=True,
        risk_ticker_fn=explicit_ticker,
        now_fn=_static_now,
    )

    run_dir = tmp_path / "unvalidated_ticker"
    candidates = _read_jsonl(run_dir / "candidate_log.jsonl")
    decisions = _read_jsonl(run_dir / "risk_decision_log.jsonl")

    assert summary["candidate_count"] == 1
    assert summary["risk_allow_count"] == 0
    assert summary["risk_reject_count"] == 1
    assert summary["virtual_orders_count"] == 0
    assert summary["real_public_bid_ask_count"] == 0
    assert candidates[0]["spread_provenance"] == "UNKNOWN"
    assert decisions[0]["status"] == "REJECT_SHADOW"
    assert "invalid_data" in decisions[0]["reasons"]
    assert not (run_dir / "virtual_result_log.jsonl").exists()


def test_stale_public_ticker_snapshot_fails_closed_without_candidate(tmp_path) -> None:
    def stale_snapshot(candle: Candle, evaluation_time: datetime):
        return create_public_market_snapshot(
            symbol="USD_JPY",
            interval="M1",
            kline_timestamp=candle.time,
            ticker_symbol="USD_JPY",
            ticker_bid=candle.close,
            ticker_ask=candle.close + 0.001,
            ticker_timestamp=evaluation_time - timedelta(seconds=31),
            evaluation_time=evaluation_time,
        )

    summary = run_shadow_session(
        symbol="USD_JPY",
        interval="M1",
        source="gmo-public",
        candles=_iso_candles(2),
        out_root=tmp_path,
        steps=2,
        run_id="stale_ticker",
        enable_shadow_risk=True,
        risk_snapshot_fn=stale_snapshot,
        now_fn=_static_now,
    )

    run_dir = tmp_path / "stale_ticker"
    signal_rows = _read_jsonl(run_dir / "signal_decision_log.jsonl")

    assert summary["candidate_count"] == 0
    assert summary["risk_allow_count"] == 0
    assert summary["risk_reject_count"] == 0
    assert summary["virtual_orders_count"] == 0
    assert summary["ticker_stale_count"] == 1
    assert summary["ticker_missing_count"] == 0
    assert signal_rows[-1]["disposition"] == "NO_TRADE"
    assert signal_rows[-1]["reason_codes"] == ["stale_data"]
    assert not (run_dir / "candidate_log.jsonl").exists()
    assert not (run_dir / "virtual_result_log.jsonl").exists()


def test_public_ticker_fetch_error_count_is_summary_only_fail_closed(tmp_path) -> None:
    summary = run_shadow_session(
        symbol="USD_JPY",
        interval="M1",
        source="gmo-public",
        candles=_iso_candles(2),
        out_root=tmp_path,
        steps=2,
        run_id="ticker_fetch_error",
        enable_shadow_risk=True,
        public_ticker_fetch_error_count=1,
        now_fn=_static_now,
    )

    assert summary["public_ticker_fetch_error_count"] == 1
    assert summary["real_public_bid_ask_count"] == 0
    assert summary["risk_allow_count"] == 0
    assert summary["risk_reject_count"] == 1
    assert summary["synthetic_spread_reject_count"] == 1


def test_stop_file_pre_gate_halts_with_exit_code_2(tmp_path) -> None:
    (tmp_path / "STOP").write_text("stop")
    summary = run_shadow_session(
        symbol="USD_JPY",
        interval="M1",
        source="mock",
        candles=make_mock_candles(5),
        out_root=tmp_path,
        steps=5,
        run_id="risk_stop",
        enable_shadow_risk=True,
    )

    run_dir = tmp_path / "risk_stop"
    assert summary["exit_code"] == 2
    assert summary["halted"] is True
    assert summary["kill_switch_active"] is True
    assert summary["kill_switch_reason"] == "manual_stop_file_exists"
    assert summary["candidate_count"] == 0
    assert summary["virtual_orders_count"] == 0
    assert summary["steps_executed"] == 0
    assert _read_jsonl(run_dir / "kill_switch_log.jsonl")[0]["reasons"] == [
        "manual_stop_file_exists"
    ]


def test_audit_write_failure_halts_with_exit_code_2(tmp_path, monkeypatch) -> None:
    def fail_write(*_args, **_kwargs):
        raise AuditLogWriteError("forced audit failure")

    monkeypatch.setattr("app.shadow.session.write_audit_event", fail_write)
    summary = run_shadow_session(
        symbol="USD_JPY",
        interval="M1",
        source="mock",
        candles=make_mock_candles(5),
        out_root=tmp_path,
        steps=5,
        run_id="risk_audit_fail",
        enable_shadow_risk=True,
    )

    assert summary["exit_code"] == 2
    assert summary["halted"] is True
    assert summary["kill_switch_active"] is True
    assert summary["kill_switch_reason"] == "log_write_failed"
    assert summary["audit_log_write_error_count"] == 1
    assert summary["virtual_orders_count"] == 0
