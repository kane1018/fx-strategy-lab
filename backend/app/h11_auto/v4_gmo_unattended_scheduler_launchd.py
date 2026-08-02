"""LaunchAgent rendering and install for the unattended live scheduler.

Structural counterpart to ``v4_gmo_launchd.py`` (the G012 monitor
LaunchAgent). Legacy generations use non-resident periodic invocation;
G064 is the explicit resident-runtime exception: it is started once with
``RunAtLoad`` and remains resident under its own loop. ``KeepAlive=false`` and
no ``StartInterval`` ensure a HALT exit cannot be relaunched.
No other generation is made resident here.

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
    """Render a generation-bound scheduler plist.

    Legacy generations remain non-resident periodic jobs. G064 is the single
    reviewed resident exception: its worker owns the process lock, keeps a
    15-second heartbeat, and fails closed on runtime exceptions.

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
    if generation.generation_label == "H11_AUTO_30M_20260802_G066":
        launcher_path = (
            repository / "backend/scripts/h11_auto_v4_g066_runtime_bootstrap_no_post.py"
        ).resolve()
    if generation.generation_label == "H11_AUTO_30M_20260802_G067":
        launcher_path = (
            repository / "backend/scripts/h11_auto_v4_g067_runtime_bootstrap_no_post.py"
        ).resolve()
    if generation.generation_label == "H11_AUTO_30M_20260802_G068":
        launcher_path = (
            repository / "backend/scripts/h11_auto_v4_g068_runtime_bootstrap_no_post.py"
        ).resolve()
    if generation.generation_label == "H11_AUTO_30M_20260802_G069":
        launcher_path = (
            repository / "backend/scripts/h11_auto_v4_g069_runtime_bootstrap_no_post.py"
        ).resolve()
    if generation.generation_label == "H11_AUTO_30M_20260802_G070":
        launcher_path = (
            repository / "backend/scripts/h11_auto_v4_g070_runtime_bootstrap_no_post.py"
        ).resolve()
    if generation.generation_label == "H11_AUTO_30M_20260802_G071":
        launcher_path = (
            repository / "backend/scripts/h11_auto_v4_g071_runtime_bootstrap_no_post.py"
        ).resolve()
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
    resident = generation.generation_label in {
        "H11_AUTO_30M_20260801_G064",
        "H11_AUTO_30M_20260801_G065",
        "H11_AUTO_30M_20260802_G066",
        "H11_AUTO_30M_20260802_G067",
        "H11_AUTO_30M_20260802_G068",
        "H11_AUTO_30M_20260802_G069",
        "H11_AUTO_30M_20260802_G070",
        "H11_AUTO_30M_20260802_G071",
    }
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
        "ProcessType": "Background",
        "StandardOutPath": str(state_root / "unattended-scheduler.stdout.log"),
        "StandardErrorPath": str(state_root / "unattended-scheduler.stderr.log"),
    }
    if not resident:
        payload["StartInterval"] = start_interval_seconds
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
    arguments = parsed.get("ProgramArguments")
    if parsed.get("KeepAlive") is True and isinstance(arguments, list):
        try:
            arguments.index("--repository")
            arguments.index("--expected-reviewed-files-digest")
            arguments.index("--expected-generation-digest")
        except (IndexError, TypeError, ValueError):
            raise V4GmoUnattendedSchedulerLaunchdError(
                "V4_UNATTENDED_SCHEDULER_LAUNCHD_ARGUMENTS_INVALID"
            ) from None
        # The resident worker writes scheduler-service-state.json with its own
        # PID. The installer must never publish its installer PID as runtime
        # evidence; readiness polling waits for the worker-owned evidence.
    return V4GmoUnattendedSchedulerLaunchdResult(
        installed=True,
        bootstrapped=True,
        previous_service_present=previous_service_present,
        previous_service_booted_out=previous_service_booted_out,
        service_running=True,
    )
