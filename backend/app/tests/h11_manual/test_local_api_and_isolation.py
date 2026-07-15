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
        styles = client.get("/static/styles.css")
        assert script.status_code == 200
        assert styles.status_code == 200
        assert '["10m", "30m", "24h", "realtime"]' in script.text
        assert "data-signal-key" in script.text
        assert "signalSparkline" in script.text
        assert "毎秒ローリング" in script.text
        assert 'realtimeHorizon: "10m"' in script.text
        assert 'data-realtime-horizon="10m"' in script.text
        assert 'data-realtime-horizon="30m"' in script.text
        assert 'realtimeByHorizon(state.realtimeHorizon)' in script.text
        assert '["10m", "30m"].forEach' in script.text
        assert "MARKET_RENDER_INTERVAL_MS = 1000" in script.text
        assert "SIGNAL_SETTLE_DELAY_MS = 3000" in script.text
        assert "FORMAL_REFRESH_RECHECK_MS = 10000" in script.text
        assert "FORMAL_REFRESH_MAX_RECHECKS = 3" in script.text
        assert "formalSignalsIncludeLatestCompletedM1" in script.text
        assert 'request("/api/manual/realtime-estimate"' in script.text
        assert "非正式・検証前" in script.text
        assert "renderValidationDiagnostics" in script.text
        assert "renderActionBreakdown" in script.text
        assert "openExitPlan" not in script.text
        assert "quickExitContext" not in script.text
        assert 'request("/api/manual/exit-plan/quick-start"' not in script.text
        assert "data-trade-start" not in script.text
        assert "実建玉の出口シグナル" in script.text
        assert "actualPositions" in script.text
        assert "brokerSnapshotRevision" in script.text
        assert "allowBrokerSnapshot" in script.text
        assert "requestedBrokerSnapshotRevision === state.brokerSnapshotRevision" in script.text
        assert '"買い": "Buy"' in script.text
        assert '"売り": "Sell"' in script.text
        assert '"見送り": "Stay"' in script.text
        assert "24時間モデルは相場方向の参考表示です" in script.text
        assert "毎秒推定は非正式の研究表示です" in script.text
        assert "別時間軸を管理中" not in script.text
        assert 'await switchTab("exit")' not in script.text
        assert "tradeStartInFlight" not in script.text
        assert "TRADE_STARTED" not in script.text
        assert 'request("/api/manual/decisions"' not in script.text
        assert "quick-exit-close-button" not in page.text
        assert "trade-and-exit-button" not in page.text
        assert "quickSettlementAction" not in script.text
        assert "損切りで決済記録" not in script.text
        assert "現在価格で決済記録" not in script.text
        assert "data-card-fill-input" not in script.text
        assert "data-card-settle" not in script.text
        assert "correctActualFill" not in script.text
        assert 'request("/api/manual/exit-plan/actual-fill"' not in script.text
        assert 'request("/api/manual/broker-sync"' in script.text
        assert 'request("/api/manual/positions?limit=100"' in script.text
        assert "ポジション履歴" in page.text
        assert 'id="position-table"' in page.text
        assert "Broker IDは表示しません" in page.text
        assert "wss://forex-api.coin.z.com/ws/public/v1" in script.text
        assert "data-chart-timeframe" in page.text
        assert "出口シグナル" in script.text
        assert 'data-tab="exit"' not in page.text
        assert 'id="exit"' not in page.text
        assert "exit-signal-strip" not in page.text
        assert "管理中" not in page.text
        assert "建玉数" in page.text
        assert "建玉同期 確認中" in page.text
        assert 'id="broker-position-count"' in page.text
        assert "signalAgeLabel" in script.text
        assert "確定足 ${seconds}秒前" in script.text
        assert "最終推定 ${seconds}秒前" in script.text
        assert 'if (["10m", "30m"].includes(key)) return 60' in script.text
        assert 'if (key === "24h") return 3600' in script.text
        assert "data-signal-age" in script.text
        assert ".direction.buy, .direction.sell { color: var(--amber)" in styles.text
        assert ".direction.no-trade { color: #67a8ff" in styles.text
        assert 'id="open-position-count"' not in page.text
        assert "確率帯別の実現上昇率" in page.text
        assert "売買判定別の結果" in page.text
        assert 'id="action-breakdown-cards"' in page.text
        assert 'data-validation-horizon="overall"' in page.text
        assert "確率予測の採点" in page.text
        assert "コストモデルを事前固定した後" in page.text
        assert "全予測方向一致率" not in script.text
        assert "毎秒推定の検証" in page.text
        assert "非正式・別台帳" in page.text
        assert "renderRealtimeValidationDiagnostics" in script.text
        assert "prepareCalculator" in script.text
        assert "calc-max-loss" in page.text
        assert "逆算数量" in page.text
        assert "注文計算へ" not in page.text
        assert "見送った" not in page.text
        assert "保留" not in page.text

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
        assert exit_status.json()["active_plans"] == []
        assert exit_status.json()["open_position_count"] == 0
        assert exit_status.json()["exit_signal"]["code"] == "NO_MANUAL_POSITION"
        broker_sync = client.get("/api/manual/broker-sync")
        assert broker_sync.status_code == 200
        assert broker_sync.json()["status"] == "NOT_CONFIGURED"
        assert broker_sync.json()["safety"]["actual_post"] is False
        positions = client.get("/api/manual/positions")
        assert positions.status_code == 200
        assert positions.json()["positions"] == []
        assert positions.json()["safety"]["actual_post"] is False
        quick_start = client.post(
            "/api/manual/exit-plan/quick-start",
            json={
                "forecast_id": "missing_forecast",
                "horizon": "10m",
                "direction": "買い",
            },
        )
        assert quick_start.status_code == 422
        actual_fill = client.post(
            "/api/manual/exit-plan/actual-fill",
            json={"plan_id": 1, "actual_fill_price": 160.012},
        )
        assert actual_fill.status_code == 422
        validation = client.get("/api/manual/validation")
        assert validation.status_code == 200
        assert validation.json()["metrics"]["threshold_auto_change_allowed"] is False
        assert validation.json()["metrics"]["diagnostics"]["10m"]["action_breakdown"][
            "cost_adjusted_stay_fit_available"
        ] is False
        assert validation.json()["realtime_rolling"]["formal_signal"] is False
        assert validation.json()["realtime_rolling"]["promotion_eligible"] is False
        assert validation.json()["realtime_rolling"]["target_price_max_delay_seconds"] == 15
        assert client.post("/api/manual/decisions", json={}).status_code == 404
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
    assert client.get("/api/manual/positions").status_code == 404
    assert client.get("/api/manual/exit-plan").status_code == 404
    assert client.post("/api/manual/exit-plan").status_code == 404
    assert client.post("/api/manual/exit-plan/quick-start").status_code == 404
    assert client.post("/api/manual/exit-plan/actual-fill").status_code == 404
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
