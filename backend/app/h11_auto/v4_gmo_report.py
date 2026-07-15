"""Read-only safe aggregate for the relaxed GMO v4 SQLite state."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from app.h11_auto.v4_gmo_contracts import V4GmoAction, V4GmoCycleState
from app.h11_auto.v4_gmo_persistence import V4_GMO_SCHEMA_VERSION


class V4GmoReportError(RuntimeError):
    """Safe report error without broker identifiers or value-bearing rows."""


class V4GmoReportStatus(str, Enum):
    READY = "READY"
    STATE_MISSING = "STATE_MISSING"
    EMPTY = "EMPTY"


@dataclass(frozen=True)
class V4GmoSafeAggregate:
    report_status: V4GmoReportStatus
    generation_label: str
    profile_version: str
    strategy_version: str
    selected_horizon: str
    risk_policy_label: str
    dead_man_policy_label: str
    broker_capability_evidence_hash: str
    cycle_count: int
    active_cycle_count: int
    protected_cycle_count: int
    flat_cycle_count: int
    halted_cycle_count: int
    operator_reload_cleared_cycle_count: int
    latest_state: str
    global_halt_latched: bool
    global_halt_reason_safe: str
    action_attempt_count: int
    market_entry_attempt_count: int
    entry_remainder_cancel_attempt_count: int
    protection_attempt_count: int
    protection_cancel_attempt_count: int
    emergency_exit_attempt_count: int
    journal_event_count: int
    journal_valid: bool
    actual_post_count: int = 0
    broker_read_performed: bool = False
    broker_write_performed: bool = False
    credential_read_performed: bool = False
    network_access_performed: bool = False
    raw_or_id_value_exposure: bool = False
    performance_proof_status: bool = False
    live_ready: bool = False
    unattended_live_supported: bool = False

    def __bool__(self) -> bool:
        return False

    def to_safe_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["report_status"] = self.report_status.value
        return payload


_ACTIVE_STATES = frozenset(
    state.value
    for state in V4GmoCycleState
    if state
    not in (
        V4GmoCycleState.FLAT_RECONCILED,
        V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        V4GmoCycleState.OPERATOR_RELOAD_CLEARED,
    )
)


def summarize_v4_gmo_state_no_post(state_path: Path) -> V4GmoSafeAggregate:
    if state_path.is_symlink():
        raise V4GmoReportError("v4 report state path must not be a symlink")
    if not state_path.exists():
        return _empty(V4GmoReportStatus.STATE_MISSING)
    if not state_path.is_file():
        raise V4GmoReportError("v4 report state path must be a regular file")
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"{state_path.resolve().as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        schema = connection.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()
        if schema is None or schema["value"] != V4_GMO_SCHEMA_VERSION:
            raise V4GmoReportError("v4 report schema mismatch")
        cycles = connection.execute(
            "SELECT cycle_ref, state, updated_at_utc FROM cycles ORDER BY updated_at_utc"
        ).fetchall()
        attempts = connection.execute(
            "SELECT cycle_ref, action_kind, outcome_safe_label FROM action_attempts"
        ).fetchall()
        events = connection.execute(
            """
            SELECT sequence, cycle_ref, event_category, state_safe_label,
                   previous_digest, digest
            FROM safe_events ORDER BY sequence
            """
        ).fetchall()
        metadata = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
    except sqlite3.Error as error:
        raise V4GmoReportError("v4 report database read failed") from error
    finally:
        if connection is not None:
            connection.close()
    generation = _generation(metadata)
    journal_valid = _verify_journal(events=events, attempts=attempts, cycles=cycles)
    if not cycles:
        return _empty(
            V4GmoReportStatus.EMPTY,
            generation=generation,
            global_halt_latched=metadata.get("global_halt_latched") == "true",
            global_halt_reason=str(metadata.get("global_halt_reason", "NONE")),
            journal_event_count=len(events),
            journal_valid=journal_valid,
        )
    states = [str(row["state"]) for row in cycles]
    action_counts = {
        action: sum(row["action_kind"] == action.value for row in attempts)
        for action in V4GmoAction
    }
    return V4GmoSafeAggregate(
        report_status=V4GmoReportStatus.READY,
        **generation,
        cycle_count=len(cycles),
        active_cycle_count=sum(state in _ACTIVE_STATES for state in states),
        protected_cycle_count=states.count(V4GmoCycleState.POSITION_PROTECTED.value),
        flat_cycle_count=states.count(V4GmoCycleState.FLAT_RECONCILED.value),
        halted_cycle_count=states.count(
            V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED.value
        ),
        operator_reload_cleared_cycle_count=states.count(
            V4GmoCycleState.OPERATOR_RELOAD_CLEARED.value
        ),
        latest_state=states[-1],
        global_halt_latched=metadata.get("global_halt_latched") == "true",
        global_halt_reason_safe=str(metadata.get("global_halt_reason", "NONE")),
        action_attempt_count=len(attempts),
        market_entry_attempt_count=action_counts[V4GmoAction.MARKET_ENTRY],
        entry_remainder_cancel_attempt_count=action_counts[
            V4GmoAction.CANCEL_ENTRY_REMAINDER
        ],
        protection_attempt_count=action_counts[V4GmoAction.EXACT_SIZE_OCO_PROTECTION],
        protection_cancel_attempt_count=action_counts[
            V4GmoAction.CANCEL_MISMATCHED_PROTECTION
        ],
        emergency_exit_attempt_count=action_counts[
            V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT
        ],
        journal_event_count=len(events),
        journal_valid=journal_valid,
    )


def render_v4_gmo_report_markdown(report: V4GmoSafeAggregate) -> str:
    return "\n".join(
        (
            "# H-11 v4 GMO Safe Aggregate",
            "",
            f"- status: `{report.report_status.value}`",
            f"- generation: `{report.generation_label}`",
            f"- profile: `{report.profile_version}`",
            f"- broker capability evidence: "
            f"`{report.broker_capability_evidence_hash}`",
            f"- strategy / horizon: `{report.strategy_version}` / "
            f"`{report.selected_horizon}`",
            f"- cycles active / protected / flat / halted: `{report.active_cycle_count}` / "
            f"`{report.protected_cycle_count}` / `{report.flat_cycle_count}` / "
            f"`{report.halted_cycle_count}`",
            f"- operator reload cleared cycles: "
            f"`{report.operator_reload_cleared_cycle_count}`",
            f"- action attempts total: `{report.action_attempt_count}`",
            f"- entry / remainder cancel: `{report.market_entry_attempt_count}` / "
            f"`{report.entry_remainder_cancel_attempt_count}`",
            f"- protection / protection cancel / emergency exit: "
            f"`{report.protection_attempt_count}` / "
            f"`{report.protection_cancel_attempt_count}` / "
            f"`{report.emergency_exit_attempt_count}`",
            f"- latest_state: `{report.latest_state}`",
            f"- global_halt: `{str(report.global_halt_latched).lower()}` / "
            f"`{report.global_halt_reason_safe}`",
            f"- journal: `{report.journal_event_count}` events / "
            f"valid=`{str(report.journal_valid).lower()}`",
            "- actual_post / broker_write / credential_read: `false` / `false` / `false`",
            "- live_ready / unattended_live_supported: `false` / `false`",
        )
    )


def _generation(metadata: dict[str, str]) -> dict[str, str]:
    fields = (
        "generation_label",
        "profile_version",
        "strategy_version",
        "selected_horizon",
        "risk_policy_label",
        "dead_man_policy_label",
        "broker_capability_evidence_hash",
    )
    if "generation_digest" not in metadata:
        return {field: "UNBOUND" for field in fields}
    manifest = metadata.get("generation_manifest")
    digest = metadata.get("generation_digest")
    if manifest is None or digest != hashlib.sha256(manifest.encode()).hexdigest():
        raise V4GmoReportError("v4 generation digest is invalid")
    try:
        payload = json.loads(manifest)
    except json.JSONDecodeError as error:
        raise V4GmoReportError("v4 generation manifest is invalid") from error
    if not isinstance(payload, dict):
        raise V4GmoReportError("v4 generation manifest is invalid")
    values: dict[str, str] = {}
    for field in fields:
        value = metadata.get(field)
        if not isinstance(value, str) or payload.get(field) != value:
            raise V4GmoReportError("v4 generation metadata mismatch")
        values[field] = value
    return values


def _verify_journal(
    *,
    events: list[sqlite3.Row],
    attempts: list[sqlite3.Row],
    cycles: list[sqlite3.Row],
) -> bool:
    previous = "GENESIS"
    categories: list[tuple[str, str]] = []
    final_state_by_cycle: dict[str, str] = {}
    for expected_sequence, row in enumerate(events, start=1):
        canonical = "|".join(
            (
                str(row["sequence"]),
                str(row["cycle_ref"]),
                str(row["event_category"]),
                str(row["state_safe_label"]),
                str(row["previous_digest"]),
            )
        )
        expected_digest = hashlib.sha256(canonical.encode()).hexdigest()
        if (
            row["sequence"] != expected_sequence
            or row["previous_digest"] != previous
            or row["digest"] != expected_digest
        ):
            raise V4GmoReportError("v4 safe journal verification failed")
        previous = row["digest"]
        cycle_ref = str(row["cycle_ref"])
        categories.append((cycle_ref, str(row["event_category"])))
        final_state_by_cycle[cycle_ref] = str(row["state_safe_label"])
    if set(final_state_by_cycle) != {str(row["cycle_ref"]) for row in cycles}:
        raise V4GmoReportError("v4 cycle journal coverage failed")
    if any(
        final_state_by_cycle[str(row["cycle_ref"])] != str(row["state"])
        for row in cycles
    ):
        raise V4GmoReportError("v4 cycle state journal mismatch")
    for attempt in attempts:
        action = str(attempt["action_kind"])
        outcome = str(attempt["outcome_safe_label"])
        cycle_ref = str(attempt["cycle_ref"])
        expected_start = f"{action}_ATTEMPT_STARTED"
        expected_outcome = f"{action}_{outcome}"
        start_matches = categories.count((cycle_ref, expected_start))
        outcome_categories = [
            category
            for event_cycle_ref, category in categories
            if event_cycle_ref == cycle_ref
            and category.startswith(f"{action}_")
            and category != expected_start
        ]
        outcome_matches = outcome_categories.count(expected_outcome)
        outcome_pending = outcome == "ATTEMPT_STARTED"
        if start_matches != 1 or (
            outcome_pending and outcome_categories
        ) or (
            not outcome_pending
            and (outcome_matches != 1 or len(outcome_categories) != 1)
        ):
            raise V4GmoReportError("v4 action journal verification failed")
    start_count = sum(
        category.endswith("_ATTEMPT_STARTED") for _, category in categories
    )
    if start_count != len(attempts):
        raise V4GmoReportError("v4 action journal verification failed")
    return True


def _empty(
    status: V4GmoReportStatus,
    *,
    generation: dict[str, str] | None = None,
    global_halt_latched: bool = False,
    global_halt_reason: str = "NONE",
    journal_event_count: int = 0,
    journal_valid: bool = True,
) -> V4GmoSafeAggregate:
    generation = generation or {
        "generation_label": "UNBOUND",
        "profile_version": "UNBOUND",
        "strategy_version": "UNBOUND",
        "selected_horizon": "UNBOUND",
        "risk_policy_label": "UNBOUND",
        "dead_man_policy_label": "UNBOUND",
        "broker_capability_evidence_hash": "UNBOUND",
    }
    return V4GmoSafeAggregate(
        report_status=status,
        **generation,
        cycle_count=0,
        active_cycle_count=0,
        protected_cycle_count=0,
        flat_cycle_count=0,
        halted_cycle_count=0,
        operator_reload_cleared_cycle_count=0,
        latest_state="NONE",
        global_halt_latched=global_halt_latched,
        global_halt_reason_safe=global_halt_reason,
        action_attempt_count=0,
        market_entry_attempt_count=0,
        entry_remainder_cancel_attempt_count=0,
        protection_attempt_count=0,
        protection_cancel_attempt_count=0,
        emergency_exit_attempt_count=0,
        journal_event_count=journal_event_count,
        journal_valid=journal_valid,
    )
