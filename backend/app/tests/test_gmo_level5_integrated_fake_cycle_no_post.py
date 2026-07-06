"""No-POST tests for the integrated Level 5 fake cycle.

Unlike test_gmo_level5_fake_cycle_no_post.py (a pure state-machine
simulation), this exercises the real GmoFxBroker skeleton methods with a
refusing fake HTTP client, and now routes through the runner boundary, the
risk_service shadow gate, and settlement reconciliation too. It proves the
default (real-broker) path fails closed end-to-end even when every upstream
gate is fully permissive, and that the separate `simulate_accepted_transport_
for_state_machine_test_only` mode -- which never touches the real broker or
the hard guard's allow flag -- can only reach Level5=true when settlement
reconciliation also confirms NO_POSITION/count=0.
"""

from __future__ import annotations

import pathlib

import pytest

from app.services.gmo_level5_integrated_fake_cycle import (
    GmoLevel5IntegratedCycleInput,
    run_gmo_level5_integrated_fake_cycle,
)
from app.services.gmo_live_runner_boundary import GmoLiveRunnerBoundaryInput
from app.services.gmo_live_safety_policy import (
    GmoLiveEnablePolicyInput,
    GmoLiveKillSwitchState,
    GmoLiveRiskConfig,
)
from app.services.gmo_settlement_reconciliation import GmoSettlementSafeReadSnapshot
from app.services.risk_service import GmoLiveReadinessShadowInput

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_level5_integrated_fake_cycle.py"
)

_ALL_ENABLE_GATES_TRUE = {
    "operator_live_enable_declared": True,
    "post_incident_resume_policy_allowed": True,
    "hard_guard_default_deny_confirmed": True,
    "allow_bridge_absent": True,
    "production_allow_true_wiring_absent": True,
    "risk_config_present": True,
    "kill_switch_present_and_armed": True,
    "paper_evidence_safe_label_present": True,
    "official_settlement_route_required": True,
    "generic_close_forbidden": True,
    "settlement_side_provenance_ready": True,
    "settlement_side_docs_status_classified": True,
    "head_equals_origin_main": True,
    "working_tree_clean": True,
    "fresh_runtime_read_required": True,
    "fresh_operator_confirmation_required": True,
}


def _permissive_runner_input() -> GmoLiveRunnerBoundaryInput:
    return GmoLiveRunnerBoundaryInput(
        process_just_started=False,
        risk_config=GmoLiveRiskConfig(gmo_live_enabled=True),
        live_enable_policy_input=GmoLiveEnablePolicyInput(**_ALL_ENABLE_GATES_TRUE),
        kill_switch_state=GmoLiveKillSwitchState(process_start_default_off=False),
        settlement_side_docs_status_classified=True,
    )


def _permissive_shadow_input() -> GmoLiveReadinessShadowInput:
    return GmoLiveReadinessShadowInput(
        risk_config=GmoLiveRiskConfig(gmo_live_enabled=True),
        live_enable_policy_input=GmoLiveEnablePolicyInput(**_ALL_ENABLE_GATES_TRUE),
        kill_switch_state=GmoLiveKillSwitchState(process_start_default_off=False),
        settlement_side_docs_status_classified=True,
        paper_evidence_safe_label_present=True,
        operator_live_enable_declared=True,
    )


def _permissive_input(**overrides: object) -> GmoLevel5IntegratedCycleInput:
    values: dict[str, object] = {
        "runner_boundary_input": _permissive_runner_input(),
        "shadow_gate_input": _permissive_shadow_input(),
        "manual_intervention_performed": False,
    }
    values.update(overrides)
    return GmoLevel5IntegratedCycleInput(**values)


def _reconciled_snapshot() -> GmoSettlementSafeReadSnapshot:
    return GmoSettlementSafeReadSnapshot(
        safe_read_succeeded=True,
        position_status_safe="NO_POSITION",
        position_count_safe=0,
    )


def test_default_input_blocks_at_upstream_gates() -> None:
    result = run_gmo_level5_integrated_fake_cycle()
    assert result.level5_full_auto_cycle_completed is False
    assert result.entry_attempt_blocked_reason == "upstream_gate_blocked"
    assert "runner_boundary_blocked" in result.blocked_reasons
    assert "risk_shadow_gate_blocked" in result.blocked_reasons


def test_runner_boundary_blocked_stops_before_broker_call() -> None:
    result = run_gmo_level5_integrated_fake_cycle(
        _permissive_input(runner_boundary_input=GmoLiveRunnerBoundaryInput())
    )
    assert result.level5_full_auto_cycle_completed is False
    assert "runner_boundary_blocked" in result.blocked_reasons


def test_risk_shadow_gate_blocked_stops_before_broker_call() -> None:
    result = run_gmo_level5_integrated_fake_cycle(
        _permissive_input(shadow_gate_input=GmoLiveReadinessShadowInput())
    )
    assert result.level5_full_auto_cycle_completed is False
    assert "risk_shadow_gate_blocked" in result.blocked_reasons


def test_manual_intervention_blocks_before_broker_call() -> None:
    result = run_gmo_level5_integrated_fake_cycle(
        _permissive_input(manual_intervention_performed=True)
    )
    assert result.level5_full_auto_cycle_completed is False
    assert "manual_intervention_performed" in result.blocked_reasons


def test_fully_permissive_real_broker_path_still_fails_closed() -> None:
    """Key integration guarantee: with every upstream gate permissive, the
    real GmoFxBroker skeleton must still block before any network call.
    """
    result = run_gmo_level5_integrated_fake_cycle(_permissive_input())
    assert result.level5_full_auto_cycle_completed is False
    assert result.entry_attempt_blocked_reason == "entry_transport_not_available"
    assert result.official_settlement_transport_fails_closed is True


def test_simulate_mode_with_reconciled_snapshot_reaches_level5_true() -> None:
    result = run_gmo_level5_integrated_fake_cycle(
        _permissive_input(
            simulate_accepted_transport_for_state_machine_test_only=True,
            settlement_snapshot=_reconciled_snapshot(),
        )
    )
    assert result.level5_full_auto_cycle_completed is True
    assert result.blocked_reasons == ()


def test_simulate_mode_without_snapshot_blocks() -> None:
    result = run_gmo_level5_integrated_fake_cycle(
        _permissive_input(simulate_accepted_transport_for_state_machine_test_only=True)
    )
    assert result.level5_full_auto_cycle_completed is False
    assert result.entry_attempt_blocked_reason == "settlement_snapshot_missing"


@pytest.mark.parametrize(
    ("position_status", "position_count"),
    [("ONE_POSITION_OPEN", 1), ("MULTIPLE_POSITIONS", 2)],
)
def test_simulate_mode_unreconciled_snapshot_blocks(
    position_status: str, position_count: int,
) -> None:
    result = run_gmo_level5_integrated_fake_cycle(
        _permissive_input(
            simulate_accepted_transport_for_state_machine_test_only=True,
            settlement_snapshot=GmoSettlementSafeReadSnapshot(
                safe_read_succeeded=True,
                position_status_safe=position_status,
                position_count_safe=position_count,
            ),
        )
    )
    assert result.level5_full_auto_cycle_completed is False
    assert result.entry_attempt_blocked_reason == "settlement_not_reconciled"


def test_simulate_mode_settlement_side_docs_not_confirmed_blocks_settlement() -> None:
    result = run_gmo_level5_integrated_fake_cycle(
        _permissive_input(
            runner_boundary_input=GmoLiveRunnerBoundaryInput(
                process_just_started=False,
                risk_config=GmoLiveRiskConfig(gmo_live_enabled=True),
                live_enable_policy_input=GmoLiveEnablePolicyInput(**_ALL_ENABLE_GATES_TRUE),
                kill_switch_state=GmoLiveKillSwitchState(process_start_default_off=False),
                settlement_side_docs_status_classified=False,
            ),
            simulate_accepted_transport_for_state_machine_test_only=True,
            settlement_snapshot=_reconciled_snapshot(),
        )
    )
    assert result.level5_full_auto_cycle_completed is False
    assert result.entry_attempt_blocked_reason == "settlement_gate_blocked"


def test_settlement_reconciliation_rejected_blocks() -> None:
    from app.services.gmo_settlement_reconciliation import (
        GmoSettlementReconciliationInput,
        evaluate_gmo_settlement_reconciliation,
    )

    result = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(settlement_result_category="REJECTED_SANITIZED")
    )
    assert result.reconciled is False


def test_settlement_reconciliation_unknown_or_timeout_blocks() -> None:
    from app.services.gmo_settlement_reconciliation import (
        GmoSettlementReconciliationInput,
        evaluate_gmo_settlement_reconciliation,
    )

    result = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(settlement_result_category="UNKNOWN_SANITIZED")
    )
    assert result.reconciled is False


def test_module_uses_a_refusing_fake_client_never_real_network() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "MockTransport" in text
    assert "AssertionError" in text
    assert "requests.post" not in text


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_has_no_production_allow_true_wiring() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text


def test_simulate_flag_never_true_in_production_code() -> None:
    """The simulate switch is not an allow bridge: it never touches the
    real broker, credentials, or the hard guard. Still, production code
    (non-test files) must never construct it as True -- only test fixtures
    may.
    """
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "simulate_accepted_transport_for_state_machine_test_only=True" not in text


def test_run_cycle_raises_assertion_error_only_if_broker_ever_stops_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail-safe: if a future change makes market_order() stop raising
    without this module being updated, the cycle must not silently report
    success -- it must raise loudly instead.
    """
    import app.services.gmo_level5_integrated_fake_cycle as integrated_cycle_module
    from app.brokers.gmo_fx_broker import BrokerResult

    def fake_market_order(self, request):
        return BrokerResult(
            broker_order_id="FAKE",
            status="filled",
            filled_price=0.0,
        )

    monkeypatch.setattr(
        integrated_cycle_module.GmoFxBroker, "market_order", fake_market_order,
    )
    with pytest.raises(AssertionError, match="must be reviewed"):
        run_gmo_level5_integrated_fake_cycle(_permissive_input())
