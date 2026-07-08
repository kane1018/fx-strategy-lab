"""No-POST tests for the historical data source selection model."""

from __future__ import annotations

import inspect
from dataclasses import replace

from app.services import gmo_historical_data_source_selection as module
from app.services.gmo_historical_data_source_selection import (
    FORBIDDEN_CSV_COLUMNS,
    REQUIRED_CSV_COLUMNS,
    HistoricalDataSourceCandidate,
    HistoricalDataSourceClass,
    build_default_source_candidates,
    build_historical_data_source_decision,
    build_local_csv_intake_requirements,
    classify_historical_data_source,
)


def _manual_csv_candidate(**overrides) -> HistoricalDataSourceCandidate:
    base = HistoricalDataSourceCandidate(
        source_name_safe_label="TEST_MANUAL_CSV",
        acquisition_method_safe_label="OPERATOR_MANUAL_EXPORT_LOCAL_CSV",
        credential_required=False,
        broker_api_required=False,
        real_http_required_at_intake=False,
        ohlc_available=True,
        bid_ask_available=True,
        spread_available=False,
        timestamp_tz_clear=True,
        session_derivable=True,
        local_csv_possible=True,
        broker_consistent_with_gmo=True,
    )
    return replace(base, **overrides)


class TestClassification:
    def test_manual_csv_with_bid_ask_is_official_candidate(self) -> None:
        assessment = classify_historical_data_source(_manual_csv_candidate())
        assert assessment.source_class is (
            HistoricalDataSourceClass.OFFICIAL_EVALUATION_CANDIDATE
        )
        assert assessment.official_evaluation_eligible is True
        assert assessment.spread_included_evaluation_possible is True

    def test_explicit_spread_column_is_official_candidate(self) -> None:
        assessment = classify_historical_data_source(
            _manual_csv_candidate(bid_ask_available=False, spread_available=True)
        )
        assert assessment.official_evaluation_eligible is True

    def test_ohlc_only_source_is_reference_only(self) -> None:
        assessment = classify_historical_data_source(
            _manual_csv_candidate(bid_ask_available=False, spread_available=False)
        )
        assert assessment.source_class is (
            HistoricalDataSourceClass.REFERENCE_ONLY_CANDIDATE
        )
        assert assessment.official_evaluation_eligible is False
        assert "REFERENCE_ONLY_SPREAD_DATA_MISSING" in assessment.reasons

    def test_credential_required_source_is_blocked(self) -> None:
        assessment = classify_historical_data_source(
            _manual_csv_candidate(credential_required=True)
        )
        assert assessment.source_class is HistoricalDataSourceClass.BLOCKED_SOURCE
        assert "BLOCKED_CREDENTIAL_REQUIRED" in assessment.reasons

    def test_real_http_at_intake_is_blocked(self) -> None:
        assessment = classify_historical_data_source(
            _manual_csv_candidate(real_http_required_at_intake=True)
        )
        assert assessment.source_class is HistoricalDataSourceClass.BLOCKED_SOURCE

    def test_broker_api_required_is_blocked(self) -> None:
        assessment = classify_historical_data_source(
            _manual_csv_candidate(broker_api_required=True)
        )
        assert assessment.source_class is HistoricalDataSourceClass.BLOCKED_SOURCE

    def test_missing_timezone_is_blocked(self) -> None:
        assessment = classify_historical_data_source(
            _manual_csv_candidate(timestamp_tz_clear=False)
        )
        assert assessment.source_class is HistoricalDataSourceClass.BLOCKED_SOURCE
        assert "BLOCKED_TIMESTAMP_TZ_UNCLEAR" in assessment.reasons

    def test_forbidden_columns_are_blocked(self) -> None:
        assessment = classify_historical_data_source(
            _manual_csv_candidate(forbidden_columns_present=True)
        )
        assert assessment.source_class is HistoricalDataSourceClass.BLOCKED_SOURCE
        assert "BLOCKED_FORBIDDEN_COLUMNS" in assessment.reasons

    def test_synthetic_source_is_development_only(self) -> None:
        assessment = classify_historical_data_source(
            _manual_csv_candidate(synthetic_only=True, local_csv_possible=False)
        )
        assert assessment.source_class is (
            HistoricalDataSourceClass.DEVELOPMENT_ONLY_SOURCE
        )
        assert assessment.official_evaluation_eligible is False
        assert assessment.performance_proof_status is False

    def test_cross_broker_official_candidate_carries_caution(self) -> None:
        assessment = classify_historical_data_source(
            _manual_csv_candidate(broker_consistent_with_gmo=False)
        )
        assert "CAUTION_BROKER_ENVIRONMENT_DIFFERS_FROM_GMO" in assessment.reasons

    def test_assessment_is_never_performance_proof(self) -> None:
        assessment = classify_historical_data_source(_manual_csv_candidate())
        assert assessment.performance_proof_status is False
        assert assessment.live_ready is False
        assert assessment.real_data_fetch_performed is False
        assert not assessment


class TestDefaultCandidatesAndDecision:
    def test_default_candidates_classify_as_documented(self) -> None:
        by_name = {
            candidate.source_name_safe_label: classify_historical_data_source(
                candidate
            )
            for candidate in build_default_source_candidates()
        }
        assert by_name[
            "GMO_PUBLIC_KLINES_BID_ASK_LOCAL_CSV"
        ].source_class is HistoricalDataSourceClass.OFFICIAL_EVALUATION_CANDIDATE
        assert by_name[
            "GMO_MEMBER_SITE_MANUAL_EXPORT_CSV"
        ].source_class is HistoricalDataSourceClass.REFERENCE_ONLY_CANDIDATE
        assert by_name[
            "OTHER_BROKER_EXPORT_LOCAL_CSV"
        ].source_class is HistoricalDataSourceClass.OFFICIAL_EVALUATION_CANDIDATE
        assert (
            "CAUTION_BROKER_ENVIRONMENT_DIFFERS_FROM_GMO"
            in by_name["OTHER_BROKER_EXPORT_LOCAL_CSV"].reasons
        )
        assert by_name[
            "SYNTHETIC_FIXTURE_CONTINUED"
        ].source_class is HistoricalDataSourceClass.DEVELOPMENT_ONLY_SOURCE
        assert by_name[
            "ANY_CREDENTIAL_OR_API_REQUIRED_SOURCE"
        ].source_class is HistoricalDataSourceClass.BLOCKED_SOURCE

    def test_primary_route_uses_gmo_public_bid_ask_klines(self) -> None:
        decision = build_historical_data_source_decision()
        assert decision.primary_route_safe_label == (
            "GMO_PUBLIC_KLINES_BID_ASK_LOCAL_CSV"
        )
        assert decision.development_only_route_safe_label == (
            "SYNTHETIC_FIXTURE_CONTINUED"
        )

    def test_decision_lists_operator_actions_and_no_claims(self) -> None:
        decision = build_historical_data_source_decision()
        assert decision.operator_required_actions
        assert any(
            "OPERATOR_APPROVE" in action
            for action in decision.operator_required_actions
        )
        assert decision.performance_proof_status is False
        assert decision.live_ready is False
        assert decision.real_data_fetch_performed is False
        assert decision.unattended_live_supported is False
        assert not decision

    def test_gmo_public_bid_ask_official_condition_is_recorded(self) -> None:
        decision = build_historical_data_source_decision()
        primary = next(
            assessment
            for assessment in decision.assessments
            if assessment.source_name_safe_label
            == "GMO_PUBLIC_KLINES_BID_ASK_LOCAL_CSV"
        )
        assert (
            "OFFICIAL_CONDITION_SPREAD_FROM_BID_ASK_BAR_APPROXIMATION"
            in primary.reasons
        )


class TestCsvIntakeSpec:
    def test_required_columns_are_fixed(self) -> None:
        spec = build_local_csv_intake_requirements()
        expected = (
            "timestamp",
            "symbol",
            "timeframe",
            "open",
            "high",
            "low",
            "close",
            "source_label",
        )
        for column in expected:
            assert column in spec.required_columns
        assert spec.required_columns == REQUIRED_CSV_COLUMNS

    def test_spread_or_bid_ask_group_required_for_official(self) -> None:
        spec = build_local_csv_intake_requirements()
        assert ("spread",) in spec.spread_column_groups
        assert ("bid", "ask") in spec.spread_column_groups
        assert (
            "RULE_SPREAD_OR_BID_ASK_REQUIRED_FOR_OFFICIAL"
            in spec.validation_rule_labels
        )

    def test_forbidden_columns_include_ids_and_credentials(self) -> None:
        spec = build_local_csv_intake_requirements()
        for column in ("account_id", "order_id", "position_id", "api_key", "raw_response"):
            assert column in spec.forbidden_columns
        assert spec.forbidden_columns == FORBIDDEN_CSV_COLUMNS

    def test_validation_rules_cover_required_families(self) -> None:
        spec = build_local_csv_intake_requirements()
        labels = spec.validation_rule_labels
        assert "RULE_TIMESTAMP_MONOTONIC_INCREASING" in labels
        assert "RULE_DUPLICATE_TIMESTAMP_BLOCKED" in labels
        assert "RULE_HIGH_GTE_LOW" in labels
        assert "RULE_SESSION_DERIVED_FROM_TZ_OR_PROVIDED" in labels
        assert "RULE_FORBIDDEN_COLUMNS_BLOCKED" in labels

    def test_intake_spec_is_local_only_no_download(self) -> None:
        spec = build_local_csv_intake_requirements()
        assert spec.local_file_only is True
        assert spec.download_performed is False
        assert spec.timezone_policy_safe_label == (
            "UTC_EPOCH_OR_ISO_WITH_EXPLICIT_TZ"
        )
        assert "REFERENCE_ONLY" in spec.spread_policy_safe_label
        assert not spec


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
        assert "curl" not in source
        assert "wget" not in source
