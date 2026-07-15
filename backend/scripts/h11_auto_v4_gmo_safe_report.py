"""Render a read-only safe aggregate for relaxed GMO v4 state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.h11_auto.v4_gmo_report import (
    V4GmoReportError,
    render_v4_gmo_report_markdown,
    summarize_v4_gmo_state_no_post,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        report = summarize_v4_gmo_state_no_post(args.state)
    except V4GmoReportError as error:
        print(f"V4_GMO_REPORT_BLOCKED: {error}")
        return 2
    if args.format == "markdown":
        print(render_v4_gmo_report_markdown(report))
    else:
        print(
            json.dumps(
                report.to_safe_dict(),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
