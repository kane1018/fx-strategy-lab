"""Historical data source selection model (no-POST, no-download).

Classifies candidate historical data sources into official / reference-only /
blocked / development-only categories, and fixes the local CSV intake
requirements the import adapter step will implement. This module performs no
network access, no download, no credential/env read; it evaluates
safe-label descriptors only.

A source classification is NEVER a performance proof: every decision pins
``performance_proof_status = False`` and ``live_ready = False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HistoricalDataSourceClass(str, Enum):
    OFFICIAL_EVALUATION_CANDIDATE = "OFFICIAL_EVALUATION_CANDIDATE"
    REFERENCE_ONLY_CANDIDATE = "REFERENCE_ONLY_CANDIDATE"
    BLOCKED_SOURCE = "BLOCKED_SOURCE"
    DEVELOPMENT_ONLY_SOURCE = "DEVELOPMENT_ONLY_SOURCE"


@dataclass(frozen=True)
class HistoricalDataSourceCandidate:
    """Safe-label descriptor of one candidate source. Default-deny."""

    source_name_safe_label: str
    acquisition_method_safe_label: str
    automation_allowed_this_step: bool = False
    credential_required: bool = True
    broker_api_required: bool = True
    real_http_required_at_intake: bool = True
    ohlc_available: bool = False
    bid_ask_available: bool = False
    spread_available: bool = False
    timestamp_tz_clear: bool = False
    session_derivable: bool = False
    local_csv_possible: bool = False
    broker_consistent_with_gmo: bool = False
    synthetic_only: bool = False
    forbidden_columns_present: bool = False
    required_operator_action_safe_label: str = "OPERATOR_ACTION_NOT_DEFINED"


@dataclass(frozen=True)
class HistoricalDataSourceAssessment:
    """Classification result. Never a performance proof, never truthy."""

    source_name_safe_label: str
    source_class: HistoricalDataSourceClass
    reasons: tuple[str, ...]
    official_evaluation_eligible: bool
    spread_included_evaluation_possible: bool
    required_operator_action_safe_label: str
    performance_proof_status: bool = False
    live_ready: bool = False
    real_data_fetch_performed: bool = False

    def __bool__(self) -> bool:
        return False


def classify_historical_data_source(
    candidate: HistoricalDataSourceCandidate,
) -> HistoricalDataSourceAssessment:
    """Classify one candidate fail-closed.

    Order: hard blocks (credential / broker API / real HTTP at intake /
    forbidden columns / no local CSV path / unclear timezone) ->
    development-only (synthetic) -> official (OHLC + spread-or-bid/ask +
    TZ + session) -> reference-only (OHLC without spread data).
    """

    reasons: list[str] = []
    if candidate.forbidden_columns_present:
        reasons.append("BLOCKED_FORBIDDEN_COLUMNS")
    if candidate.credential_required:
        reasons.append("BLOCKED_CREDENTIAL_REQUIRED")
    if candidate.broker_api_required:
        reasons.append("BLOCKED_BROKER_API_REQUIRED")
    if candidate.real_http_required_at_intake:
        reasons.append("BLOCKED_REAL_HTTP_REQUIRED_AT_INTAKE")
    if not candidate.local_csv_possible and not candidate.synthetic_only:
        reasons.append("BLOCKED_NO_LOCAL_CSV_PATH")
    if not candidate.timestamp_tz_clear and not candidate.synthetic_only:
        reasons.append("BLOCKED_TIMESTAMP_TZ_UNCLEAR")
    if reasons:
        return HistoricalDataSourceAssessment(
            source_name_safe_label=candidate.source_name_safe_label,
            source_class=HistoricalDataSourceClass.BLOCKED_SOURCE,
            reasons=tuple(reasons),
            official_evaluation_eligible=False,
            spread_included_evaluation_possible=False,
            required_operator_action_safe_label=(
                candidate.required_operator_action_safe_label
            ),
        )

    if candidate.synthetic_only:
        return HistoricalDataSourceAssessment(
            source_name_safe_label=candidate.source_name_safe_label,
            source_class=HistoricalDataSourceClass.DEVELOPMENT_ONLY_SOURCE,
            reasons=("DEVELOPMENT_ONLY_SYNTHETIC_NEVER_PERFORMANCE_PROOF",),
            official_evaluation_eligible=False,
            spread_included_evaluation_possible=False,
            required_operator_action_safe_label=(
                candidate.required_operator_action_safe_label
            ),
        )

    spread_data_available = (
        candidate.spread_available or candidate.bid_ask_available
    )
    if (
        candidate.ohlc_available
        and spread_data_available
        and candidate.session_derivable
    ):
        return HistoricalDataSourceAssessment(
            source_name_safe_label=candidate.source_name_safe_label,
            source_class=(
                HistoricalDataSourceClass.OFFICIAL_EVALUATION_CANDIDATE
            ),
            reasons=(
                "OFFICIAL_OHLC_AND_SPREAD_DATA_AND_TZ_AND_SESSION_AVAILABLE",
            )
            + (
                ("OFFICIAL_CONDITION_SPREAD_FROM_BID_ASK_BAR_APPROXIMATION",)
                if not candidate.spread_available
                else ()
            )
            + (
                ("CAUTION_BROKER_ENVIRONMENT_DIFFERS_FROM_GMO",)
                if not candidate.broker_consistent_with_gmo
                else ()
            ),
            official_evaluation_eligible=True,
            spread_included_evaluation_possible=True,
            required_operator_action_safe_label=(
                candidate.required_operator_action_safe_label
            ),
        )

    if candidate.ohlc_available:
        reference_reasons = ["REFERENCE_ONLY_SPREAD_DATA_MISSING"]
        if not candidate.session_derivable:
            reference_reasons.append("REFERENCE_ONLY_SESSION_NOT_DERIVABLE")
        return HistoricalDataSourceAssessment(
            source_name_safe_label=candidate.source_name_safe_label,
            source_class=HistoricalDataSourceClass.REFERENCE_ONLY_CANDIDATE,
            reasons=tuple(reference_reasons),
            official_evaluation_eligible=False,
            spread_included_evaluation_possible=False,
            required_operator_action_safe_label=(
                candidate.required_operator_action_safe_label
            ),
        )

    return HistoricalDataSourceAssessment(
        source_name_safe_label=candidate.source_name_safe_label,
        source_class=HistoricalDataSourceClass.BLOCKED_SOURCE,
        reasons=("BLOCKED_OHLC_NOT_AVAILABLE",),
        official_evaluation_eligible=False,
        spread_included_evaluation_possible=False,
        required_operator_action_safe_label=(
            candidate.required_operator_action_safe_label
        ),
    )


def build_default_source_candidates() -> tuple[HistoricalDataSourceCandidate, ...]:
    """The candidate set assessed in this step (repo-truthful descriptors)."""

    return (
        HistoricalDataSourceCandidate(
            source_name_safe_label="GMO_PUBLIC_KLINES_BID_ASK_LOCAL_CSV",
            acquisition_method_safe_label=(
                "OPERATOR_APPROVED_PUBLIC_GET_SCRIPT_THEN_LOCAL_CSV"
            ),
            automation_allowed_this_step=False,
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
            required_operator_action_safe_label=(
                "OPERATOR_APPROVE_AND_RUN_PUBLIC_KLINE_EXPORT_BID_AND_ASK"
            ),
        ),
        HistoricalDataSourceCandidate(
            source_name_safe_label="GMO_MEMBER_SITE_MANUAL_EXPORT_CSV",
            acquisition_method_safe_label="OPERATOR_MANUAL_EXPORT_LOCAL_CSV",
            automation_allowed_this_step=False,
            credential_required=False,
            broker_api_required=False,
            real_http_required_at_intake=False,
            ohlc_available=True,
            bid_ask_available=False,
            spread_available=False,
            timestamp_tz_clear=True,
            session_derivable=True,
            local_csv_possible=True,
            broker_consistent_with_gmo=True,
            required_operator_action_safe_label=(
                "OPERATOR_CONFIRM_EXPORT_AVAILABILITY_AND_SPREAD_COLUMNS"
            ),
        ),
        HistoricalDataSourceCandidate(
            source_name_safe_label="OTHER_BROKER_EXPORT_LOCAL_CSV",
            acquisition_method_safe_label="OPERATOR_MANUAL_EXPORT_LOCAL_CSV",
            automation_allowed_this_step=False,
            credential_required=False,
            broker_api_required=False,
            real_http_required_at_intake=False,
            ohlc_available=True,
            bid_ask_available=True,
            spread_available=False,
            timestamp_tz_clear=True,
            session_derivable=True,
            local_csv_possible=True,
            broker_consistent_with_gmo=False,
            required_operator_action_safe_label=(
                "OPERATOR_TREAT_AS_CROSS_BROKER_REFERENCE_DECISION"
            ),
        ),
        HistoricalDataSourceCandidate(
            source_name_safe_label="SYNTHETIC_FIXTURE_CONTINUED",
            acquisition_method_safe_label="IN_PROCESS_DETERMINISTIC_FIXTURE",
            automation_allowed_this_step=True,
            credential_required=False,
            broker_api_required=False,
            real_http_required_at_intake=False,
            ohlc_available=True,
            bid_ask_available=False,
            spread_available=True,
            timestamp_tz_clear=True,
            session_derivable=True,
            local_csv_possible=False,
            broker_consistent_with_gmo=False,
            synthetic_only=True,
            required_operator_action_safe_label="OPERATOR_ACTION_NONE_DEV_ONLY",
        ),
        HistoricalDataSourceCandidate(
            source_name_safe_label="ANY_CREDENTIAL_OR_API_REQUIRED_SOURCE",
            acquisition_method_safe_label="BLOCKED_THIS_STEP",
            credential_required=True,
            broker_api_required=True,
            real_http_required_at_intake=True,
            required_operator_action_safe_label="OPERATOR_ACTION_NONE_BLOCKED",
        ),
    )


# ---------------------------------------------------------------------------
# Local CSV intake spec (fixed for the import adapter step)
# ---------------------------------------------------------------------------


class CsvIntakeResultCategory(str, Enum):
    CSV_INTAKE_READY_OFFICIAL_EVALUATION = (
        "CSV_INTAKE_READY_OFFICIAL_EVALUATION"
    )
    CSV_INTAKE_READY_REFERENCE_ONLY = "CSV_INTAKE_READY_REFERENCE_ONLY"
    CSV_INTAKE_BLOCKED_MISSING_SPREAD = "CSV_INTAKE_BLOCKED_MISSING_SPREAD"
    CSV_INTAKE_BLOCKED_MISSING_TIMESTAMP_TZ = (
        "CSV_INTAKE_BLOCKED_MISSING_TIMESTAMP_TZ"
    )
    CSV_INTAKE_BLOCKED_INVALID_COLUMNS = "CSV_INTAKE_BLOCKED_INVALID_COLUMNS"
    CSV_INTAKE_BLOCKED_FORBIDDEN_COLUMNS = (
        "CSV_INTAKE_BLOCKED_FORBIDDEN_COLUMNS"
    )
    CSV_INTAKE_NOT_PROVIDED = "CSV_INTAKE_NOT_PROVIDED"


REQUIRED_CSV_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "symbol",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "source_label",
)

# Official evaluation additionally requires ONE of these column groups.
SPREAD_COLUMN_GROUPS: tuple[tuple[str, ...], ...] = (
    ("spread",),
    (
        "bid_open",
        "bid_high",
        "bid_low",
        "bid_close",
        "ask_open",
        "ask_high",
        "ask_low",
        "ask_close",
    ),
    ("bid", "ask"),
)

OPTIONAL_CSV_COLUMNS: tuple[str, ...] = (
    "volume",
    "market_status",
    "ticker_fresh_status",
    "spread_status",
    "session_label",
    "notes_safe_category",
)

FORBIDDEN_CSV_COLUMNS: tuple[str, ...] = (
    "account_id",
    "order_id",
    "position_id",
    "trade_id",
    "transaction_id",
    "api_key",
    "api_secret",
    "signature",
    "header",
    "credential",
    "raw_response",
    "broker_response",
)

CSV_VALIDATION_RULE_LABELS: tuple[str, ...] = (
    "RULE_TIMESTAMP_REQUIRED_WITH_EXPLICIT_TZ_POLICY_UTC",
    "RULE_TIMESTAMP_MONOTONIC_INCREASING",
    "RULE_DUPLICATE_TIMESTAMP_BLOCKED",
    "RULE_SYMBOL_REQUIRED",
    "RULE_TIMEFRAME_REQUIRED",
    "RULE_OHLC_REQUIRED_NUMERIC",
    "RULE_HIGH_GTE_LOW",
    "RULE_SPREAD_OR_BID_ASK_REQUIRED_FOR_OFFICIAL",
    "RULE_SPREAD_MISSING_IS_REFERENCE_ONLY_AT_BEST",
    "RULE_SESSION_DERIVED_FROM_TZ_OR_PROVIDED",
    "RULE_SESSION_UNKNOWN_BLOCKED_OR_REFERENCE_ONLY",
    "RULE_SOURCE_LABEL_REQUIRED",
    "RULE_SYNTHETIC_FIXTURE_FALSE_FOR_REAL_DATA",
    "RULE_FORBIDDEN_COLUMNS_BLOCKED",
    "RULE_MISSING_CANDLE_BLOCKED",
)


@dataclass(frozen=True)
class LocalCsvIntakeRequirements:
    """The fixed intake contract for the import adapter step."""

    required_columns: tuple[str, ...] = REQUIRED_CSV_COLUMNS
    spread_column_groups: tuple[tuple[str, ...], ...] = SPREAD_COLUMN_GROUPS
    optional_columns: tuple[str, ...] = OPTIONAL_CSV_COLUMNS
    forbidden_columns: tuple[str, ...] = FORBIDDEN_CSV_COLUMNS
    validation_rule_labels: tuple[str, ...] = CSV_VALIDATION_RULE_LABELS
    timezone_policy_safe_label: str = "UTC_EPOCH_OR_ISO_WITH_EXPLICIT_TZ"
    spread_policy_safe_label: str = (
        "SPREAD_OR_BID_ASK_REQUIRED_FOR_OFFICIAL_EXCLUDED_IS_REFERENCE_ONLY"
    )
    local_file_only: bool = True
    download_performed: bool = False

    def __bool__(self) -> bool:
        return False


def build_local_csv_intake_requirements() -> LocalCsvIntakeRequirements:
    return LocalCsvIntakeRequirements()


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HistoricalDataSourceDecision:
    """The step's source-route decision. Never a performance proof."""

    primary_route_safe_label: str
    secondary_route_safe_label: str
    development_only_route_safe_label: str
    blocked_routes_safe_label: str
    assessments: tuple[HistoricalDataSourceAssessment, ...]
    operator_required_actions: tuple[str, ...]
    performance_proof_status: bool = False
    live_ready: bool = False
    real_data_fetch_performed: bool = False
    unattended_live_supported: bool = False

    def __bool__(self) -> bool:
        return False


def build_historical_data_source_decision() -> HistoricalDataSourceDecision:
    """Assess the default candidates and fix the recommended route."""

    assessments = tuple(
        classify_historical_data_source(candidate)
        for candidate in build_default_source_candidates()
    )
    return HistoricalDataSourceDecision(
        primary_route_safe_label="GMO_PUBLIC_KLINES_BID_ASK_LOCAL_CSV",
        secondary_route_safe_label="GMO_MEMBER_SITE_MANUAL_EXPORT_CSV",
        development_only_route_safe_label="SYNTHETIC_FIXTURE_CONTINUED",
        blocked_routes_safe_label="ANY_CREDENTIAL_OR_API_REQUIRED_SOURCE",
        assessments=assessments,
        operator_required_actions=(
            "OPERATOR_DECIDE_SYMBOL_USD_JPY_AND_TIMEFRAME_M5_OR_OTHER",
            "OPERATOR_DECIDE_DATE_RANGE_FOR_TRAIN_VALIDATION_OOS",
            "OPERATOR_APPROVE_PUBLIC_KLINE_EXPORT_RUN_BID_AND_ASK_NEXT_STEP",
            "OPERATOR_PROVIDE_LOCAL_CSV_PATH_NEXT_STEP",
            "OPERATOR_CONFIRM_SOURCE_TERMS_ALLOW_LOCAL_ANALYSIS_USE",
        ),
    )
