"""Router registry.

SWAP PROTOCOL (read before editing)
-----------------------------------
``app.main`` includes every router in ``all_routers`` in order. FastAPI resolves
the *first* matching route, so any router listed **before** ``stubs_router``
shadows the corresponding stub. To replace a stub with a real implementation a
downstream session:

  1. Creates its router module, e.g. ``app/api/routers/auth.py`` exposing
     ``router = APIRouter()``.
  2. Imports it here and inserts it into ``all_routers`` **above** the
     ``stubs_router`` line at its marked ``# SESSION: S2-x`` slot.

``main.py`` never changes — the include loop picks the new router automatically.
Do NOT edit ``_stubs.py``; leaving its routes in place keeps any not-yet-built
endpoint returning 501.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routers._stubs import stubs_router
from app.api.routers.account import router as account_router
from app.api.routers.auth import router as auth_router
from app.api.routers.drawings import router as drawings_router
from app.api.routers.symbols import router as symbols_router

# Real routers are inserted ABOVE stubs_router (first-match wins).
all_routers: list[APIRouter] = [
    auth_router,  # SESSION: S2-A — shadows the /auth/* stubs below
    drawings_router,  # SESSION: S2-B inserts `drawings_router` here
    symbols_router,  # SESSION: S2-C inserts `symbols_router` here
    # SESSION: S2-D inserts `exports_router` here
    # SESSION: S2-E inserts `subscription_router` / `stripe_webhook_router` here
    account_router,  # SESSION: S2-F — shadows the /account stubs
    # SESSION: S2-G inserts `entity_classes_router` here
    stubs_router,  # fallback: every §1.6 path → 501 until shadowed above
]

__all__ = ["all_routers", "stubs_router"]
