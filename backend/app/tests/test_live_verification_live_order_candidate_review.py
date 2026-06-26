from __future__ import annotations

from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.live_order_candidate import (
    LiveOrderCandidate,
    LiveOrderCandidateSide,
    LiveOrderCandidateSourceType,
    StrategySignalInput,
    build_live_order_candidate_dry_run,
)
from app.live_verification.live_order_candidate_review import (
    LIVE_ORDER_CANDIDATE_REVIEW_ID_PREFIX,
    LiveOrderCandidateReviewBlockReason,
    LiveOrderCandidateReviewReport,
    LiveOrderCandidateReviewStatus,
    build_live_order_candidate_review_report,
    make_live_order_candidate_review_id,
    render_live_order_candidate_review_markdown,
)
from app.live_verification.live_order_candidate_risk_gate import (
    LiveOrderCandidateRiskBlockReason,
    LiveOrderCandidateRiskDecision,
    LiveOrderCandidateRiskSnapshot,
    evaluate_live_order_candidate_risk_gate,
)
from app.live_verification.live_order_candidate_trace import (
    LiveOrderCandidateTraceBlockReason,
    LiveOrderCandidateTraceRecord,
    build_live_order_candidate_trace_record,
)

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


def _candidate(**overrides: object) -> LiveOrderCandidate:
    signal = StrategySignalInput(
        source_signal_id="signal_step5e_001",
        source_type=LiveOrderCandidateSourceType.STRATEGY_SIGNAL,
        strategy_name="rsi_reversal",
        symbol="USD_JPY",
        side=LiveOrderCandidateSide.BUY,
        confidence=0.8,
        rationale="sanitized review fixture",
        market_snapshot_ref="snapshot_ref_001",
        paper_trade_ref="paper_ref_001",
        shadow_run_ref="shadow_ref_001",
        created_at=CREATED_AT,
        expires_at=CREATED_AT + timedelta(minutes=10),
    )
    candidate = build_live_order_candidate_dry_run(signal).candidate
    assert candidate is not None
    return _unchecked_candidate(candidate, **overrides)


def _unchecked_candidate(
    base: LiveOrderCandidate,
    **overrides: object,
) -> LiveOrderCandidate:
    values = {field.name: getattr(base, field.name) for field in fields(LiveOrderCandidate)}
    values.update(overrides)
    candidate = object.__new__(LiveOrderCandidate)
    for name, value in values.items():
        object.__setattr__(candidate, name, value)
    return candidate


def _snapshot(**overrides: object) -> LiveOrderCandidateRiskSnapshot:
    values = {
        "snapshot_id": "risk_snapshot_step5e_001",
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


def _decision(
    candidate: LiveOrderCandidate,
    *,
    snapshot: LiveOrderCandidateRiskSnapshot | None = None,
    **overrides: object,
) -> LiveOrderCandidateRiskDecision:
    decision = evaluate_live_order_candidate_risk_gate(
        candidate=candidate,
        snapshot=snapshot or _snapshot(),
    )
    return _unchecked_decision(decision, **overrides)


def _unchecked_decision(
    base: LiveOrderCandidateRiskDecision,
    **overrides: object,
) -> LiveOrderCandidateRiskDecision:
    values = {
        field.name: getattr(base, field.name)
        for field in fields(LiveOrderCandidateRiskDecision)
    }
    values.update(overrides)
    decision = object.__new__(LiveOrderCandidateRiskDecision)
    for name, value in values.items():
        object.__setattr__(decision, name, value)
    return decision


def _trace(
    candidate: LiveOrderCandidate,
    decision: LiveOrderCandidateRiskDecision,
    **overrides: object,
) -> LiveOrderCandidateTraceRecord:
    trace = build_live_order_candidate_trace_record(
        candidate=candidate,
        risk_decision=decision,
        created_at=CREATED_AT,
    ).trace_record
    return _unchecked_trace(trace, **overrides)


def _unchecked_trace(
    base: LiveOrderCandidateTraceRecord,
    **overrides: object,
) -> LiveOrderCandidateTraceRecord:
    values = {
        field.name: getattr(base, field.name)
        for field in fields(LiveOrderCandidateTraceRecord)
    }
    values.update(overrides)
    trace = object.__new__(LiveOrderCandidateTraceRecord)
    for name, value in values.items():
        object.__setattr__(trace, name, value)
    return trace


def _review(
    candidate: LiveOrderCandidate,
    decision: LiveOrderCandidateRiskDecision | None = None,
    trace: LiveOrderCandidateTraceRecord | None = None,
):
    actual_decision = decision or _decision(candidate)
    actual_trace = trace or _trace(candidate, actual_decision)
    return build_live_order_candidate_review_report(
        candidate=candidate,
        risk_decision=actual_decision,
        trace_record=actual_trace,
        created_at=CREATED_AT,
    )


def _assert_blocked(
    *,
    candidate: LiveOrderCandidate,
    decision: LiveOrderCandidateRiskDecision | None = None,
    trace: LiveOrderCandidateTraceRecord | None = None,
    reason: LiveOrderCandidateReviewBlockReason,
) -> None:
    result = _review(candidate, decision=decision, trace=trace)

    assert result.review_status is LiveOrderCandidateReviewStatus.BLOCKED_REVIEW
    assert result.review_report.review_status is LiveOrderCandidateReviewStatus.BLOCKED_REVIEW
    assert result.allowed_for_live is False
    assert result.eligible_for_human_review is False
    assert reason.value in result.blocked_reasons
    assert result.recommended_next_step == "fix_blocked_reasons_no_post"


def test_ready_candidate_passed_risk_decision_and_ready_trace_build_review_report() -> None:
    candidate = _candidate()
    decision = _decision(candidate)
    trace = _trace(candidate, decision)

    result = _review(candidate, decision=decision, trace=trace)
    report = result.review_report

    assert report.review_id.startswith(LIVE_ORDER_CANDIDATE_REVIEW_ID_PREFIX)
    assert report.review_id == make_live_order_candidate_review_id(
        candidate_id=candidate.candidate_id,
        risk_decision_id=decision.decision_id,
        trace_id=trace.trace_id,
        created_at=CREATED_AT,
        review_status=LiveOrderCandidateReviewStatus.READY_FOR_HUMAN_REVIEW,
        blocked_reasons=(),
    )
    assert report.review_status is LiveOrderCandidateReviewStatus.READY_FOR_HUMAN_REVIEW
    assert report.eligible_for_human_review is True
    assert report.risk_gate_passed is True
    assert report.allowed_for_live is False
    assert report.recommended_next_step == "show_to_user_for_review_no_post"
    assert report.candidate_id == candidate.candidate_id
    assert report.risk_decision_id == decision.decision_id
    assert report.trace_id == trace.trace_id
    assert report.symbol == "USD_JPY"
    assert report.side == "BUY"
    assert report.size == 100
    assert report.execution_type == "MARKET"
    assert report.blocked_reasons == ()
    assert report.sections


def test_review_safety_defaults_are_always_fixed() -> None:
    report = _review(_candidate()).review_report

    assert report.allowed_for_live is False
    assert report.requires_human_approval is True
    assert report.approval_gate_required is True
    assert report.dry_run_only is True


def test_blocked_risk_decision_builds_blocked_review() -> None:
    candidate = _candidate()
    decision = _decision(candidate, snapshot=_snapshot(open_positions_count=1))
    trace = _trace(candidate, decision)

    result = _review(candidate, decision=decision, trace=trace)

    assert result.review_status is LiveOrderCandidateReviewStatus.BLOCKED_REVIEW
    assert result.eligible_for_human_review is False
    assert result.allowed_for_live is False
    assert (
        LiveOrderCandidateRiskBlockReason.OPEN_POSITION_EXISTS.value
        in result.blocked_reasons
    )


def test_blocked_trace_builds_blocked_review() -> None:
    candidate = _candidate()
    decision = _decision(candidate)
    trace = _trace(
        candidate,
        decision,
        blocked_reasons=(
            LiveOrderCandidateTraceBlockReason.MISSING_PAPER_SHADOW_REFERENCE.value,
        ),
    )

    result = _review(candidate, decision=decision, trace=trace)

    assert result.review_status is LiveOrderCandidateReviewStatus.BLOCKED_REVIEW
    assert result.eligible_for_human_review is False
    assert (
        LiveOrderCandidateTraceBlockReason.MISSING_PAPER_SHADOW_REFERENCE.value
        in result.blocked_reasons
    )


def test_blocked_reasons_are_merged() -> None:
    candidate = _candidate()
    decision = _decision(candidate, snapshot=_snapshot(open_positions_count=1))
    trace = _trace(
        candidate,
        decision,
        blocked_reasons=(
            LiveOrderCandidateTraceBlockReason.MISSING_PAPER_SHADOW_REFERENCE.value,
        ),
    )

    result = _review(candidate, decision=decision, trace=trace)

    assert {
        LiveOrderCandidateRiskBlockReason.OPEN_POSITION_EXISTS.value,
        LiveOrderCandidateTraceBlockReason.MISSING_PAPER_SHADOW_REFERENCE.value,
    }.issubset(set(result.blocked_reasons))


def test_candidate_id_mismatch_blocks_review() -> None:
    candidate = _candidate()
    decision = _decision(candidate, candidate_id="LOCAND-MISMATCH")
    trace = _trace(candidate, _decision(candidate))

    _assert_blocked(
        candidate=candidate,
        decision=decision,
        trace=trace,
        reason=LiveOrderCandidateReviewBlockReason.CANDIDATE_ID_MISMATCH,
    )


def test_trace_candidate_id_mismatch_blocks_review() -> None:
    candidate = _candidate()
    decision = _decision(candidate)
    trace = _trace(candidate, decision, candidate_id="LOCAND-MISMATCH")

    _assert_blocked(
        candidate=candidate,
        decision=decision,
        trace=trace,
        reason=LiveOrderCandidateReviewBlockReason.CANDIDATE_ID_MISMATCH,
    )


def test_risk_decision_id_mismatch_blocks_review() -> None:
    candidate = _candidate()
    decision = _decision(candidate)
    trace = _trace(candidate, decision, risk_decision_id="LOCRISK-MISMATCH")

    _assert_blocked(
        candidate=candidate,
        decision=decision,
        trace=trace,
        reason=LiveOrderCandidateReviewBlockReason.RISK_DECISION_ID_MISMATCH,
    )


def test_missing_trace_id_blocks_review() -> None:
    candidate = _candidate()
    decision = _decision(candidate)
    trace = _trace(candidate, decision, trace_id="")
    result = _review(candidate, decision=decision, trace=trace)

    assert result.review_status is LiveOrderCandidateReviewStatus.BLOCKED_REVIEW
    assert LiveOrderCandidateReviewBlockReason.MISSING_TRACE_ID.value in result.blocked_reasons
    assert result.review_report.trace_id == "missing_trace_id"


@pytest.mark.parametrize(
    ("candidate_overrides", "decision_overrides", "trace_overrides", "reason"),
    [
        (
            {"allowed_for_live": True},
            {},
            {},
            LiveOrderCandidateReviewBlockReason.CANDIDATE_ALREADY_ALLOWED_FOR_LIVE,
        ),
        (
            {},
            {"allowed_for_live": True},
            {},
            LiveOrderCandidateReviewBlockReason.RISK_DECISION_ALLOWS_LIVE,
        ),
        (
            {},
            {},
            {"allowed_for_live": True},
            LiveOrderCandidateReviewBlockReason.TRACE_RECORD_ALLOWS_LIVE,
        ),
        (
            {"dry_run_only": False},
            {},
            {},
            LiveOrderCandidateReviewBlockReason.CANDIDATE_NOT_DRY_RUN,
        ),
        (
            {},
            {"dry_run_only": False},
            {},
            LiveOrderCandidateReviewBlockReason.RISK_DECISION_NOT_DRY_RUN,
        ),
        (
            {},
            {},
            {"dry_run_only": False},
            LiveOrderCandidateReviewBlockReason.TRACE_RECORD_NOT_DRY_RUN,
        ),
        (
            {"requires_human_approval": False},
            {},
            {},
            LiveOrderCandidateReviewBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        ),
        (
            {},
            {"requires_human_approval": False},
            {},
            LiveOrderCandidateReviewBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        ),
        (
            {},
            {},
            {"requires_human_approval": False},
            LiveOrderCandidateReviewBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        ),
        (
            {"approval_gate_required": False},
            {},
            {},
            LiveOrderCandidateReviewBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        ),
        (
            {},
            {"approval_gate_required": False},
            {},
            LiveOrderCandidateReviewBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        ),
        (
            {},
            {},
            {"approval_gate_required": False},
            LiveOrderCandidateReviewBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        ),
    ],
)
def test_safety_flag_failures_block_review(
    candidate_overrides: dict[str, object],
    decision_overrides: dict[str, object],
    trace_overrides: dict[str, object],
    reason: LiveOrderCandidateReviewBlockReason,
) -> None:
    base_candidate = _candidate()
    candidate = _unchecked_candidate(base_candidate, **candidate_overrides)
    decision = _decision(base_candidate, **decision_overrides)
    trace = _trace(base_candidate, decision, **trace_overrides)

    _assert_blocked(candidate=candidate, decision=decision, trace=trace, reason=reason)


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"symbol": "EUR_USD"}, LiveOrderCandidateReviewBlockReason.UNSUPPORTED_SYMBOL),
        (
            {"side": LiveOrderCandidateSide.NO_TRADE},
            LiveOrderCandidateReviewBlockReason.UNSUPPORTED_SIDE,
        ),
        ({"size": 101}, LiveOrderCandidateReviewBlockReason.UNSUPPORTED_SIZE),
        (
            {"execution_type": "LIMIT"},
            LiveOrderCandidateReviewBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        ),
    ],
)
def test_unsupported_candidate_terms_block_review(
    overrides: dict[str, object],
    reason: LiveOrderCandidateReviewBlockReason,
) -> None:
    candidate = _candidate(**overrides)
    valid_candidate = _candidate()
    decision = _decision(valid_candidate)
    trace = _trace(valid_candidate, decision)

    _assert_blocked(candidate=candidate, decision=decision, trace=trace, reason=reason)


def test_markdown_rendering_includes_dry_run_no_approval_no_live_post_warnings() -> None:
    report = _review(_candidate()).review_report
    markdown = render_live_order_candidate_review_markdown(report)

    assert "This review report is dry-run only." in markdown
    assert "This report is not an approval gate." in markdown
    assert "This report does not authorize live POST." in markdown
    assert "allowed_for_live=false." in markdown
    assert report.review_id in markdown
    assert report.candidate_id in markdown
    assert report.risk_decision_id in markdown
    assert report.trace_id in markdown
    assert "recommended_next_step: show_to_user_for_review_no_post" in markdown


def test_markdown_rendering_excludes_sensitive_artifacts() -> None:
    report = _review(_candidate()).review_report
    markdown = render_live_order_candidate_review_markdown(report)
    blocked_names = {
        "api_key",
        "api_secret",
        "signature",
        "headers",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "open_price",
        "detailed_pl",
    }

    for name in blocked_names:
        assert name not in markdown


def test_review_serialization_and_repr_do_not_include_sensitive_artifacts() -> None:
    report = _review(_candidate()).review_report
    serialized = asdict(report)
    rendered = repr(report)
    blocked_names = {
        "api_key",
        "api_secret",
        "signature",
        "headers",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "open_price",
        "detailed_pl",
    }

    assert set(serialized).isdisjoint(blocked_names)
    for name in blocked_names:
        assert name not in rendered


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "api_key",
        "api_secret",
        "signature",
        "headers",
        "raw_request",
        "raw_response",
        "order_id",
        "execution_id",
        "position_id",
        "clientOrderId",
        "request_url",
        "open_price",
        "detailed_pl",
    ],
)
def test_review_report_does_not_accept_sensitive_or_transport_fields(
    forbidden_field: str,
) -> None:
    kwargs = asdict(_review(_candidate()).review_report)
    kwargs[forbidden_field] = "blocked"

    with pytest.raises(TypeError):
        LiveOrderCandidateReviewReport(**kwargs)


def test_review_module_does_not_depend_on_http_private_api_broker_or_live_runner() -> None:
    import app.live_verification.live_order_candidate_review as module

    module_names = set(module.__dict__)

    assert "post_live_order_with_httpx" not in module_names
    assert "execute_one_shot_live_order" not in module_names
    assert "prepare_one_shot_live_order" not in module_names
    assert "load_live_order_attempt_ledger" not in module_names
    assert "build_step4_approval_gate" not in module_names
