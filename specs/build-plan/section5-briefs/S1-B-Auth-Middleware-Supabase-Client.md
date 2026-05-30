---

#### S1-B — Auth Middleware & Supabase Client

**Phase 1 | Auth/Contracts | Needs: S0-A, S0-B**

##### Objective

Provide JWT verification, Supabase Auth client wrapper, FastAPI auth middleware/dependencies, role-permission matrix, and Redis-backed brute-force lockout — the security primitives every Phase 2 API endpoint will depend on.

##### Scope

P0 MVP. All work in this session is P0. The role matrix includes `team_member` and `team_admin` entries (consumed by P1 sessions); these are implemented fully because the matrix is a single static constant and stubbing it would create silent regressions.

##### Technology constraints

- **Supabase Auth (self-hosted)** — JWT RS256 verification using `JWT_RS256_PUBLIC_KEY`. Session revocation must use Supabase `admin.signOut(userId)`.
- **PyJWT** (or equivalent) for RS256 verification — must verify signature, `exp`, `iss`, `aud`.
- **Redis** (from S1-D contract — but S1-D is parallel; this session must talk to Redis directly via `redis.asyncio` using `REDIS_URL` and not import from `backend/app/redis/`). Brute-force keys use pattern `brute_force:{email}` with 15-minute TTL.
- **FastAPI** dependency injection for `get_current_user` / `require_role`.
- **MUST NOT** use Auth0, custom JWT signing, or any HS256 path — RS256 only (irreversible per §1.8).
- **MUST NOT** look up users via DB on every request for the hot path beyond a single indexed query on `user.id`; `token_invalidated_at` check is mandatory and non-cacheable.

##### Performance targets

None directly owned. Middleware overhead must remain well under the dashboard <2s P95 and canvas-interaction <200ms P95 budgets owned downstream. Monitoring target only.

##### Owned files

- `backend/app/auth/__init__.py`
- `backend/app/auth/supabase_client.py`
- `backend/app/auth/jwt_verifier.py`
- `backend/app/auth/middleware.py`
- `backend/app/auth/dependencies.py`
- `backend/app/auth/permissions.py`
- `backend/app/auth/brute_force.py`
- `tests/integration/test_auth_middleware.py`

##### Read-only imports

- From **S0-A**:
  - `backend/app/config.py` — settings object exposing `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_RS256_PUBLIC_KEY`, `REDIS_URL`, `ENVIRONMENT`.
  - `backend/app/schemas/contracts.py` — `UserRole` type alias matching `'user' | 'team_member' | 'team_admin'`.
  - `backend/app/db/session.py` — async session factory `get_db()` (for `token_invalidated_at` lookup).
- From **S0-B**:
  - `tests/integration/conftest.py` — pytest fixtures (`db`, `redis`, `app_client`).
  - `tests/integration/fixtures/redis.py` — `redis_client` fixture.

##### Do not touch

- `backend/app/main.py`, `backend/app/api/routers/__init__.py`, `backend/app/api/routers/_stubs.py` (entry/router files — scaffold-owned).
- `backend/app/db/models/user.py` and all other model files (owned by S1-A — parallel session). This session must access `USER.token_invalidated_at` via raw SQL on `"user"` table, NOT via importing the SQLAlchemy model, since S1-A is a parallel sibling that may not have merged yet.
- Any file under `backend/app/redis/` (owned by S1-D — parallel). Use `redis.asyncio.from_url(settings.REDIS_URL)` directly.
- Any file under `backend/app/analytics/` (owned by S1-E).
- All Phase 2 router/service files.

##### Architecture context

From §1.3 — Role-Permission Matrix (verbatim):

```typescript
const ROLE_PERMISSIONS = {
  user: {
    drawing_upload:          true,
    drawing_view:            'own',
    drawing_delete:          'own',
    drawing_retry:           'own',
    symbol_correct:          'own',
    export_initiate:         'own',
    team_manage:             false,
    billing_manage:          true,
    gdpr_delete_account:     true,
  },
  team_member: {
    drawing_upload:          true,
    drawing_view:            'team',
    drawing_delete:          false,
    drawing_retry:           'team',
    symbol_correct:          'team',
    export_initiate:         'team',
    team_manage:             false,
    billing_manage:          false,
    gdpr_delete_account:     true,
  },
  team_admin: {
    drawing_upload:          true,
    drawing_view:            'team',
    drawing_delete:          'team',
    drawing_retry:           'team',
    symbol_correct:          'team',
    export_initiate:         'team',
    team_manage:             true,
    billing_manage:          true,
    gdpr_delete_account:     true,
  },
} as const;
```

From §1.4 Critical Ordering Rules:

> **#12.** "On password reset, all tokens are invalidated via Supabase Auth's `admin.signOut(userId)` call; `USER.token_invalidated_at` is simultaneously updated."

From §1.7 Third-Party Dependencies:

> **Supabase Auth** — JWT RS256; Google OAuth 2.0 via Supabase; `admin.signOut(userId)` API for session revocation.
> **Google OAuth 2.0** — Account-link prompt required when OAuth email matches existing password account; never silent merge.

From §1.9 Performance Targets:

> Brute-force lockout — After 5 failed attempts, 15-minute lockout — Hard constraint (security) — Redis TTL-based counter.

From §1.11 Cross-Session Runtime Patterns:

| Key Pattern | Written By | Read By | TTL |
|---|---|---|---|
| `subscription:flags:{user_id}` | FastAPI on login / Stripe webhook handler | FastAPI middleware (every authenticated request, feature-gate evaluation) | 5 minutes; invalidated on webhook receipt |
| `brute_force:{email}` | FastAPI login handler | FastAPI login handler | 15-minute TTL |

From §1.5 HTTP Status Code Contracts:

| Condition | Required code |
|---|---|
| Unauthenticated request to protected endpoint | `401` |
| Authenticated user accessing resource they do not own | `403` |

##### User stories and acceptance criteria

This session implements no end-user UI. It provides the security primitives that the following P0 stories depend on (US-001 registration, US-002 login + brute force + account link, US-005 GDPR/password reset session invalidation, US-008/009/013/016/018 ownership checks, US-023 team roles). Verbatim ACs that this session's code must satisfy when called by Phase 2:

- **US-002 AC (brute force):** After 5 failed login attempts for the same email, the account is locked for 15 minutes. Subsequent attempts during the lockout window return a lockout response without verifying credentials.
- **US-002 AC (account link, never silent merge):** When a Google OAuth email matches an existing password account, the system must prompt for account linking; it must never silently merge.
- **US-005 AC (password reset invalidates sessions):** Password reset invalidates all existing sessions via `admin.signOut(userId)` and updates `USER.token_invalidated_at`; tokens issued before `token_invalidated_at` must be rejected with `401`.
- **Permission ACs** (derived from §1.3): every cross-tenant access attempt must return `403`; unauthenticated requests to protected routes must return `401`.

##### UX and design specification

N/A — backend security primitives session, no frontend component.

##### Critical implementation notes

- **RS256 only.** Verify `alg=RS256`, `iss=SUPABASE_URL`, signature, and `exp`. Reject any token with `alg=none` or HS256.
- **`token_invalidated_at` check is mandatory on every authenticated request.** Per Critical Ordering Rule #12, if `USER.token_invalidated_at` is non-null AND `iat < token_invalidated_at`, return `401`. There is no cache exemption — the check must fire on every request.
- **Brute force counter increments on failed login only, not success.** Key is `brute_force:{email_lowercased}`. Increment with `INCR`; on first increment set `EXPIRE` to 900s. At count `>= 5` reject with lockout response WITHOUT calling Supabase. Lockout window does not reset on additional failed attempts (TTL preserved).
- **Brute force key MUST NOT be cleared on successful login** unless count is still below threshold — if locked out, the lockout stands until TTL expires. (Clear on threshold-not-reached success is acceptable and recommended.)
- **HTTP status contract:** unauthenticated → `401`; authenticated-but-forbidden → `403`. Never `404` for ownership failures (information leak avoidance is not required by spec; explicit `403` is required).
- **Ownership helpers must support both `owner_user_id` and `owner_team_id`.** A drawing owned by team T is accessible to all users where `user.team_id = T`, scoped by role (`team_member` and `team_admin` both have `drawing_view='team'`; only `team_admin` has `drawing_delete='team'`; `team_member` has `drawing_delete=false`).
- **Direct Redis client construction.** Since S1-D is parallel, do not import `backend/app/redis/`. Instantiate `redis.asyncio.Redis.from_url(settings.REDIS_URL)` in this module. S1-D's parallel client coexists peacefully.
- **Direct SQL for `token_invalidated_at`.** Use `text("SELECT token_invalidated_at, deleted_at, team_id, role FROM \"user\" WHERE id = :id")` rather than importing the User model — S1-A is parallel.
- **Supabase admin client.** `supabase_client.py` exposes `admin_sign_out(user_id: UUID) -> None` which calls Supabase Admin API `POST {SUPABASE_URL}/auth/v1/admin/users/{user_id}/logout` with `Authorization: Bearer {SUPABASE_SERVICE_ROLE_KEY}` header. This is the only sanctioned session-revocation path.
- **Silent failure mode to avoid:** if `JWT_RS256_PUBLIC_KEY` is missing or malformed, fail fast at app startup (config layer already enforces). Never default to skipping signature verification in development — both `development` and `production` must verify.
- **Account-link prompt is implemented in S2-A, but `supabase_client.py` must expose `find_user_by_email(email)` for that flow.** Never auto-merge identities in this session.
- **Soft-deleted users (`deleted_at IS NOT NULL`) must be rejected with `401`** by middleware, identical to invalid token.

##### Mocking contract

This session consumes:

- **Redis** (external service spun up in integration fixtures from S0-B): `INCR`, `EXPIRE`, `TTL`, `GET`, `DEL` against keys `brute_force:{email}`. Real Redis in tests.
- **PostgreSQL `"user"` table** (real DB from S0-B fixtures). For tests in this session, the test creates the `"user"` table inline via raw `CREATE TABLE` because S1-A's migrations may not be present in the test transaction. Columns required for tests: `id UUID PRIMARY KEY`, `email VARCHAR`, `role VARCHAR`, `team_id UUID NULL`, `deleted_at TIMESTAMPTZ NULL`, `token_invalidated_at TIMESTAMPTZ NULL`.
- **Supabase Admin API** (external HTTP): mocked via `respx` or `httpx.MockTransport` in tests. Mock response for `POST /auth/v1/admin/users/{id}/logout` → `204`. Mock for `GET /auth/v1/admin/users?email=...` → `{"users": [{"id": "...", "email": "..."}]}` or `{"users": []}`.
- **JWT signing for tests:** generate ephemeral RS256 keypair in the test fixture and inject the public key into settings; sign test tokens with the private key.

##### Acceptance criteria checklist

- [ ] Valid RS256 JWT with active user yields `request.state.user` populated with `id`, `email`, `role`, `team_id` [US-002 AC]
- [ ] Missing `Authorization` header on protected dependency returns `401` [§1.5]
- [ ] Malformed JWT returns `401` [§1.5]
- [ ] JWT with `alg=none` is rejected with `401` [§1.5]
- [ ] JWT with `alg=HS256` is rejected with `401` [§1.5]
- [ ] Expired JWT (`exp` in past) returns `401` [§1.5]
- [ ] JWT with wrong `iss` returns `401` [§1.5]
- [ ] JWT with `iat` earlier than `USER.token_invalidated_at` returns `401` [US-005, Rule #12]
- [ ] User with `deleted_at IS NOT NULL` returns `401` even with otherwise-valid token [US-005]
- [ ] Cross-tenant access (user accesses another user's resource via `require_owner`) returns `403` [§1.5]
- [ ] `team_member` denied `drawing_delete` permission check returns `403` [§1.3]
- [ ] `team_admin` granted `drawing_delete` permission for team drawing succeeds [§1.3]
- [ ] `team_member` granted `drawing_view` for fellow team's drawing succeeds [§1.3]
- [ ] `user` role denied `team_manage` returns `403` [§1.3]
- [ ] Brute-force counter increments on each failed login; 6th attempt within 15min is rejected without credential check [US-002, §1.9]
- [ ] Brute-force lockout TTL is 900 seconds and is set on first failure [§1.9, §1.11]
- [ ] Brute-force key is `brute_force:{email}` with email lowercased [§1.11]
- [ ] Successful login below threshold clears the brute-force counter [US-002]
- [ ] `supabase_client.admin_sign_out(user_id)` issues `POST {SUPABASE_URL}/auth/v1/admin/users/{id}/logout` with service-role bearer token [Rule #12]
- [ ] `supabase_client.find_user_by_email(email)` returns existing user record or `None` (used by S2-A account-link flow; never auto-merges) [US-002, §1.7]
- [ ] Permissions module exports `ROLE_PERMISSIONS` matching §1.3 byte-for-byte [§1.3]
- [ ] [MANUAL] Public-key rotation: rotating `JWT_RS256_PUBLIC_KEY` in production env invalidates previously issued tokens without code change [US-005]

##### Independent Test

- **Test file path:** `tests/integration/test_auth_middleware.py`
- **Exact CI command:** `cd backend && poetry run pytest tests/integration/test_auth_middleware.py -v`
- **AC → assertion mapping:**
  - Valid JWT populates user → `it("accepts_valid_rs256_token_and_populates_request_state")`
  - Missing header → `it("returns_401_when_authorization_header_missing")`
  - Malformed JWT → `it("returns_401_for_malformed_jwt")`
  - `alg=none` → `it("rejects_alg_none_token")`
  - `alg=HS256` → `it("rejects_hs256_token")`
  - Expired → `it("returns_401_for_expired_token")`
  - Wrong iss → `it("returns_401_for_wrong_issuer")`
  - `iat < token_invalidated_at` → `it("rejects_token_issued_before_token_invalidated_at")`
  - `deleted_at` set → `it("rejects_soft_deleted_user")`
  - Cross-tenant `403` → `it("returns_403_on_cross_user_resource_access")`
  - `team_member` denied delete → `it("denies_team_member_drawing_delete")`
  - `team_admin` allowed delete → `it("allows_team_admin_drawing_delete")`
  - `team_member` allowed view → `it("allows_team_member_view_of_team_drawing")`
  - `user` denied team_manage → `it("denies_user_role_team_manage")`
  - Brute force 6th attempt blocked → `it("locks_out_after_5_failed_attempts")`
  - TTL 900s on first failure → `it("sets_900s_ttl_on_first_failure")`
  - Email lowercased key → `it("uses_lowercased_email_in_brute_force_key")`
  - Successful login clears counter → `it("clears_brute_force_counter_on_success_below_threshold")`
  - `admin_sign_out` HTTP call → `it("admin_sign_out_calls_supabase_logout_endpoint")`
  - `find_user_by_email` returns or None → `it("find_user_by_email_returns_user_or_none_never_merges")`
  - `ROLE_PERMISSIONS` matches spec → `it("role_permissions_matrix_matches_spec")`
- **Fixtures / test doubles:**
  - `rsa_keypair` (session-scoped): generates RSA keypair; injects public key into `settings.JWT_RS256_PUBLIC_KEY`.
  - `make_token(user_id, iat=None, exp=None, iss=None, alg="RS256")` factory signs with private key.
  - `redis_client` from `tests/integration/fixtures/redis.py`.
  - `db` from `tests/integration/fixtures/db.py` — creates `"user"` table via inline DDL inside the test fixture's setup, inserts test users.
  - `respx_mock` for Supabase Admin API HTTP calls.
  - `app_client` (FastAPI `TestClient`) with a test route registered locally inside the test module: `@app.get("/_test/protected", dependencies=[Depends(get_current_user)])` and `@app.get("/_test/resource/{drawing_id}", dependencies=[Depends(require_drawing_view(drawing_id))])`.
- **Pre-conditions:**
  - Env vars: `JWT_RS256_PUBLIC_KEY` (injected), `SUPABASE_URL=https://test.supabase.co`, `SUPABASE_SERVICE_ROLE_KEY=test-key`, `REDIS_URL`, `DATABASE_URL`.
  - Redis and Postgres running (per S0-B `docker-compose.fixtures.yml`).
  - The test file creates a minimal `"user"` table inline since S1-A may merge in parallel — the table DDL is duplicated for test isolation.
- **Isolation rule:** This test passes when only S0-A + S0-B + this PR are merged. It does not depend on S1-A's models, S1-D's Redis wrapper, or S1-E's analytics. The inline DDL and direct `redis.asyncio` client make this true.

##### Checkpoint

- **Observable outcome:** A FastAPI test route guarded by `Depends(get_current_user)` returns `401` without a token and the authenticated user payload with a valid RS256 token; a Redis key `brute_force:test@example.com` reaches TTL=900 after one simulated failed login through `record_login_failure()`.
- **Shippability claim:** This PR is independently mergeable to main even if no other session in the same wave has merged.

##### Output and handoff

Exports consumed by downstream sessions:

- `backend/app/auth/dependencies.py::get_current_user` `[LOAD-BEARING]` — used by every Phase 2 router.
- `backend/app/auth/dependencies.py::require_role(*roles)` — used by S2-F (account), S2-E (subscription billing_manage), future teams API.
- `backend/app/auth/dependencies.py::CurrentUser` (Pydantic model: `{id: UUID, email: str, role: UserRole, team_id: UUID|None}`) `[LOAD-BEARING]` — imported by all Phase 2 routers.
- `backend/app/auth/permissions.py::ROLE_PERMISSIONS` `[LOAD-BEARING]` — imported by S2-B, S2-C, S2-D, S2-F.
- `backend/app/auth/permissions.py::check_permission(role, action, resource_owner) -> bool` — imported by Phase 2 services.
- `backend/app/auth/brute_force.py::record_login_failure(email)`, `is_locked_out(email)`, `clear_failures(email)` — imported by S2-A.
- `backend/app/auth/supabase_client.py::admin_sign_out(user_id)` — imported by S2-A (password reset), S2-F (account deletion).
- `backend/app/auth/supabase_client.py::find_user_by_email(email)` — imported by S2-A (OAuth account-link path).
- `backend/app/auth/jwt_verifier.py::verify_token(token) -> dict` — imported by `middleware.py` only; treat as internal but exposed for testability.

---

```json
{
  "test": { "cmd": "cd backend && poetry run pytest tests/integration/test_auth_middleware.py -v", "file": "tests/integration/test_auth_middleware.py" },
  "checkpoint": "A FastAPI route guarded by Depends(get_current_user) returns 401 without a token and the authenticated user payload with a valid RS256 token; Redis key brute_force:{email} reaches TTL=900 after one recorded failed login.",
  "manualAcs": [
    { "id": "US-005-AC-KEY-ROT", "text": "Public-key rotation: rotating JWT_RS256_PUBLIC_KEY in production env invalidates previously issued tokens without code change." }
  ],
  "exports": [
    { "kind": "function", "name": "get_current_user", "shape": "(request: Request, db: AsyncSession = Depends(get_db)) => Awaitable<CurrentUser>" },
    { "kind": "function", "name": "require_role", "shape": "(*roles: UserRole) => Callable[[CurrentUser], CurrentUser]" },
    { "kind": "type", "name": "CurrentUser", "shape": "{ id: UUID; email: str; role: 'user'|'team_member'|'team_admin'; team_id: UUID | None }" },
    { "kind": "function", "name": "check_permission", "shape": "(role: UserRole, action: str, ownership: 'own'|'team'|None) => bool" },
    { "kind": "module", "name": "ROLE_PERMISSIONS", "shape": "backend/app/auth/permissions.py" },
    { "kind": "function", "name": "record_login_failure", "shape": "(email: str) => Awaitable<int>" },
    { "kind": "function", "name": "is_locked_out", "shape": "(email: str) => Awaitable<bool>" },
    { "kind": "function", "name": "clear_failures", "shape": "(email: str) => Awaitable<None>" },
    { "kind": "function", "name": "admin_sign_out", "shape": "(user_id: UUID) => Awaitable<None>" },
    { "kind": "function", "name": "find_user_by_email", "shape": "(email: str) => Awaitable<dict | None>" },
    { "kind": "function", "name": "verify_token", "shape": "(token: str) => dict" }
  ]
}
```