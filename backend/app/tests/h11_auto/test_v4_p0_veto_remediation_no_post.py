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
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_g075_runtime import (
    G075_GENERATION_LABEL,
    G075_PERSISTENT_HALT_FILE,
    G075Error,
    G075ResidentSupervisor,
    G075SanitizedSnapshot,
    _canonical_hash,
    load_g075_release_capability_digest,
    run_g075_reconciliation_cycle_once,
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


def test_review_artifacts_still_bind_the_current_reviewed_digest() -> None:
    """The attestation must continue to bind the latest reviewed digest.

    2026-08-07、Phase E〜H の 3レーンレビューが CLEAR を確定し、operator の
    指示で binding フィールドを再束縛したため、artifacts は現行 reviewed
    digest を指す状態が正しい。コード変更でこの状態が崩れたら再レビュー要件で
    再束縛する。
    """
    reviewed, _generation = _current_digests()
    for path in (EVIDENCE, ATTESTATION):
        payload = _load(path)
        assert payload["reviewed_files_digest"] == reviewed, (
            f"{path.name} should match the latest independently reviewed digest"
        )


def test_review_gate_passes_when_latest_review_is_bound() -> None:
    """The gate passes for the post-Phase H rebound artifacts.

    When the reviewed and generation digests are bound to the current code state,
    ``verify_g075_review_artifacts`` must pass. If either binding is stale, this
    test will revert to raising ``G075_REVIEW_ARTIFACT`` and prompt a new review.
    """
    from app.services.h11_v4_g075_runtime import verify_g075_review_artifacts

    reviewed, generation = _current_digests()
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


def test_the_orphaned_predecessor_halt_evidence_survives_on_disk() -> None:
    """Guard against 'resolving' the finding by deleting the evidence.

    On 2026-08-06 the operator discharged this halt through the documented
    procedure (``h11_auto_v4_halt_discharge.py``), which renames the marker
    into a ``*-halt-discharged.<UTC>.json`` archive carrying the original
    payload verbatim plus a resolution record.  Deletion remains forbidden,
    so this test now accepts either state -- an undischarged marker, or an
    archive -- and in both cases still asserts the original halt content,
    including the fact that no order ever reached the broker.
    """
    root = v4_gmo_runtime_state_root(
        repository=REPOSITORY, generation_digest=PREDECESSOR_DIGEST
    )
    marker = root / G075_PERSISTENT_HALT_FILE
    archives = sorted(root.glob("g0*-halt-discharged.*.json"))
    assert marker.is_file() or archives, (
        "the predecessor halt evidence must not be deleted: neither the "
        f"marker {G075_PERSISTENT_HALT_FILE} nor a discharge archive exists "
        f"under {root}"
    )

    if marker.is_file():
        payload = _load(marker)
    else:
        archive = _load(archives[-1])
        payload = archive["original"]
        resolution = archive["resolution"]
        for field in (
            "operator",
            "reason",
            "broker_state_confirmation",
            "halt_content_sha256",
        ):
            assert isinstance(resolution.get(field), str) and resolution[field].strip(), (
                f"the discharge archive must record {field}"
            )

    assert payload["status"] == "HALTED"
    assert payload["reason"] == "G075_INITIAL_TRANSACTION_UNKNOWN"
    # It never actually reached the broker; the halt was an internal
    # misclassification (the false-UNKNOWN pattern rooted out in Phase C),
    # which is why the record has to survive its own discharge.
    assert payload["actual_post_count"] == 0
    assert payload["broker_write"] is False


def _write_orphaned_halt(repository: Path, *, generation_suffix: str, halt_file: str) -> Path:
    """Plant an unresolved halt under a generation root of a pseudo-repo."""
    root = (
        repository
        / "backend/market_data/h11_v4_gmo_actual_runtime"
        / f"generation-{generation_suffix}"
    )
    root.mkdir(parents=True, exist_ok=True)
    halt = root / halt_file
    halt.write_text(
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
    return halt


def _valid_flat_evidence(
    root: Path, generation_digest: str, reviewed_files_digest: str
) -> None:
    """Write a fresh flat reconciliation into the current state root so the
    supervisor's own root is otherwise clean."""

    class _FakeReconciler:
        def reconcile_once(
            self, *, cycle_id: str, now_utc: datetime
        ) -> G075SanitizedSnapshot:
            del cycle_id, now_utc
            return G075SanitizedSnapshot(
                latest_execution_count=0,
                open_position_count=0,
                active_order_count=0,
            )

    run_g075_reconciliation_cycle_once(
        state_root=root,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
        cycle_id="phase-a-cycle-1",
        reconciler=_FakeReconciler(),
        now_utc=datetime.now(UTC),
    )


def _bind_g075_capability(
    root: Path, generation_digest: str, reviewed_files_digest: str
) -> str:
    """Bind an ENABLED release capability into the current state root and
    return the release artifact digest the reader should return."""

    base = {
        "schema": "H11_V4_G075_SWITCH_CONTROL_CAPABILITY_V1",
        "generation_label": G075_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "reconciliation_artifact_digest": "sha256:" + "4" * 64,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "daily_authorization_required": False,
        "per_trade_confirmation_required": False,
        "status": "ENABLED",
    }
    digest = _canonical_hash(base)
    root.mkdir(parents=True, exist_ok=True)
    (root / "g075-switch-control-capability.json").write_text(
        json.dumps({**base, "artifact_digest": digest}), encoding="utf-8"
    )
    (root / "g075-release-capability.json").write_text(
        json.dumps({**base, "artifact_digest": digest}), encoding="utf-8"
    )
    outcome = {
        "status": "PASSED",
        "generation_label": G075_GENERATION_LABEL,
        "generation_digest": generation_digest,
        "reviewed_files_digest": reviewed_files_digest,
        "broker_post_count": 0,
    }
    (root / "g075-initial-activation.outcome.json").write_text(
        json.dumps({**outcome, "artifact_digest": _canonical_hash(outcome)}),
        encoding="utf-8",
    )
    (root / "g075-operation-60.result.json").write_text(
        json.dumps({key: value for key, value in outcome.items() if key != "broker_post_count"}),
        encoding="utf-8",
    )
    return digest


def test_supervisor_tick_refuses_on_any_unresolved_generation_halt(
    tmp_path: Path,
) -> None:
    """A-2a wiring: the resident supervisor must refuse (HALTED) when ANY
    generation root holds an unresolved halt, even when its own state root is
    clean.  The halt here lives in a *different* generation root and uses the
    G074-form filename to prove the scan is directory-wide, not keyed to the
    frozen manifest."""
    generation_digest = "sha256:" + "c" * 64
    reviewed_files_digest = "sha256:" + "d" * 64
    current = tmp_path / "current"
    _valid_flat_evidence(current, generation_digest, reviewed_files_digest)
    _write_orphaned_halt(
        tmp_path, generation_suffix="9" * 64, halt_file="g074-persistent-halt.json"
    )

    supervisor = G075ResidentSupervisor(
        state_root=current,
        generation_digest=generation_digest,
        reviewed_files_digest=reviewed_files_digest,
        repository=tmp_path,
    )
    status = supervisor.tick(now_utc=datetime.now(UTC), arm_on=False)
    assert status["persistent_halt"] is True
    assert status["effective_state"] == "HALTED"


def test_release_capability_digest_refuses_on_any_unresolved_halt(
    tmp_path: Path,
) -> None:
    """A-2a wiring: the release-capability reader must refuse while any
    generation root holds an unresolved halt.  The identical state root is
    accepted before the halt is planted, proving the difference comes from
    the directory scan, not from the state root itself."""
    generation_digest = "sha256:" + "c" * 64
    reviewed_files_digest = "sha256:" + "d" * 64
    current = tmp_path / "current"
    release_digest = _bind_g075_capability(
        current, generation_digest, reviewed_files_digest
    )

    assert (
        load_g075_release_capability_digest(
            state_root=current,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
            repository=tmp_path,
        )
        == release_digest
    )

    _write_orphaned_halt(
        tmp_path, generation_suffix="9" * 64, halt_file="g074-persistent-halt.json"
    )
    with pytest.raises(G075Error, match="G075_RELEASE_CAPABILITY_LOCKED"):
        load_g075_release_capability_digest(
            state_root=current,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
            repository=tmp_path,
        )


def test_turn_on_refuses_when_any_unresolved_halt_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A-2b wiring: ARM ON must refuse while any generation root holds an
    unresolved halt, even when the current release state is ENABLED.  This is
    the same entry point the operator's UI uses."""
    from fastapi import HTTPException

    from app.h11_manual import unattended_control_api as control

    class _FakeGeneration:
        generation_label = G075_GENERATION_LABEL
        digest = "sha256:" + "c" * 64

    class _FakeContract:
        generation = _FakeGeneration()
        reviewed_files_digest = "sha256:" + "d" * 64

    _write_orphaned_halt(
        tmp_path, generation_suffix="9" * 64, halt_file="g074-persistent-halt.json"
    )

    monkeypatch.setattr(control, "REPOSITORY", tmp_path)
    monkeypatch.setattr(control, "require_clean_main", lambda *, repository: object())
    monkeypatch.setattr(control, "_load_current_contract", lambda: _FakeContract())
    monkeypatch.setattr(
        control, "_safe_status", lambda contract: {"release_state": "ENABLED"}
    )
    monkeypatch.setattr(control, "_require_local_csrf", lambda request: None)

    def _forbidden_arm_store(contract: object) -> object:
        raise AssertionError("turn_on reached the arm store: the halt check did not fire")

    monkeypatch.setattr(control, "_arm_store", _forbidden_arm_store)

    class _FakeRequest:
        headers = {
            "origin": "http://127.0.0.1:8765",
            "x-h11-v4-control-csrf": "synthetic-token",
        }
        cookies = {"h11_v4_control_csrf": "synthetic-token"}

    body = control.ArmChangeRequest(
        expected_revision=0,
        expected_generation_digest=_FakeContract.generation.digest,
        expected_reviewed_files_digest=_FakeContract.reviewed_files_digest,
    )
    with pytest.raises(HTTPException) as excinfo:
        control.turn_on(request_body=body, request=_FakeRequest())
    assert "G075_UNRESOLVED_HALT_PRESENT" in str(excinfo.value.detail)


def test_repository_is_mandatory_on_the_supervisor(tmp_path: Path) -> None:
    """Phase C inverted the Phase A opt-in: ``repository`` is now REQUIRED on
    the resident supervisor (and the capability reader), so omitting it raises
    TypeError instead of silently skipping the unresolved-halt scan."""
    generation_digest = "sha256:" + "c" * 64
    reviewed_files_digest = "sha256:" + "d" * 64
    current = tmp_path / "current"
    _valid_flat_evidence(current, generation_digest, reviewed_files_digest)
    _write_orphaned_halt(
        tmp_path, generation_suffix="9" * 64, halt_file="g074-persistent-halt.json"
    )

    with pytest.raises(TypeError):
        G075ResidentSupervisor(
            state_root=current,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
            # repository deliberately omitted: it is mandatory since Phase C
        )
    with pytest.raises(TypeError):
        load_g075_release_capability_digest(
            state_root=current,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
        )


def test_unresolved_unknown_cannot_be_escaped_by_dropping_the_digest() -> None:
    """Close the remaining escape hatch.

    ``require_g075_predecessor_halt_clear`` is a no-op when the digest is
    None, and the digest is read from the manifest -- so deleting one field
    would walk straight past a latched halt. A manifest that still claims
    ``predecessor_initial_activation_unknown: true`` while omitting the
    digest that says *which* predecessor is unresolved is self-contradictory
    and must not be constructible.

    This is the whole point of P0-b: re-baking or editing a manifest must
    not be a way out of a latched halt.
    """
    from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration, V4GmoGenerationError

    payload = _load(CANONICAL)
    assert payload["predecessor_initial_activation_unknown"] is True

    stripped = {k: v for k, v in payload.items() if k != "predecessor_generation_digest"}
    stripped["blocked_hours_jst"] = tuple(stripped["blocked_hours_jst"])
    stripped["weekend_days_jst"] = tuple(stripped["weekend_days_jst"])

    with pytest.raises(V4GmoGenerationError):
        V4GmoFrozenGeneration(**stripped)


def test_nulling_the_predecessor_digest_is_also_refused() -> None:
    """Same invariant, expressed as an explicit null rather than an omission."""
    from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration, V4GmoGenerationError

    payload = _load(CANONICAL)
    payload["predecessor_generation_digest"] = None
    payload["blocked_hours_jst"] = tuple(payload["blocked_hours_jst"])
    payload["weekend_days_jst"] = tuple(payload["weekend_days_jst"])

    with pytest.raises(V4GmoGenerationError):
        V4GmoFrozenGeneration(**payload)


def test_a_generation_with_no_unresolved_predecessor_is_still_valid() -> None:
    """The invariant must not block the normal case: once nothing is
    unresolved, both fields may legitimately be absent."""
    from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration

    payload = _load(CANONICAL)
    payload["predecessor_initial_activation_unknown"] = False
    payload.pop("predecessor_generation_digest", None)
    payload["blocked_hours_jst"] = tuple(payload["blocked_hours_jst"])
    payload["weekend_days_jst"] = tuple(payload["weekend_days_jst"])

    V4GmoFrozenGeneration(**payload)  # must not raise


def test_predecessor_check_does_not_offer_a_release_path() -> None:
    """Clearing a halt is an operator decision and a separate design. P0 must
    not introduce any way to discharge one.

    Scoped to functions that reference the persistent-halt constant.  An
    earlier draft banned the bare token ``.unlink()`` module-wide, which also
    caught the unrelated process-lock cleanup in ``G075ProcessLock`` and
    pushed the implementer into rewriting working code; that was the test's
    fault, not theirs.  An AST scan over call nodes catches split forms
    (``halt.unlink()`` on its own line), literal filenames, ``os.rename`` and
    truncation, which a text regex cannot.
    """
    import ast

    import app.services.h11_v4_g075_runtime as runtime

    tree = ast.parse(Path(runtime.__file__).read_text(encoding="utf-8"))
    deletion_attrs = {"unlink", "remove", "rename", "truncate", "rmtree"}
    halt_constants = {"G075_PERSISTENT_HALT_FILE"}
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name in {"clear_g075_halt", "release_g075_halt"}:
                offenders.append(f"def {node.name}")
            referenced = {name.id for name in ast.walk(node) if isinstance(name, ast.Name)}
            if not (halt_constants & referenced):
                continue
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr in deletion_attrs
                ):
                    offenders.append(f"{node.name}() calls .{call.func.attr}")
    assert offenders == [], f"a halt marker deletion/truncation path appeared: {offenders}"


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


# -------------------------------------------------------------- Phase A: A-1


def test_g075_is_not_a_runtime_only_carry_forward_target() -> None:
    """A-1: G075 must not open the runtime-only carry-forward lane.  That
    lane (``_G040_RUNTIME_CARRIED_OPERATIONS`` /
    ``load_g040_runtime_only_carry_forward_evidence``) reuses 2026-07-29
    evidence for *Reviewed* runtime-only successors; G075 is unreviewed."""
    from app.h11_auto.v4_actual_preparation_guard import (
        _RUNTIME_ONLY_TARGET_GENERATION_LABELS,
    )

    assert G075_GENERATION_LABEL not in _RUNTIME_ONLY_TARGET_GENERATION_LABELS


def test_g075_is_still_a_known_preparation_generation() -> None:
    from app.h11_auto.v4_actual_preparation_guard import (
        _PREPARATION_KNOWN_GENERATION_LABELS,
    )

    assert G075_GENERATION_LABEL in _PREPARATION_KNOWN_GENERATION_LABELS


def test_g075_preparation_evidence_does_not_carry_forward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A-1: without today's 00-50 evidence, G075 preparation must fail on the
    normal reviewed lane with PREPARATION_SEQUENCE_NOT_COMPLETE instead of
    reusing the 2026-07-29 runtime-only carry-forward evidence (which would
    have produced a different, G040-specific error)."""
    from app.h11_auto import v4_actual_preparation_guard as guard_module
    from app.h11_auto.v4_actual_preparation_guard import (
        V4ActualPreparationGuardError,
        load_external_preparation_gate,
        load_generation_completed_preparation_evidence,
    )

    reviewed_digest = "sha256:" + "a" * 64
    generation_digest = "sha256:" + "b" * 64
    artifact = {
        "schema": "H11_V4_EXTERNAL_PREPARATION_EVIDENCE_V1",
        "status": "REVIEWED_PREPARATION_ONLY_NO_BROKER_POST",
        "broker_post_authorized": False,
        "activation_permit_issued": False,
        "reviewed_files_digest": reviewed_digest,
        "generation_manifest_digest": generation_digest,
        "focused_tests_passed": True,
        "related_tests_passed": True,
        "ruff_passed": True,
        "diff_check_passed": True,
        "danger_scan_passed": True,
        "architecture_review_clear": True,
        "safety_review_clear": True,
        "operations_review_clear": True,
    }
    artifact_path = tmp_path / guard_module.PREPARATION_ARTIFACT
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    manifest_path = tmp_path / "docs/templates/h11_v4_gmo_frozen_generation.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"generation_label": G075_GENERATION_LABEL}), encoding="utf-8"
    )
    monkeypatch.setattr(
        guard_module, "reviewed_files_digest", lambda *, repository: reviewed_digest
    )
    monkeypatch.setattr(
        guard_module,
        "load_v4_gmo_frozen_generation",
        lambda *, repository, implementation_digest: type(
            "SyntheticGeneration", (), {"digest": generation_digest}
        )(),
    )
    monkeypatch.setattr(guard_module, "require_clean_main", lambda *, repository: object())

    gate = load_external_preparation_gate(repository=tmp_path)
    with pytest.raises(
        V4ActualPreparationGuardError, match="PREPARATION_SEQUENCE_NOT_COMPLETE"
    ):
        load_generation_completed_preparation_evidence(
            repository=tmp_path,
            external_gate=gate,
            generation_digest=generation_digest,
            generation_label=G075_GENERATION_LABEL,
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
