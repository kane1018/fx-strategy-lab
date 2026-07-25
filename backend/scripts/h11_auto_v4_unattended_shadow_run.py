#!/usr/bin/env python3
"""Bounded, finite H-11 v4 Public-only shadow runner (structurally no-POST).

This driver runs a fixed number of finite cycles.  Each cycle performs one
Public-only observation and records one non-authorizing shadow decision in the
generation-independent SQLite ledger under ``backend/shadow_exports``.  It is
not a resident process, scheduler, cron, or daemon; it exits after the requested
cycle budget.  It never touches a broker, credential, notification, or the
G013 canary / post-canary state, and it prints only sanitized aggregates.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from app.h11_auto.contracts import FormalHorizon
from app.h11_auto.persistence import H11AutoPersistenceError
from app.h11_auto.v4_gmo_contracts import V4GmoExecutionPolicy
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.h11_auto.v4_unattended_shadow_controller import (
    V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH,
    V4UnattendedShadowError,
    V4UnattendedShadowStore,
    run_v4_unattended_shadow_cycle_once,
)
from app.h11_manual.data import DEFAULT_DATA_ROOT
from app.h11_manual.short_model import ShortModelArtifact
from app.services.h11_v4_unattended_shadow_public_adapter import (
    V4_UNATTENDED_SHADOW_STRATEGY_VERSION,
    V4UnattendedShadowPublicError,
    observe_public_shadow_cycle,
)

# Absolute default so the run works regardless of the caller's cwd; it resolves
# to <repo>/backend/shadow_exports/unattended_shadow, matching the confinement
# root the adapter and controller derive from their own __file__.
_DEFAULT_SHADOW_ROOT = (
    Path(__file__).resolve().parents[1] / "shadow_exports" / "unattended_shadow"
)
_MAXIMUM_CYCLES = 240
_MAXIMUM_INTERVAL_SECONDS = 3_600.0
# IO-class errors from the store/ledger that must degrade to a fixed safe label
# rather than leak an unsanitized message or abort the bounded run.
_UNEXPECTED_IO_ERRORS = (sqlite3.Error, H11AutoPersistenceError, OSError)


def _frozen_policy() -> V4GmoExecutionPolicy:
    return V4GmoExecutionPolicy(
        strategy_version=V4_UNATTENDED_SHADOW_STRATEGY_VERSION,
        signal_config_hash=V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH,
        selected_horizon=FormalHorizon.MINUTES_30,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def _safe_error(status: str) -> dict[str, object]:
    return {
        "status": status,
        "blocked_reasons": [],
        "recorded": False,
        "shadow_intent_created": False,
        "broker_post_authorized": False,
        "actual_post_count": 0,
        "broker_read_performed": False,
        "broker_write_performed": False,
        "credential_read_performed": False,
        "network_access_performed": False,
        "live_ready": False,
        "unattended_live_supported": False,
    }


def _run_one_cycle(
    *,
    shadow_root: Path,
    store: V4UnattendedShadowStore,
    policy: V4GmoExecutionPolicy,
    artifact: ShortModelArtifact,
    now_utc: datetime,
) -> dict[str, object]:
    try:
        observation = observe_public_shadow_cycle(
            slot_state_root=shadow_root / "slots",
            artifact=artifact,
            now_utc=now_utc,
        )
        report = run_v4_unattended_shadow_cycle_once(
            signal=observation.signal,
            policy=policy,
            snapshot=observation.snapshot,
            store=store,
            lock_path=shadow_root / "shadow.lock",
            now_utc=now_utc,
        )
    except (V4UnattendedShadowPublicError, V4UnattendedShadowError) as error:
        # These carry fixed safe UPPERCASE labels only.
        return _safe_error(str(error))
    except _UNEXPECTED_IO_ERRORS:
        # A transient store/ledger IO error must not abort the bounded run and
        # must not leak an unsanitized message.
        return _safe_error("SHADOW_PUBLIC_CYCLE_IO_ERROR")
    return report.to_safe_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded, finite, no-POST H-11 v4 Public-only shadow.",
    )
    parser.add_argument("--max-cycles", type=int, required=True)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--shadow-root", type=Path, default=_DEFAULT_SHADOW_ROOT)
    parser.add_argument(
        "--model-path",
        type=Path,
        default=DEFAULT_DATA_ROOT / "short_model_artifact.json",
    )
    args = parser.parse_args(argv)

    if not 1 <= args.max_cycles <= _MAXIMUM_CYCLES:
        parser.error(f"--max-cycles must be between 1 and {_MAXIMUM_CYCLES}")
    if not 0.0 <= args.interval_seconds <= _MAXIMUM_INTERVAL_SECONDS:
        parser.error(
            f"--interval-seconds must be between 0 and {_MAXIMUM_INTERVAL_SECONDS}"
        )

    shadow_root = args.shadow_root.resolve()
    try:
        artifact = ShortModelArtifact.load(args.model_path)
    except Exception:
        # Any malformed model file (missing keys, wrong types, bad JSON, IO)
        # degrades to one fixed safe label; no path or key name is leaked.
        print(json.dumps(_safe_error("SHADOW_PUBLIC_MODEL_INPUT_INVALID"), sort_keys=True))
        return 2
    try:
        store = V4UnattendedShadowStore(shadow_root / "shadow.sqlite3")
    except V4UnattendedShadowError as error:
        print(json.dumps(_safe_error(str(error)), sort_keys=True))
        return 2
    except _UNEXPECTED_IO_ERRORS:
        print(json.dumps(_safe_error("SHADOW_PUBLIC_STORE_INIT_FAILED"), sort_keys=True))
        return 2

    policy = _frozen_policy()
    for index in range(args.max_cycles):
        result = _run_one_cycle(
            shadow_root=shadow_root,
            store=store,
            policy=policy,
            artifact=artifact,
            now_utc=datetime.now(UTC),
        )
        print(json.dumps({"cycle": index, **result}, sort_keys=True))
        sys.stdout.flush()
        if index + 1 < args.max_cycles and args.interval_seconds > 0:
            time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
