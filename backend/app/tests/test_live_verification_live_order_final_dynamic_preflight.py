from __future__ import annotations

from dataclasses import asdict, fields

from app.live_verification.live_order_final_dynamic_preflight import (
    FINAL_DYNAMIC_PREFLIGHT_MAX_SPREAD_JPY,
    LIVE_ORDER_FINAL_DYNAMIC_PREFLIGHT_ID_PREFIX,
    LiveOrderFinalDynamicPreflightBlockReason,
    LiveOrderFinalDynamicPreflightSnapshot,
    LiveOrderFinalDynamicPreflightStatus,
    evaluate_live_order_final_dynamic_preflight,
    render_live_order_final_dynamic_preflight_markdown,
)
from app.tests.test_live_verification_live_order_approval_validation_simulator import (
    CREATED_AT,
    _simulate,
)


def _unchecked(base: object, **overrides: object):
    values = {field.name: getattr(base, field.name) for field in fields(base)}
    values.update(overrides)
    instance = object.__new__(type(base))
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    return instance


def _snapshot(**overrides: object) -> LiveOrderFinalDynamicPreflightSnapshot:
    simulation = _simulate().simulation
    values = {
        "snapshot_id": "final_preflight_snapshot_step5m_001",
        "created_at": CREATED_AT,
        "simulation_id": simulation.simulation_id,
        "preview_id": simulation.preview_id,
        "design_id": simulation.design_id,
        "handoff_id": simulation.handoff_id,
        "operator_review_id": simulation.operator_review_id,
        "bundle_id": simulation.bundle_id,
        "review_id": simulation.review_id,
        "candidate_id": simulation.candidate_id,
        "risk_decision_id": simulation.risk_decision_id,
        "trace_id": simulation.trace_id,
        "session_policy_decision_id": simulation.session_policy_decision_id,
        "source_signal_id": simulation.source_signal_id,
        "source_type": simulation.source_type,
        "strategy_name": simulation.strategy_name,
        "symbol": "USD_JPY",
        "side": "BUY",
        "size": 100,
        "execution_type": "MARKET",
        "account_assets_status": "success",
        "open_positions_count": 0,
        "active_orders_count": 0,
        "min_open_order_size": 100,
        "size_step": 1,
        "ticker_available": True,
        "spread_jpy": 0.005,
        "ticker_age_seconds": 0.5,
        "ticker_age_threshold_seconds": 30,
        "market_window_allowed": True,
        "maintenance_active": False,
        "important_event_window_ok": True,
        "ledger_unused": True,
        "session_attempt_count_today": 0,
        "max_sessions_per_day": 2,
        "daily_live_size_total": 0,
        "max_daily_size_total": 200,
        "previous_result_confirmed": True,
        "result_unknown": False,
        "git_clean": True,
        "tests_passed": True,
        "ruff_passed": True,
        "secret_scan_passed": True,
        "raw_response_saved": False,
        "raw_response_displayed": False,
        "outbound_body_allowlist_matched": True,
        "request_body_equals_signing_body": True,
        "final_preflight_age_seconds": 0.5,
        "final_preflight_age_threshold_seconds": 30,
        "allowed_for_live": False,
        "requires_human_approval": True,
        "approval_gate_required": True,
        "approval_gate_issued": False,
        "approval_id_generated": False,
        "approval_command_generated": False,
        "approval_command_template_only": True,
        "approval_command_copyable": False,
        "final_dynamic_preflight_required": True,
        "dry_run_only": True,
    }
    values.update(overrides)
    return LiveOrderFinalDynamicPreflightSnapshot(**values)


def _evaluate(
    *,
    simulation=None,
    snapshot: LiveOrderFinalDynamicPreflightSnapshot | None = None,
    **snapshot_overrides: object,
):
    actual_simulation = simulation or _simulate().simulation
    actual_snapshot = snapshot or _snapshot(**snapshot_overrides)
    return evaluate_live_order_final_dynamic_preflight(
        approval_validation_simulation=actual_simulation,
        snapshot=actual_snapshot,
        created_at=CREATED_AT,
    )


def _assert_blocked(
    reason: LiveOrderFinalDynamicPreflightBlockReason | str,
    *,
    simulation=None,
    **snapshot_overrides: object,
) -> None:
    result = _evaluate(simulation=simulation, **snapshot_overrides)
    expected = (
        reason.value
        if isinstance(reason, LiveOrderFinalDynamicPreflightBlockReason)
        else reason
    )

    assert (
        result.preflight_status
        is LiveOrderFinalDynamicPreflightStatus.BLOCKED_FINAL_DYNAMIC_PREFLIGHT
    )
    assert result.preflight_passed is False
    assert result.eligible_for_future_one_shot_review is False
    assert result.allowed_for_live is False
    assert expected in result.blocked_reasons
    assert result.recommended_next_step in {
        "fix_approval_validation_blockers_no_post",
        "fix_final_dynamic_preflight_snapshot_no_post",
    }


def test_passed_simulation_and_safe_snapshot_are_review_eligible_only() -> None:
    result = _evaluate()
    decision = result.decision

    assert decision.decision_id.startswith(LIVE_ORDER_FINAL_DYNAMIC_PREFLIGHT_ID_PREFIX)
    assert (
        decision.preflight_status
        is LiveOrderFinalDynamicPreflightStatus.READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW
    )
    assert decision.preflight_passed is True
    assert decision.eligible_for_future_one_shot_review is True
    assert decision.allowed_for_live is False
    assert decision.approval_gate_issued is False
    assert decision.approval_id_generated is False
    assert decision.approval_command_generated is False
    assert decision.final_dynamic_preflight_required is True
    assert decision.blocked_reasons == ()
    assert result.recommended_next_step == (
        "prepare_future_one_shot_boundary_design_no_post"
    )


def test_safety_defaults_are_always_fixed_on_decision() -> None:
    decision = _evaluate().decision

    assert decision.allowed_for_live is False
    assert decision.requires_human_approval is True
    assert decision.approval_gate_required is True
    assert decision.approval_gate_issued is False
    assert decision.approval_id_generated is False
    assert decision.approval_command_generated is False
    assert decision.approval_command_template_only is True
    assert decision.approval_command_copyable is False
    assert decision.final_dynamic_preflight_required is True
    assert decision.dry_run_only is True


def test_blocked_approval_validation_blocks_and_preserves_simulation_reasons() -> None:
    blocked_simulation = _simulate(ttl_seconds=301).simulation
    result = _evaluate(simulation=blocked_simulation)

    assert (
        result.preflight_status
        is LiveOrderFinalDynamicPreflightStatus.BLOCKED_FINAL_DYNAMIC_PREFLIGHT
    )
    assert result.preflight_passed is False
    assert "expired_ttl" in result.blocked_reasons
    assert (
        LiveOrderFinalDynamicPreflightBlockReason.APPROVAL_VALIDATION_NOT_PASSED.value
        in result.blocked_reasons
    )
    assert result.recommended_next_step == "fix_approval_validation_blockers_no_post"


def test_simulation_safety_flags_block() -> None:
    simulation = _simulate().simulation

    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_ALLOWS_LIVE,
        simulation=_unchecked(simulation, allowed_for_live=True),
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_NOT_DRY_RUN,
        simulation=_unchecked(simulation, dry_run_only=False),
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_APPROVAL_GATE_ISSUED,
        simulation=_unchecked(simulation, approval_gate_issued=True),
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_APPROVAL_ID_GENERATED,
        simulation=_unchecked(simulation, approval_id_generated=True),
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_APPROVAL_COMMAND_GENERATED,
        simulation=_unchecked(simulation, approval_command_generated=True),
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.SIMULATION_MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT,
        simulation=_unchecked(simulation, final_dynamic_preflight_required=False),
    )


def test_snapshot_safety_flags_block() -> None:
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.SNAPSHOT_ALLOWS_LIVE,
        snapshot=_unchecked(_snapshot(), allowed_for_live=True),
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.SNAPSHOT_NOT_DRY_RUN,
        snapshot=_unchecked(_snapshot(), dry_run_only=False),
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        snapshot=_unchecked(_snapshot(), approval_gate_issued=True),
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        snapshot=_unchecked(_snapshot(), approval_id_generated=True),
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        snapshot=_unchecked(_snapshot(), approval_command_generated=True),
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.MISSING_FINAL_DYNAMIC_PREFLIGHT_REQUIREMENT,
        snapshot=_unchecked(_snapshot(), final_dynamic_preflight_required=False),
    )


def test_unsupported_order_shape_blocks() -> None:
    _assert_blocked(LiveOrderFinalDynamicPreflightBlockReason.UNSUPPORTED_SYMBOL, symbol="EUR_USD")
    _assert_blocked(LiveOrderFinalDynamicPreflightBlockReason.UNSUPPORTED_SIDE, side="NO_TRADE")
    _assert_blocked(LiveOrderFinalDynamicPreflightBlockReason.UNSUPPORTED_SIZE, size=200)
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        execution_type="LIMIT",
    )


def test_account_and_open_state_blocks() -> None:
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.ACCOUNT_ASSETS_NOT_SUCCESS,
        account_assets_status="failure",
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.OPEN_POSITIONS_EXIST,
        open_positions_count=1,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.ACTIVE_ORDERS_EXIST,
        active_orders_count=1,
    )


def test_symbol_rules_and_ticker_blocks() -> None:
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.INVALID_MIN_OPEN_ORDER_SIZE,
        min_open_order_size=101,
    )
    _assert_blocked(LiveOrderFinalDynamicPreflightBlockReason.INVALID_SIZE_STEP, size_step=2)
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.TICKER_UNAVAILABLE,
        ticker_available=False,
    )
    _assert_blocked(LiveOrderFinalDynamicPreflightBlockReason.MISSING_SPREAD, spread_jpy=None)
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.SPREAD_TOO_WIDE,
        spread_jpy=FINAL_DYNAMIC_PREFLIGHT_MAX_SPREAD_JPY + 0.001,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.MISSING_TICKER_AGE,
        ticker_age_seconds=None,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.INVALID_TICKER_AGE,
        ticker_age_seconds=-1,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.STALE_TICKER,
        ticker_age_seconds=31,
    )


def test_market_ledger_session_and_result_blocks() -> None:
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.MARKET_WINDOW_NOT_ALLOWED,
        market_window_allowed=False,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.MAINTENANCE_ACTIVE,
        maintenance_active=True,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.IMPORTANT_EVENT_WINDOW_NOT_OK,
        important_event_window_ok=False,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.LEDGER_NOT_UNUSED,
        ledger_unused=False,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.SESSION_ATTEMPT_LIMIT_REACHED,
        session_attempt_count_today=2,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.DAILY_SIZE_LIMIT_EXCEEDED,
        daily_live_size_total=200,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.PREVIOUS_RESULT_NOT_CONFIRMED,
        previous_result_confirmed=False,
    )
    _assert_blocked(LiveOrderFinalDynamicPreflightBlockReason.RESULT_UNKNOWN, result_unknown=True)


def test_repo_secret_and_raw_artifact_blocks() -> None:
    _assert_blocked(LiveOrderFinalDynamicPreflightBlockReason.GIT_NOT_CLEAN, git_clean=False)
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.TESTS_NOT_PASSED,
        tests_passed=False,
    )
    _assert_blocked(LiveOrderFinalDynamicPreflightBlockReason.RUFF_NOT_PASSED, ruff_passed=False)
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.SECRET_SCAN_NOT_PASSED,
        secret_scan_passed=False,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.RAW_RESPONSE_SAVED,
        raw_response_saved=True,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.RAW_RESPONSE_DISPLAYED,
        raw_response_displayed=True,
    )


def test_body_match_and_final_preflight_age_blocks() -> None:
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.OUTBOUND_BODY_ALLOWLIST_MISMATCH,
        outbound_body_allowlist_matched=False,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.REQUEST_BODY_SIGNING_BODY_MISMATCH,
        request_body_equals_signing_body=False,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.MISSING_FINAL_PREFLIGHT_AGE,
        final_preflight_age_seconds=None,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.INVALID_FINAL_PREFLIGHT_AGE,
        final_preflight_age_seconds=-1,
    )
    _assert_blocked(
        LiveOrderFinalDynamicPreflightBlockReason.STALE_FINAL_PREFLIGHT,
        final_preflight_age_seconds=31,
    )


def test_check_results_cover_key_final_dynamic_preflight_checks() -> None:
    check_names = {check.name for check in _evaluate().decision.check_results}

    assert "approval_validation_simulation" in check_names
    assert "account_assets" in check_names
    assert "open_positions" in check_names
    assert "active_orders" in check_names
    assert "ticker_available" in check_names
    assert "spread" in check_names
    assert "ticker_age" in check_names
    assert "ledger_unused" in check_names
    assert "outbound_body_allowlist" in check_names
    assert "request_body_equals_signing_body" in check_names
    assert "final_preflight_age" in check_names


def test_multiple_failures_return_multiple_blocked_reasons() -> None:
    result = _evaluate(
        open_positions_count=1,
        active_orders_count=1,
        spread_jpy=0.02,
        tests_passed=False,
    )

    assert "open_positions_exist" in result.blocked_reasons
    assert "active_orders_exist" in result.blocked_reasons
    assert "spread_too_wide" in result.blocked_reasons
    assert "tests_not_passed" in result.blocked_reasons


def test_markdown_rendering_includes_dry_run_no_api_no_live_warnings() -> None:
    markdown = render_live_order_final_dynamic_preflight_markdown(_evaluate().decision)

    assert "This final dynamic preflight model is dry-run only." in markdown
    assert "This model does not call read-only API." in markdown
    assert "This model does not call Private API." in markdown
    assert "This model does not execute final dynamic preflight." in markdown
    assert "This model does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_final_dynamic_preflight_markdown(_evaluate().decision)
    forbidden_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "STEP4F-F1007D35",
        "STEP4_APPROVE STEP4F-F1007D35",
        "pbcopy",
    )

    for value in forbidden_values:
        assert value not in markdown


def test_serialization_and_repr_do_not_include_forbidden_actual_values() -> None:
    decision = _evaluate().decision
    serialized = str(asdict(decision))
    rendered = repr(decision)
    forbidden_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "STEP4F-F1007D35",
        "STEP4_APPROVE STEP4F-F1007D35",
        "pbcopy",
    )

    for value in forbidden_values:
        assert value not in serialized
        assert value not in rendered


def test_builder_does_not_accept_forbidden_real_api_or_approval_fields() -> None:
    forbidden_kwargs = {
        "api_key": "x",
        "secret": "x",
        "signature": "x",
        "headers": {},
        "raw_request": {},
        "raw_response": {},
        "clientOrderId": "x",
        "positionId": "x",
        "executionId": "x",
        "approval_id": "x",
        "approval_command": "x",
        "copyable_command": "x",
        "pbcopy": True,
    }

    for key, value in forbidden_kwargs.items():
        try:
            evaluate_live_order_final_dynamic_preflight(
                approval_validation_simulation=_simulate().simulation,
                snapshot=_snapshot(),
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_final_dynamic_preflight_module_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_final_dynamic_preflight as module

    module_names = set(module.__dict__)

    assert "requests" not in module_names
    assert "httpx" not in module_names
    assert "aiohttp" not in module_names
    assert "urllib" not in module_names
    assert "socket" not in module_names
    assert "subprocess" not in module_names
    assert "live_order_once" not in module_names
    assert "private_api" not in module_names
    assert "brokers" not in module_names
    assert "pbcopy" not in module_names
