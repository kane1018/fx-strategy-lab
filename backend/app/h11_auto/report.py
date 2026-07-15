"""Read-only safe aggregates for the H11 auto local state database."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from app.h11_auto.persistence import PHASE_A_SCHEMA_VERSION
from app.h11_auto.state_machine import AutoCycleState


class H11AutoReportError(RuntimeError):
    """Fail-closed report error without persisted values or identifiers."""


class H11AutoReportStatus(str, Enum):
    READY = "READY"
    STATE_MISSING = "STATE_MISSING"
    NO_RECORDS_IN_PERIOD = "NO_RECORDS_IN_PERIOD"


@dataclass(frozen=True)
class H11AutoSafeAggregate:
    report_status: H11AutoReportStatus
    period_start_jst: str
    period_end_jst: str
    cycle_count: int
    active_cycle_count: int
    flat_cycle_count: int
    halted_cycle_count: int
    entry_attempt_count: int
    exit_attempt_count: int
    latest_state: str
    latest_halt_reason_code: str
    last_updated_at_utc: str
    journal_event_count: int
    journal_valid: bool
    generation_label: str
    strategy_version: str
    selected_horizon: str
    risk_policy_label: str
    dead_man_policy_label: str
    actual_post_count: int = 0
    broker_read_performed: bool = False
    broker_write_performed: bool = False
    network_access_performed: bool = False
    credential_read_performed: bool = False
    raw_id_value_exposure: bool = False
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
    {
        AutoCycleState.INTENT_PERSISTED.value,
        AutoCycleState.PROTECTED_ENTRY_PENDING.value,
        AutoCycleState.POSITION_PROTECTED.value,
        AutoCycleState.EXIT_PENDING.value,
    }
)


def summarize_h11_auto_state(
    state_path: Path,
    *,
    since_jst: date | None = None,
    until_jst: date | None = None,
) -> H11AutoSafeAggregate:
    if since_jst and until_jst and since_jst > until_jst:
        raise H11AutoReportError("report period is invalid")
    if state_path.is_symlink():
        raise H11AutoReportError("state path must not be a symlink")
    if not state_path.exists():
        return _empty(H11AutoReportStatus.STATE_MISSING, since_jst, until_jst)
    if not state_path.is_file():
        raise H11AutoReportError("state path must be a regular file")
    try:
        connection = sqlite3.connect(
            f"{state_path.resolve().as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        with connection:
            metadata = connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            if metadata is None or metadata["value"] != PHASE_A_SCHEMA_VERSION:
                raise H11AutoReportError("state schema metadata is missing or invalid")
            rows = connection.execute(
                "SELECT intent_id, state, attempt_count, exit_attempt_count, "
                "created_at_utc, updated_at_utc, halt_reason "
                "FROM cycles ORDER BY created_at_utc"
            ).fetchall()
            events = connection.execute(
                "SELECT sequence, intent_id, event_category, state_safe_label, "
                "previous_digest, digest FROM safe_events ORDER BY sequence"
            ).fetchall()
            generation = _safe_generation_metadata(connection)
    except sqlite3.Error as error:
        raise H11AutoReportError("state database cannot be read") from error
    finally:
        if "connection" in locals():
            connection.close()

    filtered = [
        row
        for row in rows
        if _within_jst_period(
            row["created_at_utc"], since_jst=since_jst, until_jst=until_jst
        )
    ]
    if not filtered:
        return _empty(
            H11AutoReportStatus.NO_RECORDS_IN_PERIOD,
            since_jst,
            until_jst,
            generation=generation,
        )

    filtered_intent_ids = {row["intent_id"] for row in filtered}
    filtered_events = [row for row in events if row["intent_id"] in filtered_intent_ids]
    latest = max(filtered, key=lambda row: _parse_timestamp(row["updated_at_utc"]))
    states = [str(row["state"]) for row in filtered]
    halt_reason = latest["halt_reason"] if latest["halt_reason"] else "NONE"
    if not isinstance(halt_reason, str):
        raise H11AutoReportError("halt reason code is invalid")
    return H11AutoSafeAggregate(
        report_status=H11AutoReportStatus.READY,
        period_start_jst=since_jst.isoformat() if since_jst else "ALL",
        period_end_jst=until_jst.isoformat() if until_jst else "ALL",
        cycle_count=len(filtered),
        active_cycle_count=sum(state in _ACTIVE_STATES for state in states),
        flat_cycle_count=states.count(AutoCycleState.FLAT_RECONCILED.value),
        halted_cycle_count=states.count(
            AutoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED.value
        ),
        entry_attempt_count=sum(int(row["attempt_count"]) for row in filtered),
        exit_attempt_count=sum(int(row["exit_attempt_count"]) for row in filtered),
        latest_state=str(latest["state"]),
        latest_halt_reason_code=halt_reason,
        last_updated_at_utc=str(latest["updated_at_utc"]),
        journal_event_count=len(filtered_events),
        journal_valid=_verify_events(events),
        **generation,
    )


def render_h11_auto_report_markdown(report: H11AutoSafeAggregate) -> str:
    return "\n".join(
        (
            "# H-11 Auto Phase B Safe Aggregate",
            "",
            f"- status: `{report.report_status.value}`",
            f"- period_jst: `{report.period_start_jst}` to `{report.period_end_jst}`",
            f"- cycles: `{report.cycle_count}`",
            f"- active / flat / halted: `{report.active_cycle_count}` / "
            f"`{report.flat_cycle_count}` / `{report.halted_cycle_count}`",
            f"- entry / exit attempts: `{report.entry_attempt_count}` / "
            f"`{report.exit_attempt_count}`",
            f"- latest_state: `{report.latest_state}`",
            f"- latest_halt_reason: `{report.latest_halt_reason_code}`",
            f"- journal: `{report.journal_event_count}` events / "
            f"valid=`{str(report.journal_valid).lower()}`",
            f"- generation: `{report.generation_label}`",
            f"- strategy / horizon: `{report.strategy_version}` / "
            f"`{report.selected_horizon}`",
            f"- risk / dead-man policy: `{report.risk_policy_label}` / "
            f"`{report.dead_man_policy_label}`",
            "- actual_post: `false`",
            "- broker_read / broker_write: `false` / `false`",
            "- credential_read: `false`",
            "- live_ready / unattended_live_supported: `false` / `false`",
        )
    )


def _empty(
    status: H11AutoReportStatus,
    since_jst: date | None,
    until_jst: date | None,
    *,
    generation: dict[str, str] | None = None,
) -> H11AutoSafeAggregate:
    generation = generation or {
        "generation_label": "UNBOUND",
        "strategy_version": "UNBOUND",
        "selected_horizon": "UNBOUND",
        "risk_policy_label": "UNBOUND",
        "dead_man_policy_label": "UNBOUND",
    }
    return H11AutoSafeAggregate(
        report_status=status,
        period_start_jst=since_jst.isoformat() if since_jst else "ALL",
        period_end_jst=until_jst.isoformat() if until_jst else "ALL",
        cycle_count=0,
        active_cycle_count=0,
        flat_cycle_count=0,
        halted_cycle_count=0,
        entry_attempt_count=0,
        exit_attempt_count=0,
        latest_state="NONE",
        latest_halt_reason_code="NONE",
        last_updated_at_utc="NOT_AVAILABLE",
        journal_event_count=0,
        journal_valid=True,
        **generation,
    )


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise H11AutoReportError("state timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise H11AutoReportError("state timestamp is invalid") from error
    if parsed.tzinfo is None:
        raise H11AutoReportError("state timestamp must be timezone-aware")
    return parsed


def _within_jst_period(
    value: object,
    *,
    since_jst: date | None,
    until_jst: date | None,
) -> bool:
    from zoneinfo import ZoneInfo

    day = _parse_timestamp(value).astimezone(ZoneInfo("Asia/Tokyo")).date()
    return (since_jst is None or day >= since_jst) and (
        until_jst is None or day <= until_jst
    )


def _verify_events(rows: list[sqlite3.Row]) -> bool:
    previous = "GENESIS"
    for expected, row in enumerate(rows, start=1):
        payload = {
            "event_category": row["event_category"],
            "intent_id": row["intent_id"],
            "previous_digest": row["previous_digest"],
            "sequence": row["sequence"],
            "state_safe_label": row["state_safe_label"],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        if (
            row["sequence"] != expected
            or row["previous_digest"] != previous
            or row["digest"] != digest
        ):
            raise H11AutoReportError("safe journal verification failed")
        previous = row["digest"]
    return True


def _safe_generation_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    keys = (
        "run_generation_digest",
        "run_generation_manifest",
        "generation_label",
        "strategy_version",
        "selected_horizon",
        "risk_policy_label",
        "dead_man_policy_label",
    )
    placeholders = ",".join("?" for _ in keys)
    rows = connection.execute(
        f"SELECT key, value FROM metadata WHERE key IN ({placeholders})",  # noqa: S608
        keys,
    ).fetchall()
    if not rows:
        return {
            "generation_label": "UNBOUND",
            "strategy_version": "UNBOUND",
            "selected_horizon": "UNBOUND",
            "risk_policy_label": "UNBOUND",
            "dead_man_policy_label": "UNBOUND",
        }
    values = {str(row["key"]): str(row["value"]) for row in rows}
    if set(values) != set(keys):
        raise H11AutoReportError("run generation metadata is incomplete or invalid")
    manifest = values.pop("run_generation_manifest")
    digest = values.pop("run_generation_digest")
    if hashlib.sha256(manifest.encode()).hexdigest() != digest:
        raise H11AutoReportError("run generation metadata digest is invalid")
    try:
        manifest_values = json.loads(manifest)
    except json.JSONDecodeError as error:
        raise H11AutoReportError("run generation metadata manifest is invalid") from error
    if not isinstance(manifest_values, dict) or any(
        manifest_values.get(key) != value for key, value in values.items()
    ):
        raise H11AutoReportError("run generation metadata manifest is invalid")
    if any(
        not value.strip()
        or len(value) > 128
        or "\n" in value
        or "\r" in value
        for value in values.values()
    ):
        raise H11AutoReportError("run generation metadata label is invalid")
    return values
