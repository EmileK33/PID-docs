#### S2-G — Entity Classes & Misc Endpoints

**Phase 2 | Backend API | Needs: S1-A, S1-D**

---

##### Objective

Build the `GET /entity-classes` endpoint and its service layer, providing the full entity-class taxonomy (ids, names, hierarchy, color codes) to the React SPA and other backend services via a Redis-cached read path.

---

##### Scope

**P0 MVP** — this session is entirely P0. The single route `GET /entity-classes` is the only P0 endpoint listed in §1.6 for this surface area. No P1 entity-class endpoints exist in the spec; no stubs are required beyond the existing `_stubs.py` placeholder already owned by S0-A.

---

##### Technology constraints

From §1.8 — Technology Stack (verbatim selections relevant to this session):

> **API Server** | FastAPI (Python) | Unifies language with ML worker codebase, eliminating cross-service interface surface; Python-first ML ecosystem

> **Database** | PostgreSQL (RDS/Aurora) | ACID, JSONB for bbox payloads, RLS, mature GDPR tooling, all entities have relational structure; schema migrations via Alembic

> **Queue / Cache / SSE pub-sub** | Redis (ElastiCache) | Three-in-one: Celery broker, subscription feature flag cache, SSE pub/sub for drawing status push; single operational dependency

**Must NOT use**: any in-process or application-level dict/LRU cache as a substitute for Redis — the spec mandates Redis as the sole caching layer and the `entity_classes:taxonomy` key must be readable by any API replica, not just the instance that first populated it. An in-memory cache would produce inconsistent behaviour across horizontally scaled replicas and would silently pass tests while violating the multi-instance contract.

**Must NOT use**: any ORM lazy-load pattern that issues N+1 queries (one query per entity class). A single `SELECT * FROM entity_class` query is required.

---

##### Performance targets

No hard SLA is directly owned by this session. The endpoint is a prerequisite for the canvas load path (`<3s P95` owned by S2-C/S3-D) and the symbol reclassification panel. Cache-aside pattern with indefinite TTL ensures the DB is queried at most once per deployment (until explicit invalidation).

> From §1.9: "Canvas load (symbol fetch) <3s P95 — Monitoring target — FastAPI `GET /drawings/{id}/symbols` + PostgreSQL JSONB bbox storage; correction history co-loaded in same response"

The entity class response must be served from Redis cache on all non-first requests to avoid contributing measurable latency to that 3-second budget.

---

##### Owned files

- `backend/app/api/routers/entity_classes.py`
- `backend/app/services/entity_class_service.py`
- `tests/integration/test_entity_classes.py`

---

##### Read-only imports

| Owning session | File path | Specific named exports required |
|---|---|---|
| S0-A | `backend/app/schemas/contracts.py` | `EntityClassId` (Pydantic-equivalent literal or `Literal` type), base schema helpers |
| S0-A | `backend/app/api/routers/__init__.py` | Router registration pattern (read for consistency; do not modify) |
| S1-A | `backend/app/db/models/entity_class.py` | `EntityClass` SQLAlchemy model |
| S1-A | `backend/app/db/session.py` | `get_db` async session dependency |
| S1-D | `backend/app/redis/cache.py` | `get_cached`, `set_cached`, `invalidate_cached` (or equivalent cache CRUD helpers) |
| S1-D | `backend/app/redis/client.py` | `get_redis_client` dependency |

---

##### Do not touch

- `backend/app/main.py` — pre-stubbed by S0-A; router inclusion already present
- `backend/app/api/routers/__init__.py` — pre-stubbed by S0-A
- `backend/app/api/routers/_stubs.py` — pre-stubbed by S0-A
- `backend/app/db/models/entity_class.py` — owned by S1-A
- `backend/app/db/seed_entity_classes.py` — owned by S1-A
- `backend/app/redis/cache.py` — owned by S1-D
- `backend/app/redis/client.py` — owned by S1-D
- `backend/app/redis/pubsub.py` — owned by S1-D
- `backend/app/db/session.py` — owned by S1-A
- All files owned by S1-B, S1-C, S1-E, S2-A through S2-F, S2-H through S2-M

---

##### Architecture context

From §1.11 — Cross-Session Runtime Patterns, Redis Cache Keys (verbatim):

> | `entity_classes:taxonomy` | FastAPI admin update | FastAPI `GET /entity-classes`; React SPA (via API) | Indefinite; invalidated on admin update |

From §1.2 — Database Schema (verbatim):

```sql
-- ENTITY_CLASS
CREATE TABLE entity_class (
  id           VARCHAR PRIMARY KEY,  -- EntityClassId values
  name         VARCHAR NOT NULL,
  parent_class VARCHAR,
  color_hex    VARCHAR NOT NULL
);
```

From §1.1 — Shared Contracts (verbatim):

```typescript
// Entity Classes (from FR-2 AC-2)
type EntityClassId =
  | 'pipe'
  | 'valve_gate'
  | 'valve_globe'
  | 'valve_ball'
  | 'valve_butterfly'
  | 'valve_check'
  | 'valve_control'
  | 'instrument';
```

From §1.3 — Feature-Tier Gate Matrix (verbatim, for context):

The entity class taxonomy is consumed by symbol correction (reclassification) and manual annotation features. No tier gate applies to reading entity classes — all tiers need the taxonomy to render the canvas.

**Design decisions imposed by spec:**

1. The cache key `entity_classes:taxonomy` is a singleton key (not per-user, not per-drawing). All users share the same taxonomy, making this a global cache entry.
2. TTL is indefinite — the Redis `SET` must not pass an expiry. Invalidation is event-driven (admin update). Since no admin update endpoint exists in P0, the practical implication is: once cached, the value persists until explicit cache eviction or Redis restart.
3. The endpoint is not listed as requiring authentication. Its only prerequisite sessions are S1-A (DB models) and S1-D (Redis) — S1-B (auth middleware) is deliberately excluded from prerequisites. The endpoint is public reference data.
4. A cache-aside pattern is mandatory: check Redis first, fall back to Postgres, write result to Redis on cache miss.
5. The service must expose an `invalidate_entity_class_cache` function as a load-bearing export even though no P0 caller invokes it — it is the hook for the future admin update path specified in §1.11.

---

##### User stories and acceptance criteria

The spec's §1.13 P0 scope references entity classes as a supporting resource for corrections and manual annotation. No dedicated numbered user story exists for the entity-class endpoint. The following stories are the consuming stories whose ACs gate this session's correctness:

**From §1.13 P0 scope (verbatim excerpt):**

> US-013: Symbol inspection panel; reclassify (predefined list only); reject; undo rejection; server persistence with optimistic save indicator

> US-014: Manual annotation (draw bounding box, assign entity class, optional tag_label, confidence 1.0, source=manual)

The direct acceptance criteria for the `GET /entity-classes` endpoint are derived from spec constraints and the consuming stories:

**EC-1 (Entity Class List — happy path):**
- Given a client calls `GET /entity-classes`
- The response status is `200 OK`
- The response body contains all 8 seeded entity class records (pipe, valve_gate, valve_globe, valve_ball, valve_butterfly, valve_check, valve_control, instrument)
- Each record contains: `id` (string, one of the EntityClassId values), `name` (string, non-empty), `parent_class` (string or null), `color_hex` (string matching `#[0-9A-Fa-f]{6}` pattern)

**EC-2 (Redis cache population on first request):**
- Given Redis has no value at key `entity_classes:taxonomy`
- When `GET /entity-classes` is called
- Then the service queries PostgreSQL
- And the result is written to Redis under key `entity_classes:taxonomy` with no TTL (indefinite)

**EC-3 (Redis cache hit on subsequent requests):**
- Given Redis already holds a value at `entity_classes:taxonomy`
- When `GET /entity-classes` is called
- Then the service does NOT query PostgreSQL
- And the cached value is returned in the response with status `200 OK`

**EC-4 (Cache invalidation function):**
- Given the `invalidate_entity_class_cache` function is called
- Then the Redis key `entity_classes:taxonomy` is deleted
- And the next `GET /entity-classes` call re-queries PostgreSQL and re-populates the cache

**EC-5 (Response structure — all required fields present):**
- The response envelope wraps the list under an `entity_classes` key (list of objects)
- No entity class record is missing `id`, `name`, or `color_hex`
- `parent_class` is present as a key even when null (not omitted from serialisation)

**EC-6 (Empty DB edge case):**
- Given entity_class table is empty (no seed data)
- When `GET /entity-classes` is called
- Then response is `200 OK` with `{ "entity_classes": [] }`
- And the empty list is cached at `entity_classes:taxonomy`

**EC-7 (Redis unavailable — graceful degradation):**
- Given Redis connection is unavailable
- When `GET /entity-classes` is called
- Then the service falls back to querying PostgreSQL directly
- And returns `200 OK` with the full entity class list
- And does NOT raise an unhandled exception or return a 5xx to the client

---

##### UX and design specification

N/A — no frontend component. This is a backend-only session producing a JSON API endpoint consumed by S3-D (Review Canvas) and S2-C (Symbols & Corrections) via their own frontend layers.

---

##### Critical implementation notes

- **Cache key must be exactly `entity_classes:taxonomy`** (verbatim from §1.11). Any variation (e.g., `entity-classes:taxonomy`, `taxonomy:entity_classes`) will break the cross-session contract with S1-D's cache management and any future admin invalidation path.

- **No TTL on cache write.** §1.11 specifies "Indefinite; invalidated on admin update." Redis `SET` must not include `EX`, `PX`, `EXAT`, or `KEEPTTL` modifiers. A TTL would cause silent stale-cache misses in production that are invisible in short-running tests.

- **Cache value must be JSON-serializable as a list of dicts**, not a SQLAlchemy model instance list. Serialize to `list[dict]` (via Pydantic `.model_dump()` or equivalent) before writing to Redis. Deserialize from JSON on cache read. Failure to serialize produces a silent write of a non-JSON-parseable value that raises a deserialization error on next read.

- **Single DB query.** `SELECT * FROM entity_class` — no joins, no lazy loads, no per-row queries. This is enforced by the `<3s P95` canvas load SLA budget that this endpoint contributes to.

- **`invalidate_entity_class_cache` is a load-bearing export** even with no P0 caller. It must be exported from `entity_class_service.py` and must delete the key (not set it to empty). Mark it `[LOAD-BEARING]` — its signature must not change after merge.

- **No authentication required.** The endpoint's prerequisites (S1-A, S1-D) deliberately exclude S1-B. Do not add an auth dependency. Adding auth would break S3-D which may call this endpoint before full auth context is established in the canvas bootstrap, and would contradict the stated dependency graph.

- **Ordering rule from §1.4, rule 5 (user_id in job payload):** not applicable to this session but do not inadvertently import auth dependencies that would create a hidden coupling to S1-B.

- **Redis graceful degradation is mandatory.** If `get_cached` raises a `ConnectionError` or `TimeoutError`, the service must catch it, log a warning, query Postgres directly, and return the result — without attempting to write back to Redis during the degraded state. Silently swallowing the Redis error while still returning a 5xx would violate the "analytics failure must not surface to users" NFR pattern (§1.10) which is the general design philosophy.

- **`parent_class` field must always be present in serialisation even when `None`** (EC-5). FastAPI/Pydantic default behaviour of omitting `None` fields must be overridden with `model_config = ConfigDict(serialize_none=True)` or equivalent. Omitting the field breaks TypeScript consumers that check `entity.parent_class === null`.

- **Endpoint path must match §1.6 exactly:** `GET /entity-classes` (hyphen, lowercase). The ORM model table is `entity_class` (underscore) but the API path uses a hyphen.

---

##### Mocking contract

**Backend session** — lists internal service interfaces consumed from other sessions:

| Dependency | Interface | Exact payload/signature |
|---|---|---|
| S1-A `EntityClass` model | SQLAlchemy ORM model | `EntityClass(id: str, name: str, parent_class: str \| None, color_hex: str)` |
| S1-A `get_db` | FastAPI dependency | `AsyncGenerator[AsyncSession, None]` |
| S1-D `get_cached(key: str) -> str \| None` | Redis GET wrapper | Returns JSON string or `None` on miss; raises `ConnectionError` on Redis unavailability |
| S1-D `set_cached(key: str, value: str, ttl: int \| None = None) -> None` | Redis SET wrapper | Writes string; `ttl=None` means no expiry |
| S1-D `invalidate_cached(key: str) -> None` | Redis DEL wrapper | Deletes the key; no-op if key absent |

**Test doubles used in isolation tests:**
- Redis: mock object with `get` returning `None` (cache miss) or a pre-serialised JSON string (cache hit)
- PostgreSQL: real test DB (via `tests/integration/fixtures/db.py` from S0-B) with S1-A seed data applied
- No Celery, no auth, no S3 — this endpoint has no dependency on any of those

---

##### Acceptance criteria checklist

- [ ] `GET /entity-classes` returns HTTP 200 with Content-Type `application/json` [EC-1]
- [ ] Response body has top-level key `entity_classes` containing a list [EC-1, EC-5]
- [ ] List contains exactly 8 items when seed data is applied (all EntityClassId values present) [EC-1]
- [ ] Each item contains `id`, `name`, `parent_class`, `color_hex` fields [EC-5]
- [ ] `id` for each record is one of: `pipe`, `valve_gate`, `valve_globe`, `valve_ball`, `valve_butterfly`, `valve_check`, `valve_control`, `instrument` [EC-1]
- [ ] `color_hex` matches pattern `#[0-9A-Fa-f]{6}` for each record [EC-1]
- [ ] `parent_class` key is present in serialised output even when value is `null` [EC-5]
- [ ] On cache miss: PostgreSQL is queried and result is written to Redis key `entity_classes:taxonomy` with no TTL [EC-2]
- [ ] On cache hit: PostgreSQL is NOT queried; cached value is returned [EC-3]
- [ ] Redis key is exactly `entity_classes:taxonomy` (not a variant) [EC-2, EC-3]
- [ ] `invalidate_entity_class_cache()` deletes the Redis key `entity_classes:taxonomy` [EC-4]
- [ ] After invalidation, next request re-queries PostgreSQL and re-populates cache [EC-4]
- [ ] Empty entity_class table returns `200 OK` with `{ "entity_classes": [] }` [EC-6]
- [ ] Empty list result is written to cache (not skipped) [EC-6]
- [ ] Redis `ConnectionError` during cache read falls back to Postgres without raising 5xx [EC-7]
- [ ] Redis `ConnectionError` during cache write is suppressed — response still returns 200 with data [EC-7]
- [ ] Endpoint requires no Authorization header — `GET /entity-classes` without any token returns 200 (not 401) [MANUAL]
- [ ] Response is a single DB query (no N+1) when cache is cold [MANUAL]

---

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation):
`tests/integration/test_entity_classes.py`

**Exact CI command:**
```bash
pytest tests/integration/test_entity_classes.py -v
```

**AC → assertion mapping:**

| AC | `it(...)` / `test(...)` block name |
|---|---|
| EC-1 — 200 status + list shape | `test_get_entity_classes_returns_200_with_all_classes` |
| EC-1 — all 8 IDs present | `test_get_entity_classes_returns_200_with_all_classes` |
| EC-1 — color_hex pattern | `test_get_entity_classes_field_shapes` |
| EC-5 — envelope key + field presence | `test_get_entity_classes_field_shapes` |
| EC-5 — parent_class not omitted when null | `test_get_entity_classes_parent_class_null_serialised` |
| EC-2 — cache miss triggers DB query + Redis write | `test_cache_miss_queries_db_and_writes_redis` |
| EC-3 — cache hit skips DB | `test_cache_hit_skips_db_query` |
| EC-2/3 — key is exactly `entity_classes:taxonomy` | `test_cache_key_is_entity_classes_taxonomy` |
| EC-4 — invalidate deletes key | `test_invalidate_entity_class_cache_deletes_key` |
| EC-4 — post-invalidate re-queries DB | `test_invalidate_then_request_re_queries_db` |
| EC-6 — empty table returns 200 with empty list | `test_empty_entity_class_table_returns_empty_list` |
| EC-6 — empty list is cached | `test_empty_list_is_written_to_cache` |
| EC-7 — Redis unavailable falls back to Postgres | `test_redis_connection_error_falls_back_to_postgres` |
| EC-7 — Redis write error does not raise 5xx | `test_redis_write_error_response_still_200` |

**Fixtures / test doubles:**

```python
# Fixture: real Postgres via tests/integration/fixtures/db.py (S0-B)
# Seeded with: backend/app/db/seed_entity_classes.py (S1-A) — all 8 EntityClass rows

# Fixture: real Redis via tests/integration/fixtures/redis.py (S0-B)

# Mock for Redis unavailability tests:
class FailingRedisClient:
    def get(self, key): raise ConnectionError("Redis down")
    def set(self, key, value, ex=None): raise ConnectionError("Redis down")
    def delete(self, key): raise ConnectionError("Redis down")

# Mock for cache-hit test:
# Pre-populate Redis with key `entity_classes:taxonomy` = JSON list of 8 EntityClass dicts
# Then assert db.execute was NOT called (patch SQLAlchemy session.execute)

# HTTP client: httpx.AsyncClient wrapping the FastAPI app (TestClient or ASGI test client)
# No auth header required (public endpoint)
```

Mock shapes for cached value must match the API response shape exactly:
```json
{
  "entity_classes": [
    {
      "id": "pipe",
      "name": "Pipe",
      "parent_class": null,
      "color_hex": "#4A90D9"
    }
    // ... 7 more
  ]
}
```
(Exact `color_hex` values come from seed data owned by S1-A; test assertions should check format pattern `#[0-9A-Fa-f]{6}`, not hardcoded hex values, to avoid coupling to seed implementation details.)

**Pre-conditions:**
- `DATABASE_URL` env var set to test Postgres instance
- `REDIS_URL` env var set to test Redis instance
- Alembic migrations `0001_initial_schema.py` applied
- `seed_entity_classes.py` executed against test DB
- No other sessions need to have merged — S1-A and S1-D ORM models/Redis helpers are the only imports, both are Phase 1 prerequisites

**Isolation rule:**
Tests in this file pass when only S2-G's PR is merged (on top of Phase 1 merges). No other Phase 2 session is required. The endpoint has no dependency on auth, workers, or other API routers.

---

##### Checkpoint

- **One-sentence observable outcome:** `GET /entity-classes` returns a `200 OK` JSON response listing all 8 entity-class records (with ids, names, parent hierarchy, and color codes), and a second call within the same process lifetime is served from Redis without hitting Postgres.
- **Shippability claim:** This PR is independently mergeable to main even if no other Phase 2 session in the same wave has merged. It depends only on S1-A (DB models) and S1-D (Redis) which are Phase 1 prerequisites.

---

##### Output and handoff

| Export | Kind | Shape | Consuming session(s) | Load-bearing? |
|---|---|---|---|---|
| `get_entity_classes` | function | `async (db: AsyncSession, redis) -> list[EntityClassResponse]` | S2-C (correction_service validates `new_class_id` against taxonomy), S3-D (canvas bootstrap) | No |
| `invalidate_entity_class_cache` | function | `async (redis) -> None` | Future admin endpoint (not in P0 scope); referenced in §1.11 | **[LOAD-BEARING]** |
| `EntityClassResponse` | Pydantic model | `{ id: str, name: str, parent_class: str \| None, color_hex: str }` | S2-C (import for type hints in correction validation), S3-D (via API response shape) | **[LOAD-BEARING]** |
| `ENTITY_CLASS_CACHE_KEY` | constant | `str = "entity_classes:taxonomy"` | S1-D cache helpers if they need to pre-warm; any future admin session | **[LOAD-BEARING]** |
| `backend/app/api/routers/entity_classes.py` | module | FastAPI router mounted at `/entity-classes` | S0-A router registration (already stubbed) | No |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/test_entity_classes.py -v",
    "file": "tests/integration/test_entity_classes.py"
  },
  "checkpoint": "GET /entity-classes returns 200 OK with all 8 entity-class records (pipe, valve_gate, valve_globe, valve_ball, valve_butterfly, valve_check, valve_control, instrument), and a second call within the same process lifetime is served from Redis under key entity_classes:taxonomy without querying Postgres.",
  "manualAcs": [
    {
      "id": "EC-PUBLIC-1",
      "text": "Endpoint requires no Authorization header — GET /entity-classes without any token returns 200 (not 401)."
    },
    {
      "id": "EC-PERF-1",
      "text": "Response is served from a single DB query (no N+1) when cache is cold — verified by query count instrumentation or SQL log inspection."
    }
  ],
  "exports": [
    {
      "kind": "function",
      "name": "get_entity_classes",
      "shape": "async (db: AsyncSession, redis: Any) => Promise<list[EntityClassResponse]>"
    },
    {
      "kind": "function",
      "name": "invalidate_entity_class_cache",
      "shape": "async (redis: Any) => Promise<None>"
    },
    {
      "kind": "type",
      "name": "EntityClassResponse",
      "shape": "{ id: str; name: str; parent_class: str | None; color_hex: str }"
    },
    {
      "kind": "type",
      "name": "ENTITY_CLASS_CACHE_KEY",
      "shape": "str"
    },
    {
      "kind": "module",
      "name": "backend/app/api/routers/entity_classes",
      "shape": "backend/app/api/routers/entity_classes.py"
    },
    {
      "kind": "module",
      "name": "backend/app/services/entity_class_service",
      "shape": "backend/app/services/entity_class_service.py"
    }
  ]
}
```