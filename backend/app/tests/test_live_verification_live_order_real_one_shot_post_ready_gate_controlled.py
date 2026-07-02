from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.live_verification.live_order_real_final_confirmation_gate_controlled import (
    LiveOrderRealFinalConfirmationGateControlledInput,
    build_live_order_real_final_confirmation_gate_controlled,
)
from app.live_verification.live_order_real_final_exec_stack_controlled import (
    LiveOrderRealFinalExecStackControlledInput,
    build_live_order_real_final_exec_stack_controlled,
)
from app.live_verification.live_order_real_final_readiness_controlled import (
    LiveOrderRealFinalReadinessControlledInput,
    build_live_order_real_final_readiness_controlled,
)
from app.live_verification.live_order_real_one_shot_post_ready_gate_controlled import (
    SAFE_ONE_SHOT_POST_READY_GATE_LABEL,
    LiveOrderRealOneShotPostReadyGateControlledInput,
    LiveOrderRealOneShotPostReadyGateControlledStatus,
    build_live_order_real_one_shot_post_ready_gate_controlled,
    render_live_order_real_one_shot_post_ready_gate_controlled_markdown,
)
from app.live_verification.live_order_real_post_guard_controlled import (
    LiveOrderRealPostGuardControlledInput,
    build_live_order_real_post_guard_controlled,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    LiveOrderRealSanitizedPostResultInput,
    build_live_order_real_sanitized_post_result,
)

Status = LiveOrderRealOneShotPostReadyGateControlledStatus
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


def _input(
    **overrides: object,
) -> LiveOrderRealOneShotPostReadyGateControlledInput:
    base = LiveOrderRealOneShotPostReadyGateControlledInput()
    return replace(base, **overrides)


def _build(**overrides: object):
    return build_live_order_real_one_shot_post_ready_gate_controlled(
        input_snapshot=_input(**overrides),
    )


def _confirmed_final_confirmation_result():
    return build_live_order_real_final_confirmation_gate_controlled(
        input_snapshot=LiveOrderRealFinalConfirmationGateControlledInput(
            final_confirmation_received=True,
            current_turn_explicit_user_reply_received=True,
            confirmation_current_turn=True,
            confirmation_new=True,
            confirmation_one_time=True,
        ),
    )


def test_default_ready_gate_passes_no_post_and_only_plans_execution_step() -> None:
    result = _build()

    assert result.status is Status.ONE_SHOT_POST_READY_GATE_PASSED_NO_POST
    assert result.ready_gate_passed is True
    assert result.one_shot_post_execution_step_may_be_planned is True
    assert result.safe_one_shot_post_ready_gate_label == (
        SAFE_ONE_SHOT_POST_READY_GATE_LABEL
    )
    assert result.fresh_preflight_passed_required is True
    assert result.fresh_preflight_passed is True
    assert result.fresh_preflight_current is True
    assert result.fresh_preflight_new is True
    assert result.fresh_preflight_reused is False
    assert result.fresh_preflight_stale is False
    assert result.final_confirmation_required is True
    assert result.final_confirmation_received is True
    assert result.confirmation_current_turn is True
    assert result.confirmation_new is True
    assert result.confirmation_one_time is True
    assert result.confirmation_reused is False
    assert result.previous_turn_confirmation_reused is False
    assert result.step4_approval_phrase_reused is False
    assert result.confirmation_actual_value_stored is False
    assert result.confirmation_actual_value_reported is False
    assert result.confirmation_actual_value_logged is False
    assert result.post_guard_ready is True
    assert result.one_post_max is True
    assert result.retry_allowed is False
    assert result.timeout_fail_closed is True
    assert result.final_readiness_ready is True
    assert result.final_exec_stack_ready is True
    assert result.sanitized_result_contract_ready is True
    assert result.ledger_update_required_after_post_only is True
    assert result.actual_receipt_handoff_required_after_post_only is True
    assert result.actual_post_permitted_now is False
    assert result.post_allowed_this_step is False
    assert result.http_post_executed is False
    assert result.order_endpoint_called is False
    assert result.live_order_once_called is False
    assert result.ledger_updated is False
    assert result.attempt_counter_persisted is False
    assert result.actual_receipt_handoff_executed is False
    assert result.blocked_reasons == ()
    assert result.recommended_next_step == (
        "one_shot_post_execution_gate_requires_new_explicit_confirmation"
    )


def test_safe_prerequisite_results_drive_ready_gate_without_raw_or_values() -> None:
    post_guard_result = build_live_order_real_post_guard_controlled()
    sanitized_result = build_live_order_real_sanitized_post_result(
        post_guard_result=post_guard_result,
    )
    final_readiness_result = build_live_order_real_final_readiness_controlled(
        post_guard_result=post_guard_result,
        sanitized_result=sanitized_result,
    )
    final_exec_stack_result = build_live_order_real_final_exec_stack_controlled(
        final_readiness_result=final_readiness_result,
        post_guard_result=post_guard_result,
        sanitized_result=sanitized_result,
    )
    result = build_live_order_real_one_shot_post_ready_gate_controlled(
        final_confirmation_result=_confirmed_final_confirmation_result(),
        post_guard_result=post_guard_result,
        final_readiness_result=final_readiness_result,
        final_exec_stack_result=final_exec_stack_result,
        sanitized_result=sanitized_result,
    )
    payload = repr(asdict(result))

    assert result.status is Status.ONE_SHOT_POST_READY_GATE_PASSED_NO_POST
    assert result.ready_gate_passed is True
    assert result.final_confirmation_received is True
    assert result.final_exec_stack_ready is True
    assert result.actual_post_permitted_now is False
    assert result.post_allowed_this_step is False
    for forbidden in (
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
    ):
        assert forbidden not in payload


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

    assert result.status is (
        Status.ONE_SHOT_POST_READY_GATE_BLOCKED_MISSING_FRESH_PREFLIGHT
    )
    assert result.ready_gate_passed is False
    assert result.one_shot_post_execution_step_may_be_planned is False
    assert result.post_allowed_this_step is False
    assert "fresh_preflight_pass_current_new_non_reused_missing" in (
        result.blocked_reasons
    )


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"fresh_preflight_unknown": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_UNKNOWN,
        ),
        (
            {"fresh_preflight_failed": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_FAILED,
        ),
        (
            {"fresh_preflight_timeout": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_TIMEOUT,
        ),
        (
            {"fresh_preflight_unavailable": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_UNAVAILABLE,
        ),
        (
            {"fresh_preflight_stale": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_STALE,
        ),
    ],
)
def test_fresh_preflight_bad_states_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.ready_gate_passed is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"final_confirmation_received": False},
        {"confirmation_current_turn": False},
        {"confirmation_new": False},
        {"confirmation_one_time": False},
    ],
)
def test_final_confirmation_current_new_one_time_required(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is (
        Status.ONE_SHOT_POST_READY_GATE_BLOCKED_MISSING_FINAL_CONFIRMATION
    )
    assert result.ready_gate_passed is False
    assert "final_confirmation_current_new_one_time_missing" in (
        result.blocked_reasons
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"confirmation_reused": True},
        {"previous_turn_confirmation_reused": True},
        {"step4_approval_phrase_reused": True},
    ],
)
def test_confirmation_reuse_blocks_ready_gate(
    overrides: dict[str, object],
) -> None:
    result = _build(**overrides)

    assert result.status is (
        Status.ONE_SHOT_POST_READY_GATE_BLOCKED_CONFIRMATION_REUSED
    )
    assert result.ready_gate_passed is False
    assert result.post_allowed_this_step is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"post_guard_ready": False},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_POST_GUARD_NOT_READY,
        ),
        (
            {"one_post_max": False},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_POST_GUARD_NOT_READY,
        ),
        (
            {"retry_allowed": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_POST_GUARD_NOT_READY,
        ),
        (
            {"timeout_fail_closed": False},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_POST_GUARD_NOT_READY,
        ),
        (
            {"final_readiness_ready": False},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_FINAL_READINESS_NOT_READY,
        ),
        (
            {"final_exec_stack_ready": False},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_FINAL_EXEC_STACK_NOT_READY,
        ),
        (
            {"sanitized_result_contract_ready": False},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_SANITIZED_RESULT_NOT_READY,
        ),
    ],
)
def test_ready_contract_prerequisites_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.ready_gate_passed is False
    assert result.actual_post_permitted_now is False


def test_blocked_safe_prerequisite_results_fail_closed() -> None:
    post_guard_result = build_live_order_real_post_guard_controlled(
        input_snapshot=LiveOrderRealPostGuardControlledInput(
            post_guard_declared=False,
        ),
    )
    sanitized_result = build_live_order_real_sanitized_post_result(
        input_snapshot=LiveOrderRealSanitizedPostResultInput(
            result_contract_declared=False,
        ),
    )
    final_readiness_result = build_live_order_real_final_readiness_controlled(
        input_snapshot=LiveOrderRealFinalReadinessControlledInput(
            final_readiness_declared=False,
        ),
    )
    final_exec_stack_result = build_live_order_real_final_exec_stack_controlled(
        input_snapshot=LiveOrderRealFinalExecStackControlledInput(
            final_exec_stack_declared=False,
        ),
    )

    assert (
        build_live_order_real_one_shot_post_ready_gate_controlled(
            post_guard_result=post_guard_result,
        ).status
        is Status.ONE_SHOT_POST_READY_GATE_BLOCKED_POST_GUARD_NOT_READY
    )
    assert (
        build_live_order_real_one_shot_post_ready_gate_controlled(
            sanitized_result=sanitized_result,
        ).status
        is Status.ONE_SHOT_POST_READY_GATE_BLOCKED_SANITIZED_RESULT_NOT_READY
    )
    assert (
        build_live_order_real_one_shot_post_ready_gate_controlled(
            final_readiness_result=final_readiness_result,
        ).status
        is Status.ONE_SHOT_POST_READY_GATE_BLOCKED_FINAL_READINESS_NOT_READY
    )
    assert (
        build_live_order_real_one_shot_post_ready_gate_controlled(
            final_exec_stack_result=final_exec_stack_result,
        ).status
        is Status.ONE_SHOT_POST_READY_GATE_BLOCKED_FINAL_EXEC_STACK_NOT_READY
    )


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"actual_post_permitted_now": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_POST_ATTEMPTED,
        ),
        (
            {"post_allowed_this_step": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_POST_ATTEMPTED,
        ),
        (
            {"http_post_executed": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_POST_ATTEMPTED,
        ),
        (
            {"order_endpoint_called": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_ORDER_ENDPOINT,
        ),
        (
            {"live_order_once_called": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_LIVE_ORDER_ONCE,
        ),
        (
            {"ledger_updated": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_LEDGER_UPDATE,
        ),
        (
            {"attempt_counter_persisted": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_LEDGER_UPDATE,
        ),
        (
            {"actual_receipt_handoff_executed": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_RECEIPT_HANDOFF,
        ),
        (
            {"raw_request_exposed": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_RAW_EXPOSURE,
        ),
        (
            {"broker_api_response_exposed": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_RAW_EXPOSURE,
        ),
        (
            {"real_id_exposed": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_ID_EXPOSURE,
        ),
        (
            {"credential_value_exposed": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_VALUE_EXPOSURE,
        ),
        (
            {"confirmation_actual_value_reported": True},
            Status.ONE_SHOT_POST_READY_GATE_BLOCKED_MISSING_FINAL_CONFIRMATION,
        ),
    ],
)
def test_forbidden_execution_and_exposure_flags_fail_closed(
    overrides: dict[str, object],
    expected_status: Status,
) -> None:
    result = _build(**overrides)

    assert result.status is expected_status
    assert result.ready_gate_passed is False
    assert result.one_shot_post_execution_step_may_be_planned is False


def test_renderer_is_safe_summary_only() -> None:
    markdown = render_live_order_real_one_shot_post_ready_gate_controlled_markdown(
        _build(),
    )

    assert "ONE_SHOT_POST_READY_GATE_PASSED_NO_POST" in markdown
    assert "Ready gate passed does not permit POST in this step." in markdown
    for forbidden in (
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
    ):
        assert forbidden not in markdown
