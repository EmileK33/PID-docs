---

#### S0-B — Integration Harness & Manifests

**Phase 0 | Testing/Hardening | Needs: none**

##### Objective

Establish the project-wide dependency manifests, integration test harness (Postgres/Redis/MinIO fixtures), and CI workflow so every downstream session has a single `npm run test:integration` command that boots a green baseline.

##### Scope

P0 MVP. This is the mandatory Phase 0 integration-harness session. Only smoke tests run here; full E2E coverage is S4-A.

##### Technology constraints

From spec §1.8 (non-negotiable):
- Backend: **Python + FastAPI** (managed via `pyproject.toml` + Poetry; `poetry.lock` committed)
- Frontend: **React + Vite + TypeScript**
- Marketing: **Next.js**
- Database: **PostgreSQL** (test fixture via Docker)
- Queue/Cache/PubSub: **Redis** (test fixture via Docker)
- Object storage: **S3-compatible** — test fixture uses **MinIO** Docker image (S3 API compatible)
- Test runners: **pytest** for Python; root `package.json` provides `npm run test:integration` as the orchestrator (per the brief template's Phase 0 integration-harness rule)
- CI: **GitHub Actions**

MUST NOT use:
- `unittest` (standard lib) as primary runner — pytest only, to match downstream session conventions
- LocalStack for S3 (heavier and slower than MinIO; spec doesn't require AWS-specific S3 APIs in tests)
- SQLite as Postgres substitute — schema uses JSONB, partitioning, RLS, `pgcrypto` (§1.2) which SQLite cannot model

##### Performance targets

None — this session owns no runtime SLA. See downstream sessions (S2-B for canvas <3s, S3-D for <200ms interaction, etc.).

##### Owned files

- `package.json` (root workspace; defines `test:integration` script)
- `backend/pyproject.toml`
- `backend/poetry.lock`
- `frontend/package.json`
- `marketing/package.json`
- `tests/integration/conftest.py`
- `tests/integration/docker-compose.fixtures.yml`
- `tests/integration/fixtures/db.py`
- `tests/integration/fixtures/redis.py`
- `tests/integration/fixtures/s3.py`
- `tests/integration/smoke/test_smoke.py`
- `tests/integration/README.md`
- `scripts/test-integration.sh`
- `.github/workflows/integration.yml`

##### Read-only imports

None. This session runs before any source code exists (S0-A is a sibling that owns app scaffolding; this session must NOT import from `backend/app/*` or `frontend/src/*` because S0-B and S0-A may merge in either order).

The smoke test verifies infrastructure only (DB reachable, Redis reachable, MinIO reachable) — it does NOT import application code.

##### Do not touch

- Every file owned by S0-A (`backend/app/main.py`, `backend/app/config.py`, `backend/app/db/base.py`, `backend/app/db/session.py`, all `backend/app/api/**`, all `backend/app/workers/**`, all `backend/app/schemas/**`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/Dockerfile*`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, all `frontend/src/**`, `marketing/next.config.js`, `marketing/tsconfig.json`, all `marketing/app/**`, `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, `README.md`, all `ops/**`)
- Any file under `backend/app/`, `frontend/src/`, `marketing/app/` — even if it would simplify the smoke test
- Any future session's files

##### Architecture context

From spec §1.8 (verbatim):

> | **API Server** | FastAPI (Python) | Unifies language with ML worker codebase, eliminating cross-service interface surface; Python-first ML ecosystem |
> | **Async Workers** | Celery on Redis broker | Durable persistent queue (NFR-7); Redis already required for cache + SSE; Celery retry/timeout/priority support; changing broker requires worker rewrite |
> | **Database** | PostgreSQL (RDS/Aurora) | ACID, JSONB for bbox payloads, RLS, mature GDPR tooling, all entities have relational structure; schema migrations via Alembic |
> | **Queue / Cache / SSE pub-sub** | Redis (ElastiCache) | Three-in-one: Celery broker, subscription feature flag cache, SSE pub/sub for drawing status push; single operational dependency |
> | **Object Storage** | AWS S3-compatible | Pre-signed URL pattern, IAM role scoping, SSE encryption, lifecycle policies; client-direct upload pattern avoids API byte-proxy |

From spec §1.12 (env vars the harness must provide to tests):

> | `DATABASE_URL` | string | PostgreSQL connection URI | None | Refuse to start | Refuse to start |
> | `REDIS_URL` | string | Redis connection URI | None | Refuse to start | Refuse to start |
> | `S3_BUCKET_NAME` | string | Any non-empty string | None | Refuse to start | Refuse to start |
> | `S3_REGION` | string | AWS region code | None | Refuse to start | Refuse to start |
> | `HMAC_SERVER_SECRET` | string | Any non-empty high-entropy string | None | Refuse to start | Refuse to start |
> | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_RS256_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `SENDGRID_API_KEY` | Refuse to start |
> | `ENVIRONMENT` | string | `development` \| `staging` \| `production` | `production` | Log warning | Use `production` |

The harness must export test-safe values for every "Refuse to start" variable so downstream sessions' application code can boot under pytest.

##### User stories and acceptance criteria

N/A — this is an infrastructure/harness session. No user stories. Technical ACs only (listed in the checklist below).

##### UX and design specification

N/A — no frontend component. (The `frontend/package.json` and `marketing/package.json` files declared here are manifest-only; their UI is built in S1-F / S3-H.)

##### Critical implementation notes

- **The integration command MUST be `npm run test:integration` at repo root.** Per the brief template's Phase 0 integration-harness rule, this is the project-level integration command that downstream session test plans reference. The root `package.json` must define this script, and it must invoke `scripts/test-integration.sh`.
- **`scripts/test-integration.sh` must be idempotent**: bring up `tests/integration/docker-compose.fixtures.yml`, wait for healthchecks, run `pytest tests/integration`, capture exit code, tear down compose, exit with the captured code. Use `set -euo pipefail`.
- **Fixture compose file is separate from `docker-compose.yml`** (owned by S0-A). Do not modify or reference S0-A's compose file. The fixtures compose must use distinct container names (e.g., `pidtest-postgres`, `pidtest-redis`, `pidtest-minio`) and distinct host ports (e.g., 55432, 56379, 59000) to avoid collision with dev compose.
- **Postgres fixture must enable `pgcrypto`** (required by §1.2 `gen_random_uuid()`). Do this via an init SQL mounted at `/docker-entrypoint-initdb.d/`.
- **MinIO fixture must auto-create the test bucket** named by `S3_BUCKET_NAME` env var at startup (use `minio/mc` sidecar or init container).
- **`conftest.py` must expose session-scoped fixtures** named `db_engine`, `redis_client`, `s3_client`, plus a function-scoped `db_session` that wraps each test in a transaction + rollback (so smoke + future tests do not pollute each other).
- **Every env var listed in §1.12 with "Refuse to start" behavior must have a value set in `conftest.py`'s autouse env fixture** (use fake/test values like `STRIPE_SECRET_KEY=sk_test_FAKE`, `HMAC_SERVER_SECRET=test-secret-do-not-use`). Otherwise downstream session tests cannot import application code.
- **`ENVIRONMENT` must be set to `development`** (not `production`) in test env — production default would enable strict checks that may break tests.
- **CI workflow `.github/workflows/integration.yml` must run `npm run test:integration`** on push/PR. Use `services:` block for Postgres/Redis if it simplifies things, OR invoke the same shell script — but the CI green signal must be the same command developers run locally.
- **`poetry.lock` must be committed.** Floating versions are forbidden in CI.
- **The smoke test must NOT import any code from `backend/app/`, `frontend/src/`, or `marketing/`.** It only verifies the three fixture services respond. This isolates S0-B from S0-A's merge timing.
- **Silent failure to avoid**: forgetting to `await` healthchecks before running tests — pytest will race the fixture startup and produce flaky "connection refused" errors. The shell script must explicitly poll readiness (`pg_isready`, `redis-cli ping`, MinIO `/minio/health/ready`) before invoking pytest.

##### Mocking contract

N/A — this session defines contracts (fixture infrastructure), does not consume them. External services touched: Postgres, Redis, MinIO — all run as local Docker containers, no network calls to real third parties (Stripe, SendGrid, PostHog, Supabase) in this harness.

##### Acceptance criteria checklist

- [ ] Running `npm run test:integration` from repo root with Docker available exits 0 on a clean checkout
- [ ] `npm run test:integration` invokes `scripts/test-integration.sh` which brings up `tests/integration/docker-compose.fixtures.yml`
- [ ] Fixture compose starts Postgres 15+ with `pgcrypto` extension pre-installed
- [ ] Fixture compose starts Redis 7+ reachable on the URL exposed via `REDIS_URL`
- [ ] Fixture compose starts MinIO with bucket named by `S3_BUCKET_NAME` auto-created at boot
- [ ] `scripts/test-integration.sh` polls all three services for readiness before invoking pytest
- [ ] `scripts/test-integration.sh` tears down compose containers regardless of test pass/fail (trap on EXIT)
- [ ] `tests/integration/conftest.py` exports session-scoped `db_engine`, `redis_client`, `s3_client` fixtures
- [ ] `tests/integration/conftest.py` exports a function-scoped `db_session` fixture that rolls back on teardown
- [ ] `tests/integration/conftest.py` sets every §1.12 "Refuse to start" env var to a test-safe value via autouse fixture
- [ ] `tests/integration/conftest.py` sets `ENVIRONMENT=development` (not `production`) in test env
- [ ] `tests/integration/smoke/test_smoke.py` contains an `it`-equivalent `test_postgres_reachable` that runs `SELECT 1` and asserts result
- [ ] `tests/integration/smoke/test_smoke.py` contains `test_redis_reachable` that PINGs and asserts PONG
- [ ] `tests/integration/smoke/test_smoke.py` contains `test_minio_reachable` that lists buckets and asserts the test bucket exists
- [ ] `tests/integration/smoke/test_smoke.py` contains `test_pgcrypto_extension_available` that calls `gen_random_uuid()` successfully
- [ ] `tests/integration/smoke/test_smoke.py` does NOT import from `backend/app/`, `frontend/src/`, or `marketing/`
- [ ] Root `package.json` declares `test:integration` script
- [ ] `backend/pyproject.toml` declares pytest, pytest-asyncio, psycopg/asyncpg, redis, boto3 (or minio) as dev dependencies
- [ ] `backend/poetry.lock` is committed and consistent with `pyproject.toml`
- [ ] `frontend/package.json` and `marketing/package.json` exist as valid manifests (no install errors)
- [ ] `.github/workflows/integration.yml` runs `npm run test:integration` on push and pull_request events
- [ ] `tests/integration/README.md` documents the local run command, prerequisites (Docker), and ports used

##### Independent Test

- **Test file path** (TDD — written first, must fail before implementation): `tests/integration/smoke/test_smoke.py`
- **Exact CI command** (Phase 0 integration-harness — project-level command per template rule): `npm run test:integration`
- **AC → assertion mapping**:
  - `npm run test:integration` exits 0 → entire pytest run green (covered by all `test_smoke.py` tests)
  - Postgres reachable + pgcrypto → `test_postgres_reachable`, `test_pgcrypto_extension_available`
  - Redis reachable → `test_redis_reachable`
  - MinIO reachable + bucket created → `test_minio_reachable`
  - Fixture isolation (no app imports) → `test_smoke_does_not_import_app` (uses `sys.modules` introspection)
  - Env vars set → `test_required_env_vars_present` (asserts each §1.12 "Refuse to start" var has a value)
  - Shell script teardown → covered by CI workflow run (script must exit 0 with no leaked containers; verifiable via `docker ps` post-run in CI step)
  - Manifest validity → `test_root_package_json_has_test_integration_script` (reads file, asserts script key exists)
- **Fixtures / test doubles**: real Postgres/Redis/MinIO containers via the fixture compose. No mocks — this harness validates real connectivity.
- **Pre-conditions**: Docker daemon running; ports 55432, 56379, 59000 free; Node 20+ and Python 3.11+ available.
- **Isolation rule**: Passes when S0-B's PR is the only one merged. Does NOT depend on S0-A (smoke test does not import app code).

##### Checkpoint

- **Observable outcome**: running `npm run test:integration` from a clean repo checkout on a machine with Docker boots Postgres/Redis/MinIO containers, runs the smoke suite, prints green pytest output, and tears down containers — verifiable without reading the diff.
- **Shippability claim**: this PR is independently mergeable to main even if no other session in the same wave has merged.

##### Output and handoff

Downstream consumers (every Phase 1+ session):
- `npm run test:integration` script in root `package.json` [LOAD-BEARING] — every session's CI command references this
- `tests/integration/conftest.py` fixtures: `db_engine`, `db_session`, `redis_client`, `s3_client` [LOAD-BEARING] — every Phase 1/2 backend test imports these
- `tests/integration/docker-compose.fixtures.yml` — backing services for all integration tests
- `scripts/test-integration.sh` — invocation contract
- `backend/pyproject.toml` Poetry dep manifest — all backend sessions add deps here
- Env var defaults in `conftest.py` — every test importing application code relies on these being set

---

```json
{
  "test": { "cmd": "npm run test:integration", "file": "tests/integration/smoke/test_smoke.py" },
  "checkpoint": "Running `npm run test:integration` from a clean checkout boots Postgres/Redis/MinIO containers, the smoke suite passes green, and containers are torn down cleanly.",
  "manualAcs": [],
  "exports": [
    { "kind": "module", "name": "tests/integration/conftest", "shape": "tests/integration/conftest.py" },
    { "kind": "module", "name": "tests/integration/fixtures/db", "shape": "tests/integration/fixtures/db.py" },
    { "kind": "module", "name": "tests/integration/fixtures/redis", "shape": "tests/integration/fixtures/redis.py" },
    { "kind": "module", "name": "tests/integration/fixtures/s3", "shape": "tests/integration/fixtures/s3.py" },
    { "kind": "module", "name": "scripts/test-integration", "shape": "scripts/test-integration.sh" },
    { "kind": "module", "name": "tests/integration/docker-compose.fixtures", "shape": "tests/integration/docker-compose.fixtures.yml" },
    { "kind": "function", "name": "db_engine", "shape": "() => SQLAlchemy Engine (pytest session-scoped fixture)" },
    { "kind": "function", "name": "db_session", "shape": "() => SQLAlchemy Session (pytest function-scoped fixture, transactional rollback)" },
    { "kind": "function", "name": "redis_client", "shape": "() => redis.Redis (pytest session-scoped fixture)" },
    { "kind": "function", "name": "s3_client", "shape": "() => boto3.S3Client (pytest session-scoped fixture, MinIO-backed)" }
  ]
}
```