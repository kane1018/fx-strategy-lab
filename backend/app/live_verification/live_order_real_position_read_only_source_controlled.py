"""Step 6G controlled position read-only source adapter.

This module accepts an already-sanitized position source summary and maps it to
safe status/count fields only. It does not import broker/private API clients,
HTTP clients, env readers, order endpoints, live_order_once, ledger writers, or
receipt handoff code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

SAFE_POSITION_READ_ONLY_SOURCE_LABEL = (
    "STEP6G_POSITION_READ_ONLY_SOURCE_CONTROLLED"
)
POSITION_READ_ONLY_SOURCE_RECOMMENDED_NEXT_STEP = (
    "step6g_close_order_route_implementation_no_post"
)


class PositionReadOnlySourceControlledStatus(str, Enum):
    NO_POSITION = "NO_POSITION"
    ONE_POSITION_OPEN = "ONE_POSITION_OPEN"
    MULTIPLE_POSITIONS_BLOCKED = "MULTIPLE_POSITIONS_BLOCKED"
    UNKNOWN_FAIL_CLOSED = "UNKNOWN_FAIL_CLOSED"
    SOURCE_MISSING_BLOCKED = "SOURCE_MISSING_BLOCKED"
    RAW_EXPOSURE_BLOCKED = "RAW_EXPOSURE_BLOCKED"
    ID_EXPOSURE_BLOCKED = "ID_EXPOSURE_BLOCKED"
    VALUE_EXPOSURE_BLOCKED = "VALUE_EXPOSURE_BLOCKED"
    CREDENTIAL_UNAVAILABLE_BLOCKED = "CREDENTIAL_UNAVAILABLE_BLOCKED"


@dataclass(frozen=True)
class PositionReadOnlySourceControlledInput:
    position_source_ready: bool = True
    position_source_connected: bool = True
    position_source_read_only: bool = True
    position_source_checked: bool = True
    position_status_unknown: bool = False
    position_count_safe: int = 0
    max_open_positions: int = 1
    raw_response_exposure_attempted: bool = False
    raw_position_exposure_attempted: bool = False
    broker_api_response_exposure_attempted: bool = False
    position_id_exposure_attempted: bool = False
    account_id_exposure_attempted: bool = False
    order_id_exposure_attempted: bool = False
    transaction_id_exposure_attempted: bool = False
    trade_id_exposure_attempted: bool = False
    actual_price_value_exposure_attempted: bool = False
    actual_pnl_value_exposure_attempted: bool = False
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
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("max_open_positions", self.max_open_positions)
        _validate_bool_fields(self, _SOURCE_INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class PositionReadOnlySourceControlledResult:
    position_source_ready: bool
    position_source_connected: bool
    position_source_read_only: bool
    position_source_checked: bool
    safe_position_source_label: str
    position_status: PositionReadOnlySourceControlledStatus
    position_count_safe: int
    has_open_position: bool
    has_exactly_one_position: bool
    has_multiple_positions: bool
    new_entry_allowed: bool
    close_planning_allowed: bool
    close_execution_allowed_now: bool
    max_open_positions: int
    raw_response_exposed: bool
    raw_position_exposed: bool
    broker_api_response_exposed: bool
    position_id_exposed: bool
    account_id_exposed: bool
    order_id_exposed: bool
    transaction_id_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool
    sealed_position_handle_created: bool
    handle_value_exposed: bool
    actual_http_post_executed: bool
    close_post_executed: bool
    retry_attempted: bool
    second_post_attempted: bool
    ledger_updated: bool
    receipt_handoff_executed: bool
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.position_status, PositionReadOnlySourceControlledStatus):
            raise LiveVerificationValidationError("position_status must be controlled enum")
        _require_non_empty("safe_position_source_label", self.safe_position_source_label)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("max_open_positions", self.max_open_positions)
        _validate_bool_fields(self, _SOURCE_RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_position_read_only_source_controlled(
    input_snapshot: PositionReadOnlySourceControlledInput | None = None,
) -> PositionReadOnlySourceControlledResult:
    snapshot = input_snapshot or PositionReadOnlySourceControlledInput()
    status, reasons = _status_and_reasons(snapshot)
    clean_source = (
        snapshot.position_source_ready
        and snapshot.position_source_connected
        and snapshot.position_source_read_only
        and status
        not in {
            PositionReadOnlySourceControlledStatus.SOURCE_MISSING_BLOCKED,
            PositionReadOnlySourceControlledStatus.RAW_EXPOSURE_BLOCKED,
            PositionReadOnlySourceControlledStatus.ID_EXPOSURE_BLOCKED,
            PositionReadOnlySourceControlledStatus.VALUE_EXPOSURE_BLOCKED,
            PositionReadOnlySourceControlledStatus.CREDENTIAL_UNAVAILABLE_BLOCKED,
        }
    )
    safe_checked = (
        snapshot.position_source_checked
        and status
        in {
            PositionReadOnlySourceControlledStatus.NO_POSITION,
            PositionReadOnlySourceControlledStatus.ONE_POSITION_OPEN,
            PositionReadOnlySourceControlledStatus.MULTIPLE_POSITIONS_BLOCKED,
        }
    )
    return PositionReadOnlySourceControlledResult(
        position_source_ready=clean_source,
        position_source_connected=snapshot.position_source_connected and clean_source,
        position_source_read_only=snapshot.position_source_read_only and clean_source,
        position_source_checked=safe_checked,
        safe_position_source_label=SAFE_POSITION_READ_ONLY_SOURCE_LABEL,
        position_status=status,
        position_count_safe=snapshot.position_count_safe,
        has_open_position=snapshot.position_count_safe > 0
        and status
        in {
            PositionReadOnlySourceControlledStatus.ONE_POSITION_OPEN,
            PositionReadOnlySourceControlledStatus.MULTIPLE_POSITIONS_BLOCKED,
        },
        has_exactly_one_position=(
            status is PositionReadOnlySourceControlledStatus.ONE_POSITION_OPEN
        ),
        has_multiple_positions=(
            status is PositionReadOnlySourceControlledStatus.MULTIPLE_POSITIONS_BLOCKED
        ),
        new_entry_allowed=status is PositionReadOnlySourceControlledStatus.NO_POSITION,
        close_planning_allowed=(
            status is PositionReadOnlySourceControlledStatus.ONE_POSITION_OPEN
        ),
        close_execution_allowed_now=False,
        max_open_positions=1,
        raw_response_exposed=False,
        raw_position_exposed=False,
        broker_api_response_exposed=False,
        position_id_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
        sealed_position_handle_created=False,
        handle_value_exposed=False,
        actual_http_post_executed=False,
        close_post_executed=False,
        retry_attempted=False,
        second_post_attempted=False,
        ledger_updated=False,
        receipt_handoff_executed=False,
        recommended_next_step=POSITION_READ_ONLY_SOURCE_RECOMMENDED_NEXT_STEP,
        blocked_reasons=reasons,
    )


def render_position_read_only_source_controlled_markdown(
    result: PositionReadOnlySourceControlledResult,
) -> str:
    """Render safe source status/count only."""
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Position Read-Only Source Controlled",
            "",
            "This source renders safe position status/count only.",
            "It does not execute actual POST or close POST.",
            "It does not expose raw position data, broker/API responses, IDs,",
            "credential values, signature values, or headers values.",
            "",
            f"position_source_ready: {_bool_text(result.position_source_ready)}",
            f"position_source_connected: {_bool_text(result.position_source_connected)}",
            f"position_source_read_only: {_bool_text(result.position_source_read_only)}",
            f"position_source_checked: {_bool_text(result.position_source_checked)}",
            f"position_status: {result.position_status.value}",
            f"position_count_safe: {result.position_count_safe}",
            f"has_open_position: {_bool_text(result.has_open_position)}",
            f"has_exactly_one_position: {_bool_text(result.has_exactly_one_position)}",
            f"has_multiple_positions: {_bool_text(result.has_multiple_positions)}",
            f"new_entry_allowed: {_bool_text(result.new_entry_allowed)}",
            f"close_planning_allowed: {_bool_text(result.close_planning_allowed)}",
            (
                "close_execution_allowed_now: "
                f"{_bool_text(result.close_execution_allowed_now)}"
            ),
            f"raw_response_exposed: {_bool_text(result.raw_response_exposed)}",
            f"raw_position_exposed: {_bool_text(result.raw_position_exposed)}",
            (
                "broker_api_response_exposed: "
                f"{_bool_text(result.broker_api_response_exposed)}"
            ),
            f"position_id_exposed: {_bool_text(result.position_id_exposed)}",
            f"account_id_exposed: {_bool_text(result.account_id_exposed)}",
            f"order_id_exposed: {_bool_text(result.order_id_exposed)}",
            f"transaction_id_exposed: {_bool_text(result.transaction_id_exposed)}",
            (
                "credential_value_exposed: "
                f"{_bool_text(result.credential_value_exposed)}"
            ),
            f"signature_value_exposed: {_bool_text(result.signature_value_exposed)}",
            f"headers_value_exposed: {_bool_text(result.headers_value_exposed)}",
            (
                "sealed_position_handle_created: "
                f"{_bool_text(result.sealed_position_handle_created)}"
            ),
            f"handle_value_exposed: {_bool_text(result.handle_value_exposed)}",
            f"actual_http_post_executed: {_bool_text(result.actual_http_post_executed)}",
            f"close_post_executed: {_bool_text(result.close_post_executed)}",
            f"retry_attempted: {_bool_text(result.retry_attempted)}",
            f"second_post_attempted: {_bool_text(result.second_post_attempted)}",
            f"ledger_updated: {_bool_text(result.ledger_updated)}",
            f"receipt_handoff_executed: {_bool_text(result.receipt_handoff_executed)}",
            f"blocked_reasons: {blocked}",
            f"recommended_next_step: {result.recommended_next_step}",
        )
    ) + "\n"


def _status_and_reasons(
    snapshot: PositionReadOnlySourceControlledInput,
) -> tuple[PositionReadOnlySourceControlledStatus, tuple[str, ...]]:
    reasons = _blocked_reasons(snapshot)
    if _credential_exposure_attempted(snapshot):
        return PositionReadOnlySourceControlledStatus.CREDENTIAL_UNAVAILABLE_BLOCKED, reasons
    if _raw_exposure_attempted(snapshot):
        return PositionReadOnlySourceControlledStatus.RAW_EXPOSURE_BLOCKED, reasons
    if _id_exposure_attempted(snapshot):
        return PositionReadOnlySourceControlledStatus.ID_EXPOSURE_BLOCKED, reasons
    if _value_exposure_attempted(snapshot):
        return PositionReadOnlySourceControlledStatus.VALUE_EXPOSURE_BLOCKED, reasons
    if reasons:
        if "position_source_missing" in reasons:
            return PositionReadOnlySourceControlledStatus.SOURCE_MISSING_BLOCKED, reasons
        if "multiple_positions_blocked" in reasons:
            return PositionReadOnlySourceControlledStatus.MULTIPLE_POSITIONS_BLOCKED, reasons
        return PositionReadOnlySourceControlledStatus.UNKNOWN_FAIL_CLOSED, reasons
    if not snapshot.position_source_checked or snapshot.position_status_unknown:
        return (
            PositionReadOnlySourceControlledStatus.UNKNOWN_FAIL_CLOSED,
            ("position_unknown_fail_closed",),
        )
    if snapshot.position_count_safe == 0:
        return PositionReadOnlySourceControlledStatus.NO_POSITION, ()
    if snapshot.position_count_safe == 1:
        return PositionReadOnlySourceControlledStatus.ONE_POSITION_OPEN, ()
    return (
        PositionReadOnlySourceControlledStatus.MULTIPLE_POSITIONS_BLOCKED,
        ("multiple_positions_blocked",),
    )


def _blocked_reasons(snapshot: PositionReadOnlySourceControlledInput) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.max_open_positions != 1:
        reasons.append("max_open_positions_must_be_1")
    if (
        not snapshot.position_source_ready
        or not snapshot.position_source_connected
        or not snapshot.position_source_read_only
    ):
        reasons.append("position_source_missing")
    if _raw_exposure_attempted(snapshot):
        reasons.append("raw_exposure_blocked")
    if _id_exposure_attempted(snapshot):
        reasons.append("id_exposure_blocked")
    if _value_exposure_attempted(snapshot):
        reasons.append("value_exposure_blocked")
    if _credential_exposure_attempted(snapshot):
        reasons.append("credential_or_header_exposure_blocked")
    if snapshot.position_count_safe > 1:
        reasons.append("multiple_positions_blocked")
    for field_name in (
        "actual_http_post_attempted",
        "close_post_attempted",
        "retry_or_repost_attempted",
        "ledger_update_attempted",
        "receipt_handoff_attempted",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(reasons)


def _raw_exposure_attempted(snapshot: PositionReadOnlySourceControlledInput) -> bool:
    return (
        snapshot.raw_response_exposure_attempted
        or snapshot.raw_position_exposure_attempted
        or snapshot.broker_api_response_exposure_attempted
    )


def _id_exposure_attempted(snapshot: PositionReadOnlySourceControlledInput) -> bool:
    return (
        snapshot.position_id_exposure_attempted
        or snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
    )


def _value_exposure_attempted(snapshot: PositionReadOnlySourceControlledInput) -> bool:
    return (
        snapshot.actual_price_value_exposure_attempted
        or snapshot.actual_pnl_value_exposure_attempted
        or snapshot.position_value_exposure_attempted
    )


def _credential_exposure_attempted(
    snapshot: PositionReadOnlySourceControlledInput,
) -> bool:
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


_SOURCE_INPUT_BOOL_FIELDS = (
    "position_source_ready",
    "position_source_connected",
    "position_source_read_only",
    "position_source_checked",
    "position_status_unknown",
    "raw_response_exposure_attempted",
    "raw_position_exposure_attempted",
    "broker_api_response_exposure_attempted",
    "position_id_exposure_attempted",
    "account_id_exposure_attempted",
    "order_id_exposure_attempted",
    "transaction_id_exposure_attempted",
    "trade_id_exposure_attempted",
    "actual_price_value_exposure_attempted",
    "actual_pnl_value_exposure_attempted",
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

_SOURCE_RESULT_BOOL_FIELDS = (
    "position_source_ready",
    "position_source_connected",
    "position_source_read_only",
    "position_source_checked",
    "has_open_position",
    "has_exactly_one_position",
    "has_multiple_positions",
    "new_entry_allowed",
    "close_planning_allowed",
    "close_execution_allowed_now",
    "raw_response_exposed",
    "raw_position_exposed",
    "broker_api_response_exposed",
    "position_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
    "sealed_position_handle_created",
    "handle_value_exposed",
    "actual_http_post_executed",
    "close_post_executed",
    "retry_attempted",
    "second_post_attempted",
    "ledger_updated",
    "receipt_handoff_executed",
)
