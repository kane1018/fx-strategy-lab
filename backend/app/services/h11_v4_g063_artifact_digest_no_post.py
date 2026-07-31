"""Canonical digest helpers for G063 no-POST artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any


class G063ArtifactDigestError(ValueError):
    """Safe artifact digest contract error."""


def canonical_digest_without_field(
    payload: dict[str, Any],
    *,
    digest_field: str,
) -> str:
    """Hash canonical JSON after removing the self-referential digest field."""

    if not isinstance(payload, dict) or not isinstance(digest_field, str):
        raise G063ArtifactDigestError("G063_ARTIFACT_DIGEST_INPUT_INVALID")
    if digest_field not in payload:
        raise G063ArtifactDigestError("G063_ARTIFACT_DIGEST_FIELD_MISSING")
    canonical_payload = dict(payload)
    del canonical_payload[digest_field]
    canonical = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()
