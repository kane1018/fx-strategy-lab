from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services import h11_v4_unattended_account_snapshot_evidence_no_post as subject


def _evidence(
    *,
    now: datetime,
    reviewed: str = "sha256:" + ("a" * 64),
    generation: str = "sha256:" + ("b" * 64),
    cycle: str = "sha256:" + ("c" * 64),
    positions: int = 0,
    active: int = 0,
    broker_read_performed: bool = True,
    broker_post_count: int = 0,
) -> subject.V4BoundAccountSnapshotEvidenceNoPost:
    marker = subject.build_account_snapshot_operation_marker_no_post(
        reviewed_files_digest=reviewed,
        generation_digest=generation,
        cycle_binding_digest=cycle,
        observed_at_utc=(now - timedelta(seconds=1)).isoformat(),
        valid_until_utc=(now + timedelta(seconds=30)).isoformat(),
        broker_read_performed=broker_read_performed,
        broker_get_count=3,
        open_positions_count=positions,
        active_orders_count=active,
        broker_post_count=broker_post_count,
    )
    return subject.build_bound_account_snapshot_evidence_no_post(
        reviewed_files_digest=reviewed,
        generation_digest=generation,
        cycle_binding_digest=cycle,
        operation_marker=marker,
        observed_at_utc=(now - timedelta(seconds=1)).isoformat(),
        valid_until_utc=(now + timedelta(seconds=30)).isoformat(),
        broker_read_performed=broker_read_performed,
        broker_get_count=3,
        open_positions_count=positions,
        active_orders_count=active,
        account_flat=positions == 0,
        active_orders_zero=active == 0,
        broker_post_count=broker_post_count,
    )


def test_exact_bound_fresh_evidence_is_accepted() -> None:
    now = datetime.now(UTC)
    evidence = _evidence(now=now)
    subject.validate_bound_account_snapshot_evidence_no_post(
        evidence,
        expected_reviewed_files_digest=evidence.reviewed_files_digest,
        expected_generation_digest=evidence.generation_digest,
        expected_cycle_binding_digest=evidence.cycle_binding_digest,
        now_utc=now,
    )
    assert bool(evidence) is False
    assert evidence.broker_write is False
    assert evidence.broker_post_count == 0


@pytest.mark.parametrize("field", ("reviewed", "generation", "cycle"))
def test_binding_mismatch_is_rejected(field: str) -> None:
    now = datetime.now(UTC)
    evidence = _evidence(now=now)
    expected = {
        "expected_reviewed_files_digest": evidence.reviewed_files_digest,
        "expected_generation_digest": evidence.generation_digest,
        "expected_cycle_binding_digest": evidence.cycle_binding_digest,
    }
    expected_key = {
        "reviewed": "expected_reviewed_files_digest",
        "generation": "expected_generation_digest",
        "cycle": "expected_cycle_binding_digest",
    }[field]
    expected[expected_key] = "sha256:" + ("9" * 64)
    with pytest.raises(
        subject.V4BoundAccountSnapshotEvidenceNoPostError,
        match="BINDING_INVALID",
    ):
        subject.validate_bound_account_snapshot_evidence_no_post(
            evidence,
            now_utc=now,
            **expected,
        )


def test_stale_or_oversized_window_is_rejected() -> None:
    now = datetime.now(UTC)
    marker = subject.build_account_snapshot_operation_marker_no_post(
        reviewed_files_digest="sha256:" + ("a" * 64),
        generation_digest="sha256:" + ("b" * 64),
        cycle_binding_digest="sha256:" + ("c" * 64),
        observed_at_utc=(now - timedelta(minutes=2)).isoformat(),
        valid_until_utc=(now - timedelta(minutes=1)).isoformat(),
        broker_read_performed=True,
        broker_get_count=3,
        open_positions_count=0,
        active_orders_count=0,
    )
    stale = subject.build_bound_account_snapshot_evidence_no_post(
        reviewed_files_digest="sha256:" + ("a" * 64),
        generation_digest="sha256:" + ("b" * 64),
        cycle_binding_digest="sha256:" + ("c" * 64),
        operation_marker=marker,
        observed_at_utc=(now - timedelta(minutes=2)).isoformat(),
        valid_until_utc=(now - timedelta(minutes=1)).isoformat(),
        broker_read_performed=True,
        broker_get_count=3,
        open_positions_count=0,
        active_orders_count=0,
        account_flat=True,
        active_orders_zero=True,
    )
    with pytest.raises(
        subject.V4BoundAccountSnapshotEvidenceNoPostError,
        match="NOT_FRESH",
    ):
        subject.validate_bound_account_snapshot_evidence_no_post(
            stale,
            expected_reviewed_files_digest=stale.reviewed_files_digest,
            expected_generation_digest=stale.generation_digest,
            expected_cycle_binding_digest=stale.cycle_binding_digest,
            now_utc=now,
        )


@pytest.mark.parametrize(
    "overrides",
    (
        {"broker_read_performed": False},
        {"broker_post_count": 1},
    ),
)
def test_non_observed_or_write_capable_shape_is_rejected(
    overrides: dict[str, object],
) -> None:
    now = datetime.now(UTC)
    with pytest.raises(
        subject.V4BoundAccountSnapshotEvidenceNoPostError,
        match="ACCOUNT_SNAPSHOT_OPERATION_MARKER_INVALID",
    ):
        _evidence(now=now, **overrides)


def test_cross_generation_or_noncanonical_marker_is_rejected() -> None:
    now = datetime.now(UTC)
    marker = subject.build_account_snapshot_operation_marker_no_post(
        reviewed_files_digest="sha256:" + ("a" * 64),
        generation_digest="sha256:" + ("9" * 64),
        cycle_binding_digest="sha256:" + ("c" * 64),
        observed_at_utc=(now - timedelta(seconds=1)).isoformat(),
        valid_until_utc=(now + timedelta(seconds=30)).isoformat(),
        broker_read_performed=True,
        broker_get_count=3,
        open_positions_count=0,
        active_orders_count=0,
    )
    with pytest.raises(
        subject.V4BoundAccountSnapshotEvidenceNoPostError,
        match="SHAPE_INVALID",
    ):
        subject.build_bound_account_snapshot_evidence_no_post(
            reviewed_files_digest="sha256:" + ("a" * 64),
            generation_digest="sha256:" + ("b" * 64),
            cycle_binding_digest="sha256:" + ("c" * 64),
            operation_marker=marker,
            observed_at_utc=marker.observed_at_utc,
            valid_until_utc=marker.valid_until_utc,
            broker_read_performed=True,
            broker_get_count=3,
            open_positions_count=0,
            active_orders_count=0,
            account_flat=True,
            active_orders_zero=True,
        )
