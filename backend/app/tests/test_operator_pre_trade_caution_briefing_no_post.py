"""No-POST tests for the operator pre-trade caution briefing (read-only)."""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest

from app.services import operator_pre_trade_caution_briefing as module
from app.services.operator_pre_trade_caution_briefing import (
    BriefingInputs,
    CautionBriefing,
    EventProximitySafeLabel,
    ExposureSafeLabel,
    NoActionStatus,
    RiskBudgetSafeStatus,
    SafeExecutionReadiness,
    SpreadSafeCategory,
    generate_caution_briefing,
    render_caution_briefing,
)

# Referenced via ``module.`` (its name starts with "Test" so importing it into
# this test module would make pytest try to collect the enum as a test class).
_ScopeMatch = module.TestedScopeMatch


def _all_clear_inputs() -> BriefingInputs:
    return BriefingInputs(
        exposure=ExposureSafeLabel.FLAT,
        pending_order_safe_count=0,
        risk_budget=RiskBudgetSafeStatus.WITHIN_BUDGET,
        safe_execution_readiness=SafeExecutionReadiness.READY,
        spread=SpreadSafeCategory.NORMAL,
        event_proximity=EventProximitySafeLabel.NONE,
        uncertainty_high=False,
        intended_context_tags=("intraday", "novel_context"),
    )


class TestNoActionDefault:
    def test_all_clear_is_no_action_default_not_permission(self) -> None:
        b = generate_caution_briefing(_all_clear_inputs())
        assert b.no_action_status is NoActionStatus.NO_ACTION_DEFAULT
        assert b.hard_stop_present is False
        assert b.no_flag_is_not_permission is True
        assert b.is_recommendation is False
        assert b.provides_direction is False
        # even fully clear, it is never a "go"
        assert "NO_ACTION_DEFAULT_SETUP_NOT_A_PERMISSION" in b.no_action_reasons

    def test_default_inputs_fail_closed_to_hard_stops(self) -> None:
        # defaults: unknown exposure/readiness + uncertainty_high => hard stops
        b = generate_caution_briefing(BriefingInputs())
        assert b.hard_stop_present is True
        assert b.no_action_status is NoActionStatus.NO_ACTION_STRONGLY_INDICATED
        assert "HARD_STOP_HIGH_UNCERTAINTY" in b.hard_stop_reasons
        assert "HARD_STOP_INTERNAL_STATE_UNKNOWN" in b.hard_stop_reasons


class TestHardStops:
    def test_spread_abnormal_is_hard_stop(self) -> None:
        inp = _all_clear_inputs()
        inp = BriefingInputs(**{**inp.__dict__, "spread": SpreadSafeCategory.ABNORMAL})
        b = generate_caution_briefing(inp)
        assert b.hard_stop_present is True
        assert "HARD_STOP_SPREAD_ABNORMAL" in b.hard_stop_reasons
        assert b.no_action_status is NoActionStatus.NO_ACTION_STRONGLY_INDICATED

    def test_event_proximity_is_hard_stop(self) -> None:
        inp = BriefingInputs(
            **{
                **_all_clear_inputs().__dict__,
                "event_proximity": EventProximitySafeLabel.NEAR_SCHEDULED_EVENT,
            }
        )
        assert "HARD_STOP_EVENT_PROXIMITY" in generate_caution_briefing(inp).hard_stop_reasons

    def test_budget_exceeded_is_hard_stop(self) -> None:
        inp = BriefingInputs(
            **{
                **_all_clear_inputs().__dict__,
                "risk_budget": RiskBudgetSafeStatus.BUDGET_EXCEEDED,
            }
        )
        assert "HARD_STOP_RISK_BUDGET_EXCEEDED" in generate_caution_briefing(inp).hard_stop_reasons

    def test_budget_unknown_is_fail_closed_hard_stop(self) -> None:
        inp = BriefingInputs(
            **{
                **_all_clear_inputs().__dict__,
                "risk_budget": RiskBudgetSafeStatus.BUDGET_UNKNOWN,
            }
        )
        b = generate_caution_briefing(inp)
        assert "HARD_STOP_RISK_BUDGET_UNKNOWN" in b.hard_stop_reasons
        assert b.no_action_status is NoActionStatus.NO_ACTION_STRONGLY_INDICATED

    def test_event_proximity_unknown_is_fail_closed_hard_stop(self) -> None:
        inp = BriefingInputs(
            **{
                **_all_clear_inputs().__dict__,
                "event_proximity": EventProximitySafeLabel.EVENT_PROXIMITY_UNKNOWN,
            }
        )
        b = generate_caution_briefing(inp)
        assert "HARD_STOP_EVENT_PROXIMITY_UNKNOWN" in b.hard_stop_reasons


class TestRejectedLedgerMatching:
    def test_resembles_rejected_is_caution_only(self) -> None:
        inp = BriefingInputs(
            **{
                **_all_clear_inputs().__dict__,
                "intended_context_tags": ("breakout", "high_vol"),
            }
        )
        b = generate_caution_briefing(inp)
        assert b.tested_scope_match is _ScopeMatch.RESEMBLES_REJECTED
        assert "H-05_VOL_REGIME_BREAKOUT" in b.matched_rejected_ids
        # caution wording, never a direction/permission
        assert "注意喚起" in b.tested_scope_note

    def test_outside_scope_is_not_permission(self) -> None:
        inp = BriefingInputs(
            **{**_all_clear_inputs().__dict__, "intended_context_tags": ("unrelated",)}
        )
        b = generate_caution_briefing(inp)
        assert b.tested_scope_match is _ScopeMatch.OUTSIDE_TESTED_SCOPE
        assert b.matched_rejected_ids == ()
        assert "no-flag != permission" in b.tested_scope_note

    def test_no_tags_is_not_assessed_not_permission(self) -> None:
        inp = BriefingInputs(**{**_all_clear_inputs().__dict__, "intended_context_tags": ()})
        b = generate_caution_briefing(inp)
        assert b.tested_scope_match is _ScopeMatch.NOT_ASSESSED
        assert "no-flag != permission" in b.tested_scope_note


class TestSafetyInvariants:
    def test_never_truthy_and_flags_false(self) -> None:
        b = generate_caution_briefing(_all_clear_inputs())
        assert bool(b) is False
        assert b.performance_proof_status is False
        assert b.live_ready is False

    def test_output_has_no_direction_or_confidence_fields(self) -> None:
        names = {f.name for f in fields(CautionBriefing)}
        for banned in (
            "direction", "confidence", "confidence_score", "alpha", "alpha_score",
            "expected_profit", "win_rate", "signal", "recommendation",
            "auto_preview_signal", "buy", "sell", "score",
        ):
            assert banned not in names

    def test_output_has_no_raw_value_or_id_fields(self) -> None:
        names = {f.name for f in fields(CautionBriefing)}
        for banned in (
            "price", "spread_value", "pnl", "size", "account_id", "order_id",
            "transaction_id", "position_id", "trade_id",
        ):
            assert banned not in names

    def test_is_deterministic(self) -> None:
        inp = _all_clear_inputs()
        assert generate_caution_briefing(inp) == generate_caution_briefing(inp)


class TestRenderer:
    def test_render_is_warning_first(self) -> None:
        text = render_caution_briefing(generate_caution_briefing(_all_clear_inputs()))
        assert text.index("[1] DISCLAIMER") < text.index("[2] NO_ACTION")
        assert text.index("[2] NO_ACTION") < text.index("[6] MARKET-STATE")
        assert "not advice" in text
        assert "no-flag != permission" in text

    def test_render_has_no_recommendation_fragments(self) -> None:
        for inp in (_all_clear_inputs(), BriefingInputs()):
            text = render_caution_briefing(generate_caution_briefing(inp)).lower()
            for frag in ("今は買い", "今は売り", "buy推奨", "sell推奨", "勝てる",
                         "good setup", "opportunity now", "confidence=", "win_rate="):
                assert frag.lower() not in text

    def test_render_guard_raises_on_injected_fragment(self) -> None:
        b = generate_caution_briefing(_all_clear_inputs())
        tampered = CautionBriefing(**{**b.__dict__, "tested_scope_note": "今は買い"})
        with pytest.raises(ValueError):
            render_caution_briefing(tampered)


class TestModuleIsolation:
    def test_no_network_broker_env_or_execution_surface(self) -> None:
        source = inspect.getsource(module)
        for token in (
            "httpx", "requests", "urllib", "socket", "os.environ", "getenv",
            "open(", "/private/v1", "live_order_once", "live_verification",
            "assert_real_broker_post_allowed", "actual_entry_POST",
            "settlement_POST", "broker", "fetch_candles", "import_historical",
        ):
            assert token not in source
