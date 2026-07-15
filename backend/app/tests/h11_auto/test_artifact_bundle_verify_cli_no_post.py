from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

import scripts.h11_auto_artifact_bundle_verify as bundle_module
from app.tests.h11_auto.test_generation_manifest_cli_no_post import _frozen_manifest
from app.tests.h11_auto.test_profile_freeze_cli_no_post import (
    _accepted_evidence,
    _frozen_profile,
)
from scripts.h11_auto_artifact_bundle_verify import (
    ArtifactBundleError,
    main,
    verify_frozen_bundle,
)
from scripts.h11_auto_profile_acceptance import Capability
from scripts.h11_auto_profile_freeze import validate_and_bind_profile


def _coherent_bundle(
    *, immediate: bool = False
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    evidence = _accepted_evidence(immediate=immediate)
    profile = _frozen_profile(evidence, immediate=immediate)
    _, profile_digest, _ = validate_and_bind_profile(
        profile, evidence, mode="frozen"
    )
    manifest = _frozen_manifest()
    manifest["entry"]["execution_profile_label"] = profile["profile_label"]  # type: ignore[index]
    manifest["entry"]["execution_profile_hash"] = profile_digest  # type: ignore[index]
    manifest["entry"]["entry_style"] = (  # type: ignore[index]
        "IMMEDIATE_ENTRY" if immediate else "PENDING_ENTRY"
    )
    return manifest, profile, evidence


@pytest.mark.parametrize("immediate", [False, True])
def test_coherent_bundle_verifies_without_authority(immediate: bool) -> None:
    result = verify_frozen_bundle(*_coherent_bundle(immediate=immediate))
    safe = result.to_safe_dict()
    assert safe["verification_status"] == "BUNDLE_COHERENT_NOT_ACTIVATED"
    assert safe["actual_adapter_authorized"] is False
    assert safe["broker_read_authorized"] is False
    assert safe["broker_write_authorized"] is False
    assert safe["credential_read_authorized"] is False
    assert safe["actual_post_authorized"] is False
    assert safe["live_ready"] is False
    assert safe["unattended_live_supported"] is False


def test_bundle_digest_is_deterministic_and_generation_bound() -> None:
    manifest, profile, evidence = _coherent_bundle()
    first = verify_frozen_bundle(manifest, profile, evidence).bundle_digest
    second = verify_frozen_bundle(
        copy.deepcopy(manifest), copy.deepcopy(profile), copy.deepcopy(evidence)
    ).bundle_digest
    manifest["identity"]["generation_label"] = "H11_AUTO_30M_20260715_G002"  # type: ignore[index]
    changed = verify_frozen_bundle(manifest, profile, evidence).bundle_digest
    assert first == second
    assert changed != first


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("execution_profile_label", "OTHER_PROFILE", "labels do not match"),
        ("execution_profile_hash", "sha256:" + "f" * 64, "digests do not match"),
        ("entry_style", "IMMEDIATE_ENTRY", "entry modes do not match"),
    ],
)
def test_cross_artifact_mismatch_is_blocked(
    field: str, value: str, message: str
) -> None:
    manifest, profile, evidence = _coherent_bundle()
    manifest["entry"][field] = value  # type: ignore[index]
    with pytest.raises(ArtifactBundleError, match=message):
        verify_frozen_bundle(manifest, profile, evidence)


def test_ownership_contract_mismatch_is_blocked() -> None:
    manifest, profile, evidence = _coherent_bundle()
    profile["ownership_contract"] = "OFFICIAL_UNIQUE_OWNERSHIP"
    _, digest, _ = validate_and_bind_profile(profile, evidence, mode="frozen")
    manifest["entry"]["execution_profile_hash"] = digest  # type: ignore[index]
    with pytest.raises(ArtifactBundleError, match="ownership"):
        verify_frozen_bundle(manifest, profile, evidence)


def test_unaccepted_evidence_is_blocked_as_invalid_artifact() -> None:
    manifest, profile, evidence = _coherent_bundle()
    evidence["capabilities"]["server_side_stop_loss"] = (  # type: ignore[index]
        Capability.NOT_ANSWERED.value
    )
    with pytest.raises(ArtifactBundleError, match="artifacts are invalid"):
        verify_frozen_bundle(manifest, profile, evidence)


def test_unknown_sensitive_field_is_not_echoed() -> None:
    manifest, profile, evidence = _coherent_bundle()
    manifest["raw_secret"] = "DO_NOT_ECHO"
    with pytest.raises(ArtifactBundleError) as captured:
        verify_frozen_bundle(manifest, profile, evidence)
    assert "DO_NOT_ECHO" not in str(captured.value)


def test_cli_outputs_only_safe_bundle_projection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest, profile, evidence = _coherent_bundle()
    paths = {
        "manifest": tmp_path / "manifest.json",
        "profile": tmp_path / "profile.json",
        "evidence": tmp_path / "evidence.json",
    }
    for key, payload in (
        ("manifest", manifest),
        ("profile", profile),
        ("evidence", evidence),
    ):
        paths[key].write_text(json.dumps(payload), encoding="utf-8")
    assert (
        main(
            [
                "--manifest",
                str(paths["manifest"]),
                "--profile",
                str(paths["profile"]),
                "--evidence",
                str(paths["evidence"]),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    projected = json.loads(output)
    assert projected["bundle_digest"].startswith("sha256:")
    assert projected["actual_post_authorized"] is False
    assert "official_evidence_refs" not in output
    assert "quantity_units" not in output
    assert "operator_approval_ref" not in output


def test_script_imports_only_offline_modules() -> None:
    source_path = Path(bundle_module.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert imported_roots <= {
        "__future__",
        "argparse",
        "dataclasses",
        "hashlib",
        "json",
        "pathlib",
        "scripts",
        "typing",
    }
