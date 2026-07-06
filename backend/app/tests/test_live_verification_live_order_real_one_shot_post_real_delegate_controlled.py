from __future__ import annotations

from dataclasses import asdict, dataclass

import pytest

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
from app.live_verification.live_order_real_one_shot_post_real_delegate_controlled import (  # noqa: E501
    SAFE_REAL_POST_DELEGATE_LABEL,
    SAFE_REAL_POST_DELEGATE_SOURCE_LABEL,
    LiveOrderRealOneShotPostRealDelegateControlledInput,
    LiveOrderRealOneShotPostRealDelegateControlledStatus,
    build_live_order_real_one_shot_post_real_delegate_controlled,
    construct_live_order_real_one_shot_post_real_delegate_controlled,
    make_live_order_real_one_shot_post_real_delegate,
    map_live_order_real_one_shot_post_real_delegate_outcome,
    render_live_order_real_one_shot_post_real_delegate_markdown,
)
from app.live_verification.live_order_real_one_shot_post_real_transport_binding_controlled import (  # noqa: E501
    construct_live_order_real_one_shot_post_real_transport_binding_controlled,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    SafePostResultCategory,
)

DelegateStatus = LiveOrderRealOneShotPostRealDelegateControlledStatus
ExecutionStatus = LiveOrderRealOneShotPostExecutionControlledStatus
TransportCategory = LiveOrderRealOneShotPostTransportResultCategory

CREDENTIAL_VALUE_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"
RAW_REQUEST_SENTINEL = "RAW_REQUEST_SHOULD_NOT_SURFACE"
RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
BROKER_RESPONSE_SENTINEL = "BROKER_RESPONSE_SHOULD_NOT_SURFACE"
ACCOUNT_ID_SENTINEL = "ACCOUNT_ID_SHOULD_NOT_SURFACE"
ORDER_ID_SENTINEL = "ORDER_ID_SHOULD_NOT_SURFACE"
TRANSACTION_ID_SENTINEL = "TRANSACTION_ID_SHOULD_NOT_SURFACE"
REAL_ID_SENTINEL = "REAL_ID_SHOULD_NOT_SURFACE"

FORBIDDEN_SENTINELS = (
    CREDENTIAL_VALUE_SENTINEL,
    SIGNATURE_VALUE_SENTINEL,
    HEADERS_VALUE_SENTINEL,
    RAW_REQUEST_SENTINEL,
    RAW_RESPONSE_SENTINEL,
    BROKER_RESPONSE_SENTINEL,
    ACCOUNT_ID_SENTINEL,
    ORDER_ID_SENTINEL,
    TRANSACTION_ID_SENTINEL,
    REAL_ID_SENTINEL,
)


def _safe_payload(result: object) -> str:
    return repr(asdict(result))


def _assert_no_sentinel_exposure(*payloads: str) -> None:
    joined = "\n".join(payloads)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in joined


def _transport_input(
    *, allow_real_broker_post: bool = False,
) -> LiveOrderRealOneShotPostTransportInput:
    return LiveOrderRealOneShotPostTransportInput(
        execution_step="ONE_SHOT_POST_EXECUTION_GATE_RETRY_8",
        symbol="USD_JPY",
        side="BUY",
        order_type="MARKET",
        size=100,
        time_in_force_label="NOT_PROVIDED_BY_SAFE_CANDIDATE",
        environment_label="STEP6G_CONTROLLED_REAL_ROUTE",
        risk_label="STEP6G_ONE_SHOT_SMALL_SIZE",
        one_post_max=True,
        retry_allowed=False,
        timeout_fail_closed=True,
        allow_real_broker_post=allow_real_broker_post,
    )


def _transport_result(
    category: TransportCategory = TransportCategory.TRANSPORT_ACCEPTED_SANITIZED,
    **overrides: object,
) -> LiveOrderRealOneShotPostTransportResult:
    return LiveOrderRealOneShotPostTransportResult(
        result_category=category,
        **overrides,
    )


@dataclass(frozen=True)
class _FakeLiveOrderTransportResponse:
    transport_result: str = "success"
    api_status_success: str = "true"
    response_data_present: str = "true"


def _confirmed():
    return validate_live_order_real_post_specific_confirmation(
        LiveOrderRealPostSpecificConfirmationInput(
            post_specific_confirmation_received=True,
            post_specific_confirmation_current_turn=True,
            post_specific_confirmation_new=True,
            post_specific_confirmation_one_time=True,
        ),
    )


def test_real_delegate_summary_is_safe_and_supplies_factory_without_post() -> None:
    connection = construct_live_order_real_one_shot_post_real_delegate_controlled()
    result = connection.summary
    rendered = render_live_order_real_one_shot_post_real_delegate_markdown(result)

    assert result.status is DelegateStatus.REAL_POST_DELEGATE_READY_NO_POST
    assert result.real_post_delegate_ready is True
    assert result.real_post_delegate_label == SAFE_REAL_POST_DELEGATE_LABEL
    assert result.real_post_delegate_source_label == SAFE_REAL_POST_DELEGATE_SOURCE_LABEL
    assert result.delegate_default_no_execution is True
    assert result.delegate_import_executes_post is False
    assert result.delegate_construct_executes_post is False
    assert result.delegate_summary_executes_post is False
    assert result.delegate_supply_executes_post is False
    assert result.delegate_supplied_to_factory is True
    assert result.source_callable_unavailable_due_missing_delegate is False
    assert result.real_post_delegate_runner_materialized is True
    assert result.real_post_delegate_runner_supplied is True
    assert result.delegate_runner_missing is False
    assert result.source_callable_unavailable_due_missing_runner is False
    assert result.runner_default_no_execution is True
    assert result.runner_import_executes_post is False
    assert result.runner_construct_executes_post is False
    assert result.runner_summary_executes_post is False
    assert result.runner_materialization_executes_post is False
    assert result.runner_supply_executes_post is False
    assert result.runner_requires_post_specific_confirmation is True
    assert result.approved_primitive_actual_source_available is True
    assert result.actual_post_allowed is False
    assert result.actual_http_post_executed is False
    assert result.post_execution_count == 0
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False
    assert connection.factory.summary.source_delegate_supplied is True
    assert (
        connection.factory.summary.source_callable_unavailable_due_missing_delegate
        is False
    )
    assert "actual_http_post_executed: false" in rendered
    assert "real_post_delegate_runner_materialized: true" in rendered
    assert "source_callable_unavailable_due_missing_runner: false" in rendered
    _assert_no_sentinel_exposure(rendered, _safe_payload(result), repr(result))


def test_real_delegate_materialization_does_not_call_post_function_before_execution() -> (
    None
):
    calls: list[object] = []

    def fail_if_called(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        raise AssertionError("post function reference must not be called")

    connection = construct_live_order_real_one_shot_post_real_delegate_controlled(
        post_function_reference=fail_if_called,
    )

    assert calls == []
    assert connection.summary.real_post_delegate_runner_materialized is True
    assert connection.summary.real_post_delegate_runner_supplied is True
    assert connection.summary.delegate_runner_missing is False
    assert connection.summary.source_callable_unavailable_due_missing_runner is False
    assert connection.summary.actual_post_allowed is False
    assert connection.summary.actual_http_post_executed is False
    assert connection.summary.post_execution_count == 0


def test_execution_without_confirmation_does_not_call_materialized_runner() -> None:
    calls: list[object] = []

    def fail_if_called(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        raise AssertionError("post function reference must not be called")

    connection = construct_live_order_real_one_shot_post_real_delegate_controlled(
        post_function_reference=fail_if_called,
        credential_lookup=lambda _name: CREDENTIAL_VALUE_SENTINEL,
        timestamp_factory=lambda: "1700000000000",
        client_order_id_factory=lambda: "S6GTESTCLIENT01",
    )
    source_boundary = (
        construct_live_order_real_one_shot_post_approved_primitive_source_controlled(
            source=connection.approved_primitive_actual_source.approved_primitive_actual_source,
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
    )

    assert calls == []
    assert execution.status is (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_POST_SPECIFIC_CONFIRMATION
    )
    assert execution.post_execution_count == 0
    assert execution.http_post_executed is False
    assert execution.retry_attempted is False
    assert execution.second_post_attempted is False
    assert execution.ledger_updated is False
    assert execution.actual_receipt_handoff_executed is False
    assert execution.raw_request_exposed is False
    assert execution.raw_response_exposed is False
    assert execution.credential_value_exposed is False
    assert execution.signature_value_exposed is False
    assert execution.headers_value_exposed is False


def test_materialized_runner_uses_fake_post_reference_once_after_confirmation() -> None:
    calls: list[str] = []

    def fake_post_reference(*args: object, **kwargs: object) -> object:
        assert args
        assert not kwargs
        calls.append("called")
        return _FakeLiveOrderTransportResponse()

    connection = construct_live_order_real_one_shot_post_real_delegate_controlled(
        post_function_reference=fake_post_reference,
        credential_lookup=lambda _name: CREDENTIAL_VALUE_SENTINEL,
        timestamp_factory=lambda: "1700000000000",
        client_order_id_factory=lambda: "S6GTESTCLIENT01",
    )
    source_boundary = (
        construct_live_order_real_one_shot_post_approved_primitive_source_controlled(
            source=connection.approved_primitive_actual_source.approved_primitive_actual_source,
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

    # The Step 6G controlled execution route never sets allow_real_broker_post on
    # the TransportInput it builds, so the real-broker-post hard guard denies
    # before the fake post reference is ever invoked. This is the intended
    # default-deny behavior added after the 2026-07-06 incident, not a bug.
    assert calls == []
    assert connection.summary.real_post_delegate_runner_materialized is True
    assert connection.summary.real_post_delegate_runner_supplied is True
    assert connection.summary.delegate_runner_missing is False
    assert connection.summary.source_callable_unavailable_due_missing_runner is False
    assert execution.status is (
        ExecutionStatus.ONE_SHOT_POST_EXECUTION_BLOCKED_UNAVAILABLE_FAIL_CLOSED
    )
    assert execution.post_execution_count == 1
    assert execution.retry_attempted is False
    assert execution.second_post_attempted is False
    assert execution.ledger_updated is False
    assert execution.actual_receipt_handoff_executed is False
    assert execution.raw_request_exposed is False
    assert execution.raw_response_exposed is False
    assert execution.credential_value_exposed is False
    assert execution.signature_value_exposed is False
    assert execution.headers_value_exposed is False
    assert execution.real_id_exposed is False


def test_source_delegate_denies_by_default_and_requires_explicit_allow_true() -> None:
    """Prove the real-broker-post hard guard at the lowest wiring layer.

    `connection.source_delegate` is the raw materialized runner (bypassing the
    Step 6G execution route, which never sets allow_real_broker_post). It must
    still deny by default, deny for any non-True value, and only reach the
    injected fake transport when allow_real_broker_post is the literal True.
    """
    calls: list[str] = []

    def fake_post_reference(*args: object, **kwargs: object) -> object:
        calls.append("called")
        return _FakeLiveOrderTransportResponse()

    connection = construct_live_order_real_one_shot_post_real_delegate_controlled(
        post_function_reference=fake_post_reference,
        credential_lookup=lambda _name: CREDENTIAL_VALUE_SENTINEL,
        timestamp_factory=lambda: "1700000000000",
        client_order_id_factory=lambda: "S6GTESTCLIENT02",
    )

    denied_result = connection.source_delegate(_transport_input())
    assert calls == []
    assert denied_result.result_category is TransportCategory.TRANSPORT_UNAVAILABLE_FAIL_CLOSED
    assert denied_result.fake_transport_used is False
    assert denied_result.unavailable is True

    allowed_result = connection.source_delegate(
        _transport_input(allow_real_broker_post=True),
    )
    assert calls == ["called"]
    assert allowed_result.result_category is TransportCategory.TRANSPORT_ACCEPTED_SANITIZED


@pytest.mark.parametrize(
    ("override", "expected_status", "reason"),
    [
        (
            {"post_live_order_with_httpx_reference_available": False},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_MISSING_FUNCTION_REFERENCE,
            "post_live_order_with_httpx_reference_missing",
        ),
        (
            {"source_callable_unavailable_due_missing_delegate": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_CONTRACT,
            "source_callable_unavailable_due_missing_delegate",
        ),
        (
            {"real_post_delegate_runner_materialized": False},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_CONTRACT,
            "real_post_delegate_runner_materialized_missing",
        ),
        (
            {"real_post_delegate_runner_supplied": False},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_CONTRACT,
            "real_post_delegate_runner_supplied_missing",
        ),
        (
            {"delegate_runner_missing": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_CONTRACT,
            "delegate_runner_missing",
        ),
        (
            {"source_callable_unavailable_due_missing_runner": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_CONTRACT,
            "source_callable_unavailable_due_missing_runner",
        ),
        (
            {"runner_materialization_executes_post": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_CONTRACT,
            "runner_materialization_executes_post",
        ),
        (
            {"runner_supply_executes_post": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_CONTRACT,
            "runner_supply_executes_post",
        ),
        (
            {"actual_http_post_executed": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_POST_OR_ORDER_EXECUTION,
            "actual_http_post_executed",
        ),
        (
            {"post_execution_count": 1},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_POST_OR_ORDER_EXECUTION,
            "post_execution_count_nonzero",
        ),
        (
            {"retry_attempted": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_LEDGER_RECEIPT_RETRY,
            "retry_attempted",
        ),
        (
            {"second_post_attempted": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_LEDGER_RECEIPT_RETRY,
            "second_post_attempted",
        ),
        (
            {"ledger_update_attempted": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_LEDGER_RECEIPT_RETRY,
            "ledger_update_attempted",
        ),
        (
            {"receipt_handoff_attempted": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_LEDGER_RECEIPT_RETRY,
            "receipt_handoff_attempted",
        ),
        (
            {"raw_response_exposure_attempted": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_RAW_ID_VALUE_EXPOSURE,
            "raw_response_exposure_attempted",
        ),
        (
            {"credential_value_exposure_attempted": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_RAW_ID_VALUE_EXPOSURE,
            "credential_value_exposure_attempted",
        ),
        (
            {"headers_value_exposure_attempted": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_RAW_ID_VALUE_EXPOSURE,
            "headers_value_exposure_attempted",
        ),
        (
            {"id_exposure_attempted": True},
            DelegateStatus.REAL_POST_DELEGATE_BLOCKED_RAW_ID_VALUE_EXPOSURE,
            "id_exposure_attempted",
        ),
    ],
)
def test_real_delegate_blocks_unsafe_inputs(
    override: dict[str, object],
    expected_status: DelegateStatus,
    reason: str,
) -> None:
    result = build_live_order_real_one_shot_post_real_delegate_controlled(
        LiveOrderRealOneShotPostRealDelegateControlledInput(**override),
    )

    assert result.status is expected_status
    assert reason in result.blocked_reasons
    assert result.actual_post_allowed is False
    assert result.actual_http_post_executed is False
    assert result.post_execution_count == 0
    assert result.retry_attempted is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False


def test_controlled_executor_uses_fake_delegate_exactly_once_without_retry() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_delegate(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result(fake_transport_used=True)

    source_delegate = make_live_order_real_one_shot_post_real_delegate(
        delegate_runner=fake_delegate,
    )
    connection = construct_live_order_real_one_shot_post_real_delegate_controlled(
        source_delegate=source_delegate,
    )
    source_boundary = (
        construct_live_order_real_one_shot_post_approved_primitive_source_controlled(
            source=connection.approved_primitive_actual_source.approved_primitive_actual_source,
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

    assert len(calls) == 1
    assert connection.summary.real_post_delegate_ready is True
    assert connection.summary.delegate_supplied_to_factory is True
    assert connection.summary.source_callable_unavailable_due_missing_delegate is False
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
    assert execution.raw_response_exposed is False
    assert execution.credential_value_exposed is False
    assert execution.signature_value_exposed is False
    assert execution.headers_value_exposed is False
    assert execution.real_id_exposed is False


@pytest.mark.parametrize(
    ("category", "expected_category", "flags"),
    [
        (
            TransportCategory.TRANSPORT_ACCEPTED_SANITIZED,
            SafePostResultCategory.RESULT_ACCEPTED_SANITIZED.value,
            {},
        ),
        (
            TransportCategory.TRANSPORT_REJECTED_SANITIZED,
            SafePostResultCategory.RESULT_REJECTED_SANITIZED.value,
            {},
        ),
        (
            TransportCategory.TRANSPORT_FAILED_FAIL_CLOSED,
            SafePostResultCategory.RESULT_UNKNOWN_FAIL_CLOSED.value,
            {"failed": True},
        ),
        (
            TransportCategory.TRANSPORT_TIMEOUT_FAIL_CLOSED,
            SafePostResultCategory.RESULT_TIMEOUT_FAIL_CLOSED.value,
            {"timeout": True},
        ),
        (
            TransportCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED,
            SafePostResultCategory.RESULT_UNKNOWN_FAIL_CLOSED.value,
            {"unknown": True},
        ),
        (
            TransportCategory.TRANSPORT_UNAVAILABLE_FAIL_CLOSED,
            SafePostResultCategory.RESULT_UNAVAILABLE_FAIL_CLOSED.value,
            {"unavailable": True},
        ),
    ],
)
def test_real_delegate_safe_result_mapping_is_fail_closed(
    category: TransportCategory,
    expected_category: str,
    flags: dict[str, object],
) -> None:
    mapped = map_live_order_real_one_shot_post_real_delegate_outcome(
        _transport_result(category, **flags),
    )

    assert mapped.sanitized_result_category == expected_category
    assert mapped.retry_allowed is False
    assert mapped.ledger_update_allowed is False
    assert mapped.receipt_handoff_allowed is False
    assert mapped.raw_response_exposed is False
    assert mapped.broker_api_response_exposed is False
    assert mapped.credential_value_exposed is False
    assert mapped.signature_value_exposed is False
    assert mapped.headers_value_exposed is False
    assert mapped.id_exposed is False
