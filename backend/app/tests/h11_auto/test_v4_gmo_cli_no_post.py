from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.v4_gmo_contracts import V4GmoCycleState, V4GmoExecutionPolicy
from app.h11_auto.v4_gmo_persistence import V4GmoStateStore
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from scripts.h11_auto_v4_gmo_no_post_run import main as run_main
from scripts.h11_auto_v4_gmo_operator_reload_no_post import main as reload_main
from scripts.h11_auto_v4_gmo_safe_report import main as report_main


def _policy() -> V4GmoExecutionPolicy:
    return V4GmoExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:v4-cli-signal",
        selected_horizon=FormalHorizon.MINUTES_10,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def test_fake_only_cli_accepts_one_sanitized_formal_signal_and_reports_safe_json(
    tmp_path: Path, capsys
) -> None:
    now = datetime.now(UTC)
    input_path = tmp_path / "signal.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "horizon": "10m",
                "direction": "BUY",
                "status": "OK",
                "p_up": "0.61",
                "origin_time_utc": now.isoformat(),
                "model_config_hash": "sha256:v4-cli-signal",
                "recorded_mode": "PROSPECTIVE",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    state_dir = tmp_path / "runtime"
    result = run_main(
        [
            "--mode",
            "signal",
            "--signals",
            str(input_path),
            "--state-dir",
            str(state_dir),
            "--strategy-version",
            "SHORT_V1",
            "--signal-config-hash",
            "sha256:v4-cli-signal",
            "--horizon",
            "10m",
            "--generation-label",
            "H11_V4_GMO_10M_G001",
            "--scenario",
            "FULL_FILL_PROTECTED",
        ]
    )
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "POSITION_PROTECTED_SYNTHETIC"
    assert payload["actual_post_count"] == 0
    assert payload["broker_write_performed"] is False
    assert payload["credential_read_performed"] is False
    assert payload["network_access_performed"] is False

    assert report_main(
        ["--state", str(state_dir / "v4_state.sqlite3"), "--format", "json"]
    ) == 0
    aggregate = json.loads(capsys.readouterr().out)
    assert aggregate["report_status"] == "READY"
    assert aggregate["protected_cycle_count"] == 1


def test_operator_reload_cli_clears_only_halted_fake_flat_state(
    tmp_path: Path, capsys
) -> None:
    now = datetime.now(UTC)
    state_path = tmp_path / "v4.sqlite3"
    store = V4GmoStateStore(state_path)
    signal = FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash="sha256:v4-cli-signal",
        horizon=FormalHorizon.MINUTES_10,
        observed_at_utc=now,
        valid_until_utc=now + timedelta(minutes=10),
        decision=SignalDecision.BUY,
        probability_up=Decimal("0.61"),
    )
    cycle = store.create_cycle(signal=signal, policy=_policy(), now_utc=now)
    store.transition(
        cycle_ref=cycle.cycle_ref,
        target=V4GmoCycleState.HALTED_OPERATOR_REVIEW_REQUIRED,
        event_category="HALTED_OPERATOR_REVIEW_REQUIRED",
        now_utc=now,
        halt_reason="SYNTHETIC_TEST_HALT",
    )
    result = reload_main(
        [
            "--state",
            str(state_path),
            "--lock",
            str(tmp_path / "v4.lock"),
            "--confirmation",
            "H11_V4_GMO_OPERATOR_RELOAD_NO_POST",
            "--synthetic-snapshot",
            "FLAT",
        ]
    )
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "CLEARED_NO_POST"
    assert payload["action_attempt_count"] == 0
    assert payload["actual_post_count"] == 0
    assert store.load_cycle(cycle.cycle_ref).state is V4GmoCycleState.OPERATOR_RELOAD_CLEARED
