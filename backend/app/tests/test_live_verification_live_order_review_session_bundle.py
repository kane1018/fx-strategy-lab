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
from app.live_verification.live_order_review_session_bundle import (
    REVIEW_GATED_SESSION_BUNDLE_ID_PREFIX,
    ReviewGatedSessionBundleBlockReason,
    ReviewGatedSessionBundleStatus,
    build_review_gated_session_bundle,
    render_review_gated_session_bundle_markdown,
)
from app.live_verification.live_order_session_policy import (
    ReviewGatedSessionPolicyDecision,
    ReviewGatedSessionPolicySnapshot,
    evaluate_review_gated_session_policy,
)

CREATED_AT = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def _candidate(**overrides: object) -> LiveOrderCandidate:
    signal = StrategySignalInput(
        source_signal_id="signal_step5g_001",
        source_type=LiveOrderCandidateSourceType.STRATEGY_SIGNAL,
        strategy_name="rsi_reversal",
        symbol="USD_JPY",
        side=LiveOrderCandidateSide.BUY,
        confidence=0.8,
        rationale="sanitized bundle fixture",
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
        "snapshot_id": "risk_snapshot_step5g_001",
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
        "snapshot_id": "session_snapshot_step5g_001",
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
):
    actual_review = review_report or _review()
    actual_policy = policy_decision or _policy_decision(review_report=actual_review)
    return build_review_gated_session_bundle(
        review_report=actual_review,
        session_policy_decision=actual_policy,
        created_at=CREATED_AT,
        session_count_today=session_count_today,
        daily_live_size_total=daily_live_size_total,
    )


def _assert_blocked(
    *,
    reason: ReviewGatedSessionBundleBlockReason | str,
    review_report: LiveOrderCandidateReviewReport | None = None,
    policy_decision: ReviewGatedSessionPolicyDecision | None = None,
    session_count_today: int | None = 0,
    daily_live_size_total: int | None = 0,
) -> None:
    result = _bundle(
        review_report=review_report,
        policy_decision=policy_decision,
        session_count_today=session_count_today,
        daily_live_size_total=daily_live_size_total,
    )
    expected = reason.value if isinstance(reason, ReviewGatedSessionBundleBlockReason) else reason

    assert result.bundle_status is ReviewGatedSessionBundleStatus.BLOCKED_BUNDLE
    assert result.bundle.bundle_status is ReviewGatedSessionBundleStatus.BLOCKED_BUNDLE
    assert result.allowed_for_live is False
    assert result.eligible_for_review_session is False
    assert result.bundle.policy_passed is False
    assert expected in result.blocked_reasons
    assert result.recommended_next_step == "fix_blocked_reasons_no_post"


def test_ready_review_and_passed_session_policy_build_operator_review_bundle() -> None:
    review = _review()
    policy = _policy_decision(review_report=review)

    result = _bundle(review_report=review, policy_decision=policy)
    bundle = result.bundle

    assert bundle.bundle_id.startswith(REVIEW_GATED_SESSION_BUNDLE_ID_PREFIX)
    assert bundle.bundle_status is ReviewGatedSessionBundleStatus.READY_FOR_OPERATOR_REVIEW
    assert bundle.review_id == review.review_id
    assert bundle.session_policy_decision_id == policy.decision_id
    assert bundle.risk_gate_passed is True
    assert bundle.eligible_for_human_review is True
    assert bundle.policy_passed is True
    assert bundle.eligible_for_review_session is True
    assert bundle.allowed_for_live is False
    assert bundle.symbol == "USD_JPY"
    assert bundle.side == "BUY"
    assert bundle.size == 100
    assert bundle.execution_type == "MARKET"
    assert bundle.remaining_sessions_today == 2
    assert bundle.remaining_daily_size == 200
    assert bundle.recommended_next_step == "operator_review_no_post"
    assert bundle.blocked_reasons == ()
    assert bundle.sections


def test_bundle_safety_defaults_are_always_fixed() -> None:
    bundle = _bundle().bundle

    assert bundle.allowed_for_live is False
    assert bundle.requires_human_approval is True
    assert bundle.approval_gate_required is True
    assert bundle.dry_run_only is True


def test_blocked_review_builds_blocked_bundle() -> None:
    blocked_review = _review(risk_snapshot=_risk_snapshot(open_positions_count=1))
    blocked_policy = _policy_decision(review_report=blocked_review)

    _assert_blocked(
        review_report=blocked_review,
        policy_decision=blocked_policy,
        reason="open_position_exists",
    )


def test_blocked_session_policy_builds_blocked_bundle() -> None:
    review = _review()
    blocked_policy = _policy_decision(
        review_report=review,
        snapshot=_snapshot(active_orders_count=1),
    )

    _assert_blocked(
        review_report=review,
        policy_decision=blocked_policy,
        reason="active_order_exists",
    )


def test_blocked_reasons_are_merged_from_review_and_session_policy() -> None:
    blocked_review = _review(risk_snapshot=_risk_snapshot(open_positions_count=1))
    blocked_policy = _policy_decision(
        review_report=blocked_review,
        snapshot=_snapshot(active_orders_count=1),
    )

    result = _bundle(review_report=blocked_review, policy_decision=blocked_policy)

    assert "open_position_exists" in result.blocked_reasons
    assert "active_order_exists" in result.blocked_reasons


def test_review_id_mismatch_blocks_bundle() -> None:
    review = _review()
    policy = _policy_decision(review_report=review, review_id="LOCREVIEW-DIFFERENT")

    _assert_blocked(
        review_report=review,
        policy_decision=policy,
        reason=ReviewGatedSessionBundleBlockReason.REVIEW_ID_MISMATCH,
    )


def test_review_report_allowed_for_live_blocks_bundle() -> None:
    review = _review(allowed_for_live=True)
    policy = _policy_decision(review_id=review.review_id, candidate_id=review.candidate_id)

    _assert_blocked(
        review_report=review,
        policy_decision=policy,
        reason=ReviewGatedSessionBundleBlockReason.REVIEW_REPORT_ALLOWS_LIVE,
    )


def test_session_policy_allowed_for_live_blocks_bundle() -> None:
    review = _review()
    policy = _policy_decision(review_report=review, allowed_for_live=True)

    _assert_blocked(
        review_report=review,
        policy_decision=policy,
        reason=ReviewGatedSessionBundleBlockReason.SESSION_POLICY_ALLOWS_LIVE,
    )


def test_review_report_not_dry_run_blocks_bundle() -> None:
    review = _review(dry_run_only=False)
    policy = _policy_decision(review_id=review.review_id, candidate_id=review.candidate_id)

    _assert_blocked(
        review_report=review,
        policy_decision=policy,
        reason=ReviewGatedSessionBundleBlockReason.REVIEW_REPORT_NOT_DRY_RUN,
    )


def test_session_policy_not_dry_run_blocks_bundle() -> None:
    review = _review()
    policy = _policy_decision(review_report=review, dry_run_only=False)

    _assert_blocked(
        review_report=review,
        policy_decision=policy,
        reason=ReviewGatedSessionBundleBlockReason.SESSION_POLICY_NOT_DRY_RUN,
    )


def test_missing_human_approval_requirement_blocks_bundle() -> None:
    review = _review(requires_human_approval=False)
    policy = _policy_decision(review_id=review.review_id, candidate_id=review.candidate_id)

    _assert_blocked(
        review_report=review,
        policy_decision=policy,
        reason=ReviewGatedSessionBundleBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
    )


def test_missing_approval_gate_requirement_blocks_bundle() -> None:
    review = _review(approval_gate_required=False)
    policy = _policy_decision(review_id=review.review_id, candidate_id=review.candidate_id)

    _assert_blocked(
        review_report=review,
        policy_decision=policy,
        reason=ReviewGatedSessionBundleBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
    )


def test_unsupported_symbol_blocks_bundle() -> None:
    review = _review(symbol="EUR_USD")
    policy = _policy_decision(review_id=review.review_id, candidate_id=review.candidate_id)

    _assert_blocked(
        review_report=review,
        policy_decision=policy,
        reason=ReviewGatedSessionBundleBlockReason.UNSUPPORTED_SYMBOL,
    )


def test_unsupported_side_blocks_bundle() -> None:
    review = _review(side="NO_TRADE")
    policy = _policy_decision(review_id=review.review_id, candidate_id=review.candidate_id)

    _assert_blocked(
        review_report=review,
        policy_decision=policy,
        reason=ReviewGatedSessionBundleBlockReason.UNSUPPORTED_SIDE,
    )


def test_unsupported_size_blocks_bundle() -> None:
    review = _review(size=200)
    policy = _policy_decision(review_id=review.review_id, candidate_id=review.candidate_id)

    _assert_blocked(
        review_report=review,
        policy_decision=policy,
        reason=ReviewGatedSessionBundleBlockReason.UNSUPPORTED_SIZE,
    )


def test_unsupported_execution_type_blocks_bundle() -> None:
    review = _review(execution_type="LIMIT")
    policy = _policy_decision(review_id=review.review_id, candidate_id=review.candidate_id)

    _assert_blocked(
        review_report=review,
        policy_decision=policy,
        reason=ReviewGatedSessionBundleBlockReason.UNSUPPORTED_EXECUTION_TYPE,
    )


def test_remaining_capacity_is_calculated_for_second_review_session() -> None:
    review = _review()
    snapshot = _snapshot(
        session_count_today=1,
        daily_live_size_total=100,
        minutes_since_last_session=120,
    )
    policy = _policy_decision(review_report=review, snapshot=snapshot)

    result = _bundle(
        review_report=review,
        policy_decision=policy,
        session_count_today=1,
        daily_live_size_total=100,
    )

    assert result.bundle.bundle_status is ReviewGatedSessionBundleStatus.READY_FOR_OPERATOR_REVIEW
    assert result.bundle.remaining_sessions_today == 1
    assert result.bundle.remaining_daily_size == 100


def test_missing_session_count_blocks_bundle() -> None:
    _assert_blocked(
        reason=ReviewGatedSessionBundleBlockReason.MISSING_SESSION_COUNT,
        session_count_today=None,
    )


def test_missing_daily_size_total_blocks_bundle() -> None:
    _assert_blocked(
        reason=ReviewGatedSessionBundleBlockReason.MISSING_DAILY_SIZE_TOTAL,
        daily_live_size_total=None,
    )


def test_negative_remaining_sessions_blocks_bundle() -> None:
    _assert_blocked(
        reason=ReviewGatedSessionBundleBlockReason.INVALID_REMAINING_SESSIONS,
        session_count_today=3,
    )


def test_negative_remaining_daily_size_blocks_bundle() -> None:
    _assert_blocked(
        reason=ReviewGatedSessionBundleBlockReason.INVALID_REMAINING_DAILY_SIZE,
        daily_live_size_total=250,
    )


def test_markdown_rendering_includes_warnings_and_remaining_capacity() -> None:
    markdown = render_review_gated_session_bundle_markdown(_bundle().bundle)

    assert "This operation bundle is dry-run only." in markdown
    assert "This bundle is not an approval gate." in markdown
    assert "This bundle does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown
    assert "remaining_sessions_today: 2" in markdown
    assert "remaining_daily_size: 200" in markdown


def test_markdown_rendering_omits_forbidden_sensitive_terms() -> None:
    markdown = render_review_gated_session_bundle_markdown(_bundle().bundle)
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


def test_bundle_serialization_and_repr_do_not_include_sensitive_artifacts() -> None:
    bundle = _bundle().bundle
    serialized = str(asdict(bundle))
    rendered = repr(bundle)
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


def test_bundle_builder_does_not_accept_forbidden_order_or_credential_fields() -> None:
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
            build_review_gated_session_bundle(
                review_report=_review(),
                session_policy_decision=_policy_decision(),
                created_at=CREATED_AT,
                session_count_today=0,
                daily_live_size_total=0,
                **{key: value},
            )
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_review_session_bundle_module_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_review_session_bundle as module

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
