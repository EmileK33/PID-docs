"""Integration tests for S2-G — GET /entity-classes + entity-class service.

Covers every acceptance criterion (EC-1 .. EC-7) plus the two "manual" ACs
(public/no-auth, single-DB-query) from the S2-G brief.

SELF-CONTAINED re backing services. The authoritative ``session-tests`` CI gate
runs this file's ``test.cmd`` (``pytest tests/integration/test_entity_classes.py
-v``) WITHOUT booting the Docker fixture stack (Postgres/Redis/MinIO) — only the
separate ``integration`` workflow brings them up. So this suite must not open a
real DB or Redis connection:

* the entity_class taxonomy is served from an in-memory **SQLite** DB created
  from the S1-A ``EntityClass`` model and seeded from S1-A's
  ``ENTITY_CLASS_SEED_DATA`` (``get_db`` is overridden), and
* the Redis cache layer is replaced with a tiny in-process fake that honours the
  exact ``app.redis.cache`` async contract the service depends on
  (``get_entity_taxonomy`` / ``set_entity_taxonomy`` / ``invalidate_entity_taxonomy``).

It therefore depends only on Phase-1 (S1-A models + S1-D cache contract) and the
S0-A app scaffold; no live services. ``app.*`` modules are imported *inside*
fixtures/tests (never at import time) so the sibling S0-B smoke assertion
``test_smoke_does_not_import_app`` stays green when the whole ``tests/integration``
suite runs together.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make the backend package (``app.*``) importable when pytest runs from the repo
# root. tests/integration/test_entity_classes.py -> parents[2] == repo root.
_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# S0-A's config.py marks ML_MODEL_S3_KEY / ODA_CONVERTER_PATH as REQUIRED ("refuse
# to start"), but the S0-B harness conftest only seeds the subset its smoke suite
# needs. Provide test-safe values here — at import time, before any ``app.config``
# import — so the settings singleton can construct. setdefault leaves any value
# the harness / CI already provided untouched. This file owns none of those files.
os.environ.setdefault("ML_MODEL_S3_KEY", "models/test-model.onnx")
os.environ.setdefault("ODA_CONVERTER_PATH", "/usr/bin/ODAFileConverter")

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_EXPECTED_IDS = {
    "pipe",
    "valve_gate",
    "valve_globe",
    "valve_ball",
    "valve_butterfly",
    "valve_check",
    "valve_control",
    "instrument",
}


# --------------------------------------------------------------------------- #
# In-memory fake of the S1-D ``app.redis.cache`` taxonomy helpers
# --------------------------------------------------------------------------- #
class FakeTaxonomyCache:
    """Honours the async ``app.redis.cache`` taxonomy contract in-process.

    The service calls (via the module object, so monkeypatching the attributes
    here takes effect):

    * ``await get_entity_taxonomy() -> dict | None`` — S1-D fails open, but we
      can also be told to *raise* to exercise the service's own EC-7 read guard.
    * ``await set_entity_taxonomy(payload: dict) -> None``
    * ``await invalidate_entity_taxonomy() -> None``
    """

    def __init__(self) -> None:
        self.store: dict[str, dict] = {}
        self.get_calls = 0
        self.set_calls = 0
        self.del_calls = 0
        self.raise_on_get = False
        self.raise_on_set = False

    async def get_entity_taxonomy(self) -> dict | None:
        self.get_calls += 1
        if self.raise_on_get:
            raise ConnectionError("Redis down (read)")
        # The real key is the only key this fake ever stores under.
        return next(iter(self.store.values()), None) if self.store else None

    async def set_entity_taxonomy(self, payload: dict) -> None:
        self.set_calls += 1
        if self.raise_on_set:
            raise ConnectionError("Redis down (write)")
        from app.redis.cache import ENTITY_TAXONOMY_KEY

        self.store[ENTITY_TAXONOMY_KEY] = payload

    async def invalidate_entity_taxonomy(self) -> None:
        self.del_calls += 1
        from app.redis.cache import ENTITY_TAXONOMY_KEY

        self.store.pop(ENTITY_TAXONOMY_KEY, None)


# --------------------------------------------------------------------------- #
# SQLite engine helpers (in-memory, shared across connections)
# --------------------------------------------------------------------------- #
def _make_engine_and_factory(seed: bool):
    """Build a shared in-memory SQLite engine + session factory + query log.

    A ``StaticPool`` with a single connection keeps the in-memory DB alive and
    shared across the TestClient's request threads. The returned ``queries`` list
    accumulates every SQL statement executed against the engine so tests can
    assert the cold-cache read is a single ``SELECT`` (no N+1).
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db.models import EntityClass
    from app.db.seed_entity_classes import ENTITY_CLASS_SEED_DATA

    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    EntityClass.__table__.create(bind=engine)

    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)

    if seed:
        with factory() as session:
            for record in ENTITY_CLASS_SEED_DATA:
                session.add(EntityClass(**record))
            session.commit()

    queries: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ARG001
        queries.append(statement)

    return engine, factory, queries


def _entity_class_selects(queries: list[str]) -> list[str]:
    return [
        q
        for q in queries
        if q.lstrip().upper().startswith("SELECT") and "entity_class" in q.lower()
    ]


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def fake_cache() -> FakeTaxonomyCache:
    return FakeTaxonomyCache()


@pytest.fixture
def client_factory(monkeypatch, fake_cache):
    """Return a builder for a TestClient over the REAL app.

    The builder swaps the S1-D cache helpers for ``fake_cache`` and overrides
    ``get_db`` with a SQLite session. ``seed=False`` exercises the empty-table
    edge case (EC-6). Yields ``(make_client, fake_cache, get_queries)``.
    """
    created_apps: list = []

    def make_client(seed: bool = True):
        from app.db.session import get_db
        from app.main import app
        from app.redis import cache as cache_mod

        engine, factory, queries = _make_engine_and_factory(seed=seed)

        # Replace the S1-D cache helpers (looked up on the module at call time).
        monkeypatch.setattr(cache_mod, "get_entity_taxonomy", fake_cache.get_entity_taxonomy)
        monkeypatch.setattr(cache_mod, "set_entity_taxonomy", fake_cache.set_entity_taxonomy)
        monkeypatch.setattr(cache_mod, "invalidate_entity_taxonomy", fake_cache.invalidate_entity_taxonomy)

        def override_get_db():
            session = factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        created_apps.append((app, get_db, engine))
        return TestClient(app), queries

    yield make_client

    # Clean up shared-app state so sibling test files are unaffected.
    for app, get_db, engine in created_apps:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _build_envelope():
    """The exact cached payload shape (response envelope), built from seed data."""
    from app.db.seed_entity_classes import ENTITY_CLASS_SEED_DATA

    return {"entity_classes": [dict(r) for r in ENTITY_CLASS_SEED_DATA]}


# --------------------------------------------------------------------------- #
# EC-1 — happy path: 200 + all 8 classes
# --------------------------------------------------------------------------- #
def test_get_entity_classes_returns_200_with_all_classes(client_factory):
    client, _ = client_factory(seed=True)
    resp = client.get("/entity-classes")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert "entity_classes" in body
    items = body["entity_classes"]
    assert isinstance(items, list)
    assert len(items) == 8
    assert {item["id"] for item in items} == _EXPECTED_IDS


# --------------------------------------------------------------------------- #
# EC-1 / EC-5 — field shapes, envelope key, color_hex pattern
# --------------------------------------------------------------------------- #
def test_get_entity_classes_field_shapes(client_factory):
    client, _ = client_factory(seed=True)
    body = client.get("/entity-classes").json()

    assert set(body.keys()) == {"entity_classes"}
    for item in body["entity_classes"]:
        # Every required field present (EC-5).
        assert set(item.keys()) >= {"id", "name", "parent_class", "color_hex"}
        assert item["id"] in _EXPECTED_IDS
        assert isinstance(item["name"], str) and item["name"]
        assert _HEX_COLOR.match(item["color_hex"]), f"bad color_hex: {item['color_hex']!r}"


# --------------------------------------------------------------------------- #
# EC-5 — parent_class present (as null) even when None
# --------------------------------------------------------------------------- #
def test_get_entity_classes_parent_class_null_serialised(client_factory):
    client, _ = client_factory(seed=True)
    items = {i["id"]: i for i in client.get("/entity-classes").json()["entity_classes"]}

    # The key must be present, not omitted, when the value is null.
    for top_level in ("pipe", "instrument"):
        assert "parent_class" in items[top_level]
        assert items[top_level]["parent_class"] is None

    # Valves carry their parent class.
    for valve in ("valve_gate", "valve_globe", "valve_ball", "valve_butterfly", "valve_check", "valve_control"):
        assert items[valve]["parent_class"] == "valve"


# --------------------------------------------------------------------------- #
# EC-2 — cache miss queries DB and writes Redis
# --------------------------------------------------------------------------- #
def test_cache_miss_queries_db_and_writes_redis(client_factory, fake_cache):
    client, queries = client_factory(seed=True)
    queries.clear()

    resp = client.get("/entity-classes")

    assert resp.status_code == 200
    # DB was queried on the miss...
    assert _entity_class_selects(queries), "cache miss must query Postgres/SQLite"
    # ...and the result was written back to the cache exactly once.
    assert fake_cache.set_calls == 1
    assert fake_cache.store, "cache must be populated on miss"
    cached = next(iter(fake_cache.store.values()))
    assert len(cached["entity_classes"]) == 8


# --------------------------------------------------------------------------- #
# EC-3 — cache hit skips the DB
# --------------------------------------------------------------------------- #
def test_cache_hit_skips_db_query(client_factory, fake_cache):
    from app.redis.cache import ENTITY_TAXONOMY_KEY

    # Pre-populate the cache.
    fake_cache.store[ENTITY_TAXONOMY_KEY] = _build_envelope()

    client, queries = client_factory(seed=True)
    queries.clear()

    resp = client.get("/entity-classes")

    assert resp.status_code == 200
    assert len(resp.json()["entity_classes"]) == 8
    # The DB must NOT be touched on a hit.
    assert _entity_class_selects(queries) == [], "cache hit must not query the DB"
    # And we must not re-write the cache on a hit.
    assert fake_cache.set_calls == 0
    assert fake_cache.get_calls >= 1


# --------------------------------------------------------------------------- #
# EC-2/3 — the cache key is exactly entity_classes:taxonomy
# --------------------------------------------------------------------------- #
def test_cache_key_is_entity_classes_taxonomy(client_factory, fake_cache):
    from app.redis.cache import ENTITY_TAXONOMY_KEY
    from app.services.entity_class_service import ENTITY_CLASS_CACHE_KEY

    assert ENTITY_CLASS_CACHE_KEY == "entity_classes:taxonomy"
    # The service constant must agree with S1-D's key (no drift).
    assert ENTITY_CLASS_CACHE_KEY == ENTITY_TAXONOMY_KEY

    client, _ = client_factory(seed=True)
    client.get("/entity-classes")

    assert list(fake_cache.store.keys()) == ["entity_classes:taxonomy"]


# --------------------------------------------------------------------------- #
# EC-4 — invalidate deletes the key
# --------------------------------------------------------------------------- #
def test_invalidate_entity_class_cache_deletes_key(monkeypatch, fake_cache):
    from app.redis import cache as cache_mod
    from app.redis.cache import ENTITY_TAXONOMY_KEY
    from app.services.entity_class_service import invalidate_entity_class_cache

    monkeypatch.setattr(cache_mod, "invalidate_entity_taxonomy", fake_cache.invalidate_entity_taxonomy)
    fake_cache.store[ENTITY_TAXONOMY_KEY] = _build_envelope()

    asyncio.run(invalidate_entity_class_cache())

    assert ENTITY_TAXONOMY_KEY not in fake_cache.store
    assert fake_cache.del_calls == 1


# --------------------------------------------------------------------------- #
# EC-4 — after invalidation the next request re-queries the DB and re-populates
# --------------------------------------------------------------------------- #
def test_invalidate_then_request_re_queries_db(client_factory, fake_cache):
    from app.services.entity_class_service import invalidate_entity_class_cache

    client, queries = client_factory(seed=True)

    # Warm the cache.
    client.get("/entity-classes")
    assert fake_cache.store
    assert fake_cache.set_calls == 1

    # Invalidate, then request again → DB re-queried, cache re-populated.
    asyncio.run(invalidate_entity_class_cache())
    assert not fake_cache.store

    queries.clear()
    resp = client.get("/entity-classes")

    assert resp.status_code == 200
    assert _entity_class_selects(queries), "post-invalidation request must re-query the DB"
    assert fake_cache.set_calls == 2
    assert fake_cache.store


# --------------------------------------------------------------------------- #
# EC-6 — empty table returns 200 with an empty list
# --------------------------------------------------------------------------- #
def test_empty_entity_class_table_returns_empty_list(client_factory):
    client, _ = client_factory(seed=False)
    resp = client.get("/entity-classes")

    assert resp.status_code == 200
    assert resp.json() == {"entity_classes": []}


# --------------------------------------------------------------------------- #
# EC-6 — the empty list is written to the cache (not skipped)
# --------------------------------------------------------------------------- #
def test_empty_list_is_written_to_cache(client_factory, fake_cache):
    client, _ = client_factory(seed=False)
    client.get("/entity-classes")

    assert fake_cache.set_calls == 1
    cached = next(iter(fake_cache.store.values()))
    assert cached == {"entity_classes": []}


# --------------------------------------------------------------------------- #
# EC-7 — Redis read error falls back to Postgres (no 5xx)
# --------------------------------------------------------------------------- #
def test_redis_connection_error_falls_back_to_postgres(client_factory, fake_cache):
    fake_cache.raise_on_get = True

    client, _ = client_factory(seed=True)
    resp = client.get("/entity-classes")

    assert resp.status_code == 200
    assert len(resp.json()["entity_classes"]) == 8


# --------------------------------------------------------------------------- #
# EC-7 — Redis write error does not surface as a 5xx
# --------------------------------------------------------------------------- #
def test_redis_write_error_response_still_200(client_factory, fake_cache):
    fake_cache.raise_on_set = True

    client, _ = client_factory(seed=True)
    resp = client.get("/entity-classes")

    assert resp.status_code == 200
    assert len(resp.json()["entity_classes"]) == 8


# --------------------------------------------------------------------------- #
# EC-PUBLIC-1 (manual AC) — no Authorization header required
# --------------------------------------------------------------------------- #
def test_no_auth_header_returns_200(client_factory):
    client, _ = client_factory(seed=True)
    # TestClient sends no Authorization header by default.
    resp = client.get("/entity-classes")
    assert resp.status_code == 200
    assert resp.status_code != 401


# --------------------------------------------------------------------------- #
# EC-PERF-1 (manual AC) — cold cache is served by a single DB query (no N+1)
# --------------------------------------------------------------------------- #
def test_cold_cache_single_db_query(client_factory):
    client, queries = client_factory(seed=True)
    queries.clear()

    client.get("/entity-classes")

    selects = _entity_class_selects(queries)
    assert len(selects) == 1, f"expected exactly one entity_class SELECT, got {selects}"
