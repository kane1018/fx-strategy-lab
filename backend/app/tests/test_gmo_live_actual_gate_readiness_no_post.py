"""No-POST tests for GMO live actual entry/settlement gate readiness summaries.

These tests validate strict, value-less permit/readiness modeling for a future real
POST step while preserving no-POST and no-credential boundaries.
"""

from __future__ import annotations

import pathlib

from app.services.gmo_live_actual_gate_readiness import (
    GmoActualEntryGateReadinessStatus,
    GmoActualSettlementGateReadinessStatus,
    GmoPermitKind,
    GmoPermitStatus,
    GmoPreActualSupportAnswerStatus,
    build_gmo_live_actual_entry_gate_readiness_summary,
    build_gmo_live_actual_settlement_gate_readiness_summary,
    build_gmo_live_entry_permit,
    build_gmo_live_settlement_permit,
)
from app.services.gmo_live_credential_boundary import (
    build_gmo_live_credential_boundary_snapshot,
)
from app.services.gmo_live_pre_actual_readiness import GmoCloseOrderSideSemanticsStatus
from app.services.gmo_live_runner_boundary import GmoLiveRunnerBoundaryResult
from app.services.risk_service import GmoLiveReadinessShadowResult

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_actual_gate_readiness.py"
)


def _runner_summary(
    *,
    entry: bool = True,
    settlement: bool = True,
) -> GmoLiveRunnerBoundaryResult:
    return GmoLiveRunnerBoundaryResult(
        runner_may_start_gmo_live_entry=entry,
        runner_may_start_gmo_live_settlement=settlement,
        process_start_default_off_enforced=False,
        blocked_reasons=(),
        settlement_blocked_reasons=(),
    )


def _shadow_result(
    *,
    entry: bool = True,
    settlement: bool = True,
) -> GmoLiveReadinessShadowResult:
    return GmoLiveReadinessShadowResult(
        entry_shadow_allowed=entry,
        settlement_shadow_allowed=settlement,
        blocked_reasons=(),
    )


def test_entry_permit_ready_only_when_preconditions_met() -> None:
    permit = build_gmo_live_entry_permit(
        operator_signal_safe_label_exists=True,
        pre_entry_open_positions_count=0,
        pre_entry_active_or_pending_order_conflict_count=0,
        max_entry_post_count=1,
        settlement_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    assert permit.permit_kind is GmoPermitKind.ENTRY
    assert permit.permit_status is GmoPermitStatus.READY
    assert permit.permit_ready is True
    assert permit.has_entry_preconditions is True
    assert bool(permit) is False


def test_entry_permit_blocked_when_operator_signal_is_missing() -> None:
    permit = build_gmo_live_entry_permit(
        operator_signal_safe_label_exists=False,
        pre_entry_open_positions_count=0,
        pre_entry_active_or_pending_order_conflict_count=0,
        max_entry_post_count=1,
        settlement_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    assert permit.permit_ready is False
    assert permit.permit_status is GmoPermitStatus.BLOCKED_BY_OPERATOR_CONFIRMATION


def test_settlement_permit_ready_only_when_requirements_met() -> None:
    permit = build_gmo_live_settlement_permit(
        pre_settlement_open_positions_count=1,
        pre_settlement_active_or_pending_order_conflict_count=0,
        settlement_route_required=True,
        generic_close_forbidden=True,
        side_provenance_ready=True,
        side_docs_confirmed=True,
        max_settlement_post_count=1,
        entry_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    assert permit.permit_kind is GmoPermitKind.OFFICIAL_SETTLEMENT
    assert permit.permit_status is GmoPermitStatus.READY
    assert permit.permit_ready is True
    assert permit.has_settlement_preconditions is True
    assert bool(permit) is False


def test_settlement_permit_blocked_without_settlement_route() -> None:
    permit = build_gmo_live_settlement_permit(
        pre_settlement_open_positions_count=1,
        pre_settlement_active_or_pending_order_conflict_count=0,
        settlement_route_required=False,
        generic_close_forbidden=True,
        side_provenance_ready=True,
        side_docs_confirmed=True,
        max_settlement_post_count=1,
        entry_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    assert permit.permit_ready is False
    assert permit.permit_status is GmoPermitStatus.BLOCKED_BY_GUARD_SETTINGS


def test_entry_gate_readiness_ready_when_all_inputs_safe() -> None:
    permit = build_gmo_live_entry_permit(
        operator_signal_safe_label_exists=True,
        pre_entry_open_positions_count=0,
        pre_entry_active_or_pending_order_conflict_count=0,
        max_entry_post_count=1,
        settlement_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    summary = build_gmo_live_actual_entry_gate_readiness_summary(
        runner_summary=_runner_summary(),
        shadow_result=_shadow_result(),
        credential_boundary=build_gmo_live_credential_boundary_snapshot(
            sealed_provider_ready=True,
        ),
        permit=permit,
        gmo_live_enable_policy_ready=True,
    )

    assert summary.actual_entry_gate_ready is True
    assert (
        summary.status
        is GmoActualEntryGateReadinessStatus.ACTUAL_ENTRY_GATE_DESIGN_READY_NO_POST
    )
    assert summary.permit.permit_ready is True
    assert summary.runner_boundary_ready is True
    assert summary.credential_boundary_ready is True
    assert summary.max_consecutive_losses_selected == 2
    assert summary.actual_entry_POST_allowed is False


def test_entry_gate_readiness_blocked_when_credential_boundary_not_ready() -> None:
    permit = build_gmo_live_entry_permit(
        operator_signal_safe_label_exists=True,
        pre_entry_open_positions_count=0,
        pre_entry_active_or_pending_order_conflict_count=0,
        max_entry_post_count=1,
        settlement_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    summary = build_gmo_live_actual_entry_gate_readiness_summary(
        runner_summary=_runner_summary(),
        shadow_result=_shadow_result(),
        credential_boundary=build_gmo_live_credential_boundary_snapshot(),
        permit=permit,
        gmo_live_enable_policy_ready=True,
    )

    assert summary.actual_entry_gate_ready is False
    assert (
        summary.status
        is GmoActualEntryGateReadinessStatus.ACTUAL_ENTRY_GATE_BLOCKED_BY_CREDENTIAL_BOUNDARY
    )
    assert "credential_boundary_not_ready" in summary.blocked_reasons


def test_settlement_gate_readiness_ready_when_all_inputs_safe() -> None:
    permit = build_gmo_live_settlement_permit(
        pre_settlement_open_positions_count=1,
        pre_settlement_active_or_pending_order_conflict_count=0,
        settlement_route_required=True,
        generic_close_forbidden=True,
        side_provenance_ready=True,
        side_docs_confirmed=True,
        max_settlement_post_count=1,
        entry_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    summary = build_gmo_live_actual_settlement_gate_readiness_summary(
        runner_summary=_runner_summary(),
        shadow_result=_shadow_result(),
        credential_boundary=build_gmo_live_credential_boundary_snapshot(
            sealed_provider_ready=True,
        ),
        permit=permit,
        support_answer_status=GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_OPPOSITE_SIDE,
        settlement_side_status=GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE,
    )

    assert summary.actual_settlement_gate_ready is True
    assert (
        summary.status
        is GmoActualSettlementGateReadinessStatus.ACTUAL_SETTLEMENT_GATE_DESIGN_READY_NO_POST
    )
    assert summary.permit.permit_ready is True
    assert summary.runner_boundary_ready is True
    assert summary.risk_shadow_settlement_allowed is True
    assert summary.side_provenance_correction_required is False
    assert summary.size_only_one_position_settlement_candidate_ready is True
    assert summary.size_only_multiple_position_targeting_block_retained is False
    assert summary.size_only_dual_position_targeting_block_retained is False
    assert summary.position_specific_actual_path_enabled is False
    assert summary.full_cycle_design_ready_no_post is True
    assert summary.actual_settlement_POST_allowed is False
    assert summary.entry_only_actual_post_recommended is False


def test_settlement_gate_readiness_blocked_when_support_not_received() -> None:
    permit = build_gmo_live_settlement_permit(
        pre_settlement_open_positions_count=1,
        pre_settlement_active_or_pending_order_conflict_count=0,
        settlement_route_required=True,
        generic_close_forbidden=True,
        side_provenance_ready=True,
        side_docs_confirmed=True,
        max_settlement_post_count=1,
        entry_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    summary = build_gmo_live_actual_settlement_gate_readiness_summary(
        runner_summary=_runner_summary(),
        shadow_result=_shadow_result(),
        credential_boundary=build_gmo_live_credential_boundary_snapshot(
            sealed_provider_ready=True,
        ),
        permit=permit,
        support_answer_status=GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED,
        settlement_side_status=GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_STILL_UNCONFIRMED,
    )

    assert summary.actual_settlement_gate_ready is False
    assert (
        summary.status
        is (
            GmoActualSettlementGateReadinessStatus
            .ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_SUPPORT_NOT_RECEIVED
        )
    )
    assert "support_answer_not_received" in summary.blocked_reasons


def test_settlement_gate_readiness_blocks_when_side_provenance_correction_required() -> None:
    permit = build_gmo_live_settlement_permit(
        pre_settlement_open_positions_count=1,
        pre_settlement_active_or_pending_order_conflict_count=0,
        settlement_route_required=True,
        generic_close_forbidden=True,
        side_provenance_ready=False,
        side_docs_confirmed=True,
        max_settlement_post_count=1,
        entry_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    summary = build_gmo_live_actual_settlement_gate_readiness_summary(
        runner_summary=_runner_summary(),
        shadow_result=_shadow_result(),
        credential_boundary=build_gmo_live_credential_boundary_snapshot(
            sealed_provider_ready=True,
        ),
        permit=permit,
        support_answer_status=(
            GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_POSITION_SIDE
        ),
        settlement_side_status=(
            GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_POSITION_SIDE
        ),
    )

    assert (
        summary.status
        is (
            GmoActualSettlementGateReadinessStatus
            .ACTUAL_SETTLEMENT_GATE_BLOCKED_BY_SIDE_PROVENANCE_CORRECTION_REQUIRED
        )
    )
    assert summary.side_provenance_correction_required is True
    assert summary.full_cycle_design_ready_no_post is False
    assert summary.actual_settlement_POST_allowed is False


def test_settlement_gate_full_cycle_flags_for_multiple_positions() -> None:
    permit = build_gmo_live_settlement_permit(
        pre_settlement_open_positions_count=2,
        pre_settlement_active_or_pending_order_conflict_count=0,
        settlement_route_required=True,
        generic_close_forbidden=True,
        side_provenance_ready=True,
        side_docs_confirmed=True,
        max_settlement_post_count=1,
        entry_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    summary = build_gmo_live_actual_settlement_gate_readiness_summary(
        runner_summary=_runner_summary(),
        shadow_result=_shadow_result(),
        credential_boundary=build_gmo_live_credential_boundary_snapshot(
            sealed_provider_ready=True,
        ),
        permit=permit,
        support_answer_status=(
            GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_OPPOSITE_SIDE
        ),
        settlement_side_status=GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE,
    )

    assert summary.actual_settlement_gate_ready is False
    assert summary.size_only_one_position_settlement_candidate_ready is False
    assert summary.size_only_multiple_position_targeting_block_retained is True
    assert summary.size_only_dual_position_targeting_block_retained is True
    assert summary.position_specific_actual_path_enabled is False
    assert summary.full_cycle_design_ready_no_post is False
    assert summary.actual_settlement_POST_allowed is False
    assert (
        "operator_size_only_closeOrder_dual_position_targeting="
        "SETTLE_POSITION_REQUIRED_FOR_DUAL_OR_MULTIPLE_POSITIONS"
        in summary.blocked_reasons
    )


def test_settlement_gate_without_dual_position_label_when_one_position_is_candidate() -> None:
    permit = build_gmo_live_settlement_permit(
        pre_settlement_open_positions_count=1,
        pre_settlement_active_or_pending_order_conflict_count=0,
        settlement_route_required=True,
        generic_close_forbidden=True,
        side_provenance_ready=True,
        side_docs_confirmed=True,
        max_settlement_post_count=1,
        entry_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    summary = build_gmo_live_actual_settlement_gate_readiness_summary(
        runner_summary=_runner_summary(),
        shadow_result=_shadow_result(),
        credential_boundary=build_gmo_live_credential_boundary_snapshot(
            sealed_provider_ready=True,
        ),
        permit=permit,
        support_answer_status=(
            GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_OPPOSITE_SIDE
        ),
        settlement_side_status=GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE,
    )

    assert (
        "operator_size_only_closeOrder_dual_position_targeting="
        "SETTLE_POSITION_REQUIRED_FOR_DUAL_OR_MULTIPLE_POSITIONS"
        not in summary.blocked_reasons
    )


def test_settlement_gate_full_cycle_flags_for_active_pending_conflict() -> None:
    permit = build_gmo_live_settlement_permit(
        pre_settlement_open_positions_count=1,
        pre_settlement_active_or_pending_order_conflict_count=1,
        settlement_route_required=True,
        generic_close_forbidden=True,
        side_provenance_ready=True,
        side_docs_confirmed=True,
        max_settlement_post_count=1,
        entry_post_not_allowed=True,
        retry_allowed=False,
        repost_allowed=False,
        manual_intervention_performed=False,
    )

    summary = build_gmo_live_actual_settlement_gate_readiness_summary(
        runner_summary=_runner_summary(),
        shadow_result=_shadow_result(),
        credential_boundary=build_gmo_live_credential_boundary_snapshot(
            sealed_provider_ready=True,
        ),
        permit=permit,
        support_answer_status=(
            GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_OPPOSITE_SIDE
        ),
        settlement_side_status=GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE,
    )

    assert summary.actual_settlement_gate_ready is False
    assert summary.size_only_one_position_settlement_candidate_ready is False
    assert summary.full_cycle_design_ready_no_post is False


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_does_not_read_env_or_network_client() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "httpx" not in text
    assert "requests" not in text


def test_module_has_no_production_allow_true_wiring() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text


def test_module_keeps_actual_post_fail_closed_fields_hardcoded_false() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "actual_settlement_POST_allowed=False" in text
    assert "actual_settlement_POST_allowed=True" not in text
    assert "actual_entry_POST_allowed=False" in text
    assert "actual_entry_POST_allowed=True" not in text
    assert "position_specific_actual_path_enabled=False" in text
    assert "position_specific_actual_path_enabled=True" not in text
    assert "entry_only_actual_post_recommended=False" in text
    assert "entry_only_actual_post_recommended=True" not in text
