"""Strict multi-run evidence accounting for the E1 -> E2 review gate.

The pre-registered thresholds are not caller-configurable.  A complete report is
still review-only: it never starts E2 and never grants any live capability.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.shadow.e1.contracts import (
    E1ContractError,
    E1Policy,
    EngineDecision,
    EngineLabel,
    ExecutionOutcome,
    FaultKind,
    GateAction,
    KillReason,
    PnlCategory,
    parse_timestamp,
    shadow_safety_flags,
)
from app.shadow.e1.persistence import JournalEventType, JournalRecord, ShadowIntentJournal


class E1GateStatus(str, Enum):
    IMPLEMENTED_NOT_GATE_PASSED = "E1_IMPLEMENTED_NOT_GATE_PASSED"
    EVIDENCE_COMPLETE_REVIEW_REQUIRED = "E1_EVIDENCE_COMPLETE_E2_REVIEW_REQUIRED"


REQUIRED_FAULT_KINDS = (
    FaultKind.TIMEOUT,
    FaultKind.UNKNOWN_RESULT,
    FaultKind.NETWORK_ERROR,
    FaultKind.CRASH_MID_VIRTUAL_EXECUTION,
    FaultKind.RESTART_RECONCILE,
)


@dataclass(frozen=True)
class E1GateThresholds:
    minimum_calendar_days: int = 14
    minimum_business_days: int = 10
    minimum_virtual_entries: int = 100
    minimum_virtual_settlements: int = 100
    minimum_no_action_events: int = 300
    minimum_each_fault_handled: int = 5
    minimum_kill_tests: int = 3
    minimum_deadman_tests: int = 3
    maximum_high_incidents: int = 0
    maximum_medium_incidents: int = 2

    def __post_init__(self) -> None:
        actual = (
            self.minimum_calendar_days,
            self.minimum_business_days,
            self.minimum_virtual_entries,
            self.minimum_virtual_settlements,
            self.minimum_no_action_events,
            self.minimum_each_fault_handled,
            self.minimum_kill_tests,
            self.minimum_deadman_tests,
            self.maximum_high_incidents,
            self.maximum_medium_incidents,
        )
        expected = (14, 10, 100, 100, 300, 5, 3, 3, 0, 2)
        if actual != expected:
            raise ValueError("E1 gate thresholds are frozen and cannot be relaxed or changed")


@dataclass(frozen=True)
class E1AuditSummary:
    durable_intent_count: int
    consumed_shadow_token_count: int
    virtual_execution_count: int
    unique_intent_count: int
    unique_token_count: int
    virtual_entry_effect_count: int
    virtual_settlement_effect_count: int
    no_action_count: int
    reconcile_mismatch_count: int
    unresolved_intent_count: int
    safety_violation_count: int
    kill_test_count: int
    deadman_test_count: int
    fault_handled_counts: tuple[tuple[str, int], ...]
    cardinality_invariant_ok: bool
    control_exercise_invariant_ok: bool = True
    fault_exercise_invariant_ok: bool = True
    no_action_evidence_invariant_ok: bool = True
    actual_post_count: int = 0
    live_permission_granted: bool = False

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class E1EvidenceWindow:
    first_event_at: str | None
    last_event_at: str | None
    calendar_days: int
    business_days: int
    high_incidents: int
    medium_incidents: int
    incomplete_medium_postmortem_refs: tuple[str, ...]
    incident_evidence_invariant_ok: bool = True

    @property
    def all_medium_incidents_have_postmortems(self) -> bool:
        return not self.incomplete_medium_postmortem_refs


@dataclass(frozen=True)
class E1GateReport:
    status: E1GateStatus
    blockers: tuple[str, ...]
    audit: E1AuditSummary
    window: E1EvidenceWindow
    thresholds: E1GateThresholds
    run_count: int
    config_hash: str | None
    e2_review_required: bool = True
    e2_execution_permission: bool = False
    e3_or_live_permission: bool = False
    performance_proof_status: bool = False

    def __bool__(self) -> bool:
        return False


def _correlation_key(record: JournalRecord) -> tuple[object, ...]:
    return (
        record.intent_id,
        record.intent_digest,
        record.token_id,
        record.action,
        record.state_before_digest,
        record.planned_state_digest,
        record.fault_kind,
        record.pnl_category,
        record.virtual_loss,
    )


def _intent_binding_key(record: JournalRecord) -> tuple[object, ...]:
    return (
        record.intent_id,
        record.intent_digest,
        record.token_id,
        record.action,
        record.state_before_digest,
        record.planned_state_digest,
        record.pnl_category,
        record.virtual_loss,
    )


def _lifecycle_contract_ok(
    *,
    prepared: JournalRecord,
    started: JournalRecord,
    resolved: JournalRecord,
    uncertain_rows: list[JournalRecord],
) -> tuple[bool, bool]:
    """Return exact lifecycle validity and whether one virtual effect occurred."""

    if not prepared.intent_id or not prepared.token_id:
        return False, False
    if not (prepared.sequence < started.sequence < resolved.sequence):
        return False, False
    if not (
        _correlation_key(prepared)
        == _correlation_key(started)
        == _correlation_key(resolved)
    ):
        return False, False
    if prepared.state_before_digest == prepared.planned_state_digest:
        return False, False
    before = prepared.state_before_digest
    planned = prepared.planned_state_digest
    if before is None or planned is None:
        return False, False
    before_count = 0 if prepared.action is GateAction.VIRTUAL_ENTRY else 1
    effect_count = 1 - before_count
    if not (
        prepared.status_label == "DURABLE_INTENT_PREPARED_BEFORE_VIRTUAL_EFFECT"
        and started.status_label == "VIRTUAL_EXECUTION_STARTED_ONCE"
        and prepared.execution_outcome is None
        and started.execution_outcome is None
        and prepared.expected_state_digest == before
        and prepared.observed_state_digest == before
        and started.expected_state_digest == before
        and started.observed_state_digest == before
        and prepared.position_count == before_count
        and started.position_count == before_count
    ):
        return False, False

    if len(uncertain_rows) > 1:
        return False, False
    if uncertain_rows:
        uncertain = uncertain_rows[0]
        expected_uncertain_outcomes = {
            FaultKind.NONE: ExecutionOutcome.UNKNOWN,
            FaultKind.TIMEOUT: ExecutionOutcome.TIMEOUT,
            FaultKind.UNKNOWN_RESULT: ExecutionOutcome.UNKNOWN,
            FaultKind.NETWORK_ERROR: ExecutionOutcome.NETWORK_ERROR,
            FaultKind.PARTIAL_FILL: ExecutionOutcome.PARTIAL_FILL,
        }
        if not (
            started.sequence < uncertain.sequence < resolved.sequence
            and _correlation_key(uncertain) == _correlation_key(prepared)
            and uncertain.status_label
            == "VIRTUAL_EXECUTION_UNCERTAIN_RECONCILE_REQUIRED"
            and uncertain.execution_outcome
            is expected_uncertain_outcomes.get(uncertain.fault_kind)
            and uncertain.expected_state_digest == before
        ):
            return False, False

    if resolved.event_type is JournalEventType.VIRTUAL_EXECUTION_CONFIRMED:
        valid = bool(
            not uncertain_rows
            and resolved.status_label == "VIRTUAL_EFFECT_CONFIRMED"
            and resolved.execution_outcome is ExecutionOutcome.ACCEPTED
            and resolved.fault_kind is FaultKind.NONE
            and resolved.expected_state_digest == planned
            and resolved.observed_state_digest == planned
            and resolved.position_count == effect_count
        )
        return valid, valid
    if resolved.event_type is JournalEventType.VIRTUAL_EXECUTION_REJECTED:
        valid = bool(
            not uncertain_rows
            and resolved.status_label == "VIRTUAL_EXECUTION_REJECTED_NO_RETRY"
            and resolved.execution_outcome is ExecutionOutcome.REJECTED
            and resolved.fault_kind is FaultKind.REJECTED
            and resolved.expected_state_digest == before
            and resolved.observed_state_digest == before
            and resolved.position_count == before_count
        )
        return valid, False
    if resolved.event_type is JournalEventType.RECONCILE_MATCHED:
        if resolved.execution_outcome is not None:
            return False, False
        if resolved.status_label == "RECOVERED_PLANNED_EFFECT":
            valid = bool(
                resolved.expected_state_digest == planned
                and resolved.observed_state_digest == planned
                and resolved.position_count == effect_count
            )
            return valid, valid
        if resolved.status_label == "RECOVERED_NO_EFFECT":
            valid = bool(
                resolved.expected_state_digest == before
                and resolved.observed_state_digest == before
                and resolved.position_count == before_count
            )
            return valid, False
        return False, False
    if resolved.event_type is JournalEventType.RECONCILE_MISMATCH:
        valid = bool(
            resolved.execution_outcome is None
            and resolved.status_label == "MISMATCH_HALTED"
            and resolved.expected_state_digest == planned
            and resolved.observed_state_digest not in {before, planned}
        )
        return valid, False
    return False, False


def _control_exercise_counts(
    records: tuple[JournalRecord, ...],
) -> tuple[int, int, bool]:
    """Count one successful position-flattening control exercise per run."""

    activations = [
        record
        for record in records
        if record.event_type
        in {JournalEventType.KILL_ACTIVATED, JournalEventType.DEADMAN_ACTIVATED}
    ]
    if not activations:
        return 0, 0, True
    if len(activations) != 1:
        return 0, 0, False
    activation = activations[0]
    expected_statuses = (
        {
            reason.value
            for reason in KillReason
            if reason is not KillReason.DEADMAN_HEARTBEAT_EXPIRED
        }
        if activation.event_type is JournalEventType.KILL_ACTIVATED
        else {KillReason.DEADMAN_HEARTBEAT_EXPIRED.value}
    )
    if not (
        activation.status_label in expected_statuses
        and activation.reason_codes == ("NEW_ENTRY_BLOCKED_IMMEDIATELY",)
        and activation.expected_state_digest == activation.observed_state_digest
        and activation.action is None
        and activation.intent_id is None
        and activation.intent_digest is None
        and activation.token_id is None
        and activation.execution_outcome is None
        and activation.fault_kind is FaultKind.NONE
        and activation.state_before_digest is None
        and activation.planned_state_digest is None
        and activation.pnl_category is PnlCategory.NOT_APPLICABLE
        and activation.virtual_loss == "0"
        and activation.position_count == 1
    ):
        return 0, 0, False
    later_starts = [
        record
        for record in records
        if record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
        and record.sequence > activation.sequence
    ]
    if len(later_starts) != 1 or later_starts[0].action is not GateAction.VIRTUAL_SETTLEMENT:
        return 0, 0, False
    started = later_starts[0]
    prepared_rows = [
        record
        for record in records
        if record.event_type is JournalEventType.INTENT_PREPARED
        and record.intent_id == started.intent_id
    ]
    resolved_rows = [
        record
        for record in records
        if record.event_type
        in {
            JournalEventType.VIRTUAL_EXECUTION_CONFIRMED,
            JournalEventType.VIRTUAL_EXECUTION_REJECTED,
            JournalEventType.RECONCILE_MATCHED,
            JournalEventType.RECONCILE_MISMATCH,
        }
        and record.intent_id == started.intent_id
    ]
    uncertain_rows = [
        record
        for record in records
        if record.event_type is JournalEventType.VIRTUAL_EXECUTION_UNCERTAIN
        and record.intent_id == started.intent_id
    ]
    if len(prepared_rows) != 1 or len(resolved_rows) != 1:
        return 0, 0, False
    prepared = prepared_rows[0]
    resolved = resolved_rows[0]
    lifecycle_ok, effect_confirmed = _lifecycle_contract_ok(
        prepared=prepared,
        started=started,
        resolved=resolved,
        uncertain_rows=uncertain_rows,
    )
    later_halts = [
        record
        for record in records
        if record.event_type is JournalEventType.HALTED
        and record.sequence > resolved.sequence
        and record.status_label == "ENGINE_HALTED_STICKY"
        and record.reason_codes == (activation.status_label,)
        and record.expected_state_digest == resolved.planned_state_digest
        and record.observed_state_digest == resolved.planned_state_digest
        and record.position_count == 0
        and record.action is None
        and record.intent_id is None
        and record.token_id is None
        and record.execution_outcome is None
    ]
    if not (
        prepared.sequence > activation.sequence
        and lifecycle_ok
        and effect_confirmed
        and resolved.event_type is JournalEventType.VIRTUAL_EXECUTION_CONFIRMED
        and len(later_halts) == 1
    ):
        return 0, 0, False
    if activation.event_type is JournalEventType.KILL_ACTIVATED:
        return 1, 0, True
    return 0, 1, True


def _fault_exercise_counts(
    records: tuple[JournalRecord, ...],
) -> tuple[dict[str, int], bool]:
    """Count only fault rows bound to one complete reconcile lifecycle."""

    counts = {kind.value: 0 for kind in REQUIRED_FAULT_KINDS}
    handled_rows = [
        record for record in records if record.event_type is JournalEventType.FAULT_HANDLED
    ]
    evidence_ok = True
    seen: set[tuple[str | None, FaultKind]] = set()
    for handled in handled_rows:
        key = (handled.intent_id, handled.fault_kind)
        if handled.fault_kind not in REQUIRED_FAULT_KINDS or key in seen:
            evidence_ok = False
            continue
        seen.add(key)
        prepared_rows = [
            record
            for record in records
            if record.event_type is JournalEventType.INTENT_PREPARED
            and record.intent_id == handled.intent_id
        ]
        started_rows = [
            record
            for record in records
            if record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
            and record.intent_id == handled.intent_id
        ]
        resolved_rows = [
            record
            for record in records
            if record.event_type is JournalEventType.RECONCILE_MATCHED
            and record.intent_id == handled.intent_id
        ]
        uncertain_rows = [
            record
            for record in records
            if record.event_type is JournalEventType.VIRTUAL_EXECUTION_UNCERTAIN
            and record.intent_id == handled.intent_id
        ]
        if (
            len(prepared_rows) != 1
            or len(started_rows) != 1
            or len(resolved_rows) != 1
        ):
            evidence_ok = False
            continue
        prepared = prepared_rows[0]
        started = started_rows[0]
        resolved = resolved_rows[0]
        lifecycle_ok, _effect_confirmed = _lifecycle_contract_ok(
            prepared=prepared,
            started=started,
            resolved=resolved,
            uncertain_rows=uncertain_rows,
        )
        source_kind_ok = (
            True
            if handled.fault_kind is FaultKind.RESTART_RECONCILE
            else prepared.fault_kind is handled.fault_kind
        )
        uncertain_shape_ok = True
        if handled.fault_kind in {
            FaultKind.TIMEOUT,
            FaultKind.UNKNOWN_RESULT,
            FaultKind.NETWORK_ERROR,
        }:
            uncertain_shape_ok = len(uncertain_rows) == 1
        elif handled.fault_kind is FaultKind.CRASH_MID_VIRTUAL_EXECUTION:
            uncertain_shape_ok = not uncertain_rows
        row_ok = bool(
            lifecycle_ok
            and source_kind_ok
            and uncertain_shape_ok
            and _intent_binding_key(handled) == _intent_binding_key(prepared)
            and resolved.sequence < handled.sequence
            and handled.expected_state_digest == resolved.expected_state_digest
            and handled.observed_state_digest == resolved.observed_state_digest
            and handled.position_count == resolved.position_count
        )
        if not row_ok:
            evidence_ok = False
            continue
        counts[handled.fault_kind.value] += 1
    return counts, evidence_ok


def _no_action_evidence_count(
    records: tuple[JournalRecord, ...],
    *,
    policy: E1Policy,
) -> tuple[int, bool]:
    """Validate terminal no-action rows against their frozen decision identity."""

    count = 0
    evidence_ok = True
    for record in records:
        if (
            record.event_type is not JournalEventType.NO_ACTION_RECORDED
            or record.status_label != "ENGINE_NO_ACTION_TERMINAL"
        ):
            continue
        try:
            decision = EngineDecision(
                engine_label=EngineLabel.NO_ACTION,
                config_hash=record.config_hash,
                reason_code=record.reason_codes[0],
                hypothesis_label=record.hypothesis_label,
                hypothesis_id=record.hypothesis_id,
                hypothesis_version=record.hypothesis_version,
            )
        except (E1ContractError, IndexError):
            evidence_ok = False
            continue
        row_ok = bool(
            decision.decision_digest == record.decision_digest
            and record.config_hash == policy.config_hash
            and policy.hypothesis_registry.contains(
                hypothesis_id=record.hypothesis_id or "",
                version=record.hypothesis_version or "",
            )
            and record.expected_state_digest == record.observed_state_digest
            and record.execution_outcome is None
            and record.fault_kind is FaultKind.NONE
            and record.pnl_category is PnlCategory.NOT_APPLICABLE
            and record.virtual_loss == "0"
        )
        if not row_ok:
            evidence_ok = False
            continue
        count += 1
    return count, evidence_ok


def summarize_e1_journal(
    journal: ShadowIntentJournal,
    *,
    policy: E1Policy,
) -> E1AuditSummary:
    records = journal.records
    prepared = [
        record
        for record in records
        if record.event_type is JournalEventType.INTENT_PREPARED
    ]
    started = [
        record
        for record in records
        if record.event_type is JournalEventType.VIRTUAL_EXECUTION_STARTED
    ]
    resolving_types = {
        JournalEventType.VIRTUAL_EXECUTION_CONFIRMED,
        JournalEventType.VIRTUAL_EXECUTION_REJECTED,
        JournalEventType.RECONCILE_MATCHED,
        JournalEventType.RECONCILE_MISMATCH,
    }
    resolutions = [
        record
        for record in records
        if record.event_type in resolving_types and record.intent_id is not None
    ]
    prepared_by_intent: dict[str, list[JournalRecord]] = {}
    started_by_intent: dict[str, list[JournalRecord]] = {}
    resolved_by_intent: dict[str, list[JournalRecord]] = {}
    uncertain_by_intent: dict[str, list[JournalRecord]] = {}
    for record, target in (
        *((record, prepared_by_intent) for record in prepared),
        *((record, started_by_intent) for record in started),
        *((record, resolved_by_intent) for record in resolutions),
    ):
        if record.intent_id is not None:
            target.setdefault(record.intent_id, []).append(record)
    for record in records:
        if (
            record.event_type is JournalEventType.VIRTUAL_EXECUTION_UNCERTAIN
            and record.intent_id is not None
        ):
            uncertain_by_intent.setdefault(record.intent_id, []).append(record)

    all_intent_ids = (
        set(prepared_by_intent)
        | set(started_by_intent)
        | set(resolved_by_intent)
        | set(uncertain_by_intent)
    )
    lifecycle_ok = True
    entry_effects = 0
    settlement_effects = 0
    for intent_id in all_intent_ids:
        prepared_rows = prepared_by_intent.get(intent_id, [])
        started_rows = started_by_intent.get(intent_id, [])
        resolved_rows = resolved_by_intent.get(intent_id, [])
        if len(prepared_rows) != 1 or len(started_rows) != 1 or len(resolved_rows) != 1:
            lifecycle_ok = False
            continue
        prepared_row = prepared_rows[0]
        started_row = started_rows[0]
        resolved_row = resolved_rows[0]
        lifecycle_valid, effect_confirmed = _lifecycle_contract_ok(
            prepared=prepared_row,
            started=started_row,
            resolved=resolved_row,
            uncertain_rows=uncertain_by_intent.get(intent_id, []),
        )
        if not lifecycle_valid:
            lifecycle_ok = False
            continue
        if effect_confirmed and prepared_row.action is GateAction.VIRTUAL_ENTRY:
            entry_effects += 1
        elif effect_confirmed and prepared_row.action is GateAction.VIRTUAL_SETTLEMENT:
            settlement_effects += 1

    intent_ids = [record.intent_id for record in prepared if record.intent_id]
    token_ids = [record.token_id for record in prepared if record.token_id]
    unresolved = journal.unresolved_intents()
    no_actions, no_action_evidence_ok = _no_action_evidence_count(
        records,
        policy=policy,
    )
    fault_counts, fault_exercise_ok = _fault_exercise_counts(records)
    safety_violations = sum(record.safety != shadow_safety_flags() for record in records)
    kill_tests, deadman_tests, control_exercise_ok = _control_exercise_counts(records)
    cardinality_ok = bool(
        lifecycle_ok
        and len(prepared) == len(started) == len(resolutions)
        and len(intent_ids) == len(set(intent_ids))
        and len(token_ids) == len(set(token_ids))
        and len(prepared) == len(token_ids)
        and not unresolved
    )
    return E1AuditSummary(
        durable_intent_count=len(prepared),
        consumed_shadow_token_count=len(token_ids),
        virtual_execution_count=len(started),
        unique_intent_count=len(set(intent_ids)),
        unique_token_count=len(set(token_ids)),
        virtual_entry_effect_count=entry_effects,
        virtual_settlement_effect_count=settlement_effects,
        no_action_count=no_actions,
        reconcile_mismatch_count=sum(
            record.event_type is JournalEventType.RECONCILE_MISMATCH for record in records
        ),
        unresolved_intent_count=len(unresolved),
        safety_violation_count=safety_violations,
        kill_test_count=kill_tests,
        deadman_test_count=deadman_tests,
        fault_handled_counts=tuple(sorted(fault_counts.items())),
        cardinality_invariant_ok=cardinality_ok,
        control_exercise_invariant_ok=control_exercise_ok,
        fault_exercise_invariant_ok=fault_exercise_ok,
        no_action_evidence_invariant_ok=no_action_evidence_ok,
    )


def _sum_audits(audits: tuple[E1AuditSummary, ...]) -> E1AuditSummary:
    fault_counts = {kind.value: 0 for kind in REQUIRED_FAULT_KINDS}
    for audit in audits:
        for label, count in audit.fault_handled_counts:
            fault_counts[label] += count
    return E1AuditSummary(
        durable_intent_count=sum(item.durable_intent_count for item in audits),
        consumed_shadow_token_count=sum(item.consumed_shadow_token_count for item in audits),
        virtual_execution_count=sum(item.virtual_execution_count for item in audits),
        unique_intent_count=sum(item.unique_intent_count for item in audits),
        unique_token_count=sum(item.unique_token_count for item in audits),
        virtual_entry_effect_count=sum(item.virtual_entry_effect_count for item in audits),
        virtual_settlement_effect_count=sum(
            item.virtual_settlement_effect_count for item in audits
        ),
        no_action_count=sum(item.no_action_count for item in audits),
        reconcile_mismatch_count=sum(item.reconcile_mismatch_count for item in audits),
        unresolved_intent_count=sum(item.unresolved_intent_count for item in audits),
        safety_violation_count=sum(item.safety_violation_count for item in audits),
        kill_test_count=sum(item.kill_test_count for item in audits),
        deadman_test_count=sum(item.deadman_test_count for item in audits),
        fault_handled_counts=tuple(sorted(fault_counts.items())),
        cardinality_invariant_ok=all(item.cardinality_invariant_ok for item in audits),
        control_exercise_invariant_ok=all(
            item.control_exercise_invariant_ok for item in audits
        ),
        fault_exercise_invariant_ok=all(
            item.fault_exercise_invariant_ok for item in audits
        ),
        no_action_evidence_invariant_ok=all(
            item.no_action_evidence_invariant_ok for item in audits
        ),
    )


def summarize_e1_bundle(
    journals: tuple[ShadowIntentJournal, ...],
    *,
    policy: E1Policy,
) -> tuple[E1AuditSummary, E1EvidenceWindow, str | None, bool]:
    if not isinstance(journals, tuple) or not journals:
        raise ValueError("E1 gate requires a non-empty tuple of journals")
    run_ids = [journal.run_id for journal in journals]
    config_hashes = {journal.config_hash for journal in journals}
    bundle_identity_ok = bool(
        len(run_ids) == len(set(run_ids))
        and config_hashes == {policy.config_hash}
    )
    audits = tuple(
        summarize_e1_journal(journal, policy=policy) for journal in journals
    )
    combined = _sum_audits(audits)
    prepared_records = [
        record
        for journal in journals
        for record in journal.records
        if record.event_type is JournalEventType.INTENT_PREPARED
    ]
    all_token_ids = [record.token_id for record in prepared_records if record.token_id]
    run_intent_ids = [
        (journal.run_id, record.intent_id)
        for journal in journals
        for record in journal.records
        if record.event_type is JournalEventType.INTENT_PREPARED and record.intent_id
    ]
    bundle_cardinality_ok = bool(
        combined.cardinality_invariant_ok
        and len(all_token_ids) == len(set(all_token_ids))
        and len(run_intent_ids) == len(set(run_intent_ids))
    )
    if not bundle_identity_ok or not bundle_cardinality_ok:
        combined = replace(combined, cardinality_invariant_ok=False)
    records = [record for journal in journals for record in journal.records]
    timestamps = sorted(parse_timestamp(record.recorded_at) for record in records)
    if timestamps:
        first = timestamps[0]
        last = timestamps[-1]
        calendar_days = (last.date() - first.date()).days
        business_dates = {value.date() for value in timestamps if value.weekday() < 5}
        first_text = first.isoformat(timespec="microseconds").replace("+00:00", "Z")
        last_text = last.isoformat(timespec="microseconds").replace("+00:00", "Z")
    else:
        calendar_days = 0
        business_dates = set()
        first_text = None
        last_text = None
    incidents = [
        record for record in records if record.event_type is JournalEventType.INCIDENT_RECORDED
    ]
    postmortems = [
        record for record in records if record.event_type is JournalEventType.POSTMORTEM_RECORDED
    ]
    incident_refs = [record.incident_ref for record in incidents]
    postmortem_refs = [record.incident_ref for record in postmortems]
    incident_evidence_ok = bool(
        len(incident_refs) == len(set(incident_refs))
        and len(postmortem_refs) == len(set(postmortem_refs))
    )
    incidents_by_ref = {record.incident_ref: record for record in incidents}
    valid_postmortem_refs: set[str] = set()
    for postmortem in postmortems:
        incident = incidents_by_ref.get(postmortem.incident_ref)
        if incident is None:
            incident_evidence_ok = False
            continue
        incident_recorded_at = parse_timestamp(incident.recorded_at)
        postmortem_recorded_at = parse_timestamp(postmortem.recorded_at)
        is_later = postmortem_recorded_at > incident_recorded_at or (
            postmortem_recorded_at == incident_recorded_at
            and postmortem.run_id == incident.run_id
            and postmortem.sequence > incident.sequence
        )
        if not is_later:
            incident_evidence_ok = False
            continue
        if postmortem.incident_ref is not None:
            valid_postmortem_refs.add(postmortem.incident_ref)
    medium_refs = {
        record.incident_ref
        for record in incidents
        if record.incident_severity == "MEDIUM" and record.incident_ref is not None
    }
    window = E1EvidenceWindow(
        first_event_at=first_text,
        last_event_at=last_text,
        calendar_days=calendar_days,
        business_days=len(business_dates),
        high_incidents=sum(record.incident_severity == "HIGH" for record in incidents),
        medium_incidents=sum(record.incident_severity == "MEDIUM" for record in incidents),
        incomplete_medium_postmortem_refs=tuple(
            sorted(medium_refs - valid_postmortem_refs)
        ),
        incident_evidence_invariant_ok=incident_evidence_ok,
    )
    config_hash = next(iter(config_hashes)) if len(config_hashes) == 1 else None
    return combined, window, config_hash, bundle_identity_ok


def evaluate_e1_to_e2_review_gate(
    *,
    journals: tuple[ShadowIntentJournal, ...],
    policy: E1Policy,
) -> E1GateReport:
    limits = E1GateThresholds()
    audit, window, config_hash, bundle_identity_ok = summarize_e1_bundle(
        journals,
        policy=policy,
    )
    blockers: list[str] = []
    if not bundle_identity_ok:
        blockers.append("EVIDENCE_BUNDLE_IDENTITY_MISMATCH")
    if window.calendar_days < limits.minimum_calendar_days:
        blockers.append("MINIMUM_CALENDAR_DAYS_NOT_MET")
    if window.business_days < limits.minimum_business_days:
        blockers.append("MINIMUM_BUSINESS_DAYS_NOT_MET")
    if audit.virtual_entry_effect_count < limits.minimum_virtual_entries:
        blockers.append("MINIMUM_VIRTUAL_ENTRY_EVENTS_NOT_MET")
    if audit.virtual_settlement_effect_count < limits.minimum_virtual_settlements:
        blockers.append("MINIMUM_VIRTUAL_SETTLEMENT_EVENTS_NOT_MET")
    if audit.no_action_count < limits.minimum_no_action_events:
        blockers.append("MINIMUM_NO_ACTION_EVENTS_NOT_MET")
    fault_counts = dict(audit.fault_handled_counts)
    for kind in REQUIRED_FAULT_KINDS:
        if fault_counts.get(kind.value, 0) < limits.minimum_each_fault_handled:
            blockers.append(f"MINIMUM_{kind.value}_FAULT_TESTS_NOT_MET")
    if audit.kill_test_count < limits.minimum_kill_tests:
        blockers.append("MINIMUM_KILL_TESTS_NOT_MET")
    if audit.deadman_test_count < limits.minimum_deadman_tests:
        blockers.append("MINIMUM_DEADMAN_TESTS_NOT_MET")
    if audit.reconcile_mismatch_count != 0:
        blockers.append("RECONCILE_MISMATCH_PRESENT")
    if audit.unresolved_intent_count != 0:
        blockers.append("UNRESOLVED_INTENT_PRESENT")
    if audit.safety_violation_count != 0:
        blockers.append("SAFETY_VIOLATION_PRESENT")
    if not audit.cardinality_invariant_ok:
        blockers.append("TOKEN_INTENT_EXECUTION_CARDINALITY_FAILED")
    if not audit.control_exercise_invariant_ok:
        blockers.append("KILL_DEADMAN_EXERCISE_CONTRACT_FAILED")
    if not audit.fault_exercise_invariant_ok:
        blockers.append("FAULT_EXERCISE_EVIDENCE_INVALID")
    if not audit.no_action_evidence_invariant_ok:
        blockers.append("NO_ACTION_EVIDENCE_INVALID")
    if audit.actual_post_count != 0:
        blockers.append("ACTUAL_POST_COUNT_NOT_ZERO")
    if window.high_incidents > limits.maximum_high_incidents:
        blockers.append("HIGH_INCIDENT_PRESENT")
    if window.medium_incidents > limits.maximum_medium_incidents:
        blockers.append("TOO_MANY_MEDIUM_INCIDENTS")
    if not window.all_medium_incidents_have_postmortems:
        blockers.append("MEDIUM_INCIDENT_POSTMORTEM_INCOMPLETE")
    if not window.incident_evidence_invariant_ok:
        blockers.append("INCIDENT_POSTMORTEM_EVIDENCE_INVALID")
    return E1GateReport(
        status=(
            E1GateStatus.IMPLEMENTED_NOT_GATE_PASSED
            if blockers
            else E1GateStatus.EVIDENCE_COMPLETE_REVIEW_REQUIRED
        ),
        blockers=tuple(blockers),
        audit=audit,
        window=window,
        thresholds=limits,
        run_count=len(journals),
        config_hash=config_hash,
    )
