"""Aggregate multiple local shadow-run summaries (Phase 2D, local-only, no I/O network).

Reads `<input_root>/<run_id>/summary.json` files, totals virtual PnL / order / step
counts, groups by source/symbol/interval/date, flags safety violations, and renders
Markdown / CSV. Pure aggregation: no API, no orders, no secret. Inputs and outputs live
under shadow_exports/ (gitignored) and must never be committed.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.shadow.audit_schema import (
    AUDIT_EVENT_TYPES,
    AuditSchemaError,
    validate_audit_row,
)
from app.shadow.audit_schema import (
    SAFETY_EXPECTED as SAFE_EXPECTED,
)

_NUMERIC_TOTALS = {
    "total_steps_executed": "steps_executed",
    "total_events_count": "events_count",
    "total_virtual_orders_count": "virtual_orders_count",
    "total_buy_count": "buy_count",
    "total_sell_count": "sell_count",
    "total_flat_count": "flat_count",
}

_RISK_LOG_EVENT_TYPES = tuple(sorted(AUDIT_EVENT_TYPES))


def _risk_log_error(
    *,
    event_type: str,
    line_number: int | None,
    error: AuditSchemaError,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "line": line_number,
        "field": error.field,
        "value": error.value,
        "expected": error.expected,
    }


def _plain_risk_log_error(
    *,
    event_type: str,
    line_number: int | None,
    field: str,
    value: Any,
    expected: Any,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "line": line_number,
        "field": field,
        "value": value,
        "expected": expected,
    }


def _load_risk_pipeline(run_dir: Path) -> dict[str, Any] | None:
    """Read optional Phase 2E-1 JSONL logs without penalizing legacy runs."""
    result: dict[str, Any] = {
        "candidate_count": 0,
        "risk_allow_count": 0,
        "risk_reject_count": 0,
        "kill_switch_count": 0,
        "kill_switch_active": False,
        "shadow_risk_schema_versions": [],
        "reject_reasons": {},
        "kill_switch_reasons": {},
        "log_errors": [],
        "invalid_risk_row_count": 0,
    }
    found = False
    versions: set[str] = set()
    kill_reasons: Counter[str] = Counter()
    candidates: dict[str, dict[str, Any]] = {}
    duplicate_candidate_ids: set[str] = set()
    decisions_by_id: dict[str, dict[str, Any]] = {}
    duplicate_decision_ids: set[str] = set()
    decisions_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for event_type in _RISK_LOG_EVENT_TYPES:
        path = run_dir / f"{event_type}.jsonl"
        if not path.exists():
            continue
        found = True
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            result["invalid_risk_row_count"] += 1
            result["log_errors"].append(
                _plain_risk_log_error(
                    event_type=event_type,
                    line_number=None,
                    field=path.name,
                    value=error.__class__.__name__,
                    expected="readable JSONL file",
                )
            )
            continue
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("row is not an object")
            except (ValueError, json.JSONDecodeError):
                result["invalid_risk_row_count"] += 1
                result["log_errors"].append(
                    _plain_risk_log_error(
                        event_type=event_type,
                        line_number=line_number,
                        field="row",
                        value="invalid_json",
                        expected="JSON object",
                    )
                )
                continue
            try:
                row = validate_audit_row(event_type, row, expected_run_id=run_dir.name)
            except AuditSchemaError as error:
                result["invalid_risk_row_count"] += 1
                result["log_errors"].append(
                    _risk_log_error(
                        event_type=event_type,
                        line_number=line_number,
                        error=error,
                    )
                )
                continue
            versions.add(row["schema_version"])
            if event_type == "candidate_log":
                candidate_id = row["candidate_id"]
                if candidate_id in candidates:
                    duplicate_candidate_ids.add(candidate_id)
                    continue
                candidates[candidate_id] = row
            elif event_type == "risk_decision_log":
                decision_id = row["decision_id"]
                if decision_id in decisions_by_id:
                    duplicate_decision_ids.add(decision_id)
                    continue
                decisions_by_id[decision_id] = row
                decisions_by_candidate.setdefault(row["candidate_id"], []).append(row)
            elif event_type == "kill_switch_log":
                result["kill_switch_count"] += 1
                result["kill_switch_active"] = result["kill_switch_active"] or bool(
                    row.get("active")
                )
                for reason in row.get("reasons") or []:
                    kill_reasons[str(reason)] += 1

    invalid_candidate_ids = set(duplicate_candidate_ids)
    for candidate_id in sorted(duplicate_candidate_ids):
        result["invalid_risk_row_count"] += 1
        result["log_errors"].append(
            _plain_risk_log_error(
                event_type="candidate_log",
                line_number=None,
                field="candidate_id",
                value=candidate_id,
                expected="unique candidate_id",
            )
        )

    invalid_decision_ids = set(duplicate_decision_ids)
    for decision_id in sorted(duplicate_decision_ids):
        result["invalid_risk_row_count"] += 1
        result["log_errors"].append(
            _plain_risk_log_error(
                event_type="risk_decision_log",
                line_number=None,
                field="decision_id",
                value=decision_id,
                expected="unique decision_id",
            )
        )

    for candidate_id in sorted(set(decisions_by_candidate) - set(candidates)):
        invalid_decision_ids.update(
            row["decision_id"] for row in decisions_by_candidate[candidate_id]
        )
        result["invalid_risk_row_count"] += 1
        result["log_errors"].append(
            _plain_risk_log_error(
                event_type="risk_decision_log",
                line_number=None,
                field="candidate_id",
                value=candidate_id,
                expected="matching candidate_log row",
            )
        )

    for candidate_id, decisions in sorted(decisions_by_candidate.items()):
        if candidate_id not in candidates:
            continue
        if len(decisions) != 1:
            invalid_candidate_ids.add(candidate_id)
            invalid_decision_ids.update(row["decision_id"] for row in decisions)
            result["invalid_risk_row_count"] += 1
            result["log_errors"].append(
                _plain_risk_log_error(
                    event_type="risk_decision_log",
                    line_number=None,
                    field="candidate_id",
                    value=candidate_id,
                    expected="exactly one risk decision",
                )
            )

    for candidate_id in sorted(set(candidates) - set(decisions_by_candidate)):
        invalid_candidate_ids.add(candidate_id)
        result["invalid_risk_row_count"] += 1
        result["log_errors"].append(
            _plain_risk_log_error(
                event_type="candidate_log",
                line_number=None,
                field="candidate_id",
                value=candidate_id,
                expected="matching risk_decision_log row",
            )
        )

    reject_reasons: Counter[str] = Counter()
    for candidate_id, candidate in candidates.items():
        decisions = decisions_by_candidate.get(candidate_id) or []
        if candidate_id in invalid_candidate_ids or len(decisions) != 1:
            continue
        decision = decisions[0]
        if decision["decision_id"] in invalid_decision_ids:
            continue
        if (
            decision["run_id"] != candidate["run_id"]
            or decision["step_index"] != candidate["step_index"]
        ):
            result["invalid_risk_row_count"] += 1
            result["log_errors"].append(
                _plain_risk_log_error(
                    event_type="risk_decision_log",
                    line_number=None,
                    field="candidate_correlation",
                    value=decision["decision_id"],
                    expected="same run_id and step_index as candidate",
                )
            )
            continue
        result["candidate_count"] += 1
        if decision["status"] == "ALLOW_SHADOW":
            result["risk_allow_count"] += 1
        else:
            result["risk_reject_count"] += 1
            reject_reasons.update(decision["reasons"])

    if not found:
        return None
    result["shadow_risk_schema_versions"] = sorted(versions)
    result["reject_reasons"] = dict(sorted(reject_reasons.items()))
    result["kill_switch_reasons"] = dict(sorted(kill_reasons.items()))
    return result


def load_run_summaries(input_root: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Load every <input_root>/<dir>/summary.json. Returns (summaries, broken_run_ids).

    Broken/unreadable summaries are skipped (their dir name is reported), not fatal.
    Raises FileNotFoundError only if input_root itself is missing/not a directory.
    """
    root = Path(input_root)
    if not root.is_dir():
        raise FileNotFoundError(f"shadow input_root not found or not a directory: {root}")
    summaries: list[dict[str, Any]] = []
    broken: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        path = child / "summary.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                raise ValueError("summary.json is not an object")
            data.setdefault("run_id", child.name)
            risk_pipeline = _load_risk_pipeline(child)
            if risk_pipeline is not None:
                data["risk_pipeline"] = risk_pipeline
            summaries.append(data)
        except (OSError, ValueError):
            broken.append(child.name)
    return summaries, broken


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _date_of(summary: dict[str, Any]) -> str:
    created = str(summary.get("created_at") or "")
    return created[:10] or "unknown"


def safety_violations(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one record per (run, violated safety flag). Empty = all safe."""
    out: list[dict[str, Any]] = []
    for s in summaries:
        safety = s.get("safety") or {}
        for field, expected in SAFE_EXPECTED.items():
            if safety.get(field) != expected:
                out.append({
                    "run_id": s.get("run_id"),
                    "field": field,
                    "value": safety.get(field),
                    "expected": expected,
                })
        risk_pipeline = s.get("risk_pipeline") or {}
        for error in risk_pipeline.get("log_errors") or []:
            if isinstance(error, dict):
                event_type = error.get("event_type") or "risk_pipeline"
                field = error.get("field") or "row"
                out.append({
                    "run_id": s.get("run_id"),
                    "event_type": event_type,
                    "field": f"{event_type}.{field}",
                    "value": error.get("value"),
                    "expected": error.get("expected"),
                })
            else:
                out.append({
                    "run_id": s.get("run_id"),
                    "event_type": "risk_pipeline",
                    "field": "risk_pipeline",
                    "value": error,
                    "expected": "valid shadow-risk-v1 JSONL",
                })
    return out


def _group(summaries: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for s in summaries:
        name = str(s.get(key) if key != "date" else _date_of(s)) or "unknown"
        g = groups.setdefault(name, {"runs_count": 0, "virtual_orders_count": 0,
                                     "final_unrealized_pnl": 0.0, "halted_runs_count": 0})
        g["runs_count"] += 1
        g["virtual_orders_count"] += int(_num(s.get("virtual_orders_count")))
        g["final_unrealized_pnl"] += _num(s.get("final_unrealized_pnl"))
        if s.get("halted"):
            g["halted_runs_count"] += 1
    return groups


def aggregate_summaries(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the overall aggregate (totals + grouped + safety) from run summaries."""
    violations = safety_violations(summaries)
    violated_run_ids = sorted({v["run_id"] for v in violations})
    totals = {
        agg: sum(int(_num(s.get(src))) for s in summaries)
        for agg, src in _NUMERIC_TOTALS.items()
    }
    created = sorted(str(s.get("created_at") or "") for s in summaries if s.get("created_at"))
    risk_pipelines = [s.get("risk_pipeline") or {} for s in summaries]
    reject_reasons: Counter[str] = Counter()
    kill_reasons: Counter[str] = Counter()
    schema_versions: set[str] = set()
    for pipeline in risk_pipelines:
        reject_reasons.update(pipeline.get("reject_reasons") or {})
        kill_reasons.update(pipeline.get("kill_switch_reasons") or {})
        schema_versions.update(pipeline.get("shadow_risk_schema_versions") or [])
    return {
        "runs_count": len(summaries),
        "sources": sorted({str(s.get("source") or "unknown") for s in summaries}),
        "symbols": sorted({str(s.get("symbol") or "unknown") for s in summaries}),
        "intervals": sorted({str(s.get("interval") or "unknown") for s in summaries}),
        **totals,
        "total_final_unrealized_pnl": round(
            sum(_num(s.get("final_unrealized_pnl")) for s in summaries), 5
        ),
        "halted_runs_count": sum(1 for s in summaries if s.get("halted")),
        "safety_violation_runs_count": len(violated_run_ids),
        "max_abs_units_overall": max(
            (int(_num(s.get("max_abs_units"))) for s in summaries), default=0
        ),
        "first_created_at": created[0] if created else None,
        "last_created_at": created[-1] if created else None,
        "by_source": _group(summaries, "source"),
        "by_symbol": _group(summaries, "symbol"),
        "by_interval": _group(summaries, "interval"),
        "by_date": _group(summaries, "date"),
        "safety_violations": violations,
        "safety_violation_run_ids": violated_run_ids,
        "candidate_count": sum(int(_num(p.get("candidate_count"))) for p in risk_pipelines),
        "risk_allow_count": sum(int(_num(p.get("risk_allow_count"))) for p in risk_pipelines),
        "risk_reject_count": sum(int(_num(p.get("risk_reject_count"))) for p in risk_pipelines),
        "kill_switch_count": sum(int(_num(p.get("kill_switch_count"))) for p in risk_pipelines),
        "invalid_risk_row_count": sum(
            int(_num(p.get("invalid_risk_row_count"))) for p in risk_pipelines
        ),
        "kill_switch_active_runs_count": sum(
            1 for p in risk_pipelines if p.get("kill_switch_active")
        ),
        "shadow_risk_schema_versions": sorted(schema_versions),
        "reject_reasons": dict(sorted(reject_reasons.items())),
        "kill_switch_reasons": dict(sorted(kill_reasons.items())),
    }


def _group_md(title: str, groups: dict[str, dict[str, Any]]) -> list[str]:
    lines = [
        f"### {title}", "",
        "| key | runs | orders | pnl | halted |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, g in sorted(groups.items()):
        lines.append(
            f"| {name} | {g['runs_count']} | {g['virtual_orders_count']} | "
            f"{g['final_unrealized_pnl']:.5f} | {g['halted_runs_count']} |"
        )
    lines.append("")
    return lines


def render_markdown(agg: dict[str, Any], summaries: list[dict[str, Any]], broken: list[str]) -> str:
    """Render the aggregate as a human/ChatGPT Markdown report (read-only)."""
    lines = ["# Shadow Runs Aggregate (local, no-order)", ""]
    lines += [
        "## Overview", "",
        f"- runs_count: {agg['runs_count']} (broken/skipped: {len(broken)})",
        f"- sources: {', '.join(agg['sources']) or '-'}",
        f"- symbols: {', '.join(agg['symbols']) or '-'}",
        f"- intervals: {', '.join(agg['intervals']) or '-'}",
        f"- created_at: {agg['first_created_at']} .. {agg['last_created_at']}", "",
        "## Totals", "",
        f"- total_steps_executed: {agg['total_steps_executed']}",
        f"- total_events_count: {agg['total_events_count']}",
        f"- total_virtual_orders_count: {agg['total_virtual_orders_count']}",
        f"- buy/sell/flat: {agg['total_buy_count']}/{agg['total_sell_count']}/"
        f"{agg['total_flat_count']}",
        f"- total_final_unrealized_pnl: {agg['total_final_unrealized_pnl']:.5f}",
        f"- halted_runs_count: {agg['halted_runs_count']}",
        f"- max_abs_units_overall: {agg['max_abs_units_overall']}",
        f"- safety_violation_runs_count: {agg['safety_violation_runs_count']}", "",
    ]
    lines += _group_md("By Source", agg["by_source"])
    lines += _group_md("By Symbol", agg["by_symbol"])
    lines += _group_md("By Interval", agg["by_interval"])
    lines += _group_md("By Date", agg["by_date"])

    lines += [
        "## Shadow Risk Pipeline", "",
        f"- candidate_count: {agg['candidate_count']}",
        f"- risk_allow_count: {agg['risk_allow_count']}",
        f"- risk_reject_count: {agg['risk_reject_count']}",
        f"- kill_switch_count: {agg['kill_switch_count']}",
        f"- invalid_risk_row_count: {agg['invalid_risk_row_count']}",
        f"- kill_switch_active_runs_count: {agg['kill_switch_active_runs_count']}",
        "- shadow_risk_schema_versions: "
        f"{', '.join(agg['shadow_risk_schema_versions']) or '-'}",
        f"- reject_reasons: {json.dumps(agg['reject_reasons'], sort_keys=True)}",
        f"- kill_switch_reasons: {json.dumps(agg['kill_switch_reasons'], sort_keys=True)}",
        "",
    ]

    lines += ["## Safety Violations", ""]
    if not agg["safety_violations"]:
        lines += ["(none — all runs read-only / no-order)", ""]
    else:
        lines += ["| run_id | field | value | expected |", "| --- | --- | --- | --- |"]
        for v in agg["safety_violations"]:
            lines.append(f"| {v['run_id']} | {v['field']} | {v['value']} | {v['expected']} |")
        lines.append("")

    lines += ["## Halted Runs", ""]
    halted = [s for s in summaries if s.get("halted")]
    if not halted:
        lines += ["(none)", ""]
    else:
        lines += ["| run_id | reason |", "| --- | --- |"]
        for s in halted:
            lines.append(f"| {s.get('run_id')} | {s.get('halt_reason') or '-'} |")
        lines.append("")

    if broken:
        lines += ["## Skipped (broken summary)", "", *[f"- {name}" for name in broken], ""]
    return "\n".join(lines)


_RUNS_CSV_FIELDS = [
    "run_id", "source", "symbol", "interval", "steps_executed", "events_count",
    "virtual_orders_count", "buy_count", "sell_count", "flat_count", "max_abs_units",
    "final_position_side", "final_position_units", "final_unrealized_pnl", "halted",
    "halt_reason", "created_at",
]


def render_runs_csv(summaries: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_RUNS_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for s in summaries:
        writer.writerow({k: s.get(k, "") for k in _RUNS_CSV_FIELDS})
    return buf.getvalue()


def render_group_csv(groups: dict[str, dict[str, Any]], key_name: str) -> str:
    buf = io.StringIO()
    fields = [
        key_name, "runs_count", "virtual_orders_count", "final_unrealized_pnl",
        "halted_runs_count",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for name, g in sorted(groups.items()):
        writer.writerow({key_name: name, **g})
    return buf.getvalue()
