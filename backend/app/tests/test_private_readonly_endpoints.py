from decimal import Decimal

import pytest

from app.private_api.readonly_client import (
    GET_ACCOUNT_ASSETS,
    GET_ACTIVE_ORDERS,
    GET_EXECUTIONS,
    GET_LATEST_EXECUTIONS,
    GET_OPEN_POSITIONS,
    GET_ORDERS,
    GET_POSITION_SUMMARY,
    READ_ONLY_ENDPOINTS,
    PrivateReadonlyClient,
    ReadOnlyRequest,
)


def _client(payloads: dict[str, object], calls: list[ReadOnlyRequest]) -> PrivateReadonlyClient:
    def provider(request: ReadOnlyRequest):
        calls.append(request)
        return {"status": 0, "data": payloads[request.path]}

    return PrivateReadonlyClient(
        api_key="<API_KEY>",
        api_secret="<API_SECRET>",
        timestamp_factory=lambda: "1700000000000",
        response_provider=provider,
    )


@pytest.mark.parametrize(
    "path",
    [
        GET_ACCOUNT_ASSETS,
        GET_OPEN_POSITIONS,
        GET_ACTIVE_ORDERS,
        GET_ORDERS,
        GET_EXECUTIONS,
        GET_LATEST_EXECUTIONS,
        GET_POSITION_SUMMARY,
    ],
)
def test_phase_3b_readonly_get_endpoints_are_whitelisted(path: str) -> None:
    assert ("GET", path) in READ_ONLY_ENDPOINTS


def test_all_readonly_endpoints_use_mocked_provider_payloads() -> None:
    calls: list[ReadOnlyRequest] = []
    client = _client(
        {
            GET_ACCOUNT_ASSETS: {"actualAmount": "1000000", "availableAmount": "900000"},
            GET_OPEN_POSITIONS: [
                {
                    "positionId": "pos-1",
                    "symbol": "USD_JPY",
                    "side": "BUY",
                    "size": "100",
                    "price": "150.1",
                    "lossGain": "12.3",
                }
            ],
            GET_ACTIVE_ORDERS: [
                {
                    "orderId": "active-1",
                    "symbol": "USD_JPY",
                    "side": "SELL",
                    "orderType": "LIMIT",
                    "size": "200",
                    "price": "151.0",
                    "status": "ORDERED",
                }
            ],
            GET_ORDERS: [
                {
                    "rootOrderId": "order-1",
                    "symbol": "USD_JPY",
                    "side": "BUY",
                    "executionType": "MARKET",
                    "orderSize": "300",
                    "status": "EXECUTED",
                }
            ],
            GET_EXECUTIONS: [
                {
                    "executionId": "exec-1",
                    "orderId": "order-1",
                    "symbol": "USD_JPY",
                    "side": "BUY",
                    "executionSize": "300",
                    "executionPrice": "150.2",
                }
            ],
            GET_LATEST_EXECUTIONS: [
                {
                    "executionId": "latest-1",
                    "rootOrderId": "order-2",
                    "symbol": "USD_JPY",
                    "side": "SELL",
                    "size": "100",
                    "price": "150.4",
                }
            ],
            GET_POSITION_SUMMARY: [
                {
                    "symbol": "USD_JPY",
                    "side": "BUY",
                    "sumPositionQuantity": "400",
                    "averagePrice": "150.3",
                    "sumLossGain": "456.7",
                }
            ],
        },
        calls,
    )

    assert client.get_account_assets().equity == Decimal("1000000")
    assert client.get_open_positions(symbol="USD_JPY")[0].position_id == "pos-1"
    assert client.get_active_orders(symbol="USD_JPY")[0].order_id == "active-1"
    assert client.get_orders(order_id="order-1")[0].order_id == "order-1"
    assert client.get_executions(order_id="order-1")[0].execution_id == "exec-1"
    assert client.get_latest_executions(symbol="USD_JPY")[0].execution_id == "latest-1"
    summary = client.get_position_summary(symbol="USD_JPY")[0]
    assert summary.size == Decimal("400")
    assert summary.profit_loss == Decimal("456.7")

    assert [(call.method, call.path) for call in calls] == [
        ("GET", GET_ACCOUNT_ASSETS),
        ("GET", GET_OPEN_POSITIONS),
        ("GET", GET_ACTIVE_ORDERS),
        ("GET", GET_ORDERS),
        ("GET", GET_EXECUTIONS),
        ("GET", GET_LATEST_EXECUTIONS),
        ("GET", GET_POSITION_SUMMARY),
    ]
    assert calls[1].params == {"symbol": "USD_JPY"}
    assert calls[3].params == {"orderId": "order-1"}
    assert calls[5].params == {"symbol": "USD_JPY"}


def test_empty_list_payloads_are_safe_for_collection_endpoints() -> None:
    calls: list[ReadOnlyRequest] = []
    client = _client(
        {
            GET_OPEN_POSITIONS: [],
            GET_ACTIVE_ORDERS: [],
            GET_ORDERS: [],
            GET_EXECUTIONS: [],
            GET_LATEST_EXECUTIONS: [],
            GET_POSITION_SUMMARY: [],
        },
        calls,
    )

    assert client.get_open_positions() == []
    assert client.get_active_orders() == []
    assert client.get_orders() == []
    assert client.get_executions() == []
    assert client.get_latest_executions(symbol="USD_JPY") == []
    assert client.get_position_summary() == []
    assert len(calls) == 6


def test_missing_optional_fields_are_sanitized_without_raw_field_retention() -> None:
    calls: list[ReadOnlyRequest] = []
    client = _client(
        {
            GET_ACTIVE_ORDERS: [
                {
                    "orderId": "active-min",
                    "symbol": "USD_JPY",
                    "API-KEY": "<API_KEY>",
                    "API-SIGN": "<SIGNATURE>",
                }
            ],
            GET_EXECUTIONS: [
                {
                    "executionId": "exec-min",
                    "symbol": "USD_JPY",
                    "API-KEY": "<API_KEY>",
                    "API-SIGN": "<SIGNATURE>",
                }
            ],
            GET_POSITION_SUMMARY: [{"symbol": "USD_JPY", "API-SIGN": "<SIGNATURE>"}],
        },
        calls,
    )

    active = client.get_active_orders()[0].model_dump()
    execution = client.get_executions()[0].model_dump()
    summary = client.get_position_summary()[0].model_dump()

    assert active["order_id"] == "active-min"
    assert active["side"] is None
    assert execution["execution_id"] == "exec-min"
    assert execution["price"] is None
    assert summary["symbol"] == "USD_JPY"
    for dumped in (active, execution, summary):
        assert "API-KEY" not in dumped
        assert "API-SIGN" not in dumped
