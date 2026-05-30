---

#### S2-B — Drawings Endpoints + SSE Status

**Phase 2 | Backend API | Needs: S1-A, S1-B, S1-C, S1-D, S1-E**

##### Objective

Implement all drawing-lifecycle HTTP endpoints (hash-check, create, list, detail, update, delete, retry, upload-complete) plus the Server-Sent Events status stream, enforcing the two-gate blocklist pattern, free-tier monthly limit, drawing state machine, and drawing_uploaded / free_limit_reached analytics events.

##### Scope

**P0 MVP** — all work in this session is P0.

Stories covered:
- US-003 (P0): Hash-check, drawing creation, pre-signed URL issuance, upload-complete
- US-006 (P0): Drawing Library list with pagination, status badges, revision labels
- US-007 (P0): Search (filename/revision FTS) and filter (processing_state, date range)
- US-008 (P0): Processing state machine service + live SSE status stream with polling fallback
- US-009 (P0): Retry failed drawings; delete drawings including mid-processing cancellation
- US-010 (P0): `drawing_uploaded` and `free_limit_reached` analytics events
- US-018 (P0): Free-tier 3-drawing/month enforcement at job-enqueue time

No P1 work. All P1 drawing endpoints (`/drawings/compare`, `/comparisons/{id}`, `/drawings/{id}/tables`, `/table-cells/{id}`) are owned by downstream sessions and must not be touched here. Stub endpoints for those routes already exist in `backend/app/api/routers/_stubs.py` (S0-A) and must not be modified.

##### Technology constraints

**Required (from §1.8):**
- **FastAPI** (Python) — all HTTP endpoints
- **SQLAlchemy** (ORM via `backend/app/db/session.py` from S1-A) — database access
- **Celery on Redis broker** (via `backend/app/workers/celery_app.py` from S0-A and queue config from S1-D) — persistent job enqueue; **must NOT use in-memory task dispatch** (violates NFR-7 / Ordering Rule 14)
- **Redis** (via `backend/app/redis/client.py` from S1-D) — pub/sub subscription for SSE, brute-force keys, hash-check pass tracking
- **boto3 / S3 client** (via `backend/app/storage/s3_client.py` and `backend/app/storage/presigned.py` from S1-C) — pre-signed URL generation
- **Alembic** migrations owned by S1-A — do not create migrations in this session
- **PostHog** (via `backend/app/analytics/events.py` from S1-E) — analytics event emission

**Must NOT use:**
- In-memory queue or threading for job dispatch — violates Ordering Rule 14 (durable persistent queue required)
- Client-supplied `training_consent` values in this session (consent is owned by S2-C/S2-F)
- Direct Stripe or SendGrid calls in this session

##### Performance targets

| Metric | Target | Hard SLA or Monitoring |
|---|---|---|
| `GET /drawings` (Drawing Library load) | <2s P95 | Monitoring target |
| `GET /drawings/{id}/status` SSE max fallback interval | ≤10 seconds | Monitoring target |
| Pre-signed S3 URL expiry | Exactly 15 minutes (`PRESIGNED_URL_EXPIRY_SECONDS` env, default 900) | **Hard constraint (security)** |
| ML job timeout before `Failed` state | 20 min max (`ML_JOB_TIMEOUT_SECONDS` env, default 1200) | Hard SLA — enforced in Celery task config (S1-D base task); surface in `drawing_state_machine.py` documentation |

##### Owned files

```
backend/app/api/routers/drawings.py
backend/app/services/drawing_service.py
backend/app/services/hash_check_service.py
backend/app/services/upload_complete_service.py
backend/app/services/drawing_state_machine.py
backend/app/services/free_tier_counter.py
backend/app/sse/drawing_status.py
tests/integration/test_drawings_api.py
tests/integration/test_drawings_sse.py
```

##### Read-only imports

| Session | File | Named exports required |
|---|---|---|
| S0-A | `backend/app/api/routers/__init__.py` | Router registration pattern |
| S0-A | `backend/app/schemas/contracts.py` | `HashCheckRequest`, `HashCheckResponse`, `DrawingProcessingState`, `MLInferenceJobPayload`, `DrawingStatusSSEEvent`, `BoundingBox` |
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` |
| S1-A | `backend/app/db/models/stored_file.py` | `StoredFile` |
| S1-A | `backend/app/db/models/file_hash_blocklist.py` | `FileHashBlocklist` |
| S1-A | `backend/app/db/models/subscription.py` | `Subscription` |
| S1-A | `backend/app/db/models/tier.py` | `Tier` |
| S1-A | `backend/app/db/models/user.py` | `User` |
| S1-A | `backend/app/db/session.py` | `get_db` |
| S1-B | `backend/app/auth/dependencies.py` | `get_current_user`, `require_authenticated` |
| S1-B | `backend/app/auth/permissions.py` | `ROLE_PERMISSIONS`, `assert_drawing_access`, `assert_drawing_delete` |
| S1-C | `backend/app/storage/presigned.py` | `generate_upload_presigned_url`, `generate_download_presigned_url` |
| S1-C | `backend/app/storage/s3_client.py` | `get_s3_client` |
| S1-C | `backend/app/storage/blocklist.py` | `is_hash_blocked` |
| S1-D | `backend/app/redis/client.py` | `get_redis_client` |
| S1-D | `backend/app/redis/pubsub.py` | `subscribe_drawing_status`, `DRAWING_STATUS_CHANNEL` |
| S1-D | `backend/app/workers/queues.py` | `INGEST_QUEUE` |
| S1-E | `backend/app/analytics/events.py` | `emit_drawing_uploaded`, `emit_free_limit_reached` |

##### Do not touch

- `backend/app/main.py` — entry point, pre-stubbed by S0-A
- `backend/app/api/routers/__init__.py` — router registration, pre-stubbed by S0-A
- `backend/app/api/routers/_stubs.py` — P1 stub endpoints, pre-stubbed by S0-A
- `backend/app/config.py` — owned by S0-A
- `backend/app/db/base.py` — owned by S0-A
- `backend/app/db/session.py` — owned by S1-A
- `backend/app/db/models/*.py` — owned by S1-A
- `backend/alembic/versions/*.py` — owned by S1-A
- `backend/app/auth/*.py` — owned by S1-B
- `backend/app/storage/*.py` — owned by S1-C
- `backend/app/redis/*.py` — owned by S1-D
- `backend/app/workers/celery_app.py`, `backend/app/workers/queues.py`, `backend/app/workers/base.py` — owned by S0-A / S1-D
- `backend/app/analytics/*.py` — owned by S1-E
- `backend/app/api/routers/symbols.py`, `backend/app/services/correction_service.py` — owned by S2-C
- `backend/app/api/routers/exports.py` — owned by S2-D
- `backend/app/api/routers/subscription.py`, `backend/app/api/routers/stripe_webhook.py` — owned by S2-E
- `backend/app/api/routers/account.py` — owned by S2-F
- `backend/app/api/routers/entity_classes.py` — owned by S2-G
- `backend/app/workers/ingest/` — owned by S2-H
- `backend/app/workers/scan/` — owned by S2-I
- `backend/app/workers/ml/` — owned by S2-J

##### Architecture context

The following specification sections are reproduced verbatim as they directly constrain this session's implementation.

---

**From §1.1 — Shared Contracts:**

```typescript
// ML Inference Job Payload
interface MLInferenceJobPayload {
  storage_reference: string;       // S3 object key
  drawing_id: string;              // UUID
  user_id: string;                 // UUID — MUST be set at enqueue time by API layer
  page_range?: [number, number];   // optional, 1-based inclusive
}

// Drawing Processing State Machine
type DrawingProcessingState =
  | 'Pending'
  | 'Queued'
  | 'Scanning'
  | 'Processing'
  | 'Complete'
  | 'Under_Review'
  | 'Failed'
  | 'Scan_Failed';

// Hash Check Request/Response
interface HashCheckRequest {
  sha256_hash: string;
  filename: string;
  size_bytes: number;
}

interface HashCheckResponse {
  allowed: boolean;
  drawing_id?: string;
}

// SSE Drawing Status Event (Redis pub/sub → client)
interface DrawingStatusSSEEvent {
  drawing_id: string;
  state: DrawingProcessingState;
  timestamp: string;               // ISO 8601 UTC
}
```

---

**From §1.3 — Drawing Processing State Transitions:**

```typescript
const DRAWING_STATE_TRANSITIONS: Record<DrawingProcessingState, DrawingProcessingState[]> = {
  Pending:      ['Queued', 'Failed'],
  Queued:       ['Scanning', 'Failed'],
  Scanning:     ['Processing', 'Scan_Failed', 'Failed'],
  Processing:   ['Complete', 'Failed'],
  Complete:     ['Under_Review', 'Queued'],
  Under_Review: ['Queued'],
  Failed:       ['Queued'],
  Scan_Failed:  [],                // Terminal — no retry permitted
} as const;

// Under_Review trigger: first user correction action — NOT canvas open
// Retry: re-uses existing StoredFile; no new file written to S3
```

**From §1.3 — Role-Permission Matrix:**

```typescript
const ROLE_PERMISSIONS = {
  user: {
    drawing_upload:   true,
    drawing_view:     'own',
    drawing_delete:   'own',
    drawing_retry:    'own',
  },
  team_member: {
    drawing_upload:   true,
    drawing_view:     'team',
    drawing_delete:   false,       // blocked — admin only
    drawing_retry:    'team',
  },
  team_admin: {
    drawing_upload:   true,
    drawing_view:     'team',
    drawing_delete:   'team',
    drawing_retry:    'team',
  },
} as const;
```

**From §1.3 — Feature-Tier Gate Matrix:**

```typescript
const TIER_FEATURE_GATES = {
  free: {
    monthly_drawing_limit: 3,
    // ...
  },
  pro: {
    monthly_drawing_limit: null,   // unlimited
    // ...
  },
  team: {
    monthly_drawing_limit: null,
    // ...
  },
} as const;
```

---

**From §1.4 — Critical Ordering Rules (verbatim):**

> 1. **Hash check before pre-signed URL issuance.** "Client calls `POST /drawings/hash-check` with `{sha256_hash, filename, size_bytes}`. Server checks `FILE_HASH_BLOCKLIST`. If the hash is present, returns `409 Conflict` — no Drawing record is created, no S3 URL is issued." A `POST /drawings` without a valid prior hash-check pass returns `400`.

> 2. **Pre-signed URL issued only after hash-check pass.** "The upload flow enforces FR-17 AC-2 (no blocked file byte reaches S3) through a mandatory hash pre-check before pre-signed URL issuance."

> 3. **Server-side SHA-256 re-verification after storage.** "Ingest Worker performs a server-side SHA-256 verification of the stored object against the client-supplied hash... hash is also checked a second time against the blocklist to handle newly-added entries between steps 3 and 7." [NOTE: This rule is enforced in S2-H (Ingest Worker), not this session. This session provides the first gate only.]

> 4. **Upload-complete idempotency check before enqueue.** "`POST /drawings/{id}/upload-complete` is idempotent. If the Drawing record is already in `Queued` or any later processing state, the endpoint returns `200` without re-enqueuing the ingest job."

> 5. **user_id written into job payload at enqueue time by API layer.** "The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access. This is mandatory for `processing_complete` and `processing_failed` events."

> 8. **Free-tier monthly counter incremented at job enqueue, not completion.** "The counter increment must occur at the point processing is initiated (job enqueued), not at job completion, to prevent race conditions from concurrent uploads."

> 14. **ML job must be enqueued via persistent queue (never in-memory).** "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts."

---

**From §1.5 — HTTP Status Code Contracts:**

| Condition | Required code | Must never return |
|---|---|---|
| Hash blocked on `POST /drawings/hash-check` | `409 Conflict` | `200`, `400` |
| `POST /drawings` without valid prior hash-check pass | `400` | `200`, `201` |
| `POST /drawings/{id}/upload-complete` when Drawing already in `Queued` or later state (idempotent) | `200` | `201`, `409` |
| `POST /drawings/{id}/upload-complete` initial success (job enqueued) | `202` | `200`, `201` |
| Drawing deletion success | `204` | `200` |
| Unauthenticated request to protected endpoint | `401` | `403`, `200` |
| Authenticated user accessing resource they do not own | `403` | `404`, `200` |

---

**From §1.9 — Performance Targets:**

> Dashboard (Drawing Library) load: <2s P95 — Monitoring target — FastAPI + PostgreSQL (paginated 25 records, indexed queries)

> Status push to client during processing: ≤10 second polling fallback — Monitoring target — SSE via Redis pub/sub; 10s polling fallback for proxied connections

> Pre-signed S3 URL expiry: 15 minutes — Hard constraint (security) — FastAPI URL generation

---

**From §1.10 — Analytics Event Contracts (events fired in this session):**

| Event Name | Payload Shape | Code Surface That Fires It | Trigger Condition | Must NOT have happened yet | Must NEVER fire from |
|---|---|---|---|---|---|
| `drawing_uploaded` | `{ event: 'drawing_uploaded', timestamp: string (UTC ISO8601), user_id: string, drawing_id: string }` | FastAPI — `POST /drawings/{id}/upload-complete` handler | Drawing transitions to `Queued` state after upload-complete signal | Drawing must not already be in `Queued` or later state | Browser client; ML worker |
| `free_limit_reached` | `{ event: 'free_limit_reached', timestamp: string, user_id: string, drawing_id: string, subscription_id: string }` | FastAPI — processing initiation handler | Free tier user attempts to initiate processing of drawing that would exceed 3/month limit | Processing job must not be queued | Browser client; must fire before upgrade prompt is shown |

---

**From §1.11 — Cross-Session Runtime Patterns:**

Redis pub/sub channels:
> `drawing:status:{drawing_id}` — Published By: Ingest Worker, Scan Worker, ML Worker (on each state transition) — Consumed By: FastAPI SSE handler (`GET /drawings/{id}/status`) → client — Payload: `DrawingStatusSSEEvent`

Redis cache keys:
> `subscription:flags:{user_id}` — Written By: FastAPI on login / Stripe webhook handler — Read By: FastAPI middleware (every authenticated request, feature-gate evaluation) — TTL: 5 minutes; invalidated on webhook receipt

Celery queue names:
> `ingest` — Workers: Ingest Worker (CPU) — Job Types: DWG-to-raster conversion, format detection, post-storage hash verification

---

**From §1.2 — Relevant DB indexes:**

```sql
CREATE INDEX idx_drawing_team_state_date ON drawing(owner_team_id, processing_state, uploaded_at DESC);
CREATE INDEX idx_drawing_user ON drawing(owner_user_id);
CREATE INDEX idx_drawing_fts ON drawing USING GIN (to_tsvector('english', filename || ' ' || COALESCE(revision_label, '')));
CREATE INDEX idx_stored_file_hash ON stored_file(sha256_hash);
```

---

##### User stories and acceptance criteria

The following stories and ACs are derived from the P0 feature scope descriptions in §1.13 and the detailed requirements in §1.3–§1.11. Full verbatim story text is not present in the provided specification; ACs are constructed from the binding spec requirements above.

---

**US-003 — File Upload with Blocklist & Pre-signed URL Issuance**

As a user uploading a P&ID drawing, I want the system to validate my file hash against the blocklist before accepting the upload, so that blocked files never reach storage.

- **AC-1 (Hash blocked):** Given a SHA-256 hash present in `FILE_HASH_BLOCKLIST`, when I call `POST /drawings/hash-check` with `{sha256_hash, filename, size_bytes}`, then the response is `409 Conflict`, no Drawing record is created, and no S3 pre-signed URL is issued.
- **AC-2 (Hash allowed):** Given a SHA-256 hash NOT in `FILE_HASH_BLOCKLIST`, when I call `POST /drawings/hash-check`, then the response is `200 OK` with `{ allowed: true }` and the server records that this hash passed the check for this user (enabling `POST /drawings` to proceed).
- **AC-3 (POST /drawings without prior hash-check):** Given I call `POST /drawings` without having first called `POST /drawings/hash-check` for the same hash (or the hash-check result has expired), then the response is `400 Bad Request`.
- **AC-4 (POST /drawings after hash-check pass):** Given I have passed hash-check for a hash, when I call `POST /drawings` with valid `{filename, sha256_hash, size_bytes, file_type}`, then a Drawing record is created in `Pending` state, a StoredFile record is created with the S3 object key, and the response contains `{ drawing_id, presigned_url }` where `presigned_url` expires in exactly 15 minutes.
- **AC-5 (Unauthenticated hash-check):** Given no auth token, when I call `POST /drawings/hash-check`, then the response is `401`.
- **AC-6 (Unauthenticated drawing create):** Given no auth token, when I call `POST /drawings`, then the response is `401`.

---

**US-006 — Drawing Library List**

As a user, I want to view my drawings (or my team's drawings) in a paginated list with status and revision information, so that I can track the state of all processed P&IDs.

- **AC-1 (Paginated list):** Given I am authenticated, when I call `GET /drawings`, then I receive a paginated response with up to 25 records by default, ordered by `uploaded_at DESC`.
- **AC-2 (Own drawings only for `role=user`):** Given my `role=user`, when I call `GET /drawings`, then only drawings with `owner_user_id = my_user_id` are returned.
- **AC-3 (Team drawings for `role=team_member`):** Given my `role=team_member`, when I call `GET /drawings`, then all drawings with `owner_team_id = my_team_id` are returned.
- **AC-4 (Team drawings for `role=team_admin`):** Given my `role=team_admin`, when I call `GET /drawings`, then all drawings with `owner_team_id = my_team_id` are returned.
- **AC-5 (Fields present):** Each drawing record in the response includes `id`, `filename`, `revision_label`, `processing_state`, `page_count`, `estimated_symbol_count`, `uploaded_at`, `processed_at`.
- **AC-6 (Unauthenticated):** Given no auth token, `GET /drawings` returns `401`.

---

**US-007 — Drawing Library Search and Filter**

As a user, I want to search drawings by filename or revision label and filter by status or date range, so that I can quickly locate specific drawings.

- **AC-1 (Full-text search):** Given `?q=pump+station`, when I call `GET /drawings?q=pump+station`, then only drawings whose `filename` or `revision_label` match the FTS query are returned (using `idx_drawing_fts`).
- **AC-2 (Status filter):** Given `?state=Failed`, when I call `GET /drawings?state=Failed`, then only drawings with `processing_state='Failed'` are returned.
- **AC-3 (Date range filter):** Given `?uploaded_after=2024-01-01&uploaded_before=2024-12-31`, then only drawings uploaded in that range are returned.
- **AC-4 (Combined filters):** Given `?q=rev2&state=Complete`, then filters are applied in conjunction (AND).
- **AC-5 (Pagination params):** `?limit=N&offset=M` controls page size; maximum `limit` is 100.

---

**US-008 — Processing State Machine + Live SSE Status**

As a user waiting for a drawing to be processed, I want live status updates pushed to my browser, so that I know immediately when processing completes or fails.

- **AC-1 (SSE stream established):** Given I am authenticated and own the drawing, when I call `GET /drawings/{id}/status`, then the response is `Content-Type: text/event-stream` and the current drawing state is sent immediately as the first event.
- **AC-2 (SSE event shape):** Each SSE event data matches `DrawingStatusSSEEvent: { drawing_id, state, timestamp }`.
- **AC-3 (Redis pub/sub forwarding):** When a worker publishes to `drawing:status:{drawing_id}`, the connected SSE client receives the event within the expected latency.
- **AC-4 (Keepalive / polling fallback):** The SSE stream sends a comment or state event at least every 10 seconds to prevent proxied connection drops.
- **AC-5 (Unauthenticated SSE):** Given no auth token, `GET /drawings/{id}/status` returns `401`.
- **AC-6 (Access to another user's drawing SSE):** Given I authenticate as User A, when I call `GET /drawings/{id}/status` for a drawing owned by User B (not my team), then the response is `403`.
- **AC-7 (State machine valid transitions only):** `drawing_state_machine.py` rejects any transition not in `DRAWING_STATE_TRANSITIONS`; calling `transition_drawing(drawing, invalid_target_state)` raises `InvalidStateTransitionError`.
- **AC-8 (Terminal state Scan_Failed has no allowed transitions):** Calling `transition_drawing(drawing_in_scan_failed, any_state)` raises `InvalidStateTransitionError`.

---

**US-009 — Retry Failed Drawings; Delete Drawings**

As a user, I want to retry a failed drawing processing job and delete drawings I no longer need, so that I can recover from processing errors and manage my library.

- **AC-1 (Retry from Failed):** Given a drawing in `Failed` state that I own, when I call `POST /drawings/{id}/retry`, then the drawing transitions to `Queued`, an ingest job is enqueued to the `ingest` Celery queue using the existing `stored_file_id` (no new S3 upload), and the response is `202 Accepted`.
- **AC-2 (Retry from Scan_Failed is rejected):** Given a drawing in `Scan_Failed` state, when I call `POST /drawings/{id}/retry`, then the response is `422 Unprocessable Entity` (terminal state, no retry permitted).
- **AC-3 (Retry re-uses StoredFile):** The ingest job payload for a retry contains the same `storage_reference` as the original upload — no new StoredFile record is created.
- **AC-4 (Retry from non-Failed state):** Given a drawing in `Complete` state and I call `POST /drawings/{id}/retry`, then `422` is returned (retry only permitted from `Failed`; `Complete`→`Queued` edge case does not apply to user-initiated retry endpoint).
- **AC-5 (Retry by non-owner user):** Given I call `POST /drawings/{id}/retry` for a drawing owned by another user (not my team), the response is `403`.
- **AC-6 (team_member cannot delete):** Given my `role=team_member`, when I call `DELETE /drawings/{id}`, then the response is `403`.
- **AC-7 (Delete own drawing as `user`):** Given my `role=user` and I own the drawing, when I call `DELETE /drawings/{id}`, then the drawing and its cascade-deleted child records are removed and the response is `204 No Content`.
- **AC-8 (Delete while mid-processing):** Given a drawing in `Processing` state, when I call `DELETE /drawings/{id}` as the owner, then the record is deleted and the response is `204` (the running worker will encounter a missing drawing_id and abort gracefully).
- **AC-9 (team_admin can delete team drawing):** Given my `role=team_admin`, when I call `DELETE /drawings/{id}` for any drawing in my team, the response is `204`.
- **AC-10 (Delete non-existent drawing):** Given a drawing_id that does not exist, `DELETE /drawings/{id}` returns `404`.

---

**US-010 — Analytics Events (drawing_uploaded and free_limit_reached)**

As the system, I must emit structured analytics events on drawing upload and on free tier limit breach, so that product analytics are accurate.

- **AC-1 (drawing_uploaded fires on upload-complete):** When `POST /drawings/{id}/upload-complete` transitions a Drawing from `Pending` to `Queued`, the `drawing_uploaded` event is emitted with `{ event, timestamp, user_id, drawing_id }` where `user_id` matches the authenticated user.
- **AC-2 (drawing_uploaded not fired when idempotent):** When `POST /drawings/{id}/upload-complete` is called on a drawing already in `Queued` or later state (idempotent path, returns `200`), the `drawing_uploaded` event is NOT emitted.
- **AC-3 (drawing_uploaded never fires from browser or ML worker):** The emit call exists only in `upload_complete_service.py`, not in client-accessible code.
- **AC-4 (free_limit_reached fires before job enqueue):** When a free-tier user attempts `POST /drawings/{id}/upload-complete` that would exceed 3 drawings/month, the `free_limit_reached` event is emitted and the job is NOT enqueued.
- **AC-5 (free_limit_reached payload):** The event payload includes `subscription_id` resolved server-side.
- **AC-6 (Analytics failure does not surface to user):** If the PostHog emit raises an exception, the HTTP response is still returned normally (emit is fire-and-forget).

---

**US-018 — Free Tier Monthly Limit Enforcement**

As the system, I must enforce a 3-drawing/month limit for free-tier users at job enqueue time, so that quota is respected and cannot be bypassed by concurrent uploads.

- **AC-1 (Limit enforced at enqueue):** Given a free-tier user who has already enqueued 3 drawings this calendar month, when they call `POST /drawings/{id}/upload-complete` for a 4th drawing, the response is `402 Payment Required` (or `429` — implementation choice documented in code), the ingest job is NOT enqueued, and `free_limit_reached` is fired.
- **AC-2 (Counter incremented atomically at enqueue):** The monthly counter increment and the limit check occur in a single atomic operation (Redis `INCR`+`EXPIRE` or `SELECT FOR UPDATE` in a DB transaction) to prevent concurrent-upload bypass.
- **AC-3 (Pro/Team tiers bypass limit):** Given a pro or team subscription, no limit check is performed and drawing processing proceeds normally.
- **AC-4 (Counter resets monthly):** The limit counter is scoped to the current calendar month (UTC). A user who hit the limit in January can enqueue drawings again in February.
- **AC-5 (Counter based on enqueued drawings, not completed):** The counter counts drawings that have been enqueued (Queued or later state), not drawings that have completed processing.

---

**US-003-extended — Upload Complete Idempotency and State**

- **AC-7 (upload-complete initial success):** Given a Drawing in `Pending` state, when `POST /drawings/{id}/upload-complete` is called, the Drawing transitions to `Queued`, an ingest job is enqueued, and the response is `202 Accepted`.
- **AC-8 (upload-complete idempotent on already-Queued):** Given a Drawing in `Queued` state, when `POST /drawings/{id}/upload-complete` is called again, the response is `200 OK` and no new job is enqueued.
- **AC-9 (upload-complete idempotent on Complete/Failed):** Given a Drawing in `Complete` or `Failed` state, when `POST /drawings/{id}/upload-complete` is called, the response is `200 OK` and no new job is enqueued.
- **AC-10 (user_id in ingest job payload):** The ingest job payload always contains `user_id` set to the authenticated user's ID at enqueue time (not resolved by the worker).

---

##### UX and design specification

N/A — This is a backend API session. No frontend components are implemented here. The API contracts defined here are consumed by S3-B (Drawing Library), S3-C (Upload Flow), and S3-D (Review Canvas) frontend sessions.

##### Critical implementation notes

**Ordering rules (verbatim from §1.4):**

- "Client calls `POST /drawings/hash-check` with `{sha256_hash, filename, size_bytes}`. Server checks `FILE_HASH_BLOCKLIST`. If the hash is present, returns `409 Conflict` — no Drawing record is created, no S3 URL is issued. A `POST /drawings` without a valid prior hash-check pass returns `400`." — Implement hash-check pass tracking via Redis key `hash_check_passed:{user_id}:{sha256_hash}` with TTL of 30 minutes. `POST /drawings` reads this key; absence → `400`.

- "`POST /drawings/{id}/upload-complete` is idempotent. If the Drawing record is already in `Queued` or any later processing state, the endpoint returns `200` without re-enqueuing the ingest job." — **Silent failure mode**: if you return `202` on the idempotent path, downstream clients will enqueue duplicate ingest jobs.

- "The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access. This is mandatory for `processing_complete` and `processing_failed` events." — The `user_id` field in the ingest Celery task kwargs is load-bearing for S2-H, S2-J analytics. Never omit it or set it to None.

- "The counter increment must occur at the point processing is initiated (job enqueued), not at job completion, to prevent race conditions from concurrent uploads." — Use Redis `INCR` on key `free_tier_counter:{user_id}:{YYYY-MM}` with `EXPIRE` set to end-of-month + 1 day (or use a Lua script for atomicity). Do NOT use a simple SELECT COUNT(*) without locking.

- "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts." — Always use `celery_app.send_task('ingest.process_drawing', kwargs={...}, queue=INGEST_QUEUE)`. Never use `apply_async` with `task_always_eager=True` in non-test code.

**HTTP status code contracts:**

- `POST /drawings/hash-check` blocked → `409` (NEVER `200` or `400`)
- `POST /drawings` no hash-check → `400` (NEVER `201`)
- `POST /drawings/{id}/upload-complete` initial success → `202` (NEVER `200`)
- `POST /drawings/{id}/upload-complete` idempotent → `200` (NEVER `201`, `409`)
- `DELETE /drawings/{id}` success → `204` (NEVER `200`)
- Unauthenticated → `401` (NEVER `403`)
- Wrong owner → `403` (NEVER `404`) — do NOT leak resource existence to unauthorized users UNLESS the resource does not exist (then `404`)

**Atomicity requirements:**

- `upload_complete_service.py`: The free-tier limit increment + drawing state transition + Celery task enqueue must be structured so that if the DB transaction rolls back, the Celery task is NOT committed to the broker. Achieve this by using `transaction.on_commit()` (if using Django-style) or by using the Celery `Task.apply_async` call AFTER a successful `db.commit()`. If the Celery send fails after commit, the Drawing remains in `Queued` but without a running job — this is recoverable (admin retry). This is preferable to double-counting.

- `free_tier_counter.py`: The Redis `INCR` must be a Lua script (or pipeline) that atomically checks-and-increments to prevent TOCTOU race between two concurrent uploads. Pattern: `INCR key; GET key; if value > limit: DECR key; return 'limit_exceeded'`.

- `drawing_state_machine.py`: All state transitions must be wrapped in a DB transaction that also writes to `audit_log`. A failed audit write must roll back the state change.

**Cross-session contracts:**

- **Ingest job payload is load-bearing for S2-H.** The Celery task kwargs shape `{ drawing_id: str, user_id: str, stored_file_id: str, storage_reference: str }` must not change after merge. S2-H's `ingest.process_drawing` task reads exactly these keys.

- **drawing_state_machine.py is imported by S2-H, S2-I, S2-J.** The functions `transition_drawing(drawing, target_state, db)` and `is_valid_transition(from_state, to_state)` must remain stable in signature.

- **SSE channel key format `drawing:status:{drawing_id}` is load-bearing.** S2-H, S2-I, and S2-J publish to exactly this channel. The `drawing_status.py` SSE handler subscribes to exactly this channel. Any mismatch is a silent runtime failure.

**Silent failure modes:**

- **If `user_id` is omitted from ingest job payload**: Workers (S2-H, S2-J) emit analytics with `user_id=None`, corrupting analytics data. The spec states "This is mandatory for `processing_complete` and `processing_failed` events."

- **If free tier counter uses `SELECT COUNT(*)` without a lock**: Two concurrent `upload-complete` calls for the same user can both read count=2 and both increment to 3, allowing 5 drawings instead of 3.

- **If `drawing_uploaded` event is emitted before `db.commit()`**: The drawing transitions to Queued in analytics but the DB transaction rolls back, leaving analytics in inconsistent state. Emit analytics after a successful commit.

- **If the SSE handler does not send the current state as the first event**: Clients that connect after the last state change never learn the current state until the next transition, causing stale UI.

- **If `POST /drawings/hash-check` returns `200 {allowed: false}` instead of `409` for blocked hashes**: Clients treat `allowed: false` as a soft signal; the spec requires `409` as a hard rejection.

- **If retry endpoint transitions any non-Failed drawing to Queued**: The state machine allows `Complete → Queued` but the user-facing retry endpoint must only allow `Failed → Queued`. Accepting `Complete` state on retry would re-process already-completed drawings silently.

**Approaches to avoid:**

- Do NOT resolve `training_consent` in this session — that is owned by S2-C and S2-F.
- Do NOT implement Under_Review transition in this session — it is triggered by the first correction action in S2-C.
- Do NOT emit `processing_complete` or `processing_failed` analytics from this session — those are emitted by S2-J (ML Worker).
- Do NOT serve export pre-signed URLs from this session — owned by S2-D.
- Do NOT cache subscription tier in this session's code — read the existing `subscription:flags:{user_id}` cache written by S1-D / S2-E. If the key is absent, fall back to DB query and do NOT write back to the cache (that is S2-E's responsibility).

##### Mocking contract

This is a backend session. Listed below are the internal service interfaces and queue payload shapes this session depends on from other sessions, and defines for consumers.

**Consumed from S1-B (auth):**

```python
# backend/app/auth/dependencies.py
async def get_current_user(token: str = ..., db: Session = ...) -> User:
    # Returns User ORM object with .id, .role, .team_id, .token_invalidated_at
    ...

# backend/app/auth/permissions.py
def assert_drawing_access(user: User, drawing: Drawing) -> None:
    # Raises HTTP 403 if user cannot access drawing per ROLE_PERMISSIONS
    ...

def assert_drawing_delete(user: User, drawing: Drawing) -> None:
    # Raises HTTP 403 if user cannot delete drawing per ROLE_PERMISSIONS
    ...
```

**Consumed from S1-C (storage):**

```python
# backend/app/storage/presigned.py
def generate_upload_presigned_url(
    bucket: str, object_key: str, expiry_seconds: int
) -> str: ...

# backend/app/storage/blocklist.py
def is_hash_blocked(sha256_hash: str, db: Session) -> bool: ...
```

**Consumed from S1-D (Redis + queues):**

```python
# backend/app/redis/pubsub.py
async def subscribe_drawing_status(
    redis: Redis, drawing_id: str
) -> AsyncIterator[DrawingStatusSSEEvent]: ...

DRAWING_STATUS_CHANNEL = "drawing:status:{drawing_id}"

# backend/app/workers/queues.py
INGEST_QUEUE: str = "ingest"
```

**Consumed from S1-E (analytics):**

```python
# backend/app/analytics/events.py
async def emit_drawing_uploaded(user_id: str, drawing_id: str) -> None: ...
async def emit_free_limit_reached(
    user_id: str, drawing_id: str, subscription_id: str
) -> None: ...
```

**Defined by this session, consumed by S2-H (Ingest Worker) — LOAD-BEARING:**

```python
# Celery task kwargs shape — enqueued by upload_complete_service.py
# Consumed by backend/app/workers/ingest/tasks.py (S2-H)
IngestJobPayload = {
    "drawing_id": str,         # UUID of Drawing record
    "user_id": str,            # UUID of authenticated user — MUST be set at enqueue time
    "stored_file_id": str,     # UUID of StoredFile record
    "storage_reference": str,  # S3 object key (same as StoredFile.object_key)
}
# Task name: "ingest.process_drawing"
# Queue: INGEST_QUEUE ("ingest")
```

**Defined by this session, consumed by S2-H, S2-I, S2-J — LOAD-BEARING:**

```python
# backend/app/services/drawing_state_machine.py

class InvalidStateTransitionError(Exception):
    """Raised when a state transition is not in DRAWING_STATE_TRANSITIONS."""
    pass

def is_valid_transition(from_state: str, to_state: str) -> bool:
    """Returns True if the transition is permitted per DRAWING_STATE_TRANSITIONS."""
    ...

def transition_drawing(
    drawing: Drawing,
    target_state: str,
    db: Session,
    audit_user_id: Optional[str] = None,
) -> Drawing:
    """
    Atomically transitions drawing.processing_state to target_state.
    Writes to audit_log in the same DB transaction.
    Raises InvalidStateTransitionError on invalid transition.
    Raises ValueError on Scan_Failed (terminal, no transitions).
    """
    ...
```

**Test doubles used in integration tests:**

For `tests/integration/test_drawings_api.py` and `tests/integration/test_drawings_sse.py`:

```python
# S3 presigned URL — mocked via moto or localstack
MOCK_PRESIGNED_URL = "https://s3.example.com/bucket/key?X-Amz-Signature=mock"

# Celery task dispatch — mocked via unittest.mock.patch
# celery_app.send_task returns a mock AsyncResult with .id = "mock-task-id"

# Analytics emitters — mocked via pytest fixtures
# emit_drawing_uploaded, emit_free_limit_reached are patched to record calls

# Redis pubsub — uses real Redis (from S0-B docker-compose.fixtures.yml)
# Test publishes directly to channel and verifies SSE client receives event

# Example DrawingStatusSSEEvent fixture:
MOCK_SSE_EVENT = {
    "drawing_id": "550e8400-e29b-41d4-a716-446655440000",
    "state": "Processing",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

##### Acceptance criteria checklist

- [ ] `POST /drawings/hash-check` with blocked hash returns `409 Conflict`, no Drawing created, no presigned URL issued [US-003 AC-1]
- [ ] `POST /drawings/hash-check` with non-blocked hash returns `200 OK` with `{ allowed: true }` and records pass in Redis [US-003 AC-2]
- [ ] `POST /drawings` called without prior hash-check pass returns `400` [US-003 AC-3]
- [ ] `POST /drawings` after hash-check pass creates Drawing (`Pending`), StoredFile, returns `{ drawing_id, presigned_url }` [US-003 AC-4]
- [ ] `presigned_url` TTL is exactly `PRESIGNED_URL_EXPIRY_SECONDS` (default 900s) [US-003 AC-4]
- [ ] `POST /drawings/hash-check` unauthenticated returns `401` [US-003 AC-5]
- [ ] `POST /drawings` unauthenticated returns `401` [US-003 AC-6]
- [ ] `GET /drawings` returns paginated list (default 25) ordered by `uploaded_at DESC` [US-006 AC-1]
- [ ] `GET /drawings` for `role=user` returns only own drawings [US-006 AC-2]
- [ ] `GET /drawings` for `role=team_member` returns all team drawings [US-006 AC-3]
- [ ] `GET /drawings` for `role=team_admin` returns all team drawings [US-006 AC-4]
- [ ] Each drawing record in `GET /drawings` includes all required fields: `id, filename, revision_label, processing_state, page_count, estimated_symbol_count, uploaded_at, processed_at` [US-006 AC-5]
- [ ] `GET /drawings` unauthenticated returns `401` [US-006 AC-6]
- [ ] `GET /drawings?q=<term>` returns FTS-matched drawings only [US-007 AC-1]
- [ ] `GET /drawings?state=Failed` returns only `Failed` drawings [US-007 AC-2]
- [ ] `GET /drawings?uploaded_after=X&uploaded_before=Y` filters by date range [US-007 AC-3]
- [ ] Combined `?q=&state=` applies filters in AND conjunction [US-007 AC-4]
- [ ] `GET /drawings?limit=N&offset=M` respects pagination; max limit is 100 [US-007 AC-5]
- [ ] `GET /drawings/{id}/status` for authenticated owner returns `Content-Type: text/event-stream` with first event containing current state [US-008 AC-1]
- [ ] Each SSE event data is valid `DrawingStatusSSEEvent` JSON with `drawing_id, state, timestamp` [US-008 AC-2]
- [ ] SSE stream forwards events published to Redis `drawing:status:{drawing_id}` channel [US-008 AC-3]
- [ ] SSE stream sends comment or state event at least every 10 seconds [US-008 AC-4]
- [ ] `GET /drawings/{id}/status` unauthenticated returns `401` [US-008 AC-5]
- [ ] `GET /drawings/{id}/status` for drawing owned by another user returns `403` [US-008 AC-6]
- [ ] `drawing_state_machine.is_valid_transition(from, invalid_target)` returns `False` for invalid transitions [US-008 AC-7]
- [ ] `transition_drawing(drawing_in_scan_failed, any_state, db)` raises `InvalidStateTransitionError` [US-008 AC-8]
- [ ] `POST /drawings/{id}/retry` on `Failed` drawing transitions to `Queued`, enqueues ingest job, returns `202` [US-009 AC-1]
- [ ] `POST /drawings/{id}/retry` on `Scan_Failed` drawing returns `422` [US-009 AC-2]
- [ ] Ingest job payload on retry contains same `storage_reference` as original; no new StoredFile created [US-009 AC-3]
- [ ] `POST /drawings/{id}/retry` on `Complete` drawing returns `422` [US-009 AC-4]
- [ ] `POST /drawings/{id}/retry` for drawing not owned by caller returns `403` [US-009 AC-5]
- [ ] `DELETE /drawings/{id}` by `role=team_member` returns `403` [US-009 AC-6]
- [ ] `DELETE /drawings/{id}` by owner (`role=user`) returns `204` and drawing is removed [US-009 AC-7]
- [ ] `DELETE /drawings/{id}` for drawing in `Processing` state returns `204` [US-009 AC-8]
- [ ] `DELETE /drawings/{id}` by `role=team_admin` for team drawing returns `204` [US-009 AC-9]
- [ ] `DELETE /drawings/{id}` for non-existent drawing returns `404` [US-009 AC-10]
- [ ] `drawing_uploaded` event emitted with `{ event, timestamp, user_id, drawing_id }` after successful `upload-complete` Pending→Queued transition [US-010 AC-1]
- [ ] `drawing_uploaded` NOT emitted when `upload-complete` called on drawing already in `Queued` or later state [US-010 AC-2]
- [ ] Analytics emit does not cause HTTP error if PostHog call raises exception [US-010 AC-6]
- [ ] `free_limit_reached` event emitted before `upload-complete` returns non-success for free-tier user at limit [US-010 AC-4]
- [ ] `free_limit_reached` event payload includes `subscription_id` [US-010 AC-5]
- [ ] Free-tier user with 3 drawings enqueued this month gets `402` (or `429`) on 4th upload-complete; job NOT enqueued [US-018 AC-1]
- [ ] Free-tier counter increment is atomic (concurrent requests cannot bypass limit) [US-018 AC-2]
- [ ] Pro/Team subscription users are not subject to monthly limit [US-018 AC-3]
- [ ] Free-tier counter is scoped to calendar month (UTC); resets next month [US-018 AC-4]
- [ ] Counter counts enqueued drawings, not completed ones [US-018 AC-5]
- [ ] `POST /drawings/{id}/upload-complete` initial success (Pending→Queued) returns `202` [US-003 AC-7]
- [ ] `POST /drawings/{id}/upload-complete` on already-`Queued` drawing returns `200`, no new job enqueued [US-003 AC-8]
- [ ] `POST /drawings/{id}/upload-complete` on `Complete`/`Failed` drawing returns `200`, no new job enqueued [US-003 AC-9]
- [ ] Ingest job payload contains `user_id` equal to authenticated user's UUID [US-003 AC-10]
- [ ] `GET /drawings/{id}` for authenticated owner returns full drawing detail with `200` [MANUAL]
- [ ] `PATCH /drawings/{id}` updates `revision_label` and returns updated record [MANUAL]
- [ ] `GET /drawings` query uses `idx_drawing_fts` GIN index (EXPLAIN shows index scan, not seq scan) [MANUAL]
- [ ] Deleting a drawing cascades to `detected_symbol`, `table_cell`, `user_correction`, `export_record` (DB ON DELETE CASCADE) [MANUAL]

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation):
- `tests/integration/test_drawings_api.py`
- `tests/integration/test_drawings_sse.py`

**Exact CI command:**
```bash
pytest tests/integration/test_drawings_api.py tests/integration/test_drawings_sse.py -v --tb=short
```

**AC → assertion mapping:**

| AC | `it(...)` / `test(...)` block |
|---|---|
| US-003 AC-1 | `test_hash_check_blocked_returns_409` |
| US-003 AC-2 | `test_hash_check_allowed_returns_200_and_sets_redis_flag` |
| US-003 AC-3 | `test_post_drawings_without_hash_check_returns_400` |
| US-003 AC-4 | `test_post_drawings_after_hash_check_creates_drawing_and_presigned_url` |
| US-003 AC-4 (TTL) | `test_presigned_url_expiry_matches_config` |
| US-003 AC-5 | `test_hash_check_unauthenticated_returns_401` |
| US-003 AC-6 | `test_post_drawings_unauthenticated_returns_401` |
| US-006 AC-1 | `test_get_drawings_paginated_default_25_desc` |
| US-006 AC-2 | `test_get_drawings_user_role_sees_own_only` |
| US-006 AC-3 | `test_get_drawings_team_member_sees_team_drawings` |
| US-006 AC-4 | `test_get_drawings_team_admin_sees_team_drawings` |
| US-006 AC-5 | `test_get_drawings_response_fields_present` |
| US-006 AC-6 | `test_get_drawings_unauthenticated_returns_401` |
| US-007 AC-1 | `test_get_drawings_fts_search` |
| US-007 AC-2 | `test_get_drawings_filter_by_state` |
| US-007 AC-3 | `test_get_drawings_filter_by_date_range` |
| US-007 AC-4 | `test_get_drawings_combined_filters` |
| US-007 AC-5 | `test_get_drawings_pagination_params` |
| US-008 AC-1 | `test_sse_status_stream_established_with_initial_event` |
| US-008 AC-2 | `test_sse_event_shape_matches_contract` |
| US-008 AC-3 | `test_sse_forwards_redis_pubsub_event` |
| US-008 AC-4 | `test_sse_sends_keepalive_within_10_seconds` |
| US-008 AC-5 | `test_sse_unauthenticated_returns_401` |
| US-008 AC-6 | `test_sse_wrong_owner_returns_403` |
| US-008 AC-7 | `test_state_machine_rejects_invalid_transition` |
| US-008 AC-8 | `test_state_machine_scan_failed_terminal` |
| US-009 AC-1 | `test_retry_failed_drawing_transitions_to_queued_and_enqueues` |
| US-009 AC-2 | `test_retry_scan_failed_returns_422` |
| US-009 AC-3 | `test_retry_reuses_stored_file` |
| US-009 AC-4 | `test_retry_complete_drawing_returns_422` |
| US-009 AC-5 | `test_retry_wrong_owner_returns_403` |
| US-009 AC-6 | `test_delete_by_team_member_returns_403` |
| US-009 AC-7 | `test_delete_own_drawing_returns_204` |
| US-009 AC-8 | `test_delete_mid_processing_drawing_returns_204` |
| US-009 AC-9 | `test_delete_by_team_admin_returns_204` |
| US-009 AC-10 | `test_delete_nonexistent_drawing_returns_404` |
| US-010 AC-1 | `test_drawing_uploaded_event_emitted_on_upload_complete` |
| US-010 AC-2 | `test_drawing_uploaded_not_emitted_on_idempotent_upload_complete` |
| US-010 AC-6 | `test_analytics_failure_does_not_surface_to_user` |
| US-010 AC-4 | `test_free_limit_reached_event_fired_before_job_enqueue` |
| US-010 AC-5 | `test_free_limit_reached_payload_includes_subscription_id` |
| US-018 AC-1 | `test_free_tier_limit_blocks_4th_drawing_upload_complete` |
| US-018 AC-2 | `test_free_tier_counter_is_atomic_concurrent` |
| US-018 AC-3 | `test_pro_tier_bypasses_monthly_limit` |
| US-018 AC-4 | `test_free_tier_counter_scoped_to_calendar_month` |
| US-018 AC-5 | `test_free_tier_counter_counts_enqueued_not_completed` |
| US-003 AC-7 | `test_upload_complete_initial_returns_202` |
| US-003 AC-8 | `test_upload_complete_idempotent_on_queued_returns_200` |
| US-003 AC-9 | `test_upload_complete_idempotent_on_complete_failed_returns_200` |
| US-003 AC-10 | `test_ingest_job_payload_contains_user_id` |

**Fixtures / test doubles:**

```python
# conftest.py (tests/integration/) — from S0-B
@pytest.fixture
def db_session():
    # Test PostgreSQL session with rollback after each test

@pytest.fixture
def redis_client():
    # Real Redis instance (docker-compose.fixtures.yml)

@pytest.fixture
def s3_mock():
    # moto S3 mock or localstack; returns boto3 client pointed at fake bucket

# Session-local fixtures in test_drawings_api.py
@pytest.fixture
def auth_user(db_session):
    # Creates User(role='user') + Subscription(tier_id='free') + returns JWT token

@pytest.fixture
def pro_user(db_session):
    # Creates User(role='user') + Subscription(tier_id='pro') + returns JWT token

@pytest.fixture
def team_member_user(db_session):
    # Creates Team + User(role='team_member', team_id=team.id) + returns JWT token

@pytest.fixture
def team_admin_user(db_session):
    # Creates Team + User(role='team_admin', team_id=team.id) + returns JWT token

@pytest.fixture
def pending_drawing(db_session, auth_user):
    # Creates Drawing(processing_state='Pending', owner_user_id=auth_user.id)
    # Creates StoredFile linked to drawing

@pytest.fixture
def failed_drawing(db_session, auth_user):
    # Creates Drawing(processing_state='Failed', owner_user_id=auth_user.id)

@pytest.fixture
def mock_analytics(monkeypatch):
    # Patches emit_drawing_uploaded and emit_free_limit_reached
    # Records calls for assertion

@pytest.fixture
def mock_celery_send_task(monkeypatch):
    # Patches celery_app.send_task to record calls without dispatching
    # Returns mock with .id attribute

# Ingest job payload shape (must match S2-H contract)
EXPECTED_INGEST_PAYLOAD = {
    "drawing_id": "<uuid>",
    "user_id": "<uuid>",
    "stored_file_id": "<uuid>",
    "storage_reference": "<s3-object-key>",
}

# DrawingStatusSSEEvent fixture
MOCK_SSE_EVENT = {
    "drawing_id": "550e8400-e29b-41d4-a716-446655440000",
    "state": "Processing",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

**Pre-conditions:**

- PostgreSQL running and migrated (Alembic `0001_initial_schema`, `0002_rls_policies`, `0003_audit_partitions` from S1-A)
- Tier seed data present (`seed_tiers.py` from S1-A): `free`, `pro`, `team` records
- Entity class seed data present (`seed_entity_classes.py` from S1-A)
- Redis running (from S0-B docker-compose.fixtures.yml)
- S3 mock active (moto or localstack; S3_BUCKET_NAME env var set)
- Environment variables set: `DATABASE_URL`, `REDIS_URL`, `S3_BUCKET_NAME`, `S3_REGION`, `JWT_RS256_PUBLIC_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `PRESIGNED_URL_EXPIRY_SECONDS=900`

**Isolation rule:**

All tests use database rollback and Redis key cleanup in teardown. The Celery send_task is mocked — no actual workers need to be running. The SSE tests use an in-process ASGI test client with async test runner (httpx `AsyncClient` or `starlette.testclient.TestClient` with SSE support). This session's tests pass when only S1-A, S1-B, S1-C, S1-D, S1-E have merged — no S2-C, S2-D, S2-E, or S3 sessions required.

##### Checkpoint

- **One-sentence observable outcome:** After this PR merges, calling `POST /drawings/hash-check` → `POST /drawings` → (S3 upload) → `POST /drawings/{id}/upload-complete` against the running API creates a Drawing record in `Queued` state, enqueues a task on the `ingest` Celery queue, emits a `drawing_uploaded` PostHog event, and `GET /drawings/{id}/status` streams the state transitions as SSE events.
- **Shippability claim:** This PR is independently mergeable to main even if no other session in the same wave (S2-C through S2-M) has merged. S2-B depends only on Phase 1 sessions (S1-A, S1-B, S1-C, S1-D, S1-E) which must have already merged per the Phase 1 → Phase 2 gate definition.

##### Output and handoff

| Export | Kind | Consuming sessions |
|---|---|---|
| `drawing_state_machine.transition_drawing(drawing, target_state, db, audit_user_id)` | Function — `(Drawing, str, Session, Optional[str]) -> Drawing` | S2-H, S2-I, S2-J [LOAD-BEARING] |
| `drawing_state_machine.is_valid_transition(from_state, to_state)` | Function — `(str, str) -> bool` | S2-H, S2-I, S2-J [LOAD-BEARING] |
| `drawing_state_machine.InvalidStateTransitionError` | Exception class | S2-H, S2-I, S2-J [LOAD-BEARING] |
| `IngestJobPayload` kwargs shape `{ drawing_id, user_id, stored_file_id, storage_reference }` | Queue payload contract (Celery task `ingest.process_drawing`) | S2-H [LOAD-BEARING] |
| `GET /drawings` response shape | HTTP API contract | S3-B, S4-A |
| `POST /drawings/hash-check` / `POST /drawings` / `POST /drawings/{id}/upload-complete` contracts | HTTP API contract | S3-C, S4-A |
| `GET /drawings/{id}/status` SSE event contract (`DrawingStatusSSEEvent`) | HTTP/SSE API contract | S3-B, S3-D, S4-A |
| `DELETE /drawings/{id}` 204 contract | HTTP API contract | S3-B, S4-A |
| `POST /drawings/{id}/retry` 202 contract | HTTP API contract | S3-B, S4-A |
| `free_tier_counter.check_and_increment(user_id, db, redis)` | Function — `(str, Session, Redis) -> FreeCounterResult` | S2-B internal only (not consumed by other sessions) |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/test_drawings_api.py tests/integration/test_drawings_sse.py -v --tb=short",
    "file": "tests/integration/test_drawings_api.py"
  },
  "checkpoint": "Calling POST /drawings/hash-check → POST /drawings → POST /drawings/{id}/upload-complete against the running API creates a Drawing in Queued state, enqueues a task on the ingest Celery queue, emits a drawing_uploaded PostHog event, and GET /drawings/{id}/status streams SSE state transitions.",
  "manualAcs": [
    {
      "id": "US-003-MANUAL-1",
      "text": "GET /drawings/{id} for authenticated owner returns full drawing detail with 200."
    },
    {
      "id": "US-003-MANUAL-2",
      "text": "PATCH /drawings/{id} updates revision_label and returns updated record."
    },
    {
      "id": "US-007-MANUAL-1",
      "text": "GET /drawings query uses idx_drawing_fts GIN index (EXPLAIN shows index scan, not seq scan)."
    },
    {
      "id": "US-009-MANUAL-1",
      "text": "Deleting a drawing cascades to detected_symbol, table_cell, user_correction, export_record via DB ON DELETE CASCADE."
    }
  ],
  "exports": [
    {
      "kind": "function",
      "name": "transition_drawing",
      "shape": "(drawing: Drawing, target_state: str, db: Session, audit_user_id: Optional[str] = None) -> Drawing"
    },
    {
      "kind": "function",
      "name": "is_valid_transition",
      "shape": "(from_state: str, to_state: str) -> bool"
    },
    {
      "kind": "type",
      "name": "InvalidStateTransitionError",
      "shape": "class InvalidStateTransitionError(Exception): ..."
    },
    {
      "kind": "type",
      "name": "IngestJobPayload",
      "shape": "{ drawing_id: str; user_id: str; stored_file_id: str; storage_reference: str }"
    },
    {
      "kind": "module",
      "name": "backend/app/services/drawing_state_machine",
      "shape": "backend/app/services/drawing_state_machine.py"
    },
    {
      "kind": "module",
      "name": "backend/app/services/free_tier_counter",
      "shape": "backend/app/services/free_tier_counter.py"
    },
    {
      "kind": "module",
      "name": "backend/app/sse/drawing_status",
      "shape": "backend/app/sse/drawing_status.py"
    }
  ]
}
```