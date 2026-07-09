"""No-POST tests for the read-only operator briefing CLI."""

from __future__ import annotations

import inspect

import pytest

from app.cli import operator_briefing_cli as module
from app.cli.operator_briefing_cli import main

_FULL_VALID = [
    "--exposure", "FLAT",
    "--pending-count", "0",
    "--risk-budget", "WITHIN_BUDGET",
    "--execution-readiness", "READY",
    "--trend", "RANGING",
    "--volatility", "NORMAL",
    "--spread", "NORMAL",
    "--liquidity", "NORMAL",
    "--time-of-day", "TOKYO",
    "--event", "NONE",
    "--uncertainty", "NORMAL",
]


class TestMain:
    def test_no_args_fail_closed_strong_no_action(self, capsys) -> None:
        rc = main([])
        assert rc == 0
        out = capsys.readouterr().out
        assert "not advice" in out
        assert "no-flag != permission" in out
        assert "NO_ACTION_STRONGLY_INDICATED" in out
        assert "PENDING" in out

    def test_full_valid_is_no_action_default(self, capsys) -> None:
        rc = main(_FULL_VALID)
        assert rc == 0
        out = capsys.readouterr().out
        assert "NO_ACTION_DEFAULT" in out
        assert "PENDING" in out

    def test_records_operator_decision(self, capsys) -> None:
        rc = main([*_FULL_VALID, "--decision", "HOLD", "--reason", "waiting"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "OPERATOR_DECIDED_HOLD" in out
        assert "operator's own discretionary decision" in out

    def test_context_label_surfaces_rejected_caution(self, capsys) -> None:
        rc = main([*_FULL_VALID, "--context", "VOL_REGIME_CONDITIONAL_BREAKOUT"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "RESEMBLES_REJECTED" in out

    def test_decision_without_reason_errors(self) -> None:
        with pytest.raises(SystemExit):
            main(["--decision", "HOLD"])

    def test_invalid_decision_errors(self) -> None:
        with pytest.raises(SystemExit):
            main(["--decision", "MAYBE"])

    def test_output_has_no_recommendation_fragments(self, capsys) -> None:
        main([*_FULL_VALID, "--context", "VOL_REGIME_CONDITIONAL_BREAKOUT",
              "--decision", "NO_ACTION", "--reason", "uncertain"])
        out = capsys.readouterr().out.lower()
        for frag in ("今は買い", "今は売り", "buy推奨", "sell推奨", "confidence=",
                     "win_rate=", "expected_profit=", "good setup",
                     "opportunity now"):
            assert frag.lower() not in out


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
