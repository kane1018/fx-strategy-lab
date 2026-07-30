"""Script-level guard ordering for the unattended scheduler LaunchAgent installer."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

from scripts import (
    h11_auto_v4_install_monitor_launchagent as monitor_installer_script,
)
from scripts import (
    h11_auto_v4_install_unattended_live_scheduler_launchagent as installer_script,
)


def test_launchctl_runner_uses_phase_specific_timeouts(monkeypatch) -> None:
    observed: list[tuple[list[str], float]] = []

    def fake_run(command, **kwargs):
        observed.append((command, kwargs["timeout"]))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(installer_script.subprocess, "run", fake_run)

    for action in ("print", "bootout", "bootstrap"):
        result = installer_script._run(["launchctl", action, "safe-target"])
        assert result.returncode == 0

    assert observed == [
        (["launchctl", "print", "safe-target"], 15.0),
        (["launchctl", "bootout", "safe-target"], 30.0),
        (["launchctl", "bootstrap", "safe-target"], 30.0),
    ]


def test_launchctl_runner_rejects_unknown_action_without_subprocess(monkeypatch) -> None:
    monkeypatch.setattr(
        installer_script.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unknown launchctl action must not execute")
        ),
    )

    result = installer_script._run(["launchctl", "kickstart", "safe-target"])

    assert result.returncode == 126
    assert result.stdout == ""
    assert result.stderr == ""


def test_g052_startup_probe_does_not_hold_installer_process_lock() -> None:
    assert (
        monitor_installer_script._startup_probe_requires_installer_process_lock(
            "H11_AUTO_30M_20260730_G052"
        )
        is False
    )
    assert (
        monitor_installer_script._startup_probe_requires_installer_process_lock(
            "H11_AUTO_30M_20260730_G051"
        )
        is True
    )


def test_g052_claims_operation_60_before_runtime_startup_probe() -> None:
    source = inspect.getsource(monitor_installer_script.main)
    assert source.index("begin_g052_flat_only_monitor") < source.index(
        "_probe_g040_launchd_runtime_startup"
    )
    assert source.index("begin_g052_flat_only_monitor") < source.index(
        "MONITOR_LAUNCHAGENT_RUNTIME_STARTUP_BLOCKED_NO_RETRY"
    )


def test_gui_domain_refusal_is_retry_safe_before_install(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    repository = tmp_path / "repo"
    (repository / "backend").mkdir(parents=True)
    digest = "sha256:" + ("a" * 64)
    generation = SimpleNamespace(digest="sha256:" + ("b" * 64), implementation_digest=digest)
    reached = {"install": False}

    monkeypatch.setattr(
        sys, "argv", ["installer", "--repository", str(repository)]
    )
    monkeypatch.setattr(installer_script, "reviewed_files_digest", lambda **_kw: digest)
    monkeypatch.setattr(
        installer_script, "load_v4_gmo_frozen_generation", lambda **_kw: generation
    )
    monkeypatch.setattr(
        installer_script,
        "render_v4_gmo_unattended_scheduler_launchagent",
        lambda **_kw: b"safe-plist",
    )

    def refuse(**_kwargs) -> None:
        raise installer_script.V4GmoLaunchdDomainNotReady("V4_LAUNCHD_GUI_DOMAIN_NOT_READY")

    def install(**_kwargs):
        reached["install"] = True
        raise AssertionError("install must remain unreachable")

    monkeypatch.setattr(installer_script, "require_stable_v4_gmo_aqua_domain", refuse)
    monkeypatch.setattr(
        installer_script,
        "install_and_restart_v4_gmo_unattended_scheduler_launchagent",
        install,
    )

    assert installer_script.main() == 3
    output = capsys.readouterr().out
    assert "GUI_DOMAIN_NOT_READY_RETRY_SAFE" in output
    assert "NO_RETRY" not in output
    assert reached == {"install": False}
    assert list(repository.rglob("*.plist")) == []


def test_g039_requires_completed_preparation_before_render_or_launchctl(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    repository = tmp_path / "repo"
    (repository / "backend").mkdir(parents=True)
    digest = "sha256:" + ("a" * 64)
    generation = SimpleNamespace(
        digest="sha256:" + ("b" * 64),
        implementation_digest=digest,
        generation_label="H11_AUTO_30M_20260729_G039",
    )
    reached = {"render": False, "launchctl": False}

    monkeypatch.setattr(
        sys, "argv", ["installer", "--repository", str(repository)]
    )
    monkeypatch.setattr(installer_script, "reviewed_files_digest", lambda **_kw: digest)
    monkeypatch.setattr(
        installer_script, "load_v4_gmo_frozen_generation", lambda **_kw: generation
    )
    monkeypatch.setattr(
        installer_script,
        "load_external_preparation_gate",
        lambda **_kw: (_ for _ in ()).throw(
            installer_script.V4ActualPreparationGuardError(
                "PREPARATION_SEQUENCE_NOT_COMPLETE"
            )
        ),
    )
    monkeypatch.setattr(
        installer_script,
        "render_v4_gmo_unattended_scheduler_launchagent",
        lambda **_kw: reached.__setitem__("render", True),
    )
    monkeypatch.setattr(
        installer_script,
        "require_stable_v4_gmo_aqua_domain",
        lambda **_kw: reached.__setitem__("launchctl", True),
    )

    assert installer_script.main() == 2
    output = capsys.readouterr().out
    assert "UNATTENDED_SCHEDULER_PREPARATION_NOT_CLEAR" in output
    assert "broker_write=false" in output
    assert reached == {"render": False, "launchctl": False}


def test_successful_install_prints_broker_write_false(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    repository = tmp_path / "repo"
    (repository / "backend").mkdir(parents=True)
    digest = "sha256:" + ("a" * 64)
    generation = SimpleNamespace(digest="sha256:" + ("b" * 64), implementation_digest=digest)

    monkeypatch.setattr(
        sys, "argv", ["installer", "--repository", str(repository)]
    )
    monkeypatch.setattr(installer_script, "reviewed_files_digest", lambda **_kw: digest)
    monkeypatch.setattr(
        installer_script, "load_v4_gmo_frozen_generation", lambda **_kw: generation
    )
    monkeypatch.setattr(
        installer_script,
        "render_v4_gmo_unattended_scheduler_launchagent",
        lambda **_kw: b"safe-plist",
    )
    monkeypatch.setattr(
        installer_script, "require_stable_v4_gmo_aqua_domain", lambda **_kw: None
    )
    monkeypatch.setattr(
        installer_script,
        "install_and_restart_v4_gmo_unattended_scheduler_launchagent",
        lambda **_kw: SimpleNamespace(
            to_safe_dict=lambda: {"broker_write": False, "actual_post_count": 0}
        ),
    )

    assert installer_script.main() == 0
    output = capsys.readouterr().out
    assert "INSTALLED_RESTARTED_UNATTENDED_SCHEDULER" in output
    assert "broker_write=false" in output
    assert "actual_post_count=0" in output
