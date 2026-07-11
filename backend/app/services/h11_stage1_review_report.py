"""Read-only safe-aggregate reporting for the H-11 v2 Stage 1 journal.

The reporter never mutates the journal and never returns raw prices, individual
paper PnL values, identifiers, credentials, or broker data.  It reduces the
local JSONL journal to counts and coarse performance labels suitable for the
weekly operator review.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

from app.services.h11_stage1_paper_wiring import PER_TRADE_MAX_LOSS_BOUND_JPY

JST = timezone(timedelta(hours=9))


class H11Stage1ReviewReportError(RuntimeError):
    """Fail-closed report error that never includes journal contents."""


class H11Stage1ReportStatus(str, Enum):
    READY = "READY"
    JOURNAL_MISSING = "JOURNAL_MISSING"
    NO_RECORDS_IN_PERIOD = "NO_RECORDS_IN_PERIOD"


class H11Stage1NetResult(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    FLAT = "FLAT"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True)
class H11Stage1SafeAggregate:
    """Safe counts and labels only.  Never truthy or an execution permission."""

    report_status: H11Stage1ReportStatus
    period_start_jst: str
    period_end_jst: str
    first_recorded_at_jst: str
    last_recorded_at_jst: str
    journal_records_in_period: int
    entry_count: int
    settle_count: int
    block_count: int
    no_entry_count: int
    unknown_event_count: int
    stop_event_count: int
    latest_stop_state: str
    closed_trades_cumulative: int
    discipline_violation_count_cumulative: int
    period_wins: int
    period_losses: int
    period_flats: int
    period_win_rate_pct: float | None
    period_net_result: H11Stage1NetResult
    actual_post: bool = False
    entry_post: bool = False
    settlement_post: bool = False
    post_count: int = 0
    broker_read: bool = False
    broker_write: bool = False
    credential_read: bool = False
    env_read: bool = False
    raw_request_response_access: bool = False
    raw_id_value_exposure: bool = False
    performance_proof_status: bool = False
    live_ready: bool = False
    unattended_live_supported: bool = False

    def __bool__(self) -> bool:
        return False

    def to_safe_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["report_status"] = self.report_status.value
        result["period_net_result"] = self.period_net_result.value
        return result


@dataclass(frozen=True)
class _JournalRecord:
    recorded_at_jst: datetime
    payload: dict[str, object]


_KNOWN_EVENTS = frozenset(
    {
        "PAPER_ENTRY_OPENED",
        "PAPER_POSITION_SETTLED",
        "STAGE1_BLOCKED_PRE_TRADE",
        "STAGE1_NO_ENTRY",
        "DISCIPLINE_VIOLATION",
    }
)


def _parse_recorded_at(value: object) -> datetime:
    if not isinstance(value, str):
        raise H11Stage1ReviewReportError("journal timestamp is missing or invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise H11Stage1ReviewReportError("journal timestamp is invalid") from error
    if parsed.tzinfo is None:
        raise H11Stage1ReviewReportError("journal timestamp must be timezone-aware")
    return parsed.astimezone(JST)


def _load_records(journal_path: Path) -> list[_JournalRecord]:
    if journal_path.is_symlink():
        raise H11Stage1ReviewReportError("journal path must not be a symlink")
    if not journal_path.exists():
        return []
    if not journal_path.is_file():
        raise H11Stage1ReviewReportError("journal path must be a regular file")

    records: list[_JournalRecord] = []
    try:
        with journal_path.open() as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise H11Stage1ReviewReportError(
                        "journal contains invalid JSON"
                    ) from error
                if not isinstance(payload, dict):
                    raise H11Stage1ReviewReportError(
                        "journal record must be an object"
                    )
                records.append(
                    _JournalRecord(
                        recorded_at_jst=_parse_recorded_at(
                            payload.get("recorded_at_utc")
                        ),
                        payload=payload,
                    )
                )
    except OSError as error:
        raise H11Stage1ReviewReportError("journal cannot be read") from error
    return records


def _paper_outcome(payload: dict[str, object]) -> float:
    value = payload.get("paper_outcome_jpy")
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise H11Stage1ReviewReportError("settlement outcome is missing or invalid")
    outcome = float(value)
    if not math.isfinite(outcome):
        raise H11Stage1ReviewReportError("settlement outcome must be finite")
    return outcome


def _closed_total(payload: dict[str, object]) -> int:
    value = payload.get("closed_trades_total")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise H11Stage1ReviewReportError(
            "settlement closed-trades total is missing or invalid"
        )
    return value


def _empty_aggregate(
    *,
    status: H11Stage1ReportStatus,
    since_jst: date | None,
    until_jst: date | None,
) -> H11Stage1SafeAggregate:
    return H11Stage1SafeAggregate(
        report_status=status,
        period_start_jst=since_jst.isoformat() if since_jst else "ALL",
        period_end_jst=until_jst.isoformat() if until_jst else "ALL",
        first_recorded_at_jst="NOT_AVAILABLE",
        last_recorded_at_jst="NOT_AVAILABLE",
        journal_records_in_period=0,
        entry_count=0,
        settle_count=0,
        block_count=0,
        no_entry_count=0,
        unknown_event_count=0,
        stop_event_count=0,
        latest_stop_state="NOT_RECORDED_IN_JOURNAL",
        closed_trades_cumulative=0,
        discipline_violation_count_cumulative=0,
        period_wins=0,
        period_losses=0,
        period_flats=0,
        period_win_rate_pct=None,
        period_net_result=H11Stage1NetResult.NOT_AVAILABLE,
    )


def summarize_h11_stage1_journal(
    journal_path: Path,
    *,
    since_jst: date | None = None,
    until_jst: date | None = None,
) -> H11Stage1SafeAggregate:
    """Read a journal and return safe aggregates for the requested JST period."""

    if since_jst and until_jst and since_jst > until_jst:
        raise H11Stage1ReviewReportError("report period is invalid")

    journal_exists = journal_path.exists()
    all_records = _load_records(journal_path)
    if not all_records:
        return _empty_aggregate(
            status=(
                H11Stage1ReportStatus.NO_RECORDS_IN_PERIOD
                if journal_exists
                else H11Stage1ReportStatus.JOURNAL_MISSING
            ),
            since_jst=since_jst,
            until_jst=until_jst,
        )

    cumulative_closed = 0
    cumulative_violations = 0
    latest_stop_state = "NOT_RECORDED_IN_JOURNAL"
    for record in all_records:
        event = record.payload.get("event")
        if event == "PAPER_POSITION_SETTLED":
            outcome = _paper_outcome(record.payload)
            cumulative_closed = max(cumulative_closed, _closed_total(record.payload))
            if outcome < -PER_TRADE_MAX_LOSS_BOUND_JPY:
                cumulative_violations += 1
            stop_state = record.payload.get("stop_state")
            if isinstance(stop_state, str) and stop_state:
                latest_stop_state = stop_state
        elif event == "DISCIPLINE_VIOLATION":
            cumulative_violations += 1
        elif event == "STAGE1_BLOCKED_PRE_TRADE":
            reasons = record.payload.get("reasons")
            if not isinstance(reasons, list) or not all(
                isinstance(reason, str) for reason in reasons
            ):
                raise H11Stage1ReviewReportError(
                    "blocked record reasons are missing or invalid"
                )
            if "KILL_SWITCH_ON" in reasons:
                latest_stop_state = "KILLED"
            elif "SESSION_STOPPED" in reasons:
                if latest_stop_state in ("NOT_RECORDED_IN_JOURNAL", "ACTIVE"):
                    latest_stop_state = "STOPPED_UNSPECIFIED"
            else:
                # The frozen pre-trade gate always records SESSION_STOPPED
                # when its state is non-ACTIVE.  A block without that reason
                # therefore proves the session remained ACTIVE.
                latest_stop_state = "ACTIVE"
        elif event in ("PAPER_ENTRY_OPENED", "STAGE1_NO_ENTRY"):
            # Both events occur only after the frozen pre-trade gate passes.
            latest_stop_state = "ACTIVE"

    records = [
        record
        for record in all_records
        if (since_jst is None or record.recorded_at_jst.date() >= since_jst)
        and (until_jst is None or record.recorded_at_jst.date() <= until_jst)
    ]
    if not records:
        empty = _empty_aggregate(
            status=H11Stage1ReportStatus.NO_RECORDS_IN_PERIOD,
            since_jst=since_jst,
            until_jst=until_jst,
        )
        return H11Stage1SafeAggregate(
            **{
                **empty.to_safe_dict(),
                "report_status": empty.report_status,
                "period_net_result": empty.period_net_result,
                "closed_trades_cumulative": cumulative_closed,
                "discipline_violation_count_cumulative": cumulative_violations,
                "latest_stop_state": latest_stop_state,
            }
        )

    event_counts = {event: 0 for event in _KNOWN_EVENTS}
    unknown_events = 0
    stop_events = 0
    wins = 0
    losses = 0
    flats = 0
    net_total = 0.0
    for record in records:
        event = record.payload.get("event")
        if isinstance(event, str) and event in event_counts:
            event_counts[event] += 1
        else:
            unknown_events += 1
        if event == "PAPER_POSITION_SETTLED":
            outcome = _paper_outcome(record.payload)
            net_total += outcome
            if outcome > 0:
                wins += 1
            elif outcome < 0:
                losses += 1
            else:
                flats += 1
            stop_state = record.payload.get("stop_state")
            if isinstance(stop_state, str) and stop_state not in ("", "ACTIVE"):
                stop_events += 1

    settled = wins + losses + flats
    if settled == 0:
        net_result = H11Stage1NetResult.NOT_AVAILABLE
        win_rate = None
    else:
        net_result = (
            H11Stage1NetResult.POSITIVE
            if net_total > 0
            else H11Stage1NetResult.NEGATIVE
            if net_total < 0
            else H11Stage1NetResult.FLAT
        )
        win_rate = round(100.0 * wins / settled, 1)

    return H11Stage1SafeAggregate(
        report_status=H11Stage1ReportStatus.READY,
        period_start_jst=since_jst.isoformat() if since_jst else "ALL",
        period_end_jst=until_jst.isoformat() if until_jst else "ALL",
        first_recorded_at_jst=records[0].recorded_at_jst.isoformat(
            timespec="seconds"
        ),
        last_recorded_at_jst=records[-1].recorded_at_jst.isoformat(
            timespec="seconds"
        ),
        journal_records_in_period=len(records),
        entry_count=event_counts["PAPER_ENTRY_OPENED"],
        settle_count=event_counts["PAPER_POSITION_SETTLED"],
        block_count=event_counts["STAGE1_BLOCKED_PRE_TRADE"],
        no_entry_count=event_counts["STAGE1_NO_ENTRY"],
        unknown_event_count=unknown_events,
        stop_event_count=stop_events,
        latest_stop_state=latest_stop_state,
        closed_trades_cumulative=cumulative_closed,
        discipline_violation_count_cumulative=cumulative_violations,
        period_wins=wins,
        period_losses=losses,
        period_flats=flats,
        period_win_rate_pct=win_rate,
        period_net_result=net_result,
    )


def render_h11_stage1_report_markdown(summary: H11Stage1SafeAggregate) -> str:
    """Render a copy-safe Markdown report without raw journal values."""

    win_rate = (
        "NOT_AVAILABLE"
        if summary.period_win_rate_pct is None
        else f"{summary.period_win_rate_pct:.1f}%"
    )
    return "\n".join(
        (
            "# H-11 v2 Stage 1 Safe-Aggregate Review",
            "",
            f"- report_status: `{summary.report_status.value}`",
            f"- period_jst: `{summary.period_start_jst}` to `{summary.period_end_jst}`",
            f"- first_recorded_at_jst: `{summary.first_recorded_at_jst}`",
            f"- last_recorded_at_jst: `{summary.last_recorded_at_jst}`",
            f"- entry_count: `{summary.entry_count}`",
            f"- settle_count: `{summary.settle_count}`",
            f"- block_count: `{summary.block_count}`",
            f"- no_entry_count: `{summary.no_entry_count}`",
            f"- stop_event_count: `{summary.stop_event_count}`",
            f"- latest_stop_state: `{summary.latest_stop_state}`",
            f"- closed_trades_cumulative: `{summary.closed_trades_cumulative}`",
            "- discipline_violation_count_cumulative: "
            f"`{summary.discipline_violation_count_cumulative}`",
            f"- period_wins/losses/flats: `{summary.period_wins}/"
            f"{summary.period_losses}/{summary.period_flats}`",
            f"- period_win_rate: `{win_rate}`",
            f"- period_net_result: `{summary.period_net_result.value}`",
            f"- unknown_event_count: `{summary.unknown_event_count}`",
            "",
            "```text",
            "actual_post=false",
            "entry_post=false",
            "settlement_post=false",
            "post_count=0",
            "broker_read=false",
            "broker_write=false",
            "credential_read=false",
            "env_read=false",
            "raw_request_response_access=false",
            "raw_id_value_exposure=false",
            "performance_proof_status=false",
            "live_ready=false",
            "unattended_live_supported=false",
            "```",
        )
    )
