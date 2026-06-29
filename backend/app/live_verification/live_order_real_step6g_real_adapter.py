"""Step 6G real adapter contract with stub transport only.

This module models the adapter boundary that may precede a future real Step 6G
execution adapter. In this step it accepts only stub transport evidence. It does
not call APIs, import broker or Private API clients, import live_order_once,
build a real order payload, or execute HTTP POST.
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
from app.live_verification.live_order_real_step6g_controlled_adapter import (
    AdapterStatus as ControlledAdapterStatus,
)
from app.live_verification.live_order_real_step6g_controlled_adapter import (
    LiveOrderRealStep6GControlledAdapterResult,
)
from app.live_verification.live_order_real_step6g_post_route_bridge import (
    BridgeStatus,
    LiveOrderRealStep6GPostRouteBridgeResult,
)
from app.live_verification.live_order_real_step6g_runtime_bridge import (
    LiveOrderRealStep6GRuntimeBridgeResult,
    RuntimeStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_REAL_STEP6G_REAL_ADAPTER_ID_PREFIX = "LOR6GAD-"
STEP6G_REAL_ADAPTER_RECOMMENDED_NEXT_STEP = (
    "implement_separate_real_adapter_step_with_new_final_confirmation_fresh_preflight_and_no_retry"
)


class LiveOrderRealStep6GRealAdapterStatus(str, Enum):
    STEP6G_REAL_ADAPTER_CONTRACT_READY_STUB_ONLY_NO_API_NO_POST = (
        "STEP6G_REAL_ADAPTER_CONTRACT_READY_STUB_ONLY_NO_API_NO_POST"
    )
    STEP6G_REAL_ADAPTER_STUB_COMPLETED_NO_API_NO_POST = (
        "STEP6G_REAL_ADAPTER_STUB_COMPLETED_NO_API_NO_POST"
    )
    BLOCKED_STEP6G_REAL_ADAPTER_INPUT_NOT_READY = (
        "BLOCKED_STEP6G_REAL_ADAPTER_INPUT_NOT_READY"
    )
    BLOCKED_STEP6G_REAL_ADAPTER_TRANSPORT_UNSAFE = (
        "BLOCKED_STEP6G_REAL_ADAPTER_TRANSPORT_UNSAFE"
    )
    BLOCKED_STEP6G_REAL_ADAPTER_REAL_TRANSPORT_NOT_ALLOWED = (
        "BLOCKED_STEP6G_REAL_ADAPTER_REAL_TRANSPORT_NOT_ALLOWED"
    )
    BLOCKED_STEP6G_REAL_ADAPTER_ATTEMPT_STATE = (
        "BLOCKED_STEP6G_REAL_ADAPTER_ATTEMPT_STATE"
    )
    BLOCKED_STEP6G_REAL_ADAPTER_RAW_OR_SECRET_EXPOSURE = (
        "BLOCKED_STEP6G_REAL_ADAPTER_RAW_OR_SECRET_EXPOSURE"
    )
    BLOCKED_STEP6G_REAL_ADAPTER_RETRY_OR_LOOP = (
        "BLOCKED_STEP6G_REAL_ADAPTER_RETRY_OR_LOOP"
    )
    BLOCKED_STEP6G_REAL_ADAPTER_STEP4_SPOOFING = (
        "BLOCKED_STEP6G_REAL_ADAPTER_STEP4_SPOOFING"
    )
    BLOCKED_STEP6G_REAL_ADAPTER_UNSUPPORTED = (
        "BLOCKED_STEP6G_REAL_ADAPTER_UNSUPPORTED"
    )


class LiveOrderRealStep6GRealAdapterMode(str, Enum):
    STUB_TRANSPORT_ONLY_NO_API_NO_POST = "STUB_TRANSPORT_ONLY_NO_API_NO_POST"


class LiveOrderRealStep6GRealTransportMode(str, Enum):
    STUB_ONLY = "STUB_ONLY"
    REAL_TRANSPORT = "REAL_TRANSPORT"


class LiveOrderRealStep6GStubTransportResultCategory(str, Enum):
    STUB_REAL_ADAPTER_ACCEPTED_NO_API_NO_POST = (
        "STUB_REAL_ADAPTER_ACCEPTED_NO_API_NO_POST"
    )
    STUB_REAL_ADAPTER_REJECTED_NO_RETRY_NO_API_NO_POST = (
        "STUB_REAL_ADAPTER_REJECTED_NO_RETRY_NO_API_NO_POST"
    )
    STUB_REAL_ADAPTER_RESULT_UNKNOWN_NO_RETRY_NO_API_NO_POST = (
        "STUB_REAL_ADAPTER_RESULT_UNKNOWN_NO_RETRY_NO_API_NO_POST"
    )
    STUB_REAL_ADAPTER_TIMEOUT_NO_RETRY_NO_API_NO_POST = (
        "STUB_REAL_ADAPTER_TIMEOUT_NO_RETRY_NO_API_NO_POST"
    )


RealAdapterStatus = LiveOrderRealStep6GRealAdapterStatus
RealAdapterMode = LiveOrderRealStep6GRealAdapterMode
RealTransportMode = LiveOrderRealStep6GRealTransportMode
StubTransportResultCategory = LiveOrderRealStep6GStubTransportResultCategory
AdapterStatus = LiveOrderRealStep6GRealAdapterStatus
AdapterMode = LiveOrderRealStep6GRealAdapterMode
TransportMode = LiveOrderRealStep6GRealTransportMode
TransportResultCategory = LiveOrderRealStep6GStubTransportResultCategory


@dataclass(frozen=True)
class LiveOrderRealStep6GRealAdapterRequest:
    source_bridge_id: str
    source_bridge_status: str
    source_runtime_bridge_id: str
    source_runtime_bridge_status: str
    source_controlled_adapter_id: str
    source_controlled_adapter_status: str
    adapter_mode: LiveOrderRealStep6GRealAdapterMode
    step6g_post_route_bridge_ready: bool
    step6g_post_route_bridge_status: str
    step6g_runtime_bridge_fake_ready: bool
    step6g_runtime_bridge_fake_completed: bool
    step6g_controlled_adapter_fake_ready: bool
    step6g_controlled_adapter_fake_completed: bool
    final_confirmation_exact_match: bool
    final_confirmation_reused: bool
    approval_artifact_reestablished: bool
    approval_validation_passed: bool
    approval_exact_match: bool
    final_confirmation_preflight_passed: bool
    post_immediate_preflight_passed: bool
    order_intent_exact_match: bool
    symbol: str
    side: str
    size: int
    execution_type: str
    post_attempt_limit: int
    post_attempt_count_before: int
    stub_attempt_count: int
    post_allowed_this_step: bool
    post_executed: bool
    allowed_for_live: bool
    allowed_for_live_persisted: bool
    retry_allowed: bool
    loop_allowed: bool
    add_order_allowed: bool
    change_order_allowed: bool
    cancel_order_allowed: bool
    close_order_allowed: bool
    raw_secret_id_exposure: bool
    route_unsafe: bool
    step4_spoofing: bool
    real_http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    broker_order_path_called: bool

    def __post_init__(self) -> None:
        _require_non_empty("source_bridge_id", self.source_bridge_id)
        _require_non_empty("source_bridge_status", self.source_bridge_status)
        _require_non_empty("source_runtime_bridge_id", self.source_runtime_bridge_id)
        _require_non_empty("source_runtime_bridge_status", self.source_runtime_bridge_status)
        _require_non_empty("source_controlled_adapter_id", self.source_controlled_adapter_id)
        _require_non_empty(
            "source_controlled_adapter_status",
            self.source_controlled_adapter_status,
        )
        if not isinstance(self.adapter_mode, LiveOrderRealStep6GRealAdapterMode):
            raise LiveVerificationValidationError("adapter_mode must be Step 6G adapter mode")
        _require_non_empty("symbol", self.symbol)
        _require_non_empty("side", self.side)
        _require_non_empty("execution_type", self.execution_type)
        _validate_non_negative_int("size", self.size)
        _validate_non_negative_int("post_attempt_limit", self.post_attempt_limit)
        _validate_non_negative_int("post_attempt_count_before", self.post_attempt_count_before)
        _validate_non_negative_int("stub_attempt_count", self.stub_attempt_count)
        _validate_bool_fields(
            self,
            (
                "step6g_post_route_bridge_ready",
                "step6g_runtime_bridge_fake_ready",
                "step6g_runtime_bridge_fake_completed",
                "step6g_controlled_adapter_fake_ready",
                "step6g_controlled_adapter_fake_completed",
                "final_confirmation_exact_match",
                "final_confirmation_reused",
                "approval_artifact_reestablished",
                "approval_validation_passed",
                "approval_exact_match",
                "final_confirmation_preflight_passed",
                "post_immediate_preflight_passed",
                "order_intent_exact_match",
                "post_allowed_this_step",
                "post_executed",
                "allowed_for_live",
                "allowed_for_live_persisted",
                "retry_allowed",
                "loop_allowed",
                "add_order_allowed",
                "change_order_allowed",
                "cancel_order_allowed",
                "close_order_allowed",
                "raw_secret_id_exposure",
                "route_unsafe",
                "step4_spoofing",
                "real_http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "broker_order_path_called",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealStep6GRealTransportContract:
    transport_mode: LiveOrderRealStep6GRealTransportMode
    transport_name: str
    is_stub_transport: bool
    is_real_transport: bool
    can_execute_http_post: bool
    can_call_order_endpoint: bool
    can_call_live_order_once: bool
    imports_http_client: bool
    imports_private_api: bool
    imports_broker: bool
    imports_live_order_once: bool
    exposes_raw_request: bool
    exposes_raw_response: bool
    exposes_headers: bool
    exposes_signature: bool
    exposes_credentials: bool
    exposes_real_ids: bool
    returns_real_order_id: bool
    returns_raw_response: bool
    retry_on_unknown: bool
    retry_on_timeout: bool
    retry_on_reject: bool
    max_attempts: int

    def __post_init__(self) -> None:
        if not isinstance(self.transport_mode, LiveOrderRealStep6GRealTransportMode):
            raise LiveVerificationValidationError("transport_mode must be Step 6G transport mode")
        _require_non_empty("transport_name", self.transport_name)
        _validate_non_negative_int("max_attempts", self.max_attempts)
        _validate_bool_fields(
            self,
            (
                "is_stub_transport",
                "is_real_transport",
                "can_execute_http_post",
                "can_call_order_endpoint",
                "can_call_live_order_once",
                "imports_http_client",
                "imports_private_api",
                "imports_broker",
                "imports_live_order_once",
                "exposes_raw_request",
                "exposes_raw_response",
                "exposes_headers",
                "exposes_signature",
                "exposes_credentials",
                "exposes_real_ids",
                "returns_real_order_id",
                "returns_raw_response",
                "retry_on_unknown",
                "retry_on_timeout",
                "retry_on_reject",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealStep6GStubTransportResult:
    stub_transport_attempted: bool
    stub_transport_result_category: LiveOrderRealStep6GStubTransportResultCategory
    stub_attempt_count: int
    stub_retry_count: int = 0
    stub_loop_count: int = 0
    real_http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    broker_order_path_called: bool = False
    raw_request_present: bool = False
    raw_response_present: bool = False
    headers_present: bool = False
    signature_present: bool = False
    credentials_present: bool = False
    real_order_id_present: bool = False
    real_execution_id_present: bool = False
    real_position_id_present: bool = False
    real_client_order_id_present: bool = False
    result_is_stub: bool = True

    def __post_init__(self) -> None:
        if not isinstance(
            self.stub_transport_result_category,
            LiveOrderRealStep6GStubTransportResultCategory,
        ):
            raise LiveVerificationValidationError(
                "stub_transport_result_category must be Step 6G stub adapter category",
            )
        _validate_non_negative_int("stub_attempt_count", self.stub_attempt_count)
        _validate_non_negative_int("stub_retry_count", self.stub_retry_count)
        _validate_non_negative_int("stub_loop_count", self.stub_loop_count)
        _validate_bool_fields(
            self,
            (
                "stub_transport_attempted",
                "real_http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "broker_order_path_called",
                "raw_request_present",
                "raw_response_present",
                "headers_present",
                "signature_present",
                "credentials_present",
                "real_order_id_present",
                "real_execution_id_present",
                "real_position_id_present",
                "real_client_order_id_present",
                "result_is_stub",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealStep6GRealAdapterCheckResult:
    name: str
    passed: bool
    reason: str
    sanitized_value: str
    expected: str

    def __post_init__(self) -> None:
        _require_non_empty("name", self.name)
        if type(self.passed) is not bool:
            raise LiveVerificationValidationError("passed must be bool")
        _require_non_empty("reason", self.reason)
        _require_non_empty("sanitized_value", self.sanitized_value)
        _require_non_empty("expected", self.expected)


@dataclass(frozen=True)
class LiveOrderRealStep6GRealAdapterResult:
    adapter_id: str
    created_at: datetime
    status: LiveOrderRealStep6GRealAdapterStatus
    real_adapter_contract_ready: bool
    stub_transport_attempted: bool
    stub_transport_result_category: str
    real_http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    broker_order_path_called: bool
    allowed_for_live: bool
    post_allowed_this_step: bool
    post_executed: bool
    post_attempt_limit: int
    stub_attempt_count: int
    recommended_next_step: str
    request: LiveOrderRealStep6GRealAdapterRequest
    transport_contract: LiveOrderRealStep6GRealTransportContract
    transport_result: LiveOrderRealStep6GStubTransportResult | None
    check_results: tuple[LiveOrderRealStep6GRealAdapterCheckResult, ...]
    blocked_reasons: tuple[str, ...]

    @property
    def adapter_status(self) -> LiveOrderRealStep6GRealAdapterStatus:
        return self.status

    def __post_init__(self) -> None:
        _require_non_empty("adapter_id", self.adapter_id)
        _ensure_aware(self.created_at)
        if not isinstance(self.status, LiveOrderRealStep6GRealAdapterStatus):
            raise LiveVerificationValidationError("status must be Step 6G adapter status")
        _validate_non_negative_int("post_attempt_limit", self.post_attempt_limit)
        _validate_non_negative_int("stub_attempt_count", self.stub_attempt_count)
        _validate_bool_fields(
            self,
            (
                "real_adapter_contract_ready",
                "stub_transport_attempted",
                "real_http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "broker_order_path_called",
                "allowed_for_live",
                "post_allowed_this_step",
                "post_executed",
            ),
        )
        _require_non_empty("stub_transport_result_category", self.stub_transport_result_category)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        if self.real_adapter_contract_ready and self.blocked_reasons:
            raise LiveVerificationValidationError("ready stub adapter cannot have blockers")
        if self.real_http_post_executed:
            raise LiveVerificationValidationError(
                "stub adapter must keep real_http_post_executed=false",
            )
        if self.order_endpoint_called:
            raise LiveVerificationValidationError(
                "stub adapter must keep order_endpoint_called=false",
            )
        if self.live_order_once_called:
            raise LiveVerificationValidationError(
                "stub adapter must keep live_order_once_called=false",
            )
        if self.broker_order_path_called:
            raise LiveVerificationValidationError(
                "stub adapter must keep broker_order_path_called=false",
            )
        if self.allowed_for_live:
            raise LiveVerificationValidationError("stub adapter must keep allowed_for_live=false")
        if self.post_allowed_this_step:
            raise LiveVerificationValidationError(
                "stub adapter must keep post_allowed_this_step=false",
            )
        if self.post_executed:
            raise LiveVerificationValidationError("stub adapter must keep post_executed=false")


def build_live_order_real_step6g_real_adapter_contract(
    *,
    step6g_post_route_bridge_result: LiveOrderRealStep6GPostRouteBridgeResult,
    step6g_runtime_bridge_result: LiveOrderRealStep6GRuntimeBridgeResult,
    step6g_controlled_adapter_result: LiveOrderRealStep6GControlledAdapterResult,
    transport_contract: LiveOrderRealStep6GRealTransportContract,
    adapter_request: LiveOrderRealStep6GRealAdapterRequest | None = None,
    transport_result: LiveOrderRealStep6GStubTransportResult | None = None,
    created_at: datetime | None = None,
) -> LiveOrderRealStep6GRealAdapterResult:
    """Build a stub-transport-only real adapter contract decision."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    request = adapter_request or make_live_order_real_step6g_real_adapter_request(
        step6g_post_route_bridge_result=step6g_post_route_bridge_result,
        step6g_runtime_bridge_result=step6g_runtime_bridge_result,
        step6g_controlled_adapter_result=step6g_controlled_adapter_result,
        stub_attempt_count=transport_result.stub_attempt_count
        if transport_result
        else step6g_controlled_adapter_result.fake_attempt_count,
    )

    input_reasons = _input_not_ready_reasons(
        step6g_post_route_bridge_result,
        step6g_runtime_bridge_result,
        step6g_controlled_adapter_result,
        request,
    )
    step4_spoofing_reasons = _step4_spoofing_reasons(request)
    real_transport_reasons = _real_transport_reasons(transport_contract)
    attempt_reasons = _attempt_state_reasons(request, transport_result)
    retry_reasons = _retry_or_loop_reasons(request, transport_contract, transport_result)
    raw_reasons = _raw_or_secret_exposure_reasons(request, transport_contract, transport_result)
    transport_reasons = _transport_unsafe_reasons(request, transport_contract, transport_result)
    unsupported_reasons = _unsupported_reasons(request)

    if step4_spoofing_reasons:
        status = AdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_STEP4_SPOOFING
        primary_reasons = step4_spoofing_reasons
    elif input_reasons:
        status = AdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_INPUT_NOT_READY
        primary_reasons = input_reasons
    elif real_transport_reasons:
        status = AdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_REAL_TRANSPORT_NOT_ALLOWED
        primary_reasons = real_transport_reasons
    elif attempt_reasons:
        status = AdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_ATTEMPT_STATE
        primary_reasons = attempt_reasons
    elif retry_reasons:
        status = AdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_RETRY_OR_LOOP
        primary_reasons = retry_reasons
    elif raw_reasons:
        status = AdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_RAW_OR_SECRET_EXPOSURE
        primary_reasons = raw_reasons
    elif transport_reasons:
        status = AdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_TRANSPORT_UNSAFE
        primary_reasons = transport_reasons
    elif unsupported_reasons:
        status = AdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_UNSUPPORTED
        primary_reasons = unsupported_reasons
    elif transport_result is None:
        status = AdapterStatus.STEP6G_REAL_ADAPTER_CONTRACT_READY_STUB_ONLY_NO_API_NO_POST
        primary_reasons = ()
    else:
        status = AdapterStatus.STEP6G_REAL_ADAPTER_STUB_COMPLETED_NO_API_NO_POST
        primary_reasons = ()

    all_reasons = _merge_reasons(
        primary_reasons,
        input_reasons,
        step4_spoofing_reasons,
        real_transport_reasons,
        attempt_reasons,
        retry_reasons,
        raw_reasons,
        transport_reasons,
        unsupported_reasons,
    )
    ready = status in {
        AdapterStatus.STEP6G_REAL_ADAPTER_CONTRACT_READY_STUB_ONLY_NO_API_NO_POST,
        AdapterStatus.STEP6G_REAL_ADAPTER_STUB_COMPLETED_NO_API_NO_POST,
    }
    check_results = _build_check_results(
        request=request,
        transport_contract=transport_contract,
        transport_result=transport_result,
    )
    return LiveOrderRealStep6GRealAdapterResult(
        adapter_id=make_live_order_real_step6g_real_adapter_id(created),
        created_at=created,
        status=status,
        real_adapter_contract_ready=ready,
        stub_transport_attempted=bool(
            transport_result and transport_result.stub_transport_attempted
        ),
        stub_transport_result_category=transport_result.stub_transport_result_category.value
        if transport_result
        else "NOT_RUN_STUB_TRANSPORT_ONLY_NO_API_NO_POST",
        real_http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        broker_order_path_called=False,
        allowed_for_live=False,
        post_allowed_this_step=False,
        post_executed=False,
        post_attempt_limit=request.post_attempt_limit,
        stub_attempt_count=transport_result.stub_attempt_count
        if transport_result
        else request.stub_attempt_count,
        recommended_next_step=STEP6G_REAL_ADAPTER_RECOMMENDED_NEXT_STEP
        if ready
        else "fix_step6g_real_adapter_blockers_no_api_no_post",
        request=request,
        transport_contract=transport_contract,
        transport_result=transport_result,
        check_results=check_results,
        blocked_reasons=all_reasons,
    )


def run_live_order_real_step6g_real_adapter_with_stub_transport(
    *,
    step6g_post_route_bridge_result: LiveOrderRealStep6GPostRouteBridgeResult,
    step6g_runtime_bridge_result: LiveOrderRealStep6GRuntimeBridgeResult,
    step6g_controlled_adapter_result: LiveOrderRealStep6GControlledAdapterResult,
    transport_contract: LiveOrderRealStep6GRealTransportContract | None = None,
    stub_transport_result_category: LiveOrderRealStep6GStubTransportResultCategory = (
        TransportResultCategory.STUB_REAL_ADAPTER_ACCEPTED_NO_API_NO_POST
    ),
    adapter_request: LiveOrderRealStep6GRealAdapterRequest | None = None,
    created_at: datetime | None = None,
) -> LiveOrderRealStep6GRealAdapterResult:
    """Run the stub-transport-only real adapter contract without API or POST execution."""
    contract = transport_contract or make_live_order_real_step6g_stub_transport_contract()
    request = adapter_request or make_live_order_real_step6g_real_adapter_request(
        step6g_post_route_bridge_result=step6g_post_route_bridge_result,
        step6g_runtime_bridge_result=step6g_runtime_bridge_result,
        step6g_controlled_adapter_result=step6g_controlled_adapter_result,
        stub_attempt_count=1,
    )
    transport_result = LiveOrderRealStep6GStubTransportResult(
        stub_transport_attempted=True,
        stub_transport_result_category=stub_transport_result_category,
        stub_attempt_count=request.stub_attempt_count,
        stub_retry_count=0,
        stub_loop_count=0,
    )
    return build_live_order_real_step6g_real_adapter_contract(
        step6g_post_route_bridge_result=step6g_post_route_bridge_result,
        step6g_runtime_bridge_result=step6g_runtime_bridge_result,
        step6g_controlled_adapter_result=step6g_controlled_adapter_result,
        transport_contract=contract,
        adapter_request=request,
        transport_result=transport_result,
        created_at=created_at,
    )


build_live_order_real_step6g_real_adapter = (
    build_live_order_real_step6g_real_adapter_contract
)


def make_live_order_real_step6g_stub_transport_contract(
    *,
    transport_name: str = "step6g_controlled_stub_transport_no_api_no_post",
) -> LiveOrderRealStep6GRealTransportContract:
    return LiveOrderRealStep6GRealTransportContract(
        transport_mode=TransportMode.STUB_ONLY,
        transport_name=transport_name,
        is_stub_transport=True,
        is_real_transport=False,
        can_execute_http_post=False,
        can_call_order_endpoint=False,
        can_call_live_order_once=False,
        imports_http_client=False,
        imports_private_api=False,
        imports_broker=False,
        imports_live_order_once=False,
        exposes_raw_request=False,
        exposes_raw_response=False,
        exposes_headers=False,
        exposes_signature=False,
        exposes_credentials=False,
        exposes_real_ids=False,
        returns_real_order_id=False,
        returns_raw_response=False,
        retry_on_unknown=False,
        retry_on_timeout=False,
        retry_on_reject=False,
        max_attempts=1,
    )


def make_live_order_real_step6g_real_adapter_request(
    *,
    step6g_post_route_bridge_result: LiveOrderRealStep6GPostRouteBridgeResult,
    step6g_runtime_bridge_result: LiveOrderRealStep6GRuntimeBridgeResult,
    step6g_controlled_adapter_result: LiveOrderRealStep6GControlledAdapterResult,
    stub_attempt_count: int | None = None,
) -> LiveOrderRealStep6GRealAdapterRequest:
    bridge = step6g_post_route_bridge_result
    runtime = step6g_runtime_bridge_result
    controlled = step6g_controlled_adapter_result
    approval = bridge.approval_snapshot
    preflight = bridge.preflight_snapshot
    attempt = bridge.attempt_state
    order_intent = bridge.order_intent_snapshot
    route = bridge.route_contract_snapshot
    runtime_ready_statuses = {
        RuntimeStatus.STEP6G_RUNTIME_BRIDGE_FAKE_READY_NO_API_NO_POST,
        RuntimeStatus.STEP6G_RUNTIME_BRIDGE_FAKE_COMPLETED_NO_API_NO_POST,
    }
    controlled_ready_statuses = {
        ControlledAdapterStatus.STEP6G_CONTROLLED_ADAPTER_FAKE_READY_NO_API_NO_POST,
        ControlledAdapterStatus.STEP6G_CONTROLLED_ADAPTER_FAKE_COMPLETED_NO_API_NO_POST,
    }
    return LiveOrderRealStep6GRealAdapterRequest(
        source_bridge_id=bridge.bridge_id,
        source_bridge_status=bridge.status.value,
        source_runtime_bridge_id=runtime.runtime_bridge_id,
        source_runtime_bridge_status=runtime.status.value,
        source_controlled_adapter_id=controlled.adapter_id,
        source_controlled_adapter_status=controlled.status.value,
        adapter_mode=AdapterMode.STUB_TRANSPORT_ONLY_NO_API_NO_POST,
        step6g_post_route_bridge_ready=bridge.bridge_ready,
        step6g_post_route_bridge_status=bridge.status.value,
        step6g_runtime_bridge_fake_ready=runtime.fake_runtime_ready
        and runtime.status in runtime_ready_statuses,
        step6g_runtime_bridge_fake_completed=(
            runtime.status is RuntimeStatus.STEP6G_RUNTIME_BRIDGE_FAKE_COMPLETED_NO_API_NO_POST
        ),
        step6g_controlled_adapter_fake_ready=controlled.fake_adapter_ready
        and controlled.status in controlled_ready_statuses,
        step6g_controlled_adapter_fake_completed=(
            controlled.status
            is ControlledAdapterStatus.STEP6G_CONTROLLED_ADAPTER_FAKE_COMPLETED_NO_API_NO_POST
        ),
        final_confirmation_exact_match=(
            approval.step6g_final_confirmation_received
            and approval.step6g_final_confirmation_exact_match
        ),
        final_confirmation_reused=approval.final_confirmation_phrase_reused,
        approval_artifact_reestablished=approval.approval_artifact_reestablished,
        approval_validation_passed=approval.approval_validation_passed,
        approval_exact_match=approval.approval_exact_match_ready,
        final_confirmation_preflight_passed=preflight.final_confirmation_preflight_passed,
        post_immediate_preflight_passed=preflight.post_immediate_preflight_passed,
        order_intent_exact_match=_order_intent_exact_match(bridge),
        symbol=order_intent.symbol,
        side=order_intent.side,
        size=order_intent.size,
        execution_type=order_intent.executionType,
        post_attempt_limit=attempt.post_attempt_limit,
        post_attempt_count_before=attempt.post_attempt_count_before,
        stub_attempt_count=controlled.fake_attempt_count
        if stub_attempt_count is None
        else stub_attempt_count,
        post_allowed_this_step=(
            bridge.post_allowed_this_step
            or runtime.post_allowed_this_step
            or controlled.post_allowed_this_step
        ),
        post_executed=bridge.post_executed or runtime.post_executed or controlled.post_executed,
        allowed_for_live=(
            bridge.allowed_for_live
            or runtime.allowed_for_live
            or controlled.allowed_for_live
        ),
        allowed_for_live_persisted=(
            attempt.allowed_for_live_persisted or controlled.request.allowed_for_live_persisted
        ),
        retry_allowed=(
            attempt.retry_allowed
            or runtime.request.retry_allowed
            or controlled.request.retry_allowed
        ),
        loop_allowed=(
            attempt.loop_allowed
            or runtime.request.loop_allowed
            or controlled.request.loop_allowed
        ),
        add_order_allowed=(
            attempt.add_order_allowed
            or runtime.request.add_order_allowed
            or controlled.request.add_order_allowed
        ),
        change_order_allowed=(
            attempt.change_order_allowed
            or runtime.request.change_order_allowed
            or controlled.request.change_order_allowed
        ),
        cancel_order_allowed=(
            attempt.cancel_order_allowed
            or runtime.request.cancel_order_allowed
            or controlled.request.cancel_order_allowed
        ),
        close_order_allowed=(
            attempt.close_order_allowed
            or runtime.request.close_order_allowed
            or controlled.request.close_order_allowed
        ),
        raw_secret_id_exposure=runtime.request.raw_secret_id_exposure
        or controlled.request.raw_secret_id_exposure
        or _source_has_raw_or_secret_exposure(bridge),
        route_unsafe=(
            runtime.request.route_unsafe
            or controlled.request.route_unsafe
            or _source_route_is_unsafe(bridge)
        ),
        step4_spoofing=(
            runtime.request.step4_spoofing
            or controlled.request.step4_spoofing
            or _source_has_step4_spoofing(bridge)
        ),
        real_http_post_executed=(
            runtime.real_http_post_executed
            or runtime.request.real_http_post_executed
            or controlled.real_http_post_executed
            or controlled.request.real_http_post_executed
            or route.http_post_executed
        ),
        order_endpoint_called=(
            bridge.order_endpoint_called
            or runtime.order_endpoint_called
            or runtime.request.order_endpoint_called
            or controlled.order_endpoint_called
            or controlled.request.order_endpoint_called
            or route.order_endpoint_called
        ),
        live_order_once_called=(
            bridge.live_order_once_called
            or runtime.live_order_once_called
            or runtime.request.live_order_once_called
            or controlled.live_order_once_called
            or controlled.request.live_order_once_called
            or route.calls_live_order_once_directly
        ),
        broker_order_path_called=(
            runtime.broker_order_path_called
            or runtime.request.broker_order_path_called
            or controlled.broker_order_path_called
            or controlled.request.broker_order_path_called
            or route.imports_broker
        ),
    )


def render_live_order_real_step6g_real_adapter_markdown(
    result: LiveOrderRealStep6GRealAdapterResult,
) -> str:
    """Render a sanitized stub-only real adapter contract report."""
    lines = [
        "# Step 6G Real Adapter Contract Stub Transport",
        "",
        "This real adapter contract is stub transport only.",
        "This real adapter contract does not execute API calls.",
        "This real adapter contract does not execute HTTP POST.",
        "This real adapter contract does not call order endpoint.",
        "This real adapter contract does not call live_order_once.",
        "This real adapter contract does not reuse old final confirmation.",
        "Future real Step 6G execution requires a new final confirmation and fresh preflight.",
        "Future real transport implementation must be a separate Step.",
        "",
        "## Summary",
        f"- status: {result.status.value}",
        f"- real_adapter_contract_ready: {_bool_text(result.real_adapter_contract_ready)}",
        f"- stub_transport_attempted: {_bool_text(result.stub_transport_attempted)}",
        f"- stub_transport_result_category: {result.stub_transport_result_category}",
        f"- transport_mode: {result.transport_contract.transport_mode.value}",
        f"- real_http_post_executed: {_bool_text(result.real_http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- allowed_for_live: {_bool_text(result.allowed_for_live)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- post_attempt_limit: {result.post_attempt_limit}",
        f"- stub_attempt_count: {result.stub_attempt_count}",
        "",
        "## Inputs",
        f"- source_bridge_status: {result.request.source_bridge_status}",
        f"- source_runtime_bridge_status: {result.request.source_runtime_bridge_status}",
        f"- source_controlled_adapter_status: {result.request.source_controlled_adapter_status}",
        (
            "- final_confirmation_exact_match: "
            f"{_bool_text(result.request.final_confirmation_exact_match)}"
        ),
        f"- final_confirmation_reused: {_bool_text(result.request.final_confirmation_reused)}",
        f"- approval_exact_match: {_bool_text(result.request.approval_exact_match)}",
        f"- order_intent_exact_match: {_bool_text(result.request.order_intent_exact_match)}",
        "",
        "## Transport Contract",
        f"- transport_name: {result.transport_contract.transport_name}",
        f"- is_stub_transport: {_bool_text(result.transport_contract.is_stub_transport)}",
        f"- is_real_transport: {_bool_text(result.transport_contract.is_real_transport)}",
        (
            "- can_execute_http_post: "
            f"{_bool_text(result.transport_contract.can_execute_http_post)}"
        ),
        (
            "- can_call_order_endpoint: "
            f"{_bool_text(result.transport_contract.can_call_order_endpoint)}"
        ),
        (
            "- can_call_live_order_once: "
            f"{_bool_text(result.transport_contract.can_call_live_order_once)}"
        ),
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Check Results",
        *[
            (
                f"- {check.name}: {_bool_text(check.passed)} "
                f"({check.sanitized_value}; expected {check.expected})"
            )
            for check in result.check_results
        ],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def make_live_order_real_step6g_real_adapter_id(created_at: datetime) -> str:
    created = _ensure_aware(created_at)
    return (
        f"{LIVE_ORDER_REAL_STEP6G_REAL_ADAPTER_ID_PREFIX}"
        f"{created.strftime('%Y%m%dT%H%M%SZ')}"
    )


def _input_not_ready_reasons(
    bridge: LiveOrderRealStep6GPostRouteBridgeResult,
    runtime: LiveOrderRealStep6GRuntimeBridgeResult,
    controlled: LiveOrderRealStep6GControlledAdapterResult,
    request: LiveOrderRealStep6GRealAdapterRequest,
) -> tuple[str, ...]:
    reasons: list[str] = []
    runtime_ready_statuses = {
        RuntimeStatus.STEP6G_RUNTIME_BRIDGE_FAKE_READY_NO_API_NO_POST,
        RuntimeStatus.STEP6G_RUNTIME_BRIDGE_FAKE_COMPLETED_NO_API_NO_POST,
    }
    controlled_ready_statuses = {
        ControlledAdapterStatus.STEP6G_CONTROLLED_ADAPTER_FAKE_READY_NO_API_NO_POST,
        ControlledAdapterStatus.STEP6G_CONTROLLED_ADAPTER_FAKE_COMPLETED_NO_API_NO_POST,
    }
    if not bridge.bridge_ready:
        reasons.append("post_route_bridge_not_ready")
    if bridge.status is not BridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST:
        reasons.append("post_route_bridge_status_not_ready")
    if not runtime.fake_runtime_ready:
        reasons.append("runtime_bridge_not_ready")
    if runtime.status not in runtime_ready_statuses:
        reasons.append("runtime_bridge_status_not_ready")
    if not controlled.fake_adapter_ready:
        reasons.append("controlled_adapter_not_ready")
    if controlled.status not in controlled_ready_statuses:
        reasons.append("controlled_adapter_status_not_ready")
    if not request.step6g_post_route_bridge_ready:
        reasons.append("request_post_route_bridge_not_ready")
    if (
        request.step6g_post_route_bridge_status
        != BridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST
    ):
        reasons.append("request_post_route_bridge_status_not_ready")
    if not request.step6g_runtime_bridge_fake_ready:
        reasons.append("request_runtime_bridge_not_ready")
    if not request.step6g_controlled_adapter_fake_ready:
        reasons.append("request_controlled_adapter_not_ready")
    if request.source_bridge_status != bridge.status.value:
        reasons.append("source_bridge_status_mismatch")
    if request.source_runtime_bridge_status != runtime.status.value:
        reasons.append("source_runtime_bridge_status_mismatch")
    if request.source_controlled_adapter_status != controlled.status.value:
        reasons.append("source_controlled_adapter_status_mismatch")
    if not request.final_confirmation_exact_match:
        reasons.append("final_confirmation_exact_match_missing")
    if request.final_confirmation_reused:
        reasons.append("final_confirmation_reused")
    if not request.approval_artifact_reestablished:
        reasons.append("approval_artifact_reestablished_missing")
    if not request.approval_validation_passed:
        reasons.append("approval_validation_passed_missing")
    if not request.approval_exact_match:
        reasons.append("approval_exact_match_missing")
    if not request.final_confirmation_preflight_passed:
        reasons.append("final_confirmation_preflight_missing")
    if not request.post_immediate_preflight_passed:
        reasons.append("post_immediate_preflight_missing")
    if not request.order_intent_exact_match:
        reasons.append("order_intent_exact_match_missing")
    if request.symbol != SUPPORTED_SYMBOL:
        reasons.append("symbol_not_usd_jpy")
    if request.side != "BUY":
        reasons.append("side_not_buy")
    if request.size != LIVE_ORDER_CANDIDATE_SIZE:
        reasons.append("size_not_100")
    if request.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        reasons.append("execution_type_not_market")
    return tuple(reasons)


def _step4_spoofing_reasons(
    request: LiveOrderRealStep6GRealAdapterRequest,
) -> tuple[str, ...]:
    if request.step4_spoofing:
        return ("step4_spoofing",)
    return ()


def _real_transport_reasons(
    contract: LiveOrderRealStep6GRealTransportContract,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if contract.transport_mode is not TransportMode.STUB_ONLY:
        reasons.append("transport_mode_not_stub_only")
    if not contract.is_stub_transport:
        reasons.append("transport_not_stub")
    if contract.is_real_transport:
        reasons.append("transport_is_real")
    return tuple(reasons)


def _attempt_state_reasons(
    request: LiveOrderRealStep6GRealAdapterRequest,
    transport_result: LiveOrderRealStep6GStubTransportResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if request.post_attempt_limit != 1:
        reasons.append("post_attempt_limit_not_one")
    if request.post_attempt_count_before != 0:
        reasons.append("post_attempt_count_before_not_zero")
    if request.stub_attempt_count > 1:
        reasons.append("stub_attempt_count_exceeds_one")
    if request.post_executed:
        reasons.append("post_executed_unsafe")
    if request.post_allowed_this_step:
        reasons.append("post_allowed_this_step_unsafe_for_real_adapter")
    if request.allowed_for_live:
        reasons.append("allowed_for_live_unsafe")
    if request.allowed_for_live_persisted:
        reasons.append("allowed_for_live_persisted_unsafe")
    if transport_result and transport_result.stub_attempt_count > 1:
        reasons.append("stub_transport_attempt_count_exceeds_one")
    return tuple(reasons)


def _retry_or_loop_reasons(
    request: LiveOrderRealStep6GRealAdapterRequest,
    contract: LiveOrderRealStep6GRealTransportContract,
    transport_result: LiveOrderRealStep6GStubTransportResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(request, field_name):
            reasons.append(f"{field_name}_unsafe")
    if contract.retry_on_unknown:
        reasons.append("transport_retry_on_unknown")
    if contract.retry_on_timeout:
        reasons.append("transport_retry_on_timeout")
    if contract.retry_on_reject:
        reasons.append("transport_retry_on_reject")
    if transport_result:
        if transport_result.stub_retry_count:
            reasons.append("stub_transport_retry_count_non_zero")
        if transport_result.stub_loop_count:
            reasons.append("stub_transport_loop_count_non_zero")
    return tuple(reasons)


def _transport_unsafe_reasons(
    request: LiveOrderRealStep6GRealAdapterRequest,
    contract: LiveOrderRealStep6GRealTransportContract,
    transport_result: LiveOrderRealStep6GStubTransportResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if request.route_unsafe:
        reasons.append("route_unsafe")
    for field_name in (
        "can_execute_http_post",
        "can_call_order_endpoint",
        "can_call_live_order_once",
        "imports_http_client",
        "imports_private_api",
        "imports_broker",
        "imports_live_order_once",
    ):
        if getattr(contract, field_name):
            reasons.append(f"transport_{field_name}_unsafe")
    if contract.max_attempts != 1:
        reasons.append("transport_max_attempts_not_one")
    for field_name in (
        "real_http_post_executed",
        "order_endpoint_called",
        "live_order_once_called",
        "broker_order_path_called",
    ):
        if getattr(request, field_name):
            reasons.append(f"{field_name}_unsafe")
    if transport_result:
        for field_name in (
            "real_http_post_executed",
            "order_endpoint_called",
            "live_order_once_called",
            "broker_order_path_called",
        ):
            if getattr(transport_result, field_name):
                reasons.append(f"stub_transport_{field_name}_unsafe")
    return tuple(reasons)


def _raw_or_secret_exposure_reasons(
    request: LiveOrderRealStep6GRealAdapterRequest,
    contract: LiveOrderRealStep6GRealTransportContract,
    transport_result: LiveOrderRealStep6GStubTransportResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if request.raw_secret_id_exposure:
        reasons.append("raw_secret_id_exposure")
    for field_name in (
        "exposes_raw_request",
        "exposes_raw_response",
        "exposes_headers",
        "exposes_signature",
        "exposes_credentials",
        "exposes_real_ids",
        "returns_real_order_id",
        "returns_raw_response",
    ):
        if getattr(contract, field_name):
            reasons.append(f"transport_{field_name}_unsafe")
    if transport_result:
        for field_name in (
            "raw_request_present",
            "raw_response_present",
            "headers_present",
            "signature_present",
            "credentials_present",
            "real_order_id_present",
            "real_execution_id_present",
            "real_position_id_present",
            "real_client_order_id_present",
        ):
            if getattr(transport_result, field_name):
                reasons.append(f"stub_transport_{field_name}_unsafe")
        if not transport_result.result_is_stub:
            reasons.append("stub_transport_result_not_stub")
    return tuple(reasons)


def _unsupported_reasons(request: LiveOrderRealStep6GRealAdapterRequest) -> tuple[str, ...]:
    if request.adapter_mode is AdapterMode.STUB_TRANSPORT_ONLY_NO_API_NO_POST:
        return ()
    return ("unsupported_adapter_mode",)


def _build_check_results(
    *,
    request: LiveOrderRealStep6GRealAdapterRequest,
    transport_contract: LiveOrderRealStep6GRealTransportContract,
    transport_result: LiveOrderRealStep6GStubTransportResult | None,
) -> tuple[LiveOrderRealStep6GRealAdapterCheckResult, ...]:
    checks: list[LiveOrderRealStep6GRealAdapterCheckResult] = []
    transport_unsafe = _transport_unsafe_reasons(
        request, transport_contract, transport_result
    )
    retry_or_loop = _retry_or_loop_reasons(
        request, transport_contract, transport_result
    )
    raw_or_secret_exposure = _raw_or_secret_exposure_reasons(
        request, transport_contract, transport_result
    )

    def add(name: str, passed: bool, value: object, expected: str) -> None:
        checks.append(
            LiveOrderRealStep6GRealAdapterCheckResult(
                name=name,
                passed=passed,
                reason="passed" if passed else "blocked",
                sanitized_value=_safe_value(value),
                expected=expected,
            ),
        )

    add(
        "PB bridge ready",
        request.step6g_post_route_bridge_ready
        and request.step6g_post_route_bridge_status
        == BridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST,
        request.step6g_post_route_bridge_status,
        BridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST.value,
    )
    add(
        "EB runtime bridge ready",
        request.step6g_runtime_bridge_fake_ready,
        request.source_runtime_bridge_status,
        "fake ready or fake completed",
    )
    add(
        "AD controlled adapter ready",
        request.step6g_controlled_adapter_fake_ready,
        request.source_controlled_adapter_status,
        "fake ready or fake completed",
    )
    add(
        "final confirmation exact and not reused",
        request.final_confirmation_exact_match and not request.final_confirmation_reused,
        {
            "exact": request.final_confirmation_exact_match,
            "reused": request.final_confirmation_reused,
        },
        "exact=true reused=false",
    )
    add(
        "approval exact match",
        request.approval_artifact_reestablished
        and request.approval_validation_passed
        and request.approval_exact_match,
        request.approval_exact_match,
        "true",
    )
    add(
        "both preflights passed",
        request.final_confirmation_preflight_passed and request.post_immediate_preflight_passed,
        {
            "final": request.final_confirmation_preflight_passed,
            "post_immediate": request.post_immediate_preflight_passed,
        },
        "both true",
    )
    add(
        "order intent exact match",
        request.order_intent_exact_match
        and request.symbol == SUPPORTED_SYMBOL
        and request.side == "BUY"
        and request.size == LIVE_ORDER_CANDIDATE_SIZE
        and request.execution_type == LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
        f"{request.symbol} {request.side} {request.size} {request.execution_type}",
        f"{SUPPORTED_SYMBOL} BUY {LIVE_ORDER_CANDIDATE_SIZE} {LIVE_ORDER_CANDIDATE_EXECUTION_TYPE}",
    )
    add(
        "one stub attempt maximum",
        request.post_attempt_limit == 1
        and request.post_attempt_count_before == 0
        and request.stub_attempt_count <= 1,
        {
            "limit": request.post_attempt_limit,
            "before": request.post_attempt_count_before,
            "stub": request.stub_attempt_count,
        },
        "limit=1 before=0 stub<=1",
    )
    add(
        "transport stub only",
        transport_contract.transport_mode is TransportMode.STUB_ONLY
        and transport_contract.is_stub_transport
        and not transport_contract.is_real_transport,
        transport_contract.transport_mode.value,
        TransportMode.STUB_ONLY.value,
    )
    add(
        "transport cannot execute live path",
        not transport_unsafe,
        "none" if not transport_unsafe else "unsafe",
        "none",
    )
    add(
        "no retry loop order mutation",
        not retry_or_loop,
        "none" if not retry_or_loop else "unsafe",
        "none",
    )
    add(
        "no raw secret real ID exposure",
        not raw_or_secret_exposure,
        "none"
        if not raw_or_secret_exposure
        else "unsafe",
        "none",
    )
    add(
        "stub result stays stub",
        transport_result is None
        or (transport_result.stub_transport_attempted and transport_result.result_is_stub),
        "stub" if transport_result else "not_run",
        "stub or not_run",
    )
    return tuple(checks)


def _order_intent_exact_match(bridge: LiveOrderRealStep6GPostRouteBridgeResult) -> bool:
    snapshot = bridge.order_intent_snapshot
    return (
        snapshot.symbol == SUPPORTED_SYMBOL
        and snapshot.side == "BUY"
        and snapshot.size == LIVE_ORDER_CANDIDATE_SIZE
        and snapshot.executionType == LIVE_ORDER_CANDIDATE_EXECUTION_TYPE
        and not snapshot.codex_inferred_side
        and not snapshot.codex_inferred_symbol
        and not snapshot.codex_inferred_size
        and not snapshot.codex_inferred_execution_type
    )


def _source_has_step4_spoofing(bridge: LiveOrderRealStep6GPostRouteBridgeResult) -> bool:
    approval = bridge.approval_snapshot
    route = bridge.route_contract_snapshot
    return (
        approval.step4_approval_phrase_used
        or approval.step4_approval_phrase_spoofed
        or approval.step4_approval_gate_reused_as_step6g
        or route.uses_step4_approval_phrase
        or route.spoofs_step4_approval_phrase
        or route.mutates_step4_ledger_state
    )


def _source_route_is_unsafe(bridge: LiveOrderRealStep6GPostRouteBridgeResult) -> bool:
    route = bridge.route_contract_snapshot
    return (
        route.requires_step4_prepared_ledger
        or route.calls_live_order_once_directly
        or route.imports_live_order_once
        or route.imports_broker
        or route.imports_private_api
        or route.creates_new_order_endpoint
        or route.creates_new_payload_builder
        or route.order_endpoint_called
        or route.order_payload_generated
        or route.order_payload_sent
        or route.http_post_executed
        or route.retry_on_unknown
        or route.retry_on_timeout
        or route.retry_on_reject
    )


def _source_has_raw_or_secret_exposure(bridge: LiveOrderRealStep6GPostRouteBridgeResult) -> bool:
    approval = bridge.approval_snapshot
    preflight = bridge.preflight_snapshot
    route = bridge.route_contract_snapshot
    return (
        approval.approval_command_displayed
        or approval.approval_command_saved
        or approval.approval_command_copyable
        or approval.approval_command_pbcopy
        or approval.approval_command_full_text_present
        or preflight.raw_request_saved
        or preflight.raw_request_displayed
        or preflight.raw_response_saved
        or preflight.raw_response_displayed
        or preflight.headers_saved
        or preflight.headers_displayed
        or preflight.signature_saved
        or preflight.signature_displayed
        or preflight.credentials_displayed
        or preflight.order_ids_displayed
        or preflight.execution_ids_displayed
        or preflight.position_ids_displayed
        or preflight.client_order_ids_displayed
        or route.raw_request_displayed
        or route.raw_response_displayed
        or route.headers_displayed
        or route.signature_displayed
        or route.credentials_displayed
        or route.real_ids_displayed
    )


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise LiveVerificationValidationError("datetime value must be datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise LiveVerificationValidationError("datetime value must be timezone-aware")
    return value.astimezone(UTC)


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _safe_value(value: object) -> str:
    if isinstance(value, bool):
        return _bool_text(value)
    if isinstance(value, int | float | str):
        return str(value)
    if isinstance(value, dict):
        return ",".join(f"{key}={_safe_value(item)}" for key, item in sorted(value.items()))
    return value.__class__.__name__


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
