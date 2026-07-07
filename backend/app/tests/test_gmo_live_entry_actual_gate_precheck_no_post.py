"""No-POST tests for the GMO live entry actual-gate PRECHECK.

These tests pin that the precheck is fail-closed by default, that no input
combination ever turns it into an entry POST permission, that the operator
current-turn exact confirmation can never be captured or banked here, and
that the module has no env/network/live_verification surface.
"""

from __future__ import annotations

import pathlib
from dataclasses import fields, replace

import pytest

from app.services.gmo_live_entry_actual_gate_precheck import (
    GmoEntryActualGatePrecheckInput,
    GmoEntryActualGatePrecheckNextStep,
    GmoEntryActualGatePrecheckStatus,
    GmoEntryOperatorSignalSafeLabel,
    build_gmo_live_entry_actual_gate_precheck_summary,
    classify_gmo_entry_actual_gate_precheck_blockers,
    normalize_entry_operator_signal_safe_label,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_entry_actual_gate_precheck.py"
)


def _all_safe_input(**overrides: object) -> GmoEntryActualGatePrecheckInput:
    base = GmoEntryActualGatePrecheckInput(
        head_equals_origin_main_safe=True,
        working_tree_clean_safe=True,
        credential_presence_safe_boolean=True,
        credential_boundary_ready=True,
        credential_actual_use_operator_approved=True,
        runtime_safe_read_performed=True,
        runtime_safe_read_fresh=True,
        pre_entry_open_positions_count_safe=0,
        pre_entry_active_or_pending_order_conflict_count_safe=0,
        fresh_entry_signal_safe_label_exists=True,
        entry_signal_is_fresh=True,
        operator_entry_signal_safe_label=GmoEntryOperatorSignalSafeLabel.ENTRY_BUY,
        operator_readiness_confirmed=True,
        max_entry_post_count=1,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def test_default_precheck_is_fail_closed_and_never_a_post_permission() -> None:
    summary = build_gmo_live_entry_actual_gate_precheck_summary()

    assert summary.precheck_ready is False
    assert summary.actual_entry_POST_allowed is False
    assert summary.ai_trade_decision_performed is False
    assert summary.entry_post_execution_gate_is_separate_step is True
    assert summary.operator_current_turn_exact_confirmation_still_required is True
    assert summary.operator_confirmation_substituted is False
    assert summary.entry_candidate_exists is False
    assert summary.retry_allowed is False
    assert summary.repost_allowed is False
    assert summary.second_post_allowed is False
    assert bool(summary) is False
    assert "ENTRY_PRECHECK_HEAD_MISMATCH" in summary.blocked_reasons
    assert "ENTRY_PRECHECK_CREDENTIAL_PRESENCE_NOT_CONFIRMED" in summary.blocked_reasons
    assert "ENTRY_PRECHECK_RUNTIME_SAFE_READ_NOT_PERFORMED" in summary.blocked_reasons
    assert "ENTRY_PRECHECK_OPEN_POSITIONS_NOT_ZERO" in summary.blocked_reasons
    assert "ENTRY_PRECHECK_OPERATOR_SIGNAL_NOT_PROVIDED" in summary.blocked_reasons
    assert "ENTRY_PRECHECK_OPERATOR_READINESS_NOT_CONFIRMED" in summary.blocked_reasons


def test_all_safe_input_is_ready_but_still_not_a_post_permission() -> None:
    summary = build_gmo_live_entry_actual_gate_precheck_summary(_all_safe_input())

    assert summary.precheck_ready is True
    assert summary.blocked_reasons == ()
    assert summary.entry_candidate_exists is True
    assert (
        summary.status
        is GmoEntryActualGatePrecheckStatus
        .ENTRY_PRECHECK_READY_NO_POST_OPERATOR_CURRENT_TURN_GATE_REQUIRED
    )
    assert (
        summary.recommended_next_step
        is GmoEntryActualGatePrecheckNextStep
        .NEXT_STEP_ENTRY_POST_GATE_WITH_OPERATOR_CURRENT_TURN_CONFIRMATION
    )
    assert summary.actual_entry_POST_allowed is False
    assert summary.ai_trade_decision_performed is False
    assert summary.operator_current_turn_exact_confirmation_still_required is True
    assert summary.operator_confirmation_substituted is False
    assert summary.max_entry_post_limit == 1
    assert bool(summary) is False


@pytest.mark.parametrize(
    ("overrides", "expected_blocker"),
    [
        ({"head_equals_origin_main_safe": False}, "ENTRY_PRECHECK_HEAD_MISMATCH"),
        ({"working_tree_clean_safe": False}, "ENTRY_PRECHECK_WORKING_TREE_NOT_CLEAN"),
        (
            {"credential_presence_safe_boolean": False},
            "ENTRY_PRECHECK_CREDENTIAL_PRESENCE_NOT_CONFIRMED",
        ),
        (
            {"credential_boundary_ready": False},
            "ENTRY_PRECHECK_CREDENTIAL_BOUNDARY_NOT_READY",
        ),
        (
            {"credential_actual_use_operator_approved": False},
            "ENTRY_PRECHECK_CREDENTIAL_ACTUAL_USE_NOT_APPROVED",
        ),
        (
            {"runtime_safe_read_performed": False},
            "ENTRY_PRECHECK_RUNTIME_SAFE_READ_NOT_PERFORMED",
        ),
        ({"runtime_safe_read_fresh": False}, "ENTRY_PRECHECK_RUNTIME_SAFE_READ_STALE"),
        (
            {"pre_entry_open_positions_count_safe": 1},
            "ENTRY_PRECHECK_OPEN_POSITIONS_NOT_ZERO",
        ),
        (
            {"pre_entry_open_positions_count_safe": None},
            "ENTRY_PRECHECK_OPEN_POSITIONS_NOT_ZERO",
        ),
        (
            {"pre_entry_active_or_pending_order_conflict_count_safe": 1},
            "ENTRY_PRECHECK_ACTIVE_PENDING_ORDER_CONFLICT",
        ),
        (
            {"pre_entry_active_or_pending_order_conflict_count_safe": None},
            "ENTRY_PRECHECK_ACTIVE_PENDING_ORDER_CONFLICT",
        ),
        (
            {"fresh_entry_signal_safe_label_exists": False},
            "ENTRY_PRECHECK_FRESH_ENTRY_SIGNAL_MISSING",
        ),
        ({"entry_signal_is_fresh": False}, "ENTRY_PRECHECK_ENTRY_SIGNAL_STALE"),
        (
            {"operator_entry_signal_safe_label": None},
            "ENTRY_PRECHECK_OPERATOR_SIGNAL_NOT_PROVIDED",
        ),
        (
            {"operator_readiness_confirmed": False},
            "ENTRY_PRECHECK_OPERATOR_READINESS_NOT_CONFIRMED",
        ),
        ({"max_entry_post_count": 0}, "ENTRY_PRECHECK_POST_LIMIT_INVALID"),
        ({"max_entry_post_count": 2}, "ENTRY_PRECHECK_POST_LIMIT_INVALID"),
        (
            {"retry_requested": True},
            "ENTRY_PRECHECK_RETRY_REPOST_OR_SECOND_POST_REQUESTED",
        ),
        (
            {"repost_requested": True},
            "ENTRY_PRECHECK_RETRY_REPOST_OR_SECOND_POST_REQUESTED",
        ),
        (
            {"second_post_requested": True},
            "ENTRY_PRECHECK_RETRY_REPOST_OR_SECOND_POST_REQUESTED",
        ),
        (
            {"settlement_post_requested": True},
            "ENTRY_PRECHECK_SETTLEMENT_POST_REQUESTED",
        ),
        ({"generic_close_requested": True}, "ENTRY_PRECHECK_GENERIC_CLOSE_REQUESTED"),
    ],
)
def test_each_gate_fails_closed(
    overrides: dict[str, object], expected_blocker: str
) -> None:
    summary = build_gmo_live_entry_actual_gate_precheck_summary(
        _all_safe_input(**overrides)
    )

    assert summary.precheck_ready is False
    assert expected_blocker in summary.blocked_reasons
    assert summary.entry_candidate_exists is False
    assert summary.actual_entry_POST_allowed is False
    assert (
        summary.recommended_next_step
        is not GmoEntryActualGatePrecheckNextStep
        .NEXT_STEP_ENTRY_POST_GATE_WITH_OPERATOR_CURRENT_TURN_CONFIRMATION
    )


def test_hold_label_is_safe_but_never_an_entry_candidate() -> None:
    summary = build_gmo_live_entry_actual_gate_precheck_summary(
        _all_safe_input(
            operator_entry_signal_safe_label=GmoEntryOperatorSignalSafeLabel.HOLD,
        )
    )

    assert summary.operator_entry_signal_safe_label is GmoEntryOperatorSignalSafeLabel.HOLD
    assert summary.precheck_ready is False
    assert summary.entry_candidate_exists is False
    assert (
        "ENTRY_PRECHECK_OPERATOR_SIGNAL_HOLD_NO_ENTRY_CANDIDATE"
        in summary.blocked_reasons
    )
    assert (
        summary.status
        is GmoEntryActualGatePrecheckStatus.ENTRY_PRECHECK_BLOCKED_BY_OPERATOR_SIGNAL
    )


def test_raw_operator_text_is_classified_unsafe_and_blocks() -> None:
    label = normalize_entry_operator_signal_safe_label("今すぐ買って")
    assert (
        label
        is GmoEntryOperatorSignalSafeLabel.OPERATOR_SIGNAL_UNSAFE_RAW_TEXT_PROVIDED
    )

    summary = build_gmo_live_entry_actual_gate_precheck_summary(
        _all_safe_input(operator_entry_signal_safe_label="今すぐ買って")
    )
    assert summary.precheck_ready is False
    assert "ENTRY_PRECHECK_OPERATOR_SIGNAL_UNSAFE_RAW_TEXT" in summary.blocked_reasons
    assert summary.entry_candidate_exists is False


def test_entry_sell_label_is_accepted_as_candidate_when_all_gates_pass() -> None:
    summary = build_gmo_live_entry_actual_gate_precheck_summary(
        _all_safe_input(
            operator_entry_signal_safe_label=GmoEntryOperatorSignalSafeLabel.ENTRY_SELL,
        )
    )
    assert summary.precheck_ready is True
    assert summary.entry_candidate_exists is True
    assert summary.actual_entry_POST_allowed is False


def test_operator_blockers_route_next_step_to_operator_confirmation_required() -> None:
    summary = build_gmo_live_entry_actual_gate_precheck_summary(
        _all_safe_input(operator_readiness_confirmed=False)
    )
    assert (
        summary.recommended_next_step
        is GmoEntryActualGatePrecheckNextStep
        .NEXT_STEP_ENTRY_ACTUAL_GATE_PRECHECK_OPERATOR_CONFIRMATION_REQUIRED
    )


def test_non_operator_blockers_route_next_step_to_resolve_blockers() -> None:
    summary = build_gmo_live_entry_actual_gate_precheck_summary(
        _all_safe_input(working_tree_clean_safe=False)
    )
    assert (
        summary.recommended_next_step
        is GmoEntryActualGatePrecheckNextStep
        .NEXT_STEP_RESOLVE_ENTRY_PRECHECK_BLOCKERS_NO_POST
    )


def test_classifier_returns_no_blockers_for_all_safe_input() -> None:
    assert classify_gmo_entry_actual_gate_precheck_blockers(_all_safe_input()) == ()


def test_input_has_no_current_turn_confirmation_field_to_bank() -> None:
    field_names = {field.name for field in fields(GmoEntryActualGatePrecheckInput)}
    assert not any("confirmation" in name for name in field_names)
    assert not any("current_turn" in name for name in field_names)


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_does_not_read_env_or_network_client() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "load_dotenv" not in text
    assert "httpx" not in text
    assert "requests" not in text


def test_module_keeps_actual_post_fail_closed_fields_hardcoded_false() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text
    assert "actual_entry_POST_allowed=False" in text
    assert "actual_entry_POST_allowed=True" not in text
    assert "ai_trade_decision_performed=False" in text
    assert "ai_trade_decision_performed=True" not in text
    assert "operator_confirmation_substituted=False" in text
    assert "operator_confirmation_substituted=True" not in text
    assert "operator_current_turn_exact_confirmation_still_required=True" in text
    assert "operator_current_turn_exact_confirmation_still_required=False" not in text
