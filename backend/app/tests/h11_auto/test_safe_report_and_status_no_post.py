from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.h11_auto.contracts import (
    FormalHorizon,
    FormalSignal,
    PhaseAExecutionPolicy,
    SignalDecision,
)
from app.h11_auto.persistence import H11AutoStateStore
from app.h11_auto.report import (
    H11AutoReportError,
    H11AutoReportStatus,
    render_h11_auto_report_markdown,
    summarize_h11_auto_state,
)
from app.h11_auto.state_machine import AutoCycleState
from app.h11_auto.status import AutoProjectionState, project_h11_auto_status

NOW = datetime(2026, 7, 15, 5, 0, tzinfo=UTC)


def _populate(path: Path, *, halt: bool = False) -> tuple[str, str]:
    store = H11AutoStateStore(path)
    signal = FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:report-test",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=NOW,
        valid_until_utc=NOW + timedelta(minutes=10),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.62"),
    )
    policy = PhaseAExecutionPolicy(
        strategy_version=signal.strategy_version,
        signal_config_hash=signal.signal_config_hash,
        selected_horizon=signal.horizon,
    )
    cycle = store.create_intent(signal=signal, policy=policy, now_utc=NOW)
    store.record_attempt_started(intent_id=cycle.intent_id, now_utc=NOW)
    if halt:
        store.transition(
            intent_id=cycle.intent_id,
            target=AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
            event_category="HALTED_SYNTHETIC",
            now_utc=NOW,
            halt_reason="SAFE_TEST_HALT",
        )
    else:
        store.transition(
            intent_id=cycle.intent_id,
            target=AutoCycleState.POSITION_PROTECTED,
            event_category="POSITION_PROTECTED_SYNTHETIC",
            now_utc=NOW,
        )
    return cycle.intent_id, signal.fingerprint


def test_report_returns_only_safe_aggregates_and_no_identifiers(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    intent_id, fingerprint = _populate(path)
    report = summarize_h11_auto_state(path)
    assert report.report_status is H11AutoReportStatus.READY
    assert report.cycle_count == 1
    assert report.active_cycle_count == 1
    assert report.entry_attempt_count == 1
    assert report.journal_valid is True
    rendered = render_h11_auto_report_markdown(report)
    safe_json = str(report.to_safe_dict())
    assert intent_id not in rendered + safe_json
    assert fingerprint not in rendered + safe_json
    assert report.actual_post_count == 0
    assert report.broker_read_performed is False
    assert report.credential_read_performed is False
    assert report.generation_label == "UNBOUND"


def test_report_and_status_include_safe_generation_labels(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    store = H11AutoStateStore(path)
    signal = FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:report-generation-test",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=NOW,
        valid_until_utc=NOW + timedelta(minutes=10),
        decision=SignalDecision.STAY,
        probability_up=Decimal("0.50"),
    )
    policy = PhaseAExecutionPolicy(
        strategy_version=signal.strategy_version,
        signal_config_hash=signal.signal_config_hash,
        selected_horizon=signal.horizon,
    )
    store.bind_run_generation(
        generation_label="GENERATION_SAFE_LABEL",
        policy=policy,
        risk_policy_label="RISK_SAFE_LABEL",
        risk_policy_digest="risk-digest",
        dead_man_policy_label="DEAD_MAN_SAFE_LABEL",
        dead_man_policy_digest="dead-man-digest",
    )
    store.create_intent(signal=signal, policy=policy, now_utc=NOW)
    report = summarize_h11_auto_state(path)
    status = project_h11_auto_status(path)
    assert report.generation_label == "GENERATION_SAFE_LABEL"
    assert report.strategy_version == "SHORT_V1"
    assert report.selected_horizon == "10m"
    assert report.risk_policy_label == "RISK_SAFE_LABEL"
    assert status.generation_label == "GENERATION_SAFE_LABEL"
    assert status.dead_man_policy_label == "DEAD_MAN_SAFE_LABEL"


def test_bound_generation_is_visible_before_first_signal(tmp_path: Path) -> None:
    path = tmp_path / "empty-bound-state.sqlite3"
    store = H11AutoStateStore(path)
    policy = PhaseAExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:empty-generation-test",
        selected_horizon=FormalHorizon.MINUTES_30,
    )
    store.bind_run_generation(
        generation_label="EMPTY_GENERATION_SAFE_LABEL",
        policy=policy,
        risk_policy_label="RISK_SAFE_LABEL",
        risk_policy_digest="risk-digest",
        dead_man_policy_label="DEAD_MAN_SAFE_LABEL",
        dead_man_policy_digest="dead-man-digest",
    )
    report = summarize_h11_auto_state(path)
    assert report.report_status is H11AutoReportStatus.NO_RECORDS_IN_PERIOD
    assert report.generation_label == "EMPTY_GENERATION_SAFE_LABEL"
    assert report.selected_horizon == "30m"


def test_report_rejects_tampered_generation_manifest(tmp_path: Path) -> None:
    path = tmp_path / "tampered-generation.sqlite3"
    store = H11AutoStateStore(path)
    policy = PhaseAExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:tampered-generation-test",
        selected_horizon=FormalHorizon.MINUTES_10,
    )
    store.bind_run_generation(
        generation_label="GENERATION_SAFE_LABEL",
        policy=policy,
        risk_policy_label="RISK_SAFE_LABEL",
        risk_policy_digest="risk-digest",
        dead_man_policy_label="DEAD_MAN_SAFE_LABEL",
        dead_man_policy_digest="dead-man-digest",
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE metadata SET value = 'TAMPERED' WHERE key = 'generation_label'"
        )
    with pytest.raises(H11AutoReportError, match="manifest"):
        summarize_h11_auto_state(path)


def test_report_filters_by_jst_date_without_mutating_state(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    _populate(path)
    before = path.stat().st_mtime_ns
    report = summarize_h11_auto_state(
        path,
        since_jst=date(2026, 7, 16),
        until_jst=date(2026, 7, 16),
    )
    after = path.stat().st_mtime_ns
    assert report.report_status is H11AutoReportStatus.NO_RECORDS_IN_PERIOD
    assert before == after


def test_status_projection_is_separate_fake_only_and_fail_closed(tmp_path: Path) -> None:
    missing = project_h11_auto_status(tmp_path / "missing.sqlite3")
    assert missing.state is AutoProjectionState.OFF
    path = tmp_path / "halted.sqlite3"
    _populate(path, halt=True)
    status = project_h11_auto_status(path)
    assert status.state is AutoProjectionState.HALTED_OPERATOR_REVIEW_REQUIRED
    assert status.halt_latched is True
    assert status.halt_reason_code == "SAFE_TEST_HALT"
    assert status.actual_transport_present is False
    assert status.actual_post_allowed is False
    assert status.broker_read_allowed is False
    assert status.broker_write_allowed is False
    assert status.credential_read_allowed is False


def test_report_rejects_symlink_and_invalid_period(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    _populate(path)
    link = tmp_path / "state-link.sqlite3"
    link.symlink_to(path)
    with pytest.raises(H11AutoReportError, match="symlink"):
        summarize_h11_auto_state(link)
    with pytest.raises(H11AutoReportError, match="period"):
        summarize_h11_auto_state(
            path,
            since_jst=date(2026, 7, 16),
            until_jst=date(2026, 7, 15),
        )


def test_report_rejects_wrong_schema_without_mutating_database(tmp_path: Path) -> None:
    path = tmp_path / "wrong.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT)")
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES('schema_version', 'WRONG')"
        )
    before = path.stat().st_mtime_ns
    with pytest.raises(H11AutoReportError, match="schema"):
        summarize_h11_auto_state(path)
    assert path.stat().st_mtime_ns == before
