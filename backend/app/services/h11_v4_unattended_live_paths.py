"""Canonical generation-bound paths for the unattended live authorization track.

Mirrors ``app.h11_auto.v4_gmo_runtime_paths``' digest-validated state-root
pattern, with one deliberate difference: the default root is **not** derived
from the repository checkout location. This project's repository lives under
``~/Desktop``, and a read-only check on the development machine confirmed
iCloud Desktop & Documents sync is active there (``com.apple.bird``/
``com.apple.cloudd`` running, ``FXICloudDriveDesktop`` preference set) --
exactly the condition
``docs/H11_V4_UNATTENDED_LIVE_ADAPTER_DESIGN_20260724.md`` §9.2 item 2 warned
about: O_EXCL atomicity is not dependable on synced filesystems, and a sync
conflict/restore could delete or resurrect a one-use marker.

``~/Library/Application Support`` is never touched by iCloud Desktop &
Documents sync (that feature only syncs ``~/Desktop`` and ``~/Documents``),
so it is used as the default root instead. The root remains fully overridable
(tests and any future caller may pass an explicit ``state_root``) --
established as an idiomatic default, not hardcoded without an escape hatch.
"""

from __future__ import annotations

from pathlib import Path

V4_UNATTENDED_LIVE_STATE_RELATIVE = Path("h11_v4_unattended_live")
V4_UNATTENDED_LIVE_DAILY_AUTHORIZATION_FILENAME = "daily-authorization.json"
DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT = (
    Path.home() / "Library" / "Application Support" / "fx-strategy-lab-h11-v4-unattended-live"
)


class V4UnattendedLivePathError(RuntimeError):
    """Fixed safe canonical-path failure."""


def v4_unattended_live_state_root(
    *, state_root: Path = DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT, generation_digest: str
) -> Path:
    normalized = _require_generation_digest(generation_digest)
    return (
        state_root.resolve()
        / V4_UNATTENDED_LIVE_STATE_RELATIVE
        / f"generation-{normalized}"
    )


def v4_unattended_live_daily_authorization_path(
    *, state_root: Path = DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT, generation_digest: str
) -> Path:
    return (
        v4_unattended_live_state_root(
            state_root=state_root, generation_digest=generation_digest
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
