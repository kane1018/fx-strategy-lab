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
from app.live_verification.live_order_real_post_entry_position_confirmation_gate_controlled import (
    NEXT_STEP_ENTRY_UNKNOWN_NO_POSITION_CLOSEOUT,
    NEXT_STEP_MANUAL_POSITION_RISK_CHECK,
    NEXT_STEP_POSITION_OPEN_SAFE_HANDOFF,
    NEXT_STEP_POST_ENTRY_UNKNOWN_SAFE_STOP,
    PostEntryPositionConfirmationGateCase,
    PostEntryPositionConfirmationGateInput,
    PostEntryPositionConfirmationStatus,
    PreviousEntryPostSafeSummaryInput,
    build_post_entry_position_confirmation_gate_controlled,
    render_post_entry_position_confirmation_gate_markdown,
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


def test_credential_missing_blocks_post_entry_position_confirmation() -> None:
    runtime = build_position_runtime_safe_read_controlled(
        PositionRuntimeSafeReadControlledInput(
            credential_presence_checked=True,
            credential_presence_available=False,
            all_required_credentials_present=False,
            runtime_read_executed=False,
        ),
    )

    result = build_post_entry_position_confirmation_gate_controlled(
        runtime_result=runtime,
    )

    assert result.case is PostEntryPositionConfirmationGateCase.CASE_4
    assert (
        result.position_confirmation_status
        is PostEntryPositionConfirmationStatus.CREDENTIAL_PRESENCE_BLOCKED
    )
    assert result.credential_presence_available is False
    assert result.runtime_read_executed is False
    assert result.entry_effect_confirmed_by_position is False
    assert result.close_execution_allowed_now is False


def test_runtime_one_position_confirms_entry_effect_and_position_open_safe_planning() -> None:
    result = build_post_entry_position_confirmation_gate_controlled(
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.case is PostEntryPositionConfirmationGateCase.CASE_1
    assert (
        result.position_confirmation_status
        is PostEntryPositionConfirmationStatus
        .ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE
    )
    assert result.position_status is PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    assert result.position_count_safe == 1
    assert result.entry_effect_confirmed_by_position is True
    assert result.next_cycle_state == "POSITION_OPEN_SAFE"
    assert result.close_planning_allowed is True
    assert result.close_execution_gate_may_be_planned is True
    assert result.close_execution_allowed_now is False
    assert result.recommended_next_step == NEXT_STEP_POSITION_OPEN_SAFE_HANDOFF


def test_runtime_no_position_maps_to_entry_unknown_no_position_stop() -> None:
    result = build_post_entry_position_confirmation_gate_controlled(
        runtime_result=_runtime(position_count_safe=0),
    )

    assert result.case is PostEntryPositionConfirmationGateCase.CASE_2
    assert (
        result.position_confirmation_status
        is PostEntryPositionConfirmationStatus.NO_POSITION_AFTER_ENTRY_POST
    )
    assert result.position_status is PositionReadOnlyControlledStatus.NO_POSITION
    assert result.position_count_safe == 0
    assert result.entry_effect_confirmed_by_position is False
    assert result.new_entry_allowed is False
    assert result.retry_allowed is False
    assert result.second_entry_allowed is False
    assert result.next_cycle_state == "UNKNOWN_RESULT_SAFE_STOP"
    assert result.recommended_next_step == NEXT_STEP_ENTRY_UNKNOWN_NO_POSITION_CLOSEOUT


def test_runtime_multiple_blocks_tool_action_and_requires_manual_check() -> None:
    result = build_post_entry_position_confirmation_gate_controlled(
        runtime_result=_runtime(position_count_safe=2),
    )

    assert result.case is PostEntryPositionConfirmationGateCase.CASE_3
    assert (
        result.position_confirmation_status
        is PostEntryPositionConfirmationStatus
        .MULTIPLE_POSITIONS_BLOCKED_MANUAL_CHECK_REQUIRED
    )
    assert result.position_status is (
        PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    )
    assert result.has_multiple_positions is True
    assert result.close_planning_allowed is False
    assert result.close_execution_allowed_now is False
    assert result.recommended_next_step == NEXT_STEP_MANUAL_POSITION_RISK_CHECK


def test_runtime_unknown_fails_closed() -> None:
    result = build_post_entry_position_confirmation_gate_controlled(
        runtime_result=_runtime(runtime_read_succeeded=False),
    )

    assert result.case is PostEntryPositionConfirmationGateCase.CASE_4
    assert (
        result.position_confirmation_status
        is PostEntryPositionConfirmationStatus
        .UNKNOWN_FAIL_CLOSED_MANUAL_CHECK_REQUIRED
    )
    assert result.position_status is PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    assert result.entry_effect_confirmed_by_position is False
    assert result.close_planning_allowed is False
    assert result.recommended_next_step == NEXT_STEP_POST_ENTRY_UNKNOWN_SAFE_STOP


def test_previous_entry_summary_must_be_exactly_one_post_without_retry_or_close() -> None:
    result = build_post_entry_position_confirmation_gate_controlled(
        PostEntryPositionConfirmationGateInput(
            previous_entry_summary=PreviousEntryPostSafeSummaryInput(
                entry_post_execution_count=2,
                entry_retry_attempted=True,
                entry_second_post_attempted=True,
                close_post_executed=True,
                ledger_updated=True,
                receipt_handoff_executed=True,
            ),
        ),
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.case is PostEntryPositionConfirmationGateCase.CASE_4
    assert (
        result.position_confirmation_status
        is PostEntryPositionConfirmationStatus.PREVIOUS_ENTRY_SUMMARY_BLOCKED
    )
    assert result.entry_effect_confirmed_by_position is False
    assert result.close_planning_allowed is False
    assert "previous_entry_post_count_not_one" in result.blocked_reasons
    assert "previous_entry_retry_attempted" in result.blocked_reasons
    assert "previous_entry_second_post_attempted" in result.blocked_reasons
    assert "previous_close_post_executed" in result.blocked_reasons
    assert "previous_ledger_updated" in result.blocked_reasons
    assert "previous_receipt_handoff_executed" in result.blocked_reasons


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
    result = build_post_entry_position_confirmation_gate_controlled(
        PostEntryPositionConfirmationGateInput(
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
    rendered = render_post_entry_position_confirmation_gate_markdown(result)
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
    result = build_post_entry_position_confirmation_gate_controlled(
        PostEntryPositionConfirmationGateInput(
            actual_entry_post_attempted_this_step=True,
            entry_retry_attempted_this_step=True,
            entry_repost_attempted_this_step=True,
            second_entry_post_attempted_this_step=True,
            close_post_attempted_this_step=True,
            order_endpoint_called_this_step=True,
            live_order_once_called_this_step=True,
            ledger_update_attempted_this_step=True,
            receipt_handoff_attempted_this_step=True,
        ),
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.actual_entry_post_executed_this_step is False
    assert result.close_post_executed_this_step is False
    assert result.retry_or_repost_attempted_this_step is False
    assert result.second_entry_post_attempted_this_step is False
    assert result.ledger_updated_this_step is False
    assert result.receipt_handoff_executed_this_step is False
    assert result.retry_allowed is False
    assert result.second_entry_allowed is False
    assert result.close_post_allowed_now is False
    assert "entry_post_attempted_this_step" in result.blocked_reasons
    assert "close_post_attempted_this_step" in result.blocked_reasons
    assert "ledger_update_attempted_this_step" in result.blocked_reasons
    assert "receipt_handoff_attempted_this_step" in result.blocked_reasons


def test_module_has_no_api_order_env_private_http_or_live_order_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_post_entry_position_confirmation_gate_controlled.py"
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
