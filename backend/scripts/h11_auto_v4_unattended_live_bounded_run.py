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
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.h11_auto import v4_gmo_canary_activation as activation_module
from app.h11_auto.runtime_safety import DeadManStore, PhaseBRiskPolicy, PhaseBRiskStore
from app.services import h11_v4_gmo_g013_canary as canary_module
from app.services import h11_v4_unattended_live_orchestration as orchestration_module
from app.services.h11_v4_g064_unattended_activation import G064_GENERATION_LABEL
from app.services.h11_v4_gmo_actual_transport import V4GmoSealedCredentialPair
from app.services.h11_v4_gmo_g013_canary import V4GmoG013PreparedSession
from app.services.h11_v4_notification_binding_no_post import (
    H11V4EmailTransport,
    H11V4PushoverTransport,
)
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

# Not routine "gate not clear yet" waits, even though their exception type is
# otherwise in the retry-safe list. First two: the reviewed implementation
# digest or frozen generation changed underneath an already-running session --
# an integrity/tamper-drift signal that must never blend into market-timing
# noise. Third: the decision layer rejected its own inputs as malformed
# (e.g. a provider label with a bad charset slipping past the runner's
# element check below) -- always a programming error, never a market
# condition, so retrying it would only burn the cycle budget on repeat
# failures. Fourth: a failed real notification send that already burned this
# run's one prepared session's authorization (§15.2) -- a significant,
# actionable event the operator must see distinctly, and retrying is
# pointless regardless since this run's one session is already spent (a
# separate invocation with a freshly prepared session, later the same day, is
# a different matter -- see the entries-per-day cap enforced independently by
# the risk policy). All must abort the run loudly.
_INTEGRITY_ABORT_LABELS = frozenset(
    {
        "G013_IMPLEMENTATION_CHANGED_BEFORE_PERMIT",
        "G013_GENERATION_CHANGED_BEFORE_PERMIT",
        "V4_CANARY_UNATTENDED_DECISION_INVALID",
        "UNATTENDED_ORCHESTRATION_NOTIFICATION_SEND_FAILED",
    }
)


class V4UnattendedLiveRunnerError(RuntimeError):
    """Programming-error boundary of the runner itself (never caught here).

    Deliberately NOT in ``_EXPECTED_NOT_YET_ERRORS``: a buggy entry-gate
    provider must abort the run loudly, not silently burn the cycle budget
    as repeat "not yet" lines (design doc §13.2, same reasoning as the
    integrity-abort labels above).
    """


def _safe_not_yet(error: BaseException) -> dict[str, object]:
    return {"status": "UNATTENDED_LIVE_CYCLE_NOT_YET", "reason_label": str(error)}


@dataclass(frozen=True)
class _CycleOutcome:
    safe_dict: dict[str, object]
    entry_attempted: bool


def _switch_only_cycle(
    *,
    generation_label: str,
    entry_gate_blocked_reasons: tuple[str, ...],
    arm_intent: bool,
) -> _CycleOutcome:
    """Evaluate a resident switch-only runtime boundary without side effects.

    Resident generations treat persisted ARM ON as runtime intent. The legacy per-trade
    authorization, confirmation, notification, credential, and client path
    is deliberately not entered here. Actual broker transport remains behind
    the separate default-deny activation boundary.
    """

    entry_gate_open = arm_intent and not entry_gate_blocked_reasons
    return _CycleOutcome(
        safe_dict={
            "status": (
                f"{generation_label}_UNATTENDED_SWITCH_ONLY_ENTRY_GATE_EVALUATED_NO_POST"
                if entry_gate_open
                else f"{generation_label}_UNATTENDED_SWITCH_ONLY_ENTRY_GATE_BLOCKED_NO_POST"
            ),
            "runtime_mode": "SWITCH_ONLY",
            "entry_gate_open": entry_gate_open,
            "entry_state": "WAITING" if entry_gate_open else "BLOCKED",
            "authorization_required": False,
            "confirmation_required": False,
            "notification_attempted": False,
            "credential_read": False,
            "private_api_read": False,
            "broker_write": False,
            "broker_post_count": 0,
        },
        entry_attempted=False,
    )


def _g064_switch_only_cycle(
    *, entry_gate_blocked_reasons: tuple[str, ...], arm_intent: bool
) -> _CycleOutcome:
    return _switch_only_cycle(
        generation_label="G064",
        entry_gate_blocked_reasons=entry_gate_blocked_reasons,
        arm_intent=arm_intent,
    )


def _run_one_cycle(
    *,
    session: V4GmoG013PreparedSession,
    risk_store: PhaseBRiskStore,
    risk_policy: PhaseBRiskPolicy,
    dead_man_store: DeadManStore,
    heartbeat_chain_store: V4HeartbeatChainStore,
    notification_primary: H11V4PushoverTransport,
    notification_secondary: H11V4EmailTransport,
    entry_gate_blocked_reasons: tuple[str, ...],
    credential_pair: V4GmoSealedCredentialPair,
    client: httpx.Client,
    now_utc: datetime,
    arm_intent: bool = False,
) -> _CycleOutcome:
    if session.generation.label in {
        G064_GENERATION_LABEL,
        "H11_AUTO_30M_20260801_G065",
    }:
        return _switch_only_cycle(
            generation_label=(
                "G064" if session.generation.label == G064_GENERATION_LABEL else "G065"
            ),
            entry_gate_blocked_reasons=entry_gate_blocked_reasons,
            arm_intent=arm_intent,
        )
    try:
        result = orchestration_module.run_unattended_live_entry_cycle_once(
            session=session,
            risk_store=risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man_store,
            heartbeat_chain_store=heartbeat_chain_store,
            notification_primary=notification_primary,
            notification_secondary=notification_secondary,
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
    notification_primary: H11V4PushoverTransport,
    notification_secondary: H11V4EmailTransport,
    entry_gate_reason_provider: Callable[[datetime], tuple[str, ...]],
    credential_pair: V4GmoSealedCredentialPair,
    client: httpx.Client,
    arm_intent: bool = False,
) -> int:
    """Bounded runner loop; each cycle derives its gate reasons freshly.

    ``entry_gate_reason_provider`` is called exactly once per cycle with
    that cycle's ``now_utc`` and must return a ``tuple`` of safe reason
    labels (empty = clear) -- satisfying §9.2 item 4's "derive from the
    real evaluations in the same cycle" for the credential-free half.
    A provider returning a non-tuple, or raising, aborts the whole run
    (``V4UnattendedLiveRunnerError`` / the provider's own exception) --
    providers must map their own fetch failures to a blocking reason such
    as ``ENTRY_GATE_QUOTE_UNAVAILABLE``, never raise for market/network
    conditions.

    ``notification_primary``/``notification_secondary`` (design doc §15.2)
    are required, no-default caller-constructed transport objects, passed
    through to the orchestration layer unchanged every cycle -- unlike the
    entry-gate reasons, these are not per-cycle-derived values, so no
    provider/callable wrapper is used here. The orchestration layer derives
    the cheap per-cycle channel-ready signal from them and performs the one
    real send at issuance time; a failed send aborts this run loudly (it is
    in ``_INTEGRITY_ABORT_LABELS`` below), never retried.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded, finite unattended H-11 v4 live entry cycle "
            "(at most one entry per invocation, using the single session "
            "supplied to this run -- the entries-per-day cap, now up to "
            "MAXIMUM_ENTRIES_PER_DAY_CEILING, is enforced independently by "
            "the risk policy and may permit further invocations with a "
            "freshly prepared session later the same day)."
        ),
    )
    parser.add_argument("--max-cycles", type=int, required=True)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    args = parser.parse_args(argv)

    if not 1 <= args.max_cycles <= _MAXIMUM_CYCLES:
        parser.error(f"--max-cycles must be between 1 and {_MAXIMUM_CYCLES}")
    if not 0.0 <= args.interval_seconds <= _MAXIMUM_INTERVAL_SECONDS:
        parser.error(f"--interval-seconds must be between 0 and {_MAXIMUM_INTERVAL_SECONDS}")

    for index in range(args.max_cycles):
        now_utc = datetime.now(UTC)
        entry_gate_blocked_reasons = entry_gate_reason_provider(now_utc)
        if type(entry_gate_blocked_reasons) is not tuple or not all(
            type(reason) is str for reason in entry_gate_blocked_reasons
        ):
            raise V4UnattendedLiveRunnerError("UNATTENDED_RUNNER_ENTRY_GATE_PROVIDER_INVALID")
        outcome = _run_one_cycle(
            session=session,
            risk_store=risk_store,
            risk_policy=risk_policy,
            dead_man_store=dead_man_store,
            heartbeat_chain_store=heartbeat_chain_store,
            notification_primary=notification_primary,
            notification_secondary=notification_secondary,
            entry_gate_blocked_reasons=entry_gate_blocked_reasons,
            credential_pair=credential_pair,
            client=client,
            now_utc=now_utc,
            arm_intent=arm_intent,
        )
        # No `default=` fallback: every safe_dict shape this can actually
        # produce today is JSON-native (str/int/bool/None); a future field
        # holding a non-primitive would fail loudly here rather than being
        # silently stringified and printed.
        print(json.dumps({"cycle": index, **outcome.safe_dict}, sort_keys=True))
        sys.stdout.flush()
        if outcome.entry_attempted:
            # This run's one prepared session is spent -- it was built for a
            # single signal, so it cannot produce a second, different entry.
            # Further cycles this run would only hit the gate again. Stop
            # early. A later invocation with a freshly prepared session may
            # still place another entry the same day, up to the
            # entries-per-day cap enforced independently by the risk policy.
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
