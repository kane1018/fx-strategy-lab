"""No-POST tests for risk_service's GMO live shadow gate.

`evaluate_gmo_live_readiness_shadow` never gates a real order request and is
not called by `evaluate_order_risk` -- the existing unconditional GMO live
rejection there is untouched (verified below). This is a pure, no-network,
no-credential classification function.
"""

from __future__ import annotations

import inspect
import pathlib

from app.services.gmo_live_safety_policy import (
    GmoLiveEnablePolicyInput,
    GmoLiveKillSwitchState,
    GmoLiveRiskConfig,
)
from app.services.risk_service import (
    GmoLiveReadinessShadowInput,
    GmoLiveShadowBlockReason,
    evaluate_gmo_live_readiness_shadow,
    evaluate_order_risk,
)

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "services" / "risk_service.py"

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


def _permissive_shadow_input(**overrides: object) -> GmoLiveReadinessShadowInput:
    values: dict[str, object] = {
        "risk_config": GmoLiveRiskConfig(gmo_live_enabled=True),
        "live_enable_policy_input": GmoLiveEnablePolicyInput(**_ALL_ENABLE_GATES_TRUE),
        "kill_switch_state": GmoLiveKillSwitchState(process_start_default_off=False),
        "generic_close_attempt_detected": False,
        "settlement_side_docs_status_classified": True,
        "paper_evidence_safe_label_present": True,
        "operator_live_enable_declared": True,
    }
    values.update(overrides)
    return GmoLiveReadinessShadowInput(**values)


def test_shadow_gate_blocks_by_default() -> None:
    result = evaluate_gmo_live_readiness_shadow()
    assert result.entry_shadow_allowed is False
    assert result.settlement_shadow_allowed is False
    assert result.shadow_only is True
    assert GmoLiveShadowBlockReason.GMO_LIVE_ENABLED_FALSE.value in result.blocked_reasons


def test_shadow_gate_blocked_when_gmo_live_enabled_is_false() -> None:
    result = evaluate_gmo_live_readiness_shadow(
        _permissive_shadow_input(risk_config=GmoLiveRiskConfig(gmo_live_enabled=False))
    )
    assert result.entry_shadow_allowed is False
    assert GmoLiveShadowBlockReason.GMO_LIVE_ENABLED_FALSE.value in result.blocked_reasons


def test_shadow_gate_blocked_when_live_enable_policy_not_ready() -> None:
    result = evaluate_gmo_live_readiness_shadow(
        _permissive_shadow_input(live_enable_policy_input=GmoLiveEnablePolicyInput())
    )
    assert result.entry_shadow_allowed is False
    assert "LIVE_ENABLE_POLICY_NOT_READY" in result.blocked_reasons


def test_shadow_gate_blocked_when_kill_switch_triggered() -> None:
    result = evaluate_gmo_live_readiness_shadow(
        _permissive_shadow_input(kill_switch_state=GmoLiveKillSwitchState())
    )
    assert result.entry_shadow_allowed is False
    assert "KILL_SWITCH_TRIGGERED" in result.blocked_reasons


def test_shadow_gate_blocks_settlement_when_side_docs_not_classified() -> None:
    result = evaluate_gmo_live_readiness_shadow(
        _permissive_shadow_input(settlement_side_docs_status_classified=False)
    )
    assert result.settlement_shadow_allowed is False
    assert "SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED" in result.blocked_reasons


def test_shadow_gate_blocked_without_paper_evidence() -> None:
    result = evaluate_gmo_live_readiness_shadow(
        _permissive_shadow_input(paper_evidence_safe_label_present=False)
    )
    assert result.entry_shadow_allowed is False
    assert "PAPER_EVIDENCE_MISSING" in result.blocked_reasons


def test_shadow_gate_blocked_without_operator_enable_declaration() -> None:
    result = evaluate_gmo_live_readiness_shadow(
        _permissive_shadow_input(operator_live_enable_declared=False)
    )
    assert result.entry_shadow_allowed is False
    assert "OPERATOR_ENABLE_MISSING" in result.blocked_reasons


def test_shadow_gate_blocked_on_generic_close_attempt() -> None:
    result = evaluate_gmo_live_readiness_shadow(
        _permissive_shadow_input(generic_close_attempt_detected=True)
    )
    assert result.entry_shadow_allowed is False
    assert "GENERIC_CLOSE_ATTEMPT_DETECTED" in result.blocked_reasons


def test_shadow_gate_allows_entry_and_settlement_when_fully_permissive() -> None:
    result = evaluate_gmo_live_readiness_shadow(_permissive_shadow_input())
    assert result.entry_shadow_allowed is True
    assert result.settlement_shadow_allowed is True
    assert result.blocked_reasons == ()


def test_shadow_gate_never_calls_evaluate_order_risk() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    shadow_start = text.index("def evaluate_gmo_live_readiness_shadow")
    shadow_source = text[shadow_start:]
    assert "evaluate_order_risk(" not in shadow_source


def test_evaluate_order_risk_signature_is_unchanged() -> None:
    signature = inspect.signature(evaluate_order_risk)
    assert list(signature.parameters) == [
        "request",
        "risk",
        "settings",
        "open_positions",
        "daily_loss",
        "consecutive_losses",
    ]


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_has_no_production_allow_true_wiring() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text
