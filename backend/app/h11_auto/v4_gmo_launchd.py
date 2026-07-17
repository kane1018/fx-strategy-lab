"""LaunchAgent rendering and finite lifecycle operations for the G013 monitor."""

from __future__ import annotations

import plistlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root

V4_GMO_MONITOR_LABEL = "com.fxstrategylab.h11v4.g013.monitor"


class V4GmoLaunchdError(RuntimeError):
    """Fixed safe LaunchAgent failure."""


@dataclass(frozen=True)
class V4GmoLaunchdResult:
    installed: bool
    bootstrapped: bool
    restarted: bool
    broker_write: bool = False
    actual_post_count: int = 0

    def __bool__(self) -> bool:
        return False


def render_v4_gmo_monitor_launchagent(
    *,
    repository: Path,
    generation: V4GmoFrozenGeneration,
    python_executable: Path,
) -> bytes:
    repository = repository.resolve()
    python_executable = python_executable.resolve()
    if not repository.is_dir() or not python_executable.is_file():
        raise V4GmoLaunchdError("V4_LAUNCHD_PATH_INVALID")
    state_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=generation.digest,
    )
    payload = {
        "Label": V4_GMO_MONITOR_LABEL,
        "ProgramArguments": [
            str(python_executable),
            "-m",
            "scripts.h11_auto_v4_monitor_supervisor",
            "--repository",
            str(repository),
        ],
        "WorkingDirectory": str(repository / "backend"),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "ProcessType": "Background",
        "StandardOutPath": str(state_root / "supervisor.stdout.log"),
        "StandardErrorPath": str(state_root / "supervisor.stderr.log"),
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def install_and_restart_v4_gmo_monitor_launchagent(
    *,
    plist_path: Path,
    plist_content: bytes,
    user_id: int,
    runner: CommandRunner,
) -> V4GmoLaunchdResult:
    """Install one reviewed plist and perform one finite bootstrap/kickstart."""

    if (
        plist_path.name != f"{V4_GMO_MONITOR_LABEL}.plist"
        or plist_path.is_symlink()
        or user_id < 1
        or not plist_content
    ):
        raise V4GmoLaunchdError("V4_LAUNCHD_INSTALL_ARGUMENT_INVALID")
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = plist_path.with_suffix(".plist.tmp")
    temporary.write_bytes(plist_content)
    temporary.replace(plist_path)
    domain = f"gui/{user_id}"
    service = f"{domain}/{V4_GMO_MONITOR_LABEL}"
    bootstrap = runner(["launchctl", "bootstrap", domain, str(plist_path)])
    if bootstrap.returncode != 0:
        raise V4GmoLaunchdError("V4_LAUNCHD_BOOTSTRAP_FAILED")
    kickstart = runner(["launchctl", "kickstart", "-k", service])
    if kickstart.returncode != 0:
        raise V4GmoLaunchdError("V4_LAUNCHD_RESTART_FAILED")
    return V4GmoLaunchdResult(installed=True, bootstrapped=True, restarted=True)
