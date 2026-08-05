"""Acceptance tests for P0 (VETO remediation) — written BEFORE implementation.

Authored by the reviewer, not the implementer (see the operating rules in
docs/H11_V4_COMPLETION_PLAN_HANDOFF.md §1). Fake-only: no broker access, no
credentials, no LaunchAgent interaction, no notification, no network.

Covers P0-a .. P0-d. P0-e (restoring the ARM control-API behaviour tests) is
the reviewer's own task, and P0-f is documentation only, so neither is
asserted here.

The single most important property this file protects
-----------------------------------------------------
A latched persistent HALT must NOT be escapable by re-baking a digest.

Twice already, a generation latched ``*_INITIAL_TRANSACTION_UNKNOWN`` and the
project moved on by minting a new generation digest — which silently re-keys
the runtime state root and orphans the halt (G074 at
``generation-ce098ee8…``, G075 at ``generation-f0e74bf0…``, both still on
disk, both still unresolved). That escape hatch is what P0-b closes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_g075_runtime import (
    G075_GENERATION_LABEL,
    G075_PERSISTENT_HALT_FILE,
    G075Error,
    _canonical_hash,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest

REPOSITORY = Path(__file__).resolve().parents[4]
TEMPLATES = REPOSITORY / "docs/templates"

CANONICAL = TEMPLATES / "h11_v4_gmo_frozen_generation.json"
G075_TEMPLATE = TEMPLATES / "h11_v4_g075_frozen_generation.json"
EVIDENCE = TEMPLATES / "h11_v4_g075_runtime_commissioning_evidence.json"
ATTESTATION = TEMPLATES / "h11_v4_g075_independent_review_attestation.json"

# The generation digest G075 carried before the 5df62a3 re-bake. Its runtime
# state root holds the unresolved G075_INITIAL_TRANSACTION_UNKNOWN halt.
PREDECESSOR_DIGEST = (
    "sha256:f0e74bf0f3ef114db3474df4aa7348edf112a5c8534d55121f730173ea868c0d"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_digests() -> tuple[str, str]:
    reviewed = compute_reviewed_files_digest(repository=REPOSITORY)
    generation = load_v4_gmo_frozen_generation(
        repository=REPOSITORY, implementation_digest=reviewed
    )
    return reviewed, generation.digest


# ------------------------------------------------------------------ P0-a


def test_manifest_binds_the_real_artifact_hashes() -> None:
    """The half-installed forgery must be gone.

    5df62a3 reverted the two review artifacts but left the manifest's
    binding digests pointing at the *forged* versions, pre-satisfying two of
    the five gate conditions.
    """
    manifest = _load(G075_TEMPLATE)
    for artifact_path, field in (
        (EVIDENCE, "runtime_commissioning_evidence_digest"),
        (ATTESTATION, "successor_halt_release_digest"),
    ):
        artifact = _load(artifact_path)
        real = _canonical_hash(
            {k: v for k, v in artifact.items() if k != "artifact_digest"}
        )
        assert artifact["artifact_digest"] == real, (
            f"{artifact_path.name}: the artifact's own digest is inconsistent"
        )
        assert manifest[field] == real, (
            f"{field}: manifest does not bind the real artifact hash"
        )


def test_canonical_and_template_stay_identical() -> None:
    assert _load(CANONICAL) == _load(G075_TEMPLATE)


def test_review_artifacts_were_not_touched() -> None:
    """P0-a fixes the manifest side only. Re-baking the artifacts themselves
    would transplant a stale CLEAR verdict onto unreviewed code."""
    reviewed, generation = _current_digests()
    for path in (EVIDENCE, ATTESTATION):
        payload = _load(path)
        assert payload["reviewed_files_digest"] != reviewed, path.name
        assert payload["generation_digest"] != generation, path.name


def test_review_gate_still_refuses() -> None:
    """Until a genuine three-lane review of this tree happens, the gate must
    refuse. Making it pass is out of scope for P0 and forbidden."""
    from app.services.h11_v4_g075_runtime import verify_g075_review_artifacts

    reviewed, generation = _current_digests()
    with pytest.raises(G075Error, match="G075_REVIEW_ARTIFACT"):
        verify_g075_review_artifacts(
            repository=REPOSITORY,
            generation_digest=generation,
            reviewed_files_digest=reviewed,
        )


# ------------------------------------------------------------------ P0-b


def test_predecessor_fields_are_restored() -> None:
    for path in (CANONICAL, G075_TEMPLATE):
        payload = _load(path)
        assert payload.get("predecessor_generation_digest") == PREDECESSOR_DIGEST, (
            f"{path.name}: predecessor_generation_digest missing or wrong"
        )
        assert payload.get("predecessor_initial_activation_unknown") is True, (
            f"{path.name}: the unresolved initial-activation UNKNOWN is not recorded"
        )


def test_digests_reached_a_fixed_point_after_the_predecessor_fields() -> None:
    """Unlike P0-a, these fields are NOT nulled before hashing, so adding them
    moves both digests. Implementation must iterate to convergence."""
    reviewed, _ = _current_digests()
    for path in (CANONICAL, G075_TEMPLATE):
        assert _load(path)["implementation_digest"] == reviewed, path.name


def test_the_orphaned_predecessor_halt_is_still_on_disk() -> None:
    """Guard against 'resolving' the finding by deleting the evidence."""
    root = v4_gmo_runtime_state_root(
        repository=REPOSITORY, generation_digest=PREDECESSOR_DIGEST
    )
    halt = root / G075_PERSISTENT_HALT_FILE
    assert halt.is_file(), "the predecessor halt marker must not be deleted"
    payload = _load(halt)
    assert payload["status"] == "HALTED"
    assert payload["reason"] == "G075_INITIAL_TRANSACTION_UNKNOWN"
    # It never actually reached the broker; the halt is an internal
    # misclassification (see P1 R1), which is why it must not be silently
    # discharged.
    assert payload["actual_post_count"] == 0
    assert payload["broker_write"] is False


def test_predecessor_halt_blocks_startup_even_when_current_root_is_clean(
    tmp_path: Path,
) -> None:
    """The core of P0-b: a halt latched under the PREVIOUS digest must still
    block, so that re-baking a digest is not an escape hatch.

    The implementation must expose a callable that performs this check. It
    should accept a repository, the current state root (or generation digest)
    and the predecessor generation digest, and raise a G075Error whose label
    contains PREDECESSOR when the predecessor root holds an unresolved halt.
    """
    from app.services.h11_v4_g075_runtime import require_g075_predecessor_halt_clear

    # Current root: clean. Predecessor root: halted.
    current_root = tmp_path / "current"
    current_root.mkdir()
    predecessor_root = v4_gmo_runtime_state_root(
        repository=tmp_path, generation_digest=PREDECESSOR_DIGEST
    )
    predecessor_root.mkdir(parents=True)
    (predecessor_root / G075_PERSISTENT_HALT_FILE).write_text(
        json.dumps(
            {
                "status": "HALTED",
                "reason": "G075_INITIAL_TRANSACTION_UNKNOWN",
                "broker_post_count": 0,
                "actual_post_count": 0,
                "generation_label": G075_GENERATION_LABEL,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(G075Error, match="PREDECESSOR"):
        require_g075_predecessor_halt_clear(
            repository=tmp_path,
            predecessor_generation_digest=PREDECESSOR_DIGEST,
        )


def test_predecessor_check_passes_when_predecessor_is_clean(tmp_path: Path) -> None:
    from app.services.h11_v4_g075_runtime import require_g075_predecessor_halt_clear

    v4_gmo_runtime_state_root(
        repository=tmp_path, generation_digest=PREDECESSOR_DIGEST
    ).mkdir(parents=True)
    require_g075_predecessor_halt_clear(
        repository=tmp_path,
        predecessor_generation_digest=PREDECESSOR_DIGEST,
    )


def test_predecessor_check_is_a_noop_without_a_predecessor(tmp_path: Path) -> None:
    from app.services.h11_v4_g075_runtime import require_g075_predecessor_halt_clear

    require_g075_predecessor_halt_clear(
        repository=tmp_path, predecessor_generation_digest=None
    )


def test_predecessor_check_does_not_offer_a_release_path() -> None:
    """Clearing a halt is an operator decision and a separate design. P0 must
    not introduce any way to discharge one."""
    import app.services.h11_v4_g075_runtime as runtime

    source = Path(runtime.__file__).read_text(encoding="utf-8")
    for forbidden in ("def clear_g075_halt", "def release_g075_halt", ".unlink()"):
        assert forbidden not in source, f"a halt-release path appeared: {forbidden}"


# ------------------------------------------------------------------ P0-c


def test_monday_self_check_references_only_existing_files() -> None:
    import re

    script = REPOSITORY / "backend/scripts/h11_auto_v4_monday_self_check.py"
    source = script.read_text(encoding="utf-8")
    referenced = set(re.findall(r"\"(app/tests/[^\"]+\.py)\"", source))
    missing = sorted(
        path for path in referenced if not (REPOSITORY / "backend" / path).is_file()
    )
    assert missing == [], f"references deleted test files: {missing}"


def test_monday_self_check_knows_the_canonical_generation() -> None:
    script = REPOSITORY / "backend/scripts/h11_auto_v4_monday_self_check.py"
    source = script.read_text(encoding="utf-8")
    assert "G064_GENERATION_LABEL" not in source, "still pinned to a retired generation"
    assert "G075_GENERATION_LABEL" in source


def test_no_new_generation_label_literals_were_introduced() -> None:
    """Label literals drifting out of sync across files caused two prior
    VETOs. New code must import the canonical constant."""
    import re

    for relative in (
        "backend/scripts/h11_auto_v4_monday_self_check.py",
        "backend/app/h11_auto/v4_actual_preparation_guard.py",
    ):
        source = (REPOSITORY / relative).read_text(encoding="utf-8")
        assert not re.search(r'"H11_AUTO_30M_\d+_G075"', source), (
            f"{relative}: hardcoded G075 label; import G075_GENERATION_LABEL instead"
        )


# ------------------------------------------------------------------ P0-d


def test_preparation_gate_knows_the_canonical_generation() -> None:
    from app.h11_auto.v4_actual_preparation_guard import (
        _PREPARATION_KNOWN_GENERATION_LABELS,
    )

    assert G075_GENERATION_LABEL in _PREPARATION_KNOWN_GENERATION_LABELS


def test_preparation_gate_no_longer_rejects_on_generation_mismatch() -> None:
    """The gate may still refuse for other reasons (git state, digests, the
    predecessor halt) — those are correct. It must simply stop refusing
    *because it does not recognise the canonical generation*."""
    from app.h11_auto.v4_actual_preparation_guard import (
        V4ActualPreparationGuardError,
        load_external_preparation_gate,
    )

    try:
        load_external_preparation_gate(repository=REPOSITORY)
    except V4ActualPreparationGuardError as error:
        assert "PREPARATION_FROZEN_GENERATION_MISMATCH" not in str(error), (
            "the canonical generation is still unknown to the preparation gate"
        )


# ------------------------------------------------- global P0 invariants


def test_no_capability_flag_was_flipped() -> None:
    for path in (CANONICAL, G075_TEMPLATE):
        payload = _load(path)
        assert payload["actual_post_authorized"] is False, path.name
        assert payload["live_ready"] is False, path.name
        assert payload["unattended_live_supported"] is False, path.name


def test_trading_contract_is_untouched() -> None:
    payload = _load(CANONICAL)
    assert payload["symbol"] == "USD_JPY"
    assert payload["selected_horizon"] == "30m"
    assert payload["strategy_version"] == "SHORT_V1"
    assert payload["quantity_units"] == 1000
    assert payload["maximum_hold_seconds"] == 1800
    assert payload["maximum_entries_per_day"] == 30
    assert payload["per_trade_loss_bound_jpy"] == 5000
    assert payload["daily_loss_limit_jpy"] == 10000
    assert payload["monthly_loss_limit_jpy"] == 50000
    assert payload["maximum_consecutive_losses"] == 5


def test_generation_label_is_still_g075() -> None:
    assert _load(CANONICAL)["generation_label"] == G075_GENERATION_LABEL


def test_no_new_generation_was_created() -> None:
    """The churn rule: fixes happen inside G075, never by minting G076+."""
    offenders = sorted(
        path.name
        for path in TEMPLATES.glob("h11_v4_g0*_frozen_generation.json")
        if path.name > "h11_v4_g075_frozen_generation.json"
    )
    assert offenders == [], f"a new generation was created: {offenders}"
