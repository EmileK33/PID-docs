# PID Analyzer

Automated P&ID (Piping & Instrumentation Diagram) analysis — symbol detection,
instrument-table extraction, and revision comparison for AutoCAD DWG/PDF
drawings.

This repository is a monorepo built in waves by the HyperSpeed build plan
(`specs/build-plan/`). **This is the Phase-0 scaffold (session S0-A)**: a stable,
importable surface for every downstream session. There is no business logic yet —
almost every endpoint returns `501 Not Implemented` with a `detail` naming the
session that will own its real implementation.

## Layout

```
backend/        FastAPI app (Python 3.11), Celery workers, Alembic migrations
  app/
    main.py         FastAPI `app` + GET /healthz (the only non-501 route)
    config.py       §1.12 env schema via Pydantic BaseSettings (refuses to start
                    when a REQUIRED variable is missing)
    schemas/        §1.1 shared contracts (Pydantic v2)
    api/routers/    _stubs.py (every §1.6 endpoint → 501) + swap-protocol registry
    workers/        celery_app.py (six queues from §1.11)
    db/             declarative Base + session factory
  alembic/        migration environment (S1-A adds versions/)
  Dockerfile          API image (uvicorn)
  Dockerfile.worker   CPU worker image (Celery)
  Dockerfile.ml       GPU ML worker image (CUDA base)
frontend/       React 18 + Vite + TypeScript SPA
  src/
    router.tsx      single declarative route array, lazy-loaded stub pages
    types/contracts.ts  verbatim §1.1 TypeScript contracts
marketing/      Next.js 14 App Router marketing site (separate deployment)
ops/
  clamav/         ClamAV sidecar image
  oda-sandbox/    ODA File Converter sandbox (non-root, no egress, read-only fs)
docker-compose.yml        local dev stack
docker-compose.test.yml   ephemeral CI override
.env.example              every §1.12 variable
```

## Quick start

```bash
cp .env.example .env        # fill in <REQUIRED> values
docker compose up postgres redis api
curl localhost:8000/healthz # -> {"status":"ok"}
```

Every other endpoint returns `501`:

```bash
curl -X POST localhost:8000/drawings/hash-check -d '{}'
# 501 {"detail":"Not implemented — session S2-B owns this endpoint"}
```

### Frontend / marketing dev servers

```bash
cd frontend && npm install && npm run dev      # http://localhost:5173
cd marketing && npm install && npm run dev     # http://localhost:3000
```

## Tests

The scaffold's own acceptance suite (passes in isolation, no sibling session
required):

```bash
pytest tests/sessions/s0-a.test.py -v
```

## Swap protocol (how downstream sessions replace stubs)

* **Backend endpoints** — a session creates its router module (e.g.
  `backend/app/api/routers/auth.py`) and registers it *above* `stubs_router` in
  `backend/app/api/routers/__init__.py`. FastAPI resolves the first matching
  route, so the real router shadows the stub. `main.py` never changes.
* **Frontend pages** — S3-* sessions edit the single `routes` array in
  `frontend/src/router.tsx` at their marked `// SESSION: S3-x` slot (the one
  documented exception to "do not touch entry points").
* **DB models** — S1-A attaches models to `backend/app/db/base.py:Base`; Alembic
  picks them up without editing `alembic/env.py`.

See `specs/build-plan/section5-briefs/` for per-session briefs.
