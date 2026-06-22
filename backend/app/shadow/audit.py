"""Fail-closed local JSONL audit writer for Phase 2E-1 shadow events."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from app.shadow.risk import SCHEMA_VERSION

AUDIT_EVENT_TYPES = frozenset({
    "signal_decision_log",
    "candidate_log",
    "risk_decision_log",
    "virtual_result_log",
    "kill_switch_log",
})

_FORBIDDEN_KEYS = frozenset({
    "api_key",
    "secret",
    "token",
    "password",
    "account_id",
    "broker_order_id",
})


class AuditLogWriteError(RuntimeError):
    """A required audit row could not be validated or durably appended."""


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_jsonable(item) for item in value]
    return value


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).lower() in _FORBIDDEN_KEYS or _contains_forbidden_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def write_audit_event(
    run_dir: str | Path,
    *,
    event_type: str,
    payload: Any,
) -> Path:
    """Append one validated local event, raising on the first failure (fail closed)."""
    try:
        if event_type not in AUDIT_EVENT_TYPES:
            raise ValueError("unsupported shadow audit event_type")
        row = _jsonable(payload)
        if not isinstance(row, dict):
            raise ValueError("audit payload must be an object")
        row = {"schema_version": SCHEMA_VERSION, "event_type": event_type, **row}
        if row.get("schema_version") != SCHEMA_VERSION or row.get("event_type") != event_type:
            raise ValueError("audit safety fields cannot be overridden")
        if not row.get("run_id") or not row.get("timestamp"):
            raise ValueError("audit row requires run_id and timestamp")
        if _contains_forbidden_key(row):
            raise ValueError("audit row contains a forbidden secret/account field")

        directory = Path(run_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{event_type}.jsonl"
        encoded = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with path.open("a", encoding="utf-8") as fh:
            fh.write(encoded + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return path
    except (OSError, TypeError, ValueError) as error:
        raise AuditLogWriteError(f"shadow audit write failed: {error}") from error
