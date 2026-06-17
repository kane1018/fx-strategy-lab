"""Tests for the read-only deployment entrypoint (app/main_readonly.py).

Proves the public surface is limited to /health + GET /api/reports*: report GETs are
reachable, POST to reports is 405, and the order/paper/bot/automation/broker routes that
exist on app.main:app are absent (404) here. Uses tmp_path fixtures (no real analysis_exports).
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main_readonly import app
from scripts.create_e2e_report_fixtures import create_e2e_report_fixtures


@pytest.fixture
def client(tmp_path):
    create_e2e_report_fixtures(tmp_path)
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
        analysis_exports_root=str(tmp_path))
    yield TestClient(app)
    app.dependency_overrides.pop(get_settings, None)


def test_health_ok() -> None:
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["mode"] == "read-only"
    assert body["live_broker_implemented"] is False


def test_report_gets_reachable(client) -> None:
    listing = client.get("/api/reports")
    assert listing.status_code == 200
    assert "items" in listing.json() and "count" in listing.json()
    assert client.get("/api/reports/e2e_normal_run").status_code == 200
    assert client.get("/api/reports/markdown").status_code == 200
    assert client.get("/api/reports/e2e_normal_run/markdown").status_code == 200


def test_post_to_reports_is_405(client) -> None:
    # the reports router is GET-only; writes are not allowed
    assert client.post("/api/reports").status_code == 405


@pytest.mark.parametrize(
    "path",
    [
        "/api/orders",
        "/api/paper/sessions",
        "/api/signals",
        "/api/bot/status",
        "/api/automation/status",
        "/api/broker/connection-test",
        "/api/backtests",
    ],
)
def test_non_reports_routes_absent(client, path) -> None:
    # these exist on app.main:app but must NOT be reachable on the read-only entrypoint
    assert client.get(path).status_code == 404
    assert client.post(path).status_code == 404


def test_cors_allows_only_get_options() -> None:
    resp = TestClient(app).options(
        "/api/reports",
        headers={
            "Origin": get_settings().frontend_origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    allow = resp.headers.get("access-control-allow-methods", "")
    assert "GET" in allow
    assert "POST" not in allow and "DELETE" not in allow
