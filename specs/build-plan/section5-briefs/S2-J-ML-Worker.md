#### S2-J — ML Worker

**Phase 2 | Real-time/Queue | Needs: S1-A, S1-C, S1-D, S1-E**

---

##### Objective

Implement the Celery-based ML inference worker that downloads processed drawings from S3, runs symbol detection, atomically persists results to the database, transitions the drawing through the `Processing → Complete | Failed` state machine, publishes SSE events via Redis, and emits the `processing_complete` / `processing_failed` analytics events — all with a 20-minute hard timeout and one automatic retry before terminal failure.

---

##### Scope

**P0 MVP** (implement fully):
- US-008: Processing state machine leg `Processing → Complete | Failed` with live SSE pub/sub
- US-010: `processing_complete` and `processing_failed` analytics events emitted from worker (user_id from job payload only)
- US-011: Automatic ML inference execution; symbol detection results with confidence scores persisted and drawing transitioned to Complete

**P1 v1.0** (stub as clearly marked placeholder):
- US-021: ML instrument table region detection and table_cell record persistence — stub as `# P1-STUB: table extraction not implemented` in `result_persistence.py`; the `TableRegionResult` structures returned from inference should be ignored/logged but not persisted until P1

---

##### Technology constraints

Per §1.8 (non-negotiable):

| Layer | Requirement |
|---|---|
| Worker runtime | **Celery** on **Redis** broker — persistent queue (`ml_inference` queue name). Must NOT use any in-memory queue or asyncio task; see Critical Ordering Rule 14 |
| Language | **Python** (unified with FastAPI and ML codebase) |
| DB ORM | **SQLAlchemy** (same `backend/app/db/session.py` session factory from S1-A) |
| Queue broker | **Redis** (ElastiCache) via `CELERY_BROKER_URL` env var, falling back to `REDIS_URL` |
| Object storage | **AWS S3-compatible** via S3 client from S1-C (`backend/app/storage/s3_client.py`) |
| Analytics | **PostHog** via emitter from S1-E (`backend/app/analytics/events.py`) |
| Pub/Sub | **Redis** pub/sub via S1-D (`backend/app/redis/pubsub.py`); channel pattern `drawing:status:{drawing_id}` |
| Schema migrations | **Alembic** (owned by S1-A — do not create migrations here) |
| Deployment target | EC2 G4dn (GPU) — worker image built from `backend/Dockerfile.ml` |

Must NOT use:
- Any browser/client-side code path to emit analytics events (Rule from §1.10: "Must NEVER fire from: Browser client")
- DB lookup to resolve `user_id` in the worker — must read from job payload only (§1.4 Rule 5)
- In-memory Celery task routing (must use named queue `ml_inference` with durable Redis broker)

---

##### Performance targets

| Metric | Target | Type | Owned here |
|---|---|---|---|
| ML inference timeout before `Failed` state | 20 minutes max | **Hard SLA** | Yes — `soft_time_limit=1200, time_limit=1260` on Celery task |
| Automatic retries before terminal `Failed` | 1 retry (2 attempts total) | Hard constraint | Yes — `max_retries=1` on Celery task |
| `processing_complete` / `processing_failed` analytics | Non-blocking, asynchronous, must not surface failure to worker | Monitoring target | Yes |

All other SLAs (canvas load <3s, export timing) are downstream — see those sessions.

---

##### Owned files

```
backend/app/workers/ml/__init__.py
backend/app/workers/ml/tasks.py
backend/app/workers/ml/inference.py
backend/app/workers/ml/model_loader.py
backend/app/workers/ml/result_persistence.py
tests/integration/test_ml_worker.py
```

---

##### Read-only imports

| Owning session | File path | Required named exports |
|---|---|---|
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` |
| S0-A | `backend/app/schemas/contracts.py` | `MLInferenceJobPayload`, `MLInferenceResult`, `DetectedSymbolResult`, `TableRegionResult`, `BoundingBox`, `DrawingStatusSSEEvent`, `DrawingProcessingState` |
| S0-A | `backend/app/config.py` | `settings` (env var access: `ML_MODEL_S3_KEY`, `ML_MODEL_VERSION`, `ML_JOB_TIMEOUT_SECONDS`, `S3_BUCKET_NAME`) |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` |
| S1-A | `backend/app/db/models/detected_symbol.py` | `DetectedSymbol` |
| S1-A | `backend/app/db/models/table_cell.py` | `TableCell` (for P1 stub reference only) |
| S1-A | `backend/app/db/session.py` | `SessionLocal`, `get_db` |
| S1-C | `backend/app/storage/s3_client.py` | `download_file_bytes`, `get_s3_client` |
| S1-D | `backend/app/redis/pubsub.py` | `publish_drawing_status` |
| S1-D | `backend/app/workers/base.py` | `BaseTask` |
| S1-D | `backend/app/workers/queues.py` | `ML_INFERENCE_QUEUE` |
| S1-E | `backend/app/analytics/events.py` | `emit_processing_complete`, `emit_processing_failed` |

---

##### Do not touch

- `backend/app/main.py` — entry point, owned by S0-A
- `backend/app/api/routers/__init__.py` — router registration, owned by S0-A
- `backend/app/api/routers/_stubs.py` — route stubs, owned by S0-A
- `backend/app/workers/celery_app.py` — Celery app config, owned by S0-A
- `backend/app/workers/queues.py` — queue routing config, owned by S1-D
- `backend/app/workers/base.py` — base task class, owned by S1-D
- `backend/app/db/models/*.py` — all DB models, owned by S1-A
- `backend/alembic/versions/*.py` — migrations, owned by S1-A
- `backend/app/redis/pubsub.py` — pub/sub client, owned by S1-D
- `backend/app/analytics/events.py` — analytics emitters, owned by S1-E
- `backend/app/storage/s3_client.py` — S3 client, owned by S1-C
- All S2-H (Ingest Worker) files
- All S2-I (Scan Worker) files
- All S2-B (Drawings API) files
- All S2-C (Symbols API) files

---

##### Architecture context

The following sections from the distilled specification apply verbatim:

**§1.1 — Shared Contracts (ML types):**

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

// ML Inference Service Response
interface MLInferenceResult {
  drawing_id: string;
  symbols: DetectedSymbolResult[];
  tables: TableRegionResult[];
}

interface DetectedSymbolResult {
  entity_class_id: string;
  subtype: string;
  tag_label: string | null;
  confidence: number;              // 0.0–1.0
  bbox: BoundingBox;
  page_number: number;
}

interface TableRegionResult {
  bbox: BoundingBox;
  page_number: number;
  cells: TableCellResult[];
}

interface TableCellResult {
  row_label: string;
  column_label: string;
  bbox: BoundingBox;
  extracted_value: string;
}

interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
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

**§1.3 — Drawing Processing State Transitions:**

```typescript
const DRAWING_STATE_TRANSITIONS: Record<DrawingProcessingState, DrawingProcessingState[]> = {
  Pending:      ['Queued', 'Failed'],
  Queued:       ['Scanning', 'Failed'],
  Scanning:     ['Processing', 'Scan_Failed', 'Failed'],
  Processing:   ['Complete', 'Failed'],
  Complete:     ['Under_Review', 'Queued'],
  Under_Review: ['Queued'],
  Failed:       ['Queued'],
  Scan_Failed:  [],                             // Terminal — no retry permitted
} as const;
```

**§1.4 — Critical Ordering Rules (applicable):**

> **Rule 5**: "The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access. This is mandatory for `processing_complete` and `processing_failed` events."

> **Rule 14**: "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts."

**§1.9 — Performance Targets:**

> "ML inference timeout before Failed state | 20 minutes max | Hard SLA | ML Worker; 1 automatic retry before `Failed` transition"

**§1.10 — Analytics Event Contracts (ML Worker events):**

| Event | Payload | Code Surface | Trigger Condition | Must NOT have happened yet | Must NEVER fire from |
|---|---|---|---|---|---|
| `processing_complete` | `{ event: 'processing_complete', timestamp: string, user_id: string, drawing_id: string }` | ML Worker (user_id from job payload) | Drawing transitions to `Complete` state | `processing_failed` for same drawing_id in same job run | Browser client; must not resolve user_id via DB lookup in worker |
| `processing_failed` | `{ event: 'processing_failed', timestamp: string, user_id: string, drawing_id: string }` | ML Worker (user_id from job payload) | Drawing transitions to `Failed` state (after 1 automatic retry exhausted) | `processing_complete` for same drawing_id in same job run | Browser client |

> "Events must be non-blocking and asynchronous. Analytics failure must not surface to users. Server-side retry queue (dead-letter) recommended."

**§1.11 — Cross-Session Runtime Patterns:**

Redis Pub/Sub:
| Channel Pattern | Published By | Consumed By | Payload Shape |
|---|---|---|---|
| `drawing:status:{drawing_id}` | Ingest Worker, Scan Worker, ML Worker (on each state transition) | FastAPI SSE handler (`GET /drawings/{id}/status`) → client | `DrawingStatusSSEEvent` |

```typescript
interface DrawingStatusSSEEvent {
  drawing_id: string;
  state: DrawingProcessingState;
  timestamp: string;               // ISO 8601 UTC
}
```

Celery Queue:
| Queue | Workers | Job Types |
|---|---|---|
| `ml_inference` | ML Worker (GPU — G4dn) | Symbol detection + table extraction |

**§1.12 — Environment Variables (ML Worker relevant):**

| Variable | Startup if Absent |
|---|---|
| `DATABASE_URL` | Refuse to start |
| `REDIS_URL` | Refuse to start |
| `CELERY_BROKER_URL` | Falls back to `REDIS_URL` |
| `S3_BUCKET_NAME` | Refuse to start |
| `S3_REGION` | Refuse to start |
| `ML_MODEL_S3_KEY` | Refuse to start |
| `ML_MODEL_VERSION` | Log warning; use latest in bucket |
| `ML_JOB_TIMEOUT_SECONDS` | Use default `1200` |
| `POSTHOG_API_KEY` | Log warning; analytics disabled |

---

##### User stories and acceptance criteria

The following user stories from §1.13 are directly implemented by this session:

**US-008: Processing state machine with live SSE/poll status updates**

Acceptance criteria (derived from §1.3, §1.4, §1.9, §1.11):

- AC-1: When the ML worker task is invoked with a valid `MLInferenceJobPayload` for a drawing in `Processing` state, the worker runs inference and transitions the drawing to `Complete` upon successful completion.
- AC-2: When the drawing transitions to `Complete`, the worker publishes a `DrawingStatusSSEEvent` with `state: 'Complete'` and an ISO 8601 UTC timestamp to the Redis channel `drawing:status:{drawing_id}`.
- AC-3: When the ML inference raises an exception on the first attempt, the Celery task automatically retries exactly once (max_retries=1).
- AC-4: When the ML inference fails on the retry attempt (second attempt), the drawing is transitioned to `Failed`, a `DrawingStatusSSEEvent` with `state: 'Failed'` is published to Redis, and no further retries are attempted.
- AC-5: When the ML inference task exceeds 20 minutes (ML_JOB_TIMEOUT_SECONDS), the task is terminated and treated as a failure (applying the retry logic in AC-3/AC-4).
- AC-6: When a `Failed` transition occurs due to timeout or error after retries exhausted, the drawing `processing_state` is set to `'Failed'` in the database.
- AC-7: If the drawing record cannot be found in the DB (e.g., deleted mid-flight), the task raises without emitting analytics events or corrupting state.

**US-010: Analytics events — processing_complete and processing_failed**

Acceptance criteria (derived from §1.10):

- AC-1: When drawing transitions to `Complete`, `emit_processing_complete` is called with `{ event: 'processing_complete', timestamp: <UTC ISO 8601>, user_id: <from job payload>, drawing_id: <from job payload> }` — `user_id` is read from the job payload, not from any DB query.
- AC-2: When drawing transitions to `Failed` (after retries exhausted), `emit_processing_failed` is called with `{ event: 'processing_failed', timestamp: <UTC ISO 8601>, user_id: <from job payload>, drawing_id: <from job payload> }` — `user_id` is read from the job payload.
- AC-3: `processing_complete` and `processing_failed` must never both be emitted for the same drawing in the same task execution.
- AC-4: An exception in the analytics emitter must not propagate to the worker — it must be caught, logged, and the task must still complete normally (drawing state already persisted).
- AC-5: Analytics events must never be emitted from the browser client; they are emitted server-side by the worker only.

**US-011: ML inference execution and result persistence**

Acceptance criteria (derived from §1.1, §1.2, §1.3):

- AC-1: The worker downloads the drawing file bytes from S3 using the `storage_reference` field of the job payload.
- AC-2: The worker loads the ML model from S3 using `ML_MODEL_S3_KEY` at worker startup (not per-task); model is cached in memory for the worker process lifetime.
- AC-3: After successful inference, all `DetectedSymbolResult` items are written to the `detected_symbol` table with: `drawing_id`, `entity_class_id`, `subtype`, `tag_label`, `confidence` (0.0–1.0), `bbox` (JSONB), `source='ml'`, `rejected=False`, `page_number`.
- AC-4: The drawing record's `processing_state`, `processed_at`, and `estimated_symbol_count` are updated atomically in the same database transaction as the `detected_symbol` inserts.
- AC-5: If `page_range` is specified in the job payload, only symbols on pages within the inclusive range are written; symbols outside the range are discarded.
- AC-6: The detected symbol and drawing state update commit is atomic: either all symbols are written and the drawing is `Complete`, or none are written and the drawing is `Failed` (no partial result state visible in DB).
- AC-7: The `estimated_symbol_count` on the Drawing record is set to the count of non-rejected symbols written in this job run.

**US-021 (P1 stub): Table region detection and cell extraction**

- AC-1 [P1-STUB]: The `tables` field of `MLInferenceResult` is accepted in the inference response but table_cell records are NOT written to the database in P0 — this code path must be clearly marked with `# P1-STUB` and log a debug message indicating table results were received but not persisted.

---

##### UX and design specification

N/A — no frontend component. This session is a backend Celery worker.

---

##### Critical implementation notes

- **user_id MUST come from job payload only** (§1.4 Rule 5): The Celery task function signature must accept `user_id` as part of the `MLInferenceJobPayload` dict argument. No SQLAlchemy query for `user_id` is ever permitted inside `tasks.py`. If `user_id` is missing from the payload, log an error and proceed without emitting analytics (do not raise in a way that prevents drawing state update).

- **Persistent queue only** (§1.4 Rule 14): The `run_ml_inference` task must be decorated with `@celery_app.task(bind=True, base=BaseTask, queue=ML_INFERENCE_QUEUE, max_retries=1, soft_time_limit=ML_JOB_TIMEOUT_SECONDS, time_limit=ML_JOB_TIMEOUT_SECONDS + 60)`. The `time_limit` must be set slightly higher than `soft_time_limit` to allow graceful `SoftTimeLimitExceeded` handling. Never use `celery_app.send_task` with a string queue name bypassing the `ML_INFERENCE_QUEUE` constant.

- **Atomic transaction for result persistence** (§1.2 schema): The following operations MUST be in a single SQLAlchemy `session.commit()` call: (a) `INSERT INTO detected_symbol` for all symbols, (b) `UPDATE drawing SET processing_state='Complete', processed_at=NOW(), estimated_symbol_count=N WHERE id=drawing_id`. If the commit fails, the exception propagates to the Celery retry mechanism. Never commit detected symbols before the drawing state update; never update drawing state before all detected symbols are inserted.

- **State transition guard**: Before updating `processing_state` to `Complete` or `Failed`, validate that the current `processing_state` is `Processing`. If the drawing is in any other state (e.g., already `Failed` from a race), log a warning and skip the update without raising — prevents duplicate-delivery corruption.

- **SSE publish must happen after DB commit**: `publish_drawing_status()` is called only after `session.commit()` succeeds. Never publish SSE before the transaction is durable.

- **Analytics emit must happen after DB commit**: `emit_processing_complete()` / `emit_processing_failed()` are called only after `session.commit()` succeeds and after the SSE publish. Wrap in try/except so analytics failure never raises.

- **Model loading is per-worker-process, not per-task**: `model_loader.py` must use a module-level singleton (cached after first load). The model is downloaded from S3 once when the first task is processed. Subsequent tasks reuse the in-memory model. This is critical for GPU memory management on G4dn instances.

- **`processing_failed` fires only after retries are exhausted** (§1.10): Celery's `on_failure` callback fires after the final retry. Do NOT emit `processing_failed` inside the task body on first exception — only emit it in `on_failure` (or equivalent `BaseTask.on_failure` override from S1-D). This ensures the event fires exactly once after the final attempt.

- **P1 stub for table cells**: `result_persistence.py` must contain a clearly marked stub block:
  ```python
  # P1-STUB: Table cell persistence not implemented in P0.
  # Tables from inference result are intentionally discarded.
  # See US-021 for P1 implementation requirements.
  if result.tables:
      logger.debug(f"Received {len(result.tables)} table regions for drawing {drawing_id}; skipping persistence (P1-STUB)")
  ```

- **`page_count` update**: When `page_range` is absent, derive `page_count` from `max(symbol.page_number for symbol in result.symbols)` if symbols are present, else leave `page_count` unchanged (ingest worker may have set it already). If `page_range` is present, `page_count` is already known from ingest; do not overwrite.

- **Silent failure mode — missing `user_id` in payload**: If a job is enqueued without `user_id` (should never happen per Rule 5, but must be handled defensively), the task must still process the drawing and update its state. It logs `ERROR` and skips analytics emission. Failing to handle this defensively would cause the task to raise before persisting results, leaving the drawing stuck in `Processing` indefinitely.

- **Silent failure mode — double-commit pattern**: If `result_persistence.py` commits detected symbols in one transaction and drawing state in a second transaction, a crash between them leaves the DB in a partially-complete state that is not retryable (symbols already exist for the drawing_id). The single-commit atomicity rule prevents this.

- **Do not transition `Scan_Failed` drawings**: `Scan_Failed` is terminal (§1.3). If an ML job somehow arrives for a `Scan_Failed` drawing, it must no-op entirely.

---

##### Mocking contract

This is a backend worker session. Listed below are the internal event/queue payloads and service interfaces this session consumes from other sessions:

**Celery job payload** (produced by S2-B `upload_complete_service.py` at enqueue time, consumed by this worker):

```python
# Exact shape — matches MLInferenceJobPayload from §1.1
{
    "storage_reference": "drawings/uuid/filename.pdf",   # str: S3 object key
    "drawing_id": "550e8400-e29b-41d4-a716-446655440000",  # str: UUID
    "user_id": "660e8400-e29b-41d4-a716-446655440001",     # str: UUID (set by API layer)
    "page_range": [1, 5]  # optional — omit for full document
}
```

**Redis pub/sub publish interface** (S1-D `publish_drawing_status`):

```python
# Expected call signature from backend/app/redis/pubsub.py
publish_drawing_status(drawing_id: str, state: str, timestamp: str) -> None
# Publishes to channel: drawing:status:{drawing_id}
# Payload: {"drawing_id": str, "state": str, "timestamp": str}  # DrawingStatusSSEEvent shape
```

**Analytics emitter interface** (S1-E `backend/app/analytics/events.py`):

```python
# Expected call signatures
emit_processing_complete(user_id: str, drawing_id: str) -> None
emit_processing_failed(user_id: str, drawing_id: str) -> None
# Both are async/non-blocking; exceptions must be caught by caller
```

**S3 download interface** (S1-C `backend/app/storage/s3_client.py`):

```python
download_file_bytes(bucket: str, object_key: str) -> bytes
```

**Test doubles for integration tests:**

For `tests/integration/test_ml_worker.py`, use the following mock shapes:

```python
# Mock MLInferenceResult returned by mock inference engine
MOCK_INFERENCE_RESULT = {
    "drawing_id": "<drawing_id>",
    "symbols": [
        {
            "entity_class_id": "valve_gate",
            "subtype": "manual",
            "tag_label": "V-101",
            "confidence": 0.92,
            "bbox": {"x": 100, "y": 200, "w": 50, "h": 50},
            "page_number": 1
        },
        {
            "entity_class_id": "pipe",
            "subtype": "",
            "tag_label": None,
            "confidence": 0.87,
            "bbox": {"x": 300, "y": 400, "w": 200, "h": 10},
            "page_number": 1
        }
    ],
    "tables": []  # empty for P0 test; P1-STUB path tested separately
}

# Mock job payload
MOCK_JOB_PAYLOAD = {
    "storage_reference": "drawings/test-drawing-id/test.pdf",
    "drawing_id": "<uuid>",
    "user_id": "<uuid>",
    # page_range omitted
}
```

---

##### Acceptance criteria checklist

- [ ] When task invoked with valid payload for `Processing` drawing, inference runs and drawing transitions to `Complete` in DB [US-011 AC-1, US-008 AC-1]
- [ ] All `DetectedSymbolResult` records are written to `detected_symbol` table with correct fields: `drawing_id`, `entity_class_id`, `subtype`, `tag_label`, `confidence`, `bbox` (JSONB), `source='ml'`, `rejected=False`, `page_number` [US-011 AC-3]
- [ ] `detected_symbol` inserts and `drawing.processing_state='Complete'` + `drawing.processed_at` + `drawing.estimated_symbol_count` update occur in a single atomic DB transaction [US-011 AC-4, US-011 AC-6]
- [ ] `estimated_symbol_count` on Drawing equals the count of symbols written in the job run [US-011 AC-7]
- [ ] After DB commit to `Complete`, `publish_drawing_status` is called with `state='Complete'` and an ISO 8601 UTC timestamp on channel `drawing:status:{drawing_id}` [US-008 AC-2]
- [ ] After successful DB commit and SSE publish, `emit_processing_complete` is called with `user_id` and `drawing_id` sourced from job payload — no DB query for `user_id` [US-010 AC-1]
- [ ] `user_id` in emitted analytics event matches the `user_id` field of the job payload exactly [US-010 AC-1]
- [ ] On first inference exception, the Celery task retries exactly once (total of 2 execution attempts) [US-008 AC-3]
- [ ] On second (retry) inference failure, drawing is transitioned to `Failed` in DB [US-008 AC-4, US-008 AC-6]
- [ ] After second failure, `publish_drawing_status` is called with `state='Failed'` [US-008 AC-4]
- [ ] After second failure, `emit_processing_failed` is called with `user_id` and `drawing_id` from job payload [US-010 AC-2]
- [ ] `processing_complete` and `processing_failed` are never both emitted in a single task execution [US-010 AC-3]
- [ ] If `emit_processing_complete` raises an exception, the exception is caught and logged; drawing state remains `Complete` and the task does not re-raise [US-010 AC-4]
- [ ] If `emit_processing_failed` raises an exception, the exception is caught and logged; drawing state remains `Failed` and the task does not re-raise [US-010 AC-4]
- [ ] When `page_range` is provided, only symbols with `page_number` within the inclusive range are persisted; out-of-range symbols are discarded [US-011 AC-5]
- [ ] If drawing is not in `Processing` state when task executes (e.g., already `Failed`), the task logs a warning and exits without writing symbols or emitting analytics [US-008 AC-7]
- [ ] If drawing record does not exist in DB, the task raises without emitting analytics events [US-008 AC-7]
- [ ] `tables` field from inference result is NOT persisted to `table_cell` in P0; a debug log is emitted when tables are present [US-021 AC-1 P1-STUB]
- [ ] ML model is loaded from S3 using `ML_MODEL_S3_KEY` at worker startup and cached; the model loader is not called again on subsequent task invocations [US-011 AC-2]
- [ ] `Scan_Failed` drawings are not processed; task no-ops if drawing is in `Scan_Failed` state [US-008 AC-7] [MANUAL]
- [ ] Task is configured with `soft_time_limit` and `time_limit` derived from `ML_JOB_TIMEOUT_SECONDS` (default 1200s); `SoftTimeLimitExceeded` is caught, triggers retry/failure path [US-008 AC-5] [MANUAL]
- [ ] Worker process refuses to start if `ML_MODEL_S3_KEY`, `DATABASE_URL`, `REDIS_URL`, or `S3_BUCKET_NAME` are absent from environment [MANUAL]
- [ ] No `user_id` DB lookup occurs anywhere in `tasks.py`, `result_persistence.py`, or `inference.py` (static code review) [US-010 AC-1, AC-2] [MANUAL]

---

##### Independent Test

- **Test file path** (TDD — written first, must fail before implementation): `tests/integration/test_ml_worker.py`
- **Exact CI command**: `pytest tests/integration/test_ml_worker.py -v`

**AC → assertion mapping:**

| AC | `it(...)` / `test(...)` block name |
|---|---|
| US-011 AC-1, US-008 AC-1 | `test_successful_inference_transitions_drawing_to_complete` |
| US-011 AC-3 | `test_detected_symbols_written_with_correct_fields` |
| US-011 AC-4, US-011 AC-6 | `test_result_persistence_is_atomic` |
| US-011 AC-7 | `test_estimated_symbol_count_set_on_drawing` |
| US-008 AC-2 | `test_sse_event_published_on_complete` |
| US-010 AC-1 (first) | `test_processing_complete_analytics_emitted_on_success` |
| US-010 AC-1 (user_id source) | `test_analytics_user_id_from_payload_not_db` |
| US-008 AC-3 | `test_task_retries_once_on_first_inference_failure` |
| US-008 AC-4, US-008 AC-6 | `test_drawing_transitions_to_failed_after_retry_exhausted` |
| US-008 AC-4 (SSE) | `test_sse_event_published_on_failed` |
| US-010 AC-2 | `test_processing_failed_analytics_emitted_after_retries_exhausted` |
| US-010 AC-3 | `test_complete_and_failed_not_both_emitted` |
| US-010 AC-4 (complete) | `test_analytics_exception_does_not_propagate_on_success` |
| US-010 AC-4 (failed) | `test_analytics_exception_does_not_propagate_on_failure` |
| US-011 AC-5 | `test_page_range_filters_symbols` |
| US-008 AC-7 (wrong state) | `test_task_noop_when_drawing_not_in_processing_state` |
| US-008 AC-7 (missing drawing) | `test_task_raises_when_drawing_not_found` |
| US-021 AC-1 P1-STUB | `test_table_results_not_persisted_in_p0` |
| US-011 AC-2 | `test_model_loader_called_once_across_multiple_tasks` |

**Fixtures / test doubles:**

```python
# conftest.py additions for this session:

@pytest.fixture
def db_session():
    """Provides a real PostgreSQL test session (from tests/integration/fixtures/db.py)."""
    ...

@pytest.fixture
def mock_s3_client(monkeypatch):
    """Patches download_file_bytes to return minimal PDF bytes."""
    monkeypatch.setattr(
        "backend.app.storage.s3_client.download_file_bytes",
        lambda bucket, key: b"%PDF-1.4 minimal"
    )

@pytest.fixture
def mock_inference_engine(monkeypatch):
    """Patches the inference function to return MOCK_INFERENCE_RESULT."""
    ...

@pytest.fixture
def mock_inference_raises_once(monkeypatch):
    """Patches inference to raise on first call, succeed on second (for retry test)."""
    ...

@pytest.fixture
def mock_inference_always_raises(monkeypatch):
    """Patches inference to always raise (for exhausted retry test)."""
    ...

@pytest.fixture
def mock_publish_drawing_status(monkeypatch):
    """Captures all publish_drawing_status calls for assertion."""
    ...

@pytest.fixture
def mock_analytics(monkeypatch):
    """Captures emit_processing_complete / emit_processing_failed calls."""
    ...

@pytest.fixture
def processing_drawing(db_session):
    """Creates a Drawing in 'Processing' state with a valid stored_file_id."""
    ...

# MOCK_INFERENCE_RESULT shape (matches §1.1 MLInferenceResult):
MOCK_INFERENCE_RESULT = MLInferenceResult(
    drawing_id="<drawing_id>",
    symbols=[
        DetectedSymbolResult(
            entity_class_id="valve_gate",
            subtype="manual",
            tag_label="V-101",
            confidence=0.92,
            bbox=BoundingBox(x=100, y=200, w=50, h=50),
            page_number=1
        ),
        DetectedSymbolResult(
            entity_class_id="pipe",
            subtype="",
            tag_label=None,
            confidence=0.87,
            bbox=BoundingBox(x=300, y=400, w=200, h=10),
            page_number=1
        ),
    ],
    tables=[]
)

MOCK_JOB_PAYLOAD = MLInferenceJobPayload(
    storage_reference="drawings/test-uuid/test.pdf",
    drawing_id="<uuid-from-fixture>",
    user_id="user-uuid-12345",
)
```

**Pre-conditions:**
- PostgreSQL test DB running (from `tests/integration/fixtures/db.py`, S0-B)
- Redis test instance running (from `tests/integration/fixtures/redis.py`, S0-B)
- All S1-A migrations applied to test DB
- `entity_class` seed data present (from `backend/app/db/seed_entity_classes.py`, S1-A) — required so FK constraint on `detected_symbol.entity_class_id` does not fail
- Environment variables set: `DATABASE_URL`, `REDIS_URL`, `S3_BUCKET_NAME`, `S3_REGION`, `ML_MODEL_S3_KEY` (any non-empty string for testing), `CELERY_BROKER_URL`
- S3 mock via LocalStack or `moto` fixture (from `tests/integration/fixtures/s3.py`, S0-B)
- `ML_MODEL_S3_KEY` env var set; `model_loader.py` must be patchable to return a mock model object without actual S3 download in unit-style integration tests

**Isolation rule:**
All tests in `tests/integration/test_ml_worker.py` invoke the Celery task function directly (via `.apply()` with `CELERY_TASK_ALWAYS_EAGER=True` or by calling the underlying task implementation directly) rather than through a live Celery broker. This ensures the test passes when only S2-J is merged — no S2-H or S2-I sibling sessions need to have merged. The test fixtures create DB state directly without relying on the Ingest or Scan workers.

---

##### Checkpoint

- **One-sentence observable outcome**: After this PR merges, calling the `run_ml_inference` Celery task directly with a valid payload for a `Processing` drawing results in all detected symbols written to `detected_symbol`, the drawing `processing_state` set to `'Complete'` in PostgreSQL, a `DrawingStatusSSEEvent` published to the `drawing:status:{drawing_id}` Redis channel, and `emit_processing_complete` called with the `user_id` sourced from the job payload — all verifiable by running `pytest tests/integration/test_ml_worker.py`.

- **Shippability claim**: This PR is independently mergeable to `main` even if no other session in the same Phase 2 wave has merged, provided S1-A, S1-C, S1-D, and S1-E have already merged (Phase 1 gate). Tests invoke the task function directly and do not depend on S2-B, S2-H, or S2-I being present.

---

##### Output and handoff

| Export | Kind | Consuming sessions | Notes |
|---|---|---|---|
| `run_ml_inference` Celery task | function | S2-B (enqueues via `celery_app.send_task('app.workers.ml.tasks.run_ml_inference', ...)`) | **[LOAD-BEARING]** — task name string must not change after merge; S2-B hard-codes the task name at enqueue time |
| `ML_INFERENCE_QUEUE` queue name constant | re-exported from S1-D | S2-B (at enqueue time) | Queue name must remain `'ml_inference'` |
| `DetectedSymbol` records in DB | DB rows | S2-C (`GET /drawings/{id}/symbols`), S2-D (export generators), S3-D (canvas review) | Written atomically by `result_persistence.py`; shape defined by S1-A |
| `drawing.processing_state = 'Complete'` | DB row update | S2-B (SSE stream), S3-B (dashboard status), S3-D (review canvas) | Downstream consumers poll or subscribe to Redis pub/sub channel |
| `drawing:status:{drawing_id}` Redis channel event | SSE pub/sub | S2-B `drawing_status.py` SSE handler → frontend | Payload shape: `DrawingStatusSSEEvent` — **[LOAD-BEARING]** field names must not change |
| `emit_processing_complete` / `emit_processing_failed` calls | analytics events | S1-E dead-letter queue / PostHog | Non-blocking; failure silent |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/test_ml_worker.py -v",
    "file": "tests/integration/test_ml_worker.py"
  },
  "checkpoint": "Calling the run_ml_inference Celery task directly with a valid MLInferenceJobPayload for a Processing drawing results in detected symbols written to detected_symbol, drawing.processing_state set to Complete in PostgreSQL, a DrawingStatusSSEEvent published to the drawing:status:{drawing_id} Redis channel, and emit_processing_complete invoked with user_id from the job payload.",
  "manualAcs": [
    {
      "id": "US-008-AC-7-scan-failed",
      "text": "Scan_Failed drawings are not processed; task no-ops if drawing is in Scan_Failed state."
    },
    {
      "id": "US-008-AC-5",
      "text": "Task is configured with soft_time_limit and time_limit derived from ML_JOB_TIMEOUT_SECONDS (default 1200s); SoftTimeLimitExceeded is caught and triggers the retry/failure path."
    },
    {
      "id": "ENV-STARTUP",
      "text": "Worker process refuses to start if ML_MODEL_S3_KEY, DATABASE_URL, REDIS_URL, or S3_BUCKET_NAME are absent from the environment."
    },
    {
      "id": "US-010-AC-1-static",
      "text": "No user_id DB lookup occurs anywhere in tasks.py, result_persistence.py, or inference.py (verified by static code review or grep)."
    }
  ],
  "exports": [
    {
      "kind": "function",
      "name": "run_ml_inference",
      "shape": "(self: Task, payload: dict) -> None"
    },
    {
      "kind": "module",
      "name": "backend/app/workers/ml/tasks",
      "shape": "backend/app/workers/ml/tasks.py"
    },
    {
      "kind": "module",
      "name": "backend/app/workers/ml/result_persistence",
      "shape": "backend/app/workers/ml/result_persistence.py"
    },
    {
      "kind": "function",
      "name": "persist_inference_results",
      "shape": "(session: Session, drawing_id: str, result: MLInferenceResult, page_range: tuple[int, int] | None) -> int"
    },
    {
      "kind": "function",
      "name": "load_model",
      "shape": "() -> Any"
    },
    {
      "kind": "function",
      "name": "run_inference",
      "shape": "(model: Any, file_bytes: bytes, drawing_id: str, page_range: tuple[int, int] | None) -> MLInferenceResult"
    }
  ]
}
```