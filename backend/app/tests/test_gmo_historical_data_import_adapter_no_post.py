"""No-POST tests for the local CSV historical data import adapter.

All CSV files here are synthetic temporary fixtures created inside tmp_path.
No real data file exists or is read; no network surface exists.
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from pathlib import Path

from app.services import gmo_historical_data_import_adapter as module
from app.services.gmo_historical_data_import_adapter import (
    NOT_TICK_LEVEL_LABEL,
    SPREAD_FROM_BID_ASK_LABEL,
    CsvImportIntakeCategory,
    HistoricalCsvImportRequest,
    import_historical_csv,
)
from app.services.gmo_strategy_backtest_dataset import (
    GmoBacktestDatasetStatus,
    validate_backtest_dataset,
)

_BASE_TS = 1_750_000_000_000  # synthetic epoch-ms fixture base (test-only)
_STEP_MS = 300_000  # 5 minutes

_COMBINED_HEADER = (
    "timestamp,symbol,timeframe,open,high,low,close,spread,source_label"
)
_OHLC_ONLY_HEADER = "timestamp,symbol,timeframe,open,high,low,close,source_label"


def _combined_rows(count: int = 8, *, spread: str = "0.003") -> list[str]:
    rows = []
    for index in range(count):
        ts = _BASE_TS + index * _STEP_MS
        rows.append(
            f"{ts},USD_JPY,M5,100.0,100.2,99.9,100.1,{spread},SYNTHETIC_TEST"
        )
    return rows


def _write(path: Path, header: str, rows: list[str]) -> str:
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return str(path)


def _side_rows(count: int = 8, *, offset: float = 0.0) -> list[str]:
    rows = []
    for index in range(count):
        ts = _BASE_TS + index * _STEP_MS
        base = 100.0 + offset
        rows.append(
            f"{ts},USD_JPY,M5,{base},{base + 0.2},{base - 0.1},{base + 0.1},"
            "SYNTHETIC_TEST"
        )
    return rows


class TestAdapterConfiguration:
    def test_no_path_provided_fails_closed_not_configured(self) -> None:
        result = import_historical_csv(HistoricalCsvImportRequest())
        assert result.intake_category is (
            CsvImportIntakeCategory.DATA_ADAPTER_NOT_CONFIGURED_CATEGORY
        )
        assert result.dataset is None
        assert not result

    def test_remote_url_path_is_blocked_before_read(self) -> None:
        result = import_historical_csv(
            HistoricalCsvImportRequest(
                combined_csv_path="https://example.invalid/data.csv"
            )
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_REMOTE_PATH
        )

    def test_scheme_prefixed_path_is_blocked(self) -> None:
        for path in ("s3://bucket/data.csv", "ftp://host/data.csv", "file:///x.csv"):
            result = import_historical_csv(
                HistoricalCsvImportRequest(combined_csv_path=path)
            )
            assert result.intake_category is (
                CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_REMOTE_PATH
            )

    def test_directory_path_is_blocked_no_auto_discovery(self, tmp_path) -> None:
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=str(tmp_path))
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_UNSUPPORTED_FORMAT
        )

    def test_missing_file_is_not_provided(self, tmp_path) -> None:
        result = import_historical_csv(
            HistoricalCsvImportRequest(
                combined_csv_path=str(tmp_path / "missing.csv")
            )
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_NOT_PROVIDED
        )

    def test_non_csv_extension_is_blocked(self, tmp_path) -> None:
        path = tmp_path / "data.parquet"
        path.write_text("x", encoding="utf-8")
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=str(path))
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_UNSUPPORTED_FORMAT
        )

    def test_combined_and_pair_modes_are_mutually_exclusive(self, tmp_path) -> None:
        combined = _write(tmp_path / "c.csv", _COMBINED_HEADER, _combined_rows())
        result = import_historical_csv(
            HistoricalCsvImportRequest(
                combined_csv_path=combined,
                bid_csv_path=combined,
                ask_csv_path=combined,
            )
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_UNSUPPORTED_FORMAT
        )


class TestCombinedCsvMode:
    def test_valid_combined_csv_is_official_candidate(self, tmp_path) -> None:
        path = _write(tmp_path / "combined.csv", _COMBINED_HEADER, _combined_rows())
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_READY_OFFICIAL_EVALUATION
        )
        assert result.metadata is not None
        assert result.metadata.official_evaluation_eligible is True
        assert result.metadata.spread_included is True
        assert result.metadata.bar_count == 8
        assert result.dataset is not None

    def test_ohlc_only_official_request_is_blocked_missing_spread(
        self, tmp_path
    ) -> None:
        path = _write(
            tmp_path / "ohlc.csv",
            _OHLC_ONLY_HEADER,
            [row.replace(",0.003,", ",") for row in _combined_rows()],
        )
        result = import_historical_csv(
            HistoricalCsvImportRequest(
                combined_csv_path=path, official_evaluation_requested=True
            )
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_MISSING_SPREAD
        )

    def test_ohlc_only_reference_request_is_reference_only(self, tmp_path) -> None:
        path = _write(
            tmp_path / "ohlc.csv",
            _OHLC_ONLY_HEADER,
            [row.replace(",0.003,", ",") for row in _combined_rows()],
        )
        result = import_historical_csv(
            HistoricalCsvImportRequest(
                combined_csv_path=path, official_evaluation_requested=False
            )
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_READY_REFERENCE_ONLY
        )
        assert result.metadata is not None
        assert result.metadata.official_evaluation_eligible is False

    def test_missing_required_column_is_blocked(self, tmp_path) -> None:
        header = "timestamp,symbol,timeframe,open,high,low,spread,source_label"
        rows = [
            f"{_BASE_TS},USD_JPY,M5,100.0,100.2,99.9,0.003,SYNTHETIC_TEST"
        ]
        path = _write(tmp_path / "bad.csv", header, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS
        )
        assert "REQUIRED_COLUMN_MISSING_CLOSE" in result.blocked_reasons

    def test_forbidden_column_is_blocked_without_reading_values(
        self, tmp_path
    ) -> None:
        header = _COMBINED_HEADER + ",order_id"
        rows = [row + ",synthetic" for row in _combined_rows()]
        path = _write(tmp_path / "forbidden.csv", header, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_FORBIDDEN_COLUMNS
        )

    def test_forbidden_column_detected_despite_case_and_spaces(
        self, tmp_path
    ) -> None:
        header = _COMBINED_HEADER + ",Raw Response"
        rows = [row + ",synthetic" for row in _combined_rows()]
        path = _write(tmp_path / "forbidden2.csv", header, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_FORBIDDEN_COLUMNS
        )

    def test_duplicate_timestamp_is_blocked(self, tmp_path) -> None:
        rows = _combined_rows(4)
        rows[2] = rows[1]
        path = _write(tmp_path / "dup.csv", _COMBINED_HEADER, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS
        )
        assert "DUPLICATE_TIMESTAMP_BLOCKED" in result.blocked_reasons

    def test_non_monotonic_timestamp_is_blocked(self, tmp_path) -> None:
        rows = _combined_rows(4)
        rows[1], rows[2] = rows[2], rows[1]
        path = _write(tmp_path / "mono.csv", _COMBINED_HEADER, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert "TIMESTAMP_NOT_MONOTONIC_BLOCKED" in result.blocked_reasons

    def test_naive_iso_timestamp_is_blocked_tz_missing(self, tmp_path) -> None:
        rows = [
            "2026-07-08T09:00:00,USD_JPY,M5,100.0,100.2,99.9,100.1,0.003,"
            "SYNTHETIC_TEST"
        ]
        path = _write(tmp_path / "naive.csv", _COMBINED_HEADER, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_MISSING_TIMESTAMP_TZ
        )

    def test_tz_aware_iso_timestamp_is_accepted(self, tmp_path) -> None:
        rows = [
            "2026-07-08T09:00:00+00:00,USD_JPY,M5,100.0,100.2,99.9,100.1,0.003,"
            "SYNTHETIC_TEST",
            "2026-07-08T09:05:00+00:00,USD_JPY,M5,100.1,100.3,100.0,100.2,0.003,"
            "SYNTHETIC_TEST",
        ]
        path = _write(tmp_path / "iso.csv", _COMBINED_HEADER, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_READY_OFFICIAL_EVALUATION
        )

    def test_high_below_low_is_blocked(self, tmp_path) -> None:
        rows = [
            f"{_BASE_TS},USD_JPY,M5,100.0,99.0,100.5,100.1,0.003,SYNTHETIC_TEST"
        ]
        path = _write(tmp_path / "range.csv", _COMBINED_HEADER, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert "HIGH_BELOW_LOW_BLOCKED" in result.blocked_reasons

    def test_nonnumeric_ohlc_is_blocked(self, tmp_path) -> None:
        rows = [
            f"{_BASE_TS},USD_JPY,M5,abc,100.2,99.9,100.1,0.003,SYNTHETIC_TEST"
        ]
        path = _write(tmp_path / "nonnum.csv", _COMBINED_HEADER, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert "OHLC_MISSING_OR_NONNUMERIC_BLOCKED" in result.blocked_reasons

    def test_symbol_mismatch_is_blocked(self, tmp_path) -> None:
        rows = [
            f"{_BASE_TS},EUR_JPY,M5,100.0,100.2,99.9,100.1,0.003,SYNTHETIC_TEST"
        ]
        path = _write(tmp_path / "sym.csv", _COMBINED_HEADER, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert "SYMBOL_MISSING_OR_MISMATCH_BLOCKED" in result.blocked_reasons

    def test_timeframe_mismatch_is_blocked(self, tmp_path) -> None:
        rows = [
            f"{_BASE_TS},USD_JPY,M1,100.0,100.2,99.9,100.1,0.003,SYNTHETIC_TEST"
        ]
        path = _write(tmp_path / "tf.csv", _COMBINED_HEADER, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert "TIMEFRAME_MISSING_OR_MISMATCH_BLOCKED" in result.blocked_reasons

    def test_missing_source_label_is_blocked(self, tmp_path) -> None:
        rows = [f"{_BASE_TS},USD_JPY,M5,100.0,100.2,99.9,100.1,0.003,"]
        path = _write(tmp_path / "src.csv", _COMBINED_HEADER, rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert "SOURCE_LABEL_MISSING_BLOCKED" in result.blocked_reasons

    def test_empty_file_is_blocked(self, tmp_path) -> None:
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=str(path))
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_EMPTY_FILE
        )

    def test_header_only_file_is_blocked(self, tmp_path) -> None:
        path = _write(tmp_path / "headeronly.csv", _COMBINED_HEADER, [])
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_EMPTY_FILE
        )


class TestBidAskPairMode:
    def _pair_paths(self, tmp_path, *, ask_offset: float = 0.003) -> tuple[str, str]:
        bid = _write(
            tmp_path / "bid.csv", _OHLC_ONLY_HEADER, _side_rows(offset=0.0)
        )
        ask = _write(
            tmp_path / "ask.csv",
            _OHLC_ONLY_HEADER,
            _side_rows(offset=ask_offset),
        )
        return bid, ask

    def test_valid_pair_is_official_with_bar_approximation_labels(
        self, tmp_path
    ) -> None:
        bid, ask = self._pair_paths(tmp_path)
        result = import_historical_csv(
            HistoricalCsvImportRequest(bid_csv_path=bid, ask_csv_path=ask)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_READY_OFFICIAL_EVALUATION
        )
        assert result.metadata is not None
        assert SPREAD_FROM_BID_ASK_LABEL in (
            result.metadata.spread_derivation_labels
        )
        assert NOT_TICK_LEVEL_LABEL in result.metadata.spread_derivation_labels
        assert result.metadata.spread_included is True

    def test_bid_only_is_blocked(self, tmp_path) -> None:
        bid = _write(tmp_path / "bid.csv", _OHLC_ONLY_HEADER, _side_rows())
        result = import_historical_csv(
            HistoricalCsvImportRequest(bid_csv_path=bid)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_BID_ASK_MISMATCH
        )

    def test_ask_only_is_blocked(self, tmp_path) -> None:
        ask = _write(tmp_path / "ask.csv", _OHLC_ONLY_HEADER, _side_rows())
        result = import_historical_csv(
            HistoricalCsvImportRequest(ask_csv_path=ask)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_BID_ASK_MISMATCH
        )

    def test_row_count_mismatch_is_blocked(self, tmp_path) -> None:
        bid = _write(tmp_path / "bid.csv", _OHLC_ONLY_HEADER, _side_rows(8))
        ask = _write(
            tmp_path / "ask.csv",
            _OHLC_ONLY_HEADER,
            _side_rows(6, offset=0.003),
        )
        result = import_historical_csv(
            HistoricalCsvImportRequest(bid_csv_path=bid, ask_csv_path=ask)
        )
        assert "BID_ASK_ROW_COUNT_MISMATCH" in result.blocked_reasons

    def test_timestamp_mismatch_is_blocked(self, tmp_path) -> None:
        bid_rows = _side_rows(4)
        ask_rows = _side_rows(4, offset=0.003)
        shifted = str(_BASE_TS + 7 * _STEP_MS)
        ask_rows[2] = ask_rows[2].replace(
            str(_BASE_TS + 2 * _STEP_MS), shifted
        )
        # keep ask monotonic by replacing the final row too
        ask_rows[3] = ask_rows[3].replace(
            str(_BASE_TS + 3 * _STEP_MS), str(_BASE_TS + 8 * _STEP_MS)
        )
        bid = _write(tmp_path / "bid.csv", _OHLC_ONLY_HEADER, bid_rows)
        ask = _write(tmp_path / "ask.csv", _OHLC_ONLY_HEADER, ask_rows)
        result = import_historical_csv(
            HistoricalCsvImportRequest(bid_csv_path=bid, ask_csv_path=ask)
        )
        assert "BID_ASK_TIMESTAMP_MISMATCH" in result.blocked_reasons

    def test_negative_derived_spread_is_blocked(self, tmp_path) -> None:
        bid, ask = self._pair_paths(tmp_path, ask_offset=-0.05)
        result = import_historical_csv(
            HistoricalCsvImportRequest(bid_csv_path=bid, ask_csv_path=ask)
        )
        assert (
            "BID_ASK_SPREAD_DERIVATION_IMPOSSIBLE_NEGATIVE"
            in result.blocked_reasons
        )

    def test_pair_side_with_forbidden_column_is_blocked(self, tmp_path) -> None:
        bid = _write(
            tmp_path / "bid.csv",
            _OHLC_ONLY_HEADER + ",api_key",
            [row + ",synthetic" for row in _side_rows()],
        )
        ask = _write(
            tmp_path / "ask.csv", _OHLC_ONLY_HEADER, _side_rows(offset=0.003)
        )
        result = import_historical_csv(
            HistoricalCsvImportRequest(bid_csv_path=bid, ask_csv_path=ask)
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_FORBIDDEN_COLUMNS
        )


class TestDatasetConnection:
    def test_adapter_output_is_valid_backtest_dataset(self, tmp_path) -> None:
        path = _write(tmp_path / "combined.csv", _COMBINED_HEADER, _combined_rows())
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert result.dataset is not None
        validation = validate_backtest_dataset(result.dataset)
        assert validation.status is (
            GmoBacktestDatasetStatus.DATASET_VALID_SYNTHETIC
        )

    def test_session_labels_derived_from_utc_timestamp(self, tmp_path) -> None:
        path = _write(tmp_path / "combined.csv", _COMBINED_HEADER, _combined_rows())
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert result.metadata is not None
        assert result.metadata.session_derivation_label in (
            "SESSION_DERIVED_FROM_UTC_TIMESTAMP_JST_POLICY",
            "SESSION_PROVIDED_IN_CSV",
        )

    def test_result_pins_no_proof_and_no_live(self, tmp_path) -> None:
        path = _write(tmp_path / "combined.csv", _COMBINED_HEADER, _combined_rows())
        result = import_historical_csv(
            HistoricalCsvImportRequest(combined_csv_path=path)
        )
        assert result.metadata is not None
        assert result.metadata.performance_proof_status is False
        assert result.metadata.live_ready is False
        assert result.metadata.real_data_used is False
        assert result.metadata.synthetic_fixture_only is True
        assert result.download_performed is False
        assert result.real_http_performed is False
        assert result.credential_value_read is False
        assert result.env_read_performed is False
        assert result.raw_id_value_exposure is False
        assert not result

    def test_request_defaults_are_synthetic_phase(self) -> None:
        request = HistoricalCsvImportRequest()
        assert request.treat_as_synthetic_fixture is True
        assert replace(request, official_evaluation_requested=False)


class TestModuleIsolation:
    def test_module_has_no_network_broker_or_env_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "requests" not in source
        assert "urllib" not in source
        assert "socket" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "/private/v1" not in source
        assert "glob" not in source
        assert "curl" not in source
        assert "wget" not in source
