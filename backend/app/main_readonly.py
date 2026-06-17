"""Read-only ASGI entrypoint for the initial deployment (docs/DEPLOYMENT_RUNBOOK.md).

Exposes ONLY `GET /health` and the read-only report routes (`/api/reports*`). It does NOT
include the order / paper / signals / bot / automation / broker endpoints that live on
`app.main:app`, so those are unreachable when this entrypoint is served. CORS is limited to
GET/OPTIONS from `FRONTEND_ORIGIN`. The full app (`app.main:app`) is left unchanged for local
development and future phases.

This app intentionally has no DB/automation lifespan: read-only report viewing reads files
under `ANALYSIS_EXPORTS_ROOT` and needs no database.

Render start command:
    uvicorn app.main_readonly:app --host 0.0.0.0 --port $PORT
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import reports

settings = get_settings()

app = FastAPI(
    title="FX Strategy Lab Reports (read-only)",
    version="0.1.0",
    description="Read-only FX report viewer API. No orders, no broker, no Private API.",
)

# Read-only public surface: allow only GET/OPTIONS from the configured frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# Only the read-only report routes. No order/paper/signals/bot/automation/broker routers.
app.include_router(reports.router)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "mode": "read-only",
        "live_trading_environment_enabled": settings.enable_live_trading,
        "live_broker_implemented": False,
    }
