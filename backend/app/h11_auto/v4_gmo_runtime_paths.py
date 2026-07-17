"""Canonical generation-bound local paths shared by v4 runtime components."""

from __future__ import annotations

from pathlib import Path

V4_GMO_RUNTIME_STATE_RELATIVE = Path(
    "backend/market_data/h11_v4_gmo_actual_runtime"
)


class V4GmoRuntimePathError(RuntimeError):
    """Fixed safe canonical-path failure."""


def v4_gmo_runtime_state_root(
    *, repository: Path, generation_digest: str
) -> Path:
    prefix = "sha256:"
    normalized = generation_digest.removeprefix(prefix)
    if (
        not generation_digest.startswith(prefix)
        or len(normalized) != 64
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise V4GmoRuntimePathError("V4_RUNTIME_GENERATION_DIGEST_INVALID")
    return (
        repository.resolve()
        / V4_GMO_RUNTIME_STATE_RELATIVE
        / f"generation-{normalized}"
    )
