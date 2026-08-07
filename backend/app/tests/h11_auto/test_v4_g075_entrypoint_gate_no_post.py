"""Acceptance tests for the G075 stabilization VETO fixes.

Written BEFORE the implementation, by the reviewer, not the implementer.
Fake-only: no broker access, no credentials, no LaunchAgent interaction,
no notification, no network.

Why this file exists
--------------------
The first stabilization pass shipped 12 acceptance tests that were all
source-string scans and JSON field comparisons. Every one of them passed
while G075's three real entry points were still dead, because none of them
ever CALLED an entry gate. An independent review caught it:
``verify_g075_review_artifacts`` raised
``G075_REVIEW_ARTIFACT_BINDING_MISMATCH`` because the two G075 review
artifacts still carried the pre-rebake digests, so the LaunchAgent
bootstrap, operation 60 and initial activation all still aborted -- the
failure had merely been renamed from ``implementation digest mismatch``.

So the rule for this file: **actually invoke the gate.** A test that only
greps for a string cannot tell whether the release works.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.services.h11_v4_g075_runtime import (
    G075_GENERATION_LABEL,
    G075Error,
    verify_g075_review_artifacts,
)
from h11_v4_reviewed_digest import REVIEWED_FILES, compute_reviewed_files_digest

REPOSITORY = Path(__file__).resolve().parents[4]
BACKEND = REPOSITORY / "backend"
TEMPLATES = REPOSITORY / "docs/templates"

DEAD_GENERATIONS = (
    "g066",
    "g067",
    "g068",
    "g069",
    "g070",
    "g071",
    "g072",
    "g073",
    "g074",
    "g076",
    "g077",
    "g078",
    "g079",
)


def _canonical_digests() -> tuple[str, str]:
    reviewed = compute_reviewed_files_digest(repository=REPOSITORY)
    generation = load_v4_gmo_frozen_generation(
        repository=REPOSITORY, implementation_digest=reviewed
    )
    return reviewed, generation.digest


# ------------------------- the gate reflects the latest independent review
#
# 2026-08-07、Phase E〜H に対する独立3レーンレビューが3ラウンドを経て
# 全レーン CLEAR を確定し、operator の指示で binding フィールドのみ再束縛した。
# この時点の証跡は現行コード状態を参照するため、ゲートは PASS 側にある。
# code が再変更され digest が一致しなくなれば、ゲートは再拒否へ戻る。


def test_g075_review_artifact_gate_passes_after_independent_review() -> None:
    """2026-08-07 時点で、独立3レーンレビュー(CLEAR)反映の束縛を検証する。

    3レーンが CLEAR を確定し、operator の指示で reviewed/reviewed-only
    6フィールド再束縛を経た後、現行 artifacts は現行 digest を受理する状態である。
    したがってゲートは PASS し、環境による偶発的な 2点差分はない。
    """
    reviewed, generation = _canonical_digests()
    verify_g075_review_artifacts(
        repository=REPOSITORY,
        generation_digest=generation,
        reviewed_files_digest=reviewed,
    )


def test_review_artifacts_still_bind_the_last_reviewed_digest() -> None:
    """The artifacts must keep pointing at the last reviewed digest.

    2026-08-07 の再束縛対象は reviewed/reviewed-only 6 フィールドのみで、
    レビュー済み証跡は当該 digest に一致し続ける必要がある。
    なお、working tree 変更時には再レビュー後の再束縛が必要。
    """
    reviewed, _generation = _canonical_digests()
    for name in (
        "h11_v4_g075_runtime_commissioning_evidence.json",
        "h11_v4_g075_independent_review_attestation.json",
    ):
        payload = json.loads((TEMPLATES / name).read_text(encoding="utf-8"))
        assert payload["reviewed_files_digest"] == reviewed, (
            f"{name} must bind the latest independently reviewed digest"
        )
        assert re.fullmatch(
            r"sha256:[0-9a-f]{64}", payload["reviewed_files_digest"]
        ), name


def test_attestation_still_asserts_no_external_human_signoff() -> None:
    attestation = json.loads(
        (TEMPLATES / "h11_v4_g075_independent_review_attestation.json").read_text(
            encoding="utf-8"
        )
    )
    assert attestation["external_human_signoff_verified"] is False


def test_rebake_did_not_authorize_anything() -> None:
    """Re-baking digests must never flip a capability flag."""

    evidence = json.loads(
        (TEMPLATES / "h11_v4_g075_runtime_commissioning_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["broker_write"] is False
    assert evidence["actual_post_authorized"] is False
    assert evidence["broker_post_authorized"] is False
    for counter in (
        "broker_get_count",
        "broker_post_count",
        "private_api_read_count",
        "credential_read_count",
        "notification_attempt_count",
        "arm_mutation_count",
        "launchagent_mutation_count",
    ):
        assert evidence[counter] == 0, counter

    manifest = json.loads(
        (TEMPLATES / "h11_v4_g075_frozen_generation.json").read_text(encoding="utf-8")
    )
    assert manifest["actual_post_authorized"] is False
    assert manifest["live_ready"] is False
    assert manifest["unattended_live_supported"] is False


def test_gate_still_rejects_a_tampered_artifact(tmp_path: Path) -> None:
    """The gate must not have been loosened to make the release pass."""

    reviewed, generation = _canonical_digests()
    staged = tmp_path / "docs/templates"
    staged.mkdir(parents=True)
    for name in (
        "h11_v4_g075_frozen_generation.json",
        "h11_v4_g075_runtime_commissioning_evidence.json",
        "h11_v4_g075_independent_review_attestation.json",
    ):
        (staged / name).write_text(
            (TEMPLATES / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    evidence_path = staged / "h11_v4_g075_runtime_commissioning_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["safety_review_clear"] = False
    evidence_path.write_text(json.dumps(evidence, sort_keys=True), encoding="utf-8")
    with pytest.raises(G075Error):
        verify_g075_review_artifacts(
            repository=tmp_path,
            generation_digest=generation,
            reviewed_files_digest=reviewed,
        )


def test_canonical_manifest_is_g075_and_matches_the_template() -> None:
    canonical = json.loads(
        (TEMPLATES / "h11_v4_gmo_frozen_generation.json").read_text(encoding="utf-8")
    )
    template = json.loads(
        (TEMPLATES / "h11_v4_g075_frozen_generation.json").read_text(encoding="utf-8")
    )
    assert canonical["generation_label"] == G075_GENERATION_LABEL
    assert canonical == template


# --------------------------------- P1-2: no surviving alternate digest algo


def test_no_alternate_reviewed_digest_module_survives_anywhere_in_backend() -> None:
    """The first pass only globbed ``app/services``; three modules sat in
    ``backend/`` itself and were missed."""

    offenders = [
        path.relative_to(BACKEND).as_posix()
        for path in BACKEND.rglob("*.py")
        if "__pycache__" not in path.parts
        and re.search(r"def compute_g\d+_reviewed_files_digest", path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_no_dead_generation_digest_modules_remain() -> None:
    offenders = [
        path.name
        for path in BACKEND.glob("h11_v4_g*_reviewed_digest.py")
        if any(dead in path.name for dead in DEAD_GENERATIONS)
    ]
    assert offenders == []


def test_reviewed_files_has_no_dead_generation_entries_case_insensitive() -> None:
    """The first pass matched only lowercase ``_g07x_`` and let uppercase
    design-document paths through."""

    pattern = re.compile(rf"[_/]({'|'.join(DEAD_GENERATIONS)})[_.]", re.IGNORECASE)
    offenders = [relative for relative in REVIEWED_FILES if pattern.search(relative)]
    assert offenders == []


def test_every_reviewed_file_still_exists() -> None:
    missing = [r for r in REVIEWED_FILES if not (REPOSITORY / r).is_file()]
    assert missing == []


def test_digest_remains_a_fixed_point() -> None:
    reviewed, _ = _canonical_digests()
    canonical = json.loads(
        (TEMPLATES / "h11_v4_gmo_frozen_generation.json").read_text(encoding="utf-8")
    )
    template = json.loads(
        (TEMPLATES / "h11_v4_g075_frozen_generation.json").read_text(encoding="utf-8")
    )
    assert canonical["implementation_digest"] == reviewed
    assert template["implementation_digest"] == reviewed


# ------------------------- P1-3: restored coverage for surviving modules


def test_monday_self_check_has_no_external_trading_entrypoint() -> None:
    """Restored from the deleted G076 test file: the offline self-check must
    never invoke a broker/credential/transport entry point. This guarded a
    SURVIVING script and its loss was real coverage loss."""

    source = (BACKEND / "scripts/h11_auto_v4_monday_self_check.py").read_text(
        encoding="utf-8"
    )
    commands = re.findall(r"\"([^\"]*\.py)\"", source) + re.findall(
        r"'([^']*\.py)'", source
    )
    forbidden = ("broker", "keychain", "transport", "private_get", "order", "credential")
    offenders = [
        command
        for command in commands
        for token in forbidden
        if token in command.lower()
    ]
    assert offenders == []


def test_unattended_control_api_never_imports_broker_write_code() -> None:
    """Restored intent from the deleted control-API test file: the manual UI
    control plane must stay free of broker-write capability."""

    source = (BACKEND / "app/h11_manual/unattended_control_api.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "h11_v4_gmo_actual_transport",
        "assert_real_broker_post_allowed",
        "V4GmoHttpxPrivateTransport",
        "issue_v4_gmo_actual_activation_permit",
    ):
        assert forbidden not in source, forbidden


def test_public_readonly_app_does_not_expose_control_routes() -> None:
    source = (BACKEND / "app/main_readonly.py").read_text(encoding="utf-8")
    assert "unattended_control_api" not in source
    assert "h11_auto" not in source
