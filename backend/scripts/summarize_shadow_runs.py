"""Local CLI: aggregate shadow-run summaries under shadow_exports/ (Phase 2D).

Reads every <input-root>/<run_id>/summary.json, totals/groups them, flags safety
violations, and prints Markdown (default) or writes Markdown+CSV to --out. NO network,
NO API key / secret / .env, NO orders. Inputs and outputs are gitignored — never commit.

Usage:
    python -m scripts.summarize_shadow_runs --input-root shadow_exports
    python -m scripts.summarize_shadow_runs --input-root shadow_exports --format markdown
    python -m scripts.summarize_shadow_runs --input-root shadow_exports --format csv \
        --out shadow_exports/aggregate
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.shadow.aggregate import (
    aggregate_summaries,
    load_run_summaries,
    render_group_csv,
    render_markdown,
    render_runs_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate local shadow-run summaries (read-only, no network)."
    )
    parser.add_argument(
        "--input-root", default="shadow_exports", help="dir with <run_id>/summary.json"
    )
    parser.add_argument("--format", choices=["markdown", "csv"], default="markdown")
    parser.add_argument("--out", default=None, help="output dir (gitignored). default: stdout")
    args = parser.parse_args()

    try:
        summaries, broken = load_run_summaries(args.input_root)
    except FileNotFoundError as error:
        print(f"ERROR: {error}")
        return 1

    if not summaries:
        print(f"No shadow runs found under {args.input_root} (broken/skipped: {len(broken)}).")
        return 0

    agg = aggregate_summaries(summaries)

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "aggregate.json").write_text(json.dumps(agg, ensure_ascii=False, indent=2))
        (out_dir / "aggregate.md").write_text(render_markdown(agg, summaries, broken))
        (out_dir / "runs.csv").write_text(render_runs_csv(summaries))
        (out_dir / "by_symbol.csv").write_text(render_group_csv(agg["by_symbol"], "symbol"))
        (out_dir / "by_date.csv").write_text(render_group_csv(agg["by_date"], "date"))
        print(f"wrote aggregate to {out_dir}/")
        print("files: aggregate.json, aggregate.md, runs.csv, by_symbol.csv, by_date.csv")
    elif args.format == "csv":
        print(render_runs_csv(summaries), end="")
    else:
        print(render_markdown(agg, summaries, broken))

    if agg["safety_violation_runs_count"]:
        print(f"WARNING: {agg['safety_violation_runs_count']} run(s) with safety violations")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
