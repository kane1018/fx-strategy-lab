from __future__ import annotations

from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.live_order_candidate import (
    LiveOrderCandidate,
    LiveOrderCandidateSide,
    LiveOrderCandidateSourceType,
    LiveOrderCandidateStatus,
    StrategySignalInput,
    build_live_order_candidate_dry_run,
)
from app.live_verification.live_order_candidate_risk_gate import (
    LIVE_ORDER_CANDIDATE_MAX_SPREAD_JPY,
    LIVE_ORDER_CANDIDATE_MAX_TICKER_AGE_SECONDS,
    LIVE_ORDER_CANDIDATE_RISK_DECISION_ID_PREFIX,
    LiveOrderCandidateRiskBlockReason,
    LiveOrderCandidateRiskDecision,
    LiveOrderCandidateRiskSnapshot,
    LiveOrderCandidateRiskStatus,
    evaluate_live_order_candidate_risk_gate,
    make_live_order_candidate_risk_decision_id,
)

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
_DEFAULT_CANDIDATE = object()
_DEFAULT_SNAPSHOT = object()


def _candidate(**overrides: object) -> LiveOrderCandidate:
    signal = StrategySignalInput(
        source_signal_id="signal_step5c_001",
        source_type=LiveOrderCandidateSourceType.STRATEGY_SIGNAL,
        strategy_name="rsi_reversal",
        symbol="USD_JPY",
        side=overrides.pop("signal_side", LiveOrderCandidateSide.BUY),
        confidence=0.8,
        rationale="sanitized risk gate fixture",
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
        "snapshot_id": "risk_snapshot_step5c_001",
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
    *,
    candidate: LiveOrderCandidate | None | object = _DEFAULT_CANDIDATE,
    snapshot: LiveOrderCandidateRiskSnapshot | object = _DEFAULT_SNAPSHOT,
) -> LiveOrderCandidateRiskDecision:
    return evaluate_live_order_candidate_risk_gate(
        candidate=_candidate() if candidate is _DEFAULT_CANDIDATE else candidate,
        snapshot=_snapshot() if snapshot is _DEFAULT_SNAPSHOT else snapshot,
    )


def _assert_blocked(
    decision: LiveOrderCandidateRiskDecision,
    reason: LiveOrderCandidateRiskBlockReason,
) -> None:
    assert decision.status is LiveOrderCandidateRiskStatus.BLOCKED
    assert decision.risk_gate_passed is False
    assert decision.eligible_for_human_review is False
    assert decision.allowed_for_live is False
    assert reason.value in decision.blocked_reasons
    assert decision.recommended_next_step == "fix_inputs_or_wait_no_post"


def test_valid_buy_candidate_and_safe_snapshot_pass_for_human_review_only() -> None:
    decision = _decision(candidate=_candidate(signal_side=LiveOrderCandidateSide.BUY))

    assert decision.decision_id.startswith(LIVE_ORDER_CANDIDATE_RISK_DECISION_ID_PREFIX)
    assert decision.status is LiveOrderCandidateRiskStatus.PASSED_FOR_HUMAN_REVIEW
    assert decision.risk_gate_passed is True
    assert decision.eligible_for_human_review is True
    assert decision.allowed_for_live is False
    assert decision.requires_human_approval is True
    assert decision.approval_gate_required is True
    assert decision.dry_run_only is True
    assert decision.blocked_reasons == ()
    assert decision.recommended_next_step == "proceed_to_candidate_review_no_post"


def test_valid_sell_candidate_and_safe_snapshot_pass_for_human_review_only() -> None:
    decision = _decision(candidate=_candidate(signal_side=LiveOrderCandidateSide.SELL))

    assert decision.risk_gate_passed is True
    assert decision.eligible_for_human_review is True
    assert decision.allowed_for_live is False


def test_decision_id_is_deterministic_and_not_order_execution_or_position_id() -> None:
    candidate = _candidate()
    snapshot = _snapshot()
    first = _decision(candidate=candidate, snapshot=snapshot)
    second = _decision(candidate=candidate, snapshot=snapshot)
    expected = make_live_order_candidate_risk_decision_id(
        candidate_id=candidate.candidate_id,
        snapshot_id=snapshot.snapshot_id,
        created_at=snapshot.created_at,
        blocked_reasons=(),
    )

    assert first.decision_id == second.decision_id == expected
    assert first.decision_id.startswith("LOCRISK-")
    assert not first.decision_id.startswith(("order_", "execution_", "position_"))


@pytest.mark.parametrize(
    ("candidate", "reason"),
    [
        (None, LiveOrderCandidateRiskBlockReason.INVALID_CANDIDATE_STATUS),
        (
            _candidate(status=LiveOrderCandidateStatus.BLOCKED),
            LiveOrderCandidateRiskBlockReason.INVALID_CANDIDATE_STATUS,
        ),
        (
            _candidate(allowed_for_live=True),
            LiveOrderCandidateRiskBlockReason.CANDIDATE_ALREADY_ALLOWED_FOR_LIVE,
        ),
        (
            _candidate(dry_run_only=False),
            LiveOrderCandidateRiskBlockReason.CANDIDATE_NOT_DRY_RUN,
        ),
        (
            _candidate(requires_human_approval=False),
            LiveOrderCandidateRiskBlockReason.MISSING_HUMAN_APPROVAL_REQUIREMENT,
        ),
        (
            _candidate(risk_gate_required=False),
            LiveOrderCandidateRiskBlockReason.MISSING_RISK_GATE_REQUIREMENT,
        ),
        (
            _candidate(approval_gate_required=False),
            LiveOrderCandidateRiskBlockReason.MISSING_APPROVAL_GATE_REQUIREMENT,
        ),
        (
            _candidate(symbol="EUR_USD"),
            LiveOrderCandidateRiskBlockReason.UNSUPPORTED_SYMBOL,
        ),
        (
            _candidate(side=LiveOrderCandidateSide.NO_TRADE),
            LiveOrderCandidateRiskBlockReason.UNSUPPORTED_SIDE,
        ),
        (
            _candidate(size=101),
            LiveOrderCandidateRiskBlockReason.UNSUPPORTED_SIZE,
        ),
        (
            _candidate(execution_type="LIMIT"),
            LiveOrderCandidateRiskBlockReason.UNSUPPORTED_EXECUTION_TYPE,
        ),
    ],
)
def test_invalid_candidate_inputs_block(
    candidate: LiveOrderCandidate | None,
    reason: LiveOrderCandidateRiskBlockReason,
) -> None:
    _assert_blocked(_decision(candidate=candidate), reason)


@pytest.mark.parametrize(
    ("snapshot", "reason"),
    [
        (
            _snapshot(account_assets_success=False),
            LiveOrderCandidateRiskBlockReason.ACCOUNT_ASSETS_UNAVAILABLE,
        ),
        (_snapshot(open_positions_count=1), LiveOrderCandidateRiskBlockReason.OPEN_POSITION_EXISTS),
        (_snapshot(active_orders_count=1), LiveOrderCandidateRiskBlockReason.ACTIVE_ORDER_EXISTS),
        (
            _snapshot(symbol_min_open_order_size=101),
            LiveOrderCandidateRiskBlockReason.MIN_ORDER_SIZE_TOO_LARGE,
        ),
        (_snapshot(symbol_size_step=3), LiveOrderCandidateRiskBlockReason.SIZE_STEP_MISMATCH),
        (_snapshot(spread_jpy=None), LiveOrderCandidateRiskBlockReason.MISSING_SPREAD),
        (
            _snapshot(spread_jpy=LIVE_ORDER_CANDIDATE_MAX_SPREAD_JPY + 0.001),
            LiveOrderCandidateRiskBlockReason.SPREAD_TOO_WIDE,
        ),
        (_snapshot(ticker_age_seconds=None), LiveOrderCandidateRiskBlockReason.MISSING_TICKER_AGE),
        (
            _snapshot(ticker_age_seconds=LIVE_ORDER_CANDIDATE_MAX_TICKER_AGE_SECONDS + 0.1),
            LiveOrderCandidateRiskBlockReason.TICKER_TOO_OLD,
        ),
        (
            _snapshot(market_window_allowed=False),
            LiveOrderCandidateRiskBlockReason.MARKET_WINDOW_NOT_ALLOWED,
        ),
        (_snapshot(maintenance_active=True), LiveOrderCandidateRiskBlockReason.MAINTENANCE_ACTIVE),
        (
            _snapshot(important_event_window_ok=False),
            LiveOrderCandidateRiskBlockReason.IMPORTANT_EVENT_WINDOW_NOT_CONFIRMED,
        ),
        (
            _snapshot(important_event_window_ok=None),
            LiveOrderCandidateRiskBlockReason.IMPORTANT_EVENT_WINDOW_NOT_CONFIRMED,
        ),
        (_snapshot(ledger_unused=False), LiveOrderCandidateRiskBlockReason.LEDGER_ALREADY_USED),
        (
            _snapshot(daily_live_attempt_count=1),
            LiveOrderCandidateRiskBlockReason.DAILY_ATTEMPT_EXISTS,
        ),
        (
            _snapshot(session_live_attempt_count=1),
            LiveOrderCandidateRiskBlockReason.SESSION_ATTEMPT_EXISTS,
        ),
        (_snapshot(result_unknown=True), LiveOrderCandidateRiskBlockReason.RESULT_UNKNOWN_STATE),
        (_snapshot(git_clean=False), LiveOrderCandidateRiskBlockReason.GIT_NOT_CLEAN),
        (_snapshot(tests_passed=False), LiveOrderCandidateRiskBlockReason.TESTS_NOT_PASSED),
        (_snapshot(ruff_passed=False), LiveOrderCandidateRiskBlockReason.RUFF_NOT_PASSED),
        (
            _snapshot(secret_scan_passed=False),
            LiveOrderCandidateRiskBlockReason.SECRET_SCAN_NOT_PASSED,
        ),
        (_snapshot(raw_response_saved=True), LiveOrderCandidateRiskBlockReason.RAW_RESPONSE_SAVED),
        (
            _snapshot(raw_response_displayed=True),
            LiveOrderCandidateRiskBlockReason.RAW_RESPONSE_DISPLAYED,
        ),
    ],
)
def test_unsafe_risk_snapshot_inputs_block(
    snapshot: LiveOrderCandidateRiskSnapshot,
    reason: LiveOrderCandidateRiskBlockReason,
) -> None:
    _assert_blocked(_decision(snapshot=snapshot), reason)


@pytest.mark.parametrize(
    "snapshot",
    [
        _snapshot(symbol_min_open_order_size=None),
        _snapshot(symbol_size_step=None),
    ],
)
def test_missing_symbol_rules_block(snapshot: LiveOrderCandidateRiskSnapshot) -> None:
    _assert_blocked(
        _decision(snapshot=snapshot),
        LiveOrderCandidateRiskBlockReason.MISSING_SYMBOL_RULES,
    )


@pytest.mark.parametrize(
    "snapshot",
    [
        _snapshot(snapshot_id=None),
        _snapshot(open_positions_count=None),
        _snapshot(active_orders_count=None),
        _snapshot(maintenance_active=None),
        _snapshot(result_unknown=None),
        _snapshot(raw_response_saved=None),
        _snapshot(raw_response_displayed=None),
    ],
)
def test_missing_required_risk_input_blocks(
    snapshot: LiveOrderCandidateRiskSnapshot,
) -> None:
    _assert_blocked(
        _decision(snapshot=snapshot),
        LiveOrderCandidateRiskBlockReason.MISSING_REQUIRED_RISK_INPUT,
    )


@pytest.mark.parametrize(
    "snapshot",
    [
        _snapshot(created_at=None),
        _snapshot(open_positions_count=-1),
        _snapshot(active_orders_count=True),
        _snapshot(symbol_min_open_order_size=0),
        _snapshot(symbol_size_step=0),
        _snapshot(spread_jpy=float("nan")),
        _snapshot(ticker_age_seconds=-0.1),
    ],
)
def test_invalid_risk_input_blocks(snapshot: LiveOrderCandidateRiskSnapshot) -> None:
    _assert_blocked(
        _decision(snapshot=snapshot),
        LiveOrderCandidateRiskBlockReason.INVALID_RISK_INPUT,
    )


def test_multiple_failures_return_multiple_blocked_reasons() -> None:
    decision = _decision(
        snapshot=_snapshot(
            open_positions_count=1,
            active_orders_count=2,
            spread_jpy=0.02,
            tests_passed=False,
        )
    )

    assert {
        LiveOrderCandidateRiskBlockReason.OPEN_POSITION_EXISTS.value,
        LiveOrderCandidateRiskBlockReason.ACTIVE_ORDER_EXISTS.value,
        LiveOrderCandidateRiskBlockReason.SPREAD_TOO_WIDE.value,
        LiveOrderCandidateRiskBlockReason.TESTS_NOT_PASSED.value,
    }.issubset(set(decision.blocked_reasons))


def test_risk_decision_serialization_and_repr_do_not_include_sensitive_artifacts() -> None:
    decision = _decision()
    serialized = asdict(decision)
    rendered = repr(decision)
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
def test_risk_snapshot_does_not_accept_sensitive_or_transport_fields(
    forbidden_field: str,
) -> None:
    kwargs = asdict(_snapshot())
    kwargs[forbidden_field] = "blocked"

    with pytest.raises(TypeError):
        LiveOrderCandidateRiskSnapshot(**kwargs)


def test_risk_gate_module_does_not_depend_on_http_private_api_broker_or_live_runner() -> None:
    import app.live_verification.live_order_candidate_risk_gate as module

    module_names = set(module.__dict__)

    assert "post_live_order_with_httpx" not in module_names
    assert "execute_one_shot_live_order" not in module_names
    assert "prepare_one_shot_live_order" not in module_names
    assert "load_live_order_attempt_ledger" not in module_names
