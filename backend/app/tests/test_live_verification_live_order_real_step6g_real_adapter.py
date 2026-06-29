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
from app.live_verification.live_order_real_step6g_controlled_adapter import (
    TransportMode as ControlledTransportMode,
)
from app.live_verification.live_order_real_step6g_controlled_adapter import (
    build_live_order_real_step6g_controlled_adapter,
    make_live_order_real_step6g_fake_transport_contract,
    run_live_order_real_step6g_controlled_adapter_with_fake_transport,
)
from app.live_verification.live_order_real_step6g_post_route_bridge import (
    LiveOrderRealStep6GApprovalSnapshot,
    LiveOrderRealStep6GAttemptState,
    LiveOrderRealStep6GOrderIntentSnapshot,
    LiveOrderRealStep6GPreflightSnapshot,
    LiveOrderRealStep6GRouteContractSnapshot,
    build_live_order_real_step6g_post_route_bridge,
)
from app.live_verification.live_order_real_step6g_real_adapter import (
    LiveOrderRealStep6GRealAdapterRequest,
    LiveOrderRealStep6GStubTransportResult,
    RealAdapterStatus,
    RealTransportMode,
    StubTransportResultCategory,
    build_live_order_real_step6g_real_adapter_contract,
    make_live_order_real_step6g_real_adapter_request,
    make_live_order_real_step6g_stub_transport_contract,
    render_live_order_real_step6g_real_adapter_markdown,
    run_live_order_real_step6g_real_adapter_with_stub_transport,
)
from app.live_verification.live_order_real_step6g_runtime_bridge import (
    build_live_order_real_step6g_runtime_bridge,
    run_live_order_real_step6g_fake_runtime_bridge,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


def _order_intent(**overrides: object) -> LiveOrderRealStep6GOrderIntentSnapshot:
    values = {
        "symbol": SUPPORTED_SYMBOL,
        "side": "BUY",
        "size": LIVE_ORDER_CANDIDATE_SIZE,
        "executionType": LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
        "source_label": "operator_explicit_step6g_buy_intent",
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


def _runtime(bridge=None):
    return run_live_order_real_step6g_fake_runtime_bridge(
        step6g_post_route_bridge_result=bridge or _bridge(),
        created_at=CREATED_AT,
    )


def _blocked_runtime(bridge=None):
    source_bridge = bridge or _bridge(
        approval_snapshot=_approval(approval_validation_passed=False)
    )
    return build_live_order_real_step6g_runtime_bridge(
        step6g_post_route_bridge_result=source_bridge,
        runtime_request=None,
        fake_executor_result=None,
        created_at=CREATED_AT,
    )


def _controlled(bridge=None, runtime=None):
    source_bridge = bridge or _bridge()
    source_runtime = runtime or _runtime(source_bridge)
    return run_live_order_real_step6g_controlled_adapter_with_fake_transport(
        step6g_post_route_bridge_result=source_bridge,
        step6g_runtime_bridge_result=source_runtime,
        created_at=CREATED_AT,
    )


def _blocked_controlled(bridge=None, runtime=None):
    source_bridge = bridge or _bridge()
    source_runtime = runtime or _runtime(source_bridge)
    return build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=source_bridge,
        step6g_runtime_bridge_result=source_runtime,
        transport_contract=replace(
            make_live_order_real_step6g_fake_transport_contract(),
            transport_mode=ControlledTransportMode.REAL_TRANSPORT,
            is_fake_transport=False,
            is_real_transport=True,
        ),
        created_at=CREATED_AT,
    )


def _request(**overrides: object) -> LiveOrderRealStep6GRealAdapterRequest:
    bridge = _bridge()
    runtime = _runtime(bridge)
    controlled = _controlled(bridge, runtime)
    request = make_live_order_real_step6g_real_adapter_request(
        step6g_post_route_bridge_result=bridge,
        step6g_runtime_bridge_result=runtime,
        step6g_controlled_adapter_result=controlled,
        stub_attempt_count=1,
    )
    return replace(request, **overrides)


def _contract(**overrides: object):
    contract = make_live_order_real_step6g_stub_transport_contract()
    return replace(contract, **overrides)


def _transport_result(**overrides: object) -> LiveOrderRealStep6GStubTransportResult:
    values = {
        "stub_transport_attempted": True,
        "stub_transport_result_category": (
            StubTransportResultCategory.STUB_REAL_ADAPTER_ACCEPTED_NO_API_NO_POST
        ),
        "stub_attempt_count": 1,
        "stub_retry_count": 0,
        "stub_loop_count": 0,
        "real_http_post_executed": False,
        "order_endpoint_called": False,
        "live_order_once_called": False,
        "broker_order_path_called": False,
        "raw_request_present": False,
        "raw_response_present": False,
        "headers_present": False,
        "signature_present": False,
        "credentials_present": False,
        "real_order_id_present": False,
        "real_execution_id_present": False,
        "real_position_id_present": False,
        "real_client_order_id_present": False,
        "result_is_stub": True,
    }
    values.update(overrides)
    return LiveOrderRealStep6GStubTransportResult(**values)


def _build(*, bridge=None, runtime=None, controlled=None, **kwargs):
    source_bridge = bridge or _bridge()
    source_runtime = runtime or _runtime(source_bridge)
    source_controlled = controlled or _controlled(source_bridge, source_runtime)
    return build_live_order_real_step6g_real_adapter_contract(
        step6g_post_route_bridge_result=source_bridge,
        step6g_runtime_bridge_result=source_runtime,
        step6g_controlled_adapter_result=source_controlled,
        transport_contract=kwargs.pop("transport_contract", _contract()),
        created_at=CREATED_AT,
        **kwargs,
    )


def test_valid_pb_eb_ad_stub_accepted_completes_without_real_post() -> None:
    bridge = _bridge()
    runtime = _runtime(bridge)
    controlled = _controlled(bridge, runtime)

    result = run_live_order_real_step6g_real_adapter_with_stub_transport(
        step6g_post_route_bridge_result=bridge,
        step6g_runtime_bridge_result=runtime,
        step6g_controlled_adapter_result=controlled,
        created_at=CREATED_AT,
    )

    assert result.status is RealAdapterStatus.STEP6G_REAL_ADAPTER_STUB_COMPLETED_NO_API_NO_POST
    assert result.real_adapter_contract_ready is True
    assert result.stub_transport_attempted is True
    assert result.stub_transport_result_category == (
        StubTransportResultCategory.STUB_REAL_ADAPTER_ACCEPTED_NO_API_NO_POST.value
    )
    assert result.real_http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.allowed_for_live is False


def test_ready_without_stub_result_keeps_real_post_blocked() -> None:
    result = _build()

    assert result.status is (
        RealAdapterStatus.STEP6G_REAL_ADAPTER_CONTRACT_READY_STUB_ONLY_NO_API_NO_POST
    )
    assert result.real_adapter_contract_ready is True
    assert result.stub_transport_attempted is False
    assert result.stub_transport_result_category == "NOT_RUN_STUB_TRANSPORT_ONLY_NO_API_NO_POST"
    assert result.real_http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    ("bridge", "runtime", "controlled", "request_overrides"),
    [
        (_bridge(order_intent_snapshot=_order_intent(symbol="EUR_JPY")), None, None, {}),
        (None, _blocked_runtime(), None, {}),
        (None, None, _blocked_controlled(), {}),
        (None, None, None, {"final_confirmation_exact_match": False}),
        (None, None, None, {"final_confirmation_reused": True}),
        (None, None, None, {"approval_exact_match": False}),
        (None, None, None, {"final_confirmation_preflight_passed": False}),
        (None, None, None, {"post_immediate_preflight_passed": False}),
        (None, None, None, {"order_intent_exact_match": False}),
    ],
)
def test_input_not_ready_blocks(bridge, runtime, controlled, request_overrides: dict) -> None:
    source_bridge = bridge or _bridge()
    source_runtime = runtime or _runtime(source_bridge)
    source_controlled = controlled or _controlled(source_bridge, source_runtime)
    request = None
    if request_overrides:
        request = make_live_order_real_step6g_real_adapter_request(
            step6g_post_route_bridge_result=source_bridge,
            step6g_runtime_bridge_result=source_runtime,
            step6g_controlled_adapter_result=source_controlled,
            stub_attempt_count=1,
        )
        request = replace(request, **request_overrides)

    result = _build(
        bridge=source_bridge,
        runtime=source_runtime,
        controlled=source_controlled,
        adapter_request=request,
    )

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_INPUT_NOT_READY
    assert result.real_adapter_contract_ready is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "request_overrides",
    [
        {"post_attempt_count_before": 1},
        {"post_attempt_limit": 2},
        {"stub_attempt_count": 2},
        {"post_allowed_this_step": True},
        {"post_executed": True},
        {"allowed_for_live": True},
        {"allowed_for_live_persisted": True},
    ],
)
def test_attempt_state_blocks(request_overrides: dict) -> None:
    result = _build(adapter_request=_request(**request_overrides))

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_ATTEMPT_STATE
    assert result.real_http_post_executed is False


def test_stub_attempt_count_from_result_over_one_blocks_attempt_state() -> None:
    result = _build(transport_result=_transport_result(stub_attempt_count=2))

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_ATTEMPT_STATE
    assert "stub_transport_attempt_count_exceeds_one" in result.blocked_reasons


@pytest.mark.parametrize(
    "request_overrides",
    [
        {"retry_allowed": True},
        {"loop_allowed": True},
        {"add_order_allowed": True},
        {"change_order_allowed": True},
        {"cancel_order_allowed": True},
        {"close_order_allowed": True},
    ],
)
def test_retry_loop_or_order_mutation_blocks(request_overrides: dict) -> None:
    result = _build(adapter_request=_request(**request_overrides))

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_RETRY_OR_LOOP


@pytest.mark.parametrize(
    "contract_overrides",
    [
        {"retry_on_unknown": True},
        {"retry_on_timeout": True},
        {"retry_on_reject": True},
    ],
)
def test_transport_retry_policy_blocks(contract_overrides: dict) -> None:
    result = _build(transport_contract=_contract(**contract_overrides))

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_RETRY_OR_LOOP


@pytest.mark.parametrize(
    "transport_result",
    [
        _transport_result(stub_retry_count=1),
        _transport_result(stub_loop_count=1),
    ],
)
def test_stub_retry_or_loop_counts_block(transport_result) -> None:
    result = _build(transport_result=transport_result)

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_RETRY_OR_LOOP


@pytest.mark.parametrize(
    "route_overrides",
    [
        {"uses_step4_approval_phrase": True},
        {"spoofs_step4_approval_phrase": True},
        {"mutates_step4_ledger_state": True},
    ],
)
def test_step4_spoofing_blocks(route_overrides: dict) -> None:
    bridge = _bridge(route_contract_snapshot=_route(**route_overrides))
    runtime = _runtime(bridge)
    controlled = _controlled(bridge, runtime)

    result = _build(bridge=bridge, runtime=runtime, controlled=controlled)

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_STEP4_SPOOFING
    assert "step4_spoofing" in result.blocked_reasons


def test_real_transport_is_explicitly_blocked() -> None:
    result = _build(
        transport_contract=_contract(
            transport_mode=RealTransportMode.REAL_TRANSPORT,
            is_stub_transport=False,
            is_real_transport=True,
        )
    )

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_REAL_TRANSPORT_NOT_ALLOWED


@pytest.mark.parametrize(
    "contract_overrides",
    [
        {"can_execute_http_post": True},
        {"can_call_order_endpoint": True},
        {"can_call_live_order_once": True},
        {"imports_http_client": True},
        {"imports_private_api": True},
        {"imports_broker": True},
        {"imports_live_order_once": True},
        {"max_attempts": 2},
    ],
)
def test_transport_live_path_capability_blocks(contract_overrides: dict) -> None:
    result = _build(transport_contract=_contract(**contract_overrides))

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_TRANSPORT_UNSAFE


@pytest.mark.parametrize(
    "request_overrides",
    [
        {"route_unsafe": True},
        {"real_http_post_executed": True},
        {"order_endpoint_called": True},
        {"live_order_once_called": True},
        {"broker_order_path_called": True},
    ],
)
def test_request_route_or_live_path_flags_block_transport(request_overrides: dict) -> None:
    result = _build(adapter_request=_request(**request_overrides))

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_TRANSPORT_UNSAFE


@pytest.mark.parametrize(
    "transport_result",
    [
        _transport_result(real_http_post_executed=True),
        _transport_result(order_endpoint_called=True),
        _transport_result(live_order_once_called=True),
        _transport_result(broker_order_path_called=True),
    ],
)
def test_stub_live_path_flags_block_transport(transport_result) -> None:
    result = _build(transport_result=transport_result)

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_TRANSPORT_UNSAFE


@pytest.mark.parametrize(
    "contract_overrides",
    [
        {"exposes_raw_request": True},
        {"exposes_raw_response": True},
        {"exposes_headers": True},
        {"exposes_signature": True},
        {"exposes_credentials": True},
        {"exposes_real_ids": True},
        {"returns_real_order_id": True},
        {"returns_raw_response": True},
    ],
)
def test_transport_raw_secret_or_id_exposure_blocks(contract_overrides: dict) -> None:
    result = _build(transport_contract=_contract(**contract_overrides))

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_RAW_OR_SECRET_EXPOSURE


@pytest.mark.parametrize(
    "transport_result",
    [
        _transport_result(raw_request_present=True),
        _transport_result(raw_response_present=True),
        _transport_result(headers_present=True),
        _transport_result(signature_present=True),
        _transport_result(credentials_present=True),
        _transport_result(real_order_id_present=True),
        _transport_result(real_execution_id_present=True),
        _transport_result(real_position_id_present=True),
        _transport_result(real_client_order_id_present=True),
        _transport_result(result_is_stub=False),
    ],
)
def test_stub_raw_secret_or_id_exposure_blocks(transport_result) -> None:
    result = _build(transport_result=transport_result)

    assert result.status is RealAdapterStatus.BLOCKED_STEP6G_REAL_ADAPTER_RAW_OR_SECRET_EXPOSURE


@pytest.mark.parametrize(
    "category",
    [
        StubTransportResultCategory.STUB_REAL_ADAPTER_ACCEPTED_NO_API_NO_POST,
        StubTransportResultCategory.STUB_REAL_ADAPTER_REJECTED_NO_RETRY_NO_API_NO_POST,
        StubTransportResultCategory.STUB_REAL_ADAPTER_RESULT_UNKNOWN_NO_RETRY_NO_API_NO_POST,
        StubTransportResultCategory.STUB_REAL_ADAPTER_TIMEOUT_NO_RETRY_NO_API_NO_POST,
    ],
)
def test_stub_result_categories_do_not_retry_or_mark_real_post(category) -> None:
    bridge = _bridge()
    runtime = _runtime(bridge)
    controlled = _controlled(bridge, runtime)

    result = run_live_order_real_step6g_real_adapter_with_stub_transport(
        step6g_post_route_bridge_result=bridge,
        step6g_runtime_bridge_result=runtime,
        step6g_controlled_adapter_result=controlled,
        stub_transport_result_category=category,
        created_at=CREATED_AT,
    )

    assert result.status is RealAdapterStatus.STEP6G_REAL_ADAPTER_STUB_COMPLETED_NO_API_NO_POST
    assert result.stub_transport_result_category == category.value
    assert result.real_http_post_executed is False
    assert result.post_executed is False
    assert result.blocked_reasons == ()


def test_renderer_includes_stub_only_warnings_and_no_forbidden_payloads() -> None:
    result = _build(transport_result=_transport_result())
    rendered = render_live_order_real_step6g_real_adapter_markdown(result)

    assert "This real adapter contract is stub transport only." in rendered
    assert "does not execute API calls" in rendered
    assert "does not execute HTTP POST" in rendered
    assert "does not call order endpoint" in rendered
    assert "does not call live_order_once" in rendered
    assert "does not reuse old final confirmation" in rendered
    assert "Future real transport implementation must be a separate Step." in rendered
    assert "real_http_post_executed: false" in rendered
    assert "order_endpoint_called: false" in rendered
    assert "live_order_once_called: false" in rendered
    forbidden = (
        "APPROVAL_COMMAND_FULL_TEXT_SENTINEL",
        "RAW_RESPONSE_SENTINEL",
        "SECRET_SENTINEL",
        "REAL_ORDER_ID_SENTINEL",
    )
    for token in forbidden:
        assert token not in rendered


def test_serialization_contains_no_raw_secret_real_ids_or_full_approval_command() -> None:
    result = _build(transport_result=_transport_result())
    payload = str(asdict(result))

    forbidden = (
        "APPROVAL_COMMAND_FULL_TEXT_SENTINEL",
        "RAW_RESPONSE_SENTINEL",
        "SECRET_SENTINEL",
        "REAL_ORDER_ID_SENTINEL",
    )
    for token in forbidden:
        assert token not in payload
    assert "'real_http_post_executed': False" in payload
    assert "'order_endpoint_called': False" in payload
    assert "'live_order_once_called': False" in payload
    assert "'post_executed': False" in payload


def test_new_module_does_not_import_http_private_broker_or_live_order_once() -> None:
    module_path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_step6g_real_adapter.py"
    )
    tree = ast.parse(module_path.read_text())
    forbidden_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "http.client",
        "socket",
        "subprocess",
        "app.brokers",
        "app.private_api",
        "dotenv",
        "os",
        "app.live_verification.live_order_once",
    }
    forbidden_names = {
        "OrderRequest",
        "GMO_FX_API_KEY",
        "GMO_FX_API_SECRET",
        "Authorization",
        "speedOrder",
        "changeOrder",
        "cancelOrders",
        "closeOrder",
        "ENABLE_LIVE_TRADING",
        "LIVE_ORDER_PLACED",
        "BROKER_SUBMIT",
        "ORDER_SENT",
        "live_order_once",
        "pbcopy",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden_modules
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_modules
            assert not any(
                node.module and node.module.startswith(f"{module}.")
                for module in forbidden_modules
            )
            for alias in node.names:
                assert alias.name not in forbidden_names
        elif isinstance(node, ast.Name):
            assert node.id not in forbidden_names
