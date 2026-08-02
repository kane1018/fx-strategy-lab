from pathlib import Path

from app.h11_auto import v4_gmo_generation
from h11_v4_reviewed_digest import compute_reviewed_files_digest


def test_g068_candidate_manifest_is_readable_by_canonical_loader(monkeypatch) -> None:
    backend = Path(__file__).resolve().parents[3]
    repository = backend.parent
    reviewed_digest = compute_reviewed_files_digest(repository=repository)
    monkeypatch.setattr(
        v4_gmo_generation,
        "V4_GMO_GENERATION_ARTIFACT",
        Path("docs/templates/h11_v4_g068_frozen_generation.json"),
    )
    generation = v4_gmo_generation.load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=reviewed_digest,
    )

    assert generation.generation_label == "H11_AUTO_30M_20260802_G068"
    assert generation.implementation_digest == reviewed_digest
    assert generation.actual_post_authorized is False
    assert generation.status == "UNATTENDED_LIVE_COMMISSIONED"
    assert generation.live_ready is True
    assert generation.unattended_live_supported is True
