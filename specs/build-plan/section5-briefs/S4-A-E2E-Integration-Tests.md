---

#### S4-A — E2E Integration Tests

**Phase 4 | Testing/Hardening | Needs: S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M, S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G**

---

##### Objective

Verify that every critical cross-component flow in the PID Analyzer system operates correctly end-to-end against a live integration environment: file upload through ML completion, correction lifecycle, sync/async export, Stripe billing state transitions, GDPR erasure, two-gate blocklist enforcement, and free-tier rate limiting.

---

##### Scope

**P0 MVP — all seven test files cover P0 scenarios exclusively.** No P1 stubs are required in this session because all P1 features (revision comparison, team workspace, table editing, API key access) are explicitly out of scope for the E2E harness at this phase.

| File | Scenarios Covered | P0 / P1 |
|---|---|---|
| `test_upload_to_complete.py` | Full upload → ingest → scan → ML → Complete pipeline, SSE, analytics | P0 |
| `test_correction_flow.py` | Reclassify, reject, restore, manual_add, Under_Review transition, training consent | P0 |
| `test_export_sync_and_async.py` | Sync CSV/XLSX (<1 000 symbols), async path (>1 000 symbols), polling, re-export | P0 |
| `test_stripe_lifecycle.py` | Checkout, webhook idempotency, upgrade/downgrade analytics, grace period, cancellation | P0 |
| `test_gdpr_erasure.py` | Account deletion initiation, worker pipeline, anonymous_id, PII purge, post-deletion auth block | P0 |
| `test_blocklist_two_gate.py` | Hash-check gate (409), no-URL-on-block, POST /drawings without hash-check (400), ingest re-verify | P0 |
| `test_free_tier_limit.py` | 3-drawing limit, counter-at-enqueue, free_limit_reached event, no-queue-on-breach, upgrade unblocks | P0 |

---

##### Technology constraints

The following are sourced from §1.8 Technology Stack and are non-negotiable:

- **Python 3.11+** — all test files are Python (FastAPI/Celery backend is Python; test stack is Python)
- **pytest** — test runner; version pinned in `backend/pyproject.toml` (owned by S0-B)
- **pytest-asyncio** — required for async FastAPI endpoint tests and SSE stream assertions
- **httpx** — async HTTP client used for all API calls inside test coroutines (consistent with FastAPI's `TestClient`/`AsyncClient`)
- **moto (or localstack)** — S3-compatible stub; exact choice follows `tests/integration/fixtures/s3.py` (owned by S0-B)
- **fakeredis** or real Redis — follows `tests/integration/fixtures/redis.py` (owned by S0-B); must support pub/sub for SSE tests
- **PostgreSQL (real)** — follows `tests/integration/fixtures/db.py`; Alembic migrations run before suite; do NOT use SQLite
- **Celery `task_always_eager=True` mode** — for worker tasks that must complete synchronously in tests; set via pytest fixture override, not globally
- **stripe-mock** or manual HMAC-signed webhook construction — for Stripe webhook tests; no live Stripe calls
- **unittest.mock / pytest-mock** — for PostHog client, SendGrid client, ClamAV socket, ODA Converter subprocess, ML model loader
- **Konva.js / React (S3-D)** — NOT tested here; this session covers backend API and worker E2E flows only; no browser automation (Playwright/Selenium) is in scope
- **Must NOT use `requests` (sync) for async endpoint tests** — use `httpx.AsyncClient`
- **Must NOT use in-memory Celery broker** for the blocklist two-gate test (`test_blocklist_two_gate.py`) — that test explicitly verifies the ingest-worker second-gate, which requires a real persistent queue path (use the Redis fixture broker with `task_always_eager=False` and explicit `task.get()` awaiting)

---

##### Performance targets

The following targets from §1.9 are verified as pass/fail assertions in this session:

| Metric | Target | Test file | Assertion type |
|---|---|---|---|
| Export (<1,000 symbols) completes end-to-end | <30 s P95 | `test_export_sync_and_async.py` | Hard timing assert in sync export test |
| ML inference timeout before Failed state | 20-minute cap enforced by worker | `test_upload_to_complete.py` (timeout path) | Hard — task configured with `ML_JOB_TIMEOUT_SECONDS` |
| Pre-signed S3 URL expiry | 15 minutes (`PRESIGNED_URL_EXPIRY_SECONDS=900`) | `test_blocklist_two_gate.py`, `test_upload_to_complete.py` | Verify presigned URL metadata |
| Async export threshold evaluated server-side | >1,000 symbols | `test_export_sync_and_async.py` | Assert no async path taken at ≤1,000; assert async path taken at 1,001 |
| Free-tier counter incremented at enqueue, not completion | Order guarantee | `test_free_tier_limit.py` | Assert counter incremented before ML completion |
| Stripe tier activation after Checkout redirect | <30 s | `test_stripe_lifecycle.py` | Monitoring target — no hard timing assert; webhook handler latency logged |

---

##### Owned files

Every file this session creates or modifies:

```
tests/integration/e2e/test_upload_to_complete.py
tests/integration/e2e/test_correction_flow.py
tests/integration/e2e/test_export_sync_and_async.py
tests/integration/e2e/test_stripe_lifecycle.py
tests/integration/e2e/test_gdpr_erasure.py
tests/integration/e2e/test_blocklist_two_gate.py
tests/integration/e2e/test_free_tier_limit.py
```

This session does NOT create a `conftest.py` — that is owned by S0-B. If shared E2E fixtures are needed that are not already in `tests/integration/conftest.py`, they must be defined as module-level fixtures inside the individual test files or as a new `tests/integration/e2e/conftest.py` (acceptable only if it contains no logic already owned by S0-B).

---

##### Read-only imports

| Owning Session | File path | Specific named exports required |
|---|---|---|
| S0-B | `tests/integration/conftest.py` | `db_session`, `redis_client`, `s3_client`, `test_app`, `async_client` |
| S0-B | `tests/integration/fixtures/db.py` | `db_session`, `apply_migrations`, `seed_tiers`, `seed_entity_classes` |
| S0-B | `tests/integration/fixtures/redis.py` | `redis_client`, `pubsub_listener` |
| S0-B | `tests/integration/fixtures/s3.py` | `s3_client`, `s3_bucket` |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` (ORM model — for direct DB assertions) |
| S1-A | `backend/app/db/models/user.py` | `User` |
| S1-A | `backend/app/db/models/subscription.py` | `Subscription` |
| S1-A | `backend/app/db/models/detected_symbol.py` | `DetectedSymbol` |
| S1-A | `backend/app/db/models/user_correction.py` | `UserCorrection` |
| S1-A | `backend/app/db/models/export_record.py` | `ExportRecord` |
| S1-A | `backend/app/db/models/stripe_event.py` | `StripeEvent` |
| S1-A | `backend/app/db/models/stored_file.py` | `StoredFile` |
| S1-A | `backend/app/db/models/file_hash_blocklist.py` | `FileHashBlocklist` |
| S1-A | `backend/app/db/seed_tiers.py` | `seed_tiers` |
| S1-A | `backend/app/db/seed_entity_classes.py` | `seed_entity_classes` |
| S1-B | `backend/app/auth/jwt_verifier.py` | `create_test_token` (or equivalent test helper) |
| S1-C | `backend/app/storage/hashing.py` | `compute_sha256` |
| S1-D | `backend/app/redis/pubsub.py` | `DRAWING_STATUS_CHANNEL` |
| S1-E | `backend/app/analytics/events.py` | All typed emitter functions (for mock-capture assertions) |
| S0-A | `backend/app/schemas/contracts.py` | `MLInferenceJobPayload`, `MLInferenceResult`, `DetectedSymbolResult`, `DrawingStatusSSEEvent`, `SymbolsPageResponse`, `HashCheckResponse` |
| S2-H | `backend/app/workers/ingest/tasks.py` | `ingest_drawing` (Celery task — for direct task invocation in tests) |
| S2-I | `backend/app/workers/scan/tasks.py` | `scan_drawing` |
| S2-J | `backend/app/workers/ml/tasks.py` | `run_ml_inference` |
| S2-K | `backend/app/workers/export/tasks.py` | `generate_export` |
| S2-L | `backend/app/workers/gdpr/tasks.py` | `run_gdpr_erasure` |

---

##### Do not touch

This session must not modify any of the following:

- `backend/app/main.py` — owned by S0-A (entry point)
- `backend/app/api/routers/__init__.py` — owned by S0-A (router includes)
- `backend/app/api/routers/auth.py` — owned by S2-A
- `backend/app/api/routers/drawings.py` — owned by S2-B
- `backend/app/api/routers/symbols.py` — owned by S2-C
- `backend/app/api/routers/exports.py` — owned by S2-D
- `backend/app/api/routers/subscription.py` — owned by S2-E
- `backend/app/api/routers/stripe_webhook.py` — owned by S2-E
- `backend/app/api/routers/account.py` — owned by S2-F
- `backend/app/api/routers/entity_classes.py` — owned by S2-G
- `backend/app/services/` (all files) — owned by S2-A through S2-G
- `backend/app/workers/` (all `tasks.py`, `__init__.py`, implementation files) — owned by S2-H through S2-M
- `backend/app/analytics/` — owned by S1-E
- `backend/app/auth/` — owned by S1-B
- `backend/app/storage/` — owned by S1-C
- `backend/app/redis/` — owned by S1-D
- `backend/app/db/models/` — owned by S1-A
- `backend/alembic/` — owned by S1-A
- `tests/integration/conftest.py` — owned by S0-B
- `tests/integration/fixtures/` (all) — owned by S0-B
- `tests/integration/smoke/test_smoke.py` — owned by S0-B
- `frontend/` (all files) — owned by S1-F and S3-A through S3-G
- `marketing/` (all files) — owned by S3-H
- `docker-compose.yml`, `docker-compose.test.yml` — owned by S0-A
- `backend/pyproject.toml`, `backend/poetry.lock` — owned by S0-B

---

##### Architecture context

The following sections are pasted verbatim from the distilled specification.

**From §1.4 Critical Ordering Rules:**

> 1. **Hash check before pre-signed URL issuance.** "Client calls `POST /drawings/hash-check` with `{sha256_hash, filename, size_bytes}`. Server checks `FILE_HASH_BLOCKLIST`. If the hash is present, returns `409 Conflict` — no Drawing record is created, no S3 URL is issued." A `POST /drawings` without a valid prior hash-check pass returns `400`.
>
> 2. **Pre-signed URL issued only after hash-check pass.** "The upload flow enforces FR-17 AC-2 (no blocked file byte reaches S3) through a mandatory hash pre-check before pre-signed URL issuance."
>
> 3. **Server-side SHA-256 re-verification after storage.** "Ingest Worker performs a server-side SHA-256 verification of the stored object against the client-supplied hash... hash is also checked a second time against the blocklist to handle newly-added entries between steps 3 and 7."
>
> 4. **Upload-complete idempotency check before enqueue.** "`POST /drawings/{id}/upload-complete` is idempotent. If the Drawing record is already in `Queued` or any later processing state, the endpoint returns `200` without re-enqueuing the ingest job."
>
> 5. **user_id written into job payload at enqueue time by API layer.** "The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access. This is mandatory for `processing_complete` and `processing_failed` events."
>
> 6. **training_consent snapshotted at correction creation time.** "Each correction save sends... the resolved `training_consent` value... at time of creation; the consent value must be snapshotted at correction time, not resolved lazily."
>
> 7. **Team-level consent evaluated server-side.** "Team-level consent resolution must be evaluated server-side to prevent client-side bypass; the resolved value is not a client-supplied field."
>
> 8. **Free-tier monthly counter incremented at job enqueue, not completion.** "The counter increment must occur at the point processing is initiated (job enqueued), not at job completion, to prevent race conditions from concurrent uploads."
>
> 9. **Stripe webhook state changes via webhook only, never inline after redirect.** "The subscription state in the application database must be updated exclusively via Stripe webhook events (not inline after the payment redirect) to ensure consistency and idempotency."
>
> 10. **Stripe webhook idempotency via stored event ID before any state mutation.** "Idempotency enforced via Stripe event ID stored in DB before any state mutation."
>
> 11. **GDPR erasure: anonymous_id written before any records updated.** "On first erasure job execution, the computed anonymous ID is written to `USER.anonymous_id` before any records are updated. All subsequent erasure job retries... read `USER.anonymous_id` directly."
>
> 12. **Password reset: all sessions invalidated before token_invalidated_at updated.** "On password reset, all tokens are invalidated via Supabase Auth's `admin.signOut(userId)` call; `USER.token_invalidated_at` is simultaneously updated."
>
> 13. **Under_Review transition triggered by first correction action, not canvas open.** "The drawing transitions from `Complete` to `Under_Review` on the user's first correction action (e.g., accepting, rejecting, or editing a detected symbol), not on canvas open."
>
> 14. **ML job must be enqueued via persistent queue (never in-memory).** "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts."
>
> 15. **Async export threshold evaluated server-side.** "The 1,000-symbol threshold for triggering async vs. synchronous export (FR-4 AC-3) must be evaluated server-side at job creation time, not client-side, to prevent bypass."

**From §1.5 HTTP Status Code Contracts:**

> | Condition | Required code | Must never return |
> |---|---|---|
> | Hash blocked on `POST /drawings/hash-check` | `409 Conflict` | `200`, `400` |
> | `POST /drawings` without valid prior hash-check pass | `400` | `200`, `201` |
> | `POST /drawings/{id}/upload-complete` when Drawing already in `Queued` or later state (idempotent) | `200` | `201`, `409` |
> | `POST /drawings/{id}/upload-complete` initial success (job enqueued) | `202` | `200`, `201` |
> | Drawing deletion success | `204` | `200` |
> | Auth logout success | `204` | `200` |
> | Password reset request success | `204` | `200` |
> | Password reset confirm success | `204` | `200` |
> | Account deletion initiation success | `204` | `200` |
> | Stripe webhook received and processed | `200` | `4xx`, `5xx` |
> | Stripe duplicate webhook (already processed, idempotent) | `200` | `4xx` |
> | Unauthenticated request to protected endpoint | `401` | `403`, `200` |
> | Authenticated user accessing resource they do not own | `403` | `404`, `200` |

**From §1.10 Analytics Event Contracts:**

> All nine events must be instrumented. Events must be non-blocking and asynchronous. Analytics failure must not surface to users. Server-side retry queue (dead-letter) recommended.
>
> | Event Name | Payload Shape | Code Surface That Fires It | Trigger Condition | Must NOT have happened yet | Must NEVER fire from |
> |---|---|---|---|---|---|
> | `drawing_uploaded` | `{ event: 'drawing_uploaded', timestamp: string (UTC ISO8601), user_id: string, drawing_id: string }` | FastAPI — `POST /drawings/{id}/upload-complete` handler | Drawing transitions to `Queued` state after upload-complete signal | Drawing must not already be in `Queued` or later state | Browser client; ML worker |
> | `processing_complete` | `{ event: 'processing_complete', timestamp: string, user_id: string, drawing_id: string }` | ML Worker (user_id from job payload) | Drawing transitions to `Complete` state | `processing_failed` for same drawing_id in same job run | Browser client; must not resolve user_id via DB lookup in worker |
> | `processing_failed` | `{ event: 'processing_failed', timestamp: string, user_id: string, drawing_id: string }` | ML Worker (user_id from job payload) | Drawing transitions to `Failed` state (after 1 automatic retry exhausted) | `processing_complete` for same drawing_id in same job run | Browser client |
> | `correction_action` | `{ event: 'correction_action', timestamp: string, user_id: string, drawing_id: string, symbol_id: string }` | FastAPI — `PATCH /symbols/{id}` and `POST /drawings/{id}/symbols` handlers | User submits a reclassify, reject, restore, or manual_add correction | None specified | Browser client directly; must fire server-side on persistence |
> | `export_initiated` | `{ event: 'export_initiated', timestamp: string, user_id: string, drawing_id: string, export_id: string, format: ExportFormat }` | FastAPI — `POST /drawings/{id}/exports` handler | Export job created (both sync and async paths) | Export file generated | Export Worker; browser client |
> | `export_downloaded` | `{ event: 'export_downloaded', timestamp: string, user_id: string, drawing_id: string, export_id: string }` | FastAPI — pre-signed URL access or download endpoint | User accesses pre-signed download URL | None specified | Export Worker |
> | `free_limit_reached` | `{ event: 'free_limit_reached', timestamp: string, user_id: string, drawing_id: string, subscription_id: string }` | FastAPI — processing initiation handler | Free tier user attempts to initiate processing of drawing that would exceed 3/month limit | Processing job must not be queued | Browser client; must fire before upgrade prompt is shown |
> | `subscription_upgraded` | `{ event: 'subscription_upgraded', timestamp: string, user_id: string, subscription_id: string, previous_tier: TierId, new_tier: TierId }` | FastAPI — Stripe webhook handler (`customer.subscription.updated`) | Subscription tier increases | Tier change applied before event fires | Browser client; Stripe redirect handler inline |
> | `subscription_downgraded` | `{ event: 'subscription_downgraded', timestamp: string, user_id: string, subscription_id: string, previous_tier: TierId, new_tier: TierId }` | FastAPI — Stripe webhook handler or downgrade confirmation handler | Subscription tier decreases (fires immediately at confirmation, not at period end) | None specified | Browser client |

**From §1.3 State Machines:**

> ```typescript
> const DRAWING_STATE_TRANSITIONS: Record<DrawingProcessingState, DrawingProcessingState[]> = {
>   Pending:      ['Queued', 'Failed'],
>   Queued:       ['Scanning', 'Failed'],
>   Scanning:     ['Processing', 'Scan_Failed', 'Failed'],
>   Processing:   ['Complete', 'Failed'],
>   Complete:     ['Under_Review', 'Queued'],
>   Under_Review: ['Queued'],
>   Failed:       ['Queued'],
>   Scan_Failed:  [],                             // Terminal — no retry permitted
> } as const;
>
> // Under_Review trigger: first user correction action (reclassify, reject, manual_add) — NOT canvas open
> // Retry: re-uses existing StoredFile; no new file written to S3
> ```
>
> ```typescript
> const BILLING_STATE_TRANSITIONS: Record<BillingState, BillingState[]> = {
>   Active: ['Grace', 'Canceled'],
>   Grace:  ['Active', 'Canceled'],
>   Canceled: ['Active'],
> } as const;
>
> // Grace period: 7 days from first invoice.payment_failed Stripe event
> // Grace period day-1 email on entry; day-6 reminder email
> ```

**From §1.11 Cross-Session Runtime Patterns:**

> | Channel Pattern | Published By | Consumed By | Payload Shape |
> |---|---|---|---|
> | `drawing:status:{drawing_id}` | Ingest Worker, Scan Worker, ML Worker (on each state transition) | FastAPI SSE handler (`GET /drawings/{id}/status`) → client | `DrawingStatusSSEEvent` (see §1.1) |
>
> | Queue | Workers | Job Types |
> |---|---|---|
> | `ingest` | Ingest Worker (CPU) | DWG-to-raster conversion, format detection, post-storage hash verification |
> | `scan` | Scan Worker (ClamAV sidecar, CPU) | Malware scan |
> | `ml_inference` | ML Worker (GPU — G4dn) | Symbol detection + table extraction |
> | `export` | Export Worker (CPU) | CSV/XLSX generation |
> | `gdpr_erasure` | GDPR Worker (CPU, scheduled) | PII purge, anonymization |

**From §1.9 Performance Targets:**

> | Metric | Target Value | Hard SLA or Monitoring Target | Responsible Component |
> |---|---|---|---|
> | Export (<1,000 symbols) | <30s P95 | Monitoring target | Export Worker (synchronous generation) |
> | ML inference timeout before Failed state | 20 minutes max | Hard SLA | ML Worker; 1 automatic retry before `Failed` transition |
> | Pre-signed S3 URL expiry | 15 minutes | Hard constraint (security) | FastAPI URL generation |
> | Async export threshold | >1,000 symbols triggers async path | Hard constraint | Export Worker; evaluated server-side |
> | Symbol pagination default / max | 200 default / 500 max per page | Hard constraint | `GET /drawings/{id}/symbols` |

**From §1.1 Shared Contracts (MLInferenceJobPayload):**

> ```typescript
> interface MLInferenceJobPayload {
>   storage_reference: string;       // S3 object key
>   drawing_id: string;              // UUID
>   user_id: string;                 // UUID — MUST be set at enqueue time by API layer
>   page_range?: [number, number];   // optional, 1-based inclusive
> }
> ```

---

##### User stories and acceptance criteria

The following user story scope (from §1.13) is covered by this session's E2E tests:

> **US-003**: PDF and DWG file upload with format, size, raster, DWG version, and blocklist validation
>
> **US-005**: Account deletion and GDPR erasure pipeline (30-day async, anonymous_id persistence)
>
> **US-008**: Processing state machine (Pending → Queued → Scanning → Processing → Complete/Failed/Scan_Failed) with live SSE/poll status updates and in-app notifications
>
> **US-009**: Retry failed processing jobs; delete drawings with confirmation (including mid-processing cancellation)
>
> **US-010**: All nine structured analytics events (drawing_uploaded, processing_complete, processing_failed, correction_action, export_initiated, export_downloaded, free_limit_reached, subscription_upgraded, subscription_downgraded)
>
> **US-011**: Automatic ML processing trigger after upload; detection results with confidence scores display
>
> **US-013**: Symbol inspection panel; reclassify (predefined list only); reject; undo rejection; server persistence with optimistic save indicator
>
> **US-014**: Manual annotation (draw bounding box, assign entity class, optional tag_label, confidence 1.0, source=manual)
>
> **US-015**: Session-restore for corrections (server-persistent); training consent gating at correction creation (server-side); team-level consent override
>
> **US-016**: CSV and XLSX export (synchronous path, <1,000 symbols); pre-signed download URL; re-export without overwriting prior exports
>
> **US-017**: Async export queue for >1,000 symbols; in-app notification when ready; async export failure with retry
>
> **US-018**: Free tier 3-drawing/month limit enforcement; upgrade prompt on limit hit; tier-gated features visible but inaccessible
>
> **US-019**: Stripe Checkout upgrade (Pro and Team tiers); downgrade deferred to period end; pending state with 30s webhook resolution timeout
>
> **US-020**: Grace period handling (7-day, day-1 and day-6 emails); Stripe cancellation (access until period end); idempotent webhook processing
>
> **Pre-storage SHA-256 blocklist enforcement** (two-gate: hash-check endpoint + Ingest Worker re-verification)
>
> **JWT middleware token_invalidated_at check on every authenticated request**

Derived acceptance criteria (from §1.4, §1.5, §1.10, §1.3):

**E2E-001 — Upload to Complete (test_upload_to_complete.py)**

- E2E-001-AC-1: `POST /drawings/hash-check` with a non-blocked SHA-256 hash, valid filename, and valid size_bytes returns HTTP 200 with body `{ "allowed": true }`.
- E2E-001-AC-2: `POST /drawings` following a valid hash-check pass creates a Drawing record in `Pending` state and returns HTTP 201.
- E2E-001-AC-3: The response to `POST /drawings` includes a pre-signed S3 upload URL with expiry of 900 seconds (15 minutes).
- E2E-001-AC-4: Uploading the file bytes to the pre-signed URL via HTTP PUT to S3/MinIO succeeds (HTTP 200 from S3).
- E2E-001-AC-5: `POST /drawings/{id}/upload-complete` transitions the Drawing to `Queued` and returns HTTP 202.
- E2E-001-AC-6: Calling `POST /drawings/{id}/upload-complete` a second time (Drawing already `Queued`) returns HTTP 200 and does not enqueue a second ingest job.
- E2E-001-AC-7: The `MLInferenceJobPayload` written to the Celery queue at enqueue time contains `user_id` set to the authenticated user's ID (verified by inspecting enqueued task arguments).
- E2E-001-AC-8: The `drawing_uploaded` analytics event fires with payload `{ event: 'drawing_uploaded', user_id, drawing_id }` at upload-complete time, before ML completion.
- E2E-001-AC-9: After the ingest task runs, the Drawing transitions from `Queued` to `Scanning`; a `DrawingStatusSSEEvent` with `state: 'Scanning'` is published to `drawing:status:{drawing_id}`.
- E2E-001-AC-10: After the scan task runs (clean file), the Drawing transitions from `Scanning` to `Processing`; a `DrawingStatusSSEEvent` with `state: 'Processing'` is published.
- E2E-001-AC-11: After the ML inference task runs (stub returns pre-canned symbols), the Drawing transitions from `Processing` to `Complete`; a `DrawingStatusSSEEvent` with `state: 'Complete'` is published.
- E2E-001-AC-12: The `processing_complete` analytics event fires from the ML worker with `user_id` sourced from `MLInferenceJobPayload` (not from a DB lookup or session context).
- E2E-001-AC-13: The ingest worker performs a server-side SHA-256 re-verification of the stored S3 object; if the hash matches the client-supplied value, the drawing proceeds normally.
- E2E-001-AC-14: Detected symbols are persisted in `detected_symbol` table with correct `drawing_id`, `entity_class_id`, `confidence`, `bbox`, `source='ml'`, `rejected=false`, and `page_number`.
- E2E-001-AC-15: `GET /drawings/{id}/symbols` returns HTTP 200 with all persisted symbols in `SymbolsPageResponse` shape, with default pagination limit of 200.
- E2E-001-AC-16: A failed ML inference (stub raises exception) transitions Drawing to `Failed` after 1 automatic retry; `processing_failed` analytics event fires; `processing_complete` does NOT fire.
- E2E-001-AC-17: `POST /drawings/{id}/retry` on a `Failed` drawing re-enqueues the ingest job (reusing the existing `StoredFile`) and transitions Drawing to `Queued`.
- E2E-001-AC-18: `DELETE /drawings/{id}` returns HTTP 204 and soft-deletes or removes the drawing record.
- E2E-001-AC-19: Unauthenticated `GET /drawings/{id}` returns HTTP 401.
- E2E-001-AC-20: Authenticated user accessing a drawing they do not own returns HTTP 403.

**E2E-002 — Correction Flow (test_correction_flow.py)**

- E2E-002-AC-1: A drawing in `Complete` state with detected symbols is the precondition.
- E2E-002-AC-2: `PATCH /symbols/{id}` with `correction_type=reclassify` and a valid `new_class_id` returns HTTP 200 and persists a `UserCorrection` record.
- E2E-002-AC-3: The drawing transitions from `Complete` to `Under_Review` on the first correction action (reclassify, reject, or manual_add) — not before.
- E2E-002-AC-4: `PATCH /symbols/{id}` with `correction_type=reject` sets `detected_symbol.rejected=true`.
- E2E-002-AC-5: `PATCH /symbols/{id}` with `correction_type=restore` sets `detected_symbol.rejected=false` on a previously rejected symbol.
- E2E-002-AC-6: `POST /drawings/{id}/symbols` with `source=manual`, valid `entity_class_id`, valid `bbox`, and optional `tag_label` creates a `DetectedSymbol` with `confidence=1.0` and `source='manual'`.
- E2E-002-AC-7: The `correction_action` analytics event fires server-side with `{ user_id, drawing_id, symbol_id }` for each of reclassify, reject, restore, and manual_add operations.
- E2E-002-AC-8: The `training_consent` field on the created `UserCorrection` record reflects the user's consent state at time of creation (snapshotted — verified by changing consent after creation and confirming existing correction record is unchanged).
- E2E-002-AC-9: `PATCH /symbols/{id}` for a symbol belonging to a drawing the authenticated user does not own returns HTTP 403.
- E2E-002-AC-10: `GET /drawings/{id}/symbols` response includes `corrections_by_symbol_id` keyed by symbol UUID, with all correction history for each symbol.
- E2E-002-AC-11: A second correction on the same drawing (already `Under_Review`) does NOT re-trigger another state transition — drawing remains `Under_Review`.

**E2E-003 — Export Sync and Async (test_export_sync_and_async.py)**

- E2E-003-AC-1: `POST /drawings/{id}/exports` with `format=csv` on a drawing with ≤1,000 symbols initiates the synchronous export path.
- E2E-003-AC-2: The `export_initiated` analytics event fires at `POST /drawings/{id}/exports` creation time, before the file is generated.
- E2E-003-AC-3: Polling `GET /exports/{id}` for a sync export returns `status: 'Complete'` with a non-null `stored_file_id` and a pre-signed download URL within 30 seconds.
- E2E-003-AC-4: The pre-signed download URL is accessible (HTTP GET returns 200 with file content-type `text/csv` or `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).
- E2E-003-AC-5: The downloaded CSV contains a row for each non-rejected symbol in the drawing.
- E2E-003-AC-6: The downloaded XLSX contains a row for each non-rejected symbol in the drawing (format=xlsx variant).
- E2E-003-AC-7: `POST /drawings/{id}/exports` on a drawing with >1,000 symbols (server evaluates symbol count) creates an `ExportRecord` with `status: 'Queued'` and enqueues an async export Celery task.
- E2E-003-AC-8: The async threshold (>1,000 symbols) is evaluated server-side — submitting `{"force_sync": true}` or any client-side override does not bypass it.
- E2E-003-AC-9: Polling `GET /exports/{id}` for an async export transitions through `Queued` → `Generating` → `Complete` and final state includes pre-signed download URL.
- E2E-003-AC-10: Re-exporting (second `POST /drawings/{id}/exports` with same format) creates a new `ExportRecord` — the previous export record's `stored_file_id` is not overwritten.
- E2E-003-AC-11: The `export_downloaded` analytics event fires when the pre-signed download URL is accessed.
- E2E-003-AC-12: An async export failure transitions `ExportRecord` to `status: 'Failed'`; `GET /exports/{id}` returns the failed status.

**E2E-004 — Stripe Lifecycle (test_stripe_lifecycle.py)**

- E2E-004-AC-1: `POST /subscription/checkout` returns a response containing a Stripe Checkout URL.
- E2E-004-AC-2: A Stripe webhook `POST /webhooks/stripe` with event type `checkout.session.completed` and a valid `Stripe-Signature` header transitions the user's subscription from the current state to `Active` and returns HTTP 200.
- E2E-004-AC-3: The Stripe event ID is stored in the `stripe_event` table before any subscription state mutation occurs (verified by injecting a DB failure after event store but before state update, confirming atomicity).
- E2E-004-AC-4: Sending the same Stripe webhook event ID a second time returns HTTP 200 without re-applying state mutations (idempotent).
- E2E-004-AC-5: A Stripe webhook `customer.subscription.updated` event with a higher tier fires the `subscription_upgraded` analytics event with `previous_tier` and `new_tier` populated correctly.
- E2E-004-AC-6: A Stripe webhook `customer.subscription.updated` event with a lower tier fires the `subscription_downgraded` analytics event immediately.
- E2E-004-AC-7: Subscription state is NOT updated by any inline code path after the Checkout redirect — only by the webhook handler (verified by simulating redirect without webhook and asserting subscription state unchanged).
- E2E-004-AC-8: A Stripe webhook `invoice.payment_failed` event transitions subscription from `Active` to `Grace` with `grace_period_start` set.
- E2E-004-AC-9: The Grace transition enqueues a day-1 notification task to the `notification` Celery queue.
- E2E-004-AC-10: A Stripe webhook with an invalid `Stripe-Signature` header returns HTTP 400 (rejected before processing).
- E2E-004-AC-11: `POST /webhooks/stripe` returns HTTP 200 on successful processing (never 4xx or 5xx for valid events).
- E2E-004-AC-12: `GET /subscription` returns the current subscription state including `tier_id`, `billing_state`, and `current_period_end`.

**E2E-005 — GDPR Erasure (test_gdpr_erasure.py)**

- E2E-005-AC-1: `DELETE /account` by an authenticated user returns HTTP 204.
- E2E-005-AC-2: After `DELETE /account`, subsequent authenticated requests using the same JWT return HTTP 401 (token invalidated via `token_invalidated_at`).
- E2E-005-AC-3: The GDPR erasure Celery task is enqueued to the `gdpr_erasure` queue after `DELETE /account`.
- E2E-005-AC-4: On the first execution of the GDPR erasure task, `USER.anonymous_id` is written (HMAC-SHA256 of `user_id || server_secret`) before any PII records are updated.
- E2E-005-AC-5: Subsequent retries of the erasure task read `USER.anonymous_id` from the database rather than recomputing it (idempotent — verified by running the task twice and confirming `anonymous_id` is unchanged).
- E2E-005-AC-6: After erasure task completion, the user's `email` and `display_name` fields are no longer the original PII values.
- E2E-005-AC-7: `UserCorrection` records with `training_consent=true` that belonged to the erased user reference `anonymous_id` (not the original `user_id`) after erasure.
- E2E-005-AC-8: Drawings owned by the erased user are either deleted or reassigned per the erasure policy.

**E2E-006 — Blocklist Two-Gate (test_blocklist_two_gate.py)**

- E2E-006-AC-1: `POST /drawings/hash-check` with a SHA-256 hash present in `file_hash_blocklist` returns HTTP 409 Conflict (never 200 or 400).
- E2E-006-AC-2: After a 409 response from hash-check, no `Drawing` record exists in the database for that hash.
- E2E-006-AC-3: After a 409 response from hash-check, no S3 pre-signed URL has been issued (verified by asserting no S3 put-object call was made).
- E2E-006-AC-4: `POST /drawings` submitted without a preceding valid `hash-check` call (or after a 409 hash-check) returns HTTP 400.
- E2E-006-AC-5: The ingest worker, after successfully uploading a file to S3, re-verifies the object's SHA-256 hash against the blocklist; if the hash has been added to the blocklist since upload (simulated by inserting the hash between upload and ingest), the drawing transitions to `Scan_Failed`.
- E2E-006-AC-6: `Scan_Failed` is a terminal state — `POST /drawings/{id}/retry` on a `Scan_Failed` drawing returns HTTP 400 (or 422) and no retry is enqueued.
- E2E-006-AC-7: A file whose hash is NOT on the blocklist passes both gates and proceeds to the scan queue.

**E2E-007 — Free Tier Limit (test_free_tier_limit.py)**

- E2E-007-AC-1: A free-tier user can successfully upload and initiate processing for their 1st, 2nd, and 3rd drawings in the current calendar month.
- E2E-007-AC-2: The free-tier monthly counter is incremented at job enqueue time — verified by: enqueuing drawing #3, asserting counter=3 before ML completes; then attempting drawing #4, which is rejected.
- E2E-007-AC-3: Attempting to initiate processing for a 4th drawing in the same calendar month returns an HTTP error response (4xx) indicating the free limit has been reached.
- E2E-007-AC-4: The `free_limit_reached` analytics event fires with `{ user_id, drawing_id, subscription_id }` before the upload is rejected, and the processing job is NOT enqueued to any Celery queue.
- E2E-007-AC-5: Concurrent upload race condition: two simultaneous `POST /drawings/{id}/upload-complete` calls for drawings #3 and #4 result in exactly one succeeding and one failing (counter increment atomicity).
- E2E-007-AC-6: After the user upgrades to Pro (simulated by updating subscription tier via Stripe webhook), subsequent drawings are not blocked by the monthly limit.
- E2E-007-AC-7: The monthly counter resets at the start of a new calendar month (verified by backdating three drawings to the previous month via DB seed and confirming current month allows uploads).

---

##### UX and design specification

N/A — this is a backend-only integration testing session. No frontend components are created or modified. All assertions are against HTTP API responses, database state, Celery queue payloads, Redis pub/sub messages, and captured analytics events.

---

##### Critical implementation notes

- **TDD workflow**: each test file must be written with all `it`/`test`-equivalent `def test_*` blocks and their assertions before verifying they pass. The initial state (prior to merging the session's PR against the full integrated system) should be "all tests runnable but some may fail against a partially integrated environment." The tests must be written correctly enough to fail for the right reasons.

- **Celery `task_always_eager`**: set `task_always_eager = True` in the Celery app configuration within the pytest fixture scope for tests in `test_upload_to_complete.py`, `test_correction_flow.py`, `test_export_sync_and_async.py`, `test_free_tier_limit.py`, `test_gdpr_erasure.py`, and `test_stripe_lifecycle.py` so that tasks execute synchronously within the test process. **Exception**: `test_blocklist_two_gate.py` test `test_ingest_second_gate_blocks_newly_listed_hash` MUST NOT use `task_always_eager` — it must use a real Redis broker (from `tests/integration/fixtures/redis.py`) and explicit `.get()` awaiting on the Celery result, to prove the persistent queue path works as required by §1.4 Rule 14.

- **`user_id` in job payload**: the `test_upload_to_complete.py` test asserting `processing_complete` analytics must inspect the `MLInferenceJobPayload` written to the `ml_inference` queue and confirm `user_id` is present and equals the authenticated user's ID, NOT a DB-fetched value inside the worker. Inspect via `celery_app.backend` or by capturing the `run_ml_inference.apply_async` call args.

- **Analytics mock capture**: mock `backend.app.analytics.posthog_client.PostHogClient.capture` (or equivalent) with `unittest.mock.patch` at the test module level. Collect all `call_args` and assert the exact payload shape from §1.10 — including event name string, `user_id`, `drawing_id`, and any required fields. Verify `user_id` is NOT empty for `processing_complete` and `processing_failed` events.

- **Stripe webhook signature**: construct test webhook payloads using `stripe.WebhookSignature.generate_header` (test mode) or replicate the HMAC-SHA256 signature construction with `STRIPE_WEBHOOK_SECRET`. The webhook endpoint validates the `Stripe-Signature` header. Tests that skip signature validation will produce false positives.

- **Stripe idempotency atomicity (E2E-004-AC-3)**: testing that the event ID is stored before state mutation requires either: (a) mocking the DB session to raise after event-ID insert, verifying no subscription update occurred, or (b) reading the `stripe_event` table directly via `db_session` after a successful webhook call and asserting the row exists. Option (b) is sufficient.

- **`training_consent` snapshot test (E2E-002-AC-8)**: create a correction, then call `PATCH /account/consent` to flip the user's consent, then read the existing `UserCorrection` record from the DB and assert its `training_consent` value matches the state at creation time, not the new state.

- **Under_Review NOT on canvas open (E2E-002-AC-3)**: simulate "canvas open" by calling `GET /drawings/{id}/symbols` and `GET /drawings/{id}` (read-only operations), then assert drawing state is still `Complete`. Only after `PATCH /symbols/{id}` (write) should the state transition occur.

- **Free tier counter race condition test (E2E-007-AC-5)**: use `asyncio.gather` or `threading.Thread` to fire two concurrent `POST /drawings/{id}/upload-complete` requests. Assert the DB counter is exactly 1 more than before, and that exactly one succeeded (202) and one failed (4xx). This test is inherently timing-dependent — run with `@pytest.mark.flaky(reruns=3)` if needed but document the race scenario.

- **GDPR `anonymous_id` idempotency (E2E-005-AC-5)**: invoke the GDPR erasure Celery task twice (first run sets `anonymous_id`, second run is a retry). Assert `USER.anonymous_id` is identical after both runs. Do NOT clear `anonymous_id` between runs.

- **S3 pre-signed URL in blocklist tests (E2E-006-AC-3)**: use `moto` or `localstack` from `s3_client` fixture. After a 409 hash-check, assert that `s3_client.generate_presigned_url` was never called by inspecting the mock call count.

- **`Scan_Failed` terminal state (E2E-006-AC-6)**: consult the `DRAWING_STATE_TRANSITIONS` constant (§1.3): `Scan_Failed: []`. The retry endpoint must reject this; the test must assert the drawing remains in `Scan_Failed` after the rejected retry attempt.

- **Do not assert timing-sensitive SSE delivery** as a hard assertion — instead, assert that the Redis pub/sub channel `drawing:status:{drawing_id}` received the correct `DrawingStatusSSEEvent` payloads by subscribing to the channel in the test fixture before triggering state transitions.

- **Symbol count for async export threshold**: use a DB seed fixture that inserts exactly 1,001 `DetectedSymbol` rows for a drawing. Assert `ExportRecord.status` is `'Queued'` immediately after `POST /drawings/{id}/exports`. Separately seed a drawing with exactly 1,000 symbols and assert the export completes synchronously.

- **Never assert on wall-clock timing for the <30s export SLA** in CI — assert that the export worker task is called with the correct arguments and that a completed export record exists. The 30s SLA is a monitoring target, not a CI gate.

- **Auth token for test requests**: use `create_test_token` (or equivalent from S1-B's `jwt_verifier.py`) to generate valid RS256 JWTs for test users. Do not call `POST /auth/login` in every test — that adds latency and couples tests to auth service behavior unnecessarily. Use direct token generation for all non-auth-specific tests.

- **`POST /drawings` without prior hash-check (E2E-006-AC-4)**: this must return 400. The implementation in S2-B enforces this via a session-scoped token or DB record linking hash-check result to subsequent drawing creation. The test must confirm the exact HTTP 400 status — not 422 or 500.

---

##### Mocking contract

This is a backend integration testing session. The following external services are stubbed via pytest fixtures and mocks:

**PostHog analytics client:**
```python
# Patch target: backend.app.analytics.posthog_client.PostHogClient.capture
# Fixture provides: mock_posthog (MagicMock capturing all calls)
# Captured call shape:
{
    "distinct_id": "<user_id>",
    "event": "<event_name>",  # e.g. "drawing_uploaded"
    "properties": {
        "drawing_id": "<uuid>",
        "user_id": "<uuid>",
        "timestamp": "<ISO8601>",
        # event-specific fields from §1.10
    }
}
```

**SendGrid notification client:**
```python
# Patch target: backend.app.workers.notification.sendgrid_client.SendGridClient.send
# Fixture provides: mock_sendgrid (MagicMock capturing all calls)
# Assert: called with correct template_id and to_email for grace period, verification, reset emails
```

**ClamAV client:**
```python
# Patch target: backend.app.workers.scan.clamav_client.ClamAVClient.scan
# Fixture provides: mock_clamav (configurable — returns "OK" or "FOUND: Eicar-Test-Signature")
# Default: returns "OK" (clean)
```

**ODA Converter:**
```python
# Patch target: backend.app.workers.ingest.oda_converter.ODAConverter.convert
# Fixture provides: mock_oda_converter (returns bytes of pre-canned PDF/raster fixture file)
# No actual subprocess is spawned
```

**ML model loader + inference:**
```python
# Patch target: backend.app.workers.ml.inference.MLInferenceEngine.run
# Fixture provides: mock_ml_engine (returns pre-canned MLInferenceResult)
# Default stub response shape:
{
    "drawing_id": "<uuid>",
    "symbols": [
        {
            "entity_class_id": "valve_gate",
            "subtype": "gate",
            "tag_label": "V-101",
            "confidence": 0.92,
            "bbox": {"x": 10, "y": 20, "w": 30, "h": 40},
            "page_number": 1
        }
    ],
    "tables": []
}
# For async export tests: stub returns 1001 symbols to trigger async path
```

**S3 (from S0-B fixture):**
```python
# Provided by: tests/integration/fixtures/s3.py → s3_client fixture (moto or localstack)
# Fixture ensures: bucket created, pre-signed URL generation works against stub
# Used by: test_upload_to_complete.py, test_blocklist_two_gate.py, test_export_sync_and_async.py
```

**Stripe webhook construction:**
```python
# No mock — construct real HMAC-signed webhook payloads using stripe library:
import stripe
payload = json.dumps({"id": "evt_test_001", "type": "checkout.session.completed", ...})
sig = stripe.WebhookSignature.generate_header(
    payload=payload.encode(),
    secret=TEST_STRIPE_WEBHOOK_SECRET,
    timestamp=int(time.time())
)
# POST to /webhooks/stripe with headers {"Stripe-Signature": sig}
```

**Redis pub/sub (from S0-B fixture):**
```python
# Provided by: tests/integration/fixtures/redis.py → redis_client, pubsub_listener fixtures
# pubsub_listener subscribes to drawing:status:{drawing_id} before test triggers state transitions
# Asserts: list of received DrawingStatusSSEEvent payloads matches expected state sequence
```

---

##### Acceptance criteria checklist

**E2E-001 — Upload to Complete**
- [ ] `POST /drawings/hash-check` with non-blocked hash returns 200 with `allowed=true` [E2E-001-AC-1]
- [ ] `POST /drawings` after valid hash-check creates Drawing in `Pending` state, returns 201 [E2E-001-AC-2]
- [ ] Pre-signed S3 URL in POST /drawings response has 900-second expiry [E2E-001-AC-3]
- [ ] HTTP PUT to pre-signed S3 URL succeeds (HTTP 200 from S3 stub) [E2E-001-AC-4]
- [ ] `POST /drawings/{id}/upload-complete` (first call) returns 202 and transitions Drawing to `Queued` [E2E-001-AC-5]
- [ ] `POST /drawings/{id}/upload-complete` (second call, already Queued) returns 200 and does not enqueue a second job [E2E-001-AC-6]
- [ ] `MLInferenceJobPayload` in Celery queue contains `user_id` equal to authenticated user's ID [E2E-001-AC-7]
- [ ] `drawing_uploaded` analytics event fires with correct payload at upload-complete time, before ML completion [E2E-001-AC-8]
- [ ] Drawing transitions to `Scanning` after ingest task; `DrawingStatusSSEEvent{state:'Scanning'}` published to Redis channel [E2E-001-AC-9]
- [ ] Drawing transitions to `Processing` after scan task (clean file); `DrawingStatusSSEEvent{state:'Processing'}` published [E2E-001-AC-10]
- [ ] Drawing transitions to `Complete` after ML inference task; `DrawingStatusSSEEvent{state:'Complete'}` published [E2E-001-AC-11]
- [ ] `processing_complete` analytics event fires from ML worker with `user_id` from job payload (not DB) [E2E-001-AC-12]
- [ ] Ingest worker server-side SHA-256 re-verification passes for unmodified stored object [E2E-001-AC-13]
- [ ] Detected symbols persisted in `detected_symbol` table with correct fields (`source='ml'`, `rejected=false`) [E2E-001-AC-14]
- [ ] `GET /drawings/{id}/symbols` returns HTTP 200 with `SymbolsPageResponse`, default page limit 200 [E2E-001-AC-15]
- [ ] Failed ML inference (1 retry exhausted) transitions Drawing to `Failed`; `processing_failed` fires; `processing_complete` does NOT fire [E2E-001-AC-16]
- [ ] `POST /drawings/{id}/retry` on `Failed` drawing re-enqueues ingest job (reusing `StoredFile`) and transitions to `Queued` [E2E-001-AC-17]
- [ ] `DELETE /drawings/{id}` returns HTTP 204 [E2E-001-AC-18]
- [ ] Unauthenticated `GET /drawings/{id}` returns HTTP 401 (never 403 or 200) [E2E-001-AC-19]
- [ ] Authenticated user accessing another user's drawing returns HTTP 403 (never 404 or 200) [E2E-001-AC-20]

**E2E-002 — Correction Flow**
- [ ] Precondition: `Complete` drawing with detected symbols exists [E2E-002-AC-1]
- [ ] `PATCH /symbols/{id}` with `correction_type=reclassify` and valid `new_class_id` returns HTTP 200 and creates `UserCorrection` record [E2E-002-AC-2]
- [ ] Drawing transitions from `Complete` to `Under_Review` on first correction action; `GET /drawings/{id}` confirms `processing_state=Under_Review` [E2E-002-AC-3]
- [ ] `GET /drawings/{id}` after only read operations (GET symbols, GET drawing) confirms state remains `Complete` (Under_Review NOT triggered by reads) [E2E-002-AC-3]
- [ ] `PATCH /symbols/{id}` with `correction_type=reject` sets `detected_symbol.rejected=true` in DB [E2E-002-AC-4]
- [ ] `PATCH /symbols/{id}` with `correction_type=restore` sets `detected_symbol.rejected=false` in DB [E2E-002-AC-5]
- [ ] `POST /drawings/{id}/symbols` with `source=manual` creates `DetectedSymbol` with `confidence=1.0` [E2E-002-AC-6]
- [ ] `correction_action` analytics event fires server-side for reclassify, reject, restore, and manual_add operations (4 separate assertions) [E2E-002-AC-7]
- [ ] `UserCorrection.training_consent` reflects consent state at creation time; changing consent after creation does not alter existing record [E2E-002-AC-8]
- [ ] `PATCH /symbols/{id}` for symbol on drawing not owned by caller returns HTTP 403 [E2E-002-AC-9]
- [ ] `GET /drawings/{id}/symbols` response includes `corrections_by_symbol_id` with correct correction history [E2E-002-AC-10]
- [ ] Second correction on same drawing (already `Under_Review`) does NOT re-trigger another state transition [E2E-002-AC-11]

**E2E-003 — Export Sync and Async**
- [ ] `POST /drawings/{id}/exports` with format=csv on drawing with ≤1,000 symbols initiates sync export path [E2E-003-AC-1]
- [ ] `export_initiated` analytics event fires at export creation time, before file generation completes [E2E-003-AC-2]
- [ ] `GET /exports/{id}` returns `status='Complete'` and pre-signed download URL for sync export [E2E-003-AC-3]
- [ ] Pre-signed download URL returns HTTP 200 with correct content-type for CSV [E2E-003-AC-4]
- [ ] Downloaded CSV contains a row for each non-rejected symbol in the drawing [E2E-003-AC-5]
- [ ] `POST /drawings/{id}/exports` with format=xlsx on drawing with ≤1,000 symbols produces a valid XLSX file [E2E-003-AC-6]
- [ ] `POST /drawings/{id}/exports` on drawing with >1,000 symbols creates `ExportRecord` with `status='Queued'` and enqueues async Celery task [E2E-003-AC-7]
- [ ] Client-supplied override flag cannot bypass server-side async threshold evaluation (server counts symbols, not client) [E2E-003-AC-8]
- [ ] Polling `GET /exports/{id}` for async export eventually returns `status='Complete'` with pre-signed URL [E2E-003-AC-9]
- [ ] Re-export creates new `ExportRecord`; prior export record `stored_file_id` is unchanged [E2E-003-AC-10]
- [ ] `export_downloaded` analytics event fires when pre-signed download URL is accessed [E2E-003-AC-11]
- [ ] Async export failure transitions `ExportRecord` to `status='Failed'`; `GET /exports/{id}` returns failed status [E2E-003-AC-12]

**E2E-004 — Stripe Lifecycle**
- [ ] `POST /subscription/checkout` returns response body containing a Stripe Checkout URL string [E2E-004-AC-1]
- [ ] Valid `checkout.session.completed` webhook transitions subscription to `Active`; returns HTTP 200 [E2E-004-AC-2]
- [ ] Stripe event ID stored in `stripe_event` table before subscription state mutation (verified by DB read) [E2E-004-AC-3]
- [ ] Second webhook with same event ID returns HTTP 200 without re-applying state mutations [E2E-004-AC-4]
- [ ] `customer.subscription.updated` webhook with tier upgrade fires `subscription_upgraded` analytics with correct `previous_tier` and `new_tier` [E2E-004-AC-5]
- [ ] `customer.subscription.updated` webhook with tier downgrade fires `subscription_downgraded` analytics immediately [E2E-004-AC-6]
- [ ] Subscription state after Checkout redirect (without webhook) remains unchanged — only webhook updates state [E2E-004-AC-7]
- [ ] `invoice.payment_failed` webhook transitions subscription to `Grace`; `grace_period_start` set in DB [E2E-004-AC-8]
- [ ] Grace state entry enqueues day-1 notification task to `notification` queue [E2E-004-AC-9]
- [ ] Webhook with invalid `Stripe-Signature` returns HTTP 400 [E2E-004-AC-10]
- [ ] Valid webhook returns HTTP 200 (never 4xx or 5xx) [E2E-004-AC-11]
- [ ] `GET /subscription` returns `tier_id`, `billing_state`, and `current_period_end` [E2E-004-AC-12]

**E2E-005 — GDPR Erasure**
- [ ] `DELETE /account` returns HTTP 204 [E2E-005-AC-1]
- [ ] Subsequent authenticated request with same JWT after `DELETE /account` returns HTTP 401 [E2E-005-AC-2]
- [ ] GDPR erasure Celery task is enqueued to `gdpr_erasure` queue after account deletion [E2E-005-AC-3]
- [ ] First erasure task execution writes `USER.anonymous_id` (HMAC-SHA256 of `user_id||server_secret`) before updating any PII records [E2E-005-AC-4]
- [ ] Second erasure task execution reads existing `USER.anonymous_id`; value unchanged after second run [E2E-005-AC-5]
- [ ] After erasure task, user's `email` and `display_name` are no longer original PII values [E2E-005-AC-6]
- [ ] `UserCorrection` records with `training_consent=true` reference `anonymous_id` (not original `user_id`) after erasure [E2E-005-AC-7]
- [ ] [MANUAL] Drawings owned by erased user are handled per erasure policy (deleted or reassigned) — requires reviewing data in test DB post-erasure [E2E-005-AC-8]

**E2E-006 — Blocklist Two-Gate**
- [ ] `POST /drawings/hash-check` with blocked hash returns HTTP 409 (never 200 or 400) [E2E-006-AC-1]
- [ ] After 409 hash-check, no `Drawing` record exists in DB for that hash [E2E-006-AC-2]
- [ ] After 409 hash-check, no `s3.generate_presigned_url` call was made (mock call count = 0) [E2E-006-AC-3]
- [ ] `POST /drawings` without valid prior hash-check returns HTTP 400 [E2E-006-AC-4]
- [ ] Ingest worker second-gate: hash added to blocklist between upload and ingest transitions drawing to `Scan_Failed` [E2E-006-AC-5]
- [ ] `POST /drawings/{id}/retry` on `Scan_Failed` drawing returns HTTP 4xx and no retry is enqueued [E2E-006-AC-6]
- [ ] Non-blocked file passes both gates and proceeds to scan queue normally [E2E-006-AC-7]

**E2E-007 — Free Tier Limit**
- [ ] Free-tier user can upload and initiate processing for drawings #1, #2, and #3 in same calendar month (all return 202) [E2E-007-AC-1]
- [ ] Free-tier monthly counter equals 3 in DB after drawing #3 is enqueued but before ML completes [E2E-007-AC-2]
- [ ] Attempt to initiate processing for drawing #4 in same month returns HTTP 4xx [E2E-007-AC-3]
- [ ] `free_limit_reached` analytics event fires with `{ user_id, drawing_id, subscription_id }` before processing is rejected, and no Celery job is enqueued [E2E-007-AC-4]
- [ ] Concurrent upload race: two simultaneous upload-complete calls for drawings #3 and #4 result in exactly one 202 and one 4xx; counter = 3 in DB [E2E-007-AC-5]
- [ ] After subscription upgrade (via Stripe webhook), drawing #4 upload-complete returns 202 [E2E-007-AC-6]
- [ ] Three drawings backdated to prior calendar month do not count toward current month's limit [E2E-007-AC-7]

---

##### Independent Test

- **Test file path** (TDD — written first, must fail before implementation verified): `tests/integration/e2e/` (directory containing all seven test modules; also acceptable to enumerate: `tests/integration/e2e/test_upload_to_complete.py`, `tests/integration/e2e/test_correction_flow.py`, `tests/integration/e2e/test_export_sync_and_async.py`, `tests/integration/e2e/test_stripe_lifecycle.py`, `tests/integration/e2e/test_gdpr_erasure.py`, `tests/integration/e2e/test_blocklist_two_gate.py`, `tests/integration/e2e/test_free_tier_limit.py`)

- **Exact CI command**: `pytest tests/integration/e2e/ -v --tb=short`

- **AC → assertion mapping**:

| AC | `it(...)` / `def test_*` |
|---|---|
| E2E-001-AC-1 | `test_hash_check_non_blocked_returns_allowed` |
| E2E-001-AC-2 | `test_post_drawings_after_hash_check_creates_pending_record` |
| E2E-001-AC-3 | `test_presigned_url_expiry_is_900_seconds` |
| E2E-001-AC-4 | `test_s3_put_via_presigned_url_succeeds` |
| E2E-001-AC-5 | `test_upload_complete_first_call_returns_202_and_queues` |
| E2E-001-AC-6 | `test_upload_complete_idempotent_returns_200_no_double_enqueue` |
| E2E-001-AC-7 | `test_ml_job_payload_contains_user_id_from_api_layer` |
| E2E-001-AC-8 | `test_drawing_uploaded_event_fires_at_enqueue_time` |
| E2E-001-AC-9 | `test_ingest_worker_transitions_to_scanning_and_publishes_sse` |
| E2E-001-AC-10 | `test_scan_worker_clean_file_transitions_to_processing` |
| E2E-001-AC-11 | `test_ml_worker_transitions_to_complete_and_publishes_sse` |
| E2E-001-AC-12 | `test_processing_complete_event_uses_job_payload_user_id` |
| E2E-001-AC-13 | `test_ingest_worker_sha256_reverify_passes_for_unmodified_object` |
| E2E-001-AC-14 | `test_detected_symbols_persisted_with_correct_fields` |
| E2E-001-AC-15 | `test_get_symbols_returns_200_with_paginated_response` |
| E2E-001-AC-16 | `test_ml_failure_after_retry_transitions_to_failed_fires_processing_failed_event` |
| E2E-001-AC-17 | `test_retry_failed_drawing_reuses_stored_file_and_queues` |
| E2E-001-AC-18 | `test_delete_drawing_returns_204` |
| E2E-001-AC-19 | `test_unauthenticated_get_drawing_returns_401` |
| E2E-001-AC-20 | `test_get_drawing_wrong_owner_returns_403` |
| E2E-002-AC-1 | (fixture setup — `complete_drawing_with_symbols` fixture) |
| E2E-002-AC-2 | `test_reclassify_symbol_returns_200_and_persists_correction` |
| E2E-002-AC-3 | `test_first_correction_action_transitions_to_under_review` |
| E2E-002-AC-3 | `test_read_only_operations_do_not_trigger_under_review` |
| E2E-002-AC-4 | `test_reject_symbol_sets_rejected_true` |
| E2E-002-AC-5 | `test_restore_symbol_sets_rejected_false` |
| E2E-002-AC-6 | `test_manual_add_symbol_has_confidence_1_and_source_manual` |
| E2E-002-AC-7 | `test_correction_action_event_fires_for_reclassify_reject_restore_manual_add` |
| E2E-002-AC-8 | `test_training_consent_snapshotted_at_creation_time` |
| E2E-002-AC-9 | `test_patch_symbol_wrong_owner_returns_403` |
| E2E-002-AC-10 | `test_get_symbols_includes_corrections_by_symbol_id` |
| E2E-002-AC-11 | `test_second_correction_does_not_change_state_from_under_review` |
| E2E-003-AC-1 | `test_post_export_sync_path_for_drawing_under_1000_symbols` |
| E2E-003-AC-2 | `test_export_initiated_event_fires_before_file_generated` |
| E2E-003-AC-3 | `test_get_export_returns_complete_with_presigned_url_sync` |
| E2E-003-AC-4 | `test_presigned_download_url_returns_200_with_correct_content_type_csv` |
| E2E-003-AC-5 | `test_csv_contains_row_per_non_rejected_symbol` |
| E2E-003-AC-6 | `test_xlsx_export_produces_valid_spreadsheet` |
| E2E-003-AC-7 | `test_post_export_async_path_for_drawing_over_1000_symbols` |
| E2E-003-AC-8 | `test_async_threshold_cannot_be_bypassed_client_side` |
| E2E-003-AC-9 | `test_get_export_polling_async_returns_complete` |
| E2E-003-AC-10 | `test_reexport_creates_new_record_does_not_overwrite_prior` |
| E2E-003-AC-11 | `test_export_downloaded_event_fires_on_url_access` |
| E2E-003-AC-12 | `test_async_export_failure_transitions_to_failed_status` |
| E2E-004-AC-1 | `test_post_checkout_returns_stripe_url` |
| E2E-004-AC-2 | `test_checkout_completed_webhook_activates_subscription` |
| E2E-004-AC-3 | `test_stripe_event_id_stored_before_state_mutation` |
| E2E-004-AC-4 | `test_duplicate_webhook_event_id_is_idempotent` |
| E2E-004-AC-5 | `test_subscription_updated_upgrade_fires_subscription_upgraded_event` |
| E2E-004-AC-6 | `test_subscription_updated_downgrade_fires_subscription_downgraded_event` |
| E2E-004-AC-7 | `test_checkout_redirect_without_webhook_does_not_update_subscription` |
| E2E-004-AC-8 | `test_invoice_payment_failed_transitions_to_grace` |
| E2E-004-AC-9 | `test_grace_entry_enqueues_day1_notification_task` |
| E2E-004-AC-10 | `test_webhook_with_invalid_signature_returns_400` |
| E2E-004-AC-11 | `test_valid_webhook_returns_200_never_5xx` |
| E2E-004-AC-12 | `test_get_subscription_returns_tier_billing_state_period_end` |
| E2E-005-AC-1 | `test_delete_account_returns_204` |
| E2E-005-AC-2 | `test_post_delete_jwt_returns_401` |
| E2E-005-AC-3 | `test_gdpr_erasure_task_enqueued_after_account_deletion` |
| E2E-005-AC-4 | `test_erasure_task_first_run_writes_anonymous_id_before_pii_update` |
| E2E-005-AC-5 | `test_erasure_task_second_run_anonymous_id_unchanged` |
| E2E-005-AC-6 | `test_erasure_task_removes_pii_from_user_record` |
| E2E-005-AC-7 | `test_user_corrections_reference_anonymous_id_after_erasure` |
| E2E-006-AC-1 | `test_hash_check_blocked_hash_returns_409` |
| E2E-006-AC-2 | `test_hash_check_409_no_drawing_record_created` |
| E2E-006-AC-3 | `test_hash_check_409_no_presigned_url_issued` |
| E2E-006-AC-4 | `test_post_drawings_without_hash_check_returns_400` |
| E2E-006-AC-5 | `test_ingest_second_gate_blocks_newly_listed_hash` |
| E2E-006-AC-6 | `test_retry_scan_failed_drawing_returns_4xx_no_enqueue` |
| E2E-006-AC-7 | `test_non_blocked_file_passes_both_gates_proceeds_normally` |
| E2E-007-AC-1 | `test_free_tier_allows_first_three_drawings_per_month` |
| E2E-007-AC-2 | `test_free_tier_counter_incremented_at_enqueue_not_completion` |
| E2E-007-AC-3 | `test_fourth_drawing_free_tier_returns_4xx` |
| E2E-007-AC-4 | `test_free_limit_reached_event_fires_before_rejection_no_celery_job` |
| E2E-007-AC-5 | `test_concurrent_uploads_counter_atomicity` |
| E2E-007-AC-6 | `test_after_upgrade_drawing_limit_no_longer_applies` |
| E2E-007-AC-7 | `test_backdated_drawings_do_not_count_toward_current_month` |

- **Fixtures / test doubles**:

```python
# tests/integration/e2e/conftest.py (if needed, does not duplicate S0-B conftest)

@pytest.fixture
def registered_user(db_session, async_client):
    """Creates a user via POST /auth/register and returns {user_id, jwt_token}."""

@pytest.fixture
def free_tier_user(registered_user, db_session):
    """Ensures registered_user has a free-tier subscription (no Stripe subscription)."""

@pytest.fixture
def pro_tier_user(registered_user, db_session):
    """Seeds user with active Pro subscription directly in DB."""

@pytest.fixture
def complete_drawing_with_symbols(free_tier_user, db_session, s3_client):
    """Seeds a Drawing in Complete state with 5 detected symbols via DB directly."""

@pytest.fixture
def drawing_with_1001_symbols(free_tier_user, db_session, s3_client):
    """Seeds a Drawing in Complete state with 1001 detected symbols."""

@pytest.fixture
def mock_posthog():
    """Patches PostHogClient.capture; yields mock for call assertions."""
    with unittest.mock.patch("backend.app.analytics.posthog_client.PostHogClient.capture") as m:
        yield m

@pytest.fixture
def mock_sendgrid():
    with unittest.mock.patch("backend.app.workers.notification.sendgrid_client.SendGridClient.send") as m:
        yield m

@pytest.fixture
def mock_clamav_clean():
    with unittest.mock.patch("backend.app.workers.scan.clamav_client.ClamAVClient.scan", return_value="OK"):
        yield

@pytest.fixture
def mock_clamav_infected():
    with unittest.mock.patch("backend.app.workers.scan.clamav_client.ClamAVClient.scan", return_value="FOUND: Eicar-Test-Signature"):
        yield

@pytest.fixture
def mock_oda_converter():
    """Returns bytes of minimal valid PDF fixture."""
    with unittest.mock.patch("backend.app.workers.ingest.oda_converter.ODAConverter.convert",
                             return_value=MINIMAL_PDF_BYTES):
        yield

@pytest.fixture
def mock_ml_inference_success():
    """Returns 1 pre-canned DetectedSymbolResult."""
    result = MLInferenceResult(drawing_id="<overridden>", symbols=[...1 symbol...], tables=[])
    with unittest.mock.patch("backend.app.workers.ml.inference.MLInferenceEngine.run", return_value=result):
        yield

@pytest.fixture
def mock_ml_inference_1001_symbols():
    """Returns 1001 DetectedSymbolResults for async export threshold tests."""
    ...

@pytest.fixture
def mock_ml_inference_failure():
    """Raises exception on first call, exception on retry (exhausts retries)."""
    with unittest.mock.patch("backend.app.workers.ml.inference.MLInferenceEngine.run",
                             side_effect=RuntimeError("GPU OOM")):
        yield

@pytest.fixture
def stripe_webhook_factory():
    """Returns a callable: (event_type, payload_dict) -> (json_bytes, sig_header)."""
    def _make(event_type, data, event_id="evt_test_001"):
        payload = json.dumps({"id": event_id, "type": event_type, "data": {"object": data}})
        sig = stripe.WebhookSignature.generate_header(
            payload=payload.encode(),
            secret=TEST_STRIPE_WEBHOOK_SECRET,
            timestamp=int(time.time())
        )
        return payload.encode(), sig
    return _make

@pytest.fixture
def blocked_hash_in_db(db_session):
    """Inserts a specific SHA-256 hash into file_hash_blocklist and returns it."""
    blocked = FileHashBlocklist(sha256_hash=BLOCKED_SHA256, reason="test")
    db_session.add(blocked)
    db_session.commit()
    return BLOCKED_SHA256

@pytest.fixture
def celery_eager():
    """Overrides Celery to task_always_eager=True for synchronous test execution."""
    from backend.app.workers.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    yield
    celery_app.conf.task_always_eager = False

@pytest.fixture
def celery_not_eager():
    """Explicitly ensures task_always_eager=False (real Redis broker)."""
    from backend.app.workers.celery_app import celery_app
    celery_app.conf.task_always_eager = False
    yield
```

- **Pre-conditions**:
  - PostgreSQL test database with all Alembic migrations applied (`0001_initial_schema`, `0002_rls_policies`, `0003_audit_partitions`) — via `apply_migrations` fixture from S0-B
  - Tier seed data applied (`seed_tiers`) — `free`, `pro`, `team` rows in `tier` table
  - Entity class seed data applied (`seed_entity_classes`) — all 8 entity class rows
  - Redis running and accessible via `redis_client` fixture from S0-B
  - S3/MinIO stub running via `s3_client` fixture from S0-B, bucket pre-created
  - Environment variables set: `STRIPE_WEBHOOK_SECRET=whsec_test_secret`, `HMAC_SERVER_SECRET=test_server_secret_32bytes`, `ML_JOB_TIMEOUT_SECONDS=1200`, `PRESIGNED_URL_EXPIRY_SECONDS=900`, `CELERY_BROKER_URL` pointing to test Redis
  - ClamAV, ODA Converter, ML model, PostHog, SendGrid — all mocked via fixtures (no real external calls)

- **Isolation rule**: these tests are NOT independently mergeable — they require all Phase 2 and Phase 3 sessions to be merged. See the Checkpoint section for explicit acknowledgment. Per the brief template rules, this is a planning-acknowledged dependency, not a defect: Phase 4 is by definition a post-integration phase. The tests are written to fail gracefully (import errors or 404s) if prerequisite sessions have not merged, rather than silently passing.

---

##### Checkpoint

- **One-sentence observable outcome**: Running `pytest tests/integration/e2e/ -v` against the fully integrated system (all Phase 2 and Phase 3 sessions merged) exits 0, with all 66 test cases passing, demonstrating that upload-to-complete, correction, export, billing, GDPR, blocklist, and free-tier flows operate correctly end-to-end.

- **Shippability claim**: **This PR is NOT independently mergeable to main if no other session in Phase 4 is being considered** — it depends on all Phase 2 (S2-A through S2-M) and Phase 3 (S3-A through S3-G) sessions having merged. This is a Phase 4 gate session by design. Blocking sessions: S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M, S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G. **This is an expected planning constraint, not a brief defect.**

---

##### Output and handoff

S4-A is a terminal session — it consumes all prior sessions and produces no exports that downstream sessions depend on. However, it produces the following artifacts that are load-bearing for CI/CD gate enforcement:

| Artifact | Consuming Session | Load-bearing? |
|---|---|---|
| `tests/integration/e2e/test_upload_to_complete.py` | CI pipeline gate (Phase 4) | [LOAD-BEARING] — must not be removed; required for merge gate |
| `tests/integration/e2e/test_correction_flow.py` | CI pipeline gate | [LOAD-BEARING] |
| `tests/integration/e2e/test_export_sync_and_async.py` | CI pipeline gate | [LOAD-BEARING] |
| `tests/integration/e2e/test_stripe_lifecycle.py` | CI pipeline gate | [LOAD-BEARING] |
| `tests/integration/e2e/test_gdpr_erasure.py` | CI pipeline gate | [LOAD-BEARING] |
| `tests/integration/e2e/test_blocklist_two_gate.py` | CI pipeline gate | [LOAD-BEARING] |
| `tests/integration/e2e/test_free_tier_limit.py` | CI pipeline gate | [LOAD-BEARING] |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/e2e/ -v --tb=short",
    "file": "tests/integration/e2e/"
  },
  "checkpoint": "Running `pytest tests/integration/e2e/ -v` against the fully integrated system exits 0, with all 66 test cases passing, demonstrating that upload-to-complete, correction, export, billing, GDPR, blocklist, and free-tier flows operate correctly end-to-end.",
  "manualAcs": [
    {
      "id": "E2E-005-AC-8",
      "text": "Drawings owned by erased user are handled per erasure policy (deleted or reassigned) — requires reviewing data in test DB post-erasure."
    }
  ],
  "exports": []
}
```