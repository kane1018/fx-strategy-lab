from pathlib import Path

from app.h11_auto import v4_gmo_generation


def test_g071_candidate_manifest_is_readable_by_canonical_loader(monkeypatch) -> None:
    backend = Path(__file__).resolve().parents[3]
    repository = backend.parent
    reviewed_digest = "sha256:dbaded053e108ab7f0041bf8169d536c76d362bbdcbf63d567e65adc9e9be7a4"
    monkeypatch.setattr(
        v4_gmo_generation,
        "V4_GMO_GENERATION_ARTIFACT",
        Path("docs/templates/h11_v4_g071_frozen_generation.json"),
    )
    generation = v4_gmo_generation.load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=reviewed_digest,
    )

    assert generation.generation_label == "H11_AUTO_30M_20260802_G071"
    assert generation.implementation_digest == reviewed_digest
    assert generation.actual_post_authorized is False
    assert generation.status == "UNATTENDED_RUNTIME_REVIEWED_AWAITING_COMMISSIONING"
    assert generation.live_ready is False
    assert generation.unattended_live_supported is False
