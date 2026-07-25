"""Fake-only render/install tests for the unattended live scheduler LaunchAgent."""

from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

from app.h11_auto.v4_activation_preparation import V4ApprovedOperatorSelections
from app.h11_auto.v4_gmo_contracts import V4GmoExecutionPolicy
from app.h11_auto.v4_gmo_generation import build_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_gmo_unattended_scheduler_launchd import (
    MAXIMUM_START_INTERVAL_SECONDS,
    MINIMUM_START_INTERVAL_SECONDS,
    V4_GMO_UNATTENDED_SCHEDULER_LABEL,
    V4GmoUnattendedSchedulerLaunchdError,
    install_and_restart_v4_gmo_unattended_scheduler_launchagent,
    render_v4_gmo_unattended_scheduler_launchagent,
)

IMPLEMENTATION_DIGEST = "sha256:" + "d" * 64


def _policy() -> V4GmoExecutionPolicy:
    selected = V4ApprovedOperatorSelections()
    return V4GmoExecutionPolicy(
        strategy_version=selected.strategy_version,
        signal_config_hash=selected.signal_config_hash,
        selected_horizon=selected.selected_horizon,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
        max_entries_per_day=selected.maximum_entries_per_day,
    )


def _generation():
    return build_v4_gmo_frozen_generation(
        generation_label="H11_AUTO_30M_20260716_SCHED_TEST",
        implementation_digest=IMPLEMENTATION_DIGEST,
        policy=_policy(),
    )


def _repository(tmp_path: Path, *, launcher_present: bool = True) -> Path:
    repository = tmp_path / "repo"
    launcher = (
        repository
        / "backend/scripts/h11_auto_v4_unattended_live_scheduled_launcher.py"
    )
    if launcher_present:
        launcher.parent.mkdir(parents=True, exist_ok=True)
        launcher.write_text("# fake launcher placeholder\n")
    else:
        (repository / "backend").mkdir(parents=True, exist_ok=True)
    return repository


def test_render_is_non_resident_start_interval_only_no_forbidden_tokens(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    generation = _generation()
    content = render_v4_gmo_unattended_scheduler_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
        start_interval_seconds=120,
    )
    payload = plistlib.loads(content)
    joined = " ".join(payload["ProgramArguments"])
    arguments = payload["ProgramArguments"]

    assert payload["Label"] == V4_GMO_UNATTENDED_SCHEDULER_LABEL
    assert payload["KeepAlive"] is False
    assert payload["StartInterval"] == 120
    # RunAtLoad is intentionally True (fires one tick immediately at
    # bootstrap, not only after the first interval) -- not asserting this
    # would leave residency-adjacent settings only half-pinned.
    assert payload["RunAtLoad"] is True
    assert "h11_auto_v4_unattended_live_scheduled_launcher.py" in joined
    assert arguments[arguments.index("--expected-reviewed-files-digest") + 1] == (
        IMPLEMENTATION_DIGEST
    )
    assert arguments[arguments.index("--expected-generation-digest") + 1] == (
        generation.digest
    )
    for forbidden in ("credential", "api-key", "order", "POST", "secret", "keychain"):
        assert forbidden not in joined.lower()


def test_render_rejects_start_interval_outside_bounds(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    generation = _generation()
    with pytest.raises(V4GmoUnattendedSchedulerLaunchdError):
        render_v4_gmo_unattended_scheduler_launchagent(
            repository=repository,
            generation=generation,
            python_executable=Path(sys.executable),
            start_interval_seconds=MINIMUM_START_INTERVAL_SECONDS - 1,
        )
    with pytest.raises(V4GmoUnattendedSchedulerLaunchdError):
        render_v4_gmo_unattended_scheduler_launchagent(
            repository=repository,
            generation=generation,
            python_executable=Path(sys.executable),
            start_interval_seconds=MAXIMUM_START_INTERVAL_SECONDS + 1,
        )
    # Both bounds accepted.
    render_v4_gmo_unattended_scheduler_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
        start_interval_seconds=MINIMUM_START_INTERVAL_SECONDS,
    )
    render_v4_gmo_unattended_scheduler_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
        start_interval_seconds=MAXIMUM_START_INTERVAL_SECONDS,
    )


def test_render_rejects_missing_launcher_script(tmp_path: Path) -> None:
    repository = _repository(tmp_path, launcher_present=False)
    generation = _generation()
    with pytest.raises(V4GmoUnattendedSchedulerLaunchdError):
        render_v4_gmo_unattended_scheduler_launchagent(
            repository=repository,
            generation=generation,
            python_executable=Path(sys.executable),
        )


def test_install_boots_out_existing_service_once_before_bootstrap(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    generation = _generation()
    content = render_v4_gmo_unattended_scheduler_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
    )
    calls: list[list[str]] = []
    print_count = 0

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal print_count
        calls.append(command)
        if command[1] == "print":
            print_count += 1
            return subprocess.CompletedProcess(
                command, 0 if print_count > 1 else 0, "", ""
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    result = install_and_restart_v4_gmo_unattended_scheduler_launchagent(
        plist_path=(
            tmp_path / "LaunchAgents" / f"{V4_GMO_UNATTENDED_SCHEDULER_LABEL}.plist"
        ),
        plist_content=content,
        user_id=501,
        runner=runner,
    )
    assert result.installed is True
    assert result.bootstrapped is True
    assert result.previous_service_present is True
    assert result.previous_service_booted_out is True
    assert result.service_running is True
    assert result.broker_write is False
    assert result.actual_post_count == 0
    assert [command[1] for command in calls] == [
        "print",
        "bootout",
        "bootstrap",
        "print",
    ]


def test_install_skips_bootout_when_no_previous_service(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    generation = _generation()
    content = render_v4_gmo_unattended_scheduler_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
    )
    calls: list[list[str]] = []
    print_count = 0

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        nonlocal print_count
        calls.append(command)
        if command[1] == "print":
            print_count += 1
            return subprocess.CompletedProcess(
                command, 113 if print_count == 1 else 0, "", ""
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    result = install_and_restart_v4_gmo_unattended_scheduler_launchagent(
        plist_path=(
            tmp_path / "LaunchAgents" / f"{V4_GMO_UNATTENDED_SCHEDULER_LABEL}.plist"
        ),
        plist_content=content,
        user_id=501,
        runner=runner,
    )
    assert result.previous_service_present is False
    assert result.previous_service_booted_out is False
    assert [command[1] for command in calls] == ["print", "bootstrap", "print"]


def test_install_rejects_wrong_plist_filename(tmp_path: Path) -> None:
    with pytest.raises(V4GmoUnattendedSchedulerLaunchdError):
        install_and_restart_v4_gmo_unattended_scheduler_launchagent(
            plist_path=tmp_path / "wrong-name.plist",
            plist_content=b"irrelevant",
            user_id=501,
            runner=lambda _command: subprocess.CompletedProcess([], 0, "", ""),
        )


def test_install_rejects_bootstrap_failure(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    generation = _generation()
    content = render_v4_gmo_unattended_scheduler_launchagent(
        repository=repository,
        generation=generation,
        python_executable=Path(sys.executable),
    )

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[1] == "bootstrap":
            return subprocess.CompletedProcess(command, 1, "", "boom")
        return subprocess.CompletedProcess(command, 113, "", "")

    with pytest.raises(V4GmoUnattendedSchedulerLaunchdError):
        install_and_restart_v4_gmo_unattended_scheduler_launchagent(
            plist_path=(
                tmp_path / "LaunchAgents" / f"{V4_GMO_UNATTENDED_SCHEDULER_LABEL}.plist"
            ),
            plist_content=content,
            user_id=501,
            runner=runner,
        )
