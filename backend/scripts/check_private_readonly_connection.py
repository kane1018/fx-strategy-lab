"""Phase 3B-4 local GMO FX Private API read-only connection check."""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from app.private_api.auth import build_auth_headers
from app.private_api.errors import PrivateApiResponseError
from app.private_api.readonly_client import (
    GET_ACCOUNT_ASSETS,
    GET_ACTIVE_ORDERS,
    GET_OPEN_POSITIONS,
    PRIVATE_API_BASE_URL,
    assert_readonly_endpoint,
)
from app.private_api.schemas import (
    account_assets_from_api,
    active_order_from_api,
    open_position_from_api,
    private_api_error_from_payload,
)

DEFAULT_SYMBOL = "USD_JPY"
REQUEST_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class SanitizedConnectionSummary:
    connection_result: str
    account_assets: str
    open_positions: str
    active_orders: str
    account_assets_count: int = 0
    open_positions_count: int = 0
    active_orders_count: int = 0
    has_open_positions: bool = False
    has_active_orders: bool = False
    raw_response_saved: bool = False
    headers_saved: bool = False
    credentials_printed: bool = False

    def to_stdout_lines(self) -> list[str]:
        return [
            f"connection_result: {self.connection_result}",
            f"account_assets: {self.account_assets}",
            f"open_positions: {self.open_positions}",
            f"active_orders: {self.active_orders}",
            f"account_assets_count: {self.account_assets_count}",
            f"open_positions_count: {self.open_positions_count}",
            f"active_orders_count: {self.active_orders_count}",
            f"has_open_positions: {_bool_text(self.has_open_positions)}",
            f"has_active_orders: {_bool_text(self.has_active_orders)}",
            f"raw_response_saved: {_bool_text(self.raw_response_saved)}",
            f"headers_saved: {_bool_text(self.headers_saved)}",
            f"credentials_printed: {_bool_text(self.credentials_printed)}",
        ]


def run_connection_check(
    *,
    api_key: str,
    api_secret: str,
    symbol: str = DEFAULT_SYMBOL,
    http_client: httpx.Client | None = None,
    timestamp_factory: Callable[[], str] | None = None,
) -> SanitizedConnectionSummary:
    """Run one manual read-only check against the three Phase 3B-4 endpoints."""
    owns_client = http_client is None
    client = http_client or httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)
    timestamp = timestamp_factory or _timestamp_ms
    summary = SanitizedConnectionSummary(
        connection_result="failure",
        account_assets="failure",
        open_positions="not_run",
        active_orders="not_run",
    )

    try:
        account_payload = _get_private_api_data(
            client=client,
            api_key=api_key,
            api_secret=api_secret,
            path=GET_ACCOUNT_ASSETS,
            params={},
            timestamp_factory=timestamp,
        )
        if not isinstance(account_payload, Mapping):
            raise PrivateApiResponseError("account assets data must be an object")
        account_assets_from_api(account_payload)
        summary = SanitizedConnectionSummary(
            connection_result="failure",
            account_assets="success",
            open_positions="failure",
            active_orders="not_run",
            account_assets_count=1,
        )

        open_position_payload = _get_private_api_data(
            client=client,
            api_key=api_key,
            api_secret=api_secret,
            path=GET_OPEN_POSITIONS,
            params={"symbol": symbol},
            timestamp_factory=timestamp,
        )
        open_positions = [
            open_position_from_api(row) for row in _ensure_rows(open_position_payload)
        ]
        summary = SanitizedConnectionSummary(
            connection_result="failure",
            account_assets="success",
            open_positions="success",
            active_orders="failure",
            account_assets_count=1,
            open_positions_count=len(open_positions),
            has_open_positions=bool(open_positions),
        )

        active_order_payload = _get_private_api_data(
            client=client,
            api_key=api_key,
            api_secret=api_secret,
            path=GET_ACTIVE_ORDERS,
            params={"symbol": symbol},
            timestamp_factory=timestamp,
        )
        active_orders = [active_order_from_api(row) for row in _ensure_rows(active_order_payload)]
        return SanitizedConnectionSummary(
            connection_result="success",
            account_assets="success",
            open_positions="success",
            active_orders="success",
            account_assets_count=1,
            open_positions_count=len(open_positions),
            active_orders_count=len(active_orders),
            has_open_positions=bool(open_positions),
            has_active_orders=bool(active_orders),
        )
    except (PrivateApiResponseError, httpx.HTTPError, ValueError):
        return summary
    finally:
        if owns_client:
            client.close()


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[..., SanitizedConnectionSummary] = run_connection_check,
) -> int:
    args = _parse_args(argv)
    if not args.confirm_readonly:
        _print_summary(_not_run_summary(connection_result="failure"))
        return 2

    api_key = os.environ.get("GMO_FX_API_KEY")
    api_secret = os.environ.get("GMO_FX_API_SECRET")
    if not api_key or not api_secret:
        _print_summary(_not_run_summary(connection_result="failure"))
        return 2

    summary = runner(api_key=api_key, api_secret=api_secret, symbol=args.symbol)
    _print_summary(summary)
    return 0 if summary.connection_result == "success" else 1


def _get_private_api_data(
    *,
    client: httpx.Client,
    api_key: str,
    api_secret: str,
    path: str,
    params: Mapping[str, str],
    timestamp_factory: Callable[[], str],
) -> Any:
    method = "GET"
    assert_readonly_endpoint(method, path)
    response = client.get(
        _url_for_path(path),
        params=params,
        headers=build_auth_headers(
            api_key=api_key,
            api_secret=api_secret,
            timestamp=timestamp_factory(),
            method=method,
            path=_signing_path_for_endpoint(path),
        ),
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise PrivateApiResponseError("Private API response was not JSON") from exc
    if not isinstance(payload, Mapping):
        raise PrivateApiResponseError("Private API response must be an object")
    if response.status_code >= 400 or payload.get("status") != 0:
        api_error = private_api_error_from_payload(payload)
        raise PrivateApiResponseError(
            f"Private API sanitized response error: {api_error.code}",
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


def _not_run_summary(*, connection_result: str) -> SanitizedConnectionSummary:
    return SanitizedConnectionSummary(
        connection_result=connection_result,
        account_assets="not_run",
        open_positions="not_run",
        active_orders="not_run",
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local-only Phase 3B-4 Private API read-only connection check."
    )
    parser.add_argument(
        "--confirm-readonly",
        action="store_true",
        help="required explicit confirmation for the local read-only connection check",
    )
    parser.add_argument(
        "--symbol",
        default=DEFAULT_SYMBOL,
        choices=[DEFAULT_SYMBOL],
        help="symbol parameter for read-only collection endpoints",
    )
    return parser.parse_args(argv)


def _print_summary(summary: SanitizedConnectionSummary) -> None:
    print("\n".join(summary.to_stdout_lines()))


def _url_for_path(path: str) -> str:
    return f"{PRIVATE_API_BASE_URL.removesuffix('/private')}{path}"


def _signing_path_for_endpoint(path: str) -> str:
    if path.startswith("/private/v1/"):
        return path.removeprefix("/private")
    return path


def _timestamp_ms() -> str:
    return str(int(time.time() * 1000))


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
