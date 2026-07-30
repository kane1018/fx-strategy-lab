"""Fake-only tests for the operator-facing scheduled-launcher template.

All four PLACEHOLDER sections are now operator-confirmed live code
(2026-07-25): heartbeat-chain policy, real credential pair, real HTTP
client, real notification transports. Constructing
``V4GmoKeychainCredentialPair()``/``httpx.Client()``/the real transport
classes here touches no real Keychain item, network socket, or provider API
(all are lazy until actually used), so these tests exercise the real
construction rather than mocking it -- but ``bounded_run.main`` (the point
where those objects would actually be used for a real network/credential
operation) is always mocked, so no test here can perform a real broker or
notification action.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.h11_v4_gmo_actual_transport import V4GmoKeychainCredentialPair
from app.services.h11_v4_gmo_formal_canary_source import (
    V4GmoFormalCanarySourceError,
)
from scripts import h11_auto_v4_unattended_live_scheduled_launcher as launcher


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    (repository / "backend").mkdir(parents=True)
    return repository


def _argv(repository: Path) -> list[str]:
    return [
        "--repository",
        str(repository),
        "--expected-reviewed-files-digest",
        "sha256:" + "a" * 64,
        "--expected-generation-digest",
        "sha256:" + "b" * 64,
    ]


def test_absolute_launcher_bootstraps_backend_imports_without_pythonpath(
    tmp_path: Path,
) -> None:
    """LaunchAgent-style absolute execution must resolve ``app`` itself."""

    repository = Path(__file__).resolve().parents[3]
    launcher_path = (
        repository
        / "scripts/h11_auto_v4_unattended_live_scheduled_launcher.py"
    )
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, str(launcher_path), "--help"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr


def test_reviewed_files_digest_mismatch_aborts_before_session_prep(
    monkeypatch, tmp_path: Path
) -> None:
    repository = _repository(tmp_path)
    monkeypatch.setattr(
        launcher, "reviewed_files_digest", lambda **_kw: "sha256:" + "z" * 64
    )
    monkeypatch.setattr(
        launcher,
        "prepare_g013_canary_session",
        lambda **_kw: (_ for _ in ()).throw(AssertionError("must not reach session prep")),
    )
    with pytest.raises(
        launcher.V4UnattendedSchedulerLauncherError,
        match="REVIEWED_FILES_DIGEST_MISMATCH",
    ):
        launcher.main(_argv(repository))


def test_generation_digest_mismatch_aborts_before_session_prep(
    monkeypatch, tmp_path: Path
) -> None:
    repository = _repository(tmp_path)
    digest = "sha256:" + "a" * 64
    monkeypatch.setattr(launcher, "reviewed_files_digest", lambda **_kw: digest)
    monkeypatch.setattr(
        launcher,
        "load_v4_gmo_frozen_generation",
        lambda **_kw: SimpleNamespace(digest="sha256:" + "c" * 64),
    )
    monkeypatch.setattr(
        launcher,
        "prepare_g013_canary_session",
        lambda **_kw: (_ for _ in ()).throw(AssertionError("must not reach session prep")),
    )
    with pytest.raises(
        launcher.V4UnattendedSchedulerLauncherError,
        match="GENERATION_DIGEST_MISMATCH",
    ):
        launcher.main(_argv(repository))


def _valid_digests(monkeypatch, generation_digest: str) -> tuple[str, str]:
    reviewed_digest = "sha256:" + "a" * 64
    monkeypatch.setattr(launcher, "reviewed_files_digest", lambda **_kw: reviewed_digest)
    monkeypatch.setattr(
        launcher,
        "load_v4_gmo_frozen_generation",
        lambda **_kw: SimpleNamespace(
            digest=generation_digest,
            live_ready=True,
            unattended_live_supported=True,
        ),
    )
    monkeypatch.setattr(
        launcher,
        "V4UnattendedLiveArmStore",
        lambda _path: SimpleNamespace(
            check=lambda **_kw: SimpleNamespace(armed=True, blocked_reasons=())
        ),
    )
    monkeypatch.setattr(
        launcher,
        "verify_g038_generation_activation",
        lambda **_kw: SimpleNamespace(successor_activation_released=True),
    )
    monkeypatch.setattr(
        launcher,
        "record_g038_scheduler_heartbeat",
        lambda **_kw: None,
    )
    return reviewed_digest, generation_digest


def _argv_matching(repository: Path, *, reviewed_digest: str, generation_digest: str) -> list[str]:
    return [
        "--repository",
        str(repository),
        "--expected-reviewed-files-digest",
        reviewed_digest,
        "--expected-generation-digest",
        generation_digest,
    ]


def test_disarmed_tick_stops_before_session_or_credentials(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    repository = _repository(tmp_path)
    generation_digest = "sha256:" + "b" * 64
    reviewed_digest, _ = _valid_digests(monkeypatch, generation_digest)
    monkeypatch.setattr(
        launcher,
        "V4UnattendedLiveArmStore",
        lambda _path: SimpleNamespace(
            check=lambda **_kw: SimpleNamespace(
                armed=False, blocked_reasons=("OPERATOR_DISARMED",)
            )
        ),
    )
    monkeypatch.setattr(
        launcher,
        "prepare_g013_canary_session",
        lambda **_kw: (_ for _ in ()).throw(AssertionError("must not prepare session")),
    )
    assert (
        launcher.main(
            _argv_matching(
                repository,
                reviewed_digest=reviewed_digest,
                generation_digest=generation_digest,
            )
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "UNATTENDED_SCHEDULER_TICK_DISARMED" in output
    assert "broker_write=false" in output
    assert "actual_post_count=0" in output


def test_uncommissioned_generation_stops_before_arm_or_session(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    repository = _repository(tmp_path)
    digest = "sha256:" + "a" * 64
    generation_digest = "sha256:" + "b" * 64
    monkeypatch.setattr(launcher, "reviewed_files_digest", lambda **_kw: digest)
    monkeypatch.setattr(
        launcher,
        "load_v4_gmo_frozen_generation",
        lambda **_kw: SimpleNamespace(
            digest=generation_digest,
            live_ready=False,
            unattended_live_supported=False,
        ),
    )
    monkeypatch.setattr(
        launcher,
        "V4UnattendedLiveArmStore",
        lambda _path: (_ for _ in ()).throw(AssertionError("must not read arm")),
    )
    assert launcher.main(
        _argv_matching(
            repository,
            reviewed_digest=digest,
            generation_digest=generation_digest,
        )
    ) == 0
    output = capsys.readouterr().out
    assert "GENERATION_NOT_COMMISSIONED" in output
    assert "broker_write=false" in output


def test_session_not_yet_is_routine_and_returns_zero(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    repository = _repository(tmp_path)
    generation_digest = "sha256:" + "b" * 64
    reviewed_digest, _ = _valid_digests(monkeypatch, generation_digest)
    monkeypatch.setattr(
        launcher,
        "prepare_g013_canary_session",
        lambda **_kw: (_ for _ in ()).throw(
            launcher.canary_module.V4GmoG013CanaryError("G013_ENTRY_TIME_BLOCKED_BEFORE_PUBLIC_GET")
        ),
    )
    monkeypatch.setattr(
        launcher,
        "bounded_run",
        SimpleNamespace(
            main=lambda *_a, **_kw: (_ for _ in ()).throw(
                AssertionError("must not reach bounded_run.main")
            )
        ),
    )
    exit_code = launcher.main(
        _argv_matching(
            repository, reviewed_digest=reviewed_digest, generation_digest=generation_digest
        )
    )
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "UNATTENDED_SCHEDULER_TICK_NOT_YET" in output
    assert "ENTRY_TIME_BLOCKED" in output


def test_formal_signal_stay_is_routine_and_returns_zero(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    repository = _repository(tmp_path)
    generation_digest = "sha256:" + "b" * 64
    reviewed_digest, _ = _valid_digests(monkeypatch, generation_digest)
    monkeypatch.setattr(
        launcher,
        "prepare_g013_canary_session",
        lambda **_kw: (_ for _ in ()).throw(
            V4GmoFormalCanarySourceError("G013_FORMAL_SIGNAL_STAY")
        ),
    )
    monkeypatch.setattr(
        launcher,
        "bounded_run",
        SimpleNamespace(
            main=lambda *_a, **_kw: (_ for _ in ()).throw(
                AssertionError("must not reach bounded_run.main")
            )
        ),
    )

    assert launcher.main(
        _argv_matching(
            repository,
            reviewed_digest=reviewed_digest,
            generation_digest=generation_digest,
        )
    ) == 0
    output = capsys.readouterr().out
    assert "UNATTENDED_SCHEDULER_TICK_NOT_YET" in output
    assert "G013_FORMAL_SIGNAL_STAY" in output
    assert "broker_write=false" in output
    assert "actual_post_count=0" in output


def test_unexpected_formal_signal_error_remains_fail_closed(
    monkeypatch, tmp_path: Path
) -> None:
    repository = _repository(tmp_path)
    generation_digest = "sha256:" + "b" * 64
    reviewed_digest, _ = _valid_digests(monkeypatch, generation_digest)
    monkeypatch.setattr(
        launcher,
        "prepare_g013_canary_session",
        lambda **_kw: (_ for _ in ()).throw(
            V4GmoFormalCanarySourceError("G013_FORMAL_SIGNAL_INVALID")
        ),
    )

    with pytest.raises(V4GmoFormalCanarySourceError, match="G013_FORMAL_SIGNAL_INVALID"):
        launcher.main(
            _argv_matching(
                repository,
                reviewed_digest=reviewed_digest,
                generation_digest=generation_digest,
            )
        )


def _patch_up_to_bounded_run(
    monkeypatch, tmp_path: Path, *, bounded_run_main
) -> None:
    monkeypatch.setattr(
        launcher, "prepare_g013_canary_session", lambda **_kw: SimpleNamespace()
    )
    monkeypatch.setattr(
        launcher, "v4_gmo_runtime_state_root", lambda **_kw: tmp_path / "state"
    )
    monkeypatch.setattr(launcher, "PhaseBRiskStore", lambda *_a, **_kw: SimpleNamespace())
    monkeypatch.setattr(launcher, "DeadManStore", lambda *_a, **_kw: SimpleNamespace())
    monkeypatch.setattr(
        launcher,
        "bounded_run",
        SimpleNamespace(main=bounded_run_main),
    )


def test_all_placeholders_are_live_code_and_reach_bounded_run_main(
    monkeypatch, tmp_path: Path
) -> None:
    # All four PLACEHOLDER sections are now operator-confirmed live code
    # (2026-07-25): heartbeat-chain policy, real credential pair, real HTTP
    # client, real notification transports. Constructing
    # V4GmoKeychainCredentialPair()/httpx.Client()/the real transport
    # classes here touches no real Keychain item, network socket, or
    # provider API (all are lazy until actually used), so this exercises
    # the real construction rather than mocking it. Only bounded_run.main
    # -- the point where those objects would actually be used for a real
    # operation -- is mocked, here to capture what it was called with
    # rather than to perform anything real.
    repository = _repository(tmp_path)
    generation_digest = "sha256:" + "b" * 64
    reviewed_digest, _ = _valid_digests(monkeypatch, generation_digest)
    captured: dict[str, object] = {}

    def fake_bounded_run_main(*_argv, **kwargs):
        captured.update(kwargs)
        return 0

    _patch_up_to_bounded_run(
        monkeypatch, tmp_path, bounded_run_main=fake_bounded_run_main
    )

    exit_code = launcher.main(
        _argv_matching(
            repository,
            reviewed_digest=reviewed_digest,
            generation_digest=generation_digest,
        )
    )

    assert exit_code == 0
    assert isinstance(captured["credential_pair"], V4GmoKeychainCredentialPair)
    assert isinstance(captured["client"], launcher.httpx.Client)
    assert isinstance(
        captured["notification_primary"], launcher.H11V4ActualPushoverTransport
    )
    assert isinstance(
        captured["notification_secondary"], launcher.H11V4ActualEmailTransport
    )
    assert captured["notification_primary"].fake_only is False
    assert captured["notification_secondary"].fake_only is False


def test_heartbeat_chain_store_uses_the_confirmed_policy_values(
    monkeypatch, tmp_path: Path
) -> None:
    repository = _repository(tmp_path)
    generation_digest = "sha256:" + "b" * 64
    reviewed_digest, _ = _valid_digests(monkeypatch, generation_digest)
    state_root = tmp_path / "state"
    monkeypatch.setattr(launcher, "v4_gmo_runtime_state_root", lambda **_kw: state_root)
    captured: dict[str, object] = {}
    real_store = launcher.V4HeartbeatChainStore

    def spy_store(path, *, policy):
        captured["path"] = path
        captured["policy"] = policy
        return real_store(path, policy=policy)

    monkeypatch.setattr(launcher, "V4HeartbeatChainStore", spy_store)
    _patch_up_to_bounded_run(
        monkeypatch, tmp_path, bounded_run_main=lambda *_a, **_kw: 0
    )

    exit_code = launcher.main(
        _argv_matching(
            repository,
            reviewed_digest=reviewed_digest,
            generation_digest=generation_digest,
        )
    )

    assert exit_code == 0
    policy = captured["policy"]
    assert policy.policy_label == launcher._HEARTBEAT_CHAIN_POLICY_LABEL
    assert policy.maximum_gap_seconds == launcher._HEARTBEAT_CHAIN_MAXIMUM_GAP_SECONDS
    assert (
        policy.minimum_continuous_seconds
        == launcher._HEARTBEAT_CHAIN_MINIMUM_CONTINUOUS_SECONDS
    )
    assert captured["path"] == state_root / "unattended-heartbeat-chain.json"


def test_lock_is_released_after_bounded_run_raises(monkeypatch, tmp_path: Path) -> None:
    # The finally: lock.release() must run even when the real cycle attempt
    # itself fails downstream -- proven here by re-acquiring the SAME real
    # lock file after main() propagates bounded_run.main's failure, rather
    # than only trusting the finally clause exists. (Previously this test
    # relied on a placeholder raising before bounded_run.main was ever
    # reached; now that all four placeholders are live code, the failure is
    # simulated at bounded_run.main itself instead.)
    repository = _repository(tmp_path)
    generation_digest = "sha256:" + "b" * 64
    reviewed_digest, _ = _valid_digests(monkeypatch, generation_digest)
    state_root = tmp_path / "state"
    monkeypatch.setattr(launcher, "v4_gmo_runtime_state_root", lambda **_kw: state_root)

    def failing_bounded_run_main(*_a, **_kw):
        raise RuntimeError("simulated downstream cycle failure")

    _patch_up_to_bounded_run(
        monkeypatch, tmp_path, bounded_run_main=failing_bounded_run_main
    )

    with pytest.raises(RuntimeError, match="simulated downstream cycle failure"):
        launcher.main(
            _argv_matching(
                repository,
                reviewed_digest=reviewed_digest,
                generation_digest=generation_digest,
            )
        )

    reacquired = launcher.H11AutoProcessLock(state_root / "process.lock")
    assert reacquired.acquire() is True
    reacquired.release()


def test_lock_held_skips_tick_without_reaching_session_prep(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    repository = _repository(tmp_path)
    generation_digest = "sha256:" + "b" * 64
    reviewed_digest, _ = _valid_digests(monkeypatch, generation_digest)
    monkeypatch.setattr(
        launcher,
        "H11AutoProcessLock",
        lambda _path: SimpleNamespace(acquire=lambda: False, release=lambda: None),
    )
    monkeypatch.setattr(
        launcher,
        "prepare_g013_canary_session",
        lambda **_kw: (_ for _ in ()).throw(AssertionError("must not reach session prep")),
    )
    exit_code = launcher.main(
        _argv_matching(
            repository, reviewed_digest=reviewed_digest, generation_digest=generation_digest
        )
    )
    assert exit_code == 0
    assert "UNATTENDED_SCHEDULER_TICK_SKIPPED_LOCK_HELD" in capsys.readouterr().out


def test_launcher_source_has_no_forbidden_fake_transport_construction() -> None:
    # Operator confirmed PLACEHOLDER 0 and filled in PLACEHOLDER 1/2
    # themselves (2026-07-25), so V4GmoKeychainCredentialPair()/
    # httpx.Client() are now expected, legitimate executable code -- no
    # longer forbidden tokens. PLACEHOLDER 3 (notification transports)
    # remains unfilled, so this test now narrows to guarding only that:
    # a real transport implementation (h11_v4_notification_actual_transport.py)
    # exists, but this file must never quietly wire in the *fake* transports
    # as if they were real ones (that would defeat the whole
    # fake_only-is-False contract the orchestration layer relies on).
    import inspect

    # Comment lines (the instructional examples inside each PLACEHOLDER
    # block) are expected to mention these tokens -- only executable code
    # must never construct them.
    code_lines = "\n".join(
        line
        for line in inspect.getsource(launcher).splitlines()
        if not line.strip().startswith("#")
    )
    forbidden = (
        "H11V4FakePushoverTransport(",
        "H11V4FakeEmailTransport(",
    )
    for marker in forbidden:
        assert marker not in code_lines, marker
