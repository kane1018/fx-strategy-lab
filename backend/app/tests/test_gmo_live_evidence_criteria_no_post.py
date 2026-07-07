"""No-POST evidence criteria and safe summary tests for paper/shadow evidence.

These tests validate objective safe-label criteria for reporting and make sure the
new helpers remain value-less and code-safe.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from app.services.gmo_live_evidence_criteria import (
    GmoKillSwitchAndSettlementAnomalyEvidenceInput,
    GmoKillSwitchAndSettlementAnomalyEvidenceStatus,
    GmoPaperTradeEvidenceCriteriaInput,
    GmoPaperTradeEvidenceStatus,
    build_gmo_live_kill_switch_anomaly_safe_summary,
    build_gmo_live_paper_trade_evidence_safe_summary,
    evaluate_gmo_kill_switch_and_settlement_anomaly_criteria,
    evaluate_gmo_paper_trade_evidence_criteria,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_evidence_criteria.py"
)
PAPER_SHADOW_FIXTURE_PATH = (
    pathlib.Path(__file__).resolve().parent
    / "fixtures"
    / "no_post_evidence"
    / "paper_shadow_safe_evidence_no_post.json"
)
ANOMALY_REPLAY_FIXTURE_PATH = (
    pathlib.Path(__file__).resolve().parent
    / "fixtures"
    / "no_post_evidence"
    / "anomaly_replay_safe_evidence_no_post.json"
)


def test_paper_evidence_confirmed_when_all_safe_criteria_are_true() -> None:
    summary = build_gmo_live_paper_trade_evidence_safe_summary(
        GmoPaperTradeEvidenceCriteriaInput(
            evidence_source_exists=True,
            evidence_location_safe_label_exists=True,
            paper_trade_period_safe_label_exists=True,
            paper_trade_run_count_safe_label_exists=True,
            paper_trade_result_category_safe_label_exists=True,
            evidence_reproducible_or_checked_by_report=True,
            evidence_relevant_to_gmo_live_entry_readiness=True,
            evidence_is_not_unrelated_backtest=True,
            evidence_does_not_imply_actual_post_permission=True,
            paper_trade_period_safe_label="PERIOD_SAFE_LABEL",
            paper_trade_run_count_safe_label="COUNT_SAFE_LABEL",
            paper_trade_result_category="RESULT_SAFE_CATEGORY",
            performance_report_location_safe_label="SAFE_REPORT_PATH",
        )
    )
    assert summary.paper_trade_evidence_status is (
        GmoPaperTradeEvidenceStatus.PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY
    )
    assert summary.paper_trade_period_safe_label == "PERIOD_SAFE_LABEL"
    assert summary.paper_trade_run_count_safe_label == "COUNT_SAFE_LABEL"
    assert summary.paper_trade_result_category == "RESULT_SAFE_CATEGORY"
    assert summary.performance_report_location_safe_label == "SAFE_REPORT_PATH"
    assert summary.raw_trade_ids_exposed is False


def test_paper_evidence_not_ready_when_required_safe_labels_are_missing() -> None:
    result = evaluate_gmo_paper_trade_evidence_criteria(
        GmoPaperTradeEvidenceCriteriaInput(
            evidence_source_exists=True,
            evidence_location_safe_label_exists=True,
            paper_trade_period_safe_label_exists=False,
            paper_trade_run_count_safe_label_exists=False,
            paper_trade_result_category_safe_label_exists=False,
            evidence_reproducible_or_checked_by_report=True,
            evidence_relevant_to_gmo_live_entry_readiness=True,
            evidence_is_not_unrelated_backtest=True,
            evidence_does_not_imply_actual_post_permission=True,
        )
    )
    assert result.status is GmoPaperTradeEvidenceStatus.PAPER_TRADE_EVIDENCE_NOT_READY
    assert "paper_trade_period_safe_label_missing" in result.blocked_reasons
    assert "paper_trade_run_count_safe_label_missing" in result.blocked_reasons


def test_paper_evidence_unknown_when_no_source_is_found() -> None:
    result = evaluate_gmo_paper_trade_evidence_criteria(
        GmoPaperTradeEvidenceCriteriaInput()
    )
    assert result.status is GmoPaperTradeEvidenceStatus.PAPER_TRADE_EVIDENCE_UNKNOWN
    assert result.blocked_reasons == ("paper_evidence_source_missing",)


def test_paper_evidence_does_not_allow_raw_value_or_id_exposure() -> None:
    result = evaluate_gmo_paper_trade_evidence_criteria(
        GmoPaperTradeEvidenceCriteriaInput(
            evidence_source_exists=True,
            evidence_location_safe_label_exists=True,
            paper_trade_period_safe_label_exists=True,
            paper_trade_run_count_safe_label_exists=True,
            paper_trade_result_category_safe_label_exists=True,
            evidence_reproducible_or_checked_by_report=True,
            evidence_relevant_to_gmo_live_entry_readiness=True,
            evidence_is_not_unrelated_backtest=True,
            evidence_does_not_imply_actual_post_permission=True,
            raw_profit_loss_values_exposed=True,
        )
    )
    assert result.status is GmoPaperTradeEvidenceStatus.PAPER_TRADE_EVIDENCE_NOT_READY
    assert "paper_evidence_raw_profit_loss_exposed" in result.blocked_reasons


def test_paper_evidence_safe_summary_defaults_to_not_provided() -> None:
    summary = build_gmo_live_paper_trade_evidence_safe_summary(
        GmoPaperTradeEvidenceCriteriaInput()
    )
    assert summary.paper_trade_evidence_status is (
        GmoPaperTradeEvidenceStatus.PAPER_TRADE_EVIDENCE_UNKNOWN
    )
    assert summary.paper_trade_period_safe_label == "NOT_PROVIDED"
    assert summary.paper_trade_run_count_safe_label == "NOT_PROVIDED"
    assert summary.paper_trade_result_category == "NOT_PROVIDED"
    assert summary.performance_report_location_safe_label == "NOT_PROVIDED"


def test_anomaly_evidence_confirmed_when_non_synthetic_and_all_blocks_covered() -> None:
    summary = build_gmo_live_kill_switch_anomaly_safe_summary(
        GmoKillSwitchAndSettlementAnomalyEvidenceInput(
            evidence_source_exists=True,
            kill_switch_failure_modes_safe_labels=("retry", "settlement_post"),
            settlement_reconciliation_failure_modes_safe_labels=("position_conflict",),
            tested_failure_modes_safe_labels=(
                "retry_blocked",
                "repost_blocked",
                "second_post_blocked",
                "settlement_post_blocked",
            ),
            kill_switch_test_scope_safe_label_exists=True,
            settlement_reconciliation_test_scope_safe_label_exists=True,
            retry_requested_blocked=True,
            repost_requested_blocked=True,
            second_post_requested_blocked=True,
            settlement_post_in_entry_step_blocked=True,
            generic_close_attempt_blocked=True,
            active_or_pending_order_conflict_blocked=True,
            position_count_nonzero_blocked=True,
            runtime_read_stale_blocked=True,
            runtime_read_unknown_blocked=True,
            missing_credential_boundary_blocked=True,
            unknown_result_no_retry_blocked=True,
            rejected_result_no_retry_blocked=True,
            timeout_result_no_retry_blocked=True,
            raw_id_value_exposure_attempt_blocked=True,
            fake_settlement_reconciliation_mismatch_blocked=True,
            fake_kill_switch_trigger_blocked=True,
            fake_no_order_guard_triggered_blocked=True,
            fake_level5_cycle_anomaly_blocked=True,
            synthetic_only=False,
            tested_failure_modes_distinguish_multiple_blocks=True,
            tested_failure_modes_distinguish_unknown_result_no_retry=True,
            evidence_does_not_imply_actual_post_permission=True,
        )
    )
    assert summary.kill_switch_anomaly_test_status is (
        GmoKillSwitchAndSettlementAnomalyEvidenceStatus.KILL_SWITCH_AND_SETTLEMENT_ANOMALY_TESTS_CONFIRMED
    )
    assert summary.synthetic_only is False
    assert summary.kill_switch_test_scope_safe_label == "NON_SYNTHETIC_SCOPE"
    assert "retry_blocked" in summary.tested_failure_modes_safe_labels


def test_anomaly_evidence_synthetic_only_is_not_sufficient() -> None:
    summary = build_gmo_live_kill_switch_anomaly_safe_summary(
        GmoKillSwitchAndSettlementAnomalyEvidenceInput(
            evidence_source_exists=True,
            kill_switch_failure_modes_safe_labels=("retry", "settlement_post"),
            settlement_reconciliation_failure_modes_safe_labels=("position_conflict",),
            tested_failure_modes_safe_labels=("retry_blocked",),
            kill_switch_test_scope_safe_label_exists=True,
            settlement_reconciliation_test_scope_safe_label_exists=True,
            retry_requested_blocked=True,
            repost_requested_blocked=True,
            second_post_requested_blocked=True,
            settlement_post_in_entry_step_blocked=True,
            generic_close_attempt_blocked=True,
            active_or_pending_order_conflict_blocked=True,
            position_count_nonzero_blocked=True,
            runtime_read_stale_blocked=True,
            runtime_read_unknown_blocked=True,
            missing_credential_boundary_blocked=True,
            unknown_result_no_retry_blocked=True,
            rejected_result_no_retry_blocked=True,
            timeout_result_no_retry_blocked=True,
            raw_id_value_exposure_attempt_blocked=True,
            fake_settlement_reconciliation_mismatch_blocked=True,
            fake_kill_switch_trigger_blocked=True,
            fake_no_order_guard_triggered_blocked=True,
            fake_level5_cycle_anomaly_blocked=True,
            tested_failure_modes_distinguish_multiple_blocks=True,
            tested_failure_modes_distinguish_unknown_result_no_retry=True,
            evidence_does_not_imply_actual_post_permission=True,
        )
    )
    assert summary.kill_switch_anomaly_test_status is (
        GmoKillSwitchAndSettlementAnomalyEvidenceStatus.SYNTHETIC_ONLY_NOT_SUFFICIENT
    )
    assert summary.synthetic_only is True
    assert summary.kill_switch_test_scope_safe_label == "SYNTHETIC_TESTS_ONLY"


def test_anomaly_not_ready_when_coverage_is_incomplete() -> None:
    result = evaluate_gmo_kill_switch_and_settlement_anomaly_criteria(
        GmoKillSwitchAndSettlementAnomalyEvidenceInput(
            evidence_source_exists=True,
            kill_switch_failure_modes_safe_labels=("retry",),
            settlement_reconciliation_failure_modes_safe_labels=("position_conflict",),
            tested_failure_modes_safe_labels=("retry_blocked",),
            kill_switch_test_scope_safe_label_exists=True,
            settlement_reconciliation_test_scope_safe_label_exists=True,
            retry_requested_blocked=True,
            repost_requested_blocked=True,
            second_post_requested_blocked=True,
            settlement_post_in_entry_step_blocked=True,
            generic_close_attempt_blocked=True,
            active_or_pending_order_conflict_blocked=True,
            position_count_nonzero_blocked=True,
            runtime_read_stale_blocked=True,
            runtime_read_unknown_blocked=True,
            missing_credential_boundary_blocked=True,
            unknown_result_no_retry_blocked=True,
            rejected_result_no_retry_blocked=True,
            timeout_result_no_retry_blocked=True,
            raw_id_value_exposure_attempt_blocked=True,
            fake_settlement_reconciliation_mismatch_blocked=True,
            fake_kill_switch_trigger_blocked=False,
            fake_no_order_guard_triggered_blocked=True,
            fake_level5_cycle_anomaly_blocked=True,
            tested_failure_modes_distinguish_multiple_blocks=True,
            tested_failure_modes_distinguish_unknown_result_no_retry=True,
            evidence_does_not_imply_actual_post_permission=True,
        )
    )
    assert result.status is GmoKillSwitchAndSettlementAnomalyEvidenceStatus.NOT_READY
    assert "fake_kill_switch_trigger_block_tests_missing" in result.blocked_reasons


def test_anomaly_unknown_when_source_missing() -> None:
    result = evaluate_gmo_kill_switch_and_settlement_anomaly_criteria(
        GmoKillSwitchAndSettlementAnomalyEvidenceInput()
    )
    assert result.status is GmoKillSwitchAndSettlementAnomalyEvidenceStatus.UNKNOWN
    assert result.blocked_reasons == ("anomaly_evidence_source_missing",)


def test_anomaly_evidence_does_not_allow_raw_response_or_ids() -> None:
    result = evaluate_gmo_kill_switch_and_settlement_anomaly_criteria(
        GmoKillSwitchAndSettlementAnomalyEvidenceInput(
            evidence_source_exists=True,
            kill_switch_failure_modes_safe_labels=("retry",),
            settlement_reconciliation_failure_modes_safe_labels=("position_conflict",),
            tested_failure_modes_safe_labels=("retry_blocked",),
            kill_switch_test_scope_safe_label_exists=True,
            settlement_reconciliation_test_scope_safe_label_exists=True,
            retry_requested_blocked=True,
            repost_requested_blocked=True,
            second_post_requested_blocked=True,
            settlement_post_in_entry_step_blocked=True,
            generic_close_attempt_blocked=True,
            active_or_pending_order_conflict_blocked=True,
            position_count_nonzero_blocked=True,
            runtime_read_stale_blocked=True,
            runtime_read_unknown_blocked=True,
            missing_credential_boundary_blocked=True,
            unknown_result_no_retry_blocked=True,
            rejected_result_no_retry_blocked=True,
            timeout_result_no_retry_blocked=True,
            raw_id_value_exposure_attempt_blocked=True,
            fake_settlement_reconciliation_mismatch_blocked=True,
            fake_kill_switch_trigger_blocked=True,
            fake_no_order_guard_triggered_blocked=True,
            fake_level5_cycle_anomaly_blocked=True,
            tested_failure_modes_distinguish_multiple_blocks=True,
            tested_failure_modes_distinguish_unknown_result_no_retry=True,
            evidence_does_not_imply_actual_post_permission=True,
            raw_response_exposed=True,
        )
    )
    assert result.status is GmoKillSwitchAndSettlementAnomalyEvidenceStatus.NOT_READY
    assert "raw_response_exposed" in result.blocked_reasons


def test_evidence_criteria_module_has_no_runtime_network_or_direct_credentials_reading() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    collapsed = text.replace(" ", "")
    assert "httpx" not in collapsed
    assert "os.environ" not in collapsed
    assert "getenv" not in collapsed
    assert "load_dotenv" not in collapsed
    assert "allow_real_broker_post=True" not in collapsed
    assert "allow_live_http_post=True" not in collapsed


def _load_json_fixture(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"fixture must be JSON object: {path}"
    return payload


def test_paper_evidence_can_be_confirmed_from_reproducible_no_post_artifact() -> None:
    fixture = _load_json_fixture(PAPER_SHADOW_FIXTURE_PATH)
    summary = build_gmo_live_paper_trade_evidence_safe_summary(
        GmoPaperTradeEvidenceCriteriaInput(
            evidence_source_exists=True,
            evidence_location_safe_label_exists=fixture[
                "evidence_location_safe_label_exists"
            ],
            paper_trade_period_safe_label_exists=True,
            paper_trade_run_count_safe_label_exists=True,
            paper_trade_result_category_safe_label_exists=True,
            evidence_reproducible_or_checked_by_report=fixture[
                "evidence_reproducible_or_checked_by_report"
            ],
            evidence_relevant_to_gmo_live_entry_readiness=fixture[
                "evidence_relevant_to_gmo_live_entry_readiness"
            ],
            evidence_is_not_unrelated_backtest=fixture[
                "evidence_is_not_unrelated_backtest"
            ],
            raw_profit_loss_values_exposed=fixture["raw_profit_loss_values_exposed"],
            raw_trade_ids_exposed=fixture["raw_trade_ids_exposed"],
            raw_order_ids_exposed=fixture["raw_order_ids_exposed"],
            raw_position_ids_exposed=fixture["raw_position_ids_exposed"],
            evidence_does_not_imply_actual_post_permission=fixture[
                "evidence_does_not_imply_actual_post_permission"
            ],
            paper_trade_period_safe_label=fixture["paper_trade_period_safe_label"],
            paper_trade_run_count_safe_label=fixture["paper_trade_run_count_safe_label"],
            paper_trade_result_category=fixture["paper_trade_result_category"],
            performance_report_location_safe_label=fixture[
                "performance_report_location_safe_label"
            ],
        )
    )
    assert summary.paper_trade_evidence_status is (
        GmoPaperTradeEvidenceStatus.PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY
    )
    assert summary.paper_trade_period_safe_label == fixture["paper_trade_period_safe_label"]
    assert summary.paper_trade_run_count_safe_label == fixture["paper_trade_run_count_safe_label"]
    assert summary.paper_trade_result_category == fixture["paper_trade_result_category"]
    assert (
        summary.performance_report_location_safe_label
        == fixture["performance_report_location_safe_label"]
    )


def test_anomaly_evidence_replay_artifact_reinforces_synthetic_only_limitation() -> None:
    fixture = _load_json_fixture(ANOMALY_REPLAY_FIXTURE_PATH)
    summary = build_gmo_live_kill_switch_anomaly_safe_summary(
        GmoKillSwitchAndSettlementAnomalyEvidenceInput(
            evidence_source_exists=True,
            kill_switch_failure_modes_safe_labels=tuple(
                fixture["kill_switch_failure_modes_safe_labels"]
            ),
            settlement_reconciliation_failure_modes_safe_labels=tuple(
                fixture["settlement_reconciliation_failure_modes_safe_labels"]
            ),
            tested_failure_modes_safe_labels=tuple(fixture["tested_failure_modes_safe_labels"]),
            kill_switch_test_scope_safe_label_exists=fixture[
                "kill_switch_test_scope_safe_label_exists"
            ],
            settlement_reconciliation_test_scope_safe_label_exists=fixture[
                "settlement_reconciliation_test_scope_safe_label_exists"
            ],
            retry_requested_blocked=fixture["retry_requested_blocked"],
            repost_requested_blocked=fixture["repost_requested_blocked"],
            second_post_requested_blocked=fixture["second_post_requested_blocked"],
            settlement_post_in_entry_step_blocked=fixture[
                "settlement_post_in_entry_step_blocked"
            ],
            generic_close_attempt_blocked=fixture["generic_close_attempt_blocked"],
            active_or_pending_order_conflict_blocked=fixture[
                "active_or_pending_order_conflict_blocked"
            ],
            position_count_nonzero_blocked=fixture["position_count_nonzero_blocked"],
            runtime_read_stale_blocked=fixture["runtime_read_stale_blocked"],
            runtime_read_unknown_blocked=fixture["runtime_read_unknown_blocked"],
            missing_credential_boundary_blocked=fixture[
                "missing_credential_boundary_blocked"
            ],
            unknown_result_no_retry_blocked=fixture["unknown_result_no_retry_blocked"],
            rejected_result_no_retry_blocked=fixture["rejected_result_no_retry_blocked"],
            timeout_result_no_retry_blocked=fixture["timeout_result_no_retry_blocked"],
            raw_id_value_exposure_attempt_blocked=fixture[
                "raw_id_value_exposure_attempt_blocked"
            ],
            fake_settlement_reconciliation_mismatch_blocked=fixture[
                "fake_settlement_reconciliation_mismatch_blocked"
            ],
            fake_kill_switch_trigger_blocked=fixture["fake_kill_switch_trigger_blocked"],
            fake_no_order_guard_triggered_blocked=fixture[
                "fake_no_order_guard_triggered_blocked"
            ],
            fake_level5_cycle_anomaly_blocked=fixture["fake_level5_cycle_anomaly_blocked"],
            synthetic_only=fixture["synthetic_only"],
            real_broker_write_used=fixture["real_broker_write_used"],
            raw_response_exposed=fixture["raw_response_exposed"],
            raw_ids_exposed=fixture["raw_ids_exposed"],
            raw_price_or_size_values_exposed=fixture["raw_price_or_size_values_exposed"],
            evidence_does_not_imply_actual_post_permission=fixture[
                "evidence_does_not_imply_actual_post_permission"
            ],
            tested_failure_modes_distinguish_multiple_blocks=fixture[
                "tested_failure_modes_distinguish_multiple_blocks"
            ],
            tested_failure_modes_distinguish_unknown_result_no_retry=fixture[
                "tested_failure_modes_distinguish_unknown_result_no_retry"
            ],
        )
    )
    assert summary.kill_switch_anomaly_test_status is (
        GmoKillSwitchAndSettlementAnomalyEvidenceStatus.SYNTHETIC_ONLY_NOT_SUFFICIENT
    )
    assert summary.real_broker_write_used is False
    assert summary.synthetic_only is True
    assert summary.raw_response_exposed is False
    assert summary.raw_ids_exposed is False
    assert summary.raw_price_or_size_values_exposed is False
    assert summary.kill_switch_test_scope_safe_label == "SYNTHETIC_TESTS_ONLY"
    assert summary.settlement_reconciliation_test_scope_safe_label == (
        "SYNTHETIC_TESTS_ONLY"
    )
    assert "raw_response_exposure_blocked" not in summary.tested_failure_modes_safe_labels
    assert "retry_blocked" in summary.tested_failure_modes_safe_labels
    assert (
        "fake_settlement_reconciliation_mismatch_blocked"
        in summary.tested_failure_modes_safe_labels
    )
