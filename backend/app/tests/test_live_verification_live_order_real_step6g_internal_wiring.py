from __future__ import annotations

import ast
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_step6g_internal_wiring import (
    LiveOrderRealStep6GInternalWiringInput,
    LiveOrderRealStep6GInternalWiringStatus,
    build_live_order_real_step6g_internal_wiring,
    build_valid_step6g_internal_wiring_snapshot,
    render_live_order_real_step6g_internal_wiring_markdown,
)

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
Status = LiveOrderRealStep6GInternalWiringStatus
UNSUPPORTED_RAW_MODE = "MODE_RAW_SHOULD_NOT_SURFACE"
UNSUPPORTED_SAFE_MODE = "UNSUPPORTED_REDACTED"


def _input(**overrides: object) -> LiveOrderRealStep6GInternalWiringInput:
    base = LiveOrderRealStep6GInternalWiringInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_step6g_internal_wiring(
        input_snapshot=_input(**overrides),
        created_at=CREATED_AT,
    )


def test_valid_full_fake_sanitized_chain_ready_no_api_no_post() -> None:
    result = _build()

    assert result.status is Status.STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST
    assert result.internal_wiring_ready is True
    assert result.pb_ready is True
    assert result.eb_ready is True
    assert result.ad_ready is True
    assert result.ra_ready is True
    assert result.tc_ready is True
    assert result.st_signing_ready is True
    assert result.st_private_transport_ready is True
    assert result.dummy_signing_ready is True
    assert result.dummy_signature_check_passed is True
    assert result.dummy_signature_value_present is False
    assert result.dummy_signature_value_displayed is False
    assert result.dummy_signature_value_saved is False
    assert result.http_transport_interface_ready is True
    assert result.http_transport_interface_mode == "INTERFACE_ONLY"
    assert result.http_client_present is False
    assert result.can_execute_http_post is False
    assert result.can_call_order_endpoint is False
    assert result.can_call_live_order_once is False
    assert result.credential_boundary_ready is True
    assert result.credential_boundary_mode == "BOUNDARY_ONLY"
    assert result.credential_handle_ready is True
    assert result.credential_handle_mode == "HANDLE_CONTRACT_ONLY"
    assert result.handle_requested is True
    assert result.handle_created is False
    assert result.handle_contains_value is False
    assert result.handle_contains_identifier is False
    assert result.handle_metadata_exposed is False
    assert result.credential_injection_ready is True
    assert result.credential_injection_mode == "INJECTION_SKELETON_ONLY"
    assert result.injection_requested is True
    assert result.injection_performed is False
    assert result.real_credential_values_available is False
    assert result.real_credential_values_injected is False
    assert result.credential_injection_metadata_available is False
    assert result.credential_presence_check_ready is True
    assert result.presence_check_mode == "OPERATOR_PROVIDED_SENTINEL_ONLY"
    assert result.operator_assertion_provided is True
    assert result.operator_assertion_is_boolean_only is True
    assert result.operator_sentinel_received is True
    assert result.operator_sentinel_fresh is True
    assert result.operator_sentinel_reused is False
    assert result.operator_sentinel_stale is False
    assert result.operator_sentinel_previous_turn is False
    assert result.sentinel_value_present is False
    assert result.sentinel_value_displayed is False
    assert result.sentinel_value_saved is False
    assert result.sentinel_hash_available is False
    assert result.sentinel_fingerprint_available is False
    assert result.sentinel_length_available is False
    assert result.presence_result_broadly_propagated is False
    assert result.presence_result_saved is False
    assert result.credential_presence_controlled_ready is True
    assert (
        result.credential_presence_controlled_mode
        == "CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY"
    )
    assert result.credential_presence_controlled_checked is True
    assert result.required_credentials_present is True
    assert result.all_required_credentials_present is True
    assert result.presence_missing is False
    assert result.presence_unknown is False
    assert result.presence_failed is False
    assert result.presence_unavailable is False
    assert result.presence_timeout is False
    assert result.controlled_env_access_for_presence_only is True
    assert result.controlled_env_file_read is False
    assert result.controlled_env_example_file_read is False
    assert result.controlled_env_actual_names_present is False
    assert result.controlled_credential_values_present is False
    assert result.controlled_credential_lengths_present is False
    assert result.controlled_credential_hashes_present is False
    assert result.controlled_credential_fingerprints_present is False
    assert result.controlled_credential_metadata_present is False
    assert result.controlled_api_call_allowed is False
    assert result.controlled_signing_allowed is False
    assert result.controlled_transport_allowed is False
    assert result.credential_injection_controlled_ready is True
    assert (
        result.credential_injection_controlled_mode
        == "CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY"
    )
    assert result.credential_injection_controlled_declared is True
    assert result.safe_credential_handle_label == "CONTROLLED_CREDENTIAL_HANDLE"
    assert result.safe_injection_status == "CREDENTIAL_INJECTION_READY_NO_SIGNING"
    assert result.controlled_injection_unknown is False
    assert result.controlled_injection_failed is False
    assert result.controlled_injection_unavailable is False
    assert result.controlled_injection_timeout is False
    assert result.controlled_injection_unsafe_exposure is False
    assert result.controlled_credential_value_exposure_attempted is False
    assert result.controlled_credential_raw_handle_exposure_attempted is False
    assert result.controlled_credential_metadata_exposure_attempted is False
    assert result.controlled_credential_length_exposure_attempted is False
    assert result.controlled_credential_hash_exposure_attempted is False
    assert result.controlled_credential_fingerprint_exposure_attempted is False
    assert result.controlled_env_actual_name_exposure_attempted is False
    assert result.credential_presence_adapter_ready is True
    assert result.presence_adapter_mode == "PRESENCE_ADAPTER_SKELETON_ONLY"
    assert result.operator_provided_presence_result is True
    assert result.operator_presence_result_is_boolean_only is True
    assert result.operator_presence_result_fresh is True
    assert result.operator_presence_result_reused is False
    assert result.operator_presence_result_stale is False
    assert result.operator_presence_result_previous_turn is False
    assert result.presence_result_adapted is True
    assert result.presence_result_displayed is False
    assert result.actual_environment_presence_check_performed is False
    assert result.real_checker_attached is False
    assert result.real_checker_executed is False
    assert result.credential_presence_checker_contract_ready is True
    assert result.checker_contract_mode == "CHECKER_CONTRACT_ONLY"
    assert result.checker_contract_requested is True
    assert result.checker_contract_ready_requested is True
    assert result.real_checker_implementation_present is False
    assert result.env_access_required is True
    assert result.env_access_allowed is False
    assert result.credential_values_available is False
    assert result.credential_values_read is False
    assert result.credential_metadata_available is False
    assert result.checker_result_available is False
    assert result.checker_result_saved is False
    assert result.checker_result_displayed is False
    assert result.checker_result_unknown is False
    assert result.checker_result_failed is False
    assert result.operator_checker_workflow_ready is True
    assert (
        result.operator_checker_workflow_mode
        == "OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY"
    )
    assert result.operator_workflow_declared is True
    assert result.operator_execution_required is True
    assert result.operator_execution_performed_outside_codex is True
    assert result.codex_execution_performed is False
    assert result.codex_env_access_requested is False
    assert result.actual_environment_presence_check_performed_by_codex is False
    assert result.operator_result_handoff_declared is True
    assert result.operator_result_handoff_safe is True
    assert result.operator_result_category_only is True
    assert result.operator_result_provided is True
    assert result.operator_result_is_boolean_only is True
    assert result.operator_result_raw_value_present is False
    assert result.operator_result_raw_value_saved is False
    assert result.operator_result_raw_value_displayed is False
    assert result.operator_result_fresh is True
    assert result.operator_result_stale is False
    assert result.operator_result_reused is False
    assert result.operator_result_previous_turn is False
    assert result.operator_result_timeout is False
    assert result.operator_result_unknown is False
    assert result.operator_result_failed is False
    assert result.operator_result_unavailable is False
    assert result.operator_result_saved is False
    assert result.operator_result_displayed is False
    assert result.operator_result_broadly_propagated is False
    assert result.operator_result_detail_present is False
    assert result.env_variable_names_present is False
    assert result.checker_result_detail_present is False
    assert result.checker_implementation_skeleton_ready is True
    assert result.checker_implementation_mode == "CHECKER_IMPLEMENTATION_SKELETON_ONLY"
    assert result.checker_execution_contract_ready is True
    assert result.checker_execution_contract_mode == "CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY"
    assert result.checker_execution_implementation_skeleton_ready is True
    assert (
        result.checker_execution_implementation_mode
        == "CHECKER_EXECUTION_IMPLEMENTATION_SKELETON_ONLY"
    )
    assert result.operator_executed_execution_boundary_ready is True
    assert (
        result.operator_execution_boundary_mode
        == "OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY"
    )
    assert result.operator_execution_boundary_declared is True
    assert result.operator_execution_must_be_outside_codex is True
    assert result.codex_execution_forbidden is True
    assert result.operator_execution_performed is False
    assert result.operator_execution_result_category_contract_ready is True
    assert (
        result.operator_execution_result_category_contract_mode
        == "OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ONLY"
    )
    assert result.category_contract_declared is True
    assert result.allowed_category_set_declared is True
    assert result.operator_result_category == "NOT_PROVIDED"
    assert result.operator_result_category_is_safe_label is True
    assert result.operator_result_category_is_allowed is True
    assert result.operator_result_ready_confirmed is False
    assert result.operator_result_blocked is False
    assert result.operator_result_handoff_policy_ready is True
    assert (
        result.operator_result_handoff_policy_mode
        == "OPERATOR_RESULT_HANDOFF_POLICY_SKELETON_ONLY"
    )
    assert result.policy_declared is True
    assert result.receipt_lifecycle_policy_declared is True
    assert result.policy_freshness_required is True
    assert result.policy_one_time_required is True
    assert result.policy_non_reuse_required is True
    assert result.policy_current_turn_required is True
    assert result.policy_previous_turn_prohibited is True
    assert result.policy_non_raw_required is True
    assert result.policy_non_detail_required is True
    assert result.policy_non_identifier_required is True
    assert result.policy_safe_category_only is True
    assert result.ready_confirmed_is_not_post_permission is True
    assert result.not_provided_is_not_actual_receipt is True
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_checker_execution_performed is False
    assert result.operator_result_handoff_lifecycle_ready is True
    assert (
        result.operator_result_handoff_lifecycle_mode
        == "OPERATOR_RESULT_HANDOFF_LIFECYCLE_SKELETON_ONLY"
    )
    assert result.lifecycle_declared is True
    assert result.lifecycle_transition_policy_declared is True
    assert result.lifecycle_from_state == "LIFECYCLE_POLICY_READY"
    assert result.lifecycle_to_state == "LIFECYCLE_RECEIPT_NOT_PROVIDED"
    assert result.lifecycle_event == "DECLARE_RECEIPT_NOT_PROVIDED"
    assert result.lifecycle_one_time_required is True
    assert result.lifecycle_fresh_required is True
    assert result.lifecycle_current_turn_required is True
    assert result.lifecycle_non_reuse_required is True
    assert result.lifecycle_previous_turn_prohibited is True
    assert result.lifecycle_stale_prohibited is True
    assert result.lifecycle_timeout_prohibited is True
    assert result.lifecycle_expired_prohibited is True
    assert result.lifecycle_non_raw_required is True
    assert result.lifecycle_non_detail_required is True
    assert result.lifecycle_non_identifier_required is True
    assert result.lifecycle_safe_category_only is True
    assert result.final_confirmation_received is False
    assert result.fresh_preflight_executed is False
    assert result.operator_result_handoff_receipt_ready is True
    assert (
        result.operator_result_handoff_receipt_mode
        == "OPERATOR_RESULT_HANDOFF_RECEIPT_SKELETON_ONLY"
    )
    assert result.receipt_contract_declared is True
    assert result.receipt_boundary_declared is True
    assert result.receipt_one_time_required is True
    assert result.receipt_fresh_required is True
    assert result.receipt_non_reuse_required is True
    assert result.receipt_non_raw_required is True
    assert result.receipt_non_detail_required is True
    assert result.receipt_provided is False
    assert result.receipt_category_confirmed is False
    assert result.receipt_current_turn is True
    assert result.receipt_fresh is True
    assert result.receipt_stale is False
    assert result.receipt_reused is False
    assert result.receipt_previous_turn is False
    assert result.receipt_expired is False
    assert result.receipt_timeout is False
    assert result.receipt_unknown is False
    assert result.receipt_failed is False
    assert result.receipt_unavailable is False
    assert result.receipt_raw_value_present is False
    assert result.receipt_detail_present is False
    assert result.receipt_id_present is False
    assert result.receipt_token_present is False
    assert result.receipt_nonce_present is False
    assert result.receipt_hash_present is False
    assert result.receipt_fingerprint_present is False
    assert result.receipt_length_present is False
    assert result.execution_contract_declared is True
    assert result.execution_inputs_declared is True
    assert result.execution_outputs_declared is True
    assert result.execution_stop_conditions_declared is True
    assert result.execution_implementation_declared is True
    assert result.execution_interface_declared is True
    assert result.implementation_interface_declared is True
    assert result.implementation_lifecycle_declared is True
    assert result.execution_lifecycle_declared is True
    assert result.execution_result_mapping_declared is True
    assert result.execution_deferred_to_future_step is True
    assert result.execution_performed is False
    assert result.execution_performed_by_codex is False
    assert result.execution_performed_by_operator is False
    assert result.credential_read_performed is False
    assert result.env_access_capability_present is False
    assert result.credential_read_capability_present is False
    assert result.checker_result_unavailable is False
    assert result.checker_result_stale is False
    assert result.checker_result_timeout is False
    assert result.operator_workflow_supported is True
    assert result.operator_workflow_preserved is True
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.credential_values_provided is False
    assert result.credential_values_loaded is False
    assert result.credential_presence_checked_against_environment is False
    assert result.env_access_requested is False
    assert result.credential_metadata_exposed is False
    assert result.signature_value_generated is False
    assert result.header_values_present is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.retry_allowed is False
    assert result.loop_allowed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"symbol": "EUR_JPY"},
        {"side": "SELL"},
        {"size": 101},
        {"executionType": "LIMIT"},
        {"codex_inferred": True},
    ],
)
def test_wrong_or_inferred_order_intent_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ORDER_INTENT


@pytest.mark.parametrize(
    "overrides",
    [
        {"final_confirmation_exact_match": False},
        {"final_confirmation_reused": True},
        {"approval_artifact_reestablished": False},
        {"approval_validation_passed": False},
        {"approval_exact_match_ready": False},
        {"approval_fingerprint": ""},
        {"sha256_prefix": ""},
    ],
)
def test_approval_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_APPROVAL


@pytest.mark.parametrize(
    "overrides",
    [
        {"approval_command_full_text_present": True},
        {"approval_command_displayed": True},
        {"approval_command_saved": True},
    ],
)
def test_approval_command_exposure_blocks_raw_secret(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE


@pytest.mark.parametrize(
    "overrides",
    [
        {"final_confirmation_preflight_passed": False},
        {"post_immediate_preflight_passed": False},
        {"market_session_state": "CLOSED"},
        {"market_hours_unknown": True},
        {"open_positions_count": 1},
        {"active_orders_count": 1},
        {"ticker_age_seconds": 31.0},
        {"ticker_age_seconds": -6.0},
        {"ticker_spread_jpy": 0.02},
        {"permission_scope_check_passed": False},
        {"ip_account_binding_check_passed": False},
        {"previous_result_unknown_check_passed": False},
    ],
)
def test_preflight_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_PREFLIGHT


@pytest.mark.parametrize(
    "overrides",
    [
        {"post_attempt_count_before": 1},
        {"post_attempt_limit": 2},
        {"retry_allowed": True},
        {"loop_allowed": True},
        {"add_order_allowed": True},
        {"change_order_allowed": True},
        {"cancel_order_allowed": True},
        {"close_order_allowed": True},
    ],
)
def test_attempt_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ATTEMPT_STATE


@pytest.mark.parametrize(
    ("field_name", "expected_status"),
    [
        ("pb_bridge_ready", Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE),
        ("eb_runtime_ready", Status.BLOCKED_STEP6G_INTERNAL_WIRING_RUNTIME_BRIDGE),
        (
            "ad_controlled_adapter_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_CONTROLLED_ADAPTER,
        ),
        ("ra_real_adapter_ready", Status.BLOCKED_STEP6G_INTERNAL_WIRING_REAL_ADAPTER),
        ("tc_transport_core_ready", Status.BLOCKED_STEP6G_INTERNAL_WIRING_TRANSPORT_CORE),
        (
            "st_signing_contract_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "st_private_transport_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_PRIVATE_TRANSPORT,
        ),
        ("dummy_signing_ready", Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT),
        (
            "dummy_signature_check_passed",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "http_transport_interface_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_PRIVATE_TRANSPORT,
        ),
        (
            "credential_boundary_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "credential_handle_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "credential_injection_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "credential_presence_check_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "credential_injection_controlled_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "credential_presence_adapter_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "credential_presence_checker_contract_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "operator_checker_workflow_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "checker_execution_contract_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "checker_execution_implementation_skeleton_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
    ],
)
def test_component_ready_flag_mismatch_blocks(
    field_name: str,
    expected_status: Status,
) -> None:
    result = _build(**{field_name: False})

    assert result.status is expected_status


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_values_provided": True},
        {"signature_value_generated": True},
        {"header_values_present": True},
        {"dummy_signature_value_present": True},
        {"dummy_signature_value_displayed": True},
        {"dummy_signature_value_saved": True},
        {"credential_values_loaded": True},
        {"credential_presence_checked_against_environment": True},
        {"env_access_requested": True},
        {"credential_metadata_exposed": True},
        {"handle_created": True},
        {"handle_contains_value": True},
        {"handle_contains_identifier": True},
        {"handle_metadata_exposed": True},
        {"injection_performed": True},
        {"real_credential_values_available": True},
        {"real_credential_values_injected": True},
        {"credential_injection_metadata_available": True},
        {"operator_sentinel_reused": True},
        {"operator_sentinel_stale": True},
        {"operator_sentinel_previous_turn": True},
        {"sentinel_value_present": True},
        {"sentinel_value_displayed": True},
        {"sentinel_value_saved": True},
        {"sentinel_hash_available": True},
        {"sentinel_fingerprint_available": True},
        {"sentinel_length_available": True},
        {"presence_result_broadly_propagated": True},
        {"presence_result_saved": True},
        {"operator_presence_result_reused": True},
        {"operator_presence_result_stale": True},
        {"operator_presence_result_previous_turn": True},
        {"presence_result_displayed": True},
        {"actual_environment_presence_check_performed": True},
        {"real_checker_attached": True},
        {"real_checker_executed": True},
        {"real_checker_implementation_present": True},
        {"env_access_allowed": True},
        {"credential_values_available": True},
        {"credential_values_read": True},
        {"credential_values_displayed": True},
        {"credential_values_saved": True},
        {"credential_metadata_available": True},
        {"credential_metadata_displayed": True},
        {"credential_metadata_saved": True},
        {"checker_result_available": True},
        {"checker_result_saved": True},
        {"checker_result_displayed": True},
        {"checker_result_broadly_propagated": True},
        {"checker_result_unknown": True},
        {"checker_result_failed": True},
        {"codex_env_access_requested": True},
        {"actual_environment_presence_check_performed_by_codex": True},
        {"operator_result_raw_value_present": True},
        {"operator_result_raw_value_saved": True},
        {"operator_result_raw_value_displayed": True},
        {"operator_result_timeout": True},
        {"operator_result_saved": True},
        {"operator_result_displayed": True},
        {"operator_result_broadly_propagated": True},
        {"operator_result_detail_present": True},
        {"env_variable_names_present": True},
        {"checker_result_detail_present": True},
        {"execution_performed_by_codex": True},
        {"execution_performed_by_operator": True},
        {"credential_read_performed": True},
        {"raw_request_displayed": True},
        {"raw_request_saved": True},
        {"raw_response_displayed": True},
        {"raw_response_saved": True},
        {"headers_displayed": True},
        {"signature_displayed": True},
        {"credentials_displayed": True},
        {"real_ids_displayed": True},
        {"checker_result_timeout": True},
    ],
)
def test_raw_secret_or_real_id_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE


@pytest.mark.parametrize(
    "overrides",
    [
        {"http_post_executed": True},
        {"order_endpoint_called": True},
        {"live_order_once_called": True},
    ],
)
def test_execution_boundary_crossing_blocks_route_bridge(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE


@pytest.mark.parametrize(
    "overrides",
    [
        {"http_client_present": True},
        {"can_execute_http_post": True},
        {"can_call_order_endpoint": True},
        {"can_call_live_order_once": True},
    ],
)
def test_http_transport_interface_boundary_crossing_blocks(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_PRIVATE_TRANSPORT
    assert result.http_transport_interface_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"step4_spoofing": True},
        {"ledger_changed": True},
    ],
)
def test_step4_spoofing_or_ledger_change_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_STEP4_SPOOFING


def test_build_valid_snapshot_uses_existing_safe_piece_results() -> None:
    snapshot = build_valid_step6g_internal_wiring_snapshot(created_at=CREATED_AT)

    assert snapshot.pb_result.bridge_ready is True
    assert snapshot.eb_result.fake_runtime_ready is True
    assert snapshot.ad_result.fake_adapter_ready is True
    assert snapshot.ra_result.real_adapter_contract_ready is True
    assert snapshot.tc_result.body_allowlist_passed is True
    assert snapshot.st_signing_result.signing_contract_ready is True
    assert snapshot.st_private_transport_result.transport_contract_ready is True
    assert snapshot.dummy_signing_result.dummy_signing_ready is True
    assert snapshot.dummy_signing_result.dummy_signature_check_passed is True
    assert snapshot.http_transport_interface_result.interface_ready is True
    assert snapshot.credential_boundary_result.credential_boundary_ready is True
    assert snapshot.credential_handle_result.credential_handle_ready is True
    assert snapshot.credential_injection_result.credential_injection_ready is True
    assert snapshot.credential_presence_check_result.credential_presence_check_ready is True
    assert (
        snapshot.credential_injection_controlled_result.credential_injection_ready
        is True
    )
    assert snapshot.credential_presence_adapter_result.credential_presence_adapter_ready is True
    assert (
        snapshot.credential_presence_checker_contract_result
        .credential_presence_checker_contract_ready
        is True
    )
    assert snapshot.operator_checker_workflow_result.operator_checker_workflow_ready is True
    assert (
        snapshot.credential_presence_checker_implementation_result
        .checker_implementation_skeleton_ready
        is True
    )
    assert (
        snapshot.credential_presence_checker_execution_contract_result
        .checker_execution_contract_ready
        is True
    )
    assert (
        snapshot.credential_presence_checker_execution_implementation_result
        .checker_execution_implementation_skeleton_ready
        is True
    )
    assert (
        snapshot.operator_executed_execution_boundary_result
        .operator_executed_execution_boundary_ready
        is True
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_assertion_provided": False},
        {"operator_assertion_is_boolean_only": False},
        {"operator_sentinel_received": False},
        {"operator_sentinel_fresh": False},
    ],
)
def test_credential_presence_check_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.credential_presence_check_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_presence_controlled_ready": False},
        {"credential_presence_controlled_checked": False},
        {"all_required_credentials_present": False},
        {"presence_unknown": True},
        {"presence_failed": True},
        {"presence_unavailable": True},
        {"presence_timeout": True},
    ],
)
def test_credential_presence_controlled_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.credential_presence_controlled_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"controlled_env_file_read": True},
        {"controlled_env_example_file_read": True},
        {"controlled_env_actual_names_present": True},
        {"controlled_credential_values_present": True},
        {"controlled_credential_lengths_present": True},
        {"controlled_credential_hashes_present": True},
        {"controlled_credential_fingerprints_present": True},
        {"controlled_credential_metadata_present": True},
        {"presence_unsafe_exposure": True},
    ],
)
def test_credential_presence_controlled_exposure_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
    assert result.internal_wiring_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"controlled_api_call_allowed": True},
        {"controlled_signing_allowed": True},
        {"controlled_transport_allowed": True},
    ],
)
def test_credential_presence_controlled_api_signing_transport_blocks(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.credential_presence_controlled_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_injection_controlled_declared": False},
        {"controlled_injection_unknown": True},
        {"controlled_injection_failed": True},
        {"controlled_injection_unavailable": True},
        {"controlled_injection_timeout": True},
    ],
)
def test_credential_injection_controlled_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.credential_injection_controlled_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"controlled_injection_unsafe_exposure": True},
        {"controlled_credential_value_exposure_attempted": True},
        {"controlled_credential_raw_handle_exposure_attempted": True},
        {"controlled_credential_metadata_exposure_attempted": True},
        {"controlled_credential_length_exposure_attempted": True},
        {"controlled_credential_hash_exposure_attempted": True},
        {"controlled_credential_fingerprint_exposure_attempted": True},
        {"controlled_env_actual_name_exposure_attempted": True},
    ],
)
def test_credential_injection_controlled_exposure_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
    assert result.internal_wiring_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"controlled_api_call_allowed": True},
        {"controlled_signing_allowed": True},
        {"controlled_transport_allowed": True},
    ],
)
def test_credential_injection_controlled_api_signing_transport_blocks(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.credential_injection_controlled_ready is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_provided_presence_result": False},
        {"operator_presence_result_is_boolean_only": False},
        {"operator_presence_result_fresh": False},
        {"presence_result_adapted": False},
    ],
)
def test_credential_presence_adapter_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.credential_presence_adapter_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"checker_contract_requested": False},
        {"checker_contract_ready_requested": False},
        {"checker_result_is_boolean_only": False},
        {"env_access_required": False},
    ],
)
def test_credential_presence_checker_contract_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.credential_presence_checker_contract_ready is False


def test_unsupported_checker_contract_mode_blocks_without_echoing_raw_value() -> None:
    result = _build(checker_contract_mode=UNSUPPORTED_RAW_MODE)
    rendered = render_live_order_real_step6g_internal_wiring_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.credential_presence_checker_contract_ready is False
    assert result.checker_contract_mode == UNSUPPORTED_SAFE_MODE
    assert (
        result.snapshot.credential_presence_checker_contract_result.checker_contract_mode
        == UNSUPPORTED_SAFE_MODE
    )
    assert (
        result.snapshot.credential_presence_checker_contract_result
        .unsupported_checker_contract_mode_present
        is True
    )
    assert result.snapshot.input_snapshot.checker_contract_mode == UNSUPPORTED_SAFE_MODE
    assert UNSUPPORTED_RAW_MODE not in repr(result)
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_workflow_declared": False},
        {"operator_execution_required": False},
        {"operator_execution_performed_outside_codex": False},
        {"operator_result_handoff_declared": False},
        {"operator_result_handoff_safe": False},
        {"operator_result_category_only": False},
        {"operator_result_provided": False},
        {"operator_result_is_boolean_only": False},
        {"operator_result_fresh": False},
        {"codex_execution_performed": True},
        {"operator_result_stale": True},
        {"operator_result_reused": True},
        {"operator_result_previous_turn": True},
        {"operator_result_unknown": True},
        {"operator_result_failed": True},
        {"operator_result_unavailable": True},
    ],
)
def test_operator_checker_workflow_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_checker_workflow_ready is False


def test_unsupported_operator_checker_workflow_mode_blocks_without_echoing_raw_value() -> None:
    result = _build(operator_checker_workflow_mode=UNSUPPORTED_RAW_MODE)
    rendered = render_live_order_real_step6g_internal_wiring_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_checker_workflow_ready is False
    assert result.operator_checker_workflow_mode == UNSUPPORTED_SAFE_MODE
    assert (
        result.snapshot.operator_checker_workflow_result.workflow_mode
        == UNSUPPORTED_SAFE_MODE
    )
    assert (
        result.snapshot.operator_checker_workflow_result
        .unsupported_workflow_mode_present
        is True
    )
    assert (
        result.snapshot.input_snapshot.operator_checker_workflow_mode
        == UNSUPPORTED_SAFE_MODE
    )
    assert UNSUPPORTED_RAW_MODE not in repr(result)
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"checker_implementation_skeleton_ready": False},
        {"implementation_interface_declared": False},
        {"implementation_lifecycle_declared": False},
        {"execution_deferred_to_future_step": False},
        {"operator_workflow_supported": False},
        {"operator_workflow_preserved": False},
    ],
)
def test_checker_implementation_skeleton_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.checker_implementation_skeleton_ready is False


def test_unsupported_checker_implementation_mode_blocks_without_echoing_raw_value() -> None:
    result = _build(checker_implementation_mode=UNSUPPORTED_RAW_MODE)
    rendered = render_live_order_real_step6g_internal_wiring_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.checker_implementation_skeleton_ready is False
    assert result.checker_implementation_mode == UNSUPPORTED_SAFE_MODE
    assert (
        result.snapshot.credential_presence_checker_implementation_result
        .implementation_mode
        == UNSUPPORTED_SAFE_MODE
    )
    assert (
        result.snapshot.credential_presence_checker_implementation_result
        .unsupported_implementation_mode_present
        is True
    )
    assert (
        result.snapshot.input_snapshot.checker_implementation_mode
        == UNSUPPORTED_SAFE_MODE
    )
    assert UNSUPPORTED_RAW_MODE not in repr(result)
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"checker_execution_contract_ready": False},
        {"execution_contract_declared": False},
        {"execution_inputs_declared": False},
        {"execution_outputs_declared": False},
        {"execution_stop_conditions_declared": False},
        {"execution_deferred_to_future_step": False},
        {"operator_workflow_preserved": False},
    ],
)
def test_checker_execution_contract_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.checker_execution_contract_ready is False


def test_unsupported_checker_execution_contract_mode_blocks_without_echoing_raw_value() -> None:
    result = _build(checker_execution_contract_mode=UNSUPPORTED_RAW_MODE)
    rendered = render_live_order_real_step6g_internal_wiring_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.checker_execution_contract_ready is False
    assert result.checker_execution_contract_mode == UNSUPPORTED_SAFE_MODE
    assert (
        result.snapshot.credential_presence_checker_execution_contract_result
        .execution_contract_mode
        == UNSUPPORTED_SAFE_MODE
    )
    assert (
        result.snapshot.credential_presence_checker_execution_contract_result
        .unsupported_execution_contract_mode_present
        is True
    )
    assert (
        result.snapshot.input_snapshot.checker_execution_contract_mode
        == UNSUPPORTED_SAFE_MODE
    )
    assert UNSUPPORTED_RAW_MODE not in repr(result)
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"codex_env_access_requested": True},
        {"execution_performed": True},
        {"env_access_capability_present": True},
        {"credential_read_capability_present": True},
        {"checker_result_available": True},
        {"checker_result_detail_present": True},
        {"checker_result_unavailable": True},
        {"checker_result_stale": True},
    ],
)
def test_checker_implementation_raw_or_secret_exposure_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
    assert result.internal_wiring_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"execution_performed": True},
        {"execution_performed_by_codex": True},
        {"execution_performed_by_operator": True},
        {"codex_env_access_requested": True},
        {"checker_result_available": True},
        {"checker_result_timeout": True},
    ],
)
def test_checker_execution_contract_raw_or_secret_exposure_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
    assert result.internal_wiring_ready is False


def test_checker_execution_contract_post_allowed_blocks_internal_wiring() -> None:
    result = _build(post_allowed_this_step=True)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE
    assert result.internal_wiring_ready is False


def test_checker_execution_contract_post_executed_hard_stops_internal_wiring() -> None:
    with pytest.raises(LiveVerificationValidationError):
        _build(post_executed=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"checker_execution_implementation_skeleton_ready": False},
        {"execution_implementation_declared": False},
        {"execution_interface_declared": False},
        {"execution_lifecycle_declared": False},
        {"execution_result_mapping_declared": False},
        {"execution_stop_conditions_declared": False},
        {"execution_deferred_to_future_step": False},
        {"operator_result_handoff_safe": False},
    ],
)
def test_checker_execution_implementation_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.checker_execution_implementation_skeleton_ready is False


def test_unsupported_checker_execution_implementation_mode_blocks_without_echoing_raw_value(
) -> None:
    result = _build(checker_execution_implementation_mode=UNSUPPORTED_RAW_MODE)
    rendered = render_live_order_real_step6g_internal_wiring_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.checker_execution_implementation_skeleton_ready is False
    assert result.checker_execution_implementation_mode == UNSUPPORTED_SAFE_MODE
    assert (
        result.snapshot.credential_presence_checker_execution_implementation_result
        .execution_implementation_mode
        == UNSUPPORTED_SAFE_MODE
    )
    assert (
        result.snapshot.credential_presence_checker_execution_implementation_result
        .unsupported_execution_implementation_mode_present
        is True
    )
    assert (
        result.snapshot.input_snapshot.checker_execution_implementation_mode
        == UNSUPPORTED_SAFE_MODE
    )
    assert UNSUPPORTED_RAW_MODE not in repr(result)
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"execution_performed": True},
        {"execution_performed_by_codex": True},
        {"execution_performed_by_operator": True},
        {"env_access_requested": True},
        {"codex_env_access_requested": True},
        {"checker_result_available": True},
        {"checker_result_detail_present": True},
        {"checker_result_timeout": True},
        {"operator_result_raw_value_present": True},
    ],
)
def test_checker_execution_implementation_raw_or_secret_exposure_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
    assert result.internal_wiring_ready is False


def test_checker_execution_implementation_post_allowed_blocks_internal_wiring() -> None:
    result = _build(post_allowed_this_step=True)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE
    assert result.internal_wiring_ready is False


def test_checker_execution_implementation_post_executed_hard_stops_internal_wiring() -> None:
    with pytest.raises(LiveVerificationValidationError):
        _build(post_executed=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_executed_execution_boundary_ready": False},
        {"operator_execution_boundary_declared": False},
        {"operator_execution_must_be_outside_codex": False},
        {"codex_execution_forbidden": False},
    ],
)
def test_operator_executed_execution_boundary_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_executed_execution_boundary_ready is False


def test_unsupported_operator_execution_boundary_mode_blocks_without_echoing_raw_value(
) -> None:
    result = _build(operator_execution_boundary_mode=UNSUPPORTED_RAW_MODE)
    rendered = render_live_order_real_step6g_internal_wiring_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_executed_execution_boundary_ready is False
    assert result.operator_execution_boundary_mode == UNSUPPORTED_SAFE_MODE
    assert (
        result.snapshot.operator_executed_execution_boundary_result.boundary_mode
        == UNSUPPORTED_SAFE_MODE
    )
    assert (
        result.snapshot.operator_executed_execution_boundary_result
        .unsupported_boundary_mode_present
        is True
    )
    assert result.snapshot.input_snapshot.operator_execution_boundary_mode == (
        UNSUPPORTED_SAFE_MODE
    )
    assert UNSUPPORTED_RAW_MODE not in repr(result)
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_execution_performed": True},
        {"env_access_requested": True},
        {"actual_environment_presence_check_performed": True},
        {"operator_result_raw_value_present": True},
    ],
)
def test_operator_executed_execution_boundary_raw_or_secret_exposure_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
    assert result.internal_wiring_ready is False


def test_operator_executed_execution_boundary_codex_execution_blocks_internal_wiring(
) -> None:
    result = _build(codex_execution_performed=True)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.internal_wiring_ready is False


def test_operator_executed_execution_boundary_post_allowed_blocks_internal_wiring() -> None:
    result = _build(post_allowed_this_step=True)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE
    assert result.internal_wiring_ready is False


def test_operator_executed_execution_boundary_post_executed_hard_stops_internal_wiring(
) -> None:
    with pytest.raises(LiveVerificationValidationError):
        _build(post_executed=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_execution_result_category_contract_ready": False},
        {"category_contract_declared": False},
        {"allowed_category_set_declared": False},
        {"operator_result_category_is_safe_label": False},
        {"operator_result_category_is_allowed": False},
    ],
)
def test_operator_execution_result_category_contract_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_execution_result_category_contract_ready is False
    assert result.internal_wiring_ready is False


def test_unsupported_operator_result_category_blocks_without_echoing_raw_value(
) -> None:
    result = _build(operator_result_category=UNSUPPORTED_RAW_MODE)
    rendered = render_live_order_real_step6g_internal_wiring_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_execution_result_category_contract_ready is False
    assert result.operator_result_category == UNSUPPORTED_SAFE_MODE
    assert (
        result.snapshot.operator_execution_result_category_contract_result
        .operator_result_category
        == UNSUPPORTED_SAFE_MODE
    )
    assert result.snapshot.input_snapshot.operator_result_category == (
        UNSUPPORTED_SAFE_MODE
    )
    assert UNSUPPORTED_RAW_MODE not in repr(result)
    assert UNSUPPORTED_RAW_MODE not in rendered
    assert UNSUPPORTED_RAW_MODE not in payload
    assert UNSUPPORTED_SAFE_MODE in rendered
    assert UNSUPPORTED_SAFE_MODE in payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_category": "BLOCKED_UNKNOWN"},
        {"operator_result_category": "BLOCKED_FAILED"},
        {"operator_result_category": "BLOCKED_UNAVAILABLE"},
        {"operator_result_category": "BLOCKED_STALE"},
        {"operator_result_category": "BLOCKED_TIMEOUT"},
        {"operator_result_category": "BLOCKED_REUSED"},
        {"operator_result_category": "BLOCKED_PREVIOUS_TURN"},
    ],
)
def test_operator_execution_result_blocked_categories_block_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_execution_result_category_contract_ready is False
    assert result.operator_result_blocked is True
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


def test_operator_execution_result_ready_confirmed_does_not_allow_post(
) -> None:
    result = _build(operator_result_category="READY_CONFIRMED")

    assert result.status is Status.STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST
    assert result.operator_execution_result_category_contract_ready is True
    assert result.operator_result_category == "READY_CONFIRMED"
    assert result.operator_result_ready_confirmed is True
    assert result.can_execute_http_post is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_handoff_policy_ready": False},
        {"policy_declared": False},
        {"receipt_lifecycle_policy_declared": False},
        {"policy_freshness_required": False},
        {"policy_one_time_required": False},
        {"policy_non_reuse_required": False},
        {"policy_current_turn_required": False},
        {"policy_previous_turn_prohibited": False},
        {"policy_non_raw_required": False},
        {"policy_non_detail_required": False},
        {"policy_non_identifier_required": False},
        {"policy_safe_category_only": False},
        {"ready_confirmed_is_not_post_permission": False},
        {"not_provided_is_not_actual_receipt": False},
    ],
)
def test_operator_result_handoff_policy_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_result_handoff_policy_ready is False
    assert result.operator_result_handoff_receipt_ready is False
    assert result.internal_wiring_ready is False


def test_operator_result_handoff_policy_ready_confirmed_does_not_allow_post(
) -> None:
    result = _build(operator_result_category="READY_CONFIRMED")

    assert result.status is Status.STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST
    assert result.operator_result_handoff_policy_ready is True
    assert result.operator_result_category == "READY_CONFIRMED"
    assert result.ready_confirmed_is_not_post_permission is True
    assert result.not_provided_is_not_actual_receipt is True
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_checker_execution_performed is False
    assert result.can_execute_http_post is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_current_turn": False},
        {"receipt_fresh": False},
        {"receipt_stale": True},
        {"receipt_reused": True},
        {"receipt_previous_turn": True},
        {"receipt_expired": True},
        {"receipt_timeout": True},
        {"actual_execution_performed": True},
    ],
)
def test_operator_result_handoff_policy_state_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_result_handoff_policy_ready is False
    assert result.internal_wiring_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_raw_value_present": True},
        {"receipt_detail_present": True},
        {"receipt_id_present": True},
        {"receipt_token_present": True},
        {"receipt_nonce_present": True},
        {"receipt_hash_present": True},
        {"receipt_fingerprint_present": True},
        {"receipt_length_present": True},
        {"env_access_requested": True},
        {"actual_receipt_handoff_executed": True},
        {"actual_result_receipt_received": True},
        {"actual_checker_execution_performed": True},
    ],
)
def test_operator_result_handoff_policy_raw_secret_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
    assert result.internal_wiring_ready is False


def test_operator_result_handoff_policy_post_allowed_blocks_internal_wiring() -> None:
    result = _build(post_allowed_this_step=True)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE
    assert result.internal_wiring_ready is False


def test_operator_result_handoff_policy_post_executed_hard_stops_internal_wiring(
) -> None:
    with pytest.raises(LiveVerificationValidationError):
        _build(post_executed=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_handoff_lifecycle_ready": False},
        {"lifecycle_declared": False},
        {"lifecycle_transition_policy_declared": False},
        {"lifecycle_one_time_required": False},
        {"lifecycle_fresh_required": False},
        {"lifecycle_current_turn_required": False},
        {"lifecycle_non_reuse_required": False},
        {"lifecycle_previous_turn_prohibited": False},
        {"lifecycle_stale_prohibited": False},
        {"lifecycle_timeout_prohibited": False},
        {"lifecycle_expired_prohibited": False},
        {"lifecycle_non_raw_required": False},
        {"lifecycle_non_detail_required": False},
        {"lifecycle_non_identifier_required": False},
        {"lifecycle_safe_category_only": False},
        {"ready_confirmed_is_not_post_permission": False},
        {"not_provided_is_not_actual_receipt": False},
    ],
)
def test_operator_result_handoff_lifecycle_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_result_handoff_lifecycle_ready is False
    assert result.operator_result_handoff_receipt_ready is False
    assert result.internal_wiring_ready is False


def test_operator_result_handoff_lifecycle_ready_confirmed_does_not_allow_post(
) -> None:
    result = _build(operator_result_category="READY_CONFIRMED")

    assert result.status is Status.STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST
    assert result.operator_result_handoff_lifecycle_ready is True
    assert result.operator_result_category == "READY_CONFIRMED"
    assert result.lifecycle_to_state == "LIFECYCLE_READY_CONFIRMED_NO_POST"
    assert result.ready_confirmed_is_not_post_permission is True
    assert result.not_provided_is_not_actual_receipt is True
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_checker_execution_performed is False
    assert result.can_execute_http_post is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.final_confirmation_received is False
    assert result.fresh_preflight_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"lifecycle_event": "DECLARE_STALE"},
        {"lifecycle_event": "DECLARE_REUSED"},
        {"lifecycle_event": "DECLARE_PREVIOUS_TURN"},
        {"lifecycle_event": "DECLARE_TIMEOUT"},
        {"lifecycle_event": "DECLARE_UNKNOWN"},
        {"lifecycle_event": "DECLARE_FAILED"},
        {"lifecycle_event": "DECLARE_UNAVAILABLE"},
        {"lifecycle_event": "DECLARE_RAW_PRESENT"},
        {"lifecycle_event": "DECLARE_DETAIL_PRESENT"},
        {"lifecycle_event": "DECLARE_IDENTIFIER_PRESENT"},
        {"receipt_current_turn": False},
        {"receipt_fresh": False},
        {"receipt_stale": True},
        {"receipt_reused": True},
        {"receipt_previous_turn": True},
        {"receipt_expired": True},
        {"receipt_timeout": True},
        {"receipt_unknown": True},
        {"receipt_failed": True},
        {"receipt_unavailable": True},
        {"final_confirmation_received": True},
        {"fresh_preflight_executed": True},
    ],
)
def test_operator_result_handoff_lifecycle_state_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_result_handoff_lifecycle_ready is False
    assert result.internal_wiring_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_raw_value_present": True},
        {"receipt_detail_present": True},
        {"receipt_id_present": True},
        {"receipt_token_present": True},
        {"receipt_nonce_present": True},
        {"receipt_hash_present": True},
        {"receipt_fingerprint_present": True},
        {"receipt_length_present": True},
        {"env_access_requested": True},
        {"actual_receipt_handoff_executed": True},
        {"actual_result_receipt_received": True},
        {"actual_checker_execution_performed": True},
    ],
)
def test_operator_result_handoff_lifecycle_raw_secret_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
    assert result.internal_wiring_ready is False


def test_operator_result_handoff_lifecycle_post_allowed_blocks_internal_wiring() -> None:
    result = _build(post_allowed_this_step=True)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE
    assert result.internal_wiring_ready is False


def test_operator_result_handoff_lifecycle_post_executed_hard_stops_internal_wiring(
) -> None:
    with pytest.raises(LiveVerificationValidationError):
        _build(post_executed=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_handoff_receipt_ready": False},
        {"receipt_contract_declared": False},
        {"receipt_boundary_declared": False},
        {"receipt_one_time_required": False},
        {"receipt_fresh_required": False},
        {"receipt_non_reuse_required": False},
        {"receipt_non_raw_required": False},
        {"receipt_non_detail_required": False},
    ],
)
def test_operator_result_handoff_receipt_not_ready_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_result_handoff_receipt_ready is False
    assert result.internal_wiring_ready is False


def test_operator_result_handoff_receipt_ready_confirmed_does_not_allow_post(
) -> None:
    result = _build(operator_result_category="READY_CONFIRMED")

    assert result.status is Status.STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST
    assert result.operator_result_handoff_receipt_ready is True
    assert result.operator_result_category == "READY_CONFIRMED"
    assert result.receipt_provided is True
    assert result.receipt_category_confirmed is True
    assert result.receipt_current_turn is True
    assert result.receipt_fresh is True
    assert result.can_execute_http_post is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_current_turn": False},
        {"receipt_fresh": False},
        {"receipt_stale": True},
        {"receipt_reused": True},
        {"receipt_previous_turn": True},
        {"receipt_expired": True},
        {"receipt_timeout": True},
        {"actual_execution_performed": True},
    ],
)
def test_operator_result_handoff_receipt_state_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_result_handoff_receipt_ready is False
    assert result.internal_wiring_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_raw_value_present": True},
        {"receipt_detail_present": True},
        {"receipt_id_present": True},
        {"receipt_token_present": True},
        {"receipt_nonce_present": True},
        {"receipt_hash_present": True},
        {"receipt_fingerprint_present": True},
        {"receipt_length_present": True},
        {"env_access_requested": True},
    ],
)
def test_operator_result_handoff_receipt_raw_secret_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
    assert result.internal_wiring_ready is False


def test_operator_result_handoff_receipt_post_allowed_blocks_internal_wiring() -> None:
    result = _build(post_allowed_this_step=True)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE
    assert result.internal_wiring_ready is False


def test_operator_result_handoff_receipt_post_executed_hard_stops_internal_wiring(
) -> None:
    with pytest.raises(LiveVerificationValidationError):
        _build(post_executed=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_handoff_non_execution_boundary_ready": False},
        {"non_execution_boundary_declared": False},
        {"actual_handoff_prohibited": False},
        {"actual_receipt_prohibited": False},
        {"actual_checker_execution_prohibited": False},
        {"env_access_prohibited": False},
        {"credential_read_prohibited": False},
        {"credential_injection_prohibited": False},
        {"api_prohibited": False},
        {"post_prohibited": False},
        {"live_order_once_prohibited": False},
        {"fresh_preflight_prohibited": False},
        {"final_confirmation_prohibited": False},
        {"raw_detail_identifier_prohibited": False},
        {"ready_flags_are_not_post_permission": False},
        {"ready_flags_are_not_actual_handoff_permission": False},
    ],
)
def test_operator_result_handoff_non_execution_boundary_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_result_handoff_non_execution_boundary_ready is False
    assert result.internal_wiring_ready is False


def test_operator_result_handoff_non_execution_boundary_ready_confirmed_no_post(
) -> None:
    result = _build(operator_result_category="READY_CONFIRMED")

    assert result.status is Status.STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST
    assert result.operator_result_handoff_non_execution_boundary_ready is True
    assert result.operator_result_category == "READY_CONFIRMED"
    assert result.ready_flags_are_not_post_permission is True
    assert result.ready_flags_are_not_actual_handoff_permission is True
    assert result.actual_handoff_prohibited is True
    assert result.actual_receipt_prohibited is True
    assert result.actual_checker_execution_prohibited is True
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_result_receipt_received is False
    assert result.actual_checker_execution_performed is False
    assert result.env_access_prohibited is True
    assert result.credential_read_prohibited is True
    assert result.credential_injection_prohibited is True
    assert result.api_prohibited is True
    assert result.post_prohibited is True
    assert result.live_order_once_prohibited is True
    assert result.can_execute_http_post is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.final_confirmation_received is False
    assert result.fresh_preflight_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_handoff_receipt_ready": False},
        {"operator_result_handoff_policy_ready": False},
        {"operator_result_handoff_lifecycle_ready": False},
    ],
)
def test_non_execution_boundary_requires_receipt_policy_lifecycle_ready(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_result_handoff_non_execution_boundary_ready is False
    assert result.internal_wiring_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"receipt_raw_value_present": True},
        {"receipt_detail_present": True},
        {"receipt_id_present": True},
        {"receipt_token_present": True},
        {"receipt_nonce_present": True},
        {"receipt_hash_present": True},
        {"receipt_fingerprint_present": True},
        {"receipt_length_present": True},
        {"operator_result_raw_value_present": True},
        {"operator_result_detail_present": True},
        {"checker_result_detail_present": True},
        {"env_access_requested": True},
        {"credential_read_performed": True},
        {"actual_receipt_handoff_executed": True},
        {"actual_result_receipt_received": True},
        {"actual_checker_execution_performed": True},
    ],
)
def test_non_execution_boundary_raw_secret_or_actual_attempt_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
    assert result.internal_wiring_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"final_confirmation_received": True},
        {"fresh_preflight_executed": True},
    ],
)
def test_non_execution_boundary_confirmation_or_preflight_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
    assert result.operator_result_handoff_non_execution_boundary_ready is False
    assert result.internal_wiring_ready is False


def test_non_execution_boundary_post_allowed_blocks_internal_wiring() -> None:
    result = _build(post_allowed_this_step=True)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE
    assert result.internal_wiring_ready is False


def test_non_execution_boundary_post_executed_hard_stops_internal_wiring() -> None:
    with pytest.raises(LiveVerificationValidationError):
        _build(post_executed=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"operator_result_raw_value_present": True},
        {"operator_result_detail_present": True},
        {"env_access_requested": True},
        {"credential_read_performed": True},
        {"operator_execution_performed": True},
    ],
)
def test_operator_execution_result_category_raw_or_secret_exposure_blocks_internal_wiring(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
    assert result.internal_wiring_ready is False


def test_operator_execution_result_category_post_allowed_blocks_internal_wiring(
) -> None:
    result = _build(post_allowed_this_step=True)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE
    assert result.internal_wiring_ready is False


def test_operator_execution_result_category_post_executed_hard_stops_internal_wiring(
) -> None:
    with pytest.raises(LiveVerificationValidationError):
        _build(post_executed=True)



def test_renderer_includes_warnings_and_no_sensitive_values() -> None:
    result = _build()
    rendered = render_live_order_real_step6g_internal_wiring_markdown(result)

    assert "This internal wiring is fake/sanitized only." in rendered
    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "does not call order endpoint" in rendered
    assert "does not call live_order_once" in rendered
    assert "does not use real credentials" in rendered
    assert "does not generate real signatures" in rendered
    assert "dummy_signing_ready: true" in rendered
    assert "dummy_signature_check_passed: true" in rendered
    assert "http_transport_interface_ready: true" in rendered
    assert "credential_boundary_ready: true" in rendered
    assert "credential_boundary_mode: BOUNDARY_ONLY" in rendered
    assert "credential_handle_ready: true" in rendered
    assert "credential_handle_mode: HANDLE_CONTRACT_ONLY" in rendered
    assert "credential_injection_ready: true" in rendered
    assert "credential_injection_mode: INJECTION_SKELETON_ONLY" in rendered
    assert "credential_presence_check_ready: true" in rendered
    assert "presence_check_mode: OPERATOR_PROVIDED_SENTINEL_ONLY" in rendered
    assert "credential_presence_controlled_ready: true" in rendered
    assert (
        "credential_presence_controlled_mode: "
        "CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY"
    ) in rendered
    assert "credential_presence_controlled_checked: true" in rendered
    assert "all_required_credentials_present: true" in rendered
    assert "presence_missing: false" in rendered
    assert "controlled_env_access_for_presence_only: true" in rendered
    assert "controlled_env_actual_names_present: false" in rendered
    assert "controlled_credential_values_present: false" in rendered
    assert "controlled_credential_lengths_present: false" in rendered
    assert "controlled_credential_hashes_present: false" in rendered
    assert "controlled_credential_fingerprints_present: false" in rendered
    assert "controlled_credential_metadata_present: false" in rendered
    assert "credential_injection_controlled_ready: true" in rendered
    assert (
        "credential_injection_controlled_mode: "
        "CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY"
    ) in rendered
    assert "safe_credential_handle_label: CONTROLLED_CREDENTIAL_HANDLE" in rendered
    assert "safe_injection_status: CREDENTIAL_INJECTION_READY_NO_SIGNING" in rendered
    assert "controlled_injection_unknown: false" in rendered
    assert "controlled_injection_failed: false" in rendered
    assert "controlled_injection_unavailable: false" in rendered
    assert "controlled_injection_timeout: false" in rendered
    assert "controlled_injection_unsafe_exposure: false" in rendered
    assert "controlled_credential_value_exposure_attempted: false" in rendered
    assert "controlled_credential_raw_handle_exposure_attempted: false" in rendered
    assert "controlled_credential_metadata_exposure_attempted: false" in rendered
    assert "controlled_credential_length_exposure_attempted: false" in rendered
    assert "controlled_credential_hash_exposure_attempted: false" in rendered
    assert "controlled_credential_fingerprint_exposure_attempted: false" in rendered
    assert "controlled_env_actual_name_exposure_attempted: false" in rendered
    assert "credential_presence_adapter_ready: true" in rendered
    assert "presence_adapter_mode: PRESENCE_ADAPTER_SKELETON_ONLY" in rendered
    assert "handle_requested: true" in rendered
    assert "handle_created: false" in rendered
    assert "handle_contains_value: false" in rendered
    assert "handle_contains_identifier: false" in rendered
    assert "handle_metadata_exposed: false" in rendered
    assert "http_client_present: false" in rendered
    assert "can_execute_http_post: false" in rendered
    assert "credential_values_loaded: false" in rendered
    assert "env_access_requested: false" in rendered
    assert "credential_metadata_exposed: false" in rendered
    assert "injection_requested: true" in rendered
    assert "injection_performed: false" in rendered
    assert "real_credential_values_available: false" in rendered
    assert "real_credential_values_injected: false" in rendered
    assert "credential_injection_metadata_available: false" in rendered
    assert "operator_assertion_provided: true" in rendered
    assert "operator_assertion_is_boolean_only: true" in rendered
    assert "operator_sentinel_received: true" in rendered
    assert "operator_sentinel_fresh: true" in rendered
    assert "operator_sentinel_reused: false" in rendered
    assert "operator_sentinel_stale: false" in rendered
    assert "operator_sentinel_previous_turn: false" in rendered
    assert "sentinel_value_present: false" in rendered
    assert "sentinel_hash_available: false" in rendered
    assert "sentinel_fingerprint_available: false" in rendered
    assert "sentinel_length_available: false" in rendered
    assert "operator_provided_presence_result: true" in rendered
    assert "operator_presence_result_is_boolean_only: true" in rendered
    assert "operator_presence_result_fresh: true" in rendered
    assert "operator_presence_result_reused: false" in rendered
    assert "operator_presence_result_stale: false" in rendered
    assert "operator_presence_result_previous_turn: false" in rendered
    assert "presence_result_adapted: true" in rendered
    assert "presence_result_displayed: false" in rendered
    assert "actual_environment_presence_check_performed: false" in rendered
    assert "real_checker_attached: false" in rendered
    assert "real_checker_executed: false" in rendered
    assert "credential_presence_checker_contract_ready: true" in rendered
    assert "checker_contract_mode: CHECKER_CONTRACT_ONLY" in rendered
    assert "operator_checker_workflow_ready: true" in rendered
    assert (
        "operator_checker_workflow_mode: "
        "OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY"
    ) in rendered
    assert "operator_workflow_declared: true" in rendered
    assert "operator_execution_required: true" in rendered
    assert "operator_execution_performed_outside_codex: true" in rendered
    assert "codex_execution_performed: false" in rendered
    assert "codex_env_access_requested: false" in rendered
    assert "actual_environment_presence_check_performed_by_codex: false" in rendered
    assert "operator_result_handoff_declared: true" in rendered
    assert "operator_result_handoff_safe: true" in rendered
    assert "operator_result_category_only: true" in rendered
    assert "operator_result_provided: true" in rendered
    assert "operator_result_is_boolean_only: true" in rendered
    assert "operator_result_raw_value_present: false" in rendered
    assert "operator_result_raw_value_saved: false" in rendered
    assert "operator_result_raw_value_displayed: false" in rendered
    assert "operator_result_fresh: true" in rendered
    assert "operator_result_unknown: false" in rendered
    assert "operator_result_timeout: false" in rendered
    assert "operator_result_failed: false" in rendered
    assert "operator_result_unavailable: false" in rendered
    assert "operator_result_detail_present: false" in rendered
    assert "env_variable_names_present: false" in rendered
    assert "checker_result_detail_present: false" in rendered
    assert "checker_implementation_skeleton_ready: true" in rendered
    assert "checker_implementation_mode: CHECKER_IMPLEMENTATION_SKELETON_ONLY" in rendered
    assert "checker_execution_contract_ready: true" in rendered
    assert (
        "checker_execution_contract_mode: "
        "CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY"
    ) in rendered
    assert "checker_execution_implementation_skeleton_ready: true" in rendered
    assert (
        "checker_execution_implementation_mode: "
        "CHECKER_EXECUTION_IMPLEMENTATION_SKELETON_ONLY"
    ) in rendered
    assert "operator_executed_execution_boundary_ready: true" in rendered
    assert (
        "operator_execution_boundary_mode: "
        "OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY"
    ) in rendered
    assert "operator_execution_boundary_declared: true" in rendered
    assert "operator_execution_must_be_outside_codex: true" in rendered
    assert "codex_execution_forbidden: true" in rendered
    assert "operator_execution_performed: false" in rendered
    assert "operator_result_handoff_policy_ready: true" in rendered
    assert (
        "operator_result_handoff_policy_mode: "
        "OPERATOR_RESULT_HANDOFF_POLICY_SKELETON_ONLY"
    ) in rendered
    assert "policy_declared: true" in rendered
    assert "receipt_lifecycle_policy_declared: true" in rendered
    assert "policy_freshness_required: true" in rendered
    assert "policy_one_time_required: true" in rendered
    assert "policy_non_reuse_required: true" in rendered
    assert "policy_current_turn_required: true" in rendered
    assert "policy_previous_turn_prohibited: true" in rendered
    assert "policy_non_raw_required: true" in rendered
    assert "policy_non_detail_required: true" in rendered
    assert "policy_non_identifier_required: true" in rendered
    assert "policy_safe_category_only: true" in rendered
    assert "ready_confirmed_is_not_post_permission: true" in rendered
    assert "not_provided_is_not_actual_receipt: true" in rendered
    assert "actual_receipt_handoff_executed: false" in rendered
    assert "actual_result_receipt_received: false" in rendered
    assert "actual_checker_execution_performed: false" in rendered
    assert "operator_result_handoff_lifecycle_ready: true" in rendered
    assert (
        "operator_result_handoff_lifecycle_mode: "
        "OPERATOR_RESULT_HANDOFF_LIFECYCLE_SKELETON_ONLY"
    ) in rendered
    assert "lifecycle_from_state: LIFECYCLE_POLICY_READY" in rendered
    assert "lifecycle_to_state: LIFECYCLE_RECEIPT_NOT_PROVIDED" in rendered
    assert "lifecycle_event: DECLARE_RECEIPT_NOT_PROVIDED" in rendered
    assert "lifecycle_declared: true" in rendered
    assert "lifecycle_transition_policy_declared: true" in rendered
    assert "lifecycle_one_time_required: true" in rendered
    assert "lifecycle_fresh_required: true" in rendered
    assert "lifecycle_current_turn_required: true" in rendered
    assert "lifecycle_non_reuse_required: true" in rendered
    assert "lifecycle_previous_turn_prohibited: true" in rendered
    assert "lifecycle_non_raw_required: true" in rendered
    assert "lifecycle_non_detail_required: true" in rendered
    assert "lifecycle_non_identifier_required: true" in rendered
    assert "lifecycle_safe_category_only: true" in rendered
    assert "final_confirmation_received: false" in rendered
    assert "fresh_preflight_executed: false" in rendered
    assert "execution_contract_declared: true" in rendered
    assert "execution_inputs_declared: true" in rendered
    assert "execution_outputs_declared: true" in rendered
    assert "execution_stop_conditions_declared: true" in rendered
    assert "execution_implementation_declared: true" in rendered
    assert "execution_interface_declared: true" in rendered
    assert "implementation_interface_declared: true" in rendered
    assert "implementation_lifecycle_declared: true" in rendered
    assert "execution_lifecycle_declared: true" in rendered
    assert "execution_result_mapping_declared: true" in rendered
    assert "execution_deferred_to_future_step: true" in rendered
    assert "execution_performed: false" in rendered
    assert "execution_performed_by_codex: false" in rendered
    assert "execution_performed_by_operator: false" in rendered
    assert "credential_read_performed: false" in rendered
    assert "env_access_capability_present: false" in rendered
    assert "credential_read_capability_present: false" in rendered
    assert "checker_result_unavailable: false" in rendered
    assert "checker_result_stale: false" in rendered
    assert "checker_result_timeout: false" in rendered
    assert "operator_workflow_supported: true" in rendered
    assert "operator_workflow_preserved: true" in rendered
    assert "real_checker_implementation_present: false" in rendered
    assert "env_access_allowed: false" in rendered
    assert "credential_values_read: false" in rendered
    assert "checker_result_available: false" in rendered
    assert "checker_result_saved: false" in rendered
    assert "checker_result_displayed: false" in rendered
    assert "checker_result_unknown: false" in rendered
    assert "checker_result_failed: false" in rendered
    assert "Future real execution requires a new final confirmation" in rendered
    assert "FULL_APPROVAL_COMMAND_SENTINEL" not in rendered
    assert "OPERATOR_SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in rendered
    assert "RAW_REQUEST_SENTINEL" not in rendered
    assert "RAW_RESPONSE_SENTINEL" not in rendered
    assert "REAL_ORDER_ID_SENTINEL" not in rendered
    assert "OPERATOR_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in rendered
    assert "RAW_OPERATOR_RESULT_VALUE_SHOULD_NOT_APPEAR" not in rendered
    assert "CHECKER_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in rendered
    assert "ENV_NAME_SHOULD_NOT_APPEAR" not in rendered
    assert '{"executionType":"MARKET"' not in rendered
    assert UNSUPPORTED_RAW_MODE not in rendered


def test_asdict_does_not_contain_raw_secret_real_ids_or_full_approval_command() -> None:
    result = _build()
    payload = repr(asdict(result))

    assert "FULL_APPROVAL_COMMAND_SENTINEL" not in payload
    assert "RAW_REQUEST_SENTINEL" not in payload
    assert "RAW_RESPONSE_SENTINEL" not in payload
    assert "REAL_ORDER_ID_SENTINEL" not in payload
    assert "REAL_EXECUTION_ID_SENTINEL" not in payload
    assert "REAL_POSITION_ID_SENTINEL" not in payload
    assert UNSUPPORTED_RAW_MODE not in payload
    assert "DUMMY_SIGNATURE_VALUE_SENTINEL" not in payload
    assert "DUMMY_SECRET_MATERIAL_VALUE_SENTINEL" not in payload
    assert "HANDLE_ID_SENTINEL" not in payload
    assert "HANDLE_TOKEN_SENTINEL" not in payload
    assert "HANDLE_SECRET_SENTINEL" not in payload
    assert "HANDLE_VALUE_SENTINEL" not in payload
    assert "KEY_MATERIAL_SENTINEL" not in payload
    assert "CREDENTIAL_METADATA_VALUE_SENTINEL" not in payload
    assert "REAL_CREDENTIAL_VALUE_SENTINEL" not in payload
    assert "OPERATOR_SENTINEL_TEXT_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_HASH_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_FINGERPRINT_SHOULD_NOT_APPEAR" not in payload
    assert "OPERATOR_SENTINEL_LENGTH_SHOULD_NOT_APPEAR" not in payload
    assert "REAL_PRESENCE_CHECKER_SENTINEL" not in payload
    assert "OPERATOR_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in payload
    assert "RAW_OPERATOR_RESULT_VALUE_SHOULD_NOT_APPEAR" not in payload
    assert "CHECKER_RESULT_DETAIL_SHOULD_NOT_APPEAR" not in payload
    assert "ENV_NAME_SHOULD_NOT_APPEAR" not in payload
    assert '{"executionType":"MARKET"' not in payload


def test_new_module_does_not_import_http_private_broker_live_order_once_or_env_access() -> None:
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app.brokers",
        "app.private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "getenv",
        "ENABLE_LIVE_TRADING",
        "GMO_FX_API_KEY",
        "GMO_FX_API_SECRET",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "pbcopy",
    }
    blocked_attrs = {"environ", "getenv"}
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_step6g_internal_wiring.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def _is_blocked_module(module: str, blocked_modules: set[str]) -> bool:
    return any(
        module == blocked or module.startswith(f"{blocked}.")
        for blocked in blocked_modules
    )
