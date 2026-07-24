from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.services import h11_v4_unattended_live_paths as paths_module
from app.services.h11_v4_unattended_live_authorization import (
    V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA,
    check_operator_daily_authorization,
)

_JST = ZoneInfo("Asia/Tokyo")
_GENERATION = "sha256:" + "c" * 64
_BACKEND_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------- path helper


def test_state_root_and_artifact_path_are_generation_bound(tmp_path: Path) -> None:
    root = paths_module.v4_unattended_live_state_root(
        repository=tmp_path, generation_digest=_GENERATION
    )
    assert root == (
        tmp_path.resolve()
        / "backend"
        / "market_data"
        / "h11_v4_unattended_live"
        / f"generation-{'c' * 64}"
    )
    artifact = paths_module.v4_unattended_live_daily_authorization_path(
        repository=tmp_path, generation_digest=_GENERATION
    )
    assert artifact == root / "daily-authorization.json"


@pytest.mark.parametrize(
    "bad_digest",
    (
        "not-a-digest",
        "sha256:" + "g" * 64,
        "sha256:" + "a" * 63,
        "SHA256:" + "a" * 64,
        "",
    ),
)
def test_malformed_generation_digest_is_refused(tmp_path: Path, bad_digest: str) -> None:
    with pytest.raises(
        paths_module.V4UnattendedLivePathError,
        match="V4_UNATTENDED_LIVE_GENERATION_DIGEST_INVALID",
    ):
        paths_module.v4_unattended_live_state_root(
            repository=tmp_path, generation_digest=bad_digest
        )


def test_non_string_generation_digest_is_refused(tmp_path: Path) -> None:
    with pytest.raises(
        paths_module.V4UnattendedLivePathError,
        match="V4_UNATTENDED_LIVE_GENERATION_DIGEST_INVALID",
    ):
        paths_module.v4_unattended_live_state_root(
            repository=tmp_path, generation_digest=12345  # type: ignore[arg-type]
        )


def test_different_generations_resolve_to_different_paths(tmp_path: Path) -> None:
    other = "sha256:" + "d" * 64
    first = paths_module.v4_unattended_live_daily_authorization_path(
        repository=tmp_path, generation_digest=_GENERATION
    )
    second = paths_module.v4_unattended_live_daily_authorization_path(
        repository=tmp_path, generation_digest=other
    )
    assert first != second


# ---------------------------------------------------------------- CLI


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.h11_auto_v4_unattended_live_create_daily_authorization",
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=_BACKEND_ROOT,
    )


def test_cli_creates_a_valid_authorized_artifact(tmp_path: Path) -> None:
    result = _run_cli(
        "--generation-digest", _GENERATION, "--repository", str(tmp_path)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["created"] is True
    assert payload["authorized"] is True
    assert payload["blocked_reasons"] == []
    assert payload["consumption_available"] is True

    artifact_path = paths_module.v4_unattended_live_daily_authorization_path(
        repository=tmp_path, generation_digest=_GENERATION
    )
    assert artifact_path.is_file()
    on_disk = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert on_disk["schema"] == V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA
    assert on_disk["generation_digest"] == _GENERATION
    assert on_disk["maximum_entries"] == 1
    assert on_disk["operator_authorized"] is True
    today_jst = datetime.now(UTC).astimezone(_JST).date().isoformat()
    assert on_disk["trading_day_jst"] == today_jst

    # The existing, unmodified check function accepts what the CLI wrote.
    check = check_operator_daily_authorization(
        artifact_path=artifact_path,
        expected_generation_digest=_GENERATION,
        now_utc=datetime.now(UTC),
    )
    assert check.authorized is True


def test_cli_never_overwrites_without_force(tmp_path: Path) -> None:
    first = _run_cli("--generation-digest", _GENERATION, "--repository", str(tmp_path))
    assert first.returncode == 0
    second = _run_cli("--generation-digest", _GENERATION, "--repository", str(tmp_path))
    assert second.returncode == 2
    payload = json.loads(second.stdout)
    assert payload["created"] is False
    assert payload["status"] == "AUTHORIZATION_ARTIFACT_ALREADY_EXISTS_USE_FORCE"


def test_cli_force_overwrites_an_existing_artifact(tmp_path: Path) -> None:
    _run_cli("--generation-digest", _GENERATION, "--repository", str(tmp_path))
    result = _run_cli(
        "--generation-digest", _GENERATION, "--repository", str(tmp_path), "--force"
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["created"] is True


def test_cli_refuses_a_symlinked_destination(tmp_path: Path) -> None:
    artifact_path = paths_module.v4_unattended_live_daily_authorization_path(
        repository=tmp_path, generation_digest=_GENERATION
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    real_target = tmp_path / "elsewhere.json"
    real_target.write_text("{}", encoding="utf-8")
    artifact_path.symlink_to(real_target)
    result = _run_cli("--generation-digest", _GENERATION, "--repository", str(tmp_path))
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "AUTHORIZATION_ARTIFACT_PATH_SYMLINK_REFUSED"
    assert payload["created"] is False


def test_cli_refuses_a_symlinked_temp_file(tmp_path: Path) -> None:
    # TOCTOU regression coverage: the .tmp intermediate must fail closed via
    # O_EXCL rather than following a planted symlink, matching the pattern
    # consume_operator_daily_authorization_once already uses for its marker.
    artifact_path = paths_module.v4_unattended_live_daily_authorization_path(
        repository=tmp_path, generation_digest=_GENERATION
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    real_target = tmp_path / "elsewhere.json"
    real_target.write_text("{}", encoding="utf-8")
    temp_path = artifact_path.with_suffix(f"{artifact_path.suffix}.tmp")
    temp_path.symlink_to(real_target)
    result = _run_cli("--generation-digest", _GENERATION, "--repository", str(tmp_path))
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "AUTHORIZATION_ARTIFACT_TEMP_FILE_ALREADY_EXISTS"
    assert payload["created"] is False
    # The symlink target must never have been written to.
    assert real_target.read_text(encoding="utf-8") == "{}"


def test_cli_rejects_a_malformed_generation_digest(tmp_path: Path) -> None:
    result = _run_cli(
        "--generation-digest", "not-a-digest", "--repository", str(tmp_path)
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["created"] is False
    assert "V4_UNATTENDED_LIVE_GENERATION_DIGEST_INVALID" in payload["status"]


def test_cli_requires_generation_digest_argument() -> None:
    result = _run_cli()
    assert result.returncode == 2
    assert "--generation-digest" in result.stderr


def test_cli_never_writes_outside_the_canonical_generation_directory(
    tmp_path: Path,
) -> None:
    _run_cli("--generation-digest", _GENERATION, "--repository", str(tmp_path))
    created = list((tmp_path / "backend" / "market_data" / "h11_v4_unattended_live").rglob("*"))
    created_files = [path for path in created if path.is_file()]
    assert len(created_files) == 1
    assert created_files[0].name == "daily-authorization.json"
