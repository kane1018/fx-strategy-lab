from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from app.live_verification.live_order_real_official_settlement_actual_transport_no_post_controlled import (  # noqa: E501
    OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_READY_RESULT,
    OfficialSettlementActualTransportHttpxClient,
    OfficialSettlementActualTransportInput,
    OfficialSettlementActualTransportStatus,
    as_safe_dict,
    build_official_settlement_actual_transport_no_post_controlled,
    render_official_settlement_actual_transport_no_post_markdown,
)

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "live_verification"
    / "live_order_real_official_settlement_actual_transport_no_post_controlled.py"
)

FORBIDDEN_RENDER_MARKERS = {
    "/private/v1/closeOrder",
    "api_key",
    "api_secret",
    "signature",
    "headers",
    "response_body",
    "raw_request",
    "raw_response",
    "credential_value",
}


def _call_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    return modules


def test_official_settlement_actual_transport_ready_no_post_path() -> None:
    result = build_official_settlement_actual_transport_no_post_controlled()

    assert result.status is OfficialSettlementActualTransportStatus.READY_NO_POST
    assert result.sanitized_result_category == OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_READY_RESULT
    assert result.blocked_reasons == ()
    assert result.all_pre_execution_code_stop_conditions_eliminated is True
    assert result.official_settlement_actual_transport_confirmed is True
    assert result.official_settlement_actual_transport_callable_available is True
    assert result.official_settlement_actual_transport_binding_ready is True
    assert result.official_settlement_actual_transport_targets_official_settlement_route is True
    assert result.official_settlement_actual_transport_targets_generic_order_route is False
    assert result.official_settlement_actual_transport_uses_generic_order_executor is False
    assert result.official_settlement_actual_transport_uses_live_order_once is False
    assert result.official_settlement_actual_transport_uses_one_shot_generic_order is False
    assert result.official_settlement_actual_transport_uses_position_specific_path is False
    assert result.official_settlement_real_network_client_binding_confirmed is True
    assert result.official_settlement_real_network_client_callable_available is True
    assert result.official_settlement_real_network_transport_binding_ready is True
    assert result.real_network_client_binding_can_be_reached_after_execution_gate_authorization
    assert result.execution_gate_can_call_actual_transport_after_confirmation is True
    assert result.next_execution_gate_has_no_known_code_blocker is True

    assert result.fake_http_transport_used is True
    assert result.fake_http_transport_call_count == 1
    assert result.real_http_client_call_count == 0
    assert result.actual_transport_real_http_post_executed is False
    assert result.actual_transport_broker_write_executed is False
    assert result.this_step_actual_transport_invoked is False
    assert result.this_step_actual_settlement_post_executed is False
    assert result.settlement_post_count == 0
    assert result.sender_call_count == 0
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
    assert result.env_read is False

    assert result.next_execution_gate_still_requires_fresh_runtime_read is True
    assert result.next_execution_gate_still_requires_operator_readiness is True
    assert result.next_execution_gate_still_requires_settlement_specific_confirmation is True


def test_official_settlement_actual_transport_plan_is_size_based_not_position_specific() -> None:
    result = build_official_settlement_actual_transport_no_post_controlled()

    assert result.actual_transport_plan is not None
    plan = result.actual_transport_plan
    assert plan.route_kind == "OFFICIAL_SIZE_BASED_SETTLEMENT"
    assert plan.size_based_settlement is True
    assert plan.position_specific_identifier_required is False
    assert plan.one_settlement_post_max is True
    assert plan.retry_allowed is False
    assert plan.repost_allowed is False
    assert plan.second_settlement_allowed is False
    assert plan.entry_post_allowed is False
    assert plan.generic_close_allowed is False
    assert plan.raw_id_value_credential_header_exposure is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("repository_clean", False),
        ("head_equals_origin_main", False),
        ("credential_presence_available", False),
        ("official_settlement_no_post_preview_ready", False),
        ("official_settlement_real_network_client_binding_confirmed", False),
        ("official_settlement_real_network_client_callable_available", False),
        ("official_settlement_real_network_transport_binding_ready", False),
        ("official_settlement_real_network_client_targets_official_settlement_route", False),
        ("runtime_position_status", "NO_POSITION"),
        ("position_count_safe", 0),
        ("has_exactly_one_position", False),
        ("has_multiple_positions", True),
        ("operator_broker_ui_checked", False),
        ("operator_broker_ui_open_position_visible", False),
        ("operator_broker_ui_values_or_ids_provided", True),
        ("operator_can_monitor", False),
        ("operator_approves_settlement_attempt", False),
        ("sanitized_settlement_preview_shown", False),
        ("settlement_specific_confirmation_current_turn", False),
        ("settlement_specific_confirmation_exact_match", False),
        ("settlement_route_kind", "GENERIC_ORDER"),
        ("settlement_route_is_generic_order", True),
        ("settlement_route_is_dedicated", False),
        ("generic_order_executor_used_for_settlement", True),
        ("live_order_once_used_for_settlement", True),
        ("generic_order_endpoint_used_for_settlement", True),
        ("one_shot_generic_order_path_used_for_settlement", True),
        ("position_specific_path_used", True),
        ("position_specific_identifier_safe_handling_ready", True),
        ("position_specific_preview_allowed", True),
        ("size_based_preview_allowed", False),
        ("retry_allowed", True),
        ("repost_allowed", True),
        ("second_settlement_allowed", True),
        ("entry_post_allowed", True),
        ("generic_close_allowed", True),
        ("ledger_update_allowed", True),
        ("receipt_handoff_allowed", True),
        ("raw_id_value_credential_header_exposure", True),
        ("env_read", True),
    ],
)
def test_official_settlement_actual_transport_fail_closed(field: str, value: object) -> None:
    snapshot = OfficialSettlementActualTransportInput(**{field: value})

    result = build_official_settlement_actual_transport_no_post_controlled(snapshot)

    assert result.status is OfficialSettlementActualTransportStatus.BLOCKED_NO_POST
    assert result.all_pre_execution_code_stop_conditions_eliminated is False
    assert result.execution_gate_can_call_actual_transport_after_confirmation is False
    assert result.next_execution_gate_has_no_known_code_blocker is False
    assert result.fake_http_transport_used is False
    assert result.fake_http_transport_call_count == 0
    assert result.real_http_client_call_count == 0
    assert result.actual_transport_real_http_post_executed is False
    assert result.actual_transport_broker_write_executed is False
    assert result.settlement_post_count == 0
    assert result.this_step_actual_transport_invoked is False
    assert result.this_step_actual_settlement_post_executed is False
    assert result.blocked_reasons


def test_actual_transport_has_concrete_httpx_client_but_does_not_call_it() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules = _imported_modules(tree)
    call_names = _call_names(tree)

    assert "httpx" in imported_modules
    assert "app.private_api.auth" in imported_modules
    assert "post" in call_names
    assert "build_auth_headers" in call_names
    assert "app.live_verification.live_order_once" not in imported_modules
    assert "post_live_order_with_httpx" not in call_names
    assert "execute_one_shot_live_order" not in call_names
    assert "prepare_one_shot_live_order" not in call_names
    assert repr(
        OfficialSettlementActualTransportHttpxClient(
            api_key="REDACTED",
            api_secret="REDACTED",
            timestamp_factory=lambda: "0",
        )
    ) == "OfficialSettlementActualTransportHttpxClient(<redacted>)"


def test_actual_transport_render_and_safe_dict_do_not_expose_raw_values() -> None:
    result = build_official_settlement_actual_transport_no_post_controlled()
    rendered = render_official_settlement_actual_transport_no_post_markdown(result)
    safe_dict_text = repr(as_safe_dict(result))
    result_dict_text = repr(asdict(result))

    for marker in FORBIDDEN_RENDER_MARKERS:
        assert marker not in rendered
        assert marker not in safe_dict_text
    assert "actual_transport_plan" not in safe_dict_text
    assert "/private/v1/closeOrder" not in result_dict_text
    assert "api_key" not in result_dict_text
    assert "api_secret" not in result_dict_text
