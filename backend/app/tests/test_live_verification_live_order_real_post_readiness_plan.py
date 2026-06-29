from __future__ import annotations

import ast
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
)
from app.live_verification.live_order_real_api_preflight_execution import (
    STEP6E_MAX_SPREAD_JPY,
    STEP6E_MAX_TICKER_AGE_SECONDS,
)
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    MARKET_HOURS_OPEN_STATE,
)
from app.live_verification.live_order_real_post_readiness_plan import (
    STEP6E_R2_PASSED_STATUS,
    STEP6E_SC_READY_STATUS,
    STEP6F_REQUEST_SCOPE_LABEL,
    LiveOrderRealPostReadinessPlanStatus,
    LiveOrderRealPostReadinessPreflightSnapshot,
    LiveOrderRealPostReadinessRequestSnapshot,
    build_live_order_real_post_readiness_plan,
    render_live_order_real_post_readiness_plan_markdown,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
Status = LiveOrderRealPostReadinessPlanStatus


def _request(**overrides: object) -> LiveOrderRealPostReadinessRequestSnapshot:
    values = {
        "request_id": "step6f-request-sanitized",
        "created_at": CREATED_AT,
        "explicit_step6f_user_instruction_received": True,
        "operator_understands_real_money_risk": True,
        "operator_understands_no_post_in_step6f": True,
        "operator_understands_no_order_endpoint_in_step6f": True,
        "operator_understands_no_live_order_once_in_step6f": True,
        "operator_understands_post_readiness_planning_only": True,
        "operator_understands_step6g_required_for_one_shot_post": True,
        "operator_understands_fresh_preflight_required_before_step6g": True,
        "operator_understands_unknown_means_stop": True,
        "request_scope_label": STEP6F_REQUEST_SCOPE_LABEL,
    }
    values.update(overrides)
    return LiveOrderRealPostReadinessRequestSnapshot(**values)


def _snapshot(**overrides: object) -> LiveOrderRealPostReadinessPreflightSnapshot:
    values = {
        "snapshot_id": "step6e-r2-sanitized-pass",
        "created_at": CREATED_AT,
        "source_step6e_r2_reported": True,
        "source_execution_status": STEP6E_R2_PASSED_STATUS,
        "source_api_preflight_executed": True,
        "source_api_preflight_passed": True,
        "source_consolidation_status": STEP6E_SC_READY_STATUS,
        "source_consolidation_ready": True,
        "source_eligible_for_step6f_post_readiness_planning": True,
        "market_session_state": MARKET_HOURS_OPEN_STATE,
        "market_window_allowed": True,
        "broker_maintenance_active": False,
        "holiday_or_special_close": False,
        "market_hours_unknown": False,
        "account_asset_status": "success",
        "account_asset_check_passed": True,
        "open_positions_count": 0,
        "open_positions_check_passed": True,
        "active_orders_count": 0,
        "active_orders_check_passed": True,
        "instrument_symbol": SUPPORTED_SYMBOL,
        "instrument_min_open_order_size": LIVE_ORDER_CANDIDATE_SIZE,
        "instrument_size_step": 1,
        "instrument_rule_check_passed": True,
        "ticker_symbol": SUPPORTED_SYMBOL,
        "ticker_spread_jpy": 0.005,
        "ticker_age_seconds": 5.0,
        "ticker_check_passed": True,
        "permission_scope_check_passed": True,
        "ip_account_binding_check_passed": True,
        "previous_result_unknown_check_passed": True,
        "raw_request_saved": False,
        "raw_request_displayed": False,
        "raw_response_saved": False,
        "raw_response_displayed": False,
        "headers_saved": False,
        "headers_displayed": False,
        "signature_saved": False,
        "signature_displayed": False,
        "credentials_displayed": False,
        "order_ids_displayed": False,
        "execution_ids_displayed": False,
        "position_ids_displayed": False,
        "client_order_ids_displayed": False,
        "preflight_result_age_seconds": 10,
        "preflight_result_max_age_seconds": 60,
    }
    values.update(overrides)
    return LiveOrderRealPostReadinessPreflightSnapshot(**values)


def _plan(**overrides: object):
    values = {
        "request_snapshot": _request(),
        "preflight_snapshot": _snapshot(),
        "created_at": CREATED_AT,
    }
    values.update(overrides)
    return build_live_order_real_post_readiness_plan(**values)


def test_ready_step6e_r2_snapshot_and_explicit_request_plans_no_post() -> None:
    result = _plan()
    plan = result.plan

    assert plan.plan_status is Status.POST_READINESS_PLANNED_NO_POST
    assert plan.plan_ready is True
    assert plan.eligible_for_step6g_one_shot_post_request is True
    assert plan.allowed_for_live is False
    assert plan.post_authorized_this_step is False
    assert plan.post_allowed_this_step is False
    assert plan.post_executed is False
    assert plan.order_endpoint_called is False
    assert plan.order_payload_generated is False
    assert plan.order_payload_sent is False
    assert plan.live_order_once_called is False
    assert plan.broker_order_path_called is False
    assert plan.retry_allowed is False
    assert plan.loop_allowed is False
    assert plan.add_order_allowed is False
    assert plan.change_order_allowed is False
    assert plan.cancel_order_allowed is False
    assert plan.close_order_allowed is False
    assert plan.post_attempt_limit == 1
    assert plan.symbol == SUPPORTED_SYMBOL
    assert plan.size == LIVE_ORDER_CANDIDATE_SIZE
    assert plan.executionType == LIVE_ORDER_CANDIDATE_EXECUTION_TYPE
    assert plan.recommended_next_step.startswith(
        "stop_and_wait_for_explicit_step6g_one_shot_post_request",
    )


def test_request_missing_blocks_step6f_request() -> None:
    result = _plan(
        request_snapshot=_request(explicit_step6f_user_instruction_received=False),
    )

    assert result.plan_status is Status.BLOCKED_STEP6F_REQUEST
    assert "explicit_step6f_user_instruction_received_missing" in result.blocked_reasons


def test_operator_ack_missing_blocks_step6f_request() -> None:
    result = _plan(
        request_snapshot=_request(operator_understands_no_post_in_step6f=False),
    )

    assert result.plan_status is Status.BLOCKED_STEP6F_REQUEST
    assert "operator_understands_no_post_in_step6f_missing" in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"source_api_preflight_executed": False}, "source_api_preflight_not_executed"),
        ({"source_api_preflight_passed": False}, "source_api_preflight_not_passed"),
        (
            {"source_eligible_for_step6f_post_readiness_planning": False},
            "source_not_eligible_for_step6f_post_readiness_planning",
        ),
    ],
)
def test_source_preflight_not_ready_blocks(override: dict[str, object], reason: str) -> None:
    result = _plan(preflight_snapshot=_snapshot(**override))

    assert result.plan_status is Status.BLOCKED_STEP6F_PREFLIGHT_NOT_READY
    assert reason in result.blocked_reasons


def test_preflight_stale_blocks_step6f_stale() -> None:
    result = _plan(
        preflight_snapshot=_snapshot(
            preflight_result_age_seconds=61,
            preflight_result_max_age_seconds=60,
        ),
    )

    assert result.plan_status is Status.BLOCKED_STEP6F_PREFLIGHT_STALE
    assert "preflight_result_stale" in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"market_session_state": "CLOSE"}, "market_session_not_open"),
        ({"market_hours_unknown": True}, "market_hours_unknown"),
        ({"open_positions_count": 1}, "open_positions_not_zero"),
        ({"active_orders_count": 1}, "active_orders_not_zero"),
        ({"ticker_spread_jpy": STEP6E_MAX_SPREAD_JPY + 0.001}, "ticker_spread_too_wide"),
        ({"ticker_age_seconds": STEP6E_MAX_TICKER_AGE_SECONDS + 1}, "ticker_age_stale"),
        ({"permission_scope_check_passed": False}, "permission_scope_check_failed"),
        ({"ip_account_binding_check_passed": False}, "ip_account_binding_check_failed"),
        (
            {"previous_result_unknown_check_passed": False},
            "previous_result_unknown_check_failed",
        ),
    ],
)
def test_preflight_not_passing_blocks(override: dict[str, object], reason: str) -> None:
    result = _plan(preflight_snapshot=_snapshot(**override))

    assert result.plan_status is Status.BLOCKED_STEP6F_PREFLIGHT_NOT_PASSING
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"allowed_for_live": True}, "allowed_for_live_unsafe"),
        ({"order_endpoint_called": True}, "order_endpoint_called_unsafe"),
        ({"order_payload_generated": True}, "order_payload_generated_unsafe"),
        ({"order_payload_sent": True}, "order_payload_sent_unsafe"),
        ({"live_order_once_called": True}, "live_order_once_called_unsafe"),
        ({"post_executed": True}, "post_executed_unsafe"),
        ({"raw_response_displayed": True}, "raw_response_displayed_unsafe"),
        ({"credentials_displayed": True}, "credentials_displayed_unsafe"),
        ({"retry_allowed": True}, "retry_allowed_unsafe"),
        ({"loop_allowed": True}, "loop_allowed_unsafe"),
        ({"add_order_allowed": True}, "add_order_allowed_unsafe"),
        ({"change_order_allowed": True}, "change_order_allowed_unsafe"),
        ({"cancel_order_allowed": True}, "cancel_order_allowed_unsafe"),
        ({"close_order_allowed": True}, "close_order_allowed_unsafe"),
    ],
)
def test_unsafe_state_blocks_step6f_unsafe_state(
    override: dict[str, object],
    reason: str,
) -> None:
    result = _plan(**override)

    assert result.plan_status is Status.BLOCKED_STEP6F_UNSAFE_STATE
    assert reason in result.blocked_reasons


def test_step6g_go_no_go_stop_handoff_and_blockers_are_present() -> None:
    plan = _plan().plan

    assert "explicit Step 6G request required" in plan.pre_step6g_go_conditions
    assert "stale preflight" in plan.pre_step6g_no_go_conditions
    assert "unknown status" in plan.pre_step6g_stop_conditions
    assert (
        "fresh real API preflight rerun immediately before POST"
        in plan.future_step6g_handoff_conditions
    )
    assert "fresh preflight unavailable" in plan.future_step6g_blockers
    assert plan.fresh_preflight_required_before_step6g is True
    assert plan.approval_artifact_revalidation_required_before_step6g is True
    assert plan.market_hours_recheck_required_before_step6g is True
    assert plan.positions_orders_recheck_required_before_step6g is True
    assert plan.ticker_recheck_required_before_step6g is True


def test_markdown_renderer_includes_planning_only_no_post_warnings() -> None:
    markdown = render_live_order_real_post_readiness_plan_markdown(_plan().plan)

    assert "This Step 6F post-readiness plan is planning-only." in markdown
    assert "This Step 6F plan does not authorize live POST." in markdown
    assert "This Step 6F plan keeps allowed_for_live=false." in markdown
    assert "This Step 6F plan does not call any order endpoint." in markdown
    assert "This Step 6F plan does not generate or send an order payload." in markdown
    assert "This Step 6F plan does not call live_order_once." in markdown
    assert "This Step 6F plan does not execute HTTP POST." in markdown
    assert "Step 6G requires a separate explicit request and fresh preflight." in markdown
    for forbidden_value in (
        "credential-value",
        "raw-response-value",
        "real-order-id-value",
        "execution-id-value",
        "position-id-value",
        "client-order-id-value",
        "STEP4_APPROVE",
        "pbcopy",
        "curl ",
    ):
        assert forbidden_value not in markdown


def test_serialization_repr_and_asdict_do_not_include_sensitive_actual_values() -> None:
    plan = _plan().plan
    serialized = str(asdict(plan))
    represented = repr(plan)

    for forbidden_value in (
        "credential-value",
        "raw-response-value",
        "header-value",
        "signature-value",
        "real-order-id-value",
        "execution-id-value",
        "position-id-value",
        "client-order-id-value",
        "approval-command-full-text",
    ):
        assert forbidden_value not in serialized
        assert forbidden_value not in represented


def test_new_module_has_no_http_private_broker_live_order_once_dependencies() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_post_readiness_plan.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not any(
                    alias.name == blocked or alias.name.startswith(f"{blocked}.")
                    for blocked in blocked_modules
                )
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not any(
                module == blocked or module.startswith(f"{blocked}.")
                for blocked in blocked_modules
            )
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            call_name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else None
            )
            assert call_name not in blocked_call_names
