"""Step 6G controlled fresh preflight runtime route.

This module prepares the fresh preflight runtime route as a safe contract only.
It does not execute fresh preflight, HTTP POST, order endpoints,
live_order_once, final confirmation, ledger updates, attempt persistence,
actual result receipt, or receipt handoff.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_final_exec_stack_controlled import (
    SAFE_DRY_RUN_STACK_LABEL,
    LiveOrderRealFinalExecStackControlledResult,
    LiveOrderRealFinalExecStackControlledStatus,
)
from app.live_verification.live_order_real_post_guard_controlled import (
    SAFE_POST_GUARD_LABEL,
    LiveOrderRealPostGuardControlledResult,
    LiveOrderRealPostGuardControlledStatus,
)

FRESH_PREFLIGHT_RUNTIME_RECOMMENDED_NEXT_STEP = (
    "fresh_preflight_check_retry_no_post_no_final_confirmation"
)
SAFE_PREFLIGHT_RUNTIME_LABEL = "CONTROLLED_FRESH_PREFLIGHT_RUNTIME_ROUTE"
SAFE_PUBLIC_MARKET_CHECK_LABEL = "PUBLIC_MARKET_SAFE_CHECK_ROUTE"
SAFE_PRIVATE_READ_ONLY_CHECK_LABEL = "PRIVATE_READ_ONLY_SAFE_CHECK_ROUTE"
SAFE_LOCAL_STATIC_CHECK_LABEL = "LOCAL_STATIC_SAFE_CHECK_ROUTE"
UNSUPPORTED_PREFLIGHT_RUNTIME_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealFreshPreflightRuntimeControlledStatus(str, Enum):
    FRESH_PREFLIGHT_RUNTIME_NOT_READY = "FRESH_PREFLIGHT_RUNTIME_NOT_READY"
    FRESH_PREFLIGHT_RUNTIME_READY_NO_EXECUTION = (
        "FRESH_PREFLIGHT_RUNTIME_READY_NO_EXECUTION"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_PUBLIC_MARKET = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_PUBLIC_MARKET"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_PRIVATE_READ_ONLY = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_PRIVATE_READ_ONLY"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_LOCAL_STATIC = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_LOCAL_STATIC"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_FINAL_EXEC_STACK = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_FINAL_EXEC_STACK"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_UNKNOWN = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_UNKNOWN"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_FAILED = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_FAILED"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_TIMEOUT = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_TIMEOUT"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_UNAVAILABLE = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_UNAVAILABLE"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_STALE = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_STALE"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_REUSED = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_REUSED"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_POST_ATTEMPTED = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_POST_ATTEMPTED"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_ORDER_ENDPOINT = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_ORDER_ENDPOINT"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_LIVE_ORDER_ONCE = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_LIVE_ORDER_ONCE"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_FINAL_CONFIRMATION = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_FINAL_CONFIRMATION"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_LEDGER_UPDATE = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_LEDGER_UPDATE"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_ACTUAL_RECEIPT = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_ACTUAL_RECEIPT"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_RAW_EXPOSURE = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_RAW_EXPOSURE"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_ID_EXPOSURE = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_ID_EXPOSURE"
    )
    FRESH_PREFLIGHT_RUNTIME_BLOCKED_VALUE_EXPOSURE = (
        "FRESH_PREFLIGHT_RUNTIME_BLOCKED_VALUE_EXPOSURE"
    )


class LiveOrderRealFreshPreflightRuntimeControlledMode(str, Enum):
    FRESH_PREFLIGHT_RUNTIME_CONTROLLED_IMPLEMENTATION_ONLY = (
        "FRESH_PREFLIGHT_RUNTIME_CONTROLLED_IMPLEMENTATION_ONLY"
    )


FreshPreflightRuntimeControlledStatus = (
    LiveOrderRealFreshPreflightRuntimeControlledStatus
)
FreshPreflightRuntimeControlledMode = (
    LiveOrderRealFreshPreflightRuntimeControlledMode
)


@dataclass(frozen=True)
class LiveOrderRealFreshPreflightRuntimeControlledInput:
    fresh_preflight_runtime_mode: str = (
        FreshPreflightRuntimeControlledMode
        .FRESH_PREFLIGHT_RUNTIME_CONTROLLED_IMPLEMENTATION_ONLY
        .value
    )
    fresh_preflight_runtime_declared: bool = True
    fresh_preflight_runtime_requested: bool = True
    safe_preflight_runtime_label: str = SAFE_PREFLIGHT_RUNTIME_LABEL
    public_market_check_declared: bool = True
    public_market_check_ready: bool = True
    public_market_status_safe: bool = True
    public_market_ticker_safe: bool = True
    public_market_spread_check_ready: bool = True
    public_market_age_check_ready: bool = True
    safe_public_market_check_label: str = SAFE_PUBLIC_MARKET_CHECK_LABEL
    private_read_only_check_declared: bool = True
    private_read_only_check_ready: bool = True
    account_assets_check_ready: bool = True
    open_positions_check_ready: bool = True
    active_orders_check_ready: bool = True
    safe_private_read_only_check_label: str = SAFE_PRIVATE_READ_ONLY_CHECK_LABEL
    safe_account_assets_count: int = 1
    safe_open_positions_count: int = 0
    safe_active_orders_count: int = 0
    local_static_check_declared: bool = True
    local_static_check_ready: bool = True
    git_state_expected_clean: bool = True
    head_origin_expected_match: bool = True
    no_order_guard_ready: bool = True
    post_disabled: bool = True
    live_order_once_disabled: bool = True
    fresh_final_separation_maintained: bool = True
    safe_local_static_check_label: str = SAFE_LOCAL_STATIC_CHECK_LABEL
    final_exec_stack_prerequisite_checked: bool = True
    final_exec_stack_ready: bool = True
    final_exec_stack_prerequisite_satisfied: bool = True
    safe_dry_run_stack_label: str = SAFE_DRY_RUN_STACK_LABEL
    safe_dry_run_stack_status: str = (
        LiveOrderRealFinalExecStackControlledStatus
        .FINAL_EXEC_STACK_READY_DRY_RUN_ONLY
        .value
    )
    final_exec_stack_one_shot_post_allowed: bool = False
    post_guard_prerequisite_checked: bool = True
    post_guard_ready: bool = True
    post_guard_prerequisite_satisfied: bool = True
    safe_post_guard_label: str = SAFE_POST_GUARD_LABEL
    safe_post_guard_status: str = (
        LiveOrderRealPostGuardControlledStatus.POST_GUARD_READY_NO_POST.value
    )
    fresh_preflight_runtime_unknown: bool = False
    fresh_preflight_runtime_failed: bool = False
    fresh_preflight_runtime_unavailable: bool = False
    fresh_preflight_runtime_timeout: bool = False
    fresh_preflight_runtime_stale: bool = False
    fresh_preflight_runtime_reused: bool = False
    fresh_preflight_executed: bool = False
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
            "fresh_preflight_runtime_mode",
            self.fresh_preflight_runtime_mode,
        )
        _require_non_empty(
            "safe_preflight_runtime_label",
            self.safe_preflight_runtime_label,
        )
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
        _require_non_empty("safe_dry_run_stack_label", self.safe_dry_run_stack_label)
        _require_non_empty("safe_dry_run_stack_status", self.safe_dry_run_stack_status)
        _require_non_empty("safe_post_guard_label", self.safe_post_guard_label)
        _require_non_empty("safe_post_guard_status", self.safe_post_guard_status)
        _validate_bool_fields(self, _FRESH_PREFLIGHT_RUNTIME_INPUT_BOOL_FIELDS)
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


@dataclass(frozen=True)
class LiveOrderRealFreshPreflightRuntimeControlledCheckResult:
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
class LiveOrderRealFreshPreflightRuntimeControlledResult:
    status: LiveOrderRealFreshPreflightRuntimeControlledStatus
    fresh_preflight_runtime_ready: bool
    fresh_preflight_runtime_mode: str
    fresh_preflight_runtime_declared: bool
    fresh_preflight_runtime_requested: bool
    safe_preflight_runtime_label: str
    safe_preflight_runtime_status: str
    public_market_check_ready: bool
    public_market_status_safe: bool
    public_market_ticker_safe: bool
    public_market_spread_check_ready: bool
    public_market_age_check_ready: bool
    safe_public_market_check_label: str
    private_read_only_check_ready: bool
    account_assets_check_ready: bool
    open_positions_check_ready: bool
    active_orders_check_ready: bool
    safe_private_read_only_check_label: str
    safe_account_assets_count: int
    safe_open_positions_count: int
    safe_active_orders_count: int
    local_static_check_ready: bool
    git_state_expected_clean: bool
    head_origin_expected_match: bool
    no_order_guard_ready: bool
    post_disabled: bool
    live_order_once_disabled: bool
    fresh_final_separation_maintained: bool
    safe_local_static_check_label: str
    final_exec_stack_ready: bool
    final_exec_stack_prerequisite_satisfied: bool
    safe_dry_run_stack_label: str
    safe_dry_run_stack_status: str
    post_guard_ready: bool
    post_guard_prerequisite_satisfied: bool
    safe_post_guard_label: str
    safe_post_guard_status: str
    fresh_preflight_runtime_unknown: bool
    fresh_preflight_runtime_failed: bool
    fresh_preflight_runtime_unavailable: bool
    fresh_preflight_runtime_timeout: bool
    fresh_preflight_runtime_stale: bool
    fresh_preflight_runtime_reused: bool
    fresh_preflight_executed: bool
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
        LiveOrderRealFreshPreflightRuntimeControlledCheckResult,
        ...,
    ]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealFreshPreflightRuntimeControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be fresh preflight runtime controlled status",
            )
        _require_non_empty(
            "fresh_preflight_runtime_mode",
            self.fresh_preflight_runtime_mode,
        )
        _require_non_empty(
            "safe_preflight_runtime_label",
            self.safe_preflight_runtime_label,
        )
        _require_non_empty(
            "safe_preflight_runtime_status",
            self.safe_preflight_runtime_status,
        )
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
        _require_non_empty("safe_dry_run_stack_label", self.safe_dry_run_stack_label)
        _require_non_empty("safe_dry_run_stack_status", self.safe_dry_run_stack_status)
        _require_non_empty("safe_post_guard_label", self.safe_post_guard_label)
        _require_non_empty("safe_post_guard_status", self.safe_post_guard_status)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(self, _FRESH_PREFLIGHT_RUNTIME_RESULT_BOOL_FIELDS)
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


def build_live_order_real_fresh_preflight_runtime_controlled(
    *,
    input_snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput | None = None,
    final_exec_stack_result: LiveOrderRealFinalExecStackControlledResult | None = None,
    post_guard_result: LiveOrderRealPostGuardControlledResult | None = None,
) -> LiveOrderRealFreshPreflightRuntimeControlledResult:
    """Build a safe fresh preflight runtime route without executing it."""
    snapshot = input_snapshot or LiveOrderRealFreshPreflightRuntimeControlledInput()
    if final_exec_stack_result is not None:
        snapshot = _merge_final_exec_stack_result(snapshot, final_exec_stack_result)
    if post_guard_result is not None:
        snapshot = _merge_post_guard_result(snapshot, post_guard_result)

    status, primary_reasons = _status_from_input(snapshot)
    ready = (
        status
        is FreshPreflightRuntimeControlledStatus
        .FRESH_PREFLIGHT_RUNTIME_READY_NO_EXECUTION
    )
    safe_mode = (
        snapshot.fresh_preflight_runtime_mode
        if snapshot.fresh_preflight_runtime_mode
        == (
            FreshPreflightRuntimeControlledMode
            .FRESH_PREFLIGHT_RUNTIME_CONTROLLED_IMPLEMENTATION_ONLY
            .value
        )
        else UNSUPPORTED_PREFLIGHT_RUNTIME_LABEL
    )
    safe_runtime_label = (
        snapshot.safe_preflight_runtime_label
        if snapshot.safe_preflight_runtime_label == SAFE_PREFLIGHT_RUNTIME_LABEL
        else UNSUPPORTED_PREFLIGHT_RUNTIME_LABEL
    )
    safe_public_label = (
        snapshot.safe_public_market_check_label
        if snapshot.safe_public_market_check_label == SAFE_PUBLIC_MARKET_CHECK_LABEL
        else UNSUPPORTED_PREFLIGHT_RUNTIME_LABEL
    )
    safe_private_label = (
        snapshot.safe_private_read_only_check_label
        if snapshot.safe_private_read_only_check_label
        == SAFE_PRIVATE_READ_ONLY_CHECK_LABEL
        else UNSUPPORTED_PREFLIGHT_RUNTIME_LABEL
    )
    safe_local_label = (
        snapshot.safe_local_static_check_label
        if snapshot.safe_local_static_check_label == SAFE_LOCAL_STATIC_CHECK_LABEL
        else UNSUPPORTED_PREFLIGHT_RUNTIME_LABEL
    )
    safe_stack_label = (
        snapshot.safe_dry_run_stack_label
        if snapshot.safe_dry_run_stack_label == SAFE_DRY_RUN_STACK_LABEL
        else UNSUPPORTED_PREFLIGHT_RUNTIME_LABEL
    )
    safe_post_guard_label = (
        snapshot.safe_post_guard_label
        if snapshot.safe_post_guard_label == SAFE_POST_GUARD_LABEL
        else UNSUPPORTED_PREFLIGHT_RUNTIME_LABEL
    )
    blocked_reasons = _blocked_reasons(
        snapshot=snapshot,
        primary_reasons=primary_reasons,
    )

    return LiveOrderRealFreshPreflightRuntimeControlledResult(
        status=status,
        fresh_preflight_runtime_ready=ready,
        fresh_preflight_runtime_mode=safe_mode,
        fresh_preflight_runtime_declared=snapshot.fresh_preflight_runtime_declared,
        fresh_preflight_runtime_requested=snapshot.fresh_preflight_runtime_requested,
        safe_preflight_runtime_label=safe_runtime_label,
        safe_preflight_runtime_status=status.value,
        public_market_check_ready=_public_market_ready(snapshot),
        public_market_status_safe=snapshot.public_market_status_safe,
        public_market_ticker_safe=snapshot.public_market_ticker_safe,
        public_market_spread_check_ready=snapshot.public_market_spread_check_ready,
        public_market_age_check_ready=snapshot.public_market_age_check_ready,
        safe_public_market_check_label=safe_public_label,
        private_read_only_check_ready=_private_read_only_ready(snapshot),
        account_assets_check_ready=snapshot.account_assets_check_ready,
        open_positions_check_ready=snapshot.open_positions_check_ready,
        active_orders_check_ready=snapshot.active_orders_check_ready,
        safe_private_read_only_check_label=safe_private_label,
        safe_account_assets_count=snapshot.safe_account_assets_count,
        safe_open_positions_count=snapshot.safe_open_positions_count,
        safe_active_orders_count=snapshot.safe_active_orders_count,
        local_static_check_ready=_local_static_ready(snapshot),
        git_state_expected_clean=snapshot.git_state_expected_clean,
        head_origin_expected_match=snapshot.head_origin_expected_match,
        no_order_guard_ready=snapshot.no_order_guard_ready,
        post_disabled=snapshot.post_disabled,
        live_order_once_disabled=snapshot.live_order_once_disabled,
        fresh_final_separation_maintained=(
            snapshot.fresh_final_separation_maintained
        ),
        safe_local_static_check_label=safe_local_label,
        final_exec_stack_ready=_final_exec_stack_ready(snapshot),
        final_exec_stack_prerequisite_satisfied=(
            snapshot.final_exec_stack_prerequisite_satisfied
        ),
        safe_dry_run_stack_label=safe_stack_label,
        safe_dry_run_stack_status=snapshot.safe_dry_run_stack_status,
        post_guard_ready=_post_guard_ready(snapshot),
        post_guard_prerequisite_satisfied=(
            snapshot.post_guard_prerequisite_satisfied
        ),
        safe_post_guard_label=safe_post_guard_label,
        safe_post_guard_status=snapshot.safe_post_guard_status,
        fresh_preflight_runtime_unknown=snapshot.fresh_preflight_runtime_unknown,
        fresh_preflight_runtime_failed=snapshot.fresh_preflight_runtime_failed,
        fresh_preflight_runtime_unavailable=(
            snapshot.fresh_preflight_runtime_unavailable
        ),
        fresh_preflight_runtime_timeout=snapshot.fresh_preflight_runtime_timeout,
        fresh_preflight_runtime_stale=snapshot.fresh_preflight_runtime_stale,
        fresh_preflight_runtime_reused=snapshot.fresh_preflight_runtime_reused,
        fresh_preflight_executed=False,
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
            status=status,
            ready=ready,
            safe_runtime_label=safe_runtime_label,
        ),
        blocked_reasons=blocked_reasons,
        recommended_next_step=FRESH_PREFLIGHT_RUNTIME_RECOMMENDED_NEXT_STEP,
    )


def render_live_order_real_fresh_preflight_runtime_controlled_markdown(
    result: LiveOrderRealFreshPreflightRuntimeControlledResult,
) -> str:
    """Render a safe fresh preflight runtime route summary only."""
    lines = [
        "# Step 6G Fresh Preflight Runtime Controlled Contract",
        "",
        "This is a controlled runtime route contract, not fresh preflight execution.",
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
        "Runtime ready does not mean fresh preflight executed.",
        "Runtime ready does not allow POST.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- fresh_preflight_runtime_ready: "
            f"{_bool_text(result.fresh_preflight_runtime_ready)}"
        ),
        f"- fresh_preflight_runtime_mode: {result.fresh_preflight_runtime_mode}",
        f"- safe_preflight_runtime_label: {result.safe_preflight_runtime_label}",
        f"- safe_preflight_runtime_status: {result.safe_preflight_runtime_status}",
        "",
        "## Safe Route Inputs",
        f"- public_market_check_ready: {_bool_text(result.public_market_check_ready)}",
        (
            "- private_read_only_check_ready: "
            f"{_bool_text(result.private_read_only_check_ready)}"
        ),
        f"- local_static_check_ready: {_bool_text(result.local_static_check_ready)}",
        f"- final_exec_stack_ready: {_bool_text(result.final_exec_stack_ready)}",
        f"- post_guard_ready: {_bool_text(result.post_guard_ready)}",
        f"- no_order_guard_ready: {_bool_text(result.no_order_guard_ready)}",
        f"- safe_account_assets_count: {result.safe_account_assets_count}",
        f"- safe_open_positions_count: {result.safe_open_positions_count}",
        f"- safe_active_orders_count: {result.safe_active_orders_count}",
        "",
        "## Non-Execution",
        f"- fresh_preflight_executed: {_bool_text(result.fresh_preflight_executed)}",
        f"- api_call_executed: {_bool_text(result.api_call_executed)}",
        (
            "- public_api_call_executed: "
            f"{_bool_text(result.public_api_call_executed)}"
        ),
        (
            "- private_api_call_executed: "
            f"{_bool_text(result.private_api_call_executed)}"
        ),
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


def _merge_final_exec_stack_result(
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
    final_exec_stack_result: LiveOrderRealFinalExecStackControlledResult,
) -> LiveOrderRealFreshPreflightRuntimeControlledInput:
    return replace(
        snapshot,
        final_exec_stack_prerequisite_checked=True,
        final_exec_stack_ready=final_exec_stack_result.dry_run_stack_ready,
        final_exec_stack_prerequisite_satisfied=(
            final_exec_stack_result.dry_run_stack_ready
            and final_exec_stack_result.status
            is (
                LiveOrderRealFinalExecStackControlledStatus
                .FINAL_EXEC_STACK_READY_DRY_RUN_ONLY
            )
        ),
        safe_dry_run_stack_label=final_exec_stack_result.safe_dry_run_stack_label,
        safe_dry_run_stack_status=final_exec_stack_result.safe_dry_run_stack_status,
        final_exec_stack_one_shot_post_allowed=(
            final_exec_stack_result.one_shot_post_allowed
        ),
        fresh_preflight_executed=(
            snapshot.fresh_preflight_executed
            or final_exec_stack_result.fresh_preflight_executed
        ),
        api_call_executed=(
            snapshot.api_call_executed or final_exec_stack_result.api_call_executed
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step
            or final_exec_stack_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or final_exec_stack_result.post_executed,
        http_post_executed=(
            snapshot.http_post_executed or final_exec_stack_result.http_post_executed
        ),
        order_endpoint_called=(
            snapshot.order_endpoint_called
            or final_exec_stack_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called
            or final_exec_stack_result.live_order_once_called
        ),
        final_confirmation_received=(
            snapshot.final_confirmation_received
            or final_exec_stack_result.final_confirmation_received
        ),
        ledger_update_allowed=(
            snapshot.ledger_update_allowed
            or final_exec_stack_result.ledger_update_allowed
        ),
        ledger_updated=snapshot.ledger_updated or final_exec_stack_result.ledger_updated,
        attempt_counter_persistence_allowed=(
            snapshot.attempt_counter_persistence_allowed
            or final_exec_stack_result.attempt_counter_persistence_allowed
        ),
        attempt_counter_persisted=(
            snapshot.attempt_counter_persisted
            or final_exec_stack_result.attempt_counter_persisted
        ),
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or final_exec_stack_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or final_exec_stack_result.actual_receipt_handoff_executed
        ),
        actual_receipt_handoff_allowed=(
            snapshot.actual_receipt_handoff_allowed
            or final_exec_stack_result.actual_receipt_handoff_allowed
        ),
        raw_request_stored=(
            snapshot.raw_request_stored or final_exec_stack_result.raw_request_stored
        ),
        raw_response_stored=(
            snapshot.raw_response_stored or final_exec_stack_result.raw_response_stored
        ),
        broker_response_exposed=(
            snapshot.broker_response_exposed
            or final_exec_stack_result.broker_response_exposed
        ),
        api_response_exposed=(
            snapshot.api_response_exposed or final_exec_stack_result.api_response_exposed
        ),
        real_id_exposed=(
            snapshot.real_id_exposed or final_exec_stack_result.real_id_exposed
        ),
        ledger_state_actual_value_exposed=(
            snapshot.ledger_state_actual_value_exposed
            or final_exec_stack_result.ledger_state_actual_value_exposed
        ),
        safe_to_render=snapshot.safe_to_render and final_exec_stack_result.safe_to_render,
        safe_to_serialize=(
            snapshot.safe_to_serialize and final_exec_stack_result.safe_to_serialize
        ),
    )


def _merge_post_guard_result(
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
    post_guard_result: LiveOrderRealPostGuardControlledResult,
) -> LiveOrderRealFreshPreflightRuntimeControlledInput:
    return replace(
        snapshot,
        post_guard_prerequisite_checked=True,
        post_guard_ready=post_guard_result.post_guard_ready,
        post_guard_prerequisite_satisfied=(
            post_guard_result.post_guard_ready
            and post_guard_result.status
            is LiveOrderRealPostGuardControlledStatus.POST_GUARD_READY_NO_POST
        ),
        safe_post_guard_label=post_guard_result.safe_post_guard_label,
        safe_post_guard_status=post_guard_result.safe_post_guard_status,
        api_call_allowed=(
            snapshot.api_call_allowed or post_guard_result.api_call_allowed
        ),
        api_call_executed=(
            snapshot.api_call_executed
            or bool(getattr(post_guard_result, "api_call_executed", False))
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step
            or post_guard_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or post_guard_result.post_executed,
        http_post_executed=(
            snapshot.http_post_executed or post_guard_result.http_post_executed
        ),
        order_endpoint_called=(
            snapshot.order_endpoint_called or post_guard_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called or post_guard_result.live_order_once_called
        ),
        fresh_preflight_executed=(
            snapshot.fresh_preflight_executed
            or post_guard_result.fresh_preflight_executed
        ),
        final_confirmation_received=(
            snapshot.final_confirmation_received
            or post_guard_result.final_confirmation_received
        ),
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or post_guard_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or post_guard_result.actual_receipt_handoff_executed
        ),
    )


def _status_from_input(
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
) -> tuple[FreshPreflightRuntimeControlledStatus, tuple[str, ...]]:
    if _runtime_contract_missing(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus.FRESH_PREFLIGHT_RUNTIME_NOT_READY,
            ("fresh_preflight_runtime_contract_missing",),
        )
    if not _public_market_ready(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_PUBLIC_MARKET,
            ("public_market_check_missing_or_not_ready",),
        )
    if not _private_read_only_ready(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_PRIVATE_READ_ONLY,
            ("private_read_only_check_missing_or_not_ready",),
        )
    if not _local_static_ready(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_LOCAL_STATIC,
            ("local_static_check_missing_or_not_ready",),
        )
    if not _final_exec_stack_ready(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_FINAL_EXEC_STACK,
            ("final_exec_stack_missing_or_not_ready",),
        )
    if not _post_guard_ready(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_LOCAL_STATIC,
            ("post_guard_missing_or_not_ready",),
        )
    if snapshot.fresh_preflight_runtime_unknown:
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_UNKNOWN,
            ("fresh_preflight_runtime_unknown",),
        )
    if _failed(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_FAILED,
            ("fresh_preflight_runtime_failed_or_counts_not_clear",),
        )
    if snapshot.fresh_preflight_runtime_timeout:
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_TIMEOUT,
            ("fresh_preflight_runtime_timeout",),
        )
    if snapshot.fresh_preflight_runtime_unavailable:
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_UNAVAILABLE,
            ("fresh_preflight_runtime_unavailable",),
        )
    if snapshot.fresh_preflight_runtime_stale:
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_STALE,
            ("fresh_preflight_runtime_stale",),
        )
    if snapshot.fresh_preflight_runtime_reused:
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_REUSED,
            ("fresh_preflight_runtime_reused",),
        )
    if snapshot.fresh_preflight_executed:
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_FAILED,
            ("fresh_preflight_executed_in_runtime_contract_step",),
        )
    if _post_attempted(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_POST_ATTEMPTED,
            ("post_attempted",),
        )
    if snapshot.order_endpoint_called:
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_ORDER_ENDPOINT,
            ("order_endpoint_called",),
        )
    if snapshot.live_order_once_called:
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_LIVE_ORDER_ONCE,
            ("live_order_once_called",),
        )
    if snapshot.final_confirmation_received:
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_FINAL_CONFIRMATION,
            ("final_confirmation_received",),
        )
    if _ledger_attempted(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_LEDGER_UPDATE,
            ("ledger_or_attempt_counter_attempted",),
        )
    if _actual_receipt_attempted(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_ACTUAL_RECEIPT,
            ("actual_receipt_or_handoff_attempted",),
        )
    if _raw_exposed(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_RAW_EXPOSURE,
            ("raw_or_response_exposure_attempted",),
        )
    if _id_exposed(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_ID_EXPOSURE,
            ("id_exposure_attempted",),
        )
    if _value_exposed(snapshot):
        return (
            FreshPreflightRuntimeControlledStatus
            .FRESH_PREFLIGHT_RUNTIME_BLOCKED_VALUE_EXPOSURE,
            ("value_exposure_attempted",),
        )
    return (
        FreshPreflightRuntimeControlledStatus
        .FRESH_PREFLIGHT_RUNTIME_READY_NO_EXECUTION,
        (),
    )


def _runtime_contract_missing(
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
) -> bool:
    return not (
        snapshot.fresh_preflight_runtime_declared
        and snapshot.fresh_preflight_runtime_requested
        and snapshot.safe_preflight_runtime_label == SAFE_PREFLIGHT_RUNTIME_LABEL
        and snapshot.fresh_preflight_runtime_mode
        == (
            FreshPreflightRuntimeControlledMode
            .FRESH_PREFLIGHT_RUNTIME_CONTROLLED_IMPLEMENTATION_ONLY
            .value
        )
    )


def _public_market_ready(
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
) -> bool:
    return (
        snapshot.public_market_check_declared
        and snapshot.public_market_check_ready
        and snapshot.public_market_status_safe
        and snapshot.public_market_ticker_safe
        and snapshot.public_market_spread_check_ready
        and snapshot.public_market_age_check_ready
        and snapshot.safe_public_market_check_label == SAFE_PUBLIC_MARKET_CHECK_LABEL
    )


def _private_read_only_ready(
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
) -> bool:
    return (
        snapshot.private_read_only_check_declared
        and snapshot.private_read_only_check_ready
        and snapshot.account_assets_check_ready
        and snapshot.open_positions_check_ready
        and snapshot.active_orders_check_ready
        and snapshot.safe_private_read_only_check_label
        == SAFE_PRIVATE_READ_ONLY_CHECK_LABEL
        and snapshot.safe_account_assets_count > 0
        and snapshot.safe_open_positions_count == 0
        and snapshot.safe_active_orders_count == 0
    )


def _local_static_ready(
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
) -> bool:
    return (
        snapshot.local_static_check_declared
        and snapshot.local_static_check_ready
        and snapshot.git_state_expected_clean
        and snapshot.head_origin_expected_match
        and snapshot.no_order_guard_ready
        and snapshot.post_disabled
        and snapshot.live_order_once_disabled
        and snapshot.fresh_final_separation_maintained
        and snapshot.safe_local_static_check_label == SAFE_LOCAL_STATIC_CHECK_LABEL
    )


def _final_exec_stack_ready(
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
) -> bool:
    return (
        snapshot.final_exec_stack_prerequisite_checked
        and snapshot.final_exec_stack_ready
        and snapshot.final_exec_stack_prerequisite_satisfied
        and snapshot.safe_dry_run_stack_label == SAFE_DRY_RUN_STACK_LABEL
        and snapshot.safe_dry_run_stack_status
        == (
            LiveOrderRealFinalExecStackControlledStatus
            .FINAL_EXEC_STACK_READY_DRY_RUN_ONLY
            .value
        )
        and not snapshot.final_exec_stack_one_shot_post_allowed
    )


def _post_guard_ready(
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
) -> bool:
    return (
        snapshot.post_guard_prerequisite_checked
        and snapshot.post_guard_ready
        and snapshot.post_guard_prerequisite_satisfied
        and snapshot.safe_post_guard_label == SAFE_POST_GUARD_LABEL
        and snapshot.safe_post_guard_status
        == LiveOrderRealPostGuardControlledStatus.POST_GUARD_READY_NO_POST.value
    )


def _failed(snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput) -> bool:
    return (
        snapshot.fresh_preflight_runtime_failed
        or snapshot.safe_account_assets_count <= 0
        or snapshot.safe_open_positions_count != 0
        or snapshot.safe_active_orders_count != 0
    )


def _post_attempted(
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
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
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
) -> bool:
    return (
        snapshot.ledger_update_allowed
        or snapshot.ledger_updated
        or snapshot.ledger_update_attempted
        or snapshot.attempt_counter_persistence_allowed
        or snapshot.attempt_counter_persisted
    )


def _actual_receipt_attempted(
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
) -> bool:
    return (
        snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
        or snapshot.actual_receipt_handoff_allowed
    )


def _raw_exposed(snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput) -> bool:
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


def _id_exposed(snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput) -> bool:
    return (
        snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.position_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
        or snapshot.real_id_exposure_attempted
        or snapshot.real_id_exposed
    )


def _value_exposed(snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput) -> bool:
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
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
    primary_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = list(primary_reasons)
    if _runtime_contract_missing(snapshot):
        reasons.append("fresh_preflight_runtime_contract_missing")
    if not _public_market_ready(snapshot):
        reasons.append("public_market_check_missing_or_not_ready")
    if not _private_read_only_ready(snapshot):
        reasons.append("private_read_only_check_missing_or_not_ready")
    if not _local_static_ready(snapshot):
        reasons.append("local_static_check_missing_or_not_ready")
    if not _final_exec_stack_ready(snapshot):
        reasons.append("final_exec_stack_missing_or_not_ready")
    if not _post_guard_ready(snapshot):
        reasons.append("post_guard_missing_or_not_ready")
    if snapshot.fresh_preflight_runtime_unknown:
        reasons.append("fresh_preflight_runtime_unknown")
    if snapshot.fresh_preflight_runtime_failed:
        reasons.append("fresh_preflight_runtime_failed")
    if snapshot.fresh_preflight_runtime_timeout:
        reasons.append("fresh_preflight_runtime_timeout")
    if snapshot.fresh_preflight_runtime_unavailable:
        reasons.append("fresh_preflight_runtime_unavailable")
    if snapshot.fresh_preflight_runtime_stale:
        reasons.append("fresh_preflight_runtime_stale")
    if snapshot.fresh_preflight_runtime_reused:
        reasons.append("fresh_preflight_runtime_reused")
    if snapshot.safe_account_assets_count <= 0:
        reasons.append("safe_account_assets_count_not_positive")
    if snapshot.safe_open_positions_count != 0:
        reasons.append("safe_open_positions_count_not_zero")
    if snapshot.safe_active_orders_count != 0:
        reasons.append("safe_active_orders_count_not_zero")
    if snapshot.fresh_preflight_executed:
        reasons.append("fresh_preflight_executed_in_runtime_contract_step")
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
        reasons.append("fresh_preflight_runtime_render_not_safe")
    if not snapshot.safe_to_serialize:
        reasons.append("fresh_preflight_runtime_serialize_not_safe")
    return tuple(dict.fromkeys(reasons))


def _build_check_results(
    *,
    snapshot: LiveOrderRealFreshPreflightRuntimeControlledInput,
    status: LiveOrderRealFreshPreflightRuntimeControlledStatus,
    ready: bool,
    safe_runtime_label: str,
) -> tuple[LiveOrderRealFreshPreflightRuntimeControlledCheckResult, ...]:
    return (
        LiveOrderRealFreshPreflightRuntimeControlledCheckResult(
            name="fresh_preflight_runtime_ready",
            passed=ready,
            sanitized_value=status.value,
            expected=(
                FreshPreflightRuntimeControlledStatus
                .FRESH_PREFLIGHT_RUNTIME_READY_NO_EXECUTION
                .value
            ),
        ),
        LiveOrderRealFreshPreflightRuntimeControlledCheckResult(
            name="safe_preflight_runtime_label",
            passed=safe_runtime_label == SAFE_PREFLIGHT_RUNTIME_LABEL,
            sanitized_value=safe_runtime_label,
            expected=SAFE_PREFLIGHT_RUNTIME_LABEL,
        ),
        LiveOrderRealFreshPreflightRuntimeControlledCheckResult(
            name="public_market_check_ready",
            passed=_public_market_ready(snapshot),
            sanitized_value=_bool_text(_public_market_ready(snapshot)),
            expected="true",
        ),
        LiveOrderRealFreshPreflightRuntimeControlledCheckResult(
            name="private_read_only_check_ready",
            passed=_private_read_only_ready(snapshot),
            sanitized_value=_bool_text(_private_read_only_ready(snapshot)),
            expected="true",
        ),
        LiveOrderRealFreshPreflightRuntimeControlledCheckResult(
            name="local_static_check_ready",
            passed=_local_static_ready(snapshot),
            sanitized_value=_bool_text(_local_static_ready(snapshot)),
            expected="true",
        ),
        LiveOrderRealFreshPreflightRuntimeControlledCheckResult(
            name="final_exec_stack_ready",
            passed=_final_exec_stack_ready(snapshot),
            sanitized_value=_bool_text(_final_exec_stack_ready(snapshot)),
            expected="true",
        ),
        LiveOrderRealFreshPreflightRuntimeControlledCheckResult(
            name="post_guard_ready",
            passed=_post_guard_ready(snapshot),
            sanitized_value=_bool_text(_post_guard_ready(snapshot)),
            expected="true",
        ),
        LiveOrderRealFreshPreflightRuntimeControlledCheckResult(
            name="fresh_preflight_not_executed",
            passed=not snapshot.fresh_preflight_executed,
            sanitized_value=_bool_text(not snapshot.fresh_preflight_executed),
            expected="true",
        ),
        LiveOrderRealFreshPreflightRuntimeControlledCheckResult(
            name="post_disabled",
            passed=not _post_attempted(snapshot),
            sanitized_value=_bool_text(not _post_attempted(snapshot)),
            expected="true",
        ),
    )


def _validate_result_safety(
    result: LiveOrderRealFreshPreflightRuntimeControlledResult,
) -> None:
    if result.fresh_preflight_executed:
        raise LiveVerificationValidationError("fresh preflight must not be executed")
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


_FRESH_PREFLIGHT_RUNTIME_INPUT_BOOL_FIELDS = (
    "fresh_preflight_runtime_declared",
    "fresh_preflight_runtime_requested",
    "public_market_check_declared",
    "public_market_check_ready",
    "public_market_status_safe",
    "public_market_ticker_safe",
    "public_market_spread_check_ready",
    "public_market_age_check_ready",
    "private_read_only_check_declared",
    "private_read_only_check_ready",
    "account_assets_check_ready",
    "open_positions_check_ready",
    "active_orders_check_ready",
    "local_static_check_declared",
    "local_static_check_ready",
    "git_state_expected_clean",
    "head_origin_expected_match",
    "no_order_guard_ready",
    "post_disabled",
    "live_order_once_disabled",
    "fresh_final_separation_maintained",
    "final_exec_stack_prerequisite_checked",
    "final_exec_stack_ready",
    "final_exec_stack_prerequisite_satisfied",
    "final_exec_stack_one_shot_post_allowed",
    "post_guard_prerequisite_checked",
    "post_guard_ready",
    "post_guard_prerequisite_satisfied",
    "fresh_preflight_runtime_unknown",
    "fresh_preflight_runtime_failed",
    "fresh_preflight_runtime_unavailable",
    "fresh_preflight_runtime_timeout",
    "fresh_preflight_runtime_stale",
    "fresh_preflight_runtime_reused",
    "fresh_preflight_executed",
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

_FRESH_PREFLIGHT_RUNTIME_RESULT_BOOL_FIELDS = (
    "fresh_preflight_runtime_ready",
    "fresh_preflight_runtime_declared",
    "fresh_preflight_runtime_requested",
    "public_market_check_ready",
    "public_market_status_safe",
    "public_market_ticker_safe",
    "public_market_spread_check_ready",
    "public_market_age_check_ready",
    "private_read_only_check_ready",
    "account_assets_check_ready",
    "open_positions_check_ready",
    "active_orders_check_ready",
    "local_static_check_ready",
    "git_state_expected_clean",
    "head_origin_expected_match",
    "no_order_guard_ready",
    "post_disabled",
    "live_order_once_disabled",
    "fresh_final_separation_maintained",
    "final_exec_stack_ready",
    "final_exec_stack_prerequisite_satisfied",
    "post_guard_ready",
    "post_guard_prerequisite_satisfied",
    "fresh_preflight_runtime_unknown",
    "fresh_preflight_runtime_failed",
    "fresh_preflight_runtime_unavailable",
    "fresh_preflight_runtime_timeout",
    "fresh_preflight_runtime_stale",
    "fresh_preflight_runtime_reused",
    "fresh_preflight_executed",
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
