"""No-POST paper/shadow and anomaly evidence criteria models.

This file defines objective safe summary criteria that only use non-sensitive
safe labels and booleans. It does not read credentials, does not touch
`.env`, and does not perform any network calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

_NOT_PROVIDED = "NOT_PROVIDED"
_SYNTHETIC_ONLY_SCOPE = "SYNTHETIC_TESTS_ONLY"
_NON_SYNTHETIC_SCOPE = "NON_SYNTHETIC_SCOPE"


class GmoPaperTradeEvidenceStatus(str, Enum):
    """Objective paper/shadow evidence classification."""

    PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY = (
        "PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY"
    )
    PAPER_TRADE_EVIDENCE_NOT_READY = "PAPER_TRADE_EVIDENCE_NOT_READY"
    PAPER_TRADE_EVIDENCE_UNKNOWN = "PAPER_TRADE_EVIDENCE_UNKNOWN"


class GmoKillSwitchAndSettlementAnomalyEvidenceStatus(str, Enum):
    """Objective kill switch / settlement anomaly evidence classification."""

    KILL_SWITCH_AND_SETTLEMENT_ANOMALY_TESTS_CONFIRMED = (
        "KILL_SWITCH_AND_SETTLEMENT_ANOMALY_TESTS_CONFIRMED"
    )
    SYNTHETIC_ONLY_NOT_SUFFICIENT = "SYNTHETIC_ONLY_NOT_SUFFICIENT"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


def _safe_default(value: str) -> str:
    return value if value else _NOT_PROVIDED


def _scope_label(is_synthetic_only: bool, has_evidence: bool) -> str:
    if not has_evidence:
        return _NOT_PROVIDED
    return _SYNTHETIC_ONLY_SCOPE if is_synthetic_only else _NON_SYNTHETIC_SCOPE


def _all_safe(*labels: bool) -> bool:
    return all(labels)


def _contains_relevant_mode(*modes: str) -> bool:
    return any(modes)


@dataclass(frozen=True)
class GmoPaperTradeEvidenceCriteriaInput:
    """Inputs for objective paper/shadow evidence review."""

    evidence_source_exists: bool = False
    evidence_location_safe_label_exists: bool = False
    paper_trade_period_safe_label_exists: bool = False
    paper_trade_run_count_safe_label_exists: bool = False
    paper_trade_result_category_safe_label_exists: bool = False
    evidence_reproducible_or_checked_by_report: bool = False
    evidence_relevant_to_gmo_live_entry_readiness: bool = False
    evidence_is_not_unrelated_backtest: bool = False
    raw_profit_loss_values_exposed: bool = False
    raw_trade_ids_exposed: bool = False
    raw_order_ids_exposed: bool = False
    raw_position_ids_exposed: bool = False
    evidence_does_not_imply_actual_post_permission: bool = False
    paper_trade_period_safe_label: str = _NOT_PROVIDED
    paper_trade_run_count_safe_label: str = _NOT_PROVIDED
    paper_trade_result_category: str = _NOT_PROVIDED
    performance_report_location_safe_label: str = _NOT_PROVIDED


@dataclass(frozen=True)
class GmoPaperTradeEvidenceCriteriaResult:
    status: GmoPaperTradeEvidenceStatus
    blocked_reasons: tuple[str, ...]


@dataclass(frozen=True)
class GmoPaperTradeEvidenceSafeSummary:
    paper_trade_evidence_status: GmoPaperTradeEvidenceStatus
    paper_trade_period_safe_label: str
    paper_trade_run_count_safe_label: str
    paper_trade_result_category: str
    performance_report_location_safe_label: str
    raw_profit_loss_values_exposed: bool
    raw_trade_ids_exposed: bool
    raw_order_ids_exposed: bool
    raw_position_ids_exposed: bool


def evaluate_gmo_paper_trade_evidence_criteria(
    input_data: GmoPaperTradeEvidenceCriteriaInput,
) -> GmoPaperTradeEvidenceCriteriaResult:
    """Return objective paper evidence status from safe criteria only."""

    if not input_data.evidence_source_exists:
        return GmoPaperTradeEvidenceCriteriaResult(
            status=GmoPaperTradeEvidenceStatus.PAPER_TRADE_EVIDENCE_UNKNOWN,
            blocked_reasons=("paper_evidence_source_missing",),
        )

    blocked: list[str] = []
    if not input_data.evidence_location_safe_label_exists:
        blocked.append("paper_evidence_location_safe_label_missing")
    if not input_data.paper_trade_period_safe_label_exists:
        blocked.append("paper_trade_period_safe_label_missing")
    if not input_data.paper_trade_run_count_safe_label_exists:
        blocked.append("paper_trade_run_count_safe_label_missing")
    if not input_data.paper_trade_result_category_safe_label_exists:
        blocked.append("paper_trade_result_category_safe_label_missing")
    if not input_data.evidence_reproducible_or_checked_by_report:
        blocked.append("paper_evidence_not_reproducible_or_reported")
    if not input_data.evidence_relevant_to_gmo_live_entry_readiness:
        blocked.append("paper_evidence_not_relevant_to_entry_readiness")
    if not input_data.evidence_is_not_unrelated_backtest:
        blocked.append("paper_evidence_not_distinguishable_from_unrelated_backtest")
    if input_data.raw_profit_loss_values_exposed:
        blocked.append("paper_evidence_raw_profit_loss_exposed")
    if input_data.raw_trade_ids_exposed:
        blocked.append("paper_evidence_raw_trade_id_exposed")
    if input_data.raw_order_ids_exposed:
        blocked.append("paper_evidence_raw_order_id_exposed")
    if input_data.raw_position_ids_exposed:
        blocked.append("paper_evidence_raw_position_id_exposed")
    if not input_data.evidence_does_not_imply_actual_post_permission:
        blocked.append("paper_evidence_implies_actual_post_permission")

    status = GmoPaperTradeEvidenceStatus.PAPER_TRADE_EVIDENCE_NOT_READY
    if blocked:
        status = GmoPaperTradeEvidenceStatus.PAPER_TRADE_EVIDENCE_NOT_READY
    else:
        status = GmoPaperTradeEvidenceStatus.PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY

    return GmoPaperTradeEvidenceCriteriaResult(status=status, blocked_reasons=tuple(blocked))


def build_gmo_live_paper_trade_evidence_safe_summary(
    input_data: GmoPaperTradeEvidenceCriteriaInput,
) -> GmoPaperTradeEvidenceSafeSummary:
    criteria = evaluate_gmo_paper_trade_evidence_criteria(input_data)
    return GmoPaperTradeEvidenceSafeSummary(
        paper_trade_evidence_status=criteria.status,
        paper_trade_period_safe_label=_safe_default(input_data.paper_trade_period_safe_label),
        paper_trade_run_count_safe_label=_safe_default(
            input_data.paper_trade_run_count_safe_label
        ),
        paper_trade_result_category=_safe_default(input_data.paper_trade_result_category),
        performance_report_location_safe_label=_safe_default(
            input_data.performance_report_location_safe_label
        ),
        raw_profit_loss_values_exposed=input_data.raw_profit_loss_values_exposed,
        raw_trade_ids_exposed=input_data.raw_trade_ids_exposed,
        raw_order_ids_exposed=input_data.raw_order_ids_exposed,
        raw_position_ids_exposed=input_data.raw_position_ids_exposed,
    )


@dataclass(frozen=True)
class GmoKillSwitchAndSettlementAnomalyEvidenceInput:
    """Inputs for no-POST kill-switch and settlement-anomaly evidence review."""

    evidence_source_exists: bool = False
    kill_switch_failure_modes_safe_labels: tuple[str, ...] = ()
    settlement_reconciliation_failure_modes_safe_labels: tuple[str, ...] = ()
    kill_switch_test_scope_safe_label_exists: bool = False
    settlement_reconciliation_test_scope_safe_label_exists: bool = False
    retry_requested_blocked: bool = False
    repost_requested_blocked: bool = False
    second_post_requested_blocked: bool = False
    settlement_post_in_entry_step_blocked: bool = False
    generic_close_attempt_blocked: bool = False
    active_or_pending_order_conflict_blocked: bool = False
    position_count_nonzero_blocked: bool = False
    runtime_read_stale_blocked: bool = False
    runtime_read_unknown_blocked: bool = False
    missing_credential_boundary_blocked: bool = False
    unknown_result_no_retry_blocked: bool = False
    rejected_result_no_retry_blocked: bool = False
    timeout_result_no_retry_blocked: bool = False
    raw_id_value_exposure_attempt_blocked: bool = False
    fake_settlement_reconciliation_mismatch_blocked: bool = False
    fake_kill_switch_trigger_blocked: bool = False
    fake_no_order_guard_triggered_blocked: bool = False
    fake_level5_cycle_anomaly_blocked: bool = False
    synthetic_only: bool = True
    real_broker_write_used: bool = False
    raw_response_exposed: bool = False
    raw_ids_exposed: bool = False
    raw_price_or_size_values_exposed: bool = False
    tested_failure_modes_safe_labels: tuple[str, ...] = ()
    evidence_does_not_imply_actual_post_permission: bool = False
    tested_failure_modes_distinguish_multiple_blocks: bool = False
    tested_failure_modes_distinguish_unknown_result_no_retry: bool = False


@dataclass(frozen=True)
class GmoKillSwitchAndSettlementAnomalyEvidenceCriteriaResult:
    status: GmoKillSwitchAndSettlementAnomalyEvidenceStatus
    blocked_reasons: tuple[str, ...]


@dataclass(frozen=True)
class GmoKillSwitchAndSettlementAnomalyEvidenceSafeSummary:
    kill_switch_anomaly_test_status: GmoKillSwitchAndSettlementAnomalyEvidenceStatus
    kill_switch_test_scope_safe_label: str
    settlement_reconciliation_test_scope_safe_label: str
    tested_failure_modes_safe_labels: tuple[str, ...]
    synthetic_only: bool
    real_broker_write_used: bool
    raw_response_exposed: bool
    raw_ids_exposed: bool
    raw_price_or_size_values_exposed: bool
    evidence_does_not_imply_actual_post_permission: bool


def evaluate_gmo_kill_switch_and_settlement_anomaly_criteria(
    input_data: GmoKillSwitchAndSettlementAnomalyEvidenceInput,
) -> GmoKillSwitchAndSettlementAnomalyEvidenceCriteriaResult:
    """Return objective anomaly status from safe criteria only."""

    if not input_data.evidence_source_exists:
        return GmoKillSwitchAndSettlementAnomalyEvidenceCriteriaResult(
            status=GmoKillSwitchAndSettlementAnomalyEvidenceStatus.UNKNOWN,
            blocked_reasons=("anomaly_evidence_source_missing",),
        )

    blocked: list[str] = []
    if not input_data.kill_switch_failure_modes_safe_labels:
        blocked.append("kill_switch_failure_modes_missing")
    if not input_data.settlement_reconciliation_failure_modes_safe_labels:
        blocked.append("settlement_reconciliation_failure_modes_missing")
    if not _contains_relevant_mode(*input_data.kill_switch_failure_modes_safe_labels):
        blocked.append("kill_switch_failure_modes_safe_labels_missing")
    if not _contains_relevant_mode(
        *input_data.settlement_reconciliation_failure_modes_safe_labels
    ):
        blocked.append("settlement_reconciliation_failure_modes_safe_labels_missing")
    if not _all_safe(
        input_data.retry_requested_blocked,
        input_data.repost_requested_blocked,
        input_data.second_post_requested_blocked,
    ):
        blocked.append("retry_repost_second_post_block_tests_missing")
    if not input_data.settlement_post_in_entry_step_blocked:
        blocked.append("settlement_post_in_entry_step_block_tests_missing")
    if not input_data.generic_close_attempt_blocked:
        blocked.append("generic_close_request_block_tests_missing")
    if not input_data.active_or_pending_order_conflict_blocked:
        blocked.append("active_pending_conflict_block_tests_missing")
    if not input_data.position_count_nonzero_blocked:
        blocked.append("position_count_nonzero_block_tests_missing")
    if not input_data.runtime_read_stale_blocked:
        blocked.append("runtime_read_stale_block_tests_missing")
    if not input_data.runtime_read_unknown_blocked:
        blocked.append("runtime_read_unknown_block_tests_missing")
    if not input_data.missing_credential_boundary_blocked:
        blocked.append("missing_credential_block_tests_missing")
    if not _all_safe(
        input_data.unknown_result_no_retry_blocked,
        input_data.rejected_result_no_retry_blocked,
        input_data.timeout_result_no_retry_blocked,
    ):
        blocked.append("result_timeout_rejected_unknown_no_retry_tests_missing")
    if not input_data.raw_id_value_exposure_attempt_blocked:
        blocked.append("raw_id_value_exposure_block_tests_missing")
    if not input_data.fake_settlement_reconciliation_mismatch_blocked:
        blocked.append("fake_settlement_reconciliation_mismatch_block_tests_missing")
    if not input_data.fake_kill_switch_trigger_blocked:
        blocked.append("fake_kill_switch_trigger_block_tests_missing")
    if not input_data.fake_no_order_guard_triggered_blocked:
        blocked.append("fake_no_order_guard_trigger_tests_missing")
    if not input_data.fake_level5_cycle_anomaly_blocked:
        blocked.append("fake_level5_cycle_anomaly_block_tests_missing")
    if not input_data.tested_failure_modes_distinguish_multiple_blocks:
        blocked.append("failure_mode_distinguish_multiple_failures_missing")
    if not input_data.tested_failure_modes_distinguish_unknown_result_no_retry:
        blocked.append("failure_mode_unknown_result_no_retry_distinction_missing")
    if not input_data.evidence_does_not_imply_actual_post_permission:
        blocked.append("anomaly_evidence_implies_actual_post_permission")
    if not input_data.kill_switch_test_scope_safe_label_exists:
        blocked.append("kill_switch_test_scope_safe_label_missing")
    if not input_data.settlement_reconciliation_test_scope_safe_label_exists:
        blocked.append("settlement_reconciliation_test_scope_safe_label_missing")

    if input_data.raw_response_exposed:
        blocked.append("raw_response_exposed")
    if input_data.raw_ids_exposed:
        blocked.append("raw_ids_exposed")
    if input_data.raw_price_or_size_values_exposed:
        blocked.append("raw_price_or_size_values_exposed")
    if input_data.real_broker_write_used:
        blocked.append("real_broker_write_used")
    if not input_data.tested_failure_modes_safe_labels:
        blocked.append("tested_failure_modes_safe_labels_missing")
    else:
        # Keep this as a distinct reason for reporting when no per-mode test list is
        # configured by this specific result channel.
        pass

    if blocked:
        return GmoKillSwitchAndSettlementAnomalyEvidenceCriteriaResult(
            status=GmoKillSwitchAndSettlementAnomalyEvidenceStatus.NOT_READY,
            blocked_reasons=tuple(blocked),
        )

    if input_data.synthetic_only:
        return GmoKillSwitchAndSettlementAnomalyEvidenceCriteriaResult(
            status=GmoKillSwitchAndSettlementAnomalyEvidenceStatus.SYNTHETIC_ONLY_NOT_SUFFICIENT,
            blocked_reasons=(),
        )

    return GmoKillSwitchAndSettlementAnomalyEvidenceCriteriaResult(
        status=GmoKillSwitchAndSettlementAnomalyEvidenceStatus.KILL_SWITCH_AND_SETTLEMENT_ANOMALY_TESTS_CONFIRMED,
        blocked_reasons=(),
    )


def build_gmo_live_kill_switch_anomaly_safe_summary(
    input_data: GmoKillSwitchAndSettlementAnomalyEvidenceInput,
) -> GmoKillSwitchAndSettlementAnomalyEvidenceSafeSummary:
    """Build a safe summary without raw values or raw IDs."""

    criteria = evaluate_gmo_kill_switch_and_settlement_anomaly_criteria(input_data)
    return GmoKillSwitchAndSettlementAnomalyEvidenceSafeSummary(
        kill_switch_anomaly_test_status=criteria.status,
        kill_switch_test_scope_safe_label=_scope_label(
            is_synthetic_only=input_data.synthetic_only,
            has_evidence=_contains_relevant_mode(
                *input_data.kill_switch_failure_modes_safe_labels
            ),
        ),
        settlement_reconciliation_test_scope_safe_label=_scope_label(
            is_synthetic_only=input_data.synthetic_only,
            has_evidence=_contains_relevant_mode(
                *input_data.settlement_reconciliation_failure_modes_safe_labels
            ),
        ),
        tested_failure_modes_safe_labels=_safe_default_labels(
            input_data.tested_failure_modes_safe_labels
        ),
        synthetic_only=input_data.synthetic_only,
        real_broker_write_used=input_data.real_broker_write_used,
        raw_response_exposed=input_data.raw_response_exposed,
        raw_ids_exposed=input_data.raw_ids_exposed,
        raw_price_or_size_values_exposed=input_data.raw_price_or_size_values_exposed,
        evidence_does_not_imply_actual_post_permission=(
            input_data.evidence_does_not_imply_actual_post_permission
        ),
    )


def _safe_default_labels(labels: tuple[str, ...]) -> tuple[str, ...]:
    if not labels:
        return (_NOT_PROVIDED,)
    return labels
