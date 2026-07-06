"""No-POST tests for the integrated Level 5 fake cycle.

Unlike test_gmo_level5_fake_cycle_no_post.py (a pure state-machine
simulation), this exercises the real GmoFxBroker skeleton methods with a
refusing fake HTTP client, proving the chain fails closed end-to-end even
when every upstream gate is fully permissive -- because real transport is
deliberately unimplemented.
"""

from __future__ import annotations

import pathlib

import pytest

from app.services.gmo_level5_integrated_fake_cycle import (
    GmoLevel5IntegratedCycleInput,
    run_gmo_level5_integrated_fake_cycle,
)
from app.services.gmo_live_safety_policy import (
    GmoLiveEnablePolicyInput,
    GmoLiveKillSwitchState,
)
from app.services.gmo_settlement_reconciliation import (
    GmoSettlementReconciliationInput,
    evaluate_gmo_settlement_reconciliation,
)

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


def _permissive_input(**overrides: object) -> GmoLevel5IntegratedCycleInput:
    values: dict[str, object] = {
        "kill_switch_state": GmoLiveKillSwitchState(process_start_default_off=False),
        "live_enable_policy_input": GmoLiveEnablePolicyInput(**_ALL_ENABLE_GATES_TRUE),
        "manual_intervention_performed": False,
    }
    values.update(overrides)
    return GmoLevel5IntegratedCycleInput(**values)


def test_default_input_blocks_at_upstream_gates() -> None:
    result = run_gmo_level5_integrated_fake_cycle()
    assert result.level5_full_auto_cycle_completed is False
    assert result.entry_attempt_blocked_reason == "upstream_gate_blocked"
    assert "kill_switch_triggered" in result.blocked_reasons
    assert "live_enable_policy_not_ready" in result.blocked_reasons


def test_kill_switch_triggered_blocks_before_broker_call() -> None:
    result = run_gmo_level5_integrated_fake_cycle(
        _permissive_input(kill_switch_state=GmoLiveKillSwitchState())
    )
    assert result.level5_full_auto_cycle_completed is False
    assert "kill_switch_triggered" in result.blocked_reasons


def test_live_enable_policy_not_ready_blocks_before_broker_call() -> None:
    result = run_gmo_level5_integrated_fake_cycle(
        _permissive_input(live_enable_policy_input=GmoLiveEnablePolicyInput())
    )
    assert result.level5_full_auto_cycle_completed is False
    assert "live_enable_policy_not_ready" in result.blocked_reasons


def test_manual_intervention_blocks_before_broker_call() -> None:
    result = run_gmo_level5_integrated_fake_cycle(
        _permissive_input(manual_intervention_performed=True)
    )
    assert result.level5_full_auto_cycle_completed is False
    assert "manual_intervention_performed" in result.blocked_reasons


def test_fully_permissive_input_still_fails_closed_at_real_broker() -> None:
    """This is the key integration guarantee: even with every upstream gate
    permissive, the real GmoFxBroker skeleton must still block before any
    network call, because transport is not implemented.
    """
    result = run_gmo_level5_integrated_fake_cycle(_permissive_input())
    assert result.level5_full_auto_cycle_completed is False
    assert result.entry_attempt_blocked_reason == "entry_transport_not_available"
    assert result.blocked_reasons == ("entry_transport_not_available",)


def test_settlement_reconciliation_rejected_blocks() -> None:
    result = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(settlement_result_category="REJECTED_SANITIZED")
    )
    assert result.reconciled is False


def test_settlement_reconciliation_unknown_or_timeout_blocks() -> None:
    result = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(settlement_result_category="UNKNOWN_SANITIZED")
    )
    assert result.reconciled is False


def test_settlement_reconciliation_only_completes_on_no_position() -> None:
    result = evaluate_gmo_settlement_reconciliation(
        GmoSettlementReconciliationInput(
            settlement_result_category="ACCEPTED_SANITIZED",
            post_settlement_position_status_safe="NO_POSITION",
            post_settlement_position_count_safe=0,
        )
    )
    assert result.reconciled is True


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


def test_run_cycle_raises_assertion_error_only_if_broker_ever_stops_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Documents the fail-safe: if a future change makes market_order() stop
    raising without this module being updated, the cycle must not silently
    report success -- it must raise loudly instead.
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
