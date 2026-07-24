"""H-11 v4 unattended live entry-gate derivation (Public-only, credential-free).

Discharges the credential-free half of design doc §9.2 item 4: derives
``entry_gate_blocked_reasons`` from primary quote facts (bid/ask/timestamp)
against the SAME frozen thresholds the human-interactive G013 flow already
uses, re-derived here rather than trusting any caller-computed boolean —
the same trust-no-precomputed-flags principle behind §9.1's VETO fix and
§10.2's Option A decision. ``market_open`` alone is accepted as a
strictly-typed bool, since exchange status cannot be re-derived from a
quote.

This module performs no network access, reads no credential, and invents
no threshold — the three gate constants are imported from
``h11_v4_gmo_public_preflight`` (the operator-frozen values), never
duplicated. The quote fetch itself stays with the caller; a provider whose
fetch fails should return ``(ENTRY_GATE_QUOTE_UNAVAILABLE,)`` rather than
raising (design doc §13.2 — a raising provider aborts the bounded run).

Provider-author notes (design doc §13.1a): ``market_open`` must be the
CONJUNCTION of the /status endpoint being OPEN and the ticker row's own
status being open — the same combined semantic the G013 path applies
(``market_open and ticker.status_open``); passing only the /status half
silently weakens the gate. And note ``read_g013_final_quote_once`` RAISES
on any blocked gate rather than returning the quote, so a provider built
on it must catch ``V4GmoPublicPreflightError`` and map every failure to
the collapsed ``ENTRY_GATE_QUOTE_UNAVAILABLE`` label — this module's four
distinct labels only become reachable once a non-raising raw-quote reader
exists (future work, not this slice).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal

from app.services.h11_v4_gmo_public_preflight import (
    G013_MAXIMUM_ENTRY_SPREAD_PIPS,
    MAXIMUM_QUOTE_AGE_SECONDS,
    MAXIMUM_QUOTE_CLOCK_SKEW_SECONDS,
)

# For providers whose own quote fetch failed: a blocking reason to RETURN
# (never to raise) so the bounded runner treats the cycle as a routine
# "not yet" instead of aborting — the fetch failing is a market/network
# condition, not a programming error.
ENTRY_GATE_QUOTE_UNAVAILABLE = "ENTRY_GATE_QUOTE_UNAVAILABLE"


class V4UnattendedLiveEntryGateError(RuntimeError):
    """Fixed safe entry-gate derivation failure containing safe labels only."""


def derive_unattended_entry_gate_blocked_reasons(
    *,
    bid: Decimal,
    ask: Decimal,
    quote_observed_at_utc: datetime,
    market_open: bool,
    now_utc: datetime,
) -> tuple[str, ...]:
    """Derive blocking reasons from primary quote facts; empty tuple = clear.

    Malformed *types* raise (a programming error must abort, not block);
    malformed quote *values* (non-finite, non-positive, inverted) block via
    ``ENTRY_GATE_QUOTE_INVALID`` (bad exchange data must fail closed, not
    crash a runner loop). The freshness window is the same asymmetric
    ``[-MAXIMUM_QUOTE_CLOCK_SKEW_SECONDS, +MAXIMUM_QUOTE_AGE_SECONDS]``
    range the frozen G013 gate applies (skew-ahead tolerance and staleness
    bound are separate constants that merely happen to share a value
    today); spread is evaluated only on a numerically valid quote.
    """

    if (
        type(market_open) is not bool
        or not isinstance(bid, Decimal)
        or not isinstance(ask, Decimal)
        or not isinstance(quote_observed_at_utc, datetime)
        or not isinstance(now_utc, datetime)
    ):
        raise V4UnattendedLiveEntryGateError("ENTRY_GATE_INPUT_INVALID")
    if quote_observed_at_utc.tzinfo is None or now_utc.tzinfo is None:
        raise V4UnattendedLiveEntryGateError("ENTRY_GATE_CLOCK_INVALID")

    reasons: list[str] = []
    if not market_open:
        reasons.append("ENTRY_GATE_MARKET_NOT_OPEN")

    age = (
        now_utc.astimezone(UTC) - quote_observed_at_utc.astimezone(UTC)
    ).total_seconds()
    if not (
        math.isfinite(age)
        and -MAXIMUM_QUOTE_CLOCK_SKEW_SECONDS <= age <= MAXIMUM_QUOTE_AGE_SECONDS
    ):
        reasons.append("ENTRY_GATE_QUOTE_NOT_FRESH")

    # is_finite() checks must short-circuit before any comparison: comparing
    # a Decimal NaN raises InvalidOperation rather than returning False.
    if not bid.is_finite() or not ask.is_finite() or bid <= 0 or ask < bid:
        reasons.append("ENTRY_GATE_QUOTE_INVALID")
    else:
        spread_pips = (ask - bid) / Decimal("0.01")
        if spread_pips > G013_MAXIMUM_ENTRY_SPREAD_PIPS:
            reasons.append("ENTRY_GATE_SPREAD_LIMIT_EXCEEDED")
    return tuple(reasons)
