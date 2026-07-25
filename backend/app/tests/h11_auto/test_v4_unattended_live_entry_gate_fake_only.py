from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.services import h11_v4_unattended_live_entry_gate as subject
from app.services.h11_v4_gmo_public_preflight import (
    G013_MAXIMUM_ENTRY_SPREAD_PIPS,
    MAXIMUM_QUOTE_AGE_SECONDS,
    MAXIMUM_QUOTE_CLOCK_SKEW_SECONDS,
)
from app.services.h11_v4_unattended_live_permit_decision import _validate_safe_reason

_NOW = datetime(2026, 7, 24, 1, 0, tzinfo=UTC)


def _derive(**overrides: object) -> tuple[str, ...]:
    values: dict[str, object] = {
        "bid": Decimal("160.000"),
        "ask": Decimal("160.005"),
        "quote_observed_at_utc": _NOW - timedelta(seconds=1),
        "market_open": True,
        "now_utc": _NOW,
    }
    values.update(overrides)
    return subject.derive_unattended_entry_gate_blocked_reasons(**values)  # type: ignore[arg-type]


def test_clear_market_returns_empty_tuple() -> None:
    assert _derive() == ()


def test_market_not_open_blocks() -> None:
    assert "ENTRY_GATE_MARKET_NOT_OPEN" in _derive(market_open=False)


def test_stale_quote_blocks_exactly_beyond_the_frozen_age_limit() -> None:
    at_limit = _derive(
        quote_observed_at_utc=_NOW - timedelta(seconds=MAXIMUM_QUOTE_AGE_SECONDS)
    )
    assert at_limit == ()
    beyond = _derive(
        quote_observed_at_utc=_NOW
        - timedelta(seconds=MAXIMUM_QUOTE_AGE_SECONDS + 0.001)
    )
    assert "ENTRY_GATE_QUOTE_NOT_FRESH" in beyond


def test_clock_skew_tolerated_exactly_up_to_the_frozen_limit() -> None:
    ahead_at_limit = _derive(
        quote_observed_at_utc=_NOW
        + timedelta(seconds=MAXIMUM_QUOTE_CLOCK_SKEW_SECONDS)
    )
    assert ahead_at_limit == ()
    ahead_beyond = _derive(
        quote_observed_at_utc=_NOW
        + timedelta(seconds=MAXIMUM_QUOTE_CLOCK_SKEW_SECONDS + 0.001)
    )
    assert "ENTRY_GATE_QUOTE_NOT_FRESH" in ahead_beyond


def test_spread_blocks_exactly_beyond_the_frozen_limit() -> None:
    limit_ask = Decimal("160.000") + G013_MAXIMUM_ENTRY_SPREAD_PIPS * Decimal("0.01")
    assert _derive(ask=limit_ask) == ()
    assert "ENTRY_GATE_SPREAD_LIMIT_EXCEEDED" in _derive(
        ask=limit_ask + Decimal("0.001")
    )


@pytest.mark.parametrize(
    ("bid", "ask"),
    (
        (Decimal("0"), Decimal("160.005")),
        (Decimal("-1"), Decimal("160.005")),
        (Decimal("160.010"), Decimal("160.005")),
        (Decimal("NaN"), Decimal("160.005")),
        (Decimal("160.000"), Decimal("Infinity")),
    ),
)
def test_numerically_invalid_quote_blocks_without_raising(
    bid: Decimal, ask: Decimal
) -> None:
    reasons = _derive(bid=bid, ask=ask)
    assert "ENTRY_GATE_QUOTE_INVALID" in reasons
    assert "ENTRY_GATE_SPREAD_LIMIT_EXCEEDED" not in reasons


def test_multiple_conditions_report_together() -> None:
    reasons = _derive(
        market_open=False,
        quote_observed_at_utc=_NOW - timedelta(seconds=600),
        ask=Decimal("160.100"),
    )
    assert set(reasons) == {
        "ENTRY_GATE_MARKET_NOT_OPEN",
        "ENTRY_GATE_QUOTE_NOT_FRESH",
        "ENTRY_GATE_SPREAD_LIMIT_EXCEEDED",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("market_open", 1),
        ("market_open", "yes"),
        ("bid", 160.0),
        ("ask", "160.005"),
        ("quote_observed_at_utc", "2026-07-24"),
        ("now_utc", None),
    ),
)
def test_type_invalid_inputs_raise_rather_than_block(
    field: str, value: object
) -> None:
    with pytest.raises(
        subject.V4UnattendedLiveEntryGateError, match="ENTRY_GATE_INPUT_INVALID"
    ):
        _derive(**{field: value})


def test_naive_datetimes_raise() -> None:
    with pytest.raises(
        subject.V4UnattendedLiveEntryGateError, match="ENTRY_GATE_CLOCK_INVALID"
    ):
        _derive(now_utc=datetime(2026, 7, 24, 1, 0))
    with pytest.raises(
        subject.V4UnattendedLiveEntryGateError, match="ENTRY_GATE_CLOCK_INVALID"
    ):
        _derive(quote_observed_at_utc=datetime(2026, 7, 24, 0, 59))


def test_every_producible_label_satisfies_the_decision_layer_safe_charset() -> None:
    # Every label this module can ever emit must pass the permit-decision
    # layer's own safe-reason validation, or a real blocked cycle would be
    # rejected as DECISION_INVALID instead of evaluated.
    for label in (
        "ENTRY_GATE_MARKET_NOT_OPEN",
        "ENTRY_GATE_QUOTE_NOT_FRESH",
        "ENTRY_GATE_QUOTE_INVALID",
        "ENTRY_GATE_SPREAD_LIMIT_EXCEEDED",
        subject.ENTRY_GATE_QUOTE_UNAVAILABLE,
    ):
        _validate_safe_reason(label)


def test_thresholds_are_imported_not_duplicated() -> None:
    source = inspect.getsource(subject)
    # The module must reference the frozen constants by import, never
    # restate their numeric values.
    for forbidden_literal in ("2.0", "5.0"):
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or '"""' in stripped:
                continue
            assert forbidden_literal not in stripped, line


def test_module_performs_no_network_or_credential_access() -> None:
    source = inspect.getsource(subject)
    for token in (
        "httpx",
        "requests",
        "urllib",
        "socket",
        "os.environ",
        "os.getenv",
        "keyring",
        "subprocess",
        "find-generic-password",
    ):
        assert token not in source, token
