from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.live_verification.live_order_real_fresh_preflight_execution_controlled import (
    SAFE_PREFLIGHT_EXECUTION_LABEL,
    LiveOrderRealFreshPreflightExecutionControlledInput,
    LiveOrderRealFreshPreflightExecutionControlledStatus,
    build_live_order_real_fresh_preflight_execution_controlled,
    render_live_order_real_fresh_preflight_execution_controlled_markdown,
)
from app.live_verification.live_order_real_fresh_preflight_runtime_controlled import (
    LiveOrderRealFreshPreflightRuntimeControlledInput,
    build_live_order_real_fresh_preflight_runtime_controlled,
)

Status = LiveOrderRealFreshPreflightExecutionControlledStatus
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
) -> LiveOrderRealFreshPreflightExecutionControlledInput:
    base = LiveOrderRealFreshPreflightExecutionControlledInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_fresh_preflight_execution_controlled(
        input_snapshot=_input(**overrides),
    )


def _runtime(**overrides: object):
    base = LiveOrderRealFreshPreflightRuntimeControlledInput()
    return build_live_order_real_fresh_preflight_runtime_controlled(
        input_snapshot=replace(base, **overrides),
    )


def test_default_execution_adapter_ready_no_execution_no_post() -> None:
    result = _build()

    assert result.status is Status.FRESH_PREFLIGHT_EXECUTION_ADAPTER_READY_NO_EXECUTION
    assert result.fresh_preflight_execution_command_available is True
    assert result.fresh_preflight_execution_allowed_next_step is True
    assert result.safe_preflight_execution_label == SAFE_PREFLIGHT_EXECUTION_LABEL
    assert result.fresh_preflight_execution_performed is False
    assert result.fresh_preflight_new_marker_required is True
    assert result.fresh_preflight_current_marker_required is True
    assert result.fresh_preflight_non_reuse_required is True
    assert result.fresh_preflight_adapter_at_most_once is True
    assert result.fresh_preflight_retry_allowed is False
    assert result.fresh_preflight_unknown_retry_allowed is False
    assert result.fresh_preflight_timeout_retry_allowed is False
    assert result.fresh_preflight_failed_retry_allowed is False
    assert result.public_market_check_available is True
    assert result.private_read_only_check_available is True
    assert result.local_static_check_available is True
    assert result.api_call_executed is False
    assert result.public_api_call_executed is False
    assert result.private_api_call_executed is False
    assert result.post_allowed_this_step is False
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


@pytest.mark.parametrize(
    ("overrides", "expected_status", "expected_reason"),
    [
        (
            {"fresh_preflight_execution_adapter_requested": False},
            Status.FRESH_PREFLIGHT_EXECUTION_ADAPTER_NOT_READY,
            "fresh_preflight_execution_adapter_contract_missing",
        ),
        (
            {"public_market_execution_mapping_available": False},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_PUBLIC_MARKET,
            "public_market_execution_mapping_missing_or_not_ready",
        ),
        (
            {"private_read_only_execution_mapping_available": False},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_PRIVATE_READ_ONLY,
            "private_read_only_execution_mapping_missing_or_not_ready",
        ),
        (
            {"local_static_execution_mapping_available": False},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_LOCAL_STATIC,
            "local_static_execution_mapping_missing_or_not_ready",
        ),
        (
            {"safe_output_renderer_ready": False},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_SAFE_RENDERER,
            "safe_output_renderer_missing_or_not_ready",
        ),
    ],
)
def test_missing_adapter_prerequisites_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
    expected_reason: str,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.fresh_preflight_execution_command_available is False
    assert result.fresh_preflight_execution_allowed_next_step is False
    assert expected_reason in result.blocked_reasons
    assert result.post_executed is False


def test_runtime_not_ready_blocks_execution_adapter() -> None:
    result = build_live_order_real_fresh_preflight_execution_controlled(
        runtime_result=_runtime(fresh_preflight_runtime_requested=False),
    )

    assert result.status is Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_RUNTIME
    assert result.fresh_preflight_execution_command_available is False
    assert result.fresh_preflight_execution_allowed_next_step is False
    assert "fresh_preflight_runtime_missing_or_not_ready" in result.blocked_reasons
    assert result.post_executed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"fresh_preflight_execution_unknown": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_UNKNOWN,
        ),
        (
            {"fresh_preflight_execution_failed": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_FAILED,
        ),
        (
            {"fresh_preflight_execution_timeout": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_TIMEOUT,
        ),
        (
            {"fresh_preflight_execution_unavailable": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_UNAVAILABLE,
        ),
        (
            {"fresh_preflight_execution_stale": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_STALE,
        ),
        (
            {"fresh_preflight_execution_reused": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_REUSED,
        ),
        (
            {"fresh_preflight_retry_allowed": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_FAILED,
        ),
    ],
)
def test_unknown_failed_timeout_unavailable_stale_reused_retry_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.fresh_preflight_execution_command_available is False
    assert result.post_executed is False
    assert result.final_confirmation_received is False


@pytest.mark.parametrize(
    ("overrides", "expected_status", "expected_reason"),
    [
        (
            {"fresh_preflight_execution_performed": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_FAILED,
            "fresh_preflight_execution_performed_in_adapter_setup_step",
        ),
        (
            {"post_executed": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_POST_ATTEMPTED,
            "api_or_post_attempted",
        ),
        (
            {"http_post_executed": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_POST_ATTEMPTED,
            "api_or_post_attempted",
        ),
        (
            {"order_endpoint_called": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_ORDER_ENDPOINT,
            "order_endpoint_called",
        ),
        (
            {"live_order_once_called": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_LIVE_ORDER_ONCE,
            "live_order_once_called",
        ),
        (
            {"final_confirmation_received": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_FINAL_CONFIRMATION,
            "final_confirmation_received",
        ),
        (
            {"ledger_updated": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_LEDGER_UPDATE,
            "ledger_or_attempt_counter_attempted",
        ),
        (
            {"actual_receipt_handoff_executed": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_ACTUAL_RECEIPT,
            "actual_receipt_or_handoff_attempted",
        ),
        (
            {"raw_response_exposure_attempted": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_RAW_EXPOSURE,
            "raw_or_response_exposure_attempted",
        ),
        (
            {"real_id_exposure_attempted": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_ID_EXPOSURE,
            "id_exposure_attempted",
        ),
        (
            {"credential_value_exposure_attempted": True},
            Status.FRESH_PREFLIGHT_EXECUTION_BLOCKED_VALUE_EXPOSURE,
            "value_exposure_attempted",
        ),
    ],
)
def test_execution_post_final_ledger_receipt_raw_id_value_attempts_block(
    overrides: dict[str, object],
    expected_status: Status,
    expected_reason: str,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert expected_reason in result.blocked_reasons
    assert result.fresh_preflight_execution_performed is False
    assert result.post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.final_confirmation_received is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False


def test_renderer_and_asdict_are_safe_summary_only() -> None:
    result = _build()
    rendered = render_live_order_real_fresh_preflight_execution_controlled_markdown(
        result,
    )
    payload = repr(asdict(result)) + rendered

    assert "fresh_preflight_execution_command_available: true" in rendered
    assert "fresh_preflight_execution_performed: false" in rendered
    assert "post_executed: false" in rendered
    assert "live_order_once_called: false" in rendered
    assert "final_confirmation_received: false" in rendered
    assert "ledger_updated: false" in rendered
    assert "actual_receipt_handoff_executed: false" in rendered
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
