"""No-POST final preflight package for the future actual entry POST step.

This module assembles the LAST no-POST checkpoint before a separate actual
entry POST step could even be considered. It is a classification model only:

- The package NEVER authorizes a POST. ``actual_entry_POST_allowed`` and
  ``actual_settlement_POST_allowed`` are hardcoded false and ``__bool__`` is
  always false, so the package cannot become an allow-bridge.
- The operator's entry signal (ENTRY_BUY / ENTRY_SELL / HOLD) and the actual
  POST exact confirmation are NOT input fields here; they cannot be captured,
  stored, or banked by this module. They belong exclusively to the separate
  ``ENTRY_POST_GATE_WITH_OPERATOR_CURRENT_TURN_CONFIRMATION`` step.
- The four remaining code blockers toward an actual POST are represented as
  fail-closed design skeletons that structurally cannot send, expose a value,
  connect, or resolve ``allow=True`` in a no-POST step.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GmoEntryFinalPreflightDesignError(RuntimeError):
    """Raised when a fail-closed design skeleton is asked to act for real."""


@dataclass(frozen=True)
class SealedCredentialRealOperationDesignSkeleton:
    """Design placeholder for the future real sealed credential operation.

    The future real provider will resolve the secret internally at the
    transport boundary only. This skeleton has no field that could carry a
    credential value, length, hash, fingerprint, prefix, or suffix, and its
    activation always raises in the no-POST phase.
    """

    design_present: bool = True
    value_exposure_possible: bool = False
    env_read_surface_present: bool = False

    def activate_real_operation(self) -> None:
        raise GmoEntryFinalPreflightDesignError(
            "sealed credential real operation is design-only in the no-POST "
            "phase; no credential is read, resolved, or exposed"
        )

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class RuntimeSafeReadRealConnectionDesignSkeleton:
    """Design placeholder for the future real read-only runtime connection.

    The future connection returns safe status/count labels only. In the
    no-POST phase this skeleton cannot execute: connecting always raises.
    """

    design_present: bool = True
    can_execute_in_no_post_step: bool = False
    raw_response_surface_present: bool = False

    def connect_read_only(self) -> None:
        raise GmoEntryFinalPreflightDesignError(
            "runtime safe read real connection is design-only in the no-POST "
            "phase; no private GET is performed"
        )

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class HardGuardControlledSupplyDesignSkeleton:
    """Design placeholder for the controlled supply of the hard guard allow.

    Per the allow-bridge rejection record, no reusable decision function may
    compute the hard guard ``allow``. This skeleton documents that the value
    will be passed only by the operator gate of the separate actual POST
    step; resolving it here always raises and never returns ``True``.
    """

    design_present: bool = True
    allow_bridge_present: bool = False
    resolvable_in_no_post_step: bool = False

    def resolve_allow(self) -> None:
        raise GmoEntryFinalPreflightDesignError(
            "hard guard allow supply is design-only in the no-POST phase; it "
            "never resolves to an allow value here"
        )

    def __bool__(self) -> bool:
        return False


class GmoEntryFinalPreflightStatus(str, Enum):
    BLOCKED_SAFE = "BLOCKED_SAFE"
    WAITING_FOR_NO_POST_ENTRY_FOUNDATION_COMPLETION = (
        "WAITING_FOR_NO_POST_ENTRY_FOUNDATION_COMPLETION"
    )
    WAITING_FOR_READ_ONLY_RUNTIME_OPERATOR_CONFIRMATION = (
        "WAITING_FOR_READ_ONLY_RUNTIME_OPERATOR_CONFIRMATION"
    )
    WAITING_FOR_SAFE_RUNTIME_RESULT = "WAITING_FOR_SAFE_RUNTIME_RESULT"
    WAITING_FOR_ANOMALY_EVIDENCE_CONFIRMATION = (
        "WAITING_FOR_ANOMALY_EVIDENCE_CONFIRMATION"
    )
    READY_FOR_FINAL_PREFLIGHT_NO_POST = "READY_FOR_FINAL_PREFLIGHT_NO_POST"
    # Superseded terminal status kept for record compatibility with earlier
    # step reports; the evaluator now ends in the three statuses below it.
    READY_FOR_OPERATOR_ENTRY_CURRENT_TURN_CONFIRMATION = (
        "READY_FOR_OPERATOR_ENTRY_CURRENT_TURN_CONFIRMATION"
    )
    WAITING_FOR_PRODUCTION_ENTRY_CODE_BLOCKERS = (
        "WAITING_FOR_PRODUCTION_ENTRY_CODE_BLOCKERS"
    )
    WAITING_FOR_ACTUAL_ENTRY_SIGNOFF = "WAITING_FOR_ACTUAL_ENTRY_SIGNOFF"
    READY_FOR_ACTUAL_ENTRY_FINAL_PREFLIGHT_NO_POST = (
        "READY_FOR_ACTUAL_ENTRY_FINAL_PREFLIGHT_NO_POST"
    )


class GmoEntryFinalPreflightNextOperatorInput(str, Enum):
    RESOLVE_BLOCKED_SAFE_CONDITIONS = "RESOLVE_BLOCKED_SAFE_CONDITIONS"
    COMPLETE_NO_POST_ENTRY_FOUNDATION = "COMPLETE_NO_POST_ENTRY_FOUNDATION"
    PROVIDE_READ_ONLY_RUNTIME_OPERATOR_INPUT_BLOCK = (
        "PROVIDE_READ_ONLY_RUNTIME_OPERATOR_INPUT_BLOCK"
    )
    RERUN_READ_ONLY_RUNTIME_SAFE_READ_FRESH = (
        "RERUN_READ_ONLY_RUNTIME_SAFE_READ_FRESH"
    )
    PROVIDE_ANOMALY_EVIDENCE_BEYOND_SYNTHETIC = (
        "PROVIDE_ANOMALY_EVIDENCE_BEYOND_SYNTHETIC"
    )
    PROVIDE_ENTRY_SIGNAL_AND_EXACT_INPUTS_IN_SEPARATE_STEP = (
        "PROVIDE_ENTRY_SIGNAL_AND_EXACT_INPUTS_IN_SEPARATE_STEP"
    )
    RESOLVE_PRODUCTION_ENTRY_CODE_BLOCKERS = (
        "RESOLVE_PRODUCTION_ENTRY_CODE_BLOCKERS"
    )
    PROVIDE_ACTUAL_ENTRY_WRITTEN_SIGNOFF = "PROVIDE_ACTUAL_ENTRY_WRITTEN_SIGNOFF"


@dataclass(frozen=True)
class GmoEntryFinalPreflightInput:
    """Default-deny input. Every gate must be supplied explicitly as safe."""

    # repository gate (an actual POST step additionally requires a fresh
    # workspace re-verification; a stale local tracking ref is never allowed
    # there even if it was tolerated in a no-POST step)
    branch_is_main: bool = False
    head_equals_remote_main_safe: bool = False
    local_tracking_ref_synced: bool = False
    working_tree_clean_safe: bool = False

    # evidence gate
    paper_evidence_confirmed_safe_summary: bool = False
    anomaly_evidence_confirmed_beyond_synthetic: bool = False

    # read-only runtime gate (results from the read-only runtime step; safe
    # labels only, never raw)
    read_only_runtime_gate_executed_this_step: bool = False
    runtime_result_fresh: bool = False
    credential_presence_safe_boolean_confirmed: bool = False
    runtime_no_position_count_zero_confirmed: bool = False
    active_pending_clear_confirmed: bool = False

    # no-POST entry foundation gate
    production_real_entry_transport_fail_closed_present: bool = False
    sealed_credential_real_operation_design_present: bool = False
    runtime_safe_read_real_connection_design_present: bool = False
    hard_guard_controlled_supply_design_present: bool = False
    entry_permit_one_use_design_present: bool = False
    sanitized_preview_ready: bool = False
    no_order_guard_tests_present: bool = False

    # separate-step design gate
    entry_post_gate_separate_step_design_ready: bool = False

    # production entry boundary gate (fail-closed no-POST implementation of
    # the four code blockers: disabled transport / sealed credential real
    # operation boundary / runtime safe read connection adapter / hard guard
    # default-deny controlled supply)
    production_entry_boundary_implemented_fail_closed: bool = False

    # operator written sign-off gate (recorded per RESUME_DESIGN §1; never a
    # POST permission by itself)
    operator_actual_entry_signoff_recorded: bool = False

    # violations (any true blocks hard)
    raw_response_exposed: bool = False
    raw_ids_exposed: bool = False
    raw_price_or_size_values_exposed: bool = False
    credential_value_exposed: bool = False
    env_read_performed: bool = False
    retry_requested: bool = False
    repost_requested: bool = False
    second_post_requested: bool = False
    settlement_post_requested: bool = False
    generic_close_requested: bool = False


@dataclass(frozen=True)
class GmoEntryFinalPreflightPackage:
    status: GmoEntryFinalPreflightStatus
    blocked_reasons: tuple[str, ...]
    next_required_operator_input: GmoEntryFinalPreflightNextOperatorInput
    package_assembled_no_post: bool
    actual_entry_POST_allowed: bool = False
    actual_settlement_POST_allowed: bool = False
    actual_post_permission_implied: bool = False
    entry_post_execution_gate_is_separate_step: bool = True
    operator_signal_still_required_in_separate_step: bool = True
    ai_trade_decision_performed: bool = False
    operator_confirmation_substituted: bool = False
    retry_repost_second_post_possible: bool = False

    def __bool__(self) -> bool:
        return False


_VIOLATION_REASONS: tuple[tuple[str, str], ...] = (
    ("raw_response_exposed", "RAW_RESPONSE_EXPOSED"),
    ("raw_ids_exposed", "RAW_IDS_EXPOSED"),
    ("raw_price_or_size_values_exposed", "RAW_PRICE_OR_SIZE_VALUES_EXPOSED"),
    ("credential_value_exposed", "CREDENTIAL_VALUE_EXPOSED"),
    ("env_read_performed", "ENV_READ_PERFORMED"),
    ("retry_requested", "RETRY_REQUESTED_BLOCKED"),
    ("repost_requested", "REPOST_REQUESTED_BLOCKED"),
    ("second_post_requested", "SECOND_POST_REQUESTED_BLOCKED"),
    ("settlement_post_requested", "SETTLEMENT_POST_IN_ENTRY_STEP_BLOCKED"),
    ("generic_close_requested", "GENERIC_CLOSE_REQUESTED_BLOCKED"),
)

_REPOSITORY_REASONS: tuple[tuple[str, str], ...] = (
    ("branch_is_main", "REPOSITORY_BRANCH_NOT_MAIN"),
    ("head_equals_remote_main_safe", "REPOSITORY_HEAD_NOT_EQUAL_REMOTE_MAIN"),
    ("local_tracking_ref_synced", "REPOSITORY_LOCAL_TRACKING_REF_STALE"),
    ("working_tree_clean_safe", "REPOSITORY_WORKING_TREE_NOT_CLEAN"),
)

_FOUNDATION_REASONS: tuple[tuple[str, str], ...] = (
    (
        "production_real_entry_transport_fail_closed_present",
        "PRODUCTION_REAL_ENTRY_TRANSPORT_FAIL_CLOSED_DESIGN_MISSING",
    ),
    (
        "sealed_credential_real_operation_design_present",
        "SEALED_CREDENTIAL_REAL_OPERATION_DESIGN_MISSING",
    ),
    (
        "runtime_safe_read_real_connection_design_present",
        "RUNTIME_SAFE_READ_REAL_CONNECTION_DESIGN_MISSING",
    ),
    (
        "hard_guard_controlled_supply_design_present",
        "HARD_GUARD_CONTROLLED_SUPPLY_DESIGN_MISSING",
    ),
    ("entry_permit_one_use_design_present", "ENTRY_PERMIT_ONE_USE_DESIGN_MISSING"),
    ("sanitized_preview_ready", "SANITIZED_PREVIEW_NOT_READY"),
    ("no_order_guard_tests_present", "NO_ORDER_GUARD_TESTS_MISSING"),
)

_RUNTIME_RESULT_REASONS: tuple[tuple[str, str], ...] = (
    ("runtime_result_fresh", "RUNTIME_RESULT_NOT_FRESH"),
    (
        "credential_presence_safe_boolean_confirmed",
        "CREDENTIAL_PRESENCE_SAFE_BOOLEAN_NOT_CONFIRMED",
    ),
    (
        "runtime_no_position_count_zero_confirmed",
        "RUNTIME_NO_POSITION_COUNT_ZERO_NOT_CONFIRMED",
    ),
    ("active_pending_clear_confirmed", "ACTIVE_PENDING_CLEAR_NOT_CONFIRMED"),
)


def build_gmo_entry_final_preflight_package(
    preflight_input: GmoEntryFinalPreflightInput,
) -> GmoEntryFinalPreflightPackage:
    """Classify final preflight readiness; never grant a POST permission."""

    blockers: list[str] = []

    for field_name, reason in _VIOLATION_REASONS:
        if getattr(preflight_input, field_name):
            blockers.append(reason)
    for field_name, reason in _REPOSITORY_REASONS:
        if not getattr(preflight_input, field_name):
            blockers.append(reason)
    if not preflight_input.paper_evidence_confirmed_safe_summary:
        blockers.append("PAPER_EVIDENCE_NOT_CONFIRMED")

    hard_blocked = bool(blockers)

    foundation_blockers = [
        reason
        for field_name, reason in _FOUNDATION_REASONS
        if not getattr(preflight_input, field_name)
    ]
    blockers.extend(foundation_blockers)

    runtime_executed = preflight_input.read_only_runtime_gate_executed_this_step
    if not runtime_executed:
        blockers.append("READ_ONLY_RUNTIME_OPERATOR_CONFIRMATION_NOT_EXECUTED")

    runtime_result_blockers = [
        reason
        for field_name, reason in _RUNTIME_RESULT_REASONS
        if not getattr(preflight_input, field_name)
    ]
    if runtime_executed:
        blockers.extend(runtime_result_blockers)

    anomaly_confirmed = preflight_input.anomaly_evidence_confirmed_beyond_synthetic
    if not anomaly_confirmed:
        blockers.append("ANOMALY_EVIDENCE_NOT_CONFIRMED_BEYOND_SYNTHETIC")

    boundary_implemented = (
        preflight_input.production_entry_boundary_implemented_fail_closed
    )
    if not boundary_implemented:
        blockers.append("PRODUCTION_ENTRY_CODE_BLOCKERS_NOT_RESOLVED")

    signoff_recorded = preflight_input.operator_actual_entry_signoff_recorded
    if not signoff_recorded:
        blockers.append("ACTUAL_ENTRY_WRITTEN_SIGNOFF_NOT_RECORDED")

    if hard_blocked:
        status = GmoEntryFinalPreflightStatus.BLOCKED_SAFE
        next_input = (
            GmoEntryFinalPreflightNextOperatorInput.RESOLVE_BLOCKED_SAFE_CONDITIONS
        )
    elif foundation_blockers:
        status = (
            GmoEntryFinalPreflightStatus
            .WAITING_FOR_NO_POST_ENTRY_FOUNDATION_COMPLETION
        )
        next_input = (
            GmoEntryFinalPreflightNextOperatorInput.COMPLETE_NO_POST_ENTRY_FOUNDATION
        )
    elif not runtime_executed:
        status = (
            GmoEntryFinalPreflightStatus
            .WAITING_FOR_READ_ONLY_RUNTIME_OPERATOR_CONFIRMATION
        )
        next_input = (
            GmoEntryFinalPreflightNextOperatorInput
            .PROVIDE_READ_ONLY_RUNTIME_OPERATOR_INPUT_BLOCK
        )
    elif runtime_result_blockers:
        status = GmoEntryFinalPreflightStatus.WAITING_FOR_SAFE_RUNTIME_RESULT
        next_input = (
            GmoEntryFinalPreflightNextOperatorInput
            .RERUN_READ_ONLY_RUNTIME_SAFE_READ_FRESH
        )
    elif not anomaly_confirmed:
        status = (
            GmoEntryFinalPreflightStatus.WAITING_FOR_ANOMALY_EVIDENCE_CONFIRMATION
        )
        next_input = (
            GmoEntryFinalPreflightNextOperatorInput
            .PROVIDE_ANOMALY_EVIDENCE_BEYOND_SYNTHETIC
        )
    elif not preflight_input.entry_post_gate_separate_step_design_ready:
        status = GmoEntryFinalPreflightStatus.READY_FOR_FINAL_PREFLIGHT_NO_POST
        next_input = (
            GmoEntryFinalPreflightNextOperatorInput
            .PROVIDE_ENTRY_SIGNAL_AND_EXACT_INPUTS_IN_SEPARATE_STEP
        )
    elif not boundary_implemented:
        status = (
            GmoEntryFinalPreflightStatus.WAITING_FOR_PRODUCTION_ENTRY_CODE_BLOCKERS
        )
        next_input = (
            GmoEntryFinalPreflightNextOperatorInput
            .RESOLVE_PRODUCTION_ENTRY_CODE_BLOCKERS
        )
    elif not signoff_recorded:
        status = GmoEntryFinalPreflightStatus.WAITING_FOR_ACTUAL_ENTRY_SIGNOFF
        next_input = (
            GmoEntryFinalPreflightNextOperatorInput
            .PROVIDE_ACTUAL_ENTRY_WRITTEN_SIGNOFF
        )
    else:
        status = (
            GmoEntryFinalPreflightStatus
            .READY_FOR_ACTUAL_ENTRY_FINAL_PREFLIGHT_NO_POST
        )
        next_input = (
            GmoEntryFinalPreflightNextOperatorInput
            .PROVIDE_ENTRY_SIGNAL_AND_EXACT_INPUTS_IN_SEPARATE_STEP
        )

    package_assembled_no_post = status in (
        GmoEntryFinalPreflightStatus.READY_FOR_FINAL_PREFLIGHT_NO_POST,
        GmoEntryFinalPreflightStatus.READY_FOR_ACTUAL_ENTRY_FINAL_PREFLIGHT_NO_POST,
    )

    return GmoEntryFinalPreflightPackage(
        status=status,
        blocked_reasons=tuple(blockers),
        next_required_operator_input=next_input,
        package_assembled_no_post=package_assembled_no_post,
        actual_entry_POST_allowed=False,
        actual_settlement_POST_allowed=False,
        actual_post_permission_implied=False,
        entry_post_execution_gate_is_separate_step=True,
        operator_signal_still_required_in_separate_step=True,
        ai_trade_decision_performed=False,
        operator_confirmation_substituted=False,
        retry_repost_second_post_possible=False,
    )
