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
from app.h11_auto.v4_gmo_protection import (
    H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    build_exact_fill_oco_plan_no_post,
)
from app.private_api.auth import create_signature
from app.services import h11_v4_gmo_actual_adapter as adapter_module
from app.services import h11_v4_gmo_actual_transport as transport_module
from app.services.h11_v4_gmo_actual_adapter import (
    V4GmoActualAdapter,
    V4GmoActualAdapterError,
    V4GmoPrivateOutcome,
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

    def request(self, request: V4GmoPrivateRequest) -> V4GmoPrivateEnvelope:
        self.requests.append(request)
        if not self.responses:
            raise V4GmoActualTransportError("FAKE_RESPONSE_MISSING")
        return V4GmoPrivateEnvelope.from_injected_payload(self.responses.pop(0))


@dataclass
class TimeoutPrivateTransport:
    calls: int = 0

    def request(self, request: V4GmoPrivateRequest) -> V4GmoPrivateEnvelope:
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
    size: int = 10_000,
    side: SignalDecision = SignalDecision.BUY,
):
    return build_v4_action_plan(
        cycle_ref=CYCLE_REF,
        action=action,
        side=side,
        requested_size=size,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
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
                        "size": "4000",
                    },
                    {
                        "clientOrderId": entry_client_id(),
                        "positionId": 1002,
                        "symbol": "USD_JPY",
                        "side": "BUY",
                        "settleType": "OPEN",
                        "size": "2000",
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
                        "size": "4000",
                        "price": "150.000",
                    },
                    {
                        "positionId": 1002,
                        "symbol": "USD_JPY",
                        "side": "BUY",
                        "size": "2000",
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
                        "size": "10000",
                    }
                ]
            },
        },
    ]


def test_activation_permit_is_structurally_unavailable() -> None:
    with pytest.raises(V4GmoActualTransportError, match="NOT_ISSUED"):
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
            "size": "10000",
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
    transport = FakePrivateTransport(responses=[{"status": 0}, {"status": 0}, {"status": 0}])
    adapter = V4GmoActualAdapter(transport=transport)

    assert adapter.perform_once(plan=action_plan(V4GmoAction.MARKET_ENTRY)) is (
        V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )
    market = transport.requests[0]
    assert market.transport_path == "/private/v1/order"
    assert market.signing_path == "/v1/order"
    assert market.body == {
        "symbol": "USD_JPY",
        "side": "BUY",
        "size": "10000",
        "clientOrderId": entry_client_id(),
        "executionType": "MARKET",
    }

    assert (
        adapter.perform_once(plan=action_plan(V4GmoAction.CANCEL_ENTRY_REMAINDER, size=4_000))
        is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )
    cancel = transport.requests[1]
    assert cancel.transport_path == "/private/v1/cancelOrders"
    assert cancel.body == {"clientOrderIds": [entry_client_id()]}
    assert len(entry_client_id()) == 36

    assert (
        adapter.perform_once(plan=action_plan(V4GmoAction.CANCEL_MISMATCHED_PROTECTION, size=6_000))
        is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )
    cancel_protection = transport.requests[2]
    assert cancel_protection.body == {"clientOrderIds": [protection_client_id()]}


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
                "size": "10000",
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
                "size": "10000",
                "clientOrderId": protection_client_id(),
                "executionType": "MARKET",
            },
        )


def test_partial_fill_reconciliation_aggregates_owned_position_parts() -> None:
    transport = FakePrivateTransport(responses=partial_responses())
    result = V4GmoActualAdapter(transport=transport).reconcile(
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=10_000,
    )
    assert result.snapshot.result_known is True
    assert result.snapshot.position_count == 1
    assert result.snapshot.filled_size == 6_000
    assert result.snapshot.pending_entry_size == 4_000
    assert result.snapshot.entry_status is V4GmoEntryStatus.PARTIAL
    assert result.snapshot.protection_status is V4GmoProtectionStatus.NONE
    assert result.average_fill_price == Decimal("150.002")
    assert result.position_bundle is not None
    assert result.position_bundle.total_size == 6_000
    assert "1001" not in repr(result)
    assert "1002" not in repr(result.position_bundle)
    assert result.raw_response_retained is False
    assert result.identifier_exposed is False
    assert [request.signing_path for request in transport.requests] == [
        "/v1/latestExecutions",
        "/v1/openPositions",
        "/v1/activeOrders",
    ]


def test_exact_oco_and_position_specific_exit_use_reconciled_bundle() -> None:
    reconcile_transport = FakePrivateTransport(responses=partial_responses())
    reconciliation = V4GmoActualAdapter(transport=reconcile_transport).reconcile(
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=10_000,
    )
    protection = build_exact_fill_oco_plan_no_post(
        position_side=SignalDecision.BUY,
        reconciled_average_fill_price=Decimal("150.002"),
        frozen_signal_atr_24=Decimal("0.100"),
        reconciled_filled_size=6_000,
    )
    transport = FakePrivateTransport(responses=[{"status": 0}, {"status": 0}])
    adapter = V4GmoActualAdapter(transport=transport)

    outcome = adapter.perform_once(
        plan=action_plan(V4GmoAction.EXACT_SIZE_OCO_PROTECTION, size=6_000),
        reconciliation=reconciliation,
        protection_plan=protection,
    )
    assert outcome is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    oco = transport.requests[0]
    assert oco.transport_path == "/private/v1/closeOrder"
    assert oco.body is not None
    assert oco.body["executionType"] == "OCO"
    assert oco.body["side"] == "SELL"
    assert oco.body["clientOrderId"] == protection_client_id()
    assert oco.body["settlePosition"] == [
        {"positionId": 1001, "size": "4000"},
        {"positionId": 1002, "size": "2000"},
    ]

    outcome = adapter.perform_once(
        plan=action_plan(V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT, size=6_000),
        reconciliation=reconciliation,
    )
    assert outcome is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    close = transport.requests[1]
    assert close.body is not None
    assert close.body["executionType"] == "MARKET"
    assert close.body["side"] == "SELL"
    assert close.body["settlePosition"] == oco.body["settlePosition"]


def test_sell_entry_and_exit_side_are_mapped_without_inference() -> None:
    transport = FakePrivateTransport(responses=[{"status": 0}])
    adapter = V4GmoActualAdapter(transport=transport)
    assert (
        adapter.perform_once(plan=action_plan(V4GmoAction.MARKET_ENTRY, side=SignalDecision.SELL))
        is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )
    assert transport.requests[0].body is not None
    assert transport.requests[0].body["side"] == "SELL"


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
                    "size": "6000",
                },
                {
                    "clientOrderId": protection_client_id(),
                    "symbol": "USD_JPY",
                    "settleType": "CLOSE",
                    "size": "6000",
                },
            ]
        },
    }
    result = V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)).reconcile(
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=10_000,
    )
    assert result.snapshot.pending_entry_size == 0
    assert result.snapshot.protection_size == 6_000
    assert result.snapshot.protection_status is V4GmoProtectionStatus.EXACT_MATCH
    assert result.snapshot.entry_status is V4GmoEntryStatus.FILLED


def test_unowned_position_or_order_fails_closed_without_identifier_exposure() -> None:
    responses = partial_responses()
    responses[1]["data"]["list"][0]["positionId"] = 9999
    result = V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)).reconcile(
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=10_000,
    )
    assert result.snapshot.result_known is False
    assert result.snapshot.entry_status is V4GmoEntryStatus.UNKNOWN
    assert "9999" not in repr(result)

    responses = partial_responses()
    responses[2]["data"]["list"].append(
        {
            "clientOrderId": "MANUALORDER000000000000000000000001",
            "symbol": "USD_JPY",
            "settleType": "OPEN",
            "size": "10000",
        }
    )
    result = V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)).reconcile(
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=10_000,
    )
    assert result.snapshot.result_known is False


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
                        "size": "10000",
                    }
                ]
            },
        },
        {"status": 0, "data": {"list": []}},
        {"status": 0, "data": {"list": []}},
    ]
    result = V4GmoActualAdapter(transport=FakePrivateTransport(responses=responses)).reconcile(
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=10_000,
    )
    assert result.snapshot == result.snapshot.flat()


def test_malformed_post_envelope_is_unknown_without_second_attempt() -> None:
    transport = FakePrivateTransport(responses=[{"status": "0"}])
    adapter = V4GmoActualAdapter(transport=transport)
    plan = action_plan(V4GmoAction.MARKET_ENTRY)
    assert adapter.perform_once(plan=plan) is V4GmoPrivateOutcome.UNKNOWN_SANITIZED
    assert len(transport.requests) == 1
    with pytest.raises(V4GmoActualAdapterError, match="SECOND_ATTEMPT_FORBIDDEN"):
        adapter.perform_once(plan=plan)


def test_same_action_and_unknown_outcome_never_retry() -> None:
    transport = TimeoutPrivateTransport()
    adapter = V4GmoActualAdapter(transport=transport)
    plan = action_plan(V4GmoAction.MARKET_ENTRY)
    assert adapter.perform_once(plan=plan) is V4GmoPrivateOutcome.UNKNOWN_SANITIZED
    assert transport.calls == 1
    with pytest.raises(V4GmoActualAdapterError, match="SECOND_ATTEMPT_FORBIDDEN"):
        adapter.perform_once(plan=plan)
    assert transport.calls == 1


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


def test_actual_transport_request_is_unavailable_even_after_low_level_forgery() -> None:
    source = inspect.getsource(transport_module.V4GmoHttpxPrivateTransport.request)
    assert "assert_real_broker_post_allowed(allow=False)" in source
    assert "V4_GMO_ACTIVATION_PERMIT_NOT_ISSUED" in source
    assert "self._factory.build" not in source
    assert "self._client.request" not in source

    forged = object.__new__(transport_module.V4GmoHttpxPrivateTransport)
    get_request = transport_module.V4GmoPrivateRequest(
        method="GET",
        transport_path="/private/v1/openPositions",
        signing_path="/v1/openPositions",
        params={"symbol": "USD_JPY", "count": "100"},
        body=None,
    )
    with pytest.raises(
        transport_module.V4GmoActualTransportError,
        match="V4_GMO_ACTIVATION_PERMIT_NOT_ISSUED",
    ):
        forged.request(get_request)
