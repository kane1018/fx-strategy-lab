"""Read-only FX report viewer routes (GET only).

Thin wrapper over the read-only helpers in scripts.fx_eval_common (list_report_index /
report_detail / format_*_markdown). No writes, no orders, no broker/Private API, no CSV
bodies. exports_root is server-fixed via Settings.analysis_exports_root and is NEVER
taken from the caller. See docs/fx_report_standardization_plan.md §14 / §14-16.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from scripts.fx_eval_common import (
    format_report_detail_markdown,
    format_report_index_markdown,
    list_report_index,
    report_detail,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])

# run_id is a single directory name: alphanumerics plus _ . - only (no path separators).
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")

SettingsDep = Annotated[Settings, Depends(get_settings)]


def _detail(message: str) -> dict[str, Any]:
    """Error body that never claims an unknown safety state is safe."""
    return {"error": message, "read_only_confirmed": False}


def _resolve_exports_root(settings: Settings) -> Path:
    """Server-fixed reports root, or 503 if the directory is not available."""
    root = Path(settings.analysis_exports_root)
    if not root.is_dir():
        raise HTTPException(
            status_code=503,
            detail=_detail(f"analysis_exports_root not available: {root}"),
        )
    return root


def _resolve_run_dir(run_id: str, root: Path) -> Path:
    """Validate run_id and return its directory (400 invalid, 404 missing)."""
    if ".." in run_id or "/" in run_id or not _RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(status_code=400, detail=_detail(f"invalid run_id: {run_id!r}"))
    root_resolved = root.resolve()
    run_dir = (root_resolved / run_id).resolve()
    if run_dir.parent != root_resolved:  # defense-in-depth against traversal
        raise HTTPException(status_code=400, detail=_detail("run_id escapes exports_root"))
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=_detail(f"run not found: {run_id}"))
    return run_dir


@router.get("")
def get_reports(settings: SettingsDep) -> dict[str, Any]:
    """List all runs (read-only). Broken runs come back as error rows, not failures."""
    root = _resolve_exports_root(settings)
    items = list_report_index(root)
    return {"items": items, "count": len(items)}


@router.get("/markdown")
def get_reports_markdown(settings: SettingsDep) -> dict[str, str]:
    """ChatGPT/human-friendly Markdown table of the run list (supporting view)."""
    root = _resolve_exports_root(settings)
    return {"markdown": format_report_index_markdown(list_report_index(root))}


@router.get("/{run_id}")
def get_report(run_id: str, settings: SettingsDep) -> dict[str, Any]:
    """One run's detail (read-only). CSV bodies are never returned, only file metadata."""
    root = _resolve_exports_root(settings)
    run_dir = _resolve_run_dir(run_id, root)
    try:
        return report_detail(run_dir)
    except (FileNotFoundError, ValueError) as exc:  # 0/multiple summary or malformed JSON
        raise HTTPException(status_code=422, detail=_detail(str(exc))) from exc


@router.get("/{run_id}/markdown")
def get_report_markdown(run_id: str, settings: SettingsDep) -> dict[str, str]:
    """ChatGPT/human-friendly Markdown of one run's detail (supporting view)."""
    root = _resolve_exports_root(settings)
    run_dir = _resolve_run_dir(run_id, root)
    try:
        return {"markdown": format_report_detail_markdown(report_detail(run_dir))}
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=_detail(str(exc))) from exc
