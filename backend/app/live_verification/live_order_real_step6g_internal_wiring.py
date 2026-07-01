"""Step 6G internal wiring dry-run, fake/sanitized only.

This module connects the existing Step 6G PB/EB/AD/RA/TC/ST safe pieces with
sentinel metadata. It does not execute API calls, HTTP POST, an order endpoint,
live_order_once, real signing, or credential access.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
)
from app.live_verification.live_order_real_credential_boundary import (
    LiveOrderRealCredentialBoundaryInput,
    LiveOrderRealCredentialBoundaryResult,
    LiveOrderRealCredentialBoundaryStatus,
    build_live_order_real_credential_boundary,
)
from app.live_verification.live_order_real_credential_handle import (
    LiveOrderRealCredentialHandleInput,
    LiveOrderRealCredentialHandleResult,
    LiveOrderRealCredentialHandleStatus,
    build_live_order_real_credential_handle,
)
from app.live_verification.live_order_real_credential_injection import (
    LiveOrderRealCredentialInjectionInput,
    LiveOrderRealCredentialInjectionResult,
    LiveOrderRealCredentialInjectionStatus,
    build_live_order_real_credential_injection,
)
from app.live_verification.live_order_real_credential_presence_adapter import (
    LiveOrderRealCredentialPresenceAdapterInput,
    LiveOrderRealCredentialPresenceAdapterResult,
    LiveOrderRealCredentialPresenceAdapterStatus,
    build_live_order_real_credential_presence_adapter,
)
from app.live_verification.live_order_real_credential_presence_check import (
    LiveOrderRealCredentialPresenceCheckInput,
    LiveOrderRealCredentialPresenceCheckResult,
    LiveOrderRealCredentialPresenceCheckStatus,
    build_live_order_real_credential_presence_check,
)
from app.live_verification.live_order_real_credential_presence_checker_contract import (
    LiveOrderRealCredentialPresenceCheckerContractInput,
    LiveOrderRealCredentialPresenceCheckerContractResult,
    LiveOrderRealCredentialPresenceCheckerContractStatus,
    build_live_order_real_credential_presence_checker_contract,
)
from app.live_verification.live_order_real_credential_presence_checker_execution_contract import (
    LiveOrderRealCredentialPresenceCheckerExecutionContractInput,
    LiveOrderRealCredentialPresenceCheckerExecutionContractResult,
    LiveOrderRealCredentialPresenceCheckerExecutionContractStatus,
    build_live_order_real_credential_presence_checker_execution_contract,
)
from app.live_verification.live_order_real_credential_presence_checker_execution_implementation import (  # noqa: E501
    LiveOrderRealCredentialPresenceCheckerExecutionImplementationInput,
    LiveOrderRealCredentialPresenceCheckerExecutionImplementationResult,
    LiveOrderRealCredentialPresenceCheckerExecutionImplementationStatus,
    build_live_order_real_credential_presence_checker_execution_implementation,
)
from app.live_verification.live_order_real_credential_presence_checker_implementation import (
    LiveOrderRealCredentialPresenceCheckerImplementationInput,
    LiveOrderRealCredentialPresenceCheckerImplementationResult,
    LiveOrderRealCredentialPresenceCheckerImplementationStatus,
    build_live_order_real_credential_presence_checker_implementation,
)
from app.live_verification.live_order_real_dummy_signing import (
    LiveOrderRealDummySigningInput,
    LiveOrderRealDummySigningResult,
    LiveOrderRealDummySigningStatus,
    build_live_order_real_dummy_signing_check,
)
from app.live_verification.live_order_real_http_transport_interface import (
    LiveOrderRealHttpTransportInterfaceInput,
    LiveOrderRealHttpTransportInterfaceResult,
    LiveOrderRealHttpTransportInterfaceStatus,
    build_live_order_real_http_transport_interface,
)
from app.live_verification.live_order_real_operator_executed_checker_workflow import (
    LiveOrderRealOperatorExecutedCheckerWorkflowInput,
    LiveOrderRealOperatorExecutedCheckerWorkflowResult,
    LiveOrderRealOperatorExecutedCheckerWorkflowStatus,
    build_live_order_real_operator_executed_checker_workflow,
)
from app.live_verification.live_order_real_operator_executed_execution_boundary import (
    LiveOrderRealOperatorExecutedExecutionBoundaryInput,
    LiveOrderRealOperatorExecutedExecutionBoundaryResult,
    LiveOrderRealOperatorExecutedExecutionBoundaryStatus,
    build_live_order_real_operator_executed_execution_boundary,
)
from app.live_verification.live_order_real_operator_execution_result_category_contract import (
    LiveOrderRealOperatorExecutionResultCategory,
    LiveOrderRealOperatorExecutionResultCategoryContractInput,
    LiveOrderRealOperatorExecutionResultCategoryContractResult,
    LiveOrderRealOperatorExecutionResultCategoryContractStatus,
    build_live_order_real_operator_execution_result_category_contract,
)
from app.live_verification.live_order_real_operator_result_handoff_receipt import (
    LiveOrderRealOperatorResultHandoffReceiptInput,
    LiveOrderRealOperatorResultHandoffReceiptResult,
    LiveOrderRealOperatorResultHandoffReceiptStatus,
    build_live_order_real_operator_result_handoff_receipt,
)
from app.live_verification.live_order_real_order_transport_core import (
    LiveOrderRealNoRetryContract,
    LiveOrderRealTransportCoreResult,
    LiveOrderRealTransportCoreStatus,
    LiveOrderRealValidatedOrderIntent,
    build_live_order_real_order_transport_core,
    build_private_order_header_contract_without_exposure,
    make_live_order_real_transport_endpoint_contract,
)
from app.live_verification.live_order_real_private_order_transport import (
    LiveOrderRealPrivateOrderTransportPrerequisites,
    LiveOrderRealPrivateOrderTransportResult,
    LiveOrderRealPrivateOrderTransportStatus,
    build_live_order_real_private_order_transport_contract,
)
from app.live_verification.live_order_real_signing_contract import (
    LiveOrderRealRedactedHeaderContract,
    LiveOrderRealSigningContractResult,
    LiveOrderRealSigningContractStatus,
    LiveOrderRealSigningInputContract,
    build_live_order_real_signing_contract,
)
from app.live_verification.live_order_real_step6g_controlled_adapter import (
    LiveOrderRealStep6GControlledAdapterResult,
    LiveOrderRealStep6GControlledAdapterStatus,
    run_live_order_real_step6g_controlled_adapter_with_fake_transport,
)
from app.live_verification.live_order_real_step6g_post_route_bridge import (
    LiveOrderRealStep6GApprovalSnapshot,
    LiveOrderRealStep6GAttemptState,
    LiveOrderRealStep6GOrderIntentSnapshot,
    LiveOrderRealStep6GPostRouteBridgeResult,
    LiveOrderRealStep6GPostRouteBridgeStatus,
    LiveOrderRealStep6GPreflightSnapshot,
    LiveOrderRealStep6GRouteContractSnapshot,
    build_live_order_real_step6g_post_route_bridge,
)
from app.live_verification.live_order_real_step6g_real_adapter import (
    LiveOrderRealStep6GRealAdapterResult,
    LiveOrderRealStep6GRealAdapterStatus,
    run_live_order_real_step6g_real_adapter_with_stub_transport,
)
from app.live_verification.live_order_real_step6g_runtime_bridge import (
    LiveOrderRealStep6GRuntimeBridgeResult,
    LiveOrderRealStep6GRuntimeBridgeStatus,
    run_live_order_real_step6g_fake_runtime_bridge,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

INTERNAL_WIRING_RECOMMENDED_NEXT_STEP = (
    "future_dummy_signing_or_transport_interface_step_no_api_no_post"
)
INTERNAL_WIRING_FINGERPRINT_SENTINEL = "DUMMY_STEP6G_FINGERPRINT"
INTERNAL_WIRING_SHA256_PREFIX_SENTINEL = "dummy6gsha"


class LiveOrderRealStep6GInternalWiringStatus(str, Enum):
    STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST = (
        "STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_ORDER_INTENT = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_ORDER_INTENT"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_APPROVAL = "BLOCKED_STEP6G_INTERNAL_WIRING_APPROVAL"
    BLOCKED_STEP6G_INTERNAL_WIRING_PREFLIGHT = "BLOCKED_STEP6G_INTERNAL_WIRING_PREFLIGHT"
    BLOCKED_STEP6G_INTERNAL_WIRING_ATTEMPT_STATE = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_ATTEMPT_STATE"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_RUNTIME_BRIDGE = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_RUNTIME_BRIDGE"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_CONTROLLED_ADAPTER = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_CONTROLLED_ADAPTER"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_REAL_ADAPTER = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_REAL_ADAPTER"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_TRANSPORT_CORE = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_TRANSPORT_CORE"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_PRIVATE_TRANSPORT = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_PRIVATE_TRANSPORT"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_STEP4_SPOOFING = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_STEP4_SPOOFING"
    )
    BLOCKED_STEP6G_INTERNAL_WIRING_UNSUPPORTED = (
        "BLOCKED_STEP6G_INTERNAL_WIRING_UNSUPPORTED"
    )


InternalWiringStatus = LiveOrderRealStep6GInternalWiringStatus


@dataclass(frozen=True)
class LiveOrderRealStep6GInternalWiringInput:
    symbol: str = SUPPORTED_SYMBOL
    side: str = "BUY"
    size: int = LIVE_ORDER_CANDIDATE_SIZE
    executionType: str = LIVE_ORDER_CANDIDATE_EXECUTION_TYPE
    codex_inferred: bool = False
    final_confirmation_exact_match: bool = True
    final_confirmation_reused: bool = False
    approval_artifact_reestablished: bool = True
    approval_validation_passed: bool = True
    approval_exact_match_ready: bool = True
    approval_fingerprint: str = INTERNAL_WIRING_FINGERPRINT_SENTINEL
    sha256_prefix: str = INTERNAL_WIRING_SHA256_PREFIX_SENTINEL
    approval_command_full_text_present: bool = False
    approval_command_displayed: bool = False
    approval_command_saved: bool = False
    final_confirmation_preflight_passed: bool = True
    post_immediate_preflight_passed: bool = True
    market_session_state: str = "OPEN"
    market_window_allowed: bool = True
    broker_maintenance_active: bool = False
    holiday_or_special_close: bool = False
    market_hours_unknown: bool = False
    open_positions_count: int = 0
    active_orders_count: int = 0
    ticker_symbol: str = SUPPORTED_SYMBOL
    ticker_spread_jpy: float = 0.005
    ticker_age_seconds: float = 0.5
    ticker_check_passed: bool = True
    permission_scope_check_passed: bool = True
    ip_account_binding_check_passed: bool = True
    previous_result_unknown_check_passed: bool = True
    post_attempt_limit: int = 1
    post_attempt_count_before: int = 0
    retry_allowed: bool = False
    loop_allowed: bool = False
    add_order_allowed: bool = False
    change_order_allowed: bool = False
    cancel_order_allowed: bool = False
    close_order_allowed: bool = False
    pb_bridge_ready: bool = True
    eb_runtime_ready: bool = True
    ad_controlled_adapter_ready: bool = True
    ra_real_adapter_ready: bool = True
    tc_transport_core_ready: bool = True
    st_signing_contract_ready: bool = True
    st_private_transport_ready: bool = True
    dummy_signing_ready: bool = True
    dummy_signature_check_passed: bool = True
    dummy_signature_value_present: bool = False
    dummy_signature_value_displayed: bool = False
    dummy_signature_value_saved: bool = False
    http_transport_interface_ready: bool = True
    http_transport_interface_mode: str = "INTERFACE_ONLY"
    http_client_present: bool = False
    can_execute_http_post: bool = False
    can_call_order_endpoint: bool = False
    can_call_live_order_once: bool = False
    credential_boundary_ready: bool = True
    credential_boundary_mode: str = "BOUNDARY_ONLY"
    credential_values_provided: bool = False
    credential_values_loaded: bool = False
    credential_presence_checked_against_environment: bool = False
    env_access_requested: bool = False
    credential_metadata_exposed: bool = False
    credential_handle_ready: bool = True
    credential_handle_mode: str = "HANDLE_CONTRACT_ONLY"
    handle_requested: bool = True
    handle_created: bool = False
    handle_contains_value: bool = False
    handle_contains_identifier: bool = False
    handle_metadata_exposed: bool = False
    credential_injection_ready: bool = True
    credential_injection_mode: str = "INJECTION_SKELETON_ONLY"
    injection_requested: bool = True
    injection_performed: bool = False
    real_credential_values_available: bool = False
    real_credential_values_injected: bool = False
    credential_injection_metadata_available: bool = False
    credential_presence_check_ready: bool = True
    presence_check_mode: str = "OPERATOR_PROVIDED_SENTINEL_ONLY"
    operator_assertion_provided: bool = True
    operator_assertion_is_boolean_only: bool = True
    operator_sentinel_received: bool = True
    operator_sentinel_fresh: bool = True
    operator_sentinel_reused: bool = False
    operator_sentinel_stale: bool = False
    operator_sentinel_previous_turn: bool = False
    sentinel_value_present: bool = False
    sentinel_value_displayed: bool = False
    sentinel_value_saved: bool = False
    sentinel_hash_available: bool = False
    sentinel_fingerprint_available: bool = False
    sentinel_length_available: bool = False
    presence_result_broadly_propagated: bool = False
    presence_result_saved: bool = False
    credential_presence_adapter_ready: bool = True
    presence_adapter_mode: str = "PRESENCE_ADAPTER_SKELETON_ONLY"
    operator_provided_presence_result: bool = True
    operator_presence_result_is_boolean_only: bool = True
    operator_presence_result_fresh: bool = True
    operator_presence_result_reused: bool = False
    operator_presence_result_stale: bool = False
    operator_presence_result_previous_turn: bool = False
    presence_result_adapted: bool = True
    presence_result_displayed: bool = False
    actual_environment_presence_check_performed: bool = False
    real_checker_attached: bool = False
    real_checker_executed: bool = False
    credential_presence_checker_contract_ready: bool = True
    checker_contract_mode: str = "CHECKER_CONTRACT_ONLY"
    checker_contract_requested: bool = True
    checker_contract_ready_requested: bool = True
    real_checker_implementation_present: bool = False
    env_access_required: bool = True
    env_access_allowed: bool = False
    credential_values_available: bool = False
    credential_values_read: bool = False
    credential_values_displayed: bool = False
    credential_values_saved: bool = False
    credential_metadata_available: bool = False
    credential_metadata_displayed: bool = False
    credential_metadata_saved: bool = False
    checker_result_available: bool = False
    checker_result_is_boolean_only: bool = True
    checker_result_saved: bool = False
    checker_result_displayed: bool = False
    checker_result_broadly_propagated: bool = False
    checker_result_unknown: bool = False
    checker_result_failed: bool = False
    operator_checker_workflow_ready: bool = True
    operator_checker_workflow_mode: str = (
        "OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY"
    )
    operator_workflow_declared: bool = True
    operator_execution_required: bool = True
    operator_execution_performed_outside_codex: bool = True
    codex_execution_performed: bool = False
    codex_env_access_requested: bool = False
    actual_environment_presence_check_performed_by_codex: bool = False
    operator_result_handoff_declared: bool = True
    operator_result_handoff_safe: bool = True
    operator_result_category_only: bool = True
    operator_result_provided: bool = True
    operator_result_is_boolean_only: bool = True
    operator_result_raw_value_present: bool = False
    operator_result_raw_value_saved: bool = False
    operator_result_raw_value_displayed: bool = False
    operator_result_fresh: bool = True
    operator_result_stale: bool = False
    operator_result_reused: bool = False
    operator_result_previous_turn: bool = False
    operator_result_timeout: bool = False
    operator_result_unknown: bool = False
    operator_result_failed: bool = False
    operator_result_unavailable: bool = False
    operator_result_saved: bool = False
    operator_result_displayed: bool = False
    operator_result_broadly_propagated: bool = False
    operator_result_detail_present: bool = False
    env_variable_names_present: bool = False
    checker_result_detail_present: bool = False
    checker_implementation_skeleton_ready: bool = True
    checker_implementation_mode: str = "CHECKER_IMPLEMENTATION_SKELETON_ONLY"
    checker_execution_contract_ready: bool = True
    checker_execution_contract_mode: str = "CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY"
    checker_execution_implementation_skeleton_ready: bool = True
    checker_execution_implementation_mode: str = (
        "CHECKER_EXECUTION_IMPLEMENTATION_SKELETON_ONLY"
    )
    operator_executed_execution_boundary_ready: bool = True
    operator_execution_boundary_mode: str = (
        "OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY"
    )
    operator_execution_boundary_declared: bool = True
    operator_execution_must_be_outside_codex: bool = True
    codex_execution_forbidden: bool = True
    actual_execution_performed: bool = False
    operator_execution_performed: bool = False
    operator_execution_result_category_contract_ready: bool = True
    operator_execution_result_category_contract_mode: str = (
        "OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ONLY"
    )
    category_contract_declared: bool = True
    allowed_category_set_declared: bool = True
    operator_result_category: str = "NOT_PROVIDED"
    operator_result_category_is_safe_label: bool = True
    operator_result_category_is_allowed: bool = True
    operator_result_handoff_receipt_ready: bool = True
    operator_result_handoff_receipt_mode: str = (
        "OPERATOR_RESULT_HANDOFF_RECEIPT_SKELETON_ONLY"
    )
    receipt_contract_declared: bool = True
    receipt_boundary_declared: bool = True
    receipt_one_time_required: bool = True
    receipt_fresh_required: bool = True
    receipt_non_reuse_required: bool = True
    receipt_non_raw_required: bool = True
    receipt_non_detail_required: bool = True
    receipt_provided: bool = False
    receipt_category_confirmed: bool = False
    receipt_current_turn: bool = True
    receipt_fresh: bool = True
    receipt_stale: bool = False
    receipt_reused: bool = False
    receipt_previous_turn: bool = False
    receipt_expired: bool = False
    receipt_timeout: bool = False
    receipt_unknown: bool = False
    receipt_failed: bool = False
    receipt_unavailable: bool = False
    receipt_raw_value_present: bool = False
    receipt_detail_present: bool = False
    receipt_id_present: bool = False
    receipt_token_present: bool = False
    receipt_nonce_present: bool = False
    receipt_hash_present: bool = False
    receipt_fingerprint_present: bool = False
    receipt_length_present: bool = False
    receipt_saved: bool = False
    receipt_displayed: bool = False
    receipt_broadly_propagated: bool = False
    execution_contract_declared: bool = True
    execution_inputs_declared: bool = True
    execution_outputs_declared: bool = True
    execution_stop_conditions_declared: bool = True
    execution_implementation_declared: bool = True
    execution_interface_declared: bool = True
    implementation_interface_declared: bool = True
    implementation_lifecycle_declared: bool = True
    execution_lifecycle_declared: bool = True
    execution_result_mapping_declared: bool = True
    execution_deferred_to_future_step: bool = True
    execution_performed: bool = False
    execution_performed_by_codex: bool = False
    execution_performed_by_operator: bool = False
    credential_read_performed: bool = False
    env_access_capability_present: bool = False
    credential_read_capability_present: bool = False
    checker_result_unavailable: bool = False
    checker_result_stale: bool = False
    checker_result_timeout: bool = False
    operator_workflow_supported: bool = True
    operator_workflow_preserved: bool = True
    signature_value_generated: bool = False
    header_values_present: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    allowed_for_live: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    raw_request_displayed: bool = False
    raw_request_saved: bool = False
    raw_response_displayed: bool = False
    raw_response_saved: bool = False
    headers_displayed: bool = False
    headers_saved: bool = False
    signature_displayed: bool = False
    signature_saved: bool = False
    credentials_displayed: bool = False
    credentials_saved: bool = False
    real_ids_displayed: bool = False
    real_ids_saved: bool = False
    step4_spoofing: bool = False
    ledger_changed: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("symbol", self.symbol)
        _require_non_empty("side", self.side)
        _require_non_empty("executionType", self.executionType)
        _require_non_empty("market_session_state", self.market_session_state)
        _require_non_empty("ticker_symbol", self.ticker_symbol)
        _require_non_empty("http_transport_interface_mode", self.http_transport_interface_mode)
        _require_non_empty("credential_boundary_mode", self.credential_boundary_mode)
        _require_non_empty("credential_handle_mode", self.credential_handle_mode)
        _require_non_empty("credential_injection_mode", self.credential_injection_mode)
        _require_non_empty("presence_check_mode", self.presence_check_mode)
        _require_non_empty("presence_adapter_mode", self.presence_adapter_mode)
        _require_non_empty("checker_contract_mode", self.checker_contract_mode)
        _require_non_empty(
            "operator_checker_workflow_mode",
            self.operator_checker_workflow_mode,
        )
        _require_non_empty(
            "checker_execution_contract_mode",
            self.checker_execution_contract_mode,
        )
        _require_non_empty(
            "checker_execution_implementation_mode",
            self.checker_execution_implementation_mode,
        )
        _require_non_empty(
            "operator_execution_boundary_mode",
            self.operator_execution_boundary_mode,
        )
        _require_non_empty(
            "operator_execution_result_category_contract_mode",
            self.operator_execution_result_category_contract_mode,
        )
        _require_non_empty(
            "operator_result_handoff_receipt_mode",
            self.operator_result_handoff_receipt_mode,
        )
        _require_non_empty("operator_result_category", self.operator_result_category)
        _validate_non_negative_int("size", self.size)
        _validate_non_negative_int("open_positions_count", self.open_positions_count)
        _validate_non_negative_int("active_orders_count", self.active_orders_count)
        _validate_non_negative_int("post_attempt_limit", self.post_attempt_limit)
        _validate_non_negative_int(
            "post_attempt_count_before",
            self.post_attempt_count_before,
        )
        _validate_bool_fields(
            self,
            (
                "codex_inferred",
                "final_confirmation_exact_match",
                "final_confirmation_reused",
                "approval_artifact_reestablished",
                "approval_validation_passed",
                "approval_exact_match_ready",
                "approval_command_full_text_present",
                "approval_command_displayed",
                "approval_command_saved",
                "final_confirmation_preflight_passed",
                "post_immediate_preflight_passed",
                "market_window_allowed",
                "broker_maintenance_active",
                "holiday_or_special_close",
                "market_hours_unknown",
                "ticker_check_passed",
                "permission_scope_check_passed",
                "ip_account_binding_check_passed",
                "previous_result_unknown_check_passed",
                "retry_allowed",
                "loop_allowed",
                "add_order_allowed",
                "change_order_allowed",
                "cancel_order_allowed",
                "close_order_allowed",
                "pb_bridge_ready",
                "eb_runtime_ready",
                "ad_controlled_adapter_ready",
                "ra_real_adapter_ready",
                "tc_transport_core_ready",
                "st_signing_contract_ready",
                "st_private_transport_ready",
                "dummy_signing_ready",
                "dummy_signature_check_passed",
                "dummy_signature_value_present",
                "dummy_signature_value_displayed",
                "dummy_signature_value_saved",
                "http_transport_interface_ready",
                "http_client_present",
                "can_execute_http_post",
                "can_call_order_endpoint",
                "can_call_live_order_once",
                "credential_boundary_ready",
                "credential_values_provided",
                "credential_values_loaded",
                "credential_presence_checked_against_environment",
                "env_access_requested",
                "credential_metadata_exposed",
                "credential_handle_ready",
                "handle_requested",
                "handle_created",
                "handle_contains_value",
                "handle_contains_identifier",
                "handle_metadata_exposed",
                "credential_injection_ready",
                "injection_requested",
                "injection_performed",
                "real_credential_values_available",
                "real_credential_values_injected",
                "credential_injection_metadata_available",
                "credential_presence_check_ready",
                "operator_assertion_provided",
                "operator_assertion_is_boolean_only",
                "operator_sentinel_received",
                "operator_sentinel_fresh",
                "operator_sentinel_reused",
                "operator_sentinel_stale",
                "operator_sentinel_previous_turn",
                "sentinel_value_present",
                "sentinel_value_displayed",
                "sentinel_value_saved",
                "sentinel_hash_available",
                "sentinel_fingerprint_available",
                "sentinel_length_available",
                "presence_result_broadly_propagated",
                "presence_result_saved",
                "credential_presence_adapter_ready",
                "operator_provided_presence_result",
                "operator_presence_result_is_boolean_only",
                "operator_presence_result_fresh",
                "operator_presence_result_reused",
                "operator_presence_result_stale",
                "operator_presence_result_previous_turn",
                "presence_result_adapted",
                "presence_result_displayed",
                "actual_environment_presence_check_performed",
                "real_checker_attached",
                "real_checker_executed",
                "credential_presence_checker_contract_ready",
                "checker_contract_requested",
                "checker_contract_ready_requested",
                "real_checker_implementation_present",
                "env_access_required",
                "env_access_allowed",
                "credential_values_available",
                "credential_values_read",
                "credential_values_displayed",
                "credential_values_saved",
                "credential_metadata_available",
                "credential_metadata_displayed",
                "credential_metadata_saved",
                "checker_result_available",
                "checker_result_is_boolean_only",
                "checker_result_saved",
                "checker_result_displayed",
                "checker_result_broadly_propagated",
                "checker_result_unknown",
                "checker_result_failed",
                "operator_checker_workflow_ready",
                "operator_workflow_declared",
                "operator_execution_required",
                "operator_execution_performed_outside_codex",
                "codex_execution_performed",
                "codex_env_access_requested",
                "actual_environment_presence_check_performed_by_codex",
                "operator_result_handoff_declared",
                "operator_result_handoff_safe",
                "operator_result_category_only",
                "operator_result_provided",
                "operator_result_is_boolean_only",
                "operator_result_raw_value_present",
                "operator_result_raw_value_saved",
                "operator_result_raw_value_displayed",
                "operator_result_fresh",
                "operator_result_stale",
                "operator_result_reused",
                "operator_result_previous_turn",
                "operator_result_timeout",
                "operator_result_unknown",
                "operator_result_failed",
                "operator_result_unavailable",
                "operator_result_saved",
                "operator_result_displayed",
                "operator_result_broadly_propagated",
                "operator_result_detail_present",
                "env_variable_names_present",
                "checker_result_detail_present",
                "checker_implementation_skeleton_ready",
                "checker_execution_contract_ready",
                "checker_execution_implementation_skeleton_ready",
                "operator_executed_execution_boundary_ready",
                "operator_execution_boundary_declared",
                "operator_execution_must_be_outside_codex",
                "codex_execution_forbidden",
                "actual_execution_performed",
                "operator_execution_performed",
                "operator_execution_result_category_contract_ready",
                "category_contract_declared",
                "allowed_category_set_declared",
                "operator_result_category_is_safe_label",
                "operator_result_category_is_allowed",
                "operator_result_handoff_receipt_ready",
                "receipt_contract_declared",
                "receipt_boundary_declared",
                "receipt_one_time_required",
                "receipt_fresh_required",
                "receipt_non_reuse_required",
                "receipt_non_raw_required",
                "receipt_non_detail_required",
                "receipt_provided",
                "receipt_category_confirmed",
                "receipt_current_turn",
                "receipt_fresh",
                "receipt_stale",
                "receipt_reused",
                "receipt_previous_turn",
                "receipt_expired",
                "receipt_timeout",
                "receipt_unknown",
                "receipt_failed",
                "receipt_unavailable",
                "receipt_raw_value_present",
                "receipt_detail_present",
                "receipt_id_present",
                "receipt_token_present",
                "receipt_nonce_present",
                "receipt_hash_present",
                "receipt_fingerprint_present",
                "receipt_length_present",
                "receipt_saved",
                "receipt_displayed",
                "receipt_broadly_propagated",
                "execution_contract_declared",
                "execution_inputs_declared",
                "execution_outputs_declared",
                "execution_stop_conditions_declared",
                "execution_implementation_declared",
                "execution_interface_declared",
                "signature_value_generated",
                "header_values_present",
                "execution_lifecycle_declared",
                "execution_result_mapping_declared",
                "execution_performed_by_codex",
                "execution_performed_by_operator",
                "credential_read_performed",
                "checker_result_timeout",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "allowed_for_live",
                "post_allowed_this_step",
                "post_executed",
                "raw_request_displayed",
                "raw_request_saved",
                "raw_response_displayed",
                "raw_response_saved",
                "headers_displayed",
                "headers_saved",
                "signature_displayed",
                "signature_saved",
                "credentials_displayed",
                "credentials_saved",
                "real_ids_displayed",
                "real_ids_saved",
                "step4_spoofing",
                "ledger_changed",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealStep6GInternalWiringCheckResult:
    name: str
    passed: bool
    sanitized_value: str
    expected: str

    def __post_init__(self) -> None:
        _require_non_empty("name", self.name)
        if type(self.passed) is not bool:
            raise LiveVerificationValidationError("passed must be bool")
        _require_non_empty("sanitized_value", self.sanitized_value)
        _require_non_empty("expected", self.expected)


@dataclass(frozen=True)
class LiveOrderRealStep6GInternalWiringSnapshot:
    input_snapshot: LiveOrderRealStep6GInternalWiringInput
    pb_result: LiveOrderRealStep6GPostRouteBridgeResult
    eb_result: LiveOrderRealStep6GRuntimeBridgeResult
    ad_result: LiveOrderRealStep6GControlledAdapterResult
    ra_result: LiveOrderRealStep6GRealAdapterResult
    tc_result: LiveOrderRealTransportCoreResult
    st_signing_result: LiveOrderRealSigningContractResult
    st_private_transport_result: LiveOrderRealPrivateOrderTransportResult
    dummy_signing_result: LiveOrderRealDummySigningResult
    http_transport_interface_result: LiveOrderRealHttpTransportInterfaceResult
    credential_boundary_result: LiveOrderRealCredentialBoundaryResult
    credential_handle_result: LiveOrderRealCredentialHandleResult
    credential_injection_result: LiveOrderRealCredentialInjectionResult
    credential_presence_check_result: LiveOrderRealCredentialPresenceCheckResult
    credential_presence_adapter_result: LiveOrderRealCredentialPresenceAdapterResult
    credential_presence_checker_contract_result: (
        LiveOrderRealCredentialPresenceCheckerContractResult
    )
    operator_checker_workflow_result: LiveOrderRealOperatorExecutedCheckerWorkflowResult
    credential_presence_checker_implementation_result: (
        LiveOrderRealCredentialPresenceCheckerImplementationResult
    )
    credential_presence_checker_execution_contract_result: (
        LiveOrderRealCredentialPresenceCheckerExecutionContractResult
    )
    credential_presence_checker_execution_implementation_result: (
        LiveOrderRealCredentialPresenceCheckerExecutionImplementationResult
    )
    operator_executed_execution_boundary_result: (
        LiveOrderRealOperatorExecutedExecutionBoundaryResult
    )
    operator_execution_result_category_contract_result: (
        LiveOrderRealOperatorExecutionResultCategoryContractResult
    )
    operator_result_handoff_receipt_result: (
        LiveOrderRealOperatorResultHandoffReceiptResult
    )


@dataclass(frozen=True)
class LiveOrderRealStep6GInternalWiringResult:
    status: LiveOrderRealStep6GInternalWiringStatus
    internal_wiring_ready: bool
    pb_ready: bool
    eb_ready: bool
    ad_ready: bool
    ra_ready: bool
    tc_ready: bool
    st_signing_ready: bool
    st_private_transport_ready: bool
    dummy_signing_ready: bool
    dummy_signature_check_passed: bool
    dummy_signature_value_present: bool
    dummy_signature_value_displayed: bool
    dummy_signature_value_saved: bool
    http_transport_interface_ready: bool
    http_transport_interface_mode: str
    http_client_present: bool
    can_execute_http_post: bool
    can_call_order_endpoint: bool
    can_call_live_order_once: bool
    credential_boundary_ready: bool
    credential_boundary_mode: str
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    credential_values_provided: bool
    credential_values_loaded: bool
    credential_presence_checked_against_environment: bool
    env_access_requested: bool
    credential_metadata_exposed: bool
    credential_handle_ready: bool
    credential_handle_mode: str
    handle_requested: bool
    handle_created: bool
    handle_contains_value: bool
    handle_contains_identifier: bool
    handle_metadata_exposed: bool
    credential_injection_ready: bool
    credential_injection_mode: str
    injection_requested: bool
    injection_performed: bool
    real_credential_values_available: bool
    real_credential_values_injected: bool
    credential_injection_metadata_available: bool
    credential_presence_check_ready: bool
    presence_check_mode: str
    operator_assertion_provided: bool
    operator_assertion_is_boolean_only: bool
    operator_sentinel_received: bool
    operator_sentinel_fresh: bool
    operator_sentinel_reused: bool
    operator_sentinel_stale: bool
    operator_sentinel_previous_turn: bool
    sentinel_value_present: bool
    sentinel_value_displayed: bool
    sentinel_value_saved: bool
    sentinel_hash_available: bool
    sentinel_fingerprint_available: bool
    sentinel_length_available: bool
    presence_result_broadly_propagated: bool
    presence_result_saved: bool
    credential_presence_adapter_ready: bool
    presence_adapter_mode: str
    operator_provided_presence_result: bool
    operator_presence_result_is_boolean_only: bool
    operator_presence_result_fresh: bool
    operator_presence_result_reused: bool
    operator_presence_result_stale: bool
    operator_presence_result_previous_turn: bool
    presence_result_adapted: bool
    presence_result_displayed: bool
    actual_environment_presence_check_performed: bool
    real_checker_attached: bool
    real_checker_executed: bool
    credential_presence_checker_contract_ready: bool
    checker_contract_mode: str
    checker_contract_requested: bool
    checker_contract_ready_requested: bool
    real_checker_implementation_present: bool
    env_access_required: bool
    env_access_allowed: bool
    credential_values_available: bool
    credential_values_read: bool
    credential_values_displayed: bool
    credential_values_saved: bool
    credential_metadata_available: bool
    credential_metadata_displayed: bool
    credential_metadata_saved: bool
    checker_result_available: bool
    checker_result_is_boolean_only: bool
    checker_result_saved: bool
    checker_result_displayed: bool
    checker_result_broadly_propagated: bool
    checker_result_unknown: bool
    checker_result_failed: bool
    operator_checker_workflow_ready: bool
    operator_checker_workflow_mode: str
    operator_workflow_declared: bool
    operator_execution_required: bool
    operator_execution_performed_outside_codex: bool
    codex_execution_performed: bool
    codex_env_access_requested: bool
    actual_environment_presence_check_performed_by_codex: bool
    operator_result_handoff_declared: bool
    operator_result_handoff_safe: bool
    operator_result_category_only: bool
    operator_result_provided: bool
    operator_result_is_boolean_only: bool
    operator_result_raw_value_present: bool
    operator_result_raw_value_saved: bool
    operator_result_raw_value_displayed: bool
    operator_result_fresh: bool
    operator_result_stale: bool
    operator_result_reused: bool
    operator_result_previous_turn: bool
    operator_result_timeout: bool
    operator_result_unknown: bool
    operator_result_failed: bool
    operator_result_unavailable: bool
    operator_result_saved: bool
    operator_result_displayed: bool
    operator_result_broadly_propagated: bool
    operator_result_detail_present: bool
    env_variable_names_present: bool
    checker_result_detail_present: bool
    checker_implementation_skeleton_ready: bool
    checker_implementation_mode: str
    checker_execution_contract_ready: bool
    checker_execution_contract_mode: str
    checker_execution_implementation_skeleton_ready: bool
    checker_execution_implementation_mode: str
    operator_executed_execution_boundary_ready: bool
    operator_execution_boundary_mode: str
    operator_execution_boundary_declared: bool
    operator_execution_must_be_outside_codex: bool
    codex_execution_forbidden: bool
    operator_execution_performed: bool
    operator_execution_result_category_contract_ready: bool
    operator_execution_result_category_contract_mode: str
    category_contract_declared: bool
    allowed_category_set_declared: bool
    operator_result_category: str
    operator_result_category_is_safe_label: bool
    operator_result_category_is_allowed: bool
    operator_result_ready_confirmed: bool
    operator_result_blocked: bool
    operator_result_handoff_receipt_ready: bool
    operator_result_handoff_receipt_mode: str
    receipt_contract_declared: bool
    receipt_boundary_declared: bool
    receipt_one_time_required: bool
    receipt_fresh_required: bool
    receipt_non_reuse_required: bool
    receipt_non_raw_required: bool
    receipt_non_detail_required: bool
    receipt_provided: bool
    receipt_category_confirmed: bool
    receipt_current_turn: bool
    receipt_fresh: bool
    receipt_stale: bool
    receipt_reused: bool
    receipt_previous_turn: bool
    receipt_expired: bool
    receipt_timeout: bool
    receipt_unknown: bool
    receipt_failed: bool
    receipt_unavailable: bool
    receipt_raw_value_present: bool
    receipt_detail_present: bool
    receipt_id_present: bool
    receipt_token_present: bool
    receipt_nonce_present: bool
    receipt_hash_present: bool
    receipt_fingerprint_present: bool
    receipt_length_present: bool
    execution_contract_declared: bool
    execution_inputs_declared: bool
    execution_outputs_declared: bool
    execution_stop_conditions_declared: bool
    execution_implementation_declared: bool
    execution_interface_declared: bool
    implementation_interface_declared: bool
    implementation_lifecycle_declared: bool
    execution_lifecycle_declared: bool
    execution_result_mapping_declared: bool
    execution_deferred_to_future_step: bool
    execution_performed: bool
    execution_performed_by_codex: bool
    execution_performed_by_operator: bool
    credential_read_performed: bool
    env_access_capability_present: bool
    credential_read_capability_present: bool
    checker_result_unavailable: bool
    checker_result_stale: bool
    checker_result_timeout: bool
    operator_workflow_supported: bool
    operator_workflow_preserved: bool
    signature_value_generated: bool
    header_values_present: bool
    allowed_for_live: bool
    post_allowed_this_step: bool
    post_executed: bool
    retry_allowed: bool
    loop_allowed: bool
    check_results: tuple[LiveOrderRealStep6GInternalWiringCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealStep6GInternalWiringStatus):
            raise LiveVerificationValidationError("status must be internal wiring status")
        _require_non_empty("http_transport_interface_mode", self.http_transport_interface_mode)
        _require_non_empty("credential_boundary_mode", self.credential_boundary_mode)
        _require_non_empty("credential_handle_mode", self.credential_handle_mode)
        _require_non_empty("credential_injection_mode", self.credential_injection_mode)
        _require_non_empty("presence_check_mode", self.presence_check_mode)
        _require_non_empty("presence_adapter_mode", self.presence_adapter_mode)
        _require_non_empty("checker_contract_mode", self.checker_contract_mode)
        _require_non_empty(
            "operator_checker_workflow_mode",
            self.operator_checker_workflow_mode,
        )
        _require_non_empty("checker_implementation_mode", self.checker_implementation_mode)
        _require_non_empty(
            "checker_execution_contract_mode",
            self.checker_execution_contract_mode,
        )
        _require_non_empty(
            "operator_execution_boundary_mode",
            self.operator_execution_boundary_mode,
        )
        _require_non_empty(
            "operator_execution_result_category_contract_mode",
            self.operator_execution_result_category_contract_mode,
        )
        _require_non_empty(
            "operator_result_handoff_receipt_mode",
            self.operator_result_handoff_receipt_mode,
        )
        _require_non_empty("operator_result_category", self.operator_result_category)
        _validate_bool_fields(
            self,
            (
                "internal_wiring_ready",
                "pb_ready",
                "eb_ready",
                "ad_ready",
                "ra_ready",
                "tc_ready",
                "st_signing_ready",
                "st_private_transport_ready",
                "dummy_signing_ready",
                "dummy_signature_check_passed",
                "dummy_signature_value_present",
                "dummy_signature_value_displayed",
                "dummy_signature_value_saved",
                "http_transport_interface_ready",
                "http_client_present",
                "can_execute_http_post",
                "can_call_order_endpoint",
                "can_call_live_order_once",
                "credential_boundary_ready",
                "http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "credential_values_provided",
                "credential_values_loaded",
                "credential_presence_checked_against_environment",
                "env_access_requested",
                "credential_metadata_exposed",
                "credential_handle_ready",
                "handle_requested",
                "handle_created",
                "handle_contains_value",
                "handle_contains_identifier",
                "handle_metadata_exposed",
                "credential_injection_ready",
                "injection_requested",
                "injection_performed",
                "real_credential_values_available",
                "real_credential_values_injected",
                "credential_injection_metadata_available",
                "credential_presence_check_ready",
                "operator_assertion_provided",
                "operator_assertion_is_boolean_only",
                "operator_sentinel_received",
                "operator_sentinel_fresh",
                "operator_sentinel_reused",
                "operator_sentinel_stale",
                "operator_sentinel_previous_turn",
                "sentinel_value_present",
                "sentinel_value_displayed",
                "sentinel_value_saved",
                "sentinel_hash_available",
                "sentinel_fingerprint_available",
                "sentinel_length_available",
                "presence_result_broadly_propagated",
                "presence_result_saved",
                "credential_presence_adapter_ready",
                "operator_provided_presence_result",
                "operator_presence_result_is_boolean_only",
                "operator_presence_result_fresh",
                "operator_presence_result_reused",
                "operator_presence_result_stale",
                "operator_presence_result_previous_turn",
                "presence_result_adapted",
                "presence_result_displayed",
                "actual_environment_presence_check_performed",
                "real_checker_attached",
                "real_checker_executed",
                "credential_presence_checker_contract_ready",
                "checker_contract_requested",
                "checker_contract_ready_requested",
                "real_checker_implementation_present",
                "env_access_required",
                "env_access_allowed",
                "credential_values_available",
                "credential_values_read",
                "credential_values_displayed",
                "credential_values_saved",
                "credential_metadata_available",
                "credential_metadata_displayed",
                "credential_metadata_saved",
                "checker_result_available",
                "checker_result_is_boolean_only",
                "checker_result_saved",
                "checker_result_displayed",
                "checker_result_broadly_propagated",
                "checker_result_unknown",
                "checker_result_failed",
                "operator_checker_workflow_ready",
                "operator_workflow_declared",
                "operator_execution_required",
                "operator_execution_performed_outside_codex",
                "codex_execution_performed",
                "codex_env_access_requested",
                "actual_environment_presence_check_performed_by_codex",
                "operator_result_handoff_declared",
                "operator_result_handoff_safe",
                "operator_result_category_only",
                "operator_result_provided",
                "operator_result_is_boolean_only",
                "operator_result_raw_value_present",
                "operator_result_raw_value_saved",
                "operator_result_raw_value_displayed",
                "operator_result_fresh",
                "operator_result_stale",
                "operator_result_reused",
                "operator_result_previous_turn",
                "operator_result_timeout",
                "operator_result_unknown",
                "operator_result_failed",
                "operator_result_unavailable",
                "operator_result_saved",
                "operator_result_displayed",
                "operator_result_broadly_propagated",
                "operator_result_detail_present",
                "env_variable_names_present",
                "checker_result_detail_present",
                "checker_implementation_skeleton_ready",
                "checker_execution_contract_ready",
                "checker_execution_implementation_skeleton_ready",
                "operator_executed_execution_boundary_ready",
                "operator_execution_boundary_declared",
                "operator_execution_must_be_outside_codex",
                "codex_execution_forbidden",
                "operator_execution_performed",
                "operator_execution_result_category_contract_ready",
                "category_contract_declared",
                "allowed_category_set_declared",
                "operator_result_category_is_safe_label",
                "operator_result_category_is_allowed",
                "operator_result_ready_confirmed",
                "operator_result_blocked",
                "operator_result_handoff_receipt_ready",
                "receipt_contract_declared",
                "receipt_boundary_declared",
                "receipt_one_time_required",
                "receipt_fresh_required",
                "receipt_non_reuse_required",
                "receipt_non_raw_required",
                "receipt_non_detail_required",
                "receipt_provided",
                "receipt_category_confirmed",
                "receipt_current_turn",
                "receipt_fresh",
                "receipt_stale",
                "receipt_reused",
                "receipt_previous_turn",
                "receipt_expired",
                "receipt_timeout",
                "receipt_unknown",
                "receipt_failed",
                "receipt_unavailable",
                "receipt_raw_value_present",
                "receipt_detail_present",
                "receipt_id_present",
                "receipt_token_present",
                "receipt_nonce_present",
                "receipt_hash_present",
                "receipt_fingerprint_present",
                "receipt_length_present",
                "execution_contract_declared",
                "execution_inputs_declared",
                "execution_outputs_declared",
                "execution_stop_conditions_declared",
                "execution_implementation_declared",
                "execution_interface_declared",
                "implementation_interface_declared",
                "implementation_lifecycle_declared",
                "execution_lifecycle_declared",
                "execution_result_mapping_declared",
                "execution_deferred_to_future_step",
                "execution_performed",
                "execution_performed_by_codex",
                "execution_performed_by_operator",
                "credential_read_performed",
                "env_access_capability_present",
                "credential_read_capability_present",
                "checker_result_unavailable",
                "checker_result_stale",
                "checker_result_timeout",
                "operator_workflow_supported",
                "operator_workflow_preserved",
                "signature_value_generated",
                "header_values_present",
                "allowed_for_live",
                "post_allowed_this_step",
                "post_executed",
                "retry_allowed",
                "loop_allowed",
            ),
        )
        if self.http_post_executed:
            raise LiveVerificationValidationError("internal wiring must not execute POST")
        if self.order_endpoint_called:
            raise LiveVerificationValidationError("internal wiring must not call endpoint")
        if self.live_order_once_called:
            raise LiveVerificationValidationError("internal wiring must not call live_order_once")
        if self.credential_values_provided:
            raise LiveVerificationValidationError("internal wiring must not use credentials")
        if self.credential_values_loaded:
            raise LiveVerificationValidationError("internal wiring must not load credentials")
        if self.credential_presence_checked_against_environment:
            raise LiveVerificationValidationError("internal wiring must not check env credentials")
        if self.env_access_requested:
            raise LiveVerificationValidationError("internal wiring must not access env")
        if self.credential_metadata_exposed:
            raise LiveVerificationValidationError("internal wiring must not expose metadata")
        if self.handle_created:
            raise LiveVerificationValidationError("internal wiring must not create handle")
        if self.handle_contains_value:
            raise LiveVerificationValidationError("internal wiring must not hold handle value")
        if self.handle_contains_identifier:
            raise LiveVerificationValidationError("internal wiring must not hold handle identifier")
        if self.handle_metadata_exposed:
            raise LiveVerificationValidationError("internal wiring must not expose handle metadata")
        if self.injection_performed:
            raise LiveVerificationValidationError("internal wiring must not inject credentials")
        if self.real_credential_values_available:
            raise LiveVerificationValidationError(
                "internal wiring must not expose credential values",
            )
        if self.real_credential_values_injected:
            raise LiveVerificationValidationError(
                "internal wiring must not inject credential values",
            )
        if self.credential_injection_metadata_available:
            raise LiveVerificationValidationError(
                "internal wiring must not expose credential injection metadata",
            )
        if self.operator_sentinel_reused or self.operator_sentinel_stale:
            raise LiveVerificationValidationError("internal wiring must not reuse sentinel")
        if self.operator_sentinel_previous_turn:
            raise LiveVerificationValidationError(
                "internal wiring must not use previous turn sentinel",
            )
        if (
            self.sentinel_value_present
            or self.sentinel_value_displayed
            or self.sentinel_value_saved
            or self.sentinel_hash_available
            or self.sentinel_fingerprint_available
            or self.sentinel_length_available
        ):
            raise LiveVerificationValidationError("internal wiring must not expose sentinel")
        if self.presence_result_broadly_propagated or self.presence_result_saved:
            raise LiveVerificationValidationError(
                "internal wiring must not broadly propagate presence result",
            )
        if self.operator_presence_result_reused or self.operator_presence_result_stale:
            raise LiveVerificationValidationError(
                "internal wiring must not reuse presence result",
            )
        if self.operator_presence_result_previous_turn:
            raise LiveVerificationValidationError(
                "internal wiring must not use previous turn presence result",
            )
        if self.presence_result_displayed:
            raise LiveVerificationValidationError(
                "internal wiring must not display presence result",
            )
        if self.actual_environment_presence_check_performed:
            raise LiveVerificationValidationError(
                "internal wiring must not check real credential presence",
            )
        if self.real_checker_attached or self.real_checker_executed:
            raise LiveVerificationValidationError(
                "internal wiring must not attach or execute real checker",
            )
        if self.real_checker_implementation_present:
            raise LiveVerificationValidationError(
                "internal wiring must not include real checker implementation",
            )
        if self.env_access_allowed:
            raise LiveVerificationValidationError("internal wiring must not allow env")
        if (
            self.credential_values_available
            or self.credential_values_read
            or self.credential_values_displayed
            or self.credential_values_saved
        ):
            raise LiveVerificationValidationError(
                "internal wiring must not use checker credentials",
            )
        if (
            self.credential_metadata_available
            or self.credential_metadata_displayed
            or self.credential_metadata_saved
        ):
            raise LiveVerificationValidationError(
                "internal wiring must not expose checker credential metadata",
            )
        if (
            self.checker_result_available
            or self.checker_result_saved
            or self.checker_result_displayed
            or self.checker_result_broadly_propagated
        ):
            raise LiveVerificationValidationError(
                "internal wiring must not expose checker results",
            )
        if self.checker_result_unknown or self.checker_result_failed:
            raise LiveVerificationValidationError(
                "internal wiring must not accept unknown or failed checker result",
            )
        if self.codex_execution_performed:
            raise LiveVerificationValidationError(
                "internal wiring must not execute checker in Codex",
            )
        if self.codex_env_access_requested:
            raise LiveVerificationValidationError(
                "internal wiring must not request Codex env access",
            )
        if self.actual_environment_presence_check_performed_by_codex:
            raise LiveVerificationValidationError(
                "internal wiring must not perform Codex environment check",
            )
        if self.operator_result_raw_value_present:
            raise LiveVerificationValidationError(
                "internal wiring must not hold raw operator result value",
            )
        if self.operator_result_raw_value_saved or self.operator_result_raw_value_displayed:
            raise LiveVerificationValidationError(
                "internal wiring must not save or display raw operator result value",
            )
        if self.operator_result_stale or self.operator_result_reused:
            raise LiveVerificationValidationError(
                "internal wiring must not accept stale or reused operator result",
            )
        if self.operator_result_previous_turn:
            raise LiveVerificationValidationError(
                "internal wiring must not use previous-turn operator result",
            )
        if self.operator_result_timeout:
            raise LiveVerificationValidationError(
                "internal wiring must not accept timeout operator result",
            )
        if (
            self.operator_result_unknown
            or self.operator_result_failed
            or self.operator_result_unavailable
        ):
            raise LiveVerificationValidationError(
                "internal wiring must not accept unknown failed or unavailable operator result",
            )
        if (
            self.operator_result_saved
            or self.operator_result_displayed
            or self.operator_result_broadly_propagated
            or self.operator_result_detail_present
        ):
            raise LiveVerificationValidationError(
                "internal wiring must not expose operator result detail",
            )
        if self.receipt_stale or self.receipt_reused:
            raise LiveVerificationValidationError(
                "internal wiring must not accept stale or reused receipt",
            )
        if self.receipt_previous_turn:
            raise LiveVerificationValidationError(
                "internal wiring must not use previous-turn receipt",
            )
        if self.receipt_expired:
            raise LiveVerificationValidationError(
                "internal wiring must not accept expired receipt",
            )
        if (
            self.receipt_timeout
            or self.receipt_unknown
            or self.receipt_failed
            or self.receipt_unavailable
        ):
            raise LiveVerificationValidationError(
                "internal wiring must not accept unknown failed unavailable or timeout receipt",
            )
        if self.receipt_raw_value_present or self.receipt_detail_present:
            raise LiveVerificationValidationError(
                "internal wiring must not expose receipt raw value or detail",
            )
        if (
            self.receipt_id_present
            or self.receipt_token_present
            or self.receipt_nonce_present
            or self.receipt_hash_present
            or self.receipt_fingerprint_present
            or self.receipt_length_present
        ):
            raise LiveVerificationValidationError(
                "internal wiring must not expose receipt identifiers",
            )
        if self.env_variable_names_present:
            raise LiveVerificationValidationError(
                "internal wiring must not expose env variable names",
            )
        if self.checker_result_detail_present:
            raise LiveVerificationValidationError(
                "internal wiring must not expose checker result detail",
            )
        if self.execution_performed:
            raise LiveVerificationValidationError(
                "internal wiring must not execute checker implementation",
            )
        if self.execution_performed_by_codex or self.execution_performed_by_operator:
            raise LiveVerificationValidationError(
                "internal wiring must not execute checker contract",
            )
        if self.credential_read_performed:
            raise LiveVerificationValidationError(
                "internal wiring must not read credentials",
            )
        if self.env_access_capability_present:
            raise LiveVerificationValidationError(
                "internal wiring must not expose env access capability",
            )
        if self.credential_read_capability_present:
            raise LiveVerificationValidationError(
                "internal wiring must not expose credential read capability",
            )
        if self.checker_result_unavailable or self.checker_result_stale:
            raise LiveVerificationValidationError(
                "internal wiring must not accept unavailable or stale checker result",
            )
        if self.checker_result_timeout:
            raise LiveVerificationValidationError(
                "internal wiring must not accept timeout checker result",
            )
        if self.signature_value_generated:
            raise LiveVerificationValidationError("internal wiring must not sign")
        if self.header_values_present:
            raise LiveVerificationValidationError("internal wiring must not hold header values")
        if (
            self.dummy_signature_value_present
            or self.dummy_signature_value_displayed
            or self.dummy_signature_value_saved
        ):
            raise LiveVerificationValidationError("internal wiring must not expose dummy signature")
        if self.http_client_present:
            raise LiveVerificationValidationError("internal wiring must not include HTTP client")
        if self.can_execute_http_post:
            raise LiveVerificationValidationError("internal wiring must not execute POST")
        if self.can_call_order_endpoint:
            raise LiveVerificationValidationError("internal wiring must not call endpoint")
        if self.can_call_live_order_once:
            raise LiveVerificationValidationError("internal wiring must not call live_order_once")
        if self.post_allowed_this_step or self.post_executed:
            raise LiveVerificationValidationError("internal wiring must not authorize POST")
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _require_non_empty("recommended_next_step", self.recommended_next_step)


def build_valid_step6g_internal_wiring_snapshot(
    *,
    input_snapshot: LiveOrderRealStep6GInternalWiringInput | None = None,
    created_at: datetime | None = None,
) -> LiveOrderRealStep6GInternalWiringSnapshot:
    """Build all fake/sanitized Step 6G pieces without API or POST execution."""
    wiring_input = input_snapshot or LiveOrderRealStep6GInternalWiringInput()
    created = _ensure_aware(created_at or datetime.now(UTC))

    pb_result = build_live_order_real_step6g_post_route_bridge(
        order_intent_snapshot=_pb_order_intent(wiring_input),
        approval_snapshot=_pb_approval(wiring_input),
        preflight_snapshot=_pb_preflight(wiring_input),
        attempt_state=_pb_attempt(wiring_input),
        route_contract_snapshot=_pb_route(wiring_input),
        created_at=created,
    )
    eb_result = run_live_order_real_step6g_fake_runtime_bridge(
        step6g_post_route_bridge_result=pb_result,
        created_at=created,
    )
    ad_result = run_live_order_real_step6g_controlled_adapter_with_fake_transport(
        step6g_post_route_bridge_result=pb_result,
        step6g_runtime_bridge_result=eb_result,
        created_at=created,
    )
    ra_result = run_live_order_real_step6g_real_adapter_with_stub_transport(
        step6g_post_route_bridge_result=pb_result,
        step6g_runtime_bridge_result=eb_result,
        step6g_controlled_adapter_result=ad_result,
        created_at=created,
    )
    tc_result = build_live_order_real_order_transport_core(
        intent=_tc_intent(wiring_input),
        endpoint_contract=make_live_order_real_transport_endpoint_contract(
            order_endpoint_called=wiring_input.order_endpoint_called,
            http_post_executed=wiring_input.http_post_executed,
            live_order_once_called=wiring_input.live_order_once_called,
        ),
        header_contract=build_private_order_header_contract_without_exposure(
            header_values_redacted=not wiring_input.header_values_present,
            signature_value_generated=wiring_input.signature_value_generated,
            signature_value_displayed=wiring_input.signature_displayed,
            signature_value_saved=wiring_input.signature_saved,
            credentials_used=wiring_input.credential_values_provided,
            credentials_displayed=wiring_input.credentials_displayed,
            headers_displayed=wiring_input.headers_displayed,
            headers_saved=wiring_input.headers_saved,
        ),
        no_retry_contract=LiveOrderRealNoRetryContract(
            post_attempt_limit=wiring_input.post_attempt_limit,
            post_attempt_count_before=wiring_input.post_attempt_count_before,
            post_attempt_count_after=0,
            retry_allowed=wiring_input.retry_allowed,
            loop_allowed=wiring_input.loop_allowed,
            retry_on_unknown=False,
            retry_on_timeout=False,
            retry_on_reject=False,
            add_order_allowed=wiring_input.add_order_allowed,
            change_order_allowed=wiring_input.change_order_allowed,
            cancel_order_allowed=wiring_input.cancel_order_allowed,
            close_order_allowed=wiring_input.close_order_allowed,
        ),
    )
    signing_result = build_live_order_real_signing_contract(
        input_contract=LiveOrderRealSigningInputContract(
            credential_values_provided=wiring_input.credential_values_provided,
            signature_value_generated=wiring_input.signature_value_generated,
            header_values_redacted=not wiring_input.header_values_present,
            headers_displayed=wiring_input.headers_displayed,
            headers_saved=wiring_input.headers_saved,
            credentials_displayed=wiring_input.credentials_displayed,
            credentials_saved=wiring_input.credentials_saved,
            signature_displayed=wiring_input.signature_displayed,
            signature_saved=wiring_input.signature_saved,
        ),
        header_contract=LiveOrderRealRedactedHeaderContract(
            header_values_present=wiring_input.header_values_present,
            header_values_redacted=not wiring_input.header_values_present,
            signature_value_present=wiring_input.signature_value_generated,
            credential_value_present=wiring_input.credential_values_provided,
        ),
    )
    private_transport_result = build_live_order_real_private_order_transport_contract(
        prerequisites=LiveOrderRealPrivateOrderTransportPrerequisites(
            signing_contract_ready=signing_result.signing_contract_ready,
            redacted_header_contract_ready=signing_result.redacted_header_contract_ready,
            order_body_allowlist_passed=tc_result.body_allowlist_passed,
            stable_serialization_ready=tc_result.stable_serialization_ready,
            endpoint_contract_ready=not (
                tc_result.http_post_executed
                or tc_result.order_endpoint_called
                or tc_result.live_order_once_called
            ),
            post_attempt_limit=wiring_input.post_attempt_limit,
            post_attempt_count_before=wiring_input.post_attempt_count_before,
            retry_allowed=wiring_input.retry_allowed,
            loop_allowed=wiring_input.loop_allowed,
            add_order_allowed=wiring_input.add_order_allowed,
            change_order_allowed=wiring_input.change_order_allowed,
            cancel_order_allowed=wiring_input.cancel_order_allowed,
            close_order_allowed=wiring_input.close_order_allowed,
            raw_request_displayed=wiring_input.raw_request_displayed,
            raw_request_saved=wiring_input.raw_request_saved,
            raw_response_displayed=wiring_input.raw_response_displayed,
            raw_response_saved=wiring_input.raw_response_saved,
            headers_displayed=wiring_input.headers_displayed,
            headers_saved=wiring_input.headers_saved,
            signature_displayed=wiring_input.signature_displayed,
            signature_saved=wiring_input.signature_saved,
            credentials_displayed=wiring_input.credentials_displayed,
            credentials_saved=wiring_input.credentials_saved,
            real_ids_displayed=wiring_input.real_ids_displayed,
            real_ids_saved=wiring_input.real_ids_saved,
            http_post_executed=wiring_input.http_post_executed,
            order_endpoint_called=wiring_input.order_endpoint_called,
            live_order_once_called=wiring_input.live_order_once_called,
            post_allowed_this_step=wiring_input.post_allowed_this_step,
            post_executed=wiring_input.post_executed,
        ),
        signing_contract_result=signing_result,
    )
    dummy_signing_result = build_live_order_real_dummy_signing_check(
        input_snapshot=LiveOrderRealDummySigningInput(
            body_contract_ready=tc_result.body_allowlist_passed,
            stable_serialization_ready=tc_result.stable_serialization_ready,
            use_real_credentials=wiring_input.credential_values_provided,
            use_env_credentials=False,
            use_dotenv=False,
            generate_real_signature=wiring_input.signature_value_generated,
            expose_signature_value=wiring_input.dummy_signature_value_displayed,
            store_signature_value=wiring_input.dummy_signature_value_saved,
            expose_header_values=wiring_input.headers_displayed,
            store_header_values=wiring_input.headers_saved,
            expose_credentials=wiring_input.credentials_displayed,
            store_credentials=wiring_input.credentials_saved,
            signature_value_present=wiring_input.dummy_signature_value_present,
            credential_value_present=wiring_input.credential_values_provided,
            header_values_present=wiring_input.header_values_present,
            raw_request_displayed=wiring_input.raw_request_displayed,
            raw_request_saved=wiring_input.raw_request_saved,
            raw_response_displayed=wiring_input.raw_response_displayed,
            raw_response_saved=wiring_input.raw_response_saved,
            http_post_executed=wiring_input.http_post_executed,
            order_endpoint_called=wiring_input.order_endpoint_called,
            live_order_once_called=wiring_input.live_order_once_called,
            post_allowed_this_step=wiring_input.post_allowed_this_step,
            post_executed=wiring_input.post_executed,
            retry_allowed=wiring_input.retry_allowed,
            loop_allowed=wiring_input.loop_allowed,
        ),
    )
    http_transport_interface_result = build_live_order_real_http_transport_interface(
        input_snapshot=LiveOrderRealHttpTransportInterfaceInput(
            interface_mode=wiring_input.http_transport_interface_mode,
            endpoint_contract_ready=not (
                tc_result.http_post_executed
                or tc_result.order_endpoint_called
                or tc_result.live_order_once_called
            ),
            order_body_allowlist_passed=tc_result.body_allowlist_passed,
            stable_serialization_ready=tc_result.stable_serialization_ready,
            signing_contract_ready=signing_result.signing_contract_ready,
            dummy_signing_ready=dummy_signing_result.dummy_signing_ready,
            dummy_signature_check_passed=(
                dummy_signing_result.dummy_signature_check_passed
            ),
            private_order_transport_contract_ready=(
                private_transport_result.transport_contract_ready
            ),
            one_shot_no_retry_ready=not _attempt_reasons(wiring_input),
            post_attempt_limit=wiring_input.post_attempt_limit,
            post_attempt_count_before=wiring_input.post_attempt_count_before,
            retry_allowed=wiring_input.retry_allowed,
            loop_allowed=wiring_input.loop_allowed,
            add_order_allowed=wiring_input.add_order_allowed,
            change_order_allowed=wiring_input.change_order_allowed,
            cancel_order_allowed=wiring_input.cancel_order_allowed,
            close_order_allowed=wiring_input.close_order_allowed,
            real_transport_requested=False,
            http_client_present=wiring_input.http_client_present,
            can_execute_http_post=wiring_input.can_execute_http_post,
            can_call_order_endpoint=wiring_input.can_call_order_endpoint,
            can_call_live_order_once=wiring_input.can_call_live_order_once,
            credential_values_provided=wiring_input.credential_values_provided,
            signature_value_generated=wiring_input.signature_value_generated,
            header_values_present=wiring_input.header_values_present,
            raw_request_present=(
                wiring_input.raw_request_displayed or wiring_input.raw_request_saved
            ),
            raw_response_present=(
                wiring_input.raw_response_displayed or wiring_input.raw_response_saved
            ),
            real_ids_present=(
                wiring_input.real_ids_displayed or wiring_input.real_ids_saved
            ),
            post_allowed_this_step=wiring_input.post_allowed_this_step,
            post_executed=wiring_input.post_executed,
        ),
    )
    credential_boundary_result = build_live_order_real_credential_boundary(
        input_snapshot=LiveOrderRealCredentialBoundaryInput(
            boundary_mode=wiring_input.credential_boundary_mode,
            real_credentials_requested=False,
            credential_values_provided=wiring_input.credential_values_provided,
            credential_values_loaded=wiring_input.credential_values_loaded,
            credential_presence_checked_against_environment=(
                wiring_input.credential_presence_checked_against_environment
            ),
            env_access_requested=wiring_input.env_access_requested,
            dotenv_access_requested=False,
            printenv_requested=False,
            credential_fingerprint_available=wiring_input.credential_metadata_exposed,
            credential_values_displayed=wiring_input.credentials_displayed,
            credential_values_saved=wiring_input.credentials_saved,
            credentials_safe_to_render=not wiring_input.credential_metadata_exposed,
            credentials_safe_to_serialize=not wiring_input.credential_metadata_exposed,
            signing_contract_ready=(
                signing_result.signing_contract_ready
                and wiring_input.credential_boundary_ready
            ),
            dummy_signing_ready=dummy_signing_result.dummy_signing_ready,
            http_transport_interface_ready=True,
            can_generate_real_signature=False,
            can_generate_real_headers=False,
            can_execute_http_post=False,
            http_post_executed=wiring_input.http_post_executed,
            order_endpoint_called=wiring_input.order_endpoint_called,
            live_order_once_called=wiring_input.live_order_once_called,
            post_allowed_this_step=wiring_input.post_allowed_this_step,
            post_executed=wiring_input.post_executed,
            retry_allowed=wiring_input.retry_allowed,
            loop_allowed=wiring_input.loop_allowed,
        ),
    )
    credential_handle_result = build_live_order_real_credential_handle(
        input_snapshot=LiveOrderRealCredentialHandleInput(
            handle_mode=wiring_input.credential_handle_mode,
            credential_boundary_ready=(
                credential_boundary_result.credential_boundary_ready
                and wiring_input.credential_handle_ready
            ),
            handle_requested=wiring_input.handle_requested,
            handle_created=wiring_input.handle_created,
            handle_contains_value=wiring_input.handle_contains_value,
            handle_contains_identifier=wiring_input.handle_contains_identifier,
            handle_fingerprint_available=wiring_input.handle_metadata_exposed,
            env_access_requested=wiring_input.env_access_requested,
            dotenv_access_requested=False,
            credential_values_provided=wiring_input.credential_values_provided,
            credential_values_loaded=wiring_input.credential_values_loaded,
            can_generate_real_signature=False,
            can_generate_real_headers=False,
            can_execute_http_post=False,
            http_post_executed=wiring_input.http_post_executed,
            order_endpoint_called=wiring_input.order_endpoint_called,
            live_order_once_called=wiring_input.live_order_once_called,
            post_allowed_this_step=wiring_input.post_allowed_this_step,
            post_executed=wiring_input.post_executed,
            retry_allowed=wiring_input.retry_allowed,
            loop_allowed=wiring_input.loop_allowed,
        ),
    )
    credential_injection_result = build_live_order_real_credential_injection(
        input_snapshot=LiveOrderRealCredentialInjectionInput(
            injection_mode=wiring_input.credential_injection_mode,
            credential_boundary_ready=credential_boundary_result.credential_boundary_ready,
            credential_handle_ready=(
                credential_handle_result.credential_handle_ready
                and wiring_input.credential_injection_ready
            ),
            injection_requested=wiring_input.injection_requested,
            injection_performed=wiring_input.injection_performed,
            real_credential_values_available=(
                wiring_input.real_credential_values_available
            ),
            real_credential_values_injected=(
                wiring_input.real_credential_values_injected
            ),
            credential_values_provided=wiring_input.credential_values_provided,
            credential_values_loaded=wiring_input.credential_values_loaded,
            credential_values_displayed=wiring_input.credentials_displayed,
            credential_values_saved=wiring_input.credentials_saved,
            credential_metadata_available=(
                wiring_input.credential_injection_metadata_available
            ),
            credential_metadata_displayed=wiring_input.credential_metadata_exposed,
            credential_metadata_saved=wiring_input.credential_metadata_exposed,
            handle_created=wiring_input.handle_created,
            handle_contains_value=wiring_input.handle_contains_value,
            handle_contains_identifier=wiring_input.handle_contains_identifier,
            handle_value_displayed=False,
            handle_value_saved=False,
            env_access_requested=wiring_input.env_access_requested,
            dotenv_access_requested=False,
            credential_presence_checked_against_environment=(
                wiring_input.credential_presence_checked_against_environment
            ),
            can_generate_real_signature=False,
            can_generate_real_headers=False,
            can_execute_http_post=False,
            http_post_executed=wiring_input.http_post_executed,
            order_endpoint_called=wiring_input.order_endpoint_called,
            live_order_once_called=wiring_input.live_order_once_called,
            post_allowed_this_step=wiring_input.post_allowed_this_step,
            post_executed=wiring_input.post_executed,
            retry_allowed=wiring_input.retry_allowed,
            loop_allowed=wiring_input.loop_allowed,
        ),
    )
    credential_presence_check_result = build_live_order_real_credential_presence_check(
        input_snapshot=LiveOrderRealCredentialPresenceCheckInput(
            presence_check_mode=wiring_input.presence_check_mode,
            credential_boundary_ready=credential_boundary_result.credential_boundary_ready,
            credential_handle_ready=credential_handle_result.credential_handle_ready,
            credential_injection_ready=(
                credential_injection_result.credential_injection_ready
                and wiring_input.credential_presence_check_ready
            ),
            operator_assertion_provided=wiring_input.operator_assertion_provided,
            operator_assertion_is_boolean_only=(
                wiring_input.operator_assertion_is_boolean_only
            ),
            operator_sentinel_received=wiring_input.operator_sentinel_received,
            operator_sentinel_fresh=wiring_input.operator_sentinel_fresh,
            operator_sentinel_reused=wiring_input.operator_sentinel_reused,
            operator_sentinel_stale=wiring_input.operator_sentinel_stale,
            operator_sentinel_previous_turn=wiring_input.operator_sentinel_previous_turn,
            sentinel_value_present=wiring_input.sentinel_value_present,
            sentinel_value_displayed=wiring_input.sentinel_value_displayed,
            sentinel_value_saved=wiring_input.sentinel_value_saved,
            sentinel_hash_available=wiring_input.sentinel_hash_available,
            sentinel_fingerprint_available=wiring_input.sentinel_fingerprint_available,
            sentinel_length_available=wiring_input.sentinel_length_available,
            credential_values_present=(
                wiring_input.credential_values_provided
                or wiring_input.credential_values_loaded
            ),
            credential_metadata_present=(
                wiring_input.credential_metadata_exposed
                or wiring_input.credential_injection_metadata_available
            ),
            credential_presence_checked_against_environment=(
                wiring_input.credential_presence_checked_against_environment
            ),
            env_access_requested=wiring_input.env_access_requested,
            dotenv_access_requested=False,
            printenv_requested=False,
            presence_result_broadly_propagated=(
                wiring_input.presence_result_broadly_propagated
            ),
            presence_result_saved=wiring_input.presence_result_saved,
            can_generate_real_signature=False,
            can_generate_real_headers=False,
            can_execute_http_post=False,
            http_post_executed=wiring_input.http_post_executed,
            order_endpoint_called=wiring_input.order_endpoint_called,
            live_order_once_called=wiring_input.live_order_once_called,
            post_allowed_this_step=wiring_input.post_allowed_this_step,
            post_executed=wiring_input.post_executed,
            retry_allowed=wiring_input.retry_allowed,
            loop_allowed=wiring_input.loop_allowed,
        ),
    )
    credential_presence_adapter_result = build_live_order_real_credential_presence_adapter(
        input_snapshot=LiveOrderRealCredentialPresenceAdapterInput(
            adapter_mode=wiring_input.presence_adapter_mode,
            credential_presence_check_ready=(
                credential_presence_check_result.credential_presence_check_ready
                and wiring_input.credential_presence_adapter_ready
            ),
            credential_boundary_ready=credential_boundary_result.credential_boundary_ready,
            credential_handle_ready=credential_handle_result.credential_handle_ready,
            credential_injection_ready=(
                credential_injection_result.credential_injection_ready
            ),
            operator_provided_presence_result=(
                wiring_input.operator_provided_presence_result
            ),
            operator_presence_result_is_boolean_only=(
                wiring_input.operator_presence_result_is_boolean_only
            ),
            operator_presence_result_fresh=wiring_input.operator_presence_result_fresh,
            operator_presence_result_reused=wiring_input.operator_presence_result_reused,
            operator_presence_result_stale=wiring_input.operator_presence_result_stale,
            operator_presence_result_previous_turn=(
                wiring_input.operator_presence_result_previous_turn
            ),
            presence_result_adapted=wiring_input.presence_result_adapted,
            presence_result_saved=wiring_input.presence_result_saved,
            presence_result_displayed=wiring_input.presence_result_displayed,
            presence_result_broadly_propagated=(
                wiring_input.presence_result_broadly_propagated
            ),
            sentinel_value_present=wiring_input.sentinel_value_present,
            sentinel_value_displayed=wiring_input.sentinel_value_displayed,
            sentinel_value_saved=wiring_input.sentinel_value_saved,
            sentinel_hash_available=wiring_input.sentinel_hash_available,
            sentinel_fingerprint_available=wiring_input.sentinel_fingerprint_available,
            sentinel_length_available=wiring_input.sentinel_length_available,
            credential_values_present=(
                wiring_input.credential_values_provided
                or wiring_input.credential_values_loaded
            ),
            credential_metadata_present=(
                wiring_input.credential_metadata_exposed
                or wiring_input.credential_injection_metadata_available
            ),
            actual_environment_presence_check_performed=(
                wiring_input.actual_environment_presence_check_performed
            ),
            env_access_requested=wiring_input.env_access_requested,
            dotenv_access_requested=False,
            printenv_requested=False,
            real_checker_attached=wiring_input.real_checker_attached,
            real_checker_executed=wiring_input.real_checker_executed,
            can_generate_real_signature=False,
            can_generate_real_headers=False,
            can_execute_http_post=False,
            http_post_executed=wiring_input.http_post_executed,
            order_endpoint_called=wiring_input.order_endpoint_called,
            live_order_once_called=wiring_input.live_order_once_called,
            post_allowed_this_step=wiring_input.post_allowed_this_step,
            post_executed=wiring_input.post_executed,
            retry_allowed=wiring_input.retry_allowed,
            loop_allowed=wiring_input.loop_allowed,
        ),
    )
    credential_presence_checker_contract_result = (
        build_live_order_real_credential_presence_checker_contract(
            input_snapshot=LiveOrderRealCredentialPresenceCheckerContractInput(
                checker_contract_mode=wiring_input.checker_contract_mode,
                credential_presence_adapter_ready=(
                    credential_presence_adapter_result.credential_presence_adapter_ready
                    and wiring_input.credential_presence_checker_contract_ready
                ),
                credential_presence_check_ready=(
                    credential_presence_check_result.credential_presence_check_ready
                ),
                credential_boundary_ready=credential_boundary_result.credential_boundary_ready,
                credential_handle_ready=credential_handle_result.credential_handle_ready,
                credential_injection_ready=(
                    credential_injection_result.credential_injection_ready
                ),
                checker_contract_requested=wiring_input.checker_contract_requested,
                checker_contract_ready_requested=(
                    wiring_input.checker_contract_ready_requested
                ),
                real_checker_implementation_present=(
                    wiring_input.real_checker_implementation_present
                ),
                real_checker_attached=wiring_input.real_checker_attached,
                real_checker_executed=wiring_input.real_checker_executed,
                actual_environment_presence_check_performed=(
                    wiring_input.actual_environment_presence_check_performed
                ),
                env_access_required=wiring_input.env_access_required,
                env_access_allowed=wiring_input.env_access_allowed,
                env_access_requested=wiring_input.env_access_requested,
                dotenv_access_requested=False,
                printenv_requested=False,
                credential_values_available=wiring_input.credential_values_available,
                credential_values_read=wiring_input.credential_values_read,
                credential_values_displayed=wiring_input.credential_values_displayed,
                credential_values_saved=wiring_input.credential_values_saved,
                credential_metadata_available=(
                    wiring_input.credential_metadata_available
                ),
                credential_metadata_displayed=(
                    wiring_input.credential_metadata_displayed
                ),
                credential_metadata_saved=wiring_input.credential_metadata_saved,
                checker_result_available=wiring_input.checker_result_available,
                checker_result_is_boolean_only=(
                    wiring_input.checker_result_is_boolean_only
                ),
                checker_result_saved=wiring_input.checker_result_saved,
                checker_result_displayed=wiring_input.checker_result_displayed,
                checker_result_broadly_propagated=(
                    wiring_input.checker_result_broadly_propagated
                ),
                checker_result_unknown=wiring_input.checker_result_unknown,
                checker_result_failed=wiring_input.checker_result_failed,
                can_generate_real_signature=False,
                can_generate_real_headers=False,
                can_execute_http_post=False,
                http_post_executed=wiring_input.http_post_executed,
                order_endpoint_called=wiring_input.order_endpoint_called,
                live_order_once_called=wiring_input.live_order_once_called,
                post_allowed_this_step=wiring_input.post_allowed_this_step,
                post_executed=wiring_input.post_executed,
                retry_allowed=wiring_input.retry_allowed,
                loop_allowed=wiring_input.loop_allowed,
            ),
        )
    )
    operator_checker_workflow_result = (
        build_live_order_real_operator_executed_checker_workflow(
            input_snapshot=LiveOrderRealOperatorExecutedCheckerWorkflowInput(
                workflow_mode=wiring_input.operator_checker_workflow_mode,
                credential_presence_checker_contract_ready=(
                    credential_presence_checker_contract_result
                    .credential_presence_checker_contract_ready
                    and wiring_input.operator_checker_workflow_ready
                ),
                credential_presence_adapter_ready=(
                    credential_presence_adapter_result.credential_presence_adapter_ready
                ),
                credential_presence_check_ready=(
                    credential_presence_check_result.credential_presence_check_ready
                ),
                operator_workflow_declared=wiring_input.operator_workflow_declared,
                operator_execution_required=wiring_input.operator_execution_required,
                operator_execution_performed_outside_codex=(
                    wiring_input.operator_execution_performed_outside_codex
                ),
                codex_execution_performed=wiring_input.codex_execution_performed,
                codex_env_access_requested=wiring_input.codex_env_access_requested,
                actual_environment_presence_check_performed_by_codex=(
                    wiring_input.actual_environment_presence_check_performed_by_codex
                ),
                operator_result_handoff_declared=(
                    wiring_input.operator_result_handoff_declared
                ),
                operator_result_handoff_safe=(
                    wiring_input.operator_result_handoff_safe
                ),
                operator_result_category_only=(
                    wiring_input.operator_result_category_only
                ),
                operator_result_provided=wiring_input.operator_result_provided,
                operator_result_is_boolean_only=(
                    wiring_input.operator_result_is_boolean_only
                ),
                operator_result_raw_value_present=(
                    wiring_input.operator_result_raw_value_present
                ),
                operator_result_raw_value_saved=(
                    wiring_input.operator_result_raw_value_saved
                ),
                operator_result_raw_value_displayed=(
                    wiring_input.operator_result_raw_value_displayed
                ),
                operator_result_fresh=wiring_input.operator_result_fresh,
                operator_result_stale=wiring_input.operator_result_stale,
                operator_result_reused=wiring_input.operator_result_reused,
                operator_result_previous_turn=(
                    wiring_input.operator_result_previous_turn
                ),
                operator_result_timeout=wiring_input.operator_result_timeout,
                operator_result_unknown=wiring_input.operator_result_unknown,
                operator_result_failed=wiring_input.operator_result_failed,
                operator_result_unavailable=wiring_input.operator_result_unavailable,
                operator_result_saved=wiring_input.operator_result_saved,
                operator_result_displayed=wiring_input.operator_result_displayed,
                operator_result_broadly_propagated=(
                    wiring_input.operator_result_broadly_propagated
                ),
                operator_result_detail_present=(
                    wiring_input.operator_result_detail_present
                ),
                credential_values_present=(
                    wiring_input.credential_values_provided
                    or wiring_input.credential_values_loaded
                    or wiring_input.credential_values_available
                    or wiring_input.credential_values_read
                ),
                credential_metadata_present=(
                    wiring_input.credential_metadata_exposed
                    or wiring_input.credential_injection_metadata_available
                    or wiring_input.credential_metadata_available
                ),
                env_variable_names_present=wiring_input.env_variable_names_present,
                sentinel_value_present=wiring_input.sentinel_value_present,
                checker_result_detail_present=(
                    wiring_input.checker_result_detail_present
                ),
                can_generate_real_signature=False,
                can_generate_real_headers=False,
                can_execute_http_post=False,
                safe_to_render=not (
                    wiring_input.operator_result_displayed
                    or wiring_input.operator_result_detail_present
                ),
                safe_to_serialize=not (
                    wiring_input.operator_result_saved
                    or wiring_input.operator_result_detail_present
                ),
                http_post_executed=wiring_input.http_post_executed,
                order_endpoint_called=wiring_input.order_endpoint_called,
                live_order_once_called=wiring_input.live_order_once_called,
                post_allowed_this_step=wiring_input.post_allowed_this_step,
                post_executed=wiring_input.post_executed,
                retry_allowed=wiring_input.retry_allowed,
                loop_allowed=wiring_input.loop_allowed,
            ),
        )
    )
    credential_presence_checker_implementation_result = (
        build_live_order_real_credential_presence_checker_implementation(
            input_snapshot=LiveOrderRealCredentialPresenceCheckerImplementationInput(
                implementation_mode=wiring_input.checker_implementation_mode,
                checker_contract_ready=(
                    credential_presence_checker_contract_result
                    .credential_presence_checker_contract_ready
                    and wiring_input.checker_implementation_skeleton_ready
                ),
                operator_checker_workflow_ready=(
                    operator_checker_workflow_result.operator_checker_workflow_ready
                ),
                credential_presence_adapter_ready=(
                    credential_presence_adapter_result.credential_presence_adapter_ready
                ),
                credential_presence_check_ready=(
                    credential_presence_check_result.credential_presence_check_ready
                ),
                implementation_interface_declared=(
                    wiring_input.implementation_interface_declared
                ),
                implementation_lifecycle_declared=(
                    wiring_input.implementation_lifecycle_declared
                ),
                execution_deferred_to_future_step=(
                    wiring_input.execution_deferred_to_future_step
                ),
                execution_performed=wiring_input.execution_performed,
                codex_env_access_requested=wiring_input.codex_env_access_requested,
                actual_environment_presence_check_performed=(
                    wiring_input.actual_environment_presence_check_performed
                ),
                env_access_capability_present=(
                    wiring_input.env_access_capability_present
                ),
                credential_read_capability_present=(
                    wiring_input.credential_read_capability_present
                ),
                credential_values_read=wiring_input.credential_values_read,
                credential_values_present=(
                    wiring_input.credential_values_provided
                    or wiring_input.credential_values_loaded
                    or wiring_input.credential_values_available
                    or wiring_input.credential_values_read
                ),
                credential_metadata_present=(
                    wiring_input.credential_metadata_exposed
                    or wiring_input.credential_injection_metadata_available
                    or wiring_input.credential_metadata_available
                ),
                checker_result_available=wiring_input.checker_result_available,
                checker_result_detail_present=(
                    wiring_input.checker_result_detail_present
                ),
                checker_result_unknown=wiring_input.checker_result_unknown,
                checker_result_failed=wiring_input.checker_result_failed,
                checker_result_unavailable=wiring_input.checker_result_unavailable,
                checker_result_stale=wiring_input.checker_result_stale,
                checker_result_saved=wiring_input.checker_result_saved,
                checker_result_displayed=wiring_input.checker_result_displayed,
                operator_workflow_supported=wiring_input.operator_workflow_supported,
                operator_workflow_preserved=wiring_input.operator_workflow_preserved,
                can_generate_real_signature=False,
                can_generate_real_headers=False,
                can_execute_http_post=False,
                safe_to_render=not (
                    wiring_input.checker_result_displayed
                    or wiring_input.checker_result_detail_present
                ),
                safe_to_serialize=not (
                    wiring_input.checker_result_saved
                    or wiring_input.checker_result_detail_present
                ),
                http_post_executed=wiring_input.http_post_executed,
                order_endpoint_called=wiring_input.order_endpoint_called,
                live_order_once_called=wiring_input.live_order_once_called,
                post_allowed_this_step=wiring_input.post_allowed_this_step,
                post_executed=wiring_input.post_executed,
                retry_allowed=wiring_input.retry_allowed,
                loop_allowed=wiring_input.loop_allowed,
            ),
        )
    )
    credential_presence_checker_execution_contract_result = (
        build_live_order_real_credential_presence_checker_execution_contract(
            input_snapshot=LiveOrderRealCredentialPresenceCheckerExecutionContractInput(
                execution_contract_mode=wiring_input.checker_execution_contract_mode,
                checker_implementation_skeleton_ready=(
                    credential_presence_checker_implementation_result
                    .checker_implementation_skeleton_ready
                    and wiring_input.checker_execution_contract_ready
                ),
                operator_checker_workflow_ready=(
                    operator_checker_workflow_result.operator_checker_workflow_ready
                ),
                checker_contract_ready=(
                    credential_presence_checker_contract_result
                    .credential_presence_checker_contract_ready
                ),
                execution_contract_declared=wiring_input.execution_contract_declared,
                execution_inputs_declared=wiring_input.execution_inputs_declared,
                execution_outputs_declared=wiring_input.execution_outputs_declared,
                execution_stop_conditions_declared=(
                    wiring_input.execution_stop_conditions_declared
                ),
                execution_deferred_to_future_step=(
                    wiring_input.execution_deferred_to_future_step
                ),
                execution_performed=wiring_input.execution_performed,
                execution_performed_by_codex=(
                    wiring_input.execution_performed_by_codex
                ),
                execution_performed_by_operator=(
                    wiring_input.execution_performed_by_operator
                ),
                codex_env_access_requested=wiring_input.codex_env_access_requested,
                actual_environment_presence_check_performed=(
                    wiring_input.actual_environment_presence_check_performed
                ),
                credential_read_performed=wiring_input.credential_read_performed,
                credential_values_present=(
                    wiring_input.credential_values_provided
                    or wiring_input.credential_values_loaded
                    or wiring_input.credential_values_available
                    or wiring_input.credential_values_read
                ),
                credential_metadata_present=(
                    wiring_input.credential_metadata_exposed
                    or wiring_input.credential_injection_metadata_available
                    or wiring_input.credential_metadata_available
                ),
                checker_result_available=wiring_input.checker_result_available,
                checker_result_is_boolean_only=(
                    wiring_input.checker_result_is_boolean_only
                ),
                checker_result_detail_present=(
                    wiring_input.checker_result_detail_present
                ),
                checker_result_unknown=wiring_input.checker_result_unknown,
                checker_result_failed=wiring_input.checker_result_failed,
                checker_result_unavailable=wiring_input.checker_result_unavailable,
                checker_result_stale=wiring_input.checker_result_stale,
                checker_result_timeout=wiring_input.checker_result_timeout,
                checker_result_saved=wiring_input.checker_result_saved,
                checker_result_displayed=wiring_input.checker_result_displayed,
                checker_result_broadly_propagated=(
                    wiring_input.checker_result_broadly_propagated
                ),
                operator_workflow_preserved=wiring_input.operator_workflow_preserved,
                can_generate_real_signature=False,
                can_generate_real_headers=False,
                can_execute_http_post=False,
                http_post_executed=wiring_input.http_post_executed,
                order_endpoint_called=wiring_input.order_endpoint_called,
                live_order_once_called=wiring_input.live_order_once_called,
                post_allowed_this_step=wiring_input.post_allowed_this_step,
                post_executed=wiring_input.post_executed,
                safe_to_render=not (
                    wiring_input.checker_result_displayed
                    or wiring_input.checker_result_detail_present
                ),
                safe_to_serialize=not (
                    wiring_input.checker_result_saved
                    or wiring_input.checker_result_detail_present
                ),
                retry_allowed=wiring_input.retry_allowed,
                loop_allowed=wiring_input.loop_allowed,
            ),
        )
    )
    credential_presence_checker_execution_implementation_result = (
        build_live_order_real_credential_presence_checker_execution_implementation(
            input_snapshot=(
                LiveOrderRealCredentialPresenceCheckerExecutionImplementationInput(
                    execution_implementation_mode=(
                        wiring_input.checker_execution_implementation_mode
                    ),
                    checker_execution_contract_ready=(
                        credential_presence_checker_execution_contract_result
                        .checker_execution_contract_ready
                        and wiring_input.checker_execution_implementation_skeleton_ready
                    ),
                    checker_implementation_skeleton_ready=(
                        credential_presence_checker_implementation_result
                        .checker_implementation_skeleton_ready
                    ),
                    operator_result_handoff_safe=(
                        operator_checker_workflow_result.operator_result_handoff_safe
                        and wiring_input.operator_result_handoff_safe
                    ),
                    operator_checker_workflow_ready=(
                        operator_checker_workflow_result.operator_checker_workflow_ready
                    ),
                    execution_implementation_declared=(
                        wiring_input.execution_implementation_declared
                    ),
                    execution_interface_declared=(
                        wiring_input.execution_interface_declared
                    ),
                    execution_lifecycle_declared=(
                        wiring_input.execution_lifecycle_declared
                    ),
                    execution_result_mapping_declared=(
                        wiring_input.execution_result_mapping_declared
                    ),
                    execution_stop_conditions_declared=(
                        wiring_input.execution_stop_conditions_declared
                    ),
                    execution_deferred_to_future_step=(
                        wiring_input.execution_deferred_to_future_step
                    ),
                    execution_performed=wiring_input.execution_performed,
                    execution_performed_by_codex=(
                        wiring_input.execution_performed_by_codex
                    ),
                    execution_performed_by_operator=(
                        wiring_input.execution_performed_by_operator
                    ),
                    env_access_requested=wiring_input.env_access_requested,
                    codex_env_access_requested=wiring_input.codex_env_access_requested,
                    actual_environment_presence_check_performed=(
                        wiring_input.actual_environment_presence_check_performed
                    ),
                    credential_read_performed=wiring_input.credential_read_performed,
                    credential_values_present=(
                        wiring_input.credential_values_provided
                        or wiring_input.credential_values_loaded
                        or wiring_input.credential_values_available
                        or wiring_input.credential_values_read
                    ),
                    credential_metadata_present=(
                        wiring_input.credential_metadata_exposed
                        or wiring_input.credential_injection_metadata_available
                        or wiring_input.credential_metadata_available
                    ),
                    checker_result_available=wiring_input.checker_result_available,
                    checker_result_detail_present=(
                        wiring_input.checker_result_detail_present
                    ),
                    checker_result_unknown=wiring_input.checker_result_unknown,
                    checker_result_failed=wiring_input.checker_result_failed,
                    checker_result_unavailable=wiring_input.checker_result_unavailable,
                    checker_result_stale=wiring_input.checker_result_stale,
                    checker_result_timeout=wiring_input.checker_result_timeout,
                    checker_result_saved=wiring_input.checker_result_saved,
                    checker_result_displayed=wiring_input.checker_result_displayed,
                    operator_result_detail_present=(
                        wiring_input.operator_result_detail_present
                    ),
                    operator_result_raw_value_present=(
                        wiring_input.operator_result_raw_value_present
                    ),
                    operator_result_reused=wiring_input.operator_result_reused,
                    operator_result_previous_turn=(
                        wiring_input.operator_result_previous_turn
                    ),
                    operator_result_timeout=wiring_input.operator_result_timeout,
                    can_generate_real_signature=False,
                    can_generate_real_headers=False,
                    can_execute_http_post=False,
                    http_post_executed=wiring_input.http_post_executed,
                    order_endpoint_called=wiring_input.order_endpoint_called,
                    live_order_once_called=wiring_input.live_order_once_called,
                    post_allowed_this_step=wiring_input.post_allowed_this_step,
                    post_executed=wiring_input.post_executed,
                    safe_to_render=not (
                        wiring_input.checker_result_displayed
                        or wiring_input.checker_result_detail_present
                        or wiring_input.operator_result_detail_present
                        or wiring_input.operator_result_raw_value_present
                    ),
                    safe_to_serialize=not (
                        wiring_input.checker_result_saved
                        or wiring_input.checker_result_detail_present
                        or wiring_input.operator_result_detail_present
                        or wiring_input.operator_result_raw_value_present
                    ),
                    retry_allowed=wiring_input.retry_allowed,
                    loop_allowed=wiring_input.loop_allowed,
                )
            ),
        )
    )
    operator_executed_execution_boundary_result = (
        build_live_order_real_operator_executed_execution_boundary(
            input_snapshot=LiveOrderRealOperatorExecutedExecutionBoundaryInput(
                boundary_mode=wiring_input.operator_execution_boundary_mode,
                boundary_declared=(
                    wiring_input.operator_executed_execution_boundary_ready
                ),
                operator_execution_boundary_declared=(
                    wiring_input.operator_execution_boundary_declared
                ),
                operator_execution_must_be_outside_codex=(
                    wiring_input.operator_execution_must_be_outside_codex
                ),
                codex_execution_forbidden=wiring_input.codex_execution_forbidden,
                checker_execution_implementation_skeleton_ready=(
                    credential_presence_checker_execution_implementation_result
                    .checker_execution_implementation_skeleton_ready
                ),
                checker_execution_contract_ready=(
                    credential_presence_checker_execution_contract_result
                    .checker_execution_contract_ready
                ),
                operator_result_handoff_safe=(
                    operator_checker_workflow_result.operator_result_handoff_safe
                    and wiring_input.operator_result_handoff_safe
                ),
                operator_checker_workflow_ready=(
                    operator_checker_workflow_result.operator_checker_workflow_ready
                ),
                operator_execution_performed=(
                    wiring_input.operator_execution_performed
                ),
                codex_execution_performed=wiring_input.codex_execution_performed,
                env_access_requested=wiring_input.env_access_requested,
                codex_env_access_requested=wiring_input.codex_env_access_requested,
                actual_environment_presence_check_performed=(
                    wiring_input.actual_environment_presence_check_performed
                ),
                credential_read_performed=wiring_input.credential_read_performed,
                credential_values_present=(
                    wiring_input.credential_values_provided
                    or wiring_input.credential_values_loaded
                    or wiring_input.credential_values_available
                    or wiring_input.credential_values_read
                ),
                credential_metadata_present=(
                    wiring_input.credential_metadata_exposed
                    or wiring_input.credential_injection_metadata_available
                    or wiring_input.credential_metadata_available
                ),
                operator_result_provided=False,
                operator_result_safe_boolean_category_only=(
                    wiring_input.operator_result_category_only
                    and wiring_input.operator_result_is_boolean_only
                ),
                operator_result_detail_present=(
                    wiring_input.operator_result_detail_present
                ),
                operator_result_raw_value_present=(
                    wiring_input.operator_result_raw_value_present
                ),
                operator_result_unknown=wiring_input.operator_result_unknown,
                operator_result_failed=wiring_input.operator_result_failed,
                operator_result_unavailable=wiring_input.operator_result_unavailable,
                operator_result_stale=wiring_input.operator_result_stale,
                operator_result_timeout=wiring_input.operator_result_timeout,
                operator_result_reused=wiring_input.operator_result_reused,
                operator_result_previous_turn=(
                    wiring_input.operator_result_previous_turn
                ),
                operator_result_saved=wiring_input.operator_result_saved,
                operator_result_displayed=wiring_input.operator_result_displayed,
                operator_result_broadly_propagated=(
                    wiring_input.operator_result_broadly_propagated
                ),
                checker_result_detail_present=(
                    wiring_input.checker_result_detail_present
                ),
                env_variable_names_present=wiring_input.env_variable_names_present,
                sentinel_value_present=wiring_input.sentinel_value_present,
                can_generate_real_signature=False,
                can_generate_real_headers=False,
                can_execute_http_post=False,
                http_post_executed=wiring_input.http_post_executed,
                order_endpoint_called=wiring_input.order_endpoint_called,
                live_order_once_called=wiring_input.live_order_once_called,
                post_allowed_this_step=wiring_input.post_allowed_this_step,
                post_executed=wiring_input.post_executed,
                safe_to_render=not (
                    wiring_input.operator_result_displayed
                    or wiring_input.operator_result_detail_present
                    or wiring_input.operator_result_raw_value_present
                    or wiring_input.checker_result_detail_present
                    or wiring_input.env_variable_names_present
                    or wiring_input.sentinel_value_present
                ),
                safe_to_serialize=not (
                    wiring_input.operator_result_saved
                    or wiring_input.operator_result_detail_present
                    or wiring_input.operator_result_raw_value_present
                    or wiring_input.checker_result_detail_present
                    or wiring_input.env_variable_names_present
                    or wiring_input.sentinel_value_present
                ),
                retry_allowed=wiring_input.retry_allowed,
                loop_allowed=wiring_input.loop_allowed,
            ),
        )
    )
    category_value = wiring_input.operator_result_category
    category_ready_confirmed = (
        category_value == LiveOrderRealOperatorExecutionResultCategory.READY_CONFIRMED.value
    )
    category_blocked = category_value.startswith("BLOCKED_")
    operator_execution_result_category_contract_result = (
        build_live_order_real_operator_execution_result_category_contract(
            input_snapshot=LiveOrderRealOperatorExecutionResultCategoryContractInput(
                category_contract_mode=(
                    wiring_input.operator_execution_result_category_contract_mode
                ),
                category_contract_declared=(
                    wiring_input.operator_execution_result_category_contract_ready
                    and wiring_input.category_contract_declared
                ),
                allowed_category_set_declared=wiring_input.allowed_category_set_declared,
                operator_executed_execution_boundary_ready=(
                    operator_executed_execution_boundary_result
                    .operator_executed_execution_boundary_ready
                    and wiring_input.operator_executed_execution_boundary_ready
                ),
                operator_result_handoff_safe=(
                    operator_checker_workflow_result.operator_result_handoff_safe
                    and wiring_input.operator_result_handoff_safe
                ),
                operator_checker_workflow_ready=(
                    operator_checker_workflow_result.operator_checker_workflow_ready
                ),
                operator_result_category=category_value,
                operator_result_category_is_safe_label=(
                    wiring_input.operator_result_category_is_safe_label
                ),
                operator_result_category_is_allowed=(
                    wiring_input.operator_result_category_is_allowed
                ),
                operator_result_provided=category_ready_confirmed or category_blocked,
                operator_result_ready_confirmed=category_ready_confirmed,
                operator_result_blocked=category_blocked,
                operator_result_unknown=wiring_input.operator_result_unknown,
                operator_result_failed=wiring_input.operator_result_failed,
                operator_result_unavailable=wiring_input.operator_result_unavailable,
                operator_result_stale=wiring_input.operator_result_stale,
                operator_result_timeout=wiring_input.operator_result_timeout,
                operator_result_reused=wiring_input.operator_result_reused,
                operator_result_previous_turn=(
                    wiring_input.operator_result_previous_turn
                ),
                operator_result_detail_present=(
                    wiring_input.operator_result_detail_present
                ),
                operator_result_raw_value_present=(
                    wiring_input.operator_result_raw_value_present
                ),
                operator_result_saved=wiring_input.operator_result_saved,
                operator_result_displayed=wiring_input.operator_result_displayed,
                operator_result_broadly_propagated=(
                    wiring_input.operator_result_broadly_propagated
                ),
                checker_result_detail_present=(
                    wiring_input.checker_result_detail_present
                ),
                env_variable_names_present=wiring_input.env_variable_names_present,
                credential_values_present=(
                    wiring_input.credential_values_provided
                    or wiring_input.credential_values_loaded
                    or wiring_input.credential_values_available
                    or wiring_input.credential_values_read
                ),
                credential_metadata_present=(
                    wiring_input.credential_metadata_exposed
                    or wiring_input.credential_injection_metadata_available
                    or wiring_input.credential_metadata_available
                ),
                sentinel_value_present=wiring_input.sentinel_value_present,
                actual_execution_performed=(
                    wiring_input.actual_execution_performed
                    or wiring_input.operator_execution_performed
                    or wiring_input.execution_performed
                    or wiring_input.execution_performed_by_operator
                ),
                codex_execution_performed=(
                    wiring_input.codex_execution_performed
                    or wiring_input.execution_performed_by_codex
                ),
                env_access_requested=(
                    wiring_input.env_access_requested
                    or wiring_input.codex_env_access_requested
                ),
                credential_read_performed=wiring_input.credential_read_performed,
                can_generate_real_signature=False,
                can_generate_real_headers=False,
                can_execute_http_post=False,
                http_post_executed=wiring_input.http_post_executed,
                order_endpoint_called=wiring_input.order_endpoint_called,
                live_order_once_called=wiring_input.live_order_once_called,
                post_allowed_this_step=wiring_input.post_allowed_this_step,
                post_executed=wiring_input.post_executed,
                safe_to_render=not (
                    wiring_input.operator_result_displayed
                    or wiring_input.operator_result_detail_present
                    or wiring_input.operator_result_raw_value_present
                    or wiring_input.checker_result_detail_present
                    or wiring_input.env_variable_names_present
                    or wiring_input.sentinel_value_present
                ),
                safe_to_serialize=not (
                    wiring_input.operator_result_saved
                    or wiring_input.operator_result_detail_present
                    or wiring_input.operator_result_raw_value_present
                    or wiring_input.checker_result_detail_present
                    or wiring_input.env_variable_names_present
                    or wiring_input.sentinel_value_present
                ),
            ),
        )
    )
    receipt_ready_confirmed = (
        operator_execution_result_category_contract_result.operator_result_category
        == LiveOrderRealOperatorExecutionResultCategory.READY_CONFIRMED.value
    )
    operator_result_handoff_receipt_result = (
        build_live_order_real_operator_result_handoff_receipt(
            input_snapshot=LiveOrderRealOperatorResultHandoffReceiptInput(
                receipt_mode=wiring_input.operator_result_handoff_receipt_mode,
                receipt_contract_declared=(
                    wiring_input.operator_result_handoff_receipt_ready
                    and wiring_input.receipt_contract_declared
                ),
                receipt_boundary_declared=wiring_input.receipt_boundary_declared,
                receipt_one_time_required=wiring_input.receipt_one_time_required,
                receipt_fresh_required=wiring_input.receipt_fresh_required,
                receipt_non_reuse_required=wiring_input.receipt_non_reuse_required,
                receipt_non_raw_required=wiring_input.receipt_non_raw_required,
                receipt_non_detail_required=wiring_input.receipt_non_detail_required,
                operator_execution_result_category_contract_ready=(
                    operator_execution_result_category_contract_result
                    .operator_execution_result_category_contract_ready
                    and wiring_input.operator_execution_result_category_contract_ready
                ),
                operator_executed_execution_boundary_ready=(
                    operator_executed_execution_boundary_result
                    .operator_executed_execution_boundary_ready
                    and wiring_input.operator_executed_execution_boundary_ready
                ),
                operator_result_handoff_safe=(
                    operator_checker_workflow_result.operator_result_handoff_safe
                    and wiring_input.operator_result_handoff_safe
                ),
                operator_result_category=(
                    operator_execution_result_category_contract_result
                    .operator_result_category
                ),
                operator_result_category_is_safe_label=(
                    operator_execution_result_category_contract_result
                    .operator_result_category_is_safe_label
                ),
                operator_result_category_is_allowed=(
                    operator_execution_result_category_contract_result
                    .operator_result_category_is_allowed
                ),
                receipt_provided=receipt_ready_confirmed or wiring_input.receipt_provided,
                receipt_category_confirmed=(
                    receipt_ready_confirmed or wiring_input.receipt_category_confirmed
                ),
                receipt_current_turn=wiring_input.receipt_current_turn,
                receipt_fresh=wiring_input.receipt_fresh,
                receipt_stale=wiring_input.receipt_stale,
                receipt_reused=wiring_input.receipt_reused,
                receipt_previous_turn=wiring_input.receipt_previous_turn,
                receipt_expired=wiring_input.receipt_expired,
                receipt_timeout=wiring_input.receipt_timeout,
                receipt_unknown=wiring_input.receipt_unknown,
                receipt_failed=wiring_input.receipt_failed,
                receipt_unavailable=wiring_input.receipt_unavailable,
                receipt_raw_value_present=wiring_input.receipt_raw_value_present,
                receipt_detail_present=wiring_input.receipt_detail_present,
                receipt_id_present=wiring_input.receipt_id_present,
                receipt_token_present=wiring_input.receipt_token_present,
                receipt_nonce_present=wiring_input.receipt_nonce_present,
                receipt_hash_present=wiring_input.receipt_hash_present,
                receipt_fingerprint_present=wiring_input.receipt_fingerprint_present,
                receipt_length_present=wiring_input.receipt_length_present,
                receipt_saved=wiring_input.receipt_saved,
                receipt_displayed=wiring_input.receipt_displayed,
                receipt_broadly_propagated=(
                    wiring_input.receipt_broadly_propagated
                ),
                operator_result_detail_present=(
                    wiring_input.operator_result_detail_present
                ),
                operator_result_raw_value_present=(
                    wiring_input.operator_result_raw_value_present
                ),
                checker_result_detail_present=(
                    wiring_input.checker_result_detail_present
                ),
                env_variable_names_present=wiring_input.env_variable_names_present,
                credential_values_present=(
                    wiring_input.credential_values_provided
                    or wiring_input.credential_values_loaded
                    or wiring_input.credential_values_available
                    or wiring_input.credential_values_read
                ),
                credential_metadata_present=(
                    wiring_input.credential_metadata_exposed
                    or wiring_input.credential_injection_metadata_available
                    or wiring_input.credential_metadata_available
                ),
                sentinel_value_present=wiring_input.sentinel_value_present,
                actual_execution_performed=(
                    wiring_input.actual_execution_performed
                    or wiring_input.operator_execution_performed
                    or wiring_input.execution_performed
                    or wiring_input.execution_performed_by_operator
                ),
                codex_execution_performed=(
                    wiring_input.codex_execution_performed
                    or wiring_input.execution_performed_by_codex
                ),
                env_access_requested=(
                    wiring_input.env_access_requested
                    or wiring_input.codex_env_access_requested
                ),
                credential_read_performed=wiring_input.credential_read_performed,
                can_generate_real_signature=False,
                can_generate_real_headers=False,
                can_execute_http_post=False,
                http_post_executed=wiring_input.http_post_executed,
                order_endpoint_called=wiring_input.order_endpoint_called,
                live_order_once_called=wiring_input.live_order_once_called,
                post_allowed_this_step=wiring_input.post_allowed_this_step,
                post_executed=wiring_input.post_executed,
                safe_to_render=not (
                    wiring_input.receipt_displayed
                    or wiring_input.receipt_raw_value_present
                    or wiring_input.receipt_detail_present
                    or wiring_input.receipt_id_present
                    or wiring_input.receipt_token_present
                    or wiring_input.receipt_nonce_present
                    or wiring_input.receipt_hash_present
                    or wiring_input.receipt_fingerprint_present
                    or wiring_input.receipt_length_present
                    or wiring_input.operator_result_displayed
                    or wiring_input.operator_result_detail_present
                    or wiring_input.operator_result_raw_value_present
                    or wiring_input.checker_result_detail_present
                    or wiring_input.env_variable_names_present
                    or wiring_input.sentinel_value_present
                ),
                safe_to_serialize=not (
                    wiring_input.receipt_saved
                    or wiring_input.receipt_raw_value_present
                    or wiring_input.receipt_detail_present
                    or wiring_input.receipt_id_present
                    or wiring_input.receipt_token_present
                    or wiring_input.receipt_nonce_present
                    or wiring_input.receipt_hash_present
                    or wiring_input.receipt_fingerprint_present
                    or wiring_input.receipt_length_present
                    or wiring_input.operator_result_saved
                    or wiring_input.operator_result_detail_present
                    or wiring_input.operator_result_raw_value_present
                    or wiring_input.checker_result_detail_present
                    or wiring_input.env_variable_names_present
                    or wiring_input.sentinel_value_present
                ),
            ),
        )
    )
    return LiveOrderRealStep6GInternalWiringSnapshot(
        input_snapshot=wiring_input,
        pb_result=pb_result,
        eb_result=eb_result,
        ad_result=ad_result,
        ra_result=ra_result,
        tc_result=tc_result,
        st_signing_result=signing_result,
        st_private_transport_result=private_transport_result,
        dummy_signing_result=dummy_signing_result,
        http_transport_interface_result=http_transport_interface_result,
        credential_boundary_result=credential_boundary_result,
        credential_handle_result=credential_handle_result,
        credential_injection_result=credential_injection_result,
        credential_presence_check_result=credential_presence_check_result,
        credential_presence_adapter_result=credential_presence_adapter_result,
        credential_presence_checker_contract_result=(
            credential_presence_checker_contract_result
        ),
        operator_checker_workflow_result=operator_checker_workflow_result,
        credential_presence_checker_implementation_result=(
            credential_presence_checker_implementation_result
        ),
        credential_presence_checker_execution_contract_result=(
            credential_presence_checker_execution_contract_result
        ),
        credential_presence_checker_execution_implementation_result=(
            credential_presence_checker_execution_implementation_result
        ),
        operator_executed_execution_boundary_result=(
            operator_executed_execution_boundary_result
        ),
        operator_execution_result_category_contract_result=(
            operator_execution_result_category_contract_result
        ),
        operator_result_handoff_receipt_result=operator_result_handoff_receipt_result,
    )


def build_live_order_real_step6g_internal_wiring(
    *,
    input_snapshot: LiveOrderRealStep6GInternalWiringInput | None = None,
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot | None = None,
    created_at: datetime | None = None,
) -> LiveOrderRealStep6GInternalWiringResult:
    """Validate Step 6G PB/EB/AD/RA/TC/ST compatibility without live execution."""
    wiring_snapshot = snapshot or build_valid_step6g_internal_wiring_snapshot(
        input_snapshot=input_snapshot,
        created_at=created_at,
    )
    wiring_input = wiring_snapshot.input_snapshot
    credential_presence_checker_contract_result = (
        wiring_snapshot.credential_presence_checker_contract_result
    )
    operator_checker_workflow_result = (
        wiring_snapshot.operator_checker_workflow_result
    )
    credential_presence_checker_implementation_result = (
        wiring_snapshot.credential_presence_checker_implementation_result
    )
    credential_presence_checker_execution_contract_result = (
        wiring_snapshot.credential_presence_checker_execution_contract_result
    )
    credential_presence_checker_execution_implementation_result = (
        wiring_snapshot.credential_presence_checker_execution_implementation_result
    )
    operator_executed_execution_boundary_result = (
        wiring_snapshot.operator_executed_execution_boundary_result
    )
    operator_execution_result_category_contract_result = (
        wiring_snapshot.operator_execution_result_category_contract_result
    )
    operator_result_handoff_receipt_result = (
        wiring_snapshot.operator_result_handoff_receipt_result
    )
    order_reasons = _order_reasons(wiring_input)
    approval_reasons = _approval_reasons(wiring_input)
    preflight_reasons = _preflight_reasons(wiring_input)
    attempt_reasons = _attempt_reasons(wiring_input)
    route_reasons = _route_bridge_reasons(wiring_snapshot)
    runtime_reasons = _runtime_bridge_reasons(wiring_snapshot)
    controlled_reasons = _controlled_adapter_reasons(wiring_snapshot)
    real_adapter_reasons = _real_adapter_reasons(wiring_snapshot)
    tc_reasons = _transport_core_reasons(wiring_snapshot)
    signing_reasons = _signing_contract_reasons(wiring_snapshot)
    dummy_signing_reasons = _dummy_signing_reasons(wiring_snapshot)
    private_transport_reasons = _private_transport_reasons(wiring_snapshot)
    http_interface_reasons = _http_transport_interface_reasons(wiring_snapshot)
    credential_boundary_reasons = _credential_boundary_reasons(wiring_snapshot)
    credential_handle_reasons = _credential_handle_reasons(wiring_snapshot)
    credential_injection_reasons = _credential_injection_reasons(wiring_snapshot)
    credential_presence_check_reasons = _credential_presence_check_reasons(
        wiring_snapshot,
    )
    credential_presence_adapter_reasons = _credential_presence_adapter_reasons(
        wiring_snapshot,
    )
    credential_presence_checker_contract_reasons = (
        _credential_presence_checker_contract_reasons(wiring_snapshot)
    )
    operator_checker_workflow_reasons = _operator_checker_workflow_reasons(
        wiring_snapshot,
    )
    credential_presence_checker_implementation_reasons = (
        _credential_presence_checker_implementation_reasons(wiring_snapshot)
    )
    credential_presence_checker_execution_contract_reasons = (
        _credential_presence_checker_execution_contract_reasons(wiring_snapshot)
    )
    credential_presence_checker_execution_implementation_reasons = (
        _credential_presence_checker_execution_implementation_reasons(wiring_snapshot)
    )
    operator_executed_execution_boundary_reasons = (
        _operator_executed_execution_boundary_reasons(wiring_snapshot)
    )
    operator_execution_result_category_contract_reasons = (
        _operator_execution_result_category_contract_reasons(wiring_snapshot)
    )
    operator_result_handoff_receipt_reasons = (
        _operator_result_handoff_receipt_reasons(wiring_snapshot)
    )
    raw_reasons = _raw_or_secret_reasons(wiring_input)
    step4_reasons = _step4_reasons(wiring_input)
    unsupported_reasons = _unsupported_reasons(wiring_snapshot)

    if step4_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_STEP4_SPOOFING
        primary_reasons = step4_reasons
    elif raw_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE
        primary_reasons = raw_reasons
    elif order_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_ORDER_INTENT
        primary_reasons = order_reasons
    elif approval_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_APPROVAL
        primary_reasons = approval_reasons
    elif preflight_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_PREFLIGHT
        primary_reasons = preflight_reasons
    elif attempt_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_ATTEMPT_STATE
        primary_reasons = attempt_reasons
    elif route_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE
        primary_reasons = route_reasons
    elif runtime_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_RUNTIME_BRIDGE
        primary_reasons = runtime_reasons
    elif controlled_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_CONTROLLED_ADAPTER
        primary_reasons = controlled_reasons
    elif real_adapter_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_REAL_ADAPTER
        primary_reasons = real_adapter_reasons
    elif tc_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_TRANSPORT_CORE
        primary_reasons = tc_reasons
    elif (
        signing_reasons
        or dummy_signing_reasons
        or credential_boundary_reasons
        or credential_handle_reasons
        or credential_injection_reasons
        or credential_presence_check_reasons
        or credential_presence_adapter_reasons
        or credential_presence_checker_contract_reasons
        or operator_checker_workflow_reasons
        or credential_presence_checker_implementation_reasons
        or credential_presence_checker_execution_contract_reasons
        or credential_presence_checker_execution_implementation_reasons
        or operator_executed_execution_boundary_reasons
        or operator_execution_result_category_contract_reasons
        or operator_result_handoff_receipt_reasons
    ):
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
        primary_reasons = _merge_reasons(
            signing_reasons,
            dummy_signing_reasons,
            credential_boundary_reasons,
            credential_handle_reasons,
            credential_injection_reasons,
            credential_presence_check_reasons,
            credential_presence_adapter_reasons,
            credential_presence_checker_contract_reasons,
            operator_checker_workflow_reasons,
            credential_presence_checker_implementation_reasons,
            credential_presence_checker_execution_contract_reasons,
            credential_presence_checker_execution_implementation_reasons,
            operator_executed_execution_boundary_reasons,
            operator_execution_result_category_contract_reasons,
            operator_result_handoff_receipt_reasons,
        )
    elif private_transport_reasons or http_interface_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_PRIVATE_TRANSPORT
        primary_reasons = _merge_reasons(private_transport_reasons, http_interface_reasons)
    elif unsupported_reasons:
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_UNSUPPORTED
        primary_reasons = unsupported_reasons
    else:
        status = InternalWiringStatus.STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST
        primary_reasons = ()

    blocked_reasons = _merge_reasons(
        primary_reasons,
        step4_reasons,
        raw_reasons,
        order_reasons,
        approval_reasons,
        preflight_reasons,
        attempt_reasons,
        route_reasons,
        runtime_reasons,
        controlled_reasons,
        real_adapter_reasons,
        tc_reasons,
        signing_reasons,
        dummy_signing_reasons,
        credential_boundary_reasons,
        credential_handle_reasons,
        credential_injection_reasons,
        credential_presence_check_reasons,
        credential_presence_adapter_reasons,
        credential_presence_checker_contract_reasons,
        operator_checker_workflow_reasons,
        credential_presence_checker_implementation_reasons,
        credential_presence_checker_execution_contract_reasons,
        credential_presence_checker_execution_implementation_reasons,
        operator_executed_execution_boundary_reasons,
        operator_execution_result_category_contract_reasons,
        operator_result_handoff_receipt_reasons,
        private_transport_reasons,
        http_interface_reasons,
        unsupported_reasons,
    )
    ready = status is InternalWiringStatus.STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST
    result_snapshot = replace(
        wiring_snapshot,
        input_snapshot=replace(
            wiring_snapshot.input_snapshot,
            checker_contract_mode=(
                credential_presence_checker_contract_result.checker_contract_mode
            ),
            operator_checker_workflow_mode=(
                operator_checker_workflow_result.workflow_mode
            ),
            checker_implementation_mode=(
                credential_presence_checker_implementation_result.implementation_mode
            ),
            checker_execution_contract_mode=(
                credential_presence_checker_execution_contract_result
                .execution_contract_mode
            ),
            checker_execution_implementation_mode=(
                credential_presence_checker_execution_implementation_result
                .execution_implementation_mode
            ),
            operator_execution_boundary_mode=(
                operator_executed_execution_boundary_result.boundary_mode
            ),
            operator_execution_result_category_contract_mode=(
                operator_execution_result_category_contract_result
                .category_contract_mode
            ),
            operator_result_category=(
                operator_execution_result_category_contract_result
                .operator_result_category
            ),
            operator_result_handoff_receipt_mode=(
                operator_result_handoff_receipt_result.receipt_mode
            ),
        ),
    )
    return LiveOrderRealStep6GInternalWiringResult(
        status=status,
        internal_wiring_ready=ready,
        pb_ready=not route_reasons,
        eb_ready=not runtime_reasons,
        ad_ready=not controlled_reasons,
        ra_ready=not real_adapter_reasons,
        tc_ready=not tc_reasons,
        st_signing_ready=not _merge_reasons(
            signing_reasons,
            dummy_signing_reasons,
            credential_boundary_reasons,
            credential_handle_reasons,
            credential_injection_reasons,
            credential_presence_check_reasons,
            credential_presence_adapter_reasons,
            credential_presence_checker_contract_reasons,
            operator_checker_workflow_reasons,
            credential_presence_checker_implementation_reasons,
            credential_presence_checker_execution_contract_reasons,
            credential_presence_checker_execution_implementation_reasons,
            operator_executed_execution_boundary_reasons,
            operator_execution_result_category_contract_reasons,
            operator_result_handoff_receipt_reasons,
        ),
        st_private_transport_ready=not _merge_reasons(
            private_transport_reasons,
            http_interface_reasons,
        ),
        dummy_signing_ready=not dummy_signing_reasons,
        dummy_signature_check_passed=(
            wiring_snapshot.dummy_signing_result.dummy_signature_check_passed
        ),
        dummy_signature_value_present=False,
        dummy_signature_value_displayed=False,
        dummy_signature_value_saved=False,
        http_transport_interface_ready=not http_interface_reasons,
        http_transport_interface_mode=wiring_input.http_transport_interface_mode,
        http_client_present=False,
        can_execute_http_post=False,
        can_call_order_endpoint=False,
        can_call_live_order_once=False,
        credential_boundary_ready=not credential_boundary_reasons,
        credential_boundary_mode=wiring_input.credential_boundary_mode,
        credential_handle_ready=not credential_handle_reasons,
        credential_handle_mode=wiring_input.credential_handle_mode,
        handle_requested=wiring_input.handle_requested,
        handle_created=False,
        handle_contains_value=False,
        handle_contains_identifier=False,
        handle_metadata_exposed=False,
        credential_injection_ready=not credential_injection_reasons,
        credential_injection_mode=wiring_input.credential_injection_mode,
        injection_requested=wiring_input.injection_requested,
        injection_performed=False,
        real_credential_values_available=False,
        real_credential_values_injected=False,
        credential_injection_metadata_available=False,
        credential_presence_check_ready=not credential_presence_check_reasons,
        presence_check_mode=wiring_input.presence_check_mode,
        operator_assertion_provided=wiring_input.operator_assertion_provided,
        operator_assertion_is_boolean_only=(
            wiring_input.operator_assertion_is_boolean_only
        ),
        operator_sentinel_received=wiring_input.operator_sentinel_received,
        operator_sentinel_fresh=wiring_input.operator_sentinel_fresh,
        operator_sentinel_reused=False,
        operator_sentinel_stale=False,
        operator_sentinel_previous_turn=False,
        sentinel_value_present=False,
        sentinel_value_displayed=False,
        sentinel_value_saved=False,
        sentinel_hash_available=False,
        sentinel_fingerprint_available=False,
        sentinel_length_available=False,
        presence_result_broadly_propagated=False,
        presence_result_saved=False,
        credential_presence_adapter_ready=not credential_presence_adapter_reasons,
        presence_adapter_mode=wiring_input.presence_adapter_mode,
        operator_provided_presence_result=wiring_input.operator_provided_presence_result,
        operator_presence_result_is_boolean_only=(
            wiring_input.operator_presence_result_is_boolean_only
        ),
        operator_presence_result_fresh=wiring_input.operator_presence_result_fresh,
        operator_presence_result_reused=False,
        operator_presence_result_stale=False,
        operator_presence_result_previous_turn=False,
        presence_result_adapted=wiring_input.presence_result_adapted,
        presence_result_displayed=False,
        actual_environment_presence_check_performed=False,
        real_checker_attached=False,
        real_checker_executed=False,
        credential_presence_checker_contract_ready=(
            not credential_presence_checker_contract_reasons
        ),
        checker_contract_mode=(
            credential_presence_checker_contract_result.checker_contract_mode
        ),
        checker_contract_requested=wiring_input.checker_contract_requested,
        checker_contract_ready_requested=(
            wiring_input.checker_contract_ready_requested
        ),
        real_checker_implementation_present=False,
        env_access_required=wiring_input.env_access_required,
        env_access_allowed=False,
        credential_values_available=False,
        credential_values_read=False,
        credential_values_displayed=False,
        credential_values_saved=False,
        credential_metadata_available=False,
        credential_metadata_displayed=False,
        credential_metadata_saved=False,
        checker_result_available=False,
        checker_result_is_boolean_only=wiring_input.checker_result_is_boolean_only,
        checker_result_saved=False,
        checker_result_displayed=False,
        checker_result_broadly_propagated=False,
        checker_result_unknown=False,
        checker_result_failed=False,
        operator_checker_workflow_ready=not operator_checker_workflow_reasons,
        operator_checker_workflow_mode=operator_checker_workflow_result.workflow_mode,
        operator_workflow_declared=wiring_input.operator_workflow_declared,
        operator_execution_required=wiring_input.operator_execution_required,
        operator_execution_performed_outside_codex=(
            wiring_input.operator_execution_performed_outside_codex
        ),
        codex_execution_performed=False,
        codex_env_access_requested=False,
        actual_environment_presence_check_performed_by_codex=False,
        operator_result_handoff_declared=(
            wiring_input.operator_result_handoff_declared
        ),
        operator_result_handoff_safe=wiring_input.operator_result_handoff_safe,
        operator_result_category_only=wiring_input.operator_result_category_only,
        operator_result_provided=wiring_input.operator_result_provided,
        operator_result_is_boolean_only=wiring_input.operator_result_is_boolean_only,
        operator_result_raw_value_present=False,
        operator_result_raw_value_saved=False,
        operator_result_raw_value_displayed=False,
        operator_result_fresh=wiring_input.operator_result_fresh,
        operator_result_stale=False,
        operator_result_reused=False,
        operator_result_previous_turn=False,
        operator_result_timeout=False,
        operator_result_unknown=False,
        operator_result_failed=False,
        operator_result_unavailable=False,
        operator_result_saved=False,
        operator_result_displayed=False,
        operator_result_broadly_propagated=False,
        operator_result_detail_present=False,
        env_variable_names_present=False,
        checker_result_detail_present=False,
        checker_implementation_skeleton_ready=(
            not credential_presence_checker_implementation_reasons
        ),
        checker_implementation_mode=(
            credential_presence_checker_implementation_result.implementation_mode
        ),
        checker_execution_contract_ready=(
            not credential_presence_checker_execution_contract_reasons
        ),
        checker_execution_contract_mode=(
            credential_presence_checker_execution_contract_result.execution_contract_mode
        ),
        checker_execution_implementation_skeleton_ready=(
            not credential_presence_checker_execution_implementation_reasons
        ),
        checker_execution_implementation_mode=(
            credential_presence_checker_execution_implementation_result
            .execution_implementation_mode
        ),
        operator_executed_execution_boundary_ready=(
            not operator_executed_execution_boundary_reasons
        ),
        operator_execution_boundary_mode=(
            operator_executed_execution_boundary_result.boundary_mode
        ),
        operator_execution_boundary_declared=(
            wiring_input.operator_execution_boundary_declared
        ),
        operator_execution_must_be_outside_codex=(
            wiring_input.operator_execution_must_be_outside_codex
        ),
        codex_execution_forbidden=wiring_input.codex_execution_forbidden,
        operator_execution_performed=False,
        operator_execution_result_category_contract_ready=(
            not operator_execution_result_category_contract_reasons
        ),
        operator_execution_result_category_contract_mode=(
            operator_execution_result_category_contract_result.category_contract_mode
        ),
        category_contract_declared=wiring_input.category_contract_declared,
        allowed_category_set_declared=wiring_input.allowed_category_set_declared,
        operator_result_category=(
            operator_execution_result_category_contract_result.operator_result_category
        ),
        operator_result_category_is_safe_label=(
            operator_execution_result_category_contract_result
            .operator_result_category_is_safe_label
        ),
        operator_result_category_is_allowed=(
            operator_execution_result_category_contract_result
            .operator_result_category_is_allowed
        ),
        operator_result_ready_confirmed=(
            operator_execution_result_category_contract_result
            .operator_result_ready_confirmed
        ),
        operator_result_blocked=(
            operator_execution_result_category_contract_result.operator_result_blocked
        ),
        operator_result_handoff_receipt_ready=(
            not operator_result_handoff_receipt_reasons
        ),
        operator_result_handoff_receipt_mode=(
            operator_result_handoff_receipt_result.receipt_mode
        ),
        receipt_contract_declared=(
            operator_result_handoff_receipt_result.receipt_contract_declared
        ),
        receipt_boundary_declared=(
            operator_result_handoff_receipt_result.receipt_boundary_declared
        ),
        receipt_one_time_required=(
            operator_result_handoff_receipt_result.receipt_one_time_required
        ),
        receipt_fresh_required=(
            operator_result_handoff_receipt_result.receipt_fresh_required
        ),
        receipt_non_reuse_required=(
            operator_result_handoff_receipt_result.receipt_non_reuse_required
        ),
        receipt_non_raw_required=(
            operator_result_handoff_receipt_result.receipt_non_raw_required
        ),
        receipt_non_detail_required=(
            operator_result_handoff_receipt_result.receipt_non_detail_required
        ),
        receipt_provided=operator_result_handoff_receipt_result.receipt_provided,
        receipt_category_confirmed=(
            operator_result_handoff_receipt_result.receipt_category_confirmed
        ),
        receipt_current_turn=(
            operator_result_handoff_receipt_result.receipt_current_turn
        ),
        receipt_fresh=operator_result_handoff_receipt_result.receipt_fresh,
        receipt_stale=False,
        receipt_reused=False,
        receipt_previous_turn=False,
        receipt_expired=False,
        receipt_timeout=False,
        receipt_unknown=False,
        receipt_failed=False,
        receipt_unavailable=False,
        receipt_raw_value_present=False,
        receipt_detail_present=False,
        receipt_id_present=False,
        receipt_token_present=False,
        receipt_nonce_present=False,
        receipt_hash_present=False,
        receipt_fingerprint_present=False,
        receipt_length_present=False,
        execution_contract_declared=wiring_input.execution_contract_declared,
        execution_inputs_declared=wiring_input.execution_inputs_declared,
        execution_outputs_declared=wiring_input.execution_outputs_declared,
        execution_stop_conditions_declared=(
            wiring_input.execution_stop_conditions_declared
        ),
        execution_implementation_declared=(
            wiring_input.execution_implementation_declared
        ),
        execution_interface_declared=wiring_input.execution_interface_declared,
        implementation_interface_declared=(
            wiring_input.implementation_interface_declared
        ),
        implementation_lifecycle_declared=(
            wiring_input.implementation_lifecycle_declared
        ),
        execution_lifecycle_declared=wiring_input.execution_lifecycle_declared,
        execution_result_mapping_declared=(
            wiring_input.execution_result_mapping_declared
        ),
        execution_deferred_to_future_step=(
            wiring_input.execution_deferred_to_future_step
        ),
        execution_performed=False,
        execution_performed_by_codex=False,
        execution_performed_by_operator=False,
        credential_read_performed=False,
        env_access_capability_present=False,
        credential_read_capability_present=False,
        checker_result_unavailable=False,
        checker_result_stale=False,
        checker_result_timeout=False,
        operator_workflow_supported=wiring_input.operator_workflow_supported,
        operator_workflow_preserved=wiring_input.operator_workflow_preserved,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        credential_values_provided=False,
        credential_values_loaded=False,
        credential_presence_checked_against_environment=False,
        env_access_requested=False,
        credential_metadata_exposed=False,
        signature_value_generated=False,
        header_values_present=False,
        allowed_for_live=False,
        post_allowed_this_step=False,
        post_executed=False,
        retry_allowed=False,
        loop_allowed=False,
        check_results=_build_check_results(result_snapshot),
        blocked_reasons=blocked_reasons,
        snapshot=result_snapshot,
        recommended_next_step=INTERNAL_WIRING_RECOMMENDED_NEXT_STEP
        if ready
        else "fix_step6g_internal_wiring_blockers_no_api_no_post",
    )


def render_live_order_real_step6g_internal_wiring_markdown(
    result: LiveOrderRealStep6GInternalWiringResult,
) -> str:
    """Render sanitized internal wiring metadata only."""
    input_snapshot = result.snapshot.input_snapshot
    lines = [
        "# Step 6G Internal Wiring Dry Run",
        "",
        "This internal wiring is fake/sanitized only.",
        "This internal wiring does not execute API calls.",
        "This internal wiring does not execute HTTP POST.",
        "This internal wiring does not call order endpoint.",
        "This internal wiring does not call live_order_once.",
        "This internal wiring does not use real credentials.",
        "This internal wiring does not generate real signatures.",
        "Future real execution requires a new final confirmation and fresh preflight.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- internal_wiring_ready: {_bool_text(result.internal_wiring_ready)}",
        f"- PB_ready: {_bool_text(result.pb_ready)}",
        f"- EB_ready: {_bool_text(result.eb_ready)}",
        f"- AD_ready: {_bool_text(result.ad_ready)}",
        f"- RA_ready: {_bool_text(result.ra_ready)}",
        f"- TC_ready: {_bool_text(result.tc_ready)}",
        f"- ST_signing_ready: {_bool_text(result.st_signing_ready)}",
        f"- ST_private_transport_ready: {_bool_text(result.st_private_transport_ready)}",
        f"- dummy_signing_ready: {_bool_text(result.dummy_signing_ready)}",
        (
            "- dummy_signature_check_passed: "
            f"{_bool_text(result.dummy_signature_check_passed)}"
        ),
        (
            "- http_transport_interface_ready: "
            f"{_bool_text(result.http_transport_interface_ready)}"
        ),
        f"- http_transport_interface_mode: {result.http_transport_interface_mode}",
        f"- credential_boundary_ready: {_bool_text(result.credential_boundary_ready)}",
        f"- credential_boundary_mode: {result.credential_boundary_mode}",
        f"- credential_handle_ready: {_bool_text(result.credential_handle_ready)}",
        f"- credential_handle_mode: {result.credential_handle_mode}",
        f"- credential_injection_ready: {_bool_text(result.credential_injection_ready)}",
        f"- credential_injection_mode: {result.credential_injection_mode}",
        (
            "- credential_presence_check_ready: "
            f"{_bool_text(result.credential_presence_check_ready)}"
        ),
        f"- presence_check_mode: {result.presence_check_mode}",
        (
            "- credential_presence_adapter_ready: "
            f"{_bool_text(result.credential_presence_adapter_ready)}"
        ),
        f"- presence_adapter_mode: {result.presence_adapter_mode}",
        (
            "- credential_presence_checker_contract_ready: "
            f"{_bool_text(result.credential_presence_checker_contract_ready)}"
        ),
        f"- checker_contract_mode: {result.checker_contract_mode}",
        (
            "- operator_checker_workflow_ready: "
            f"{_bool_text(result.operator_checker_workflow_ready)}"
        ),
        f"- operator_checker_workflow_mode: {result.operator_checker_workflow_mode}",
        (
            "- checker_implementation_skeleton_ready: "
            f"{_bool_text(result.checker_implementation_skeleton_ready)}"
        ),
        f"- checker_implementation_mode: {result.checker_implementation_mode}",
        (
            "- checker_execution_contract_ready: "
            f"{_bool_text(result.checker_execution_contract_ready)}"
        ),
        f"- checker_execution_contract_mode: {result.checker_execution_contract_mode}",
        (
            "- checker_execution_implementation_skeleton_ready: "
            f"{_bool_text(result.checker_execution_implementation_skeleton_ready)}"
        ),
        (
            "- checker_execution_implementation_mode: "
            f"{result.checker_execution_implementation_mode}"
        ),
        (
            "- operator_executed_execution_boundary_ready: "
            f"{_bool_text(result.operator_executed_execution_boundary_ready)}"
        ),
        (
            "- operator_execution_boundary_mode: "
            f"{result.operator_execution_boundary_mode}"
        ),
        (
            "- operator_execution_boundary_declared: "
            f"{_bool_text(result.operator_execution_boundary_declared)}"
        ),
        (
            "- operator_execution_must_be_outside_codex: "
            f"{_bool_text(result.operator_execution_must_be_outside_codex)}"
        ),
        f"- codex_execution_forbidden: {_bool_text(result.codex_execution_forbidden)}",
        (
            "- operator_execution_performed: "
            f"{_bool_text(result.operator_execution_performed)}"
        ),
        (
            "- operator_execution_result_category_contract_ready: "
            f"{_bool_text(result.operator_execution_result_category_contract_ready)}"
        ),
        (
            "- operator_execution_result_category_contract_mode: "
            f"{result.operator_execution_result_category_contract_mode}"
        ),
        (
            "- allowed_category_set_declared: "
            f"{_bool_text(result.allowed_category_set_declared)}"
        ),
        f"- operator_result_category: {result.operator_result_category}",
        (
            "- operator_result_category_is_safe_label: "
            f"{_bool_text(result.operator_result_category_is_safe_label)}"
        ),
        (
            "- operator_result_category_is_allowed: "
            f"{_bool_text(result.operator_result_category_is_allowed)}"
        ),
        (
            "- operator_result_ready_confirmed: "
            f"{_bool_text(result.operator_result_ready_confirmed)}"
        ),
        f"- operator_result_blocked: {_bool_text(result.operator_result_blocked)}",
        (
            "- operator_result_handoff_receipt_ready: "
            f"{_bool_text(result.operator_result_handoff_receipt_ready)}"
        ),
        (
            "- operator_result_handoff_receipt_mode: "
            f"{result.operator_result_handoff_receipt_mode}"
        ),
        (
            "- receipt_one_time_required: "
            f"{_bool_text(result.receipt_one_time_required)}"
        ),
        f"- receipt_fresh_required: {_bool_text(result.receipt_fresh_required)}",
        (
            "- receipt_non_reuse_required: "
            f"{_bool_text(result.receipt_non_reuse_required)}"
        ),
        f"- receipt_non_raw_required: {_bool_text(result.receipt_non_raw_required)}",
        (
            "- receipt_non_detail_required: "
            f"{_bool_text(result.receipt_non_detail_required)}"
        ),
        f"- receipt_provided: {_bool_text(result.receipt_provided)}",
        (
            "- receipt_category_confirmed: "
            f"{_bool_text(result.receipt_category_confirmed)}"
        ),
        f"- receipt_current_turn: {_bool_text(result.receipt_current_turn)}",
        f"- receipt_fresh: {_bool_text(result.receipt_fresh)}",
        f"- receipt_reused: {_bool_text(result.receipt_reused)}",
        f"- receipt_previous_turn: {_bool_text(result.receipt_previous_turn)}",
        f"- receipt_timeout: {_bool_text(result.receipt_timeout)}",
        f"- receipt_raw_value_present: {_bool_text(result.receipt_raw_value_present)}",
        f"- receipt_detail_present: {_bool_text(result.receipt_detail_present)}",
        "",
        "## Order Intent",
        f"- symbol: {input_snapshot.symbol}",
        f"- side: {input_snapshot.side}",
        f"- size: {input_snapshot.size}",
        f"- executionType: {input_snapshot.executionType}",
        f"- codex_inferred: {_bool_text(input_snapshot.codex_inferred)}",
        "",
        "## Approval",
        f"- approval_fingerprint: {input_snapshot.approval_fingerprint}",
        f"- sha256_prefix: {input_snapshot.sha256_prefix}",
        (
            "- final_confirmation_exact_match: "
            f"{_bool_text(input_snapshot.final_confirmation_exact_match)}"
        ),
        f"- final_confirmation_reused: {_bool_text(input_snapshot.final_confirmation_reused)}",
        "",
        "## Preflight",
        f"- market_session_state: {input_snapshot.market_session_state}",
        f"- open_positions_count: {input_snapshot.open_positions_count}",
        f"- active_orders_count: {input_snapshot.active_orders_count}",
        f"- ticker_symbol: {input_snapshot.ticker_symbol}",
        f"- ticker_spread_jpy: {input_snapshot.ticker_spread_jpy}",
        f"- ticker_age_seconds: {input_snapshot.ticker_age_seconds}",
        "",
        "## Safety",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- credential_values_provided: {_bool_text(result.credential_values_provided)}",
        f"- credential_values_loaded: {_bool_text(result.credential_values_loaded)}",
        (
            "- credential_presence_checked_against_environment: "
            f"{_bool_text(result.credential_presence_checked_against_environment)}"
        ),
        f"- env_access_requested: {_bool_text(result.env_access_requested)}",
        f"- credential_metadata_exposed: {_bool_text(result.credential_metadata_exposed)}",
        f"- handle_requested: {_bool_text(result.handle_requested)}",
        f"- handle_created: {_bool_text(result.handle_created)}",
        f"- handle_contains_value: {_bool_text(result.handle_contains_value)}",
        f"- handle_contains_identifier: {_bool_text(result.handle_contains_identifier)}",
        f"- handle_metadata_exposed: {_bool_text(result.handle_metadata_exposed)}",
        f"- injection_requested: {_bool_text(result.injection_requested)}",
        f"- injection_performed: {_bool_text(result.injection_performed)}",
        (
            "- real_credential_values_available: "
            f"{_bool_text(result.real_credential_values_available)}"
        ),
        (
            "- real_credential_values_injected: "
            f"{_bool_text(result.real_credential_values_injected)}"
        ),
        (
            "- credential_injection_metadata_available: "
            f"{_bool_text(result.credential_injection_metadata_available)}"
        ),
        (
            "- operator_assertion_provided: "
            f"{_bool_text(result.operator_assertion_provided)}"
        ),
        (
            "- operator_assertion_is_boolean_only: "
            f"{_bool_text(result.operator_assertion_is_boolean_only)}"
        ),
        f"- operator_sentinel_received: {_bool_text(result.operator_sentinel_received)}",
        f"- operator_sentinel_fresh: {_bool_text(result.operator_sentinel_fresh)}",
        f"- operator_sentinel_reused: {_bool_text(result.operator_sentinel_reused)}",
        f"- operator_sentinel_stale: {_bool_text(result.operator_sentinel_stale)}",
        (
            "- operator_sentinel_previous_turn: "
            f"{_bool_text(result.operator_sentinel_previous_turn)}"
        ),
        f"- sentinel_value_present: {_bool_text(result.sentinel_value_present)}",
        f"- sentinel_value_displayed: {_bool_text(result.sentinel_value_displayed)}",
        f"- sentinel_value_saved: {_bool_text(result.sentinel_value_saved)}",
        f"- sentinel_hash_available: {_bool_text(result.sentinel_hash_available)}",
        (
            "- sentinel_fingerprint_available: "
            f"{_bool_text(result.sentinel_fingerprint_available)}"
        ),
        f"- sentinel_length_available: {_bool_text(result.sentinel_length_available)}",
        (
            "- presence_result_broadly_propagated: "
            f"{_bool_text(result.presence_result_broadly_propagated)}"
        ),
        f"- presence_result_saved: {_bool_text(result.presence_result_saved)}",
        (
            "- operator_provided_presence_result: "
            f"{_bool_text(result.operator_provided_presence_result)}"
        ),
        (
            "- operator_presence_result_is_boolean_only: "
            f"{_bool_text(result.operator_presence_result_is_boolean_only)}"
        ),
        (
            "- operator_presence_result_fresh: "
            f"{_bool_text(result.operator_presence_result_fresh)}"
        ),
        (
            "- operator_presence_result_reused: "
            f"{_bool_text(result.operator_presence_result_reused)}"
        ),
        (
            "- operator_presence_result_stale: "
            f"{_bool_text(result.operator_presence_result_stale)}"
        ),
        (
            "- operator_presence_result_previous_turn: "
            f"{_bool_text(result.operator_presence_result_previous_turn)}"
        ),
        f"- presence_result_adapted: {_bool_text(result.presence_result_adapted)}",
        f"- presence_result_displayed: {_bool_text(result.presence_result_displayed)}",
        (
            "- actual_environment_presence_check_performed: "
            f"{_bool_text(result.actual_environment_presence_check_performed)}"
        ),
        f"- real_checker_attached: {_bool_text(result.real_checker_attached)}",
        f"- real_checker_executed: {_bool_text(result.real_checker_executed)}",
        (
            "- real_checker_implementation_present: "
            f"{_bool_text(result.real_checker_implementation_present)}"
        ),
        f"- env_access_required: {_bool_text(result.env_access_required)}",
        f"- env_access_allowed: {_bool_text(result.env_access_allowed)}",
        (
            "- credential_values_available: "
            f"{_bool_text(result.credential_values_available)}"
        ),
        f"- credential_values_read: {_bool_text(result.credential_values_read)}",
        (
            "- credential_metadata_available: "
            f"{_bool_text(result.credential_metadata_available)}"
        ),
        f"- checker_result_available: {_bool_text(result.checker_result_available)}",
        (
            "- checker_result_is_boolean_only: "
            f"{_bool_text(result.checker_result_is_boolean_only)}"
        ),
        f"- checker_result_saved: {_bool_text(result.checker_result_saved)}",
        f"- checker_result_displayed: {_bool_text(result.checker_result_displayed)}",
        (
            "- checker_result_broadly_propagated: "
            f"{_bool_text(result.checker_result_broadly_propagated)}"
        ),
        f"- checker_result_unknown: {_bool_text(result.checker_result_unknown)}",
        f"- checker_result_failed: {_bool_text(result.checker_result_failed)}",
        (
            "- operator_workflow_declared: "
            f"{_bool_text(result.operator_workflow_declared)}"
        ),
        (
            "- operator_execution_required: "
            f"{_bool_text(result.operator_execution_required)}"
        ),
        (
            "- operator_execution_performed_outside_codex: "
            f"{_bool_text(result.operator_execution_performed_outside_codex)}"
        ),
        (
            "- codex_execution_performed: "
            f"{_bool_text(result.codex_execution_performed)}"
        ),
        (
            "- codex_env_access_requested: "
            f"{_bool_text(result.codex_env_access_requested)}"
        ),
        (
            "- actual_environment_presence_check_performed_by_codex: "
            f"{_bool_text(result.actual_environment_presence_check_performed_by_codex)}"
        ),
        (
            "- operator_result_handoff_declared: "
            f"{_bool_text(result.operator_result_handoff_declared)}"
        ),
        (
            "- operator_result_handoff_safe: "
            f"{_bool_text(result.operator_result_handoff_safe)}"
        ),
        (
            "- operator_result_category_only: "
            f"{_bool_text(result.operator_result_category_only)}"
        ),
        (
            "- operator_result_provided: "
            f"{_bool_text(result.operator_result_provided)}"
        ),
        (
            "- operator_result_is_boolean_only: "
            f"{_bool_text(result.operator_result_is_boolean_only)}"
        ),
        (
            "- operator_result_raw_value_present: "
            f"{_bool_text(result.operator_result_raw_value_present)}"
        ),
        (
            "- operator_result_raw_value_saved: "
            f"{_bool_text(result.operator_result_raw_value_saved)}"
        ),
        (
            "- operator_result_raw_value_displayed: "
            f"{_bool_text(result.operator_result_raw_value_displayed)}"
        ),
        f"- operator_result_fresh: {_bool_text(result.operator_result_fresh)}",
        f"- operator_result_stale: {_bool_text(result.operator_result_stale)}",
        f"- operator_result_reused: {_bool_text(result.operator_result_reused)}",
        (
            "- operator_result_previous_turn: "
            f"{_bool_text(result.operator_result_previous_turn)}"
        ),
        f"- operator_result_timeout: {_bool_text(result.operator_result_timeout)}",
        f"- operator_result_unknown: {_bool_text(result.operator_result_unknown)}",
        f"- operator_result_failed: {_bool_text(result.operator_result_failed)}",
        (
            "- operator_result_unavailable: "
            f"{_bool_text(result.operator_result_unavailable)}"
        ),
        f"- operator_result_saved: {_bool_text(result.operator_result_saved)}",
        f"- operator_result_displayed: {_bool_text(result.operator_result_displayed)}",
        (
            "- operator_result_broadly_propagated: "
            f"{_bool_text(result.operator_result_broadly_propagated)}"
        ),
        (
            "- operator_result_detail_present: "
            f"{_bool_text(result.operator_result_detail_present)}"
        ),
        (
            "- env_variable_names_present: "
            f"{_bool_text(result.env_variable_names_present)}"
        ),
        (
            "- checker_result_detail_present: "
            f"{_bool_text(result.checker_result_detail_present)}"
        ),
        (
            "- implementation_interface_declared: "
            f"{_bool_text(result.implementation_interface_declared)}"
        ),
        (
            "- execution_implementation_declared: "
            f"{_bool_text(result.execution_implementation_declared)}"
        ),
        (
            "- execution_interface_declared: "
            f"{_bool_text(result.execution_interface_declared)}"
        ),
        (
            "- execution_contract_declared: "
            f"{_bool_text(result.execution_contract_declared)}"
        ),
        (
            "- execution_inputs_declared: "
            f"{_bool_text(result.execution_inputs_declared)}"
        ),
        (
            "- execution_outputs_declared: "
            f"{_bool_text(result.execution_outputs_declared)}"
        ),
        (
            "- execution_stop_conditions_declared: "
            f"{_bool_text(result.execution_stop_conditions_declared)}"
        ),
        (
            "- implementation_lifecycle_declared: "
            f"{_bool_text(result.implementation_lifecycle_declared)}"
        ),
        (
            "- execution_lifecycle_declared: "
            f"{_bool_text(result.execution_lifecycle_declared)}"
        ),
        (
            "- execution_result_mapping_declared: "
            f"{_bool_text(result.execution_result_mapping_declared)}"
        ),
        (
            "- execution_deferred_to_future_step: "
            f"{_bool_text(result.execution_deferred_to_future_step)}"
        ),
        f"- execution_performed: {_bool_text(result.execution_performed)}",
        (
            "- execution_performed_by_codex: "
            f"{_bool_text(result.execution_performed_by_codex)}"
        ),
        (
            "- execution_performed_by_operator: "
            f"{_bool_text(result.execution_performed_by_operator)}"
        ),
        f"- credential_read_performed: {_bool_text(result.credential_read_performed)}",
        (
            "- env_access_capability_present: "
            f"{_bool_text(result.env_access_capability_present)}"
        ),
        (
            "- credential_read_capability_present: "
            f"{_bool_text(result.credential_read_capability_present)}"
        ),
        (
            "- checker_result_unavailable: "
            f"{_bool_text(result.checker_result_unavailable)}"
        ),
        f"- checker_result_stale: {_bool_text(result.checker_result_stale)}",
        f"- checker_result_timeout: {_bool_text(result.checker_result_timeout)}",
        (
            "- operator_workflow_supported: "
            f"{_bool_text(result.operator_workflow_supported)}"
        ),
        (
            "- operator_workflow_preserved: "
            f"{_bool_text(result.operator_workflow_preserved)}"
        ),
        f"- signature_value_generated: {_bool_text(result.signature_value_generated)}",
        f"- header_values_present: {_bool_text(result.header_values_present)}",
        (
            "- dummy_signature_value_present: "
            f"{_bool_text(result.dummy_signature_value_present)}"
        ),
        f"- http_client_present: {_bool_text(result.http_client_present)}",
        f"- can_execute_http_post: {_bool_text(result.can_execute_http_post)}",
        f"- can_call_order_endpoint: {_bool_text(result.can_call_order_endpoint)}",
        f"- can_call_live_order_once: {_bool_text(result.can_call_live_order_once)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- retry_allowed: {_bool_text(result.retry_allowed)}",
        f"- loop_allowed: {_bool_text(result.loop_allowed)}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def _pb_order_intent(
    wiring_input: LiveOrderRealStep6GInternalWiringInput,
) -> LiveOrderRealStep6GOrderIntentSnapshot:
    return LiveOrderRealStep6GOrderIntentSnapshot(
        symbol=wiring_input.symbol,
        side=wiring_input.side,
        size=wiring_input.size,
        executionType=wiring_input.executionType,
        source_label="fake_sanitized_step6g_internal_wiring",
        codex_inferred_side=wiring_input.codex_inferred,
        codex_inferred_symbol=wiring_input.codex_inferred,
        codex_inferred_size=wiring_input.codex_inferred,
        codex_inferred_execution_type=wiring_input.codex_inferred,
    )


def _pb_approval(
    wiring_input: LiveOrderRealStep6GInternalWiringInput,
) -> LiveOrderRealStep6GApprovalSnapshot:
    return LiveOrderRealStep6GApprovalSnapshot(
        step6g_final_confirmation_received=wiring_input.final_confirmation_exact_match,
        step6g_final_confirmation_exact_match=wiring_input.final_confirmation_exact_match,
        final_confirmation_phrase_reused=wiring_input.final_confirmation_reused,
        approval_artifact_reestablished=wiring_input.approval_artifact_reestablished,
        approval_validation_passed=wiring_input.approval_validation_passed,
        approval_exact_match_ready=wiring_input.approval_exact_match_ready,
        approval_command_fingerprint=wiring_input.approval_fingerprint,
        approval_sha256_prefix=wiring_input.sha256_prefix,
        approval_command_displayed=wiring_input.approval_command_displayed,
        approval_command_saved=wiring_input.approval_command_saved,
        approval_command_copyable=False,
        approval_command_pbcopy=False,
        step4_approval_phrase_used=wiring_input.step4_spoofing,
        step4_approval_phrase_spoofed=wiring_input.step4_spoofing,
        step4_approval_gate_reused_as_step6g=wiring_input.step4_spoofing,
        approval_command_full_text_present=wiring_input.approval_command_full_text_present,
    )


def _pb_preflight(
    wiring_input: LiveOrderRealStep6GInternalWiringInput,
) -> LiveOrderRealStep6GPreflightSnapshot:
    return LiveOrderRealStep6GPreflightSnapshot(
        final_confirmation_preflight_passed=wiring_input.final_confirmation_preflight_passed,
        post_immediate_preflight_passed=wiring_input.post_immediate_preflight_passed,
        market_session_state=wiring_input.market_session_state,
        market_window_allowed=wiring_input.market_window_allowed,
        broker_maintenance_active=wiring_input.broker_maintenance_active,
        holiday_or_special_close=wiring_input.holiday_or_special_close,
        market_hours_unknown=wiring_input.market_hours_unknown,
        open_positions_count=wiring_input.open_positions_count,
        active_orders_count=wiring_input.active_orders_count,
        ticker_symbol=wiring_input.ticker_symbol,
        ticker_spread_jpy=wiring_input.ticker_spread_jpy,
        ticker_age_seconds=wiring_input.ticker_age_seconds,
        ticker_check_passed=wiring_input.ticker_check_passed,
        permission_scope_check_passed=wiring_input.permission_scope_check_passed,
        ip_account_binding_check_passed=wiring_input.ip_account_binding_check_passed,
        previous_result_unknown_check_passed=(
            wiring_input.previous_result_unknown_check_passed
        ),
        raw_request_saved=wiring_input.raw_request_saved,
        raw_request_displayed=wiring_input.raw_request_displayed,
        raw_response_saved=wiring_input.raw_response_saved,
        raw_response_displayed=wiring_input.raw_response_displayed,
        headers_saved=wiring_input.headers_saved,
        headers_displayed=wiring_input.headers_displayed,
        signature_saved=wiring_input.signature_saved,
        signature_displayed=wiring_input.signature_displayed,
        credentials_displayed=wiring_input.credentials_displayed,
        order_ids_displayed=wiring_input.real_ids_displayed,
        execution_ids_displayed=wiring_input.real_ids_displayed,
        position_ids_displayed=wiring_input.real_ids_displayed,
        client_order_ids_displayed=wiring_input.real_ids_displayed,
    )


def _pb_attempt(
    wiring_input: LiveOrderRealStep6GInternalWiringInput,
) -> LiveOrderRealStep6GAttemptState:
    return LiveOrderRealStep6GAttemptState(
        post_attempt_limit=wiring_input.post_attempt_limit,
        post_attempt_count_before=wiring_input.post_attempt_count_before,
        post_attempt_count_after=0,
        post_executed=wiring_input.post_executed,
        post_allowed_this_step=wiring_input.post_allowed_this_step,
        allowed_for_live_before=False,
        allowed_for_live_persisted=wiring_input.allowed_for_live,
        allowed_for_live_after=False,
        retry_allowed=wiring_input.retry_allowed,
        loop_allowed=wiring_input.loop_allowed,
        add_order_allowed=wiring_input.add_order_allowed,
        change_order_allowed=wiring_input.change_order_allowed,
        cancel_order_allowed=wiring_input.cancel_order_allowed,
        close_order_allowed=wiring_input.close_order_allowed,
    )


def _pb_route(
    wiring_input: LiveOrderRealStep6GInternalWiringInput,
) -> LiveOrderRealStep6GRouteContractSnapshot:
    return LiveOrderRealStep6GRouteContractSnapshot(
        route_contract_name="step6g_internal_wiring_fake_sanitized_chain",
        route_contract_kind="internal_wiring_no_api_no_post",
        uses_step4_approval_phrase=wiring_input.step4_spoofing,
        spoofs_step4_approval_phrase=wiring_input.step4_spoofing,
        mutates_step4_ledger_state=wiring_input.ledger_changed,
        requires_step4_prepared_ledger=False,
        uses_step6g_dedicated_attempt_state=True,
        calls_live_order_once_directly=wiring_input.live_order_once_called,
        imports_live_order_once=False,
        imports_broker=False,
        imports_private_api=False,
        creates_new_order_endpoint=False,
        creates_new_payload_builder=False,
        order_endpoint_called=wiring_input.order_endpoint_called,
        order_payload_generated=False,
        order_payload_sent=False,
        http_post_executed=wiring_input.http_post_executed,
        raw_request_displayed=wiring_input.raw_request_displayed,
        raw_response_displayed=wiring_input.raw_response_displayed,
        headers_displayed=wiring_input.headers_displayed,
        signature_displayed=wiring_input.signature_displayed,
        credentials_displayed=wiring_input.credentials_displayed,
        real_ids_displayed=wiring_input.real_ids_displayed,
        retry_on_unknown=wiring_input.retry_allowed,
        retry_on_timeout=wiring_input.retry_allowed,
        retry_on_reject=wiring_input.retry_allowed,
        explicit_safe_adapter_contract=True,
    )


def _tc_intent(
    wiring_input: LiveOrderRealStep6GInternalWiringInput,
) -> LiveOrderRealValidatedOrderIntent:
    return LiveOrderRealValidatedOrderIntent(
        symbol=wiring_input.symbol,
        side=wiring_input.side,
        size=wiring_input.size,
        executionType=wiring_input.executionType,
        source_label="fake_sanitized_step6g_internal_wiring",
        codex_inferred_symbol=wiring_input.codex_inferred,
        codex_inferred_side=wiring_input.codex_inferred,
        codex_inferred_size=wiring_input.codex_inferred,
        codex_inferred_execution_type=wiring_input.codex_inferred,
        retry_allowed=wiring_input.retry_allowed,
        loop_allowed=wiring_input.loop_allowed,
        add_order_allowed=wiring_input.add_order_allowed,
        change_order_allowed=wiring_input.change_order_allowed,
        cancel_order_allowed=wiring_input.cancel_order_allowed,
        close_order_allowed=wiring_input.close_order_allowed,
        extra_fields=(),
    )


def _order_reasons(wiring_input: LiveOrderRealStep6GInternalWiringInput) -> tuple[str, ...]:
    reasons: list[str] = []
    if wiring_input.symbol != SUPPORTED_SYMBOL:
        reasons.append("symbol_not_usd_jpy")
    if wiring_input.side != "BUY":
        reasons.append("side_not_buy")
    if wiring_input.size != LIVE_ORDER_CANDIDATE_SIZE:
        reasons.append("size_not_100")
    if wiring_input.executionType != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        reasons.append("execution_type_not_market")
    if wiring_input.codex_inferred:
        reasons.append("codex_inferred_order_intent")
    return tuple(reasons)


def _approval_reasons(
    wiring_input: LiveOrderRealStep6GInternalWiringInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not wiring_input.final_confirmation_exact_match:
        reasons.append("final_confirmation_missing_or_not_exact")
    if wiring_input.final_confirmation_reused:
        reasons.append("final_confirmation_reused")
    if not wiring_input.approval_artifact_reestablished:
        reasons.append("approval_artifact_missing")
    if not wiring_input.approval_validation_passed:
        reasons.append("approval_validation_failed")
    if not wiring_input.approval_exact_match_ready:
        reasons.append("approval_exact_match_not_ready")
    if not wiring_input.approval_fingerprint:
        reasons.append("approval_fingerprint_missing")
    if not wiring_input.sha256_prefix:
        reasons.append("approval_sha256_prefix_missing")
    return tuple(reasons)


def _preflight_reasons(
    wiring_input: LiveOrderRealStep6GInternalWiringInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not wiring_input.final_confirmation_preflight_passed:
        reasons.append("final_confirmation_preflight_failed")
    if not wiring_input.post_immediate_preflight_passed:
        reasons.append("post_immediate_preflight_failed")
    if wiring_input.market_session_state != "OPEN":
        reasons.append("market_session_not_open")
    if not wiring_input.market_window_allowed:
        reasons.append("market_window_not_allowed")
    if wiring_input.broker_maintenance_active:
        reasons.append("broker_maintenance_active")
    if wiring_input.holiday_or_special_close:
        reasons.append("holiday_or_special_close")
    if wiring_input.market_hours_unknown:
        reasons.append("market_hours_unknown")
    if wiring_input.open_positions_count != 0:
        reasons.append("open_positions_not_zero")
    if wiring_input.active_orders_count != 0:
        reasons.append("active_orders_not_zero")
    if wiring_input.ticker_symbol != SUPPORTED_SYMBOL:
        reasons.append("ticker_symbol_mismatch")
    if wiring_input.ticker_spread_jpy > 0.01:
        reasons.append("ticker_spread_too_wide")
    if wiring_input.ticker_age_seconds > 30 or wiring_input.ticker_age_seconds < -5:
        reasons.append("ticker_age_out_of_range")
    if not wiring_input.ticker_check_passed:
        reasons.append("ticker_check_failed")
    if not wiring_input.permission_scope_check_passed:
        reasons.append("permission_scope_failed")
    if not wiring_input.ip_account_binding_check_passed:
        reasons.append("ip_account_binding_failed")
    if not wiring_input.previous_result_unknown_check_passed:
        reasons.append("previous_result_unknown_check_failed")
    return tuple(reasons)


def _attempt_reasons(
    wiring_input: LiveOrderRealStep6GInternalWiringInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if wiring_input.post_attempt_limit != 1:
        reasons.append("post_attempt_limit_not_one")
    if wiring_input.post_attempt_count_before != 0:
        reasons.append("post_attempt_count_before_not_zero")
    for field_name in (
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(wiring_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _route_bridge_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealStep6GPostRouteBridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST
    )
    if not snapshot.input_snapshot.pb_bridge_ready:
        reasons.append("pb_bridge_ready_flag_false")
    if snapshot.pb_result.status is not expected:
        reasons.append(f"pb_status_{snapshot.pb_result.status.value}")
    if snapshot.pb_result.order_endpoint_called:
        reasons.append("pb_order_endpoint_called")
    if snapshot.pb_result.live_order_once_called:
        reasons.append("pb_live_order_once_called")
    if snapshot.input_snapshot.http_post_executed:
        reasons.append("http_post_executed")
    return tuple(reasons)


def _runtime_bridge_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    allowed = {
        LiveOrderRealStep6GRuntimeBridgeStatus.STEP6G_RUNTIME_BRIDGE_FAKE_READY_NO_API_NO_POST,
        LiveOrderRealStep6GRuntimeBridgeStatus.STEP6G_RUNTIME_BRIDGE_FAKE_COMPLETED_NO_API_NO_POST,
    }
    if not snapshot.input_snapshot.eb_runtime_ready:
        reasons.append("eb_runtime_ready_flag_false")
    if snapshot.eb_result.status not in allowed:
        reasons.append(f"eb_status_{snapshot.eb_result.status.value}")
    if snapshot.eb_result.real_http_post_executed:
        reasons.append("eb_real_http_post_executed")
    if snapshot.eb_result.order_endpoint_called:
        reasons.append("eb_order_endpoint_called")
    if snapshot.eb_result.live_order_once_called:
        reasons.append("eb_live_order_once_called")
    return tuple(reasons)


def _controlled_adapter_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    allowed = {
        LiveOrderRealStep6GControlledAdapterStatus
        .STEP6G_CONTROLLED_ADAPTER_FAKE_READY_NO_API_NO_POST,
        LiveOrderRealStep6GControlledAdapterStatus
        .STEP6G_CONTROLLED_ADAPTER_FAKE_COMPLETED_NO_API_NO_POST,
    }
    if not snapshot.input_snapshot.ad_controlled_adapter_ready:
        reasons.append("ad_controlled_adapter_ready_flag_false")
    if snapshot.ad_result.status not in allowed:
        reasons.append(f"ad_status_{snapshot.ad_result.status.value}")
    if snapshot.ad_result.real_http_post_executed:
        reasons.append("ad_real_http_post_executed")
    if snapshot.ad_result.order_endpoint_called:
        reasons.append("ad_order_endpoint_called")
    if snapshot.ad_result.live_order_once_called:
        reasons.append("ad_live_order_once_called")
    return tuple(reasons)


def _real_adapter_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    allowed = {
        LiveOrderRealStep6GRealAdapterStatus
        .STEP6G_REAL_ADAPTER_CONTRACT_READY_STUB_ONLY_NO_API_NO_POST,
        LiveOrderRealStep6GRealAdapterStatus.STEP6G_REAL_ADAPTER_STUB_COMPLETED_NO_API_NO_POST,
    }
    if not snapshot.input_snapshot.ra_real_adapter_ready:
        reasons.append("ra_real_adapter_ready_flag_false")
    if snapshot.ra_result.status not in allowed:
        reasons.append(f"ra_status_{snapshot.ra_result.status.value}")
    if snapshot.ra_result.real_http_post_executed:
        reasons.append("ra_real_http_post_executed")
    if snapshot.ra_result.order_endpoint_called:
        reasons.append("ra_order_endpoint_called")
    if snapshot.ra_result.live_order_once_called:
        reasons.append("ra_live_order_once_called")
    return tuple(reasons)


def _transport_core_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.input_snapshot.tc_transport_core_ready:
        reasons.append("tc_transport_core_ready_flag_false")
    if (
        snapshot.tc_result.status
        is not LiveOrderRealTransportCoreStatus.TRANSPORT_CORE_READY_NO_API_NO_POST
    ):
        reasons.append(f"tc_status_{snapshot.tc_result.status.value}")
    if snapshot.tc_result.http_post_executed:
        reasons.append("tc_http_post_executed")
    if snapshot.tc_result.order_endpoint_called:
        reasons.append("tc_order_endpoint_called")
    if snapshot.tc_result.live_order_once_called:
        reasons.append("tc_live_order_once_called")
    return tuple(reasons)


def _signing_contract_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealSigningContractStatus
        .SIGNING_CONTRACT_READY_NO_CREDENTIAL_NO_SIGNATURE
    )
    if not snapshot.input_snapshot.st_signing_contract_ready:
        reasons.append("st_signing_contract_ready_flag_false")
    if snapshot.st_signing_result.status is not expected:
        reasons.append(f"st_signing_status_{snapshot.st_signing_result.status.value}")
    if snapshot.st_signing_result.credential_values_provided:
        reasons.append("st_credential_values_provided")
    if snapshot.st_signing_result.signature_value_generated:
        reasons.append("st_signature_value_generated")
    return tuple(reasons)


def _dummy_signing_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.input_snapshot.dummy_signing_ready:
        reasons.append("dummy_signing_ready_flag_false")
    if not snapshot.input_snapshot.dummy_signature_check_passed:
        reasons.append("dummy_signature_check_passed_flag_false")
    expected = LiveOrderRealDummySigningStatus.DUMMY_SIGNING_CHECK_PASSED_NO_VALUE_EXPOSED
    if snapshot.dummy_signing_result.status is not expected:
        reasons.append(f"dummy_signing_status_{snapshot.dummy_signing_result.status.value}")
    if not snapshot.dummy_signing_result.dummy_signature_check_passed:
        reasons.append("dummy_signature_check_not_passed")
    return tuple(reasons)


def _private_transport_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealPrivateOrderTransportStatus
        .PRIVATE_ORDER_TRANSPORT_CONTRACT_READY_NO_API_NO_POST
    )
    if not snapshot.input_snapshot.st_private_transport_ready:
        reasons.append("st_private_transport_ready_flag_false")
    if snapshot.st_private_transport_result.status is not expected:
        reasons.append(
            f"st_private_transport_status_{snapshot.st_private_transport_result.status.value}",
        )
    if snapshot.st_private_transport_result.http_post_executed:
        reasons.append("st_private_http_post_executed")
    if snapshot.st_private_transport_result.order_endpoint_called:
        reasons.append("st_private_order_endpoint_called")
    if snapshot.st_private_transport_result.live_order_once_called:
        reasons.append("st_private_live_order_once_called")
    return tuple(reasons)


def _http_transport_interface_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealHttpTransportInterfaceStatus
        .HTTP_TRANSPORT_INTERFACE_READY_NO_API_NO_POST
    )
    if not snapshot.input_snapshot.http_transport_interface_ready:
        reasons.append("http_transport_interface_ready_flag_false")
    if snapshot.http_transport_interface_result.status is not expected:
        reasons.append(
            "http_transport_interface_status_"
            f"{snapshot.http_transport_interface_result.status.value}",
        )
    if snapshot.http_transport_interface_result.http_client_present:
        reasons.append("http_transport_interface_http_client_present")
    if snapshot.http_transport_interface_result.can_execute_http_post:
        reasons.append("http_transport_interface_can_execute_http_post")
    if snapshot.http_transport_interface_result.can_call_order_endpoint:
        reasons.append("http_transport_interface_can_call_order_endpoint")
    if snapshot.http_transport_interface_result.can_call_live_order_once:
        reasons.append("http_transport_interface_can_call_live_order_once")
    if snapshot.input_snapshot.http_client_present:
        reasons.append("http_client_present")
    if snapshot.input_snapshot.can_execute_http_post:
        reasons.append("can_execute_http_post")
    if snapshot.input_snapshot.can_call_order_endpoint:
        reasons.append("can_call_order_endpoint")
    if snapshot.input_snapshot.can_call_live_order_once:
        reasons.append("can_call_live_order_once")
    return tuple(reasons)


def _credential_boundary_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealCredentialBoundaryStatus
        .CREDENTIAL_BOUNDARY_READY_NO_CREDENTIAL_NO_ENV
    )
    if not snapshot.input_snapshot.credential_boundary_ready:
        reasons.append("credential_boundary_ready_flag_false")
    if snapshot.credential_boundary_result.status is not expected:
        reasons.append(
            "credential_boundary_status_"
            f"{snapshot.credential_boundary_result.status.value}",
        )
    if snapshot.credential_boundary_result.credential_values_provided:
        reasons.append("credential_boundary_values_provided")
    if snapshot.credential_boundary_result.credential_values_loaded:
        reasons.append("credential_boundary_values_loaded")
    if snapshot.credential_boundary_result.env_access_requested:
        reasons.append("credential_boundary_env_access_requested")
    if snapshot.credential_boundary_result.credential_metadata_exposed:
        reasons.append("credential_boundary_metadata_exposed")
    return tuple(reasons)


def _credential_handle_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = LiveOrderRealCredentialHandleStatus.CREDENTIAL_HANDLE_READY_NO_VALUE_NO_ENV
    if not snapshot.input_snapshot.credential_handle_ready:
        reasons.append("credential_handle_ready_flag_false")
    if snapshot.credential_handle_result.status is not expected:
        reasons.append(
            "credential_handle_status_"
            f"{snapshot.credential_handle_result.status.value}",
        )
    if snapshot.credential_handle_result.handle_created:
        reasons.append("credential_handle_created")
    if snapshot.credential_handle_result.handle_contains_value:
        reasons.append("credential_handle_contains_value")
    if snapshot.credential_handle_result.handle_contains_identifier:
        reasons.append("credential_handle_contains_identifier")
    if snapshot.credential_handle_result.handle_metadata_exposed:
        reasons.append("credential_handle_metadata_exposed")
    return tuple(reasons)


def _credential_injection_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealCredentialInjectionStatus
        .CREDENTIAL_INJECTION_READY_NO_VALUE_NO_ENV
    )
    if not snapshot.input_snapshot.credential_injection_ready:
        reasons.append("credential_injection_ready_flag_false")
    if snapshot.credential_injection_result.status is not expected:
        reasons.append(
            "credential_injection_status_"
            f"{snapshot.credential_injection_result.status.value}",
        )
    if snapshot.credential_injection_result.injection_performed:
        reasons.append("credential_injection_performed")
    if snapshot.credential_injection_result.real_credential_values_available:
        reasons.append("credential_injection_real_values_available")
    if snapshot.credential_injection_result.real_credential_values_injected:
        reasons.append("credential_injection_real_values_injected")
    if snapshot.credential_injection_result.credential_metadata_available:
        reasons.append("credential_injection_metadata_available")
    return tuple(reasons)


def _credential_presence_check_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealCredentialPresenceCheckStatus
        .CREDENTIAL_PRESENCE_CHECK_READY_OPERATOR_PROVIDED_NO_ENV
    )
    if not snapshot.input_snapshot.credential_presence_check_ready:
        reasons.append("credential_presence_check_ready_flag_false")
    if snapshot.credential_presence_check_result.status is not expected:
        reasons.append(
            "credential_presence_check_status_"
            f"{snapshot.credential_presence_check_result.status.value}",
        )
    if not snapshot.credential_presence_check_result.operator_sentinel_fresh:
        reasons.append("credential_presence_check_sentinel_not_fresh")
    if snapshot.credential_presence_check_result.operator_sentinel_reused:
        reasons.append("credential_presence_check_sentinel_reused")
    if snapshot.credential_presence_check_result.operator_sentinel_stale:
        reasons.append("credential_presence_check_sentinel_stale")
    if snapshot.credential_presence_check_result.operator_sentinel_previous_turn:
        reasons.append("credential_presence_check_previous_turn_sentinel")
    if snapshot.credential_presence_check_result.sentinel_value_present:
        reasons.append("credential_presence_check_sentinel_value_present")
    if snapshot.credential_presence_check_result.credential_values_present:
        reasons.append("credential_presence_check_values_present")
    if snapshot.credential_presence_check_result.credential_metadata_present:
        reasons.append("credential_presence_check_metadata_present")
    if (
        snapshot.credential_presence_check_result
        .credential_presence_checked_against_environment
    ):
        reasons.append("credential_presence_check_real_environment_checked")
    if snapshot.credential_presence_check_result.env_access_requested:
        reasons.append("credential_presence_check_env_access_requested")
    if snapshot.credential_presence_check_result.presence_result_broadly_propagated:
        reasons.append("credential_presence_check_result_broadly_propagated")
    if snapshot.credential_presence_check_result.presence_result_saved:
        reasons.append("credential_presence_check_result_saved")
    return tuple(reasons)


def _credential_presence_adapter_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealCredentialPresenceAdapterStatus
        .CREDENTIAL_PRESENCE_ADAPTER_READY_NO_ENV_NO_REAL_CHECK
    )
    if not snapshot.input_snapshot.credential_presence_adapter_ready:
        reasons.append("credential_presence_adapter_ready_flag_false")
    if snapshot.credential_presence_adapter_result.status is not expected:
        reasons.append(
            "credential_presence_adapter_status_"
            f"{snapshot.credential_presence_adapter_result.status.value}",
        )
    if not snapshot.credential_presence_adapter_result.operator_presence_result_fresh:
        reasons.append("credential_presence_adapter_result_not_fresh")
    if snapshot.credential_presence_adapter_result.operator_presence_result_reused:
        reasons.append("credential_presence_adapter_result_reused")
    if snapshot.credential_presence_adapter_result.operator_presence_result_stale:
        reasons.append("credential_presence_adapter_result_stale")
    if snapshot.credential_presence_adapter_result.operator_presence_result_previous_turn:
        reasons.append("credential_presence_adapter_previous_turn_result")
    if not snapshot.credential_presence_adapter_result.presence_result_adapted:
        reasons.append("credential_presence_adapter_not_adapted")
    if snapshot.credential_presence_adapter_result.presence_result_saved:
        reasons.append("credential_presence_adapter_result_saved")
    if snapshot.credential_presence_adapter_result.presence_result_displayed:
        reasons.append("credential_presence_adapter_result_displayed")
    if snapshot.credential_presence_adapter_result.presence_result_broadly_propagated:
        reasons.append("credential_presence_adapter_result_broadly_propagated")
    if snapshot.credential_presence_adapter_result.sentinel_value_present:
        reasons.append("credential_presence_adapter_sentinel_value_present")
    if snapshot.credential_presence_adapter_result.credential_values_present:
        reasons.append("credential_presence_adapter_values_present")
    if snapshot.credential_presence_adapter_result.credential_metadata_present:
        reasons.append("credential_presence_adapter_metadata_present")
    if snapshot.credential_presence_adapter_result.actual_environment_presence_check_performed:
        reasons.append("credential_presence_adapter_real_environment_checked")
    if snapshot.credential_presence_adapter_result.env_access_requested:
        reasons.append("credential_presence_adapter_env_access_requested")
    if snapshot.credential_presence_adapter_result.real_checker_attached:
        reasons.append("credential_presence_adapter_real_checker_attached")
    if snapshot.credential_presence_adapter_result.real_checker_executed:
        reasons.append("credential_presence_adapter_real_checker_executed")
    return tuple(reasons)


def _credential_presence_checker_contract_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealCredentialPresenceCheckerContractStatus
        .CREDENTIAL_PRESENCE_CHECKER_CONTRACT_READY_NO_ENV_NO_REAL_CHECK
    )
    result = snapshot.credential_presence_checker_contract_result
    if not snapshot.input_snapshot.credential_presence_checker_contract_ready:
        reasons.append("credential_presence_checker_contract_ready_flag_false")
    if result.status is not expected:
        reasons.append(
            "credential_presence_checker_contract_status_"
            f"{result.status.value}",
        )
    if result.unsupported_checker_contract_mode_present:
        reasons.append("credential_presence_checker_contract_unsupported_mode")
    if result.real_checker_implementation_present:
        reasons.append("credential_presence_checker_contract_real_checker_present")
    if result.real_checker_attached:
        reasons.append("credential_presence_checker_contract_real_checker_attached")
    if result.real_checker_executed:
        reasons.append("credential_presence_checker_contract_real_checker_executed")
    if result.actual_environment_presence_check_performed:
        reasons.append("credential_presence_checker_contract_real_environment_checked")
    if result.env_access_allowed:
        reasons.append("credential_presence_checker_contract_env_allowed")
    if result.env_access_requested:
        reasons.append("credential_presence_checker_contract_env_requested")
    if result.credential_values_read:
        reasons.append("credential_presence_checker_contract_values_read")
    if result.credential_values_available:
        reasons.append("credential_presence_checker_contract_values_available")
    if result.credential_metadata_available:
        reasons.append("credential_presence_checker_contract_metadata_available")
    if result.checker_result_available:
        reasons.append("credential_presence_checker_contract_result_available")
    if result.checker_result_saved:
        reasons.append("credential_presence_checker_contract_result_saved")
    if result.checker_result_displayed:
        reasons.append("credential_presence_checker_contract_result_displayed")
    if result.checker_result_broadly_propagated:
        reasons.append("credential_presence_checker_contract_result_broadly_propagated")
    if result.checker_result_unknown:
        reasons.append("credential_presence_checker_contract_result_unknown")
    if result.checker_result_failed:
        reasons.append("credential_presence_checker_contract_result_failed")
    return tuple(reasons)


def _operator_checker_workflow_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealOperatorExecutedCheckerWorkflowStatus
        .OPERATOR_CHECKER_WORKFLOW_READY_NO_CODEX_ENV_NO_API_NO_POST
    )
    result = snapshot.operator_checker_workflow_result
    if not snapshot.input_snapshot.operator_checker_workflow_ready:
        reasons.append("operator_checker_workflow_ready_flag_false")
    if result.status is not expected:
        reasons.append(f"operator_checker_workflow_status_{result.status.value}")
    if result.unsupported_workflow_mode_present:
        reasons.append("operator_checker_workflow_unsupported_mode")
    if result.codex_execution_performed:
        reasons.append("operator_checker_workflow_codex_execution_performed")
    if result.codex_env_access_requested:
        reasons.append("operator_checker_workflow_codex_env_requested")
    if result.actual_environment_presence_check_performed_by_codex:
        reasons.append("operator_checker_workflow_codex_environment_checked")
    if not result.operator_result_handoff_declared:
        reasons.append("operator_checker_workflow_handoff_not_declared")
    if not result.operator_result_handoff_safe:
        reasons.append("operator_checker_workflow_handoff_not_safe")
    if not result.operator_result_category_only:
        reasons.append("operator_checker_workflow_result_not_category_only")
    if not result.operator_result_provided:
        reasons.append("operator_checker_workflow_result_not_provided")
    if not result.operator_result_is_boolean_only:
        reasons.append("operator_checker_workflow_result_not_boolean_only")
    if result.operator_result_raw_value_present:
        reasons.append("operator_checker_workflow_raw_value_present")
    if result.operator_result_raw_value_saved:
        reasons.append("operator_checker_workflow_raw_value_saved")
    if result.operator_result_raw_value_displayed:
        reasons.append("operator_checker_workflow_raw_value_displayed")
    if not result.operator_result_fresh:
        reasons.append("operator_checker_workflow_result_not_fresh")
    if result.operator_result_stale:
        reasons.append("operator_checker_workflow_result_stale")
    if result.operator_result_reused:
        reasons.append("operator_checker_workflow_result_reused")
    if result.operator_result_previous_turn:
        reasons.append("operator_checker_workflow_previous_turn_result")
    if result.operator_result_timeout:
        reasons.append("operator_checker_workflow_result_timeout")
    if result.operator_result_unknown:
        reasons.append("operator_checker_workflow_result_unknown")
    if result.operator_result_failed:
        reasons.append("operator_checker_workflow_result_failed")
    if result.operator_result_unavailable:
        reasons.append("operator_checker_workflow_result_unavailable")
    if result.operator_result_saved:
        reasons.append("operator_checker_workflow_result_saved")
    if result.operator_result_displayed:
        reasons.append("operator_checker_workflow_result_displayed")
    if result.operator_result_broadly_propagated:
        reasons.append("operator_checker_workflow_result_broadly_propagated")
    if result.operator_result_detail_present:
        reasons.append("operator_checker_workflow_result_detail_present")
    if result.credential_values_present:
        reasons.append("operator_checker_workflow_values_present")
    if result.credential_metadata_present:
        reasons.append("operator_checker_workflow_metadata_present")
    if result.env_variable_names_present:
        reasons.append("operator_checker_workflow_env_names_present")
    if result.sentinel_value_present:
        reasons.append("operator_checker_workflow_sentinel_present")
    if result.checker_result_detail_present:
        reasons.append("operator_checker_workflow_checker_detail_present")
    return tuple(reasons)


def _credential_presence_checker_implementation_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealCredentialPresenceCheckerImplementationStatus
        .CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_READY_NO_ENV_NO_CHECK
    )
    result = snapshot.credential_presence_checker_implementation_result
    if not snapshot.input_snapshot.checker_implementation_skeleton_ready:
        reasons.append("checker_implementation_skeleton_ready_flag_false")
    if result.status is not expected:
        reasons.append(f"checker_implementation_status_{result.status.value}")
    if result.unsupported_implementation_mode_present:
        reasons.append("checker_implementation_unsupported_mode")
    if not result.execution_deferred_to_future_step:
        reasons.append("checker_implementation_execution_not_deferred")
    if result.execution_performed:
        reasons.append("checker_implementation_execution_performed")
    if result.codex_env_access_requested:
        reasons.append("checker_implementation_codex_env_requested")
    if result.actual_environment_presence_check_performed:
        reasons.append("checker_implementation_real_environment_checked")
    if result.env_access_capability_present:
        reasons.append("checker_implementation_env_access_capability_present")
    if result.credential_read_capability_present:
        reasons.append("checker_implementation_credential_read_capability_present")
    if result.credential_values_read:
        reasons.append("checker_implementation_values_read")
    if result.credential_values_present:
        reasons.append("checker_implementation_values_present")
    if result.credential_metadata_present:
        reasons.append("checker_implementation_metadata_present")
    if result.checker_result_available:
        reasons.append("checker_implementation_result_available")
    if result.checker_result_detail_present:
        reasons.append("checker_implementation_result_detail_present")
    if result.checker_result_unknown:
        reasons.append("checker_implementation_result_unknown")
    if result.checker_result_failed:
        reasons.append("checker_implementation_result_failed")
    if result.checker_result_unavailable:
        reasons.append("checker_implementation_result_unavailable")
    if result.checker_result_stale:
        reasons.append("checker_implementation_result_stale")
    if result.checker_result_saved:
        reasons.append("checker_implementation_result_saved")
    if result.checker_result_displayed:
        reasons.append("checker_implementation_result_displayed")
    if not result.operator_workflow_supported:
        reasons.append("checker_implementation_operator_workflow_not_supported")
    if not result.operator_workflow_preserved:
        reasons.append("checker_implementation_operator_workflow_not_preserved")
    return tuple(reasons)


def _credential_presence_checker_execution_contract_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealCredentialPresenceCheckerExecutionContractStatus
        .CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_READY_NO_ENV_NO_CHECK
    )
    result = snapshot.credential_presence_checker_execution_contract_result
    if not snapshot.input_snapshot.checker_execution_contract_ready:
        reasons.append("checker_execution_contract_ready_flag_false")
    if result.status is not expected:
        reasons.append(f"checker_execution_contract_status_{result.status.value}")
    if result.unsupported_execution_contract_mode_present:
        reasons.append("checker_execution_contract_unsupported_mode")
    if not result.execution_contract_declared:
        reasons.append("checker_execution_contract_not_declared")
    if not result.execution_inputs_declared:
        reasons.append("checker_execution_contract_inputs_not_declared")
    if not result.execution_outputs_declared:
        reasons.append("checker_execution_contract_outputs_not_declared")
    if not result.execution_stop_conditions_declared:
        reasons.append("checker_execution_contract_stop_conditions_not_declared")
    if not result.execution_deferred_to_future_step:
        reasons.append("checker_execution_contract_execution_not_deferred")
    if result.execution_performed:
        reasons.append("checker_execution_contract_execution_performed")
    if result.execution_performed_by_codex:
        reasons.append("checker_execution_contract_codex_execution_performed")
    if result.execution_performed_by_operator:
        reasons.append("checker_execution_contract_operator_execution_performed")
    if result.codex_env_access_requested:
        reasons.append("checker_execution_contract_codex_env_requested")
    if result.actual_environment_presence_check_performed:
        reasons.append("checker_execution_contract_real_environment_checked")
    if result.credential_read_performed:
        reasons.append("checker_execution_contract_credential_read_performed")
    if result.credential_values_present:
        reasons.append("checker_execution_contract_values_present")
    if result.credential_metadata_present:
        reasons.append("checker_execution_contract_metadata_present")
    if result.checker_result_available:
        reasons.append("checker_execution_contract_result_available")
    if not result.checker_result_is_boolean_only:
        reasons.append("checker_execution_contract_result_not_boolean_only")
    if result.checker_result_detail_present:
        reasons.append("checker_execution_contract_result_detail_present")
    if result.checker_result_unknown:
        reasons.append("checker_execution_contract_result_unknown")
    if result.checker_result_failed:
        reasons.append("checker_execution_contract_result_failed")
    if result.checker_result_unavailable:
        reasons.append("checker_execution_contract_result_unavailable")
    if result.checker_result_stale:
        reasons.append("checker_execution_contract_result_stale")
    if result.checker_result_timeout:
        reasons.append("checker_execution_contract_result_timeout")
    if result.checker_result_saved:
        reasons.append("checker_execution_contract_result_saved")
    if result.checker_result_displayed:
        reasons.append("checker_execution_contract_result_displayed")
    if result.checker_result_broadly_propagated:
        reasons.append("checker_execution_contract_result_broadly_propagated")
    if not result.operator_workflow_preserved:
        reasons.append("checker_execution_contract_operator_workflow_not_preserved")
    return tuple(reasons)


def _credential_presence_checker_execution_implementation_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealCredentialPresenceCheckerExecutionImplementationStatus
        .CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_READY_NO_ENV_NO_CHECK
    )
    result = snapshot.credential_presence_checker_execution_implementation_result
    if not snapshot.input_snapshot.checker_execution_implementation_skeleton_ready:
        reasons.append("checker_execution_implementation_ready_flag_false")
    if result.status is not expected:
        reasons.append(f"checker_execution_implementation_status_{result.status.value}")
    if result.unsupported_execution_implementation_mode_present:
        reasons.append("checker_execution_implementation_unsupported_mode")
    if not result.checker_execution_contract_ready:
        reasons.append("checker_execution_implementation_contract_not_ready")
    if not result.checker_implementation_skeleton_ready:
        reasons.append("checker_execution_implementation_skeleton_not_ready")
    if not result.operator_result_handoff_safe:
        reasons.append("checker_execution_implementation_operator_handoff_not_safe")
    if not result.operator_checker_workflow_ready:
        reasons.append("checker_execution_implementation_operator_workflow_not_ready")
    if not result.execution_implementation_declared:
        reasons.append("checker_execution_implementation_not_declared")
    if not result.execution_interface_declared:
        reasons.append("checker_execution_implementation_interface_not_declared")
    if not result.execution_lifecycle_declared:
        reasons.append("checker_execution_implementation_lifecycle_not_declared")
    if not result.execution_result_mapping_declared:
        reasons.append("checker_execution_implementation_mapping_not_declared")
    if not result.execution_stop_conditions_declared:
        reasons.append("checker_execution_implementation_stop_conditions_not_declared")
    if not result.execution_deferred_to_future_step:
        reasons.append("checker_execution_implementation_execution_not_deferred")
    if result.execution_performed:
        reasons.append("checker_execution_implementation_execution_performed")
    if result.execution_performed_by_codex:
        reasons.append("checker_execution_implementation_codex_execution_performed")
    if result.execution_performed_by_operator:
        reasons.append("checker_execution_implementation_operator_execution_performed")
    if result.env_access_requested:
        reasons.append("checker_execution_implementation_env_requested")
    if result.codex_env_access_requested:
        reasons.append("checker_execution_implementation_codex_env_requested")
    if result.actual_environment_presence_check_performed:
        reasons.append("checker_execution_implementation_real_environment_checked")
    if result.credential_read_performed:
        reasons.append("checker_execution_implementation_credential_read_performed")
    if result.credential_values_present:
        reasons.append("checker_execution_implementation_values_present")
    if result.credential_metadata_present:
        reasons.append("checker_execution_implementation_metadata_present")
    if result.checker_result_available:
        reasons.append("checker_execution_implementation_result_available")
    if result.checker_result_detail_present:
        reasons.append("checker_execution_implementation_result_detail_present")
    if result.checker_result_unknown:
        reasons.append("checker_execution_implementation_result_unknown")
    if result.checker_result_failed:
        reasons.append("checker_execution_implementation_result_failed")
    if result.checker_result_unavailable:
        reasons.append("checker_execution_implementation_result_unavailable")
    if result.checker_result_stale:
        reasons.append("checker_execution_implementation_result_stale")
    if result.checker_result_timeout:
        reasons.append("checker_execution_implementation_result_timeout")
    if result.checker_result_saved:
        reasons.append("checker_execution_implementation_result_saved")
    if result.checker_result_displayed:
        reasons.append("checker_execution_implementation_result_displayed")
    if result.operator_result_detail_present:
        reasons.append("checker_execution_implementation_operator_detail_present")
    if result.operator_result_raw_value_present:
        reasons.append("checker_execution_implementation_operator_raw_value_present")
    if result.operator_result_reused:
        reasons.append("checker_execution_implementation_operator_result_reused")
    if result.operator_result_previous_turn:
        reasons.append("checker_execution_implementation_operator_previous_turn")
    if result.operator_result_timeout:
        reasons.append("checker_execution_implementation_operator_timeout")
    return tuple(reasons)


def _operator_executed_execution_boundary_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    expected = (
        LiveOrderRealOperatorExecutedExecutionBoundaryStatus
        .OPERATOR_EXECUTED_EXECUTION_BOUNDARY_READY_NO_ENV_NO_CHECK
    )
    result = snapshot.operator_executed_execution_boundary_result
    if not snapshot.input_snapshot.operator_executed_execution_boundary_ready:
        reasons.append("operator_executed_execution_boundary_ready_flag_false")
    if result.status is not expected:
        reasons.append(f"operator_execution_boundary_status_{result.status.value}")
    if result.unsupported_boundary_mode_present:
        reasons.append("operator_execution_boundary_unsupported_mode")
    if not result.boundary_declared:
        reasons.append("operator_execution_boundary_not_declared")
    if not result.operator_execution_boundary_declared:
        reasons.append("operator_execution_boundary_contract_not_declared")
    if not result.operator_execution_must_be_outside_codex:
        reasons.append("operator_execution_boundary_not_outside_codex")
    if not result.codex_execution_forbidden:
        reasons.append("operator_execution_boundary_codex_execution_not_forbidden")
    if not result.checker_execution_implementation_skeleton_ready:
        reasons.append("operator_execution_boundary_implementation_not_ready")
    if not result.checker_execution_contract_ready:
        reasons.append("operator_execution_boundary_contract_not_ready")
    if not result.operator_result_handoff_safe:
        reasons.append("operator_execution_boundary_handoff_not_safe")
    if not result.operator_checker_workflow_ready:
        reasons.append("operator_execution_boundary_workflow_not_ready")
    if result.operator_execution_performed:
        reasons.append("operator_execution_boundary_operator_execution_performed")
    if result.codex_execution_performed:
        reasons.append("operator_execution_boundary_codex_execution_performed")
    if result.env_access_requested:
        reasons.append("operator_execution_boundary_env_requested")
    if result.codex_env_access_requested:
        reasons.append("operator_execution_boundary_codex_env_requested")
    if result.actual_environment_presence_check_performed:
        reasons.append("operator_execution_boundary_real_environment_checked")
    if result.credential_read_performed:
        reasons.append("operator_execution_boundary_credential_read")
    if result.credential_values_present:
        reasons.append("operator_execution_boundary_values_present")
    if result.credential_metadata_present:
        reasons.append("operator_execution_boundary_metadata_present")
    if result.operator_result_provided:
        reasons.append("operator_execution_boundary_operator_result_provided")
    if not result.operator_result_safe_boolean_category_only:
        reasons.append("operator_execution_boundary_result_not_safe_category")
    if result.operator_result_detail_present:
        reasons.append("operator_execution_boundary_operator_detail_present")
    if result.operator_result_raw_value_present:
        reasons.append("operator_execution_boundary_operator_raw_value_present")
    if result.operator_result_unknown:
        reasons.append("operator_execution_boundary_result_unknown")
    if result.operator_result_failed:
        reasons.append("operator_execution_boundary_result_failed")
    if result.operator_result_unavailable:
        reasons.append("operator_execution_boundary_result_unavailable")
    if result.operator_result_stale:
        reasons.append("operator_execution_boundary_result_stale")
    if result.operator_result_timeout:
        reasons.append("operator_execution_boundary_result_timeout")
    if result.operator_result_reused:
        reasons.append("operator_execution_boundary_result_reused")
    if result.operator_result_previous_turn:
        reasons.append("operator_execution_boundary_previous_turn_result")
    if result.operator_result_saved:
        reasons.append("operator_execution_boundary_result_saved")
    if result.operator_result_displayed:
        reasons.append("operator_execution_boundary_result_displayed")
    if result.operator_result_broadly_propagated:
        reasons.append("operator_execution_boundary_result_broadly_propagated")
    if result.checker_result_detail_present:
        reasons.append("operator_execution_boundary_checker_detail_present")
    if result.env_variable_names_present:
        reasons.append("operator_execution_boundary_env_names_present")
    if result.sentinel_value_present:
        reasons.append("operator_execution_boundary_sentinel_present")
    return tuple(reasons)


def _operator_execution_result_category_contract_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    ready_statuses = (
        LiveOrderRealOperatorExecutionResultCategoryContractStatus
        .OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_NO_RESULT,
        LiveOrderRealOperatorExecutionResultCategoryContractStatus
        .OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_CONFIRMED_NO_POST,
    )
    result = snapshot.operator_execution_result_category_contract_result
    if not snapshot.input_snapshot.operator_execution_result_category_contract_ready:
        reasons.append("operator_result_category_contract_ready_flag_false")
    if result.status not in ready_statuses:
        reasons.append(f"operator_result_category_status_{result.status.value}")
    if result.unsupported_category_present:
        reasons.append("operator_result_category_unsupported")
    if not result.category_contract_declared:
        reasons.append("operator_result_category_contract_not_declared")
    if not result.allowed_category_set_declared:
        reasons.append("operator_result_category_set_not_declared")
    if not result.operator_executed_execution_boundary_ready:
        reasons.append("operator_result_category_boundary_not_ready")
    if not result.operator_result_handoff_safe:
        reasons.append("operator_result_category_handoff_not_safe")
    if not result.operator_checker_workflow_ready:
        reasons.append("operator_result_category_workflow_not_ready")
    if not result.operator_result_category_is_safe_label:
        reasons.append("operator_result_category_not_safe_label")
    if not result.operator_result_category_is_allowed:
        reasons.append("operator_result_category_not_allowed")
    if result.operator_result_category not in {
        category.value for category in LiveOrderRealOperatorExecutionResultCategory
    }:
        reasons.append("operator_result_category_not_allowlisted")
    if result.operator_result_unknown:
        reasons.append("operator_result_category_unknown")
    if result.operator_result_failed:
        reasons.append("operator_result_category_failed")
    if result.operator_result_unavailable:
        reasons.append("operator_result_category_unavailable")
    if result.operator_result_stale:
        reasons.append("operator_result_category_stale")
    if result.operator_result_timeout:
        reasons.append("operator_result_category_timeout")
    if result.operator_result_reused:
        reasons.append("operator_result_category_reused")
    if result.operator_result_previous_turn:
        reasons.append("operator_result_category_previous_turn")
    if result.operator_result_detail_present:
        reasons.append("operator_result_category_detail_present")
    if result.operator_result_raw_value_present:
        reasons.append("operator_result_category_raw_value_present")
    if result.operator_result_saved:
        reasons.append("operator_result_category_saved")
    if result.operator_result_displayed:
        reasons.append("operator_result_category_displayed")
    if result.operator_result_broadly_propagated:
        reasons.append("operator_result_category_broadly_propagated")
    if result.checker_result_detail_present:
        reasons.append("operator_result_category_checker_detail_present")
    if result.env_variable_names_present:
        reasons.append("operator_result_category_env_names_present")
    if result.credential_values_present:
        reasons.append("operator_result_category_credential_values_present")
    if result.credential_metadata_present:
        reasons.append("operator_result_category_credential_metadata_present")
    if result.sentinel_value_present:
        reasons.append("operator_result_category_sentinel_present")
    if result.actual_execution_performed:
        reasons.append("operator_result_category_actual_execution_performed")
    if result.codex_execution_performed:
        reasons.append("operator_result_category_codex_execution_performed")
    if result.env_access_requested:
        reasons.append("operator_result_category_env_requested")
    if result.credential_read_performed:
        reasons.append("operator_result_category_credential_read")
    if result.can_generate_real_signature:
        reasons.append("operator_result_category_can_generate_signature")
    if result.can_generate_real_headers:
        reasons.append("operator_result_category_can_generate_headers")
    if result.can_execute_http_post:
        reasons.append("operator_result_category_can_execute_post")
    if result.http_post_executed:
        reasons.append("operator_result_category_http_post_executed")
    if result.order_endpoint_called:
        reasons.append("operator_result_category_order_endpoint_called")
    if result.live_order_once_called:
        reasons.append("operator_result_category_live_order_once_called")
    if result.post_allowed_this_step:
        reasons.append("operator_result_category_post_allowed")
    if result.post_executed:
        reasons.append("operator_result_category_post_executed")
    if not result.safe_to_render:
        reasons.append("operator_result_category_render_not_safe")
    if not result.safe_to_serialize:
        reasons.append("operator_result_category_serialize_not_safe")
    return tuple(reasons)


def _operator_result_handoff_receipt_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    ready_statuses = (
        LiveOrderRealOperatorResultHandoffReceiptStatus
        .OPERATOR_RESULT_HANDOFF_RECEIPT_READY_NOT_PROVIDED,
        LiveOrderRealOperatorResultHandoffReceiptStatus
        .OPERATOR_RESULT_HANDOFF_RECEIPT_READY_CONFIRMED_NO_POST,
    )
    result = snapshot.operator_result_handoff_receipt_result
    if not snapshot.input_snapshot.operator_result_handoff_receipt_ready:
        reasons.append("operator_result_handoff_receipt_ready_flag_false")
    if result.status not in ready_statuses:
        reasons.append(f"operator_result_handoff_receipt_status_{result.status.value}")
    if result.unsupported_category_present:
        reasons.append("operator_result_handoff_receipt_unsupported_category")
    for field_name, reason in (
        ("receipt_contract_declared", "receipt_contract_not_declared"),
        ("receipt_boundary_declared", "receipt_boundary_not_declared"),
        ("receipt_one_time_required", "receipt_one_time_not_required"),
        ("receipt_fresh_required", "receipt_fresh_not_required"),
        ("receipt_non_reuse_required", "receipt_non_reuse_not_required"),
        ("receipt_non_raw_required", "receipt_non_raw_not_required"),
        ("receipt_non_detail_required", "receipt_non_detail_not_required"),
        (
            "operator_execution_result_category_contract_ready",
            "receipt_category_contract_not_ready",
        ),
        (
            "operator_executed_execution_boundary_ready",
            "receipt_execution_boundary_not_ready",
        ),
        ("operator_result_handoff_safe", "receipt_operator_handoff_not_safe"),
        (
            "operator_result_category_is_safe_label",
            "receipt_category_not_safe_label",
        ),
        ("operator_result_category_is_allowed", "receipt_category_not_allowed"),
        ("receipt_current_turn", "receipt_not_current_turn"),
        ("receipt_fresh", "receipt_not_fresh"),
    ):
        if not getattr(result, field_name):
            reasons.append(reason)
    if result.operator_result_category not in {
        category.value for category in LiveOrderRealOperatorExecutionResultCategory
    }:
        reasons.append("operator_result_handoff_receipt_category_not_allowlisted")
    for field_name in (
        "receipt_stale",
        "receipt_reused",
        "receipt_previous_turn",
        "receipt_expired",
        "receipt_timeout",
        "receipt_unknown",
        "receipt_failed",
        "receipt_unavailable",
        "receipt_raw_value_present",
        "receipt_detail_present",
        "receipt_id_present",
        "receipt_token_present",
        "receipt_nonce_present",
        "receipt_hash_present",
        "receipt_fingerprint_present",
        "receipt_length_present",
        "receipt_saved",
        "receipt_displayed",
        "receipt_broadly_propagated",
        "operator_result_detail_present",
        "operator_result_raw_value_present",
        "checker_result_detail_present",
        "env_variable_names_present",
        "credential_values_present",
        "credential_metadata_present",
        "sentinel_value_present",
        "actual_execution_performed",
        "codex_execution_performed",
        "env_access_requested",
        "credential_read_performed",
        "can_generate_real_signature",
        "can_generate_real_headers",
        "can_execute_http_post",
        "http_post_executed",
        "order_endpoint_called",
        "live_order_once_called",
        "post_allowed_this_step",
        "post_executed",
    ):
        if getattr(result, field_name):
            reasons.append(f"operator_result_handoff_receipt_{field_name}_unsafe")
    if not result.safe_to_render:
        reasons.append("operator_result_handoff_receipt_render_not_safe")
    if not result.safe_to_serialize:
        reasons.append("operator_result_handoff_receipt_serialize_not_safe")
    return tuple(reasons)


def _raw_or_secret_reasons(
    wiring_input: LiveOrderRealStep6GInternalWiringInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "approval_command_full_text_present",
        "approval_command_displayed",
        "approval_command_saved",
        "raw_request_displayed",
        "raw_request_saved",
        "raw_response_displayed",
        "raw_response_saved",
        "headers_displayed",
        "headers_saved",
        "signature_displayed",
        "signature_saved",
        "credentials_displayed",
        "credentials_saved",
        "real_ids_displayed",
        "real_ids_saved",
        "credential_values_provided",
        "signature_value_generated",
        "header_values_present",
        "dummy_signature_value_present",
        "dummy_signature_value_displayed",
        "dummy_signature_value_saved",
        "credential_values_loaded",
        "credential_presence_checked_against_environment",
        "env_access_requested",
        "credential_metadata_exposed",
        "handle_created",
        "handle_contains_value",
        "handle_contains_identifier",
        "handle_metadata_exposed",
        "injection_performed",
        "real_credential_values_available",
        "real_credential_values_injected",
        "credential_injection_metadata_available",
        "operator_sentinel_reused",
        "operator_sentinel_stale",
        "operator_sentinel_previous_turn",
        "sentinel_value_present",
        "sentinel_value_displayed",
        "sentinel_value_saved",
        "sentinel_hash_available",
        "sentinel_fingerprint_available",
        "sentinel_length_available",
        "presence_result_broadly_propagated",
        "presence_result_saved",
        "operator_presence_result_reused",
        "operator_presence_result_stale",
        "operator_presence_result_previous_turn",
        "presence_result_displayed",
        "actual_environment_presence_check_performed",
        "real_checker_attached",
        "real_checker_executed",
        "real_checker_implementation_present",
        "env_access_allowed",
        "credential_values_available",
        "credential_values_read",
        "credential_values_displayed",
        "credential_values_saved",
        "credential_metadata_available",
        "credential_metadata_displayed",
        "credential_metadata_saved",
        "checker_result_available",
        "checker_result_saved",
        "checker_result_displayed",
        "checker_result_broadly_propagated",
        "checker_result_unknown",
        "checker_result_failed",
        "codex_env_access_requested",
        "actual_environment_presence_check_performed_by_codex",
        "operator_result_raw_value_present",
        "operator_result_raw_value_saved",
        "operator_result_raw_value_displayed",
        "operator_result_timeout",
        "operator_result_saved",
        "operator_result_displayed",
        "operator_result_broadly_propagated",
        "operator_result_detail_present",
        "env_variable_names_present",
        "checker_result_detail_present",
        "execution_performed",
        "execution_performed_by_codex",
        "execution_performed_by_operator",
        "operator_execution_performed",
        "credential_read_performed",
        "env_access_capability_present",
        "credential_read_capability_present",
        "checker_result_unavailable",
        "checker_result_stale",
        "checker_result_timeout",
        "receipt_raw_value_present",
        "receipt_detail_present",
        "receipt_id_present",
        "receipt_token_present",
        "receipt_nonce_present",
        "receipt_hash_present",
        "receipt_fingerprint_present",
        "receipt_length_present",
        "receipt_saved",
        "receipt_displayed",
        "receipt_broadly_propagated",
    ):
        if getattr(wiring_input, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _step4_reasons(
    wiring_input: LiveOrderRealStep6GInternalWiringInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if wiring_input.step4_spoofing:
        reasons.append("step4_spoofing")
    if wiring_input.ledger_changed:
        reasons.append("ledger_changed")
    return tuple(reasons)


def _unsupported_reasons(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.input_snapshot.allowed_for_live:
        reasons.append("allowed_for_live_true")
    if snapshot.input_snapshot.post_allowed_this_step:
        reasons.append("post_allowed_this_step_true")
    if snapshot.input_snapshot.post_executed:
        reasons.append("post_executed_true")
    return tuple(reasons)


def _build_check_results(
    snapshot: LiveOrderRealStep6GInternalWiringSnapshot,
) -> tuple[LiveOrderRealStep6GInternalWiringCheckResult, ...]:
    input_snapshot = snapshot.input_snapshot
    checks = (
        ("order intent", not _order_reasons(input_snapshot), "USD_JPY BUY 100 MARKET"),
        ("approval", not _approval_reasons(input_snapshot), "fake exact approval flags"),
        ("preflight", not _preflight_reasons(input_snapshot), "fake preflights passed"),
        ("attempt", not _attempt_reasons(input_snapshot), "one shot no retry"),
        ("PB", not _route_bridge_reasons(snapshot), "post route bridge ready"),
        ("EB", not _runtime_bridge_reasons(snapshot), "runtime fake ready"),
        ("AD", not _controlled_adapter_reasons(snapshot), "controlled fake ready"),
        ("RA", not _real_adapter_reasons(snapshot), "real adapter stub ready"),
        ("TC", not _transport_core_reasons(snapshot), "transport core ready"),
        ("ST signing", not _signing_contract_reasons(snapshot), "signing contract ready"),
        ("dummy signing", not _dummy_signing_reasons(snapshot), "dummy signing ready"),
        (
            "ST private transport",
            not _merge_reasons(
                _private_transport_reasons(snapshot),
                _http_transport_interface_reasons(snapshot),
            ),
            "private transport and HTTP interface contracts ready",
        ),
        (
            "HTTP transport interface",
            not _http_transport_interface_reasons(snapshot),
            "interface-only transport ready",
        ),
        (
            "credential boundary",
            not _credential_boundary_reasons(snapshot),
            "boundary-only credential contract ready",
        ),
        (
            "credential handle",
            not _credential_handle_reasons(snapshot),
            "contract-only credential handle ready",
        ),
        (
            "credential injection",
            not _credential_injection_reasons(snapshot),
            "skeleton-only credential injection ready",
        ),
        (
            "credential presence check",
            not _credential_presence_check_reasons(snapshot),
            "operator-provided sentinel skeleton ready",
        ),
        (
            "credential presence adapter",
            not _credential_presence_adapter_reasons(snapshot),
            "presence adapter skeleton ready",
        ),
        (
            "credential presence checker contract",
            not _credential_presence_checker_contract_reasons(snapshot),
            "checker contract ready",
        ),
        (
            "operator checker workflow",
            not _operator_checker_workflow_reasons(snapshot),
            "operator-executed workflow skeleton ready",
        ),
        (
            "credential presence checker implementation",
            not _credential_presence_checker_implementation_reasons(snapshot),
            "checker implementation skeleton ready",
        ),
        (
            "credential presence checker execution contract",
            not _credential_presence_checker_execution_contract_reasons(snapshot),
            "checker execution contract skeleton ready",
        ),
        (
            "credential presence checker execution implementation",
            not _credential_presence_checker_execution_implementation_reasons(snapshot),
            "checker execution implementation skeleton ready",
        ),
        (
            "operator executed execution boundary",
            not _operator_executed_execution_boundary_reasons(snapshot),
            "actual execution outside Codex and safe handoff boundary ready",
        ),
        (
            "operator execution result category contract",
            not _operator_execution_result_category_contract_reasons(snapshot),
            "operator execution result category contract ready without POST",
        ),
        (
            "operator result handoff receipt",
            not _operator_result_handoff_receipt_reasons(snapshot),
            "one-time fresh non-raw receipt ready without POST",
        ),
        ("raw secret IDs", not _raw_or_secret_reasons(input_snapshot), "none"),
        ("Step 4 spoofing", not _step4_reasons(input_snapshot), "none"),
    )
    return tuple(
        LiveOrderRealStep6GInternalWiringCheckResult(
            name=name,
            passed=passed,
            sanitized_value="ready" if passed else "blocked",
            expected=expected,
        )
        for name, passed, expected in checks
    )


def _merge_reasons(*reason_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in reason_groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
