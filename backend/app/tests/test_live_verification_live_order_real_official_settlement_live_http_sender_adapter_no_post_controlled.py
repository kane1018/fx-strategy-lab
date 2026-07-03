from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from app.live_verification.live_order_real_official_settlement_live_http_sender_adapter_no_post_controlled import (  # noqa: E501
    RESULT_LIVE_HTTP_SENDER_ADAPTER_READY_NO_POST_SANITIZED,
    ConcreteOfficialSettlementLiveHttpSenderAdapter,
    FakeHttpClientForOfficialSettlementLiveSender,
    OfficialSettlementLiveHttpSenderAdapterInput,
    OfficialSettlementLiveHttpSenderAdapterStatus,
    build_official_settlement_live_http_sender_adapter_no_post_controlled,
    render_official_settlement_live_http_sender_adapter_no_post_markdown,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)

Status = OfficialSettlementLiveHttpSenderAdapterStatus

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


def _ready_input(**overrides: object) -> OfficialSettlementLiveHttpSenderAdapterInput:
    values: dict[str, object] = {
        "runtime_position_status": PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        "position_count_safe": 1,
        "has_exactly_one_position": True,
        "has_multiple_positions": False,
    }
    values.update(overrides)
    return OfficialSettlementLiveHttpSenderAdapterInput(**values)


def test_live_sender_adapter_ready_path_uses_fake_http_client_once() -> None:
    result = build_official_settlement_live_http_sender_adapter_no_post_controlled()
    rendered = render_official_settlement_live_http_sender_adapter_no_post_markdown(result)
    payload = repr(asdict(result))

    assert result.status is Status.READY_NO_POST
    assert result.dedicated_official_settlement_live_http_sender_adapter_confirmed is True
    assert result.dedicated_official_settlement_live_http_sender_adapter_callable_available is True
    assert result.dedicated_official_settlement_live_http_sender_adapter_boundary_ready is True
    assert (
        result.dedicated_official_settlement_live_http_sender_adapter_uses_official_settlement_route
        is True
    )
    assert (
        result.dedicated_official_settlement_live_http_sender_adapter_uses_generic_order_route
        is False
    )
    assert (
        result.dedicated_official_settlement_live_http_sender_adapter_uses_generic_order_executor
        is False
    )
    assert (
        result.dedicated_official_settlement_live_http_sender_adapter_uses_live_order_once
        is False
    )
    assert (
        result.dedicated_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order
        is False
    )
    assert (
        result.dedicated_official_settlement_live_http_sender_adapter_uses_position_specific_path
        is False
    )
    assert result.dedicated_official_settlement_actual_http_post_sender_confirmed is True
    assert result.dedicated_official_settlement_actual_http_post_sender_callable_available is True
    assert result.actual_settlement_post_live_capable_transport_available is True
    assert result.actual_settlement_post_can_be_allowed_after_fresh_execution_gates is True
    assert result.live_sender_adapter_can_be_reached_after_execution_gate_authorization is True
    assert result.next_execution_gate_can_call_live_http_sender_adapter_after_confirmation is True
    assert result.live_sender_adapter_code_path_exercised_with_fake_http_client is True
    assert result.fake_http_client_used is True
    assert result.fake_http_client_call_count == 1
    assert result.real_http_client_call_count == 0
    assert result.live_sender_adapter_real_http_post_executed is False
    assert result.live_sender_adapter_broker_write_executed is False
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
    assert result.raw_id_value_credential_header_exposure is False
    assert result.env_read is False
    assert result.result_safe_category == RESULT_LIVE_HTTP_SENDER_ADAPTER_READY_NO_POST_SANITIZED
    assert "dedicated_official_settlement_live_http_sender_adapter_confirmed: true" in rendered
    assert "fake_http_client_call_count: 1" in rendered
    assert "live_sender_adapter_real_http_post_executed: false" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_concrete_adapter_exercises_code_path_with_fake_client() -> None:
    result = build_official_settlement_live_http_sender_adapter_no_post_controlled(
        _ready_input(),
    )
    adapter = result.concrete_live_adapter
    fake_client = result.fake_http_client
    plan = result.live_adapter_plan

    assert isinstance(adapter, ConcreteOfficialSettlementLiveHttpSenderAdapter)
    assert isinstance(fake_client, FakeHttpClientForOfficialSettlementLiveSender)
    assert adapter.uses_official_settlement_route is True
    assert adapter.uses_generic_order_route is False
    assert adapter.uses_generic_order_executor is False
    assert adapter.uses_live_order_once is False
    assert adapter.uses_one_shot_generic_order is False
    assert adapter.uses_position_specific_path is False

    call_result = adapter.exercise_authorized_no_post_code_path(plan, fake_client)

    assert call_result.live_sender_adapter_code_path_exercised_with_fake_http_client is True
    assert call_result.fake_http_client_used is True
    assert call_result.fake_http_client_call_count == 1
    assert call_result.real_http_client_call_count == 0
    assert call_result.live_sender_adapter_real_http_post_executed is False
    assert call_result.live_sender_adapter_broker_write_executed is False
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
    result = build_official_settlement_live_http_sender_adapter_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status is status
    assert result.live_sender_adapter_can_be_reached_after_execution_gate_authorization is False
    assert result.next_execution_gate_can_call_live_http_sender_adapter_after_confirmation is False
    assert result.live_sender_adapter_code_path_exercised_with_fake_http_client is False
    assert result.fake_http_client_call_count == 0
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
                "has_multiple_positions": True,
            },
            "has_multiple_positions_blocked",
        ),
    ),
)
def test_runtime_position_gates_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_live_http_sender_adapter_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status is Status.BLOCKED_POSITION
    assert result.live_sender_adapter_can_be_reached_after_execution_gate_authorization is False
    assert result.fake_http_client_call_count == 0
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
            "operator_broker_ui_values_or_ids_provided_blocked",
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
    result = build_official_settlement_live_http_sender_adapter_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status is status
    assert result.live_sender_adapter_can_be_reached_after_execution_gate_authorization is False
    assert result.fake_http_client_call_count == 0
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        (
            {"dedicated_official_settlement_live_http_sender_adapter_confirmed": False},
            "dedicated_official_settlement_live_http_sender_adapter_confirmed_required",
        ),
        (
            {
                "dedicated_official_settlement_live_http_sender_adapter_callable_available": False,
            },
            "dedicated_official_settlement_live_http_sender_adapter_callable_available_required",
        ),
        (
            {"dedicated_official_settlement_live_http_sender_adapter_boundary_ready": False},
            "dedicated_official_settlement_live_http_sender_adapter_boundary_ready_required",
        ),
        (
            {
                (
                    "dedicated_official_settlement_live_http_sender_adapter_uses_"
                    "official_settlement_route"
                ): False,
            },
            "live_sender_adapter_must_use_official_settlement_route",
        ),
        (
            {
                (
                    "dedicated_official_settlement_live_http_sender_adapter_uses_"
                    "generic_order_route"
                ): True,
            },
            "live_sender_adapter_uses_generic_order_route",
        ),
        (
            {
                (
                    "dedicated_official_settlement_live_http_sender_adapter_uses_"
                    "generic_order_executor"
                ): True,
            },
            "live_sender_adapter_uses_generic_order_executor",
        ),
        (
            {
                "dedicated_official_settlement_live_http_sender_adapter_uses_live_order_once": True,
            },
            "live_sender_adapter_uses_live_order_once",
        ),
        (
            {
                (
                    "dedicated_official_settlement_live_http_sender_adapter_uses_"
                    "one_shot_generic_order"
                ): True,
            },
            "live_sender_adapter_uses_one_shot_generic_order",
        ),
        (
            {
                (
                    "dedicated_official_settlement_live_http_sender_adapter_uses_"
                    "position_specific_path"
                ): True,
            },
            "live_sender_adapter_uses_position_specific_path",
        ),
    ),
)
def test_live_adapter_gates_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_live_http_sender_adapter_no_post_controlled(
        _ready_input(**override),
    )

    assert result.live_sender_adapter_can_be_reached_after_execution_gate_authorization is False
    assert result.next_execution_gate_can_call_live_http_sender_adapter_after_confirmation is False
    assert result.fake_http_client_call_count == 0
    assert result.http_post_executed is False
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"settlement_route_is_generic_order": True}, "settlement_route_must_not_be_generic_order"),
        ({"settlement_route_is_dedicated": False}, "settlement_route_must_be_dedicated"),
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
def test_route_misuse_gates_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_live_http_sender_adapter_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status in {Status.BLOCKED_ROUTE, Status.BLOCKED_SENDER}
    assert result.fake_http_client_call_count == 0
    assert result.http_post_executed is False
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
        ({"http_post_executed": True}, "http_post_executed"),
        ({"external_api_write_executed": True}, "external_api_write_executed"),
        (
            {"live_sender_adapter_real_http_post_executed": True},
            "live_sender_adapter_real_http_post_executed",
        ),
        (
            {"live_sender_adapter_broker_write_executed": True},
            "live_sender_adapter_broker_write_executed",
        ),
    ),
)
def test_lifecycle_and_exposure_gates_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_live_http_sender_adapter_no_post_controlled(
        _ready_input(**override),
    )

    assert result.live_sender_adapter_can_be_reached_after_execution_gate_authorization is False
    assert result.fake_http_client_call_count == 0
    assert result.http_post_executed is False
    assert reason in result.blocked_reasons


def test_live_sender_adapter_module_has_no_http_secret_or_generic_order_imports() -> None:
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
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_official_settlement_live_http_sender_adapter_no_post_controlled.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name not in blocked_modules for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not any(
                module == blocked or module.startswith(f"{blocked}.")
                for blocked in blocked_modules
            )
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
