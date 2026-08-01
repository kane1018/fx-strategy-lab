#!/usr/bin/env python3
"""Operator-facing launcher invoked by the unattended scheduler.

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

The operator has already connected the real Keychain credential wrapper,
HTTP client, and notification transports in this reviewed file. Construction
is lazy; no credential or network operation occurs until the bounded runner.
Every tick first re-verifies both digests and independently requires a frozen
generation with ``live_ready=true`` and ``unattended_live_supported=true``,
then requires the generation-bound persistent arm to be clear.

Changing this file requires a new reviewed-files digest, corrective generation,
fresh review/preparation, and LaunchAgent reinstall. The current no-POST
generation is not commissioned, so this launcher exits before session,
credential, notification, or broker construction.
"""

from __future__ import annotations

# ruff: noqa: E402  -- imports below intentionally follow the sys.path
# bootstrap: launchd invokes this script by absolute path (not `python -m`),
# so `backend/` is not otherwise on sys.path and the `app.*` imports below
# would fail to resolve without this.
import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

_ROOT_PATH = Path(__file__).resolve().parents[1]
if str(_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(_ROOT_PATH))

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import DeadManStore, PhaseBRiskStore
from app.h11_auto.v4_actual_preparation_guard import (
    V4ActualPreparationGuardError,
    load_external_preparation_gate,
    require_g040_runtime_only_monitor_completion,
    require_g052_flat_only_monitor_completion,
    require_g053_flat_only_monitor_completion,
    reviewed_files_digest,
)
from app.h11_auto.v4_gmo_generation import (
    load_v4_gmo_frozen_generation,
    v4_gmo_dead_man_policy,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services import h11_v4_gmo_g013_canary as canary_module
from app.services.h11_v4_g038_unattended_activation import (
    V4G038ActivationError,
    record_g038_scheduler_heartbeat,
    verify_g038_generation_activation,
)
from app.services.h11_v4_g064_position_reconciliation_no_post import (
    load_g064_position_reconciliation_no_post,
    write_g064_position_reconciliation_no_post,
)
from app.services.h11_v4_g064_unattended_activation import (
    G064_GENERATION_LABEL,
    V4G064ActivationError,
    clear_g064_worker_lease,
    run_g064_exit_only_dispatch_no_post,
    verify_g064_generation_activation,
    verify_g064_generation_contract,
    write_g064_exit_only_dispatch_no_post,
    write_g064_persistent_halt_no_post,
    write_g064_worker_lease,
)
from app.services.h11_v4_gmo_formal_canary_source import (
    V4GmoFormalCanarySourceError,
)
from app.services.h11_v4_gmo_g013_canary import prepare_g013_canary_session
from app.services.h11_v4_notification_actual_preparation import (
    H11V4NotificationCredentialBundle,
)
from app.services.h11_v4_notification_actual_transport import (
    H11V4ActualEmailTransport,
    H11V4ActualPushoverTransport,
)
from app.services.h11_v4_unattended_live_arm_state import V4UnattendedLiveArmStore
from app.services.h11_v4_unattended_live_entry_gate_provider import (
    unattended_live_entry_gate_provider,
)
from app.services.h11_v4_unattended_live_heartbeat_chain import (
    V4_UNATTENDED_RUNTIME_HEARTBEAT_MAXIMUM_GAP_SECONDS,
    V4_UNATTENDED_RUNTIME_HEARTBEAT_MINIMUM_CONTINUOUS_SECONDS,
    V4_UNATTENDED_RUNTIME_HEARTBEAT_POLICY_LABEL,
    V4HeartbeatChainStore,
    v4_unattended_runtime_heartbeat_policy,
)
from app.services.h11_v4_unattended_live_paths import (
    v4_unattended_live_arm_state_path,
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
_HEARTBEAT_CHAIN_POLICY_LABEL = V4_UNATTENDED_RUNTIME_HEARTBEAT_POLICY_LABEL
_HEARTBEAT_CHAIN_MAXIMUM_GAP_SECONDS = (
    V4_UNATTENDED_RUNTIME_HEARTBEAT_MAXIMUM_GAP_SECONDS
)
_HEARTBEAT_CHAIN_MINIMUM_CONTINUOUS_SECONDS = (
    V4_UNATTENDED_RUNTIME_HEARTBEAT_MINIMUM_CONTINUOUS_SECONDS
)


class V4UnattendedSchedulerLauncherError(RuntimeError):
    """Fixed safe launcher failure (digest mismatch, missing placeholder)."""


def _g064_runtime_state_root_for_expected_digest(
    *, repository: Path, expected_generation_digest: object
) -> Path | None:
    if (
        not isinstance(expected_generation_digest, str)
        or len(expected_generation_digest) != 71
        or not expected_generation_digest.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in expected_generation_digest[7:])
    ):
        return None
    manifest_path = repository / "docs/templates/h11_v4_gmo_frozen_generation.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("generation_label") != G064_GENERATION_LABEL
        or payload.get("digest") != expected_generation_digest
    ):
        return None
    return v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=expected_generation_digest,
    )


def _latch_g064_halt_after_binding_failure(
    *,
    repository: Path,
    expected_generation_digest: object,
    expected_reviewed_files_digest: object,
) -> bool:
    state_root = _g064_runtime_state_root_for_expected_digest(
        repository=repository,
        expected_generation_digest=expected_generation_digest,
    )
    if (
        state_root is None
        or not isinstance(expected_generation_digest, str)
        or not isinstance(expected_reviewed_files_digest, str)
    ):
        return False
    try:
        write_g064_persistent_halt_no_post(
            state_root=state_root,
            generation_digest=expected_generation_digest,
            reviewed_files_digest=expected_reviewed_files_digest,
        )
    except V4G064ActivationError:
        return False
    return True


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


def _run_one_tick(
    argv: list[str], *, preheld_process_lock: H11AutoProcessLock | None = None
) -> int:
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

    try:
        digest, generation = _verify_baked_digests(
            repository=repository,
            expected_reviewed_files_digest=args.expected_reviewed_files_digest,
            expected_generation_digest=args.expected_generation_digest,
        )
    except Exception:  # noqa: BLE001
        if _latch_g064_halt_after_binding_failure(
            repository=repository,
            expected_generation_digest=args.expected_generation_digest,
            expected_reviewed_files_digest=args.expected_reviewed_files_digest,
        ):
            print(
                "status=G064_RESIDENT_RUNTIME_HALTED "
                "broker_write=false actual_post_count=0"
            )
        else:
            print(
                "status=G064_RESIDENT_RUNTIME_HALT_NOT_WRITTEN "
                "broker_write=false actual_post_count=0"
            )
        return 2
    state_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=generation.digest,
    )
    if (
        generation.live_ready is not True
        or generation.unattended_live_supported is not True
    ):
        if getattr(generation, "generation_label", "") == (
            "H11_AUTO_30M_20260731_G063"
        ):
            from app.h11_auto.v4_gmo_monitor_supervisor import (
                V4GmoMonitorSupervisor,
            )

            state_root = v4_gmo_runtime_state_root(
                repository=repository,
                generation_digest=generation.digest,
            )
            supervisor = V4GmoMonitorSupervisor(
                repository=repository,
                generation=generation,
            )
            try:
                supervisor.acquire_single_process()
                try:
                    completion_marker = (
                        state_root / "g063-no-post-runtime-bootstrap-completed.json"
                    )
                    if completion_marker.is_symlink():
                        print(
                            "status=G063_NO_POST_RUNTIME_BOOTSTRAP_NOT_CLEAR "
                            "broker_write=false actual_post_count=0"
                        )
                        return 0
                    if completion_marker.is_file():
                        marker = json.loads(
                            completion_marker.read_text(encoding="utf-8")
                        )
                        required_files = (
                            "risk.json",
                            "dead-man.json",
                            "unattended-heartbeat-chain.json",
                            "supervisor-heartbeat.json",
                        )
                        if (
                            marker.get("generation_digest") != generation.digest
                            or marker.get("status")
                            != "G063_NO_POST_RUNTIME_BOOTSTRAP_COMPLETED"
                            or any(
                                (state_root / name).is_symlink()
                                or not (state_root / name).is_file()
                                for name in required_files
                            )
                        ):
                            print(
                                "status=G063_NO_POST_RUNTIME_BOOTSTRAP_NOT_CLEAR "
                                "broker_write=false actual_post_count=0"
                            )
                            return 0
                        print(
                            "status=G063_NO_POST_RUNTIME_BOOTSTRAP_ALREADY_COMPLETED "
                            "live_ready=false unattended_live_supported=false "
                            "broker_write=false actual_post_count=0"
                        )
                        return 0
                    tick = supervisor.run_tick(now_utc=datetime.now(UTC))
                    if tick.broker_write is False and tick.actual_post_count == 0:
                        supervisor._write_once_marker(  # noqa: SLF001
                            "g063-no-post-runtime-bootstrap-completed.json",
                            status="G063_NO_POST_RUNTIME_BOOTSTRAP_COMPLETED",
                            observed_at_utc=datetime.now(UTC),
                        )
                finally:
                    supervisor.close()
                if tick.broker_write is False and tick.actual_post_count == 0:
                    print(
                        "status=G063_NO_POST_RUNTIME_BOOTSTRAP_COMPLETED "
                        "live_ready=false unattended_live_supported=false "
                        "broker_write=false actual_post_count=0"
                    )
                else:
                    print(
                        "status=G063_NO_POST_RUNTIME_BOOTSTRAP_NOT_CLEAR "
                        "broker_write=false actual_post_count=0"
                    )
            except Exception:  # noqa: BLE001
                print(
                    "status=G063_NO_POST_RUNTIME_BOOTSTRAP_NOT_CLEAR "
                    "broker_write=false actual_post_count=0"
                )
            return 0
        print(
            "status=UNATTENDED_SCHEDULER_GENERATION_NOT_COMMISSIONED "
            "broker_write=false actual_post_count=0"
        )
        return 0
    g064_tick = None
    if generation.generation_label == G064_GENERATION_LABEL:
        try:
            verify_g064_generation_contract(generation=generation)
            monitor = V4GmoMonitorSupervisor(
                repository=repository,
                generation=generation,
                runtime_lock=preheld_process_lock,
            )
            monitor.acquire_single_process()
            try:
                g064_tick = monitor.run_tick(now_utc=datetime.now(UTC))
            finally:
                monitor.close()
            verify_g064_generation_activation(
                generation=generation,
                state_root=state_root,
            )
        except Exception:  # noqa: BLE001
            try:
                write_g064_persistent_halt_no_post(
                    state_root=state_root,
                    generation_digest=generation.digest,
                    reviewed_files_digest=digest,
                )
            except V4G064ActivationError:
                print(
                    "status=G064_RESIDENT_RUNTIME_HALT_NOT_WRITTEN "
                    "broker_write=false actual_post_count=0"
                )
                return 2
            print(
                "status=G064_RESIDENT_RUNTIME_NOT_CLEAR "
                "broker_write=false actual_post_count=0"
            )
            return 2
        if (
            g064_tick.broker_write is not False
            or g064_tick.actual_post_count != 0
            or g064_tick.runtime_risk_ready is not True
            or g064_tick.dead_man_alive is not True
            or g064_tick.heartbeat_chain_beat is not True
            or g064_tick.process_lock_clear is not True
        ):
            try:
                write_g064_persistent_halt_no_post(
                    state_root=state_root,
                    generation_digest=generation.digest,
                    reviewed_files_digest=digest,
                )
            except V4G064ActivationError:
                print(
                    "status=G064_RESIDENT_RUNTIME_HALT_NOT_WRITTEN "
                    "broker_write=false actual_post_count=0"
                )
                return 2
            print(
                "status=G064_RESIDENT_RUNTIME_NOT_CLEAR "
                "broker_write=false actual_post_count=0"
            )
            return 2
    else:
        try:
            verify_g038_generation_activation(generation=generation)
            record_g038_scheduler_heartbeat(generation=generation)
        except V4G038ActivationError:
            print(
                "status=UNATTENDED_SCHEDULER_ACTIVATION_EVIDENCE_NOT_CLEAR "
                "broker_write=false actual_post_count=0"
            )
            return 2
    arm_check = V4UnattendedLiveArmStore(
        v4_unattended_live_arm_state_path(generation_digest=generation.digest)
    ).check(
        expected_generation_digest=generation.digest,
        expected_reviewed_files_digest=digest,
    )
    if not arm_check.armed and generation.generation_label != G064_GENERATION_LABEL:
        reason = arm_check.blocked_reasons[0] if arm_check.blocked_reasons else "OPERATOR_DISARMED"
        print(
            "status=UNATTENDED_SCHEDULER_TICK_DISARMED "
            f"reason_label={reason} broker_write=false actual_post_count=0"
        )
        return 2
    if generation.generation_label == G064_GENERATION_LABEL and (
        g064_tick is None
        or g064_tick.persistent_halt is True
        or g064_tick.unknown_halt is True
        or (arm_check.armed and g064_tick.entry_gate_open is not True)
    ):
        print(
            "status=G064_ENTRY_GATE_CLOSED "
            "broker_write=false actual_post_count=0"
        )
        return 0
    if getattr(generation, "generation_label", "") in {
        "H11_AUTO_30M_20260729_G040",
        "H11_AUTO_30M_20260729_G041",
        "H11_AUTO_30M_20260730_G047",
        "H11_AUTO_30M_20260730_G048",
        "H11_AUTO_30M_20260730_G049",
        "H11_AUTO_30M_20260730_G050",
        "H11_AUTO_30M_20260730_G051",
        "H11_AUTO_30M_20260730_G052",
        "H11_AUTO_30M_20260730_G053",
        "H11_AUTO_30M_20260730_G054",
        "H11_AUTO_30M_20260730_G055",
        "H11_AUTO_30M_20260730_G056",
    }:
        state_root = v4_gmo_runtime_state_root(
            repository=repository,
            generation_digest=generation.digest,
        )
        try:
            external_gate = load_external_preparation_gate(
                repository=repository
            )
            if (
                generation.generation_label
                == "H11_AUTO_30M_20260730_G052"
            ):
                require_g052_flat_only_monitor_completion(
                    repository=repository,
                    external_gate=external_gate,
                    generation_digest=generation.digest,
                    now_utc=datetime.now(UTC),
                )
            elif (
                generation.generation_label
                == "H11_AUTO_30M_20260730_G053"
            ):
                require_g053_flat_only_monitor_completion(
                    repository=repository,
                    external_gate=external_gate,
                    generation_digest=generation.digest,
                    now_utc=datetime.now(UTC),
                )
            else:
                require_g040_runtime_only_monitor_completion(
                    repository=repository,
                    external_gate=external_gate,
                    generation_digest=generation.digest,
                    now_utc=datetime.now(UTC),
                )
            heartbeat = json.loads(
                (state_root / "supervisor-heartbeat.json").read_text(
                    encoding="utf-8"
                )
            )
            observed = datetime.fromisoformat(
                str(heartbeat["observed_at_utc"])
            )
            heartbeat_age = (
                datetime.now(UTC) - observed.astimezone(UTC)
            ).total_seconds()
            supervisor_lock = H11AutoProcessLock(
                state_root / "supervisor.lock"
            )
            supervisor_is_running = not supervisor_lock.acquire()
            if not supervisor_is_running:
                supervisor_lock.release()
        except (
            V4ActualPreparationGuardError,
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            print(
                "status=UNATTENDED_SCHEDULER_RUNTIME_NOT_CLEAR "
                "broker_write=false actual_post_count=0"
            )
            return 0
        if (
            heartbeat.get("generation_digest") != generation.digest
            or heartbeat.get("runtime_risk_ready") is not True
            or heartbeat.get("dead_man_alive") is not True
            or heartbeat.get("heartbeat_chain_beat") is not True
            or heartbeat.get("broker_write") is not False
            or heartbeat.get("actual_post_count") != 0
            or heartbeat_age < 0
            or heartbeat_age > 60
            or not supervisor_is_running
        ):
            print(
                "status=UNATTENDED_SCHEDULER_RUNTIME_NOT_CLEAR "
                "broker_write=false actual_post_count=0"
            )
            return 0

    # Same lock filename ("process.lock") the interactive G013-G016 canary
    # path uses (h11_v4_gmo_actual_runtime_binding.py) -- NOT a distinct
    # scheduler-only name. Both paths open the identical risk.json/
    # dead-man.json files under the same state_root; a different lock name
    # here would let an interactive canary run and a scheduled tick corrupt
    # each other's risk/dead-man state concurrently instead of the second
    # one correctly skipping.
    if preheld_process_lock is None:
        lock = H11AutoProcessLock(
            v4_gmo_runtime_state_root(
                repository=repository, generation_digest=generation.digest
            )
            / "process.lock"
        )
        if not lock.acquire():
            print("status=UNATTENDED_SCHEDULER_TICK_SKIPPED_LOCK_HELD")
            return 0
        lock_held = True
    else:
        lock = preheld_process_lock
        lock_held = False
    try:
        state_root = v4_gmo_runtime_state_root(
            repository=repository, generation_digest=generation.digest
        )
        if generation.generation_label == G064_GENERATION_LABEL and not arm_check.armed:
            write_g064_worker_lease(
                state_root=state_root,
                generation_digest=generation.digest,
                reviewed_files_digest=digest,
                now_utc=datetime.now(UTC),
            )
            position = load_g064_position_reconciliation_no_post(
                state_root=state_root,
                generation_digest=generation.digest,
                now_utc=datetime.now(UTC),
            )
            if not position.evidence_available or not position.generation_bound:
                if preheld_process_lock is None:
                    clear_g064_worker_lease(
                        state_root=state_root, expected_pid=os.getpid()
                    )
                raise canary_module.V4GmoG013CanaryError(
                    "G064_POSITION_EVIDENCE_NOT_CLEAR"
                )
            write_g064_exit_only_dispatch_no_post(
                state_root=state_root,
                generation_digest=generation.digest,
                reviewed_files_digest=digest,
                position_open=position.position_open,
                protection_confirmed=position.protection_confirmed,
                ownership_exact=position.ownership_exact,
                quantity_matches=position.quantity_matches,
            )
            if position.position_open:
                run_g064_exit_only_dispatch_no_post(
                    state_root=state_root,
                    generation_digest=generation.digest,
                    reviewed_files_digest=digest,
                )
            print(
                "status=G064_ARM_OFF_EXIT_ONLY_MONITORING_NO_POST "
                "entry_gate_open=false broker_write=false actual_post_count=0"
            )
            if preheld_process_lock is None:
                clear_g064_worker_lease(
                    state_root=state_root, expected_pid=os.getpid()
                )
            return 0
        try:
            session = prepare_g013_canary_session(
                repository=repository, now_utc=datetime.now(UTC)
            )
        except canary_module.V4GmoG013CanaryError as error:
            print(f"status=UNATTENDED_SCHEDULER_TICK_NOT_YET reason_label={error}")
            return 0
        except V4GmoFormalCanarySourceError as error:
            if str(error) != "G013_FORMAL_SIGNAL_STAY":
                raise
            print(
                "status=UNATTENDED_SCHEDULER_TICK_NOT_YET "
                "reason_label=G013_FORMAL_SIGNAL_STAY "
                "broker_write=false actual_post_count=0"
            )
            return 0

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
            policy=v4_unattended_runtime_heartbeat_policy(),
        )

        # G064 switch-only runtime never constructs credentials, clients, or
        # notification transports. Legacy generations retain their existing
        # explicit caller-supplied boundary.
        if generation.generation_label == G064_GENERATION_LABEL:
            credential_pair = None
            client = None
            notification_primary = None
            notification_secondary = None
        else:
            from app.services.h11_v4_gmo_actual_transport import (
                V4GmoKeychainCredentialPair,
            )

            credential_pair = V4GmoKeychainCredentialPair()
            client = httpx.Client(timeout=5.0)
            notification_primary = H11V4ActualPushoverTransport(
                credentials=H11V4NotificationCredentialBundle(),
                client=httpx.Client(timeout=10.0),
            )
            notification_secondary = H11V4ActualEmailTransport(
                credentials=H11V4NotificationCredentialBundle(),
            )

        # G064 retains process.lock for the resident worker and records the
        # same owner PID. Legacy generations release the preflight lock before
        # entering their existing inner binding.
        if generation.generation_label == G064_GENERATION_LABEL:
            write_g064_worker_lease(
                state_root=state_root,
                generation_digest=generation.digest,
                reviewed_files_digest=digest,
                now_utc=datetime.now(UTC),
            )
        else:
            lock.release()
            lock_held = False
        try:
            result = bounded_run.main(
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
                arm_intent=arm_check.armed,
            )
            if generation.generation_label == G064_GENERATION_LABEL and all(
                hasattr(result, name)
                for name in (
                    "flat_reconciled",
                    "exact_protection_confirmed",
                    "ownership_exact",
                    "quantity_matches",
                )
            ):
                write_g064_position_reconciliation_no_post(
                    state_root=state_root,
                    generation_digest=generation.digest,
                    position_open=not bool(getattr(result, "flat_reconciled", False)),
                    protection_confirmed=bool(
                        getattr(result, "exact_protection_confirmed", False)
                    ),
                    ownership_exact=bool(getattr(result, "ownership_exact", False)),
                    quantity_matches=bool(getattr(result, "quantity_matches", False)),
                    generation_bound=True,
                    observed_at_utc=datetime.now(UTC),
                )
            return result
        finally:
            if (
                generation.generation_label == G064_GENERATION_LABEL
                and preheld_process_lock is None
            ):
                clear_g064_worker_lease(state_root=state_root, expected_pid=os.getpid())
    finally:
        if lock_held:
            lock.release()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-reviewed-files-digest", required=True)
    parser.add_argument("--expected-generation-digest", required=True)
    if "--help" in argv or "-h" in argv:
        return _run_one_tick(argv)
    args = parser.parse_args(argv)
    try:
        _, generation = _verify_baked_digests(
            repository=args.repository.resolve(),
            expected_reviewed_files_digest=args.expected_reviewed_files_digest,
            expected_generation_digest=args.expected_generation_digest,
        )
    except Exception:  # noqa: BLE001
        if _latch_g064_halt_after_binding_failure(
            repository=args.repository.resolve(),
            expected_generation_digest=args.expected_generation_digest,
            expected_reviewed_files_digest=args.expected_reviewed_files_digest,
        ):
            print(
                "status=G064_RESIDENT_RUNTIME_HALTED "
                "broker_write=false actual_post_count=0"
            )
        else:
            print(
                "status=G064_RESIDENT_RUNTIME_HALT_NOT_WRITTEN "
                "broker_write=false actual_post_count=0"
            )
        return 2
    if getattr(generation, "generation_label", "") != G064_GENERATION_LABEL:
        return _run_one_tick(argv)
    state_root = v4_gmo_runtime_state_root(
        repository=args.repository.resolve(), generation_digest=generation.digest
    )
    resident_lock = H11AutoProcessLock(state_root / "process.lock")
    if not resident_lock.acquire():
        print(
            "status=G064_RESIDENT_WORKER_LOCK_HELD "
            "broker_write=false actual_post_count=0"
        )
        return 0
    try:
        while True:
            try:
                tick_status = _run_one_tick(
                    argv, preheld_process_lock=resident_lock
                )
                if tick_status != 0:
                    return tick_status
            except BaseException:  # noqa: BLE001
                try:
                    write_g064_persistent_halt_no_post(
                        state_root=state_root,
                        generation_digest=generation.digest,
                        reviewed_files_digest=generation.implementation_digest,
                    )
                except V4G064ActivationError:
                    print(
                        "status=G064_RESIDENT_RUNTIME_HALT_NOT_WRITTEN "
                        "broker_write=false actual_post_count=0"
                    )
                    return 2
                print(
                    "status=G064_RESIDENT_RUNTIME_HALTED "
                    "broker_write=false actual_post_count=0"
                )
                return 2
            time.sleep(15)
    finally:
        clear_g064_worker_lease(
            state_root=state_root, expected_pid=os.getpid()
        )
        resident_lock.release()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
