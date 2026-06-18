"""Tests for the local shadow-session runner (app/shadow/session.py).

Offline only (mock candles / httpx MockTransport). Verifies log+summary files, safety
flags, counts/PnL, the steps cap, halted behavior, gitignore coverage, and that the
gmo-public path uses only the Public read-only adapter (no auth / no orders).
"""

import json

import httpx

from app.shadow.gmo_public import GmoPublicMarketDataClient
from app.shadow.models import Candle, Signal
from app.shadow.session import make_mock_candles, run_shadow_session


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_mock_session_writes_events_and_summary(tmp_path) -> None:
    summary = run_shadow_session(
        symbol="USD_JPY", interval="M1", source="mock",
        candles=make_mock_candles(20), out_root=tmp_path, steps=20, run_id="r_mock",
    )
    run_dir = tmp_path / "r_mock"
    assert (run_dir / "events.jsonl").exists()
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "metadata.json").exists()
    events = _read_jsonl(run_dir / "events.jsonl")
    assert len(events) == 20 == summary["events_count"]
    # every event keeps no-order safety
    for ev in events:
        s = ev["safety"]
        assert s["real_order"] is False
        assert s["private_api_used"] is False
        assert s["api_key_used"] is False
        assert s["no_order_execution"] is True
        assert s["live_trading_environment_enabled"] is False


def test_summary_counts_and_pnl(tmp_path) -> None:
    summary = run_shadow_session(
        symbol="USD_JPY", interval="M1", source="mock",
        candles=make_mock_candles(10), out_root=tmp_path, steps=10, run_id="r_counts",
    )
    assert summary["buy_count"] + summary["sell_count"] + summary["flat_count"] == 10
    assert summary["virtual_orders_count"] >= 1
    assert "final_unrealized_pnl" in summary and "final_position_units" in summary
    assert summary["safety"]["real_order"] is False


def test_steps_cap_is_respected(tmp_path) -> None:
    # 50 candles available but only 5 steps requested -> 5 executed
    summary = run_shadow_session(
        symbol="USD_JPY", interval="M1", source="mock",
        candles=make_mock_candles(50), out_root=tmp_path, steps=5, run_id="r_cap",
    )
    assert summary["steps_executed"] == 5
    assert summary["data_points"] == 50
    assert len(_read_jsonl(tmp_path / "r_cap" / "events.jsonl")) == 5


def test_halt_stops_position_growth(tmp_path) -> None:
    # units > max_units -> halt on first actionable signal, position never opens
    summary = run_shadow_session(
        symbol="USD_JPY", interval="M1", source="mock",
        candles=make_mock_candles(20), out_root=tmp_path, steps=20, run_id="r_halt",
        units=500, max_units=100,
    )
    assert summary["halted"] is True
    assert "exceed max_units" in summary["halt_reason"]
    assert summary["final_position_units"] == 0
    assert summary["virtual_orders_count"] == 0


def test_flat_signal_session_creates_no_orders(tmp_path) -> None:
    def always_flat(_candles) -> Signal:
        return Signal(side="flat", reason="test")

    summary = run_shadow_session(
        symbol="USD_JPY", interval="M1", source="mock",
        candles=make_mock_candles(8), out_root=tmp_path, steps=8, run_id="r_flat",
        signal_fn=always_flat,
    )
    assert summary["virtual_orders_count"] == 0
    assert summary["final_position_side"] == "flat"
    assert summary["final_unrealized_pnl"] == 0.0


def test_gmo_public_source_uses_readonly_adapter_offline(tmp_path) -> None:
    # gmo-public path through the Public adapter, mocked with no network / no auth.
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/klines")
        assert "authorization" not in {k.lower() for k in request.headers.keys()}
        data = [
            {"openTime": str(1781308800000 + i * 60000), "open": "154.0",
             "high": "154.2", "low": "153.9", "close": f"{154.0 + i * 0.1:.3f}"}
            for i in range(5)
        ]
        return httpx.Response(200, json={"status": 0, "data": data, "responsetime": "t"})

    client = GmoPublicMarketDataClient(
        client=httpx.Client(base_url="https://example.test/public",
                            transport=httpx.MockTransport(handler))
    )
    candles = client.fetch_candles("USD_JPY", "M1", limit=5, date="20260618")
    assert len(candles) == 5 and all(isinstance(c, Candle) for c in candles)
    summary = run_shadow_session(
        symbol="USD_JPY", interval="M1", source="gmo-public",
        candles=candles, out_root=tmp_path, steps=5, run_id="r_gmo",
    )
    assert summary["steps_executed"] == 5
    assert summary["safety"]["api_key_used"] is False
    assert summary["safety"]["private_api_used"] is False


def test_shadow_exports_is_gitignored() -> None:
    # repo policy: generated shadow runs must never be committed
    from pathlib import Path

    gitignore = Path(__file__).resolve().parents[3] / ".gitignore"
    text = gitignore.read_text()
    assert "shadow_exports/" in text
