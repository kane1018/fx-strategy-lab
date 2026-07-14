"""H-11 manual settlement read-only sync tests; fake HTTP and fake broker only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx

from app.h11_manual.contracts import Direction, Horizon, SignalStatus, SignalView
from app.h11_manual.service import ManualSignalService
from app.h11_manual.settlement_sync import (
    ALLOWED_PRIVATE_GET_PATHS,
    LATEST_EXECUTIONS_PATH,
    OPEN_POSITIONS_PATH,
    FakeManualSettlementReadClient,
    GmoManualSettlementPrivateGetClient,
    ManualSettlementSnapshot,
    SanitizedExecution,
    SanitizedOpenPosition,
)


def _execution(
    *,
    ref: str,
    position_ref: str = "opaque-position-a",
    settle_type: str = "OPEN",
    side: str = "BUY",
    size: str = "10000",
    price: str = "160.012",
    executed_at: datetime,
) -> SanitizedExecution:
    return SanitizedExecution(
        execution_ref=ref,
        position_ref=position_ref,
        symbol="USD_JPY",
        side=side,
        settle_type=settle_type,
        size=Decimal(size),
        price=Decimal(price),
        executed_at_utc=executed_at.isoformat(),
    )


def _position(
    *, position_ref: str = "opaque-position-a", side: str = "BUY", size: str = "10000"
) -> SanitizedOpenPosition:
    return SanitizedOpenPosition(
        position_ref=position_ref,
        symbol="USD_JPY",
        side=side,
        size=Decimal(size),
        average_price=Decimal("160.012"),
    )


def _service_with_plan(tmp_path, *, now: datetime) -> tuple[ManualSignalService, int]:
    service = ManualSignalService(tmp_path, supplemental_h1_paths=())
    forecast = SignalView(
        horizon=Horizon.MINUTES_10,
        direction=Direction.BUY,
        status=SignalStatus.OK,
        p_up=0.62,
        p_down=0.38,
        reason="test",
        origin_time_utc=now.isoformat(),
        model_config_hash="sha256:manual-sync-test",
        forecast_id="manual_sync_forecast",
        recorded_mode="PROSPECTIVE",
    )
    assert service.ledger.record_forecast(forecast, recorded_at=now)
    assert service.ledger.record_realtime_tick(
        bid=160.0,
        ask=160.005,
        market_time_utc=now.isoformat(),
        sampled_at=now,
    )
    opened = service.quick_start_exit_plan(
        forecast_id="manual_sync_forecast",
        horizon=Horizon.MINUTES_10,
        direction=Direction.BUY,
        now=now,
    )
    return service, int(opened["plan_id"])


def test_private_transport_uses_only_two_gets_and_opaque_refs() -> None:
    raw_execution_id = "raw-execution-123"
    raw_position_id = "raw-position-456"
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.method == "GET"
        assert request.url.path in ALLOWED_PRIVATE_GET_PATHS
        if request.url.path == LATEST_EXECUTIONS_PATH:
            return httpx.Response(
                200,
                json={
                    "status": 0,
                    "data": {
                        "list": [
                            {
                                "executionId": raw_execution_id,
                                "positionId": raw_position_id,
                                "symbol": "USD_JPY",
                                "side": "BUY",
                                "settleType": "OPEN",
                                "size": "10000",
                                "price": "160.012",
                                "timestamp": "2026-07-15T01:00:01+00:00",
                            }
                        ]
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "status": 0,
                "data": {
                    "list": [
                        {
                            "positionId": raw_position_id,
                            "symbol": "USD_JPY",
                            "side": "BUY",
                            "size": "10000",
                            "price": "160.012",
                        }
                    ]
                },
            },
        )

    http = httpx.Client(
        base_url="https://example.invalid",
        transport=httpx.MockTransport(handler),
    )
    client = GmoManualSettlementPrivateGetClient(
        api_key="fake-key",
        api_secret="fake-secret",
        client=http,
        timestamp_factory=lambda: "1700000000000",
    )

    snapshot = client.fetch_snapshot(symbol="USD_JPY")

    assert seen == [("GET", LATEST_EXECUTIONS_PATH), ("GET", OPEN_POSITIONS_PATH)]
    assert raw_execution_id not in repr(snapshot)
    assert raw_position_id not in repr(snapshot)
    assert snapshot.executions[0].execution_ref.startswith("hmac256:")
    assert snapshot.open_positions[0].position_ref == snapshot.executions[0].position_ref
    assert "fake-key" not in repr(client)
    assert "fake-secret" not in repr(client)


def test_sync_source_has_no_broker_write_or_environment_escape_hatch() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "h11_manual"
        / "settlement_sync.py"
    ).read_text()
    lowered = source.lower()
    assert ".post(" not in lowered
    assert ".put(" not in lowered
    assert ".delete(" not in lowered
    assert "closeorder" not in lowered
    assert "cancelorder" not in lowered
    assert "changeorder" not in lowered
    assert "os.environ" not in lowered
    assert "getenv(" not in lowered
    assert "dotenv" not in lowered
    assert "print(" not in lowered
    assert "logger" not in lowered


def test_open_partial_and_full_close_are_applied_idempotently(tmp_path) -> None:
    now = datetime(2026, 7, 15, 1, 0, tzinfo=UTC)
    service, plan_id = _service_with_plan(tmp_path, now=now)
    open_execution = _execution(ref="opaque-open", executed_at=now + timedelta(seconds=1))
    service.settlement_reader = FakeManualSettlementReadClient(
        ManualSettlementSnapshot(
            executions=(open_execution,),
            open_positions=(_position(),),
            source="FAKE_READONLY",
        )
    )

    opened = service.synchronize_manual_settlements(now=now + timedelta(seconds=2))
    active = opened["active_plans"][0]["plan"]
    assert opened["events"] == [{"type": "OPEN_LINKED", "plan_id": plan_id}]
    assert active["entry_price"] == 160.012
    assert active["stop_loss_price"] == 159.862
    assert active["take_profit_price"] == 160.237
    assert active["broker_sync"]["state"] == "LINKED"
    assert active["broker_sync"]["entry_size"] == 10000

    partial = _execution(
        ref="opaque-close-1",
        settle_type="CLOSE",
        side="SELL",
        size="4000",
        price="160.050",
        executed_at=now + timedelta(seconds=10),
    )
    service.settlement_reader = FakeManualSettlementReadClient(
        ManualSettlementSnapshot(
            executions=(open_execution, partial),
            open_positions=(_position(size="6000"),),
            source="FAKE_READONLY",
        )
    )
    partially_closed = service.synchronize_manual_settlements(now=now + timedelta(seconds=11))
    active = partially_closed["active_plans"][0]["plan"]
    assert partially_closed["events"] == [
        {"type": "PARTIAL_CLOSE_APPLIED", "plan_id": plan_id}
    ]
    assert active["broker_sync"]["state"] == "PARTIALLY_CLOSED"
    assert active["broker_sync"]["remaining_size"] == 6000

    final = _execution(
        ref="opaque-close-2",
        settle_type="CLOSE",
        side="SELL",
        size="6000",
        price="160.100",
        executed_at=now + timedelta(seconds=20),
    )
    service.settlement_reader = FakeManualSettlementReadClient(
        ManualSettlementSnapshot(
            executions=(open_execution, partial, final),
            open_positions=(),
            source="FAKE_READONLY",
        )
    )
    closed = service.synchronize_manual_settlements(now=now + timedelta(seconds=21))
    assert closed["events"] == [{"type": "CLOSE_APPLIED", "plan_id": plan_id}]
    assert closed["active_plans"] == []
    history = service.ledger.manual_trade_history()
    assert history[0]["status"] == "CLOSED"
    assert history[0]["exit_reason"] == "API同期決済"
    assert history[0]["exit_price"] == 160.08

    repeated = service.synchronize_manual_settlements(now=now + timedelta(seconds=22))
    assert repeated["events"] == []
    assert len(service.ledger.manual_trade_history()) == 1


def test_ambiguous_open_is_not_guessed(tmp_path) -> None:
    now = datetime(2026, 7, 15, 2, 0, tzinfo=UTC)
    service, _ = _service_with_plan(tmp_path, now=now)
    second_forecast = SignalView(
        horizon=Horizon.MINUTES_30,
        direction=Direction.BUY,
        status=SignalStatus.OK,
        p_up=0.63,
        p_down=0.37,
        reason="test",
        origin_time_utc=now.isoformat(),
        model_config_hash="sha256:manual-sync-test",
        forecast_id="manual_sync_forecast_30m",
        recorded_mode="PROSPECTIVE",
    )
    assert service.ledger.record_forecast(second_forecast, recorded_at=now)
    second_plan = service.open_exit_plan(
        forecast_id="manual_sync_forecast_30m",
        horizon=Horizon.MINUTES_30,
        direction=Direction.BUY,
        entry_price=160.005,
        stop_loss_price=159.855,
        take_profit_price=160.230,
        now=now,
    )
    assert service.ledger.record_manual_trade_quick_start(
        plan_id=int(second_plan["plan_id"]),
        forecast_id="manual_sync_forecast_30m",
        horizon=Horizon.MINUTES_30,
        reference_entry_price=160.005,
        started_at=now,
    )
    service.settlement_reader = FakeManualSettlementReadClient(
        ManualSettlementSnapshot(
            executions=(
                _execution(ref="one-open-for-two-plans", executed_at=now + timedelta(seconds=1)),
            ),
            open_positions=(_position(),),
            source="FAKE_READONLY",
        )
    )

    result = service.synchronize_manual_settlements(now=now + timedelta(seconds=2))

    assert result["events"] == []
    assert {item["plan"]["broker_sync"]["state"] for item in result["active_plans"]} == {
        "AMBIGUOUS_OPEN"
    }
