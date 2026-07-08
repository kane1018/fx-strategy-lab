"""No-POST tests for the backtest dataset schema, split, and adapters."""

from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

from app.services import gmo_strategy_backtest_dataset as module
from app.services.gmo_strategy_backtest_dataset import (
    DATA_ADAPTER_NOT_CONFIGURED,
    FutureBrokerExportHistoricalDataAdapter,
    FutureCsvHistoricalDataAdapter,
    GmoBacktestDatasetError,
    GmoBacktestDatasetStatus,
    SpreadCategorySafeLabel,
    SyntheticHistoricalDataAdapter,
    assert_no_lookahead_leakage,
    build_synthetic_trend_dataset,
    split_backtest_dataset_chronologically,
    validate_backtest_dataset,
)


def _valid_dataset():
    return build_synthetic_trend_dataset(direction_safe_label="UP", bars=60)


class TestDatasetValidation:
    def test_valid_synthetic_dataset_is_accepted(self) -> None:
        validation = validate_backtest_dataset(_valid_dataset())
        assert validation.status is (
            GmoBacktestDatasetStatus.DATASET_VALID_SYNTHETIC
        )
        assert validation.blocked_reasons == ()

    def test_non_monotonic_timestamp_is_blocked(self) -> None:
        dataset = _valid_dataset()
        candles = list(dataset.candles)
        candles[10] = replace(candles[10], timestamp=5)
        validation = validate_backtest_dataset(
            replace(dataset, candles=tuple(candles))
        )
        assert "DATASET_TIMESTAMP_NOT_MONOTONIC" in validation.blocked_reasons

    def test_duplicate_timestamp_is_blocked(self) -> None:
        dataset = _valid_dataset()
        candles = list(dataset.candles)
        candles[10] = replace(candles[10], timestamp=candles[9].timestamp)
        validation = validate_backtest_dataset(
            replace(dataset, candles=tuple(candles))
        )
        assert "DATASET_DUPLICATE_TIMESTAMP" in validation.blocked_reasons

    def test_missing_spread_record_is_blocked(self) -> None:
        dataset = _valid_dataset()
        validation = validate_backtest_dataset(
            replace(dataset, spreads=dataset.spreads[:-5])
        )
        assert "DATASET_SPREAD_RECORD_MISSING" in validation.blocked_reasons

    def test_missing_session_record_is_blocked(self) -> None:
        dataset = _valid_dataset()
        validation = validate_backtest_dataset(
            replace(dataset, sessions=dataset.sessions[:-5])
        )
        assert "DATASET_SESSION_RECORD_MISSING" in validation.blocked_reasons

    def test_spread_value_missing_for_known_category_is_blocked(self) -> None:
        dataset = _valid_dataset()
        spreads = list(dataset.spreads)
        spreads[0] = replace(spreads[0], spread_value=None)
        validation = validate_backtest_dataset(
            replace(dataset, spreads=tuple(spreads))
        )
        assert "DATASET_SPREAD_VALUE_MISSING" in validation.blocked_reasons

    def test_invalid_candle_range_is_blocked(self) -> None:
        dataset = _valid_dataset()
        candles = list(dataset.candles)
        candles[0] = replace(candles[0], high_value=0.0, low_value=1.0)
        validation = validate_backtest_dataset(
            replace(dataset, candles=tuple(candles))
        )
        assert "DATASET_CANDLE_RANGE_INVALID" in validation.blocked_reasons

    def test_non_synthetic_dataset_is_blocked_this_phase(self) -> None:
        validation = validate_backtest_dataset(
            replace(_valid_dataset(), synthetic_fixture=False)
        )
        assert (
            "DATASET_REAL_DATA_NOT_SUPPORTED_THIS_PHASE"
            in validation.blocked_reasons
        )

    def test_invalid_warmup_is_blocked(self) -> None:
        validation = validate_backtest_dataset(
            replace(_valid_dataset(), warmup_bars=1000)
        )
        assert "DATASET_WARMUP_INVALID" in validation.blocked_reasons

    def test_unknown_spread_category_without_value_is_allowed_shape(self) -> None:
        dataset = build_synthetic_trend_dataset(
            direction_safe_label="UP",
            bars=20,
            spread_category=SpreadCategorySafeLabel.SPREAD_CATEGORY_UNKNOWN,
        )
        validation = validate_backtest_dataset(dataset)
        # Shape-valid, but the engine blocks SPREAD_UNKNOWN before entry.
        assert validation.status is (
            GmoBacktestDatasetStatus.DATASET_VALID_SYNTHETIC
        )


class TestChronologicalSplit:
    def test_split_is_chronological_and_leak_free(self) -> None:
        split = split_backtest_dataset_chronologically(
            _valid_dataset(), train_bars=30, validation_bars=15
        )
        assert split.split_method_safe_label == "CHRONOLOGICAL_NO_SHUFFLE"
        assert split.random_shuffle_used is False
        assert split.oos_used_for_parameter_selection is False
        assert_no_lookahead_leakage(split)
        assert split.warmup_end < split.train_end < split.validation_end
        assert split.validation_end < split.oos_end

    def test_split_without_oos_segment_raises(self) -> None:
        with pytest.raises(GmoBacktestDatasetError):
            split_backtest_dataset_chronologically(
                _valid_dataset(), train_bars=40, validation_bars=30
            )

    def test_random_shuffle_flag_fails_leakage_check(self) -> None:
        split = split_backtest_dataset_chronologically(
            _valid_dataset(), train_bars=30, validation_bars=15
        )
        with pytest.raises(GmoBacktestDatasetError):
            assert_no_lookahead_leakage(
                replace(split, random_shuffle_used=True)
            )

    def test_oos_parameter_selection_flag_fails_leakage_check(self) -> None:
        split = split_backtest_dataset_chronologically(
            _valid_dataset(), train_bars=30, validation_bars=15
        )
        with pytest.raises(GmoBacktestDatasetError):
            assert_no_lookahead_leakage(
                replace(split, oos_used_for_parameter_selection=True)
            )


class TestAdapters:
    def test_synthetic_adapter_returns_its_dataset(self) -> None:
        dataset = _valid_dataset()
        assert SyntheticHistoricalDataAdapter(dataset).load_dataset() is dataset

    def test_future_csv_adapter_fails_closed(self) -> None:
        with pytest.raises(GmoBacktestDatasetError) as excinfo:
            FutureCsvHistoricalDataAdapter().load_dataset()
        assert DATA_ADAPTER_NOT_CONFIGURED in str(excinfo.value)

    def test_future_broker_export_adapter_fails_closed(self) -> None:
        with pytest.raises(GmoBacktestDatasetError) as excinfo:
            FutureBrokerExportHistoricalDataAdapter().load_dataset()
        assert DATA_ADAPTER_NOT_CONFIGURED in str(excinfo.value)


class TestModuleIsolation:
    def test_module_has_no_network_broker_or_env_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "requests" not in source
        assert "urllib" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "/private/v1" not in source
        assert "import random" not in source
