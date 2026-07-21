"""H-11 GMO relaxed v4 Private API transport (activation gated).

This module contains the reviewed actual-shaped transport boundary: sealed
Keychain loading, GMO HMAC signing, and an httpx request implementation.  It is
constructible only from a generation/cycle-bound one-use activation permit.
The production permit is not issued by preparation code. Fake tests use an
injected client and never call Keychain or the network.

The distinction between ``transport_path`` (``/private/v1/...``) and
``signing_path`` (``/v1/...``) follows the official GMO FX examples and is
validated for every request.
"""

from __future__ import annotations

import hashlib
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
    V4CadenceMethod,
    V4PrivateApiCadenceGate,
)
from app.h11_auto.v4_gmo_canary_activation import (
    V4ActivatedRuntimeScope,
    V4GmoActualActivationPermit,
    V4GmoCanaryActivationError,
    consume_v4_gmo_actual_activation_permit,
    require_v4_activated_runtime_scope_internal,
)
from app.h11_auto.v4_gmo_contracts import V4GmoAction
from app.h11_auto.v4_gmo_persisted_authorization import (
    V4PersistedAuthorizationError,
    V4PersistedTransportAuthorization,
    consume_persisted_transport_authorization,
)
from app.private_api.auth import build_auth_headers
from app.security.real_broker_post_hard_guard import assert_real_broker_post_allowed

GMO_V4_PRIVATE_BASE_URL = "https://forex-api.coin.z.com"
GMO_V4_KEYCHAIN_SERVICE = "fx-strategy-lab-h11-v4-actual"
GMO_V4_API_KEY_ACCOUNT = "gmo-fx-api-key"
GMO_V4_API_SECRET_ACCOUNT = "gmo-fx-api-secret"

# Fixed diagnostic classes for a private call whose result is unknown. These carry
# ONLY the failure mechanism (never broker response content, identifiers, or
# credentials) so a real incident like 2026-07-21 (entry POST -> unknown halt, no
# broker-side order record) can be attributed to timeout / connection / non-JSON /
# invalid-envelope instead of remaining a single opaque UNKNOWN.
V4_GMO_UNKNOWN_TIMEOUT = "V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT"
V4_GMO_UNKNOWN_CONNECTION = "V4_GMO_PRIVATE_RESULT_UNKNOWN_CONNECTION"
V4_GMO_UNKNOWN_NON_JSON = "V4_GMO_PRIVATE_RESULT_UNKNOWN_NON_JSON"
V4_GMO_UNKNOWN_ENVELOPE_INVALID = "V4_GMO_PRIVATE_RESULT_UNKNOWN_ENVELOPE_INVALID"
V4_GMO_PRIVATE_RESULT_UNKNOWN_CLASSES = frozenset(
    {
        V4_GMO_UNKNOWN_TIMEOUT,
        V4_GMO_UNKNOWN_CONNECTION,
        V4_GMO_UNKNOWN_NON_JSON,
        V4_GMO_UNKNOWN_ENVELOPE_INVALID,
    }
)

# Closed allow-list of transport labels that may be surfaced as an operator-facing
# failure class. Exact membership only — a shape/charset test would still admit a
# future ``f"V4_GMO_...{broker_value}"``, so anything not enumerated here collapses
# to the base UNKNOWN label. Every entry is a fixed literal raised by this module.
V4_GMO_SURFACEABLE_FAILURE_CLASSES = V4_GMO_PRIVATE_RESULT_UNKNOWN_CLASSES | frozenset(
    {
        "V4_GMO_PRIVATE_RESULT_UNKNOWN",
        "V4_GMO_ACTIVATION_PERMIT_NOT_ISSUED",
        "V4_GMO_PERSISTED_TRANSPORT_AUTHORIZATION_REQUIRED",
        "V4_GMO_PERSISTED_TRANSPORT_AUTHORIZATION_UNEXPECTED",
        "V4_GMO_CURRENT_TURN_ENTRY_SCOPE_EXPIRED_OR_MISMATCHED",
        "V4_GMO_PRIVATE_CADENCE_BLOCKED",
        "V4_GMO_SAME_ACTION_SECOND_ATTEMPT_FORBIDDEN",
        "V4_GMO_POST_SEQUENCE_INVALID",
        "V4_GMO_POST_SCOPE_INVALID",
        "V4_GMO_POST_BODY_REQUIRED",
        "V4_GMO_POST_PARAMETERS_FORBIDDEN",
        "V4_GMO_PRIVATE_ENDPOINT_NOT_ALLOWED",
        "V4_GMO_REQUEST_INVALID",
        "V4_GMO_REQUEST_BODY_INVALID",
        "V4_GMO_MARKET_BODY_INVALID",
        "V4_GMO_ORDER_SCOPE_INVALID",
        "V4_GMO_ORDER_SIZE_INVALID",
        "V4_GMO_RESPONSE_STATUS_INVALID",
        "V4_GMO_SIGNER_INVALID",
        "V4_GMO_TIMESTAMP_INVALID",
        "V4_GMO_UNKNOWN_POST_CALLBACK_REQUIRED",
        "V4_GMO_KEYCHAIN_READ_FAILED",
        "V4_GMO_KEYCHAIN_ITEM_UNAVAILABLE",
        "V4_GMO_KEYCHAIN_ITEM_EMPTY",
        "V4_GMO_KEYCHAIN_ARGUMENT_INVALID",
        "V4_GMO_KEYCHAIN_PLATFORM_UNSUPPORTED",
        "V4_GMO_KEYCHAIN_READER_CONTRACT_INVALID",
    }
)


def _classify_private_result_unknown(error: Exception) -> str:
    """Map one private-call failure to one FIXED label; never echo error content."""

    if isinstance(error, httpx.TimeoutException):
        return V4_GMO_UNKNOWN_TIMEOUT
    if isinstance(error, httpx.TransportError):
        return V4_GMO_UNKNOWN_CONNECTION
    if isinstance(error, json.JSONDecodeError):
        return V4_GMO_UNKNOWN_NON_JSON
    if isinstance(error, V4GmoActualTransportError):
        label = str(error)
        if label in V4_GMO_PRIVATE_RESULT_UNKNOWN_CLASSES:
            return label
        if label == "V4_GMO_RESPONSE_STATUS_INVALID":
            return V4_GMO_UNKNOWN_ENVELOPE_INVALID
    return "V4_GMO_PRIVATE_RESULT_UNKNOWN"

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


def v4_gmo_private_request_binding_digest(request: V4GmoPrivateRequest) -> str:
    if not isinstance(request, V4GmoPrivateRequest):
        raise V4GmoActualTransportError("V4_GMO_REQUEST_INVALID")
    canonical = json.dumps(
        {
            "body": None if request.body is None else dict(request.body),
            "method": request.method,
            "params": dict(request.params),
            "signing_path": request.signing_path,
            "transport_path": request.transport_path,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True, repr=False)
class V4GmoSignedPrivateRequest:
    request: V4GmoPrivateRequest
    headers: Mapping[str, str]

    def __repr__(self) -> str:
        return "V4GmoSignedPrivateRequest(<redacted>)"

    def __bool__(self) -> bool:
        return False


class V4GmoPrivateTransport(Protocol):
    def request(
        self,
        request: V4GmoPrivateRequest,
        *,
        persisted_transport_authorization: (
            V4PersistedTransportAuthorization | None
        ) = None,
    ) -> V4GmoPrivateEnvelope: ...


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
    """Generation/cycle-bound transport with no retry or repost path."""

    def __init__(
        self,
        *,
        activation_permit: V4GmoActualActivationPermit,
        signed_request_factory: V4GmoSignedRequestFactory,
        client: httpx.Client | None = None,
        cadence_gate: V4PrivateApiCadenceGate | None = None,
        monotonic_factory: Callable[[], float] = time.monotonic,
        unknown_post_callback: Callable[[], None] | None = None,
    ) -> None:
        try:
            scope = consume_v4_gmo_actual_activation_permit(
                activation_permit,
                now_monotonic=monotonic_factory(),
            )
        except (V4GmoCanaryActivationError, TypeError, ValueError) as error:
            raise V4GmoActualTransportError(
                "V4_GMO_ACTIVATION_PERMIT_NOT_ISSUED"
            ) from error
        if not isinstance(signed_request_factory, V4GmoSignedRequestFactory):
            raise V4GmoActualTransportError("V4_GMO_SIGNER_INVALID")
        self._scope: V4ActivatedRuntimeScope = scope
        self._signed_request_factory = signed_request_factory
        self._client = client if client is not None else httpx.Client()
        self._owns_client = client is None
        self._cadence_gate = cadence_gate or V4PrivateApiCadenceGate()
        self._monotonic_factory = monotonic_factory
        self._post_keys: set[str] = set()
        self._market_close_attempted = False
        if not callable(unknown_post_callback):
            raise V4GmoActualTransportError("V4_GMO_UNKNOWN_POST_CALLBACK_REQUIRED")
        self._unknown_post_callback = unknown_post_callback

    def __repr__(self) -> str:
        return "V4GmoHttpxPrivateTransport(<activation-gated>)"

    def request(
        self,
        request: V4GmoPrivateRequest,
        *,
        persisted_transport_authorization: (
            V4PersistedTransportAuthorization | None
        ) = None,
    ) -> V4GmoPrivateEnvelope:
        try:
            scope = require_v4_activated_runtime_scope_internal(self._scope)
        except (AttributeError, V4GmoCanaryActivationError) as error:
            raise V4GmoActualTransportError(
                "V4_GMO_ACTIVATION_PERMIT_NOT_ISSUED"
            ) from error
        if not isinstance(request, V4GmoPrivateRequest):
            raise V4GmoActualTransportError("V4_GMO_REQUEST_INVALID")
        now = self._monotonic_factory()
        method = (
            V4CadenceMethod.PRIVATE_GET
            if request.method == "GET"
            else V4CadenceMethod.PRIVATE_POST
        )
        if not self._cadence_gate.admit(method=method, now_monotonic=now):
            raise V4GmoActualTransportError("V4_GMO_PRIVATE_CADENCE_BLOCKED")
        if request.method == "POST":
            request_binding_digest = v4_gmo_private_request_binding_digest(request)
            post_key, allowed_actions = self._require_bound_post_once(request)
            try:
                consume_persisted_transport_authorization(
                    persisted_transport_authorization,
                    cycle_ref=scope.cycle_ref,
                    allowed_actions=allowed_actions,
                    request_binding_digest=request_binding_digest,
                )
            except V4PersistedAuthorizationError as error:
                raise V4GmoActualTransportError(
                    "V4_GMO_PERSISTED_TRANSPORT_AUTHORIZATION_REQUIRED"
                ) from error
            self._post_keys.add(post_key)
            if (
                V4GmoAction.MARKET_ENTRY in allowed_actions
                and (
                    now > scope.entry_expires_monotonic
                    or request.body is None
                    or request.body.get("side") != scope.side
                    or request.body.get("size") != str(scope.size)
                    or request.body.get("symbol") != scope.symbol
                    or request.body.get("executionType") != scope.execution_type
                )
            ):
                raise V4GmoActualTransportError(
                    "V4_GMO_CURRENT_TURN_ENTRY_SCOPE_EXPIRED_OR_MISMATCHED"
                )
        elif persisted_transport_authorization is not None:
            raise V4GmoActualTransportError(
                "V4_GMO_PERSISTED_TRANSPORT_AUTHORIZATION_UNEXPECTED"
            )
        signed = self._signed_request_factory.build(request)
        try:
            if request.method == "POST":
                assert_real_broker_post_allowed(allow=True)
            response = self._client.request(
                request.method,
                GMO_V4_PRIVATE_BASE_URL + request.transport_path,
                params=dict(request.params),
                headers=dict(signed.headers),
                content=(request.body_json if request.method == "POST" else None),
                timeout=5.0,
            )
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise V4GmoActualTransportError(V4_GMO_UNKNOWN_NON_JSON)
            envelope = V4GmoPrivateEnvelope.from_injected_payload(payload)
        except Exception as error:  # noqa: BLE001
            if request.method == "POST":
                try:
                    self._unknown_post_callback()
                except Exception:  # noqa: BLE001
                    pass
            raise V4GmoActualTransportError(
                _classify_private_result_unknown(error)
            ) from error
        return envelope

    def _require_bound_post_once(
        self, request: V4GmoPrivateRequest
    ) -> tuple[str, tuple[V4GmoAction, ...]]:
        client_key = _post_key(request)
        action_key = f"{request.transport_path}|{client_key}"
        if action_key in self._post_keys or not _request_matches_cycle(
            request,
            cycle_ref=self._scope.cycle_ref,
        ):
            raise V4GmoActualTransportError("V4_GMO_SAME_ACTION_SECOND_ATTEMPT_FORBIDDEN")
        prefix = client_key[:1]
        entry_key = "/private/v1/order|E" + self._scope.cycle_ref[:30]
        protection_key = "/private/v1/closeOrder|P" + self._scope.cycle_ref[:30]
        if prefix == "E" and request.transport_path == "/private/v1/order":
            if self._post_keys:
                raise V4GmoActualTransportError("V4_GMO_POST_SEQUENCE_INVALID")
            allowed_actions = (V4GmoAction.MARKET_ENTRY,)
        elif prefix == "E":
            if entry_key not in self._post_keys:
                raise V4GmoActualTransportError("V4_GMO_POST_SEQUENCE_INVALID")
            allowed_actions = (V4GmoAction.CANCEL_ENTRY_REMAINDER,)
        elif prefix == "P":
            if entry_key not in self._post_keys:
                raise V4GmoActualTransportError("V4_GMO_POST_SEQUENCE_INVALID")
            if (
                request.transport_path == "/private/v1/cancelOrders"
                and protection_key not in self._post_keys
            ):
                raise V4GmoActualTransportError("V4_GMO_POST_SEQUENCE_INVALID")
            allowed_actions = (
                (V4GmoAction.EXACT_SIZE_OCO_PROTECTION,)
                if request.transport_path == "/private/v1/closeOrder"
                else (
                    V4GmoAction.CANCEL_MISMATCHED_PROTECTION,
                    V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
                )
            )
        elif prefix in {"X", "T"}:
            if entry_key not in self._post_keys or self._market_close_attempted:
                raise V4GmoActualTransportError("V4_GMO_POST_SEQUENCE_INVALID")
            self._market_close_attempted = True
            allowed_actions = (
                (
                    V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
                )
                if prefix == "X"
                else (V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,)
            )
        else:
            raise V4GmoActualTransportError("V4_GMO_POST_SEQUENCE_INVALID")
        return action_key, allowed_actions

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __bool__(self) -> bool:
        return False


def _post_key(request: V4GmoPrivateRequest) -> str:
    if request.transport_path == "/private/v1/cancelOrders":
        values = None if request.body is None else request.body.get("clientOrderIds")
        if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], str):
            raise V4GmoActualTransportError("V4_GMO_POST_SCOPE_INVALID")
        return values[0][5:]
    client_order_id = None if request.body is None else request.body.get("clientOrderId")
    if not isinstance(client_order_id, str):
        raise V4GmoActualTransportError("V4_GMO_POST_SCOPE_INVALID")
    return client_order_id[5:]


def _request_matches_cycle(request: V4GmoPrivateRequest, *, cycle_ref: str) -> bool:
    try:
        key = _post_key(request)
    except V4GmoActualTransportError:
        return False
    return len(key) == 31 and key[0] in {"E", "P", "X", "T"} and key[1:] == cycle_ref[:30]


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
        if size != size.to_integral_value() or size > 1_000:
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
    if total > 1_000:
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
