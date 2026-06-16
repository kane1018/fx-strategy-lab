"""Tests for the E2E report fixture generator (scripts/create_e2e_report_fixtures.py).

Generates into tmp_path only and reads back via the real report helpers. The real
analysis_exports/ is never touched.
"""

import json

from scripts.create_e2e_report_fixtures import (
    CSV_BODY_MARKER,
    create_e2e_report_fixtures,
)
from scripts.fx_eval_common import list_report_index, report_detail


def _rows_by_id(tmp_path):
    create_e2e_report_fixtures(tmp_path)
    rows = list_report_index(tmp_path)
    return {r["run_id"]: r for r in rows}


def test_generates_all_runs_and_list_is_readable(tmp_path) -> None:
    run_ids = create_e2e_report_fixtures(tmp_path)
    assert set(run_ids) == {
        "e2e_normal_run",
        "e2e_error_run",
        "e2e_conflict_run",
        "e2e_incomplete_run",
    }
    rows = list_report_index(tmp_path)  # must not raise
    assert {r["run_id"] for r in rows} == set(run_ids)


def test_normal_run_is_safe_read_only(tmp_path) -> None:
    row = _rows_by_id(tmp_path)["e2e_normal_run"]
    assert row["has_error"] is False
    assert row["read_only_confirmed"] is True
    assert row["safety_conflicts"] == []
    assert row["safety_complete"] is True


def test_error_run_has_error(tmp_path) -> None:
    row = _rows_by_id(tmp_path)["e2e_error_run"]
    assert row["has_error"] is True
    assert row["read_only_confirmed"] is False


def test_conflict_run_has_safety_conflicts(tmp_path) -> None:
    row = _rows_by_id(tmp_path)["e2e_conflict_run"]
    assert "real_order" in row["safety_conflicts"]
    assert row["read_only_confirmed"] is False


def test_incomplete_run_is_safety_incomplete(tmp_path) -> None:
    row = _rows_by_id(tmp_path)["e2e_incomplete_run"]
    assert row["safety_complete"] is False
    assert row["read_only_confirmed"] is False


def test_normal_detail_has_seven_section_data(tmp_path) -> None:
    create_e2e_report_fixtures(tmp_path)
    detail = report_detail(tmp_path / "e2e_normal_run")
    # blocks backing the 7 UI sections
    assert detail["index"]["strategy"] == "rsi_reversal"  # Overview
    assert "read_only_confirmed" in detail["index"]  # Safety
    assert "median_expectancy" in detail["summary"]  # Metrics
    assert detail["manifest"]["spread_pips"] == 1.2  # Cost / Execution
    csv_names = {f["name"] for f in detail["files"]}
    assert "metrics_by_window.csv" in csv_names  # Files (metadata only)
    assert detail["summary_markdown"]  # Summary Markdown
    assert detail["final_decision_markdown"]  # Final Decision


def test_files_carry_metadata_only(tmp_path) -> None:
    create_e2e_report_fixtures(tmp_path)
    detail = report_detail(tmp_path / "e2e_normal_run")
    csv_files = [f for f in detail["files"] if f["name"].endswith(".csv")]
    assert csv_files
    for f in csv_files:
        assert set(f) == {"name", "kind", "size_bytes"}
        assert f["kind"] == "csv"


def test_csv_marker_not_in_detail_payload(tmp_path) -> None:
    create_e2e_report_fixtures(tmp_path)
    detail = report_detail(tmp_path / "e2e_normal_run")
    payload = json.dumps(detail, ensure_ascii=False, default=str)
    assert CSV_BODY_MARKER not in payload  # CSV body never surfaces via the API
    # but the marker really is in the CSV file on disk (fixture sanity check)
    csv_text = (tmp_path / "e2e_normal_run" / "metrics_by_window.csv").read_text()
    assert CSV_BODY_MARKER in csv_text


def test_no_secret_or_env_strings_in_fixtures(tmp_path) -> None:
    create_e2e_report_fixtures(tmp_path)
    blob = ""
    for path in tmp_path.rglob("*"):
        if path.is_file():
            blob += path.read_text()
    lowered = blob.lower()
    for forbidden in ("secret", "api_key=", "apikey", "password", "token", ".env"):
        assert forbidden not in lowered
