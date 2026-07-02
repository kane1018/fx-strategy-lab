from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.live_verification.live_order_real_one_shot_post_approved_primitive_actual_source_controlled import (  # noqa: E501
    SAFE_APPROVED_PRIMITIVE_ACTUAL_SOURCE_LABEL,
    LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput,
    LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledStatus,
    build_live_order_real_one_shot_post_approved_primitive_actual_source_controlled,
    construct_live_order_real_one_shot_post_approved_primitive_actual_source_controlled,
    render_live_order_real_one_shot_post_approved_primitive_actual_source_markdown,
)
from app.live_verification.live_order_real_one_shot_post_approved_primitive_controlled import (  # noqa: E501
    construct_live_order_real_one_shot_post_approved_primitive_controlled,
)
from app.live_verification.live_order_real_one_shot_post_approved_primitive_source_controlled import (  # noqa: E501
    construct_live_order_real_one_shot_post_approved_primitive_source_controlled,
)
from app.live_verification.live_order_real_one_shot_post_execution_controlled import (
    LiveOrderRealOneShotPostExecutionControlledStatus,
    LiveOrderRealOneShotPostTransportInput,
    LiveOrderRealOneShotPostTransportResult,
    LiveOrderRealOneShotPostTransportResultCategory,
    LiveOrderRealPostSpecificConfirmationInput,
    execute_live_order_real_one_shot_post_execution_controlled,
    validate_live_order_real_post_specific_confirmation,
)
from app.live_verification.live_order_real_one_shot_post_real_transport_binding_controlled import (  # noqa: E501
    construct_live_order_real_one_shot_post_real_transport_binding_controlled,
)

ActualSourceStatus = (
    LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledStatus
)
ExecutionStatus = LiveOrderRealOneShotPostExecutionControlledStatus
TransportCategory = LiveOrderRealOneShotPostTransportResultCategory

CREDENTIAL_VALUE_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"
RAW_REQUEST_SENTINEL = "RAW_REQUEST_SHOULD_NOT_SURFACE"
RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
BROKER_RESPONSE_SENTINEL = "BROKER_RESPONSE_SHOULD_NOT_SURFACE"
API_RESPONSE_SENTINEL = "API_RESPONSE_SHOULD_NOT_SURFACE"
ACCOUNT_ID_SENTINEL = "ACCOUNT_ID_SHOULD_NOT_SURFACE"
ORDER_ID_SENTINEL = "ORDER_ID_SHOULD_NOT_SURFACE"
TRANSACTION_ID_SENTINEL = "TRANSACTION_ID_SHOULD_NOT_SURFACE"
REAL_ID_SENTINEL = "REAL_ID_SHOULD_NOT_SURFACE"
CONFIRMATION_SENTINEL = "CONFIRMATION_PHRASE_SHOULD_NOT_SURFACE"
LEDGER_SENTINEL = "LEDGER_STATE_SHOULD_NOT_SURFACE"


def _available_input() -> (
    LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput
):
    return LiveOrderRealOneShotPostApprovedPrimitiveActualSourceControlledInput(
        approved_primitive_actual_source_supplied=True,
    )


def _transport_result(
    category: TransportCategory = TransportCategory.TRANSPORT_ACCEPTED_SANITIZED,
    **overrides: object,
) -> LiveOrderRealOneShotPostTransportResult:
    return LiveOrderRealOneShotPostTransportResult(
        result_category=category,
        **overrides,
    )


def _confirmed():
    return validate_live_order_real_post_specific_confirmation(
        LiveOrderRealPostSpecificConfirmationInput(
            post_specific_confirmation_received=True,
            post_specific_confirmation_current_turn=True,
            post_specific_confirmation_new=True,
            post_specific_confirmation_one_time=True,
        ),
    )


def _execute_with_actual_source(fake_actual_source):
    actual_source_boundary = (
        construct_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
            actual_source=fake_actual_source,
        )
    )
    source_boundary = (
        construct_live_order_real_one_shot_post_approved_primitive_source_controlled(
            source=actual_source_boundary.approved_primitive_actual_source,
        )
    )
    approved = construct_live_order_real_one_shot_post_approved_primitive_controlled(
        primitive=source_boundary.approved_primitive_source,
    )
    binding = construct_live_order_real_one_shot_post_real_transport_binding_controlled(
        primitive=approved.controlled_primitive,
    )
    result = execute_live_order_real_one_shot_post_execution_controlled(
        transport=binding.controlled_transport,
        confirmation=_confirmed(),
    )
    return actual_source_boundary, source_boundary, approved, binding, result


def test_approved_primitive_actual_source_summary_is_safe_only_and_does_not_post() -> (
    None
):
    summary = (
        build_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
            _available_input(),
        )
    )
    rendered = (
        render_live_order_real_one_shot_post_approved_primitive_actual_source_markdown(
            summary,
        )
    )
    payload = repr(asdict(summary))

    assert (
        summary.status
        is ActualSourceStatus.APPROVED_PRIMITIVE_ACTUAL_SOURCE_READY_NO_POST
    )
    assert summary.approved_primitive_actual_source_available is True
    assert (
        summary.approved_primitive_actual_source_label
        == SAFE_APPROVED_PRIMITIVE_ACTUAL_SOURCE_LABEL
    )
    assert summary.approved_primitive_actual_source_default_no_execution is True
    assert summary.approved_primitive_actual_source_import_executes_post is False
    assert summary.approved_primitive_actual_source_construct_executes_post is False
    assert summary.approved_primitive_actual_source_summary_executes_post is False
    assert summary.approved_primitive_source_boundary_compatible is True
    assert summary.approved_primitive_boundary_compatible is True
    assert summary.controlled_binding_compatible is True
    assert summary.controlled_executor_required is True
    assert summary.post_specific_confirmation_required is True
    assert summary.one_post_max is True
    assert summary.retry_allowed is False
    assert summary.timeout_fail_closed is True
    assert summary.ledger_update_this_step is False
    assert summary.receipt_handoff_this_step is False
    assert summary.actual_http_post_executed is False
    assert summary.actual_source_attempted is False
    assert summary.actual_source_call_count == 0
    assert summary.post_execution_count == 0
    assert summary.retry_attempted is False
    assert summary.second_post_attempted is False
    assert summary.raw_request_exposed is False
    assert summary.real_id_exposed is False
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in rendered
        assert forbidden not in payload


def test_approved_primitive_actual_source_blocks_missing_source() -> None:
    summary = (
        build_live_order_real_one_shot_post_approved_primitive_actual_source_controlled()
    )

    assert summary.approved_primitive_actual_source_available is False
    assert summary.status is (
        ActualSourceStatus.APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_MISSING_SOURCE
    )
    assert "approved_primitive_actual_source_missing" in summary.blocked_reasons
    assert summary.actual_http_post_executed is False
    assert summary.actual_source_call_count == 0


def test_import_summary_and_construction_do_not_call_actual_source() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_actual_source(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result()

    summary = (
        build_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
            _available_input(),
        )
    )
    actual_source_boundary = (
        construct_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
            actual_source=fake_actual_source,
        )
    )
    rendered = (
        render_live_order_real_one_shot_post_approved_primitive_actual_source_markdown(
            summary,
        )
    )

    assert calls == []
    assert summary.approved_primitive_actual_source_available is True
    assert (
        actual_source_boundary.summary.approved_primitive_actual_source_available
        is True
    )
    assert "actual_http_post_executed: false" in rendered
    assert summary.actual_source_call_count == 0
    assert actual_source_boundary.summary.actual_source_call_count == 0


@pytest.mark.parametrize(
    ("override", "expected_status", "reason"),
    [
        (
            {"direct_live_order_once": True},
            (
                ActualSourceStatus
                .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_DIRECT_LIVE_ORDER_ONCE
            ),
            "direct_live_order_once",
        ),
        (
            {"direct_order_endpoint": True},
            (
                ActualSourceStatus
                .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_ORDER_ENDPOINT_DIRECT
            ),
            "direct_order_endpoint",
        ),
        (
            {"actual_source_retry_enabled": True},
            (
                ActualSourceStatus
                .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RETRY_ENABLED
            ),
            "actual_source_retry_enabled",
        ),
        (
            {"retry_allowed": True},
            (
                ActualSourceStatus
                .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RETRY_ENABLED
            ),
            "retry_allowed",
        ),
        (
            {"actual_source_timeout_fail_closed": False},
            (
                ActualSourceStatus
                .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_TIMEOUT_NOT_FAIL_CLOSED
            ),
            "actual_source_timeout_fail_closed_missing",
        ),
        (
            {"actual_source_ledger_coupled": True},
            (
                ActualSourceStatus
                .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_LEDGER_COUPLED
            ),
            "actual_source_ledger_coupled",
        ),
        (
            {"actual_source_receipt_coupled": True},
            (
                ActualSourceStatus
                .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RECEIPT_COUPLED
            ),
            "actual_source_receipt_coupled",
        ),
        (
            {"actual_source_raw_exposure": True},
            (
                ActualSourceStatus
                .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_RAW_EXPOSURE
            ),
            "actual_source_raw_exposure",
        ),
        (
            {"actual_source_id_exposure": True},
            (
                ActualSourceStatus
                .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_ID_EXPOSURE
            ),
            "actual_source_id_exposure",
        ),
        (
            {"actual_source_value_exposure": True},
            (
                ActualSourceStatus
                .APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_VALUE_EXPOSURE
            ),
            "actual_source_value_exposure",
        ),
    ],
)
def test_approved_primitive_actual_source_blocks_unsafe_contracts(
    override: dict[str, object],
    expected_status: ActualSourceStatus,
    reason: str,
) -> None:
    summary = (
        build_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
            replace(_available_input(), **override),
        )
    )

    assert summary.approved_primitive_actual_source_available is False
    assert summary.status is expected_status
    assert reason in summary.blocked_reasons
    assert summary.actual_http_post_executed is False
    assert summary.ledger_updated is False
    assert summary.actual_receipt_handoff_executed is False


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        (
            {"approved_primitive_source_boundary_compatible": False},
            "approved_primitive_source_boundary_compatible_missing",
        ),
        (
            {"approved_primitive_boundary_compatible": False},
            "approved_primitive_boundary_compatible_missing",
        ),
        (
            {"controlled_binding_compatible": False},
            "controlled_binding_compatible_missing",
        ),
    ],
)
def test_approved_primitive_actual_source_blocks_missing_compatibility(
    override: dict[str, object],
    reason: str,
) -> None:
    summary = (
        build_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
            replace(_available_input(), **override),
        )
    )

    assert summary.approved_primitive_actual_source_available is False
    assert summary.status is (
        ActualSourceStatus.APPROVED_PRIMITIVE_ACTUAL_SOURCE_BLOCKED_MISSING_SOURCE
    )
    assert reason in summary.blocked_reasons
    assert summary.post_execution_count == 0


def test_blocked_actual_source_does_not_call_candidate() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_actual_source(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result()

    actual_source_boundary = (
        construct_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
            actual_source=fake_actual_source,
            input_snapshot=replace(
                _available_input(),
                actual_source_retry_enabled=True,
            ),
        )
    )
    source_boundary = (
        construct_live_order_real_one_shot_post_approved_primitive_source_controlled(
            source=actual_source_boundary.approved_primitive_actual_source,
        )
    )
    approved = construct_live_order_real_one_shot_post_approved_primitive_controlled(
        primitive=source_boundary.approved_primitive_source,
    )
    binding = construct_live_order_real_one_shot_post_real_transport_binding_controlled(
        primitive=approved.controlled_primitive,
    )
    result = execute_live_order_real_one_shot_post_execution_controlled(
        transport=binding.controlled_transport,
        confirmation=_confirmed(),
    )

    assert calls == []
    assert (
        actual_source_boundary.summary.approved_primitive_actual_source_available
        is False
    )
    assert source_boundary.summary.approved_primitive_source_available is True
    assert approved.summary.approved_primitive_available is True
    assert binding.summary.real_transport_binding_available is True
    assert result.post_execution_count == 1
    assert result.status is (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_FAILED_FAIL_CLOSED
    )
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False


def test_source_boundary_approved_primitive_and_binding_use_fake_actual_source_once() -> (
    None
):
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_actual_source(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result(fake_transport_used=True)

    actual_source_boundary, source_boundary, approved, binding, result = (
        _execute_with_actual_source(fake_actual_source)
    )

    assert len(calls) == 1
    assert (
        actual_source_boundary.summary.approved_primitive_actual_source_available
        is True
    )
    assert source_boundary.summary.approved_primitive_source_available is True
    assert approved.summary.approved_primitive_available is True
    assert binding.summary.real_transport_binding_available is True
    assert result.status is (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY
    )
    assert result.post_execution_count == 1
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.http_post_executed is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False


@pytest.mark.parametrize(
    ("category", "expected_status"),
    [
        (
            TransportCategory.TRANSPORT_FAILED_FAIL_CLOSED,
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_FAILED_FAIL_CLOSED,
        ),
        (
            TransportCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED,
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_UNKNOWN_FAIL_CLOSED,
        ),
        (
            TransportCategory.TRANSPORT_UNAVAILABLE_FAIL_CLOSED,
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_UNAVAILABLE_FAIL_CLOSED,
        ),
    ],
)
def test_approved_primitive_actual_source_failure_unknown_unavailable_maps_safe_result(
    category: TransportCategory,
    expected_status: ExecutionStatus,
) -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_actual_source(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result(category)

    _, _, _, _, result = _execute_with_actual_source(fake_actual_source)

    assert len(calls) == 1
    assert result.status is expected_status
    assert result.post_execution_count == 1
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.raw_request_exposed is False
    assert result.real_id_exposed is False


def test_approved_primitive_actual_source_timeout_maps_to_fail_closed() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_actual_source(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        raise TimeoutError

    _, _, _, _, result = _execute_with_actual_source(fake_actual_source)

    assert len(calls) == 1
    assert result.status is (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_TIMEOUT_FAIL_CLOSED
    )
    assert result.post_execution_count == 1
    assert result.retry_attempted is False
    assert result.second_post_attempted is False


def test_approved_primitive_actual_source_non_result_maps_to_unknown_fail_closed() -> (
    None
):
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_actual_source(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return object()

    _, _, _, _, result = _execute_with_actual_source(fake_actual_source)

    assert len(calls) == 1
    assert result.status is (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_UNKNOWN_FAIL_CLOSED
    )
    assert result.retry_attempted is False
    assert result.second_post_attempted is False


def test_approved_primitive_actual_source_unsafe_result_is_sanitized() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_actual_source(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result(
            raw_request_exposed=True,
            raw_response_exposed=True,
            broker_api_response_exposed=True,
            credential_value_exposed=True,
            signature_value_exposed=True,
            headers_value_exposed=True,
            account_id_exposed=True,
            order_id_exposed=True,
            transaction_id_exposed=True,
            ledger_updated=True,
            attempt_counter_persisted=True,
            actual_receipt_handoff_executed=True,
        )

    _, _, _, _, result = _execute_with_actual_source(fake_actual_source)
    payload = repr(asdict(result))

    assert len(calls) == 1
    assert result.status is (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_FAILED_FAIL_CLOSED
    )
    assert result.raw_request_exposed is False
    assert result.raw_response_exposed is False
    assert result.broker_api_response_exposed is False
    assert result.credential_value_exposed is False
    assert result.signature_value_exposed is False
    assert result.headers_value_exposed is False
    assert result.account_id_exposed is False
    assert result.order_id_exposed is False
    assert result.transaction_id_exposed is False
    assert result.ledger_updated is False
    assert result.attempt_counter_persisted is False
    assert result.actual_receipt_handoff_executed is False
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload


_FORBIDDEN_SENTINELS = (
    CREDENTIAL_VALUE_SENTINEL,
    SIGNATURE_VALUE_SENTINEL,
    HEADERS_VALUE_SENTINEL,
    RAW_REQUEST_SENTINEL,
    RAW_RESPONSE_SENTINEL,
    BROKER_RESPONSE_SENTINEL,
    API_RESPONSE_SENTINEL,
    ACCOUNT_ID_SENTINEL,
    ORDER_ID_SENTINEL,
    TRANSACTION_ID_SENTINEL,
    REAL_ID_SENTINEL,
    CONFIRMATION_SENTINEL,
    LEDGER_SENTINEL,
)
