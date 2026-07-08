"""Backtest dataset schema, validation, chronological split, and adapters.

No-POST, synthetic-fixture-only phase. This module defines the dataset shape
a future real-data backtest will need, validates it fail-closed, and splits
it chronologically (never randomly). It performs no network access, no
broker access, no credential/env read, and no file download; the only data
that exists here is deterministic synthetic fixture data built in-process.

Numeric OHLC/spread values are SYNTHETIC TEST-ONLY values: they are never
broker values, never live values, and the report layer only ever exposes
aggregates -- per-bar prices are not part of any report surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

SYNTHETIC_SOURCE_LABEL = "SYNTHETIC_FIXTURE_SOURCE"
SUPPORTED_SYMBOL_SAFE_LABELS = ("USD_JPY",)
SUPPORTED_TIMEFRAME_SAFE_LABELS = ("M1", "M5", "M15", "H1")


class GmoBacktestDatasetError(RuntimeError):
    """Raised for fail-closed dataset violations. Never echoes row values."""


class SpreadCategorySafeLabel(str, Enum):
    SPREAD_CATEGORY_NORMAL = "SPREAD_CATEGORY_NORMAL"
    SPREAD_CATEGORY_WIDE = "SPREAD_CATEGORY_WIDE"
    SPREAD_CATEGORY_UNKNOWN = "SPREAD_CATEGORY_UNKNOWN"


class SessionAllowedSafeLabel(str, Enum):
    SESSION_ALLOWED = "SESSION_ALLOWED"
    SESSION_BLOCKED = "SESSION_BLOCKED"
    SESSION_UNKNOWN = "SESSION_UNKNOWN"


@dataclass(frozen=True)
class BacktestCandleRecord:
    """One synthetic OHLC bar. ``timestamp`` is a synthetic monotonic tick."""

    timestamp: int
    symbol_safe_label: str
    timeframe_safe_label: str
    open_value: float
    high_value: float
    low_value: float
    close_value: float
    volume_value: float | None = None
    source_label: str = SYNTHETIC_SOURCE_LABEL
    synthetic_fixture: bool = True


@dataclass(frozen=True)
class BacktestSpreadRecord:
    """Per-bar spread. ``spread_value`` is synthetic test-only, never broker."""

    timestamp: int
    symbol_safe_label: str
    spread_category: SpreadCategorySafeLabel
    spread_value: float | None = None
    source_label: str = SYNTHETIC_SOURCE_LABEL
    synthetic_fixture: bool = True


@dataclass(frozen=True)
class BacktestSessionRecord:
    """Per-bar session allowance label."""

    timestamp: int
    session_safe_label: SessionAllowedSafeLabel
    source_label: str = SYNTHETIC_SOURCE_LABEL
    synthetic_fixture: bool = True


class GmoBacktestDatasetStatus(str, Enum):
    DATASET_VALID_SYNTHETIC = "DATASET_VALID_SYNTHETIC"
    DATASET_INVALID_BLOCKED = "DATASET_INVALID_BLOCKED"
    DATASET_NOT_CONFIGURED = "DATASET_NOT_CONFIGURED"


@dataclass(frozen=True)
class BacktestDataset:
    """One aligned synthetic dataset (candles + spreads + sessions)."""

    symbol_safe_label: str
    timeframe_safe_label: str
    candles: tuple[BacktestCandleRecord, ...]
    spreads: tuple[BacktestSpreadRecord, ...]
    sessions: tuple[BacktestSessionRecord, ...]
    warmup_bars: int = 3
    synthetic_fixture: bool = True

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class BacktestDatasetValidation:
    status: GmoBacktestDatasetStatus
    blocked_reasons: tuple[str, ...]

    def __bool__(self) -> bool:
        return False


def validate_backtest_dataset(dataset: BacktestDataset) -> BacktestDatasetValidation:
    """Fail-closed dataset validation. Reasons are safe labels only."""

    reasons: list[str] = []
    if not dataset.synthetic_fixture:
        # Real data enters only through a future, explicitly reviewed
        # adapter step; in this phase a non-synthetic dataset is blocked.
        reasons.append("DATASET_REAL_DATA_NOT_SUPPORTED_THIS_PHASE")
    if dataset.symbol_safe_label not in SUPPORTED_SYMBOL_SAFE_LABELS:
        reasons.append("DATASET_SYMBOL_NOT_SUPPORTED")
    if dataset.timeframe_safe_label not in SUPPORTED_TIMEFRAME_SAFE_LABELS:
        reasons.append("DATASET_TIMEFRAME_NOT_SUPPORTED")
    if not dataset.candles:
        reasons.append("DATASET_CANDLES_MISSING")
    if dataset.warmup_bars < 0 or (
        dataset.candles and dataset.warmup_bars >= len(dataset.candles)
    ):
        reasons.append("DATASET_WARMUP_INVALID")

    previous_ts: int | None = None
    for candle in dataset.candles:
        if not candle.synthetic_fixture:
            reasons.append("DATASET_CANDLE_NOT_SYNTHETIC")
            break
        for field_value in (
            candle.open_value,
            candle.high_value,
            candle.low_value,
            candle.close_value,
        ):
            if not isinstance(field_value, int | float):
                reasons.append("DATASET_CANDLE_FIELD_MISSING_OR_INVALID")
                break
        if candle.high_value < candle.low_value:
            reasons.append("DATASET_CANDLE_RANGE_INVALID")
            break
        if previous_ts is not None:
            if candle.timestamp == previous_ts:
                reasons.append("DATASET_DUPLICATE_TIMESTAMP")
                break
            if candle.timestamp < previous_ts:
                reasons.append("DATASET_TIMESTAMP_NOT_MONOTONIC")
                break
        previous_ts = candle.timestamp

    candle_timestamps = [candle.timestamp for candle in dataset.candles]
    spread_timestamps = {record.timestamp for record in dataset.spreads}
    session_timestamps = {record.timestamp for record in dataset.sessions}
    if any(ts not in spread_timestamps for ts in candle_timestamps):
        # Spread-included evaluation is mandatory: a bar without a spread
        # record cannot be officially evaluated.
        reasons.append("DATASET_SPREAD_RECORD_MISSING")
    if any(ts not in session_timestamps for ts in candle_timestamps):
        reasons.append("DATASET_SESSION_RECORD_MISSING")
    for record in dataset.spreads:
        if (
            record.spread_category
            is not SpreadCategorySafeLabel.SPREAD_CATEGORY_UNKNOWN
            and record.spread_value is None
        ):
            reasons.append("DATASET_SPREAD_VALUE_MISSING")
            break

    unique_reasons = tuple(dict.fromkeys(reasons))
    return BacktestDatasetValidation(
        status=(
            GmoBacktestDatasetStatus.DATASET_VALID_SYNTHETIC
            if not unique_reasons
            else GmoBacktestDatasetStatus.DATASET_INVALID_BLOCKED
        ),
        blocked_reasons=unique_reasons,
    )


# ---------------------------------------------------------------------------
# Chronological split (never random)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChronologicalSplit:
    """Index ranges over the candle sequence, in strict chronological order.

    Warmup bars precede the train range and are excluded from evaluation.
    Out-of-sample is the final segment and must never be used for parameter
    selection (policy fixed in the report layer and docs).
    """

    warmup_end: int
    train_end: int
    validation_end: int
    oos_end: int
    split_method_safe_label: str = "CHRONOLOGICAL_NO_SHUFFLE"
    random_shuffle_used: bool = False
    oos_used_for_parameter_selection: bool = False

    def __bool__(self) -> bool:
        return False


def split_backtest_dataset_chronologically(
    dataset: BacktestDataset,
    *,
    train_bars: int,
    validation_bars: int,
) -> ChronologicalSplit:
    """Split candles into warmup / train / validation / OOS, in order.

    Raises fail-closed when the requested segments do not fit; the error
    carries no row values.
    """

    total = len(dataset.candles)
    warmup_end = dataset.warmup_bars
    train_end = warmup_end + train_bars
    validation_end = train_end + validation_bars
    if train_bars <= 0 or validation_bars <= 0:
        raise GmoBacktestDatasetError("split segments must be positive")
    if validation_end >= total:
        raise GmoBacktestDatasetError(
            "split does not leave an out-of-sample segment"
        )
    return ChronologicalSplit(
        warmup_end=warmup_end,
        train_end=train_end,
        validation_end=validation_end,
        oos_end=total,
    )


def assert_no_lookahead_leakage(split: ChronologicalSplit) -> None:
    """Raise unless segment boundaries are strictly ordered (no leakage)."""

    if not (
        0
        <= split.warmup_end
        < split.train_end
        < split.validation_end
        < split.oos_end
    ):
        raise GmoBacktestDatasetError("split boundaries are not chronological")
    if split.random_shuffle_used:
        raise GmoBacktestDatasetError("random shuffle is forbidden")
    if split.oos_used_for_parameter_selection:
        raise GmoBacktestDatasetError(
            "out-of-sample must not be used for parameter selection"
        )


# ---------------------------------------------------------------------------
# Adapters: synthetic now; real data adapters are design-only and fail closed
# ---------------------------------------------------------------------------

DATA_ADAPTER_NOT_CONFIGURED = "DATA_ADAPTER_NOT_CONFIGURED"


class HistoricalDataAdapter(Protocol):
    """Future-facing dataset source interface. Synthetic-only this phase."""

    def load_dataset(self) -> BacktestDataset:
        """Return one validated-shape dataset. Never performs network I/O."""


@dataclass(frozen=True)
class SyntheticHistoricalDataAdapter:
    """The only working adapter in this phase: returns its fixture dataset."""

    dataset: BacktestDataset

    def load_dataset(self) -> BacktestDataset:
        return self.dataset


@dataclass(frozen=True)
class FutureCsvHistoricalDataAdapter:
    """Design-only local CSV adapter skeleton. Fail-closed: not configured.

    A future step will implement local CSV loading (required columns:
    timestamp with explicit timezone policy, OHLC, spread, session label)
    with validation through ``validate_backtest_dataset``. Until that
    reviewed step, loading always fails closed. No download surface exists.
    """

    csv_path_design_note: str = "LOCAL_FILE_ONLY_NO_DOWNLOAD"

    def load_dataset(self) -> BacktestDataset:
        raise GmoBacktestDatasetError(DATA_ADAPTER_NOT_CONFIGURED)


@dataclass(frozen=True)
class FutureBrokerExportHistoricalDataAdapter:
    """Design-only broker-export adapter. Fail-closed: not configured.

    A future step may load operator-exported files (never a live broker
    connection from this code path). Until then, loading always fails
    closed.
    """

    export_design_note: str = "OPERATOR_EXPORTED_FILE_ONLY_NO_BROKER_CONNECTION"

    def load_dataset(self) -> BacktestDataset:
        raise GmoBacktestDatasetError(DATA_ADAPTER_NOT_CONFIGURED)


# ---------------------------------------------------------------------------
# Deterministic synthetic fixture builders (test/demo only)
# ---------------------------------------------------------------------------


def build_synthetic_trend_dataset(
    *,
    direction_safe_label: str,
    bars: int = 60,
    base_value: float = 100.0,
    step_value: float = 0.05,
    spread_value: float = 0.002,
    spread_category: SpreadCategorySafeLabel = (
        SpreadCategorySafeLabel.SPREAD_CATEGORY_NORMAL
    ),
    session_safe_label: SessionAllowedSafeLabel = (
        SessionAllowedSafeLabel.SESSION_ALLOWED
    ),
    warmup_bars: int = 3,
) -> BacktestDataset:
    """Build a deterministic synthetic dataset. Values are test-only.

    ``direction_safe_label``: "UP" (rising closes), "DOWN" (falling), or
    "FLAT" (constant closes).
    """

    if direction_safe_label not in ("UP", "DOWN", "FLAT"):
        raise GmoBacktestDatasetError("unsupported synthetic direction label")
    candles: list[BacktestCandleRecord] = []
    spreads: list[BacktestSpreadRecord] = []
    sessions: list[BacktestSessionRecord] = []
    value = base_value
    for index in range(bars):
        if direction_safe_label == "UP":
            delta = step_value
        elif direction_safe_label == "DOWN":
            delta = -step_value
        else:
            delta = 0.0
        open_value = value
        close_value = value + delta
        high_value = max(open_value, close_value) + abs(step_value) * 0.5
        low_value = min(open_value, close_value) - abs(step_value) * 0.5
        candles.append(
            BacktestCandleRecord(
                timestamp=index,
                symbol_safe_label="USD_JPY",
                timeframe_safe_label="M5",
                open_value=open_value,
                high_value=high_value,
                low_value=low_value,
                close_value=close_value,
            )
        )
        spreads.append(
            BacktestSpreadRecord(
                timestamp=index,
                symbol_safe_label="USD_JPY",
                spread_category=spread_category,
                spread_value=(
                    spread_value
                    if spread_category
                    is not SpreadCategorySafeLabel.SPREAD_CATEGORY_UNKNOWN
                    else None
                ),
            )
        )
        sessions.append(
            BacktestSessionRecord(
                timestamp=index, session_safe_label=session_safe_label
            )
        )
        value = close_value
    return BacktestDataset(
        symbol_safe_label="USD_JPY",
        timeframe_safe_label="M5",
        candles=tuple(candles),
        spreads=tuple(spreads),
        sessions=tuple(sessions),
        warmup_bars=warmup_bars,
    )
