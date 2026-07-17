"""Only production-shaped v4 path: authoritative GET, commit, then transport.

The actual transport remains unconstructible.  This module binds each future
write to one opaque, one-use three-GET reconciliation and persists every
attempt before a transport call.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.h11_auto.contracts import FormalHorizon, SignalDecision
from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import (
    DeadManStore,
    PhaseBRiskPolicy,
    PhaseBRiskState,
    PhaseBRiskStore,
    evaluate_risk_before_entry,
    record_closed_result_once,
    record_risk_entry_attempt,
)
from app.h11_auto.v4_actual_preparation_guard import V4CompletedPreparationEvidence
from app.h11_auto.v4_gmo_actual_coordinator import (
    _ENTRY_PREFLIGHT_ISSUER_TOKEN,
    V4CanaryEntryPreflightEvidence,
    V4GmoActualCoordinatorError,
    V4GmoActualCoordinatorStore,
    V4PendingTransportRecovery,
    _V4VerifiedEntryPreflightAuthorization,
)
from app.h11_auto.v4_gmo_contracts import (
    V4GmoAction,
    V4GmoActionPlan,
    V4GmoEntryStatus,
    V4GmoExecutionPolicy,
    V4GmoProtectionStatus,
)
from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration
from app.h11_auto.v4_gmo_protection import V4GmoExactProtectionPlan
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_gmo_actual_adapter import (
    V4GmoActualAdapter,
    V4GmoActualReconciliation,
    V4GmoPrivateOutcome,
)
from app.services.h11_v4_gmo_public_market_status import (
    V4GmoPublicMarketStatusError,
    V4GmoPublicMarketStatusEvidence,
    V4GmoPublicMarketStatusTransportGuard,
)


class V4GmoCoordinatedPathError(RuntimeError):
    """Fixed safe integrated-path failure."""


_RECONCILIATION_EVIDENCE_TOKEN = object()


class V4AuthoritativeReconciliationEvidence:
    """Opaque one-use handle to one fixed three-GET reconciliation."""

    __slots__ = (
        "_token",
        "_generation_digest",
        "_cycle_ref",
        "_binding_digest",
        "_issued_monotonic",
        "_consumed",
    )

    def __init__(
        self,
        *,
        token: object,
        generation_digest: str,
        cycle_ref: str,
        binding_digest: str,
        issued_monotonic: float,
    ) -> None:
        if token is not _RECONCILIATION_EVIDENCE_TOKEN:
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_RECONCILIATION_EVIDENCE_INVALID"
            )
        self._token = token
        self._generation_digest = generation_digest
        self._cycle_ref = cycle_ref
        self._binding_digest = binding_digest
        self._issued_monotonic = issued_monotonic
        self._consumed = False

    def __repr__(self) -> str:
        return "V4AuthoritativeReconciliationEvidence(<redacted-one-use>)"

    def __bool__(self) -> bool:
        return False


@dataclass
class V4GmoCoordinatedActualPath:
    repository: Path
    store: V4GmoActualCoordinatorStore
    adapter: V4GmoActualAdapter
    process_lock: H11AutoProcessLock
    generation: V4GmoFrozenGeneration
    risk_store: PhaseBRiskStore
    risk_policy: PhaseBRiskPolicy
    dead_man_store: DeadManStore
    after_persist_before_transport: Callable[[], None] = lambda: None
    wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    monotonic_clock: Callable[[], float] = time.monotonic
    reconciliation_wait: Callable[[float], None] = time.sleep
    _reconciliations: dict[int, V4GmoActualReconciliation] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _entry_authorizations: dict[
        str, _V4VerifiedEntryPreflightAuthorization
    ] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        state_root = v4_gmo_runtime_state_root(
            repository=self.repository,
            generation_digest=self.generation.digest,
        )
        expected = {
            "coordinator": (state_root / "coordinator.sqlite3").resolve(),
            "process_lock": (state_root / "process.lock").resolve(),
            "risk": (state_root / "risk.json").resolve(),
            "dead_man": (state_root / "dead-man.json").resolve(),
        }
        actual = {
            "coordinator": self.store.path.resolve(),
            "process_lock": self.process_lock.path.resolve(),
            "risk": self.risk_store.path.resolve(),
            "dead_man": self.dead_man_store.path.resolve(),
        }
        if actual != expected or state_root.is_symlink():
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_RUNTIME_PATHS_NOT_GENERATION_BOUND"
            )
        self._require_policy_binding()

    def reconcile_once_fixed(
        self,
        *,
        cycle_ref: str,
        side: SignalDecision,
        requested_size: int,
    ) -> V4AuthoritativeReconciliationEvidence:
        if not self.process_lock.held:
            raise V4GmoCoordinatedPathError("V4_COORDINATED_RECONCILIATION_BLOCKED")
        result = self.adapter.reconcile(
            cycle_ref=cycle_ref,
            side=side,
            requested_size=requested_size,
            monotonic_factory=self.monotonic_clock,
            wait=self.reconciliation_wait,
        )
        if result.snapshot.result_known is not True:
            self.store.engage_unknown_halt()
            raise V4GmoCoordinatedPathError("V4_COORDINATED_RECONCILIATION_UNKNOWN")
        evidence = V4AuthoritativeReconciliationEvidence(
            token=_RECONCILIATION_EVIDENCE_TOKEN,
            generation_digest=self.generation.digest,
            cycle_ref=cycle_ref,
            binding_digest=result._binding_digest_internal(),
            issued_monotonic=self._monotonic_now(),
        )
        self._reconciliations[id(evidence)] = result
        return evidence

    def record_canary_entry_preflight(
        self,
        *,
        signal_fingerprint: str,
        cycle_ref: str,
        instruction_bid: Decimal,
        instruction_ask: Decimal,
        reconciliation_evidence: V4AuthoritativeReconciliationEvidence,
        preparation_evidence: V4CompletedPreparationEvidence,
    ) -> str:
        """Bind one fresh authoritative flat snapshot to the exact cycle."""

        if not self.process_lock.held:
            raise V4GmoCoordinatedPathError("V4_COORDINATED_PROCESS_LOCK_REQUIRED")
        self.store.bind_generation(self.generation)
        preparation_evidence.consume_for_generation(self.generation.digest)
        now_utc = self._wall_now()
        now_monotonic = self._monotonic_now()
        reconciliation, binding_digest = self._consume_reconciliation_evidence(
            reconciliation_evidence,
            cycle_ref=cycle_ref,
            now_monotonic=now_monotonic,
            maximum_age_seconds=2.0,
        )
        authorization = self.store._record_entry_preflight_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            evidence=V4CanaryEntryPreflightEvidence(
                generation_digest=self.generation.digest,
                cycle_ref=cycle_ref,
                signal_fingerprint=signal_fingerprint,
                clock_status_label="NETWORK_TIME_ENABLED_VERIFIED",
                notification_status_label="PUSHOVER_ACK_AND_EMAIL_RECEIVED",
                account_exclusivity_label="H11_V4_ACCOUNT_EXCLUSIVE_CURRENT_GENERATION",
                unowned_position_count=reconciliation.unowned_position_count,
                active_order_count=reconciliation.account_active_order_count,
                unowned_active_order_count=(
                    reconciliation.unowned_active_order_count
                ),
            ),
            snapshot=reconciliation.snapshot,
            position_bundle_present=reconciliation.position_bundle is not None,
            average_fill_price_present=reconciliation.average_fill_price is not None,
            instruction_bid=instruction_bid,
            instruction_ask=instruction_ask,
            authoritative_reconciliation_digest=binding_digest,
            now_utc=now_utc,
            now_monotonic=now_monotonic,
        )
        if signal_fingerprint in self._entry_authorizations:
            self.store.engage_unknown_halt()
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_ENTRY_AUTHORIZATION_DUPLICATE"
            )
        self._entry_authorizations[signal_fingerprint] = authorization
        return authorization._preflight_digest

    def recover_pending_transport_once(
        self,
        *,
        cycle_ref: str,
        reconciliation_evidence: V4AuthoritativeReconciliationEvidence,
    ) -> V4PendingTransportRecovery:
        """Consume one fresh reconciliation to resolve a crashed attempt only."""

        if not self.process_lock.held:
            raise V4GmoCoordinatedPathError("V4_COORDINATED_PROCESS_LOCK_REQUIRED")
        self.store.bind_generation(self.generation)
        reconciliation, binding_digest = self._consume_reconciliation_evidence(
            reconciliation_evidence,
            cycle_ref=cycle_ref,
            now_monotonic=self._monotonic_now(),
            maximum_age_seconds=15.0,
        )
        try:
            return self.store._resolve_pending_transport_from_coordinated_path(
                issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
                cycle_ref=cycle_ref,
                snapshot=reconciliation.snapshot,
                position_bundle_total=(
                    reconciliation.position_bundle.total_size
                    if reconciliation.position_bundle is not None
                    else None
                ),
                authoritative_reconciliation_digest=binding_digest,
                now_utc=self._wall_now(),
            )
        except V4GmoActualCoordinatorError:
            self.store.engage_unknown_halt()
            raise

    def perform_market_once(
        self,
        *,
        signal_fingerprint: str,
        plan: V4GmoActionPlan,
    ) -> V4GmoPrivateOutcome:
        now_utc = self._wall_now()
        now_monotonic = self._monotonic_now()
        cycle_day_jst = now_utc.astimezone(ZoneInfo("Asia/Tokyo")).date().isoformat()
        self._require_ready(action=V4GmoAction.MARKET_ENTRY, plan=plan)
        policy = self._execution_policy()
        if not policy.entry_time_allowed(now_utc=now_utc):
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_ENTRY_TIME_BLOCKED"
            )
        risk_state = self._require_entry_runtime_safety(
            now_utc=now_utc,
            cycle_day_jst=cycle_day_jst,
        )
        entry_authorization = self._entry_authorizations.pop(
            signal_fingerprint, None
        )
        if entry_authorization is None:
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_ENTRY_AUTHORIZATION_REQUIRED"
            )
        attempt = self.store._record_market_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            entry_authorization=entry_authorization,
            signal_fingerprint=signal_fingerprint,
            plan=plan,
            now_utc=now_utc,
            now_monotonic=now_monotonic,
        )
        if attempt.cycle_ref != plan.cycle_ref:
            self.store.engage_unknown_halt()
            raise V4GmoCoordinatedPathError("V4_COORDINATED_CYCLE_MISMATCH")
        try:
            record_risk_entry_attempt(
                state=risk_state,
                policy=self.risk_policy,
                cycle_day_jst=cycle_day_jst,
            )
            self.risk_store.save(risk_state)
            self.after_persist_before_transport()
            self._require_transport_boundary_dead_man()
            outcome = self.adapter.perform_once(
                plan=plan,
                persisted_authorization=attempt.authorization,
                now_monotonic=self._monotonic_now(),
            )
            self._finish_transport(plan=plan, outcome=outcome)
        except BaseException:
            self.store.engage_unknown_halt()
            raise
        return outcome

    def prepare_exact_protection_plan(
        self,
        *,
        signal_fingerprint: str,
        reconciliation_evidence: V4AuthoritativeReconciliationEvidence,
    ) -> tuple[V4GmoExactProtectionPlan, V4AuthoritativeReconciliationEvidence]:
        """Persist an exact-fill plan and carry the same bundle forward once."""

        cycle_ref = self.store.cycle_ref_for_signal_internal(signal_fingerprint)
        now_utc = self._wall_now()
        now_monotonic = self._monotonic_now()
        reconciliation, _ = self._consume_reconciliation_evidence(
            reconciliation_evidence,
            cycle_ref=cycle_ref,
            now_monotonic=now_monotonic,
            maximum_age_seconds=15.0,
        )
        if (
            reconciliation.snapshot.fresh is not True
            or reconciliation.snapshot.result_known is not True
            or reconciliation.snapshot.position_count != 1
            or reconciliation.snapshot.position_side is not self._signal_side(
                signal_fingerprint
            )
            or reconciliation.average_fill_price is None
            or reconciliation.snapshot.filled_size <= 0
            or reconciliation.snapshot.pending_entry_size != 0
            or reconciliation.snapshot.entry_status is not V4GmoEntryStatus.FILLED
            or reconciliation.snapshot.protection_size != 0
            or reconciliation.snapshot.protection_status
            is not V4GmoProtectionStatus.NONE
            or reconciliation.position_bundle is None
            or reconciliation.position_bundle.total_size
            != reconciliation.snapshot.filled_size
        ):
            self.store.engage_unknown_halt()
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_EXACT_FILL_RECONCILIATION_REQUIRED"
            )
        plan = self.store._persist_exact_protection_plan_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal_fingerprint,
            reconciled_average_fill_price=reconciliation.average_fill_price,
            reconciled_filled_size=reconciliation.snapshot.filled_size,
            now_utc=now_utc,
            now_monotonic=now_monotonic,
        )
        carried = self._mint_reconciliation_evidence(
            cycle_ref=cycle_ref,
            reconciliation=reconciliation,
            issued_monotonic=now_monotonic,
        )
        return plan, carried

    def _signal_side(self, signal_fingerprint: str) -> SignalDecision:
        return self.store.side_for_signal_internal(signal_fingerprint)

    def perform_exact_protection_once(
        self,
        *,
        signal_fingerprint: str,
        plan: V4GmoActionPlan,
        protection_plan: V4GmoExactProtectionPlan,
        reconciliation_evidence: V4AuthoritativeReconciliationEvidence,
    ) -> V4GmoPrivateOutcome:
        now_utc = self._wall_now()
        now_monotonic = self._monotonic_now()
        self._require_ready(action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION, plan=plan)
        reconciliation, binding_digest = self._consume_reconciliation_evidence(
            reconciliation_evidence,
            cycle_ref=plan.cycle_ref,
            now_monotonic=now_monotonic,
            maximum_age_seconds=15.0,
        )
        attempt = self.store._record_exact_protection_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal_fingerprint,
            plan=plan,
            protection_plan=protection_plan,
            reconciliation_digest=binding_digest,
            now_utc=now_utc,
            now_monotonic=now_monotonic,
        )
        if attempt.cycle_ref != plan.cycle_ref:
            self.store.engage_unknown_halt()
            raise V4GmoCoordinatedPathError("V4_COORDINATED_CYCLE_MISMATCH")
        try:
            self.after_persist_before_transport()
            outcome = self.adapter.perform_once(
                plan=plan,
                persisted_authorization=attempt.authorization,
                now_monotonic=self._monotonic_now(),
                reconciliation=reconciliation,
                protection_plan=protection_plan,
            )
            self._finish_transport(plan=plan, outcome=outcome)
        except BaseException:
            self.store.engage_unknown_halt()
            raise
        return outcome

    def perform_risk_reducing_once(
        self,
        *,
        signal_fingerprint: str,
        plan: V4GmoActionPlan,
        reconciliation_evidence: V4AuthoritativeReconciliationEvidence,
        market_status_evidence: V4GmoPublicMarketStatusEvidence | None = None,
    ) -> V4GmoPrivateOutcome:
        now_utc = self._wall_now()
        now_monotonic = self._monotonic_now()
        if plan.action not in {
            V4GmoAction.CANCEL_ENTRY_REMAINDER,
            V4GmoAction.CANCEL_MISMATCHED_PROTECTION,
            V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
            V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
            V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
        }:
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_RISK_REDUCING_ACTION_REQUIRED"
            )
        self._require_ready(action=plan.action, plan=plan)
        public_market_status_guard: (
            V4GmoPublicMarketStatusTransportGuard | None
        ) = None
        if plan.action in {
            V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
            V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
        }:
            try:
                if market_status_evidence is None:
                    raise V4GmoPublicMarketStatusError(
                        "V4_PUBLIC_MARKET_STATUS_EVIDENCE_REQUIRED"
                    )
                public_market_status_guard = (
                    market_status_evidence.bind_transport_guard(
                        generation_digest=self.generation.digest,
                        monotonic_factory=self.monotonic_clock,
                    )
                )
            except V4GmoPublicMarketStatusError:
                self.store.engage_unknown_halt()
                raise V4GmoCoordinatedPathError(
                    "V4_COORDINATED_TIME_EXIT_MARKET_OPEN_REQUIRED"
                ) from None
        reconciliation, binding_digest = self._consume_reconciliation_evidence(
            reconciliation_evidence,
            cycle_ref=plan.cycle_ref,
            now_monotonic=now_monotonic,
            maximum_age_seconds=15.0,
        )
        attempt = self.store._record_risk_reducing_attempt_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            signal_fingerprint=signal_fingerprint,
            plan=plan,
            snapshot=reconciliation.snapshot,
            position_bundle_total=(
                reconciliation.position_bundle.total_size
                if reconciliation.position_bundle is not None
                else None
            ),
            authoritative_reconciliation_digest=binding_digest,
            now_utc=now_utc,
        )
        if attempt.cycle_ref != plan.cycle_ref:
            self.store.engage_unknown_halt()
            raise V4GmoCoordinatedPathError("V4_COORDINATED_CYCLE_MISMATCH")
        try:
            self.after_persist_before_transport()
            outcome = self.adapter.perform_once(
                plan=plan,
                persisted_authorization=attempt.authorization,
                now_monotonic=self._monotonic_now(),
                reconciliation=reconciliation,
                public_market_status_guard=public_market_status_guard,
            )
            self._finish_transport(plan=plan, outcome=outcome)
        except BaseException:
            self.store.engage_unknown_halt()
            raise
        return outcome

    def confirm_exact_protection_once(
        self,
        *,
        signal_fingerprint: str,
        reconciliation_evidence: V4AuthoritativeReconciliationEvidence,
    ) -> None:
        now_utc = self._wall_now()
        now_monotonic = self._monotonic_now()
        if not self.process_lock.held:
            raise V4GmoCoordinatedPathError("V4_COORDINATED_PROCESS_LOCK_REQUIRED")
        cycle_ref = self.store.cycle_ref_for_signal_internal(signal_fingerprint)
        reconciliation, _ = self._consume_reconciliation_evidence(
            reconciliation_evidence,
            cycle_ref=cycle_ref,
            now_monotonic=now_monotonic,
            maximum_age_seconds=15.0,
        )
        snapshot = reconciliation.snapshot
        if (
            snapshot.result_known is not True
            or snapshot.protection_status is not V4GmoProtectionStatus.EXACT_MATCH
            or snapshot.protection_size != snapshot.filled_size
            or snapshot.protection_size <= 0
        ):
            self.store.engage_unknown_halt()
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_PROTECTION_CONFIRMATION_FAILED"
            )
        try:
            self.store.confirm_exact_protection_within_deadline(
                signal_fingerprint=signal_fingerprint,
                confirmed_protection_size=snapshot.protection_size,
                now_utc=now_utc,
                now_monotonic=now_monotonic,
            )
        except V4GmoActualCoordinatorError:
            self.store.engage_unknown_halt()
            raise

    def record_flat_closed_result_once(
        self,
        *,
        signal_fingerprint: str,
        reconciliation_evidence: V4AuthoritativeReconciliationEvidence,
    ) -> bool:
        """Apply one owned flat settlement result to persistent risk state."""

        if not self.process_lock.held:
            raise V4GmoCoordinatedPathError("V4_COORDINATED_PROCESS_LOCK_REQUIRED")
        cycle_ref = self.store.cycle_ref_for_signal_internal(signal_fingerprint)
        now_utc = self._wall_now()
        reconciliation, _ = self._consume_reconciliation_evidence(
            reconciliation_evidence,
            cycle_ref=cycle_ref,
            now_monotonic=self._monotonic_now(),
            maximum_age_seconds=15.0,
        )
        snapshot = reconciliation.snapshot
        expected_size = self.store.expected_closed_size_for_signal_internal(
            signal_fingerprint
        )
        if (
            snapshot.fresh is not True
            or snapshot.result_known is not True
            or snapshot.position_count != 0
            or snapshot.position_side is not None
            or snapshot.filled_size != 0
            or snapshot.pending_entry_size != 0
            or snapshot.protection_size != 0
            or reconciliation.position_bundle is not None
            or reconciliation.closed_size != expected_size
            or reconciliation.realized_pnl_jpy_internal is None
        ):
            self.store.engage_unknown_halt()
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_FLAT_RESULT_RECONCILIATION_REQUIRED"
            )
        try:
            self.store.record_closed_metrics_once_internal(
                cycle_ref=cycle_ref,
                realized_pnl_jpy=reconciliation.realized_pnl_jpy_internal,
            )
        except V4GmoActualCoordinatorError:
            self.store.engage_unknown_halt()
            raise
        risk_state = self.risk_store.load()
        _, applied = record_closed_result_once(
            state=risk_state,
            policy=self.risk_policy,
            cycle_day_jst=(
                now_utc.astimezone(ZoneInfo("Asia/Tokyo")).date().isoformat()
            ),
            cycle_ref=cycle_ref,
            pnl_jpy_internal=reconciliation.realized_pnl_jpy_internal,
        )
        self.risk_store.save(risk_state)
        return applied

    def _mint_reconciliation_evidence(
        self,
        *,
        cycle_ref: str,
        reconciliation: V4GmoActualReconciliation,
        issued_monotonic: float,
    ) -> V4AuthoritativeReconciliationEvidence:
        evidence = V4AuthoritativeReconciliationEvidence(
            token=_RECONCILIATION_EVIDENCE_TOKEN,
            generation_digest=self.generation.digest,
            cycle_ref=cycle_ref,
            binding_digest=reconciliation._binding_digest_internal(),
            issued_monotonic=issued_monotonic,
        )
        self._reconciliations[id(evidence)] = reconciliation
        return evidence

    def _consume_reconciliation_evidence(
        self,
        evidence: V4AuthoritativeReconciliationEvidence,
        *,
        cycle_ref: str,
        now_monotonic: float,
        maximum_age_seconds: float,
    ) -> tuple[V4GmoActualReconciliation, str]:
        if (
            type(evidence) is not V4AuthoritativeReconciliationEvidence
            or getattr(evidence, "_token", None) is not _RECONCILIATION_EVIDENCE_TOKEN
            or evidence._consumed
            or evidence._generation_digest != self.generation.digest
            or evidence._cycle_ref != cycle_ref
            or not 0
            <= now_monotonic - evidence._issued_monotonic
            <= maximum_age_seconds
        ):
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_RECONCILIATION_EVIDENCE_INVALID"
            )
        reconciliation = self._reconciliations.pop(id(evidence), None)
        if (
            reconciliation is None
            or reconciliation._binding_digest_internal() != evidence._binding_digest
        ):
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_RECONCILIATION_EVIDENCE_INVALID"
            )
        evidence._consumed = True
        return reconciliation, evidence._binding_digest

    def _finish_transport(
        self,
        *,
        plan: V4GmoActionPlan,
        outcome: V4GmoPrivateOutcome,
    ) -> None:
        self.store._record_transport_outcome_from_coordinated_path(
            issuer_token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            cycle_ref=plan.cycle_ref,
            action=plan.action,
            outcome_label=outcome.value,
        )

    def _require_ready(self, *, action: V4GmoAction, plan: V4GmoActionPlan) -> None:
        if not self.process_lock.held:
            raise V4GmoCoordinatedPathError("V4_COORDINATED_PROCESS_LOCK_REQUIRED")
        if action is V4GmoAction.MARKET_ENTRY and self.store.unknown_halt_latched():
            raise V4GmoCoordinatedPathError("V4_COORDINATED_UNKNOWN_HALT_LATCHED")
        if plan.action is not action:
            raise V4GmoCoordinatedPathError("V4_COORDINATED_ACTION_MISMATCH")
        self.store.bind_generation(self.generation)
        self._require_policy_binding()

    def _require_policy_binding(self) -> None:
        if (
            self.risk_policy.policy_label != self.generation.risk_policy_label
            or self.risk_policy.digest != self.generation.risk_policy_digest
            or self.dead_man_store.policy.policy_label
            != self.generation.dead_man_policy_label
            or self.dead_man_store.policy.digest
            != self.generation.dead_man_policy_digest
        ):
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_RUNTIME_POLICY_MISMATCH"
            )

    def _execution_policy(self) -> V4GmoExecutionPolicy:
        return V4GmoExecutionPolicy(
            strategy_version=self.generation.strategy_version,
            signal_config_hash=self.generation.signal_config_hash,
            selected_horizon=FormalHorizon(self.generation.selected_horizon),
            protection_contract_hash=self.generation.protection_contract_hash,
            broker_capability_evidence_hash=(
                self.generation.broker_capability_evidence_hash
            ),
        )

    def _require_entry_runtime_safety(
        self,
        *,
        now_utc: datetime,
        cycle_day_jst: str,
    ) -> PhaseBRiskState:
        dead_man = self.dead_man_store.evaluate(now_utc=now_utc)
        if not dead_man.alive:
            self.store.engage_unknown_halt()
            raise V4GmoCoordinatedPathError("V4_COORDINATED_DEAD_MAN_BLOCKED")
        risk_state = self.risk_store.load()
        gate = evaluate_risk_before_entry(
            state=risk_state,
            policy=self.risk_policy,
            cycle_day_jst=cycle_day_jst,
        )
        if not gate.allowed:
            raise V4GmoCoordinatedPathError("V4_COORDINATED_RISK_GATE_BLOCKED")
        return risk_state

    def _require_transport_boundary_dead_man(self) -> None:
        if not self.dead_man_store.evaluate(now_utc=self._wall_now()).alive:
            self.store.engage_unknown_halt()
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_TRANSPORT_BOUNDARY_DEAD_MAN_BLOCKED"
            )

    def _wall_now(self) -> datetime:
        value = self.wall_clock()
        if value.tzinfo is None:
            raise V4GmoCoordinatedPathError("V4_COORDINATED_WALL_CLOCK_INVALID")
        return value.astimezone(UTC)

    def _monotonic_now(self) -> float:
        value = self.monotonic_clock()
        if (
            not isinstance(value, int | float)
            or not math.isfinite(value)
            or value < 0
        ):
            raise V4GmoCoordinatedPathError(
                "V4_COORDINATED_MONOTONIC_CLOCK_INVALID"
            )
        return float(value)

    def __repr__(self) -> str:
        return "V4GmoCoordinatedActualPath(<persistent-before-transport>)"

    def __bool__(self) -> bool:
        return False
