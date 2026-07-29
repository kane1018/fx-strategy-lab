"""G037 successful-canary evidence and unattended binding, strictly no POST."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import MISSING, asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    preparation_state_root,
    require_clean_main,
    reviewed_files_digest,
)
from app.h11_auto.v4_gmo_generation import (
    V4GmoFrozenGeneration,
    load_v4_gmo_frozen_generation,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_unattended_live_authorization import (
    check_operator_daily_authorization,
)
from app.services.h11_v4_unattended_live_paths import (
    v4_unattended_g037_canary_evidence_path,
)

G037_CANARY_EVIDENCE_SCHEMA = "H11_V4_G037_SUCCESSFUL_CANARY_EVIDENCE_NO_POST_V1"
G037_TERMINAL_FLAT_HALT = "TERMINAL_FLAT_RECONCILED_HALT_LATCHED"
G037_HALT_RELEASE_REQUIRED = "POST_FLAT_HALT_REQUIRES_SEPARATE_RELEASE_POLICY"
_EVIDENCE_ISSUER_TOKEN = object()
_ACTION_COUNTS = {
    "MARKET_ENTRY": 1,
    "EXACT_SIZE_OCO_PROTECTION": 1,
    "CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT": 1,
    "POSITION_SPECIFIC_TIME_EXIT": 1,
}


class V4G037CommissioningNoPostError(RuntimeError):
    """Fixed safe G037 commissioning failure."""


@dataclass(frozen=True)
class V4G037SuccessfulCanaryEvidenceNoPost:
    schema: str
    origin_reviewed_files_digest: str
    origin_generation_digest: str
    target_reviewed_files_digest: str
    target_generation_digest: str
    cycle_count: int
    flat_cycle_count: int
    protected_cycle_count: int
    unresolved_cycle_count: int
    entry_attempt_count: int
    protection_attempt_count: int
    risk_reducing_attempt_count: int
    permit_marker_count: int
    runtime_binding_marker_count: int
    generation_consumed_marker_count: int
    post_flat_halt_classification: str
    successful_canary_fixed: bool
    post_flat_halt_blocks_activation: bool
    broker_write: bool = False
    broker_post_count: int = 0
    credential_read: bool = False
    private_api_read: bool = False
    permit_issued: bool = False
    broker_post_authorized: bool = False
    _issuer_token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        for digest in (
            self.origin_reviewed_files_digest,
            self.origin_generation_digest,
            self.target_reviewed_files_digest,
            self.target_generation_digest,
        ):
            _require_digest(digest)
        if (
            self.schema != G037_CANARY_EVIDENCE_SCHEMA
            or self.cycle_count != 1
            or self.flat_cycle_count != 1
            or self.protected_cycle_count != 1
            or self.unresolved_cycle_count != 0
            or self.entry_attempt_count != 1
            or self.protection_attempt_count != 1
            or self.risk_reducing_attempt_count != 2
            or self.permit_marker_count != 1
            or self.runtime_binding_marker_count != 1
            or self.generation_consumed_marker_count != 1
            or self.post_flat_halt_classification != G037_TERMINAL_FLAT_HALT
            or self.successful_canary_fixed is not True
            or self.post_flat_halt_blocks_activation is not True
            or self.broker_write is not False
            or self.broker_post_count != 0
            or self.credential_read is not False
            or self.private_api_read is not False
            or self.permit_issued is not False
            or self.broker_post_authorized is not False
            or self._issuer_token is not _EVIDENCE_ISSUER_TOKEN
        ):
            raise V4G037CommissioningNoPostError("G037_CANARY_EVIDENCE_INVALID")

    def _payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("_issuer_token")
        return payload

    @property
    def evidence_digest(self) -> str:
        encoded = json.dumps(
            self._payload(), sort_keys=True, separators=(",", ":")
        ).encode()
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    def to_safe_dict(self) -> dict[str, object]:
        return {**self._payload(), "evidence_digest": self.evidence_digest}

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4G037UnattendedBindingNoPost:
    generation_binding_verified: bool
    daily_authorization_clear: bool
    unattended_activation_eligible: bool
    blocked_reasons: tuple[str, ...]
    permit_issued: bool = False
    broker_post_authorized: bool = False
    broker_write: bool = False
    broker_post_count: int = 0
    credential_read: bool = False
    private_api_read: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.generation_binding_verified) is not bool
            or type(self.daily_authorization_clear) is not bool
            or self.unattended_activation_eligible is not False
            or G037_HALT_RELEASE_REQUIRED not in self.blocked_reasons
            or self.permit_issued is not False
            or self.broker_post_authorized is not False
            or self.broker_write is not False
            or self.broker_post_count != 0
            or self.credential_read is not False
            or self.private_api_read is not False
        ):
            raise V4G037CommissioningNoPostError("G037_BINDING_INVALID")

    def __bool__(self) -> bool:
        return False


def inspect_successful_canary_no_post(
    *,
    repository: Path,
    origin_reviewed_files_digest: str,
    origin_generation_digest: str,
    target_reviewed_files_digest: str,
    target_generation_digest: str,
) -> V4G037SuccessfulCanaryEvidenceNoPost:
    """Authenticate and inspect local canary state through read-only handles."""

    for digest in (
        origin_reviewed_files_digest,
        origin_generation_digest,
        target_reviewed_files_digest,
        target_generation_digest,
    ):
        _require_digest(digest)
    require_clean_main(repository=repository)
    actual_reviewed_digest = reviewed_files_digest(repository=repository)
    if actual_reviewed_digest != target_reviewed_files_digest:
        raise V4G037CommissioningNoPostError("G037_TARGET_REVIEWED_DIGEST_MISMATCH")
    target_generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=actual_reviewed_digest
    )
    if target_generation.digest != target_generation_digest:
        raise V4G037CommissioningNoPostError("G037_TARGET_GENERATION_MISMATCH")

    runtime_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=origin_generation_digest
    )
    _reject_symlink_ancestry(runtime_root)
    database = runtime_root / "coordinator.sqlite3"
    if database.is_symlink() or not database.is_file():
        raise V4G037CommissioningNoPostError("G037_COORDINATOR_DB_UNAVAILABLE")
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        metadata = {
            str(row["key"]): str(row["value"])
            for row in connection.execute("SELECT key, value FROM metadata")
        }
        cycle = connection.execute(
            """
            SELECT COUNT(*) cycle_count, MIN(cycle_ref) cycle_ref,
              MIN(trading_day_jst) trading_day_jst,
              SUM(realized_pnl_jpy IS NOT NULL) flat_count,
              SUM(protection_confirmed_at_utc IS NOT NULL) protected_count,
              SUM(realized_pnl_jpy IS NULL) unresolved_count
            FROM cycles
            """
        ).fetchone()
        attempts = {
            str(row["action"]): int(row["attempt_count"])
            for row in connection.execute(
                "SELECT action, COUNT(*) attempt_count FROM attempts GROUP BY action"
            )
        }
        latest_attempt = connection.execute(
            "SELECT MAX(attempted_at_utc) value FROM attempts"
        ).fetchone()["value"]
    except sqlite3.Error as error:
        raise V4G037CommissioningNoPostError(
            "G037_COORDINATOR_DB_READ_FAILED"
        ) from error
    finally:
        if "connection" in locals():
            connection.close()

    if (
        metadata.get("generation_digest") != origin_generation_digest
        or metadata.get("implementation_digest") != origin_reviewed_files_digest
        or "pending_transport_attempt" in metadata
    ):
        raise V4G037CommissioningNoPostError("G037_ORIGIN_METADATA_MISMATCH")
    try:
        manifest_payload = json.loads(metadata.get("generation_manifest", ""))
        if not isinstance(manifest_payload, dict):
            raise TypeError
        generation_fields = fields(V4GmoFrozenGeneration)
        expected_keys = {item.name for item in generation_fields}
        required_keys = {
            item.name
            for item in generation_fields
            if item.default is MISSING and item.default_factory is MISSING
        }
        if not required_keys.issubset(manifest_payload) or (
            set(manifest_payload) - expected_keys
        ):
            raise TypeError
        normalized_manifest = dict(manifest_payload)
        normalized_manifest["blocked_hours_jst"] = tuple(
            normalized_manifest["blocked_hours_jst"]
        )
        normalized_manifest["weekend_days_jst"] = tuple(
            normalized_manifest["weekend_days_jst"]
        )
        origin_generation = V4GmoFrozenGeneration(**normalized_manifest)
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise V4G037CommissioningNoPostError(
            "G037_ORIGIN_MANIFEST_INVALID"
        ) from error
    if (
        origin_generation.implementation_digest != origin_reviewed_files_digest
        or origin_generation.digest != origin_generation_digest
    ):
        raise V4G037CommissioningNoPostError("G037_ORIGIN_MANIFEST_MISMATCH")
    if attempts != _ACTION_COUNTS:
        raise V4G037CommissioningNoPostError("G037_ACTION_HISTORY_MISMATCH")

    pending = _load_json_object(metadata.get("pending_transport_resolution", ""))
    reconciliation_digest = pending.get("reconciliation_digest")
    if (
        pending.get("classification") != "FLAT_OR_REJECTED"
        or pending.get("generation_digest") != origin_generation_digest
        or pending.get("cycle_ref") != cycle["cycle_ref"]
        or pending.get("previous_action") != "POSITION_SPECIFIC_TIME_EXIT"
        or not isinstance(reconciliation_digest, str)
        or not _is_digest(reconciliation_digest)
        or _parse_aware_datetime(pending.get("resolved_at_utc"))
        < _parse_aware_datetime(latest_attempt)
        or metadata.get("unknown_halt_latched") != "true"
    ):
        raise V4G037CommissioningNoPostError("G037_TERMINAL_STATE_UNVERIFIED")
    counts = (
        int(cycle["cycle_count"]),
        int(cycle["flat_count"] or 0),
        int(cycle["protected_count"] or 0),
        int(cycle["unresolved_count"] or 0),
    )
    if counts != (1, 1, 1, 0):
        raise V4G037CommissioningNoPostError("G037_CYCLE_STATE_MISMATCH")

    permit_path, permit = _load_single_marker(
        runtime_root, "activation-permit-issued.*.json"
    )
    binding_path, binding = _load_single_marker(
        runtime_root, "activation-runtime-bound.*.json"
    )
    preparation_root = preparation_state_root(
        repository=repository,
        reviewed_files_digest=origin_reviewed_files_digest,
        generation_manifest_digest=origin_generation_digest,
    )
    consumed_path, consumed = _load_single_marker(
        preparation_root, "generation_consumed.*.json"
    )
    cycle_ref = str(cycle["cycle_ref"])
    trading_day = str(cycle["trading_day_jst"])
    intent_digest = permit.get("intent_digest")
    if (
        permit.get("generation_digest") != origin_generation_digest
        or permit.get("status") != "ISSUED_ONE_USE_NOT_POSTED"
        or permit.get("cycle_ref") != cycle_ref
        or permit_path.name.split(".")[1] != cycle_ref
        or not isinstance(intent_digest, str)
        or not _is_digest(intent_digest)
        or binding.get("intent_digest") != intent_digest
        or binding.get("generation_digest") != origin_generation_digest
        or binding.get("status") != "RUNTIME_BOUND_POST_NOT_ATTEMPTED"
        or binding_path.name.split(".")[1] != cycle_ref
        or consumed.get("generation_digest") != origin_generation_digest
        or consumed.get("status") != "CONSUMED_FOR_CANARY_PREFLIGHT"
        or consumed.get("trading_day_jst") != trading_day
        or trading_day not in consumed_path.name
    ):
        raise V4G037CommissioningNoPostError("G037_MARKER_CONTENT_MISMATCH")

    return V4G037SuccessfulCanaryEvidenceNoPost(
        schema=G037_CANARY_EVIDENCE_SCHEMA,
        origin_reviewed_files_digest=origin_reviewed_files_digest,
        origin_generation_digest=origin_generation_digest,
        target_reviewed_files_digest=target_reviewed_files_digest,
        target_generation_digest=target_generation_digest,
        cycle_count=1,
        flat_cycle_count=1,
        protected_cycle_count=1,
        unresolved_cycle_count=0,
        entry_attempt_count=1,
        protection_attempt_count=1,
        risk_reducing_attempt_count=2,
        permit_marker_count=1,
        runtime_binding_marker_count=1,
        generation_consumed_marker_count=1,
        post_flat_halt_classification=G037_TERMINAL_FLAT_HALT,
        successful_canary_fixed=True,
        post_flat_halt_blocks_activation=True,
        _issuer_token=_EVIDENCE_ISSUER_TOKEN,
    )


def record_successful_canary_evidence_once_no_post(
    *,
    repository: Path,
    origin_reviewed_files_digest: str,
    origin_generation_digest: str,
    target_reviewed_files_digest: str,
    target_generation_digest: str,
    state_root: Path,
) -> tuple[Path, V4G037SuccessfulCanaryEvidenceNoPost]:
    """Reinspect, create once, and verify exact content after restart."""

    evidence = inspect_successful_canary_no_post(
        repository=repository,
        origin_reviewed_files_digest=origin_reviewed_files_digest,
        origin_generation_digest=origin_generation_digest,
        target_reviewed_files_digest=target_reviewed_files_digest,
        target_generation_digest=target_generation_digest,
    )
    _reject_symlink_ancestry(state_root, allow_missing=True)
    path = v4_unattended_g037_canary_evidence_path(
        state_root=state_root, generation_digest=evidence.target_generation_digest
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_ancestry(path.parent)
    payload = json.dumps(
        evidence.to_safe_dict(), sort_keys=True, separators=(",", ":")
    ) + "\n"
    if path.exists():
        if path.is_symlink() or path.read_text(encoding="utf-8") != payload:
            raise V4G037CommissioningNoPostError("G037_EXISTING_EVIDENCE_MISMATCH")
        return path, evidence
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except FileExistsError:
        raise V4G037CommissioningNoPostError(
            "G037_EVIDENCE_RACE_OR_UNKNOWN_RESULT"
        ) from None
    except OSError as error:
        raise V4G037CommissioningNoPostError(
            "G037_CANARY_EVIDENCE_WRITE_FAILED"
        ) from error
    return path, evidence


def verify_unattended_generation_binding_no_post(
    *,
    repository: Path,
    evidence: V4G037SuccessfulCanaryEvidenceNoPost,
    daily_authorization_path: Path,
    now_utc: datetime,
) -> V4G037UnattendedBindingNoPost:
    """Verify target-generation and daily gates while HALT remains blocking."""

    if (
        type(evidence) is not V4G037SuccessfulCanaryEvidenceNoPost
        or evidence._issuer_token is not _EVIDENCE_ISSUER_TOKEN
    ):
        raise V4G037CommissioningNoPostError("G037_BINDING_INPUT_INVALID")
    actual_reviewed = reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=actual_reviewed
    )
    binding_verified = (
        actual_reviewed == evidence.target_reviewed_files_digest
        and generation.digest == evidence.target_generation_digest
    )
    authorization = check_operator_daily_authorization(
        artifact_path=daily_authorization_path,
        expected_generation_digest=evidence.target_generation_digest,
        now_utc=now_utc,
    )
    reasons = [G037_HALT_RELEASE_REQUIRED]
    if not binding_verified:
        reasons.append("GENERATION_BINDING_MISMATCH")
    if not authorization.authorized or not authorization.consumption_available:
        reasons.append("DAILY_AUTHORIZATION_NOT_CLEAR")
        reasons.extend(authorization.blocked_reasons)
    return V4G037UnattendedBindingNoPost(
        generation_binding_verified=binding_verified,
        daily_authorization_clear=(
            authorization.authorized and authorization.consumption_available
        ),
        unattended_activation_eligible=False,
        blocked_reasons=tuple(dict.fromkeys(reasons)),
    )


def _load_single_marker(
    root: Path, pattern: str
) -> tuple[Path, dict[str, object]]:
    _reject_symlink_ancestry(root)
    markers = [
        path for path in root.glob(pattern) if path.is_file() and not path.is_symlink()
    ]
    if len(markers) != 1:
        raise V4G037CommissioningNoPostError("G037_MARKER_CARDINALITY_MISMATCH")
    try:
        return markers[0], _load_json_object(markers[0].read_text(encoding="utf-8"))
    except OSError as error:
        raise V4G037CommissioningNoPostError("G037_MARKER_READ_FAILED") from error


def _load_json_object(raw: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise V4G037CommissioningNoPostError("G037_JSON_INVALID") from error
    if not isinstance(value, dict):
        raise V4G037CommissioningNoPostError("G037_JSON_INVALID")
    return value


def _reject_symlink_ancestry(path: Path, *, allow_missing: bool = False) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise V4G037CommissioningNoPostError("G037_SYMLINK_ANCESTRY_REFUSED")
        if current == current.parent:
            break
        current = current.parent
    if not allow_missing and not path.is_dir():
        raise V4G037CommissioningNoPostError("G037_STATE_DIRECTORY_INVALID")


def _parse_aware_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise V4G037CommissioningNoPostError("G037_TIMESTAMP_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise V4G037CommissioningNoPostError("G037_TIMESTAMP_INVALID") from error
    if parsed.tzinfo is None:
        raise V4G037CommissioningNoPostError("G037_TIMESTAMP_INVALID")
    return parsed


def _is_digest(value: str) -> bool:
    return (
        value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _require_digest(value: object) -> None:
    if not isinstance(value, str) or not _is_digest(value):
        raise V4G037CommissioningNoPostError("G037_DIGEST_INVALID")
