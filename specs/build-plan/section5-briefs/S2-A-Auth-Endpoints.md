---

#### S2-A — Auth Endpoints

**Phase 2 | Auth/Contracts | Needs: S1-A, S1-B, S1-D, S1-E**

##### Objective

Implement all seven authentication API endpoints (`register`, `login`, `oauth/google`, `refresh`, `logout`, `password-reset/request`, `password-reset/confirm`) as the sole P0 authentication boundary, enforcing brute-force lockout, account-link conflict detection, and atomic session invalidation on password reset.

##### Scope

**P0 MVP** — all work in this session is P0. All seven auth route handlers, the `auth_service.py` and `password_reset.py` service modules, and the integration test file must be fully implemented.

There are no P1 stubs required from this session. P1 API-key access (FR-11) is gated in a future session and touches none of the files owned here.

##### Technology constraints

| Layer | Required | Notes |
|---|---|---|
| API Framework | FastAPI (Python) | Non-negotiable per §1.8; async handlers required |
| Auth backend | Supabase Auth (self-hosted) | JWT RS256; `admin.signOut(userId)` for session revocation; client provided by S1-B `supabase_client.py` |
| Token format | JWT RS256 | Verified using `JWT_RS256_PUBLIC_KEY`; verification logic in S1-B `jwt_verifier.py` |
| Brute-force storage | Redis (ElastiCache) | `brute_force.py` provided by S1-B; key pattern `brute_force:{email}` with 15-minute TTL |
| Queue | Celery on Redis broker | Notification tasks dispatched to `notification` queue (queue names in S1-D `queues.py`); must use persistent queue, never in-memory dispatch |
| ORM / DB | SQLAlchemy (async) + PostgreSQL | Session factory from S1-A / S0-A `db/session.py` |
| Migrations | Alembic | No new migrations in this session; user model already created in S1-A |
| Analytics | PostHog via S1-E | No analytics events are fired from auth endpoints (none of the 9 defined events map to auth actions); S1-E dependency is infra completeness |

**Must NOT use:**
- Direct SendGrid API calls from auth endpoints — all email dispatch must go through the `notification` Celery queue (S2-M consumes it)
- In-memory task dispatch (e.g., `asyncio.create_task` for notifications) — violates §1.4 rule 14 for queue durability
- Direct Supabase Admin API for brute-force storage — use Redis only (S1-B `brute_force.py`)

##### Performance targets

None directly owned — see downstream sessions.

The brute-force lockout is a **hard security constraint** (not an SLA): "After 5 failed attempts, 15-minute lockout — Hard constraint (security) — Redis TTL-based counter" (§1.9). This session is directly responsible for enforcing it.

The pre-signed URL expiry and ML timeouts are not relevant to this session.

##### Owned files

```
backend/app/api/routers/auth.py
backend/app/services/auth_service.py
backend/app/services/password_reset.py
tests/integration/test_auth_endpoints.py
```

##### Read-only imports

| Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/schemas/contracts.py` | Pydantic mirrors of §1.1 shared contracts (used for response shaping) |
| S0-A | `backend/app/api/routers/__init__.py` | Router include stubs (do not modify; import only) |
| S1-A | `backend/app/db/models/user.py` | `User` ORM model |
| S1-A | `backend/app/db/models/subscription.py` | `Subscription` ORM model |
| S1-A | `backend/app/db/models/audit_log.py` | `AuditLog` ORM model |
| S1-B | `backend/app/auth/supabase_client.py` | `get_supabase_client`, `get_supabase_admin_client` |
| S1-B | `backend/app/auth/jwt_verifier.py` | `verify_jwt_token`, `decode_jwt_claims` |
| S1-B | `backend/app/auth/dependencies.py` | `get_current_user` FastAPI dependency |
| S1-B | `backend/app/auth/brute_force.py` | `check_brute_force_lockout`, `increment_brute_force_counter`, `reset_brute_force_counter` |
| S1-D | `backend/app/redis/client.py` | `get_redis_client` |
| S1-D | `backend/app/workers/queues.py` | `NOTIFICATION_QUEUE` queue name constant |
| S1-D | `backend/app/workers/base.py` | `BaseTask` Celery task base class |
| S1-E | `backend/app/analytics/posthog_client.py` | `get_posthog_client` (imported but not called in auth; present for consistent wiring pattern) |
| S0-A | `backend/app/db/session.py` | `get_db` async session dependency |

##### Do not touch

- `backend/app/main.py` — entry point, pre-stubbed by S0-A
- `backend/app/api/routers/__init__.py` — router registration, pre-stubbed by S0-A
- `backend/app/api/routers/_stubs.py` — placeholder endpoints, pre-stubbed by S0-A
- `backend/app/config.py` — environment variable config, owned by S0-A
- `backend/app/auth/middleware.py` — owned by S1-B
- `backend/app/auth/permissions.py` — owned by S1-B
- `backend/app/auth/jwt_verifier.py` — owned by S1-B
- `backend/app/auth/brute_force.py` — owned by S1-B
- `backend/app/auth/supabase_client.py` — owned by S1-B
- `backend/app/db/models/user.py` — owned by S1-A
- All `backend/app/workers/notification/` files — owned by S2-M
- All `backend/app/redis/` files — owned by S1-D
- All `backend/app/analytics/` files — owned by S1-E
- All `frontend/` files — owned by Phase 1/3 frontend sessions
- `tests/integration/test_auth_middleware.py` — owned by S1-B

##### Architecture context

The following sections from the distilled specification apply verbatim:

**From §1.4 Critical Ordering Rules:**

> **Rule 12.** "On password reset, all tokens are invalidated via Supabase Auth's `admin.signOut(userId)` call; `USER.token_invalidated_at` is simultaneously updated."

> **Rule 5.** "The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access."

> **Rule 14.** "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts." *(By analogy, all Celery task enqueues from the API layer must use the persistent Celery broker — this includes notification tasks dispatched by auth endpoints.)*

**From §1.5 HTTP Status Code Contracts:**

> | Auth logout success | `204` | `200` |
> | Password reset request success | `204` | `200` |
> | Password reset confirm success | `204` | `200` |
> | Unauthenticated request to protected endpoint | `401` | `403`, `200` |
> | Authenticated user accessing resource they do not own | `403` | `404`, `200` |

**From §1.7 Third-Party Dependencies:**

> **Supabase Auth:** JWT RS256; Google OAuth 2.0 via Supabase; `admin.signOut(userId)` API for session revocation.

> **Google OAuth 2.0:** "Account-link prompt required when OAuth email matches existing password account; never silent merge."

> **SendGrid:** "Transactional only: verification, password reset, invitations, payment notifications (day-1 and day-6 grace period emails)."

**From §1.9 Performance Targets:**

> **Brute-force lockout:** "After 5 failed attempts, 15-minute lockout — Hard constraint (security) — Redis TTL-based counter."

**From §1.2 Database Schema (relevant columns):**

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
  anonymous_id           VARCHAR,
  token_invalidated_at   TIMESTAMPTZ,
  CONSTRAINT user_email_unique UNIQUE (email)
);
```

**From §1.3 Role-Permission Matrix:**

```typescript
const ROLE_PERMISSIONS = {
  user: {
    billing_manage:          true,      // personal subscription
    gdpr_delete_account:     true,
    // ... (all other user permissions)
  },
```

New registrations default to `role = 'user'`.

**From §1.11 Cross-Session Runtime Patterns:**

> | `brute_force:{email}` | FastAPI login handler | FastAPI login handler | 15-minute TTL |

**From §1.12 Environment Variable Schema:**

> | `SUPABASE_URL` | string | HTTPS URL | None | Refuse to start | Refuse to start |
> | `SUPABASE_SERVICE_ROLE_KEY` | string | Any non-empty string | None | Refuse to start | Refuse to start |
> | `JWT_RS256_PUBLIC_KEY` | string | PEM-encoded RSA public key | None | Refuse to start | Refuse to start |

##### User stories and acceptance criteria

The following are the P0 user stories this session implements, derived from §1.13 scope definitions combined with the functional constraints in §1.4, §1.5, §1.7, and §1.9:

---

**US-001: User Registration and Email Verification**

As a new user, I want to register with my email and password so that I can access the PID Analyzer.

*AC-1 (Happy path):* Given a valid email address and a password meeting Supabase Auth's complexity requirements, when I `POST /auth/register`, then the server creates a Supabase Auth user, creates a `user` record in the application database with `email_verified = false`, `role = 'user'`, and `password_hash = NULL` (Supabase manages credentials), enqueues a `send_verification_email` task to the `notification` queue, and returns `201 Created` with a JSON body containing `access_token`, `refresh_token`, and `user` object (`id`, `email`, `display_name`, `email_verified`).

*AC-2 (Duplicate email):* Given an email address already registered in the system, when I `POST /auth/register` with that email, then the server returns `409 Conflict` with `{"error": "email_already_registered"}`. No new user record is created. No notification task is enqueued.

*AC-3 (Invalid email format):* Given a malformed email string, when I `POST /auth/register`, then the server returns `400 Bad Request` with a validation error body. No user record is created.

*AC-4 (Verification email enqueue):* The `send_verification_email` task dispatched to the `notification` queue must include `user_id` (UUID string), `email`, and `verification_url` (Supabase-generated magic link URL). The task must be dispatched **after** the user DB record is committed. If the Celery enqueue fails, the registration still returns `201` but logs the failure (email delivery is eventually-consistent, not synchronous).

*AC-5 (Email already verified cannot re-register):* A user who is already registered and has `email_verified = true` in the DB cannot re-register with the same email — returns `409 Conflict`. (Covered by AC-2; duplicate-email check does not depend on verification status.)

---

**US-002: Email/Password and Google OAuth Login with Account Linking and Brute-Force Lockout**

As a registered user, I want to log in securely so that I can access my drawings.

*AC-1 (Login happy path):* Given a registered user with correct email and password, when I `POST /auth/login`, then the server verifies credentials via Supabase Auth, resets the brute-force counter for that email, and returns `200 OK` with `{"access_token": "...", "refresh_token": "...", "user": {"id": ..., "email": ..., "display_name": ..., "email_verified": ...}}`.

*AC-2 (Wrong password — counter increment):* Given a registered user with incorrect password, when I `POST /auth/login`, then the server increments the Redis brute-force counter for that email key (`brute_force:{email}`) and returns `401 Unauthorized` with `{"error": "invalid_credentials"}`.

*AC-3 (Brute-force lockout — 5th attempt):* Given a user who has 4 consecutive failed login attempts within the 15-minute window, when I `POST /auth/login` with any credentials (correct or not), then if the counter is already at 5, the server returns `429 Too Many Requests` with `{"error": "account_locked", "retry_after_seconds": <remaining TTL>}` without performing any Supabase Auth credential check.

*AC-4 (Lockout persists until TTL expires):* Given a locked-out email, when I `POST /auth/login` with correct credentials during the 15-minute window, then the server returns `429` — it does NOT authenticate successfully until the Redis TTL expires. After expiry, a correct login returns `200`.

*AC-5 (Counter resets on successful login):* Given a user who has 3 failed attempts followed by a correct password, when I `POST /auth/login` successfully, then the brute-force counter for that email is deleted from Redis.

*AC-6 (Google OAuth — new user):* Given a valid Supabase OAuth token for a Google account whose email does not exist in the application database, when I `POST /auth/oauth/google` with `{"supabase_access_token": "...", "supabase_refresh_token": "..."}`, then the server creates a new `user` record with `role = 'user'`, `password_hash = NULL`, `email_verified = true` (Google accounts are pre-verified), enqueues no verification email, and returns `200 OK` with tokens and user object.

*AC-7 (Google OAuth — existing OAuth user):* Given a valid Supabase OAuth token for a Google account whose email already exists in the application database as an OAuth-linked user (no password), when I `POST /auth/oauth/google`, then the server finds the existing user and returns `200 OK` with tokens and user object. No new record is created.

*AC-8 (Google OAuth — account-link conflict):* Given a valid Supabase OAuth token for a Google account whose email already exists in the application database with `password_hash IS NOT NULL` (i.e., a password-based registration), when I `POST /auth/oauth/google`, then the server returns `409 Conflict` with `{"error": "account_link_required", "email": "..."}`. The accounts are **never silently merged**. No session is created.

*AC-9 (Token refresh — happy path):* Given a valid Supabase refresh token, when I `POST /auth/refresh` with `{"refresh_token": "..."}`, then the server calls Supabase Auth to exchange it for a new access token and returns `200 OK` with `{"access_token": "...", "refresh_token": "..."}`.

*AC-10 (Token refresh — expired or invalid):* Given an expired or tampered refresh token, when I `POST /auth/refresh`, then the server returns `401 Unauthorized` with `{"error": "invalid_or_expired_refresh_token"}`.

*AC-11 (Logout):* Given an authenticated user, when I `POST /auth/logout` (with a valid `Authorization: Bearer` header), then the server calls Supabase Auth to revoke the session and returns `204 No Content` with no response body. The endpoint must return `204`, never `200`.

*AC-12 (Logout — unauthenticated):* Given a request to `POST /auth/logout` with no or invalid `Authorization` header, the server returns `401 Unauthorized`.

*AC-13 (Password reset request — registered email):* Given a registered email address, when I `POST /auth/password-reset/request` with `{"email": "..."}`, then the server enqueues a `send_password_reset_email` Celery task with `user_id`, `email`, and `reset_url` (Supabase-generated password-reset magic link), and returns `204 No Content`. The response does not reveal whether the email is registered.

*AC-14 (Password reset request — unregistered email):* Given an email address not in the application database, when I `POST /auth/password-reset/request`, then the server returns `204 No Content` without enqueuing any task and without revealing whether the email exists.

*AC-15 (Password reset confirm — happy path):* Given a valid Supabase password-reset token and a new password meeting complexity requirements, when I `POST /auth/password-reset/confirm` with `{"token": "...", "new_password": "..."}`, then the server: (1) calls Supabase Auth to reset the password, (2) calls `admin.signOut(userId)` to revoke all existing sessions, (3) in the same DB transaction updates `USER.token_invalidated_at = now()`, and (4) returns `204 No Content`. Steps 2 and 3 must both complete before `204` is returned. The ordering rule from §1.4 rule 12 applies: `admin.signOut` before DB commit is acceptable; DB commit must not precede `admin.signOut`.

*AC-16 (Password reset confirm — invalid token):* Given an expired or invalid password-reset token, when I `POST /auth/password-reset/confirm`, then the server returns `400 Bad Request` with `{"error": "invalid_or_expired_reset_token"}`. No session invalidation occurs.

*AC-17 (Password reset confirm — post-reset tokens rejected):* Given a JWT issued before a successful password reset confirm, when that JWT is used on a subsequent authenticated request, the `token_invalidated_at` middleware check (owned by S1-B) rejects it with `401`. This session is responsible for correctly setting `token_invalidated_at` so that S1-B's middleware can enforce this; the middleware behavior itself is tested in S1-B.

*AC-18 (Deleted user cannot log in):* Given a user with `deleted_at IS NOT NULL`, when I `POST /auth/login`, the server returns `401 Unauthorized` with `{"error": "account_not_found"}` after verifying credentials fail against Supabase (Supabase Auth account is also deactivated on deletion — handled by S2-F; this session must check `deleted_at` on the DB record after Supabase auth succeeds and return `401` if set).

##### UX and design specification

N/A — this is a backend-only session. The auth page UI is owned by S3-A. This session provides the JSON API that S3-A calls.

##### Critical implementation notes

- **"On password reset, all tokens are invalidated via Supabase Auth's `admin.signOut(userId)` call; `USER.token_invalidated_at` is simultaneously updated."** (§1.4 rule 12) — In practice: call `admin.signOut(userId)` first (Supabase external call), then immediately update `token_invalidated_at` in the same DB write. If Supabase signOut succeeds but the DB write fails, the endpoint must retry the DB write (do not return 204 until DB is committed). If Supabase signOut fails, the endpoint must return 500 — do not update `token_invalidated_at` and do not return 204.

- **Brute-force counter at 5 (not after 5).** The lockout activates when `counter >= 5`. The 5th failed attempt increments the counter to 5 AND sets the 15-minute TTL. All subsequent attempts within the TTL window return 429 without checking credentials. Use `brute_force.check_brute_force_lockout` from S1-B before any Supabase credential check.

- **HTTP status code for lockout is `429`, not `401`.** The spec states "15-minute lockout" as a hard constraint; returning 401 for a locked account silently hides the lockout from the client. The `retry_after_seconds` field in the 429 response body is the remaining Redis TTL for the `brute_force:{email}` key.

- **`POST /auth/logout` must return `204`, never `200`.** From §1.5: "Auth logout success — `204` — Must never return `200`."

- **`POST /auth/password-reset/request` and `/confirm` must return `204`, never `200`.** From §1.5.

- **Account-link detection in `POST /auth/oauth/google`:** After verifying the Supabase OAuth token and extracting the email, query the `user` table for `WHERE email = :email AND password_hash IS NOT NULL AND deleted_at IS NULL`. If found: return `409 Conflict` with `{"error": "account_link_required", "email": "<email>"}`. Do NOT call `admin.signOut`. Do NOT create any DB record. Per §1.7: "never silent merge."

- **`POST /auth/password-reset/request` must always return `204`.** Do not differentiate response between registered and unregistered emails — this prevents email enumeration attacks. The Celery task is only enqueued if `user.email` exists in the DB; the response is 204 either way.

- **User `role` on registration:** Always set to `'user'`. Never accept `role` from the request body.

- **`email_verified` on OAuth registration:** Set to `true` for Google OAuth users (Google guarantees verified email). Set to `false` for email/password registrations.

- **`password_hash` column:** This column is `NULL` in our DB for all users — Supabase Auth manages the actual password hash. Our `password_hash` column serves as a **flag** indicating whether the user has a password-based registration (non-NULL means "user registered with password"). On `POST /auth/register`, set `password_hash = '<SUPABASE_MANAGED>'` (a sentinel value, not the actual hash) to mark the account as password-based for the account-link detection query. On OAuth registration, leave `password_hash = NULL`.

- **Free-tier subscription creation on registration:** When creating a new user on `POST /auth/register` or first OAuth login, also create a `subscription` record with `tier_id = 'free'`, `billing_state = 'Active'`, and `user_id` set. This is inside the same DB transaction as the `user` insert.

- **Notification task enqueue failure must not fail registration.** If the Celery broker is unreachable when enqueuing `send_verification_email`, catch the exception, log it at ERROR level, and return `201` anyway. Email delivery is eventual-consistency.

- **`POST /auth/oauth/google` request body:** `{"supabase_access_token": string, "supabase_refresh_token": string}`. Verify the `supabase_access_token` using `jwt_verifier.verify_jwt_token` (S1-B) before any DB operation. On invalid token: return `401`.

- **Audit log on security-relevant events:** Write to `audit_log` for: successful login (`action_type='login_success'`), failed login (`action_type='login_failed'`), lockout triggered (`action_type='login_locked'`), password reset confirmed (`action_type='password_reset_confirmed'`), logout (`action_type='logout'`). These writes are best-effort (do not fail the request if the audit write fails).

- **`deleted_at` check after Supabase auth on login:** Supabase may still authenticate a "soft-deleted" user (our `deleted_at` column is application-level, not Supabase-level). After a successful Supabase credential check, always query the DB for `deleted_at IS NULL` before issuing tokens.

- **`POST /auth/refresh` does not touch brute-force counters.** Refresh is a separate flow from password login.

- **Cross-session contract with S2-M (notification worker):** The `send_verification_email` and `send_password_reset_email` task payloads defined in this session are **load-bearing** — S2-M must consume exactly these shapes. See Mocking contract section for canonical shapes.

##### Mocking contract

This is a backend session. The following internal Celery task payloads are dispatched by this session and consumed by S2-M (Notification Worker). These shapes are **cross-session contracts**:

**`send_verification_email` task** — dispatched to `NOTIFICATION_QUEUE` on successful registration:
```python
{
    "task_name": "send_verification_email",
    "user_id": str,           # UUID string, e.g. "550e8400-e29b-41d4-a716-446655440000"
    "email": str,             # e.g. "user@example.com"
    "display_name": str,      # e.g. "Jane Smith"
    "verification_url": str   # Supabase-generated magic link, e.g. "https://auth.example.com/verify?token=..."
}
```

**`send_password_reset_email` task** — dispatched to `NOTIFICATION_QUEUE` on `POST /auth/password-reset/request` when email is registered:
```python
{
    "task_name": "send_password_reset_email",
    "user_id": str,           # UUID string
    "email": str,
    "display_name": str,
    "reset_url": str          # Supabase-generated password reset link
}
```

**External service mocks for tests:**

| Mock Target | Mock Method | Behavior |
|---|---|---|
| `supabase_client.auth.sign_up()` | `AsyncMock` | Returns `{"user": {"id": "<uuid>", "email": "<email>"}, "session": {"access_token": "mock_access", "refresh_token": "mock_refresh"}}` on success; raises `AuthApiError` for duplicate email |
| `supabase_client.auth.sign_in_with_password()` | `AsyncMock` | Returns session on correct creds; raises `AuthApiError("Invalid login credentials")` on wrong password |
| `supabase_admin_client.auth.admin.sign_out()` | `AsyncMock` | Returns `{}` on success; raises `Exception("Supabase signout failed")` for failure test case |
| `supabase_client.auth.refresh_session()` | `AsyncMock` | Returns new session on valid token; raises `AuthApiError` on expired token |
| `supabase_client.auth.sign_out()` | `AsyncMock` | Returns `{}` always |
| `supabase_admin_client.auth.admin.generate_link()` | `AsyncMock` | Returns `{"action_link": "https://auth.example.com/verify?token=mock_token"}` |
| Celery `send_verification_email.apply_async()` | `MagicMock` | Captures call args; does not send actual task |
| Celery `send_password_reset_email.apply_async()` | `MagicMock` | Captures call args; does not send actual task |

**`jwt_verifier.verify_jwt_token` mock for OAuth tests:**
```python
# For valid OAuth token:
{"sub": "<supabase_user_id>", "email": "user@example.com", "email_confirmed_at": "2024-01-01T00:00:00Z", "app_metadata": {"provider": "google"}}
# For invalid token: raises JWTVerificationError
```

##### Acceptance criteria checklist

- [ ] `POST /auth/register` with valid email + password returns `201 Created` with `access_token`, `refresh_token`, `user.id`, `user.email`, `user.display_name`, `user.email_verified=false` [US-001 AC-1]
- [ ] `POST /auth/register` creates a `user` row in the DB with `email_verified=false`, `role='user'`, `deleted_at=NULL` [US-001 AC-1]
- [ ] `POST /auth/register` creates a `subscription` row with `tier_id='free'`, `billing_state='Active'` in the same transaction as the user insert [US-001 AC-1]
- [ ] `POST /auth/register` enqueues a `send_verification_email` Celery task with correct `user_id`, `email`, `display_name`, `verification_url` to `NOTIFICATION_QUEUE` [US-001 AC-4]
- [ ] `POST /auth/register` with duplicate email returns `409 Conflict` with `{"error": "email_already_registered"}` [US-001 AC-2]
- [ ] `POST /auth/register` with duplicate email does NOT enqueue any notification task [US-001 AC-2]
- [ ] `POST /auth/register` with malformed email returns `400 Bad Request` [US-001 AC-3]
- [ ] `POST /auth/register` with Celery broker unreachable still returns `201` (notification failure is non-fatal) [US-001 AC-4]
- [ ] `POST /auth/login` with valid credentials returns `200 OK` with `access_token`, `refresh_token`, and `user` object [US-002 AC-1]
- [ ] `POST /auth/login` success resets the brute-force counter for that email in Redis [US-002 AC-5]
- [ ] `POST /auth/login` with wrong password returns `401 Unauthorized` with `{"error": "invalid_credentials"}` [US-002 AC-2]
- [ ] `POST /auth/login` with wrong password increments the Redis brute-force counter for `brute_force:{email}` [US-002 AC-2]
- [ ] `POST /auth/login` when brute-force counter is >= 5 returns `429 Too Many Requests` with `{"error": "account_locked", "retry_after_seconds": <N>}` regardless of password correctness [US-002 AC-3]
- [ ] `POST /auth/login` when brute-force counter is >= 5 does NOT call Supabase Auth credential check [US-002 AC-3]
- [ ] `POST /auth/login` with correct credentials during lockout window returns `429`, not `200` [US-002 AC-4]
- [ ] `POST /auth/login` with `deleted_at IS NOT NULL` returns `401` with `{"error": "account_not_found"}` even after Supabase credential check succeeds [US-002 AC-18]
- [ ] `POST /auth/oauth/google` with valid token for new email creates user with `email_verified=true`, `password_hash=NULL`, returns `200 OK` with tokens [US-002 AC-6]
- [ ] `POST /auth/oauth/google` with valid token for existing OAuth user returns `200 OK` and finds existing user (no duplicate created) [US-002 AC-7]
- [ ] `POST /auth/oauth/google` when email matches existing password-based user (`password_hash IS NOT NULL`) returns `409 Conflict` with `{"error": "account_link_required", "email": "..."}` [US-002 AC-8]
- [ ] `POST /auth/oauth/google` account-link conflict does NOT create a new user record and does NOT create a session [US-002 AC-8]
- [ ] `POST /auth/oauth/google` with invalid/expired Supabase token returns `401 Unauthorized` [US-002 AC-8, technical]
- [ ] `POST /auth/refresh` with valid refresh token returns `200 OK` with new `access_token` and `refresh_token` [US-002 AC-9]
- [ ] `POST /auth/refresh` with expired/invalid token returns `401 Unauthorized` with `{"error": "invalid_or_expired_refresh_token"}` [US-002 AC-10]
- [ ] `POST /auth/logout` with valid auth header returns `204 No Content` with no response body [US-002 AC-11]
- [ ] `POST /auth/logout` return code is exactly `204`, never `200` [US-002 AC-11]
- [ ] `POST /auth/logout` without valid auth header returns `401 Unauthorized` [US-002 AC-12]
- [ ] `POST /auth/password-reset/request` with registered email returns `204 No Content` [US-002 AC-13]
- [ ] `POST /auth/password-reset/request` with registered email enqueues `send_password_reset_email` task with correct payload [US-002 AC-13]
- [ ] `POST /auth/password-reset/request` with unregistered email returns `204 No Content` [US-002 AC-14]
- [ ] `POST /auth/password-reset/request` with unregistered email does NOT enqueue any notification task [US-002 AC-14]
- [ ] `POST /auth/password-reset/request` response is identical for registered and unregistered emails (no enumeration) [US-002 AC-14]
- [ ] `POST /auth/password-reset/confirm` with valid token calls `admin.signOut(userId)` before updating `token_invalidated_at` in DB [US-002 AC-15]
- [ ] `POST /auth/password-reset/confirm` with valid token updates `USER.token_invalidated_at` to current UTC timestamp [US-002 AC-15]
- [ ] `POST /auth/password-reset/confirm` with valid token returns `204 No Content` [US-002 AC-15]
- [ ] `POST /auth/password-reset/confirm` does NOT return `204` if `admin.signOut` fails [US-002 AC-15]
- [ ] `POST /auth/password-reset/confirm` does NOT update `token_invalidated_at` if `admin.signOut` fails [US-002 AC-15]
- [ ] `POST /auth/password-reset/confirm` with invalid/expired token returns `400 Bad Request` with `{"error": "invalid_or_expired_reset_token"}` [US-002 AC-16]
- [ ] `POST /auth/password-reset/confirm` with invalid token does NOT call `admin.signOut` and does NOT update `token_invalidated_at` [US-002 AC-16]
- [ ] `token_invalidated_at` is set to a timestamp equal to or after the `admin.signOut` call time [US-002 AC-17, technical atomicity]
- [ ] Free-tier `subscription` row is created in the same DB transaction as the `user` row on registration [US-001 AC-1, technical atomicity]
- [ ] All six endpoints (`register`, `login`, `oauth/google`, `refresh`, `logout`, `password-reset/request`, `password-reset/confirm`) are registered under the `/auth` prefix [technical]
- [ ] `POST /auth/password-reset/request` return code is exactly `204` [§1.5]
- [ ] `POST /auth/password-reset/confirm` return code is exactly `204` [§1.5]

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation): `tests/integration/test_auth_endpoints.py`

**Exact CI command**: `pytest tests/integration/test_auth_endpoints.py -v`

**AC → assertion mapping:**

| AC | `it(...)` / `test(...)` block name |
|---|---|
| US-001 AC-1 (registration happy path, 201) | `test_register_success_returns_201_with_tokens` |
| US-001 AC-1 (user DB row created) | `test_register_creates_user_in_db` |
| US-001 AC-1 (subscription row created atomically) | `test_register_creates_free_subscription` |
| US-001 AC-4 (verification email enqueued) | `test_register_enqueues_verification_email` |
| US-001 AC-2 (duplicate email → 409) | `test_register_duplicate_email_returns_409` |
| US-001 AC-2 (no task on duplicate) | `test_register_duplicate_email_no_task_enqueued` |
| US-001 AC-3 (invalid email → 400) | `test_register_invalid_email_returns_400` |
| US-001 AC-4 (notification failure non-fatal) | `test_register_succeeds_when_celery_broker_unavailable` |
| US-002 AC-1 (login happy path) | `test_login_success_returns_200_with_tokens` |
| US-002 AC-5 (counter reset on success) | `test_login_success_resets_brute_force_counter` |
| US-002 AC-2 (wrong password → 401) | `test_login_wrong_password_returns_401` |
| US-002 AC-2 (counter increment) | `test_login_wrong_password_increments_counter` |
| US-002 AC-3 (lockout at count >= 5) | `test_login_locked_after_5_failures_returns_429` |
| US-002 AC-3 (no Supabase call when locked) | `test_login_locked_skips_supabase_check` |
| US-002 AC-4 (correct creds still 429 during lockout) | `test_login_correct_creds_returns_429_during_lockout` |
| US-002 AC-18 (deleted user → 401) | `test_login_deleted_user_returns_401` |
| US-002 AC-6 (OAuth new user → 200, email_verified=true) | `test_oauth_google_new_user_returns_200` |
| US-002 AC-7 (OAuth existing OAuth user → 200) | `test_oauth_google_existing_oauth_user_returns_200` |
| US-002 AC-8 (OAuth account-link conflict → 409) | `test_oauth_google_password_account_conflict_returns_409` |
| US-002 AC-8 (no record created on conflict) | `test_oauth_google_conflict_no_user_created` |
| US-002 AC-8 (invalid OAuth token → 401) | `test_oauth_google_invalid_token_returns_401` |
| US-002 AC-9 (refresh happy path) | `test_refresh_valid_token_returns_200` |
| US-002 AC-10 (refresh expired → 401) | `test_refresh_expired_token_returns_401` |
| US-002 AC-11 (logout → 204) | `test_logout_returns_204` |
| US-002 AC-11 (logout status code exactly 204) | `test_logout_status_code_is_204_not_200` |
| US-002 AC-12 (logout no auth → 401) | `test_logout_unauthenticated_returns_401` |
| US-002 AC-13 (reset request registered → 204) | `test_password_reset_request_registered_email_returns_204` |
| US-002 AC-13 (reset request enqueues task) | `test_password_reset_request_enqueues_task` |
| US-002 AC-14 (reset request unregistered → 204) | `test_password_reset_request_unregistered_email_returns_204` |
| US-002 AC-14 (no task for unregistered) | `test_password_reset_request_unregistered_no_task` |
| US-002 AC-14 (no enumeration) | `test_password_reset_request_response_identical_for_known_and_unknown` |
| US-002 AC-15 (confirm happy path → 204) | `test_password_reset_confirm_valid_token_returns_204` |
| US-002 AC-15 (admin.signOut called before DB update) | `test_password_reset_confirm_signout_before_db_update` |
| US-002 AC-15 (token_invalidated_at updated) | `test_password_reset_confirm_updates_token_invalidated_at` |
| US-002 AC-15 (no 204 if signOut fails) | `test_password_reset_confirm_returns_500_if_signout_fails` |
| US-002 AC-15 (no DB update if signOut fails) | `test_password_reset_confirm_no_db_update_if_signout_fails` |
| US-002 AC-16 (confirm invalid token → 400) | `test_password_reset_confirm_invalid_token_returns_400` |
| US-002 AC-16 (no signOut on invalid token) | `test_password_reset_confirm_invalid_token_no_signout` |
| technical (token_invalidated_at >= signOut call time) | `test_password_reset_confirm_token_invalidated_at_is_after_signout` |
| technical (subscription atomicity) | `test_register_subscription_rolled_back_if_user_insert_fails` |
| §1.5 (password-reset/request code is 204) | `test_password_reset_request_status_code_is_204_not_200` |
| §1.5 (password-reset/confirm code is 204) | `test_password_reset_confirm_status_code_is_204_not_200` |

**Fixtures / test doubles:**

| Fixture / Mock | Purpose | Source |
|---|---|---|
| `db_session` | Async SQLAlchemy session backed by test PostgreSQL | S0-B `tests/integration/fixtures/db.py` |
| `redis_client` | In-process Redis (fakeredis or test Redis container) | S0-B `tests/integration/fixtures/redis.py` |
| `test_client` | FastAPI `AsyncClient` from `httpx` | Pytest fixture wrapping `app` from S0-A `main.py` |
| `mock_supabase_client` | `unittest.mock.AsyncMock` patching `get_supabase_client` | Local fixture in test file |
| `mock_supabase_admin_client` | `unittest.mock.AsyncMock` patching `get_supabase_admin_client` | Local fixture in test file |
| `mock_celery_notification_task` | `unittest.mock.MagicMock` patching `apply_async` on notification tasks | Local fixture in test file |
| `seeded_user_password` | DB row: `user` with `email='test@example.com'`, `password_hash='<SUPABASE_MANAGED>'`, `email_verified=true`, `deleted_at=NULL` | Local factory in test file |
| `seeded_user_oauth` | DB row: `user` with `email='oauth@example.com'`, `password_hash=NULL`, `email_verified=true` | Local factory in test file |
| `seeded_user_deleted` | DB row: `user` with `deleted_at=now()` | Local factory in test file |
| `brute_force_at_4` | Pre-seeded Redis key `brute_force:test@example.com` = 4, TTL 900s | Local fixture |
| `brute_force_at_5` | Pre-seeded Redis key `brute_force:test@example.com` = 5, TTL 850s | Local fixture |
| `tier_free_seed` | `tier` row with `id='free'` (required FK for subscription creation) | S1-A `seed_tiers.py` run in conftest |

**Pre-conditions:**

1. PostgreSQL test database running with all migrations applied (S1-A `0001_initial_schema.py`, `0002_rls_policies.py`, `0003_audit_partitions.py`)
2. `tier` table seeded with `free` row (S1-A `seed_tiers.py`)
3. `entity_class` table seeded (S1-A `seed_entity_classes.py`) — needed for FK integrity even though not used here
4. Redis test instance running (fakeredis or containerized via S0-B fixtures)
5. Environment variables: `DATABASE_URL`, `REDIS_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_RS256_PUBLIC_KEY`, `HMAC_SERVER_SECRET` — set to test values via pytest `monkeypatch` or `.env.test`
6. All Supabase Auth calls mocked — no live Supabase service required for test suite to pass

**Isolation rule:** This test file patches all Supabase Auth calls and all Celery task dispatches. It only requires a live PostgreSQL test database and Redis. Both are provided by S0-B fixtures. No sibling Phase 2 session (S2-B through S2-M) needs to have merged for these tests to pass. ✅

##### Checkpoint

- **One-sentence observable outcome:** `POST /auth/register` creates a user and free subscription in the database, `POST /auth/login` with the registered credentials returns a JWT, and `POST /auth/logout` returns `204 No Content` — all verifiable against the running API without any other Phase 2 session merged.
- **Shippability claim:** This PR is independently mergeable to main even if no other session in the same wave has merged. All Supabase and Celery dependencies are mocked in tests; no S2-B through S2-M code is imported or required.

##### Output and handoff

| Export | Kind | Consuming Sessions | Load-Bearing? |
|---|---|---|---|
| `POST /auth/register` response shape `{"access_token": str, "refresh_token": str, "user": {"id": str, "email": str, "display_name": str, "email_verified": bool}}` | HTTP contract | S3-A (Frontend Auth Pages) | [LOAD-BEARING] |
| `POST /auth/login` response shape (same as register) | HTTP contract | S3-A | [LOAD-BEARING] |
| `POST /auth/oauth/google` 409 shape `{"error": "account_link_required", "email": str}` | HTTP contract | S3-A (AccountLinkPrompt.tsx) | [LOAD-BEARING] |
| `POST /auth/logout` → `204` | HTTP contract | S3-A | [LOAD-BEARING] |
| `POST /auth/password-reset/request` → `204` | HTTP contract | S3-A | [LOAD-BEARING] |
| `POST /auth/password-reset/confirm` → `204` | HTTP contract | S3-A | [LOAD-BEARING] |
| `send_verification_email` Celery task payload shape | Queue contract | S2-M (Notification Worker) | [LOAD-BEARING] |
| `send_password_reset_email` Celery task payload shape | Queue contract | S2-M (Notification Worker) | [LOAD-BEARING] |
| `user.token_invalidated_at` set correctly on password reset confirm | DB column contract | S1-B middleware (`token_invalidated_at` check) | [LOAD-BEARING] |
| `user.password_hash = '<SUPABASE_MANAGED>'` sentinel for password-account detection | DB convention | S2-F (account service, for GDPR soft-delete) | [LOAD-BEARING] |
| `backend/app/services/auth_service.py` — `AuthService` class | Python module | S2-F (`account_service.py` may import for account deletion flow) | — |
| `backend/app/api/routers/auth.py` — `router` FastAPI `APIRouter` | Python module | S0-A `routers/__init__.py` (already has include stub) | — |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/test_auth_endpoints.py -v",
    "file": "tests/integration/test_auth_endpoints.py"
  },
  "checkpoint": "POST /auth/register creates a user and free subscription in the database, POST /auth/login with valid credentials returns a JWT access token, and POST /auth/logout returns 204 No Content — all verifiable against the running API without any other Phase 2 session merged.",
  "manualAcs": [],
  "exports": [
    {
      "kind": "module",
      "name": "backend/app/api/routers/auth",
      "shape": "backend/app/api/routers/auth.py"
    },
    {
      "kind": "module",
      "name": "backend/app/services/auth_service",
      "shape": "backend/app/services/auth_service.py"
    },
    {
      "kind": "module",
      "name": "backend/app/services/password_reset",
      "shape": "backend/app/services/password_reset.py"
    },
    {
      "kind": "type",
      "name": "RegisterRequest",
      "shape": "{ email: string; password: string; display_name: string }"
    },
    {
      "kind": "type",
      "name": "LoginRequest",
      "shape": "{ email: string; password: string }"
    },
    {
      "kind": "type",
      "name": "OAuthGoogleRequest",
      "shape": "{ supabase_access_token: string; supabase_refresh_token: string }"
    },
    {
      "kind": "type",
      "name": "AuthResponse",
      "shape": "{ access_token: string; refresh_token: string; user: { id: string; email: string; display_name: string; email_verified: boolean } }"
    },
    {
      "kind": "type",
      "name": "SendVerificationEmailTaskPayload",
      "shape": "{ task_name: 'send_verification_email'; user_id: string; email: string; display_name: string; verification_url: string }"
    },
    {
      "kind": "type",
      "name": "SendPasswordResetEmailTaskPayload",
      "shape": "{ task_name: 'send_password_reset_email'; user_id: string; email: string; display_name: string; reset_url: string }"
    }
  ]
}
```