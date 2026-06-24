import pytest

from app.private_api.errors import (
    PrivateApiConnectionDisabledError,
    PrivateApiForbiddenEndpointError,
)
from app.private_api.readonly_client import (
    FORBIDDEN_ENDPOINTS,
    GET_ACCOUNT_ASSETS,
    GET_ACTIVE_ORDERS,
    GET_OPEN_POSITIONS,
    READ_ONLY_ENDPOINTS,
    PrivateReadonlyClient,
    ReadOnlyRequest,
    assert_readonly_endpoint,
    is_readonly_endpoint,
)


def _client(payloads: dict[str, object]) -> PrivateReadonlyClient:
    def provider(request: ReadOnlyRequest):
        return {"status": 0, "data": payloads[request.path]}

    return PrivateReadonlyClient(
        api_key="<API_KEY>",
        api_secret="<API_SECRET>",
        timestamp_factory=lambda: "1700000000000",
        response_provider=provider,
    )


def test_readonly_endpoint_whitelist_contains_phase_3b1_gets() -> None:
    assert ("GET", GET_ACCOUNT_ASSETS) in READ_ONLY_ENDPOINTS
    assert ("GET", GET_OPEN_POSITIONS) in READ_ONLY_ENDPOINTS
    assert ("GET", GET_ACTIVE_ORDERS) in READ_ONLY_ENDPOINTS
    assert is_readonly_endpoint("GET", GET_ACCOUNT_ASSETS)


def test_account_assets_open_positions_and_active_orders_use_mocked_payloads() -> None:
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
                }
            ],
            GET_ACTIVE_ORDERS: [
                {
                    "orderId": "ord-1",
                    "symbol": "USD_JPY",
                    "side": "SELL",
                    "orderType": "LIMIT",
                    "size": "100",
                    "price": "151.0",
                }
            ],
        }
    )

    assert client.get_account_assets().equity == 1000000
    assert client.get_open_positions()[0].position_id == "pos-1"
    assert client.get_active_orders()[0].order_id == "ord-1"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/private/v1/order"),
        ("POST", "/private/v1/speedOrder"),
        ("POST", "/private/v1/cancelOrders"),
        ("POST", "/private/v1/closeOrder"),
        ("PUT", "/private/v1/ws-auth"),
        ("DELETE", "/private/v1/ws-auth"),
    ],
)
def test_forbidden_endpoint_guard_rejects_non_readonly_paths(method: str, path: str) -> None:
    assert (method, path) in FORBIDDEN_ENDPOINTS
    with pytest.raises(PrivateApiForbiddenEndpointError):
        assert_readonly_endpoint(method, path)


def test_unknown_or_wrong_method_endpoint_is_rejected() -> None:
    with pytest.raises(PrivateApiForbiddenEndpointError):
        assert_readonly_endpoint("POST", GET_ACCOUNT_ASSETS)
    with pytest.raises(PrivateApiForbiddenEndpointError):
        assert_readonly_endpoint("GET", "/private/v1/unknown")


def test_connection_disabled_without_mocked_provider() -> None:
    client = PrivateReadonlyClient(
        api_key="<API_KEY>",
        api_secret="<API_SECRET>",
        timestamp_factory=lambda: "1700000000000",
    )

    with pytest.raises(PrivateApiConnectionDisabledError):
        client.get_account_assets()
