"""Display and persistence contracts for the local manual-signal UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

BUY_THRESHOLD = 0.58
SELL_THRESHOLD = 0.42


class Horizon(str, Enum):
    MINUTES_10 = "10m"
    MINUTES_30 = "30m"
    HOURS_24 = "24h"

    @property
    def label(self) -> str:
        return {"10m": "10分", "30m": "30分", "24h": "24時間"}[self.value]

    @property
    def bars(self) -> int:
        return {"10m": 10, "30m": 30, "24h": 24}[self.value]

    @property
    def interval(self) -> str:
        return "H1" if self is Horizon.HOURS_24 else "M1"


class Direction(str, Enum):
    BUY = "買い"
    SELL = "売り"
    NO_TRADE = "見送り"
    UNKNOWN = "判定不可"


class SignalStatus(str, Enum):
    OK = "OK"
    BLOCKED = "BLOCKED"


class RealtimeEstimateMode(str, Enum):
    M1_BOOTSTRAP = "M1_BOOTSTRAP_ROLLING_60S"
    TICK_NATIVE = "TICK_NATIVE_ROLLING_60S"
    UNAVAILABLE = "UNAVAILABLE"


class OperatorDecision(str, Enum):
    TRADED = "取引した"
    SKIPPED = "見送った"
    PENDING = "保留"


class ManualExitReason(str, Enum):
    STOP_LOSS = "損切り"
    TAKE_PROFIT = "利益確定"
    TIME_EXIT = "時間切れ"
    MANUAL = "手動終了"
    ABNORMAL = "異常終了"


@dataclass(frozen=True)
class SignalView:
    horizon: Horizon
    direction: Direction
    status: SignalStatus
    p_up: float | None
    p_down: float | None
    reason: str
    origin_time_utc: str | None
    model_config_hash: str | None
    forecast_id: str | None = None
    recorded_mode: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["horizon"] = self.horizon.value
        result["horizon_label"] = self.horizon.label
        result["direction"] = self.direction.value
        result["status"] = self.status.value
        return result


@dataclass(frozen=True)
class RealtimeEstimateView:
    horizon: Horizon
    direction: Direction
    status: SignalStatus
    p_up: float | None
    p_down: float | None
    reason: str
    estimate_time_utc: str | None
    model_config_hash: str | None
    estimate_mode: RealtimeEstimateMode
    tick_native_window_ready: bool
    formal_signal: bool = False
    promotion_eligible: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["horizon"] = self.horizon.value
        result["horizon_label"] = self.horizon.label
        result["direction"] = self.direction.value
        result["status"] = self.status.value
        result["estimate_mode"] = self.estimate_mode.value
        return result


def map_probability(p_up: float | None, *, blocked: bool = False) -> Direction:
    if blocked or p_up is None:
        return Direction.UNKNOWN
    if p_up >= BUY_THRESHOLD:
        return Direction.BUY
    if p_up <= SELL_THRESHOLD:
        return Direction.SELL
    return Direction.NO_TRADE


def reason_for_direction(direction: Direction) -> str:
    return {
        Direction.BUY: "上昇確率が買い基準を上回っています",
        Direction.SELL: "上昇確率が売り基準を下回っています",
        Direction.NO_TRADE: "確率が見送り帯の内側です",
        Direction.UNKNOWN: "必要なモデルまたは市場データを確認できません",
    }[direction]
