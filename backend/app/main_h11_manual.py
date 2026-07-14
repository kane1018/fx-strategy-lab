"""Local-only H-11 manual signal UI entrypoint.

Start only through ``python -m scripts.h11_manual_ui``. This application has no
broker/order/credential routes and is intentionally separate from both
``app.main`` and the public ``app.main_readonly`` deployment.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.h11_manual.api import router
from app.h11_manual.service import ManualSignalService

STATIC_ROOT = Path(__file__).resolve().parent / "h11_manual" / "static"
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}

app = FastAPI(
    title="FX Strategy Lab Manual Signals (local-only)",
    version="1.0.0",
    description="Local-only directional signal viewer. No broker, credentials, or orders.",
)


@app.middleware("http")
async def localhost_only(request: Request, call_next):
    host = request.url.hostname or ""
    if host not in ALLOWED_HOSTS:
        return JSONResponse(status_code=403, content={"detail": "localhost only"})
    return await call_next(request)


app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="manual-static")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "mode": "local-manual-signal",
        "screen": "シグナル",
        "safety": ManualSignalService.safety_flags(),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")
