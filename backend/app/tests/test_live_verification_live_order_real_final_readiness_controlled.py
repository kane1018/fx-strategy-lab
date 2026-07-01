from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.live_verification.live_order_real_final_readiness_controlled import (
    SAFE_FINAL_READINESS_LABEL,
    LiveOrderRealFinalReadinessControlledInput,
    LiveOrderRealFinalReadinessControlledStatus,
    build_live_order_real_final_readiness_controlled,
    render_live_order_real_final_readiness_controlled_markdown,
)
from app.live_verification.live_order_real_post_guard_controlled import (
    LiveOrderRealPostGuardControlledInput,
    build_live_order_real_post_guard_controlled,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    LiveOrderRealSanitizedPostResultInput,
    build_live_order_real_sanitized_post_result,
)

Status = LiveOrderRealFinalReadinessControlledStatus
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


def _input(**overrides: object) -> LiveOrderRealFinalReadinessControlledInput:
    base = LiveOrderRealFinalReadinessControlledInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_final_readiness_controlled(
        input_snapshot=_input(**overrides),
    )


def test_default_final_readiness_ready_no_post_or_execution() -> None:
    result = _build()

    assert result.status is Status.FINAL_READINESS_READY_NO_POST
    assert result.final_readiness_controlled_ready is True
    assert result.final_readiness_mode == (
        "FINAL_READINESS_CONTROLLED_IMPLEMENTATION_ONLY"
    )
    assert result.safe_final_readiness_label == SAFE_FINAL_READINESS_LABEL
    assert result.safe_final_readiness_status == "FINAL_READINESS_READY_NO_POST"
    assert result.blocked_reasons == ()
    assert result.fresh_preflight_required is True
    assert result.fresh_preflight_current_required is True
    assert result.fresh_preflight_non_reuse_required is True
    assert result.fresh_preflight_executed is False
    assert result.final_confirmation_required is True
    assert result.final_confirmation_current_turn_required is True
    assert result.final_confirmation_one_time_required is True
    assert result.final_confirmation_received is False
    assert result.ledger_attempt_counter_required is True
    assert result.ledger_update_allowed is False
    assert result.attempt_counter_persistence_allowed is False
    assert result.actual_receipt_handoff_required is True
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_receipt_handoff_allowed is False
    assert result.one_shot_post_readiness_blocked is True
    assert result.one_shot_post_allowed is False
    assert result.api_call_allowed is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False


def test_safe_prerequisite_results_drive_ready_without_values_or_raw_exposure() -> None:
    post_guard_result = build_live_order_real_post_guard_controlled()
    sanitized_result = build_live_order_real_sanitized_post_result(
        post_guard_result=post_guard_result,
    )
    result = build_live_order_real_final_readiness_controlled(
        post_guard_result=post_guard_result,
        sanitized_result=sanitized_result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.FINAL_READINESS_READY_NO_POST
    assert result.post_guard_prerequisite_satisfied is True
    assert result.sanitized_result_prerequisite_satisfied is True
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


def test_missing_post_guard_prerequisite_fails_closed() -> None:
    post_guard_result = build_live_order_real_post_guard_controlled(
        input_snapshot=LiveOrderRealPostGuardControlledInput(
            post_guard_declared=False,
        ),
    )
    result = build_live_order_real_final_readiness_controlled(
        post_guard_result=post_guard_result,
    )

    assert result.status is Status.FINAL_READINESS_BLOCKED_MISSING_POST_GUARD
    assert result.final_readiness_controlled_ready is False
    assert result.post_guard_prerequisite_satisfied is False
    assert "post_guard_prerequisite_missing" in result.blocked_reasons
    assert result.one_shot_post_allowed is False


def test_missing_sanitized_result_prerequisite_fails_closed() -> None:
    post_guard_result = build_live_order_real_post_guard_controlled()
    sanitized_result = build_live_order_real_sanitized_post_result(
        input_snapshot=LiveOrderRealSanitizedPostResultInput(
            result_contract_declared=False,
        ),
        post_guard_result=post_guard_result,
    )
    result = build_live_order_real_final_readiness_controlled(
        post_guard_result=post_guard_result,
        sanitized_result=sanitized_result,
    )

    assert result.status is Status.FINAL_READINESS_BLOCKED_MISSING_SANITIZED_RESULT
    assert result.final_readiness_controlled_ready is False
    assert result.sanitized_result_prerequisite_satisfied is False
    assert "sanitized_result_prerequisite_missing" in result.blocked_reasons
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"final_readiness_unknown": True}, Status.FINAL_READINESS_BLOCKED_UNKNOWN),
        ({"final_readiness_failed": True}, Status.FINAL_READINESS_BLOCKED_FAILED),
        (
            {"final_readiness_unavailable": True},
            Status.FINAL_READINESS_BLOCKED_UNAVAILABLE,
        ),
        ({"final_readiness_timeout": True}, Status.FINAL_READINESS_BLOCKED_TIMEOUT),
        ({"final_readiness_stale": True}, Status.FINAL_READINESS_BLOCKED_STALE),
        (
            {"final_readiness_previous_turn": True},
            Status.FINAL_READINESS_BLOCKED_PREVIOUS_TURN,
        ),
        ({"final_readiness_reused": True}, Status.FINAL_READINESS_BLOCKED_REUSED),
    ],
)
def test_final_readiness_fail_closed_statuses(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.final_readiness_controlled_ready is False
    assert result.one_shot_post_allowed is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"fresh_preflight_required": False},
        {"fresh_preflight_current_required": False},
        {"fresh_preflight_non_reuse_required": False},
        {"fresh_preflight_must_be_after_latest_readiness": False},
        {"fresh_preflight_failed_fail_closed": False},
        {"fresh_preflight_unknown_fail_closed": False},
        {"fresh_preflight_timeout_fail_closed": False},
        {"fresh_preflight_unavailable_fail_closed": False},
    ],
)
def test_fresh_preflight_contract_missing_blocks(overrides: dict[str, object]) -> None:
    result = _build(**overrides)

    assert result.status is Status.FINAL_READINESS_BLOCKED_FRESH_PREFLIGHT_REQUIRED
    assert result.final_readiness_controlled_ready is False
    assert "fresh_preflight_required_contract_missing" in result.blocked_reasons


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"fresh_preflight_executed": True},
            Status.FINAL_READINESS_BLOCKED_PREFLIGHT_EXECUTED,
        ),
        ({"fresh_preflight_reused": True}, Status.FINAL_READINESS_BLOCKED_REUSED),
        ({"fresh_preflight_stale": True}, Status.FINAL_READINESS_BLOCKED_STALE),
        ({"fresh_preflight_unknown": True}, Status.FINAL_READINESS_BLOCKED_UNKNOWN),
        ({"fresh_preflight_failed": True}, Status.FINAL_READINESS_BLOCKED_FAILED),
        ({"fresh_preflight_timeout": True}, Status.FINAL_READINESS_BLOCKED_TIMEOUT),
        (
            {"fresh_preflight_unavailable": True},
            Status.FINAL_READINESS_BLOCKED_UNAVAILABLE,
        ),
    ],
)
def test_fresh_preflight_attempt_or_bad_state_blocks_and_sanitizes_output(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.final_readiness_controlled_ready is False
    assert result.fresh_preflight_executed is False
    assert result.one_shot_post_allowed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"final_confirmation_required": False},
        {"final_confirmation_must_be_after_fresh_preflight": False},
        {"final_confirmation_new_required": False},
        {"final_confirmation_current_turn_required": False},
        {"final_confirmation_one_time_required": False},
        {"final_confirmation_non_reuse_required": False},
        {"previous_turn_confirmation_reuse_blocked": False},
        {"step4_approval_phrase_reuse_blocked": False},
        {"confirmation_phrase_exposure_blocked": False},
    ],
)
def test_final_confirmation_contract_missing_blocks(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is Status.FINAL_READINESS_BLOCKED_FINAL_CONFIRMATION_REQUIRED
    assert result.final_readiness_controlled_ready is False
    assert "final_confirmation_required_contract_missing" in result.blocked_reasons


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"final_confirmation_received": True},
            Status.FINAL_READINESS_BLOCKED_FINAL_CONFIRMATION_EXECUTED,
        ),
        (
            {"final_confirmation_reused": True},
            Status.FINAL_READINESS_BLOCKED_CONFIRMATION_REUSE,
        ),
        (
            {"previous_turn_confirmation_reused": True},
            Status.FINAL_READINESS_BLOCKED_CONFIRMATION_REUSE,
        ),
        (
            {"step4_approval_phrase_reused": True},
            Status.FINAL_READINESS_BLOCKED_STEP4_APPROVAL_REUSE,
        ),
        (
            {"confirmation_phrase_exposure_attempted": True},
            Status.FINAL_READINESS_BLOCKED_UNSAFE_EXPOSURE,
        ),
    ],
)
def test_final_confirmation_attempt_reuse_or_exposure_blocks(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.final_confirmation_received is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"ledger_attempt_counter_required": False},
            Status.FINAL_READINESS_BLOCKED_LEDGER_ATTEMPT_COUNTER_REQUIRED,
        ),
        (
            {"ledger_state_exposure_blocked": False},
            Status.FINAL_READINESS_BLOCKED_LEDGER_ATTEMPT_COUNTER_REQUIRED,
        ),
        (
            {"ledger_state_reuse_blocked": False},
            Status.FINAL_READINESS_BLOCKED_LEDGER_ATTEMPT_COUNTER_REQUIRED,
        ),
        (
            {"one_post_max_runtime_recheck_required": False},
            Status.FINAL_READINESS_BLOCKED_LEDGER_ATTEMPT_COUNTER_REQUIRED,
        ),
        (
            {"no_retry_runtime_recheck_required": False},
            Status.FINAL_READINESS_BLOCKED_LEDGER_ATTEMPT_COUNTER_REQUIRED,
        ),
        (
            {"ledger_update_allowed": True},
            Status.FINAL_READINESS_BLOCKED_LEDGER_UPDATE,
        ),
        (
            {"ledger_update_attempted": True},
            Status.FINAL_READINESS_BLOCKED_LEDGER_UPDATE,
        ),
        (
            {"attempt_counter_persistence_allowed": True},
            Status.FINAL_READINESS_BLOCKED_ATTEMPT_COUNTER_PERSISTENCE,
        ),
        (
            {"attempt_counter_persisted": True},
            Status.FINAL_READINESS_BLOCKED_ATTEMPT_COUNTER_PERSISTENCE,
        ),
        (
            {"ledger_state_reused": True},
            Status.FINAL_READINESS_BLOCKED_LEDGER_STATE_REUSE,
        ),
    ],
)
def test_ledger_attempt_counter_contract_blocks(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.ledger_update_allowed is False
    assert result.attempt_counter_persistence_allowed is False
    assert result.one_shot_post_allowed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"actual_receipt_handoff_required": False},
            Status.FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF_REQUIRED,
        ),
        (
            {"actual_receipt_safe_summary_required": False},
            Status.FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF_REQUIRED,
        ),
        (
            {"raw_broker_api_response_exposure_blocked": False},
            Status.FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF_REQUIRED,
        ),
        (
            {"receipt_handoff_is_not_ledger_permission": False},
            Status.FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF_REQUIRED,
        ),
        (
            {"receipt_handoff_is_not_retry_permission": False},
            Status.FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF_REQUIRED,
        ),
        (
            {"receipt_handoff_is_not_repost_permission": False},
            Status.FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF_REQUIRED,
        ),
        (
            {"actual_result_receipt_received": True},
            Status.FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF,
        ),
        (
            {"actual_receipt_handoff_executed": True},
            Status.FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF,
        ),
        (
            {"actual_receipt_handoff_allowed": True},
            Status.FINAL_READINESS_BLOCKED_ACTUAL_RECEIPT_HANDOFF,
        ),
    ],
)
def test_actual_receipt_handoff_contract_blocks(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.actual_receipt_handoff_executed is False
    assert result.actual_receipt_handoff_allowed is False
    assert result.one_shot_post_allowed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"raw_request_exposure_attempted": True},
            Status.FINAL_READINESS_BLOCKED_RAW_REQUEST_EXPOSURE,
        ),
        (
            {"raw_response_exposure_attempted": True},
            Status.FINAL_READINESS_BLOCKED_RAW_RESPONSE_EXPOSURE,
        ),
        (
            {"broker_response_exposure_attempted": True},
            Status.FINAL_READINESS_BLOCKED_BROKER_API_RESPONSE_EXPOSURE,
        ),
        (
            {"api_response_exposure_attempted": True},
            Status.FINAL_READINESS_BLOCKED_BROKER_API_RESPONSE_EXPOSURE,
        ),
        (
            {"real_id_exposure_attempted": True},
            Status.FINAL_READINESS_BLOCKED_REAL_ID_EXPOSURE,
        ),
        (
            {"credential_value_exposure_attempted": True},
            Status.FINAL_READINESS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"signature_value_exposure_attempted": True},
            Status.FINAL_READINESS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"headers_value_exposure_attempted": True},
            Status.FINAL_READINESS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"ledger_state_exposure_attempted": True},
            Status.FINAL_READINESS_BLOCKED_UNSAFE_EXPOSURE,
        ),
        (
            {"approval_command_exposure_attempted": True},
            Status.FINAL_READINESS_BLOCKED_UNSAFE_EXPOSURE,
        ),
    ],
)
def test_exposure_attempts_block_and_sanitize_output(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.final_readiness_controlled_ready is False
    assert result.raw_request_exposure_attempted is False
    assert result.raw_response_exposure_attempted is False
    assert result.credential_value_exposure_attempted is False
    assert result.signature_value_exposure_attempted is False
    assert result.headers_value_exposure_attempted is False
    assert result.ledger_state_exposure_attempted is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"api_call_allowed": True}, Status.FINAL_READINESS_BLOCKED_API_ATTEMPTED),
        ({"api_call_attempted": True}, Status.FINAL_READINESS_BLOCKED_API_ATTEMPTED),
        ({"http_client_present": True}, Status.FINAL_READINESS_BLOCKED_API_ATTEMPTED),
        (
            {"post_allowed_this_step": True},
            Status.FINAL_READINESS_BLOCKED_POST_ATTEMPTED,
        ),
        ({"post_executed": True}, Status.FINAL_READINESS_BLOCKED_POST_ATTEMPTED),
        ({"http_post_executed": True}, Status.FINAL_READINESS_BLOCKED_POST_ATTEMPTED),
        (
            {"one_shot_post_allowed": True},
            Status.FINAL_READINESS_BLOCKED_POST_ATTEMPTED,
        ),
        (
            {"one_shot_post_readiness_blocked": False},
            Status.FINAL_READINESS_BLOCKED_POST_ATTEMPTED,
        ),
        (
            {"order_endpoint_called": True},
            Status.FINAL_READINESS_BLOCKED_ORDER_ENDPOINT,
        ),
        (
            {"live_order_once_called": True},
            Status.FINAL_READINESS_BLOCKED_LIVE_ORDER_ONCE,
        ),
    ],
)
def test_api_post_order_live_order_once_attempts_block(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.api_call_allowed is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.one_shot_post_allowed is False


def test_renderer_is_safe_summary_only() -> None:
    rendered = render_live_order_real_final_readiness_controlled_markdown(_build())

    assert "FINAL_READINESS_READY_NO_POST" in rendered
    assert "final_readiness_controlled_ready: true" in rendered
    assert "fresh_preflight_executed: false" in rendered
    assert "final_confirmation_received: false" in rendered
    assert "ledger_update_allowed: false" in rendered
    assert "one_shot_post_allowed: false" in rendered
    assert CREDENTIAL_VALUE_SENTINEL not in rendered
    assert SIGNATURE_VALUE_SENTINEL not in rendered
    assert RAW_REQUEST_SENTINEL not in rendered
    assert RAW_RESPONSE_SENTINEL not in rendered
    assert REAL_ID_SENTINEL not in rendered
    assert CONFIRMATION_SENTINEL not in rendered
    assert LEDGER_SENTINEL not in rendered
