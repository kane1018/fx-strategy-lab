"""Read-only GMO manual-settlement synchronization for the localhost UI.

Only ``latestExecutions`` and ``openPositions`` are reachable.  Broker IDs are
converted to keyed opaque references before leaving the transport boundary;
raw payloads, credentials, headers, signatures, and IDs are never returned or
logged.  The default reader is disabled unless both dedicated Keychain items
exist.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Protocol

import httpx

from app.private_api.auth import build_auth_headers
from app.private_api.schemas import (
    execution_from_api,
    open_positions_from_api_data,
)
from app.services.h11_v3_keychain_credential_no_post import (
    H11V3KeychainError,
    read_h11_v3_keychain_secret,
)

GMO_PRIVATE_BASE_URL = "https://forex-api.coin.z.com"
LATEST_EXECUTIONS_PATH = "/private/v1/latestExecutions"
OPEN_POSITIONS_PATH = "/private/v1/openPositions"
ALLOWED_PRIVATE_GET_PATHS = frozenset({LATEST_EXECUTIONS_PATH, OPEN_POSITIONS_PATH})
KEYCHAIN_SERVICE = "fx-strategy-lab-h11-manual-readonly"
KEYCHAIN_API_KEY_ACCOUNT = "gmo-fx-api-key"
KEYCHAIN_API_SECRET_ACCOUNT = "gmo-fx-api-secret"


class ManualSettlementSyncError(RuntimeError):
    """Safe synchronization error; the message contains only a fixed code."""


class SyncAvailability(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED = "CONFIGURED"


@dataclass(frozen=True)
class SanitizedExecution:
    execution_ref: str
    position_ref: str
    symbol: str
    side: str
    settle_type: str
    size: Decimal
    price: Decimal
    executed_at_utc: str


@dataclass(frozen=True)
class SanitizedOpenPosition:
    position_ref: str
    symbol: str
    side: str
    size: Decimal
    average_price: Decimal | None


@dataclass(frozen=True)
class ManualSettlementSnapshot:
    executions: tuple[SanitizedExecution, ...]
    open_positions: tuple[SanitizedOpenPosition, ...]
    source: str


class ManualSettlementReadClient(Protocol):
    @property
    def availability(self) -> SyncAvailability: ...

    def fetch_snapshot(self, *, symbol: str) -> ManualSettlementSnapshot: ...


@dataclass(frozen=True)
class DisabledManualSettlementReadClient:
    @property
    def availability(self) -> SyncAvailability:
        return SyncAvailability.NOT_CONFIGURED

    def fetch_snapshot(self, *, symbol: str) -> ManualSettlementSnapshot:
        del symbol
        raise ManualSettlementSyncError("BROKER_SYNC_NOT_CONFIGURED")


@dataclass(frozen=True)
class FakeManualSettlementReadClient:
    snapshot: ManualSettlementSnapshot

    @property
    def availability(self) -> SyncAvailability:
        return SyncAvailability.CONFIGURED

    def fetch_snapshot(self, *, symbol: str) -> ManualSettlementSnapshot:
        if any(row.symbol != symbol for row in self.snapshot.executions):
            raise ManualSettlementSyncError("FAKE_EXECUTION_SYMBOL_MISMATCH")
        if any(row.symbol != symbol for row in self.snapshot.open_positions):
            raise ManualSettlementSyncError("FAKE_POSITION_SYMBOL_MISMATCH")
        return self.snapshot


class GmoManualSettlementPrivateGetClient:
    """Concrete, GET-only transport with an injected HTTP client."""

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        client: httpx.Client | None = None,
        timestamp_factory: Callable[[], str] | None = None,
    ) -> None:
        if not api_key or not api_secret:
            raise ManualSettlementSyncError("BROKER_SYNC_CREDENTIAL_MISSING")
        self._api_key = api_key
        self._api_secret = api_secret
        self._client = client or httpx.Client(base_url=GMO_PRIVATE_BASE_URL, timeout=10.0)
        self._timestamp_factory = timestamp_factory or (lambda: str(int(time.time() * 1000)))

    def __repr__(self) -> str:
        return "GmoManualSettlementPrivateGetClient(***)"

    @property
    def availability(self) -> SyncAvailability:
        return SyncAvailability.CONFIGURED

    def fetch_snapshot(self, *, symbol: str) -> ManualSettlementSnapshot:
        if symbol != "USD_JPY":
            raise ManualSettlementSyncError("BROKER_SYNC_SYMBOL_NOT_ALLOWED")
        executions_data = self._private_get(LATEST_EXECUTIONS_PATH, {"symbol": symbol})
        positions_data = self._private_get(OPEN_POSITIONS_PATH, {"symbol": symbol})
        return ManualSettlementSnapshot(
            executions=tuple(self._sanitize_executions(executions_data, symbol=symbol)),
            open_positions=tuple(self._sanitize_positions(positions_data, symbol=symbol)),
            source="GMO_FX_PRIVATE_GET_READONLY",
        )

    def _private_get(self, path: str, params: Mapping[str, str]) -> Any:
        if path not in ALLOWED_PRIVATE_GET_PATHS:
            raise ManualSettlementSyncError("BROKER_SYNC_ENDPOINT_NOT_ALLOWED")
        timestamp = self._timestamp_factory()
        headers = build_auth_headers(
            api_key=self._api_key,
            api_secret=self._api_secret,
            timestamp=timestamp,
            method="GET",
            path=path,
        )
        try:
            response = self._client.get(path, params=dict(params), headers=headers)
        except httpx.HTTPError as error:
            raise ManualSettlementSyncError("BROKER_SYNC_NETWORK_ERROR") from error
        if response.status_code != 200:
            raise ManualSettlementSyncError("BROKER_SYNC_HTTP_ERROR")
        try:
            payload = response.json()
        except ValueError as error:
            raise ManualSettlementSyncError("BROKER_SYNC_INVALID_JSON") from error
        if not isinstance(payload, Mapping) or payload.get("status") != 0:
            raise ManualSettlementSyncError("BROKER_SYNC_API_ERROR")
        return payload.get("data")

    def _sanitize_executions(
        self, data: Any, *, symbol: str
    ) -> list[SanitizedExecution]:
        rows = _collection_rows(data, endpoint="latestExecutions")
        sanitized: list[SanitizedExecution] = []
        for raw in rows:
            try:
                execution = execution_from_api(raw)
            except (ValueError, InvalidOperation) as error:
                raise ManualSettlementSyncError("BROKER_SYNC_EXECUTION_SCHEMA_ERROR") from error
            settle_type = (execution.settle_type or "").upper()
            side = (execution.side or "").upper()
            if (
                execution.symbol != symbol
                or settle_type not in {"OPEN", "CLOSE"}
                or side not in {"BUY", "SELL"}
                or not execution.execution_id
                or not execution.position_id
                or execution.size is None
                or execution.price is None
                or not execution.executed_at
                or execution.size <= 0
                or execution.price <= 0
            ):
                raise ManualSettlementSyncError("BROKER_SYNC_EXECUTION_SCHEMA_ERROR")
            sanitized.append(
                SanitizedExecution(
                    execution_ref=self._opaque_ref("execution", execution.execution_id),
                    position_ref=self._opaque_ref("position", execution.position_id),
                    symbol=execution.symbol,
                    side=side,
                    settle_type=settle_type,
                    size=execution.size,
                    price=execution.price,
                    executed_at_utc=execution.executed_at,
                )
            )
        return sanitized

    def _sanitize_positions(
        self, data: Any, *, symbol: str
    ) -> list[SanitizedOpenPosition]:
        try:
            positions = open_positions_from_api_data(data)
        except (ValueError, InvalidOperation) as error:
            raise ManualSettlementSyncError("BROKER_SYNC_POSITION_SCHEMA_ERROR") from error
        sanitized: list[SanitizedOpenPosition] = []
        for position in positions:
            side = position.side.upper()
            if (
                position.symbol != symbol
                or side not in {"BUY", "SELL"}
                or not position.position_id
                or position.size <= 0
            ):
                raise ManualSettlementSyncError("BROKER_SYNC_POSITION_SCHEMA_ERROR")
            sanitized.append(
                SanitizedOpenPosition(
                    position_ref=self._opaque_ref("position", position.position_id),
                    symbol=position.symbol,
                    side=side,
                    size=position.size,
                    average_price=position.average_price,
                )
            )
        return sanitized

    def _opaque_ref(self, kind: str, raw_identifier: str) -> str:
        digest = hmac.new(
            self._api_secret.encode("utf-8"),
            f"h11-manual:{kind}:{raw_identifier}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"hmac256:{digest}"


def build_keychain_manual_settlement_client() -> ManualSettlementReadClient:
    """Load the dedicated read-only pair from Keychain; fail closed if absent."""

    try:
        api_key = read_h11_v3_keychain_secret(
            service=KEYCHAIN_SERVICE,
            account=KEYCHAIN_API_KEY_ACCOUNT,
        )
        api_secret = read_h11_v3_keychain_secret(
            service=KEYCHAIN_SERVICE,
            account=KEYCHAIN_API_SECRET_ACCOUNT,
        )
    except H11V3KeychainError:
        return DisabledManualSettlementReadClient()
    return GmoManualSettlementPrivateGetClient(
        api_key=api_key.reveal_once(),
        api_secret=api_secret.reveal_once(),
    )


def _collection_rows(data: Any, *, endpoint: str) -> Sequence[Mapping[str, Any]]:
    if data is None:
        return ()
    if isinstance(data, list):
        rows = data
    elif isinstance(data, Mapping) and isinstance(data.get("list"), list):
        rows = data["list"]
    else:
        raise ManualSettlementSyncError(f"BROKER_SYNC_{endpoint.upper()}_SCHEMA_ERROR")
    if any(not isinstance(row, Mapping) for row in rows):
        raise ManualSettlementSyncError(f"BROKER_SYNC_{endpoint.upper()}_SCHEMA_ERROR")
    return rows
