"""Step 6G controlled one-shot POST execution route.

This module implements the safe execution route contract for a later dedicated
real POST step. It does not import live_order_once, broker/private API clients,
HTTP clients, env readers, or ledger writers. Actual transport must be injected
by a later step after a new POST-specific confirmation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.live_order_real_one_shot_post_ready_gate_controlled import (
    SAFE_ONE_SHOT_POST_READY_GATE_LABEL,
    LiveOrderRealOneShotPostReadyGateControlledResult,
    LiveOrderRealOneShotPostReadyGateControlledStatus,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    SAFE_POST_RESULT_LABEL,
    SafePostResultCategory,
    SafeReconciliationStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

SAFE_ONE_SHOT_POST_EXECUTION_LABEL = "CONTROLLED_ONE_SHOT_POST_EXECUTION_ROUTE"
SAFE_EXECUTABLE_ORDER_PREVIEW_LABEL = "CONTROLLED_EXECUTABLE_ORDER_PREVIEW"
SAFE_POST_SPECIFIC_CONFIRMATION_LABEL = (
    "CONTROLLED_POST_SPECIFIC_CONFIRMATION_ADAPTER"
)
UNSUPPORTED_ONE_SHOT_POST_EXECUTION_LABEL = "UNSUPPORTED_REDACTED"
ONE_SHOT_POST_EXECUTION_RECOMMENDED_NEXT_STEP = (
    "one_shot_post_execution_gate_retry_requires_new_post_specific_confirmation"
)
ONE_SHOT_POST_EXECUTION_BLOCKED_NEXT_STEP = (
    "fix_one_shot_post_execution_route_blockers_no_post"
)
SAFE_TIME_IN_FORCE_LABEL = "NOT_PROVIDED_BY_SAFE_CANDIDATE"
SAFE_ENVIRONMENT_LABEL = "STEP6G_CONTROLLED_REAL_ROUTE"
SAFE_RISK_LABEL = "STEP6G_ONE_SHOT_SMALL_SIZE"


class LiveOrderRealOneShotPostExecutionControlledStatus(str, Enum):
    ONE_SHOT_POST_EXECUTION_ROUTE_NOT_READY = (
        "ONE_SHOT_POST_EXECUTION_ROUTE_NOT_READY"
    )
    ONE_SHOT_POST_EXECUTION_ROUTE_READY_NO_POST = (
        "ONE_SHOT_POST_EXECUTION_ROUTE_READY_NO_POST"
    )
    ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY = (
        "ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_PREREQUISITE = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_PREREQUISITE"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_SANITIZED_PREVIEW = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_SANITIZED_PREVIEW"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_ORDER_AMBIGUOUS = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_ORDER_AMBIGUOUS"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_POST_SPECIFIC_CONFIRMATION = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_POST_SPECIFIC_CONFIRMATION"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_CONFIRMATION_REUSED = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_CONFIRMATION_REUSED"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_TRANSPORT = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_TRANSPORT"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_RETRY_OR_SECOND_POST = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_RETRY_OR_SECOND_POST"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_TIMEOUT_FAIL_CLOSED = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_TIMEOUT_FAIL_CLOSED"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_UNKNOWN_FAIL_CLOSED = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_UNKNOWN_FAIL_CLOSED"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_UNAVAILABLE_FAIL_CLOSED = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_UNAVAILABLE_FAIL_CLOSED"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_FAILED_FAIL_CLOSED = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_FAILED_FAIL_CLOSED"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_LEDGER_OR_RECEIPT = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_LEDGER_OR_RECEIPT"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_RAW_EXPOSURE = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_RAW_EXPOSURE"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_ID_EXPOSURE = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_ID_EXPOSURE"
    )
    ONE_SHOT_POST_EXECUTION_BLOCKED_VALUE_EXPOSURE = (
        "ONE_SHOT_POST_EXECUTION_BLOCKED_VALUE_EXPOSURE"
    )


class LiveOrderRealExecutableOrderPreviewStatus(str, Enum):
    EXECUTABLE_ORDER_PREVIEW_AVAILABLE_SAFE_SUMMARY = (
        "EXECUTABLE_ORDER_PREVIEW_AVAILABLE_SAFE_SUMMARY"
    )
    EXECUTABLE_ORDER_PREVIEW_BLOCKED_MISSING_ORDER_CANDIDATE = (
        "EXECUTABLE_ORDER_PREVIEW_BLOCKED_MISSING_ORDER_CANDIDATE"
    )
    EXECUTABLE_ORDER_PREVIEW_BLOCKED_ORDER_AMBIGUITY = (
        "EXECUTABLE_ORDER_PREVIEW_BLOCKED_ORDER_AMBIGUITY"
    )
    EXECUTABLE_ORDER_PREVIEW_BLOCKED_PREREQUISITE = (
        "EXECUTABLE_ORDER_PREVIEW_BLOCKED_PREREQUISITE"
    )
    EXECUTABLE_ORDER_PREVIEW_BLOCKED_UNSAFE_EXPOSURE = (
        "EXECUTABLE_ORDER_PREVIEW_BLOCKED_UNSAFE_EXPOSURE"
    )


class LiveOrderRealPostSpecificConfirmationStatus(str, Enum):
    POST_SPECIFIC_CONFIRMATION_REQUIRED_NOT_RECEIVED = (
        "POST_SPECIFIC_CONFIRMATION_REQUIRED_NOT_RECEIVED"
    )
    POST_SPECIFIC_CONFIRMATION_VALIDATED_SAFE_SUMMARY = (
        "POST_SPECIFIC_CONFIRMATION_VALIDATED_SAFE_SUMMARY"
    )
    POST_SPECIFIC_CONFIRMATION_BLOCKED_NOT_CURRENT_TURN = (
        "POST_SPECIFIC_CONFIRMATION_BLOCKED_NOT_CURRENT_TURN"
    )
    POST_SPECIFIC_CONFIRMATION_BLOCKED_NOT_NEW_OR_ONE_TIME = (
        "POST_SPECIFIC_CONFIRMATION_BLOCKED_NOT_NEW_OR_ONE_TIME"
    )
    POST_SPECIFIC_CONFIRMATION_BLOCKED_REUSED = (
        "POST_SPECIFIC_CONFIRMATION_BLOCKED_REUSED"
    )
    POST_SPECIFIC_CONFIRMATION_BLOCKED_VALUE_EXPOSURE = (
        "POST_SPECIFIC_CONFIRMATION_BLOCKED_VALUE_EXPOSURE"
    )


class LiveOrderRealOneShotPostTransportResultCategory(str, Enum):
    TRANSPORT_ACCEPTED_SANITIZED = "TRANSPORT_ACCEPTED_SANITIZED"
    TRANSPORT_REJECTED_SANITIZED = "TRANSPORT_REJECTED_SANITIZED"
    TRANSPORT_FAILED_FAIL_CLOSED = "TRANSPORT_FAILED_FAIL_CLOSED"
    TRANSPORT_UNKNOWN_FAIL_CLOSED = "TRANSPORT_UNKNOWN_FAIL_CLOSED"
    TRANSPORT_TIMEOUT_FAIL_CLOSED = "TRANSPORT_TIMEOUT_FAIL_CLOSED"
    TRANSPORT_UNAVAILABLE_FAIL_CLOSED = "TRANSPORT_UNAVAILABLE_FAIL_CLOSED"


ExecutionStatus = LiveOrderRealOneShotPostExecutionControlledStatus
PreviewStatus = LiveOrderRealExecutableOrderPreviewStatus
PostSpecificConfirmationStatus = LiveOrderRealPostSpecificConfirmationStatus
TransportResultCategory = LiveOrderRealOneShotPostTransportResultCategory


@dataclass(frozen=True)
class LiveOrderRealExecutableOrderPreviewInput:
    execution_step: str = "ONE_SHOT_POST_EXECUTION_GATE"
    safe_preview_label: str = SAFE_EXECUTABLE_ORDER_PREVIEW_LABEL
    fresh_preflight_passed: bool = True
    final_confirmation_received: bool = True
    ready_gate_passed: bool = True
    post_guard_ready: bool = True
    one_post_max: bool = True
    retry_allowed: bool = False
    timeout_fail_closed: bool = True
    actual_post_requires_post_specific_confirmation: bool = True
    ledger_update_this_step: bool = False
    receipt_handoff_this_step: bool = False
    raw_exposure: bool = False
    id_exposure: bool = False
    credential_value_exposure: bool = False
    signature_value_exposure: bool = False
    headers_value_exposure: bool = False
    safe_order_candidate_available: bool = True
    order_ambiguity: bool = False
    symbol: str = SUPPORTED_SYMBOL
    side: str = LiveOrderCandidateSide.BUY.value
    order_type: str = LIVE_ORDER_CANDIDATE_EXECUTION_TYPE
    size: int = LIVE_ORDER_CANDIDATE_SIZE
    time_in_force_label: str = SAFE_TIME_IN_FORCE_LABEL
    environment_label: str = SAFE_ENVIRONMENT_LABEL
    risk_label: str = SAFE_RISK_LABEL
    safe_order_source_label: str = "STEP6G_REPO_DEFINED_ORDER_INTENT"
    codex_inferred_symbol: bool = False
    codex_inferred_side: bool = False
    codex_inferred_size: bool = False
    codex_inferred_order_type: bool = False

    def __post_init__(self) -> None:
        for field_name, value in (
            ("execution_step", self.execution_step),
            ("safe_preview_label", self.safe_preview_label),
            ("symbol", self.symbol),
            ("side", self.side),
            ("order_type", self.order_type),
            ("time_in_force_label", self.time_in_force_label),
            ("environment_label", self.environment_label),
            ("risk_label", self.risk_label),
            ("safe_order_source_label", self.safe_order_source_label),
        ):
            _require_non_empty(field_name, value)
        _validate_non_negative_int("size", self.size)
        _validate_bool_fields(self, _PREVIEW_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealExecutableOrderPreviewResult:
    status: LiveOrderRealExecutableOrderPreviewStatus
    sanitized_order_preview_available: bool
    order_ambiguity: bool
    execution_step: str
    safe_preview_label: str
    fresh_preflight_passed: bool
    final_confirmation_received: bool
    ready_gate_passed: bool
    post_guard_ready: bool
    one_post_max: bool
    retry_allowed: bool
    timeout_fail_closed: bool
    actual_post_requires_post_specific_confirmation: bool
    ledger_update_this_step: bool
    receipt_handoff_this_step: bool
    raw_exposure: bool
    id_exposure: bool
    credential_value_exposure: bool
    signature_value_exposure: bool
    headers_value_exposure: bool
    symbol: str
    side: str
    order_type: str
    size: int
    time_in_force_label: str
    environment_label: str
    risk_label: str
    safe_order_source_label: str
    codex_inferred_symbol: bool
    codex_inferred_side: bool
    codex_inferred_size: bool
    codex_inferred_order_type: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealExecutableOrderPreviewStatus):
            raise LiveVerificationValidationError("status must be preview status")
        _require_non_empty("execution_step", self.execution_step)
        _require_non_empty("safe_preview_label", self.safe_preview_label)
        _require_non_empty("symbol", self.symbol)
        _require_non_empty("side", self.side)
        _require_non_empty("order_type", self.order_type)
        _require_non_empty("time_in_force_label", self.time_in_force_label)
        _require_non_empty("environment_label", self.environment_label)
        _require_non_empty("risk_label", self.risk_label)
        _require_non_empty("safe_order_source_label", self.safe_order_source_label)
        _validate_non_negative_int("size", self.size)
        _validate_bool_fields(self, _PREVIEW_RESULT_BOOL_FIELDS)
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")


@dataclass(frozen=True)
class LiveOrderRealPostSpecificConfirmationInput:
    safe_confirmation_label: str = SAFE_POST_SPECIFIC_CONFIRMATION_LABEL
    post_specific_confirmation_required: bool = True
    post_specific_confirmation_received: bool = False
    post_specific_confirmation_current_turn: bool = False
    post_specific_confirmation_new: bool = False
    post_specific_confirmation_one_time: bool = False
    post_specific_confirmation_reused: bool = False
    final_confirmation_reused_as_post_confirmation: bool = False
    ready_gate_confirmation_reused_as_post_confirmation: bool = False
    previous_turn_confirmation_reused: bool = False
    step4_approval_phrase_reused: bool = False
    post_confirmation_actual_value_stored: bool = False
    post_confirmation_actual_value_reported: bool = False
    post_confirmation_actual_value_logged: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("safe_confirmation_label", self.safe_confirmation_label)
        _validate_bool_fields(self, _CONFIRMATION_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealPostSpecificConfirmationResult:
    status: LiveOrderRealPostSpecificConfirmationStatus
    post_specific_confirmation_adapter_ready: bool
    post_specific_confirmation_validated: bool
    safe_confirmation_label: str
    post_specific_confirmation_required: bool
    post_specific_confirmation_received: bool
    post_specific_confirmation_current_turn: bool
    post_specific_confirmation_new: bool
    post_specific_confirmation_one_time: bool
    post_specific_confirmation_reused: bool
    final_confirmation_reused_as_post_confirmation: bool
    ready_gate_confirmation_reused_as_post_confirmation: bool
    previous_turn_confirmation_reused: bool
    step4_approval_phrase_reused: bool
    post_confirmation_actual_value_stored: bool
    post_confirmation_actual_value_reported: bool
    post_confirmation_actual_value_logged: bool
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealPostSpecificConfirmationStatus):
            raise LiveVerificationValidationError(
                "status must be POST-specific confirmation status",
            )
        _require_non_empty("safe_confirmation_label", self.safe_confirmation_label)
        _validate_bool_fields(self, _CONFIRMATION_RESULT_BOOL_FIELDS)
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")


@dataclass(frozen=True)
class LiveOrderRealOneShotPostExecutionControlledInput:
    safe_post_execution_label: str = SAFE_ONE_SHOT_POST_EXECUTION_LABEL
    safe_post_result_label: str = SAFE_POST_RESULT_LABEL
    fresh_preflight_passed: bool = True
    fresh_preflight_current: bool = True
    fresh_preflight_new: bool = True
    fresh_preflight_reused: bool = False
    fresh_preflight_stale: bool = False
    final_confirmation_received: bool = True
    confirmation_current_turn: bool = True
    confirmation_new: bool = True
    confirmation_one_time: bool = True
    confirmation_reused: bool = False
    previous_turn_confirmation_reused: bool = False
    step4_approval_phrase_reused: bool = False
    ready_gate_passed: bool = True
    safe_ready_gate_label: str = SAFE_ONE_SHOT_POST_READY_GATE_LABEL
    ready_gate_status: str = (
        LiveOrderRealOneShotPostReadyGateControlledStatus
        .ONE_SHOT_POST_READY_GATE_PASSED_NO_POST
        .value
    )
    post_guard_ready: bool = True
    one_post_max: bool = True
    retry_allowed: bool = False
    timeout_fail_closed: bool = True
    final_readiness_ready: bool = True
    final_exec_stack_ready: bool = True
    sanitized_result_contract_ready: bool = True
    ledger_update_this_step: bool = False
    receipt_handoff_this_step: bool = False
    raw_exposure: bool = False
    id_exposure: bool = False
    credential_value_exposure: bool = False
    signature_value_exposure: bool = False
    headers_value_exposure: bool = False
    actual_http_post_executed: bool = False
    order_endpoint_executed: bool = False
    live_order_once_executed: bool = False
    ledger_updated: bool = False
    attempt_counter_persisted: bool = False
    actual_receipt_handoff_executed: bool = False
    fresh_preflight_reexecuted: bool = False
    final_confirmation_reobtained: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("safe_post_execution_label", self.safe_post_execution_label)
        _require_non_empty("safe_post_result_label", self.safe_post_result_label)
        _require_non_empty("safe_ready_gate_label", self.safe_ready_gate_label)
        _require_non_empty("ready_gate_status", self.ready_gate_status)
        _validate_bool_fields(self, _EXECUTION_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostTransportInput:
    execution_step: str
    symbol: str
    side: str
    order_type: str
    size: int
    time_in_force_label: str
    environment_label: str
    risk_label: str
    one_post_max: bool
    retry_allowed: bool
    timeout_fail_closed: bool
    allow_real_broker_post: bool = False

    def __post_init__(self) -> None:
        for field_name, value in (
            ("execution_step", self.execution_step),
            ("symbol", self.symbol),
            ("side", self.side),
            ("order_type", self.order_type),
            ("time_in_force_label", self.time_in_force_label),
            ("environment_label", self.environment_label),
            ("risk_label", self.risk_label),
        ):
            _require_non_empty(field_name, value)
        _validate_non_negative_int("size", self.size)
        _validate_bool_fields(
            self,
            (
                "one_post_max",
                "retry_allowed",
                "timeout_fail_closed",
                "allow_real_broker_post",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealOneShotPostTransportResult:
    result_category: LiveOrderRealOneShotPostTransportResultCategory
    fake_transport_used: bool = True
    http_post_executed: bool = False
    second_post_attempted: bool = False
    retry_attempted: bool = False
    timeout: bool = False
    unknown: bool = False
    unavailable: bool = False
    failed: bool = False
    ledger_updated: bool = False
    attempt_counter_persisted: bool = False
    actual_receipt_handoff_executed: bool = False
    raw_request_exposed: bool = False
    raw_response_exposed: bool = False
    broker_api_response_exposed: bool = False
    credential_value_exposed: bool = False
    signature_value_exposed: bool = False
    headers_value_exposed: bool = False
    real_id_exposed: bool = False
    account_id_exposed: bool = False
    order_id_exposed: bool = False
    transaction_id_exposed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(
            self.result_category,
            LiveOrderRealOneShotPostTransportResultCategory,
        ):
            raise LiveVerificationValidationError(
                "result_category must be transport result category",
            )
        _validate_bool_fields(self, _TRANSPORT_RESULT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostExecutionControlledResult:
    status: LiveOrderRealOneShotPostExecutionControlledStatus
    safe_post_execution_route_available: bool
    post_execution_allowed: bool
    post_attempted: bool
    http_post_executed: bool
    actual_http_post_executed: bool
    post_execution_count: int
    second_post_attempted: bool
    retry_attempted: bool
    fake_transport_used: bool
    transport_injected: bool
    safe_post_execution_label: str
    safe_post_execution_status: str
    safe_post_result_label: str
    safe_result_category: str
    safe_reconciliation_status: str
    sanitized_order_preview_available: bool
    order_ambiguity: bool
    post_specific_confirmation_adapter_ready: bool
    post_specific_confirmation_validated: bool
    post_specific_confirmation_required: bool
    post_specific_confirmation_received: bool
    post_specific_confirmation_current_turn: bool
    post_specific_confirmation_new: bool
    post_specific_confirmation_one_time: bool
    post_specific_confirmation_reused: bool
    final_confirmation_reused_as_post_confirmation: bool
    ready_gate_confirmation_reused_as_post_confirmation: bool
    previous_turn_confirmation_reused: bool
    step4_approval_phrase_reused: bool
    post_confirmation_actual_value_stored: bool
    post_confirmation_actual_value_reported: bool
    post_confirmation_actual_value_logged: bool
    fresh_preflight_passed: bool
    final_confirmation_received: bool
    ready_gate_passed: bool
    post_guard_ready: bool
    one_post_max: bool
    retry_allowed: bool
    timeout_fail_closed: bool
    final_readiness_ready: bool
    final_exec_stack_ready: bool
    sanitized_result_contract_ready: bool
    ledger_update_this_step: bool
    receipt_handoff_this_step: bool
    ledger_updated: bool
    attempt_counter_persisted: bool
    actual_receipt_handoff_executed: bool
    raw_request_exposed: bool
    raw_response_exposed: bool
    broker_api_response_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool
    real_id_exposed: bool
    account_id_exposed: bool
    order_id_exposed: bool
    transaction_id_exposed: bool
    order_endpoint_executed: bool
    live_order_once_executed: bool
    fresh_preflight_reexecuted: bool
    final_confirmation_reobtained: bool
    preview: LiveOrderRealExecutableOrderPreviewResult
    confirmation: LiveOrderRealPostSpecificConfirmationResult
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealOneShotPostExecutionControlledStatus,
        ):
            raise LiveVerificationValidationError("status must be execution status")
        _require_non_empty("safe_post_execution_label", self.safe_post_execution_label)
        _require_non_empty("safe_post_execution_status", self.safe_post_execution_status)
        _require_non_empty("safe_post_result_label", self.safe_post_result_label)
        _require_non_empty("safe_result_category", self.safe_result_category)
        _require_non_empty(
            "safe_reconciliation_status",
            self.safe_reconciliation_status,
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_non_negative_int("post_execution_count", self.post_execution_count)
        _validate_bool_fields(self, _EXECUTION_RESULT_BOOL_FIELDS)
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_execution_result_safety(self)


ControlledTransport = Callable[
    [LiveOrderRealOneShotPostTransportInput],
    LiveOrderRealOneShotPostTransportResult,
]


def build_live_order_real_executable_order_preview(
    input_snapshot: LiveOrderRealExecutableOrderPreviewInput | None = None,
) -> LiveOrderRealExecutableOrderPreviewResult:
    """Build the safe executable order preview without payload or API details."""
    snapshot = input_snapshot or LiveOrderRealExecutableOrderPreviewInput()
    status, reasons = _preview_status(snapshot)
    available = (
        status
        is PreviewStatus.EXECUTABLE_ORDER_PREVIEW_AVAILABLE_SAFE_SUMMARY
    )
    order_ambiguity = snapshot.order_ambiguity or not available

    return LiveOrderRealExecutableOrderPreviewResult(
        status=status,
        sanitized_order_preview_available=available,
        order_ambiguity=order_ambiguity,
        execution_step=_safe_label(
            snapshot.execution_step,
            "ONE_SHOT_POST_EXECUTION_GATE",
        ),
        safe_preview_label=_safe_label(
            snapshot.safe_preview_label,
            SAFE_EXECUTABLE_ORDER_PREVIEW_LABEL,
        ),
        fresh_preflight_passed=snapshot.fresh_preflight_passed,
        final_confirmation_received=snapshot.final_confirmation_received,
        ready_gate_passed=snapshot.ready_gate_passed,
        post_guard_ready=snapshot.post_guard_ready,
        one_post_max=snapshot.one_post_max,
        retry_allowed=snapshot.retry_allowed,
        timeout_fail_closed=snapshot.timeout_fail_closed,
        actual_post_requires_post_specific_confirmation=(
            snapshot.actual_post_requires_post_specific_confirmation
        ),
        ledger_update_this_step=False,
        receipt_handoff_this_step=False,
        raw_exposure=False,
        id_exposure=False,
        credential_value_exposure=False,
        signature_value_exposure=False,
        headers_value_exposure=False,
        symbol=snapshot.symbol if available else UNSUPPORTED_ONE_SHOT_POST_EXECUTION_LABEL,
        side=snapshot.side if available else UNSUPPORTED_ONE_SHOT_POST_EXECUTION_LABEL,
        order_type=(
            snapshot.order_type
            if available
            else UNSUPPORTED_ONE_SHOT_POST_EXECUTION_LABEL
        ),
        size=snapshot.size if available else 0,
        time_in_force_label=_safe_text_label(snapshot.time_in_force_label),
        environment_label=_safe_text_label(snapshot.environment_label),
        risk_label=_safe_text_label(snapshot.risk_label),
        safe_order_source_label=_safe_text_label(snapshot.safe_order_source_label),
        codex_inferred_symbol=False,
        codex_inferred_side=False,
        codex_inferred_size=False,
        codex_inferred_order_type=False,
        blocked_reasons=reasons,
    )


def validate_live_order_real_post_specific_confirmation(
    input_snapshot: LiveOrderRealPostSpecificConfirmationInput | None = None,
) -> LiveOrderRealPostSpecificConfirmationResult:
    """Validate POST-specific confirmation using safe booleans only."""
    snapshot = input_snapshot or LiveOrderRealPostSpecificConfirmationInput()
    status, reasons = _confirmation_status(snapshot)
    validated = (
        status
        is PostSpecificConfirmationStatus
        .POST_SPECIFIC_CONFIRMATION_VALIDATED_SAFE_SUMMARY
    )
    return LiveOrderRealPostSpecificConfirmationResult(
        status=status,
        post_specific_confirmation_adapter_ready=True,
        post_specific_confirmation_validated=validated,
        safe_confirmation_label=_safe_label(
            snapshot.safe_confirmation_label,
            SAFE_POST_SPECIFIC_CONFIRMATION_LABEL,
        ),
        post_specific_confirmation_required=(
            snapshot.post_specific_confirmation_required
        ),
        post_specific_confirmation_received=(
            snapshot.post_specific_confirmation_received
        ),
        post_specific_confirmation_current_turn=(
            snapshot.post_specific_confirmation_current_turn
        ),
        post_specific_confirmation_new=snapshot.post_specific_confirmation_new,
        post_specific_confirmation_one_time=(
            snapshot.post_specific_confirmation_one_time
        ),
        post_specific_confirmation_reused=(
            snapshot.post_specific_confirmation_reused
        ),
        final_confirmation_reused_as_post_confirmation=(
            snapshot.final_confirmation_reused_as_post_confirmation
        ),
        ready_gate_confirmation_reused_as_post_confirmation=(
            snapshot.ready_gate_confirmation_reused_as_post_confirmation
        ),
        previous_turn_confirmation_reused=snapshot.previous_turn_confirmation_reused,
        step4_approval_phrase_reused=snapshot.step4_approval_phrase_reused,
        post_confirmation_actual_value_stored=False,
        post_confirmation_actual_value_reported=False,
        post_confirmation_actual_value_logged=False,
        blocked_reasons=reasons,
    )


def build_live_order_real_one_shot_post_execution_controlled(
    *,
    input_snapshot: LiveOrderRealOneShotPostExecutionControlledInput | None = None,
    preview: LiveOrderRealExecutableOrderPreviewResult | None = None,
    confirmation: LiveOrderRealPostSpecificConfirmationResult | None = None,
    ready_gate_result: LiveOrderRealOneShotPostReadyGateControlledResult
    | None = None,
) -> LiveOrderRealOneShotPostExecutionControlledResult:
    """Build route readiness without invoking transport or executing POST."""
    snapshot = _merge_ready_gate(
        input_snapshot or LiveOrderRealOneShotPostExecutionControlledInput(),
        ready_gate_result,
    )
    preview_result = preview or build_live_order_real_executable_order_preview(
        _preview_input_from_execution(snapshot),
    )
    confirmation_result = confirmation or validate_live_order_real_post_specific_confirmation()
    status, reasons = _route_status(
        snapshot=snapshot,
        preview=preview_result,
    )
    return _build_execution_result(
        status=status,
        snapshot=snapshot,
        preview=preview_result,
        confirmation=confirmation_result,
        transport_injected=False,
        post_attempted=False,
        post_execution_count=0,
        fake_transport_used=False,
        transport_result=None,
        primary_reasons=reasons,
    )


def execute_live_order_real_one_shot_post_execution_controlled(
    *,
    transport: ControlledTransport | None,
    input_snapshot: LiveOrderRealOneShotPostExecutionControlledInput | None = None,
    preview: LiveOrderRealExecutableOrderPreviewResult | None = None,
    confirmation: LiveOrderRealPostSpecificConfirmationResult | None = None,
    ready_gate_result: LiveOrderRealOneShotPostReadyGateControlledResult
    | None = None,
) -> LiveOrderRealOneShotPostExecutionControlledResult:
    """Execute the injected transport at most once when all safe gates pass."""
    snapshot = _merge_ready_gate(
        input_snapshot or LiveOrderRealOneShotPostExecutionControlledInput(),
        ready_gate_result,
    )
    preview_result = preview or build_live_order_real_executable_order_preview(
        _preview_input_from_execution(snapshot),
    )
    confirmation_result = confirmation or validate_live_order_real_post_specific_confirmation()
    pre_status, pre_reasons = _execution_pre_status(
        snapshot=snapshot,
        preview=preview_result,
        confirmation=confirmation_result,
        transport_injected=transport is not None,
    )
    if pre_status is not None or transport is None:
        return _build_execution_result(
            status=pre_status
            or ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_TRANSPORT,
            snapshot=snapshot,
            preview=preview_result,
            confirmation=confirmation_result,
            transport_injected=transport is not None,
            post_attempted=False,
            post_execution_count=0,
            fake_transport_used=False,
            transport_result=None,
            primary_reasons=pre_reasons or ("transport_missing",),
        )

    transport_input = LiveOrderRealOneShotPostTransportInput(
        execution_step=preview_result.execution_step,
        symbol=preview_result.symbol,
        side=preview_result.side,
        order_type=preview_result.order_type,
        size=preview_result.size,
        time_in_force_label=preview_result.time_in_force_label,
        environment_label=preview_result.environment_label,
        risk_label=preview_result.risk_label,
        one_post_max=snapshot.one_post_max,
        retry_allowed=snapshot.retry_allowed,
        timeout_fail_closed=snapshot.timeout_fail_closed,
    )
    transport_result = transport(transport_input)
    status, reasons = _transport_status(transport_result)
    return _build_execution_result(
        status=status,
        snapshot=snapshot,
        preview=preview_result,
        confirmation=confirmation_result,
        transport_injected=True,
        post_attempted=True,
        post_execution_count=1,
        fake_transport_used=transport_result.fake_transport_used,
        transport_result=transport_result,
        primary_reasons=reasons,
    )


def render_live_order_real_one_shot_post_execution_controlled_markdown(
    result: LiveOrderRealOneShotPostExecutionControlledResult,
) -> str:
    """Render a safe one-shot POST execution route summary."""
    lines = [
        "# Step 6G One-Shot POST Execution Controlled",
        "",
        "This is a controlled route summary.",
        "It contains safe labels, statuses, booleans, counts, and categories.",
        "It does not expose raw request, raw response, broker/API response, IDs,",
        "credential values, signature values, headers values, confirmation values,",
        "or ledger state values.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- safe_post_execution_route_available: "
            f"{_bool_text(result.safe_post_execution_route_available)}"
        ),
        f"- post_execution_allowed: {_bool_text(result.post_execution_allowed)}",
        f"- post_attempted: {_bool_text(result.post_attempted)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- post_execution_count: {result.post_execution_count}",
        f"- second_post_attempted: {_bool_text(result.second_post_attempted)}",
        f"- retry_attempted: {_bool_text(result.retry_attempted)}",
        f"- fake_transport_used: {_bool_text(result.fake_transport_used)}",
        f"- transport_injected: {_bool_text(result.transport_injected)}",
        f"- safe_post_execution_label: {result.safe_post_execution_label}",
        f"- safe_post_execution_status: {result.safe_post_execution_status}",
        f"- safe_result_category: {result.safe_result_category}",
        f"- safe_reconciliation_status: {result.safe_reconciliation_status}",
        "",
        "## Preview",
        (
            "- sanitized_order_preview_available: "
            f"{_bool_text(result.sanitized_order_preview_available)}"
        ),
        f"- order_ambiguity: {_bool_text(result.order_ambiguity)}",
        f"- symbol: {result.preview.symbol}",
        f"- side: {result.preview.side}",
        f"- order_type: {result.preview.order_type}",
        f"- size: {result.preview.size}",
        f"- time_in_force_label: {result.preview.time_in_force_label}",
        f"- environment_label: {result.preview.environment_label}",
        f"- risk_label: {result.preview.risk_label}",
        "",
        "## POST-Specific Confirmation",
        (
            "- post_specific_confirmation_required: "
            f"{_bool_text(result.post_specific_confirmation_required)}"
        ),
        (
            "- post_specific_confirmation_received: "
            f"{_bool_text(result.post_specific_confirmation_received)}"
        ),
        (
            "- post_specific_confirmation_current_turn: "
            f"{_bool_text(result.post_specific_confirmation_current_turn)}"
        ),
        f"- post_specific_confirmation_new: {_bool_text(result.post_specific_confirmation_new)}",
        (
            "- post_specific_confirmation_one_time: "
            f"{_bool_text(result.post_specific_confirmation_one_time)}"
        ),
        (
            "- post_specific_confirmation_reused: "
            f"{_bool_text(result.post_specific_confirmation_reused)}"
        ),
        (
            "- final_confirmation_reused_as_post_confirmation: "
            f"{_bool_text(result.final_confirmation_reused_as_post_confirmation)}"
        ),
        (
            "- ready_gate_confirmation_reused_as_post_confirmation: "
            f"{_bool_text(result.ready_gate_confirmation_reused_as_post_confirmation)}"
        ),
        (
            "- previous_turn_confirmation_reused: "
            f"{_bool_text(result.previous_turn_confirmation_reused)}"
        ),
        f"- step4_approval_phrase_reused: {_bool_text(result.step4_approval_phrase_reused)}",
        (
            "- post_confirmation_actual_value_stored: "
            f"{_bool_text(result.post_confirmation_actual_value_stored)}"
        ),
        (
            "- post_confirmation_actual_value_reported: "
            f"{_bool_text(result.post_confirmation_actual_value_reported)}"
        ),
        (
            "- post_confirmation_actual_value_logged: "
            f"{_bool_text(result.post_confirmation_actual_value_logged)}"
        ),
        "",
        "## Safety",
        f"- ledger_updated: {_bool_text(result.ledger_updated)}",
        f"- attempt_counter_persisted: {_bool_text(result.attempt_counter_persisted)}",
        (
            "- actual_receipt_handoff_executed: "
            f"{_bool_text(result.actual_receipt_handoff_executed)}"
        ),
        f"- raw_request_exposed: {_bool_text(result.raw_request_exposed)}",
        f"- raw_response_exposed: {_bool_text(result.raw_response_exposed)}",
        (
            "- broker_api_response_exposed: "
            f"{_bool_text(result.broker_api_response_exposed)}"
        ),
        f"- credential_value_exposed: {_bool_text(result.credential_value_exposed)}",
        f"- signature_value_exposed: {_bool_text(result.signature_value_exposed)}",
        f"- headers_value_exposed: {_bool_text(result.headers_value_exposed)}",
        f"- real_id_exposed: {_bool_text(result.real_id_exposed)}",
        f"- order_endpoint_executed: {_bool_text(result.order_endpoint_executed)}",
        f"- live_order_once_executed: {_bool_text(result.live_order_once_executed)}",
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def _preview_status(
    snapshot: LiveOrderRealExecutableOrderPreviewInput,
) -> tuple[LiveOrderRealExecutableOrderPreviewStatus, tuple[str, ...]]:
    prereq_reasons = _preview_prerequisite_reasons(snapshot)
    if prereq_reasons:
        return PreviewStatus.EXECUTABLE_ORDER_PREVIEW_BLOCKED_PREREQUISITE, prereq_reasons
    exposure_reasons = _preview_exposure_reasons(snapshot)
    if exposure_reasons:
        return PreviewStatus.EXECUTABLE_ORDER_PREVIEW_BLOCKED_UNSAFE_EXPOSURE, exposure_reasons
    if not snapshot.safe_order_candidate_available:
        return (
            PreviewStatus.EXECUTABLE_ORDER_PREVIEW_BLOCKED_MISSING_ORDER_CANDIDATE,
            ("safe_order_candidate_missing",),
        )
    ambiguity_reasons = _order_ambiguity_reasons(snapshot)
    if ambiguity_reasons:
        return (
            PreviewStatus.EXECUTABLE_ORDER_PREVIEW_BLOCKED_ORDER_AMBIGUITY,
            ambiguity_reasons,
        )
    return PreviewStatus.EXECUTABLE_ORDER_PREVIEW_AVAILABLE_SAFE_SUMMARY, ()


def _confirmation_status(
    snapshot: LiveOrderRealPostSpecificConfirmationInput,
) -> tuple[LiveOrderRealPostSpecificConfirmationStatus, tuple[str, ...]]:
    if _confirmation_value_exposure(snapshot):
        return (
            PostSpecificConfirmationStatus
            .POST_SPECIFIC_CONFIRMATION_BLOCKED_VALUE_EXPOSURE,
            ("post_confirmation_actual_value_exposure",),
        )
    if _confirmation_reused(snapshot):
        return (
            PostSpecificConfirmationStatus.POST_SPECIFIC_CONFIRMATION_BLOCKED_REUSED,
            _confirmation_reuse_reasons(snapshot),
        )
    if (
        snapshot.post_specific_confirmation_required
        and not snapshot.post_specific_confirmation_received
    ):
        return (
            PostSpecificConfirmationStatus
            .POST_SPECIFIC_CONFIRMATION_REQUIRED_NOT_RECEIVED,
            ("post_specific_confirmation_missing",),
        )
    if not snapshot.post_specific_confirmation_current_turn:
        return (
            PostSpecificConfirmationStatus
            .POST_SPECIFIC_CONFIRMATION_BLOCKED_NOT_CURRENT_TURN,
            ("post_specific_confirmation_not_current_turn",),
        )
    if (
        not snapshot.post_specific_confirmation_new
        or not snapshot.post_specific_confirmation_one_time
    ):
        return (
            PostSpecificConfirmationStatus
            .POST_SPECIFIC_CONFIRMATION_BLOCKED_NOT_NEW_OR_ONE_TIME,
            ("post_specific_confirmation_not_new_or_one_time",),
        )
    return (
        PostSpecificConfirmationStatus
        .POST_SPECIFIC_CONFIRMATION_VALIDATED_SAFE_SUMMARY,
        (),
    )


def _route_status(
    *,
    snapshot: LiveOrderRealOneShotPostExecutionControlledInput,
    preview: LiveOrderRealExecutableOrderPreviewResult,
) -> tuple[LiveOrderRealOneShotPostExecutionControlledStatus, tuple[str, ...]]:
    prereq_reasons = _execution_prerequisite_reasons(snapshot)
    if prereq_reasons:
        return (
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_PREREQUISITE,
            prereq_reasons,
        )
    unsafe_reasons = _execution_unsafe_reasons(snapshot)
    if unsafe_reasons:
        return _status_from_unsafe_reasons(unsafe_reasons), unsafe_reasons
    if not preview.sanitized_order_preview_available:
        return (
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_SANITIZED_PREVIEW,
            _prefix_reasons("preview", preview.blocked_reasons),
        )
    if preview.order_ambiguity:
        return (
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_ORDER_AMBIGUOUS,
            ("order_ambiguity",),
        )
    return ExecutionStatus.ONE_SHOT_POST_EXECUTION_ROUTE_READY_NO_POST, ()


def _execution_pre_status(
    *,
    snapshot: LiveOrderRealOneShotPostExecutionControlledInput,
    preview: LiveOrderRealExecutableOrderPreviewResult,
    confirmation: LiveOrderRealPostSpecificConfirmationResult,
    transport_injected: bool,
) -> tuple[LiveOrderRealOneShotPostExecutionControlledStatus | None, tuple[str, ...]]:
    route_status, route_reasons = _route_status(snapshot=snapshot, preview=preview)
    if route_status is not ExecutionStatus.ONE_SHOT_POST_EXECUTION_ROUTE_READY_NO_POST:
        return route_status, route_reasons
    if not confirmation.post_specific_confirmation_validated:
        if (
            confirmation.status
            is PostSpecificConfirmationStatus.POST_SPECIFIC_CONFIRMATION_BLOCKED_REUSED
        ):
            return (
                ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_CONFIRMATION_REUSED,
                _prefix_reasons("confirmation", confirmation.blocked_reasons),
            )
        return (
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_POST_SPECIFIC_CONFIRMATION,
            _prefix_reasons("confirmation", confirmation.blocked_reasons),
        )
    if not transport_injected:
        return (
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_TRANSPORT,
            ("transport_missing",),
        )
    return None, ()


def _transport_status(
    transport_result: LiveOrderRealOneShotPostTransportResult,
) -> tuple[LiveOrderRealOneShotPostExecutionControlledStatus, tuple[str, ...]]:
    unsafe_reasons = _transport_unsafe_reasons(transport_result)
    if unsafe_reasons:
        return _status_from_unsafe_reasons(unsafe_reasons), unsafe_reasons
    if (
        transport_result.retry_attempted
        or transport_result.second_post_attempted
    ):
        return (
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_RETRY_OR_SECOND_POST,
            ("retry_or_second_post_attempted",),
        )
    category = transport_result.result_category
    if category is TransportResultCategory.TRANSPORT_ACCEPTED_SANITIZED:
        return (
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY,
            (),
        )
    if category is TransportResultCategory.TRANSPORT_REJECTED_SANITIZED:
        return (
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_FAILED_FAIL_CLOSED,
            ("transport_rejected_sanitized",),
        )
    if category is TransportResultCategory.TRANSPORT_FAILED_FAIL_CLOSED:
        return (
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_FAILED_FAIL_CLOSED,
            ("transport_failed_fail_closed",),
        )
    if category is TransportResultCategory.TRANSPORT_TIMEOUT_FAIL_CLOSED:
        return (
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_TIMEOUT_FAIL_CLOSED,
            ("transport_timeout_fail_closed",),
        )
    if category is TransportResultCategory.TRANSPORT_UNAVAILABLE_FAIL_CLOSED:
        return (
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_UNAVAILABLE_FAIL_CLOSED,
            ("transport_unavailable_fail_closed",),
        )
    return (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_UNKNOWN_FAIL_CLOSED,
        ("transport_unknown_fail_closed",),
    )


def _build_execution_result(
    *,
    status: LiveOrderRealOneShotPostExecutionControlledStatus,
    snapshot: LiveOrderRealOneShotPostExecutionControlledInput,
    preview: LiveOrderRealExecutableOrderPreviewResult,
    confirmation: LiveOrderRealPostSpecificConfirmationResult,
    transport_injected: bool,
    post_attempted: bool,
    post_execution_count: int,
    fake_transport_used: bool,
    transport_result: LiveOrderRealOneShotPostTransportResult | None,
    primary_reasons: tuple[str, ...],
) -> LiveOrderRealOneShotPostExecutionControlledResult:
    route_available = (
        status is ExecutionStatus.ONE_SHOT_POST_EXECUTION_ROUTE_READY_NO_POST
        or status
        is ExecutionStatus.ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY
        or post_attempted
    )
    accepted = (
        status
        is ExecutionStatus.ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY
    )
    safe_result_category = _safe_result_category(status).value
    safe_reconciliation_status = (
        SafeReconciliationStatus.RECONCILIATION_READY_NO_RECEIPT_HANDOFF.value
        if accepted
        else SafeReconciliationStatus.RECONCILIATION_BLOCKED_NOT_READY.value
    )
    return LiveOrderRealOneShotPostExecutionControlledResult(
        status=status,
        safe_post_execution_route_available=route_available,
        post_execution_allowed=accepted,
        post_attempted=post_attempted,
        http_post_executed=bool(transport_result and transport_result.http_post_executed),
        actual_http_post_executed=(
            bool(transport_result and transport_result.http_post_executed)
        ),
        post_execution_count=post_execution_count,
        second_post_attempted=False,
        retry_attempted=False,
        fake_transport_used=fake_transport_used,
        transport_injected=transport_injected,
        safe_post_execution_label=_safe_label(
            snapshot.safe_post_execution_label,
            SAFE_ONE_SHOT_POST_EXECUTION_LABEL,
        ),
        safe_post_execution_status=status.value,
        safe_post_result_label=_safe_label(
            snapshot.safe_post_result_label,
            SAFE_POST_RESULT_LABEL,
        ),
        safe_result_category=safe_result_category,
        safe_reconciliation_status=safe_reconciliation_status,
        sanitized_order_preview_available=preview.sanitized_order_preview_available,
        order_ambiguity=preview.order_ambiguity,
        post_specific_confirmation_adapter_ready=(
            confirmation.post_specific_confirmation_adapter_ready
        ),
        post_specific_confirmation_validated=(
            confirmation.post_specific_confirmation_validated
        ),
        post_specific_confirmation_required=(
            confirmation.post_specific_confirmation_required
        ),
        post_specific_confirmation_received=(
            confirmation.post_specific_confirmation_received
        ),
        post_specific_confirmation_current_turn=(
            confirmation.post_specific_confirmation_current_turn
        ),
        post_specific_confirmation_new=confirmation.post_specific_confirmation_new,
        post_specific_confirmation_one_time=(
            confirmation.post_specific_confirmation_one_time
        ),
        post_specific_confirmation_reused=(
            confirmation.post_specific_confirmation_reused
        ),
        final_confirmation_reused_as_post_confirmation=(
            confirmation.final_confirmation_reused_as_post_confirmation
        ),
        ready_gate_confirmation_reused_as_post_confirmation=(
            confirmation.ready_gate_confirmation_reused_as_post_confirmation
        ),
        previous_turn_confirmation_reused=(
            confirmation.previous_turn_confirmation_reused
        ),
        step4_approval_phrase_reused=confirmation.step4_approval_phrase_reused,
        post_confirmation_actual_value_stored=False,
        post_confirmation_actual_value_reported=False,
        post_confirmation_actual_value_logged=False,
        fresh_preflight_passed=snapshot.fresh_preflight_passed,
        final_confirmation_received=snapshot.final_confirmation_received,
        ready_gate_passed=snapshot.ready_gate_passed,
        post_guard_ready=snapshot.post_guard_ready,
        one_post_max=snapshot.one_post_max,
        retry_allowed=snapshot.retry_allowed,
        timeout_fail_closed=snapshot.timeout_fail_closed,
        final_readiness_ready=snapshot.final_readiness_ready,
        final_exec_stack_ready=snapshot.final_exec_stack_ready,
        sanitized_result_contract_ready=snapshot.sanitized_result_contract_ready,
        ledger_update_this_step=False,
        receipt_handoff_this_step=False,
        ledger_updated=False,
        attempt_counter_persisted=False,
        actual_receipt_handoff_executed=False,
        raw_request_exposed=False,
        raw_response_exposed=False,
        broker_api_response_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
        real_id_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
        order_endpoint_executed=False,
        live_order_once_executed=False,
        fresh_preflight_reexecuted=False,
        final_confirmation_reobtained=False,
        preview=preview,
        confirmation=confirmation,
        blocked_reasons=_merge_reasons(primary_reasons),
        recommended_next_step=(
            "post_result_reconciliation_gate_no_retry_no_repost"
            if accepted
            else (
                ONE_SHOT_POST_EXECUTION_RECOMMENDED_NEXT_STEP
                if route_available
                else ONE_SHOT_POST_EXECUTION_BLOCKED_NEXT_STEP
            )
        ),
    )


def _merge_ready_gate(
    snapshot: LiveOrderRealOneShotPostExecutionControlledInput,
    ready_gate_result: LiveOrderRealOneShotPostReadyGateControlledResult | None,
) -> LiveOrderRealOneShotPostExecutionControlledInput:
    if ready_gate_result is None:
        return snapshot
    return LiveOrderRealOneShotPostExecutionControlledInput(
        safe_post_execution_label=snapshot.safe_post_execution_label,
        safe_post_result_label=snapshot.safe_post_result_label,
        fresh_preflight_passed=ready_gate_result.fresh_preflight_passed,
        fresh_preflight_current=ready_gate_result.fresh_preflight_current,
        fresh_preflight_new=ready_gate_result.fresh_preflight_new,
        fresh_preflight_reused=ready_gate_result.fresh_preflight_reused,
        fresh_preflight_stale=ready_gate_result.fresh_preflight_stale,
        final_confirmation_received=ready_gate_result.final_confirmation_received,
        confirmation_current_turn=ready_gate_result.confirmation_current_turn,
        confirmation_new=ready_gate_result.confirmation_new,
        confirmation_one_time=ready_gate_result.confirmation_one_time,
        confirmation_reused=ready_gate_result.confirmation_reused,
        previous_turn_confirmation_reused=(
            ready_gate_result.previous_turn_confirmation_reused
        ),
        step4_approval_phrase_reused=ready_gate_result.step4_approval_phrase_reused,
        ready_gate_passed=ready_gate_result.ready_gate_passed,
        safe_ready_gate_label=ready_gate_result.safe_one_shot_post_ready_gate_label,
        ready_gate_status=ready_gate_result.safe_one_shot_post_ready_gate_status,
        post_guard_ready=ready_gate_result.post_guard_ready,
        one_post_max=ready_gate_result.one_post_max,
        retry_allowed=ready_gate_result.retry_allowed,
        timeout_fail_closed=ready_gate_result.timeout_fail_closed,
        final_readiness_ready=ready_gate_result.final_readiness_ready,
        final_exec_stack_ready=ready_gate_result.final_exec_stack_ready,
        sanitized_result_contract_ready=(
            ready_gate_result.sanitized_result_contract_ready
        ),
        ledger_update_this_step=snapshot.ledger_update_this_step,
        receipt_handoff_this_step=snapshot.receipt_handoff_this_step,
        raw_exposure=snapshot.raw_exposure,
        id_exposure=snapshot.id_exposure,
        credential_value_exposure=snapshot.credential_value_exposure,
        signature_value_exposure=snapshot.signature_value_exposure,
        headers_value_exposure=snapshot.headers_value_exposure,
        actual_http_post_executed=snapshot.actual_http_post_executed,
        order_endpoint_executed=snapshot.order_endpoint_executed,
        live_order_once_executed=snapshot.live_order_once_executed,
        ledger_updated=snapshot.ledger_updated,
        attempt_counter_persisted=snapshot.attempt_counter_persisted,
        actual_receipt_handoff_executed=snapshot.actual_receipt_handoff_executed,
        fresh_preflight_reexecuted=snapshot.fresh_preflight_reexecuted,
        final_confirmation_reobtained=snapshot.final_confirmation_reobtained,
    )


def _preview_input_from_execution(
    snapshot: LiveOrderRealOneShotPostExecutionControlledInput,
) -> LiveOrderRealExecutableOrderPreviewInput:
    return LiveOrderRealExecutableOrderPreviewInput(
        fresh_preflight_passed=snapshot.fresh_preflight_passed,
        final_confirmation_received=snapshot.final_confirmation_received,
        ready_gate_passed=snapshot.ready_gate_passed,
        post_guard_ready=snapshot.post_guard_ready,
        one_post_max=snapshot.one_post_max,
        retry_allowed=snapshot.retry_allowed,
        timeout_fail_closed=snapshot.timeout_fail_closed,
        ledger_update_this_step=snapshot.ledger_update_this_step,
        receipt_handoff_this_step=snapshot.receipt_handoff_this_step,
        raw_exposure=snapshot.raw_exposure,
        id_exposure=snapshot.id_exposure,
        credential_value_exposure=snapshot.credential_value_exposure,
        signature_value_exposure=snapshot.signature_value_exposure,
        headers_value_exposure=snapshot.headers_value_exposure,
    )


def _preview_prerequisite_reasons(
    snapshot: LiveOrderRealExecutableOrderPreviewInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    checks = (
        ("fresh_preflight_passed", snapshot.fresh_preflight_passed),
        ("final_confirmation_received", snapshot.final_confirmation_received),
        ("ready_gate_passed", snapshot.ready_gate_passed),
        ("post_guard_ready", snapshot.post_guard_ready),
        ("one_post_max", snapshot.one_post_max),
        ("timeout_fail_closed", snapshot.timeout_fail_closed),
        (
            "actual_post_requires_post_specific_confirmation",
            snapshot.actual_post_requires_post_specific_confirmation,
        ),
    )
    for name, passed in checks:
        if not passed:
            reasons.append(f"{name}_missing")
    if snapshot.retry_allowed:
        reasons.append("retry_allowed")
    if snapshot.ledger_update_this_step:
        reasons.append("ledger_update_this_step")
    if snapshot.receipt_handoff_this_step:
        reasons.append("receipt_handoff_this_step")
    return tuple(reasons)


def _preview_exposure_reasons(
    snapshot: LiveOrderRealExecutableOrderPreviewInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "raw_exposure",
        "id_exposure",
        "credential_value_exposure",
        "signature_value_exposure",
        "headers_value_exposure",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _order_ambiguity_reasons(
    snapshot: LiveOrderRealExecutableOrderPreviewInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.order_ambiguity:
        reasons.append("order_ambiguity")
    if snapshot.symbol != SUPPORTED_SYMBOL:
        reasons.append("symbol_not_supported")
    if snapshot.side != LiveOrderCandidateSide.BUY.value:
        reasons.append("side_not_repo_defined_buy")
    if snapshot.order_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        reasons.append("order_type_not_repo_defined_market")
    if snapshot.size != LIVE_ORDER_CANDIDATE_SIZE:
        reasons.append("size_not_repo_defined")
    for field_name in (
        "codex_inferred_symbol",
        "codex_inferred_side",
        "codex_inferred_size",
        "codex_inferred_order_type",
    ):
        if getattr(snapshot, field_name):
            reasons.append(f"{field_name}_unsafe")
    if _unsafe_text(snapshot.safe_order_source_label):
        reasons.append("safe_order_source_label_unsafe")
    return tuple(reasons)


def _confirmation_value_exposure(
    snapshot: LiveOrderRealPostSpecificConfirmationInput,
) -> bool:
    return (
        snapshot.post_confirmation_actual_value_stored
        or snapshot.post_confirmation_actual_value_reported
        or snapshot.post_confirmation_actual_value_logged
    )


def _confirmation_reused(
    snapshot: LiveOrderRealPostSpecificConfirmationInput,
) -> bool:
    return (
        snapshot.post_specific_confirmation_reused
        or snapshot.final_confirmation_reused_as_post_confirmation
        or snapshot.ready_gate_confirmation_reused_as_post_confirmation
        or snapshot.previous_turn_confirmation_reused
        or snapshot.step4_approval_phrase_reused
    )


def _confirmation_reuse_reasons(
    snapshot: LiveOrderRealPostSpecificConfirmationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "post_specific_confirmation_reused",
        "final_confirmation_reused_as_post_confirmation",
        "ready_gate_confirmation_reused_as_post_confirmation",
        "previous_turn_confirmation_reused",
        "step4_approval_phrase_reused",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _execution_prerequisite_reasons(
    snapshot: LiveOrderRealOneShotPostExecutionControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    required_true = (
        "fresh_preflight_passed",
        "fresh_preflight_current",
        "fresh_preflight_new",
        "final_confirmation_received",
        "confirmation_current_turn",
        "confirmation_new",
        "confirmation_one_time",
        "ready_gate_passed",
        "post_guard_ready",
        "one_post_max",
        "timeout_fail_closed",
        "final_readiness_ready",
        "final_exec_stack_ready",
        "sanitized_result_contract_ready",
    )
    for field_name in required_true:
        if not getattr(snapshot, field_name):
            reasons.append(f"{field_name}_missing")
    required_false = (
        "fresh_preflight_reused",
        "fresh_preflight_stale",
        "confirmation_reused",
        "previous_turn_confirmation_reused",
        "step4_approval_phrase_reused",
        "retry_allowed",
        "fresh_preflight_reexecuted",
        "final_confirmation_reobtained",
    )
    for field_name in required_false:
        if getattr(snapshot, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _execution_unsafe_reasons(
    snapshot: LiveOrderRealOneShotPostExecutionControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "ledger_update_this_step",
        "receipt_handoff_this_step",
        "ledger_updated",
        "attempt_counter_persisted",
        "actual_receipt_handoff_executed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    for field_name in (
        "raw_exposure",
        "id_exposure",
        "credential_value_exposure",
        "signature_value_exposure",
        "headers_value_exposure",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    for field_name in (
        "actual_http_post_executed",
        "order_endpoint_executed",
        "live_order_once_executed",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _transport_unsafe_reasons(
    transport_result: LiveOrderRealOneShotPostTransportResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "ledger_updated",
        "attempt_counter_persisted",
        "actual_receipt_handoff_executed",
    ):
        if getattr(transport_result, field_name):
            reasons.append(field_name)
    for field_name in (
        "raw_request_exposed",
        "raw_response_exposed",
        "broker_api_response_exposed",
        "credential_value_exposed",
        "signature_value_exposed",
        "headers_value_exposed",
    ):
        if getattr(transport_result, field_name):
            reasons.append(field_name)
    for field_name in (
        "real_id_exposed",
        "account_id_exposed",
        "order_id_exposed",
        "transaction_id_exposed",
    ):
        if getattr(transport_result, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _status_from_unsafe_reasons(
    reasons: tuple[str, ...],
) -> LiveOrderRealOneShotPostExecutionControlledStatus:
    if any("raw" in reason or "broker_api" in reason for reason in reasons):
        return ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_RAW_EXPOSURE
    if any("id" in reason for reason in reasons):
        return ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_ID_EXPOSURE
    if any(
        "credential" in reason
        or "signature_value" in reason
        or "headers" in reason
        for reason in reasons
    ):
        return ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_VALUE_EXPOSURE
    if any(
        "ledger" in reason or "receipt" in reason or "counter" in reason
        for reason in reasons
    ):
        return ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_LEDGER_OR_RECEIPT
    return ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_PREREQUISITE


def _safe_result_category(
    status: LiveOrderRealOneShotPostExecutionControlledStatus,
) -> SafePostResultCategory:
    if status is ExecutionStatus.ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY:
        return SafePostResultCategory.RESULT_ACCEPTED_SANITIZED
    if status in {
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_TIMEOUT_FAIL_CLOSED,
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_UNKNOWN_FAIL_CLOSED,
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_UNAVAILABLE_FAIL_CLOSED,
    }:
        if status is ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_TIMEOUT_FAIL_CLOSED:
            return SafePostResultCategory.RESULT_TIMEOUT_FAIL_CLOSED
        if status is ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_UNAVAILABLE_FAIL_CLOSED:
            return SafePostResultCategory.RESULT_UNAVAILABLE_FAIL_CLOSED
        return SafePostResultCategory.RESULT_UNKNOWN_FAIL_CLOSED
    if status is ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_FAILED_FAIL_CLOSED:
        return SafePostResultCategory.RESULT_REJECTED_SANITIZED
    return SafePostResultCategory.RESULT_NOT_RECEIVED


def _validate_execution_result_safety(
    result: LiveOrderRealOneShotPostExecutionControlledResult,
) -> None:
    if result.post_execution_count > 1:
        raise LiveVerificationValidationError("post_execution_count must be <= 1")
    if result.second_post_attempted:
        raise LiveVerificationValidationError("second POST must remain false")
    if result.retry_attempted:
        raise LiveVerificationValidationError("retry must remain false")
    if result.ledger_updated or result.attempt_counter_persisted:
        raise LiveVerificationValidationError("ledger and attempt counter remain false")
    if result.actual_receipt_handoff_executed:
        raise LiveVerificationValidationError("receipt handoff remains false")
    unsafe_fields = (
        "raw_request_exposed",
        "raw_response_exposed",
        "broker_api_response_exposed",
        "credential_value_exposed",
        "signature_value_exposed",
        "headers_value_exposed",
        "real_id_exposed",
        "account_id_exposed",
        "order_id_exposed",
        "transaction_id_exposed",
        "order_endpoint_executed",
        "live_order_once_executed",
        "fresh_preflight_reexecuted",
        "final_confirmation_reobtained",
        "post_confirmation_actual_value_stored",
        "post_confirmation_actual_value_reported",
        "post_confirmation_actual_value_logged",
    )
    for field_name in unsafe_fields:
        if getattr(result, field_name):
            raise LiveVerificationValidationError(f"{field_name} must remain false")


def _safe_label(value: str, expected: str) -> str:
    return value if value == expected else UNSUPPORTED_ONE_SHOT_POST_EXECUTION_LABEL


def _safe_text_label(value: str) -> str:
    if _unsafe_text(value):
        return UNSUPPORTED_ONE_SHOT_POST_EXECUTION_LABEL
    return value


def _unsafe_text(value: str) -> bool:
    upper = value.upper()
    unsafe_terms = (
        "RAW",
        "SECRET",
        "TOKEN",
        "CREDENTIAL",
        "SIGNATURE",
        "HEADER",
        "ACCOUNT_ID",
        "ORDER_ID",
        "TRANSACTION_ID",
        "REAL_ID",
        "LEDGER",
        "CONFIRMATION_PHRASE",
    )
    return not value.strip() or any(term in upper for term in unsafe_terms)


def _prefix_reasons(prefix: str, reasons: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"{prefix}_{reason}" for reason in reasons) or (f"{prefix}_blocked",)


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason and reason not in merged:
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
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


_PREVIEW_INPUT_BOOL_FIELDS = (
    "fresh_preflight_passed",
    "final_confirmation_received",
    "ready_gate_passed",
    "post_guard_ready",
    "one_post_max",
    "retry_allowed",
    "timeout_fail_closed",
    "actual_post_requires_post_specific_confirmation",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "raw_exposure",
    "id_exposure",
    "credential_value_exposure",
    "signature_value_exposure",
    "headers_value_exposure",
    "safe_order_candidate_available",
    "order_ambiguity",
    "codex_inferred_symbol",
    "codex_inferred_side",
    "codex_inferred_size",
    "codex_inferred_order_type",
)

_PREVIEW_RESULT_BOOL_FIELDS = (
    "sanitized_order_preview_available",
    "order_ambiguity",
    "fresh_preflight_passed",
    "final_confirmation_received",
    "ready_gate_passed",
    "post_guard_ready",
    "one_post_max",
    "retry_allowed",
    "timeout_fail_closed",
    "actual_post_requires_post_specific_confirmation",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "raw_exposure",
    "id_exposure",
    "credential_value_exposure",
    "signature_value_exposure",
    "headers_value_exposure",
    "codex_inferred_symbol",
    "codex_inferred_side",
    "codex_inferred_size",
    "codex_inferred_order_type",
)

_CONFIRMATION_INPUT_BOOL_FIELDS = (
    "post_specific_confirmation_required",
    "post_specific_confirmation_received",
    "post_specific_confirmation_current_turn",
    "post_specific_confirmation_new",
    "post_specific_confirmation_one_time",
    "post_specific_confirmation_reused",
    "final_confirmation_reused_as_post_confirmation",
    "ready_gate_confirmation_reused_as_post_confirmation",
    "previous_turn_confirmation_reused",
    "step4_approval_phrase_reused",
    "post_confirmation_actual_value_stored",
    "post_confirmation_actual_value_reported",
    "post_confirmation_actual_value_logged",
)

_CONFIRMATION_RESULT_BOOL_FIELDS = (
    "post_specific_confirmation_adapter_ready",
    "post_specific_confirmation_validated",
    *_CONFIRMATION_INPUT_BOOL_FIELDS,
)

_EXECUTION_INPUT_BOOL_FIELDS = (
    "fresh_preflight_passed",
    "fresh_preflight_current",
    "fresh_preflight_new",
    "fresh_preflight_reused",
    "fresh_preflight_stale",
    "final_confirmation_received",
    "confirmation_current_turn",
    "confirmation_new",
    "confirmation_one_time",
    "confirmation_reused",
    "previous_turn_confirmation_reused",
    "step4_approval_phrase_reused",
    "ready_gate_passed",
    "post_guard_ready",
    "one_post_max",
    "retry_allowed",
    "timeout_fail_closed",
    "final_readiness_ready",
    "final_exec_stack_ready",
    "sanitized_result_contract_ready",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "raw_exposure",
    "id_exposure",
    "credential_value_exposure",
    "signature_value_exposure",
    "headers_value_exposure",
    "actual_http_post_executed",
    "order_endpoint_executed",
    "live_order_once_executed",
    "ledger_updated",
    "attempt_counter_persisted",
    "actual_receipt_handoff_executed",
    "fresh_preflight_reexecuted",
    "final_confirmation_reobtained",
)

_TRANSPORT_RESULT_BOOL_FIELDS = (
    "fake_transport_used",
    "http_post_executed",
    "second_post_attempted",
    "retry_attempted",
    "timeout",
    "unknown",
    "unavailable",
    "failed",
    "ledger_updated",
    "attempt_counter_persisted",
    "actual_receipt_handoff_executed",
    "raw_request_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
    "real_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
)

_EXECUTION_RESULT_BOOL_FIELDS = (
    "safe_post_execution_route_available",
    "post_execution_allowed",
    "post_attempted",
    "http_post_executed",
    "actual_http_post_executed",
    "second_post_attempted",
    "retry_attempted",
    "fake_transport_used",
    "transport_injected",
    "sanitized_order_preview_available",
    "order_ambiguity",
    "post_specific_confirmation_adapter_ready",
    "post_specific_confirmation_validated",
    "post_specific_confirmation_required",
    "post_specific_confirmation_received",
    "post_specific_confirmation_current_turn",
    "post_specific_confirmation_new",
    "post_specific_confirmation_one_time",
    "post_specific_confirmation_reused",
    "final_confirmation_reused_as_post_confirmation",
    "ready_gate_confirmation_reused_as_post_confirmation",
    "previous_turn_confirmation_reused",
    "step4_approval_phrase_reused",
    "post_confirmation_actual_value_stored",
    "post_confirmation_actual_value_reported",
    "post_confirmation_actual_value_logged",
    "fresh_preflight_passed",
    "final_confirmation_received",
    "ready_gate_passed",
    "post_guard_ready",
    "one_post_max",
    "retry_allowed",
    "timeout_fail_closed",
    "final_readiness_ready",
    "final_exec_stack_ready",
    "sanitized_result_contract_ready",
    "ledger_update_this_step",
    "receipt_handoff_this_step",
    "ledger_updated",
    "attempt_counter_persisted",
    "actual_receipt_handoff_executed",
    "raw_request_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
    "real_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
    "order_endpoint_executed",
    "live_order_once_executed",
    "fresh_preflight_reexecuted",
    "final_confirmation_reobtained",
)
