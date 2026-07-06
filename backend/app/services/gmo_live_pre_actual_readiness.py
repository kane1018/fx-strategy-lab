"""Pre-actual live-readiness convergence helpers for GMO live execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.gmo_live_safety_policy import (
    GmoLiveRiskConfig,
    classify_max_consecutive_losses_decision_status,
)


class GmoPreActualSupportAnswerStatus(str, Enum):
    """Safe labels used when operator provides GMO support answer."""

    SUPPORT_ANSWER_NOT_RECEIVED = "SUPPORT_ANSWER_NOT_RECEIVED"
    SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_POSITION_SIDE = (
        "SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_POSITION_SIDE"
    )
    SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_OPPOSITE_SIDE = (
        "SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_OPPOSITE_SIDE"
    )
    SUPPORT_ANSWER_AMBIGUOUS = "SUPPORT_ANSWER_AMBIGUOUS"
    SUPPORT_ANSWER_CONFLICTING = "SUPPORT_ANSWER_CONFLICTING"
    SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED = (
        "SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED"
    )


class GmoCloseOrderSideSemanticsStatus(str, Enum):
    """Safe, bounded labels for `/private/v1/closeOrder` side semantics."""

    SIDE_DOCS_STILL_UNCONFIRMED = "SIDE_DOCS_STILL_UNCONFIRMED"
    SIDE_SEMANTICS_CONFIRMED_POSITION_SIDE = (
        "SIDE_SEMANTICS_CONFIRMED_POSITION_SIDE"
    )
    SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE = (
        "SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE"
    )
    SIDE_DOCS_CONFLICT_OR_AMBIGUOUS = "SIDE_DOCS_CONFLICT_OR_AMBIGUOUS"


class GmoPreActualServiceWiringStatus(str, Enum):
    SERVICE_WIRING_DESIGN_READY = "SERVICE_WIRING_DESIGN_READY"
    SERVICE_WIRING_CAN_PROCEED_TO_NO_POST_HOOK = (
        "SERVICE_WIRING_CAN_PROCEED_TO_NO_POST_HOOK"
    )
    SERVICE_WIRING_BLOCKED_BY_SIDE_DOCS = "SERVICE_WIRING_BLOCKED_BY_SIDE_DOCS"
    SERVICE_WIRING_BLOCKED_BY_EXISTING_OANDA_SQLALCHEMY_COUPLING = (
        "SERVICE_WIRING_BLOCKED_BY_EXISTING_OANDA_SQLALCHEMY_COUPLING"
    )
    SERVICE_WIRING_OPERATOR_DECISION_REQUIRED = (
        "SERVICE_WIRING_OPERATOR_DECISION_REQUIRED"
    )


class GmoPreActualNextStep(str, Enum):
    NEXT_STEP_GMO_SUPPORT_ANSWER_SAFE_LABEL_CAPTURE = (
        "NEXT_STEP_GMO_SUPPORT_ANSWER_SAFE_LABEL_CAPTURE"
    )
    NEXT_STEP_SERVICE_NO_POST_HOOK_WIRING = "NEXT_STEP_SERVICE_NO_POST_HOOK_WIRING"
    NEXT_STEP_CREDENTIAL_BOUNDARY_DESIGN = "NEXT_STEP_CREDENTIAL_BOUNDARY_DESIGN"
    NEXT_STEP_ACTUAL_ENTRY_GATE_DESIGN = "NEXT_STEP_ACTUAL_ENTRY_GATE_DESIGN"
    NEXT_STEP_BLOCKED_UNTIL_SIDE_DOCS_CONFIRMED = (
        "NEXT_STEP_BLOCKED_UNTIL_SIDE_DOCS_CONFIRMED"
    )
    NEXT_STEP_ENTRY_ACTUAL_GATE_PRECHECK_NO_POST_OR_OPERATOR_CONFIRMATION_DESIGN = (
        "NEXT_STEP_ENTRY_ACTUAL_GATE_PRECHECK_NO_POST_OR_OPERATOR_CONFIRMATION_DESIGN"
    )
    NEXT_STEP_CREDENTIAL_ACTUAL_USE_POLICY_DECISION = (
        "NEXT_STEP_CREDENTIAL_ACTUAL_USE_POLICY_DECISION"
    )


@dataclass(frozen=True)
class GmoPreActualReadinessInput:
    """Safe inputs used to build a pre-actual readiness snapshot."""

    repo_clean_safe: bool = True
    head_equals_origin_main_safe: bool = True
    hard_guard_default_deny_confirmed: bool = True
    allow_bridge_absent: bool = True
    production_allow_true_wiring_absent: bool = True
    gmo_risk_config_ready: bool = True
    gmo_kill_switch_ready: bool = True
    gmo_live_enable_policy_ready: bool = False
    service_boundary_ready: bool = True
    runner_boundary_ready: bool = True
    readonly_snapshot_adapter_ready: bool = True
    settlement_reconciliation_ready: bool = True
    integrated_fake_level5_cycle_ready: bool = True
    max_consecutive_losses_selected: int | None = 2
    settlement_side_official_docs_semantics_confirmed: bool = False
    closeOrder_side_semantics_status: GmoCloseOrderSideSemanticsStatus = (
        GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_STILL_UNCONFIRMED
    )
    support_answer_status: GmoPreActualSupportAnswerStatus = (
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED
    )
    credential_boundary_ready: bool = False
    actual_entry_gate_ready: bool = False
    actual_settlement_gate_ready: bool = False
    pre_settlement_open_positions_count: int = 0
    pre_settlement_active_or_pending_order_conflict_count: int = 0
    existing_oanda_sqlalchemy_coupling_safe: bool = True
    service_wiring_policy: str = "DESIGN_FIRST_NO_CODE"


def normalize_support_answer_status(
    candidate: str | GmoPreActualSupportAnswerStatus | None,
) -> GmoPreActualSupportAnswerStatus:
    """Validate a support-answer status label passed from the operator."""

    if candidate is None:
        return GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED
    if isinstance(candidate, GmoPreActualSupportAnswerStatus):
        return candidate
    try:
        return GmoPreActualSupportAnswerStatus(str(candidate))
    except ValueError:
        return GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED


@dataclass(frozen=True)
class GmoLivePreActualReadinessSummary:
    """Safe-only pre-actual readiness snapshot for planning and reporting."""

    pre_actual_readiness_ready: bool
    support_answer_safe_label_capture_ready: bool
    next_step_decision_ready: bool
    settlement_side_docs_status: GmoCloseOrderSideSemanticsStatus
    settlement_side_official_docs_semantics_confirmed: bool
    closeorder_side_semantics_status: GmoCloseOrderSideSemanticsStatus
    support_answer_status: GmoPreActualSupportAnswerStatus
    support_answer_safe_label_accepted: bool
    side_provenance_correction_required: bool
    current_side_derivation_matches_docs: bool
    size_only_one_position_settlement_candidate_ready: bool
    size_only_multiple_position_targeting_block_retained: bool
    size_only_dual_position_targeting_block_retained: bool
    position_specific_actual_path_enabled: bool
    full_cycle_actual_ready: bool
    full_cycle_design_ready_no_post: bool
    entry_only_actual_post_recommended: bool
    actual_settlement_POST_allowed: bool
    service_wiring_policy: str
    service_wiring_status: GmoPreActualServiceWiringStatus
    proposed_hook_points: tuple[str, ...]
    max_consecutive_losses_selected: int | None
    max_consecutive_losses_decision: str
    gmo_risk_config_ready: bool
    gmo_kill_switch_ready: bool
    gmo_live_enable_policy_ready: bool
    service_boundary_ready: bool
    runner_boundary_ready: bool
    readonly_snapshot_adapter_ready: bool
    settlement_reconciliation_ready: bool
    integrated_fake_level5_cycle_ready: bool
    credential_boundary_ready: bool
    actual_entry_gate_ready: bool
    actual_settlement_gate_ready: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: GmoPreActualNextStep


_HOOK_POINTS = (
    "bot_service.start_bot: evaluate GmoLiveServiceBoundarySummary before live-mode handoff",
    "automation_service.AutomationRunner: evaluate GmoLiveServiceBoundarySummary before entry flow",
    "reconciliation adapter: use build_gmo_settlement_reconciliation_input_from_safe_snapshot",
)


def _derive_side_semantics(
    baseline_status: GmoCloseOrderSideSemanticsStatus,
    side_docs_confirmed: bool,
    support_status: GmoPreActualSupportAnswerStatus,
) -> tuple[GmoCloseOrderSideSemanticsStatus, bool]:
    """Derive resolved settlement-side semantics with only safe labels."""

    if (
        support_status
        is GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_POSITION_SIDE
    ):
        return (
            GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_POSITION_SIDE,
            True,
        )
    if (
        support_status
        is GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_OPPOSITE_SIDE
    ):
        return (
            GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE,
            True,
        )
    if support_status in {
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_AMBIGUOUS,
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_CONFLICTING,
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED,
    }:
        return (
            GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_CONFLICT_OR_AMBIGUOUS,
            False,
        )
    if side_docs_confirmed:
        if baseline_status in {
            GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_POSITION_SIDE,
            GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE,
        }:
            return baseline_status, True
        return GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_CONFLICT_OR_AMBIGUOUS, False
    return GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_STILL_UNCONFIRMED, False


def _current_side_derivation_matches_docs(
    side_status: GmoCloseOrderSideSemanticsStatus,
    support_status: GmoPreActualSupportAnswerStatus,
) -> bool:
    return (
        support_status
        is GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_OPPOSITE_SIDE
        and side_status
        is GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE
    )


def _max_consecutive_losses_decision(
    selected: int | None,
) -> tuple[str, bool]:
    if selected not in (2, 3):
        return ("INVALID_MAX_CONSECUTIVE_LOSSES_SELECTION", False)
    try:
        status = classify_max_consecutive_losses_decision_status(
            GmoLiveRiskConfig(max_consecutive_losses_selected=selected)
        )
    except Exception:
        return ("INVALID_MAX_CONSECUTIVE_LOSSES_SELECTION", False)
    return (status.value, True)


def classify_gmo_live_pre_actual_blockers(
    summary_input: GmoPreActualReadinessInput,
) -> tuple[str, ...]:
    """Build deterministic blocker labels for planning-only readiness reporting."""

    blockers: list[str] = []
    if not summary_input.repo_clean_safe:
        blockers.append("REPO_NOT_CLEAN")
    if not summary_input.head_equals_origin_main_safe:
        blockers.append("HEAD_MISMATCH")
    if not summary_input.hard_guard_default_deny_confirmed:
        blockers.append("HARD_GUARD_DEFAULT_DENY_NOT_CONFIRMED")
    if not summary_input.allow_bridge_absent:
        blockers.append("ALLOW_BRIDGE_PRESENT")
    if not summary_input.production_allow_true_wiring_absent:
        blockers.append("PRODUCTION_ALLOW_TRUE_WIRING_PRESENT")
    if not summary_input.gmo_risk_config_ready:
        blockers.append("GMO_RISK_CONFIG_NOT_READY")
    if not summary_input.gmo_kill_switch_ready:
        blockers.append("GMO_KILL_SWITCH_NOT_READY")
    if not summary_input.gmo_live_enable_policy_ready:
        blockers.append("GMO_LIVE_ENABLE_POLICY_NOT_READY")
    if not summary_input.service_boundary_ready:
        blockers.append("SERVICE_BOUNDARY_NOT_READY")
    if not summary_input.runner_boundary_ready:
        blockers.append("RUNNER_BOUNDARY_NOT_READY")
    if not summary_input.readonly_snapshot_adapter_ready:
        blockers.append("READONLY_SNAPSHOT_ADAPTER_NOT_READY")
    if not summary_input.settlement_reconciliation_ready:
        blockers.append("SETTLEMENT_RECONCILIATION_NOT_READY")
    if not summary_input.integrated_fake_level5_cycle_ready:
        blockers.append("INTEGRATED_LEVEL5_CYCLE_NOT_READY")
    if summary_input.max_consecutive_losses_selected not in (2, 3):
        blockers.append("MAX_CONSECUTIVE_LOSSES_SELECTION_INVALID")

    support_status = normalize_support_answer_status(summary_input.support_answer_status)
    resolved_status, _effective_confirmed = _derive_side_semantics(
        summary_input.closeOrder_side_semantics_status,
        summary_input.settlement_side_official_docs_semantics_confirmed,
        support_status,
    )

    if not summary_input.settlement_side_official_docs_semantics_confirmed:
        blockers.append("SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED")

    if support_status is GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED:
        blockers.append("SUPPORT_ANSWER_NOT_RECEIVED")
    if support_status is GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED:
        blockers.append("SUPPORT_ANSWER_UNSAFE_RAW_TEXT")
    if (
        resolved_status
        is GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_STILL_UNCONFIRMED
    ):
        blockers.append("SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED")
    if (
        resolved_status
        is GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_CONFLICT_OR_AMBIGUOUS
    ):
        blockers.append("SETTLEMENT_SIDE_DOCS_CONFLICT_OR_AMBIGUOUS")
    if not summary_input.credential_boundary_ready:
        blockers.append("CREDENTIAL_BOUNDARY_NOT_READY")
    if not summary_input.actual_entry_gate_ready:
        blockers.append("ACTUAL_ENTRY_GATE_NOT_READY")
    if not summary_input.actual_settlement_gate_ready:
        blockers.append("ACTUAL_SETTLEMENT_GATE_NOT_READY")
    if summary_input.pre_settlement_open_positions_count > 1:
        blockers.append("BLOCKER_SIZE_ONLY_MULTIPLE_POSITION_TARGETING_UNCONFIRMED")
        blockers.append("BLOCKER_POST_ENTRY_ONE_POSITION_CONFIRMATION_REQUIRED")
        blockers.append("BLOCKER_POSITION_SPECIFIC_PATH_DISABLED")
    if summary_input.pre_settlement_open_positions_count == 0:
        blockers.append("BLOCKER_POST_ENTRY_ONE_POSITION_CONFIRMATION_REQUIRED")
    if summary_input.pre_settlement_active_or_pending_order_conflict_count > 0:
        blockers.append("BLOCKER_ACTIVE_PENDING_CLEAR_READ_REQUIRED")
        blockers.append("BLOCKER_POST_ENTRY_ONE_POSITION_CONFIRMATION_REQUIRED")
    if not summary_input.existing_oanda_sqlalchemy_coupling_safe:
        blockers.append("EXISTING_OANDA_SQLALCHEMY_COUPLING_BLOCKED")
    if (
        not summary_input.readonly_snapshot_adapter_ready
        or not summary_input.settlement_reconciliation_ready
    ):
        blockers.append("BLOCKER_RUNTIME_NO_POSITION_READ_REQUIRED")
    if summary_input.support_answer_status in {
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED,
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_AMBIGUOUS,
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_CONFLICTING,
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED,
    }:
        blockers.append("BLOCKER_OPERATOR_SETTLEMENT_CONFIRMATION_REQUIRED")
        blockers.append("BLOCKER_OPERATOR_ENTRY_CONFIRMATION_REQUIRED")

    return tuple(blockers)


def _service_wiring_status(
    summary_input: GmoPreActualReadinessInput,
) -> GmoPreActualServiceWiringStatus:
    if summary_input.service_wiring_policy != "DESIGN_FIRST_NO_CODE":
        return GmoPreActualServiceWiringStatus.SERVICE_WIRING_OPERATOR_DECISION_REQUIRED

    if not summary_input.service_boundary_ready or not summary_input.runner_boundary_ready:
        return GmoPreActualServiceWiringStatus.SERVICE_WIRING_OPERATOR_DECISION_REQUIRED

    if not summary_input.existing_oanda_sqlalchemy_coupling_safe:
        return (
            GmoPreActualServiceWiringStatus.SERVICE_WIRING_BLOCKED_BY_EXISTING_OANDA_SQLALCHEMY_COUPLING
        )

    return GmoPreActualServiceWiringStatus.SERVICE_WIRING_CAN_PROCEED_TO_NO_POST_HOOK


def _next_step(
    summary_input: GmoPreActualReadinessInput,
    support_status: GmoPreActualSupportAnswerStatus,
    _service_wiring_status: GmoPreActualServiceWiringStatus,
) -> GmoPreActualNextStep:
    if not summary_input.credential_boundary_ready:
        return GmoPreActualNextStep.NEXT_STEP_CREDENTIAL_ACTUAL_USE_POLICY_DECISION

    if support_status in {
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_NOT_RECEIVED,
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_AMBIGUOUS,
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_CONFLICTING,
        GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED,
    }:
        return GmoPreActualNextStep.NEXT_STEP_GMO_SUPPORT_ANSWER_SAFE_LABEL_CAPTURE

    return (
        GmoPreActualNextStep
        .NEXT_STEP_ENTRY_ACTUAL_GATE_PRECHECK_NO_POST_OR_OPERATOR_CONFIRMATION_DESIGN
    )


def build_gmo_live_pre_actual_entry_readiness_summary(
    summary_input: GmoPreActualReadinessInput | None = None,
) -> GmoLivePreActualReadinessSummary:
    """Build one no-POST readiness snapshot focused on entry path."""

    snapshot = summary_input or GmoPreActualReadinessInput()

    support_status = normalize_support_answer_status(snapshot.support_answer_status)
    side_status, _ = _derive_side_semantics(
        snapshot.closeOrder_side_semantics_status,
        snapshot.settlement_side_official_docs_semantics_confirmed,
        support_status,
    )
    max_losses_decision, losses_selected_valid = _max_consecutive_losses_decision(
        snapshot.max_consecutive_losses_selected,
    )
    blockers = list(classify_gmo_live_pre_actual_blockers(snapshot))

    settlement_gate_ready = (
        snapshot.actual_settlement_gate_ready
        and side_status is not GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_STILL_UNCONFIRMED
        and side_status is not GmoCloseOrderSideSemanticsStatus.SIDE_DOCS_CONFLICT_OR_AMBIGUOUS
        and snapshot.settlement_side_official_docs_semantics_confirmed
        and snapshot.readonly_snapshot_adapter_ready
        and snapshot.settlement_reconciliation_ready
        and snapshot.credential_boundary_ready
    )

    size_only_one_position_settlement_candidate_ready = (
        snapshot.pre_settlement_open_positions_count == 1
        and snapshot.pre_settlement_active_or_pending_order_conflict_count == 0
    )
    size_only_multiple_position_targeting_block_retained = (
        snapshot.pre_settlement_open_positions_count > 1
    )
    size_only_dual_position_targeting_block_retained = (
        snapshot.pre_settlement_open_positions_count > 1
    )
    full_cycle_design_ready_no_post = (
        snapshot.settlement_side_official_docs_semantics_confirmed
        and side_status
        is GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE
        and support_status
        is GmoPreActualSupportAnswerStatus.SUPPORT_CONFIRMED_CLOSEORDER_SIDE_IS_OPPOSITE_SIDE
        and snapshot.readonly_snapshot_adapter_ready
        and snapshot.settlement_reconciliation_ready
        and size_only_one_position_settlement_candidate_ready
        and not size_only_multiple_position_targeting_block_retained
        and not size_only_dual_position_targeting_block_retained
    )
    if not size_only_one_position_settlement_candidate_ready:
        blockers.append("BLOCKER_POST_ENTRY_ONE_POSITION_CONFIRMATION_REQUIRED")

    entry_gate_ready = (
        snapshot.actual_entry_gate_ready
        and snapshot.credential_boundary_ready
        and snapshot.gmo_risk_config_ready
        and snapshot.gmo_kill_switch_ready
        and snapshot.gmo_live_enable_policy_ready
    )

    service_wiring = _service_wiring_status(snapshot)
    next_step = _next_step(snapshot, support_status, service_wiring)

    settlement_provenance_correction_required = (
        side_status is GmoCloseOrderSideSemanticsStatus.SIDE_SEMANTICS_CONFIRMED_POSITION_SIDE
    )
    current_side_derivation_matches_docs = _current_side_derivation_matches_docs(
        side_status=side_status,
        support_status=support_status,
    )

    return GmoLivePreActualReadinessSummary(
        pre_actual_readiness_ready=losses_selected_valid and bool(not blockers),
        support_answer_safe_label_capture_ready=(
            support_status
            is not GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED
        ),
        next_step_decision_ready=(
            support_status
            is not GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED
        ),
        settlement_side_docs_status=side_status,
        settlement_side_official_docs_semantics_confirmed=(
            snapshot.settlement_side_official_docs_semantics_confirmed
        ),
        closeorder_side_semantics_status=side_status,
        support_answer_status=support_status,
        support_answer_safe_label_accepted=(
            support_status
            is not GmoPreActualSupportAnswerStatus.SUPPORT_ANSWER_UNSAFE_RAW_TEXT_PROVIDED
        ),
        side_provenance_correction_required=settlement_provenance_correction_required,
        current_side_derivation_matches_docs=current_side_derivation_matches_docs,
        service_wiring_policy=snapshot.service_wiring_policy,
        service_wiring_status=service_wiring,
        proposed_hook_points=_HOOK_POINTS,
        max_consecutive_losses_selected=snapshot.max_consecutive_losses_selected,
        max_consecutive_losses_decision=max_losses_decision,
        gmo_risk_config_ready=snapshot.gmo_risk_config_ready,
        gmo_kill_switch_ready=snapshot.gmo_kill_switch_ready,
        gmo_live_enable_policy_ready=snapshot.gmo_live_enable_policy_ready,
        service_boundary_ready=snapshot.service_boundary_ready,
        runner_boundary_ready=snapshot.runner_boundary_ready,
        readonly_snapshot_adapter_ready=snapshot.readonly_snapshot_adapter_ready,
        settlement_reconciliation_ready=snapshot.settlement_reconciliation_ready,
        integrated_fake_level5_cycle_ready=snapshot.integrated_fake_level5_cycle_ready,
        credential_boundary_ready=snapshot.credential_boundary_ready,
        actual_entry_gate_ready=entry_gate_ready,
        actual_settlement_gate_ready=settlement_gate_ready,
        size_only_one_position_settlement_candidate_ready=(
            size_only_one_position_settlement_candidate_ready
        ),
        size_only_multiple_position_targeting_block_retained=(
            size_only_multiple_position_targeting_block_retained
        ),
        size_only_dual_position_targeting_block_retained=(
            size_only_dual_position_targeting_block_retained
        ),
        position_specific_actual_path_enabled=False,
        full_cycle_actual_ready=False,
        full_cycle_design_ready_no_post=full_cycle_design_ready_no_post,
        entry_only_actual_post_recommended=False,
        actual_settlement_POST_allowed=False,
        blocked_reasons=tuple(dict.fromkeys(blockers)),
        recommended_next_step=next_step,
    )


def build_gmo_live_pre_actual_cycle_readiness_summary(
    summary_input: GmoPreActualReadinessInput | None = None,
) -> GmoLivePreActualReadinessSummary:
    """Alias for the same pre-actual readiness summary used by cycle flow."""

    return build_gmo_live_pre_actual_entry_readiness_summary(summary_input)
