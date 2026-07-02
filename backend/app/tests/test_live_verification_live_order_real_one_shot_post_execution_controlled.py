from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.live_verification.live_order_real_one_shot_post_execution_controlled import (
    SAFE_EXECUTABLE_ORDER_PREVIEW_LABEL,
    SAFE_ONE_SHOT_POST_EXECUTION_LABEL,
    SAFE_POST_SPECIFIC_CONFIRMATION_LABEL,
    LiveOrderRealExecutableOrderPreviewInput,
    LiveOrderRealOneShotPostExecutionControlledInput,
    LiveOrderRealOneShotPostExecutionControlledStatus,
    LiveOrderRealOneShotPostTransportInput,
    LiveOrderRealOneShotPostTransportResult,
    LiveOrderRealOneShotPostTransportResultCategory,
    LiveOrderRealPostSpecificConfirmationInput,
    LiveOrderRealPostSpecificConfirmationStatus,
    build_live_order_real_executable_order_preview,
    build_live_order_real_one_shot_post_execution_controlled,
    execute_live_order_real_one_shot_post_execution_controlled,
    render_live_order_real_one_shot_post_execution_controlled_markdown,
    validate_live_order_real_post_specific_confirmation,
)

Status = LiveOrderRealOneShotPostExecutionControlledStatus
TransportCategory = LiveOrderRealOneShotPostTransportResultCategory
ConfirmationStatus = LiveOrderRealPostSpecificConfirmationStatus

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


def _confirmed():
    return validate_live_order_real_post_specific_confirmation(
        LiveOrderRealPostSpecificConfirmationInput(
            post_specific_confirmation_received=True,
            post_specific_confirmation_current_turn=True,
            post_specific_confirmation_new=True,
            post_specific_confirmation_one_time=True,
        ),
    )


def _transport_result(
    category: TransportCategory = TransportCategory.TRANSPORT_ACCEPTED_SANITIZED,
    **overrides: object,
) -> LiveOrderRealOneShotPostTransportResult:
    return LiveOrderRealOneShotPostTransportResult(
        result_category=category,
        **overrides,
    )


def test_preview_is_safe_summary_only() -> None:
    preview = build_live_order_real_executable_order_preview()
    payload = repr(asdict(preview))

    assert preview.sanitized_order_preview_available is True
    assert preview.order_ambiguity is False
    assert preview.safe_preview_label == SAFE_EXECUTABLE_ORDER_PREVIEW_LABEL
    assert preview.fresh_preflight_passed is True
    assert preview.final_confirmation_received is True
    assert preview.ready_gate_passed is True
    assert preview.one_post_max is True
    assert preview.retry_allowed is False
    assert preview.timeout_fail_closed is True
    assert preview.ledger_update_this_step is False
    assert preview.receipt_handoff_this_step is False
    assert preview.raw_exposure is False
    assert preview.id_exposure is False
    assert preview.credential_value_exposure is False
    assert preview.codex_inferred_symbol is False
    assert preview.codex_inferred_side is False
    assert preview.codex_inferred_size is False
    assert preview.codex_inferred_order_type is False
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload


def test_preview_blocks_when_order_candidate_is_missing() -> None:
    preview = build_live_order_real_executable_order_preview(
        replace(
            LiveOrderRealExecutableOrderPreviewInput(),
            safe_order_candidate_available=False,
        ),
    )

    assert preview.sanitized_order_preview_available is False
    assert preview.order_ambiguity is True
    assert "safe_order_candidate_missing" in preview.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"order_ambiguity": True}, "order_ambiguity"),
        ({"symbol": "EUR_JPY"}, "symbol_not_supported"),
        ({"side": "SELL"}, "side_not_repo_defined_buy"),
        ({"size": 101}, "size_not_repo_defined"),
        ({"order_type": "LIMIT"}, "order_type_not_repo_defined_market"),
        ({"codex_inferred_side": True}, "codex_inferred_side_unsafe"),
    ],
)
def test_preview_blocks_when_order_ambiguity_exists(
    override: dict[str, object],
    reason: str,
) -> None:
    preview = build_live_order_real_executable_order_preview(
        replace(LiveOrderRealExecutableOrderPreviewInput(), **override),
    )

    assert preview.sanitized_order_preview_available is False
    assert preview.order_ambiguity is True
    assert reason in preview.blocked_reasons


def test_post_specific_confirmation_is_required_by_default() -> None:
    confirmation = validate_live_order_real_post_specific_confirmation()

    assert confirmation.status is (
        ConfirmationStatus.POST_SPECIFIC_CONFIRMATION_REQUIRED_NOT_RECEIVED
    )
    assert confirmation.post_specific_confirmation_adapter_ready is True
    assert confirmation.post_specific_confirmation_validated is False
    assert confirmation.safe_confirmation_label == SAFE_POST_SPECIFIC_CONFIRMATION_LABEL
    assert confirmation.post_confirmation_actual_value_stored is False
    assert confirmation.post_confirmation_actual_value_reported is False
    assert confirmation.post_confirmation_actual_value_logged is False


def test_post_specific_confirmation_validates_safe_booleans_only() -> None:
    confirmation = _confirmed()

    assert confirmation.status is (
        ConfirmationStatus.POST_SPECIFIC_CONFIRMATION_VALIDATED_SAFE_SUMMARY
    )
    assert confirmation.post_specific_confirmation_validated is True
    assert confirmation.post_specific_confirmation_received is True
    assert confirmation.post_specific_confirmation_current_turn is True
    assert confirmation.post_specific_confirmation_new is True
    assert confirmation.post_specific_confirmation_one_time is True
    assert confirmation.post_specific_confirmation_reused is False


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        (
            {"final_confirmation_reused_as_post_confirmation": True},
            "final_confirmation_reused_as_post_confirmation",
        ),
        (
            {"ready_gate_confirmation_reused_as_post_confirmation": True},
            "ready_gate_confirmation_reused_as_post_confirmation",
        ),
        (
            {"previous_turn_confirmation_reused": True},
            "previous_turn_confirmation_reused",
        ),
        ({"step4_approval_phrase_reused": True}, "step4_approval_phrase_reused"),
        (
            {"post_specific_confirmation_reused": True},
            "post_specific_confirmation_reused",
        ),
    ],
)
def test_confirmation_reuse_is_rejected(
    override: dict[str, object],
    reason: str,
) -> None:
    values = {
        "post_specific_confirmation_received": True,
        "post_specific_confirmation_current_turn": True,
        "post_specific_confirmation_new": True,
        "post_specific_confirmation_one_time": True,
    }
    values.update(override)
    confirmation = validate_live_order_real_post_specific_confirmation(
        LiveOrderRealPostSpecificConfirmationInput(**values),
    )

    assert confirmation.status is ConfirmationStatus.POST_SPECIFIC_CONFIRMATION_BLOCKED_REUSED
    assert confirmation.post_specific_confirmation_validated is False
    assert reason in confirmation.blocked_reasons


def test_route_builds_without_actual_post_and_awaits_confirmation() -> None:
    result = build_live_order_real_one_shot_post_execution_controlled()

    assert result.status is Status.ONE_SHOT_POST_EXECUTION_ROUTE_READY_NO_POST
    assert result.safe_post_execution_route_available is True
    assert result.safe_post_execution_label == SAFE_ONE_SHOT_POST_EXECUTION_LABEL
    assert result.sanitized_order_preview_available is True
    assert result.post_specific_confirmation_adapter_ready is True
    assert result.post_specific_confirmation_received is False
    assert result.post_attempted is False
    assert result.http_post_executed is False
    assert result.actual_http_post_executed is False
    assert result.post_execution_count == 0
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False


def test_executor_does_not_run_without_post_specific_confirmation() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_transport(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result()

    result = execute_live_order_real_one_shot_post_execution_controlled(
        transport=fake_transport,
    )

    assert calls == []
    assert result.status is (
        Status.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_POST_SPECIFIC_CONFIRMATION
    )
    assert result.post_attempted is False
    assert result.post_execution_count == 0


def test_executor_does_not_run_without_sanitized_preview() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []
    preview = build_live_order_real_executable_order_preview(
        replace(
            LiveOrderRealExecutableOrderPreviewInput(),
            safe_order_candidate_available=False,
        ),
    )

    def fake_transport(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result()

    result = execute_live_order_real_one_shot_post_execution_controlled(
        transport=fake_transport,
        preview=preview,
        confirmation=_confirmed(),
    )

    assert calls == []
    assert result.status is Status.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_SANITIZED_PREVIEW
    assert result.post_attempted is False


def test_executor_does_not_run_when_order_ambiguous() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []
    preview = build_live_order_real_executable_order_preview(
        replace(LiveOrderRealExecutableOrderPreviewInput(), order_ambiguity=True),
    )

    def fake_transport(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result()

    result = execute_live_order_real_one_shot_post_execution_controlled(
        transport=fake_transport,
        preview=preview,
        confirmation=_confirmed(),
    )

    assert calls == []
    assert result.status is Status.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_SANITIZED_PREVIEW
    assert result.post_attempted is False


@pytest.mark.parametrize(
    "override",
    [
        {"fresh_preflight_passed": False},
        {"final_confirmation_received": False},
        {"ready_gate_passed": False},
        {"post_guard_ready": False},
        {"retry_allowed": True},
        {"timeout_fail_closed": False},
    ],
)
def test_executor_does_not_run_when_prerequisite_gate_missing(
    override: dict[str, object],
) -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_transport(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result()

    result = execute_live_order_real_one_shot_post_execution_controlled(
        transport=fake_transport,
        input_snapshot=replace(
            LiveOrderRealOneShotPostExecutionControlledInput(),
            **override,
        ),
        confirmation=_confirmed(),
    )

    assert calls == []
    assert result.status in {
        Status.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_PREREQUISITE,
        Status.ONE_SHOT_POST_EXECUTION_BLOCKED_MISSING_SANITIZED_PREVIEW,
    }
    assert result.post_execution_count == 0


def test_executor_calls_fake_transport_exactly_once_when_all_conditions_true() -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_transport(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result()

    result = execute_live_order_real_one_shot_post_execution_controlled(
        transport=fake_transport,
        confirmation=_confirmed(),
    )

    assert len(calls) == 1
    assert result.status is (
        Status.ONE_SHOT_POST_EXECUTION_TRANSPORT_COMPLETED_SAFE_SUMMARY
    )
    assert result.post_attempted is True
    assert result.post_execution_count == 1
    assert result.fake_transport_used is True
    assert result.http_post_executed is False
    assert result.actual_http_post_executed is False
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False


@pytest.mark.parametrize(
    ("category", "expected_status"),
    [
        (
            TransportCategory.TRANSPORT_FAILED_FAIL_CLOSED,
            Status.ONE_SHOT_POST_EXECUTION_BLOCKED_FAILED_FAIL_CLOSED,
        ),
        (
            TransportCategory.TRANSPORT_TIMEOUT_FAIL_CLOSED,
            Status.ONE_SHOT_POST_EXECUTION_BLOCKED_TIMEOUT_FAIL_CLOSED,
        ),
        (
            TransportCategory.TRANSPORT_UNKNOWN_FAIL_CLOSED,
            Status.ONE_SHOT_POST_EXECUTION_BLOCKED_UNKNOWN_FAIL_CLOSED,
        ),
        (
            TransportCategory.TRANSPORT_UNAVAILABLE_FAIL_CLOSED,
            Status.ONE_SHOT_POST_EXECUTION_BLOCKED_UNAVAILABLE_FAIL_CLOSED,
        ),
    ],
)
def test_executor_does_not_retry_failure_timeout_unknown_or_unavailable(
    category: TransportCategory,
    expected_status: Status,
) -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_transport(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result(category)

    result = execute_live_order_real_one_shot_post_execution_controlled(
        transport=fake_transport,
        confirmation=_confirmed(),
    )

    assert len(calls) == 1
    assert result.status is expected_status
    assert result.post_execution_count == 1
    assert result.retry_attempted is False
    assert result.second_post_attempted is False


@pytest.mark.parametrize(
    ("override", "expected_status"),
    [
        (
            {"retry_attempted": True},
            Status.ONE_SHOT_POST_EXECUTION_BLOCKED_RETRY_OR_SECOND_POST,
        ),
        (
            {"second_post_attempted": True},
            Status.ONE_SHOT_POST_EXECUTION_BLOCKED_RETRY_OR_SECOND_POST,
        ),
        (
            {"ledger_updated": True},
            Status.ONE_SHOT_POST_EXECUTION_BLOCKED_LEDGER_OR_RECEIPT,
        ),
        (
            {"actual_receipt_handoff_executed": True},
            Status.ONE_SHOT_POST_EXECUTION_BLOCKED_LEDGER_OR_RECEIPT,
        ),
        (
            {"raw_response_exposed": True},
            Status.ONE_SHOT_POST_EXECUTION_BLOCKED_RAW_EXPOSURE,
        ),
        (
            {"credential_value_exposed": True},
            Status.ONE_SHOT_POST_EXECUTION_BLOCKED_VALUE_EXPOSURE,
        ),
        (
            {"order_id_exposed": True},
            Status.ONE_SHOT_POST_EXECUTION_BLOCKED_ID_EXPOSURE,
        ),
    ],
)
def test_transport_unsafe_result_blocks_and_sanitizes_public_booleans(
    override: dict[str, object],
    expected_status: Status,
) -> None:
    calls: list[LiveOrderRealOneShotPostTransportInput] = []

    def fake_transport(input_snapshot: LiveOrderRealOneShotPostTransportInput):
        calls.append(input_snapshot)
        return _transport_result(**override)

    result = execute_live_order_real_one_shot_post_execution_controlled(
        transport=fake_transport,
        confirmation=_confirmed(),
    )

    assert len(calls) == 1
    assert result.status is expected_status
    assert result.retry_attempted is False
    assert result.second_post_attempted is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False
    assert result.raw_request_exposed is False
    assert result.raw_response_exposed is False
    assert result.credential_value_exposed is False
    assert result.order_id_exposed is False


def test_renderer_and_payload_do_not_surface_raw_id_or_value_sentinels() -> None:
    result = execute_live_order_real_one_shot_post_execution_controlled(
        transport=lambda _: _transport_result(),
        confirmation=_confirmed(),
    )
    rendered = render_live_order_real_one_shot_post_execution_controlled_markdown(
        result,
    )
    payload = repr(asdict(result))

    assert "http_post_executed: false" in rendered
    assert "ledger_updated: false" in rendered
    assert "actual_receipt_handoff_executed: false" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in rendered
        assert forbidden not in payload


def test_default_import_builder_and_preview_do_not_post() -> None:
    preview = build_live_order_real_executable_order_preview()
    route = build_live_order_real_one_shot_post_execution_controlled(preview=preview)

    assert preview.sanitized_order_preview_available is True
    assert route.post_attempted is False
    assert route.http_post_executed is False
    assert route.post_execution_count == 0
    assert route.live_order_once_executed is False
    assert route.order_endpoint_executed is False


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
