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
    AdapterStatus,
    LiveOrderRealStep6GControlledAdapterRequest,
    LiveOrderRealStep6GControlledTransportResult,
    TransportMode,
    TransportResultCategory,
    build_live_order_real_step6g_controlled_adapter,
    make_live_order_real_step6g_controlled_adapter_request,
    make_live_order_real_step6g_fake_transport_contract,
    render_live_order_real_step6g_controlled_adapter_markdown,
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


def _runtime(bridge=None):
    return run_live_order_real_step6g_fake_runtime_bridge(
        step6g_post_route_bridge_result=bridge or _bridge(),
        created_at=CREATED_AT,
    )


def _blocked_runtime(bridge=None):
    return build_live_order_real_step6g_runtime_bridge(
        step6g_post_route_bridge_result=bridge or _bridge(),
        runtime_request=None,
        fake_executor_result=None,
        created_at=CREATED_AT,
    )


def _request(**overrides: object) -> LiveOrderRealStep6GControlledAdapterRequest:
    bridge = _bridge()
    runtime = _runtime(bridge)
    request = make_live_order_real_step6g_controlled_adapter_request(
        step6g_post_route_bridge_result=bridge,
        step6g_runtime_bridge_result=runtime,
        fake_attempt_count=1,
    )
    return replace(request, **overrides)


def _contract(**overrides: object):
    contract = make_live_order_real_step6g_fake_transport_contract()
    return replace(contract, **overrides)


def _transport_result(**overrides: object) -> LiveOrderRealStep6GControlledTransportResult:
    values = {
        "fake_transport_attempted": True,
        "fake_transport_result_category": (
            TransportResultCategory.FAKE_CONTROLLED_ADAPTER_ACCEPTED_NO_API_NO_POST
        ),
        "fake_attempt_count": 1,
        "fake_retry_count": 0,
        "fake_loop_count": 0,
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
        "result_is_fake": True,
    }
    values.update(overrides)
    return LiveOrderRealStep6GControlledTransportResult(**values)


def test_valid_pb_runtime_and_fake_transport_accepted_completes_no_api_no_post() -> None:
    bridge = _bridge()
    runtime = _runtime(bridge)
    result = run_live_order_real_step6g_controlled_adapter_with_fake_transport(
        step6g_post_route_bridge_result=bridge,
        step6g_runtime_bridge_result=runtime,
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.STEP6G_CONTROLLED_ADAPTER_FAKE_COMPLETED_NO_API_NO_POST
    assert result.fake_adapter_ready is True
    assert result.fake_transport_attempted is True
    assert (
        result.fake_transport_result_category
        == "FAKE_CONTROLLED_ADAPTER_ACCEPTED_NO_API_NO_POST"
    )
    assert result.real_http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


def test_valid_pb_runtime_without_transport_result_is_fake_ready() -> None:
    bridge = _bridge()
    runtime = _runtime(bridge)
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=bridge,
        step6g_runtime_bridge_result=runtime,
        transport_contract=_contract(),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.STEP6G_CONTROLLED_ADAPTER_FAKE_READY_NO_API_NO_POST
    assert result.fake_adapter_ready is True
    assert result.fake_transport_attempted is False
    assert result.fake_transport_result_category == "NOT_RUN_FAKE_TRANSPORT_ONLY_NO_API_NO_POST"
    assert result.real_http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False


def test_pb_bridge_not_ready_blocks_input_not_ready() -> None:
    bridge = _bridge(approval_snapshot=_approval(approval_validation_passed=False))
    runtime = _blocked_runtime(bridge)
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=bridge,
        step6g_runtime_bridge_result=runtime,
        transport_contract=_contract(),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_INPUT_NOT_READY
    assert "post_route_bridge_not_ready" in result.blocked_reasons


def test_runtime_bridge_not_ready_blocks_input_not_ready() -> None:
    bridge = _bridge()
    runtime = build_live_order_real_step6g_runtime_bridge(
        step6g_post_route_bridge_result=bridge,
        runtime_request=replace(
            _runtime(bridge).request,
            final_confirmation_exact_match=False,
        ),
        created_at=CREATED_AT,
    )
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=bridge,
        step6g_runtime_bridge_result=runtime,
        transport_contract=_contract(),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_INPUT_NOT_READY
    assert "runtime_bridge_not_ready" in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"final_confirmation_exact_match": False}, "final_confirmation_exact_match_missing"),
        ({"final_confirmation_reused": True}, "final_confirmation_reused"),
        ({"approval_exact_match": False}, "approval_exact_match_missing"),
        ({"approval_artifact_reestablished": False}, "approval_artifact_reestablished_missing"),
        ({"approval_validation_passed": False}, "approval_validation_passed_missing"),
        ({"final_confirmation_preflight_passed": False}, "final_confirmation_preflight_missing"),
        ({"post_immediate_preflight_passed": False}, "post_immediate_preflight_missing"),
        ({"order_intent_exact_match": False}, "order_intent_exact_match_missing"),
        ({"symbol": "EUR_JPY"}, "symbol_not_usd_jpy"),
        ({"side": "SELL"}, "side_not_buy"),
        ({"size": 101}, "size_not_100"),
        ({"execution_type": "LIMIT"}, "execution_type_not_market"),
    ],
)
def test_input_readiness_blockers_block_input_not_ready(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=_bridge(),
        step6g_runtime_bridge_result=_runtime(),
        transport_contract=_contract(),
        adapter_request=_request(**override),
        transport_result=_transport_result(),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_INPUT_NOT_READY
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"post_attempt_count_before": 1}, "post_attempt_count_before_not_zero"),
        ({"post_attempt_limit": 2}, "post_attempt_limit_not_one"),
        ({"fake_attempt_count": 2}, "fake_attempt_count_exceeds_one"),
        ({"post_allowed_this_step": True}, "post_allowed_this_step_unsafe_for_fake_adapter"),
        ({"post_executed": True}, "post_executed_unsafe"),
        ({"allowed_for_live_persisted": True}, "allowed_for_live_persisted_unsafe"),
    ],
)
def test_attempt_state_blockers_block_attempt_state(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=_bridge(),
        step6g_runtime_bridge_result=_runtime(),
        transport_contract=_contract(),
        adapter_request=_request(**override),
        transport_result=_transport_result(),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_ATTEMPT_STATE
    assert reason in result.blocked_reasons


def test_fake_transport_attempt_count_over_one_blocks_attempt_state() -> None:
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=_bridge(),
        step6g_runtime_bridge_result=_runtime(),
        transport_contract=_contract(),
        adapter_request=_request(),
        transport_result=_transport_result(fake_attempt_count=2),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_ATTEMPT_STATE
    assert "fake_transport_attempt_count_exceeds_one" in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"retry_allowed": True}, "retry_allowed_unsafe"),
        ({"loop_allowed": True}, "loop_allowed_unsafe"),
        ({"add_order_allowed": True}, "add_order_allowed_unsafe"),
        ({"change_order_allowed": True}, "change_order_allowed_unsafe"),
        ({"cancel_order_allowed": True}, "cancel_order_allowed_unsafe"),
        ({"close_order_allowed": True}, "close_order_allowed_unsafe"),
    ],
)
def test_retry_loop_or_order_mutation_blocks_retry_or_loop(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=_bridge(),
        step6g_runtime_bridge_result=_runtime(),
        transport_contract=_contract(),
        adapter_request=_request(**override),
        transport_result=_transport_result(),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_RETRY_OR_LOOP
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("contract_override", "reason"),
    [
        ({"retry_on_unknown": True}, "transport_retry_on_unknown"),
        ({"retry_on_timeout": True}, "transport_retry_on_timeout"),
        ({"retry_on_reject": True}, "transport_retry_on_reject"),
    ],
)
def test_transport_retry_policy_blocks_retry_or_loop(
    contract_override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=_bridge(),
        step6g_runtime_bridge_result=_runtime(),
        transport_contract=_contract(**contract_override),
        adapter_request=_request(),
        transport_result=_transport_result(),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_RETRY_OR_LOOP
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("result_override", "reason"),
    [
        ({"fake_retry_count": 1}, "fake_transport_retry_count_non_zero"),
        ({"fake_loop_count": 1}, "fake_transport_loop_count_non_zero"),
    ],
)
def test_fake_transport_retry_or_loop_counts_block(
    result_override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=_bridge(),
        step6g_runtime_bridge_result=_runtime(),
        transport_contract=_contract(),
        adapter_request=_request(),
        transport_result=_transport_result(**result_override),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_RETRY_OR_LOOP
    assert reason in result.blocked_reasons


def test_real_transport_blocks_real_transport_not_allowed() -> None:
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=_bridge(),
        step6g_runtime_bridge_result=_runtime(),
        transport_contract=_contract(
            transport_mode=TransportMode.REAL_TRANSPORT,
            is_fake_transport=False,
            is_real_transport=True,
        ),
        adapter_request=_request(),
        transport_result=_transport_result(),
        created_at=CREATED_AT,
    )

    assert (
        result.status
        is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_REAL_TRANSPORT_NOT_ALLOWED
    )
    assert "transport_mode_not_fake_only" in result.blocked_reasons
    assert "transport_is_real" in result.blocked_reasons


@pytest.mark.parametrize(
    ("contract_override", "reason"),
    [
        ({"can_execute_http_post": True}, "transport_can_execute_http_post_unsafe"),
        ({"can_call_order_endpoint": True}, "transport_can_call_order_endpoint_unsafe"),
        ({"can_call_live_order_once": True}, "transport_can_call_live_order_once_unsafe"),
        ({"imports_http_client": True}, "transport_imports_http_client_unsafe"),
        ({"imports_private_api": True}, "transport_imports_private_api_unsafe"),
        ({"imports_broker": True}, "transport_imports_broker_unsafe"),
        ({"imports_live_order_once": True}, "transport_imports_live_order_once_unsafe"),
        ({"max_attempts": 2}, "transport_max_attempts_not_one"),
    ],
)
def test_transport_capability_blocks_transport_unsafe(
    contract_override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=_bridge(),
        step6g_runtime_bridge_result=_runtime(),
        transport_contract=_contract(**contract_override),
        adapter_request=_request(),
        transport_result=_transport_result(),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_TRANSPORT_UNSAFE
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("request_override", "result_override", "reason"),
    [
        ({"real_http_post_executed": True}, {}, "real_http_post_executed_unsafe"),
        ({"order_endpoint_called": True}, {}, "order_endpoint_called_unsafe"),
        ({"live_order_once_called": True}, {}, "live_order_once_called_unsafe"),
        ({"broker_order_path_called": True}, {}, "broker_order_path_called_unsafe"),
        ({}, {"real_http_post_executed": True}, "fake_transport_real_http_post_executed_unsafe"),
        ({}, {"order_endpoint_called": True}, "fake_transport_order_endpoint_called_unsafe"),
        ({}, {"live_order_once_called": True}, "fake_transport_live_order_once_called_unsafe"),
        ({}, {"broker_order_path_called": True}, "fake_transport_broker_order_path_called_unsafe"),
    ],
)
def test_request_or_fake_result_live_path_flags_block_transport_unsafe(
    request_override: dict[str, object],
    result_override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=_bridge(),
        step6g_runtime_bridge_result=_runtime(),
        transport_contract=_contract(),
        adapter_request=_request(**request_override),
        transport_result=_transport_result(**result_override),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_TRANSPORT_UNSAFE
    assert reason in result.blocked_reasons
    assert result.real_http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False


@pytest.mark.parametrize(
    ("request_override", "contract_override", "result_override", "reason"),
    [
        ({"raw_secret_id_exposure": True}, {}, {}, "raw_secret_id_exposure"),
        ({}, {"exposes_raw_request": True}, {}, "transport_exposes_raw_request_unsafe"),
        ({}, {"exposes_raw_response": True}, {}, "transport_exposes_raw_response_unsafe"),
        ({}, {"exposes_headers": True}, {}, "transport_exposes_headers_unsafe"),
        ({}, {"exposes_signature": True}, {}, "transport_exposes_signature_unsafe"),
        ({}, {"exposes_credentials": True}, {}, "transport_exposes_credentials_unsafe"),
        ({}, {"exposes_real_ids": True}, {}, "transport_exposes_real_ids_unsafe"),
        ({}, {"returns_real_order_id": True}, {}, "transport_returns_real_order_id_unsafe"),
        ({}, {"returns_raw_response": True}, {}, "transport_returns_raw_response_unsafe"),
        ({}, {}, {"raw_request_present": True}, "fake_transport_raw_request_present_unsafe"),
        ({}, {}, {"raw_response_present": True}, "fake_transport_raw_response_present_unsafe"),
        ({}, {}, {"headers_present": True}, "fake_transport_headers_present_unsafe"),
        ({}, {}, {"signature_present": True}, "fake_transport_signature_present_unsafe"),
        ({}, {}, {"credentials_present": True}, "fake_transport_credentials_present_unsafe"),
        ({}, {}, {"real_order_id_present": True}, "fake_transport_real_order_id_present_unsafe"),
        (
            {},
            {},
            {"real_execution_id_present": True},
            "fake_transport_real_execution_id_present_unsafe",
        ),
        (
            {},
            {},
            {"real_position_id_present": True},
            "fake_transport_real_position_id_present_unsafe",
        ),
        (
            {},
            {},
            {"real_client_order_id_present": True},
            "fake_transport_real_client_order_id_present_unsafe",
        ),
        ({}, {}, {"result_is_fake": False}, "fake_transport_result_not_fake"),
    ],
)
def test_raw_secret_or_real_id_exposure_blocks(
    request_override: dict[str, object],
    contract_override: dict[str, object],
    result_override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_step6g_controlled_adapter(
        step6g_post_route_bridge_result=_bridge(),
        step6g_runtime_bridge_result=_runtime(),
        transport_contract=_contract(**contract_override),
        adapter_request=_request(**request_override),
        transport_result=_transport_result(**result_override),
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.BLOCKED_STEP6G_CONTROLLED_ADAPTER_RAW_OR_SECRET_EXPOSURE
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    "category",
    [
        TransportResultCategory.FAKE_CONTROLLED_ADAPTER_REJECTED_NO_RETRY_NO_API_NO_POST,
        TransportResultCategory.FAKE_CONTROLLED_ADAPTER_RESULT_UNKNOWN_NO_RETRY_NO_API_NO_POST,
        TransportResultCategory.FAKE_CONTROLLED_ADAPTER_TIMEOUT_NO_RETRY_NO_API_NO_POST,
    ],
)
def test_fake_rejected_timeout_or_unknown_does_not_retry(
    category: TransportResultCategory,
) -> None:
    bridge = _bridge()
    runtime = _runtime(bridge)
    result = run_live_order_real_step6g_controlled_adapter_with_fake_transport(
        step6g_post_route_bridge_result=bridge,
        step6g_runtime_bridge_result=runtime,
        fake_transport_result_category=category,
        created_at=CREATED_AT,
    )

    assert result.status is AdapterStatus.STEP6G_CONTROLLED_ADAPTER_FAKE_COMPLETED_NO_API_NO_POST
    assert result.fake_transport_result_category == category.value
    assert result.transport_result is not None
    assert result.transport_result.fake_retry_count == 0
    assert result.transport_result.fake_loop_count == 0
    assert result.post_executed is False


def test_renderer_includes_fake_only_warnings_and_no_secret_markers() -> None:
    bridge = _bridge()
    runtime = _runtime(bridge)
    result = run_live_order_real_step6g_controlled_adapter_with_fake_transport(
        step6g_post_route_bridge_result=bridge,
        step6g_runtime_bridge_result=runtime,
        created_at=CREATED_AT,
    )
    markdown = render_live_order_real_step6g_controlled_adapter_markdown(result)

    assert "This controlled adapter is fake transport only." in markdown
    assert "This controlled adapter does not execute API calls." in markdown
    assert "This controlled adapter does not execute HTTP POST." in markdown
    assert "This controlled adapter does not call order endpoint." in markdown
    assert "This controlled adapter does not call live_order_once." in markdown
    assert "This controlled adapter does not reuse old final confirmation." in markdown
    assert (
        "Future real Step 6G execution requires a new final confirmation and fresh preflight."
        in markdown
    )
    assert "FULL_APPROVAL_COMMAND_VALUE" not in markdown
    assert "RAW_RESPONSE_VALUE" not in markdown
    assert "REAL_ORDER_ID_VALUE" not in markdown
    assert "SECRET_VALUE" not in markdown


def test_serialization_contains_only_sanitized_fake_flags() -> None:
    bridge = _bridge()
    runtime = _runtime(bridge)
    result = run_live_order_real_step6g_controlled_adapter_with_fake_transport(
        step6g_post_route_bridge_result=bridge,
        step6g_runtime_bridge_result=runtime,
        created_at=CREATED_AT,
    )
    serialized = str(asdict(result))

    assert "FULL_APPROVAL_COMMAND_VALUE" not in serialized
    assert "RAW_REQUEST_VALUE" not in serialized
    assert "RAW_RESPONSE_VALUE" not in serialized
    assert "REAL_ORDER_ID_VALUE" not in serialized
    assert "SECRET_VALUE" not in serialized
    assert "real_http_post_executed': False" in serialized
    assert "order_endpoint_called': False" in serialized
    assert "live_order_once_called': False" in serialized


def test_new_controlled_adapter_module_has_no_api_order_or_live_order_once_imports() -> None:
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
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "load_live_order_attempt_ledger",
        "build_step4_approval_gate",
        "evaluate_step4_approval",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_step6g_controlled_adapter.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(not _is_blocked_module(alias.name, blocked_modules) for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _is_blocked_module(module, blocked_modules)
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            assert _call_name(node) not in blocked_call_names


def _is_blocked_module(module: str, blocked_modules: set[str]) -> bool:
    return any(module == blocked or module.startswith(f"{blocked}.") for blocked in blocked_modules)


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None
