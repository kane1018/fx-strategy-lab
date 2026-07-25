"""Public-only, credential-free entry-gate provider for the unattended scheduler.

Discharges design doc §13's deferred "future work, not this slice" note: a
non-raising raw status+ticker reader wired to the existing
``derive_unattended_entry_gate_blocked_reasons``, usable as the bounded
runner's ``entry_gate_reason_provider``. Reuses the already-reviewed G013
status/ticker parsing (``_market_open``/``_usd_jpy_ticker``) rather than
duplicating it, so any future schema fix lands in one place.

Performs exactly one status GET and one ticker GET per call -- no retry, no
credential, no Private API, no broker write. Any fetch or parse failure
collapses to ``(ENTRY_GATE_QUOTE_UNAVAILABLE,)`` (design doc §13.2): a
raising provider aborts the whole bounded run, and a market/network hiccup
is a routine "not yet", never a programming error.
"""

from __future__ import annotations

from datetime import datetime

import httpx

from app.services.h11_v4_gmo_public_preflight import (
    GMO_V4_PUBLIC_BASE_URL,
    GMO_V4_PUBLIC_STATUS_PATH,
    GMO_V4_PUBLIC_TICKER_PATH,
    V4GmoFinitePublicPreflight,
    V4GmoPublicPreflightError,
    _market_open,
    _usd_jpy_ticker,
)
from app.services.h11_v4_unattended_live_entry_gate import (
    ENTRY_GATE_QUOTE_UNAVAILABLE,
    derive_unattended_entry_gate_blocked_reasons,
)


def unattended_live_entry_gate_provider(
    now_utc: datetime,
    *,
    client: httpx.Client | None = None,
) -> tuple[str, ...]:
    """One status GET, one ticker GET; never raises for a market/network cause.

    ``market_open`` is the conjunction of the /status endpoint and the
    ticker row's own status (the same combined semantic the G013 path
    applies), matching the provider-author note in
    ``h11_v4_unattended_live_entry_gate``'s module docstring.
    """

    selected = client or httpx.Client(base_url=GMO_V4_PUBLIC_BASE_URL, timeout=5.0)
    owns_client = client is None
    try:
        status_response = V4GmoFinitePublicPreflight._get_once(
            selected, GMO_V4_PUBLIC_STATUS_PATH
        )
        market_open = _market_open(status_response)
        ticker_response = V4GmoFinitePublicPreflight._get_once(
            selected, GMO_V4_PUBLIC_TICKER_PATH
        )
        ticker = _usd_jpy_ticker(ticker_response)
    except V4GmoPublicPreflightError:
        return (ENTRY_GATE_QUOTE_UNAVAILABLE,)
    finally:
        if owns_client:
            selected.close()
    return derive_unattended_entry_gate_blocked_reasons(
        bid=ticker.bid,
        ask=ticker.ask,
        quote_observed_at_utc=ticker.timestamp,
        market_open=market_open and ticker.status_open,
        now_utc=now_utc,
    )
