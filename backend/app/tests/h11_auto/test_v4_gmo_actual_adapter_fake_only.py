from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx
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



def test_transport_unknown_failure_is_classified_into_fixed_labels() -> None:
    # Diagnostic classes carry ONLY the failure mechanism, never broker content:
    # a real incident (entry POST -> unknown halt, no broker-side order record)
    # must be attributable to timeout / connection / non-JSON / invalid envelope.
    classify = transport_module._classify_private_result_unknown
    assert classify(httpx.ConnectTimeout("t")) == (
        "V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT"
    )
    assert classify(httpx.ConnectError("c")) == (
        "V4_GMO_PRIVATE_RESULT_UNKNOWN_CONNECTION"
    )
    assert classify(json.JSONDecodeError("m", "<html>", 0)) == (
        "V4_GMO_PRIVATE_RESULT_UNKNOWN_NON_JSON"
    )
    assert classify(
        V4GmoActualTransportError("V4_GMO_RESPONSE_STATUS_INVALID")
    ) == "V4_GMO_PRIVATE_RESULT_UNKNOWN_ENVELOPE_INVALID"
    # Anything unrecognised collapses to the base label; no content leaks through.
    assert classify(ValueError("broker said <html>")) == (
        "V4_GMO_PRIVATE_RESULT_UNKNOWN"
    )


def test_adapter_failure_class_only_passes_fixed_internal_labels() -> None:
    sanitize = adapter_module._sanitized_failure_class
    assert sanitize(
        V4GmoActualTransportError("V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT")
    ) == "V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT"
    assert sanitize(
        V4GmoActualTransportError("V4_GMO_CURRENT_TURN_ENTRY_SCOPE_EXPIRED_OR_MISMATCHED")
    ) == "V4_GMO_CURRENT_TURN_ENTRY_SCOPE_EXPIRED_OR_MISMATCHED"
    # Arbitrary text (possible broker content) never passes through.
    assert sanitize(V4GmoActualTransportError("broker said: <html>")) == (
        "V4_GMO_PRIVATE_RESULT_UNKNOWN"
    )
    # Membership is EXACT, not a charset/shape test: a label merely SHAPED like an
    # internal one (e.g. a future f-string carrying a broker code) is refused.
    assert sanitize(V4GmoActualTransportError("V4_GMO_ERR5106_REJECTED")) == (
        "V4_GMO_PRIVATE_RESULT_UNKNOWN"
    )
    assert sanitize(TimeoutError()) == "V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT"
    assert sanitize(OSError()) == "V4_GMO_PRIVATE_RESULT_UNKNOWN_CONNECTION"


def test_every_transport_error_label_is_a_non_interpolated_literal() -> None:
    # The allow-list is only trustworthy while transport labels stay literal: an
    # f-string label could otherwise be built to match an enumerated entry.
    source = inspect.getsource(transport_module)
    assert 'V4GmoActualTransportError(f"' not in source
    assert "V4GmoActualTransportError(f'" not in source
    # Every enumerated surfaceable class must actually be a fixed string constant.
    for label in transport_module.V4_GMO_SURFACEABLE_FAILURE_CLASSES:
        assert label.startswith("V4_GMO_")
        assert f'"{label}"' in source


def test_perform_once_records_failure_class_behaviourally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Behavioural (not source-scan): drive real outcomes through perform_once and
    # assert the recorded diagnostic, so a dead assignment would fail the test.
    # The authorization CONSUMER is stubbed rather than forging an issuance, so the
    # coordinator-only issuer invariant stays intact.
    monkeypatch.setattr(
        adapter_module,
        "consume_persisted_action_authorization",
        lambda *args, **kwargs: object(),
    )

    def _run(transport: Any) -> tuple[Any, str | None]:
        adapter = V4GmoActualAdapter(transport=transport)
        outcome = adapter.perform_once(
            plan=action_plan(V4GmoAction.MARKET_ENTRY),
            persisted_authorization=object(),  # type: ignore[arg-type]
            now_monotonic=1.0,
        )
        return outcome, adapter.last_failure_class

    timeout_outcome, timeout_label = _run(TimeoutPrivateTransport())
    assert timeout_outcome is adapter_module.V4GmoPrivateOutcome.UNKNOWN_SANITIZED
    assert timeout_label == "V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT"

    rejected_outcome, rejected_label = _run(
        FakePrivateTransport(responses=[{"status": 5}])
    )
    assert rejected_outcome is adapter_module.V4GmoPrivateOutcome.REJECTED_SANITIZED
    assert rejected_label == "V4_GMO_PRIVATE_RESULT_REJECTED_BY_BROKER"

    accepted_outcome, accepted_label = _run(
        FakePrivateTransport(responses=[{"status": 0}])
    )
    assert accepted_outcome is adapter_module.V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    assert accepted_label is None


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
    assert waits == pytest.approx([0.55, 0.55, 0.55])


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
    assert starts == pytest.approx([100.55, 101.10, 101.65])


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
        later - earlier >= 0.549999
        for earlier, later in zip(starts[:-1], starts[1:], strict=True)
    )


def test_reconcile_first_get_waits_out_the_post_to_get_pacing() -> None:
    # A reconciliation started right after a POST must keep the first GET at least
    # V4_PRIVATE_POST_TO_GET_PACING_SECONDS after that POST, so the post-entry
    # reconciliation can never share the broker's one-second window with the entry.
    transport = FakePrivateTransport(responses=partial_responses())
    adapter = V4GmoActualAdapter(transport=transport)
    adapter._last_private_post_start_monotonic = 100.0
    clock = [100.2]
    starts: list[float] = []
    original_request = transport.request

    def request(request: V4GmoPrivateRequest) -> V4GmoPrivateEnvelope:
        starts.append(clock[0])
        return original_request(request)

    transport.request = request  # type: ignore[method-assign]

    def wait(seconds: float) -> None:
        clock[0] += seconds

    result = adapter.reconcile_at_fixed_cadence(
        cycle_ref=CYCLE_REF,
        side=SignalDecision.BUY,
        requested_size=1_000,
        monotonic_factory=lambda: clock[0],
        wait=wait,
    )
    assert result.snapshot.result_known is True
    # Without the POST buffer the first GET would start at 100.75 (100.2 + 0.55);
    # the POST at 100.0 pushes it to 101.10.
    assert starts[0] == pytest.approx(101.10)


def test_reconcile_records_failure_class_for_rejected_and_timeout_gets() -> None:
    # A rate-limited/rejected GET (JSON envelope with status != 0) and a timed-out
    # GET must be distinguishable when the reconciliation comes back unknown.
    rejected = V4GmoActualAdapter(
        transport=FakePrivateTransport(responses=[{"status": 5}])
    )
    result = reconcile_fixed(
        rejected, cycle_ref=CYCLE_REF, side=SignalDecision.BUY, requested_size=1_000
    )
    assert result.snapshot.result_known is False
    assert rejected.last_failure_class == "V4_GMO_PRIVATE_GET_REJECTED_BY_BROKER"

    timed_out = V4GmoActualAdapter(transport=TimeoutPrivateTransport())
    result = reconcile_fixed(
        timed_out, cycle_ref=CYCLE_REF, side=SignalDecision.BUY, requested_size=1_000
    )
    assert result.snapshot.result_known is False
    assert timed_out.last_failure_class == "V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT"


def test_coordinated_path_paces_posts_and_classifies_reconcile_unknown() -> None:
    from types import SimpleNamespace

    from app.services.h11_v4_gmo_coordinated_actual_path import (
        _RECONCILIATION_UNKNOWN_LABELS,
        V4GmoCoordinatedActualPath,
    )

    # The classification map is a closed literal->literal mapping.
    assert _RECONCILIATION_UNKNOWN_LABELS[
        "V4_GMO_PRIVATE_GET_REJECTED_BY_BROKER"
    ] == "V4_COORDINATED_RECONCILIATION_REJECTED_BY_BROKER"
    assert _RECONCILIATION_UNKNOWN_LABELS[
        "V4_GMO_PRIVATE_RESULT_UNKNOWN_TIMEOUT"
    ] == "V4_COORDINATED_RECONCILIATION_UNKNOWN_TIMEOUT"

    # _pace_before_private_post waits (never skips) until the POST is clear of the
    # last GET by the GET->POST buffer and of the last POST by the POST->POST buffer.
    path = object.__new__(V4GmoCoordinatedActualPath)
    clock = [100.0]
    waits: list[float] = []

    def wait(seconds: float) -> None:
        waits.append(seconds)
        clock[0] += seconds

    path.monotonic_clock = lambda: clock[0]
    path.reconciliation_wait = wait
    path.adapter = SimpleNamespace(
        _last_private_get_start_monotonic=99.5,
        _last_private_post_start_monotonic=None,
    )
    path._pace_before_private_post()
    assert waits == pytest.approx([0.6])  # 99.5 + 1.10 = 100.6

    path.adapter = SimpleNamespace(
        _last_private_get_start_monotonic=None,
        _last_private_post_start_monotonic=100.0,
    )
    path._pace_before_private_post()
    assert waits[-1] == pytest.approx(0.6)  # 100.0 + 1.20 = 101.2 from 100.6

    # Already clear of both buffers: no wait at all.
    before = len(waits)
    path.adapter = SimpleNamespace(
        _last_private_get_start_monotonic=clock[0] - 5.0,
        _last_private_post_start_monotonic=clock[0] - 5.0,
    )
    path._pace_before_private_post()
    assert len(waits) == before


def test_private_call_budget_keeps_oco_post_inside_protection_deadline() -> None:
    # Worst pre-OCO chain: entry POST + 3 reconcile GETs, each running to the full
    # HTTP timeout, plus the post->get and get->post pacing buffers. The OCO must
    # still be POSTED within the frozen 15s protection deadline with real margin.
    from app.h11_auto.v4_activation_preparation import (
        V4_PRIVATE_GET_PACING_SECONDS,
        V4_PRIVATE_GET_TO_POST_PACING_SECONDS,
        V4_PRIVATE_POST_TO_GET_PACING_SECONDS,
    )
    from app.services.h11_v4_gmo_actual_transport import (
        GMO_V4_PRIVATE_HTTP_TIMEOUT_SECONDS,
    )

    timeout = GMO_V4_PRIVATE_HTTP_TIMEOUT_SECONDS
    worst_case = (
        4 * timeout
        + V4_PRIVATE_POST_TO_GET_PACING_SECONDS
        + 2 * V4_PRIVATE_GET_PACING_SECONDS
        + V4_PRIVATE_GET_TO_POST_PACING_SECONDS
    )
    assert worst_case <= 15.0 - 1.5  # >=1.5s margin for store/plan/signing work


def test_fixed_get_cadence_fails_closed_on_monotonic_clock_regression() -> None:
    transport = FakePrivateTransport(responses=partial_responses())
    readings = iter((100.0, 100.0, 100.55, 100.10))

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
