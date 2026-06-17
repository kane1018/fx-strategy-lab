"""Local-only shadow-trading domain (Phase 2A).

Pure, in-memory models for "trade-as-if" verification: normalize market data, run a
signal, build a VIRTUAL order (never sent), update a virtual position, compute virtual
PnL, and emit a shadow event. No network, no broker, no Private API, no API key, no real
orders. Not wired into any FastAPI route (not exposed by app.main_readonly:app).
See docs/PHASE2_SHADOW_TRADING_PLAN.md.
"""
