from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

import scripts.h11_auto_profile_freeze as freeze_module
from scripts.h11_auto_profile_acceptance import (
    SCHEMA as EVIDENCE_SCHEMA,
)
from scripts.h11_auto_profile_acceptance import (
    Capability,
    ProfileVerdict,
    evaluate_profile_evidence,
)
from scripts.h11_auto_profile_freeze import (
    DRAFT_SCHEMA,
    DRAFT_STATUS,
    FROZEN_SCHEMA,
    FROZEN_STATUS,
    MAX_PROFILE_BYTES,
    ProfileFreezeError,
    load_local_profile,
    main,
    validate_and_bind_profile,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _accepted_evidence(*, immediate: bool = False) -> dict[str, object]:
    yes = Capability.CONFIRMED_YES.value
    no = Capability.CONFIRMED_NO.value
    return {
        "schema": EVIDENCE_SCHEMA,
        "profile_label": "TEST_SAFE_PROFILE",
        "capabilities": {
            "short_pending_expiry": no if immediate else yes,
            "no_pending_entry": yes if immediate else no,
            "full_fill_or_none": yes,
            "atomic_protection_with_entry": no,
            "protection_size_matches_actual_fill": no,
            "server_side_stop_loss": yes,
            "server_side_take_profit": yes,
            "position_specific_settlement": yes,
            "authoritative_read_after_unknown": yes,
            "broker_state_readable": yes,
            "protected_size_readable": yes,
            "excess_size_can_reverse_position": no,
            "minimum_permission_known": yes,
            "private_get_rate_limit_known": yes,
            "private_post_rate_limit_known": yes,
            "tos_automatic_trading_allowed": yes,
            "fee_model_known": yes,
            "ownership_isolation_supported": yes,
        },
        "official_evidence_refs": ["GMO_OFFICIAL_RESPONSE_TEST"],
    }


def _frozen_profile(
    evidence: dict[str, object], *, immediate: bool = False
) -> dict[str, object]:
    return {
        "profile_schema": FROZEN_SCHEMA,
        "profile_status": FROZEN_STATUS,
        "profile_label": evidence["profile_label"],
        "broker_label": "GMO_FX",
        "entry_mode": "IMMEDIATE" if immediate else "PENDING",
        "pending_expiry_contract": "NO_PENDING_ENTRY" if immediate else "SHORT_EXPIRY_V1",
        "fill_atomicity_contract": "FULL_FILL_OR_NONE_V1",
        "protection_creation_contract": "ATOMIC_SERVER_PROTECTION_V1",
        "protection_size_contract": "EXACT_ACTUAL_FILL_V1",
        "server_side_stop_loss": True,
        "server_side_take_profit": True,
        "position_specific_settlement": True,
        "authoritative_read_after_unknown": True,
        "ownership_contract": "DEDICATED_ACCOUNT",
        "minimum_permission_contract": "MINIMUM_PERMISSION_V1",
        "rate_limit_contract": "OFFICIAL_RATE_LIMIT_V1",
        "fee_and_holding_cost_contract": "OFFICIAL_COST_MODEL_V1",
        "official_evidence_refs": evidence["official_evidence_refs"],
        "accepted_evidence_digest": evaluate_profile_evidence(evidence).evidence_digest,
        "operator_approval_ref": "OPERATOR_PROFILE_APPROVAL_TEST",
        "safety": {
            "actual_adapter_authorized": False,
            "broker_read_authorized": False,
            "broker_write_authorized": False,
            "credential_read_authorized": False,
            "actual_post_authorized": False,
            "live_ready": False,
            "unattended_live_supported": False,
        },
    }


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("immediate", [False, True])
def test_accepted_evidence_can_freeze_matching_profile(immediate: bool) -> None:
    evidence = _accepted_evidence(immediate=immediate)
    profile = _frozen_profile(evidence, immediate=immediate)
    validated, digest, verdict = validate_and_bind_profile(
        profile, evidence, mode="frozen"
    )
    assert validated == profile
    assert digest.startswith("sha256:")
    assert verdict is ProfileVerdict.ACCEPT_FOR_DISABLED_ADAPTER_DESIGN


def test_profile_digest_is_deterministic_and_content_bound() -> None:
    evidence = _accepted_evidence()
    profile = _frozen_profile(evidence)
    _, first, _ = validate_and_bind_profile(profile, evidence, mode="frozen")
    reordered = json.loads(json.dumps(profile, sort_keys=True))
    _, second, _ = validate_and_bind_profile(reordered, evidence, mode="frozen")
    changed = copy.deepcopy(profile)
    changed["rate_limit_contract"] = "OFFICIAL_RATE_LIMIT_V2"
    _, third, _ = validate_and_bind_profile(changed, evidence, mode="frozen")
    assert first == second
    assert first != third


def test_unaccepted_evidence_cannot_freeze_profile() -> None:
    evidence = _accepted_evidence()
    evidence["capabilities"]["server_side_stop_loss"] = (  # type: ignore[index]
        Capability.NOT_ANSWERED.value
    )
    profile = _frozen_profile(_accepted_evidence())
    with pytest.raises(ProfileFreezeError, match="not accepted"):
        validate_and_bind_profile(profile, evidence, mode="frozen")


def test_evidence_digest_and_refs_must_match_exactly() -> None:
    evidence = _accepted_evidence()
    profile = _frozen_profile(evidence)
    profile["accepted_evidence_digest"] = "sha256:" + "a" * 64
    with pytest.raises(ProfileFreezeError, match="digest does not match"):
        validate_and_bind_profile(profile, evidence, mode="frozen")
    profile = _frozen_profile(evidence)
    profile["official_evidence_refs"] = ["DIFFERENT_OFFICIAL_REF"]
    with pytest.raises(ProfileFreezeError, match="refs do not match"):
        validate_and_bind_profile(profile, evidence, mode="frozen")


def test_entry_mode_requires_matching_capability_path() -> None:
    evidence = _accepted_evidence()
    profile = _frozen_profile(evidence)
    profile["entry_mode"] = "IMMEDIATE"
    with pytest.raises(ProfileFreezeError, match="immediate entry mode"):
        validate_and_bind_profile(profile, evidence, mode="frozen")


@pytest.mark.parametrize(
    "key",
    [
        "server_side_stop_loss",
        "server_side_take_profit",
        "position_specific_settlement",
        "authoritative_read_after_unknown",
    ],
)
def test_frozen_required_profile_capability_must_be_true(key: str) -> None:
    evidence = _accepted_evidence()
    profile = _frozen_profile(evidence)
    profile[key] = False
    with pytest.raises(ProfileFreezeError, match="required profile capability"):
        validate_and_bind_profile(profile, evidence, mode="frozen")


@pytest.mark.parametrize(
    "key",
    [
        "actual_adapter_authorized",
        "broker_read_authorized",
        "broker_write_authorized",
        "credential_read_authorized",
        "actual_post_authorized",
        "live_ready",
        "unattended_live_supported",
    ],
)
def test_profile_cannot_grant_authority(key: str) -> None:
    evidence = _accepted_evidence()
    profile = _frozen_profile(evidence)
    profile["safety"][key] = True  # type: ignore[index]
    with pytest.raises(ProfileFreezeError, match="must remain false"):
        validate_and_bind_profile(profile, evidence, mode="frozen")


def test_frozen_profile_rejects_pending_and_unknown_fields_without_echo() -> None:
    evidence = _accepted_evidence()
    profile = _frozen_profile(evidence)
    profile["minimum_permission_contract"] = "PENDING_SECRET_VALUE"
    with pytest.raises(ProfileFreezeError, match="pending") as captured:
        validate_and_bind_profile(profile, evidence, mode="frozen")
    assert "SECRET_VALUE" not in str(captured.value)
    profile = _frozen_profile(evidence)
    profile["raw_response"] = "DO_NOT_ECHO"
    with pytest.raises(ProfileFreezeError, match="schema mismatch") as captured:
        validate_and_bind_profile(profile, evidence, mode="frozen")
    assert "DO_NOT_ECHO" not in str(captured.value)


def test_draft_template_validates_but_never_freezes_pending_evidence() -> None:
    profile = load_local_profile(
        REPO_ROOT / "docs/templates/h11_auto_execution_profile.draft.json"
    )
    evidence = json.loads(
        (
            REPO_ROOT
            / "docs/templates/h11_auto_execution_profile_evidence.draft.json"
        ).read_text(encoding="utf-8")
    )
    validated, _, verdict = validate_and_bind_profile(profile, evidence, mode="draft")
    assert validated["profile_schema"] == DRAFT_SCHEMA
    assert validated["profile_status"] == DRAFT_STATUS
    assert verdict is ProfileVerdict.NEEDS_FOLLOWUP
    profile["profile_schema"] = FROZEN_SCHEMA
    profile["profile_status"] = FROZEN_STATUS
    with pytest.raises(ProfileFreezeError):
        validate_and_bind_profile(profile, evidence, mode="frozen")


def test_regular_non_symlink_bounded_file_only(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    _write(path, _frozen_profile(_accepted_evidence()))
    assert load_local_profile(path)["profile_schema"] == FROZEN_SCHEMA
    link = tmp_path / "profile-link.json"
    link.symlink_to(path)
    with pytest.raises(ProfileFreezeError, match="regular non-symlink"):
        load_local_profile(link)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"{" + b" " * MAX_PROFILE_BYTES + b"}")
    with pytest.raises(ProfileFreezeError, match="file size"):
        load_local_profile(oversized)


def test_cli_outputs_safe_projection_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    evidence = _accepted_evidence()
    profile_path = tmp_path / "profile.json"
    evidence_path = tmp_path / "evidence.json"
    _write(profile_path, _frozen_profile(evidence))
    _write(evidence_path, evidence)
    assert (
        main(
            [
                "--profile",
                str(profile_path),
                "--evidence",
                str(evidence_path),
                "--mode",
                "frozen",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    projected = json.loads(output)
    assert projected["profile_digest"].startswith("sha256:")
    assert projected["validation_status"].endswith("REVIEW_ONLY")
    assert projected["actual_post_authorized"] is False
    assert "official_evidence_refs" not in output
    assert "operator_approval_ref" not in output
    assert "minimum_permission_contract" not in output


def test_script_imports_only_offline_modules() -> None:
    source_path = Path(freeze_module.__file__)
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
        "hashlib",
        "json",
        "pathlib",
        "re",
        "scripts",
        "stat",
        "typing",
    }
