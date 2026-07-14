"""Local-ledger and three-horizon service tests; no network or external data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.h11_manual import data as data_module
from app.h11_manual.contracts import (
    Direction,
    Horizon,
    ManualExitReason,
    OperatorDecision,
    SignalStatus,
    SignalView,
)
from app.h11_manual.data import save_candle_csv
from app.h11_manual.ledger import SignalLedger
from app.h11_manual.service import ManualSignalService
from app.h11_manual.short_model import train_short_model
from app.shadow.models import Candle


def _synthetic_frame(rows: int, frequency: str, seed: int = 23) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 155.0 * np.exp(np.cumsum(rng.normal(0.000002, 0.00015, rows)))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    width = np.abs(rng.normal(0.008, 0.002, rows))
    return pd.DataFrame(
        {
            "time_utc": pd.date_range("2026-01-01", periods=rows, freq=frequency, tz="UTC").astype(
                str
            ),
            "open": open_,
            "high": np.maximum(open_, close) + width,
            "low": np.minimum(open_, close) - width,
            "close": close,
        }
    )


def test_ledger_is_idempotent_and_scores_resolved_forecasts(tmp_path) -> None:
    ledger = SignalLedger(tmp_path / "signals.sqlite3")
    signal = SignalView(
        horizon=Horizon.MINUTES_10,
        direction=Direction.BUY,
        status=SignalStatus.OK,
        p_up=0.62,
        p_down=0.38,
        reason="test",
        origin_time_utc="2026-07-14T01:00:00+00:00",
        model_config_hash="sha256:test",
        forecast_id="forecast_test",
        recorded_mode="PROSPECTIVE",
    )
    assert ledger.record_forecast(signal)
    assert not ledger.record_forecast(signal)
    assert ledger.resolve(
        "forecast_test", outcome_up=True, target_time_utc="2026-07-14T01:10:00+00:00"
    )
    assert not ledger.resolve(
        "forecast_test", outcome_up=False, target_time_utc="2026-07-14T01:10:00+00:00"
    )
    summary = ledger.validation_summary()
    assert summary["overall"]["resolved_n"] == 1
    assert summary["overall"]["brier"] == round((0.62 - 1.0) ** 2, 6)
    decision_id = ledger.record_operator_decision(
        forecast_id="forecast_test",
        horizon=Horizon.MINUTES_10,
        decision=OperatorDecision.TRADED,
    )
    assert decision_id == 1
    assert ledger.latest_decisions()[0]["decision"] == "取引した"


def test_validation_diagnostics_are_prospective_and_overlap_aware(tmp_path) -> None:
    ledger = SignalLedger(tmp_path / "signals.sqlite3")
    probabilities = (0.40, 0.44, 0.56, 0.60, 0.64)
    outcomes = (False, False, True, True, False)
    for index, (probability, outcome) in enumerate(zip(probabilities, outcomes, strict=True)):
        origin = datetime(2026, 7, 14, 1, index, tzinfo=UTC).isoformat()
        signal = SignalView(
            horizon=Horizon.MINUTES_10,
            direction=Direction.BUY if probability >= 0.58 else Direction.NO_TRADE,
            status=SignalStatus.OK,
            p_up=probability,
            p_down=1 - probability,
            reason="test",
            origin_time_utc=origin,
            model_config_hash="sha256:test",
            forecast_id=f"forecast_{index}",
            recorded_mode="PROSPECTIVE",
        )
        assert ledger.record_forecast(signal)
        assert ledger.resolve(
            signal.forecast_id or "",
            outcome_up=outcome,
            target_time_utc=(datetime.fromisoformat(origin) + timedelta(minutes=10)).isoformat(),
        )

    replayed = SignalView(
        horizon=Horizon.MINUTES_10,
        direction=Direction.BUY,
        status=SignalStatus.OK,
        p_up=0.99,
        p_down=0.01,
        reason="replayed",
        origin_time_utc=datetime(2026, 7, 13, tzinfo=UTC).isoformat(),
        model_config_hash="sha256:test",
        forecast_id="forecast_replayed",
        recorded_mode="REPLAYED_AFTER_MATURITY",
    )
    assert ledger.record_forecast(replayed)
    assert ledger.resolve(
        "forecast_replayed", outcome_up=False, target_time_utc="2026-07-13T00:10:00+00:00"
    )

    summary = ledger.validation_summary()
    diagnostics = summary["diagnostics"]["10m"]
    assert summary["scope"] == "PROSPECTIVE_ONLY"
    assert summary["threshold_auto_change_allowed"] is False
    assert summary["horizons"]["10m"]["resolved_n"] == 5
    assert diagnostics["raw_resolved_n"] == 5
    assert diagnostics["non_overlapping_n"] == 1
    assert sum(row["sample_n"] for row in diagnostics["calibration_bands"]) == 5
    current = next(row for row in diagnostics["threshold_curve"] if row["is_current_v1"])
    assert current["buy_threshold"] == 0.58
    assert current["sell_threshold"] == 0.42
    assert current["sample_n"] == 3

    series = ledger.signal_probability_series(limit=120)
    assert [row["p_up"] for row in series["10m"]] == list(probabilities)
    assert series["30m"] == []
    assert series["24h"] == []
    assert all(row["p_up"] != 0.99 for row in series["10m"])


def test_realtime_tick_samples_are_separate_and_one_per_second(tmp_path) -> None:
    ledger = SignalLedger(tmp_path / "signals.sqlite3")
    sampled_at = datetime(2026, 7, 14, 1, 2, 3, 400_000, tzinfo=UTC)
    assert ledger.record_realtime_tick(
        bid=160.001,
        ask=160.006,
        market_time_utc="2026-07-14T01:02:03+00:00",
        sampled_at=sampled_at,
    )
    assert not ledger.record_realtime_tick(
        bid=160.002,
        ask=160.007,
        market_time_utc="2026-07-14T01:02:03+00:00",
        sampled_at=sampled_at.replace(microsecond=900_000),
    )
    assert ledger.realtime_tick_count() == 1
    assert ledger.latest_forecasts() == []
    assert ledger.recent_realtime_ticks()[0]["bid"] == 160.001


def test_realtime_rolling_forecasts_resolve_only_near_exact_target_time(tmp_path) -> None:
    ledger = SignalLedger(tmp_path / "signals.sqlite3")
    origin = datetime(2026, 7, 14, 1, 0, 0, tzinfo=UTC)
    assert ledger.record_realtime_rolling_forecast(
        forecast_id="rolling_resolved",
        horizon=Horizon.MINUTES_10,
        origin_time_utc=origin.isoformat(),
        p_up=0.60,
        direction=Direction.BUY,
        origin_bid=160.0,
        estimate_mode="M1_BOOTSTRAP_ROLLING_60S",
        model_config_hash="sha256:test",
        tick_native_window_ready=False,
        recorded_at=origin,
    )
    assert not ledger.record_realtime_rolling_forecast(
        forecast_id="rolling_resolved",
        horizon=Horizon.MINUTES_10,
        origin_time_utc=origin.isoformat(),
        p_up=0.60,
        direction=Direction.BUY,
        origin_bid=160.0,
        estimate_mode="M1_BOOTSTRAP_ROLLING_60S",
        model_config_hash="sha256:test",
        tick_native_window_ready=False,
        recorded_at=origin,
    )
    resolution = ledger.resolve_due_realtime_rolling_forecasts(
        observed_at=origin + timedelta(minutes=10, seconds=5), bid=160.1
    )
    assert resolution == {"resolved_n": 1, "target_price_missing_n": 0}

    missing_origin = origin + timedelta(seconds=20)
    assert ledger.record_realtime_rolling_forecast(
        forecast_id="rolling_missing",
        horizon=Horizon.MINUTES_10,
        origin_time_utc=missing_origin.isoformat(),
        p_up=0.40,
        direction=Direction.SELL,
        origin_bid=160.1,
        estimate_mode="TICK_NATIVE_ROLLING_60S",
        model_config_hash="sha256:test",
        tick_native_window_ready=True,
        recorded_at=missing_origin,
    )
    resolution = ledger.resolve_due_realtime_rolling_forecasts(
        observed_at=missing_origin + timedelta(minutes=10, seconds=16), bid=159.9
    )
    assert resolution == {"resolved_n": 0, "target_price_missing_n": 1}

    summary = ledger.realtime_rolling_validation_summary()
    ten_minutes = summary["horizons"]["10m"]
    assert summary["formal_signal"] is False
    assert summary["promotion_eligible"] is False
    assert summary["target_price_max_delay_seconds"] == 15
    assert ten_minutes["forecast_n"] == 2
    assert ten_minutes["resolved_n"] == 1
    assert ten_minutes["target_price_missing_n"] == 1
    assert ten_minutes["pending_n"] == 0
    assert ten_minutes["target_resolution_coverage"] == 0.5
    assert ten_minutes["raw_metrics"]["brier"] == 0.16
    assert ten_minutes["non_overlapping_metrics"]["resolved_n"] == 1


def test_service_outputs_three_horizons_and_records_locally(tmp_path) -> None:
    m1 = _synthetic_frame(4_000, "min")
    h1 = _synthetic_frame(1_000, "h", seed=31)
    now = pd.to_datetime(m1.iloc[-1]["time_utc"], utc=True).to_pydatetime() + timedelta(minutes=2)
    service = ManualSignalService(tmp_path, supplemental_h1_paths=())
    save_candle_csv(service.repository.m1_path, m1)
    save_candle_csv(service.repository.h1_path, h1)
    train_short_model(m1, now=now).save(service.short_artifact_path)

    payload = service.current(now=now)
    assert payload["screen"] == "シグナル"
    assert [item["horizon"] for item in payload["signals"]] == ["10m", "30m", "24h"]
    allowed = {"買い", "売り", "見送り", "判定不可"}
    assert all(item["direction"] in allowed for item in payload["signals"])
    assert payload["safety"] == {
        "actual_post": False,
        "broker_read": False,
        "broker_write": False,
        "private_api": False,
        "credential_read": False,
        "env_read": False,
        "automatic_trade_authority": False,
    }
    assert len(service.ledger.latest_forecasts()) >= 2


def test_realtime_estimate_is_non_formal_and_does_not_record_forecast(tmp_path) -> None:
    m1 = _synthetic_frame(4_000, "min")
    now = pd.to_datetime(m1.iloc[-1]["time_utc"], utc=True).to_pydatetime() + timedelta(minutes=2)
    service = ManualSignalService(tmp_path, supplemental_h1_paths=())
    save_candle_csv(service.repository.m1_path, m1)
    train_short_model(m1, now=now).save(service.short_artifact_path)

    payload = service.realtime_estimate(
        bid=float(m1.iloc[-1]["close"]),
        ask=float(m1.iloc[-1]["close"]) + 0.005,
        market_time_utc=now.isoformat(),
        now=now,
    )

    assert payload["status"] == "REALTIME_ESTIMATE_NOT_FORMAL"
    assert [item["horizon"] for item in payload["estimates"]] == ["10m", "30m"]
    assert all(item["formal_signal"] is False for item in payload["estimates"])
    assert all(item["promotion_eligible"] is False for item in payload["estimates"])
    assert all(item["estimate_mode"] == "M1_BOOTSTRAP_ROLLING_60S" for item in payload["estimates"])
    assert service.ledger.latest_forecasts() == []
    assert payload["collection"]["stored_sample_count"] == 1
    assert payload["collection"]["validation_forecasts_recorded_n"] == 2
    assert service.ledger.realtime_rolling_forecast_count() == 2

    later = now + timedelta(minutes=10, seconds=5)
    later_payload = service.realtime_estimate(
        bid=float(m1.iloc[-1]["close"]) + 0.01,
        ask=float(m1.iloc[-1]["close"]) + 0.015,
        market_time_utc=later.isoformat(),
        now=later,
    )
    assert later_payload["collection"]["validation_resolutions_this_tick"] == {
        "resolved_n": 1,
        "target_price_missing_n": 0,
    }
    validation = service.validation()["realtime_rolling"]
    assert validation["horizons"]["10m"]["resolved_n"] == 1
    assert validation["horizons"]["30m"]["resolved_n"] == 0


def test_manual_exit_plan_is_local_record_only_with_fixed_levels(tmp_path) -> None:
    m1 = _synthetic_frame(4_000, "min")
    now = pd.to_datetime(m1.iloc[-1]["time_utc"], utc=True).to_pydatetime() + timedelta(minutes=2)
    service = ManualSignalService(tmp_path, supplemental_h1_paths=())
    save_candle_csv(service.repository.m1_path, m1)
    train_short_model(m1, now=now).save(service.short_artifact_path)
    forecast = service.current(now=now)["signals"][0]

    opened = service.open_exit_plan(
        forecast_id=forecast["forecast_id"],
        horizon=Horizon.MINUTES_10,
        direction=Direction.BUY,
        entry_price=160.0,
        stop_loss_price=159.85,
        take_profit_price=160.225,
        now=now,
    )
    assert opened["opened"] is True
    assert opened["active"]["status"] == "OPEN"
    assert opened["exit_signal"]["code"] == "PRICE_UNKNOWN"
    assert opened["automatic_exit"] is False
    assert opened["broker_state_known"] is False

    closed = service.close_exit_plan(
        reason=ManualExitReason.MANUAL,
        exit_price=160.05,
        now=now + timedelta(minutes=1),
    )
    assert closed["closed"] is True
    assert closed["active"] is None
    assert closed["history"][0]["exit_reason"] == "手動終了"


def test_quick_exit_start_uses_fresh_public_side_and_fixed_preset(tmp_path) -> None:
    now = datetime(2026, 7, 15, 1, 0, tzinfo=UTC)
    service = ManualSignalService(tmp_path, supplemental_h1_paths=())
    signal = SignalView(
        horizon=Horizon.MINUTES_10,
        direction=Direction.BUY,
        status=SignalStatus.OK,
        p_up=0.62,
        p_down=0.38,
        reason="test",
        origin_time_utc=now.isoformat(),
        model_config_hash="sha256:test",
        forecast_id="quick_forecast_test",
        recorded_mode="PROSPECTIVE",
    )
    assert service.ledger.record_forecast(signal, recorded_at=now)

    with pytest.raises(ValueError, match="fresh Public quote is unavailable"):
        service.quick_start_exit_plan(
            forecast_id="quick_forecast_test",
            horizon=Horizon.MINUTES_10,
            direction=Direction.BUY,
            now=now,
        )

    assert service.ledger.record_realtime_tick(
        bid=160.000,
        ask=160.005,
        market_time_utc=(now - timedelta(seconds=16)).isoformat(),
        sampled_at=now - timedelta(seconds=16),
    )
    with pytest.raises(ValueError, match="older than 15 seconds"):
        service.quick_start_exit_plan(
            forecast_id="quick_forecast_test",
            horizon=Horizon.MINUTES_10,
            direction=Direction.BUY,
            now=now,
        )

    assert service.ledger.record_realtime_tick(
        bid=160.000,
        ask=160.005,
        market_time_utc=now.isoformat(),
        sampled_at=now,
    )
    with pytest.raises(ValueError, match="must match the formal forecast"):
        service.quick_start_exit_plan(
            forecast_id="quick_forecast_test",
            horizon=Horizon.MINUTES_10,
            direction=Direction.SELL,
            now=now,
        )

    result = service.quick_start_exit_plan(
        forecast_id="quick_forecast_test",
        horizon=Horizon.MINUTES_10,
        direction=Direction.BUY,
        now=now,
    )
    assert result["opened"] is True
    assert result["active"]["entry_price"] == 160.005
    assert result["active"]["stop_loss_price"] == 159.855
    assert result["active"]["take_profit_price"] == 160.23
    assert result["quick_start"] == {
        "used": True,
        "price_source": "FRESH_GMO_PUBLIC_TICKER",
        "stop_loss_pips": 15.0,
        "take_profit_pips": 22.5,
        "max_quote_age_seconds": 15,
        "broker_position_confirmed": False,
        "actual_fill_confirmed": False,
    }

    assert (
        service.close_exit_plan(
            reason=ManualExitReason.MANUAL,
            exit_price=160.01,
            now=now + timedelta(seconds=1),
        )["closed"]
        is True
    )
    sell_origin = now + timedelta(seconds=1)
    sell_signal = SignalView(
        horizon=Horizon.MINUTES_30,
        direction=Direction.SELL,
        status=SignalStatus.OK,
        p_up=0.38,
        p_down=0.62,
        reason="test sell",
        origin_time_utc=sell_origin.isoformat(),
        model_config_hash="sha256:test",
        forecast_id="quick_sell_forecast_test",
        recorded_mode="PROSPECTIVE",
    )
    assert service.ledger.record_forecast(sell_signal, recorded_at=sell_origin)
    assert service.ledger.record_realtime_tick(
        bid=159.990,
        ask=159.995,
        market_time_utc=sell_origin.isoformat(),
        sampled_at=sell_origin,
    )
    sell_result = service.quick_start_exit_plan(
        forecast_id="quick_sell_forecast_test",
        horizon=Horizon.MINUTES_30,
        direction=Direction.SELL,
        now=sell_origin,
    )
    assert sell_result["active"]["entry_price"] == 159.99
    assert sell_result["active"]["stop_loss_price"] == 160.14
    assert sell_result["active"]["take_profit_price"] == 159.765


def test_position_aware_exit_signal_requires_two_formal_reversals_and_hard_stop_wins(
    tmp_path,
) -> None:
    service = ManualSignalService(tmp_path, supplemental_h1_paths=())
    now = datetime(2026, 7, 15, 1, 0, tzinfo=UTC)

    def record_signal(offset_minutes: int, probability: float, forecast_id: str) -> SignalView:
        signal = SignalView(
            horizon=Horizon.MINUTES_10,
            direction=(
                Direction.BUY
                if probability >= 0.58
                else Direction.SELL
                if probability <= 0.42
                else Direction.NO_TRADE
            ),
            status=SignalStatus.OK,
            p_up=probability,
            p_down=1 - probability,
            reason="test",
            origin_time_utc=(now + timedelta(minutes=offset_minutes)).isoformat(),
            model_config_hash="sha256:exit-signal-test",
            forecast_id=forecast_id,
            recorded_mode="PROSPECTIVE",
        )
        assert service.ledger.record_forecast(signal, recorded_at=now)
        return signal

    initial = record_signal(-1, 0.64, "exit_initial")
    service.open_exit_plan(
        forecast_id=initial.forecast_id or "",
        horizon=Horizon.MINUTES_10,
        direction=Direction.BUY,
        entry_price=160.0,
        stop_loss_price=159.85,
        take_profit_price=160.225,
        now=now,
    )

    def record_price(at: datetime, bid: float) -> None:
        assert service.ledger.record_realtime_tick(
            bid=bid,
            ask=bid + 0.005,
            market_time_utc=at.isoformat(),
            sampled_at=at,
        )

    record_price(now, 160.0)
    assert service.exit_plan_status(now=now)["exit_signal"]["code"] == "CONTINUE_POSITION"

    record_signal(1, 0.49, "exit_warning")
    record_price(now + timedelta(minutes=1), 160.0)
    warning = service.exit_plan_status(now=now + timedelta(minutes=1))["exit_signal"]
    assert warning["code"] == "MODEL_EDGE_WARNING"
    assert warning["adverse_confirmation_count"] == 0

    record_signal(2, 0.40, "exit_adverse_1")
    record_price(now + timedelta(minutes=2), 160.0)
    first_reversal = service.exit_plan_status(now=now + timedelta(minutes=2))["exit_signal"]
    assert first_reversal["code"] == "MODEL_EDGE_WARNING"
    assert first_reversal["adverse_confirmation_count"] == 1

    record_signal(3, 0.41, "exit_adverse_2")
    record_price(now + timedelta(minutes=3), 160.0)
    candidate = service.exit_plan_status(now=now + timedelta(minutes=3))["exit_signal"]
    assert candidate["code"] == "MODEL_STOP_CANDIDATE"
    assert candidate["label"] == "損切り候補"
    assert candidate["adverse_confirmation_count"] == 2

    record_price(now + timedelta(minutes=4), 159.80)
    hard_stop = service.exit_plan_status(now=now + timedelta(minutes=4))["exit_signal"]
    assert hard_stop["code"] == "STOP_LOSS_REACHED"
    assert hard_stop["label"] == "損切り"


def test_position_aware_exit_signal_maps_take_profit_and_time_exit(tmp_path) -> None:
    now = datetime(2026, 7, 15, 2, 0, tzinfo=UTC)

    def opened_service(folder, forecast_id: str) -> ManualSignalService:
        service = ManualSignalService(folder, supplemental_h1_paths=())
        signal = SignalView(
            horizon=Horizon.MINUTES_10,
            direction=Direction.BUY,
            status=SignalStatus.OK,
            p_up=0.64,
            p_down=0.36,
            reason="test",
            origin_time_utc=(now - timedelta(minutes=1)).isoformat(),
            model_config_hash="sha256:exit-fixed-test",
            forecast_id=forecast_id,
            recorded_mode="PROSPECTIVE",
        )
        assert service.ledger.record_forecast(signal, recorded_at=now)
        service.open_exit_plan(
            forecast_id=forecast_id,
            horizon=Horizon.MINUTES_10,
            direction=Direction.BUY,
            entry_price=160.0,
            stop_loss_price=159.85,
            take_profit_price=160.225,
            now=now,
        )
        return service

    take_service = opened_service(tmp_path / "take", "take_forecast")
    assert take_service.ledger.record_realtime_tick(
        bid=160.23,
        ask=160.235,
        market_time_utc=now.isoformat(),
        sampled_at=now,
    )
    take_signal = take_service.exit_plan_status(now=now)["exit_signal"]
    assert take_signal["code"] == "TAKE_PROFIT_REACHED"
    assert take_signal["label"] == "利益確定"

    time_service = opened_service(tmp_path / "time", "time_forecast")
    after_target = now + timedelta(minutes=10)
    assert time_service.ledger.record_realtime_tick(
        bid=160.0,
        ask=160.005,
        market_time_utc=after_target.isoformat(),
        sampled_at=after_target,
    )
    time_signal = time_service.exit_plan_status(now=after_target)["exit_signal"]
    assert time_signal["code"] == "TIME_EXIT_DUE"
    assert time_signal["label"] == "時間切れ"


def test_chart_returns_real_cache_candles_and_aggregates_timeframes(tmp_path) -> None:
    m1 = _synthetic_frame(240, "min")
    now = pd.to_datetime(m1.iloc[-1]["time_utc"], utc=True).to_pydatetime() + timedelta(minutes=2)
    service = ManualSignalService(tmp_path, supplemental_h1_paths=())
    save_candle_csv(service.repository.m1_path, m1)

    one_minute = service.chart("1m", limit=60, now=now)
    ten_minutes = service.chart("10m", limit=60, now=now)
    assert one_minute["source"] == "GMO_PUBLIC_LOCAL_CACHE"
    assert one_minute["price_type"] == "BID"
    assert len(one_minute["candles"]) == 60
    assert 20 <= len(ten_minutes["candles"]) <= 25
    assert ten_minutes["candles"][-1]["high"] >= ten_minutes["candles"][-1]["low"]


def test_chart_rejects_unsupported_timeframe(tmp_path) -> None:
    service = ManualSignalService(tmp_path, supplemental_h1_paths=())
    try:
        service.chart("5s")
    except ValueError as error:
        assert "unsupported" in str(error)
    else:
        raise AssertionError("unsupported chart timeframe must fail closed")


def test_uninitialized_short_model_is_unknown_not_mocked(tmp_path) -> None:
    service = ManualSignalService(tmp_path, supplemental_h1_paths=())
    payload = service.current(now=datetime(2026, 7, 14, tzinfo=UTC), record=False)
    short = payload["signals"][:2]
    assert all(item["direction"] == "判定不可" for item in short)
    assert all(item["p_up"] is None for item in short)


def test_explicit_refresh_uses_fake_public_get_and_initializes_once(tmp_path, monkeypatch) -> None:
    class FakePublicClient:
        def fetch_candles(
            self,
            symbol: str,
            interval: str,
            limit: int = 200,
            *,
            price_type: str = "BID",
            date: str | None = None,
        ) -> list[Candle]:
            assert symbol == "USD_JPY"
            assert price_type == "BID"
            start = pd.Timestamp(date, tz="UTC")
            count = 100 if interval == "M1" else 20
            step = timedelta(minutes=1 if interval == "M1" else 60)
            return [
                Candle(
                    time=(start.to_pydatetime() + i * step).isoformat(),
                    open=155.0 + i * 0.001,
                    high=155.01 + i * 0.001,
                    low=154.99 + i * 0.001,
                    close=155.002 + i * 0.001 + (i % 3) * 0.0001,
                    volume=None,
                )
                for i in range(count)
            ]

    monkeypatch.setattr(data_module.time, "sleep", lambda _: None)
    service = ManualSignalService(tmp_path, supplemental_h1_paths=())
    now = datetime(2026, 7, 14, 23, 59, tzinfo=UTC)
    result = service.refresh(FakePublicClient(), now=now)
    assert result["refresh"]["m1_completed_rows"] > 2_000
    assert result["refresh"]["short_model_trained"] is True
    assert service.short_artifact_path.exists()

    second = service.refresh(FakePublicClient(), now=now)
    assert second["refresh"]["short_model_trained"] is False
