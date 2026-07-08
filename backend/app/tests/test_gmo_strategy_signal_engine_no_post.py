"""No-POST tests for the deterministic strategy signal engine."""

from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

from app.services import gmo_strategy_signal_engine as module
from app.services.gmo_paper_auto_cycle_runner import AutoPreviewSignal
from app.services.gmo_strategy_signal_engine import (
    GuardSafeLabel,
    MarketSafeLabel,
    MomentumSafeLabel,
    PositionContextSafeLabel,
    SessionSafeLabel,
    SpreadSafeLabel,
    StrategyDecisionCategory,
    StrategySignalSafeInput,
    TickerFreshSafeLabel,
    TrendSafeLabel,
    VolatilitySafeLabel,
    build_all_safe_entry_context_input,
    evaluate_strategy_signal,
)


def _input(trend: TrendSafeLabel, momentum: MomentumSafeLabel):
    return build_all_safe_entry_context_input(
        trend_safe_label=trend, momentum_safe_label=momentum
    )


class TestTrendMomentumRules:
    def test_clear_uptrend_yields_buy_preview(self) -> None:
        decision = evaluate_strategy_signal(
            _input(TrendSafeLabel.UPTREND, MomentumSafeLabel.MOMENTUM_UP)
        )
        assert decision.auto_preview_signal is (
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY
        )
        assert decision.strategy_decision_category is (
            StrategyDecisionCategory.ENTRY_PREVIEW_PROPOSED
        )
        assert decision.rule_path_safe_label == (
            "RULE_UPTREND_MOMENTUM_ALIGNED_BUY"
        )

    def test_clear_downtrend_yields_sell_preview(self) -> None:
        decision = evaluate_strategy_signal(
            _input(TrendSafeLabel.DOWNTREND, MomentumSafeLabel.MOMENTUM_DOWN)
        )
        assert decision.auto_preview_signal is (
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL
        )

    @pytest.mark.parametrize(
        "momentum",
        [
            MomentumSafeLabel.MOMENTUM_UP,
            MomentumSafeLabel.MOMENTUM_DOWN,
            MomentumSafeLabel.MOMENTUM_FLAT,
        ],
    )
    def test_range_yields_hold(self, momentum: MomentumSafeLabel) -> None:
        decision = evaluate_strategy_signal(_input(TrendSafeLabel.RANGE, momentum))
        assert decision.auto_preview_signal is (
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD
        )
        assert decision.strategy_decision_category is (
            StrategyDecisionCategory.HOLD_NO_ORDER
        )

    @pytest.mark.parametrize(
        ("trend", "momentum"),
        [
            (TrendSafeLabel.UPTREND, MomentumSafeLabel.MOMENTUM_DOWN),
            (TrendSafeLabel.DOWNTREND, MomentumSafeLabel.MOMENTUM_UP),
        ],
    )
    def test_trend_momentum_conflict_yields_hold(self, trend, momentum) -> None:
        decision = evaluate_strategy_signal(_input(trend, momentum))
        assert decision.auto_preview_signal is (
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD
        )
        assert decision.rule_path_safe_label == (
            "RULE_TREND_MOMENTUM_CONFLICT_HOLD"
        )

    @pytest.mark.parametrize(
        "trend",
        [TrendSafeLabel.TREND_UNKNOWN, TrendSafeLabel.TREND_CONFLICT],
    )
    def test_non_derivable_trend_blocks(self, trend: TrendSafeLabel) -> None:
        decision = evaluate_strategy_signal(
            _input(trend, MomentumSafeLabel.MOMENTUM_UP)
        )
        assert decision.auto_preview_signal is (
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED
        )
        assert decision.strategy_decision_category is (
            StrategyDecisionCategory.BLOCKED_FAIL_CLOSED
        )

    def test_momentum_unknown_blocks(self) -> None:
        decision = evaluate_strategy_signal(
            _input(TrendSafeLabel.UPTREND, MomentumSafeLabel.MOMENTUM_UNKNOWN)
        )
        assert decision.block_reason_safe_label == "BLOCK_MOMENTUM_UNKNOWN"


class TestEnvironmentGates:
    @pytest.mark.parametrize(
        ("overrides", "reason"),
        [
            (
                {"spread_safe_label": SpreadSafeLabel.SPREAD_OUT_OF_LIMIT},
                "BLOCK_SPREAD_NOT_WITHIN_LIMIT",
            ),
            (
                {"spread_safe_label": SpreadSafeLabel.SPREAD_UNKNOWN},
                "BLOCK_SPREAD_NOT_WITHIN_LIMIT",
            ),
            (
                {"ticker_fresh_safe_label": TickerFreshSafeLabel.TICKER_STALE},
                "BLOCK_TICKER_NOT_FRESH",
            ),
            (
                {"market_safe_label": MarketSafeLabel.MARKET_UNSAFE},
                "BLOCK_MARKET_NOT_SAFE",
            ),
            (
                {"session_safe_label": SessionSafeLabel.SESSION_BLOCKED},
                "BLOCK_SESSION_NOT_ALLOWED",
            ),
            (
                {"session_safe_label": SessionSafeLabel.SESSION_UNKNOWN},
                "BLOCK_SESSION_NOT_ALLOWED",
            ),
            (
                {
                    "volatility_safe_label": (
                        VolatilitySafeLabel.VOLATILITY_HIGH_BLOCKED
                    )
                },
                "BLOCK_VOLATILITY_NOT_NORMAL",
            ),
            (
                {"guard_safe_label": GuardSafeLabel.GUARD_HALT},
                "BLOCK_GUARD_NOT_PASS",
            ),
            (
                {"guard_safe_label": GuardSafeLabel.GUARD_UNKNOWN},
                "BLOCK_GUARD_NOT_PASS",
            ),
        ],
    )
    def test_each_unsafe_environment_gate_blocks(self, overrides, reason) -> None:
        base = _input(TrendSafeLabel.UPTREND, MomentumSafeLabel.MOMENTUM_UP)
        decision = evaluate_strategy_signal(replace(base, **overrides))
        assert decision.auto_preview_signal is (
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED
        )
        assert decision.block_reason_safe_label == reason
        assert decision.rule_path_safe_label == "RULE_ENVIRONMENT_GATE_BLOCKED"

    def test_fully_default_input_blocks(self) -> None:
        decision = evaluate_strategy_signal(StrategySignalSafeInput())
        assert decision.auto_preview_signal is (
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED
        )


class TestPositionContext:
    def test_one_position_context_blocks_entry_preview(self) -> None:
        base = _input(TrendSafeLabel.UPTREND, MomentumSafeLabel.MOMENTUM_UP)
        decision = evaluate_strategy_signal(
            replace(
                base,
                position_context_safe_label=(
                    PositionContextSafeLabel.ONE_POSITION_CONTEXT
                ),
            )
        )
        assert decision.strategy_decision_category is (
            StrategyDecisionCategory.SETTLEMENT_PREVIEW_CONTEXT_ONLY
        )
        assert decision.auto_preview_signal is (
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD
        )
        assert decision.block_reason_safe_label == (
            "ENTRY_PREVIEW_BLOCKED_POSITION_ALREADY_OPEN"
        )

    def test_unknown_position_context_blocks(self) -> None:
        base = _input(TrendSafeLabel.UPTREND, MomentumSafeLabel.MOMENTUM_UP)
        decision = evaluate_strategy_signal(
            replace(
                base,
                position_context_safe_label=(
                    PositionContextSafeLabel.POSITION_CONTEXT_UNKNOWN
                ),
            )
        )
        assert decision.strategy_decision_category is (
            StrategyDecisionCategory.BLOCKED_FAIL_CLOSED
        )


class TestDecisionSafety:
    def test_decision_is_never_permission_or_operator_signal(self) -> None:
        decision = evaluate_strategy_signal(
            _input(TrendSafeLabel.UPTREND, MomentumSafeLabel.MOMENTUM_UP)
        )
        assert decision.auto_preview_signal_is_operator_signal is False
        assert decision.actual_entry_POST_allowed is False
        assert decision.actual_settlement_POST_allowed is False
        assert decision.order_attempt_created is False
        assert decision.raw_id_value_exposure is False
        assert decision.auto_preview_signal.value not in (
            "ENTRY_BUY",
            "ENTRY_SELL",
            "HOLD",
        )
        assert not decision

    def test_entry_preview_lists_required_names_only(self) -> None:
        decision = evaluate_strategy_signal(
            _input(TrendSafeLabel.UPTREND, MomentumSafeLabel.MOMENTUM_UP)
        )
        assert decision.required_future_gate_names
        assert (
            "operator_current_turn_exact_confirmation"
            in decision.required_operator_input_names
        )
        assert decision.why_not_permission

    def test_hold_and_blocked_list_no_gate_names(self) -> None:
        hold = evaluate_strategy_signal(
            _input(TrendSafeLabel.RANGE, MomentumSafeLabel.MOMENTUM_FLAT)
        )
        assert hold.required_future_gate_names == ()
        blocked = evaluate_strategy_signal(StrategySignalSafeInput())
        assert blocked.required_operator_input_names == ()

    def test_engine_is_deterministic(self) -> None:
        signal_input = _input(
            TrendSafeLabel.DOWNTREND, MomentumSafeLabel.MOMENTUM_FLAT
        )
        assert evaluate_strategy_signal(signal_input) == evaluate_strategy_signal(
            signal_input
        )


class TestModuleIsolation:
    def test_module_has_no_broker_env_or_raw_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "requests" not in source
        assert "/private/v1" not in source
        assert "build_auth_headers" not in source
        assert "random" not in source
