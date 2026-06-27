from __future__ import annotations

from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.live_order_approval_gate_design import (
    build_live_order_approval_gate_design,
)
from app.live_verification.live_order_approval_gate_preview import (
    build_live_order_approval_gate_preview,
)
from app.live_verification.live_order_approval_handoff import (
    build_live_order_approval_handoff_package,
)
from app.live_verification.live_order_approval_validation_simulator import (
    simulate_live_order_approval_validation,
)
from app.live_verification.live_order_candidate import (
    LiveOrderCandidate,
    LiveOrderCandidateSide,
    LiveOrderCandidateSourceType,
    StrategySignalInput,
    build_live_order_candidate_dry_run,
)
from app.live_verification.live_order_candidate_review import (
    build_live_order_candidate_review_report,
)
from app.live_verification.live_order_candidate_risk_gate import (
    LiveOrderCandidateRiskSnapshot,
    evaluate_live_order_candidate_risk_gate,
)
from app.live_verification.live_order_candidate_trace import (
    build_live_order_candidate_trace_record,
)
from app.live_verification.live_order_e2e_dry_run_chain import (
    LIVE_ORDER_E2E_DRY_RUN_CHAIN_ID_PREFIX,
    REQUIRED_E2E_DRY_RUN_CHAIN_STAGE_NAMES,
    LiveOrderE2EDryRunChainBlockReason,
    LiveOrderE2EDryRunChainStatus,
    build_live_order_e2e_dry_run_chain_review,
    render_live_order_e2e_dry_run_chain_markdown,
)
from app.live_verification.live_order_execution_runbook import (
    build_live_order_one_shot_execution_runbook,
)
from app.live_verification.live_order_final_dynamic_preflight import (
    LiveOrderFinalDynamicPreflightSnapshot,
    evaluate_live_order_final_dynamic_preflight,
)
from app.live_verification.live_order_one_shot_boundary import (
    build_live_order_one_shot_boundary,
)
from app.live_verification.live_order_operator_review import (
    build_live_order_operator_review_procedure,
)
from app.live_verification.live_order_review_session_bundle import (
    build_review_gated_session_bundle,
)
from app.live_verification.live_order_session_policy import (
    ReviewGatedSessionPolicySnapshot,
    evaluate_review_gated_session_policy,
)

CREATED_AT = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def _unchecked(base: object, **overrides: object):
    values = {field.name: getattr(base, field.name) for field in fields(base)}
    values.update(overrides)
    instance = object.__new__(type(base))
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    return instance


def _candidate(**overrides: object) -> LiveOrderCandidate:
    signal = StrategySignalInput(
        source_signal_id="signal_step5p_001",
        source_type=LiveOrderCandidateSourceType.STRATEGY_SIGNAL,
        strategy_name="rsi_reversal",
        symbol="USD_JPY",
        side=LiveOrderCandidateSide.BUY,
        confidence=0.8,
        rationale="sanitized e2e dry-run chain fixture",
        market_snapshot_ref="snapshot_ref_001",
        paper_trade_ref="paper_ref_001",
        shadow_run_ref="shadow_ref_001",
        created_at=CREATED_AT,
        expires_at=CREATED_AT + timedelta(minutes=10),
    )
    candidate = build_live_order_candidate_dry_run(signal).candidate
    assert candidate is not None
    return _unchecked(candidate, **overrides)


def _risk_snapshot(**overrides: object) -> LiveOrderCandidateRiskSnapshot:
    values = {
        "snapshot_id": "risk_snapshot_step5p_001",
        "created_at": CREATED_AT,
        "account_assets_success": True,
        "open_positions_count": 0,
        "active_orders_count": 0,
        "symbol_min_open_order_size": 100,
        "symbol_size_step": 1,
        "spread_jpy": 0.005,
        "ticker_age_seconds": 0.5,
        "market_window_allowed": True,
        "maintenance_active": False,
        "important_event_window_ok": True,
        "ledger_unused": True,
        "daily_live_attempt_count": 0,
        "session_live_attempt_count": 0,
        "result_unknown": False,
        "git_clean": True,
        "tests_passed": True,
        "ruff_passed": True,
        "secret_scan_passed": True,
        "raw_response_saved": False,
        "raw_response_displayed": False,
    }
    values.update(overrides)
    return LiveOrderCandidateRiskSnapshot(**values)


def _session_snapshot(**overrides: object) -> ReviewGatedSessionPolicySnapshot:
    values = {
        "snapshot_id": "session_snapshot_step5p_001",
        "created_at": CREATED_AT,
        "policy_date": "2026-01-01",
        "initial_micro_live_completed": True,
        "previous_order_result_confirmed": True,
        "previous_result_unknown": False,
        "open_positions_count": 0,
        "active_orders_count": 0,
        "session_count_today": 0,
        "daily_live_size_total": 0,
        "last_session_completed_at": None,
        "minutes_since_last_session": None,
        "session_size": 100,
        "max_sessions_per_day": 2,
        "min_minutes_between_sessions": 120,
        "max_daily_size_total": 200,
        "git_clean": True,
        "tests_passed": True,
        "ruff_passed": True,
        "secret_scan_passed": True,
        "raw_response_saved": False,
        "raw_response_displayed": False,
        "market_window_allowed": True,
        "maintenance_active": False,
        "important_event_window_ok": True,
    }
    values.update(overrides)
    return ReviewGatedSessionPolicySnapshot(**values)


def _final_preflight_snapshot(simulation, **overrides: object):
    values = {
        "snapshot_id": "final_preflight_snapshot_step5p_001",
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


def _safe_artifacts() -> dict[str, object]:
    candidate = _candidate()
    risk_decision = evaluate_live_order_candidate_risk_gate(
        candidate=candidate,
        snapshot=_risk_snapshot(),
    )
    trace_record = build_live_order_candidate_trace_record(
        candidate=candidate,
        risk_decision=risk_decision,
        created_at=CREATED_AT,
    ).trace_record
    review_report = build_live_order_candidate_review_report(
        candidate=candidate,
        risk_decision=risk_decision,
        trace_record=trace_record,
        created_at=CREATED_AT,
    ).review_report
    session_policy_decision = evaluate_review_gated_session_policy(
        review_report=review_report,
        snapshot=_session_snapshot(),
    )
    session_bundle = build_review_gated_session_bundle(
        review_report=review_report,
        session_policy_decision=session_policy_decision,
        created_at=CREATED_AT,
        session_count_today=0,
        daily_live_size_total=0,
    ).bundle
    operator_review = build_live_order_operator_review_procedure(
        bundle=session_bundle,
        created_at=CREATED_AT,
    ).procedure
    approval_handoff = build_live_order_approval_handoff_package(
        operator_review=operator_review,
        created_at=CREATED_AT,
    ).package
    approval_gate_design = build_live_order_approval_gate_design(
        handoff_package=approval_handoff,
        created_at=CREATED_AT,
    ).design
    approval_gate_preview = build_live_order_approval_gate_preview(
        approval_gate_design=approval_gate_design,
        created_at=CREATED_AT,
    ).preview
    approval_validation_simulation = simulate_live_order_approval_validation(
        approval_gate_preview=approval_gate_preview,
        simulated_command_input=approval_gate_preview.approval_command_template,
        simulated_ttl_seconds=approval_gate_preview.ttl_seconds,
        same_session=True,
        already_used=False,
        created_at=CREATED_AT,
    ).simulation
    final_dynamic_preflight_decision = evaluate_live_order_final_dynamic_preflight(
        approval_validation_simulation=approval_validation_simulation,
        snapshot=_final_preflight_snapshot(approval_validation_simulation),
        created_at=CREATED_AT,
    ).decision
    one_shot_boundary_decision = build_live_order_one_shot_boundary(
        final_dynamic_preflight_decision=final_dynamic_preflight_decision,
        created_at=CREATED_AT,
    ).decision
    execution_runbook = build_live_order_one_shot_execution_runbook(
        one_shot_boundary_decision=one_shot_boundary_decision,
        created_at=CREATED_AT,
    ).runbook
    return {
        "candidate": candidate,
        "risk_decision": risk_decision,
        "trace_record": trace_record,
        "review_report": review_report,
        "session_policy_decision": session_policy_decision,
        "session_bundle": session_bundle,
        "operator_review": operator_review,
        "approval_handoff": approval_handoff,
        "approval_gate_design": approval_gate_design,
        "approval_gate_preview": approval_gate_preview,
        "approval_validation_simulation": approval_validation_simulation,
        "final_dynamic_preflight_decision": final_dynamic_preflight_decision,
        "one_shot_boundary_decision": one_shot_boundary_decision,
        "execution_runbook": execution_runbook,
    }


def _chain(**overrides: object):
    artifacts = _safe_artifacts()
    artifacts.update(overrides)
    return build_live_order_e2e_dry_run_chain_review(
        created_at=CREATED_AT,
        **artifacts,
    )


def _assert_blocked(reason: LiveOrderE2EDryRunChainBlockReason | str, **overrides: object) -> None:
    result = _chain(**overrides)
    expected = reason.value if isinstance(reason, LiveOrderE2EDryRunChainBlockReason) else reason

    assert result.chain_status is LiveOrderE2EDryRunChainStatus.BLOCKED_E2E_DRY_RUN_CHAIN
    assert result.chain_ready is False
    assert result.eligible_for_future_real_approval_planning is False
    assert result.allowed_for_live is False
    assert expected in result.blocked_reasons
    assert result.recommended_next_step == "fix_e2e_dry_run_chain_blockers_no_post"


def test_full_safe_fake_chain_is_ready_for_e2e_dry_run_review_only() -> None:
    result = _chain()
    review = result.chain_review

    assert review.chain_id.startswith(LIVE_ORDER_E2E_DRY_RUN_CHAIN_ID_PREFIX)
    assert (
        review.chain_status
        is LiveOrderE2EDryRunChainStatus.READY_FOR_E2E_DRY_RUN_CHAIN_REVIEW
    )
    assert review.chain_ready is True
    assert review.eligible_for_future_real_approval_planning is True
    assert review.allowed_for_live is False
    assert review.post_attempt_limit == 1
    assert review.post_executed is False
    assert review.live_order_once_called is False
    assert review.blocked_reasons == ()
    assert result.recommended_next_step == (
        "review_e2e_dry_run_chain_then_prepare_future_real_approval_planning_"
        "separate_step_no_post"
    )


def test_chain_ready_safety_defaults_are_fixed_and_not_post_permission() -> None:
    review = _chain().chain_review

    assert review.allowed_for_live is False
    assert review.requires_human_approval is True
    assert review.approval_gate_required is True
    assert review.approval_gate_issued is False
    assert review.approval_id_generated is False
    assert review.approval_command_generated is False
    assert review.approval_command_template_only is True
    assert review.approval_command_copyable is False
    assert review.final_dynamic_preflight_required is True
    assert review.dry_run_only is True
    assert review.private_api_called is False
    assert review.broker_called is False
    assert review.read_only_api_called is False
    assert review.retry_allowed is False
    assert review.loop_allowed is False
    assert review.add_order_allowed is False
    assert review.change_order_allowed is False
    assert review.cancel_order_allowed is False
    assert review.close_order_allowed is False
    assert review.post_reconciliation_required is True


def test_missing_required_stage_blocks_chain() -> None:
    _assert_blocked(
        LiveOrderE2EDryRunChainBlockReason.MISSING_REQUIRED_STAGE,
        candidate=None,
    )


def test_blocked_stage_blocks_and_preserves_stage_reasons() -> None:
    artifacts = _safe_artifacts()
    candidate = artifacts["candidate"]
    blocked_risk = evaluate_live_order_candidate_risk_gate(
        candidate=candidate,
        snapshot=_risk_snapshot(spread_jpy=0.02),
    )

    result = _chain(risk_decision=blocked_risk)

    assert result.chain_status is LiveOrderE2EDryRunChainStatus.BLOCKED_E2E_DRY_RUN_CHAIN
    assert LiveOrderE2EDryRunChainBlockReason.STAGE_NOT_READY.value in result.blocked_reasons
    assert "spread_too_wide" in result.blocked_reasons


def test_blocked_reasons_are_merged_from_multiple_stage_failures() -> None:
    artifacts = _safe_artifacts()
    blocked_candidate = _unchecked(artifacts["candidate"], allowed_for_live=True)
    blocked_runbook = _unchecked(artifacts["execution_runbook"], post_executed=True)
    result = _chain(candidate=blocked_candidate, execution_runbook=blocked_runbook)

    assert LiveOrderE2EDryRunChainBlockReason.STAGE_ALLOWS_LIVE.value in result.blocked_reasons
    assert LiveOrderE2EDryRunChainBlockReason.POST_ALREADY_EXECUTED.value in result.blocked_reasons


def test_candidate_id_mismatch_blocks_chain() -> None:
    artifacts = _safe_artifacts()
    _assert_blocked(
        LiveOrderE2EDryRunChainBlockReason.CANDIDATE_ID_MISMATCH,
        review_report=_unchecked(artifacts["review_report"], candidate_id="other_candidate"),
    )


def test_review_id_mismatch_blocks_chain() -> None:
    artifacts = _safe_artifacts()
    _assert_blocked(
        LiveOrderE2EDryRunChainBlockReason.REVIEW_ID_MISMATCH,
        session_policy_decision=_unchecked(
            artifacts["session_policy_decision"],
            review_id="other_review",
        ),
    )


def test_trace_id_mismatch_blocks_chain() -> None:
    artifacts = _safe_artifacts()
    _assert_blocked(
        LiveOrderE2EDryRunChainBlockReason.TRACE_ID_MISMATCH,
        review_report=_unchecked(artifacts["review_report"], trace_id="other_trace"),
    )


def test_risk_decision_id_mismatch_blocks_chain() -> None:
    artifacts = _safe_artifacts()
    _assert_blocked(
        LiveOrderE2EDryRunChainBlockReason.RISK_DECISION_ID_MISMATCH,
        trace_record=_unchecked(artifacts["trace_record"], risk_decision_id="other_risk"),
    )


def test_source_signal_id_mismatch_blocks_chain() -> None:
    artifacts = _safe_artifacts()
    _assert_blocked(
        LiveOrderE2EDryRunChainBlockReason.SOURCE_SIGNAL_ID_MISMATCH,
        session_bundle=_unchecked(artifacts["session_bundle"], source_signal_id="other_signal"),
    )


@pytest.mark.parametrize(
    ("field_name", "value", "reason"),
    (
        ("symbol", "EUR_USD", LiveOrderE2EDryRunChainBlockReason.SYMBOL_MISMATCH),
        ("side", "NO_TRADE", LiveOrderE2EDryRunChainBlockReason.SIDE_MISMATCH),
        ("size", 200, LiveOrderE2EDryRunChainBlockReason.SIZE_MISMATCH),
        (
            "execution_type",
            "LIMIT",
            LiveOrderE2EDryRunChainBlockReason.EXECUTION_TYPE_MISMATCH,
        ),
    ),
)
def test_order_shape_mismatches_block_chain(
    field_name: str,
    value: object,
    reason: LiveOrderE2EDryRunChainBlockReason,
) -> None:
    artifacts = _safe_artifacts()
    _assert_blocked(
        reason,
        execution_runbook=_unchecked(artifacts["execution_runbook"], **{field_name: value}),
    )


@pytest.mark.parametrize(
    ("artifact_name", "field_name", "value", "reason"),
    (
        (
            "candidate",
            "allowed_for_live",
            True,
            LiveOrderE2EDryRunChainBlockReason.STAGE_ALLOWS_LIVE,
        ),
        (
            "session_bundle",
            "dry_run_only",
            False,
            LiveOrderE2EDryRunChainBlockReason.STAGE_NOT_DRY_RUN,
        ),
        (
            "approval_gate_design",
            "approval_gate_issued",
            True,
            LiveOrderE2EDryRunChainBlockReason.APPROVAL_GATE_ALREADY_ISSUED,
        ),
        (
            "approval_gate_design",
            "approval_id_generated",
            True,
            LiveOrderE2EDryRunChainBlockReason.APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            "approval_gate_design",
            "approval_command_generated",
            True,
            LiveOrderE2EDryRunChainBlockReason.APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            "approval_gate_preview",
            "approval_command_copyable",
            True,
            LiveOrderE2EDryRunChainBlockReason.APPROVAL_COMMAND_COPYABLE,
        ),
        (
            "execution_runbook",
            "post_executed",
            True,
            LiveOrderE2EDryRunChainBlockReason.POST_ALREADY_EXECUTED,
        ),
        (
            "one_shot_boundary_decision",
            "live_order_once_called",
            True,
            LiveOrderE2EDryRunChainBlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        ),
        (
            "one_shot_boundary_decision",
            "private_api_called",
            True,
            LiveOrderE2EDryRunChainBlockReason.PRIVATE_API_ALREADY_CALLED,
        ),
        (
            "one_shot_boundary_decision",
            "broker_called",
            True,
            LiveOrderE2EDryRunChainBlockReason.BROKER_ALREADY_CALLED,
        ),
        (
            "one_shot_boundary_decision",
            "read_only_api_called",
            True,
            LiveOrderE2EDryRunChainBlockReason.READ_ONLY_API_ALREADY_CALLED,
        ),
        (
            "one_shot_boundary_decision",
            "retry_allowed",
            True,
            LiveOrderE2EDryRunChainBlockReason.RETRY_ALLOWED,
        ),
        (
            "one_shot_boundary_decision",
            "loop_allowed",
            True,
            LiveOrderE2EDryRunChainBlockReason.LOOP_ALLOWED,
        ),
        (
            "one_shot_boundary_decision",
            "add_order_allowed",
            True,
            LiveOrderE2EDryRunChainBlockReason.ADD_ORDER_ALLOWED,
        ),
        (
            "one_shot_boundary_decision",
            "change_order_allowed",
            True,
            LiveOrderE2EDryRunChainBlockReason.CHANGE_ORDER_ALLOWED,
        ),
        (
            "one_shot_boundary_decision",
            "cancel_order_allowed",
            True,
            LiveOrderE2EDryRunChainBlockReason.CANCEL_ORDER_ALLOWED,
        ),
        (
            "one_shot_boundary_decision",
            "close_order_allowed",
            True,
            LiveOrderE2EDryRunChainBlockReason.CLOSE_ORDER_ALLOWED,
        ),
    ),
)
def test_safety_flag_failures_block_chain(
    artifact_name: str,
    field_name: str,
    value: object,
    reason: LiveOrderE2EDryRunChainBlockReason,
) -> None:
    artifacts = _safe_artifacts()
    _assert_blocked(
        reason,
        **{artifact_name: _unchecked(artifacts[artifact_name], **{field_name: value})},
    )


def test_invalid_post_attempt_limit_blocks_chain() -> None:
    artifacts = _safe_artifacts()
    _assert_blocked(
        LiveOrderE2EDryRunChainBlockReason.INVALID_POST_ATTEMPT_LIMIT,
        one_shot_boundary_decision=_unchecked(
            artifacts["one_shot_boundary_decision"],
            post_attempt_limit=2,
        ),
    )


def test_missing_post_reconciliation_requirement_blocks_chain() -> None:
    artifacts = _safe_artifacts()
    _assert_blocked(
        LiveOrderE2EDryRunChainBlockReason.MISSING_POST_RECONCILIATION_REQUIREMENT,
        execution_runbook=_unchecked(
            artifacts["execution_runbook"],
            post_reconciliation_required=False,
        ),
    )


def test_stages_include_all_required_stage_names() -> None:
    stage_names = {stage.name for stage in _chain().chain_review.stages}

    assert set(REQUIRED_E2E_DRY_RUN_CHAIN_STAGE_NAMES).issubset(stage_names)


def test_check_results_include_required_chain_checks() -> None:
    check_names = {check.name for check in _chain().chain_review.check_results}

    assert "all_required_stages_present" in check_names
    assert "stage_statuses_ready" in check_names
    assert "symbol_consistency" in check_names
    assert "side_consistency" in check_names
    assert "size_consistency" in check_names
    assert "execution_type_consistency" in check_names
    assert "source_signal_consistency" in check_names
    assert "candidate_review_trace_risk_session_ids_consistency" in check_names
    assert "allowed_for_live_false_across_chain" in check_names
    assert "dry_run_only_true_across_chain" in check_names
    assert "approval_artifacts_not_generated" in check_names
    assert "post_not_executed" in check_names
    assert "no_api_broker_live_order_once_called" in check_names
    assert "one_shot_constraints_preserved" in check_names
    assert "post_reconciliation_required" in check_names


def test_markdown_rendering_includes_required_dry_run_warnings() -> None:
    markdown = render_live_order_e2e_dry_run_chain_markdown(_chain().chain_review)

    assert "This E2E dry-run chain review is dry-run only." in markdown
    assert "This review does not call read-only API." in markdown
    assert "This review does not call Private API." in markdown
    assert "This review does not call live_order_once." in markdown
    assert "This review does not execute HTTP POST." in markdown
    assert "This review does not issue a real approval gate." in markdown
    assert "This review does not generate a real approval command." in markdown
    assert "This review does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_e2e_dry_run_chain_markdown(_chain().chain_review)
    forbidden_values = (
        "forbidden_credential_marker",
        "forbidden_response_marker",
        "forbidden_order_marker",
        "forbidden_approval_marker",
        "forbidden_clipboard_marker",
    )

    for value in forbidden_values:
        assert value not in markdown


def test_serialization_and_repr_do_not_include_forbidden_actual_values() -> None:
    review = _chain().chain_review
    serialized = str(asdict(review))
    rendered = repr(review)
    forbidden_values = (
        "forbidden_credential_marker",
        "forbidden_response_marker",
        "forbidden_order_marker",
        "forbidden_approval_marker",
        "forbidden_clipboard_marker",
    )

    for value in forbidden_values:
        assert value not in serialized
        assert value not in rendered


def test_chain_module_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_e2e_dry_run_chain as module

    module_names = set(module.__dict__)

    assert "requests" not in module_names
    assert "httpx" not in module_names
    assert "aiohttp" not in module_names
    assert "urllib" not in module_names
    assert "socket" not in module_names
    assert "subprocess" not in module_names
    assert "private_api" not in module_names
    assert "brokers" not in module_names
    assert "live_order_once" not in module_names
    assert "pbcopy" not in module_names
