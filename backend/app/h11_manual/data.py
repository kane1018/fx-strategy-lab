"""Local candle cache and explicitly invoked Public-GET refresh support."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol

import pandas as pd

from app.shadow.models import Candle

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = BACKEND_ROOT / "market_data" / "h11_manual"
H1_DEVELOPMENT_CACHE = BACKEND_ROOT / "market_data" / "usdjpy_h1_dev_bid.csv"
H1_STAGE1_CACHE = BACKEND_ROOT / "market_data" / "usdjpy_h1_stage1_bid.csv"


class PublicCandleClient(Protocol):
    def fetch_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 200,
        *,
        price_type: str = "BID",
        date: str | None = None,
    ) -> list[Candle]: ...


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["time_utc", "open", "high", "low", "close"])


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["time_utc", "open", "high", "low", "close"]
    if frame.empty:
        return _empty_frame()
    if not set(required).issubset(frame.columns):
        raise ValueError("candle cache is missing required columns")
    result = frame[required].copy()
    result["time_utc"] = pd.to_datetime(result["time_utc"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna().sort_values("time_utc").drop_duplicates("time_utc", keep="last")
    result["time_utc"] = result["time_utc"].map(lambda value: value.isoformat())
    return result.reset_index(drop=True)


def _merge(frames: list[pd.DataFrame]) -> pd.DataFrame:
    populated = [frame for frame in frames if not frame.empty]
    return _empty_frame() if not populated else _normalize(pd.concat(populated, ignore_index=True))


def load_candle_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return _empty_frame()
    return _normalize(pd.read_csv(path))


def save_candle_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    _normalize(frame).to_csv(temp, index=False)
    temp.replace(path)


def candles_to_frame(candles: list[Candle]) -> pd.DataFrame:
    return _normalize(
        pd.DataFrame(
            [
                {
                    "time_utc": candle.time,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                }
                for candle in candles
            ]
        )
    )


class CandleRepository:
    """Caches Public BID candles locally; it has no credential or Private API surface."""

    def __init__(
        self,
        data_root: Path = DEFAULT_DATA_ROOT,
        supplemental_h1_paths: tuple[Path, ...] = (H1_DEVELOPMENT_CACHE, H1_STAGE1_CACHE),
    ) -> None:
        self.data_root = data_root
        self.m1_path = data_root / "usdjpy_m1_bid.csv"
        self.h1_path = data_root / "usdjpy_h1_bid.csv"
        self.supplemental_h1_paths = supplemental_h1_paths

    def load_m1(self, *, now: datetime | None = None) -> pd.DataFrame:
        return self._completed(load_candle_csv(self.m1_path), minutes=1, now=now)

    def load_h1(self, *, now: datetime | None = None) -> pd.DataFrame:
        frames = [load_candle_csv(self.h1_path)]
        for path in self.supplemental_h1_paths:
            if path.exists():
                frames.append(load_candle_csv(path))
        merged = _merge(frames)
        return self._completed(merged, minutes=60, now=now)

    @staticmethod
    def _completed(frame: pd.DataFrame, *, minutes: int, now: datetime | None) -> pd.DataFrame:
        if frame.empty:
            return frame
        current = (now or datetime.now(UTC)).astimezone(UTC)
        opened = pd.to_datetime(frame["time_utc"], utc=True)
        return frame[opened + pd.Timedelta(minutes=minutes) <= current].reset_index(drop=True)

    def refresh(
        self,
        client: PublicCandleClient,
        *,
        now: datetime | None = None,
        initial_calendar_days: int = 45,
    ) -> dict[str, int]:
        """Fetch public BID klines once per requested date, then atomically merge.

        This method is only called by the operator's local `データを更新` action.
        There is no automatic retry or background loop.
        """

        current = (now or datetime.now(UTC)).astimezone(UTC)
        m1 = load_candle_csv(self.m1_path)
        h1 = load_candle_csv(self.h1_path)
        start = self._refresh_start(m1, current.date(), initial_calendar_days)
        fetched_m1: list[pd.DataFrame] = []
        day = start
        while day <= current.date():
            try:
                candles = client.fetch_candles(
                    "USD_JPY", "M1", limit=0, price_type="BID", date=day.strftime("%Y%m%d")
                )
            except Exception as error:
                # Empty weekends/holidays are expected; all other Public errors fail closed.
                if "no klines" not in str(error):
                    raise
            else:
                fetched_m1.append(candles_to_frame(candles))
            day += timedelta(days=1)
            time.sleep(0.15)

        try:
            h1_candles = client.fetch_candles(
                "USD_JPY",
                "H1",
                limit=0,
                price_type="BID",
                date=current.strftime("%Y%m%d"),
            )
        except Exception as error:
            if "no klines" not in str(error):
                raise
        else:
            h1 = _merge([h1, candles_to_frame(h1_candles)])
            save_candle_csv(self.h1_path, h1)

        if fetched_m1:
            m1 = _merge([m1, *fetched_m1])
            save_candle_csv(self.m1_path, m1)
        return {
            "m1_completed_rows": len(self.load_m1(now=current)),
            "h1_completed_rows": len(self.load_h1(now=current)),
        }

    @staticmethod
    def _refresh_start(frame: pd.DataFrame, today: date, initial_days: int) -> date:
        if frame.empty:
            return today - timedelta(days=max(1, min(initial_days, 90)))
        latest = pd.to_datetime(frame["time_utc"], utc=True).max().date()
        return max(latest - timedelta(days=1), today - timedelta(days=90))
