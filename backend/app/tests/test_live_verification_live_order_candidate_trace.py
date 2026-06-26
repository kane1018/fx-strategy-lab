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
from app.live_verification.live_order_candidate_risk_gate import (
    LiveOrderCandidateRiskBlockReason,
    LiveOrderCandidateRiskDecision,
    LiveOrderCandidateRiskSnapshot,
    LiveOrderCandidateRiskStatus,
    evaluate_live_order_candidate_risk_gate,
)
from app.live_verification.live_order_candidate_trace import (
    LIVE_ORDER_CANDIDATE_TRACE_ID_PREFIX,
    LiveOrderCandidateTraceBlockReason,
    LiveOrderCandidateTraceRecord,
    LiveOrderCandidateTraceStatus,
    build_live_order_candidate_trace_record,
    make_live_order_candidate_trace_id,
)

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


def _candidate(
    *,
    paper_trade_ref: str | None = "paper_ref_001",
    shadow_run_ref: str | None = None,
    signal_side: LiveOrderCandidateSide = LiveOrderCandidateSide.BUY,
    **overrides: object,
) -> LiveOrderCandidate:
    signal = StrategySignalInput(
        source_signal_id="signal_step5d_001",
        source_type=LiveOrderCandidateSourceType.STRATEGY_SIGNAL,
        strategy_name="rsi_reversal",
        symbol="USD_JPY",
        side=signal_side,
        confidence=0.8,
        rationale="sanitized trace fixture",
        market_snapshot_ref="snapshot_ref_001",
        paper_trade_ref=paper_trade_ref,
        shadow_run_ref=shadow_run_ref,
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
        "snapshot_id": "risk_snapshot_step5d_001",
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
    decision: LiveOrderCandidateRiskDecision | None = None,
    **overrides: object,
):
    return build_live_order_candidate_trace_record(
        candidate=candidate,
        risk_decision=decision or _decision(candidate),
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    candidate: LiveOrderCandidate,
    decision: LiveOrderCandidateRiskDecision,
    reason: LiveOrderCandidateTraceBlockReason,
) -> None:
    result = _trace(candidate, decision)

    assert result.trace_status is LiveOrderCandidateTraceStatus.BLOCKED
    assert result.trace_record.trace_status is LiveOrderCandidateTraceStatus.BLOCKED
    assert result.allowed_for_live is False
    assert result.eligible_for_human_review is False
    assert reason.value in result.blocked_reasons
    assert result.recommended_next_step == "fix_trace_inputs_no_post"


def test_valid_candidate_passed_risk_decision_and_paper_ref_are_ready_for_review() -> None:
    candidate = _candidate(paper_trade_ref="paper_ref_001", shadow_run_ref=None)
    decision = _decision(candidate)
    result = _trace(candidate, decision)
    trace = result.trace_record

    assert trace.trace_id.startswith(LIVE_ORDER_CANDIDATE_TRACE_ID_PREFIX)
    assert trace.trace_id == make_live_order_candidate_trace_id(
        candidate_id=candidate.candidate_id,
        risk_decision_id=decision.decision_id,
        source_signal_id=candidate.source_signal_id,
        created_at=CREATED_AT,
        paper_trade_ref=candidate.paper_trade_ref,
        shadow_run_ref=candidate.shadow_run_ref,
        paper_decision_ref=None,
        shadow_decision_ref=None,
        review_batch_id=None,
    )
    assert trace.trace_status is LiveOrderCandidateTraceStatus.READY_FOR_REVIEW
    assert trace.eligible_for_human_review is True
    assert trace.risk_gate_passed is True
    assert trace.allowed_for_live is False
    assert trace.paper_trade_ref == "paper_ref_001"
    assert trace.shadow_run_ref is None
    assert trace.candidate_id == decision.candidate_id
    assert trace.risk_decision_id == decision.decision_id
    assert trace.recommended_next_step == "proceed_to_candidate_review_no_post"


def test_valid_candidate_passed_risk_decision_and_shadow_ref_are_ready_for_review() -> None:
    candidate = _candidate(paper_trade_ref=None, shadow_run_ref="shadow_ref_001")
    result = _trace(candidate)

    assert result.trace_status is LiveOrderCandidateTraceStatus.READY_FOR_REVIEW
    assert result.trace_record.paper_trade_ref is None
    assert result.trace_record.shadow_run_ref == "shadow_ref_001"
    assert result.trace_record.allowed_for_live is False


def test_valid_candidate_passed_risk_decision_with_both_refs_is_ready_for_review() -> None:
    candidate = _candidate(paper_trade_ref="paper_ref_001", shadow_run_ref="shadow_ref_001")
    result = _trace(candidate, review_batch_id="review_batch_step5d_001")

    assert result.trace_status is LiveOrderCandidateTraceStatus.READY_FOR_REVIEW
    assert result.trace_record.paper_trade_ref == "paper_ref_001"
    assert result.trace_record.shadow_run_ref == "shadow_ref_001"
    assert result.trace_record.review_batch_id == "review_batch_step5d_001"


def test_risk_decision_blocked_records_audit_trace_without_human_review_eligibility() -> None:
    candidate = _candidate()
    decision = _decision(candidate, snapshot=_snapshot(open_positions_count=1))

    result = _trace(candidate, decision)

    assert result.trace_status is LiveOrderCandidateTraceStatus.BLOCKED_TRACE_RECORDED
    assert result.trace_record.risk_status == LiveOrderCandidateRiskStatus.BLOCKED.value
    assert result.trace_record.risk_gate_passed is False
    assert result.trace_record.eligible_for_human_review is False
    assert result.trace_record.allowed_for_live is False
    assert (
        LiveOrderCandidateRiskBlockReason.OPEN_POSITION_EXISTS.value
        in result.trace_record.blocked_reasons
    )
    assert result.recommended_next_step == "fix_risk_inputs_or_wait_no_post"


def test_risk_decision_blocked_reasons_are_preserved() -> None:
    candidate = _candidate()
    decision = _decision(
        candidate,
        snapshot=_snapshot(open_positions_count=1, active_orders_count=1),
    )

    result = _trace(candidate, decision)

    assert {
        LiveOrderCandidateRiskBlockReason.OPEN_POSITION_EXISTS.value,
        LiveOrderCandidateRiskBlockReason.ACTIVE_ORDER_EXISTS.value,
    }.issubset(set(result.blocked_reasons))


def test_candidate_id_mismatch_blocks_trace() -> None:
    candidate = _candidate()
    decision = _decision(candidate, candidate_id="LOCAND-MISMATCH")

    _assert_blocked(
        candidate,
        decision,
        LiveOrderCandidateTraceBlockReason.CANDIDATE_ID_MISMATCH,
    )


def test_candidate_allowed_for_live_blocks_trace() -> None:
    candidate = _candidate(allowed_for_live=True)
    decision = _decision(_candidate())

    _assert_blocked(
        candidate,
        decision,
        LiveOrderCandidateTraceBlockReason.CANDIDATE_ALREADY_ALLOWED_FOR_LIVE,
    )


def test_risk_decision_allowed_for_live_blocks_trace() -> None:
    candidate = _candidate()
    decision = _decision(candidate, allowed_for_live=True)

    _assert_blocked(
        candidate,
        decision,
        LiveOrderCandidateTraceBlockReason.RISK_DECISION_ALLOWS_LIVE,
    )


def test_candidate_not_dry_run_blocks_trace() -> None:
    candidate = _candidate(dry_run_only=False)
    decision = _decision(_candidate())

    _assert_blocked(
        candidate,
        decision,
        LiveOrderCandidateTraceBlockReason.CANDIDATE_NOT_DRY_RUN,
    )


def test_risk_decision_not_dry_run_blocks_trace() -> None:
    candidate = _candidate()
    decision = _decision(candidate, dry_run_only=False)

    _assert_blocked(
        candidate,
        decision,
        LiveOrderCandidateTraceBlockReason.RISK_DECISION_NOT_DRY_RUN,
    )


def test_missing_human_approval_requirement_blocks_trace() -> None:
    candidate = _candidate(requires_human_approval=False)
    decision = _decision(_candidate())

    _assert_blocked(
        candidate,
        decision,
        LiveOrderCandidateTraceBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
    )


def test_missing_risk_decision_human_approval_requirement_blocks_trace() -> None:
    candidate = _candidate()
    decision = _decision(candidate, requires_human_approval=False)

    _assert_blocked(
        candidate,
        decision,
        LiveOrderCandidateTraceBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
    )


def test_missing_approval_gate_requirement_blocks_trace() -> None:
    candidate = _candidate(approval_gate_required=False)
    decision = _decision(_candidate())

    _assert_blocked(
        candidate,
        decision,
        LiveOrderCandidateTraceBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
    )


def test_missing_risk_decision_approval_gate_requirement_blocks_trace() -> None:
    candidate = _candidate()
    decision = _decision(candidate, approval_gate_required=False)

    _assert_blocked(
        candidate,
        decision,
        LiveOrderCandidateTraceBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
    )


def test_missing_source_signal_id_blocks_trace() -> None:
    candidate = _candidate(source_signal_id="")
    decision = _decision(_candidate())
    result = _trace(candidate, decision)

    assert result.trace_status is LiveOrderCandidateTraceStatus.BLOCKED
    assert (
        LiveOrderCandidateTraceBlockReason.MISSING_SOURCE_SIGNAL_ID.value
        in result.blocked_reasons
    )
    assert result.trace_record.source_signal_id == "missing_source_signal_id"


def test_missing_paper_and_shadow_refs_blocks_trace() -> None:
    candidate = _candidate(paper_trade_ref=None, shadow_run_ref=None)
    decision = _decision(candidate)

    _assert_blocked(
        candidate,
        decision,
        LiveOrderCandidateTraceBlockReason.MISSING_PAPER_SHADOW_REFERENCE,
    )


def test_optional_paper_decision_ref_can_supply_review_trace_reference() -> None:
    candidate = _candidate(paper_trade_ref=None, shadow_run_ref=None)
    result = _trace(candidate, paper_decision_ref="paper_decision_ref_001")

    assert result.trace_status is LiveOrderCandidateTraceStatus.READY_FOR_REVIEW
    assert result.trace_record.paper_decision_ref == "paper_decision_ref_001"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"symbol": "EUR_USD"}, LiveOrderCandidateTraceBlockReason.UNSUPPORTED_SYMBOL),
        (
            {"side": LiveOrderCandidateSide.NO_TRADE},
            LiveOrderCandidateTraceBlockReason.UNSUPPORTED_SIDE,
        ),
        ({"size": 101}, LiveOrderCandidateTraceBlockReason.UNSUPPORTED_SIZE),
        (
            {"execution_type": "LIMIT"},
            LiveOrderCandidateTraceBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        ),
    ],
)
def test_unsupported_candidate_terms_block_trace(
    overrides: dict[str, object],
    reason: LiveOrderCandidateTraceBlockReason,
) -> None:
    candidate = _candidate(**overrides)
    decision = _decision(_candidate())

    _assert_blocked(candidate, decision, reason)


def test_trace_safety_defaults_are_always_fixed() -> None:
    result = _trace(_candidate())
    trace = result.trace_record

    for target in (result, trace):
        assert target.allowed_for_live is False
        assert target.eligible_for_human_review is True
    assert trace.requires_human_approval is True
    assert trace.approval_gate_required is True
    assert trace.dry_run_only is True


def test_blocked_trace_safety_defaults_are_always_fixed() -> None:
    candidate = _candidate()
    result = _trace(candidate, _decision(candidate, allowed_for_live=True))
    trace = result.trace_record

    assert result.allowed_for_live is False
    assert result.eligible_for_human_review is False
    assert trace.allowed_for_live is False
    assert trace.requires_human_approval is True
    assert trace.approval_gate_required is True
    assert trace.dry_run_only is True


def test_trace_serialization_and_repr_do_not_include_sensitive_artifacts() -> None:
    trace = _trace(_candidate()).trace_record
    serialized = asdict(trace)
    rendered = repr(trace)
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
def test_trace_record_does_not_accept_sensitive_or_transport_fields(
    forbidden_field: str,
) -> None:
    kwargs = asdict(_trace(_candidate()).trace_record)
    kwargs[forbidden_field] = "blocked"

    with pytest.raises(TypeError):
        LiveOrderCandidateTraceRecord(**kwargs)


def test_trace_module_does_not_depend_on_http_private_api_broker_or_live_runner() -> None:
    import app.live_verification.live_order_candidate_trace as module

    module_names = set(module.__dict__)

    assert "post_live_order_with_httpx" not in module_names
    assert "execute_one_shot_live_order" not in module_names
    assert "prepare_one_shot_live_order" not in module_names
    assert "load_live_order_attempt_ledger" not in module_names
    assert "build_step4_approval_gate" not in module_names
