"""H-11 GMO relaxed v4 Private API transport (activation absent).

This module contains the reviewed actual-shaped transport boundary: sealed
Keychain loading, GMO HMAC signing, and an httpx request implementation.  It is
structurally unconstructible in the current build because no v4 activation
permit can be created.  Fake adapter tests use an injected fake transport and
never call Keychain or the network.

The distinction between ``transport_path`` (``/private/v1/...``) and
``signing_path`` (``/v1/...``) follows the official GMO FX examples and is
validated for every request.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Protocol

import httpx

from app.h11_auto.v4_activation_preparation import (
    V4PrivateApiCadenceGate,
)
from app.private_api.auth import build_auth_headers
from app.security.real_broker_post_hard_guard import assert_real_broker_post_allowed

GMO_V4_PRIVATE_BASE_URL = "https://forex-api.coin.z.com"
GMO_V4_KEYCHAIN_SERVICE = "fx-strategy-lab-h11-v4-actual"
GMO_V4_API_KEY_ACCOUNT = "gmo-fx-api-key"
GMO_V4_API_SECRET_ACCOUNT = "gmo-fx-api-secret"

_ALLOWED_ENDPOINTS = frozenset(
    {
        ("GET", "/private/v1/latestExecutions", "/v1/latestExecutions"),
        ("GET", "/private/v1/openPositions", "/v1/openPositions"),
        ("GET", "/private/v1/activeOrders", "/v1/activeOrders"),
        ("POST", "/private/v1/order", "/v1/order"),
        ("POST", "/private/v1/cancelOrders", "/v1/cancelOrders"),
        ("POST", "/private/v1/closeOrder", "/v1/closeOrder"),
    }
)
_CLIENT_ORDER_ID_PATTERN = re.compile(r"^H11V4[EPXT][0-9a-f]{30}$")


class V4GmoActualTransportError(RuntimeError):
    """Fixed safe transport failure. Messages never contain response data."""


class V4GmoActualActivationPermit:
    """Unconstructible marker until a separately authorized activation step."""

    def __new__(cls) -> V4GmoActualActivationPermit:
        del cls
        raise V4GmoActualTransportError("V4_GMO_ACTIVATION_PERMIT_NOT_ISSUED")


@dataclass(frozen=True, repr=False)
class V4GmoSealedSecret:
    _value: str

    def reveal_for_internal_request_only(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "V4GmoSealedSecret(***)"

    def __str__(self) -> str:
        return "***"

    def __bool__(self) -> bool:
        return False


class V4GmoSealedCredentialPair(Protocol):
    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4GmoSealedSecret, V4GmoSealedSecret]: ...


SecretReader = Callable[[str, str], V4GmoSealedSecret]


@dataclass(frozen=True, repr=False)
class V4GmoPrivateEnvelope:
    """Ephemeral response envelope whose repr never exposes broker content."""

    _status: int
    _data: Any

    @classmethod
    def from_injected_payload(cls, payload: Mapping[str, Any]) -> V4GmoPrivateEnvelope:
        status = payload.get("status")
        if type(status) is not int:  # noqa: E721
            raise V4GmoActualTransportError("V4_GMO_RESPONSE_STATUS_INVALID")
        return cls(_status=status, _data=payload.get("data"))

    def _status_for_adapter(self) -> int:
        return self._status

    def _data_for_adapter(self) -> Any:
        return self._data

    def __repr__(self) -> str:
        return "V4GmoPrivateEnvelope(<redacted>)"

    def __bool__(self) -> bool:
        return False


def read_v4_gmo_keychain_secret(
    service: str,
    account: str,
    *,
    timeout_seconds: float = 5.0,
) -> V4GmoSealedSecret:
    """Read one Keychain item without exposing its value in errors or repr."""

    if platform.system() != "Darwin":
        raise V4GmoActualTransportError("V4_GMO_KEYCHAIN_PLATFORM_UNSUPPORTED")
    if not service or not account or timeout_seconds <= 0:
        raise V4GmoActualTransportError("V4_GMO_KEYCHAIN_ARGUMENT_INVALID")
    try:
        completed = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise V4GmoActualTransportError("V4_GMO_KEYCHAIN_READ_FAILED") from error
    if completed.returncode != 0:
        raise V4GmoActualTransportError("V4_GMO_KEYCHAIN_ITEM_UNAVAILABLE")
    value = completed.stdout.rstrip("\n")
    if not value:
        raise V4GmoActualTransportError("V4_GMO_KEYCHAIN_ITEM_EMPTY")
    return V4GmoSealedSecret(value)


@dataclass(frozen=True, repr=False)
class V4GmoKeychainCredentialPair:
    """Dedicated v4 pair; values are loaded fresh and retained only briefly."""

    reader: SecretReader = read_v4_gmo_keychain_secret

    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4GmoSealedSecret, V4GmoSealedSecret]:
        try:
            api_key = self.reader(GMO_V4_KEYCHAIN_SERVICE, GMO_V4_API_KEY_ACCOUNT)
            api_secret = self.reader(GMO_V4_KEYCHAIN_SERVICE, GMO_V4_API_SECRET_ACCOUNT)
        except V4GmoActualTransportError:
            raise
        except Exception as error:  # noqa: BLE001
            raise V4GmoActualTransportError("V4_GMO_KEYCHAIN_READ_FAILED") from error
        if not isinstance(api_key, V4GmoSealedSecret) or not isinstance(
            api_secret, V4GmoSealedSecret
        ):
            raise V4GmoActualTransportError("V4_GMO_KEYCHAIN_READER_CONTRACT_INVALID")
        return api_key, api_secret

    def __repr__(self) -> str:
        return "V4GmoKeychainCredentialPair(***)"

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True, repr=False)
class V4GmoPrivateRequest:
    method: str
    transport_path: str
    signing_path: str
    params: Mapping[str, str]
    body: Mapping[str, Any] | None
    _body_json: str = field(default="", init=False, repr=False)

    def __post_init__(self) -> None:
        normalized = (self.method, self.transport_path, self.signing_path)
        if normalized not in _ALLOWED_ENDPOINTS:
            raise V4GmoActualTransportError("V4_GMO_PRIVATE_ENDPOINT_NOT_ALLOWED")
        if self.method == "GET" and self.body is not None:
            raise V4GmoActualTransportError("V4_GMO_GET_BODY_FORBIDDEN")
        if self.method == "POST" and self.body is None:
            raise V4GmoActualTransportError("V4_GMO_POST_BODY_REQUIRED")
        params = dict(self.params)
        body = None if self.body is None else dict(self.body)
        _validate_request_contract(
            method=self.method,
            transport_path=self.transport_path,
            params=params,
            body=body,
        )
        try:
            body_json = (
                "" if body is None else json.dumps(body, sort_keys=True, separators=(",", ":"))
            )
        except (TypeError, ValueError) as error:
            raise V4GmoActualTransportError("V4_GMO_REQUEST_BODY_INVALID") from error
        object.__setattr__(self, "params", MappingProxyType(params))
        object.__setattr__(
            self,
            "body",
            None if body is None else MappingProxyType(body),
        )
        object.__setattr__(self, "_body_json", body_json)

    @property
    def body_json(self) -> str:
        return self._body_json

    def __repr__(self) -> str:
        return f"V4GmoPrivateRequest(method={self.method!r}, route=<sanitized>, content=<redacted>)"

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True, repr=False)
class V4GmoSignedPrivateRequest:
    request: V4GmoPrivateRequest
    headers: Mapping[str, str]

    def __repr__(self) -> str:
        return "V4GmoSignedPrivateRequest(<redacted>)"

    def __bool__(self) -> bool:
        return False


class V4GmoPrivateTransport(Protocol):
    def request(self, request: V4GmoPrivateRequest) -> V4GmoPrivateEnvelope: ...


@dataclass(frozen=True, repr=False)
class V4GmoSignedRequestFactory:
    credential_pair: V4GmoSealedCredentialPair
    timestamp_factory: Callable[[], str] = lambda: str(int(time.time() * 1000))

    def build(self, request: V4GmoPrivateRequest) -> V4GmoSignedPrivateRequest:
        api_key, api_secret = self.credential_pair.unseal_for_internal_request_only()
        timestamp = self.timestamp_factory()
        if not timestamp or not timestamp.isdigit():
            raise V4GmoActualTransportError("V4_GMO_TIMESTAMP_INVALID")
        headers = build_auth_headers(
            api_key=api_key.reveal_for_internal_request_only(),
            api_secret=api_secret.reveal_for_internal_request_only(),
            timestamp=timestamp,
            method=request.method,
            path=request.signing_path,
            body=request.body_json,
        )
        return V4GmoSignedPrivateRequest(request=request, headers=headers)

    def __repr__(self) -> str:
        return "V4GmoSignedRequestFactory(***)"

    def __bool__(self) -> bool:
        return False


class V4GmoHttpxPrivateTransport:
    """Actual-capable transport whose activation permit is absent in this build."""

    def __init__(
        self,
        *,
        activation_permit: V4GmoActualActivationPermit,
        signed_request_factory: V4GmoSignedRequestFactory,
        client: httpx.Client | None = None,
        cadence_gate: V4PrivateApiCadenceGate | None = None,
        monotonic_factory: Callable[[], float] = time.monotonic,
    ) -> None:
        del (
            activation_permit,
            signed_request_factory,
            client,
            cadence_gate,
            monotonic_factory,
        )
        # The current build has no activation factory.  Refuse the entire
        # actual transport constructor instead of trusting a Python type check,
        # which can be bypassed with object.__new__(PermitType).
        raise V4GmoActualTransportError("V4_GMO_ACTIVATION_PERMIT_NOT_ISSUED")

    def __repr__(self) -> str:
        return "V4GmoHttpxPrivateTransport(<activation-gated>)"

    def request(self, request: V4GmoPrivateRequest) -> V4GmoPrivateEnvelope:
        # Keep the call boundary unavailable as well as the constructor.  This
        # prevents object.__new__(TransportType) plus injected attributes from
        # becoming an activation substitute in the preparation-only build.
        if request.method == "POST":
            # The common hard guard stays in the POST call boundary even while
            # activation is unavailable.  A future activation change must keep
            # this per-call guard and receive a separate operator review.
            assert_real_broker_post_allowed(allow=False)
        raise V4GmoActualTransportError("V4_GMO_ACTIVATION_PERMIT_NOT_ISSUED")

    def __bool__(self) -> bool:
        return False


def _validate_request_contract(
    *,
    method: str,
    transport_path: str,
    params: Mapping[str, str],
    body: Mapping[str, Any] | None,
) -> None:
    if method == "GET":
        if transport_path == "/private/v1/latestExecutions":
            if (
                set(params) != {"symbol", "count"}
                or params.get("symbol") != "USD_JPY"
            ):
                raise V4GmoActualTransportError("V4_GMO_GET_PARAMETERS_INVALID")
        elif set(params) != {"count"}:
            raise V4GmoActualTransportError("V4_GMO_GET_PARAMETERS_INVALID")
        if params.get("count") != "100":
            raise V4GmoActualTransportError("V4_GMO_GET_COUNT_INVALID")
        return
    if params:
        raise V4GmoActualTransportError("V4_GMO_POST_PARAMETERS_FORBIDDEN")
    if body is None:
        raise V4GmoActualTransportError("V4_GMO_POST_BODY_REQUIRED")
    if transport_path == "/private/v1/order":
        expected = {"symbol", "side", "size", "clientOrderId", "executionType"}
        if set(body) != expected or body.get("executionType") != "MARKET":
            raise V4GmoActualTransportError("V4_GMO_MARKET_BODY_INVALID")
        _validate_common_order_fields(body, expected_prefix="E")
        return
    if transport_path == "/private/v1/cancelOrders":
        if set(body) != {"clientOrderIds"}:
            raise V4GmoActualTransportError("V4_GMO_CANCEL_BODY_INVALID")
        client_ids = body.get("clientOrderIds")
        if (
            not isinstance(client_ids, list)
            or len(client_ids) != 1
            or not _valid_client_order_id(client_ids[0], prefixes={"E", "P"})
        ):
            raise V4GmoActualTransportError("V4_GMO_CANCEL_CLIENT_ID_INVALID")
        return
    if transport_path == "/private/v1/closeOrder":
        execution_type = body.get("executionType")
        if execution_type == "OCO":
            expected = {
                "symbol",
                "side",
                "clientOrderId",
                "executionType",
                "limitPrice",
                "stopPrice",
                "settlePosition",
            }
            if set(body) != expected:
                raise V4GmoActualTransportError("V4_GMO_OCO_BODY_INVALID")
            _validate_common_order_fields(body, expected_prefix="P", size_required=False)
            _positive_decimal(body.get("limitPrice"))
            _positive_decimal(body.get("stopPrice"))
        elif execution_type == "MARKET":
            expected = {
                "symbol",
                "side",
                "clientOrderId",
                "executionType",
                "settlePosition",
            }
            if set(body) != expected:
                raise V4GmoActualTransportError("V4_GMO_CLOSE_BODY_INVALID")
            _validate_common_order_fields(
                body,
                expected_prefix={"X", "T"},
                size_required=False,
            )
        else:
            raise V4GmoActualTransportError("V4_GMO_CLOSE_EXECUTION_TYPE_INVALID")
        _validate_settle_positions(body.get("settlePosition"))
        return
    raise V4GmoActualTransportError("V4_GMO_PRIVATE_ENDPOINT_NOT_ALLOWED")


def _validate_common_order_fields(
    body: Mapping[str, Any],
    *,
    expected_prefix: str | set[str],
    size_required: bool = True,
) -> None:
    if body.get("symbol") != "USD_JPY" or body.get("side") not in {"BUY", "SELL"}:
        raise V4GmoActualTransportError("V4_GMO_ORDER_SCOPE_INVALID")
    prefixes = (
        {expected_prefix}
        if isinstance(expected_prefix, str)
        else expected_prefix
    )
    if not _valid_client_order_id(body.get("clientOrderId"), prefixes=prefixes):
        raise V4GmoActualTransportError("V4_GMO_CLIENT_ORDER_ID_INVALID")
    if size_required:
        size = _positive_decimal(body.get("size"))
        if size != size.to_integral_value() or size > 10_000:
            raise V4GmoActualTransportError("V4_GMO_ORDER_SIZE_INVALID")


def _validate_settle_positions(value: Any) -> None:
    if not isinstance(value, list) or not 1 <= len(value) <= 10:
        raise V4GmoActualTransportError("V4_GMO_SETTLE_POSITION_LIST_INVALID")
    total = Decimal("0")
    for row in value:
        if not isinstance(row, Mapping) or set(row) != {"positionId", "size"}:
            raise V4GmoActualTransportError("V4_GMO_SETTLE_POSITION_ROW_INVALID")
        position_id = row.get("positionId")
        if type(position_id) is not int or position_id <= 0:  # noqa: E721
            raise V4GmoActualTransportError("V4_GMO_SETTLE_POSITION_ID_INVALID")
        size = _positive_decimal(row.get("size"))
        if size != size.to_integral_value():
            raise V4GmoActualTransportError("V4_GMO_SETTLE_POSITION_SIZE_INVALID")
        total += size
    if total > 10_000:
        raise V4GmoActualTransportError("V4_GMO_SETTLE_POSITION_TOTAL_INVALID")


def _valid_client_order_id(value: Any, *, prefixes: set[str]) -> bool:
    if not isinstance(value, str) or not _CLIENT_ORDER_ID_PATTERN.fullmatch(value):
        return False
    return value[5] in prefixes


def _positive_decimal(value: Any) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise V4GmoActualTransportError("V4_GMO_DECIMAL_FIELD_INVALID") from error
    if not parsed.is_finite() or parsed <= 0:
        raise V4GmoActualTransportError("V4_GMO_DECIMAL_FIELD_INVALID")
    return parsed
