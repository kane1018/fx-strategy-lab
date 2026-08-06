"""Operator-only HALT discharge: rename-archive, never delete.

A persistent halt is a one-way latch; discharging it is an operator decision
with recorded provenance.  This module is deliberately NOT imported by any
runtime path (see the AST guard in test_v4_c2_halt_discharge_no_post.py): it
exists only for the operator-facing script.

Rules enforced here:
- rename-only: the halt file is moved to a ``*-halt-discharged.<UTC>.json``
  archive that does NOT match the runtime scan glob ``g0*-persistent-halt.json``
- the original halt JSON is preserved verbatim under the ``original`` key and
  the operator resolution is recorded alongside it
- exactly one explicit file per call; no glob, no bulk discharge
- the resolution must carry the sha256 of the halt content actually on disk,
  so a discharge cannot be applied to the wrong file or without reading it
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root

V4_HALT_DISCHARGE_REQUIRED_RESOLUTION_KEYS = (
    "operator",
    "reason",
    "broker_state_confirmation",
    "halt_content_sha256",
)
_HALT_FILE_NAME = re.compile(r"^g[0-9]{3}-persistent-halt\.json$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class V4HaltDischargeError(ValueError):
    """Safe-label-only HALT discharge failure."""


def halt_content_sha256(payload: Mapping[str, object]) -> str:
    """Canonical sha256 of a halt marker payload (identical hashing to the
    runtime's ``_canonical_hash`` so a discharge reference is unambiguous)."""

    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def discharge_halt(
    *,
    repository: Path,
    generation_digest: str,
    halt_file_name: str,
    resolution: Mapping[str, str],
    now_utc: datetime,
) -> Path:
    """Rename-archive one explicit halt file and record the operator resolution.

    Returns the archive path.  Raises ``V4HaltDischargeError`` with a fixed
    safe label on any invalid input; the halt file is left untouched in every
    failure path.
    """

    if now_utc.tzinfo is None:
        raise V4HaltDischargeError("V4_HALT_DISCHARGE_CLOCK_INVALID")
    if (
        not isinstance(halt_file_name, str)
        or _HALT_FILE_NAME.fullmatch(halt_file_name) is None
    ):
        raise V4HaltDischargeError("V4_HALT_DISCHARGE_TARGET_INVALID")
    for key in V4_HALT_DISCHARGE_REQUIRED_RESOLUTION_KEYS:
        value = resolution.get(key)
        if not isinstance(value, str) or not value.strip():
            raise V4HaltDischargeError("V4_HALT_DISCHARGE_RESOLUTION_INCOMPLETE")

    halt_path = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation_digest
    ) / halt_file_name
    if halt_path.is_symlink() or not halt_path.is_file():
        raise V4HaltDischargeError("V4_HALT_DISCHARGE_TARGET_MISSING")
    try:
        original = json.loads(halt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4HaltDischargeError("V4_HALT_DISCHARGE_TARGET_INVALID") from error
    if not isinstance(original, dict):
        raise V4HaltDischargeError("V4_HALT_DISCHARGE_TARGET_INVALID")

    actual = halt_content_sha256(original)
    confirmed = resolution["halt_content_sha256"]
    if not _DIGEST.fullmatch(confirmed) or confirmed != actual:
        raise V4HaltDischargeError("V4_HALT_DISCHARGE_SHA256_MISMATCH")

    archive_path = halt_path.with_name(
        halt_file_name.replace(
            "-persistent-halt.json",
            "-halt-discharged." + now_utc.strftime("%Y%m%dT%H%M%SZ") + ".json",
        )
    )
    if archive_path.exists() or archive_path.is_symlink():
        raise V4HaltDischargeError("V4_HALT_DISCHARGE_ARCHIVE_EXISTS_NO_RETRY")

    os.replace(halt_path, archive_path)
    payload = {
        "schema": "H11_V4_HALT_DISCHARGE_ARCHIVE_V1",
        "original": original,
        "resolution": {key: resolution[key] for key in V4_HALT_DISCHARGE_REQUIRED_RESOLUTION_KEYS},
        "discharged_at_utc": now_utc.astimezone(UTC).isoformat(),
        "archive_sha256": halt_content_sha256(
            {
                "original": original,
                "resolution": {
                    key: resolution[key]
                    for key in V4_HALT_DISCHARGE_REQUIRED_RESOLUTION_KEYS
                },
                "discharged_at_utc": now_utc.astimezone(UTC).isoformat(),
            }
        ),
    }
    archive_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8"
    )
    return archive_path
