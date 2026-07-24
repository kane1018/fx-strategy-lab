"""H-11 v4 unattended shadow Private-GET account/order preflight (slice 1).

This module derives the ``broker_snapshot_fresh`` / ``boot_reconciled`` /
``position_count`` / ``active_order_count`` fields of a shadow preflight from a
sanitized, generation-independent, GET-only Private API read of
``latestExecutions``, ``openPositions``, and ``activeOrders``. It is
deliberately narrower than a full operational preflight: notification
readiness, daily/monthly/consecutive-loss-stop tracking, host/dead-man state,
and operator persistent HALT are out of scope here and are never touched by the
composer below.

No real Keychain reader ships in this module. ``read_v4_unattended_shadow_private_snapshot``
requires the caller to supply both an already-unsealed credential pair and an
``httpx.Client``; neither argument has a default, so there is no path from this
module's own defaults to real credential material or a real network
destination. Requests are issued against caller-supplied relative paths, so the
caller's own ``httpx.Client(base_url=...)`` is always the actual destination --
this module never hardcodes or falls back to the real GMO host internally.
Every test in this codebase uses a fake credential pair and a fake ``httpx``
transport. This module is not wired into the shadow runner CLI; real
activation is a separate, explicitly authorized future change.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any, Protocol, runtime_checkable

import httpx

from app.h11_auto.v4_gmo_contracts import V4GmoPreflightSnapshot
from app.private_api.auth import build_auth_headers

GMO_V4_PRIVATE_BASE_URL = "https://forex-api.coin.z.com"
# Reference only: this module never constructs a client against this URL
# itself. A caller who wants the real destination must configure their own
# injected ``httpx.Client(base_url=GMO_V4_PRIVATE_BASE_URL)``.
# Each entry is (transport_path, signing_path, params): GMO signs the path
# without the "/private" prefix while the actual request path includes it.
_READ_SEQUENCE = (
    (
        "/private/v1/latestExecutions",
        "/v1/latestExecutions",
        (("symbol", "USD_JPY"), ("count", "100")),
    ),
    (
        "/private/v1/openPositions",
        "/v1/openPositions",
        (("count", "100"),),
    ),
    (
        "/private/v1/activeOrders",
        "/v1/activeOrders",
        (("count", "100"),),
    ),
)
_READ_CADENCE_SECONDS = 0.25


class V4UnattendedShadowPrivateError(RuntimeError):
    """Fixed safe Private-GET preflight failure; messages carry safe labels only."""


@dataclass(frozen=True, repr=False)
class V4UnattendedShadowSealedSecret:
    _value: str

    def reveal_internal_only(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "V4UnattendedShadowSealedSecret(***)"

    def __str__(self) -> str:
        return "***"

    def __bool__(self) -> bool:
        return False


@runtime_checkable
class V4UnattendedShadowCredentialPair(Protocol):
    """Structural credential source. No concrete implementation ships here."""

    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4UnattendedShadowSealedSecret, V4UnattendedShadowSealedSecret]: ...


@dataclass(frozen=True, repr=False)
class V4UnattendedShadowPrivateSnapshot:
    status: str
    credential_read_performed: bool
    broker_read_performed: bool
    broker_get_count: int
    latest_executions_count: int
    open_positions_count: int
    active_orders_count: int
    account_flat: bool
    active_orders_zero: bool
    raw_response_retained: bool = False
    identifier_exposed: bool = False
    broker_write_performed: bool = False
    broker_post_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.status, str) or not self.status:
            raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_SNAPSHOT_STATUS_INVALID")
        boolean_fields = (
            self.credential_read_performed,
            self.broker_read_performed,
            self.account_flat,
            self.active_orders_zero,
        )
        if any(type(value) is not bool for value in boolean_fields):
            raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_SNAPSHOT_FLAG_INVALID")
        count_fields = (
            self.broker_get_count,
            self.latest_executions_count,
            self.open_positions_count,
            self.active_orders_count,
        )
        if any(type(value) is not int or value < 0 for value in count_fields):
            raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_SNAPSHOT_COUNT_INVALID")
        if self.broker_get_count != 3:
            raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_SNAPSHOT_GET_COUNT_INVALID")
        if self.account_flat != (self.open_positions_count == 0):
            raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_SNAPSHOT_FLAT_MISMATCH")
        if self.active_orders_zero != (self.active_orders_count == 0):
            raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_SNAPSHOT_ZERO_MISMATCH")
        if (
            self.raw_response_retained
            or self.identifier_exposed
            or self.broker_write_performed
            or type(self.broker_post_count) is not int
            or self.broker_post_count != 0
        ):
            raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_SNAPSHOT_CANNOT_CLAIM_WRITE")

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __repr__(self) -> str:
        return "V4UnattendedShadowPrivateSnapshot(<sanitized-read-only>)"

    def __bool__(self) -> bool:
        return False


def read_v4_unattended_shadow_private_snapshot(
    *,
    credential_pair: V4UnattendedShadowCredentialPair,
    client: httpx.Client,
    monotonic_factory: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> V4UnattendedShadowPrivateSnapshot:
    """Perform the fixed 3-GET sequence once; never retries within a call.

    The caller controls both credential sourcing and the network destination:
    this module has no default that can reach real Keychain material, and it
    never constructs its own client or hardcodes a request-time host -- every
    request path is relative, so it always resolves against the caller's own
    ``client.base_url``. The caller owns the client's lifecycle (this function
    never closes it).
    """

    if not isinstance(credential_pair, V4UnattendedShadowCredentialPair):
        raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_CREDENTIAL_CONTRACT_INVALID")
    try:
        key, secret = credential_pair.unseal_for_internal_request_only()
    except V4UnattendedShadowPrivateError:
        raise
    except Exception:  # noqa: BLE001
        raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_CREDENTIAL_UNAVAILABLE") from None
    if not isinstance(key, V4UnattendedShadowSealedSecret) or not isinstance(
        secret, V4UnattendedShadowSealedSecret
    ):
        raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_CREDENTIAL_CONTRACT_INVALID")

    started = float(monotonic_factory())
    if not math.isfinite(started) or started < 0:
        raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_GET_CADENCE_CLOCK_INVALID")
    counts: list[int] = []
    previous_request_started: float | None = None
    for index, (transport_path, signing_path, parameter_pairs) in enumerate(_READ_SEQUENCE):
        target_offset = index * _READ_CADENCE_SECONDS
        now = float(monotonic_factory())
        if (
            not math.isfinite(now)
            or now < started
            or (previous_request_started is not None and now < previous_request_started)
        ):
            raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_GET_CADENCE_CLOCK_INVALID")
        minimum_start = started + target_offset
        if previous_request_started is not None:
            minimum_start = max(
                minimum_start, previous_request_started + _READ_CADENCE_SECONDS
            )
        if now < minimum_start:
            sleep(minimum_start - now)
        request_started = float(monotonic_factory())
        if (
            not math.isfinite(request_started)
            or request_started < minimum_start
            or (
                previous_request_started is not None
                and request_started < previous_request_started + _READ_CADENCE_SECONDS
            )
        ):
            # The requested sleep did not actually advance the clock enough
            # (interrupted sleep, broken clock, or a future implementer's
            # mistake) -- fail closed instead of firing requests too close
            # together.
            raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_GET_CADENCE_NOT_REACHED")
        previous_request_started = request_started
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
                transport_path,
                params=dict(parameter_pairs),
                headers={**headers, "Accept": "application/json"},
            )
        except httpx.HTTPError:
            # `from None`: the original exception's `.request.headers` carries
            # the real signed API-KEY value; it must never be reachable via
            # `__cause__` (e.g. from an APM/error-tracking integration).
            raise V4UnattendedShadowPrivateError(
                "SHADOW_PRIVATE_GET_NETWORK_FAILED_NO_RETRY"
            ) from None
        counts.append(_sanitized_count(response))
    if len(counts) != 3:
        raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_SEQUENCE_INCOMPLETE")
    open_positions_count, active_orders_count = counts[1], counts[2]
    return V4UnattendedShadowPrivateSnapshot(
        status="SHADOW_PRIVATE_SNAPSHOT_OBSERVED",
        credential_read_performed=True,
        broker_read_performed=True,
        broker_get_count=3,
        latest_executions_count=counts[0],
        open_positions_count=open_positions_count,
        active_orders_count=active_orders_count,
        account_flat=(open_positions_count == 0),
        active_orders_zero=(active_orders_count == 0),
    )


def _sanitized_count(response: httpx.Response) -> int:
    if response.status_code != 200:
        raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_GET_HTTP_FAILED_NO_RETRY")
    try:
        payload = response.json()
    except ValueError:
        # `from None`: a JSONDecodeError's `.doc` holds the entire raw broker
        # response body, which this module guarantees is never retained
        # (`raw_response_retained=False`).
        raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_GET_RESPONSE_INVALID") from None
    if not isinstance(payload, Mapping) or payload.get("status") != 0:
        raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_GET_RESPONSE_REJECTED")
    data: Any = payload.get("data")
    if data is None:
        return 0
    if isinstance(data, Sequence) and not isinstance(data, str | bytes | bytearray):
        rows = data
    elif isinstance(data, Mapping) and isinstance(data.get("list"), list):
        rows = data["list"]
    else:
        raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_GET_SCHEMA_INVALID")
    if any(not isinstance(row, Mapping) for row in rows):
        raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_GET_ROW_INVALID")
    return len(rows)


def augment_shadow_preflight_with_private_snapshot(
    *,
    base: V4GmoPreflightSnapshot,
    private: V4UnattendedShadowPrivateSnapshot,
) -> V4GmoPreflightSnapshot:
    """Replace only the Private-GET-observable fields of ``base``.

    ``boot_reconciled`` here means "a fresh, structurally valid Private
    snapshot was obtained this cycle" -- it is not a persisted restart
    reconciliation guarantee. ``notification_path_ready`` and the
    daily/monthly/consecutive-loss-stop/operator-HALT fields are deliberately
    left untouched; they keep whatever value ``base`` already carried.
    """

    if type(base) is not V4GmoPreflightSnapshot or type(private) is not (
        V4UnattendedShadowPrivateSnapshot
    ):
        raise V4UnattendedShadowPrivateError("SHADOW_PRIVATE_COMPOSE_INPUT_INVALID")
    return replace(
        base,
        boot_reconciled=True,
        broker_snapshot_fresh=True,
        position_count=private.open_positions_count,
        active_order_count=private.active_orders_count,
    )
