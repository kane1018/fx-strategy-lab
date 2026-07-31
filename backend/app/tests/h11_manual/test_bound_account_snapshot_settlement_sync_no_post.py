from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.h11_manual.settlement_sync import (
    BoundAccountSnapshotManualSettlementReadClient,
    ManualSettlementSyncError,
    SyncAvailability,
)
from app.services.h11_v4_unattended_account_snapshot_evidence_no_post import (
    build_account_snapshot_operation_marker_no_post,
    build_bound_account_snapshot_evidence_no_post,
)
from app.services.h11_v4_unattended_account_snapshot_store_no_post import (
    V4AccountSnapshotStoreNoPost,
)
from app.services.h11_v4_unattended_controller_snapshot_no_post import (
    controller_cycle_binding_no_post,
)

_REVIEWED = "sha256:" + ("a" * 64)
_GENERATION = "sha256:" + ("b" * 64)


def _reader(tmp_path, *, now: datetime, valid_until: datetime):
    cycle_binding = controller_cycle_binding_no_post(
        generation_digest=_GENERATION,
        observed_at_utc=now,
    )
    marker = build_account_snapshot_operation_marker_no_post(
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
        cycle_binding_digest=cycle_binding,
        observed_at_utc=now.isoformat(),
        valid_until_utc=valid_until.isoformat(),
        broker_read_performed=True,
        broker_get_count=3,
        open_positions_count=0,
        active_orders_count=0,
    )
    evidence = build_bound_account_snapshot_evidence_no_post(
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
        cycle_binding_digest=cycle_binding,
        operation_marker=marker,
        observed_at_utc=now.isoformat(),
        valid_until_utc=valid_until.isoformat(),
        broker_read_performed=True,
        broker_get_count=3,
        open_positions_count=0,
        active_orders_count=0,
        account_flat=True,
        active_orders_zero=True,
    )
    store = V4AccountSnapshotStoreNoPost(tmp_path)
    started_digest = store.begin(
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
        cycle_binding_digest=cycle_binding,
        started_at_utc=now.isoformat(),
    )
    store.complete(
        evidence=evidence,
        started_marker_digest=started_digest,
        completed_at_utc=now.isoformat(),
    )
    return BoundAccountSnapshotManualSettlementReadClient(
        store=store,
        expected_reviewed_files_digest=_REVIEWED,
        expected_generation_digest=_GENERATION,
        now_factory=lambda: now + timedelta(seconds=5),
    )


def test_fresh_bound_flat_evidence_is_local_and_non_post(tmp_path) -> None:
    now = datetime(2026, 7, 31, 0, 0, tzinfo=UTC)
    reader = _reader(tmp_path, now=now, valid_until=now + timedelta(seconds=30))

    assert reader.availability is SyncAvailability.CONFIGURED
    snapshot = reader.fetch_snapshot(symbol="USD_JPY")
    assert snapshot.executions == ()
    assert snapshot.open_positions == ()
    assert snapshot.source == "H11_V4_BOUND_ACCOUNT_SNAPSHOT_NO_POST"


def test_expired_bound_flat_evidence_fails_closed(tmp_path) -> None:
    now = datetime(2026, 7, 31, 0, 0, tzinfo=UTC)
    reader = _reader(tmp_path, now=now, valid_until=now + timedelta(seconds=4))

    assert reader.availability is SyncAvailability.NOT_CONFIGURED
    try:
        reader.fetch_snapshot(symbol="USD_JPY")
    except ManualSettlementSyncError as error:
        assert str(error) == "BROKER_SYNC_BOUND_EVIDENCE_UNAVAILABLE"
    else:
        raise AssertionError("expired evidence must not be exposed")
