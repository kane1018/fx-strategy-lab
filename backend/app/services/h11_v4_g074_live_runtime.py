"""G074 concrete resident ports, dormant until durable release activation.

The module supplies the missing production wiring without changing the hard
guard. Tests inject fake runners and clients. Importing this module performs no
Keychain read, network request, ARM mutation, notification, or broker action.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.h11_auto.contracts import SignalDecision
from app.h11_auto.runtime_safety import DeadManStore, PhaseBRiskStore
from app.h11_auto.v4_actual_preparation_guard import require_clean_main, reviewed_files_digest
from app.h11_auto.v4_gmo_actual_coordinator import (
    V4GmoActualCoordinatorError,
    V4GmoActualCoordinatorStore,
)
from app.h11_auto.v4_gmo_canary_activation import V4CurrentTurnChallenge, V4GmoCanaryIntent
from app.h11_auto.v4_gmo_contracts import V4GmoProtectionStatus
from app.h11_auto.v4_gmo_generation import (
    V4GmoFrozenGeneration,
    load_v4_gmo_frozen_generation,
    v4_gmo_dead_man_policy,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services import h11_v4_gmo_g013_canary as g013
from app.services.h11_v4_g074_runtime import (
    G074Action,
    G074ActionOutcome,
    G074ActionScope,
    G074ProcessLock,
    G074ReconciliationEvidence,
    G074SanitizedSnapshot,
    G074StrategyObservation,
    build_g074_recovery_scope,
    load_g074_reconciliation,
    load_g074_release_capability_digest,
)
from app.services.h11_v4_gmo_actual_adapter import (
    V4GmoActualAdapter,
)
from app.services.h11_v4_gmo_actual_transport import (
    GMO_V4_PRIVATE_BASE_URL,
    GMO_V4_PRIVATE_HTTP_TIMEOUT_SECONDS,
    V4GmoHttpxPrivateTransport,
    V4GmoKeychainCredentialPair,
    V4GmoPrivateEnvelope,
    V4GmoPrivateRequest,
    V4GmoSignedRequestFactory,
)
from app.services.h11_v4_gmo_coordinated_actual_path import V4GmoCoordinatedActualPath
from app.services.h11_v4_gmo_exit_dispatcher import V4GmoExitDispatcher
from app.services.h11_v4_gmo_formal_canary_source import refresh_g013_formal_canary_input
from app.services.h11_v4_gmo_post_canary_reconciliation import require_g013_entry_enabled
from app.services.h11_v4_gmo_public_market_status import V4GmoPublicMarketStatusReader
from app.services.h11_v4_gmo_public_preflight import (
    G013_MAXIMUM_ENTRY_SPREAD_PIPS,
    V4GmoG013PublicOperation,
    V4GmoG013PublicOperationLedger,
    g013_public_cycle_key,
    read_g013_final_quote_once,
)


class G074LiveRuntimeError(RuntimeError):
    """Safe-label-only concrete runtime failure."""


class G074ReadOnlyActualTransport:
    """Signed Private GET-only transport; POST is structurally refused."""

    def __init__(
        self,
        *,
        credential_pair: V4GmoKeychainCredentialPair,
        client: httpx.Client,
    ) -> None:
        self._signer = V4GmoSignedRequestFactory(credential_pair=credential_pair)
        self._signer.prime_for_protection_window()
        self._client = client
        self.request_count = 0

    def request(self, request: V4GmoPrivateRequest, *, persisted_transport_authorization=None):
        if (
            not isinstance(request, V4GmoPrivateRequest)
            or request.method != "GET"
            or persisted_transport_authorization is not None
            or self.request_count >= 3
        ):
            raise G074LiveRuntimeError("G074_READ_ONLY_TRANSPORT_BOUNDARY_VIOLATION")
        self.request_count += 1
        signed = self._signer.build(request)
        try:
            response = self._client.request(
                "GET",
                GMO_V4_PRIVATE_BASE_URL + request.transport_path,
                params=dict(request.params),
                headers=dict(signed.headers),
                timeout=GMO_V4_PRIVATE_HTTP_TIMEOUT_SECONDS,
            )
            payload = response.json()
        except Exception as error:
            raise G074LiveRuntimeError("G074_PRIVATE_GET_RESULT_UNKNOWN") from error
        if not isinstance(payload, Mapping):
            raise G074LiveRuntimeError("G074_PRIVATE_GET_RESULT_UNKNOWN")
        return V4GmoPrivateEnvelope.from_injected_payload(payload)

    def __bool__(self) -> bool:
        return False

    def close(self) -> None:
        self._signer.clear_protection_window_credentials()


@dataclass(repr=False)
class G074ReleasePreparationEvidence:
    """Per-signal release proof replacing daily preparation for G074 only."""

    state_root: Path
    generation_digest: str
    reviewed_files_digest: str
    release_capability_digest: str
    cycle_ref: str
    _consumed: bool = field(default=False, init=False, repr=False)

    def refresh_for_generation(
        self,
        *,
        generation_digest: str,
        reviewed_files_digest: str,
        now_utc: datetime,
    ) -> G074ReleasePreparationEvidence:
        if now_utc.tzinfo is None:
            raise G074LiveRuntimeError("G074_RELEASE_EVIDENCE_CLOCK_INVALID")
        current = load_g074_release_capability_digest(
            state_root=self.state_root,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
        )
        if (
            generation_digest != self.generation_digest
            or reviewed_files_digest != self.reviewed_files_digest
            or current != self.release_capability_digest
            or self._consumed
        ):
            raise G074LiveRuntimeError("G074_RELEASE_EVIDENCE_INVALID")
        return self

    def consume_for_generation(self, generation_digest: str) -> None:
        if generation_digest != self.generation_digest or self._consumed:
            raise G074LiveRuntimeError("G074_RELEASE_EVIDENCE_ALREADY_CONSUMED")
        marker = self.state_root / f"g074-release-evidence-{self.cycle_ref}.consumed.json"
        if marker.is_symlink():
            raise G074LiveRuntimeError("G074_RELEASE_EVIDENCE_SYMLINK_REFUSED")
        try:
            descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise G074LiveRuntimeError("G074_RELEASE_EVIDENCE_ALREADY_CONSUMED") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "generation_digest": self.generation_digest,
                    "reviewed_files_digest": self.reviewed_files_digest,
                    "release_capability_digest": self.release_capability_digest,
                    "cycle_ref": self.cycle_ref,
                    "status": "CONSUMED",
                },
                stream,
                sort_keys=True,
            )
        self._consumed = True

    def __repr__(self) -> str:
        return "G074ReleasePreparationEvidence(<generation-cycle-bound>)"

    def __bool__(self) -> bool:
        return False


def prepare_g074_unattended_session(
    *, repository: Path, state_root: Path, now_utc: datetime
) -> g013.V4GmoG013PreparedSession:
    """Prepare a current formal session using durable release, not daily approval."""

    repository = repository.resolve()
    require_clean_main(repository=repository)
    implementation_digest = reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=implementation_digest
    )
    if generation.generation_label != "H11_AUTO_30M_20260802_G074":
        raise G074LiveRuntimeError("G074_CANONICAL_GENERATION_REQUIRED")
    release_digest = load_g074_release_capability_digest(
        state_root=state_root,
        generation_digest=generation.digest,
        reviewed_files_digest=implementation_digest,
    )
    require_g013_entry_enabled(
        repository=repository,
        reviewed_files_digest=implementation_digest,
        generation_digest=generation.digest,
        generation_entry_disabled=generation.entry_disabled,
        reconciliation_contract_digest=generation.reconciliation_contract_digest,
    )
    policy = g013._execution_policy(generation)  # noqa: SLF001
    if not policy.entry_time_allowed(now_utc=now_utc):
        raise G074LiveRuntimeError("G074_ENTRY_TIME_BLOCKED")
    public_ledger = V4GmoG013PublicOperationLedger(
        state_root=state_root, generation_digest=generation.digest
    )
    formal_input = refresh_g013_formal_canary_input(
        operation_ledger=public_ledger, now_utc=now_utc
    )
    if not policy.accepts(formal_input.signal):
        raise G074LiveRuntimeError("G074_FORMAL_SIGNAL_NOT_ACTIONABLE")
    reference_quote = read_g013_final_quote_once(
        operation_ledger=public_ledger,
        operation=V4GmoG013PublicOperation.REFERENCE_QUOTE,
        cycle_key=g013_public_cycle_key(now_utc),
    )
    store = V4GmoActualCoordinatorStore(state_root / "coordinator.sqlite3")
    risk = store.evaluate_entry_intent(
        generation=generation,
        signal=formal_input.signal,
        policy=policy,
        frozen_atr_24=formal_input.frozen_atr_24,
        now_utc=now_utc,
    )
    g013._require_fresh_monitor_heartbeat(  # noqa: SLF001
        state_root=state_root, require_cycle_present=False
    )
    cycle_ref = store.cycle_ref_for_signal_pure(
        generation=generation, signal_fingerprint=formal_input.signal.fingerprint
    )
    sheet = g013.V4GmoG013OrderSheet(
        generation_label=generation.generation_label,
        strategy_version=generation.strategy_version,
        horizon=generation.selected_horizon,
        symbol=generation.symbol,
        side=formal_input.signal.decision.value,
        size=generation.quantity_units,
        execution_type="MARKET",
        probability_up=format(formal_input.signal.probability_up, "f"),
        formal_origin_utc=formal_input.signal.observed_at_utc.isoformat(),
        formal_valid_until_utc=formal_input.signal.valid_until_utc.isoformat(),
        frozen_atr_24=format(formal_input.frozen_atr_24.normalize(), "f"),
        formal_input_provenance_digest=formal_input.input_provenance_digest,
        atr_timeframe=formal_input.atr_timeframe,
        stop_distance_rule="1.50 * frozen ATR(24) from actual average fill",
        take_profit_rule="1.50R from actual average fill",
        maximum_spread_pips=format(G013_MAXIMUM_ENTRY_SPREAD_PIPS.normalize(), "f"),
        reference_bid=format(reference_quote.bid.normalize(), "f"),
        reference_ask=format(reference_quote.ask.normalize(), "f"),
        reference_quote_observed_at_utc=reference_quote.observed_at_utc.isoformat(),
        maximum_reference_deviation_pips=generation.adverse_slippage_allowance_pips,
        planned_loss_bound_jpy=risk.planned_loss_bound_jpy,
        maximum_loss_per_trade_jpy=generation.per_trade_loss_bound_jpy,
        maximum_unprotected_seconds=generation.maximum_unprotected_seconds,
    )
    intent = V4GmoCanaryIntent(
        generation_digest=generation.digest,
        cycle_ref=cycle_ref,
        side=formal_input.signal.decision.value,
        exact_order_sheet_digest=sheet.digest,
    )
    release = G074ReleasePreparationEvidence(
        state_root=state_root,
        generation_digest=generation.digest,
        reviewed_files_digest=implementation_digest,
        release_capability_digest=release_digest,
        cycle_ref=cycle_ref,
    )
    return g013.V4GmoG013PreparedSession(
        repository=repository,
        generation=generation,
        formal_input=formal_input,
        store=store,
        risk=risk,
        intent=intent,
        challenge=V4CurrentTurnChallenge.create(intent=intent),
        preparation_evidence=release,  # type: ignore[arg-type]
        public_operation_ledger=public_ledger,
        reference_quote=reference_quote,
        order_sheet=sheet,
    )


@dataclass
class G074PrivateReconciler:
    repository: Path
    generation: V4GmoFrozenGeneration
    client_factory: Callable[[], httpx.Client] = lambda: httpx.Client(timeout=5.0)
    credential_factory: Callable[[], V4GmoKeychainCredentialPair] = (
        V4GmoKeychainCredentialPair
    )

    def reconcile_once(self, *, cycle_id: str, now_utc: datetime) -> G074SanitizedSnapshot:
        del cycle_id
        state_root = v4_gmo_runtime_state_root(
            repository=self.repository, generation_digest=self.generation.digest
        )
        store = V4GmoActualCoordinatorStore(state_root / "coordinator.sqlite3")
        try:
            fingerprint = store.load_single_signal_fingerprint_internal()
            cycle_ref = store.cycle_ref_for_signal_internal(fingerprint)
            side = store.side_for_signal_internal(fingerprint)
        except V4GmoActualCoordinatorError:
            cycle_ref = self.generation.digest.removeprefix("sha256:")
            side = SignalDecision.BUY
        client = self.client_factory()
        transport = G074ReadOnlyActualTransport(
            credential_pair=self.credential_factory(), client=client
        )
        try:
            result = V4GmoActualAdapter(transport=transport).reconcile(
                cycle_ref=cycle_ref,
                side=side,
                requested_size=self.generation.quantity_units,
                monotonic_factory=time.monotonic,
                wait=time.sleep,
            )
        finally:
            transport.close()
            client.close()
        snapshot = result.snapshot
        owned = (
            result.unowned_position_count == 0
            and result.position_bundle is not None
            and snapshot.position_count == 1
        )
        quantity_matches = (
            owned
            and result.position_bundle is not None
            and result.position_bundle.total_size == self.generation.quantity_units
            and snapshot.filled_size == self.generation.quantity_units
        )
        protected = (
            quantity_matches
            and result.account_active_order_count == 2
            and snapshot.protection_size == self.generation.quantity_units
            and snapshot.protection_status is V4GmoProtectionStatus.EXACT_MATCH
        )
        return G074SanitizedSnapshot(
            latest_execution_count=0,
            open_position_count=result.account_position_count,
            active_order_count=result.account_active_order_count,
            position_side=(snapshot.position_side.value if snapshot.position_side else None),
            ownership_exact=owned,
            quantity_matches=quantity_matches,
            protection_confirmed=protected,
            broker_get_count=transport.request_count,
            private_api_read_count=transport.request_count,
            credential_read_count=1,
        )


@dataclass
class G074LiveActionPort:
    repository: Path
    generation: V4GmoFrozenGeneration
    process_lock: G074ProcessLock
    current_session: g013.V4GmoG013PreparedSession | None = None
    entry_result: Any | None = None
    exit_result: Any | None = None
    entry_runner: Callable[[g013.V4GmoG013PreparedSession], Any] | None = None
    exit_runner: Callable[[G074ActionScope], Any] | None = None

    def observe(self, *, now_utc: datetime) -> G074StrategyObservation:
        state_root = self.process_lock.state_root
        session = prepare_g074_unattended_session(
            repository=self.repository, state_root=state_root, now_utc=now_utc
        )
        self.current_session = session
        return G074StrategyObservation(
            strategy_artifact_digest=session.generation.frozen_design_digest or "",
            strategy_version=session.generation.strategy_version,
            symbol=session.generation.symbol,
            quantity=session.generation.quantity_units,
            side=session.formal_input.signal.decision.value,
            horizon=session.generation.selected_horizon,
            generation_digest=session.generation.digest,
            reviewed_files_digest=session.generation.implementation_digest,
            signal_actionable=True,
            risk_clear=True,
            market_open=True,
            spread_clear=True,
            quote_fresh=True,
            signal_fresh=True,
            limits_clear=True,
            position_flat=True,
            active_orders_zero=True,
        )

    def attempt_once(self, scope: G074ActionScope) -> G074ActionOutcome:
        if scope.action is G074Action.ENTRY:
            if self.current_session is None:
                raise G074LiveRuntimeError("G074_ENTRY_SESSION_REQUIRED")
            runner = self.entry_runner or self._run_entry_actual
            self.entry_result = runner(self.current_session)
            if not getattr(self.entry_result, "exact_protection_confirmed", False):
                raise G074LiveRuntimeError("G074_ENTRY_PROTECTION_NOT_CONFIRMED")
            return G074ActionOutcome.ACCEPTED
        if scope.action is G074Action.PROTECTION:
            if not getattr(self.entry_result, "exact_protection_confirmed", False):
                raise G074LiveRuntimeError("G074_ENTRY_PROTECTION_NOT_CONFIRMED")
            return G074ActionOutcome.PROTECTED
        if scope.action is G074Action.CANCEL_PROTECTION:
            runner = self.exit_runner or self._run_exit_actual
            self.exit_result = runner(scope)
            if not getattr(self.exit_result, "protection_cancel_accepted", False):
                raise G074LiveRuntimeError("G074_EXIT_CANCEL_NOT_CONFIRMED")
            return G074ActionOutcome.ACCEPTED
        if scope.action is G074Action.CLOSE_POSITION:
            if not getattr(self.exit_result, "flat_reconciled", False):
                raise G074LiveRuntimeError("G074_EXIT_FLAT_NOT_CONFIRMED")
            return G074ActionOutcome.FLAT
        raise G074LiveRuntimeError("G074_ACTION_NOT_SUPPORTED")

    def time_exit_reason(
        self, evidence: G074ReconciliationEvidence, now_utc: datetime
    ) -> G074Action | None:
        if evidence.position_open is not True:
            return None
        store = V4GmoActualCoordinatorStore(self.process_lock.state_root / "coordinator.sqlite3")
        monitor = store.monitor_snapshot_safe()
        if monitor.entry_attempted_at_utc is None:
            raise G074LiveRuntimeError("G074_ENTRY_TIME_UNKNOWN")
        elapsed = (now_utc.astimezone(UTC) - monitor.entry_attempted_at_utc).total_seconds()
        return G074Action.TIME_EXIT if elapsed >= self.generation.maximum_hold_seconds else None

    def _run_entry_actual(self, session: g013.V4GmoG013PreparedSession):
        # G074 is terminal: no entry execution path may construct real
        # credentials or bypass the bounded runner CLI single-caller contract.
        # The unattended entry cycle is reachable only through
        # backend/scripts/h11_auto_v4_unattended_live_bounded_run.py.
        raise G074LiveRuntimeError("G074_GENERATION_TERMINAL_NO_ENTRY")

    def _run_exit_actual(self, scope: G074ActionScope):
        now = datetime.now(UTC)
        evidence = load_g074_reconciliation(
            state_root=self.process_lock.state_root,
            generation_digest=self.generation.digest,
            reviewed_files_digest=self.generation.implementation_digest,
            now_utc=now,
        )
        if evidence is None:
            raise G074LiveRuntimeError("G074_EXIT_RECONCILIATION_REQUIRED")
        recovery = build_g074_recovery_scope(
            state_root=self.process_lock.state_root,
            generation_digest=self.generation.digest,
            reviewed_files_digest=self.generation.implementation_digest,
            evidence=evidence,
            side=scope.side,
            action_key=scope.action_key,
            now_utc=now,
        )
        store = V4GmoActualCoordinatorStore(
            self.process_lock.state_root / "coordinator.sqlite3"
        )
        risk_policy = v4_gmo_risk_policy()
        risk_store = PhaseBRiskStore(self.process_lock.state_root / "risk.json", policy=risk_policy)
        dead_man = DeadManStore(
            self.process_lock.state_root / "dead-man-runtime.json",
            policy=v4_gmo_dead_man_policy(),
        )
        client = httpx.Client(timeout=5.0)
        transport = V4GmoHttpxPrivateTransport(
            recovered_exit_scope=recovery,
            signed_request_factory=V4GmoSignedRequestFactory(
                credential_pair=V4GmoKeychainCredentialPair()
            ),
            client=client,
            unknown_post_callback=store.engage_unknown_halt,
        )
        path = V4GmoCoordinatedActualPath(
            repository=self.repository,
            store=store,
            adapter=V4GmoActualAdapter(transport=transport),
            process_lock=self.process_lock,  # type: ignore[arg-type]
            generation=self.generation,
            risk_store=risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man,
        )
        day = now.astimezone(ZoneInfo("Asia/Tokyo")).date().isoformat()
        marker = self.process_lock.state_root / f"exit-sequence-dispatch-required.{day}.json"
        try:
            descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            transport.close()
            raise G074LiveRuntimeError("G074_EXIT_ALREADY_DISPATCHED_NO_RETRY") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "generation_digest": self.generation.digest,
                    "status": "GENERATION_BOUND_EXIT_DISPATCH_REQUIRED",
                },
                stream,
                sort_keys=True,
            )
        try:
            return V4GmoExitDispatcher(
                coordinated_path=path, state_root=self.process_lock.state_root
            ).dispatch_once(
                public_cancel_reader=V4GmoPublicMarketStatusReader(
                    generation_digest=self.generation.digest
                ),
                public_close_reader=V4GmoPublicMarketStatusReader(
                    generation_digest=self.generation.digest
                ),
                observed_at_utc=now,
                cycle_day_jst=day,
            )
        finally:
            transport.close()


__all__ = [
    "G074LiveActionPort",
    "G074LiveRuntimeError",
    "G074PrivateReconciler",
    "G074ReadOnlyActualTransport",
    "G074ReleasePreparationEvidence",
    "prepare_g074_unattended_session",
]
