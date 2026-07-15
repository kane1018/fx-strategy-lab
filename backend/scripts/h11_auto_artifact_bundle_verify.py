"""Verify one frozen H-11 evidence/profile/generation artifact bundle offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.h11_auto_generation_manifest import (
    GenerationManifestError,
    canonical_manifest_digest,
    load_local_manifest,
    validate_generation_manifest,
)
from scripts.h11_auto_profile_acceptance import (
    ProfileAcceptanceError,
    ProfileVerdict,
    evaluate_profile_evidence,
    load_local_evidence,
)
from scripts.h11_auto_profile_freeze import (
    ProfileFreezeError,
    load_local_profile,
    validate_and_bind_profile,
)


class ArtifactBundleError(ValueError):
    """Artifact bundle mismatch without echoing source values."""


@dataclass(frozen=True)
class BundleVerification:
    generation_label: str
    profile_label: str
    entry_style: str
    manifest_digest: str
    profile_digest: str
    evidence_digest: str
    bundle_digest: str

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "verification_status": "BUNDLE_COHERENT_NOT_ACTIVATED",
            "generation_label": self.generation_label,
            "profile_label": self.profile_label,
            "entry_style": self.entry_style,
            "manifest_digest": self.manifest_digest,
            "profile_digest": self.profile_digest,
            "evidence_digest": self.evidence_digest,
            "bundle_digest": self.bundle_digest,
            "actual_adapter_authorized": False,
            "broker_read_authorized": False,
            "broker_write_authorized": False,
            "credential_read_authorized": False,
            "actual_post_authorized": False,
            "live_ready": False,
            "unattended_live_supported": False,
        }


def _canonical_digest(payload: dict[str, str]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def verify_frozen_bundle(
    manifest_payload: Any,
    profile_payload: Any,
    evidence_payload: Any,
) -> BundleVerification:
    """Verify exact cross-artifact identity and execution-mode binding."""

    try:
        manifest = validate_generation_manifest(manifest_payload, mode="frozen")
        profile, profile_digest, profile_verdict = validate_and_bind_profile(
            profile_payload,
            evidence_payload,
            mode="frozen",
        )
        evidence = evaluate_profile_evidence(evidence_payload)
    except (GenerationManifestError, ProfileFreezeError, ProfileAcceptanceError) as error:
        raise ArtifactBundleError("one or more frozen artifacts are invalid") from error

    if profile_verdict is not ProfileVerdict.ACCEPT_FOR_DISABLED_ADAPTER_DESIGN:
        raise ArtifactBundleError("profile evidence is not accepted")

    entry = manifest["entry"]
    if entry["execution_profile_label"] != profile["profile_label"]:
        raise ArtifactBundleError("manifest and profile labels do not match")
    if entry["execution_profile_hash"] != profile_digest:
        raise ArtifactBundleError("manifest and profile digests do not match")

    expected_style = {
        "PENDING": "PENDING_ENTRY",
        "IMMEDIATE": "IMMEDIATE_ENTRY",
    }[profile["entry_mode"]]
    if entry["entry_style"] != expected_style:
        raise ArtifactBundleError("manifest and profile entry modes do not match")

    if manifest["ownership"]["account_mode"] == "DEDICATED" and (
        profile["ownership_contract"] != "DEDICATED_ACCOUNT"
    ):
        raise ArtifactBundleError("manifest and profile ownership do not match")

    manifest_digest = canonical_manifest_digest(manifest)
    digest_payload = {
        "bundle_schema": "H11_AUTO_FROZEN_ARTIFACT_BUNDLE_V1",
        "generation_label": manifest["identity"]["generation_label"],
        "manifest_digest": manifest_digest,
        "profile_digest": profile_digest,
        "evidence_digest": evidence.evidence_digest,
    }
    return BundleVerification(
        generation_label=manifest["identity"]["generation_label"],
        profile_label=profile["profile_label"],
        entry_style=entry["entry_style"],
        manifest_digest=manifest_digest,
        profile_digest=profile_digest,
        evidence_digest=evidence.evidence_digest,
        bundle_digest=_canonical_digest(digest_payload),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify one frozen H-11 artifact bundle without activation"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_frozen_bundle(
            load_local_manifest(args.manifest),
            load_local_profile(args.profile),
            load_local_evidence(args.evidence),
        )
    except (
        ArtifactBundleError,
        GenerationManifestError,
        ProfileFreezeError,
        ProfileAcceptanceError,
    ) as error:
        print(f"ARTIFACT_BUNDLE_BLOCKED: {error}")
        return 2
    print(json.dumps(result.to_safe_dict(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
