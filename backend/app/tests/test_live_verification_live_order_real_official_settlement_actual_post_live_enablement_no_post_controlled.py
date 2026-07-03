from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from app.live_verification.live_order_real_official_settlement_actual_executor_transport_no_post_controlled import (  # noqa: E501
    build_official_settlement_actual_executor_transport_no_post_controlled,
)
from app.live_verification.live_order_real_official_settlement_actual_post_live_enablement_no_post_controlled import (  # noqa: E501
    RESULT_ACTUAL_POST_LIVE_ENABLEMENT_READY_NO_POST_SANITIZED,
    OfficialSettlementActualPostLiveEnablementInput,
    OfficialSettlementActualPostLiveEnablementStatus,
    build_official_settlement_actual_post_live_enablement_no_post_controlled,
    render_official_settlement_actual_post_live_enablement_no_post_markdown,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)

Status = OfficialSettlementActualPostLiveEnablementStatus

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
) -> OfficialSettlementActualPostLiveEnablementInput:
    values: dict[str, object] = {
        "runtime_position_status": PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        "position_count_safe": 1,
        "has_exactly_one_position": True,
        "has_multiple_positions": False,
    }
    values.update(overrides)
    return OfficialSettlementActualPostLiveEnablementInput(**values)


def test_live_enablement_from_transport_allows_only_fake_simulation() -> None:
    transport = build_official_settlement_actual_executor_transport_no_post_controlled()
    result = build_official_settlement_actual_post_live_enablement_no_post_controlled(
        transport_result=transport,
    )
    rendered = render_official_settlement_actual_post_live_enablement_no_post_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.READY_NO_POST
    assert result.actual_settlement_post_live_capable_transport_available is True
    assert result.actual_settlement_post_can_be_allowed_after_fresh_execution_gates is True
    assert result.execution_gate_simulation_can_set_actual_settlement_post_allowed_now is True
    assert result.simulated_actual_settlement_post_allowed_now is True
    assert result.execution_gate_simulation_uses_fake_transport is True
    assert result.execution_gate_simulation_http_post_executed is False
    assert result.simulated_settlement_post_count == 0
    assert result.this_step_actual_settlement_post_allowed_now is False
    assert result.this_step_actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert result.transport_call_count == 0
    assert result.http_post_executed is False
    assert result.entry_post_executed is False
    assert result.generic_close_post_executed is False
    assert result.live_order_once_executed is False
    assert result.external_api_write_executed is False
    assert result.raw_id_value_credential_header_exposure is False
    assert result.env_read is False
    assert result.next_execution_gate_can_attempt_actual_settlement_post_after_confirmation is True
    assert result.next_execution_gate_still_requires_fresh_runtime_read is True
    assert result.next_execution_gate_still_requires_operator_readiness is True
    assert result.next_execution_gate_still_requires_settlement_specific_confirmation is True
    assert result.result_safe_category == (
        RESULT_ACTUAL_POST_LIVE_ENABLEMENT_READY_NO_POST_SANITIZED
    )
    assert "simulated_actual_settlement_post_allowed_now: true" in rendered
    assert "this_step_actual_settlement_post_allowed_now: false" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_authorization_records_required_fresh_execution_gates() -> None:
    result = build_official_settlement_actual_post_live_enablement_no_post_controlled(
        _ready_input(),
    )
    authorization = result.gate_authorization
    fake_transport = result.fake_transport

    assert authorization.authorization_ready is True
    assert authorization.actual_settlement_post_can_be_allowed_after_fresh_execution_gates is True
    assert (
        authorization.execution_gate_simulation_can_set_actual_settlement_post_allowed_now
        is True
    )
    assert authorization.simulated_actual_settlement_post_allowed_now is True
    assert authorization.execution_gate_simulation_requires_repository_clean is True
    assert authorization.execution_gate_simulation_requires_head_equals_origin_main is True
    assert authorization.execution_gate_simulation_requires_credential_presence is True
    assert authorization.execution_gate_simulation_requires_runtime_position_one_count_one is True
    assert authorization.execution_gate_simulation_requires_operator_readiness is True
    assert authorization.execution_gate_simulation_requires_settlement_specific_confirmation is True
    assert authorization.one_settlement_post_max is True
    assert authorization.retry_allowed is False
    assert authorization.repost_allowed is False
    assert authorization.second_settlement_allowed is False
    assert authorization.entry_post_allowed is False
    assert authorization.generic_close_allowed is False
    assert authorization.ledger_update_allowed is False
    assert authorization.receipt_handoff_allowed is False

    assert fake_transport.execution_gate_simulation_uses_fake_transport is True
    assert fake_transport.execution_gate_simulation_http_post_executed is False
    assert fake_transport.simulated_settlement_post_count == 0
    assert fake_transport.transport_call_count == 0
    assert fake_transport.http_post_executed is False
    assert fake_transport.external_api_write_executed is False
    assert fake_transport.raw_request_exposed is False
    assert fake_transport.raw_response_exposed is False
    assert fake_transport.broker_api_response_exposed is False
    assert fake_transport.id_exposed is False
    assert fake_transport.credential_value_exposed is False
    assert fake_transport.signature_value_exposed is False
    assert fake_transport.headers_value_exposed is False


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"repository_clean": False}, "repository_clean_required"),
        ({"head_equals_origin_main": False}, "head_equals_origin_main_required"),
        (
            {"credential_presence_available": False},
            "credential_presence_available_required",
        ),
    ),
)
def test_repository_and_credential_gates_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_post_live_enablement_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status in {Status.BLOCKED_REPOSITORY, Status.BLOCKED_CREDENTIAL}
    assert result.execution_gate_simulation_can_set_actual_settlement_post_allowed_now is False
    assert result.simulated_actual_settlement_post_allowed_now is False
    assert result.actual_settlement_post_live_capable_transport_available is False
    assert result.this_step_actual_settlement_post_executed is False
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
    result = build_official_settlement_actual_post_live_enablement_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status is Status.BLOCKED_POSITION
    assert result.execution_gate_simulation_can_set_actual_settlement_post_allowed_now is False
    assert result.simulated_actual_settlement_post_allowed_now is False
    assert result.settlement_post_count == 0
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        (
            {"official_settlement_no_post_preview_ready": False},
            "official_settlement_no_post_preview_not_ready",
        ),
        (
            {"dedicated_settlement_actual_executor_compatibility_ready": False},
            "dedicated_settlement_actual_executor_compatibility_not_ready",
        ),
        (
            {"dedicated_actual_official_settlement_post_executor_available": False},
            "dedicated_actual_official_settlement_post_executor_not_available",
        ),
        (
            {"dedicated_actual_official_settlement_transport_boundary_ready": False},
            "dedicated_actual_official_settlement_transport_boundary_not_ready",
        ),
        (
            {"actual_settlement_post_live_capable_transport_available": False},
            "actual_settlement_post_live_capable_transport_not_available",
        ),
        (
            {"next_execution_gate_can_detect_actual_executor": False},
            "next_execution_gate_cannot_detect_actual_executor",
        ),
    ),
)
def test_preview_compatibility_and_transport_gates_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_post_live_enablement_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status is Status.BLOCKED_TRANSPORT
    assert result.execution_gate_simulation_can_set_actual_settlement_post_allowed_now is False
    assert result.simulated_actual_settlement_post_allowed_now is False
    assert result.this_step_actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
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
        ({"position_specific_path_used": True}, "position_specific_path_used"),
        (
            {"position_specific_identifier_safe_handling_ready": True},
            "position_specific_identifier_handling_not_this_step",
        ),
        (
            {"position_specific_preview_allowed": True},
            "position_specific_preview_must_remain_blocked",
        ),
    ),
)
def test_route_generic_one_shot_and_position_specific_paths_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_post_live_enablement_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status in {Status.BLOCKED_ROUTE, Status.BLOCKED_TRANSPORT}
    assert result.generic_order_executor_used_for_settlement is False
    assert result.live_order_once_used_for_settlement is False
    assert result.generic_order_endpoint_used_for_settlement is False
    assert result.one_shot_generic_order_path_used_for_settlement is False
    assert result.position_specific_path_used is False
    assert result.execution_gate_simulation_can_set_actual_settlement_post_allowed_now is False
    assert result.settlement_post_count == 0
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"operator_broker_ui_checked": False}, "operator_broker_ui_checked_required"),
        (
            {"operator_broker_ui_open_position_visible": False},
            "operator_broker_ui_open_position_visible_required",
        ),
        (
            {"operator_broker_ui_values_or_ids_provided": True},
            "operator_broker_ui_values_or_ids_provided_blocked",
        ),
        ({"operator_can_monitor": False}, "operator_can_monitor_required"),
        (
            {"operator_approves_settlement_attempt": False},
            "operator_approves_settlement_attempt_required",
        ),
    ),
)
def test_operator_readiness_gate_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_post_live_enablement_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status is Status.BLOCKED_OPERATOR
    assert result.execution_gate_simulation_can_set_actual_settlement_post_allowed_now is False
    assert result.simulated_actual_settlement_post_allowed_now is False
    assert result.settlement_post_count == 0
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        (
            {"sanitized_settlement_preview_shown": False},
            "sanitized_settlement_preview_required",
        ),
        (
            {"settlement_specific_confirmation_current_turn": False},
            "settlement_specific_confirmation_current_turn_required",
        ),
        (
            {"settlement_specific_confirmation_exact_match": False},
            "settlement_specific_confirmation_exact_match_required",
        ),
    ),
)
def test_preview_and_confirmation_gates_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_post_live_enablement_no_post_controlled(
        _ready_input(**override),
    )

    expected_status = (
        Status.BLOCKED_TRANSPORT
        if reason == "sanitized_settlement_preview_required"
        else Status.BLOCKED_CONFIRMATION
    )
    assert result.status is expected_status
    assert result.execution_gate_simulation_can_set_actual_settlement_post_allowed_now is False
    assert result.simulated_actual_settlement_post_allowed_now is False
    assert result.settlement_post_count == 0
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
            {"this_step_actual_settlement_post_allowed_now": True},
            "this_step_actual_settlement_post_allowed_now",
        ),
        (
            {"this_step_actual_settlement_post_executed": True},
            "this_step_actual_settlement_post_executed",
        ),
        ({"settlement_post_count": 1}, "settlement_post_count_must_remain_0"),
        ({"transport_call_count": 1}, "transport_call_count_must_remain_0"),
        ({"http_post_executed": True}, "http_post_executed"),
        ({"entry_post_executed": True}, "entry_post_executed"),
        ({"generic_close_post_executed": True}, "generic_close_post_executed"),
        ({"live_order_once_executed": True}, "live_order_once_executed"),
        ({"external_api_write_executed": True}, "external_api_write_executed"),
        (
            {"execution_gate_simulation_uses_fake_transport": False},
            "execution_gate_simulation_must_use_fake_transport",
        ),
        (
            {"execution_gate_simulation_http_post_executed": True},
            "execution_gate_simulation_http_post_executed",
        ),
    ),
)
def test_lifecycle_execution_and_fake_transport_requirements_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_post_live_enablement_no_post_controlled(
        _ready_input(**override),
    )

    assert result.status in {Status.BLOCKED_LIFECYCLE, Status.BLOCKED_TRANSPORT}
    assert result.this_step_actual_settlement_post_allowed_now is False
    assert result.this_step_actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert result.transport_call_count == 0
    assert result.http_post_executed is False
    assert result.entry_post_executed is False
    assert result.generic_close_post_executed is False
    assert result.live_order_once_executed is False
    assert result.external_api_write_executed is False
    assert result.execution_gate_simulation_can_set_actual_settlement_post_allowed_now is False
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        (
            {"raw_id_value_credential_header_exposure": True},
            "raw_id_value_credential_header_exposure",
        ),
        ({"env_read": True}, "env_read"),
    ),
)
def test_raw_id_value_credential_header_and_env_exposure_fail_closed(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_official_settlement_actual_post_live_enablement_no_post_controlled(
        _ready_input(**override),
    )
    rendered = render_official_settlement_actual_post_live_enablement_no_post_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.BLOCKED_UNSAFE
    assert result.execution_gate_simulation_can_set_actual_settlement_post_allowed_now is False
    assert result.raw_id_value_credential_header_exposure is (
        reason == "raw_id_value_credential_header_exposure"
    )
    assert result.env_read is False
    assert result.fake_transport.raw_request_exposed is False
    assert result.fake_transport.id_exposed is False
    assert result.settlement_post_count == 0
    assert reason in result.blocked_reasons
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_live_enablement_module_has_no_execution_imports_or_calls() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / (
            "live_order_real_official_settlement_actual_post_live_enablement_no_post"
            "_controlled.py"
        )
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
