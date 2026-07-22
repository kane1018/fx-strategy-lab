"""LaunchAgent rendering and finite lifecycle operations for the G013 monitor."""

from __future__ import annotations

import json
import plistlib
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root

V4_GMO_MONITOR_LABEL = "com.fxstrategylab.h11v4.g013.monitor"


class V4GmoLaunchdError(RuntimeError):
    """Fixed safe LaunchAgent failure."""


class V4GmoLaunchdDomainNotReady(V4GmoLaunchdError):
    """Retry-safe refusal before the operation 60 marker is claimed."""


@dataclass(frozen=True)
class V4GmoLaunchdResult:
    installed: bool
    bootstrapped: bool
    restarted: bool
    previous_service_present: bool
    previous_service_booted_out: bool
    service_running: bool
    heartbeat_fresh: bool
    heartbeat_generation_digest_match: bool
    heartbeat_waiting_for_canonical_runtime: bool
    heartbeat_broker_read: bool
    heartbeat_broker_write: bool
    raw_output_retained: bool = False
    broker_write: bool = False
    actual_post_count: int = 0

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

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
            "--expected-reviewed-files-digest",
            generation.implementation_digest,
            "--expected-generation-digest",
            generation.digest,
        ],
        "WorkingDirectory": str(repository / "backend"),
        "RunAtLoad": True,
        "KeepAlive": False,
        "ThrottleInterval": 30,
        "ProcessType": "Background",
        "StandardOutPath": str(state_root / "supervisor.stdout.log"),
        "StandardErrorPath": str(state_root / "supervisor.stderr.log"),
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
WallClock = Callable[[], datetime]
MonotonicClock = Callable[[], float]
Wait = Callable[[float], None]


def require_stable_v4_gmo_aqua_domain(
    *,
    user_id: int,
    runner: CommandRunner,
) -> None:
    """Fail closed before op60 if the GUI login domain is still transitioning."""

    if user_id < 1:
        raise V4GmoLaunchdDomainNotReady("V4_LAUNCHD_GUI_DOMAIN_NOT_READY")
    try:
        state = runner(["launchctl", "print", f"gui/{user_id}"])
    except (OSError, subprocess.TimeoutExpired) as error:
        raise V4GmoLaunchdDomainNotReady(
            "V4_LAUNCHD_GUI_DOMAIN_NOT_READY"
        ) from error
    required_markers = (
        "type = login",
        "session = Aqua",
        "auxiliary bootstrapper = com.apple.xpc.otherbsd (complete)",
        "properties = gui | gui login",
    )
    if (
        state.returncode != 0
        or not state.stdout
        or any(marker not in state.stdout for marker in required_markers)
    ):
        raise V4GmoLaunchdDomainNotReady("V4_LAUNCHD_GUI_DOMAIN_NOT_READY")


def install_and_restart_v4_gmo_monitor_launchagent(
    *,
    plist_path: Path,
    plist_content: bytes,
    user_id: int,
    runner: CommandRunner,
    heartbeat_path: Path,
    expected_generation_digest: str,
    wall_clock: WallClock = lambda: datetime.now(UTC),
    monotonic_clock: MonotonicClock = time.monotonic,
    wait: Wait = time.sleep,
    heartbeat_timeout_seconds: float = 50.0,
) -> V4GmoLaunchdResult:
    """Replace the exact monitor service once and prove a fresh safe heartbeat."""

    if (
        plist_path.name != f"{V4_GMO_MONITOR_LABEL}.plist"
        or plist_path.is_symlink()
        or plist_path.parent.is_symlink()
        or user_id < 1
        or not plist_content
        or heartbeat_path.name != "supervisor-heartbeat.json"
        or heartbeat_path.is_symlink()
        or heartbeat_path.parent.is_symlink()
        or not expected_generation_digest.startswith("sha256:")
        or len(expected_generation_digest.removeprefix("sha256:")) != 64
        or not 0 < heartbeat_timeout_seconds <= 60.0
    ):
        raise V4GmoLaunchdError("V4_LAUNCHD_INSTALL_ARGUMENT_INVALID")
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = plist_path.with_suffix(".plist.tmp")
    if temporary.is_symlink():
        raise V4GmoLaunchdError("V4_LAUNCHD_INSTALL_ARGUMENT_INVALID")
    temporary.write_bytes(plist_content)
    domain = f"gui/{user_id}"
    service = f"{domain}/{V4_GMO_MONITOR_LABEL}"
    service_state = runner(["launchctl", "print", service])
    if service_state.returncode not in {0, 113}:
        raise V4GmoLaunchdError("V4_LAUNCHD_SERVICE_STATE_UNKNOWN")
    previous_service_present = service_state.returncode == 0
    previous_service_booted_out = False
    if previous_service_present:
        bootout = runner(["launchctl", "bootout", service])
        if bootout.returncode != 0:
            raise V4GmoLaunchdError("V4_LAUNCHD_BOOTOUT_FAILED")
        previous_service_booted_out = True
    temporary.replace(plist_path)
    try:
        previous_heartbeat_mtime_ns = heartbeat_path.stat().st_mtime_ns
    except FileNotFoundError:
        previous_heartbeat_mtime_ns = None
    except OSError as error:
        raise V4GmoLaunchdError("V4_LAUNCHD_HEARTBEAT_STATE_UNKNOWN") from error
    bootstrap_started_at = wall_clock().astimezone(UTC)
    bootstrap = runner(["launchctl", "bootstrap", domain, str(plist_path)])
    if bootstrap.returncode != 0:
        raise V4GmoLaunchdError("V4_LAUNCHD_BOOTSTRAP_FAILED")
    service_after_bootstrap = runner(["launchctl", "print", service])
    if service_after_bootstrap.returncode != 0:
        raise V4GmoLaunchdError("V4_LAUNCHD_SERVICE_NOT_RUNNING")
    deadline = monotonic_clock() + heartbeat_timeout_seconds
    heartbeat: dict[str, object] | None = None
    while monotonic_clock() < deadline:
        try:
            candidate = json.loads(heartbeat_path.read_text(encoding="utf-8"))
            candidate_mtime_ns = heartbeat_path.stat().st_mtime_ns
            observed = datetime.fromisoformat(str(candidate["observed_at_utc"]))
        except (OSError, ValueError, KeyError, json.JSONDecodeError, TypeError):
            wait(0.25)
            continue
        age_seconds = (
            wall_clock().astimezone(UTC) - observed.astimezone(UTC)
        ).total_seconds()
        if (
            0 <= age_seconds <= 60
            and observed.astimezone(UTC) >= bootstrap_started_at
            and (
                previous_heartbeat_mtime_ns is None
                or candidate_mtime_ns > previous_heartbeat_mtime_ns
            )
            and candidate.get("generation_digest") == expected_generation_digest
            and candidate.get("status") == "WAITING_FOR_CANONICAL_RUNTIME"
            and candidate.get("generation_bound") is False
            and candidate.get("cycle_present") is False
            and candidate.get("broker_read") is False
            and candidate.get("broker_write") is False
            and candidate.get("actual_post_count") == 0
        ):
            heartbeat = candidate
            break
        wait(0.25)
    if heartbeat is None:
        raise V4GmoLaunchdError("V4_LAUNCHD_HEARTBEAT_NOT_CLEAR")
    return V4GmoLaunchdResult(
        installed=True,
        bootstrapped=True,
        restarted=True,
        previous_service_present=previous_service_present,
        previous_service_booted_out=previous_service_booted_out,
        service_running=True,
        heartbeat_fresh=True,
        heartbeat_generation_digest_match=True,
        heartbeat_waiting_for_canonical_runtime=True,
        heartbeat_broker_read=False,
        heartbeat_broker_write=False,
    )
