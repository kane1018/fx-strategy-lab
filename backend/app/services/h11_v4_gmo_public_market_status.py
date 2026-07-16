"""One-shot sanitized GMO public market-status evidence for v4 time exits.

The reader performs at most one public GET, retains no raw response, and
returns an opaque generation-bound handle.  Only a fresh ``OPEN`` handle can
authorize removing server-side protection for the fixed time exit.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping
from enum import Enum
from typing import Any

import httpx

GMO_V4_PUBLIC_BASE_URL = "https://forex-api.coin.z.com"
GMO_V4_PUBLIC_STATUS_PATH = "/public/v1/status"
V4_GMO_PUBLIC_STATUS_MAX_AGE_SECONDS = 2.0


class V4GmoPublicMarketStatusError(RuntimeError):
    """Fixed fail-closed public status error."""


class V4GmoPublicMarketStatus(str, Enum):
    OPEN = "OPEN"
    NOT_OPEN = "NOT_OPEN"
    UNKNOWN = "UNKNOWN"


_PUBLIC_STATUS_EVIDENCE_TOKEN = object()


class V4GmoPublicMarketStatusEvidence:
    """Opaque one-use status evidence with no raw response fields."""

    __slots__ = (
        "_token",
        "_generation_digest",
        "_status",
        "_issued_monotonic",
        "_consumed",
    )

    def __init__(
        self,
        *,
        token: object,
        generation_digest: str,
        status: V4GmoPublicMarketStatus,
        issued_monotonic: float,
    ) -> None:
        if token is not _PUBLIC_STATUS_EVIDENCE_TOKEN:
            raise V4GmoPublicMarketStatusError(
                "V4_PUBLIC_MARKET_STATUS_EVIDENCE_INVALID"
            )
        self._token = token
        self._generation_digest = generation_digest
        self._status = status
        self._issued_monotonic = issued_monotonic
        self._consumed = False

    def require_fresh_open(
        self,
        *,
        generation_digest: str,
        now_monotonic: float,
    ) -> None:
        age = now_monotonic - self._issued_monotonic
        valid = (
            type(self) is V4GmoPublicMarketStatusEvidence
            and self._token is _PUBLIC_STATUS_EVIDENCE_TOKEN
            and not self._consumed
            and self._generation_digest == generation_digest
            and math.isfinite(now_monotonic)
            and 0 <= age <= V4_GMO_PUBLIC_STATUS_MAX_AGE_SECONDS
        )
        self._consumed = True
        if not valid:
            raise V4GmoPublicMarketStatusError(
                "V4_PUBLIC_MARKET_STATUS_EVIDENCE_INVALID"
            )
        if self._status is not V4GmoPublicMarketStatus.OPEN:
            raise V4GmoPublicMarketStatusError(
                "V4_PUBLIC_MARKET_STATUS_NOT_OPEN"
            )

    def __repr__(self) -> str:
        return "V4GmoPublicMarketStatusEvidence(<sanitized-one-use>)"

    def __bool__(self) -> bool:
        return False


class V4GmoPublicMarketStatusReader:
    """Read the official public status endpoint exactly once, without retry."""

    def __init__(
        self,
        *,
        generation_digest: str,
        client: httpx.Client | None = None,
        monotonic_factory: Callable[[], float] = time.monotonic,
    ) -> None:
        self._generation_digest = generation_digest
        self._client = client
        self._monotonic = monotonic_factory
        self._used = False

    def read_once(self) -> V4GmoPublicMarketStatusEvidence:
        if self._used:
            raise V4GmoPublicMarketStatusError(
                "V4_PUBLIC_MARKET_STATUS_SECOND_READ_FORBIDDEN"
            )
        self._used = True
        issued = float(self._monotonic())
        if not math.isfinite(issued) or issued < 0:
            raise V4GmoPublicMarketStatusError(
                "V4_PUBLIC_MARKET_STATUS_CLOCK_INVALID"
            )
        client = self._client or httpx.Client(
            base_url=GMO_V4_PUBLIC_BASE_URL,
            timeout=5.0,
        )
        owns_client = self._client is None
        status = V4GmoPublicMarketStatus.UNKNOWN
        try:
            try:
                response = client.get(GMO_V4_PUBLIC_STATUS_PATH)
                status = _sanitized_status(response)
            except httpx.HTTPError:
                status = V4GmoPublicMarketStatus.UNKNOWN
        finally:
            if owns_client:
                client.close()
        return V4GmoPublicMarketStatusEvidence(
            token=_PUBLIC_STATUS_EVIDENCE_TOKEN,
            generation_digest=self._generation_digest,
            status=status,
            issued_monotonic=issued,
        )

    def __repr__(self) -> str:
        return "V4GmoPublicMarketStatusReader(<one-shot-sanitized>)"

    def __bool__(self) -> bool:
        return False


def _sanitized_status(response: httpx.Response) -> V4GmoPublicMarketStatus:
    if response.status_code != 200:
        return V4GmoPublicMarketStatus.UNKNOWN
    try:
        payload: Any = response.json()
    except ValueError:
        return V4GmoPublicMarketStatus.UNKNOWN
    if not isinstance(payload, Mapping) or payload.get("status") != 0:
        return V4GmoPublicMarketStatus.UNKNOWN
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return V4GmoPublicMarketStatus.UNKNOWN
    value = data.get("status")
    if value == "OPEN":
        return V4GmoPublicMarketStatus.OPEN
    if value in {"CLOSE", "MAINTENANCE"}:
        return V4GmoPublicMarketStatus.NOT_OPEN
    return V4GmoPublicMarketStatus.UNKNOWN
