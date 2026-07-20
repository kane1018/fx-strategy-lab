from __future__ import annotations

import inspect
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

import app.h11_auto.v4_actual_preparation_guard as preparation_guard
from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import DeadManStore, PhaseBRiskStore
from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_actual_coordinator import (
    _ENTRY_PREFLIGHT_ISSUER_TOKEN,
    V4_ACCOUNT_EXCLUSIVITY_REQUIRED,
    V4_CLOCK_STATUS_REQUIRED,
    V4_NOTIFICATION_STATUS_REQUIRED,
    V4CanaryEntryPreflightEvidence,
    V4GmoActualCoordinatorError,
    V4GmoActualCoordinatorStore,
    _V4VerifiedEntryPreflightAuthorization,
    calculate_v4_planned_loss,
)
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
    V4GmoEntryStatus,
    V4GmoExecutionPolicy,
    V4GmoProtectionStatus,
    build_v4_action_plan,
    v4_gmo_scheduled_time_exit_at,
)
from app.h11_auto.v4_gmo_generation import (
    V4_GMO_GENERATION_SCHEMA,
    V4GmoGenerationError,
    build_v4_gmo_frozen_generation,
    load_v4_gmo_frozen_generation,
    v4_gmo_dead_man_policy,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_persisted_authorization import (
    V4PersistedAuthorizationError,
    consume_persisted_action_authorization,
)
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.services.h11_v4_gmo_actual_adapter import (
    V4GmoActualAdapter,
    V4GmoActualAdapterError,
    V4GmoActualReconciliation,
    V4GmoPrivateOutcome,
    v4_gmo_client_order_id,
)
from app.services.h11_v4_gmo_actual_runtime_binding import (
    bind_v4_gmo_actual_runtime,
)
from app.services.h11_v4_gmo_actual_runtime_driver import V4GmoActualRuntimeDriver
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
    v4_gmo_runtime_state_root,
)
from app.services.h11_v4_gmo_exit_dispatcher import V4GmoExitDispatchResult
from app.services.h11_v4_gmo_public_market_status import (
    V4GmoPublicMarketStatusError,
    V4GmoPublicMarketStatusReader,
)

NOW = datetime(2026, 7, 16, 3, 0, tzinfo=UTC)
IMPLEMENTATION_DIGEST = "sha256:" + "a" * 64
RECONCILIATION_DIGEST = "sha256:" + "b" * 64


@dataclass
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
    requests: list[V4GmoPrivateRequest] = field(default_factory=list)

    def request(
        self,
        request: V4GmoPrivateRequest,
        *,
        persisted_transport_authorization: object | None = None,
    ) -> V4GmoPrivateEnvelope:
        del persisted_transport_authorization
        self.requests.append(request)
        return V4GmoPrivateEnvelope.from_injected_payload(self.responses.pop(0))


@dataclass
class _TimeoutThenReadTransport:
    requests: list[V4GmoPrivateRequest] = field(default_factory=list)
    calls: int = 0

    def request(
        self,
        request: V4GmoPrivateRequest,
        *,
        persisted_transport_authorization: object | None = None,
    ) -> V4GmoPrivateEnvelope:
        del persisted_transport_authorization
        self.requests.append(request)
        self.calls += 1
        if request.method == "POST":
            raise TimeoutError
        return V4GmoPrivateEnvelope.from_injected_payload(
            {"status": 0, "data": {"list": []}}
        )


def _policy() -> V4GmoExecutionPolicy:
    selected = V4ApprovedOperatorSelections()
    return V4GmoExecutionPolicy(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        selected_horizon=selected.selected_horizon,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
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


def _public_status_evidence(*, generation_digest: str, status: str, monotonic: float):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"status": 0, "data": {"status": status}},
            )
        ),
        base_url="https://forex-api.coin.z.com",
    ) as client:
        return V4GmoPublicMarketStatusReader(
            generation_digest=generation_digest,
            client=client,
            monotonic_factory=lambda: monotonic,
        ).read_once()


def test_v4_public_market_status_evidence_is_one_shot_and_fail_closed() -> None:
    evidence = _public_status_evidence(
        generation_digest=_generation().digest,
        status="OPEN",
        monotonic=100.0,
    )
    evidence.require_fresh_open(
        generation_digest=_generation().digest,
        now_monotonic=101.0,
    )
    with pytest.raises(V4GmoPublicMarketStatusError, match="EVIDENCE_INVALID"):
        evidence.require_fresh_open(
            generation_digest=_generation().digest,
            now_monotonic=101.5,
        )


def _market_plan(
    store: V4GmoActualCoordinatorStore,
    signal: FormalSignal,
    *,
    side: SignalDecision = SignalDecision.BUY,
    size: int = 1_000,
):
    return build_v4_action_plan(
        cycle_ref=store.cycle_ref_for_signal_internal(signal.fingerprint),
        action=V4GmoAction.MARKET_ENTRY,
        side=side,
        requested_size=size,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def _flat_reconciliation() -> V4GmoActualReconciliation:
    return V4GmoActualReconciliation(
        snapshot=V4GmoBrokerSnapshot.flat(),
        position_bundle=None,
        average_fill_price=None,
    )


def _record_flat_preflight(
    store: V4GmoActualCoordinatorStore,
    signal: FormalSignal,
    *,
    now_utc: datetime,
    now_monotonic: float,
) -> object:
    reconciliation = _flat_reconciliation()
    return store._record_entry_preflight_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        evidence=V4CanaryEntryPreflightEvidence(
            generation_digest=_generation().digest,
            cycle_ref=store.cycle_ref_for_signal_internal(signal.fingerprint),
            signal_fingerprint=signal.fingerprint,
            clock_status_label=V4_CLOCK_STATUS_REQUIRED,
            notification_status_label=V4_NOTIFICATION_STATUS_REQUIRED,
            account_exclusivity_label=V4_ACCOUNT_EXCLUSIVITY_REQUIRED,
            unowned_position_count=0,
            active_order_count=0,
            unowned_active_order_count=0,
        ),
        snapshot=reconciliation.snapshot,
        position_bundle_present=False,
        average_fill_price_present=False,
        instruction_bid=Decimal("159.995"),
        instruction_ask=Decimal("160.000"),
        authoritative_reconciliation_digest=reconciliation._binding_digest_internal(),
        now_utc=now_utc,
        now_monotonic=now_monotonic,
    )


def _record_market(
    store: V4GmoActualCoordinatorStore,
    signal: FormalSignal,
    *,
    now_utc: datetime = NOW + timedelta(seconds=1),
    now_monotonic: float = 101.0,
    resolve_filled: bool = True,
):
    entry_authorization = _record_flat_preflight(
        store,
        signal,
        now_utc=now_utc - timedelta(milliseconds=100),
        now_monotonic=now_monotonic - 0.1,
    )
    attempt = store._record_market_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        entry_authorization=entry_authorization,
        signal_fingerprint=signal.fingerprint,
        plan=_market_plan(store, signal),
        now_utc=now_utc,
        now_monotonic=now_monotonic,
    )
    store._record_transport_outcome_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        cycle_ref=attempt.cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
        outcome_label="ACCEPTED_SANITIZED",
    )
    if resolve_filled:
        store._resolve_pending_transport_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            cycle_ref=attempt.cycle_ref,
            snapshot=V4GmoBrokerSnapshot(
                fresh=True,
                result_known=True,
                position_count=1,
                position_side=signal.decision,
                filled_size=1_000,
                pending_entry_size=0,
                protection_size=0,
                entry_status=V4GmoEntryStatus.FILLED,
                protection_status=V4GmoProtectionStatus.NONE,
            ),
            position_bundle_total=1_000,
            authoritative_reconciliation_digest=RECONCILIATION_DIGEST,
            now_utc=now_utc + timedelta(milliseconds=100),
        )
    return attempt


def _prepare_exact_protected_store(
    tmp_path: Path,
    *,
    entry_time_utc: datetime = NOW + timedelta(seconds=1),
) -> tuple[FormalSignal, Path, V4GmoActualCoordinatorStore, str]:
    observed_at_utc = entry_time_utc - timedelta(seconds=1)
    signal = _signal(observed_at_utc=observed_at_utc)
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=observed_at_utc,
    )
    _record_market(store, signal, now_utc=entry_time_utc)
    protection = store._persist_exact_protection_plan_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        reconciled_average_fill_price=Decimal("160.000"),
        reconciled_filled_size=1_000,
        now_utc=entry_time_utc + timedelta(seconds=1),
        now_monotonic=102.0,
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    protection_action = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    store._record_exact_protection_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        plan=protection_action,
        protection_plan=protection,
        reconciliation_digest=RECONCILIATION_DIGEST,
        now_utc=entry_time_utc + timedelta(seconds=1),
        now_monotonic=102.0,
    )
    store._record_transport_outcome_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        cycle_ref=cycle_ref,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
        outcome_label="ACCEPTED_SANITIZED",
    )
    store._resolve_pending_transport_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        cycle_ref=cycle_ref,
        snapshot=V4GmoBrokerSnapshot(
            fresh=True,
            result_known=True,
            position_count=1,
            position_side=SignalDecision.BUY,
            filled_size=1_000,
            pending_entry_size=0,
            protection_size=1_000,
            entry_status=V4GmoEntryStatus.FILLED,
            protection_status=V4GmoProtectionStatus.EXACT_MATCH,
        ),
        position_bundle_total=1_000,
        authoritative_reconciliation_digest=RECONCILIATION_DIGEST,
        now_utc=entry_time_utc + timedelta(seconds=2),
    )
    return signal, runtime_root, store, cycle_ref


def _test_only_entry_authorization(
    store: V4GmoActualCoordinatorStore,
    signal: FormalSignal,
) -> _V4VerifiedEntryPreflightAuthorization:
    """Fabricate the private capability only for lower-store negative tests."""

    with sqlite3.connect(store.path) as connection:
        row = connection.execute(
            "SELECT cycle_ref,entry_preflight_digest FROM cycles WHERE signal_fingerprint=?",
            (signal.fingerprint,),
        ).fetchone()
    assert row is not None
    assert row[1] is not None
    return _V4VerifiedEntryPreflightAuthorization(
        token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        cycle_ref=str(row[0]),
        signal_fingerprint=signal.fingerprint,
        preflight_digest=str(row[1]),
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
    if isinstance(transport, _FakeTransport | _TimeoutThenReadTransport):
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
        ),
    )


def _path_partial_reconciliation(
    path: V4GmoCoordinatedActualPath,
    *,
    cycle_ref: str,
) -> object:
    transport = path.adapter.transport
    assert isinstance(transport, _FakeTransport)
    entry_id = v4_gmo_client_order_id(
        cycle_ref=cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
    )
    transport.responses[:0] = [
        {
            "status": 0,
            "data": {
                "list": [
                    {
                        "clientOrderId": entry_id,
                        "positionId": 1001,
                        "symbol": "USD_JPY",
                        "side": "BUY",
                        "settleType": "OPEN",
                        "size": "600",
                    }
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
                        "size": "600",
                        "price": "160.000",
                    }
                ]
            },
        },
        {
            "status": 0,
            "data": {
                "list": [
                    {
                        "clientOrderId": entry_id,
                        "symbol": "USD_JPY",
                        "settleType": "OPEN",
                        "size": "1000",
                    }
                ]
            },
        },
    ]
    clock = getattr(path.monotonic_clock, "__self__", None)
    assert isinstance(clock, _Clock)
    path.reconciliation_wait = clock.advance
    evidence = path.reconcile_once_fixed(
        cycle_ref=cycle_ref,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    if isinstance(transport, _FakeTransport | _TimeoutThenReadTransport):
        transport.requests.clear()
    return evidence


def _path_filled_reconciliation(
    path: V4GmoCoordinatedActualPath,
    *,
    cycle_ref: str,
    filled_size: int,
) -> object:
    transport = path.adapter.transport
    assert isinstance(transport, _FakeTransport)
    entry_id = v4_gmo_client_order_id(
        cycle_ref=cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
    )
    transport.responses[:0] = [
        {
            "status": 0,
            "data": {
                "list": [
                    {
                        "clientOrderId": entry_id,
                        "positionId": 1001,
                        "symbol": "USD_JPY",
                        "side": "BUY",
                        "settleType": "OPEN",
                        "size": str(filled_size),
                    }
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
                        "size": str(filled_size),
                        "price": "160.000",
                    }
                ]
            },
        },
        {"status": 0, "data": {"list": []}},
    ]
    evidence = path.reconcile_once_fixed(
        cycle_ref=cycle_ref,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    transport.requests.clear()
    return evidence


def _path_protected_reconciliation(
    path: V4GmoCoordinatedActualPath,
    *,
    cycle_ref: str,
    filled_size: int,
) -> object:
    transport = path.adapter.transport
    assert isinstance(transport, _FakeTransport)
    entry_id = v4_gmo_client_order_id(
        cycle_ref=cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
    )
    protection_id = v4_gmo_client_order_id(
        cycle_ref=cycle_ref,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
    )
    transport.responses[:0] = [
        {
            "status": 0,
            "data": {
                "list": [
                    {
                        "clientOrderId": entry_id,
                        "positionId": 1001,
                        "symbol": "USD_JPY",
                        "side": "BUY",
                        "settleType": "OPEN",
                        "size": str(filled_size),
                    }
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
                        "size": str(filled_size),
                        "price": "160.000",
                    }
                ]
            },
        },
        {
            "status": 0,
            "data": {
                "list": [
                    {
                        "clientOrderId": protection_id,
                        "symbol": "USD_JPY",
                        "settleType": "CLOSE",
                        "size": str(filled_size),
                    },
                    {
                        "clientOrderId": protection_id,
                        "symbol": "USD_JPY",
                        "settleType": "CLOSE",
                        "size": str(filled_size),
                    },
                ]
            },
        },
    ]
    evidence = path.reconcile_once_fixed(
        cycle_ref=cycle_ref,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    transport.requests.clear()
    return evidence


def test_v4_generation_is_separate_frozen_and_disabled() -> None:
    generation = _generation()
    assert generation.schema == V4_GMO_GENERATION_SCHEMA
    assert generation.actual_post_authorized is False
    assert generation.live_ready is False
    assert generation.unattended_live_supported is False
    assert generation.operator_selection_digest == V4ApprovedOperatorSelections().digest
    assert generation.digest.startswith("sha256:")
    with pytest.raises(V4GmoGenerationError, match="operator selection"):
        build_v4_gmo_frozen_generation(
            generation_label="H11_AUTO_30M_20260716_G001",
            implementation_digest=IMPLEMENTATION_DIGEST,
            policy=V4GmoExecutionPolicy(
                strategy_version="SHORT_V1",
                signal_config_hash="sha256:wrong",
                selected_horizon=FormalHorizon.MINUTES_30,
                protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
            ),
        )


def test_preflight_uses_reconciled_account_counts_not_hardcoded_zero() -> None:
    source = inspect.getsource(V4GmoCoordinatedActualPath.record_canary_entry_preflight)
    assert "reconciliation.unowned_position_count" in source
    assert "reconciliation.account_active_order_count" in source
    assert "reconciliation.unowned_active_order_count" in source
    assert "unowned_position_count=0" not in source
    assert "active_order_count=0" not in source
    assert "unowned_active_order_count=0" not in source


def test_frozen_generation_artifact_must_match_reviewed_digest(tmp_path: Path) -> None:
    generation = _generation()
    path = tmp_path / "docs/templates/h11_v4_gmo_frozen_generation.json"
    path.parent.mkdir(parents=True)
    path.write_text(generation.canonical_json, encoding="utf-8")
    assert (
        load_v4_gmo_frozen_generation(
            repository=tmp_path,
            implementation_digest=IMPLEMENTATION_DIGEST,
        )
        == generation
    )
    with pytest.raises(V4GmoGenerationError, match="implementation digest"):
        load_v4_gmo_frozen_generation(
            repository=tmp_path,
            implementation_digest="sha256:" + "c" * 64,
        )


def test_coordinated_runtime_refuses_fresh_noncanonical_state_paths(
    tmp_path: Path,
) -> None:
    runtime_root = _runtime_root(tmp_path)
    correct_store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    _, risk_policy, dead_man = _runtime_safety(runtime_root)
    wrong_risk_store = PhaseBRiskStore(
        tmp_path / "fresh-but-wrong" / "risk.json",
        policy=risk_policy,
    )
    with pytest.raises(
        V4GmoCoordinatedPathError,
        match="RUNTIME_PATHS_NOT_GENERATION_BOUND",
    ):
        V4GmoCoordinatedActualPath(
            repository=tmp_path,
            store=correct_store,
            adapter=V4GmoActualAdapter(transport=_FakeTransport(responses=[])),
            process_lock=lock,
            generation=_generation(),
            risk_store=wrong_risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man,
        )


def test_planned_loss_gate_counts_atr_stop_and_frozen_slippage() -> None:
    signal = _signal()
    risk = calculate_v4_planned_loss(
        signal_fingerprint=signal.fingerprint,
        frozen_atr_24=Decimal("0.20"),
        quantity_units=1_000,
        adverse_slippage_allowance_pips=Decimal("5.0"),
    )
    assert risk.planned_loss_bound_jpy == 351
    assert risk.atr_digest.startswith("sha256:")


def test_intent_attempt_and_oco_are_persisted_before_transport(tmp_path: Path) -> None:
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    risk = store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    assert risk.planned_loss_bound_jpy == 351
    attempt = _record_market(store, signal)
    assert attempt.transport_called is False
    assert attempt.actual_post_count == 0
    plan = store._persist_exact_protection_plan_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        reconciled_average_fill_price=Decimal("160.000"),
        reconciled_filled_size=1_000,
        now_utc=NOW + timedelta(seconds=10),
        now_monotonic=110.0,
    )
    assert plan.exact_filled_size == 1_000
    assert plan.actual_post_allowed is False
    with sqlite3.connect(store.path) as connection:
        metrics = connection.execute(
            "SELECT probability_up,instruction_bid,instruction_ask,"
            "entry_average_fill_price,entry_spread_pips,entry_slippage_pips "
            "FROM cycles"
        ).fetchone()
    assert metrics == ("0.61", "159.995", "160", "160", "0.5", "0")
    protection_action = build_v4_action_plan(
        cycle_ref=store.cycle_ref_for_signal_internal(signal.fingerprint),
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    protection_attempt = store._record_exact_protection_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        plan=protection_action,
        protection_plan=plan,
        reconciliation_digest=RECONCILIATION_DIGEST,
        now_utc=NOW + timedelta(seconds=11),
        now_monotonic=111.0,
    )
    assert protection_attempt.transport_called is False
    assert protection_attempt.actual_post_count == 0
    with pytest.raises(V4GmoActualCoordinatorError, match="second v4 protection"):
        store._record_exact_protection_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal.fingerprint,
            plan=protection_action,
            protection_plan=plan,
            reconciliation_digest=RECONCILIATION_DIGEST,
            now_utc=NOW + timedelta(seconds=12),
            now_monotonic=112.0,
        )


def test_evaluate_entry_intent_prices_without_reserving_a_cycle(tmp_path: Path) -> None:
    # evaluate validates and prices the entry for the order sheet but writes NO cycle,
    # so an operator who then mistypes/times out a confirmation leaves the generation
    # reusable.  reserve, called only after the exact confirmations succeed, then writes
    # exactly the cycle the pure cycle_ref predicted.
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    risk = store.evaluate_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    assert risk.planned_loss_bound_jpy == 351
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cycles").fetchone()[0] == 0
    pure_ref = store.cycle_ref_for_signal_pure(
        generation=_generation(), signal_fingerprint=signal.fingerprint
    )
    reserved = store.reserve_entry_cycle(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    assert reserved.planned_loss_bound_jpy == risk.planned_loss_bound_jpy
    assert store.cycle_ref_for_signal_internal(signal.fingerprint) == pure_ref
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cycles").fetchone()[0] == 1


def test_reserve_entry_cycle_blocks_any_second_cycle(tmp_path: Path) -> None:
    # The single-cycle guard is unchanged: once ANY cycle is reserved (i.e. an entry POST
    # has been committed to), no second cycle can be reserved for the generation, even for
    # a different, later actionable signal.
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    store.reserve_entry_cycle(
        generation=_generation(),
        signal=_signal(),
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    later = _signal(observed_at_utc=NOW + timedelta(seconds=30))
    assert later.fingerprint != _signal().fingerprint
    with pytest.raises(V4GmoActualCoordinatorError, match="already has a cycle"):
        store.reserve_entry_cycle(
            generation=_generation(),
            signal=later,
            policy=_policy(),
            frozen_atr_24=Decimal("0.20"),
            now_utc=NOW + timedelta(seconds=30),
        )
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cycles").fetchone()[0] == 1


def test_evaluate_entry_intent_fails_closed_on_unknown_halt(tmp_path: Path) -> None:
    # A latched unknown halt (e.g. a prior unknown transport result) still blocks even the
    # non-reserving evaluate path, so no order sheet is built after an ambiguous POST.
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    store.bind_generation(_generation())
    store.engage_unknown_halt()
    with pytest.raises(V4GmoActualCoordinatorError, match="unknown halt"):
        store.evaluate_entry_intent(
            generation=_generation(),
            signal=_signal(),
            policy=_policy(),
            frozen_atr_24=Decimal("0.20"),
            now_utc=NOW,
        )
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM cycles").fetchone()[0] == 0


def test_restart_refuses_second_market_attempt_and_generation_change(
    tmp_path: Path,
) -> None:
    path = tmp_path / "coordinator.sqlite3"
    signal = _signal()
    store = V4GmoActualCoordinatorStore(path)
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    plan = _market_plan(store, signal)
    _record_market(store, signal, resolve_filled=False)
    restarted = V4GmoActualCoordinatorStore(path)
    with pytest.raises(V4GmoActualCoordinatorError, match="unknown halt"):
        restarted._record_market_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            entry_authorization=_test_only_entry_authorization(restarted, signal),
            signal_fingerprint=signal.fingerprint,
            plan=plan,
            now_utc=NOW + timedelta(seconds=2),
            now_monotonic=102.0,
        )
    changed = build_v4_gmo_frozen_generation(
        generation_label="H11_AUTO_30M_20260716_G002",
        implementation_digest=IMPLEMENTATION_DIGEST,
        policy=_policy(),
    )
    with pytest.raises(V4GmoActualCoordinatorError, match="binding mismatch"):
        restarted.bind_generation(changed)


def test_restart_latches_unknown_when_process_dies_after_attempt_persist(
    tmp_path: Path,
) -> None:
    signal = _signal()
    database = tmp_path / "coordinator.sqlite3"
    store = V4GmoActualCoordinatorStore(database)
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    entry_authorization = _record_flat_preflight(
        store,
        signal,
        now_utc=NOW + timedelta(milliseconds=900),
        now_monotonic=100.9,
    )
    store._record_market_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        entry_authorization=entry_authorization,
        signal_fingerprint=signal.fingerprint,
        plan=_market_plan(store, signal),
        now_utc=NOW + timedelta(seconds=1),
        now_monotonic=101.0,
    )

    restarted = V4GmoActualCoordinatorStore(database)
    assert restarted.unknown_halt_latched() is True
    with pytest.raises(V4GmoActualCoordinatorError, match="unknown halt"):
        restarted._record_market_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            entry_authorization=_test_only_entry_authorization(restarted, signal),
            signal_fingerprint=signal.fingerprint,
            plan=_market_plan(restarted, signal),
            now_utc=NOW + timedelta(seconds=1, milliseconds=100),
            now_monotonic=101.1,
        )


@pytest.mark.parametrize(
    ("snapshot", "bundle_total", "classification"),
    (
        (
            V4GmoBrokerSnapshot(
                fresh=True,
                result_known=True,
                position_count=1,
                position_side=SignalDecision.BUY,
                filled_size=1_000,
                pending_entry_size=0,
                protection_size=0,
                entry_status=V4GmoEntryStatus.FILLED,
                protection_status=V4GmoProtectionStatus.NONE,
            ),
            1_000,
            "FILLED_UNPROTECTED",
        ),
        (
            V4GmoBrokerSnapshot(
                fresh=True,
                result_known=True,
                position_count=1,
                position_side=SignalDecision.BUY,
                filled_size=600,
                pending_entry_size=400,
                protection_size=0,
                entry_status=V4GmoEntryStatus.PARTIAL,
                protection_status=V4GmoProtectionStatus.NONE,
            ),
            600,
            "MARKET_PARTIAL_PENDING",
        ),
        (V4GmoBrokerSnapshot.flat(), None, "FLAT_OR_REJECTED"),
    ),
)
def test_crashed_market_is_classified_once_without_market_reauthorization(
    tmp_path: Path,
    snapshot: V4GmoBrokerSnapshot,
    bundle_total: int | None,
    classification: str,
) -> None:
    signal = _signal()
    database = tmp_path / "coordinator.sqlite3"
    store = V4GmoActualCoordinatorStore(database)
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    authorization = _record_flat_preflight(
        store,
        signal,
        now_utc=NOW + timedelta(milliseconds=900),
        now_monotonic=100.9,
    )
    store._record_market_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        entry_authorization=authorization,
        signal_fingerprint=signal.fingerprint,
        plan=_market_plan(store, signal),
        now_utc=NOW + timedelta(seconds=1),
        now_monotonic=101.0,
    )
    restarted = V4GmoActualCoordinatorStore(database)
    recovery = restarted._resolve_pending_transport_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        cycle_ref=restarted.cycle_ref_for_signal_internal(signal.fingerprint),
        snapshot=snapshot,
        position_bundle_total=bundle_total,
        authoritative_reconciliation_digest=RECONCILIATION_DIGEST,
        now_utc=NOW + timedelta(seconds=2),
    )
    assert recovery.classification == classification
    assert recovery.pending_marker_cleared is True
    assert restarted.unknown_halt_latched() is True
    with sqlite3.connect(database) as connection:
        pending = connection.execute(
            "SELECT 1 FROM metadata WHERE key='pending_transport_attempt'"
        ).fetchone()
        attempts = connection.execute(
            "SELECT COUNT(*) FROM attempts WHERE action='MARKET_ENTRY'"
        ).fetchone()[0]
    assert pending is None
    assert attempts == 1
    if classification == "MARKET_PARTIAL_PENDING":
        cancel = build_v4_action_plan(
            cycle_ref=recovery.cycle_ref,
            action=V4GmoAction.CANCEL_ENTRY_REMAINDER,
            side=SignalDecision.BUY,
            requested_size=snapshot.pending_entry_size,
            protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
        )
        prepared = restarted._record_risk_reducing_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            snapshot=snapshot,
            position_bundle_total=bundle_total,
            authoritative_reconciliation_digest=RECONCILIATION_DIGEST,
            now_utc=NOW + timedelta(seconds=2),
        )
        assert prepared.action == V4GmoAction.CANCEL_ENTRY_REMAINDER.value
    elif classification == "FILLED_UNPROTECTED":
        protection = restarted._persist_exact_protection_plan_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal.fingerprint,
            reconciled_average_fill_price=Decimal("160.000"),
            reconciled_filled_size=snapshot.filled_size,
            now_utc=NOW + timedelta(seconds=2),
            now_monotonic=102.0,
        )
        oco = build_v4_action_plan(
            cycle_ref=recovery.cycle_ref,
            action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
            side=SignalDecision.BUY,
            requested_size=snapshot.filled_size,
            protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
        )
        prepared = restarted._record_exact_protection_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal.fingerprint,
            plan=oco,
            protection_plan=protection,
            reconciliation_digest=RECONCILIATION_DIGEST,
            now_utc=NOW + timedelta(seconds=2),
            now_monotonic=102.0,
        )
        assert prepared.action == V4GmoAction.EXACT_SIZE_OCO_PROTECTION.value
    with pytest.raises(V4GmoActualCoordinatorError, match="unknown halt"):
        restarted._record_market_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            entry_authorization=_test_only_entry_authorization(restarted, signal),
            signal_fingerprint=signal.fingerprint,
            plan=_market_plan(restarted, signal),
            now_utc=NOW + timedelta(seconds=2),
            now_monotonic=102.0,
        )


def test_unknown_crashed_market_recovery_keeps_pending_marker(
    tmp_path: Path,
) -> None:
    signal = _signal()
    database = tmp_path / "coordinator.sqlite3"
    store = V4GmoActualCoordinatorStore(database)
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    authorization = _record_flat_preflight(
        store,
        signal,
        now_utc=NOW + timedelta(milliseconds=900),
        now_monotonic=100.9,
    )
    store._record_market_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        entry_authorization=authorization,
        signal_fingerprint=signal.fingerprint,
        plan=_market_plan(store, signal),
        now_utc=NOW + timedelta(seconds=1),
        now_monotonic=101.0,
    )
    restarted = V4GmoActualCoordinatorStore(database)
    unknown = V4GmoBrokerSnapshot(
        fresh=False,
        result_known=False,
        position_count=0,
        position_side=None,
        filled_size=0,
        pending_entry_size=0,
        protection_size=0,
        entry_status=V4GmoEntryStatus.UNKNOWN,
        protection_status=V4GmoProtectionStatus.UNKNOWN,
    )
    with pytest.raises(V4GmoActualCoordinatorError, match="remains unknown"):
        restarted._resolve_pending_transport_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            cycle_ref=restarted.cycle_ref_for_signal_internal(signal.fingerprint),
            snapshot=unknown,
            position_bundle_total=None,
            authoritative_reconciliation_digest=RECONCILIATION_DIGEST,
            now_utc=NOW + timedelta(seconds=2),
        )
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM metadata WHERE key='pending_transport_attempt'"
            ).fetchone()
            is not None
        )


def test_crash_recovery_requires_one_fresh_three_get_evidence(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    database = runtime_root / "coordinator.sqlite3"
    store = V4GmoActualCoordinatorStore(database)
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    authorization = _record_flat_preflight(
        store,
        signal,
        now_utc=NOW + timedelta(milliseconds=900),
        now_monotonic=100.9,
    )
    store._record_market_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        entry_authorization=authorization,
        signal_fingerprint=signal.fingerprint,
        plan=_market_plan(store, signal),
        now_utc=NOW + timedelta(seconds=1),
        now_monotonic=101.0,
    )
    restarted = V4GmoActualCoordinatorStore(database)
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(runtime_root)
    transport = _FakeTransport(
        responses=[
            {"status": 0, "data": {"list": []}},
            {"status": 0, "data": {"list": []}},
            {"status": 0, "data": {"list": []}},
        ]
    )
    clock = _Clock(wall=NOW + timedelta(seconds=2), monotonic=102.0)
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=restarted,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
        reconciliation_wait=clock.advance,
    )
    cycle_ref = restarted.cycle_ref_for_signal_internal(signal.fingerprint)
    evidence = path.reconcile_once_fixed(
        cycle_ref=cycle_ref,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    recovery = path.recover_pending_transport_once(
        cycle_ref=cycle_ref,
        reconciliation_evidence=evidence,
    )
    assert recovery.classification == "FLAT_OR_REJECTED"
    assert [request.method for request in transport.requests] == ["GET", "GET", "GET"]
    lock.release()


def test_loss_over_limit_and_protection_after_15_seconds_are_refused(
    tmp_path: Path,
) -> None:
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    with pytest.raises(V4GmoActualCoordinatorError, match="planned loss"):
        store.prepare_entry_intent(
            generation=_generation(),
            signal=signal,
            policy=_policy(),
            frozen_atr_24=Decimal("4.00"),
            now_utc=NOW,
        )

    accepted = _signal()
    store.prepare_entry_intent(
        generation=_generation(),
        signal=accepted,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, accepted)
    with pytest.raises(V4GmoActualCoordinatorError, match="deadline"):
        store._persist_exact_protection_plan_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=accepted.fingerprint,
            reconciled_average_fill_price=Decimal("160.000"),
            reconciled_filled_size=1_000,
            now_utc=NOW + timedelta(seconds=17),
            now_monotonic=117.0,
        )


def test_negative_deadline_and_tampered_atr_are_refused(tmp_path: Path) -> None:
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, signal)
    with pytest.raises(V4GmoActualCoordinatorError, match="deadline"):
        store._persist_exact_protection_plan_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal.fingerprint,
            reconciled_average_fill_price=Decimal("160.000"),
            reconciled_filled_size=1_000,
            now_utc=NOW,
            now_monotonic=100.0,
        )
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE cycles SET frozen_atr_24='0.21'")
    with pytest.raises(V4GmoActualCoordinatorError, match="ATR digest"):
        store._persist_exact_protection_plan_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal.fingerprint,
            reconciled_average_fill_price=Decimal("160.000"),
            reconciled_filled_size=1_000,
            now_utc=NOW + timedelta(seconds=10),
            now_monotonic=110.0,
        )


def test_protection_attempt_rechecks_deadline_after_plan_was_persisted(
    tmp_path: Path,
) -> None:
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, signal)
    plan = store._persist_exact_protection_plan_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        reconciled_average_fill_price=Decimal("160.000"),
        reconciled_filled_size=1_000,
        now_utc=NOW + timedelta(seconds=10),
        now_monotonic=110.0,
    )
    protection_action = build_v4_action_plan(
        cycle_ref=store.cycle_ref_for_signal_internal(signal.fingerprint),
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    with pytest.raises(V4GmoActualCoordinatorError, match="deadline"):
        store._record_exact_protection_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal.fingerprint,
            plan=protection_action,
            protection_plan=plan,
            reconciliation_digest=RECONCILIATION_DIGEST,
            now_utc=NOW + timedelta(seconds=17),
            now_monotonic=117.0,
        )


def test_integrated_path_commits_attempt_before_adapter_and_restart_cannot_send(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    plan = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(runtime_root)
    first_transport = _FakeTransport(responses=[{"status": 0}])
    clock = _Clock()
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=first_transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
    )
    _path_preflight(path, signal, cycle_ref)
    clock.advance(0.1)
    assert (
        path.perform_market_once(
            signal_fingerprint=signal.fingerprint,
            plan=plan,
        )
        is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )
    assert len(first_transport.requests) == 1

    restarted_transport = _FakeTransport(responses=[{"status": 0}])
    restarted = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=V4GmoActualCoordinatorStore(store.path),
        adapter=V4GmoActualAdapter(transport=restarted_transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
    )
    with pytest.raises(V4GmoCoordinatedPathError, match="UNKNOWN_HALT_LATCHED"):
        restarted.perform_market_once(
            signal_fingerprint=signal.fingerprint,
            plan=plan,
        )
    assert restarted_transport.requests == []
    lock.release()


def test_generation_preparation_evidence_cannot_preflight_second_coordinator(
    tmp_path: Path,
) -> None:
    signal = _signal()
    generation_suffix = _generation().digest.removeprefix("sha256:")
    state_root = (tmp_path / f"shared-preparation-{generation_suffix}").resolve()
    state_root.mkdir()
    first_evidence = preparation_guard.V4CompletedPreparationEvidence(
        token=preparation_guard._COMPLETED_EVIDENCE_TOKEN,
        generation_digest=_generation().digest,
        state_root=state_root,
    )
    second_evidence = preparation_guard.V4CompletedPreparationEvidence(
        token=preparation_guard._COMPLETED_EVIDENCE_TOKEN,
        generation_digest=_generation().digest,
        state_root=state_root,
    )

    paths: list[V4GmoCoordinatedActualPath] = []
    locks: list[H11AutoProcessLock] = []
    for label in ("first", "second"):
        repository = tmp_path / label
        root = _runtime_root(repository)
        store = V4GmoActualCoordinatorStore(root / "coordinator.sqlite3")
        store.prepare_entry_intent(
            generation=_generation(),
            signal=signal,
            policy=_policy(),
            frozen_atr_24=Decimal("0.20"),
            now_utc=NOW,
        )
        lock = H11AutoProcessLock(root / "process.lock")
        assert lock.acquire() is True
        risk_store, risk_policy, dead_man = _runtime_safety(root)
        clock = _Clock()
        path = V4GmoCoordinatedActualPath(
            repository=repository,
            store=store,
            adapter=V4GmoActualAdapter(
                transport=_FakeTransport(
                    responses=[
                        {"status": 0, "data": {"list": []}},
                        {"status": 0, "data": {"list": []}},
                        {"status": 0, "data": {"list": []}},
                    ]
                )
            ),
            process_lock=lock,
            generation=_generation(),
            risk_store=risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man,
            wall_clock=clock.wall_now,
            monotonic_clock=clock.monotonic_now,
            reconciliation_wait=clock.advance,
        )
        paths.append(path)
        locks.append(lock)

    first_reconciliation = paths[0].reconcile_once_fixed(
        cycle_ref=paths[0].store.cycle_ref_for_signal_internal(signal.fingerprint),
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    paths[0].record_canary_entry_preflight(
        signal_fingerprint=signal.fingerprint,
        cycle_ref=paths[0].store.cycle_ref_for_signal_internal(signal.fingerprint),
        instruction_bid=Decimal("159.995"),
        instruction_ask=Decimal("160.000"),
        reconciliation_evidence=first_reconciliation,
        preparation_evidence=first_evidence,
    )

    second_reconciliation = paths[1].reconcile_once_fixed(
        cycle_ref=paths[1].store.cycle_ref_for_signal_internal(signal.fingerprint),
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    with pytest.raises(
        preparation_guard.V4ActualPreparationGuardError,
        match="EVIDENCE_INVALID",
    ):
        paths[1].record_canary_entry_preflight(
            signal_fingerprint=signal.fingerprint,
            cycle_ref=paths[1].store.cycle_ref_for_signal_internal(signal.fingerprint),
            instruction_bid=Decimal("159.995"),
            instruction_ask=Decimal("160.000"),
            reconciliation_evidence=second_reconciliation,
            preparation_evidence=second_evidence,
        )
    for lock in locks:
        lock.release()


def test_integrated_path_requires_fresh_dead_man_before_market(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(
        runtime_root,
        heartbeat_at=NOW - timedelta(seconds=61),
    )
    transport = _FakeTransport(responses=[{"status": 0}])
    clock = _Clock()
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
    )
    plan = build_v4_action_plan(
        cycle_ref=store.cycle_ref_for_signal_internal(signal.fingerprint),
        action=V4GmoAction.MARKET_ENTRY,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    with pytest.raises(V4GmoCoordinatedPathError, match="DEAD_MAN_BLOCKED"):
        path.perform_market_once(
            signal_fingerprint=signal.fingerprint,
            plan=plan,
        )
    assert store.unknown_halt_latched() is True
    assert transport.requests == []
    lock.release()


def test_integrated_market_refuses_blocked_jst_hour_before_transport(
    tmp_path: Path,
) -> None:
    blocked_now = datetime(2026, 7, 16, 20, 0, tzinfo=UTC)  # Fri 05:00 JST
    selected = V4ApprovedOperatorSelections()
    signal = FormalSignal(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        horizon=FormalHorizon.MINUTES_30,
        observed_at_utc=blocked_now - timedelta(seconds=30),
        valid_until_utc=blocked_now + timedelta(seconds=30),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.61"),
    )
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=blocked_now - timedelta(seconds=20),
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    transport = _FakeTransport(responses=[])
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(
        runtime_root,
        heartbeat_at=blocked_now,
    )
    clock = _Clock(wall=blocked_now, monotonic=100.0)
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
    )
    _path_preflight(path, signal, cycle_ref)
    with pytest.raises(V4GmoCoordinatedPathError, match="ENTRY_TIME_BLOCKED"):
        path.perform_market_once(
            signal_fingerprint=signal.fingerprint,
            plan=_market_plan(store, signal),
        )
    assert transport.requests == []
    assert risk_store.load().entries_today == 0
    lock.release()


@pytest.mark.parametrize(
    ("now_utc", "expected"),
    (
        (datetime(2026, 7, 16, 20, 0, tzinfo=UTC), False),  # Fri 05:00 JST
        (datetime(2026, 7, 16, 15, 0, tzinfo=UTC), False),  # Fri 00:00 JST
        (datetime(2026, 7, 17, 0, 0, tzinfo=UTC), True),  # Fri 09:00 JST
        (datetime(2026, 7, 17, 11, 59, tzinfo=UTC), True),  # Fri 20:59 JST
        (datetime(2026, 7, 17, 12, 0, tzinfo=UTC), False),  # Fri 21:00 JST
        (datetime(2026, 7, 18, 3, 0, tzinfo=UTC), False),  # Sat 12:00 JST
        (datetime(2026, 7, 16, 11, 59, tzinfo=UTC), True),  # Thu 20:59 JST
        (datetime(2026, 7, 20, 1, 0, tzinfo=UTC), True),  # Mon 10:00 JST
    ),
)
def test_v4_generation_bound_entry_time_policy_covers_all_frozen_boundaries(
    now_utc: datetime,
    expected: bool,
) -> None:
    assert _policy().entry_time_allowed(now_utc=now_utc) is expected


def test_v4_scheduled_time_exit_is_23h_except_friday_03_45jst_start() -> None:
    thursday_entry = datetime(2026, 7, 16, 3, 0, tzinfo=UTC)  # Thu 12 JST
    friday_morning_entry = datetime(2026, 7, 17, 0, 0, tzinfo=UTC)  # Fri 09 JST
    friday_evening_entry = datetime(2026, 7, 17, 11, 0, tzinfo=UTC)  # Fri 20 JST

    assert v4_gmo_scheduled_time_exit_at(
        entry_time_utc=thursday_entry
    ) == thursday_entry + timedelta(seconds=82_800)
    assert v4_gmo_scheduled_time_exit_at(
        entry_time_utc=friday_morning_entry
    ) == datetime(2026, 7, 17, 18, 45, tzinfo=UTC)  # Sat 03:45 JST
    assert v4_gmo_scheduled_time_exit_at(
        entry_time_utc=friday_evening_entry
    ) == datetime(2026, 7, 17, 18, 45, tzinfo=UTC)  # Sat 03:45 JST
    assert (
        v4_gmo_scheduled_time_exit_at(entry_time_utc=datetime(2026, 7, 17, 9, 0))
        is None
    )


def test_unknown_market_latches_halt_but_readonly_reconciliation_remains_allowed(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(runtime_root)
    transport = _TimeoutThenReadTransport()
    clock = _Clock()
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    plan = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    _path_preflight(path, signal, cycle_ref)
    clock.advance(0.1)
    assert (
        path.perform_market_once(
            signal_fingerprint=signal.fingerprint,
            plan=plan,
        )
        is V4GmoPrivateOutcome.UNKNOWN_SANITIZED
    )
    assert store.unknown_halt_latched() is True
    evidence = path.reconcile_once_fixed(
        cycle_ref=cycle_ref,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    assert "redacted-one-use" in repr(evidence)
    assert len(transport.requests) == 4
    lock.release()


def test_exact_protection_confirmation_enforces_same_fifteen_second_deadline(
    tmp_path: Path,
) -> None:
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "accepted.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, signal)
    store._persist_exact_protection_plan_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        reconciled_average_fill_price=Decimal("160.000"),
        reconciled_filled_size=1_000,
        now_utc=NOW + timedelta(seconds=10),
        now_monotonic=110.0,
    )
    store.confirm_exact_protection_within_deadline(
        signal_fingerprint=signal.fingerprint,
        confirmed_protection_size=1_000,
        now_utc=NOW + timedelta(seconds=16),
        now_monotonic=116.0,
    )

    late = V4GmoActualCoordinatorStore(tmp_path / "late.sqlite3")
    late.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(late, signal)
    late._persist_exact_protection_plan_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        reconciled_average_fill_price=Decimal("160.000"),
        reconciled_filled_size=1_000,
        now_utc=NOW + timedelta(seconds=10),
        now_monotonic=110.0,
    )
    with pytest.raises(V4GmoActualCoordinatorError, match="confirmation failed"):
        late.confirm_exact_protection_within_deadline(
            signal_fingerprint=signal.fingerprint,
            confirmed_protection_size=1_000,
            now_utc=NOW + timedelta(seconds=16, microseconds=1),
            now_monotonic=116.000001,
        )


def test_risk_reducing_cancel_is_persisted_once_before_transport(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, signal, resolve_filled=False)
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(runtime_root)
    transport = _FakeTransport(responses=[{"status": 0}, {"status": 0}])
    clock = _Clock(wall=NOW + timedelta(seconds=2), monotonic=102.0)
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    recovery_evidence = _path_partial_reconciliation(path, cycle_ref=cycle_ref)
    assert (
        path.recover_pending_transport_once(
            cycle_ref=cycle_ref,
            reconciliation_evidence=recovery_evidence,
        ).classification
        == "MARKET_PARTIAL_PENDING"
    )
    cancel = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.CANCEL_ENTRY_REMAINDER,
        side=SignalDecision.BUY,
        requested_size=400,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    reconciliation_evidence = _path_partial_reconciliation(path, cycle_ref=cycle_ref)
    assert (
        path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            reconciliation_evidence=reconciliation_evidence,
        )
        is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )
    assert len(transport.requests) == 1
    with pytest.raises(V4GmoCoordinatedPathError, match="EVIDENCE_INVALID"):
        path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            reconciliation_evidence=reconciliation_evidence,
        )
    assert len(transport.requests) == 1
    lock.release()


def test_partial_fill_cancel_then_exact_filled_size_oco_is_authorized(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, signal, resolve_filled=False)
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(runtime_root)
    transport = _FakeTransport(responses=[{"status": 0}, {"status": 0}])
    clock = _Clock(wall=NOW + timedelta(seconds=2), monotonic=102.0)
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
        reconciliation_wait=clock.advance,
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    recovery_evidence = _path_partial_reconciliation(path, cycle_ref=cycle_ref)
    partial_recovery, partial_carried = path.recover_pending_transport_and_carry_once(
        cycle_ref=cycle_ref,
        reconciliation_evidence=recovery_evidence,
    )
    assert partial_recovery.classification == "MARKET_PARTIAL_PENDING"
    cancel, carried_partial = path.prepare_cancel_entry_remainder_plan(
        signal_fingerprint=signal.fingerprint,
        reconciliation_evidence=partial_carried,
    )
    assert cancel.action is V4GmoAction.CANCEL_ENTRY_REMAINDER
    assert cancel.requested_size == 400
    assert (
        path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            reconciliation_evidence=carried_partial,
        )
        is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )

    recovery_after_cancel = _path_filled_reconciliation(
        path,
        cycle_ref=cycle_ref,
        filled_size=600,
    )
    filled_recovery, filled_carried = path.recover_pending_transport_and_carry_once(
        cycle_ref=cycle_ref,
        reconciliation_evidence=recovery_after_cancel,
    )
    assert filled_recovery.classification == "FILLED_UNPROTECTED"
    protection, carried_evidence = path.prepare_exact_protection_plan(
        signal_fingerprint=signal.fingerprint,
        reconciliation_evidence=filled_carried,
    )
    assert protection.exact_filled_size == 600
    oco = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
        side=SignalDecision.BUY,
        requested_size=600,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    assert (
        path.perform_exact_protection_once(
            signal_fingerprint=signal.fingerprint,
            plan=oco,
            protection_plan=protection,
            reconciliation_evidence=carried_evidence,
        )
        is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )
    request = transport.requests[-1]
    assert request.body is not None
    assert request.body["executionType"] == "OCO"
    settle_positions = request.body["settlePosition"]
    assert isinstance(settle_positions, list)
    assert sum(int(item["size"]) for item in settle_positions) == 600
    assert store.unknown_halt_latched() is True
    lock.release()


def test_protection_is_blocked_if_entry_remainder_survives_cancel(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, signal, resolve_filled=False)
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(runtime_root)
    transport = _FakeTransport(responses=[{"status": 0}])
    clock = _Clock(wall=NOW + timedelta(seconds=2), monotonic=102.0)
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
        reconciliation_wait=clock.advance,
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    recovery_evidence = _path_partial_reconciliation(path, cycle_ref=cycle_ref)
    assert (
        path.recover_pending_transport_once(
            cycle_ref=cycle_ref,
            reconciliation_evidence=recovery_evidence,
        ).classification
        == "MARKET_PARTIAL_PENDING"
    )
    partial_evidence = _path_partial_reconciliation(path, cycle_ref=cycle_ref)
    cancel = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.CANCEL_ENTRY_REMAINDER,
        side=SignalDecision.BUY,
        requested_size=400,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    assert (
        path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            reconciliation_evidence=partial_evidence,
        )
        is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )
    still_partial = _path_partial_reconciliation(path, cycle_ref=cycle_ref)
    transport.requests.clear()
    with pytest.raises(
        V4GmoCoordinatedPathError,
        match="EXACT_FILL_RECONCILIATION_REQUIRED",
    ):
        path.prepare_exact_protection_plan(
            signal_fingerprint=signal.fingerprint,
            reconciliation_evidence=still_partial,
        )
    assert transport.requests == []
    assert store.unknown_halt_latched() is True
    lock.release()


@pytest.mark.parametrize(
    ("side", "size"),
    ((SignalDecision.SELL, 1_000), (SignalDecision.BUY, 900)),
)
def test_market_side_and_size_must_exact_match_persisted_intent(
    tmp_path: Path, side: SignalDecision, size: int
) -> None:
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    entry_authorization = _record_flat_preflight(
        store,
        signal,
        now_utc=NOW + timedelta(milliseconds=500),
        now_monotonic=100.5,
    )
    with pytest.raises(V4GmoActualCoordinatorError, match="MARKET plan"):
        store._record_market_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            entry_authorization=entry_authorization,
            signal_fingerprint=signal.fingerprint,
            plan=_market_plan(store, signal, side=side, size=size),
            now_utc=NOW + timedelta(seconds=1),
            now_monotonic=101.0,
        )
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 0


def test_stale_entry_preflight_cannot_authorize_market(tmp_path: Path) -> None:
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    entry_authorization = _record_flat_preflight(
        store,
        signal,
        now_utc=NOW + timedelta(milliseconds=500),
        now_monotonic=100.0,
    )
    with pytest.raises(V4GmoActualCoordinatorError, match="MARKET plan"):
        store._record_market_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            entry_authorization=entry_authorization,
            signal_fingerprint=signal.fingerprint,
            plan=_market_plan(store, signal),
            now_utc=NOW + timedelta(seconds=3),
            now_monotonic=103.0,
        )


def test_dead_man_is_rechecked_after_persistence_immediately_before_transport(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(runtime_root)
    transport = _FakeTransport(responses=[{"status": 0}])
    clock = _Clock()
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        after_persist_before_transport=lambda: clock.advance(61),
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    _path_preflight(path, signal, cycle_ref)
    with pytest.raises(V4GmoCoordinatedPathError, match="TRANSPORT_BOUNDARY"):
        path.perform_market_once(
            signal_fingerprint=signal.fingerprint,
            plan=_market_plan(store, signal),
        )
    assert transport.requests == []
    assert store.unknown_halt_latched() is True
    lock.release()


def test_transport_deadlines_use_executor_owned_clocks_only() -> None:
    signatures = (
        inspect.signature(V4GmoCoordinatedActualPath.perform_market_once),
        inspect.signature(V4GmoCoordinatedActualPath.perform_exact_protection_once),
        inspect.signature(V4GmoCoordinatedActualPath.perform_risk_reducing_once),
        inspect.signature(V4GmoCoordinatedActualPath.confirm_exact_protection_once),
    )
    for signature in signatures:
        assert "now_utc" not in signature.parameters
        assert "now_monotonic" not in signature.parameters


def test_persisted_authorization_issuer_is_coordinator_only() -> None:
    backend_root = Path(__file__).resolve().parents[3]
    marker = "_issue_persisted_action_" + "authorization"
    references = {
        path.relative_to(backend_root).as_posix()
        for path in backend_root.rglob("*.py")
        if marker in path.read_text(encoding="utf-8")
    }
    assert references == {
        "app/h11_auto/v4_gmo_actual_coordinator.py",
        "app/h11_auto/v4_gmo_persisted_authorization.py",
    }


def test_actual_transport_fake_client_requires_committed_coordinator_proof(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    entry_authorization = _record_flat_preflight(
        store,
        signal,
        now_utc=NOW + timedelta(milliseconds=900),
        now_monotonic=100.9,
    )
    plan = _market_plan(store, signal)
    attempt = store._record_market_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        entry_authorization=entry_authorization,
        signal_fingerprint=signal.fingerprint,
        plan=plan,
        now_utc=NOW + timedelta(seconds=1),
        now_monotonic=101.0,
    )
    intent = V4GmoCanaryIntent(
        generation_digest=_generation().digest,
        cycle_ref=attempt.cycle_ref,
        side="BUY",
        exact_order_sheet_digest="sha256:" + "c" * 64,
    )
    resume = confirm_v4_major_incident_resume_exact(
        phrase=(
            "I APPROVE H11 V4 MAJOR INCIDENT RESUME FOR THIS REVIEWED GENERATION ONLY"
        ),
        generation_digest=_generation().digest,
    )
    challenge = V4CurrentTurnChallenge.create(intent=intent)
    current = confirm_v4_current_turn_exact(
        typed_phrase=challenge.phrase_for_operator_internal(),
        challenge=challenge,
        intent=intent,
    )
    permit = issue_v4_gmo_actual_activation_permit(
        intent=intent,
        resume_proof=resume,
        current_turn_proof=current,
        repository=tmp_path,
        now_monotonic=101.2,
    )

    @dataclass(frozen=True)
    class FakeCredentials:
        def unseal_for_internal_request_only(
            self,
        ) -> tuple[V4GmoSealedSecret, V4GmoSealedSecret]:
            return V4GmoSealedSecret("fake-key"), V4GmoSealedSecret("fake-secret")

    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"status": 0, "data": {}})

    clock = iter((101.3, 102.5, 103.7, 104.9))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = V4GmoHttpxPrivateTransport(
            activation_permit=permit,
            signed_request_factory=V4GmoSignedRequestFactory(
                credential_pair=FakeCredentials(),
                timestamp_factory=lambda: "1700000000000",
            ),
            client=client,
            monotonic_factory=lambda: next(clock),
            unknown_post_callback=store.engage_unknown_halt,
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
                "clientOrderId": v4_gmo_client_order_id(
                    cycle_ref=attempt.cycle_ref,
                    action=V4GmoAction.MARKET_ENTRY,
                ),
                "executionType": "MARKET",
            },
        )
        final_transport_proof = consume_persisted_action_authorization(
            attempt.authorization,
            plan=plan,
            protection_plan=None,
            reconciliation_digest=None,
            request_binding_digest=v4_gmo_private_request_binding_digest(request),
            now_monotonic=101.1,
        )
        tampered_request = V4GmoPrivateRequest(
            method="POST",
            transport_path="/private/v1/order",
            signing_path="/v1/order",
            params={},
            body={
                "symbol": "USD_JPY",
                "side": "SELL",
                "size": "900",
                "clientOrderId": v4_gmo_client_order_id(
                    cycle_ref=attempt.cycle_ref,
                    action=V4GmoAction.MARKET_ENTRY,
                ),
                "executionType": "MARKET",
            },
        )
        with pytest.raises(V4GmoActualTransportError, match="AUTHORIZATION_REQUIRED"):
            transport.request(
                tampered_request,
                persisted_transport_authorization=final_transport_proof,
            )
        assert calls == 0
        transport.request(
            request,
            persisted_transport_authorization=final_transport_proof,
        )
        assert calls == 1
        with pytest.raises(V4GmoActualTransportError, match="SECOND_ATTEMPT"):
            transport.request(
                request,
                persisted_transport_authorization=final_transport_proof,
            )
        assert calls == 1


def test_actual_runtime_binding_consumes_permit_on_canonical_generation_paths(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    intent = V4GmoCanaryIntent(
        generation_digest=_generation().digest,
        cycle_ref=cycle_ref,
        side="BUY",
        exact_order_sheet_digest="sha256:" + "c" * 64,
    )
    resume = confirm_v4_major_incident_resume_exact(
        phrase=(
            "I APPROVE H11 V4 MAJOR INCIDENT RESUME FOR THIS REVIEWED GENERATION ONLY"
        ),
        generation_digest=_generation().digest,
    )
    challenge = V4CurrentTurnChallenge.create(intent=intent)
    current = confirm_v4_current_turn_exact(
        typed_phrase=challenge.phrase_for_operator_internal(),
        challenge=challenge,
        intent=intent,
    )
    permit = issue_v4_gmo_actual_activation_permit(
        intent=intent,
        resume_proof=resume,
        current_turn_proof=current,
        repository=tmp_path,
        now_monotonic=50.0,
    )

    @dataclass(frozen=True)
    class FakeCredentials:
        def unseal_for_internal_request_only(
            self,
        ) -> tuple[V4GmoSealedSecret, V4GmoSealedSecret]:
            return V4GmoSealedSecret("fake-key"), V4GmoSealedSecret("fake-secret")

    with httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(500))
    ) as client:
        binding = bind_v4_gmo_actual_runtime(
            repository=tmp_path,
            generation=_generation(),
            activation_permit=permit,
            credential_pair=FakeCredentials(),
            client=client,
            monotonic_factory=lambda: 50.1,
        )
        assert binding.process_lock.held is True
        assert (runtime_root / "activation-runtime-bound.json").is_file()
        binding.close()
        assert binding.process_lock.held is False


def test_risk_reducing_action_refuses_state_mismatch_before_transport(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, signal)
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(runtime_root)
    transport = _FakeTransport(responses=[{"status": 0}])
    clock = _Clock(wall=NOW + timedelta(seconds=2), monotonic=102.0)
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
    )
    cancel = build_v4_action_plan(
        cycle_ref=store.cycle_ref_for_signal_internal(signal.fingerprint),
        action=V4GmoAction.CANCEL_ENTRY_REMAINDER,
        side=SignalDecision.BUY,
        requested_size=400,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    transport.responses[:0] = [
        {"status": 0, "data": {"list": []}},
        {"status": 0, "data": {"list": []}},
        {"status": 0, "data": {"list": []}},
    ]
    path.reconciliation_wait = clock.advance
    flat_evidence = path.reconcile_once_fixed(
        cycle_ref=cancel.cycle_ref,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    transport.requests.clear()
    with pytest.raises(V4GmoActualCoordinatorError, match="mismatch"):
        path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            reconciliation_evidence=flat_evidence,
        )
    assert transport.requests == []
    lock.release()


def test_transport_reverifies_committed_attempt_and_refuses_db_tamper(
    tmp_path: Path,
) -> None:
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    plan = _market_plan(store, signal)
    attempt = _record_market(store, signal)
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE attempts SET plan_digest=? WHERE action='MARKET_ENTRY'",
            ("sha256:" + "0" * 64,),
        )
    transport = _FakeTransport(responses=[{"status": 0}])
    with pytest.raises(V4PersistedAuthorizationError, match="REVERIFY_FAILED"):
        V4GmoActualAdapter(transport=transport).perform_once(
            plan=plan,
            persisted_authorization=attempt.authorization,
            now_monotonic=101.1,
        )
    assert transport.requests == []


@pytest.mark.parametrize("mutation", ("delete", "change"))
def test_transport_reverifies_exact_pending_marker(
    tmp_path: Path,
    mutation: str,
) -> None:
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    plan = _market_plan(store, signal)
    authorization = _record_flat_preflight(
        store,
        signal,
        now_utc=NOW + timedelta(milliseconds=900),
        now_monotonic=100.9,
    )
    attempt = store._record_market_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        entry_authorization=authorization,
        signal_fingerprint=signal.fingerprint,
        plan=plan,
        now_utc=NOW + timedelta(seconds=1),
        now_monotonic=101.0,
    )
    with sqlite3.connect(store.path) as connection:
        if mutation == "delete":
            connection.execute(
                "DELETE FROM metadata WHERE key='pending_transport_attempt'"
            )
        else:
            connection.execute(
                "UPDATE metadata SET value=? WHERE key='pending_transport_attempt'",
                ('{"action":"MARKET_ENTRY","cycle_ref":"tampered"}',),
            )
    transport = _FakeTransport(responses=[{"status": 0}])
    with pytest.raises(V4PersistedAuthorizationError, match="REVERIFY_FAILED"):
        V4GmoActualAdapter(transport=transport).perform_once(
            plan=plan,
            persisted_authorization=attempt.authorization,
            now_monotonic=101.1,
        )
    assert transport.requests == []


def test_entry_issuer_is_confined_to_coordinated_path() -> None:
    backend_root = Path(__file__).resolve().parents[3]
    markers = (
        "_ENTRY_PREFLIGHT_ISSUER_" + "TOKEN",
        "_record_entry_preflight_from_" + "coordinated_path",
        "_record_market_attempt_from_" + "coordinated_path",
        "_resolve_pending_transport_from_" + "coordinated_path",
        "_persist_exact_protection_plan_from_" + "coordinated_path",
        "_record_exact_protection_attempt_from_" + "coordinated_path",
        "_record_risk_reducing_attempt_from_" + "coordinated_path",
        "_record_transport_outcome_from_" + "coordinated_path",
    )
    allowed = {
        "app/h11_auto/v4_gmo_actual_coordinator.py",
        "app/services/h11_v4_gmo_coordinated_actual_path.py",
        "app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py",
    }
    for marker in markers:
        references = {
            path.relative_to(backend_root).as_posix()
            for path in backend_root.rglob("*.py")
            if marker in path.read_text(encoding="utf-8")
        }
        assert references <= allowed
    assert not hasattr(V4GmoActualCoordinatorStore, "record_entry_preflight")
    assert not hasattr(
        V4GmoActualCoordinatorStore,
        "record_market_attempt_before_transport",
    )
    assert not hasattr(V4GmoActualCoordinatorStore, "persist_exact_protection_plan")
    assert not hasattr(
        V4GmoActualCoordinatorStore,
        "record_exact_protection_attempt_before_transport",
    )
    assert not hasattr(
        V4GmoActualCoordinatorStore,
        "record_risk_reducing_attempt_before_transport",
    )


def test_risk_reducing_action_requires_authoritative_matching_state(
    tmp_path: Path,
) -> None:
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, signal)
    cancel = build_v4_action_plan(
        cycle_ref=store.cycle_ref_for_signal_internal(signal.fingerprint),
        action=V4GmoAction.CANCEL_ENTRY_REMAINDER,
        side=SignalDecision.BUY,
        requested_size=400,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    with pytest.raises(V4GmoActualCoordinatorError, match="mismatch"):
        store._record_risk_reducing_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            snapshot=V4GmoBrokerSnapshot.flat(),
            position_bundle_total=None,
            authoritative_reconciliation_digest=RECONCILIATION_DIGEST,
            now_utc=NOW + timedelta(seconds=2),
        )
    with sqlite3.connect(store.path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM attempts WHERE action='CANCEL_ENTRY_REMAINDER'"
            ).fetchone()[0]
            == 0
        )


def test_flat_result_updates_persistent_risk_exactly_once(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, signal)
    store._persist_exact_protection_plan_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        reconciled_average_fill_price=Decimal("150.000"),
        reconciled_filled_size=1_000,
        now_utc=NOW + timedelta(seconds=2),
        now_monotonic=102.0,
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    entry_id = v4_gmo_client_order_id(
        cycle_ref=cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
    )
    protection_id = v4_gmo_client_order_id(
        cycle_ref=cycle_ref,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
    )

    def flat_close_responses() -> list[dict[str, Any]]:
        return [
            {
                "status": 0,
                "data": {
                    "list": [
                        {
                            "clientOrderId": entry_id,
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
                            "clientOrderId": protection_id,
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

    transport = _FakeTransport(responses=flat_close_responses())
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(runtime_root)
    clock = _Clock(wall=NOW + timedelta(seconds=3), monotonic=103.0)
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
        reconciliation_wait=clock.advance,
    )
    evidence = path.reconcile_once_fixed(
        cycle_ref=cycle_ref,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    assert (
        path.record_flat_closed_result_once(
            signal_fingerprint=signal.fingerprint,
            reconciliation_evidence=evidence,
        )
        is True
    )

    transport.responses.extend(flat_close_responses())
    second = path.reconcile_once_fixed(
        cycle_ref=cycle_ref,
        side=SignalDecision.BUY,
        requested_size=1_000,
    )
    assert (
        path.record_flat_closed_result_once(
            signal_fingerprint=signal.fingerprint,
            reconciliation_evidence=second,
        )
        is False
    )
    state = risk_store.load()
    assert state.daily_loss_jpy_internal == 1_235
    assert state.monthly_loss_jpy_internal == 1_235
    assert state.consecutive_losses == 1
    assert state.closed_result_cycle_refs == [cycle_ref]
    with sqlite3.connect(store.path) as connection:
        closed_metrics = connection.execute(
            "SELECT realized_pnl_jpy,net_pips,trade_won FROM cycles"
        ).fetchone()
    assert closed_metrics == (-1235, "-123.5", 0)
    lock.release()


def test_amount_only_flat_result_is_unknown_and_latches_halt(
    tmp_path: Path,
) -> None:
    signal = _signal()
    runtime_root = _runtime_root(tmp_path)
    store = V4GmoActualCoordinatorStore(runtime_root / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, signal)
    store._persist_exact_protection_plan_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        reconciled_average_fill_price=Decimal("150.000"),
        reconciled_filled_size=1_000,
        now_utc=NOW + timedelta(seconds=2),
        now_monotonic=102.0,
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    entry_id = v4_gmo_client_order_id(
        cycle_ref=cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
    )
    protection_id = v4_gmo_client_order_id(
        cycle_ref=cycle_ref,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
    )
    transport = _FakeTransport(
        responses=[
            {
                "status": 0,
                "data": {
                    "list": [
                        {
                            "clientOrderId": entry_id,
                            "positionId": 1001,
                            "symbol": "USD_JPY",
                            "side": "BUY",
                            "settleType": "OPEN",
                            "size": "1000",
                            "amount": "0",
                        },
                        {
                            "clientOrderId": protection_id,
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
    )
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(runtime_root)
    clock = _Clock(wall=NOW + timedelta(seconds=3), monotonic=103.0)
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
        reconciliation_wait=clock.advance,
    )
    with pytest.raises(
        V4GmoCoordinatedPathError,
        match="RECONCILIATION_UNKNOWN",
    ):
        path.reconcile_once_fixed(
            cycle_ref=cycle_ref,
            side=SignalDecision.BUY,
            requested_size=1_000,
        )
    assert store.unknown_halt_latched() is True
    assert risk_store.load().daily_loss_jpy_internal == 0
    lock.release()


def test_time_exit_requires_23h_and_exact_protection_cancel_first(
    tmp_path: Path,
) -> None:
    signal = _signal()
    store = V4GmoActualCoordinatorStore(tmp_path / "coordinator.sqlite3")
    store.prepare_entry_intent(
        generation=_generation(),
        signal=signal,
        policy=_policy(),
        frozen_atr_24=Decimal("0.20"),
        now_utc=NOW,
    )
    _record_market(store, signal)
    protection = store._persist_exact_protection_plan_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        reconciled_average_fill_price=Decimal("150.000"),
        reconciled_filled_size=1_000,
        now_utc=NOW + timedelta(seconds=2),
        now_monotonic=102.0,
    )
    cycle_ref = store.cycle_ref_for_signal_internal(signal.fingerprint)
    protection_action = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    store._record_exact_protection_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        plan=protection_action,
        protection_plan=protection,
        reconciliation_digest=RECONCILIATION_DIGEST,
        now_utc=NOW + timedelta(seconds=2),
        now_monotonic=102.0,
    )
    store._record_transport_outcome_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        cycle_ref=cycle_ref,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
        outcome_label="ACCEPTED_SANITIZED",
    )
    exact_snapshot = V4GmoBrokerSnapshot(
        fresh=True,
        result_known=True,
        position_count=1,
        position_side=SignalDecision.BUY,
        filled_size=1_000,
        pending_entry_size=0,
        protection_size=1_000,
        entry_status=V4GmoEntryStatus.FILLED,
        protection_status=V4GmoProtectionStatus.EXACT_MATCH,
    )
    store._resolve_pending_transport_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        cycle_ref=cycle_ref,
        snapshot=exact_snapshot,
        position_bundle_total=1_000,
        authoritative_reconciliation_digest=RECONCILIATION_DIGEST,
        now_utc=NOW + timedelta(seconds=3),
    )
    cancel = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    with pytest.raises(V4GmoActualCoordinatorError, match="state mismatch"):
        store._record_risk_reducing_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            snapshot=exact_snapshot,
            position_bundle_total=1_000,
            authoritative_reconciliation_digest=RECONCILIATION_DIGEST,
            now_utc=NOW + timedelta(seconds=82_800),
        )
    attempt = store._record_risk_reducing_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        plan=cancel,
        snapshot=exact_snapshot,
        position_bundle_total=1_000,
        authoritative_reconciliation_digest=RECONCILIATION_DIGEST,
        now_utc=NOW + timedelta(seconds=82_801),
    )
    assert attempt.action == V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT.value


def test_friday_time_exit_uses_saturday_03_45jst_sequence_start(
    tmp_path: Path,
) -> None:
    friday_entry = datetime(2026, 7, 17, 0, 0, tzinfo=UTC)  # Fri 09 JST
    signal, _, store, cycle_ref = _prepare_exact_protected_store(
        tmp_path,
        entry_time_utc=friday_entry,
    )
    cancel = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    exact_snapshot = V4GmoBrokerSnapshot(
        fresh=True,
        result_known=True,
        position_count=1,
        position_side=SignalDecision.BUY,
        filled_size=1_000,
        pending_entry_size=0,
        protection_size=1_000,
        entry_status=V4GmoEntryStatus.FILLED,
        protection_status=V4GmoProtectionStatus.EXACT_MATCH,
    )
    sequence_start = datetime(2026, 7, 17, 18, 45, tzinfo=UTC)  # Sat 03:45 JST
    with pytest.raises(V4GmoActualCoordinatorError, match="state mismatch"):
        store._record_risk_reducing_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            snapshot=exact_snapshot,
            position_bundle_total=1_000,
            authoritative_reconciliation_digest=RECONCILIATION_DIGEST,
            now_utc=sequence_start - timedelta(microseconds=1),
        )
    attempt = store._record_risk_reducing_attempt_from_coordinated_path(
        issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
        signal_fingerprint=signal.fingerprint,
        plan=cancel,
        snapshot=exact_snapshot,
        position_bundle_total=1_000,
        authoritative_reconciliation_digest=RECONCILIATION_DIGEST,
        now_utc=sequence_start,
    )
    assert attempt.action == V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT.value


def test_full_time_exit_sequence_is_fixed_and_each_write_is_once_only(
    tmp_path: Path,
) -> None:
    signal, runtime_root, store, cycle_ref = _prepare_exact_protected_store(tmp_path)

    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(
        runtime_root,
        heartbeat_at=NOW + timedelta(seconds=82_801),
    )
    transport = _FakeTransport(responses=[{"status": 0}, {"status": 0}])
    clock = _Clock(
        wall=NOW + timedelta(seconds=82_801),
        monotonic=82_901.0,
    )
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
        reconciliation_wait=clock.advance,
    )
    cancel = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    protected = _path_protected_reconciliation(
        path,
        cycle_ref=cycle_ref,
        filled_size=1_000,
    )
    assert (
        path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            reconciliation_evidence=protected,
            market_status_evidence=_public_status_evidence(
                generation_digest=_generation().digest,
                status="OPEN",
                monotonic=clock.monotonic,
            ),
        )
        is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )
    assert [request.transport_path for request in transport.requests] == [
        "/private/v1/cancelOrders"
    ]

    after_cancel = _path_filled_reconciliation(
        path,
        cycle_ref=cycle_ref,
        filled_size=1_000,
    )
    assert (
        path.recover_pending_transport_once(
            cycle_ref=cycle_ref,
            reconciliation_evidence=after_cancel,
        ).classification
        == "FILLED_UNPROTECTED"
    )
    time_exit = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    unprotected = _path_filled_reconciliation(
        path,
        cycle_ref=cycle_ref,
        filled_size=1_000,
    )
    assert (
        path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=time_exit,
            reconciliation_evidence=unprotected,
            market_status_evidence=_public_status_evidence(
                generation_digest=_generation().digest,
                status="OPEN",
                monotonic=clock.monotonic,
            ),
        )
        is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )
    assert [request.transport_path for request in transport.requests] == [
        "/private/v1/closeOrder"
    ]
    assert transport.requests[0].body is not None
    assert transport.requests[0].body["executionType"] == "MARKET"
    assert transport.requests[0].body["settlePosition"] == [
        {"positionId": 1001, "size": "1000"}
    ]

    duplicate_evidence = _path_filled_reconciliation(
        path,
        cycle_ref=cycle_ref,
        filled_size=1_000,
    )
    with pytest.raises(V4GmoActualCoordinatorError, match="second v4"):
        path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=time_exit,
            reconciliation_evidence=duplicate_evidence,
            market_status_evidence=_public_status_evidence(
                generation_digest=_generation().digest,
                status="OPEN",
                monotonic=clock.monotonic,
            ),
        )
    assert transport.requests == []
    lock.release()


def test_foreground_driver_reads_real_coordinator_snapshot_and_dispatches(
    tmp_path: Path,
) -> None:
    signal, runtime_root, store, _cycle_ref = _prepare_exact_protected_store(tmp_path)
    store.confirm_exact_protection_within_deadline(
        signal_fingerprint=signal.fingerprint,
        confirmed_protection_size=1_000,
        now_utc=NOW + timedelta(seconds=3),
        now_monotonic=103.0,
    )
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(
        runtime_root,
        heartbeat_at=NOW + timedelta(seconds=82_801),
    )
    clock = _Clock(
        wall=NOW + timedelta(seconds=82_801),
        monotonic=82_901.0,
    )
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=_FakeTransport(responses=[])),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
        reconciliation_wait=clock.advance,
    )
    (runtime_root / "exit-sequence-dispatch-required.json").write_text(
        "{}\n", encoding="utf-8"
    )
    dispatcher = MagicMock()
    dispatcher.path = path
    dispatcher.dispatch_once.return_value = V4GmoExitDispatchResult(
        claimed=True,
        protection_cancel_accepted=True,
        position_close_accepted=True,
        flat_reconciled=True,
        broker_post_attempt_count=2,
    )
    driver = V4GmoActualRuntimeDriver(
        coordinated_path=path,
        dispatcher=dispatcher,
    )

    result = driver.run_until_flat(
        public_reader_factory=MagicMock(side_effect=[MagicMock(), MagicMock()]),
        wall_clock=clock.wall_now,
        wait=lambda _seconds: None,
    )

    assert result.flat_reconciled is True
    dispatcher.dispatch_once.assert_called_once()
    lock.release()


@pytest.mark.parametrize(
    ("status", "boundary_delay_seconds"),
    (("CLOSE", 0.0), ("OPEN", 2.1)),
)
def test_time_exit_non_open_or_stale_at_transport_retains_oco_and_halts(
    tmp_path: Path,
    status: str,
    boundary_delay_seconds: float,
) -> None:
    signal, runtime_root, store, cycle_ref = _prepare_exact_protected_store(tmp_path)
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(
        runtime_root,
        heartbeat_at=NOW + timedelta(seconds=82_801),
    )
    transport = _FakeTransport(responses=[])
    clock = _Clock(
        wall=NOW + timedelta(seconds=82_801),
        monotonic=82_901.0,
    )
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
        reconciliation_wait=clock.advance,
        after_persist_before_transport=lambda: clock.advance(boundary_delay_seconds),
    )
    protected = _path_protected_reconciliation(
        path,
        cycle_ref=cycle_ref,
        filled_size=1_000,
    )
    cancel = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    with pytest.raises(
        V4GmoActualAdapterError,
        match="PUBLIC_MARKET_OPEN_REQUIRED_AT_TRANSPORT_BOUNDARY",
    ):
        path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            reconciliation_evidence=protected,
            market_status_evidence=_public_status_evidence(
                generation_digest=_generation().digest,
                status=status,
                monotonic=clock.monotonic,
            ),
        )
    assert store.unknown_halt_latched() is True
    assert transport.requests == []
    lock.release()


@pytest.mark.parametrize(
    ("status", "boundary_delay_seconds"),
    (("CLOSE", 0.0), ("UNKNOWN", 0.0), ("OPEN", 2.1)),
)
def test_position_time_exit_requires_separate_fresh_open_at_transport_boundary(
    tmp_path: Path,
    status: str,
    boundary_delay_seconds: float,
) -> None:
    signal, runtime_root, store, cycle_ref = _prepare_exact_protected_store(tmp_path)
    lock = H11AutoProcessLock(runtime_root / "process.lock")
    assert lock.acquire() is True
    risk_store, risk_policy, dead_man = _runtime_safety(
        runtime_root,
        heartbeat_at=NOW + timedelta(seconds=82_801),
    )
    transport = _FakeTransport(responses=[{"status": 0}])
    clock = _Clock(
        wall=NOW + timedelta(seconds=82_801),
        monotonic=82_901.0,
    )
    path = V4GmoCoordinatedActualPath(
        repository=tmp_path,
        store=store,
        adapter=V4GmoActualAdapter(transport=transport),
        process_lock=lock,
        generation=_generation(),
        risk_store=risk_store,
        risk_policy=risk_policy,
        dead_man_store=dead_man,
        wall_clock=clock.wall_now,
        monotonic_clock=clock.monotonic_now,
        reconciliation_wait=clock.advance,
    )
    cancel = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    assert (
        path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=cancel,
            reconciliation_evidence=_path_protected_reconciliation(
                path,
                cycle_ref=cycle_ref,
                filled_size=1_000,
            ),
            market_status_evidence=_public_status_evidence(
                generation_digest=_generation().digest,
                status="OPEN",
                monotonic=clock.monotonic,
            ),
        )
        is V4GmoPrivateOutcome.ACCEPTED_SANITIZED
    )
    assert (
        path.recover_pending_transport_once(
            cycle_ref=cycle_ref,
            reconciliation_evidence=_path_filled_reconciliation(
                path,
                cycle_ref=cycle_ref,
                filled_size=1_000,
            ),
        ).classification
        == "FILLED_UNPROTECTED"
    )
    transport.requests.clear()
    path.after_persist_before_transport = lambda: clock.advance(boundary_delay_seconds)
    time_exit = build_v4_action_plan(
        cycle_ref=cycle_ref,
        action=V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
        side=SignalDecision.BUY,
        requested_size=1_000,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    with pytest.raises(
        V4GmoActualAdapterError,
        match="PUBLIC_MARKET_OPEN_REQUIRED_AT_TRANSPORT_BOUNDARY",
    ):
        path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=time_exit,
            reconciliation_evidence=_path_filled_reconciliation(
                path,
                cycle_ref=cycle_ref,
                filled_size=1_000,
            ),
            market_status_evidence=_public_status_evidence(
                generation_digest=_generation().digest,
                status=status,
                monotonic=clock.monotonic,
            ),
        )
    assert store.unknown_halt_latched() is True
    assert transport.requests == []
    lock.release()
