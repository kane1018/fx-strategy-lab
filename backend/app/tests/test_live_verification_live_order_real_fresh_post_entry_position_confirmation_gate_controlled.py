from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification.live_order_real_fresh_post_entry_position_confirmation_gate_controlled import (  # noqa: E501
    FRESH_ENTRY_SAFE_STATUS_ACCEPTED,
    NEXT_STEP_FRESH_ACCEPTED_NO_POSITION_SAFE_STOP,
    NEXT_STEP_FRESH_POSITION_OPEN_SAFE_HANDOFF,
    NEXT_STEP_FRESH_POST_ENTRY_UNKNOWN_SAFE_STOP,
    NEXT_STEP_MANUAL_POSITION_RISK_CHECK,
    FreshEntryPostSafeSummaryInput,
    FreshPostEntryPositionConfirmationGateCase,
    FreshPostEntryPositionConfirmationGateInput,
    FreshPostEntryPositionConfirmationStatus,
    build_fresh_post_entry_position_confirmation_gate_controlled,
    render_fresh_post_entry_position_confirmation_gate_markdown,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_position_runtime_safe_read_controlled import (
    PositionRuntimeSafeReadControlledInput,
    build_position_runtime_safe_read_controlled,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    SafePostResultCategory,
    SafeReconciliationStatus,
)


def _runtime_input(**overrides: object) -> PositionRuntimeSafeReadControlledInput:
    defaults: dict[str, object] = {
        "credential_presence_checked": True,
        "credential_presence_available": True,
        "all_required_credentials_present": True,
        "runtime_read_executed": True,
        "runtime_read_succeeded": True,
        "position_count_safe": 1,
    }
    defaults.update(overrides)
    return PositionRuntimeSafeReadControlledInput(**defaults)


def _runtime(**overrides: object):
    return build_position_runtime_safe_read_controlled(_runtime_input(**overrides))


def test_fresh_accepted_one_position_confirms_entry_effect_open_safe() -> None:
    result = build_fresh_post_entry_position_confirmation_gate_controlled(
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.case is FreshPostEntryPositionConfirmationGateCase.CASE_1
    assert (
        result.fresh_position_confirmation_status
        is FreshPostEntryPositionConfirmationStatus
        .FRESH_ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE
    )
    assert result.fresh_entry_http_post_executed is True
    assert result.fresh_entry_post_execution_count == 1
    assert (
        result.fresh_entry_sanitized_result_category
        == SafePostResultCategory.RESULT_ACCEPTED_SANITIZED.value
    )
    assert result.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert result.position_count_safe == 1
    assert result.fresh_entry_effect_confirmed_by_position is True
    assert result.next_cycle_state == "FRESH_POSITION_OPEN_SAFE"
    assert result.close_planning_allowed is True
    assert result.close_execution_gate_may_be_planned is True
    assert result.close_execution_allowed_now is False
    assert result.close_post_allowed_now is False
    assert result.recommended_next_step == NEXT_STEP_FRESH_POSITION_OPEN_SAFE_HANDOFF


def test_fresh_accepted_no_position_safe_stops_without_retry() -> None:
    result = build_fresh_post_entry_position_confirmation_gate_controlled(
        runtime_result=_runtime(position_count_safe=0),
    )

    assert result.case is FreshPostEntryPositionConfirmationGateCase.CASE_2
    assert (
        result.fresh_position_confirmation_status
        is FreshPostEntryPositionConfirmationStatus
        .FRESH_ACCEPTED_BUT_NO_POSITION_VISIBLE_SAFE_STOP
    )
    assert result.position_status is PositionReadOnlyControlledStatus.NO_POSITION
    assert result.position_count_safe == 0
    assert result.fresh_entry_effect_confirmed_by_position is False
    assert result.next_cycle_state == "FRESH_ACCEPTED_NO_POSITION_SAFE_STOP"
    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_entry_allowed is False
    assert result.close_post_allowed_now is False
    assert result.recommended_next_step == NEXT_STEP_FRESH_ACCEPTED_NO_POSITION_SAFE_STOP


def test_fresh_accepted_multiple_positions_requires_manual_risk_check() -> None:
    result = build_fresh_post_entry_position_confirmation_gate_controlled(
        runtime_result=_runtime(position_count_safe=2),
    )

    assert result.case is FreshPostEntryPositionConfirmationGateCase.CASE_3
    assert (
        result.fresh_position_confirmation_status
        is FreshPostEntryPositionConfirmationStatus.FRESH_MULTIPLE_POSITIONS_BLOCKED
    )
    assert result.position_status is (
        PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    )
    assert result.has_multiple_positions is True
    assert result.close_planning_allowed is False
    assert result.close_execution_allowed_now is False
    assert result.recommended_next_step == NEXT_STEP_MANUAL_POSITION_RISK_CHECK


def test_fresh_accepted_unknown_position_fails_closed() -> None:
    result = build_fresh_post_entry_position_confirmation_gate_controlled(
        runtime_result=_runtime(runtime_read_succeeded=False),
    )

    assert result.case is FreshPostEntryPositionConfirmationGateCase.CASE_4
    assert (
        result.fresh_position_confirmation_status
        is FreshPostEntryPositionConfirmationStatus.FRESH_POSITION_UNKNOWN_FAIL_CLOSED
    )
    assert result.position_status is PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    assert result.fresh_entry_effect_confirmed_by_position is False
    assert result.close_planning_allowed is False
    assert result.recommended_next_step == NEXT_STEP_FRESH_POST_ENTRY_UNKNOWN_SAFE_STOP


def test_fresh_entry_summary_must_be_accepted_once_without_retry_or_repost() -> None:
    result = build_fresh_post_entry_position_confirmation_gate_controlled(
        FreshPostEntryPositionConfirmationGateInput(
            fresh_entry_summary=FreshEntryPostSafeSummaryInput(
                fresh_cycle=False,
                previous_attempt_retry=True,
                previous_attempt_repost=True,
                fresh_entry_post_execution_count=2,
                fresh_entry_result_safe_status="UNKNOWN_BLOCKED",
                fresh_entry_sanitized_result_category=(
                    SafePostResultCategory.RESULT_UNKNOWN_FAIL_CLOSED.value
                ),
                fresh_entry_safe_reconciliation_status=(
                    SafeReconciliationStatus.RECONCILIATION_BLOCKED_NOT_READY.value
                ),
                fresh_entry_retry_attempted=True,
                fresh_entry_repost_attempted=True,
                fresh_entry_second_post_attempted=True,
                close_post_executed=True,
                ledger_updated=True,
                receipt_handoff_executed=True,
            ),
        ),
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.case is FreshPostEntryPositionConfirmationGateCase.CASE_4
    assert (
        result.fresh_position_confirmation_status
        is FreshPostEntryPositionConfirmationStatus.FRESH_ENTRY_SUMMARY_BLOCKED
    )
    assert result.fresh_entry_effect_confirmed_by_position is False
    assert result.close_planning_allowed is False
    for reason in (
        "fresh_cycle_missing",
        "previous_attempt_retry",
        "previous_attempt_repost",
        "fresh_entry_post_count_not_one",
        "fresh_entry_result_status_not_accepted",
        "fresh_entry_result_category_not_accepted",
        "fresh_entry_reconciliation_not_ready",
        "fresh_entry_retry_attempted",
        "fresh_entry_repost_attempted",
        "fresh_entry_second_post_attempted",
        "close_post_executed",
        "ledger_updated",
        "receipt_handoff_executed",
    ):
        assert reason in result.blocked_reasons


def test_raw_id_value_and_credential_sentinels_block_without_exposure() -> None:
    runtime = _runtime(
        raw_response_exposure_attempted=True,
        raw_position_exposure_attempted=True,
        broker_api_response_exposure_attempted=True,
        position_id_exposure_attempted=True,
        account_id_exposure_attempted=True,
        order_id_exposure_attempted=True,
        transaction_id_exposure_attempted=True,
        actual_price_value_exposure_attempted=True,
        actual_pnl_value_exposure_attempted=True,
        credential_value_exposure_attempted=True,
        signature_value_exposure_attempted=True,
        headers_value_exposure_attempted=True,
    )
    result = build_fresh_post_entry_position_confirmation_gate_controlled(
        FreshPostEntryPositionConfirmationGateInput(
            fresh_entry_summary=FreshEntryPostSafeSummaryInput(
                raw_request_exposed=True,
                broker_api_response_exposed=True,
                position_id_exposed=True,
                account_id_exposed=True,
                order_id_exposed=True,
                transaction_id_exposed=True,
                credential_value_exposed=True,
                signature_value_exposed=True,
                headers_value_exposed=True,
            ),
            raw_request_exposure_attempted_this_step=True,
            position_id_exposure_attempted_this_step=True,
            account_id_exposure_attempted_this_step=True,
            order_id_exposure_attempted_this_step=True,
            transaction_id_exposure_attempted_this_step=True,
            credential_value_exposure_attempted_this_step=True,
            signature_value_exposure_attempted_this_step=True,
            headers_value_exposure_attempted_this_step=True,
        ),
        runtime_result=runtime,
    )
    rendered = render_fresh_post_entry_position_confirmation_gate_markdown(result)
    dumped = repr(asdict(result)) + rendered

    assert result.raw_position_exposed is False
    assert result.raw_request_exposed is False
    assert result.raw_response_exposed is False
    assert result.position_id_exposed is False
    assert result.account_id_exposed is False
    assert result.order_id_exposed is False
    assert result.transaction_id_exposed is False
    assert result.broker_api_response_exposed is False
    assert result.credential_value_exposed is False
    assert result.signature_value_exposed is False
    assert result.headers_value_exposed is False
    for sentinel in ("raw_payload", "pos-", "acct-", "order-", "txn-", "secret"):
        assert sentinel not in dumped


def test_current_step_never_retries_posts_closes_ledgers_or_receipts() -> None:
    result = build_fresh_post_entry_position_confirmation_gate_controlled(
        FreshPostEntryPositionConfirmationGateInput(
            fresh_entry_post_attempted_this_step=True,
            fresh_entry_retry_attempted_this_step=True,
            fresh_entry_repost_attempted_this_step=True,
            second_entry_post_attempted_this_step=True,
            close_post_attempted_this_step=True,
            order_endpoint_called_this_step=True,
            live_order_once_called_this_step=True,
            ledger_update_attempted_this_step=True,
            receipt_handoff_attempted_this_step=True,
        ),
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.fresh_entry_post_executed_this_step is False
    assert result.close_post_executed_this_step is False
    assert result.retry_or_repost_attempted_this_step is False
    assert result.second_entry_post_attempted_this_step is False
    assert result.ledger_updated_this_step is False
    assert result.receipt_handoff_executed_this_step is False
    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_entry_allowed is False
    assert result.close_post_allowed_now is False
    assert "fresh_entry_post_attempted_this_step" in result.blocked_reasons
    assert "close_post_attempted_this_step" in result.blocked_reasons
    assert "ledger_update_attempted_this_step" in result.blocked_reasons
    assert "receipt_handoff_attempted_this_step" in result.blocked_reasons


def test_default_summary_is_current_fresh_accepted_safe_category() -> None:
    summary = FreshEntryPostSafeSummaryInput()

    assert summary.previous_case == "CASE 1"
    assert summary.fresh_cycle is True
    assert summary.previous_attempt_retry is False
    assert summary.previous_attempt_repost is False
    assert summary.fresh_entry_http_post_executed is True
    assert summary.fresh_entry_post_execution_count == 1
    assert summary.fresh_entry_result_safe_status == FRESH_ENTRY_SAFE_STATUS_ACCEPTED
    assert (
        summary.fresh_entry_sanitized_result_category
        == SafePostResultCategory.RESULT_ACCEPTED_SANITIZED.value
    )


def test_module_has_no_api_order_env_private_http_or_live_order_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_fresh_post_entry_position_confirmation_gate_controlled.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "app.brokers",
        "app.private_api",
        "backend.scripts",
        "scripts",
        "httpx",
        "requests",
        "urllib",
        "urllib3",
        "socket",
        "subprocess",
        "dotenv",
        "os",
    }
    blocked_names = {
        "live_order_once",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "getenv",
        "environ",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not alias.name.startswith(tuple(blocked_modules))
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(tuple(blocked_modules))
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
