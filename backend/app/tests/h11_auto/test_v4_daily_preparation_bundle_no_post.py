"""Fake-only tests for the daily preparation bundler's stage/order logic.

Never invokes a real subprocess -- ``subprocess.run`` is monkeypatched in
every test, so no real Pushover/SMTP send, Private API call, or
LaunchAgent install can occur here.
"""

from __future__ import annotations

from types import SimpleNamespace

from scripts import h11_auto_v4_daily_preparation_bundle as bundle


def test_stage_1_runs_presence_keychain_pushover_smtp_in_order(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(bundle.subprocess, "run", fake_run)
    exit_code = bundle.main(["--stage", "1"])

    assert exit_code == 0
    modules = [command[2] for command in calls]
    assert modules == [
        "scripts.h11_auto_v4_actual_preparation_presence",
        "scripts.h11_auto_v4_keychain_access_rehearsal",
        "scripts.h11_auto_v4_pushover_rehearsal",
        "scripts.h11_auto_v4_smtp_rehearsal",
    ]


def test_stage_2_runs_network_time_then_host_kill(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(bundle.subprocess, "run", fake_run)
    exit_code = bundle.main(["--stage", "2"])

    assert exit_code == 0
    modules = [command[2] for command in calls]
    assert modules == [
        "scripts.h11_auto_v4_network_time_preflight",
        "scripts.h11_auto_v4_actual_host_kill_rehearsal",
    ]


def test_stage_3_passes_repository_to_monitor_launchagent(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(bundle.subprocess, "run", fake_run)
    exit_code = bundle.main(["--stage", "3"])

    assert exit_code == 0
    modules = [command[2] for command in calls]
    assert modules == [
        "scripts.h11_auto_v4_public_get_preflight",
        "scripts.h11_auto_v4_private_get_preflight",
        "scripts.h11_auto_v4_install_monitor_launchagent",
    ]
    last_command = calls[-1]
    assert last_command[3:] == ["--repository", str(bundle.REPOSITORY)]


def test_stage_stops_at_first_failure_and_does_not_run_remaining_steps(
    monkeypatch,
    capsys,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        # Fail on the second step (keychain_access); pushover/smtp must
        # never be attempted afterward.
        if "h11_auto_v4_keychain_access_rehearsal" in command[2]:
            return SimpleNamespace(returncode=2)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(bundle.subprocess, "run", fake_run)
    exit_code = bundle.main(["--stage", "1"])

    assert exit_code == 2
    modules = [command[2] for command in calls]
    assert modules == [
        "scripts.h11_auto_v4_actual_preparation_presence",
        "scripts.h11_auto_v4_keychain_access_rehearsal",
    ]
    output = capsys.readouterr().out
    assert "reviewed corrective generation" in output
    assert "restarts external preparation at operation 00" in output
    assert "still retryable today" not in output
    assert "Do not infer success from ALREADY_ATTEMPTED" in output


def test_stage_1_success_prints_next_manual_step(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        bundle.subprocess, "run", lambda *_a, **_kw: SimpleNamespace(returncode=0)
    )
    bundle.main(["--stage", "1"])
    output = capsys.readouterr().out
    assert "h11_auto_v4_email_delivery_confirm" in output


def test_stage_2_success_prints_next_manual_step(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        bundle.subprocess, "run", lambda *_a, **_kw: SimpleNamespace(returncode=0)
    )
    bundle.main(["--stage", "2"])
    output = capsys.readouterr().out
    assert "GUI-capable escalated Codex execution context" in output
    assert "h11_auto_v4_exclusivity_confirm" in output


def test_stage_3_success_prints_completion_message(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        bundle.subprocess, "run", lambda *_a, **_kw: SimpleNamespace(returncode=0)
    )
    bundle.main(["--stage", "3"])
    output = capsys.readouterr().out
    assert "complete for today" in output
