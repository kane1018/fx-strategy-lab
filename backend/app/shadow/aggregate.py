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
from pathlib import Path
from typing import Any

# The read-only safety contract every shadow summary must keep (value each flag must hold).
SAFE_EXPECTED = {
    "real_order": False,
    "private_api_used": False,
    "api_key_used": False,
    "no_order_execution": True,
    "live_trading_environment_enabled": False,
    "gmo_order_enabled": False,
}

_NUMERIC_TOTALS = {
    "total_steps_executed": "steps_executed",
    "total_events_count": "events_count",
    "total_virtual_orders_count": "virtual_orders_count",
    "total_buy_count": "buy_count",
    "total_sell_count": "sell_count",
    "total_flat_count": "flat_count",
}


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
