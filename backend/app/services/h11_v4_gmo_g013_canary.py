"""Finite, generation-bound G013 actual canary orchestration.

This is the only G013 production orchestration surface.  It does not infer a
direction: the frozen formal 30m signal supplies it.  It issues no permit until
both operator proofs are supplied in the same process.  MARKET and exact-size
OCO are distinct one-attempt actions; partial-pending, unknown, or mismatched
states latch HALT and do not trigger another write.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.h11_auto.contracts import FormalHorizon, FormalSignal
from app.h11_auto.v4_actual_preparation_guard import (
    V4CompletedPreparationEvidence,
    load_completed_preparation_evidence,
    load_external_preparation_gate,
    require_clean_main,
    reviewed_files_digest,
)
from app.h11_auto.v4_gmo_actual_coordinator import (
    V4FrozenSignalRisk,
    V4GmoActualCoordinatorStore,
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
    V4GmoExecutionPolicy,
    build_v4_action_plan,
)
from app.h11_auto.v4_gmo_generation import (
    V4GmoFrozenGeneration,
    load_v4_gmo_frozen_generation,
)
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_gmo_actual_adapter import V4GmoPrivateOutcome
from app.services.h11_v4_gmo_actual_runtime_binding import (
    V4GmoActualRuntimeBinding,
    bind_v4_gmo_actual_runtime,
)
from app.services.h11_v4_gmo_actual_transport import (
    V4_GMO_SURFACEABLE_FAILURE_CLASSES,
)
from app.services.h11_v4_gmo_formal_canary_source import (
    MAXIMUM_FORMAL_SIGNAL_AGE_SECONDS,
    V4GmoFormalCanaryInput,
    refresh_g013_formal_canary_input,
)
from app.services.h11_v4_gmo_public_preflight import (
    G013_MAXIMUM_ENTRY_SPREAD_PIPS,
    V4GmoG013FinalQuote,
    V4GmoG013PublicOperation,
    V4GmoG013PublicOperationLedger,
    g013_public_cycle_key,
    read_g013_final_quote_once,
)


class V4GmoG013CanaryError(RuntimeError):
    """Fixed safe G013 canary failure."""


@dataclass(frozen=True, repr=False)
class V4GmoG013OrderSheet:
    generation_label: str
    strategy_version: str
    horizon: str
    symbol: str
    side: str
    size: int
    execution_type: str
    probability_up: str
    formal_origin_utc: str
    formal_valid_until_utc: str
    frozen_atr_24: str
    formal_input_provenance_digest: str
    atr_timeframe: str
    stop_distance_rule: str
    take_profit_rule: str
    maximum_spread_pips: str
    reference_bid: str
    reference_ask: str
    reference_quote_observed_at_utc: str
    maximum_reference_deviation_pips: str
    planned_loss_bound_jpy: int
    maximum_loss_per_trade_jpy: int
    maximum_unprotected_seconds: int
    same_action_retry: bool = False
    same_action_repost: bool = False
    entry_post_attempt_limit: int = 1
    partial_remainder_cancel_attempt_limit: int = 1
    protection_post_attempt_limit: int = 1
    broker_post_count_before_confirmation: int = 0

    def to_safe_dict(self) -> dict[str, object]:
        return dict(self.__dict__)

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.to_safe_dict(), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    def __repr__(self) -> str:
        return "V4GmoG013OrderSheet(<sanitized-exact-intent>)"

    def __bool__(self) -> bool:
        return False


class _V4GmoG013SessionUse:
    __slots__ = ("used",)

    def __init__(self) -> None:
        self.used = False

    def consume_once(self) -> None:
        if self.used:
            raise V4GmoG013CanaryError("G013_SESSION_ALREADY_USED")
        self.used = True


@dataclass(frozen=True, repr=False)
class V4GmoG013PreparedSession:
    repository: Path
    generation: V4GmoFrozenGeneration
    formal_input: V4GmoFormalCanaryInput
    store: V4GmoActualCoordinatorStore
    risk: V4FrozenSignalRisk
    intent: V4GmoCanaryIntent
    challenge: V4CurrentTurnChallenge
    preparation_evidence: V4CompletedPreparationEvidence
    public_operation_ledger: V4GmoG013PublicOperationLedger
    reference_quote: V4GmoG013FinalQuote
    order_sheet: V4GmoG013OrderSheet
    _use: _V4GmoG013SessionUse = field(default_factory=_V4GmoG013SessionUse)

    def current_turn_phrase_for_operator(self) -> str:
        if self._use.used:
            raise V4GmoG013CanaryError("G013_SESSION_ALREADY_USED")
        return self.challenge.phrase_for_operator_internal()

    def __repr__(self) -> str:
        return "V4GmoG013PreparedSession(<ephemeral-current-turn>)"

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4GmoG013CanaryResult:
    status: str
    entry_post_attempt_count: int
    cancel_post_attempt_count: int
    protection_post_attempt_count: int
    exact_protection_confirmed: bool
    flat_reconciled: bool
    persistent_halt: bool
    raw_response_retained: bool = False
    identifier_exposed: bool = False
    # Diagnostic only: fixed internal label describing why the entry POST failed
    # (timeout / connection / non-JSON / rejected-by-broker / pre-HTTP guard).
    # Never broker response content or identifiers.
    failure_class: str | None = None

    def to_safe_dict(self) -> dict[str, object]:
        return dict(self.__dict__)

    def __bool__(self) -> bool:
        return False


def prepare_g013_canary_session(
    *,
    repository: Path,
    now_utc: datetime | None = None,
) -> V4GmoG013PreparedSession:
    """Prepare an exact order sheet; never issue a permit or call Private API."""

    repository = repository.resolve()
    current = (now_utc or datetime.now(UTC)).astimezone(UTC)
    require_clean_main(repository=repository)
    implementation_digest = reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=implementation_digest,
    )
    if not generation.generation_label.endswith("G013"):
        raise V4GmoG013CanaryError("G013_GENERATION_REQUIRED")
    external_gate = load_external_preparation_gate(repository=repository)
    # Same instant as `current` below: today's preparation (00-60) must have
    # passed, not merely some earlier day's under this same reviewed generation.
    preparation_evidence = load_completed_preparation_evidence(
        external_gate=external_gate,
        generation_digest=generation.digest,
        now_utc=current,
    )
    state_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=generation.digest,
    )
    public_operation_ledger = V4GmoG013PublicOperationLedger(
        state_root=state_root,
        generation_digest=generation.digest,
    )
    policy = _execution_policy(generation)
    if not policy.entry_time_allowed(now_utc=current):
        raise V4GmoG013CanaryError("G013_ENTRY_TIME_BLOCKED_BEFORE_PUBLIC_GET")
    formal_input = refresh_g013_formal_canary_input(
        operation_ledger=public_operation_ledger,
        now_utc=current,
    )
    if not policy.accepts(formal_input.signal):
        raise V4GmoG013CanaryError("G013_FORMAL_OR_ENTRY_TIME_BLOCKED")
    reference_quote = read_g013_final_quote_once(
        operation_ledger=public_operation_ledger,
        operation=V4GmoG013PublicOperation.REFERENCE_QUOTE,
        cycle_key=g013_public_cycle_key(current),
    )
    store = V4GmoActualCoordinatorStore(state_root / "coordinator.sqlite3")
    # Validate and price the entry to build the exact order sheet, but do NOT reserve
    # the single cycle yet.  The cycle is reserved only after the operator's exact
    # resume + current-turn confirmations succeed (see reserve_entry_cycle in the run
    # phase), so a mistyped or timed-out confirmation leaves the generation reusable.
    risk = store.evaluate_entry_intent(
        generation=generation,
        signal=formal_input.signal,
        policy=policy,
        frozen_atr_24=formal_input.frozen_atr_24,
        now_utc=current,
    )
    # No cycle is reserved yet at order-sheet build time, so require the supervisor to be
    # alive, generation-bound, broker-quiet, and observing a clean (no-cycle) coordinator.
    _require_fresh_monitor_heartbeat(
        state_root=state_root,
        require_cycle_present=False,
    )
    cycle_ref = store.cycle_ref_for_signal_pure(
        generation=generation,
        signal_fingerprint=formal_input.signal.fingerprint,
    )
    sheet = V4GmoG013OrderSheet(
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
        reference_quote_observed_at_utc=(reference_quote.observed_at_utc.isoformat()),
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
    challenge = V4CurrentTurnChallenge.create(intent=intent)
    return V4GmoG013PreparedSession(
        repository=repository,
        generation=generation,
        formal_input=formal_input,
        store=store,
        risk=risk,
        intent=intent,
        challenge=challenge,
        preparation_evidence=preparation_evidence,
        public_operation_ledger=public_operation_ledger,
        reference_quote=reference_quote,
        order_sheet=sheet,
    )


def run_g013_actual_canary_after_exact_confirmation(
    *,
    session: V4GmoG013PreparedSession,
    major_incident_resume_phrase: str,
    current_turn_phrase: str,
    on_protected: Callable[[V4GmoG013CanaryResult], None] | None = None,
) -> V4GmoG013CanaryResult:
    """Perform at most one entry and one exact-protection POST, then supervise."""

    session._use.consume_once()
    _require_exact_session_binding(session)
    session = _refresh_session_evidence_before_permit(session)
    resume = confirm_v4_major_incident_resume_exact(
        phrase=major_incident_resume_phrase,
        generation_digest=session.generation.digest,
    )
    confirmation = confirm_v4_current_turn_exact(
        typed_phrase=current_turn_phrase,
        challenge=session.challenge,
        intent=session.intent,
    )
    # Both exact confirmations succeeded: the operator has authorised THIS exact entry.
    # Only now commit — re-check the signal is still postable, then atomically reserve
    # the single per-generation cycle. Any failure up to here (mistyped/timed-out
    # confirmation, or a signal that aged out during operator input) reserves no cycle,
    # so the generation stays reusable. reserve_entry_cycle still blocks fail-closed once
    # a cycle exists, so an entry POST is never reserved twice.
    _ensure_signal_postable(
        generation=session.generation,
        signal=session.formal_input.signal,
        now_utc=datetime.now(UTC),
    )
    state_root = v4_gmo_runtime_state_root(
        repository=session.repository,
        generation_digest=session.generation.digest,
    )
    # Before reserving, re-confirm the dead-man supervisor is alive, generation-bound and
    # broker-quiet on a still-clean coordinator. A supervisor that died during operator
    # input is caught here, before any cycle is written, leaving the generation reusable
    # rather than burned.
    _require_fresh_monitor_heartbeat(
        state_root=state_root,
        require_cycle_present=False,
    )
    session.store.reserve_entry_cycle(
        generation=session.generation,
        signal=session.formal_input.signal,
        policy=_execution_policy(session.generation),
        frozen_atr_24=session.formal_input.frozen_atr_24,
        now_utc=datetime.now(UTC),
    )
    # The single cycle now exists: require the resident dead-man supervisor to have
    # observed it (cycle_present is True) and still be fresh and broker-quiet before the
    # entry POST, so the position is monitored the instant it opens.
    _require_fresh_monitor_heartbeat(
        state_root=state_root,
        require_cycle_present=True,
    )
    # Capture the permit clock only now, AFTER the two supervisor-heartbeat waits
    # (each up to 20s). Capturing earlier could consume most of the permit's 30s
    # lifetime before it is even issued, yielding a permit born (nearly) expired
    # whose one-shot marker is already written — burning the generation with 0 POST.
    now_monotonic = time.monotonic()
    permit = issue_v4_gmo_actual_activation_permit(
        intent=session.intent,
        resume_proof=resume,
        current_turn_proof=confirmation,
        repository=session.repository,
        now_monotonic=now_monotonic,
    )
    binding = bind_v4_gmo_actual_runtime(
        repository=session.repository,
        generation=session.generation,
        activation_permit=permit,
    )
    try:
        return _run_bound_g013_canary(
            session=session,
            binding=binding,
            on_protected=on_protected,
        )
    finally:
        binding.close()


def _refresh_session_evidence_before_permit(
    session: V4GmoG013PreparedSession,
) -> V4GmoG013PreparedSession:
    """Recheck clean-main and remint exact evidence immediately before permit."""

    require_clean_main(repository=session.repository)
    implementation_digest = reviewed_files_digest(repository=session.repository)
    if implementation_digest != session.generation.implementation_digest:
        raise V4GmoG013CanaryError("G013_IMPLEMENTATION_CHANGED_BEFORE_PERMIT")
    generation = load_v4_gmo_frozen_generation(
        repository=session.repository,
        implementation_digest=implementation_digest,
    )
    if generation.digest != session.generation.digest:
        raise V4GmoG013CanaryError("G013_GENERATION_CHANGED_BEFORE_PERMIT")
    external_gate = load_external_preparation_gate(repository=session.repository)
    evidence = load_completed_preparation_evidence(
        external_gate=external_gate,
        generation_digest=generation.digest,
    )
    refreshed = replace(
        session,
        generation=generation,
        preparation_evidence=evidence,
    )
    _require_exact_session_binding(refreshed)
    return refreshed


_SURFACEABLE_FAILURE_CLASSES = V4_GMO_SURFACEABLE_FAILURE_CLASSES | frozenset(
    {
        "V4_GMO_PRIVATE_RESULT_UNKNOWN_ENVELOPE_INVALID",
        "V4_GMO_PRIVATE_RESULT_REJECTED_BY_BROKER",
        "V4_GMO_PRIVATE_GET_REJECTED_BY_BROKER",
    }
)


def _failure_class_from_path(path: object) -> str | None:
    """Fixed internal diagnostic label recorded by the adapter, if any.

    Defensive second filter: exact membership in a closed allow-list, so no
    broker content — and nothing merely shaped like an internal label — can
    surface even if an upstream filter were weakened.
    """

    label = getattr(getattr(path, "adapter", None), "last_failure_class", None)
    if isinstance(label, str) and label in _SURFACEABLE_FAILURE_CLASSES:
        return label
    return None


def _ensure_signal_postable(
    *,
    generation: V4GmoFrozenGeneration,
    signal: FormalSignal,
    now_utc: datetime,
) -> None:
    """Fail closed unless the frozen 30m signal is still postable at ``now_utc``.

    Enforced identically both immediately before the single cycle is reserved (so a
    signal that ages out during operator input reserves no cycle and leaves the
    generation reusable) and again inside the bound run as the final pre-POST gate.
    """

    if now_utc.tzinfo is None:
        raise V4GmoG013CanaryError("G013_CLOCK_INVALID_BEFORE_POST")
    now = now_utc.astimezone(UTC)
    signal_age_seconds = (now - signal.observed_at_utc).total_seconds()
    if (
        signal.horizon is not FormalHorizon.MINUTES_30
        or not 0 <= signal_age_seconds <= MAXIMUM_FORMAL_SIGNAL_AGE_SECONDS
        or now >= signal.valid_until_utc
        or not _execution_policy(generation).entry_time_allowed(now_utc=now)
    ):
        raise V4GmoG013CanaryError("G013_SIGNAL_EXPIRED_BEFORE_POST")


def _run_bound_g013_canary(
    *,
    session: V4GmoG013PreparedSession,
    binding: V4GmoActualRuntimeBinding,
    on_protected: Callable[[V4GmoG013CanaryResult], None] | None,
    wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> V4GmoG013CanaryResult:
    path = binding.coordinated_path
    signal = session.formal_input.signal
    current = wall_clock()
    _ensure_signal_postable(
        generation=session.generation, signal=signal, now_utc=current
    )
    _require_exact_session_binding(session)
    # Per-minute slot (not once-per-generation-forever): under daily rollover, the
    # same generation legitimately reads a fresh FINAL_QUOTE on every trading day
    # (and, in practice, at most once per day since reserve_entry_cycle then caps
    # the day). Minute granularity is strictly finer than day granularity, so this
    # is always at least as fresh a check as before.
    quote = read_g013_final_quote_once(
        operation_ledger=session.public_operation_ledger,
        operation=V4GmoG013PublicOperation.FINAL_QUOTE,
        cycle_key=g013_public_cycle_key(current),
    )
    _require_final_quote_near_reference(
        reference=session.reference_quote,
        final=quote,
        maximum_deviation_pips=Decimal(session.order_sheet.maximum_reference_deviation_pips),
    )
    path.dead_man_store.heartbeat(heartbeat_utc=wall_clock().astimezone(UTC))
    flat_evidence = path.reconcile_once_fixed(
        cycle_ref=session.intent.cycle_ref,
        side=signal.decision,
        requested_size=session.intent.size,
    )
    path.record_canary_entry_preflight(
        signal_fingerprint=signal.fingerprint,
        cycle_ref=session.intent.cycle_ref,
        instruction_bid=quote.bid,
        instruction_ask=quote.ask,
        reconciliation_evidence=flat_evidence,
        preparation_evidence=session.preparation_evidence,
    )
    market_plan = build_v4_action_plan(
        cycle_ref=session.intent.cycle_ref,
        action=V4GmoAction.MARKET_ENTRY,
        side=signal.decision,
        requested_size=session.intent.size,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    entry_outcome = path.perform_market_once(
        signal_fingerprint=signal.fingerprint,
        plan=market_plan,
    )
    if entry_outcome is not V4GmoPrivateOutcome.ACCEPTED_SANITIZED:
        return V4GmoG013CanaryResult(
            status="ENTRY_NOT_ACCEPTED_HALT",
            entry_post_attempt_count=1,
            cancel_post_attempt_count=0,
            protection_post_attempt_count=0,
            exact_protection_confirmed=False,
            flat_reconciled=False,
            persistent_halt=path.store.unknown_halt_latched(),
            failure_class=_failure_class_from_path(path),
        )
    post_entry_evidence = path.reconcile_once_fixed(
        cycle_ref=session.intent.cycle_ref,
        side=signal.decision,
        requested_size=session.intent.size,
    )
    recovery, carried_evidence = path.recover_pending_transport_and_carry_once(
        cycle_ref=session.intent.cycle_ref,
        reconciliation_evidence=post_entry_evidence,
    )
    cancel_attempts = 0
    if recovery.classification == "MARKET_PARTIAL_PENDING":
        cancel_plan, cancel_action_evidence = path.prepare_cancel_entry_remainder_plan(
            signal_fingerprint=signal.fingerprint,
            reconciliation_evidence=carried_evidence,
        )
        cancel_attempts = 1
        cancel_outcome = path.perform_risk_reducing_once(
            signal_fingerprint=signal.fingerprint,
            plan=cancel_plan,
            reconciliation_evidence=cancel_action_evidence,
        )
        if cancel_outcome is not V4GmoPrivateOutcome.ACCEPTED_SANITIZED:
            return V4GmoG013CanaryResult(
                status="ENTRY_REMAINDER_CANCEL_NOT_ACCEPTED_HALT",
                entry_post_attempt_count=1,
                cancel_post_attempt_count=cancel_attempts,
                protection_post_attempt_count=0,
                exact_protection_confirmed=False,
                flat_reconciled=False,
                failure_class=_failure_class_from_path(path),
                persistent_halt=True,
            )
        post_cancel_evidence = path.reconcile_once_fixed(
            cycle_ref=session.intent.cycle_ref,
            side=signal.decision,
            requested_size=session.intent.size,
        )
        recovery, carried_evidence = path.recover_pending_transport_and_carry_once(
            cycle_ref=session.intent.cycle_ref,
            reconciliation_evidence=post_cancel_evidence,
        )
    if recovery.classification == "FLAT_OR_REJECTED":
        return V4GmoG013CanaryResult(
            status="ENTRY_FLAT_OR_REJECTED",
            entry_post_attempt_count=1,
            cancel_post_attempt_count=cancel_attempts,
            protection_post_attempt_count=0,
            exact_protection_confirmed=False,
            flat_reconciled=True,
            persistent_halt=True,
        )
    if recovery.classification != "FILLED_UNPROTECTED":
        return V4GmoG013CanaryResult(
            status="ENTRY_NOT_FULLY_SETTLED_HALT",
            entry_post_attempt_count=1,
            cancel_post_attempt_count=cancel_attempts,
            protection_post_attempt_count=0,
            exact_protection_confirmed=False,
            flat_reconciled=False,
            persistent_halt=True,
        )
    protection, protection_action_evidence = path.prepare_exact_protection_plan(
        signal_fingerprint=signal.fingerprint,
        reconciliation_evidence=carried_evidence,
    )
    protection_plan = build_v4_action_plan(
        cycle_ref=session.intent.cycle_ref,
        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
        side=signal.decision,
        requested_size=protection.exact_filled_size,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )
    protection_outcome = path.perform_exact_protection_once(
        signal_fingerprint=signal.fingerprint,
        plan=protection_plan,
        protection_plan=protection,
        reconciliation_evidence=protection_action_evidence,
    )
    if protection_outcome is not V4GmoPrivateOutcome.ACCEPTED_SANITIZED:
        return V4GmoG013CanaryResult(
            status="PROTECTION_NOT_ACCEPTED_HALT",
            entry_post_attempt_count=1,
            cancel_post_attempt_count=cancel_attempts,
            protection_post_attempt_count=1,
            exact_protection_confirmed=False,
            flat_reconciled=False,
            persistent_halt=True,
            failure_class=_failure_class_from_path(path),
        )
    post_protection_evidence = path.reconcile_once_fixed(
        cycle_ref=session.intent.cycle_ref,
        side=signal.decision,
        requested_size=session.intent.size,
    )
    protection_recovery, protection_confirmation_evidence = (
        path.recover_pending_transport_and_carry_once(
            cycle_ref=session.intent.cycle_ref,
            reconciliation_evidence=post_protection_evidence,
        )
    )
    if protection_recovery.classification != "FILLED_PROTECTED":
        return V4GmoG013CanaryResult(
            status="PROTECTION_NOT_EXACT_HALT",
            entry_post_attempt_count=1,
            cancel_post_attempt_count=cancel_attempts,
            protection_post_attempt_count=1,
            exact_protection_confirmed=False,
            flat_reconciled=False,
            persistent_halt=True,
        )
    path.confirm_exact_protection_once(
        signal_fingerprint=signal.fingerprint,
        reconciliation_evidence=protection_confirmation_evidence,
    )
    if on_protected is not None:
        on_protected(
            V4GmoG013CanaryResult(
                status="POSITION_EXACTLY_PROTECTED_MONITORING",
                entry_post_attempt_count=1,
                cancel_post_attempt_count=cancel_attempts,
                protection_post_attempt_count=1,
                exact_protection_confirmed=True,
                flat_reconciled=False,
                persistent_halt=path.store.unknown_halt_latched(),
            )
        )
    lifecycle = binding.build_foreground_lifecycle_driver().run_until_flat()
    return V4GmoG013CanaryResult(
        status=("CANARY_FLAT_RECONCILED" if lifecycle.flat_reconciled else "CANARY_HALTED"),
        entry_post_attempt_count=1,
        cancel_post_attempt_count=cancel_attempts,
        protection_post_attempt_count=1,
        exact_protection_confirmed=True,
        flat_reconciled=lifecycle.flat_reconciled,
        persistent_halt=path.store.unknown_halt_latched(),
    )


def _execution_policy(generation: V4GmoFrozenGeneration) -> V4GmoExecutionPolicy:
    return V4GmoExecutionPolicy(
        strategy_version=generation.strategy_version,
        signal_config_hash=generation.signal_config_hash,
        selected_horizon=FormalHorizon(generation.selected_horizon),
        protection_contract_hash=generation.protection_contract_hash,
        broker_capability_evidence_hash=generation.broker_capability_evidence_hash,
    )


def _require_exact_session_binding(session: V4GmoG013PreparedSession) -> None:
    """Revalidate every displayed field that can affect the actual write path."""

    sheet = session.order_sheet
    signal = session.formal_input.signal
    reference = session.reference_quote
    if (
        sheet.digest != session.intent.exact_order_sheet_digest
        or session.challenge.intent_digest != session.intent.digest
        or session.intent.generation_digest != session.generation.digest
        or session.intent.side != signal.decision.value
        or session.intent.side != sheet.side
        or session.intent.size != session.generation.quantity_units
        or session.intent.size != sheet.size
        or session.intent.symbol != session.generation.symbol
        or session.intent.symbol != sheet.symbol
        or session.intent.execution_type != sheet.execution_type
        or sheet.generation_label != session.generation.generation_label
        or sheet.strategy_version != signal.strategy_version
        or sheet.horizon != signal.horizon.value
        or sheet.probability_up != format(signal.probability_up, "f")
        or sheet.formal_origin_utc != signal.observed_at_utc.isoformat()
        or sheet.formal_valid_until_utc != signal.valid_until_utc.isoformat()
        or sheet.frozen_atr_24 != format(session.formal_input.frozen_atr_24.normalize(), "f")
        or sheet.formal_input_provenance_digest
        != session.formal_input.input_provenance_digest
        or sheet.atr_timeframe != session.formal_input.atr_timeframe
        or sheet.reference_bid != format(reference.bid.normalize(), "f")
        or sheet.reference_ask != format(reference.ask.normalize(), "f")
        or sheet.reference_quote_observed_at_utc != reference.observed_at_utc.isoformat()
        or sheet.maximum_reference_deviation_pips
        != session.generation.adverse_slippage_allowance_pips
        or sheet.planned_loss_bound_jpy != session.risk.planned_loss_bound_jpy
        or sheet.maximum_loss_per_trade_jpy != session.generation.per_trade_loss_bound_jpy
        or sheet.maximum_unprotected_seconds != session.generation.maximum_unprotected_seconds
        or sheet.same_action_retry
        or sheet.same_action_repost
        or sheet.broker_post_count_before_confirmation != 0
    ):
        raise V4GmoG013CanaryError("G013_EXACT_SESSION_BINDING_MISMATCH")


def _require_final_quote_near_reference(
    *,
    reference: V4GmoG013FinalQuote,
    final: V4GmoG013FinalQuote,
    maximum_deviation_pips: Decimal,
) -> None:
    if not maximum_deviation_pips.is_finite() or maximum_deviation_pips < 0:
        raise V4GmoG013CanaryError("G013_REFERENCE_QUOTE_GATE_INVALID")
    reference_mid = (reference.bid + reference.ask) / Decimal("2")
    final_mid = (final.bid + final.ask) / Decimal("2")
    deviation_pips = abs(final_mid - reference_mid) / Decimal("0.01")
    if deviation_pips > maximum_deviation_pips:
        raise V4GmoG013CanaryError("G013_REFERENCE_QUOTE_MOVED_POST_BLOCKED")


def _require_fresh_monitor_heartbeat(
    *, state_root: Path, require_cycle_present: bool, timeout_seconds: float = 20.0
) -> None:
    """Require a fresh, generation-bound, broker-quiet resident-supervisor heartbeat.

    ``require_cycle_present`` selects the coordinator state the supervisor must be
    observing: ``False`` at order-sheet build time (no cycle is reserved yet, so the
    coordinator must be clean), and ``True`` after the single cycle is reserved and
    before the entry POST (the dead-man supervisor must already be tracking the cycle so
    the position is monitored the instant it opens).
    """

    deadline = time.monotonic() + timeout_seconds
    heartbeat_path = state_root / "supervisor-heartbeat.json"
    while time.monotonic() < deadline:
        try:
            payload = json.loads(heartbeat_path.read_text(encoding="utf-8"))
            observed = datetime.fromisoformat(str(payload["observed_at_utc"]))
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            time.sleep(0.5)
            continue
        age = (datetime.now(UTC) - observed.astimezone(UTC)).total_seconds()
        if (
            0 <= age <= 60
            and payload.get("generation_bound") is True
            and payload.get("cycle_present") is require_cycle_present
            and payload.get("broker_read") is False
            and payload.get("broker_write") is False
            and payload.get("actual_post_count") == 0
        ):
            return
        time.sleep(0.5)
    raise V4GmoG013CanaryError("G013_MONITOR_HEARTBEAT_NOT_CLEAR")
