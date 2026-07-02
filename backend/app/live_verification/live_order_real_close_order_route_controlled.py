"""Step 6G close order route controlled foundation.

This module builds a close-planning summary from safe position status/count only.
It does not import broker/private API clients, HTTP clients, env readers, order
endpoints, live_order_once, ledger writers, or receipt handoff code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledResult,
    PositionReadOnlyControlledStatus,
    build_position_read_only_controlled,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

SAFE_CLOSE_ORDER_ROUTE_LABEL = "STEP6G_CLOSE_ORDER_ROUTE_CONTROLLED_NO_POST"
SAFE_SEALED_CLOSE_INSTRUCTION_LABEL = "STEP6G_SEALED_CLOSE_INSTRUCTION_SAFE"
SAFE_CLOSE_EXECUTION_READINESS_LABEL = "STEP6G_CLOSE_EXECUTION_READINESS_PLANNING_ONLY"
SAFE_CLOSE_ENVIRONMENT_LABEL = "STEP6G_CLOSE_ROUTE_NO_POST"
SAFE_CLOSE_RISK_LABEL = "STEP6G_CLOSE_100_UNITS_ONE_POSITION_ONLY"
CLOSE_ORDER_TYPE_SAFE_LABEL = "MARKET"
CLOSE_SIDE_SAFE_LABEL = "OPPOSITE_OF_SAFE_POSITION_SIDE"
CLOSE_ROUTE_RECOMMENDED_NEXT_STEP = "step6g_position_runtime_safe_read_check_no_post"


class CloseOrderRouteControlledStatus(str, Enum):
    READY = "CLOSE_ORDER_ROUTE_PLANNING_READY_NO_POST"
    BLOCKED = "CLOSE_ORDER_ROUTE_BLOCKED"


@dataclass(frozen=True)
class CloseOrderRouteControlledInput:
    position_status: PositionReadOnlyControlledStatus = (
        PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    )
    position_status_checked: bool = False
    position_count_safe: int = 0
    max_open_positions: int = 1
    close_units: int = SUPPORTED_UNITS
    close_symbol_safe_label: str = SUPPORTED_SYMBOL
    close_side_safe_label: str = CLOSE_SIDE_SAFE_LABEL
    close_order_type_safe_label: str = CLOSE_ORDER_TYPE_SAFE_LABEL
    raw_position_exposure_attempted: bool = False
    raw_request_exposure_attempted: bool = False
    raw_response_exposure_attempted: bool = False
    broker_api_response_exposure_attempted: bool = False
    position_id_exposure_attempted: bool = False
    account_id_exposure_attempted: bool = False
    order_id_exposure_attempted: bool = False
    transaction_id_exposure_attempted: bool = False
    trade_id_exposure_attempted: bool = False
    client_order_id_actual_value_exposure_attempted: bool = False
    position_value_exposure_attempted: bool = False
    credential_value_exposure_attempted: bool = False
    signature_value_exposure_attempted: bool = False
    headers_value_exposure_attempted: bool = False
    actual_http_post_attempted: bool = False
    close_post_attempted: bool = False
    retry_or_repost_attempted: bool = False
    ledger_update_attempted: bool = False
    receipt_handoff_attempted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError("position_status must be controlled enum")
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("max_open_positions", self.max_open_positions)
        _validate_non_negative_int("close_units", self.close_units)
        _require_non_empty("close_symbol_safe_label", self.close_symbol_safe_label)
        _require_non_empty("close_side_safe_label", self.close_side_safe_label)
        _require_non_empty("close_order_type_safe_label", self.close_order_type_safe_label)
        _validate_bool_fields(self, _CLOSE_ROUTE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class SealedCloseInstructionSummary:
    sealed_close_instruction_ready: bool
    safe_sealed_close_instruction_label: str
    safe_symbol_label: str
    safe_side_label: str
    safe_units_label: int
    safe_order_type_label: str
    position_handle_value_exposed: bool
    position_id_exposed: bool
    raw_position_exposed: bool
    raw_request_exposed: bool
    raw_response_exposed: bool
    broker_api_response_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool

    def __post_init__(self) -> None:
        _require_non_empty(
            "safe_sealed_close_instruction_label",
            self.safe_sealed_close_instruction_label,
        )
        _require_non_empty("safe_symbol_label", self.safe_symbol_label)
        _require_non_empty("safe_side_label", self.safe_side_label)
        _require_non_empty("safe_order_type_label", self.safe_order_type_label)
        _validate_non_negative_int("safe_units_label", self.safe_units_label)
        _validate_bool_fields(self, _SEALED_INSTRUCTION_BOOL_FIELDS)


@dataclass(frozen=True)
class CloseExecutionReadinessSummary:
    close_execution_step_may_be_planned: bool
    safe_close_execution_readiness_label: str
    close_execution_requires_new_confirmation: bool
    close_execution_requires_time_market_operator_gate: bool
    close_execution_requires_position_status_current: bool
    close_execution_requires_exactly_one_position: bool
    close_execution_requires_no_retry: bool
    close_execution_requires_no_second_post: bool
    close_execution_requires_raw_id_exposure_false: bool
    close_execution_permission_granted_now: bool

    def __post_init__(self) -> None:
        _require_non_empty(
            "safe_close_execution_readiness_label",
            self.safe_close_execution_readiness_label,
        )
        _validate_bool_fields(self, _CLOSE_EXECUTION_READINESS_BOOL_FIELDS)


@dataclass(frozen=True)
class CloseOrderRouteControlledResult:
    status: CloseOrderRouteControlledStatus
    close_route_ready: bool
    close_planning_allowed: bool
    close_execution_allowed_now: bool
    close_post_executed: bool
    close_post_count: int
    close_retry_allowed: bool
    close_repost_allowed: bool
    close_second_post_allowed: bool
    safe_close_route_label: str
    requires_position_status: bool
    requires_exactly_one_position: bool
    requires_position_unknown_blocked: bool
    requires_no_position_blocked: bool
    requires_multiple_positions_blocked: bool
    close_units_fixed: int
    close_symbol_safe_label: str
    close_side_safe_label: str
    close_order_type_safe_label: str
    close_environment_label: str
    close_risk_label: str
    sealed_close_instruction: SealedCloseInstructionSummary
    close_execution_readiness: CloseExecutionReadinessSummary
    raw_position_exposed: bool
    raw_request_exposed: bool
    raw_response_exposed: bool
    broker_api_response_exposed: bool
    position_id_exposed: bool
    account_id_exposed: bool
    order_id_exposed: bool
    transaction_id_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool
    actual_http_post_executed: bool
    retry_attempted: bool
    second_post_attempted: bool
    ledger_updated: bool
    receipt_handoff_executed: bool
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, CloseOrderRouteControlledStatus):
            raise LiveVerificationValidationError("status must be close route enum")
        _require_non_empty("safe_close_route_label", self.safe_close_route_label)
        _require_non_empty("close_symbol_safe_label", self.close_symbol_safe_label)
        _require_non_empty("close_side_safe_label", self.close_side_safe_label)
        _require_non_empty("close_order_type_safe_label", self.close_order_type_safe_label)
        _require_non_empty("close_environment_label", self.close_environment_label)
        _require_non_empty("close_risk_label", self.close_risk_label)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_non_negative_int("close_post_count", self.close_post_count)
        _validate_non_negative_int("close_units_fixed", self.close_units_fixed)
        _validate_bool_fields(self, _CLOSE_ROUTE_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_close_order_route_controlled(
    input_snapshot: CloseOrderRouteControlledInput | None = None,
    *,
    position_result: PositionReadOnlyControlledResult | None = None,
) -> CloseOrderRouteControlledResult:
    snapshot = input_snapshot or _input_from_position_result(
        position_result or build_position_read_only_controlled(),
    )
    reasons = _blocked_reasons(snapshot)
    ready = not reasons
    instruction = _sealed_instruction(snapshot, ready)
    readiness = CloseExecutionReadinessSummary(
        close_execution_step_may_be_planned=ready,
        safe_close_execution_readiness_label=SAFE_CLOSE_EXECUTION_READINESS_LABEL,
        close_execution_requires_new_confirmation=True,
        close_execution_requires_time_market_operator_gate=True,
        close_execution_requires_position_status_current=True,
        close_execution_requires_exactly_one_position=True,
        close_execution_requires_no_retry=True,
        close_execution_requires_no_second_post=True,
        close_execution_requires_raw_id_exposure_false=True,
        close_execution_permission_granted_now=False,
    )
    return CloseOrderRouteControlledResult(
        status=(
            CloseOrderRouteControlledStatus.READY
            if ready
            else CloseOrderRouteControlledStatus.BLOCKED
        ),
        close_route_ready=ready,
        close_planning_allowed=ready,
        close_execution_allowed_now=False,
        close_post_executed=False,
        close_post_count=0,
        close_retry_allowed=False,
        close_repost_allowed=False,
        close_second_post_allowed=False,
        safe_close_route_label=SAFE_CLOSE_ORDER_ROUTE_LABEL,
        requires_position_status=True,
        requires_exactly_one_position=True,
        requires_position_unknown_blocked=True,
        requires_no_position_blocked=True,
        requires_multiple_positions_blocked=True,
        close_units_fixed=SUPPORTED_UNITS,
        close_symbol_safe_label=snapshot.close_symbol_safe_label,
        close_side_safe_label=snapshot.close_side_safe_label,
        close_order_type_safe_label=CLOSE_ORDER_TYPE_SAFE_LABEL,
        close_environment_label=SAFE_CLOSE_ENVIRONMENT_LABEL,
        close_risk_label=SAFE_CLOSE_RISK_LABEL,
        sealed_close_instruction=instruction,
        close_execution_readiness=readiness,
        raw_position_exposed=False,
        raw_request_exposed=False,
        raw_response_exposed=False,
        broker_api_response_exposed=False,
        position_id_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
        actual_http_post_executed=False,
        retry_attempted=False,
        second_post_attempted=False,
        ledger_updated=False,
        receipt_handoff_executed=False,
        recommended_next_step=CLOSE_ROUTE_RECOMMENDED_NEXT_STEP,
        blocked_reasons=reasons,
    )


def render_close_order_route_controlled_markdown(
    result: CloseOrderRouteControlledResult,
) -> str:
    """Render a safe close route planning summary only."""
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Close Order Route Controlled",
            "",
            "This route renders close planning only.",
            "It does not execute actual close POST or entry POST.",
            "It does not expose raw position data, request/response data,",
            "broker/API responses, IDs, credential values, signature values,",
            "or headers values.",
            "",
            f"close_route_ready: {_bool_text(result.close_route_ready)}",
            f"close_planning_allowed: {_bool_text(result.close_planning_allowed)}",
            (
                "close_execution_allowed_now: "
                f"{_bool_text(result.close_execution_allowed_now)}"
            ),
            f"close_post_executed: {_bool_text(result.close_post_executed)}",
            f"close_post_count: {result.close_post_count}",
            f"close_retry_allowed: {_bool_text(result.close_retry_allowed)}",
            f"close_repost_allowed: {_bool_text(result.close_repost_allowed)}",
            (
                "close_second_post_allowed: "
                f"{_bool_text(result.close_second_post_allowed)}"
            ),
            f"requires_position_status: {_bool_text(result.requires_position_status)}",
            (
                "requires_exactly_one_position: "
                f"{_bool_text(result.requires_exactly_one_position)}"
            ),
            f"close_units_fixed: {result.close_units_fixed}",
            f"close_symbol_safe_label: {result.close_symbol_safe_label}",
            f"close_side_safe_label: {result.close_side_safe_label}",
            f"close_order_type_safe_label: {result.close_order_type_safe_label}",
            (
                "sealed_close_instruction_ready: "
                f"{_bool_text(result.sealed_close_instruction.sealed_close_instruction_ready)}"
            ),
            (
                "close_execution_step_may_be_planned: "
                f"{_bool_text(result.close_execution_readiness.close_execution_step_may_be_planned)}"
            ),
            f"raw_position_exposed: {_bool_text(result.raw_position_exposed)}",
            f"position_id_exposed: {_bool_text(result.position_id_exposed)}",
            f"account_id_exposed: {_bool_text(result.account_id_exposed)}",
            f"order_id_exposed: {_bool_text(result.order_id_exposed)}",
            f"transaction_id_exposed: {_bool_text(result.transaction_id_exposed)}",
            f"actual_http_post_executed: {_bool_text(result.actual_http_post_executed)}",
            f"retry_attempted: {_bool_text(result.retry_attempted)}",
            f"second_post_attempted: {_bool_text(result.second_post_attempted)}",
            f"ledger_updated: {_bool_text(result.ledger_updated)}",
            f"receipt_handoff_executed: {_bool_text(result.receipt_handoff_executed)}",
            f"blocked_reasons: {blocked}",
            f"recommended_next_step: {result.recommended_next_step}",
        )
    ) + "\n"


def _input_from_position_result(
    result: PositionReadOnlyControlledResult,
) -> CloseOrderRouteControlledInput:
    return CloseOrderRouteControlledInput(
        position_status=result.position_status,
        position_status_checked=result.position_status_checked,
        position_count_safe=result.position_count_safe,
        max_open_positions=result.max_open_positions,
        raw_position_exposure_attempted=result.raw_position_exposed,
        broker_api_response_exposure_attempted=result.broker_api_response_exposed,
        position_id_exposure_attempted=result.position_id_exposed,
        account_id_exposure_attempted=result.account_id_exposed,
        order_id_exposure_attempted=result.order_id_exposed,
        transaction_id_exposure_attempted=result.transaction_id_exposed,
        credential_value_exposure_attempted=result.credential_value_exposed,
        signature_value_exposure_attempted=result.signature_value_exposed,
        headers_value_exposure_attempted=result.headers_value_exposed,
        actual_http_post_attempted=result.actual_http_post_executed,
        close_post_attempted=result.close_post_executed,
        retry_or_repost_attempted=result.retry_attempted,
        ledger_update_attempted=result.ledger_updated,
        receipt_handoff_attempted=result.receipt_handoff_executed,
    )


def _sealed_instruction(
    snapshot: CloseOrderRouteControlledInput,
    ready: bool,
) -> SealedCloseInstructionSummary:
    return SealedCloseInstructionSummary(
        sealed_close_instruction_ready=ready,
        safe_sealed_close_instruction_label=SAFE_SEALED_CLOSE_INSTRUCTION_LABEL,
        safe_symbol_label=snapshot.close_symbol_safe_label,
        safe_side_label=snapshot.close_side_safe_label,
        safe_units_label=SUPPORTED_UNITS,
        safe_order_type_label=CLOSE_ORDER_TYPE_SAFE_LABEL,
        position_handle_value_exposed=False,
        position_id_exposed=False,
        raw_position_exposed=False,
        raw_request_exposed=False,
        raw_response_exposed=False,
        broker_api_response_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
    )


def _blocked_reasons(snapshot: CloseOrderRouteControlledInput) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.max_open_positions != 1:
        reasons.append("max_open_positions_must_be_1")
    if snapshot.position_status is PositionReadOnlyControlledStatus.NO_POSITION:
        reasons.append("no_position")
    elif snapshot.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        if not snapshot.position_status_checked:
            reasons.append("position_status_not_checked")
        if snapshot.position_count_safe != 1:
            reasons.append("requires_exactly_one_position")
    elif snapshot.position_status is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED:
        reasons.append("multiple_positions_blocked")
    elif snapshot.position_status is PositionReadOnlyControlledStatus.SOURCE_MISSING_BLOCKED:
        reasons.append("position_source_missing")
    elif snapshot.position_status is PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED:
        reasons.append("position_unknown")
    elif snapshot.position_status is PositionReadOnlyControlledStatus.RAW_EXPOSURE_BLOCKED:
        reasons.append("raw_exposure_blocked")
    elif snapshot.position_status is PositionReadOnlyControlledStatus.ID_EXPOSURE_BLOCKED:
        reasons.append("id_exposure_blocked")
    elif snapshot.position_status is PositionReadOnlyControlledStatus.VALUE_EXPOSURE_BLOCKED:
        reasons.append("value_exposure_blocked")
    elif (
        snapshot.position_status
        is PositionReadOnlyControlledStatus.CREDENTIAL_UNAVAILABLE_BLOCKED
    ):
        reasons.append("credential_or_header_exposure_blocked")
    if snapshot.close_units != SUPPORTED_UNITS:
        reasons.append("close_units_must_be_100")
    if snapshot.close_symbol_safe_label != SUPPORTED_SYMBOL:
        reasons.append("close_symbol_safe_label_must_match_supported_symbol")
    if snapshot.close_order_type_safe_label != CLOSE_ORDER_TYPE_SAFE_LABEL:
        reasons.append("close_order_type_must_be_market")
    if _raw_exposure_attempted(snapshot):
        reasons.append("raw_exposure_blocked")
    if _id_exposure_attempted(snapshot):
        reasons.append("id_exposure_blocked")
    if _value_exposure_attempted(snapshot):
        reasons.append("value_exposure_blocked")
    if _credential_exposure_attempted(snapshot):
        reasons.append("credential_or_header_exposure_blocked")
    for field_name in (
        "actual_http_post_attempted",
        "close_post_attempted",
        "retry_or_repost_attempted",
        "ledger_update_attempted",
        "receipt_handoff_attempted",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(dict.fromkeys(reasons))


def _raw_exposure_attempted(snapshot: CloseOrderRouteControlledInput) -> bool:
    return (
        snapshot.raw_position_exposure_attempted
        or snapshot.raw_request_exposure_attempted
        or snapshot.raw_response_exposure_attempted
        or snapshot.broker_api_response_exposure_attempted
    )


def _id_exposure_attempted(snapshot: CloseOrderRouteControlledInput) -> bool:
    return (
        snapshot.position_id_exposure_attempted
        or snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
        or snapshot.client_order_id_actual_value_exposure_attempted
    )


def _value_exposure_attempted(snapshot: CloseOrderRouteControlledInput) -> bool:
    return snapshot.position_value_exposure_attempted


def _credential_exposure_attempted(snapshot: CloseOrderRouteControlledInput) -> bool:
    return (
        snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
    )


def _validate_non_negative_int(name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{name} must be a non-negative int")


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{name} must be non-empty")


def _validate_bool_fields(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        if type(getattr(instance, name)) is not bool:
            raise LiveVerificationValidationError(f"{name} must be bool")


def _validate_blocked_reasons(reasons: tuple[str, ...]) -> None:
    if not isinstance(reasons, tuple):
        raise LiveVerificationValidationError("blocked_reasons must be tuple")
    for reason in reasons:
        _require_non_empty("blocked_reason", reason)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


_CLOSE_ROUTE_INPUT_BOOL_FIELDS = (
    "position_status_checked",
    "raw_position_exposure_attempted",
    "raw_request_exposure_attempted",
    "raw_response_exposure_attempted",
    "broker_api_response_exposure_attempted",
    "position_id_exposure_attempted",
    "account_id_exposure_attempted",
    "order_id_exposure_attempted",
    "transaction_id_exposure_attempted",
    "trade_id_exposure_attempted",
    "client_order_id_actual_value_exposure_attempted",
    "position_value_exposure_attempted",
    "credential_value_exposure_attempted",
    "signature_value_exposure_attempted",
    "headers_value_exposure_attempted",
    "actual_http_post_attempted",
    "close_post_attempted",
    "retry_or_repost_attempted",
    "ledger_update_attempted",
    "receipt_handoff_attempted",
)

_SEALED_INSTRUCTION_BOOL_FIELDS = (
    "sealed_close_instruction_ready",
    "position_handle_value_exposed",
    "position_id_exposed",
    "raw_position_exposed",
    "raw_request_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
)

_CLOSE_EXECUTION_READINESS_BOOL_FIELDS = (
    "close_execution_step_may_be_planned",
    "close_execution_requires_new_confirmation",
    "close_execution_requires_time_market_operator_gate",
    "close_execution_requires_position_status_current",
    "close_execution_requires_exactly_one_position",
    "close_execution_requires_no_retry",
    "close_execution_requires_no_second_post",
    "close_execution_requires_raw_id_exposure_false",
    "close_execution_permission_granted_now",
)

_CLOSE_ROUTE_RESULT_BOOL_FIELDS = (
    "close_route_ready",
    "close_planning_allowed",
    "close_execution_allowed_now",
    "close_post_executed",
    "close_retry_allowed",
    "close_repost_allowed",
    "close_second_post_allowed",
    "requires_position_status",
    "requires_exactly_one_position",
    "requires_position_unknown_blocked",
    "requires_no_position_blocked",
    "requires_multiple_positions_blocked",
    "raw_position_exposed",
    "raw_request_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "position_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
    "actual_http_post_executed",
    "retry_attempted",
    "second_post_attempted",
    "ledger_updated",
    "receipt_handoff_executed",
)
