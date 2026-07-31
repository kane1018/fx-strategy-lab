"""Generation-bound local position evidence for G063.

This module consumes only an explicitly written, sanitized local evidence file.
It never reads credentials, contacts a broker, or authorizes a broker write.
Missing or malformed evidence is conservative and never proves protection.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class G063PositionEvidenceError(RuntimeError):
    """Safe failure for the local reconciliation contract."""


@dataclass(frozen=True)
class G063PositionReconciliationEvidence:
    position_open: bool
    protection_confirmed: bool
    ownership_exact: bool
    quantity_matches: bool
    generation_bound: bool

    def __bool__(self) -> bool:
        return False


def load_g063_position_reconciliation_no_post(
    *,
    state_root: Path,
    generation_digest: str,
    now_utc: datetime | None = None,
    maximum_age_seconds: int = 60,
) -> G063PositionReconciliationEvidence:
    """Load only sanitized, generation-bound local position evidence."""

    if type(maximum_age_seconds) is not int or maximum_age_seconds <= 0:
        raise G063PositionEvidenceError("G063_POSITION_EVIDENCE_AGE_INVALID")
    path = state_root / "position-reconciliation.json"
    if path.is_symlink() or not path.is_file():
        return G063PositionReconciliationEvidence(False, False, False, False, False)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return G063PositionReconciliationEvidence(False, False, False, False, False)
    fields = (
        "position_open",
        "protection_confirmed",
        "ownership_exact",
        "quantity_matches",
        "generation_bound",
    )
    observed_raw = payload.get("observed_at_utc")
    if (
        not isinstance(payload, dict)
        or payload.get("generation_digest") != generation_digest
        or not isinstance(observed_raw, str)
        or any(type(payload.get(field)) is not bool for field in fields)
    ):
        return G063PositionReconciliationEvidence(False, False, False, False, False)
    try:
        observed_at = datetime.fromisoformat(observed_raw).astimezone(UTC)
    except ValueError:
        return G063PositionReconciliationEvidence(False, False, False, False, False)
    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    age = (now - observed_at).total_seconds()
    if age < 0 or age > maximum_age_seconds:
        return G063PositionReconciliationEvidence(False, False, False, False, False)
    return G063PositionReconciliationEvidence(
        position_open=payload["position_open"],
        protection_confirmed=payload["protection_confirmed"],
        ownership_exact=payload["ownership_exact"],
        quantity_matches=payload["quantity_matches"],
        generation_bound=payload["generation_bound"],
    )


def write_g063_position_reconciliation_no_post(
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
    """Atomically write only sanitized local synthetic evidence."""

    values: tuple[object, ...] = (
        generation_digest,
        position_open,
        protection_confirmed,
        ownership_exact,
        quantity_matches,
        generation_bound,
    )
    if not isinstance(generation_digest, str) or any(
        type(value) is not bool for value in values[1:]
    ):
        raise G063PositionEvidenceError("G063_POSITION_EVIDENCE_INPUT_INVALID")
    if observed_at_utc.tzinfo is None:
        raise G063PositionEvidenceError("G063_POSITION_EVIDENCE_TIME_INVALID")
    payload: dict[str, Any] = {
        "generation_digest": generation_digest,
        "observed_at_utc": observed_at_utc.astimezone(UTC).isoformat(),
        "position_open": position_open,
        "protection_confirmed": protection_confirmed,
        "ownership_exact": ownership_exact,
        "quantity_matches": quantity_matches,
        "generation_bound": generation_bound,
    }
    state_root.mkdir(parents=True, exist_ok=True)
    temporary = state_root / "position-reconciliation.json.tmp"
    target = state_root / "position-reconciliation.json"
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
        raise G063PositionEvidenceError("G063_POSITION_EVIDENCE_WRITE_FAILED") from error
