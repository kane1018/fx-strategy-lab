from app.services.h11_v4_g063_artifact_digest_no_post import (
    canonical_digest_without_field,
)


def test_digest_contract_excludes_only_the_declared_self_field() -> None:
    payload = {"artifact_digest": "", "generation_digest": "sha256:g", "safe": True}
    first = canonical_digest_without_field(payload, digest_field="artifact_digest")
    payload["artifact_digest"] = first
    assert canonical_digest_without_field(
        payload,
        digest_field="artifact_digest",
    ) == first


def test_generation_digest_contract_is_independent_of_self_value() -> None:
    payload = {"generation_digest": "", "generation_label": "G063"}
    expected = canonical_digest_without_field(
        payload,
        digest_field="generation_digest",
    )
    payload["generation_digest"] = "sha256:" + "f" * 64
    assert canonical_digest_without_field(
        payload,
        digest_field="generation_digest",
    ) == expected
