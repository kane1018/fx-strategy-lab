from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.live_verification.live_order_real_final_confirmation_gate_controlled import (
    SAFE_FINAL_CONFIRMATION_GATE_LABEL,
    LiveOrderRealFinalConfirmationGateControlledInput,
    LiveOrderRealFinalConfirmationGateControlledStatus,
    build_live_order_real_final_confirmation_gate_controlled,
    render_live_order_real_final_confirmation_gate_controlled_markdown,
)

Status = LiveOrderRealFinalConfirmationGateControlledStatus
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
) -> LiveOrderRealFinalConfirmationGateControlledInput:
    base = LiveOrderRealFinalConfirmationGateControlledInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_final_confirmation_gate_controlled(
        input_snapshot=_input(**overrides),
    )


def test_default_gate_ready_for_current_turn_request_without_confirmation() -> None:
    result = _build()

    assert result.status is Status.FINAL_CONFIRMATION_GATE_READY_FOR_REQUEST_NO_POST
    assert result.final_confirmation_gate_ready is True
    assert result.final_confirmation_gate_confirmed is False
    assert result.safe_final_confirmation_gate_label == SAFE_FINAL_CONFIRMATION_GATE_LABEL
    assert result.fresh_preflight_pass_required is True
    assert result.fresh_preflight_passed is True
    assert result.fresh_preflight_current is True
    assert result.fresh_preflight_new is True
    assert result.fresh_preflight_reused is False
    assert result.fresh_preflight_stale is False
    assert result.final_confirmation_required is True
    assert result.final_confirmation_received is False
    assert result.current_turn_explicit_user_reply_received is False
    assert result.confirmation_current_turn is False
    assert result.confirmation_new is False
    assert result.confirmation_one_time is False
    assert result.confirmation_reused is False
    assert result.previous_turn_confirmation_reused is False
    assert result.step4_approval_phrase_reused is False
    assert result.confirmation_actual_value_stored is False
    assert result.confirmation_actual_value_reported is False
    assert result.confirmation_actual_value_logged is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.ledger_updated is False
    assert result.attempt_counter_persisted is False
    assert result.actual_receipt_handoff_executed is False
    assert result.blocked_reasons == ()


def test_current_turn_confirmation_marks_confirmed_without_post_permission() -> None:
    result = _build(
        final_confirmation_received=True,
        current_turn_explicit_user_reply_received=True,
        confirmation_current_turn=True,
        confirmation_new=True,
        confirmation_one_time=True,
    )

    assert result.status is Status.FINAL_CONFIRMATION_GATE_CONFIRMED_NO_POST
    assert result.final_confirmation_gate_ready is True
    assert result.final_confirmation_gate_confirmed is True
    assert result.final_confirmation_received is True
    assert result.current_turn_explicit_user_reply_received is True
    assert result.confirmation_current_turn is True
    assert result.confirmation_new is True
    assert result.confirmation_one_time is True
    assert result.confirmation_reused is False
    assert result.previous_turn_confirmation_reused is False
    assert result.step4_approval_phrase_reused is False
    assert result.confirmation_actual_value_stored is False
    assert result.confirmation_actual_value_reported is False
    assert result.confirmation_actual_value_logged is False
    assert result.post_allowed_this_step is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False
    assert result.recommended_next_step == "one_shot_post_ready_gate_no_post"


@pytest.mark.parametrize(
    "overrides",
    [
        {"fresh_preflight_passed": False},
        {"fresh_preflight_current": False},
        {"fresh_preflight_new": False},
        {"fresh_preflight_reused": True},
    ],
)
def test_fresh_preflight_pass_current_new_non_reused_required(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert (
        result.status
        is Status.FINAL_CONFIRMATION_GATE_BLOCKED_MISSING_FRESH_PREFLIGHT_PASS
    )
    assert result.final_confirmation_gate_ready is False
    assert result.post_allowed_this_step is False
    assert "fresh_preflight_pass_current_new_non_reused_missing" in (
        result.blocked_reasons
    )


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"fresh_preflight_unknown": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_UNKNOWN,
        ),
        (
            {"fresh_preflight_timeout": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_TIMEOUT,
        ),
        (
            {"fresh_preflight_unavailable": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_UNAVAILABLE,
        ),
        (
            {"fresh_preflight_stale": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_STALE,
        ),
    ],
)
def test_fresh_preflight_bad_states_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.final_confirmation_gate_ready is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    ("overrides", "expected_status", "expected_reason"),
    [
        (
            {
                "final_confirmation_received": True,
                "current_turn_explicit_user_reply_received": False,
            },
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_CURRENT_TURN,
            "current_turn_explicit_user_reply_missing",
        ),
        (
            {
                "final_confirmation_received": True,
                "current_turn_explicit_user_reply_received": True,
                "confirmation_current_turn": False,
            },
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_CURRENT_TURN,
            "confirmation_not_current_turn",
        ),
        (
            {
                "final_confirmation_received": True,
                "current_turn_explicit_user_reply_received": True,
                "confirmation_current_turn": True,
                "confirmation_new": False,
            },
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_NEW,
            "confirmation_not_new",
        ),
        (
            {
                "final_confirmation_received": True,
                "current_turn_explicit_user_reply_received": True,
                "confirmation_current_turn": True,
                "confirmation_new": True,
                "confirmation_one_time": False,
            },
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_NOT_ONE_TIME,
            "confirmation_not_one_time",
        ),
    ],
)
def test_confirmation_must_be_current_turn_new_and_one_time(
    overrides: dict[str, object],
    expected_status: Status,
    expected_reason: str,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.final_confirmation_gate_confirmed is False
    assert expected_reason in result.blocked_reasons
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"confirmation_reused": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_REUSED,
        ),
        (
            {"previous_turn_confirmation_reused": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_PREVIOUS_TURN_CONFIRMATION,
        ),
        (
            {"step4_approval_phrase_reused": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_STEP4_APPROVAL_REUSE,
        ),
        (
            {"prompt_used_as_confirmation": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_VALUE_EXPOSURE,
        ),
        (
            {"fresh_preflight_pass_report_used_as_confirmation": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_VALUE_EXPOSURE,
        ),
        (
            {"confirmation_actual_value_stored": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_VALUE_EXPOSURE,
        ),
        (
            {"confirmation_actual_value_reported": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_VALUE_EXPOSURE,
        ),
        (
            {"confirmation_actual_value_logged": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_VALUE_EXPOSURE,
        ),
        (
            {"confirmation_phrase_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_CONFIRMATION_VALUE_EXPOSURE,
        ),
    ],
)
def test_confirmation_reuse_or_value_exposure_fails_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.final_confirmation_gate_confirmed is False
    assert result.final_confirmation_received is False
    assert result.confirmation_actual_value_stored is False
    assert result.confirmation_actual_value_reported is False
    assert result.confirmation_actual_value_logged is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"post_allowed_this_step": True}, Status.FINAL_CONFIRMATION_GATE_BLOCKED_POST_ATTEMPTED),
        ({"post_executed": True}, Status.FINAL_CONFIRMATION_GATE_BLOCKED_POST_ATTEMPTED),
        ({"http_post_executed": True}, Status.FINAL_CONFIRMATION_GATE_BLOCKED_POST_ATTEMPTED),
        (
            {"order_endpoint_called": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_ORDER_ENDPOINT,
        ),
        (
            {"live_order_once_called": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_LIVE_ORDER_ONCE,
        ),
        (
            {"ledger_update_allowed": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_LEDGER_UPDATE,
        ),
        ({"ledger_updated": True}, Status.FINAL_CONFIRMATION_GATE_BLOCKED_LEDGER_UPDATE),
        (
            {"attempt_counter_persisted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_LEDGER_UPDATE,
        ),
        (
            {"actual_result_receipt_received": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_ACTUAL_RECEIPT,
        ),
        (
            {"actual_receipt_handoff_executed": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_ACTUAL_RECEIPT,
        ),
    ],
)
def test_post_ledger_receipt_paths_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.ledger_updated is False
    assert result.actual_receipt_handoff_executed is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"raw_request_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_RAW_EXPOSURE,
        ),
        (
            {"raw_response_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_RAW_EXPOSURE,
        ),
        (
            {"broker_response_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_RAW_EXPOSURE,
        ),
        (
            {"api_response_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_RAW_EXPOSURE,
        ),
        (
            {"account_id_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_ID_EXPOSURE,
        ),
        (
            {"order_id_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_ID_EXPOSURE,
        ),
        (
            {"real_id_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_ID_EXPOSURE,
        ),
        (
            {"credential_value_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_VALUE_EXPOSURE,
        ),
        (
            {"signature_value_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_VALUE_EXPOSURE,
        ),
        (
            {"headers_value_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_VALUE_EXPOSURE,
        ),
        (
            {"ledger_state_exposure_attempted": True},
            Status.FINAL_CONFIRMATION_GATE_BLOCKED_VALUE_EXPOSURE,
        ),
    ],
)
def test_raw_id_value_exposure_fails_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.final_confirmation_gate_ready is False


def test_renderer_and_asdict_do_not_include_actual_value_sentinels() -> None:
    result = _build(
        safe_final_confirmation_gate_label=CONFIRMATION_SENTINEL,
    )
    rendered = render_live_order_real_final_confirmation_gate_controlled_markdown(
        result,
    )
    payload = repr(asdict(result))

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
        assert forbidden not in payload
    assert "post_allowed_this_step: false" in rendered
    assert "final_confirmation_received: false" in rendered
