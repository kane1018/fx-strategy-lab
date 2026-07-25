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
dead-man/heartbeat-chain stores and the Public-only, credential-free
entry-gate provider. Operator confirmed the heartbeat-chain policy
constants (2026-07-25, the suggested 60s/300s values -- see the
module-level comment above ``_HEARTBEAT_CHAIN_POLICY_LABEL``), so that
placeholder is now live code, not a raise.

THREE PLACEHOLDER sections remain: real Keychain credential pair, real
HTTP client, real Pushover/email transports. All three are intentionally
left unimplemented and RAISE with a clear message if reached. This is a
deliberate project boundary (AGENTS.md "H-11 v4 unattended liveスケジューラ
配線 実装限定例外"; also independently documented in
``h11_v4_unattended_live_entry_notification.py``'s own module docstring
for the notification-transport half specifically), not an oversight:
connecting this scheduler to a real broker account, and to real
notification transports, are decisions only the operator makes, in code
the operator writes themselves, in this exact file.

To activate: edit all THREE remaining PLACEHOLDER blocks below, following
the instructions in each -- filling in only some still leaves the rest
raising, so there is no path to a real cycle attempt with any of them
unfilled. Do not remove the digest re-verification, the "not yet" handling,
or anything above the placeholders -- those are the reviewed safety
boundary, not scaffolding.

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

# ruff: noqa: E402  -- imports below intentionally follow the sys.path
# bootstrap: launchd invokes this script by absolute path (not `python -m`),
# so `backend/` is not otherwise on sys.path and the `app.*` imports below
# would fail to resolve without this.
import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

_ROOT_PATH = Path(__file__).resolve().parents[1]
if str(_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(_ROOT_PATH))

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
from app.services.h11_v4_notification_actual_preparation import (
    H11V4NotificationCredentialBundle,
)
from app.services.h11_v4_notification_actual_transport import (
    H11V4ActualEmailTransport,
    H11V4ActualPushoverTransport,
)
from app.services.h11_v4_unattended_live_entry_gate_provider import (
    unattended_live_entry_gate_provider,
)
from app.services.h11_v4_unattended_live_heartbeat_chain import (
    V4HeartbeatChainPolicy,
    V4HeartbeatChainStore,
)
from scripts import h11_auto_v4_unattended_live_bounded_run as bounded_run

# Heartbeat-chain continuity thresholds for this scheduler specifically --
# NOT part of the frozen generation contract (no operator-approved constant
# existed for this anywhere in the codebase before this track). Independent
# review traced these directly into
# confirm_v4_unattended_authorization_once's six-condition permit-issuance
# check (heartbeat_chain_store.assess(...) is one of the six), so despite
# governing "continuity" rather than yen amounts, this IS money-affecting --
# an earlier version of this comment incorrectly claimed it wasn't. Operator
# reviewed and explicitly confirmed these suggested values (2026-07-25):
# maximum_gap mirrors the already-approved dead-man maximum_heartbeat_age_seconds
# (60s); minimum_continuous matches a value already used in this track's own
# orchestration TEST fixtures (300s, explicitly labeled test-only there).
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

        # PLACEHOLDER 0 (heartbeat-chain policy confirmation) -- operator
        # reviewed and confirmed the suggested values (2026-07-25): 60s/300s,
        # matching the approved dead-man maximum_heartbeat_age_seconds and
        # this track's own orchestration test precedent respectively (see
        # the module-level comment above _HEARTBEAT_CHAIN_POLICY_LABEL).
        heartbeat_chain_store = V4HeartbeatChainStore(
            state_root / "unattended-heartbeat-chain.json",
            policy=V4HeartbeatChainPolicy(
                policy_label=_HEARTBEAT_CHAIN_POLICY_LABEL,
                maximum_gap_seconds=_HEARTBEAT_CHAIN_MAXIMUM_GAP_SECONDS,
                minimum_continuous_seconds=_HEARTBEAT_CHAIN_MINIMUM_CONTINUOUS_SECONDS,
            ),
        )

        # ================= PLACEHOLDER 1 of 3: real broker credential =================
        # Replace the next statement with, e.g.:
        #     from app.services.h11_v4_gmo_actual_transport import (
        #         V4GmoKeychainCredentialPair,
        #     )
        #     credential_pair = V4GmoKeychainCredentialPair()
        # This one line is the entire "last millimeter" this project has
        # deliberately withheld from every automated component in this
        # track. Writing it here is your explicit decision to connect this
        # scheduler to your real GMO Coin account -- not this launcher's.
        from app.services.h11_v4_gmo_actual_transport import V4GmoKeychainCredentialPair
        credential_pair = V4GmoKeychainCredentialPair()

        # ================= PLACEHOLDER 2 of 3: real HTTP client =================
        # Replace the next statement with, e.g.:
        #     client = httpx.Client(timeout=5.0)
        client = httpx.Client(timeout=5.0)

        # ================= PLACEHOLDER 3 of 3: real notification transports =================
        notification_primary = H11V4ActualPushoverTransport(
            credentials=H11V4NotificationCredentialBundle(),
            client=httpx.Client(timeout=10.0),
        )
        notification_secondary = H11V4ActualEmailTransport(
            credentials=H11V4NotificationCredentialBundle(),
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
