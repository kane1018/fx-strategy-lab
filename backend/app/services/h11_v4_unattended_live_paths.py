"""Canonical generation-bound paths for the unattended live authorization track.

Mirrors ``app.h11_auto.v4_gmo_runtime_paths``' digest-validated state-root
pattern. Establishing one canonical path now -- used by both the operator's
artifact-creation CLI and, later, the wiring step that reads it -- resolves
part of the Phase 4 design's wiring obligation that the authorization
artifact path must never be caller-supplied at read time (see
``docs/H11_V4_UNATTENDED_LIVE_ADAPTER_DESIGN_20260724.md`` §9.2 item 2).
"""

from __future__ import annotations

from pathlib import Path

V4_UNATTENDED_LIVE_STATE_RELATIVE = Path("backend/market_data/h11_v4_unattended_live")
V4_UNATTENDED_LIVE_DAILY_AUTHORIZATION_FILENAME = "daily-authorization.json"


class V4UnattendedLivePathError(RuntimeError):
    """Fixed safe canonical-path failure."""


def v4_unattended_live_state_root(*, repository: Path, generation_digest: str) -> Path:
    normalized = _require_generation_digest(generation_digest)
    return (
        repository.resolve()
        / V4_UNATTENDED_LIVE_STATE_RELATIVE
        / f"generation-{normalized}"
    )


def v4_unattended_live_daily_authorization_path(
    *, repository: Path, generation_digest: str
) -> Path:
    return (
        v4_unattended_live_state_root(
            repository=repository, generation_digest=generation_digest
        )
        / V4_UNATTENDED_LIVE_DAILY_AUTHORIZATION_FILENAME
    )


def _require_generation_digest(value: str) -> str:
    if not isinstance(value, str):
        raise V4UnattendedLivePathError("V4_UNATTENDED_LIVE_GENERATION_DIGEST_INVALID")
    prefix = "sha256:"
    normalized = value.removeprefix(prefix)
    if (
        not value.startswith(prefix)
        or len(normalized) != 64
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise V4UnattendedLivePathError("V4_UNATTENDED_LIVE_GENERATION_DIGEST_INVALID")
    return normalized
