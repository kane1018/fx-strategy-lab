"""Versioned local-only audit schema for Phase 2E shadow safety logs."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from app.shadow.risk import (
    SCHEMA_VERSION,
    Disposition,
    KillSwitchReason,
    RejectReason,
    RiskStatus,
    SignalLabel,
    SpreadProvenance,
    SupplementalReason,
    canonical_timestamp,
)

SAFETY_EXPECTED: dict[str, bool] = {
    "real_order": False,
    "private_api_used": False,
    "api_key_used": False,
    "no_order_execution": True,
    "live_trading_environment_enabled": False,
    "gmo_order_enabled": False,
}

AUDIT_EVENT_TYPES = frozenset({
    "signal_decision_log",
    "candidate_log",
    "risk_decision_log",
    "virtual_result_log",
    "kill_switch_log",
})

EVENT_FILENAMES = {
    "signal_decision_log": "signal_decision_log.jsonl",
    "candidate_log": "candidate_log.jsonl",
    "risk_decision_log": "risk_decision_log.jsonl",
    "virtual_result_log": "virtual_result_log.jsonl",
    "kill_switch_log": "kill_switch_log.jsonl",
}

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

_FORBIDDEN_FIELD_NAMES = {
    "apikey",
    "secret",
    "token",
    "password",
    "privatekey",
    "authorization",
    "accountid",
    "brokerorderid",
    "rawresponse",
    "rawrequest",
    "rawheaders",
    "responseheaders",
    "requestheaders",
    "responsebody",
    "requestbody",
    "credentials",
}

_COMMON_FIELDS = frozenset({"schema_version", "event_type", "run_id", "timestamp"}) | frozenset(
    SAFETY_EXPECTED
)

_EVENT_ALLOWED_FIELDS = {
    "signal_decision_log": _COMMON_FIELDS
    | frozenset({
        "step_index",
        "signal_label",
        "disposition",
        "reason_codes",
        "market_data_timestamp",
        "source",
        "symbol",
        "interval",
        "signal_name",
    }),
    "candidate_log": _COMMON_FIELDS
    | frozenset({
        "candidate_id",
        "step_index",
        "market_data_timestamp",
        "source",
        "symbol",
        "interval",
        "side",
        "quantity_mode",
        "quantity",
        "entry_reference_price",
        "spread_pips",
        "spread_provenance",
        "signal_name",
        "signal_reason",
        "confidence",
        "risk_status",
        "blocked_reason",
        "created_by",
    }),
    "risk_decision_log": _COMMON_FIELDS
    | frozenset({
        "decision_id",
        "candidate_id",
        "step_index",
        "status",
        "reasons",
        "checked_policy_id",
    }),
    "virtual_result_log": _COMMON_FIELDS
    | frozenset({
        "candidate_id",
        "decision_id",
        "status",
        "position_side",
        "units",
        "unrealized_pnl",
    }),
    "kill_switch_log": _COMMON_FIELDS
    | frozenset({
        "active",
        "reasons",
        "activated_at",
        "trigger",
        "safety_snapshot",
    }),
}

_EVENT_REQUIRED_FIELDS = {
    "signal_decision_log": _COMMON_FIELDS
    | frozenset({
        "step_index",
        "signal_label",
        "disposition",
        "reason_codes",
        "market_data_timestamp",
        "source",
        "symbol",
        "interval",
        "signal_name",
    }),
    "candidate_log": _COMMON_FIELDS
    | frozenset({
        "candidate_id",
        "step_index",
        "market_data_timestamp",
        "source",
        "symbol",
        "interval",
        "side",
        "quantity_mode",
        "quantity",
        "entry_reference_price",
        "spread_pips",
        "spread_provenance",
        "signal_name",
        "signal_reason",
        "confidence",
        "risk_status",
        "blocked_reason",
        "created_by",
    }),
    "risk_decision_log": _COMMON_FIELDS
    | frozenset({
        "decision_id",
        "candidate_id",
        "step_index",
        "status",
        "reasons",
        "checked_policy_id",
    }),
    "virtual_result_log": _COMMON_FIELDS
    | frozenset({
        "candidate_id",
        "decision_id",
        "status",
        "position_side",
        "units",
        "unrealized_pnl",
    }),
    "kill_switch_log": _COMMON_FIELDS
    | frozenset({
        "active",
        "reasons",
        "activated_at",
        "trigger",
        "safety_snapshot",
    }),
}


class AuditSchemaError(ValueError):
    """A JSONL audit row violates the versioned local-only schema."""

    def __init__(
        self,
        message: str,
        *,
        field: str = "row",
        value: Any = None,
        expected: Any = "valid shadow-risk-v1 audit row",
    ) -> None:
        super().__init__(message)
        self.field = field
        self.value = value
        self.expected = expected


@dataclass(frozen=True)
class SignalDecisionAuditRecord:
    run_id: str
    timestamp: str
    step_index: int
    signal_label: SignalLabel
    disposition: Disposition
    reason_codes: tuple[SupplementalReason | RejectReason, ...]
    market_data_timestamp: str
    source: str
    symbol: str
    interval: str
    signal_name: str
    real_order: bool = False
    private_api_used: bool = False
    api_key_used: bool = False
    no_order_execution: bool = True
    live_trading_environment_enabled: bool = False
    gmo_order_enabled: bool = False


@dataclass(frozen=True)
class VirtualResultAuditRecord:
    run_id: str
    timestamp: str
    candidate_id: str
    decision_id: str
    status: str
    position_side: str
    units: int
    unrealized_pnl: float
    real_order: bool = False
    private_api_used: bool = False
    api_key_used: bool = False
    no_order_execution: bool = True
    live_trading_environment_enabled: bool = False
    gmo_order_enabled: bool = False


@dataclass(frozen=True)
class KillSwitchAuditRecord:
    run_id: str
    timestamp: str
    active: bool
    reasons: tuple[KillSwitchReason, ...]
    activated_at: str | None
    trigger: str
    safety_snapshot: dict[str, bool] = field(default_factory=lambda: dict(SAFETY_EXPECTED))
    real_order: bool = False
    private_api_used: bool = False
    api_key_used: bool = False
    no_order_execution: bool = True
    live_trading_environment_enabled: bool = False
    gmo_order_enabled: bool = False


def normalize_field_name(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return canonical_timestamp(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_jsonable(item) for item in value]
    return value


def _find_forbidden_field(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = normalize_field_name(str(key))
            if normalized in _FORBIDDEN_FIELD_NAMES:
                return str(key)
            nested = _find_forbidden_field(item)
            if nested is not None:
                return nested
    if isinstance(value, list):
        for item in value:
            nested = _find_forbidden_field(item)
            if nested is not None:
                return nested
    return None


def validate_run_id(run_id: Any) -> str:
    if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
        raise AuditSchemaError(
            "invalid run_id",
            field="run_id",
            value=run_id,
            expected="safe relative run id",
        )
    if run_id in {".", ".."} or ".." in run_id:
        raise AuditSchemaError(
            "invalid run_id",
            field="run_id",
            value=run_id,
            expected="no path traversal",
        )
    return run_id


def _expect_event_type(event_type: Any) -> str:
    if event_type not in AUDIT_EVENT_TYPES:
        raise AuditSchemaError(
            "invalid event_type",
            field="event_type",
            value=event_type,
            expected=sorted(AUDIT_EVENT_TYPES),
        )
    return str(event_type)


def _expect_timestamp(row: dict[str, Any], field_name: str) -> None:
    try:
        canonical_timestamp(row[field_name])
    except (TypeError, ValueError) as error:
        raise AuditSchemaError(
            "invalid timestamp",
            field=field_name,
            value=row.get(field_name),
            expected="timezone-aware UTC-compatible ISO timestamp",
        ) from error


def _expect_bool(row: dict[str, Any], field_name: str, expected: bool | None = None) -> None:
    value = row.get(field_name)
    if type(value) is not bool:
        raise AuditSchemaError(
            "invalid boolean field",
            field=field_name,
            value=value,
            expected="bool",
        )
    if expected is not None and value is not expected:
        raise AuditSchemaError(
            "safety flag violation",
            field=field_name,
            value=value,
            expected=expected,
        )


def _expect_int(row: dict[str, Any], field_name: str, *, minimum: int = 0) -> None:
    value = row.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise AuditSchemaError(
            "invalid integer field",
            field=field_name,
            value=value,
            expected=f"int >= {minimum}",
        )


def _expect_finite_number(
    row: dict[str, Any],
    field_name: str,
    *,
    minimum: float | None = None,
) -> None:
    value = row.get(field_name)
    if not isinstance(value, int | float) or isinstance(value, bool) or not math.isfinite(value):
        raise AuditSchemaError(
            "invalid numeric field",
            field=field_name,
            value=value,
            expected="finite number",
        )
    if minimum is not None and value < minimum:
        raise AuditSchemaError(
            "numeric field below minimum",
            field=field_name,
            value=value,
            expected=f">= {minimum}",
        )


def _expect_text(row: dict[str, Any], field_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise AuditSchemaError(
            "invalid text field",
            field=field_name,
            value=value,
            expected="non-empty string",
        )
    return value


def _expect_id(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or not _ID_RE.fullmatch(value):
        raise AuditSchemaError(
            "invalid id field",
            field=field_name,
            value=value,
            expected="safe audit id",
        )
    return value


def _expect_reason_codes(row: dict[str, Any], field_name: str, allowed: set[str]) -> None:
    value = row.get(field_name)
    if not isinstance(value, list):
        raise AuditSchemaError(
            "invalid reason code list",
            field=field_name,
            value=value,
            expected="list of known reason codes",
        )
    for reason in value:
        if reason not in allowed:
            raise AuditSchemaError(
                "invalid reason code",
                field=field_name,
                value=reason,
                expected=sorted(allowed),
            )


def _validate_safety_snapshot(row: dict[str, Any]) -> None:
    snapshot = row.get("safety_snapshot")
    if not isinstance(snapshot, dict):
        raise AuditSchemaError(
            "invalid safety_snapshot",
            field="safety_snapshot",
            value=snapshot,
            expected="object with fixed safety flags",
        )
    unknown = sorted(set(snapshot) - set(SAFETY_EXPECTED))
    if unknown:
        raise AuditSchemaError(
            "unknown nested safety field",
            field=f"safety_snapshot.{unknown[0]}",
            value=snapshot.get(unknown[0]),
            expected="known safety flag only",
        )
    for field_name, expected in SAFETY_EXPECTED.items():
        if snapshot.get(field_name) is not expected:
            raise AuditSchemaError(
                "nested safety flag violation",
                field=f"safety_snapshot.{field_name}",
                value=snapshot.get(field_name),
                expected=expected,
            )


def _validate_candidate_id(row: dict[str, Any]) -> str:
    candidate_id = _expect_id(row.get("candidate_id"), field_name="candidate_id")
    run_id = row.get("run_id")
    if isinstance(run_id, str) and not candidate_id.startswith(f"cand_{run_id}_"):
        raise AuditSchemaError(
            "candidate_id/run_id mismatch",
            field="candidate_id",
            value=candidate_id,
            expected=f"cand_{run_id}_...",
        )
    return candidate_id


def _validate_decision_id(row: dict[str, Any], candidate_id: str) -> str:
    decision_id = _expect_id(row.get("decision_id"), field_name="decision_id")
    if not decision_id.startswith(f"risk_{candidate_id}_"):
        raise AuditSchemaError(
            "decision_id/candidate_id mismatch",
            field="decision_id",
            value=decision_id,
            expected=f"risk_{candidate_id}_...",
        )
    return decision_id


def _validate_event_specific_fields(event_type: str, row: dict[str, Any]) -> None:
    if event_type == "signal_decision_log":
        _expect_int(row, "step_index")
        if row.get("signal_label") not in {item.value for item in SignalLabel}:
            raise AuditSchemaError(
                "invalid signal_label",
                field="signal_label",
                value=row.get("signal_label"),
                expected=[item.value for item in SignalLabel],
            )
        if row.get("disposition") not in {item.value for item in Disposition}:
            raise AuditSchemaError(
                "invalid disposition",
                field="disposition",
                value=row.get("disposition"),
                expected=[item.value for item in Disposition],
            )
        allowed_reasons = {item.value for item in SupplementalReason} | {
            item.value for item in RejectReason
        }
        _expect_reason_codes(row, "reason_codes", allowed_reasons)
        _expect_timestamp(row, "market_data_timestamp")
        for field_name in ("source", "symbol", "interval", "signal_name"):
            _expect_text(row, field_name)
        return

    if event_type == "candidate_log":
        _validate_candidate_id(row)
        _expect_int(row, "step_index")
        _expect_timestamp(row, "market_data_timestamp")
        for field_name in (
            "source",
            "symbol",
            "interval",
            "quantity_mode",
            "signal_name",
            "signal_reason",
            "risk_status",
            "created_by",
        ):
            _expect_text(row, field_name)
        if row.get("side") not in {SignalLabel.BUY.value, SignalLabel.SELL.value}:
            raise AuditSchemaError(
                "invalid candidate side",
                field="side",
                value=row.get("side"),
                expected=[SignalLabel.BUY.value, SignalLabel.SELL.value],
            )
        if row.get("spread_provenance") not in {item.value for item in SpreadProvenance}:
            raise AuditSchemaError(
                "invalid spread_provenance",
                field="spread_provenance",
                value=row.get("spread_provenance"),
                expected=[item.value for item in SpreadProvenance],
            )
        _expect_int(row, "quantity", minimum=1)
        _expect_finite_number(row, "entry_reference_price", minimum=0.0)
        if row.get("spread_pips") is None:
            raise AuditSchemaError(
                "missing spread_pips",
                field="spread_pips",
                value=None,
                expected="finite number",
            )
        _expect_finite_number(row, "spread_pips", minimum=0.0)
        _expect_finite_number(row, "confidence", minimum=0.0)
        if row["confidence"] > 1:
            raise AuditSchemaError(
                "confidence out of range",
                field="confidence",
                value=row["confidence"],
                expected="0 <= confidence <= 1",
            )
        _expect_reason_codes(row, "blocked_reason", {item.value for item in RejectReason})
        if row.get("risk_status") != "PENDING":
            raise AuditSchemaError(
                "invalid candidate risk_status",
                field="risk_status",
                value=row.get("risk_status"),
                expected="PENDING",
            )
        return

    if event_type == "risk_decision_log":
        candidate_id = _validate_candidate_id(row)
        _validate_decision_id(row, candidate_id)
        _expect_int(row, "step_index")
        if row.get("checked_policy_id") != "shadow-risk-policy-v1":
            raise AuditSchemaError(
                "invalid checked_policy_id",
                field="checked_policy_id",
                value=row.get("checked_policy_id"),
                expected="shadow-risk-policy-v1",
            )
        if row.get("status") not in {item.value for item in RiskStatus}:
            raise AuditSchemaError(
                "invalid risk status",
                field="status",
                value=row.get("status"),
                expected=[item.value for item in RiskStatus],
            )
        _expect_reason_codes(row, "reasons", {item.value for item in RejectReason})
        if row["status"] == RiskStatus.REJECT_SHADOW.value and not row["reasons"]:
            raise AuditSchemaError(
                "reject decision requires reasons",
                field="reasons",
                value=row["reasons"],
                expected="at least one known reject reason",
            )
        if row["status"] == RiskStatus.ALLOW_SHADOW.value and row["reasons"]:
            raise AuditSchemaError(
                "allow decision cannot have reject reasons",
                field="reasons",
                value=row["reasons"],
                expected=[],
            )
        return

    if event_type == "virtual_result_log":
        candidate_id = _validate_candidate_id(row)
        _validate_decision_id(row, candidate_id)
        if row.get("status") not in {"VIRTUAL_RESULT", "HALTED"}:
            raise AuditSchemaError(
                "invalid virtual result status",
                field="status",
                value=row.get("status"),
                expected=["VIRTUAL_RESULT", "HALTED"],
            )
        _expect_text(row, "position_side")
        _expect_int(row, "units")
        _expect_finite_number(row, "unrealized_pnl")
        return

    if event_type == "kill_switch_log":
        _expect_bool(row, "active")
        _expect_reason_codes(row, "reasons", {item.value for item in KillSwitchReason})
        if row["active"]:
            if not row["reasons"]:
                raise AuditSchemaError(
                    "active kill switch requires reasons",
                    field="reasons",
                    value=row["reasons"],
                    expected="at least one kill switch reason",
                )
            if row.get("activated_at") is None:
                raise AuditSchemaError(
                    "active kill switch requires activated_at",
                    field="activated_at",
                    value=None,
                    expected="timestamp",
                )
            _expect_timestamp(row, "activated_at")
        elif row["reasons"] or row.get("activated_at") is not None:
            raise AuditSchemaError(
                "inactive kill switch cannot hold active fields",
                field="active",
                value=row,
                expected="active=false with empty reasons and activated_at=null",
            )
        _expect_text(row, "trigger")
        _validate_safety_snapshot(row)
        return

    raise AuditSchemaError(
        "invalid event_type",
        field="event_type",
        value=event_type,
        expected=sorted(AUDIT_EVENT_TYPES),
    )


def validate_audit_row(
    event_type: str,
    row: dict[str, Any],
    *,
    expected_run_id: str | None = None,
) -> dict[str, Any]:
    event_type = _expect_event_type(event_type)
    if not isinstance(row, dict):
        raise AuditSchemaError(
            "audit row must be an object",
            field="row",
            value=type(row).__name__,
            expected="object",
        )
    forbidden = _find_forbidden_field(row)
    if forbidden is not None:
        raise AuditSchemaError(
            "forbidden audit field",
            field=forbidden,
            value="<redacted>",
            expected="field absent",
        )
    allowed = _EVENT_ALLOWED_FIELDS[event_type]
    unknown = sorted(set(row) - allowed)
    if unknown:
        raise AuditSchemaError(
            "unknown audit field",
            field=unknown[0],
            value=row.get(unknown[0]),
            expected="field absent",
        )
    missing = sorted(_EVENT_REQUIRED_FIELDS[event_type] - set(row))
    if missing:
        raise AuditSchemaError(
            "missing required audit field",
            field=missing[0],
            value=None,
            expected="present",
        )
    if row.get("schema_version") != SCHEMA_VERSION:
        raise AuditSchemaError(
            "invalid schema_version",
            field="schema_version",
            value=row.get("schema_version"),
            expected=SCHEMA_VERSION,
        )
    if row.get("event_type") != event_type:
        raise AuditSchemaError(
            "invalid event_type",
            field="event_type",
            value=row.get("event_type"),
            expected=event_type,
        )
    run_id = validate_run_id(row.get("run_id"))
    if expected_run_id is not None and run_id != expected_run_id:
        raise AuditSchemaError(
            "run_id mismatch",
            field="run_id",
            value=run_id,
            expected=expected_run_id,
        )
    _expect_timestamp(row, "timestamp")
    for field_name, expected in SAFETY_EXPECTED.items():
        _expect_bool(row, field_name, expected)
    _validate_event_specific_fields(event_type, row)
    return row


def build_audit_row(event_type: str, payload: Any) -> dict[str, Any]:
    event_type = _expect_event_type(event_type)
    if not is_dataclass(payload):
        raise AuditSchemaError(
            "audit payload must be a typed dataclass",
            field="payload",
            value=type(payload).__name__,
            expected="typed shadow audit record",
        )
    row = _jsonable(payload)
    if not isinstance(row, dict):
        raise AuditSchemaError(
            "audit payload must serialize to an object",
            field="payload",
            value=type(row).__name__,
            expected="object",
        )
    if "schema_version" in row and row["schema_version"] != SCHEMA_VERSION:
        raise AuditSchemaError(
            "schema_version cannot be overridden",
            field="schema_version",
            value=row["schema_version"],
            expected=SCHEMA_VERSION,
        )
    if "event_type" in row and row["event_type"] != event_type:
        raise AuditSchemaError(
            "event_type cannot be overridden",
            field="event_type",
            value=row["event_type"],
            expected=event_type,
        )
    row["schema_version"] = SCHEMA_VERSION
    row["event_type"] = event_type
    return validate_audit_row(event_type, row, expected_run_id=row.get("run_id"))
