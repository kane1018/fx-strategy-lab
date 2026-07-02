from __future__ import annotations

from app.live_verification import run_fresh_preflight_execution_controlled as cli_module
from app.live_verification.live_order_real_fresh_preflight_execution_controlled import (
    FreshPreflightExecutionControlledMode,
    LiveOrderRealFreshPreflightExecutionControlledInput,
    build_live_order_real_fresh_preflight_execution_controlled,
)
from app.live_verification.run_fresh_preflight_execution_controlled import main


def test_cli_adapter_summary_only_outputs_safe_summary(
    capsys,
) -> None:
    exit_code = main(["--adapter-summary-only"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "fresh_preflight_execution_command_available: true" in captured.out
    assert "fresh_preflight_execution_allowed_next_step: true" in captured.out
    assert "fresh_preflight_execution_performed: false" in captured.out
    assert "post_executed: false" in captured.out
    assert "http_post_executed: false" in captured.out
    assert "order_endpoint_called: false" in captured.out
    assert "live_order_once_called: false" in captured.out
    assert "final_confirmation_received: false" in captured.out
    assert "ledger_updated: false" in captured.out
    assert "actual_receipt_handoff_executed: false" in captured.out


def test_cli_default_does_not_execute_fresh_preflight(capsys) -> None:
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "fresh_preflight_execute_mode_available: true" in captured.out
    assert "fresh_preflight_execute_mode_not_run_this_step: true" in captured.out
    assert "fresh_preflight_execution_performed: false" in captured.out
    assert "fresh_preflight_passed: false" in captured.out


def test_cli_execute_once_flag_uses_monkeypatched_safe_summary_only(
    monkeypatch,
    capsys,
) -> None:
    calls = 0

    def fake_execute_once():
        nonlocal calls
        calls += 1
        return build_live_order_real_fresh_preflight_execution_controlled(
            input_snapshot=LiveOrderRealFreshPreflightExecutionControlledInput(
                fresh_preflight_execution_mode=(
                    FreshPreflightExecutionControlledMode
                    .FRESH_PREFLIGHT_EXECUTION_CONTROLLED_SAFE_EXECUTE_ONCE
                    .value
                ),
                fresh_preflight_execution_requested=True,
                fresh_preflight_execute_mode_not_run_this_step=False,
            ),
        )

    monkeypatch.setattr(
        cli_module,
        "execute_live_order_real_fresh_preflight_once_controlled",
        fake_execute_once,
    )

    exit_code = main(["--execute-once", "--safe-summary-only"])

    captured = capsys.readouterr()
    assert calls == 1
    assert exit_code == 0
    assert captured.err == ""
    assert "FRESH_PREFLIGHT_EXECUTION_PASSED_SAFE_SUMMARY" in captured.out
    assert "fresh_preflight_execute_mode_available: true" in captured.out
    assert "fresh_preflight_execute_mode_not_run_this_step: false" in captured.out
    assert "fresh_preflight_execution_performed: true" in captured.out
    assert "fresh_preflight_passed: true" in captured.out
    assert "post_executed: false" in captured.out
    assert "order_endpoint_called: false" in captured.out
    assert "live_order_once_called: false" in captured.out
    assert "final_confirmation_received: false" in captured.out
    assert "ledger_updated: false" in captured.out
    assert "actual_receipt_handoff_executed: false" in captured.out
    for forbidden in (
        "RAW_REQUEST_SHOULD_NOT_SURFACE",
        "RAW_RESPONSE_SHOULD_NOT_SURFACE",
        "API_RESPONSE_SHOULD_NOT_SURFACE",
        "REAL_ID_SHOULD_NOT_SURFACE",
    ):
        assert forbidden not in captured.out


def test_cli_runtime_not_ready_fails_closed_with_safe_summary(
    capsys,
) -> None:
    exit_code = main(["--simulate-runtime-not-ready"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.err == ""
    assert (
        "FRESH_PREFLIGHT_EXECUTION_BLOCKED_MISSING_RUNTIME"
        in captured.out
    )
    assert "fresh_preflight_execution_command_available: false" in captured.out
    assert "fresh_preflight_execution_performed: false" in captured.out
    assert "post_executed: false" in captured.out
    assert "live_order_once_called: false" in captured.out


def test_cli_unknown_argument_returns_safe_usage(capsys) -> None:
    exit_code = main(["--execute"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "run_fresh_preflight_execution_controlled" in captured.err
    assert "raw" not in captured.err.lower()
    assert "credential" not in captured.err.lower()
