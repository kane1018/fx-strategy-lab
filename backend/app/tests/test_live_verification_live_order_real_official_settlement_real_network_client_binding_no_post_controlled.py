from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from app.live_verification.live_order_real_official_settlement_real_network_client_binding_no_post_controlled import (  # noqa: E501
    RESULT_REAL_NETWORK_CLIENT_BINDING_READY_NO_POST_SANITIZED,
    ConcreteOfficialSettlementRealNetworkClient,
    FakeHttpTransportForOfficialSettlementRealNetworkClient,
    OfficialSettlementRealNetworkClientBindingInput,
    OfficialSettlementRealNetworkClientBindingStatus,
    build_official_settlement_real_network_client_binding_no_post_controlled,
    render_official_settlement_real_network_client_binding_no_post_markdown,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)

Status = OfficialSettlementRealNetworkClientBindingStatus

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


def _ready_input(**overrides: object) -> OfficialSettlementRealNetworkClientBindingInput:
    values: dict[str, object] = {
        "runtime_position_status": PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        "position_count_safe": 1,
        "has_exactly_one_position": True,
        "has_multiple_positions": False,
    }
    values.update(overrides)
    return OfficialSettlementRealNetworkClientBindingInput(**values)


def test_real_network_client_binding_ready_path_uses_fake_transport_once() -> None:
    result = build_official_settlement_real_network_client_binding_no_post_controlled()
    rendered = render_official_settlement_real_network_client_binding_no_post_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.READY_NO_POST
    assert result.official_settlement_real_network_client_binding_confirmed is True
    assert result.official_settlement_real_network_client_callable_available is True
    assert result.official_settlement_real_network_transport_binding_ready is True
    assert (
        result.official_settlement_real_network_client_targets_official_settlement_route
        is True
    )
    assert result.official_settlement_real_network_client_targets_generic_order_route is False
    assert result.official_settlement_real_network_client_uses_generic_order_executor is False
    assert result.official_settlement_real_network_client_uses_live_order_once is False
    assert result.official_settlement_real_network_client_uses_one_shot_generic_order is False
    assert result.official_settlement_real_network_client_uses_position_specific_path is False
    assert (
        result.concrete_real_network_official_settlement_live_http_sender_adapter_confirmed
        is True
    )
    assert (
        result.concrete_real_network_official_settlement_live_http_sender_adapter_callable_available
        is True
    )
    assert (
        result.concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization
        is True
    )
    assert (
        result.real_network_client_binding_can_be_reached_after_execution_gate_authorization
        is True
    )
    assert result.next_execution_gate_can_call_real_network_client_after_confirmation is True
    assert result.fake_no_network_adapter_distinguished_from_real_network_client is True
    assert result.real_network_client_accepts_injected_transport is True
    assert result.real_network_client_code_path_exercised_with_fake_http_transport is True
    assert result.fake_http_transport_used is True
    assert result.fake_http_transport_call_count == 1
    assert result.real_http_client_call_count == 0
    assert result.real_network_client_actual_http_post_executed is False
    assert result.real_network_client_broker_write_executed is False
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
    assert result.this_step_real_network_client_invoked is False
    assert result.this_step_actual_http_post_sender_invoked is False
    assert result.this_step_actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert result.sender_call_count == 0
    assert result.transport_call_count == 0
    assert result.http_post_executed is False
    assert result.entry_post_executed is False
    assert result.generic_close_post_executed is False
    assert result.live_order_once_executed is False
    assert result.external_api_write_executed is False
    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_settlement_allowed is False
    assert result.ledger_update is False
    assert result.receipt_handoff is False
    assert result.raw_id_value_credential_header_exposure is False
    assert result.env_read is False
    assert result.next_execution_gate_still_requires_fresh_runtime_read is True
    assert result.next_execution_gate_still_requires_operator_readiness is True
    assert result.next_execution_gate_still_requires_settlement_specific_confirmation is True
    assert result.result_safe_category == RESULT_REAL_NETWORK_CLIENT_BINDING_READY_NO_POST_SANITIZED
    assert "official_settlement_real_network_client_binding_confirmed: true" in rendered
    assert "fake_http_transport_call_count: 1" in rendered
    assert "real_http_client_call_count: 0" in rendered
    assert "real_network_client_actual_http_post_executed: false" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_concrete_client_exercises_code_path_with_fake_transport() -> None:
    result = build_official_settlement_real_network_client_binding_no_post_controlled(
        _ready_input(),
    )
    client = result.concrete_real_network_client
    fake_transport = result.fake_http_transport
    plan = result.real_network_client_binding_plan
    boundary = result.real_network_client_boundary

    assert isinstance(client, ConcreteOfficialSettlementRealNetworkClient)
    assert isinstance(fake_transport, FakeHttpTransportForOfficialSettlementRealNetworkClient)
    assert client.is_real_network_client_binding is True
    assert client.is_fake_no_network_adapter is False
    assert client.accepts_injected_transport is True
    assert client.default_no_post is True
    assert client.targets_official_settlement_route is True
    assert client.targets_generic_order_route is False
    assert client.uses_generic_order_executor is False
    assert client.uses_live_order_once is False
    assert client.uses_one_shot_generic_order is False
    assert client.uses_position_specific_path is False
    assert boundary.concrete_client_is_real_network_binding is True
    assert boundary.concrete_client_is_fake_no_network_adapter is False
    assert boundary.client_accepts_injected_transport is True
    assert boundary.transport_binding_ready is True

    call_result = client.transmit_after_execution_gate_authorization_with_transport(
        plan,
        fake_transport,
    )

    assert call_result.real_network_client_code_path_exercised_with_fake_http_transport is True
    assert call_result.fake_http_transport_used is True
    assert call_result.fake_http_transport_call_count == 1
    assert call_result.real_http_client_call_count == 0
    assert call_result.real_network_client_actual_http_post_executed is False
    assert call_result.real_network_client_broker_write_executed is False
    assert call_result.simulated_settlement_post_count == 0
    assert call_result.sender_call_count == 0
    assert call_result.transport_call_count == 0
    assert call_result.http_post_executed is False
    assert call_result.external_api_write_executed is False
    assert call_result.raw_request_exposed is False
    assert call_result.raw_response_exposed is False
    assert call_result.broker_api_response_exposed is False
    assert call_result.id_exposed is False
    assert call_result.credential_value_exposed is False
    assert call_result.signature_value_exposed is False
    assert call_result.headers_value_exposed is False


@pytest.mark.parametrize(
    ("override", "reason", "status"),
    (
        ({"repository_clean": False}, "repository_clean_required", Status.BLOCKED_REPOSITORY),
        (
            {"head_equals_origin_main": False},
            "head_equals_origin_main_required",
            Status.BLOCKED_REPOSITORY,
        ),
        (
            {"credential_presence_available": False},
            "credential_presence_available_required",
            Status.BLOCKED_CREDENTIAL,
        ),
    ),
)
def test_repository_and_credential_gates_fail_closed(
    override: dict[str, object],
    reason: str,
    status: Status,
) -> None:
    result = build_official_settlement_real_network_client_binding_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status is status
    assert (
        result.real_network_client_binding_can_be_reached_after_execution_gate_authorization
        is False
    )
    assert result.next_execution_gate_can_call_real_network_client_after_confirmation is False
    assert result.real_network_client_code_path_exercised_with_fake_http_transport is False
    assert result.fake_http_transport_call_count == 0
    assert result.settlement_post_count == 0
    assert reason in result.blocked_reasons


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
def test_runtime_position_gate_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_real_network_client_binding_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status is Status.BLOCKED_POSITION
    assert result.fake_http_transport_call_count == 0
    assert result.http_post_executed is False
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        (
            {"official_settlement_no_post_preview_ready": False},
            "official_settlement_no_post_preview_ready_required",
        ),
        (
            {"dedicated_settlement_actual_executor_compatibility_ready": False},
            "dedicated_settlement_actual_executor_compatibility_ready_required",
        ),
        (
            {"dedicated_actual_official_settlement_post_executor_available": False},
            "dedicated_actual_official_settlement_post_executor_available_required",
        ),
        (
            {"dedicated_actual_official_settlement_transport_boundary_ready": False},
            "dedicated_actual_official_settlement_transport_boundary_ready_required",
        ),
        (
            {"actual_settlement_post_live_capable_transport_available": False},
            "actual_settlement_post_live_capable_transport_available_required",
        ),
        (
            {"dedicated_official_settlement_actual_http_post_sender_confirmed": False},
            "dedicated_official_settlement_actual_http_post_sender_confirmed_required",
        ),
        (
            {
                "concrete_real_network_official_settlement_live_http_sender_adapter_confirmed": (
                    False
                ),
            },
            "concrete_real_network_official_settlement_live_http_sender_adapter_confirmed_required",
        ),
        (
            {"official_settlement_real_network_client_binding_confirmed": False},
            "official_settlement_real_network_client_binding_confirmed_required",
        ),
        (
            {"official_settlement_real_network_client_callable_available": False},
            "official_settlement_real_network_client_callable_available_required",
        ),
        (
            {"official_settlement_real_network_transport_binding_ready": False},
            "official_settlement_real_network_transport_binding_ready_required",
        ),
    ),
)
def test_upstream_and_client_binding_gates_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_real_network_client_binding_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status in {
        Status.BLOCKED_CLIENT,
        Status.BLOCKED_ROUTE,
    }
    assert result.fake_http_transport_call_count == 0
    assert result.real_http_client_call_count == 0
    assert result.real_network_client_actual_http_post_executed is False
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        (
            {"official_settlement_real_network_client_targets_official_settlement_route": False},
            "official_settlement_real_network_client_targets_official_settlement_route_required",
        ),
        (
            {"official_settlement_real_network_client_targets_generic_order_route": True},
            "official_settlement_real_network_client_targets_generic_order_route",
        ),
        (
            {"official_settlement_real_network_client_uses_generic_order_executor": True},
            "official_settlement_real_network_client_uses_generic_order_executor",
        ),
        (
            {"official_settlement_real_network_client_uses_live_order_once": True},
            "official_settlement_real_network_client_uses_live_order_once",
        ),
        (
            {"official_settlement_real_network_client_uses_one_shot_generic_order": True},
            "official_settlement_real_network_client_uses_one_shot_generic_order",
        ),
        (
            {"official_settlement_real_network_client_uses_position_specific_path": True},
            "official_settlement_real_network_client_uses_position_specific_path",
        ),
        ({"settlement_route_is_generic_order": True}, "settlement_route_is_generic_order"),
        ({"settlement_route_is_dedicated": False}, "settlement_route_is_dedicated_required"),
        (
            {"generic_order_executor_used_for_settlement": True},
            "generic_order_executor_used_for_settlement",
        ),
        ({"live_order_once_used_for_settlement": True}, "live_order_once_used_for_settlement"),
        (
            {"one_shot_generic_order_path_used_for_settlement": True},
            "one_shot_generic_order_path_used_for_settlement",
        ),
        ({"position_specific_path_used": True}, "position_specific_path_used"),
    ),
)
def test_route_and_forbidden_path_gates_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_real_network_client_binding_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status in {
        Status.BLOCKED_ROUTE,
        Status.BLOCKED_CLIENT,
        Status.BLOCKED_POSITION,
    }
    assert result.fake_http_transport_call_count == 0
    assert result.http_post_executed is False
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason", "status"),
    (
        (
            {"operator_broker_ui_checked": False},
            "operator_broker_ui_checked_required",
            Status.BLOCKED_OPERATOR,
        ),
        (
            {"operator_broker_ui_open_position_visible": False},
            "operator_broker_ui_open_position_visible_required",
            Status.BLOCKED_OPERATOR,
        ),
        (
            {"operator_broker_ui_values_or_ids_provided": True},
            "operator_broker_ui_values_or_ids_provided",
            Status.BLOCKED_OPERATOR,
        ),
        (
            {"operator_can_monitor": False},
            "operator_can_monitor_required",
            Status.BLOCKED_OPERATOR,
        ),
        (
            {"operator_approves_settlement_attempt": False},
            "operator_approves_settlement_attempt_required",
            Status.BLOCKED_OPERATOR,
        ),
        (
            {"sanitized_settlement_preview_shown": False},
            "sanitized_settlement_preview_shown_required",
            Status.BLOCKED_CONFIRMATION,
        ),
        (
            {"settlement_specific_confirmation_current_turn": False},
            "settlement_specific_confirmation_current_turn_required",
            Status.BLOCKED_CONFIRMATION,
        ),
        (
            {"settlement_specific_confirmation_exact_match": False},
            "settlement_specific_confirmation_exact_match_required",
            Status.BLOCKED_CONFIRMATION,
        ),
    ),
)
def test_operator_and_confirmation_gates_fail_closed(
    override: dict[str, object],
    reason: str,
    status: Status,
) -> None:
    result = build_official_settlement_real_network_client_binding_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status is status
    assert result.fake_http_transport_call_count == 0
    assert result.real_network_client_actual_http_post_executed is False
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"retry_allowed": True}, "retry_allowed"),
        ({"repost_allowed": True}, "repost_allowed"),
        ({"second_settlement_allowed": True}, "second_settlement_allowed"),
        ({"entry_post_allowed": True}, "entry_post_allowed"),
        ({"generic_close_allowed": True}, "generic_close_allowed"),
        ({"ledger_update_allowed": True}, "ledger_update_allowed"),
        ({"receipt_handoff_allowed": True}, "receipt_handoff_allowed"),
        (
            {"raw_id_value_credential_header_exposure": True},
            "raw_id_value_credential_header_exposure",
        ),
        (
            {"real_network_client_actual_http_post_executed": True},
            "real_network_client_actual_http_post_executed",
        ),
        (
            {"real_network_client_broker_write_executed": True},
            "real_network_client_broker_write_executed",
        ),
        ({"this_step_real_network_client_invoked": True}, "this_step_real_network_client_invoked"),
        (
            {"this_step_actual_http_post_sender_invoked": True},
            "this_step_actual_http_post_sender_invoked",
        ),
        (
            {"this_step_actual_settlement_post_executed": True},
            "this_step_actual_settlement_post_executed",
        ),
        ({"settlement_post_count": 1}, "settlement_post_count_must_be_0"),
        ({"sender_call_count": 1}, "sender_call_count_must_be_0"),
        ({"transport_call_count": 1}, "transport_call_count_must_be_0"),
        ({"http_post_executed": True}, "http_post_executed"),
        ({"entry_post_executed": True}, "entry_post_executed"),
        ({"generic_close_post_executed": True}, "generic_close_post_executed"),
        ({"live_order_once_executed": True}, "live_order_once_executed"),
        ({"external_api_write_executed": True}, "external_api_write_executed"),
        ({"env_read": True}, "env_read"),
    ),
)
def test_lifecycle_and_exposure_gates_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_real_network_client_binding_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status in {
        Status.BLOCKED_LIFECYCLE,
        Status.BLOCKED_UNSAFE,
    }
    assert result.fake_http_transport_call_count == 0
    assert result.settlement_post_count == 0
    assert result.sender_call_count == 0
    assert result.transport_call_count == 0
    assert result.http_post_executed is False
    assert reason in result.blocked_reasons


def test_rendered_markdown_and_payload_do_not_surface_forbidden_sentinels() -> None:
    result = build_official_settlement_real_network_client_binding_no_post_controlled()
    rendered = render_official_settlement_real_network_client_binding_no_post_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert "raw_id_value_credential_header_exposure: false" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in rendered
        assert forbidden not in payload


def test_module_has_no_direct_http_private_api_or_generic_order_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_official_settlement_real_network_client_binding_no_post_controlled.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app.brokers",
        "app.private_api",
        "app.live_verification.live_order_once",
    }
    blocked_call_names = {
        "post",
        "put",
        "delete",
        "request",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "pbcopy",
        "read_text",
        "write_text",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name not in blocked_modules for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in blocked_modules
        if isinstance(node, ast.Call):
            call = node.func.attr if isinstance(node.func, ast.Attribute) else None
            assert call not in blocked_call_names
