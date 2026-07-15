"""Render daily/weekly safe aggregates from H11 auto local state."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from app.h11_auto.report import (
    H11AutoReportError,
    render_h11_auto_report_markdown,
    summarize_h11_auto_state,
)


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="H-11 auto Phase B safe-aggregate report (read-only)"
    )
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--since-jst", type=_date)
    parser.add_argument("--until-jst", type=_date)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    try:
        report = summarize_h11_auto_state(
            args.state,
            since_jst=args.since_jst,
            until_jst=args.until_jst,
        )
    except H11AutoReportError as error:
        print(f"REPORT_BLOCKED: {error}")
        return 2
    if args.format == "json":
        print(json.dumps(report.to_safe_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(render_h11_auto_report_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
