"""H-11 v4 unattended live daily operator authorization artifact (fake-only, unwired).

Phase 4 §3.2 item 1, with the operator's 2026-07-24 decisions applied: each
authorization artifact covers exactly one JST trading day and, combined with
the frozen 1-entry-per-day cap, permits at most one entry. Every trading day
of unattended operation therefore requires a fresh, separate operator action.

**This module is read-and-consume only.** It contains no function that
creates, extends, re-dates, or re-issues an authorization artifact — the
artifact is operator-write-only by construction, symmetric with the latch-only
risk KILL. The only write this module ever performs is the one-use O_EXCL
consumption marker placed next to the artifact when an entry attempt claims
it. No network, credential, broker, or notification access exists here, and
nothing is wired into any runtime.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA = (
    "H11_V4_UNATTENDED_LIVE_DAILY_AUTHORIZATION_V1"
)
# The marker deliberately carries a DIFFERENT schema tag than the operator's
# artifact, so nothing keying on the artifact schema can ever mistake the
# automation-written marker for an operator-written authorization.
V4_UNATTENDED_LIVE_CONSUMPTION_SCHEMA = (
    "H11_V4_UNATTENDED_LIVE_AUTHORIZATION_CONSUMPTION_V1"
)
V4_UNATTENDED_LIVE_MAXIMUM_ENTRIES_PER_AUTHORIZATION = 1
_JST = ZoneInfo("Asia/Tokyo")


class V4UnattendedLiveAuthorizationError(RuntimeError):
    """Fail-closed authorization error containing safe labels only."""


@dataclass(frozen=True)
class V4UnattendedLiveAuthorizationCheck:
    authorized: bool
    blocked_reasons: tuple[str, ...]
    trading_day_jst: str
    consumption_available: bool
    permit_issued: bool = False
    broker_post_authorized: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.authorized) is not bool
            or type(self.consumption_available) is not bool
            or type(self.blocked_reasons) is not tuple
            or self.permit_issued is not False
            or self.broker_post_authorized is not False
        ):
            raise V4UnattendedLiveAuthorizationError("AUTHORIZATION_CHECK_INVALID")
        for reason in self.blocked_reasons:
            _validate_safe_reason(reason)
        if self.authorized and self.blocked_reasons:
            raise V4UnattendedLiveAuthorizationError("AUTHORIZATION_CHECK_INCONSISTENT")
        if not self.authorized and not self.blocked_reasons:
            raise V4UnattendedLiveAuthorizationError("AUTHORIZATION_CHECK_INCONSISTENT")

    def __bool__(self) -> bool:
        return False


def check_operator_daily_authorization(
    *,
    artifact_path: Path,
    expected_generation_digest: str,
    now_utc: datetime,
) -> V4UnattendedLiveAuthorizationCheck:
    """Validate the operator's daily artifact read-only; never consume or write."""

    _require_generation_digest(expected_generation_digest)
    if now_utc.tzinfo is None:
        raise V4UnattendedLiveAuthorizationError("AUTHORIZATION_CLOCK_INVALID")
    today_jst = now_utc.astimezone(_JST).date().isoformat()
    reasons: list[str] = []
    payload: dict[str, object] | None = None
    if artifact_path.is_symlink():
        reasons.append("AUTHORIZATION_ARTIFACT_SYMLINK_REFUSED")
    elif not artifact_path.is_file():
        reasons.append("AUTHORIZATION_ARTIFACT_MISSING")
    else:
        try:
            loaded = json.loads(artifact_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
            else:
                reasons.append("AUTHORIZATION_ARTIFACT_MALFORMED")
        except (OSError, json.JSONDecodeError):
            reasons.append("AUTHORIZATION_ARTIFACT_MALFORMED")
    if payload is not None:
        if payload.get("schema") != V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA:
            reasons.append("AUTHORIZATION_SCHEMA_INVALID")
        if payload.get("generation_digest") != expected_generation_digest:
            reasons.append("AUTHORIZATION_GENERATION_MISMATCH")
        if payload.get("trading_day_jst") != today_jst:
            reasons.append("AUTHORIZATION_DAY_MISMATCH")
        if (
            payload.get("maximum_entries")
            != V4_UNATTENDED_LIVE_MAXIMUM_ENTRIES_PER_AUTHORIZATION
        ):
            reasons.append("AUTHORIZATION_ENTRY_CAP_INVALID")
        if payload.get("operator_authorized") is not True:
            reasons.append("AUTHORIZATION_NOT_GRANTED_BY_OPERATOR")
    consumed_marker = _consumption_marker_path(
        artifact_path=artifact_path, trading_day_jst=today_jst
    )
    consumption_available = not consumed_marker.exists()
    if not consumption_available:
        reasons.append("AUTHORIZATION_ALREADY_CONSUMED")
    return V4UnattendedLiveAuthorizationCheck(
        authorized=not reasons,
        blocked_reasons=tuple(dict.fromkeys(reasons)),
        trading_day_jst=today_jst,
        consumption_available=consumption_available,
    )


def consume_operator_daily_authorization_once(
    *,
    artifact_path: Path,
    expected_generation_digest: str,
    now_utc: datetime,
) -> None:
    """Claim the artifact's single entry exactly once; a second claim fails closed."""

    check = check_operator_daily_authorization(
        artifact_path=artifact_path,
        expected_generation_digest=expected_generation_digest,
        now_utc=now_utc,
    )
    if not check.consumption_available:
        raise V4UnattendedLiveAuthorizationError("AUTHORIZATION_ALREADY_CONSUMED")
    if not check.authorized:
        raise V4UnattendedLiveAuthorizationError("AUTHORIZATION_NOT_CLEAR_FOR_CONSUMPTION")
    marker = _consumption_marker_path(
        artifact_path=artifact_path, trading_day_jst=check.trading_day_jst
    )
    payload = (
        '{"schema":"' + V4_UNATTENDED_LIVE_CONSUMPTION_SCHEMA + '",'
        '"trading_day_jst":"' + check.trading_day_jst + '",'
        '"status":"CONSUMED_ONE_USE_NO_RETRY","broker_post_count":0}\n'
    )
    try:
        descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        raise V4UnattendedLiveAuthorizationError(
            "AUTHORIZATION_ALREADY_CONSUMED"
        ) from None
    except OSError as error:
        raise V4UnattendedLiveAuthorizationError(
            "AUTHORIZATION_CONSUMPTION_FAILED"
        ) from error


def _consumption_marker_path(*, artifact_path: Path, trading_day_jst: str) -> Path:
    return artifact_path.parent / (
        f"unattended-authorization-consumed-{trading_day_jst}.json"
    )


def _require_generation_digest(value: str) -> None:
    # The isinstance check must run before any str method so a non-string
    # input still raises the module's own safe-label error, never a bare
    # AttributeError.
    if not isinstance(value, str):
        raise V4UnattendedLiveAuthorizationError("AUTHORIZATION_GENERATION_DIGEST_INVALID")
    normalized = value.removeprefix("sha256:")
    if (
        not value.startswith("sha256:")
        or len(normalized) != 64
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise V4UnattendedLiveAuthorizationError("AUTHORIZATION_GENERATION_DIGEST_INVALID")


def _validate_safe_reason(reason: str) -> None:
    if (
        not isinstance(reason, str)
        or not reason
        or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"
            for character in reason
        )
    ):
        raise V4UnattendedLiveAuthorizationError("AUTHORIZATION_REASON_INVALID")
