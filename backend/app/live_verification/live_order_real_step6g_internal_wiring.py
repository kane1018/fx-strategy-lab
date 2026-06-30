"""Step 6G internal wiring dry-run, fake/sanitized only.

This module connects the existing Step 6G PB/EB/AD/RA/TC/ST safe pieces with
sentinel metadata. It does not execute API calls, HTTP POST, an order endpoint,
live_order_once, real signing, or credential access.
"""

from __future__ import annotations

from dataclasses import dataclass
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
                "signature_value_generated",
                "header_values_present",
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
    ):
        status = InternalWiringStatus.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT
        primary_reasons = _merge_reasons(
            signing_reasons,
            dummy_signing_reasons,
            credential_boundary_reasons,
            credential_handle_reasons,
            credential_injection_reasons,
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
        private_transport_reasons,
        http_interface_reasons,
        unsupported_reasons,
    )
    ready = status is InternalWiringStatus.STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST
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
        check_results=_build_check_results(wiring_snapshot),
        blocked_reasons=blocked_reasons,
        snapshot=wiring_snapshot,
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
