"""Shared definitions for the GMO Public read-only paper 15-window evaluations.

Single home for the things every 15-window runner must agree on: the standard
window set, the fixed config (M5 / current_cost / SL30 / TP60 / 4 JPY pairs), the
read-only safety metadata, run-id naming, and the 3-way classification verdict.

Runners import from here so a new strategy/timeframe can be evaluated under the
exact same protocol (see docs/fx_strategy_evaluation_protocol.md). This module is
library-only: it performs NO network or broker I/O.

No real orders, no Private API, no API key/secret.
"""

from __future__ import annotations

import csv
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.trading import ExecutionConfig  # noqa: E402

# Re-exported from the original helper module so runners can import everything
# they need from one place. (robustness_windows holds the per-trade summarizers.)
from scripts.robustness_windows import (  # noqa: E402,F401
    _FORCED,
    _OPP,
    _SL,
    _STAT_FIELDS,
    _exit_category,
    _mem,
    _summarize,
    _weekdays,
    robustness_summary,
)

EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "analysis_exports"

# --- standard fixed config (M5 / current_cost; never tuned per the protocol) ---
SYMBOLS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY"]
TIMEFRAME = "M5"
SPREAD, SLIP = ExecutionConfig().spread_pips, ExecutionConfig().slippage_pips
STOP_LOSS_PIPS = ExecutionConfig().stop_loss_pips
TAKE_PROFIT_PIPS = ExecutionConfig().take_profit_pips
EXIT_POLICY = "baseline"
DATA_SOURCE = "GMO Public API klines (BID), read-only"

# (label, start, end, group) — 10 prior independent weeks + 5 OOS weeks.
WINDOWS = [
    ("window_1", "20260504", "20260515", "prior10"),
    ("window_2", "20260420", "20260501", "prior10"),
    ("window_3", "20260406", "20260417", "prior10"),
    ("window_4", "20260323", "20260403", "prior10"),
    ("window_5", "20260309", "20260320", "prior10"),
    ("window_6", "20260223", "20260306", "prior10"),
    ("window_7", "20260209", "20260220", "prior10"),
    ("window_8", "20260126", "20260206", "prior10"),
    ("window_9", "20260112", "20260123", "prior10"),
    ("window_10", "20251229", "20260109", "prior10"),
    ("oos_window_1", "20251215", "20251226", "oos5"),
    ("oos_window_2", "20251201", "20251212", "oos5"),
    ("oos_window_3", "20251117", "20251128", "oos5"),
    ("oos_window_4", "20251103", "20251114", "oos5"),
    ("oos_window_5", "20251020", "20251031", "oos5"),
]


def window_groups() -> dict[str, str]:
    """Map each window label to its group ('prior10' / 'oos5')."""
    return {label: group for label, _s, _e, group in WINDOWS}


def group_labels(group: str) -> list[str]:
    return [label for label, _s, _e, g in WINDOWS if g == group]


def run_id(kind: str) -> str:
    """Timestamped run id, e.g. '20260616_120000_gmo_public_paper_<kind>'."""
    return datetime.now().strftime("%Y%m%d_%H%M%S") + f"_gmo_public_paper_{kind}"


def fixed_config(**overrides: object) -> dict:
    """Standard fixed-config block for manifest.json / warnings.json."""
    config = {
        "data_source": DATA_SOURCE,
        "mode": "read-only paper",
        "timeframe": TIMEFRAME,
        "cost_scenario": "current_cost",
        "spread_pips": SPREAD,
        "slippage_pips": SLIP,
        "stop_loss_pips": STOP_LOSS_PIPS,
        "take_profit_pips": TAKE_PROFIT_PIPS,
        "exit_policy": EXIT_POLICY,
        "symbols": SYMBOLS,
        "continuous_replay": True,
    }
    config.update(overrides)
    return config


def safety_metadata() -> dict:
    """Read-only safety flags asserted by every paper run (no live access)."""
    return {
        "real_order": False,
        "private_api_used": False,
        "api_key_used": False,
        "no_order_execution": True,
        "gmo_readonly": True,
        "gmo_order_enabled": False,
    }


# --- shared report writers (stdlib only; standardize analysis_exports output) ---
# These centralize the file-writing mechanics so every runner produces the same
# on-disk shape. They do NOT change content: write_json mirrors the prior inline
# json.dumps(ensure_ascii=False, indent=2), and write_metrics_csv mirrors the
# prior key-columns + _STAT_FIELDS CSV shape exactly.
def ensure_output_dir(path: str | Path) -> Path:
    """Create the run output directory (parents ok) and return it as a Path."""
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_json(path: str | Path, data: object) -> None:
    """Write indent-2 JSON, preserving non-ASCII (Japanese) characters."""
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def write_manifest(out_dir: str | Path, manifest: dict) -> None:
    write_json(Path(out_dir) / "manifest.json", manifest)


def write_warnings(out_dir: str | Path, warnings: dict) -> None:
    write_json(Path(out_dir) / "warnings.json", warnings)


def write_markdown(path: str | Path, content: str) -> None:
    """Write a markdown/text file verbatim (e.g. summary.md, *_final_decision.md)."""
    Path(path).write_text(content)


def write_summary_markdown(out_dir: str | Path, content: str) -> None:
    write_markdown(Path(out_dir) / "summary.md", content)


def write_csv(path: str | Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    """Generic list[dict] -> CSV (DictWriter). fieldnames defaults to first row's keys."""
    rows = list(rows)
    if not rows and not fieldnames:
        Path(path).write_text("")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with Path(path).open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_metrics_csv(path: str | Path, rows: list[dict], key_fields: list[str],
                      stat_fields: list[str] | None = None) -> None:
    """Metrics CSV in the standard shape: key columns + stat columns.

    Each row is {<key_fields...>, "stats": {<stat_fields...>}}. Matches the existing
    15-window runner CSV output (csv.writer, header = keys + _STAT_FIELDS).
    """
    fields = stat_fields if stat_fields is not None else _STAT_FIELDS
    with Path(path).open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([*key_fields, *fields])
        for row in rows:
            writer.writerow([*[row[k] for k in key_fields], *[row["stats"][f] for f in fields]])


def classify_strategy(
    *,
    median_exp: float,
    median_pf: float,
    positive_windows: int,
    n_windows: int,
    edge_windows: int,
    total_pnl: float,
    prior_median_exp: float,
    oos_median_exp: float,
    symbol_concentrated: bool,
) -> tuple[str, list[str]]:
    """Pure 3-way verdict: 継続検証候補 / 研究用ベースライン / 撤退.

    継続: robustly positive across the whole independent set AND both sub-periods.
    撤退: net non-positive overall (median<=0 or total<=0 or positive windows <=half).
    研究用ベースライン: overall mildly positive but fails robustness (period sign
    flip, OOS negative, PF<=1, or concentration) -> keep only as reference.
    """
    reasons: list[str] = []
    majority = n_windows / 2
    sign_flip = (prior_median_exp > 0) != (oos_median_exp > 0)

    strong_keep = (
        median_exp > 0
        and median_pf > 1
        and positive_windows > majority
        and edge_windows > majority
        and total_pnl > 0
        and prior_median_exp > 0
        and oos_median_exp > 0
        and not symbol_concentrated
    )
    if strong_keep:
        return "継続検証候補", ["全window横断で頑健に正(両期間ともプラス)"]

    retire = median_exp <= 0 or total_pnl <= 0 or positive_windows <= majority
    if median_exp <= 0:
        reasons.append(f"期待値中央値 {median_exp} ≤ 0")
    if median_pf <= 1:
        reasons.append(f"PF中央値 {median_pf} ≤ 1")
    if total_pnl <= 0:
        reasons.append(f"合計損益 {total_pnl} ≤ 0")
    if positive_windows <= majority:
        reasons.append(f"プラスwindow {positive_windows}/{n_windows} が過半未満")
    if sign_flip:
        reasons.append("前10窓とOOS5窓で期待値中央値の符号が反転(期間依存)")
    if oos_median_exp <= 0:
        reasons.append(f"OOS5窓の期待値中央値 {oos_median_exp} ≤ 0")
    if symbol_concentrated:
        reasons.append("損益が単一通貨ペアに偏重")

    if retire:
        return "撤退", reasons
    return "研究用ベースライン", reasons


# --- summary.json schema contract (presence-only; values incl. None/"" are allowed) ---
# Strategy 15-window runners (rsi/breakout/bollinger/market_structure/rsi_m15/scaled)
# share robustness_summary() + _build_summary() keys; diagnostic runners (regime) have
# a different shape. Keep them as separate contracts rather than forcing one schema.
STRATEGY_SUMMARY_REQUIRED_KEYS = (
    "window_count",
    "median_expectancy",
    "median_pf",
    "positive_windows",
    "negative_windows",
    "total_pnl",
    "max_drawdown_max",
    "group_prior10",
    "group_oos5",
    "verdict",
)
DIAGNOSTIC_SUMMARY_REQUIRED_KEYS = (
    "best_oos_rule",
    "best_oos",
    "oos5_majority_acc",
    "oos_margin_vs_majority",
    "verdict",
)


def validate_summary_schema(
    summary: Mapping[str, Any],
    required_keys: Sequence[str] = STRATEGY_SUMMARY_REQUIRED_KEYS,
) -> None:
    """Assert a metrics_*_summary.json dict carries the required keys (presence only).

    Raises ValueError listing any missing keys. Does NOT inspect or change values
    (None / "" are allowed) and does NOT touch runner-specific extra keys. Call this
    right before write_json(summary) so future report UIs can rely on the contract.
    """
    if not isinstance(summary, Mapping):
        raise ValueError(f"summary must be a mapping, got {type(summary).__name__}")
    missing = [key for key in required_keys if key not in summary]
    if missing:
        raise ValueError(f"summary is missing required keys: {missing}")


# --- report index (read-only metadata for a future report-list UI) ---
# The 6 read-only safety flags a paper run asserts. Source order: manifest then
# warnings (older strategy runners record only a subset in the manifest; m15/scaled/
# regime record the full set). Unknown flags are NEVER treated as safe.
REPORT_INDEX_SAFETY_KEYS = (
    "real_order",
    "private_api_used",
    "api_key_used",
    "gmo_readonly",
    "gmo_order_enabled",
    "no_order_execution",
)
# Keys report_index_entry() always returns (present even when value is None).
REPORT_INDEX_REQUIRED_KEYS = (
    "run_id",
    "kind",
    "strategy",
    "timeframe",
    "cost_scenario",
    "verdict",
    "median_expectancy",
    "median_pf",
    "total_pnl",
    "max_drawdown_max",
    "created_at",
    "summary_file",
    "safety",
    "safety_complete",
    "safety_conflicts",
    "read_only_confirmed",
    "warnings_count",
    "has_warnings",
)
# Safe (read-only) means every flag is present AND has its read-only value.
_SAFE_EXPECTED = {
    "real_order": False,
    "private_api_used": False,
    "api_key_used": False,
    "gmo_order_enabled": False,
    "gmo_readonly": True,
    "no_order_execution": True,
}


def _read_json_if_exists(path: Path) -> dict:
    """Load a JSON object if the file exists, else return {} (read-only helper)."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else {}


def report_index_entry(run_dir: str | Path) -> dict[str, Any]:
    """Extract one report-list row from a single analysis_exports/<run_id>/ dir.

    Read-only: reads manifest.json (metadata + cost), the single metrics_*_summary.json
    (verdict + headline metrics), and warnings.json (data warnings + safety). Performs
    NO directory traversal, network, or writes. Safety flags are unioned from manifest
    then warnings; any unknown or conflicting flag makes read_only_confirmed False
    (fail-safe — unknown is never treated as safe). Raises FileNotFoundError if no
    summary file exists and ValueError if more than one is found.
    """
    run_dir = Path(run_dir)
    manifest = _read_json_if_exists(run_dir / "manifest.json")
    warnings = _read_json_if_exists(run_dir / "warnings.json")

    summaries = sorted(run_dir.glob("metrics_*_summary.json"))
    if not summaries:
        raise FileNotFoundError(f"no metrics_*_summary.json found in {run_dir}")
    if len(summaries) > 1:
        names = [p.name for p in summaries]
        raise ValueError(f"multiple metrics_*_summary.json in {run_dir}: {names}")
    summary = _read_json_if_exists(summaries[0])

    safety: dict[str, Any] = {}
    conflicts: list[str] = []
    for key in REPORT_INDEX_SAFETY_KEYS:
        m_val, w_val = manifest.get(key), warnings.get(key)
        if m_val is not None and w_val is not None and m_val != w_val:
            conflicts.append(key)
        safety[key] = m_val if m_val is not None else w_val

    read_only_confirmed = not conflicts and all(
        safety.get(k) == v for k, v in _SAFE_EXPECTED.items()
    )
    fetch_warnings = warnings.get("fetch_warnings") or []

    return {
        "run_id": manifest.get("run_id") or run_dir.name,
        "kind": manifest.get("kind"),
        "strategy": manifest.get("strategy"),
        "timeframe": manifest.get("timeframe"),
        "cost_scenario": manifest.get("cost_scenario"),
        "spread_pips": manifest.get("spread_pips"),
        "slippage_pips": manifest.get("slippage_pips"),
        "stop_loss_pips": manifest.get("stop_loss_pips"),
        "take_profit_pips": manifest.get("take_profit_pips"),
        "verdict": summary.get("verdict"),
        "median_expectancy": summary.get("median_expectancy"),
        "median_pf": summary.get("median_pf"),
        "total_pnl": summary.get("total_pnl"),
        "max_drawdown_max": summary.get("max_drawdown_max"),
        "created_at": manifest.get("created_at"),
        "summary_file": summaries[0].name,
        "safety": safety,
        "safety_complete": all(safety[k] is not None for k in REPORT_INDEX_SAFETY_KEYS),
        "safety_conflicts": conflicts,
        "read_only_confirmed": read_only_confirmed,
        "warnings_count": len(fetch_warnings),
        "has_warnings": bool(fetch_warnings),
    }


def list_report_index(exports_root: str | Path) -> list[dict[str, Any]]:
    """List report-index rows for every run directory under exports_root (read-only).

    Each immediate non-hidden subdirectory is passed to report_index_entry(); a row
    that cannot be read (no/duplicate summary, malformed JSON, permission error) becomes
    an error row instead of aborting the whole listing. Normal rows get has_error=False;
    error rows carry run_id/error/has_error=True/read_only_confirmed=False. Sorted:
    normal rows with created_at (desc), then normal rows lacking created_at, then error
    rows (each tier by run_id). Raises FileNotFoundError if exports_root is missing or
    not a directory (a missing root is likely a misconfig, not an empty list). Performs
    NO network, broker, or write I/O.
    """
    root = Path(exports_root)
    if not root.is_dir():
        raise FileNotFoundError(f"exports_root not found or not a directory: {root}")

    entries: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        try:
            entry = report_index_entry(child)
            entry["has_error"] = False
            entries.append(entry)
        except (OSError, ValueError) as exc:
            entries.append({
                "run_id": child.name,
                "error": str(exc),
                "has_error": True,
                "read_only_confirmed": False,
                "created_at": None,
                "summary_file": None,
            })

    with_created = [e for e in entries if not e["has_error"] and e.get("created_at")]
    without_created = [e for e in entries if not e["has_error"] and not e.get("created_at")]
    errors = [e for e in entries if e["has_error"]]
    with_created.sort(key=lambda e: (e["created_at"], e.get("run_id") or ""), reverse=True)
    without_created.sort(key=lambda e: e.get("run_id") or "")
    errors.sort(key=lambda e: e.get("run_id") or "")
    return [*with_created, *without_created, *errors]
