"""Stdlib-only G079 reviewed-source and generation digest.

G079 uses its own reviewed-file list so that adding the G079 candidate never
perturbs the shared ``h11_v4_reviewed_digest`` binding used by predecessor
generations.  The frozen-generation artifact is normalized by nulling the
self-referential binding fields before hashing (self-consistent digests).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

G079_GENERATION_ARTIFACT = "docs/templates/h11_v4_g079_frozen_generation.json"

G079_REVIEWED_FILES = (
    "backend/app/services/h11_v4_g079_runtime.py",
    "backend/app/services/h11_v4_g078_private_get_producer.py",
    "backend/app/tests/h11_auto/test_v4_g079_runtime_fake_only.py",
    "backend/app/tests/h11_auto/test_v4_g078_private_get_producer_fake_only.py",
    "backend/scripts/h11_auto_v4_g079_operation_60_no_post.py",
    "backend/scripts/h11_auto_v4_g079_initial_activation.py",
    "backend/h11_v4_g079_reviewed_digest.py",
    "docs/templates/h11_v4_g079_frozen_generation.json",
    "docs/H11_V4_G079_FINAL_COMMISSIONING_DESIGN.md",
    "AGENTS.md",
)

# Self-referential fields nulled before hashing the generation artifact.
_G079_BINDING_FIELDS = frozenset(
    {
        "artifact_digest",
        "generation_digest",
        "implementation_digest",
        "reviewed_files_digest",
        "runtime_commissioning_evidence_digest",
        "successor_halt_release_digest",
        "unknown_resolution_contract_digest",
    }
)

# Fields popped unconditionally from the generation canonical form (mirrors the
# G070-G076 generation digest convention).
_G079_GENERATION_POP_FIELDS = frozenset(
    {
        "runtime_commissioning_evidence_digest",
        "successor_halt_release_digest",
    }
)

# Fields popped from the generation canonical form when None.
_G079_GENERATION_POP_IF_NONE = frozenset(
    {
        "per_trade_confirmation_required",
        "arm_is_operating_intent",
        "arm_directly_authorizes_post",
        "entry_gate_separate_from_arm",
        "reconciliation_required_before_entry",
        "predecessor_authorization_reused",
        "predecessor_state_root_reused",
        "frozen_design_digest",
    }
)


class G079ReviewedDigestError(ValueError):
    """Fixed safe-label digest failure."""


def _canonical_hash(payload: dict[str, object]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _normalize_artifact(
    *,
    repository: Path,
    relative: str,
    binding_fields: frozenset[str],
) -> tuple[str, str]:
    path = repository.resolve() / relative
    if not path.is_file() or path.is_symlink():
        raise G079ReviewedDigestError("G079_REVIEWED_FILE_INVALID")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise G079ReviewedDigestError("G079_REVIEWED_ARTIFACT_INVALID") from error
    if not isinstance(payload, dict):
        raise G079ReviewedDigestError("G079_REVIEWED_ARTIFACT_INVALID")
    normalized = {k: v for k, v in payload.items() if k not in binding_fields}
    return relative, _canonical_hash(normalized)


def compute_g079_reviewed_files_digest(*, repository: Path) -> str:
    digest = hashlib.sha256()
    for relative in G079_REVIEWED_FILES:
        if relative == G079_GENERATION_ARTIFACT:
            path = repository.resolve() / relative
            if not path.is_file() or path.is_symlink():
                raise G079ReviewedDigestError("G079_REVIEWED_FILE_INVALID")
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise G079ReviewedDigestError(
                    "G079_GENERATION_ARTIFACT_INVALID"
                ) from error
            if not isinstance(payload, dict):
                raise G079ReviewedDigestError("G079_GENERATION_ARTIFACT_INVALID")
            normalized = {k: v for k, v in payload.items() if k not in _G079_BINDING_FIELDS}
            digest.update(relative.encode())
            digest.update(b"\0")
            digest.update(_canonical_hash(normalized).encode())
            continue
        path = repository.resolve() / relative
        if not path.is_file() or path.is_symlink():
            raise G079ReviewedDigestError("G079_REVIEWED_FILE_INVALID")
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _load_g079_generation_artifact(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise G079ReviewedDigestError("G079_GENERATION_ARTIFACT_INVALID")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise G079ReviewedDigestError("G079_GENERATION_ARTIFACT_INVALID") from error
    if not isinstance(payload, dict):
        raise G079ReviewedDigestError("G079_GENERATION_ARTIFACT_INVALID")
    return payload


def compute_g079_generation_digest(*, repository: Path) -> str:
    payload = _load_g079_generation_artifact(
        repository.resolve() / G079_GENERATION_ARTIFACT
    )
    canonical = dict(payload)
    for field in _G079_GENERATION_POP_FIELDS:
        canonical.pop(field, None)
    for field in _G079_GENERATION_POP_IF_NONE:
        if canonical.get(field) is None:
            canonical.pop(field, None)
    for field in _G079_BINDING_FIELDS:
        canonical.pop(field, None)
    return _canonical_hash(canonical)


__all__ = [
    "G079_GENERATION_ARTIFACT",
    "G079_REVIEWED_FILES",
    "G079ReviewedDigestError",
    "compute_g079_generation_digest",
    "compute_g079_reviewed_files_digest",
]
