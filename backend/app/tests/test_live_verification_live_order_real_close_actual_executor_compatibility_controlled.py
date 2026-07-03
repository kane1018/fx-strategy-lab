from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.live_verification.live_order_real_close_actual_executor_compatibility_controlled import (
    EXECUTION_STEP_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY,
    NEXT_CYCLE_STATE_CLOSE_ACTUAL_EXECUTOR_BLOCKED,
    NEXT_CYCLE_STATE_CLOSE_ACTUAL_EXECUTOR_READY,
    CloseActualExecutorCompatibilityControlledInput,
    CloseActualExecutorCompatibilityControlledStatus,
    build_close_actual_executor_compatibility_controlled,
    render_close_actual_executor_compatibility_markdown,
)
from app.live_verification.live_order_real_close_order_execution_route_controlled import (
    APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC,
    CloseOrderExecutionRouteControlledInput,
    build_close_order_execution_route_controlled,
)
from app.live_verification.live_order_real_one_shot_post_execution_controlled import (
    LiveOrderRealExecutableOrderPreviewInput,
    build_live_order_real_executable_order_preview,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_step6g_level5_fast_mvp_controlled import (
    build_level5_fast_mvp_foundation,
    render_level5_fast_mvp_foundation_markdown,
)

Status = CloseActualExecutorCompatibilityControlledStatus

RAW_REQUEST_SENTINEL = "RAW_REQUEST_SHOULD_NOT_SURFACE"
RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
BROKER_RESPONSE_SENTINEL = "BROKER_RESPONSE_SHOULD_NOT_SURFACE"
POSITION_ID_SENTINEL = "POSITION_ID_SHOULD_NOT_SURFACE"
ACCOUNT_ID_SENTINEL = "ACCOUNT_ID_SHOULD_NOT_SURFACE"
ORDER_ID_SENTINEL = "ORDER_ID_SHOULD_NOT_SURFACE"
TRANSACTION_ID_SENTINEL = "TRANSACTION_ID_SHOULD_NOT_SURFACE"
CREDENTIAL_VALUE_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"

_FORBIDDEN_SENTINELS = (
    RAW_REQUEST_SENTINEL,
    RAW_RESPONSE_SENTINEL,
    BROKER_RESPONSE_SENTINEL,
    POSITION_ID_SENTINEL,
    ACCOUNT_ID_SENTINEL,
    ORDER_ID_SENTINEL,
    TRANSACTION_ID_SENTINEL,
    CREDENTIAL_VALUE_SENTINEL,
    SIGNATURE_VALUE_SENTINEL,
    HEADERS_VALUE_SENTINEL,
)


def _ready_route(entry_side: str = "BUY"):
    return build_close_order_execution_route_controlled(
        CloseOrderExecutionRouteControlledInput(
            runtime_position_status=PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
            position_count_safe=1,
            has_exactly_one_position=True,
            has_multiple_positions=False,
            close_route_ready=True,
            close_planning_allowed=True,
            fresh_entry_side_safe_label=entry_side,
            approved_close_post_primitive_kind=(
                APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC
            ),
            approved_close_post_primitive_is_generic_order=True,
            generic_order_accepted_as_close_only_with_exact_one_position_guard=True,
        ),
    )


def _ready_input(**overrides: object) -> CloseActualExecutorCompatibilityControlledInput:
    values = {
        "close_specific_context": True,
        "generic_entry_context": False,
        "input_close_execution_route_ready": True,
        "input_close_executable_preview_ready": True,
        "input_approved_close_post_primitive_ready": True,
        "input_approved_close_post_primitive_kind": (
            APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC
        ),
        "input_approved_close_post_primitive_is_generic_order": True,
        "input_generic_order_accepted_as_close_only_with_exact_one_position_guard": True,
        "runtime_position_status": PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        "position_count_safe": 1,
        "has_exactly_one_position": True,
        "has_multiple_positions": False,
        "close_side_safe_label": "SELL",
    }
    values.update(overrides)
    return CloseActualExecutorCompatibilityControlledInput(**values)


@pytest.mark.parametrize(
    ("entry_side", "close_side"),
    (
        ("BUY", "SELL"),
        ("SELL", "BUY"),
    ),
)
def test_close_specific_preview_accepts_concrete_close_side_from_route(
    entry_side: str,
    close_side: str,
) -> None:
    route = _ready_route(entry_side)
    result = build_close_actual_executor_compatibility_controlled(
        close_execution_route_result=route,
    )
    rendered = render_close_actual_executor_compatibility_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.READY_NO_POST
    assert result.close_actual_executor_compatibility_ready is True
    assert result.close_specific_executor_preview_ready is True
    assert result.close_specific_context is True
    assert result.generic_entry_context is False
    assert result.close_side_safe_label == close_side
    assert result.one_shot_executor_preview.sanitized_order_preview_available is True
    assert result.one_shot_executor_preview.order_ambiguity is False
    assert result.one_shot_executor_preview.side == close_side
    assert result.one_shot_executor_preview.size == 100
    assert result.close_units_fixed == 100
    assert result.close_order_type_safe_label == "MARKET"
    assert result.one_close_post_max is True
    assert result.close_retry_allowed is False
    assert result.close_repost_allowed is False
    assert result.close_second_post_allowed is False
    assert result.actual_close_post_allowed_now is False
    assert result.actual_close_post_executed is False
    assert result.transport_call_count == 0
    assert result.entry_post_this_step is False
    assert result.ledger_update_this_step is False
    assert result.receipt_handoff_this_step is False
    assert result.level5_connection.next_cycle_state == NEXT_CYCLE_STATE_CLOSE_ACTUAL_EXECUTOR_READY
    assert "actual_close_post_executed: false" in rendered
    assert "transport_call_count: 0" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_generic_entry_buy_guard_is_intact_and_generic_sell_remains_blocked() -> None:
    buy_preview = build_live_order_real_executable_order_preview()
    sell_preview = build_live_order_real_executable_order_preview(
        replace(LiveOrderRealExecutableOrderPreviewInput(), side="SELL"),
    )
    close_preview = build_close_actual_executor_compatibility_controlled(
        _ready_input(close_side_safe_label="SELL"),
    )

    assert buy_preview.sanitized_order_preview_available is True
    assert buy_preview.side == "BUY"
    assert sell_preview.sanitized_order_preview_available is False
    assert sell_preview.order_ambiguity is True
    assert "side_not_repo_defined_buy" in sell_preview.blocked_reasons
    assert close_preview.close_specific_sell_accepted is True
    assert close_preview.one_shot_executor_preview.sanitized_order_preview_available is True
    assert close_preview.one_shot_executor_preview.side == "SELL"
    assert close_preview.generic_entry_buy_guard_intact is True
    assert close_preview.generic_entry_sell_blocked is True


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"close_specific_context": False}, "close_specific_context_required"),
        ({"generic_entry_context": True}, "generic_entry_context_not_allowed_for_close"),
        ({"position_count_safe": 0}, "position_count_safe_not_1"),
        ({"position_count_safe": 2}, "position_count_safe_not_1"),
        ({"has_multiple_positions": True}, "has_multiple_positions_blocked"),
        (
            {"input_approved_close_post_primitive_ready": False},
            "input_approved_close_post_primitive_not_ready",
        ),
        (
            {"close_side_safe_label": "OPPOSITE_OF_SAFE_POSITION_SIDE"},
            "close_side_safe_label_must_be_concrete_buy_or_sell",
        ),
        ({"close_units_fixed": 101}, "close_units_must_be_100"),
        ({"close_order_type_safe_label": "LIMIT"}, "close_order_type_must_be_market"),
        ({"close_retry_allowed": True}, "close_retry_allowed"),
        ({"close_repost_allowed": True}, "close_repost_allowed"),
        ({"close_second_post_allowed": True}, "close_second_post_allowed"),
        ({"actual_close_post_allowed_now": True}, "actual_close_post_allowed_now"),
        (
            {"actual_close_post_attempted_this_step": True},
            "actual_close_post_attempted_this_step",
        ),
        ({"transport_call_count": 1}, "transport_call_count_must_remain_0"),
    ),
)
def test_close_specific_preview_fails_closed_on_guard_or_contract_breaks(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_close_actual_executor_compatibility_controlled(
        _ready_input(**override),
    )

    assert result.close_actual_executor_compatibility_ready is False
    assert result.close_specific_executor_preview_ready is False
    assert result.actual_close_post_allowed_now is False
    assert result.actual_close_post_executed is False
    assert result.transport_call_count == 0
    assert result.one_shot_executor_preview.sanitized_order_preview_available is False
    assert (
        result.level5_connection.next_cycle_state
        == NEXT_CYCLE_STATE_CLOSE_ACTUAL_EXECUTOR_BLOCKED
    )
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        (
            {"runtime_position_status": PositionReadOnlyControlledStatus.NO_POSITION},
            "runtime_position_status_not_one_position_open",
        ),
        (
            {
                "runtime_position_status": (
                    PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
                ),
                "position_count_safe": 2,
                "has_exactly_one_position": False,
                "has_multiple_positions": True,
            },
            "has_multiple_positions_blocked",
        ),
        (
            {"has_exactly_one_position": False},
            "has_exactly_one_position_required",
        ),
        (
            {
                "input_generic_order_accepted_as_close_only_with_exact_one_position_guard": (
                    False
                ),
            },
            "generic_order_close_exact_one_position_guard_required",
        ),
    ),
)
def test_exact_one_position_and_approved_close_guard_are_required(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_close_actual_executor_compatibility_controlled(
        _ready_input(**override),
    )

    assert result.close_actual_executor_compatibility_ready is False
    assert result.exact_one_position_guard_required is True
    assert result.approved_primitive_required is True
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"raw_request_exposure_attempted": True}, "raw_exposure_blocked"),
        ({"raw_response_exposure_attempted": True}, "raw_exposure_blocked"),
        ({"broker_api_response_exposure_attempted": True}, "raw_exposure_blocked"),
        ({"position_id_exposure_attempted": True}, "id_exposure_blocked"),
        ({"account_id_exposure_attempted": True}, "id_exposure_blocked"),
        ({"order_id_exposure_attempted": True}, "id_exposure_blocked"),
        ({"transaction_id_exposure_attempted": True}, "id_exposure_blocked"),
        (
            {"credential_value_exposure_attempted": True},
            "credential_signature_headers_exposure_blocked",
        ),
        (
            {"signature_value_exposure_attempted": True},
            "credential_signature_headers_exposure_blocked",
        ),
        (
            {"headers_value_exposure_attempted": True},
            "credential_signature_headers_exposure_blocked",
        ),
    ),
)
def test_unsafe_raw_id_value_exposure_attempts_are_blocked(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_close_actual_executor_compatibility_controlled(
        _ready_input(**override),
    )
    payload = repr(asdict(result))
    rendered = render_close_actual_executor_compatibility_markdown(result)

    assert result.status is Status.BLOCKED_UNSAFE
    assert result.close_actual_executor_compatibility_ready is False
    assert result.raw_request_exposed is False
    assert result.raw_response_exposed is False
    assert result.broker_api_response_exposed is False
    assert result.position_id_exposed is False
    assert result.account_id_exposed is False
    assert result.order_id_exposed is False
    assert result.transaction_id_exposed is False
    assert result.credential_value_exposed is False
    assert result.signature_value_exposed is False
    assert result.headers_value_exposed is False
    assert reason in result.blocked_reasons
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_level5_connection_reaches_close_actual_executor_ready_only_no_post() -> None:
    result = build_level5_fast_mvp_foundation(
        close_execution_route_input=CloseOrderExecutionRouteControlledInput(
            runtime_position_status=PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
            position_count_safe=1,
            has_exactly_one_position=True,
            has_multiple_positions=False,
            close_route_ready=True,
            close_planning_allowed=True,
            fresh_entry_side_safe_label="BUY",
            approved_close_post_primitive_kind=(
                APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC
            ),
            approved_close_post_primitive_is_generic_order=True,
            generic_order_accepted_as_close_only_with_exact_one_position_guard=True,
        ),
    )
    rendered = render_level5_fast_mvp_foundation_markdown(result)

    assert result.close_actual_executor_compatibility.close_side_safe_label == "SELL"
    assert result.close_actual_executor_compatibility.close_specific_sell_accepted is True
    assert result.close_actual_executor_compatibility.transport_call_count == 0
    assert result.close_actual_executor_compatibility.actual_close_post_allowed_now is False
    assert result.close_actual_executor_compatibility.actual_close_post_executed is False
    assert result.close_actual_executor_compatibility.entry_post_this_step is False
    assert result.close_actual_executor_compatibility.ledger_update_this_step is False
    assert result.close_actual_executor_compatibility.receipt_handoff_this_step is False
    assert (
        result.close_actual_executor_compatibility.level5_connection.next_cycle_state
        == NEXT_CYCLE_STATE_CLOSE_ACTUAL_EXECUTOR_READY
    )
    assert result.close_actual_executor_compatibility.level5_connection.close_sent_reached is False
    assert (
        result.close_actual_executor_compatibility.level5_connection.close_post_executed_reached
        is False
    )
    assert result.close_post_executed is False
    assert result.actual_http_post_executed is False
    assert "close_actual_executor_compatibility_ready: true" in rendered
    assert "close_actual_executor_transport_call_count: 0" in rendered


def test_level5_connection_blocks_when_close_execution_route_is_not_ready() -> None:
    result = build_level5_fast_mvp_foundation()

    assert (
        result.close_actual_executor_compatibility.close_actual_executor_compatibility_ready
        is False
    )
    assert (
        result.close_actual_executor_compatibility.level5_connection.next_cycle_state
        == NEXT_CYCLE_STATE_CLOSE_ACTUAL_EXECUTOR_BLOCKED
    )
    assert result.close_actual_executor_compatibility.transport_call_count == 0
    assert result.close_post_executed is False
    assert result.actual_http_post_executed is False


def test_preview_shape_contains_only_sanitized_close_executor_fields() -> None:
    result = build_close_actual_executor_compatibility_controlled(
        close_execution_route_result=_ready_route("BUY"),
    )
    preview = result.executable_preview

    assert preview.preview_ready is True
    assert preview.execution_step == EXECUTION_STEP_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY
    assert preview.close_specific_context is True
    assert preview.generic_entry_context is False
    assert preview.runtime_position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert preview.position_count_safe == 1
    assert preview.close_symbol_safe_label == "USD_JPY"
    assert preview.close_side_safe_label == "SELL"
    assert preview.close_units_fixed == 100
    assert preview.close_order_type_safe_label == "MARKET"
    assert preview.one_close_post_max is True
    assert preview.close_retry_allowed is False
    assert preview.close_repost_allowed is False
    assert preview.close_second_post_allowed is False
    assert preview.entry_post_this_step is False
    assert preview.actual_close_post_allowed_now is False
    assert preview.actual_close_post_executed is False
    assert preview.transport_call_count == 0
    assert preview.ledger_update_this_step is False
    assert preview.receipt_handoff_this_step is False
    assert preview.raw_exposure is False
    assert preview.id_exposure is False
    assert preview.credential_value_exposure is False
    assert preview.signature_value_exposure is False
    assert preview.headers_value_exposure is False
    assert preview.actual_close_post_requires_separate_close_execution_gate is True
