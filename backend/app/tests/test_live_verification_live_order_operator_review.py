from __future__ import annotations

from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta

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
    LIVE_ORDER_OPERATOR_REVIEW_ID_PREFIX,
    LiveOrderOperatorReviewBlockReason,
    LiveOrderOperatorReviewStatus,
    build_live_order_operator_review_procedure,
    render_live_order_operator_review_markdown,
)
from app.live_verification.live_order_review_session_bundle import (
    UNKNOWN_CAPACITY,
    ReviewGatedSessionBundle,
    build_review_gated_session_bundle,
)
from app.live_verification.live_order_session_policy import (
    ReviewGatedSessionPolicyDecision,
    ReviewGatedSessionPolicySnapshot,
    evaluate_review_gated_session_policy,
)

CREATED_AT = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def _candidate(**overrides: object) -> LiveOrderCandidate:
    signal = StrategySignalInput(
        source_signal_id="signal_step5h_001",
        source_type=LiveOrderCandidateSourceType.STRATEGY_SIGNAL,
        strategy_name="rsi_reversal",
        symbol="USD_JPY",
        side=LiveOrderCandidateSide.BUY,
        confidence=0.8,
        rationale="sanitized operator review fixture",
        market_snapshot_ref="snapshot_ref_001",
        paper_trade_ref="paper_ref_001",
        shadow_run_ref="shadow_ref_001",
        created_at=CREATED_AT,
        expires_at=CREATED_AT + timedelta(minutes=10),
    )
    candidate = build_live_order_candidate_dry_run(signal).candidate
    assert candidate is not None
    return _unchecked(candidate, **overrides)


def _unchecked(base: object, **overrides: object):
    values = {field.name: getattr(base, field.name) for field in fields(base)}
    values.update(overrides)
    instance = object.__new__(type(base))
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    return instance


def _risk_snapshot(**overrides: object) -> LiveOrderCandidateRiskSnapshot:
    values = {
        "snapshot_id": "risk_snapshot_step5h_001",
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
        "snapshot_id": "session_snapshot_step5h_001",
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


def _procedure(*, bundle: ReviewGatedSessionBundle | None = None):
    return build_live_order_operator_review_procedure(
        bundle=bundle or _bundle(),
        created_at=CREATED_AT,
    )


def _assert_blocked(
    *,
    reason: LiveOrderOperatorReviewBlockReason | str,
    bundle: ReviewGatedSessionBundle | None = None,
) -> None:
    result = _procedure(bundle=bundle)
    expected = reason.value if isinstance(reason, LiveOrderOperatorReviewBlockReason) else reason

    assert result.operator_review_status is LiveOrderOperatorReviewStatus.BLOCKED_OPERATOR_REVIEW
    assert result.procedure.operator_review_status is (
        LiveOrderOperatorReviewStatus.BLOCKED_OPERATOR_REVIEW
    )
    assert result.allowed_for_live is False
    assert result.eligible_for_operator_review is False
    assert expected in result.blocked_reasons
    assert result.recommended_next_step == "fix_bundle_blockers_no_post"


def test_ready_bundle_builds_ready_operator_checklist() -> None:
    result = _procedure()
    procedure = result.procedure

    assert procedure.operator_review_id.startswith(LIVE_ORDER_OPERATOR_REVIEW_ID_PREFIX)
    assert (
        procedure.operator_review_status
        is LiveOrderOperatorReviewStatus.READY_FOR_OPERATOR_CHECKLIST
    )
    assert procedure.eligible_for_operator_review is True
    assert procedure.allowed_for_live is False
    assert procedure.symbol == "USD_JPY"
    assert procedure.side == "BUY"
    assert procedure.size == 100
    assert procedure.execution_type == "MARKET"
    assert procedure.remaining_sessions_today == 2
    assert procedure.remaining_daily_size == 200
    assert procedure.recommended_next_step == "operator_checklist_review_no_post"
    assert procedure.blocked_reasons == ()
    assert procedure.checklist_items


def test_operator_review_safety_defaults_are_always_fixed() -> None:
    procedure = _procedure().procedure

    assert procedure.allowed_for_live is False
    assert procedure.requires_human_approval is True
    assert procedure.approval_gate_required is True
    assert procedure.dry_run_only is True


def test_blocked_bundle_builds_blocked_operator_review() -> None:
    blocked_review = _review(risk_snapshot=_risk_snapshot(open_positions_count=1))
    blocked_policy = _policy_decision(review_report=blocked_review)
    blocked_bundle = _bundle(
        review_report=blocked_review,
        policy_decision=blocked_policy,
    )

    _assert_blocked(bundle=blocked_bundle, reason="open_position_exists")


def test_blocked_reasons_are_preserved() -> None:
    blocked_review = _review(risk_snapshot=_risk_snapshot(open_positions_count=1))
    blocked_policy = _policy_decision(
        review_report=blocked_review,
        snapshot=_snapshot(active_orders_count=1),
    )
    blocked_bundle = _bundle(
        review_report=blocked_review,
        policy_decision=blocked_policy,
    )

    result = _procedure(bundle=blocked_bundle)

    assert "open_position_exists" in result.blocked_reasons
    assert "active_order_exists" in result.blocked_reasons


def test_bundle_allowed_for_live_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(allowed_for_live=True),
        reason=LiveOrderOperatorReviewBlockReason.BUNDLE_ALLOWS_LIVE,
    )


def test_bundle_not_dry_run_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(dry_run_only=False),
        reason=LiveOrderOperatorReviewBlockReason.BUNDLE_NOT_DRY_RUN,
    )


def test_missing_human_approval_requirement_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(requires_human_approval=False),
        reason=LiveOrderOperatorReviewBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
    )


def test_missing_approval_gate_requirement_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(approval_gate_required=False),
        reason=LiveOrderOperatorReviewBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
    )


def test_unsupported_symbol_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(symbol="EUR_USD"),
        reason=LiveOrderOperatorReviewBlockReason.UNSUPPORTED_SYMBOL,
    )


def test_unsupported_side_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(side="NO_TRADE"),
        reason=LiveOrderOperatorReviewBlockReason.UNSUPPORTED_SIDE,
    )


def test_unsupported_size_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(size=200),
        reason=LiveOrderOperatorReviewBlockReason.UNSUPPORTED_SIZE,
    )


def test_unsupported_execution_type_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(execution_type="LIMIT"),
        reason=LiveOrderOperatorReviewBlockReason.UNSUPPORTED_EXECUTION_TYPE,
    )


def test_missing_remaining_sessions_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(remaining_sessions_today=UNKNOWN_CAPACITY),
        reason=LiveOrderOperatorReviewBlockReason.MISSING_REMAINING_SESSIONS,
    )


def test_missing_remaining_daily_size_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(remaining_daily_size=UNKNOWN_CAPACITY),
        reason=LiveOrderOperatorReviewBlockReason.MISSING_REMAINING_DAILY_SIZE,
    )


def test_no_remaining_sessions_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(remaining_sessions_today=0),
        reason=LiveOrderOperatorReviewBlockReason.NO_REMAINING_SESSIONS,
    )


def test_insufficient_remaining_daily_size_blocks_operator_review() -> None:
    _assert_blocked(
        bundle=_bundle(remaining_daily_size=99),
        reason=LiveOrderOperatorReviewBlockReason.INSUFFICIENT_REMAINING_DAILY_SIZE,
    )


def test_ready_checklist_contains_dry_run_no_approval_and_no_live_post_items() -> None:
    labels = {item.label for item in _procedure().procedure.checklist_items}

    assert "Confirm this is dry-run review only" in labels
    assert "Confirm this is not an approval gate" in labels
    assert "Confirm this does not authorize live POST" in labels
    assert "Confirm future approval gate is a separate Step" in labels
    assert "Confirm future final dynamic preflight is a separate Step" in labels


def test_blocked_checklist_contains_do_not_proceed_items() -> None:
    blocked = _procedure(bundle=_bundle(remaining_sessions_today=0)).procedure
    labels = {item.label for item in blocked.checklist_items}

    assert "Review blocked reasons" in labels
    assert "Fix or wait until blockers are cleared" in labels
    assert "Do not proceed to approval gate" in labels
    assert "Do not proceed to live POST" in labels


def test_markdown_rendering_includes_warnings_and_checklist() -> None:
    markdown = render_live_order_operator_review_markdown(_procedure().procedure)

    assert "This operator review is dry-run only." in markdown
    assert "This review is not an approval gate." in markdown
    assert "This review does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown
    assert "Confirm this is dry-run review only" in markdown
    assert "Confirm this does not authorize live POST" in markdown


def test_markdown_rendering_omits_forbidden_sensitive_terms() -> None:
    markdown = render_live_order_operator_review_markdown(_procedure().procedure)
    forbidden_terms = (
        "api_key",
        "api_secret",
        "signature",
        "headers",
        "raw_request",
        "raw_response_value",
        "clientOrderId",
        "positionId",
        "executionId",
    )

    for term in forbidden_terms:
        assert term not in markdown


def test_operator_review_serialization_and_repr_do_not_include_sensitive_artifacts() -> None:
    procedure = _procedure().procedure
    serialized = str(asdict(procedure))
    rendered = repr(procedure)
    forbidden_terms = (
        "api_key",
        "api_secret",
        "signature",
        "headers",
        "raw_request",
        "raw_response_value",
        "clientOrderId",
        "positionId",
        "executionId",
    )

    for term in forbidden_terms:
        assert term not in serialized
        assert term not in rendered


def test_operator_review_builder_does_not_accept_forbidden_order_or_credential_fields() -> None:
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
    }

    for key, value in forbidden_kwargs.items():
        try:
            build_live_order_operator_review_procedure(
                bundle=_bundle(),
                created_at=CREATED_AT,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_operator_review_module_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_operator_review as module

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
