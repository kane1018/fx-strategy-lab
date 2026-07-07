"""No-POST tests for the entry transport boundary (fake only)."""

from __future__ import annotations

import pathlib
from dataclasses import fields

import pytest

from app.services.gmo_live_entry_transport import (
    FakeEntryTransport,
    GmoEntryPostResultCategory,
    GmoEntryPostSanitizedPreview,
    GmoEntryPostStateMachineStatus,
    GmoEntryTransportError,
    ProductionEntryTransportNotImplemented,
    simulate_gmo_entry_post_once_fake_only,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_entry_transport.py"
)


def test_production_transport_is_fail_closed_not_implemented() -> None:
    transport = ProductionEntryTransportNotImplemented()
    assert transport.is_real_transport is True
    with pytest.raises(GmoEntryTransportError, match="not implemented"):
        transport.send_entry_order_sanitized()


def test_state_machine_refuses_real_transport() -> None:
    result = simulate_gmo_entry_post_once_fake_only(
        transport=ProductionEntryTransportNotImplemented(),
        permit_usable_for_one_entry_post=True,
    )
    assert result.fake_post_count == 0
    assert result.real_post_count == 0
    assert (
        result.status
        is GmoEntryPostStateMachineStatus
        .ENTRY_POST_BLOCKED_REAL_TRANSPORT_FORBIDDEN_IN_NO_POST
    )


def test_state_machine_blocks_when_permit_not_usable() -> None:
    result = simulate_gmo_entry_post_once_fake_only(
        transport=FakeEntryTransport(),
        permit_usable_for_one_entry_post=False,
    )
    assert result.fake_post_count == 0
    assert (
        result.status
        is GmoEntryPostStateMachineStatus.ENTRY_POST_BLOCKED_PERMIT_NOT_USABLE
    )


@pytest.mark.parametrize(
    ("category", "expected_next"),
    [
        (
            GmoEntryPostResultCategory.RESULT_ACCEPTED_SANITIZED,
            "POST_ENTRY_READ_ONLY_CONFIRMATION_NO_POST",
        ),
        (
            GmoEntryPostResultCategory.RESULT_REJECTED_SANITIZED,
            "REJECTED_SAFE_REVIEW_NO_POST",
        ),
        (
            GmoEntryPostResultCategory.RESULT_UNKNOWN_SANITIZED,
            "UNKNOWN_RESULT_SAFE_REVIEW_NO_POST",
        ),
    ],
)
def test_fake_post_runs_once_and_never_resends(
    category: GmoEntryPostResultCategory, expected_next: str
) -> None:
    result = simulate_gmo_entry_post_once_fake_only(
        transport=FakeEntryTransport(preset_result=category),
        permit_usable_for_one_entry_post=True,
    )
    assert result.fake_post_count == 1
    assert result.real_post_count == 0
    assert result.retry_performed is False
    assert result.repost_performed is False
    assert result.second_post_performed is False
    assert result.result_category is category
    assert result.next_recommended_step == expected_next
    assert bool(result) is False


def test_sanitized_preview_has_no_raw_or_id_or_value_fields() -> None:
    field_names = {field.name for field in fields(GmoEntryPostSanitizedPreview)}
    for banned in (
        "raw_request", "raw_response", "response_body", "request_body",
        "order_id", "position_id", "account_id", "trade_id",
        "avg_price", "fill_price", "pnl", "profit_loss", "signature_value",
        "header_value", "body_json",
    ):
        assert not any(banned in name for name in field_names)


def test_sanitized_preview_pins_forbidden_actions_false() -> None:
    preview = GmoEntryPostSanitizedPreview(
        operator_signal_safe_label="ENTRY_SELL",
        order_side_safe_label="SELL",
        symbol_safe_label="USD_JPY",
        execution_type_safe_label="MARKET",
        runtime_position_safe_status="NO_POSITION",
        position_count_safe=0,
        active_pending_safe_status="CLEAR",
        credential_presence_safe_boolean=True,
    )
    assert preview.entry_post_max_count == 1
    assert preview.retry is False
    assert preview.repost is False
    assert preview.second_post is False
    assert preview.settlement_post is False
    assert preview.generic_close is False
    assert preview.credential_value_exposed is False
    assert preview.raw_id_value_exposure is False
    assert bool(preview) is False


def test_transport_interface_has_no_settlement_or_close_method() -> None:
    assert not hasattr(FakeEntryTransport, "send_settlement_order_sanitized")
    assert not hasattr(FakeEntryTransport, "close_position")
    assert not hasattr(FakeEntryTransport, "settle_position")


def test_module_does_not_perform_real_http_or_read_env() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "httpx" not in text
    assert "requests" not in text
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "app.live_verification" not in text
    assert "live_order_once" not in text
    assert "closeOrder" not in text
    assert "settlePosition" not in text


def test_module_has_no_retry_repost_true_or_allow_true() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "retry_performed=True" not in text
    assert "repost_performed=True" not in text
    assert "second_post_performed=True" not in text
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text
