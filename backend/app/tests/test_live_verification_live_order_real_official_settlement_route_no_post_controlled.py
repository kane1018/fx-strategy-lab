from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification import (
    live_order_real_official_settlement_route_no_post_controlled as preview,
)

RAW_REQUEST_SENTINEL = "RAW_REQUEST_SHOULD_NOT_SURFACE"
RAW_ENDPOINT_SENTINEL = "RAW_ENDPOINT_SHOULD_NOT_SURFACE"
RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
BROKER_API_RESPONSE_SENTINEL = "BROKER_API_RESPONSE_SHOULD_NOT_SURFACE"
POSITION_ID_SENTINEL = "POSITION_ID_SHOULD_NOT_SURFACE"
ACCOUNT_ID_SENTINEL = "ACCOUNT_ID_SHOULD_NOT_SURFACE"
ORDER_ID_SENTINEL = "ORDER_ID_SHOULD_NOT_SURFACE"
TRANSACTION_ID_SENTINEL = "TRANSACTION_ID_SHOULD_NOT_SURFACE"
CREDENTIAL_VALUE_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"

_FORBIDDEN_SENTINELS = (
    RAW_REQUEST_SENTINEL,
    RAW_ENDPOINT_SENTINEL,
    RAW_RESPONSE_SENTINEL,
    BROKER_API_RESPONSE_SENTINEL,
    POSITION_ID_SENTINEL,
    ACCOUNT_ID_SENTINEL,
    ORDER_ID_SENTINEL,
    TRANSACTION_ID_SENTINEL,
    CREDENTIAL_VALUE_SENTINEL,
    SIGNATURE_VALUE_SENTINEL,
    HEADERS_VALUE_SENTINEL,
)


def _ready_input(**overrides: object) -> preview.OfficialSettlementRouteNoPostInput:
    values = {
        "official_settlement_route_confirmed": True,
        "official_settlement_route_confirmation_basis": (
            preview.OFFICIAL_SETTLEMENT_ROUTE_CONFIRMATION_BASIS
        ),
        "generic_opposite_order_as_close_forbidden": True,
        "generic_close_primitive_revoked": True,
        "size_based_path_exists": True,
        "size_based_path_requires_raw_id": False,
        "position_specific_path_exists": True,
        "position_specific_identifier_required": True,
        "position_specific_identifier_safe_handling_ready": False,
        "settlement_side_semantics_confirmed": True,
    }
    values.update(overrides)
    return preview.OfficialSettlementRouteNoPostInput(**values)


def test_official_settlement_route_confirmed_builds_no_post_preview() -> None:
    result = preview.build_official_settlement_route_no_post_controlled(_ready_input())
    rendered = preview.render_official_settlement_route_no_post_markdown(result)
    payload = repr(asdict(result))

    assert result.case is preview.OfficialSettlementRouteNoPostCase.CASE_1
    assert result.status is preview.OfficialSettlementRouteNoPostStatus.READY_NO_POST
    assert result.official_settlement_no_post_preview_ready is True
    assert result.preview.official_settlement_route_confirmed is True
    assert (
        result.preview.official_settlement_route_confirmation_basis
        == preview.OFFICIAL_SETTLEMENT_ROUTE_CONFIRMATION_BASIS
    )
    assert result.preview.settlement_route_kind == (
        preview.SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED
    )
    assert result.preview.settlement_route_is_dedicated is True
    assert result.preview.settlement_route_is_generic_order is False
    assert result.preview.settlement_route_invocation_deferred is True
    assert result.preview.actual_settlement_post_allowed_now is False
    assert result.preview.actual_close_post_allowed_now is False
    assert result.preview.symbol_safe_label == "USD_JPY"
    assert result.preview.settlement_size_safe_label == "100"
    assert result.preview.settlement_order_type_safe_label == "MARKET"
    assert result.preview.settlement_side_semantics_safe_label == (
        preview.SETTLEMENT_SIDE_SEMANTICS_CONFIRMED
    )
    assert result.preview.one_settlement_post_max is True
    assert result.preview.settlement_retry_allowed is False
    assert result.preview.settlement_repost_allowed is False
    assert result.preview.settlement_second_post_allowed is False
    assert result.actual_entry_post is False
    assert result.actual_close_post is False
    assert result.actual_settlement_post is False
    assert result.retry_repost is False
    assert result.second_close_post is False
    assert result.ledger_update is False
    assert result.receipt_handoff is False
    assert "official_settlement_no_post_preview_ready: true" in rendered
    assert "actual_settlement_post_allowed_now: false" in rendered
    assert "raw_endpoint_exposed: false" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_generic_opposite_order_and_generic_close_primitive_remain_blocked() -> None:
    result = preview.build_official_settlement_route_no_post_controlled(
        _ready_input(generic_opposite_order_as_close_forbidden=False),
    )

    assert result.case is preview.OfficialSettlementRouteNoPostCase.CASE_2
    assert result.official_settlement_no_post_preview_ready is False
    assert result.preview.settlement_route_is_generic_order is False
    assert result.preview.actual_settlement_post_allowed_now is False
    assert "generic_opposite_order_as_close_not_forbidden" in result.blocked_reasons

    primitive_result = preview.build_official_settlement_route_no_post_controlled(
        _ready_input(generic_close_primitive_revoked=False),
    )

    assert primitive_result.case is preview.OfficialSettlementRouteNoPostCase.CASE_2
    assert primitive_result.preview.actual_close_post_allowed_now is False
    assert "generic_close_primitive_not_revoked" in primitive_result.blocked_reasons


def test_size_based_preview_does_not_expose_raw_request_or_endpoint() -> None:
    result = preview.build_official_settlement_route_no_post_controlled(_ready_input())

    assert result.size_based_path_exists is True
    assert result.size_based_path_requires_raw_id is False
    assert result.size_based_preview_allowed is True
    assert result.size_based_preview_raw_request_exposed is False
    assert result.size_based_preview_raw_endpoint_exposed is False
    assert result.preview.raw_request_exposed is False
    assert result.preview.raw_endpoint_exposed is False


def test_position_specific_path_exists_but_safe_id_handling_false_blocks_that_path() -> None:
    result = preview.build_official_settlement_route_no_post_controlled(_ready_input())

    assert result.position_specific_path_exists is True
    assert result.position_specific_identifier_required is True
    assert result.position_specific_identifier_safe_handling_ready is False
    assert result.position_specific_preview_allowed is False
    assert result.position_specific_execution_blocked_reason == (
        preview.POSITION_SPECIFIC_BLOCKED_REASON_SAFE_ID_NOT_READY
    )
    assert result.preview.position_id_exposed is False


def test_position_specific_identifier_only_path_blocks_without_safe_handling() -> None:
    result = preview.build_official_settlement_route_no_post_controlled(
        _ready_input(
            size_based_path_exists=False,
            size_based_path_requires_raw_id=None,
            position_specific_path_exists=True,
            position_specific_identifier_required=True,
            position_specific_identifier_safe_handling_ready=False,
        ),
    )

    assert result.case is preview.OfficialSettlementRouteNoPostCase.CASE_3
    assert result.status is (
        preview.OfficialSettlementRouteNoPostStatus.BLOCKED_UNSAFE_IDENTIFIER
    )
    assert result.official_settlement_no_post_preview_ready is False
    assert result.preview.actual_settlement_post_allowed_now is False
    assert "position_specific_safe_identifier_handling_not_ready" in (
        result.blocked_reasons
    )


def test_position_id_and_raw_value_attempt_sentinels_are_blocked() -> None:
    result = preview.build_official_settlement_route_no_post_controlled(
        _ready_input(
            raw_request_exposure_attempted=True,
            raw_endpoint_exposure_attempted=True,
            raw_response_exposure_attempted=True,
            broker_api_response_exposure_attempted=True,
            position_id_exposure_attempted=True,
            account_id_exposure_attempted=True,
            order_id_exposure_attempted=True,
            transaction_id_exposure_attempted=True,
            credential_value_exposure_attempted=True,
            signature_value_exposure_attempted=True,
            headers_value_exposure_attempted=True,
        ),
    )
    rendered = preview.render_official_settlement_route_no_post_markdown(result)
    payload = repr(asdict(result))

    assert result.case is preview.OfficialSettlementRouteNoPostCase.CASE_4
    assert result.status is (
        preview.OfficialSettlementRouteNoPostStatus.BLOCKED_UNSAFE_EXPOSURE
    )
    assert result.preview.raw_request_exposed is False
    assert result.preview.raw_response_exposed is False
    assert result.preview.broker_api_response_exposed is False
    assert result.preview.position_id_exposed is False
    assert result.preview.credential_value_exposed is False
    assert "raw_id_value_exposure_attempted" in result.blocked_reasons
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_settlement_side_semantics_unclear_blocks_preview() -> None:
    result = preview.build_official_settlement_route_no_post_controlled(
        _ready_input(settlement_side_semantics_confirmed=False),
    )

    assert result.case is preview.OfficialSettlementRouteNoPostCase.CASE_2
    assert result.status is preview.OfficialSettlementRouteNoPostStatus.BLOCKED_SEMANTICS
    assert result.official_settlement_no_post_preview_ready is False
    assert result.preview.settlement_side_semantics_safe_label == (
        preview.SETTLEMENT_SIDE_SEMANTICS_BLOCKED
    )
    assert result.preview.actual_settlement_post_allowed_now is False


def test_level5_moves_to_preview_ready_no_post_only() -> None:
    result = preview.build_official_settlement_route_no_post_controlled(_ready_input())

    assert result.level5_connection.previous_cycle_state == (
        preview.PREVIOUS_CYCLE_STATE_OFFICIAL_SETTLEMENT_REVIEWED
    )
    assert result.level5_connection.next_cycle_state == (
        preview.NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_PREVIEW_READY
    )
    assert result.level5_connection.settlement_execution_gate_may_be_planned is True
    assert result.level5_connection.settlement_post_executed_reached is False
    assert result.level5_connection.close_post_executed_reached is False
    assert result.level5_connection.post_close_position_confirmation_reached is False
    assert result.level5_connection.ledger_updated_reached is False
    assert result.level5_connection.receipt_handoff_reached is False
    assert result.level5_connection.level5_minimal_cycle_completed is False
    assert result.level5_connection.level5_full_auto_cycle_completed is False


def test_unsafe_execution_attempts_remain_false_in_result() -> None:
    result = preview.build_official_settlement_route_no_post_controlled(
        _ready_input(
            actual_entry_post_attempted_this_step=True,
            actual_close_post_attempted_this_step=True,
            actual_settlement_post_attempted_this_step=True,
            retry_attempted_this_step=True,
            repost_attempted_this_step=True,
            second_close_post_attempted_this_step=True,
        ),
    )

    assert result.case is preview.OfficialSettlementRouteNoPostCase.CASE_4
    assert result.actual_entry_post is False
    assert result.actual_close_post is False
    assert result.actual_settlement_post is False
    assert result.retry_repost is False
    assert result.second_close_post is False
    assert result.preview.actual_settlement_post_allowed_now is False
    assert "actual_entry_post_attempted" in result.blocked_reasons
    assert "actual_close_post_attempted" in result.blocked_reasons
    assert "actual_settlement_post_attempted" in result.blocked_reasons


def test_official_settlement_no_post_module_has_no_execution_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_official_settlement_route_no_post_controlled.py"
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
