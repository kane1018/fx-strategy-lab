from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from app.live_verification.live_order_real_close_order_execution_route_controlled import (
    APPROVED_CLOSE_PRIMITIVE_KIND_CLOSE_SPECIFIC,
    APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC,
    APPROVED_CLOSE_PRIMITIVE_KIND_NOT_APPROVED,
    NEXT_CYCLE_STATE_READY,
    NEXT_CYCLE_STATE_SIDE_UNRESOLVED,
    CloseOrderExecutionRouteControlledInput,
    CloseOrderExecutionRouteControlledStatus,
    build_close_order_execution_route_controlled,
    render_close_order_executable_preview_markdown,
)
from app.live_verification.live_order_real_close_order_route_controlled import (
    CLOSE_ORDER_TYPE_SAFE_LABEL,
    CLOSE_SIDE_SAFE_LABEL,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)


def _ready_input(**overrides: object) -> CloseOrderExecutionRouteControlledInput:
    values = {
        "runtime_position_status": PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        "position_count_safe": 1,
        "has_exactly_one_position": True,
        "has_multiple_positions": False,
        "close_route_ready": True,
        "close_planning_allowed": True,
        "fresh_entry_side_safe_label": "BUY",
        "approved_close_post_primitive_kind": (
            APPROVED_CLOSE_PRIMITIVE_KIND_GUARDED_GENERIC
        ),
        "approved_close_post_primitive_is_generic_order": True,
        "generic_order_accepted_as_close_only_with_exact_one_position_guard": True,
    }
    values.update(overrides)
    return CloseOrderExecutionRouteControlledInput(**values)


@pytest.mark.parametrize(
    ("entry_side", "close_side"),
    (
        ("BUY", "SELL"),
        ("SELL", "BUY"),
    ),
)
def test_fresh_entry_side_derives_concrete_close_side(
    entry_side: str,
    close_side: str,
) -> None:
    result = build_close_order_execution_route_controlled(
        _ready_input(fresh_entry_side_safe_label=entry_side),
    )

    assert result.status is CloseOrderExecutionRouteControlledStatus.READY_NO_POST
    assert result.close_execution_route_ready is True
    assert result.close_executable_preview_ready is True
    assert result.side_derivation.close_side_derivation_source == (
        "fresh_entry_side_safe_label"
    )
    assert result.side_derivation.input_side_safe_label == entry_side
    assert result.close_side_safe_label == close_side
    assert result.side_derivation.side_concrete is True
    assert result.side_derivation.opposite_placeholder_accepted is False
    assert result.side_derivation.codex_inferred_side is False


@pytest.mark.parametrize(
    ("operator_signal", "position_side", "close_side"),
    (
        ("ENTRY_BUY", "NOT_PROVIDED", "SELL"),
        ("ENTRY_SELL", "NOT_PROVIDED", "BUY"),
        ("NOT_PROVIDED", "BUY", "SELL"),
        ("NOT_PROVIDED", "SELL", "BUY"),
    ),
)
def test_operator_signal_and_position_side_derive_close_side(
    operator_signal: str,
    position_side: str,
    close_side: str,
) -> None:
    result = build_close_order_execution_route_controlled(
        _ready_input(
            fresh_entry_side_safe_label="NOT_PROVIDED",
            operator_signal_type=operator_signal,
            safe_position_side_label=position_side,
        ),
    )

    assert result.close_execution_route_ready is True
    assert result.close_side_safe_label == close_side
    assert result.executable_preview.close_side_safe_label == close_side


def test_consistent_safe_inputs_are_accepted_without_codex_inference() -> None:
    result = build_close_order_execution_route_controlled(
        _ready_input(
            fresh_entry_side_safe_label="BUY",
            operator_signal_type="ENTRY_BUY",
            safe_position_side_label="BUY",
        ),
    )

    assert result.close_execution_route_ready is True
    assert result.close_side_safe_label == "SELL"
    assert result.side_derivation.close_side_derivation_source == "MULTIPLE_SAFE_INPUTS"
    assert result.side_derivation.input_side_safe_label == "CONSISTENT_SAFE_INPUTS"
    assert result.side_derivation.codex_inferred_side is False


def test_opposite_placeholder_is_blocked_for_executable_preview() -> None:
    result = build_close_order_execution_route_controlled(
        _ready_input(fresh_entry_side_safe_label=CLOSE_SIDE_SAFE_LABEL),
    )

    assert result.close_execution_route_ready is False
    assert result.close_executable_preview_ready is False
    assert result.next_cycle_state == NEXT_CYCLE_STATE_SIDE_UNRESOLVED
    assert result.side_derivation.close_side_safe_label == CLOSE_SIDE_SAFE_LABEL
    assert result.side_derivation.opposite_placeholder_accepted is False
    assert "opposite_placeholder_not_executable" in result.blocked_reasons


def test_unknown_side_blocks_close_execution_route() -> None:
    result = build_close_order_execution_route_controlled(
        _ready_input(fresh_entry_side_safe_label="UNKNOWN"),
    )

    assert result.close_execution_route_ready is False
    assert result.close_executable_preview_ready is False
    assert result.side_derivation.side_concrete is False
    assert "close_side_unresolved" in result.blocked_reasons


def test_entry_side_and_position_side_mismatch_blocks_route() -> None:
    result = build_close_order_execution_route_controlled(
        _ready_input(
            fresh_entry_side_safe_label="BUY",
            safe_position_side_label="SELL",
        ),
    )

    assert result.close_execution_route_ready is False
    assert result.side_derivation.side_mismatch_detected is True
    assert result.side_derivation.close_side_safe_label == "SIDE_MISMATCH_BLOCKED"
    assert "close_side_safe_label_mismatch" in result.blocked_reasons


@pytest.mark.parametrize(
    ("status", "count", "exactly_one", "multiple", "reason"),
    (
        (
            PositionReadOnlyControlledStatus.NO_POSITION,
            0,
            False,
            False,
            "runtime_position_status_not_one_position_open",
        ),
        (
            PositionReadOnlyControlledStatus.MULTIPLE_POSITIONS_BLOCKED,
            2,
            False,
            True,
            "has_multiple_positions_blocked",
        ),
        (
            PositionReadOnlyControlledStatus.UNKNOWN_FAIL_CLOSED,
            0,
            False,
            False,
            "runtime_position_status_not_one_position_open",
        ),
    ),
)
def test_non_one_position_status_blocks_close_executable_preview(
    status: PositionReadOnlyControlledStatus,
    count: int,
    exactly_one: bool,
    multiple: bool,
    reason: str,
) -> None:
    result = build_close_order_execution_route_controlled(
        _ready_input(
            runtime_position_status=status,
            position_count_safe=count,
            has_exactly_one_position=exactly_one,
            has_multiple_positions=multiple,
        ),
    )

    assert result.close_execution_route_ready is False
    assert result.close_executable_preview_ready is False
    assert reason in result.blocked_reasons


def test_close_executable_preview_keeps_fixed_units_market_and_no_post_flags() -> None:
    result = build_close_order_execution_route_controlled(_ready_input())
    preview = result.executable_preview

    assert result.next_cycle_state == NEXT_CYCLE_STATE_READY
    assert result.close_units_fixed == 100
    assert result.close_order_type_safe_label == CLOSE_ORDER_TYPE_SAFE_LABEL
    assert preview.close_units_fixed == 100
    assert preview.close_order_type_safe_label == "MARKET"
    assert result.one_close_post_max is True
    assert result.actual_close_post_allowed_now is False
    assert result.actual_close_post_executed is False
    assert result.close_post_execution_count == 0
    assert result.entry_post_this_step is False
    assert result.close_retry_allowed is False
    assert result.close_repost_allowed is False
    assert result.close_second_post_allowed is False
    assert result.ledger_update_this_step is False
    assert result.receipt_handoff_this_step is False


def test_actual_close_post_entry_retry_ledger_and_receipt_attempts_block() -> None:
    result = build_close_order_execution_route_controlled(
        _ready_input(
            actual_close_post_allowed_now=True,
            actual_close_post_attempted_this_step=True,
            entry_post_this_step=True,
            close_retry_allowed=True,
            close_repost_allowed=True,
            close_second_post_allowed=True,
            ledger_update_this_step=True,
            receipt_handoff_this_step=True,
            one_close_post_max=False,
            close_primitive_invocation_deferred=False,
        ),
    )

    assert result.close_execution_route_ready is False
    assert result.actual_close_post_allowed_now is False
    assert result.actual_close_post_executed is False
    assert result.entry_post_this_step is False
    assert result.close_retry_allowed is False
    assert result.close_repost_allowed is False
    assert result.close_second_post_allowed is False
    assert result.ledger_update_this_step is False
    assert result.receipt_handoff_this_step is False
    assert "actual_close_post_allowed_now" in result.blocked_reasons
    assert "actual_close_post_attempted_this_step" in result.blocked_reasons
    assert "close_primitive_invocation_must_be_deferred" in result.blocked_reasons


def test_raw_id_broker_and_credential_exposure_attempts_block_without_exposing() -> None:
    result = build_close_order_execution_route_controlled(
        _ready_input(
            raw_position_exposure_attempted=True,
            raw_request_exposure_attempted=True,
            raw_response_exposure_attempted=True,
            broker_api_response_exposure_attempted=True,
            position_id_exposure_attempted=True,
            account_id_exposure_attempted=True,
            order_id_exposure_attempted=True,
            transaction_id_exposure_attempted=True,
            trade_id_exposure_attempted=True,
            client_order_id_actual_value_exposure_attempted=True,
            credential_value_exposure_attempted=True,
            signature_value_exposure_attempted=True,
            headers_value_exposure_attempted=True,
        ),
    )

    assert result.close_execution_route_ready is False
    assert result.raw_position_exposed is False
    assert result.raw_request_exposed is False
    assert result.raw_response_exposed is False
    assert result.broker_api_response_exposed is False
    assert result.position_id_exposed is False
    assert result.account_id_exposed is False
    assert result.order_id_exposed is False
    assert result.transaction_id_exposed is False
    assert result.credential_value_exposed is False
    assert result.signature_value_exposed is False
    assert result.headers_value_exposed is False
    assert "raw_exposure_blocked" in result.blocked_reasons
    assert "id_exposure_blocked" in result.blocked_reasons
    assert "credential_signature_headers_exposure_blocked" in result.blocked_reasons


def test_generic_order_primitive_requires_explicit_exact_one_position_guard() -> None:
    missing_guard = build_close_order_execution_route_controlled(
        _ready_input(generic_order_accepted_as_close_only_with_exact_one_position_guard=False),
    )
    wrong_kind = build_close_order_execution_route_controlled(
        _ready_input(
            approved_close_post_primitive_kind=APPROVED_CLOSE_PRIMITIVE_KIND_NOT_APPROVED,
        ),
    )
    guarded = build_close_order_execution_route_controlled(_ready_input())

    assert missing_guard.approved_close_post_primitive_ready is False
    assert "generic_order_close_guard_missing" in missing_guard.blocked_reasons
    assert wrong_kind.approved_close_post_primitive_ready is False
    assert "approved_close_post_primitive_kind_not_guarded_generic" in (
        wrong_kind.blocked_reasons
    )
    assert guarded.approved_close_post_primitive_ready is True
    assert guarded.approved_close_post_primitive_is_generic_order is True
    assert (
        guarded.generic_order_accepted_as_close_only_with_exact_one_position_guard
        is True
    )


def test_close_specific_primitive_can_be_declared_ready_without_invocation() -> None:
    result = build_close_order_execution_route_controlled(
        _ready_input(
            approved_close_post_primitive_kind=APPROVED_CLOSE_PRIMITIVE_KIND_CLOSE_SPECIFIC,
            approved_close_post_primitive_is_close_specific=True,
            approved_close_post_primitive_is_generic_order=False,
            generic_order_accepted_as_close_only_with_exact_one_position_guard=False,
        ),
    )

    assert result.close_execution_route_ready is True
    assert result.approved_close_post_primitive_ready is True
    assert result.approved_close_post_primitive_is_close_specific is True
    assert result.close_primitive_invocation_deferred is True
    assert result.actual_close_post_allowed_now is False


def test_rendered_preview_and_asdict_exclude_unsafe_actual_values() -> None:
    result = build_close_order_execution_route_controlled(_ready_input())
    rendered = render_close_order_executable_preview_markdown(result)
    combined = repr(asdict(result)) + rendered

    assert "preview_ready: true" not in rendered
    assert "close_side_safe_label: SELL" in rendered
    assert "actual_close_post_allowed_now: false" in rendered
    assert "actual_close_post_executed: false" in rendered
    for fragment in (
        "acct-",
        "order-",
        "txn-",
        "pos-",
        "trade-",
        "client-order-",
        "raw_payload",
        "broker-body",
    ):
        assert fragment not in combined


def test_close_execution_route_module_has_no_api_order_env_or_http_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_close_order_execution_route_controlled.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "app.brokers",
        "app.private_api",
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
