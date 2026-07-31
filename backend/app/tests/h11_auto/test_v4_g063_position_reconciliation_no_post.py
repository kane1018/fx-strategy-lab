from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.services.h11_v4_g063_position_reconciliation_no_post import (
    load_g063_position_reconciliation_no_post,
    write_g063_position_reconciliation_no_post,
)


def _write_evidence(root: Path, *, generation_digest: str, **values: bool) -> None:
    (root / "position-reconciliation.json").write_text(
        json.dumps(
            {
                "generation_digest": generation_digest,
                "observed_at_utc": datetime.now(UTC).isoformat(),
                **values,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_missing_evidence_never_proves_position_safety(tmp_path: Path) -> None:
    evidence = load_g063_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest="sha256:g063",
    )

    assert evidence.position_open is False
    assert evidence.protection_confirmed is False
    assert evidence.ownership_exact is False
    assert evidence.quantity_matches is False
    assert evidence.generation_bound is False
    assert bool(evidence) is False


def test_matching_explicit_evidence_is_consumed_without_broker_access(
    tmp_path: Path,
) -> None:
    _write_evidence(
        tmp_path,
        generation_digest="sha256:g063",
        position_open=True,
        protection_confirmed=True,
        ownership_exact=True,
        quantity_matches=True,
        generation_bound=True,
    )

    evidence = load_g063_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest="sha256:g063",
    )

    assert evidence.position_open is True
    assert evidence.protection_confirmed is True
    assert evidence.ownership_exact is True
    assert evidence.quantity_matches is True
    assert evidence.generation_bound is True


def test_generation_mismatch_and_incomplete_fields_fail_closed(tmp_path: Path) -> None:
    _write_evidence(
        tmp_path,
        generation_digest="sha256:old",
        position_open=True,
        protection_confirmed=True,
        ownership_exact=True,
        quantity_matches=True,
        generation_bound=True,
    )
    mismatch = load_g063_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest="sha256:g063",
    )
    assert mismatch.ownership_exact is False

    _write_evidence(
        tmp_path,
        generation_digest="sha256:g063",
        position_open=True,
        protection_confirmed=True,
        ownership_exact=True,
        quantity_matches="true",  # type: ignore[arg-type]
        generation_bound=True,
    )
    incomplete = load_g063_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest="sha256:g063",
    )
    assert incomplete.protection_confirmed is False
    assert incomplete.quantity_matches is False


def test_stale_evidence_fails_closed(tmp_path: Path) -> None:
    observed_at = datetime(2026, 7, 31, 1, 0, tzinfo=UTC)
    write_g063_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest="sha256:g063",
        position_open=True,
        protection_confirmed=True,
        ownership_exact=True,
        quantity_matches=True,
        generation_bound=True,
        observed_at_utc=observed_at,
    )

    evidence = load_g063_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest="sha256:g063",
        now_utc=observed_at + timedelta(seconds=61),
    )

    assert evidence.position_open is False
    assert evidence.protection_confirmed is False


def test_writer_round_trips_only_sanitized_boolean_evidence(tmp_path: Path) -> None:
    observed_at = datetime(2026, 7, 31, 1, 0, tzinfo=UTC)
    write_g063_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest="sha256:g063",
        position_open=True,
        protection_confirmed=True,
        ownership_exact=True,
        quantity_matches=True,
        generation_bound=True,
        observed_at_utc=observed_at,
    )

    evidence = load_g063_position_reconciliation_no_post(
        state_root=tmp_path,
        generation_digest="sha256:g063",
        now_utc=observed_at,
    )
    assert evidence.position_open is True
    assert evidence.protection_confirmed is True
    assert evidence.ownership_exact is True
    assert evidence.quantity_matches is True
