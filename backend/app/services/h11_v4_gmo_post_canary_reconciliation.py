"""G013 post-canary reconciliation with a fixed read-only broker surface.

This module is independent from the entry, protection, and exit paths. It owns
no action plan, activation permit, or mutable broker transport. The concrete
client can perform only three fixed private GET operations.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_gmo_actual_transport import (
    GMO_V4_PRIVATE_BASE_URL,
    GMO_V4_PRIVATE_HTTP_TIMEOUT_SECONDS,
    V4GmoActualTransportError,
    V4GmoKeychainCredentialPair,
    V4GmoPrivateRequest,
    V4GmoSignedRequestFactory,
)

_CONTRACT_PATH = Path("docs/templates/h11_v4_g013_post_canary_reconciliation.json")
_ENTRY_PREFIX = "H11V4E"
_ENDPOINTS = (
    (
        "latest_executions",
        "/private/v1/latestExecutions",
        "/v1/latestExecutions",
        {"symbol": "USD_JPY", "count": "100"},
    ),
    (
        "open_positions",
        "/private/v1/openPositions",
        "/v1/openPositions",
        {"count": "100"},
    ),
    (
        "active_orders",
        "/private/v1/activeOrders",
        "/v1/activeOrders",
        {"count": "100"},
    ),
)
_PACING_SECONDS = 0.25


class V4GmoPostCanaryReconciliationError(RuntimeError):
    """Fixed, safe failure labels for the read-only reconciliation lane."""


class _HttpGetClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Any: ...


class V4GmoPostCanaryReadOnlyClient(Protocol):
    def get_latest_executions(self) -> Mapping[str, Any]: ...

    def get_open_positions(self) -> Mapping[str, Any]: ...

    def get_active_orders(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class V4GmoPostCanaryResult:
    status: str
    result_known: bool
    subject_entry_observed: bool
    account_flat: bool
    active_orders_zero: bool
    broker_read_count: int
    broker_write_attempt_count: int = 0
    raw_response_retained: bool = False
    identifier_exposed: bool = False

    def safe_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "result_known": self.result_known,
            "subject_entry_observed": self.subject_entry_observed,
            "account_flat": self.account_flat,
            "active_orders_zero": self.active_orders_zero,
            "broker_read_count": self.broker_read_count,
            "broker_write_attempt_count": self.broker_write_attempt_count,
            "raw_response_retained": self.raw_response_retained,
            "identifier_exposed": self.identifier_exposed,
        }


@dataclass
class V4GmoHttpxPostCanaryReadOnlyClient:
    """Concrete client whose public surface exposes only the three fixed GETs."""

    signed_request_factory: V4GmoSignedRequestFactory
    client: _HttpGetClient

    @classmethod
    def from_keychain(cls) -> V4GmoHttpxPostCanaryReadOnlyClient:
        return cls(
            signed_request_factory=V4GmoSignedRequestFactory(
                credential_pair=V4GmoKeychainCredentialPair()
            ),
            client=httpx.Client(),
        )

    def get_latest_executions(self) -> Mapping[str, Any]:
        return self._get_fixed(index=0)

    def get_open_positions(self) -> Mapping[str, Any]:
        return self._get_fixed(index=1)

    def get_active_orders(self) -> Mapping[str, Any]:
        return self._get_fixed(index=2)

    def _get_fixed(self, *, index: int) -> Mapping[str, Any]:
        try:
            _, transport_path, signing_path, params = _ENDPOINTS[index]
            request = V4GmoPrivateRequest(
                method="GET",
                transport_path=transport_path,
                signing_path=signing_path,
                params=params,
                body=None,
            )
            signed = self.signed_request_factory.build(request)
            response = self.client.get(
                GMO_V4_PRIVATE_BASE_URL + transport_path,
                params=dict(params),
                headers=dict(signed.headers),
                timeout=GMO_V4_PRIVATE_HTTP_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                raise V4GmoPostCanaryReconciliationError(
                    "G013_POST_CANARY_READ_REJECTED"
                )
            payload = response.json()
            if not isinstance(payload, Mapping) or payload.get("status") != 0:
                raise V4GmoPostCanaryReconciliationError(
                    "G013_POST_CANARY_READ_REJECTED"
                )
            return _normalize_rows_data(payload.get("data"))
        except V4GmoPostCanaryReconciliationError:
            raise
        except (V4GmoActualTransportError, httpx.HTTPError, OSError, ValueError):
            raise V4GmoPostCanaryReconciliationError(
                "G013_POST_CANARY_READ_UNKNOWN"
            ) from None


def require_g013_entry_enabled(
    *, repository: Path, reviewed_files_digest: str, generation_digest: str
) -> None:
    """Fail closed when this reviewed generation is reconciliation-only."""

    path = repository.resolve() / _CONTRACT_PATH
    if not path.exists():
        return
    payload = _load_contract(path)
    if payload.get("reviewed_files_digest") != reviewed_files_digest:
        raise V4GmoPostCanaryReconciliationError("G013_POST_CANARY_CONTRACT_MISMATCH")
    if payload.get("generation_digest") != generation_digest:
        raise V4GmoPostCanaryReconciliationError("G013_POST_CANARY_CONTRACT_MISMATCH")
    if payload.get("entry_disabled") is True:
        raise V4GmoPostCanaryReconciliationError(
            "G013_ENTRY_DISABLED_POST_CANARY_RECONCILIATION_ONLY"
        )


def load_post_canary_origin_generation_digest(
    *, repository: Path, reviewed_files_digest: str, generation_digest: str
) -> str:
    """Load only a reviewed target-to-origin binding; never an operator input."""

    payload = _load_contract(repository.resolve() / _CONTRACT_PATH)
    origin = payload.get("origin_generation_digest")
    if (
        payload.get("reviewed_files_digest") != reviewed_files_digest
        or payload.get("generation_digest") != generation_digest
        or not isinstance(origin, str)
        or len(origin) != 71
        or not origin.startswith("sha256:")
    ):
        raise V4GmoPostCanaryReconciliationError("G013_POST_CANARY_CONTRACT_MISMATCH")
    return origin


@dataclass
class V4GmoPostCanaryReconciler:
    repository: Path
    target_generation_digest: str
    origin_generation_digest: str
    cycle_ref: str
    client: V4GmoPostCanaryReadOnlyClient
    wait: Callable[[float], None] = time.sleep

    def reconcile_once(self) -> V4GmoPostCanaryResult:
        root = v4_gmo_runtime_state_root(
            repository=self.repository, generation_digest=self.target_generation_digest
        )
        _claim_once(root=root, origin_generation_digest=self.origin_generation_digest)
        read_count = 0
        try:
            executions = self.client.get_latest_executions()
            read_count = 1
            self.wait(_PACING_SECONDS)
            positions = self.client.get_open_positions()
            read_count = 2
            self.wait(_PACING_SECONDS)
            active_orders = self.client.get_active_orders()
            read_count = 3
            entry_seen = _subject_entry_seen(executions, cycle_ref=self.cycle_ref)
            positions_rows = _rows(positions)
            active_order_rows = _rows(active_orders)
            if not entry_seen:
                raise V4GmoPostCanaryReconciliationError(
                    "G013_POST_CANARY_SUBJECT_NOT_OBSERVED"
                )
            result = V4GmoPostCanaryResult(
                status=(
                    "G013_POST_CANARY_FLAT_CONFIRMED"
                    if not positions_rows and not active_order_rows
                    else "G013_POST_CANARY_NOT_FLAT_PERSISTENT_HALT"
                ),
                result_known=True,
                subject_entry_observed=True,
                account_flat=not positions_rows,
                active_orders_zero=not active_order_rows,
                broker_read_count=3,
            )
        except V4GmoPostCanaryReconciliationError as error:
            result = V4GmoPostCanaryResult(
                status=_safe_failure_status(error),
                result_known=False,
                subject_entry_observed=False,
                account_flat=False,
                active_orders_zero=False,
                broker_read_count=read_count,
            )
        try:
            _write_result_once(root=root, result=result)
        except OSError:
            return V4GmoPostCanaryResult(
                status="G013_POST_CANARY_RESULT_UNKNOWN_PERSISTENT_HALT",
                result_known=False,
                subject_entry_observed=False,
                account_flat=False,
                active_orders_zero=False,
                broker_read_count=read_count,
            )
        return result


def _load_contract(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise V4GmoPostCanaryReconciliationError(
            "G013_POST_CANARY_CONTRACT_INVALID"
        ) from None
    if not isinstance(payload, dict):
        raise V4GmoPostCanaryReconciliationError("G013_POST_CANARY_CONTRACT_INVALID")
    return payload


def _claim_once(*, root: Path, origin_generation_digest: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "post-canary-reconciliation.started.json"
    payload = {
        "schema": "H11_V4_G013_POST_CANARY_RECONCILIATION_V1",
        "origin_generation_digest": origin_generation_digest,
        "broker_write_attempt_count": 0,
    }
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise V4GmoPostCanaryReconciliationError(
            "G013_POST_CANARY_RECONCILIATION_ALREADY_CONSUMED"
        ) from None
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def _write_result_once(*, root: Path, result: V4GmoPostCanaryResult) -> None:
    name = (
        "post-canary-reconciliation.passed.json"
        if result.status == "G013_POST_CANARY_FLAT_CONFIRMED"
        else "post-canary-reconciliation.halt.json"
    )
    path = root / name
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(result.safe_dict(), handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def _rows(data: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    rows = data.get("list")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise V4GmoPostCanaryReconciliationError("G013_POST_CANARY_READ_SCHEMA_INVALID")
    return rows


def _normalize_rows_data(data: Any) -> Mapping[str, Any]:
    if data is None:
        return {"list": []}
    if isinstance(data, Sequence) and not isinstance(data, str | bytes | bytearray):
        rows = list(data)
    elif isinstance(data, Mapping):
        rows = data.get("list")
        if not isinstance(rows, list):
            raise V4GmoPostCanaryReconciliationError(
                "G013_POST_CANARY_READ_SCHEMA_INVALID"
            )
    else:
        raise V4GmoPostCanaryReconciliationError(
            "G013_POST_CANARY_READ_SCHEMA_INVALID"
        )
    if any(not isinstance(row, Mapping) for row in rows):
        raise V4GmoPostCanaryReconciliationError(
            "G013_POST_CANARY_READ_SCHEMA_INVALID"
        )
    return {"list": rows}


def _subject_entry_seen(data: Mapping[str, Any], *, cycle_ref: str) -> bool:
    if len(cycle_ref) != 64 or any(character not in "0123456789abcdef" for character in cycle_ref):
        raise V4GmoPostCanaryReconciliationError("G013_POST_CANARY_CYCLE_INVALID")
    entry_client_order_id = _ENTRY_PREFIX + cycle_ref[:30]
    for row in _rows(data):
        if row.get("symbol") == "USD_JPY" and row.get("clientOrderId") == entry_client_order_id:
            return True
    return False


def _safe_failure_status(error: V4GmoPostCanaryReconciliationError) -> str:
    del error
    return "G013_POST_CANARY_RESULT_UNKNOWN_PERSISTENT_HALT"
