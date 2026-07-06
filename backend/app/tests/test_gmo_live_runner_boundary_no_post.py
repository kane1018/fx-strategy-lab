"""No-POST tests for the GMO live runner/bot-service boundary adapter."""

from __future__ import annotations

import pathlib

from app.services.gmo_live_runner_boundary import (
    GmoLiveRunnerBoundaryInput,
    build_gmo_live_runner_boundary_summary,
    build_gmo_live_service_boundary_summary,
    build_gmo_live_service_no_post_hook_summary,
)
from app.services.gmo_live_safety_policy import (
    GmoLiveEnablePolicyInput,
    GmoLiveKillSwitchState,
    GmoLiveRiskConfig,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "services" / "gmo_live_runner_boundary.py"
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


def test_boundary_blocks_by_default() -> None:
    result = build_gmo_live_runner_boundary_summary()
    assert result.runner_may_start_gmo_live_entry is False
    assert result.runner_may_start_gmo_live_settlement is False
    assert "PROCESS_START_DEFAULT_OFF" in result.blocked_reasons


def test_boundary_still_blocked_when_process_started_but_policy_not_ready() -> None:
    result = build_gmo_live_runner_boundary_summary(
        GmoLiveRunnerBoundaryInput(process_just_started=False)
    )
    assert result.runner_may_start_gmo_live_entry is False
    assert "LIVE_ENABLE_POLICY_NOT_READY" in result.blocked_reasons


def test_boundary_blocked_when_kill_switch_triggered_even_if_policy_ready() -> None:
    result = build_gmo_live_runner_boundary_summary(
        GmoLiveRunnerBoundaryInput(
            process_just_started=False,
            live_enable_policy_input=GmoLiveEnablePolicyInput(**_ALL_ENABLE_GATES_TRUE),
            kill_switch_state=GmoLiveKillSwitchState(),
        )
    )
    assert result.runner_may_start_gmo_live_entry is False
    assert "KILL_SWITCH_TRIGGERED" in result.blocked_reasons


def _permissive_boundary_input(**overrides: object) -> GmoLiveRunnerBoundaryInput:
    values: dict[str, object] = {
        "process_just_started": False,
        "risk_config": GmoLiveRiskConfig(gmo_live_enabled=True),
        "live_enable_policy_input": GmoLiveEnablePolicyInput(**_ALL_ENABLE_GATES_TRUE),
        "kill_switch_state": GmoLiveKillSwitchState(process_start_default_off=False),
        "settlement_side_docs_status_classified": True,
    }
    values.update(overrides)
    return GmoLiveRunnerBoundaryInput(**values)


def test_boundary_blocked_when_gmo_live_enabled_is_false() -> None:
    result = build_gmo_live_runner_boundary_summary(
        _permissive_boundary_input(risk_config=GmoLiveRiskConfig(gmo_live_enabled=False))
    )
    assert result.runner_may_start_gmo_live_entry is False
    assert "GMO_LIVE_ENABLED_FALSE" in result.blocked_reasons


def test_boundary_blocks_settlement_when_side_docs_not_classified() -> None:
    result = build_gmo_live_runner_boundary_summary(
        _permissive_boundary_input(settlement_side_docs_status_classified=False)
    )
    assert result.runner_may_start_gmo_live_entry is True
    assert result.runner_may_start_gmo_live_settlement is False
    assert "SETTLEMENT_SIDE_DOCS_NOT_CONFIRMED" in result.settlement_blocked_reasons


def test_boundary_allows_entry_and_settlement_when_fully_permissive() -> None:
    result = build_gmo_live_runner_boundary_summary(_permissive_boundary_input())
    assert result.runner_may_start_gmo_live_entry is True
    assert result.runner_may_start_gmo_live_settlement is True
    assert result.blocked_reasons == ()
    assert result.settlement_blocked_reasons == ()


def test_boundary_reports_not_wired_into_real_automation() -> None:
    result = build_gmo_live_runner_boundary_summary()
    assert result.wired_into_bot_service is False
    assert result.wired_into_automation_runner is False


def test_service_boundary_blocks_by_default_and_reports_unwired() -> None:
    summary = build_gmo_live_service_boundary_summary()
    assert summary.runner_summary.runner_may_start_gmo_live_entry is False
    assert summary.service_hook_wired is False
    assert summary.service_hook_wired_into_bot_service is False
    assert summary.service_hook_wired_into_automation_runner is False


def test_service_boundary_allows_when_fully_permissive() -> None:
    summary = build_gmo_live_service_boundary_summary(_permissive_boundary_input())
    assert summary.runner_summary.runner_may_start_gmo_live_entry is True
    assert summary.runner_summary.runner_may_start_gmo_live_settlement is True
    assert summary.service_hook_wired is False


def test_service_no_post_hook_summary_marks_wire_in_targets() -> None:
    summary = build_gmo_live_service_no_post_hook_summary(
        _permissive_boundary_input(),
        invoked_from_bot_service=True,
        invoked_from_automation_runner=True,
    )
    assert summary.service_hook_wired is True
    assert summary.service_hook_wired_into_bot_service is True
    assert summary.service_hook_wired_into_automation_runner is True


def test_service_no_post_hook_summary_embeds_shadow_gate_state() -> None:
    summary = build_gmo_live_service_no_post_hook_summary(
        _permissive_boundary_input(
            risk_config=GmoLiveRiskConfig(gmo_live_enabled=True),
            live_enable_policy_input=GmoLiveEnablePolicyInput(**_ALL_ENABLE_GATES_TRUE),
            kill_switch_state=GmoLiveKillSwitchState(process_start_default_off=False),
            settlement_side_docs_status_classified=True,
        )
    )
    assert summary.readiness_shadow_entry_allowed is True
    assert summary.readiness_shadow_settlement_allowed is True
    assert summary.readiness_shadow_blocked_reasons == ()


def test_module_never_calls_a_real_post_capable_method() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    forbidden_terms = (
        "market_order(",
        "official_settlement_order(",
        "httpx",
        "requests",
    )
    for term in forbidden_terms:
        assert term not in text


def test_module_does_not_import_bot_service_or_automation_service() -> None:
    import ast

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    assert not any("bot_service" in module for module in imported_modules)
    assert not any("automation_service" in module for module in imported_modules)


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_has_no_production_allow_true_wiring() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text
