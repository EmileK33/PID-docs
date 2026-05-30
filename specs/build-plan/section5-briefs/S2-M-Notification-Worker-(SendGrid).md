---

#### S2-M — Notification Worker (SendGrid)

**Phase 2 | Real-time/Queue | Needs: S1-A, S1-D**

##### Objective

Implement the Celery-based asynchronous notification worker that dispatches all transactional emails (verification, password reset, grace period day-1, grace period day-6, and P1 team invitation) via the SendGrid API, so that user-facing email flows defined in US-001, US-002, and US-020 are reliably delivered without blocking the API request path.

##### Scope

**P0 MVP** — implement fully:
- `send_verification_email` Celery task (US-001)
- `send_password_reset_email` Celery task (US-002)
- `send_grace_day1_email` Celery task (US-020)
- `send_grace_day6_email` Celery task (US-020)
- `SendGridClient` wrapper with retry-aware error handling
- Template builders for all four P0 email types

**P1** — stub with clearly marked `# P1-STUB` placeholders, do not implement:
- `send_team_invitation_email` Celery task (US-023 — Team workspace invite by email, 72-hour link, seat-limited)

Every P1 stub must be importable and callable without raising an error; it must raise `NotImplementedError` with the message `"P1-STUB: team invitation email not implemented"` when invoked.

##### Technology constraints

From §1.8 (non-negotiable):

| Layer | Selected Technology |
|---|---|
| Async Workers | **Celery on Redis broker** — durable persistent queue (NFR-7); Redis already required for cache + SSE; changing broker requires worker rewrite |
| Queue / Cache | **Redis (ElastiCache)** — Celery broker |
| API Server | **FastAPI (Python)** — language unified with ML worker codebase |
| Database | **PostgreSQL (RDS/Aurora)** — schema migrations via Alembic |
| Email | **SendGrid** — transactional email integration |

From §1.7:
> **SendGrid** | API key (Bearer) | Standard SendGrid send limits | Transactional only: verification, password reset, invitations, payment notifications (day-1 and day-6 grace period emails)

Library requirements:
- `sendgrid` Python SDK (≥6.x) — **must** be used for HTTP calls to SendGrid
- `celery[redis]` — as established by S0-A/S1-D
- `sqlalchemy` — via S1-A models if DB lookups are required
- `tenacity` or Celery built-in `autoretry_for` — for retry policy on transient SendGrid 5xx errors

Must **NOT** use:
- Direct `httpx`/`requests` calls to SendGrid bypassing the `sendgrid` SDK — would lose built-in retry/header handling
- In-memory task execution (`CELERY_TASK_ALWAYS_EAGER` in production config) — violates NFR-7 persistent queue requirement
- Synchronous sleep-based polling for delivery confirmation — SendGrid is fire-and-send; delivery status is webhook-driven (out of scope for MVP)

##### Performance targets

From §1.9 — none assigned directly to the notification worker.

The notification worker has no hard SLA from §1.9. It is a best-effort delivery worker. However:
- **Analytics failures must not surface to users** (§1.10 general principle applied here): email send failures must not propagate exceptions to the Celery result backend in a way that blocks other queue processing.
- Celery task retry on transient failures (5xx / network errors): maximum 3 retries with exponential backoff (base 60s, max 3600s). Permanent failures (4xx, except 429) are logged and marked as failed without retry.
- 429 (rate limit) from SendGrid: retry after `Retry-After` header value, up to 3 additional attempts.

##### Owned files

```
backend/app/workers/notification/__init__.py
backend/app/workers/notification/tasks.py
backend/app/workers/notification/sendgrid_client.py
backend/app/workers/notification/templates.py
tests/integration/test_notification_worker.py
```

##### Read-only imports

| Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` (Celery application instance) |
| S0-A | `backend/app/config.py` | `settings` (Settings object exposing `SENDGRID_API_KEY`, `ENVIRONMENT`) |
| S1-A | `backend/app/db/session.py` | `get_db_session` (sync session factory for worker use) |
| S1-A | `backend/app/db/models/user.py` | `User` (ORM model — for any required email lookup fallback) |
| S1-D | `backend/app/workers/base.py` | `BaseTask` (Celery Task base class with retry policy hooks) |
| S1-D | `backend/app/workers/queues.py` | `NOTIFICATION_QUEUE` (queue name constant — `"notification"`) |

##### Do not touch

- `backend/app/main.py` — entry point, owned by S0-A
- `backend/app/api/routers/__init__.py` — router registry, owned by S0-A
- `backend/app/workers/celery_app.py` — Celery app instance, owned by S0-A
- `backend/app/workers/base.py` — base task class, owned by S1-D
- `backend/app/workers/queues.py` — queue routing config, owned by S1-D
- `backend/app/redis/client.py` — Redis client, owned by S1-D
- `backend/app/redis/cache.py` — cache helpers, owned by S1-D
- `backend/app/redis/pubsub.py` — pub/sub helpers, owned by S1-D
- `backend/app/db/models/*.py` — all ORM models, owned by S1-A
- `backend/app/analytics/events.py` — analytics emitters, owned by S1-E
- All files owned by S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-G, S2-H, S2-I, S2-J, S2-K, S2-L

##### Architecture context

From §1.7 (verbatim):

> **SendGrid** | API key (Bearer) | Standard SendGrid send limits | Transactional only: verification, password reset, invitations, payment notifications (day-1 and day-6 grace period emails)

From §1.8 (verbatim):

> **Async Workers** | Celery on Redis broker | Durable persistent queue (NFR-7); Redis already required for cache + SSE; Celery retry/timeout/priority support; changing broker requires worker rewrite

From §1.3 State Machines (verbatim):

> **Grace period: 7 days from first invoice.payment_failed Stripe event**
> Grace period day-1 email on entry; day-6 reminder email

From §1.11 Cross-Session Runtime Patterns — Celery Job Queue Names (verbatim):

> | `notification` | Notification Worker (CPU) | SendGrid email dispatch |

From §1.4 Critical Ordering Rules — Rule 14 (verbatim):

> **ML job must be enqueued via persistent queue (never in-memory).** "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts."

This rule applies to **all** Celery workers, including the notification worker. Tasks enqueued to the `notification` queue must survive server/worker restarts.

From §1.13 P0 Feature Scope (verbatim):

> - US-001: User registration and email verification
> - US-002: Email/password and Google OAuth login with account linking and brute-force lockout
> - US-020: Grace period handling (7-day, day-1 and day-6 emails); Stripe cancellation (access until period end); idempotent webhook processing

From §1.13 P1 Feature Scope (verbatim):

> - US-023: Team workspace — invite by email (72-hour link, seat-limited), member removal, seat release, team-level ML consent override

From §1.10 Analytics Event Contracts (verbatim — confirming no notification-worker-originated events):

> All nine events must be instrumented. Events must be non-blocking and asynchronous. Analytics failure must not surface to users.

The nine events are: `drawing_uploaded`, `processing_complete`, `processing_failed`, `correction_action`, `export_initiated`, `export_downloaded`, `free_limit_reached`, `subscription_upgraded`, `subscription_downgraded`. None originate from the notification worker; this session fires **no PostHog events**.

##### User stories and acceptance criteria

The spec provides the following verbatim story descriptions. Full AC text is derived from the described behaviors and cross-referenced constraints:

**US-001 — User registration and email verification**

From §1.13 (verbatim): "User registration and email verification"

Acceptance criteria relevant to S2-M:
- **AC-1**: When a `send_verification_email` task is consumed from the `notification` queue, it sends exactly one email to the address specified in the job payload via the SendGrid API.
- **AC-2**: The verification email contains the `verification_token` from the job payload embedded in a confirmation link.
- **AC-3**: If SendGrid returns a 5xx error or a network timeout, the task is retried up to 3 times with exponential backoff before being marked failed.
- **AC-4**: If SendGrid returns a 4xx error (excluding 429), the task is marked failed immediately without retry, and the error is logged with the user_id and email.
- **AC-5**: If SendGrid returns 429, the task retries after the `Retry-After` header value (or 60s fallback), up to 3 additional attempts.
- **AC-6**: A failed verification email task does **not** raise an unhandled exception that would crash the worker process.

**US-002 — Email/password login and password reset**

From §1.13 (verbatim): "Email/password and Google OAuth login with account linking and brute-force lockout"

Acceptance criteria relevant to S2-M:
- **AC-1**: When a `send_password_reset_email` task is consumed from the `notification` queue, it sends exactly one email to the address specified in the job payload via the SendGrid API.
- **AC-2**: The password reset email contains the `reset_token` from the job payload embedded in a reset link.
- **AC-3**: Retry behavior on SendGrid errors is identical to US-001 AC-3 through AC-6 (3 retries on 5xx, no retry on 4xx except 429).

**US-020 — Grace period handling**

From §1.13 (verbatim): "Grace period handling (7-day, day-1 and day-6 emails); Stripe cancellation (access until period end); idempotent webhook processing"
From §1.3 (verbatim): "Grace period day-1 email on entry; day-6 reminder email"

Acceptance criteria relevant to S2-M:
- **AC-1**: When a `send_grace_day1_email` task is consumed from the `notification` queue, it sends exactly one email to the address in the payload notifying the user that their subscription has entered a grace period.
- **AC-2**: The grace day-1 email body includes the `grace_period_end` datetime (formatted as human-readable date in UTC) from the job payload so the user knows when their access will be revoked.
- **AC-3**: When a `send_grace_day6_email` task is consumed from the `notification` queue, it sends exactly one reminder email to the address in the payload.
- **AC-4**: The grace day-6 email body includes the `grace_period_end` datetime from the payload and communicates urgency (access revocation within 24 hours).
- **AC-5**: The grace day-1 and day-6 tasks are independently enqueue-able; a failure of the day-1 task does not prevent the day-6 task from being enqueued or executed (scheduling is managed by the enqueueing caller, S2-E, not by S2-M).
- **AC-6**: Retry policy for grace period emails is identical to US-001 AC-3 through AC-6.

**US-023 — Team invitation email (P1 stub)**

From §1.13 P1 (verbatim): "Team workspace — invite by email (72-hour link, seat-limited), member removal, seat release, team-level ML consent override"

Acceptance criteria for stub:
- **AC-1**: `send_team_invitation_email` is importable from `backend/app/workers/notification/tasks.py`.
- **AC-2**: Calling `send_team_invitation_email.apply_async(kwargs={...})` raises `NotImplementedError` with message `"P1-STUB: team invitation email not implemented"`.

##### UX and design specification

N/A — this is a backend worker session with no frontend component.

##### Critical implementation notes

- **Persistent queue mandatory**: All four P0 tasks must be bound to the `notification` Celery queue via `queue=NOTIFICATION_QUEUE` in their `apply_async` options or via the task's `queue` attribute. From §1.4 Rule 14: "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts." — this applies to all Celery workers.

- **Email content must not be fetched from DB at execution time when payload contains it**: The enqueueing callers (S2-A for verification/reset, S2-E for grace emails) embed `email`, `display_name`, and all template-required fields into the job payload at enqueue time. The worker must use the payload values directly. This prevents stale data issues and DB coupling in workers. If a DB lookup is unavoidable for fallback, it must be clearly documented as an exception.

- **user_id in all payloads**: All P0 task payloads must include `user_id` (UUID string) for log correlation. This parallels the pattern from §1.4 Rule 5: "The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup."

- **HTTP status code contracts for SendGrid retry gating** — must implement exactly:
  - 2xx → success, mark task complete
  - 429 → retry with `Retry-After` header value (fallback: 60s), up to 3 additional attempts
  - 5xx / network error / timeout → retry with exponential backoff (60s base, ×2 per attempt, max 3600s), up to 3 attempts
  - 4xx (except 429) → log error with `user_id`, `email`, status code; mark task failed; **no retry**

- **SendGrid API key loaded from `settings`, not environment directly**: The `SendGridClient` must instantiate using `settings.SENDGRID_API_KEY` from `backend/app/config.py` (S0-A). From §1.12: if `SENDGRID_API_KEY` is absent, the application must "Refuse to start" — this is enforced in `config.py`, not in this worker. The worker can assume the key is present if the process started.

- **No analytics events fired from this worker**: Verify §1.10 — none of the nine structured PostHog events are triggered by the notification worker. Do not add PostHog calls; doing so would create a silent cross-session contract violation.

- **Grace period day-6 scheduling is the caller's responsibility**: The `send_grace_day6_email` task is an ordinary Celery task. Its delayed execution (6 days after grace start) is achieved by S2-E calling `send_grace_day6_email.apply_async(kwargs={...}, eta=grace_period_start + timedelta(days=6))`. This session implements the task only — not the ETA logic.

- **Email failures must never surface to end users**: Exceptions from SendGrid calls must be caught within the task. After max retries are exhausted, the task transitions to `FAILURE` state (Celery default), logs the error, and exits. No exception propagates to crash the worker process.

- **`send_team_invitation_email` stub must be importable without error at module load**: The `NotImplementedError` must only be raised when the task body executes, not at import time. The Celery `@celery_app.task` decorator must still decorate the stub so it registers as a valid Celery task.

- **Do not use `CELERY_TASK_ALWAYS_EAGER` in any production or integration test configuration**: Tests must mock the SendGrid SDK, not use eager execution as a substitute for testing queue behavior.

- **Silent failure mode — wrong queue name**: If the task is registered against a queue name other than `NOTIFICATION_QUEUE` (the constant from S1-D `queues.py`), tasks enqueued by S2-A and S2-E will never be consumed. The constant must be imported and used, not hardcoded as a string literal.

- **Template module must be pure (no I/O)**: `templates.py` must contain only string-building functions. No file reads, no DB calls, no network calls. All variable content (tokens, names, dates) must come from function parameters.

##### Mocking contract

This is a backend session. The following describes every internal event, queue payload, and service interface this session depends on from other sessions, with exact payload shapes.

**Celery `notification` queue — inbound job payloads (defined here, consumed here, produced by S2-A and S2-E):**

```python
# Task: send_verification_email
# Enqueued by: S2-A (auth_service.py — POST /auth/register)
{
    "user_id": str,              # UUID string
    "email": str,                # recipient email address
    "display_name": str,         # user display name for greeting
    "verification_token": str,   # opaque token for email confirmation link
}

# Task: send_password_reset_email
# Enqueued by: S2-A (password_reset.py — POST /auth/password-reset/request)
{
    "user_id": str,              # UUID string
    "email": str,                # recipient email address
    "display_name": str,         # user display name for greeting
    "reset_token": str,          # opaque token embedded in reset link
}

# Task: send_grace_day1_email
# Enqueued by: S2-E (stripe_webhook.py — on invoice.payment_failed → Grace transition)
{
    "user_id": str,              # UUID string
    "email": str,                # recipient email address
    "display_name": str,         # user display name for greeting
    "grace_period_end": str,     # ISO 8601 UTC datetime string, e.g. "2024-01-15T00:00:00Z"
}

# Task: send_grace_day6_email
# Enqueued by: S2-E (stripe_webhook.py — apply_async with eta=grace_period_start + 6 days)
{
    "user_id": str,              # UUID string
    "email": str,                # recipient email address
    "display_name": str,         # user display name for greeting
    "grace_period_end": str,     # ISO 8601 UTC datetime string
}

# Task: send_team_invitation_email — P1 STUB
# Enqueued by: future team session (P1)
{
    "invited_email": str,        # recipient email address
    "inviter_name": str,         # display name of the inviting user
    "team_name": str,            # team name for email body
    "invitation_token": str,     # opaque token for accept-invite link
    "expires_at": str,           # ISO 8601 UTC — 72 hours from enqueue time
}
```

**S0-A — `backend/app/workers/celery_app.py`:**
```python
celery_app  # Celery instance configured with Redis broker; tasks auto-discovered
```

**S0-A — `backend/app/config.py`:**
```python
settings.SENDGRID_API_KEY: str       # SendGrid API key
settings.ENVIRONMENT: str            # "development" | "staging" | "production"
```

**S1-D — `backend/app/workers/queues.py`:**
```python
NOTIFICATION_QUEUE: str = "notification"
```

**S1-D — `backend/app/workers/base.py`:**
```python
BaseTask  # Celery Task subclass with retry hooks and structured logging
```

**SendGrid SDK (external) — mock shape for tests:**
```python
# sendgrid.SendGridAPIClient(api_key=...).send(message) -> Response
# Response.status_code: int  (202 on success)
# On 4xx/5xx: raises sendgrid.exceptions.SendGridException or similar

# Mock interface expected by tests:
class MockSendGridResponse:
    status_code: int  # 202 | 429 | 500 | 400

class MockSendGridClient:
    def send(self, message) -> MockSendGridResponse: ...
```

##### Acceptance criteria checklist

- [ ] `send_verification_email` task sends exactly one email to the payload `email` address on success [US-001-AC-1]
- [ ] `send_verification_email` email contains `verification_token` in body/link [US-001-AC-2]
- [ ] `send_verification_email` retries up to 3 times on SendGrid 5xx, with exponential backoff [US-001-AC-3]
- [ ] `send_verification_email` marks task failed immediately on SendGrid 4xx (non-429), no retry [US-001-AC-4]
- [ ] `send_verification_email` retries up to 3 times on SendGrid 429, respecting `Retry-After` [US-001-AC-5]
- [ ] `send_verification_email` task failure does not crash the worker process [US-001-AC-6]
- [ ] `send_password_reset_email` task sends exactly one email to the payload `email` address on success [US-002-AC-1]
- [ ] `send_password_reset_email` email contains `reset_token` in body/link [US-002-AC-2]
- [ ] `send_password_reset_email` retry behavior matches US-001 AC-3 through AC-6 [US-002-AC-3]
- [ ] `send_grace_day1_email` task sends exactly one email to the payload `email` address [US-020-AC-1]
- [ ] `send_grace_day1_email` email body includes the `grace_period_end` value formatted as a human-readable date [US-020-AC-2]
- [ ] `send_grace_day6_email` task sends exactly one reminder email to the payload `email` address [US-020-AC-3]
- [ ] `send_grace_day6_email` email body includes `grace_period_end` and communicates urgency (imminent access revocation) [US-020-AC-4]
- [ ] `send_grace_day1_email` and `send_grace_day6_email` are independently executable; task definitions have no ordering dependency on each other [US-020-AC-5]
- [ ] `send_grace_day1_email` and `send_grace_day6_email` retry behavior matches US-001 AC-3 through AC-6 [US-020-AC-6]
- [ ] `send_team_invitation_email` is importable from `backend/app/workers/notification/tasks.py` without error [US-023-AC-1]
- [ ] `send_team_invitation_email.apply_async(kwargs={...})` raises `NotImplementedError` with message `"P1-STUB: team invitation email not implemented"` [US-023-AC-2]
- [ ] All four P0 tasks are registered against the `NOTIFICATION_QUEUE` queue constant from S1-D, not a hardcoded string [TECHNICAL]
- [ ] `SendGridClient` is instantiated with `settings.SENDGRID_API_KEY` from `config.py`, never `os.environ` directly [TECHNICAL]
- [ ] `templates.py` functions are pure — no I/O, no DB calls, no network calls; all variable content from parameters [TECHNICAL]
- [ ] No PostHog/analytics events are fired from any notification worker task [TECHNICAL]
- [ ] All tasks inherit from `BaseTask` (S1-D) [TECHNICAL]
- [ ] `send_team_invitation_email` is decorated with `@celery_app.task` and registers without error at import time; `NotImplementedError` is raised only in the task body, not at decoration time [TECHNICAL]

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation): `tests/integration/test_notification_worker.py`

**Exact CI command**: `pytest tests/integration/test_notification_worker.py -v`

**AC → assertion mapping**:

| AC | `it(...)` / `test(...)` block name |
|---|---|
| US-001-AC-1 | `test_verification_email_sends_to_correct_address` |
| US-001-AC-2 | `test_verification_email_contains_token_in_body` |
| US-001-AC-3 | `test_verification_email_retries_on_5xx` |
| US-001-AC-4 | `test_verification_email_no_retry_on_4xx` |
| US-001-AC-5 | `test_verification_email_retries_on_429` |
| US-001-AC-6 | `test_verification_email_failure_does_not_crash_worker` |
| US-002-AC-1 | `test_password_reset_email_sends_to_correct_address` |
| US-002-AC-2 | `test_password_reset_email_contains_reset_token` |
| US-002-AC-3 | `test_password_reset_retry_mirrors_verification_policy` |
| US-020-AC-1 | `test_grace_day1_email_sends_to_correct_address` |
| US-020-AC-2 | `test_grace_day1_email_contains_grace_period_end` |
| US-020-AC-3 | `test_grace_day6_email_sends_to_correct_address` |
| US-020-AC-4 | `test_grace_day6_email_contains_urgency_and_grace_period_end` |
| US-020-AC-5 | `test_grace_day1_and_day6_are_independent_tasks` |
| US-020-AC-6 | `test_grace_email_retry_policy_matches_verification` |
| US-023-AC-1 | `test_team_invitation_stub_is_importable` |
| US-023-AC-2 | `test_team_invitation_stub_raises_not_implemented` |
| TECHNICAL (queue) | `test_all_p0_tasks_bound_to_notification_queue` |
| TECHNICAL (api key) | `test_sendgrid_client_uses_settings_api_key` |
| TECHNICAL (pure templates) | `test_templates_are_pure_functions` |
| TECHNICAL (no analytics) | `test_no_posthog_calls_in_tasks` |
| TECHNICAL (BaseTask) | `test_all_tasks_inherit_from_base_task` |
| TECHNICAL (stub registration) | `test_team_invitation_stub_registered_as_celery_task` |

**Fixtures / test doubles**:

```python
# conftest.py additions for this test file

@pytest.fixture
def mock_sendgrid_client_success(mocker):
    """Returns mock SendGridClient whose .send() returns status_code=202."""
    mock = mocker.MagicMock()
    mock.send.return_value = mocker.MagicMock(status_code=202)
    return mock

@pytest.fixture
def mock_sendgrid_client_5xx(mocker):
    """Returns mock SendGridClient whose .send() raises on first 2 calls, succeeds on 3rd."""
    from sendgrid.exceptions import SendGridException
    mock = mocker.MagicMock()
    mock.send.side_effect = [
        SendGridException(status_code=500, body="Internal Server Error"),
        SendGridException(status_code=503, body="Service Unavailable"),
        mocker.MagicMock(status_code=202),
    ]
    return mock

@pytest.fixture
def mock_sendgrid_client_4xx(mocker):
    """Returns mock SendGridClient whose .send() raises a 400 immediately."""
    from sendgrid.exceptions import SendGridException
    mock = mocker.MagicMock()
    mock.send.side_effect = SendGridException(status_code=400, body="Bad Request")
    return mock

@pytest.fixture
def mock_sendgrid_client_429(mocker):
    """Returns mock SendGridClient simulating 429 then 202."""
    from sendgrid.exceptions import SendGridException
    response_429 = mocker.MagicMock(status_code=429, headers={"Retry-After": "30"})
    mock = mocker.MagicMock()
    mock.send.side_effect = [
        SendGridException(status_code=429, body="Too Many Requests"),
        mocker.MagicMock(status_code=202),
    ]
    return mock

# Payload factories
VERIFICATION_PAYLOAD = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "user@example.com",
    "display_name": "Test User",
    "verification_token": "tok_verify_abc123",
}

PASSWORD_RESET_PAYLOAD = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "user@example.com",
    "display_name": "Test User",
    "reset_token": "tok_reset_xyz789",
}

GRACE_DAY1_PAYLOAD = {
    "user_id": "00000000-0000-0000-0000-000000000002",
    "email": "user@example.com",
    "display_name": "Grace User",
    "grace_period_end": "2024-01-22T00:00:00Z",
}

GRACE_DAY6_PAYLOAD = {
    "user_id": "00000000-0000-0000-0000-000000000002",
    "email": "user@example.com",
    "display_name": "Grace User",
    "grace_period_end": "2024-01-22T00:00:00Z",
}

TEAM_INVITATION_PAYLOAD = {
    "invited_email": "invite@example.com",
    "inviter_name": "Admin User",
    "team_name": "Acme Corp",
    "invitation_token": "tok_invite_aaa111",
    "expires_at": "2024-01-18T12:00:00Z",
}
```

All mock `send()` call shapes match the `SendGridClient.send(message)` interface defined in the Mocking contract section above.

**Pre-conditions**:
- `SENDGRID_API_KEY=sg_test_key` set in test environment (value is non-empty; tests mock the actual HTTP call)
- `CELERY_TASK_ALWAYS_EAGER` must **not** be set; tasks are tested by directly calling the task function body (`task_fn(**payload)`) with the `SendGridClient` patched, not via Celery broker dispatch
- No Redis or PostgreSQL connection required for unit-level tests (all DB dependencies mocked via `mocker.patch`); the test file may optionally use the S0-B fixtures for smoke-level integration if environment is available, but all ACs must pass without them
- `backend/app/workers/celery_app.py` (S0-A) must be importable — it provides `celery_app`; tests patch `SendGridClient` at the `sendgrid_client` module level

**Isolation rule**: All ACs pass when only S2-M's PR is merged. Tests mock `celery_app` task registration (using `@celery_app.task` which only requires the Celery app instance from S0-A, already merged in Phase 0) and mock all SendGrid HTTP calls. No S2-A or S2-E code is imported or required. The queue constant `NOTIFICATION_QUEUE` from S1-D is the only Phase 1 import beyond S0-A; S1-D is a prerequisite and will have merged.

##### Checkpoint

- **One-sentence observable outcome**: After this PR merges, the four P0 Celery task definitions (`send_verification_email`, `send_password_reset_email`, `send_grace_day1_email`, `send_grace_day6_email`) are registered on the `notification` queue and, when executed against a live SendGrid API key, deliver transactional emails with the correct content for their respective templates.
- **Shippability claim**: This PR is independently mergeable to main even if no other Phase 2 session in the same wave has merged, provided S0-A (Phase 0) and S1-A, S1-D (Phase 1) have already merged. S2-A and S2-E (which enqueue these tasks) have not merged, so no tasks will be enqueued in production until those sessions merge — but the task definitions, client, and templates are fully functional and tested in isolation.

##### Output and handoff

| Export | Consuming Session(s) | Load-Bearing |
|---|---|---|
| `send_verification_email` — Celery task, signature: `(user_id: str, email: str, display_name: str, verification_token: str) -> None` | S2-A | **[LOAD-BEARING]** |
| `send_password_reset_email` — Celery task, signature: `(user_id: str, email: str, display_name: str, reset_token: str) -> None` | S2-A | **[LOAD-BEARING]** |
| `send_grace_day1_email` — Celery task, signature: `(user_id: str, email: str, display_name: str, grace_period_end: str) -> None` | S2-E | **[LOAD-BEARING]** |
| `send_grace_day6_email` — Celery task, signature: `(user_id: str, email: str, display_name: str, grace_period_end: str) -> None` | S2-E | **[LOAD-BEARING]** |
| `send_team_invitation_email` — P1 stub Celery task, importable but raises `NotImplementedError` | Future team session (P1) | No (P1 stub) |
| `SendGridClient` — class in `sendgrid_client.py`, `send(message) -> None` | Internal to worker only | No |
| `build_verification_email`, `build_password_reset_email`, `build_grace_day1_email`, `build_grace_day6_email` — pure functions in `templates.py` | Internal to worker only | No |
| Module path `backend/app/workers/notification/tasks` | S2-A, S2-E (import task references for `.delay()`/`.apply_async()`) | **[LOAD-BEARING]** |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/test_notification_worker.py -v",
    "file": "tests/integration/test_notification_worker.py"
  },
  "checkpoint": "The four P0 Celery notification tasks (send_verification_email, send_password_reset_email, send_grace_day1_email, send_grace_day6_email) are registered on the 'notification' queue and deliver transactional emails with correct content when executed against a live SendGrid API key.",
  "manualAcs": [],
  "exports": [
    {
      "kind": "function",
      "name": "send_verification_email",
      "shape": "(user_id: str, email: str, display_name: str, verification_token: str) -> None"
    },
    {
      "kind": "function",
      "name": "send_password_reset_email",
      "shape": "(user_id: str, email: str, display_name: str, reset_token: str) -> None"
    },
    {
      "kind": "function",
      "name": "send_grace_day1_email",
      "shape": "(user_id: str, email: str, display_name: str, grace_period_end: str) -> None"
    },
    {
      "kind": "function",
      "name": "send_grace_day6_email",
      "shape": "(user_id: str, email: str, display_name: str, grace_period_end: str) -> None"
    },
    {
      "kind": "function",
      "name": "send_team_invitation_email",
      "shape": "(invited_email: str, inviter_name: str, team_name: str, invitation_token: str, expires_at: str) -> None"
    },
    {
      "kind": "type",
      "name": "SendGridClient",
      "shape": "{ __init__(api_key: str): None; send(message: Any) -> None }"
    },
    {
      "kind": "module",
      "name": "backend/app/workers/notification/tasks",
      "shape": "backend/app/workers/notification/tasks.py"
    },
    {
      "kind": "module",
      "name": "backend/app/workers/notification/templates",
      "shape": "backend/app/workers/notification/templates.py"
    },
    {
      "kind": "module",
      "name": "backend/app/workers/notification/sendgrid_client",
      "shape": "backend/app/workers/notification/sendgrid_client.py"
    }
  ]
}
```