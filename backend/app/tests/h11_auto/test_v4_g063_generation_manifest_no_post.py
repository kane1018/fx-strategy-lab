from pathlib import Path

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from h11_v4_reviewed_digest import compute_reviewed_files_digest


def test_g063_manifest_is_readable_by_canonical_loader() -> None:
    backend = Path(__file__).resolve().parents[3]
    repository = backend.parent
    reviewed_digest = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=reviewed_digest,
    )

    assert generation.generation_label == "H11_AUTO_30M_20260731_G063"
    assert generation.implementation_digest == reviewed_digest
    assert generation.actual_post_authorized is False
    assert generation.live_ready is False
    assert generation.unattended_live_supported is False
