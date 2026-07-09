"""No-POST tests for the operator briefing safe-label supply (read-only)."""

from __future__ import annotations

import inspect
from dataclasses import fields

from app.services import operator_briefing_safe_label_supply as module
from app.services import operator_pre_trade_caution_briefing as bmod
from app.services.operator_briefing_safe_label_supply import (
    InputCompleteness,
    SafeLabelSupplyRequest,
    SafeLabelSupplyResult,
    build_briefing_inputs,
    build_caution_briefing_from_labels,
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


class TestNormalization:
    def test_full_valid_is_complete_no_cautions(self) -> None:
        r = build_briefing_inputs(_full_valid())
        assert r.input_completeness is InputCompleteness.COMPLETE
        assert r.supply_cautions == ()
        bi = r.briefing_inputs
        assert bi.exposure is bmod.ExposureSafeLabel.FLAT
        assert bi.risk_budget is bmod.RiskBudgetSafeStatus.WITHIN_BUDGET
        assert bi.uncertainty_high is False

    def test_all_none_fails_closed_to_unknown(self) -> None:
        r = build_briefing_inputs(SafeLabelSupplyRequest())
        assert r.input_completeness is InputCompleteness.MOSTLY_UNKNOWN
        assert r.supply_cautions  # non-empty
        bi = r.briefing_inputs
        assert bi.exposure is bmod.ExposureSafeLabel.EXPOSURE_UNKNOWN
        assert bi.risk_budget is bmod.RiskBudgetSafeStatus.BUDGET_UNKNOWN
        assert bi.safe_execution_readiness is (
            bmod.SafeExecutionReadiness.READINESS_UNKNOWN
        )
        assert bi.uncertainty_high is True  # fail-closed

    def test_invalid_string_fails_closed_with_caution(self) -> None:
        r = build_briefing_inputs(
            SafeLabelSupplyRequest(
                **{**_full_valid().__dict__, "exposure_status": "garbage_value"}
            )
        )
        assert r.briefing_inputs.exposure is bmod.ExposureSafeLabel.EXPOSURE_UNKNOWN
        assert "EXPOSURE_STATUS_UNKNOWN_TREATED_AS_CAUTION" in r.supply_cautions

    def test_uncertainty_mapping(self) -> None:
        def unc(v: str | None) -> bool:
            return build_briefing_inputs(
                SafeLabelSupplyRequest(**{**_full_valid().__dict__, "uncertainty": v})
            ).briefing_inputs.uncertainty_high

        assert unc("HIGH") is True
        assert unc("NORMAL") is False
        assert unc(None) is True  # fail-closed
        assert unc("nonsense") is True  # fail-closed


class TestPendingOrders:
    def test_count_used_directly(self) -> None:
        r = build_briefing_inputs(
            SafeLabelSupplyRequest(**{**_full_valid().__dict__, "pending_order_safe_count": 2})
        )
        assert r.briefing_inputs.pending_order_safe_count == 2

    def test_status_present_without_count_assumes_at_least_one(self) -> None:
        r = build_briefing_inputs(
            SafeLabelSupplyRequest(
                exposure_status="FLAT", pending_order_status="PRESENT"
            )
        )
        assert r.briefing_inputs.pending_order_safe_count == 1
        assert any("AT_LEAST_ONE" in c for c in r.supply_cautions)

    def test_unknown_pending_is_caution(self) -> None:
        r = build_briefing_inputs(SafeLabelSupplyRequest(exposure_status="FLAT"))
        assert r.briefing_inputs.pending_order_safe_count == 0
        assert any("PENDING_ORDER_STATUS_UNKNOWN" in c for c in r.supply_cautions)

    def test_bool_count_is_rejected_as_invalid(self) -> None:
        # bool is an int subclass; must not be accepted as a count
        r = build_briefing_inputs(
            SafeLabelSupplyRequest(
                exposure_status="FLAT", pending_order_safe_count=True  # type: ignore[arg-type]
            )
        )
        assert r.briefing_inputs.pending_order_safe_count == 0


class TestRejectedLedgerContext:
    def test_resembles_rejected_via_context_label(self) -> None:
        r, briefing = build_caution_briefing_from_labels(
            SafeLabelSupplyRequest(
                **{
                    **_full_valid().__dict__,
                    "intended_context_labels": ("VOL_REGIME_CONDITIONAL_BREAKOUT",),
                }
            )
        )
        assert briefing.tested_scope_match is _ScopeMatch.RESEMBLES_REJECTED
        assert "H-05_VOL_REGIME_BREAKOUT" in briefing.matched_rejected_ids

    def test_explicit_outside_scope_is_caution_not_permission(self) -> None:
        _, briefing = build_caution_briefing_from_labels(
            SafeLabelSupplyRequest(
                **{**_full_valid().__dict__, "intended_context_labels": ("OUTSIDE_TESTED_SCOPE",)}
            )
        )
        assert briefing.tested_scope_match is _ScopeMatch.OUTSIDE_TESTED_SCOPE
        assert "no-flag != permission" in briefing.tested_scope_note

    def test_unknown_context_is_not_assessed(self) -> None:
        _, briefing = build_caution_briefing_from_labels(
            SafeLabelSupplyRequest(
                **{**_full_valid().__dict__, "intended_context_labels": ("UNKNOWN_CONTEXT",)}
            )
        )
        assert briefing.tested_scope_match is _ScopeMatch.NOT_ASSESSED

    def test_unrecognised_context_is_caution(self) -> None:
        r, briefing = build_caution_briefing_from_labels(
            SafeLabelSupplyRequest(
                **{**_full_valid().__dict__, "intended_context_labels": ("made_up_context",)}
            )
        )
        assert briefing.tested_scope_match is _ScopeMatch.OUTSIDE_TESTED_SCOPE
        assert any("UNRECOGNISED_CONTEXT_LABEL" in c for c in r.supply_cautions)


class TestEndToEndFailClosed:
    def test_all_unknown_briefing_is_strong_no_action(self) -> None:
        _, briefing = build_caution_briefing_from_labels(SafeLabelSupplyRequest())
        assert briefing.hard_stop_present is True
        assert briefing.no_action_status is bmod.NoActionStatus.NO_ACTION_STRONGLY_INDICATED
        assert briefing.no_flag_is_not_permission is True

    def test_full_valid_briefing_is_no_action_default_not_go(self) -> None:
        _, briefing = build_caution_briefing_from_labels(_full_valid())
        assert briefing.hard_stop_present is False
        assert briefing.no_action_status is bmod.NoActionStatus.NO_ACTION_DEFAULT
        assert bool(briefing) is False

    def test_render_has_no_direction_or_recommendation(self) -> None:
        _, briefing = build_caution_briefing_from_labels(_full_valid())
        text = bmod.render_caution_briefing(briefing).lower()
        for frag in ("今は買い", "今は売り", "buy推奨", "sell推奨", "confidence=",
                     "win_rate=", "expected_profit=", "good setup"):
            assert frag.lower() not in text


class TestResultInvariants:
    def test_result_never_truthy_and_flags_false(self) -> None:
        r = build_briefing_inputs(_full_valid())
        assert bool(r) is False
        assert r.performance_proof_status is False
        assert r.live_ready is False

    def test_no_raw_value_id_direction_or_score_fields(self) -> None:
        req_names = {f.name for f in fields(SafeLabelSupplyRequest)}
        res_names = {f.name for f in fields(SafeLabelSupplyResult)}
        for names in (req_names, res_names):
            for banned in (
                "price", "pnl", "raw_size", "spread_value", "account_id",
                "order_id", "transaction_id", "position_id", "trade_id",
                "confidence", "alpha", "win_rate", "expected_profit", "signal",
                "direction", "side", "buy", "sell", "entry", "score",
            ):
                assert banned not in names

    def test_is_deterministic(self) -> None:
        req = _full_valid()
        assert build_briefing_inputs(req) == build_briefing_inputs(req)


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
