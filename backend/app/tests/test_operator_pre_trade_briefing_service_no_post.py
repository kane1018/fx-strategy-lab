"""No-POST tests for the operator pre-trade briefing service (read-only façade)."""

from __future__ import annotations

import inspect
from dataclasses import fields

from app.services import operator_pre_trade_briefing_service as module
from app.services import operator_pre_trade_caution_briefing as bmod
from app.services.operator_briefing_safe_label_supply import (
    InputCompleteness,
    SafeLabelSupplyRequest,
)
from app.services.operator_pre_trade_briefing_service import (
    OperatorPreTradeBriefingBundle,
    produce_operator_pre_trade_briefing,
    render_operator_pre_trade_briefing,
)

_ScopeMatch = bmod.TestedScopeMatch


def _full_valid() -> SafeLabelSupplyRequest:
    return SafeLabelSupplyRequest(
        exposure_status="FLAT",
        pending_order_safe_count=0,
        risk_budget_status="WITHIN_BUDGET",
        execution_readiness="READY",
        trend_range="RANGING",
        volatility="NORMAL",
        spread_condition="NORMAL",
        liquidity="NORMAL",
        time_of_day="TOKYO",
        event_proximity="NONE",
        uncertainty="NORMAL",
        intended_context_labels=(),
    )


class TestProduce:
    def test_full_valid_bundle(self) -> None:
        b = produce_operator_pre_trade_briefing(_full_valid())
        assert b.input_completeness is InputCompleteness.COMPLETE
        assert b.supply_cautions == ()
        assert b.briefing.no_action_status is bmod.NoActionStatus.NO_ACTION_DEFAULT
        assert b.briefing.hard_stop_present is False
        assert bool(b) is False
        assert b.performance_proof_status is False
        assert b.live_ready is False
        assert b.is_recommendation is False
        assert b.provides_direction is False

    def test_all_unknown_bundle_is_strong_no_action(self) -> None:
        b = produce_operator_pre_trade_briefing(SafeLabelSupplyRequest())
        assert b.input_completeness is InputCompleteness.MOSTLY_UNKNOWN
        assert b.supply_cautions
        assert b.briefing.hard_stop_present is True
        assert b.briefing.no_action_status is (
            bmod.NoActionStatus.NO_ACTION_STRONGLY_INDICATED
        )

    def test_context_resembles_rejected(self) -> None:
        b = produce_operator_pre_trade_briefing(
            SafeLabelSupplyRequest(
                **{
                    **_full_valid().__dict__,
                    "intended_context_labels": ("VOL_REGIME_CONDITIONAL_BREAKOUT",),
                }
            )
        )
        assert b.briefing.tested_scope_match is _ScopeMatch.RESEMBLES_REJECTED

    def test_is_deterministic(self) -> None:
        req = _full_valid()
        assert produce_operator_pre_trade_briefing(req) == (
            produce_operator_pre_trade_briefing(req)
        )


class TestRender:
    def test_combined_text_is_warning_first_and_safe(self) -> None:
        text = render_operator_pre_trade_briefing(_full_valid())
        assert "read-only, not advice" in text
        assert text.index("[0] INPUT / SUPPLY") < text.index("[1] DISCLAIMER")
        assert "no-flag != permission" in text
        assert "[2] NO_ACTION" in text

    def test_render_has_no_recommendation_fragments(self) -> None:
        for req in (
            _full_valid(),
            SafeLabelSupplyRequest(),
            SafeLabelSupplyRequest(
                **{
                    **_full_valid().__dict__,
                    "intended_context_labels": ("VOL_REGIME_CONDITIONAL_BREAKOUT", "made_up"),
                }
            ),
        ):
            lowered = render_operator_pre_trade_briefing(req).lower()
            for frag in ("今は買い", "今は売り", "buy推奨", "sell推奨", "confidence=",
                         "win_rate=", "expected_profit=", "good setup",
                         "opportunity now"):
                assert frag.lower() not in lowered

    def test_supply_cautions_surface_in_combined_text(self) -> None:
        text = render_operator_pre_trade_briefing(SafeLabelSupplyRequest())
        assert "EXPOSURE_STATUS_UNKNOWN_TREATED_AS_CAUTION" in text


class TestBundleInvariants:
    def test_no_direction_confidence_or_raw_fields(self) -> None:
        names = {f.name for f in fields(OperatorPreTradeBriefingBundle)}
        for banned in (
            "direction", "confidence", "alpha", "expected_profit", "win_rate",
            "signal", "recommendation", "side", "buy", "sell", "entry", "score",
            "price", "pnl", "raw_size", "account_id", "order_id",
            "transaction_id", "position_id", "trade_id",
        ):
            assert banned not in names


class TestModuleIsolation:
    def test_no_network_venue_env_or_execution_surface(self) -> None:
        source = inspect.getsource(module)
        for token in (
            "httpx", "requests", "urllib", "socket", "os.environ", "getenv",
            "dotenv", "open(", ".post(", ".get(", "/private/v1",
            "live_order_once", "live_verification",
            "assert_real_broker_post_allowed", "actual_entry_POST",
            "settlement_POST", "broker", "credential", "fetch_candles",
            "import_historical",
        ):
            assert token not in source
