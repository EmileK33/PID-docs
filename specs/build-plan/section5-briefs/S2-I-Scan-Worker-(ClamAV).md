#### S2-I — Scan Worker (ClamAV)

**Phase 2 | Real-time/Queue | Needs: S1-A, S1-C, S1-D, S1-E**

---

##### Objective

Build the ClamAV-backed malware scan Celery worker that dequeues tasks from the `scan` queue, streams S3 objects directly into clamd, drives the `Scanning → Processing | Scan_Failed | Failed` state machine branch, publishes SSE status events via Redis pub/sub, and — on a clean scan result — enqueues the downstream ML inference job with the correct `MLInferenceJobPayload`.

---

##### Scope

**P0 MVP — all work in this session is P0.**

This session implements the malware-scanning step of the drawing processing pipeline (US-008 Scanning leg). No P1 work exists for this session; no stubs are required.

---

##### Technology constraints

- **Celery on Redis broker** — mandatory per §1.8. No in-memory queue variants (e.g., `always_eager=True`) in any non-test code path.
- **pyclamd** — Python library for TCP communication with the clamd daemon. Must NOT use subprocess calls to the `clamscan` binary; streaming bytes via `pyclamd.ClamdNetworkSocket.scan_stream()` is required for the sidecar pattern. Must NOT buffer the file to disk — infected bytes must never touch the worker filesystem.
- **FastAPI stack — Python** — no Node.js or JavaScript in this session.
- **SQLAlchemy** ORM with models from S1-A — direct SQL strings are forbidden.
- **Pydantic v2** — task payload validated on receipt.
- The ML inference job must be dispatched via `celery_app.send_task(name_string, ...)` — never by importing the ML task function directly (avoids cross-session circular imports at Python module load time).

---

##### Performance targets

None — this session owns no SLA directly. The 20-minute ML inference timeout (§1.9) is downstream and owned by S2-J. See downstream sessions for SLA accountability.

---

##### Owned files

- `backend/app/workers/scan/__init__.py`
- `backend/app/workers/scan/tasks.py`
- `backend/app/workers/scan/clamav_client.py`
- `tests/integration/test_scan_worker.py`

---

##### Read-only imports

| Owning Session | File | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/schemas/contracts.py` | `MLInferenceJobPayload`, `DrawingStatusSSEEvent`, `DrawingProcessingState` |
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` |
| S1-A | `backend/app/db/models/stored_file.py` | `StoredFile` |
| S1-A | `backend/app/db/session.py` | `SessionLocal` (or `get_db`) |
| S1-C | `backend/app/storage/s3_client.py` | `get_s3_client` |
| S1-D | `backend/app/redis/pubsub.py` | `publish_drawing_status` |
| S1-D | `backend/app/workers/queues.py` | `Queues` (queue name constants) |
| S1-D | `backend/app/workers/base.py` | `BaseTask` |
| S1-E | `backend/app/analytics/events.py` | *(available but not invoked — no analytics events are fired by the scan worker per §1.10; this import exists only for awareness)* |

---

##### Do not touch

- `backend/app/main.py` — entry point, owned by S0-A
- `backend/app/config.py` — config, owned by S0-A
- `backend/app/api/routers/__init__.py` — router registry, owned by S0-A
- `backend/app/api/routers/_stubs.py` — placeholder endpoints, owned by S0-A
- `backend/app/workers/celery_app.py` — Celery app factory, owned by S0-A
- `backend/app/workers/queues.py` — queue routing config, owned by S1-D
- `backend/app/workers/base.py` — base task class, owned by S1-D
- `backend/app/redis/pubsub.py` — owned by S1-D
- `backend/app/redis/client.py` — owned by S1-D
- `backend/app/redis/cache.py` — owned by S1-D
- `backend/app/storage/s3_client.py` — owned by S1-C
- `backend/app/storage/presigned.py` — owned by S1-C
- `backend/app/storage/hashing.py` — owned by S1-C
- `backend/app/storage/blocklist.py` — owned by S1-C
- All `backend/app/db/models/*.py` — owned by S1-A
- All `backend/app/analytics/*.py` — owned by S1-E
- `backend/app/workers/ingest/` — owned by S2-H
- `backend/app/workers/ml/` — owned by S2-J
- `backend/app/workers/export/` — owned by S2-K
- `backend/app/workers/gdpr/` — owned by S2-L
- `backend/app/workers/notification/` — owned by S2-M
- All `backend/app/api/routers/*.py` — owned by respective S2-* sessions
- All `frontend/` files — owned by S1-F, S3-* sessions

---

##### Architecture context

**From §1.3 — Drawing Processing State Machine (verbatim):**

```typescript
const DRAWING_STATE_TRANSITIONS: Record<DrawingProcessingState, DrawingProcessingState[]> = {
  Pending:      ['Queued', 'Failed'],           // Pending → Queued after hash-check pass; → Failed on pre-check error
  Queued:       ['Scanning', 'Failed'],
  Scanning:     ['Processing', 'Scan_Failed', 'Failed'],
  Processing:   ['Complete', 'Failed'],
  Complete:     ['Under_Review', 'Queued'],     // → Under_Review on first correction action; → Queued on retry (shouldn't occur)
  Under_Review: ['Queued'],                     // → Queued on retry (edge case)
  Failed:       ['Queued'],                     // → Queued on user retry (re-uses stored file)
  Scan_Failed:  [],                             // Terminal — no retry permitted
} as const;

// Retry: re-uses existing StoredFile; no new file written to S3
```

**From §1.11 — Celery Job Queue Names (verbatim):**

| Queue | Workers | Job Types |
|---|---|---|
| `ingest` | Ingest Worker (CPU) | DWG-to-raster conversion, format detection, post-storage hash verification |
| `scan` | Scan Worker (ClamAV sidecar, CPU) | Malware scan |
| `ml_inference` | ML Worker (GPU — G4dn) | Symbol detection + table extraction |

**From §1.11 — Redis Pub/Sub Channels (verbatim):**

| Channel Pattern | Published By | Consumed By | Payload Shape |
|---|---|---|---|
| `drawing:status:{drawing_id}` | Ingest Worker, Scan Worker, ML Worker (on each state transition) | FastAPI SSE handler (`GET /drawings/{id}/status`) → client | `DrawingStatusSSEEvent` (see §1.1) |

**From §1.1 — Shared Contracts (verbatim):**

```typescript
// [CRITICAL BOUNDARY] — ML Inference Job Payload
// Written by: FastAPI (API layer at enqueue time)
// Read by: ML Worker, Ingest Worker (for job context), analytics emitters
interface MLInferenceJobPayload {
  storage_reference: string;       // S3 object key
  drawing_id: string;              // UUID
  user_id: string;                 // UUID — MUST be set at enqueue time by API layer
  page_range?: [number, number];   // optional, 1-based inclusive
}

// SSE Drawing Status Event (Redis pub/sub → client)
interface DrawingStatusSSEEvent {
  drawing_id: string;
  state: DrawingProcessingState;
  timestamp: string;               // ISO 8601 UTC
}

// Drawing Processing State Machine
type DrawingProcessingState =
  | 'Pending'
  | 'Queued'
  | 'Scanning'
  | 'Processing'
  | 'Complete'
  | 'Under_Review'
  | 'Failed'
  | 'Scan_Failed';
```

**From §1.4 — Critical Ordering Rule 5 (verbatim):**

"The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access. This is mandatory for `processing_complete` and `processing_failed` events."

**From §1.4 — Critical Ordering Rule 14 (verbatim):**

"ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts."

**From §1.7 — ClamAV Third-Party Dependency (verbatim):**

| Service | Auth Mechanism | Known Quota Limits | Risk Flags |
|---|---|---|---|
| **ClamAV** | Self-hosted sidecar | N/A | No per-scan cost; adequate for engineering file types; alternative: Trend Micro File Security for enterprise compliance certification |

**From §1.8 — Technology Stack (verbatim):**

| Layer | Selected Technology | Architecturally Irreversible Because |
|---|---|---|
| **Async Workers** | Celery on Redis broker | Durable persistent queue (NFR-7); Redis already required for cache + SSE; Celery retry/timeout/priority support; changing broker requires worker rewrite |

**From §1.13 — P0 Feature Scope (verbatim):**

"US-008: Processing state machine (Pending → Queued → Scanning → Processing → Complete/Failed/Scan_Failed) with live SSE/poll status updates and in-app notifications"

"Malware scanning via ClamAV sidecar on Ingest Worker"

---

##### User stories and acceptance criteria

The scan worker implements the Scanning leg of US-008. The full governing spec text is presented verbatim above in Architecture context. The following acceptance criteria are derived directly from §1.3 state transitions, §1.4 ordering rules, §1.11 runtime patterns, and §1.1 shared contracts.

**US-008 — Drawing Processing State Machine (Scan Worker Subset)**

From §1.13 P0 scope (verbatim): "US-008: Processing state machine (Pending → Queued → Scanning → Processing → Complete/Failed/Scan_Failed) with live SSE/poll status updates and in-app notifications"

From §1.13 P0 scope (verbatim): "Malware scanning via ClamAV sidecar on Ingest Worker"

**AC-1 — Clean transition to Processing:** When a scan task is received for a drawing whose `processing_state` is `Scanning` and ClamAV reports the streamed file bytes as clean (no infection found), the drawing record's `processing_state` is updated to `Processing` in the database and committed before any subsequent action.

**AC-2 — SSE event on Processing transition:** Immediately after the DB commit to `Processing`, the worker publishes a `DrawingStatusSSEEvent` to the Redis channel `drawing:status:{drawing_id}` with `state="Processing"` and an ISO 8601 UTC timestamp.

**AC-3 — ML inference job enqueued on clean scan:** After transitioning to `Processing`, the worker enqueues a task carrying `MLInferenceJobPayload` (with `drawing_id`, `storage_reference`, `user_id`, and no `page_range`) to the Celery `ml_inference` queue. The `user_id` field is taken directly from the scan task payload.

**AC-4 — Infected transition to Scan_Failed:** When ClamAV reports the file as infected (malware detected), the drawing record's `processing_state` is updated to `Scan_Failed` and committed.

**AC-5 — SSE event on Scan_Failed transition:** Immediately after the DB commit to `Scan_Failed`, the worker publishes a `DrawingStatusSSEEvent` to `drawing:status:{drawing_id}` with `state="Scan_Failed"` and an ISO 8601 UTC timestamp.

**AC-6 — No ML job on infected file:** When ClamAV reports infection, no ML inference job is enqueued to any queue.

**AC-7 — Scan_Failed is terminal, no Celery retry:** When malware is detected, the Celery task completes (ACKs) after setting `Scan_Failed`. No `self.retry()` call is made, and no `autoretry_for` mechanism fires. The state `Scan_Failed: []` (§1.3) means no further state transitions are possible.

**AC-8 — ClamAV transient error triggers Celery retry:** When the ClamAV daemon is unreachable (connection refused, socket timeout, `pyclamd.ConnectionError`), the Celery task retries automatically. The drawing remains in `Scanning` state during retries. Retry count does not exceed `max_retries=3`.

**AC-9 — Max retries exhausted → Failed state:** When all 3 Celery retries for a ClamAV connection error are exhausted (`MaxRetriesExceededError`), the drawing's `processing_state` is updated to `Failed` and committed.

**AC-10 — SSE event on Failed transition (after retries):** After committing the `Failed` state, the worker publishes a `DrawingStatusSSEEvent` to `drawing:status:{drawing_id}` with `state="Failed"` and an ISO 8601 UTC timestamp.

**AC-11 — user_id from task payload, never from DB:** The `user_id` written into the `MLInferenceJobPayload` (AC-3) is sourced exclusively from the inbound scan task payload dict. No database query for `user_id` is made inside the scan worker task function.

**AC-12 — DrawingStatusSSEEvent payload shape:** Every `DrawingStatusSSEEvent` published to Redis contains exactly the three fields `drawing_id` (string UUID), `state` (a valid `DrawingProcessingState` literal), and `timestamp` (ISO 8601 UTC string, e.g., `"2024-01-15T10:30:00.000000Z"`). No additional or missing fields.

**AC-13 — ClamAVClient.ping() behaviour:** `ClamAVClient.ping()` returns `True` when a TCP connection to clamd succeeds and clamd responds to a PING command. It raises `ClamAVConnectionError` (a custom exception defined in `clamav_client.py`) when the connection fails.

**AC-14 — ClamAVClient.scan_stream() clean result:** `ClamAVClient.scan_stream(stream)` returns a `ScanResult` with `clean=True` and `infection=None` when `pyclamd` returns no infection.

**AC-15 — ClamAVClient.scan_stream() infected result:** `ClamAVClient.scan_stream(stream)` returns a `ScanResult` with `clean=False` and a non-`None` `infection` string (the malware name) when `pyclamd` reports a positive detection.

**AC-16 — Idempotent state guard:** If the drawing's `processing_state` is not `Scanning` when the task function begins (e.g., duplicate delivery, re-queued task after an earlier partial success), the task exits immediately: no DB mutation, no Redis publish, no ML job enqueue. A warning is logged with drawing_id and current state.

**AC-17 — Persistent queue registration:** The `scan_drawing` Celery task is bound to the `scan` queue (not the default queue, not in-memory). The ML inference job is dispatched to the `ml_inference` queue via `celery_app.send_task(...)`. Both queue names must match the constants in `backend/app/workers/queues.py` (S1-D).

---

##### UX and design specification

N/A — this is a backend Celery worker session with no frontend component.

---

##### Critical implementation notes

- **`Scan_Failed` is strictly terminal — never retry after malware detection** (§1.3: `Scan_Failed: []`): Do NOT configure `autoretry_for`, `bind`-based `self.retry()`, or any Celery retry mechanism on the malware-detected code path. The task must call `session.commit()` to set `Scan_Failed` and then return normally (ACK). Any retry attempt after malware detection would violate the state machine contract and is a silent correctness failure.

- **`user_id` must NOT be resolved via DB query inside the scan worker** (§1.4 Rule 5: "so that worker processes can include it in emitted events without requiring a database lookup or session access"): The `user_id` must flow unchanged from the inbound scan payload dict into the outbound `MLInferenceJobPayload`. A DB lookup for `user_id` appears to work in testing but creates a GDPR/deleted-user correctness failure in production.

- **ML inference job dispatch: string-based `send_task` only** (§1.4 Rule 14): Use `celery_app.send_task("backend.app.workers.ml.tasks.run_ml_inference", args=[payload_dict], queue=Queues.ML_INFERENCE)`. Do NOT `from backend.app.workers.ml.tasks import run_ml_inference` — this creates a Python module circular import between S2-I and S2-J (same phase, different owners), which silently fails at worker startup.

- **Atomic DB commit before SSE publish**: The `session.commit()` updating `processing_state` must succeed before calling `publish_drawing_status(...)`. If the commit raises an exception, the SSE publish must NOT occur. The reversed order — SSE published, then DB fails — produces phantom state in connected clients with no recovery path.

- **Stream S3 object directly to pyclamd — no disk write**: Retrieve the S3 object using `get_object(Bucket=..., Key=...)['Body']` and pass the streaming body bytes directly to `ClamdNetworkSocket.scan_stream()`. Writing to a temporary file is forbidden: it defeats the no-disk-storage security property and risks infected bytes persisting if the worker crashes.

- **Celery task must be `bind=True`**: Required to call `self.retry(exc=..., countdown=30)` and inspect `self.request.retries` for the max-retries-exceeded path. A non-bound task has no `self` reference and cannot distinguish retry counts.

- **Max-retries-exceeded detection pattern**: After catching a ClamAV connection error, call `raise self.retry(exc=exc, countdown=30, max_retries=3)` inside a `try/except celery.exceptions.MaxRetriesExceededError` block. On `MaxRetriesExceededError`, perform the `Failed` state transition and SSE publish. Do NOT let `MaxRetriesExceededError` propagate to Celery unhandled — that re-queues the task.

- **State guard is a read-for-check, not a lock**: The `Scanning` state guard at task entry should use a `SELECT` then check, not `SELECT FOR UPDATE`. Scan worker tasks are not expected to race (each drawing has one scan task). A `SELECT FOR UPDATE` escalation is unnecessary and creates lock contention.

- **SSE timestamp must be UTC with 'Z' suffix**: `DrawingStatusSSEEvent.timestamp` must be an ISO 8601 UTC string (e.g., `datetime.now(timezone.utc).isoformat()`). Python's `datetime.utcnow().isoformat()` produces a naive datetime string without timezone info — this silently produces incorrect timestamps in consumers. Always use `timezone.utc`.

- **ClamAV connection config from environment — no hard failures**: Read `CLAMAV_HOST` (default: `"clamav"`) and `CLAMAV_PORT` (default: `3310`) from environment variables. These are not in §1.12's mandatory manifest. Missing values must fall back to defaults silently — the scan worker must not refuse to start if these are absent.

- **Do not emit any analytics events from the scan worker** (§1.10): The `processing_complete` and `processing_failed` PostHog events are the ML Worker's (S2-J's) responsibility. Firing them from the scan worker would produce duplicate or incorrect events (e.g., `processing_complete` before ML inference has run).

- **`ScanJobPayload` is a load-bearing cross-session contract**: S2-H (Ingest Worker) enqueues tasks using the shape defined in this session's `ScanJobPayload`. Once merged, the field names `drawing_id`, `storage_reference`, and `user_id` must not be renamed.

---

##### Mocking contract

This is a backend worker session. It consumes internal queue payloads and service interfaces, not HTTP endpoints.

**Inbound — from S2-H Ingest Worker (Celery task payload, runtime only, no compile-time import):**

The ingest worker enqueues a task to the `scan` queue with this exact payload shape. S2-H must match this shape:

```python
# ScanJobPayload — written by S2-H, consumed by S2-I scan_drawing task
{
    "drawing_id": str,           # UUID string, e.g. "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    "storage_reference": str,    # S3 object key, e.g. "uploads/3fa85f64-5717-4562-b3fc-2c963f66afa6/drawing.pdf"
    "user_id": str,              # UUID string — set at API layer upload-complete time per §1.4 Rule 5
}
```

**Outbound — to S2-J ML Worker (Celery `send_task` dispatch, `ml_inference` queue):**

Dispatched via `celery_app.send_task("backend.app.workers.ml.tasks.run_ml_inference", args=[payload], queue="ml_inference")`:

```python
# MLInferenceJobPayload (§1.1) — written by S2-I, consumed by S2-J
{
    "storage_reference": str,    # S3 object key (passed through from scan payload)
    "drawing_id": str,           # UUID string
    "user_id": str,              # UUID string — from scan payload, never from DB
    "page_range": None,          # Not set at scan time; ML worker treats None as full document
}
```

**Outbound — to S2-B SSE handler via Redis (pub/sub, `drawing:status:{drawing_id}` channel):**

Published via `publish_drawing_status(drawing_id, state, timestamp)` (S1-D):

```python
# DrawingStatusSSEEvent (§1.1) — JSON-serialised, published by S2-I, consumed by S2-B
{
    "drawing_id": str,           # UUID string
    "state": str,                # Literal: "Processing" | "Scan_Failed" | "Failed"
    "timestamp": str,            # ISO 8601 UTC, e.g. "2024-01-15T10:30:00.000000+00:00"
}
```

**Test doubles used in `tests/integration/test_scan_worker.py`:**

| Double | Type | Purpose |
|---|---|---|
| `mock_clamav_clean` | `MagicMock` | `ClamAVClient.scan_stream()` returns `ScanResult(clean=True, infection=None)` |
| `mock_clamav_infected` | `MagicMock` | `ClamAVClient.scan_stream()` returns `ScanResult(clean=False, infection="Eicar-Test-Signature")` |
| `mock_clamav_error` | `MagicMock` side_effect | `ClamAVClient.scan_stream()` raises `ClamAVConnectionError` |
| `mock_clamav_ping_ok` | `MagicMock` return_value=True | `ClamAVClient.ping()` returns True |
| `mock_clamav_ping_fail` | `MagicMock` side_effect | `ClamAVClient.ping()` raises `ClamAVConnectionError` |
| `mock_s3_stream` | `MagicMock` | `get_s3_client().get_object(...)['Body']` returns a bytes-like mock |
| `fake_redis` | `fakeredis.FakeRedis()` | Redis pub/sub; assert `publish_drawing_status` writes correct channel + payload |
| `mock_celery_send_task` | `unittest.mock.patch("backend.app.workers.scan.tasks.celery_app.send_task")` | Capture ML inference job dispatch; assert payload shape |
| `db_session` | pytest fixture from `tests/integration/fixtures/db.py` (S0-B) | Test DB with S1-A schema |
| `scanning_drawing_factory` | pytest fixture | Creates a `Drawing` row with `processing_state='Scanning'`, `owner_user_id`, `stored_file_id` populated |

---

##### Acceptance criteria checklist

- [ ] Drawing in `Scanning` state with clean file → `processing_state` updated to `Processing` in DB [US-008 AC-1]
- [ ] Clean scan → `DrawingStatusSSEEvent` with `state="Processing"` published to `drawing:status:{drawing_id}` [US-008 AC-2]
- [ ] Clean scan → `MLInferenceJobPayload` with `drawing_id`, `storage_reference`, `user_id` enqueued to `ml_inference` queue [US-008 AC-3]
- [ ] Infected file → `processing_state` updated to `Scan_Failed` in DB [US-008 AC-4]
- [ ] Infected file → `DrawingStatusSSEEvent` with `state="Scan_Failed"` published to `drawing:status:{drawing_id}` [US-008 AC-5]
- [ ] Infected file → no ML inference job enqueued to any Celery queue [US-008 AC-6]
- [ ] Malware detection → no `self.retry()` call made; task ACKs after setting `Scan_Failed` [US-008 AC-7]
- [ ] ClamAV connection error → task retries automatically via Celery; drawing remains `Scanning` during retries [US-008 AC-8]
- [ ] All 3 retries exhausted (ClamAV unavailable) → `processing_state` updated to `Failed` in DB [US-008 AC-9]
- [ ] Retries exhausted → `DrawingStatusSSEEvent` with `state="Failed"` published to `drawing:status:{drawing_id}` [US-008 AC-10]
- [ ] `user_id` in enqueued `MLInferenceJobPayload` matches value from inbound scan task payload; no DB query for user_id [US-008 AC-11]
- [ ] All published `DrawingStatusSSEEvent` messages contain exactly `drawing_id`, `state`, and ISO 8601 UTC `timestamp` [US-008 AC-12]
- [ ] `ClamAVClient.ping()` returns `True` when clamd reachable [US-008 AC-13]
- [ ] `ClamAVClient.scan_stream()` returns `ScanResult(clean=True, infection=None)` for a clean file [US-008 AC-14]
- [ ] `ClamAVClient.scan_stream()` returns `ScanResult(clean=False, infection="<name>")` for an infected file [US-008 AC-15]
- [ ] Drawing not in `Scanning` state → task exits without DB mutation, SSE publish, or ML enqueue [US-008 AC-16]
- [ ] `scan_drawing` task registered on `scan` queue; ML job dispatched to `ml_inference` queue (both matching `Queues` constants from S1-D) [US-008 AC-17]

---

##### Independent Test

- **Test file path** (TDD — written first, must fail before implementation): `tests/integration/test_scan_worker.py`
- **Exact CI command**: `pytest tests/integration/test_scan_worker.py -v`

**AC → assertion mapping:**

| AC | `test_*` function name |
|---|---|
| US-008 AC-1 | `test_transitions_to_processing_when_file_is_clean` |
| US-008 AC-2 | `test_publishes_sse_processing_on_clean_scan` |
| US-008 AC-3 | `test_enqueues_ml_inference_job_on_clean_scan` |
| US-008 AC-4 | `test_transitions_to_scan_failed_when_infected` |
| US-008 AC-5 | `test_publishes_sse_scan_failed_when_infected` |
| US-008 AC-6 | `test_no_ml_job_enqueued_when_infected` |
| US-008 AC-7 | `test_scan_failed_is_terminal_no_celery_retry` |
| US-008 AC-8 | `test_retries_on_clamav_connection_error` |
| US-008 AC-9 | `test_transitions_to_failed_after_max_retries_exhausted` |
| US-008 AC-10 | `test_publishes_sse_failed_after_max_retries_exhausted` |
| US-008 AC-11 | `test_user_id_taken_from_task_payload_not_db` |
| US-008 AC-12 | `test_sse_event_payload_shape_is_correct` |
| US-008 AC-13 | `test_clamav_client_ping_returns_true_when_reachable` |
| US-008 AC-14 | `test_clamav_client_scan_stream_returns_clean_result` |
| US-008 AC-15 | `test_clamav_client_scan_stream_returns_infected_result` |
| US-008 AC-16 | `test_noop_when_drawing_not_in_scanning_state` |
| US-008 AC-17 | `test_task_registered_on_scan_queue_and_ml_dispatched_to_ml_inference_queue` |

**Fixtures / test doubles:**

```python
# tests/integration/test_scan_worker.py — fixture inventory

@pytest.fixture
def db_session():
    # From tests/integration/fixtures/db.py (S0-B)
    # Provides a SQLAlchemy Session against test DB with S1-A schema applied
    ...

@pytest.fixture
def scanning_drawing(db_session):
    # Creates Drawing(processing_state='Scanning', owner_user_id=<uuid>, stored_file_id=<uuid>)
    # Also creates StoredFile(object_key='uploads/test/drawing.pdf', bucket='test-bucket')
    # Returns (drawing, stored_file)
    ...

@pytest.fixture
def fake_redis():
    # fakeredis.FakeRedis() instance; injected via monkeypatch into pubsub module
    ...

@pytest.fixture
def mock_s3_stream(mocker):
    # Patches get_s3_client().get_object(...) to return {'Body': io.BytesIO(b'fake-pdf-bytes')}
    ...

@pytest.fixture
def mock_clamav_clean(mocker):
    # Patches ClamAVClient.scan_stream to return ScanResult(clean=True, infection=None)
    ...

@pytest.fixture
def mock_clamav_infected(mocker):
    # Patches ClamAVClient.scan_stream to return ScanResult(clean=False, infection="Eicar-Test-Signature")
    ...

@pytest.fixture
def mock_clamav_error(mocker):
    # Patches ClamAVClient.scan_stream to raise ClamAVConnectionError on first N calls
    ...

@pytest.fixture
def mock_celery_send_task(mocker):
    # mocker.patch("backend.app.workers.scan.tasks.celery_app.send_task")
    # Returns MagicMock; assert_called_once_with(name, args=[payload], queue=...)
    ...
```

All mock `ScanResult` shapes must match `ScanResult` as defined in `clamav_client.py`:
```python
# Exact shape — must match implementation
@dataclass
class ScanResult:
    clean: bool
    infection: Optional[str]  # None when clean; malware name string when infected
```

**Pre-conditions:**

- S1-A DB migration applied (all tables including `drawing`, `stored_file` created; `tier` and `entity_class` seed data present)
- `DATABASE_URL` pointing to test PostgreSQL instance (from `tests/integration/fixtures/db.py`)
- `REDIS_URL` pointing to test Redis instance (fakeredis or test container from `tests/integration/fixtures/redis.py`)
- `S3_BUCKET_NAME=test-bucket`, `S3_REGION=us-east-1` set in test environment
- `CLAMAV_HOST` and `CLAMAV_PORT` not required for tests — `ClamAVClient` is fully mocked
- No real clamd daemon required in CI

**Isolation rule:**

This test passes when only S2-I is merged in its wave. It does not require S2-H (ingest worker) — the `scan_drawing` task is invoked directly in tests without going through the queue. It does not require S2-J (ML worker) — the `celery_app.send_task` call is mocked. All Phase 1 prerequisites (S1-A, S1-C, S1-D) are already merged before Phase 2 begins.

---

##### Checkpoint

- **One-sentence observable outcome**: A `Drawing` record seeded in `Scanning` state and submitted directly to the `scan_drawing` Celery task transitions to `Processing` (clean file), `Scan_Failed` (infected file), or `Failed` (ClamAV connection error after 3 retries), with a corresponding `DrawingStatusSSEEvent` verifiable in the Redis `drawing:status:{drawing_id}` pub/sub channel for each case.
- **Shippability claim**: This PR is independently mergeable to main even if no other session in the same wave has merged. All S2-* sibling sessions (S2-H, S2-J, etc.) are decoupled at runtime via Celery queue names and Redis channels; no cross-session Python import is introduced.

---

##### Output and handoff

| Export | Kind | Shape | Consuming Session(s) | Load-bearing? |
|---|---|---|---|---|
| `ScanJobPayload` | Pydantic model | `{ drawing_id: str, storage_reference: str, user_id: str }` from `backend/app/workers/scan/tasks.py` | S2-H (Ingest Worker — must enqueue tasks with this exact field set) | **[LOAD-BEARING]** |
| `scan_drawing` | Celery task (string name: `"backend.app.workers.scan.tasks.scan_drawing"`) | `(payload: dict) -> None` | S2-H (Ingest Worker — `celery_app.send_task("backend.app.workers.scan.tasks.scan_drawing", ...)`) | **[LOAD-BEARING]** |
| `ClamAVClient` | class | `__init__(host: str, port: int)`, `ping() -> bool`, `scan_stream(stream: IO[bytes]) -> ScanResult` from `backend/app/workers/scan/clamav_client.py` | S2-I internal only | — |
| `ScanResult` | dataclass | `{ clean: bool, infection: Optional[str] }` from `backend/app/workers/scan/clamav_client.py` | S2-I internal only | — |
| `ClamAVConnectionError` | exception class | `class ClamAVConnectionError(Exception)` from `backend/app/workers/scan/clamav_client.py` | S2-I internal only | — |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/test_scan_worker.py -v",
    "file": "tests/integration/test_scan_worker.py"
  },
  "checkpoint": "A Drawing record in Scanning state submitted directly to the scan_drawing Celery task transitions to Processing (clean file), Scan_Failed (infected file), or Failed (ClamAV connection error after 3 retries), with a corresponding DrawingStatusSSEEvent verifiable in the Redis drawing:status:{drawing_id} pub/sub channel for each case.",
  "manualAcs": [],
  "exports": [
    {
      "kind": "type",
      "name": "ScanJobPayload",
      "shape": "{ drawing_id: str; storage_reference: str; user_id: str }"
    },
    {
      "kind": "function",
      "name": "scan_drawing",
      "shape": "(payload: dict) -> None  /* Celery task; registered name: 'backend.app.workers.scan.tasks.scan_drawing'; queue: 'scan' */"
    },
    {
      "kind": "type",
      "name": "ScanResult",
      "shape": "{ clean: bool; infection: Optional[str] }"
    },
    {
      "kind": "type",
      "name": "ClamAVConnectionError",
      "shape": "class ClamAVConnectionError(Exception)"
    },
    {
      "kind": "module",
      "name": "backend/app/workers/scan/tasks.py",
      "shape": "backend/app/workers/scan/tasks.py"
    },
    {
      "kind": "module",
      "name": "backend/app/workers/scan/clamav_client.py",
      "shape": "backend/app/workers/scan/clamav_client.py"
    }
  ]
}
```