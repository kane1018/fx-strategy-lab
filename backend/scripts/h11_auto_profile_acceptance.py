"""Classify one sanitized H-11 execution profile capability record offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

SCHEMA = "H11_AUTO_EXECUTION_PROFILE_EVIDENCE_V1"
MAX_EVIDENCE_BYTES = 128 * 1024
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")


class ProfileAcceptanceError(ValueError):
    """Invalid sanitized evidence without echoing source values."""


class Capability(str, Enum):
    CONFIRMED_YES = "CONFIRMED_YES"
    CONFIRMED_NO = "CONFIRMED_NO"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_ANSWERED = "NOT_ANSWERED"


class ProfileVerdict(str, Enum):
    ACCEPT_FOR_DISABLED_ADAPTER_DESIGN = "ACCEPT_FOR_DISABLED_ADAPTER_DESIGN"
    NEEDS_FOLLOWUP = "NEEDS_FOLLOWUP"
    REJECT = "REJECT"


CAPABILITY_KEYS = frozenset(
    {
        "short_pending_expiry",
        "no_pending_entry",
        "full_fill_or_none",
        "atomic_protection_with_entry",
        "protection_size_matches_actual_fill",
        "server_side_stop_loss",
        "server_side_take_profit",
        "position_specific_settlement",
        "authoritative_read_after_unknown",
        "broker_state_readable",
        "protected_size_readable",
        "excess_size_can_reverse_position",
        "minimum_permission_known",
        "private_get_rate_limit_known",
        "private_post_rate_limit_known",
        "tos_automatic_trading_allowed",
        "fee_model_known",
        "ownership_isolation_supported",
    }
)

DIRECT_YES_REQUIREMENTS = {
    "server_side_stop_loss": "SERVER_SIDE_STOP_LOSS_NOT_CONFIRMED",
    "server_side_take_profit": "SERVER_SIDE_TAKE_PROFIT_NOT_CONFIRMED",
    "position_specific_settlement": "POSITION_SPECIFIC_SETTLEMENT_NOT_CONFIRMED",
    "authoritative_read_after_unknown": "AUTHORITATIVE_READ_AFTER_UNKNOWN_NOT_CONFIRMED",
    "broker_state_readable": "BROKER_STATE_READ_NOT_CONFIRMED",
    "protected_size_readable": "PROTECTED_SIZE_READ_NOT_CONFIRMED",
    "minimum_permission_known": "MINIMUM_PERMISSION_NOT_CONFIRMED",
    "private_get_rate_limit_known": "PRIVATE_GET_RATE_LIMIT_NOT_CONFIRMED",
    "private_post_rate_limit_known": "PRIVATE_POST_RATE_LIMIT_NOT_CONFIRMED",
    "tos_automatic_trading_allowed": "TOS_AUTOMATIC_TRADING_NOT_CONFIRMED",
    "fee_model_known": "FEE_MODEL_NOT_CONFIRMED",
    "ownership_isolation_supported": "OWNERSHIP_ISOLATION_NOT_CONFIRMED",
}


@dataclass(frozen=True)
class AcceptanceResult:
    profile_label: str
    evidence_digest: str
    verdict: ProfileVerdict
    blocking_codes: tuple[str, ...]
    actual_adapter_authorized: bool = False
    broker_read_authorized: bool = False
    broker_write_authorized: bool = False
    credential_read_authorized: bool = False
    actual_post_authorized: bool = False
    live_ready: bool = False
    unattended_live_supported: bool = False

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "profile_label": self.profile_label,
            "evidence_digest": self.evidence_digest,
            "verdict": self.verdict.value,
            "blocking_codes": list(self.blocking_codes),
            "actual_adapter_authorized": self.actual_adapter_authorized,
            "broker_read_authorized": self.broker_read_authorized,
            "broker_write_authorized": self.broker_write_authorized,
            "credential_read_authorized": self.credential_read_authorized,
            "actual_post_authorized": self.actual_post_authorized,
            "live_ready": self.live_ready,
            "unattended_live_supported": self.unattended_live_supported,
        }


def _exact_mapping(value: Any, expected: frozenset[str], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ProfileAcceptanceError(f"{label} schema mismatch")
    return value


def _safe_label(value: Any) -> str:
    if not isinstance(value, str) or not SAFE_LABEL.fullmatch(value):
        raise ProfileAcceptanceError("profile label is invalid")
    return value


def _capability(value: Any) -> Capability:
    if not isinstance(value, str):
        raise ProfileAcceptanceError("capability value is invalid")
    try:
        return Capability(value)
    except ValueError as error:
        raise ProfileAcceptanceError("capability value is invalid") from error


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _alternative_gate(
    *,
    first_path: tuple[Capability, ...],
    second_path: tuple[Capability, ...],
    code: str,
) -> tuple[str, str | None]:
    paths = (first_path, second_path)
    if any(all(value is Capability.CONFIRMED_YES for value in path) for path in paths):
        return "PASS", None
    if all(any(value is Capability.CONFIRMED_NO for value in path) for path in paths):
        return "REJECT", code
    return "FOLLOWUP", code


def evaluate_profile_evidence(payload: Any) -> AcceptanceResult:
    """Validate and classify sanitized official capability evidence."""

    root = _exact_mapping(
        payload,
        frozenset({"schema", "profile_label", "capabilities", "official_evidence_refs"}),
        label="profile evidence",
    )
    if root["schema"] != SCHEMA:
        raise ProfileAcceptanceError("profile evidence schema is invalid")
    profile_label = _safe_label(root["profile_label"])
    capability_mapping = _exact_mapping(
        root["capabilities"], CAPABILITY_KEYS, label="capabilities"
    )
    capabilities = {key: _capability(value) for key, value in capability_mapping.items()}

    refs = root["official_evidence_refs"]
    if not isinstance(refs, list) or len(refs) > 32:
        raise ProfileAcceptanceError("official evidence refs are invalid")
    if any(not isinstance(value, str) or not SAFE_LABEL.fullmatch(value) for value in refs):
        raise ProfileAcceptanceError("official evidence ref is invalid")
    if len(set(refs)) != len(refs):
        raise ProfileAcceptanceError("official evidence refs contain duplicates")

    rejected: list[str] = []
    followup: list[str] = []

    expiry_state, expiry_code = _alternative_gate(
        first_path=(capabilities["short_pending_expiry"],),
        second_path=(capabilities["no_pending_entry"],),
        code="SHORT_EXPIRY_OR_NO_PENDING_ENTRY_NOT_CONFIRMED",
    )
    if expiry_state == "REJECT" and expiry_code:
        rejected.append(expiry_code)
    elif expiry_state == "FOLLOWUP" and expiry_code:
        followup.append(expiry_code)

    fill_state, fill_code = _alternative_gate(
        first_path=(capabilities["full_fill_or_none"],),
        second_path=(
            capabilities["atomic_protection_with_entry"],
            capabilities["protection_size_matches_actual_fill"],
        ),
        code="FILL_OR_ATOMIC_PROTECTION_NOT_CONFIRMED",
    )
    if fill_state == "REJECT" and fill_code:
        rejected.append(fill_code)
    elif fill_state == "FOLLOWUP" and fill_code:
        followup.append(fill_code)

    for key, code in DIRECT_YES_REQUIREMENTS.items():
        value = capabilities[key]
        if value is Capability.CONFIRMED_NO:
            rejected.append(code)
        elif value in {Capability.AMBIGUOUS, Capability.NOT_ANSWERED}:
            followup.append(code)

    excess = capabilities["excess_size_can_reverse_position"]
    if excess is Capability.CONFIRMED_YES:
        rejected.append("EXCESS_SIZE_CAN_REVERSE_POSITION")
    elif excess in {Capability.AMBIGUOUS, Capability.NOT_ANSWERED}:
        followup.append("EXCESS_SIZE_REVERSAL_BEHAVIOR_NOT_CONFIRMED")

    if not refs:
        followup.append("OFFICIAL_EVIDENCE_REFS_MISSING")

    if rejected:
        verdict = ProfileVerdict.REJECT
        blocking_codes = tuple(sorted(set(rejected + followup)))
    elif followup:
        verdict = ProfileVerdict.NEEDS_FOLLOWUP
        blocking_codes = tuple(sorted(set(followup)))
    else:
        verdict = ProfileVerdict.ACCEPT_FOR_DISABLED_ADAPTER_DESIGN
        blocking_codes = ()

    return AcceptanceResult(
        profile_label=profile_label,
        evidence_digest=_canonical_digest(root),
        verdict=verdict,
        blocking_codes=blocking_codes,
    )


def load_local_evidence(path: Path) -> Any:
    """Read bounded sanitized JSON from a regular non-symlink local file."""

    try:
        info = path.lstat()
    except OSError as error:
        raise ProfileAcceptanceError("profile evidence file is unavailable") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ProfileAcceptanceError("profile evidence must be a regular non-symlink file")
    if info.st_size <= 0 or info.st_size > MAX_EVIDENCE_BYTES:
        raise ProfileAcceptanceError("profile evidence file size is invalid")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileAcceptanceError("profile evidence JSON is invalid") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify one sanitized H-11 broker capability record offline"
    )
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate_profile_evidence(load_local_evidence(args.evidence))
    except ProfileAcceptanceError as error:
        print(f"PROFILE_EVIDENCE_BLOCKED: {error}")
        return 2
    print(json.dumps(result.to_safe_dict(), sort_keys=True, indent=2))
    return 0 if result.verdict is ProfileVerdict.ACCEPT_FOR_DISABLED_ADAPTER_DESIGN else 3


if __name__ == "__main__":
    raise SystemExit(main())
