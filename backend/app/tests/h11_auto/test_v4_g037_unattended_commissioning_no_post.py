from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.h11_auto.v4_actual_preparation_guard import preparation_state_root
from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services import h11_v4_g037_unattended_commissioning_no_post as module
from app.services.h11_v4_g037_unattended_commissioning_no_post import (
    G037_HALT_RELEASE_REQUIRED,
    G037_TERMINAL_FLAT_HALT,
    V4G037CommissioningNoPostError,
    inspect_successful_canary_no_post,
    record_successful_canary_evidence_once_no_post,
    verify_unattended_generation_binding_no_post,
)

ORIGIN_REVIEWED = "sha256:" + "a" * 64
TARGET_REVIEWED = "sha256:" + "c" * 64
TARGET = "sha256:" + "d" * 64
CYCLE = "e" * 64
INTENT = "sha256:" + "f" * 64
_TEMPLATE = (
    Path(__file__).resolve().parents[4]
    / "docs/templates/h11_v4_gmo_frozen_generation.json"
)
ORIGIN_MANIFEST = json.loads(_TEMPLATE.read_text(encoding="utf-8"))
ORIGIN_MANIFEST["implementation_digest"] = ORIGIN_REVIEWED
_NORMALIZED_ORIGIN = dict(ORIGIN_MANIFEST)
_NORMALIZED_ORIGIN["blocked_hours_jst"] = tuple(
    _NORMALIZED_ORIGIN["blocked_hours_jst"]
)
_NORMALIZED_ORIGIN["weekend_days_jst"] = tuple(
    _NORMALIZED_ORIGIN["weekend_days_jst"]
)
_ORIGIN_GENERATION = V4GmoFrozenGeneration(**_NORMALIZED_ORIGIN)
ORIGIN_CANONICAL = json.dumps(
    ORIGIN_MANIFEST, sort_keys=True, separators=(",", ":")
)
ORIGIN = _ORIGIN_GENERATION.digest


def _runtime(tmp_path: Path, *, extra_entry: bool = False) -> None:
    root = v4_gmo_runtime_state_root(repository=tmp_path, generation_digest=ORIGIN)
    root.mkdir(parents=True)
    database = sqlite3.connect(root / "coordinator.sqlite3")
    database.executescript(
        """
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE cycles(
          cycle_ref TEXT, trading_day_jst TEXT, realized_pnl_jpy TEXT,
          protection_confirmed_at_utc TEXT
        );
        CREATE TABLE attempts(action TEXT NOT NULL, attempted_at_utc TEXT);
        """
    )
    database.executemany(
        "INSERT INTO metadata VALUES(?, ?)",
        (
            ("generation_digest", ORIGIN),
            ("implementation_digest", ORIGIN_REVIEWED),
            ("generation_manifest", ORIGIN_CANONICAL),
            ("unknown_halt_latched", "true"),
            (
                "pending_transport_resolution",
                json.dumps(
                    {
                        "classification": "FLAT_OR_REJECTED",
                        "generation_digest": ORIGIN,
                        "cycle_ref": CYCLE,
                        "previous_action": "POSITION_SPECIFIC_TIME_EXIT",
                        "reconciliation_digest": "sha256:" + "1" * 64,
                        "resolved_at_utc": "2026-07-29T00:01:00+00:00",
                    },
                    separators=(",", ":"),
                ),
            ),
        ),
    )
    database.execute(
        "INSERT INTO cycles VALUES(?, '2026-07-29', '0', ?)",
        (CYCLE, "2026-07-29T00:00:00+00:00"),
    )
    database.executemany(
        "INSERT INTO attempts VALUES(?, ?)",
        (
            ("MARKET_ENTRY", "2026-07-29T00:00:01+00:00"),
            ("EXACT_SIZE_OCO_PROTECTION", "2026-07-29T00:00:02+00:00"),
            (
                "CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT",
                "2026-07-29T00:00:03+00:00",
            ),
            ("POSITION_SPECIFIC_TIME_EXIT", "2026-07-29T00:00:04+00:00"),
        ),
    )
    if extra_entry:
        database.execute(
            "INSERT INTO attempts VALUES('MARKET_ENTRY','2026-07-29T00:00:05+00:00')"
        )
    database.commit()
    database.close()
    (root / f"activation-permit-issued.{CYCLE}.json").write_text(
        json.dumps(
            {
                "generation_digest": ORIGIN,
                "status": "ISSUED_ONE_USE_NOT_POSTED",
                "cycle_ref": CYCLE,
                "intent_digest": INTENT,
            }
        ),
        encoding="utf-8",
    )
    (root / f"activation-runtime-bound.{CYCLE}.json").write_text(
        json.dumps(
            {
                "generation_digest": ORIGIN,
                "status": "RUNTIME_BOUND_POST_NOT_ATTEMPTED",
                "intent_digest": INTENT,
            }
        ),
        encoding="utf-8",
    )
    prep = preparation_state_root(
        repository=tmp_path,
        reviewed_files_digest=ORIGIN_REVIEWED,
        generation_manifest_digest=ORIGIN,
    )
    prep.mkdir(parents=True)
    (prep / "generation_consumed.2026-07-29.json").write_text(
        json.dumps(
            {
                "generation_digest": ORIGIN,
                "status": "CONSUMED_FOR_CANARY_PREFLIGHT",
                "trading_day_jst": "2026-07-29",
            }
        ),
        encoding="utf-8",
    )


def _patch_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "require_clean_main", lambda **_kw: None)
    monkeypatch.setattr(module, "reviewed_files_digest", lambda **_kw: TARGET_REVIEWED)
    monkeypatch.setattr(
        module,
        "load_v4_gmo_frozen_generation",
        lambda **_kw: SimpleNamespace(digest=TARGET),
    )


def _inspect(tmp_path: Path):
    return inspect_successful_canary_no_post(
        repository=tmp_path,
        origin_reviewed_files_digest=ORIGIN_REVIEWED,
        origin_generation_digest=ORIGIN,
        target_reviewed_files_digest=TARGET_REVIEWED,
        target_generation_digest=TARGET,
    )


def _record(tmp_path: Path):
    return record_successful_canary_evidence_once_no_post(
        repository=tmp_path,
        origin_reviewed_files_digest=ORIGIN_REVIEWED,
        origin_generation_digest=ORIGIN,
        target_reviewed_files_digest=TARGET_REVIEWED,
        target_generation_digest=TARGET,
        state_root=tmp_path / "state",
    )


def test_successful_canary_is_fixed_and_halt_remains_activation_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch)
    _runtime(tmp_path)
    path, evidence = _record(tmp_path)
    assert path.is_file()
    assert evidence.post_flat_halt_classification == G037_TERMINAL_FLAT_HALT
    assert evidence.post_flat_halt_blocks_activation is True
    assert bool(evidence) is False
    assert _record(tmp_path)[0] == path


def test_extra_entry_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch)
    _runtime(tmp_path, extra_entry=True)
    with pytest.raises(
        V4G037CommissioningNoPostError, match="G037_ACTION_HISTORY_MISMATCH"
    ):
        _inspect(tmp_path)


def test_empty_marker_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch)
    _runtime(tmp_path)
    root = v4_gmo_runtime_state_root(repository=tmp_path, generation_digest=ORIGIN)
    (root / f"activation-permit-issued.{CYCLE}.json").write_text(
        "{}", encoding="utf-8"
    )
    with pytest.raises(
        V4G037CommissioningNoPostError, match="G037_MARKER_CONTENT_MISMATCH"
    ):
        _inspect(tmp_path)


def test_pending_transport_attempt_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch)
    _runtime(tmp_path)
    root = v4_gmo_runtime_state_root(repository=tmp_path, generation_digest=ORIGIN)
    database = sqlite3.connect(root / "coordinator.sqlite3")
    database.execute("INSERT INTO metadata VALUES('pending_transport_attempt','{}')")
    database.commit()
    database.close()
    with pytest.raises(
        V4G037CommissioningNoPostError, match="G037_ORIGIN_METADATA_MISMATCH"
    ):
        _inspect(tmp_path)


def test_dangling_symlink_state_root_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch)
    _runtime(tmp_path)
    dangling = tmp_path / "dangling-state"
    dangling.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    with pytest.raises(
        V4G037CommissioningNoPostError, match="G037_SYMLINK_ANCESTRY_REFUSED"
    ):
        record_successful_canary_evidence_once_no_post(
            repository=tmp_path,
            origin_reviewed_files_digest=ORIGIN_REVIEWED,
            origin_generation_digest=ORIGIN,
            target_reviewed_files_digest=TARGET_REVIEWED,
            target_generation_digest=TARGET,
            state_root=dangling,
        )


def test_daily_gate_rechecks_day_and_never_releases_post_flat_halt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_target(monkeypatch)
    _runtime(tmp_path)
    artifact = tmp_path / "daily.json"
    artifact.write_text(
        json.dumps(
            {
                "schema": "H11_V4_UNATTENDED_LIVE_DAILY_AUTHORIZATION_V1",
                "generation_digest": TARGET,
                "trading_day_jst": "2026-07-29",
                "maximum_entries": 1,
                "operator_authorized": True,
            }
        ),
        encoding="utf-8",
    )
    binding = verify_unattended_generation_binding_no_post(
        repository=tmp_path,
        evidence=_inspect(tmp_path),
        daily_authorization_path=artifact,
        now_utc=datetime(2026, 7, 29, tzinfo=UTC),
    )
    assert binding.generation_binding_verified is True
    assert binding.daily_authorization_clear is True
    assert binding.unattended_activation_eligible is False
    assert G037_HALT_RELEASE_REQUIRED in binding.blocked_reasons
    assert binding.permit_issued is False
    assert bool(binding) is False
