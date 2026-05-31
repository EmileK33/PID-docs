"""FastAPI application entry point.

[LOAD-BEARING] Exports the ``app`` instance consumed by every backend test and
by ``uvicorn app.main:app``. This is the one session permitted to author this
file; after merge it becomes a "do not touch" entry point.

The router include loop is load-bearing: it iterates ``all_routers`` so
downstream sessions can swap a stub for a real router by editing
``app/api/routers/__init__.py`` alone (see SWAP PROTOCOL there) — never this file.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.api.routers import all_routers
from app.config import settings

app = FastAPI(
    title="PID Analyzer API",
    version="0.1.0",
    description="P&ID drawing analysis API. Phase-0 scaffold — most endpoints return 501.",
)


@app.get("/healthz", tags=["health"])
def healthz() -> dict[str, str]:
    """Checkpoint signal — the only non-501 endpoint in the scaffold."""
    return {"status": "ok"}


# Include every router. Order matters: real routers (added by downstream
# sessions) precede ``stubs_router`` so they shadow the corresponding stubs.
for _router in all_routers:
    app.include_router(_router)


# Touch settings so a misconfigured environment fails fast at import time
# (config.py exits the process if a REQUIRED §1.12 variable is missing).
_ = settings.ENVIRONMENT
