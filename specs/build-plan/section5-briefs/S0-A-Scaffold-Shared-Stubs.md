---

#### S0-A — Scaffold & Shared Stubs

**Phase 0 | Infrastructure | Needs: none**

##### Objective

Create the complete monorepo scaffold (FastAPI backend, React+Vite SPA, Next.js marketing, Docker Compose, Alembic, Celery, shared TypeScript/Pydantic contracts, and stub route/page modules) so every downstream session has a stable, importable surface to build against.

##### Scope

P0 MVP. All route stubs and page stubs for both P0 and P1 endpoints/pages from §1.6 must be present (P1 stubs return `501 Not Implemented`; P0 stubs return `501 Not Implemented` and will be overwritten by Phase 2 sessions). No business logic. No DB models (S1-A owns those). No real auth (S1-B owns that). This session produces the skeleton only.

##### Technology constraints

Sourced from §1.8 (non-negotiable):

- **Backend**: FastAPI (Python 3.11+). MUST NOT use Flask, Django, or any other web framework.
- **Async workers**: Celery on Redis broker. MUST NOT use RQ, Dramatiq, arq, or in-memory queues — NFR-7 requires durable persistence.
- **Database**: PostgreSQL via SQLAlchemy 2.x + Alembic migrations. MUST NOT use Django ORM, raw psycopg without SQLAlchemy session, or any other migration tool (e.g., yoyo, dbmate).
- **Cache/queue/SSE**: Redis (single instance for Phase 0/1).
- **Frontend SPA**: React 18 + Vite + TypeScript. MUST NOT use Next.js, Create React App, or Remix for the SPA.
- **Marketing**: Next.js 14+ App Router (separate deployment from SPA). MUST NOT collapse into the SPA — §1.8 mandates separation for SEO/SSR.
- **Canvas**: Konva.js will be imported by S3-D (do not add to scaffold unless needed by stubs — it is not).
- **Auth**: Supabase Auth client to be wired in S1-B/S1-F; scaffold must NOT hand-roll JWT verification here.
- **Docker**: three separate Dockerfiles required — API (`backend/Dockerfile`), CPU worker (`backend/Dockerfile.worker`), GPU ML worker (`backend/Dockerfile.ml`). The ML Dockerfile must base on an NVIDIA CUDA image (e.g., `nvidia/cuda:12.x-runtime-ubuntu22.04`).
- **ODA sandbox**: `ops/oda-sandbox/Dockerfile` must declare `USER` non-root, no network egress capability (documented in comments — runtime enforcement is infra-time), and read-only root filesystem intent.
- **ClamAV**: `ops/clamav/Dockerfile` based on the official `clamav/clamav` image.

##### Performance targets

None — see downstream sessions. Scaffold must boot (`uvicorn` starts, `vite dev` starts, `next dev` starts) without runtime error.

##### Owned files

(exactly as listed in the prompt — exhaustive, do not touch anything else)

##### Read-only imports

None — this is the root session.

##### Do not touch

Every file not in the Owned files list. Specifically:
- Any file under `backend/app/db/models/**` (owned by S1-A)
- Any file under `backend/app/auth/**` (owned by S1-B)
- Any file under `backend/app/storage/**` (owned by S1-C)
- Any file under `backend/app/redis/**`, `backend/app/workers/queues.py`, `backend/app/workers/base.py` (owned by S1-D)
- Any file under `backend/app/analytics/**` (owned by S1-E)
- Any file under `frontend/src/api/**`, `frontend/src/auth/**`, `frontend/src/hooks/**`, `frontend/src/components/**`, `frontend/src/lib/**`, `frontend/src/styles/**` (owned by S1-F)
- `package.json` root, `backend/pyproject.toml`, `backend/poetry.lock`, `frontend/package.json`, `marketing/package.json`, `tests/integration/**`, `scripts/test-integration.sh`, `.github/workflows/**` (all owned by S0-B)

Entry points (`backend/app/main.py`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/router.tsx`, `marketing/app/layout.tsx`, `marketing/app/page.tsx`) ARE owned by this session — this is the one session permitted to write them. After this PR merges they become the "do not touch" entry points for all downstream sessions.

##### Architecture context

Verbatim from the distilled spec:

**§1.8 Technology Stack — Selected Choices:**
> **Frontend SPA**: React + Vite — Canvas rendering via Konva.js requires rich ecosystem; pure SPA sufficient for authenticated views.
> **Marketing/Landing**: Next.js (separate deployment) — SSR required for NFR-17 SEO; separate from SPA to avoid complexity bleed.
> **API Server**: FastAPI (Python) — Unifies language with ML worker codebase, eliminating cross-service interface surface; Python-first ML ecosystem.
> **Async Workers**: Celery on Redis broker — Durable persistent queue (NFR-7); Redis already required for cache + SSE; Celery retry/timeout/priority support; changing broker requires worker rewrite.
> **Deployment**: Docker on ECS Fargate (API + CPU workers); EC2 G4dn (GPU ML workers) — GPU instance type selection is irreversible at infrastructure provisioning time.

**§1.11 Celery Job Queue Names** (queues must be declared in `celery_app.py`):

| Queue | Workers | Job Types |
|---|---|---|
| `ingest` | Ingest Worker (CPU) | DWG-to-raster conversion, format detection, post-storage hash verification |
| `scan` | Scan Worker (ClamAV sidecar, CPU) | Malware scan |
| `ml_inference` | ML Worker (GPU — G4dn) | Symbol detection + table extraction |
| `export` | Export Worker (CPU) | CSV/XLSX generation |
| `gdpr_erasure` | GDPR Worker (CPU, scheduled) | PII purge, anonymization |
| `notification` | Notification Worker (CPU) | SendGrid email dispatch |

**§1.6 Route Manifest** (full list — every endpoint must have a stub returning `501 Not Implemented`; every SPA route must have a lazy-loaded stub page):

Backend P0:
```
POST   /auth/register
POST   /auth/login
POST   /auth/oauth/google
POST   /auth/refresh
POST   /auth/logout
POST   /auth/password-reset/request
POST   /auth/password-reset/confirm
POST   /drawings/hash-check
GET    /drawings
POST   /drawings
GET    /drawings/{id}
PATCH  /drawings/{id}
DELETE /drawings/{id}
POST   /drawings/{id}/retry
GET    /drawings/{id}/status              (SSE stream)
GET    /drawings/{id}/symbols
PATCH  /symbols/{id}
POST   /drawings/{id}/symbols
POST   /drawings/{id}/exports
GET    /exports/{id}
POST   /drawings/{id}/upload-complete
GET    /account
PATCH  /account
DELETE /account
GET    /account/consent
PATCH  /account/consent
GET    /subscription
POST   /subscription/checkout
POST   /webhooks/stripe
GET    /entity-classes
```

Backend P1:
```
GET    /teams
POST   /teams
GET    /teams/{id}/members
POST   /teams/{id}/members
DELETE /teams/{id}/members/{user_id}
GET    /teams/{id}/consent
PATCH  /teams/{id}/consent
POST   /drawings/compare
GET    /comparisons/{id}
GET    /drawings/{id}/tables
PATCH  /table-cells/{id}
GET    /exports/{id}/comparison-csv
```

SPA P0 routes:
```
/register /login /verify-email /dashboard /upload /drawings/{id}/review /account /subscription
```

SPA P1 routes:
```
/teams /teams/{id}/members /teams/invite/accept /comparisons/{id}
```

**§1.12 Environment Variable Schema** — every variable listed there must appear in `.env.example` with the documented default (or `<REQUIRED>` placeholder). `backend/app/config.py` must load all of them via Pydantic `BaseSettings` and apply the documented startup behavior (refuse to start vs. warn vs. use default). The session is REQUIRED to implement the "refuse to start" semantics — startup must `sys.exit(1)` with a clear message naming the missing/invalid variable.

**§1.1 Shared Contracts** must be mirrored in BOTH:
- `backend/app/schemas/contracts.py` as Pydantic v2 models / `Literal` types
- `frontend/src/types/contracts.ts` as TypeScript types (verbatim copy of the §1.1 block, no edits)

##### User stories and acceptance criteria

N/A — scaffold session. No user stories. Acceptance is operational (services boot, stubs respond `501`, contracts importable).

##### UX and design specification

N/A — scaffold owns stub page components only. Each stub page renders a single `<h1>{routeName} (stub)</h1>` placeholder. Real UX is delivered in S3-A through S3-H.

##### Critical implementation notes

- **Every endpoint stub returns HTTP 501** with body `{"detail": "Not implemented — session <S2-X> owns this endpoint"}`. This is the only acceptable stub behavior. Do NOT return 200, 404, or empty body — downstream tests in S0-B's smoke harness assert 501.
- **EXCEPT**: `GET /healthz` MUST be implemented and return `200 OK` with body `{"status": "ok"}`. This is the checkpoint signal. Place it in `backend/app/main.py`, not in `_stubs.py`.
- **Router include order in `backend/app/main.py` is load-bearing**: include every router from `backend/app/api/routers/__init__.py` via a single `app.include_router(...)` loop. Downstream sessions will REPLACE individual router modules (e.g., S2-A replaces the auth stub by creating `backend/app/api/routers/auth.py`); the include mechanism must auto-pick the replacement without main.py edits. Implement this by having `_stubs.py` define every route under its final path, and have each future-owned router file (auth.py, drawings.py, etc.) NOT exist yet — `__init__.py` exposes a single `stubs_router` for now, and downstream sessions will add their own routers and update `__init__.py` to swap in. Document this swap protocol in a comment at the top of `routers/__init__.py`.
- **Celery `celery_app.py` must declare all six queues from §1.11** with `task_routes` config, even though no tasks exist yet. Downstream worker sessions register tasks against these queue names; renaming queues post-merge breaks every worker.
- **Pydantic contracts in `schemas/contracts.py` are LOAD-BEARING**: field names, types, and `Literal` values must match §1.1 verbatim. Any rename here cascades into S2-B, S2-C, S2-J, and the frontend.
- **TypeScript `contracts.ts` must be a verbatim transcription of §1.1**. Do not rename `snake_case` fields to `camelCase` — the API serves snake_case and the frontend consumes snake_case to keep contract parity (this is a deliberate choice; do not "fix" it).
- **`.env.example` must list every variable from §1.12** with the documented default value or `<REQUIRED>` marker — S0-B's integration harness reads from a copy of this file.
- **Docker Compose `docker-compose.yml` must define services**: `postgres` (postgres:16), `redis` (redis:7), `api` (built from `backend/Dockerfile`), `worker` (built from `backend/Dockerfile.worker`), `ml-worker` (built from `backend/Dockerfile.ml`, profile `gpu` so it's opt-in), `clamav` (built from `ops/clamav/Dockerfile`), `oda-sandbox` (built from `ops/oda-sandbox/Dockerfile`, profile `ingest`), `frontend` (vite dev server), `marketing` (next dev server). `docker-compose.test.yml` overrides with ephemeral volumes for CI.
- **ODA sandbox Dockerfile**: must contain comments documenting "no network egress at runtime — enforced by ECS task definition `networkMode: none` in production" and "read-only filesystem at runtime — enforced by `readOnlyRootFilesystem: true`". Use `USER 1000:1000` non-root.
- **Do NOT add real database models, real auth, real S3 clients, or real Redis client wrappers**. Those belong to S1-A through S1-F. This session creates empty `__init__.py` files where appropriate as placeholders.
- **Alembic `env.py`** must import `Base` from `backend/app/db/base.py` (which exports an empty `Base = declarative_base()`) so S1-A can attach models without touching `env.py`.
- **`frontend/src/router.tsx`** must lazy-import every page stub via `React.lazy(...)`. This file becomes the "do not touch" router for Phase 3 — downstream frontend sessions REPLACE the stub page file (e.g., S3-A overwrites `frontend/src/pages/_stubs.tsx`? NO — S3-A creates its own files under `frontend/src/pages/auth/*` and updates router.tsx). **Exception**: because S3 sessions need to add their own page imports to `router.tsx`, this scaffold's `router.tsx` must be structured as a single declarative route array with clearly-marked `// SESSION: S3-X` insertion comments so downstream sessions can add lines without restructuring. Frontend session briefs will be told to edit `router.tsx` despite the "do not touch entry points" rule — this is the documented exception.

##### Mocking contract

N/A — this session defines contracts, does not consume them.

External service contracts referenced (no implementation here, just declared in `.env.example`):
- Supabase Auth, Stripe, SendGrid, PostHog, AWS S3 — all per §1.7.

##### Acceptance criteria checklist

- [ ] `docker compose up postgres redis api` boots without error and `curl localhost:8000/healthz` returns `200 {"status":"ok"}`
- [ ] Every backend route from §1.6 (both P0 and P1, total ≥40 endpoints) is registered in the FastAPI app and returns HTTP `501` with a JSON body containing `"detail"` mentioning the owning session ID
- [ ] `GET /healthz` returns `200` (not 501) and is the only non-501 endpoint
- [ ] `backend/app/schemas/contracts.py` exports Pydantic models for every type in §1.1: `MLInferenceJobPayload`, `MLInferenceResult`, `DetectedSymbolResult`, `TableRegionResult`, `TableCellResult`, `BoundingBox`, `DrawingProcessingState` (Literal), `BillingState` (Literal), `TierId` (Literal), `UserRole` (Literal), `SymbolSource` (Literal), `CorrectionType` (Literal), `ExportFormat` (Literal), `ExportStatus` (Literal), `EntityClassId` (Literal), `DrawingStatusSSEEvent`, `HashCheckRequest`, `HashCheckResponse`, `SymbolsPageResponse`, `SymbolRecord`, `CorrectionRecord`
- [ ] `frontend/src/types/contracts.ts` is a verbatim copy of the §1.1 TypeScript block (no field renames, no comments removed)
- [ ] `backend/app/workers/celery_app.py` declares all six queues from §1.11 (`ingest`, `scan`, `ml_inference`, `export`, `gdpr_erasure`, `notification`) in `task_routes` config
- [ ] `backend/app/config.py` loads every env var from §1.12 via Pydantic `BaseSettings`; missing `DATABASE_URL` causes `sys.exit(1)` on import with a clear error naming the variable
- [ ] `.env.example` lists every variable from §1.12 with the documented default or `<REQUIRED>` placeholder
- [ ] `alembic upgrade head` runs against the docker-compose postgres without error (no migrations exist yet, but the env is wired up)
- [ ] `frontend` dev server (`npm run dev` in frontend/) starts and serves all SPA routes from §1.6 as stub pages
- [ ] `marketing` dev server (`npm run dev` in marketing/) starts and serves `/` and `/pricing` stub pages
- [ ] Three Docker images build successfully: `backend/Dockerfile`, `backend/Dockerfile.worker`, `backend/Dockerfile.ml` (CUDA base) [MANUAL]
- [ ] `ops/clamav/Dockerfile` and `ops/oda-sandbox/Dockerfile` build successfully; oda-sandbox runs as non-root `USER 1000:1000` [MANUAL]

##### Independent Test

- **Test file path** (TDD — written first, must fail before implementation): `tests/sessions/s0-a.test.py`
- **Exact CI command**: `pytest tests/sessions/s0-a.test.py -v`
- **AC → assertion mapping**:
  - Healthz returns 200 → `it("healthz_returns_200_with_ok_status")`
  - Every §1.6 endpoint returns 501 → `it("every_route_manifest_endpoint_returns_501")` (parametrized over the route list)
  - Pydantic contracts exist → `it("backend_schemas_export_all_section_1_1_types")`
  - TS contracts file matches §1.1 verbatim → `it("frontend_contracts_ts_contains_all_section_1_1_type_names")`
  - Celery queues declared → `it("celery_app_declares_all_six_queue_routes")`
  - Config refuses to start without DATABASE_URL → `it("config_exits_when_database_url_missing")`
  - `.env.example` completeness → `it("env_example_lists_every_section_1_12_variable")`
  - Alembic env imports Base → `it("alembic_env_imports_base_declarative_base")`
  - Frontend router has all SPA routes → `it("frontend_router_registers_every_section_1_6_spa_route")` (parsed from router.tsx as text)
  - Docker image builds → `[MANUAL]`
  - ops/* Dockerfiles → `[MANUAL]`
- **Fixtures / test doubles**: FastAPI `TestClient` over `backend.app.main:app`; file-text reads of `frontend/src/types/contracts.ts`, `frontend/src/router.tsx`, `.env.example`. No DB or Redis required — config test monkeypatches env to assert exit behavior.
- **Pre-conditions**: backend dependencies installed (handled by S0-B's `pyproject.toml`). No migrations. No external services.
- **Isolation rule**: passes with only this PR merged. No sibling deps.

##### Checkpoint

- **Observable outcome**: `docker compose up api` boots; `curl localhost:8000/healthz` returns `200 {"status":"ok"}`; `curl -X POST localhost:8000/drawings/hash-check -d '{}'` returns `501` with a `detail` mentioning session `S2-B`.
- **Shippability claim**: this PR is independently mergeable to main even if no other session in the same wave has merged. (S0-A and S0-B are both in Phase 0 wave; S0-A produces no test that depends on S0-B because S0-A's own tests live under `tests/sessions/` which uses only pytest + FastAPI TestClient — S0-B's harness is a separate concern.)

##### Output and handoff

Exports consumed by downstream sessions:
- `backend/app/main.py` → FastAPI `app` instance [LOAD-BEARING] — consumed by every backend test
- `backend/app/config.py` → `Settings` class, `settings` singleton [LOAD-BEARING] — consumed by S1-A, S1-B, S1-C, S1-D, S1-E, all S2-*
- `backend/app/db/base.py` → `Base = declarative_base()` [LOAD-BEARING] — consumed by S1-A models
- `backend/app/db/session.py` → `SessionLocal`, `get_db()` dependency [LOAD-BEARING] — consumed by all backend services
- `backend/app/workers/celery_app.py` → `celery_app` instance, queue names [LOAD-BEARING] — consumed by S1-D, all S2-H..M workers
- `backend/app/schemas/contracts.py` → all Pydantic models per §1.1 [LOAD-BEARING] — consumed by every API/service/worker session
- `backend/app/api/routers/__init__.py` → router registration mechanism — consumed by every S2-* endpoint session
- `frontend/src/types/contracts.ts` → all TS types per §1.1 [LOAD-BEARING] — consumed by S1-F, all S3-*
- `frontend/src/router.tsx` → route registration array — consumed by all S3-* page sessions
- `.env.example` — consumed by S0-B integration harness and every dev/CI setup
- `docker-compose.yml` — consumed by S0-B harness

---

```json
{
  "test": { "cmd": "pytest tests/sessions/s0-a.test.py -v", "file": "tests/sessions/s0-a.test.py" },
  "checkpoint": "`docker compose up api` boots and `GET /healthz` returns 200 {\"status\":\"ok\"}; every other §1.6 endpoint returns 501 with a detail naming its owning session.",
  "manualAcs": [
    { "id": "S0-A-AC-DOCKER-BUILD", "text": "Three Docker images build successfully: backend/Dockerfile, backend/Dockerfile.worker, backend/Dockerfile.ml (CUDA base)." },
    { "id": "S0-A-AC-OPS-DOCKER", "text": "ops/clamav/Dockerfile and ops/oda-sandbox/Dockerfile build successfully; oda-sandbox runs as non-root USER 1000:1000." }
  ],
  "exports": [
    { "kind": "module", "name": "backend/app/main", "shape": "backend/app/main.py" },
    { "kind": "module", "name": "backend/app/config", "shape": "backend/app/config.py" },
    { "kind": "module", "name": "backend/app/db/base", "shape": "backend/app/db/base.py" },
    { "kind": "module", "name": "backend/app/db/session", "shape": "backend/app/db/session.py" },
    { "kind": "module", "name": "backend/app/workers/celery_app", "shape": "backend/app/workers/celery_app.py" },
    { "kind": "module", "name": "backend/app/schemas/contracts", "shape": "backend/app/schemas/contracts.py" },
    { "kind": "module", "name": "backend/app/api/routers", "shape": "backend/app/api/routers/__init__.py" },
    { "kind": "module", "name": "frontend/src/types/contracts", "shape": "frontend/src/types/contracts.ts" },
    { "kind": "module", "name": "frontend/src/router", "shape": "frontend/src/router.tsx" },
    { "kind": "type", "name": "Settings", "shape": "class Settings(BaseSettings): DATABASE_URL: str; REDIS_URL: str; S3_BUCKET_NAME: str; ... (all §1.12 vars)" },
    { "kind": "function", "name": "get_db", "shape": "() -> Generator[Session, None, None]" }
  ]
}
```