"""No-POST evidence criteria and safe summary tests for paper/shadow evidence.

These tests validate objective safe-label criteria for reporting and make sure the
new helpers remain value-less and code-safe.
"""

from __future__ import annotations

import pathlib

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
