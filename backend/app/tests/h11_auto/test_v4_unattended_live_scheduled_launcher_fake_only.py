"""Fake-only tests for the operator-facing scheduled-launcher template.

Everything up to the PLACEHOLDER sections is real code and is exercised for
real here (digest re-verification, session-prep "not yet" handling, the
process lock). The PLACEHOLDER sections themselves are never filled in by
these tests -- proving they still raise, in order, is the point.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

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
        lambda **_kw: SimpleNamespace(digest=generation_digest),
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


def _patch_up_to_placeholders(monkeypatch, tmp_path: Path) -> None:
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
        SimpleNamespace(
            main=lambda *_a, **_kw: (_ for _ in ()).throw(
                AssertionError("must not reach bounded_run.main -- placeholders unfilled")
            )
        ),
    )


def test_placeholders_0_1_2_are_live_code_then_placeholder_3_raises(
    monkeypatch, tmp_path: Path
) -> None:
    # Operator confirmed PLACEHOLDER 0 (heartbeat-chain policy, 2026-07-25)
    # and filled in PLACEHOLDER 1/2 (real credential pair, real HTTP client,
    # same date) themselves -- all three are now live code, not raises.
    # Constructing V4GmoKeychainCredentialPair()/httpx.Client() here touches
    # no real Keychain item or network socket (both are lazy), so this is
    # safe to exercise for real rather than mock. Execution now reaches
    # PLACEHOLDER 3 (notification transports), which still raises since it
    # remains unfilled in this file (a real, tested transport implementation
    # exists in h11_v4_notification_actual_transport.py, but has not yet
    # been wired into this launcher's PLACEHOLDER 3).
    repository = _repository(tmp_path)
    generation_digest = "sha256:" + "b" * 64
    reviewed_digest, _ = _valid_digests(monkeypatch, generation_digest)
    state_root = tmp_path / "state"
    monkeypatch.setattr(launcher, "v4_gmo_runtime_state_root", lambda **_kw: state_root)
    _patch_up_to_placeholders(monkeypatch, tmp_path)
    with pytest.raises(
        launcher.V4UnattendedSchedulerLauncherError,
        match="PLACEHOLDER_3_NOTIFICATION_PRIMARY_NOT_CONFIGURED",
    ):
        launcher.main(
            _argv_matching(
                repository,
                reviewed_digest=reviewed_digest,
                generation_digest=generation_digest,
            )
        )


def test_heartbeat_chain_store_uses_the_confirmed_policy_values(
    monkeypatch, tmp_path: Path
) -> None:
    repository = _repository(tmp_path)
    generation_digest = "sha256:" + "b" * 64
    reviewed_digest, _ = _valid_digests(monkeypatch, generation_digest)
    state_root = tmp_path / "state"
    monkeypatch.setattr(launcher, "v4_gmo_runtime_state_root", lambda **_kw: state_root)
    _patch_up_to_placeholders(monkeypatch, tmp_path)
    captured: dict[str, object] = {}
    real_store = launcher.V4HeartbeatChainStore

    def spy_store(path, *, policy):
        captured["path"] = path
        captured["policy"] = policy
        return real_store(path, policy=policy)

    monkeypatch.setattr(launcher, "V4HeartbeatChainStore", spy_store)
    with pytest.raises(launcher.V4UnattendedSchedulerLauncherError):
        launcher.main(
            _argv_matching(
                repository,
                reviewed_digest=reviewed_digest,
                generation_digest=generation_digest,
            )
        )
    policy = captured["policy"]
    assert policy.policy_label == launcher._HEARTBEAT_CHAIN_POLICY_LABEL
    assert policy.maximum_gap_seconds == launcher._HEARTBEAT_CHAIN_MAXIMUM_GAP_SECONDS
    assert (
        policy.minimum_continuous_seconds
        == launcher._HEARTBEAT_CHAIN_MINIMUM_CONTINUOUS_SECONDS
    )
    assert captured["path"] == state_root / "unattended-heartbeat-chain.json"


def test_lock_is_released_after_a_placeholder_raise(monkeypatch, tmp_path: Path) -> None:
    # The finally: lock.release() must run even when a placeholder raises
    # partway through -- proven here by re-acquiring the SAME real lock file
    # after main() raises, rather than only trusting the finally clause exists.
    repository = _repository(tmp_path)
    generation_digest = "sha256:" + "b" * 64
    reviewed_digest, _ = _valid_digests(monkeypatch, generation_digest)
    state_root = tmp_path / "state"
    monkeypatch.setattr(launcher, "v4_gmo_runtime_state_root", lambda **_kw: state_root)
    _patch_up_to_placeholders(monkeypatch, tmp_path)

    with pytest.raises(launcher.V4UnattendedSchedulerLauncherError):
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
