"""No-POST planning tests for GMO live pre-actual convergence readiness."""

from __future__ import annotations

from pathlib import Path

from app.services.gmo_live_pre_actual_readiness import (
    GmoCloseOrderSideSemanticsStatus,
    GmoPreActualNextStep,
    GmoPreActualReadinessInput,
    GmoPreActualServiceWiringStatus,
    GmoPreActualSupportAnswerStatus,
    build_gmo_live_pre_actual_cycle_readiness_summary,
    build_gmo_live_pre_actual_entry_readiness_summary,
    classify_gmo_live_pre_actual_blockers,
    normalize_support_answer_status,
)

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_pre_actual_readiness.py"
)


def test_default_summary_is_not_live_ready_and_flags_settled_side_docs_blocked() -> None:
    summary = build_gmo_live_pre_actual_entry_readiness_summary()

    assert summary.pre_actual_readiness_ready is False
    assert summary.actual_entry_gate_ready is False
    assert summary.actual_settlement_gate_ready is False
    assert summary.settlement_side_official_docs_semantics_confirmed is False
    assert (
        summary.support_answer_status
        is GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED
    )
    assert summary.settlement_side_docs_status is (
        GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_STILL_UNCONFIRMED
    )
    assert "SUPPORT_ANSWER_NOT_RECEIVED" in summary.blocked_reasons
    assert "SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED" in summary.blocked_reasons


def test_side_docs_not_confirmed_blocks_settlement_readiness() -> None:
    summary = build_gmo_live_pre_actual_entry_readiness_summary(
        GmoPreActualReadinessInput(
            closeOrder_side_semantics_status=GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE,
            actual_settlement_gate_ready=True,
            credential_boundary_ready=True,
            actual_entry_gate_ready=True,
        )
    )

    assert summary.actual_settlement_gate_ready is False
    assert "SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED" in summary.blocked_reasons


def test_support_not_received_keeps_settlement_blocked() -> None:
    summary = build_gmo_live_pre_actual_entry_readiness_summary(
        GmoPreActualReadinessInput(
            support_answer_status=GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED,
            settlement_side_official_docs_semantics_confirmed=True,
            actual_entry_gate_ready=True,
            actual_settlement_gate_ready=True,
            credential_boundary_ready=True,
        )
    )

    assert summary.settlement_side_official_docs_semantics_confirmed is True
    assert "SUPPORT_ANSWER_NOT_RECEIVED" in summary.blocked_reasons
    assert summary.actual_settlement_gate_ready is False


def test_support_answer_position_side_is_classified_as_side_provenance_correction_needed() -> None:
    summary = build_gmo_live_pre_actual_entry_readiness_summary(
        GmoPreActualReadinessInput(
            support_answer_status=(
                GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_POSITION_SIDE
            ),
            actual_entry_gate_ready=True,
            actual_settlement_gate_ready=True,
            credential_boundary_ready=True,
            gmo_live_enable_policy_ready=True,
        )
    )

    assert (
        summary.settlement_side_docs_status
        is GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_POSITION_SIDE
    )
    assert summary.settlement_side_official_docs_semantics_confirmed is False
    assert summary.side_provenance_correction_required is True
    assert "SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED" in summary.blocked_reasons


def test_support_answer_opposite_side_is_consistent_and_no_correction_needed() -> None:
    summary = build_gmo_live_pre_actual_entry_readiness_summary(
        GmoPreActualReadinessInput(
            support_answer_status=(
                GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_OPPOSITE_SIDE
            ),
            actual_entry_gate_ready=True,
            actual_settlement_gate_ready=True,
            credential_boundary_ready=True,
            gmo_live_enable_policy_ready=True,
            readonly_snapshot_adapter_ready=True,
            settlement_reconciliation_ready=True,
        )
    )

    assert (
        summary.settlement_side_docs_status
        is GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE
    )
    assert summary.side_provenance_correction_required is False


def test_raw_support_text_is_unsafe_and_rejected() -> None:
    safe_status = normalize_support_answer_status("Buyはこうです")
    summary = build_gmo_live_pre_actual_entry_readiness_summary(
        GmoPreActualReadinessInput(
            support_answer_status=safe_status,
            actual_entry_gate_ready=True,
            actual_settlement_gate_ready=True,
            credential_boundary_ready=True,
            gmo_live_enable_policy_ready=True,
        )
    )

    assert safe_status is GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED
    assert (
        summary.support_answer_status
        is GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED
    )
    assert summary.support_answer_safe_label_capture_ready is False
    assert "SUPPORT_ANSWER_UNSAFE_RAW_TEXT" in summary.blocked_reasons


def test_max_consecutive_losses_selected_reflected_and_invalid_blocked() -> None:
    selected_two = build_gmo_live_pre_actual_entry_readiness_summary(
        GmoPreActualReadinessInput(
            actual_entry_gate_ready=True,
            gmo_live_enable_policy_ready=True,
            credential_boundary_ready=True,
        )
    )
    assert selected_two.max_consecutive_losses_selected == 2
    assert selected_two.max_consecutive_losses_decision == (
        "MINIMAL_START_MAX_CONSECUTIVE_LOSSES_2"
    )

    selected_three = build_gmo_live_pre_actual_entry_readiness_summary(
        GmoPreActualReadinessInput(
            max_consecutive_losses_selected=3,
            actual_entry_gate_ready=True,
            gmo_live_enable_policy_ready=True,
            credential_boundary_ready=True,
        )
    )
    assert selected_three.max_consecutive_losses_selected == 3
    assert selected_three.max_consecutive_losses_decision == (
        "MINIMAL_START_MAX_CONSECUTIVE_LOSSES_3"
    )

    invalid = build_gmo_live_pre_actual_entry_readiness_summary(
        GmoPreActualReadinessInput(
            max_consecutive_losses_selected=5,
            actual_entry_gate_ready=True,
            gmo_live_enable_policy_ready=True,
            credential_boundary_ready=True,
        )
    )
    assert invalid.max_consecutive_losses_decision == (
        "INVALID_MAX_CONSECUTIVE_LOSSES_SELECTION"
    )
    assert "MAX_CONSECUTIVE_LOSSES_SELECTION_INVALID" in invalid.blocked_reasons


def test_service_wiring_policy_and_no_post_hook_plan_are_reflected() -> None:
    summary = build_gmo_live_pre_actual_entry_readiness_summary(
        GmoPreActualReadinessInput(
            actual_entry_gate_ready=True,
            gmo_live_enable_policy_ready=True,
            credential_boundary_ready=True,
            support_answer_status=(
                GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED
            ),
        )
    )

    assert summary.service_wiring_policy == "DESIGN_FIRST_NO_CODE"
    assert (
        summary.service_wiring_status
        is GmoPreActualServiceWiringStatus.SERVICE_WIRING_CAN_PROCEED_TO_NO_POST_HOOK
    )
    assert (
        summary.recommended_next_step
        is GmoPreActualNextStep.NEXT_STEP_SERVICE_NO_POST_HOOK_WIRING
    )
    assert len(summary.proposed_hook_points) >= 1


def test_credential_boundary_false_keeps_live_entry_blocked() -> None:
    summary = build_gmo_live_pre_actual_entry_readiness_summary(
        GmoPreActualReadinessInput(
            actual_entry_gate_ready=True,
            gmo_live_enable_policy_ready=True,
            credential_boundary_ready=False,
        )
    )

    assert summary.credential_boundary_ready is False
    assert summary.actual_entry_gate_ready is False
    assert "CREDENTIAL_BOUNDARY_NOT_READY" in summary.blocked_reasons


def test_cycle_alias_returns_same_ready_snapshot_shape() -> None:
    entry_summary = build_gmo_live_pre_actual_entry_readiness_summary()
    cycle_summary = build_gmo_live_pre_actual_cycle_readiness_summary()

    assert cycle_summary == entry_summary


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_no_production_allow_true_wiring_in_module() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text


def test_blocker_classifier_includes_side_and_support_rules() -> None:
    reasons = classify_gmo_live_pre_actual_blockers(
        GmoPreActualReadinessInput(
            settlement_side_official_docs_semantics_confirmed=False,
            support_answer_status=GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED,
            actual_entry_gate_ready=True,
            actual_settlement_gate_ready=True,
            gmo_live_enable_policy_ready=True,
            credential_boundary_ready=True,
        )
    )
    assert "SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED" in reasons
    assert "SUPPORT_ANSWER_NOT_RECEIVED" in reasons
