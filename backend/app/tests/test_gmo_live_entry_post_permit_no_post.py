"""No-POST tests for the ephemeral, single-use entry POST permit."""

from __future__ import annotations

import pathlib

import pytest

from app.services.gmo_live_entry_post_permit import (
    ENTRY_POST_PERMIT_SCOPE_ENTRY_ONLY,
    GmoEntryPostPermitScopeError,
    GmoEntryPostPermitStatus,
    assert_entry_only_permit_scope,
    build_gmo_entry_post_permit,
    consume_gmo_entry_post_permit,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_entry_post_permit.py"
)


def _granted():
    return build_gmo_entry_post_permit(
        operator_current_turn_exact_confirmation_present=True,
        operator_readiness_present=True,
        operator_signal_is_entry_buy_or_sell=True,
    )


def test_default_permit_is_denied_when_confirmation_missing() -> None:
    permit = build_gmo_entry_post_permit(
        operator_current_turn_exact_confirmation_present=False,
        operator_readiness_present=True,
        operator_signal_is_entry_buy_or_sell=True,
    )
    assert permit.permit_granted is False
    assert permit.usable_for_one_entry_post is False
    assert (
        permit.status
        is GmoEntryPostPermitStatus.PERMIT_DENIED_MISSING_CURRENT_TURN_CONFIRMATION
    )
    assert bool(permit) is False


def test_permit_denied_when_readiness_missing() -> None:
    permit = build_gmo_entry_post_permit(
        operator_current_turn_exact_confirmation_present=True,
        operator_readiness_present=False,
        operator_signal_is_entry_buy_or_sell=True,
    )
    assert permit.permit_granted is False
    assert (
        permit.status
        is GmoEntryPostPermitStatus.PERMIT_DENIED_MISSING_OPERATOR_READINESS
    )


def test_permit_denied_when_signal_is_not_entry() -> None:
    permit = build_gmo_entry_post_permit(
        operator_current_turn_exact_confirmation_present=True,
        operator_readiness_present=True,
        operator_signal_is_entry_buy_or_sell=False,
    )
    assert permit.permit_granted is False
    assert permit.status is GmoEntryPostPermitStatus.PERMIT_DENIED_SIGNAL_NOT_ENTRY


def test_permit_denied_in_retry_or_repost_context() -> None:
    permit = build_gmo_entry_post_permit(
        operator_current_turn_exact_confirmation_present=True,
        operator_readiness_present=True,
        operator_signal_is_entry_buy_or_sell=True,
        retry_or_repost_context=True,
    )
    assert permit.permit_granted is False
    assert (
        permit.status
        is GmoEntryPostPermitStatus.PERMIT_DENIED_RETRY_OR_REPOST_CONTEXT
    )


def test_granted_permit_is_entry_only_one_shot_and_never_allow_bridge() -> None:
    permit = _granted()
    assert permit.permit_granted is True
    assert permit.usable_for_one_entry_post is True
    assert permit.scope == ENTRY_POST_PERMIT_SCOPE_ENTRY_ONLY
    assert permit.one_post_max == 1
    assert permit.settlement_use_allowed is False
    assert permit.close_use_allowed is False
    assert permit.cancel_use_allowed is False
    assert permit.change_use_allowed is False
    assert permit.retry_use_allowed is False
    assert permit.repost_use_allowed is False
    assert permit.second_post_use_allowed is False
    assert permit.hard_guard_allow_resolved is False
    assert permit.storable is False
    assert permit.reusable is False
    assert bool(permit) is False


def test_consumed_permit_cannot_be_reused() -> None:
    permit = _granted()
    consumed = consume_gmo_entry_post_permit(permit)
    assert consumed.permit_granted is False
    assert consumed.consumed is True
    assert consumed.usable_for_one_entry_post is False
    # Consuming again stays denied (no second POST).
    again = consume_gmo_entry_post_permit(consumed)
    assert again.permit_granted is False
    assert again.usable_for_one_entry_post is False


@pytest.mark.parametrize(
    "scope",
    ["SETTLEMENT", "CLOSE", "closeOrder", "CANCEL", "cancelOrders", "CHANGE", "changeOrder"],
)
def test_entry_permit_scope_rejects_non_entry_scopes(scope: str) -> None:
    with pytest.raises(GmoEntryPostPermitScopeError):
        assert_entry_only_permit_scope(scope)


def test_entry_permit_scope_accepts_entry_only() -> None:
    assert_entry_only_permit_scope(ENTRY_POST_PERMIT_SCOPE_ENTRY_ONLY)


def test_module_has_no_allow_true_direct_write() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text
    assert "hard_guard_allow_resolved:bool=False" in text
    assert "hard_guard_allow_resolved=True" not in text


def test_module_does_not_read_env_or_network() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "httpx" not in text
    assert "app.live_verification" not in text
    assert "live_order_once" not in text
