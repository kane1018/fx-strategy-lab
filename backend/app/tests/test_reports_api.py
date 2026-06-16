"""Tests for the read-only /api/reports routes (app/routers/reports.py).

Uses TestClient + tmp_path only; the real analysis_exports/ is never read. The
server-fixed exports_root is injected by overriding get_settings (no .env access).
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from scripts.fx_eval_common import ensure_output_dir, safety_metadata, write_json


def _summary() -> dict:
    return {
        "window_count": 15, "median_expectancy": 0.02, "median_pf": 1.05,
        "positive_windows": 8, "negative_windows": 7, "total_pnl": 12.3,
        "max_drawdown_max": -9.9, "group_prior10": {}, "group_oos5": {},
        "verdict": "研究用ベースライン",
    }


def _make_run(root, name, *, n_summary=1, created_at="2026-02-01T00:00:00",
              with_csv=True):
    run = ensure_output_dir(root / name)
    write_json(run / "manifest.json", {
        "run_id": name, "kind": "rsi_final15", "strategy": "rsi_reversal",
        "timeframe": "M5", "cost_scenario": "current_cost", "spread_pips": 1.2,
        "slippage_pips": 0.2, "stop_loss_pips": 30, "take_profit_pips": 60,
        "created_at": created_at, **safety_metadata()})
    write_json(run / "warnings.json", {"fetch_warnings": []})
    for i in range(n_summary):
        write_json(run / f"metrics_{i}_15window_summary.json", _summary())
    if with_csv:
        (run / "metrics_by_window.csv").write_text("window,n,accuracy\nw1,30,0.55\n")
    return run


@pytest.fixture
def client_factory(tmp_path):
    """Return a TestClient whose reports root points at the given dir (default tmp_path)."""
    def make(root=None):
        resolved = tmp_path if root is None else root
        app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
            analysis_exports_root=str(resolved))
        return TestClient(app)
    yield make
    app.dependency_overrides.pop(get_settings, None)


def test_api01_list_returns_items_and_count(client_factory, tmp_path) -> None:
    _make_run(tmp_path, "run_a")
    _make_run(tmp_path, "run_b")
    resp = client_factory().get("/api/reports")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert {r["run_id"] for r in body["items"]} == {"run_a", "run_b"}


def test_api02_list_includes_error_rows(client_factory, tmp_path) -> None:
    _make_run(tmp_path, "ok_run")
    _make_run(tmp_path, "broken_run", n_summary=0)  # no summary -> error row
    body = client_factory().get("/api/reports").json()
    broken = [r for r in body["items"] if r["run_id"] == "broken_run"][0]
    assert broken["has_error"] is True
    assert broken["read_only_confirmed"] is False


def test_api03_list_does_not_include_csv_body(client_factory, tmp_path) -> None:
    _make_run(tmp_path, "run_a", with_csv=True)
    resp = client_factory().get("/api/reports")
    assert "window,n,accuracy" not in resp.text  # CSV content never inlined


def test_api04_detail_returns_core_blocks(client_factory, tmp_path) -> None:
    _make_run(tmp_path, "run_a")
    body = client_factory().get("/api/reports/run_a").json()
    for key in ("index", "manifest", "warnings", "summary", "files"):
        assert key in body
    assert body["run_id"] == "run_a"
    assert "window,n,accuracy" not in client_factory().get("/api/reports/run_a").text


@pytest.mark.parametrize("bad", ["foo$bar", "a..b", "sp ace", "semi;colon", "name@x"])
def test_api05_invalid_run_id_returns_400(client_factory, bad) -> None:
    # names that reach the handler and fail validation -> 400 (embedded '..' included)
    assert client_factory().get(f"/api/reports/{bad}").status_code == 400


def test_api05b_traversal_run_id_never_escapes(client_factory, tmp_path) -> None:
    # literal '..'/'/' are normalized/blocked at the URL+routing layer (never a 200 detail);
    # the server-side guard additionally rejects them. Either way: no run detail is served.
    _make_run(tmp_path, "run_a")
    for path in ("/api/reports/..", "/api/reports/../etc", "/api/reports/a/b"):
        assert client_factory().get(path).status_code != 200


def test_api06_missing_run_returns_404(client_factory, tmp_path) -> None:
    _make_run(tmp_path, "run_a")
    assert client_factory().get("/api/reports/does_not_exist").status_code == 404


def test_api07_broken_run_detail_returns_422(client_factory, tmp_path) -> None:
    _make_run(tmp_path, "no_sum", n_summary=0)
    _make_run(tmp_path, "dup", n_summary=2)
    c = client_factory()
    assert c.get("/api/reports/no_sum").status_code == 422
    assert c.get("/api/reports/dup").status_code == 422


def test_api08_markdown_endpoints_return_markdown(client_factory, tmp_path) -> None:
    _make_run(tmp_path, "run_a")
    c = client_factory()
    index_md = c.get("/api/reports/markdown").json()
    detail_md = c.get("/api/reports/run_a/markdown").json()
    assert "markdown" in index_md and "| status | run_id |" in index_md["markdown"]
    assert "markdown" in detail_md
    assert detail_md["markdown"].startswith("# FX Report Detail: run_a")


def test_api08b_markdown_path_not_treated_as_run_id(client_factory, tmp_path) -> None:
    # /api/reports/markdown must hit the list-markdown route, not /{run_id}
    _make_run(tmp_path, "run_a")
    resp = client_factory().get("/api/reports/markdown")
    assert resp.status_code == 200
    assert "| status | run_id |" in resp.json()["markdown"]


def test_api09_safety_mapping_preserved(client_factory, tmp_path) -> None:
    _make_run(tmp_path, "run_a")
    row = client_factory().get("/api/reports").json()["items"][0]
    for key in ("read_only_confirmed", "safety", "safety_complete", "safety_conflicts"):
        assert key in row
    assert set(row["safety"]) >= {"real_order", "gmo_readonly", "no_order_execution"}
    detail = client_factory().get("/api/reports/run_a").json()
    assert "read_only_confirmed" in detail["index"]


def test_api10_only_get_methods_on_reports(client_factory, tmp_path) -> None:
    _make_run(tmp_path, "run_a")
    c = client_factory()
    for method in ("post", "put", "patch", "delete"):
        assert getattr(c, method)("/api/reports").status_code == 405
        assert getattr(c, method)("/api/reports/run_a").status_code == 405
    # route table: every /api/reports route exposes GET (+HEAD) only
    for route in app.routes:
        if getattr(route, "path", "").startswith("/api/reports"):
            assert route.methods <= {"GET", "HEAD"}


def test_root_missing_returns_503(client_factory, tmp_path) -> None:
    resp = client_factory(tmp_path / "nope").get("/api/reports")
    assert resp.status_code == 503
    assert resp.json()["detail"]["read_only_confirmed"] is False
