"""No-POST tests for the GMO entry final preflight package.

These tests pin that the final preflight package is fail-closed by default,
that no input combination ever turns it into a POST permission, that the
operator entry signal / actual POST exact confirmation cannot be captured or
banked here, and that the module has no env/network/live_verification
surface. The fail-closed design skeletons for the four remaining code
blockers must raise instead of acting.
"""

from __future__ import annotations

import pathlib
from dataclasses import fields, replace

import pytest

from app.services.gmo_live_entry_final_preflight import (
    GmoEntryFinalPreflightDesignError,
    GmoEntryFinalPreflightInput,
    GmoEntryFinalPreflightNextOperatorInput,
    GmoEntryFinalPreflightStatus,
    HardGuardControlledSupplyDesignSkeleton,
    RuntimeSafeReadRealConnectionDesignSkeleton,
    SealedCredentialRealOperationDesignSkeleton,
    build_gmo_entry_final_preflight_package,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_entry_final_preflight.py"
)


def _all_safe_input(**overrides: object) -> GmoEntryFinalPreflightInput:
    base = GmoEntryFinalPreflightInput(
        branch_is_main=True,
        head_equals_remote_main_safe=True,
        local_tracking_ref_synced=True,
        working_tree_clean_safe=True,
        paper_evidence_confirmed_safe_summary=True,
        anomaly_evidence_confirmed_beyond_synthetic=True,
        read_only_runtime_gate_executed_this_step=True,
        runtime_result_fresh=True,
        credential_presence_safe_boolean_confirmed=True,
        runtime_no_position_count_zero_confirmed=True,
        active_pending_clear_confirmed=True,
        production_real_entry_transport_fail_closed_present=True,
        sealed_credential_real_operation_design_present=True,
        runtime_safe_read_real_connection_design_present=True,
        hard_guard_controlled_supply_design_present=True,
        entry_permit_one_use_design_present=True,
        sanitized_preview_ready=True,
        no_order_guard_tests_present=True,
        entry_post_gate_separate_step_design_ready=True,
        production_entry_boundary_implemented_fail_closed=True,
        operator_actual_entry_signoff_recorded=True,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def test_default_package_is_fail_closed_and_falsey() -> None:
    package = build_gmo_entry_final_preflight_package(GmoEntryFinalPreflightInput())
    assert package.status is GmoEntryFinalPreflightStatus.BLOCKED_SAFE
    assert package.blocked_reasons
    assert package.actual_entry_POST_allowed is False
    assert package.actual_settlement_POST_allowed is False
    assert package.actual_post_permission_implied is False
    assert package.entry_post_execution_gate_is_separate_step is True
    assert package.operator_signal_still_required_in_separate_step is True
    assert package.ai_trade_decision_performed is False
    assert package.operator_confirmation_substituted is False
    assert package.retry_repost_second_post_possible is False
    assert package.package_assembled_no_post is False
    assert not package


def test_all_safe_input_is_ready_but_still_not_a_post_permission() -> None:
    package = build_gmo_entry_final_preflight_package(_all_safe_input())
    assert package.status is (
        GmoEntryFinalPreflightStatus.READY_FOR_ACTUAL_ENTRY_FINAL_PREFLIGHT_NO_POST
    )
    assert package.blocked_reasons == ()
    assert package.package_assembled_no_post is True
    assert package.actual_entry_POST_allowed is False
    assert package.actual_settlement_POST_allowed is False
    assert package.next_required_operator_input is (
        GmoEntryFinalPreflightNextOperatorInput
        .PROVIDE_ENTRY_SIGNAL_AND_EXACT_INPUTS_IN_SEPARATE_STEP
    )
    assert not package


@pytest.mark.parametrize(
    ("override", "expected_reason"),
    [
        ({"branch_is_main": False}, "REPOSITORY_BRANCH_NOT_MAIN"),
        (
            {"head_equals_remote_main_safe": False},
            "REPOSITORY_HEAD_NOT_EQUAL_REMOTE_MAIN",
        ),
        ({"local_tracking_ref_synced": False}, "REPOSITORY_LOCAL_TRACKING_REF_STALE"),
        ({"working_tree_clean_safe": False}, "REPOSITORY_WORKING_TREE_NOT_CLEAN"),
        (
            {"paper_evidence_confirmed_safe_summary": False},
            "PAPER_EVIDENCE_NOT_CONFIRMED",
        ),
        ({"raw_response_exposed": True}, "RAW_RESPONSE_EXPOSED"),
        ({"raw_ids_exposed": True}, "RAW_IDS_EXPOSED"),
        (
            {"raw_price_or_size_values_exposed": True},
            "RAW_PRICE_OR_SIZE_VALUES_EXPOSED",
        ),
        ({"credential_value_exposed": True}, "CREDENTIAL_VALUE_EXPOSED"),
        ({"env_read_performed": True}, "ENV_READ_PERFORMED"),
        ({"retry_requested": True}, "RETRY_REQUESTED_BLOCKED"),
        ({"repost_requested": True}, "REPOST_REQUESTED_BLOCKED"),
        ({"second_post_requested": True}, "SECOND_POST_REQUESTED_BLOCKED"),
        (
            {"settlement_post_requested": True},
            "SETTLEMENT_POST_IN_ENTRY_STEP_BLOCKED",
        ),
        ({"generic_close_requested": True}, "GENERIC_CLOSE_REQUESTED_BLOCKED"),
    ],
)
def test_hard_violations_block_safe(override: dict, expected_reason: str) -> None:
    package = build_gmo_entry_final_preflight_package(_all_safe_input(**override))
    assert package.status is GmoEntryFinalPreflightStatus.BLOCKED_SAFE
    assert expected_reason in package.blocked_reasons
    assert package.package_assembled_no_post is False
    assert package.actual_entry_POST_allowed is False


@pytest.mark.parametrize(
    ("override", "expected_reason"),
    [
        (
            {"production_real_entry_transport_fail_closed_present": False},
            "PRODUCTION_REAL_ENTRY_TRANSPORT_FAIL_CLOSED_DESIGN_MISSING",
        ),
        (
            {"sealed_credential_real_operation_design_present": False},
            "SEALED_CREDENTIAL_REAL_OPERATION_DESIGN_MISSING",
        ),
        (
            {"runtime_safe_read_real_connection_design_present": False},
            "RUNTIME_SAFE_READ_REAL_CONNECTION_DESIGN_MISSING",
        ),
        (
            {"hard_guard_controlled_supply_design_present": False},
            "HARD_GUARD_CONTROLLED_SUPPLY_DESIGN_MISSING",
        ),
        (
            {"entry_permit_one_use_design_present": False},
            "ENTRY_PERMIT_ONE_USE_DESIGN_MISSING",
        ),
        ({"sanitized_preview_ready": False}, "SANITIZED_PREVIEW_NOT_READY"),
        (
            {"no_order_guard_tests_present": False},
            "NO_ORDER_GUARD_TESTS_MISSING",
        ),
    ],
)
def test_foundation_gaps_wait_for_foundation(
    override: dict, expected_reason: str
) -> None:
    package = build_gmo_entry_final_preflight_package(_all_safe_input(**override))
    assert package.status is (
        GmoEntryFinalPreflightStatus.WAITING_FOR_NO_POST_ENTRY_FOUNDATION_COMPLETION
    )
    assert expected_reason in package.blocked_reasons
    assert package.actual_entry_POST_allowed is False


def test_runtime_gate_not_executed_waits_for_operator_confirmation() -> None:
    package = build_gmo_entry_final_preflight_package(
        _all_safe_input(read_only_runtime_gate_executed_this_step=False)
    )
    assert package.status is (
        GmoEntryFinalPreflightStatus
        .WAITING_FOR_READ_ONLY_RUNTIME_OPERATOR_CONFIRMATION
    )
    assert (
        "READ_ONLY_RUNTIME_OPERATOR_CONFIRMATION_NOT_EXECUTED"
        in package.blocked_reasons
    )
    assert package.next_required_operator_input is (
        GmoEntryFinalPreflightNextOperatorInput
        .PROVIDE_READ_ONLY_RUNTIME_OPERATOR_INPUT_BLOCK
    )


@pytest.mark.parametrize(
    ("override", "expected_reason"),
    [
        ({"runtime_result_fresh": False}, "RUNTIME_RESULT_NOT_FRESH"),
        (
            {"credential_presence_safe_boolean_confirmed": False},
            "CREDENTIAL_PRESENCE_SAFE_BOOLEAN_NOT_CONFIRMED",
        ),
        (
            {"runtime_no_position_count_zero_confirmed": False},
            "RUNTIME_NO_POSITION_COUNT_ZERO_NOT_CONFIRMED",
        ),
        (
            {"active_pending_clear_confirmed": False},
            "ACTIVE_PENDING_CLEAR_NOT_CONFIRMED",
        ),
    ],
)
def test_unsafe_runtime_result_waits_for_safe_result(
    override: dict, expected_reason: str
) -> None:
    package = build_gmo_entry_final_preflight_package(_all_safe_input(**override))
    assert package.status is (
        GmoEntryFinalPreflightStatus.WAITING_FOR_SAFE_RUNTIME_RESULT
    )
    assert expected_reason in package.blocked_reasons


def test_synthetic_only_anomaly_waits_for_evidence_confirmation() -> None:
    package = build_gmo_entry_final_preflight_package(
        _all_safe_input(anomaly_evidence_confirmed_beyond_synthetic=False)
    )
    assert package.status is (
        GmoEntryFinalPreflightStatus.WAITING_FOR_ANOMALY_EVIDENCE_CONFIRMATION
    )
    assert (
        "ANOMALY_EVIDENCE_NOT_CONFIRMED_BEYOND_SYNTHETIC" in package.blocked_reasons
    )


def test_separate_step_design_pending_is_ready_for_final_preflight() -> None:
    package = build_gmo_entry_final_preflight_package(
        _all_safe_input(entry_post_gate_separate_step_design_ready=False)
    )
    assert package.status is (
        GmoEntryFinalPreflightStatus.READY_FOR_FINAL_PREFLIGHT_NO_POST
    )
    assert package.package_assembled_no_post is True
    assert package.actual_entry_POST_allowed is False


def test_production_boundary_missing_waits_for_code_blockers() -> None:
    package = build_gmo_entry_final_preflight_package(
        _all_safe_input(production_entry_boundary_implemented_fail_closed=False)
    )
    assert package.status is (
        GmoEntryFinalPreflightStatus.WAITING_FOR_PRODUCTION_ENTRY_CODE_BLOCKERS
    )
    assert "PRODUCTION_ENTRY_CODE_BLOCKERS_NOT_RESOLVED" in package.blocked_reasons
    assert package.next_required_operator_input is (
        GmoEntryFinalPreflightNextOperatorInput.RESOLVE_PRODUCTION_ENTRY_CODE_BLOCKERS
    )
    assert package.package_assembled_no_post is False
    assert package.actual_entry_POST_allowed is False


def test_signoff_missing_waits_for_actual_entry_signoff() -> None:
    package = build_gmo_entry_final_preflight_package(
        _all_safe_input(operator_actual_entry_signoff_recorded=False)
    )
    assert package.status is (
        GmoEntryFinalPreflightStatus.WAITING_FOR_ACTUAL_ENTRY_SIGNOFF
    )
    assert "ACTUAL_ENTRY_WRITTEN_SIGNOFF_NOT_RECORDED" in package.blocked_reasons
    assert package.next_required_operator_input is (
        GmoEntryFinalPreflightNextOperatorInput.PROVIDE_ACTUAL_ENTRY_WRITTEN_SIGNOFF
    )
    assert package.package_assembled_no_post is False
    assert package.actual_entry_POST_allowed is False


def test_ready_for_actual_entry_final_preflight_is_still_not_a_permission() -> None:
    package = build_gmo_entry_final_preflight_package(_all_safe_input())
    assert package.actual_entry_POST_allowed is False
    assert package.actual_settlement_POST_allowed is False
    assert package.entry_post_execution_gate_is_separate_step is True
    assert package.operator_signal_still_required_in_separate_step is True
    assert not package


def test_input_has_no_entry_signal_or_confirmation_field_to_bank() -> None:
    field_names = {field.name for field in fields(GmoEntryFinalPreflightInput)}
    assert not any("confirmation" in name for name in field_names)
    assert not any("current_turn" in name for name in field_names)
    assert not any("signal" in name for name in field_names)


def test_design_skeletons_are_fail_closed_and_falsey() -> None:
    credential_design = SealedCredentialRealOperationDesignSkeleton()
    runtime_design = RuntimeSafeReadRealConnectionDesignSkeleton()
    hard_guard_design = HardGuardControlledSupplyDesignSkeleton()

    assert credential_design.value_exposure_possible is False
    assert credential_design.env_read_surface_present is False
    assert runtime_design.can_execute_in_no_post_step is False
    assert runtime_design.raw_response_surface_present is False
    assert hard_guard_design.allow_bridge_present is False
    assert hard_guard_design.resolvable_in_no_post_step is False
    assert not credential_design
    assert not runtime_design
    assert not hard_guard_design

    with pytest.raises(GmoEntryFinalPreflightDesignError):
        credential_design.activate_real_operation()
    with pytest.raises(GmoEntryFinalPreflightDesignError):
        runtime_design.connect_read_only()
    with pytest.raises(GmoEntryFinalPreflightDesignError):
        hard_guard_design.resolve_allow()


def test_hard_guard_design_never_returns_an_allow_value() -> None:
    hard_guard_design = HardGuardControlledSupplyDesignSkeleton()
    try:
        result = hard_guard_design.resolve_allow()
    except GmoEntryFinalPreflightDesignError:
        result = None
    assert result is not True


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_does_not_read_env_or_network_client() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "load_dotenv" not in text
    assert "httpx" not in text
    assert "requests" not in text


def test_module_keeps_actual_post_fail_closed_fields_hardcoded_false() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text
    assert "actual_entry_POST_allowed=False" in text
    assert "actual_entry_POST_allowed=True" not in text
    assert "actual_settlement_POST_allowed=False" in text
    assert "actual_settlement_POST_allowed=True" not in text
    assert "actual_post_permission_implied=False" in text
    assert "actual_post_permission_implied=True" not in text
    assert "ai_trade_decision_performed=False" in text
    assert "ai_trade_decision_performed=True" not in text
    assert "operator_confirmation_substituted=False" in text
    assert "operator_confirmation_substituted=True" not in text
    assert "retry_repost_second_post_possible=False" in text
    assert "retry_repost_second_post_possible=True" not in text
