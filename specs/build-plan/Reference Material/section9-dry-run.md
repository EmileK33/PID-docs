# Dry-Run Verification Procedure

---

## Step 1 — Phase 0 Export Manifest

Run S0-A and S0-B independently and capture every named export. Expected manifest derived from Phase 1 import tables:

| # | File (Phase 0 owner) | Named Export | Kind |
|---|----------------------|--------------|------|
| 1 | `backend/app/db/base.py` (S0-A) | `Base` | SQLAlchemy declarative base class |
| 2 | `backend/app/db/session.py` (S0-A) | `engine` | SQLAlchemy engine |
| 3 | `backend/app/db/session.py` (S0-A) | `SessionLocal` | Session factory |
| 4 | `backend/app/db/session.py` (S0-A) | `get_db` | Dependency callable (sync **or** async — see Step 4) |
| 5 | `backend/app/config.py` (S0-A) | `settings` | Pydantic Settings object |
| 6 | `backend/alembic/env.py` (S0-A) | *(wired import)* | Imports `Base.metadata` — no re-export needed |
| 7 | `backend/app/schemas/contracts.py` (S0-A) | `EntityClassId` | Literal type |
| 8 | `backend/app/schemas/contracts.py` (S0-A) | `DrawingProcessingState` | Enum/Literal |
| 9 | `backend/app/schemas/contracts.py` (S0-A) | `BillingState` | Enum/Literal |
| 10 | `backend/app/schemas/contracts.py` (S0-A) | `TierId` | Enum/Literal |
| 11 | `backend/app/schemas/contracts.py` (S0-A) | `UserRole` | Literal `'user' \| 'team_member' \| 'team_admin'` |
| 12 | `backend/app/schemas/contracts.py` (S0-A) | `SymbolSource` | Enum/Literal |
| 13 | `backend/app/schemas/contracts.py` (S0-A) | `CorrectionType` | Enum/Literal |
| 14 | `backend/app/schemas/contracts.py` (S0-A) | `ExportFormat` | Enum/Literal |
| 15 | `backend/app/schemas/contracts.py` (S0-A) | `ExportStatus` | Enum/Literal |
| 16 | `backend/app/schemas/contracts.py` (S0-A) | `HashCheckRequest` | Pydantic model |
| 17 | `backend/app/schemas/contracts.py` (S0-A) | `HashCheckResponse` | Pydantic model |
| 18 | `backend/app/schemas/contracts.py` (S0-A) | `DrawingStatusSSEEvent` | Pydantic model |
| 19 | `backend/app/workers/celery_app.py` (S0-A) | `celery_app` | Celery application instance |
| 20 | `frontend/src/types/contracts.ts` (S0-A) | `DrawingProcessingState` | TS type/enum |
| 21 | `frontend/src/types/contracts.ts` (S0-A) | `DrawingStatusSSEEvent` | TS type |
| 22 | `frontend/src/types/contracts.ts` (S0-A) | `HashCheckRequest` | TS type |
| 23 | `frontend/src/types/contracts.ts` (S0-A) | `HashCheckResponse` | TS type |
| 24 | `frontend/src/types/contracts.ts` (S0-A) | `SymbolsPageResponse` | TS type |
| 25 | `frontend/src/types/contracts.ts` (S0-A) | `BillingState` | TS type |
| 26 | `frontend/src/types/contracts.ts` (S0-A) | `TierId` | TS type |
| 27 | `frontend/src/types/contracts.ts` (S0-A) | `UserRole` | TS type |
| 28 | `frontend/src/types/contracts.ts` (S0-A) | `SymbolSource` | TS type |
| 29 | `frontend/src/types/contracts.ts` (S0-A) | `CorrectionType` | TS type |
| 30 | `frontend/src/types/contracts.ts` (S0-A) | `ExportFormat` | TS type |
| 31 | `frontend/src/types/contracts.ts` (S0-A) | `ExportStatus` | TS type |
| 32 | `frontend/src/types/contracts.ts` (S0-A) | `EntityClassId` | TS type |
| 33 | `frontend/src/types/contracts.ts` (S0-A) | `SymbolRecord` | TS type |
| 34 | `frontend/src/types/contracts.ts` (S0-A) | `CorrectionRecord` | TS type |
| 35 | `frontend/src/types/contracts.ts` (S0-A) | `BoundingBox` | TS type |
| 36 | `frontend/src/router.tsx` (S0-A) | *(file exists, route names readable)* | TSX module |
| 37 | `tests/integration/conftest.py` (S0-B) | `db_session` | pytest fixture |
| 38 | `tests/integration/conftest.py` (S0-B) | `clean_db` | pytest fixture |
| 39 | `tests/integration/conftest.py` (S0-B) | `db` | pytest fixture |
| 40 | `tests/integration/conftest.py` (S0-B) | `redis` | pytest fixture |
| 41 | `tests/integration/conftest.py` (S0-B) | `app_client` | pytest fixture |
| 42 | `tests/integration/conftest.py` (S0-B) | `redis_client` | pytest fixture |
| 43 | `tests/integration/conftest.py` (S0-B) | *(event loop fixture)* | pytest-asyncio fixture |
| 44 | `tests/integration/fixtures/db.py` (S0-B) | `migrate_to_head` | callable helper |
| 45 | `tests/integration/fixtures/db.py` (S0-B) | `drop_all` | callable helper |
| 46 | `tests/integration/fixtures/db.py` (S0-B) | *(DB fixture re-export or standalone)* | pytest fixture |
| 47 | `tests/integration/fixtures/redis.py` (S0-B) | `redis_client` | pytest fixture (ephemeral container) |
| 48 | `tests/integration/fixtures/s3.py` (S0-B) | *(S3 fixture)* | pytest fixture |

---

## Step 2 — Consolidated Import Table

| Session | File Path | Export Name | Expected Type/Shape |
|---------|-----------|-------------|---------------------|
| S1-A | `backend/app/db/base.py` | `Base` | SQLAlchemy `DeclarativeBase` (or `declarative_base()` result) |
| S1-A | `backend/app/db/session.py` | `engine` | `sqlalchemy.Engine` |
| S1-A | `backend/app/db/session.py` | `SessionLocal` | `sessionmaker` instance |
| S1-A | `backend/app/db/session.py` | `get_db` | Generator/dependency yielding a Session |
| S1-A | `backend/app/config.py` | `settings` | Object with `.DATABASE_URL`, `.ENVIRONMENT` |
| S1-A | `backend/alembic/env.py` | *(wired)* | File imports `Base.metadata`; no named export needed |
| S1-A | `backend/app/schemas/contracts.py` | `EntityClassId` | Literal or StrEnum |
| S1-A | `backend/app/schemas/contracts.py` | `DrawingProcessingState` | Enum/Literal |
| S1-A | `backend/app/schemas/contracts.py` | `BillingState` | Enum/Literal |
| S1-A | `backend/app/schemas/contracts.py` | `TierId` | Enum/Literal |
| S1-A | `backend/app/schemas/contracts.py` | `UserRole` | Literal `'user' \| 'team_member' \| 'team_admin'` |
| S1-A | `backend/app/schemas/contracts.py` | `SymbolSource` | Enum/Literal |
| S1-A | `backend/app/schemas/contracts.py` | `CorrectionType` | Enum/Literal |
| S1-A | `backend/app/schemas/contracts.py` | `ExportFormat` | Enum/Literal |
| S1-A | `backend/app/schemas/contracts.py` | `ExportStatus` | Enum/Literal |
| S1-A | `tests/integration/conftest.py` | `db_session` | pytest fixture → DB session |
| S1-A | `tests/integration/conftest.py` | `clean_db` | pytest fixture → truncation helper |
| S1-A | `tests/integration/fixtures/db.py` | `migrate_to_head` | `() -> None` callable |
| S1-A | `tests/integration/fixtures/db.py` | `drop_all` | `() -> None` callable |
| S1-B | `backend/app/config.py` | `settings` | Object with `.SUPABASE_URL`, `.SUPABASE_SERVICE_ROLE_KEY`, `.JWT_RS256_PUBLIC_KEY`, `.REDIS_URL`, `.ENVIRONMENT` |
| S1-B | `backend/app/schemas/contracts.py` | `UserRole` | Literal `'user' \| 'team_member' \| 'team_admin'` |
| S1-B | `backend/app/db/session.py` | `get_db` | **Async** generator/dependency (FastAPI async-compatible) |
| S1-B | `tests/integration/conftest.py` | `db` | pytest fixture |
| S1-B | `tests/integration/conftest.py` | `redis` | pytest fixture |
| S1-B | `tests/integration/conftest.py` | `app_client` | pytest fixture (HTTPX/Starlette test client) |
| S1-B | `tests/integration/fixtures/redis.py` | `redis_client` | pytest fixture → Redis client |
| S1-C | `backend/app/config.py` | `settings` | Object with `.S3_BUCKET_NAME`, `.S3_REGION`, `.AWS_ACCESS_KEY_ID`, `.AWS_SECRET_ACCESS_KEY`, `.PRESIGNED_URL_EXPIRY_SECONDS`, `.MAX_UPLOAD_SIZE_BYTES` |
| S1-C | `backend/app/db/session.py` | `get_db` | DB session factory/dependency |
| S1-C | `backend/app/schemas/contracts.py` | `HashCheckRequest` | Pydantic `BaseModel` |
| S1-C | `backend/app/schemas/contracts.py` | `HashCheckResponse` | Pydantic `BaseModel` |
| S1-C | `tests/integration/conftest.py` | *(general fixtures)* | pytest fixtures |
| S1-C | `tests/integration/fixtures/db.py` | *(DB fixture)* | pytest fixture |
| S1-C | `tests/integration/fixtures/s3.py` | *(S3 fixture)* | pytest fixture (moto/localstack bucket) |
| S1-D | `backend/app/config.py` | `settings` | Object with `.REDIS_URL`, `.CELERY_BROKER_URL`, `.ENVIRONMENT` |
| S1-D | `backend/app/workers/celery_app.py` | `celery_app` | `celery.Celery` instance |
| S1-D | `backend/app/schemas/contracts.py` | `DrawingStatusSSEEvent` | Pydantic model |
| S1-D | `backend/app/schemas/contracts.py` | `DrawingProcessingState` | Enum/Literal |
| S1-D | `backend/app/schemas/contracts.py` | `TierId` | Enum/Literal |
| S1-D | `backend/app/schemas/contracts.py` | `BillingState` | Enum/Literal |
| S1-D | `tests/integration/conftest.py` | `redis_client` | pytest fixture |
| S1-D | `tests/integration/conftest.py` | *(event loop fixture)* | pytest-asyncio event loop |
| S1-D | `tests/integration/fixtures/redis.py` | *(ephemeral Redis fixture)* | pytest fixture (container) |
| S1-E | `backend/app/config.py` | `settings` | Object with `.POSTHOG_API_KEY`, `.POSTHOG_HOST`, `.ENVIRONMENT` |
| S1-E | `backend/app/schemas/contracts.py` | `TierId` | Enum/Literal |
| S1-E | `backend/app/schemas/contracts.py` | `ExportFormat` | Enum/Literal |
| S1-E | `tests/integration/conftest.py` | *(db, redis container fixtures)* | pytest fixtures |
| S1-F | `frontend/src/types/contracts.ts` | `DrawingProcessingState` | TS exported type/enum |
| S1-F | `frontend/src/types/contracts.ts` | `DrawingStatusSSEEvent` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `HashCheckRequest` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `HashCheckResponse` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `SymbolsPageResponse` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `BillingState` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `TierId` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `UserRole` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `SymbolSource` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `CorrectionType` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `ExportFormat` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `ExportStatus` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `EntityClassId` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `SymbolRecord` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `CorrectionRecord` | TS exported type |
| S1-F | `frontend/src/types/contracts.ts` | `BoundingBox` | TS exported type |
| S1-F | `frontend/src/router.tsx` | *(file readable, route names accessible)* | TSX module (read-only) |

---

## Step 3 — Mismatch Report

Two structural mismatches are detectable from the briefs alone without inspecting actual output:

| Session | File | Expected Export | Issue | Fix |
|---------|------|-----------------|-------|-----|
| S1-A vs S1-B | `backend/app/db/session.py` | `get_db` | **Sync/async conflict.** S1-A describes `get_db` with no async qualifier (implies sync generator, standard for SQLAlchemy sync sessions). S1-B explicitly requires "async session factory `get_db()`". Both sessions import the same name from the same file — it cannot be both. If S0-A scaffolds it as sync, S1-B's async middleware will break; if async, S1-A's sync ORM usage will break. | S0-A brief must declare definitively whether `get_db` is `async def get_db()` (AsyncSession) or `def get_db()` (Session). One of S1-A or S1-B must be updated to match. Recommended resolution: make `get_db` async (AsyncSession) throughout, and update S1-A's import description to note async usage. |
| S1-D vs S1-B | `tests/integration/conftest.py` | `redis_client` | **Fixture name duplication across conftest and fixtures/redis.py.** S1-B imports `redis_client` from `fixtures/redis.py`. S1-D imports `redis_client` from `conftest.py`. S0-B must ensure `conftest.py` either defines `redis_client` itself or imports and re-exports it from `fixtures/redis.py` so both import paths resolve to the same fixture without collision. If conftest.py and fixtures/redis.py both define `redis_client` independently, pytest may see duplicate fixture definitions. | S0-B brief must clarify: `fixtures/redis.py` owns the `redis_client` fixture definition; `conftest.py` imports it via `from tests.integration.fixtures.redis import redis_client` (or uses `pytest_plugins`). Both S1-B and S1-D then reference the same underlying fixture regardless of which file they cite. Update S0-B's conftest template to make this explicit. |

---

## Step 4 — Ambiguous Items Requiring Step 1 Output Inspection

| # | Session | File | What to verify |
|---|---------|------|----------------|
| 1 | S1-A, S1-B, S1-C, S1-D | `backend/app/config.py` | Confirm `settings` is a single Pydantic `BaseSettings` object and that **all** required fields across all sessions are present in one class: `DATABASE_URL`, `ENVIRONMENT`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_RS256_PUBLIC_KEY`, `REDIS_URL`, `CELERY_BROKER_URL`, `S3_BUCKET_NAME`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `PRESIGNED_URL_EXPIRY_SECONDS`, `MAX_UPLOAD_SIZE_BYTES`, `POSTHOG_API_KEY`, `POSTHOG_HOST`. Verify no field is missing or misspelled. |
| 2 | S1-A, S1-B, S1-D | `backend/app/schemas/contracts.py` | Confirm `UserRole` is exactly `Literal['user', 'team_member', 'team_admin']` (or a StrEnum with those three values). The brief text is consistent but the actual Python representation (Literal vs StrEnum vs plain str) must be verified — S1-B uses it for JWT claim comparison, which is sensitive to type. |
| 3 | S1-A | `backend/app/schemas/contracts.py` | Confirm `EntityClassId` is a `Literal[...]` (fixed set of string values) vs a plain `str` alias. S1-A uses it for seed validation, so the literal values must be enumerated in the actual file. |
| 4 | S1-C, S1-D | `backend/app/schemas/contracts.py` | Confirm `HashCheckRequest` and `HashCheckResponse` are `pydantic.BaseModel` subclasses with fields (not bare TypedDicts or dataclasses), since S1-C uses them for request/response parsing. |
| 5 | S1-D | `backend/app/workers/celery_app.py` | Confirm `celery_app` is a fully-configured `Celery` instance (broker set from `settings.CELERY_BROKER_URL`), not a bare `Celery()` stub. S1-D adds queue routing on top of it and must not re-set the broker. |
| 6 | S0-B | `tests/integration/conftest.py` | Confirm all of these fixture names are present and individually importable: `db_session`, `clean_db`, `db`, `redis`, `app_client`, `redis_client`, and an event loop fixture. Verify `db` and `db_session` are distinct fixtures (S1-A uses `db_session`; S1-B uses `db`) and do not shadow each other. |
| 7 | S0-B | `tests/integration/fixtures/db.py` | Confirm the file exports both a **callable helper** `migrate_to_head()` (called directly in test setup, not as a fixture) and `drop_all()`, as well as a **pytest fixture** (the fixture name is unspecified in the brief — verify what name it registers under, since S1-C references "DB fixture" from this file). |
| 8 | S0-B | `tests/integration/fixtures/s3.py` | Confirm the S3 fixture name (unspecified in all briefs — S1-C says only "moto/localstack-backed S3 fixture"). Verify the registered pytest name so S1-C can reference it correctly. |
| 9 | S1-F | `frontend/src/types/contracts.ts` | Confirm the `etc.` types referenced by S1-F ("etc." in the brief) are fully enumerated. Specifically verify that `SymbolRecord`, `CorrectionRecord`, and `BoundingBox` are named exports (not just internal types), and identify any additional types implied by the "etc." that S1-F may depend on. |
| 10 | S1-F | `frontend/src/router.tsx` | Confirm S0-A's owned-files list includes `frontend/src/router.tsx`. This file is not mentioned in any Phase 0 export, only in S1-F's read-only import. If S0-A does not own it, it will not exist when S1-F runs. |

---

**The dry run cannot issue a full PASS until:**
1. The sync/async conflict on `get_db` (Step 3, row 1) is resolved in the relevant briefs.
2. The `redis_client` fixture ownership path (Step 3, row 2) is made unambiguous in S0-B.
3. All ten ambiguous items in Step 4 are confirmed against actual S0 output before any Phase 1 session begins.