from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from app.h11_auto.contracts import SignalDecision
from app.h11_auto.v4_gmo_canary_activation import (
    V4ActivatedRuntimeScope,
    V4CurrentTurnChallenge,
    V4GmoCanaryActivationError,
    V4GmoCanaryIntent,
    confirm_v4_current_turn_exact,
    confirm_v4_major_incident_resume_exact,
    issue_v4_gmo_actual_activation_permit,
)
from app.h11_auto.v4_gmo_contracts import V4GmoAction, build_v4_action_plan
from app.h11_auto.v4_gmo_persisted_authorization import (
    _TRANSPORT_TOKEN,
    V4PersistedTransportAuthorization,
)
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_gmo_actual_transport import (
    V4GmoActualTransportError,
    V4GmoHttpxPrivateTransport,
    V4GmoPrivateRequest,
    V4GmoSealedSecret,
    V4GmoSignedRequestFactory,
    v4_gmo_private_request_binding_digest,
)

GENERATION_DIGEST = "sha256:" + "a" * 64
CYCLE_REF = "b" * 64
RESUME_PHRASE = "I APPROVE H11 V4 MAJOR INCIDENT RESUME FOR THIS REVIEWED GENERATION ONLY"


@dataclass(frozen=True)
class _FakeCredentials:
    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4GmoSealedSecret, V4GmoSealedSecret]:
        return V4GmoSealedSecret("fake-key"), V4GmoSealedSecret("fake-secret")


@dataclass
class _FakeResponse:
    payload: Any

    def json(self) -> Any:
        return self.payload


@dataclass
class _FakeHttpClient:
    calls: list[tuple[str, str]] = field(default_factory=list)

    def request(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
        del kwargs
        self.calls.append((method, url))
        return _FakeResponse({"status": 0, "data": {}})

    def close(self) -> None:
        pass


@dataclass
class _MalformedHttpClient:
    payload: Any
    calls: int = 0

    def request(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
        del method, url, kwargs
        self.calls += 1
        return _FakeResponse(self.payload)

    def close(self) -> None:
        pass


def _intent() -> V4GmoCanaryIntent:
    return V4GmoCanaryIntent(
        generation_digest=GENERATION_DIGEST,
        cycle_ref=CYCLE_REF,
        side="BUY",
        exact_order_sheet_digest="sha256:" + "c" * 64,
    )


def _permit(tmp_path: Path, *, monotonic: float = 10.0):
    intent = _intent()
    resume = confirm_v4_major_incident_resume_exact(
        phrase=RESUME_PHRASE,
        generation_digest=GENERATION_DIGEST,
    )
    challenge = V4CurrentTurnChallenge.create(intent=intent)
    current = confirm_v4_current_turn_exact(
        typed_phrase=challenge.phrase_for_operator_internal(),
        challenge=challenge,
        intent=intent,
    )
    return issue_v4_gmo_actual_activation_permit(
        intent=intent,
        resume_proof=resume,
        current_turn_proof=current,
        repository=tmp_path,
        now_monotonic=monotonic,
    )


def test_current_turn_challenge_and_permit_are_fresh_one_use(tmp_path: Path) -> None:
    intent = _intent()
    challenge = V4CurrentTurnChallenge.create(intent=intent)
    with pytest.raises(V4GmoCanaryActivationError, match="MISMATCH"):
        confirm_v4_current_turn_exact(
            typed_phrase="stale confirmation",
            challenge=challenge,
            intent=intent,
        )
    permit = _permit(tmp_path)
    state_root = v4_gmo_runtime_state_root(
        repository=tmp_path,
        generation_digest=GENERATION_DIGEST,
    )
    marker = json.loads(
        (state_root / "activation-permit-issued.json").read_text(encoding="utf-8")
    )
    assert marker["status"] == "ISSUED_ONE_USE_NOT_POSTED"
    with pytest.raises(V4GmoCanaryActivationError, match="ALREADY_USED"):
        _permit(tmp_path)
    assert permit is not None


def test_activated_runtime_scope_cannot_be_constructed_by_caller() -> None:
    with pytest.raises(V4GmoCanaryActivationError, match="SCOPE_INVALID"):
        V4ActivatedRuntimeScope(
            token=object(),
            generation_digest=GENERATION_DIGEST,
            cycle_ref=CYCLE_REF,
            intent_digest="sha256:" + "c" * 64,
            side="BUY",
            size=1_000,
            symbol="USD_JPY",
            execution_type="MARKET",
            entry_expires_monotonic=30.0,
        )


def test_actual_transport_refuses_post_without_db_backed_final_proof(
    tmp_path: Path,
) -> None:
    client = _FakeHttpClient()
    transport = V4GmoHttpxPrivateTransport(
        activation_permit=_permit(tmp_path),
        signed_request_factory=V4GmoSignedRequestFactory(
            credential_pair=_FakeCredentials()
        ),
        client=client,  # type: ignore[arg-type]
        monotonic_factory=lambda: 10.1,
        unknown_post_callback=lambda: None,
    )
    request = V4GmoPrivateRequest(
        method="POST",
        transport_path="/private/v1/order",
        signing_path="/v1/order",
        params={},
        body={
            "symbol": "USD_JPY",
            "side": "BUY",
            "size": "1000",
            "clientOrderId": "H11V4E" + CYCLE_REF[:30],
            "executionType": "MARKET",
        },
    )
    with pytest.raises(V4GmoActualTransportError, match="AUTHORIZATION_REQUIRED"):
        transport.request(request)
    assert client.calls == []


@pytest.mark.parametrize("payload", ([], {"data": {}}))
def test_post_unparseable_result_latches_halt_once_without_resend(
    tmp_path: Path,
    payload: Any,
) -> None:
    client = _MalformedHttpClient(payload=payload)
    halt_calls: list[bool] = []
    transport = V4GmoHttpxPrivateTransport(
        activation_permit=_permit(tmp_path),
        signed_request_factory=V4GmoSignedRequestFactory(
            credential_pair=_FakeCredentials()
        ),
        client=client,  # type: ignore[arg-type]
        monotonic_factory=lambda: 10.1,
        unknown_post_callback=lambda: halt_calls.append(True),
    )
    request = V4GmoPrivateRequest(
        method="POST",
        transport_path="/private/v1/order",
        signing_path="/v1/order",
        params={},
        body={
            "symbol": "USD_JPY",
            "side": "BUY",
            "size": "1000",
            "clientOrderId": "H11V4E" + CYCLE_REF[:30],
            "executionType": "MARKET",
        },
    )
    plan = build_v4_action_plan(
        cycle_ref=CYCLE_REF,
        action=V4GmoAction.MARKET_ENTRY,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    proof = V4PersistedTransportAuthorization(
        token=_TRANSPORT_TOKEN,
        plan=plan,
        request_binding_digest=v4_gmo_private_request_binding_digest(request),
    )

    with pytest.raises(V4GmoActualTransportError, match="RESULT_UNKNOWN"):
        transport.request(
            request,
            persisted_transport_authorization=proof,
        )
    assert client.calls == 1
    assert halt_calls == [True]
    with pytest.raises(V4GmoActualTransportError):
        transport.request(
            request,
            persisted_transport_authorization=proof,
        )
    assert client.calls == 1
    assert halt_calls == [True]
