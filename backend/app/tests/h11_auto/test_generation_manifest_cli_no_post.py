from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

import scripts.h11_auto_generation_manifest as manifest_module
from scripts.h11_auto_generation_manifest import (
    DRAFT_SCHEMA,
    DRAFT_STATUS,
    FROZEN_SCHEMA,
    FROZEN_STATUS,
    MAX_MANIFEST_BYTES,
    GenerationManifestError,
    canonical_manifest_digest,
    load_local_manifest,
    main,
    validate_generation_manifest,
)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
REPO_ROOT = Path(__file__).resolve().parents[4]


def _frozen_manifest() -> dict[str, object]:
    return {
        "manifest_schema": FROZEN_SCHEMA,
        "manifest_status": FROZEN_STATUS,
        "identity": {
            "generation_label": "H11_AUTO_30M_20260715_G001",
            "project": "H11_AUTO_PARALLEL",
            "strategy_version": "SHORT_V1",
            "implementation_digest": HASH_A,
        },
        "signal": {
            "selected_horizon": "30m",
            "signal_config_hash": HASH_B,
            "buy_threshold": "0.58",
            "sell_threshold": "0.42",
            "formal_only": True,
            "rolling_allowed": False,
            "h24_allowed": False,
        },
        "data_clock": {
            "source_profile_label": "FORMAL_M1_V1",
            "finalized_m1_required": True,
            "finalization_margin_seconds": 3,
            "maximum_m1_age_seconds": 90,
            "maximum_ticker_age_seconds": 15,
            "maximum_clock_skew_seconds": 5,
            "missed_signal_backfill_allowed": False,
        },
        "position": {
            "symbol": "USD_JPY",
            "quantity_units": 10_000,
            "maximum_open_positions": 1,
            "maximum_entries_per_jst_day": 1,
            "scale_in_allowed": False,
            "hedging_allowed": False,
        },
        "risk": {
            "policy_label": "H11_AUTO_INITIAL_MINIMUM_LIVE_V1",
            "per_trade_loss_bound_jpy": 5_000,
            "daily_loss_limit_jpy": 10_000,
            "monthly_loss_limit_jpy": 50_000,
            "maximum_consecutive_losses": 5,
            "automatic_resume_after_stop": False,
        },
        "entry": {
            "execution_profile_label": "TEST_ATOMIC_PROFILE",
            "execution_profile_hash": HASH_A,
            "entry_style": "IMMEDIATE_ENTRY",
            "short_pending_expiry_or_no_pending_entry_required": True,
            "full_fill_or_atomic_protection_size_match_required": True,
            "server_side_stop_required": True,
            "server_side_take_profit_required": True,
            "maximum_attempts_per_intent": 1,
            "retry_allowed": False,
            "repost_allowed": False,
        },
        "exit": {
            "exit_profile_label": "TEST_POSITION_SPECIFIC_EXIT",
            "position_specific_route_required": True,
            "generic_close_allowed": False,
            "opposite_entry_as_exit_allowed": False,
            "maximum_attempts_per_intent": 1,
            "retry_allowed": False,
            "repost_allowed": False,
            "stop_loss_contract": "TEST_SERVER_STOP",
            "take_profit_contract": "TEST_SERVER_TAKE",
            "maximum_hold_seconds": 1_800,
            "formal_edge_exit_enabled": False,
        },
        "reconciliation": {
            "boot_required": True,
            "before_entry_required": True,
            "after_entry_required": True,
            "periodic_position_monitor_required": True,
            "before_exit_required": True,
            "after_exit_required": True,
            "after_websocket_reconnect_required": True,
            "after_process_restart_required": True,
            "maximum_age_seconds": 15,
            "unknown_result_halts": True,
        },
        "dead_man": {
            "policy_label": "H11_AUTO_DEAD_MAN_V1",
            "heartbeat_interval_seconds": 15,
            "maximum_heartbeat_age_seconds": 60,
            "automatic_resume": False,
        },
        "notification": {
            "primary_profile_label": "PRIMARY_ACK_V1",
            "secondary_profile_label": "SECONDARY_INDEPENDENT_V1",
            "entry_requires_primary_ready": True,
            "delivery_failure_blocks_new_entry": True,
        },
        "ownership": {
            "account_mode": "DEDICATED",
            "external_or_manual_position_halts": True,
        },
        "host": {
            "host_profile_label": "DEDICATED_HOST_V1",
            "supervisor_profile_label": "SUPERVISOR_V1",
            "clock_monitor_required": True,
            "operator_kill_required": True,
        },
        "credential_permission": {
            "credential_profile_label": "SEALED_AUTO_CREDENTIAL_V1",
            "permission_profile_label": "MINIMUM_PROFILE_V1",
            "env_fallback_allowed": False,
            "raw_secret_logging_allowed": False,
        },
        "safety": {
            "actual_post_authorized": False,
            "live_ready": False,
            "unattended_live_supported": False,
        },
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_frozen_manifest_validates_and_hash_is_deterministic() -> None:
    manifest = _frozen_manifest()
    validated = validate_generation_manifest(manifest, mode="frozen")
    first = canonical_manifest_digest(validated)
    reordered = json.loads(json.dumps(manifest, sort_keys=False))
    second = canonical_manifest_digest(validate_generation_manifest(reordered, mode="frozen"))
    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == 71


def test_execution_profile_hash_is_required_and_content_bound() -> None:
    manifest = _frozen_manifest()
    original = canonical_manifest_digest(
        validate_generation_manifest(manifest, mode="frozen")
    )
    manifest["entry"]["execution_profile_hash"] = HASH_B  # type: ignore[index]
    changed = canonical_manifest_digest(
        validate_generation_manifest(manifest, mode="frozen")
    )
    assert changed != original


def test_frozen_execution_profile_hash_must_be_canonical_sha256() -> None:
    manifest = _frozen_manifest()
    manifest["entry"]["execution_profile_hash"] = "TEST_ATOMIC_PROFILE"  # type: ignore[index]
    with pytest.raises(GenerationManifestError, match="SHA-256"):
        validate_generation_manifest(manifest, mode="frozen")


def test_draft_accepts_pending_but_frozen_rejects_it() -> None:
    manifest = _frozen_manifest()
    manifest["manifest_schema"] = DRAFT_SCHEMA
    manifest["manifest_status"] = DRAFT_STATUS
    manifest["entry"]["execution_profile_label"] = "PENDING_GMO_RESPONSE"  # type: ignore[index]
    manifest["entry"]["execution_profile_hash"] = "PENDING_GMO_RESPONSE"  # type: ignore[index]
    validate_generation_manifest(manifest, mode="draft")
    manifest["manifest_schema"] = FROZEN_SCHEMA
    manifest["manifest_status"] = FROZEN_STATUS
    with pytest.raises(GenerationManifestError, match="pending"):
        validate_generation_manifest(manifest, mode="frozen")


@pytest.mark.parametrize(
    ("section", "key", "unsafe"),
    [
        ("signal", "rolling_allowed", True),
        ("signal", "h24_allowed", True),
        ("position", "maximum_open_positions", 2),
        ("position", "maximum_entries_per_jst_day", 2),
        ("position", "scale_in_allowed", True),
        ("position", "hedging_allowed", True),
        ("entry", "maximum_attempts_per_intent", 2),
        ("entry", "retry_allowed", True),
        ("entry", "repost_allowed", True),
        ("exit", "generic_close_allowed", True),
        ("exit", "opposite_entry_as_exit_allowed", True),
        ("exit", "maximum_attempts_per_intent", 2),
        ("dead_man", "automatic_resume", True),
        ("credential_permission", "env_fallback_allowed", True),
        ("credential_permission", "raw_secret_logging_allowed", True),
        ("safety", "actual_post_authorized", True),
        ("safety", "live_ready", True),
        ("safety", "unattended_live_supported", True),
    ],
)
def test_frozen_safety_invariants_cannot_be_weakened(
    section: str, key: str, unsafe: object
) -> None:
    manifest = _frozen_manifest()
    manifest[section][key] = unsafe  # type: ignore[index]
    with pytest.raises(GenerationManifestError):
        validate_generation_manifest(manifest, mode="frozen")


def test_unknown_or_sensitive_field_is_rejected() -> None:
    manifest = _frozen_manifest()
    manifest["entry"]["raw_response"] = "forbidden"  # type: ignore[index]
    with pytest.raises(GenerationManifestError, match="schema mismatch"):
        validate_generation_manifest(manifest, mode="frozen")


def test_bool_is_not_accepted_as_integer() -> None:
    manifest = _frozen_manifest()
    manifest["position"]["quantity_units"] = True  # type: ignore[index]
    with pytest.raises(GenerationManifestError, match="integer"):
        validate_generation_manifest(manifest, mode="frozen")


@pytest.mark.parametrize(
    ("buy", "sell"),
    [("0.50", "0.42"), ("0.58", "0.50"), ("NaN", "0.42"), ("0.580", "0.42")],
)
def test_threshold_contract_is_fail_closed(buy: str, sell: str) -> None:
    manifest = _frozen_manifest()
    manifest["signal"]["buy_threshold"] = buy  # type: ignore[index]
    manifest["signal"]["sell_threshold"] = sell  # type: ignore[index]
    with pytest.raises(GenerationManifestError):
        validate_generation_manifest(manifest, mode="frozen")


def test_risk_limits_must_be_monotonic() -> None:
    manifest = _frozen_manifest()
    manifest["risk"]["daily_loss_limit_jpy"] = 1_000  # type: ignore[index]
    with pytest.raises(GenerationManifestError, match="risk limits"):
        validate_generation_manifest(manifest, mode="frozen")


def test_dead_man_maximum_age_must_exceed_interval() -> None:
    manifest = _frozen_manifest()
    manifest["dead_man"]["maximum_heartbeat_age_seconds"] = 15  # type: ignore[index]
    with pytest.raises(GenerationManifestError, match="dead-man"):
        validate_generation_manifest(manifest, mode="frozen")


def test_concurrent_live_manifest_requires_dedicated_account() -> None:
    manifest = _frozen_manifest()
    manifest["ownership"]["account_mode"] = "SHARED"  # type: ignore[index]
    with pytest.raises(GenerationManifestError, match="dedicated"):
        validate_generation_manifest(manifest, mode="frozen")


def test_regular_json_file_only(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_json(manifest_path, _frozen_manifest())
    assert load_local_manifest(manifest_path)["manifest_schema"] == FROZEN_SCHEMA
    symlink = tmp_path / "manifest-link.json"
    symlink.symlink_to(manifest_path)
    with pytest.raises(GenerationManifestError, match="regular non-symlink"):
        load_local_manifest(symlink)


def test_oversized_manifest_file_is_rejected(tmp_path: Path) -> None:
    manifest_path = tmp_path / "oversized.json"
    manifest_path.write_bytes(b"{" + b" " * MAX_MANIFEST_BYTES + b"}")
    with pytest.raises(GenerationManifestError, match="file size"):
        load_local_manifest(manifest_path)


def test_nonfinite_json_number_is_rejected() -> None:
    manifest = _frozen_manifest()
    manifest["risk"]["monthly_loss_limit_jpy"] = float("nan")  # type: ignore[index]
    with pytest.raises(GenerationManifestError, match="non-finite"):
        validate_generation_manifest(manifest, mode="frozen")


def test_cli_outputs_safe_projection_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_json(manifest_path, _frozen_manifest())
    assert main(["--manifest", str(manifest_path), "--mode", "frozen"]) == 0
    output = capsys.readouterr().out
    projected = json.loads(output)
    assert projected["validation_status"] == "FROZEN_VALID_NOT_ACTIVATED"
    assert projected["actual_post_authorized"] is False
    assert projected["execution_profile_hash_bound"] is True
    assert projected["broker_read_performed"] is False
    assert projected["broker_write_performed"] is False
    assert projected["credential_read_performed"] is False
    assert "quantity_units" not in output
    assert "loss_limit" not in output
    assert "credential_profile_label" not in output


def test_cli_blocks_invalid_manifest_without_echoing_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = _frozen_manifest()
    manifest["unexpected_secret_field"] = "DO_NOT_ECHO"
    manifest_path = tmp_path / "manifest.json"
    _write_json(manifest_path, manifest)
    assert main(["--manifest", str(manifest_path), "--mode", "frozen"]) == 2
    output = capsys.readouterr().out
    assert output.startswith("MANIFEST_BLOCKED:")
    assert "DO_NOT_ECHO" not in output


def test_draft_cli_never_outputs_frozen_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = _frozen_manifest()
    manifest["manifest_schema"] = DRAFT_SCHEMA
    manifest["manifest_status"] = DRAFT_STATUS
    manifest["entry"]["execution_profile_label"] = "PENDING_GMO_RESPONSE"  # type: ignore[index]
    manifest["entry"]["execution_profile_hash"] = "PENDING_GMO_RESPONSE"  # type: ignore[index]
    manifest_path = tmp_path / "draft.json"
    _write_json(manifest_path, manifest)
    assert main(["--manifest", str(manifest_path), "--mode", "draft"]) == 0
    projected = json.loads(capsys.readouterr().out)
    assert projected["validation_status"] == "DRAFT_VALID_NOT_FROZEN"
    assert "manifest_digest" not in projected


def test_script_imports_only_offline_standard_library_modules() -> None:
    source_path = Path(manifest_module.__file__)
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
        "decimal",
        "hashlib",
        "json",
        "math",
        "pathlib",
        "re",
        "stat",
        "typing",
    }


def test_digest_changes_when_frozen_policy_changes() -> None:
    base = _frozen_manifest()
    changed = copy.deepcopy(base)
    changed["risk"]["monthly_loss_limit_jpy"] = 40_000  # type: ignore[index]
    assert canonical_manifest_digest(validate_generation_manifest(base, mode="frozen")) != (
        canonical_manifest_digest(validate_generation_manifest(changed, mode="frozen"))
    )


def test_repository_draft_template_is_machine_valid_but_not_frozen() -> None:
    template = load_local_manifest(
        REPO_ROOT / "docs/templates/h11_auto_generation_manifest.draft.json"
    )
    validate_generation_manifest(template, mode="draft")
    with pytest.raises(GenerationManifestError):
        validate_generation_manifest(template, mode="frozen")
