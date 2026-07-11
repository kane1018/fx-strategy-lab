"""No-POST tests for the pure GMO FX Private API order/settlement builders.

These builders never perform HTTP requests, never accept credential values,
never read `.env`, and never import `app.live_verification` or
`live_order_once`. Only synthetic fixture values are used; nothing here is a
real credential, ID, quantity, or price.
"""

from __future__ import annotations

import inspect
import json
import pathlib

import pytest

from app.private_api.order_builders import (
    GMO_FX_ENTRY_ORDER_METHOD,
    GMO_FX_ENTRY_ORDER_PATH,
    GMO_FX_IFDOCO_ORDER_PATH,
    GMO_FX_OFFICIAL_SETTLEMENT_METHOD,
    GMO_FX_OFFICIAL_SETTLEMENT_PATH,
    REQUEST_KIND_ENTRY,
    REQUEST_KIND_IFDOCO_PROTECTED_ENTRY,
    REQUEST_KIND_OFFICIAL_SETTLEMENT,
    GmoFxEntryOrderBody,
    GmoFxOfficialSettlementBody,
    GmoFxOrderBuilderError,
    GmoFxOrderSide,
    build_gmo_fx_entry_order_body,
    build_gmo_fx_entry_request_plan,
    build_gmo_fx_ifdoco_request_plan,
    build_gmo_fx_official_settlement_body,
    build_gmo_fx_official_settlement_request_plan,
    summarize_gmo_fx_private_request_plan,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "private_api" / "order_builders.py"
)

FIXTURE_SYMBOL = "USD_JPY"
FIXTURE_SIZE = "100"

FORBIDDEN_SENTINELS = (
    "RAW_RESPONSE_SHOULD_NOT_SURFACE",
    "BROKER_RESPONSE_SHOULD_NOT_SURFACE",
    "ACCOUNT_ID_SHOULD_NOT_SURFACE",
    "ORDER_ID_SHOULD_NOT_SURFACE",
    "POSITION_ID_SHOULD_NOT_SURFACE",
    "TRADE_ID_SHOULD_NOT_SURFACE",
    "QUANTITY_VALUE_SHOULD_NOT_SURFACE",
    "PRICE_VALUE_SHOULD_NOT_SURFACE",
    "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE",
    "SIGNATURE_VALUE_SHOULD_NOT_SURFACE",
    "HEADERS_VALUE_SHOULD_NOT_SURFACE",
)


def test_entry_body_has_no_settlement_only_fields() -> None:
    body = build_gmo_fx_entry_order_body(symbol=FIXTURE_SYMBOL, side="BUY", size=FIXTURE_SIZE)
    assert isinstance(body, GmoFxEntryOrderBody)
    field_names = set(GmoFxEntryOrderBody.model_fields)
    assert field_names == {"symbol", "side", "size", "executionType"}
    assert "settlePosition" not in field_names
    assert "position_specific_settlement_id" not in field_names


def test_settlement_body_targets_dedicated_route_not_generic_order() -> None:
    assert GMO_FX_OFFICIAL_SETTLEMENT_PATH != GMO_FX_ENTRY_ORDER_PATH
    assert GMO_FX_OFFICIAL_SETTLEMENT_PATH == "/private/v1/closeOrder"
    assert GMO_FX_ENTRY_ORDER_PATH == "/private/v1/order"
    body = build_gmo_fx_official_settlement_body(
        symbol=FIXTURE_SYMBOL, side="SELL", size=FIXTURE_SIZE,
    )
    assert isinstance(body, GmoFxOfficialSettlementBody)
    field_names = set(GmoFxOfficialSettlementBody.model_fields)
    assert "settlePosition" not in field_names, (
        "settlement body must never carry a position-specific field"
    )


def test_settlement_rejects_size_and_position_specific_together() -> None:
    with pytest.raises(GmoFxOrderBuilderError, match="mutually exclusive"):
        build_gmo_fx_official_settlement_body(
            symbol=FIXTURE_SYMBOL,
            side="SELL",
            size=FIXTURE_SIZE,
            position_specific_settlement_id="SYNTHETIC_FIXTURE_ID",
        )


def test_settlement_rejects_position_specific_alone_as_not_ready() -> None:
    with pytest.raises(GmoFxOrderBuilderError, match="not actual-path-enabled"):
        build_gmo_fx_official_settlement_body(
            symbol=FIXTURE_SYMBOL,
            side="SELL",
            position_specific_settlement_id="SYNTHETIC_FIXTURE_ID",
        )


def test_settlement_position_specific_id_never_appears_in_error_text() -> None:
    sentinel = "POSITION_ID_SHOULD_NOT_SURFACE"
    with pytest.raises(GmoFxOrderBuilderError) as exc_info:
        build_gmo_fx_official_settlement_body(
            symbol=FIXTURE_SYMBOL,
            side="SELL",
            position_specific_settlement_id=sentinel,
        )
    assert sentinel not in str(exc_info.value)


def test_settlement_requires_size_when_nothing_else_given() -> None:
    with pytest.raises(GmoFxOrderBuilderError, match="size is required"):
        build_gmo_fx_official_settlement_body(symbol=FIXTURE_SYMBOL, side="SELL")


def test_side_enum_and_string_input_both_accepted() -> None:
    body_from_enum = build_gmo_fx_entry_order_body(
        symbol=FIXTURE_SYMBOL, side=GmoFxOrderSide.BUY, size=FIXTURE_SIZE,
    )
    body_from_str = build_gmo_fx_entry_order_body(
        symbol=FIXTURE_SYMBOL, side="buy", size=FIXTURE_SIZE,
    )
    assert body_from_enum.side == body_from_str.side == "BUY"


def test_invalid_side_rejected() -> None:
    with pytest.raises(GmoFxOrderBuilderError):
        build_gmo_fx_entry_order_body(symbol=FIXTURE_SYMBOL, side="HOLD", size=FIXTURE_SIZE)


def test_request_plan_has_method_path_body_json_and_kind() -> None:
    plan = build_gmo_fx_entry_request_plan(symbol=FIXTURE_SYMBOL, side="BUY", size=FIXTURE_SIZE)
    assert plan.request_kind == REQUEST_KIND_ENTRY
    assert plan.method == GMO_FX_ENTRY_ORDER_METHOD == "POST"
    assert plan.path == GMO_FX_ENTRY_ORDER_PATH
    parsed = json.loads(plan.body_json)
    assert parsed["symbol"] == FIXTURE_SYMBOL
    assert parsed["side"] == "BUY"

    settlement_plan = build_gmo_fx_official_settlement_request_plan(
        symbol=FIXTURE_SYMBOL, side="SELL", size=FIXTURE_SIZE,
    )
    assert settlement_plan.request_kind == REQUEST_KIND_OFFICIAL_SETTLEMENT
    assert settlement_plan.method == GMO_FX_OFFICIAL_SETTLEMENT_METHOD == "POST"
    assert settlement_plan.path == GMO_FX_OFFICIAL_SETTLEMENT_PATH
    assert settlement_plan.path != plan.path

    ifdoco_plan = build_gmo_fx_ifdoco_request_plan(
        symbol=FIXTURE_SYMBOL,
        first_side="BUY",
        first_size=FIXTURE_SIZE,
        first_price="150.1",
        second_size=FIXTURE_SIZE,
        second_limit_price="151.0",
        second_stop_price="149.0",
        client_order_id="SYNTHETIC123",
    )
    assert ifdoco_plan.request_kind == REQUEST_KIND_IFDOCO_PROTECTED_ENTRY
    assert ifdoco_plan.path == GMO_FX_IFDOCO_ORDER_PATH == "/private/v1/ifoOrder"
    assert ifdoco_plan.path not in {plan.path, settlement_plan.path}


def test_safe_summary_never_includes_body_content_or_sensitive_flags() -> None:
    plan = build_gmo_fx_entry_request_plan(symbol=FIXTURE_SYMBOL, side="BUY", size=FIXTURE_SIZE)
    summary = summarize_gmo_fx_private_request_plan(plan)
    assert summary.request_kind == REQUEST_KIND_ENTRY
    assert summary.method == plan.method
    assert summary.path == plan.path
    assert summary.body_field_count == len(json.loads(plan.body_json))
    assert summary.credential_value_included is False
    assert summary.signature_included is False
    assert summary.headers_value_included is False
    rendered = repr(summary)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in rendered


def test_builder_functions_never_accept_credential_parameters() -> None:
    from app.private_api import order_builders

    builder_functions = (
        order_builders.build_gmo_fx_entry_order_body,
        order_builders.build_gmo_fx_ifdoco_order_body,
        order_builders.build_gmo_fx_official_settlement_body,
        order_builders.build_gmo_fx_entry_request_plan,
        order_builders.build_gmo_fx_ifdoco_request_plan,
        order_builders.build_gmo_fx_official_settlement_request_plan,
        order_builders.summarize_gmo_fx_private_request_plan,
    )
    forbidden_param_names = {
        "api_key",
        "api_secret",
        "credential",
        "credentials",
        "signature",
        "headers",
    }
    for func in builder_functions:
        params = set(inspect.signature(func).parameters)
        overlap = params & forbidden_param_names
        assert overlap == set(), f"{func.__name__} accepts credential-like params: {overlap}"


def test_module_does_not_read_environment_or_call_http_client() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "httpx" not in text
    assert "requests" not in text
    assert ".env" not in text


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_does_not_wire_allow_true() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text


def test_module_never_calls_auth_signing_functions_directly() -> None:
    """This module builds signing-ready plans but never signs anything
    itself; signing is the future real transport boundary's job."""
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "create_signature(" not in text
    assert "build_auth_headers(" not in text
