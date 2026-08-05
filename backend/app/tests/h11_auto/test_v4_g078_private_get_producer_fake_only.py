"""Fake-only acceptance tests for the G078 read-back producer.

The producer builds the one-use read-back client for the G078 resolution
step.  All tests use a fake credential pair and a fake httpx client; no
Keychain, no Private API, no network access.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.h11_v4_g026_private_get_keychain import (
    V4G026PrivateGetKeychainCredentialPair,
)
from app.services.h11_v4_g078_private_get_producer import (
    V4G078PrivateGetProducerError,
    build_g078_read_back_producer,
)
from app.services.h11_v4_g078_runtime import (
    G078FakeOnlyCallable,
    G078ReadBackSource,
)
from app.services.h11_v4_unattended_shadow_private_preflight import (
    V4UnattendedShadowSealedSecret,
)

GEN = "sha256:" + "a" * 64
SCOPE = "sha256:" + "b" * 64
NOW = datetime(2026, 8, 5, 1, 0, 0, tzinfo=UTC)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, responses: dict[str, _FakeResponse] | None = None) -> None:
        self.responses = responses or {}
        self.requested: list[str] = []

    def get(
        self, url: str, *, headers: dict | None = None, timeout: float | None = None
    ) -> _FakeResponse:
        del headers, timeout
        self.requested.append(url)
        if url not in self.responses:
            raise AssertionError(f"unexpected url: {url}")
        return self.responses[url]


def _fake_credential_pair() -> V4G026PrivateGetKeychainCredentialPair:
    def reader(service: str, account: str) -> V4UnattendedShadowSealedSecret:
        assert service == "fx-strategy-lab-h11-v4-actual"
        assert account in {"gmo-fx-api-key", "gmo-fx-api-secret"}
        return V4UnattendedShadowSealedSecret("fake-value")

    return V4G026PrivateGetKeychainCredentialPair(reader=reader)


def _payload(
    *,
    executions: list[dict] | None = None,
    positions: list[dict] | None = None,
    orders: list[dict] | None = None,
) -> dict:
    return {
        "status": 0,
        "responsetime": "2026-08-05T00:59:59.000Z",
        "data": {
            "executions": executions or [],
            "positions": positions or [],
            "orders": orders or [],
        },
    }


def _executed_responses() -> dict[str, _FakeResponse]:
    return {
        "https://api.coin.z.com/private/v1/latestExecutions": _FakeResponse(
            {"data": [{"size": "1000", "symbol": "USD_JPY"}]}
        ),
        "https://api.coin.z.com/private/v1/openPositions": _FakeResponse(
            {"data": [{"symbol": "USD_JPY", "size": "1000", "ocoOrderId": "123"}]}
        ),
        "https://api.coin.z.com/private/v1/activeOrders": _FakeResponse({"data": []}),
    }


def test_producer_returns_sanitized_reads_for_all_sources(tmp_path):
    del tmp_path
    client = _FakeClient(_executed_responses())
    producer = build_g078_read_back_producer(
        credential_pair=_fake_credential_pair(),
        client=client,
        generation_digest=GEN,
        action_scope_digest=SCOPE,
        now_factory=lambda: NOW,
    )
    assert isinstance(producer, G078FakeOnlyCallable)
    executions = producer(G078ReadBackSource.LATEST_EXECUTIONS, NOW)
    positions = producer(G078ReadBackSource.OPEN_POSITIONS, NOW)
    orders = producer(G078ReadBackSource.ACTIVE_ORDERS, NOW)
    assert executions.known is True and executions.matched_execution_seen is True
    assert positions.known is True and positions.account_flat is False
    assert positions.ownership_exact is True and positions.quantity_matches is True
    assert positions.protection_confirmed is True
    assert orders.known is True and orders.active_orders_zero is True
    assert len(client.requested) == 3


def test_producer_reads_each_source_at_most_once():
    client = _FakeClient(_executed_responses())
    producer = build_g078_read_back_producer(
        credential_pair=_fake_credential_pair(),
        client=client,
        generation_digest=GEN,
        action_scope_digest=SCOPE,
        now_factory=lambda: NOW,
    )
    producer(G078ReadBackSource.LATEST_EXECUTIONS, NOW)
    with pytest.raises(V4G078PrivateGetProducerError, match="G078_PRODUCER_SOURCE_READ_TWICE"):
        producer(G078ReadBackSource.LATEST_EXECUTIONS, NOW)


def test_producer_failed_fetch_is_known_false():
    client = _FakeClient()
    producer = build_g078_read_back_producer(
        credential_pair=_fake_credential_pair(),
        client=client,
        generation_digest=GEN,
        action_scope_digest=SCOPE,
        now_factory=lambda: NOW,
    )
    result = producer(G078ReadBackSource.OPEN_POSITIONS, NOW)
    assert result.known is False and result.account_flat is False
    assert result.count == 0


def test_producer_flat_zero_reads():
    client = _FakeClient(
        {
            "https://api.coin.z.com/private/v1/latestExecutions": _FakeResponse({"data": []}),
            "https://api.coin.z.com/private/v1/openPositions": _FakeResponse({"data": []}),
            "https://api.coin.z.com/private/v1/activeOrders": _FakeResponse({"data": []}),
        }
    )
    producer = build_g078_read_back_producer(
        credential_pair=_fake_credential_pair(),
        client=client,
        generation_digest=GEN,
        action_scope_digest=SCOPE,
        now_factory=lambda: NOW,
    )
    assert producer(G078ReadBackSource.OPEN_POSITIONS, NOW).account_flat is True
    assert producer(G078ReadBackSource.ACTIVE_ORDERS, NOW).active_orders_zero is True
    assert (
        producer(G078ReadBackSource.LATEST_EXECUTIONS, NOW).matched_execution_seen
        is False
    )


def test_producer_rejects_invalid_credential_pair():
    client = _FakeClient(_executed_responses())
    with pytest.raises(
        V4G078PrivateGetProducerError, match="G078_PRODUCER_CREDENTIAL_PAIR_INVALID"
    ):
        build_g078_read_back_producer(
            credential_pair="not-a-pair",  # type: ignore[arg-type]
            client=client,
            generation_digest=GEN,
            action_scope_digest=SCOPE,
        )


def test_producer_rejects_invalid_digests():
    client = _FakeClient(_executed_responses())
    with pytest.raises(
        V4G078PrivateGetProducerError, match="G078_PRODUCER_GENERATION_DIGEST_INVALID"
    ):
        build_g078_read_back_producer(
            credential_pair=_fake_credential_pair(),
            client=client,
            generation_digest="bad",
            action_scope_digest=SCOPE,
        )
    with pytest.raises(
        V4G078PrivateGetProducerError, match="G078_PRODUCER_ACTION_SCOPE_DIGEST_INVALID"
    ):
        build_g078_read_back_producer(
            credential_pair=_fake_credential_pair(),
            client=client,
            generation_digest=GEN,
            action_scope_digest="bad",
        )


def test_producer_module_source_scan_no_inline_keychain():
    source = (
        Path(__file__).resolve().parents[2]
        / "services"
        / "h11_v4_g078_private_get_producer.py"
    )
    content = source.read_text(encoding="utf-8")
    # The producer never touches Keychain or launchd itself (credential reads
    # are delegated to the sealed G026 credential pair).
    for token in (
        "find-generic-password",
        "subprocess",
        "smtplib",
        "launchd",
        "Pushover",
        "os.environ",
    ):
        assert token not in content, token
    # The producer constructs signed GETs (real-capable) but never POSTs.
    assert 'method="GET"' in content
    assert "def build_g078_read_back_producer" in content
