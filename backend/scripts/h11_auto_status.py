"""Print one safe H11 auto status snapshot; never starts a server."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.h11_auto.report import H11AutoReportError
from app.h11_auto.status import project_h11_auto_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="H-11 auto one-shot local status projection (read-only)"
    )
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        projection = project_h11_auto_status(args.state)
    except H11AutoReportError as error:
        print(f"STATUS_BLOCKED: {error}")
        return 2
    print(
        json.dumps(
            projection.to_safe_dict(),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
