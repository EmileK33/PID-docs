#### S2-E — Subscription + Stripe Webhook

**Phase 2 | Backend API | Needs: S1-A, S1-B, S1-D, S1-E**

---

##### Objective

Implements the Stripe Checkout session creation, subscription state management, billing state machine, and idempotent Stripe webhook processing that gate every paid-tier feature in the system.

---

##### Scope

**P0 MVP.** Both US-019 and US-020 are fully P0.

P1 stub required: `POST /subscription/manage` (Stripe Customer Portal redirect for user-initiated downgrades and payment method management). Must be present as a clearly marked `NotImplementedError` placeholder in `subscription.py` — the P0 route manifest has only `GET /subscription` and `POST /subscription/checkout`.

---

##### Technology constraints

- **FastAPI (Python)** — all route handlers; from `backend/app/main.py` scaffold (S0-A)
- **`stripe` Python SDK** — Stripe API calls and webhook verification; version pinned in `backend/pyproject.toml` (S0-B). Use `stripe.Webhook.construct_event()` for signature verification. Wrap blocking Stripe SDK calls with `asyncio.get_event_loop().run_in_executor(None, ...)` inside async handlers.
- **SQLAlchemy (sync session)** — DB access via session from `backend/app/db/session.py` (S0-A)
- **Alembic** — migrations owned by S1-A; this session must not create new migrations
- **Redis** via `backend/app/redis/client.py` (S1-D) — for cache invalidation/write of `subscription:flags:{user_id}`
- **Celery** via `backend/app/workers/celery_app.py` (S0-A) — task dispatch to `notification` queue for grace-period emails
- **PostHog** via `backend/app/analytics/events.py` (S1-E) — `subscription_upgraded` / `subscription_downgraded` events
- **MUST NOT** update any subscription DB field inside `POST /subscription/checkout` — state mutations are exclusively webhook-driven (§1.4 Rule 9)
- **MUST NOT** use in-memory event deduplication — idempotency must use the `stripe_event` DB table (§1.4 Rule 10)
- **MUST NOT** use `stripe-mock` for integration tests — construct real Stripe event payloads signed with a test webhook secret using `stripe.WebhookSignature.generate_header()`

---

##### Performance targets

- **`GET /subscription`**: No hard SLA owned here. Must support polling at sub-second latency; serves the frontend 30-second post-checkout polling window (§1.9 monitoring target). Redis cache (`subscription:flags:{user_id}`, 5-minute TTL) must be updated synchronously within the webhook handler so the first subsequent poll reflects the new tier.
- **`POST /webhooks/stripe`**: Must return `200` within Stripe's 30-second delivery timeout. All heavy work (analytics, cache write, Celery dispatch) runs synchronously within the handler before returning — no fire-and-forget deferral that could cause a timeout return before state is committed.
- **Stripe tier activation after Checkout redirect**: <30 seconds (monitoring target, §1.9) — owned end-to-end by this session's webhook handler latency plus DB commit.

---

##### Owned files

- `backend/app/api/routers/subscription.py`
- `backend/app/api/routers/stripe_webhook.py`
- `backend/app/services/stripe_client.py`
- `backend/app/services/subscription_service.py`
- `backend/app/services/billing_state_machine.py`
- `backend/app/services/stripe_event_idempotency.py`
- `tests/integration/test_subscription.py`
- `tests/integration/test_stripe_webhook.py`

---

##### Read-only imports

| Owning Session | File Path | Required Named Exports |
|---|---|---|
| S1-A | `backend/app/db/models/subscription.py` | `Subscription` |
| S1-A | `backend/app/db/models/stripe_event.py` | `StripeEvent` |
| S1-A | `backend/app/db/models/user.py` | `User` |
| S1-A | `backend/app/db/models/tier.py` | `Tier` |
| S1-B | `backend/app/auth/dependencies.py` | `get_current_user` |
| S1-D | `backend/app/redis/client.py` | `get_redis` |
| S1-D | `backend/app/redis/cache.py` | `invalidate_subscription_flags`, `set_subscription_flags` |
| S1-E | `backend/app/analytics/events.py` | `emit_subscription_upgraded`, `emit_subscription_downgraded` |
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` |
| S0-A | `backend/app/schemas/contracts.py` | `BillingState`, `TierId` |

---

##### Do not touch

- `backend/app/main.py` — entry point, pre-stubbed by S0-A
- `backend/app/api/routers/__init__.py` — router includes, pre-stubbed by S0-A
- `backend/app/api/routers/_stubs.py` — placeholder endpoints by S0-A
- All S1-A model files (`backend/app/db/models/`)
- All S1-B auth files (`backend/app/auth/`)
- All S1-D Redis files (`backend/app/redis/`)
- All S1-E analytics files (`backend/app/analytics/`)
- `backend/app/workers/notification/` — owned by S2-M
- `backend/app/services/free_tier_counter.py` — owned by S2-B
- `backend/app/services/drawing_service.py` — owned by S2-B
- `backend/alembic/versions/` — migrations owned by S1-A

---

##### Architecture context

From **§1.1 Shared Contracts** (verbatim):

```typescript
// Subscription Billing State
type BillingState = 'Active' | 'Grace' | 'Canceled';

// Tier IDs
type TierId = 'free' | 'pro' | 'team';
```

From **§1.3 State Machines and Permission Matrices** (verbatim):

```typescript
// Subscription Billing State Transitions
const BILLING_STATE_TRANSITIONS: Record<BillingState, BillingState[]> = {
  Active: ['Grace', 'Canceled'],
  Grace:  ['Active', 'Canceled'],   // → Active on payment resolved; → Canceled on grace expiry (downgrade to Free)
  Canceled: ['Active'],             // → Active on resubscribe
} as const;

// Grace period: 7 days from first invoice.payment_failed Stripe event
// Grace period day-1 email on entry; day-6 reminder email
```

```typescript
// Feature-Tier Gate Matrix
const TIER_FEATURE_GATES = {
  free: {
    monthly_drawing_limit:   3,
    export_csv_xlsx:         true,
    revision_comparison:     false,     // Pro/Team only
    team_library:            false,     // Team only
    api_access:              false,
  },
  pro: {
    monthly_drawing_limit:   null,      // unlimited
    export_csv_xlsx:         true,
    revision_comparison:     true,
    team_library:            false,
    api_access:              false,
  },
  team: {
    monthly_drawing_limit:   null,
    export_csv_xlsx:         true,
    revision_comparison:     true,
    team_library:            true,
    api_access:              false,     // P1 (FR-11)
  },
} as const;
```

From **§1.4 Critical Ordering Rules** (verbatim):

> **Rule 9. Stripe webhook state changes via webhook only, never inline after redirect.** "The subscription state in the application database must be updated exclusively via Stripe webhook events (not inline after the payment redirect) to ensure consistency and idempotency."

> **Rule 10. Stripe webhook idempotency via stored event ID before any state mutation.** "Idempotency enforced via Stripe event ID stored in DB before any state mutation."

From **§1.5 HTTP Status Code Contracts** (verbatim):

| Condition | Required code | Must never return |
|---|---|---|
| Stripe webhook received and processed | `200` | `4xx`, `5xx` |
| Stripe duplicate webhook (already processed, idempotent) | `200` | `4xx` |
| Unauthenticated request to protected endpoint | `401` | `403`, `200` |

From **§1.7 Third-Party Dependencies** (verbatim):

> **Stripe Billing**: `Stripe-Signature` header (HMAC) on webhooks; API key for server calls | Standard Stripe rate limits | Webhook delivery retries require idempotency enforcement; event ID must be stored before any state mutation; `checkout.session.completed` and `customer.subscription.updated` events required

From **§1.9 Performance Targets** (verbatim):

> Stripe tier activation after Checkout redirect | <30 seconds | Monitoring target | Stripe webhook handler + subscription update

From **§1.10 Analytics Event Contracts** (verbatim):

| Event Name | Payload Shape | Code Surface That Fires It | Trigger Condition | Must NOT have happened yet | Must NEVER fire from |
|---|---|---|---|---|---|
| `subscription_upgraded` | `{ event: 'subscription_upgraded', timestamp: string (UTC ISO8601), user_id: string, subscription_id: string, previous_tier: TierId, new_tier: TierId }` | FastAPI — Stripe webhook handler (`customer.subscription.updated`) | Subscription tier increases | Tier change applied before event fires | Browser client; Stripe redirect handler inline |
| `subscription_downgraded` | `{ event: 'subscription_downgraded', timestamp: string (UTC ISO8601), user_id: string, subscription_id: string, previous_tier: TierId, new_tier: TierId }` | FastAPI — Stripe webhook handler or downgrade confirmation handler | Subscription tier decreases (fires immediately at confirmation, not at period end) | None specified | Browser client |

From **§1.11 Cross-Session Runtime Patterns — Redis Cache Keys** (verbatim):

| Key Pattern | Written By | Read By | TTL |
|---|---|---|---|
| `subscription:flags:{user_id}` | FastAPI on login / Stripe webhook handler | FastAPI middleware (every authenticated request, feature-gate evaluation) | 5 minutes; invalidated on webhook receipt |

From **§1.12 Environment Variable Schema** (verbatim, relevant rows):

| Variable | Startup Behavior if Invalid | Startup Behavior if Absent |
|---|---|---|
| `STRIPE_SECRET_KEY` | Refuse to start | Refuse to start |
| `STRIPE_WEBHOOK_SECRET` | Refuse to start | Refuse to start |

---

##### User stories and acceptance criteria

From **§1.13 Feature Scope — P0** (verbatim):

> **US-019**: Stripe Checkout upgrade (Pro and Team tiers); downgrade deferred to period end; pending state with 30s webhook resolution timeout

> **US-020**: Grace period handling (7-day, day-1 and day-6 emails); Stripe cancellation (access until period end); idempotent webhook processing

**Derived acceptance criteria from specification requirements:**

**US-019 — Stripe Checkout Upgrade**

- **AC-1**: `POST /subscription/checkout` with `{"tier_id": "pro"}` for an authenticated user returns HTTP 200 with a `checkout_url` pointing to a Stripe-hosted Checkout session.
- **AC-2**: `POST /subscription/checkout` with `{"tier_id": "team"}` for an authenticated user returns HTTP 200 with a valid `checkout_url`.
- **AC-3**: `POST /subscription/checkout` does NOT mutate any row in the `subscription` table; the subscription `tier_id` and `billing_state` are unchanged after the call (state only changes via webhook, §1.4 Rule 9).
- **AC-4**: `POST /subscription/checkout` returns HTTP 401 for unauthenticated requests.
- **AC-5**: `GET /subscription` returns the authenticated user's current `tier_id`, `billing_state`, `current_period_end`, and `grace_period_start`.
- **AC-6**: `GET /subscription` returns HTTP 401 for unauthenticated requests.
- **AC-7**: After `checkout.session.completed` webhook is received, the subscription record for the user identified by `client_reference_id` has its `tier_id` updated to the new tier and `billing_state` set to `Active`.
- **AC-8**: After `checkout.session.completed`, `stripe_customer_id` and `stripe_subscription_id` are stored on the subscription record.
- **AC-9**: After `checkout.session.completed`, `subscription:flags:{user_id}` Redis cache entry is invalidated (deleted or rewritten) so that the next `GET /subscription` poll reflects the new tier.
- **AC-10**: After `customer.subscription.updated` webhook is received with a tier increase (detected via `previous_attributes`), the `subscription_upgraded` analytics event is emitted with correct `previous_tier`, `new_tier`, `user_id`, and `subscription_id`. The DB tier change is committed BEFORE the analytics event fires.
- **AC-11**: `subscription_upgraded` is NEVER fired from the inline checkout response path — only from the webhook handler.

**US-020 — Grace Period, Cancellation, Idempotency**

- **AC-1**: `invoice.payment_failed` webhook transitions `billing_state` from `Active` to `Grace`.
- **AC-2**: `invoice.payment_failed` sets `grace_period_start` to the current UTC timestamp on the subscription record.
- **AC-3**: Subsequent `invoice.payment_failed` events for a subscription already in `Grace` state do NOT reset `grace_period_start`.
- **AC-4**: `invoice.payment_failed` enqueues a day-1 grace notification Celery task to the `notification` queue (immediately).
- **AC-5**: `invoice.payment_failed` enqueues a day-6 grace reminder Celery task to the `notification` queue with ETA = `grace_period_start + timedelta(days=6)`.
- **AC-6**: `invoice.payment_succeeded` when subscription is in `Grace` state transitions `billing_state` to `Active` and clears `grace_period_start` (sets to NULL).
- **AC-7**: `customer.subscription.deleted` transitions `billing_state` to `Canceled` and resets `tier_id` to `free`.
- **AC-8**: `customer.subscription.updated` with a tier decrease fires `subscription_downgraded` analytics event immediately (not deferred to period end), with correct `previous_tier` and `new_tier`.
- **AC-9**: Stripe webhook `Stripe-Signature` header is verified via `stripe.Webhook.construct_event()` before any processing. An invalid or missing signature returns HTTP 400.
- **AC-10**: A Stripe event with an `id` that already exists in the `stripe_event` table returns HTTP 200 without executing any subscription state mutations (idempotent, §1.4 Rule 10).
- **AC-11**: `POST /webhooks/stripe` returns HTTP 200 for every successfully processed event type.
- **AC-12**: `POST /webhooks/stripe` returns HTTP 200 for duplicate events (same Stripe event ID) — never 4xx.
- **AC-13**: The `StripeEvent` record INSERT is the first DB write in any webhook transaction — it precedes any write to the `subscription` table (§1.4 Rule 10).
- **AC-14**: `subscription:flags:{user_id}` Redis cache is invalidated after every webhook-driven subscription state change.
- **AC-15**: Unrecognized Stripe event types (e.g., `payment_intent.created`) return HTTP 200 without error.
- **AC-16**: The billing state machine raises `InvalidTransitionError` (and does not silently skip) for any transition not defined in `BILLING_STATE_TRANSITIONS` (e.g., attempting `Grace → Grace`). [MANUAL]
- **AC-17**: Stripe tier activation (tier reflected in `GET /subscription`) occurs within 30 seconds of Stripe firing `checkout.session.completed` in a staging environment. [MANUAL]

---

##### UX and design specification

N/A — backend-only session. No frontend component. Frontend polling UI and upgrade prompt UI are implemented in S3-F (`frontend/src/pages/Subscription.tsx` and related files).

---

##### Critical implementation notes

- **[§1.4 Rule 9 — hard constraint]**: `POST /subscription/checkout` must NOT write to `subscription` table. It calls `stripe.checkout.Session.create(...)` and returns the `url`. If a developer adds "optimistic" DB writes here, the subscription state will become inconsistent with Stripe's state.

- **[§1.4 Rule 10 — ordering rule]**: Inside every webhook event handler, the `StripeEvent` INSERT must be the first DB write. Use `INSERT INTO stripe_event (id, event_type, processed_at) VALUES (:id, :type, NOW()) ON CONFLICT (id) DO NOTHING`. Check `rowcount == 0` after the insert; if zero rows were inserted, the event is a duplicate — return `200` immediately without touching the `subscription` table.

- **[§1.5 — HTTP contract]**: Duplicate Stripe webhooks return `200`, never `409`. Stripe will retry any non-2xx response, leading to infinite reprocessing loops.

- **[Stripe customer linkage]**: At checkout session creation time, embed the authenticated user's UUID via both `client_reference_id=str(user.id)` and `metadata={"user_id": str(user.id)}`. In `checkout.session.completed`, retrieve the user via `client_reference_id`. In `customer.subscription.updated` and `invoice.*` events, look up the subscription record via `stripe_customer_id` on the `subscription` table.

- **[Tier mapping — required env vars not in §1.12]**: Tier identification from Stripe events requires `STRIPE_PRO_PRICE_ID` and `STRIPE_TEAM_PRICE_ID` environment variables to map Stripe price IDs to `TierId`. Add these to startup validation in `backend/app/config.py`. Without these, the webhook handler cannot determine which tier a Stripe subscription corresponds to.

- **[§1.10 — analytics ordering]**: `subscription_upgraded` must fire ONLY after the DB `tier_id` update is committed. Use a `try/finally` or post-commit hook pattern — never fire analytics before `db.commit()`.

- **[§1.10 — analytics surface]**: `subscription_downgraded` fires immediately in `customer.subscription.updated` when `cancel_at_period_end` flips to `True` (scheduled cancellation) or when subscription items reflect a lower tier. It does NOT wait for `customer.subscription.deleted`. This means users see `subscription_downgraded` fired even though they retain access until `current_period_end`.

- **[§1.11 — cache write]**: After any state mutation in a webhook handler, call both `invalidate_subscription_flags(user_id)` AND `set_subscription_flags(user_id, fresh_flags)` before returning `200`. This ensures the next poll after the webhook lands gets fresh data without a DB hit. The 5-minute TTL is a fallback, not the primary path.

- **[Subscription record bootstrap]**: If `checkout.session.completed` fires and no `subscription` row exists for the user (edge case: user was registered before seeding), INSERT a new subscription row. Normally, the auth registration flow (S2-A) should have created a `tier_id='free'` subscription; do not assume it exists.

- **[Grace period idempotency]**: `invoice.payment_failed` sets `grace_period_start` only if it is currently NULL (i.e., on first failure). Subsequent `invoice.payment_failed` events while already in `Grace` state must NOT reset `grace_period_start` (or the day-6 ETA would be recalculated, delaying the reminder incorrectly).

- **[Webhook raw body]**: FastAPI must read the raw request body (bytes) before any JSON parsing for webhook signature verification. Do NOT use `Request.json()` before `stripe.Webhook.construct_event()`; instead, use `await request.body()` and pass raw bytes.

- **[`stripe_event` model contract — cross-session]**: This session reads and writes `backend/app/db/models/stripe_event.py` (owned by S1-A). The model MUST have at minimum: `id: String (PK)`, `event_type: String (non-null)`, `processed_at: TIMESTAMPTZ (non-null, server_default=now())`. If S1-A's model differs from this contract, flag as a planning bug before implementation.

- **[Invalid state transitions]**: `billing_state_machine.py` must validate every transition against `BILLING_STATE_TRANSITIONS`. An attempt to transition to a state not in the allowed list (e.g., `Canceled → Grace`) must raise `InvalidTransitionError` — never silently apply an illegal state write. This prevents corrupt billing state from a malformed webhook.

- **[Unrecognized events]**: Return `200` for all unrecognized Stripe event types — Stripe sends many event types beyond the ones this session handles. Never return `400` for an unknown event type; doing so will cause Stripe to retry indefinitely.

- **[`STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` — startup gates]**: Per §1.12, both must cause the application to refuse to start if absent. This is enforced in `backend/app/config.py` (S0-A), but `stripe_client.py` must also call `stripe.api_key = settings.STRIPE_SECRET_KEY` at module initialization time and raise `ConfigurationError` if blank.

---

##### Mocking contract

This is a backend session. The following lists every internal queue payload and service interface consumed from other sessions.

**Celery notification tasks** (owned by S2-M, `backend/app/workers/notification/tasks.py`):

```python
# Task signature this session dispatches (S2-M implements):
send_grace_period_started_email.delay(
    user_id: str,                   # UUID string
    grace_period_end: str,          # ISO 8601 UTC datetime string (grace_period_start + 7 days)
)

send_grace_period_reminder_email.apply_async(
    args=[user_id, grace_period_end],
    eta=grace_period_start + timedelta(days=6),
)
```

In tests: mock both tasks as `MagicMock` via `unittest.mock.patch` and assert `.delay()` / `.apply_async()` called with correct `user_id` and `grace_period_end`.

**Analytics events** (owned by S1-E, `backend/app/analytics/events.py`):

```python
# Subscription upgraded
emit_subscription_upgraded(
    user_id: str,           # UUID string
    subscription_id: str,   # internal subscription UUID
    previous_tier: str,     # TierId: 'free' | 'pro' | 'team'
    new_tier: str,          # TierId
)

# Subscription downgraded
emit_subscription_downgraded(
    user_id: str,
    subscription_id: str,
    previous_tier: str,
    new_tier: str,
)
```

In tests: mock both via `unittest.mock.patch` and assert called with correct args, called AFTER DB commit.

**Redis cache operations** (owned by S1-D, `backend/app/redis/cache.py`):

```python
invalidate_subscription_flags(user_id: str) -> None
set_subscription_flags(user_id: str, flags: dict) -> None
# flags dict shape:
{
    "tier_id": str,          # 'free' | 'pro' | 'team'
    "billing_state": str,    # 'Active' | 'Grace' | 'Canceled'
    "monthly_drawing_limit": int | None,
    "revision_comparison": bool,
    "team_library": bool,
}
```

**Stripe API mock shapes** (for integration tests — sign payloads with test `STRIPE_WEBHOOK_SECRET`):

```python
# POST /subscription/checkout — stripe.checkout.Session.create mock response
MOCK_CHECKOUT_SESSION = {
    "id": "cs_test_abc123",
    "url": "https://checkout.stripe.com/pay/cs_test_abc123",
    "client_reference_id": "<user_uuid>",
    "customer": "cus_test_xxx",
    "payment_status": "unpaid",
}

# checkout.session.completed event payload
CHECKOUT_COMPLETED_PAYLOAD = {
    "id": "evt_checkout_completed_001",
    "type": "checkout.session.completed",
    "data": {
        "object": {
            "id": "cs_test_abc123",
            "client_reference_id": "<user_uuid>",
            "customer": "cus_test_xxx",
            "subscription": "sub_test_pro_001",
            "payment_status": "paid",
        }
    }
}

# customer.subscription.updated (tier increase: free → pro)
SUBSCRIPTION_UPDATED_UPGRADE_PAYLOAD = {
    "id": "evt_sub_updated_upgrade_001",
    "type": "customer.subscription.updated",
    "data": {
        "object": {
            "id": "sub_test_pro_001",
            "customer": "cus_test_xxx",
            "status": "active",
            "current_period_end": 1767225600,
            "cancel_at_period_end": False,
            "items": {
                "data": [{"price": {"id": "<STRIPE_PRO_PRICE_ID>", "product": "prod_pro"}}]
            }
        },
        "previous_attributes": {
            "items": {
                "data": [{"price": {"id": "price_free", "product": "prod_free"}}]
            }
        }
    }
}

# customer.subscription.updated (downgrade: pro → free via cancel_at_period_end)
SUBSCRIPTION_UPDATED_DOWNGRADE_PAYLOAD = {
    "id": "evt_sub_updated_downgrade_001",
    "type": "customer.subscription.updated",
    "data": {
        "object": {
            "id": "sub_test_pro_001",
            "customer": "cus_test_xxx",
            "status": "active",
            "current_period_end": 1767225600,
            "cancel_at_period_end": True,
            "items": {
                "data": [{"price": {"id": "<STRIPE_PRO_PRICE_ID>", "product": "prod_pro"}}]
            }
        },
        "previous_attributes": {"cancel_at_period_end": False}
    }
}

# invoice.payment_failed
INVOICE_PAYMENT_FAILED_PAYLOAD = {
    "id": "evt_invoice_failed_001",
    "type": "invoice.payment_failed",
    "data": {
        "object": {
            "id": "in_test_failed_001",
            "customer": "cus_test_xxx",
            "subscription": "sub_test_pro_001",
        }
    }
}

# invoice.payment_succeeded (payment recovery during grace)
INVOICE_PAYMENT_SUCCEEDED_PAYLOAD = {
    "id": "evt_invoice_succeeded_001",
    "type": "invoice.payment_succeeded",
    "data": {
        "object": {
            "id": "in_test_ok_001",
            "customer": "cus_test_xxx",
            "subscription": "sub_test_pro_001",
        }
    }
}

# customer.subscription.deleted
SUBSCRIPTION_DELETED_PAYLOAD = {
    "id": "evt_sub_deleted_001",
    "type": "customer.subscription.deleted",
    "data": {
        "object": {
            "id": "sub_test_pro_001",
            "customer": "cus_test_xxx",
        }
    }
}
```

All webhook payloads in tests must be signed using:
```python
import stripe, time, json
payload_str = json.dumps(payload)
timestamp = int(time.time())
sig_header = stripe.WebhookSignature.generate_header(
    timestamp=timestamp,
    payload=payload_str,
    secret=TEST_WEBHOOK_SECRET,
)
```

---

##### Acceptance criteria checklist

- [ ] `POST /subscription/checkout` with `tier_id=pro` returns HTTP 200 with `checkout_url` for authenticated user [US-019 AC-1]
- [ ] `POST /subscription/checkout` with `tier_id=team` returns HTTP 200 with `checkout_url` for authenticated user [US-019 AC-2]
- [ ] `POST /subscription/checkout` does NOT mutate the `subscription` table row; `tier_id` and `billing_state` unchanged after call [US-019 AC-3]
- [ ] `POST /subscription/checkout` returns HTTP 401 for unauthenticated request [US-019 AC-4]
- [ ] `GET /subscription` returns current `tier_id`, `billing_state`, `current_period_end`, and `grace_period_start` for authenticated user [US-019 AC-5]
- [ ] `GET /subscription` returns HTTP 401 for unauthenticated request [US-019 AC-6]
- [ ] After `checkout.session.completed` webhook, `subscription.tier_id` updated to new tier and `billing_state` set to `Active` for user identified by `client_reference_id` [US-019 AC-7]
- [ ] After `checkout.session.completed`, `stripe_customer_id` and `stripe_subscription_id` stored on subscription record [US-019 AC-8]
- [ ] After `checkout.session.completed`, `subscription:flags:{user_id}` Redis cache invalidated/rewritten [US-019 AC-9]
- [ ] After `customer.subscription.updated` with tier increase, `subscription_upgraded` analytics event emitted with correct `previous_tier`, `new_tier`, `user_id`, `subscription_id` [US-019 AC-10]
- [ ] `subscription_upgraded` analytics event is NOT emitted from inline `POST /subscription/checkout` response path [US-019 AC-11]
- [ ] `invoice.payment_failed` transitions `billing_state` from `Active` to `Grace` [US-020 AC-1]
- [ ] `invoice.payment_failed` sets `grace_period_start` to current UTC timestamp [US-020 AC-2]
- [ ] Second `invoice.payment_failed` for subscription already in `Grace` state does NOT reset `grace_period_start` [US-020 AC-3]
- [ ] `invoice.payment_failed` enqueues day-1 grace notification Celery task with correct `user_id` and `grace_period_end` [US-020 AC-4]
- [ ] `invoice.payment_failed` enqueues day-6 grace reminder Celery task with ETA = `grace_period_start + timedelta(days=6)` [US-020 AC-5]
- [ ] `invoice.payment_succeeded` when `billing_state == Grace` transitions to `Active` and sets `grace_period_start = NULL` [US-020 AC-6]
- [ ] `customer.subscription.deleted` transitions `billing_state` to `Canceled` and sets `tier_id` to `free` [US-020 AC-7]
- [ ] `customer.subscription.updated` with tier decrease fires `subscription_downgraded` analytics event immediately with correct `previous_tier` and `new_tier` [US-020 AC-8]
- [ ] Invalid or missing `Stripe-Signature` header returns HTTP 400 [US-020 AC-9]
- [ ] Webhook with already-processed `event.id` returns HTTP 200 without mutating `subscription` table [US-020 AC-10]
- [ ] `POST /webhooks/stripe` returns HTTP 200 for successfully processed event [US-020 AC-11]
- [ ] `POST /webhooks/stripe` returns HTTP 200 for duplicate events (same Stripe event ID) — not 4xx [US-020 AC-12]
- [ ] `StripeEvent` INSERT is the first DB write in every webhook handler, before any `subscription` table write [US-020 AC-13]
- [ ] `subscription:flags:{user_id}` Redis cache invalidated after every webhook-driven subscription state change [US-020 AC-14]
- [ ] Unrecognized Stripe event type (e.g., `payment_intent.created`) returns HTTP 200 [US-020 AC-15]
- [ ] Billing state machine `InvalidTransitionError` raised for illegal transition (e.g., `Canceled → Grace`), not silently skipped [US-020 AC-16] [MANUAL]
- [ ] Stripe tier activation (reflected in `GET /subscription`) occurs within 30 seconds of `checkout.session.completed` in staging [US-020 AC-17] [MANUAL]

---

##### Independent Test

**Test file path** (TDD — written first, must fail before implementation): `tests/sessions/test_s2_e.py`

**Exact CI command**: `pytest tests/sessions/test_s2_e.py -v`

**AC → assertion mapping**:

| AC | `test_` function name |
|---|---|
| US-019 AC-1 | `test_checkout_creates_session_pro_tier` |
| US-019 AC-2 | `test_checkout_creates_session_team_tier` |
| US-019 AC-3 | `test_checkout_does_not_mutate_subscription_table` |
| US-019 AC-4 | `test_checkout_returns_401_unauthenticated` |
| US-019 AC-5 | `test_get_subscription_returns_current_state` |
| US-019 AC-6 | `test_get_subscription_returns_401_unauthenticated` |
| US-019 AC-7 | `test_checkout_completed_webhook_updates_tier_and_billing_state` |
| US-019 AC-8 | `test_checkout_completed_webhook_stores_stripe_ids` |
| US-019 AC-9 | `test_checkout_completed_webhook_invalidates_redis_cache` |
| US-019 AC-10 | `test_subscription_updated_webhook_fires_upgraded_analytics` |
| US-019 AC-11 | `test_checkout_endpoint_does_not_fire_upgraded_analytics` |
| US-020 AC-1 | `test_invoice_payment_failed_enters_grace_period` |
| US-020 AC-2 | `test_invoice_payment_failed_sets_grace_period_start` |
| US-020 AC-3 | `test_invoice_payment_failed_does_not_reset_grace_period_start_if_already_in_grace` |
| US-020 AC-4 | `test_invoice_payment_failed_enqueues_day1_notification` |
| US-020 AC-5 | `test_invoice_payment_failed_enqueues_day6_reminder_with_eta` |
| US-020 AC-6 | `test_invoice_payment_succeeded_exits_grace_period` |
| US-020 AC-7 | `test_subscription_deleted_cancels_and_downgrades_to_free` |
| US-020 AC-8 | `test_subscription_updated_webhook_fires_downgraded_analytics_immediately` |
| US-020 AC-9 | `test_webhook_invalid_signature_returns_400` |
| US-020 AC-10 | `test_duplicate_webhook_returns_200_without_state_mutation` |
| US-020 AC-11 | `test_webhook_returns_200_on_success` |
| US-020 AC-12 | `test_duplicate_webhook_returns_200_not_4xx` |
| US-020 AC-13 | `test_stripe_event_inserted_before_subscription_mutation` |
| US-020 AC-14 | `test_webhook_invalidates_subscription_cache` |
| US-020 AC-15 | `test_unrecognized_event_type_returns_200` |

**Fixtures / test doubles**:

```python
# conftest.py imports (from tests/integration/fixtures/ owned by S0-B)
# db: Session — real PostgreSQL test DB with S1-A migrations applied
# redis_client — real Redis test instance
# async_client: AsyncClient — HTTPX test client wrapping FastAPI app

# Fixtures defined in tests/sessions/test_s2_e.py:

@pytest.fixture
def free_user_with_subscription(db):
    """Creates a User row and a free-tier Subscription row."""
    user = User(email="test@example.com", role="user", ...)
    db.add(user)
    sub = Subscription(user_id=user.id, tier_id="free", billing_state="Active", ...)
    db.add(sub)
    db.commit()
    return user, sub

@pytest.fixture
def pro_user_with_stripe_subscription(db):
    """Creates a User and Pro-tier Subscription with Stripe IDs set."""
    user = User(email="pro@example.com", role="user", ...)
    sub = Subscription(
        user_id=user.id,
        tier_id="pro",
        billing_state="Active",
        stripe_customer_id="cus_test_xxx",
        stripe_subscription_id="sub_test_pro_001",
        current_period_end=datetime.utcnow() + timedelta(days=30),
    )
    db.add_all([user, sub])
    db.commit()
    return user, sub

@pytest.fixture
def signed_webhook_payload():
    """Factory that returns (json_bytes, sig_header) for a given event dict."""
    def _make(event_dict: dict) -> tuple[bytes, str]:
        payload = json.dumps(event_dict).encode()
        timestamp = int(time.time())
        sig = stripe.WebhookSignature.generate_header(
            timestamp=timestamp,
            payload=payload.decode(),
            secret=TEST_WEBHOOK_SECRET,  # from os.environ["STRIPE_WEBHOOK_SECRET"]
        )
        return payload, sig
    return _make

# Mocks (patched at module level for each test):
# - unittest.mock.patch("backend.app.workers.notification.tasks.send_grace_period_started_email")
# - unittest.mock.patch("backend.app.workers.notification.tasks.send_grace_period_reminder_email")
# - unittest.mock.patch("backend.app.analytics.events.emit_subscription_upgraded")
# - unittest.mock.patch("backend.app.analytics.events.emit_subscription_downgraded")
# - unittest.mock.patch("stripe.checkout.Session.create", return_value=MOCK_CHECKOUT_SESSION)
```

**Pre-conditions**:

- S1-A migrations must have been applied to the test DB (Alembic `alembic upgrade head`)
- Tier seed data (`seed_tiers.py` — S1-A) must be present: rows for `free`, `pro`, `team` in `tier` table
- Environment variables: `STRIPE_SECRET_KEY=sk_test_xxx`, `STRIPE_WEBHOOK_SECRET=whsec_test_xxx`, `STRIPE_PRO_PRICE_ID=price_pro_test`, `STRIPE_TEAM_PRICE_ID=price_team_test`
- Redis test instance running (from `tests/integration/fixtures/redis.py`, S0-B)

**Isolation rule**: All external Stripe API calls are mocked. DB and Redis are real but use isolated test databases (created/destroyed per test session by S0-B fixtures). No dependency on S2-A, S2-B, S2-C, S2-D, S2-M, or S3-F having merged. The notification tasks are mocked, so S2-M need not exist. Analytics emitter functions are mocked, so S1-E module must be importable (it is, as it's Phase 1).

---

##### Checkpoint

`GET /subscription` returns the authenticated user's current tier and billing state; `POST /subscription/checkout` returns a valid Stripe Checkout URL; and `POST /webhooks/stripe` processes `checkout.session.completed` to upgrade the subscription tier in the DB, invalidate the Redis cache, and return `200` — verifiable by seeding a free-tier user, posting a signed `checkout.session.completed` event, and observing the subscription record transition to `tier_id=pro` / `billing_state=Active`.

**Shippability claim**: This PR is independently mergeable to main even if no other session in the same wave (S2-A through S2-M) has merged.

---

##### Output and handoff

| Export | Kind | Shape | Consumed By | Load-bearing? |
|---|---|---|---|---|
| `GET /subscription` endpoint | HTTP route | `SubscriptionResponse { id, tier_id, billing_state, current_period_end, grace_period_start, stripe_subscription_id }` | S3-F (polling after checkout) | [LOAD-BEARING] |
| `POST /subscription/checkout` endpoint | HTTP route | Request: `{ tier_id: 'pro' \| 'team' }` → Response: `{ checkout_url: str, session_id: str }` | S3-F (`CheckoutRedirect.tsx`) | [LOAD-BEARING] |
| `POST /webhooks/stripe` endpoint | HTTP route | Raw Stripe event body + `Stripe-Signature` header → `200` | Stripe (external) | [LOAD-BEARING] |
| `subscription:flags:{user_id}` Redis key | Redis cache entry | `{ tier_id, billing_state, monthly_drawing_limit, revision_comparison, team_library }` | S1-B middleware (every authenticated request); S2-B free tier counter | [LOAD-BEARING] |
| `billing_state_machine.py::BillingStateMachine` | Python class | `transition(subscription, new_state) -> Subscription` | Internal to S2-E only | No |
| `billing_state_machine.py::InvalidTransitionError` | Python exception class | `class InvalidTransitionError(Exception)` | Internal to S2-E only; could be imported by S4-A tests | No |
| `stripe_event_idempotency.py::check_and_store` | Python function | `(db: Session, event_id: str, event_type: str) -> bool` (True = new, False = duplicate) | Internal to S2-E; S4-A (`test_stripe_lifecycle.py`) | No |

---

```json
{
  "test": {
    "cmd": "pytest tests/sessions/test_s2_e.py -v",
    "file": "tests/sessions/test_s2_e.py"
  },
  "checkpoint": "GET /subscription returns the authenticated user's current tier and billing state; POST /subscription/checkout returns a valid Stripe Checkout URL; and POST /webhooks/stripe processes checkout.session.completed to upgrade the subscription tier in the DB, invalidate the Redis cache, and return 200.",
  "manualAcs": [
    {
      "id": "US-020-AC-16",
      "text": "Billing state machine InvalidTransitionError raised for illegal transition (e.g., Canceled → Grace), not silently skipped."
    },
    {
      "id": "US-020-AC-17",
      "text": "Stripe tier activation (reflected in GET /subscription) occurs within 30 seconds of checkout.session.completed in staging."
    }
  ],
  "exports": [
    {
      "kind": "module",
      "name": "backend/app/api/routers/subscription",
      "shape": "backend/app/api/routers/subscription.py"
    },
    {
      "kind": "module",
      "name": "backend/app/api/routers/stripe_webhook",
      "shape": "backend/app/api/routers/stripe_webhook.py"
    },
    {
      "kind": "function",
      "name": "get_subscription_for_user",
      "shape": "(user_id: str, db: Session) -> Subscription"
    },
    {
      "kind": "function",
      "name": "check_and_store",
      "shape": "(db: Session, event_id: str, event_type: str) -> bool"
    },
    {
      "kind": "type",
      "name": "SubscriptionResponse",
      "shape": "{ id: str; tier_id: str; billing_state: str; current_period_end: Optional[datetime]; grace_period_start: Optional[datetime]; stripe_subscription_id: Optional[str]; stripe_customer_id: Optional[str] }"
    },
    {
      "kind": "type",
      "name": "CheckoutResponse",
      "shape": "{ checkout_url: str; session_id: str }"
    },
    {
      "kind": "type",
      "name": "InvalidTransitionError",
      "shape": "class InvalidTransitionError(Exception): ..."
    },
    {
      "kind": "type",
      "name": "BillingStateMachine",
      "shape": "class BillingStateMachine: transition(subscription: Subscription, new_state: str) -> Subscription"
    }
  ]
}
```