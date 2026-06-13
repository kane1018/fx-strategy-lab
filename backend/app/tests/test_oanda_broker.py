from datetime import UTC, datetime

import httpx
import pytest

from app.brokers.oanda_broker import OandaBroker, OandaBrokerError
from app.config import Settings
from app.schemas.trading import OrderRequest, Side


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "OANDA_ENV": "practice",
        "oanda_api_url": "https://api-fxpractice.oanda.com",
        "oanda_api_token": "test-token",
        "oanda_account_id": "test-account",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_oanda_broker_rejects_missing_credentials_and_non_practice_url() -> None:
    with pytest.raises(OandaBrokerError, match="OANDA_API_TOKEN"):
        OandaBroker(settings(oanda_api_token=None))
    with pytest.raises(OandaBrokerError, match="OANDA_ACCOUNT_ID"):
        OandaBroker(settings(oanda_account_id=None))
    with pytest.raises(OandaBrokerError, match="practice以外"):
        OandaBroker(settings(oanda_api_url="https://example-practice.invalid"))


def test_oanda_practice_price_order_fill_position_and_close() -> None:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/summary"):
            return httpx.Response(
                200,
                json={
                    "account": {
                        "balance": "100000",
                        "NAV": "100100",
                        "currency": "JPY",
                        "openPositionCount": "0",
                    }
                },
            )
        if path.endswith("/pricing"):
            return httpx.Response(
                200,
                json={
                    "prices": [
                        {
                            "status": "tradeable",
                            "closeoutBid": "149.990",
                            "closeoutAsk": "150.010",
                            "time": now,
                            "quoteHomeConversionFactors": {
                                "positiveUnits": "0.00667",
                                "negativeUnits": "0.00668",
                            },
                        }
                    ]
                },
            )
        if path.endswith("/openPositions"):
            return httpx.Response(200, json={"positions": []})
        if path.endswith("/orders"):
            return httpx.Response(
                201,
                json={
                    "orderCreateTransaction": {"id": "100"},
                    "orderFillTransaction": {"id": "101", "orderID": "100"},
                },
            )
        if path.endswith("/transactions/101"):
            return httpx.Response(
                200,
                json={
                    "transaction": {
                        "id": "101",
                        "type": "ORDER_FILL",
                        "time": now,
                        "units": "100",
                        "tradeOpened": {"tradeID": "200", "price": "150.012"},
                    }
                },
            )
        if path.endswith("/positions/USD_JPY/close"):
            return httpx.Response(
                200,
                json={
                    "longOrderCreateTransaction": {"id": "102"},
                    "longOrderFillTransaction": {"id": "103", "orderID": "102"},
                },
            )
        if path.endswith("/transactions/103"):
            return httpx.Response(
                200,
                json={
                    "transaction": {
                        "id": "103",
                        "type": "ORDER_FILL",
                        "time": now,
                        "units": "-100",
                        "pl": "12.5",
                        "financing": "-0.2",
                        "commission": "0.1",
                        "halfSpreadCost": "0.3",
                        "tradesClosed": [
                            {
                                "tradeID": "200",
                                "price": "150.020",
                                "realizedPL": "12.5",
                            }
                        ],
                    }
                },
            )
        if path.endswith("/trades/200"):
            return httpx.Response(
                200,
                json={
                    "trade": {
                        "id": "200",
                        "state": "CLOSED",
                        "averageClosePrice": "150.020",
                        "realizedPL": "12.5",
                        "financing": "-0.2",
                        "closeTime": now,
                        "closingTransactionIDs": ["103"],
                    }
                },
            )
        return httpx.Response(404, json={"errorMessage": "not found"})

    client = httpx.Client(
        base_url="https://api-fxpractice.oanda.com",
        transport=httpx.MockTransport(handler),
    )
    broker = OandaBroker(settings(), client=client)
    account = broker.account_summary()
    price = broker.current_price("USD_JPY")
    order = broker.market_order(
        OrderRequest(
            client_order_id="PRACTICE-ORDER-1",
            mode="practice",
            symbol="USD_JPY",
            side=Side.BUY,
            units=100,
            current_price=price.ask,
            stop_loss=149.7,
            take_profit=150.6,
            estimated_loss=10,
            api_connection_ok=True,
        )
    )
    closed = broker.close_position("USD_JPY", "buy")
    summary = broker.closed_trade_summary("200")

    assert account.balance == 100000
    assert price.ask == 150.01
    assert order.fill_transaction_id == "101"
    assert order.trade_id == "200"
    assert closed.status == "closed"
    assert closed.fill_transaction_id == "103"
    assert closed.realized_pnl == pytest.approx(12.2)
    assert summary["realized_pnl"] == pytest.approx(12.2)


@pytest.mark.parametrize("status_code", [401, 403, 404, 429])
def test_oanda_http_errors_are_not_suppressed(status_code: int) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"errorMessage": f"simulated-{status_code}"},
        )

    broker = OandaBroker(
        settings(),
        client=httpx.Client(
            base_url="https://api-fxpractice.oanda.com",
            transport=httpx.MockTransport(handler),
        ),
    )
    with pytest.raises(OandaBrokerError, match=str(status_code)):
        broker.account_summary()


def test_oanda_timeout_is_not_suppressed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated", request=request)

    broker = OandaBroker(
        settings(),
        client=httpx.Client(
            base_url="https://api-fxpractice.oanda.com",
            transport=httpx.MockTransport(handler),
        ),
    )
    with pytest.raises(OandaBrokerError, match="connection error"):
        broker.account_summary()
