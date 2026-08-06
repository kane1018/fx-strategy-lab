"""C-2 acceptance tests: operator-only HALT discharge (rename-archive).

Authored by the reviewer, not the implementer. Fake-only: tmp_path pseudo-repos
only; the two real halts on disk are never touched (guarded by the repository
scan check in test_archive_clears_the_runtime_scan and by the AST guard in
test_runtime_modules_cannot_reach_halt_discharge).
"""

from __future__ import annotations

import ast
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.h11_auto.v4_gmo_runtime_paths import (
    v4_gmo_runtime_state_root,
)
from app.services.h11_v4_g075_runtime import require_g075_no_unresolved_halt
from app.services.h11_v4_halt_discharge import (
    V4_HALT_DISCHARGE_REQUIRED_RESOLUTION_KEYS,
    V4HaltDischargeError,
    discharge_halt,
    halt_content_sha256,
)

REPOSITORY = Path(__file__).resolve().parents[4]
GENERATION_DIGEST = "sha256:" + "f" * 64
NOW = datetime(2026, 8, 6, 1, 2, 3, tzinfo=UTC)


def _plant_halt(repository: Path, *, reason: str = "G074_INITIAL_TRANSACTION_UNKNOWN") -> Path:
    root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=GENERATION_DIGEST
    )
    root.mkdir(parents=True, exist_ok=True)
    halt = root / "g074-persistent-halt.json"
    halt.write_text(
        json.dumps(
            {
                "generation_label": "H11_AUTO_30M_20260802_G075",
                "status": "HALTED",
                "reason": reason,
                "broker_write": False,
                "actual_post_count": 0,
            }
        ),
        encoding="utf-8",
    )
    return halt


def _resolution(*, halt: Path, sha256: str | None = None) -> dict[str, str]:
    return {
        "operator": "operator-1",
        "reason": "flat confirmed by operator",
        "broker_state_confirmation": "openPositions=0 and activeOrders=0 on 2026-08-06",
        "halt_content_sha256": (
            sha256
            if sha256 is not None
            else halt_content_sha256(json.loads(halt.read_text(encoding="utf-8")))
        ),
    }


def test_discharge_archives_halt_and_clears_the_runtime_scan(tmp_path: Path) -> None:
    """Normal path: the halt is renamed to an archive that preserves the
    original content plus the resolution, the original filename is gone, and
    the runtime scan no longer sees an unresolved halt."""
    halt = _plant_halt(tmp_path)
    resolution = {
        "operator": "operator-1",
        "reason": "flat confirmed by operator",
        "broker_state_confirmation": "openPositions=0 and activeOrders=0 on 2026-08-06",
        "halt_content_sha256": halt_content_sha256(
            json.loads(halt.read_text(encoding="utf-8"))
        ),
    }

    archive = discharge_halt(
        repository=tmp_path,
        generation_digest=GENERATION_DIGEST,
        halt_file_name="g074-persistent-halt.json",
        resolution=resolution,
        now_utc=NOW,
    )

    assert not halt.exists()
    assert archive.is_file()
    payload = json.loads(archive.read_text(encoding="utf-8"))
    assert payload["original"]["reason"] == "G074_INITIAL_TRANSACTION_UNKNOWN"
    assert payload["original"]["status"] == "HALTED"
    assert payload["resolution"]["operator"] == "operator-1"
    assert payload["resolution"]["halt_content_sha256"] == resolution["halt_content_sha256"]
    assert payload["discharged_at_utc"] == NOW.isoformat()
    # The runtime scan must now pass (no unresolved halt remains).
    require_g075_no_unresolved_halt(repository=tmp_path)


def test_sha256_mismatch_refuses_and_leaves_halt_intact(tmp_path: Path) -> None:
    halt = _plant_halt(tmp_path)
    resolution = _resolution(halt=halt, sha256="sha256:" + "0" * 64)

    with pytest.raises(V4HaltDischargeError, match="SHA256_MISMATCH"):
        discharge_halt(
            repository=tmp_path,
            generation_digest=GENERATION_DIGEST,
            halt_file_name="g074-persistent-halt.json",
            resolution=resolution,
            now_utc=NOW,
        )
    assert halt.is_file()
    assert json.loads(halt.read_text(encoding="utf-8"))["status"] == "HALTED"


def test_incomplete_resolution_refuses(tmp_path: Path) -> None:
    halt = _plant_halt(tmp_path)
    for missing_key in V4_HALT_DISCHARGE_REQUIRED_RESOLUTION_KEYS:
        resolution = _resolution(halt=halt)
        resolution[missing_key] = "   "
        with pytest.raises(V4HaltDischargeError, match="RESOLUTION_INCOMPLETE"):
            discharge_halt(
                repository=tmp_path,
                generation_digest=GENERATION_DIGEST,
                halt_file_name="g074-persistent-halt.json",
                resolution=resolution,
                now_utc=NOW,
            )
        assert halt.is_file()


def test_archive_name_does_not_match_the_runtime_scan_glob(tmp_path: Path) -> None:
    halt = _plant_halt(tmp_path)
    archive = discharge_halt(
        repository=tmp_path,
        generation_digest=GENERATION_DIGEST,
        halt_file_name="g074-persistent-halt.json",
        resolution={
            "operator": "operator-1",
            "reason": "flat confirmed by operator",
            "broker_state_confirmation": "openPositions=0 and activeOrders=0 on 2026-08-06",
            "halt_content_sha256": halt_content_sha256(
                json.loads(halt.read_text(encoding="utf-8"))
            ),
        },
        now_utc=NOW,
    )
    assert "halt-discharged" in archive.name
    # The Phase A scan glob must not match the archive name.
    assert re.fullmatch(r"g0.*-persistent-halt\.json", archive.name) is None
    generation_root = archive.parent
    assert list(generation_root.glob("g0*-persistent-halt.json")) == []
    require_g075_no_unresolved_halt(repository=tmp_path)


def test_runtime_modules_cannot_reach_halt_discharge() -> None:
    """The discharge module is operator-only: no runtime path may import it."""
    for relative in (
        "backend/app/services/h11_v4_g075_runtime.py",
        "backend/app/services/h11_v4_gmo_coordinated_actual_path.py",
        "backend/app/services/h11_v4_gmo_actual_runtime_driver.py",
        "backend/app/services/h11_v4_gmo_actual_transport.py",
        "backend/app/services/h11_v4_g075_live_runtime.py",
    ):
        source = (REPOSITORY / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert "halt_discharge" not in " ".join(
                    alias.name for alias in node.names
                ), f"{relative} imports halt_discharge"
            elif isinstance(node, ast.ImportFrom):
                assert "halt_discharge" not in (node.module or ""), (
                    f"{relative} imports halt_discharge"
                )
