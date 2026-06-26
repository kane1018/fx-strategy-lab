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
from app.live_verification.live_order_session_policy import (
    REVIEW_GATED_SESSION_POLICY_DECISION_ID_PREFIX,
    ReviewGatedSessionPolicyBlockReason,
    ReviewGatedSessionPolicyDecision,
    ReviewGatedSessionPolicySnapshot,
    ReviewGatedSessionPolicyStatus,
    evaluate_review_gated_session_policy,
    make_review_gated_session_policy_decision_id,
)

CREATED_AT = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def _candidate(**overrides: object) -> LiveOrderCandidate:
    signal = StrategySignalInput(
        source_signal_id="signal_step5f_001",
        source_type=LiveOrderCandidateSourceType.STRATEGY_SIGNAL,
        strategy_name="rsi_reversal",
        symbol="USD_JPY",
        side=LiveOrderCandidateSide.BUY,
        confidence=0.8,
        rationale="sanitized session policy fixture",
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
        "snapshot_id": "risk_snapshot_step5f_001",
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


def _review(candidate: LiveOrderCandidate | None = None, **overrides: object):
    actual_candidate = candidate or _candidate()
    risk_decision = evaluate_live_order_candidate_risk_gate(
        candidate=actual_candidate,
        snapshot=_risk_snapshot(),
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


def _blocked_review() -> LiveOrderCandidateReviewReport:
    candidate = _candidate()
    risk_decision = evaluate_live_order_candidate_risk_gate(
        candidate=candidate,
        snapshot=_risk_snapshot(open_positions_count=1),
    )
    trace = build_live_order_candidate_trace_record(
        candidate=candidate,
        risk_decision=risk_decision,
        created_at=CREATED_AT,
    ).trace_record
    return build_live_order_candidate_review_report(
        candidate=candidate,
        risk_decision=risk_decision,
        trace_record=trace,
        created_at=CREATED_AT,
    ).review_report


def _snapshot(**overrides: object) -> ReviewGatedSessionPolicySnapshot:
    values = {
        "snapshot_id": "session_snapshot_step5f_001",
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


def _decision(
    *,
    review_report: LiveOrderCandidateReviewReport | None = None,
    snapshot: ReviewGatedSessionPolicySnapshot | None = None,
) -> ReviewGatedSessionPolicyDecision:
    return evaluate_review_gated_session_policy(
        review_report=review_report or _review(),
        snapshot=snapshot or _snapshot(),
    )


def _assert_blocked(
    *,
    reason: ReviewGatedSessionPolicyBlockReason,
    review_report: LiveOrderCandidateReviewReport | None = None,
    snapshot: ReviewGatedSessionPolicySnapshot | None = None,
) -> None:
    decision = _decision(review_report=review_report, snapshot=snapshot)

    assert decision.status is ReviewGatedSessionPolicyStatus.BLOCKED
    assert decision.policy_passed is False
    assert decision.eligible_for_review_session is False
    assert decision.allowed_for_live is False
    assert reason.value in decision.blocked_reasons
    assert decision.recommended_next_step == "fix_session_policy_inputs_no_post"


def test_ready_review_and_safe_session_snapshot_pass_policy_for_review_only() -> None:
    review = _review()
    snapshot = _snapshot()

    decision = _decision(review_report=review, snapshot=snapshot)

    assert decision.decision_id.startswith(REVIEW_GATED_SESSION_POLICY_DECISION_ID_PREFIX)
    assert decision.decision_id == make_review_gated_session_policy_decision_id(
        review_id=review.review_id,
        candidate_id=review.candidate_id,
        snapshot_id=snapshot.snapshot_id,
        created_at=snapshot.created_at,
        blocked_reasons=(),
    )
    assert decision.status is ReviewGatedSessionPolicyStatus.POLICY_PASSED_FOR_REVIEW
    assert decision.policy_passed is True
    assert decision.eligible_for_review_session is True
    assert decision.allowed_for_live is False
    assert decision.session_size == 100
    assert decision.max_sessions_per_day == 2
    assert decision.min_minutes_between_sessions == 120
    assert decision.max_daily_size_total == 200
    assert decision.blocked_reasons == ()
    assert (
        decision.recommended_next_step
        == "proceed_to_review_gated_session_design_no_post"
    )


def test_session_policy_safety_defaults_are_always_fixed() -> None:
    decision = _decision()

    assert decision.allowed_for_live is False
    assert decision.requires_human_approval is True
    assert decision.approval_gate_required is True
    assert decision.dry_run_only is True


def test_blocked_review_blocks_session_policy() -> None:
    _assert_blocked(
        review_report=_blocked_review(),
        reason=ReviewGatedSessionPolicyBlockReason.INVALID_REVIEW_STATUS,
    )


def test_review_allowed_for_live_blocks_policy() -> None:
    _assert_blocked(
        review_report=_review(allowed_for_live=True),
        reason=ReviewGatedSessionPolicyBlockReason.REVIEW_ALREADY_ALLOWED_FOR_LIVE,
    )


def test_review_not_dry_run_blocks_policy() -> None:
    _assert_blocked(
        review_report=_review(dry_run_only=False),
        reason=ReviewGatedSessionPolicyBlockReason.REVIEW_NOT_DRY_RUN,
    )


def test_missing_human_approval_requirement_blocks_policy() -> None:
    _assert_blocked(
        review_report=_review(requires_human_approval=False),
        reason=ReviewGatedSessionPolicyBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
    )


def test_missing_approval_gate_requirement_blocks_policy() -> None:
    _assert_blocked(
        review_report=_review(approval_gate_required=False),
        reason=ReviewGatedSessionPolicyBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
    )


def test_unsupported_symbol_blocks_policy() -> None:
    _assert_blocked(
        review_report=_review(symbol="EUR_USD"),
        reason=ReviewGatedSessionPolicyBlockReason.UNSUPPORTED_SYMBOL,
    )


def test_unsupported_side_blocks_policy() -> None:
    _assert_blocked(
        review_report=_review(side="NO_TRADE"),
        reason=ReviewGatedSessionPolicyBlockReason.UNSUPPORTED_SIDE,
    )


def test_unsupported_size_blocks_policy() -> None:
    _assert_blocked(
        review_report=_review(size=200),
        reason=ReviewGatedSessionPolicyBlockReason.UNSUPPORTED_SIZE,
    )


def test_unsupported_execution_type_blocks_policy() -> None:
    _assert_blocked(
        review_report=_review(execution_type="LIMIT"),
        reason=ReviewGatedSessionPolicyBlockReason.UNSUPPORTED_EXECUTION_TYPE,
    )


def test_initial_micro_live_not_completed_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(initial_micro_live_completed=False),
        reason=ReviewGatedSessionPolicyBlockReason.INITIAL_MICRO_LIVE_NOT_COMPLETED,
    )


def test_previous_order_result_not_confirmed_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(previous_order_result_confirmed=False),
        reason=ReviewGatedSessionPolicyBlockReason.PREVIOUS_ORDER_RESULT_NOT_CONFIRMED,
    )


def test_previous_result_unknown_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(previous_result_unknown=True),
        reason=ReviewGatedSessionPolicyBlockReason.PREVIOUS_RESULT_UNKNOWN_STATE,
    )


def test_open_position_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(open_positions_count=1),
        reason=ReviewGatedSessionPolicyBlockReason.OPEN_POSITION_EXISTS,
    )


def test_active_order_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(active_orders_count=1),
        reason=ReviewGatedSessionPolicyBlockReason.ACTIVE_ORDER_EXISTS,
    )


def test_max_sessions_per_day_reached_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(session_count_today=2),
        reason=ReviewGatedSessionPolicyBlockReason.MAX_SESSIONS_PER_DAY_REACHED,
    )


def test_unsupported_session_size_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(session_size=200),
        reason=ReviewGatedSessionPolicyBlockReason.UNSUPPORTED_SESSION_SIZE,
    )


def test_daily_size_limit_exceeded_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(daily_live_size_total=150),
        reason=ReviewGatedSessionPolicyBlockReason.DAILY_SIZE_LIMIT_EXCEEDED,
    )


def test_session_interval_too_short_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(session_count_today=1, minutes_since_last_session=119),
        reason=ReviewGatedSessionPolicyBlockReason.SESSION_INTERVAL_TOO_SHORT,
    )


def test_second_session_after_two_hours_passes_interval_rule() -> None:
    decision = _decision(
        snapshot=_snapshot(session_count_today=1, minutes_since_last_session=120),
    )

    assert decision.policy_passed is True
    assert decision.eligible_for_review_session is True
    assert decision.allowed_for_live is False


def test_git_not_clean_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(git_clean=False),
        reason=ReviewGatedSessionPolicyBlockReason.GIT_NOT_CLEAN,
    )


def test_tests_not_passed_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(tests_passed=False),
        reason=ReviewGatedSessionPolicyBlockReason.TESTS_NOT_PASSED,
    )


def test_ruff_not_passed_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(ruff_passed=False),
        reason=ReviewGatedSessionPolicyBlockReason.RUFF_NOT_PASSED,
    )


def test_secret_scan_not_passed_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(secret_scan_passed=False),
        reason=ReviewGatedSessionPolicyBlockReason.SECRET_SCAN_NOT_PASSED,
    )


def test_raw_response_saved_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(raw_response_saved=True),
        reason=ReviewGatedSessionPolicyBlockReason.RAW_RESPONSE_SAVED,
    )


def test_raw_response_displayed_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(raw_response_displayed=True),
        reason=ReviewGatedSessionPolicyBlockReason.RAW_RESPONSE_DISPLAYED,
    )


def test_market_window_not_allowed_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(market_window_allowed=False),
        reason=ReviewGatedSessionPolicyBlockReason.MARKET_WINDOW_NOT_ALLOWED,
    )


def test_maintenance_active_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(maintenance_active=True),
        reason=ReviewGatedSessionPolicyBlockReason.MAINTENANCE_ACTIVE,
    )


def test_important_event_window_not_confirmed_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(important_event_window_ok=False),
        reason=ReviewGatedSessionPolicyBlockReason.IMPORTANT_EVENT_WINDOW_NOT_CONFIRMED,
    )


def test_missing_important_event_window_blocks_fail_closed() -> None:
    _assert_blocked(
        snapshot=_snapshot(important_event_window_ok=None),
        reason=ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT,
    )


def test_missing_required_session_input_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(snapshot_id=None),
        reason=ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT,
    )


def test_invalid_session_input_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(created_at=None),
        reason=ReviewGatedSessionPolicyBlockReason.INVALID_SESSION_INPUT,
    )


def test_missing_interval_for_second_session_blocks_policy() -> None:
    _assert_blocked(
        snapshot=_snapshot(session_count_today=1, minutes_since_last_session=None),
        reason=ReviewGatedSessionPolicyBlockReason.MISSING_REQUIRED_SESSION_INPUT,
    )


def test_multiple_failures_return_multiple_blocked_reasons() -> None:
    decision = _decision(
        snapshot=_snapshot(
            open_positions_count=1,
            active_orders_count=1,
            git_clean=False,
            raw_response_saved=True,
        )
    )

    assert {
        ReviewGatedSessionPolicyBlockReason.OPEN_POSITION_EXISTS.value,
        ReviewGatedSessionPolicyBlockReason.ACTIVE_ORDER_EXISTS.value,
        ReviewGatedSessionPolicyBlockReason.GIT_NOT_CLEAN.value,
        ReviewGatedSessionPolicyBlockReason.RAW_RESPONSE_SAVED.value,
    }.issubset(set(decision.blocked_reasons))


def test_session_policy_serialization_and_repr_do_not_include_sensitive_artifacts() -> None:
    decision = _decision()
    serialized = str(asdict(decision))
    rendered = repr(decision)

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


def test_snapshot_does_not_accept_forbidden_order_or_credential_fields() -> None:
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
            ReviewGatedSessionPolicySnapshot(**(_snapshot().__dict__ | {key: value}))
        except TypeError:
            pass
        else:  # pragma: no cover - defensive assertion
            raise AssertionError(f"forbidden field accepted: {key}")


def test_session_policy_module_has_no_ordering_or_api_dependencies() -> None:
    import app.live_verification.live_order_session_policy as module

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
