"""C-1 acceptance tests: the dispatch boundary, not the outer catch-all, owns
the unknown-halt latch (R1: false-UNKNOWN eradication).

Authored by the reviewer, not the implementer (see the operating rules in
docs/H11_V4_COMPLETION_PLAN_HANDOFF.md §1). Fake-only: no broker access, no
credentials, no LaunchAgent interaction, no notification, no network.

The single property this file protects
--------------------------------------
A persistent halt may only be latched at the true dispatch boundary (the
transport's unknown-post callback).  Failures that occur BEFORE dispatch (no
POST sent) must be retryable and must NOT manufacture a false-UNKNOWN
permanent halt.  Tests 1-3 go through the real coordinated-path / transport
wiring, not direct calls to the classification helper, so removing the wiring
breaks them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import app.h11_auto.v4_actual_preparation_guard as preparation_guard
from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import DeadManStore, PhaseBRiskStore
from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_actual_coordinator import V4GmoActualCoordinatorStore
from app.h11_auto.v4_gmo_canary_activation import (
    V4CurrentTurnChallenge,
    V4GmoCanaryIntent,
    confirm_v4_current_turn_exact,
    confirm_v4_major_incident_resume_exact,
    issue_v4_gmo_actual_activation_permit,
)
from app.h11_auto.v4_gmo_contracts import (
    V4GmoAction,
    V4GmoBrokerSnapshot,
    V4GmoExecutionPolicy,
    build_v4_action_plan,
)
from app.h11_auto.v4_gmo_generation import (
    build_v4_gmo_frozen_generation,
    v4_gmo_dead_man_policy,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_persisted_authorization import (
    _TRANSPORT_TOKEN,
    V4PersistedTransportAuthorization,
)
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_g075_runtime import (
    G075_PERSISTENT_HALT_FILE,
    G075Action,
    G075ActionOutcome,
    G075Error,
    G075OneShotActionDispatcher,
)
from app.services.h11_v4_gmo_actual_adapter import (
    V4GmoActualReconciliation,
    V4GmoPrivateOutcome,
)
from app.services.h11_v4_gmo_actual_transport import (
    V4GmoActualTransportError,
    V4GmoHttpxPrivateTransport,
    V4GmoPrivateEnvelope,
    V4GmoPrivateRequest,
    V4GmoSealedSecret,
    V4GmoSignedRequestFactory,
    v4_gmo_private_request_binding_digest,
)
from app.services.h11_v4_gmo_coordinated_actual_path import (
    V4GmoCoordinatedActualPath,
    V4GmoCoordinatedPathError,
)

NOW = datetime(2026, 7, 16, 3, 0, tzinfo=UTC)
IMPLEMENTATION_DIGEST = "sha256:" + "a" * 64
GENERATION_DIGEST = "sha256:" + "a" * 64
CYCLE_REF = "b" * 64
RESUME_PHRASE = "I APPROVE H11 V4 MAJOR INCIDENT RESUME FOR THIS REVIEWED GENERATION ONLY"


# ---------------------------------------------------------------- helpers


class _Clock:
    wall: datetime = NOW + timedelta(seconds=1)
    monotonic: float = 101.0

    def wall_now(self) -> datetime:
        return self.wall

    def monotonic_now(self) -> float:
        return self.monotonic

    def advance(self, seconds: float) -> None:
        self.wall += timedelta(seconds=seconds)
        self.monotonic += seconds


@dataclass
class _FakeTransport:
    responses: list[dict[str, Any]]
    requests: list[Any] = field(default_factory=list)
    posts_dispatched: int = 0

    def request(self, request: Any, **kwargs: object) -> V4GmoPrivateEnvelope:
        del kwargs
        self.requests.append(request)
        return V4GmoPrivateEnvelope.from_injected_payload(self.responses.pop(0))


@dataclass
class _PreDispatchRaisingAdapter:
    """Adapter whose perform_once fails before any transport call."""

    transport: _FakeTransport
    _last_private_get_start_monotonic: float | None = None
    _last_private_post_start_monotonic: float | None = None

    def reconcile(self, **kwargs: object) -> V4GmoActualReconciliation:
        del kwargs
        return V4GmoActualReconciliation(
            snapshot=V4GmoBrokerSnapshot.flat(),
            position_bundle=None,
            average_fill_price=None,
        )

    def perform_once(self, **kwargs: object) -> object:
        del kwargs
        raise TimeoutError("synthetic pre-dispatch adapter failure")


@dataclass
class _LatchedThenRaisingAdapter:
    """Adapter that models a real post-dispatch unknown: the transport's
    unknown-post callback latches the store, then the transport re-raises."""

    transport: _FakeTransport
    store: V4GmoActualCoordinatorStore
    _last_private_get_start_monotonic: float | None = None
    _last_private_post_start_monotonic: float | None = None

    def reconcile(self, **kwargs: object) -> V4GmoActualReconciliation:
        del kwargs
        return V4GmoActualReconciliation(
            snapshot=V4GmoBrokerSnapshot.flat(),
            position_bundle=None,
            average_fill_price=None,
        )

    def perform_once(self, **kwargs: object) -> object:
        del kwargs
        self.store.engage_unknown_halt()
        raise TimeoutError("synthetic post-dispatch unknown")


@dataclass
class _DispatchThenSuccessAdapter:
    """Adapter that models a successful POST: the dispatch counter advances and
    perform_once returns normally.  A failure in the coordinated path's
    outcome-recording step (``_finish_transport``) then happens AFTER the POST
    reached the broker."""

    transport: _FakeTransport
    _last_private_get_start_monotonic: float | None = None
    _last_private_post_start_monotonic: float | None = None

    def reconcile(self, **kwargs: object) -> V4GmoActualReconciliation:
        del kwargs
        return V4GmoActualReconciliation(
            snapshot=V4GmoBrokerSnapshot.flat(),
            position_bundle=None,
            average_fill_price=None,
        )

    def perform_once(self, **kwargs: object) -> V4GmoPrivateOutcome:
        del kwargs
        self.transport.posts_dispatched += 1
        return V4GmoPrivateOutcome.ACCEPTED_SANITIZED


def _policy() -> V4GmoExecutionPolicy:
    selected = V4ApprovedOperatorSelections()
    return V4GmoExecutionPolicy(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        selected_horizon=selected.selected_horizon,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
        max_entries_per_day=selected.maximum_entries_per_day,
    )


def _signal(*, observed_at_utc: datetime = NOW) -> FormalSignal:
    selected = V4ApprovedOperatorSelections()
    return FormalSignal(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        horizon=FormalHorizon.MINUTES_30,
        observed_at_utc=observed_at_utc,
        valid_until_utc=observed_at_utc + timedelta(minutes=1),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.61"),
    )


def _generation():
    return build_v4_gmo_frozen_generation(
        generation_label="H11_AUTO_30M_20260716_G001",
        implementation_digest=IMPLEMENTATION_DIGEST,
        policy=_policy(),
    )


def _runtime_root(repository: Path) -> Path:
    root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=_generation().digest,
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def _runtime_safety(
    tmp_path: Path, *, heartbeat_at: datetime = NOW + timedelta(seconds=1)
) -> tuple[PhaseBRiskStore, Any, DeadManStore]:
    risk_policy = v4_gmo_risk_policy()
    risk_store = PhaseBRiskStore(tmp_path / "risk.json", policy=risk_policy)
    dead_man = DeadManStore(
        tmp_path / "dead-man.json",
        policy=v4_gmo_dead_man_policy(),
    )
    dead_man.heartbeat(heartbeat_utc=heartbeat_at)
    return risk_store, risk_policy, dead_man


def _market_plan(store: V4GmoActualCoordinatorStore, signal: FormalSignal):
    return build_v4_action_plan(
        cycle_ref=store.cycle_ref_for_signal_internal(signal.fingerprint),
        action=V4GmoAction.MARKET_ENTRY,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def _path_preflight(
    path: V4GmoCoordinatedActualPath,
    signal: FormalSignal,
    cycle_ref: str,
) -> None:
    transport = path.adapter.transport
    if isinstance(transport, _FakeTransport):
        transport.responses[:0] = [
            {"status": 0, "data": {"list": []}},
            {"status": 0, "data": {"list": []}},
            {"status": 0, "data": {"list": []}},
        ]
    clock = getattr(path.monotonic_clock, "__self__", None)
    assert isinstance(clock, _Clock)
    path.reconciliation_wait = clock.advance
    evidence = path.reconcile_once_fixed(
        cycle_ref=cycle_ref,
        side=signal.decision,
        requested_size=1_000,
    )
    if isinstance(transport, _FakeTransport):
        transport.requests.clear()
    generation_suffix = path.generation.digest.removeprefix("sha256:")
    preparation_state_root = (
        path.store.path.parent / f"preparation-{cycle_ref}-{generation_suffix}"
    )
    preparation_state_root.mkdir(parents=True, exist_ok=True)
    path.record_canary_entry_preflight(
        signal_fingerprint=signal.fingerprint,
        cycle_ref=cycle_ref,
        instruction_bid=Decimal("159.995"),
        instruction_ask=Decimal("160.000"),
        reconciliation_evidence=evidence,
        preparation_evidence=preparation_guard.V4CompletedPreparationEvidence(
            token=preparation_guard._COMPLETED_EVIDENCE_TOKEN,
            generation_digest=path.generation.digest,
            state_root=preparation_state_root,
            trading_day_jst="2026-07-16",
        ),
    )


def _market_path(
    tmp_path: Path, adapter: object
) -> tuple[V4GmoCoordinatedActualPath, V4GmoActualCoordinatorStore, FormalSignal, str]:
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    signal = _signal()
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW - timedelta(seconds=20),
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(runtime_root)
    clock = _Clock()
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=adapter,  # type: ignore[arg-type]
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
    )
    _path_preflight(path, signal, cycle_ref)
    return path, store, signal, cycle_ref


@dataclass(frozen=True)
class _FakeCredentials:
    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4GmoSealedSecret, V4GmoSealedSecret]:
        return V4GmoSealedSecret("fake-key"), V4GmoSealedSecret("fake-secret")


@dataclass
class _KeyboardInterruptClient:
    calls: int = 0

    def request(self, method: str, url: str, **kwargs: object) -> object:
        del method, url, kwargs
        self.calls += 1
        raise KeyboardInterrupt

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


def _entry_post_request() -> V4GmoPrivateRequest:
    return V4GmoPrivateRequest(
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


class _PreDispatchFailingPort:
    def attempt_once(self, scope: object) -> object:
        del scope
        raise V4GmoCoordinatedPathError(
            "V4_GMO_PRE_DISPATCH_FAILURE_NO_POST_SENT"
        )


class _GenericFailingPort:
    def attempt_once(self, scope: object) -> object:
        del scope
        raise RuntimeError("synthetic unclassifiable failure")


class _WorkingPort:
    def __init__(self, outcome: G075ActionOutcome) -> None:
        self.outcome = outcome

    def attempt_once(self, scope: object) -> G075ActionOutcome:
        del scope
        return self.outcome


# ------------------------------------------------------------- S1 wiring


def test_pre_dispatch_failure_does_not_latch_halt(tmp_path: Path) -> None:
    """The outer coordinated-path handler must not manufacture a false-UNKNOWN
    halt: a failure before any POST was dispatched (store not latched) is
    retryable and is reported as V4_GMO_PRE_DISPATCH_FAILURE_NO_POST_SENT."""
    raising = _PreDispatchRaisingAdapter(transport=_FakeTransport(responses=[]))
    path, store, signal, _cycle_ref = _market_path(tmp_path, raising)

    with pytest.raises(V4GmoCoordinatedPathError, match="PRE_DISPATCH_FAILURE"):
        path.perform_market_once(
            signal_fingerprint=signal.fingerprint,
            plan=_market_plan(store, signal),
        )
    assert store.unknown_halt_latched() is False
    assert raising.transport.requests == []


def test_latched_store_re_raises_and_keeps_halt(tmp_path: Path) -> None:
    """When the store IS latched (the transport callback ran, so a POST may
    have reached the broker), the original failure is re-raised and the halt
    stays latched — the handler must not convert it into a retryable
    pre-dispatch error."""
    latching = _LatchedThenRaisingAdapter(
        transport=_FakeTransport(responses=[]),
        store=None,  # replaced below after store exists
    )
    path, store, signal, _cycle_ref = _market_path(
        tmp_path, _PreDispatchRaisingAdapter(transport=_FakeTransport(responses=[]))
    )
    latching.store = store
    path.adapter = latching  # type: ignore[assignment]
    with pytest.raises(TimeoutError, match="post-dispatch unknown"):
        path.perform_market_once(
            signal_fingerprint=signal.fingerprint,
            plan=_market_plan(store, signal),
        )
    assert store.unknown_halt_latched() is True


def test_post_dispatched_but_outcome_recording_failed_latches_halt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-1f: a POST that REACHED the broker (the dispatch counter advanced)
    but whose outcome could not be recorded must latch the store — it must
    NOT be misclassified as V4_GMO_PRE_DISPATCH_FAILURE_NO_POST_SENT."""
    dispatching = _DispatchThenSuccessAdapter(
        transport=_FakeTransport(responses=[])
    )
    path, store, signal, _cycle_ref = _market_path(tmp_path, dispatching)

    def _fail_finish_transport(**kwargs: object) -> object:
        del kwargs
        raise RuntimeError("synthetic outcome recording failure")

    monkeypatch.setattr(path, "_finish_transport", _fail_finish_transport)

    with pytest.raises(RuntimeError, match="outcome recording failure"):
        path.perform_market_once(
            signal_fingerprint=signal.fingerprint,
            plan=_market_plan(store, signal),
        )
    assert store.unknown_halt_latched() is True
    assert dispatching.transport.posts_dispatched == 1


# ----------------------------------------------------------------- S0


def test_keyboard_interrupt_during_post_runs_unknown_callback(
    tmp_path: Path,
) -> None:
    """Ctrl-C (or any BaseException) during an in-flight POST must run the
    transport's unknown-post callback before re-raising; otherwise the
    interrupted POST would silently skip the latch and the process would die
    with the outcome unknown."""
    client = _KeyboardInterruptClient()
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
    request = _entry_post_request()
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


# ------------------------------------------------------ G075 action wrapper


def test_g075_wrapper_pre_dispatch_failure_is_retryable(tmp_path: Path) -> None:
    """A labeled pre-dispatch failure must not write a .result. marker, must
    not latch a halt, and must drop the .started. marker so the same
    action_key can be attempted again."""
    dispatcher = G075OneShotActionDispatcher.bound(
        state_root=tmp_path,
        port=_PreDispatchFailingPort(),
        generation_digest="sha256:" + "a" * 64,
        reviewed_files_digest="sha256:" + "b" * 64,
        release_capability_digest="sha256:" + "c" * 64,
        strategy_artifact_digest="sha256:" + "d" * 64,
    )
    kwargs = {
        "cycle_id": "cycle-1",
        "action": G075Action.PROTECTION,
        "side": "BUY",
        "quantity": 1_000,
        "reconciliation_artifact_digest": "sha256:" + "1" * 64,
        "now_utc": NOW,
    }
    with pytest.raises(G075Error, match="G075_ACTION_PRE_DISPATCH_FAILED_RETRYABLE"):
        dispatcher.attempt_once(**kwargs)
    assert not list(tmp_path.glob("g075-action-*.result.json"))
    assert not (tmp_path / G075_PERSISTENT_HALT_FILE).exists()
    assert not list(tmp_path.glob("g075-action-*.started.json"))

    # Same action_key (same cycle/action/reconciliation digest) can be retried.
    dispatcher.port = _WorkingPort(G075ActionOutcome.PROTECTED)
    outcome = dispatcher.attempt_once(**kwargs)
    assert outcome is G075ActionOutcome.PROTECTED
    assert not (tmp_path / G075_PERSISTENT_HALT_FILE).exists()


def test_g075_wrapper_unclassifiable_failure_is_fail_safe(tmp_path: Path) -> None:
    """Any failure that cannot be classified as pre-dispatch keeps the
    existing fail-safe: an UNKNOWN result marker and a persistent halt."""
    dispatcher = G075OneShotActionDispatcher.bound(
        state_root=tmp_path,
        port=_GenericFailingPort(),
        generation_digest="sha256:" + "a" * 64,
        reviewed_files_digest="sha256:" + "b" * 64,
        release_capability_digest="sha256:" + "c" * 64,
        strategy_artifact_digest="sha256:" + "d" * 64,
    )
    with pytest.raises(G075Error, match="G075_ACTION_RESULT_UNKNOWN_NO_RETRY"):
        dispatcher.attempt_once(
            cycle_id="cycle-2",
            action=G075Action.CLOSE_POSITION,
            side="BUY",
            quantity=1_000,
            reconciliation_artifact_digest="sha256:" + "2" * 64,
            now_utc=NOW,
        )
    results = list(tmp_path.glob("g075-action-*.result.json"))
    assert len(results) == 1
    payload = json.loads(results[0].read_text(encoding="utf-8"))
    assert payload["status"] == G075ActionOutcome.UNKNOWN.value
    assert (tmp_path / G075_PERSISTENT_HALT_FILE).is_file()
    # The started marker is NOT removed: the action is terminal.
    assert list(tmp_path.glob("g075-action-*.started.json"))


# ------------------------------------------------------- wiring sensitivity


def test_wiring_is_sensitive_to_classification_and_callback() -> None:
    """Tests 1/2 exercise the real coordinated-path handler and test 3 the
    real transport, so removing either wiring point breaks them.  Additionally
    pin the two wiring points in source so a rewrite that keeps direct-call
    tests green cannot silently drop them."""
    repo = Path(__file__).resolve().parents[4]
    coordinated = (
        repo / "backend/app/services/h11_v4_gmo_coordinated_actual_path.py"
    ).read_text(encoding="utf-8")
    assert "if self.store.unknown_halt_latched():" in coordinated
    assert "V4_GMO_PRE_DISPATCH_FAILURE_NO_POST_SENT" in coordinated
    assert (
        "except BaseException:\n            self.store.engage_unknown_halt()"
        not in coordinated
    )
    transport = (
        repo / "backend/app/services/h11_v4_gmo_actual_transport.py"
    ).read_text(encoding="utf-8")
    assert "except BaseException as error:  # noqa: BLE001" in transport
    assert "self._unknown_post_callback()" in transport
