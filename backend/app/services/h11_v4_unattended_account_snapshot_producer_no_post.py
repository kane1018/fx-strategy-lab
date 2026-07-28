"""One-use G026 Private-GET producer for inert controller evidence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from app.services.h11_v4_unattended_account_snapshot_store_no_post import (
    V4AccountSnapshotStoreNoPost,
)
from app.services.h11_v4_unattended_controller_snapshot_no_post import (
    controller_cycle_binding_no_post,
)
from app.services.h11_v4_unattended_shadow_private_preflight import (
    V4UnattendedShadowCredentialPair,
    bind_private_snapshot_for_controller_no_post,
    read_v4_unattended_shadow_private_snapshot,
)


class V4AccountSnapshotProducerNoPostError(RuntimeError):
    """Fixed safe terminal producer failure."""


@dataclass(frozen=True)
class V4AccountSnapshotProducerNoPostResult:
    status: str
    account_flat: bool
    active_orders_zero: bool
    broker_get_count: int = 3
    credential_read_count: int = 2
    raw_response_retained: bool = False
    identifier_exposed: bool = False
    broker_write: bool = False
    broker_post_count: int = 0
    persistent_arm_changed: bool = False
    notification_send_count: int = 0

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __bool__(self) -> bool:
        return False


def produce_account_snapshot_once_no_post(
    *,
    reviewed_files_digest: str,
    generation_digest: str,
    store_directory: Path,
    credential_pair: V4UnattendedShadowCredentialPair,
    client_factory: Callable[[], httpx.Client],
    now_factory: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> V4AccountSnapshotProducerNoPostResult:
    """Create one durable snapshot; any post-start failure is terminal."""

    started_at = _utc_now(now_factory)
    cycle_binding = controller_cycle_binding_no_post(
        generation_digest=generation_digest,
        observed_at_utc=started_at,
    )
    store = V4AccountSnapshotStoreNoPost(store_directory)
    started_digest = store.begin(
        reviewed_files_digest=reviewed_files_digest,
        generation_digest=generation_digest,
        cycle_binding_digest=cycle_binding,
        started_at_utc=started_at.isoformat(),
    )
    phase = "CREDENTIAL"
    try:
        phase = "CLIENT"
        client = client_factory()
        phase = "PRIVATE_GET"
        try:
            private = read_v4_unattended_shadow_private_snapshot(
                credential_pair=credential_pair,
                client=client,
            )
        finally:
            client.close()
        observed_at = _utc_now(now_factory)
        phase = "CYCLE"
        if (
            controller_cycle_binding_no_post(
                generation_digest=generation_digest,
                observed_at_utc=observed_at,
            )
            != cycle_binding
        ):
            raise V4AccountSnapshotProducerNoPostError(
                "ACCOUNT_SNAPSHOT_PRODUCER_CYCLE_ROLLOVER_NO_RETRY"
            )
        phase = "EVIDENCE"
        evidence = bind_private_snapshot_for_controller_no_post(
            private=private,
            reviewed_files_digest=reviewed_files_digest,
            generation_digest=generation_digest,
            cycle_binding_digest=cycle_binding,
            observed_at_utc=observed_at.isoformat(),
            valid_until_utc=(observed_at + timedelta(seconds=45)).isoformat(),
        )
        phase = "STORE"
        store.complete(
            evidence=evidence,
            started_marker_digest=started_digest,
            completed_at_utc=_utc_now(now_factory).isoformat(),
        )
        return V4AccountSnapshotProducerNoPostResult(
            status="ACCOUNT_SNAPSHOT_PRODUCED_NO_POST",
            account_flat=private.account_flat,
            active_orders_zero=private.active_orders_zero,
        )
    except Exception:
        store.record_failure(
            reviewed_files_digest=reviewed_files_digest,
            generation_digest=generation_digest,
            cycle_binding_digest=cycle_binding,
            started_marker_digest=started_digest,
            failed_at_utc=_utc_now(now_factory).isoformat(),
            failure_phase=phase,
        )
        raise V4AccountSnapshotProducerNoPostError(
            "ACCOUNT_SNAPSHOT_PRODUCER_FAILED_NO_RETRY"
        ) from None


def _utc_now(factory: Callable[[], datetime]) -> datetime:
    value = factory()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise V4AccountSnapshotProducerNoPostError(
            "ACCOUNT_SNAPSHOT_PRODUCER_CLOCK_INVALID"
        )
    return value.astimezone(UTC)
