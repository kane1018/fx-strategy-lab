"""Install and restart the reviewed monitor-only G013 LaunchAgent."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import reviewed_files_digest
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_launchd import (
    V4_GMO_MONITOR_LABEL,
    install_and_restart_v4_gmo_monitor_launchagent,
    render_v4_gmo_monitor_launchagent,
)


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=15.0,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    digest = reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=digest,
    )
    content = render_v4_gmo_monitor_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
    )
    plist_path = (
        Path.home() / "Library" / "LaunchAgents" / f"{V4_GMO_MONITOR_LABEL}.plist"
    )
    result = install_and_restart_v4_gmo_monitor_launchagent(
        plist_path=plist_path,
        plist_content=content,
        user_id=os.getuid(),
        runner=_run,
    )
    print(
        "status=INSTALLED_RESTARTED_MONITOR_ONLY "
        f"broker_write={str(result.broker_write).lower()} "
        f"actual_post_count={result.actual_post_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
