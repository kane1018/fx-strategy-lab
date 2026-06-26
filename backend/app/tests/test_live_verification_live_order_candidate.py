from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_ID_PREFIX,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateBlockedReason,
    LiveOrderCandidateSide,
    LiveOrderCandidateSourceType,
    LiveOrderCandidateStatus,
    StrategySignalInput,
    build_live_order_candidate_dry_run,
    make_live_order_candidate_id,
)

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
EXPIRES_AT = CREATED_AT + timedelta(minutes=10)


def _signal(**overrides: object) -> StrategySignalInput:
    kwargs = {
        "source_signal_id": "signal_step5b_001",
        "source_type": LiveOrderCandidateSourceType.STRATEGY_SIGNAL,
        "strategy_name": "rsi_reversal",
        "symbol": "USD_JPY",
        "side": LiveOrderCandidateSide.BUY,
        "confidence": 0.72,
        "rationale": "dry-run strategy signal only",
        "market_snapshot_ref": "snapshot_ref_001",
        "paper_trade_ref": "paper_ref_001",
        "shadow_run_ref": "shadow_run_ref_001",
        "created_at": CREATED_AT,
        "expires_at": EXPIRES_AT,
    }
    kwargs.update(overrides)
    return StrategySignalInput(**kwargs)


def _result(**overrides: object):
    return build_live_order_candidate_dry_run(_signal(**overrides))


def test_buy_signal_builds_usd_jpy_100_market_dry_run_candidate() -> None:
    result = _result(side="buy")

    candidate = result.candidate
    assert candidate is not None
    assert result.status is LiveOrderCandidateStatus.REVIEW_REQUIRED
    assert candidate.candidate_id.startswith(LIVE_ORDER_CANDIDATE_ID_PREFIX)
    assert candidate.source_signal_id == "signal_step5b_001"
    assert candidate.source_type is LiveOrderCandidateSourceType.STRATEGY_SIGNAL
    assert candidate.strategy_name == "rsi_reversal"
    assert candidate.symbol == "USD_JPY"
    assert candidate.side is LiveOrderCandidateSide.BUY
    assert candidate.size == LIVE_ORDER_CANDIDATE_SIZE == 100
    assert candidate.execution_type == LIVE_ORDER_CANDIDATE_EXECUTION_TYPE == "MARKET"
    assert candidate.confidence == 0.72
    assert candidate.rationale == "dry-run strategy signal only"
    assert candidate.market_snapshot_ref == "snapshot_ref_001"
    assert candidate.paper_trade_ref == "paper_ref_001"
    assert candidate.shadow_run_ref == "shadow_run_ref_001"


def test_sell_signal_builds_usd_jpy_100_market_dry_run_candidate() -> None:
    result = _result(side="SELL")

    candidate = result.candidate
    assert candidate is not None
    assert candidate.side is LiveOrderCandidateSide.SELL
    assert candidate.symbol == "USD_JPY"
    assert candidate.size == 100
    assert candidate.execution_type == "MARKET"
    assert candidate.allowed_for_live is False


@pytest.mark.parametrize("side", ["NO_TRADE", "hold", LiveOrderCandidateSide.NO_TRADE])
def test_no_trade_signal_blocks_without_candidate(side: str | LiveOrderCandidateSide) -> None:
    result = _result(side=side)

    assert result.candidate is None
    assert result.candidate_id is None
    assert result.status is LiveOrderCandidateStatus.BLOCKED
    assert result.blocked_reason == LiveOrderCandidateBlockedReason.NO_TRADE_SIGNAL.value
    assert result.allowed_for_live is False


def test_unsupported_symbol_blocks_without_candidate() -> None:
    result = _result(symbol="EUR_USD")

    assert result.candidate is None
    assert result.status is LiveOrderCandidateStatus.BLOCKED
    assert result.blocked_reason == LiveOrderCandidateBlockedReason.UNSUPPORTED_SYMBOL.value
    assert result.allowed_for_live is False


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("nan"), "0.5", True])
def test_invalid_confidence_blocks_without_candidate(confidence: object) -> None:
    result = _result(confidence=confidence)

    assert result.candidate is None
    assert result.status is LiveOrderCandidateStatus.BLOCKED
    assert result.blocked_reason == LiveOrderCandidateBlockedReason.INVALID_CONFIDENCE.value
    assert result.allowed_for_live is False


@pytest.mark.parametrize("rationale", ["", "   "])
def test_missing_rationale_blocks_without_candidate(rationale: str) -> None:
    result = _result(rationale=rationale)

    assert result.candidate is None
    assert result.status is LiveOrderCandidateStatus.BLOCKED
    assert result.blocked_reason == LiveOrderCandidateBlockedReason.MISSING_RATIONALE.value
    assert result.allowed_for_live is False


def test_missing_source_signal_id_blocks_without_candidate() -> None:
    result = _result(source_signal_id="")

    assert result.candidate is None
    assert result.status is LiveOrderCandidateStatus.BLOCKED
    assert (
        result.blocked_reason
        == LiveOrderCandidateBlockedReason.MISSING_SOURCE_SIGNAL_ID.value
    )
    assert result.source_signal_id == "missing_source_signal_id"
    assert result.allowed_for_live is False


def test_review_candidate_safety_defaults_are_fixed() -> None:
    result = _result()
    candidate = result.candidate
    assert candidate is not None

    for target in (result, candidate):
        assert target.allowed_for_live is False
        assert target.requires_human_approval is True
        assert target.risk_gate_required is True
        assert target.approval_gate_required is True
        assert target.dry_run_only is True


def test_blocked_result_safety_defaults_are_fixed() -> None:
    result = _result(side="NO_TRADE")

    assert result.allowed_for_live is False
    assert result.requires_human_approval is True
    assert result.risk_gate_required is True
    assert result.approval_gate_required is True
    assert result.dry_run_only is True


def test_candidate_id_is_deterministic_and_not_order_execution_or_position_id() -> None:
    first = _result().candidate
    second = _result().candidate
    assert first is not None
    assert second is not None

    expected_id = make_live_order_candidate_id(
        source_signal_id=first.source_signal_id,
        source_type=first.source_type,
        strategy_name=first.strategy_name,
        symbol=first.symbol,
        side=first.side,
        confidence=first.confidence,
        created_at=first.created_at,
        expires_at=first.expires_at,
    )
    blocked_prefixes = ("order_", "execution_", "position_", "client_", "ORDER", "EXEC", "POS")

    assert first.candidate_id == second.candidate_id == expected_id
    assert first.candidate_id.startswith("LOCAND-")
    assert not first.candidate_id.startswith(blocked_prefixes)


def test_candidate_serialization_and_repr_do_not_include_sensitive_artifacts() -> None:
    candidate = _result().candidate
    assert candidate is not None

    serialized = asdict(candidate)
    rendered = repr(candidate)
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
    ],
)
def test_strategy_signal_input_does_not_accept_sensitive_or_transport_fields(
    forbidden_field: str,
) -> None:
    kwargs = asdict(_signal())
    kwargs[forbidden_field] = "blocked"

    with pytest.raises(TypeError):
        StrategySignalInput(**kwargs)


def test_candidate_module_does_not_depend_on_live_runner_private_api_or_broker() -> None:
    import app.live_verification.live_order_candidate as module

    module_names = set(module.__dict__)

    assert "execute_one_shot_live_order" not in module_names
    assert "post_live_order_with_httpx" not in module_names
    assert "load_live_order_attempt_ledger" not in module_names
    assert "prepare_one_shot_live_order" not in module_names
    assert "build_step4_approval_gate" not in module_names
