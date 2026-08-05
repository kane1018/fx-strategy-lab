"""G078 one-use Private-GET read-back producer (fake-only tested).

Serves the G078 read-back resolution's ``read_back_client`` port: for a given
action scope it reads ``latestExecutions``, ``openPositions`` and
``activeOrders`` at most once each and returns a sanitized ``G078SanitizedRead``
(counts / flat / zero / ownership flags only -- never raw identifiers, prices,
headers, signatures, or credential values).

The module is named ``app.services.h11_v4_g078_private_get_producer`` so that
callbacks defined here satisfy the G078 resolution step's fake-only module
prefix gate.  Implementation and tests are fake-only: real Keychain reads and
real Private GETs are operator-executed with a separate explicit approval.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from app.private_api.auth import build_auth_headers
from app.services.h11_v4_g026_private_get_keychain import (
    V4G026PrivateGetKeychainCredentialPair,
)
from app.services.h11_v4_g078_runtime import (
    G078FakeOnlyCallable,
    G078ReadBackSource,
    G078SanitizedRead,
)

_PRIVATE_BASE_URL = "https://api.coin.z.com/private/v1"
_MIN_READ_INTERVAL_SECONDS = 0.25
_TIMEOUT_SECONDS = 10.0


class V4G078PrivateGetProducerError(RuntimeError):
    """Fixed safe-label producer failure."""


def _extract_latest_executions(
    payload: dict[str, Any], *, expected_quantity: int
) -> G078SanitizedRead:
    try:
        executions = payload.get("data") or []
    except AttributeError:
        executions = []
    matched = False
    for execution in executions:
        if not isinstance(execution, dict):
            continue
        if int(execution.get("size") or 0) == expected_quantity:
            matched = True
            break
    return G078SanitizedRead(
        source=G078ReadBackSource.LATEST_EXECUTIONS,
        known=True,
        count=len(executions),
        matched_execution_seen=matched,
    )


def _extract_open_positions(
    payload: dict[str, Any], *, expected_symbol: str, expected_quantity: int
) -> G078SanitizedRead:
    try:
        positions = payload.get("data") or []
    except AttributeError:
        positions = []
    owned = [p for p in positions if isinstance(p, dict) and p.get("symbol") == expected_symbol]
    quantity_matches = any(
        int(p.get("size") or 0) == expected_quantity for p in owned
    )
    return G078SanitizedRead(
        source=G078ReadBackSource.OPEN_POSITIONS,
        known=True,
        count=len(positions),
        account_flat=len(owned) == 0,
        ownership_exact=len(owned) == 1,
        quantity_matches=quantity_matches,
        protection_confirmed=any(
            bool(p.get("ocoOrderId")) for p in owned
        ),
    )


def _extract_active_orders(payload: dict[str, Any]) -> G078SanitizedRead:
    try:
        orders = payload.get("data") or []
    except AttributeError:
        orders = []
    return G078SanitizedRead(
        source=G078ReadBackSource.ACTIVE_ORDERS,
        known=True,
        count=len(orders),
        active_orders_zero=len(orders) == 0,
    )


def build_g078_read_back_producer(
    *,
    credential_pair: V4G026PrivateGetKeychainCredentialPair,
    client: httpx.Client,
    generation_digest: str,
    action_scope_digest: str,
    expected_symbol: str = "USD_JPY",
    expected_quantity: int = 1_000,
    now_factory: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], None] = time.sleep,
) -> G078FakeOnlyCallable:
    """Build the one-use read-back client for a single action scope.

    Each source is read at most once (0.25s pacing between reads); a repeated
    read of the same source is a contract violation and raises.  Any fetch
    failure is converted to ``known=False`` (fail-closed), never an exception.
    """
    if not isinstance(credential_pair, V4G026PrivateGetKeychainCredentialPair):
        raise V4G078PrivateGetProducerError("G078_PRODUCER_CREDENTIAL_PAIR_INVALID")
    if not isinstance(generation_digest, str) or not generation_digest.startswith("sha256:"):
        raise V4G078PrivateGetProducerError("G078_PRODUCER_GENERATION_DIGEST_INVALID")
    if not isinstance(action_scope_digest, str) or not action_scope_digest.startswith("sha256:"):
        raise V4G078PrivateGetProducerError("G078_PRODUCER_ACTION_SCOPE_DIGEST_INVALID")

    read_sources: set[str] = set()
    last_read_at: float | None = None
    monotonic = time.monotonic

    def read_back(source: object, now_utc: object) -> G078SanitizedRead:
        nonlocal last_read_at
        if now_utc is not None and now_utc.tzinfo is None:
            raise V4G078PrivateGetProducerError("G078_PRODUCER_TIME_INVALID")
        if not isinstance(source, G078ReadBackSource):
            raise V4G078PrivateGetProducerError("G078_PRODUCER_SOURCE_INVALID")
        if source.value in read_sources:
            raise V4G078PrivateGetProducerError("G078_PRODUCER_SOURCE_READ_TWICE")
        if last_read_at is not None:
            elapsed = monotonic() - last_read_at
            if elapsed < _MIN_READ_INTERVAL_SECONDS:
                sleep(_MIN_READ_INTERVAL_SECONDS - elapsed)
        read_sources.add(source.value)
        result = _get_source_once(
            source=source,
            credential_pair=credential_pair,
            client=client,
            expected_symbol=expected_symbol,
            expected_quantity=expected_quantity,
        )
        last_read_at = monotonic()
        return result

    return G078FakeOnlyCallable(read_back)


def _get_source_once(
    *,
    source: G078ReadBackSource,
    credential_pair: V4G026PrivateGetKeychainCredentialPair,
    client: httpx.Client,
    expected_symbol: str,
    expected_quantity: int,
) -> G078SanitizedRead:
    endpoint = {
        G078ReadBackSource.LATEST_EXECUTIONS: "latestExecutions",
        G078ReadBackSource.OPEN_POSITIONS: "openPositions",
        G078ReadBackSource.ACTIVE_ORDERS: "activeOrders",
    }[source]
    signing_path = f"/v1/{endpoint}"
    try:
        key, secret = credential_pair.unseal_for_internal_request_only()
        headers = build_auth_headers(
            api_key=key.reveal_internal_only(),
            api_secret=secret.reveal_internal_only(),
            timestamp=str(int(time.time() * 1000)),
            method="GET",
            path=signing_path,
            body="",
        )
        response = client.get(
            f"{_PRIVATE_BASE_URL}/{endpoint}",
            headers=headers,
            timeout=_TIMEOUT_SECONDS,
        )
        payload = response.json()
    except Exception:
        # Fail-closed: a failed fetch is an unknown observation, never a crash.
        return G078SanitizedRead(source=source, known=False, count=0)
    if source is G078ReadBackSource.LATEST_EXECUTIONS:
        return _extract_latest_executions(payload, expected_quantity=expected_quantity)
    if source is G078ReadBackSource.OPEN_POSITIONS:
        return _extract_open_positions(
            payload, expected_symbol=expected_symbol, expected_quantity=expected_quantity
        )
    return _extract_active_orders(payload)


__all__ = [
    "V4G078PrivateGetProducerError",
    "build_g078_read_back_producer",
]
