from __future__ import annotations

import ast
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.live_verification.live_order_real_step6g_internal_wiring import (
    LiveOrderRealStep6GInternalWiringInput,
    LiveOrderRealStep6GInternalWiringStatus,
    build_live_order_real_step6g_internal_wiring,
    build_valid_step6g_internal_wiring_snapshot,
    render_live_order_real_step6g_internal_wiring_markdown,
)

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
Status = LiveOrderRealStep6GInternalWiringStatus


def _input(**overrides: object) -> LiveOrderRealStep6GInternalWiringInput:
    base = LiveOrderRealStep6GInternalWiringInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_step6g_internal_wiring(
        input_snapshot=_input(**overrides),
        created_at=CREATED_AT,
    )


def test_valid_full_fake_sanitized_chain_ready_no_api_no_post() -> None:
    result = _build()

    assert result.status is Status.STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST
    assert result.internal_wiring_ready is True
    assert result.pb_ready is True
    assert result.eb_ready is True
    assert result.ad_ready is True
    assert result.ra_ready is True
    assert result.tc_ready is True
    assert result.st_signing_ready is True
    assert result.st_private_transport_ready is True
    assert result.dummy_signing_ready is True
    assert result.dummy_signature_check_passed is True
    assert result.dummy_signature_value_present is False
    assert result.dummy_signature_value_displayed is False
    assert result.dummy_signature_value_saved is False
    assert result.http_transport_interface_ready is True
    assert result.http_transport_interface_mode == "INTERFACE_ONLY"
    assert result.http_client_present is False
    assert result.can_execute_http_post is False
    assert result.can_call_order_endpoint is False
    assert result.can_call_live_order_once is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.credential_values_provided is False
    assert result.signature_value_generated is False
    assert result.header_values_present is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.retry_allowed is False
    assert result.loop_allowed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"symbol": "EUR_JPY"},
        {"side": "SELL"},
        {"size": 101},
        {"executionType": "LIMIT"},
        {"codex_inferred": True},
    ],
)
def test_wrong_or_inferred_order_intent_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ORDER_INTENT


@pytest.mark.parametrize(
    "overrides",
    [
        {"final_confirmation_exact_match": False},
        {"final_confirmation_reused": True},
        {"approval_artifact_reestablished": False},
        {"approval_validation_passed": False},
        {"approval_exact_match_ready": False},
        {"approval_fingerprint": ""},
        {"sha256_prefix": ""},
    ],
)
def test_approval_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_APPROVAL


@pytest.mark.parametrize(
    "overrides",
    [
        {"approval_command_full_text_present": True},
        {"approval_command_displayed": True},
        {"approval_command_saved": True},
    ],
)
def test_approval_command_exposure_blocks_raw_secret(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE


@pytest.mark.parametrize(
    "overrides",
    [
        {"final_confirmation_preflight_passed": False},
        {"post_immediate_preflight_passed": False},
        {"market_session_state": "CLOSED"},
        {"market_hours_unknown": True},
        {"open_positions_count": 1},
        {"active_orders_count": 1},
        {"ticker_age_seconds": 31.0},
        {"ticker_age_seconds": -6.0},
        {"ticker_spread_jpy": 0.02},
        {"permission_scope_check_passed": False},
        {"ip_account_binding_check_passed": False},
        {"previous_result_unknown_check_passed": False},
    ],
)
def test_preflight_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_PREFLIGHT


@pytest.mark.parametrize(
    "overrides",
    [
        {"post_attempt_count_before": 1},
        {"post_attempt_limit": 2},
        {"retry_allowed": True},
        {"loop_allowed": True},
        {"add_order_allowed": True},
        {"change_order_allowed": True},
        {"cancel_order_allowed": True},
        {"close_order_allowed": True},
    ],
)
def test_attempt_blockers(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ATTEMPT_STATE


@pytest.mark.parametrize(
    ("field_name", "expected_status"),
    [
        ("pb_bridge_ready", Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE),
        ("eb_runtime_ready", Status.BLOCKED_STEP6G_INTERNAL_WIRING_RUNTIME_BRIDGE),
        (
            "ad_controlled_adapter_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_CONTROLLED_ADAPTER,
        ),
        ("ra_real_adapter_ready", Status.BLOCKED_STEP6G_INTERNAL_WIRING_REAL_ADAPTER),
        ("tc_transport_core_ready", Status.BLOCKED_STEP6G_INTERNAL_WIRING_TRANSPORT_CORE),
        (
            "st_signing_contract_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "st_private_transport_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_PRIVATE_TRANSPORT,
        ),
        ("dummy_signing_ready", Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT),
        (
            "dummy_signature_check_passed",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_SIGNING_CONTRACT,
        ),
        (
            "http_transport_interface_ready",
            Status.BLOCKED_STEP6G_INTERNAL_WIRING_PRIVATE_TRANSPORT,
        ),
    ],
)
def test_component_ready_flag_mismatch_blocks(
    field_name: str,
    expected_status: Status,
) -> None:
    result = _build(**{field_name: False})

    assert result.status is expected_status


@pytest.mark.parametrize(
    "overrides",
    [
        {"credential_values_provided": True},
        {"signature_value_generated": True},
        {"header_values_present": True},
        {"dummy_signature_value_present": True},
        {"dummy_signature_value_displayed": True},
        {"dummy_signature_value_saved": True},
        {"raw_request_displayed": True},
        {"raw_request_saved": True},
        {"raw_response_displayed": True},
        {"raw_response_saved": True},
        {"headers_displayed": True},
        {"signature_displayed": True},
        {"credentials_displayed": True},
        {"real_ids_displayed": True},
    ],
)
def test_raw_secret_or_real_id_exposure_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_RAW_OR_SECRET_EXPOSURE


@pytest.mark.parametrize(
    "overrides",
    [
        {"http_post_executed": True},
        {"order_endpoint_called": True},
        {"live_order_once_called": True},
    ],
)
def test_execution_boundary_crossing_blocks_route_bridge(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_ROUTE_BRIDGE


@pytest.mark.parametrize(
    "overrides",
    [
        {"http_client_present": True},
        {"can_execute_http_post": True},
        {"can_call_order_endpoint": True},
        {"can_call_live_order_once": True},
    ],
)
def test_http_transport_interface_boundary_crossing_blocks(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_PRIVATE_TRANSPORT
    assert result.http_transport_interface_ready is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"step4_spoofing": True},
        {"ledger_changed": True},
    ],
)
def test_step4_spoofing_or_ledger_change_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.BLOCKED_STEP6G_INTERNAL_WIRING_STEP4_SPOOFING


def test_build_valid_snapshot_uses_existing_safe_piece_results() -> None:
    snapshot = build_valid_step6g_internal_wiring_snapshot(created_at=CREATED_AT)

    assert snapshot.pb_result.bridge_ready is True
    assert snapshot.eb_result.fake_runtime_ready is True
    assert snapshot.ad_result.fake_adapter_ready is True
    assert snapshot.ra_result.real_adapter_contract_ready is True
    assert snapshot.tc_result.body_allowlist_passed is True
    assert snapshot.st_signing_result.signing_contract_ready is True
    assert snapshot.st_private_transport_result.transport_contract_ready is True
    assert snapshot.dummy_signing_result.dummy_signing_ready is True
    assert snapshot.dummy_signing_result.dummy_signature_check_passed is True
    assert snapshot.http_transport_interface_result.interface_ready is True


def test_renderer_includes_warnings_and_no_sensitive_values() -> None:
    result = _build()
    rendered = render_live_order_real_step6g_internal_wiring_markdown(result)

    assert "This internal wiring is fake/sanitized only." in rendered
    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "does not call order endpoint" in rendered
    assert "does not call live_order_once" in rendered
    assert "does not use real credentials" in rendered
    assert "does not generate real signatures" in rendered
    assert "dummy_signing_ready: true" in rendered
    assert "dummy_signature_check_passed: true" in rendered
    assert "http_transport_interface_ready: true" in rendered
    assert "http_client_present: false" in rendered
    assert "can_execute_http_post: false" in rendered
    assert "Future real execution requires a new final confirmation" in rendered
    assert "FULL_APPROVAL_COMMAND_SENTINEL" not in rendered
    assert "RAW_REQUEST_SENTINEL" not in rendered
    assert "RAW_RESPONSE_SENTINEL" not in rendered
    assert "REAL_ORDER_ID_SENTINEL" not in rendered
    assert '{"executionType":"MARKET"' not in rendered


def test_asdict_does_not_contain_raw_secret_real_ids_or_full_approval_command() -> None:
    result = _build()
    payload = repr(asdict(result))

    assert "FULL_APPROVAL_COMMAND_SENTINEL" not in payload
    assert "RAW_REQUEST_SENTINEL" not in payload
    assert "RAW_RESPONSE_SENTINEL" not in payload
    assert "REAL_ORDER_ID_SENTINEL" not in payload
    assert "REAL_EXECUTION_ID_SENTINEL" not in payload
    assert "REAL_POSITION_ID_SENTINEL" not in payload
    assert "DUMMY_SIGNATURE_VALUE_SENTINEL" not in payload
    assert "DUMMY_SECRET_MATERIAL_VALUE_SENTINEL" not in payload
    assert '{"executionType":"MARKET"' not in payload


def test_new_module_does_not_import_http_private_broker_live_order_once_or_env_access() -> None:
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
    blocked_names = {
        "getenv",
        "ENABLE_LIVE_TRADING",
        "GMO_FX_API_KEY",
        "GMO_FX_API_SECRET",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "pbcopy",
    }
    blocked_attrs = {"environ", "getenv"}
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_step6g_internal_wiring.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not _is_blocked_module(alias.name, blocked_modules)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs


def _is_blocked_module(module: str, blocked_modules: set[str]) -> bool:
    return any(
        module == blocked or module.startswith(f"{blocked}.")
        for blocked in blocked_modules
    )
