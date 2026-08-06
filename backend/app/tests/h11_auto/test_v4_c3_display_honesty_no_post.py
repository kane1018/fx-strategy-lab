"""C-3 acceptance tests: the display must honestly project the unresolved-halt
scan without ever crashing (display honesty).

Authored by the reviewer, not the implementer. Fake-only: tmp_path pseudo-repos
and synthetic state roots; the real halts on disk are never touched.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.h11_v4_g075_runtime import (
    G075_GENERATION_LABEL,
    safe_g075_api_status,
)

NOW = datetime(2026, 8, 6, 1, 0, 0, tzinfo=UTC)
GENERATION_DIGEST = "sha256:" + "c" * 64
REVIEWED_FILES_DIGEST = "sha256:" + "d" * 64


def _plant_halt(repository: Path, *, generation_suffix: str) -> None:
    root = (
        repository
        / "backend/market_data/h11_v4_gmo_actual_runtime"
        / f"generation-{generation_suffix}"
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / "g074-persistent-halt.json").write_text(
        json.dumps(
            {
                "generation_label": G075_GENERATION_LABEL,
                "status": "HALTED",
                "reason": "G074_INITIAL_TRANSACTION_UNKNOWN",
                "broker_write": False,
                "actual_post_count": 0,
            }
        ),
        encoding="utf-8",
    )


def test_halted_display_when_any_unresolved_halt_exists(tmp_path: Path) -> None:
    """With an unresolved halt anywhere under the runtime directory, the status
    projection must report persistent_halt True / control_plane_state HALTED /
    halt_scan UNRESOLVED_HALT_PRESENT even though the current state root is
    clean and empty."""
    _plant_halt(tmp_path, generation_suffix="9" * 64)
    status = safe_g075_api_status(
        state_root=tmp_path / "current",
        arm_on=False,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
        repository=tmp_path,
    )
    assert status["halt_scan"] == "UNRESOLVED_HALT_PRESENT"
    assert status["persistent_halt"] is True
    assert status["control_plane_state"] == "HALTED"
    assert status["release_state"] == "LOCKED"


def test_clean_display_when_no_halt_exists(tmp_path: Path) -> None:
    """With no halt on disk the projection keeps its current shape and adds a
    CLEAR halt_scan."""
    status = safe_g075_api_status(
        state_root=tmp_path / "current",
        arm_on=False,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
        repository=tmp_path,
    )
    assert status["halt_scan"] == "CLEAR"
    assert status["persistent_halt"] is False
    assert status["control_plane_state"] == "READY"
    assert status["release_state"] == "LOCKED"


def test_scan_failure_projects_scanned_failed_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the scan itself fails, the display must project halt_scan
    SCAN_FAILED and must NOT raise (the display is never allowed to crash)."""
    from app.services import h11_v4_g075_runtime as runtime

    def _failing_scan(*, repository: object) -> None:
        del repository
        raise OSError("synthetic scan failure")

    monkeypatch.setattr(runtime, "require_g075_no_unresolved_halt", _failing_scan)
    status = safe_g075_api_status(
        state_root=tmp_path / "current",
        arm_on=False,
        generation_digest=GENERATION_DIGEST,
        reviewed_files_digest=REVIEWED_FILES_DIGEST,
        repository=tmp_path,
    )
    assert status["halt_scan"] == "SCAN_FAILED"
    assert status["persistent_halt"] is False
    assert status["control_plane_state"] == "READY"
