"""Step 6G final confirmation gate controlled contract.

This module models the final confirmation boundary after a fresh preflight PASS.
It accepts only safe booleans and labels. It does not accept, store, render, or
log the confirmation phrase actual value. It does not call APIs, execute HTTP
POST, call order endpoints, call live_order_once, update ledgers, persist
attempt counters, receive actual results, or hand off receipts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

FINAL_CONFIRMATION_GATE_RECOMMENDED_NEXT_STEP = (
    "final_confirmation_gate_retry_current_turn_confirmation_no_post"
)
SAFE_FINAL_CONFIRMATION_GATE_LABEL = "CONTROLLED_FINAL_CONFIRMATION_GATE"
UNSUPPORTED_FINAL_CONFIRMATION_GATE_LABEL = "UNSUPPORTED_REDACTED"


class LiveOrderRealFinalConfirmationGateControlledStatus(str, Enum):
    FINAL_CONFIRMATION_GATE_NOT_READY = "FINAL_CONFIRMATION_GATE_NOT_READY"
    FINAL_CONFIRMATION_GATE_READY_FOR_REQUEST_NO_POST = (
        "FINAL_CONFIRMATION_GATE_READY_FOR_REQUEST_NO_POST"
    )
    FINAL_CONFIRMATION_GATE_CONFIRMED_NO_POST = (
        "FINAL_CONFIRMATION_GATE_CONFIRMED_NO_POST"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_MISSING_FRESH_PREFLIGHT_PASS = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_MISSING_FRESH_PREFLIGHT_PASS"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_CURRENT_TURN = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_CURRENT_TURN"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_NEW = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_NEW"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_ONE_TIME = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_ONE_TIME"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_REUSED = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_REUSED"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_PREVIOUS_TURN_CONFIRMATION = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_PREVIOUS_TURN_CONFIRMATION"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_STEP4_APPROVAL_REUSE = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_STEP4_APPROVAL_REUSE"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_VALUE_EXPOSURE = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_VALUE_EXPOSURE"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_UNKNOWN = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_UNKNOWN"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_FAILED = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_FAILED"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_UNAVAILABLE = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_UNAVAILABLE"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_TIMEOUT = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_TIMEOUT"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_STALE = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_STALE"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_POST_ATTEMPTED = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_POST_ATTEMPTED"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_ORDER_ENDPOINT = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_ORDER_ENDPOINT"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_LIVE_ORDER_ONCE = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_LIVE_ORDER_ONCE"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_LEDGER_UPDATE = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_LEDGER_UPDATE"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_ACTUAL_RECEIPT = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_ACTUAL_RECEIPT"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_RAW_EXPOSURE = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_RAW_EXPOSURE"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_ID_EXPOSURE = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_ID_EXPOSURE"
    )
    FINAL_CONFIRMATION_GATE_BLOCKED_VALUE_EXPOSURE = (
        "FINAL_CONFIRMATION_GATE_BLOCKED_VALUE_EXPOSURE"
    )


class LiveOrderRealFinalConfirmationGateControlledMode(str, Enum):
    FINAL_CONFIRMATION_GATE_CONTROLLED_SAFE_CONFIRMATION_ONLY = (
        "FINAL_CONFIRMATION_GATE_CONTROLLED_SAFE_CONFIRMATION_ONLY"
    )


FinalConfirmationGateControlledStatus = (
    LiveOrderRealFinalConfirmationGateControlledStatus
)
FinalConfirmationGateControlledMode = (
    LiveOrderRealFinalConfirmationGateControlledMode
)


@dataclass(frozen=True)
class LiveOrderRealFinalConfirmationGateControlledInput:
    final_confirmation_gate_mode: str = (
        FinalConfirmationGateControlledMode
        .FINAL_CONFIRMATION_GATE_CONTROLLED_SAFE_CONFIRMATION_ONLY
        .value
    )
    final_confirmation_gate_requested: bool = True
    safe_final_confirmation_gate_label: str = SAFE_FINAL_CONFIRMATION_GATE_LABEL
    fresh_preflight_passed: bool = True
    fresh_preflight_current: bool = True
    fresh_preflight_new: bool = True
    fresh_preflight_reused: bool = False
    fresh_preflight_stale: bool = False
    fresh_preflight_unknown: bool = False
    fresh_preflight_timeout: bool = False
    fresh_preflight_unavailable: bool = False
    final_confirmation_required: bool = True
    final_confirmation_received: bool = False
    current_turn_explicit_user_reply_received: bool = False
    confirmation_current_turn: bool = False
    confirmation_new: bool = False
    confirmation_one_time: bool = False
    confirmation_reused: bool = False
    previous_turn_confirmation_reused: bool = False
    step4_approval_phrase_reused: bool = False
    prompt_used_as_confirmation: bool = False
    fresh_preflight_pass_report_used_as_confirmation: bool = False
    confirmation_actual_value_stored: bool = False
    confirmation_actual_value_reported: bool = False
    confirmation_actual_value_logged: bool = False
    confirmation_phrase_exposure_attempted: bool = False
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
    raw_request_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    request_body_exposure_attempted: bool = False
    response_body_exposure_attempted: bool = False
    broker_response_exposure_attempted: bool = False
    api_response_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    account_id_exposure_attempted: bool = False
    order_id_exposure_attempted: bool = False
    transaction_id_exposure_attempted: bool = False
    position_id_exposure_attempted: bool = False
    trade_id_exposure_attempted: bool = False
    real_id_exposure_attempted: bool = False
    ledger_state_exposure_attempted: bool = False
    approval_command_exposure_attempted: bool = False
    safe_to_render: bool = True
    safe_to_serialize: bool = True

    def __post_init__(self) -> None:
        _require_non_empty(
            "final_confirmation_gate_mode",
            self.final_confirmation_gate_mode,
        )
        _require_non_empty(
            "safe_final_confirmation_gate_label",
            self.safe_final_confirmation_gate_label,
        )
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class LiveOrderRealFinalConfirmationGateControlledResult:
    status: LiveOrderRealFinalConfirmationGateControlledStatus
    final_confirmation_gate_ready: bool
    final_confirmation_gate_confirmed: bool
    final_confirmation_gate_mode: str
    safe_final_confirmation_gate_label: str
    safe_final_confirmation_gate_status: str
    fresh_preflight_pass_required: bool
    fresh_preflight_passed: bool
    fresh_preflight_current: bool
    fresh_preflight_new: bool
    fresh_preflight_reused: bool
    fresh_preflight_stale: bool
    fresh_preflight_unknown: bool
    fresh_preflight_timeout: bool
    fresh_preflight_unavailable: bool
    final_confirmation_required: bool
    final_confirmation_received: bool
    current_turn_explicit_user_reply_received: bool
    confirmation_current_turn: bool
    confirmation_new: bool
    confirmation_one_time: bool
    confirmation_reused: bool
    previous_turn_confirmation_reused: bool
    step4_approval_phrase_reused: bool
    prompt_used_as_confirmation: bool
    fresh_preflight_pass_report_used_as_confirmation: bool
    confirmation_actual_value_stored: bool
    confirmation_actual_value_reported: bool
    confirmation_actual_value_logged: bool
    confirmation_phrase_exposure_attempted: bool
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
    raw_request_exposure_attempted: bool
    raw_response_exposure_attempted: bool
    broker_response_exposure_attempted: bool
    api_response_exposure_attempted: bool
    credential_value_exposure_attempted: bool
    signature_value_exposure_attempted: bool
    headers_value_exposure_attempted: bool
    real_id_exposure_attempted: bool
    safe_to_render: bool
    safe_to_serialize: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            LiveOrderRealFinalConfirmationGateControlledStatus,
        ):
            raise LiveVerificationValidationError(
                "status must be final confirmation gate controlled status",
            )
        _require_non_empty(
            "final_confirmation_gate_mode",
            self.final_confirmation_gate_mode,
        )
        _require_non_empty(
            "safe_final_confirmation_gate_label",
            self.safe_final_confirmation_gate_label,
        )
        _require_non_empty(
            "safe_final_confirmation_gate_status",
            self.safe_final_confirmation_gate_status,
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        _validate_result_safety(self)


def build_live_order_real_final_confirmation_gate_controlled(
    *,
    input_snapshot: LiveOrderRealFinalConfirmationGateControlledInput | None = None,
) -> LiveOrderRealFinalConfirmationGateControlledResult:
    """Build a safe final confirmation gate result with no side effects."""
    snapshot = input_snapshot or LiveOrderRealFinalConfirmationGateControlledInput()
    status, primary_reasons = _status_from_input(snapshot)
    confirmed = (
        status
        is (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_CONFIRMED_NO_POST
        )
    )
    ready = status in {
        (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_READY_FOR_REQUEST_NO_POST
        ),
        (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_CONFIRMED_NO_POST
        ),
    }
    safe_mode = (
        snapshot.final_confirmation_gate_mode
        if snapshot.final_confirmation_gate_mode
        == (
            FinalConfirmationGateControlledMode
            .FINAL_CONFIRMATION_GATE_CONTROLLED_SAFE_CONFIRMATION_ONLY
            .value
        )
        else UNSUPPORTED_FINAL_CONFIRMATION_GATE_LABEL
    )
    safe_label = (
        snapshot.safe_final_confirmation_gate_label
        if snapshot.safe_final_confirmation_gate_label
        == SAFE_FINAL_CONFIRMATION_GATE_LABEL
        else UNSUPPORTED_FINAL_CONFIRMATION_GATE_LABEL
    )
    return LiveOrderRealFinalConfirmationGateControlledResult(
        status=status,
        final_confirmation_gate_ready=ready,
        final_confirmation_gate_confirmed=confirmed,
        final_confirmation_gate_mode=safe_mode,
        safe_final_confirmation_gate_label=safe_label,
        safe_final_confirmation_gate_status=status.value,
        fresh_preflight_pass_required=True,
        fresh_preflight_passed=snapshot.fresh_preflight_passed,
        fresh_preflight_current=snapshot.fresh_preflight_current,
        fresh_preflight_new=snapshot.fresh_preflight_new,
        fresh_preflight_reused=snapshot.fresh_preflight_reused,
        fresh_preflight_stale=snapshot.fresh_preflight_stale,
        fresh_preflight_unknown=snapshot.fresh_preflight_unknown,
        fresh_preflight_timeout=snapshot.fresh_preflight_timeout,
        fresh_preflight_unavailable=snapshot.fresh_preflight_unavailable,
        final_confirmation_required=snapshot.final_confirmation_required,
        final_confirmation_received=confirmed,
        current_turn_explicit_user_reply_received=(
            snapshot.current_turn_explicit_user_reply_received
        ),
        confirmation_current_turn=confirmed and snapshot.confirmation_current_turn,
        confirmation_new=confirmed and snapshot.confirmation_new,
        confirmation_one_time=confirmed and snapshot.confirmation_one_time,
        confirmation_reused=False,
        previous_turn_confirmation_reused=False,
        step4_approval_phrase_reused=False,
        prompt_used_as_confirmation=False,
        fresh_preflight_pass_report_used_as_confirmation=False,
        confirmation_actual_value_stored=False,
        confirmation_actual_value_reported=False,
        confirmation_actual_value_logged=False,
        confirmation_phrase_exposure_attempted=False,
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
        raw_request_exposure_attempted=False,
        raw_response_exposure_attempted=False,
        broker_response_exposure_attempted=False,
        api_response_exposure_attempted=False,
        credential_value_exposure_attempted=False,
        signature_value_exposure_attempted=False,
        headers_value_exposure_attempted=False,
        real_id_exposure_attempted=False,
        safe_to_render=True,
        safe_to_serialize=True,
        blocked_reasons=_blocked_reasons(
            snapshot=snapshot,
            primary_reasons=primary_reasons,
        ),
        recommended_next_step=(
            "one_shot_post_ready_gate_no_post"
            if confirmed
            else FINAL_CONFIRMATION_GATE_RECOMMENDED_NEXT_STEP
        ),
    )


def render_live_order_real_final_confirmation_gate_controlled_markdown(
    result: LiveOrderRealFinalConfirmationGateControlledResult,
) -> str:
    """Render a safe final confirmation gate summary only."""
    lines = [
        "# Step 6G Final Confirmation Gate Controlled",
        "",
        "This is a final confirmation gate summary only.",
        "It contains safe labels, statuses, booleans, and blocked reason labels.",
        "It does not expose confirmation phrase actual values.",
        "It does not execute HTTP POST.",
        "It does not call order endpoints.",
        "It does not call live_order_once.",
        "It does not update ledgers or persist attempt counters.",
        "It does not receive actual results or hand off receipts.",
        "Final confirmation confirmed here does not allow POST in this step.",
        "",
        "## Status",
        f"- status: {result.status.value}",
        (
            "- final_confirmation_gate_ready: "
            f"{_bool_text(result.final_confirmation_gate_ready)}"
        ),
        (
            "- final_confirmation_gate_confirmed: "
            f"{_bool_text(result.final_confirmation_gate_confirmed)}"
        ),
        f"- final_confirmation_gate_mode: {result.final_confirmation_gate_mode}",
        (
            "- safe_final_confirmation_gate_label: "
            f"{result.safe_final_confirmation_gate_label}"
        ),
        (
            "- safe_final_confirmation_gate_status: "
            f"{result.safe_final_confirmation_gate_status}"
        ),
        "",
        "## Fresh Preflight Prerequisite",
        f"- fresh_preflight_passed: {_bool_text(result.fresh_preflight_passed)}",
        f"- fresh_preflight_current: {_bool_text(result.fresh_preflight_current)}",
        f"- fresh_preflight_new: {_bool_text(result.fresh_preflight_new)}",
        f"- fresh_preflight_reused: {_bool_text(result.fresh_preflight_reused)}",
        f"- fresh_preflight_stale: {_bool_text(result.fresh_preflight_stale)}",
        "",
        "## Confirmation",
        (
            "- final_confirmation_required: "
            f"{_bool_text(result.final_confirmation_required)}"
        ),
        (
            "- final_confirmation_received: "
            f"{_bool_text(result.final_confirmation_received)}"
        ),
        (
            "- current_turn_explicit_user_reply_received: "
            f"{_bool_text(result.current_turn_explicit_user_reply_received)}"
        ),
        (
            "- confirmation_current_turn: "
            f"{_bool_text(result.confirmation_current_turn)}"
        ),
        f"- confirmation_new: {_bool_text(result.confirmation_new)}",
        f"- confirmation_one_time: {_bool_text(result.confirmation_one_time)}",
        f"- confirmation_reused: {_bool_text(result.confirmation_reused)}",
        (
            "- previous_turn_confirmation_reused: "
            f"{_bool_text(result.previous_turn_confirmation_reused)}"
        ),
        (
            "- step4_approval_phrase_reused: "
            f"{_bool_text(result.step4_approval_phrase_reused)}"
        ),
        (
            "- confirmation_actual_value_stored: "
            f"{_bool_text(result.confirmation_actual_value_stored)}"
        ),
        (
            "- confirmation_actual_value_reported: "
            f"{_bool_text(result.confirmation_actual_value_reported)}"
        ),
        (
            "- confirmation_actual_value_logged: "
            f"{_bool_text(result.confirmation_actual_value_logged)}"
        ),
        "",
        "## Non-Execution",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
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


def _status_from_input(
    snapshot: LiveOrderRealFinalConfirmationGateControlledInput,
) -> tuple[LiveOrderRealFinalConfirmationGateControlledStatus, tuple[str, ...]]:
    if (
        snapshot.final_confirmation_gate_mode
        != (
            FinalConfirmationGateControlledMode
            .FINAL_CONFIRMATION_GATE_CONTROLLED_SAFE_CONFIRMATION_ONLY
            .value
        )
    ):
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_UNKNOWN,
            ("unsupported_final_confirmation_gate_mode",),
        )
    if not snapshot.final_confirmation_gate_requested:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_NOT_READY,
            ("final_confirmation_gate_not_requested",),
        )
    if snapshot.fresh_preflight_unknown:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_UNKNOWN,
            ("fresh_preflight_unknown",),
        )
    if snapshot.fresh_preflight_timeout:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_TIMEOUT,
            ("fresh_preflight_timeout",),
        )
    if snapshot.fresh_preflight_unavailable:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_UNAVAILABLE,
            ("fresh_preflight_unavailable",),
        )
    if snapshot.fresh_preflight_stale:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_STALE,
            ("fresh_preflight_stale",),
        )
    if (
        not snapshot.fresh_preflight_passed
        or not snapshot.fresh_preflight_current
        or not snapshot.fresh_preflight_new
        or snapshot.fresh_preflight_reused
    ):
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_MISSING_FRESH_PREFLIGHT_PASS,
            ("fresh_preflight_pass_current_new_non_reused_missing",),
        )
    if not snapshot.final_confirmation_required:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_NOT_READY,
            ("final_confirmation_not_required",),
        )
    unsafe_status = _unsafe_status(snapshot)
    if unsafe_status is not None:
        return unsafe_status
    if not snapshot.final_confirmation_received:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_READY_FOR_REQUEST_NO_POST,
            (),
        )
    if not snapshot.current_turn_explicit_user_reply_received:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_CURRENT_TURN,
            ("current_turn_explicit_user_reply_missing",),
        )
    if not snapshot.confirmation_current_turn:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_CURRENT_TURN,
            ("confirmation_not_current_turn",),
        )
    if not snapshot.confirmation_new:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_NEW,
            ("confirmation_not_new",),
        )
    if not snapshot.confirmation_one_time:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_ONE_TIME,
            ("confirmation_not_one_time",),
        )
    return (
        FinalConfirmationGateControlledStatus
        .FINAL_CONFIRMATION_GATE_CONFIRMED_NO_POST,
        (),
    )


def _unsafe_status(
    snapshot: LiveOrderRealFinalConfirmationGateControlledInput,
) -> tuple[LiveOrderRealFinalConfirmationGateControlledStatus, tuple[str, ...]] | None:
    if snapshot.confirmation_reused:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_REUSED,
            ("confirmation_reused",),
        )
    if snapshot.previous_turn_confirmation_reused:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_PREVIOUS_TURN_CONFIRMATION,
            ("previous_turn_confirmation_reused",),
        )
    if snapshot.step4_approval_phrase_reused:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_STEP4_APPROVAL_REUSE,
            ("step4_approval_phrase_reused",),
        )
    if (
        snapshot.prompt_used_as_confirmation
        or snapshot.fresh_preflight_pass_report_used_as_confirmation
        or snapshot.confirmation_actual_value_stored
        or snapshot.confirmation_actual_value_reported
        or snapshot.confirmation_actual_value_logged
        or snapshot.confirmation_phrase_exposure_attempted
    ):
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_VALUE_EXPOSURE,
            ("confirmation_value_or_invalid_source_attempted",),
        )
    if (
        snapshot.post_allowed_this_step
        or snapshot.post_executed
        or snapshot.http_post_executed
    ):
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_POST_ATTEMPTED,
            ("post_attempted_or_allowed",),
        )
    if snapshot.order_endpoint_called:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_ORDER_ENDPOINT,
            ("order_endpoint_called",),
        )
    if snapshot.live_order_once_called:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_LIVE_ORDER_ONCE,
            ("live_order_once_called",),
        )
    if (
        snapshot.ledger_update_allowed
        or snapshot.ledger_updated
        or snapshot.ledger_update_attempted
        or snapshot.attempt_counter_persistence_allowed
        or snapshot.attempt_counter_persisted
    ):
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_LEDGER_UPDATE,
            ("ledger_or_attempt_counter_attempted",),
        )
    if (
        snapshot.actual_result_receipt_received
        or snapshot.actual_receipt_handoff_executed
        or snapshot.actual_receipt_handoff_allowed
    ):
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_ACTUAL_RECEIPT,
            ("actual_receipt_or_handoff_attempted",),
        )
    if (
        snapshot.raw_request_exposure_attempted
        or snapshot.raw_response_exposure_attempted
        or snapshot.request_body_exposure_attempted
        or snapshot.response_body_exposure_attempted
        or snapshot.broker_response_exposure_attempted
        or snapshot.api_response_exposure_attempted
    ):
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_RAW_EXPOSURE,
            ("raw_or_broker_api_exposure_attempted",),
        )
    if (
        snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.position_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
        or snapshot.real_id_exposure_attempted
    ):
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_ID_EXPOSURE,
            ("identifier_exposure_attempted",),
        )
    if (
        snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
        or snapshot.ledger_state_exposure_attempted
        or snapshot.approval_command_exposure_attempted
    ):
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_VALUE_EXPOSURE,
            ("value_exposure_attempted",),
        )
    if not snapshot.safe_to_render or not snapshot.safe_to_serialize:
        return (
            FinalConfirmationGateControlledStatus
            .FINAL_CONFIRMATION_GATE_BLOCKED_VALUE_EXPOSURE,
            ("render_or_serialize_not_safe",),
        )
    return None


def _blocked_reasons(
    *,
    snapshot: LiveOrderRealFinalConfirmationGateControlledInput,
    primary_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    reasons = list(primary_reasons)
    if snapshot.safe_final_confirmation_gate_label != SAFE_FINAL_CONFIRMATION_GATE_LABEL:
        reasons.append("safe_final_confirmation_gate_label_invalid")
    return _dedupe(reasons)


def _validate_result_safety(
    result: LiveOrderRealFinalConfirmationGateControlledResult,
) -> None:
    if result.post_allowed_this_step or result.post_executed:
        raise LiveVerificationValidationError("final confirmation gate must not POST")
    if result.http_post_executed or result.order_endpoint_called:
        raise LiveVerificationValidationError("order execution must remain false")
    if result.live_order_once_called:
        raise LiveVerificationValidationError("live_order_once must remain false")
    if result.ledger_updated or result.attempt_counter_persisted:
        raise LiveVerificationValidationError("ledger and attempt state must not change")
    if (
        result.actual_result_receipt_received
        or result.actual_receipt_handoff_executed
        or result.actual_receipt_handoff_allowed
    ):
        raise LiveVerificationValidationError("actual receipt must not be handled")
    if (
        result.confirmation_actual_value_stored
        or result.confirmation_actual_value_reported
        or result.confirmation_actual_value_logged
    ):
        raise LiveVerificationValidationError("confirmation actual value must not surface")
    if result.confirmation_reused or result.previous_turn_confirmation_reused:
        raise LiveVerificationValidationError("confirmation reuse must remain false")
    if result.step4_approval_phrase_reused:
        raise LiveVerificationValidationError("Step 4 approval reuse must remain false")
    if (
        result.raw_request_exposure_attempted
        or result.raw_response_exposure_attempted
        or result.broker_response_exposure_attempted
        or result.api_response_exposure_attempted
        or result.real_id_exposure_attempted
        or result.credential_value_exposure_attempted
        or result.signature_value_exposure_attempted
        or result.headers_value_exposure_attempted
    ):
        raise LiveVerificationValidationError("unsafe exposure must remain false")


def _require_non_empty(name: str, value: str) -> None:
    if not value:
        raise LiveVerificationValidationError(f"{name} must be non-empty")


def _validate_bool_fields(instance: object, fields: tuple[str, ...]) -> None:
    for field_name in fields:
        if type(getattr(instance, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _dedupe(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


_INPUT_BOOL_FIELDS = (
    "final_confirmation_gate_requested",
    "fresh_preflight_passed",
    "fresh_preflight_current",
    "fresh_preflight_new",
    "fresh_preflight_reused",
    "fresh_preflight_stale",
    "fresh_preflight_unknown",
    "fresh_preflight_timeout",
    "fresh_preflight_unavailable",
    "final_confirmation_required",
    "final_confirmation_received",
    "current_turn_explicit_user_reply_received",
    "confirmation_current_turn",
    "confirmation_new",
    "confirmation_one_time",
    "confirmation_reused",
    "previous_turn_confirmation_reused",
    "step4_approval_phrase_reused",
    "prompt_used_as_confirmation",
    "fresh_preflight_pass_report_used_as_confirmation",
    "confirmation_actual_value_stored",
    "confirmation_actual_value_reported",
    "confirmation_actual_value_logged",
    "confirmation_phrase_exposure_attempted",
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
    "raw_request_exposure_attempted",
    "raw_response_exposure_attempted",
    "request_body_exposure_attempted",
    "response_body_exposure_attempted",
    "broker_response_exposure_attempted",
    "api_response_exposure_attempted",
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
    "account_id_exposure_attempted",
    "order_id_exposure_attempted",
    "transaction_id_exposure_attempted",
    "position_id_exposure_attempted",
    "trade_id_exposure_attempted",
    "real_id_exposure_attempted",
    "ledger_state_exposure_attempted",
    "approval_command_exposure_attempted",
    "safe_to_render",
    "safe_to_serialize",
)

_RESULT_BOOL_FIELDS = (
    "final_confirmation_gate_ready",
    "final_confirmation_gate_confirmed",
    "fresh_preflight_pass_required",
    "fresh_preflight_passed",
    "fresh_preflight_current",
    "fresh_preflight_new",
    "fresh_preflight_reused",
    "fresh_preflight_stale",
    "fresh_preflight_unknown",
    "fresh_preflight_timeout",
    "fresh_preflight_unavailable",
    "final_confirmation_required",
    "final_confirmation_received",
    "current_turn_explicit_user_reply_received",
    "confirmation_current_turn",
    "confirmation_new",
    "confirmation_one_time",
    "confirmation_reused",
    "previous_turn_confirmation_reused",
    "step4_approval_phrase_reused",
    "prompt_used_as_confirmation",
    "fresh_preflight_pass_report_used_as_confirmation",
    "confirmation_actual_value_stored",
    "confirmation_actual_value_reported",
    "confirmation_actual_value_logged",
    "confirmation_phrase_exposure_attempted",
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
    "raw_request_exposure_attempted",
    "raw_response_exposure_attempted",
    "broker_response_exposure_attempted",
    "api_response_exposure_attempted",
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
    "real_id_exposure_attempted",
    "safe_to_render",
    "safe_to_serialize",
)

__all__ = [
    "FINAL_CONFIRMATION_GATE_RECOMMENDED_NEXT_STEP",
    "SAFE_FINAL_CONFIRMATION_GATE_LABEL",
    "FinalConfirmationGateControlledMode",
    "FinalConfirmationGateControlledStatus",
    "LiveOrderRealFinalConfirmationGateControlledInput",
    "LiveOrderRealFinalConfirmationGateControlledMode",
    "LiveOrderRealFinalConfirmationGateControlledResult",
    "LiveOrderRealFinalConfirmationGateControlledStatus",
    "build_live_order_real_final_confirmation_gate_controlled",
    "render_live_order_real_final_confirmation_gate_controlled_markdown",
]
