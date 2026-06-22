"""Fail-closed local JSONL audit writer for Phase 2E shadow events."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.shadow.audit_schema import (
    EVENT_FILENAMES,
    AuditSchemaError,
    build_audit_row,
    validate_run_id,
)


class AuditLogWriteError(RuntimeError):
    """A required audit row could not be validated or durably appended."""


def _ensure_not_symlink(path: Path, label: str) -> None:
    if path.exists() and path.is_symlink():
        raise AuditLogWriteError(f"shadow audit write failed: {label} must not be a symlink")


def _ensure_contained(root: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise AuditLogWriteError(
            "shadow audit write failed: resolved path escapes trusted root"
        ) from error


def write_audit_event(
    trusted_root: str | Path = "shadow_exports",
    *,
    run_id: str,
    event_type: str,
    payload: Any,
) -> Path:
    """Append one typed local event below trusted_root/run_id, raising on first failure."""
    try:
        safe_run_id = validate_run_id(run_id)
        row = build_audit_row(event_type, payload)
        if row["run_id"] != safe_run_id:
            raise AuditSchemaError(
                "payload run_id mismatch",
                field="run_id",
                value=row["run_id"],
                expected=safe_run_id,
            )

        root = Path(trusted_root)
        _ensure_not_symlink(root, "trusted_root")
        root.mkdir(parents=True, exist_ok=True)
        root_resolved = root.resolve()

        run_dir = root / safe_run_id
        _ensure_not_symlink(run_dir, "run directory")
        run_dir.mkdir(parents=True, exist_ok=True)
        _ensure_contained(root_resolved, run_dir)

        path = run_dir / EVENT_FILENAMES[event_type]
        _ensure_not_symlink(path, "event file")
        _ensure_contained(root_resolved, path)

        encoded = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with path.open("a", encoding="utf-8") as fh:
            fh.write(encoded + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return path
    except (OSError, TypeError, ValueError, AuditLogWriteError) as error:
        if isinstance(error, AuditLogWriteError):
            raise error
        raise AuditLogWriteError(f"shadow audit write failed: {error}") from error
