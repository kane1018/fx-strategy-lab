"""Mocked Private API read-only client skeleton.

Phase 3B-1 intentionally has no HTTP implementation. Tests inject mocked payloads
through `response_provider`; otherwise every request fails closed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.private_api.auth import build_auth_headers
from app.private_api.errors import (
    PrivateApiAuthError,
    PrivateApiConnectionDisabledError,
    PrivateApiForbiddenEndpointError,
    PrivateApiResponseError,
)
from app.private_api.schemas import (
    AccountAssets,
    ActiveOrder,
    Execution,
    OpenPosition,
    PositionSummary,
    account_assets_from_api,
    active_order_from_api,
    execution_from_api,
    open_positions_from_api_data,
    position_summary_from_api,
    private_api_error_from_payload,
)

PRIVATE_API_BASE_URL = "https://forex-api.coin.z.com/private"

GET_ACCOUNT_ASSETS = "/private/v1/account/assets"
GET_ORDERS = "/private/v1/orders"
GET_ACTIVE_ORDERS = "/private/v1/activeOrders"
GET_EXECUTIONS = "/private/v1/executions"
GET_LATEST_EXECUTIONS = "/private/v1/latestExecutions"
GET_OPEN_POSITIONS = "/private/v1/openPositions"
GET_POSITION_SUMMARY = "/private/v1/positionSummary"

READ_ONLY_ENDPOINTS = frozenset(
    {
        ("GET", GET_ACCOUNT_ASSETS),
        ("GET", GET_ORDERS),
        ("GET", GET_ACTIVE_ORDERS),
        ("GET", GET_EXECUTIONS),
        ("GET", GET_LATEST_EXECUTIONS),
        ("GET", GET_OPEN_POSITIONS),
        ("GET", GET_POSITION_SUMMARY),
    }
)

FORBIDDEN_ENDPOINTS = frozenset(
    {
        ("POST", "/private/v1/speedOrder"),
        ("POST", "/private/v1/order"),
        ("POST", "/private/v1/ifdOrder"),
        ("POST", "/private/v1/ifoOrder"),
        ("POST", "/private/v1/changeOrder"),
        ("POST", "/private/v1/changeOcoOrder"),
        ("POST", "/private/v1/changeIfdOrder"),
        ("POST", "/private/v1/changeIfoOrder"),
        ("POST", "/private/v1/cancelOrders"),
        ("POST", "/private/v1/cancelBulkOrder"),
        ("POST", "/private/v1/closeOrder"),
        ("POST", "/private/v1/ws-auth"),
        ("PUT", "/private/v1/ws-auth"),
        ("DELETE", "/private/v1/ws-auth"),
    }
)


@dataclass(frozen=True)
class ReadOnlyRequest:
    method: str
    path: str
    params: Mapping[str, str] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)


MockResponseProvider = Callable[[ReadOnlyRequest], Mapping[str, Any]]


def is_readonly_endpoint(method: str, path: str) -> bool:
    return (method.upper(), path) in READ_ONLY_ENDPOINTS


def assert_readonly_endpoint(method: str, path: str) -> None:
    normalized = (method.upper(), path)
    if normalized in FORBIDDEN_ENDPOINTS:
        raise PrivateApiForbiddenEndpointError(f"forbidden Private API endpoint: {method} {path}")
    if normalized not in READ_ONLY_ENDPOINTS:
        raise PrivateApiForbiddenEndpointError(
            f"non-read-only Private API endpoint: {method} {path}"
        )


class PrivateReadonlyClient:
    """Read-only skeleton backed by injected mocked responses."""

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        timestamp_factory: Callable[[], str],
        response_provider: MockResponseProvider | None = None,
        network_enabled: bool = False,
    ) -> None:
        if not api_key:
            raise PrivateApiAuthError("api_key is required")
        if not api_secret:
            raise PrivateApiAuthError("api_secret is required")
        self._api_key = api_key
        self._api_secret = api_secret
        self._timestamp_factory = timestamp_factory
        self._response_provider = response_provider
        self.network_enabled = network_enabled

    def get_account_assets(self) -> AccountAssets:
        data = self._request_readonly(GET_ACCOUNT_ASSETS)
        if not isinstance(data, Mapping):
            raise PrivateApiResponseError("account assets data must be an object")
        return account_assets_from_api(data)

    def get_open_positions(self, *, symbol: str | None = None) -> list[OpenPosition]:
        data = self._request_readonly(GET_OPEN_POSITIONS, _optional_params(symbol=symbol))
        try:
            return open_positions_from_api_data(data)
        except ValueError as exc:
            raise PrivateApiResponseError(str(exc)) from exc

    def get_active_orders(self, *, symbol: str | None = None) -> list[ActiveOrder]:
        rows = self._request_readonly(GET_ACTIVE_ORDERS, _optional_params(symbol=symbol))
        return [active_order_from_api(row) for row in _ensure_rows(rows)]

    def get_orders(self, *, order_id: str | None = None) -> list[ActiveOrder]:
        rows = self._request_readonly(GET_ORDERS, _optional_params(orderId=order_id))
        return [active_order_from_api(row) for row in _ensure_rows(rows)]

    def get_executions(self, *, order_id: str | None = None) -> list[Execution]:
        rows = self._request_readonly(GET_EXECUTIONS, _optional_params(orderId=order_id))
        return [execution_from_api(row) for row in _ensure_rows(rows)]

    def get_latest_executions(self, *, symbol: str) -> list[Execution]:
        rows = self._request_readonly(GET_LATEST_EXECUTIONS, {"symbol": symbol})
        return [execution_from_api(row) for row in _ensure_rows(rows)]

    def get_position_summary(self, *, symbol: str | None = None) -> list[PositionSummary]:
        rows = self._request_readonly(GET_POSITION_SUMMARY, _optional_params(symbol=symbol))
        return [position_summary_from_api(row) for row in _ensure_rows(rows)]

    def _request_readonly(
        self,
        path: str,
        params: Mapping[str, str] | None = None,
    ) -> Any:
        method = "GET"
        assert_readonly_endpoint(method, path)
        timestamp = self._timestamp_factory()
        request = ReadOnlyRequest(
            method=method,
            path=path,
            params=params or {},
            headers=build_auth_headers(
                api_key=self._api_key,
                api_secret=self._api_secret,
                timestamp=timestamp,
                method=method,
                path=path,
            ),
        )
        if self._response_provider is None:
            raise PrivateApiConnectionDisabledError(
                "Private API connection is disabled in Phase 3B-1"
            )
        payload = self._response_provider(request)
        return _extract_data(payload)


def _extract_data(payload: Mapping[str, Any]) -> Any:
    status = payload.get("status")
    if status != 0:
        api_error = private_api_error_from_payload(payload)
        raise PrivateApiResponseError(
            f"Private API mocked response error: {api_error.code}",
            api_error=api_error,
        )
    return payload.get("data")


def _ensure_rows(data: Any) -> list[Mapping[str, Any]]:
    if data is None:
        return []
    if not isinstance(data, list):
        raise PrivateApiResponseError("response data must be a list")
    rows: list[Mapping[str, Any]] = []
    for row in data:
        if not isinstance(row, Mapping):
            raise PrivateApiResponseError("response row must be an object")
        rows.append(row)
    return rows


def _optional_params(**values: str | None) -> dict[str, str]:
    return {key: value for key, value in values.items() if value is not None}
