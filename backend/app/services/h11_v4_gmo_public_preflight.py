"""Finite sanitized GMO public status+ticker preparation for H-11 v4.

The official ticker endpoint returns all symbols and accepts no symbol query.
This reader performs exactly two GETs, selects USD_JPY in memory, and exposes
only safe aggregate fields.  It has no retry and no broker-write capability.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path

import httpx

from app.h11_auto.v4_actual_preparation_guard import (
    V4ExternalPreparationGate,
    V4PreparationOperation,
    V4PreparationOperationPermit,
    _attest_public_get_success_internal,
    require_external_preparation_gate,
    require_operation_permit,
)

GMO_V4_PUBLIC_BASE_URL = "https://forex-api.coin.z.com"
GMO_V4_PUBLIC_STATUS_PATH = "/public/v1/status"
GMO_V4_PUBLIC_TICKER_PATH = "/public/v1/ticker"
GMO_V4_PUBLIC_SYMBOL = "USD_JPY"
MAXIMUM_QUOTE_AGE_SECONDS = 5.0
G013_MAXIMUM_ENTRY_SPREAD_PIPS = Decimal("0.5")


class V4GmoPublicPreflightError(RuntimeError):
    """Fixed safe public-preflight failure."""


class V4GmoG013PublicOperation(str, Enum):
    """Distinct generation-bound public operations; none is a retry."""

    FORMAL_CANDLES = "formal-candles"
    REFERENCE_QUOTE = "reference-quote"
    FINAL_QUOTE = "final-quote"


@dataclass(frozen=True, repr=False)
class V4GmoG013PublicOperationLedger:
    """Persist a claim before the first byte of each G013 public operation."""

    state_root: Path
    generation_digest: str

    def __post_init__(self) -> None:
        root = self.state_root.resolve()
        if (
            self.state_root.is_symlink()
            or not self.generation_digest.startswith("sha256:")
            or len(self.generation_digest) != 71
        ):
            raise V4GmoPublicPreflightError("G013_PUBLIC_LEDGER_INVALID")
        root.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "state_root", root)

    def claim_once(self, operation: V4GmoG013PublicOperation) -> None:
        if type(operation) is not V4GmoG013PublicOperation:  # noqa: E721
            raise V4GmoPublicPreflightError("G013_PUBLIC_OPERATION_INVALID")
        path = self.state_root / f"g013-public-{operation.value}-attempted.json"
        payload = (
            '{"generation_digest":"'
            + self.generation_digest
            + '","operation":"'
            + operation.value
            + '","status":"ATTEMPTED_NO_RETRY"}\n'
        )
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            directory = os.open(self.state_root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except FileExistsError as error:
            raise V4GmoPublicPreflightError(
                "G013_PUBLIC_OPERATION_ALREADY_ATTEMPTED_NO_RETRY"
            ) from error
        except OSError as error:
            raise V4GmoPublicPreflightError("G013_PUBLIC_OPERATION_CLAIM_FAILED") from error

    def __repr__(self) -> str:
        return "V4GmoG013PublicOperationLedger(<generation-bound-no-retry>)"

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4GmoPublicPreflightReport:
    status: str
    public_get_count: int
    market_open: bool
    ticker_symbol_match: bool
    ticker_status_open: bool
    quote_fresh: bool
    spread_within_limit: bool
    quote_age_seconds: float
    spread_pips: str
    raw_response_retained: bool = False
    identifier_exposed: bool = False
    broker_post_count: int = 0
    broker_write_performed: bool = False
    activation_permit_issued: bool = False

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __bool__(self) -> bool:
        return False


class V4GmoFinitePublicPreflight:
    """Perform one fixed status+ticker sequence without retry."""

    def __init__(
        self,
        *,
        external_gate: V4ExternalPreparationGate,
        operation_permit: V4PreparationOperationPermit,
        client: httpx.Client | None = None,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        require_external_preparation_gate(external_gate)
        self._operation_permit = operation_permit
        self._client = client
        self._wall_clock = wall_clock
        self._used = False

    def run_once(self) -> V4GmoPublicPreflightReport:
        if self._used:
            raise V4GmoPublicPreflightError("PUBLIC_GET_SECOND_RUN_FORBIDDEN")
        self._used = True
        require_operation_permit(
            self._operation_permit,
            expected_operation=V4PreparationOperation.PUBLIC_GET,
            claim=True,
        )
        client = self._client or httpx.Client(
            base_url=GMO_V4_PUBLIC_BASE_URL,
            timeout=5.0,
        )
        owns_client = self._client is None
        try:
            status_response = self._get_once(client, GMO_V4_PUBLIC_STATUS_PATH)
            market_open = _market_open(status_response)
            ticker_response = self._get_once(client, GMO_V4_PUBLIC_TICKER_PATH)
            ticker = _usd_jpy_ticker(ticker_response)
        finally:
            if owns_client:
                client.close()
        now = self._wall_clock()
        if now.tzinfo is None:
            raise V4GmoPublicPreflightError("PUBLIC_GET_CLOCK_INVALID")
        age = (now.astimezone(UTC) - ticker.timestamp.astimezone(UTC)).total_seconds()
        fresh = math.isfinite(age) and 0.0 <= age <= MAXIMUM_QUOTE_AGE_SECONDS
        spread = (ticker.ask - ticker.bid) / Decimal("0.01")
        if spread < 0:
            raise V4GmoPublicPreflightError("PUBLIC_GET_TICKER_INVALID")
        report = V4GmoPublicPreflightReport(
            status=(
                "PASSED_PUBLIC_STATUS_TICKER_SANITIZED_NO_BROKER_POST"
                if (
                    market_open
                    and ticker.status_open
                    and fresh
                    and spread <= G013_MAXIMUM_ENTRY_SPREAD_PIPS
                )
                else "BLOCKED_PUBLIC_STATUS_TICKER_NOT_CLEAR"
            ),
            public_get_count=2,
            market_open=market_open,
            ticker_symbol_match=True,
            ticker_status_open=ticker.status_open,
            quote_fresh=fresh,
            spread_within_limit=(spread <= G013_MAXIMUM_ENTRY_SPREAD_PIPS),
            quote_age_seconds=round(age, 6),
            spread_pips=format(spread.normalize(), "f"),
        )
        if report.status.startswith("PASSED_"):
            _attest_public_get_success_internal(
                self._operation_permit,
                report.to_safe_dict(),
            )
        return report

    @staticmethod
    def _get_once(client: httpx.Client, path: str) -> httpx.Response:
        try:
            return client.request("GET", f"{GMO_V4_PUBLIC_BASE_URL}{path}")
        except httpx.HTTPError:
            raise V4GmoPublicPreflightError("PUBLIC_GET_NETWORK_FAILED_NO_RETRY") from None

    def __repr__(self) -> str:
        return "V4GmoFinitePublicPreflight(<sanitized-one-use>)"

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class _Ticker:
    bid: Decimal
    ask: Decimal
    timestamp: datetime
    status_open: bool


@dataclass(frozen=True, repr=False)
class V4GmoG013FinalQuote:
    bid: Decimal
    ask: Decimal
    observed_at_utc: datetime
    spread_pips: Decimal
    market_open: bool
    quote_fresh: bool
    spread_within_limit: bool
    public_get_count: int = 2
    broker_post_count: int = 0

    def __post_init__(self) -> None:
        if (
            not self.bid.is_finite()
            or not self.ask.is_finite()
            or self.bid <= 0
            or self.ask < self.bid
            or self.observed_at_utc.tzinfo is None
            or self.public_get_count != 2
            or self.broker_post_count != 0
        ):
            raise V4GmoPublicPreflightError("G013_FINAL_QUOTE_INVALID")

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "bid": format(self.bid.normalize(), "f"),
            "ask": format(self.ask.normalize(), "f"),
            "spread_pips": format(self.spread_pips.normalize(), "f"),
            "maximum_spread_pips": format(G013_MAXIMUM_ENTRY_SPREAD_PIPS.normalize(), "f"),
            "market_open": self.market_open,
            "quote_fresh": self.quote_fresh,
            "spread_within_limit": self.spread_within_limit,
            "public_get_count": self.public_get_count,
            "broker_post_count": 0,
        }

    def __repr__(self) -> str:
        return "V4GmoG013FinalQuote(<sanitized-current-market>)"

    def __bool__(self) -> bool:
        return False


def read_g013_final_quote_once(
    *,
    operation_ledger: V4GmoG013PublicOperationLedger,
    operation: V4GmoG013PublicOperation,
    client: httpx.Client | None = None,
    wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> V4GmoG013FinalQuote:
    """Read one final status+ticker pair for G013; never retry or write."""

    operation_ledger.claim_once(operation)
    selected = client or httpx.Client(timeout=5.0)
    owns_client = client is None
    try:
        status_response = V4GmoFinitePublicPreflight._get_once(selected, GMO_V4_PUBLIC_STATUS_PATH)
        ticker_response = V4GmoFinitePublicPreflight._get_once(selected, GMO_V4_PUBLIC_TICKER_PATH)
        market_open = _market_open(status_response)
        ticker = _usd_jpy_ticker(ticker_response)
    finally:
        if owns_client:
            selected.close()
    now = wall_clock()
    if now.tzinfo is None:
        raise V4GmoPublicPreflightError("G013_FINAL_QUOTE_CLOCK_INVALID")
    age = (now.astimezone(UTC) - ticker.timestamp.astimezone(UTC)).total_seconds()
    fresh = math.isfinite(age) and 0 <= age <= MAXIMUM_QUOTE_AGE_SECONDS
    spread = (ticker.ask - ticker.bid) / Decimal("0.01")
    quote = V4GmoG013FinalQuote(
        bid=ticker.bid,
        ask=ticker.ask,
        observed_at_utc=ticker.timestamp.astimezone(UTC),
        spread_pips=spread,
        market_open=market_open and ticker.status_open,
        quote_fresh=fresh,
        spread_within_limit=(spread >= 0 and spread <= G013_MAXIMUM_ENTRY_SPREAD_PIPS),
    )
    if not quote.market_open or not quote.quote_fresh or not quote.spread_within_limit:
        raise V4GmoPublicPreflightError("G013_FINAL_QUOTE_GATE_BLOCKED")
    return quote


def _payload(response: httpx.Response) -> object:
    if response.status_code != 200:
        raise V4GmoPublicPreflightError("PUBLIC_GET_HTTP_FAILED_NO_RETRY")
    try:
        payload = response.json()
    except ValueError:
        raise V4GmoPublicPreflightError("PUBLIC_GET_RESPONSE_INVALID") from None
    if not isinstance(payload, Mapping) or payload.get("status") != 0:
        raise V4GmoPublicPreflightError("PUBLIC_GET_RESPONSE_REJECTED")
    return payload.get("data")


def _market_open(response: httpx.Response) -> bool:
    data = _payload(response)
    if not isinstance(data, Mapping):
        raise V4GmoPublicPreflightError("PUBLIC_GET_STATUS_SCHEMA_INVALID")
    return data.get("status") == "OPEN"


def _usd_jpy_ticker(response: httpx.Response) -> _Ticker:
    data = _payload(response)
    if not isinstance(data, Sequence) or isinstance(data, str | bytes | bytearray):
        raise V4GmoPublicPreflightError("PUBLIC_GET_TICKER_SCHEMA_INVALID")
    matches = [
        row
        for row in data
        if isinstance(row, Mapping) and row.get("symbol") == GMO_V4_PUBLIC_SYMBOL
    ]
    if len(matches) != 1:
        raise V4GmoPublicPreflightError("PUBLIC_GET_TICKER_SYMBOL_INVALID")
    row = matches[0]
    try:
        bid = Decimal(str(row.get("bid")))
        ask = Decimal(str(row.get("ask")))
        timestamp = datetime.fromisoformat(str(row.get("timestamp")).replace("Z", "+00:00"))
    except (InvalidOperation, ValueError):
        raise V4GmoPublicPreflightError("PUBLIC_GET_TICKER_INVALID") from None
    if not bid.is_finite() or not ask.is_finite() or timestamp.tzinfo is None:
        raise V4GmoPublicPreflightError("PUBLIC_GET_TICKER_INVALID")
    return _Ticker(
        bid=bid,
        ask=ask,
        timestamp=timestamp,
        status_open=row.get("status") == "OPEN",
    )
