"""Script-level guard ordering for the G013 monitor LaunchAgent runner."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from scripts import h11_auto_v4_install_monitor_launchagent as runner_script


def test_launchctl_runner_uses_phase_specific_timeouts(monkeypatch) -> None:
    observed: list[tuple[list[str], float]] = []

    def fake_run(command, **kwargs):
        observed.append((command, kwargs["timeout"]))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner_script.subprocess, "run", fake_run)

    for action in ("print", "bootout", "bootstrap"):
        result = runner_script._run(["launchctl", action, "safe-target"])
        assert result.returncode == 0

    assert observed == [
        (["launchctl", "print", "safe-target"], 15.0),
        (["launchctl", "bootout", "safe-target"], 30.0),
        (["launchctl", "bootstrap", "safe-target"], 30.0),
    ]


def test_launchctl_runner_rejects_unknown_action_without_subprocess(monkeypatch) -> None:
    monkeypatch.setattr(
        runner_script.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("unknown launchctl action must not execute")
        ),
    )

    result = runner_script._run(["launchctl", "kickstart", "safe-target"])

    assert result.returncode == 126
    assert result.stdout == ""
    assert result.stderr == ""


def test_g039_desktop_access_probe_is_fixed_read_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    target = repository / "backend" / "h11_v4_reviewed_digest.py"
    target.parent.mkdir(parents=True)
    target.write_text("REVIEWED_FILES = ()\n", encoding="utf-8")
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner_script.subprocess, "run", fake_run)

    assert runner_script._probe_g039_launchd_desktop_access(
        repository=repository,
        user_id=501,
        python_executable=Path("/safe/python"),
    )
    assert observed["command"][:4] == [
        "launchctl",
        "asuser",
        "501",
        "/safe/python",
    ]
    assert observed["command"][-1] == str(target)
    assert "read_bytes" in observed["command"][-2]
    assert observed["kwargs"]["check"] is False
    assert observed["kwargs"]["timeout"] == 15.0


def test_g039_desktop_access_failure_stops_before_operation_marker(
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
        generation_label="H11_AUTO_30M_20260729_G039",
    )
    reached = {"gate": False}

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
    monkeypatch.setattr(
        runner_script,
        "require_stable_v4_gmo_aqua_domain",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        runner_script,
        "_probe_g039_launchd_desktop_access",
        lambda **_kw: False,
    )

    def gate(**_kwargs):
        reached["gate"] = True
        raise AssertionError("operation marker gate must remain unreachable")

    monkeypatch.setattr(runner_script, "load_external_preparation_gate", gate)

    assert runner_script.main() == 2
    output = capsys.readouterr().out
    assert "MONITOR_LAUNCHAGENT_DESKTOP_ACCESS_BLOCKED_NO_MARKER_CLAIMED" in output
    assert "G039_LAUNCHD_DESKTOP_ACCESS_NOT_CLEAR" in output
    assert reached == {"gate": False}


def test_failure_class_allows_only_fixed_safe_labels() -> None:
    assert (
        runner_script._safe_failure_class(
            runner_script.V4GmoLaunchdError(
                runner_script.V4GmoLaunchdFailureCode.BOOTOUT_FAILED
            )
        )
        == "V4_LAUNCHD_BOOTOUT_FAILED"
    )
    assert (
        runner_script._safe_failure_class(
            runner_script.V4ActualPreparationGuardError(
                runner_script.V4PreparationFailureCode.SEQUENCE_PREVIOUS_NOT_CLEAR
            )
        )
        == "PREPARATION_SEQUENCE_BLOCKED"
    )
    assert (
        runner_script._safe_failure_class(
            runner_script.V4GmoLaunchdError("unsafe provider detail")
        )
        == "MONITOR_LAUNCHAGENT_FAILURE_CLASS_UNKNOWN"
    )
    assert (
        runner_script._safe_failure_class(
            runner_script.V4ActualPreparationGuardError(
                "V4_LAUNCHD_BOOTOUT_FAILED"
            )
        )
        == "PREPARATION_OPERATION_FAILED"
    )
    assert (
        runner_script._safe_failure_class(
            runner_script.subprocess.TimeoutExpired(["launchctl"], 15.0)
        )
        == "V4_LAUNCHD_COMMAND_TIMEOUT"
    )
    assert (
        runner_script._safe_failure_class(
            runner_script.subprocess.TimeoutExpired(
                ["launchctl", "bootout", "safe-target"],
                30.0,
            )
        )
        == "V4_LAUNCHD_BOOTOUT_TIMEOUT"
    )
    assert (
        runner_script._safe_failure_class(
            runner_script.subprocess.TimeoutExpired(
                ["launchctl", "bootstrap", "safe-target"],
                30.0,
            )
        )
        == "V4_LAUNCHD_BOOTSTRAP_TIMEOUT"
    )


def test_gui_domain_timeout_is_retry_safe_through_main(
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
    reached = {"gate": False}

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
    monkeypatch.setattr(
        runner_script,
        "_run",
        lambda _command: (_ for _ in ()).throw(
            runner_script.subprocess.TimeoutExpired(["launchctl", "print"], 15.0)
        ),
    )

    def gate(**_kwargs):
        reached["gate"] = True
        raise AssertionError("gate must remain unreachable")

    monkeypatch.setattr(runner_script, "load_external_preparation_gate", gate)

    assert runner_script.main() == 3
    output = capsys.readouterr().out
    assert "GUI_DOMAIN_NOT_READY_RETRY_SAFE" in output
    assert "failure_class=V4_LAUNCHD_PRINT_TIMEOUT" in output
    assert "NO_RETRY" not in output
    assert reached == {"gate": False}


def test_pre_marker_failure_does_not_claim_no_retry(
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
    monkeypatch.setattr(
        runner_script,
        "require_stable_v4_gmo_aqua_domain",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        runner_script,
        "load_external_preparation_gate",
        lambda **_kw: (_ for _ in ()).throw(
            runner_script.V4ActualPreparationGuardError(
                runner_script.V4PreparationFailureCode.SEQUENCE_PREVIOUS_NOT_CLEAR
            )
        ),
    )

    assert runner_script.main() == 2
    output = capsys.readouterr().out
    assert "MONITOR_LAUNCHAGENT_PRECHECK_BLOCKED_NO_MARKER_CLAIMED" in output
    assert "NO_RETRY" not in output


def test_gui_domain_unknown_failure_is_sanitized_without_marker_claim(
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
    monkeypatch.setattr(
        runner_script,
        "require_stable_v4_gmo_aqua_domain",
        lambda **_kw: (_ for _ in ()).throw(
            OSError("unsafe provider detail")
        ),
    )

    assert runner_script.main() == 2
    output = capsys.readouterr().out
    assert "GUI_DOMAIN_CHECK_BLOCKED_NO_MARKER_CLAIMED" in output
    assert "failure_class=MONITOR_LAUNCHAGENT_FAILURE_CLASS_UNKNOWN" in output
    assert "unsafe provider detail" not in output
    assert "NO_RETRY" not in output


def test_begin_failure_reports_unknown_state_no_retry(
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
    ledger = SimpleNamespace(
        begin=lambda _operation: (_ for _ in ()).throw(
            runner_script.V4ActualPreparationGuardError(
                runner_script.V4PreparationFailureCode.ATTEMPT_NOT_PERSISTED
            )
        )
    )

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
    monkeypatch.setattr(
        runner_script,
        "require_stable_v4_gmo_aqua_domain",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        runner_script,
        "load_external_preparation_gate",
        lambda **_kw: object(),
    )
    monkeypatch.setattr(
        runner_script,
        "V4PreparationAttemptLedger",
        lambda **_kw: ledger,
    )

    assert runner_script.main() == 2
    output = capsys.readouterr().out
    assert "MONITOR_LAUNCHAGENT_BEGIN_BLOCKED_STATE_UNKNOWN_NO_RETRY" in output
    assert "failure_class=PREPARATION_PERSISTENCE_FAILED" in output


def test_deterministic_begin_refusal_does_not_claim_new_marker(
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
    ledger = SimpleNamespace(
        begin=lambda _operation: (_ for _ in ()).throw(
            runner_script.V4ActualPreparationGuardError(
                runner_script.V4PreparationFailureCode.SEQUENCE_PREVIOUS_NOT_CLEAR
            )
        )
    )

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
    monkeypatch.setattr(
        runner_script,
        "require_stable_v4_gmo_aqua_domain",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        runner_script,
        "load_external_preparation_gate",
        lambda **_kw: object(),
    )
    monkeypatch.setattr(
        runner_script,
        "V4PreparationAttemptLedger",
        lambda **_kw: ledger,
    )

    assert runner_script.main() == 2
    output = capsys.readouterr().out
    assert "MONITOR_LAUNCHAGENT_BEGIN_REFUSED_NO_NEW_MARKER" in output
    assert "failure_class=PREPARATION_SEQUENCE_BLOCKED" in output
    assert "NO_RETRY" not in output

    ledger.begin = lambda _operation: (_ for _ in ()).throw(
        runner_script.V4ActualPreparationGuardError(
            runner_script.V4PreparationFailureCode
            .GENERATION_TERMINAL_UNRESOLVED
        )
    )
    assert runner_script.main() == 2
    output = capsys.readouterr().out.strip()
    assert "\n" not in output
    pairs = [field.split("=", 1) for field in output.split()]
    assert all(len(pair) == 2 for pair in pairs)
    assert len({pair[0] for pair in pairs}) == len(pairs)
    fields = dict(pairs)
    assert fields == {
        "status": (
            "MONITOR_LAUNCHAGENT_BEGIN_REFUSED_EXISTING_TERMINAL_NO_RETRY"
        ),
        "failure_class": "PREPARATION_GENERATION_TERMINAL_UNRESOLVED",
        "broker_write": "false",
        "actual_post_count": "0",
    }


def test_post_marker_failure_reports_no_retry(
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
    permit = object()
    ledger = SimpleNamespace(begin=lambda _operation: permit)

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
    monkeypatch.setattr(
        runner_script,
        "require_stable_v4_gmo_aqua_domain",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        runner_script,
        "load_external_preparation_gate",
        lambda **_kw: object(),
    )
    monkeypatch.setattr(
        runner_script,
        "V4PreparationAttemptLedger",
        lambda **_kw: ledger,
    )
    monkeypatch.setattr(
        runner_script,
        "require_operation_permit",
        lambda *_args, **_kwargs: permit,
    )
    monkeypatch.setattr(
        runner_script,
        "install_and_restart_v4_gmo_monitor_launchagent",
        lambda **_kw: (_ for _ in ()).throw(
            runner_script.V4GmoLaunchdError(
                runner_script.V4GmoLaunchdFailureCode.BOOTOUT_FAILED
            )
        ),
    )

    assert runner_script.main() == 2
    output = capsys.readouterr().out
    assert "MONITOR_LAUNCHAGENT_BLOCKED_NO_RETRY" in output
    assert "failure_class=V4_LAUNCHD_BOOTOUT_FAILED" in output


def test_post_marker_timeout_reports_exact_launchctl_phase(
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
    permit = object()
    ledger = SimpleNamespace(begin=lambda _operation: permit)

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
    monkeypatch.setattr(
        runner_script,
        "require_stable_v4_gmo_aqua_domain",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        runner_script,
        "load_external_preparation_gate",
        lambda **_kw: object(),
    )
    monkeypatch.setattr(
        runner_script,
        "V4PreparationAttemptLedger",
        lambda **_kw: ledger,
    )
    monkeypatch.setattr(
        runner_script,
        "require_operation_permit",
        lambda *_args, **_kwargs: permit,
    )

    for action, expected in (
        ("bootout", "V4_LAUNCHD_BOOTOUT_TIMEOUT"),
        ("bootstrap", "V4_LAUNCHD_BOOTSTRAP_TIMEOUT"),
    ):
        monkeypatch.setattr(
            runner_script,
            "install_and_restart_v4_gmo_monitor_launchagent",
            lambda _action=action, **_kw: (_ for _ in ()).throw(
                runner_script.subprocess.TimeoutExpired(
                    ["launchctl", _action, "safe-target"],
                    30.0,
                )
            ),
        )
        assert runner_script.main() == 2
        output = capsys.readouterr().out
        assert "MONITOR_LAUNCHAGENT_BLOCKED_NO_RETRY" in output
        assert f"failure_class={expected}" in output


def test_post_marker_unknown_failure_is_sanitized_no_retry(
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
    permit = object()
    ledger = SimpleNamespace(begin=lambda _operation: permit)

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
    monkeypatch.setattr(
        runner_script,
        "require_stable_v4_gmo_aqua_domain",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        runner_script,
        "load_external_preparation_gate",
        lambda **_kw: object(),
    )
    monkeypatch.setattr(
        runner_script,
        "V4PreparationAttemptLedger",
        lambda **_kw: ledger,
    )
    monkeypatch.setattr(
        runner_script,
        "require_operation_permit",
        lambda *_args, **_kwargs: permit,
    )
    monkeypatch.setattr(
        runner_script,
        "install_and_restart_v4_gmo_monitor_launchagent",
        lambda **_kw: (_ for _ in ()).throw(
            OSError("unsafe provider detail")
        ),
    )

    assert runner_script.main() == 2
    output = capsys.readouterr().out
    assert "MONITOR_LAUNCHAGENT_BLOCKED_NO_RETRY" in output
    assert "failure_class=MONITOR_LAUNCHAGENT_FAILURE_CLASS_UNKNOWN" in output
    assert "unsafe provider detail" not in output


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
    assert "failure_class=V4_LAUNCHD_GUI_DOMAIN_NOT_READY" in output
    assert "NO_RETRY" not in output
    assert reached == {"gate": False, "install": False}
    assert list(repository.rglob("*.json")) == []
    assert list(repository.rglob("*.plist")) == []
