"""Script-level guard ordering for the G013 monitor LaunchAgent runner."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from scripts import h11_auto_v4_install_monitor_launchagent as runner_script


def test_gui_domain_refusal_is_retry_safe_before_ledger_begin(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    repository = tmp_path / "repo"
    (repository / "backend").mkdir(parents=True)
    digest = "sha256:" + ("a" * 64)
    generation = SimpleNamespace(
        digest="sha256:" + ("b" * 64),
        implementation_digest=digest,
    )
    reached = {"gate": False, "install": False}

    monkeypatch.setattr(sys, "argv", ["runner", "--repository", str(repository)])
    monkeypatch.setattr(runner_script, "reviewed_files_digest", lambda **_kw: digest)
    monkeypatch.setattr(
        runner_script,
        "load_v4_gmo_frozen_generation",
        lambda **_kw: generation,
    )
    monkeypatch.setattr(
        runner_script,
        "render_v4_gmo_monitor_launchagent",
        lambda **_kw: b"safe-plist",
    )

    def refuse(**_kwargs) -> None:
        raise runner_script.V4GmoLaunchdDomainNotReady(
            "V4_LAUNCHD_GUI_DOMAIN_NOT_READY"
        )

    def gate(**_kwargs):
        reached["gate"] = True
        raise AssertionError("gate must remain unreachable")

    def install(**_kwargs):
        reached["install"] = True
        raise AssertionError("install must remain unreachable")

    monkeypatch.setattr(runner_script, "require_stable_v4_gmo_aqua_domain", refuse)
    monkeypatch.setattr(runner_script, "load_external_preparation_gate", gate)
    monkeypatch.setattr(
        runner_script,
        "install_and_restart_v4_gmo_monitor_launchagent",
        install,
    )

    assert runner_script.main() == 3
    output = capsys.readouterr().out
    assert "GUI_DOMAIN_NOT_READY_RETRY_SAFE" in output
    assert "NO_RETRY" not in output
    assert reached == {"gate": False, "install": False}
    assert list(repository.rglob("*.json")) == []
    assert list(repository.rglob("*.plist")) == []
