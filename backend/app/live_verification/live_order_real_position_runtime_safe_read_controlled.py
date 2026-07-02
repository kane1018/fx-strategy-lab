"""Step 6G runtime position safe read mapper.

This module maps an already-sanitized runtime read result to safe position
status/count fields only. It has no broker, Private API, HTTP, env, order,
ledger, receipt, or live_order_once dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_close_order_route_controlled import (
    CloseOrderRouteControlledResult,
    build_close_order_route_controlled,
)
from app.live_verification.live_order_real_credential_presence_controlled import (
    LiveOrderRealCredentialPresenceControlledResult,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledResult,
    PositionReadOnlyControlledStatus,
    build_position_read_only_controlled,
)
from app.live_verification.live_order_real_position_read_only_source_controlled import (
    PositionReadOnlySourceControlledInput,
    build_position_read_only_source_controlled,
)

SAFE_POSITION_RUNTIME_READ_LABEL = "STEP6G_POSITION_RUNTIME_SAFE_READ_CONTROLLED"
POSITION_RUNTIME_READ_RECOMMENDED_NEXT_STEP_NO_POSITION = (
    "step6g_level5_signal_entry_cycle_gate_no_post"
)
POSITION_RUNTIME_READ_RECOMMENDED_NEXT_STEP_ONE_POSITION = (
    "step6g_close_order_execution_gate_requires_extra_high_confirmation"
)
POSITION_RUNTIME_READ_RECOMMENDED_NEXT_STEP_BLOCKED = (
    "step6g_runtime_position_read_blocker_resolution_no_post"
)


class PositionRuntimeSafeReadControlledStatus(str, Enum):
    READY = "POSITION_RUNTIME_SAFE_READ_READY"
    BLOCKED = "POSITION_RUNTIME_SAFE_READ_BLOCKED"


@dataclass(frozen=True)
class PositionRuntimeSafeReadControlledInput:
    credential_presence_checked: bool = False
    credential_presence_available: bool = False
    all_required_credentials_present: bool = False
    runtime_read_requested: bool = True
    runtime_read_executed: bool = False
    runtime_read_succeeded: bool = False
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
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class PositionRuntimeSafeReadControlledResult:
    status: PositionRuntimeSafeReadControlledStatus
    position_runtime_safe_read_ready: bool
    safe_position_runtime_read_label: str
    credential_presence_checked: bool
    credential_presence_available: bool
    all_required_credentials_present: bool
    runtime_read_executed: bool
    position_source_checked: bool
    position_status_checked: bool
    position_status: PositionReadOnlyControlledStatus
    position_count_safe: int
    has_open_position: bool
    has_exactly_one_position: bool
    has_multiple_positions: bool
    new_entry_allowed: bool
    close_planning_allowed: bool
    close_execution_allowed_now: bool
    max_open_positions: int
    raw_position_exposed: bool
    position_id_exposed: bool
    account_id_exposed: bool
    order_id_exposed: bool
    transaction_id_exposed: bool
    broker_api_response_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool
    actual_http_post_executed: bool
    close_post_executed: bool
    retry_attempted: bool
    second_post_attempted: bool
    ledger_updated: bool
    receipt_handoff_executed: bool
    position_route: PositionReadOnlyControlledResult
    close_route: CloseOrderRouteControlledResult
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, PositionRuntimeSafeReadControlledStatus):
            raise LiveVerificationValidationError("status must be runtime read enum")
        if not isinstance(self.position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError("position_status must be controlled enum")
        _require_non_empty(
            "safe_position_runtime_read_label",
            self.safe_position_runtime_read_label,
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("max_open_positions", self.max_open_positions)
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_position_runtime_safe_read_controlled(
    input_snapshot: PositionRuntimeSafeReadControlledInput | None = None,
    *,
    credential_presence_result: LiveOrderRealCredentialPresenceControlledResult
    | None = None,
) -> PositionRuntimeSafeReadControlledResult:
    snapshot = input_snapshot or _input_from_credential_presence(
        credential_presence_result,
    )
    source_result = build_position_read_only_source_controlled(
        PositionReadOnlySourceControlledInput(
            position_source_ready=_credential_ready(snapshot),
            position_source_connected=_credential_ready(snapshot),
            position_source_read_only=True,
            position_source_checked=snapshot.runtime_read_succeeded,
            position_status_unknown=not snapshot.runtime_read_succeeded,
            position_count_safe=snapshot.position_count_safe,
            max_open_positions=snapshot.max_open_positions,
            raw_response_exposure_attempted=snapshot.raw_response_exposure_attempted,
            raw_position_exposure_attempted=snapshot.raw_position_exposure_attempted,
            broker_api_response_exposure_attempted=(
                snapshot.broker_api_response_exposure_attempted
            ),
            position_id_exposure_attempted=snapshot.position_id_exposure_attempted,
            account_id_exposure_attempted=snapshot.account_id_exposure_attempted,
            order_id_exposure_attempted=snapshot.order_id_exposure_attempted,
            transaction_id_exposure_attempted=(
                snapshot.transaction_id_exposure_attempted
            ),
            trade_id_exposure_attempted=snapshot.trade_id_exposure_attempted,
            actual_price_value_exposure_attempted=(
                snapshot.actual_price_value_exposure_attempted
            ),
            actual_pnl_value_exposure_attempted=(
                snapshot.actual_pnl_value_exposure_attempted
            ),
            position_value_exposure_attempted=snapshot.position_value_exposure_attempted,
            credential_value_exposure_attempted=(
                snapshot.credential_value_exposure_attempted
            ),
            signature_value_exposure_attempted=(
                snapshot.signature_value_exposure_attempted
            ),
            headers_value_exposure_attempted=snapshot.headers_value_exposure_attempted,
            actual_http_post_attempted=snapshot.actual_http_post_attempted,
            close_post_attempted=snapshot.close_post_attempted,
            retry_or_repost_attempted=snapshot.retry_or_repost_attempted,
            ledger_update_attempted=snapshot.ledger_update_attempted,
            receipt_handoff_attempted=snapshot.receipt_handoff_attempted,
        ),
    )
    position_route = build_position_read_only_controlled(source_result=source_result)
    close_route = build_close_order_route_controlled(position_result=position_route)
    reasons = _blocked_reasons(snapshot, position_route)
    checked = position_route.position_status_checked
    safe_status_ready = position_route.position_status in {
        PositionReadOnlyControlledStatus.NO_POSITION,
        PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED,
    }
    ready = checked and safe_status_ready and not _execution_or_exposure_attempted(snapshot)
    return PositionRuntimeSafeReadControlledResult(
        status=(
            PositionRuntimeSafeReadControlledStatus.READY
            if ready
            else PositionRuntimeSafeReadControlledStatus.BLOCKED
        ),
        position_runtime_safe_read_ready=ready,
        safe_position_runtime_read_label=SAFE_POSITION_RUNTIME_READ_LABEL,
        credential_presence_checked=snapshot.credential_presence_checked,
        credential_presence_available=snapshot.credential_presence_available,
        all_required_credentials_present=snapshot.all_required_credentials_present,
        runtime_read_executed=snapshot.runtime_read_executed and _credential_ready(snapshot),
        position_source_checked=source_result.position_source_checked,
        position_status_checked=position_route.position_status_checked,
        position_status=position_route.position_status,
        position_count_safe=position_route.position_count_safe,
        has_open_position=position_route.has_open_position,
        has_exactly_one_position=position_route.has_exactly_one_position,
        has_multiple_positions=position_route.has_multiple_positions,
        new_entry_allowed=position_route.new_entry_allowed,
        close_planning_allowed=close_route.close_planning_allowed,
        close_execution_allowed_now=False,
        max_open_positions=1,
        raw_position_exposed=False,
        position_id_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
        broker_api_response_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
        actual_http_post_executed=False,
        close_post_executed=False,
        retry_attempted=False,
        second_post_attempted=False,
        ledger_updated=False,
        receipt_handoff_executed=False,
        position_route=position_route,
        close_route=close_route,
        recommended_next_step=_recommended_next_step(position_route.position_status),
        blocked_reasons=reasons,
    )


def render_position_runtime_safe_read_controlled_markdown(
    result: PositionRuntimeSafeReadControlledResult,
) -> str:
    """Render runtime position safe status/count only."""
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Step 6G Position Runtime Safe Read Controlled",
            "",
            "This route renders runtime position status/count only.",
            "It does not execute actual entry POST or close POST.",
            "It does not expose raw position data, broker/API responses, IDs,",
            "credential values, signature values, or headers values.",
            "",
            f"credential_presence_checked: {_bool_text(result.credential_presence_checked)}",
            (
                "credential_presence_available: "
                f"{_bool_text(result.credential_presence_available)}"
            ),
            (
                "all_required_credentials_present: "
                f"{_bool_text(result.all_required_credentials_present)}"
            ),
            f"runtime_read_executed: {_bool_text(result.runtime_read_executed)}",
            f"position_source_checked: {_bool_text(result.position_source_checked)}",
            f"position_status_checked: {_bool_text(result.position_status_checked)}",
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
            f"raw_position_exposed: {_bool_text(result.raw_position_exposed)}",
            f"position_id_exposed: {_bool_text(result.position_id_exposed)}",
            f"account_id_exposed: {_bool_text(result.account_id_exposed)}",
            f"order_id_exposed: {_bool_text(result.order_id_exposed)}",
            f"transaction_id_exposed: {_bool_text(result.transaction_id_exposed)}",
            (
                "broker_api_response_exposed: "
                f"{_bool_text(result.broker_api_response_exposed)}"
            ),
            (
                "credential_value_exposed: "
                f"{_bool_text(result.credential_value_exposed)}"
            ),
            f"signature_value_exposed: {_bool_text(result.signature_value_exposed)}",
            f"headers_value_exposed: {_bool_text(result.headers_value_exposed)}",
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


def _input_from_credential_presence(
    result: LiveOrderRealCredentialPresenceControlledResult | None,
) -> PositionRuntimeSafeReadControlledInput:
    if result is None:
        return PositionRuntimeSafeReadControlledInput()
    ready = result.credential_presence_controlled_ready
    return PositionRuntimeSafeReadControlledInput(
        credential_presence_checked=result.process_env_checked_for_presence_only,
        credential_presence_available=ready,
        all_required_credentials_present=result.all_required_credentials_present,
    )


def _credential_ready(snapshot: PositionRuntimeSafeReadControlledInput) -> bool:
    return (
        snapshot.credential_presence_checked
        and snapshot.credential_presence_available
        and snapshot.all_required_credentials_present
    )


def _blocked_reasons(
    snapshot: PositionRuntimeSafeReadControlledInput,
    position_route: PositionReadOnlyControlledResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.credential_presence_checked:
        reasons.append("credential_presence_not_checked")
    if not snapshot.credential_presence_available:
        reasons.append("credential_presence_unavailable")
    if not snapshot.all_required_credentials_present:
        reasons.append("required_credentials_missing")
    if snapshot.runtime_read_requested and not snapshot.runtime_read_executed:
        reasons.append("runtime_read_not_executed")
    if snapshot.runtime_read_executed and not snapshot.runtime_read_succeeded:
        reasons.append("runtime_read_unknown_fail_closed")
    if position_route.position_status is PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED:
        reasons.append("position_unknown_fail_closed")
    if position_route.position_status is PositionReadOnlyControlledStatus.SOURCE_MISSING_BLOCKED:
        reasons.append("position_source_missing")
    if (
        position_route.position_status
        is PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    ):
        reasons.append("multiple_positions_blocked")
    if _execution_or_exposure_attempted(snapshot):
        reasons.extend(_execution_or_exposure_reasons(snapshot))
    return tuple(dict.fromkeys(reasons))


def _execution_or_exposure_attempted(
    snapshot: PositionRuntimeSafeReadControlledInput,
) -> bool:
    return bool(_execution_or_exposure_reasons(snapshot))


def _execution_or_exposure_reasons(
    snapshot: PositionRuntimeSafeReadControlledInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        snapshot.raw_response_exposure_attempted
        or snapshot.raw_position_exposure_attempted
        or snapshot.broker_api_response_exposure_attempted
    ):
        reasons.append("raw_or_broker_response_exposure_blocked")
    if (
        snapshot.position_id_exposure_attempted
        or snapshot.account_id_exposure_attempted
        or snapshot.order_id_exposure_attempted
        or snapshot.transaction_id_exposure_attempted
        or snapshot.trade_id_exposure_attempted
    ):
        reasons.append("id_exposure_blocked")
    if (
        snapshot.actual_price_value_exposure_attempted
        or snapshot.actual_pnl_value_exposure_attempted
        or snapshot.position_value_exposure_attempted
    ):
        reasons.append("value_exposure_blocked")
    if (
        snapshot.credential_value_exposure_attempted
        or snapshot.signature_value_exposure_attempted
        or snapshot.headers_value_exposure_attempted
    ):
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
    return tuple(reasons)


def _recommended_next_step(status: PositionReadOnlyControlledStatus) -> str:
    if status is PositionReadOnlyControlledStatus.NO_POSITION:
        return POSITION_RUNTIME_READ_RECOMMENDED_NEXT_STEP_NO_POSITION
    if status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        return POSITION_RUNTIME_READ_RECOMMENDED_NEXT_STEP_ONE_POSITION
    return POSITION_RUNTIME_READ_RECOMMENDED_NEXT_STEP_BLOCKED


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


_INPUT_BOOL_FIELDS = (
    "credential_presence_checked",
    "credential_presence_available",
    "all_required_credentials_present",
    "runtime_read_requested",
    "runtime_read_executed",
    "runtime_read_succeeded",
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

_RESULT_BOOL_FIELDS = (
    "position_runtime_safe_read_ready",
    "credential_presence_checked",
    "credential_presence_available",
    "all_required_credentials_present",
    "runtime_read_executed",
    "position_source_checked",
    "position_status_checked",
    "has_open_position",
    "has_exactly_one_position",
    "has_multiple_positions",
    "new_entry_allowed",
    "close_planning_allowed",
    "close_execution_allowed_now",
    "raw_position_exposed",
    "position_id_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
    "broker_api_response_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
    "actual_http_post_executed",
    "close_post_executed",
    "retry_attempted",
    "second_post_attempted",
    "ledger_updated",
    "receipt_handoff_executed",
)
