#!/usr/bin/env python3
"""Operator-facing launcher template invoked by the unattended scheduler.

This is the "separate, operator-authored launcher" that
``h11_auto_v4_unattended_live_bounded_run.py`` (design doc §12.5) requires:
that file ships no runnable ``__main__`` and never constructs a real
credential pair or a real HTTP client, by design. This launcher is what a
LaunchAgent (rendered by
``app.h11_auto.v4_gmo_unattended_scheduler_launchd``) actually executes on
each scheduled tick.

Everything up to the marked PLACEHOLDER sections below is real, working
code: it re-verifies the reviewed-files/generation digests baked into the
plist at install time, prepares a fresh G013 session, and builds the risk/
dead-man stores and the Public-only, credential-free entry-gate provider.
There are FOUR PLACEHOLDER sections, not three -- independent review traced
the heartbeat-chain policy constants (PLACEHOLDER 0) directly into
``confirm_v4_unattended_authorization_once``'s six-condition permit-issuance
check, so despite being a "continuity" setting rather than a yen amount, it
IS money-affecting and gets the same explicit-confirmation treatment as
PLACEHOLDERs 1-3 (real Keychain credential pair, real HTTP client, real
Pushover/email transports). All four are intentionally left unimplemented
and RAISE with a clear message if reached. This is a deliberate project
boundary (AGENTS.md "H-11 v4 unattended liveスケジューラ配線 実装限定例外"),
not an oversight: connecting this scheduler to a real broker account, and
confirming the values that gate its permit issuance, are decisions only the
operator makes, in code the operator writes themselves, in this exact file.

To activate: edit all FOUR PLACEHOLDER blocks below, following the
instructions in each -- filling in only some still leaves the rest raising,
so there is no path to a real cycle attempt with any of them unfilled. Do
not remove the digest re-verification, the "not yet" handling, or anything
above the placeholders -- those are the reviewed safety boundary, not
scaffolding.

Editing this file changes its own reviewed-files digest (it is itself
REVIEWED_FILES-listed), which changes ``implementation_digest``. After
filling in the placeholders you must: (1) recompute
``implementation_digest`` and update it in
``docs/templates/h11_v4_gmo_frozen_generation.json`` -- this file will not
tell you to do this; skipping it makes ``load_v4_gmo_frozen_generation``
raise ``V4GmoGenerationError`` (not this file's own clean error class) the
next time this launcher runs; and (2) re-render and reinstall the
LaunchAgent (``h11_auto_v4_install_unattended_live_scheduler_launchagent.py``)
so the plist bakes in the new digests -- the OLD plist's baked
``--expected-reviewed-files-digest`` will otherwise correctly, but
confusingly, refuse to match your edited file forever.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import DeadManStore, PhaseBRiskStore
from app.h11_auto.v4_actual_preparation_guard import reviewed_files_digest
from app.h11_auto.v4_gmo_generation import (
    load_v4_gmo_frozen_generation,
    v4_gmo_dead_man_policy,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services import h11_v4_gmo_g013_canary as canary_module
from app.services.h11_v4_gmo_g013_canary import prepare_g013_canary_session
from app.services.h11_v4_unattended_live_entry_gate_provider import (
    unattended_live_entry_gate_provider,
)
from scripts import h11_auto_v4_unattended_live_bounded_run as bounded_run

# Heartbeat-chain continuity thresholds for this scheduler specifically --
# NOT part of the frozen generation contract (no operator-approved constant
# exists for this anywhere in the codebase yet). Independent review traced
# these directly into confirm_v4_unattended_authorization_once's six-condition
# permit-issuance check (heartbeat_chain_store.assess(...) is one of the six),
# so despite governing "continuity" rather than yen amounts, this IS
# money-affecting and does need explicit operator sign-off before real use --
# an earlier version of this comment incorrectly claimed otherwise. The
# suggested values below are precedent-matched, not operator-approved:
# maximum_gap mirrors the already-approved dead-man maximum_heartbeat_age_seconds
# (60s); minimum_continuous matches a value already used in this track's own
# orchestration TEST fixtures (300s, explicitly labeled test-only there) --
# neither has been reviewed by the operator for this real, if still
# placeholder-gated, use. Treated as PLACEHOLDER 0 below: raises until the
# operator explicitly confirms (or changes) these two numbers themselves.
_HEARTBEAT_CHAIN_POLICY_LABEL = "H11_V4_UNATTENDED_SCHEDULER_CHAIN_V1"
_HEARTBEAT_CHAIN_MAXIMUM_GAP_SECONDS = 60
_HEARTBEAT_CHAIN_MINIMUM_CONTINUOUS_SECONDS = 300


class V4UnattendedSchedulerLauncherError(RuntimeError):
    """Fixed safe launcher failure (digest mismatch, missing placeholder)."""


def _require_operator_configuration(placeholder_name: str):
    """Raise until the named PLACEHOLDER block below is filled in for real.

    Each of the three placeholders calls this independently, so filling in
    only one (e.g. the credential pair) still leaves the other two raising
    -- there is no path to `bounded_run.main` with any placeholder unfilled.
    """

    raise V4UnattendedSchedulerLauncherError(
        f"SCHEDULER_{placeholder_name}_NOT_CONFIGURED: edit this block in "
        "h11_auto_v4_unattended_live_scheduled_launcher.py to construct the "
        "real object it describes before this scheduler can run for real."
    )


def _verify_baked_digests(
    *, repository: Path, expected_reviewed_files_digest: str, expected_generation_digest: str
):
    """Re-derive both digests fresh; refuse a worktree that drifted since install."""

    digest = reviewed_files_digest(repository=repository)
    if digest != expected_reviewed_files_digest:
        raise V4UnattendedSchedulerLauncherError(
            "SCHEDULER_REVIEWED_FILES_DIGEST_MISMATCH"
        )
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=digest
    )
    if generation.digest != expected_generation_digest:
        raise V4UnattendedSchedulerLauncherError(
            "SCHEDULER_GENERATION_DIGEST_MISMATCH"
        )
    return digest, generation


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scheduler-invoked launcher for one bounded unattended live "
            "entry-cycle attempt. Baked digests are re-verified fresh on "
            "every tick; a mismatch aborts without constructing anything."
        )
    )
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-reviewed-files-digest", required=True)
    parser.add_argument("--expected-generation-digest", required=True)
    args = parser.parse_args(argv)
    repository = args.repository.resolve()

    digest, generation = _verify_baked_digests(
        repository=repository,
        expected_reviewed_files_digest=args.expected_reviewed_files_digest,
        expected_generation_digest=args.expected_generation_digest,
    )

    # Same lock filename ("process.lock") the interactive G013/G014 canary
    # path uses (h11_v4_gmo_actual_runtime_binding.py) -- NOT a distinct
    # scheduler-only name. Both paths open the identical risk.json/
    # dead-man.json files under the same state_root; a different lock name
    # here would let an interactive canary run and a scheduled tick corrupt
    # each other's risk/dead-man state concurrently instead of the second
    # one correctly skipping.
    lock = H11AutoProcessLock(
        v4_gmo_runtime_state_root(repository=repository, generation_digest=generation.digest)
        / "process.lock"
    )
    if not lock.acquire():
        print("status=UNATTENDED_SCHEDULER_TICK_SKIPPED_LOCK_HELD")
        return 0
    try:
        try:
            session = prepare_g013_canary_session(
                repository=repository, now_utc=datetime.now(UTC)
            )
        except canary_module.V4GmoG013CanaryError as error:
            print(f"status=UNATTENDED_SCHEDULER_TICK_NOT_YET reason_label={error}")
            return 0

        state_root = v4_gmo_runtime_state_root(
            repository=repository, generation_digest=generation.digest
        )
        risk_policy = v4_gmo_risk_policy()
        risk_store = PhaseBRiskStore(state_root / "risk.json", policy=risk_policy)
        dead_man_store = DeadManStore(
            state_root / "dead-man.json", policy=v4_gmo_dead_man_policy()
        )

        # ========= PLACEHOLDER 0 of 4: heartbeat-chain policy confirmation =========
        # heartbeat_chain_store.assess(...) is one of the six conditions
        # confirm_v4_unattended_authorization_once checks before minting a
        # real permit -- this IS money-affecting, despite governing
        # "continuity" rather than a yen amount, and has no operator-approved
        # value anywhere in this codebase yet (see the module-level comment
        # above _HEARTBEAT_CHAIN_POLICY_LABEL for the suggested values and
        # their precedent). Review those two numbers, then replace this
        # statement with the policy construction below (as-is if you accept
        # the suggested values, or with your own numbers):
        #     from app.services.h11_v4_unattended_live_heartbeat_chain import (
        #         V4HeartbeatChainPolicy,
        #         V4HeartbeatChainStore,
        #     )
        #     heartbeat_chain_store = V4HeartbeatChainStore(
        #         state_root / "unattended-heartbeat-chain.json",
        #         policy=V4HeartbeatChainPolicy(
        #             policy_label=_HEARTBEAT_CHAIN_POLICY_LABEL,
        #             maximum_gap_seconds=_HEARTBEAT_CHAIN_MAXIMUM_GAP_SECONDS,
        #             minimum_continuous_seconds=_HEARTBEAT_CHAIN_MINIMUM_CONTINUOUS_SECONDS,
        #         ),
        #     )
        heartbeat_chain_store = _require_operator_configuration(
            "PLACEHOLDER_0_HEARTBEAT_CHAIN_POLICY"
        )

        # ================= PLACEHOLDER 1 of 4: real broker credential =================
        # Replace the next statement with, e.g.:
        #     from app.services.h11_v4_gmo_actual_transport import (
        #         V4GmoKeychainCredentialPair,
        #     )
        #     credential_pair = V4GmoKeychainCredentialPair()
        # This one line is the entire "last millimeter" this project has
        # deliberately withheld from every automated component in this
        # track. Writing it here is your explicit decision to connect this
        # scheduler to your real GMO Coin account -- not this launcher's.
        credential_pair = _require_operator_configuration("PLACEHOLDER_1_CREDENTIAL_PAIR")

        # ================= PLACEHOLDER 2 of 4: real HTTP client =================
        # Replace the next statement with, e.g.:
        #     client = httpx.Client(timeout=5.0)
        client = _require_operator_configuration("PLACEHOLDER_2_HTTP_CLIENT")

        # ================= PLACEHOLDER 3 of 4: real notification transports =================
        # No real (non-fake) Pushover/email transport class exists anywhere
        # in this repository yet -- only H11V4FakePushoverTransport/
        # H11V4FakeEmailTransport (app/services/h11_v4_notification_binding_no_post.py)
        # exist today. You must implement a real transport satisfying the
        # H11V4PushoverTransport/H11V4EmailTransport Protocols (real HTTP
        # POST to Pushover's API; real SMTP send) and construct instances
        # here, replacing both of the next two statements.
        notification_primary = _require_operator_configuration(
            "PLACEHOLDER_3_NOTIFICATION_PRIMARY"
        )
        notification_secondary = _require_operator_configuration(
            "PLACEHOLDER_3_NOTIFICATION_SECONDARY"
        )

        return bounded_run.main(
            ["--max-cycles", "1", "--interval-seconds", "0"],
            session=session,
            risk_store=risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man_store,
            heartbeat_chain_store=heartbeat_chain_store,
            notification_primary=notification_primary,
            notification_secondary=notification_secondary,
            entry_gate_reason_provider=unattended_live_entry_gate_provider,
            credential_pair=credential_pair,
            client=client,
        )
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
