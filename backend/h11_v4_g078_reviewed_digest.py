"""Stdlib-only G078 reviewed-source and generation digest.

G078 uses its own reviewed-file list so that adding the G078 candidate never
perturbs the shared ``h11_v4_reviewed_digest`` binding used by predecessor
generations.  The frozen-generation artifact is normalized by nulling the
self-referential binding fields before hashing (self-consistent digests).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

G078_GENERATION_ARTIFACT = "docs/templates/h11_v4_g078_frozen_generation.json"

G078_REVIEWED_FILES = (
    "backend/app/services/h11_v4_g078_runtime.py",
    "backend/app/tests/h11_auto/test_v4_g078_unknown_resolution_fake_only.py",
    "backend/h11_v4_g078_reviewed_digest.py",
    "docs/templates/h11_v4_g078_frozen_generation.json",
    "docs/H11_V4_G078_CORRECTIVE_FIXES_DESIGN.md",
    "AGENTS.md",
)

# Self-referential fields nulled before hashing the generation artifact.
_G078_BINDING_FIELDS = frozenset(
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
_G078_GENERATION_POP_FIELDS = frozenset(
    {
        "runtime_commissioning_evidence_digest",
        "successor_halt_release_digest",
        "unknown_resolution_contract_digest",
    }
)

# Nullable binding fields popped from the generation canonical form when None
# (mirrors the shared V4GmoFrozenGeneration.canonical_json convention).
_G078_GENERATION_POP_IF_NONE = frozenset(
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


class G078ReviewedDigestError(RuntimeError):
    """Safe-label-only G078 digest failure."""


def _g078_normalize_artifact(payload: dict[str, object]) -> dict[str, object]:
    normalized = dict(payload)
    for field_name in _G078_BINDING_FIELDS:
        if field_name in normalized:
            normalized[field_name] = None
    return normalized


def _g078_canonical_generation(payload: dict[str, object]) -> str:
    canonical = dict(payload)
    for field_name in _G078_GENERATION_POP_IF_NONE:
        if canonical.get(field_name) is None:
            canonical.pop(field_name, None)
    for field_name in _G078_GENERATION_POP_FIELDS:
        canonical.pop(field_name, None)
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"))


def compute_g078_reviewed_files_digest(*, repository: Path) -> str:
    """Digest of the G078 reviewed files with artifact binding fields nulled."""
    digest = hashlib.sha256()
    root = repository.resolve()
    for relative in G078_REVIEWED_FILES:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise G078ReviewedDigestError("G078_REVIEWED_FILE_INVALID")
        digest.update(relative.encode())
        digest.update(b"\0")
        content = path.read_bytes()
        if relative == G078_GENERATION_ARTIFACT:
            try:
                payload = json.loads(content)
                if not isinstance(payload, dict):
                    raise TypeError
                content = json.dumps(
                    _g078_normalize_artifact(payload),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            except (json.JSONDecodeError, TypeError) as error:
                raise G078ReviewedDigestError("G078_REVIEWED_ARTIFACT_INVALID") from error
        digest.update(content)
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def compute_g078_generation_digest(*, repository: Path) -> str:
    """Generation digest of the G078 frozen artifact (self-consistent)."""
    path = repository.resolve() / G078_GENERATION_ARTIFACT
    if not path.is_file() or path.is_symlink():
        raise G078ReviewedDigestError("G078_GENERATION_ARTIFACT_INVALID")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G078ReviewedDigestError("G078_GENERATION_ARTIFACT_INVALID") from error
    if not isinstance(payload, dict):
        raise G078ReviewedDigestError("G078_GENERATION_ARTIFACT_INVALID")
    canonical = _g078_canonical_generation(payload)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


__all__ = [
    "G078ReviewedDigestError",
    "G078_GENERATION_ARTIFACT",
    "G078_REVIEWED_FILES",
    "compute_g078_generation_digest",
    "compute_g078_reviewed_files_digest",
]
