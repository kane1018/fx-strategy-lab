from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.live_verification.live_order_real_final_exec_stack_controlled import (
    SAFE_DRY_RUN_DECISION_LABEL,
    SAFE_DRY_RUN_LEDGER_ATTEMPT_PREVIEW_LABEL,
    SAFE_DRY_RUN_RECEIPT_HANDOFF_PREVIEW_LABEL,
    SAFE_DRY_RUN_RECONCILIATION_PREVIEW_LABEL,
    SAFE_DRY_RUN_RESULT_CATEGORY,
    SAFE_DRY_RUN_STACK_LABEL,
    LiveOrderRealFinalExecStackControlledInput,
    LiveOrderRealFinalExecStackControlledStatus,
    build_live_order_real_final_exec_stack_controlled,
    render_live_order_real_final_exec_stack_controlled_markdown,
)
from app.live_verification.live_order_real_final_readiness_controlled import (
    LiveOrderRealFinalReadinessControlledInput,
    build_live_order_real_final_readiness_controlled,
)
from app.live_verification.live_order_real_post_guard_controlled import (
    LiveOrderRealPostGuardControlledInput,
    build_live_order_real_post_guard_controlled,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    LiveOrderRealSanitizedPostResultInput,
    build_live_order_real_sanitized_post_result,
)

Status = LiveOrderRealFinalExecStackControlledStatus
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


def _input(**overrides: object) -> LiveOrderRealFinalExecStackControlledInput:
    base = LiveOrderRealFinalExecStackControlledInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_final_exec_stack_controlled(
        input_snapshot=_input(**overrides),
    )


def test_default_final_exec_stack_ready_dry_run_only_no_post() -> None:
    result = _build()

    assert result.status is Status.FINAL_EXEC_STACK_READY_DRY_RUN_ONLY
    assert result.dry_run_stack_ready is True
    assert result.final_exec_stack_mode == "FINAL_EXEC_STACK_DRY_RUN_ONLY"
    assert result.safe_dry_run_stack_label == SAFE_DRY_RUN_STACK_LABEL
    assert result.safe_dry_run_stack_status == "FINAL_EXEC_STACK_READY_DRY_RUN_ONLY"
    assert result.dry_run_mode is True
    assert result.fake_transport_used is True
    assert result.no_network_transport_used is True
    assert result.network_transport_used is False
    assert result.real_transport_used is False
    assert result.dry_run_one_shot_decision == SAFE_DRY_RUN_DECISION_LABEL
    assert result.safe_dry_run_result_category == SAFE_DRY_RUN_RESULT_CATEGORY
    assert (
        result.safe_dry_run_reconciliation_preview_label
        == SAFE_DRY_RUN_RECONCILIATION_PREVIEW_LABEL
    )
    assert (
        result.safe_dry_run_receipt_handoff_preview_label
        == SAFE_DRY_RUN_RECEIPT_HANDOFF_PREVIEW_LABEL
    )
    assert (
        result.safe_dry_run_ledger_attempt_preview_label
        == SAFE_DRY_RUN_LEDGER_ATTEMPT_PREVIEW_LABEL
    )
    assert result.api_call_executed is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.fresh_preflight_executed is False
    assert result.final_confirmation_received is False
    assert result.ledger_updated is False
    assert result.attempt_counter_persisted is False
    assert result.actual_result_receipt_received is False
    assert result.actual_receipt_handoff_executed is False
    assert result.one_shot_post_allowed is False
    assert result.one_shot_post_readiness_blocked is True
    assert result.blocked_reasons == ()


def test_safe_prerequisite_results_drive_dry_run_stack_without_values_or_raw() -> None:
    post_guard_result = build_live_order_real_post_guard_controlled()
    sanitized_result = build_live_order_real_sanitized_post_result(
        post_guard_result=post_guard_result,
    )
    final_readiness_result = build_live_order_real_final_readiness_controlled(
        post_guard_result=post_guard_result,
        sanitized_result=sanitized_result,
    )
    result = build_live_order_real_final_exec_stack_controlled(
        final_readiness_result=final_readiness_result,
        post_guard_result=post_guard_result,
        sanitized_result=sanitized_result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.FINAL_EXEC_STACK_READY_DRY_RUN_ONLY
    assert result.final_readiness_prerequisite_satisfied is True
    assert result.post_guard_prerequisite_satisfied is True
    assert result.sanitized_result_prerequisite_satisfied is True
    assert result.dry_run_stack_ready is True
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


def test_missing_final_readiness_prerequisite_fails_closed() -> None:
    final_readiness_result = build_live_order_real_final_readiness_controlled(
        input_snapshot=LiveOrderRealFinalReadinessControlledInput(
            final_readiness_declared=False,
        ),
    )
    result = build_live_order_real_final_exec_stack_controlled(
        final_readiness_result=final_readiness_result,
    )

    assert result.status is Status.FINAL_EXEC_STACK_BLOCKED_MISSING_FINAL_READINESS
    assert result.dry_run_stack_ready is False
    assert result.final_readiness_prerequisite_satisfied is False
    assert "final_readiness_prerequisite_missing" in result.blocked_reasons
    assert result.one_shot_post_allowed is False


def test_missing_post_guard_or_sanitized_prerequisites_fail_closed() -> None:
    post_guard_result = build_live_order_real_post_guard_controlled(
        input_snapshot=LiveOrderRealPostGuardControlledInput(
            post_guard_declared=False,
        ),
    )
    sanitized_result = build_live_order_real_sanitized_post_result(
        input_snapshot=LiveOrderRealSanitizedPostResultInput(
            result_contract_declared=False,
        ),
        post_guard_result=build_live_order_real_post_guard_controlled(),
    )

    post_guard_blocked = build_live_order_real_final_exec_stack_controlled(
        post_guard_result=post_guard_result,
    )
    sanitized_blocked = build_live_order_real_final_exec_stack_controlled(
        sanitized_result=sanitized_result,
    )

    assert post_guard_blocked.status is (
        Status.FINAL_EXEC_STACK_BLOCKED_MISSING_FINAL_READINESS
    )
    assert post_guard_blocked.post_guard_prerequisite_satisfied is False
    assert "post_guard_prerequisite_missing" in post_guard_blocked.blocked_reasons
    assert sanitized_blocked.status is (
        Status.FINAL_EXEC_STACK_BLOCKED_MISSING_FINAL_READINESS
    )
    assert sanitized_blocked.sanitized_result_prerequisite_satisfied is False
    assert (
        "sanitized_result_prerequisite_missing"
        in sanitized_blocked.blocked_reasons
    )


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"dry_run_stack_unknown": True}, Status.FINAL_EXEC_STACK_BLOCKED_UNKNOWN),
        ({"dry_run_stack_failed": True}, Status.FINAL_EXEC_STACK_BLOCKED_FAILED),
        (
            {"dry_run_stack_unavailable": True},
            Status.FINAL_EXEC_STACK_BLOCKED_UNAVAILABLE,
        ),
        ({"dry_run_stack_timeout": True}, Status.FINAL_EXEC_STACK_BLOCKED_TIMEOUT),
        ({"dry_run_stack_stale": True}, Status.FINAL_EXEC_STACK_BLOCKED_STALE),
        ({"dry_run_stack_reused": True}, Status.FINAL_EXEC_STACK_BLOCKED_REUSED),
    ],
)
def test_dry_run_stack_fail_closed_statuses(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.dry_run_stack_ready is False
    assert result.one_shot_post_allowed is False
    assert result.post_executed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"dry_run_mode": False},
        {"dry_run_stack_ready_input": False},
        {"fake_transport_used": False},
        {"dry_run_one_shot_decision_declared": False},
        {"dry_run_one_shot_decision_safe": False},
        {"dry_run_sanitized_result_ready": False},
        {"dry_run_reconciliation_preview_ready": False},
        {"dry_run_receipt_handoff_preview_ready": False},
        {"dry_run_ledger_attempt_preview_ready": False},
    ],
)
def test_missing_dry_run_contract_parts_are_not_ready(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.FINAL_EXEC_STACK_NOT_READY
    assert result.dry_run_stack_ready is False
    assert "dry_run_stack_contract_missing" in result.blocked_reasons
    assert result.one_shot_post_allowed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"one_shot_post_allowed": True},
            Status.FINAL_EXEC_STACK_BLOCKED_ONE_SHOT_POST_ALLOWED,
        ),
        (
            {"one_shot_post_readiness_blocked": False},
            Status.FINAL_EXEC_STACK_BLOCKED_ONE_SHOT_POST_ALLOWED,
        ),
        (
            {"network_transport_used": True},
            Status.FINAL_EXEC_STACK_BLOCKED_NETWORK_TRANSPORT,
        ),
        (
            {"no_network_transport_used": False},
            Status.FINAL_EXEC_STACK_BLOCKED_NETWORK_TRANSPORT,
        ),
        (
            {"real_transport_used": True},
            Status.FINAL_EXEC_STACK_BLOCKED_REAL_TRANSPORT,
        ),
        ({"api_call_allowed": True}, Status.FINAL_EXEC_STACK_BLOCKED_API_ATTEMPTED),
        ({"api_call_executed": True}, Status.FINAL_EXEC_STACK_BLOCKED_API_ATTEMPTED),
        ({"api_call_attempted": True}, Status.FINAL_EXEC_STACK_BLOCKED_API_ATTEMPTED),
        (
            {"post_allowed_this_step": True},
            Status.FINAL_EXEC_STACK_BLOCKED_POST_ATTEMPTED,
        ),
        ({"post_executed": True}, Status.FINAL_EXEC_STACK_BLOCKED_POST_ATTEMPTED),
        (
            {"http_post_executed": True},
            Status.FINAL_EXEC_STACK_BLOCKED_POST_ATTEMPTED,
        ),
        (
            {"order_endpoint_called": True},
            Status.FINAL_EXEC_STACK_BLOCKED_ORDER_ENDPOINT,
        ),
        (
            {"live_order_once_called": True},
            Status.FINAL_EXEC_STACK_BLOCKED_LIVE_ORDER_ONCE,
        ),
        (
            {"fresh_preflight_executed": True},
            Status.FINAL_EXEC_STACK_BLOCKED_FRESH_PREFLIGHT_EXECUTED,
        ),
        (
            {"final_confirmation_received": True},
            Status.FINAL_EXEC_STACK_BLOCKED_FINAL_CONFIRMATION_EXECUTED,
        ),
        (
            {"ledger_update_allowed": True},
            Status.FINAL_EXEC_STACK_BLOCKED_LEDGER_UPDATE,
        ),
        ({"ledger_updated": True}, Status.FINAL_EXEC_STACK_BLOCKED_LEDGER_UPDATE),
        (
            {"attempt_counter_persistence_allowed": True},
            Status.FINAL_EXEC_STACK_BLOCKED_ATTEMPT_COUNTER_PERSISTENCE,
        ),
        (
            {"attempt_counter_persisted": True},
            Status.FINAL_EXEC_STACK_BLOCKED_ATTEMPT_COUNTER_PERSISTENCE,
        ),
        (
            {"actual_result_receipt_received": True},
            Status.FINAL_EXEC_STACK_BLOCKED_ACTUAL_RECEIPT,
        ),
        (
            {"actual_receipt_handoff_executed": True},
            Status.FINAL_EXEC_STACK_BLOCKED_ACTUAL_RECEIPT,
        ),
    ],
)
def test_execution_or_real_transport_attempts_block_and_output_stays_sanitized(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.dry_run_stack_ready is False
    assert result.network_transport_used is False
    assert result.real_transport_used is False
    assert result.api_call_executed is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.fresh_preflight_executed is False
    assert result.final_confirmation_received is False
    assert result.ledger_updated is False
    assert result.attempt_counter_persisted is False
    assert result.actual_result_receipt_received is False
    assert result.actual_receipt_handoff_executed is False
    assert result.one_shot_post_allowed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"raw_request_generated": True},
            Status.FINAL_EXEC_STACK_BLOCKED_RAW_REQUEST,
        ),
        (
            {"raw_request_exposure_attempted": True},
            Status.FINAL_EXEC_STACK_BLOCKED_RAW_REQUEST,
        ),
        (
            {"raw_response_received": True},
            Status.FINAL_EXEC_STACK_BLOCKED_RAW_RESPONSE,
        ),
        (
            {"raw_response_exposure_attempted": True},
            Status.FINAL_EXEC_STACK_BLOCKED_RAW_RESPONSE,
        ),
        (
            {"broker_response_received": True},
            Status.FINAL_EXEC_STACK_BLOCKED_BROKER_API_RESPONSE,
        ),
        (
            {"api_response_received": True},
            Status.FINAL_EXEC_STACK_BLOCKED_BROKER_API_RESPONSE,
        ),
        (
            {"broker_response_exposure_attempted": True},
            Status.FINAL_EXEC_STACK_BLOCKED_BROKER_API_RESPONSE,
        ),
        (
            {"api_response_exposure_attempted": True},
            Status.FINAL_EXEC_STACK_BLOCKED_BROKER_API_RESPONSE,
        ),
        ({"account_id_exposure_attempted": True}, Status.FINAL_EXEC_STACK_BLOCKED_REAL_ID),
        ({"order_id_exposure_attempted": True}, Status.FINAL_EXEC_STACK_BLOCKED_REAL_ID),
        (
            {"transaction_id_exposure_attempted": True},
            Status.FINAL_EXEC_STACK_BLOCKED_REAL_ID,
        ),
        ({"real_id_exposure_attempted": True}, Status.FINAL_EXEC_STACK_BLOCKED_REAL_ID),
        (
            {"credential_value_exposure_attempted": True},
            Status.FINAL_EXEC_STACK_BLOCKED_VALUE_EXPOSURE,
        ),
        (
            {"signature_value_exposure_attempted": True},
            Status.FINAL_EXEC_STACK_BLOCKED_VALUE_EXPOSURE,
        ),
        (
            {"headers_value_exposure_attempted": True},
            Status.FINAL_EXEC_STACK_BLOCKED_VALUE_EXPOSURE,
        ),
        (
            {"confirmation_phrase_exposure_attempted": True},
            Status.FINAL_EXEC_STACK_BLOCKED_VALUE_EXPOSURE,
        ),
        (
            {"ledger_state_exposure_attempted": True},
            Status.FINAL_EXEC_STACK_BLOCKED_VALUE_EXPOSURE,
        ),
    ],
)
def test_raw_response_id_and_value_exposure_attempts_block_without_exposing(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)
    payload = repr(asdict(result))

    assert result.status is expected_status
    assert result.dry_run_stack_ready is False
    assert result.raw_request_generated is False
    assert result.raw_response_received is False
    assert result.broker_response_received is False
    assert result.api_response_received is False
    assert result.raw_request_stored is False
    assert result.raw_response_stored is False
    assert result.broker_response_exposed is False
    assert result.api_response_exposed is False
    assert result.real_id_exposed is False
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


def test_render_markdown_is_safe_summary_only() -> None:
    result = _build()
    rendered = render_live_order_real_final_exec_stack_controlled_markdown(result)

    assert "dry-run only one-shot execution stack contract" in rendered
    assert "dry_run_stack_ready: true" in rendered
    assert "fake_transport_used: true" in rendered
    assert "network_transport_used: false" in rendered
    assert "real_transport_used: false" in rendered
    assert "post_executed: false" in rendered
    assert "one_shot_post_allowed: false" in rendered
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
