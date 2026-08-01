from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.services import h11_v4_unattended_live_orchestration as orchestration_module
from app.services.h11_v4_g064_unattended_activation import G064_GENERATION_LABEL
from scripts import h11_auto_v4_unattended_live_bounded_run as runner


def _g064_session() -> SimpleNamespace:
    return SimpleNamespace(
        generation=SimpleNamespace(label=G064_GENERATION_LABEL),
    )


def _run_cycle(
    monkeypatch, blocked: tuple[str, ...], *, arm_intent: bool = True
):
    def _unexpected_legacy_path(**_kwargs):
        raise AssertionError("legacy authorization path must not run for G064")

    monkeypatch.setattr(
        orchestration_module,
        "run_unattended_live_entry_cycle_once",
        _unexpected_legacy_path,
    )
    return runner._run_one_cycle(
        session=_g064_session(),
        risk_store=None,
        risk_policy=None,
        dead_man_store=None,
        heartbeat_chain_store=None,
        notification_primary=None,
        notification_secondary=None,
        entry_gate_blocked_reasons=blocked,
        credential_pair=None,
        client=None,
        now_utc=datetime.now(UTC),
        arm_intent=arm_intent,
    )


def test_g064_switch_only_cycle_does_not_require_daily_authorization(monkeypatch):
    outcome = _run_cycle(monkeypatch, ())

    assert outcome.entry_attempted is False
    assert outcome.safe_dict == {
        "status": "G064_UNATTENDED_SWITCH_ONLY_ENTRY_GATE_EVALUATED_NO_POST",
        "runtime_mode": "SWITCH_ONLY",
        "entry_gate_open": True,
        "entry_state": "WAITING",
        "authorization_required": False,
        "confirmation_required": False,
        "notification_attempted": False,
        "credential_read": False,
        "private_api_read": False,
        "broker_write": False,
        "broker_post_count": 0,
    }


def test_g064_switch_only_cycle_preserves_blocked_entry_gate(monkeypatch):
    outcome = _run_cycle(monkeypatch, ("ENTRY_GATE_QUOTE_UNAVAILABLE",))

    assert outcome.entry_attempted is False
    assert outcome.safe_dict["status"] == (
        "G064_UNATTENDED_SWITCH_ONLY_ENTRY_GATE_BLOCKED_NO_POST"
    )
    assert outcome.safe_dict["entry_gate_open"] is False
    assert outcome.safe_dict["entry_state"] == "BLOCKED"
    assert outcome.safe_dict["broker_post_count"] == 0


def test_g064_switch_only_cycle_keeps_entry_closed_when_arm_is_off(monkeypatch):
    outcome = _run_cycle(monkeypatch, (), arm_intent=False)

    assert outcome.entry_attempted is False
    assert outcome.safe_dict["entry_gate_open"] is False
    assert outcome.safe_dict["entry_state"] == "BLOCKED"
