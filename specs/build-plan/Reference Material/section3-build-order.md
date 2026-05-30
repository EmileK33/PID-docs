# PID Analyzer — Precise Build Execution Order

---

## Phase 0

### Sessions Starting at Gate Open

| Session | Parallel with |
|---------|--------------|
| S0-A Scaffold & Shared Stubs | S0-B |
| S0-B Integration Harness & Manifests | S0-A |

**Parallelism:** S0-A and S0-B are fully parallel. Neither imports from the other. Both start from a clean repository simultaneously.

**Intra-phase sequencing:** None.

---

### Phase 0 → Phase 1 Gate Verification Checklist

A human must confirm every item independently before any Phase 1 session begins.

1. `docker compose -f docker-compose.yml up -d` completes without error; `docker ps` shows every service (`postgres`, `redis`, `localstack`, `clamav-sandbox`) with Docker health status **`healthy`** (not merely `running` or `starting`).
2. `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/healthz` returns **`200`**.
3. `cd backend && python -m pytest tests/integration/smoke/test_smoke.py -v` exits **0** with all collected tests passing (0 failures, 0 errors).
4. `bash scripts/test-integration.sh` exits **0** — this is the integration harness green baseline required by the gate definition.
5. `cd backend && python -c "from app.schemas.contracts import *; print('ok')"` prints `ok` and exits **0** — all Pydantic contract models import cleanly.
6. `cd frontend && npm run build` exits **0** and produces a non-empty `dist/` directory — TypeScript compiles without errors.
7. `cd marketing && npm run build` exits **0** — Next.js compiles without errors.
8. `curl -s http://localhost:8000/api/v1/drawings` returns HTTP **`200`** or **`501`** with a valid JSON body — stub router is mounted and reachable (not 404 or 500).
9. `python -c "import yaml; yaml.safe_load(open('.github/workflows/integration.yml'))"` exits **0** — workflow YAML is syntactically valid.
10. `docker compose -f docker-compose.test.yml config` exits **0** — test compose manifest is valid.

---

## Phase 1

### Sessions Starting at Phase 0 Gate Open

| Session | Parallel with |
|---------|--------------|
| S1-A DB Models & Migrations | S1-B, S1-C, S1-D, S1-E, S1-F |
| S1-B Auth Middleware & Supabase Client | S1-A, S1-C, S1-D, S1-E, S1-F |
| S1-C Storage & Hash Utilities | S1-A, S1-B, S1-D, S1-E, S1-F |
| S1-D Redis, Cache, Pub/Sub & Celery Config | S1-A, S1-B, S1-C, S1-E, S1-F |
| S1-E Analytics Emitter (PostHog) | S1-A, S1-B, S1-C, S1-D, S1-F |
| S1-F Frontend Shared Infrastructure | S1-A, S1-B, S1-C, S1-D, S1-E |

**Parallelism:** All six sessions are fully parallel. Each imports only from S0-A stubs and the S0-B harness. No Phase 1 session owns a file that another Phase 1 session imports at runtime.

**Intra-phase sequencing:** None.

**Note on S1-F:** S1-F gates Phase 3 only. It does **not** block the Phase 1 → Phase 2 gate for backend sessions. It must be merged before any Phase 3 session begins but does not hold up Phase 2.

---

### Phase 1 → Phase 2 Gate Verification Checklist

Required merges before Phase 2 opens: **S1-A, S1-B, S1-C, S1-D, S1-E**. (S1-F must also be merged before any Phase 3 session runs but does not block Phase 2.)

1. `cd backend && alembic upgrade head` exits **0**; `alembic current` output contains the string **`0003_audit_partitions (head)`**.
2. `psql $DATABASE_URL -c "\dt public.*"` lists at minimum: `audit_log`, `detected_symbol`, `drawing`, `entity_class`, `export_record`, `file_hash_blocklist`, `ml_training_consent`, `revision_comparison`, `stored_file`, `stripe_event`, `subscription`, `table_cell`, `team`, `tier`, `user`, `user_correction` — **16 tables present**.
3. `psql $DATABASE_URL -c "SELECT COUNT(*) FROM tiers;"` returns a count **≥ 1** (tier seed ran).
4. `psql $DATABASE_URL -c "SELECT COUNT(*) FROM entity_classes;"` returns a count **≥ 1** (entity class seed ran).
5. `cd backend && python -c "from app.auth.jwt_verifier import verify_token; from app.auth.permissions import ROLE_MATRIX; print('ok')"` exits **0**.
6. `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/auth/me` returns **`401`** — auth middleware is active and rejects unauthenticated requests.
7. `cd backend && python -m pytest tests/integration/test_auth_middleware.py -v` exits **0**.
8. `cd backend && python -m pytest tests/integration/test_storage.py -v` exits **0** — S3/LocalStack presigned URL generation and retrieval functional.
9. `cd backend && python -m pytest tests/integration/test_redis_pubsub.py -v` exits **0**.
10. `cd backend && celery -A app.workers.celery_app inspect ping -t 10` receives a pong response from **at least one worker node** — Celery app starts, broker connection established, queues declared.
11. `cd backend && python -m pytest tests/integration/test_analytics.py -v` exits **0**.
12. `redis-cli -u $REDIS_URL PING` returns **`PONG`** — Redis is reachable at the configured URL.

---

## Phase 2

### Sessions Starting at Phase 1 Gate Open

| Session | Parallel with |
|---------|--------------|
| S2-A Auth Endpoints | all other Phase 2 sessions |
| S2-B Drawings Endpoints + SSE Status | all other Phase 2 sessions |
| S2-C Symbols & Corrections Endpoints | all other Phase 2 sessions |
| S2-D Export Endpoints + Sync Path | all other Phase 2 sessions |
| S2-E Subscription + Stripe Webhook | all other Phase 2 sessions |
| S2-F Account, Consent & GDPR Init Endpoints | all other Phase 2 sessions |
| S2-G Entity Classes & Misc Endpoints | all other Phase 2 sessions |
| S2-H Ingest Worker | all other Phase 2 sessions |
| S2-I Scan Worker (ClamAV) | all other Phase 2 sessions |
| S2-J ML Worker | all other Phase 2 sessions |
| S2-K Export Worker (Async) | all other Phase 2 sessions |
| S2-L GDPR Erasure Worker | all other Phase 2 sessions |
| S2-M Notification Worker (SendGrid) | all other Phase 2 sessions |

**Parallelism:** All 13 sessions are fully parallel. Each owns a disjoint set of files (router, service, or worker subdirectory). Inter-session communication at runtime occurs exclusively through Celery task queues, Redis channels, and the database schema — all defined in Phase 1.

**Intra-phase sequencing:** None.

---

### Phase 2 → Phase 3 Gate

Phase 3 sessions unlock **individually** as their specific Phase 2 prerequisites merge; the full Phase 2 gate (all 13 merged) is required only before S4-A.

**Per-session Phase 3 unlock conditions:**

| Phase 3 Session | Unlocks when |
|-----------------|-------------|
| S3-A Auth Pages | S1-F ✓ AND S2-A ✓ |
| S3-B Drawing Library | S1-F ✓ AND S2-B ✓ |
| S3-C Upload Flow | S1-F ✓ AND S2-B ✓ |
| S3-D Review Canvas | S1-F ✓ AND S2-B ✓ AND S2-C ✓ |
| S3-E Account & Consent | S1-F ✓ AND S2-F ✓ |
| S3-F Subscription & Upgrade | S1-F ✓ AND S2-E ✓ |
| S3-G Exports UI + Notifications | S1-F ✓ AND S2-D ✓ |
| S3-H Marketing Site | S0-A ✓ (already satisfied in Phase 0) |

**Phase 2 → Phase 3 Gate Verification Checklist (per unlock group):**

**S1-F prerequisite (verify once, before any S3-A through S3-G begins):**
1. `cd frontend && npm run build` exits **0**, producing a non-empty `dist/`.
2. `cd frontend && npx tsc --noEmit` exits **0** — `AuthContext.tsx`, `useSSE.ts`, `usePolling.ts`, `api/client.ts`, `api/endpoints.ts` all type-check with no errors.

**Before S3-A (after S2-A merges):**
1. `curl -s -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"gate@example.com","password":"Test1234!"}' -o /dev/null -w "%{http_code}"` returns **`201`** or **`409`** (not 404 or 500).
2. `curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"x","password":"x"}' -o /dev/null -w "%{http_code}"` returns **`401`** or **`422`** (not 404 or 500).
3. `cd backend && python -m pytest tests/integration/test_auth_endpoints.py -v` exits **0**.

**Before S3-B and S3-C (after S2-B merges):**
1. `curl -s -H "Authorization: Bearer $TEST_TOKEN" http://localhost:8000/api/v1/drawings -o /dev/null -w "%{http_code}"` returns **`200`** (not 404 or 500).
2. `curl -s -X POST http://localhost:8000/api/v1/drawings/presign -H "Authorization: Bearer $TEST_TOKEN" -H "Content-Type: application/json" -d '{"filename":"t.pdf","content_type":"application/pdf","sha256":"abc123"}' -o /dev/null -w "%{http_code}"` returns **`200`** or **`400`** (not 404 or 500).
3. `curl -s -I -H "Authorization: Bearer $TEST_TOKEN" -H "Accept: text/event-stream" "http://localhost:8000/api/v1/drawings/sse/00000000-0000-0000-0000-000000000000"` response headers contain **`content-type: text/event-stream`**.
4. `cd backend && python -m pytest tests/integration/test_drawings_api.py tests/integration/test_drawings_sse.py -v` exits **0**.

**Before S3-D (after S2-B and S2-C both merge):**
1. All three S2-B checks above pass.
2. `curl -s -H "Authorization: Bearer $TEST_TOKEN" "http://localhost:8000/api/v1/drawings/00000000-0000-0000-0000-000000000000/symbols" -o /dev/null -w "%{http_code}"` returns **`200`** or **`404`** (not 500).
3. `cd backend && python -m pytest tests/integration/test_symbols_api.py -v` exits **0**.

**Before S3-E (after S2-F merges):**
1. `curl -s -H "Authorization: Bearer $TEST_TOKEN" http://localhost:8000/api/v1/account -o /dev/null -w "%{http_code}"` returns **`200`** (not 404 or 500).
2. `cd backend && python -m pytest tests/integration/test_account.py -v` exits **0**.

**Before S3-F (after S2-E merges):**
1. `curl -s -H "Authorization: Bearer $TEST_TOKEN" http://localhost:8000/api/v1/subscription -o /dev/null -w "%{http_code}"` returns **`200`** (not 404 or 500).
2. `curl -s -X POST http://localhost:8000/api/v1/stripe/webhook -H "Stripe-Signature: t=0,v1=invalid" -d '{}' -o /dev/null -w "%{http_code}"` returns **`400`** — Stripe signature validation executes (not 404 or 500).
3. `cd backend && python -m pytest tests/integration/test_subscription.py tests/integration/test_stripe_webhook.py -v` exits **0**.

**Before S3-G (after S2-D merges):**
1. `curl -s -H "Authorization: Bearer $TEST_TOKEN" http://localhost:8000/api/v1/exports -o /dev/null -w "%{http_code}"` returns **`200`** (not 404 or 500).
2. `cd backend && python -m pytest tests/integration/test_exports_api.py -v` exits **0**.

**S3-H has no additional backend gate** — S0-A was verified at Phase 0.

---

## Phase 3

### Sessions Starting at Their Respective Unlock Conditions

| Session | Parallel with |
|---------|--------------|
| S3-A Auth Pages | S3-B, S3-C, S3-D, S3-E, S3-F, S3-G, S3-H |
| S3-B Drawing Library | S3-A, S3-C, S3-D, S3-E, S3-F, S3-G, S3-H |
| S3-C Upload Flow | S3-A, S3-B, S3-D, S3-E, S3-F, S3-G, S3-H |
| S3-D Review Canvas | S3-A, S3-B, S3-C, S3-E, S3-F, S3-G, S3-H |
| S3-E Account & Consent | S3-A, S3-B, S3-C, S3-D, S3-F, S3-G, S3-H |
| S3-F Subscription & Upgrade | S3-A, S3-B, S3-C, S3-D, S3-E, S3-G, S3-H |
| S3-G Exports UI + Notifications | S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-H |
| S3-H Marketing Site | S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G |

**Parallelism:** All 8 sessions are fully parallel. Each owns a disjoint subdirectory (`frontend/src/features/<name>/`, `frontend/src/pages/<name>/`, or `marketing/`). All import from S1-F's shared infrastructure but not from each other's owned files.

**Intra-phase sequencing:** None.

---

### Phase 3 → Phase 4 Gate Verification Checklist

All Phase 2 and all Phase 3 sessions must be merged before S4-A begins.

1. `cd backend && python -m pytest tests/integration/ --ignore=tests/integration/e2e -v` exits **0** — all unit-level and session-level integration tests pass (covers all Phase 1 and Phase 2 test files).
2. `cd backend && celery -A app.workers.celery_app inspect registered` output contains task names from all six worker modules: strings matching `ingest.tasks`, `scan.tasks`, `ml.tasks`, `export.tasks`, `gdpr.tasks`, `notification.tasks` are all present.
3. `cd frontend && npm run build` exits **0** — all Phase 3 sessions compile together without TypeScript errors; `dist/` produced.
4. `cd frontend && npx tsc --noEmit` exits **0** — full type-check across all `frontend/src/**` with zero errors.
5. Navigate a browser (or `curl -s http://localhost:5173/`) to each of the following routes; each returns a non-empty HTML body and the browser console shows **zero uncaught errors**: `/`, `/auth/login`, `/auth/register`, `/upload`, `/dashboard`, `/account`, `/subscription`.
6. `cd marketing && npm run build` exits **0** — Next.js produces a `.next/` output directory.
7. `curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/` returns **`200`** (marketing preview server running).
8. `curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/pricing` returns **`200`** (pricing route rendered).

---

## Phase 4

### Sessions Starting at Phase 3 Gate Open

| Session | Parallel with |
|---------|--------------|
| S4-A E2E Integration Tests | — (sole session) |

**Parallelism:** N/A.

**Intra-phase sequencing:** N/A.

---

## Early-Start Optimizations

### 1. S1-F — Start with Phase 1 (no Phase 2 wait)

**Session:** S1-F (Frontend Shared Infrastructure)  
**Enabling prerequisites:** S0-A + S0-B (the Phase 0 gate — identical to all other Phase 1 sessions)  
**Optimization:** S1-F begins in full parallel with S1-A through S1-E. It does not need to wait for any Phase 2 backend session. Because it gates only Phase 3, this means Phase 3 frontend sessions can begin unlocking as soon as individual Phase 2 sessions complete rather than waiting for the full Phase 2 sweep.  
**Risk:** S1-F consumes `frontend/src/types/contracts.ts` (owned by S0-A). If a schema discrepancy discovered during S1-A's migration work forces a revision to `contracts.ts`, S1-F may need a patch pass. Probability: low, because `contracts.ts` is locked at Phase 0 merge. Impact: one targeted fix to S1-F before affected Phase 3 sessions start.

---

### 2. S3-H — Start as early as Phase 1

**Session:** S3-H (Marketing Site)  
**Enabling prerequisites:** S0-A only (provides `marketing/next.config.js`, `marketing/tsconfig.json`, `marketing/app/layout.tsx`)  
**Optimization:** S3-H can begin immediately after S0-A merges — in parallel with S0-B and all of Phase 1. It has zero backend or shared-frontend dependency.  
**Risk:** If `marketing/next.config.js` or `marketing/tsconfig.json` are revised after S3-H starts (e.g., a Phase 1 fix to S0-A outputs), a merge conflict on those two files is possible. Mitigation: treat S0-A's marketing scaffold files as immutable after merge. Impact if conflict occurs: trivial manual merge, no logic change.

---

### 3. S2-G — Start as soon as S1-A + S1-D merge (skip S1-B, S1-C, S1-E wait)

**Session:** S2-G (Entity Classes & Misc Endpoints)  
**Enabling prerequisites:** S1-A + S1-D (declared in the prerequisites column)  
**Optimization:** S2-G's only runtime dependencies are ORM models (S1-A) and Redis cache for entity taxonomy (S1-D). It does not call storage, auth, or analytics directly. If S1-B, S1-C, or S1-E are delayed, S2-G proceeds without them.  
**Risk:** S2-G's entity class router will ultimately sit behind auth middleware (S1-B). If S2-G is implemented before S1-B merges, the auth dependency is resolved against the S0-A stub (`_stubs.py`). If the stub signature diverges from S1-B's final `dependencies.py` interface, S2-G will need one wiring fix. Impact: small, localized to `entity_classes.py` route decorator. Probability: low if S0-A stubs are written to the correct interface.

---

### 4. S2-M — Start as soon as S1-A + S1-D merge (skip S1-B, S1-C, S1-E wait)

**Session:** S2-M (Notification Worker)  
**Enabling prerequisites:** S1-A + S1-D  
**Optimization:** The notification worker reads user records (S1-A models) and enqueues/dequeues tasks via Celery (S1-D). It does not call S3 storage, verify JWTs, or emit PostHog events.  
**Risk:** Negligible. The worker is triggered by a Celery task payload, not an HTTP request, so auth middleware is irrelevant to its logic. If S1-E's `dead_letter.py` interface changes, S2-M is unaffected because it does not import from `app.analytics`.

---

### 5. S2-L — Start as soon as S1-A + S1-C + S1-D merge (skip S1-B and S1-E wait)

**Session:** S2-L (GDPR Erasure Worker)  
**Enabling prerequisites:** S1-A + S1-C + S1-D  
**Optimization:** GDPR erasure reads and wipes DB records (S1-A), purges S3 objects (S1-C), and uses Celery (S1-D). It is never called via an authenticated HTTP endpoint — it is enqueued by `S2-F`'s GDPR init service. No JWT verification or analytics emission.  
**Risk:** Very low. The only exposure is if S1-B's HMAC secret constant (used by `anonymizer.py` for the `anonymous_id` derivation) is defined in `app.auth` rather than `app.config`. If so, `anonymizer.py` would import from a stub. Mitigation: define the HMAC secret in `app/config.py` (owned by S0-A) rather than in S1-B's auth module.

---

### 6. S3-A — Unlock immediately when S2-A + S1-F merge (no other Phase 2 dependencies)

**Session:** S3-A (Frontend Auth Pages)  
**Enabling prerequisites:** S1-F + S2-A  
**Optimization:** S3-A is the fastest Phase 3 session to unlock because S2-A has the fewest workers (no S1-C storage dependency), making it likely to complete before S2-B or S2-E. Frontend auth work can begin while the majority of Phase 2 is still in progress.  
**Risk:** Near zero. S3-A imports exclusively from `frontend/src/auth/` and `frontend/src/api/` (S1-F) and calls the auth endpoints defined in S2-A. If the auth endpoint contract changes after S2-A merges, a small patch to S3-A's `endpoints.ts` calls is needed. Probability: very low post-merge.

---

## Critical Path

**`S0-A` → `S1-A` → `S2-B` → `S3-D` → `S4-A`**

Rationale for each link:
- **S0-A → S1-A:** S1-A imports from `app/db/base.py`, `app/db/session.py`, and `app/schemas/contracts.py` — all owned by S0-A. S1-A is the largest Phase 1 session (17 models, 3 migrations, 2 seed scripts) and the one whose output is required by the most Phase 2 sessions.
- **S1-A → S2-B:** S2-B depends on S1-A for all drawing-related ORM models, plus S1-B, S1-C, S1-D, and S1-E — but S1-A is the longest of those five and therefore the last to satisfy S2-B's prerequisites in the worst case. S2-B is itself the largest Phase 2 API session (state machine, SSE, free-tier counter, hash-check service).
- **S2-B → S3-D:** S3-D requires both S2-B and S2-C. S2-B is the larger of the two, so it is S2-B that determines when S3-D can start. S3-D is the largest Phase 3 session (Konva canvas, 9 files, correction store, keyboard shortcuts).
- **S3-D → S4-A:** S4-A cannot begin until all Phase 2 and Phase 3 sessions are merged, and S3-D (complexity L) is among the last Phase 3 sessions to complete.

**Total depth:** 5 sessions, all rated complexity L, ≈ 15 hours of serial execution. Any slip on S0-A, S1-A, S2-B, S3-D, or S4-A propagates directly to the final delivery date with no parallel track available to absorb it.