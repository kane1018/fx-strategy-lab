from __future__ import annotations

from app.services.automation_service import (
    _build_automation_no_post_gmo_service_summary,
    run_automation_cycle,
)
from app.services.bot_service import (
    start_bot,
)
from app.services.gmo_live_runner_boundary import (
    GmoLiveRunnerBoundaryResult,
    GmoLiveServiceBoundarySummary,
    build_gmo_live_service_no_post_hook_summary,
)


def _blocked_summary() -> GmoLiveServiceBoundarySummary:
    return GmoLiveServiceBoundarySummary(
        runner_summary=GmoLiveRunnerBoundaryResult(
            runner_may_start_gmo_live_entry=False,
            runner_may_start_gmo_live_settlement=False,
            process_start_default_off_enforced=True,
            blocked_reasons=("PROCESS_START_DEFAULT_OFF",),
            settlement_blocked_reasons=("PROCESS_START_DEFAULT_OFF",),
        ),
        service_hook_wired=True,
        service_hook_wired_into_bot_service=True,
    )


def test_bot_service_live_mode_calls_no_post_service_hook(monkeypatch, db) -> None:
    calls = {"count": 0}

    def fake_hook() -> GmoLiveServiceBoundarySummary:
        calls["count"] += 1
        return _blocked_summary()

    monkeypatch.setattr(
        "app.services.bot_service._build_bot_service_live_no_post_hook_summary",
        fake_hook,
    )
    result = start_bot(db, "live")

    assert calls["count"] == 1
    assert result["status"] == "risk_stopped"
    assert "GMO live no-POST hook blocked" in result["stop_reason"]


def test_automation_cycle_evaluates_no_post_service_hook_even_when_stopped(monkeypatch, db) -> None:
    calls = {"count": 0}

    def fake_hook() -> GmoLiveServiceBoundarySummary:
        calls["count"] += 1
        return _blocked_summary()

    monkeypatch.setattr(
        "app.services.automation_service._build_automation_no_post_gmo_service_summary",
        fake_hook,
    )
    result = run_automation_cycle(db, broker=None)

    assert calls["count"] == 1
    assert result["enabled"] is False


def test_bot_service_no_post_hook_summary_indicates_bot_service_entry() -> None:
    summary = build_gmo_live_service_no_post_hook_summary(invoked_from_bot_service=True)
    assert summary.service_hook_wired is True
    assert summary.service_hook_wired_into_bot_service is True


def test_automation_no_post_hook_summary_indicates_automation_runner_entry() -> None:
    summary = _build_automation_no_post_gmo_service_summary()
    assert summary.service_hook_wired is True
    assert summary.service_hook_wired_into_automation_runner is True
    assert summary.readiness_shadow_blocked_reasons
