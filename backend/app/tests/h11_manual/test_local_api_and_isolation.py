"""Local UI/API behavior and public/live isolation regression tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.h11_manual.api import get_manual_signal_service
from app.h11_manual.service import ManualSignalService
from app.main_h11_manual import app as manual_app
from app.main_readonly import app as public_app


def test_local_ui_uses_four_switchable_signals_with_probability_charts(tmp_path) -> None:
    service = ManualSignalService(tmp_path, supplemental_h1_paths=())
    manual_app.dependency_overrides[get_manual_signal_service] = lambda: service
    try:
        client = TestClient(manual_app)
        page = client.get("/")
        assert page.status_code == 200
        assert "シグナル" in page.text
        assert "今の判断" not in page.text
        script = client.get("/static/app.js")
        assert script.status_code == 200
        assert '["10m", "30m", "24h", "realtime"]' in script.text
        assert "data-signal-key" in script.text
        assert "signalSparkline" in script.text
        assert "毎秒ローリング" in script.text
        assert "MARKET_RENDER_INTERVAL_MS = 1000" in script.text
        assert "SIGNAL_SETTLE_DELAY_MS = 3000" in script.text
        assert 'request("/api/manual/realtime-estimate"' in script.text
        assert "非正式・検証前" in script.text
        assert "renderValidationDiagnostics" in script.text
        assert "openExitPlan" in script.text
        assert "quickExitContext" in script.text
        assert 'request("/api/manual/exit-plan/quick-start"' in script.text
        assert "取引した＋出口開始" in script.text
        assert "固定SL 15 / TP 22.5 pips" in script.text
        assert "decisionInFlight" in script.text
        assert "wss://forex-api.coin.z.com/ws/public/v1" in script.text
        assert "data-chart-timeframe" in page.text
        assert "出口管理" in page.text
        assert "出口シグナル" in page.text
        assert "exit-signal-strip" in page.text
        assert "確率帯別の実現上昇率" in page.text
        assert "毎秒ローリング検証" in page.text
        assert "非正式・別台帳" in page.text
        assert "renderRealtimeValidationDiagnostics" in script.text

        current = client.get("/api/manual/current")
        assert current.status_code == 200
        assert len(current.json()["signals"]) == 3
        chart = client.get("/api/manual/chart?timeframe=1m")
        assert chart.status_code == 200
        assert chart.json()["source"] == "GMO_PUBLIC_LOCAL_CACHE"
        realtime = client.post(
            "/api/manual/realtime-estimate",
            json={"bid": 160.0, "ask": 160.005, "market_time_utc": "2000-01-01T00:00:00Z"},
        )
        assert realtime.status_code == 422
        realtime_current = client.post(
            "/api/manual/realtime-estimate",
            json={"bid": 160.0, "ask": 160.005, "market_time_utc": datetime.now(UTC).isoformat()},
        )
        assert realtime_current.status_code == 200
        assert realtime_current.json()["status"] == "REALTIME_ESTIMATE_NOT_FORMAL"
        assert all(item["formal_signal"] is False for item in realtime_current.json()["estimates"])
        series = client.get("/api/manual/signal-series")
        assert series.status_code == 200
        assert set(series.json()["series"]) == {"10m", "30m", "24h"}
        assert series.json()["realtime_series_persistence"] is False
        assert series.json()["realtime_validation_forecasts_persisted_separately"] is True
        exit_status = client.get("/api/manual/exit-plan")
        assert exit_status.status_code == 200
        assert exit_status.json()["automatic_exit"] is False
        assert exit_status.json()["exit_signal"]["code"] == "NO_MANUAL_POSITION"
        assert exit_status.json()["exit_signal"]["label"] == "建玉なし"
        quick_start = client.post(
            "/api/manual/exit-plan/quick-start",
            json={
                "forecast_id": "missing_forecast",
                "horizon": "10m",
                "direction": "買い",
            },
        )
        assert quick_start.status_code == 422
        validation = client.get("/api/manual/validation")
        assert validation.status_code == 200
        assert validation.json()["metrics"]["threshold_auto_change_allowed"] is False
        assert validation.json()["realtime_rolling"]["formal_signal"] is False
        assert validation.json()["realtime_rolling"]["promotion_eligible"] is False
        assert validation.json()["realtime_rolling"]["target_price_max_delay_seconds"] == 15
        decision = client.post(
            "/api/manual/decisions",
            json={"horizon": "10m", "decision": "見送った", "forecast_id": None},
        )
        assert decision.status_code == 200
        assert decision.json()["recorded"] is True
    finally:
        manual_app.dependency_overrides.pop(get_manual_signal_service, None)


def test_non_local_host_is_rejected() -> None:
    response = TestClient(manual_app, base_url="http://example.test").get("/health")
    assert response.status_code == 403


def test_public_entrypoint_does_not_expose_manual_ui() -> None:
    client = TestClient(public_app)
    assert client.get("/api/manual/current").status_code == 404
    assert client.get("/api/manual/chart").status_code == 404
    assert client.post("/api/manual/realtime-estimate").status_code == 404
    assert client.get("/api/manual/signal-series").status_code == 404
    assert client.get("/api/manual/exit-plan").status_code == 404
    assert client.post("/api/manual/exit-plan").status_code == 404
    assert client.post("/api/manual/exit-plan/quick-start").status_code == 404
    assert client.post("/api/manual/exit-plan/close").status_code == 404
    assert client.post("/api/manual/decisions").status_code == 404


def test_manual_package_has_no_forbidden_execution_imports() -> None:
    root = Path(__file__).resolve().parents[2] / "h11_manual"
    source = "\n".join(path.read_text() for path in root.rglob("*.py"))
    forbidden_imports = (
        "app.brokers",
        "app.live_verification",
        "h11_v3_actual_transport",
        "live_order_once",
        "real_broker_post_hard_guard",
    )
    assert not any(token in source for token in forbidden_imports)
