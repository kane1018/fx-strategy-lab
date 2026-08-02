"""G069-only bridge from fresh inert account evidence to runtime projection.

The G069 ARM boundary must not infer an account-wide flat state from a
position boolean. This bridge preserves and revalidates the explicit
``account_flat`` and ``active_orders_zero`` fields from the generation-bound
snapshot producer. It never performs network, credential, or broker I/O.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.h11_v4_unattended_account_snapshot_evidence_no_post import (
    V4BoundAccountSnapshotEvidenceNoPost,
    V4BoundAccountSnapshotEvidenceNoPostError,
    validate_bound_account_snapshot_evidence_no_post,
)
from app.services.h11_v4_unattended_account_snapshot_store_no_post import (
    V4AccountSnapshotStoreNoPost,
    V4AccountSnapshotStoreNoPostError,
)
from app.services.h11_v4_unattended_live_paths import (
    v4_unattended_account_snapshot_state_directory,
)

_POSITION_PROTECTION_SCHEMA = "H11_V4_G069_POSITION_PROTECTION_EVIDENCE_V1"
_SHA256_LENGTH = 71


@dataclass(frozen=True)
class G069PositionReconciliationEvidence:
    position_open: bool
    account_flat: bool
    active_orders_zero: bool
    open_positions_count: int
    active_orders_count: int
    protection_confirmed: bool
    ownership_exact: bool
    quantity_matches: bool
    generation_bound: bool
    evidence_available: bool = False
    evidence_fresh: bool = False

    def __bool__(self) -> bool:
        return False


def _unknown() -> G069PositionReconciliationEvidence:
    return G069PositionReconciliationEvidence(
        position_open=False,
        account_flat=False,
        active_orders_zero=False,
        open_positions_count=0,
        active_orders_count=0,
        protection_confirmed=False,
        ownership_exact=False,
        quantity_matches=False,
        generation_bound=False,
    )


def load_g069_position_reconciliation_no_post(
    *,
    reviewed_files_digest: str,
    generation_digest: str,
    now_utc: datetime | None = None,
    snapshot_state_root: Path | None = None,
) -> G069PositionReconciliationEvidence:
    """Load one fresh, explicitly account-wide snapshot or return unknown."""

    evaluated_at = now_utc or datetime.now(UTC)
    if evaluated_at.tzinfo is None:
        return _unknown()
    snapshot_directory = snapshot_state_root or v4_unattended_account_snapshot_state_directory(
        generation_digest=generation_digest
    )
    try:
        snapshot = V4AccountSnapshotStoreNoPost(snapshot_directory).load_completed(
            expected_reviewed_files_digest=reviewed_files_digest,
            expected_generation_digest=generation_digest,
        )
        if snapshot is None:
            return _unknown()
        _validate_snapshot(
            snapshot,
            reviewed_files_digest=reviewed_files_digest,
            generation_digest=generation_digest,
            now_utc=evaluated_at,
        )
    except (
        OSError,
        TypeError,
        V4AccountSnapshotStoreNoPostError,
        V4BoundAccountSnapshotEvidenceNoPostError,
    ):
        return _unknown()

    protection_confirmed = False
    ownership_exact = False
    quantity_matches = False
    if snapshot.open_positions_count > 0 and snapshot.active_orders_zero is False:
        snapshot_artifact_digest = getattr(snapshot, "artifact_digest", None)
        if isinstance(snapshot_artifact_digest, str):
            (
                ownership_exact,
                quantity_matches,
                protection_confirmed,
            ) = _load_position_protection_evidence(
                snapshot_state_root=snapshot_directory,
                reviewed_files_digest=reviewed_files_digest,
                generation_digest=generation_digest,
                account_snapshot_artifact_digest=snapshot_artifact_digest,
                now_utc=evaluated_at,
            )

    return G069PositionReconciliationEvidence(
        position_open=snapshot.open_positions_count > 0,
        account_flat=snapshot.account_flat,
        active_orders_zero=snapshot.active_orders_zero,
        open_positions_count=snapshot.open_positions_count,
        active_orders_count=snapshot.active_orders_count,
        protection_confirmed=protection_confirmed,
        ownership_exact=ownership_exact,
        quantity_matches=quantity_matches,
        generation_bound=True,
        evidence_available=True,
        evidence_fresh=True,
    )


def write_g069_position_protection_evidence_no_post(
    *,
    snapshot_state_root: Path,
    reviewed_files_digest: str,
    generation_digest: str,
    account_snapshot_artifact_digest: str,
    observed_at_utc: datetime,
    valid_until_utc: datetime,
    ownership_exact: bool,
    quantity_matches: bool,
    protection_confirmed: bool,
) -> None:
    """Persist explicit, sanitized position proof bound to one fresh snapshot."""

    values: tuple[object, ...] = (
        reviewed_files_digest,
        generation_digest,
        account_snapshot_artifact_digest,
    )
    if (
        any(
            type(value) is not str
            or len(value) != _SHA256_LENGTH
            or not value.startswith("sha256:")
            for value in values
        )
        or observed_at_utc.tzinfo is None
        or valid_until_utc.tzinfo is None
        or valid_until_utc <= observed_at_utc
        or any(
            type(value) is not bool
            for value in (ownership_exact, quantity_matches, protection_confirmed)
        )
        or not all((ownership_exact, quantity_matches, protection_confirmed))
    ):
        raise V4BoundAccountSnapshotEvidenceNoPostError(
            "G069_POSITION_PROTECTION_EVIDENCE_INVALID"
        )
    payload: dict[str, object] = {
        "schema": _POSITION_PROTECTION_SCHEMA,
        "reviewed_files_digest": reviewed_files_digest,
        "generation_digest": generation_digest,
        "account_snapshot_artifact_digest": account_snapshot_artifact_digest,
        "observed_at_utc": observed_at_utc.astimezone(UTC).isoformat(),
        "valid_until_utc": valid_until_utc.astimezone(UTC).isoformat(),
        "position_open": True,
        "generation_bound": True,
        "ownership_exact": ownership_exact,
        "quantity_matches": quantity_matches,
        "protection_confirmed": protection_confirmed,
        "broker_post_count": 0,
    }
    payload["artifact_digest"] = _canonical_digest(payload)
    snapshot_state_root.mkdir(parents=True, exist_ok=True)
    target = snapshot_state_root / "position-protection.json"
    temporary = snapshot_state_root / ".position-protection.json.tmp"
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise V4BoundAccountSnapshotEvidenceNoPostError(
            "G069_POSITION_PROTECTION_EVIDENCE_WRITE_FAILED"
        ) from None


def _validate_snapshot(
    snapshot: V4BoundAccountSnapshotEvidenceNoPost,
    *,
    reviewed_files_digest: str,
    generation_digest: str,
    now_utc: datetime,
) -> None:
    validate_bound_account_snapshot_evidence_no_post(
        snapshot,
        expected_reviewed_files_digest=reviewed_files_digest,
        expected_generation_digest=generation_digest,
        expected_cycle_binding_digest=snapshot.cycle_binding_digest,
        now_utc=now_utc,
    )
    if (
        snapshot.account_flat is not (snapshot.open_positions_count == 0)
        or snapshot.active_orders_zero is not (snapshot.active_orders_count == 0)
        or snapshot.broker_get_count != 3
        or snapshot.broker_write is not False
        or snapshot.broker_post_count != 0
    ):
        raise V4BoundAccountSnapshotEvidenceNoPostError(
            "G069_POSITION_EVIDENCE_ACCOUNT_STATE_INVALID"
        )


def _load_position_protection_evidence(
    *,
    snapshot_state_root: Path,
    reviewed_files_digest: str,
    generation_digest: str,
    account_snapshot_artifact_digest: str,
    now_utc: datetime,
) -> tuple[bool, bool, bool]:
    path = snapshot_state_root / "position-protection.json"
    if path.is_symlink() or not path.is_file():
        return False, False, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return False, False, False
        artifact_digest = payload.pop("artifact_digest")
        if artifact_digest != _canonical_digest(payload):
            return False, False, False
        if (
            payload.get("schema") != _POSITION_PROTECTION_SCHEMA
            or payload.get("reviewed_files_digest") != reviewed_files_digest
            or payload.get("generation_digest") != generation_digest
            or payload.get("account_snapshot_artifact_digest")
            != account_snapshot_artifact_digest
            or payload.get("position_open") is not True
            or payload.get("generation_bound") is not True
            or payload.get("broker_post_count") != 0
            or not all(
                type(payload.get(name)) is bool and payload.get(name) is True
                for name in (
                    "ownership_exact",
                    "quantity_matches",
                    "protection_confirmed",
                )
            )
        ):
            return False, False, False
        observed = datetime.fromisoformat(str(payload["observed_at_utc"])).astimezone(UTC)
        valid_until = datetime.fromisoformat(str(payload["valid_until_utc"])).astimezone(UTC)
        evaluated = now_utc.astimezone(UTC)
        if observed > evaluated or evaluated > valid_until or valid_until <= observed:
            return False, False, False
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return False, False, False
    return True, True, True


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
