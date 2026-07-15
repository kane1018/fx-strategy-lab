"""Validate and hash an H-11 auto generation manifest without external I/O.

The CLI accepts local JSON only.  It never reads environment variables,
credentials, broker state, or network resources and never writes runtime state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

MAX_MANIFEST_BYTES = 256 * 1024
DRAFT_SCHEMA = "H11_AUTO_GENERATION_V1_DRAFT"
FROZEN_SCHEMA = "H11_AUTO_GENERATION_V1"
DRAFT_STATUS = "PENDING_OPERATOR_APPROVAL"
FROZEN_STATUS = "OPERATOR_FROZEN_NOT_ACTIVATED"
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
SHA256_LABEL = re.compile(r"^sha256:[0-9a-f]{64}$")


class GenerationManifestError(ValueError):
    """Fail-closed manifest validation error with no manifest value echo."""


TOP_LEVEL_KEYS = frozenset(
    {
        "manifest_schema",
        "manifest_status",
        "identity",
        "signal",
        "data_clock",
        "position",
        "risk",
        "entry",
        "exit",
        "reconciliation",
        "dead_man",
        "notification",
        "ownership",
        "host",
        "credential_permission",
        "safety",
    }
)

SECTION_KEYS = {
    "identity": frozenset(
        {"generation_label", "project", "strategy_version", "implementation_digest"}
    ),
    "signal": frozenset(
        {
            "selected_horizon",
            "signal_config_hash",
            "buy_threshold",
            "sell_threshold",
            "formal_only",
            "rolling_allowed",
            "h24_allowed",
        }
    ),
    "data_clock": frozenset(
        {
            "source_profile_label",
            "finalized_m1_required",
            "finalization_margin_seconds",
            "maximum_m1_age_seconds",
            "maximum_ticker_age_seconds",
            "maximum_clock_skew_seconds",
            "missed_signal_backfill_allowed",
        }
    ),
    "position": frozenset(
        {
            "symbol",
            "quantity_units",
            "maximum_open_positions",
            "maximum_entries_per_jst_day",
            "scale_in_allowed",
            "hedging_allowed",
        }
    ),
    "risk": frozenset(
        {
            "policy_label",
            "per_trade_loss_bound_jpy",
            "daily_loss_limit_jpy",
            "monthly_loss_limit_jpy",
            "maximum_consecutive_losses",
            "automatic_resume_after_stop",
        }
    ),
    "entry": frozenset(
        {
            "execution_profile_label",
            "execution_profile_hash",
            "entry_style",
            "short_pending_expiry_or_no_pending_entry_required",
            "full_fill_or_atomic_protection_size_match_required",
            "server_side_stop_required",
            "server_side_take_profit_required",
            "maximum_attempts_per_intent",
            "retry_allowed",
            "repost_allowed",
        }
    ),
    "exit": frozenset(
        {
            "exit_profile_label",
            "position_specific_route_required",
            "generic_close_allowed",
            "opposite_entry_as_exit_allowed",
            "maximum_attempts_per_intent",
            "retry_allowed",
            "repost_allowed",
            "stop_loss_contract",
            "take_profit_contract",
            "maximum_hold_seconds",
            "formal_edge_exit_enabled",
        }
    ),
    "reconciliation": frozenset(
        {
            "boot_required",
            "before_entry_required",
            "after_entry_required",
            "periodic_position_monitor_required",
            "before_exit_required",
            "after_exit_required",
            "after_websocket_reconnect_required",
            "after_process_restart_required",
            "maximum_age_seconds",
            "unknown_result_halts",
        }
    ),
    "dead_man": frozenset(
        {
            "policy_label",
            "heartbeat_interval_seconds",
            "maximum_heartbeat_age_seconds",
            "automatic_resume",
        }
    ),
    "notification": frozenset(
        {
            "primary_profile_label",
            "secondary_profile_label",
            "entry_requires_primary_ready",
            "delivery_failure_blocks_new_entry",
        }
    ),
    "ownership": frozenset({"account_mode", "external_or_manual_position_halts"}),
    "host": frozenset(
        {
            "host_profile_label",
            "supervisor_profile_label",
            "clock_monitor_required",
            "operator_kill_required",
        }
    ),
    "credential_permission": frozenset(
        {
            "credential_profile_label",
            "permission_profile_label",
            "env_fallback_allowed",
            "raw_secret_logging_allowed",
        }
    ),
    "safety": frozenset(
        {"actual_post_authorized", "live_ready", "unattended_live_supported"}
    ),
}


def _is_pending(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("PENDING")
        and value not in {"PENDING_ENTRY"}
    )


def _exact_keys(mapping: Any, expected: frozenset[str], *, section: str) -> dict[str, Any]:
    if not isinstance(mapping, dict) or set(mapping) != expected:
        raise GenerationManifestError(f"{section} schema mismatch")
    return mapping


def _value_or_pending(value: Any, *, draft: bool) -> bool:
    if _is_pending(value):
        if not draft:
            raise GenerationManifestError("frozen manifest contains pending value")
        return True
    return False


def _label(value: Any, *, draft: bool) -> str | None:
    if _value_or_pending(value, draft=draft):
        return None
    if not isinstance(value, str) or not SAFE_LABEL.fullmatch(value):
        raise GenerationManifestError("manifest label is invalid")
    return value


def _sha256(value: Any, *, draft: bool) -> None:
    if _value_or_pending(value, draft=draft):
        return
    if not isinstance(value, str) or not SHA256_LABEL.fullmatch(value):
        raise GenerationManifestError("manifest SHA-256 is invalid")


def _positive_int(value: Any, *, draft: bool, allow_zero: bool = False) -> int | None:
    if _value_or_pending(value, draft=draft):
        return None
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise GenerationManifestError("manifest integer is invalid")
    return value


def _boolean(value: Any, *, draft: bool) -> bool | None:
    if _value_or_pending(value, draft=draft):
        return None
    if type(value) is not bool:
        raise GenerationManifestError("manifest boolean is invalid")
    return value


def _decimal_probability(value: Any, *, draft: bool) -> Decimal | None:
    if _value_or_pending(value, draft=draft):
        return None
    if not isinstance(value, str):
        raise GenerationManifestError("threshold must be a canonical decimal string")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise GenerationManifestError("threshold is invalid") from error
    if not result.is_finite() or not Decimal("0") < result < Decimal("1"):
        raise GenerationManifestError("threshold is outside probability range")
    if format(result.normalize(), "f") != value:
        raise GenerationManifestError("threshold is not canonical")
    return result


def _required_bool(mapping: dict[str, Any], key: str, expected: bool, *, draft: bool) -> None:
    value = _boolean(mapping[key], draft=draft)
    if value is not None and value is not expected:
        raise GenerationManifestError("frozen safety invariant is weakened")


def _contains_nonfinite(value: Any) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_contains_nonfinite(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_nonfinite(item) for item in value)
    return False


def validate_generation_manifest(payload: Any, *, mode: str) -> dict[str, Any]:
    """Return a validated manifest mapping or raise a fail-closed error."""

    if mode not in {"draft", "frozen"}:
        raise GenerationManifestError("manifest validation mode is invalid")
    draft = mode == "draft"
    root = _exact_keys(payload, TOP_LEVEL_KEYS, section="manifest")
    if _contains_nonfinite(root):
        raise GenerationManifestError("manifest contains non-finite number")

    expected_schema = DRAFT_SCHEMA if draft else FROZEN_SCHEMA
    expected_status = DRAFT_STATUS if draft else FROZEN_STATUS
    if root["manifest_schema"] != expected_schema or root["manifest_status"] != expected_status:
        raise GenerationManifestError("manifest identity is invalid for selected mode")

    sections = {
        name: _exact_keys(root[name], keys, section=name) for name, keys in SECTION_KEYS.items()
    }

    identity = sections["identity"]
    for key in ("generation_label", "project", "strategy_version"):
        _label(identity[key], draft=draft)
    _sha256(identity["implementation_digest"], draft=draft)

    signal = sections["signal"]
    horizon = _label(signal["selected_horizon"], draft=draft)
    if horizon is not None and horizon not in {"10m", "30m"}:
        raise GenerationManifestError("formal horizon is invalid")
    _sha256(signal["signal_config_hash"], draft=draft)
    buy = _decimal_probability(signal["buy_threshold"], draft=draft)
    sell = _decimal_probability(signal["sell_threshold"], draft=draft)
    if buy is not None and sell is not None and not sell < Decimal("0.5") < buy:
        raise GenerationManifestError("formal thresholds do not straddle 0.5")
    _required_bool(signal, "formal_only", True, draft=draft)
    _required_bool(signal, "rolling_allowed", False, draft=draft)
    _required_bool(signal, "h24_allowed", False, draft=draft)

    data_clock = sections["data_clock"]
    _label(data_clock["source_profile_label"], draft=draft)
    _required_bool(data_clock, "finalized_m1_required", True, draft=draft)
    for key in (
        "finalization_margin_seconds",
        "maximum_m1_age_seconds",
        "maximum_ticker_age_seconds",
        "maximum_clock_skew_seconds",
    ):
        _positive_int(data_clock[key], draft=draft, allow_zero=key == "finalization_margin_seconds")
    _required_bool(data_clock, "missed_signal_backfill_allowed", False, draft=draft)

    position = sections["position"]
    _label(position["symbol"], draft=draft)
    _positive_int(position["quantity_units"], draft=draft)
    for key in ("maximum_open_positions", "maximum_entries_per_jst_day"):
        value = _positive_int(position[key], draft=draft)
        if value is not None and value != 1:
            raise GenerationManifestError("position invariant must remain one")
    _required_bool(position, "scale_in_allowed", False, draft=draft)
    _required_bool(position, "hedging_allowed", False, draft=draft)

    risk = sections["risk"]
    _label(risk["policy_label"], draft=draft)
    per_trade = _positive_int(risk["per_trade_loss_bound_jpy"], draft=draft)
    daily = _positive_int(risk["daily_loss_limit_jpy"], draft=draft)
    monthly = _positive_int(risk["monthly_loss_limit_jpy"], draft=draft)
    _positive_int(risk["maximum_consecutive_losses"], draft=draft)
    if None not in {per_trade, daily, monthly} and not per_trade <= daily <= monthly:
        raise GenerationManifestError("risk limits are not monotonic")
    _required_bool(risk, "automatic_resume_after_stop", False, draft=draft)

    entry = sections["entry"]
    _label(entry["execution_profile_label"], draft=draft)
    _sha256(entry["execution_profile_hash"], draft=draft)
    entry_style = _label(entry["entry_style"], draft=draft)
    if entry_style is not None and entry_style not in {"PENDING_ENTRY", "IMMEDIATE_ENTRY"}:
        raise GenerationManifestError("entry style is invalid")
    for key in (
        "short_pending_expiry_or_no_pending_entry_required",
        "full_fill_or_atomic_protection_size_match_required",
        "server_side_stop_required",
        "server_side_take_profit_required",
    ):
        _required_bool(entry, key, True, draft=draft)
    attempts = _positive_int(entry["maximum_attempts_per_intent"], draft=draft)
    if attempts is not None and attempts != 1:
        raise GenerationManifestError("entry attempts must remain one")
    _required_bool(entry, "retry_allowed", False, draft=draft)
    _required_bool(entry, "repost_allowed", False, draft=draft)

    exit_config = sections["exit"]
    for key in ("exit_profile_label", "stop_loss_contract", "take_profit_contract"):
        _label(exit_config[key], draft=draft)
    _required_bool(exit_config, "position_specific_route_required", True, draft=draft)
    for key in (
        "generic_close_allowed",
        "opposite_entry_as_exit_allowed",
        "retry_allowed",
        "repost_allowed",
    ):
        _required_bool(exit_config, key, False, draft=draft)
    exit_attempts = _positive_int(exit_config["maximum_attempts_per_intent"], draft=draft)
    if exit_attempts is not None and exit_attempts != 1:
        raise GenerationManifestError("exit attempts must remain one")
    _positive_int(exit_config["maximum_hold_seconds"], draft=draft)
    _boolean(exit_config["formal_edge_exit_enabled"], draft=draft)

    reconciliation = sections["reconciliation"]
    for key in SECTION_KEYS["reconciliation"] - {"maximum_age_seconds"}:
        _required_bool(reconciliation, key, True, draft=draft)
    _positive_int(reconciliation["maximum_age_seconds"], draft=draft)

    dead_man = sections["dead_man"]
    _label(dead_man["policy_label"], draft=draft)
    interval = _positive_int(dead_man["heartbeat_interval_seconds"], draft=draft)
    maximum_age = _positive_int(dead_man["maximum_heartbeat_age_seconds"], draft=draft)
    if interval is not None and maximum_age is not None and maximum_age <= interval:
        raise GenerationManifestError("dead-man maximum age must exceed heartbeat interval")
    _required_bool(dead_man, "automatic_resume", False, draft=draft)

    notification = sections["notification"]
    _label(notification["primary_profile_label"], draft=draft)
    _label(notification["secondary_profile_label"], draft=draft)
    _required_bool(notification, "entry_requires_primary_ready", True, draft=draft)
    _required_bool(notification, "delivery_failure_blocks_new_entry", True, draft=draft)

    ownership = sections["ownership"]
    account_mode = _label(ownership["account_mode"], draft=draft)
    if account_mode is not None and account_mode != "DEDICATED":
        raise GenerationManifestError("concurrent auto live requires dedicated account ownership")
    _required_bool(ownership, "external_or_manual_position_halts", True, draft=draft)

    host = sections["host"]
    _label(host["host_profile_label"], draft=draft)
    _label(host["supervisor_profile_label"], draft=draft)
    _required_bool(host, "clock_monitor_required", True, draft=draft)
    _required_bool(host, "operator_kill_required", True, draft=draft)

    credential = sections["credential_permission"]
    _label(credential["credential_profile_label"], draft=draft)
    _label(credential["permission_profile_label"], draft=draft)
    _required_bool(credential, "env_fallback_allowed", False, draft=draft)
    _required_bool(credential, "raw_secret_logging_allowed", False, draft=draft)

    safety = sections["safety"]
    for key in SECTION_KEYS["safety"]:
        _required_bool(safety, key, False, draft=draft)

    return root


def canonical_manifest_digest(manifest: dict[str, Any]) -> str:
    """Return a deterministic digest for an already validated frozen manifest."""

    encoded = json.dumps(
        manifest,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def load_local_manifest(path: Path) -> Any:
    """Read a bounded regular JSON file without following symlinks."""

    try:
        info = path.lstat()
    except OSError as error:
        raise GenerationManifestError("manifest file is unavailable") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise GenerationManifestError("manifest path must be a regular non-symlink file")
    if info.st_size <= 0 or info.st_size > MAX_MANIFEST_BYTES:
        raise GenerationManifestError("manifest file size is invalid")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GenerationManifestError("manifest JSON is invalid") from error


def _safe_projection(manifest: dict[str, Any], *, mode: str) -> dict[str, Any]:
    projection = {
        "validation_status": "DRAFT_VALID_NOT_FROZEN"
        if mode == "draft"
        else "FROZEN_VALID_NOT_ACTIVATED",
        "manifest_schema": manifest["manifest_schema"],
        "manifest_status": manifest["manifest_status"],
        "generation_label": manifest["identity"]["generation_label"],
        "strategy_version": manifest["identity"]["strategy_version"],
        "selected_horizon": manifest["signal"]["selected_horizon"],
        "execution_profile_label": manifest["entry"]["execution_profile_label"],
        "execution_profile_hash_bound": not _is_pending(
            manifest["entry"]["execution_profile_hash"]
        ),
        "actual_post_authorized": False,
        "broker_read_performed": False,
        "broker_write_performed": False,
        "credential_read_performed": False,
        "live_ready": False,
        "unattended_live_supported": False,
    }
    if mode == "frozen":
        projection["manifest_digest"] = canonical_manifest_digest(manifest)
    return projection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate one local H-11 auto generation manifest without activation"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--mode", choices=("draft", "frozen"), required=True)
    args = parser.parse_args(argv)
    try:
        payload = load_local_manifest(args.manifest)
        manifest = validate_generation_manifest(payload, mode=args.mode)
    except GenerationManifestError as error:
        print(f"MANIFEST_BLOCKED: {error}")
        return 2
    print(json.dumps(_safe_projection(manifest, mode=args.mode), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
