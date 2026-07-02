"""Step 6G controlled fresh preflight execution adapter.

This module declares the safe adapter/CLI boundary for a later fresh preflight
execution step. It does not execute fresh preflight, HTTP POST, order
endpoints, live_order_once, final confirmation, ledger updates, attempt
persistence, actual result receipt, or receipt handoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_fresh_preflight_runtime_controlled import (
    SAFE_LOCAL_STATIC_CHECK_LABEL,
    SAFE_PREFLIGHT_RUNTIME_LABEL,
    SAFE_PRIVATE_READ_ONLY_CHECK_LABEL,
    SAFE_PUBLIC_MARKET_CHECK_LABEL,
    LiveOrderRealFreshPreflightRuntimeControlledResult,
    LiveOrderRealFreshPreflightRuntimeControlledStatus,
    build_live_order_real_fresh_preflight_runtime_controlled,
)

FRESH_PREFLIGHT_EXECUTION_RECOMMENDED_NEXT_STEP = (
    "fresh_preflight_check_retry_2_with_safe_adapter_no_post_no_final_confirmation"
)
SAFE_PREFLIGHT_EXECUTION_LABEL = "CONTROLLED_FRESH_PREFLIGHT_EXECUTION_ADAPTER"
UNSUPPORTED_PREFLIGHT_EXECUTION_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealFreshPreflightExecutionControlledStatus(str, Enum):
    FRESH_PREFLIGHT_EXECUTION_ADAPTER_NOT_READY = (
        "FRESH_PREFLIGHT_EXECUTION_ADAPTER_NOT_READY"
    )
    FRESH_PREFLIGHT_EXECUTION_ADAPTER_READY_NO_EXECUTION = (
        "FRESH_PREFLIGHT_EXECUTION_ADAPTER_READY_NO_EXECUTION"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_RUNTIME = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_RUNTIME"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_PUBLIC_MARKET = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_PUBLIC_MARKET"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_PRIVATE_READ_ONLY = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_PRIVATE_READ_ONLY"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_LOCAL_STATIC = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_LOCAL_STATIC"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_SAFE_RENDERER = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_SAFE_RENDERER"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_UNKNOWN = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_UNKNOWN"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_FAILED = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_FAILED"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_TIMEOUT = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_TIMEOUT"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_UNAVAILABLE = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_UNAVAILABLE"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_STALE = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_STALE"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_REUSED = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_REUSED"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_POST_ATTEMPTED = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_POST_ATTEMPTED"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_ORDER_ENDPOINT = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_ORDER_ENDPOINT"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_LIVE_ORDER_ONCE = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_LIVE_ORDER_ONCE"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_FINAL_CONFIRMATION = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_FINAL_CONFIRMATION"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_LEDGER_UPDATE = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_LEDGER_UPDATE"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_ACTUAL_RECEIPT = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_ACTUAL_RECEIPT"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_RAW_EXPOSURE = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_RAW_EXPOSURE"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_ID_EXPOSURE = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_ID_EXPOSURE"
    )
    FRESH_PREFLIGHT_EXECUTION_BLOCKED_VALUE_EXPOSURE = (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_VALUE_EXPOSURE"
    )


class LiveOrderRealFreshPreflightExecutionControlledMode(str, Enum):
    FRESH_PREFLIGHT_EXECUTION_CONTROLLED_ADAPTER_ONLY = (
        "FRESH_PREFLIGHT_EXECUTION_CONTROLLED_ADAPTER_ONLY"
    )


FreshPreflightExecutionControlledStatus = (
    LiveOrderRealFreshPreflightExecutionControlledStatus
)
FreshPreflightExecutionControlledMode = (
    LiveOrderRealFreshPreflightExecutionControlledMode
)


@dataclass(frozen=True)
class LiveOrderRealFreshPreflightExecutionControlledInput:
    fresh_preflight_execution_mode: str = (
        FreshPreflightExecutionControlledMode
        .FRESH_PREFLIGHT_EXECUTION_CONTROLLED_ADAPTER_ONLY
        .value
    )
    fresh_preflight_execution_adapter_declared: bool = True
    fresh_preflight_execution_adapter_requested: bool = True
    safe_preflight_execution_label: str = SAFE_PREFLIGHT_EXECUTION_LABEL
    safe_output_renderer_ready: bool = True
    public_market_execution_mapping_available: bool = True
    private_read_only_execution_mapping_available: bool = True
    local_static_execution_mapping_available: bool = True
    fresh_preflight_new_marker_required: bool = True
    fresh_preflight_current_marker_required: bool = True
    fresh_preflight_non_reuse_required: bool = True
    fresh_preflight_adapter_at_most_once: bool = True
    fresh_preflight_retry_allowed: bool = False
    fresh_preflight_unknown_retry_allowed: bool = False
    fresh_preflight_timeout_retry_allowed: bool = False
    fresh_preflight_failed_retry_allowed: bool = False
    fresh_preflight_execution_unknown: bool = False
    fresh_preflight_execution_failed: bool = False
    fresh_preflight_execution_unavailable: bool = False
    fresh_preflight_execution_timeout: bool = False
    fresh_preflight_execution_stale: bool = False
    fresh_preflight_execution_reused: bool = False
    fresh_preflight_execution_performed: bool = False
    api_call_allowed: bool = False
    api_call_executed: bool = False
    public_api_call_executed: bool = False
    private_api_call_executed: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    final_confirmation_received: bool = False
    ledger_update_allowed: bool = False
    ledger_updated: bool = False
    ledger_update_attempted: bool = False
    attempt_counter_persistence_allowed: bool = False
    attempt_counter_persisted: bool = False
    actual_result_receipt_received: bool = False
    actual_receipt_handoff_executed: bool = False
    actual_receipt_handoff_allowed: bool = False
    unsafe_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    raw_request_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    request_body_exposure_attempted: bool = False
    response_body_exposure_attempted: bool = False
    broker_response_exposure_attempted: bool = False
    api_response_exposure_attempted: bool = False
    endpoint_actual_value_exposure_attempted: bool = False
    account_id_exposure_attempted: bool = False
    order_id_exposure_attempted: bool = False
    transaction_id_exposure_attempted: bool = False
    position_id_exposure_attempted: bool = False
    trade_id_exposure_attempted: bool = False
    real_id_exposure_attempted: bool = False
    confirmation_phrase_exposure_attempted: bool = False
    ledger_state_exposure_attempted: bool = False
    approval_command_exposure_attempted: bool = False
    raw_request_stored: bool = False
    raw_response_stored: bool = False
    broker_response_exposed: bool = False
    api_response_exposed: bool = False
    real_id_exposed: bool = False
    ledger_state_actual_value_exposed: bool = False
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty(
            "fresh_preflight_execution_mode",
            self.fresh_preflight_execution_mode,
        )
        _require_non_empty(
            "safe_preflight_execution_label",
            self.safe_preflight_execution_label,
        )
        _validate_bool_fields(self, _FRESH_PREFLIGHT_EXECUTION_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealFreshPreflightExecutionControlledCheckResult:
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
class LiveOrderRealFreshPreflightExecutionControlledResult:
    status: LiveOrderRealFreshPreflightExecutionControlledStatus
    fresh_preflight_execution_command_available: bool
    fresh_preflight_execution_allowed_next_step: bool
    fresh_preflight_execution_mode: str
    safe_preflight_execution_label: str
    safe_preflight_execution_status: str
    safe_preflight_runtime_label: str
    safe_preflight_runtime_status: str
    fresh_preflight_runtime_ready: bool
    fresh_preflight_execution_performed: bool
    fresh_preflight_new_marker_required: bool
    fresh_preflight_current_marker_required: bool
    fresh_preflight_non_reuse_required: bool
    fresh_preflight_adapter_at_most_once: bool
    fresh_preflight_retry_allowed: bool
    fresh_preflight_unknown_retry_allowed: bool
    fresh_preflight_timeout_retry_allowed: bool
    fresh_preflight_failed_retry_allowed: bool
    public_market_check_available: bool
    private_read_only_check_available: bool
    local_static_check_available: bool
    safe_public_market_check_label: str
    safe_private_read_only_check_label: str
    safe_local_static_check_label: str
    safe_account_assets_count: int
    safe_open_positions_count: int
    safe_active_orders_count: int
    safe_output_renderer_ready: bool
    api_call_allowed: bool
    api_call_executed: bool
    public_api_call_executed: bool
    private_api_call_executed: bool
    post_allowed_this_step: bool
    post_executed: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    final_confirmation_received: bool
    ledger_update_allowed: bool
    ledger_updated: bool
    attempt_counter_persistence_allowed: bool
    attempt_counter_persisted: bool
    actual_result_receipt_received: bool
    actual_receipt_handoff_executed: bool
    actual_receipt_handoff_allowed: bool
    raw_request_stored: bool
    raw_response_stored: bool
    broker_response_exposed: bool
    api_response_exposed: bool
    real_id_exposed: bool
    ledger_state_actual_value_exposed: bool
    safe_to_render: bool
    safe_to_serialize: bool
    check_results: tuple[
        LiveOrderRealFreshPreflightExecutionControlledCheckResult,
        ...,
    ]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealFreshPreflightExecutionControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be fresh preflight execution controlled status",
            )
        _require_non_empty(
            "fresh_preflight_execution_mode",
            self.fresh_preflight_execution_mode,
        )
        _require_non_empty(
            "safe_preflight_execution_label",
            self.safe_preflight_execution_label,
        )
        _require_non_empty(
            "safe_preflight_execution_status",
            self.safe_preflight_execution_status,
        )
        _require_non_empty("safe_preflight_runtime_label", self.safe_preflight_runtime_label)
        _require_non_empty("safe_preflight_runtime_status", self.safe_preflight_runtime_status)
        _require_non_empty(
            "safe_public_market_check_label",
            self.safe_public_market_check_label,
        )
        _require_non_empty(
            "safe_private_read_only_check_label",
            self.safe_private_read_only_check_label,
        )
        _require_non_empty(
            "safe_local_static_check_label",
            self.safe_local_static_check_label,
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(self, _FRESH_PREFLIGHT_EXECUTION_RESULT_BOOL_FIELDS)
        _validate_non_negative_int(
            "safe_account_assets_count",
            self.safe_account_assets_count,
        )
        _validate_non_negative_int(
            "safe_open_positions_count",
            self.safe_open_positions_count,
        )
        _validate_non_negative_int(
            "safe_active_orders_count",
            self.safe_active_orders_count,
        )
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_fresh_preflight_execution_controlled(
    *,
    input_snapshot: LiveOrderRealFreshPreflightExecutionControlledInput | None = None,
    runtime_result: LiveOrderRealFreshPreflightRuntimeControlledResult | None = None,
) -> LiveOrderRealFreshPreflightExecutionControlledResult:
    """Build the safe execution adapter command contract without executing it."""
    snapshot = input_snapshot or LiveOrderRealFreshPreflightExecutionControlledInput()
    safe_runtime_result = (
        runtime_result
        or build_live_order_real_fresh_preflight_runtime_controlled()
    )
    status, primary_reasons = _status_from_input(snapshot, safe_runtime_result)
    ready = (
        status
        is (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_ADAPTER_READY_NO_EXECUTION
        )
    )
    safe_mode = (
        snapshot.fresh_preflight_execution_mode
        if snapshot.fresh_preflight_execution_mode
        == (
            FreshPreflightExecutionControlledMode
            .FRESH_PREFLIGHT_EXECUTION_CONTROLLED_ADAPTER_ONLY
            .value
        )
        else UNSUPPORTED_PREFLIGHT_EXECUTION_LABEL
    )
    safe_label = (
        snapshot.safe_preflight_execution_label
        if snapshot.safe_preflight_execution_label == SAFE_PREFLIGHT_EXECUTION_LABEL
        else UNSUPPORTED_PREFLIGHT_EXECUTION_LABEL
    )
    blocked_reasons = _blocked_reasons(
        snapshot=snapshot,
        runtime_result=safe_runtime_result,
        primary_reasons=primary_reasons,
    )

    return LiveOrderRealFreshPreflightExecutionControlledResult(
        status=status,
        fresh_preflight_execution_command_available=ready,
        fresh_preflight_execution_allowed_next_step=ready,
        fresh_preflight_execution_mode=safe_mode,
        safe_preflight_execution_label=safe_label,
        safe_preflight_execution_status=status.value,
        safe_preflight_runtime_label=safe_runtime_result.safe_preflight_runtime_label,
        safe_preflight_runtime_status=safe_runtime_result.safe_preflight_runtime_status,
        fresh_preflight_runtime_ready=safe_runtime_result.fresh_preflight_runtime_ready,
        fresh_preflight_execution_performed=False,
        fresh_preflight_new_marker_required=(
            snapshot.fresh_preflight_new_marker_required
        ),
        fresh_preflight_current_marker_required=(
            snapshot.fresh_preflight_current_marker_required
        ),
        fresh_preflight_non_reuse_required=(
            snapshot.fresh_preflight_non_reuse_required
        ),
        fresh_preflight_adapter_at_most_once=(
            snapshot.fresh_preflight_adapter_at_most_once
        ),
        fresh_preflight_retry_allowed=False,
        fresh_preflight_unknown_retry_allowed=False,
        fresh_preflight_timeout_retry_allowed=False,
        fresh_preflight_failed_retry_allowed=False,
        public_market_check_available=_public_market_available(snapshot, safe_runtime_result),
        private_read_only_check_available=_private_read_only_available(
            snapshot,
            safe_runtime_result,
        ),
        local_static_check_available=_local_static_available(snapshot, safe_runtime_result),
        safe_public_market_check_label=safe_runtime_result.safe_public_market_check_label,
        safe_private_read_only_check_label=(
            safe_runtime_result.safe_private_read_only_check_label
        ),
        safe_local_static_check_label=safe_runtime_result.safe_local_static_check_label,
        safe_account_assets_count=safe_runtime_result.safe_account_assets_count,
        safe_open_positions_count=safe_runtime_result.safe_open_positions_count,
        safe_active_orders_count=safe_runtime_result.safe_active_orders_count,
        safe_output_renderer_ready=snapshot.safe_output_renderer_ready,
        api_call_allowed=False,
        api_call_executed=False,
        public_api_call_executed=False,
        private_api_call_executed=False,
        post_allowed_this_step=False,
        post_executed=False,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        final_confirmation_received=False,
        ledger_update_allowed=False,
        ledger_updated=False,
        attempt_counter_persistence_allowed=False,
        attempt_counter_persisted=False,
        actual_result_receipt_received=False,
        actual_receipt_handoff_executed=False,
        actual_receipt_handoff_allowed=False,
        raw_request_stored=False,
        raw_response_stored=False,
        broker_response_exposed=False,
        api_response_exposed=False,
        real_id_exposed=False,
        ledger_state_actual_value_exposed=False,
        safe_to_render=snapshot.safe_to_render,
        safe_to_serialize=snapshot.safe_to_serialize,
        check_results=_build_check_results(
            snapshot=snapshot,
            runtime_result=safe_runtime_result,
            status=status,
            ready=ready,
            safe_label=safe_label,
        ),
        blocked_reasons=blocked_reasons,
        recommended_next_step=FRESH_PREFLIGHT_EXECUTION_RECOMMENDED_NEXT_STEP,
    )


def render_live_order_real_fresh_preflight_execution_controlled_markdown(
    result: LiveOrderRealFreshPreflightExecutionControlledResult,
) -> str:
    """Render a safe fresh preflight execution adapter summary only."""
    lines = [
        "# Step 6G Fresh Preflight Execution Controlled Adapter",
        "",
        "This is a controlled execution adapter/CLI contract.",
        "It does not execute fresh preflight in this step.",
        "It contains only safe labels, statuses, booleans, counts, and blocked",
        "reason labels.",
        "It does not execute HTTP POST.",
        "It does not call order endpoints.",
        "It does not call live_order_once.",
        "It does not obtain final confirmation.",
        "It does not update ledgers or persist attempt counters.",
        "It does not receive actual results or hand off receipts.",
        "It does not expose raw requests, raw responses, broker/API responses, IDs,",
        "credential values, signature values, headers values, confirmation phrases,",
        "ledger state values, or approval command values.",
        "Adapter ready does not mean fresh preflight executed.",
        "Adapter ready does not allow POST.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- fresh_preflight_execution_command_available: "
            f"{_bool_text(result.fresh_preflight_execution_command_available)}"
        ),
        (
            "- fresh_preflight_execution_allowed_next_step: "
            f"{_bool_text(result.fresh_preflight_execution_allowed_next_step)}"
        ),
        f"- fresh_preflight_execution_mode: {result.fresh_preflight_execution_mode}",
        f"- safe_preflight_execution_label: {result.safe_preflight_execution_label}",
        f"- safe_preflight_execution_status: {result.safe_preflight_execution_status}",
        f"- safe_preflight_runtime_label: {result.safe_preflight_runtime_label}",
        f"- safe_preflight_runtime_status: {result.safe_preflight_runtime_status}",
        "",
        "## Next-Step Requirements",
        (
            "- fresh_preflight_execution_performed: "
            f"{_bool_text(result.fresh_preflight_execution_performed)}"
        ),
        (
            "- fresh_preflight_new_marker_required: "
            f"{_bool_text(result.fresh_preflight_new_marker_required)}"
        ),
        (
            "- fresh_preflight_current_marker_required: "
            f"{_bool_text(result.fresh_preflight_current_marker_required)}"
        ),
        (
            "- fresh_preflight_non_reuse_required: "
            f"{_bool_text(result.fresh_preflight_non_reuse_required)}"
        ),
        (
            "- fresh_preflight_adapter_at_most_once: "
            f"{_bool_text(result.fresh_preflight_adapter_at_most_once)}"
        ),
        f"- fresh_preflight_retry_allowed: {_bool_text(result.fresh_preflight_retry_allowed)}",
        (
            "- fresh_preflight_unknown_retry_allowed: "
            f"{_bool_text(result.fresh_preflight_unknown_retry_allowed)}"
        ),
        (
            "- fresh_preflight_timeout_retry_allowed: "
            f"{_bool_text(result.fresh_preflight_timeout_retry_allowed)}"
        ),
        (
            "- fresh_preflight_failed_retry_allowed: "
            f"{_bool_text(result.fresh_preflight_failed_retry_allowed)}"
        ),
        "",
        "## Safe Check Mappings",
        (
            "- public_market_check_available: "
            f"{_bool_text(result.public_market_check_available)}"
        ),
        (
            "- private_read_only_check_available: "
            f"{_bool_text(result.private_read_only_check_available)}"
        ),
        (
            "- local_static_check_available: "
            f"{_bool_text(result.local_static_check_available)}"
        ),
        f"- safe_account_assets_count: {result.safe_account_assets_count}",
        f"- safe_open_positions_count: {result.safe_open_positions_count}",
        f"- safe_active_orders_count: {result.safe_active_orders_count}",
        f"- safe_output_renderer_ready: {_bool_text(result.safe_output_renderer_ready)}",
        "",
        "## Non-Execution",
        f"- api_call_executed: {_bool_text(result.api_call_executed)}",
        f"- public_api_call_executed: {_bool_text(result.public_api_call_executed)}",
        f"- private_api_call_executed: {_bool_text(result.private_api_call_executed)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        (
            "- final_confirmation_received: "
            f"{_bool_text(result.final_confirmation_received)}"
        ),
        f"- ledger_updated: {_bool_text(result.ledger_updated)}",
        (
            "- attempt_counter_persisted: "
            f"{_bool_text(result.attempt_counter_persisted)}"
        ),
        (
            "- actual_receipt_handoff_executed: "
            f"{_bool_text(result.actual_receipt_handoff_executed)}"
        ),
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines)


def _status_from_input(
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
    runtime_result: LiveOrderRealFreshPreflightRuntimeControlledResult,
) -> tuple[FreshPreflightExecutionControlledStatus, tuple[str, ...]]:
    if _adapter_contract_missing(snapshot):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_ADAPTER_NOT_READY,
            ("fresh_preflight_execution_adapter_contract_missing",),
        )
    if not _runtime_ready(runtime_result):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_RUNTIME,
            ("fresh_preflight_runtime_missing_or_not_ready",),
        )
    if not _public_market_available(snapshot, runtime_result):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_PUBLIC_MARKET,
            ("public_market_execution_mapping_missing_or_not_ready",),
        )
    if not _private_read_only_available(snapshot, runtime_result):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_PRIVATE_READ_ONLY,
            ("private_read_only_execution_mapping_missing_or_not_ready",),
        )
    if not _local_static_available(snapshot, runtime_result):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_LOCAL_STATIC,
            ("local_static_execution_mapping_missing_or_not_ready",),
        )
    if not snapshot.safe_output_renderer_ready:
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_SAFE_RENDERER,
            ("safe_output_renderer_missing_or_not_ready",),
        )
    if snapshot.fresh_preflight_execution_unknown:
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_UNKNOWN,
            ("fresh_preflight_execution_unknown",),
        )
    if _failed(snapshot):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_FAILED,
            ("fresh_preflight_execution_failed_or_adapter_policy_invalid",),
        )
    if snapshot.fresh_preflight_execution_timeout:
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_TIMEOUT,
            ("fresh_preflight_execution_timeout",),
        )
    if snapshot.fresh_preflight_execution_unavailable:
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_UNAVAILABLE,
            ("fresh_preflight_execution_unavailable",),
        )
    if snapshot.fresh_preflight_execution_stale:
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_STALE,
            ("fresh_preflight_execution_stale",),
        )
    if snapshot.fresh_preflight_execution_reused:
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_REUSED,
            ("fresh_preflight_execution_reused",),
        )
    if snapshot.fresh_preflight_execution_performed:
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_FAILED,
            ("fresh_preflight_execution_performed_in_adapter_setup_step",),
        )
    if _post_attempted(snapshot):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_POST_ATTEMPTED,
            ("post_attempted",),
        )
    if snapshot.order_endpoint_called:
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_ORDER_ENDPOINT,
            ("order_endpoint_called",),
        )
    if snapshot.live_order_once_called:
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_LIVE_ORDER_ONCE,
            ("live_order_once_called",),
        )
    if snapshot.final_confirmation_received:
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_FINAL_CONFIRMATION,
            ("final_confirmation_received",),
        )
    if _ledger_attempted(snapshot):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_LEDGER_UPDATE,
            ("ledger_or_attempt_counter_attempted",),
        )
    if _actual_receipt_attempted(snapshot):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_ACTUAL_RECEIPT,
            ("actual_receipt_or_handoff_attempted",),
        )
    if _raw_exposed(snapshot):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_RAW_EXPOSURE,
            ("raw_or_response_exposure_attempted",),
        )
    if _id_exposed(snapshot):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_ID_EXPOSURE,
            ("id_exposure_attempted",),
        )
    if _value_exposed(snapshot):
        return (
            FreshPreflightExecutionControlledStatus
            .FRESH_PREFLIGHT_EXECUTION_BLOCKED_VALUE_EXPOSURE,
            ("value_exposure_attempted",),
        )
    return (
        FreshPreflightExecutionControlledStatus
        .FRESH_PREFLIGHT_EXECUTION_ADAPTER_READY_NO_EXECUTION,
        (),
    )


def _adapter_contract_missing(
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
) -> bool:
    return not (
        snapshot.fresh_preflight_execution_adapter_declared
        and snapshot.fresh_preflight_execution_adapter_requested
        and snapshot.safe_preflight_execution_label == SAFE_PREFLIGHT_EXECUTION_LABEL
        and snapshot.fresh_preflight_execution_mode
        == (
            FreshPreflightExecutionControlledMode
            .FRESH_PREFLIGHT_EXECUTION_CONTROLLED_ADAPTER_ONLY
            .value
        )
    )


def _runtime_ready(
    runtime_result: LiveOrderRealFreshPreflightRuntimeControlledResult,
) -> bool:
    return (
        runtime_result.status
        is (
            LiveOrderRealFreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_READY_NO_EXECUTION
        )
        and runtime_result.fresh_preflight_runtime_ready
        and runtime_result.safe_preflight_runtime_label == SAFE_PREFLIGHT_RUNTIME_LABEL
        and runtime_result.safe_preflight_runtime_status
        == (
            LiveOrderRealFreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_READY_NO_EXECUTION
            .value
        )
    )


def _public_market_available(
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
    runtime_result: LiveOrderRealFreshPreflightRuntimeControlledResult,
) -> bool:
    return (
        snapshot.public_market_execution_mapping_available
        and runtime_result.public_market_check_ready
        and runtime_result.safe_public_market_check_label
        == SAFE_PUBLIC_MARKET_CHECK_LABEL
    )


def _private_read_only_available(
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
    runtime_result: LiveOrderRealFreshPreflightRuntimeControlledResult,
) -> bool:
    return (
        snapshot.private_read_only_execution_mapping_available
        and runtime_result.private_read_only_check_ready
        and runtime_result.safe_private_read_only_check_label
        == SAFE_PRIVATE_READ_ONLY_CHECK_LABEL
        and runtime_result.safe_account_assets_count > 0
        and runtime_result.safe_open_positions_count == 0
        and runtime_result.safe_active_orders_count == 0
    )


def _local_static_available(
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
    runtime_result: LiveOrderRealFreshPreflightRuntimeControlledResult,
) -> bool:
    return (
        snapshot.local_static_execution_mapping_available
        and runtime_result.local_static_check_ready
        and runtime_result.no_order_guard_ready
        and runtime_result.post_disabled
        and runtime_result.live_order_once_disabled
        and runtime_result.fresh_final_separation_maintained
        and runtime_result.safe_local_static_check_label == SAFE_LOCAL_STATIC_CHECK_LABEL
    )


def _failed(snapshot: LiveOrderRealFreshPreflightExecutionControlledInput) -> bool:
    return (
        snapshot.fresh_preflight_execution_failed
        or not snapshot.fresh_preflight_new_marker_required
        or not snapshot.fresh_preflight_current_marker_required
        or not snapshot.fresh_preflight_non_reuse_required
        or not snapshot.fresh_preflight_adapter_at_most_once
        or snapshot.fresh_preflight_retry_allowed
        or snapshot.fresh_preflight_unknown_retry_allowed
        or snapshot.fresh_preflight_timeout_retry_allowed
        or snapshot.fresh_preflight_failed_retry_allowed
    )


def _post_attempted(
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
) -> bool:
    return (
        snapshot.api_call_allowed
        or snapshot.api_call_executed
        or snapshot.public_api_call_executed
        or snapshot.private_api_call_executed
        or snapshot.post_allowed_this_step
        or snapshot.post_executed
        or snapshot.http_post_executed
    )


def _ledger_attempted(
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
) -> bool:
    return (
        snapshot.ledger_update_allowed
        or snapshot.ledger_updated
        or snapshot.ledger_update_attempted
        or snapshot.attempt_counter_persistence_allowed
        or snapshot.attempt_counter_persisted
    )


def _actual_receipt_attempted(
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
) -> bool:
    return (
        snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
        or snapshot.actual_receipt_handoff_allowed
    )


def _raw_exposed(
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
) -> bool:
    return (
        snapshot.unsafe_exposure_attempted
        or snapshot.raw_request_exposure_attempted
        or snapshot.raw_response_exposure_attempted
        or snapshot.request_body_exposure_attempted
        or snapshot.response_body_exposure_attempted
        or snapshot.broker_response_exposure_attempted
        or snapshot.api_response_exposure_attempted
        or snapshot.endpoint_actual_value_exposure_attempted
        or snapshot.raw_request_stored
        or snapshot.raw_response_stored
        or snapshot.broker_response_exposed
        or snapshot.api_response_exposed
    )


def _id_exposed(snapshot: LiveOrderRealFreshPreflightExecutionControlledInput) -> bool:
    return (
        snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.position_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
        or snapshot.real_id_exposure_attempted
        or snapshot.real_id_exposed
    )


def _value_exposed(
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
) -> bool:
    return (
        snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
        or snapshot.confirmation_phrase_exposure_attempted
        or snapshot.ledger_state_exposure_attempted
        or snapshot.approval_command_exposure_attempted
        or snapshot.ledger_state_actual_value_exposed
    )


def _blocked_reasons(
    *,
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
    runtime_result: LiveOrderRealFreshPreflightRuntimeControlledResult,
    primary_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = list(primary_reasons)
    if _adapter_contract_missing(snapshot):
        reasons.append("fresh_preflight_execution_adapter_contract_missing")
    if not _runtime_ready(runtime_result):
        reasons.append("fresh_preflight_runtime_missing_or_not_ready")
    if not _public_market_available(snapshot, runtime_result):
        reasons.append("public_market_execution_mapping_missing_or_not_ready")
    if not _private_read_only_available(snapshot, runtime_result):
        reasons.append("private_read_only_execution_mapping_missing_or_not_ready")
    if not _local_static_available(snapshot, runtime_result):
        reasons.append("local_static_execution_mapping_missing_or_not_ready")
    if not snapshot.safe_output_renderer_ready:
        reasons.append("safe_output_renderer_missing_or_not_ready")
    if snapshot.fresh_preflight_execution_unknown:
        reasons.append("fresh_preflight_execution_unknown")
    if snapshot.fresh_preflight_execution_failed:
        reasons.append("fresh_preflight_execution_failed")
    if snapshot.fresh_preflight_execution_timeout:
        reasons.append("fresh_preflight_execution_timeout")
    if snapshot.fresh_preflight_execution_unavailable:
        reasons.append("fresh_preflight_execution_unavailable")
    if snapshot.fresh_preflight_execution_stale:
        reasons.append("fresh_preflight_execution_stale")
    if snapshot.fresh_preflight_execution_reused:
        reasons.append("fresh_preflight_execution_reused")
    if not snapshot.fresh_preflight_new_marker_required:
        reasons.append("fresh_preflight_new_marker_not_required")
    if not snapshot.fresh_preflight_current_marker_required:
        reasons.append("fresh_preflight_current_marker_not_required")
    if not snapshot.fresh_preflight_non_reuse_required:
        reasons.append("fresh_preflight_non_reuse_not_required")
    if not snapshot.fresh_preflight_adapter_at_most_once:
        reasons.append("fresh_preflight_adapter_at_most_once_not_enforced")
    if _retry_allowed(snapshot):
        reasons.append("fresh_preflight_retry_allowed")
    if snapshot.fresh_preflight_execution_performed:
        reasons.append("fresh_preflight_execution_performed_in_adapter_setup_step")
    if _post_attempted(snapshot):
        reasons.append("api_or_post_attempted")
    if snapshot.order_endpoint_called:
        reasons.append("order_endpoint_called")
    if snapshot.live_order_once_called:
        reasons.append("live_order_once_called")
    if snapshot.final_confirmation_received:
        reasons.append("final_confirmation_received")
    if _ledger_attempted(snapshot):
        reasons.append("ledger_or_attempt_counter_attempted")
    if _actual_receipt_attempted(snapshot):
        reasons.append("actual_receipt_or_handoff_attempted")
    if _raw_exposed(snapshot):
        reasons.append("raw_or_response_exposure_attempted")
    if _id_exposed(snapshot):
        reasons.append("id_exposure_attempted")
    if _value_exposed(snapshot):
        reasons.append("value_exposure_attempted")
    if not snapshot.safe_to_render:
        reasons.append("fresh_preflight_execution_render_not_safe")
    if not snapshot.safe_to_serialize:
        reasons.append("fresh_preflight_execution_serialize_not_safe")
    return tuple(dict.fromkeys(reasons))


def _retry_allowed(
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
) -> bool:
    return (
        snapshot.fresh_preflight_retry_allowed
        or snapshot.fresh_preflight_unknown_retry_allowed
        or snapshot.fresh_preflight_timeout_retry_allowed
        or snapshot.fresh_preflight_failed_retry_allowed
    )


def _build_check_results(
    *,
    snapshot: LiveOrderRealFreshPreflightExecutionControlledInput,
    runtime_result: LiveOrderRealFreshPreflightRuntimeControlledResult,
    status: LiveOrderRealFreshPreflightExecutionControlledStatus,
    ready: bool,
    safe_label: str,
) -> tuple[LiveOrderRealFreshPreflightExecutionControlledCheckResult, ...]:
    return (
        LiveOrderRealFreshPreflightExecutionControlledCheckResult(
            name="fresh_preflight_execution_adapter_ready",
            passed=ready,
            sanitized_value=status.value,
            expected=(
                FreshPreflightExecutionControlledStatus
                .FRESH_PREFLIGHT_EXECUTION_ADAPTER_READY_NO_EXECUTION
                .value
            ),
        ),
        LiveOrderRealFreshPreflightExecutionControlledCheckResult(
            name="safe_preflight_execution_label",
            passed=safe_label == SAFE_PREFLIGHT_EXECUTION_LABEL,
            sanitized_value=safe_label,
            expected=SAFE_PREFLIGHT_EXECUTION_LABEL,
        ),
        LiveOrderRealFreshPreflightExecutionControlledCheckResult(
            name="runtime_ready",
            passed=_runtime_ready(runtime_result),
            sanitized_value=_bool_text(_runtime_ready(runtime_result)),
            expected="true",
        ),
        LiveOrderRealFreshPreflightExecutionControlledCheckResult(
            name="public_market_execution_mapping_available",
            passed=_public_market_available(snapshot, runtime_result),
            sanitized_value=_bool_text(_public_market_available(snapshot, runtime_result)),
            expected="true",
        ),
        LiveOrderRealFreshPreflightExecutionControlledCheckResult(
            name="private_read_only_execution_mapping_available",
            passed=_private_read_only_available(snapshot, runtime_result),
            sanitized_value=_bool_text(
                _private_read_only_available(snapshot, runtime_result),
            ),
            expected="true",
        ),
        LiveOrderRealFreshPreflightExecutionControlledCheckResult(
            name="local_static_execution_mapping_available",
            passed=_local_static_available(snapshot, runtime_result),
            sanitized_value=_bool_text(_local_static_available(snapshot, runtime_result)),
            expected="true",
        ),
        LiveOrderRealFreshPreflightExecutionControlledCheckResult(
            name="fresh_preflight_not_executed",
            passed=not snapshot.fresh_preflight_execution_performed,
            sanitized_value=_bool_text(not snapshot.fresh_preflight_execution_performed),
            expected="true",
        ),
        LiveOrderRealFreshPreflightExecutionControlledCheckResult(
            name="adapter_at_most_once_no_retry",
            passed=snapshot.fresh_preflight_adapter_at_most_once
            and not _retry_allowed(snapshot),
            sanitized_value=_bool_text(
                snapshot.fresh_preflight_adapter_at_most_once
                and not _retry_allowed(snapshot),
            ),
            expected="true",
        ),
        LiveOrderRealFreshPreflightExecutionControlledCheckResult(
            name="post_disabled",
            passed=not _post_attempted(snapshot),
            sanitized_value=_bool_text(not _post_attempted(snapshot)),
            expected="true",
        ),
    )


def _validate_result_safety(
    result: LiveOrderRealFreshPreflightExecutionControlledResult,
) -> None:
    if result.fresh_preflight_execution_performed:
        raise LiveVerificationValidationError("fresh preflight execution must not run")
    if (
        result.api_call_allowed
        or result.api_call_executed
        or result.public_api_call_executed
        or result.private_api_call_executed
        or result.post_allowed_this_step
        or result.post_executed
        or result.http_post_executed
    ):
        raise LiveVerificationValidationError("API or POST must remain disabled")
    if result.order_endpoint_called or result.live_order_once_called:
        raise LiveVerificationValidationError("order route must remain disabled")
    if result.final_confirmation_received:
        raise LiveVerificationValidationError("final confirmation must not be received")
    if (
        result.ledger_update_allowed
        or result.ledger_updated
        or result.attempt_counter_persistence_allowed
        or result.attempt_counter_persisted
    ):
        raise LiveVerificationValidationError("ledger and attempt state must not change")
    if (
        result.actual_result_receipt_received
        or result.actual_receipt_handoff_executed
        or result.actual_receipt_handoff_allowed
    ):
        raise LiveVerificationValidationError("actual receipt must not be handled")
    if (
        result.raw_request_stored
        or result.raw_response_stored
        or result.broker_response_exposed
        or result.api_response_exposed
        or result.real_id_exposed
        or result.ledger_state_actual_value_exposed
    ):
        raise LiveVerificationValidationError("unsafe exposure must not be returned")


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{name} must be non-empty string")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_non_negative_int(name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{name} must be non-negative int")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


_FRESH_PREFLIGHT_EXECUTION_INPUT_BOOL_FIELDS = (
    "fresh_preflight_execution_adapter_declared",
    "fresh_preflight_execution_adapter_requested",
    "safe_output_renderer_ready",
    "public_market_execution_mapping_available",
    "private_read_only_execution_mapping_available",
    "local_static_execution_mapping_available",
    "fresh_preflight_new_marker_required",
    "fresh_preflight_current_marker_required",
    "fresh_preflight_non_reuse_required",
    "fresh_preflight_adapter_at_most_once",
    "fresh_preflight_retry_allowed",
    "fresh_preflight_unknown_retry_allowed",
    "fresh_preflight_timeout_retry_allowed",
    "fresh_preflight_failed_retry_allowed",
    "fresh_preflight_execution_unknown",
    "fresh_preflight_execution_failed",
    "fresh_preflight_execution_unavailable",
    "fresh_preflight_execution_timeout",
    "fresh_preflight_execution_stale",
    "fresh_preflight_execution_reused",
    "fresh_preflight_execution_performed",
    "api_call_allowed",
    "api_call_executed",
    "public_api_call_executed",
    "private_api_call_executed",
    "post_allowed_this_step",
    "post_executed",
    "http_post_executed",
    "order_endpoint_called",
    "live_order_once_called",
    "final_confirmation_received",
    "ledger_update_allowed",
    "ledger_updated",
    "ledger_update_attempted",
    "attempt_counter_persistence_allowed",
    "attempt_counter_persisted",
    "actual_result_receipt_received",
    "actual_receipt_handoff_executed",
    "actual_receipt_handoff_allowed",
    "unsafe_exposure_attempted",
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
    "raw_request_exposure_attempted",
    "raw_response_exposure_attempted",
    "request_body_exposure_attempted",
    "response_body_exposure_attempted",
    "broker_response_exposure_attempted",
    "api_response_exposure_attempted",
    "endpoint_actual_value_exposure_attempted",
    "account_id_exposure_attempted",
    "order_id_exposure_attempted",
    "transaction_id_exposure_attempted",
    "position_id_exposure_attempted",
    "trade_id_exposure_attempted",
    "real_id_exposure_attempted",
    "confirmation_phrase_exposure_attempted",
    "ledger_state_exposure_attempted",
    "approval_command_exposure_attempted",
    "raw_request_stored",
    "raw_response_stored",
    "broker_response_exposed",
    "api_response_exposed",
    "real_id_exposed",
    "ledger_state_actual_value_exposed",
    "safe_to_render",
    "safe_to_serialize",
)

_FRESH_PREFLIGHT_EXECUTION_RESULT_BOOL_FIELDS = (
    "fresh_preflight_execution_command_available",
    "fresh_preflight_execution_allowed_next_step",
    "fresh_preflight_runtime_ready",
    "fresh_preflight_execution_performed",
    "fresh_preflight_new_marker_required",
    "fresh_preflight_current_marker_required",
    "fresh_preflight_non_reuse_required",
    "fresh_preflight_adapter_at_most_once",
    "fresh_preflight_retry_allowed",
    "fresh_preflight_unknown_retry_allowed",
    "fresh_preflight_timeout_retry_allowed",
    "fresh_preflight_failed_retry_allowed",
    "public_market_check_available",
    "private_read_only_check_available",
    "local_static_check_available",
    "safe_output_renderer_ready",
    "api_call_allowed",
    "api_call_executed",
    "public_api_call_executed",
    "private_api_call_executed",
    "post_allowed_this_step",
    "post_executed",
    "http_post_executed",
    "order_endpoint_called",
    "live_order_once_called",
    "final_confirmation_received",
    "ledger_update_allowed",
    "ledger_updated",
    "attempt_counter_persistence_allowed",
    "attempt_counter_persisted",
    "actual_result_receipt_received",
    "actual_receipt_handoff_executed",
    "actual_receipt_handoff_allowed",
    "raw_request_stored",
    "raw_response_stored",
    "broker_response_exposed",
    "api_response_exposed",
    "real_id_exposed",
    "ledger_state_actual_value_exposed",
    "safe_to_render",
    "safe_to_serialize",
)
