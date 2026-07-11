"""Render the H-11 v2 Stage 1 journal as safe aggregates only.

Usage from backend/:
    python -m scripts.h11_stage1_review_report
    python -m scripts.h11_stage1_review_report --since-jst 2026-07-13 --until-jst 2026-07-17
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from app.services.h11_stage1_review_report import (
    H11Stage1ReviewReportError,
    render_h11_stage1_report_markdown,
    summarize_h11_stage1_journal,
)

DEFAULT_JOURNAL_PATH = Path("market_data/h11_stage1_journal.jsonl")


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="H-11 Stage 1 safe-aggregate review report (read-only)"
    )
    parser.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL_PATH)
    parser.add_argument("--since-jst", type=_date)
    parser.add_argument("--until-jst", type=_date)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)

    try:
        summary = summarize_h11_stage1_journal(
            args.journal,
            since_jst=args.since_jst,
            until_jst=args.until_jst,
        )
    except H11Stage1ReviewReportError as error:
        print(f"REPORT_BLOCKED: {error}")
        return 2

    if args.format == "json":
        print(json.dumps(summary.to_safe_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(render_h11_stage1_report_markdown(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
