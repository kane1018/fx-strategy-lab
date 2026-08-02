"""G065-only bridge from inert snapshot evidence to position projection.

The bridge never queries a broker and never infers ownership, quantity, or
protection. A flat snapshot can prove only that the entry gate may be
considered; an open or otherwise non-flat snapshot remains HALTED until
separate generation-bound protection evidence is present.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.services.h11_v4_g065_position_reconciliation_no_post import (
    G065PositionReconciliationEvidence,
    write_g065_position_reconciliation_no_post,
)
from app.services.h11_v4_unattended_account_snapshot_evidence_no_post import (
    validate_bound_account_snapshot_evidence_no_post,
)
from app.services.h11_v4_unattended_account_snapshot_store_no_post import (
    V4AccountSnapshotStoreNoPost,
)
from app.services.h11_v4_unattended_live_paths import (
    v4_unattended_account_snapshot_state_directory,
)


def materialize_g065_position_reconciliation_no_post(
    *,
    state_root: Path,
    generation_digest: str,
    reviewed_files_digest: str,
    now_utc: datetime,
    snapshot_state_root: Path | None = None,
) -> G065PositionReconciliationEvidence | None:
    """Materialize only a fresh, already-completed inert snapshot.

    Missing or malformed snapshot evidence is not converted to flat. The
    caller must treat ``None`` as an unknown/HALTED condition.
    """

    if now_utc.tzinfo is None:
        return None
    snapshot_directory = snapshot_state_root or v4_unattended_account_snapshot_state_directory(
        generation_digest=generation_digest
    )
    snapshot = V4AccountSnapshotStoreNoPost(snapshot_directory).load_completed(
        expected_reviewed_files_digest=reviewed_files_digest,
        expected_generation_digest=generation_digest,
    )
    if snapshot is None:
        return None
    validate_bound_account_snapshot_evidence_no_post(
        snapshot,
        expected_reviewed_files_digest=reviewed_files_digest,
        expected_generation_digest=generation_digest,
        expected_cycle_binding_digest=snapshot.cycle_binding_digest,
        now_utc=now_utc,
    )
    # The store validates its generation binding. The reviewed-files digest is
    # checked by the caller before this bridge is used; do not weaken that
    # contract with an inferred value here.
    position_open = not (snapshot.account_flat and snapshot.active_orders_zero)
    observed = now_utc.astimezone(UTC)
    write_g065_position_reconciliation_no_post(
        state_root=state_root,
        generation_digest=generation_digest,
        position_open=position_open,
        protection_confirmed=False,
        ownership_exact=False,
        quantity_matches=False,
        generation_bound=True,
        observed_at_utc=observed,
    )
    return G065PositionReconciliationEvidence(
        position_open=position_open,
        protection_confirmed=False,
        ownership_exact=False,
        quantity_matches=False,
        generation_bound=True,
        evidence_available=True,
        evidence_fresh=True,
    )
