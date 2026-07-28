"""Inert, generation-bound account snapshot evidence for no-POST controllers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

_SCHEMA = "H11_V4_UNATTENDED_ACCOUNT_SNAPSHOT_EVIDENCE_NO_POST_V1"
_STATUS = "ACCOUNT_SNAPSHOT_OBSERVED_READ_ONLY_NO_POST"
_MARKER_SCHEMA = "H11_V4_ACCOUNT_SNAPSHOT_OPERATION_MARKER_NO_POST_V1"
_MARKER_STATUS = "ACCOUNT_SNAPSHOT_GET_OPERATION_COMPLETED_NO_POST"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class V4BoundAccountSnapshotEvidenceNoPostError(ValueError):
    """Fixed safe failure for malformed or stale inert account evidence."""


@dataclass(frozen=True)
class V4AccountSnapshotOperationMarkerNoPost:
    schema: str
    reviewed_files_digest: str
    generation_digest: str
    cycle_binding_digest: str
    observed_at_utc: str
    valid_until_utc: str
    status: str
    broker_read_performed: bool
    broker_get_count: int
    open_positions_count: int
    active_orders_count: int
    broker_write: bool
    broker_post_count: int
    artifact_digest: str

    def __post_init__(self) -> None:
        _validate_marker_shape(self)

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4BoundAccountSnapshotEvidenceNoPost:
    schema: str
    reviewed_files_digest: str
    generation_digest: str
    cycle_binding_digest: str
    operation_marker: V4AccountSnapshotOperationMarkerNoPost
    observed_at_utc: str
    valid_until_utc: str
    status: str
    broker_read_performed: bool
    broker_get_count: int
    open_positions_count: int
    active_orders_count: int
    account_flat: bool
    active_orders_zero: bool
    raw_response_retained: bool
    identifier_exposed: bool
    broker_write: bool
    broker_post_count: int
    artifact_digest: str

    def __post_init__(self) -> None:
        _validate_shape(self)

    def __bool__(self) -> bool:
        return False


def build_bound_account_snapshot_evidence_no_post(
    *,
    reviewed_files_digest: str,
    generation_digest: str,
    cycle_binding_digest: str,
    operation_marker: V4AccountSnapshotOperationMarkerNoPost,
    observed_at_utc: str,
    valid_until_utc: str,
    broker_read_performed: bool,
    broker_get_count: int,
    open_positions_count: int,
    active_orders_count: int,
    account_flat: bool,
    active_orders_zero: bool,
    raw_response_retained: bool = False,
    identifier_exposed: bool = False,
    broker_write: bool = False,
    broker_post_count: int = 0,
) -> V4BoundAccountSnapshotEvidenceNoPost:
    payload: dict[str, object] = {
        "schema": _SCHEMA,
        "reviewed_files_digest": reviewed_files_digest,
        "generation_digest": generation_digest,
        "cycle_binding_digest": cycle_binding_digest,
        "operation_marker": asdict(operation_marker),
        "observed_at_utc": observed_at_utc,
        "valid_until_utc": valid_until_utc,
        "status": _STATUS,
        "broker_read_performed": broker_read_performed,
        "broker_get_count": broker_get_count,
        "open_positions_count": open_positions_count,
        "active_orders_count": active_orders_count,
        "account_flat": account_flat,
        "active_orders_zero": active_orders_zero,
        "raw_response_retained": raw_response_retained,
        "identifier_exposed": identifier_exposed,
        "broker_write": broker_write,
        "broker_post_count": broker_post_count,
    }
    return V4BoundAccountSnapshotEvidenceNoPost(
        schema=_SCHEMA,
        reviewed_files_digest=reviewed_files_digest,
        generation_digest=generation_digest,
        cycle_binding_digest=cycle_binding_digest,
        operation_marker=operation_marker,
        observed_at_utc=observed_at_utc,
        valid_until_utc=valid_until_utc,
        status=_STATUS,
        broker_read_performed=broker_read_performed,
        broker_get_count=broker_get_count,
        open_positions_count=open_positions_count,
        active_orders_count=active_orders_count,
        account_flat=account_flat,
        active_orders_zero=active_orders_zero,
        raw_response_retained=raw_response_retained,
        identifier_exposed=identifier_exposed,
        broker_write=broker_write,
        broker_post_count=broker_post_count,
        artifact_digest=_canonical_digest(payload),
    )


def build_account_snapshot_operation_marker_no_post(
    *,
    reviewed_files_digest: str,
    generation_digest: str,
    cycle_binding_digest: str,
    observed_at_utc: str,
    valid_until_utc: str,
    broker_read_performed: bool,
    broker_get_count: int,
    open_positions_count: int,
    active_orders_count: int,
    broker_write: bool = False,
    broker_post_count: int = 0,
) -> V4AccountSnapshotOperationMarkerNoPost:
    payload: dict[str, object] = {
        "schema": _MARKER_SCHEMA,
        "reviewed_files_digest": reviewed_files_digest,
        "generation_digest": generation_digest,
        "cycle_binding_digest": cycle_binding_digest,
        "observed_at_utc": observed_at_utc,
        "valid_until_utc": valid_until_utc,
        "status": _MARKER_STATUS,
        "broker_read_performed": broker_read_performed,
        "broker_get_count": broker_get_count,
        "open_positions_count": open_positions_count,
        "active_orders_count": active_orders_count,
        "broker_write": broker_write,
        "broker_post_count": broker_post_count,
    }
    return V4AccountSnapshotOperationMarkerNoPost(
        **payload,
        artifact_digest=_canonical_digest(payload),
    )


def validate_bound_account_snapshot_evidence_no_post(
    evidence: V4BoundAccountSnapshotEvidenceNoPost,
    *,
    expected_reviewed_files_digest: str,
    expected_generation_digest: str,
    expected_cycle_binding_digest: str,
    now_utc: datetime,
) -> None:
    if type(evidence) is not V4BoundAccountSnapshotEvidenceNoPost:
        raise V4BoundAccountSnapshotEvidenceNoPostError(
            "BOUND_ACCOUNT_SNAPSHOT_TYPE_INVALID"
        )
    _validate_shape(evidence)
    if (
        evidence.reviewed_files_digest != expected_reviewed_files_digest
        or evidence.generation_digest != expected_generation_digest
        or evidence.cycle_binding_digest != expected_cycle_binding_digest
    ):
        raise V4BoundAccountSnapshotEvidenceNoPostError(
            "BOUND_ACCOUNT_SNAPSHOT_BINDING_INVALID"
        )
    if now_utc.tzinfo is None:
        raise V4BoundAccountSnapshotEvidenceNoPostError(
            "BOUND_ACCOUNT_SNAPSHOT_CLOCK_INVALID"
        )
    observed = _parse_utc(evidence.observed_at_utc)
    valid_until = _parse_utc(evidence.valid_until_utc)
    evaluated = now_utc.astimezone(UTC)
    if (
        observed > evaluated
        or evaluated > valid_until
        or valid_until <= observed
        or (valid_until - observed).total_seconds() > 60
    ):
        raise V4BoundAccountSnapshotEvidenceNoPostError(
            "BOUND_ACCOUNT_SNAPSHOT_NOT_FRESH"
        )


def _validate_shape(evidence: V4BoundAccountSnapshotEvidenceNoPost) -> None:
    payload = asdict(evidence)
    artifact_digest = payload.pop("artifact_digest")
    if (
        evidence.schema != _SCHEMA
        or evidence.status != _STATUS
        or any(
            type(value) is not str or _SHA256.fullmatch(value) is None
            for value in (
                evidence.reviewed_files_digest,
                evidence.generation_digest,
                evidence.cycle_binding_digest,
                artifact_digest,
            )
        )
        or artifact_digest != _canonical_digest(payload)
        or type(evidence.operation_marker)
        is not V4AccountSnapshotOperationMarkerNoPost
        or evidence.operation_marker.reviewed_files_digest
        != evidence.reviewed_files_digest
        or evidence.operation_marker.generation_digest != evidence.generation_digest
        or evidence.operation_marker.cycle_binding_digest
        != evidence.cycle_binding_digest
        or evidence.operation_marker.observed_at_utc != evidence.observed_at_utc
        or evidence.operation_marker.valid_until_utc != evidence.valid_until_utc
        or evidence.operation_marker.broker_read_performed
        != evidence.broker_read_performed
        or evidence.operation_marker.broker_get_count != evidence.broker_get_count
        or evidence.operation_marker.open_positions_count
        != evidence.open_positions_count
        or evidence.operation_marker.active_orders_count
        != evidence.active_orders_count
        or evidence.broker_read_performed is not True
        or type(evidence.broker_get_count) is not int
        or evidence.broker_get_count != 3
        or type(evidence.open_positions_count) is not int
        or evidence.open_positions_count < 0
        or type(evidence.active_orders_count) is not int
        or evidence.active_orders_count < 0
        or type(evidence.account_flat) is not bool
        or type(evidence.active_orders_zero) is not bool
        or evidence.account_flat != (evidence.open_positions_count == 0)
        or evidence.active_orders_zero != (evidence.active_orders_count == 0)
        or evidence.raw_response_retained is not False
        or evidence.identifier_exposed is not False
        or evidence.broker_write is not False
        or type(evidence.broker_post_count) is not int
        or evidence.broker_post_count != 0
    ):
        raise V4BoundAccountSnapshotEvidenceNoPostError(
            "BOUND_ACCOUNT_SNAPSHOT_SHAPE_INVALID"
        )
    _parse_utc(evidence.observed_at_utc)
    _parse_utc(evidence.valid_until_utc)


def _validate_marker_shape(marker: V4AccountSnapshotOperationMarkerNoPost) -> None:
    payload = asdict(marker)
    artifact_digest = payload.pop("artifact_digest")
    if (
        marker.schema != _MARKER_SCHEMA
        or marker.status != _MARKER_STATUS
        or any(
            type(value) is not str or _SHA256.fullmatch(value) is None
            for value in (
                marker.reviewed_files_digest,
                marker.generation_digest,
                marker.cycle_binding_digest,
                artifact_digest,
            )
        )
        or artifact_digest != _canonical_digest(payload)
        or marker.broker_read_performed is not True
        or type(marker.broker_get_count) is not int
        or marker.broker_get_count != 3
        or type(marker.open_positions_count) is not int
        or marker.open_positions_count < 0
        or type(marker.active_orders_count) is not int
        or marker.active_orders_count < 0
        or marker.broker_write is not False
        or type(marker.broker_post_count) is not int
        or marker.broker_post_count != 0
    ):
        raise V4BoundAccountSnapshotEvidenceNoPostError(
            "ACCOUNT_SNAPSHOT_OPERATION_MARKER_INVALID"
        )
    _parse_utc(marker.observed_at_utc)
    _parse_utc(marker.valid_until_utc)


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise V4BoundAccountSnapshotEvidenceNoPostError(
            "BOUND_ACCOUNT_SNAPSHOT_CLOCK_INVALID"
        ) from None
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise V4BoundAccountSnapshotEvidenceNoPostError(
            "BOUND_ACCOUNT_SNAPSHOT_CLOCK_INVALID"
        )
    return parsed.astimezone(UTC)


def _canonical_digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
