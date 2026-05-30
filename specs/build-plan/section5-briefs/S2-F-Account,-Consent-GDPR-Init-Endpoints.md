#### S2-F — Account, Consent & GDPR Init Endpoints

**Phase 2 | Backend API | Needs: S1-A, S1-B, S1-D, S1-E**

---

##### Objective

Implement the account profile management, ML training consent, and GDPR account-deletion-initiation HTTP endpoints, plus the shared server-side consent resolver function that the Phase 2 corrections endpoints depend on at correction-creation time.

---

##### Scope

**P0 MVP.** All work in this session is P0.

P0 work (implement fully):
- `GET /account`, `PATCH /account` — US-004 profile management
- `GET /account/consent`, `PATCH /account/consent` — US-004 ML training consent
- `DELETE /account` — US-005 GDPR erasure initiation (soft-delete + Celery job enqueue)
- `consent_service.resolve_training_consent` — cross-session LOAD-BEARING export consumed by S2-C

P1 stubs (clearly marked `# P1 STUB — not implemented`):
- In `consent_service.py`: stub methods for team-level consent *write* operations (setting team consent via `/teams/{id}/consent`). **Reading** team consent for resolution purposes IS required in P0 — `resolve_training_consent` must already read from `ml_training_consent WHERE team_id = user.team_id`. Only the team-admin-facing set/update surface is P1.

---

##### Technology constraints

From §1.8 — non-negotiable:

- **API Server**: FastAPI (Python). All HTTP handlers are FastAPI route functions in `account.py`.
- **Database ORM**: SQLAlchemy async (`AsyncSession`) with models from S1-A. Schema migrations are owned by S1-A; this session must not create Alembic revision files.
- **Queue broker**: Celery on Redis (`gdpr_erasure` queue). GDPR erasure jobs **must** be enqueued via `celery_app.send_task(...)` — never in-memory, never deferred via a background thread. Required by §1.4 ordering rule 14: "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts." The same principle applies to the GDPR erasure job.
- **Auth**: Supabase Python client (`supabase-py`) from S1-B's `supabase_client.py`. On account deletion, call `supabase_admin_client.auth.admin.sign_out(user_id)` to invalidate all Supabase sessions. Do **not** use raw `httpx` or `requests` for Supabase Admin calls.
- **Must NOT** use in-memory data stores, module-level dicts, or any non-Redis/DB persistence for consent or deletion state.
- **Pydantic v2**: Use `model_config = ConfigDict(extra='ignore')` on all request schemas so unknown fields are silently dropped.

---

##### Performance targets

None — see downstream sessions. This session owns no hard SLAs. `GET /account` and `GET /account/consent` are single-row DB lookups expected to comfortably fit within the Dashboard <2s P95 umbrella target (§1.9) but no per-endpoint SLA is assigned here.

---

##### Owned files

- `backend/app/api/routers/account.py`
- `backend/app/services/account_service.py`
- `backend/app/services/consent_service.py`
- `backend/app/services/gdpr_init_service.py`
- `tests/integration/test_account.py`

---

##### Read-only imports

| Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/schemas/contracts.py` | All Pydantic contract types; `DrawingProcessingState`, `BillingState`, `TierId`, `UserRole` |
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` (Celery application instance) |
| S0-A | `backend/app/config.py` | `settings` (for `settings.ENVIRONMENT`, `settings.HMAC_SERVER_SECRET`) |
| S1-A | `backend/app/db/models/user.py` | `User` (ORM model with fields: `id`, `email`, `display_name`, `email_verified`, `role`, `team_id`, `deleted_at`, `token_invalidated_at`, `anonymous_id`) |
| S1-A | `backend/app/db/models/ml_training_consent.py` | `MLTrainingConsent` (ORM model with fields: `id`, `user_id`, `team_id`, `opted_in`, `updated_at`) |
| S1-A | `backend/app/db/session.py` | `get_async_session` (FastAPI dependency providing `AsyncSession`) |
| S1-B | `backend/app/auth/dependencies.py` | `get_current_user` (FastAPI dependency returning authenticated `User` instance; raises `HTTPException(401)` if token invalid, expired, or `token_invalidated_at` check fails; raises `HTTPException(401)` if `user.deleted_at` is set) |
| S1-B | `backend/app/auth/supabase_client.py` | `supabase_admin_client` (initialized Supabase client with service role key) |
| S1-D | `backend/app/redis/cache.py` | `invalidate_subscription_flags(user_id: str) -> None` (deletes `subscription:flags:{user_id}` Redis key) |
| S1-E | `backend/app/analytics/events.py` | (imported for structural completeness; no analytics events are fired from account/consent endpoints per §1.10 event table — none of the nine events originate from this session's handlers) |

---

##### Do not touch

- `backend/app/main.py` — owned by S0-A (entry point)
- `backend/app/api/routers/__init__.py` — owned by S0-A (router registration stubs)
- `backend/app/api/routers/_stubs.py` — owned by S0-A
- `backend/app/config.py` — owned by S0-A
- `backend/app/db/base.py` — owned by S0-A
- `backend/app/db/session.py` — owned by S1-A
- `backend/app/db/models/` — all files owned by S1-A
- `backend/alembic/versions/` — all migration files owned by S1-A
- `backend/app/auth/` — all files owned by S1-B
- `backend/app/redis/` — all files owned by S1-D
- `backend/app/analytics/` — all files owned by S1-E
- `backend/app/workers/celery_app.py` — owned by S0-A
- `backend/app/workers/gdpr/` — owned by S2-L
- `backend/app/api/routers/auth.py`, `backend/app/services/auth_service.py`, `backend/app/services/password_reset.py` — owned by S2-A
- `backend/app/api/routers/drawings.py` and associated drawing services — owned by S2-B
- `backend/app/api/routers/symbols.py`, `backend/app/services/symbol_service.py`, `backend/app/services/correction_service.py` — owned by S2-C
- `backend/app/api/routers/exports.py` and associated export services — owned by S2-D
- `backend/app/api/routers/subscription.py`, `backend/app/api/routers/stripe_webhook.py`, and associated subscription services — owned by S2-E
- All files owned by S2-G, S2-H, S2-I, S2-J, S2-K, S2-L, S2-M

---

##### Architecture context

From §1.2 — Database Schema (verbatim):

```sql
-- USER
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

CREATE INDEX idx_user_team ON "user"(team_id);
CREATE INDEX idx_user_email ON "user"(email);

-- ML_TRAINING_CONSENT
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

From §1.3 — Role-Permission Matrix (verbatim, relevant rows):

```typescript
const ROLE_PERMISSIONS = {
  user: {
    gdpr_delete_account:     true,
    billing_manage:          true,      // personal subscription
  },
  team_member: {
    gdpr_delete_account:     true,
    billing_manage:          false,
  },
  team_admin: {
    gdpr_delete_account:     true,
    billing_manage:          true,      // team subscription
  },
} as const;
```

From §1.4 — Critical Ordering Rules (verbatim):

> **Rule 6 — training_consent snapshotted at correction creation time.** "Each correction save sends... the resolved `training_consent` value... at time of creation; the consent value must be snapshotted at correction time, not resolved lazily."

> **Rule 7 — Team-level consent evaluated server-side.** "Team-level consent resolution must be evaluated server-side to prevent client-side bypass; the resolved value is not a client-supplied field."

> **Rule 11 — GDPR erasure: anonymous_id written before any records updated.** "On first erasure job execution, the computed anonymous ID is written to `USER.anonymous_id` before any records are updated. All subsequent erasure job retries... read `USER.anonymous_id` directly." *(This rule governs the S2-L worker execution; S2-F is only responsible for initiating the job — the `anonymous_id` derivation logic lives in S2-L's `anonymizer.py`.)*

> **Rule 12 — Password reset: all sessions invalidated before token_invalidated_at updated.** "On password reset, all tokens are invalidated via Supabase Auth's `admin.signOut(userId)` call; `USER.token_invalidated_at` is simultaneously updated." *(Applied analogously to account deletion: S2-F must call Supabase `admin.sign_out` and set `token_invalidated_at` atomically with `deleted_at` in the same DB transaction.)*

> **Rule 14 — ML job must be enqueued via persistent queue (never in-memory).** "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts." *(Applies equally to the GDPR erasure job enqueued by this session.)*

From §1.5 — HTTP Status Code Contracts (verbatim, all applicable rows):

| Condition | Required code | Must never return |
|---|---|---|
| Account deletion initiation success | `204` | `200` |
| Unauthenticated request to protected endpoint | `401` | `403`, `200` |
| Authenticated user accessing resource they do not own | `403` | `404`, `200` |

From §1.11 — Cross-Session Runtime Patterns (verbatim, applicable rows):

**Redis Cache Keys:**

| Key Pattern | Written By | Read By | TTL |
|---|---|---|---|
| `subscription:flags:{user_id}` | FastAPI on login / Stripe webhook handler | FastAPI middleware (every authenticated request, feature-gate evaluation) | 5 minutes; invalidated on webhook receipt |

*(On `DELETE /account`, this session must call `invalidate_subscription_flags(user_id)` from S1-D's `cache.py` after the DB transaction commits, to prevent stale feature-gate data from a soft-deleted user.)*

**Celery Job Queue Names (verbatim):**

| Queue | Workers | Job Types |
|---|---|---|
| `gdpr_erasure` | GDPR Worker (CPU, scheduled) | PII purge, anonymization |

From §1.12 — Environment Variable Schema (relevant rows):

| Variable | Default if Absent | Startup Behavior if Absent |
|---|---|---|
| `HMAC_SERVER_SECRET` | None | Refuse to start (used for `anonymous_id` derivation — in S2-L, but config validation applies at startup) |
| `SUPABASE_URL` | None | Refuse to start |
| `SUPABASE_SERVICE_ROLE_KEY` | None | Refuse to start |
| `ENVIRONMENT` | `production` | Use `production` |

From §1.13 — Feature Scope:

> **P0 (MVP):** US-004: ML training consent management and account settings (display name, email); US-005: Account deletion and GDPR erasure pipeline (30-day async, anonymous_id persistence)

---

##### User stories and acceptance criteria

**US-004: ML training consent management and account settings (display name, email)**

*P0 MVP (§1.13)*

As a registered user, I want to view and update my account profile (display name, email address) and manage my ML training consent preference, so that my personal information is accurate and I control whether my correction actions are used for model improvement.

**AC-1 (Profile Retrieval — Happy Path):** Given I am authenticated with a valid JWT, when I call `GET /account`, then I receive HTTP 200 with a JSON body containing at minimum: `id` (UUID), `email` (string), `display_name` (string), `email_verified` (boolean), `role` (one of `user | team_member | team_admin`), `team_id` (UUID or null) — all reflecting the current state of my `user` record.

**AC-2 (Profile Retrieval — Unauthenticated):** Given I am not authenticated (no `Authorization` header, or an expired/invalid token), when I call `GET /account`, then I receive HTTP 401 and no user data is returned.

**AC-3 (Display Name Update — Happy Path):** Given I am authenticated, when I call `PATCH /account` with body `{"display_name": "New Name"}`, then I receive HTTP 200 with a response body reflecting the updated `display_name`, and the change is durably persisted in the `user` table.

**AC-4 (Email Update — Happy Path):** Given I am authenticated, when I call `PATCH /account` with body `{"email": "newemail@example.com"}`, then I receive HTTP 200 with the updated profile, the `email` field in the `user` table is updated, and `email_verified` is set to `false` in the same transaction (re-verification is required for the new address).

**AC-5 (Email Update — Invalid Format):** Given I am authenticated, when I call `PATCH /account` with body `{"email": "not-a-valid-email"}`, then I receive HTTP 422 (Pydantic validation failure) and no database write occurs.

**AC-6 (Profile Update — Empty Body No-Op):** Given I am authenticated, when I call `PATCH /account` with an empty body `{}` or a body containing only unknown fields, then I receive HTTP 200 with the unchanged profile. An empty PATCH is a valid no-op; it must not raise an error.

**AC-7 (Profile Update — Extra Fields Ignored):** Given I am authenticated, when I call `PATCH /account` with a body that includes fields not in the allowed set (e.g., `{"role": "team_admin"}`, `{"team_id": "..."}`, `{"deleted_at": "..."}`), then those fields are silently ignored, the allowed fields (if present) are applied, and no privilege escalation occurs.

**AC-8 (Profile Update — Unauthenticated):** Given I am not authenticated, when I call `PATCH /account`, then I receive HTTP 401.

**AC-9 (Consent Retrieval — Solo User, No Consent Record):** Given I am authenticated as a solo user (no `team_id`), and no `ml_training_consent` record exists for my `user_id`, when I call `GET /account/consent`, then I receive HTTP 200 with body `{"opted_in": false, "source": "user"}`.

**AC-10 (Consent Retrieval — Solo User, Existing Opted-In Record):** Given I am authenticated as a solo user, and an `ml_training_consent` record exists for my `user_id` with `opted_in = true`, when I call `GET /account/consent`, then I receive HTTP 200 with body `{"opted_in": true, "source": "user"}`.

**AC-11 (Consent Retrieval — Team Member, Team Consent Record Present):** Given I am a team member (`team_id` is set on my `user` record), and an `ml_training_consent` record exists for my `team_id` with `opted_in = true`, when I call `GET /account/consent`, then I receive HTTP 200 with body `{"opted_in": true, "source": "team"}` — regardless of my personal `ml_training_consent` record.

**AC-12 (Consent Retrieval — Team Member, Team Consent Record Absent):** Given I am a team member but no `ml_training_consent` record exists for my `team_id`, when I call `GET /account/consent`, then the response falls back to my personal consent record (`{"opted_in": <user_value>, "source": "user"}`), or `{"opted_in": false, "source": "user"}` if no personal record exists either.

**AC-13 (Consent Retrieval — Unauthenticated):** Given I am not authenticated, when I call `GET /account/consent`, then I receive HTTP 401.

**AC-14 (Consent Update — Create Record):** Given I am authenticated as a solo user with no existing consent record, when I call `PATCH /account/consent` with body `{"opted_in": true}`, then I receive HTTP 200, a new `ml_training_consent` record is created for my `user_id` with `opted_in = true` and `updated_at` set to the current timestamp.

**AC-15 (Consent Update — Update Existing Record):** Given I am authenticated and an `ml_training_consent` record already exists for my `user_id` with `opted_in = false`, when I call `PATCH /account/consent` with body `{"opted_in": true}`, then I receive HTTP 200, the existing record's `opted_in` is updated to `true` and `updated_at` is refreshed. No duplicate records are created.

**AC-16 (Consent Update — Unauthenticated):** Given I am not authenticated, when I call `PATCH /account/consent`, then I receive HTTP 401.

**AC-17 (Consent Resolution — Server-Side Enforcement):** The effective training consent returned by `GET /account/consent` and the value returned by `consent_service.resolve_training_consent(user_id, db)` must always be derived from database records. The `PATCH /account/consent` request body must not contain a `source` or `resolved` field — these are computed server-side only. (§1.4 rule 7.)

**AC-18 (resolve_training_consent — Team Precedence):** When called for a user who is a team member whose team has a `ml_training_consent` record with `opted_in = true`, `resolve_training_consent` returns `True` — regardless of the user's personal consent record.

**AC-19 (resolve_training_consent — Solo User):** When called for a user with no `team_id` and a personal `ml_training_consent` record with `opted_in = false`, `resolve_training_consent` returns `False`.

**AC-20 (resolve_training_consent — Default False):** When called for a user with no team and no personal consent record, `resolve_training_consent` returns `False`.

---

**US-005: Account deletion and GDPR erasure pipeline (30-day async, anonymous_id persistence)**

*P0 MVP (§1.13)*

As a registered user, I want to permanently delete my account and all associated personal data, so that I can exercise my right to erasure under GDPR.

**AC-1 (Deletion Initiation — Happy Path):** Given I am authenticated, when I call `DELETE /account`, then I receive HTTP 204 (no body), `user.deleted_at` is set to the current UTC timestamp in the `user` table, and a GDPR erasure Celery task is enqueued on the `gdpr_erasure` queue with a payload containing my `user_id`.

**AC-2 (Session Invalidation on Deletion):** Given I am authenticated, when I call `DELETE /account`, then `user.token_invalidated_at` is set to the current UTC timestamp atomically in the same database transaction as `deleted_at` (both committed or neither committed), and `supabase_admin_client.auth.admin.sign_out(user_id)` is called to revoke all active Supabase sessions.

**AC-3 (Post-Deletion Auth Rejection):** Given my account has been soft-deleted (`deleted_at` is set and `token_invalidated_at` is set), when I make a subsequent request to `GET /account` using my previously-valid JWT, then I receive HTTP 401. (S1-B middleware checks `deleted_at` and `token_invalidated_at`; this session is responsible for correctly setting those fields.)

**AC-4 (Deletion — Unauthenticated):** Given I am not authenticated, when I call `DELETE /account`, then I receive HTTP 401.

**AC-5 (GDPR Job Payload):** The Celery task enqueued on `DELETE /account` must be sent to the `gdpr_erasure` queue. The task arguments must contain `user_id` as a string UUID. In environments where `settings.ENVIRONMENT != "production"`, the `countdown` parameter must be `0` (immediate execution for testability). In `production`, `countdown` must be `30 * 24 * 3600` (2,592,000 seconds — 30 days).

**AC-6 (Subscription Cache Invalidation):** When `DELETE /account` is called, `invalidate_subscription_flags(user_id)` from S1-D must be called after the DB transaction commits, removing the `subscription:flags:{user_id}` Redis key.

**AC-7 (Deletion Idempotency):** If `DELETE /account` is called when `user.deleted_at` is already set (account already soft-deleted), the endpoint returns HTTP 204 immediately without re-enqueuing the GDPR Celery job. The GDPR job must be enqueued exactly once per account.

**AC-8 (Celery Enqueue Failure Resilience):** If the Celery broker is unavailable and `send_task` raises an exception when `DELETE /account` is called, the endpoint must still return HTTP 204 (the DB transaction for soft-delete has already committed). The Celery enqueue failure must be logged as an error. The `deleted_at` and `token_invalidated_at` values already committed to the database must not be rolled back. (A manual re-enqueue or retry mechanism is a P1 concern.)

---

##### UX and design specification

N/A — no frontend component. This is a backend-only API session. All frontend interaction with these endpoints is handled by S3-E (Account & Consent frontend).

---

##### Critical implementation notes

- **`resolve_training_consent` is LOAD-BEARING for S2-C.** S2-C's `correction_service.py` imports and calls `consent_service.resolve_training_consent(user_id, db)` at correction-creation time to snapshot the `training_consent` value into `user_correction.training_consent` (§1.4 rule 6). The function signature `(user_id: str, db: AsyncSession) -> bool` must not change after merge. The resolution algorithm must be:
  1. Load `user` record; read `user.team_id`
  2. If `team_id` is non-null: query `SELECT * FROM ml_training_consent WHERE team_id = :team_id LIMIT 1`; if found, return `record.opted_in`
  3. Query `SELECT * FROM ml_training_consent WHERE user_id = :user_id LIMIT 1`; if found, return `record.opted_in`
  4. Return `False` (default — not consented)
  Step 2 must execute before step 3 — team consent takes precedence unconditionally.

- **Atomicity on `DELETE /account` — DB transaction scope:** `user.deleted_at` and `user.token_invalidated_at` must be set within a single `async with db.begin()` block. Supabase `admin.sign_out` and Celery `send_task` must be called **after** the transaction commits. If the DB transaction fails, neither Supabase invalidation nor job enqueue should occur. If the DB succeeds but Supabase `admin.sign_out` fails, log and continue — `token_invalidated_at` serves as the fallback guard.

- **GDPR job enqueue only after commit:** Do not call `celery_app.send_task(...)` inside the `async with db.begin()` block. Call it in the `finally`/`else` path after the transaction closes successfully. Enqueuing before commit risks creating a worker job for a user whose soft-delete did not persist.

- **Idempotency guard on `DELETE /account`:** Before writing to the DB, check `user.deleted_at is not None`. If already set, return `Response(status_code=204)` immediately without any DB writes, Supabase calls, Redis invalidation, or Celery enqueue.

- **Email update atomicity:** When `PATCH /account` changes `email`, set `user.email_verified = False` in the same `UPDATE` statement as `user.email`. Never leave a state where `email` has changed but `email_verified` is still `True`.

- **No `role` or `team_id` in `PATCH /account` request schema.** The `PatchAccountRequest` Pydantic model must only expose `display_name: Optional[str]` and `email: Optional[EmailStr]`. Configure `model_config = ConfigDict(extra='ignore')` so extra fields (e.g., `role`, `team_id`, `deleted_at`) are silently dropped. Never expose these fields for client mutation.

- **Consent record update-or-create must be safe for concurrent requests.** The `ml_training_consent` table has no unique constraint on `user_id` in the spec schema (§1.2). Use a `SELECT ... FOR UPDATE` within a transaction (read-then-write pattern inside `async with db.begin()`) rather than a bare `INSERT ON CONFLICT` which requires a named unique index. The pattern:
  1. `SELECT ... WHERE user_id = :uid FOR UPDATE` — locks any existing row
  2. If found: `UPDATE ... SET opted_in = :v, updated_at = now()`
  3. If not found: `INSERT INTO ml_training_consent (user_id, opted_in, updated_at) VALUES (...)`
  This ensures exactly one record per user and prevents duplicate inserts under concurrent requests.

- **`source` field in consent response is always computed server-side.** `GET /account/consent` must derive `source` by checking whether the returned value came from a team record (`"team"`) or a user/default record (`"user"`). This field is read-only and must not be accepted in `PATCH /account/consent` request bodies (§1.4 rule 7).

- **HTTP 204 must have no response body** for `DELETE /account`. Use `Response(status_code=204)` in FastAPI, not `JSONResponse({"status": "ok"}, status_code=204)`.

- **Supabase `admin.sign_out` failure must not block the 204 response.** Wrap the Supabase call in `try/except`, log the exception at `ERROR` level including user_id, then proceed to Celery enqueue and return 204. The `token_invalidated_at` field is the fallback enforcement mechanism.

- **GDPR countdown configuration:**
  ```python
  countdown = 0 if settings.ENVIRONMENT != "production" else (30 * 24 * 3600)
  celery_app.send_task(
      "backend.app.workers.gdpr.tasks.gdpr_erasure_task",
      args=[str(user_id)],
      queue="gdpr_erasure",
      countdown=countdown,
  )
  ```
  The task name string `"backend.app.workers.gdpr.tasks.gdpr_erasure_task"` is the contract with S2-L. If S2-L names its task differently, this string must match S2-L's registered task name.

- **Silent failure risk — stale subscription cache:** If `invalidate_subscription_flags` raises (Redis unavailable), log a warning and do not let it propagate into the 204 response. A stale cache entry will expire naturally within 5 minutes (§1.11 TTL).

- **Do not fire any of the nine analytics events from this session's handlers.** None of the events listed in §1.10 are emitted from account/consent endpoints. Importing S1-E is for structural completeness only.

---

##### Mocking contract

**Backend session** — this session depends on the following internal interfaces from other sessions:

| Dependency | Interface Type | Exact Contract Shape |
|---|---|---|
| S1-A `User` ORM | DB read/write | Fields used: `id (UUID)`, `email (str)`, `display_name (str)`, `email_verified (bool)`, `role (str)`, `team_id (UUID \| None)`, `deleted_at (datetime \| None)`, `token_invalidated_at (datetime \| None)` |
| S1-A `MLTrainingConsent` ORM | DB read/write | Fields used: `id (UUID)`, `user_id (UUID \| None)`, `team_id (UUID \| None)`, `opted_in (bool)`, `updated_at (datetime)` |
| S1-B `get_current_user` dependency | FastAPI dependency | Returns `User` instance; raises `HTTPException(status_code=401)` for invalid/expired token, `token_invalidated_at` violation, or `deleted_at` set |
| S1-B `supabase_admin_client` | Supabase Python client | `await supabase_admin_client.auth.admin.sign_out(str(user_id))` — call signature; no return value used |
| S1-D `invalidate_subscription_flags` | Redis function | `invalidate_subscription_flags(user_id: str) -> None` — deletes `subscription:flags:{user_id}` |
| S0-A `celery_app.send_task` | Celery dispatch | `celery_app.send_task(name: str, args: list, queue: str, countdown: int)` — name must match S2-L's registered task name `"backend.app.workers.gdpr.tasks.gdpr_erasure_task"`, queue `"gdpr_erasure"`, args `[user_id_str]` |

**Test doubles used in `tests/integration/test_account.py`:**

```python
# Real infrastructure
# - PostgreSQL (via tests/integration/fixtures/db.py from S0-B)
# - Redis (via tests/integration/fixtures/redis.py from S0-B)

# Mocked interfaces
@pytest.fixture
def mock_supabase_sign_out(monkeypatch):
    """
    Patches supabase_admin_client.auth.admin.sign_out to AsyncMock.
    Returns MagicMock so tests can assert call count and args.
    """
    mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "backend.app.auth.supabase_client.supabase_admin_client.auth.admin.sign_out",
        mock
    )
    return mock

@pytest.fixture
def mock_celery_send_task(monkeypatch):
    """
    Patches celery_app.send_task to MagicMock.
    Does NOT enqueue real tasks; captures (name, args, kwargs) for assertion.
    """
    mock = MagicMock(return_value=None)
    monkeypatch.setattr("backend.app.workers.celery_app.celery_app.send_task", mock)
    return mock

@pytest.fixture
def mock_invalidate_flags(monkeypatch):
    """
    Patches invalidate_subscription_flags to MagicMock to assert it is called.
    """
    mock = MagicMock(return_value=None)
    monkeypatch.setattr(
        "backend.app.redis.cache.invalidate_subscription_flags", mock
    )
    return mock
```

---

##### Acceptance criteria checklist

**US-004 — Profile Management:**
- [ ] `GET /account` returns HTTP 200 with `{id, email, display_name, email_verified, role, team_id}` for authenticated user [US-004 AC-1]
- [ ] `GET /account` returns HTTP 401 when called without a valid token [US-004 AC-2]
- [ ] `PATCH /account` with `{"display_name": "New Name"}` returns HTTP 200 and persists the new display_name to the DB [US-004 AC-3]
- [ ] `PATCH /account` with `{"email": "new@example.com"}` returns HTTP 200, updates the email column, and sets `email_verified = false` in the same transaction [US-004 AC-4]
- [ ] `PATCH /account` with `{"email": "invalid"}` returns HTTP 422 with no DB write [US-004 AC-5]
- [ ] `PATCH /account` with empty body `{}` returns HTTP 200 with unchanged profile (no-op) [US-004 AC-6]
- [ ] `PATCH /account` with `{"role": "team_admin"}` silently ignores the `role` field and does not escalate privileges [US-004 AC-7]
- [ ] `PATCH /account` returns HTTP 401 when unauthenticated [US-004 AC-8]

**US-004 — Consent:**
- [ ] `GET /account/consent` returns `{"opted_in": false, "source": "user"}` for solo user with no consent record [US-004 AC-9]
- [ ] `GET /account/consent` returns `{"opted_in": true, "source": "user"}` for solo user with existing opted-in consent record [US-004 AC-10]
- [ ] `GET /account/consent` returns `{"opted_in": true, "source": "team"}` for team member whose team has `opted_in = true` record, regardless of user's personal record [US-004 AC-11]
- [ ] `GET /account/consent` falls back to user consent record (or default false) when team has no consent record [US-004 AC-12]
- [ ] `GET /account/consent` returns HTTP 401 when unauthenticated [US-004 AC-13]
- [ ] `PATCH /account/consent` with `{"opted_in": true}` creates a new `ml_training_consent` record for the user and returns HTTP 200 [US-004 AC-14]
- [ ] `PATCH /account/consent` with `{"opted_in": true}` on an existing `opted_in = false` record updates the record without creating a duplicate, and returns HTTP 200 [US-004 AC-15]
- [ ] `PATCH /account/consent` returns HTTP 401 when unauthenticated [US-004 AC-16]
- [ ] `PATCH /account/consent` request body does not accept a `source` field (422 or silent ignore) [US-004 AC-17]
- [ ] `resolve_training_consent` returns `True` for a team member whose team has `opted_in = true`, regardless of their personal consent record [US-004 AC-18]
- [ ] `resolve_training_consent` returns `False` for a solo user with `opted_in = false` personal record [US-004 AC-19]
- [ ] `resolve_training_consent` returns `False` for a user with no consent record and no team [US-004 AC-20]

**US-005 — Account Deletion:**
- [ ] `DELETE /account` returns HTTP 204 with no response body [US-005 AC-1]
- [ ] `DELETE /account` sets `user.deleted_at` to a non-null UTC timestamp [US-005 AC-1]
- [ ] `DELETE /account` enqueues a Celery task on the `gdpr_erasure` queue with `user_id` in the args [US-005 AC-1]
- [ ] `DELETE /account` sets `user.token_invalidated_at` in the same DB transaction as `user.deleted_at` [US-005 AC-2]
- [ ] `DELETE /account` calls `supabase_admin_client.auth.admin.sign_out` with the user's ID [US-005 AC-2]
- [ ] After `DELETE /account`, a subsequent `GET /account` with the same token returns HTTP 401 [US-005 AC-3]
- [ ] `DELETE /account` returns HTTP 401 when unauthenticated [US-005 AC-4]
- [ ] The GDPR Celery task `countdown` is `0` when `ENVIRONMENT != "production"` [US-005 AC-5]
- [ ] The GDPR task args contain `[user_id_as_string]` and queue is `"gdpr_erasure"` [US-005 AC-5]
- [ ] `DELETE /account` calls `invalidate_subscription_flags(user_id)` after DB commit [US-005 AC-6]
- [ ] Calling `DELETE /account` a second time on an already soft-deleted account returns HTTP 204 without re-enqueuing the GDPR job [US-005 AC-7]
- [ ] When `celery_app.send_task` raises an exception, `DELETE /account` still returns HTTP 204 and `user.deleted_at` remains committed in the DB [US-005 AC-8]

**Technical ACs (no direct story mapping):**
- [ ] `deleted_at` and `token_invalidated_at` are both set in a single atomic DB transaction (verified by asserting both non-null after a successful `DELETE /account`) [TECHNICAL]
- [ ] Celery `send_task` is called only after the DB transaction commits, never inside the transaction block [TECHNICAL]
- [ ] `PATCH /account/consent` repeated twice for the same user produces exactly one `ml_training_consent` row (no duplicate rows created) [TECHNICAL]
- [ ] `resolve_training_consent` Python function signature is exactly `(user_id: str, db: AsyncSession) -> bool` [TECHNICAL]
- [ ] `Supabase sign_out` failure (raises exception) does not prevent HTTP 204 response on `DELETE /account` [TECHNICAL — covered by AC-8 test variant]

---

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation): `tests/integration/test_account.py`

**Exact CI command**: `pytest tests/integration/test_account.py -v`

**AC → assertion mapping**:

| AC | `test(...)` block name |
|---|---|
| US-004 AC-1 | `test_get_account_returns_profile_for_authenticated_user` |
| US-004 AC-2 | `test_get_account_returns_401_when_unauthenticated` |
| US-004 AC-3 | `test_patch_account_updates_display_name` |
| US-004 AC-4 | `test_patch_account_updates_email_and_clears_email_verified` |
| US-004 AC-5 | `test_patch_account_invalid_email_returns_422` |
| US-004 AC-6 | `test_patch_account_empty_body_is_noop` |
| US-004 AC-7 | `test_patch_account_ignores_role_field` |
| US-004 AC-8 | `test_patch_account_unauthenticated_returns_401` |
| US-004 AC-9 | `test_get_consent_no_record_returns_default_false_user_source` |
| US-004 AC-10 | `test_get_consent_solo_user_opted_in_returns_true` |
| US-004 AC-11 | `test_get_consent_team_member_team_consent_overrides_user` |
| US-004 AC-12 | `test_get_consent_team_member_no_team_record_falls_back_to_user` |
| US-004 AC-13 | `test_get_consent_unauthenticated_returns_401` |
| US-004 AC-14 | `test_patch_consent_creates_new_record` |
| US-004 AC-15 | `test_patch_consent_updates_existing_record_no_duplicate` |
| US-004 AC-16 | `test_patch_consent_unauthenticated_returns_401` |
| US-004 AC-17 | `test_patch_consent_source_field_not_accepted` |
| US-004 AC-18 | `test_resolve_training_consent_team_takes_precedence_over_user` |
| US-004 AC-19 | `test_resolve_training_consent_solo_user_false` |
| US-004 AC-20 | `test_resolve_training_consent_default_false_no_record` |
| US-005 AC-1 (204 + deleted_at + job) | `test_delete_account_returns_204_sets_deleted_at_enqueues_job` |
| US-005 AC-2 (token_invalidated_at + sign_out) | `test_delete_account_sets_token_invalidated_at_and_calls_sign_out` |
| US-005 AC-3 (post-deletion 401) | `test_delete_account_subsequent_request_returns_401` |
| US-005 AC-4 | `test_delete_account_unauthenticated_returns_401` |
| US-005 AC-5 (countdown + payload) | `test_delete_account_gdpr_task_payload_and_countdown` |
| US-005 AC-6 | `test_delete_account_invalidates_subscription_flags_cache` |
| US-005 AC-7 | `test_delete_account_idempotent_no_double_enqueue` |
| US-005 AC-8 | `test_delete_account_celery_failure_still_returns_204` |
| Technical (atomic deleted_at + token_invalidated_at) | `test_delete_account_both_timestamps_set_in_same_transaction` |
| Technical (send_task after commit) | *(verified implicitly by `test_delete_account_celery_failure_still_returns_204` — soft-delete survives Celery failure)* |
| Technical (consent no duplicate rows) | `test_patch_consent_is_idempotent_no_duplicate_rows` |
| Technical (resolve_training_consent signature) | *(verified by all `test_resolve_training_consent_*` tests importing and calling the function directly)* |

**Fixtures / test doubles**:

```python
# Pre-built fixture objects (all using real Postgres from S0-B)

@pytest.fixture
async def solo_user(db_session) -> User:
    """User with no team_id, no consent record, email_verified=True."""

@pytest.fixture
async def solo_user_with_consent(db_session, solo_user) -> tuple[User, MLTrainingConsent]:
    """solo_user plus an ml_training_consent record with opted_in=True."""

@pytest.fixture
async def team_and_member(db_session) -> tuple[Team, User]:
    """A Team row and a User with team_id set to that team, role='team_member'."""

@pytest.fixture
async def team_consent_opted_in(db_session, team_and_member) -> MLTrainingConsent:
    """ml_training_consent record for the team with opted_in=True."""

@pytest.fixture
def auth_headers_for(monkeypatch):
    """
    Factory fixture: given a User, patches get_current_user dependency
    to return that user. Returns Authorization header dict for httpx TestClient.
    """

@pytest.fixture
def mock_supabase_sign_out(monkeypatch) -> AsyncMock:
    """
    Patches backend.app.auth.supabase_client.supabase_admin_client.auth.admin.sign_out
    to AsyncMock(return_value=None). Returns mock for call assertions.
    """

@pytest.fixture
def mock_celery_send_task(monkeypatch) -> MagicMock:
    """
    Patches backend.app.workers.celery_app.celery_app.send_task
    to MagicMock(return_value=None). Returns mock for call/kwarg assertions.
    No real Celery broker connection made.
    """

@pytest.fixture
def mock_invalidate_flags(monkeypatch) -> MagicMock:
    """
    Patches backend.app.redis.cache.invalidate_subscription_flags
    to MagicMock(return_value=None).
    """

@pytest.fixture
def mock_celery_send_task_raises(monkeypatch) -> MagicMock:
    """
    Variant of mock_celery_send_task that raises ConnectionError.
    Used in test_delete_account_celery_failure_still_returns_204.
    """
```

Mock response shapes used in tests are consistent with the `AccountProfileResponse` and `ConsentResponse` schemas defined in this session.

**Pre-conditions**:
- PostgreSQL running with S1-A migrations applied (tables: `user`, `team`, `ml_training_consent`, `subscription`)
- Redis running (S0-B `tests/integration/fixtures/redis.py`)
- Environment variables set: `DATABASE_URL`, `REDIS_URL`, `ENVIRONMENT=test`, `SUPABASE_URL=http://localhost:54321`, `SUPABASE_SERVICE_ROLE_KEY=test-key`, `HMAC_SERVER_SECRET=test-secret-32chars`
- S1-B `get_current_user` dependency is patchable via `monkeypatch` to return specific test `User` instances without a real JWT

**Isolation rule**: This test passes with only S2-F merged into main. It does not require S2-C, S2-L, or any other Phase 2 session to be merged. `resolve_training_consent` is tested directly by importing from `backend.app.services.consent_service`. No correction endpoints, no export endpoints, no Stripe endpoints are invoked. All Celery, Supabase, and Redis external calls are mocked. S1-A through S1-E are Phase 1 prerequisites and are already merged.

---

##### Checkpoint

- **One-sentence observable outcome**: `GET /account` with a valid JWT returns a 200 JSON profile; `PATCH /account/consent` with `{"opted_in": true}` upserts an ML training consent record; `DELETE /account` returns 204, sets `deleted_at` and `token_invalidated_at` on the user row, and enqueues a task on the `gdpr_erasure` Celery queue.
- **Shippability claim**: This PR is independently mergeable to main even if no other session in the same wave (S2-A through S2-M) has merged.

---

##### Output and handoff

| Export | Kind | Consuming Sessions | Load-Bearing? |
|---|---|---|---|
| `consent_service.resolve_training_consent(user_id: str, db: AsyncSession) -> bool` | Function | S2-C (`correction_service.py` — snapshots value into `user_correction.training_consent` at correction-creation time) | **[LOAD-BEARING]** — signature must not change after merge |
| `gdpr_init_service.initiate_account_deletion(user_id: str, db: AsyncSession) -> None` | Function | S2-L implicitly (via queue contract: task name `"backend.app.workers.gdpr.tasks.gdpr_erasure_task"`, queue `"gdpr_erasure"`, args `[user_id_str]`) | Yes |
| `AccountProfileResponse` Pydantic schema (`id: str, email: str, display_name: str, email_verified: bool, role: str, team_id: str | None`) | Type | S3-E (frontend expects this shape from `GET /account`) | Yes |
| `ConsentResponse` Pydantic schema (`opted_in: bool, source: Literal["user", "team"]`) | Type | S3-E (frontend expects this shape from `GET /account/consent`) | Yes |
| `account` FastAPI router (prefix `/account`) | Module/Router | S0-A (router include stub maps to `backend.app.api.routers.account.router`) | Yes |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/test_account.py -v",
    "file": "tests/integration/test_account.py"
  },
  "checkpoint": "GET /account with a valid JWT returns HTTP 200 with a JSON profile, PATCH /account/consent with {opted_in: true} upserts an ML training consent record, and DELETE /account returns HTTP 204 with user.deleted_at set and a task enqueued on the gdpr_erasure Celery queue.",
  "manualAcs": [],
  "exports": [
    {
      "kind": "function",
      "name": "resolve_training_consent",
      "shape": "(user_id: str, db: AsyncSession) -> bool"
    },
    {
      "kind": "function",
      "name": "initiate_account_deletion",
      "shape": "(user_id: str, db: AsyncSession) -> None"
    },
    {
      "kind": "type",
      "name": "AccountProfileResponse",
      "shape": "{ id: str; email: str; display_name: str; email_verified: bool; role: str; team_id: str | None }"
    },
    {
      "kind": "type",
      "name": "ConsentResponse",
      "shape": "{ opted_in: bool; source: Literal['user', 'team'] }"
    },
    {
      "kind": "module",
      "name": "backend/app/api/routers/account",
      "shape": "backend/app/api/routers/account.py"
    },
    {
      "kind": "module",
      "name": "backend/app/services/consent_service",
      "shape": "backend/app/services/consent_service.py"
    },
    {
      "kind": "module",
      "name": "backend/app/services/gdpr_init_service",
      "shape": "backend/app/services/gdpr_init_service.py"
    }
  ]
}
```