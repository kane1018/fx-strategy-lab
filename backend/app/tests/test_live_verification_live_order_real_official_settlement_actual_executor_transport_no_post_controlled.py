from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from app.live_verification.live_order_real_official_settlement_actual_executor_compatibility_controlled import (  # noqa: E501
    OfficialSettlementActualExecutorCompatibilityInput,
    build_official_settlement_actual_executor_compatibility_controlled,
)
from app.live_verification.live_order_real_official_settlement_actual_executor_transport_no_post_controlled import (  # noqa: E501
    NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED,
    NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_READY,
    OFFICIAL_SETTLEMENT_RESULT_ACTUAL_EXECUTOR_TRANSPORT_READY_NO_POST_SANITIZED,
    OfficialSettlementActualExecutorTransportInput,
    OfficialSettlementActualExecutorTransportNoPostStatus,
    build_official_settlement_actual_executor_transport_no_post_controlled,
    render_official_settlement_actual_executor_transport_no_post_markdown,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)

Status = OfficialSettlementActualExecutorTransportNoPostStatus

RAW_REQUEST_SENTINEL = "RAW_REQUEST_SHOULD_NOT_SURFACE"
RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
BROKER_RESPONSE_SENTINEL = "BROKER_RESPONSE_SHOULD_NOT_SURFACE"
POSITION_ID_SENTINEL = "POSITION_ID_SHOULD_NOT_SURFACE"
ACCOUNT_ID_SENTINEL = "ACCOUNT_ID_SHOULD_NOT_SURFACE"
ORDER_ID_SENTINEL = "ORDER_ID_SHOULD_NOT_SURFACE"
TRANSACTION_ID_SENTINEL = "TRANSACTION_ID_SHOULD_NOT_SURFACE"
TRADE_ID_SENTINEL = "TRADE_ID_SHOULD_NOT_SURFACE"
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
    TRADE_ID_SENTINEL,
    CREDENTIAL_VALUE_SENTINEL,
    SIGNATURE_VALUE_SENTINEL,
    HEADERS_VALUE_SENTINEL,
)


def _ready_input(
    **overrides: object,
) -> OfficialSettlementActualExecutorTransportInput:
    values = {
        "runtime_position_status": PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        "position_count_safe": 1,
        "has_exactly_one_position": True,
        "has_multiple_positions": False,
    }
    values.update(overrides)
    return OfficialSettlementActualExecutorTransportInput(**values)


def test_compatibility_ready_builds_actual_executor_transport_boundary_no_post() -> None:
    compatibility = build_official_settlement_actual_executor_compatibility_controlled()
    result = build_official_settlement_actual_executor_transport_no_post_controlled(
        compatibility_result=compatibility,
    )
    rendered = render_official_settlement_actual_executor_transport_no_post_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.READY_NO_POST
    assert result.dedicated_actual_official_settlement_post_executor_available is True
    assert result.dedicated_actual_official_settlement_transport_boundary_ready is True
    assert result.next_execution_gate_can_detect_actual_executor is True
    assert result.dedicated_settlement_actual_executor_compatibility_ready is True
    assert result.official_settlement_no_post_preview_ready is True
    assert result.official_settlement_executor_preview_ready is True
    assert result.settlement_route_kind == "OFFICIAL_SIZE_BASED_SETTLEMENT"
    assert result.settlement_route_is_generic_order is False
    assert result.settlement_route_is_dedicated is True
    assert result.generic_order_executor_used_for_settlement is False
    assert result.live_order_once_used_for_settlement is False
    assert result.generic_order_endpoint_used_for_settlement is False
    assert result.one_shot_generic_order_path_used_for_settlement is False
    assert result.position_specific_path_used is False
    assert result.position_specific_identifier_safe_handling_ready is False
    assert result.position_specific_preview_allowed is False
    assert result.size_based_preview_allowed is True
    assert result.actual_settlement_post_allowed_now is False
    assert result.actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert result.transport_call_count == 0
    assert result.http_post_executed is False
    assert result.entry_post_executed is False
    assert result.generic_close_post_executed is False
    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_settlement_allowed is False
    assert result.ledger_update is False
    assert result.receipt_handoff is False
    assert result.raw_id_value_credential_header_exposure is False
    assert result.next_execution_gate_still_requires_fresh_runtime_read is True
    assert result.next_execution_gate_still_requires_operator_readiness is True
    assert result.next_execution_gate_still_requires_settlement_specific_confirmation is True
    assert result.result_safe_category == (
        OFFICIAL_SETTLEMENT_RESULT_ACTUAL_EXECUTOR_TRANSPORT_READY_NO_POST_SANITIZED
    )
    assert result.level5_connection.next_cycle_state == (
        NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_READY
    )
    assert "dedicated_actual_official_settlement_post_executor_available: true" in rendered
    assert "transport_call_count: 0" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_actual_executor_plan_and_transport_boundary_are_dedicated_no_post() -> None:
    result = build_official_settlement_actual_executor_transport_no_post_controlled(
        _ready_input(),
    )
    plan = result.executor_plan
    transport = result.transport_boundary

    assert plan.plan_ready is True
    assert plan.dedicated_actual_official_settlement_post_executor_available is True
    assert plan.settlement_route_is_generic_order is False
    assert plan.settlement_route_is_dedicated is True
    assert plan.runtime_position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert plan.position_count_safe == 1
    assert plan.actual_settlement_post_allowed_now is False
    assert plan.actual_settlement_post_executed is False
    assert plan.settlement_post_count == 0
    assert plan.retry_allowed is False
    assert plan.repost_allowed is False
    assert plan.second_settlement_allowed is False
    assert plan.entry_post_executed is False
    assert plan.generic_close_post_executed is False
    assert plan.raw_id_value_credential_header_exposure is False

    assert transport.dedicated_actual_official_settlement_transport_boundary_ready is True
    assert transport.dedicated_settlement_transport is True
    assert transport.generic_order_transport is False
    assert transport.one_shot_generic_order_transport is False
    assert transport.can_call_live_order_once is False
    assert transport.position_specific_transport is False
    assert transport.size_based_transport is True
    assert transport.transport_invocation_deferred is True
    assert transport.transport_call_count == 0
    assert transport.http_post_executed is False
    assert transport.settlement_endpoint_called is False
    assert transport.generic_order_endpoint_called is False
    assert transport.live_order_once_called is False
    assert transport.raw_request_exposed is False
    assert transport.raw_response_exposed is False
    assert transport.broker_api_response_exposed is False
    assert transport.id_exposed is False
    assert transport.credential_value_exposed is False
    assert transport.signature_value_exposed is False
    assert transport.headers_value_exposed is False


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        (
            {"runtime_position_status": PositionReadOnlyControlledStatus.NO_POSITION},
            "runtime_position_status_not_one_position_open",
        ),
        ({"position_count_safe": 0}, "position_count_safe_not_1"),
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
        ({"has_exactly_one_position": False}, "has_exactly_one_position_required"),
    ),
)
def test_only_one_position_open_count_one_can_plan_executor_boundary(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_executor_transport_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status is Status.BLOCKED_POSITION
    assert result.dedicated_actual_official_settlement_post_executor_available is False
    assert result.dedicated_actual_official_settlement_transport_boundary_ready is False
    assert result.next_execution_gate_can_detect_actual_executor is False
    assert result.actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert reason in result.blocked_reasons
    assert result.level5_connection.next_cycle_state == (
        NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_TRANSPORT_BLOCKED
    )


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"settlement_route_is_generic_order": True}, "settlement_route_must_not_be_generic_order"),
        ({"settlement_route_is_dedicated": False}, "settlement_route_must_be_dedicated"),
        (
            {"generic_order_executor_used_for_settlement": True},
            "generic_order_executor_used_for_settlement",
        ),
        (
            {"live_order_once_used_for_settlement": True},
            "live_order_once_used_for_settlement",
        ),
        (
            {"generic_order_endpoint_used_for_settlement": True},
            "generic_order_endpoint_used_for_settlement",
        ),
        (
            {"one_shot_generic_order_path_used_for_settlement": True},
            "one_shot_generic_order_path_used_for_settlement",
        ),
    ),
)
def test_generic_and_one_shot_paths_are_not_settlement_transport(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_executor_transport_no_post_controlled(
        _ready_input(**override),
    )

    expected = (
        Status.BLOCKED_ROUTE
        if reason == "settlement_route_must_be_dedicated"
        else Status.BLOCKED_GENERIC_EXECUTOR
    )
    assert result.status is expected
    assert result.dedicated_actual_official_settlement_post_executor_available is False
    assert result.generic_order_executor_used_for_settlement is False
    assert result.live_order_once_used_for_settlement is False
    assert result.generic_order_endpoint_used_for_settlement is False
    assert result.one_shot_generic_order_path_used_for_settlement is False
    assert result.actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"position_specific_path_used": True}, "position_specific_path_used"),
        (
            {"position_specific_identifier_safe_handling_ready": True},
            "position_specific_identifier_handling_not_this_step",
        ),
        (
            {"position_specific_preview_allowed": True},
            "position_specific_preview_must_remain_blocked",
        ),
        ({"size_based_preview_allowed": False}, "size_based_preview_not_allowed"),
    ),
)
def test_position_specific_path_stays_blocked(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_executor_transport_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status in {
        Status.BLOCKED_POSITION_SPECIFIC_IDENTIFIER,
        Status.BLOCKED_ROUTE,
    }
    assert result.dedicated_actual_official_settlement_post_executor_available is False
    assert result.position_specific_path_used is False
    assert result.actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        (
            {"actual_settlement_post_allowed_now": True},
            "actual_settlement_post_allowed_now",
        ),
        (
            {"actual_settlement_post_executed": True},
            "actual_settlement_post_executed",
        ),
        ({"settlement_post_count": 1}, "settlement_post_count_must_remain_0"),
        ({"transport_call_count": 1}, "transport_call_count_must_remain_0"),
        ({"http_post_executed": True}, "http_post_executed"),
        ({"settlement_endpoint_called": True}, "settlement_endpoint_called"),
        ({"entry_post_executed": True}, "entry_post_executed"),
        ({"generic_close_post_executed": True}, "generic_close_post_executed"),
        ({"retry_allowed": True}, "retry_allowed"),
        ({"repost_allowed": True}, "repost_allowed"),
        ({"second_settlement_allowed": True}, "second_settlement_allowed"),
        ({"ledger_update": True}, "ledger_update"),
        ({"receipt_handoff": True}, "receipt_handoff"),
    ),
)
def test_lifecycle_execution_attempts_are_blocked_no_post(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_executor_transport_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status is Status.BLOCKED_LIFECYCLE
    assert result.dedicated_actual_official_settlement_post_executor_available is False
    assert result.actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert result.transport_call_count == 0
    assert result.http_post_executed is False
    assert result.entry_post_executed is False
    assert result.generic_close_post_executed is False
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
        ({"trade_id_exposure_attempted": True}, "id_exposure_blocked"),
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
def test_raw_id_value_credential_header_exposure_attempts_are_blocked(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_executor_transport_no_post_controlled(
        _ready_input(**override),
    )
    rendered = render_official_settlement_actual_executor_transport_no_post_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_UNSAFE
    assert result.dedicated_actual_official_settlement_post_executor_available is False
    assert result.raw_id_value_credential_header_exposure is True
    assert result.transport_boundary.raw_request_exposed is False
    assert result.transport_boundary.id_exposed is False
    assert result.executor_plan.raw_id_value_credential_header_exposure is True
    assert reason in result.blocked_reasons
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_blocked_compatibility_blocks_actual_executor_transport_boundary() -> None:
    compatibility = build_official_settlement_actual_executor_compatibility_controlled(
        OfficialSettlementActualExecutorCompatibilityInput(
            official_settlement_no_post_preview_ready=False,
        ),
    )
    result = build_official_settlement_actual_executor_transport_no_post_controlled(
        compatibility_result=compatibility,
    )

    assert result.status is Status.BLOCKED_COMPATIBILITY
    assert result.dedicated_settlement_actual_executor_compatibility_ready is False
    assert result.dedicated_actual_official_settlement_post_executor_available is False
    assert result.dedicated_actual_official_settlement_transport_boundary_ready is False
    assert result.actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert (
        "dedicated_settlement_actual_executor_compatibility_not_ready"
        in result.blocked_reasons
    )


@pytest.mark.parametrize(
    "field_name",
    (
        "next_execution_gate_can_detect_actual_executor",
        "next_execution_gate_still_requires_fresh_runtime_read",
        "next_execution_gate_still_requires_operator_readiness",
        "next_execution_gate_still_requires_settlement_specific_confirmation",
    ),
)
def test_next_execution_gate_detection_flags_are_required(field_name: str) -> None:
    result = build_official_settlement_actual_executor_transport_no_post_controlled(
        _ready_input(**{field_name: False}),
    )

    assert result.status is Status.BLOCKED_ROUTE
    assert result.dedicated_actual_official_settlement_post_executor_available is False
    assert field_name in result.blocked_reasons


def test_actual_executor_transport_module_has_no_execution_imports_or_calls() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_official_settlement_actual_executor_transport_no_post_controlled.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "app.brokers",
        "app.private_api",
        "httpx",
        "requests",
        "urllib",
        "urllib3",
        "socket",
        "subprocess",
        "dotenv",
        "os",
    }
    blocked_names = {
        "live_order_once",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "getenv",
        "environ",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in blocked_modules
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module not in blocked_modules
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Call):
            call_name = _call_name(node)
            assert call_name not in blocked_names


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None
