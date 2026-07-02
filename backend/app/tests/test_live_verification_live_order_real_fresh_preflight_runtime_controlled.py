from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.live_verification.live_order_real_final_exec_stack_controlled import (
    build_live_order_real_final_exec_stack_controlled,
)
from app.live_verification.live_order_real_fresh_preflight_runtime_controlled import (
    SAFE_LOCAL_STATIC_CHECK_LABEL,
    SAFE_PREFLIGHT_RUNTIME_LABEL,
    SAFE_PRIVATE_READ_ONLY_CHECK_LABEL,
    SAFE_PUBLIC_MARKET_CHECK_LABEL,
    LiveOrderRealFreshPreflightRuntimeControlledInput,
    LiveOrderRealFreshPreflightRuntimeControlledStatus,
    build_live_order_real_fresh_preflight_runtime_controlled,
    render_live_order_real_fresh_preflight_runtime_controlled_markdown,
)
from app.live_verification.live_order_real_post_guard_controlled import (
    build_live_order_real_post_guard_controlled,
)

Status = LiveOrderRealFreshPreflightRuntimeControlledStatus
CREDENTIAL_VALUE_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"
RAW_REQUEST_SENTINEL = "RAW_REQUEST_SHOULD_NOT_SURFACE"
RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
BROKER_RESPONSE_SENTINEL = "BROKER_RESPONSE_SHOULD_NOT_SURFACE"
API_RESPONSE_SENTINEL = "API_RESPONSE_SHOULD_NOT_SURFACE"
REAL_ID_SENTINEL = "REAL_ID_SHOULD_NOT_SURFACE"
CONFIRMATION_SENTINEL = "CONFIRMATION_PHRASE_SHOULD_NOT_SURFACE"
LEDGER_SENTINEL = "LEDGER_STATE_SHOULD_NOT_SURFACE"


def _input(
    **overrides: object,
) -> LiveOrderRealFreshPreflightRuntimeControlledInput:
    base = LiveOrderRealFreshPreflightRuntimeControlledInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_fresh_preflight_runtime_controlled(
        input_snapshot=_input(**overrides),
    )


def test_default_runtime_ready_no_execution_no_post() -> None:
    result = _build()

    assert result.status is Status.FRESH_PREFLIGHT_RUNTIME_READY_NO_EXECUTION
    assert result.fresh_preflight_runtime_ready is True
    assert (
        result.fresh_preflight_runtime_mode
        == "FRESH_PREFLIGHT_RUNTIME_CONTROLLED_IMPLEMENTATION_ONLY"
    )
    assert result.safe_preflight_runtime_label == SAFE_PREFLIGHT_RUNTIME_LABEL
    assert (
        result.safe_preflight_runtime_status
        == "FRESH_PREFLIGHT_RUNTIME_READY_NO_EXECUTION"
    )
    assert result.public_market_check_ready is True
    assert result.safe_public_market_check_label == SAFE_PUBLIC_MARKET_CHECK_LABEL
    assert result.private_read_only_check_ready is True
    assert (
        result.safe_private_read_only_check_label
        == SAFE_PRIVATE_READ_ONLY_CHECK_LABEL
    )
    assert result.local_static_check_ready is True
    assert result.safe_local_static_check_label == SAFE_LOCAL_STATIC_CHECK_LABEL
    assert result.final_exec_stack_ready is True
    assert result.post_guard_ready is True
    assert result.no_order_guard_ready is True
    assert result.safe_account_assets_count == 1
    assert result.safe_open_positions_count == 0
    assert result.safe_active_orders_count == 0
    assert result.fresh_preflight_executed is False
    assert result.api_call_executed is False
    assert result.public_api_call_executed is False
    assert result.private_api_call_executed is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.final_confirmation_received is False
    assert result.ledger_updated is False
    assert result.attempt_counter_persisted is False
    assert result.actual_result_receipt_received is False
    assert result.actual_receipt_handoff_executed is False
    assert result.blocked_reasons == ()


def test_safe_prerequisite_results_drive_runtime_without_values_or_raw() -> None:
    final_exec_stack_result = build_live_order_real_final_exec_stack_controlled()
    post_guard_result = build_live_order_real_post_guard_controlled()
    result = build_live_order_real_fresh_preflight_runtime_controlled(
        final_exec_stack_result=final_exec_stack_result,
        post_guard_result=post_guard_result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.FRESH_PREFLIGHT_RUNTIME_READY_NO_EXECUTION
    assert result.final_exec_stack_prerequisite_satisfied is True
    assert result.post_guard_prerequisite_satisfied is True
    assert result.fresh_preflight_runtime_ready is True
    for forbidden in (
        CREDENTIAL_VALUE_SENTINEL,
        SIGNATURE_VALUE_SENTINEL,
        HEADERS_VALUE_SENTINEL,
        RAW_REQUEST_SENTINEL,
        RAW_RESPONSE_SENTINEL,
        BROKER_RESPONSE_SENTINEL,
        API_RESPONSE_SENTINEL,
        REAL_ID_SENTINEL,
        CONFIRMATION_SENTINEL,
        LEDGER_SENTINEL,
    ):
        assert forbidden not in payload


@pytest.mark.parametrize(
    ("overrides", "expected_status", "expected_reason"),
    [
        (
            {"public_market_check_ready": False},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_PUBLIC_MARKET,
            "public_market_check_missing_or_not_ready",
        ),
        (
            {"private_read_only_check_ready": False},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_PRIVATE_READ_ONLY,
            "private_read_only_check_missing_or_not_ready",
        ),
        (
            {"local_static_check_ready": False},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_LOCAL_STATIC,
            "local_static_check_missing_or_not_ready",
        ),
        (
            {"final_exec_stack_ready": False},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_FINAL_EXEC_STACK,
            "final_exec_stack_missing_or_not_ready",
        ),
        (
            {"post_guard_ready": False},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_LOCAL_STATIC,
            "post_guard_missing_or_not_ready",
        ),
    ],
)
def test_missing_route_prerequisites_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
    expected_reason: str,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.fresh_preflight_runtime_ready is False
    assert expected_reason in result.blocked_reasons
    assert result.post_executed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"fresh_preflight_runtime_unknown": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_UNKNOWN,
        ),
        (
            {"fresh_preflight_runtime_failed": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_FAILED,
        ),
        (
            {"fresh_preflight_runtime_timeout": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_TIMEOUT,
        ),
        (
            {"fresh_preflight_runtime_unavailable": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_UNAVAILABLE,
        ),
        (
            {"fresh_preflight_runtime_stale": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_STALE,
        ),
        (
            {"fresh_preflight_runtime_reused": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_REUSED,
        ),
        (
            {"safe_open_positions_count": 1},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_PRIVATE_READ_ONLY,
        ),
        (
            {"safe_active_orders_count": 1},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_MISSING_PRIVATE_READ_ONLY,
        ),
    ],
)
def test_runtime_unknown_failed_timeout_unavailable_stale_reused_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.fresh_preflight_runtime_ready is False
    assert result.post_executed is False
    assert result.final_confirmation_received is False


@pytest.mark.parametrize(
    ("overrides", "expected_status", "expected_reason"),
    [
        (
            {"fresh_preflight_executed": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_FAILED,
            "fresh_preflight_executed_in_runtime_contract_step",
        ),
        (
            {"post_executed": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_POST_ATTEMPTED,
            "api_or_post_attempted",
        ),
        (
            {"http_post_executed": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_POST_ATTEMPTED,
            "api_or_post_attempted",
        ),
        (
            {"order_endpoint_called": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_ORDER_ENDPOINT,
            "order_endpoint_called",
        ),
        (
            {"live_order_once_called": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_LIVE_ORDER_ONCE,
            "live_order_once_called",
        ),
        (
            {"final_confirmation_received": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_FINAL_CONFIRMATION,
            "final_confirmation_received",
        ),
        (
            {"ledger_updated": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_LEDGER_UPDATE,
            "ledger_or_attempt_counter_attempted",
        ),
        (
            {"actual_receipt_handoff_executed": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_ACTUAL_RECEIPT,
            "actual_receipt_or_handoff_attempted",
        ),
    ],
)
def test_execution_attempts_block_but_returned_flags_remain_false(
    overrides: dict[str, object],
    expected_status: Status,
    expected_reason: str,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert expected_reason in result.blocked_reasons
    assert result.fresh_preflight_executed is False
    assert result.api_call_executed is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.final_confirmation_received is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status", "expected_reason"),
    [
        (
            {"raw_request_exposure_attempted": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_RAW_EXPOSURE,
            "raw_or_response_exposure_attempted",
        ),
        (
            {"broker_response_exposure_attempted": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_RAW_EXPOSURE,
            "raw_or_response_exposure_attempted",
        ),
        (
            {"real_id_exposure_attempted": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_ID_EXPOSURE,
            "id_exposure_attempted",
        ),
        (
            {"credential_value_exposure_attempted": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_VALUE_EXPOSURE,
            "value_exposure_attempted",
        ),
        (
            {"confirmation_phrase_exposure_attempted": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_VALUE_EXPOSURE,
            "value_exposure_attempted",
        ),
        (
            {"ledger_state_exposure_attempted": True},
            Status.FRESH_PREFLIGHT_RUNTIME_BLOCKED_VALUE_EXPOSURE,
            "value_exposure_attempted",
        ),
    ],
)
def test_exposure_attempts_fail_closed_without_returning_exposure(
    overrides: dict[str, object],
    expected_status: Status,
    expected_reason: str,
) -> None:
    result = _build(**overrides)
    payload = repr(asdict(result))

    assert result.status is expected_status
    assert expected_reason in result.blocked_reasons
    assert result.raw_request_stored is False
    assert result.raw_response_stored is False
    assert result.broker_response_exposed is False
    assert result.api_response_exposed is False
    assert result.real_id_exposed is False
    assert result.ledger_state_actual_value_exposed is False
    for forbidden in (
        CREDENTIAL_VALUE_SENTINEL,
        SIGNATURE_VALUE_SENTINEL,
        HEADERS_VALUE_SENTINEL,
        RAW_REQUEST_SENTINEL,
        RAW_RESPONSE_SENTINEL,
        BROKER_RESPONSE_SENTINEL,
        API_RESPONSE_SENTINEL,
        REAL_ID_SENTINEL,
        CONFIRMATION_SENTINEL,
        LEDGER_SENTINEL,
    ):
        assert forbidden not in payload


def test_renderer_is_safe_summary_only() -> None:
    result = _build()
    rendered = render_live_order_real_fresh_preflight_runtime_controlled_markdown(
        result,
    )

    assert "fresh_preflight_runtime_ready: true" in rendered
    assert "fresh_preflight_executed: false" in rendered
    assert "post_executed: false" in rendered
    assert "http_post_executed: false" in rendered
    assert "order_endpoint_called: false" in rendered
    assert "live_order_once_called: false" in rendered
    assert "final_confirmation_received: false" in rendered
    assert "ledger_updated: false" in rendered
    for forbidden in (
        CREDENTIAL_VALUE_SENTINEL,
        SIGNATURE_VALUE_SENTINEL,
        HEADERS_VALUE_SENTINEL,
        RAW_REQUEST_SENTINEL,
        RAW_RESPONSE_SENTINEL,
        BROKER_RESPONSE_SENTINEL,
        API_RESPONSE_SENTINEL,
        REAL_ID_SENTINEL,
        CONFIRMATION_SENTINEL,
        LEDGER_SENTINEL,
    ):
        assert forbidden not in rendered
