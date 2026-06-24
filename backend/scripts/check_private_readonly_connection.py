"""Phase 3B-4 local GMO FX Private API read-only connection check."""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
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
    open_positions_from_api_data,
    private_api_error_from_payload,
)

DEFAULT_SYMBOL = "USD_JPY"
REQUEST_TIMEOUT_SECONDS = 10.0
MESSAGE_MAX_LENGTH = 120
KEYS_MAX_COUNT = 24
OPEN_POSITION_LIST_KEYS = ("list", "positions", "openPositions", "open_positions", "data")


@dataclass(frozen=True)
class SanitizedResponseShape:
    response_data_shape: str = "unknown"
    response_top_level_keys: str = "unknown"
    response_data_keys: str = "unknown"
    response_data_item_keys: str = "unknown"


@dataclass(frozen=True)
class PrivateApiData:
    data: Any
    shape: SanitizedResponseShape


@dataclass(frozen=True)
class SanitizedConnectionSummary:
    connection_result: str
    account_assets: str
    open_positions: str
    active_orders: str
    failed_endpoint: str = "unknown"
    failed_method: str = "unknown"
    failed_path: str = "unknown"
    sanitized_http_status: str = "unknown"
    sanitized_error_code: str = "unknown"
    sanitized_error_message: str = "unknown"
    diagnostic_reason_category: str = "unknown"
    response_data_shape: str = "unknown"
    response_top_level_keys: str = "unknown"
    response_data_keys: str = "unknown"
    response_data_item_keys: str = "unknown"
    account_assets_count: int = 0
    open_positions_count: int = 0
    active_orders_count: int = 0
    has_open_positions: bool = False
    has_active_orders: bool = False
    raw_response_saved: bool = False
    headers_saved: bool = False
    credentials_printed: bool = False
    retry_attempted: bool = False

    def to_stdout_lines(self) -> list[str]:
        return [
            f"connection_result: {self.connection_result}",
            f"account_assets: {self.account_assets}",
            f"open_positions: {self.open_positions}",
            f"active_orders: {self.active_orders}",
            f"failed_endpoint: {self.failed_endpoint}",
            f"failed_method: {self.failed_method}",
            f"failed_path: {self.failed_path}",
            f"sanitized_http_status: {self.sanitized_http_status}",
            f"sanitized_error_code: {self.sanitized_error_code}",
            f"sanitized_error_message: {self.sanitized_error_message}",
            f"diagnostic_reason_category: {self.diagnostic_reason_category}",
            f"response_data_shape: {self.response_data_shape}",
            f"response_top_level_keys: {self.response_top_level_keys}",
            f"response_data_keys: {self.response_data_keys}",
            f"response_data_item_keys: {self.response_data_item_keys}",
            f"account_assets_count: {self.account_assets_count}",
            f"open_positions_count: {self.open_positions_count}",
            f"active_orders_count: {self.active_orders_count}",
            f"has_open_positions: {_bool_text(self.has_open_positions)}",
            f"has_active_orders: {_bool_text(self.has_active_orders)}",
            f"raw_response_saved: {_bool_text(self.raw_response_saved)}",
            f"headers_saved: {_bool_text(self.headers_saved)}",
            f"credentials_printed: {_bool_text(self.credentials_printed)}",
            f"retry_attempted: {_bool_text(self.retry_attempted)}",
        ]


@dataclass(frozen=True)
class SanitizedFailureDetail:
    failed_endpoint: str
    failed_method: str
    failed_path: str
    sanitized_http_status: str = "unknown"
    sanitized_error_code: str = "unknown"
    sanitized_error_message: str = "unknown"
    diagnostic_reason_category: str = "unknown"
    response_shape: SanitizedResponseShape = field(default_factory=SanitizedResponseShape)


class SanitizedPrivateApiFailure(RuntimeError):
    def __init__(self, detail: SanitizedFailureDetail) -> None:
        super().__init__(detail.sanitized_error_code)
        self.detail = detail


def run_connection_check(
    *,
    api_key: str,
    api_secret: str,
    symbol: str = DEFAULT_SYMBOL,
    http_client: httpx.Client | None = None,
    timestamp_factory: Callable[[], str] | None = None,
    diagnose_open_positions: bool = False,
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
    last_response_shape = SanitizedResponseShape()

    try:
        account_payload = _get_private_api_data(
            client=client,
            api_key=api_key,
            api_secret=api_secret,
            path=GET_ACCOUNT_ASSETS,
            params={},
            timestamp_factory=timestamp,
        )
        last_response_shape = account_payload.shape
        if not isinstance(account_payload.data, Mapping):
            raise PrivateApiResponseError("account assets data must be an object")
        account_assets_from_api(account_payload.data)
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
        last_response_shape = open_position_payload.shape
        open_positions = open_positions_from_api_data(open_position_payload.data)
        if diagnose_open_positions:
            return SanitizedConnectionSummary(
                connection_result="success",
                account_assets="success",
                open_positions="success",
                active_orders="not_run",
                response_data_shape=open_position_payload.shape.response_data_shape,
                response_top_level_keys=open_position_payload.shape.response_top_level_keys,
                response_data_keys=open_position_payload.shape.response_data_keys,
                response_data_item_keys=open_position_payload.shape.response_data_item_keys,
                account_assets_count=1,
                open_positions_count=len(open_positions),
                has_open_positions=bool(open_positions),
            )

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
        last_response_shape = active_order_payload.shape
        active_orders = [
            active_order_from_api(row) for row in _ensure_rows(active_order_payload.data)
        ]
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
    except SanitizedPrivateApiFailure as exc:
        return _with_failure(summary, exc.detail)
    except PrivateApiResponseError as exc:
        return _with_failure(summary, _schema_failure(summary, str(exc), last_response_shape))
    except ValueError as exc:
        return _with_failure(summary, _schema_failure(summary, str(exc), last_response_shape))
    except httpx.HTTPError:
        return _with_failure(summary, _schema_failure(summary, "transport_error"))
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

    summary = runner(
        api_key=api_key,
        api_secret=api_secret,
        symbol=args.symbol,
        diagnose_open_positions=args.diagnose_open_positions,
    )
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
) -> PrivateApiData:
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
    response_shape = _response_shape(payload)
    if response.status_code >= 400 or payload.get("status") != 0:
        api_error = private_api_error_from_payload(payload)
        raise SanitizedPrivateApiFailure(
            _failure_detail(
                method=method,
                path=path,
                http_status=response.status_code,
                error_code=api_error.code,
                error_message=api_error.message,
                response_shape=response_shape,
            )
        )
    return PrivateApiData(data=payload.get("data"), shape=response_shape)


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


def _response_shape(payload: Mapping[str, Any]) -> SanitizedResponseShape:
    data_is_missing = "data" not in payload
    data = payload.get("data")
    data_for_shape = _MissingData if data_is_missing else data
    return SanitizedResponseShape(
        response_data_shape=_shape_label(data_for_shape),
        response_top_level_keys=_key_names(payload),
        response_data_keys=_key_names(data) if isinstance(data, Mapping) else "unknown",
        response_data_item_keys=_data_item_key_names(data),
    )


class _MissingData:
    pass


def _shape_label(value: Any) -> str:
    if value is _MissingData:
        return "missing"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "list"
    if isinstance(value, Mapping):
        return "object"
    return "unknown"


def _data_item_key_names(data: Any) -> str:
    if isinstance(data, list):
        return _first_mapping_item_keys(data)
    if isinstance(data, Mapping):
        nested = _first_nested_list(data)
        if nested is not None:
            return _first_mapping_item_keys(nested)
    return "unknown"


def _first_nested_list(data: Mapping[str, Any]) -> list[Any] | None:
    for key in OPEN_POSITION_LIST_KEYS:
        value = data.get(key)
        if isinstance(value, list):
            return value
    return None


def _first_mapping_item_keys(rows: list[Any]) -> str:
    if not rows:
        return "none"
    first = rows[0]
    if not isinstance(first, Mapping):
        return "unknown"
    return _key_names(first)


def _key_names(mapping: Mapping[str, Any]) -> str:
    names: list[str] = []
    for key in mapping:
        sanitized = _sanitize_key_name(str(key))
        if sanitized not in names:
            names.append(sanitized)
    if not names:
        return "none"
    names = sorted(names)
    if len(names) > KEYS_MAX_COUNT:
        names = [*names[:KEYS_MAX_COUNT], "truncated"]
    return _sanitize_error_token(",".join(names))


def _sanitize_key_name(value: str) -> str:
    normalized = value.lower().translate({ord("_"): "-"})
    sensitive_markers = (
        "api-key",
        "api-sign",
        "api-timestamp",
        "authorization",
        "secret",
        "token",
        "password",
        "private-key",
    )
    if any(marker in normalized for marker in sensitive_markers):
        return "redacted_key"
    return value


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
    parser.add_argument(
        "--diagnose-open-positions",
        action="store_true",
        help="stop after account/assets and openPositions with sanitized diagnostics",
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


def _with_failure(
    summary: SanitizedConnectionSummary,
    detail: SanitizedFailureDetail,
) -> SanitizedConnectionSummary:
    return SanitizedConnectionSummary(
        connection_result=summary.connection_result,
        account_assets=summary.account_assets,
        open_positions=summary.open_positions,
        active_orders=summary.active_orders,
        failed_endpoint=detail.failed_endpoint,
        failed_method=detail.failed_method,
        failed_path=detail.failed_path,
        sanitized_http_status=detail.sanitized_http_status,
        sanitized_error_code=detail.sanitized_error_code,
        sanitized_error_message=detail.sanitized_error_message,
        diagnostic_reason_category=detail.diagnostic_reason_category,
        response_data_shape=detail.response_shape.response_data_shape,
        response_top_level_keys=detail.response_shape.response_top_level_keys,
        response_data_keys=detail.response_shape.response_data_keys,
        response_data_item_keys=detail.response_shape.response_data_item_keys,
        account_assets_count=summary.account_assets_count,
        open_positions_count=summary.open_positions_count,
        active_orders_count=summary.active_orders_count,
        has_open_positions=summary.has_open_positions,
        has_active_orders=summary.has_active_orders,
        raw_response_saved=summary.raw_response_saved,
        headers_saved=summary.headers_saved,
        credentials_printed=summary.credentials_printed,
        retry_attempted=summary.retry_attempted,
    )


def _failure_detail(
    *,
    method: str,
    path: str,
    http_status: int | str,
    error_code: str,
    error_message: str,
    response_shape: SanitizedResponseShape | None = None,
) -> SanitizedFailureDetail:
    sanitized_message = _sanitize_error_message(error_message)
    return SanitizedFailureDetail(
        failed_endpoint=_endpoint_name(path),
        failed_method=method.upper(),
        failed_path=path,
        sanitized_http_status=str(http_status),
        sanitized_error_code=_sanitize_error_token(error_code),
        sanitized_error_message=sanitized_message,
        diagnostic_reason_category=_reason_category(
            http_status=str(http_status),
            error_code=error_code,
            error_message=sanitized_message,
        ),
        response_shape=response_shape or SanitizedResponseShape(),
    )


def _schema_failure(
    summary: SanitizedConnectionSummary,
    error_message: str,
    response_shape: SanitizedResponseShape | None = None,
) -> SanitizedFailureDetail:
    if summary.account_assets != "success":
        path = GET_ACCOUNT_ASSETS
    elif summary.open_positions != "success":
        path = GET_OPEN_POSITIONS
    else:
        path = GET_ACTIVE_ORDERS
    return SanitizedFailureDetail(
        failed_endpoint=_endpoint_name(path),
        failed_method="GET",
        failed_path=path,
        sanitized_error_code="schema_error",
        sanitized_error_message=_sanitize_error_message(error_message),
        diagnostic_reason_category="schema_error",
        response_shape=response_shape or SanitizedResponseShape(),
    )


def _endpoint_name(path: str) -> str:
    if path == GET_ACCOUNT_ASSETS:
        return "account_assets"
    if path == GET_OPEN_POSITIONS:
        return "open_positions"
    if path == GET_ACTIVE_ORDERS:
        return "active_orders"
    return "unknown"


def _sanitize_error_token(value: str) -> str:
    token = " ".join(str(value or "unknown").split())
    if not token:
        return "unknown"
    return token[:MESSAGE_MAX_LENGTH]


def _sanitize_error_message(value: str) -> str:
    message = " ".join(str(value or "unknown").split())
    if not message:
        return "unknown"
    sensitive_markers = ("API-KEY:", "API-SIGN:", "Authorization:", "Bearer ")
    if any(marker.lower() in message.lower() for marker in sensitive_markers):
        return "redacted_sensitive_error_message"
    return message[:MESSAGE_MAX_LENGTH]


def _reason_category(*, http_status: str, error_code: str, error_message: str) -> str:
    text = f"{error_code} {error_message}".lower()
    if http_status in {"400", "422"}:
        return "parameter_error"
    if http_status == "401":
        return "auth_error"
    if http_status == "403":
        return "permission_error"
    if any(marker in text for marker in ("permission", "forbidden", "scope", "not allowed")):
        return "permission_error"
    if any(marker in text for marker in ("auth", "signature", "timestamp", "api key", "api-key")):
        return "auth_error"
    if any(marker in text for marker in ("parameter", "param", "symbol", "invalid request")):
        return "parameter_error"
    if "schema" in text:
        return "schema_error"
    return "unknown"


def _timestamp_ms() -> str:
    return str(int(time.time() * 1000))


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
