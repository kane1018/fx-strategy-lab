from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from app.live_verification.errors import LiveVerificationIntentError
from app.live_verification.intent import (
    OrderIntent,
    OrderIntentSide,
    build_order_intent_from_allowed_decision,
)

CREATED_AT = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
EXPIRES_AT = CREATED_AT + timedelta(minutes=10)


def _valid_kwargs() -> dict[str, object]:
    return {
        "candidate_id": "cand_run_1_000001_buy_abc123",
        "decision_id": "risk_cand_run_1_000001_buy_abc123_def456",
        "readonly_precheck_id": "precheck_run_1_abc123",
        "verification_run_id": "run_1",
        "symbol": "USD_JPY",
        "side": "BUY",
        "units": 100,
        "risk_decision_status": "ALLOW_SHADOW",
        "readonly_precheck_passed": True,
        "manual_confirmation_required": True,
        "created_at": CREATED_AT,
        "expires_at": EXPIRES_AT,
    }


def _intent(**overrides: object) -> OrderIntent:
    kwargs = _valid_kwargs()
    kwargs.update(overrides)
    return build_order_intent_from_allowed_decision(**kwargs)


def test_builds_order_intent_for_supported_fixed_allow_precheck_passed() -> None:
    intent = _intent()

    assert intent.order_intent_id.startswith("intent_run_1_")
    assert intent.candidate_id == "cand_run_1_000001_buy_abc123"
    assert intent.decision_id == "risk_cand_run_1_000001_buy_abc123_def456"
    assert intent.readonly_precheck_id == "precheck_run_1_abc123"
    assert intent.verification_run_id == "run_1"
    assert intent.symbol == "USD_JPY"
    assert intent.side is OrderIntentSide.BUY
    assert intent.units == 100
    assert intent.mode == "live_verification"
    assert intent.manual_confirmation_required is True
    assert intent.readonly_precheck_passed is True
    assert intent.risk_decision_status == "ALLOW_SHADOW"


def test_order_intent_id_correlates_candidate_decision_precheck_and_run() -> None:
    intent = _intent()
    same = _intent()
    changed_candidate = _intent(candidate_id="cand_run_1_000002_buy_changed")

    assert intent.order_intent_id == same.order_intent_id
    assert intent.order_intent_id != changed_candidate.order_intent_id


def test_allow_status_alias_is_accepted() -> None:
    assert _intent(risk_decision_status="ALLOW").risk_decision_status == "ALLOW"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("symbol", "EUR_USD"),
        ("units", 101),
        ("risk_decision_status", "REJECT_SHADOW"),
        ("readonly_precheck_passed", False),
        ("candidate_id", ""),
        ("decision_id", ""),
        ("readonly_precheck_id", ""),
        ("verification_run_id", ""),
        ("manual_confirmation_required", False),
        ("mode", "shadow"),
        ("side", "HOLD"),
    ],
)
def test_order_intent_rejects_unsafe_or_incomplete_inputs(field: str, value: object) -> None:
    with pytest.raises(LiveVerificationIntentError):
        _intent(**{field: value})


def test_order_intent_rejects_expired_time_window() -> None:
    with pytest.raises(LiveVerificationIntentError):
        _intent(expires_at=CREATED_AT)


def test_order_intent_rejects_duplicate_intent_in_same_verification_run() -> None:
    existing = _intent()

    with pytest.raises(LiveVerificationIntentError):
        _intent(existing_intents=(existing,))


def test_order_intent_does_not_hold_secret_or_raw_transport_fields() -> None:
    fields = set(asdict(_intent()))

    assert "raw_response" not in fields
    assert "headers" not in fields
    assert "signature" not in fields
    assert "api_key" not in fields
    assert "api_secret" not in fields
    assert "order_id" not in fields
    assert "execution_id" not in fields
