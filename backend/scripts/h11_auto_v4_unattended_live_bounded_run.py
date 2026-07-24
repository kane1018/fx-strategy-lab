#!/usr/bin/env python3
"""Bounded, finite H-11 v4 unattended live entry-cycle runner (fake-only in
this repo's own tests; unwired -- no scheduler, no credential construction).

Mirrors Phase 1's shadow runner structurally: ``--max-cycles``/
``--interval-seconds``, never resident, no auto-restart, exits after the
requested cycle budget. Each cycle calls the already-reviewed
``run_unattended_live_entry_cycle_once`` (six-condition proof constructor
then the proof-accepting G013 driver) at most once.

This file never constructs a real credential pair or a real HTTP client --
``main``'s ``credential_pair``/``client`` are required, no-default
parameters, and there is no ``if __name__ == "__main__":`` path that runs a
real cycle. Real invocation requires a separate, operator-authored launcher
that imports ``main`` directly and supplies both explicitly (design doc
§12.5). Running this file directly explains why and stops there.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.h11_auto import v4_gmo_canary_activation as activation_module
from app.h11_auto.runtime_safety import DeadManStore, PhaseBRiskPolicy, PhaseBRiskStore
from app.services import h11_v4_gmo_g013_canary as canary_module
from app.services import h11_v4_unattended_live_orchestration as orchestration_module
from app.services.h11_v4_gmo_actual_transport import V4GmoSealedCredentialPair
from app.services.h11_v4_gmo_g013_canary import V4GmoG013PreparedSession
from app.services.h11_v4_unattended_live_heartbeat_chain import V4HeartbeatChainStore

_MAXIMUM_CYCLES = 240
_MAXIMUM_INTERVAL_SECONDS = 3_600.0

# Fixed safe-label exception types this call chain can raise for an expected
# "not yet" outcome (gate not clear, authorization not present, session not
# refreshable). Anything else is unexpected and must abort the loop loudly,
# mirroring Phase 1's uniform-safe-degrade-known-errors-only boundary.
_EXPECTED_NOT_YET_ERRORS = (
    activation_module.V4GmoCanaryActivationError,
    orchestration_module.V4UnattendedLiveOrchestrationError,
    canary_module.V4GmoG013CanaryError,
)

# Not routine "gate not clear yet" waits: the reviewed implementation digest
# or the frozen generation changed underneath an already-running session --
# an integrity/tamper-drift signal. Folding these into ordinary retries would
# let a live tamper signal blend into routine market-timing noise for the
# rest of the cycle budget. These must always propagate and abort the loop
# loudly instead, even though their type is otherwise in the retry-safe list.
_INTEGRITY_ABORT_LABELS = frozenset(
    {
        "G013_IMPLEMENTATION_CHANGED_BEFORE_PERMIT",
        "G013_GENERATION_CHANGED_BEFORE_PERMIT",
    }
)


def _safe_not_yet(error: BaseException) -> dict[str, object]:
    return {"status": "UNATTENDED_LIVE_CYCLE_NOT_YET", "reason_label": str(error)}


@dataclass(frozen=True)
class _CycleOutcome:
    safe_dict: dict[str, object]
    entry_attempted: bool


def _run_one_cycle(
    *,
    session: V4GmoG013PreparedSession,
    risk_store: PhaseBRiskStore,
    risk_policy: PhaseBRiskPolicy,
    dead_man_store: DeadManStore,
    heartbeat_chain_store: V4HeartbeatChainStore,
    notification_ready: bool,
    entry_gate_blocked_reasons: tuple[str, ...],
    credential_pair: V4GmoSealedCredentialPair,
    client: httpx.Client,
    now_utc: datetime,
) -> _CycleOutcome:
    try:
        result = orchestration_module.run_unattended_live_entry_cycle_once(
            session=session,
            risk_store=risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man_store,
            heartbeat_chain_store=heartbeat_chain_store,
            notification_ready=notification_ready,
            entry_gate_blocked_reasons=entry_gate_blocked_reasons,
            credential_pair=credential_pair,
            client=client,
            now_utc=now_utc,
        )
    except _EXPECTED_NOT_YET_ERRORS as error:
        if str(error) in _INTEGRITY_ABORT_LABELS:
            raise
        return _CycleOutcome(safe_dict=_safe_not_yet(error), entry_attempted=False)
    return _CycleOutcome(safe_dict=result.to_safe_dict(), entry_attempted=True)


def main(
    argv: list[str],
    *,
    session: V4GmoG013PreparedSession,
    risk_store: PhaseBRiskStore,
    risk_policy: PhaseBRiskPolicy,
    dead_man_store: DeadManStore,
    heartbeat_chain_store: V4HeartbeatChainStore,
    notification_ready: bool,
    entry_gate_blocked_reasons: tuple[str, ...],
    credential_pair: V4GmoSealedCredentialPair,
    client: httpx.Client,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded, finite unattended H-11 v4 live entry cycle "
            "(at most one entry per authorized day)."
        ),
    )
    parser.add_argument("--max-cycles", type=int, required=True)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    args = parser.parse_args(argv)

    if not 1 <= args.max_cycles <= _MAXIMUM_CYCLES:
        parser.error(f"--max-cycles must be between 1 and {_MAXIMUM_CYCLES}")
    if not 0.0 <= args.interval_seconds <= _MAXIMUM_INTERVAL_SECONDS:
        parser.error(
            f"--interval-seconds must be between 0 and {_MAXIMUM_INTERVAL_SECONDS}"
        )

    for index in range(args.max_cycles):
        outcome = _run_one_cycle(
            session=session,
            risk_store=risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man_store,
            heartbeat_chain_store=heartbeat_chain_store,
            notification_ready=notification_ready,
            entry_gate_blocked_reasons=entry_gate_blocked_reasons,
            credential_pair=credential_pair,
            client=client,
            now_utc=datetime.now(UTC),
        )
        # No `default=` fallback: every safe_dict shape this can actually
        # produce today is JSON-native (str/int/bool/None); a future field
        # holding a non-primitive would fail loudly here rather than being
        # silently stringified and printed.
        print(json.dumps({"cycle": index, **outcome.safe_dict}, sort_keys=True))
        sys.stdout.flush()
        if outcome.entry_attempted:
            # The day's one authorization is spent; further cycles this run
            # would only hit the gate again. Stop early.
            return 0
        if index + 1 < args.max_cycles and args.interval_seconds > 0:
            time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(
        "h11_auto_v4_unattended_live_bounded_run.py cannot be run directly: "
        "this file never constructs credential_pair/client (by design -- see "
        "docs/H11_V4_UNATTENDED_LIVE_ADAPTER_DESIGN_20260724.md §12.5). An "
        "operator must import main() from a separate, operator-authored "
        "launcher that supplies both explicitly, along with the session and "
        "store objects."
    )
