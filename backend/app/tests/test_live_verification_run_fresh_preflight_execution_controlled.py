from __future__ import annotations

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
