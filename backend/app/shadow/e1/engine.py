"""Finite full-auto E1 shadow engine.

The engine consumes caller-supplied local/synthetic market frames and decision
labels.  It has no scheduler and no network surface.  Labels never reach the
virtual executor: only a risk-gate-issued, TTL-bound, single-use token can do so.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from functools import wraps
from pathlib import Path
from threading import RLock

from app.shadow.e1.contracts import (
    E1CycleResult,
    E1Policy,
    E1Stage,
    EngineDecision,
    EngineLabel,
    EnginePhase,
    EntryIntent,
    ExecutionOutcome,
    FaultInjection,
    FaultKind,
    GateAction,
    KillReason,
    MarketFrame,
    PnlCategory,
    PositionSide,
    ReconcileStatus,
    SettlementIntent,
    ShadowGateToken,
    VirtualExecutionResult,
    VirtualPosition,
    build_token_expiry,
    canonical_decimal,
    canonical_timestamp,
    classify_pnl,
    finite_decimal,
    make_local_id,
    parse_timestamp,
    position_digest,
    validate_safe_local_id,
)
from app.shadow.e1.persistence import (
    E1PersistenceError,
    JournalEventType,
    JournalRecord,
    ShadowIntentJournal,
    VirtualVenueStateStore,
)


class E1EngineError(RuntimeError):
    """Sanitized engine failure; no raw external data exists in this lane."""


class SimulatedShadowCrash(RuntimeError):
    """Bounded fault-harness exception, never a real process/network failure."""


def _serialized_engine_operation(method):
    """Serialize all state-changing entry points on one engine instance."""

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._operation_lock:
            return method(self, *args, **kwargs)

    return wrapped


class ShadowTokenAuthority:
    """In-process issuer registry; forged or reused tokens are rejected."""

    def __init__(
        self,
        *,
        run_id: str,
        policy: E1Policy,
        journal: ShadowIntentJournal,
        issuer_key: object,
        clock: Callable[[], datetime],
    ) -> None:
        self.run_id = run_id
        self.policy = policy
        self.journal = journal
        self._issuer_key = issuer_key
        self._clock = clock
        self._counter = 0
        self._issued: dict[str, ShadowGateToken] = {}
        self._consumed: set[str] = set()
        self._executed: set[str] = set()
        self._process_lock = RLock()

    def issue(
        self,
        *,
        action: GateAction,
        intent_id: str,
        intent_digest: str,
        issuer_key: object,
    ) -> ShadowGateToken:
        with self._process_lock:
            if issuer_key is not self._issuer_key:
                raise E1EngineError("only the bound E1 risk gate may issue a shadow token")
            self._counter += 1
            issued_at = canonical_timestamp(self._clock())
            token_id = make_local_id(
                "shadowtoken",
                {
                    "action": action.value,
                    "config_hash": self.policy.config_hash,
                    "counter": self._counter,
                    "intent_id": intent_id,
                    "intent_digest": intent_digest,
                    "issued_at": issued_at,
                    "run_id": self.run_id,
                },
            )
            token = ShadowGateToken(
                token_id=token_id,
                run_id=self.run_id,
                intent_id=intent_id,
                intent_digest=intent_digest,
                action=action,
                stage=E1Stage.SHADOW,
                config_hash=self.policy.config_hash,
                issued_at=issued_at,
                expires_at=build_token_expiry(issued_at, self.policy.token_ttl_seconds),
            )
            self._issued[token.token_id] = token
            return token

    def commit_intent(
        self,
        *,
        token: ShadowGateToken,
        durable_append: Callable[[], None],
    ) -> None:
        with self._process_lock:
            self._validate(token=token)
            if token.token_id in self._consumed or token.token_id in self._executed:
                raise E1EngineError("shadow token is single-use")
            if any(record.token_id == token.token_id for record in self.journal.records):
                raise E1EngineError("shadow token already has a durable journal record")
            record_count = len(self.journal.records)
            durable_append()
            records = self.journal.records
            if len(records) != record_count + 1:
                raise E1EngineError("shadow token consumption requires one durable intent")
            record = records[-1]
            if (
                record.event_type is not JournalEventType.INTENT_PREPARED
                or record.token_id != token.token_id
                or record.intent_id != token.intent_id
                or record.intent_digest != token.intent_digest
                or record.action is not token.action
            ):
                raise E1EngineError("durable intent does not match the shadow token")
            self._consumed.add(token.token_id)

    def begin_execution(
        self,
        *,
        token: ShadowGateToken,
        action: GateAction,
        intent_id: str,
        intent_digest: str,
    ) -> None:
        with self._process_lock:
            self._validate(token=token)
            if token.token_id not in self._consumed:
                raise E1EngineError("shadow token has no durable intent")
            if token.token_id in self._executed:
                raise E1EngineError("shadow token is single-use")
            if (
                token.action is not action
                or token.intent_id != intent_id
                or token.intent_digest != intent_digest
            ):
                raise E1EngineError("shadow token action/intent binding mismatch")
            records = self.journal.records
            record = records[-1] if records else None
            if (
                record is None
                or record.event_type is not JournalEventType.VIRTUAL_EXECUTION_STARTED
                or record.token_id != token.token_id
                or record.intent_id != intent_id
                or record.intent_digest != intent_digest
                or record.action is not action
            ):
                raise E1EngineError("virtual execution start is not durably journaled")
            self._executed.add(token.token_id)

    def _validate(self, *, token: ShadowGateToken) -> None:
        if not isinstance(token, ShadowGateToken):
            raise E1EngineError("virtual executor accepts ShadowGateToken only")
        registered = self._issued.get(token.token_id)
        if registered != token:
            raise E1EngineError("shadow token was not issued by this engine")
        if (
            token.run_id != self.run_id
            or token.stage is not E1Stage.SHADOW
            or token.config_hash != self.policy.config_hash
        ):
            raise E1EngineError("shadow token run/stage/config mismatch")
        if token.is_expired(self._clock()):
            raise E1EngineError("shadow token expired")


class E1RiskGate:
    """Issues capabilities only after every E1 entry/settlement gate passes."""

    def __init__(
        self,
        *,
        run_id: str,
        policy: E1Policy,
        journal: ShadowIntentJournal,
        venue: VirtualVenueStateStore,
        authority: ShadowTokenAuthority,
        issuer_key: object,
    ) -> None:
        self.run_id = run_id
        self.policy = policy
        self.journal = journal
        self.venue = venue
        self.authority = authority
        self._issuer_key = issuer_key

    def issue_entry_token(
        self,
        *,
        intent: EntryIntent,
        market: MarketFrame,
        phase: EnginePhase,
    ) -> tuple[ShadowGateToken | None, tuple[str, ...]]:
        reasons = list(self._common_reasons(market=market, require_heartbeat=True))
        if phase is not EnginePhase.READY_FLAT:
            reasons.append("ENGINE_NOT_READY_FLAT")
        if self.journal.kill_active or self.journal.halted:
            reasons.append("STICKY_HALT_OR_KILL_ACTIVE")
        if self.venue.position_count != 0:
            reasons.append("POSITION_LIMIT_ONE_BLOCKED")
        if intent.run_id != self.run_id or intent.config_hash != self.policy.config_hash:
            reasons.append("INTENT_RUN_OR_CONFIG_MISMATCH")
        if intent.position.symbol != self.policy.allowed_symbol:
            reasons.append("SYMBOL_NOT_ALLOWED")
        if intent.position.units != self.policy.fixed_virtual_units:
            reasons.append("FIXED_VIRTUAL_UNITS_MISMATCH")
        counters = self.journal.risk_counters(now=market.evaluation_time)
        if counters["entries_today"] >= self.policy.max_entries_per_day:
            reasons.append("DAILY_ENTRY_CAP_REACHED")
        if counters["daily_loss"] >= self.policy.max_daily_virtual_loss:
            reasons.append("DAILY_VIRTUAL_LOSS_CAP_REACHED")
        if counters["weekly_loss"] >= self.policy.max_weekly_virtual_loss:
            reasons.append("WEEKLY_VIRTUAL_LOSS_CAP_REACHED")
        if counters["consecutive_losses"] >= self.policy.max_consecutive_losses:
            reasons.append("CONSECUTIVE_LOSS_CAP_REACHED")
        prospective_loss = (
            abs(intent.position.entry_price - intent.position.protective_stop_price)
            * intent.position.units
        )
        if prospective_loss > self.policy.max_virtual_loss_per_trade:
            reasons.append("PER_TRADE_VIRTUAL_LOSS_CAP_EXCEEDED")
        if counters["daily_loss"] + prospective_loss > self.policy.max_daily_virtual_loss:
            reasons.append("DAILY_PROSPECTIVE_VIRTUAL_LOSS_CAP_EXCEEDED")
        if counters["weekly_loss"] + prospective_loss > self.policy.max_weekly_virtual_loss:
            reasons.append("WEEKLY_PROSPECTIVE_VIRTUAL_LOSS_CAP_EXCEEDED")
        if market.spread_pips > self.policy.max_spread_pips:
            reasons.append("SPREAD_LIMIT_EXCEEDED")
        if not market.event_clear:
            reasons.append("EVENT_WINDOW_BLOCKED")
        if not market.trading_window_open:
            reasons.append("NO_TRADE_WINDOW_ACTIVE")
        last_entry_at = counters["last_entry_at"]
        if last_entry_at is not None:
            elapsed = parse_timestamp(market.evaluation_time) - parse_timestamp(last_entry_at)
            if elapsed.total_seconds() < self.policy.cooldown_seconds:
                reasons.append("COOLDOWN_ACTIVE")
        if reasons:
            return None, tuple(dict.fromkeys(reasons))
        return (
            self.authority.issue(
                action=GateAction.VIRTUAL_ENTRY,
                intent_id=intent.intent_id,
                intent_digest=intent.intent_digest,
                issuer_key=self._issuer_key,
            ),
            (),
        )

    def issue_settlement_token(
        self,
        *,
        intent: SettlementIntent,
        market: MarketFrame,
        phase: EnginePhase,
        emergency: bool = False,
    ) -> tuple[ShadowGateToken | None, tuple[str, ...]]:
        reasons: list[str] = []
        if not emergency:
            reasons.extend(self._common_reasons(market=market, require_heartbeat=True))
            if phase is not EnginePhase.POSITION_OPEN:
                reasons.append("ENGINE_NOT_IN_POSITION_OPEN")
            if self.journal.kill_active or self.journal.halted:
                reasons.append("STICKY_HALT_OR_KILL_ACTIVE")
        if intent.run_id != self.run_id or intent.config_hash != self.policy.config_hash:
            reasons.append("INTENT_RUN_OR_CONFIG_MISMATCH")
        position = self.venue.position
        if position is None or position.position_ref != intent.position_ref:
            reasons.append("POSITION_SPECIFIC_SETTLEMENT_MISMATCH")
        if reasons:
            return None, tuple(dict.fromkeys(reasons))
        return (
            self.authority.issue(
                action=GateAction.VIRTUAL_SETTLEMENT,
                intent_id=intent.intent_id,
                intent_digest=intent.intent_digest,
                issuer_key=self._issuer_key,
            ),
            (),
        )

    def _common_reasons(
        self, *, market: MarketFrame, require_heartbeat: bool
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if market.symbol != self.policy.allowed_symbol:
            reasons.append("SYMBOL_NOT_ALLOWED")
        if market.age_seconds < 0 or market.age_seconds > self.policy.max_data_age_seconds:
            reasons.append("MARKET_DATA_NOT_FRESH")
        if not market.market_open:
            reasons.append("MARKET_NOT_OPEN")
        if not market.feed_consistent:
            reasons.append("FEED_STATE_INCONSISTENT")
        if require_heartbeat:
            heartbeat = self.journal.last_heartbeat
            if heartbeat is None:
                reasons.append("HEARTBEAT_MISSING")
            else:
                age = parse_timestamp(market.evaluation_time) - parse_timestamp(heartbeat)
                if age.total_seconds() < 0 or (
                    age.total_seconds() > self.policy.heartbeat_timeout_seconds
                ):
                    reasons.append("HEARTBEAT_EXPIRED")
        return tuple(reasons)


class ShadowVirtualExecutor:
    """Virtual effect boundary.  Public methods require a ShadowGateToken."""

    def __init__(
        self,
        *,
        authority: ShadowTokenAuthority,
        venue: VirtualVenueStateStore,
        mutation_key: object,
    ) -> None:
        self.authority = authority
        self.venue = venue
        self._mutation_key = mutation_key

    def execute_entry(
        self,
        *,
        token: ShadowGateToken,
        intent: EntryIntent,
        fault: FaultInjection,
    ) -> VirtualExecutionResult:
        self.authority.begin_execution(
            token=token,
            action=GateAction.VIRTUAL_ENTRY,
            intent_id=intent.intent_id,
            intent_digest=intent.intent_digest,
        )
        if fault.kind is FaultKind.REJECTED:
            return self._result(ExecutionOutcome.REJECTED)
        if fault.kind is FaultKind.NONE:
            self.venue._open_position(intent.position, executor_key=self._mutation_key)
            return self._result(ExecutionOutcome.ACCEPTED)
        if fault.kind is FaultKind.PARTIAL_FILL:
            partial = replace(intent.position, units=max(1, intent.position.units // 2))
            self.venue._open_position(partial, executor_key=self._mutation_key)
            return self._result(ExecutionOutcome.PARTIAL_FILL)
        if fault.apply_effect_before_fault:
            self.venue._open_position(intent.position, executor_key=self._mutation_key)
        if fault.kind is FaultKind.CRASH_MID_VIRTUAL_EXECUTION:
            raise SimulatedShadowCrash("simulated crash after durable intent")
        outcomes = {
            FaultKind.TIMEOUT: ExecutionOutcome.TIMEOUT,
            FaultKind.UNKNOWN_RESULT: ExecutionOutcome.UNKNOWN,
            FaultKind.NETWORK_ERROR: ExecutionOutcome.NETWORK_ERROR,
        }
        try:
            return self._result(outcomes[fault.kind])
        except KeyError as error:
            raise E1EngineError("unsupported entry fault kind") from error

    def execute_settlement(
        self,
        *,
        token: ShadowGateToken,
        intent: SettlementIntent,
        fault: FaultInjection,
    ) -> VirtualExecutionResult:
        self.authority.begin_execution(
            token=token,
            action=GateAction.VIRTUAL_SETTLEMENT,
            intent_id=intent.intent_id,
            intent_digest=intent.intent_digest,
        )
        if fault.kind is FaultKind.REJECTED:
            return self._result(ExecutionOutcome.REJECTED)
        if fault.kind is FaultKind.NONE:
            self.venue._settle_position_specific(
                position_ref=intent.position_ref,
                executor_key=self._mutation_key,
            )
            return self._result(ExecutionOutcome.ACCEPTED)
        if fault.kind is FaultKind.PARTIAL_FILL:
            return self._result(ExecutionOutcome.PARTIAL_FILL)
        if fault.apply_effect_before_fault:
            self.venue._settle_position_specific(
                position_ref=intent.position_ref,
                executor_key=self._mutation_key,
            )
        if fault.kind is FaultKind.CRASH_MID_VIRTUAL_EXECUTION:
            raise SimulatedShadowCrash("simulated crash after durable settlement intent")
        outcomes = {
            FaultKind.TIMEOUT: ExecutionOutcome.TIMEOUT,
            FaultKind.UNKNOWN_RESULT: ExecutionOutcome.UNKNOWN,
            FaultKind.NETWORK_ERROR: ExecutionOutcome.NETWORK_ERROR,
        }
        try:
            return self._result(outcomes[fault.kind])
        except KeyError as error:
            raise E1EngineError("unsupported settlement fault kind") from error

    def _result(self, outcome: ExecutionOutcome) -> VirtualExecutionResult:
        return VirtualExecutionResult(
            outcome=outcome,
            observed_state_digest=self.venue.state_digest,
            position_count=self.venue.position_count,
        )


class E1ShadowFullAutoEngine:
    """Bounded E1 orchestrator.  A caller drives finite steps; no loop is created."""

    def __init__(
        self,
        *,
        run_id: str,
        policy: E1Policy,
        journal: ShadowIntentJournal,
        venue: VirtualVenueStateStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if journal.run_id != run_id or journal.config_hash != policy.config_hash:
            raise E1EngineError("engine/journal identity mismatch")
        if venue.config_hash != policy.config_hash:
            raise E1EngineError("engine/venue config mismatch")
        self.run_id = run_id
        self.policy = policy
        self.journal = journal
        self.venue = venue
        self.phase = EnginePhase.BOOT_RECONCILE_REQUIRED
        self._operation_lock = RLock()
        self._journal_preexisting = not journal.is_new
        issuer_key = object()
        mutation_key = object()
        venue._bind_executor(mutation_key)
        token_clock = clock or (lambda: datetime.now(UTC))
        self._authority = ShadowTokenAuthority(
            run_id=run_id,
            policy=policy,
            journal=journal,
            issuer_key=issuer_key,
            clock=token_clock,
        )
        self._risk_gate = E1RiskGate(
            run_id=run_id,
            policy=policy,
            journal=journal,
            venue=venue,
            authority=self._authority,
            issuer_key=issuer_key,
        )
        self._executor = ShadowVirtualExecutor(
            authority=self._authority,
            venue=venue,
            mutation_key=mutation_key,
        )

    @_serialized_engine_operation
    def boot_reconcile(self, *, now: datetime | str) -> ReconcileStatus:
        if self.phase is not EnginePhase.BOOT_RECONCILE_REQUIRED:
            raise E1EngineError("boot reconcile may run exactly once per engine instance")
        timestamp = canonical_timestamp(now)
        if not self._journal_preexisting:
            expected = position_digest(None)
            self.journal.append(
                event_type=JournalEventType.RUN_STARTED,
                timestamp=timestamp,
                status_label="E1_RUN_STARTED",
                expected_state_digest=expected,
                observed_state_digest=self.venue.state_digest,
                position_count=self.venue.position_count,
            )
            if self.venue.position is not None:
                self._record_reconcile_mismatch(
                    now=timestamp,
                    reason="INITIAL_VENUE_NOT_FLAT",
                    expected=expected,
                    observed=self.venue.state_digest,
                )
                return ReconcileStatus.MISMATCH_HALTED
            self.phase = EnginePhase.READY_FLAT
            return ReconcileStatus.INITIAL_FLAT_CONFIRMED
        return self._reconcile(now=timestamp, is_restart=True)

    @_serialized_engine_operation
    def reconcile_after_uncertain(self, *, now: datetime | str) -> ReconcileStatus:
        if self.phase is not EnginePhase.RECONCILE_REQUIRED:
            raise E1EngineError("engine is not awaiting reconciliation")
        return self._reconcile(now=canonical_timestamp(now), is_restart=False)

    def _reconcile(self, *, now: str, is_restart: bool) -> ReconcileStatus:
        observed = self.venue.state_digest
        pending = self.journal.unresolved_intents()
        if len(pending) > 1:
            self._record_reconcile_mismatch(
                now=now,
                reason="MULTIPLE_UNRESOLVED_INTENTS",
                expected=self.journal.expected_state_digest,
                observed=observed,
            )
            return ReconcileStatus.MISMATCH_HALTED
        matched_status = ReconcileStatus.MATCHED_STABLE_STATE
        expected = self.journal.expected_state_digest
        source: JournalRecord | None = None
        if pending:
            source = pending[0]
            before = source.state_before_digest
            planned = source.planned_state_digest
            if observed == before:
                matched_status = ReconcileStatus.RECOVERED_NO_EFFECT
                expected = before
            elif observed == planned:
                matched_status = ReconcileStatus.RECOVERED_PLANNED_EFFECT
                expected = planned
            else:
                self._record_reconcile_mismatch(
                    now=now,
                    reason="INTENT_VENUE_STATE_MISMATCH",
                    expected=planned or self.journal.expected_state_digest,
                    observed=observed,
                    source=source,
                )
                return ReconcileStatus.MISMATCH_HALTED
        elif observed != expected:
            self._record_reconcile_mismatch(
                now=now,
                reason="STABLE_VENUE_STATE_MISMATCH",
                expected=expected,
                observed=observed,
            )
            return ReconcileStatus.MISMATCH_HALTED
        self.journal.append(
            event_type=JournalEventType.RECONCILE_MATCHED,
            timestamp=now,
            status_label=matched_status.value,
            expected_state_digest=expected,
            observed_state_digest=observed,
            position_count=self.venue.position_count,
            action=source.action if source else None,
            intent_id=source.intent_id if source else None,
            intent_digest=source.intent_digest if source else None,
            token_id=source.token_id if source else None,
            fault_kind=source.fault_kind if source else FaultKind.NONE,
            state_before_digest=source.state_before_digest if source else expected,
            planned_state_digest=source.planned_state_digest if source else expected,
            pnl_category=source.pnl_category if source else PnlCategory.NOT_APPLICABLE,
            virtual_loss=source.virtual_loss if source else "0",
        )
        if source and source.fault_kind in {
            FaultKind.TIMEOUT,
            FaultKind.UNKNOWN_RESULT,
            FaultKind.NETWORK_ERROR,
            FaultKind.CRASH_MID_VIRTUAL_EXECUTION,
        }:
            self._record_fault_handled(
                now=now,
                fault_kind=source.fault_kind,
                source=source,
            )
        if is_restart and source is not None:
            self._record_fault_handled(
                now=now,
                fault_kind=FaultKind.RESTART_RECONCILE,
                source=source,
            )
        if (
            source is not None
            and source.fault_kind is FaultKind.REJECTED
            and not self.journal.kill_active
            and not self.journal.halted
        ):
            self._append_fake_alert(
                now=now,
                reason="REJECTED_TERMINAL_PERSISTENCE_RECOVERED_NO_RETRY",
            )
            self._append_halt(now=now, reason=KillReason.EXECUTION_REJECTED.value)
        if self.journal.kill_active and not self.journal.halted:
            activation = next(
                record
                for record in reversed(self.journal.records)
                if record.event_type
                in {JournalEventType.KILL_ACTIVATED, JournalEventType.DEADMAN_ACTIVATED}
            )
            if self.venue.position is not None:
                self._append_fake_alert(
                    now=now,
                    reason="STICKY_KILL_RESTART_POSITION_REMAINS_MANUAL_ESCALATION",
                )
            self._append_halt(now=now, reason=activation.status_label)
        if self.journal.kill_active or self.journal.halted:
            self.phase = EnginePhase.HALTED
        else:
            self.phase = EnginePhase.RESTART_ACK_REQUIRED
        return matched_status

    @_serialized_engine_operation
    def acknowledge_restart(
        self, *, now: datetime | str, operator_acknowledged: bool
    ) -> E1CycleResult:
        if self.phase is not EnginePhase.RESTART_ACK_REQUIRED:
            raise E1EngineError("restart acknowledgement is not currently required")
        if operator_acknowledged is not True:
            return self._result(
                status="RESTART_ACK_NOT_PROVIDED",
                reasons=("RESTART_REMAINS_BLOCKED",),
                attempted=False,
                token_issued=False,
            )
        timestamp = canonical_timestamp(now)
        self.journal.append(
            event_type=JournalEventType.RESTART_ACK_RECORDED,
            timestamp=timestamp,
            status_label="OPERATOR_RESTART_ACK_RECORDED",
            expected_state_digest=self.venue.state_digest,
            observed_state_digest=self.venue.state_digest,
            position_count=self.venue.position_count,
        )
        self.phase = (
            EnginePhase.POSITION_OPEN if self.venue.position is not None else EnginePhase.READY_FLAT
        )
        return self._result(
            status="RESTART_ACKNOWLEDGED",
            reasons=(),
            attempted=False,
            token_issued=False,
        )

    @_serialized_engine_operation
    def record_heartbeat(self, *, now: datetime | str) -> E1CycleResult:
        if self.phase not in {EnginePhase.READY_FLAT, EnginePhase.POSITION_OPEN}:
            raise E1EngineError("heartbeat cannot resume a blocked or halted engine")
        timestamp = canonical_timestamp(now)
        self.journal.append(
            event_type=JournalEventType.HEARTBEAT_RECORDED,
            timestamp=timestamp,
            status_label="OPERATOR_HEARTBEAT_ACK_RECORDED",
            expected_state_digest=self.venue.state_digest,
            observed_state_digest=self.venue.state_digest,
            position_count=self.venue.position_count,
        )
        return self._result(
            status="HEARTBEAT_RECORDED",
            reasons=(),
            attempted=False,
            token_issued=False,
        )

    @_serialized_engine_operation
    def record_incident(
        self,
        *,
        now: datetime | str,
        incident_ref: str,
        severity: str,
        reason_code: str,
    ) -> E1CycleResult:
        self.journal.append(
            event_type=JournalEventType.INCIDENT_RECORDED,
            timestamp=canonical_timestamp(now),
            status_label="E1_INCIDENT_RECORDED",
            reason_codes=(reason_code,),
            expected_state_digest=self.journal.expected_state_digest,
            observed_state_digest=self.venue.state_digest,
            position_count=self.venue.position_count,
            incident_ref=incident_ref,
            incident_severity=severity,
        )
        return self._result(
            status="E1_INCIDENT_RECORDED",
            reasons=(reason_code,),
            attempted=False,
            token_issued=False,
        )

    @_serialized_engine_operation
    def record_postmortem(
        self, *, now: datetime | str, incident_ref: str
    ) -> E1CycleResult:
        self.journal.append(
            event_type=JournalEventType.POSTMORTEM_RECORDED,
            timestamp=canonical_timestamp(now),
            status_label="E1_POSTMORTEM_RECORDED",
            expected_state_digest=self.journal.expected_state_digest,
            observed_state_digest=self.venue.state_digest,
            position_count=self.venue.position_count,
            incident_ref=incident_ref,
        )
        return self._result(
            status="E1_POSTMORTEM_RECORDED",
            reasons=(),
            attempted=False,
            token_issued=False,
        )

    @_serialized_engine_operation
    def process_decision(
        self,
        *,
        decision: EngineDecision,
        market: MarketFrame,
        protective_stop_price: Decimal | int | float | str | None = None,
        fault: FaultInjection | None = None,
    ) -> E1CycleResult:
        injected = fault or FaultInjection()
        self._assert_processable_state(market=market)
        if decision.config_hash != self.policy.config_hash:
            return self.activate_kill(
                now=market.evaluation_time,
                reason=KillReason.CONFIG_HASH_MISMATCH,
                market=market,
            )
        if decision.hypothesis_label is not None and not self.policy.hypothesis_registry.contains(
            hypothesis_id=decision.hypothesis_id or "",
            version=decision.hypothesis_version or "",
        ):
            return self.activate_kill(
                now=market.evaluation_time,
                reason=KillReason.SAFETY_VIOLATION,
                market=market,
            )
        if decision.engine_label is EngineLabel.NO_ACTION:
            self.journal.append(
                event_type=JournalEventType.NO_ACTION_RECORDED,
                timestamp=market.evaluation_time,
                status_label="ENGINE_NO_ACTION_TERMINAL",
                reason_codes=(decision.reason_code,),
                expected_state_digest=self.venue.state_digest,
                observed_state_digest=self.venue.state_digest,
                position_count=self.venue.position_count,
                decision_digest=decision.decision_digest,
                hypothesis_label=decision.hypothesis_label,
                hypothesis_id=decision.hypothesis_id,
                hypothesis_version=decision.hypothesis_version,
            )
            return self._result(
                status="ENGINE_NO_ACTION_TERMINAL",
                reasons=(decision.reason_code,),
                attempted=False,
                token_issued=False,
            )
        if decision.engine_label in {
            EngineLabel.ENTRY_BUY_CANDIDATE,
            EngineLabel.ENTRY_SELL_CANDIDATE,
        }:
            return self._process_entry(
                decision=decision,
                market=market,
                protective_stop_price=protective_stop_price,
                fault=injected,
            )
        if decision.engine_label in {
            EngineLabel.EXIT_CANDIDATE,
            EngineLabel.SETTLEMENT_CANDIDATE,
        }:
            return self._process_settlement(decision=decision, market=market, fault=injected)
        raise E1EngineError("unsupported engine decision")

    def _process_entry(
        self,
        *,
        decision: EngineDecision,
        market: MarketFrame,
        protective_stop_price: Decimal | int | float | str | None,
        fault: FaultInjection,
    ) -> E1CycleResult:
        if protective_stop_price is None:
            return self._risk_blocked(
                market=market,
                reasons=("VIRTUAL_PROTECTIVE_STOP_REQUIRED",),
            )
        long_entry = decision.engine_label is EngineLabel.ENTRY_BUY_CANDIDATE
        side = PositionSide.LONG if long_entry else PositionSide.SHORT
        entry_price = market.ask if long_entry else market.bid
        stop = finite_decimal(protective_stop_price, field_name="protective_stop_price")
        intent_id = make_local_id(
            "intent",
            {
                "config_hash": self.policy.config_hash,
                "decision": decision.engine_label.value,
                "run_id": self.run_id,
                "sequence": len(self.journal.records),
                "time": market.evaluation_time,
            },
        )
        position = VirtualPosition(
            position_ref=make_local_id(
                "vposition", {"intent_id": intent_id, "run_id": self.run_id}
            ),
            symbol=market.symbol,
            side=side,
            units=self.policy.fixed_virtual_units,
            entry_price=entry_price,
            protective_stop_price=stop,
        )
        intent = EntryIntent(
            intent_id=intent_id,
            run_id=self.run_id,
            config_hash=self.policy.config_hash,
            created_at=market.evaluation_time,
            position=position,
        )
        token, reasons = self._risk_gate.issue_entry_token(
            intent=intent,
            market=market,
            phase=self.phase,
        )
        if token is None:
            return self._risk_blocked(market=market, reasons=reasons)
        return self._execute_entry(token=token, intent=intent, market=market, fault=fault)

    def _process_settlement(
        self,
        *,
        decision: EngineDecision,
        market: MarketFrame,
        fault: FaultInjection,
        emergency: bool = False,
    ) -> E1CycleResult:
        position = self.venue.position
        if position is None or decision.position_ref != position.position_ref:
            return self._risk_blocked(
                market=market,
                reasons=("POSITION_SPECIFIC_SETTLEMENT_MISMATCH",),
            )
        exit_price = market.bid if position.side is PositionSide.LONG else market.ask
        pnl_category, loss = classify_pnl(position, exit_price)
        intent = SettlementIntent(
            intent_id=make_local_id(
                "intent",
                {
                    "action": GateAction.VIRTUAL_SETTLEMENT.value,
                    "config_hash": self.policy.config_hash,
                    "position_ref": position.position_ref,
                    "run_id": self.run_id,
                    "sequence": len(self.journal.records),
                    "time": market.evaluation_time,
                },
            ),
            run_id=self.run_id,
            config_hash=self.policy.config_hash,
            created_at=market.evaluation_time,
            position_ref=position.position_ref,
            exit_price=exit_price,
            pnl_category=pnl_category,
            virtual_loss=loss,
        )
        token, reasons = self._risk_gate.issue_settlement_token(
            intent=intent,
            market=market,
            phase=self.phase,
            emergency=emergency,
        )
        if token is None:
            return self._risk_blocked(market=market, reasons=reasons)
        return self._execute_settlement(token=token, intent=intent, market=market, fault=fault)

    def _execute_entry(
        self,
        *,
        token: ShadowGateToken,
        intent: EntryIntent,
        market: MarketFrame,
        fault: FaultInjection,
    ) -> E1CycleResult:
        before = self.venue.state_digest
        planned = position_digest(intent.position)
        self._prepare_and_start(
            token=token,
            action=GateAction.VIRTUAL_ENTRY,
            intent_id=intent.intent_id,
            intent_digest=intent.intent_digest,
            market=market,
            fault=fault,
            before=before,
            planned=planned,
            pnl_category=PnlCategory.NOT_APPLICABLE,
            virtual_loss=Decimal("0"),
        )
        try:
            result = self._executor.execute_entry(
                token=token,
                intent=intent,
                fault=fault,
            )
        except E1PersistenceError as error:
            self._record_venue_persistence_unknown(
                token=token,
                action=GateAction.VIRTUAL_ENTRY,
                intent_id=intent.intent_id,
                intent_digest=intent.intent_digest,
                market=market,
                fault=fault,
                before=before,
                planned=planned,
                pnl_category=PnlCategory.NOT_APPLICABLE,
                virtual_loss=Decimal("0"),
            )
            raise E1EngineError("virtual venue persistence outcome is unknown") from error
        return self._finish_execution(
            token=token,
            action=GateAction.VIRTUAL_ENTRY,
            intent_id=intent.intent_id,
            intent_digest=intent.intent_digest,
            market=market,
            fault=fault,
            before=before,
            planned=planned,
            result=result,
            pnl_category=PnlCategory.NOT_APPLICABLE,
            virtual_loss=Decimal("0"),
        )

    def _execute_settlement(
        self,
        *,
        token: ShadowGateToken,
        intent: SettlementIntent,
        market: MarketFrame,
        fault: FaultInjection,
    ) -> E1CycleResult:
        before = self.venue.state_digest
        planned = position_digest(None)
        self._prepare_and_start(
            token=token,
            action=GateAction.VIRTUAL_SETTLEMENT,
            intent_id=intent.intent_id,
            intent_digest=intent.intent_digest,
            market=market,
            fault=fault,
            before=before,
            planned=planned,
            pnl_category=intent.pnl_category,
            virtual_loss=intent.virtual_loss,
        )
        try:
            result = self._executor.execute_settlement(
                token=token,
                intent=intent,
                fault=fault,
            )
        except E1PersistenceError as error:
            self._record_venue_persistence_unknown(
                token=token,
                action=GateAction.VIRTUAL_SETTLEMENT,
                intent_id=intent.intent_id,
                intent_digest=intent.intent_digest,
                market=market,
                fault=fault,
                before=before,
                planned=planned,
                pnl_category=intent.pnl_category,
                virtual_loss=intent.virtual_loss,
            )
            raise E1EngineError("virtual venue persistence outcome is unknown") from error
        return self._finish_execution(
            token=token,
            action=GateAction.VIRTUAL_SETTLEMENT,
            intent_id=intent.intent_id,
            intent_digest=intent.intent_digest,
            market=market,
            fault=fault,
            before=before,
            planned=planned,
            result=result,
            pnl_category=intent.pnl_category,
            virtual_loss=intent.virtual_loss,
        )

    def _prepare_and_start(
        self,
        *,
        token: ShadowGateToken,
        action: GateAction,
        intent_id: str,
        intent_digest: str,
        market: MarketFrame,
        fault: FaultInjection,
        before: str,
        planned: str,
        pnl_category: PnlCategory,
        virtual_loss: Decimal,
    ) -> None:
        try:
            self._authority.commit_intent(
                token=token,
                durable_append=lambda: self.journal.append(
                    event_type=JournalEventType.INTENT_PREPARED,
                    timestamp=market.evaluation_time,
                    status_label="DURABLE_INTENT_PREPARED_BEFORE_VIRTUAL_EFFECT",
                    expected_state_digest=before,
                    position_count=self.venue.position_count,
                    action=action,
                    intent_id=intent_id,
                    intent_digest=intent_digest,
                    token_id=token.token_id,
                    fault_kind=fault.kind,
                    state_before_digest=before,
                    planned_state_digest=planned,
                    observed_state_digest=before,
                    pnl_category=pnl_category,
                    virtual_loss=canonical_decimal(virtual_loss),
                ),
            )
            self.journal.append(
                event_type=JournalEventType.VIRTUAL_EXECUTION_STARTED,
                timestamp=market.evaluation_time,
                status_label="VIRTUAL_EXECUTION_STARTED_ONCE",
                expected_state_digest=before,
                position_count=self.venue.position_count,
                action=action,
                intent_id=intent_id,
                intent_digest=intent_digest,
                token_id=token.token_id,
                fault_kind=fault.kind,
                state_before_digest=before,
                planned_state_digest=planned,
                observed_state_digest=before,
                pnl_category=pnl_category,
                virtual_loss=canonical_decimal(virtual_loss),
            )
        except E1PersistenceError as error:
            self.phase = EnginePhase.HALTED
            raise E1EngineError("durable intent journal failed before virtual execution") from error

    def _finish_execution(
        self,
        *,
        token: ShadowGateToken,
        action: GateAction,
        intent_id: str,
        intent_digest: str,
        market: MarketFrame,
        fault: FaultInjection,
        before: str,
        planned: str,
        result: VirtualExecutionResult,
        pnl_category: PnlCategory,
        virtual_loss: Decimal,
    ) -> E1CycleResult:
        if result.outcome is ExecutionOutcome.ACCEPTED:
            if result.observed_state_digest != planned:
                self._record_reconcile_mismatch(
                    now=market.evaluation_time,
                    reason="ACCEPTED_RESULT_STATE_MISMATCH",
                    expected=planned,
                    observed=result.observed_state_digest,
                )
                return self._result(
                    status="RECONCILE_MISMATCH_HALTED",
                    reasons=("ACCEPTED_RESULT_STATE_MISMATCH",),
                    attempted=True,
                    token_issued=True,
                )
            try:
                self.journal.append(
                    event_type=JournalEventType.VIRTUAL_EXECUTION_CONFIRMED,
                    timestamp=market.evaluation_time,
                    status_label="VIRTUAL_EFFECT_CONFIRMED",
                    expected_state_digest=planned,
                    position_count=result.position_count,
                    action=action,
                    intent_id=intent_id,
                    intent_digest=intent_digest,
                    token_id=token.token_id,
                    execution_outcome=result.outcome,
                    fault_kind=fault.kind,
                    state_before_digest=before,
                    planned_state_digest=planned,
                    observed_state_digest=result.observed_state_digest,
                    pnl_category=pnl_category,
                    virtual_loss=canonical_decimal(virtual_loss),
                )
            except E1PersistenceError as error:
                self.phase = EnginePhase.RECONCILE_REQUIRED
                raise E1EngineError(
                    "virtual effect occurred but terminal journal persistence failed"
                ) from error
            self.phase = (
                EnginePhase.POSITION_OPEN
                if self.venue.position is not None
                else EnginePhase.READY_FLAT
            )
            return self._result(
                status="VIRTUAL_EXECUTION_CONFIRMED",
                reasons=(),
                attempted=True,
                token_issued=True,
            )
        if result.outcome is ExecutionOutcome.REJECTED:
            try:
                self.journal.append(
                    event_type=JournalEventType.VIRTUAL_EXECUTION_REJECTED,
                    timestamp=market.evaluation_time,
                    status_label="VIRTUAL_EXECUTION_REJECTED_NO_RETRY",
                    reason_codes=("NO_RETRY",),
                    expected_state_digest=before,
                    position_count=result.position_count,
                    action=action,
                    intent_id=intent_id,
                    intent_digest=intent_digest,
                    token_id=token.token_id,
                    execution_outcome=result.outcome,
                    fault_kind=fault.kind,
                    state_before_digest=before,
                    planned_state_digest=planned,
                    observed_state_digest=result.observed_state_digest,
                    pnl_category=pnl_category,
                    virtual_loss=canonical_decimal(virtual_loss),
                )
            except E1PersistenceError as error:
                self.phase = EnginePhase.RECONCILE_REQUIRED
                raise E1EngineError(
                    "virtual rejection occurred but terminal journal persistence failed"
                ) from error
            self._append_halt(
                now=market.evaluation_time,
                reason=KillReason.EXECUTION_REJECTED.value,
            )
            return self._result(
                status="VIRTUAL_EXECUTION_REJECTED_NO_RETRY",
                reasons=("NO_RETRY",),
                attempted=True,
                token_issued=True,
            )
        try:
            self.journal.append(
                event_type=JournalEventType.VIRTUAL_EXECUTION_UNCERTAIN,
                timestamp=market.evaluation_time,
                status_label="VIRTUAL_EXECUTION_UNCERTAIN_RECONCILE_REQUIRED",
                reason_codes=("NO_RETRY", "NEW_ENTRY_BLOCKED"),
                expected_state_digest=before,
                position_count=result.position_count,
                action=action,
                intent_id=intent_id,
                intent_digest=intent_digest,
                token_id=token.token_id,
                execution_outcome=result.outcome,
                fault_kind=fault.kind,
                state_before_digest=before,
                planned_state_digest=planned,
                observed_state_digest=result.observed_state_digest,
                pnl_category=pnl_category,
                virtual_loss=canonical_decimal(virtual_loss),
            )
        except E1PersistenceError as error:
            self.phase = EnginePhase.RECONCILE_REQUIRED
            raise E1EngineError(
                "virtual outcome is unknown and terminal journal persistence failed"
            ) from error
        self.journal.append(
            event_type=JournalEventType.FAKE_CRITICAL_ALERT,
            timestamp=market.evaluation_time,
            status_label="FAKE_CRITICAL_ALERT_RECONCILE_REQUIRED",
            reason_codes=(result.outcome.value,),
            expected_state_digest=before,
            position_count=result.position_count,
            action=action,
            intent_id=intent_id,
            intent_digest=intent_digest,
            token_id=token.token_id,
            fault_kind=fault.kind,
            state_before_digest=before,
            planned_state_digest=planned,
            observed_state_digest=result.observed_state_digest,
            pnl_category=pnl_category,
            virtual_loss=canonical_decimal(virtual_loss),
        )
        self.phase = EnginePhase.RECONCILE_REQUIRED
        return self._result(
            status="VIRTUAL_EXECUTION_UNCERTAIN_RECONCILE_REQUIRED",
            reasons=("NO_RETRY", "NEW_ENTRY_BLOCKED"),
            attempted=True,
            token_issued=True,
        )

    def _record_venue_persistence_unknown(
        self,
        *,
        token: ShadowGateToken,
        action: GateAction,
        intent_id: str,
        intent_digest: str,
        market: MarketFrame,
        fault: FaultInjection,
        before: str,
        planned: str,
        pnl_category: PnlCategory,
        virtual_loss: Decimal,
    ) -> None:
        try:
            self.journal.append(
                event_type=JournalEventType.VIRTUAL_EXECUTION_UNCERTAIN,
                timestamp=market.evaluation_time,
                status_label="VIRTUAL_VENUE_PERSISTENCE_UNKNOWN_RECONCILE_REQUIRED",
                reason_codes=("NO_RETRY", "NEW_ENTRY_BLOCKED"),
                expected_state_digest=before,
                position_count=self.venue.position_count,
                action=action,
                intent_id=intent_id,
                intent_digest=intent_digest,
                token_id=token.token_id,
                execution_outcome=ExecutionOutcome.UNKNOWN,
                fault_kind=fault.kind,
                state_before_digest=before,
                planned_state_digest=planned,
                observed_state_digest=self.venue.state_digest,
                pnl_category=pnl_category,
                virtual_loss=canonical_decimal(virtual_loss),
            )
            self._append_fake_alert(
                now=market.evaluation_time,
                reason="VIRTUAL_VENUE_PERSISTENCE_UNKNOWN",
            )
            self.phase = EnginePhase.RECONCILE_REQUIRED
        except E1PersistenceError:
            self.phase = EnginePhase.HALTED

    @_serialized_engine_operation
    def activate_kill(
        self,
        *,
        now: datetime | str,
        reason: KillReason,
        market: MarketFrame | None = None,
        fault: FaultInjection | None = None,
        deadman: bool = False,
    ) -> E1CycleResult:
        timestamp = canonical_timestamp(now)
        injected = fault or FaultInjection()
        event_type = (
            JournalEventType.DEADMAN_ACTIVATED
            if deadman
            else JournalEventType.KILL_ACTIVATED
        )
        if self.journal.kill_active:
            self.phase = EnginePhase.HALTED
            return self._result(
                status="KILL_ALREADY_ACTIVE_NO_SECOND_ATTEMPT",
                reasons=("NO_RETRY", "STICKY_KILL_ACTIVE"),
                attempted=False,
                token_issued=False,
            )
        if self.journal.halted:
            self.phase = EnginePhase.HALTED
            return self._result(
                status="ENGINE_ALREADY_HALTED_NO_FURTHER_ATTEMPT",
                reasons=("NO_RETRY", "STICKY_HALT_ACTIVE"),
                attempted=False,
                token_issued=False,
            )
        if self.journal.unresolved_intents() or self.phase in {
            EnginePhase.BOOT_RECONCILE_REQUIRED,
            EnginePhase.RESTART_ACK_REQUIRED,
            EnginePhase.RECONCILE_REQUIRED,
            EnginePhase.HALTED,
        }:
            self.phase = EnginePhase.HALTED
            try:
                self.journal.append(
                    event_type=event_type,
                    timestamp=timestamp,
                    status_label=reason.value,
                    reason_codes=(
                        "NEW_ENTRY_BLOCKED_IMMEDIATELY",
                        "UNRECONCILED_STATE_NO_EXECUTION_ATTEMPT",
                    ),
                    expected_state_digest=self.journal.expected_state_digest,
                    observed_state_digest=self.venue.state_digest,
                    position_count=self.venue.position_count,
                )
                self._append_fake_alert(
                    now=timestamp,
                    reason="UNRECONCILED_STATE_KILL_REQUIRES_RESTART_RECONCILE",
                )
                self._append_halt(now=timestamp, reason=reason.value)
            except E1PersistenceError as error:
                raise E1EngineError(
                    "blocked-state kill could not be durably completed"
                ) from error
            return self._result(
                status="RECONCILE_REQUIRED_DURABLE_KILL_NO_ATTEMPT",
                reasons=("NO_RETRY", "UNRESOLVED_OR_UNRECONCILED_STATE"),
                attempted=False,
                token_issued=False,
            )
        try:
            self.journal.append(
                event_type=event_type,
                timestamp=timestamp,
                status_label=reason.value,
                reason_codes=("NEW_ENTRY_BLOCKED_IMMEDIATELY",),
                expected_state_digest=self.journal.expected_state_digest,
                observed_state_digest=self.venue.state_digest,
                position_count=self.venue.position_count,
            )
        except E1PersistenceError as error:
            self.phase = EnginePhase.HALTED
            raise E1EngineError("kill activation could not be durably recorded") from error
        if self.venue.position is None:
            self._append_halt(now=timestamp, reason=reason.value)
            return self._result(
                status="KILL_HALTED_FLAT",
                reasons=(reason.value,),
                attempted=False,
                token_issued=False,
            )
        if market is None:
            self._append_fake_alert(now=timestamp, reason="KILL_FLATTEN_MARKET_FRAME_MISSING")
            self._append_halt(now=timestamp, reason=reason.value)
            return self._result(
                status="KILL_HALTED_ESCALATION_REQUIRED",
                reasons=("KILL_FLATTEN_MARKET_FRAME_MISSING",),
                attempted=False,
                token_issued=False,
            )
        position = self.venue.position
        assert position is not None
        decision = EngineDecision(
            engine_label=EngineLabel.SETTLEMENT_CANDIDATE,
            config_hash=self.policy.config_hash,
            reason_code="KILL_POSITION_SPECIFIC_FLATTEN",
            position_ref=position.position_ref,
        )
        try:
            result = self._process_settlement(
                decision=decision,
                market=market,
                fault=injected,
                emergency=True,
            )
        except SimulatedShadowCrash:
            raise
        except E1EngineError:
            self._append_fake_alert(now=timestamp, reason="KILL_FLATTEN_PERSISTENCE_UNKNOWN")
            self._append_halt(now=timestamp, reason=reason.value)
            settlement_started = any(
                record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
                and record.action is GateAction.VIRTUAL_SETTLEMENT
                for record in self.journal.records
            )
            return self._result(
                status="KILL_HALTED_ESCALATION_REQUIRED",
                reasons=("KILL_FLATTEN_PERSISTENCE_UNKNOWN", "NO_RETRY"),
                attempted=settlement_started,
                token_issued=True,
            )
        if self.venue.position is not None or result.status != "VIRTUAL_EXECUTION_CONFIRMED":
            self._append_fake_alert(now=timestamp, reason="KILL_FLATTEN_NOT_CONFIRMED_NO_RETRY")
        self._append_halt(now=timestamp, reason=reason.value)
        return self._result(
            status=(
                "KILL_FLATTENED_ONCE_THEN_HALTED"
                if self.venue.position is None
                else "KILL_HALTED_ESCALATION_REQUIRED"
            ),
            reasons=(reason.value, "NO_RETRY"),
            attempted=result.virtual_execution_attempted,
            token_issued=result.token_issued,
        )

    @_serialized_engine_operation
    def check_deadman(
        self,
        *,
        now: datetime | str,
        market: MarketFrame | None = None,
        fault: FaultInjection | None = None,
    ) -> E1CycleResult:
        timestamp = canonical_timestamp(now)
        heartbeat = self.journal.last_heartbeat
        expired = heartbeat is None
        if heartbeat is not None:
            elapsed = parse_timestamp(timestamp) - parse_timestamp(heartbeat)
            expired = elapsed.total_seconds() < 0 or (
                elapsed.total_seconds() > self.policy.heartbeat_timeout_seconds
            )
        if not expired:
            return self._result(
                status="DEADMAN_HEARTBEAT_WITHIN_SLA",
                reasons=(),
                attempted=False,
                token_issued=False,
            )
        return self.activate_kill(
            now=timestamp,
            reason=KillReason.DEADMAN_HEARTBEAT_EXPIRED,
            market=market,
            fault=fault,
            deadman=True,
        )

    def _assert_processable_state(self, *, market: MarketFrame) -> None:
        if self.journal.kill_active or self.journal.halted:
            self.phase = EnginePhase.HALTED
            raise E1EngineError("sticky halt/kill blocks processing")
        if self.phase not in {EnginePhase.READY_FLAT, EnginePhase.POSITION_OPEN}:
            raise E1EngineError("engine must reconcile and acknowledge before processing")
        if self.journal.unresolved_intents():
            self.phase = EnginePhase.RECONCILE_REQUIRED
            raise E1EngineError("unresolved intent blocks processing")
        if self.journal.expected_state_digest != self.venue.state_digest:
            self._record_reconcile_mismatch(
                now=market.evaluation_time,
                reason="PRE_DECISION_STATE_MISMATCH",
                expected=self.journal.expected_state_digest,
                observed=self.venue.state_digest,
            )
            raise E1EngineError("pre-decision reconcile mismatch")

    def _risk_blocked(
        self, *, market: MarketFrame, reasons: tuple[str, ...]
    ) -> E1CycleResult:
        self.journal.append(
            event_type=JournalEventType.NO_ACTION_RECORDED,
            timestamp=market.evaluation_time,
            status_label="RISK_GATE_BLOCKED_NO_ACTION",
            reason_codes=reasons,
            expected_state_digest=self.venue.state_digest,
            observed_state_digest=self.venue.state_digest,
            position_count=self.venue.position_count,
        )
        return self._result(
            status="RISK_GATE_BLOCKED_NO_ACTION",
            reasons=reasons,
            attempted=False,
            token_issued=False,
        )

    def _record_reconcile_mismatch(
        self,
        *,
        now: str,
        reason: str,
        expected: str,
        observed: str,
        source: JournalRecord | None = None,
    ) -> None:
        self.journal.append(
            event_type=JournalEventType.RECONCILE_MISMATCH,
            timestamp=now,
            status_label=ReconcileStatus.MISMATCH_HALTED.value,
            reason_codes=(reason,),
            expected_state_digest=expected,
            observed_state_digest=observed,
            position_count=self.venue.position_count,
            action=source.action if source else None,
            intent_id=source.intent_id if source else None,
            intent_digest=source.intent_digest if source else None,
            token_id=source.token_id if source else None,
            fault_kind=source.fault_kind if source else FaultKind.NONE,
            state_before_digest=source.state_before_digest if source else expected,
            planned_state_digest=source.planned_state_digest if source else expected,
            pnl_category=source.pnl_category if source else PnlCategory.NOT_APPLICABLE,
            virtual_loss=source.virtual_loss if source else "0",
        )
        self._append_fake_alert(now=now, reason=reason)
        self._append_halt(now=now, reason=KillReason.RECONCILE_MISMATCH.value)

    def _record_fault_handled(
        self,
        *,
        now: str,
        fault_kind: FaultKind,
        source: JournalRecord,
    ) -> None:
        self.journal.append(
            event_type=JournalEventType.FAULT_HANDLED,
            timestamp=now,
            status_label="FAULT_HANDLED_WITHOUT_RETRY",
            reason_codes=(fault_kind.value,),
            expected_state_digest=self.venue.state_digest,
            observed_state_digest=self.venue.state_digest,
            position_count=self.venue.position_count,
            action=source.action,
            intent_id=source.intent_id,
            intent_digest=source.intent_digest,
            token_id=source.token_id,
            fault_kind=fault_kind,
            state_before_digest=source.state_before_digest,
            planned_state_digest=source.planned_state_digest,
            pnl_category=source.pnl_category,
            virtual_loss=source.virtual_loss,
        )

    def _append_fake_alert(self, *, now: str, reason: str) -> None:
        self.journal.append(
            event_type=JournalEventType.FAKE_CRITICAL_ALERT,
            timestamp=now,
            status_label="FAKE_CRITICAL_ALERT_RECORDED",
            reason_codes=(reason,),
            expected_state_digest=self.journal.expected_state_digest,
            observed_state_digest=self.venue.state_digest,
            position_count=self.venue.position_count,
        )

    def _append_halt(self, *, now: str, reason: str) -> None:
        self.journal.append(
            event_type=JournalEventType.HALTED,
            timestamp=now,
            status_label="ENGINE_HALTED_STICKY",
            reason_codes=(reason,),
            expected_state_digest=self.journal.expected_state_digest,
            observed_state_digest=self.venue.state_digest,
            position_count=self.venue.position_count,
        )
        self.phase = EnginePhase.HALTED

    def _result(
        self,
        *,
        status: str,
        reasons: tuple[str, ...],
        attempted: bool,
        token_issued: bool,
    ) -> E1CycleResult:
        return E1CycleResult(
            status=status,
            phase=self.phase,
            reason_codes=reasons,
            virtual_execution_attempted=attempted,
            token_issued=token_issued,
        )


def build_e1_shadow_engine(
    *,
    output_root: Path,
    run_id: str,
    policy: E1Policy | None = None,
    clock: Callable[[], datetime] | None = None,
) -> E1ShadowFullAutoEngine:
    """Create the supported public E1 engine with isolated local persistence."""

    if tuple(output_root.parts[-2:]) != ("shadow_exports", "e1"):
        raise E1EngineError("public E1 output_root must end with shadow_exports/e1")
    try:
        validate_safe_local_id(run_id, field_name="run_id")
    except ValueError as error:
        raise E1EngineError("public E1 run_id must be a safe local identifier") from error
    if any(candidate.is_symlink() for candidate in (output_root, *output_root.parents)):
        raise E1EngineError("public E1 output_root ancestors cannot be symlinks")
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        resolved_output_root = output_root.resolve(strict=True)
    except OSError as error:
        raise E1EngineError("public E1 output_root cannot be prepared") from error
    active_policy = policy or E1Policy()
    run_root = resolved_output_root / run_id
    if run_root.is_symlink():
        raise E1EngineError("public E1 run root cannot be a symlink")
    try:
        run_root.mkdir(parents=False, exist_ok=True)
        resolved_run_root = run_root.resolve(strict=True)
    except OSError as error:
        raise E1EngineError("public E1 run root cannot be prepared") from error
    if resolved_run_root.parent != resolved_output_root:
        raise E1EngineError("public E1 run root escapes output_root")
    journal = ShadowIntentJournal(
        root=resolved_run_root,
        path=resolved_run_root / "intent_journal.jsonl",
        run_id=run_id,
        config_hash=active_policy.config_hash,
    )
    venue = VirtualVenueStateStore(
        root=resolved_run_root,
        path=resolved_run_root / "virtual_venue_state.json",
        config_hash=active_policy.config_hash,
    )
    return E1ShadowFullAutoEngine(
        run_id=run_id,
        policy=active_policy,
        journal=journal,
        venue=venue,
        clock=clock,
    )
