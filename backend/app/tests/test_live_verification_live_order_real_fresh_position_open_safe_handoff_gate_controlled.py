from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification.live_order_real_fresh_position_open_safe_handoff_gate_controlled import (
    NEXT_STEP_CLOSE_ORDER_EXECUTION_GATE,
    NEXT_STEP_FRESH_POSITION_OPEN_UNKNOWN_SAFE_STOP,
    NEXT_STEP_MANUAL_POSITION_RISK_CHECK,
    NEXT_STEP_POSITION_GONE_SAFE_STOP,
    FreshPositionOpenSafeHandoffGateCase,
    FreshPositionOpenSafeHandoffGateInput,
    FreshPositionOpenSafeHandoffStatus,
    build_fresh_position_open_safe_handoff_gate_controlled,
    render_fresh_position_open_safe_handoff_gate_markdown,
)
from app.live_verification.live_order_real_fresh_post_entry_position_confirmation_gate_controlled import (  # noqa: E501
    FreshEntryPostSafeSummaryInput,
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


def test_fresh_accepted_one_position_handoff_ready() -> None:
    result = build_fresh_position_open_safe_handoff_gate_controlled(
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.case is FreshPositionOpenSafeHandoffGateCase.CASE_1
    assert (
        result.handoff_status
        is FreshPositionOpenSafeHandoffStatus.FRESH_POSITION_OPEN_SAFE_HANDOFF_READY
    )
    assert result.handoff_gate_ready is True
    assert result.fresh_entry_post_executed is True
    assert result.fresh_entry_post_execution_count == 1
    assert (
        result.fresh_entry_result_safe_category
        == SafePostResultCategory.RESULT_ACCEPTED_SANITIZED.value
    )
    assert result.runtime_position_status is (
        PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    )
    assert result.runtime_position_count_safe == 1
    assert result.fresh_position_open_safe is True
    assert result.fresh_position_open_safe_handoff_ready is True
    assert result.next_cycle_state == "FRESH_POSITION_OPEN_SAFE_HANDOFF_READY"
    assert result.close_execution_gate_may_be_planned is True
    assert result.close_execution_allowed_now is False
    assert result.close_post_allowed_now is False
    assert result.recommended_next_step == NEXT_STEP_CLOSE_ORDER_EXECUTION_GATE


def test_close_route_planning_is_ready_only_for_one_position_open() -> None:
    open_result = build_fresh_position_open_safe_handoff_gate_controlled(
        runtime_result=_runtime(position_count_safe=1),
    )
    no_position = build_fresh_position_open_safe_handoff_gate_controlled(
        runtime_result=_runtime(position_count_safe=0),
    )
    multiple = build_fresh_position_open_safe_handoff_gate_controlled(
        runtime_result=_runtime(position_count_safe=2),
    )

    assert open_result.close_route_ready is True
    assert open_result.close_planning_allowed is True
    assert open_result.close_execution_gate_may_be_planned is True
    assert no_position.close_route_ready is False
    assert no_position.close_planning_allowed is False
    assert no_position.close_execution_gate_may_be_planned is False
    assert multiple.close_route_ready is False
    assert multiple.close_planning_allowed is False
    assert multiple.close_execution_gate_may_be_planned is False


def test_fresh_accepted_no_position_safe_stops_before_close_gate() -> None:
    result = build_fresh_position_open_safe_handoff_gate_controlled(
        runtime_result=_runtime(position_count_safe=0),
    )

    assert result.case is FreshPositionOpenSafeHandoffGateCase.CASE_2
    assert (
        result.handoff_status
        is FreshPositionOpenSafeHandoffStatus
        .FRESH_POSITION_GONE_BEFORE_CLOSE_SAFE_STOP
    )
    assert result.runtime_position_status is PositionReadOnlyControlledStatus.NO_POSITION
    assert result.runtime_position_count_safe == 0
    assert result.handoff_gate_ready is False
    assert result.fresh_position_open_safe is False
    assert result.close_execution_gate_may_be_planned is False
    assert result.close_execution_allowed_now is False
    assert result.recommended_next_step == NEXT_STEP_POSITION_GONE_SAFE_STOP


def test_fresh_accepted_multiple_positions_requires_manual_risk_check() -> None:
    result = build_fresh_position_open_safe_handoff_gate_controlled(
        runtime_result=_runtime(position_count_safe=2),
    )

    assert result.case is FreshPositionOpenSafeHandoffGateCase.CASE_3
    assert (
        result.handoff_status
        is FreshPositionOpenSafeHandoffStatus
        .FRESH_MULTIPLE_POSITIONS_HANDOFF_BLOCKED
    )
    assert result.runtime_position_status is (
        PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED
    )
    assert result.has_multiple_positions is True
    assert result.handoff_gate_ready is False
    assert result.close_execution_gate_may_be_planned is False
    assert result.recommended_next_step == NEXT_STEP_MANUAL_POSITION_RISK_CHECK


def test_fresh_accepted_unknown_position_fails_closed() -> None:
    result = build_fresh_position_open_safe_handoff_gate_controlled(
        runtime_result=_runtime(runtime_read_succeeded=False),
    )

    assert result.case is FreshPositionOpenSafeHandoffGateCase.CASE_4
    assert (
        result.handoff_status
        is FreshPositionOpenSafeHandoffStatus.FRESH_POSITION_HANDOFF_UNKNOWN_FAIL_CLOSED
    )
    assert result.runtime_position_status is (
        PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED
    )
    assert result.handoff_gate_ready is False
    assert result.close_execution_gate_may_be_planned is False
    assert result.recommended_next_step == NEXT_STEP_FRESH_POSITION_OPEN_UNKNOWN_SAFE_STOP


def test_fresh_retry_repost_second_entry_or_previous_close_blocks_handoff() -> None:
    result = build_fresh_position_open_safe_handoff_gate_controlled(
        FreshPositionOpenSafeHandoffGateInput(
            fresh_entry_summary=FreshEntryPostSafeSummaryInput(
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
            ),
        ),
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.case is FreshPositionOpenSafeHandoffGateCase.CASE_4
    assert (
        result.handoff_status
        is FreshPositionOpenSafeHandoffStatus.FRESH_ENTRY_SUMMARY_BLOCKED
    )
    assert result.handoff_gate_ready is False
    assert result.close_execution_gate_may_be_planned is False
    for reason in (
        "fresh_entry_post_count_not_one",
        "fresh_entry_result_status_not_accepted",
        "fresh_entry_result_category_not_accepted",
        "fresh_entry_reconciliation_not_ready",
        "fresh_entry_retry_attempted",
        "fresh_entry_repost_attempted",
        "fresh_entry_second_post_attempted",
        "close_post_executed",
    ):
        assert reason in result.blocked_reasons


def test_current_step_never_posts_retries_closes_ledgers_or_receipts() -> None:
    result = build_fresh_position_open_safe_handoff_gate_controlled(
        FreshPositionOpenSafeHandoffGateInput(
            entry_post_attempted_this_step=True,
            entry_retry_attempted_this_step=True,
            entry_repost_attempted_this_step=True,
            second_entry_post_attempted_this_step=True,
            close_post_attempted_this_step=True,
            close_order_endpoint_called_this_step=True,
            order_endpoint_called_this_step=True,
            live_order_once_called_this_step=True,
            ledger_update_attempted_this_step=True,
            attempt_counter_persisted_this_step=True,
            receipt_handoff_attempted_this_step=True,
        ),
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.entry_post_executed_this_step is False
    assert result.close_post_executed_this_step is False
    assert result.retry_or_repost_attempted_this_step is False
    assert result.second_entry_post_attempted_this_step is False
    assert result.ledger_updated_this_step is False
    assert result.receipt_handoff_executed_this_step is False
    assert result.actual_entry_post_allowed_now is False
    assert result.close_post_allowed_now is False
    assert "entry_post_attempted_this_step" in result.blocked_reasons
    assert "close_post_attempted_this_step" in result.blocked_reasons
    assert "close_order_endpoint_called_this_step" in result.blocked_reasons
    assert "ledger_update_attempted_this_step" in result.blocked_reasons
    assert "attempt_counter_persisted_this_step" in result.blocked_reasons


def test_close_execution_allowed_now_is_false_for_all_safe_runtime_statuses() -> None:
    for runtime in (
        _runtime(position_count_safe=1),
        _runtime(position_count_safe=0),
        _runtime(position_count_safe=2),
        _runtime(runtime_read_succeeded=False),
    ):
        result = build_fresh_position_open_safe_handoff_gate_controlled(
            runtime_result=runtime,
        )

        assert result.close_execution_allowed_now is False
        assert result.close_post_executed is False
        assert result.close_post_count == 0
        assert result.close_retry_allowed is False
        assert result.close_repost_allowed is False
        assert result.close_second_post_allowed is False


def test_close_gate_requires_new_inputs_and_does_not_reuse_entry_confirmation() -> None:
    result = build_fresh_position_open_safe_handoff_gate_controlled(
        runtime_result=_runtime(position_count_safe=1),
    )

    assert result.close_gate_requires_new_runtime_position_read is True
    assert result.close_gate_requires_new_operator_readiness is True
    assert result.close_gate_requires_new_close_preview is True
    assert result.close_gate_requires_new_close_confirmation is True
    assert result.close_gate_must_not_reuse_entry_confirmation is True
    assert result.close_gate_must_not_expose_raw_id_value is True
    assert result.level5_full_auto_cycle_completed is False


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
    result = build_fresh_position_open_safe_handoff_gate_controlled(
        FreshPositionOpenSafeHandoffGateInput(
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
    rendered = render_fresh_position_open_safe_handoff_gate_markdown(result)
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


def test_module_has_no_api_order_env_private_http_or_live_order_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_fresh_position_open_safe_handoff_gate_controlled.py"
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
