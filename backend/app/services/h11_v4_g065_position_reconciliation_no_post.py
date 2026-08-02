"""Generation-bound local position evidence for G065.

This bridge accepts only sanitized local evidence written by the reviewed
runtime after its own reconciliation. Missing, stale, malformed, or
generation-mismatched evidence never proves ownership, quantity, or
protection.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class G065PositionEvidenceError(RuntimeError):
    """Safe failure for the generation-bound local evidence contract."""


@dataclass(frozen=True)
class G065PositionReconciliationEvidence:
    position_open: bool
    protection_confirmed: bool
    ownership_exact: bool
    quantity_matches: bool
    generation_bound: bool
    evidence_available: bool = False
    evidence_fresh: bool = False

    def __bool__(self) -> bool:
        return False


def _unknown() -> G065PositionReconciliationEvidence:
    return G065PositionReconciliationEvidence(False, False, False, False, False, False, False)


def load_g065_position_reconciliation_no_post(
    *,
    state_root: Path,
    generation_digest: str,
    now_utc: datetime | None = None,
    maximum_age_seconds: int = 60,
) -> G065PositionReconciliationEvidence:
    if type(maximum_age_seconds) is not int or maximum_age_seconds <= 0:
        raise G065PositionEvidenceError("G065_POSITION_EVIDENCE_AGE_INVALID")
    path = state_root / "position-reconciliation.json"
    if path.is_symlink() or not path.is_file():
        return _unknown()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _unknown()
    fields = (
        "position_open",
        "protection_confirmed",
        "ownership_exact",
        "quantity_matches",
        "generation_bound",
    )
    observed_raw = payload.get("observed_at_utc") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != "H11_V4_G065_POSITION_RECONCILIATION_V1"
        or payload.get("generation_digest") != generation_digest
        or payload.get("broker_post_count") != 0
        or not isinstance(observed_raw, str)
        or any(type(payload.get(field)) is not bool for field in fields)
    ):
        return _unknown()
    try:
        observed_at = datetime.fromisoformat(observed_raw).astimezone(UTC)
    except ValueError:
        return _unknown()
    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    age = (now - observed_at).total_seconds()
    if age < 0 or age > maximum_age_seconds:
        return _unknown()
    return G065PositionReconciliationEvidence(
        position_open=payload["position_open"],
        protection_confirmed=payload["protection_confirmed"],
        ownership_exact=payload["ownership_exact"],
        quantity_matches=payload["quantity_matches"],
        generation_bound=payload["generation_bound"],
        evidence_available=True,
        evidence_fresh=True,
    )


def write_g065_position_reconciliation_no_post(
    *,
    state_root: Path,
    generation_digest: str,
    position_open: bool,
    protection_confirmed: bool,
    ownership_exact: bool,
    quantity_matches: bool,
    generation_bound: bool,
    observed_at_utc: datetime,
) -> None:
    values: tuple[object, ...] = (
        position_open,
        protection_confirmed,
        ownership_exact,
        quantity_matches,
        generation_bound,
    )
    if (
        type(generation_digest) is not str
        or len(generation_digest) != 71
        or not generation_digest.startswith("sha256:")
        or any(type(value) is not bool for value in values)
        or observed_at_utc.tzinfo is None
    ):
        raise G065PositionEvidenceError("G065_POSITION_EVIDENCE_INPUT_INVALID")
    state_root.mkdir(parents=True, exist_ok=True)
    target = state_root / "position-reconciliation.json"
    temporary = state_root / "position-reconciliation.json.tmp"
    payload: dict[str, Any] = {
        "generation_digest": generation_digest,
        "observed_at_utc": observed_at_utc.astimezone(UTC).isoformat(),
        "position_open": position_open,
        "protection_confirmed": protection_confirmed,
        "ownership_exact": ownership_exact,
        "quantity_matches": quantity_matches,
        "generation_bound": generation_bound,
        "schema": "H11_V4_G065_POSITION_RECONCILIATION_V1",
        "broker_post_count": 0,
    }
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise G065PositionEvidenceError("G065_POSITION_EVIDENCE_WRITE_FAILED") from error
