---

#### S1-E — Analytics Emitter (PostHog)

**Phase 1 | Infrastructure | Needs: S0-A, S0-B**

##### Objective

Provide a typed, non-blocking analytics emission layer (PostHog client + dead-letter retry queue + typed event functions for all nine MVP events) that downstream Phase 2 sessions call to record user/system events.

##### Scope

P0 MVP. All nine events listed in §1.10 are P0 and must be implemented. No P1 work in this session.

##### Technology constraints

- **Must use**: PostHog (Python SDK `posthog>=3.0`). Self-hosted-compatible — must respect `POSTHOG_HOST` env var.
- **Must use**: Redis (via session S1-D's client) for dead-letter queue persistence.
- **Must NOT use**: Any other analytics SDK (Segment, Amplitude, Mixpanel) — PostHog is the only sanctioned analytics provider per §1.7 / §1.8.
- **Must NOT**: block request/response cycle on PostHog network calls. Emission must be fire-and-forget (background task / thread / queue).
- **Must NOT**: surface analytics failures to users — analytics failure must not raise into request handlers.

##### Performance targets

None — see downstream sessions. (Events must be non-blocking; this is a correctness constraint, not an SLA.)

##### Owned files

- `backend/app/analytics/__init__.py`
- `backend/app/analytics/posthog_client.py`
- `backend/app/analytics/events.py`
- `backend/app/analytics/dead_letter.py`
- `tests/integration/test_analytics.py`

##### Read-only imports

- From **S0-A**: `backend/app/config.py` — env var accessors (`POSTHOG_API_KEY`, `POSTHOG_HOST`, `ENVIRONMENT`); `backend/app/schemas/contracts.py` — types `TierId`, `ExportFormat` (for typed event signatures).
- From **S0-B**: `tests/integration/conftest.py` — pytest fixtures (db, redis container handles) for the test file.

Note: S1-D (Redis client) is **not** a prerequisite per the session plan. This session must therefore use the raw `REDIS_URL` env var directly via `redis-py` for its dead-letter queue, and not import from `backend/app/redis/*` (which is owned by S1-D and may not exist when this session runs in isolation). If S1-D has merged, callers may later inject its client, but this session's code must function standalone.

##### Do not touch

- `backend/app/main.py`, `backend/app/api/routers/__init__.py`, `backend/app/api/routers/_stubs.py` (S0-A scaffold)
- `frontend/src/router.tsx`, `frontend/src/App.tsx` (S0-A scaffold)
- Any file owned by S1-A, S1-B, S1-C, S1-D, S1-F, or any Phase 2/3/4 session
- All test fixture files outside `tests/integration/test_analytics.py`

##### Architecture context

Verbatim from §1.10:

> All nine events must be instrumented. Events must be non-blocking and asynchronous. Analytics failure must not surface to users. Server-side retry queue (dead-letter) recommended.

Verbatim from §1.7 (PostHog row):

> **PostHog** | API key | Self-hostable; no hard quota | GDPR-compliant; self-hostable

Verbatim from §1.8 (Analytics row):

> **Analytics** | PostHog | Self-hostable, GDPR-compliant, named events with properties

Verbatim from §1.12 (env vars):

> `POSTHOG_API_KEY` | string | Any non-empty string | None | Log warning; analytics disabled | Log warning; analytics disabled
> `POSTHOG_HOST` | string | HTTPS URL | `https://app.posthog.com` | Warn; use default | Use default

Verbatim from §1.4 (ordering rules touching analytics):

> 5. **user_id written into job payload at enqueue time by API layer.** "The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access. This is mandatory for `processing_complete` and `processing_failed` events."

##### User stories and acceptance criteria

This session has no direct user-story ACs; it implements infrastructure consumed by US-010 (analytics events), which is delivered through Phase 2 sessions that call into the emitters here.

Verbatim relevant scope item from §1.13 (P0):

> US-010: All nine structured analytics events (drawing_uploaded, processing_complete, processing_failed, correction_action, export_initiated, export_downloaded, free_limit_reached, subscription_upgraded, subscription_downgraded)

The full event contract table from §1.10 is included verbatim under "Critical implementation notes — event payloads" below.

##### UX and design specification

N/A — backend infrastructure session, no frontend component.

##### Critical implementation notes

**Event payloads (verbatim from §1.10):** every emitter function in `events.py` must produce a payload with EXACTLY these fields and field names.

| Event | Payload Shape | Trigger | Must NOT have happened | Must NEVER fire from |
|---|---|---|---|---|
| `drawing_uploaded` | `{ event: 'drawing_uploaded', timestamp: string (UTC ISO8601), user_id: string, drawing_id: string }` | Drawing transitions to `Queued` state after upload-complete signal | Drawing must not already be in `Queued` or later state | Browser client; ML worker |
| `processing_complete` | `{ event: 'processing_complete', timestamp: string, user_id: string, drawing_id: string }` | Drawing transitions to `Complete` state | `processing_failed` for same drawing_id in same job run | Browser client; must not resolve user_id via DB lookup in worker |
| `processing_failed` | `{ event: 'processing_failed', timestamp: string, user_id: string, drawing_id: string }` | Drawing transitions to `Failed` state (after 1 automatic retry exhausted) | `processing_complete` for same drawing_id in same job run | Browser client |
| `correction_action` | `{ event: 'correction_action', timestamp: string, user_id: string, drawing_id: string, symbol_id: string }` | User submits a reclassify, reject, restore, or manual_add correction | None | Browser client; must fire server-side on persistence |
| `export_initiated` | `{ event: 'export_initiated', timestamp: string, user_id: string, drawing_id: string, export_id: string, format: ExportFormat }` | Export job created (both sync and async) | Export file generated | Export Worker; browser client |
| `export_downloaded` | `{ event: 'export_downloaded', timestamp: string, user_id: string, drawing_id: string, export_id: string }` | User accesses pre-signed download URL | None | Export Worker |
| `free_limit_reached` | `{ event: 'free_limit_reached', timestamp: string, user_id: string, drawing_id: string, subscription_id: string }` | Free tier user attempts to initiate processing that would exceed 3/month limit | Processing job must not be queued | Browser client; must fire before upgrade prompt shown |
| `subscription_upgraded` | `{ event: 'subscription_upgraded', timestamp: string, user_id: string, subscription_id: string, previous_tier: TierId, new_tier: TierId }` | Subscription tier increases | Tier change applied before event fires | Browser client; Stripe redirect handler inline |
| `subscription_downgraded` | `{ event: 'subscription_downgraded', timestamp: string, user_id: string, subscription_id: string, previous_tier: TierId, new_tier: TierId }` | Subscription tier decreases (fires immediately at confirmation, not at period end) | None | Browser client |

**Non-negotiable constraints:**

- **Non-blocking**: every public `emit_*(...)` function must return synchronously without awaiting a network call. Use PostHog's built-in async batch sender (the default `posthog.capture()` is already async-batched) OR offload to a `concurrent.futures.ThreadPoolExecutor`. Caller must never observe added latency above ~1ms.
- **Swallow all exceptions**: every emitter must wrap PostHog send in `try/except Exception` and log at WARN. Never re-raise. Analytics failure surfacing to a user is a critical bug.
- **Timestamp**: must be ISO 8601 UTC with timezone suffix (`Z` or `+00:00`). Generated server-side via `datetime.now(timezone.utc).isoformat()`. Callers MUST NOT pass timestamps.
- **distinct_id**: PostHog requires `distinct_id`. Use `user_id` as the distinct_id for all events. For events that may genuinely lack a user (none in P0 — all nine events carry `user_id`), do not invent placeholder IDs.
- **Dead-letter queue**: on PostHog send failure (exception OR PostHog client reports error), serialize event JSON to Redis list key `analytics:dead_letter` with `RPUSH`. Cap list length at 10,000 (use `LTRIM` to keep last 10,000) to prevent unbounded growth. A retry function (`retry_dead_letter()`) drains the list with `LPOP` and re-attempts emission. This function exists but is not auto-scheduled in this session (a cron/Celery beat will invoke it; that wiring is out of scope here).
- **Disabled mode**: if `POSTHOG_API_KEY` is absent or empty, log one warning at startup and have all `emit_*` functions become no-ops (do not push to dead-letter queue either, since there is no recipient).
- **`user_id` originates from caller** for worker-emitted events (`processing_complete`, `processing_failed`) — per ordering rule #5, this session must NOT perform DB lookups to resolve `user_id`. The emitter signature takes `user_id` as a required parameter.
- **No PII**: payloads must contain only the fields listed above. Never log email, filename, or correction values into PostHog payloads.

**Silent failure modes to avoid:**

- Returning `None` from emitter on send failure but not pushing to dead-letter — events lost silently.
- Calling `posthog.capture()` then `posthog.flush()` synchronously inside a request handler — adds 100–500ms latency and defeats non-blocking guarantee.
- Allowing a missing `POSTHOG_API_KEY` to crash app startup — must warn and continue.
- Reading `user_id` from `current_user` context in `processing_*` emitters — would silently break worker-emitted events where no request context exists.

##### Mocking contract

This is a backend infrastructure session. External service contract:

- **PostHog HTTP API**: `posthog.capture(distinct_id: str, event: str, properties: dict)` — the integration test must monkeypatch `posthog.capture` (or inject a fake client) and assert the call payload shape. The real network call is not exercised in tests.

Internal contracts produced for downstream consumers (Phase 2 sessions S2-A through S2-M) — these consumers will import and call:

```python
emit_drawing_uploaded(user_id: str, drawing_id: str) -> None
emit_processing_complete(user_id: str, drawing_id: str) -> None
emit_processing_failed(user_id: str, drawing_id: str) -> None
emit_correction_action(user_id: str, drawing_id: str, symbol_id: str) -> None
emit_export_initiated(user_id: str, drawing_id: str, export_id: str, format: Literal["csv","xlsx"]) -> None
emit_export_downloaded(user_id: str, drawing_id: str, export_id: str) -> None
emit_free_limit_reached(user_id: str, drawing_id: str, subscription_id: str) -> None
emit_subscription_upgraded(user_id: str, subscription_id: str, previous_tier: str, new_tier: str) -> None
emit_subscription_downgraded(user_id: str, subscription_id: str, previous_tier: str, new_tier: str) -> None
retry_dead_letter() -> int  # returns number of events successfully re-sent
```

##### Acceptance criteria checklist

- [ ] `emit_drawing_uploaded(user_id, drawing_id)` calls `posthog.capture` with `event="drawing_uploaded"`, `distinct_id=user_id`, properties containing `user_id`, `drawing_id`, ISO-8601 UTC `timestamp` [US-010]
- [ ] `emit_processing_complete(user_id, drawing_id)` calls `posthog.capture` with `event="processing_complete"` and required fields [US-010]
- [ ] `emit_processing_failed(user_id, drawing_id)` calls `posthog.capture` with `event="processing_failed"` and required fields [US-010]
- [ ] `emit_correction_action(user_id, drawing_id, symbol_id)` emits with `symbol_id` in properties [US-010]
- [ ] `emit_export_initiated(user_id, drawing_id, export_id, format)` emits with `format` field; rejects format not in `{"csv","xlsx"}` [US-010]
- [ ] `emit_export_downloaded(user_id, drawing_id, export_id)` emits with required fields [US-010]
- [ ] `emit_free_limit_reached(user_id, drawing_id, subscription_id)` emits with `subscription_id` [US-010]
- [ ] `emit_subscription_upgraded(user_id, subscription_id, previous_tier, new_tier)` emits with both tier fields [US-010]
- [ ] `emit_subscription_downgraded(user_id, subscription_id, previous_tier, new_tier)` emits with both tier fields [US-010]
- [ ] Every emitter returns `None` and adds <5ms to caller wall-clock time (non-blocking) [tech]
- [ ] When `posthog.capture` raises any `Exception`, the emitter does NOT re-raise and the event JSON is pushed to Redis list `analytics:dead_letter` via `RPUSH` [tech]
- [ ] When `POSTHOG_API_KEY` env var is missing/empty, all emitters become silent no-ops and a single startup warning is logged [tech]
- [ ] Dead-letter queue is capped at 10,000 entries via `LTRIM` [tech]
- [ ] `retry_dead_letter()` drains queue with `LPOP`, re-sends events, returns count of successful re-sends; failed re-sends are pushed back [tech]
- [ ] Timestamps are generated server-side; emitter signatures do not accept a `timestamp` parameter [tech]
- [ ] No emitter performs a DB lookup; `user_id` is always supplied by caller [§1.4 rule 5]
- [ ] `[MANUAL]` Manual verification that events appear in PostHog dashboard in staging with `POSTHOG_API_KEY` set [tech]

##### Independent Test

- **Test file path** (TDD — written first, must fail before implementation): `tests/integration/test_analytics.py`
- **Exact CI command**: `pytest tests/integration/test_analytics.py -v`
- **AC → assertion mapping**:
  - `emit_drawing_uploaded shape` → `it("emit_drawing_uploaded captures correct event and properties")`
  - `emit_processing_complete shape` → `it("emit_processing_complete captures correct event and properties")`
  - `emit_processing_failed shape` → `it("emit_processing_failed captures correct event and properties")`
  - `emit_correction_action shape` → `it("emit_correction_action includes symbol_id")`
  - `emit_export_initiated shape` → `it("emit_export_initiated includes format field")`
  - `emit_export_downloaded shape` → `it("emit_export_downloaded captures correct event")`
  - `emit_free_limit_reached shape` → `it("emit_free_limit_reached includes subscription_id")`
  - `emit_subscription_upgraded shape` → `it("emit_subscription_upgraded includes both tier fields")`
  - `emit_subscription_downgraded shape` → `it("emit_subscription_downgraded includes both tier fields")`
  - non-blocking → `it("emitter returns within 5ms")`
  - exception → dead-letter → `it("posthog exception pushes event to redis dead_letter list")`
  - missing API key → no-op → `it("missing POSTHOG_API_KEY makes emitters no-op and logs warning")`
  - dead-letter cap → `it("dead_letter list is capped at 10000 via LTRIM")`
  - retry → `it("retry_dead_letter drains queue and re-emits")`
  - timestamp server-generated → `it("timestamp is ISO-8601 UTC and not caller-supplied")`
- **Fixtures / test doubles**:
  - `monkeypatch` on `posthog.capture` to record call args
  - `fakeredis` (or testcontainers redis from S0-B conftest) for the dead-letter queue
  - `caplog` for warning assertions
- **Pre-conditions**:
  - `REDIS_URL` set to test Redis instance (from S0-B fixtures)
  - `POSTHOG_API_KEY` set to a dummy value `test-key` for most tests; one test unsets it
  - No DB migrations required
- **Isolation rule**: passes when only S0-A + S0-B + S1-E are merged. No sibling Phase 1 session required.

##### Checkpoint

- **Observable outcome**: An operator can run `python -c "from backend.app.analytics.events import emit_drawing_uploaded; emit_drawing_uploaded('user-1','drawing-1')"` with `POSTHOG_API_KEY` set against a real PostHog instance and observe a `drawing_uploaded` event arriving in the PostHog dashboard within ~30s; with the key unset, the same call returns silently and logs a warning.
- **Shippability claim**: this PR is independently mergeable to main even if no other session in the same wave has merged.

##### Output and handoff

Exports consumed by downstream sessions:

- `backend/app/analytics/events.py` [LOAD-BEARING] — function signatures `emit_drawing_uploaded`, `emit_processing_complete`, `emit_processing_failed`, `emit_correction_action`, `emit_export_initiated`, `emit_export_downloaded`, `emit_free_limit_reached`, `emit_subscription_upgraded`, `emit_subscription_downgraded`. Consumers: S2-A, S2-B, S2-C, S2-D, S2-E, S2-F, S2-J.
- `backend/app/analytics/dead_letter.py` — `retry_dead_letter() -> int`. Consumer: future cron/beat scheduler (out of MVP scope but signature must remain stable).
- `backend/app/analytics/posthog_client.py` — internal; not for direct downstream import.

---

```json
{
  "test": { "cmd": "pytest tests/integration/test_analytics.py -v", "file": "tests/integration/test_analytics.py" },
  "checkpoint": "Calling any emit_* function with POSTHOG_API_KEY set produces a corresponding event in PostHog within ~30s; with the key unset, calls are silent no-ops that log a startup warning.",
  "manualAcs": [
    { "id": "US-010-AC-MANUAL", "text": "Manual verification that events appear in PostHog dashboard in staging with POSTHOG_API_KEY set." }
  ],
  "exports": [
    { "kind": "function", "name": "emit_drawing_uploaded", "shape": "(user_id: str, drawing_id: str) -> None" },
    { "kind": "function", "name": "emit_processing_complete", "shape": "(user_id: str, drawing_id: str) -> None" },
    { "kind": "function", "name": "emit_processing_failed", "shape": "(user_id: str, drawing_id: str) -> None" },
    { "kind": "function", "name": "emit_correction_action", "shape": "(user_id: str, drawing_id: str, symbol_id: str) -> None" },
    { "kind": "function", "name": "emit_export_initiated", "shape": "(user_id: str, drawing_id: str, export_id: str, format: Literal['csv','xlsx']) -> None" },
    { "kind": "function", "name": "emit_export_downloaded", "shape": "(user_id: str, drawing_id: str, export_id: str) -> None" },
    { "kind": "function", "name": "emit_free_limit_reached", "shape": "(user_id: str, drawing_id: str, subscription_id: str) -> None" },
    { "kind": "function", "name": "emit_subscription_upgraded", "shape": "(user_id: str, subscription_id: str, previous_tier: str, new_tier: str) -> None" },
    { "kind": "function", "name": "emit_subscription_downgraded", "shape": "(user_id: str, subscription_id: str, previous_tier: str, new_tier: str) -> None" },
    { "kind": "function", "name": "retry_dead_letter", "shape": "() -> int" },
    { "kind": "module", "name": "backend/app/analytics/events", "shape": "backend/app/analytics/events.py" },
    { "kind": "module", "name": "backend/app/analytics/dead_letter", "shape": "backend/app/analytics/dead_letter.py" }
  ]
}
```