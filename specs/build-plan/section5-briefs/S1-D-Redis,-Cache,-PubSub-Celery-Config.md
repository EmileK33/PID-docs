---

#### S1-D — Redis, Cache, Pub/Sub & Celery Config

**Phase 1 | Real-time/Queue | Needs: S0-A, S0-B**

##### Objective

Provide the shared Redis client, typed cache helpers (subscription flags, entity taxonomy, brute-force counters), drawing-status pub/sub layer, and Celery queue routing + Task base class that every Phase 2 API endpoint and worker imports.

##### Scope

P0 MVP only. This session contains no P1 work. All P0 cache keys, pub/sub channels, and Celery queues listed in §1.11 must be implemented; no stubs.

##### Technology constraints

From §1.8:

- **Queue / Cache / SSE pub-sub**: Redis (ElastiCache). MUST use a single Redis instance for all three concerns (Celery broker, cache, SSE pub/sub) — do not spin up separate Redis deployments.
- **Async Workers**: Celery on Redis broker. MUST NOT use any other broker (no RabbitMQ, no SQS, no in-memory). Per §1.4 rule 14: "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts."
- Python `redis-py` client (async-compatible `redis.asyncio`) for FastAPI side; `celery[redis]` for worker side.
- Connection URL sourced from `REDIS_URL`; Celery may override with `CELERY_BROKER_URL` (§1.12), falling back to `REDIS_URL`.

##### Performance targets

- `subscription:flags:{user_id}` cache: 5-minute TTL, must be read on every authenticated request without adding measurable latency. Hard contract from §1.11.
- `brute_force:{email}`: 15-minute TTL, hard security constraint from §1.9.
- SSE pub/sub fan-out: must support the ≤10-second polling fallback SLA (i.e., publishes must be non-blocking and lossless to subscribers connected at publish time). Monitoring target.
- This session owns no end-to-end SLA directly — see S2-B (SSE endpoint) and S2-J (ML worker) for downstream targets.

##### Owned files

- `backend/app/redis/__init__.py`
- `backend/app/redis/client.py`
- `backend/app/redis/cache.py`
- `backend/app/redis/pubsub.py`
- `backend/app/workers/queues.py`
- `backend/app/workers/base.py`
- `tests/integration/test_redis_pubsub.py`

##### Read-only imports

- From **S0-A** `backend/app/config.py`: settings object exposing `REDIS_URL`, `CELERY_BROKER_URL`, `ENVIRONMENT`.
- From **S0-A** `backend/app/workers/celery_app.py`: the `celery_app` instance (this session configures its queue routing and task base class but does not redefine the app).
- From **S0-A** `backend/app/schemas/contracts.py`: `DrawingStatusSSEEvent`, `DrawingProcessingState`, `TierId`, `BillingState`.
- From **S0-B** `tests/integration/conftest.py`: redis fixture (`redis_client`), event loop fixture.
- From **S0-B** `tests/integration/fixtures/redis.py`: ephemeral Redis container fixture.

##### Do not touch

- `backend/app/main.py` (entry point — scaffolded by S0-A)
- `backend/app/workers/celery_app.py` (Celery app definition — scaffolded by S0-A; this session only configures it via side-effect imports of `queues.py` / `base.py`)
- `backend/app/config.py` (owned by S0-A)
- `backend/app/api/routers/*` (owned by Phase 2 sessions)
- `backend/app/db/*` (owned by S1-A)
- `backend/app/auth/*` (owned by S1-B; `brute_force.py` there will *consume* this session's cache helpers)
- `backend/app/storage/*` (owned by S1-C)
- `backend/app/analytics/*` (owned by S1-E)
- All Phase 2 worker subdirectories (`backend/app/workers/{ingest,scan,ml,export,gdpr,notification}/`)

##### Architecture context

From §1.8:

> **Queue / Cache / SSE pub-sub** — Redis (ElastiCache). Three-in-one: Celery broker, subscription feature flag cache, SSE pub/sub for drawing status push; single operational dependency.
>
> **Async Workers** — Celery on Redis broker. Durable persistent queue (NFR-7); Redis already required for cache + SSE; Celery retry/timeout/priority support; changing broker requires worker rewrite.

From §1.11:

**Redis Cache Keys**

| Key Pattern | Written By | Read By | TTL |
|---|---|---|---|
| `subscription:flags:{user_id}` | FastAPI on login / Stripe webhook handler | FastAPI middleware (every authenticated request, feature-gate evaluation) | 5 minutes; invalidated on webhook receipt |
| `entity_classes:taxonomy` | FastAPI admin update | FastAPI `GET /entity-classes`; React SPA (via API) | Indefinite; invalidated on admin update |
| `brute_force:{email}` | FastAPI login handler | FastAPI login handler | 15-minute TTL |

**Redis Pub/Sub Channels (SSE)**

| Channel Pattern | Published By | Consumed By | Payload Shape |
|---|---|---|---|
| `drawing:status:{drawing_id}` | Ingest Worker, Scan Worker, ML Worker (on each state transition) | FastAPI SSE handler (`GET /drawings/{id}/status`) → client | `DrawingStatusSSEEvent` (see §1.1) |

**Celery Job Queue Names** (§1.11)

| Queue | Workers | Job Types |
|---|---|---|
| `ingest` | Ingest Worker (CPU) | DWG-to-raster conversion, format detection, post-storage hash verification |
| `scan` | Scan Worker (ClamAV sidecar, CPU) | Malware scan |
| `ml_inference` | ML Worker (GPU — G4dn) | Symbol detection + table extraction |
| `export` | Export Worker (CPU) | CSV/XLSX generation |
| `gdpr_erasure` | GDPR Worker (CPU, scheduled) | PII purge, anonymization |
| `notification` | Notification Worker (CPU) | SendGrid email dispatch |

From §1.1 (the SSE payload contract — verbatim):

```typescript
interface DrawingStatusSSEEvent {
  drawing_id: string;
  state: DrawingProcessingState;
  timestamp: string;               // ISO 8601 UTC
}
```

From §1.4 (relevant ordering rule):

> **14. ML job must be enqueued via persistent queue (never in-memory).** "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts."

##### User stories and acceptance criteria

N/A — this session implements no user story directly. It provides infrastructure consumed by sessions implementing US-001, US-002, US-008, US-011, US-018, US-019, US-020, and all worker-driven user stories. ACs below are technical contracts derived from §1.4, §1.9, §1.11.

##### UX and design specification

N/A — no frontend component.

##### Critical implementation notes

- **Single Redis URL, three concerns.** Use the same `REDIS_URL` for Celery broker, cache, and pub/sub. Celery may use `CELERY_BROKER_URL` if set (§1.12: "Falls back to `REDIS_URL`"). Refuse to start if `REDIS_URL` is absent (§1.12).
- **Cache key formats are load-bearing.** `subscription:flags:{user_id}`, `entity_classes:taxonomy`, `brute_force:{email}` — exact strings, no variation. S1-B's brute-force module and S2-A/S2-E's subscription handlers will format keys with these exact patterns; deviating breaks them.
- **TTLs are contracts, not suggestions.** `subscription:flags` = 300 seconds. `brute_force` = 900 seconds. `entity_classes:taxonomy` = no TTL (indefinite until invalidation). Hard-coded constants in `cache.py`.
- **Invalidation API must exist.** `cache.invalidate_subscription_flags(user_id)` is called by S2-E's Stripe webhook handler (§1.11: "invalidated on webhook receipt"). `cache.invalidate_entity_taxonomy()` is called by S2-G admin update. Both MUST be exported.
- **Pub/sub channel name is load-bearing.** `drawing:status:{drawing_id}` exactly. S2-B's SSE handler subscribes; S2-H/S2-I/S2-J workers publish. Provide `pubsub.publish_drawing_status(drawing_id, event: DrawingStatusSSEEvent)` and `pubsub.subscribe_drawing_status(drawing_id) -> AsyncIterator[DrawingStatusSSEEvent]`.
- **Publish must serialize using the §1.1 shape.** `drawing_id`, `state`, `timestamp` (ISO 8601 UTC string). No extra fields. Consumer (S2-B) deserializes with `DrawingStatusSSEEvent.model_validate_json`.
- **Celery queue routing is exhaustive and exact.** Six queues: `ingest`, `scan`, `ml_inference`, `export`, `gdpr_erasure`, `notification`. Task names use a stable prefix per queue (e.g., `ingest.*` routes to `ingest`). Phase 2 workers will register tasks under these names — if routing drifts, their tasks land on the default queue and never execute.
- **Task base class enforces retry policy.** From §1.8: "Celery retry/timeout/priority support". Base `Task` class sets `acks_late=True`, `reject_on_worker_lost=True`, default `max_retries=3` with exponential backoff. ML inference timeout default from `ML_JOB_TIMEOUT_SECONDS` env (§1.12, default 1200s) — but enforce this via `time_limit` on tasks that declare it, not globally.
- **Persistent queue requirement.** Do NOT configure Celery with `task_always_eager=True` outside test fixtures, and do NOT use in-memory result backends in production paths. Result backend uses Redis (`result_backend = REDIS_URL`).
- **Silent failure mode**: if `pubsub.publish_drawing_status` swallows Redis connection errors, drawing status updates will silently stop reaching clients — they MUST be raised so the calling worker can retry. Logging-only is wrong.
- **Silent failure mode**: if cache reads on a Redis outage block authenticated requests indefinitely, the whole API hangs. Cache `get` operations MUST use a short connect/socket timeout (e.g., 250ms) and return `None` on failure — callers treat `None` as cache miss and fall through to DB.
- **Async vs sync clients.** FastAPI code paths use `redis.asyncio.Redis`. Celery internals use the sync client embedded in `celery[redis]`. Do NOT mix: importing async client in worker task code is fine for *task body* operations but the broker/result connections are managed by Celery itself.

##### Mocking contract

This session consumes no upstream sessions' contracts beyond S0-A scaffolding and S0-B fixtures. It defines contracts consumed by:

- **S1-B** (`brute_force.py`): will call `cache.incr_brute_force(email)`, `cache.get_brute_force(email)`, `cache.clear_brute_force(email)`.
- **S2-A, S2-E**: will call `cache.set_subscription_flags(user_id, flags: dict)`, `cache.get_subscription_flags(user_id) -> dict | None`, `cache.invalidate_subscription_flags(user_id)`.
- **S2-B** (SSE): will call `pubsub.subscribe_drawing_status(drawing_id)`.
- **S2-G**: will call `cache.set_entity_taxonomy(payload: dict)`, `cache.get_entity_taxonomy() -> dict | None`, `cache.invalidate_entity_taxonomy()`.
- **S2-H, S2-I, S2-J, S2-K, S2-L, S2-M**: will register Celery tasks against `celery_app` with queue names from `workers/queues.py` and base class from `workers/base.py`.

External service: Redis (assumed reachable at `REDIS_URL`; the integration harness from S0-B provisions an ephemeral instance).

##### Acceptance criteria checklist

- [ ] `RedisClient` singleton returns a connected `redis.asyncio.Redis` instance configured from `REDIS_URL` [tech]
- [ ] Cache helper `set_subscription_flags(user_id, flags)` writes to key `subscription:flags:{user_id}` with 300-second TTL [§1.11]
- [ ] `get_subscription_flags(user_id)` returns parsed dict on hit, `None` on miss [§1.11]
- [ ] `invalidate_subscription_flags(user_id)` deletes the key; subsequent get returns `None` [§1.11]
- [ ] Cache helper `set_entity_taxonomy(payload)` writes key `entity_classes:taxonomy` with NO TTL [§1.11]
- [ ] `invalidate_entity_taxonomy()` deletes the key [§1.11]
- [ ] `incr_brute_force(email)` increments counter at key `brute_force:{email}` and sets TTL to 900 seconds on first increment [§1.9, §1.11]
- [ ] `get_brute_force(email)` returns integer count or 0 if absent [§1.11]
- [ ] `clear_brute_force(email)` deletes the key [§1.11]
- [ ] Cache `get_*` operations return `None` on Redis connection error within 250ms instead of blocking [tech — silent-failure prevention]
- [ ] `pubsub.publish_drawing_status(drawing_id, event)` publishes JSON-serialized `DrawingStatusSSEEvent` to channel `drawing:status:{drawing_id}` [§1.11]
- [ ] `pubsub.subscribe_drawing_status(drawing_id)` yields `DrawingStatusSSEEvent` objects from the channel and raises on Redis disconnect (does NOT swallow errors) [tech — silent-failure prevention]
- [ ] Published event payload contains exactly the fields `drawing_id`, `state`, `timestamp` (ISO 8601 UTC) — no extras [§1.1]
- [ ] Subscriber receives a message published after subscription start (smoke pub/sub round-trip test passes) [§1.11]
- [ ] `workers/queues.py` declares exactly six queues: `ingest`, `scan`, `ml_inference`, `export`, `gdpr_erasure`, `notification` [§1.11]
- [ ] Celery `task_routes` maps each queue's task-name prefix to its queue (e.g., `ingest.*` → `ingest`) [§1.11]
- [ ] `workers/base.py` exports a `BaseTask` class with `acks_late=True`, `reject_on_worker_lost=True`, default `max_retries=3`, exponential backoff retry policy [§1.4 rule 14, §1.8]
- [ ] Celery result backend is set to Redis (uses `REDIS_URL` / `CELERY_BROKER_URL`) [§1.8, §1.12]
- [ ] App refuses to start if `REDIS_URL` is absent or invalid [§1.12]

##### Independent Test

- **Test file path**: `tests/integration/test_redis_pubsub.py`
- **Exact CI command**: `pytest tests/integration/test_redis_pubsub.py -v`
- **AC → assertion mapping**:
  - RedisClient singleton → `it("returns_connected_async_client_from_env")`
  - subscription_flags set/get/TTL → `it("sets_subscription_flags_with_300s_ttl")`, `it("gets_subscription_flags_returns_dict_or_none")`
  - subscription_flags invalidate → `it("invalidates_subscription_flags")`
  - entity_taxonomy set without TTL → `it("sets_entity_taxonomy_indefinite_ttl")`
  - entity_taxonomy invalidate → `it("invalidates_entity_taxonomy")`
  - brute_force incr + TTL → `it("incr_brute_force_sets_900s_ttl_on_first_increment")`
  - brute_force get → `it("gets_brute_force_returns_zero_when_absent")`
  - brute_force clear → `it("clears_brute_force_counter")`
  - cache fail-open → `it("cache_get_returns_none_within_250ms_on_redis_error")`
  - publish payload shape → `it("publish_drawing_status_emits_exact_sse_payload")`
  - pub/sub round-trip → `it("subscribe_yields_published_drawing_status_event")`
  - subscribe raises on disconnect → `it("subscribe_raises_on_redis_disconnect")`
  - six queues declared → `it("declares_all_six_celery_queues")`
  - task_routes mapping → `it("routes_task_name_prefixes_to_correct_queues")`
  - BaseTask retry policy → `it("base_task_has_acks_late_and_exponential_retry")`
  - result backend Redis → `it("celery_result_backend_uses_redis_url")`
  - missing REDIS_URL refusal → `it("app_refuses_to_start_without_redis_url")`
- **Fixtures / test doubles**: `redis_client` (from S0-B `tests/integration/fixtures/redis.py`), `celery_app` (imported read-only from S0-A), `monkeypatch` for env vars, `freezegun` for TTL assertions (or direct `TTL` Redis command check), `pytest-asyncio` for async pub/sub round-trip.
- **Pre-conditions**: Ephemeral Redis container running (provided by `docker-compose.test.yml` from S0-A and `tests/integration/docker-compose.fixtures.yml` from S0-B). `REDIS_URL` env var set by conftest. No DB or S3 dependency.
- **Isolation rule**: Test passes with only S0-A and S0-B merged plus this session's PR — no sibling Phase 1 session required. Confirmed: no imports from S1-A/B/C/E/F.

##### Checkpoint

- **Observable outcome**: Running `pytest tests/integration/test_redis_pubsub.py` after this PR merges produces a green suite; manually invoking `python -c "from backend.app.redis.pubsub import publish_drawing_status; ..."` publishes to a Redis channel an external `redis-cli SUBSCRIBE 'drawing:status:*'` subscriber receives.
- **Shippability claim**: this PR is independently mergeable to main even if no other session in the same wave has merged.

##### Output and handoff

Load-bearing exports (consumers will import these by exact name/signature):

- `backend/app/redis/client.py`:
  - `get_redis() -> redis.asyncio.Redis` `[LOAD-BEARING]` — used by S1-B, S2-A, S2-B, S2-E, S2-G
- `backend/app/redis/cache.py`:
  - `set_subscription_flags(user_id: str, flags: dict) -> None` `[LOAD-BEARING]` — S2-A, S2-E
  - `get_subscription_flags(user_id: str) -> dict | None` `[LOAD-BEARING]` — S1-B middleware, all Phase 2 routers
  - `invalidate_subscription_flags(user_id: str) -> None` `[LOAD-BEARING]` — S2-E webhook
  - `set_entity_taxonomy(payload: dict) -> None` — S2-G
  - `get_entity_taxonomy() -> dict | None` — S2-G
  - `invalidate_entity_taxonomy() -> None` — S2-G
  - `incr_brute_force(email: str) -> int` `[LOAD-BEARING]` — S1-B
  - `get_brute_force(email: str) -> int` `[LOAD-BEARING]` — S1-B
  - `clear_brute_force(email: str) -> None` `[LOAD-BEARING]` — S1-B
- `backend/app/redis/pubsub.py`:
  - `publish_drawing_status(drawing_id: str, event: DrawingStatusSSEEvent) -> None` `[LOAD-BEARING]` — S2-H, S2-I, S2-J
  - `subscribe_drawing_status(drawing_id: str) -> AsyncIterator[DrawingStatusSSEEvent]` `[LOAD-BEARING]` — S2-B SSE handler
- `backend/app/workers/queues.py`:
  - `QUEUE_INGEST = "ingest"`, `QUEUE_SCAN = "scan"`, `QUEUE_ML = "ml_inference"`, `QUEUE_EXPORT = "export"`, `QUEUE_GDPR = "gdpr_erasure"`, `QUEUE_NOTIFICATION = "notification"` `[LOAD-BEARING]` — S2-H/I/J/K/L/M
  - `TASK_ROUTES: dict` `[LOAD-BEARING]`
- `backend/app/workers/base.py`:
  - `BaseTask` (Celery Task subclass) `[LOAD-BEARING]` — all Phase 2 workers register tasks via `@celery_app.task(base=BaseTask, ...)`

---

```json
{
  "test": { "cmd": "pytest tests/integration/test_redis_pubsub.py -v", "file": "tests/integration/test_redis_pubsub.py" },
  "checkpoint": "Running `pytest tests/integration/test_redis_pubsub.py` produces a green suite, and a manual publish to `drawing:status:{id}` reaches an external `redis-cli SUBSCRIBE` listener.",
  "manualAcs": [],
  "exports": [
    { "kind": "function", "name": "get_redis", "shape": "() => redis.asyncio.Redis" },
    { "kind": "function", "name": "set_subscription_flags", "shape": "(user_id: str, flags: dict) => None" },
    { "kind": "function", "name": "get_subscription_flags", "shape": "(user_id: str) => dict | None" },
    { "kind": "function", "name": "invalidate_subscription_flags", "shape": "(user_id: str) => None" },
    { "kind": "function", "name": "set_entity_taxonomy", "shape": "(payload: dict) => None" },
    { "kind": "function", "name": "get_entity_taxonomy", "shape": "() => dict | None" },
    { "kind": "function", "name": "invalidate_entity_taxonomy", "shape": "() => None" },
    { "kind": "function", "name": "incr_brute_force", "shape": "(email: str) => int" },
    { "kind": "function", "name": "get_brute_force", "shape": "(email: str) => int" },
    { "kind": "function", "name": "clear_brute_force", "shape": "(email: str) => None" },
    { "kind": "function", "name": "publish_drawing_status", "shape": "(drawing_id: str, event: DrawingStatusSSEEvent) => None" },
    { "kind": "function", "name": "subscribe_drawing_status", "shape": "(drawing_id: str) => AsyncIterator[DrawingStatusSSEEvent]" },
    { "kind": "type", "name": "BaseTask", "shape": "class BaseTask(celery.Task): acks_late=True, reject_on_worker_lost=True, max_retries=3, exponential backoff" },
    { "kind": "module", "name": "backend/app/workers/queues", "shape": "backend/app/workers/queues.py" },
    { "kind": "module", "name": "backend/app/redis/cache", "shape": "backend/app/redis/cache.py" },
    { "kind": "module", "name": "backend/app/redis/pubsub", "shape": "backend/app/redis/pubsub.py" }
  ]
}
```