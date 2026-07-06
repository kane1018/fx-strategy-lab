"""No-POST tests for GmoLiveRiskConfig and the GMO live enable policy.

Pure dataclass/logic tests only: no network, no credentials, no `.env`, and
no import of app.live_verification or live_order_once anywhere in the
module under test.
"""

from __future__ import annotations

import pathlib

import pytest

from app.services.gmo_live_safety_policy import (
    GmoLiveEnablePolicyInput,
    GmoLiveRiskConfig,
    GmoLiveRiskConfigError,
    evaluate_gmo_live_enable_policy,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "services" / "gmo_live_safety_policy.py"
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


# --- GmoLiveRiskConfig --------------------------------------------------------


def test_gmo_live_risk_config_defaults_are_safe() -> None:
    config = GmoLiveRiskConfig()
    assert config.gmo_live_enabled is False
    assert config.process_start_default_off is True
    assert config.max_positions == 1
    assert config.max_entries_per_day == 1
    assert config.max_settlements_per_position == 1
    assert config.official_settlement_route_required is True
    assert config.generic_close_allowed is False
    assert config.opposite_order_as_close_allowed is False
    assert config.position_specific_actual_path_enabled is False
    assert config.order_size_escalation_requires_review is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"process_start_default_off": False},
        {"official_settlement_route_required": False},
        {"generic_close_allowed": True},
        {"opposite_order_as_close_allowed": True},
        {"position_specific_actual_path_enabled": True},
        {"order_size_escalation_requires_review": False},
        {"max_positions": 0},
        {"max_entries_per_day": -1},
        {"max_settlements_per_position": -1},
    ],
)
def test_gmo_live_risk_config_rejects_unsafe_overrides(overrides: dict[str, object]) -> None:
    with pytest.raises(GmoLiveRiskConfigError):
        GmoLiveRiskConfig(**overrides)


def test_gmo_live_risk_config_accepts_candidate_selection() -> None:
    config = GmoLiveRiskConfig(max_consecutive_losses_selected=2)
    assert config.max_consecutive_losses_selected == 2

    config = GmoLiveRiskConfig(max_consecutive_losses_selected=3)
    assert config.max_consecutive_losses_selected == 3

    with pytest.raises(GmoLiveRiskConfigError):
        GmoLiveRiskConfig(max_consecutive_losses_selected=5)


# --- live enable policy --------------------------------------------------------


def test_live_enable_blocked_by_default() -> None:
    result = evaluate_gmo_live_enable_policy(GmoLiveEnablePolicyInput())
    assert result.live_enable_ready is False
    assert "operator_live_enable_declared" in result.blocked_reasons


def test_live_enable_blocked_without_operator_declaration() -> None:
    values = dict(_ALL_ENABLE_GATES_TRUE)
    values["operator_live_enable_declared"] = False
    result = evaluate_gmo_live_enable_policy(GmoLiveEnablePolicyInput(**values))
    assert result.live_enable_ready is False
    assert result.blocked_reasons == ("operator_live_enable_declared",)


def test_live_enable_blocked_without_paper_evidence() -> None:
    values = dict(_ALL_ENABLE_GATES_TRUE)
    values["paper_evidence_safe_label_present"] = False
    result = evaluate_gmo_live_enable_policy(GmoLiveEnablePolicyInput(**values))
    assert result.live_enable_ready is False
    assert "paper_evidence_safe_label_present" in result.blocked_reasons


def test_live_enable_blocked_without_settlement_side_docs_status_classified() -> None:
    values = dict(_ALL_ENABLE_GATES_TRUE)
    values["settlement_side_docs_status_classified"] = False
    result = evaluate_gmo_live_enable_policy(GmoLiveEnablePolicyInput(**values))
    assert result.live_enable_ready is False
    assert "settlement_side_docs_status_classified" in result.blocked_reasons


def test_live_enable_blocked_without_settlement_side_provenance_ready() -> None:
    values = dict(_ALL_ENABLE_GATES_TRUE)
    values["settlement_side_provenance_ready"] = False
    result = evaluate_gmo_live_enable_policy(GmoLiveEnablePolicyInput(**values))
    assert result.live_enable_ready is False


def test_live_enable_blocked_without_head_equals_origin_main_or_clean_tree() -> None:
    values = dict(_ALL_ENABLE_GATES_TRUE)
    values["head_equals_origin_main"] = False
    values["working_tree_clean"] = False
    result = evaluate_gmo_live_enable_policy(GmoLiveEnablePolicyInput(**values))
    assert result.live_enable_ready is False
    assert "head_equals_origin_main" in result.blocked_reasons
    assert "working_tree_clean" in result.blocked_reasons


def test_live_enable_ready_only_when_every_gate_is_true() -> None:
    result = evaluate_gmo_live_enable_policy(GmoLiveEnablePolicyInput(**_ALL_ENABLE_GATES_TRUE))
    assert result.live_enable_ready is True
    assert result.blocked_reasons == ()


# --- isolation / no-op sanity --------------------------------------------------


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_does_not_read_env_or_call_http_client() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "httpx" not in text
    assert "requests" not in text


def test_module_has_no_production_allow_true_wiring() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text
