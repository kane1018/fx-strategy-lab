"""Step 6G one-shot POST ready gate controlled contract.

This module models the final ready gate before a later one-shot POST execution
step. It accepts only safe booleans and labels. It does not call APIs, execute
HTTP POST, call order endpoints, call live_order_once, rerun fresh preflight,
obtain final confirmation, update ledgers, persist attempt counters, receive
actual results, or hand off receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import get_type_hints

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_final_confirmation_gate_controlled import (
    LiveOrderRealFinalConfirmationGateControlledResult,
)
from app.live_verification.live_order_real_final_exec_stack_controlled import (
    SAFE_DRY_RUN_STACK_LABEL,
    LiveOrderRealFinalExecStackControlledResult,
    LiveOrderRealFinalExecStackControlledStatus,
)
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
    LiveOrderRealSanitizedPostResultResult,
    LiveOrderRealSanitizedPostResultStatus,
)

ONE_SHOT_POST_READY_GATE_RECOMMENDED_NEXT_STEP = (
    "one_shot_post_execution_gate_requires_new_explicit_confirmation"
)
SAFE_ONE_SHOT_POST_READY_GATE_LABEL = (
    "CONTROLLED_ONE_SHOT_POST_READY_GATE_NO_POST"
)
UNSUPPORTED_ONE_SHOT_POST_READY_GATE_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealOneShotPostReadyGateControlledStatus(str, Enum):
    ONE_SHOT_POST_READY_GATE_NOT_READY = "ONE_SHOT_POST_READY_GATE_NOT_READY"
    ONE_SHOT_POST_READY_GATE_PASSED_NO_POST = (
        "ONE_SHOT_POST_READY_GATE_PASSED_NO_POST"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_MISSING_FRESH_PREFLIGHT = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_MISSING_FRESH_PREFLIGHT"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_MISSING_FINAL_CONFIRMATION = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_MISSING_FINAL_CONFIRMATION"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_CONFIRMATION_REUSED = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_CONFIRMATION_REUSED"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_POST_GUARD_NOT_READY = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_POST_GUARD_NOT_READY"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_FINAL_READINESS_NOT_READY = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_FINAL_READINESS_NOT_READY"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_FINAL_EXEC_STACK_NOT_READY = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_FINAL_EXEC_STACK_NOT_READY"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_SANITIZED_RESULT_NOT_READY = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_SANITIZED_RESULT_NOT_READY"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_POST_ATTEMPTED = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_POST_ATTEMPTED"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_ORDER_ENDPOINT = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_ORDER_ENDPOINT"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_LIVE_ORDER_ONCE = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_LIVE_ORDER_ONCE"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_LEDGER_UPDATE = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_LEDGER_UPDATE"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_RECEIPT_HANDOFF = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_RECEIPT_HANDOFF"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_RAW_EXPOSURE = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_RAW_EXPOSURE"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_ID_EXPOSURE = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_ID_EXPOSURE"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_VALUE_EXPOSURE = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_VALUE_EXPOSURE"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_UNKNOWN = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_UNKNOWN"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_FAILED = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_FAILED"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_TIMEOUT = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_TIMEOUT"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_UNAVAILABLE = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_UNAVAILABLE"
    )
    ONE_SHOT_POST_READY_GATE_BLOCKED_STALE = (
        "ONE_SHOT_POST_READY_GATE_BLOCKED_STALE"
    )


class LiveOrderRealOneShotPostReadyGateControlledMode(str, Enum):
    ONE_SHOT_POST_READY_GATE_CONTROLLED_NO_POST = (
        "ONE_SHOT_POST_READY_GATE_CONTROLLED_NO_POST"
    )


OneShotPostReadyGateControlledStatus = (
    LiveOrderRealOneShotPostReadyGateControlledStatus
)
OneShotPostReadyGateControlledMode = (
    LiveOrderRealOneShotPostReadyGateControlledMode
)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostReadyGateControlledInput:
    one_shot_post_ready_gate_mode: str = (
        OneShotPostReadyGateControlledMode
        .ONE_SHOT_POST_READY_GATE_CONTROLLED_NO_POST
        .value
    )
    one_shot_post_ready_gate_requested: bool = True
    safe_one_shot_post_ready_gate_label: str = (
        SAFE_ONE_SHOT_POST_READY_GATE_LABEL
    )
    fresh_preflight_passed_required: bool = True
    fresh_preflight_passed: bool = True
    fresh_preflight_current: bool = True
    fresh_preflight_new: bool = True
    fresh_preflight_reused: bool = False
    fresh_preflight_stale: bool = False
    fresh_preflight_unknown: bool = False
    fresh_preflight_failed: bool = False
    fresh_preflight_timeout: bool = False
    fresh_preflight_unavailable: bool = False
    final_confirmation_required: bool = True
    final_confirmation_received: bool = True
    confirmation_current_turn: bool = True
    confirmation_new: bool = True
    confirmation_one_time: bool = True
    confirmation_reused: bool = False
    previous_turn_confirmation_reused: bool = False
    step4_approval_phrase_reused: bool = False
    confirmation_actual_value_stored: bool = False
    confirmation_actual_value_reported: bool = False
    confirmation_actual_value_logged: bool = False
    post_guard_ready: bool = True
    safe_post_guard_label: str = SAFE_POST_GUARD_LABEL
    safe_post_guard_status: str = (
        LiveOrderRealPostGuardControlledStatus.POST_GUARD_READY_NO_POST.value
    )
    one_post_max: bool = True
    retry_allowed: bool = False
    timeout_fail_closed: bool = True
    final_readiness_ready: bool = True
    safe_final_readiness_label: str = SAFE_FINAL_READINESS_LABEL
    safe_final_readiness_status: str = (
        LiveOrderRealFinalReadinessControlledStatus
        .FINAL_READINESS_READY_NO_POST
        .value
    )
    final_exec_stack_ready: bool = True
    safe_final_exec_stack_label: str = SAFE_DRY_RUN_STACK_LABEL
    safe_final_exec_stack_status: str = (
        LiveOrderRealFinalExecStackControlledStatus
        .FINAL_EXEC_STACK_READY_DRY_RUN_ONLY
        .value
    )
    sanitized_result_contract_ready: bool = True
    safe_post_result_label: str = SAFE_POST_RESULT_LABEL
    safe_post_result_status: str = (
        LiveOrderRealSanitizedPostResultStatus
        .SANITIZED_RESULT_READY_NO_RECEIPT
        .value
    )
    ledger_update_required_after_post_only: bool = True
    actual_receipt_handoff_required_after_post_only: bool = True
    actual_post_permitted_now: bool = False
    post_allowed_this_step: bool = False
    post_executed: bool = False
    http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    ledger_update_allowed: bool = False
    ledger_updated: bool = False
    ledger_update_attempted: bool = False
    attempt_counter_persistence_allowed: bool = False
    attempt_counter_persisted: bool = False
    actual_result_receipt_received: bool = False
    actual_receipt_handoff_executed: bool = False
    actual_receipt_handoff_allowed: bool = False
    fresh_preflight_reexecuted: bool = False
    final_confirmation_reobtained: bool = False
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
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty(
            "one_shot_post_ready_gate_mode",
            self.one_shot_post_ready_gate_mode,
        )
        _require_non_empty(
            "safe_one_shot_post_ready_gate_label",
            self.safe_one_shot_post_ready_gate_label,
        )
        _require_non_empty("safe_post_guard_label", self.safe_post_guard_label)
        _require_non_empty("safe_post_guard_status", self.safe_post_guard_status)
        _require_non_empty(
            "safe_final_readiness_label",
            self.safe_final_readiness_label,
        )
        _require_non_empty(
            "safe_final_readiness_status",
            self.safe_final_readiness_status,
        )
        _require_non_empty(
            "safe_final_exec_stack_label",
            self.safe_final_exec_stack_label,
        )
        _require_non_empty(
            "safe_final_exec_stack_status",
            self.safe_final_exec_stack_status,
        )
        _require_non_empty("safe_post_result_label", self.safe_post_result_label)
        _require_non_empty("safe_post_result_status", self.safe_post_result_status)
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealOneShotPostReadyGateControlledResult:
    status: LiveOrderRealOneShotPostReadyGateControlledStatus
    ready_gate_passed: bool
    one_shot_post_execution_step_may_be_planned: bool
    one_shot_post_ready_gate_mode: str
    safe_one_shot_post_ready_gate_label: str
    safe_one_shot_post_ready_gate_status: str
    fresh_preflight_passed_required: bool
    fresh_preflight_passed: bool
    fresh_preflight_current: bool
    fresh_preflight_new: bool
    fresh_preflight_reused: bool
    fresh_preflight_stale: bool
    fresh_preflight_unknown: bool
    fresh_preflight_failed: bool
    fresh_preflight_timeout: bool
    fresh_preflight_unavailable: bool
    final_confirmation_required: bool
    final_confirmation_received: bool
    confirmation_current_turn: bool
    confirmation_new: bool
    confirmation_one_time: bool
    confirmation_reused: bool
    previous_turn_confirmation_reused: bool
    step4_approval_phrase_reused: bool
    confirmation_actual_value_stored: bool
    confirmation_actual_value_reported: bool
    confirmation_actual_value_logged: bool
    post_guard_ready: bool
    safe_post_guard_label: str
    safe_post_guard_status: str
    one_post_max: bool
    retry_allowed: bool
    timeout_fail_closed: bool
    final_readiness_ready: bool
    safe_final_readiness_label: str
    safe_final_readiness_status: str
    final_exec_stack_ready: bool
    safe_final_exec_stack_label: str
    safe_final_exec_stack_status: str
    sanitized_result_contract_ready: bool
    safe_post_result_label: str
    safe_post_result_status: str
    ledger_update_required_after_post_only: bool
    actual_receipt_handoff_required_after_post_only: bool
    actual_post_permitted_now: bool
    post_allowed_this_step: bool
    post_executed: bool
    http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    ledger_update_allowed: bool
    ledger_updated: bool
    ledger_update_attempted: bool
    attempt_counter_persistence_allowed: bool
    attempt_counter_persisted: bool
    actual_result_receipt_received: bool
    actual_receipt_handoff_executed: bool
    actual_receipt_handoff_allowed: bool
    fresh_preflight_reexecuted: bool
    final_confirmation_reobtained: bool
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
    safe_to_render: bool
    safe_to_serialize: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealOneShotPostReadyGateControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be one-shot post ready gate controlled status",
            )
        _require_non_empty(
            "one_shot_post_ready_gate_mode",
            self.one_shot_post_ready_gate_mode,
        )
        _require_non_empty(
            "safe_one_shot_post_ready_gate_label",
            self.safe_one_shot_post_ready_gate_label,
        )
        _require_non_empty(
            "safe_one_shot_post_ready_gate_status",
            self.safe_one_shot_post_ready_gate_status,
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_one_shot_post_ready_gate_controlled(
    *,
    input_snapshot: (
        LiveOrderRealOneShotPostReadyGateControlledInput | None
    ) = None,
    final_confirmation_result: (
        LiveOrderRealFinalConfirmationGateControlledResult | None
    ) = None,
    post_guard_result: LiveOrderRealPostGuardControlledResult | None = None,
    final_readiness_result: (
        LiveOrderRealFinalReadinessControlledResult | None
    ) = None,
    final_exec_stack_result: (
        LiveOrderRealFinalExecStackControlledResult | None
    ) = None,
    sanitized_result: LiveOrderRealSanitizedPostResultResult | None = None,
) -> LiveOrderRealOneShotPostReadyGateControlledResult:
    """Build a safe ready-gate result with no execution side effects."""
    snapshot = input_snapshot or LiveOrderRealOneShotPostReadyGateControlledInput()
    if final_confirmation_result is not None:
        snapshot = _merge_final_confirmation_result(
            snapshot,
            final_confirmation_result,
        )
    if post_guard_result is not None:
        snapshot = _merge_post_guard_result(snapshot, post_guard_result)
    if final_readiness_result is not None:
        snapshot = _merge_final_readiness_result(snapshot, final_readiness_result)
    if final_exec_stack_result is not None:
        snapshot = _merge_final_exec_stack_result(snapshot, final_exec_stack_result)
    if sanitized_result is not None:
        snapshot = _merge_sanitized_result(snapshot, sanitized_result)

    status, primary_reasons = _status_from_input(snapshot)
    passed = (
        status
        is (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_PASSED_NO_POST
        )
    )
    safe_mode = (
        snapshot.one_shot_post_ready_gate_mode
        if snapshot.one_shot_post_ready_gate_mode
        == (
            OneShotPostReadyGateControlledMode
            .ONE_SHOT_POST_READY_GATE_CONTROLLED_NO_POST
            .value
        )
        else UNSUPPORTED_ONE_SHOT_POST_READY_GATE_LABEL
    )
    safe_label = (
        snapshot.safe_one_shot_post_ready_gate_label
        if snapshot.safe_one_shot_post_ready_gate_label
        == SAFE_ONE_SHOT_POST_READY_GATE_LABEL
        else UNSUPPORTED_ONE_SHOT_POST_READY_GATE_LABEL
    )

    return LiveOrderRealOneShotPostReadyGateControlledResult(
        status=status,
        ready_gate_passed=passed,
        one_shot_post_execution_step_may_be_planned=passed,
        one_shot_post_ready_gate_mode=safe_mode,
        safe_one_shot_post_ready_gate_label=safe_label,
        safe_one_shot_post_ready_gate_status=status.value,
        fresh_preflight_passed_required=(
            snapshot.fresh_preflight_passed_required
        ),
        fresh_preflight_passed=snapshot.fresh_preflight_passed,
        fresh_preflight_current=snapshot.fresh_preflight_current,
        fresh_preflight_new=snapshot.fresh_preflight_new,
        fresh_preflight_reused=snapshot.fresh_preflight_reused,
        fresh_preflight_stale=snapshot.fresh_preflight_stale,
        fresh_preflight_unknown=snapshot.fresh_preflight_unknown,
        fresh_preflight_failed=snapshot.fresh_preflight_failed,
        fresh_preflight_timeout=snapshot.fresh_preflight_timeout,
        fresh_preflight_unavailable=snapshot.fresh_preflight_unavailable,
        final_confirmation_required=snapshot.final_confirmation_required,
        final_confirmation_received=snapshot.final_confirmation_received,
        confirmation_current_turn=snapshot.confirmation_current_turn,
        confirmation_new=snapshot.confirmation_new,
        confirmation_one_time=snapshot.confirmation_one_time,
        confirmation_reused=snapshot.confirmation_reused,
        previous_turn_confirmation_reused=(
            snapshot.previous_turn_confirmation_reused
        ),
        step4_approval_phrase_reused=snapshot.step4_approval_phrase_reused,
        confirmation_actual_value_stored=False,
        confirmation_actual_value_reported=False,
        confirmation_actual_value_logged=False,
        post_guard_ready=snapshot.post_guard_ready,
        safe_post_guard_label=_safe_label(
            snapshot.safe_post_guard_label,
            SAFE_POST_GUARD_LABEL,
        ),
        safe_post_guard_status=snapshot.safe_post_guard_status,
        one_post_max=snapshot.one_post_max,
        retry_allowed=snapshot.retry_allowed,
        timeout_fail_closed=snapshot.timeout_fail_closed,
        final_readiness_ready=snapshot.final_readiness_ready,
        safe_final_readiness_label=_safe_label(
            snapshot.safe_final_readiness_label,
            SAFE_FINAL_READINESS_LABEL,
        ),
        safe_final_readiness_status=snapshot.safe_final_readiness_status,
        final_exec_stack_ready=snapshot.final_exec_stack_ready,
        safe_final_exec_stack_label=_safe_label(
            snapshot.safe_final_exec_stack_label,
            SAFE_DRY_RUN_STACK_LABEL,
        ),
        safe_final_exec_stack_status=snapshot.safe_final_exec_stack_status,
        sanitized_result_contract_ready=snapshot.sanitized_result_contract_ready,
        safe_post_result_label=_safe_label(
            snapshot.safe_post_result_label,
            SAFE_POST_RESULT_LABEL,
        ),
        safe_post_result_status=snapshot.safe_post_result_status,
        ledger_update_required_after_post_only=(
            snapshot.ledger_update_required_after_post_only
        ),
        actual_receipt_handoff_required_after_post_only=(
            snapshot.actual_receipt_handoff_required_after_post_only
        ),
        actual_post_permitted_now=False,
        post_allowed_this_step=False,
        post_executed=False,
        http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        ledger_update_allowed=False,
        ledger_updated=False,
        ledger_update_attempted=False,
        attempt_counter_persistence_allowed=False,
        attempt_counter_persisted=False,
        actual_result_receipt_received=False,
        actual_receipt_handoff_executed=False,
        actual_receipt_handoff_allowed=False,
        fresh_preflight_reexecuted=False,
        final_confirmation_reobtained=False,
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
        safe_to_render=True,
        safe_to_serialize=True,
        blocked_reasons=_blocked_reasons(snapshot, primary_reasons),
        recommended_next_step=(
            ONE_SHOT_POST_READY_GATE_RECOMMENDED_NEXT_STEP
            if passed
            else "fix_one_shot_post_ready_gate_blockers_no_post"
        ),
    )


def render_live_order_real_one_shot_post_ready_gate_controlled_markdown(
    result: LiveOrderRealOneShotPostReadyGateControlledResult,
) -> str:
    """Render a safe one-shot POST ready gate summary only."""
    lines = [
        "# Step 6G One-Shot POST Ready Gate Controlled",
        "",
        "This is a ready gate summary only.",
        "It contains safe labels, statuses, booleans, and blocked reason labels.",
        "It does not execute HTTP POST.",
        "It does not call order endpoints.",
        "It does not call live_order_once.",
        "It does not rerun fresh preflight.",
        "It does not obtain final confirmation.",
        "It does not update ledgers or persist attempt counters.",
        "It does not receive actual results or hand off receipts.",
        "Ready gate passed does not permit POST in this step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        f"- ready_gate_passed: {_bool_text(result.ready_gate_passed)}",
        (
            "- one_shot_post_execution_step_may_be_planned: "
            f"{_bool_text(result.one_shot_post_execution_step_may_be_planned)}"
        ),
        (
            "- actual_post_permitted_now: "
            f"{_bool_text(result.actual_post_permitted_now)}"
        ),
        (
            "- post_allowed_this_step: "
            f"{_bool_text(result.post_allowed_this_step)}"
        ),
        "",
        "## Prerequisites",
        f"- fresh_preflight_passed: {_bool_text(result.fresh_preflight_passed)}",
        f"- fresh_preflight_current: {_bool_text(result.fresh_preflight_current)}",
        f"- fresh_preflight_new: {_bool_text(result.fresh_preflight_new)}",
        f"- fresh_preflight_reused: {_bool_text(result.fresh_preflight_reused)}",
        (
            "- final_confirmation_received: "
            f"{_bool_text(result.final_confirmation_received)}"
        ),
        (
            "- confirmation_current_turn: "
            f"{_bool_text(result.confirmation_current_turn)}"
        ),
        f"- confirmation_new: {_bool_text(result.confirmation_new)}",
        f"- confirmation_one_time: {_bool_text(result.confirmation_one_time)}",
        f"- confirmation_reused: {_bool_text(result.confirmation_reused)}",
        "",
        "## Readiness Contracts",
        f"- post_guard_ready: {_bool_text(result.post_guard_ready)}",
        f"- one_post_max: {_bool_text(result.one_post_max)}",
        f"- retry_allowed: {_bool_text(result.retry_allowed)}",
        f"- timeout_fail_closed: {_bool_text(result.timeout_fail_closed)}",
        f"- final_readiness_ready: {_bool_text(result.final_readiness_ready)}",
        f"- final_exec_stack_ready: {_bool_text(result.final_exec_stack_ready)}",
        (
            "- sanitized_result_contract_ready: "
            f"{_bool_text(result.sanitized_result_contract_ready)}"
        ),
        (
            "- ledger_update_required_after_post_only: "
            f"{_bool_text(result.ledger_update_required_after_post_only)}"
        ),
        (
            "- actual_receipt_handoff_required_after_post_only: "
            f"{_bool_text(result.actual_receipt_handoff_required_after_post_only)}"
        ),
        "",
        "## Non-Execution",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
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


def _merge_final_confirmation_result(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
    final_confirmation_result: LiveOrderRealFinalConfirmationGateControlledResult,
) -> LiveOrderRealOneShotPostReadyGateControlledInput:
    return replace(
        snapshot,
        final_confirmation_received=(
            final_confirmation_result.final_confirmation_received
        ),
        confirmation_current_turn=(
            final_confirmation_result.confirmation_current_turn
        ),
        confirmation_new=final_confirmation_result.confirmation_new,
        confirmation_one_time=final_confirmation_result.confirmation_one_time,
        confirmation_reused=final_confirmation_result.confirmation_reused,
        previous_turn_confirmation_reused=(
            final_confirmation_result.previous_turn_confirmation_reused
        ),
        step4_approval_phrase_reused=(
            final_confirmation_result.step4_approval_phrase_reused
        ),
        confirmation_actual_value_stored=(
            final_confirmation_result.confirmation_actual_value_stored
        ),
        confirmation_actual_value_reported=(
            final_confirmation_result.confirmation_actual_value_reported
        ),
        confirmation_actual_value_logged=(
            final_confirmation_result.confirmation_actual_value_logged
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step
            or final_confirmation_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or final_confirmation_result.post_executed,
        http_post_executed=(
            snapshot.http_post_executed
            or final_confirmation_result.http_post_executed
        ),
        order_endpoint_called=(
            snapshot.order_endpoint_called
            or final_confirmation_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called
            or final_confirmation_result.live_order_once_called
        ),
        ledger_updated=snapshot.ledger_updated or final_confirmation_result.ledger_updated,
        attempt_counter_persisted=(
            snapshot.attempt_counter_persisted
            or final_confirmation_result.attempt_counter_persisted
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or final_confirmation_result.actual_receipt_handoff_executed
        ),
    )


def _merge_post_guard_result(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
    post_guard_result: LiveOrderRealPostGuardControlledResult,
) -> LiveOrderRealOneShotPostReadyGateControlledInput:
    return replace(
        snapshot,
        post_guard_ready=post_guard_result.post_guard_ready,
        safe_post_guard_label=post_guard_result.safe_post_guard_label,
        safe_post_guard_status=post_guard_result.safe_post_guard_status,
        one_post_max=post_guard_result.one_post_max_enforced,
        retry_allowed=not post_guard_result.no_retry_enforced,
        timeout_fail_closed=post_guard_result.timeout_fail_closed_enforced,
        actual_post_permitted_now=(
            snapshot.actual_post_permitted_now
            or post_guard_result.post_allowed_this_step
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
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or post_guard_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or post_guard_result.actual_receipt_handoff_executed
        ),
    )


def _merge_final_readiness_result(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
    final_readiness_result: LiveOrderRealFinalReadinessControlledResult,
) -> LiveOrderRealOneShotPostReadyGateControlledInput:
    return replace(
        snapshot,
        final_readiness_ready=(
            final_readiness_result.final_readiness_controlled_ready
        ),
        safe_final_readiness_label=(
            final_readiness_result.safe_final_readiness_label
        ),
        safe_final_readiness_status=(
            final_readiness_result.safe_final_readiness_status
        ),
        sanitized_result_contract_ready=(
            snapshot.sanitized_result_contract_ready
            and final_readiness_result.sanitized_post_result_ready
            and final_readiness_result.reconciliation_ready
        ),
        ledger_update_required_after_post_only=(
            final_readiness_result.ledger_attempt_counter_required
            and not final_readiness_result.ledger_update_allowed
        ),
        actual_receipt_handoff_required_after_post_only=(
            final_readiness_result.actual_receipt_handoff_required
            and not final_readiness_result.actual_receipt_handoff_allowed
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step
            or final_readiness_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or final_readiness_result.post_executed,
        http_post_executed=(
            snapshot.http_post_executed
            or final_readiness_result.http_post_executed
        ),
        order_endpoint_called=(
            snapshot.order_endpoint_called
            or final_readiness_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called
            or final_readiness_result.live_order_once_called
        ),
        ledger_update_attempted=(
            snapshot.ledger_update_attempted
            or final_readiness_result.ledger_update_attempted
        ),
        attempt_counter_persisted=(
            snapshot.attempt_counter_persisted
            or final_readiness_result.attempt_counter_persisted
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or final_readiness_result.actual_receipt_handoff_executed
        ),
    )


def _merge_final_exec_stack_result(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
    final_exec_stack_result: LiveOrderRealFinalExecStackControlledResult,
) -> LiveOrderRealOneShotPostReadyGateControlledInput:
    return replace(
        snapshot,
        final_exec_stack_ready=final_exec_stack_result.dry_run_stack_ready,
        safe_final_exec_stack_label=final_exec_stack_result.safe_dry_run_stack_label,
        safe_final_exec_stack_status=(
            final_exec_stack_result.safe_dry_run_stack_status
        ),
        post_allowed_this_step=(
            snapshot.post_allowed_this_step
            or final_exec_stack_result.post_allowed_this_step
        ),
        post_executed=snapshot.post_executed or final_exec_stack_result.post_executed,
        http_post_executed=(
            snapshot.http_post_executed
            or final_exec_stack_result.http_post_executed
        ),
        order_endpoint_called=(
            snapshot.order_endpoint_called
            or final_exec_stack_result.order_endpoint_called
        ),
        live_order_once_called=(
            snapshot.live_order_once_called
            or final_exec_stack_result.live_order_once_called
        ),
        ledger_updated=snapshot.ledger_updated or final_exec_stack_result.ledger_updated,
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
    )


def _merge_sanitized_result(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
    sanitized_result: LiveOrderRealSanitizedPostResultResult,
) -> LiveOrderRealOneShotPostReadyGateControlledInput:
    return replace(
        snapshot,
        sanitized_result_contract_ready=(
            sanitized_result.sanitized_post_result_ready
            and sanitized_result.reconciliation_ready
        ),
        safe_post_result_label=sanitized_result.safe_post_result_label,
        safe_post_result_status=sanitized_result.safe_post_result_status,
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
        attempt_counter_persisted=(
            snapshot.attempt_counter_persisted
            or sanitized_result.attempt_counter_persisted
        ),
        actual_result_receipt_received=(
            snapshot.actual_result_receipt_received
            or sanitized_result.actual_result_receipt_received
        ),
        actual_receipt_handoff_executed=(
            snapshot.actual_receipt_handoff_executed
            or sanitized_result.actual_receipt_handoff_executed
        ),
    )


def _status_from_input(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
) -> tuple[LiveOrderRealOneShotPostReadyGateControlledStatus, tuple[str, ...]]:
    if (
        snapshot.one_shot_post_ready_gate_mode
        != (
            OneShotPostReadyGateControlledMode
            .ONE_SHOT_POST_READY_GATE_CONTROLLED_NO_POST
            .value
        )
    ):
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_UNKNOWN,
            ("unsupported_one_shot_post_ready_gate_mode",),
        )
    if not snapshot.one_shot_post_ready_gate_requested:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_NOT_READY,
            ("one_shot_post_ready_gate_not_requested",),
        )
    if snapshot.fresh_preflight_unknown:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_UNKNOWN,
            ("fresh_preflight_unknown",),
        )
    if snapshot.fresh_preflight_failed:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_FAILED,
            ("fresh_preflight_failed",),
        )
    if snapshot.fresh_preflight_timeout:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_TIMEOUT,
            ("fresh_preflight_timeout",),
        )
    if snapshot.fresh_preflight_unavailable:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_UNAVAILABLE,
            ("fresh_preflight_unavailable",),
        )
    if snapshot.fresh_preflight_stale:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_STALE,
            ("fresh_preflight_stale",),
        )
    if not _fresh_preflight_prerequisite_satisfied(snapshot):
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_MISSING_FRESH_PREFLIGHT,
            ("fresh_preflight_pass_current_new_non_reused_missing",),
        )
    if snapshot.confirmation_reused or snapshot.previous_turn_confirmation_reused:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_CONFIRMATION_REUSED,
            ("confirmation_reused",),
        )
    if snapshot.step4_approval_phrase_reused:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_CONFIRMATION_REUSED,
            ("step4_approval_phrase_reused",),
        )
    if not _final_confirmation_prerequisite_satisfied(snapshot):
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_MISSING_FINAL_CONFIRMATION,
            ("final_confirmation_current_new_one_time_missing",),
        )
    if not snapshot.post_guard_ready:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_POST_GUARD_NOT_READY,
            ("post_guard_not_ready",),
        )
    if not snapshot.one_post_max or snapshot.retry_allowed:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_POST_GUARD_NOT_READY,
            ("one_post_max_or_no_retry_missing",),
        )
    if not snapshot.timeout_fail_closed:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_POST_GUARD_NOT_READY,
            ("timeout_fail_closed_missing",),
        )
    if not snapshot.final_readiness_ready:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_FINAL_READINESS_NOT_READY,
            ("final_readiness_not_ready",),
        )
    if not snapshot.final_exec_stack_ready:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_FINAL_EXEC_STACK_NOT_READY,
            ("final_exec_stack_not_ready",),
        )
    if not snapshot.sanitized_result_contract_ready:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_SANITIZED_RESULT_NOT_READY,
            ("sanitized_result_contract_not_ready",),
        )
    if not snapshot.ledger_update_required_after_post_only:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_LEDGER_UPDATE,
            ("ledger_update_not_after_post_only",),
        )
    if not snapshot.actual_receipt_handoff_required_after_post_only:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_RECEIPT_HANDOFF,
            ("actual_receipt_handoff_not_after_post_only",),
        )
    if snapshot.actual_post_permitted_now or snapshot.post_allowed_this_step:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_POST_ATTEMPTED,
            ("post_permission_attempted_this_step",),
        )
    if snapshot.http_post_executed or snapshot.post_executed:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_POST_ATTEMPTED,
            ("post_attempted_or_executed",),
        )
    if snapshot.order_endpoint_called:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_ORDER_ENDPOINT,
            ("order_endpoint_called",),
        )
    if snapshot.live_order_once_called:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_LIVE_ORDER_ONCE,
            ("live_order_once_called",),
        )
    if _ledger_attempted(snapshot):
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_LEDGER_UPDATE,
            ("ledger_or_attempt_counter_attempted",),
        )
    if _receipt_attempted(snapshot):
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_RECEIPT_HANDOFF,
            ("actual_receipt_or_handoff_attempted",),
        )
    if snapshot.fresh_preflight_reexecuted:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_MISSING_FRESH_PREFLIGHT,
            ("fresh_preflight_reexecution_attempted",),
        )
    if snapshot.final_confirmation_reobtained:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_MISSING_FINAL_CONFIRMATION,
            ("final_confirmation_reobtain_attempted",),
        )
    if snapshot.raw_request_exposed or snapshot.raw_response_exposed:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_RAW_EXPOSURE,
            ("raw_request_or_response_exposed",),
        )
    if snapshot.broker_api_response_exposed:
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_RAW_EXPOSURE,
            ("broker_api_response_exposed",),
        )
    if _id_exposed(snapshot):
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_ID_EXPOSURE,
            ("id_exposed",),
        )
    if _value_exposed(snapshot):
        return (
            OneShotPostReadyGateControlledStatus
            .ONE_SHOT_POST_READY_GATE_BLOCKED_VALUE_EXPOSURE,
            ("credential_signature_header_or_confirmation_value_exposed",),
        )
    return (
        OneShotPostReadyGateControlledStatus
        .ONE_SHOT_POST_READY_GATE_PASSED_NO_POST,
        (),
    )


def _fresh_preflight_prerequisite_satisfied(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
) -> bool:
    return (
        snapshot.fresh_preflight_passed_required
        and snapshot.fresh_preflight_passed
        and snapshot.fresh_preflight_current
        and snapshot.fresh_preflight_new
        and not snapshot.fresh_preflight_reused
        and not snapshot.fresh_preflight_stale
    )


def _final_confirmation_prerequisite_satisfied(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
) -> bool:
    return (
        snapshot.final_confirmation_required
        and snapshot.final_confirmation_received
        and snapshot.confirmation_current_turn
        and snapshot.confirmation_new
        and snapshot.confirmation_one_time
        and not snapshot.confirmation_reused
        and not snapshot.previous_turn_confirmation_reused
        and not snapshot.step4_approval_phrase_reused
        and not snapshot.confirmation_actual_value_stored
        and not snapshot.confirmation_actual_value_reported
        and not snapshot.confirmation_actual_value_logged
    )


def _ledger_attempted(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
) -> bool:
    return (
        snapshot.ledger_update_allowed
        or snapshot.ledger_updated
        or snapshot.ledger_update_attempted
        or snapshot.attempt_counter_persistence_allowed
        or snapshot.attempt_counter_persisted
    )


def _receipt_attempted(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
) -> bool:
    return (
        snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
        or snapshot.actual_receipt_handoff_allowed
    )


def _id_exposed(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
) -> bool:
    return (
        snapshot.real_id_exposed
        or snapshot.account_id_exposed
        or snapshot.order_id_exposed
        or snapshot.transaction_id_exposed
    )


def _value_exposed(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
) -> bool:
    return (
        snapshot.credential_value_exposed
        or snapshot.signature_value_exposed
        or snapshot.headers_value_exposed
        or snapshot.confirmation_actual_value_stored
        or snapshot.confirmation_actual_value_reported
        or snapshot.confirmation_actual_value_logged
    )


def _blocked_reasons(
    snapshot: LiveOrderRealOneShotPostReadyGateControlledInput,
    primary_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons = list(primary_reasons)
    if snapshot.post_allowed_this_step:
        reasons.append("post_allowed_this_step_true")
    if snapshot.http_post_executed:
        reasons.append("http_post_executed")
    if snapshot.order_endpoint_called:
        reasons.append("order_endpoint_called")
    if snapshot.live_order_once_called:
        reasons.append("live_order_once_called")
    if _ledger_attempted(snapshot):
        reasons.append("ledger_or_attempt_counter_attempted")
    if _receipt_attempted(snapshot):
        reasons.append("actual_receipt_or_handoff_attempted")
    if _id_exposed(snapshot):
        reasons.append("id_exposure_attempted")
    if _value_exposed(snapshot):
        reasons.append("value_exposure_attempted")
    if snapshot.raw_request_exposed or snapshot.raw_response_exposed:
        reasons.append("raw_request_or_response_exposure_attempted")
    if snapshot.broker_api_response_exposed:
        reasons.append("broker_api_response_exposure_attempted")
    return tuple(dict.fromkeys(reasons))


def _validate_result_safety(
    result: LiveOrderRealOneShotPostReadyGateControlledResult,
) -> None:
    forbidden_true_fields = (
        "actual_post_permitted_now",
        "post_allowed_this_step",
        "post_executed",
        "http_post_executed",
        "order_endpoint_called",
        "live_order_once_called",
        "ledger_update_allowed",
        "ledger_updated",
        "ledger_update_attempted",
        "attempt_counter_persistence_allowed",
        "attempt_counter_persisted",
        "actual_result_receipt_received",
        "actual_receipt_handoff_executed",
        "actual_receipt_handoff_allowed",
        "fresh_preflight_reexecuted",
        "final_confirmation_reobtained",
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
    for field_name in forbidden_true_fields:
        if getattr(result, field_name):
            raise LiveVerificationValidationError(
                f"{field_name} must remain false in one-shot ready gate result",
            )


def _safe_label(candidate: str, expected: str) -> str:
    return candidate if candidate == expected else UNSUPPORTED_ONE_SHOT_POST_READY_GATE_LABEL


def _validate_bool_fields(obj: object, fields: tuple[str, ...]) -> None:
    for field_name in fields:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{name} must be non-empty string")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _bool_fields_for(cls: type[object]) -> tuple[str, ...]:
    hints = get_type_hints(cls)
    return tuple(name for name, annotation in hints.items() if annotation is bool)


_INPUT_BOOL_FIELDS = _bool_fields_for(
    LiveOrderRealOneShotPostReadyGateControlledInput,
)
_RESULT_BOOL_FIELDS = _bool_fields_for(
    LiveOrderRealOneShotPostReadyGateControlledResult,
)
