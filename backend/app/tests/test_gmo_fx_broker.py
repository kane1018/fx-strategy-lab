import httpx
import pytest

from app.brokers.gmo_fx_broker import (
    GmoFxBroker,
    GmoFxBrokerError,
    build_gmo_order_payload,
    gmo_dry_run_order,
    normalize_symbol,
)
from app.config import Settings
from app.schemas.trading import OrderRequest, RiskConfig, Side


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"gmo_fx_max_units": 100}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://forex-api.coin.z.com/public",
        transport=httpx.MockTransport(handler),
    )


def order(**overrides: object) -> OrderRequest:
    values: dict[str, object] = {
        "client_order_id": "GMO-DRYRUN-0001",
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


def test_normalize_symbol_variants_and_rejects_garbage() -> None:
    assert normalize_symbol("usd/jpy") == "USD_JPY"
    assert normalize_symbol("EUR-JPY") == "EUR_JPY"
    assert normalize_symbol("GBP_JPY") == "GBP_JPY"
    with pytest.raises(GmoFxBrokerError, match="シンボル"):
        normalize_symbol("NOTASYMBOL")


def test_public_ticker_price_and_spread() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/ticker"):
            return httpx.Response(
                200,
                json={
                    "status": 0,
                    "data": [
                        {
                            "symbol": "USD_JPY",
                            "ask": "150.010",
                            "bid": "149.990",
                            "timestamp": "2026-06-15T05:18:30.853Z",
                            "status": "OPEN",
                        }
                    ],
                    "responsetime": "2026-06-15T05:18:30.860Z",
                },
            )
        return httpx.Response(404, json={"status": 1, "messages": []})

    broker = GmoFxBroker(settings(), client=_client(handler))
    price = broker.current_price("USD_JPY")
    assert price.bid == 149.99
    assert price.ask == 150.01
    assert price.midpoint == pytest.approx(150.0)
    assert price.spread_pips == pytest.approx(2.0)  # 0.02 / 0.01 pip
    assert price.status == "OPEN"


def test_public_ticker_rejects_non_open_symbol() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": 0,
                "data": [
                    {
                        "symbol": "USD_JPY",
                        "ask": "150.010",
                        "bid": "149.990",
                        "timestamp": "2026-06-15T05:18:30.853Z",
                        "status": "CLOSE",
                    }
                ],
            },
        )

    broker = GmoFxBroker(settings(), client=_client(handler))
    with pytest.raises(GmoFxBrokerError, match="取引できません"):
        broker.current_price("USD_JPY")


def test_public_klines_are_parsed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "USD_JPY"
        assert request.url.params["interval"] == "5min"
        return httpx.Response(
            200,
            json={
                "status": 0,
                "data": [
                    {
                        "openTime": "1750000000000",
                        "open": "149.900",
                        "high": "150.100",
                        "low": "149.800",
                        "close": "150.050",
                    },
                    {
                        "openTime": "1750000300000",
                        "open": "150.050",
                        "high": "150.200",
                        "low": "150.000",
                        "close": "150.180",
                    },
                ],
            },
        )

    broker = GmoFxBroker(settings(), client=_client(handler))
    candles = broker.candles("USD_JPY", "M5", date="20260615")
    assert len(candles) == 2
    assert candles[-1].close == 150.18
    assert candles[0].high == 150.10


def test_connection_test_uses_public_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/status")
        return httpx.Response(200, json={"status": 0, "data": {"status": "OPEN"}})

    broker = GmoFxBroker(settings(), client=_client(handler))
    assert broker.connection_test() is True


def test_error_envelope_is_not_suppressed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": 1,
                "messages": [{"message_code": "ERR-5114", "message_string": "bad"}],
            },
        )

    broker = GmoFxBroker(settings(), client=_client(handler))
    with pytest.raises(GmoFxBrokerError, match="ERR-5114"):
        broker.service_status()


@pytest.mark.parametrize("mode", ["envelope", "http429"])
def test_rate_limit_is_surfaced(mode: str) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        if mode == "http429":
            return httpx.Response(429, json={"status": 1, "messages": []})
        return httpx.Response(
            200,
            json={"status": 1, "messages": [{"message_code": "ERR-5003"}]},
        )

    broker = GmoFxBroker(settings(), client=_client(handler))
    with pytest.raises(GmoFxBrokerError, match="rate limit"):
        broker.service_status()


def test_timeout_is_not_suppressed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated", request=request)

    broker = GmoFxBroker(settings(), client=_client(handler))
    with pytest.raises(GmoFxBrokerError, match="connection error"):
        broker.service_status()


def test_market_order_is_disabled_and_makes_no_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("market_order must not perform any HTTP request")

    broker = GmoFxBroker(settings(), client=_client(handler))
    with pytest.raises(GmoFxBrokerError, match="hard guard"):
        broker.market_order(order())


def test_dry_run_order_passes_riskmanager_without_network() -> None:
    result = gmo_dry_run_order(order(), RiskConfig(max_units=100), settings())
    assert result["accepted"] is True
    assert result["status"] == "dry_run"
    assert result["payload"] == {
        "symbol": "USD_JPY",
        "side": "BUY",
        "size": "100",
        "executionType": "MARKET",
    }
    assert result["stop_loss"] == 149.7
    assert result["take_profit"] == 150.6


def test_dry_run_order_is_blocked_when_riskmanager_rejects() -> None:
    # Units over the RiskManager max must be rejected, never turned into a payload.
    result = gmo_dry_run_order(order(units=100), RiskConfig(max_units=10), settings())
    assert result["accepted"] is False
    assert result["status"] == "risk_rejected"
    assert "最大取引数量を超過" in result["reasons"]


def test_order_payload_guard_rejects_oversized_units() -> None:
    with pytest.raises(GmoFxBrokerError, match="GMO_FX_MAX_UNITS"):
        build_gmo_order_payload(order(units=500), max_units=100)
