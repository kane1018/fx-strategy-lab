"""No-POST tests for the unattended monitoring guard."""

from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

from app.services import gmo_unattended_monitoring_guard as module
from app.services.gmo_unattended_monitoring_guard import (
    ActivePendingOrderSafeStatus,
    ConsecutiveFailureStatus,
    MarketSafeStatus,
    MaxHoldStatus,
    MaxLossStatus,
    PaperTransportStatus,
    PositionCountSafeStatus,
    RuntimePositionSafeStatus,
    SpreadSafeStatus,
    StateConsistencyStatus,
    TickerFreshStatus,
    UnattendedGuardDecision,
    UnattendedMonitoringGuardSafeSnapshot,
    UnknownEventStatus,
    build_all_safe_guard_snapshot,
    evaluate_unattended_monitoring_guard,
)


def _snap(**overrides) -> UnattendedMonitoringGuardSafeSnapshot:
    return replace(build_all_safe_guard_snapshot(), **overrides)


class TestGuardPass:
    def test_all_safe_snapshot_passes(self) -> None:
        result = evaluate_unattended_monitoring_guard(
            build_all_safe_guard_snapshot()
        )
        assert result.decision is UnattendedGuardDecision.GUARD_PASS
        assert result.halted is False
        assert result.halt_causes == ()

    def test_pass_is_never_an_actual_permission(self) -> None:
        result = evaluate_unattended_monitoring_guard(
            build_all_safe_guard_snapshot()
        )
        assert result.guard_pass_is_actual_permission is False
        assert result.live_post_allowed is False
        assert result.actual_entry_POST_allowed is False
        assert result.actual_settlement_POST_allowed is False
        assert not result

    def test_one_position_open_count_one_is_also_safe(self) -> None:
        result = evaluate_unattended_monitoring_guard(
            _snap(
                runtime_position_safe_status=(
                    RuntimePositionSafeStatus.ONE_POSITION_OPEN
                ),
                position_count_safe=PositionCountSafeStatus.COUNT_ONE,
            )
        )
        assert result.decision is UnattendedGuardDecision.GUARD_PASS


class TestGuardHalts:
    @pytest.mark.parametrize(
        ("overrides", "decision"),
        [
            (
                {"kill_switch_engaged": True},
                UnattendedGuardDecision.GUARD_HALT_KILL_SWITCH,
            ),
            (
                {"kill_switch_engaged": None},
                UnattendedGuardDecision.GUARD_HALT_KILL_SWITCH,
            ),
            (
                {"market_safe_status": MarketSafeStatus.MARKET_UNSAFE},
                UnattendedGuardDecision.GUARD_HALT_MARKET_UNSAFE,
            ),
            (
                {"market_safe_status": MarketSafeStatus.MARKET_UNKNOWN},
                UnattendedGuardDecision.GUARD_HALT_MARKET_UNSAFE,
            ),
            (
                {"ticker_fresh_status": TickerFreshStatus.TICKER_STALE},
                UnattendedGuardDecision.GUARD_HALT_TICKER_STALE,
            ),
            (
                {"ticker_fresh_status": TickerFreshStatus.TICKER_UNKNOWN},
                UnattendedGuardDecision.GUARD_HALT_TICKER_STALE,
            ),
            (
                {"spread_safe_status": SpreadSafeStatus.SPREAD_OUT_OF_LIMIT},
                UnattendedGuardDecision.GUARD_HALT_SPREAD_OUT_OF_LIMIT,
            ),
            (
                {"spread_safe_status": SpreadSafeStatus.SPREAD_UNKNOWN},
                UnattendedGuardDecision.GUARD_HALT_SPREAD_OUT_OF_LIMIT,
            ),
            (
                {
                    "runtime_position_safe_status": (
                        RuntimePositionSafeStatus.MULTIPLE_POSITIONS_OPEN
                    )
                },
                UnattendedGuardDecision.GUARD_HALT_POSITION_COUNT_MISMATCH,
            ),
            (
                {
                    "runtime_position_safe_status": (
                        RuntimePositionSafeStatus.POSITION_UNKNOWN
                    )
                },
                UnattendedGuardDecision.GUARD_HALT_POSITION_COUNT_MISMATCH,
            ),
            (
                {"position_count_safe": PositionCountSafeStatus.COUNT_MISMATCH},
                UnattendedGuardDecision.GUARD_HALT_POSITION_COUNT_MISMATCH,
            ),
            (
                {"position_count_safe": PositionCountSafeStatus.COUNT_UNKNOWN},
                UnattendedGuardDecision.GUARD_HALT_POSITION_COUNT_MISMATCH,
            ),
            (
                {
                    "active_pending_order_safe_status": (
                        ActivePendingOrderSafeStatus.ACTIVE_PENDING_ORDERS_PRESENT
                    )
                },
                UnattendedGuardDecision.GUARD_HALT_ACTIVE_PENDING_PRESENT,
            ),
            (
                {
                    "active_pending_order_safe_status": (
                        ActivePendingOrderSafeStatus.ACTIVE_PENDING_ORDERS_UNKNOWN
                    )
                },
                UnattendedGuardDecision.GUARD_HALT_ACTIVE_PENDING_PRESENT,
            ),
            (
                {"max_hold_status": MaxHoldStatus.HOLD_LIMIT_EXCEEDED},
                UnattendedGuardDecision.GUARD_HALT_MAX_HOLD_EXCEEDED,
            ),
            (
                {"max_hold_status": MaxHoldStatus.HOLD_UNKNOWN},
                UnattendedGuardDecision.GUARD_HALT_MAX_HOLD_EXCEEDED,
            ),
            (
                {"max_loss_status": MaxLossStatus.LOSS_LIMIT_EXCEEDED},
                UnattendedGuardDecision.GUARD_HALT_MAX_LOSS_EXCEEDED,
            ),
            (
                {"max_loss_status": MaxLossStatus.LOSS_UNKNOWN},
                UnattendedGuardDecision.GUARD_HALT_MAX_LOSS_EXCEEDED,
            ),
            (
                {
                    "consecutive_failure_status": (
                        ConsecutiveFailureStatus.FAILURE_LIMIT_EXCEEDED
                    )
                },
                UnattendedGuardDecision.GUARD_HALT_FAILURE_LIMIT,
            ),
            (
                {"unknown_event_status": UnknownEventStatus.UNKNOWN_PRESENT},
                UnattendedGuardDecision.GUARD_HALT_UNKNOWN_EVENT,
            ),
            (
                {
                    "paper_transport_status": (
                        PaperTransportStatus.REAL_TRANSPORT_BLOCKED
                    )
                },
                UnattendedGuardDecision.GUARD_HALT_REAL_TRANSPORT,
            ),
            (
                {"paper_transport_status": PaperTransportStatus.TRANSPORT_UNKNOWN},
                UnattendedGuardDecision.GUARD_HALT_REAL_TRANSPORT,
            ),
            (
                {
                    "state_consistency_status": (
                        StateConsistencyStatus.STATE_INCONSISTENT
                    )
                },
                UnattendedGuardDecision.GUARD_HALT_STATE_INCONSISTENT,
            ),
        ],
    )
    def test_each_unsafe_or_unknown_dimension_halts(
        self, overrides, decision
    ) -> None:
        result = evaluate_unattended_monitoring_guard(_snap(**overrides))
        assert result.halted is True
        assert result.decision is decision
        assert result.live_post_allowed is False

    def test_default_snapshot_is_fully_unknown_and_halts(self) -> None:
        result = evaluate_unattended_monitoring_guard(
            UnattendedMonitoringGuardSafeSnapshot()
        )
        assert result.halted is True
        assert result.decision is UnattendedGuardDecision.GUARD_HALT_KILL_SWITCH

    def test_multiple_causes_ranked_by_fixed_priority(self) -> None:
        result = evaluate_unattended_monitoring_guard(
            _snap(
                kill_switch_engaged=True,
                spread_safe_status=SpreadSafeStatus.SPREAD_OUT_OF_LIMIT,
                max_loss_status=MaxLossStatus.LOSS_LIMIT_EXCEEDED,
            )
        )
        assert result.decision is UnattendedGuardDecision.GUARD_HALT_KILL_SWITCH
        assert result.halt_causes == (
            UnattendedGuardDecision.GUARD_HALT_KILL_SWITCH,
            UnattendedGuardDecision.GUARD_HALT_SPREAD_OUT_OF_LIMIT,
            UnattendedGuardDecision.GUARD_HALT_MAX_LOSS_EXCEEDED,
        )


class TestModuleIsolation:
    def test_snapshot_has_no_raw_value_fields(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "requests" not in source
        assert "build_auth_headers" not in source
        assert "/private/v1" not in source
