"""One finite H-11 v4 GMO Private GET preparation rehearsal.

This module is structurally read-only: it accepts no method or route from a
caller and contains no broker POST operation.  Broker identifiers and raw
responses are consumed only in process memory and are never returned.
"""

from __future__ import annotations

import platform
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import httpx

from app.h11_auto.v4_actual_preparation_guard import (
    V4ExternalPreparationGate,
    V4PreparationOperation,
    V4PreparationOperationPermit,
    require_external_preparation_gate,
    require_operation_permit,
)
from app.private_api.auth import build_auth_headers

GMO_V4_PRIVATE_BASE_URL = "https://forex-api.coin.z.com"
GMO_V4_KEYCHAIN_SERVICE = "fx-strategy-lab-h11-v4-actual"
GMO_V4_API_KEY_ACCOUNT = "gmo-fx-api-key"
GMO_V4_API_SECRET_ACCOUNT = "gmo-fx-api-secret"
KEYCHAIN_PROMPT_TIMEOUT_SECONDS = 120.0

_READ_SEQUENCE = (
    ("/private/v1/latestExecutions", "/v1/latestExecutions"),
    ("/private/v1/openPositions", "/v1/openPositions"),
    ("/private/v1/activeOrders", "/v1/activeOrders"),
)


class V4GmoReadOnlyPreflightError(RuntimeError):
    """Fixed safe preflight failure."""


@dataclass(frozen=True, repr=False)
class V4GmoReadOnlySealedSecret:
    _value: str

    def reveal_internal_only(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "V4GmoReadOnlySealedSecret(***)"

    def __str__(self) -> str:
        return "***"

    def __bool__(self) -> bool:
        return False


class V4GmoReadOnlySealedCredentialPair(Protocol):
    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4GmoReadOnlySealedSecret, V4GmoReadOnlySealedSecret]: ...


ReadOnlySecretReader = Callable[[str, str], V4GmoReadOnlySealedSecret]


def read_v4_gmo_readonly_keychain_secret(
    service: str,
    account: str,
    *,
    timeout_seconds: float = KEYCHAIN_PROMPT_TIMEOUT_SECONDS,
) -> V4GmoReadOnlySealedSecret:
    if platform.system() != "Darwin":
        raise V4GmoReadOnlyPreflightError("PRIVATE_GET_KEYCHAIN_PLATFORM_UNSUPPORTED")
    if service != GMO_V4_KEYCHAIN_SERVICE or account not in {
        GMO_V4_API_KEY_ACCOUNT,
        GMO_V4_API_SECRET_ACCOUNT,
    }:
        raise V4GmoReadOnlyPreflightError("PRIVATE_GET_KEYCHAIN_ITEM_NOT_ALLOWED")
    try:
        completed = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise V4GmoReadOnlyPreflightError("PRIVATE_GET_KEYCHAIN_READ_FAILED") from None
    if completed.returncode != 0:
        raise V4GmoReadOnlyPreflightError("PRIVATE_GET_KEYCHAIN_ITEM_UNAVAILABLE")
    value = completed.stdout.rstrip("\n")
    if not value:
        raise V4GmoReadOnlyPreflightError("PRIVATE_GET_KEYCHAIN_ITEM_EMPTY")
    return V4GmoReadOnlySealedSecret(value)


@dataclass(frozen=True, repr=False)
class V4GmoReadOnlyKeychainCredentialPair:
    reader: ReadOnlySecretReader = read_v4_gmo_readonly_keychain_secret

    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4GmoReadOnlySealedSecret, V4GmoReadOnlySealedSecret]:
        key = self.reader(GMO_V4_KEYCHAIN_SERVICE, GMO_V4_API_KEY_ACCOUNT)
        secret = self.reader(GMO_V4_KEYCHAIN_SERVICE, GMO_V4_API_SECRET_ACCOUNT)
        if not isinstance(key, V4GmoReadOnlySealedSecret) or not isinstance(
            secret, V4GmoReadOnlySealedSecret
        ):
            raise V4GmoReadOnlyPreflightError("PRIVATE_GET_KEYCHAIN_CONTRACT_INVALID")
        return key, secret

    def __repr__(self) -> str:
        return "V4GmoReadOnlyKeychainCredentialPair(***)"

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4GmoReadOnlyPreflightReport:
    status: str
    keychain_items_present: bool
    credential_read_count: int
    broker_get_count: int
    latest_executions_count: int
    usd_jpy_open_positions_count: int
    usd_jpy_active_orders_count: int
    usd_jpy_flat: bool
    usd_jpy_active_orders_zero: bool
    limited_usd_jpy_snapshot_clear: bool
    account_wide_exclusivity_proven: bool
    canary_preflight_clear: bool
    cadence_offsets_seconds: tuple[float, float, float]
    raw_response_retained: bool = False
    identifier_exposed: bool = False
    broker_post_count: int = 0
    broker_write_performed: bool = False
    activation_permit_issued: bool = False

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __bool__(self) -> bool:
        return False


class V4GmoFiniteReadOnlyPreflight:
    def __init__(
        self,
        *,
        external_gate: V4ExternalPreparationGate,
        operation_permit: V4PreparationOperationPermit,
        credential_pair: V4GmoReadOnlySealedCredentialPair | None = None,
        client: httpx.Client | None = None,
        monotonic_factory: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        require_external_preparation_gate(external_gate)
        self._operation_permit = operation_permit
        self._credential_pair = (
            credential_pair
            if credential_pair is not None
            else V4GmoReadOnlyKeychainCredentialPair()
        )
        self._client = client
        self._monotonic = monotonic_factory
        self._sleep = sleep
        self._used = False

    def run_once(self) -> V4GmoReadOnlyPreflightReport:
        if self._used:
            raise V4GmoReadOnlyPreflightError("PRIVATE_GET_PREFLIGHT_SECOND_RUN_FORBIDDEN")
        self._used = True
        require_operation_permit(
            self._operation_permit,
            expected_operation=V4PreparationOperation.PRIVATE_GET,
            consume=True,
        )
        try:
            key, secret = self._credential_pair.unseal_for_internal_request_only()
        except V4GmoReadOnlyPreflightError:
            raise
        except Exception:  # noqa: BLE001
            raise V4GmoReadOnlyPreflightError("PRIVATE_GET_KEYCHAIN_UNAVAILABLE") from None
        if not isinstance(key, V4GmoReadOnlySealedSecret) or not isinstance(
            secret, V4GmoReadOnlySealedSecret
        ):
            raise V4GmoReadOnlyPreflightError("PRIVATE_GET_KEYCHAIN_CONTRACT_INVALID")
        client = self._client or httpx.Client(
            base_url=GMO_V4_PRIVATE_BASE_URL,
            timeout=10.0,
        )
        owns_client = self._client is None
        started = self._monotonic()
        counts: list[int] = []
        observed_offsets: list[float] = []
        previous_request_started: float | None = None
        try:
            for index, (transport_path, signing_path) in enumerate(_READ_SEQUENCE):
                target_offset = index * 0.25
                now = self._monotonic()
                minimum_start = started + target_offset
                if previous_request_started is not None:
                    minimum_start = max(minimum_start, previous_request_started + 0.25)
                if now < minimum_start:
                    self._sleep(minimum_start - now)
                request_started = self._monotonic()
                observed_offsets.append(max(0.0, request_started - started))
                previous_request_started = request_started
                params = {"symbol": "USD_JPY", "count": "100"}
                headers = build_auth_headers(
                    api_key=key.reveal_internal_only(),
                    api_secret=secret.reveal_internal_only(),
                    timestamp=str(int(time.time() * 1000)),
                    method="GET",
                    path=signing_path,
                    body="",
                )
                try:
                    response = client.request(
                        "GET",
                        f"{GMO_V4_PRIVATE_BASE_URL}{transport_path}",
                        params=params,
                        headers={**headers, "Accept": "application/json"},
                    )
                except httpx.HTTPError:
                    raise V4GmoReadOnlyPreflightError(
                        "PRIVATE_GET_NETWORK_FAILED_NO_RETRY"
                    ) from None
                counts.append(_sanitized_count(response))
        finally:
            if owns_client:
                client.close()
        if len(counts) != 3:
            raise V4GmoReadOnlyPreflightError("PRIVATE_GET_SEQUENCE_INCOMPLETE")
        flat = counts[1] == 0
        zero_active = counts[2] == 0
        limited_clear = flat and zero_active
        return V4GmoReadOnlyPreflightReport(
            status=(
                "PASSED_LIMITED_USD_JPY_READ_ONLY_SNAPSHOT_NOT_CANARY_CLEAR"
                if limited_clear
                else "BLOCKED_LIMITED_USD_JPY_READ_ONLY_SNAPSHOT_NOT_CLEAR"
            ),
            keychain_items_present=True,
            credential_read_count=2,
            broker_get_count=3,
            latest_executions_count=counts[0],
            usd_jpy_open_positions_count=counts[1],
            usd_jpy_active_orders_count=counts[2],
            usd_jpy_flat=flat,
            usd_jpy_active_orders_zero=zero_active,
            limited_usd_jpy_snapshot_clear=limited_clear,
            account_wide_exclusivity_proven=False,
            canary_preflight_clear=False,
            cadence_offsets_seconds=tuple(observed_offsets),  # type: ignore[arg-type]
        )

    def __repr__(self) -> str:
        return "V4GmoFiniteReadOnlyPreflight(<redacted>)"

    def __bool__(self) -> bool:
        return False


def _sanitized_count(response: httpx.Response) -> int:
    if response.status_code != 200:
        raise V4GmoReadOnlyPreflightError("PRIVATE_GET_HTTP_FAILED_NO_RETRY")
    try:
        payload = response.json()
    except ValueError:
        raise V4GmoReadOnlyPreflightError("PRIVATE_GET_RESPONSE_INVALID") from None
    if not isinstance(payload, Mapping) or payload.get("status") != 0:
        raise V4GmoReadOnlyPreflightError("PRIVATE_GET_RESPONSE_REJECTED")
    data: Any = payload.get("data")
    if data is None:
        return 0
    if isinstance(data, Sequence) and not isinstance(data, str | bytes | bytearray):
        rows = data
    elif isinstance(data, Mapping) and isinstance(data.get("list"), list):
        rows = data["list"]
    else:
        raise V4GmoReadOnlyPreflightError("PRIVATE_GET_SCHEMA_INVALID")
    if any(not isinstance(row, Mapping) for row in rows):
        raise V4GmoReadOnlyPreflightError("PRIVATE_GET_ROW_INVALID")
    return len(rows)
