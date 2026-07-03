from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from app.live_verification.live_order_real_official_settlement_actual_executor_compatibility_controlled import (  # noqa: E501
    EXECUTION_STEP_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY,
    NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_EXECUTOR_BLOCKED,
    NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_EXECUTOR_READY,
    OFFICIAL_SETTLEMENT_RESULT_COMPATIBLE_NO_POST_SANITIZED,
    OfficialSettlementActualExecutorCompatibilityInput,
    OfficialSettlementActualExecutorCompatibilityStatus,
    build_official_settlement_actual_executor_compatibility_controlled,
    render_official_settlement_actual_executor_compatibility_markdown,
)
from app.live_verification.live_order_real_official_settlement_route_no_post_controlled import (  # noqa: E501
    OfficialSettlementRouteNoPostInput,
    build_official_settlement_route_no_post_controlled,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)

Status = OfficialSettlementActualExecutorCompatibilityStatus

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


def _ready_input(
    **overrides: object,
) -> OfficialSettlementActualExecutorCompatibilityInput:
    values = {
        "runtime_position_status": PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        "position_count_safe": 1,
        "has_exactly_one_position": True,
        "has_multiple_positions": False,
    }
    values.update(overrides)
    return OfficialSettlementActualExecutorCompatibilityInput(**values)


def test_official_size_based_preview_builds_dedicated_executor_compatibility() -> None:
    settlement_preview = build_official_settlement_route_no_post_controlled()
    result = build_official_settlement_actual_executor_compatibility_controlled(
        settlement_preview_result=settlement_preview,
    )
    rendered = render_official_settlement_actual_executor_compatibility_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.READY_NO_POST
    assert result.dedicated_settlement_actual_executor_compatibility_ready is True
    assert result.official_settlement_executor_preview_ready is True
    assert result.official_settlement_no_post_preview_ready is True
    assert result.settlement_route_kind == "OFFICIAL_SIZE_BASED_SETTLEMENT"
    assert result.settlement_route_is_generic_order is False
    assert result.settlement_route_is_dedicated is True
    assert result.generic_order_executor_used_for_settlement is False
    assert result.live_order_once_used_for_settlement is False
    assert result.generic_order_endpoint_used_for_settlement is False
    assert result.position_specific_path_used is False
    assert result.position_specific_identifier_safe_handling_ready is False
    assert result.runtime_position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert result.position_count_safe == 1
    assert result.has_exactly_one_position is True
    assert result.has_multiple_positions is False
    assert result.actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert result.entry_post_executed is False
    assert result.generic_close_post_executed is False
    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_settlement_allowed is False
    assert result.ledger_update is False
    assert result.receipt_handoff is False
    assert result.raw_id_value_credential_header_exposure is False
    assert result.result_safe_category == (
        OFFICIAL_SETTLEMENT_RESULT_COMPATIBLE_NO_POST_SANITIZED
    )
    assert result.level5_connection.next_cycle_state == (
        NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_EXECUTOR_READY
    )
    assert "dedicated_settlement_actual_executor_compatibility_ready: true" in rendered
    assert "settlement_post_count: 0" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_no_post_transport_never_executes_http_or_generic_order_path() -> None:
    result = build_official_settlement_actual_executor_compatibility_controlled(
        _ready_input(),
    )
    transport = result.no_post_transport

    assert transport.no_post_transport_ready is True
    assert transport.dedicated_settlement_transport is True
    assert transport.generic_order_transport is False
    assert transport.fake_transport_call_count == 0
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
        ({"position_count_safe": 2}, "position_count_safe_not_1"),
        ({"has_exactly_one_position": False}, "has_exactly_one_position_required"),
    ),
)
def test_only_one_position_open_count_one_can_be_compatible(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_executor_compatibility_controlled(
        _ready_input(**override),
    )

    assert result.status is Status.BLOCKED_POSITION
    assert result.dedicated_settlement_actual_executor_compatibility_ready is False
    assert result.actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert result.multiple_positions_blocked is True
    assert result.one_position_required is True
    assert reason in result.blocked_reasons
    assert result.level5_connection.next_cycle_state == (
        NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_EXECUTOR_BLOCKED
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
            {"generic_opposite_order_as_close_forbidden": False},
            "generic_opposite_order_as_close_must_be_forbidden",
        ),
        (
            {"generic_close_primitive_revoked": False},
            "generic_close_primitive_must_be_revoked",
        ),
    ),
)
def test_generic_order_and_generic_close_paths_are_not_settlement_executors(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_executor_compatibility_controlled(
        _ready_input(**override),
    )

    expected_status = (
        Status.BLOCKED_PREVIEW
        if reason == "settlement_route_must_be_dedicated"
        else Status.BLOCKED_GENERIC_EXECUTOR
    )
    assert result.status is expected_status
    assert result.dedicated_settlement_actual_executor_compatibility_ready is False
    assert result.generic_order_executor_used_for_settlement is False
    assert result.live_order_once_used_for_settlement is False
    assert result.generic_order_endpoint_used_for_settlement is False
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
        (
            {"size_based_path_requires_raw_id": True},
            "size_based_path_must_not_require_raw_id",
        ),
    ),
)
def test_position_specific_path_stays_blocked_until_safe_id_design(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_executor_compatibility_controlled(
        _ready_input(**override),
    )

    assert result.status in {
        Status.BLOCKED_POSITION_SPECIFIC_IDENTIFIER,
        Status.BLOCKED_PREVIEW,
    }
    assert result.dedicated_settlement_actual_executor_compatibility_ready is False
    assert result.position_specific_path_used is False
    assert result.position_specific_identifier_safe_handling_ready is (
        override.get("position_specific_identifier_safe_handling_ready", False)
    )
    assert result.actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"settlement_retry_allowed": True}, "settlement_retry_allowed"),
        ({"settlement_repost_allowed": True}, "settlement_repost_allowed"),
        ({"settlement_second_post_allowed": True}, "settlement_second_post_allowed"),
        ({"entry_post_allowed": True}, "entry_post_allowed"),
        ({"generic_close_allowed": True}, "generic_close_allowed"),
        (
            {"actual_settlement_post_allowed_now": True},
            "actual_settlement_post_allowed_now",
        ),
        (
            {"actual_settlement_post_executed": True},
            "actual_settlement_post_executed",
        ),
        ({"settlement_post_count": 1}, "settlement_post_count_must_remain_0"),
        ({"no_post_transport_call_count": 1}, "no_post_transport_call_count_must_remain_0"),
        ({"ledger_update_allowed": True}, "ledger_update_allowed"),
        ({"receipt_handoff_allowed": True}, "receipt_handoff_allowed"),
    ),
)
def test_execution_lifecycle_breaks_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_executor_compatibility_controlled(
        _ready_input(**override),
    )

    assert result.dedicated_settlement_actual_executor_compatibility_ready is False
    assert result.actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert result.entry_post_executed is False
    assert result.generic_close_post_executed is False
    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_settlement_allowed is False
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
def test_raw_id_value_credential_header_exposure_attempts_are_blocked(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_executor_compatibility_controlled(
        _ready_input(**override),
    )
    rendered = render_official_settlement_actual_executor_compatibility_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_UNSAFE
    assert result.dedicated_settlement_actual_executor_compatibility_ready is False
    assert result.raw_id_value_credential_header_exposure is True
    assert result.executable_preview.raw_exposure is False
    assert result.executable_preview.id_exposure is False
    assert result.executable_preview.credential_value_exposure is False
    assert result.no_post_transport.raw_request_exposed is False
    assert result.no_post_transport.id_exposed is False
    assert reason in result.blocked_reasons
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_blocked_official_settlement_preview_blocks_compatibility() -> None:
    settlement_preview = build_official_settlement_route_no_post_controlled(
        OfficialSettlementRouteNoPostInput(
            official_settlement_route_confirmed=False,
        ),
    )
    result = build_official_settlement_actual_executor_compatibility_controlled(
        settlement_preview_result=settlement_preview,
    )

    assert result.status is Status.BLOCKED_PREVIEW
    assert result.official_settlement_no_post_preview_ready is False
    assert result.dedicated_settlement_actual_executor_compatibility_ready is False
    assert result.actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert "official_settlement_no_post_preview_not_ready" in result.blocked_reasons


def test_preview_shape_is_sanitized_settlement_specific_and_no_post() -> None:
    result = build_official_settlement_actual_executor_compatibility_controlled(
        _ready_input(),
    )
    preview = result.executable_preview

    assert preview.preview_ready is True
    assert preview.execution_step == (
        EXECUTION_STEP_OFFICIAL_SETTLEMENT_ACTUAL_EXECUTOR_COMPATIBILITY
    )
    assert preview.official_settlement_context is True
    assert preview.generic_order_context is False
    assert preview.runtime_position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert preview.position_count_safe == 1
    assert preview.settlement_route_kind == "OFFICIAL_SIZE_BASED_SETTLEMENT"
    assert preview.settlement_route_is_generic_order is False
    assert preview.settlement_route_is_dedicated is True
    assert preview.symbol_safe_label == "USD_JPY"
    assert preview.settlement_size_safe_label == "100"
    assert preview.settlement_order_type_safe_label == "MARKET"
    assert preview.one_settlement_post_max is True
    assert preview.settlement_retry_allowed is False
    assert preview.settlement_repost_allowed is False
    assert preview.settlement_second_post_allowed is False
    assert preview.actual_settlement_post_allowed_now is False
    assert preview.actual_settlement_post_executed is False
    assert preview.settlement_post_count == 0
    assert preview.entry_post_executed is False
    assert preview.generic_close_post_executed is False
    assert preview.ledger_update is False
    assert preview.receipt_handoff is False
    assert preview.raw_exposure is False
    assert preview.id_exposure is False
    assert preview.credential_value_exposure is False
    assert preview.signature_value_exposure is False
    assert preview.headers_value_exposure is False
    assert preview.actual_settlement_post_requires_separate_execution_gate is True


def test_official_settlement_compatibility_module_has_no_execution_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_official_settlement_actual_executor_compatibility_controlled.py"
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
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in blocked_modules
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module not in blocked_modules
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
