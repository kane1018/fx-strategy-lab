"""Acceptance tests for the G075 stabilization (stop the generation churn).

Written BEFORE the implementation, by the reviewer, not the implementer.
Fake-only: no broker access, no credentials, no LaunchAgent interaction,
no notification, no network.

Background
----------
Fourteen generations (G066..G079) were produced in four days, each a
clone-edit of the previous one. Because ``REVIEWED_FILES`` grows with every
generation and the reviewed-files digest covers that whole list, *adding a
generation permanently invalidates every earlier generation's baked digest*.
That is the self-sustaining loop behind the churn: each new generation broke
the previous one, and the break motivated the next generation.

G075 is the only generation whose runtime is actually wired end to end
(private reconciler + entry/exit dispatchers + time-exit provider + ARM),
and it does NOT contain the heartbeat-continuity deadlock that G076
introduced (G076's ``_refresh_safety_chain`` refuses to beat the chain
unless the chain is already continuously healthy, so continuity can never
accumulate).

Target state asserted here
--------------------------
1. G075 is the canonical generation and its manifest verifies against a
   freshly computed reviewed-files digest.
2. The dead generations (G066..G074, G076..G079) are gone from
   ``REVIEWED_FILES`` and from the shared plumbing's per-generation
   branching, so the digest stops moving underneath everything.
3. The single canonical digest function is the one the canonical runtime
   actually uses -- no second, generation-specific digest algorithm that
   only one path can satisfy.
4. G075's own runtime wiring and its freedom from the G076 deadlock are
   preserved (regression guards, so a future edit cannot quietly reintroduce
   either problem).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from h11_v4_reviewed_digest import REVIEWED_FILES, compute_reviewed_files_digest

REPOSITORY = Path(__file__).resolve().parents[4]
BACKEND = REPOSITORY / "backend"
G075_LABEL = "H11_AUTO_30M_20260802_G075"

# Generations retired by this stabilization. G075 is the survivor; anything
# newer was strictly less runnable, and anything in G066..G074 was orphaned
# by the generation that replaced it.
DEAD_GENERATIONS = (
    "g066",
    "g067",
    "g068",
    "g069",
    "g070",
    "g071",
    "g072",
    "g073",
    "g074",
    "g076",
    "g077",
    "g078",
    "g079",
)

SHARED_PLUMBING = (
    BACKEND / "app/h11_auto/v4_gmo_generation.py",
    BACKEND / "app/h11_auto/v4_actual_preparation_guard.py",
    BACKEND / "app/h11_manual/unattended_control_api.py",
)


# ------------------------------------------------------- canonical is G075


def test_canonical_generation_is_g075() -> None:
    payload = json.loads(
        (REPOSITORY / "docs/templates/h11_v4_gmo_frozen_generation.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["generation_label"] == G075_LABEL


def test_canonical_manifest_verifies_against_the_single_digest_function() -> None:
    """The whole point of the stabilization: the canonical manifest must load
    using the ordinary shared digest function, with no generation-specific
    digest algorithm needed."""

    digest = compute_reviewed_files_digest(repository=REPOSITORY)
    generation = load_v4_gmo_frozen_generation(
        repository=REPOSITORY, implementation_digest=digest
    )
    assert generation.generation_label == G075_LABEL


def test_canonical_manifest_stays_no_post_until_commissioned() -> None:
    generation = load_v4_gmo_frozen_generation(
        repository=REPOSITORY,
        implementation_digest=compute_reviewed_files_digest(repository=REPOSITORY),
    )
    assert generation.actual_post_authorized is False
    assert generation.live_ready is False
    assert generation.unattended_live_supported is False


def test_trading_contract_is_untouched_by_the_stabilization() -> None:
    """Stabilizing the release plumbing must not move a single trading
    parameter."""

    generation = load_v4_gmo_frozen_generation(
        repository=REPOSITORY,
        implementation_digest=compute_reviewed_files_digest(repository=REPOSITORY),
    )
    assert generation.symbol == "USD_JPY"
    assert generation.selected_horizon == "30m"
    assert generation.strategy_version == "SHORT_V1"
    assert generation.quantity_units == 1000
    assert generation.maximum_hold_seconds == 1800
    assert generation.maximum_entries_per_day == 30
    assert generation.per_trade_loss_bound_jpy == 5000
    assert generation.daily_loss_limit_jpy == 10000
    assert generation.monthly_loss_limit_jpy == 50000
    assert generation.maximum_consecutive_losses == 5


# ------------------------------------------------- dead generations removed


def test_reviewed_files_contains_no_dead_generation_artifacts() -> None:
    offenders = [
        relative
        for relative in REVIEWED_FILES
        if re.search(rf"_({'|'.join(DEAD_GENERATIONS)})_", relative)
    ]
    assert offenders == []


def test_reviewed_files_still_contains_the_g075_artifacts() -> None:
    assert any("_g075_" in relative for relative in REVIEWED_FILES)


def test_every_reviewed_file_exists() -> None:
    """Removing artifacts must not leave dangling entries -- a missing path
    makes the digest function raise and takes every gate down with it."""

    missing = [
        relative
        for relative in REVIEWED_FILES
        if not (REPOSITORY / relative).is_file()
    ]
    assert missing == []


def test_shared_plumbing_has_no_dead_generation_branches() -> None:
    """The per-generation ``elif`` chains in the shared plumbing are what made
    every generation edit the same three files. They must be gone."""

    offenders: list[str] = []
    for path in SHARED_PLUMBING:
        source = path.read_text(encoding="utf-8")
        for generation in DEAD_GENERATIONS:
            if generation in source.lower():
                offenders.append(f"{path.name}:{generation}")
    assert offenders == []


def test_no_second_reviewed_digest_algorithm_survives() -> None:
    """A generation-specific digest function is how the canonical manifest
    ended up verifiable by exactly one code path while every other entry
    point failed with 'implementation digest mismatch'."""

    offenders: list[str] = []
    for path in (BACKEND / "app/services").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if re.search(r"def compute_g\d+_reviewed_files_digest", source):
            offenders.append(path.name)
    assert offenders == []


# ------------------------------------------- G075 runtime remains intact


def test_g075_runtime_wiring_is_preserved() -> None:
    """G075 is the survivor precisely because it wires a reconciler, both
    dispatchers, a time-exit provider and ARM. Guard all of it."""

    source = (
        BACKEND / "scripts/h11_auto_v4_g075_runtime_bootstrap.py"
    ).read_text(encoding="utf-8")
    for required in (
        "reconciliation_runner",
        "entry_dispatcher",
        "exit_dispatcher",
        "exit_reason_provider",
        "arm_on=",
    ):
        assert required in source, required


def test_g075_bootstrap_beats_the_chain_unconditionally() -> None:
    """The G076 deadlock: refusing to beat a chain that is not yet
    continuously healthy means continuity can never accumulate, so the
    resident permanently halts on its first tick. G075 beats first and
    assesses separately; keep it that way."""

    source = (
        BACKEND / "scripts/h11_auto_v4_g075_runtime_bootstrap.py"
    ).read_text(encoding="utf-8")
    assert "runtime_chain.beat(" in source
    assert "continuously_healthy" not in source


def test_no_surviving_module_gates_a_beat_on_continuity() -> None:
    """Repo-wide guard against reintroducing the deadlock anywhere."""

    offenders: list[str] = []
    for path in list((BACKEND / "app/services").glob("*.py")) + list(
        (BACKEND / "scripts").glob("*.py")
    ):
        source = path.read_text(encoding="utf-8")
        if "continuously_healthy" not in source:
            continue
        # A module may READ continuity for reporting; the deadlock is
        # specifically refusing to beat because continuity is not yet met.
        if re.search(
            r"if not .*continuously_healthy.*:\s*\n\s*return False, False", source
        ):
            offenders.append(path.name)
    assert offenders == []
