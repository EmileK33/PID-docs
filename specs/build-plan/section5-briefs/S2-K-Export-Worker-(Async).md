#### S2-K — Export Worker (Async)

**Phase 2 | Real-time/Queue | Needs: S1-A, S1-C, S1-D, S1-E**

---

##### Objective

Implement the Celery-based async export worker that generates CSV and XLSX files for drawings with more than 1,000 symbols, uploads results to S3, updates export record state, and publishes completion notifications via Redis pub/sub so the frontend can inform users their download is ready.

---

##### Scope

**P0 MVP.** All work in this session is P0.

- P0: Async CSV/XLSX generation for large exports (>1,000 symbols threshold enforced upstream by S2-D)
- P0: Export record state machine (Queued → Generating → Complete | Failed)
- P0: S3 upload and stored_file record creation
- P0: Redis pub/sub notification on completion and failure
- P0: Celery retry policy (1 automatic retry before Failed)
- P0: Idempotency guard on duplicate task delivery

**P1 stub required:** Table cell data in export output (US-022, table region export in a separate sheet) — create a clearly-marked `# TODO P1 (US-022): export table cells in second sheet` placeholder in the XLSX generator.

---

##### Technology constraints

**Must use (from §1.8):**
- **Celery** on **Redis** broker — the only permitted async task queue. Must use the shared `celery_app` instance from `backend/app/workers/celery_app.py` (owned by S0-A). Changing broker would require worker rewrite.
- **PostgreSQL** via SQLAlchemy ORM (Alembic-managed schema from S1-A). Connection pool via PgBouncer from Phase 1.
- **Redis** (ElastiCache-compatible) for Celery broker AND pub/sub notifications — same Redis instance, separate logical use.
- **AWS S3-compatible** object storage via the S3 client from S1-C (`backend/app/storage/s3_client.py`).
- **Python** — must match the FastAPI/Celery codebase language.
- **`csv` stdlib** for CSV generation (no pandas dependency introduced here — pandas is an ML worker dependency, not an export worker dependency).
- **`openpyxl`** for XLSX generation — must be added to `backend/pyproject.toml` if not already present.

**Must NOT use:**
- `pandas` — not a declared export worker dependency; adds unnecessary weight to the CPU export worker image.
- Any in-memory queue or threading-based async — violates NFR-7 (queued jobs must survive server restarts; §1.4 rule 14).
- Direct HTTP calls to the FastAPI server from the worker — workers communicate only through DB, queues, and Redis channels (§ session table intra-phase note).

**Must NOT import from S2-D** (`backend/app/services/export_generators.py`) — S2-D is a Phase 2 sibling session with no declared prerequisite relationship to S2-K. The test isolation rule ("test must pass when this session's PR is the only one merged") requires S2-K to be fully self-contained. CSV/XLSX generation logic is implemented within `tasks.py`. Any apparent duplication between S2-D's sync generators and S2-K's async generators is intentional and expected given the intra-phase isolation constraint.

---

##### Performance targets

| Metric | Target | Type |
|---|---|---|
| Async export completion | No explicit P95 SLA stated in spec | Monitoring target |
| Export (<1,000 symbols) — sync path | <30s P95 | Monitoring target (owned by S2-D, not this session) |
| Async export threshold | >1,000 symbols | Hard constraint — evaluated upstream by S2-D at enqueue time; this worker processes whatever arrives on the queue |
| ML job timeout analogy | Celery `time_limit` set to 3600s (1 hr) for export tasks | Hard constraint |

This session owns no P95 SLA directly — see S2-D for sync export SLA.

---

##### Owned files

- `backend/app/workers/export/__init__.py`
- `backend/app/workers/export/tasks.py`
- `tests/integration/test_export_worker.py`

---

##### Read-only imports

| Owning Session | File Path | Named Exports Required |
|---|---|---|
| S0-A | `backend/app/workers/celery_app.py` | `celery_app` (Celery application instance) |
| S0-A | `backend/app/config.py` | `settings` (S3_BUCKET_NAME, REDIS_URL, DATABASE_URL, etc.) |
| S1-A | `backend/app/db/models/export_record.py` | `ExportRecord` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/stored_file.py` | `StoredFile` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/detected_symbol.py` | `DetectedSymbol` (SQLAlchemy model) |
| S1-A | `backend/app/db/models/drawing.py` | `Drawing` (SQLAlchemy model) |
| S1-A | `backend/app/db/session.py` | `SessionLocal` (SQLAlchemy session factory) |
| S1-C | `backend/app/storage/s3_client.py` | `upload_bytes`, `get_s3_client` |
| S1-C | `backend/app/storage/hashing.py` | `sha256_bytes` (compute SHA-256 of bytes in memory) |
| S1-D | `backend/app/redis/pubsub.py` | `publish_event` (publishes JSON payload to Redis channel) |
| S1-D | `backend/app/redis/client.py` | `get_redis_client` |
| S1-E | `backend/app/analytics/events.py` | Not required — no analytics events fire from this worker (see §1.10) |

---

##### Do not touch

- `backend/app/main.py` — entry point, owned by S0-A
- `backend/app/api/routers/__init__.py` — router registry, owned by S0-A
- `backend/app/api/routers/_stubs.py` — stub endpoints, owned by S0-A
- `backend/app/workers/celery_app.py` — Celery app instance, owned by S0-A
- `backend/app/workers/queues.py` — queue routing config, owned by S1-D
- `backend/app/workers/base.py` — base Task class, owned by S1-D
- `backend/app/services/export_generators.py` — sync generators, owned by S2-D
- `backend/app/api/routers/exports.py` — export API endpoints, owned by S2-D
- `backend/app/services/export_service.py` — sync export service + threshold gate, owned by S2-D
- All S1-A model files (`user.py`, `drawing.py`, `detected_symbol.py`, etc.)
- All S1-C storage files
- All S1-D Redis files
- All S1-E analytics files
- All other session-owned files not in the "Owned files" list above

---

##### Architecture context

Verbatim from §1.8 Technology Stack:

> **Async Workers** | Celery on Redis broker | Durable persistent queue (NFR-7); Redis already required for cache + SSE; Celery retry/timeout/priority support; changing broker requires worker rewrite

> **Queue / Cache / SSE pub-sub** | Redis (ElastiCache) | Three-in-one: Celery broker, subscription feature flag cache, SSE pub/sub for drawing status push; single operational dependency

Verbatim from §1.11 Cross-Session Runtime Patterns — Celery Job Queue Names:

> | `export` | Export Worker (CPU) | CSV/XLSX generation |

Verbatim from §1.9 Performance Targets:

> | Export (<1,000 symbols) | <30s P95 | Monitoring target | Export Worker (synchronous generation); pre-signed URL returned on poll completion |
> | Async export threshold | >1,000 symbols triggers async path | Hard constraint | Export Worker; evaluated server-side |

Verbatim from §1.4 Critical Ordering Rules:

> **Rule 14**: ML job must be enqueued via persistent queue (not in-memory) to satisfy NFR-7's requirement that queued jobs survive server restarts. *(applies equally to export jobs — same Celery/Redis infrastructure)*

> **Rule 15**: The 1,000-symbol threshold for triggering async vs. synchronous export (FR-4 AC-3) must be evaluated server-side at job creation time, not client-side, to prevent bypass.

Verbatim from §1.10 Analytics Event Contracts:

> | `export_initiated` | `{ event: 'export_initiated', timestamp: string (UTC ISO8601), user_id: string, drawing_id: string, export_id: string, format: ExportFormat }` | FastAPI — `POST /drawings/{id}/exports` handler | Export job created (both sync and async paths) | Export file generated | Export Worker; browser client |

> | `export_downloaded` | `{ event: 'export_downloaded', ... }` | FastAPI — pre-signed URL access or download endpoint | User accesses pre-signed download URL | None specified | Export Worker |

*(Both analytics events fire from the API layer, S2-D — NOT from this worker.)*

Verbatim from §1.1 Shared Contracts — ExportFormat and ExportStatus:

> ```typescript
> // Export Format
> type ExportFormat = 'csv' | 'xlsx';
>
> // Export Status
> type ExportStatus = 'Queued' | 'Generating' | 'Complete' | 'Failed';
> ```

Verbatim from §1.2 Database Schema — EXPORT_RECORD and STORED_FILE:

> ```sql
> CREATE TABLE export_record (
>   id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>   drawing_id      UUID NOT NULL REFERENCES drawing(id),
>   user_id         UUID NOT NULL REFERENCES "user"(id),
>   format          VARCHAR NOT NULL CHECK (format IN ('csv','xlsx')),
>   status          VARCHAR NOT NULL CHECK (status IN ('Queued','Generating','Complete','Failed')),
>   stored_file_id  UUID REFERENCES stored_file(id),
>   initiated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
>   completed_at    TIMESTAMPTZ
> );
>
> CREATE TABLE stored_file (
>   id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>   bucket       VARCHAR NOT NULL,
>   object_key   VARCHAR NOT NULL,
>   sha256_hash  VARCHAR NOT NULL,
>   file_type    VARCHAR NOT NULL,
>   size_bytes   BIGINT NOT NULL,
>   CONSTRAINT stored_file_object_key_unique UNIQUE (bucket, object_key)
> );
>
> CREATE INDEX idx_stored_file_hash ON stored_file(sha256_hash);
> ```

Verbatim from §1.2 — DETECTED_SYMBOL:

> ```sql
> CREATE TABLE detected_symbol (
>   id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
>   drawing_id      UUID NOT NULL REFERENCES drawing(id) ON DELETE CASCADE,
>   entity_class_id VARCHAR NOT NULL REFERENCES entity_class(id),
>   subtype         VARCHAR,
>   tag_label       VARCHAR,
>   confidence      FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
>   bbox            JSONB NOT NULL,
>   source          VARCHAR NOT NULL CHECK (source IN ('ml','manual')),
>   rejected        BOOLEAN NOT NULL DEFAULT FALSE,
>   page_number     INTEGER NOT NULL
> );
> ```

Verbatim from §1.1 — SymbolRecord (the shape exported):

> ```typescript
> interface SymbolRecord {
>   id: string;
>   drawing_id: string;
>   entity_class_id: EntityClassId;
>   subtype: string;
>   tag_label: string | null;
>   confidence: number;
>   bbox: BoundingBox;
>   source: SymbolSource;
>   rejected: boolean;
>   page_number: number;
> }
> ```

Verbatim from §1.11 — Redis Pub/Sub Channels:

> | `drawing:status:{drawing_id}` | Ingest Worker, Scan Worker, ML Worker (on each state transition) | FastAPI SSE handler (`GET /drawings/{id}/status`) → client | `DrawingStatusSSEEvent` |

*(No export channel is defined in §1.11. S2-K defines the `export:status:{export_id}` channel. This channel must be documented here as the authoritative definition for consuming sessions S3-G and S2-D's GET /exports/{id} polling endpoint.)*

---

##### User stories and acceptance criteria

The following user stories are derived from §1.13 Feature Scope — P0 (MVP):

> **US-017**: Async export queue for >1,000 symbols; in-app notification when ready; async export failure with retry

> **US-016** (async path only): CSV and XLSX export; pre-signed download URL; re-export without overwriting prior exports

---

**US-017: Async Export Worker Processing**

*As a user whose drawing has more than 1,000 symbols, I want my CSV/XLSX export to be generated asynchronously in the background so that the application stays responsive, I am notified when the file is ready, and failures are automatically retried before I am shown an error state.*

**AC-1 (State transition on pickup):** When the export worker picks up a task for an export_record with status `Queued`, it must transition the record to `Generating` before any file generation begins. If the status is already `Generating` or `Complete` at task start (duplicate delivery), the task must exit without error and without re-processing.

**AC-2 (Successful generation — CSV):** When format is `csv` and generation succeeds, the worker must:
- Produce a valid CSV file with a header row and one data row per non-rejected symbol (`rejected = FALSE`) for the drawing, ordered by `page_number ASC, id ASC`.
- CSV columns in order: `id`, `drawing_id`, `page_number`, `entity_class_id`, `subtype`, `tag_label`, `confidence`, `bbox_x`, `bbox_y`, `bbox_w`, `bbox_h`, `source`.
- Upload the file to S3 at object key `exports/{export_id}.csv`.
- Create a `stored_file` record with correct `bucket`, `object_key`, `sha256_hash`, `file_type` (`text/csv`), and `size_bytes`.
- Update `export_record` atomically (single transaction): `status = 'Complete'`, `stored_file_id = <new stored_file.id>`, `completed_at = NOW()`.

**AC-3 (Successful generation — XLSX):** When format is `xlsx` and generation succeeds, the worker must:
- Produce a valid `.xlsx` workbook (openpyxl) with a worksheet named `Symbols` containing a header row and data rows identical in columns and ordering to the CSV format (AC-2).
- Upload to S3 at object key `exports/{export_id}.xlsx`.
- Create a `stored_file` record with `file_type` = `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
- Update `export_record` atomically: `status = 'Complete'`, `stored_file_id`, `completed_at`.
- Include a clearly-marked P1 stub comment: `# TODO P1 (US-022): add 'Tables' worksheet with table cell data`.

**AC-4 (Redis notification on completion):** On successful completion, the worker must publish to Redis channel `export:status:{export_id}` with payload:
```json
{
  "event": "export_complete",
  "export_id": "<uuid>",
  "drawing_id": "<uuid>",
  "user_id": "<uuid>",
  "format": "csv|xlsx",
  "timestamp": "<ISO8601 UTC>"
}
```

**AC-5 (Celery retry on transient failure):** If the generation task raises any exception (S3 upload error, DB error, generation error), Celery must automatically retry the task exactly once (max_retries=1) with a 30-second delay before the retry attempt. The export_record status must NOT be set to `Failed` during the retry window; it remains `Generating` (or is reset to `Generating` if a subsequent attempt starts).

**AC-6 (Failed state after retries exhausted):** After the single retry is also exhausted (exception raised on both attempts), the worker must:
- Update `export_record.status = 'Failed'` (and set `completed_at = NULL`, leaving `stored_file_id = NULL`).
- Publish to Redis channel `export:status:{export_id}` with payload:
```json
{
  "event": "export_failed",
  "export_id": "<uuid>",
  "drawing_id": "<uuid>",
  "user_id": "<uuid>",
  "format": "csv|xlsx",
  "timestamp": "<ISO8601 UTC>"
}
```

**AC-7 (No analytics fired from worker):** The export worker must NOT fire `export_initiated` or `export_downloaded` analytics events. Both are fired by the FastAPI layer (S2-D). Firing them from the worker would cause double-counting.

**AC-8 (No prior export overwritten):** The worker must never overwrite a `stored_file` record from a prior export run for the same drawing. Each export task creates a new `StoredFile` row with a unique `object_key` (`exports/{export_id}.{format}` — export_id is unique per run).

**AC-9 (Only non-rejected symbols exported):** Symbols with `rejected = TRUE` must be excluded from the export output. The SQL query must include `WHERE detected_symbol.drawing_id = :drawing_id AND detected_symbol.rejected = FALSE`.

---

##### UX and design specification

N/A — this is a backend worker session with no frontend component. UX for export status display is owned by S3-G.

---

##### Critical implementation notes

- **Atomicity of export_record final update (AC-2, AC-3):** The INSERT into `stored_file` and the UPDATE of `export_record` (setting `status='Complete'`, `stored_file_id`, `completed_at`) MUST occur within a single database transaction. If the DB commit fails after the S3 upload but before the record update, the task will retry; the retry must handle the case where the S3 object already exists (S3 `put_object` is idempotent by key — same key = overwrite is acceptable here since `export_id` is unique).

- **Idempotency guard on task pickup (AC-1):** Before transitioning to `Generating`, fetch the export_record with `SELECT ... FOR UPDATE` (row-level lock) and check status. If status is NOT `Queued`, return immediately without error. This prevents duplicate Celery delivery from double-processing.

- **Status reset on retry:** When Celery retries the task (attempt 2), the export_record may already be in `Generating` state from attempt 1. The idempotency guard must allow `Generating` as a valid start state for a retry (not just `Queued`). Specifically: if status ∈ {`Queued`, `Generating`}, proceed; if status ∈ {`Complete`, `Failed`}, abort.

- **user_id in job payload (§1.4 rule 5):** "The user ID must be written into the job payload at enqueue time (by the API layer that has authenticated session context) so that worker processes can include it in emitted events without requiring a database lookup or session access." The Celery task signature must accept `user_id` as a first-class parameter; the worker must not fetch `user_id` from the DB.

- **No analytics from worker (§1.10):** Both `export_initiated` and `export_downloaded` are explicitly assigned to the FastAPI layer. Firing from the worker would produce duplicate events and violates the "Must NEVER fire from: Export Worker" column in §1.10. Do NOT import or call any analytics emitter from S1-E in this worker.

- **Async export threshold gate is upstream:** The 1,000-symbol threshold is evaluated by S2-D at enqueue time (§1.4 rule 15). The worker does not re-evaluate it; it generates exports for any task it receives on the `export` queue.

- **Queue name:** Must use the `export` queue name exactly as defined in §1.11. The task `@celery_app.task(queue='export', ...)` routing must match `backend/app/workers/queues.py` (S1-D). Do not hardcode a different queue name.

- **Celery task registration:** The task must be imported/registered so `celery_app` discovers it on worker startup. The `__init__.py` must import `generate_export` from `tasks.py`. The Celery `include` list in `celery_app.py` (S0-A) should already include `backend.app.workers.export.tasks` — verify this matches the S0-A stub before wiring up.

- **S3 object key uniqueness:** Using `exports/{export_id}.{format}` as the object key guarantees uniqueness per export job (UUID export_id). This satisfies AC-8 (no prior export overwritten) without any additional key-uniqueness logic.

- **`stored_file.object_key` unique constraint:** The `stored_file` table has `CONSTRAINT stored_file_object_key_unique UNIQUE (bucket, object_key)` (§1.2). Since object keys are export_id-scoped, this constraint will never fire for normal operation. For retry paths (same export_id), the retry must handle `UniqueViolation` gracefully by reading the existing `stored_file` row instead of re-inserting.

- **No CDN for export files:** §1.7 states "No CDN for export files (confidential)." Pre-signed URL generation is done by S2-D's `GET /exports/{id}` endpoint, not by the worker. The worker only uploads the raw file to S3; it does NOT generate pre-signed URLs.

- **P1 stub placement (US-022):** In the XLSX generator function, after writing the `Symbols` worksheet, add:
  ```python
  # TODO P1 (US-022): add 'Tables' worksheet
  # Expected: iterate table_cell rows for drawing_id, write to second sheet
  # Prerequisite: US-021 ML table extraction must be complete
  pass
  ```

- **Silent failure mode — DB session leak:** If the task opens a `SessionLocal()` and raises before commit, the session must be explicitly closed in a `finally` block. Failure to close sessions under Celery worker processes causes connection pool exhaustion (PgBouncer pool depletion) without any obvious error message.

- **Silent failure mode — export_record left in Generating on worker crash:** If the worker process is killed mid-task (OOM, node termination), the export_record remains in `Generating` state permanently. The idempotency guard's acceptance of `Generating` as a valid start state ensures that if Celery re-delivers the task (via `acks_late=True` + visibility timeout), the task can recover. Set `acks_late=True` on the task to enable this behavior.

---

##### Mocking contract

This is a backend worker session. The following internal contracts are consumed:

**Celery task payload** (enqueued by S2-D's `export_service.py`):
```python
# Celery task call signature (S2-D calls this at enqueue time):
generate_export.apply_async(
    kwargs={
        "export_id": str,    # UUID — export_record.id
        "drawing_id": str,   # UUID — drawing.id
        "user_id": str,      # UUID — authenticated user from API session context
        "format": str,       # "csv" | "xlsx"
    },
    queue="export"
)
```

**Redis pub/sub output** (consumed by S3-G's `useExportStatus.ts` and `notificationsStore.ts`):

Channel: `export:status:{export_id}`

Completion payload:
```json
{
  "event": "export_complete",
  "export_id": "uuid-string",
  "drawing_id": "uuid-string",
  "user_id": "uuid-string",
  "format": "csv",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

Failure payload:
```json
{
  "event": "export_failed",
  "export_id": "uuid-string",
  "drawing_id": "uuid-string",
  "user_id": "uuid-string",
  "format": "csv",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**S3 upload contract** (from S1-C `s3_client.py`):
```python
upload_bytes(
    bucket: str,
    object_key: str,
    data: bytes,
    content_type: str
) -> None  # raises StorageError on failure
```

**Redis publish contract** (from S1-D `pubsub.py`):
```python
publish_event(
    channel: str,
    payload: dict
) -> None  # fire-and-forget; logs on failure
```

**DB models used** (from S1-A):
- `ExportRecord`: `id`, `drawing_id`, `user_id`, `format`, `status`, `stored_file_id`, `initiated_at`, `completed_at`
- `StoredFile`: `id`, `bucket`, `object_key`, `sha256_hash`, `file_type`, `size_bytes`
- `DetectedSymbol`: `id`, `drawing_id`, `entity_class_id`, `subtype`, `tag_label`, `confidence`, `bbox` (JSONB), `source`, `rejected`, `page_number`

---

##### Acceptance criteria checklist

- [ ] When task is received for export_record with status `Queued`, record transitions to `Generating` before file generation starts [US-017 AC-1]
- [ ] When export_record is already `Generating` at task start (duplicate delivery), task exits without error and without re-processing [US-017 AC-1]
- [ ] When export_record is `Complete` at task start, task exits without error [US-017 AC-1]
- [ ] CSV output contains header row with columns: `id`, `drawing_id`, `page_number`, `entity_class_id`, `subtype`, `tag_label`, `confidence`, `bbox_x`, `bbox_y`, `bbox_w`, `bbox_h`, `source` [US-017 AC-2]
- [ ] CSV output contains exactly one data row per non-rejected symbol for the drawing, ordered by `page_number ASC, id ASC` [US-017 AC-2]
- [ ] CSV file is uploaded to S3 at key `exports/{export_id}.csv` [US-017 AC-2]
- [ ] `stored_file` record created with correct `bucket`, `object_key`, `sha256_hash`, `file_type='text/csv'`, `size_bytes` [US-017 AC-2]
- [ ] `export_record` updated atomically in single transaction: `status='Complete'`, `stored_file_id` set, `completed_at` set [US-017 AC-2]
- [ ] XLSX output contains a worksheet named `Symbols` with identical column structure to CSV [US-017 AC-3]
- [ ] XLSX file is uploaded to S3 at key `exports/{export_id}.xlsx` [US-017 AC-3]
- [ ] XLSX `stored_file` record has `file_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'` [US-017 AC-3]
- [ ] XLSX file contains P1 stub comment for table cell worksheet [US-017 AC-3]
- [ ] On successful completion, Redis channel `export:status:{export_id}` receives `export_complete` event with correct `export_id`, `drawing_id`, `user_id`, `format`, `timestamp` [US-017 AC-4]
- [ ] On first exception, Celery retries the task (does not set Failed immediately) [US-017 AC-5]
- [ ] After both attempts fail, `export_record.status` is set to `Failed` [US-017 AC-6]
- [ ] After all retries exhausted, Redis channel `export:status:{export_id}` receives `export_failed` event [US-017 AC-6]
- [ ] Worker does not call any analytics emitter function (no `posthog_client` or `events.py` import) [US-017 AC-7]
- [ ] Each export task creates a new `stored_file` row; existing `stored_file` records for the same drawing are not overwritten [US-017 AC-8] [MANUAL]
- [ ] Symbols with `rejected=TRUE` are excluded from CSV output row count [US-017 AC-9]
- [ ] Symbols with `rejected=TRUE` are excluded from XLSX output row count [US-017 AC-9]
- [ ] `SELECT ... FOR UPDATE` (row lock) is used on `export_record` fetch to prevent double-processing under concurrent delivery
- [ ] DB session is closed in `finally` block regardless of success or exception path
- [ ] `acks_late=True` is set on the Celery task to support recovery after worker crash
- [ ] Task is registered on `queue='export'` exactly as named in §1.11
- [ ] `user_id` is sourced from task payload, not from a DB lookup in the worker

---

##### Independent Test

- **Test file path** (TDD — written first, must fail before implementation): `tests/integration/test_export_worker.py`
- **Exact CI command**: `pytest tests/integration/test_export_worker.py -v`

**AC → assertion mapping:**

| AC | `it(...)` / `test(...)` block |
|---|---|
| US-017 AC-1 (Queued → Generating transition) | `test_task_transitions_to_generating_on_pickup` |
| US-017 AC-1 (duplicate delivery — already Generating) | `test_task_is_idempotent_when_already_generating` |
| US-017 AC-1 (duplicate delivery — already Complete) | `test_task_is_idempotent_when_already_complete` |
| US-017 AC-2 (CSV header row columns) | `test_csv_export_header_columns` |
| US-017 AC-2 (CSV data rows — non-rejected only, ordered) | `test_csv_export_data_rows_exclude_rejected_ordered` |
| US-017 AC-2 (CSV S3 upload key) | `test_csv_s3_upload_key` |
| US-017 AC-2 (stored_file record CSV) | `test_stored_file_record_created_csv` |
| US-017 AC-2 (export_record atomic update Complete) | `test_export_record_set_complete_atomically` |
| US-017 AC-3 (XLSX Symbols worksheet columns) | `test_xlsx_export_symbols_worksheet_columns` |
| US-017 AC-3 (XLSX S3 upload key) | `test_xlsx_s3_upload_key` |
| US-017 AC-3 (XLSX stored_file content-type) | `test_stored_file_record_created_xlsx` |
| US-017 AC-3 (XLSX P1 stub present) | `test_xlsx_p1_stub_comment_present` |
| US-017 AC-4 (Redis export_complete published) | `test_redis_notification_published_on_success` |
| US-017 AC-5 (retry on first exception) | `test_celery_retries_on_first_exception` |
| US-017 AC-6 (Failed state after retries exhausted) | `test_export_record_set_failed_after_max_retries` |
| US-017 AC-6 (Redis export_failed published) | `test_redis_failure_notification_published` |
| US-017 AC-7 (no analytics fired) | `test_no_analytics_events_fired_from_worker` |
| US-017 AC-9 (rejected symbols excluded from CSV) | `test_csv_export_data_rows_exclude_rejected_ordered` |
| US-017 AC-9 (rejected symbols excluded from XLSX) | `test_xlsx_export_data_rows_exclude_rejected` |
| Row lock on pickup | `test_row_lock_used_on_export_record_fetch` |
| Session closed in finally | `test_db_session_closed_on_exception` |
| acks_late=True | `test_task_has_acks_late_true` |
| queue='export' | `test_task_registered_on_export_queue` |
| user_id from payload not DB | `test_user_id_sourced_from_payload_not_db` |

**Fixtures / test doubles:**

```python
# Fixture: mock_export_record_queued
# Shape matches ExportRecord SQLAlchemy model:
{
    "id": "aaaaaaaa-0000-0000-0000-000000000001",
    "drawing_id": "bbbbbbbb-0000-0000-0000-000000000001",
    "user_id": "cccccccc-0000-0000-0000-000000000001",
    "format": "csv",
    "status": "Queued",
    "stored_file_id": None,
    "initiated_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    "completed_at": None,
}

# Fixture: mock_detected_symbols (5 non-rejected + 2 rejected)
# Each matches DetectedSymbol model:
[
    {
        "id": "dddddddd-0000-0000-0000-00000000000{i}",
        "drawing_id": "bbbbbbbb-0000-0000-0000-000000000001",
        "entity_class_id": "valve_gate",
        "subtype": "gate",
        "tag_label": f"V-{i}",
        "confidence": 0.95,
        "bbox": {"x": 10.0, "y": 20.0, "w": 30.0, "h": 40.0},
        "source": "ml",
        "rejected": False,  # True for the 2 rejected fixtures
        "page_number": 1,
    }
    for i in range(7)  # indices 5,6 have rejected=True
]

# Mock: mock_s3_upload (S1-C s3_client.upload_bytes)
# Returns None on success, raises StorageError on failure

# Mock: mock_redis_publish (S1-D pubsub.publish_event)
# Returns None; call args captured for assertion

# Mock: mock_db_session (unittest.mock.MagicMock)
# Mocks SessionLocal().__enter__, query(), filter(), with_for_update(), all(), add(), commit(), close()
```

**Pre-conditions:**

- No live DB, S3, or Redis connections required — all mocked via `unittest.mock.patch` or `pytest-mock`.
- `openpyxl` must be installed (`backend/pyproject.toml`).
- `backend/app/workers/export/tasks.py` must exist and import `celery_app` from S0-A stub and DB models from S1-A stubs; test pre-conditions assume S0-A and S1-A stubs are present (Phase 0 and Phase 1 gates cleared).
- No migrations required — tests do not hit a live DB.

**Isolation rule:**

All external dependencies (DB, S3, Redis) are mocked. The test file depends only on:
1. S0-A stub `celery_app` being importable (Phase 0 gate cleared — required before Phase 2).
2. S1-A model stubs being importable (Phase 1 gate cleared — required before Phase 2).
3. S1-C `upload_bytes` being importable (Phase 1 gate cleared).
4. S1-D `publish_event` being importable (Phase 1 gate cleared).

No sibling Phase 2 session (S2-D, S2-H, etc.) needs to have merged. The test passes in full isolation within its wave.

---

##### Checkpoint

- **One-sentence observable outcome**: Running `pytest tests/integration/test_export_worker.py -v` reports all 25 tests passing, confirming the async export Celery task correctly transitions an `ExportRecord` from `Queued` through `Generating` to `Complete` (or `Failed`), writes a valid CSV/XLSX to S3, creates a `StoredFile` record, and publishes the expected Redis notification payload to `export:status:{export_id}`.
- **Shippability claim**: This PR is independently mergeable to `main` even if no other session in the same wave has merged — all external dependencies are mocked; the worker registers on the `export` Celery queue and is discoverable by `celery_app` without any sibling Phase 2 session being present.

---

##### Output and handoff

| Export | Kind | Consuming Session(s) | Load-bearing? |
|---|---|---|---|
| `generate_export` Celery task (importable at `backend.app.workers.export.tasks`) | Celery task | S2-D (enqueues it via `apply_async`), S4-A (E2E tests) | [LOAD-BEARING] — S2-D's `export_service.py` calls `generate_export.apply_async(...)` by module path |
| Redis channel `export:status:{export_id}` contract (payload shape: `export_complete` / `export_failed`) | Event contract | S3-G (`useExportStatus.ts`, `notificationsStore.ts`), S2-D (`GET /exports/{id}` may subscribe) | [LOAD-BEARING] — field names and event types must not change after merge |
| `ExportTaskPayload` type (implicit: `export_id`, `drawing_id`, `user_id`, `format`) | Celery kwargs contract | S2-D (caller), S4-A (E2E) | [LOAD-BEARING] — kwarg names must not change |

---

```json
{
  "test": {
    "cmd": "pytest tests/integration/test_export_worker.py -v",
    "file": "tests/integration/test_export_worker.py"
  },
  "checkpoint": "Running `pytest tests/integration/test_export_worker.py -v` reports all 25 tests passing, confirming the async export Celery task correctly transitions an ExportRecord from Queued through Generating to Complete (or Failed), writes a valid CSV/XLSX to S3, creates a StoredFile record, and publishes the expected Redis notification payload to export:status:{export_id}.",
  "manualAcs": [
    {
      "id": "US-017-AC-8",
      "text": "Each export task creates a new stored_file row; existing stored_file records for the same drawing are not overwritten."
    }
  ],
  "exports": [
    {
      "kind": "function",
      "name": "generate_export",
      "shape": "(self, export_id: str, drawing_id: str, user_id: str, format: str) -> None"
    },
    {
      "kind": "module",
      "name": "backend.app.workers.export.tasks",
      "shape": "backend/app/workers/export/tasks.py"
    },
    {
      "kind": "type",
      "name": "ExportStatusChannel",
      "shape": "\"export:status:{export_id}\" — Redis pub/sub channel name pattern"
    },
    {
      "kind": "type",
      "name": "ExportCompletePayload",
      "shape": "{ event: 'export_complete'; export_id: string; drawing_id: string; user_id: string; format: 'csv' | 'xlsx'; timestamp: string }"
    },
    {
      "kind": "type",
      "name": "ExportFailedPayload",
      "shape": "{ event: 'export_failed'; export_id: string; drawing_id: string; user_id: string; format: 'csv' | 'xlsx'; timestamp: string }"
    }
  ]
}
```