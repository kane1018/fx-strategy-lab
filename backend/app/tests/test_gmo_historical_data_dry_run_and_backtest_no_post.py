"""No-POST tests for the validated-operator-local-CSV real-data path.

Uses only tmp_path synthetic CSV fixtures. No operator file, no real data
file, and no network surface are touched here.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.services.gmo_historical_data_import_adapter import (
    CsvImportIntakeCategory,
    HistoricalCsvImportRequest,
    import_historical_csv,
)
from app.services.gmo_strategy_backtest_dataset import (
    DATASET_VALID_STATUSES,
    GmoBacktestDatasetStatus,
    build_synthetic_trend_dataset,
    split_backtest_dataset_chronologically,
    validate_backtest_dataset,
)
from app.services.gmo_strategy_backtest_engine import (
    GmoBacktestRunStatus,
    build_candidate_exit_policy_profiles,
    run_synthetic_backtest,
)
from app.services.gmo_strategy_backtest_metrics import compute_backtest_metrics
from app.services.gmo_strategy_backtest_report import (
    GmoBacktestReportStatus,
    build_backtest_report,
    render_backtest_report_safe_lines,
)

_HEADER = "timestamp,symbol,timeframe,open,high,low,close,source_label"
_BASE_TS = 1_750_000_000_000
_STEP_MS = 300_000


def _side(path: Path, *, count: int, offset: float, uptrend: bool) -> str:
    rows = [_HEADER]
    value = 100.0 + offset
    for index in range(count):
        ts = _BASE_TS + index * _STEP_MS
        close = value + (0.05 if uptrend else -0.05)
        high = max(value, close) + 0.02
        low = min(value, close) - 0.02
        rows.append(
            f"{ts},USD_JPY,M5,{value},{high},{low},{close},SYNTHETIC_TEST"
        )
        value = close
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(path)


def _real_data_request(tmp_path, *, count: int = 80) -> HistoricalCsvImportRequest:
    bid = _side(tmp_path / "bid.csv", count=count, offset=0.0, uptrend=True)
    ask = _side(tmp_path / "ask.csv", count=count, offset=0.004, uptrend=True)
    return HistoricalCsvImportRequest(
        bid_csv_path=bid,
        ask_csv_path=ask,
        official_evaluation_requested=True,
        treat_as_synthetic_fixture=False,
    )


class TestRealDataDatasetGrant:
    def test_validated_operator_csv_is_marked_real_data(self, tmp_path) -> None:
        result = import_historical_csv(_real_data_request(tmp_path))
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_READY_OFFICIAL_EVALUATION
        )
        assert result.dataset is not None
        assert result.dataset.synthetic_fixture is False
        assert result.dataset.validated_operator_local_csv is True
        assert result.metadata is not None
        assert result.metadata.real_data_used is True

    def test_validated_operator_csv_passes_dataset_validation(
        self, tmp_path
    ) -> None:
        result = import_historical_csv(_real_data_request(tmp_path))
        validation = validate_backtest_dataset(result.dataset)
        assert validation.status is (
            GmoBacktestDatasetStatus.DATASET_VALID_OPERATOR_LOCAL_CSV
        )
        assert validation.status in DATASET_VALID_STATUSES

    def test_unvalidated_real_dataset_stays_blocked(self) -> None:
        # A real dataset NOT produced by the adapter cannot pass.
        synthetic = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=40
        )
        forged_real = replace(
            synthetic,
            synthetic_fixture=False,
            validated_operator_local_csv=False,
        )
        validation = validate_backtest_dataset(forged_real)
        assert validation.status is (
            GmoBacktestDatasetStatus.DATASET_INVALID_BLOCKED
        )
        assert (
            "DATASET_REAL_DATA_NOT_SUPPORTED_THIS_PHASE"
            in validation.blocked_reasons
        )

    def test_synthetic_dataset_still_valid_synthetic(self) -> None:
        synthetic = build_synthetic_trend_dataset(
            direction_safe_label="UP", bars=40
        )
        validation = validate_backtest_dataset(synthetic)
        assert validation.status is (
            GmoBacktestDatasetStatus.DATASET_VALID_SYNTHETIC
        )

    def test_reference_only_request_does_not_grant_real_data(
        self, tmp_path
    ) -> None:
        # OHLC-only + reference-only request -> reference-only, not official.
        bid_only_header = _HEADER
        rows = [bid_only_header]
        value = 100.0
        for index in range(40):
            ts = _BASE_TS + index * _STEP_MS
            close = value + 0.05
            rows.append(
                f"{ts},USD_JPY,M5,{value},{value + 0.1},{value - 0.1},{close},"
                "SYNTHETIC_TEST"
            )
            value = close
        combined = tmp_path / "ohlc.csv"
        combined.write_text("\n".join(rows) + "\n", encoding="utf-8")
        result = import_historical_csv(
            HistoricalCsvImportRequest(
                combined_csv_path=str(combined),
                official_evaluation_requested=False,
                treat_as_synthetic_fixture=False,
            )
        )
        assert result.intake_category is (
            CsvImportIntakeCategory.CSV_INTAKE_READY_REFERENCE_ONLY
        )


class TestRealDataBacktest:
    def test_backtest_runs_on_validated_operator_dataset(self, tmp_path) -> None:
        result = import_historical_csv(_real_data_request(tmp_path))
        policy = build_candidate_exit_policy_profiles()[
            "CANDIDATE_MEDIUM_BALANCED"
        ]
        run_result = run_synthetic_backtest(
            dataset=result.dataset, exit_policy=policy, spread_included=True
        )
        assert run_result.status is (
            GmoBacktestRunStatus.BACKTEST_SYNTHETIC_COMPLETED
        )
        assert run_result.spread_included is True
        assert run_result.actual_post_performed is False
        assert run_result.real_http_performed is False

    def test_invalid_dry_run_prevents_backtest(self) -> None:
        forged_real = replace(
            build_synthetic_trend_dataset(direction_safe_label="UP", bars=40),
            synthetic_fixture=False,
            validated_operator_local_csv=False,
        )
        policy = build_candidate_exit_policy_profiles()[
            "CANDIDATE_MEDIUM_BALANCED"
        ]
        run_result = run_synthetic_backtest(
            dataset=forged_real, exit_policy=policy, spread_included=True
        )
        assert run_result.status is (
            GmoBacktestRunStatus.BACKTEST_SYNTHETIC_INVALID_DATASET
        )

    def test_report_pins_unproven_not_live_ready(self, tmp_path) -> None:
        result = import_historical_csv(_real_data_request(tmp_path))
        dataset = result.dataset
        split = split_backtest_dataset_chronologically(
            dataset, train_bars=40, validation_bars=20
        )
        policy = build_candidate_exit_policy_profiles()[
            "CANDIDATE_MEDIUM_BALANCED"
        ]
        run_result = run_synthetic_backtest(
            dataset=dataset, exit_policy=policy, spread_included=True
        )
        metrics = compute_backtest_metrics(run_result)
        report = build_backtest_report(
            dataset=dataset,
            split=split,
            run_result=run_result,
            metrics=metrics,
            exit_policy=policy,
        )
        assert report.report_status is (
            GmoBacktestReportStatus.REPORT_SYNTHETIC_SPREAD_INCLUDED
        )
        assert report.performance_proof_status is False
        assert report.live_ready is False
        lines = render_backtest_report_safe_lines(report)
        joined = "\n".join(lines).lower()
        assert "profitable" not in joined
        assert "winning strategy" not in joined
        assert "edge proven" not in joined
