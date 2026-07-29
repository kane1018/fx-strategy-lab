"""LaunchAgent rendering and install for the unattended live scheduler.

Structural counterpart to ``v4_gmo_launchd.py`` (the G012 monitor
LaunchAgent), but for a genuinely different shape: non-resident, periodic
invocation (design doc §12, Option B -- operator decision 2026-07-24), never
a long-lived daemon. ``KeepAlive`` is always ``False`` and ``StartInterval``
is always set; nothing here ever configures residency.

This module renders the plist and installs/bootstraps it via ``launchctl``
-- it never itself constructs a real credential, HTTP client, or
notification transport, and never itself decides whether an entry is
placed. The plist's ``ProgramArguments`` point at
``h11_auto_v4_unattended_live_scheduled_launcher.py``, whose own
PLACEHOLDER sections gate that.
"""

from __future__ import annotations

import plistlib
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root

V4_GMO_UNATTENDED_SCHEDULER_LABEL = "com.fxstrategylab.h11v4.unattended.scheduler"

# Lower bound keeps a runaway interval from hammering Public/Private API
# cadence limits. Upper bound is capped well below G013's 30-minute signal
# cadence (not just "noticeable within one trading session"): independent
# review noted a 1800s (30-minute) interval could, on unlucky phase
# alignment, fire just after a bar completes and then miss most of that
# entry window before the next tick -- 600s bounds that worst-case lag to a
# fifth of the signal period instead of the whole thing.
MINIMUM_START_INTERVAL_SECONDS = 60
MAXIMUM_START_INTERVAL_SECONDS = 600


class V4GmoUnattendedSchedulerLaunchdError(RuntimeError):
    """Fixed safe scheduler LaunchAgent failure."""


@dataclass(frozen=True)
class V4GmoUnattendedSchedulerLaunchdResult:
    installed: bool
    bootstrapped: bool
    previous_service_present: bool
    previous_service_booted_out: bool
    service_running: bool
    broker_write: bool = False
    actual_post_count: int = 0

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __bool__(self) -> bool:
        return False


def render_v4_gmo_unattended_scheduler_launchagent(
    *,
    repository: Path,
    generation: V4GmoFrozenGeneration,
    python_executable: Path,
    launcher_relative_path: Path = Path(
        "backend/scripts/h11_auto_v4_unattended_live_scheduled_launcher.py"
    ),
    start_interval_seconds: int = 300,
) -> bytes:
    """Render a non-resident, periodic LaunchAgent plist.

    ``KeepAlive`` is always ``False`` -- never the resident-daemon shape.
    ``RunAtLoad: True`` means one tick fires immediately when this plist is
    bootstrapped (not only after the first ``start_interval_seconds`` has
    elapsed), then again every ``start_interval_seconds`` thereafter; each
    invocation is expected to exit on its own, mirroring Phase 1's bounded
    runner precedent applied to a scheduler trigger rather than a daemon.

    The baked ``--expected-reviewed-files-digest``/``--expected-generation-
    digest`` are captured from ``generation`` at render time. Editing the
    launcher script (e.g. to fill in its PLACEHOLDER sections) changes
    ``implementation_digest`` -- the OLD installed plist's baked digest will
    then correctly, but unhelpfully, refuse every tick forever until this
    function is called again with the freshly recomputed generation and the
    LaunchAgent is reinstalled.
    """

    repository = repository.resolve()
    python_executable = python_executable.resolve()
    launcher_path = (repository / launcher_relative_path).resolve()
    if (
        not repository.is_dir()
        or not python_executable.is_file()
        or not launcher_path.is_file()
        or not (
            MINIMUM_START_INTERVAL_SECONDS
            <= start_interval_seconds
            <= MAXIMUM_START_INTERVAL_SECONDS
        )
    ):
        raise V4GmoUnattendedSchedulerLaunchdError(
            "V4_UNATTENDED_SCHEDULER_LAUNCHD_PATH_OR_INTERVAL_INVALID"
        )
    state_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=generation.digest,
    )
    payload = {
        "Label": V4_GMO_UNATTENDED_SCHEDULER_LABEL,
        "ProgramArguments": [
            str(python_executable),
            str(launcher_path),
            "--repository",
            str(repository),
            "--expected-reviewed-files-digest",
            generation.implementation_digest,
            "--expected-generation-digest",
            generation.digest,
        ],
        "WorkingDirectory": str(repository / "backend"),
        "RunAtLoad": True,
        "KeepAlive": False,
        "StartInterval": start_interval_seconds,
        "ProcessType": "Background",
        "StandardOutPath": str(state_root / "unattended-scheduler.stdout.log"),
        "StandardErrorPath": str(state_root / "unattended-scheduler.stderr.log"),
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def install_and_restart_v4_gmo_unattended_scheduler_launchagent(
    *,
    plist_path: Path,
    plist_content: bytes,
    user_id: int,
    runner: CommandRunner,
) -> V4GmoUnattendedSchedulerLaunchdResult:
    """Replace the exact scheduler service once; no heartbeat to wait for.

    Unlike the resident monitor's install (which waits for a fresh
    heartbeat file to prove a live process), a StartInterval job may not
    fire again for up to ``start_interval_seconds`` after bootstrap --
    there is nothing to poll for here. Success means ``launchctl`` accepted
    the plist and reports the service loaded; the first real tick's
    behaviour surfaces later via the launcher's own stdout/stderr log.
    """

    if (
        plist_path.name != f"{V4_GMO_UNATTENDED_SCHEDULER_LABEL}.plist"
        or plist_path.is_symlink()
        or plist_path.parent.is_symlink()
        or user_id < 1
        or not plist_content
    ):
        raise V4GmoUnattendedSchedulerLaunchdError(
            "V4_UNATTENDED_SCHEDULER_LAUNCHD_INSTALL_ARGUMENT_INVALID"
        )
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        parsed = plistlib.loads(plist_content)
        stdout_path = Path(parsed["StandardOutPath"])
        stderr_path = Path(parsed["StandardErrorPath"])
    except (KeyError, TypeError, ValueError, plistlib.InvalidFileException) as error:
        raise V4GmoUnattendedSchedulerLaunchdError(
            "V4_UNATTENDED_SCHEDULER_LAUNCHD_INSTALL_ARGUMENT_INVALID"
        ) from error
    if stdout_path.parent != stderr_path.parent or stdout_path.parent.is_symlink():
        raise V4GmoUnattendedSchedulerLaunchdError(
            "V4_UNATTENDED_SCHEDULER_LAUNCHD_INSTALL_ARGUMENT_INVALID"
        )
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = plist_path.with_suffix(".plist.tmp")
    if temporary.is_symlink():
        raise V4GmoUnattendedSchedulerLaunchdError(
            "V4_UNATTENDED_SCHEDULER_LAUNCHD_INSTALL_ARGUMENT_INVALID"
        )
    temporary.write_bytes(plist_content)
    domain = f"gui/{user_id}"
    service = f"{domain}/{V4_GMO_UNATTENDED_SCHEDULER_LABEL}"
    service_state = runner(["launchctl", "print", service])
    if service_state.returncode not in {0, 113}:
        raise V4GmoUnattendedSchedulerLaunchdError(
            "V4_UNATTENDED_SCHEDULER_LAUNCHD_SERVICE_STATE_UNKNOWN"
        )
    previous_service_present = service_state.returncode == 0
    previous_service_booted_out = False
    if previous_service_present:
        bootout = runner(["launchctl", "bootout", service])
        if bootout.returncode != 0:
            raise V4GmoUnattendedSchedulerLaunchdError(
                "V4_UNATTENDED_SCHEDULER_LAUNCHD_BOOTOUT_FAILED"
            )
        previous_service_booted_out = True
    temporary.replace(plist_path)
    bootstrap = runner(["launchctl", "bootstrap", domain, str(plist_path)])
    if bootstrap.returncode != 0:
        raise V4GmoUnattendedSchedulerLaunchdError(
            "V4_UNATTENDED_SCHEDULER_LAUNCHD_BOOTSTRAP_FAILED"
        )
    service_after_bootstrap = runner(["launchctl", "print", service])
    if service_after_bootstrap.returncode != 0:
        raise V4GmoUnattendedSchedulerLaunchdError(
            "V4_UNATTENDED_SCHEDULER_LAUNCHD_SERVICE_NOT_RUNNING"
        )
    return V4GmoUnattendedSchedulerLaunchdResult(
        installed=True,
        bootstrapped=True,
        previous_service_present=previous_service_present,
        previous_service_booted_out=previous_service_booted_out,
        service_running=True,
    )
