"""H-11 Stage 1 safe-aggregate report tests (no-POST)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.services.h11_stage1_review_report import (
    H11Stage1NetResult,
    H11Stage1ReportStatus,
    H11Stage1ReviewReportError,
    render_h11_stage1_report_markdown,
    summarize_h11_stage1_journal,
)


def _write(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records))


def _records() -> list[dict[str, object]]:
    return [
        {
            "recorded_at_utc": "2026-07-13T01:00:00+00:00",
            "event": "PAPER_ENTRY_OPENED",
            "p_up": 0.7,
        },
        {
            "recorded_at_utc": "2026-07-14T01:00:00+00:00",
            "event": "PAPER_POSITION_SETTLED",
            "paper_outcome_jpy": 1000,
            "stop_state": "ACTIVE",
            "closed_trades_total": 1,
        },
        {
            "recorded_at_utc": "2026-07-14T01:00:01+00:00",
            "event": "STAGE1_NO_ENTRY",
            "p_up": 0.5,
        },
        {
            "recorded_at_utc": "2026-07-15T01:00:00+00:00",
            "event": "STAGE1_BLOCKED_PRE_TRADE",
            "reasons": ["SESSION_STOPPED"],
        },
        {
            "recorded_at_utc": "2026-07-16T01:00:00+00:00",
            "event": "PAPER_POSITION_SETTLED",
            "paper_outcome_jpy": -6000,
            "stop_state": "STOPPED_DAILY_BUDGET",
            "closed_trades_total": 2,
        },
        {
            "recorded_at_utc": "2026-07-16T01:00:01+00:00",
            "event": "FUTURE_SAFE_EVENT",
        },
    ]


def test_missing_journal_is_safe_and_false(tmp_path: Path) -> None:
    summary = summarize_h11_stage1_journal(tmp_path / "missing.jsonl")
    assert summary.report_status is H11Stage1ReportStatus.JOURNAL_MISSING
    assert summary.closed_trades_cumulative == 0
    assert summary.actual_post is False
    assert bool(summary) is False


def test_aggregates_counts_without_exposing_individual_values(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    _write(journal, _records())

    summary = summarize_h11_stage1_journal(journal)

    assert summary.report_status is H11Stage1ReportStatus.READY
    assert summary.entry_count == 1
    assert summary.settle_count == 2
    assert summary.block_count == 1
    assert summary.no_entry_count == 1
    assert summary.closed_trades_cumulative == 2
    assert summary.discipline_violation_count_cumulative == 1
    assert (summary.period_wins, summary.period_losses, summary.period_flats) == (1, 1, 0)
    assert summary.period_win_rate_pct == 50.0
    assert summary.period_net_result is H11Stage1NetResult.NEGATIVE
    assert summary.latest_stop_state == "STOPPED_DAILY_BUDGET"
    assert summary.stop_event_count == 1
    assert summary.unknown_event_count == 1

    rendered = render_h11_stage1_report_markdown(summary)
    assert "1000" not in rendered
    assert "6000" not in rendered
    assert "actual_post=false" in rendered
    assert "raw_id_value_exposure=false" in rendered


def test_period_filter_keeps_cumulative_totals(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    _write(journal, _records())

    summary = summarize_h11_stage1_journal(
        journal,
        since_jst=date(2026, 7, 15),
        until_jst=date(2026, 7, 15),
    )

    assert summary.block_count == 1
    assert summary.settle_count == 0
    assert summary.closed_trades_cumulative == 2
    assert summary.discipline_violation_count_cumulative == 1
    assert summary.period_net_result is H11Stage1NetResult.NOT_AVAILABLE


def test_period_without_rows_is_explicit(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    _write(journal, _records())

    summary = summarize_h11_stage1_journal(
        journal,
        since_jst=date(2026, 7, 20),
        until_jst=date(2026, 7, 21),
    )

    assert summary.report_status is H11Stage1ReportStatus.NO_RECORDS_IN_PERIOD
    assert summary.closed_trades_cumulative == 2
    assert summary.latest_stop_state == "STOPPED_DAILY_BUDGET"


def test_block_without_session_stop_reason_proves_active_state(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    _write(
        journal,
        [
            {
                "recorded_at_utc": "2026-07-11T00:00:00+00:00",
                "event": "STAGE1_BLOCKED_PRE_TRADE",
                "reasons": ["WEEKEND_BLOCKED", "OUTSIDE_TRADING_HOURS"],
            }
        ],
    )

    summary = summarize_h11_stage1_journal(journal)

    assert summary.latest_stop_state == "ACTIVE"
    assert summary.block_count == 1


def test_invalid_json_fails_without_echoing_content(tmp_path: Path) -> None:
    journal = tmp_path / "journal.jsonl"
    journal.write_text('{"secret-looking":')

    with pytest.raises(H11Stage1ReviewReportError) as error:
        summarize_h11_stage1_journal(journal)

    assert str(error.value) == "journal contains invalid JSON"
    assert "secret-looking" not in str(error.value)


def test_symlink_journal_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.jsonl"
    _write(target, _records())
    link = tmp_path / "journal.jsonl"
    link.symlink_to(target)

    with pytest.raises(H11Stage1ReviewReportError, match="must not be a symlink"):
        summarize_h11_stage1_journal(link)
