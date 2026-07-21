from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.h11_auto import v4_activation_preparation as preparation_module
from app.h11_auto.contracts import FormalHorizon
from app.h11_auto.v4_activation_preparation import (
    V4AccountExclusivityObservation,
    V4AccountOwnershipMode,
    V4ActivationPreparationError,
    V4ApprovedOperatorSelections,
    V4CadenceMethod,
    V4ClockObservation,
    V4HostSelection,
    V4NotificationRoute,
    V4PrivateApiCadenceGate,
    assess_v4_clock,
    evaluate_v4_account_exclusivity,
    v4_reconciliation_get_offsets_seconds,
)


def test_approved_operator_selections_are_frozen_and_not_activation() -> None:
    selected = V4ApprovedOperatorSelections()
    assert selected.selected_horizon is FormalHorizon.MINUTES_30
    assert selected.strategy_version == "SHORT_V1"
    assert selected.signal_config_hash.startswith("sha256:")
    assert selected.per_trade_loss_bound_jpy == 5_000
    assert selected.daily_loss_limit_jpy == 10_000
    assert selected.monthly_loss_limit_jpy == 50_000
    assert selected.maximum_consecutive_losses == 5
    assert selected.maximum_entries_per_day == 1
    assert selected.heartbeat_interval_seconds == 15
    assert selected.maximum_heartbeat_age_seconds == 60
    assert selected.account_ownership is V4AccountOwnershipMode.EXCLUSIVE_DURING_AUTO
    assert selected.host_selection is V4HostSelection.CURRENT_MAC_SUPERVISED_FAKE_REHEARSAL
    assert selected.primary_notification is V4NotificationRoute.PUSHOVER
    assert selected.secondary_notification is V4NotificationRoute.EMAIL
    assert selected.actual_activation_allowed is False
    assert selected.digest.startswith("sha256:")
    assert bool(selected) is False

    with pytest.raises(V4ActivationPreparationError, match="cannot be changed"):
        replace(selected, selected_horizon=FormalHorizon.MINUTES_10)


def test_account_exclusivity_requires_no_manual_or_unowned_activity() -> None:
    clear = evaluate_v4_account_exclusivity(
        V4AccountExclusivityObservation(
            broker_snapshot_known=True,
            manual_trade_session_active=False,
            other_private_api_client_active=False,
            unowned_position_count=0,
            unowned_active_order_count=0,
        )
    )
    assert clear.ready is True
    assert clear.halt_required is False
    assert clear.actual_activation_allowed is False

    blocked = evaluate_v4_account_exclusivity(
        V4AccountExclusivityObservation(
            broker_snapshot_known=True,
            manual_trade_session_active=True,
            other_private_api_client_active=True,
            unowned_position_count=1,
            unowned_active_order_count=2,
        )
    )
    assert blocked.ready is False
    assert blocked.halt_required is True
    assert blocked.reasons == (
        "MANUAL_TRADE_SESSION_ACTIVE",
        "OTHER_PRIVATE_API_CLIENT_ACTIVE",
        "UNOWNED_POSITION_PRESENT",
        "UNOWNED_ACTIVE_ORDER_PRESENT",
    )


def test_private_api_cadence_is_conservative_and_never_queues_or_retries() -> None:
    gate = V4PrivateApiCadenceGate()
    assert v4_reconciliation_get_offsets_seconds() == (0.0, 0.55, 1.10)
    assert gate.admit(method=V4CadenceMethod.PRIVATE_GET, now_monotonic=10.0) is True
    assert gate.admit(method=V4CadenceMethod.PRIVATE_GET, now_monotonic=10.49) is False
    assert gate.admit(method=V4CadenceMethod.PRIVATE_GET, now_monotonic=10.50) is True
    assert gate.admit(method=V4CadenceMethod.PRIVATE_POST, now_monotonic=20.0) is True
    assert gate.admit(method=V4CadenceMethod.PRIVATE_POST, now_monotonic=21.09) is False
    assert gate.admit(method=V4CadenceMethod.PRIVATE_POST, now_monotonic=21.10) is True
    assert gate.admit(method=V4CadenceMethod.PRIVATE_POST, now_monotonic=20.0) is False

    # Cross-method backstop: a POST too soon after a GET (and vice versa) is
    # refused even though each per-method interval alone would admit it —
    # exactly the burst shape behind both 2026-07-21 unknown-result incidents.
    burst = V4PrivateApiCadenceGate()
    assert burst.admit(method=V4CadenceMethod.PRIVATE_GET, now_monotonic=50.0) is True
    assert burst.admit(method=V4CadenceMethod.PRIVATE_POST, now_monotonic=50.5) is False
    assert burst.admit(method=V4CadenceMethod.PRIVATE_POST, now_monotonic=51.0) is True
    assert burst.admit(method=V4CadenceMethod.PRIVATE_GET, now_monotonic=51.5) is False
    assert burst.admit(method=V4CadenceMethod.PRIVATE_GET, now_monotonic=52.0) is True

    with pytest.raises(V4ActivationPreparationError, match="GET cadence"):
        V4PrivateApiCadenceGate(get_minimum_interval_seconds=0.49)
    with pytest.raises(V4ActivationPreparationError, match="POST cadence"):
        V4PrivateApiCadenceGate(post_minimum_interval_seconds=1.0)
    with pytest.raises(V4ActivationPreparationError, match="cross cadence"):
        V4PrivateApiCadenceGate(cross_minimum_interval_seconds=0.99)


def test_clock_monitor_fails_closed_on_unknown_skew_or_backward_time() -> None:
    now = datetime(2026, 7, 15, 0, 0, tzinfo=UTC)
    clear = assess_v4_clock(
        V4ClockObservation(
            wall_time_utc=now,
            monotonic_seconds=101.0,
            previous_wall_time_utc=now - timedelta(seconds=1),
            previous_monotonic_seconds=100.0,
            system_clock_sync_known=True,
            absolute_clock_skew_seconds=0.5,
        )
    )
    assert clear.synchronized is True
    assert clear.skew_bucket == "AT_MOST_ONE_SECOND"

    blocked = assess_v4_clock(
        V4ClockObservation(
            wall_time_utc=now - timedelta(seconds=2),
            monotonic_seconds=100.0,
            previous_wall_time_utc=now,
            previous_monotonic_seconds=100.0,
            system_clock_sync_known=False,
            absolute_clock_skew_seconds=None,
        )
    )
    assert blocked.halt_required is True
    assert blocked.reasons == (
        "CLOCK_SYNC_UNKNOWN",
        "CLOCK_SKEW_UNKNOWN",
        "WALL_CLOCK_MOVED_BACKWARDS",
        "MONOTONIC_CLOCK_NOT_PROGRESSING",
    )


def test_preparation_module_has_no_network_credential_or_activation_bridge() -> None:
    source = inspect.getsource(preparation_module)
    forbidden = (
        "httpx",
        "requests.",
        "urllib",
        "socket",
        "subprocess",
        "Keychain",
        "os.environ",
        "os.getenv",
        "ENABLE_LIVE_TRADING",
        "assert_real_broker_post_allowed",
        "V4GmoActualActivationPermit",
        "allow_real_broker_post",
    )
    for marker in forbidden:
        assert marker not in source
