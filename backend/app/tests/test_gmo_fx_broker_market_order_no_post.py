"""No-POST tests for the GmoFxBroker.market_order() production-side skeleton.

This pins that market_order() is entry-only, builds its request via the pure
app.private_api.order_builders entry builder, and must pass the shared
real-broker-post hard guard before any transport could ever be attempted. No
production caller sets allow_real_broker_post=True; no real HTTP client is
ever touched by this method; nothing here uses real credentials, `.env`, or
the Step 6G controlled/simulation family.
"""

from __future__ import annotations

import inspect
import pathlib

import httpx
import pytest

from app.brokers.gmo_fx_broker import GmoFxBroker, GmoFxBrokerError
from app.config import Settings
from app.schemas.trading import OrderRequest, Side

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "brokers" / "gmo_fx_broker.py"

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


def _settings() -> Settings:
    return Settings(_env_file=None, gmo_fx_max_units=100)


def _refusing_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("market_order must never perform any HTTP request")

    return httpx.Client(
        base_url="https://forex-api.coin.z.com/public",
        transport=httpx.MockTransport(handler),
    )


def _order(**overrides: object) -> OrderRequest:
    values: dict[str, object] = {
        "client_order_id": "GMO-SKELETON-0001",
        "mode": "demo",
        "symbol": "USD_JPY",
        "side": Side.BUY,
        "units": 100,
        "current_price": 150.0,
        "stop_loss": 149.7,
        "take_profit": 150.6,
        "estimated_loss": 10,
        "api_connection_ok": True,
    }
    values.update(overrides)
    return OrderRequest(**values)


def test_gmo_fx_broker_is_importable() -> None:
    broker = GmoFxBroker(_settings(), client=_refusing_client())
    assert isinstance(broker, GmoFxBroker)


def test_gmo_fx_broker_module_does_not_import_live_verification() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text


def test_gmo_fx_broker_module_does_not_reference_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "live_order_once" not in text


def test_market_order_denied_by_default_hard_guard_makes_no_http_call() -> None:
    broker = GmoFxBroker(_settings(), client=_refusing_client())
    with pytest.raises(GmoFxBrokerError, match="hard guard"):
        broker.market_order(_order())


@pytest.mark.parametrize("allow_value", [False, None, 0, "true"])
def test_market_order_denied_for_any_non_true_allow_value(allow_value: object) -> None:
    broker = GmoFxBroker(_settings(), client=_refusing_client())
    broker._allow_real_broker_post = allow_value  # type: ignore[assignment]
    with pytest.raises(GmoFxBrokerError, match="hard guard"):
        broker.market_order(_order())


def test_market_order_allow_true_still_stops_at_missing_transport() -> None:
    """Even a future caller passing allow=True must not reach a real
    network call in this Step: transport is simply not implemented yet.
    """
    broker = GmoFxBroker(_settings(), client=_refusing_client(), allow_real_broker_post=True)
    with pytest.raises(GmoFxBrokerError, match="not implemented"):
        broker.market_order(_order())


def test_market_order_uses_entry_builder_not_settlement() -> None:
    import app.brokers.gmo_fx_broker as gmo_fx_broker_module

    calls: list[str] = []
    original = gmo_fx_broker_module.build_gmo_fx_entry_request_plan

    def spy(*args: object, **kwargs: object):
        calls.append("entry_builder_called")
        return original(*args, **kwargs)

    gmo_fx_broker_module.build_gmo_fx_entry_request_plan = spy
    try:
        broker = GmoFxBroker(_settings(), client=_refusing_client())
        with pytest.raises(GmoFxBrokerError):
            broker.market_order(_order())
    finally:
        gmo_fx_broker_module.build_gmo_fx_entry_request_plan = original

    assert calls == ["entry_builder_called"]


def test_market_order_does_not_reference_settlement_or_generic_close() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    start = text.index("def market_order")
    next_method_offset = text.find("\n    def ", start + len("def market_order"))
    end = next_method_offset if next_method_offset != -1 else len(text)
    market_order_source = text[start:end]
    forbidden_terms = (
        "closeOrder",
        "settlement",
        "settlePosition",
        "close_position",
        "opposite",
    )
    for term in forbidden_terms:
        assert term.lower() not in market_order_source.lower(), (
            f"market_order() must not reference '{term}'"
        )


def test_market_order_signature_never_accepts_credential_parameters() -> None:
    signature = inspect.signature(GmoFxBroker.market_order)
    forbidden_names = {"api_key", "api_secret", "credential", "credentials", "signature"}
    overlap = set(signature.parameters) & forbidden_names
    assert overlap == set()

    init_signature = inspect.signature(GmoFxBroker.__init__)
    init_overlap = set(init_signature.parameters) & forbidden_names
    assert init_overlap == set()


def test_gmo_fx_broker_module_does_not_read_env_directly() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "load_dotenv" not in text


def test_no_production_allow_true_wiring_in_module() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text


def test_error_messages_never_expose_sentinel_values() -> None:
    broker = GmoFxBroker(_settings(), client=_refusing_client())
    with pytest.raises(GmoFxBrokerError) as exc_info:
        broker.market_order(_order(client_order_id="ORDER_ID_SHOULD_NOT_SURFACE"))
    rendered = str(exc_info.value)
    for sentinel in FORBIDDEN_SENTINELS:
        assert sentinel not in rendered
