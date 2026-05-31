"""S2-G — Entity-class taxonomy read service (cache-aside over Redis + Postgres).

Implements the single read path behind ``GET /entity-classes``: a cache-aside
lookup that checks Redis first (key ``entity_classes:taxonomy``, §1.11), falls
back to a single ``SELECT * FROM entity_class`` on a miss, and writes the result
back to Redis with **no TTL** (indefinite; invalidated only on admin update).

Interface notes (why this diverges from the brief's assumed signatures)
-----------------------------------------------------------------------
The brief sketches the S1-D cache contract as generic ``get_cached`` /
``set_cached`` / ``invalidate_cached`` helpers and the DB dependency as an
``AsyncSession``. The merged Phase-1 code is different, and this module binds to
the *real* contracts:

* S1-D (``app.redis.cache``) exposes purpose-built, fail-open async helpers —
  ``get_entity_taxonomy`` / ``set_entity_taxonomy`` / ``invalidate_entity_taxonomy``
  — that operate on the process-wide Redis singleton (``app.redis.client``)
  rather than an injected client. The taxonomy key constant lives there too.
* S1-A (``app.db.session.get_db``) yields a **synchronous** SQLAlchemy ``Session``.

These functions are therefore ``async`` (the cache helpers are coroutines) but
issue a single synchronous DB query. The optional ``redis`` parameter on the
public functions is accepted only for forward-compatibility with the published
handoff signature (``async (db, redis)`` / ``async (redis)``); it is ignored
because the S1-D layer manages its own connection.

LOAD-BEARING exports
--------------------
* ``ENTITY_CLASS_CACHE_KEY`` — the exact Redis key ``entity_classes:taxonomy``.
* ``EntityClassResponse`` — the per-record response schema (S2-C type hints,
  S3-D response shape). ``parent_class`` is always serialised, even when null.
* ``invalidate_entity_class_cache`` — admin-update cache hook (§1.11); no P0
  caller, signature frozen post-merge.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EntityClass
from app.redis import cache as taxonomy_cache

logger = logging.getLogger("pid.services.entity_class")

# [LOAD-BEARING] Exact §1.11 key. Re-exported from S1-D's cache module so the two
# can never drift — a literal here that disagreed with S1-D would silently split
# the cache across reader/writer.
ENTITY_CLASS_CACHE_KEY: str = taxonomy_cache.ENTITY_TAXONOMY_KEY  # "entity_classes:taxonomy"

# Top-level envelope key for both the HTTP response body and the cached payload.
_ENVELOPE_KEY = "entity_classes"

# Redis failures we tolerate for graceful degradation (EC-7). ConnectionError and
# TimeoutError are subclasses of OSError.
_REDIS_ERRORS = (RedisError, OSError)


class EntityClassResponse(BaseModel):
    """[LOAD-BEARING] One entity-class record (§1.1 / §1.2).

    ``parent_class`` is a normal optional field; Pydantic v2 keeps ``None`` in
    ``model_dump()`` / response serialisation by default, so the key is always
    present (EC-5) for TypeScript consumers testing ``parent_class === null``.
    ``from_attributes`` lets us validate straight from the SQLAlchemy row.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    parent_class: Optional[str] = None
    color_hex: str


class EntityClassListResponse(BaseModel):
    """Response envelope: the taxonomy wrapped under ``entity_classes`` (EC-5)."""

    entity_classes: list[EntityClassResponse]


async def get_entity_classes(db: Session, redis: Any = None) -> list[EntityClassResponse]:
    """Return the full entity-class taxonomy, cache-aside (EC-1..EC-3, EC-6/7).

    1. Read Redis (``entity_classes:taxonomy``). On a hit, deserialise and return
       without touching the DB.
    2. On a miss — or any Redis read error (fall open, EC-7) — run a single
       ``SELECT`` over ``entity_class`` and write the result back to Redis with no
       TTL. A write-time Redis error is suppressed so the request still succeeds.

    ``redis`` is accepted for handoff-signature compatibility but unused (see the
    module docstring): the S1-D cache helpers use the Redis singleton.
    """
    try:
        cached = await taxonomy_cache.get_entity_taxonomy()
    except _REDIS_ERRORS as exc:  # pragma: no cover - S1-D already fails open
        logger.warning("entity-class cache read failed; falling back to DB: %s", exc)
        cached = None

    if cached is not None:
        records = cached.get(_ENVELOPE_KEY, [])
        return [EntityClassResponse(**record) for record in records]

    # Cache miss: a single query, no joins, no lazy loads (N+1 forbidden).
    rows = db.execute(select(EntityClass)).scalars().all()
    results = [EntityClassResponse.model_validate(row) for row in rows]

    # Write-back with NO TTL (indefinite, §1.11). Suppress Redis errors so a
    # degraded cache never turns a successful read into a 5xx (EC-7).
    payload = {_ENVELOPE_KEY: [item.model_dump() for item in results]}
    try:
        await taxonomy_cache.set_entity_taxonomy(payload)
    except _REDIS_ERRORS as exc:
        logger.warning("entity-class cache write failed (serving from DB anyway): %s", exc)

    return results


async def invalidate_entity_class_cache(redis: Any = None) -> None:
    """[LOAD-BEARING] Delete the cached taxonomy (§1.11 admin-update hook).

    Deletes the ``entity_classes:taxonomy`` key (does not set it to empty), so the
    next ``get_entity_classes`` re-queries Postgres and re-populates the cache
    (EC-4). No P0 caller invokes this; it is the hook for the future admin update
    path. ``redis`` is accepted for handoff compatibility but unused.
    """
    await taxonomy_cache.invalidate_entity_taxonomy()


__all__ = [
    "ENTITY_CLASS_CACHE_KEY",
    "EntityClassResponse",
    "EntityClassListResponse",
    "get_entity_classes",
    "invalidate_entity_class_cache",
]
