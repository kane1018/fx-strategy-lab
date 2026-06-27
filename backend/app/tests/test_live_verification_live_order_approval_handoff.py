from __future__ import annotations

from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta

from app.live_verification.live_order_approval_handoff import (
    LIVE_ORDER_APPROVAL_HANDOFF_ID_PREFIX,
    LiveOrderApprovalHandoffBlockReason,
    LiveOrderApprovalHandoffStatus,
    build_live_order_approval_handoff_package,
    render_live_order_approval_handoff_markdown,
)
from app.live_verification.live_order_candidate import (
    LiveOrderCandidate,
    LiveOrderCandidateSide,
    LiveOrderCandidateSourceType,
    StrategySignalInput,
    build_live_order_candidate_dry_run,
)
from app.live_verification.live_order_candidate_review import (
    LiveOrderCandidateReviewReport,
    build_live_order_candidate_review_report,
)
from app.live_verification.live_order_candidate_risk_gate import (
    LiveOrderCandidateRiskSnapshot,
    evaluate_live_order_candidate_risk_gate,
)
from app.live_verification.live_order_candidate_trace import (
    build_live_order_candidate_trace_record,
)
from app.live_verification.live_order_operator_review import (
    LiveOrderOperatorReviewProcedure,
    build_live_order_operator_review_procedure,
)
from app.live_verification.live_order_review_session_bundle import (
    ReviewGatedSessionBundle,
    build_review_gated_session_bundle,
)
from app.live_verification.live_order_session_policy import (
    ReviewGatedSessionPolicyDecision,
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
        source_signal_id="signal_step5i_001",
        source_type=LiveOrderCandidateSourceType.STRATEGY_SIGNAL,
        strategy_name="rsi_reversal",
        symbol="USD_JPY",
        side=LiveOrderCandidateSide.BUY,
        confidence=0.8,
        rationale="sanitized approval handoff fixture",
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
        "snapshot_id": "risk_snapshot_step5i_001",
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


def _review(
    *,
    candidate: LiveOrderCandidate | None = None,
    risk_snapshot: LiveOrderCandidateRiskSnapshot | None = None,
    **overrides: object,
) -> LiveOrderCandidateReviewReport:
    actual_candidate = candidate or _candidate()
    risk_decision = evaluate_live_order_candidate_risk_gate(
        candidate=actual_candidate,
        snapshot=risk_snapshot or _risk_snapshot(),
    )
    trace = build_live_order_candidate_trace_record(
        candidate=actual_candidate,
        risk_decision=risk_decision,
        created_at=CREATED_AT,
    ).trace_record
    report = build_live_order_candidate_review_report(
        candidate=actual_candidate,
        risk_decision=risk_decision,
        trace_record=trace,
        created_at=CREATED_AT,
    ).review_report
    return _unchecked(report, **overrides)


def _snapshot(**overrides: object) -> ReviewGatedSessionPolicySnapshot:
    values = {
        "snapshot_id": "session_snapshot_step5i_001",
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


def _policy_decision(
    *,
    review_report: LiveOrderCandidateReviewReport | None = None,
    snapshot: ReviewGatedSessionPolicySnapshot | None = None,
    **overrides: object,
) -> ReviewGatedSessionPolicyDecision:
    decision = evaluate_review_gated_session_policy(
        review_report=review_report or _review(),
        snapshot=snapshot or _snapshot(),
    )
    return _unchecked(decision, **overrides)


def _bundle(
    *,
    review_report: LiveOrderCandidateReviewReport | None = None,
    policy_decision: ReviewGatedSessionPolicyDecision | None = None,
    session_count_today: int | None = 0,
    daily_live_size_total: int | None = 0,
    **overrides: object,
) -> ReviewGatedSessionBundle:
    actual_review = review_report or _review()
    actual_policy = policy_decision or _policy_decision(review_report=actual_review)
    bundle = build_review_gated_session_bundle(
        review_report=actual_review,
        session_policy_decision=actual_policy,
        created_at=CREATED_AT,
        session_count_today=session_count_today,
        daily_live_size_total=daily_live_size_total,
    ).bundle
    return _unchecked(bundle, **overrides)


def _operator_review(
    *,
    bundle: ReviewGatedSessionBundle | None = None,
    **overrides: object,
) -> LiveOrderOperatorReviewProcedure:
    procedure = build_live_order_operator_review_procedure(
        bundle=bundle or _bundle(),
        created_at=CREATED_AT,
    ).procedure
    return _unchecked(procedure, **overrides)


def _handoff(*, operator_review: LiveOrderOperatorReviewProcedure | None = None):
    return build_live_order_approval_handoff_package(
        operator_review=operator_review or _operator_review(),
        created_at=CREATED_AT,
    )


def _assert_blocked(
    *,
    reason: LiveOrderApprovalHandoffBlockReason | str,
    operator_review: LiveOrderOperatorReviewProcedure | None = None,
) -> None:
    result = _handoff(operator_review=operator_review)
    expected = reason.value if isinstance(reason, LiveOrderApprovalHandoffBlockReason) else reason

    assert result.handoff_status is LiveOrderApprovalHandoffStatus.BLOCKED_HANDOFF
    assert result.package.handoff_status is LiveOrderApprovalHandoffStatus.BLOCKED_HANDOFF
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_command_generated is False
    assert expected in result.blocked_reasons
    assert result.recommended_next_step == "fix_operator_review_blockers_no_post"


def test_ready_operator_review_builds_ready_approval_handoff() -> None:
    result = _handoff()
    package = result.package

    assert package.handoff_id.startswith(LIVE_ORDER_APPROVAL_HANDOFF_ID_PREFIX)
    assert (
        package.handoff_status
        is LiveOrderApprovalHandoffStatus.READY_FOR_APPROVAL_HANDOFF_REVIEW
    )
    assert package.eligible_for_operator_review is True
    assert package.allowed_for_live is False
    assert package.approval_gate_issued is False
    assert package.approval_command_generated is False
    assert package.final_dynamic_preflight_required is True
    assert package.symbol == "USD_JPY"
    assert package.side == "BUY"
    assert package.size == 100
    assert package.execution_type == "MARKET"
    assert package.blocked_reasons == ()
    assert (
        package.recommended_next_step
        == "prepare_future_approval_gate_in_separate_step_no_post"
    )


def test_approval_handoff_safety_defaults_are_always_fixed() -> None:
    package = _handoff().package

    assert package.allowed_for_live is False
    assert package.requires_human_approval is True
    assert package.approval_gate_required is True
    assert package.approval_gate_issued is False
    assert package.approval_command_generated is False
    assert package.final_dynamic_preflight_required is True
    assert package.dry_run_only is True


def test_blocked_operator_review_builds_blocked_handoff() -> None:
    blocked_operator_review = _operator_review(bundle=_bundle(remaining_sessions_today=0))

    _assert_blocked(
        operator_review=blocked_operator_review,
        reason=LiveOrderApprovalHandoffBlockReason.OPERATOR_REVIEW_NOT_READY,
    )


def test_blocked_reasons_are_preserved() -> None:
    blocked_operator_review = _operator_review(bundle=_bundle(remaining_daily_size=99))
    result = _handoff(operator_review=blocked_operator_review)

    assert "insufficient_remaining_daily_size" in result.blocked_reasons


def test_operator_review_allowed_for_live_blocks_handoff() -> None:
    _assert_blocked(
        operator_review=_operator_review(allowed_for_live=True),
        reason=LiveOrderApprovalHandoffBlockReason.OPERATOR_REVIEW_ALLOWS_LIVE,
    )


def test_operator_review_not_dry_run_blocks_handoff() -> None:
    _assert_blocked(
        operator_review=_operator_review(dry_run_only=False),
        reason=LiveOrderApprovalHandoffBlockReason.OPERATOR_REVIEW_NOT_DRY_RUN,
    )


def test_missing_human_approval_requirement_blocks_handoff() -> None:
    _assert_blocked(
        operator_review=_operator_review(requires_human_approval=False),
        reason=LiveOrderApprovalHandoffBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
    )


def test_missing_approval_gate_requirement_blocks_handoff() -> None:
    _assert_blocked(
        operator_review=_operator_review(approval_gate_required=False),
        reason=LiveOrderApprovalHandoffBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
    )


def test_unsupported_symbol_blocks_handoff() -> None:
    _assert_blocked(
        operator_review=_operator_review(symbol="EUR_USD"),
        reason=LiveOrderApprovalHandoffBlockReason.UNSUPPORTED_SYMBOL,
    )


def test_unsupported_side_blocks_handoff() -> None:
    _assert_blocked(
        operator_review=_operator_review(side="NO_TRADE"),
        reason=LiveOrderApprovalHandoffBlockReason.UNSUPPORTED_SIDE,
    )


def test_unsupported_size_blocks_handoff() -> None:
    _assert_blocked(
        operator_review=_operator_review(size=200),
        reason=LiveOrderApprovalHandoffBlockReason.UNSUPPORTED_SIZE,
    )


def test_unsupported_execution_type_blocks_handoff() -> None:
    _assert_blocked(
        operator_review=_operator_review(execution_type="LIMIT"),
        reason=LiveOrderApprovalHandoffBlockReason.UNSUPPORTED_EXECUTION_TYPE,
    )


def test_display_allowed_fields_are_sanitized_identifiers_and_status_fields() -> None:
    fields_set = set(_handoff().package.display_allowed_fields)

    assert "handoff_id" in fields_set
    assert "operator_review_id" in fields_set
    assert "candidate_id" in fields_set
    assert "symbol" in fields_set
    assert "side" in fields_set
    assert "size" in fields_set
    assert "executionType" in fields_set
    assert "allowed_for_live=false" in fields_set
    assert "approval_gate_issued=false" in fields_set
    assert "approval_command_generated=false" in fields_set


def test_display_forbidden_fields_include_credential_raw_id_and_approval_terms() -> None:
    fields_set = set(_handoff().package.display_forbidden_fields)

    assert "API key value" in fields_set
    assert "secret value" in fields_set
    assert "raw response" in fields_set
    assert "order ID" in fields_set
    assert "execution ID" in fields_set
    assert "position ID" in fields_set
    assert "clientOrderId" in fields_set
    assert "approval_id" in fields_set
    assert "approval command" in fields_set


def test_final_dynamic_preflight_items_include_required_checks() -> None:
    items = set(_handoff().package.final_dynamic_preflight_items)

    assert "account/assets: success" in items
    assert "open_positions_count=0" in items
    assert "active_orders_count=0" in items
    assert "spread_jpy <= 0.01" in items
    assert "ledger unused" in items
    assert "Git clean" in items
    assert "tests pass" in items
    assert "secret scan pass" in items
    assert "outbound body allowlist matches" in items
    assert "request body == signing body" in items


def test_markdown_rendering_includes_required_warnings() -> None:
    markdown = render_live_order_approval_handoff_markdown(_handoff().package)

    assert "This approval handoff is dry-run only." in markdown
    assert "This handoff is not an approval gate." in markdown
    assert "This handoff does not generate approval_id or approval command." in markdown
    assert "This handoff does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown


def test_markdown_rendering_lists_allowed_forbidden_and_final_preflight_sections() -> None:
    markdown = render_live_order_approval_handoff_markdown(_handoff().package)

    assert "## Display Allowed Fields" in markdown
    assert "## Display Forbidden Fields" in markdown
    assert "## Final Dynamic Preflight Items" in markdown
    assert "approval_gate_issued=false" in markdown
    assert "approval command" in markdown
    assert "request body == signing body" in markdown


def test_markdown_rendering_omits_forbidden_actual_values() -> None:
    markdown = render_live_order_approval_handoff_markdown(_handoff().package)
    forbidden_actual_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "actual_approval_command_value",
    )

    for value in forbidden_actual_values:
        assert value not in markdown


def test_handoff_serialization_and_repr_do_not_include_forbidden_actual_values() -> None:
    package = _handoff().package
    serialized = str(asdict(package))
    rendered = repr(package)
    forbidden_actual_values = (
        "actual_api_key_value",
        "actual_secret_value",
        "actual_signature_value",
        "actual_header_value",
        "actual_raw_response_value",
        "actual_order_id_value",
        "actual_approval_command_value",
    )

    for value in forbidden_actual_values:
        assert value not in serialized
        assert value not in rendered


def test_handoff_builder_does_not_accept_forbidden_order_credential_or_approval_fields() -> None:
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
    }

    for key, value in forbidden_kwargs.items():
        try:
            build_live_order_approval_handoff_package(
                operator_review=_operator_review(),
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_approval_handoff_module_has_no_ordering_api_or_approval_generation_dependencies() -> None:
    import app.live_verification.live_order_approval_handoff as module

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
    assert "build_step4_approval_gate" not in module_names
    assert "evaluate_step4_approval" not in module_names
