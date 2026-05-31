# Integration Test Harness

Project-wide integration harness: boots real **Postgres**, **Redis**, and
**MinIO** (S3-compatible) fixtures in Docker, then runs the smoke suite that
proves every backing service is reachable. Every Phase 1+ session's integration
tests build on the fixtures defined here.

## Run it

From the repository root:

```bash
npm run test:integration
```

This invokes [`scripts/test-integration.sh`](../../scripts/test-integration.sh),
which is idempotent: it brings the fixture compose up, polls each service for
readiness, runs `pytest tests/integration`, and tears the containers down on
exit (pass or fail).

## Prerequisites

- **Docker** (with Compose v2) running locally.
- **Node 20+** (provides `npm run test:integration`).
- **Python 3.11+** and **Poetry** (backend test dependencies are installed via
  `poetry install` from `backend/`).

## Ports used

The fixture compose uses a dedicated project name (`pidtest`), distinct
container names, and non-default host ports so it never collides with the dev
compose stack owned by S0-A:

| Service | Container          | Host port        |
| ------- | ------------------ | ---------------- |
| Postgres | `pidtest-postgres` | `55432`          |
| Redis    | `pidtest-redis`    | `56379`          |
| MinIO    | `pidtest-minio`    | `59000` (API), `59001` (console) |

## Fixtures (`conftest.py`)

| Fixture        | Scope    | Description                                                        |
| -------------- | -------- | ------------------------------------------------------------------ |
| `db_engine`    | session  | SQLAlchemy `Engine` bound to the Postgres fixture.                 |
| `db_session`   | function | `Session` wrapped in a transaction that is rolled back per test.   |
| `redis_client` | session  | `redis.Redis` client bound to the Redis fixture.                   |
| `s3_client`    | session  | boto3 S3 client bound to the MinIO fixture.                        |

The harness also sets test-safe values for every environment variable the
application marks "Refuse to start" (spec §1.12) — including `DATABASE_URL`,
`REDIS_URL`, `S3_BUCKET_NAME`, `HMAC_SERVER_SECRET`, Supabase/Stripe/SendGrid
keys — and forces `ENVIRONMENT=development`, so downstream session code can
import and boot under pytest.

## Notes

- `DATABASE_URL` is a driver-agnostic `postgresql://` URI. `fixtures/db.py`
  rewrites it onto the psycopg-v3 driver (`postgresql+psycopg://`) for SQLAlchemy.
- `pgcrypto` (for `gen_random_uuid()`) is enabled at first boot via
  `fixtures/initdb/01-extensions.sql`.
- The smoke suite imports **no** application code, so it stays green regardless
  of merge order with the app-scaffold session (S0-A).
