from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest

from app.h11_auto.contracts import SignalDecision
from app.h11_auto.v4_gmo_contracts import (
    V4GmoAction,
    V4GmoEntryStatus,
    V4GmoProtectionStatus,
    build_v4_action_plan,
)
from app.h11_auto.v4_gmo_persisted_authorization import (
    V4PersistedActionAuthorization,
    V4PersistedAuthorizationError,
)
from app.h11_auto.v4_gmo_protection import (
    H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    build_exact_fill_oco_plan_no_post,
)
from app.private_api.auth import create_signature
from app.services import h11_v4_gmo_actual_adapter as adapter_module
from app.services import h11_v4_gmo_actual_transport as transport_module
from app.services.h11_v4_gmo_actual_adapter import (
    V4GmoActualAdapter,
    v4_gmo_client_order_id,
)
from app.services.h11_v4_gmo_actual_transport import (
    V4GmoActualActivationPermit,
    V4GmoActualTransportError,
    V4GmoHttpxPrivateTransport,
    V4GmoKeychainCredentialPair,
    V4GmoPrivateEnvelope,
    V4GmoPrivateRequest,
    V4GmoSealedSecret,
    V4GmoSignedRequestFactory,
)

CYCLE_REF = "a" * 64


@dataclass
class FakePrivateTransport:
    responses: list[dict[str, Any]]
    requests: list[V4GmoPrivateRequest] = field(default_factory=list)

    def request(
        self,
        request: V4GmoPrivateRequest,
        *,
        persisted_transport_authorization: object | None = None,
    ) -> V4GmoPrivateEnvelope:
        del persisted_transport_authorization
        self.requests.append(request)
        if not self.responses:
            raise V4GmoActualTransportError("FAKE_RESPONSE_MISSING")
        return V4GmoPrivateEnvelope.from_injected_payload(self.responses.pop(0))


@dataclass
class TimeoutPrivateTransport:
    calls: int = 0

    def request(
        self,
        request: V4GmoPrivateRequest,
        *,
        persisted_transport_authorization: object | None = None,
    ) -> V4GmoPrivateEnvelope:
        del persisted_transport_authorization
        del request
        self.calls += 1
        raise TimeoutError("synthetic timeout")


@dataclass(frozen=True)
class FakeCredentialPair:
    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4GmoSealedSecret, V4GmoSealedSecret]:
        return V4GmoSealedSecret("synthetic-key"), V4GmoSealedSecret("synthetic-secret")


def action_plan(
    action: V4GmoAction,
    *,
    size: int = 1_000,
    side: SignalDecision = SignalDecision.BUY,
):
    return build_v4_action_plan(
        cycle_ref=CYCLE_REF,
        action=action,
        side=side,
        requested_size=size,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def reconcile_fixed(
    adapter: V4GmoActualAdapter,
    *,
    cycle_ref: str,
    side: SignalDecision,
    requested_size: int,
):
    clock = [0.0]

    def monotonic() -> float:
        return clock[0]

    def wait(seconds: float) -> None:
        clock[0] += seconds

    return adapter.reconcile(
        cycle_ref=cycle_ref,
        side=side,
        requested_size=requested_size,
        monotonic_factory=monotonic,
        wait=wait,
    )


def entry_client_id() -> str:
    return v4_gmo_client_order_id(cycle_ref=CYCLE_REF, action=V4GmoAction.MARKET_ENTRY)


def protection_client_id() -> str:
    return v4_gmo_client_order_id(
        cycle_ref=CYCLE_REF,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
    )


def partial_responses() -> list[dict[str, Any]]:
    return [
        {
            "status": 0,
            "data": {
                "list": [
                    {
                        "clientOrderId": entry_client_id(),
                        "positionId": 1001,
                        "symbol": "USD_JPY",
                        "side": "BUY",
                        "settleType": "OPEN",
                        "size": "400",
                    },
                    {
                        "clientOrderId": entry_client_id(),
                        "positionId": 1002,
                        "symbol": "USD_JPY",
                        "side": "BUY",
                        "settleType": "OPEN",
                        "size": "200",
                    },
                ]
            },
        },
        {
            "status": 0,
            "data": {
                "list": [
                    {
                        "positionId": 1001,
                        "symbol": "USD_JPY",
                        "side": "BUY",
                        "size": "400",
                        "price": "150.000",
                    },
                    {
                        "positionId": 1002,
                        "symbol": "USD_JPY",
                        "side": "BUY",
                        "size": "200",
                        "price": "150.006",
                    },
                ]
            },
        },
        {
            "status": 0,
            "data": {
                "list": [
                    {
                        "clientOrderId": entry_client_id(),
                        "symbol": "USD_JPY",
                        "settleType": "OPEN",
                        "size": "1000",
                    }
                ]
            },
        },
    ]


def filled_responses() -> list[dict[str, Any]]:
    responses = partial_responses()
    responses[2] = {"status": 0, "data": {"list": []}}
    return responses


def test_activation_permit_is_structurally_unavailable() -> None:
    with pytest.raises(TypeError):
        V4GmoActualActivationPermit()

    forged = object.__new__(V4GmoActualActivationPermit)
    with pytest.raises(V4GmoActualTransportError, match="NOT_ISSUED"):
        V4GmoHttpxPrivateTransport(
            activation_permit=forged,
            signed_request_factory=V4GmoSignedRequestFactory(
                credential_pair=FakeCredentialPair()
            ),
        )


def test_signing_uses_official_short_path_and_redacts_repr() -> None:
    request = V4GmoPrivateRequest(
        method="POST",
        transport_path="/private/v1/order",
        signing_path="/v1/order",
        params={},
        body={
            "symbol": "USD_JPY",
            "side": "BUY",
            "size": "1000",
            "clientOrderId": entry_client_id(),
            "executionType": "MARKET",
        },
    )
    signed = V4GmoSignedRequestFactory(
        credential_pair=FakeCredentialPair(),
        timestamp_factory=lambda: "1700000000000",
    ).build(request)
    expected = create_signature(
        api_secret="synthetic-secret",
        timestamp="1700000000000",
        method="POST",
        path="/v1/order",
        body=request.body_json,
    )
    assert signed.headers["API-SIGN"] == expected
    assert "synthetic-key" not in repr(signed)
    assert "synthetic-secret" not in repr(signed)
    assert request.body_json not in repr(request)

    envelope = V4GmoPrivateEnvelope.from_injected_payload(
        {"status": 0, "data": {"positionId": 123456}}
    )
    assert "123456" not in repr(envelope)


def test_keychain_pair_accepts_injected_fake_reader_without_real_keychain() -> None:
    calls: list[tuple[str, str]] = []

    def fake_reader(service: str, account: str) -> V4GmoSealedSecret:
        calls.append((service, account))
        return V4GmoSealedSecret("synthetic-value")

    pair = V4GmoKeychainCredentialPair(reader=fake_reader)
    key, secret = pair.unseal_for_internal_request_only()
    assert len(calls) == 2
    assert repr(key) == "V4GmoSealedSecret(***)"
    assert repr(secret) == "V4GmoSealedSecret(***)"
    assert "synthetic-value" not in repr(pair)


def test_market_entry_and_cancel_use_deterministic_client_order_id() -> None:
    adapter = V4GmoActualAdapter(transport=FakePrivateTransport(responses=[]))

    market = adapter._build_action_request(
        plan=action_plan(V4GmoAction.MARKET_ENTRY),
        reconciliation=None,
        protection_plan=None,
    )
    assert market.transport_path == "/private/v1/order"
    assert market.signing_path == "/v1/order"
    assert market.body == {
        "symbol": "USD_JPY",
        "side": "BUY",
        "size": "1000",
        "clientOrderId": entry_client_id(),
        "executionType": "MARKET",
    }

    cancel_reconciliation = reconcile_fixed(
        V4GmoActualAdapter(
            transport=FakePrivateTransport(responses=partial_responses())
        ),
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    cancel = adapter._build_action_request(
        plan=action_plan(V4GmoAction.CANCEL_ENTRY_REMAINDER, size=400),
        reconciliation=cancel_reconciliation,
        protection_plan=None,
    )
    assert cancel.transport_path == "/private/v1/cancelOrders"
    assert cancel.body == {"clientOrderIds": [entry_client_id()]}
    assert len(entry_client_id()) == 36



def test_adapter_refuses_write_without_coordinator_issued_authorization() -> None:
    transport = FakePrivateTransport(responses=[{"status": 0}])
    forged = object.__new__(V4PersistedActionAuthorization)
    with pytest.raises(V4PersistedAuthorizationError, match="INVALID"):
        V4GmoActualAdapter(transport=transport).perform_once(
            plan=action_plan(V4GmoAction.MARKET_ENTRY),
            persisted_authorization=forged,
            now_monotonic=1.0,
        )
    assert transport.requests == []


def test_transport_request_contract_rejects_extra_or_wrong_v4_fields() -> None:
    with pytest.raises(V4GmoActualTransportError, match="MARKET_BODY_INVALID"):
        V4GmoPrivateRequest(
            method="POST",
            transport_path="/private/v1/order",
            signing_path="/v1/order",
            params={},
            body={
                "symbol": "USD_JPY",
                "side": "BUY",
                "size": "1000",
                "clientOrderId": entry_client_id(),
                "executionType": "MARKET",
                "unexpected": "forbidden",
            },
        )
    with pytest.raises(V4GmoActualTransportError, match="CLIENT_ORDER_ID_INVALID"):
        V4GmoPrivateRequest(
            method="POST",
            transport_path="/private/v1/order",
            signing_path="/v1/order",
            params={},
            body={
                "symbol": "USD_JPY",
                "side": "BUY",
                "size": "1000",
                "clientOrderId": protection_client_id(),
                "executionType": "MARKET",
            },
        )


def test_partial_fill_reconciliation_aggregates_owned_position_parts() -> None:
    transport = FakePrivateTransport(responses=partial_responses())
    result = reconcile_fixed(
        V4GmoActualAdapter(transport=transport),
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    assert result.snapshot.result_known is True
    assert result.snapshot.position_count == 1
    assert result.snapshot.filled_size == 600
    assert result.snapshot.pending_entry_size == 400
    assert result.snapshot.entry_status is V4GmoEntryStatus.PARTIAL
    assert result.snapshot.protection_status is V4GmoProtectionStatus.NONE
    assert result.average_fill_price == Decimal("150.002")
    assert result.position_bundle is not None
    assert result.position_bundle.total_size == 600
    assert "1001" not in repr(result)
    assert "1002" not in repr(result.position_bundle)
    assert result.raw_response_retained is False
    assert result.identifier_exposed is False
    assert [request.signing_path for request in transport.requests] == [
        "/v1/latestExecutions",
        "/v1/openPositions",
        "/v1/activeOrders",
    ]
    assert [dict(request.params) for request in transport.requests] == [
        {"symbol": "USD_JPY", "count": "100"},
        {"count": "100"},
        {"count": "100"},
    ]


def test_actual_reconciliation_path_enforces_fixed_get_cadence_without_retry() -> None:
    transport = FakePrivateTransport(responses=partial_responses())
    clock = [100.0]
    waits: list[float] = []

    def monotonic() -> float:
        return clock[0]

    def wait(seconds: float) -> None:
        waits.append(seconds)
        clock[0] += seconds

    result = V4GmoActualAdapter(transport=transport).reconcile_at_fixed_cadence(
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
        monotonic_factory=monotonic,
        wait=wait,
    )
    assert result.snapshot.result_known is True
    assert len(transport.requests) == 3
    assert waits == pytest.approx([0.25, 0.25, 0.25])


def test_fixed_get_cadence_does_not_compress_after_slow_first_get() -> None:
    clock = [100.0]
    starts: list[float] = []

    @dataclass
    class SlowFirstTransport(FakePrivateTransport):
        def request(
            self,
            request: V4GmoPrivateRequest,
            *,
            persisted_transport_authorization: object | None = None,
        ) -> V4GmoPrivateEnvelope:
            del persisted_transport_authorization
            starts.append(clock[0])
            result = super().request(request)
            if len(starts) == 1:
                clock[0] += 0.40
            return result

    def monotonic() -> float:
        return clock[0]

    def wait(seconds: float) -> None:
        clock[0] += seconds

    result = V4GmoActualAdapter(
        transport=SlowFirstTransport(responses=partial_responses())
    ).reconcile_at_fixed_cadence(
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
        monotonic_factory=monotonic,
        wait=wait,
    )
    assert result.snapshot.result_known is True
    assert starts == pytest.approx([100.25, 100.65, 100.90])


def test_fixed_get_cadence_fails_closed_when_wait_does_not_advance_clock() -> None:
    transport = FakePrivateTransport(responses=partial_responses())

    result = V4GmoActualAdapter(transport=transport).reconcile_at_fixed_cadence(
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
        monotonic_factory=lambda: 100.0,
        wait=lambda _seconds: None,
    )

    assert result.snapshot.result_known is False
    assert transport.requests == []


def test_fixed_get_cadence_is_shared_across_back_to_back_reconciliation() -> None:
    transport = FakePrivateTransport(responses=partial_responses() + partial_responses())
    adapter = V4GmoActualAdapter(transport=transport)
    clock = [100.0]
    starts: list[float] = []

    original_request = transport.request

    def request(request: V4GmoPrivateRequest) -> V4GmoPrivateEnvelope:
        starts.append(clock[0])
        return original_request(request)

    transport.request = request  # type: ignore[method-assign]

    def wait(seconds: float) -> None:
        clock[0] += seconds

    for _ in range(2):
        result = adapter.reconcile_at_fixed_cadence(
            cycle_ref=CYCLE_REF,
            side=SignalDecision.BUY,
            requested_size=1_000,
            monotonic_factory=lambda: clock[0],
            wait=wait,
        )
        assert result.snapshot.result_known is True

    assert len(starts) == 6
    assert all(
        later - earlier >= 0.249999
        for earlier, later in zip(starts[:-1], starts[1:], strict=True)
    )


def test_fixed_get_cadence_fails_closed_on_monotonic_clock_regression() -> None:
    transport = FakePrivateTransport(responses=partial_responses())
    readings = iter((100.0, 100.0, 100.25, 100.10))

    result = V4GmoActualAdapter(transport=transport).reconcile_at_fixed_cadence(
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
        monotonic_factory=lambda: next(readings),
        wait=lambda _seconds: None,
    )

    assert result.snapshot.result_known is False
    assert len(transport.requests) == 1


def test_exact_oco_and_position_specific_exit_use_reconciled_bundle() -> None:
    reconcile_transport = FakePrivateTransport(responses=filled_responses())
    reconciliation = reconcile_fixed(
        V4GmoActualAdapter(transport=reconcile_transport),
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    protection = build_exact_fill_oco_plan_no_post(
        position_side=SignalDecision.BUY,
        reconciled_average_fill_price=Decimal("150.002"),
        frozen_signal_atr_24=Decimal("0.100"),
        reconciled_filled_size=600,
    )
    adapter = V4GmoActualAdapter(transport=FakePrivateTransport(responses=[]))

    oco = adapter._build_action_request(
        plan=action_plan(V4GmoAction.EXACT_SIZE_OCO_PROTECTION, size=600),
        reconciliation=reconciliation,
        protection_plan=protection,
    )
    assert oco.transport_path == "/private/v1/closeOrder"
    assert oco.body is not None
    assert oco.body["executionType"] == "OCO"
    assert oco.body["side"] == "SELL"
    assert oco.body["clientOrderId"] == protection_client_id()
    assert oco.body["settlePosition"] == [
        {"positionId": 1001, "size": "400"},
        {"positionId": 1002, "size": "200"},
    ]

    close = adapter._build_action_request(
        plan=action_plan(V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT, size=600),
        reconciliation=reconciliation,
        protection_plan=None,
    )
    assert close.body is not None
    assert close.body["executionType"] == "MARKET"
    assert close.body["side"] == "SELL"
    assert close.body["settlePosition"] == oco.body["settlePosition"]


def test_sell_entry_and_exit_side_are_mapped_without_inference() -> None:
    adapter = V4GmoActualAdapter(transport=FakePrivateTransport(responses=[]))
    request = adapter._build_action_request(
        plan=action_plan(V4GmoAction.MARKET_ENTRY, side=SignalDecision.SELL),
        reconciliation=None,
        protection_plan=None,
    )
    assert request.body is not None
    assert request.body["side"] == "SELL"


def test_flat_reconciliation_reports_owned_realized_pnl_without_ids() -> None:
    responses = [
        {
            "status": 0,
            "data": {
                "list": [
                    {
                        "clientOrderId": entry_client_id(),
                        "positionId": 1001,
                        "symbol": "USD_JPY",
                        "side": "BUY",
                        "settleType": "OPEN",
                        "size": "1000",
                        "amount": "0",
                        "lossGain": "0",
                        "fee": "0",
                        "settledSwap": "0",
                    },
                    {
                        "clientOrderId": protection_client_id(),
                        "positionId": 1001,
                        "symbol": "USD_JPY",
                        "side": "SELL",
                        "settleType": "CLOSE",
                        "size": "1000",
                        "amount": "-1234.25",
                        "lossGain": "-1200.25",
                        "fee": "-30",
                        "settledSwap": "-4",
                    },
                ]
            },
        },
        {"status": 0, "data": {"list": []}},
        {"status": 0, "data": {"list": []}},
    ]
    result = reconcile_fixed(
        V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)),
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )

    assert result.snapshot.result_known is True
    assert result.snapshot.position_count == 0
    assert result.closed_size == 1_000
    assert result.realized_pnl_jpy_internal == -1235
    assert "1001" not in repr(result)


def test_delivery_amount_alone_is_not_accepted_as_realized_pnl() -> None:
    responses = [
        {
            "status": 0,
            "data": {
                "list": [
                    {
                        "clientOrderId": entry_client_id(),
                        "positionId": 1001,
                        "symbol": "USD_JPY",
                        "side": "BUY",
                        "settleType": "OPEN",
                        "size": "1000",
                        "amount": "0",
                    },
                    {
                        "clientOrderId": protection_client_id(),
                        "positionId": 1001,
                        "symbol": "USD_JPY",
                        "side": "SELL",
                        "settleType": "CLOSE",
                        "size": "1000",
                        "amount": "-1234.25",
                    },
                ]
            },
        },
        {"status": 0, "data": {"list": []}},
        {"status": 0, "data": {"list": []}},
    ]
    result = reconcile_fixed(
        V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)),
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )

    assert result.snapshot.result_known is False
    assert result.realized_pnl_jpy_internal is None


def test_close_execution_requires_owned_position_opposite_side_and_size() -> None:
    def result_for(*, position_id: int, side: str, close_size: str):
        responses = [
            {
                "status": 0,
                "data": {
                    "list": [
                        {
                            "clientOrderId": entry_client_id(),
                            "positionId": 1001,
                            "symbol": "USD_JPY",
                            "side": "BUY",
                            "settleType": "OPEN",
                            "size": "1000",
                            "amount": "0",
                        },
                        {
                            "clientOrderId": protection_client_id(),
                            "positionId": position_id,
                            "symbol": "USD_JPY",
                            "side": side,
                            "settleType": "CLOSE",
                            "size": close_size,
                            "amount": "-100",
                            "lossGain": "-100",
                            "fee": "0",
                            "settledSwap": "0",
                        },
                    ]
                },
            },
            {"status": 0, "data": {"list": []}},
            {"status": 0, "data": {"list": []}},
        ]
        return reconcile_fixed(
            V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)),
            cycle_ref=CYCLE_REF,
            side=SignalDecision.BUY,
            requested_size=1_000,
        )

    wrong_position = result_for(
        position_id=2002, side="SELL", close_size="1000"
    )
    wrong_side = result_for(
        position_id=1001, side="BUY", close_size="1000"
    )
    oversized = result_for(
        position_id=1001, side="SELL", close_size="10001"
    )
    assert wrong_position.snapshot.result_known is False
    assert wrong_side.snapshot.result_known is False
    assert oversized.snapshot.result_known is False


def test_exact_protection_reconciliation_treats_two_oco_legs_as_one_size() -> None:
    responses = partial_responses()
    responses[2] = {
        "status": 0,
        "data": {
            "list": [
                {
                    "clientOrderId": protection_client_id(),
                    "symbol": "USD_JPY",
                    "settleType": "CLOSE",
                    "size": "600",
                },
                {
                    "clientOrderId": protection_client_id(),
                    "symbol": "USD_JPY",
                    "settleType": "CLOSE",
                    "size": "600",
                },
            ]
        },
    }
    result = reconcile_fixed(
        V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)),
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    assert result.snapshot.pending_entry_size == 0
    assert result.snapshot.protection_size == 600
    assert result.snapshot.protection_status is V4GmoProtectionStatus.EXACT_MATCH
    assert result.snapshot.entry_status is V4GmoEntryStatus.FILLED


def test_unowned_position_or_order_fails_closed_without_identifier_exposure() -> None:
    responses = partial_responses()
    responses[1]["data"]["list"][0]["positionId"] = 9999
    result = reconcile_fixed(
        V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)),
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    assert result.snapshot.result_known is False
    assert result.snapshot.entry_status is V4GmoEntryStatus.UNKNOWN
    assert result.account_position_count == 2
    assert result.unowned_position_count == 1
    assert "9999" not in repr(result)

    responses = partial_responses()
    responses[2]["data"]["list"].append(
        {
            "clientOrderId": "MANUALORDER000000000000000000000001",
            "symbol": "USD_JPY",
            "settleType": "OPEN",
            "size": "1000",
        }
    )
    result = reconcile_fixed(
        V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)),
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    assert result.snapshot.result_known is False
    assert result.account_active_order_count == 2
    assert result.unowned_active_order_count == 1

    responses = partial_responses()
    responses[1]["data"]["list"].append(
        {
            "positionId": 8001,
            "symbol": "EUR_USD",
            "side": "SELL",
            "size": "1000",
            "price": "1.10000",
        }
    )
    result = reconcile_fixed(
        V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)),
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    assert result.snapshot.result_known is False
    assert result.unowned_position_count == 1

    responses = partial_responses()
    responses[2]["data"]["list"].append(
        {
            "clientOrderId": "MANUALORDER000000000000000000000002",
            "symbol": "EUR_USD",
            "settleType": "OPEN",
            "size": "1000",
        }
    )
    result = reconcile_fixed(
        V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)),
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    assert result.snapshot.result_known is False
    assert result.unowned_active_order_count == 1


def test_unrelated_manual_execution_history_does_not_claim_or_block_flat() -> None:
    responses = [
        {
            "status": 0,
            "data": {
                "list": [
                    {
                        "positionId": 7777,
                        "symbol": "USD_JPY",
                        "side": "SELL",
                        "settleType": "CLOSE",
                        "size": "1000",
                    }
                ]
            },
        },
        {"status": 0, "data": {"list": []}},
        {"status": 0, "data": {"list": []}},
    ]
    result = reconcile_fixed(
        V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)),
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    assert result.snapshot == result.snapshot.flat()


def test_malformed_post_envelope_is_rejected_by_sanitized_parser() -> None:
    with pytest.raises(V4GmoActualTransportError, match="STATUS_INVALID"):
        V4GmoPrivateEnvelope.from_injected_payload({"status": "0"})


def test_request_building_does_not_touch_transport() -> None:
    transport = TimeoutPrivateTransport()
    adapter = V4GmoActualAdapter(transport=transport)
    request = adapter._build_action_request(
        plan=action_plan(V4GmoAction.MARKET_ENTRY),
        reconciliation=None,
        protection_plan=None,
    )
    assert request.transport_path == "/private/v1/order"
    assert transport.calls == 0


def test_actual_adapter_is_isolated_and_has_no_logging_env_or_runtime_binding() -> None:
    source = inspect.getsource(adapter_module) + inspect.getsource(transport_module)
    forbidden = (
        "app.live_verification",
        "main_readonly",
        "os.environ",
        "os.getenv",
        "load_dotenv",
        "logging.",
        "print(",
        "while True",
        "time.sleep",
        "ENABLE_LIVE_TRADING",
    )
    for marker in forbidden:
        assert marker not in source
    assert "V4GmoActualActivationPermit(" not in source.replace(
        "class V4GmoActualActivationPermit:", ""
    )


def test_actual_transport_requires_permit_and_db_backed_boundary_proof() -> None:
    source = inspect.getsource(transport_module.V4GmoHttpxPrivateTransport.request)
    assert "assert_real_broker_post_allowed(allow=True)" in source
    assert "V4_GMO_ACTIVATION_PERMIT_NOT_ISSUED" in source
    assert "consume_persisted_transport_authorization" in source
    assert "self._client.request" in source

    forged = object.__new__(transport_module.V4GmoHttpxPrivateTransport)
    get_request = transport_module.V4GmoPrivateRequest(
        method="GET",
        transport_path="/private/v1/openPositions",
        signing_path="/v1/openPositions",
        params={"count": "100"},
        body=None,
    )
    with pytest.raises(
        transport_module.V4GmoActualTransportError,
        match="V4_GMO_ACTIVATION_PERMIT_NOT_ISSUED",
    ):
        forged.request(get_request)
