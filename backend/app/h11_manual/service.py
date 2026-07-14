"""Application service for the local three-horizon manual signal screen."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.h11_manual.contracts import (
    Direction,
    Horizon,
    ManualExitReason,
    RealtimeEstimateMode,
    RealtimeEstimateView,
    SignalStatus,
    SignalView,
    map_probability,
    reason_for_direction,
)
from app.h11_manual.data import DEFAULT_DATA_ROOT, CandleRepository, PublicCandleClient
from app.h11_manual.ledger import SignalLedger
from app.h11_manual.realtime import RollingFrameResult, build_rolling_feature_frame
from app.h11_manual.settlement_sync import (
    DisabledManualSettlementReadClient,
    ManualSettlementReadClient,
    ManualSettlementSyncError,
    SyncAvailability,
)
from app.h11_manual.short_model import (
    ShortModelArtifact,
    predict_short_model,
    train_short_model,
)
from app.strategies.h11_regime_moe import (
    H11_V2_CONFIG_HASH,
    H11PredictionStatus,
    H11V2Parameters,
    compute_features,
    predict_h11_v2,
)

PARAMETERS_V2_PATH = Path(__file__).resolve().parents[1] / "strategies" / "h11_parameters_v2.json"
QUICK_EXIT_STOP_PIPS = 15.0
QUICK_EXIT_TAKE_PIPS = 22.5
QUICK_EXIT_MAX_QUOTE_AGE_SECONDS = 15
JPY_PIP_SIZE = 0.01


class ManualSignalService:
    def __init__(
        self,
        data_root: Path = DEFAULT_DATA_ROOT,
        supplemental_h1_paths: tuple[Path, ...] | None = None,
        settlement_reader: ManualSettlementReadClient | None = None,
    ) -> None:
        self.data_root = data_root
        self.repository = (
            CandleRepository(data_root)
            if supplemental_h1_paths is None
            else CandleRepository(data_root, supplemental_h1_paths)
        )
        self.ledger = SignalLedger(data_root / "signal_ledger.sqlite3")
        self.short_artifact_path = data_root / "short_model_artifact.json"
        self.settlement_reader = settlement_reader or DisabledManualSettlementReadClient()

    def current(self, *, now: datetime | None = None, record: bool = True) -> dict[str, Any]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        signals = [
            self._short_signal(Horizon.MINUTES_10, current),
            self._short_signal(Horizon.MINUTES_30, current),
            self._h11_signal(current),
        ]
        if record:
            for signal in signals:
                self.ledger.record_forecast(signal, recorded_at=current)
            self.ledger.record_due_no_actions(now=current)
            self._resolve_available(current)
        latest_time = max(
            (signal.origin_time_utc for signal in signals if signal.origin_time_utc), default=None
        )
        return {
            "screen": "シグナル",
            "symbol": "USD/JPY",
            "updated_at_utc": current.isoformat(timespec="seconds"),
            "latest_market_time_utc": latest_time,
            "signals": [signal.to_dict() for signal in signals],
            "safety": self.safety_flags(),
        }

    def refresh(self, client: PublicCandleClient, *, now: datetime | None = None) -> dict[str, Any]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        counts = self.repository.refresh(client, now=current)
        trained = False
        if not self.short_artifact_path.exists():
            artifact = train_short_model(self.repository.load_m1(now=current), now=current)
            artifact.save(self.short_artifact_path)
            trained = True
        response = self.current(now=current)
        response["refresh"] = {**counts, "short_model_trained": trained}
        return response

    def history(self, limit: int = 100) -> dict[str, Any]:
        return {
            "forecasts": self.ledger.latest_forecasts(limit),
            "signal_actions": self.ledger.latest_signal_actions(limit),
        }

    def signal_series(self, limit: int = 120) -> dict[str, Any]:
        return {
            "status": "FORMAL_PROSPECTIVE_SERIES_WITH_SESSION_REALTIME_CLIENT_SERIES",
            "series": self.ledger.signal_probability_series(limit),
            "realtime_series_persistence": False,
            "realtime_validation_forecasts_persisted_separately": True,
        }

    def validation(self) -> dict[str, Any]:
        return {
            "status": "FORWARD_SIGNAL_SCORE_ONLY_NOT_EDGE_VALIDATION",
            "metrics": self.ledger.validation_summary(),
            "realtime_rolling": self.ledger.realtime_rolling_validation_summary(),
        }

    def open_exit_plan(
        self,
        *,
        forecast_id: str,
        horizon: Horizon,
        direction: Direction,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Record an operator-owned manual exit plan; never submit an order."""

        current = (now or datetime.now(UTC)).astimezone(UTC)
        if horizon not in (Horizon.MINUTES_10, Horizon.MINUTES_30):
            raise ValueError("24h is context only and cannot own a short-term exit plan")
        if direction not in (Direction.BUY, Direction.SELL):
            raise ValueError("manual trade direction must be explicitly buy or sell")
        if not np.isfinite([entry_price, stop_loss_price, take_profit_price]).all():
            raise ValueError("manual trade prices must be finite")
        if min(entry_price, stop_loss_price, take_profit_price) <= 0:
            raise ValueError("manual trade prices must be positive")
        if direction is Direction.BUY and not stop_loss_price < entry_price < take_profit_price:
            raise ValueError("buy plan requires stop < entry < take profit")
        if direction is Direction.SELL and not take_profit_price < entry_price < stop_loss_price:
            raise ValueError("sell plan requires take profit < entry < stop")
        forecast = self.ledger.forecast(forecast_id)
        if forecast is None or forecast["horizon"] != horizon.value:
            raise ValueError("formal forecast does not match the selected horizon")
        if forecast["recorded_mode"] != "PROSPECTIVE":
            raise ValueError("replayed forecast cannot own a manual exit plan")
        origin = datetime.fromisoformat(forecast["origin_time_utc"]).astimezone(UTC)
        target = origin + timedelta(minutes=horizon.bars)
        if current >= target:
            raise ValueError("formal forecast target time has already passed")
        plan_id = self.ledger.open_manual_trade_plan(
            forecast_id=forecast_id,
            horizon=horizon,
            direction=direction,
            signal_origin_utc=origin.isoformat(),
            target_time_utc=target.isoformat(),
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            opened_at=current,
        )
        result = self.exit_plan_status(now=current)
        result["opened"] = True
        result["plan_id"] = plan_id
        return result

    def quick_start_exit_plan(
        self,
        *,
        forecast_id: str,
        horizon: Horizon,
        direction: Direction,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Start the fixed local exit preset from a fresh Public quote; never trade."""

        current = (now or datetime.now(UTC)).astimezone(UTC)
        forecast = self.ledger.forecast(forecast_id)
        if forecast is None or forecast["horizon"] != horizon.value:
            raise ValueError("formal forecast does not match the selected horizon")
        if horizon not in (Horizon.MINUTES_10, Horizon.MINUTES_30):
            raise ValueError("quick exit start supports only 10m and 30m")
        if direction not in (Direction.BUY, Direction.SELL):
            raise ValueError("quick exit start requires a buy or sell signal")
        if forecast["direction"] != direction.value:
            raise ValueError("quick exit direction must match the formal forecast")

        tick = self.ledger.latest_realtime_tick()
        if tick is None:
            raise ValueError("fresh Public quote is unavailable")
        sampled_at = datetime.fromisoformat(str(tick["sample_time_utc"])).astimezone(UTC)
        market_time = datetime.fromisoformat(str(tick["market_time_utc"])).astimezone(UTC)
        sample_age = (current - sampled_at).total_seconds()
        market_age = (current - market_time).total_seconds()
        if not (
            -5 <= sample_age <= QUICK_EXIT_MAX_QUOTE_AGE_SECONDS
            and -5 <= market_age <= QUICK_EXIT_MAX_QUOTE_AGE_SECONDS
        ):
            raise ValueError("fresh Public quote is older than 15 seconds")

        entry_price = float(tick["ask"] if direction is Direction.BUY else tick["bid"])
        sign = 1 if direction is Direction.BUY else -1
        stop_loss_price = round(entry_price - sign * QUICK_EXIT_STOP_PIPS * JPY_PIP_SIZE, 6)
        take_profit_price = round(entry_price + sign * QUICK_EXIT_TAKE_PIPS * JPY_PIP_SIZE, 6)
        result = self.open_exit_plan(
            forecast_id=forecast_id,
            horizon=horizon,
            direction=direction,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            now=current,
        )
        if not self.ledger.record_manual_trade_quick_start(
            plan_id=int(result["plan_id"]),
            forecast_id=forecast_id,
            horizon=horizon,
            reference_entry_price=entry_price,
            started_at=current,
        ):
            raise ValueError("quick-start audit marker could not be recorded")
        result["quick_start"] = {
            "used": True,
            "price_source": "FRESH_GMO_PUBLIC_TICKER",
            "stop_loss_pips": QUICK_EXIT_STOP_PIPS,
            "take_profit_pips": QUICK_EXIT_TAKE_PIPS,
            "max_quote_age_seconds": QUICK_EXIT_MAX_QUOTE_AGE_SECONDS,
            "broker_position_confirmed": False,
            "actual_fill_confirmed": False,
        }
        result["signal_action"] = {
            "action": "TRADE_STARTED",
            "forecast_id": forecast_id,
            "recorded": True,
        }
        return result

    def synchronize_manual_settlements(
        self, *, now: datetime | None = None
    ) -> dict[str, Any]:
        """Read and apply manual OPEN/CLOSE facts; never submit or mutate an order."""

        current = (now or datetime.now(UTC)).astimezone(UTC)
        if self.settlement_reader.availability is SyncAvailability.NOT_CONFIGURED:
            self.ledger.record_broker_sync_failure(
                status="NOT_CONFIGURED",
                safe_error_code="BROKER_SYNC_NOT_CONFIGURED",
                source="DISABLED",
                attempted_at=current,
            )
            return {
                **self.ledger.broker_sync_overview(),
                "configured": False,
                "events": [],
                "active_plans": self.exit_plan_status(now=current)["active_plans"],
                "safety": self.broker_sync_safety_flags(actual_read=False),
            }
        try:
            snapshot = self.settlement_reader.fetch_snapshot(symbol="USD_JPY")
            result = self.ledger.apply_broker_sync_snapshot(
                executions=[
                    {
                        "execution_ref": row.execution_ref,
                        "position_ref": row.position_ref,
                        "settle_type": row.settle_type,
                        "symbol": row.symbol,
                        "side": row.side,
                        "size": str(row.size),
                        "price": str(row.price),
                        "executed_at_utc": row.executed_at_utc,
                    }
                    for row in snapshot.executions
                ],
                open_positions=[
                    {
                        "position_ref": row.position_ref,
                        "symbol": row.symbol,
                        "side": row.side,
                        "size": str(row.size),
                        "average_price": None
                        if row.average_price is None
                        else str(row.average_price),
                    }
                    for row in snapshot.open_positions
                ],
                source=snapshot.source,
                synced_at=current,
                stop_pips=QUICK_EXIT_STOP_PIPS,
                take_pips=QUICK_EXIT_TAKE_PIPS,
                pip_size=JPY_PIP_SIZE,
            )
        except (ManualSettlementSyncError, ValueError) as error:
            safe_code = (
                str(error)
                if isinstance(error, ManualSettlementSyncError)
                else "BROKER_SYNC_LOCAL_APPLY_ERROR"
            )
            self.ledger.record_broker_sync_failure(
                status="ERROR",
                safe_error_code=safe_code,
                source="GMO_FX_PRIVATE_GET_READONLY",
                attempted_at=current,
            )
            return {
                **self.ledger.broker_sync_overview(),
                "configured": True,
                "events": [],
                "active_plans": self.exit_plan_status(now=current)["active_plans"],
                "safety": self.broker_sync_safety_flags(actual_read=True),
            }
        result.update(
            {
                "configured": True,
                "active_plans": self.exit_plan_status(now=current)["active_plans"],
                "safety": self.broker_sync_safety_flags(
                    actual_read=snapshot.source == "GMO_FX_PRIVATE_GET_READONLY"
                ),
            }
        )
        return result

    def close_exit_plan(
        self,
        *,
        plan_id: int,
        reason: ManualExitReason,
        exit_price: float,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        if not np.isfinite(exit_price) or exit_price <= 0:
            raise ValueError("manual exit price must be positive and finite")
        active = self.ledger.active_manual_trade_plan(plan_id=plan_id)
        if active is None:
            raise ValueError("no open manual exit plan")
        if not self.ledger.close_manual_trade_plan(
            plan_id=int(active["plan_id"]),
            reason=reason,
            exit_price=exit_price,
            closed_at=current,
        ):
            raise ValueError("manual exit plan is no longer open")
        result = self.exit_plan_status(now=current)
        result["closed"] = True
        return result

    def correct_active_fill_price(
        self,
        *,
        plan_id: int,
        actual_fill_price: float,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Correct a quick-start reference price and keep its fixed pip distances."""

        current = (now or datetime.now(UTC)).astimezone(UTC)
        if not np.isfinite(actual_fill_price) or actual_fill_price <= 0:
            raise ValueError("actual fill price must be positive and finite")
        active = self.ledger.active_manual_trade_plan(plan_id=plan_id)
        if active is None:
            raise ValueError("no open manual exit plan")
        if not self.ledger.is_manual_trade_quick_start(int(active["plan_id"])):
            raise ValueError("actual fill correction supports quick-start plans only")
        direction = Direction(active["direction"])
        sign = 1 if direction is Direction.BUY else -1
        expected_stop = round(
            float(active["entry_price"]) - sign * QUICK_EXIT_STOP_PIPS * JPY_PIP_SIZE,
            6,
        )
        expected_take = round(
            float(active["entry_price"]) + sign * QUICK_EXIT_TAKE_PIPS * JPY_PIP_SIZE,
            6,
        )
        if not (
            np.isclose(float(active["stop_loss_price"]), expected_stop, rtol=0.0, atol=1e-6)
            and np.isclose(
                float(active["take_profit_price"]), expected_take, rtol=0.0, atol=1e-6
            )
        ):
            raise ValueError("actual fill correction supports the fixed quick-start preset only")
        corrected_stop = round(
            actual_fill_price - sign * QUICK_EXIT_STOP_PIPS * JPY_PIP_SIZE,
            6,
        )
        corrected_take = round(
            actual_fill_price + sign * QUICK_EXIT_TAKE_PIPS * JPY_PIP_SIZE,
            6,
        )
        if min(actual_fill_price, corrected_stop, corrected_take) <= 0:
            raise ValueError("corrected exit prices must remain positive")
        if not self.ledger.correct_active_manual_trade_fill(
            plan_id=int(active["plan_id"]),
            entry_price=actual_fill_price,
            stop_loss_price=corrected_stop,
            take_profit_price=corrected_take,
            corrected_at=current,
        ):
            raise ValueError("manual exit plan is no longer open")
        result = self.exit_plan_status(now=current)
        result["fill_correction"] = {
            "used": True,
            "actual_fill_price": actual_fill_price,
            "stop_loss_pips": QUICK_EXIT_STOP_PIPS,
            "take_profit_pips": QUICK_EXIT_TAKE_PIPS,
            "broker_fill_confirmed_by_api": False,
        }
        return result

    def exit_plan_status(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        broker_sync = self.ledger.broker_sync_overview()
        active_plans = self.ledger.active_manual_trade_plans()
        if not active_plans:
            return {
                "active": None,
                "active_plans": [],
                "open_position_count": 0,
                "exit_signal": {
                    "code": "NO_MANUAL_POSITION",
                    "label": "建玉なし",
                    "tone": "neutral",
                    "reason": "出口管理で開始した手動建玉計画はありません",
                    "latest_formal_p_up": None,
                    "adverse_confirmation_count": 0,
                    "required_confirmations": 2,
                },
                "history": self.ledger.manual_trade_history(),
                "automatic_exit": False,
                "broker_state_known": broker_sync["status"] == "SYNCED",
                "broker_sync": broker_sync,
            }
        plan_statuses = [
            self._single_exit_plan_status(active=active, current=current)
            for active in active_plans
        ]
        primary = plan_statuses[0]
        return {
            "active": primary["plan"],
            "active_plans": plan_statuses,
            "open_position_count": len(plan_statuses),
            "exit_signal": primary["exit_signal"],
            "history": self.ledger.manual_trade_history(),
            "automatic_exit": False,
            "broker_state_known": broker_sync["status"] == "SYNCED",
            "broker_sync": broker_sync,
        }

    def _single_exit_plan_status(
        self,
        *,
        active: dict[str, Any],
        current: datetime,
    ) -> dict[str, Any]:
        latest_tick = self.ledger.latest_realtime_tick()
        current_price: float | None = None
        price_is_fresh = False
        if latest_tick is not None:
            sampled_at = datetime.fromisoformat(latest_tick["sample_time_utc"]).astimezone(UTC)
            price_age_seconds = (current - sampled_at).total_seconds()
            price_is_fresh = -5 <= price_age_seconds <= 15
        if latest_tick is not None and price_is_fresh:
            current_price = float(
                latest_tick["bid"]
                if active["direction"] == Direction.BUY.value
                else latest_tick["ask"]
            )
        target = datetime.fromisoformat(active["target_time_utc"]).astimezone(UTC)
        stop_reached = False
        take_reached = False
        if current_price is not None and active["direction"] == Direction.BUY.value:
            stop_reached = current_price <= float(active["stop_loss_price"])
            take_reached = current_price >= float(active["take_profit_price"])
        elif current_price is not None:
            stop_reached = current_price >= float(active["stop_loss_price"])
            take_reached = current_price <= float(active["take_profit_price"])
        time_exit_due = current >= target
        horizon = Horizon(active["horizon"])
        formal = self.ledger.recent_prospective_forecasts(
            horizon,
            since_utc=active["signal_origin_utc"],
            limit=10,
        )
        latest_p_up = None if not formal else float(formal[0]["p_up"])
        is_buy = active["direction"] == Direction.BUY.value

        def adverse(row: dict[str, Any]) -> bool:
            probability = float(row["p_up"])
            return probability <= 0.42 if is_buy else probability >= 0.58

        adverse_count = 0
        for row in formal:
            if not adverse(row):
                break
            adverse_count += 1

        if stop_reached:
            exit_signal = {
                "code": "STOP_LOSS_REACHED",
                "label": "損切り",
                "tone": "danger",
                "reason": "現在価格が固定損切り価格へ到達しました",
            }
        elif take_reached:
            exit_signal = {
                "code": "TAKE_PROFIT_REACHED",
                "label": "利益確定",
                "tone": "profit",
                "reason": "現在価格が固定利益確定価格へ到達しました",
            }
        elif time_exit_due:
            exit_signal = {
                "code": "TIME_EXIT_DUE",
                "label": "時間切れ",
                "tone": "danger",
                "reason": "事前固定した予測対象時刻へ到達しました",
            }
        elif not price_is_fresh:
            exit_signal = {
                "code": "PRICE_UNKNOWN",
                "label": "判定不可",
                "tone": "unknown",
                "reason": "15秒以内のPublic価格を確認できません",
            }
        elif adverse_count >= 2:
            exit_signal = {
                "code": "MODEL_STOP_CANDIDATE",
                "label": "損切り候補",
                "tone": "danger",
                "reason": "反対方向の正式基準を2回連続で満たしました",
            }
        elif latest_p_up is None:
            exit_signal = {
                "code": "FORMAL_SIGNAL_UNKNOWN",
                "label": "判定不可",
                "tone": "unknown",
                "reason": "保有時間軸の正式シグナルを確認できません",
            }
        elif (is_buy and latest_p_up < 0.50) or (not is_buy and latest_p_up > 0.50):
            exit_signal = {
                "code": "MODEL_EDGE_WARNING",
                "label": "警戒",
                "tone": "warning",
                "reason": "保有方向の正式確率が50%の中立線を不利側へ越えました",
            }
        else:
            exit_signal = {
                "code": "CONTINUE_POSITION",
                "label": "継続",
                "tone": "continue",
                "reason": "固定出口未到達で、保有方向の優位性を維持しています",
            }
        exit_signal.update(
            {
                "latest_formal_p_up": latest_p_up,
                "adverse_confirmation_count": adverse_count,
                "required_confirmations": 2,
            }
        )
        if exit_signal["code"] in {
            "STOP_LOSS_REACHED",
            "TAKE_PROFIT_REACHED",
            "TIME_EXIT_DUE",
        }:
            state = "EXIT_ACTION_REQUIRED"
        elif exit_signal["code"] == "CONTINUE_POSITION":
            state = "ACTIVE"
        else:
            state = "EXIT_REVIEW_REQUIRED"
        enriched = {
            **active,
            "current_price": current_price,
            "latest_price_time_utc": None
            if latest_tick is None
            else latest_tick["sample_time_utc"],
            "remaining_seconds": max(0, int((target - current).total_seconds())),
            "stop_reached": stop_reached,
            "take_profit_reached": take_reached,
            "time_exit_due": time_exit_due,
            "display_state": state,
        }
        correction = self.ledger.manual_trade_fill_correction_summary(int(active["plan_id"]))
        enriched["actual_fill_correction_count"] = int(correction["correction_count"])
        enriched["actual_fill_corrected_at_utc"] = correction["corrected_at_utc"]
        enriched["quick_start"] = self.ledger.is_manual_trade_quick_start(
            int(active["plan_id"])
        )
        enriched["broker_sync"] = self.ledger.broker_plan_sync_status(
            int(active["plan_id"])
        )
        return {"plan": enriched, "exit_signal": exit_signal}

    def realtime_estimate(
        self,
        *,
        bid: float,
        ask: float,
        market_time_utc: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Record one Public ticker sample and return non-formal rolling estimates."""

        current = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
        if not np.isfinite([bid, ask]).all() or bid <= 0 or ask < bid:
            raise ValueError("invalid Public ticker values")
        try:
            market_time = datetime.fromisoformat(market_time_utc.replace("Z", "+00:00")).astimezone(
                UTC
            )
        except ValueError as error:
            raise ValueError("invalid Public ticker timestamp") from error
        age_seconds = (current - market_time).total_seconds()
        if age_seconds < -5 or age_seconds > 30:
            raise ValueError("stale or future Public ticker timestamp")
        resolutions = self.ledger.resolve_due_realtime_rolling_forecasts(
            observed_at=current,
            bid=bid,
            max_target_delay_seconds=15,
        )
        self.ledger.record_realtime_tick(
            bid=bid,
            ask=ask,
            market_time_utc=market_time.isoformat(timespec="milliseconds"),
            sampled_at=current,
        )
        ticks = pd.DataFrame(self.ledger.recent_realtime_ticks())
        rolling = build_rolling_feature_frame(self.repository.load_m1(now=current), ticks)
        estimates = [
            self._realtime_short_estimate(horizon, rolling, current)
            for horizon in (Horizon.MINUTES_10, Horizon.MINUTES_30)
        ]
        recorded_n = 0
        for estimate in estimates:
            if (
                estimate.status is not SignalStatus.OK
                or estimate.p_up is None
                or estimate.model_config_hash is None
                or estimate.estimate_time_utc is None
            ):
                continue
            recorded_n += int(
                self.ledger.record_realtime_rolling_forecast(
                    forecast_id=self._realtime_forecast_id(
                        estimate.horizon,
                        estimate.estimate_time_utc,
                        estimate.model_config_hash,
                    ),
                    horizon=estimate.horizon,
                    origin_time_utc=estimate.estimate_time_utc,
                    p_up=estimate.p_up,
                    direction=estimate.direction,
                    origin_bid=bid,
                    estimate_mode=estimate.estimate_mode.value,
                    model_config_hash=estimate.model_config_hash,
                    tick_native_window_ready=estimate.tick_native_window_ready,
                    recorded_at=current,
                )
            )
        return {
            "status": "REALTIME_ESTIMATE_NOT_FORMAL",
            "updated_at_utc": current.isoformat(),
            "estimates": [estimate.to_dict() for estimate in estimates],
            "collection": {
                "stored_sample_count": self.ledger.realtime_tick_count(),
                "recent_sample_count": rolling.sample_count,
                "recent_coverage_seconds": rolling.coverage_seconds,
                "tick_native_window_ready": rolling.tick_native_window_ready,
                "minimum_native_window_seconds": 31 * 60,
                "promotion_status": "REQUIRES_SEPARATE_VALIDATION_AND_OPERATOR_APPROVAL",
                "validation_forecasts_recorded_n": recorded_n,
                "validation_resolutions_this_tick": resolutions,
                "validation_target_max_delay_seconds": 15,
                "validation_ledger": "REALTIME_ROLLING_SEPARATE_LEDGER",
            },
            "safety": self.safety_flags(),
        }

    def chart(
        self,
        timeframe: str = "1m",
        *,
        limit: int = 180,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Return local-cache BID candles for the local chart only."""

        current = (now or datetime.now(UTC)).astimezone(UTC)
        safe_limit = max(30, min(limit, 500))
        if timeframe == "1h":
            frame = self.repository.load_h1(now=current)
        elif timeframe in {"1m", "10m", "30m"}:
            frame = self.repository.load_m1(now=current)
            minutes = {"1m": 1, "10m": 10, "30m": 30}[timeframe]
            if minutes > 1 and not frame.empty:
                frame = self._aggregate_chart_frame(frame, minutes)
        else:
            raise ValueError("unsupported chart timeframe")
        rows = frame.tail(safe_limit)
        candles = [
            {
                "time_utc": str(row.time_utc),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
            }
            for row in rows.itertuples(index=False)
        ]
        return {
            "symbol": "USD/JPY",
            "price_type": "BID",
            "timeframe": timeframe,
            "source": "GMO_PUBLIC_LOCAL_CACHE",
            "candles": candles,
        }

    @staticmethod
    def safety_flags() -> dict[str, bool]:
        return {
            "actual_post": False,
            "broker_read": False,
            "broker_write": False,
            "private_api": False,
            "credential_read": False,
            "env_read": False,
            "automatic_trade_authority": False,
        }

    @staticmethod
    def broker_sync_safety_flags(*, actual_read: bool) -> dict[str, bool]:
        return {
            "actual_post": False,
            "broker_read": actual_read,
            "broker_write": False,
            "private_api": actual_read,
            "credential_read": actual_read,
            "env_read": False,
            "raw_response_exposed": False,
            "real_id_exposed": False,
            "automatic_trade_authority": False,
        }

    @staticmethod
    def _aggregate_chart_frame(frame: pd.DataFrame, minutes: int) -> pd.DataFrame:
        indexed = frame.copy()
        indexed["time_utc"] = pd.to_datetime(indexed["time_utc"], utc=True)
        indexed = indexed.set_index("time_utc")
        rule = f"{minutes}min"
        aggregated = indexed.resample(rule, label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}
        )
        aggregated = aggregated.dropna().reset_index()
        aggregated["time_utc"] = aggregated["time_utc"].map(lambda value: value.isoformat())
        return aggregated

    def _short_signal(self, horizon: Horizon, now: datetime) -> SignalView:
        frame = self.repository.load_m1(now=now)
        if not self.short_artifact_path.exists():
            return self._blocked(horizon, "短期モデルの初期化が必要です")
        if frame.empty:
            return self._blocked(horizon, "M1データがありません")
        try:
            artifact = ShortModelArtifact.load(self.short_artifact_path)
            row = len(frame) - 1
            p_up = predict_short_model(artifact, frame, row, horizon)
        except (OSError, ValueError, json.JSONDecodeError):
            return self._blocked(horizon, "短期モデルまたはM1データを確認できません")
        origin = pd.to_datetime(frame.iloc[row]["time_utc"], utc=True).isoformat()
        return self._signal(horizon, p_up, origin, artifact.config_hash, now)

    def _realtime_short_estimate(
        self,
        horizon: Horizon,
        rolling: RollingFrameResult,
        now: datetime,
    ) -> RealtimeEstimateView:
        mode = (
            RealtimeEstimateMode.TICK_NATIVE
            if rolling.tick_native_window_ready
            else RealtimeEstimateMode.M1_BOOTSTRAP
        )
        if not self.short_artifact_path.exists() or rolling.frame.empty:
            return RealtimeEstimateView(
                horizon=horizon,
                direction=Direction.UNKNOWN,
                status=SignalStatus.BLOCKED,
                p_up=None,
                p_down=None,
                reason="1秒データまたは短期モデルを準備しています",
                estimate_time_utc=now.isoformat(),
                model_config_hash=None,
                estimate_mode=RealtimeEstimateMode.UNAVAILABLE,
                tick_native_window_ready=False,
            )
        try:
            artifact = ShortModelArtifact.load(self.short_artifact_path)
            p_up = predict_short_model(artifact, rolling.frame, len(rolling.frame) - 1, horizon)
        except (OSError, ValueError, json.JSONDecodeError):
            return RealtimeEstimateView(
                horizon=horizon,
                direction=Direction.UNKNOWN,
                status=SignalStatus.BLOCKED,
                p_up=None,
                p_down=None,
                reason="毎秒ローリング特徴量を計算できません",
                estimate_time_utc=now.isoformat(),
                model_config_hash=None,
                estimate_mode=RealtimeEstimateMode.UNAVAILABLE,
                tick_native_window_ready=False,
            )
        direction = map_probability(p_up)
        prefix = (
            "1秒データのみ" if rolling.tick_native_window_ready else "M1履歴を併用する蓄積中推定"
        )
        return RealtimeEstimateView(
            horizon=horizon,
            direction=direction,
            status=SignalStatus.OK,
            p_up=p_up,
            p_down=1.0 - p_up,
            reason=f"{prefix} · {reason_for_direction(direction)}",
            estimate_time_utc=now.isoformat(),
            model_config_hash=artifact.config_hash,
            estimate_mode=mode,
            tick_native_window_ready=rolling.tick_native_window_ready,
        )

    @staticmethod
    def _realtime_forecast_id(horizon: Horizon, origin: str, config_hash: str) -> str:
        digest = hashlib.sha256(
            f"realtime-rolling|{horizon.value}|{origin}|{config_hash}".encode()
        ).hexdigest()[:24]
        return f"rolling_{digest}"

    def _h11_signal(self, now: datetime) -> SignalView:
        horizon = Horizon.HOURS_24
        frame = self.repository.load_h1(now=now)
        if len(frame) < 650:
            return self._blocked(horizon, "H1データの履歴が不足しています")
        try:
            raw = json.loads(PARAMETERS_V2_PATH.read_text())
            if raw.get("config_hash") != H11_V2_CONFIG_HASH:
                return self._blocked(horizon, "24時間モデルの設定が一致しません")
            parameters = H11V2Parameters(trend_weights=tuple(raw["trend_weights"]))
            time_utc = pd.to_datetime(frame["time_utc"], utc=True)
            hour_jst = ((time_utc.dt.hour + 9) % 24).to_numpy(dtype=int)
            features = compute_features(
                frame["open"].to_numpy(dtype=float),
                frame["high"].to_numpy(dtype=float),
                frame["low"].to_numpy(dtype=float),
                frame["close"].to_numpy(dtype=float),
                hour_jst,
                np.zeros(len(frame), dtype=int),
            )
            row = len(frame) - 1
            if not features.eligible[row]:
                return self._blocked(horizon, "24時間モデルの特徴量が不足しています")
            prediction = predict_h11_v2(
                parameters, features.expert_features[row], features.regime_axes[row]
            )
            if prediction.prediction_status is not H11PredictionStatus.OK:
                return self._blocked(horizon, "24時間モデルが判定を停止しました")
            p_up = prediction.p_up
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return self._blocked(horizon, "24時間モデルまたはH1データを確認できません")
        origin = time_utc.iloc[row].isoformat()
        return self._signal(horizon, p_up, origin, H11_V2_CONFIG_HASH, now)

    def _signal(
        self,
        horizon: Horizon,
        p_up: float | None,
        origin: str,
        config_hash: str,
        now: datetime,
    ) -> SignalView:
        direction = map_probability(p_up)
        forecast_id = self._forecast_id(horizon, origin, config_hash)
        origin_dt = datetime.fromisoformat(origin).astimezone(UTC)
        elapsed_minutes = (now - origin_dt).total_seconds() / 60
        horizon_minutes = horizon.bars * (60 if horizon.interval == "H1" else 1)
        mode = "PROSPECTIVE" if elapsed_minutes < horizon_minutes else "REPLAYED_AFTER_MATURITY"
        return SignalView(
            horizon=horizon,
            direction=direction,
            status=SignalStatus.OK,
            p_up=p_up,
            p_down=None if p_up is None else 1.0 - p_up,
            reason=reason_for_direction(direction),
            origin_time_utc=origin,
            model_config_hash=config_hash,
            forecast_id=forecast_id,
            recorded_mode=mode,
        )

    @staticmethod
    def _blocked(horizon: Horizon, reason: str) -> SignalView:
        return SignalView(
            horizon=horizon,
            direction=Direction.UNKNOWN,
            status=SignalStatus.BLOCKED,
            p_up=None,
            p_down=None,
            reason=reason,
            origin_time_utc=None,
            model_config_hash=None,
        )

    @staticmethod
    def _forecast_id(horizon: Horizon, origin: str, config_hash: str) -> str:
        source = f"{horizon.value}|{origin}|{config_hash}".encode()
        return "forecast_" + hashlib.sha256(source).hexdigest()[:24]

    def _resolve_available(self, now: datetime) -> None:
        frames = {"M1": self.repository.load_m1(now=now), "H1": self.repository.load_h1(now=now)}
        for forecast in self.ledger.unresolved():
            try:
                horizon = Horizon(forecast["horizon"])
                frame = frames[horizon.interval]
                times = pd.to_datetime(frame["time_utc"], utc=True)
                origin = pd.to_datetime(forecast["origin_time_utc"], utc=True)
                matches = np.flatnonzero((times == origin).to_numpy())
                if not len(matches):
                    continue
                target_row = int(matches[0]) + horizon.bars
                if target_row >= len(frame):
                    continue
                origin_close = float(frame.iloc[int(matches[0])]["close"])
                target_close = float(frame.iloc[target_row]["close"])
                if target_close == origin_close:
                    continue
                self.ledger.resolve(
                    forecast["forecast_id"],
                    outcome_up=target_close > origin_close,
                    target_time_utc=times.iloc[target_row].isoformat(),
                    resolved_at=now,
                )
            except (KeyError, ValueError):
                continue
