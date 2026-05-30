# PID Analyzer — Shared File Ownership Table

> **Reading guide**
> - *Importing sessions* = sessions whose owned code directly `import`/`require`/consume the file (direct dependency, not merely transitive)
> - **LOAD-BEARING** rows: any structural change to the file after its owner session merges requires updating every listed importing session's brief and re-running the consistency check
> - **FOUNDATIONAL** rows (second table): single-owner but architecturally critical — treat as immutable without a formal change-control note

---

## Part 1 — Cross-Session Import Table

### S0-A — Scaffold & Shared Stubs

| File path | Owner session | Importing sessions | Mutable after merge |
|-----------|---------------|--------------------|---------------------|
| `backend/app/config.py` | S0-A | S1-A, S1-B, S1-C, S1-D, S1-E, S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M | No — **LOAD-BEARING** |
| `backend/app/db/base.py` | S0-A | S1-A (model registration), S1-B, S1-C, S2-A–S2-M (ORM base class) | No — **LOAD-BEARING** |
| `backend/app/db/session.py` | S0-A | S1-A, S1-B, S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G, S2-H, S2-J, S2-L | No — **LOAD-BEARING** |
| `backend/app/schemas/contracts.py` | S0-A | S1-B, S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G, S2-H, S2-J | No — **LOAD-BEARING** |
| `backend/app/workers/celery_app.py` | S0-A | S1-D, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M | No — **LOAD-BEARING** |
| `backend/app/api/__init__.py` | S0-A | S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G | No — **LOAD-BEARING** |
| `backend/app/api/routers/__init__.py` | S0-A | S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G | No — **LOAD-BEARING** |
| `backend/app/main.py` | S0-A | S0-B (smoke tests assert startup), S4-A (integration test client) | No — **LOAD-BEARING** |
| `backend/app/workers/__init__.py` | S0-A | S1-D, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M | No — **LOAD-BEARING** |
| `backend/app/schemas/__init__.py` | S0-A | S1-B, S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G | No — **LOAD-BEARING** |
| `frontend/src/types/contracts.ts` | S0-A | S1-F, S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G | No — **LOAD-BEARING** |
| `frontend/src/router.tsx` | S0-A | S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G (lazy-loaded page stubs expanded in-place) | No — **LOAD-BEARING** |
| `frontend/src/App.tsx` | S0-A | S1-F (mounts AuthContext provider), S3-A–S3-G (rendered via router tree) | No — **LOAD-BEARING** |
| `frontend/src/main.tsx` | S0-A | S1-F (globals.css import point), S3-A–S3-G (root render context) | No — **LOAD-BEARING** |
| `docker-compose.yml` | S0-A | S0-B (fixture orchestration), S4-A (E2E env) | No — **LOAD-BEARING** |
| `docker-compose.test.yml` | S0-A | S0-B (CI test runner), S4-A | No — **LOAD-BEARING** |
| `.env.example` | S0-A | S0-B (env schema validation), S1-A–S1-F, S2-A–S2-M (variable reference spec) | No — **LOAD-BEARING** |
| `ops/oda-sandbox/Dockerfile` | S0-A | S2-H (ingest worker builds against this image) | No — **LOAD-BEARING** |
| `ops/clamav/Dockerfile` | S0-A | S2-I (scan worker builds against this image) | No — **LOAD-BEARING** |

---

### S0-B — Integration Harness & Manifests

| File path | Owner session | Importing sessions | Mutable after merge |
|-----------|---------------|--------------------|---------------------|
| `tests/integration/conftest.py` | S0-B | S1-A, S1-B, S1-C, S1-D, S1-E, S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M, S4-A | No — **LOAD-BEARING** |
| `tests/integration/fixtures/db.py` | S0-B | S1-A, S1-B, S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G, S2-H, S2-J, S2-L, S4-A | No — **LOAD-BEARING** |
| `tests/integration/fixtures/redis.py` | S0-B | S1-D, S2-B, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M, S4-A | No — **LOAD-BEARING** |
| `tests/integration/fixtures/s3.py` | S0-B | S1-C, S2-B, S2-D, S2-H, S2-I, S2-J, S2-K, S2-L, S4-A | No — **LOAD-BEARING** |
| `tests/integration/docker-compose.fixtures.yml` | S0-B | S1-A, S1-B, S1-C, S1-D, S1-E, S4-A (service fixture startup) | No — **LOAD-BEARING** |
| `backend/pyproject.toml` | S0-B | S1-A, S1-B, S1-C, S1-D, S1-E (shared dependency manifest) | No — **LOAD-BEARING** |
| `.github/workflows/integration.yml` | S0-B | S4-A (E2E tests run in this workflow) | No — **LOAD-BEARING** |

---

### S1-A — DB Models & Migrations

| File path | Owner session | Importing sessions | Mutable after merge |
|-----------|---------------|--------------------|---------------------|
| `backend/app/db/models/__init__.py` | S1-A | S1-B, S1-C, S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M | No — **LOAD-BEARING** |
| `backend/app/db/models/user.py` | S1-A | S1-B, S2-A, S2-B, S2-C, S2-E, S2-F, S2-L, S2-M | No — **LOAD-BEARING** |
| `backend/app/db/models/team.py` | S1-A | S1-B, S2-A, S2-F, S2-M | No — **LOAD-BEARING** |
| `backend/app/db/models/tier.py` | S1-A | S1-B, S2-E, S2-G | No — **LOAD-BEARING** |
| `backend/app/db/models/subscription.py` | S1-A | S1-B, S2-E, S2-F, S2-M | No — **LOAD-BEARING** |
| `backend/app/db/models/stored_file.py` | S1-A | S2-B, S2-D, S2-H, S2-I, S2-J, S2-K, S2-L | No — **LOAD-BEARING** |
| `backend/app/db/models/file_hash_blocklist.py` | S1-A | S1-C, S2-B, S2-H, S2-I | No — **LOAD-BEARING** |
| `backend/app/db/models/drawing.py` | S1-A | S2-B, S2-C, S2-D, S2-H, S2-I, S2-J, S2-K, S2-L | No — **LOAD-BEARING** |
| `backend/app/db/models/entity_class.py` | S1-A | S2-C, S2-G, S2-J | No — **LOAD-BEARING** |
| `backend/app/db/models/detected_symbol.py` | S1-A | S2-C, S2-J | No — **LOAD-BEARING** |
| `backend/app/db/models/table_cell.py` | S1-A | S2-D, S2-J | No — **LOAD-BEARING** |
| `backend/app/db/models/user_correction.py` | S1-A | S2-C, S2-J, S2-L | No — **LOAD-BEARING** |
| `backend/app/db/models/export_record.py` | S1-A | S2-D, S2-K | No — **LOAD-BEARING** |
| `backend/app/db/models/ml_training_consent.py` | S1-A | S2-C, S2-J, S2-L | No — **LOAD-BEARING** |
| `backend/app/db/models/revision_comparison.py` | S1-A | S2-B, S2-J | No — **LOAD-BEARING** |
| `backend/app/db/models/audit_log.py` | S1-A | S1-B, S2-A, S2-B, S2-F, S2-L | No — **LOAD-BEARING** |

---

### S1-B — Auth Middleware & Supabase Client

| File path | Owner session | Importing sessions | Mutable after merge |
|-----------|---------------|--------------------|---------------------|
| `backend/app/auth/dependencies.py` | S1-B | S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G | No — **LOAD-BEARING** |
| `backend/app/auth/permissions.py` | S1-B | S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G | No — **LOAD-BEARING** |
| `backend/app/auth/middleware.py` | S1-B | S0-A `main.py` (registered at startup), S2-A | No — **LOAD-BEARING** |
| `backend/app/auth/jwt_verifier.py` | S1-B | S2-A, S1-B `dependencies.py` (propagates to all S2 routers) | No — **LOAD-BEARING** |
| `backend/app/auth/supabase_client.py` | S1-B | S2-A, S2-F | No — **LOAD-BEARING** |

---

### S1-C — Storage & Hash Utilities

| File path | Owner session | Importing sessions | Mutable after merge |
|-----------|---------------|--------------------|---------------------|
| `backend/app/storage/s3_client.py` | S1-C | S2-B, S2-D, S2-H, S2-I, S2-J, S2-K, S2-L | No — **LOAD-BEARING** |
| `backend/app/storage/presigned.py` | S1-C | S2-B, S2-D | No — **LOAD-BEARING** |
| `backend/app/storage/hashing.py` | S1-C | S2-B, S2-H | No — **LOAD-BEARING** |
| `backend/app/storage/blocklist.py` | S1-C | S2-B, S2-H, S2-I | No — **LOAD-BEARING** |

---

### S1-D — Redis, Cache, Pub/Sub & Celery Config

| File path | Owner session | Importing sessions | Mutable after merge |
|-----------|---------------|--------------------|---------------------|
| `backend/app/redis/client.py` | S1-D | S2-A, S2-B, S2-C, S2-E, S2-F, S2-G, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M | No — **LOAD-BEARING** |
| `backend/app/redis/cache.py` | S1-D | S2-A, S2-B, S2-E, S2-G | No — **LOAD-BEARING** |
| `backend/app/redis/pubsub.py` | S1-D | S2-B, S2-H, S2-I, S2-J, S2-M | No — **LOAD-BEARING** |
| `backend/app/workers/queues.py` | S1-D | S2-B, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M | No — **LOAD-BEARING** |
| `backend/app/workers/base.py` | S1-D | S2-H, S2-I, S2-J, S2-K, S2-L, S2-M | No — **LOAD-BEARING** |

---

### S1-E — Analytics Emitter (PostHog)

| File path | Owner session | Importing sessions | Mutable after merge |
|-----------|---------------|--------------------|---------------------|
| `backend/app/analytics/events.py` | S1-E | S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-H, S2-J | No — **LOAD-BEARING** |

---

### S1-F — Frontend Shared Infrastructure

| File path | Owner session | Importing sessions | Mutable after merge |
|-----------|---------------|--------------------|---------------------|
| `frontend/src/api/client.ts` | S1-F | S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G | No — **LOAD-BEARING** |
| `frontend/src/api/endpoints.ts` | S1-F | S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G | No — **LOAD-BEARING** |
| `frontend/src/auth/AuthContext.tsx` | S1-F | S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G | No — **LOAD-BEARING** |
| `frontend/src/auth/useAuth.ts` | S1-F | S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G | No — **LOAD-BEARING** |
| `frontend/src/auth/supabaseClient.ts` | S1-F | S3-A, S3-E | No — **LOAD-BEARING** |
| `frontend/src/hooks/useSSE.ts` | S1-F | S3-B, S3-D, S3-G | No — **LOAD-BEARING** |
| `frontend/src/hooks/usePolling.ts` | S1-F | S3-B, S3-F, S3-G | No — **LOAD-BEARING** |
| `frontend/src/components/Layout.tsx` | S1-F | S3-A, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G | No — **LOAD-BEARING** |
| `frontend/src/components/ProtectedRoute.tsx` | S1-F | S0-A `router.tsx`, S3-B, S3-C, S3-D, S3-E, S3-F, S3-G | No — **LOAD-BEARING** |
| `frontend/src/components/GraceBanner.tsx` | S1-F | S1-F `Layout.tsx` (internal), S3-F (direct Subscription page use) | No — **LOAD-BEARING** |
| `frontend/src/lib/analytics.ts` | S1-F | S3-A, S3-B, S3-C, S3-D, S3-G | No — **LOAD-BEARING** |
| `frontend/src/lib/storage.ts` | S1-F | S3-A, S3-E, S3-F | No — **LOAD-BEARING** |
| `frontend/src/styles/globals.css` | S1-F | S0-A `main.tsx` (import point), S3-A–S3-G (cascade renders within) | No — **LOAD-BEARING** |

---

## Part 2 — Foundational Files (Single-Owner, Architecturally Critical)

These files appear in exactly one session's owned list and have zero or one direct code importer, but a structural change to any of them is as consequential as a LOAD-BEARING change. Treat them as **immutable after their owner session merges** unless a formal change-control note is issued.

| File path | Owner session | Why foundational |
|-----------|---------------|-----------------|
| `backend/alembic.ini` | S0-A | Governs all Alembic migration execution; changing DSN targets or script location breaks S1-A and every future migration session **FOUNDATIONAL** |
| `backend/alembic/env.py` | S0-A | Wires SQLAlchemy metadata to Alembic; any model-base change must be reflected here before S1-A migrations can run **FOUNDATIONAL** |
| `backend/alembic/script.py.mako` | S0-A | Template for every generated migration file; format changes corrupt S1-A migration output **FOUNDATIONAL** |
| `backend/Dockerfile` | S0-A | Base image and build layer shared by all backend API containers; a Python version or base-image change cascades to S2-A–S2-G deployments **FOUNDATIONAL** |
| `backend/Dockerfile.worker` | S0-A | Worker image definition consumed by S2-H–S2-M Celery containers **FOUNDATIONAL** |
| `backend/Dockerfile.ml` | S0-A | ML-specific base image; GPU driver or CUDA version changes break S2-J **FOUNDATIONAL** |
| `frontend/vite.config.ts` | S0-A | Vite build config shared across all SPA sessions (S1-F, S3-A–S3-G); alias changes break cross-session imports **FOUNDATIONAL** |
| `frontend/tsconfig.json` | S0-A | TypeScript path aliases and compiler options; `paths` changes break all frontend session imports **FOUNDATIONAL** |
| `marketing/next.config.js` | S0-A | Next.js build config for marketing site; changes break S3-H **FOUNDATIONAL** |
| `marketing/tsconfig.json` | S0-A | Marketing site TS config; changes break S3-H **FOUNDATIONAL** |
| `backend/alembic/versions/0001_initial_schema.py` | S1-A | Defines all tables, types, and constraints; retroactive changes require a new migration and re-seeding across every data-touching session **FOUNDATIONAL** |
| `backend/alembic/versions/0002_rls_policies.py` | S1-A | Row-Level Security policy definitions; changes silently break multi-tenant data isolation used by S1-B, S2-A–S2-G **FOUNDATIONAL** |
| `backend/alembic/versions/0003_audit_partitions.py` | S1-A | Partition strategy for audit_log; changes break S2-F, S2-L write paths **FOUNDATIONAL** |
| `backend/app/db/seed_tiers.py` | S1-A | Source of truth for tier IDs/limits referenced by S1-B permissions and S2-B free-tier counter; seed changes require S2-B and S2-E to update hard-coded constants **FOUNDATIONAL** |
| `backend/app/db/seed_entity_classes.py` | S1-A | Canonical entity taxonomy seeded to Redis cache (S1-D); changes require S2-C, S2-G, and S2-J to revalidate class IDs **FOUNDATIONAL** |
| `backend/app/db/models/stripe_event.py` | S1-A | Idempotency table for Stripe webhooks; schema changes break S2-E's `stripe_event_idempotency.py` **FOUNDATIONAL** |
| `backend/app/auth/brute_force.py` | S1-B | Rate-limiting logic for auth endpoints; changes affect security guarantees relied upon by S2-A without being directly imported by it **FOUNDATIONAL** |
| `backend/app/analytics/posthog_client.py` | S1-E | Low-level PostHog transport used by `events.py`; retry/batching changes affect all event-emitting sessions indirectly **FOUNDATIONAL** |
| `backend/app/analytics/dead_letter.py` | S1-E | Guarantees analytics durability for all 9 event types; loss of this path affects compliance reporting across S2-A–S2-J **FOUNDATIONAL** |
| `backend/app/services/drawing_state_machine.py` | S2-B | Enforces the drawing state DAG (§1.3); any state transition change must be reflected in S2-H (ingest), S2-I (scan), S2-J (ML) queue handlers **FOUNDATIONAL** |
| `backend/app/services/billing_state_machine.py` | S2-E | Enforces subscription/grace-period DAG; changes affect S2-B (quota gate), S2-D (export gate), S2-F (account state) **FOUNDATIONAL** |
| `backend/app/services/stripe_event_idempotency.py` | S2-E | Payment-integrity guard; changes risk double-billing; no importer but operationally critical **FOUNDATIONAL** |
| `backend/app/workers/ingest/oda_converter.py` | S2-H | Proprietary DWG/DXF conversion wrapper; API surface changes break the ingest pipeline that all drawing-dependent sessions depend upon at runtime **FOUNDATIONAL** |
| `backend/app/workers/gdpr/anonymizer.py` | S2-L | HMAC anonymous-ID scheme; any change to the HMAC key derivation or output format breaks GDPR audit trails and must be coordinated with S2-F and S4-A **FOUNDATIONAL** |

---

## Quick-Reference: Highest-Fan-Out LOAD-BEARING Files

The following ten files have the widest import surfaces and represent the highest change-risk in the project:

| Rank | File | Importing session count |
|------|------|------------------------|
| 1 | `tests/integration/conftest.py` | 19 sessions |
| 2 | `backend/app/config.py` | 18 sessions |
| 3 | `backend/app/redis/client.py` | 12 sessions |
| 4 | `backend/app/db/models/__init__.py` | 14 sessions |
| 5 | `backend/app/db/session.py` | 12 sessions |
| 6 | `frontend/src/api/client.ts` | 7 sessions |
| 7 | `frontend/src/auth/useAuth.ts` | 7 sessions |
| 8 | `backend/app/auth/dependencies.py` | 7 sessions |
| 9 | `backend/app/schemas/contracts.py` | 10 sessions |
| 10 | `backend/app/analytics/events.py` | 8 sessions |

Any PR touching these files must be reviewed against every importing session's brief before merge.