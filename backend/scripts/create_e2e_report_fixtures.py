"""Generate small, fixed E2E report fixtures (read-only, offline).

Creates the 5-run fixture set described in docs §16-16 so Playwright can drive the
read-only /reports UI against deterministic data instead of the real analysis_exports/.
Pure file writing only: NO real analysis_exports read, NO GMO/Private API, NO API key /
secret / .env, NO DB, NO backtest, NO real order. Reuses scripts.fx_eval_common writers.

Usage:
    python -m scripts.create_e2e_report_fixtures [--output-root <dir>]
Default output root: <repo>/frontend/e2e/fixtures/analysis_exports
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.fx_eval_common import (
    ensure_output_dir,
    write_csv,
    write_json,
    write_markdown,
)

# Marker placed in CSV bodies. The API never returns CSV bodies, so this string must
# never appear in report_detail() output / the UI (verified by E2E-07 and the tests).
CSV_BODY_MARKER = "__CSV_BODY_MARKER__"

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = _REPO_ROOT / "frontend" / "e2e" / "fixtures" / "analysis_exports"

# The 6 read-only safety flags every paper run asserts (see fx_eval_common).
_SAFE_FLAGS = {
    "real_order": False,
    "private_api_used": False,
    "api_key_used": False,
    "gmo_readonly": True,
    "gmo_order_enabled": False,
    "no_order_execution": True,
}


def _summary() -> dict:
    """Minimal strategy summary that passes validate_summary_schema()."""
    return {
        "window_count": 15,
        "median_expectancy": 0.0164,
        "median_pf": 1.016,
        "positive_windows": 8,
        "negative_windows": 7,
        "total_pnl": 56.95,
        "max_drawdown_max": 65.46,
        "group_prior10": {"median_expectancy": 0.02},
        "group_oos5": {"median_expectancy": -0.01},
        "verdict": "研究用ベースライン",
    }


def _manifest(run_id: str, safety: dict) -> dict:
    return {
        "run_id": run_id,
        "created_at": "2026-01-01T00:00:00",
        "kind": "strategy",
        "strategy": "rsi_reversal",
        "timeframe": "M5",
        "cost_scenario": "current_cost",
        "symbols": ["USD_JPY", "EUR_JPY"],
        "spread_pips": 1.2,
        "slippage_pips": 0.2,
        "stop_loss_pips": 30,
        "take_profit_pips": 60,
        **safety,
    }


def _write_common_files(run_dir: Path, run_id: str) -> None:
    """summary JSON + markdown + a small CSV carrying the marker (in the body)."""
    write_json(run_dir / "metrics_rsi_15window_summary.json", _summary())
    write_markdown(run_dir / "summary.md", "# Summary\n研究用ベースライン (E2E fixture)\n")
    write_markdown(
        run_dir / "rsi_final_decision.md",
        "# 判定\n継続検証候補 (E2E fixture)\n",
    )
    # Marker lives only inside CSV cells; the API never returns CSV bodies.
    write_csv(
        run_dir / "metrics_by_window.csv",
        [
            {"window": "prior_window_1", "completed_trades": 10, "note": CSV_BODY_MARKER},
            {"window": "oos_window_1", "completed_trades": 5, "note": CSV_BODY_MARKER},
        ],
        fieldnames=["window", "completed_trades", "note"],
    )


def create_e2e_report_fixtures(output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> list[str]:
    """Write the 5-run E2E fixture set under output_root; return the run_ids created.

    Read-only with respect to real data: only writes the given output_root. Safe to run
    repeatedly (overwrites the fixture files). Does not touch real analysis_exports/.
    """
    root = ensure_output_dir(output_root)

    # 1. normal run: full read-only safety, valid summary, CSV marker -> SAFE_READ_ONLY
    normal = ensure_output_dir(root / "e2e_normal_run")
    write_json(normal / "manifest.json", _manifest("e2e_normal_run", dict(_SAFE_FLAGS)))
    write_json(normal / "warnings.json", {"fetch_warnings": [], **_SAFE_FLAGS})
    _write_common_files(normal, "e2e_normal_run")

    # 2. error run: no summary JSON -> list_report_index() emits an error row
    error = ensure_output_dir(root / "e2e_error_run")
    write_json(error / "manifest.json", _manifest("e2e_error_run", dict(_SAFE_FLAGS)))
    write_json(error / "warnings.json", {"fetch_warnings": [], **_SAFE_FLAGS})
    # intentionally no metrics_*_summary.json

    # 3. conflict run: manifest vs warnings disagree on real_order -> safety_conflicts
    conflict = ensure_output_dir(root / "e2e_conflict_run")
    conflict_safety = dict(_SAFE_FLAGS)  # real_order=False in manifest
    write_json(conflict / "manifest.json", _manifest("e2e_conflict_run", conflict_safety))
    write_json(
        conflict / "warnings.json",
        {"fetch_warnings": [], **{**_SAFE_FLAGS, "real_order": True}},
    )
    _write_common_files(conflict, "e2e_conflict_run")

    # 4. incomplete run: drop api_key_used from BOTH manifest and warnings -> incomplete
    incomplete = ensure_output_dir(root / "e2e_incomplete_run")
    partial = {k: v for k, v in _SAFE_FLAGS.items() if k != "api_key_used"}
    write_json(incomplete / "manifest.json", _manifest("e2e_incomplete_run", partial))
    write_json(incomplete / "warnings.json", {"fetch_warnings": [], **partial})
    _write_common_files(incomplete, "e2e_incomplete_run")

    return ["e2e_conflict_run", "e2e_error_run", "e2e_incomplete_run", "e2e_normal_run"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate read-only E2E report fixtures.")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Fixture output dir (default: frontend/e2e/fixtures/analysis_exports).",
    )
    args = parser.parse_args()
    run_ids = create_e2e_report_fixtures(args.output_root)
    print(f"Wrote {len(run_ids)} fixture runs to {args.output_root}:")
    for run_id in run_ids:
        print(f"  - {run_id}")


if __name__ == "__main__":
    main()
