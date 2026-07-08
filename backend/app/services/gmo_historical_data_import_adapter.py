"""Local CSV historical data import adapter (no-POST, no-download).

Implements the intake contract fixed by
``gmo_historical_data_source_selection``: a LOCAL-FILE-ONLY adapter that
turns an operator-provided CSV (combined OHLC+spread, or a BID/ASK kline
pair) into the existing ``BacktestDataset`` schema, fail-closed at every
step.

Hard rules enforced by construction:

- Local files only. A missing path fails closed with
  ``DATA_ADAPTER_NOT_CONFIGURED``; any URL-like or remote-scheme path and
  any directory path is blocked before a byte is read. There is no
  auto-discovery, download, HTTP, credential, or ``.env`` surface here.
- Forbidden columns (broker IDs, credentials, raw responses) block the
  intake; their values are never read into the result or echoed in errors.
- Official evaluation requires spread data (a ``spread`` column, bid/ask
  columns, or a BID/ASK file pair). OHLC-only intake is REFERENCE_ONLY at
  best, and blocked when official evaluation was requested.
- BID/ASK pair intake derives a BAR-LEVEL spread approximation and labels
  it ``SPREAD_FROM_BID_ASK_BAR_APPROXIMATION`` -- it is never presented as
  tick-level spread.
- Adapter readiness is NEVER a performance proof:
  ``performance_proof_status`` and ``live_ready`` stay false, and this
  step's runs mark ``real_data_used=false`` (real-CSV dry-run is a later,
  operator-driven step).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from app.services.gmo_historical_data_source_selection import (
    FORBIDDEN_CSV_COLUMNS,
    REQUIRED_CSV_COLUMNS,
)
from app.services.gmo_strategy_backtest_dataset import (
    DATA_ADAPTER_NOT_CONFIGURED,
    BacktestCandleRecord,
    BacktestDataset,
    BacktestSessionRecord,
    BacktestSpreadRecord,
    SessionAllowedSafeLabel,
    SpreadCategorySafeLabel,
)

SPREAD_FROM_BID_ASK_LABEL = "SPREAD_FROM_BID_ASK_BAR_APPROXIMATION"
NOT_TICK_LEVEL_LABEL = "NOT_TICK_LEVEL_SPREAD"
SESSION_FROM_TZ_LABEL = "SESSION_DERIVED_FROM_UTC_TIMESTAMP_JST_POLICY"
SESSION_SYNTHETIC_TICK_LABEL = "SESSION_DERIVED_SYNTHETIC_TICK_DEFAULT_ALLOWED"

_REMOTE_MARKERS = ("://",)
_REMOTE_PREFIXES = ("http:", "https:", "s3:", "gs:", "ftp:", "sftp:", "file:")

# JST spread-widening window (advertised spread applies 9:00-翌5:00 JST).
_JST_BLOCKED_HOURS = frozenset({5, 6, 7, 8})
_EPOCH_SECONDS_MIN = 1_000_000_000  # ~2001; below this we treat as tick index

_BID_ASK_REQUIRED_COLUMNS = (
    "timestamp",
    "symbol",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "source_label",
)


class CsvImportIntakeCategory(str, Enum):
    HISTORICAL_IMPORT_ADAPTER_READY = "HISTORICAL_IMPORT_ADAPTER_READY"
    DATA_ADAPTER_NOT_CONFIGURED_CATEGORY = DATA_ADAPTER_NOT_CONFIGURED
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
    CSV_INTAKE_BLOCKED_REMOTE_PATH = "CSV_INTAKE_BLOCKED_REMOTE_PATH"
    CSV_INTAKE_BLOCKED_BID_ASK_MISMATCH = "CSV_INTAKE_BLOCKED_BID_ASK_MISMATCH"
    CSV_INTAKE_BLOCKED_EMPTY_FILE = "CSV_INTAKE_BLOCKED_EMPTY_FILE"
    CSV_INTAKE_BLOCKED_UNSUPPORTED_FORMAT = (
        "CSV_INTAKE_BLOCKED_UNSUPPORTED_FORMAT"
    )
    CSV_INTAKE_BLOCKED_RAW_VALUE_POLICY = "CSV_INTAKE_BLOCKED_RAW_VALUE_POLICY"
    CSV_INTAKE_NOT_PROVIDED = "CSV_INTAKE_NOT_PROVIDED"


@dataclass(frozen=True)
class HistoricalCsvImportRequest:
    """Operator-declared intake request. Paths must be explicit local files."""

    symbol_safe_label: str = "USD_JPY"
    timeframe_safe_label: str = "M5"
    source_route_label: str = "GMO_PUBLIC_KLINES_BID_ASK_LOCAL_CSV"
    combined_csv_path: str | None = None
    bid_csv_path: str | None = None
    ask_csv_path: str | None = None
    official_evaluation_requested: bool = True
    # This phase runs only against synthetic temporary fixtures; the real-CSV
    # dry-run step flips this to False explicitly under operator input.
    treat_as_synthetic_fixture: bool = True


@dataclass(frozen=True)
class HistoricalCsvImportMetadata:
    """Safe-label metadata carried next to the dataset. Never raw values."""

    intake_category: CsvImportIntakeCategory
    official_evaluation_eligible: bool
    spread_included: bool
    spread_derivation_labels: tuple[str, ...]
    session_derivation_label: str
    bar_count: int
    source_route_label: str
    real_data_used: bool = False
    synthetic_fixture_only: bool = True
    performance_proof_status: bool = False
    live_ready: bool = False

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class HistoricalCsvImportResult:
    """Intake outcome. Blocked results carry safe reasons and no dataset."""

    intake_category: CsvImportIntakeCategory
    blocked_reasons: tuple[str, ...]
    dataset: BacktestDataset | None
    metadata: HistoricalCsvImportMetadata | None
    download_performed: bool = False
    real_http_performed: bool = False
    credential_value_read: bool = False
    env_read_performed: bool = False
    raw_id_value_exposure: bool = False

    def __bool__(self) -> bool:
        return False


def _blocked(
    category: CsvImportIntakeCategory, reasons: tuple[str, ...]
) -> HistoricalCsvImportResult:
    return HistoricalCsvImportResult(
        intake_category=category,
        blocked_reasons=reasons,
        dataset=None,
        metadata=None,
    )


def _normalize_column(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


_FORBIDDEN_NORMALIZED = frozenset(
    _normalize_column(name) for name in FORBIDDEN_CSV_COLUMNS
) | frozenset({"rawrequest", "rawresponse", "brokerresponse", "apikey", "apisecret"})


def _forbidden_columns_present(header: list[str]) -> bool:
    for raw_name in header:
        normalized = _normalize_column(raw_name)
        squashed = normalized.replace("_", "")
        if normalized in _FORBIDDEN_NORMALIZED or squashed in _FORBIDDEN_NORMALIZED:
            return True
    return False


def _path_check(
    path_value: str | None,
) -> tuple[Path | None, CsvImportIntakeCategory | None, str]:
    """Validate one declared path without reading file contents."""

    if path_value is None or not str(path_value).strip():
        return (None, CsvImportIntakeCategory.CSV_INTAKE_NOT_PROVIDED, "PATH_NOT_PROVIDED")
    text = str(path_value).strip()
    lowered = text.lower()
    if any(marker in lowered for marker in _REMOTE_MARKERS) or lowered.startswith(
        _REMOTE_PREFIXES
    ):
        return (
            None,
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_REMOTE_PATH,
            "REMOTE_PATH_OR_URL_BLOCKED",
        )
    path = Path(text)
    if path.is_dir():
        return (
            None,
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_UNSUPPORTED_FORMAT,
            "DIRECTORY_PATH_BLOCKED_NO_AUTO_DISCOVERY",
        )
    if not path.exists():
        return (
            None,
            CsvImportIntakeCategory.CSV_INTAKE_NOT_PROVIDED,
            "PATH_DOES_NOT_EXIST",
        )
    if path.suffix.lower() != ".csv":
        return (
            None,
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_UNSUPPORTED_FORMAT,
            "NON_CSV_FILE_BLOCKED",
        )
    return (path, None, "")


def _parse_timestamp(raw_value: str) -> tuple[int | None, str]:
    """Parse an epoch (s/ms) or explicit-TZ ISO timestamp to epoch-ms int.

    Returns (value, error_label). Ambiguous/naive timestamps fail closed.
    """

    text = (raw_value or "").strip()
    if not text:
        return (None, "TIMESTAMP_MISSING")
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        value = int(text)
        if abs(value) >= _EPOCH_SECONDS_MIN * 1000:
            return (value, "")
        if abs(value) >= _EPOCH_SECONDS_MIN:
            return (value * 1000, "")
        # Small integers are synthetic tick indices (fixtures only).
        return (value, "")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return (None, "TIMESTAMP_UNPARSEABLE")
    if parsed.tzinfo is None:
        return (None, "TIMESTAMP_TZ_MISSING")
    return (int(parsed.timestamp() * 1000), "")


def _parse_float(raw_value: str) -> float | None:
    try:
        return float(str(raw_value).strip())
    except (TypeError, ValueError):
        return None


def _derive_session_label(
    timestamp_ms: int,
) -> tuple[SessionAllowedSafeLabel, str]:
    if abs(timestamp_ms) < _EPOCH_SECONDS_MIN:
        return (
            SessionAllowedSafeLabel.SESSION_ALLOWED,
            SESSION_SYNTHETIC_TICK_LABEL,
        )
    utc_moment = datetime.fromtimestamp(timestamp_ms / 1000, UTC)
    jst_hour = (utc_moment.hour + 9) % 24
    label = (
        SessionAllowedSafeLabel.SESSION_BLOCKED
        if jst_hour in _JST_BLOCKED_HOURS
        else SessionAllowedSafeLabel.SESSION_ALLOWED
    )
    return (label, SESSION_FROM_TZ_LABEL)


@dataclass(frozen=True)
class _ParsedRow:
    timestamp_ms: int
    open_value: float
    high_value: float
    low_value: float
    close_value: float
    spread_value: float | None
    session_label: SessionAllowedSafeLabel
    session_derivation: str


def _read_csv_rows(
    path: Path,
    *,
    expected_symbol: str,
    expected_timeframe: str,
    required_columns: tuple[str, ...],
) -> tuple[list[_ParsedRow] | None, list[str], CsvImportIntakeCategory | None, list[str]]:
    """Read + validate one CSV. Returns (rows, header, block_category, reasons)."""

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = [name for name in (reader.fieldnames or [])]
        if not header:
            return (
                None,
                header,
                CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_EMPTY_FILE,
                ["CSV_EMPTY_NO_HEADER"],
            )
        if _forbidden_columns_present(header):
            return (
                None,
                header,
                CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_FORBIDDEN_COLUMNS,
                ["FORBIDDEN_COLUMN_DETECTED_VALUES_NEVER_READ"],
            )
        normalized_header = {_normalize_column(name) for name in header}
        missing = [
            column
            for column in required_columns
            if column not in normalized_header
        ]
        if missing:
            return (
                None,
                header,
                CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS,
                [f"REQUIRED_COLUMN_MISSING_{column.upper()}" for column in missing],
            )

        has_spread_column = "spread" in normalized_header
        has_bid_ask_columns = {"bid", "ask"} <= normalized_header

        rows: list[_ParsedRow] = []
        previous_ts: int | None = None
        for row in reader:
            normalized_row = {
                _normalize_column(key): value
                for key, value in row.items()
                if key is not None
            }
            timestamp_ms, ts_error = _parse_timestamp(
                normalized_row.get("timestamp", "")
            )
            if timestamp_ms is None:
                return (
                    None,
                    header,
                    CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_MISSING_TIMESTAMP_TZ,
                    [ts_error],
                )
            if previous_ts is not None:
                if timestamp_ms == previous_ts:
                    return (
                        None,
                        header,
                        CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS,
                        ["DUPLICATE_TIMESTAMP_BLOCKED"],
                    )
                if timestamp_ms < previous_ts:
                    return (
                        None,
                        header,
                        CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS,
                        ["TIMESTAMP_NOT_MONOTONIC_BLOCKED"],
                    )
            previous_ts = timestamp_ms

            if normalized_row.get("symbol", "").strip() != expected_symbol:
                return (
                    None,
                    header,
                    CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS,
                    ["SYMBOL_MISSING_OR_MISMATCH_BLOCKED"],
                )
            if normalized_row.get("timeframe", "").strip() != expected_timeframe:
                return (
                    None,
                    header,
                    CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS,
                    ["TIMEFRAME_MISSING_OR_MISMATCH_BLOCKED"],
                )
            if not normalized_row.get("source_label", "").strip():
                return (
                    None,
                    header,
                    CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS,
                    ["SOURCE_LABEL_MISSING_BLOCKED"],
                )

            ohlc = [
                _parse_float(normalized_row.get(column, ""))
                for column in ("open", "high", "low", "close")
            ]
            if any(value is None for value in ohlc):
                return (
                    None,
                    header,
                    CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS,
                    ["OHLC_MISSING_OR_NONNUMERIC_BLOCKED"],
                )
            open_v, high_v, low_v, close_v = (float(v) for v in ohlc)  # type: ignore[arg-type]
            if high_v < low_v:
                return (
                    None,
                    header,
                    CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS,
                    ["HIGH_BELOW_LOW_BLOCKED"],
                )

            spread_value: float | None = None
            if has_spread_column:
                spread_value = _parse_float(normalized_row.get("spread", ""))
                if spread_value is None or spread_value < 0:
                    return (
                        None,
                        header,
                        CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_MISSING_SPREAD,
                        ["SPREAD_VALUE_MISSING_OR_INVALID_BLOCKED"],
                    )
            elif has_bid_ask_columns:
                bid_value = _parse_float(normalized_row.get("bid", ""))
                ask_value = _parse_float(normalized_row.get("ask", ""))
                if bid_value is None or ask_value is None or ask_value < bid_value:
                    return (
                        None,
                        header,
                        CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_MISSING_SPREAD,
                        ["BID_ASK_VALUES_INVALID_BLOCKED"],
                    )
                spread_value = ask_value - bid_value

            provided_session = _normalize_column(
                normalized_row.get("session_label", "") or ""
            ).upper()
            if provided_session in (
                SessionAllowedSafeLabel.SESSION_ALLOWED.value,
                SessionAllowedSafeLabel.SESSION_BLOCKED.value,
            ):
                session_label = SessionAllowedSafeLabel(provided_session)
                session_derivation = "SESSION_PROVIDED_IN_CSV"
            else:
                session_label, session_derivation = _derive_session_label(
                    timestamp_ms
                )
            rows.append(
                _ParsedRow(
                    timestamp_ms=timestamp_ms,
                    open_value=open_v,
                    high_value=high_v,
                    low_value=low_v,
                    close_value=close_v,
                    spread_value=spread_value,
                    session_label=session_label,
                    session_derivation=session_derivation,
                )
            )

    if not rows:
        return (
            None,
            header,
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_EMPTY_FILE,
            ["CSV_EMPTY_NO_ROWS"],
        )
    return (rows, header, None, [])


def _build_dataset(
    rows: list[_ParsedRow],
    *,
    request: HistoricalCsvImportRequest,
    spread_values: list[float] | None,
    spread_derivation_labels: tuple[str, ...],
) -> HistoricalCsvImportResult:
    spread_included = spread_values is not None
    candles = tuple(
        BacktestCandleRecord(
            timestamp=row.timestamp_ms,
            symbol_safe_label=request.symbol_safe_label,
            timeframe_safe_label=request.timeframe_safe_label,
            open_value=row.open_value,
            high_value=row.high_value,
            low_value=row.low_value,
            close_value=row.close_value,
            source_label=request.source_route_label,
            synthetic_fixture=request.treat_as_synthetic_fixture,
        )
        for row in rows
    )
    spreads = tuple(
        BacktestSpreadRecord(
            timestamp=row.timestamp_ms,
            symbol_safe_label=request.symbol_safe_label,
            spread_category=(
                SpreadCategorySafeLabel.SPREAD_CATEGORY_NORMAL
                if spread_included
                else SpreadCategorySafeLabel.SPREAD_CATEGORY_UNKNOWN
            ),
            spread_value=(
                spread_values[index] if spread_values is not None else None
            ),
            source_label=request.source_route_label,
            synthetic_fixture=request.treat_as_synthetic_fixture,
        )
        for index, row in enumerate(rows)
    )
    sessions = tuple(
        BacktestSessionRecord(
            timestamp=row.timestamp_ms,
            session_safe_label=row.session_label,
            source_label=request.source_route_label,
            synthetic_fixture=request.treat_as_synthetic_fixture,
        )
        for row in rows
    )
    dataset = BacktestDataset(
        symbol_safe_label=request.symbol_safe_label,
        timeframe_safe_label=request.timeframe_safe_label,
        candles=candles,
        spreads=spreads,
        sessions=sessions,
        synthetic_fixture=request.treat_as_synthetic_fixture,
    )

    if spread_included:
        category = CsvImportIntakeCategory.CSV_INTAKE_READY_OFFICIAL_EVALUATION
        official = True
    elif request.official_evaluation_requested:
        return _blocked(
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_MISSING_SPREAD,
            ("OFFICIAL_EVALUATION_REQUESTED_BUT_SPREAD_DATA_MISSING",),
        )
    else:
        category = CsvImportIntakeCategory.CSV_INTAKE_READY_REFERENCE_ONLY
        official = False

    metadata = HistoricalCsvImportMetadata(
        intake_category=category,
        official_evaluation_eligible=official,
        spread_included=spread_included,
        spread_derivation_labels=spread_derivation_labels,
        session_derivation_label=rows[0].session_derivation,
        bar_count=len(rows),
        source_route_label=request.source_route_label,
        synthetic_fixture_only=request.treat_as_synthetic_fixture,
    )
    return HistoricalCsvImportResult(
        intake_category=category,
        blocked_reasons=(),
        dataset=dataset,
        metadata=metadata,
    )


def import_historical_csv(
    request: HistoricalCsvImportRequest,
) -> HistoricalCsvImportResult:
    """Run one local-file-only intake. Fail-closed at every stage."""

    has_combined = bool(request.combined_csv_path)
    has_pair = bool(request.bid_csv_path) or bool(request.ask_csv_path)
    if not has_combined and not has_pair:
        return _blocked(
            CsvImportIntakeCategory.DATA_ADAPTER_NOT_CONFIGURED_CATEGORY,
            ("NO_CSV_PATH_PROVIDED_FAIL_CLOSED",),
        )
    if has_combined and has_pair:
        return _blocked(
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_UNSUPPORTED_FORMAT,
            ("COMBINED_AND_PAIR_MODES_ARE_MUTUALLY_EXCLUSIVE",),
        )

    if has_combined:
        path, block_category, reason = _path_check(request.combined_csv_path)
        if path is None:
            return _blocked(block_category or (
                CsvImportIntakeCategory.CSV_INTAKE_NOT_PROVIDED
            ), (reason,))
        rows, _header, row_block, reasons = _read_csv_rows(
            path,
            expected_symbol=request.symbol_safe_label,
            expected_timeframe=request.timeframe_safe_label,
            required_columns=REQUIRED_CSV_COLUMNS,
        )
        if rows is None:
            return _blocked(
                row_block
                or CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS,
                tuple(reasons),
            )
        if all(row.spread_value is not None for row in rows) and rows[0].spread_value is not None:
            spread_values = [float(row.spread_value) for row in rows]  # type: ignore[arg-type]
            derivation: tuple[str, ...] = ("SPREAD_FROM_CSV_COLUMNS",)
        else:
            spread_values = None
            derivation = ()
        return _build_dataset(
            rows,
            request=request,
            spread_values=spread_values,
            spread_derivation_labels=derivation,
        )

    # BID/ASK pair mode: both files are required.
    if not (request.bid_csv_path and request.ask_csv_path):
        return _blocked(
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_BID_ASK_MISMATCH,
            ("BID_AND_ASK_FILES_BOTH_REQUIRED",),
        )
    parsed_sides: list[list[_ParsedRow]] = []
    for side_path_value in (request.bid_csv_path, request.ask_csv_path):
        path, block_category, reason = _path_check(side_path_value)
        if path is None:
            return _blocked(block_category or (
                CsvImportIntakeCategory.CSV_INTAKE_NOT_PROVIDED
            ), (reason,))
        rows, _header, row_block, reasons = _read_csv_rows(
            path,
            expected_symbol=request.symbol_safe_label,
            expected_timeframe=request.timeframe_safe_label,
            required_columns=_BID_ASK_REQUIRED_COLUMNS,
        )
        if rows is None:
            return _blocked(
                row_block
                or CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_INVALID_COLUMNS,
                tuple(reasons),
            )
        parsed_sides.append(rows)

    bid_rows, ask_rows = parsed_sides
    if len(bid_rows) != len(ask_rows):
        return _blocked(
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_BID_ASK_MISMATCH,
            ("BID_ASK_ROW_COUNT_MISMATCH",),
        )
    if any(
        bid.timestamp_ms != ask.timestamp_ms
        for bid, ask in zip(bid_rows, ask_rows, strict=True)
    ):
        return _blocked(
            CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_BID_ASK_MISMATCH,
            ("BID_ASK_TIMESTAMP_MISMATCH",),
        )
    spread_values: list[float] = []
    for bid, ask in zip(bid_rows, ask_rows, strict=True):
        bar_spread = ask.close_value - bid.close_value
        if bar_spread < 0:
            return _blocked(
                CsvImportIntakeCategory.CSV_INTAKE_BLOCKED_BID_ASK_MISMATCH,
                ("BID_ASK_SPREAD_DERIVATION_IMPOSSIBLE_NEGATIVE",),
            )
        spread_values.append(bar_spread)

    return _build_dataset(
        bid_rows,
        request=request,
        spread_values=spread_values,
        spread_derivation_labels=(
            SPREAD_FROM_BID_ASK_LABEL,
            NOT_TICK_LEVEL_LABEL,
        ),
    )
