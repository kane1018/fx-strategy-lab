"""Validate and hash one sanitized H-11 execution profile offline.

The tool binds a profile to accepted broker capability evidence.  It never
creates an adapter, reads credentials or broker state, performs network I/O,
or grants runtime/live authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any

from scripts.h11_auto_profile_acceptance import (
    Capability,
    ProfileAcceptanceError,
    ProfileVerdict,
    evaluate_profile_evidence,
    load_local_evidence,
)

MAX_PROFILE_BYTES = 128 * 1024
DRAFT_SCHEMA = "H11_AUTO_EXECUTION_PROFILE_V1_DRAFT"
FROZEN_SCHEMA = "H11_AUTO_EXECUTION_PROFILE_V1"
DRAFT_STATUS = "PENDING_BROKER_AND_OPERATOR"
FROZEN_STATUS = "OPERATOR_FROZEN_NOT_ACTIVATED"
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
SHA256_LABEL = re.compile(r"^sha256:[0-9a-f]{64}$")

PROFILE_KEYS = frozenset(
    {
        "profile_schema",
        "profile_status",
        "profile_label",
        "broker_label",
        "entry_mode",
        "pending_expiry_contract",
        "fill_atomicity_contract",
        "protection_creation_contract",
        "protection_size_contract",
        "server_side_stop_loss",
        "server_side_take_profit",
        "position_specific_settlement",
        "authoritative_read_after_unknown",
        "ownership_contract",
        "minimum_permission_contract",
        "rate_limit_contract",
        "fee_and_holding_cost_contract",
        "official_evidence_refs",
        "accepted_evidence_digest",
        "operator_approval_ref",
        "safety",
    }
)

SAFETY_KEYS = frozenset(
    {
        "actual_adapter_authorized",
        "broker_read_authorized",
        "broker_write_authorized",
        "credential_read_authorized",
        "actual_post_authorized",
        "live_ready",
        "unattended_live_supported",
    }
)


class ProfileFreezeError(ValueError):
    """Invalid profile input without echoing source values."""


def _exact_mapping(value: Any, expected: frozenset[str], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ProfileFreezeError(f"{label} schema mismatch")
    return value


def _is_pending(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("PENDING_")


def _label(value: Any, *, draft: bool) -> str:
    if not isinstance(value, str) or not SAFE_LABEL.fullmatch(value):
        raise ProfileFreezeError("profile label value is invalid")
    if not draft and _is_pending(value):
        raise ProfileFreezeError("frozen profile contains pending value")
    return value


def _required_false(mapping: dict[str, Any], key: str) -> None:
    if mapping[key] is not False:
        raise ProfileFreezeError("profile safety authority must remain false")


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def validate_and_bind_profile(
    profile_payload: Any,
    evidence_payload: Any,
    *,
    mode: str,
) -> tuple[dict[str, Any], str, ProfileVerdict]:
    """Validate profile and bind frozen mode to accepted sanitized evidence."""

    if mode not in {"draft", "frozen"}:
        raise ProfileFreezeError("profile mode is invalid")
    draft = mode == "draft"
    profile = _exact_mapping(profile_payload, PROFILE_KEYS, label="execution profile")
    expected_schema = DRAFT_SCHEMA if draft else FROZEN_SCHEMA
    expected_status = DRAFT_STATUS if draft else FROZEN_STATUS
    if profile["profile_schema"] != expected_schema:
        raise ProfileFreezeError("profile schema is invalid")
    if profile["profile_status"] != expected_status:
        raise ProfileFreezeError("profile status is invalid")

    try:
        acceptance = evaluate_profile_evidence(evidence_payload)
    except ProfileAcceptanceError as error:
        raise ProfileFreezeError("broker evidence is invalid") from error

    profile_label = _label(profile["profile_label"], draft=draft)
    if profile_label != acceptance.profile_label:
        raise ProfileFreezeError("profile and evidence labels do not match")
    for key in (
        "broker_label",
        "pending_expiry_contract",
        "fill_atomicity_contract",
        "protection_creation_contract",
        "protection_size_contract",
        "minimum_permission_contract",
        "rate_limit_contract",
        "fee_and_holding_cost_contract",
        "operator_approval_ref",
    ):
        _label(profile[key], draft=draft)

    entry_mode = _label(profile["entry_mode"], draft=draft)
    allowed_entry_modes = (
        {"PENDING_BROKER_ANSWER", "PENDING", "IMMEDIATE"}
        if draft
        else {"PENDING", "IMMEDIATE"}
    )
    if entry_mode not in allowed_entry_modes:
        raise ProfileFreezeError("entry mode is invalid")
    ownership = _label(profile["ownership_contract"], draft=draft)
    if not draft and ownership not in {
        "DEDICATED_ACCOUNT",
        "OFFICIAL_UNIQUE_OWNERSHIP",
    }:
        raise ProfileFreezeError("ownership contract is invalid")

    refs = profile["official_evidence_refs"]
    if not isinstance(refs, list) or len(refs) > 32:
        raise ProfileFreezeError("official evidence refs are invalid")
    if any(not isinstance(value, str) or not SAFE_LABEL.fullmatch(value) for value in refs):
        raise ProfileFreezeError("official evidence ref is invalid")
    if len(set(refs)) != len(refs):
        raise ProfileFreezeError("official evidence refs contain duplicates")

    digest = profile["accepted_evidence_digest"]
    if not isinstance(digest, str):
        raise ProfileFreezeError("accepted evidence digest is invalid")
    if draft:
        if not (_is_pending(digest) or SHA256_LABEL.fullmatch(digest)):
            raise ProfileFreezeError("accepted evidence digest is invalid")
    elif not SHA256_LABEL.fullmatch(digest):
        raise ProfileFreezeError("accepted evidence digest is invalid")

    safety = _exact_mapping(profile["safety"], SAFETY_KEYS, label="profile safety")
    for key in SAFETY_KEYS:
        _required_false(safety, key)

    bool_keys = (
        "server_side_stop_loss",
        "server_side_take_profit",
        "position_specific_settlement",
        "authoritative_read_after_unknown",
    )
    if any(type(profile[key]) is not bool for key in bool_keys):
        raise ProfileFreezeError("profile capability boolean is invalid")

    if not draft:
        if acceptance.verdict is not ProfileVerdict.ACCEPT_FOR_DISABLED_ADAPTER_DESIGN:
            raise ProfileFreezeError("broker evidence is not accepted for profile freeze")
        if digest != acceptance.evidence_digest:
            raise ProfileFreezeError("accepted evidence digest does not match")
        evidence_refs = evidence_payload["official_evidence_refs"]
        if refs != evidence_refs:
            raise ProfileFreezeError("official evidence refs do not match")
        if not all(profile[key] is True for key in bool_keys):
            raise ProfileFreezeError("required profile capability is not enabled")

        capabilities = evidence_payload["capabilities"]
        if entry_mode == "PENDING" and (
            capabilities["short_pending_expiry"] != Capability.CONFIRMED_YES.value
        ):
            raise ProfileFreezeError("pending entry mode lacks confirmed short expiry")
        if entry_mode == "IMMEDIATE" and (
            capabilities["no_pending_entry"] != Capability.CONFIRMED_YES.value
        ):
            raise ProfileFreezeError("immediate entry mode lacks confirmed evidence")

        def contains_pending(value: Any) -> bool:
            if _is_pending(value):
                return True
            if isinstance(value, dict):
                return any(contains_pending(item) for item in value.values())
            if isinstance(value, list):
                return any(contains_pending(item) for item in value)
            return False

        if contains_pending(profile):
            raise ProfileFreezeError("frozen profile contains pending value")

    return profile, _canonical_digest(profile), acceptance.verdict


def load_local_profile(path: Path) -> Any:
    """Read bounded JSON from one regular non-symlink local file."""

    try:
        info = path.lstat()
    except OSError as error:
        raise ProfileFreezeError("profile file is unavailable") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ProfileFreezeError("profile must be a regular non-symlink file")
    if info.st_size <= 0 or info.st_size > MAX_PROFILE_BYTES:
        raise ProfileFreezeError("profile file size is invalid")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileFreezeError("profile JSON is invalid") from error


def _safe_projection(
    profile: dict[str, Any],
    profile_digest: str,
    evidence_verdict: ProfileVerdict,
    *,
    mode: str,
) -> dict[str, Any]:
    result = {
        "validation_status": (
            "DRAFT_VALID_NOT_FROZEN"
            if mode == "draft"
            else "PROFILE_FROZEN_FOR_DISABLED_ADAPTER_REVIEW_ONLY"
        ),
        "profile_schema": profile["profile_schema"],
        "profile_status": profile["profile_status"],
        "profile_label": profile["profile_label"],
        "broker_label": profile["broker_label"],
        "entry_mode": profile["entry_mode"],
        "evidence_verdict": evidence_verdict.value,
        "actual_adapter_authorized": False,
        "broker_read_authorized": False,
        "broker_write_authorized": False,
        "credential_read_authorized": False,
        "actual_post_authorized": False,
        "live_ready": False,
        "unattended_live_supported": False,
    }
    if mode == "frozen":
        result["profile_digest"] = profile_digest
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and bind one local H-11 execution profile offline"
    )
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--mode", choices=("draft", "frozen"), required=True)
    args = parser.parse_args(argv)
    try:
        profile_payload = load_local_profile(args.profile)
        evidence_payload = load_local_evidence(args.evidence)
        profile, digest, verdict = validate_and_bind_profile(
            profile_payload,
            evidence_payload,
            mode=args.mode,
        )
    except (ProfileFreezeError, ProfileAcceptanceError) as error:
        print(f"PROFILE_FREEZE_BLOCKED: {error}")
        return 2
    print(
        json.dumps(
            _safe_projection(profile, digest, verdict, mode=args.mode),
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
