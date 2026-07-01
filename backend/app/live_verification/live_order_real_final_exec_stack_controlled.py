"""Step 6G final dry-run execution stack contract.

This module builds the one-shot execution stack only as an in-memory dry-run
contract. It does not call APIs, execute HTTP POST, use real transport, call
order endpoints, call live_order_once, run fresh preflight, obtain final
confirmation, update ledgers, persist attempt counters, receive actual results,
or hand off receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_final_readiness_controlled import (
    SAFE_FINAL_READINESS_LABEL,
    LiveOrderRealFinalReadinessControlledResult,
    LiveOrderRealFinalReadinessControlledStatus,
)
from app.live_verification.live_order_real_post_guard_controlled import (
    SAFE_POST_GUARD_LABEL,
    LiveOrderRealPostGuardControlledResult,
    LiveOrderRealPostGuardControlledStatus,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    SAFE_POST_RESULT_LABEL,
    SAFE_RECONCILIATION_LABEL,
    LiveOrderRealSafeReconciliationStatus,
    LiveOrderRealSanitizedPostResultResult,
    LiveOrderRealSanitizedPostResultStatus,
)

FINAL_EXEC_STACK_RECOMMENDED_NEXT_STEP = (
    "final_exec_stack_boundary_review_no_api_no_post"
)
SAFE_DRY_RUN_STACK_LABEL = "CONTROLLED_FINAL_EXEC_STACK_DRY_RUN_ONLY"
SAFE_DRY_RUN_DECISION_LABEL = "DRY_RUN_ONE_SHOT_DECISION_BLOCKED_NO_POST"
SAFE_DRY_RUN_RESULT_CATEGORY = "DRY_RUN_RESULT_ACCEPTED_SANITIZED_NO_RECEIPT"
SAFE_DRY_RUN_RECONCILIATION_PREVIEW_LABEL = (
    "DRY_RUN_RECONCILIATION_PREVIEW_SAFE_NO_RECEIPT"
)
SAFE_DRY_RUN_RECEIPT_HANDOFF_PREVIEW_LABEL = (
    "DRY_RUN_RECEIPT_HANDOFF_PREVIEW_SAFE_NOT_EXECUTED"
)
SAFE_DRY_RUN_LEDGER_ATTEMPT_PREVIEW_LABEL = (
    "DRY_RUN_LEDGER_ATTEMPT_PREVIEW_SAFE_NOT_PERSISTED"
)
UNSUPPORTED_FINAL_EXEC_STACK_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealFinalExecStackControlledStatus(str, Enum):
    FINAL_EXEC_STACK_NOT_READY = "FINAL_EXEC_STACK_NOT_READY"
    FINAL_EXEC_STACK_READY_DRY_RUN_ONLY = (
        "FINAL_EXEC_STACK_READY_DRY_RUN_ONLY"
    )
    FINAL_EXEC_STACK_BLOCKED_MISSING_FINAL_READINESS = (
        "FINAL_EXEC_STACK_BLOCKED_MISSING_FINAL_READINESS"
    )
    FINAL_EXEC_STACK_BLOCKED_ONE_SHOT_POST_ALLOWED = (
        "FINAL_EXEC_STACK_BLOCKED_ONE_SHOT_POST_ALLOWED"
    )
    FINAL_EXEC_STACK_BLOCKED_NETWORK_TRANSPORT = (
        "FINAL_EXEC_STACK_BLOCKED_NETWORK_TRANSPORT"
    )
    FINAL_EXEC_STACK_BLOCKED_REAL_TRANSPORT = (
        "FINAL_EXEC_STACK_BLOCKED_REAL_TRANSPORT"
    )
    FINAL_EXEC_STACK_BLOCKED_API_ATTEMPTED = (
        "FINAL_EXEC_STACK_BLOCKED_API_ATTEMPTED"
    )
    FINAL_EXEC_STACK_BLOCKED_POST_ATTEMPTED = (
        "FINAL_EXEC_STACK_BLOCKED_POST_ATTEMPTED"
    )
    FINAL_EXEC_STACK_BLOCKED_ORDER_ENDPOINT = (
        "FINAL_EXEC_STACK_BLOCKED_ORDER_ENDPOINT"
    )
    FINAL_EXEC_STACK_BLOCKED_LIVE_ORDER_ONCE = (
        "FINAL_EXEC_STACK_BLOCKED_LIVE_ORDER_ONCE"
    )
    FINAL_EXEC_STACK_BLOCKED_FRESH_PREFLIGHT_EXECUTED = (
        "FINAL_EXEC_STACK_BLOCKED_FRESH_PREFLIGHT_EXECUTED"
    )
    FINAL_EXEC_STACK_BLOCKED_FINAL_CONFIRMATION_EXECUTED = (
        "FINAL_EXEC_STACK_BLOCKED_FINAL_CONFIRMATION_EXECUTED"
    )
    FINAL_EXEC_STACK_BLOCKED_LEDGER_UPDATE = (
        "FINAL_EXEC_STACK_BLOCKED_LEDGER_UPDATE"
    )
    FINAL_EXEC_STACK_BLOCKED_ATTEMPT_COUNTER_PERSISTENCE = (
        "FINAL_EXEC_STACK_BLOCKED_ATTEMPT_COUNTER_PERSISTENCE"
    )
    FINAL_EXEC_STACK_BLOCKED_ACTUAL_RECEIPT = (
        "FINAL_EXEC_STACK_BLOCKED_ACTUAL_RECEIPT"
    )
    FINAL_EXEC_STACK_BLOCKED_RAW_REQUEST = (
        "FINAL_EXEC_STACK_BLOCKED_RAW_REQUEST"
    )
    FINAL_EXEC_STACK_BLOCKED_RAW_RESPONSE = (
        "FINAL_EXEC_STACK_BLOCKED_RAW_RESPONSE"
    )
    FINAL_EXEC_STACK_BLOCKED_BROKER_API_RESPONSE = (
        "FINAL_EXEC_STACK_BLOCKED_BROKER_API_RESPONSE"
    )
    FINAL_EXEC_STACK_BLOCKED_REAL_ID = "FINAL_EXEC_STACK_BLOCKED_REAL_ID"
    FINAL_EXEC_STACK_BLOCKED_VALUE_EXPOSURE = (
        "FINAL_EXEC_STACK_BLOCKED_VALUE_EXPOSURE"
    )
    FINAL_EXEC_STACK_BLOCKED_UNKNOWN = "FINAL_EXEC_STACK_BLOCKED_UNKNOWN"
    FINAL_EXEC_STACK_BLOCKED_FAILED = "FINAL_EXEC_STACK_BLOCKED_FAILED"
    FINAL_EXEC_STACK_BLOCKED_UNAVAILABLE = (
        "FINAL_EXEC_STACK_BLOCKED_UNAVAILABLE"
    )
    FINAL_EXEC_STACK_BLOCKED_TIMEOUT = "FINAL_EXEC_STACK_BLOCKED_TIMEOUT"
    FINAL_EXEC_STACK_BLOCKED_STALE = "FINAL_EXEC_STACK_BLOCKED_STALE"
    FINAL_EXEC_STACK_BLOCKED_REUSED = "FINAL_EXEC_STACK_BLOCKED_REUSED"


class LiveOrderRealFinalExecStackControlledMode(str, Enum):
    FINAL_EXEC_STACK_DRY_RUN_ONLY = "FINAL_EXEC_STACK_DRY_RUN_ONLY"


FinalExecStackControlledStatus = LiveOrderRealFinalExecStackControlledStatus
FinalExecStackControlledMode = LiveOrderRealFinalExecStackControlledMode


@dataclass(frozen=True)
class LiveOrderRealFinalExecStackControlledInput:
    final_exec_stack_mode: str = (
        FinalExecStackControlledMode.FINAL_EXEC_STACK_DRY_RUN_ONLY.value
    )
    final_exec_stack_declared: bool = True
    final_exec_stack_requested: bool = True
    safe_dry_run_stack_label: str = SAFE_DRY_RUN_STACK_LABEL
    final_readiness_prerequisite_checked: bool = True
    final_readiness_controlled_ready: bool = True
    final_readiness_prerequisite_satisfied: bool = True
    safe_final_readiness_label: str = SAFE_FINAL_READINESS_LABEL
    safe_final_readiness_status: str = (
        LiveOrderRealFinalReadinessControlledStatus
        .FINAL_READINESS_READY_NO_POST
        .value
    )
    post_guard_prerequisite_checked: bool = True
    post_guard_controlled_ready: bool = True
    post_guard_prerequisite_satisfied: bool = True
    safe_post_guard_label: str = SAFE_POST_GUARD_LABEL
    safe_post_guard_status: str = (
        LiveOrderRealPostGuardControlledStatus.POST_GUARD_READY_NO_POST.value
    )
    sanitized_result_prerequisite_checked: bool = True
    sanitized_post_result_ready: bool = True
    reconciliation_ready: bool = True
    sanitized_result_prerequisite_satisfied: bool = True
    safe_post_result_label: str = SAFE_POST_RESULT_LABEL
    safe_post_result_status: str = (
        LiveOrderRealSanitizedPostResultStatus
        .SANITIZED_RESULT_READY_NO_RECEIPT
        .value
    )
    safe_reconciliation_label: str = SAFE_RECONCILIATION_LABEL
    safe_reconciliation_status: str = (
        LiveOrderRealSafeReconciliationStatus
        .RECONCILIATION_READY_NO_RECEIPT_HANDOFF
        .value
    )
    dry_run_stack_unknown: bool = False
    dry_run_stack_failed: bool = False
    dry_run_stack_unavailable: bool = False
    dry_run_stack_timeout: bool = False
    dry_run_stack_stale: bool = False
    dry_run_stack_reused: bool = False
    dry_run_mode: bool = True
    dry_run_stack_ready_input: bool = True
    fake_transport_used: bool = True
    no_network_transport_used: bool = True
    network_transport_used: bool = False
    real_transport_used: bool = False
    raw_request_generated: bool = False
    raw_response_received: bool = False
    broker_response_received: bool = False
    api_response_received: bool = False
    dry_run_one_shot_decision_declared: bool = True
    dry_run_one_shot_decision_safe: bool = True
    dry_run_sanitized_result_ready: bool = True
    dry_run_reconciliation_preview_ready: bool = True
    dry_run_receipt_handoff_preview_ready: bool = True
    dry_run_ledger_attempt_preview_ready: bool = True
    api_call_allowed: bool = False
    api_call_executed: bool = False
    api_call_attempted: bool = False
    http_client_present: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    fresh_preflight_executed: bool = False
    final_confirmation_received: bool = False
    ledger_update_allowed: bool = False
    ledger_updated: bool = False
    ledger_update_attempted: bool = False
    attempt_counter_persistence_allowed: bool = False
    attempt_counter_persisted: bool = False
    actual_result_receipt_received: bool = False
    actual_receipt_handoff_executed: bool = False
    actual_receipt_handoff_allowed: bool = False
    one_shot_post_allowed: bool = False
    one_shot_post_readiness_blocked: bool = True
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
    raw_broker_api_response_exposed: bool = False
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty("final_exec_stack_mode", self.final_exec_stack_mode)
        _require_non_empty("safe_dry_run_stack_label", self.safe_dry_run_stack_label)
        _require_non_empty(
            "safe_final_readiness_label",
            self.safe_final_readiness_label,
        )
        _require_non_empty(
            "safe_final_readiness_status",
            self.safe_final_readiness_status,
        )
        _require_non_empty("safe_post_guard_label", self.safe_post_guard_label)
        _require_non_empty("safe_post_guard_status", self.safe_post_guard_status)
        _require_non_empty("safe_post_result_label", self.safe_post_result_label)
        _require_non_empty("safe_post_result_status", self.safe_post_result_status)
        _require_non_empty(
            "safe_reconciliation_label",
            self.safe_reconciliation_label,
        )
        _require_non_empty(
            "safe_reconciliation_status",
            self.safe_reconciliation_status,
        )
        _validate_bool_fields(self, _FINAL_EXEC_STACK_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealFinalExecStackControlledCheckResult:
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
class LiveOrderRealFinalExecStackControlledResult:
    status: LiveOrderRealFinalExecStackControlledStatus
    dry_run_stack_ready: bool
    final_exec_stack_mode: str
    final_exec_stack_declared: bool
    final_exec_stack_requested: bool
    safe_dry_run_stack_label: str
    safe_dry_run_stack_status: str
    final_readiness_prerequisite_checked: bool
    final_readiness_controlled_ready: bool
    final_readiness_prerequisite_satisfied: bool
    safe_final_readiness_label: str
    safe_final_readiness_status: str
    post_guard_prerequisite_checked: bool
    post_guard_controlled_ready: bool
    post_guard_prerequisite_satisfied: bool
    safe_post_guard_label: str
    safe_post_guard_status: str
    sanitized_result_prerequisite_checked: bool
    sanitized_post_result_ready: bool
    reconciliation_ready: bool
    sanitized_result_prerequisite_satisfied: bool
    safe_post_result_label: str
    safe_post_result_status: str
    safe_reconciliation_label: str
    safe_reconciliation_status: str
    dry_run_stack_unknown: bool
    dry_run_stack_failed: bool
    dry_run_stack_unavailable: bool
    dry_run_stack_timeout: bool
    dry_run_stack_stale: bool
    dry_run_stack_reused: bool
    dry_run_mode: bool
    fake_transport_used: bool
    no_network_transport_used: bool
    network_transport_used: bool
    real_transport_used: bool
    raw_request_generated: bool
    raw_response_received: bool
    broker_response_received: bool
    api_response_received: bool
    dry_run_one_shot_decision: str
    safe_dry_run_result_category: str
    safe_dry_run_reconciliation_preview_label: str
    safe_dry_run_receipt_handoff_preview_label: str
    safe_dry_run_ledger_attempt_preview_label: str
    dry_run_sanitized_result_ready: bool
    dry_run_reconciliation_preview_ready: bool
    dry_run_receipt_handoff_preview_ready: bool
    dry_run_ledger_attempt_preview_ready: bool
    api_call_allowed: bool
    api_call_executed: bool
    post_allowed_this_step: bool
    post_executed: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    fresh_preflight_executed: bool
    final_confirmation_received: bool
    ledger_update_allowed: bool
    ledger_updated: bool
    attempt_counter_persistence_allowed: bool
    attempt_counter_persisted: bool
    actual_result_receipt_received: bool
    actual_receipt_handoff_executed: bool
    actual_receipt_handoff_allowed: bool
    one_shot_post_allowed: bool
    one_shot_post_readiness_blocked: bool
    raw_request_stored: bool
    raw_response_stored: bool
    broker_response_exposed: bool
    api_response_exposed: bool
    real_id_exposed: bool
    ledger_state_actual_value_exposed: bool
    raw_broker_api_response_exposed: bool
    safe_to_render: bool
    safe_to_serialize: bool
    check_results: tuple[LiveOrderRealFinalExecStackControlledCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, LiveOrderRealFinalExecStackControlledStatus):
            raise LiveVerificationValidationError(
                "status must be final exec stack controlled status",
            )
        _require_non_empty("final_exec_stack_mode", self.final_exec_stack_mode)
        _require_non_empty("safe_dry_run_stack_label", self.safe_dry_run_stack_label)
        _require_non_empty("safe_dry_run_stack_status", self.safe_dry_run_stack_status)
        _require_non_empty(
            "safe_final_readiness_label",
            self.safe_final_readiness_label,
        )
        _require_non_empty(
            "safe_final_readiness_status",
            self.safe_final_readiness_status,
        )
        _require_non_empty("safe_post_guard_label", self.safe_post_guard_label)
        _require_non_empty("safe_post_guard_status", self.safe_post_guard_status)
        _require_non_empty("safe_post_result_label", self.safe_post_result_label)
        _require_non_empty("safe_post_result_status", self.safe_post_result_status)
        _require_non_empty(
            "safe_reconciliation_label",
            self.safe_reconciliation_label,
        )
        _require_non_empty(
            "safe_reconciliation_status",
            self.safe_reconciliation_status,
        )
        _require_non_empty("dry_run_one_shot_decision", self.dry_run_one_shot_decision)
        _require_non_empty(
            "safe_dry_run_result_category",
            self.safe_dry_run_result_category,
        )
        _require_non_empty(
            "safe_dry_run_reconciliation_preview_label",
            self.safe_dry_run_reconciliation_preview_label,
        )
        _require_non_empty(
            "safe_dry_run_receipt_handoff_preview_label",
            self.safe_dry_run_receipt_handoff_preview_label,
        )
        _require_non_empty(
            "safe_dry_run_ledger_attempt_preview_label",
            self.safe_dry_run_ledger_attempt_preview_label,
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(self, _FINAL_EXEC_STACK_RESULT_BOOL_FIELDS)
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_final_exec_stack_controlled(
    *,
    input_snapshot: LiveOrderRealFinalExecStackControlledInput | None = None,
    final_readiness_result: LiveOrderRealFinalReadinessControlledResult | None = None,
    post_guard_result: LiveOrderRealPostGuardControlledResult | None = None,
    sanitized_result: LiveOrderRealSanitizedPostResultResult | None = None,
) -> LiveOrderRealFinalExecStackControlledResult:
    """Build a safe dry-run execution stack without any side effects."""
    snapshot = input_snapshot or LiveOrderRealFinalExecStackControlledInput()
    if final_readiness_result is not None:
        snapshot = _merge_final_readiness_result(snapshot, final_readiness_result)
    if post_guard_result is not None:
        snapshot = _merge_post_guard_result(snapshot, post_guard_result)
    if sanitized_result is not None:
        snapshot = _merge_sanitized_result(snapshot, sanitized_result)

    status, primary_reasons = _status_from_input(snapshot)
    ready = status is FinalExecStackControlledStatus.FINAL_EXEC_STACK_READY_DRY_RUN_ONLY
    safe_mode = (
        snapshot.final_exec_stack_mode
        if snapshot.final_exec_stack_mode
        == FinalExecStackControlledMode.FINAL_EXEC_STACK_DRY_RUN_ONLY.value
        else UNSUPPORTED_FINAL_EXEC_STACK_LABEL
    )
    safe_stack_label = (
        snapshot.safe_dry_run_stack_label
        if snapshot.safe_dry_run_stack_label == SAFE_DRY_RUN_STACK_LABEL
        else UNSUPPORTED_FINAL_EXEC_STACK_LABEL
    )
    safe_final_readiness_label = (
        snapshot.safe_final_readiness_label
        if snapshot.safe_final_readiness_label == SAFE_FINAL_READINESS_LABEL
        else UNSUPPORTED_FINAL_EXEC_STACK_LABEL
    )
    safe_post_guard_label = (
        snapshot.safe_post_guard_label
        if snapshot.safe_post_guard_label == SAFE_POST_GUARD_LABEL
        else UNSUPPORTED_FINAL_EXEC_STACK_LABEL
    )
    safe_post_result_label = (
        snapshot.safe_post_result_label
        if snapshot.safe_post_result_label == SAFE_POST_RESULT_LABEL
        else UNSUPPORTED_FINAL_EXEC_STACK_LABEL
    )
    safe_reconciliation_label = (
        snapshot.safe_reconciliation_label
        if snapshot.safe_reconciliation_label == SAFE_RECONCILIATION_LABEL
        else UNSUPPORTED_FINAL_EXEC_STACK_LABEL
    )
    blocked_reasons = _blocked_reasons(
        snapshot=snapshot,
        primary_reasons=primary_reasons,
    )

    return LiveOrderRealFinalExecStackControlledResult(
        status=status,
        dry_run_stack_ready=ready,
        final_exec_stack_mode=safe_mode,
        final_exec_stack_declared=snapshot.final_exec_stack_declared,
        final_exec_stack_requested=snapshot.final_exec_stack_requested,
        safe_dry_run_stack_label=safe_stack_label,
        safe_dry_run_stack_status=status.value,
        final_readiness_prerequisite_checked=(
            snapshot.final_readiness_prerequisite_checked
        ),
        final_readiness_controlled_ready=snapshot.final_readiness_controlled_ready,
        final_readiness_prerequisite_satisfied=(
            _final_readiness_prerequisite_satisfied(snapshot)
        ),
        safe_final_readiness_label=safe_final_readiness_label,
        safe_final_readiness_status=snapshot.safe_final_readiness_status,
        post_guard_prerequisite_checked=snapshot.post_guard_prerequisite_checked,
        post_guard_controlled_ready=snapshot.post_guard_controlled_ready,
        post_guard_prerequisite_satisfied=_post_guard_prerequisite_satisfied(
            snapshot,
        ),
        safe_post_guard_label=safe_post_guard_label,
        safe_post_guard_status=snapshot.safe_post_guard_status,
        sanitized_result_prerequisite_checked=(
            snapshot.sanitized_result_prerequisite_checked
        ),
        sanitized_post_result_ready=snapshot.sanitized_post_result_ready,
        reconciliation_ready=snapshot.reconciliation_ready,
        sanitized_result_prerequisite_satisfied=(
            _sanitized_result_prerequisite_satisfied(snapshot)
        ),
        safe_post_result_label=safe_post_result_label,
        safe_post_result_status=snapshot.safe_post_result_status,
        safe_reconciliation_label=safe_reconciliation_label,
        safe_reconciliation_status=snapshot.safe_reconciliation_status,
        dry_run_stack_unknown=snapshot.dry_run_stack_unknown,
        dry_run_stack_failed=snapshot.dry_run_stack_failed,
        dry_run_stack_unavailable=snapshot.dry_run_stack_unavailable,
        dry_run_stack_timeout=snapshot.dry_run_stack_timeout,
        dry_run_stack_stale=snapshot.dry_run_stack_stale,
        dry_run_stack_reused=snapshot.dry_run_stack_reused,
        dry_run_mode=snapshot.dry_run_mode,
        fake_transport_used=snapshot.fake_transport_used,
        no_network_transport_used=snapshot.no_network_transport_used,
        network_transport_used=False,
        real_transport_used=False,
        raw_request_generated=False,
        raw_response_received=False,
        broker_response_received=False,
        api_response_received=False,
        dry_run_one_shot_decision=SAFE_DRY_RUN_DECISION_LABEL,
        safe_dry_run_result_category=SAFE_DRY_RUN_RESULT_CATEGORY,
        safe_dry_run_reconciliation_preview_label=(
            SAFE_DRY_RUN_RECONCILIATION_PREVIEW_LABEL
        ),
        safe_dry_run_receipt_handoff_preview_label=(
            SAFE_DRY_RUN_RECEIPT_HANDOFF_PREVIEW_LABEL
        ),
        safe_dry_run_ledger_attempt_preview_label=(
            SAFE_DRY_RUN_LEDGER_ATTEMPT_PREVIEW_LABEL
        ),
        dry_run_sanitized_result_ready=snapshot.dry_run_sanitized_result_ready,
        dry_run_reconciliation_preview_ready=(
            snapshot.dry_run_reconciliation_preview_ready
        ),
        dry_run_receipt_handoff_preview_ready=(
            snapshot.dry_run_receipt_handoff_preview_ready
        ),
        dry_run_ledger_attempt_preview_ready=(
            snapshot.dry_run_ledger_attempt_preview_ready
        ),
        api_call_allowed=False,
        api_call_executed=False,
        post_allowed_this_step=False,
        post_executed=False,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        fresh_preflight_executed=False,
        final_confirmation_received=False,
        ledger_update_allowed=False,
        ledger_updated=False,
        attempt_counter_persistence_allowed=False,
        attempt_counter_persisted=False,
        actual_result_receipt_received=False,
        actual_receipt_handoff_executed=False,
        actual_receipt_handoff_allowed=False,
        one_shot_post_allowed=False,
        one_shot_post_readiness_blocked=True,
        raw_request_stored=False,
        raw_response_stored=False,
        broker_response_exposed=False,
        api_response_exposed=False,
        real_id_exposed=False,
        ledger_state_actual_value_exposed=False,
        raw_broker_api_response_exposed=False,
        safe_to_render=snapshot.safe_to_render,
        safe_to_serialize=snapshot.safe_to_serialize,
        check_results=_build_check_results(
            snapshot=snapshot,
            status=status,
            ready=ready,
            safe_stack_label=safe_stack_label,
        ),
        blocked_reasons=blocked_reasons,
        recommended_next_step=FINAL_EXEC_STACK_RECOMMENDED_NEXT_STEP,
    )


def render_live_order_real_final_exec_stack_controlled_markdown(
    result: LiveOrderRealFinalExecStackControlledResult,
) -> str:
    """Render a safe dry-run execution stack summary only."""
    lines = [
        "# Step 6G Final Exec Stack Controlled Contract",
        "",
        "This is a dry-run only one-shot execution stack contract.",
        "It contains safe labels, statuses, booleans, preview labels, and",
        "blocked reason labels.",
        "It does not execute API calls.",
        "It does not execute HTTP POST.",
        "It does not call order endpoints.",
        "It does not call live_order_once.",
        "It does not use real transport or network I/O.",
        "It does not run fresh preflight or obtain final confirmation.",
        "It does not update ledgers or persist attempt counters.",
        "It does not receive actual results or hand off receipts.",
        "It does not expose raw requests, raw responses, broker/API responses, IDs,",
        "credential values, signature values, headers values, confirmation phrases,",
        "ledger state values, or approval command values.",
        "Dry-run stack ready does not allow POST.",
        "One-shot POST allowed remains false.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- dry_run_stack_ready: {_bool_text(result.dry_run_stack_ready)}",
        f"- final_exec_stack_mode: {result.final_exec_stack_mode}",
        f"- safe_dry_run_stack_label: {result.safe_dry_run_stack_label}",
        f"- safe_dry_run_stack_status: {result.safe_dry_run_stack_status}",
        "",
        "## Dry-Run Path",
        f"- dry_run_mode: {_bool_text(result.dry_run_mode)}",
        f"- fake_transport_used: {_bool_text(result.fake_transport_used)}",
        f"- no_network_transport_used: {_bool_text(result.no_network_transport_used)}",
        f"- network_transport_used: {_bool_text(result.network_transport_used)}",
        f"- real_transport_used: {_bool_text(result.real_transport_used)}",
        f"- dry_run_one_shot_decision: {result.dry_run_one_shot_decision}",
        f"- safe_dry_run_result_category: {result.safe_dry_run_result_category}",
        (
            "- safe_dry_run_reconciliation_preview_label: "
            f"{result.safe_dry_run_reconciliation_preview_label}"
        ),
        (
            "- safe_dry_run_receipt_handoff_preview_label: "
            f"{result.safe_dry_run_receipt_handoff_preview_label}"
        ),
        (
            "- safe_dry_run_ledger_attempt_preview_label: "
            f"{result.safe_dry_run_ledger_attempt_preview_label}"
        ),
        "",
        "## Non-Execution",
        f"- api_call_executed: {_bool_text(result.api_call_executed)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- fresh_preflight_executed: {_bool_text(result.fresh_preflight_executed)}",
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
            "- actual_result_receipt_received: "
            f"{_bool_text(result.actual_result_receipt_received)}"
        ),
        (
            "- actual_receipt_handoff_executed: "
            f"{_bool_text(result.actual_receipt_handoff_executed)}"
        ),
        f"- one_shot_post_allowed: {_bool_text(result.one_shot_post_allowed)}",
        (
            "- one_shot_post_readiness_blocked: "
            f"{_bool_text(result.one_shot_post_readiness_blocked)}"
        ),
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines)


def _merge_final_readiness_result(
    snapshot: LiveOrderRealFinalExecStackControlledInput,
    final_readiness_result: LiveOrderRealFinalReadinessControlledResult,
) -> LiveOrderRealFinalExecStackControlledInput:
    return replace(
        snapshot,
        final_readiness_prerequisite_checked=True,
        final_readiness_controlled_ready=(
            final_readiness_result.final_readiness_controlled_ready
        ),
        final_readiness_prerequisite_satisfied=(
            final_readiness_result.final_readiness_controlled_ready
            and final_readiness_result.status
            is (
                LiveOrderRealFinalReadinessControlledStatus
                .FINAL_READINESS_READY_NO_POST
            )
        ),
        safe_final_readiness_label=(
            final_readiness_result.safe_final_readiness_label
        ),
        safe_final_readiness_status=(
            final_readiness_result.safe_final_readiness_status
        ),
        post_guard_prerequisite_checked=(
            final_readiness_result.post_guard_prerequisite_checked
        ),
        post_guard_controlled_ready=(
            final_readiness_result.post_guard_controlled_ready
        ),
        post_guard_prerequisite_satisfied=(
            final_readiness_result.post_guard_prerequisite_satisfied
        ),
        safe_post_guard_label=final_readiness_result.safe_post_guard_label,
        safe_post_guard_status=final_readiness_result.safe_post_guard_status,
        sanitized_result_prerequisite_checked=(
            final_readiness_result.sanitized_result_prerequisite_checked
        ),
        sanitized_post_result_ready=(
            final_readiness_result.sanitized_post_result_ready
        ),
        reconciliation_ready=final_readiness_result.reconciliation_ready,
        sanitized_result_prerequisite_satisfied=(
            final_readiness_result.sanitized_result_prerequisite_satisfied
        ),
        safe_post_result_label=final_readiness_result.safe_post_result_label,
        safe_post_result_status=final_readiness_result.safe_post_result_status,
        safe_reconciliation_label=final_readiness_result.safe_reconciliation_label,
        safe_reconciliation_status=(
            final_readiness_result.safe_reconciliation_status
        ),
        api_call_allowed=(
            snapshot.api_call_allowed or final_readiness_result.api_call_allowed
        ),
        api_call_attempted=(
            snapshot.api_call_attempted or final_readiness_result.api_call_attempted
        ),
        http_client_present=(
            snapshot.http_client_present or final_readiness_result.http_client_present
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step
            or final_readiness_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or final_readiness_result.post_executed,
        http_post_executed=(
            snapshot.http_post_executed or final_readiness_result.http_post_executed
        ),
        order_endpoint_called=(
            snapshot.order_endpoint_called
            or final_readiness_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called
            or final_readiness_result.live_order_once_called
        ),
        fresh_preflight_executed=(
            snapshot.fresh_preflight_executed
            or final_readiness_result.fresh_preflight_executed
        ),
        final_confirmation_received=(
            snapshot.final_confirmation_received
            or final_readiness_result.final_confirmation_received
        ),
        ledger_update_allowed=(
            snapshot.ledger_update_allowed
            or final_readiness_result.ledger_update_allowed
        ),
        ledger_update_attempted=(
            snapshot.ledger_update_attempted
            or final_readiness_result.ledger_update_attempted
        ),
        attempt_counter_persistence_allowed=(
            snapshot.attempt_counter_persistence_allowed
            or final_readiness_result.attempt_counter_persistence_allowed
        ),
        attempt_counter_persisted=(
            snapshot.attempt_counter_persisted
            or final_readiness_result.attempt_counter_persisted
        ),
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or final_readiness_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or final_readiness_result.actual_receipt_handoff_executed
        ),
        actual_receipt_handoff_allowed=(
            snapshot.actual_receipt_handoff_allowed
            or final_readiness_result.actual_receipt_handoff_allowed
        ),
        one_shot_post_allowed=(
            snapshot.one_shot_post_allowed
            or final_readiness_result.one_shot_post_allowed
        ),
        one_shot_post_readiness_blocked=(
            snapshot.one_shot_post_readiness_blocked
            and final_readiness_result.one_shot_post_readiness_blocked
        ),
        unsafe_exposure_attempted=(
            snapshot.unsafe_exposure_attempted
            or final_readiness_result.unsafe_exposure_attempted
        ),
        credential_value_exposure_attempted=(
            snapshot.credential_value_exposure_attempted
            or final_readiness_result.credential_value_exposure_attempted
        ),
        signature_value_exposure_attempted=(
            snapshot.signature_value_exposure_attempted
            or final_readiness_result.signature_value_exposure_attempted
        ),
        headers_value_exposure_attempted=(
            snapshot.headers_value_exposure_attempted
            or final_readiness_result.headers_value_exposure_attempted
        ),
        raw_request_exposure_attempted=(
            snapshot.raw_request_exposure_attempted
            or final_readiness_result.raw_request_exposure_attempted
        ),
        raw_response_exposure_attempted=(
            snapshot.raw_response_exposure_attempted
            or final_readiness_result.raw_response_exposure_attempted
        ),
        request_body_exposure_attempted=(
            snapshot.request_body_exposure_attempted
            or final_readiness_result.request_body_exposure_attempted
        ),
        response_body_exposure_attempted=(
            snapshot.response_body_exposure_attempted
            or final_readiness_result.response_body_exposure_attempted
        ),
        broker_response_exposure_attempted=(
            snapshot.broker_response_exposure_attempted
            or final_readiness_result.broker_response_exposure_attempted
        ),
        api_response_exposure_attempted=(
            snapshot.api_response_exposure_attempted
            or final_readiness_result.api_response_exposure_attempted
        ),
        endpoint_actual_value_exposure_attempted=(
            snapshot.endpoint_actual_value_exposure_attempted
            or final_readiness_result.endpoint_actual_value_exposure_attempted
        ),
        account_id_exposure_attempted=(
            snapshot.account_id_exposure_attempted
            or final_readiness_result.account_id_exposure_attempted
        ),
        order_id_exposure_attempted=(
            snapshot.order_id_exposure_attempted
            or final_readiness_result.order_id_exposure_attempted
        ),
        transaction_id_exposure_attempted=(
            snapshot.transaction_id_exposure_attempted
            or final_readiness_result.transaction_id_exposure_attempted
        ),
        position_id_exposure_attempted=(
            snapshot.position_id_exposure_attempted
            or final_readiness_result.position_id_exposure_attempted
        ),
        trade_id_exposure_attempted=(
            snapshot.trade_id_exposure_attempted
            or final_readiness_result.trade_id_exposure_attempted
        ),
        real_id_exposure_attempted=(
            snapshot.real_id_exposure_attempted
            or final_readiness_result.real_id_exposure_attempted
        ),
        confirmation_phrase_exposure_attempted=(
            snapshot.confirmation_phrase_exposure_attempted
            or final_readiness_result.confirmation_phrase_exposure_attempted
        ),
        ledger_state_exposure_attempted=(
            snapshot.ledger_state_exposure_attempted
            or final_readiness_result.ledger_state_exposure_attempted
        ),
        approval_command_exposure_attempted=(
            snapshot.approval_command_exposure_attempted
            or final_readiness_result.approval_command_exposure_attempted
        ),
        raw_request_stored=(
            snapshot.raw_request_stored or final_readiness_result.raw_request_stored
        ),
        raw_response_stored=(
            snapshot.raw_response_stored or final_readiness_result.raw_response_stored
        ),
        broker_response_exposed=(
            snapshot.broker_response_exposed
            or final_readiness_result.broker_response_exposed
        ),
        api_response_exposed=(
            snapshot.api_response_exposed
            or final_readiness_result.api_response_exposed
        ),
        real_id_exposed=snapshot.real_id_exposed or final_readiness_result.real_id_exposed,
        safe_to_render=snapshot.safe_to_render and final_readiness_result.safe_to_render,
        safe_to_serialize=(
            snapshot.safe_to_serialize and final_readiness_result.safe_to_serialize
        ),
    )


def _merge_post_guard_result(
    snapshot: LiveOrderRealFinalExecStackControlledInput,
    post_guard_result: LiveOrderRealPostGuardControlledResult,
) -> LiveOrderRealFinalExecStackControlledInput:
    return replace(
        snapshot,
        post_guard_prerequisite_checked=True,
        post_guard_controlled_ready=post_guard_result.post_guard_ready,
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
        api_call_attempted=(
            snapshot.api_call_attempted or post_guard_result.api_call_attempted
        ),
        http_client_present=(
            snapshot.http_client_present or post_guard_result.http_client_present
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
        one_shot_post_allowed=(
            snapshot.one_shot_post_allowed or post_guard_result.post_allowed_this_step
        ),
    )


def _merge_sanitized_result(
    snapshot: LiveOrderRealFinalExecStackControlledInput,
    sanitized_result: LiveOrderRealSanitizedPostResultResult,
) -> LiveOrderRealFinalExecStackControlledInput:
    return replace(
        snapshot,
        sanitized_result_prerequisite_checked=True,
        sanitized_post_result_ready=sanitized_result.sanitized_post_result_ready,
        reconciliation_ready=sanitized_result.reconciliation_ready,
        sanitized_result_prerequisite_satisfied=(
            sanitized_result.sanitized_post_result_ready
            and sanitized_result.reconciliation_ready
            and sanitized_result.status
            is (
                LiveOrderRealSanitizedPostResultStatus
                .SANITIZED_RESULT_READY_NO_RECEIPT
            )
        ),
        safe_post_result_label=sanitized_result.safe_post_result_label,
        safe_post_result_status=sanitized_result.safe_post_result_status,
        safe_reconciliation_label=sanitized_result.safe_reconciliation_label,
        safe_reconciliation_status=sanitized_result.safe_reconciliation_status,
        api_call_allowed=(
            snapshot.api_call_allowed or sanitized_result.api_call_allowed
        ),
        api_call_attempted=(
            snapshot.api_call_attempted or sanitized_result.api_call_attempted
        ),
        http_client_present=(
            snapshot.http_client_present or sanitized_result.http_client_present
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step
            or sanitized_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or sanitized_result.post_executed,
        http_post_executed=(
            snapshot.http_post_executed or sanitized_result.http_post_executed
        ),
        order_endpoint_called=(
            snapshot.order_endpoint_called or sanitized_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called or sanitized_result.live_order_once_called
        ),
        ledger_update_allowed=(
            snapshot.ledger_update_allowed or sanitized_result.ledger_update_allowed
        ),
        ledger_update_attempted=(
            snapshot.ledger_update_attempted or sanitized_result.ledger_update_attempted
        ),
        attempt_counter_persisted=(
            snapshot.attempt_counter_persisted
            or sanitized_result.attempt_counter_persisted
        ),
        fresh_preflight_executed=(
            snapshot.fresh_preflight_executed
            or sanitized_result.fresh_preflight_executed
        ),
        final_confirmation_received=(
            snapshot.final_confirmation_received
            or sanitized_result.final_confirmation_received
        ),
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or sanitized_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or sanitized_result.actual_receipt_handoff_executed
        ),
        actual_receipt_handoff_allowed=(
            snapshot.actual_receipt_handoff_allowed
            or sanitized_result.actual_receipt_handoff_allowed
        ),
        unsafe_exposure_attempted=(
            snapshot.unsafe_exposure_attempted
            or sanitized_result.unsafe_exposure_attempted
        ),
        credential_value_exposure_attempted=(
            snapshot.credential_value_exposure_attempted
            or sanitized_result.credential_value_exposure_attempted
        ),
        signature_value_exposure_attempted=(
            snapshot.signature_value_exposure_attempted
            or sanitized_result.signature_value_exposure_attempted
        ),
        headers_value_exposure_attempted=(
            snapshot.headers_value_exposure_attempted
            or sanitized_result.headers_value_exposure_attempted
        ),
        raw_request_exposure_attempted=(
            snapshot.raw_request_exposure_attempted
            or sanitized_result.raw_request_exposure_attempted
        ),
        raw_response_exposure_attempted=(
            snapshot.raw_response_exposure_attempted
            or sanitized_result.raw_response_exposure_attempted
        ),
        request_body_exposure_attempted=(
            snapshot.request_body_exposure_attempted
            or sanitized_result.request_body_exposure_attempted
        ),
        response_body_exposure_attempted=(
            snapshot.response_body_exposure_attempted
            or sanitized_result.response_body_exposure_attempted
        ),
        broker_response_exposure_attempted=(
            snapshot.broker_response_exposure_attempted
            or sanitized_result.broker_response_exposure_attempted
        ),
        api_response_exposure_attempted=(
            snapshot.api_response_exposure_attempted
            or sanitized_result.api_response_exposure_attempted
        ),
        endpoint_actual_value_exposure_attempted=(
            snapshot.endpoint_actual_value_exposure_attempted
            or sanitized_result.endpoint_actual_value_exposure_attempted
        ),
        account_id_exposure_attempted=(
            snapshot.account_id_exposure_attempted
            or sanitized_result.account_id_exposure_attempted
        ),
        order_id_exposure_attempted=(
            snapshot.order_id_exposure_attempted
            or sanitized_result.order_id_exposure_attempted
        ),
        transaction_id_exposure_attempted=(
            snapshot.transaction_id_exposure_attempted
            or sanitized_result.transaction_id_exposure_attempted
        ),
        position_id_exposure_attempted=(
            snapshot.position_id_exposure_attempted
            or sanitized_result.position_id_exposure_attempted
        ),
        trade_id_exposure_attempted=(
            snapshot.trade_id_exposure_attempted
            or sanitized_result.trade_id_exposure_attempted
        ),
        real_id_exposure_attempted=(
            snapshot.real_id_exposure_attempted
            or sanitized_result.real_id_exposure_attempted
        ),
        confirmation_phrase_exposure_attempted=(
            snapshot.confirmation_phrase_exposure_attempted
            or sanitized_result.confirmation_phrase_exposure_attempted
        ),
        ledger_state_exposure_attempted=(
            snapshot.ledger_state_exposure_attempted
            or sanitized_result.ledger_state_exposure_attempted
        ),
        raw_request_stored=(
            snapshot.raw_request_stored or sanitized_result.raw_request_stored
        ),
        raw_response_stored=(
            snapshot.raw_response_stored or sanitized_result.raw_response_stored
        ),
        broker_response_exposed=(
            snapshot.broker_response_exposed
            or sanitized_result.broker_response_exposed
        ),
        api_response_exposed=(
            snapshot.api_response_exposed or sanitized_result.api_response_exposed
        ),
        real_id_exposed=snapshot.real_id_exposed or sanitized_result.real_id_exposed,
        safe_to_render=snapshot.safe_to_render and sanitized_result.safe_to_render,
        safe_to_serialize=(
            snapshot.safe_to_serialize and sanitized_result.safe_to_serialize
        ),
    )


def _status_from_input(
    snapshot: LiveOrderRealFinalExecStackControlledInput,
) -> tuple[LiveOrderRealFinalExecStackControlledStatus, tuple[str, ...]]:
    if (
        snapshot.final_exec_stack_mode
        != FinalExecStackControlledMode.FINAL_EXEC_STACK_DRY_RUN_ONLY.value
    ):
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_UNKNOWN, (
            "unsupported_final_exec_stack_mode",
        )
    if (
        not snapshot.final_exec_stack_declared
        or not snapshot.final_exec_stack_requested
    ):
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_NOT_READY, (
            "final_exec_stack_not_declared_or_requested",
        )
    if not _final_readiness_prerequisite_satisfied(snapshot):
        return (
            FinalExecStackControlledStatus
            .FINAL_EXEC_STACK_BLOCKED_MISSING_FINAL_READINESS,
            ("final_readiness_prerequisite_missing",),
        )
    if not _post_guard_prerequisite_satisfied(snapshot):
        return (
            FinalExecStackControlledStatus
            .FINAL_EXEC_STACK_BLOCKED_MISSING_FINAL_READINESS,
            ("post_guard_prerequisite_missing",),
        )
    if not _sanitized_result_prerequisite_satisfied(snapshot):
        return (
            FinalExecStackControlledStatus
            .FINAL_EXEC_STACK_BLOCKED_MISSING_FINAL_READINESS,
            ("sanitized_result_prerequisite_missing",),
        )
    if snapshot.dry_run_stack_unknown:
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_UNKNOWN, (
            "dry_run_stack_unknown",
        )
    if snapshot.dry_run_stack_failed:
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_FAILED, (
            "dry_run_stack_failed",
        )
    if snapshot.dry_run_stack_unavailable:
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_UNAVAILABLE, (
            "dry_run_stack_unavailable",
        )
    if snapshot.dry_run_stack_timeout:
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_TIMEOUT, (
            "dry_run_stack_timeout",
        )
    if snapshot.dry_run_stack_stale:
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_STALE, (
            "dry_run_stack_stale",
        )
    if snapshot.dry_run_stack_reused:
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_REUSED, (
            "dry_run_stack_reused",
        )
    if snapshot.one_shot_post_allowed or not snapshot.one_shot_post_readiness_blocked:
        return (
            FinalExecStackControlledStatus
            .FINAL_EXEC_STACK_BLOCKED_ONE_SHOT_POST_ALLOWED,
            ("one_shot_post_allowed_or_not_blocked",),
        )
    if snapshot.network_transport_used or not snapshot.no_network_transport_used:
        return (
            FinalExecStackControlledStatus
            .FINAL_EXEC_STACK_BLOCKED_NETWORK_TRANSPORT,
            ("network_transport_attempted_or_not_blocked",),
        )
    if snapshot.real_transport_used:
        return (
            FinalExecStackControlledStatus
            .FINAL_EXEC_STACK_BLOCKED_REAL_TRANSPORT,
            ("real_transport_attempted",),
        )
    if (
        snapshot.api_call_allowed
        or snapshot.api_call_executed
        or snapshot.api_call_attempted
        or snapshot.http_client_present
    ):
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_API_ATTEMPTED, (
            "api_attempted_or_allowed",
        )
    if (
        snapshot.post_allowed_this_step
        or snapshot.post_executed
        or snapshot.http_post_executed
    ):
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_POST_ATTEMPTED, (
            "post_attempted_or_allowed",
        )
    if snapshot.order_endpoint_called:
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_ORDER_ENDPOINT, (
            "order_endpoint_called",
        )
    if snapshot.live_order_once_called:
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_LIVE_ORDER_ONCE, (
            "live_order_once_called",
        )
    if snapshot.fresh_preflight_executed:
        return (
            FinalExecStackControlledStatus
            .FINAL_EXEC_STACK_BLOCKED_FRESH_PREFLIGHT_EXECUTED,
            ("fresh_preflight_executed_in_dry_run_stack",),
        )
    if snapshot.final_confirmation_received:
        return (
            FinalExecStackControlledStatus
            .FINAL_EXEC_STACK_BLOCKED_FINAL_CONFIRMATION_EXECUTED,
            ("final_confirmation_received_in_dry_run_stack",),
        )
    if (
        snapshot.ledger_update_allowed
        or snapshot.ledger_updated
        or snapshot.ledger_update_attempted
    ):
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_LEDGER_UPDATE, (
            "ledger_update_attempted_or_allowed",
        )
    if (
        snapshot.attempt_counter_persistence_allowed
        or snapshot.attempt_counter_persisted
    ):
        return (
            FinalExecStackControlledStatus
            .FINAL_EXEC_STACK_BLOCKED_ATTEMPT_COUNTER_PERSISTENCE,
            ("attempt_counter_persistence_attempted_or_allowed",),
        )
    if (
        snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
        or snapshot.actual_receipt_handoff_allowed
    ):
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_ACTUAL_RECEIPT, (
            "actual_receipt_or_handoff_attempted",
        )
    if snapshot.raw_request_generated or snapshot.raw_request_exposure_attempted:
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_RAW_REQUEST, (
            "raw_request_generated_or_exposed",
        )
    if snapshot.raw_response_received or snapshot.raw_response_exposure_attempted:
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_RAW_RESPONSE, (
            "raw_response_received_or_exposed",
        )
    if (
        snapshot.broker_response_received
        or snapshot.api_response_received
        or snapshot.broker_response_exposure_attempted
        or snapshot.api_response_exposure_attempted
        or snapshot.broker_response_exposed
        or snapshot.api_response_exposed
        or snapshot.raw_broker_api_response_exposed
    ):
        return (
            FinalExecStackControlledStatus
            .FINAL_EXEC_STACK_BLOCKED_BROKER_API_RESPONSE,
            ("broker_or_api_response_received_or_exposed",),
        )
    if _identifier_exposure_attempted(snapshot):
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_BLOCKED_REAL_ID, (
            "identifier_exposure_attempted",
        )
    if _unsafe_exposure_attempted(snapshot):
        return (
            FinalExecStackControlledStatus
            .FINAL_EXEC_STACK_BLOCKED_VALUE_EXPOSURE,
            ("unsafe_value_exposure_attempted",),
        )
    if not _dry_run_contract_complete(snapshot):
        return FinalExecStackControlledStatus.FINAL_EXEC_STACK_NOT_READY, (
            "dry_run_stack_contract_missing",
        )
    return FinalExecStackControlledStatus.FINAL_EXEC_STACK_READY_DRY_RUN_ONLY, ()


def _blocked_reasons(
    *,
    snapshot: LiveOrderRealFinalExecStackControlledInput,
    primary_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons = list(primary_reasons)
    if snapshot.safe_dry_run_stack_label != SAFE_DRY_RUN_STACK_LABEL:
        reasons.append("safe_dry_run_stack_label_invalid")
    if not snapshot.final_readiness_prerequisite_checked:
        reasons.append("final_readiness_prerequisite_not_checked")
    if not snapshot.final_readiness_controlled_ready:
        reasons.append("final_readiness_controlled_not_ready")
    if snapshot.safe_final_readiness_label != SAFE_FINAL_READINESS_LABEL:
        reasons.append("safe_final_readiness_label_invalid")
    if snapshot.safe_final_readiness_status != _ready_final_readiness_status():
        reasons.append("safe_final_readiness_status_not_ready")
    if not snapshot.post_guard_prerequisite_checked:
        reasons.append("post_guard_prerequisite_not_checked")
    if not snapshot.post_guard_controlled_ready:
        reasons.append("post_guard_controlled_not_ready")
    if snapshot.safe_post_guard_label != SAFE_POST_GUARD_LABEL:
        reasons.append("safe_post_guard_label_invalid")
    if snapshot.safe_post_guard_status != _ready_post_guard_status():
        reasons.append("safe_post_guard_status_not_ready")
    if not snapshot.sanitized_result_prerequisite_checked:
        reasons.append("sanitized_result_prerequisite_not_checked")
    if not snapshot.sanitized_post_result_ready:
        reasons.append("sanitized_post_result_not_ready")
    if not snapshot.reconciliation_ready:
        reasons.append("reconciliation_not_ready")
    if snapshot.safe_post_result_label != SAFE_POST_RESULT_LABEL:
        reasons.append("safe_post_result_label_invalid")
    if snapshot.safe_post_result_status != _ready_sanitized_result_status():
        reasons.append("safe_post_result_status_not_ready")
    if snapshot.safe_reconciliation_label != SAFE_RECONCILIATION_LABEL:
        reasons.append("safe_reconciliation_label_invalid")
    if snapshot.safe_reconciliation_status != _ready_reconciliation_status():
        reasons.append("safe_reconciliation_status_not_ready")
    if not snapshot.dry_run_mode:
        reasons.append("dry_run_mode_false")
    if not snapshot.dry_run_stack_ready_input:
        reasons.append("dry_run_stack_ready_input_false")
    if not snapshot.fake_transport_used:
        reasons.append("fake_transport_not_used")
    if not snapshot.no_network_transport_used:
        reasons.append("no_network_transport_not_used")
    if not snapshot.dry_run_one_shot_decision_declared:
        reasons.append("dry_run_one_shot_decision_not_declared")
    if not snapshot.dry_run_one_shot_decision_safe:
        reasons.append("dry_run_one_shot_decision_not_safe")
    if not snapshot.dry_run_sanitized_result_ready:
        reasons.append("dry_run_sanitized_result_not_ready")
    if not snapshot.dry_run_reconciliation_preview_ready:
        reasons.append("dry_run_reconciliation_preview_not_ready")
    if not snapshot.dry_run_receipt_handoff_preview_ready:
        reasons.append("dry_run_receipt_handoff_preview_not_ready")
    if not snapshot.dry_run_ledger_attempt_preview_ready:
        reasons.append("dry_run_ledger_attempt_preview_not_ready")
    if snapshot.credential_value_exposure_attempted:
        reasons.append("credential_value_exposure_attempted")
    if snapshot.signature_value_exposure_attempted:
        reasons.append("signature_value_exposure_attempted")
    if snapshot.headers_value_exposure_attempted:
        reasons.append("headers_value_exposure_attempted")
    if snapshot.request_body_exposure_attempted:
        reasons.append("request_body_exposure_attempted")
    if snapshot.response_body_exposure_attempted:
        reasons.append("response_body_exposure_attempted")
    if snapshot.endpoint_actual_value_exposure_attempted:
        reasons.append("endpoint_actual_value_exposure_attempted")
    if snapshot.confirmation_phrase_exposure_attempted:
        reasons.append("confirmation_phrase_exposure_attempted")
    if snapshot.ledger_state_exposure_attempted:
        reasons.append("ledger_state_exposure_attempted")
    if snapshot.approval_command_exposure_attempted:
        reasons.append("approval_command_exposure_attempted")
    if not snapshot.safe_to_render:
        reasons.append("render_not_safe")
    if not snapshot.safe_to_serialize:
        reasons.append("serialize_not_safe")
    return _dedupe(reasons)


def _build_check_results(
    *,
    snapshot: LiveOrderRealFinalExecStackControlledInput,
    status: LiveOrderRealFinalExecStackControlledStatus,
    ready: bool,
    safe_stack_label: str,
) -> tuple[LiveOrderRealFinalExecStackControlledCheckResult, ...]:
    return (
        LiveOrderRealFinalExecStackControlledCheckResult(
            name="final exec stack mode",
            passed=(
                snapshot.final_exec_stack_mode
                == FinalExecStackControlledMode.FINAL_EXEC_STACK_DRY_RUN_ONLY.value
            ),
            sanitized_value=(
                snapshot.final_exec_stack_mode
                if snapshot.final_exec_stack_mode
                == FinalExecStackControlledMode.FINAL_EXEC_STACK_DRY_RUN_ONLY.value
                else UNSUPPORTED_FINAL_EXEC_STACK_LABEL
            ),
            expected="dry-run only final exec stack",
        ),
        LiveOrderRealFinalExecStackControlledCheckResult(
            name="safe dry-run stack label",
            passed=safe_stack_label == SAFE_DRY_RUN_STACK_LABEL,
            sanitized_value=safe_stack_label,
            expected="fixed safe dry-run stack label",
        ),
        LiveOrderRealFinalExecStackControlledCheckResult(
            name="safe prerequisites ready",
            passed=(
                _final_readiness_prerequisite_satisfied(snapshot)
                and _post_guard_prerequisite_satisfied(snapshot)
                and _sanitized_result_prerequisite_satisfied(snapshot)
            ),
            sanitized_value="ready"
            if (
                _final_readiness_prerequisite_satisfied(snapshot)
                and _post_guard_prerequisite_satisfied(snapshot)
                and _sanitized_result_prerequisite_satisfied(snapshot)
            )
            else "blocked",
            expected="final readiness, POST guard, and sanitized result ready",
        ),
        LiveOrderRealFinalExecStackControlledCheckResult(
            name="fake no-network transport",
            passed=(
                snapshot.dry_run_mode
                and snapshot.fake_transport_used
                and snapshot.no_network_transport_used
                and not snapshot.network_transport_used
                and not snapshot.real_transport_used
            ),
            sanitized_value="fake_no_network"
            if (
                snapshot.dry_run_mode
                and snapshot.fake_transport_used
                and snapshot.no_network_transport_used
                and not snapshot.network_transport_used
                and not snapshot.real_transport_used
            )
            else "blocked",
            expected="dry-run fake transport only",
        ),
        LiveOrderRealFinalExecStackControlledCheckResult(
            name="dry-run previews ready",
            passed=_dry_run_contract_complete(snapshot),
            sanitized_value="ready"
            if _dry_run_contract_complete(snapshot)
            else "blocked",
            expected="safe result reconciliation receipt and ledger previews",
        ),
        LiveOrderRealFinalExecStackControlledCheckResult(
            name="no API POST live_order_once or real receipt",
            passed=not _execution_attempted(snapshot),
            sanitized_value="blocked" if _execution_attempted(snapshot) else "clear",
            expected="no API no POST no live_order_once no actual receipt",
        ),
        LiveOrderRealFinalExecStackControlledCheckResult(
            name="ready is not post permission",
            passed=ready
            == (
                status
                is (
                    FinalExecStackControlledStatus
                    .FINAL_EXEC_STACK_READY_DRY_RUN_ONLY
                )
            ),
            sanitized_value=status.value,
            expected="dry-run ready only one-shot POST remains blocked",
        ),
    )


def _final_readiness_prerequisite_satisfied(
    snapshot: LiveOrderRealFinalExecStackControlledInput,
) -> bool:
    return (
        snapshot.final_readiness_prerequisite_checked
        and snapshot.final_readiness_controlled_ready
        and snapshot.final_readiness_prerequisite_satisfied
        and snapshot.safe_final_readiness_label == SAFE_FINAL_READINESS_LABEL
        and snapshot.safe_final_readiness_status == _ready_final_readiness_status()
    )


def _post_guard_prerequisite_satisfied(
    snapshot: LiveOrderRealFinalExecStackControlledInput,
) -> bool:
    return (
        snapshot.post_guard_prerequisite_checked
        and snapshot.post_guard_controlled_ready
        and snapshot.post_guard_prerequisite_satisfied
        and snapshot.safe_post_guard_label == SAFE_POST_GUARD_LABEL
        and snapshot.safe_post_guard_status == _ready_post_guard_status()
    )


def _sanitized_result_prerequisite_satisfied(
    snapshot: LiveOrderRealFinalExecStackControlledInput,
) -> bool:
    return (
        snapshot.sanitized_result_prerequisite_checked
        and snapshot.sanitized_post_result_ready
        and snapshot.reconciliation_ready
        and snapshot.sanitized_result_prerequisite_satisfied
        and snapshot.safe_post_result_label == SAFE_POST_RESULT_LABEL
        and snapshot.safe_post_result_status == _ready_sanitized_result_status()
        and snapshot.safe_reconciliation_label == SAFE_RECONCILIATION_LABEL
        and snapshot.safe_reconciliation_status == _ready_reconciliation_status()
    )


def _dry_run_contract_complete(
    snapshot: LiveOrderRealFinalExecStackControlledInput,
) -> bool:
    return (
        snapshot.dry_run_mode
        and snapshot.dry_run_stack_ready_input
        and snapshot.fake_transport_used
        and snapshot.no_network_transport_used
        and snapshot.dry_run_one_shot_decision_declared
        and snapshot.dry_run_one_shot_decision_safe
        and snapshot.dry_run_sanitized_result_ready
        and snapshot.dry_run_reconciliation_preview_ready
        and snapshot.dry_run_receipt_handoff_preview_ready
        and snapshot.dry_run_ledger_attempt_preview_ready
    )


def _execution_attempted(
    snapshot: LiveOrderRealFinalExecStackControlledInput,
) -> bool:
    return (
        snapshot.api_call_allowed
        or snapshot.api_call_executed
        or snapshot.api_call_attempted
        or snapshot.http_client_present
        or snapshot.post_allowed_this_step
        or snapshot.post_executed
        or snapshot.http_post_executed
        or snapshot.order_endpoint_called
        or snapshot.live_order_once_called
        or snapshot.fresh_preflight_executed
        or snapshot.final_confirmation_received
        or snapshot.ledger_update_allowed
        or snapshot.ledger_updated
        or snapshot.ledger_update_attempted
        or snapshot.attempt_counter_persistence_allowed
        or snapshot.attempt_counter_persisted
        or snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
        or snapshot.actual_receipt_handoff_allowed
        or snapshot.one_shot_post_allowed
    )


def _unsafe_exposure_attempted(
    snapshot: LiveOrderRealFinalExecStackControlledInput,
) -> bool:
    return (
        snapshot.unsafe_exposure_attempted
        or snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
        or snapshot.request_body_exposure_attempted
        or snapshot.response_body_exposure_attempted
        or snapshot.endpoint_actual_value_exposure_attempted
        or snapshot.confirmation_phrase_exposure_attempted
        or snapshot.ledger_state_exposure_attempted
        or snapshot.approval_command_exposure_attempted
        or snapshot.ledger_state_actual_value_exposed
        or not snapshot.safe_to_render
        or not snapshot.safe_to_serialize
    )


def _identifier_exposure_attempted(
    snapshot: LiveOrderRealFinalExecStackControlledInput,
) -> bool:
    return (
        snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.position_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
        or snapshot.real_id_exposure_attempted
        or snapshot.real_id_exposed
    )


def _validate_result_safety(
    result: LiveOrderRealFinalExecStackControlledResult,
) -> None:
    if result.dry_run_stack_ready and result.status is not (
        FinalExecStackControlledStatus.FINAL_EXEC_STACK_READY_DRY_RUN_ONLY
    ):
        raise LiveVerificationValidationError(
            "dry-run stack ready must match safe ready status",
        )
    if not result.one_shot_post_readiness_blocked or result.one_shot_post_allowed:
        raise LiveVerificationValidationError("one-shot POST must remain blocked")
    forbidden_true_fields = (
        "network_transport_used",
        "real_transport_used",
        "raw_request_generated",
        "raw_response_received",
        "broker_response_received",
        "api_response_received",
        "api_call_allowed",
        "api_call_executed",
        "post_allowed_this_step",
        "post_executed",
        "http_post_executed",
        "order_endpoint_called",
        "live_order_once_called",
        "fresh_preflight_executed",
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
        "raw_broker_api_response_exposed",
    )
    for field_name in forbidden_true_fields:
        if getattr(result, field_name):
            raise LiveVerificationValidationError(
                f"{field_name} must remain false in dry-run stack result",
            )


def _ready_final_readiness_status() -> str:
    return (
        LiveOrderRealFinalReadinessControlledStatus
        .FINAL_READINESS_READY_NO_POST
        .value
    )


def _ready_post_guard_status() -> str:
    return LiveOrderRealPostGuardControlledStatus.POST_GUARD_READY_NO_POST.value


def _ready_sanitized_result_status() -> str:
    return (
        LiveOrderRealSanitizedPostResultStatus
        .SANITIZED_RESULT_READY_NO_RECEIPT
        .value
    )


def _ready_reconciliation_status() -> str:
    return (
        LiveOrderRealSafeReconciliationStatus
        .RECONCILIATION_READY_NO_RECEIPT_HANDOFF
        .value
    )


def _validate_bool_fields(instance: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(instance, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _dedupe(reasons: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for reason in reasons:
        if reason not in seen:
            ordered.append(reason)
            seen.add(reason)
    return tuple(ordered)


_FINAL_EXEC_STACK_INPUT_BOOL_FIELDS = (
    "final_exec_stack_declared",
    "final_exec_stack_requested",
    "final_readiness_prerequisite_checked",
    "final_readiness_controlled_ready",
    "final_readiness_prerequisite_satisfied",
    "post_guard_prerequisite_checked",
    "post_guard_controlled_ready",
    "post_guard_prerequisite_satisfied",
    "sanitized_result_prerequisite_checked",
    "sanitized_post_result_ready",
    "reconciliation_ready",
    "sanitized_result_prerequisite_satisfied",
    "dry_run_stack_unknown",
    "dry_run_stack_failed",
    "dry_run_stack_unavailable",
    "dry_run_stack_timeout",
    "dry_run_stack_stale",
    "dry_run_stack_reused",
    "dry_run_mode",
    "dry_run_stack_ready_input",
    "fake_transport_used",
    "no_network_transport_used",
    "network_transport_used",
    "real_transport_used",
    "raw_request_generated",
    "raw_response_received",
    "broker_response_received",
    "api_response_received",
    "dry_run_one_shot_decision_declared",
    "dry_run_one_shot_decision_safe",
    "dry_run_sanitized_result_ready",
    "dry_run_reconciliation_preview_ready",
    "dry_run_receipt_handoff_preview_ready",
    "dry_run_ledger_attempt_preview_ready",
    "api_call_allowed",
    "api_call_executed",
    "api_call_attempted",
    "http_client_present",
    "post_allowed_this_step",
    "post_executed",
    "http_post_executed",
    "order_endpoint_called",
    "live_order_once_called",
    "fresh_preflight_executed",
    "final_confirmation_received",
    "ledger_update_allowed",
    "ledger_updated",
    "ledger_update_attempted",
    "attempt_counter_persistence_allowed",
    "attempt_counter_persisted",
    "actual_result_receipt_received",
    "actual_receipt_handoff_executed",
    "actual_receipt_handoff_allowed",
    "one_shot_post_allowed",
    "one_shot_post_readiness_blocked",
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
    "raw_broker_api_response_exposed",
    "safe_to_render",
    "safe_to_serialize",
)

_FINAL_EXEC_STACK_RESULT_BOOL_FIELDS = (
    "dry_run_stack_ready",
    "final_exec_stack_declared",
    "final_exec_stack_requested",
    "final_readiness_prerequisite_checked",
    "final_readiness_controlled_ready",
    "final_readiness_prerequisite_satisfied",
    "post_guard_prerequisite_checked",
    "post_guard_controlled_ready",
    "post_guard_prerequisite_satisfied",
    "sanitized_result_prerequisite_checked",
    "sanitized_post_result_ready",
    "reconciliation_ready",
    "sanitized_result_prerequisite_satisfied",
    "dry_run_stack_unknown",
    "dry_run_stack_failed",
    "dry_run_stack_unavailable",
    "dry_run_stack_timeout",
    "dry_run_stack_stale",
    "dry_run_stack_reused",
    "dry_run_mode",
    "fake_transport_used",
    "no_network_transport_used",
    "network_transport_used",
    "real_transport_used",
    "raw_request_generated",
    "raw_response_received",
    "broker_response_received",
    "api_response_received",
    "dry_run_sanitized_result_ready",
    "dry_run_reconciliation_preview_ready",
    "dry_run_receipt_handoff_preview_ready",
    "dry_run_ledger_attempt_preview_ready",
    "api_call_allowed",
    "api_call_executed",
    "post_allowed_this_step",
    "post_executed",
    "http_post_executed",
    "order_endpoint_called",
    "live_order_once_called",
    "fresh_preflight_executed",
    "final_confirmation_received",
    "ledger_update_allowed",
    "ledger_updated",
    "attempt_counter_persistence_allowed",
    "attempt_counter_persisted",
    "actual_result_receipt_received",
    "actual_receipt_handoff_executed",
    "actual_receipt_handoff_allowed",
    "one_shot_post_allowed",
    "one_shot_post_readiness_blocked",
    "raw_request_stored",
    "raw_response_stored",
    "broker_response_exposed",
    "api_response_exposed",
    "real_id_exposed",
    "ledger_state_actual_value_exposed",
    "raw_broker_api_response_exposed",
    "safe_to_render",
    "safe_to_serialize",
)
