from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.h11_auto.v4_actual_preparation_guard import V4ActualPreparationGuardError
from app.services import h11_v4_unattended_live_paths as paths_module
from scripts import h11_auto_v4_unattended_live_authorize_today as authorize_module

_DIGEST = "sha256:" + "e" * 64
_GENERATION = SimpleNamespace(generation_label="H11_AUTO_TEST_G000", digest=_DIGEST)


def _patch_generation(monkeypatch) -> None:
    monkeypatch.setattr(authorize_module, "require_clean_main", lambda **_: None)
    monkeypatch.setattr(
        authorize_module, "compute_reviewed_files_digest", lambda **_: _DIGEST
    )
    monkeypatch.setattr(
        authorize_module, "load_v4_gmo_frozen_generation", lambda **_: _GENERATION
    )


def test_correct_confirmation_writes_artifact_with_computed_digest(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    _patch_generation(monkeypatch)
    exit_code = authorize_module.main(
        [authorize_module.AUTHORIZATION_CONFIRMATION, "--state-root", str(tmp_path)]
    )
    assert exit_code == 0
    output = capsys.readouterr().out
    assert f"generation_digest={_DIGEST}" in output
    assert "H11_AUTO_TEST_G000" in output

    artifact_path = paths_module.v4_unattended_live_daily_authorization_path(
        state_root=tmp_path, generation_digest=_DIGEST
    )
    assert artifact_path.is_file()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["generation_digest"] == _DIGEST
    assert payload["operator_authorized"] is True


def test_wrong_confirmation_writes_nothing(monkeypatch, tmp_path: Path, capsys) -> None:
    _patch_generation(monkeypatch)
    exit_code = authorize_module.main(
        ["not the phrase", "--state-root", str(tmp_path)]
    )
    assert exit_code == 2
    assert "AUTHORIZATION_CONFIRMATION_MISMATCH" in capsys.readouterr().out
    created = list(tmp_path.rglob("*"))
    assert [path for path in created if path.is_file()] == []


def test_dirty_git_blocks_before_any_write(monkeypatch, tmp_path: Path, capsys) -> None:
    def _raise(**_: object) -> None:
        raise V4ActualPreparationGuardError("PREPARATION_GIT_GATE_BLOCKED")

    monkeypatch.setattr(authorize_module, "require_clean_main", _raise)
    monkeypatch.setattr(
        authorize_module,
        "compute_reviewed_files_digest",
        lambda **_: (_ for _ in ()).throw(AssertionError("must not run after gate blocks")),
    )
    exit_code = authorize_module.main(
        [authorize_module.AUTHORIZATION_CONFIRMATION, "--state-root", str(tmp_path)]
    )
    assert exit_code == 2
    assert "PREPARATION_GIT_GATE_BLOCKED" in capsys.readouterr().out
    created = list(tmp_path.rglob("*"))
    assert [path for path in created if path.is_file()] == []


def test_second_run_without_force_does_not_overwrite(
    monkeypatch, tmp_path: Path
) -> None:
    _patch_generation(monkeypatch)
    first = authorize_module.main(
        [authorize_module.AUTHORIZATION_CONFIRMATION, "--state-root", str(tmp_path)]
    )
    assert first == 0
    second = authorize_module.main(
        [authorize_module.AUTHORIZATION_CONFIRMATION, "--state-root", str(tmp_path)]
    )
    assert second == 2


def test_force_overwrites_an_existing_artifact(monkeypatch, tmp_path: Path) -> None:
    _patch_generation(monkeypatch)
    authorize_module.main(
        [authorize_module.AUTHORIZATION_CONFIRMATION, "--state-root", str(tmp_path)]
    )
    exit_code = authorize_module.main(
        [
            authorize_module.AUTHORIZATION_CONFIRMATION,
            "--state-root",
            str(tmp_path),
            "--force",
        ]
    )
    assert exit_code == 0
