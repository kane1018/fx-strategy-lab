from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

import scripts.h11_auto_profile_acceptance as profile_module
from scripts.h11_auto_profile_acceptance import (
    MAX_EVIDENCE_BYTES,
    SCHEMA,
    Capability,
    ProfileAcceptanceError,
    ProfileVerdict,
    evaluate_profile_evidence,
    load_local_evidence,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _accepted_payload() -> dict[str, object]:
    yes = Capability.CONFIRMED_YES.value
    return {
        "schema": SCHEMA,
        "profile_label": "TEST_ATOMIC_PROFILE",
        "capabilities": {
            "short_pending_expiry": yes,
            "no_pending_entry": Capability.CONFIRMED_NO.value,
            "full_fill_or_none": yes,
            "atomic_protection_with_entry": Capability.CONFIRMED_NO.value,
            "protection_size_matches_actual_fill": Capability.CONFIRMED_NO.value,
            "server_side_stop_loss": yes,
            "server_side_take_profit": yes,
            "position_specific_settlement": yes,
            "authoritative_read_after_unknown": yes,
            "broker_state_readable": yes,
            "protected_size_readable": yes,
            "excess_size_can_reverse_position": Capability.CONFIRMED_NO.value,
            "minimum_permission_known": yes,
            "private_get_rate_limit_known": yes,
            "private_post_rate_limit_known": yes,
            "tos_automatic_trading_allowed": yes,
            "fee_model_known": yes,
            "ownership_isolation_supported": yes,
        },
        "official_evidence_refs": ["GMO_SUPPORT_RESPONSE_20260715"],
    }


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_fully_confirmed_profile_is_accepted_for_disabled_design_only() -> None:
    result = evaluate_profile_evidence(_accepted_payload())
    assert result.verdict is ProfileVerdict.ACCEPT_FOR_DISABLED_ADAPTER_DESIGN
    assert result.blocking_codes == ()
    assert result.actual_adapter_authorized is False
    assert result.broker_read_authorized is False
    assert result.broker_write_authorized is False
    assert result.credential_read_authorized is False
    assert result.actual_post_authorized is False
    assert result.live_ready is False
    assert result.unattended_live_supported is False


def test_no_pending_entry_can_replace_short_expiry() -> None:
    payload = _accepted_payload()
    payload["capabilities"]["short_pending_expiry"] = Capability.CONFIRMED_NO.value  # type: ignore[index]
    payload["capabilities"]["no_pending_entry"] = Capability.CONFIRMED_YES.value  # type: ignore[index]
    assert (
        evaluate_profile_evidence(payload).verdict
        is ProfileVerdict.ACCEPT_FOR_DISABLED_ADAPTER_DESIGN
    )


def test_atomic_exact_protection_can_replace_full_fill_or_none() -> None:
    payload = _accepted_payload()
    payload["capabilities"]["full_fill_or_none"] = Capability.CONFIRMED_NO.value  # type: ignore[index]
    payload["capabilities"]["atomic_protection_with_entry"] = (  # type: ignore[index]
        Capability.CONFIRMED_YES.value
    )
    payload["capabilities"]["protection_size_matches_actual_fill"] = (  # type: ignore[index]
        Capability.CONFIRMED_YES.value
    )
    assert (
        evaluate_profile_evidence(payload).verdict
        is ProfileVerdict.ACCEPT_FOR_DISABLED_ADAPTER_DESIGN
    )


def test_both_fill_safety_paths_confirmed_no_rejects_profile() -> None:
    payload = _accepted_payload()
    payload["capabilities"]["full_fill_or_none"] = Capability.CONFIRMED_NO.value  # type: ignore[index]
    result = evaluate_profile_evidence(payload)
    assert result.verdict is ProfileVerdict.REJECT
    assert "FILL_OR_ATOMIC_PROTECTION_NOT_CONFIRMED" in result.blocking_codes


@pytest.mark.parametrize(
    "key",
    [
        "server_side_stop_loss",
        "server_side_take_profit",
        "position_specific_settlement",
        "authoritative_read_after_unknown",
        "broker_state_readable",
        "protected_size_readable",
        "minimum_permission_known",
        "private_get_rate_limit_known",
        "private_post_rate_limit_known",
        "tos_automatic_trading_allowed",
        "fee_model_known",
        "ownership_isolation_supported",
    ],
)
def test_direct_required_capability_confirmed_no_rejects(key: str) -> None:
    payload = _accepted_payload()
    payload["capabilities"][key] = Capability.CONFIRMED_NO.value  # type: ignore[index]
    assert evaluate_profile_evidence(payload).verdict is ProfileVerdict.REJECT


@pytest.mark.parametrize(
    "unknown", [Capability.AMBIGUOUS.value, Capability.NOT_ANSWERED.value]
)
def test_unanswered_required_capability_needs_followup(unknown: str) -> None:
    payload = _accepted_payload()
    payload["capabilities"]["server_side_stop_loss"] = unknown  # type: ignore[index]
    assert evaluate_profile_evidence(payload).verdict is ProfileVerdict.NEEDS_FOLLOWUP


def test_excess_size_reversal_yes_rejects_and_unknown_needs_followup() -> None:
    payload = _accepted_payload()
    payload["capabilities"]["excess_size_can_reverse_position"] = (  # type: ignore[index]
        Capability.CONFIRMED_YES.value
    )
    assert evaluate_profile_evidence(payload).verdict is ProfileVerdict.REJECT
    payload["capabilities"]["excess_size_can_reverse_position"] = (  # type: ignore[index]
        Capability.NOT_ANSWERED.value
    )
    assert evaluate_profile_evidence(payload).verdict is ProfileVerdict.NEEDS_FOLLOWUP


def test_missing_official_evidence_ref_needs_followup() -> None:
    payload = _accepted_payload()
    payload["official_evidence_refs"] = []
    result = evaluate_profile_evidence(payload)
    assert result.verdict is ProfileVerdict.NEEDS_FOLLOWUP
    assert result.blocking_codes == ("OFFICIAL_EVIDENCE_REFS_MISSING",)


def test_unknown_or_sensitive_field_is_rejected_without_echo() -> None:
    payload = _accepted_payload()
    payload["capabilities"]["raw_response"] = "SECRET_VALUE"  # type: ignore[index]
    with pytest.raises(ProfileAcceptanceError, match="schema mismatch") as captured:
        evaluate_profile_evidence(payload)
    assert "SECRET_VALUE" not in str(captured.value)


@pytest.mark.parametrize("invalid", [True, 1, "YES", "UNKNOWN"])
def test_capability_enum_is_exact(invalid: object) -> None:
    payload = _accepted_payload()
    payload["capabilities"]["server_side_stop_loss"] = invalid  # type: ignore[index]
    with pytest.raises(ProfileAcceptanceError, match="capability value"):
        evaluate_profile_evidence(payload)


def test_evidence_digest_changes_with_capability() -> None:
    base = _accepted_payload()
    changed = copy.deepcopy(base)
    changed["capabilities"]["short_pending_expiry"] = Capability.AMBIGUOUS.value  # type: ignore[index]
    assert evaluate_profile_evidence(base).evidence_digest != (
        evaluate_profile_evidence(changed).evidence_digest
    )


def test_regular_non_symlink_bounded_file_only(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    _write(path, _accepted_payload())
    assert load_local_evidence(path)["schema"] == SCHEMA
    link = tmp_path / "evidence-link.json"
    link.symlink_to(path)
    with pytest.raises(ProfileAcceptanceError, match="regular non-symlink"):
        load_local_evidence(link)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"{" + b" " * MAX_EVIDENCE_BYTES + b"}")
    with pytest.raises(ProfileAcceptanceError, match="file size"):
        load_local_evidence(oversized)


def test_cli_safe_output_and_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "evidence.json"
    _write(path, _accepted_payload())
    assert main(["--evidence", str(path)]) == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["verdict"] == "ACCEPT_FOR_DISABLED_ADAPTER_DESIGN"
    assert result["actual_adapter_authorized"] is False
    assert result["actual_post_authorized"] is False
    assert "official_evidence_refs" not in output
    assert "capabilities" not in output

    followup = _accepted_payload()
    followup["capabilities"]["server_side_stop_loss"] = Capability.NOT_ANSWERED.value  # type: ignore[index]
    _write(path, followup)
    assert main(["--evidence", str(path)]) == 3
    assert "NEEDS_FOLLOWUP" in capsys.readouterr().out


def test_script_imports_only_offline_standard_library_modules() -> None:
    source_path = Path(profile_module.__file__)
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
        "enum",
        "hashlib",
        "json",
        "pathlib",
        "re",
        "stat",
        "typing",
    }


def test_repository_evidence_template_is_valid_and_needs_followup() -> None:
    template = load_local_evidence(
        REPO_ROOT / "docs/templates/h11_auto_execution_profile_evidence.draft.json"
    )
    result = evaluate_profile_evidence(template)
    assert result.verdict is ProfileVerdict.NEEDS_FOLLOWUP
    assert result.actual_post_authorized is False
