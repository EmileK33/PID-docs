#### S2-L — GDPR Erasure Worker

**Phase 2 | Real-time/Queue | Needs: S1-A, S1-C, S1-D**

---

##### Objective

Implement the asynchronous GDPR erasure Celery worker that, 30 days after account-deletion initiation, atomically computes and persists an `anonymous_id` for the user and then purges all PII fields from the `user` table and related records, with full idempotency for safe retries.

---

##### Scope

**P0 MVP.** All work in this session is P0. No P1 stubs required.

P0 work:
- `gdpr_erasure` Celery queue periodic scanner task (`tasks.py`)
- `anonymizer.py` — HMAC-SHA256 `anonymous_id` derivation, idempotent PII purge for `user` table, `audit_log`, `ml_training_consent`
- `__init__.py` — module exports
- `tests/integration/test_gdpr_worker.py` — TDD test covering all ACs

---

##### Technology constraints

From §1.8 (verbatim relevant selections):

| Layer | Selected Technology | Architecturally Irreversible Because |
|---|---|---|
| **API Server** | FastAPI (Python) | Unifies language with ML worker codebase, eliminating cross-service interface surface; Python-first ML ecosystem |
| **Async Workers** | Celery on Redis broker | Durable persistent queue (NFR-7); Redis already required for cache + SSE; Celery retry/timeout/priority support; changing broker requires worker rewrite |
| **Database** | PostgreSQL (RDS/Aurora) | ACID, JSONB for bbox payloads, RLS, mature GDPR tooling, all entities have relational structure; schema migrations via Alembic |
| **Queue / Cache / SSE pub-sub** | Redis (ElastiCache) | Three-in-one: Celery broker, subscription feature flag cache, SSE pub/sub for drawing status push; single operational dependency |

**Must NOT use:**
- In-memory queues or threading-based scheduling — the spec mandates: "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts." The same constraint applies to the GDPR queue.
- Any HMAC algorithm other than HMAC-SHA256 — `anonymous_id` contract is HMAC-SHA256 and is load-bearing for downstream retries.
- `hashlib.md5` or `hashlib.sha1` — security constraint.

**Required libraries** (from `backend/pyproject.toml`, managed by S0-B):
- `celery[redis]` — task worker + beat scheduler
- `sqlalchemy` — ORM; models from S1-A
- `psycopg2-binary` — PostgreSQL driver
- `python-jose` or `hmac` (stdlib) — HMAC-SHA256 for `anonymous_id` (stdlib `hmac` + `hashlib` preferred; no additional dep required)

---

##### Performance targets

None — see downstream sessions. The GDPR erasure pipeline is async and 30-days-delayed by design; no latency SLA is specified. Erasure jobs must be idempotent and survivable across broker/worker restarts (NFR-7).

---

##### Owned files

- `backend/app/workers/gdpr/__init__.py`
- `backend/app/workers/gdpr/tasks.py`
- `backend/app/workers/gdpr/anonymizer.py`
- `tests/integration/test_gdpr_worker.py`

---

##### Read-only imports

| Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` (Celery application instance) |
| S0-A | `backend/app/config.py` | `settings` (env var access, including `HMAC_SERVER_SECRET`, `DATABASE_URL`, `REDIS_URL`) |
| S1-A | `backend/app/db/models/user.py` | `User` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/audit_log.py` | `AuditLog` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/ml_training_consent.py` | `MLTrainingConsent` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/user_correction.py` | `UserCorrection` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` (SQLAlchemy model; for orphaned drawing ownership logic if needed) |
| S1-A | `backend/app/db/session.py` | `get_db_session` (session factory / context manager) |
| S1-C | `backend/app/storage/s3_client.py` | `S3Client` (for future S3 deletion stubs — import only, not called in P0) |
| S1-D | `backend/app/workers/queues.py` | `GDPR_ERASURE_QUEUE` (queue routing constant) |
| S1-D | `backend/app/workers/base.py` | `BaseTask` (base Celery task class with retry policy) |

---

##### Do not touch

- `backend/app/main.py` — entry point, pre-stubbed by S0-A
- `backend/app/api/routers/__init__.py` — router registry, pre-stubbed by S0-A
- `backend/app/api/routers/_stubs.py` — placeholder endpoints, pre-stubbed by S0-A
- `backend/app/workers/celery_app.py` — owned by S0-A
- `backend/app/workers/queues.py` — owned by S1-D
- `backend/app/workers/base.py` — owned by S1-D
- `backend/app/db/session.py` — owned by S1-A
- `backend/app/db/models/*.py` — all model files owned by S1-A
- `backend/app/services/gdpr_init_service.py` — owned by S2-F (enqueues the job this worker consumes; do not modify)
- `backend/app/config.py` — owned by S0-A
- `backend/app/storage/s3_client.py` — owned by S1-C
- Any file not listed under "Owned files"

---

##### Architecture context

From §1.11 (verbatim):

> **Celery Job Queue Names**
>
> | Queue | Workers | Job Types |
> |---|---|---|
> | `gdpr_erasure` | GDPR Worker (CPU, scheduled) | PII purge, anonymization |

From §1.2 Database Schema (verbatim, `user` table relevant columns):

```sql
CREATE TABLE "user" (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email                  VARCHAR NOT NULL,
  display_name           VARCHAR NOT NULL,
  password_hash          VARCHAR,
  email_verified         BOOLEAN NOT NULL DEFAULT FALSE,
  team_id                UUID REFERENCES team(id),
  role                   VARCHAR NOT NULL CHECK (role IN ('user','team_member','team_admin')),
  deleted_at             TIMESTAMPTZ,
  anonymous_id           VARCHAR,                     -- HMAC-SHA256(user_id||server_secret), set on first erasure run
  token_invalidated_at   TIMESTAMPTZ,
  CONSTRAINT user_email_unique UNIQUE (email)
);
```

From §1.2 Database Schema (verbatim, `audit_log` table relevant columns):

```sql
CREATE TABLE audit_log (
  id            UUID NOT NULL DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES "user"(id),
  ...
) PARTITION BY RANGE (occurred_at);
```

Note: `audit_log.user_id` is nullable — can be nulled during erasure.

From §1.2 Database Schema (verbatim, `ml_training_consent`):

```sql
CREATE TABLE ml_training_consent (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES "user"(id),
  team_id     UUID REFERENCES team(id),
  opted_in    BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT consent_user_or_team CHECK (
    (user_id IS NOT NULL AND team_id IS NULL) OR
    (user_id IS NULL AND team_id IS NOT NULL)
  )
);
```

Note: `ml_training_consent.user_id` is nullable per the CHECK constraint — rows where `team_id IS NOT NULL` already have `user_id IS NULL`. For user-owned rows, delete the record on erasure (user_id cannot be nulled without violating the CHECK constraint; deletion is the correct approach).

From §1.4 Critical Ordering Rules (verbatim):

> **Rule 11: GDPR erasure: anonymous_id written before any records updated.** "On first erasure job execution, the computed anonymous ID is written to `USER.anonymous_id` before any records are updated. All subsequent erasure job retries... read `USER.anonymous_id` directly."

From §1.12 Environment Variable Schema (verbatim):

| Variable | Type | Valid Values | Default if Absent | Startup Behavior if Invalid | Startup Behavior if Absent |
|---|---|---|---|---|---|
| `HMAC_SERVER_SECRET` | string | Any non-empty high-entropy string | None | Refuse to start | Refuse to start (used for anonymous_id derivation) |
| `DATABASE_URL` | string | PostgreSQL connection URI | None | Refuse to start | Refuse to start |
| `REDIS_URL` | string | Redis connection URI | None | Refuse to start | Refuse to start |

From §1.13 Feature Scope (P0 verbatim):

> - US-005: Account deletion and GDPR erasure pipeline (30-day async, anonymous_id persistence)

---

##### User stories and acceptance criteria

**US-005: Account Deletion and GDPR Erasure Pipeline**

*As a user who has requested account deletion, I want my personal data to be permanently erased 30 days after I initiate deletion, so that my right to erasure under GDPR is honored.*

**AC-1 (Happy Path — First Erasure Run):**
Given a user whose `deleted_at` is set and is at least 30 days in the past, and whose `anonymous_id` is NULL,
When the GDPR erasure worker processes this user,
Then:
- `anonymous_id` is computed as `HMAC-SHA256(user_id || HMAC_SERVER_SECRET)` (hex digest)
- `anonymous_id` is written to `USER.anonymous_id` in a separate committed transaction before any other records are updated
- After the anonymous_id commit, all PII fields are cleared: `email` is overwritten with a non-PII placeholder (e.g., `erased_{anonymous_id[:16]}@erased.invalid`), `display_name` is overwritten with `Deleted User`, `password_hash` is set to NULL
- `audit_log` rows referencing this `user_id` have their `user_id` column set to NULL
- `ml_training_consent` rows with this `user_id` are deleted
- The user record remains (not hard-deleted) with `deleted_at` preserved and `anonymous_id` populated

**AC-2 (Retry Idempotency — anonymous_id Already Set):**
Given a user whose `anonymous_id` is already set (prior partial run or retry),
When the GDPR erasure worker processes this user again,
Then:
- The worker reads `USER.anonymous_id` from the database directly — it does NOT recompute the HMAC
- The PII purge continues from wherever it left off (subsequent steps are safe to re-execute)
- The final state is identical to AC-1

**AC-3 (Only 30+ day deleted users are processed):**
Given a user whose `deleted_at` is set but is fewer than 30 days ago,
When the scheduled erasure scanner runs,
Then the user is NOT selected for erasure in this run.

**AC-4 (User not yet deleted — no deleted_at):**
Given a user whose `deleted_at` is NULL,
When the scheduled erasure scanner runs,
Then this user is excluded from erasure entirely.

**AC-5 (Already fully erased — idempotent):**
Given a user whose `anonymous_id` is already set AND whose `email` already matches the erased placeholder pattern,
When the GDPR erasure worker processes this user,
Then no error is raised, the `anonymous_id` is unchanged, and all PII-cleared fields remain cleared (no-op).

**AC-6 (HMAC determinism):**
Given the same `user_id` and the same `HMAC_SERVER_SECRET`,
When `compute_anonymous_id(user_id)` is called any number of times,
Then it always returns the identical hex-digest string.

**AC-7 (Worker registered on correct queue):**
The erasure task must be registered on the `gdpr_erasure` Celery queue and routed there by the queue configuration from S1-D.

**AC-8 (Startup refuses with missing HMAC_SERVER_SECRET):**
Given `HMAC_SERVER_SECRET` is absent or empty,
When the worker module is imported or the Celery app starts,
Then an `EnvironmentError` (or equivalent startup-time validation error) is raised and the worker refuses to start.

**AC-9 (anonymous_id write is a separate committed transaction before PII purge):**
Given that the system crashes (simulated by exception injection) immediately after the `anonymous_id` commit but before the PII purge,
When the erasure job is retried,
Then AC-2 applies: the worker reads the persisted `anonymous_id` and completes the PII purge without recomputing the HMAC or erroring.

---

##### UX and design specification

N/A — no frontend component. This is a backend Celery worker with no user-facing interface. Status updates are not emitted via SSE for this worker (erasure is background-only; the user's session is already invalidated before the 30-day window closes).

---

##### Critical implementation notes

- **Ordering rule (verbatim from §1.4, Rule 11):** "On first erasure job execution, the computed anonymous ID is written to `USER.anonymous_id` before any records are updated. All subsequent erasure job retries... read `USER.anonymous_id` directly." This means two separate database transactions: (1) write `anonymous_id`; commit; (2) purge PII; commit. Never combine both into a single transaction — if the combined transaction rolls back, the anonymous_id is lost and the HMAC must be recomputed, violating the idempotency contract.

- **HMAC computation:** `anonymous_id = hmac.new(HMAC_SERVER_SECRET.encode(), user_id.encode(), digestmod='sha256').hexdigest()`. Use Python stdlib `hmac` and `hashlib`. Do NOT use any other algorithm.

- **Retry reads anonymous_id from DB, never recomputes:** Before calling `compute_anonymous_id()`, always check `user.anonymous_id IS NOT NULL`. If set, use the stored value. This is the idempotency guarantee.

- **ml_training_consent rows for the erased user:** DELETE (not null user_id). The CHECK constraint `(user_id IS NOT NULL AND team_id IS NULL) OR (user_id IS NULL AND team_id IS NOT NULL)` prevents nulling user_id on a user-owned row. Deletion is the only valid approach.

- **user_correction.user_id is NOT NULL:** Do NOT attempt to null `user_correction.user_id` — the column has a NOT NULL constraint and a FK to `user`. The user record itself is anonymized, so corrections reference an anonymized user. This is GDPR-compliant: the UUID is not PII once the user row is anonymized.

- **audit_log.user_id is nullable:** Set to NULL in all partitions (use a single UPDATE across the partitioned table; PostgreSQL routes correctly to partitions).

- **30-day window — use a Celery beat periodic task:** The scheduled worker scans for `deleted_at IS NOT NULL AND deleted_at < NOW() - INTERVAL '30 days'` and dispatches `erase_user_pii.apply_async(args=[user_id])` for each qualifying user. This is more robust than a 30-day Celery ETA countdown (which does not survive broker restarts for long-lived delays). The beat schedule should run at least once per hour.

- **ML job must be enqueued via persistent queue (verbatim §1.4 Rule 14):** "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts." Same requirement applies to GDPR tasks.

- **free_tier_counter race condition pattern does not apply here:** Unlike Rule 8, GDPR erasure has no counter to increment. Do not apply counter-increment patterns.

- **No analytics event for GDPR erasure:** §1.10 lists nine analytics events; none correspond to GDPR erasure. Do not emit PostHog events from this worker.

- **No SSE pub/sub from this worker:** §1.11 lists SSE channels published by Ingest/Scan/ML workers on drawing state transitions. GDPR worker does NOT publish to any SSE channel.

- **email UNIQUE constraint:** After clearing email, the replacement must be unique. Use `erased_{anonymous_id[:16]}@erased.invalid` — the anonymous_id prefix ensures uniqueness without exposing original PII. Do NOT use a static placeholder like `deleted@erased.invalid` (violates UNIQUE constraint on re-run or multi-user erasure).

- **Cross-session contract with S2-F:** `gdpr_init_service.py` (owned by S2-F) enqueues jobs to the `gdpr_erasure` queue. The job payload shape is `{"user_id": "<uuid-string>"}`. S2-F sets `user.deleted_at` and may enqueue a fast-path task, but the canonical 30-day erasure is triggered by the beat scanner in this session. Do not break this interface.

- **Approach to avoid — eager single-transaction erasure:** Never write `anonymous_id` and purge PII in the same transaction. If the transaction rolls back (e.g., on `audit_log` partition boundary error), the anonymous_id is never committed and the next retry would recompute — potentially a different value if HMAC_SERVER_SECRET has rotated. The two-transaction pattern prevents this.

---

##### Mocking contract

This is a backend worker session. It depends on the following internal service interfaces from other sessions:

**Celery task infrastructure (S1-D)**
- Queue routing constant `GDPR_ERASURE_QUEUE = "gdpr_erasure"` from `backend/app/workers/queues.py`
- `BaseTask` class from `backend/app/workers/base.py` — provides `autoretry_for`, `max_retries`, `default_retry_delay`
- Expected BaseTask retry policy for this worker: `max_retries=5`, `default_retry_delay=60` (seconds), `autoretry_for=(Exception,)` with exponential backoff

**Database session (S1-A + S0-A)**
- `get_db_session()` context manager from `backend/app/db/session.py`
- All SQLAlchemy models from `backend/app/db/models/`

**Job payload shape (published by S2-F, consumed here):**
```python
# Enqueued by gdpr_init_service.py (S2-F) OR by the beat scanner in tasks.py
{
    "user_id": str  # UUID string of user to erase
}
```

**Test doubles required:**
- PostgreSQL test database (via `tests/integration/fixtures/db.py` from S0-B) with full schema applied
- Redis test instance (via `tests/integration/fixtures/redis.py` from S0-B) for Celery broker
- `HMAC_SERVER_SECRET=test-secret-for-s2l-tests` set in test environment
- Factory functions to create `User` rows with controlled `deleted_at`, `anonymous_id` values

---

##### Acceptance criteria checklist

- [ ] Given a user with `deleted_at` ≥ 30 days ago and `anonymous_id` IS NULL, after worker runs, `user.anonymous_id` equals `HMAC-SHA256(user_id || HMAC_SERVER_SECRET)` hex digest [US-005 AC-1]
- [ ] `anonymous_id` is written and committed in a separate database transaction before any PII field is cleared [US-005 AC-1, AC-9]
- [ ] After worker completes, `user.email` matches pattern `erased_{anonymous_id[:16]}@erased.invalid` [US-005 AC-1]
- [ ] After worker completes, `user.display_name` equals `Deleted User` [US-005 AC-1]
- [ ] After worker completes, `user.password_hash` is NULL [US-005 AC-1]
- [ ] After worker completes, all `audit_log` rows where `user_id = <erased_user_id>` have `user_id` set to NULL [US-005 AC-1]
- [ ] After worker completes, all `ml_training_consent` rows where `user_id = <erased_user_id>` are deleted [US-005 AC-1]
- [ ] `user` row is NOT hard-deleted; `deleted_at` and `anonymous_id` are preserved post-erasure [US-005 AC-1]
- [ ] On retry where `anonymous_id` is already set, the worker does NOT recompute the HMAC; reads stored value directly [US-005 AC-2]
- [ ] On retry, the final state of all PII fields is identical to the first-run result [US-005 AC-2]
- [ ] A user with `deleted_at` set 29 days ago is NOT selected by the scanner [US-005 AC-3]
- [ ] A user with `deleted_at` NULL is NOT selected by the scanner [US-005 AC-4]
- [ ] Running the worker on an already-fully-erased user raises no error and leaves `anonymous_id` unchanged [US-005 AC-5]
- [ ] `compute_anonymous_id(user_id)` is deterministic: identical inputs always produce identical hex-digest output [US-005 AC-6]
- [ ] The `erase_user_pii` task is registered with `queue=GDPR_ERASURE_QUEUE` routing [US-005 AC-7]
- [ ] Importing the `gdpr` worker module with `HMAC_SERVER_SECRET` absent raises a startup-time error [US-005 AC-8]
- [ ] After crash-and-retry simulation (anonymous_id committed, PII purge then fails), the retry completes using the persisted `anonymous_id` without recomputation [US-005 AC-9]
- [ ] `user_correction` rows referencing the erased user are NOT modified (user record anonymization is sufficient) [Technical AC — NOT NULL constraint safety]
- [ ] Re-running erasure for multiple users does not violate the `email` UNIQUE constraint (each placeholder is unique via `anonymous_id` prefix) [Technical AC — uniqueness safety]

---

##### Independent Test

- **Test file path** (TDD — written first, must fail before implementation): `tests/integration/test_gdpr_worker.py`
- **Exact CI command**: `pytest tests/integration/test_gdpr_worker.py -v`

**AC → assertion mapping:**

| AC | `it(...)` / `test(...)` block name |
|---|---|
| US-005 AC-1 (anonymous_id computed correctly) | `test_anonymous_id_computed_as_hmac_sha256` |
| US-005 AC-1 + AC-9 (anonymous_id written in separate transaction first) | `test_anonymous_id_written_in_separate_transaction_before_pii_purge` |
| US-005 AC-1 (email cleared to placeholder) | `test_email_replaced_with_erased_placeholder` |
| US-005 AC-1 (display_name cleared) | `test_display_name_replaced_with_deleted_user` |
| US-005 AC-1 (password_hash nulled) | `test_password_hash_set_to_null` |
| US-005 AC-1 (audit_log user_id nulled) | `test_audit_log_user_id_set_to_null` |
| US-005 AC-1 (ml_training_consent deleted) | `test_ml_training_consent_rows_deleted` |
| US-005 AC-1 (user row retained, not hard-deleted) | `test_user_row_retained_with_deleted_at_preserved` |
| US-005 AC-2 (retry reads existing anonymous_id) | `test_retry_reads_existing_anonymous_id_not_recompute` |
| US-005 AC-2 (retry final state identical) | `test_retry_produces_identical_final_state` |
| US-005 AC-3 (29-day user not selected) | `test_scanner_skips_user_deleted_less_than_30_days_ago` |
| US-005 AC-4 (not-deleted user skipped) | `test_scanner_skips_user_without_deleted_at` |
| US-005 AC-5 (already-erased user no error) | `test_already_erased_user_is_noop` |
| US-005 AC-6 (HMAC determinism) | `test_compute_anonymous_id_is_deterministic` |
| US-005 AC-7 (queue routing) | `test_erase_task_registered_on_gdpr_erasure_queue` |
| US-005 AC-8 (startup refuses without secret) | `test_startup_refuses_without_hmac_server_secret` |
| US-005 AC-9 (crash-and-retry uses persisted anonymous_id) | `test_crash_after_anonymous_id_commit_retry_completes_correctly` |
| Technical AC (user_correction rows not modified) | `test_user_correction_rows_not_modified` |
| Technical AC (email placeholder uniqueness across multiple users) | `test_email_placeholder_unique_across_multiple_erased_users` |

**Fixtures / test doubles:**

```python
# tests/integration/test_gdpr_worker.py — fixtures required

import hmac
import hashlib
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

# From S0-B integration harness
from tests.integration.fixtures.db import test_db_session, apply_migrations
from tests.integration.fixtures.redis import test_redis

# From S1-A
from backend.app.db.models.user import User
from backend.app.db.models.audit_log import AuditLog
from backend.app.db.models.ml_training_consent import MLTrainingConsent
from backend.app.db.models.user_correction import UserCorrection

# Test data factories
def make_user(db: Session, *, deleted_at=None, anonymous_id=None) -> User:
    """Create a User row with controlled deleted_at and anonymous_id."""
    user = User(
        email=f"user_{uuid4()}@example.com",
        display_name="Test User",
        password_hash="$argon2id$v=19$...",
        email_verified=True,
        role="user",
        deleted_at=deleted_at,
        anonymous_id=anonymous_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def make_audit_log_entry(db: Session, user_id: str) -> AuditLog:
    entry = AuditLog(user_id=user_id, action_type="test_action", occurred_at=datetime.now(timezone.utc))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

def make_ml_consent(db: Session, user_id: str) -> MLTrainingConsent:
    consent = MLTrainingConsent(user_id=user_id, opted_in=True)
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent

THIRTY_ONE_DAYS_AGO = datetime.now(timezone.utc) - timedelta(days=31)
TWENTY_NINE_DAYS_AGO = datetime.now(timezone.utc) - timedelta(days=29)
TEST_HMAC_SECRET = "test-secret-for-s2l-tests"

def expected_anonymous_id(user_id: str) -> str:
    return hmac.new(TEST_HMAC_SECRET.encode(), user_id.encode(), digestmod=hashlib.sha256).hexdigest()
```

**Pre-conditions:**
- PostgreSQL test instance running with migrations applied (S1-A migrations 0001–0003)
- Redis test instance running (Celery broker)
- Environment variable `HMAC_SERVER_SECRET=test-secret-for-s2l-tests` set before any import of the `gdpr` worker module
- `DATABASE_URL` and `REDIS_URL` pointed to test instances
- S1-A models must be importable (prerequisite session must be merged)
- S1-D `queues.py` and `base.py` must be importable

**Isolation rule:** This test passes when only S2-L's PR is merged (on top of S1-A, S1-C, S1-D which are Phase 1 prerequisites). No sibling Phase 2 session (S2-A through S2-K, S2-M) needs to be merged. The test uses direct task function calls (not Celery worker process) and direct DB fixture access — no dependency on Phase 2 API endpoints.

---

##### Checkpoint

After this session's PR is merged, a user record with `deleted_at` set 31 days ago can be processed by calling `erase_user_pii(user_id)` directly, resulting in `user.anonymous_id` populated with the correct HMAC-SHA256 hex digest, `user.email` replaced with `erased_{anonymous_id[:16]}@erased.invalid`, `user.password_hash` set to NULL, and all `audit_log` rows for that user having `user_id` nulled — verifiable by querying the test database after the Celery task executes.

**Shippability claim:** This PR is independently mergeable to main even if no other session in the same wave (S2-A through S2-K, S2-M) has merged. It depends only on Phase 1 sessions (S1-A, S1-C, S1-D) which are Phase 2 gate prerequisites and must already be merged.

---

##### Output and handoff

| Export | File | Consuming Session(s) | Load-bearing? |
|---|---|---|---|
| `erase_user_pii` Celery task function | `backend/app/workers/gdpr/tasks.py` | S2-F (`gdpr_init_service.py` may call `.delay()`), S4-A (E2E test) | [LOAD-BEARING] |
| `scan_and_dispatch_erasure_jobs` Celery beat task | `backend/app/workers/gdpr/tasks.py` | S0-A Celery beat schedule config (must be registered) | [LOAD-BEARING] |
| `compute_anonymous_id(user_id: str) -> str` | `backend/app/workers/gdpr/anonymizer.py` | S4-A (E2E test assertions), S2-F (optional validation) | [LOAD-BEARING] |
| `purge_user_pii(user_id: str, db: Session) -> None` | `backend/app/workers/gdpr/anonymizer.py` | S4-A (direct call in E2E) | — |
| `GDPRErasureJobPayload` TypedDict/Pydantic model | `backend/app/workers/gdpr/tasks.py` | S2-F (type safety at enqueue site) | [LOAD-BEARING] |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/test_gdpr_worker.py -v",
    "file": "tests/integration/test_gdpr_worker.py"
  },
  "checkpoint": "A user record with deleted_at set 31 days ago is fully anonymized after calling erase_user_pii(user_id): user.anonymous_id is populated with the HMAC-SHA256 hex digest, user.email is replaced with the erased placeholder, user.password_hash is NULL, and all audit_log rows for that user have user_id set to NULL.",
  "manualAcs": [],
  "exports": [
    {
      "kind": "function",
      "name": "erase_user_pii",
      "shape": "(user_id: str) -> None  # Celery task registered on gdpr_erasure queue"
    },
    {
      "kind": "function",
      "name": "scan_and_dispatch_erasure_jobs",
      "shape": "() -> None  # Celery beat periodic task; scans for users with deleted_at < NOW() - 30 days"
    },
    {
      "kind": "function",
      "name": "compute_anonymous_id",
      "shape": "(user_id: str) -> str  # HMAC-SHA256(user_id || HMAC_SERVER_SECRET) hex digest"
    },
    {
      "kind": "function",
      "name": "purge_user_pii",
      "shape": "(user_id: str, db: Session) -> None  # Direct DB PII purge; separated from Celery task for testability"
    },
    {
      "kind": "type",
      "name": "GDPRErasureJobPayload",
      "shape": "{ user_id: str }"
    },
    {
      "kind": "module",
      "name": "backend/app/workers/gdpr",
      "shape": "backend/app/workers/gdpr/__init__.py"
    }
  ]
}
```