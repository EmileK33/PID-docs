---

#### S2-H — Ingest Worker

**Phase 2 | Real-time/Queue | Needs: S1-A, S1-C, S1-D, S1-E**

---

##### Objective

Build the Celery-based Ingest Worker that performs post-storage SHA-256 re-verification (second security gate), file format detection, DWG-to-raster/PDF conversion via ODA File Converter in an isolated Docker sandbox, drawing state transitions (`Queued → Scanning`, `Scanning → Scan_Failed`, `Scanning → Failed`), Redis pub/sub state event publication, and scan job enqueueing — completing the pre-ML ingest pipeline for every uploaded drawing.

---

##### Scope

**P0 MVP — all work in this session is P0.**

All functionality described below is required for the P0 MVP. There is no P1 work in this session. However, the following stubs must be placed as clearly marked `# P1 STUB` comments:

- **Analytics emission from the ingest worker**: No analytics events are assigned to this worker in §1.10 for P0. A clearly-marked `# P1 STUB: emit ingest_failed analytics event here` comment must appear in the `Scan_Failed` and `Failed` transition code paths in `tasks.py`.
- **DWG version range enforcement above ODA-supported versions**: Currently ODA handles what it handles; a structured DWG version rejection code path based on AutoCAD version strings is a `# P1 STUB: enforce supported DWG version range per ops policy` comment in `format_detect.py`.

---

##### Technology constraints

**Non-negotiable per §1.8:**

| Concern | Required technology |
|---|---|
| Async task queue | **Celery on Redis broker** — `CELERY_BROKER_URL` (or falls back to `REDIS_URL`). No in-memory task dispatch. |
| Database ORM | **SQLAlchemy** with **PostgreSQL** via `DATABASE_URL`. Alembic-managed schema (already migrated by S1-A). |
| Object storage | **AWS S3-compatible** via `boto3`. Pre-signed URL pattern; IAM role or key-based auth. |
| DWG-to-PDF conversion | **ODA File Converter** (`ODA_CONVERTER_PATH` env var) executed inside the ODA sandbox Docker image (`ops/oda-sandbox/Dockerfile`, owned by S0-A). **Must NOT run ODA binary directly on the host process without Docker sandboxing.** |
| State pub/sub | **Redis pub/sub** via the `backend/app/redis/pubsub.py` module (S1-D). |
| PDF page counting | **pypdf** (`from pypdf import PdfReader`). No other PDF library. |
| Hash computation | `backend/app/storage/hashing.py` (S1-C). Must NOT reimplement SHA-256 inline. |
| Blocklist check | `backend/app/storage/blocklist.py` (S1-C). Must NOT query `file_hash_blocklist` table directly — use the provided service function. |
| Analytics infrastructure | `backend/app/analytics/events.py` (S1-E) — imported but no P0 events fired; structure must be present for future use. |

**Must NOT use:**
- `threading` or `asyncio.Queue` for task dispatch — violates NFR-7 (persistent queue requirement).
- Direct process-level execution of ODA binary without Docker isolation — violates §1.13 P0 sandbox requirement.
- `subprocess.run` with `network=host` or no network restriction for ODA sandbox — violates security requirement.

---

##### Performance targets

| Metric | Target | Hard or Monitoring | Owned by this session |
|---|---|---|---|
| Ingest job survives server restart | Enqueued via persistent Celery/Redis queue | **Hard SLA (NFR-7)** | Yes — `tasks.py` must use Celery on Redis broker, never `apply_async` on an in-memory-only backend |
| ML inference timeout (end-to-end) | 20 minutes max before `Failed` state | Hard SLA (owned by S2-J ML worker) | Not directly, but ingest pipeline must not introduce unnecessary blocking delays |
| ODA license expiry alert | Log `WARNING` when `ODA_LICENSE_EXPIRY_DATE` is within 30 days of today | Monitoring target | Yes — checked at worker startup in `oda_converter.py` |
| State event publication latency | ≤10-second polling fallback is the SSE contract | Monitoring target (SSE owned by S2-B) | Partial — ingest worker must publish to Redis pub/sub synchronously before returning from state transition |

---

##### Owned files

```
backend/app/workers/ingest/__init__.py
backend/app/workers/ingest/tasks.py
backend/app/workers/ingest/oda_converter.py
backend/app/workers/ingest/hash_reverify.py
backend/app/workers/ingest/format_detect.py
tests/integration/test_ingest_worker.py
```

---

##### Read-only imports

| Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` (Celery application instance) |
| S0-A | `backend/app/config.py` | `settings` (Settings object with all env vars from §1.12) |
| S1-A | `backend/app/db/session.py` | `get_db_session` (context manager / dependency) |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/stored_file.py` | `StoredFile` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/file_hash_blocklist.py` | `FileHashBlocklist` (SQLAlchemy model) |
| S1-C | `backend/app/storage/s3_client.py` | `get_s3_client`, `download_object_bytes`, `upload_object_bytes` |
| S1-C | `backend/app/storage/hashing.py` | `compute_sha256` |
| S1-C | `backend/app/storage/blocklist.py` | `is_hash_blocked` |
| S1-D | `backend/app/redis/pubsub.py` | `publish_drawing_status` |
| S1-D | `backend/app/workers/queues.py` | `INGEST_QUEUE`, `SCAN_QUEUE` (queue name constants) |
| S1-D | `backend/app/workers/base.py` | `BaseTaskWithRetry` (base Celery task class with retry policy) |
| S1-E | `backend/app/analytics/events.py` | `emit_event` (for P1 stubs — imported but not called in P0) |

---

##### Do not touch

- `backend/app/main.py` — owned by S0-A
- `backend/app/api/routers/__init__.py` — owned by S0-A
- `backend/app/api/routers/_stubs.py` — owned by S0-A
- `backend/app/workers/celery_app.py` — owned by S0-A
- `backend/app/workers/__init__.py` — owned by S0-A
- `backend/app/workers/queues.py` — owned by S1-D
- `backend/app/workers/base.py` — owned by S1-D
- `backend/app/db/models/*.py` — all owned by S1-A
- `backend/app/db/session.py` — owned by S1-A
- `backend/app/storage/*.py` — all owned by S1-C
- `backend/app/redis/*.py` — all owned by S1-D
- `backend/app/analytics/*.py` — all owned by S1-E
- `backend/app/auth/*.py` — all owned by S1-B
- `backend/app/workers/scan/` — owned by S2-I (must not import or modify)
- `backend/app/workers/ml/` — owned by S2-J
- `backend/app/api/routers/drawings.py` — owned by S2-B
- `ops/oda-sandbox/Dockerfile` — owned by S0-A (read-only reference; do not modify)

---

##### Architecture context

Verbatim from the distilled specification:

**§1.1 — Drawing Processing State Machine (type definition):**

```typescript
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

**§1.4 — Critical Ordering Rule 3:**

> "Ingest Worker performs a server-side SHA-256 verification of the stored object against the client-supplied hash... hash is also checked a second time against the blocklist to handle newly-added entries between steps 3 and 7."

**§1.4 — Critical Ordering Rule 5:**

> "The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access. This is mandatory for `processing_complete` and `processing_failed` events."

**§1.4 — Critical Ordering Rule 14:**

> "ML job must be enqueued via a persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts."

**§1.9 — Performance Targets:**

> | ML inference timeout before Failed state | 20 minutes max | Hard SLA | ML Worker; 1 automatic retry before `Failed` transition |
> | Pre-signed S3 URL expiry | 15 minutes | Hard constraint (security) | FastAPI URL generation |

**§1.11 — Celery Job Queue Names:**

> | Queue | Workers | Job Types |
> |---|---|---|
> | `ingest` | Ingest Worker (CPU) | DWG-to-raster conversion, format detection, post-storage hash verification |
> | `scan` | Scan Worker (ClamAV sidecar, CPU) | Malware scan |
> | `ml_inference` | ML Worker (GPU — G4dn) | Symbol detection + table extraction |

**§1.11 — Redis Pub/Sub Channels:**

> | Channel Pattern | Published By | Consumed By | Payload Shape |
> |---|---|---|---|
> | `drawing:status:{drawing_id}` | Ingest Worker, Scan Worker, ML Worker (on each state transition) | FastAPI SSE handler (`GET /drawings/{id}/status`) → client | `DrawingStatusSSEEvent` (see §1.1) |

**§1.1 — SSE Drawing Status Event:**

```typescript
interface DrawingStatusSSEEvent {
  drawing_id: string;
  state: DrawingProcessingState;
  timestamp: string;               // ISO 8601 UTC
}
```

**§1.7 — ODA File Converter:**

> | **ODA File Converter** | Commercial server-side license | N/A | **Highest risk**: success rate on complex DWGs unknown; 50-file prototype required before engineering; license expiry must be monitored with 30-day alert; commercial license must be procured before any DWG processing; fallback: LibreCAD/ezdxf for DXF path |

**§1.13 — P0 Scope (DWG sandboxing requirement):**

> DWG parsing in isolated Docker sandbox (no network egress, non-root, read-only filesystem)

**§1.12 — Relevant Environment Variables:**

> | `ODA_CONVERTER_PATH` | string | Absolute filesystem path | None | Refuse to start | Refuse to start |
> | `ODA_LICENSE_EXPIRY_DATE` | string | `YYYY-MM-DD` | None | Log warning | Log warning (30-day alert threshold) |
> | `S3_BUCKET_NAME` | string | Any non-empty string | None | Refuse to start | Refuse to start |
> | `S3_REGION` | string | AWS region code | None | Refuse to start | Refuse to start |
> | `CELERY_BROKER_URL` | string | Redis connection URI | Falls back to `REDIS_URL` | Refuse to start | Falls back to `REDIS_URL` |
> | `DATABASE_URL` | string | PostgreSQL connection URI | None | Refuse to start | Refuse to start |
> | `REDIS_URL` | string | Redis connection URI | None | Refuse to start | Refuse to start |

**§1.2 — Relevant DB Schema:**

```sql
CREATE TABLE drawing (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id          UUID REFERENCES "user"(id),
  owner_team_id          UUID REFERENCES team(id),
  filename               VARCHAR NOT NULL,
  revision_label         VARCHAR,
  processing_state       VARCHAR NOT NULL CHECK (processing_state IN (
    'Pending','Queued','Scanning','Processing','Complete','Under_Review','Failed','Scan_Failed'
  )),
  page_count             INTEGER,
  estimated_symbol_count INTEGER,
  uploaded_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at           TIMESTAMPTZ,
  stored_file_id         UUID REFERENCES stored_file(id),
  ...
);

CREATE TABLE stored_file (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  bucket       VARCHAR NOT NULL,
  object_key   VARCHAR NOT NULL,
  sha256_hash  VARCHAR NOT NULL,
  file_type    VARCHAR NOT NULL,
  size_bytes   BIGINT NOT NULL,
  CONSTRAINT stored_file_object_key_unique UNIQUE (bucket, object_key)
);

CREATE TABLE file_hash_blocklist (
  sha256_hash  VARCHAR PRIMARY KEY,
  blocked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reason       VARCHAR NOT NULL
);
```

**§1.1 — ML Inference Job Payload (produced downstream by S2-I → S2-J):**

```typescript
interface MLInferenceJobPayload {
  storage_reference: string;       // S3 object key
  drawing_id: string;              // UUID
  user_id: string;                 // UUID — MUST be set at enqueue time by API layer
  page_range?: [number, number];   // optional, 1-based inclusive
}
```

---

##### User stories and acceptance criteria

The following acceptance criteria are derived verbatim from specification language in §1.13, §1.4, §1.3, §1.7, and §1.9. The user story summaries are quoted verbatim from §1.13 P0.

---

**US-003: "PDF and DWG file upload with format, size, raster, DWG version, and blocklist validation"**

*Ingest-worker-scope ACs:*

- **US-003-AC-1**: When the ingest task downloads the stored file from S3, it computes a SHA-256 hash of the downloaded bytes using `compute_sha256` from S1-C. If the computed hash does not match `stored_file.sha256_hash`, the drawing transitions `Scanning → Scan_Failed`, a `DrawingStatusSSEEvent` is published to `drawing:status:{drawing_id}`, and the task terminates without enqueuing a scan job.
- **US-003-AC-2**: After the hash matches, the ingest task calls `is_hash_blocked(hash)` from S1-C as a second, independent blocklist check (second gate). If the hash is now blocked (i.e., it was added to `file_hash_blocklist` after the first gate passed at upload time), the drawing transitions `Scanning → Scan_Failed`, a `DrawingStatusSSEEvent` is published, and the task terminates without enqueuing a scan job. `Scan_Failed` is terminal — the task must NOT re-enqueue the drawing.
- **US-003-AC-3**: Format detection reads magic bytes from the downloaded file content (not from filename extension alone). A file beginning with `%PDF` is classified as PDF. A file beginning with `AC` (AutoCAD DWG binary header) is classified as DWG. Any other format causes the drawing to transition `Scanning → Failed` and the task terminates.
- **US-003-AC-4**: A PDF file requires no conversion. The ingest task reads the page count from the PDF using `PdfReader` from pypdf, updates `drawing.page_count`, and proceeds to enqueue the scan job.
- **US-003-AC-5**: A DWG file is converted to PDF via ODA File Converter executing inside the ODA sandbox Docker container (`ops/oda-sandbox/Dockerfile`). The container is invoked with: `--network none` (no network egress), a non-root user, and the host filesystem mounted read-only except for a temporary work directory. Failure to launch or failure of the ODA subprocess (non-zero exit code) causes the drawing to transition `Scanning → Failed`, a `DrawingStatusSSEEvent` is published, and the task terminates.
- **US-003-AC-6**: On successful DWG conversion, the resulting PDF is uploaded to S3 under a deterministic key (`converted/{drawing_id}/drawing.pdf`). A new `StoredFile` record is created in the database, and `drawing.stored_file_id` is updated to reference this new record, all within a single DB transaction. `drawing.page_count` is set from the converted PDF's page count.
- **US-003-AC-7**: `ODA_LICENSE_EXPIRY_DATE` is checked at worker startup (i.e., in `oda_converter.py` module initialization or at the start of the conversion function). If the expiry date is within 30 calendar days of today, a `WARNING`-level log message is emitted. If the env var is absent, a `WARNING` is logged and the check is skipped (does not prevent conversion).

---

**US-008: "Processing state machine (Pending → Queued → Scanning → Processing → Complete/Failed/Scan_Failed) with live SSE/poll status updates and in-app notifications"**

*Ingest-worker-scope ACs:*

- **US-008-AC-1**: At the start of processing (immediately after loading the drawing and confirming its state is `Queued`), the ingest task transitions `drawing.processing_state` from `Queued` to `Scanning` and publishes a `DrawingStatusSSEEvent` (`{drawing_id, state: "Scanning", timestamp}`) to Redis channel `drawing:status:{drawing_id}` before performing any file operations.
- **US-008-AC-2**: Every terminal state transition (`Scanning → Scan_Failed`, `Scanning → Failed`) immediately publishes a corresponding `DrawingStatusSSEEvent` to `drawing:status:{drawing_id}` before the task function returns or raises.
- **US-008-AC-3**: If the ingest task is invoked on a drawing that is already in `Scanning` or any later state (not `Queued`), the task is a no-op: it logs a warning, does not modify DB state, does not publish events, and returns without raising.

---

**US-009: "Retry failed processing jobs; delete drawings with confirmation (including mid-processing cancellation)"**

*Ingest-worker-scope ACs:*

- **US-009-AC-1**: When a drawing in `Failed` state is retried (its state is reset to `Queued` by S2-B and a new ingest job is enqueued), the ingest task re-uses the existing `stored_file_id` already on the drawing record (i.e., the same S3 object key as the original upload). It does NOT require a new upload.
- **US-009-AC-2**: Drawings in `Scan_Failed` state cannot be retried via the ingest worker. The state machine entry `Scan_Failed: []` has no outgoing transitions. If an ingest task is somehow enqueued for a `Scan_Failed` drawing, it is a no-op (logs warning, returns immediately).

---

**US-011: "Automatic ML processing trigger after upload; detection results with confidence scores display"**

*Ingest-worker-scope ACs:*

- **US-011-AC-1**: On successful completion of all ingest work (hash verified, format valid, conversion done if DWG), the ingest task enqueues a scan job to the `scan` Celery queue using `celery_app.send_task('workers.scan.tasks.scan_task', ...)` (string-based dispatch, no direct import of S2-I code). The scan job payload includes `drawing_id`, `user_id` (passed through from the ingest job payload — never resolved via DB lookup), and `storage_reference` (the S3 key of the ready file, which is the converted PDF key for DWGs or the original key for PDFs).
- **US-011-AC-2**: The `user_id` value in the scan job payload is exactly the `user_id` received in the ingest job payload, unmodified. The ingest worker must not perform a DB lookup to resolve `user_id`.

---

##### UX and design specification

N/A — this is a backend worker session with no frontend component. The worker communicates with the frontend exclusively through Redis pub/sub state events (consumed by S2-B's SSE handler) and database state updates (polled by S2-B's `GET /drawings/{id}` endpoint).

---

##### Critical implementation notes

- **State machine guard on task entry** (§1.3): The ingest task MUST check `drawing.processing_state == 'Queued'` before doing any work. If the drawing is not in `Queued` state, the task must be a no-op. This prevents double-processing on Celery task redelivery or accidental re-enqueue. Failure to guard here will silently corrupt drawing state.

- **State transition before file operations** (§1.4 rule 3, §1.3): The `Queued → Scanning` transition (DB write + Redis publish) MUST happen before any S3 download or hash computation. This ensures the drawing is never stuck in `Queued` with processing having started, which would cause the retry handler in S2-B to incorrectly re-enqueue.

- **SHA-256 re-verification is mandatory** (§1.4 rule 3): Quote: *"Ingest Worker performs a server-side SHA-256 verification of the stored object against the client-supplied hash... hash is also checked a second time against the blocklist to handle newly-added entries between steps 3 and 7."* Skipping or shortcutting this check will bypass the second security gate silently — the code will appear to work but leave a security hole.

- **Both hash checks are required** (§1.4 rule 3): Two distinct checks must happen in sequence: (1) hash-of-downloaded-file vs. `stored_file.sha256_hash`, (2) hash vs. `file_hash_blocklist`. A hash that fails check (1) means file tampering in S3. A hash that fails check (2) means the blocklist was updated between upload and ingest. Both failures must → `Scan_Failed` (terminal).

- **Scan_Failed is terminal** (§1.3): `Scan_Failed: []` has no outgoing transitions. The ingest task must NOT re-enqueue, must NOT raise a Celery exception (which would trigger Celery's automatic retry), and must NOT mark the task as failed in a way that Celery's `autoretry_for` triggers re-execution. Use `return` after setting terminal state.

- **Failed allows Celery retries for transient errors only** (§1.3): Transient failures (S3 download timeout, DB connection error, Docker daemon unavailable) should be retried by Celery using `BaseTaskWithRetry` (from S1-D). But business-logic failures (format unsupported, ODA conversion failure on a valid DWG) should set `Failed` state and NOT retry automatically — these require user-initiated retry via S2-B.

- **user_id must come from job payload, never DB lookup** (§1.4 rule 5): Quote: *"The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access."* The ingest worker passes `user_id` through to the scan job payload unchanged. Any DB lookup for user_id is a contract violation that will cause analytics attribution errors downstream.

- **ODA sandbox security requirements** (§1.13 P0): The Docker `run` command for ODA conversion must include: `--network none`, `--user nonroot` (or a non-root UID), `--read-only`, and a `--tmpfs /tmp` or writable volume mount only for the work directory. Do NOT use `--privileged`. Do NOT mount the host Docker socket. These are security requirements, not performance hints.

- **DWG converted file in DB transaction** (§1.2): Creating the new `StoredFile` record for the converted PDF AND updating `drawing.stored_file_id` MUST happen in a single SQLAlchemy transaction. If the transaction fails, the converted file in S3 may be an orphan — acceptable (S3 lifecycle policy handles cleanup) — but the drawing must NOT have a partial state with `stored_file_id` pointing to a missing DB record.

- **Redis publish must succeed before task returns** (§1.11): The `publish_drawing_status` call must be synchronous (blocking). If pub/sub fails, log the error and continue — do NOT fail the task for a pub/sub failure. S2-B's SSE handler has a 10-second polling fallback per §1.9.

- **Scan job enqueued via string-based dispatch** (cross-session contract): The ingest worker must enqueue the scan task using `celery_app.send_task('workers.scan.tasks.scan_task', kwargs={...}, queue=SCAN_QUEUE)` — a string task name — never by importing `from backend.app.workers.scan.tasks import scan_task`. This enforces intra-phase independence and prevents circular imports. If the string name is wrong, the scan job will silently enter the queue but never be consumed — verify the exact task name with the S2-I brief before finalising.

- **Celery queue name constant** (§1.11): The task must be registered on the `ingest` queue (use `INGEST_QUEUE` constant from S1-D's `queues.py`). The S2-B drawing endpoints session imports the ingest task and enqueues it using this constant — the queue name is a cross-session contract.

- **Free-tier counter NOT incremented here** (§1.4 rule 8): Quote: *"The counter increment must occur at the point processing is initiated (job enqueued), not at job completion, to prevent race conditions from concurrent uploads."* The free-tier counter is owned by S2-B (upload-complete endpoint). The ingest worker must NOT check or modify the free-tier counter.

- **`processed_at` field**: Do NOT update `drawing.processed_at` in the ingest worker. This field is set by the ML worker (S2-J) when processing completes (`Complete` state).

---

##### Mocking contract

This is a backend worker session. The following describes every internal event, queue payload, and service interface this session depends on from other sessions:

**Ingest Job Payload — produced by S2-B (`POST /drawings/{id}/upload-complete`), consumed by this worker:**

```python
# Celery task kwargs dict
{
    "drawing_id": str,          # UUID string
    "user_id": str,             # UUID string — set by S2-B at enqueue time (§1.4 rule 5)
    "stored_file_id": str,      # UUID string — references stored_file table
    "storage_reference": str,   # S3 object key of the uploaded file
}
```

**Scan Job Payload — produced by this worker, consumed by S2-I:**

```python
# Celery send_task kwargs dict
{
    "drawing_id": str,          # UUID string — passed through unchanged
    "user_id": str,             # UUID string — passed through unchanged from ingest payload
    "storage_reference": str,   # S3 object key of ready-for-scan file
                                # (converted PDF key for DWG; original key for PDF)
}
```

**Redis Pub/Sub Event — produced by this worker, consumed by S2-B SSE handler:**

```python
# Published to channel: f"drawing:status:{drawing_id}"
# JSON-serialized:
{
    "drawing_id": str,          # UUID string
    "state": str,               # One of: "Scanning", "Scan_Failed", "Failed"
    "timestamp": str,           # ISO 8601 UTC, e.g. "2024-01-15T10:30:00.123456Z"
}
```

**S1-C `blocklist.py` interface expected by this worker:**

```python
def is_hash_blocked(sha256_hash: str, db_session) -> bool:
    """Returns True if the hash is in file_hash_blocklist."""
    ...
```

**S1-D `pubsub.py` interface expected by this worker:**

```python
def publish_drawing_status(drawing_id: str, state: str, timestamp: str) -> None:
    """Publishes DrawingStatusSSEEvent JSON to drawing:status:{drawing_id}."""
    ...
```

**S1-C `s3_client.py` interface expected by this worker:**

```python
def download_object_bytes(bucket: str, object_key: str) -> bytes: ...
def upload_object_bytes(bucket: str, object_key: str, data: bytes, content_type: str) -> None: ...
```

**S1-C `hashing.py` interface expected by this worker:**

```python
def compute_sha256(data: bytes) -> str:  # Returns hex string
    ...
```

---

##### Acceptance criteria checklist

- [ ] When ingest task starts on a `Queued` drawing, `drawing.processing_state` is updated to `Scanning` in the DB before any S3 download occurs [US-008-AC-1]
- [ ] A `DrawingStatusSSEEvent` with `state="Scanning"` is published to `drawing:status:{drawing_id}` on Redis before any file operations [US-008-AC-1]
- [ ] Ingest task is a no-op (no DB write, no event publish) if drawing is already in `Scanning` or a later state [US-008-AC-3]
- [ ] Downloaded file's SHA-256 is computed using `compute_sha256` and compared to `stored_file.sha256_hash`; mismatch → `Scan_Failed` [US-003-AC-1]
- [ ] On hash mismatch, `drawing.processing_state` transitions to `Scan_Failed` [US-003-AC-1]
- [ ] On hash mismatch, `DrawingStatusSSEEvent` with `state="Scan_Failed"` is published to Redis [US-003-AC-1]
- [ ] On hash mismatch, no scan job is enqueued [US-003-AC-1]
- [ ] After hash match, `is_hash_blocked` is called as a second independent blocklist check [US-003-AC-2]
- [ ] On second-gate blocklist hit, `drawing.processing_state` transitions to `Scan_Failed` [US-003-AC-2]
- [ ] On second-gate blocklist hit, `DrawingStatusSSEEvent` with `state="Scan_Failed"` is published to Redis [US-003-AC-2]
- [ ] On second-gate blocklist hit, no scan job is enqueued [US-003-AC-2]
- [ ] `Scan_Failed` drawings are not automatically re-enqueued by the ingest task (no Celery retry triggered) [US-009-AC-2]
- [ ] Format detection reads magic bytes from file content; `%PDF` prefix → PDF classification [US-003-AC-3]
- [ ] Format detection reads magic bytes; `AC` prefix → DWG classification [US-003-AC-3]
- [ ] Unrecognised format bytes → `drawing.processing_state` transitions to `Failed` [US-003-AC-3]
- [ ] Unrecognised format → `DrawingStatusSSEEvent` with `state="Failed"` published to Redis [US-003-AC-3]
- [ ] PDF files: `PdfReader` is used to extract page count; `drawing.page_count` is updated in DB [US-003-AC-4]
- [ ] PDF files: scan job is enqueued with `storage_reference` = original S3 object key [US-011-AC-1]
- [ ] DWG files: ODA File Converter is invoked inside the ODA sandbox Docker container [US-003-AC-5]
- [ ] ODA sandbox Docker command includes `--network none` (no network egress) [US-003-AC-5] [MANUAL]
- [ ] ODA sandbox Docker command runs as non-root user [US-003-AC-5] [MANUAL]
- [ ] ODA sandbox Docker command mounts host filesystem read-only (except temp work dir) [US-003-AC-5] [MANUAL]
- [ ] ODA subprocess non-zero exit code → `drawing.processing_state` transitions to `Failed` [US-003-AC-5]
- [ ] ODA subprocess failure → `DrawingStatusSSEEvent` with `state="Failed"` published to Redis [US-003-AC-5]
- [ ] ODA subprocess failure → no scan job is enqueued [US-003-AC-5]
- [ ] On successful DWG conversion, converted PDF is uploaded to S3 at key `converted/{drawing_id}/drawing.pdf` [US-003-AC-6]
- [ ] On successful DWG conversion, a new `StoredFile` record is created in the DB [US-003-AC-6]
- [ ] On successful DWG conversion, `drawing.stored_file_id` is updated to the new `StoredFile` id [US-003-AC-6]
- [ ] `StoredFile` creation and `drawing.stored_file_id` update occur in a single DB transaction [US-003-AC-6]
- [ ] DWG: `drawing.page_count` is updated from the converted PDF's page count [US-003-AC-6]
- [ ] DWG: scan job is enqueued with `storage_reference` = converted PDF S3 key (`converted/{drawing_id}/drawing.pdf`) [US-011-AC-1]
- [ ] Scan job payload contains `user_id` copied verbatim from ingest job payload (no DB lookup) [US-011-AC-2]
- [ ] Scan job payload contains `drawing_id` and `storage_reference` [US-011-AC-1]
- [ ] Scan job is dispatched to `SCAN_QUEUE` using string-based `celery_app.send_task` (no direct import of S2-I code) [US-011-AC-1]
- [ ] If `ODA_LICENSE_EXPIRY_DATE` is within 30 days of today, a `WARNING` log is emitted at startup/conversion time [US-003-AC-7]
- [ ] If `ODA_LICENSE_EXPIRY_DATE` env var is absent, a `WARNING` is logged and conversion is not blocked [US-003-AC-7]
- [ ] A `Failed` drawing that is re-submitted (state reset to `Queued`, new ingest job enqueued) is processed using the existing `stored_file_id` without requiring a new S3 upload [US-009-AC-1]
- [ ] `Scan_Failed` drawing ingest task is no-op (drawing was never in `Queued` state for that invocation) [US-009-AC-2]
- [ ] `DrawingStatusSSEEvent` schema has exactly the fields: `drawing_id` (str), `state` (str), `timestamp` (ISO 8601 UTC str) [US-008-AC-2]
- [ ] Ingest task is registered on the `ingest` Celery queue (verifiable via task name and queue routing) [US-011-AC-1]
- [ ] Redis pub/sub publish failure is logged as error but does NOT cause the Celery task to fail or retry [US-008-AC-2]
- [ ] `drawing.processed_at` is NOT modified by the ingest worker [technical AC — owned by S2-J]
- [ ] Free-tier counter is NOT modified by the ingest worker [technical AC — §1.4 rule 8]

---

##### Independent Test

**Test file path (TDD — written first, must fail before implementation):** `tests/integration/test_ingest_worker.py`

**Exact CI command:**
```bash
pytest tests/integration/test_ingest_worker.py -v
```

**AC → assertion mapping:**

| AC | `it(...)` / `test(...)` name |
|---|---|
| US-008-AC-1 (Scanning transition before file ops) | `test_scanning_state_set_before_s3_download` |
| US-008-AC-1 (SSE event on Scanning) | `test_scanning_state_set_before_s3_download` |
| US-008-AC-3 (no-op if already Scanning+) | `test_noop_if_drawing_already_scanning` |
| US-003-AC-1 (hash mismatch → Scan_Failed) | `test_hash_mismatch_transitions_to_scan_failed` |
| US-003-AC-1 (hash mismatch → SSE event) | `test_hash_mismatch_transitions_to_scan_failed` |
| US-003-AC-1 (hash mismatch → no scan job) | `test_hash_mismatch_transitions_to_scan_failed` |
| US-003-AC-2 (second-gate blocklist → Scan_Failed) | `test_second_gate_blocklist_hit_transitions_to_scan_failed` |
| US-003-AC-2 (second-gate blocklist → SSE event) | `test_second_gate_blocklist_hit_transitions_to_scan_failed` |
| US-003-AC-2 (second-gate blocklist → no scan job) | `test_second_gate_blocklist_hit_transitions_to_scan_failed` |
| US-009-AC-2 (Scan_Failed → no Celery retry) | `test_scan_failed_is_terminal_no_celery_retry` |
| US-003-AC-3 (PDF magic bytes → PDF) | `test_format_detect_pdf_magic_bytes` |
| US-003-AC-3 (DWG magic bytes → DWG) | `test_format_detect_dwg_magic_bytes` |
| US-003-AC-3 (unknown format → Failed) | `test_unknown_format_transitions_to_failed` |
| US-003-AC-4 (PDF page count extraction) | `test_pdf_page_count_updated_on_success` |
| US-003-AC-4 (PDF scan job enqueued with original key) | `test_pdf_scan_job_enqueued_with_correct_storage_reference` |
| US-003-AC-5 (ODA called for DWG) | `test_dwg_triggers_oda_conversion` |
| US-003-AC-5 (ODA failure → Failed) | `test_oda_failure_transitions_to_failed` |
| US-003-AC-5 (ODA failure → SSE event) | `test_oda_failure_transitions_to_failed` |
| US-003-AC-5 (ODA failure → no scan job) | `test_oda_failure_transitions_to_failed` |
| US-003-AC-6 (converted PDF uploaded to S3) | `test_dwg_converted_pdf_uploaded_to_s3` |
| US-003-AC-6 (new StoredFile record created) | `test_dwg_new_stored_file_record_created` |
| US-003-AC-6 (drawing.stored_file_id updated) | `test_dwg_drawing_stored_file_id_updated` |
| US-003-AC-6 (transaction atomicity) | `test_dwg_stored_file_and_drawing_update_atomic` |
| US-003-AC-6 (DWG page count updated) | `test_dwg_page_count_updated_after_conversion` |
| US-011-AC-1 (DWG scan job with converted key) | `test_dwg_scan_job_enqueued_with_converted_storage_reference` |
| US-011-AC-2 (user_id passed through) | `test_user_id_passed_through_to_scan_job_no_db_lookup` |
| US-011-AC-1 (scan job on SCAN_QUEUE) | `test_scan_job_enqueued_on_correct_queue` |
| US-011-AC-1 (string-based dispatch) | `test_scan_job_dispatched_via_send_task_not_direct_import` |
| US-003-AC-7 (ODA expiry warning ≤30 days) | `test_oda_license_expiry_warning_within_30_days` |
| US-003-AC-7 (ODA expiry absent → warning, not blocked) | `test_oda_license_expiry_absent_logs_warning` |
| US-009-AC-1 (retry reuses existing stored_file_id) | `test_retry_reuses_existing_stored_file_id` |
| US-008-AC-2 (SSE event schema) | `test_sse_event_schema_fields` |
| technical (ingest task registered on ingest queue) | `test_ingest_task_registered_on_ingest_queue` |
| technical (Redis publish failure non-fatal) | `test_redis_publish_failure_does_not_fail_task` |
| technical (processed_at not modified) | `test_processed_at_not_modified_by_ingest_worker` |
| technical (free-tier counter not modified) | `test_free_tier_counter_not_modified` |

**Fixtures / test doubles:**

```python
# conftest.py / test file fixtures:

@pytest.fixture
def db_session():
    # From tests/integration/fixtures/db.py (S0-B)
    # Real PostgreSQL test DB with S1-A migrations applied
    ...

@pytest.fixture
def redis_client():
    # From tests/integration/fixtures/redis.py (S0-B)
    # Real Redis test instance
    ...

@pytest.fixture
def s3_client():
    # From tests/integration/fixtures/s3.py (S0-B)
    # localstack S3 with TEST_BUCKET pre-created
    ...

@pytest.fixture
def mock_oda_converter(monkeypatch):
    # Patches subprocess.run / Docker SDK call in oda_converter.py
    # Success: returns exit code 0, writes a minimal valid PDF to the output path
    # Failure variant: returns exit code 1
    ...

@pytest.fixture
def mock_publish_drawing_status(monkeypatch):
    # Patches backend.app.redis.pubsub.publish_drawing_status
    # Records calls for assertion: [(drawing_id, state, timestamp), ...]
    ...

@pytest.fixture
def mock_celery_send_task(monkeypatch):
    # Patches celery_app.send_task
    # Records: [(task_name, args, kwargs, queue), ...]
    ...

# Sample ingest job payloads:
INGEST_JOB_PDF = {
    "drawing_id": "11111111-1111-1111-1111-111111111111",
    "user_id":    "22222222-2222-2222-2222-222222222222",
    "stored_file_id": "33333333-3333-3333-3333-333333333333",
    "storage_reference": "uploads/33333333-3333-3333-3333-333333333333/drawing.pdf",
}

INGEST_JOB_DWG = {
    "drawing_id": "44444444-4444-4444-4444-444444444444",
    "user_id":    "22222222-2222-2222-2222-222222222222",
    "stored_file_id": "55555555-5555-5555-5555-555555555555",
    "storage_reference": "uploads/55555555-5555-5555-5555-555555555555/drawing.dwg",
}

# Minimal valid PDF bytes (magic bytes + minimal structure):
MINIMAL_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n..."

# DWG magic bytes (AutoCAD 2013):
DWG_MAGIC_BYTES = b"AC1027" + b"\x00" * 100

# Expected scan job payload shape:
EXPECTED_SCAN_JOB_PDF = {
    "drawing_id": "11111111-...",
    "user_id":    "22222222-...",
    "storage_reference": "uploads/33333333-.../drawing.pdf",  # original key
}

EXPECTED_SCAN_JOB_DWG = {
    "drawing_id": "44444444-...",
    "user_id":    "22222222-...",
    "storage_reference": "converted/44444444-.../drawing.pdf",  # converted key
}
```

**Pre-conditions:**
- PostgreSQL test DB running (from S0-B docker-compose.fixtures.yml), with S1-A migrations applied (tiers and entity classes seeded)
- Redis test instance running (from S0-B docker-compose.fixtures.yml)
- localstack S3 running with test bucket (from S0-B docker-compose.fixtures.yml)
- Environment variables set: `DATABASE_URL`, `REDIS_URL`, `S3_BUCKET_NAME`, `S3_REGION`, `CELERY_BROKER_URL`, `ODA_CONVERTER_PATH` (pointing to mock script for tests)
- The `ops/oda-sandbox/Dockerfile` image built (or the ODA invocation mocked via `monkeypatch`)
- Celery configured with `CELERY_TASK_ALWAYS_EAGER=True` for synchronous test execution, OR tasks invoked directly via `ingest_task.apply(kwargs=...)`

**Isolation rule:**
This test passes when only S0-A, S0-B, S1-A, S1-C, S1-D, S1-E have merged. It does NOT require S2-I (scan worker), S2-J (ML worker), or S2-B (drawings API) to be merged. Cross-session dispatch (scan job enqueueing) is verified by asserting `mock_celery_send_task` was called with correct arguments — S2-I code is never imported. The test is fully isolated.

---

##### Checkpoint

After this session's PR is merged, running `pytest tests/integration/test_ingest_worker.py -v` passes all tests green, and a manually-seeded `Queued` drawing with a valid PDF in localstack S3 transitions to `Scanning` in the database and a matching `DrawingStatusSSEEvent` appears on the Redis `drawing:status:{drawing_id}` channel when the ingest task is invoked directly.

**Shippability claim:** This PR is independently mergeable to `main` even if no other Phase 2 session in the same wave has merged. It depends only on S0-A, S0-B, S1-A, S1-C, S1-D, S1-E which are Phase 0–1 sessions that have already cleared the Phase 1 → Phase 2 gate.

---

##### Output and handoff

| Export | Kind | Consuming Session(s) | Load-bearing? |
|---|---|---|---|
| `backend/app/workers/ingest/tasks.ingest_task` | Celery task (function) | **S2-B** (drawings upload-complete handler enqueues it) | **[LOAD-BEARING]** — S2-B imports and calls `ingest_task.apply_async(...)` |
| Celery task name string: `"workers.ingest.tasks.ingest_task"` | String constant (queue routing) | **S2-B** (string-based enqueue fallback), **S4-A** (E2E tests) | **[LOAD-BEARING]** — must not change after merge |
| Ingest job payload schema `{drawing_id, user_id, stored_file_id, storage_reference}` | Dict shape contract | **S2-B** (producer), **S4-A** (E2E assertions) | **[LOAD-BEARING]** — field names must not change |
| Scan job payload schema `{drawing_id, user_id, storage_reference}` | Dict shape contract | **S2-I** (consumer in scan worker), **S4-A** | **[LOAD-BEARING]** — S2-I's task signature must match |
| `DrawingStatusSSEEvent` publish to `drawing:status:{drawing_id}` (fields: `drawing_id`, `state`, `timestamp`) | Redis pub/sub event shape | **S2-B** (SSE handler), **S4-A** | **[LOAD-BEARING]** — field names consumed by S2-B's SSE serialiser |
| State transitions: `Queued → Scanning`, `Scanning → Scan_Failed`, `Scanning → Failed` | DB state writes | **S2-B** (polls `drawing.processing_state`), **S4-A** | **[LOAD-BEARING]** — state names are from `DrawingProcessingState` enum |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/test_ingest_worker.py -v",
    "file": "tests/integration/test_ingest_worker.py"
  },
  "checkpoint": "A manually-seeded Queued drawing with a valid PDF in localstack S3 transitions to Scanning in the database and a matching DrawingStatusSSEEvent appears on the Redis drawing:status:{drawing_id} channel when the ingest task is invoked directly, confirmed by pytest tests/integration/test_ingest_worker.py passing green.",
  "manualAcs": [
    {
      "id": "US-003-AC-5-network",
      "text": "ODA sandbox Docker command includes --network none (no network egress)."
    },
    {
      "id": "US-003-AC-5-nonroot",
      "text": "ODA sandbox Docker command runs as non-root user."
    },
    {
      "id": "US-003-AC-5-readonly",
      "text": "ODA sandbox Docker command mounts host filesystem read-only (except temp work dir)."
    }
  ],
  "exports": [
    {
      "kind": "function",
      "name": "ingest_task",
      "shape": "celery.Task — apply_async(kwargs: {drawing_id: str, user_id: str, stored_file_id: str, storage_reference: str}) -> AsyncResult"
    },
    {
      "kind": "module",
      "name": "workers.ingest.tasks",
      "shape": "backend/app/workers/ingest/tasks.py"
    },
    {
      "kind": "type",
      "name": "IngestJobPayload",
      "shape": "{ drawing_id: str; user_id: str; stored_file_id: str; storage_reference: str }"
    },
    {
      "kind": "type",
      "name": "ScanJobPayload",
      "shape": "{ drawing_id: str; user_id: str; storage_reference: str }"
    },
    {
      "kind": "function",
      "name": "detect_format",
      "shape": "(file_bytes: bytes) -> Literal['pdf', 'dwg', 'unsupported']"
    },
    {
      "kind": "function",
      "name": "reverify_hash",
      "shape": "(file_bytes: bytes, expected_sha256: str, db_session: Session) -> Literal['ok', 'mismatch', 'blocked']"
    },
    {
      "kind": "function",
      "name": "convert_dwg_to_pdf",
      "shape": "(dwg_bytes: bytes, drawing_id: str) -> bytes"
    }
  ]
}
```