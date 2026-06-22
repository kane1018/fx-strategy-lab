"""Offline tests for the Phase 2E-1 local-only shadow safety layer."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta

import pytest

from app.shadow.audit import AuditLogWriteError, write_audit_event
from app.shadow.risk import (
    SCHEMA_VERSION,
    KillSwitchReason,
    KillSwitchState,
    OrderCandidate,
    RejectReason,
    RiskContext,
    RiskPolicy,
    RiskStatus,
    SignalLabel,
    SpreadProvenance,
    can_process_virtual_result,
    create_order_candidate,
    evaluate,
    signal_label_from_side,
)

NOW = datetime(2026, 6, 22, 3, 0, tzinfo=UTC)
MARKET_TIME = NOW - timedelta(seconds=30)


def _candidate(**overrides):
    values = {
        "signal_label": SignalLabel.BUY,
        "run_id": "r-safe",
        "step_index": 0,
        "timestamp": NOW,
        "market_data_timestamp": MARKET_TIME,
        "source": "mock",
        "symbol": "USD_JPY",
        "interval": "M1",
        "quantity": 100,
        "bid": 154.100,
        "ask": 154.104,
        "spread_provenance": SpreadProvenance.REAL_PUBLIC_BID_ASK,
        "signal_name": "offline_test",
        "signal_reason": "fixture",
        "confidence": 0.8,
    }
    values.update(overrides)
    candidate = create_order_candidate(**values)
    assert candidate is not None
    return candidate


def _context(**overrides) -> RiskContext:
    values = {
        "evaluation_time": NOW,
        "spread_provenance": SpreadProvenance.REAL_PUBLIC_BID_ASK,
    }
    values.update(overrides)
    return RiskContext(**values)


def _malformed_candidate(**overrides):
    original = _candidate()
    clone = object.__new__(OrderCandidate)
    for item in fields(OrderCandidate):
        object.__setattr__(clone, item.name, getattr(original, item.name))
    for key, value in overrides.items():
        object.__setattr__(clone, key, value)
    return clone


def test_signal_boundary_and_candidate_factory() -> None:
    assert signal_label_from_side("flat") is SignalLabel.HOLD
    assert create_order_candidate(
        signal_label=SignalLabel.HOLD,
        run_id="r-safe",
        step_index=0,
        timestamp=NOW,
        market_data_timestamp=MARKET_TIME,
        source="mock",
        symbol="USD_JPY",
        interval="M1",
        quantity=1,
        bid=154.1,
        ask=154.104,
        spread_provenance=SpreadProvenance.REAL_PUBLIC_BID_ASK,
        signal_name="hold",
        signal_reason="fixture",
        confidence=0.5,
    ) is None

    buy = _candidate()
    sell = _candidate(signal_label=SignalLabel.SELL)
    assert buy.entry_reference_price == pytest.approx(154.104)
    assert sell.entry_reference_price == pytest.approx(154.100)
    assert buy.schema_version == SCHEMA_VERSION
    assert buy.real_order is False
    assert buy.private_api_used is False
    assert buy.api_key_used is False
    assert buy.no_order_execution is True
    assert buy.live_trading_environment_enabled is False
    assert buy.gmo_order_enabled is False
    with pytest.raises(FrozenInstanceError):
        buy.quantity = 1  # type: ignore[misc]
    with pytest.raises(ValueError, match="safety flags"):
        replace(buy, real_order=True)


def test_candidate_id_is_deterministic_and_correlates_decision() -> None:
    first = _candidate()
    second = _candidate()
    assert first.candidate_id == second.candidate_id
    assert first.candidate_id.startswith("cand_r-safe_0_buy_")
    decision = evaluate(first, _context())
    assert decision.candidate_id == first.candidate_id
    assert decision.decision_id.startswith(f"risk_{first.candidate_id}_")


def test_normal_candidate_allows_only_virtual_processing() -> None:
    decision = evaluate(_candidate(), _context())
    assert decision.status is RiskStatus.ALLOW_SHADOW
    assert decision.reasons == ()
    assert decision.real_order is False
    assert decision.private_api_used is False
    assert decision.api_key_used is False
    assert decision.no_order_execution is True
    assert decision.live_trading_environment_enabled is False
    assert decision.gmo_order_enabled is False
    assert can_process_virtual_result(KillSwitchState(), decision) is True


@pytest.mark.parametrize(
    ("candidate_changes", "context_changes", "expected"),
    [
        ({"symbol": "EUR_JPY"}, {}, RejectReason.UNSUPPORTED_SYMBOL),
        ({"interval": "M5"}, {}, RejectReason.UNSUPPORTED_INTERVAL),
        ({"quantity": 101}, {}, RejectReason.QUANTITY_OVER_LIMIT),
        ({"spread_pips": 0.51}, {}, RejectReason.SPREAD_TOO_WIDE),
        (
            {"spread_provenance": SpreadProvenance.SYNTHETIC_ZERO},
            {},
            RejectReason.SYNTHETIC_SPREAD_NOT_ALLOWED,
        ),
        (
            {},
            {"spread_provenance": SpreadProvenance.CANDLE_DERIVED},
            RejectReason.SYNTHETIC_SPREAD_NOT_ALLOWED,
        ),
        ({}, {"market_closed": True}, RejectReason.MARKET_CLOSED),
        ({}, {"candidates_in_run": 10}, RejectReason.MAX_CANDIDATES_PER_RUN_EXCEEDED),
        ({}, {"candidates_today": 30}, RejectReason.MAX_DAILY_CANDIDATES_EXCEEDED),
    ],
)
def test_risk_reject_boundaries(candidate_changes, context_changes, expected) -> None:
    decision = evaluate(replace(_candidate(), **candidate_changes), _context(**context_changes))
    assert decision.status is RiskStatus.REJECT_SHADOW
    assert expected in decision.reasons
    assert decision.reasons


def test_freshness_future_skew_duplicate_and_cooldown() -> None:
    stale = replace(
        _candidate(),
        market_data_timestamp=(NOW - timedelta(seconds=181)).isoformat(),
    )
    assert RejectReason.STALE_DATA in evaluate(stale, _context()).reasons

    future = replace(
        _candidate(),
        market_data_timestamp=(NOW + timedelta(seconds=6)).isoformat(),
    )
    assert RejectReason.INVALID_DATA in evaluate(future, _context()).reasons

    candidate = _candidate()
    duplicate_context = _context(existing_candidate_ids=frozenset({candidate.candidate_id}))
    assert RejectReason.DUPLICATE_CANDIDATE in evaluate(candidate, duplicate_context).reasons

    cooldown_context = _context(
        last_candidate_timestamp=(MARKET_TIME - timedelta(seconds=59)).isoformat()
    )
    assert RejectReason.COOLDOWN_ACTIVE in evaluate(candidate, cooldown_context).reasons


def test_spread_provenance_is_required_and_fail_closed() -> None:
    candidate = _candidate()
    missing_context = RiskContext(evaluation_time=NOW)
    missing_decision = evaluate(candidate, missing_context)
    assert missing_decision.status is RiskStatus.REJECT_SHADOW
    assert RejectReason.INVALID_DATA in missing_decision.reasons

    for provenance in (
        SpreadProvenance.UNKNOWN,
        SpreadProvenance.SYNTHETIC_ZERO,
        SpreadProvenance.CANDLE_DERIVED,
    ):
        decision = evaluate(
            replace(candidate, spread_provenance=provenance),
            _context(spread_provenance=provenance),
        )
        assert decision.status is RiskStatus.REJECT_SHADOW
        assert decision.reasons

    zero_spread = _candidate(bid=154.1, ask=154.1)
    assert zero_spread.spread_pips == 0
    zero_missing = evaluate(zero_spread, RiskContext(evaluation_time=NOW))
    assert zero_missing.status is RiskStatus.REJECT_SHADOW
    assert RejectReason.INVALID_DATA in zero_missing.reasons

    zero_synthetic = evaluate(
        replace(zero_spread, spread_provenance=SpreadProvenance.SYNTHETIC_ZERO),
        _context(spread_provenance=SpreadProvenance.SYNTHETIC_ZERO),
    )
    assert RejectReason.SYNTHETIC_SPREAD_NOT_ALLOWED in zero_synthetic.reasons

    real_decision = evaluate(candidate, _context())
    assert real_decision.status is RiskStatus.ALLOW_SHADOW


def test_malformed_spread_provenance_rejects_or_constructor_fails() -> None:
    with pytest.raises(ValueError, match="spread_provenance"):
        replace(_candidate(), spread_provenance="REAL_PUBLIC_BID_ASK")
    with pytest.raises(ValueError, match="spread_provenance"):
        RiskContext(evaluation_time=NOW, spread_provenance="UNKNOWN")

    malformed = _malformed_candidate(spread_provenance="REAL_PUBLIC_BID_ASK")
    decision = evaluate(malformed, _context())
    assert decision.status is RiskStatus.REJECT_SHADOW
    assert RejectReason.UNKNOWN_STATE in decision.reasons


def test_missing_safety_and_unknown_states_fail_closed() -> None:
    missing = replace(_candidate(), source="")
    missing_decision = evaluate(missing, _context())
    assert RejectReason.MISSING_REQUIRED_FIELDS in missing_decision.reasons

    with pytest.raises(ValueError, match="invalid RiskPolicy"):
        RiskPolicy(allow_real_order=True)
    malformed_policy = object.__new__(RiskPolicy)
    object.__setattr__(malformed_policy, "policy_id", object())
    malformed_decision = evaluate(_candidate(), _context(), malformed_policy)
    assert malformed_decision.status is RiskStatus.REJECT_SHADOW
    assert RejectReason.UNKNOWN_STATE in malformed_decision.reasons

    unknown_decision = evaluate({"unexpected": True}, _context())
    assert unknown_decision.status is RiskStatus.REJECT_SHADOW
    assert RejectReason.UNKNOWN_STATE in unknown_decision.reasons
    assert unknown_decision.reasons


@pytest.mark.parametrize(
    "policy_changes",
    [
        {"policy_id": object()},
        {"allowed_symbols": "USD_JPY"},
        {"max_candidates_per_run": -1},
        {"max_daily_candidates": -1},
        {"max_quantity": 0},
        {"max_spread_pips": float("nan")},
        {"max_spread_pips": float("inf")},
        {"allow_private_api": True},
        {"allow_api_key": True},
        {"allow_broker_call": True},
        {"allow_synthetic_zero_spread": True},
    ],
)
def test_risk_policy_constructor_rejects_invalid_invariants(policy_changes) -> None:
    with pytest.raises(ValueError, match="invalid RiskPolicy"):
        RiskPolicy(**policy_changes)


@pytest.mark.parametrize(
    "candidate",
    [
        {"unexpected": True},
        None,
        _malformed_candidate(candidate_id=object()),
        _malformed_candidate(side="BUY"),
        _malformed_candidate(source=None),
    ],
)
def test_malformed_candidate_rejects_without_escaping(candidate) -> None:
    decision = evaluate(candidate, _context())
    assert decision.status is RiskStatus.REJECT_SHADOW
    assert decision.reasons


def test_malformed_context_rejects_without_escaping() -> None:
    decision = evaluate(_candidate(), object())
    assert decision.status is RiskStatus.REJECT_SHADOW
    assert RejectReason.UNKNOWN_STATE in decision.reasons

    malformed_context = object.__new__(RiskContext)
    decision = evaluate(_candidate(), malformed_context)
    assert decision.status is RiskStatus.REJECT_SHADOW
    assert RejectReason.UNKNOWN_STATE in decision.reasons


def test_kill_switch_is_sticky_and_gates_all_processing() -> None:
    inactive = KillSwitchState()
    active = inactive.activate(
        KillSwitchReason.MANUAL_STOP_FILE_EXISTS,
        timestamp=NOW,
        safety_snapshot={"real_order": False},
    )
    assert active.active is True
    assert active.reasons == (KillSwitchReason.MANUAL_STOP_FILE_EXISTS,)
    assert active.activate(KillSwitchReason.UNKNOWN_STATE, timestamp=NOW) is active
    assert create_order_candidate(
        signal_label=SignalLabel.BUY,
        run_id="r-stopped",
        step_index=0,
        timestamp=NOW,
        market_data_timestamp=MARKET_TIME,
        source="mock",
        symbol="USD_JPY",
        interval="M1",
        quantity=1,
        bid=154.1,
        ask=154.104,
        spread_provenance=SpreadProvenance.REAL_PUBLIC_BID_ASK,
        signal_name="stopped",
        signal_reason="fixture",
        confidence=0.5,
        kill_switch=active,
    ) is None
    decision = evaluate(_candidate(), _context(kill_switch=active))
    assert decision.status is RiskStatus.REJECT_SHADOW
    assert RejectReason.KILL_SWITCH_ACTIVE in decision.reasons
    assert can_process_virtual_result(active, decision) is False


def test_repeated_api_errors_activate_without_auto_recovery() -> None:
    state = KillSwitchState()
    policy = RiskPolicy()
    state = state.record_api_result(success=False, timestamp=NOW, policy=policy)
    state = state.record_api_result(success=False, timestamp=NOW, policy=policy)
    assert state.active is False and state.consecutive_api_errors == 2
    state = state.record_api_result(success=False, timestamp=NOW, policy=policy)
    assert state.active is True
    assert state.reasons == (KillSwitchReason.REPEATED_API_ERRORS,)
    assert state.record_api_result(success=True, timestamp=NOW, policy=policy) is state


def test_jsonl_audit_writer_adds_contract_fields(tmp_path) -> None:
    candidate = _candidate()
    path = write_audit_event(
        tmp_path,
        run_id="r-safe",
        event_type="candidate_log",
        payload=candidate,
    )
    row = json.loads(path.read_text())
    assert row["schema_version"] == SCHEMA_VERSION
    assert row["event_type"] == "candidate_log"
    assert row["real_order"] is False
    assert row["no_order_execution"] is True
    assert "secret" not in row
    assert "api_key" not in row


def test_jsonl_audit_writer_fails_closed(tmp_path) -> None:
    with pytest.raises(AuditLogWriteError, match="typed dataclass"):
        write_audit_event(
            tmp_path,
            run_id="r-safe",
            event_type="candidate_log",
            payload={"run_id": "r-safe", "timestamp": NOW.isoformat(), "secret": "value"},
        )

    not_a_directory = tmp_path / "blocked"
    not_a_directory.write_text("file")
    with pytest.raises(AuditLogWriteError, match="write failed"):
        write_audit_event(
            not_a_directory,
            run_id="r-safe",
            event_type="candidate_log",
            payload=_candidate(run_id="r-safe"),
        )
