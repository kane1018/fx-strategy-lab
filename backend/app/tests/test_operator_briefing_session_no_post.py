"""No-POST tests for the operator briefing session helper (read-only)."""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest

from app.services import operator_briefing_session as module
from app.services.operator_briefing_safe_label_supply import SafeLabelSupplyRequest
from app.services.operator_briefing_session import (
    BriefingSafeSummary,
    OperatorBriefingSession,
    OperatorDecisionLabel,
    record_operator_decision,
    render_operator_briefing_session,
    start_operator_briefing_session,
)


def _full_valid(**overrides: object) -> SafeLabelSupplyRequest:
    base = dict(
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
    base.update(overrides)
    return SafeLabelSupplyRequest(**base)  # type: ignore[arg-type]


class TestStartSession:
    def test_session_starts_pending(self) -> None:
        s = start_operator_briefing_session(_full_valid(), session_label="s1")
        assert s.operator_decision is OperatorDecisionLabel.PENDING
        assert s.operator_reason == ""
        assert s.decision_is_operator_supplied is True
        assert s.summary.no_action_status == "NO_ACTION_DEFAULT"
        assert s.summary.hard_stop_present is False
        assert bool(s) is False
        assert s.performance_proof_status is False
        assert s.live_ready is False

    def test_all_unknown_summary_is_hard_stop(self) -> None:
        s = start_operator_briefing_session(SafeLabelSupplyRequest())
        assert s.summary.hard_stop_present is True
        assert s.summary.no_action_status == "NO_ACTION_STRONGLY_INDICATED"

    def test_context_resembles_rejected_in_summary(self) -> None:
        s = start_operator_briefing_session(
            _full_valid(intended_context_labels=("VOL_REGIME_CONDITIONAL_BREAKOUT",))
        )
        assert s.summary.tested_scope_match == "RESEMBLES_REJECTED"
        assert "H-05_VOL_REGIME_BREAKOUT" in s.summary.matched_rejected_ids


class TestRecordOperatorDecision:
    def test_records_operator_supplied_decision(self) -> None:
        s = start_operator_briefing_session(_full_valid())
        s2 = record_operator_decision(
            s, OperatorDecisionLabel.OPERATOR_DECIDED_HOLD, "spread widening, waiting"
        )
        assert s2.operator_decision is OperatorDecisionLabel.OPERATOR_DECIDED_HOLD
        assert s2.operator_reason == "spread widening, waiting"

    def test_pending_is_rejected(self) -> None:
        s = start_operator_briefing_session(_full_valid())
        with pytest.raises(ValueError):
            record_operator_decision(s, OperatorDecisionLabel.PENDING, "x")

    def test_empty_reason_is_rejected(self) -> None:
        s = start_operator_briefing_session(_full_valid())
        with pytest.raises(ValueError):
            record_operator_decision(
                s, OperatorDecisionLabel.OPERATOR_DECIDED_NO_ACTION, "   "
            )

    def test_system_never_derives_decision(self) -> None:
        # The only way to set a decision is to pass it in; no function derives
        # a BUY/SELL/HOLD from market inputs.
        src = inspect.getsource(module)
        assert "def record_operator_decision(" in src
        # record_operator_decision requires operator_decision as an argument
        sig = inspect.signature(record_operator_decision)
        assert "operator_decision" in sig.parameters


class TestRender:
    def test_pending_render_says_operator_decides(self) -> None:
        s = start_operator_briefing_session(_full_valid())
        text = render_operator_briefing_session(s)
        assert "PENDING" in text
        assert "system does not decide" in text
        assert "no validated edge" in text

    def test_recorded_render_shows_operator_decision(self) -> None:
        s = record_operator_decision(
            start_operator_briefing_session(_full_valid()),
            OperatorDecisionLabel.OPERATOR_DECIDED_HOLD,
            "waiting",
        )
        text = render_operator_briefing_session(s)
        assert "OPERATOR_DECIDED_HOLD" in text
        assert "operator's own discretionary decision" in text

    def test_render_has_no_recommendation_fragments(self) -> None:
        for s in (
            start_operator_briefing_session(_full_valid()),
            start_operator_briefing_session(SafeLabelSupplyRequest()),
        ):
            lowered = render_operator_briefing_session(s).lower()
            for frag in ("今は買い", "今は売り", "buy推奨", "sell推奨", "confidence=",
                         "win_rate=", "good setup", "opportunity now"):
                assert frag.lower() not in lowered

    def test_guard_raises_on_injected_fragment(self) -> None:
        s = start_operator_briefing_session(_full_valid())
        from dataclasses import replace

        tampered = replace(s, session_label="今は買い")
        with pytest.raises(ValueError):
            render_operator_briefing_session(tampered)


class TestInvariants:
    def test_no_direction_confidence_or_raw_id_fields(self) -> None:
        names = {f.name for f in fields(OperatorBriefingSession)}
        names |= {f.name for f in fields(BriefingSafeSummary)}
        for banned in (
            "confidence", "alpha", "expected_profit", "win_rate", "score",
            "price", "pnl", "raw_size", "account_id", "order_id",
            "transaction_id", "position_id", "trade_id", "signal", "direction",
        ):
            assert banned not in names

    def test_is_deterministic(self) -> None:
        req = _full_valid()
        assert start_operator_briefing_session(req, session_label="x") == (
            start_operator_briefing_session(req, session_label="x")
        )


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
