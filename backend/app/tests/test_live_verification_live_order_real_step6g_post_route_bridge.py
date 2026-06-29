from __future__ import annotations

import ast
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
)
from app.live_verification.live_order_real_step6g_post_route_bridge import (
    LiveOrderRealStep6GApprovalSnapshot,
    LiveOrderRealStep6GAttemptState,
    LiveOrderRealStep6GOrderIntentSnapshot,
    LiveOrderRealStep6GPostRouteBridgeStatus,
    LiveOrderRealStep6GPreflightSnapshot,
    LiveOrderRealStep6GRouteContractSnapshot,
    build_live_order_real_step6g_post_route_bridge,
    render_live_order_real_step6g_post_route_bridge_markdown,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
Status = LiveOrderRealStep6GPostRouteBridgeStatus


def _order_intent(**overrides: object) -> LiveOrderRealStep6GOrderIntentSnapshot:
    values = {
        "symbol": SUPPORTED_SYMBOL,
        "side": "BUY",
        "size": LIVE_ORDER_CANDIDATE_SIZE,
        "executionType": LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
        "source_label": "operator_explicit_step6g_f2_buy_intent",
        "codex_inferred_side": False,
        "codex_inferred_symbol": False,
        "codex_inferred_size": False,
        "codex_inferred_execution_type": False,
    }
    values.update(overrides)
    return LiveOrderRealStep6GOrderIntentSnapshot(**values)


def _approval(**overrides: object) -> LiveOrderRealStep6GApprovalSnapshot:
    values = {
        "step6g_final_confirmation_received": True,
        "step6g_final_confirmation_exact_match": True,
        "final_confirmation_phrase_reused": False,
        "approval_artifact_reestablished": True,
        "approval_validation_passed": True,
        "approval_exact_match_ready": True,
        "approval_command_fingerprint": "95E0288AEEDBDFE3",
        "approval_sha256_prefix": "95e0288a",
        "approval_command_displayed": False,
        "approval_command_saved": False,
        "approval_command_copyable": False,
        "approval_command_pbcopy": False,
        "step4_approval_phrase_used": False,
        "step4_approval_phrase_spoofed": False,
        "step4_approval_gate_reused_as_step6g": False,
        "approval_command_full_text_present": False,
    }
    values.update(overrides)
    return LiveOrderRealStep6GApprovalSnapshot(**values)


def _preflight(**overrides: object) -> LiveOrderRealStep6GPreflightSnapshot:
    values = {
        "final_confirmation_preflight_passed": True,
        "post_immediate_preflight_passed": True,
        "market_session_state": "OPEN",
        "market_window_allowed": True,
        "broker_maintenance_active": False,
        "holiday_or_special_close": False,
        "market_hours_unknown": False,
        "open_positions_count": 0,
        "active_orders_count": 0,
        "ticker_symbol": SUPPORTED_SYMBOL,
        "ticker_spread_jpy": 0.005,
        "ticker_age_seconds": 0.5,
        "ticker_check_passed": True,
        "permission_scope_check_passed": True,
        "ip_account_binding_check_passed": True,
        "previous_result_unknown_check_passed": True,
        "raw_request_saved": False,
        "raw_request_displayed": False,
        "raw_response_saved": False,
        "raw_response_displayed": False,
        "headers_saved": False,
        "headers_displayed": False,
        "signature_saved": False,
        "signature_displayed": False,
        "credentials_displayed": False,
        "order_ids_displayed": False,
        "execution_ids_displayed": False,
        "position_ids_displayed": False,
        "client_order_ids_displayed": False,
    }
    values.update(overrides)
    return LiveOrderRealStep6GPreflightSnapshot(**values)


def _attempt(**overrides: object) -> LiveOrderRealStep6GAttemptState:
    values = {
        "post_attempt_limit": 1,
        "post_attempt_count_before": 0,
        "post_attempt_count_after": 0,
        "post_executed": False,
        "post_allowed_this_step": False,
        "allowed_for_live_before": False,
        "allowed_for_live_persisted": False,
        "allowed_for_live_after": False,
        "retry_allowed": False,
        "loop_allowed": False,
        "add_order_allowed": False,
        "change_order_allowed": False,
        "cancel_order_allowed": False,
        "close_order_allowed": False,
    }
    values.update(overrides)
    return LiveOrderRealStep6GAttemptState(**values)


def _route(**overrides: object) -> LiveOrderRealStep6GRouteContractSnapshot:
    values = {
        "route_contract_name": "step6g_dedicated_post_route_bridge_pure_model",
        "route_contract_kind": "pure_model_no_api_no_post",
        "uses_step4_approval_phrase": False,
        "spoofs_step4_approval_phrase": False,
        "mutates_step4_ledger_state": False,
        "requires_step4_prepared_ledger": False,
        "uses_step6g_dedicated_attempt_state": True,
        "calls_live_order_once_directly": False,
        "imports_live_order_once": False,
        "imports_broker": False,
        "imports_private_api": False,
        "creates_new_order_endpoint": False,
        "creates_new_payload_builder": False,
        "order_endpoint_called": False,
        "order_payload_generated": False,
        "order_payload_sent": False,
        "http_post_executed": False,
        "raw_request_displayed": False,
        "raw_response_displayed": False,
        "headers_displayed": False,
        "signature_displayed": False,
        "credentials_displayed": False,
        "real_ids_displayed": False,
        "retry_on_unknown": False,
        "retry_on_timeout": False,
        "retry_on_reject": False,
        "explicit_safe_adapter_contract": False,
    }
    values.update(overrides)
    return LiveOrderRealStep6GRouteContractSnapshot(**values)


def _bridge(**overrides: object):
    values = {
        "order_intent_snapshot": _order_intent(),
        "approval_snapshot": _approval(),
        "preflight_snapshot": _preflight(),
        "attempt_state": _attempt(),
        "route_contract_snapshot": _route(),
        "created_at": CREATED_AT,
    }
    values.update(overrides)
    return build_live_order_real_step6g_post_route_bridge(**values)


def test_valid_step6g_snapshots_ready_no_api_no_post() -> None:
    result = _bridge()

    assert result.status is Status.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST
    assert result.bridge_ready is True
    assert result.eligible_for_future_step6g_execution_attempt is True
    assert result.no_api_executed is True
    assert result.no_post_executed is True
    assert result.allowed_for_live is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.recommended_next_step.startswith("implement_or_run_separate_step6g")


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        (
            {"step6g_final_confirmation_received": False},
            "step6g_final_confirmation_received_missing",
        ),
        (
            {"step6g_final_confirmation_exact_match": False},
            "step6g_final_confirmation_exact_match_missing",
        ),
        ({"final_confirmation_phrase_reused": True}, "final_confirmation_phrase_reused"),
        ({"approval_artifact_reestablished": False}, "approval_artifact_reestablished_missing"),
        ({"approval_validation_passed": False}, "approval_validation_passed_missing"),
        ({"approval_command_fingerprint": ""}, "approval_command_fingerprint_missing"),
    ],
)
def test_approval_blockers_block_approval(override: dict[str, object], reason: str) -> None:
    result = _bridge(approval_snapshot=_approval(**override))

    assert result.status is Status.BLOCKED_STEP6G_BRIDGE_APPROVAL
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    "field_name",
    [
        "approval_command_displayed",
        "approval_command_saved",
        "approval_command_copyable",
        "approval_command_pbcopy",
    ],
)
def test_approval_command_exposure_blocks_raw_or_secret(field_name: str) -> None:
    result = _bridge(approval_snapshot=_approval(**{field_name: True}))

    assert result.status is Status.BLOCKED_STEP6G_BRIDGE_RAW_OR_SECRET_EXPOSURE
    assert f"{field_name}_unsafe" in result.blocked_reasons


@pytest.mark.parametrize(
    ("approval_override", "route_override", "reason"),
    [
        ({"step4_approval_phrase_used": True}, {}, "step4_approval_phrase_used"),
        ({"step4_approval_phrase_spoofed": True}, {}, "step4_approval_phrase_spoofed"),
        ({}, {"mutates_step4_ledger_state": True}, "step4_ledger_state_mutation"),
    ],
)
def test_step4_spoofing_blocks(
    approval_override: dict[str, object],
    route_override: dict[str, object],
    reason: str,
) -> None:
    result = _bridge(
        approval_snapshot=_approval(**approval_override),
        route_contract_snapshot=_route(**route_override),
    )

    assert result.status is Status.BLOCKED_STEP6G_BRIDGE_STEP4_SPOOFING
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"symbol": "EUR_JPY"}, "symbol_not_usd_jpy"),
        ({"side": "SELL"}, "side_not_buy"),
        ({"size": 101}, "size_not_100"),
        ({"executionType": "LIMIT"}, "execution_type_not_market"),
        ({"codex_inferred_side": True}, "codex_inferred_side_unsafe"),
    ],
)
def test_order_intent_blocks(override: dict[str, object], reason: str) -> None:
    result = _bridge(order_intent_snapshot=_order_intent(**override))

    assert result.status is Status.BLOCKED_STEP6G_BRIDGE_ORDER_INTENT
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"final_confirmation_preflight_passed": False}, "final_confirmation_preflight_not_passed"),
        ({"post_immediate_preflight_passed": False}, "post_immediate_preflight_not_passed"),
        ({"market_session_state": "CLOSE"}, "market_session_not_open"),
        ({"market_hours_unknown": True}, "market_hours_unknown"),
        ({"open_positions_count": 1}, "open_positions_not_zero"),
        ({"active_orders_count": 1}, "active_orders_not_zero"),
        ({"ticker_age_seconds": 31.0}, "ticker_age_stale"),
        ({"ticker_age_seconds": -5.1}, "ticker_age_future_skew_too_large"),
        ({"ticker_spread_jpy": 0.011}, "ticker_spread_too_wide"),
        ({"permission_scope_check_passed": False}, "permission_scope_check_failed"),
        ({"ip_account_binding_check_passed": False}, "ip_account_binding_check_failed"),
        ({"previous_result_unknown_check_passed": False}, "previous_result_unknown_check_failed"),
    ],
)
def test_preflight_blocks(override: dict[str, object], reason: str) -> None:
    result = _bridge(preflight_snapshot=_preflight(**override))

    assert result.status is Status.BLOCKED_STEP6G_BRIDGE_PREFLIGHT
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"post_attempt_limit": 2}, "post_attempt_limit_not_one"),
        ({"post_attempt_count_before": 1}, "post_attempt_count_before_not_zero"),
        ({"retry_allowed": True}, "retry_allowed_unsafe"),
        ({"loop_allowed": True}, "loop_allowed_unsafe"),
        ({"add_order_allowed": True}, "add_order_allowed_unsafe"),
        ({"change_order_allowed": True}, "change_order_allowed_unsafe"),
        ({"cancel_order_allowed": True}, "cancel_order_allowed_unsafe"),
        ({"close_order_allowed": True}, "close_order_allowed_unsafe"),
    ],
)
def test_attempt_state_blocks(override: dict[str, object], reason: str) -> None:
    result = _bridge(attempt_state=_attempt(**override))

    assert result.status is Status.BLOCKED_STEP6G_BRIDGE_ATTEMPT_STATE
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"calls_live_order_once_directly": True}, "calls_live_order_once_directly_unsafe"),
        ({"imports_live_order_once": True}, "imports_live_order_once_unsafe"),
        ({"imports_broker": True}, "imports_broker_unsafe"),
        ({"imports_private_api": True}, "imports_private_api_unsafe"),
        ({"creates_new_order_endpoint": True}, "creates_new_order_endpoint_unsafe"),
        ({"creates_new_payload_builder": True}, "creates_new_payload_builder_unsafe"),
    ],
)
def test_route_unsafe_blocks(override: dict[str, object], reason: str) -> None:
    result = _bridge(route_contract_snapshot=_route(**override))

    assert result.status is Status.BLOCKED_STEP6G_BRIDGE_ROUTE_UNSAFE
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("preflight_override", "route_override", "reason"),
    [
        ({"raw_response_displayed": True}, {}, "raw_response_displayed_unsafe"),
        ({"headers_displayed": True}, {}, "headers_displayed_unsafe"),
        ({"signature_displayed": True}, {}, "signature_displayed_unsafe"),
        ({"credentials_displayed": True}, {}, "credentials_displayed_unsafe"),
        ({"order_ids_displayed": True}, {}, "order_ids_displayed_unsafe"),
        ({}, {"real_ids_displayed": True}, "route_real_ids_displayed_unsafe"),
    ],
)
def test_raw_secret_or_id_exposure_blocks(
    preflight_override: dict[str, object],
    route_override: dict[str, object],
    reason: str,
) -> None:
    result = _bridge(
        preflight_snapshot=_preflight(**preflight_override),
        route_contract_snapshot=_route(**route_override),
    )

    assert result.status is Status.BLOCKED_STEP6G_BRIDGE_RAW_OR_SECRET_EXPOSURE
    assert reason in result.blocked_reasons


def test_renderer_includes_no_api_no_post_warnings_and_excludes_values() -> None:
    marker = "FULL_APPROVAL_COMMAND_SHOULD_NOT_APPEAR"
    result = _bridge(
        approval_snapshot=_approval(approval_command_fingerprint="95E0288AEEDBDFE3"),
    )
    markdown = render_live_order_real_step6g_post_route_bridge_markdown(result)

    assert "This bridge is pure model only." in markdown
    assert "This bridge does not execute API calls." in markdown
    assert "This bridge does not execute HTTP POST." in markdown
    assert "This bridge does not call order endpoint." in markdown
    assert "This bridge does not call live_order_once." in markdown
    assert "This bridge does not authorize reusing old final confirmation." in markdown
    assert (
        "Future Step 6G execution requires a new final confirmation and fresh preflight."
        in markdown
    )
    for forbidden_value in (
        marker,
        "raw-response-body-value",
        "credential-secret-value",
        "real-order-id-value",
        "execution-id-value",
        "position-id-value",
        "client-order-id-value",
        "STEP4_APPROVE",
        "pbcopy ",
    ):
        assert forbidden_value not in markdown


def test_serialization_and_repr_do_not_include_sensitive_actual_values() -> None:
    result = _bridge()
    serialized = str(asdict(result))
    represented = repr(result)

    for forbidden_value in (
        "FULL_APPROVAL_COMMAND_SHOULD_NOT_APPEAR",
        "raw-response-body-value",
        "credential-secret-value",
        "real-order-id-value",
        "execution-id-value",
        "position-id-value",
        "client-order-id-value",
    ):
        assert forbidden_value not in serialized
        assert forbidden_value not in represented


def test_new_module_has_no_http_private_broker_live_order_once_dependencies() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_step6g_post_route_bridge.py"
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
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not any(
                    alias.name == blocked or alias.name.startswith(f"{blocked}.")
                    for blocked in blocked_modules
                )
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not any(
                module == blocked or module.startswith(f"{blocked}.") for blocked in blocked_modules
            )
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            call_name = node.func.id if isinstance(node.func, ast.Name) else None
            if isinstance(node.func, ast.Attribute):
                call_name = node.func.attr
            assert call_name not in blocked_call_names


def test_replace_keeps_ready_bridge_safe_when_adapter_contract_is_explicit() -> None:
    route = replace(
        _route(),
        uses_step6g_dedicated_attempt_state=False,
        explicit_safe_adapter_contract=True,
    )

    result = _bridge(route_contract_snapshot=route)

    assert result.status is Status.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST
