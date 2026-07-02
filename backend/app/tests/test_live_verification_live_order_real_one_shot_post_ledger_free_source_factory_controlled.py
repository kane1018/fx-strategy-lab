from __future__ import annotations

from dataclasses import asdict

import pytest

from app.live_verification.live_order_real_one_shot_post_approved_primitive_actual_source_controlled import (  # noqa: E501
    build_current_live_order_real_one_shot_post_approved_primitive_actual_source_controlled,
    construct_current_live_order_real_one_shot_post_approved_primitive_actual_source_controlled,
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
from app.live_verification.live_order_real_one_shot_post_ledger_free_source_factory_controlled import (  # noqa: E501
    SAFE_LEDGER_FREE_SOURCE_CALLABLE_LABEL,
    SAFE_LEDGER_FREE_SOURCE_FACTORY_LABEL,
    LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput,
    LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledStatus,
    build_live_order_real_one_shot_post_ledger_free_source_factory_controlled,
    construct_live_order_real_one_shot_post_ledger_free_source_factory_controlled,
    make_live_order_real_one_shot_post_ledger_free_source,
    map_live_order_real_one_shot_post_ledger_free_source_outcome,
    render_live_order_real_one_shot_post_ledger_free_source_factory_markdown,
)
from app.live_verification.live_order_real_one_shot_post_real_transport_binding_controlled import (  # noqa: E501
    construct_live_order_real_one_shot_post_real_transport_binding_controlled,
)
from app.live_verification.live_order_real_one_shot_post_sealed_credential_signing_controlled import (  # noqa: E501
    LiveOrderRealOneShotPostSealedCredentialSigningControlledInput,
    build_live_order_real_one_shot_post_sealed_credential_signing_controlled,
)
from app.live_verification.live_order_real_one_shot_post_sealed_request_result_controlled import (  # noqa: E501
    LiveOrderRealOneShotPostSealedRequestResultControlledInput,
    LiveOrderRealSealedTransportSafeCategory,
    build_live_order_real_one_shot_post_sealed_request_result_controlled,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    SafePostResultCategory,
)

FactoryStatus = LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledStatus
ExecutionStatus = LiveOrderRealOneShotPostExecutionControlledStatus
TransportCategory = LiveOrderRealOneShotPostTransportResultCategory
TransportSafeCategory = LiveOrderRealSealedTransportSafeCategory

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
CLIENT_ORDER_ID_SENTINEL = "CLIENT_ORDER_ID_SHOULD_NOT_SURFACE"
LEDGER_SENTINEL = "LEDGER_STATE_SHOULD_NOT_SURFACE"

FORBIDDEN_SENTINELS = (
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
    CLIENT_ORDER_ID_SENTINEL,
    LEDGER_SENTINEL,
)


def _safe_payload(result: object) -> str:
    return repr(asdict(result))


def _assert_no_sentinel_exposure(*payloads: str) -> None:
    joined = "\n".join(payloads)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in joined


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


def _execute_factory_chain(source_delegate=None):
    factory = construct_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
        source_delegate=source_delegate,
    )
    source_boundary = (
        construct_live_order_real_one_shot_post_approved_primitive_source_controlled(
            source=factory.approved_primitive_actual_source.approved_primitive_actual_source,
        )
    )
    approved = construct_live_order_real_one_shot_post_approved_primitive_controlled(
        primitive=source_boundary.approved_primitive_source,
    )
    binding = construct_live_order_real_one_shot_post_real_transport_binding_controlled(
        primitive=approved.controlled_primitive,
    )
    execution = execute_live_order_real_one_shot_post_execution_controlled(
        transport=binding.controlled_transport,
        confirmation=_confirmed(),
    )
    return factory, source_boundary, approved, binding, execution


def test_factory_summary_is_safe_only_and_connects_current_route() -> None:
    result = build_live_order_real_one_shot_post_ledger_free_source_factory_controlled()
    rendered = render_live_order_real_one_shot_post_ledger_free_source_factory_markdown(
        result,
    )

    assert result.status is FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_READY_NO_POST
    assert result.ledger_free_post_only_source_factory_ready is True
    assert result.ledger_free_post_only_source_factory_label == (
        SAFE_LEDGER_FREE_SOURCE_FACTORY_LABEL
    )
    assert result.source_safe_label == SAFE_LEDGER_FREE_SOURCE_CALLABLE_LABEL
    assert result.factory_default_no_execution is True
    assert result.factory_import_executes_post is False
    assert result.factory_construct_executes_post is False
    assert result.factory_summary_executes_post is False
    assert result.factory_requires_sealed_request is True
    assert result.factory_requires_sealed_body is True
    assert result.factory_requires_sealed_credential_signing_provider is True
    assert result.factory_requires_safe_result_mapper is True
    assert result.factory_requires_post_specific_confirmation is True
    assert result.factory_produces_controlled_source_callable is True
    assert result.approved_primitive_actual_source_available is True
    assert result.actual_http_post_executed is False
    assert result.post_execution_count == 0
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False
    assert "actual_http_post_executed: false" in rendered
    _assert_no_sentinel_exposure(rendered, _safe_payload(result), repr(result))


def test_current_default_approved_actual_source_route_is_available_without_post() -> None:
    summary = build_current_live_order_real_one_shot_post_approved_primitive_actual_source_controlled()  # noqa: E501
    boundary = (
        construct_current_live_order_real_one_shot_post_approved_primitive_actual_source_controlled()
    )

    assert summary.approved_primitive_actual_source_available is True
    assert boundary.summary.approved_primitive_actual_source_available is True
    assert summary.actual_http_post_executed is False
    assert summary.post_execution_count == 0
    assert summary.retry_attempted is False
    assert summary.second_post_attempted is False


@pytest.mark.parametrize(
    ("override", "expected_status", "reason"),
    [
        (
            {"sealed_request_model_ready": False},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SEALED_REQUEST,
            "sealed_request_model_missing",
        ),
        (
            {"sealed_body_builder_ready": False},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SEALED_BODY,
            "sealed_body_builder_missing",
        ),
        (
            {"safe_result_mapper_ready": False},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SAFE_RESULT_MAPPER,
            "safe_result_mapper_missing",
        ),
        (
            {"sealed_credential_signing_provider_ready": False},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_CREDENTIAL_PROVIDER,
            "sealed_credential_signing_provider_missing",
        ),
        (
            {"sealed_credential_provider_ready": False},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_CREDENTIAL_PROVIDER,
            "sealed_credential_provider_missing",
        ),
        (
            {"sealed_signing_provider_ready": False},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SIGNING_PROVIDER,
            "sealed_signing_provider_missing",
        ),
        (
            {"sealed_headers_ready": False},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_HEADERS,
            "sealed_headers_missing",
        ),
        (
            {"credential_presence_available": False},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_CREDENTIAL_UNAVAILABLE,
            "credential_presence_unavailable",
        ),
    ],
)
def test_factory_blocks_missing_prerequisites(
    override: dict[str, object],
    expected_status: FactoryStatus,
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
        LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput(**override),
    )

    assert result.status is expected_status
    assert result.ledger_free_post_only_source_factory_ready is False
    assert result.approved_primitive_actual_source_available is False
    assert reason in result.blocked_reasons
    assert result.actual_post_allowed is False


def test_factory_blocks_blocked_sealed_request_and_provider_results() -> None:
    blocked_request = build_live_order_real_one_shot_post_sealed_request_result_controlled(
        LiveOrderRealOneShotPostSealedRequestResultControlledInput(
            safe_order_candidate_available=False,
        ),
    )
    blocked_provider = build_live_order_real_one_shot_post_sealed_credential_signing_controlled(
        LiveOrderRealOneShotPostSealedCredentialSigningControlledInput(
            credential_presence_available=False,
        ),
        sealed_request_result=build_live_order_real_one_shot_post_sealed_request_result_controlled(),
    )

    request_result = build_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
        sealed_request_result=blocked_request,
    )
    provider_result = build_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
        sealed_credential_signing_result=blocked_provider,
    )

    assert request_result.status is (
        FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_MISSING_SEALED_REQUEST
    )
    assert request_result.approved_primitive_actual_source_available is False
    assert provider_result.status is (
        FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_CREDENTIAL_UNAVAILABLE
    )
    assert provider_result.approved_primitive_actual_source_available is False


@pytest.mark.parametrize(
    ("override", "expected_status", "reason"),
    [
        (
            {"raw_request_exposure_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_RAW_EXPOSURE,
            "raw_request_exposure_attempted",
        ),
        (
            {"raw_response_exposure_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_RAW_EXPOSURE,
            "raw_response_exposure_attempted",
        ),
        (
            {"broker_api_response_exposure_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_RAW_EXPOSURE,
            "broker_api_response_exposure_attempted",
        ),
        (
            {"id_exposure_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_ID_EXPOSURE,
            "id_exposure_attempted",
        ),
        (
            {"client_order_id_actual_value_exposure_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_ID_EXPOSURE,
            "client_order_id_actual_value_exposure_attempted",
        ),
        (
            {"credential_value_exposure_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_VALUE_EXPOSURE,
            "credential_value_exposure_attempted",
        ),
        (
            {"signature_value_exposure_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_VALUE_EXPOSURE,
            "signature_value_exposure_attempted",
        ),
        (
            {"headers_value_exposure_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_VALUE_EXPOSURE,
            "headers_value_exposure_attempted",
        ),
    ],
)
def test_factory_blocks_raw_id_and_value_exposure_attempts(
    override: dict[str, object],
    expected_status: FactoryStatus,
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
        LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput(**override),
    )
    rendered = render_live_order_real_one_shot_post_ledger_free_source_factory_markdown(
        result,
    )

    assert result.status is expected_status
    assert reason in result.blocked_reasons
    assert result.raw_request_exposed is False
    assert result.credential_value_exposed is False
    _assert_no_sentinel_exposure(rendered, _safe_payload(result))


@pytest.mark.parametrize(
    ("override", "expected_status", "reason"),
    [
        (
            {"actual_http_post_executed": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_POST_OR_ORDER_EXECUTION,
            "actual_http_post_executed",
        ),
        (
            {"post_execution_count": 1},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_POST_OR_ORDER_EXECUTION,
            "post_execution_count_nonzero",
        ),
        (
            {"order_endpoint_executed": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_POST_OR_ORDER_EXECUTION,
            "order_endpoint_executed",
        ),
        (
            {"live_order_once_executed": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_POST_OR_ORDER_EXECUTION,
            "live_order_once_executed",
        ),
        (
            {"retry_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_LEDGER_RECEIPT_RETRY,
            "retry_attempted",
        ),
        (
            {"second_post_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_LEDGER_RECEIPT_RETRY,
            "second_post_attempted",
        ),
        (
            {"ledger_update_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_LEDGER_RECEIPT_RETRY,
            "ledger_update_attempted",
        ),
        (
            {"attempt_counter_persisted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_LEDGER_RECEIPT_RETRY,
            "attempt_counter_persisted",
        ),
        (
            {"receipt_handoff_attempted": True},
            FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_LEDGER_RECEIPT_RETRY,
            "receipt_handoff_attempted",
        ),
    ],
)
def test_factory_blocks_execution_and_lifecycle_attempts(
    override: dict[str, object],
    expected_status: FactoryStatus,
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
        LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput(**override),
    )

    assert result.status is expected_status
    assert reason in result.blocked_reasons
    assert result.actual_http_post_executed is False
    assert result.post_execution_count == 0
    assert result.retry_attempted is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"factory_default_no_execution": False}, "factory_default_no_execution_missing"),
        ({"factory_import_executes_post": True}, "factory_import_executes_post"),
        ({"factory_construct_executes_post": True}, "factory_construct_executes_post"),
        ({"factory_summary_executes_post": True}, "factory_summary_executes_post"),
        ({"factory_requires_post_specific_confirmation": False}, "factory_requires_post_specific_confirmation_missing"),  # noqa: E501
        ({"factory_produces_controlled_source_callable": False}, "factory_produces_controlled_source_callable_missing"),  # noqa: E501
        ({"one_post_max": False}, "one_post_max_missing"),
        ({"retry_allowed": True}, "retry_allowed"),
        ({"timeout_fail_closed": False}, "timeout_fail_closed_missing"),
        ({"actual_post_allowed": True}, "actual_post_allowed"),
        ({"ledger_update_allowed": True}, "ledger_update_allowed"),
        ({"receipt_handoff_allowed": True}, "receipt_handoff_allowed"),
        ({"approval_phrase_validation_coupled": True}, "approval_phrase_validation_coupled"),  # noqa: E501
    ],
)
def test_factory_blocks_unsafe_factory_contract(
    override: dict[str, object],
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
        LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput(**override),
    )

    assert result.status is (
        FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_BLOCKED_FACTORY_CONTRACT
    )
    assert reason in result.blocked_reasons
    assert result.approved_primitive_actual_source_available is False


def test_factory_construction_and_default_source_do_not_post() -> None:
    factory = construct_live_order_real_one_shot_post_ledger_free_source_factory_controlled()
    transport_input = LiveOrderRealOneShotPostTransportInput(
        execution_step="ONE_SHOT_POST_EXECUTION_GATE",
        symbol="USD_JPY",
        side="BUY",
        order_type="MARKET",
        size=1,
        time_in_force_label="NOT_PROVIDED_BY_SAFE_CANDIDATE",
        environment_label="STEP6G_CONTROLLED_REAL_ROUTE",
        risk_label="STEP6G_ONE_SHOT_SMALL_SIZE",
        one_post_max=True,
        retry_allowed=False,
        timeout_fail_closed=True,
    )
    default_result = factory.controlled_source(transport_input)

    assert factory.summary.ledger_free_post_only_source_factory_ready is True
    assert factory.summary.approved_primitive_actual_source_available is True
    assert factory.approved_primitive_actual_source.summary.approved_primitive_actual_source_available is True  # noqa: E501
    assert default_result.result_category is (
        TransportCategory.TRANSPORT_UNAVAILABLE_FAIL_CLOSED
    )
    assert default_result.unavailable is True
    assert default_result.http_post_executed is False
    assert default_result.retry_attempted is False
    assert default_result.second_post_attempted is False
    assert default_result.ledger_updated is False
    assert default_result.actual_receipt_handoff_executed is False


def test_controlled_source_callable_with_fake_transport_is_called_exactly_once() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_delegate(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result(fake_transport_used=True)

    factory, source_boundary, approved, binding, execution = _execute_factory_chain(
        source_delegate=fake_delegate,
    )

    assert len(calls) == 1
    assert factory.summary.ledger_free_post_only_source_factory_ready is True
    assert factory.summary.approved_primitive_actual_source_available is True
    assert source_boundary.summary.approved_primitive_source_available is True
    assert approved.summary.approved_primitive_available is True
    assert binding.summary.real_transport_binding_available is True
    assert execution.status is (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY
    )
    assert execution.post_execution_count == 1
    assert execution.http_post_executed is False
    assert execution.retry_attempted is False
    assert execution.second_post_attempted is False
    assert execution.ledger_updated is False
    assert execution.actual_receipt_handoff_executed is False
    assert execution.raw_request_exposed is False
    assert execution.real_id_exposed is False


@pytest.mark.parametrize(
    ("category", "expected_status"),
    [
        (
            TransportCategory.TRANSPORT_REJECTED_SANITIZED,
            ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_FAILED_FAIL_CLOSED,
        ),
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
def test_factory_source_failure_unknown_unavailable_and_rejected_fail_closed(
    category: TransportCategory,
    expected_status: ExecutionStatus,
) -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_delegate(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result(category, fake_transport_used=True)

    _, _, _, _, execution = _execute_factory_chain(source_delegate=fake_delegate)

    assert len(calls) == 1
    assert execution.status is expected_status
    assert execution.post_execution_count == 1
    assert execution.retry_attempted is False
    assert execution.second_post_attempted is False
    assert execution.raw_request_exposed is False
    assert execution.real_id_exposed is False


def test_factory_source_timeout_maps_fail_closed_without_retry() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_delegate(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        raise TimeoutError

    _, _, _, _, execution = _execute_factory_chain(source_delegate=fake_delegate)

    assert len(calls) == 1
    assert execution.status is (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_TIMEOUT_FAIL_CLOSED
    )
    assert execution.post_execution_count == 1
    assert execution.retry_attempted is False
    assert execution.second_post_attempted is False


def test_factory_source_non_result_maps_unknown_without_retry() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_delegate(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return object()

    _, _, _, _, execution = _execute_factory_chain(source_delegate=fake_delegate)

    assert len(calls) == 1
    assert execution.status is (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_UNKNOWN_FAIL_CLOSED
    )
    assert execution.retry_attempted is False
    assert execution.second_post_attempted is False


def test_factory_source_unsafe_result_is_sanitized() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_delegate(input_snapshot: LiveOrderRealOneShotPostTransportInput):
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

    _, _, _, _, execution = _execute_factory_chain(source_delegate=fake_delegate)
    payload = repr(asdict(execution))

    assert len(calls) == 1
    assert execution.status is (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_FAILED_FAIL_CLOSED
    )
    assert execution.raw_request_exposed is False
    assert execution.raw_response_exposed is False
    assert execution.broker_api_response_exposed is False
    assert execution.credential_value_exposed is False
    assert execution.signature_value_exposed is False
    assert execution.headers_value_exposed is False
    assert execution.account_id_exposed is False
    assert execution.order_id_exposed is False
    assert execution.transaction_id_exposed is False
    assert execution.ledger_updated is False
    assert execution.attempt_counter_persisted is False
    assert execution.actual_receipt_handoff_executed is False
    assert execution.retry_attempted is False
    assert execution.second_post_attempted is False
    _assert_no_sentinel_exposure(payload)


@pytest.mark.parametrize(
    ("transport_result", "expected_category", "sanitized_category"),
    [
        (
            _transport_result(TransportCategory.TRANSPORT_ACCEPTED_SANITIZED),
            TransportSafeCategory.ACCEPTED.value,
            SafePostResultCategory.RESULT_ACCEPTED_SANITIZED.value,
        ),
        (
            _transport_result(TransportCategory.TRANSPORT_REJECTED_SANITIZED),
            TransportSafeCategory.REJECTED.value,
            SafePostResultCategory.RESULT_REJECTED_SANITIZED.value,
        ),
        (
            _transport_result(
                TransportCategory.TRANSPORT_FAILED_FAIL_CLOSED,
                failed=True,
            ),
            TransportSafeCategory.FAILED.value,
            SafePostResultCategory.RESULT_UNKNOWN_FAIL_CLOSED.value,
        ),
        (
            _transport_result(
                TransportCategory.TRANSPORT_TIMEOUT_FAIL_CLOSED,
                timeout=True,
            ),
            TransportSafeCategory.TIMEOUT.value,
            SafePostResultCategory.RESULT_TIMEOUT_FAIL_CLOSED.value,
        ),
        (
            _transport_result(
                TransportCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED,
                unknown=True,
            ),
            TransportSafeCategory.UNKNOWN.value,
            SafePostResultCategory.RESULT_UNKNOWN_FAIL_CLOSED.value,
        ),
        (
            _transport_result(
                TransportCategory.TRANSPORT_UNAVAILABLE_FAIL_CLOSED,
                unavailable=True,
            ),
            TransportSafeCategory.UNAVAILABLE.value,
            SafePostResultCategory.RESULT_UNAVAILABLE_FAIL_CLOSED.value,
        ),
    ],
)
def test_factory_uses_safe_result_mapper_for_source_outcomes(
    transport_result: LiveOrderRealOneShotPostTransportResult,
    expected_category: str,
    sanitized_category: str,
) -> None:
    mapped = map_live_order_real_one_shot_post_ledger_free_source_outcome(
        transport_result,
    )

    assert mapped.transport_safe_category == expected_category
    assert mapped.sanitized_result_category == sanitized_category
    assert mapped.retry_allowed is False
    assert mapped.ledger_update_allowed is False
    assert mapped.receipt_handoff_allowed is False
    assert mapped.raw_response_exposed is False
    assert mapped.id_exposed is False


def test_make_source_does_not_retry_on_failure_or_timeout() -> None:
    failure_calls: list[LiveOrderRealOneShotPostTransportInput] = []
    timeout_calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def failing_delegate(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        failure_calls.append(input_snapshot)
        return _transport_result(TransportCategory.TRANSPORT_FAILED_FAIL_CLOSED)

    def timeout_delegate(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        timeout_calls.append(input_snapshot)
        raise TimeoutError

    transport_input = LiveOrderRealOneShotPostTransportInput(
        execution_step="ONE_SHOT_POST_EXECUTION_GATE",
        symbol="USD_JPY",
        side="BUY",
        order_type="MARKET",
        size=1,
        time_in_force_label="NOT_PROVIDED_BY_SAFE_CANDIDATE",
        environment_label="STEP6G_CONTROLLED_REAL_ROUTE",
        risk_label="STEP6G_ONE_SHOT_SMALL_SIZE",
        one_post_max=True,
        retry_allowed=False,
        timeout_fail_closed=True,
    )
    failing_source = make_live_order_real_one_shot_post_ledger_free_source(
        source_delegate=failing_delegate,
    )
    timeout_source = make_live_order_real_one_shot_post_ledger_free_source(
        source_delegate=timeout_delegate,
    )

    failing_result = failing_source(transport_input)
    timeout_result = timeout_source(transport_input)

    assert len(failure_calls) == 1
    assert len(timeout_calls) == 1
    assert failing_result.retry_attempted is False
    assert failing_result.second_post_attempted is False
    assert timeout_result.retry_attempted is False
    assert timeout_result.second_post_attempted is False
    assert timeout_result.timeout is True


def test_repr_asdict_and_renderer_do_not_expose_sentinel_labels() -> None:
    result = build_live_order_real_one_shot_post_ledger_free_source_factory_controlled(
        LiveOrderRealOneShotPostLedgerFreeSourceFactoryControlledInput(
            ledger_free_post_only_source_factory_label=RAW_REQUEST_SENTINEL,
            source_safe_label=CREDENTIAL_VALUE_SENTINEL,
        ),
    )
    rendered = render_live_order_real_one_shot_post_ledger_free_source_factory_markdown(
        result,
    )

    assert result.status is FactoryStatus.LEDGER_FREE_SOURCE_FACTORY_READY_NO_POST
    assert result.ledger_free_post_only_source_factory_label == "UNSUPPORTED_REDACTED"
    assert result.source_safe_label == "UNSUPPORTED_REDACTED"
    _assert_no_sentinel_exposure(repr(result), _safe_payload(result), rendered)
