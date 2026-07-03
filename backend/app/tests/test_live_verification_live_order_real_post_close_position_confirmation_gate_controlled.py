from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_position_runtime_safe_read_controlled import (
    PositionRuntimeSafeReadControlledInput,
    build_position_runtime_safe_read_controlled,
)
from app.live_verification.live_order_real_post_close_position_confirmation_gate_controlled import (
    CLOSE_RESULT_ACCEPTED,
    FRESH_ENTRY_RESULT_ACCEPTED,
    NEXT_STEP_LEVEL5_CYCLE_COMPLETION_HANDOFF,
    NEXT_STEP_MANUAL_POSITION_RISK_CHECK,
    NEXT_STEP_POST_CLOSE_UNKNOWN_SAFE_STOP,
    PostClosePositionConfirmationGateCase,
    PostClosePositionConfirmationGateInput,
    PostClosePositionConfirmationStatus,
    PreviousEntryClosePostSafeSummaryInput,
    build_post_close_position_confirmation_gate_controlled,
    render_post_close_position_confirmation_gate_markdown,
)


def _runtime_input(**overrides: object) -> PositionRuntimeSafeReadControlledInput:
    defaults: dict[str, object] = {
        "credential_presence_checked": True,
        "credential_presence_available": True,
        "all_required_credentials_present": True,
        "runtime_read_executed": True,
        "runtime_read_succeeded": True,
        "position_count_safe": 0,
    }
    defaults.update(overrides)
    return PositionRuntimeSafeReadControlledInput(**defaults)


def _runtime(**overrides: object):
    return build_position_runtime_safe_read_controlled(_runtime_input(**overrides))


def test_close_accepted_runtime_no_position_completes_level5_minimal_cycle() -> None:
    result = build_post_close_position_confirmation_gate_controlled(
        runtime_result=_runtime(position_count_safe=0),
    )

    assert result.case is PostClosePositionConfirmationGateCase.CASE_1
    assert (
        result.position_confirmation_status
        is PostClosePositionConfirmationStatus
        .NO_POSITION_AFTER_CLOSE_POST_LEVEL5_COMPLETED
    )
    assert result.position_status is PositionReadOnlyControlledStatus.NO_POSITION
    assert result.position_count_safe == 0
    assert result.close_effect_confirmed_by_position is True
    assert result.post_close_position_status == "NO_POSITION_AFTER_CLOSE_POST"
    assert result.next_cycle_state == "LEVEL5_MINIMAL_CYCLE_COMPLETED"
    assert result.level5_minimal_cycle_completed is True
    assert result.level5_full_auto_cycle_completed is True
    assert result.entry_post_executed_once is True
    assert result.close_post_executed_once is True
    assert result.retry_repost_second_post_all_false is True
    assert result.ledger_receipt_executed is False
    assert result.recommended_next_step == NEXT_STEP_LEVEL5_CYCLE_COMPLETION_HANDOFF


def test_close_accepted_runtime_one_position_safe_stops_without_retry() -> None:
    result = build_post_close_position_confirmation_gate_controlled(
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.case is PostClosePositionConfirmationGateCase.CASE_2
    assert (
        result.position_confirmation_status
        is PostClosePositionConfirmationStatus
        .CLOSE_ACCEPTED_BUT_POSITION_STILL_VISIBLE_SAFE_STOP
    )
    assert result.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert result.position_count_safe == 1
    assert result.close_effect_confirmed_by_position is False
    assert result.level5_minimal_cycle_completed is False
    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_close_allowed is False
    assert result.close_planning_allowed is False
    assert result.close_execution_allowed_now is False


def test_close_accepted_runtime_multiple_requires_manual_position_risk_check() -> None:
    result = build_post_close_position_confirmation_gate_controlled(
        runtime_result=_runtime(position_count_safe=2),
    )

    assert result.case is PostClosePositionConfirmationGateCase.CASE_3
    assert (
        result.position_confirmation_status
        is PostClosePositionConfirmationStatus.POST_CLOSE_MULTIPLE_POSITIONS_BLOCKED
    )
    assert result.position_status is (
        PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    )
    assert result.position_count_safe == 2
    assert result.has_multiple_positions is True
    assert result.close_effect_confirmed_by_position is False
    assert result.level5_minimal_cycle_completed is False
    assert result.next_cycle_state == "HALTED_MANUAL_CHECK_REQUIRED"
    assert result.recommended_next_step == NEXT_STEP_MANUAL_POSITION_RISK_CHECK


def test_close_accepted_runtime_unknown_fails_closed() -> None:
    result = build_post_close_position_confirmation_gate_controlled(
        runtime_result=_runtime(runtime_read_succeeded=False),
    )

    assert result.case is PostClosePositionConfirmationGateCase.CASE_4
    assert (
        result.position_confirmation_status
        is PostClosePositionConfirmationStatus.POST_CLOSE_POSITION_UNKNOWN_FAIL_CLOSED
    )
    assert result.position_status is PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    assert result.close_effect_confirmed_by_position is False
    assert result.level5_minimal_cycle_completed is False
    assert result.recommended_next_step == NEXT_STEP_POST_CLOSE_UNKNOWN_SAFE_STOP


def test_credential_missing_blocks_post_close_confirmation() -> None:
    runtime = build_position_runtime_safe_read_controlled(
        PositionRuntimeSafeReadControlledInput(
            credential_presence_checked=True,
            credential_presence_available=False,
            all_required_credentials_present=False,
            runtime_read_executed=False,
        ),
    )

    result = build_post_close_position_confirmation_gate_controlled(
        runtime_result=runtime,
    )

    assert result.case is PostClosePositionConfirmationGateCase.CASE_4
    assert (
        result.position_confirmation_status
        is PostClosePositionConfirmationStatus.CREDENTIAL_PRESENCE_BLOCKED
    )
    assert result.credential_presence_available is False
    assert result.runtime_read_executed is False
    assert result.level5_minimal_cycle_completed is False


def test_previous_entry_and_close_summaries_must_be_accepted_once_only() -> None:
    result = build_post_close_position_confirmation_gate_controlled(
        PostClosePositionConfirmationGateInput(
            previous_summary=PreviousEntryClosePostSafeSummaryInput(
                fresh_entry_http_post_executed=False,
                fresh_entry_post_execution_count=2,
                fresh_entry_sanitized_result_category="UNKNOWN_SAFE",
                fresh_entry_retry_attempted=True,
                fresh_entry_repost_attempted=True,
                fresh_entry_second_post_attempted=True,
                close_http_post_executed=False,
                close_post_execution_count=2,
                close_sanitized_result_category="UNKNOWN_SAFE",
                close_safe_reconciliation_status="UNKNOWN_SAFE",
                close_retry_attempted=True,
                close_repost_attempted=True,
                close_second_post_attempted=True,
                ledger_updated=True,
                receipt_handoff_executed=True,
            ),
        ),
        runtime_result=_runtime(position_count_safe=0),
    )

    assert result.case is PostClosePositionConfirmationGateCase.CASE_4
    assert (
        result.position_confirmation_status
        is PostClosePositionConfirmationStatus.PREVIOUS_ENTRY_CLOSE_SUMMARY_BLOCKED
    )
    assert result.entry_post_executed_once is False
    assert result.close_post_executed_once is False
    assert result.retry_repost_second_post_all_false is False
    assert result.ledger_receipt_executed is True
    assert "fresh_entry_post_not_exactly_once" in result.blocked_reasons
    assert "fresh_entry_result_not_accepted_sanitized" in result.blocked_reasons
    assert "close_post_not_exactly_once" in result.blocked_reasons
    assert "close_result_not_accepted_sanitized" in result.blocked_reasons
    assert "retry_repost_or_second_post_attempted" in result.blocked_reasons
    assert "ledger_or_receipt_executed" in result.blocked_reasons


def test_current_step_never_retries_reposts_posts_ledgers_or_receipts() -> None:
    result = build_post_close_position_confirmation_gate_controlled(
        PostClosePositionConfirmationGateInput(
            actual_close_post_attempted_this_step=True,
            close_retry_attempted_this_step=True,
            close_repost_attempted_this_step=True,
            second_close_post_attempted_this_step=True,
            actual_entry_post_attempted_this_step=True,
            order_endpoint_called_this_step=True,
            live_order_once_called_this_step=True,
            ledger_update_attempted_this_step=True,
            receipt_handoff_attempted_this_step=True,
        ),
        runtime_result=_runtime(position_count_safe=0),
    )

    assert result.actual_close_post_executed_this_step is False
    assert result.actual_entry_post_executed_this_step is False
    assert result.close_retry_or_repost_attempted_this_step is False
    assert result.second_close_post_attempted_this_step is False
    assert result.ledger_updated_this_step is False
    assert result.receipt_handoff_executed_this_step is False
    assert result.level5_minimal_cycle_completed is False
    assert result.retry_allowed is False
    assert result.repost_allowed is False
    assert result.second_close_allowed is False
    assert "close_post_attempted_this_step" in result.blocked_reasons
    assert "close_retry_attempted_this_step" in result.blocked_reasons
    assert "close_repost_attempted_this_step" in result.blocked_reasons
    assert "second_close_post_attempted_this_step" in result.blocked_reasons
    assert "entry_post_attempted_this_step" in result.blocked_reasons


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
    result = build_post_close_position_confirmation_gate_controlled(
        PostClosePositionConfirmationGateInput(
            raw_request_exposure_attempted_this_step=True,
            raw_response_exposure_attempted_this_step=True,
            broker_api_response_exposure_attempted_this_step=True,
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
    rendered = render_post_close_position_confirmation_gate_markdown(result)
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
    assert "current_step_raw_id_value_exposure_blocked" in result.blocked_reasons
    for sentinel in ("raw_payload", "pos-", "acct-", "order-", "txn-", "secret"):
        assert sentinel not in dumped


def test_render_contains_only_safe_post_close_fields() -> None:
    result = build_post_close_position_confirmation_gate_controlled(
        runtime_result=_runtime(position_count_safe=0),
    )
    rendered = render_post_close_position_confirmation_gate_markdown(result)

    assert FRESH_ENTRY_RESULT_ACCEPTED in rendered
    assert CLOSE_RESULT_ACCEPTED in rendered
    assert "position_status: NO_POSITION" in rendered
    assert "position_count_safe: 0" in rendered
    assert "level5_minimal_cycle_completed: true" in rendered
    assert "raw_position_exposed: false" in rendered
    assert "credential_value_exposed: false" in rendered


def test_module_has_no_api_order_env_private_http_or_live_order_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_post_close_position_confirmation_gate_controlled.py"
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
